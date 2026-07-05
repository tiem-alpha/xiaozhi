# Kiến trúc hiển thị ESP32-C3 Micro + GC9A01 trong project Xiaozhi

## 1. Cấu hình đang được sử dụng

Project hiện chọn:

- SoC: **ESP32-C3** (`CONFIG_IDF_TARGET_ESP32C3=y`).
- Board: **ESP32 C3 Micro** (`CONFIG_BOARD_TYPE_ESP32_C3_MICRO=y`).
- LCD: **GC9A01**, 240 × 240, giao tiếp SPI.
- GUI: **LVGL 9.5.0**.
- Định dạng màu: **RGB565, 16 bit/pixel**.
- UI: giao diện LCD mặc định; `CONFIG_USE_WECHAT_MESSAGE_STYLE` và
  `CONFIG_USE_MULTILINE_CHAT_MESSAGE` đều đang tắt.
- Font chữ: `font_puhui_basic_14_1`.
- Font icon: `font_awesome_14_1` và icon lớn `font_awesome_30_4`.

Cấu hình chân hiện tại trong `main/boards/esp32_c3_micro/config.h`:

| Tín hiệu GC9A01 | GPIO |
|---|---:|
| SCLK | GPIO9 |
| MOSI | GPIO5 |
| CS | GPIO0 |
| DC | GPIO20 |
| RESET | Không điều khiển (`GPIO_NUM_NC`) |
| Backlight | Không điều khiển (`GPIO_NUM_NC`) |

SPI đang chạy ở 10 MHz. MISO không được dùng vì màn hình chỉ nhận dữ liệu.

## 2. Các tầng của hệ thống hiển thị

Luồng tổng quát:

```text
Application / trạng thái hội thoại
        │
        │ SetStatus(), SetEmotion(), SetChatMessage()
        ▼
Display (interface chung)
        ▼
LvglDisplay (logic trạng thái chung của LVGL)
        ▼
LcdDisplay (widget, layout, theme, emoji, subtitle)
        ▼
SpiLcdDisplay (khởi tạo LVGL và ghép LVGL với LCD SPI)
        ▼
esp_lvgl_port
        ▼
ESP-LCD panel + panel IO
        ▼
driver esp_lcd_gc9a01
        ▼
SPI2_HOST → GC9A01 → panel 240 × 240
```

### Tầng 1: board và cấu hình phần cứng

File chính:

- `main/boards/esp32_c3_micro/config.h`
- `main/boards/esp32_c3_micro/esp32_c3_micro_board.cc`

`ESP32C3MicroBoard` kế thừa `WifiBoard`. Board thực hiện ba việc liên quan đến
màn hình:

1. `InitializeSpi()` tạo bus `SPI2_HOST` với MOSI, SCLK và DMA tự động.
2. `InitializeLcdDisplay()` tạo panel IO, driver GC9A01 và cấu hình panel.
3. Tạo đối tượng `SpiLcdDisplay` rồi trả nó qua `GetDisplay()` dưới kiểu
   `Display*`.

Thông số hướng hiển thị hiện tại:

```cpp
DISPLAY_MIRROR_X = true
DISPLAY_MIRROR_Y = false
DISPLAY_SWAP_XY  = false
DISPLAY_OFFSET_X = 0
DISPLAY_OFFSET_Y = 0
```

Đây là nơi cần sửa nếu hình bị xoay, lật hoặc lệch. Không nên sửa layout LVGL
để chữa lỗi xoay/lật ở tầng phần cứng.

### Tầng 2: ESP-LCD và driver GC9A01

Các API chính được dùng:

```cpp
spi_bus_initialize(...)
esp_lcd_new_panel_io_spi(...)
esp_lcd_new_panel_gc9a01(...)
esp_lcd_panel_reset(...)
esp_lcd_panel_init(...)
esp_lcd_panel_invert_color(...)
esp_lcd_panel_swap_xy(...)
esp_lcd_panel_mirror(...)
```

`esp_lcd_panel_io_handle_t` quản lý truyền lệnh/dữ liệu qua SPI.
`esp_lcd_panel_handle_t` biểu diễn controller GC9A01 và cung cấp API vẽ bitmap.

Lưu ý về code hiện tại: `panel_config.vendor_config` được gán **sau** lệnh
`esp_lcd_new_panel_gc9a01()`. Vì driver đọc cấu hình tại lúc tạo panel, bảng
`gc9107_lcd_init_cmds` hiện không được truyền vào driver. Nếu panel thực sự cần
bảng init custom, thứ tự đúng phải là:

