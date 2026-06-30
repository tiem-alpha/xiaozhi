#include "wifi_board.h"
#include "codecs/no_audio_codec.h"
#include "system_reset.h"
#include "application.h"
#include "button.h"
#include "config.h"
#include "mcp_server.h"
// #include "display/oled_display.h"
#include "display/lcd_display.h"
#include "assets/lang_config.h"
#include <esp_log.h>
// i2c lcd 
// #include <driver/i2c_master.h>
// #include <esp_lcd_panel_ops.h>
// #include <esp_lcd_panel_vendor.h>
// #include <esp_lcd_io_i2c.h>
// #include "led/single_led.h"
// spi lcd 
#include <driver/i2c_master.h>
#include <esp_lcd_panel_vendor.h>
#include <esp_lcd_panel_io.h>
#include <esp_lcd_panel_ops.h>
#include <driver/spi_common.h>

#include "settings.h"
// #include "power_save_timer.h"
#include "press_to_talk_mcp_tool.h"
#include <esp_efuse_table.h>


#define TAG "ESP32C3MicroBoard"

#if defined(LCD_TYPE_GC9A01_SERIAL)
#include <esp_lcd_gc9a01.h>

static const gc9a01_lcd_init_cmd_t gc9107_lcd_init_cmds[] = {
    //  {cmd, { data }, data_size, delay_ms}
    {0xfe, (uint8_t[]){0x00}, 0, 0},
    {0xef, (uint8_t[]){0x00}, 0, 0},
    {0xb0, (uint8_t[]){0xc0}, 1, 0},
    {0xb1, (uint8_t[]){0x80}, 1, 0},
    {0xb2, (uint8_t[]){0x27}, 1, 0},
    {0xb3, (uint8_t[]){0x13}, 1, 0},
    {0xb6, (uint8_t[]){0x19}, 1, 0},
    {0xb7, (uint8_t[]){0x05}, 1, 0},
    {0xac, (uint8_t[]){0xc8}, 1, 0},
    {0xab, (uint8_t[]){0x0f}, 1, 0},
    {0x3a, (uint8_t[]){0x05}, 1, 0},
    {0xb4, (uint8_t[]){0x04}, 1, 0},
    {0xa8, (uint8_t[]){0x08}, 1, 0},
    {0xb8, (uint8_t[]){0x08}, 1, 0},
    {0xea, (uint8_t[]){0x02}, 1, 0},
    {0xe8, (uint8_t[]){0x2A}, 1, 0},
    {0xe9, (uint8_t[]){0x47}, 1, 0},
    {0xe7, (uint8_t[]){0x5f}, 1, 0},
    {0xc6, (uint8_t[]){0x21}, 1, 0},
    {0xc7, (uint8_t[]){0x15}, 1, 0},
    {0xf0,
    (uint8_t[]){0x1D, 0x38, 0x09, 0x4D, 0x92, 0x2F, 0x35, 0x52, 0x1E, 0x0C,
                0x04, 0x12, 0x14, 0x1f},
    14, 0},
    {0xf1,
    (uint8_t[]){0x16, 0x40, 0x1C, 0x54, 0xA9, 0x2D, 0x2E, 0x56, 0x10, 0x0D,
                0x0C, 0x1A, 0x14, 0x1E},
    14, 0},
    {0xf4, (uint8_t[]){0x00, 0x00, 0xFF}, 3, 0},
    {0xba, (uint8_t[]){0xFF, 0xFF}, 2, 0},
};
#endif

class ESP32C3MicroBoard : public WifiBoard {
private:
    Button touch_button_;
    i2c_master_bus_handle_t display_i2c_bus_;
    esp_lcd_panel_io_handle_t panel_io_ = nullptr;
    esp_lcd_panel_handle_t panel_ = nullptr;
    Display* display_ = nullptr;
    // PowerSaveTimer* power_save_timer_ = nullptr;
    PressToTalkMcpTool* press_to_talk_tool_ = nullptr;

    // void InitializePowerSaveTimer() {
    //     power_save_timer_ = new PowerSaveTimer(160, 300);
    //     power_save_timer_->OnEnterSleepMode([this]() {
    //         GetDisplay()->SetPowerSaveMode(true);
    //     });
    //     power_save_timer_->OnExitSleepMode([this]() {
    //         GetDisplay()->SetPowerSaveMode(false);
    //     });
    //     power_save_timer_->SetEnabled(true);
    // }

