from argparse import ArgumentParser
from pathlib import Path
from typing import Iterable, List, Tuple

from PIL import Image


def rgb888_to_rgb565(r: int, g: int, b: int) -> int:
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def crop_box_for_aspect_ratio(
    image_size: Tuple[int, int],
    target_width: int,
    target_height: int,
    crop_position: Tuple[float, float] = (0.5, 0.5),
) -> Tuple[int, int, int, int]:
    """Return the largest target-aspect crop box at a normalized position."""
    src_width, src_height = image_size
    if src_width <= 0 or src_height <= 0 or target_width <= 0 or target_height <= 0:
        raise ValueError("Image and target dimensions must be greater than zero")

    position_x = max(0.0, min(1.0, float(crop_position[0])))
    position_y = max(0.0, min(1.0, float(crop_position[1])))
    src_ratio = src_width / src_height
    target_ratio = target_width / target_height

    if abs(src_ratio - target_ratio) < 1e-9:
        return (0, 0, src_width, src_height)

    if src_ratio > target_ratio:
        crop_width = min(src_width, round(src_height * target_ratio))
        left = round((src_width - crop_width) * position_x)
        return (left, 0, left + crop_width, src_height)

    crop_height = min(src_height, round(src_width / target_ratio))
    top = round((src_height - crop_height) * position_y)
    return (0, top, src_width, top + crop_height)


def crop_to_aspect_ratio(
    img: Image.Image,
    target_width: int,
    target_height: int,
    crop_position: Tuple[float, float] = (0.5, 0.5),
) -> Image.Image:
    return img.crop(crop_box_for_aspect_ratio(img.size, target_width, target_height, crop_position))


def prepare_image(
    image_path: str,
    width: int,
    height: int,
    crop: bool = True,
    crop_position: Tuple[float, float] = (0.5, 0.5),
) -> Image.Image:
    img = Image.open(image_path).convert("RGB")
    if crop:
        img = crop_to_aspect_ratio(img, width, height, crop_position)
    return img.resize((width, height), Image.Resampling.LANCZOS)


def pack_mono_pixels(img: Image.Image, threshold: int = 128) -> List[int]:
    width, height = img.size
    grayscale = img.convert("L")
    pixels = grayscale.load()
    data: List[int] = []
    byte = 0
    bit_count = 0

    for y in range(height):
        for x in range(width):
            bit = 1 if pixels[x, y] >= threshold else 0
            byte = (byte << 1) | bit
            bit_count += 1
            if bit_count == 8:
                data.append(byte & 0xFF)
                byte = 0
                bit_count = 0

    if bit_count != 0:
        byte <<= (8 - bit_count)
        data.append(byte & 0xFF)

    return data


def image_to_uint8_data(
    img: Image.Image,
    mode: str,
    endian: str = "little",
    mono_threshold: int = 128,
) -> List[int]:
    width, height = img.size
    pixels = img.load()
    data: List[int] = []
    mode = mode.lower()
    endian = endian.lower()

    if mode == "mono":
        return pack_mono_pixels(img, threshold=mono_threshold)

    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            if mode == "rgb888":
                data.extend((r, g, b))
            elif mode == "rgb565":
                rgb565 = rgb888_to_rgb565(r, g, b)
                if endian == "big":
                    data.extend(((rgb565 >> 8) & 0xFF, rgb565 & 0xFF))
                else:
                    data.extend((rgb565 & 0xFF, (rgb565 >> 8) & 0xFF))
            else:
                raise ValueError(f"Unsupported mode: {mode}")

    return data