```cpp
gc9a01_vendor_config_t vendor_config = {
    .init_cmds = gc9107_lcd_init_cmds,
    .init_cmds_size = sizeof(gc9107_lcd_init_cmds) /
                      sizeof(gc9a01_lcd_init_cmd_t),
};

panel_config.vendor_config = &vendor_config;
ESP_ERROR_CHECK(
    esp_lcd_new_panel_gc9a01(panel_io, &panel_config, &panel));
```

Đây là custom **driver/panel**, không phải custom giao diện.

### Tầng 3: `SpiLcdDisplay`

Khai báo tại `main/display/lcd_display.h`, triển khai tại
`main/display/lcd_display.cc`.

Chuỗi kế thừa:

```text
Display
  └── LvglDisplay
       └── LcdDisplay
            └── SpiLcdDisplay
```

Constructor `SpiLcdDisplay`:

1. Tô trắng panel ban đầu bằng `esp_lcd_panel_draw_bitmap()`.
2. Bật panel.
3. Gọi `lv_init()`.
4. Khởi tạo task/timer LVGL qua `lvgl_port_init()`.
5. Đăng ký LCD với LVGL bằng `lvgl_port_add_disp()`.

Cấu hình buffer hiện tại:

- Buffer: `width × 20 = 240 × 20` pixel, tức 4.800 pixel.
- RGB565: khoảng 9.600 byte cho buffer.
- Một buffer, dùng DMA.
- Không dùng PSRAM cho buffer.
- `full_refresh = 0`: LVGL chỉ cập nhật vùng bị thay đổi.
- `swap_bytes = 1`: đảo byte cho dữ liệu RGB565 trước khi gửi panel.

Cấu hình này phù hợp ESP32-C3 có RAM hạn chế. Full framebuffer 240 × 240 × 2
sẽ tốn khoảng 115.200 byte, chưa tính dữ liệu và overhead của LVGL.

### Tầng 4: `Display`

`Display` trong `main/display/display.h` là interface chung để application không
phụ thuộc loại màn hình. Các API quan trọng:

```cpp
SetStatus(...)
ShowNotification(...)
SetEmotion(...)
SetChatMessage(...)
ClearChatMessages()
SetTheme(...)
UpdateStatusBar(...)
SetPowerSaveMode(...)
SetupUI()
```

Nhờ interface này, `Application` chỉ gọi `board.GetDisplay()` và không cần biết
đó là GC9A01, OLED hay panel RGB.

### Tầng 5: `LvglDisplay`

`LvglDisplay` trong `main/display/lvgl_display/` chứa phần dùng chung cho các
màn hình LVGL:

- status và notification;
- icon mạng, mute và pin;
- popup pin yếu;
- cập nhật status bar;
- khóa truy cập LVGL;
- power-save và snapshot.

`DisplayLockGuard` khóa `lvgl_port_lock()` trước khi thay đổi widget và tự mở
khóa khi ra khỏi scope. Mọi code custom thay đổi LVGL từ task khác phải giữ khóa
này hoặc dùng cơ chế tương đương. Không gọi trực tiếp API LVGL từ callback/task
bất kỳ mà không khóa.

### Tầng 6: `LcdDisplay` và giao diện LVGL

`LcdDisplay::SetupUI()` tạo cây widget. Với `sdkconfig` hiện tại, nhánh UI mặc
định được biên dịch:

```text
lv_screen_active()
├── container_                 nền toàn màn hình
├── emoji_box_                 vùng cảm xúc ở giữa
│   ├── emoji_label_           icon Font Awesome dự phòng
│   └── emoji_image_           PNG/GIF cảm xúc
├── preview_image_             ảnh xem trước tạm thời
├── top_bar_                   icon trạng thái phía trên
│   ├── network_label_
│   └── right_icons
│       ├── mute_label_
│       └── battery_label_
├── status_bar_                chồng lên top_bar
│   ├── notification_label_
│   └── status_label_
├── bottom_bar_                phụ đề một dòng phía dưới
│   └── chat_message_label_
└── low_battery_popup_         cảnh báo pin yếu
    └── low_battery_label_
```

GC9A01 là màn hình tròn nhưng vùng vẽ logic vẫn là hình vuông 240 × 240. Vì
vậy các góc của UI bị panel vật lý cắt. Nội dung quan trọng nên nằm trong vùng
an toàn gần tâm; không đặt chữ hoặc icon sát bốn góc.

## 3. Dữ liệu đi từ Xiaozhi đến màn hình như thế nào

Trong `Application::Initialize()`:

```cpp
auto display = board.GetDisplay();
display->SetupUI();
```

Sau đó application cập nhật UI theo trạng thái:

