#ifndef ESP32_C3_MICRO_WATCH_DISPLAY_H
#define ESP32_C3_MICRO_WATCH_DISPLAY_H

#include "display/lcd_display.h"

#include <esp_timer.h>

class WatchDisplay : public SpiLcdDisplay {
public:
    WatchDisplay(esp_lcd_panel_io_handle_t panel_io, esp_lcd_panel_handle_t panel,
                 int width, int height, int offset_x, int offset_y,
                 bool mirror_x, bool mirror_y, bool swap_xy);
    ~WatchDisplay() override;

    void SetupUI() override;
    void SetStatus(const char* status) override;
    void SetEmotion(const char* emotion) override;
    void SetChatMessage(const char* role, const char* content) override;
    void SetPreviewImage(std::unique_ptr<LvglImage> image) override;

private:
    static void ClockTimerCallback(void* arg);
    void LayoutTextUI();
    void SetClockVisible(bool visible);
    void CreateClockFace();
    void UpdateClock();
    void UpdateHand(lv_obj_t* hand, lv_point_precise_t (&points)[2],
                    float angle, float length, float tail);

    lv_obj_t* clock_root_ = nullptr;
    lv_obj_t* hour_hand_ = nullptr;
    lv_obj_t* minute_hand_ = nullptr;
    lv_obj_t* second_hand_ = nullptr;
    lv_obj_t* center_dot_ = nullptr;
    lv_point_precise_t hour_points_[2] = {};
    lv_point_precise_t minute_points_[2] = {};
    lv_point_precise_t second_points_[2] = {};
    lv_point_precise_t tick_points_[60][2] = {};
    esp_timer_handle_t clock_timer_ = nullptr;
};

#endif