def write_header(
    output_path: str,
    array_name: str,
    width: int,
    height: int,
    data: Iterable[int],
    mode: str,
    endian: str = "little",
    mono_threshold: int = 128,
) -> None:
    output_path = Path(output_path)
    data_list = list(data)

    with output_path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(f"#ifndef {array_name.upper()}_H\n")
        f.write(f"#define {array_name.upper()}_H\n\n")
        f.write("#include <stdint.h>\n\n")
        f.write("#ifndef IMAGE_INFO_T_DEFINED\n")
        f.write("#define IMAGE_INFO_T_DEFINED\n")
        f.write("typedef enum {\n")
        f.write("    IMAGE_FORMAT_MONO = 0,\n")
        f.write("    IMAGE_FORMAT_RGB888 = 1,\n")
        f.write("    IMAGE_FORMAT_RGB565 = 2,\n")
        f.write("} image_format_t;\n\n")
        f.write("typedef enum {\n")
        f.write("    IMAGE_ENDIAN_LITTLE = 0,\n")
        f.write("    IMAGE_ENDIAN_BIG = 1,\n")
        f.write("} image_endian_t;\n\n")
        f.write("typedef struct __attribute__((packed)) {\n")
        f.write("    uint16_t width;\n")
        f.write("    uint16_t height;\n")
        f.write("    uint8_t format;\n")
        f.write("    uint8_t endian;\n")
        f.write("    uint16_t bits_per_pixel;\n")
        f.write("    uint32_t data_size;\n")
        f.write("    uint16_t mono_threshold;\n")
        f.write("} image_info_t;\n")
        f.write("#endif\n\n")
        format_value = "IMAGE_FORMAT_MONO" if mode == "mono" else ("IMAGE_FORMAT_RGB888" if mode == "rgb888" else "IMAGE_FORMAT_RGB565")
        endian_value = "IMAGE_ENDIAN_BIG" if endian == "big" else "IMAGE_ENDIAN_LITTLE"
        if mode != "rgb565":
            endian_value = "IMAGE_ENDIAN_LITTLE"
        f.write(f"static const image_info_t {array_name}_info = {{\n")
        f.write(f"    .width = {width},\n")
        f.write(f"    .height = {height},\n")
        f.write(f"    .format = {format_value},\n")
        f.write(f"    .endian = {endian_value},\n")
        f.write(f"    .bits_per_pixel = {1 if mode == 'mono' else (24 if mode == 'rgb888' else 16)},\n")
        f.write(f"    .data_size = {len(data_list)},\n")
        f.write(f"    .mono_threshold = {mono_threshold},\n")
        f.write("};\n\n")
        f.write(f"static const uint8_t {array_name}[] = {{\n")

        for i, value in enumerate(data_list):
            if i % 16 == 0:
                f.write("    ")
            f.write(f"0x{value:02X}, ")
            if (i + 1) % 16 == 0:
                f.write("\n")

        if len(data_list) % 16 != 0:
            f.write("\n")

        f.write("};\n\n")
        f.write(f"#endif // {array_name.upper()}_H\n")


def convert_to_header(
    image_path: str,
    output_path: str,
    array_name: str = "my_image",
    width: int = 240,
    height: int = 320,
    crop: bool = True,
    mode: str = "rgb565",
    endian: str = "little",
    mono_threshold: int = 128,
    crop_position: Tuple[float, float] = (0.5, 0.5),
) -> None:
    img = prepare_image(image_path, width, height, crop=crop, crop_position=crop_position)
    data = image_to_uint8_data(img, mode=mode, endian=endian, mono_threshold=mono_threshold)
    write_header(
        output_path=output_path,
        array_name=array_name,
        width=width,
        height=height,
        data=data,
        mode=mode,
        endian=endian,
        mono_threshold=mono_threshold,
    )

    print(
        f"Wrote {len(data)} bytes to {output_path} "
        f"({width}x{height}, mode={mode}, endian={endian})"
    )


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Convert an image to a uint8_t C header.")
    parser.add_argument("image_path", help="Source image path")
    parser.add_argument("output_path", help="Output header path")
    parser.add_argument("--name", default="my_image", help="Array name in the header")
    parser.add_argument("--width", type=int, default=240, help="Target width after resize")
    parser.add_argument("--height", type=int, default=320, help="Target height after resize")
    parser.add_argument("--no-crop", action="store_true", help="Disable aspect-ratio crop")
    parser.add_argument("--mode", choices=["mono", "rgb888", "rgb565"], default="rgb565")
    parser.add_argument("--endian", choices=["little", "big"], default="little")
    parser.add_argument("--mono-threshold", type=int, default=128)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    convert_to_header(
        args.image_path,
        args.output_path,
        array_name=args.name,
        width=args.width,
        height=args.height,
        crop=not args.no_crop,
        mode=args.mode,
        endian=args.endian,
        mono_threshold=args.mono_threshold,
    )


if __name__ == "__main__":
    main()