    // void InitializeDisplayI2c() {
    //     i2c_master_bus_config_t bus_config = {
    //         .i2c_port = (i2c_port_t)0,
    //         .sda_io_num = DISPLAY_SDA_PIN,
    //         .scl_io_num = DISPLAY_SCL_PIN,
    //         .clk_source = I2C_CLK_SRC_DEFAULT,
    //         .glitch_ignore_cnt = 7,
    //         .intr_priority = 0,
    //         .trans_queue_depth = 0,
    //         .flags = {
    //             .enable_internal_pullup = 1,
    //         },
    //     };
    //     ESP_ERROR_CHECK(i2c_new_master_bus(&bus_config, &display_i2c_bus_));
    // }

    void InitializeSpi() {
        spi_bus_config_t buscfg = {};
        buscfg.mosi_io_num = DISPLAY_MOSI_PIN;
        buscfg.miso_io_num = GPIO_NUM_NC;
        buscfg.sclk_io_num = DISPLAY_SCLK_PIN;
        buscfg.quadwp_io_num = GPIO_NUM_NC;
        buscfg.quadhd_io_num = GPIO_NUM_NC;
        buscfg.max_transfer_sz = DISPLAY_WIDTH * DISPLAY_HEIGHT * sizeof(uint16_t);
        ESP_ERROR_CHECK(spi_bus_initialize(SPI2_HOST, &buscfg, SPI_DMA_CH_AUTO));
    }

    // void InitializeSsd1306Display() {
    //     esp_lcd_panel_io_i2c_config_t io_config = {
    //         .dev_addr = 0x3C,
    //         .on_color_trans_done = nullptr,
    //         .user_ctx = nullptr,
    //         .control_phase_bytes = 1,
    //         .dc_bit_offset = 6,
    //         .lcd_cmd_bits = 8,
    //         .lcd_param_bits = 8,

    //         .flags = {
    //             .dc_low_on_data = 0,
    //             .disable_control_phase = 0,
    //         },

    //         .scl_speed_hz = 400 * 1000,
    //     };

    //     ESP_ERROR_CHECK(esp_lcd_new_panel_io_i2c(display_i2c_bus_, &io_config, &panel_io_));

    //     ESP_LOGI(TAG, "Install SSD1306 driver");
    //     esp_lcd_panel_dev_config_t panel_config = {};
    //     panel_config.reset_gpio_num = -1;
    //     panel_config.bits_per_pixel = 1;

    //     esp_lcd_panel_ssd1306_config_t ssd1306_config = {
    //         .height = static_cast<uint8_t>(DISPLAY_HEIGHT),
    //     };
    //     panel_config.vendor_config = &ssd1306_config;

    //     ESP_ERROR_CHECK(esp_lcd_new_panel_ssd1306(panel_io_, &panel_config, &panel_));
    //     ESP_LOGI(TAG, "SSD1306 driver installed");

    //     ESP_ERROR_CHECK(esp_lcd_panel_reset(panel_));
    //     if (esp_lcd_panel_init(panel_) != ESP_OK) {
    //         ESP_LOGE(TAG, "Failed to initialize display");
    //         display_ = new NoDisplay();
    //         return;
    //     }

    //     ESP_LOGI(TAG, "Turning display on");
    //     ESP_ERROR_CHECK(esp_lcd_panel_disp_on_off(panel_, true));

    //     display_ = new OledDisplay(panel_io_, panel_, DISPLAY_WIDTH, DISPLAY_HEIGHT, DISPLAY_MIRROR_X, DISPLAY_MIRROR_Y);
    // }