| API | Dữ liệu | Widget bị cập nhật |
|---|---|---|
| `SetStatus()` | Standby, Listening, Speaking... | `status_label_` |
| `ShowNotification()` | thông báo tạm thời | `notification_label_` |
| `SetChatMessage()` | transcript user/assistant/system | `chat_message_label_`, `bottom_bar_` |
| `SetEmotion()` | neutral, happy, sleepy... | `emoji_image_` hoặc `emoji_label_` |
| `UpdateStatusBar()` | Wi-Fi, mute, pin | các label trong `top_bar_` |

Ví dụ khi thiết bị chuyển sang nghe:

```text
State machine → Application → SetStatus("Listening")
                           └→ SetEmotion("neutral")
                                      ↓
                              LVGL cập nhật widget
                                      ↓
                            esp_lvgl_port flush vùng đổi
                                      ↓
                                  SPI → GC9A01
```

## 4. Theme, font và emoji

`LcdDisplay::InitializeLcdThemes()` đăng ký hai theme `light` và `dark`.
Theme đang dùng được đọc từ namespace settings `display`, key `theme`, mặc định
là `light`.

`LvglTheme` chứa:

- màu nền và chữ;
- màu message bubble;
- màu viền và cảnh báo pin;
- font chữ, font icon, font icon lớn;
- background image;
- `EmojiCollection`.

`SetEmotion()` ưu tiên ảnh trong `EmojiCollection`. Nếu không tìm thấy ảnh,
nó gọi `font_awesome_get_utf8()` và hiển thị icon font. Ảnh GIF được chạy qua
`LvglGif`; ảnh tĩnh được gán trực tiếp cho `emoji_image_`.

Board ESP32-C3 Micro hiện không chỉ định `DEFAULT_EMOJI_COLLECTION` riêng trong
nhánh CMake của board. Vì vậy khi custom emoji cần kiểm tra asset partition của
firmware thực tế, không nên mặc định rằng toàn bộ bộ emoji lớn đã được đóng gói.

## 5. Các mức custom giao diện

### Mức A: chỉ đổi màu/theme

Đây là cách ít rủi ro nhất. Sửa hoặc thêm theme trong
`LcdDisplay::InitializeLcdThemes()`:

```cpp
auto round_theme = new LvglTheme("round-dark");
round_theme->set_background_color(lv_color_hex(0x05070A));
round_theme->set_text_color(lv_color_hex(0xEAF6FF));
round_theme->set_chat_background_color(lv_color_hex(0x101820));
round_theme->set_border_color(lv_color_hex(0x36C5F0));
round_theme->set_low_battery_color(lv_color_hex(0xE53935));
round_theme->set_text_font(text_font);
round_theme->set_icon_font(icon_font);
round_theme->set_large_icon_font(large_icon_font);

LvglThemeManager::GetInstance().RegisterTheme("round-dark", round_theme);
```

Sau đó chọn theme qua settings hoặc gọi `display->SetTheme(theme)`. Nếu chỉ đổi
màu, không nên sao chép toàn bộ `LcdDisplay`.

### Mức B: thay bố cục chung cho mọi LCD

Sửa `LcdDisplay::SetupUI()` nếu muốn tất cả LCD dùng layout mới. Với màn hình
tròn 240 × 240, có thể:

- giảm chiều rộng status xuống khoảng 160–180 px;
- đặt icon mạng/pin lệch vào trong thay vì sát góc;
- giới hạn phụ đề khoảng 180–200 px;
- dùng `lv_obj_align()` theo tâm;
- đặt emoji ở tâm hoặc hơi cao để chừa phụ đề.

Nhược điểm: thay đổi này ảnh hưởng mọi board đang dùng `LcdDisplay`.

### Mức C: tạo UI riêng chỉ cho ESP32-C3 Micro

Đây là hướng nên dùng nếu muốn giao diện riêng cho GC9A01 mà không phá các
board khác.

Tạo lớp mới, ví dụ:

```text
main/boards/esp32_c3_micro/round_gc9a01_display.h
main/boards/esp32_c3_micro/round_gc9a01_display.cc
```

Có hai hướng thiết kế:

1. Kế thừa `SpiLcdDisplay`, override `SetupUI()` và các hàm update cần thiết.
2. Tách layout thành hook/protected method trong `LcdDisplay`, sau đó lớp con chỉ
   override phần tạo widget.

Hướng 2 sạch hơn nếu dự kiến duy trì lâu dài. Hiện nhiều widget của
`LcdDisplay` đã là `protected`, nên lớp con có thể sử dụng chúng. Tuy nhiên cần
giữ đúng hợp đồng:

