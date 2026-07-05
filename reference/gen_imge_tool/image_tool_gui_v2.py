import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from image_converter import crop_box_for_aspect_ratio, convert_to_header, prepare_image


class ImageToolApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Image C Header Tool")
        self.geometry("920x620")
        self.minsize(920, 620)

        self.image_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.array_name = tk.StringVar(value="my_image")
        self.width = tk.StringVar(value="240")
        self.height = tk.StringVar(value="320")
        self.mode = tk.StringVar(value="rgb565")
        self.endian = tk.StringVar(value="little")
        self.crop = tk.BooleanVar(value=True)
        self.mono_threshold = tk.StringVar(value="128")
        self.status = tk.StringVar(value="Chọn ảnh rồi bấm Generate.")
        self.preview_mode_text = tk.StringVar(value="Preview")
        self.preview_image = None
        self.crop_position = [0.5, 0.5]
        self._canvas_image_rect = None
        self._canvas_crop_rect = None
        self._drag_offset = (0.0, 0.0)

        self._build_ui()
        self._sync_endian_state()
        self._set_threshold(128)

    def _build_ui(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(6, weight=1)

        pad = {"padx": 8, "pady": 6}

        ttk.Label(self, text="Input image").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(self, textvariable=self.image_path).grid(row=0, column=1, sticky="ew", **pad)
        ttk.Button(self, text="Browse", command=self._choose_input).grid(row=0, column=2, **pad)

        ttk.Label(self, text="Output header").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(self, textvariable=self.output_path).grid(row=1, column=1, sticky="ew", **pad)
        ttk.Button(self, text="Save As", command=self._choose_output).grid(row=1, column=2, **pad)

        form = ttk.Frame(self)
        form.grid(row=2, column=0, columnspan=3, sticky="ew", **pad)
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)
        form.columnconfigure(5, weight=1)

        ttk.Label(form, text="Array name").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.array_name, width=16).grid(row=0, column=1, sticky="w", padx=(4, 16))
        ttk.Label(form, text="Width").grid(row=0, column=2, sticky="w")
        ttk.Entry(form, textvariable=self.width, width=8).grid(row=0, column=3, sticky="w", padx=(4, 16))
        ttk.Label(form, text="Height").grid(row=0, column=4, sticky="w")
        ttk.Entry(form, textvariable=self.height, width=8).grid(row=0, column=5, sticky="w", padx=(4, 0))

        options = ttk.Frame(self)
        options.grid(row=3, column=0, columnspan=3, sticky="ew", **pad)
        options.columnconfigure(1, weight=1)

        ttk.Label(options, text="Mode").grid(row=0, column=0, sticky="w")
        mode_frame = ttk.Frame(options)
        mode_frame.grid(row=0, column=1, sticky="w")
        for idx, value in enumerate(("mono", "rgb888", "rgb565")):
            ttk.Radiobutton(
                mode_frame,
                text=value.upper() if value != "rgb565" else "RGB565",
                value=value,
                variable=self.mode,
                command=self._sync_endian_state,
            ).grid(row=0, column=idx, padx=(0, 12))

        ttk.Label(options, text="Endian").grid(row=1, column=0, sticky="w", pady=(8, 0))
        endian_frame = ttk.Frame(options)
        endian_frame.grid(row=1, column=1, sticky="w", pady=(8, 0))
        self.endian_little = ttk.Radiobutton(endian_frame, text="Little", value="little", variable=self.endian)
        self.endian_big = ttk.Radiobutton(endian_frame, text="Big", value="big", variable=self.endian)
        self.endian_little.grid(row=0, column=0, padx=(0, 12))
        self.endian_big.grid(row=0, column=1, padx=(0, 12))

        ttk.Checkbutton(
            self,
            text="Crop theo tỉ lệ trước khi resize",
            variable=self.crop,
            command=self._update_preview,
        ).grid(
            row=4, column=0, columnspan=2, sticky="w", **pad
        )

        threshold_frame = ttk.Frame(self)
        threshold_frame.grid(row=4, column=2, sticky="e", **pad)
        ttk.Label(threshold_frame, text="Mono threshold").grid(row=0, column=0, sticky="e")
        self.threshold_scale = ttk.Scale(
            threshold_frame,
            from_=0,
            to=255,
            orient="horizontal",
            command=self._on_threshold_slide,
            length=170,
        )
        self.threshold_scale.grid(row=0, column=1, padx=(4, 0))
        ttk.Entry(threshold_frame, textvariable=self.mono_threshold, width=6).grid(row=0, column=2, padx=(8, 0))

        actions = ttk.Frame(self)
        actions.grid(row=5, column=0, columnspan=3, sticky="ew", **pad)
        actions.columnconfigure(0, weight=1)

        ttk.Button(actions, text="Refresh preview", command=self._update_preview).grid(row=0, column=0, sticky="w")
        ttk.Button(actions, text="Preview size", command=self._preview_size).grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Button(actions, text="Generate", command=self._generate).grid(row=0, column=2, sticky="e")

        self.preview_frame = ttk.LabelFrame(self, text=self.preview_mode_text.get())
        self.preview_frame.grid(row=6, column=0, columnspan=3, sticky="nsew", padx=8, pady=(4, 4))
        self.preview_frame.columnconfigure(0, weight=1)
        self.preview_frame.rowconfigure(0, weight=1)
        self.preview_canvas = tk.Canvas(self.preview_frame, highlightthickness=0, background="#202020")
        self.preview_canvas.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.preview_canvas.bind("<Configure>", lambda _event: self._render_preview())
        self.preview_canvas.bind("<ButtonPress-1>", self._start_crop_drag)
        self.preview_canvas.bind("<B1-Motion>", self._drag_crop)
        self.preview_canvas.bind("<ButtonRelease-1>", lambda _event: self._render_preview())

        ttk.Separator(self, orient="horizontal").grid(row=7, column=0, columnspan=3, sticky="ew", padx=8, pady=(4, 4))
        ttk.Label(self, textvariable=self.status, anchor="w").grid(row=8, column=0, columnspan=3, sticky="ew", padx=8)

        self.bind("<Control-o>", lambda _event: self._choose_input())
        self.bind("<Control-s>", lambda _event: self._choose_output())
        self.bind("<Control-g>", lambda _event: self._generate())

    def _choose_input(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose image",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.bmp *.webp *.gif"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return

        self.image_path.set(path)
        self.crop_position[:] = [0.5, 0.5]
        if not self.output_path.get():
            base, _ = os.path.splitext(path)
            self.output_path.set(base + ".h")
        self._update_preview()

    def _choose_output(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save header as",
            defaultextension=".h",
            filetypes=[("Header files", "*.h"), ("All files", "*.*")],
        )
        if path:
            self.output_path.set(path)

    def _set_threshold(self, value: int) -> None:
        value = max(0, min(255, int(value)))
        self.mono_threshold.set(str(value))
        self.threshold_scale.set(value)

    def _sync_endian_state(self) -> None:
        enabled = self.mode.get() == "rgb565"
        state = "normal" if enabled else "disabled"
        self.endian_little.configure(state=state)
        self.endian_big.configure(state=state)
        self._update_preview()

    def _on_threshold_slide(self, value: str) -> None:
        self.mono_threshold.set(str(int(float(value))))
        self._update_preview()

    def _set_preview_title(self, text: str) -> None:
        self.preview_mode_text.set(text)
        self.preview_frame.configure(text=text)

    def _render_preview(self, max_size=(760, 360)) -> None:
        path = self.image_path.get().strip()
        if not path:
            self.preview_canvas.delete("all")
            self.preview_canvas.create_text(380, 180, text="No image selected", fill="white")
            self.preview_image = None
            return

        try:
            width = int(self.width.get())
            height = int(self.height.get())
            source = Image.open(path).convert("RGB")
        except Exception as exc:
            self.preview_canvas.delete("all")
            self.preview_canvas.create_text(380, 180, text=f"Preview unavailable: {exc}", fill="white")
            self.preview_image = None
            return

        preview = source.copy()
        if self.mode.get() == "mono":
            threshold = int(self.mono_threshold.get() or 128)
            grayscale = preview.convert("L")
            preview = grayscale.point(lambda p: 255 if p >= threshold else 0, mode="L").convert("RGB")
            self._set_preview_title(f"Preview - mono threshold {threshold}")
        elif self.mode.get() == "rgb565":
            self._set_preview_title(f"Preview - rgb565 {self.endian.get()} endian")
        else:
            self._set_preview_title("Preview - rgb888")

        canvas_width = max(1, self.preview_canvas.winfo_width())
        canvas_height = max(1, self.preview_canvas.winfo_height())
        preview.thumbnail((min(max_size[0], canvas_width), min(max_size[1], canvas_height)), Image.Resampling.LANCZOS)
        self.preview_image = ImageTk.PhotoImage(preview)
        x0 = (canvas_width - preview.width) / 2
        y0 = (canvas_height - preview.height) / 2
        self._canvas_image_rect = (x0, y0, x0 + preview.width, y0 + preview.height)
        self.preview_canvas.delete("all")
        self.preview_canvas.create_image(x0, y0, image=self.preview_image, anchor="nw")

        if self.crop.get():
            box = crop_box_for_aspect_ratio(source.size, width, height, tuple(self.crop_position))
            scale_x = preview.width / source.width
            scale_y = preview.height / source.height
            crop_rect = (
                x0 + box[0] * scale_x, y0 + box[1] * scale_y,
                x0 + box[2] * scale_x, y0 + box[3] * scale_y,
            )
            self._canvas_crop_rect = crop_rect
            left, top, right, bottom = crop_rect
            shade = {"fill": "black", "stipple": "gray50", "outline": ""}
            self.preview_canvas.create_rectangle(x0, y0, x0 + preview.width, top, **shade)
            self.preview_canvas.create_rectangle(x0, bottom, x0 + preview.width, y0 + preview.height, **shade)
            self.preview_canvas.create_rectangle(x0, top, left, bottom, **shade)
            self.preview_canvas.create_rectangle(right, top, x0 + preview.width, bottom, **shade)
            self.preview_canvas.create_rectangle(*crop_rect, outline="#00d8ff", width=3, tags="crop_frame")
            self.preview_canvas.create_text(left + 8, top + 8, text="Kéo để chọn vùng crop", fill="white", anchor="nw")
        else:
            self._canvas_crop_rect = None

    def _start_crop_drag(self, event) -> None:
        if not self.crop.get() or not self._canvas_crop_rect:
            return
        left, top, right, bottom = self._canvas_crop_rect
        if left <= event.x <= right and top <= event.y <= bottom:
            self._drag_offset = (event.x - left, event.y - top)
        else:
            self._drag_offset = ((right - left) / 2, (bottom - top) / 2)
            self._drag_crop(event)

    def _drag_crop(self, event) -> None:
        if not self.crop.get() or not self._canvas_image_rect or not self._canvas_crop_rect:
            return
        image_left, image_top, image_right, image_bottom = self._canvas_image_rect
        left, top, right, bottom = self._canvas_crop_rect
        frame_width, frame_height = right - left, bottom - top
        new_left = max(image_left, min(image_right - frame_width, event.x - self._drag_offset[0]))
        new_top = max(image_top, min(image_bottom - frame_height, event.y - self._drag_offset[1]))
        available_x = image_right - image_left - frame_width
        available_y = image_bottom - image_top - frame_height
        self.crop_position[0] = (new_left - image_left) / available_x if available_x > 0.5 else 0.5
        self.crop_position[1] = (new_top - image_top) / available_y if available_y > 0.5 else 0.5
        self._render_preview()

    def _preview_size(self) -> None:
        try:
            width = int(self.width.get())
            height = int(self.height.get())
        except ValueError:
            messagebox.showerror("Invalid size", "Width and height must be integers.")
            return

        path = self.image_path.get().strip()
        if not path:
            messagebox.showinfo("Preview", "Chưa chọn ảnh.")
            return

        try:
            img = prepare_image(path, width, height, crop=self.crop.get(), crop_position=tuple(self.crop_position))
        except Exception as exc:
            messagebox.showerror("Preview error", str(exc))
            return

        self.status.set(f"Preview OK: {img.size[0]}x{img.size[1]} -> mode {self.mode.get()}")
        self._render_preview()

    def _update_preview(self) -> None:
        if self.image_path.get().strip():
            self._render_preview()

    def _generate(self) -> None:
        try:
            width = int(self.width.get())
            height = int(self.height.get())
            threshold = int(self.mono_threshold.get())
        except ValueError:
            messagebox.showerror("Invalid input", "Width, height, and mono threshold must be integers.")
            return

        image_path = self.image_path.get().strip()
        output_path = self.output_path.get().strip()
        array_name = self.array_name.get().strip() or "my_image"

        if not image_path:
            messagebox.showerror("Missing input", "Please choose an image file.")
            return
        if not output_path:
            messagebox.showerror("Missing output", "Please choose an output header file.")
            return

        try:
            convert_to_header(
                image_path=image_path,
                output_path=output_path,
                array_name=array_name,
                width=width,
                height=height,
                crop=self.crop.get(),
                mode=self.mode.get(),
                endian=self.endian.get(),
                mono_threshold=threshold,
                crop_position=tuple(self.crop_position),
            )
        except Exception as exc:
            messagebox.showerror("Generate failed", str(exc))
            return

        self.status.set(f"Generated {output_path}")
        self._render_preview()
        messagebox.showinfo("Done", f"Generated header:\n{output_path}")


def main() -> None:
    app = ImageToolApp()
    app.mainloop()


if __name__ == "__main__":
    main()