    void InitializeLcdDisplay() {
        esp_lcd_panel_io_handle_t panel_io = nullptr;
        esp_lcd_panel_handle_t panel = nullptr;
        // 液晶屏控制IO初始化
        ESP_LOGD(TAG, "Install panel IO");
        esp_lcd_panel_io_spi_config_t io_config = {};
        io_config.cs_gpio_num = DISPLAY_CS_PIN;
        io_config.dc_gpio_num = DISPLAY_DC_PIN;
        io_config.spi_mode = DISPLAY_SPI_MODE;
        io_config.pclk_hz = DISPLAY_SPI_SCLK_HZ;
        io_config.trans_queue_depth = 10;
        io_config.lcd_cmd_bits = 8;
        io_config.lcd_param_bits = 8;
        ESP_ERROR_CHECK(esp_lcd_new_panel_io_spi(SPI2_HOST, &io_config, &panel_io));

        // 初始化液晶屏驱动芯片
        ESP_LOGD(TAG, "Install LCD driver");
        esp_lcd_panel_dev_config_t panel_config = {};
        panel_config.reset_gpio_num = DISPLAY_RESET_PIN;
        panel_config.rgb_ele_order = DISPLAY_RGB_ORDER;
        panel_config.bits_per_pixel = 16;
#if defined(LCD_TYPE_GC9A01_SERIAL)
        ESP_ERROR_CHECK(esp_lcd_new_panel_gc9a01(panel_io, &panel_config, &panel));
        gc9a01_vendor_config_t gc9107_vendor_config = {
            .init_cmds = gc9107_lcd_init_cmds,
            .init_cmds_size = sizeof(gc9107_lcd_init_cmds) / sizeof(gc9a01_lcd_init_cmd_t),
        };        
#else
        ESP_ERROR_CHECK(esp_lcd_new_panel_st7789(panel_io, &panel_config, &panel));
#endif
        
        esp_lcd_panel_reset(panel);

        esp_lcd_panel_init(panel);
        esp_lcd_panel_invert_color(panel, DISPLAY_INVERT_COLOR);
        esp_lcd_panel_swap_xy(panel, DISPLAY_SWAP_XY);
        esp_lcd_panel_mirror(panel, DISPLAY_MIRROR_X, DISPLAY_MIRROR_Y);
#ifdef  LCD_TYPE_GC9A01_SERIAL
        panel_config.vendor_config = &gc9107_vendor_config;
#endif
        display_ = new SpiLcdDisplay(panel_io, panel,
                                    DISPLAY_WIDTH, DISPLAY_HEIGHT, DISPLAY_OFFSET_X, DISPLAY_OFFSET_Y, DISPLAY_MIRROR_X, DISPLAY_MIRROR_Y, DISPLAY_SWAP_XY);
    }

    void InitializeButtons() {
        //  touch_button_.OnClick([this]() {
        //     auto& app = Application::GetInstance();
        //     if (app.GetDeviceState() == kDeviceStateStarting) {
        //         EnterWifiConfigMode();
        //         return;
        //     }
        //     if (!press_to_talk_tool_ || !press_to_talk_tool_->IsPressToTalkEnabled()) {
        //         app.ToggleChatState();
        //     }
        // });

        touch_button_.OnPressDown([this]() {
            // if (power_save_timer_) {
            //     power_save_timer_->WakeUp();
            // }
           if (press_to_talk_tool_ && press_to_talk_tool_->IsPressToTalkEnabled()) {
                Application::GetInstance().StartListening();
            }
        });
        touch_button_.OnPressUp([this]() {
            if (press_to_talk_tool_ && press_to_talk_tool_->IsPressToTalkEnabled()) {
                Application::GetInstance().StopListening();
            }
        });
    }

    void InitializeTools() {
        press_to_talk_tool_ = new PressToTalkMcpTool();
        press_to_talk_tool_->Initialize();
    }
    
public:
    ESP32C3MicroBoard() : touch_button_(TOUCH_BUTTON_GPIO) {
        // InitializeDisplayI2c();
        // InitializeSsd1306Display();
         InitializeSpi();
        InitializeLcdDisplay();
        InitializeButtons();
        // InitializePowerSaveTimer();
        InitializeTools();
    }

    virtual AudioCodec* GetAudioCodec() override {

        static NoAudioCodecSimplex audio_codec(AUDIO_INPUT_SAMPLE_RATE, AUDIO_OUTPUT_SAMPLE_RATE,
            AUDIO_I2S_SPK_GPIO_BCLK, AUDIO_I2S_SPK_GPIO_LRCK, AUDIO_I2S_SPK_GPIO_DOUT,
            AUDIO_I2S_MIC_GPIO_SCK, AUDIO_I2S_MIC_GPIO_WS, AUDIO_I2S_MIC_GPIO_DIN);

        return &audio_codec;
    }

    virtual Display* GetDisplay() override {
        return display_;
    }
};

DECLARE_BOARD(ESP32C3MicroBoard);