- tạo `status_label_` và `notification_label_` để `LvglDisplay` hoạt động;
- tạo `network_label_`, `mute_label_`, `battery_label_` nếu dùng status bar;
- tạo `emoji_image_`/`emoji_label_` để `SetEmotion()` hoạt động;
- tạo `chat_message_label_` và `bottom_bar_` để `SetChatMessage()` hoạt động;
- gọi `Display::SetupUI()` đúng một lần;
- giữ `DisplayLockGuard` trong lúc tạo/thay đổi widget.

Sau đó tại board thay:

```cpp
display_ = new SpiLcdDisplay(...);
```

bằng:

```cpp
display_ = new RoundGc9a01Display(...);
```

và thêm file `.cc` vào source của component nếu CMake không tự thu thập file.

### Mức D: thêm widget động riêng

Nếu muốn thêm vòng sáng khi nghe, waveform hoặc đồng hồ, nên thêm API có nghĩa
ở lớp display riêng, ví dụ:

```cpp
void RoundGc9a01Display::SetListening(bool listening);
void RoundGc9a01Display::SetAudioLevel(uint8_t level);
```

Không nên để `Application` truy cập trực tiếp `lv_obj_t*`. Application nên gửi
trạng thái, còn lớp display quyết định cách biểu diễn. Điều này giữ ranh giới
giữa business logic và UI.

Animation nên dùng `lv_anim_t` hoặc timer của LVGL. Tránh redraw toàn màn hình
liên tục trên ESP32-C3; chỉ thay đổi thuộc tính/widget cần thiết.

## 6. Gợi ý layout cho màn hình tròn 240 × 240

Một layout thực dụng:

```text
             [Wi-Fi]   trạng thái   [Pin]


                    ┌─────────┐
                    │ emotion │
                    │ / GIF   │
                    └─────────┘


                 phụ đề 180–200 px
```

Khuyến nghị:

- vùng status hữu dụng: x khoảng 35–205;
- vùng nội dung chính: x/y khoảng 30–210;
- emoji 64–128 px tùy RAM và asset;
- phụ đề tối đa khoảng 190 px;
- nền đen thường phù hợp panel tròn và che vùng ngoài tốt hơn;
- không dùng widget full-screen có opacity khi không cần vì tăng lượng pixel
  phải flush qua SPI.

## 7. Quy trình custom an toàn

1. Chốt phần cứng trước: màu, mirror, swap XY, reset và tốc độ SPI.
2. Sửa lỗi thứ tự `vendor_config` nếu panel cần init command custom.
3. Tạo lớp display riêng cho board thay vì sửa trực tiếp UI chung.
4. Dựng widget trong `SetupUI()`.
5. Giữ nguyên API `SetStatus`, `SetEmotion`, `SetChatMessage` để application
   không phải thay đổi.
6. Bảo vệ mọi thao tác LVGL bằng display lock.
7. Test lần lượt startup, Wi-Fi config, standby, listening, speaking, subtitle,
   notification và pin yếu.
8. Theo dõi heap; tránh ảnh lớn hoặc nhiều GIF trên ESP32-C3 không có PSRAM.

## 8. Các file cần đọc/sửa theo mục đích

| Mục đích | File |
|---|---|
| GPIO, độ phân giải, mirror, SPI clock | `main/boards/esp32_c3_micro/config.h` |
| SPI, GC9A01, tạo display | `main/boards/esp32_c3_micro/esp32_c3_micro_board.cc` |
| Interface hiển thị | `main/display/display.h` |
| Logic LVGL chung/status bar | `main/display/lvgl_display/lvgl_display.{h,cc}` |
| Layout LCD, theme, emoji, subtitle | `main/display/lcd_display.{h,cc}` |
| Cấu hình font/asset theo board | `main/CMakeLists.txt` |
| Nguồn sự kiện trạng thái hội thoại | `main/application.cc` |
| Cấu hình chọn kiểu UI | `sdkconfig`, `main/Kconfig.projbuild` |

## 9. Kết luận thiết kế

Phần cứng GC9A01 không tự tạo giao diện. Nó chỉ nhận các vùng pixel RGB565 từ
ESP-LCD. `esp_lvgl_port` nối LVGL với panel; `SpiLcdDisplay` dựng backend;
`LcdDisplay` tạo widget; `LvglDisplay` cung cấp hành vi chung; `Display` là hợp
đồng với application; còn `Application` chỉ phát trạng thái và nội dung.

Nếu chỉ đổi màu, dùng theme. Nếu đổi bố cục riêng cho màn hình tròn, tạo một lớp
display riêng cho `esp32_c3_micro`. Nếu thêm hành vi mới, expose API trạng thái ở
lớp display và không đưa chi tiết `lv_obj_t` vào `Application`.
