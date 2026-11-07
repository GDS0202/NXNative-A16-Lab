// Live quality controls. The owner of the guest present loop is the only writer
// of the build-verified guest state page; UI threads only submit settings.
#pragma once
#include <stddef.h>
#include <stdint.h>

enum { DM_TUNE_SCALE = 1, DM_TUNE_FULL_SCALE = 2, DM_TUNE_CLIP = 4 };
enum { DM_TUNE_MANUAL, DM_TUNE_SETTLING, DM_TUNE_GPU, DM_TUNE_OTHER,
       DM_TUNE_FLOOR, DM_TUNE_NO_GPU, DM_TUNE_THERMAL, DM_TUNE_MEMORY_CAP };
typedef struct {
    int automatic, target, scale, min_height, texture, far_clip, fixed;
    int auto_texture, auto_clip, clip_floor, output, upscale;
} dm_tuning_config;
typedef struct {
    dm_tuning_config requested;
    unsigned capabilities;
    int width, height, scale, texture, far_clip, status, thermal;
    int effective_cap, cap_reasons, memory_level, memory_pressure;
    uint64_t headroom, changes;
    double gpu_ms, frame_ms;
    int measuring, measured_frames, measured_complete;
    double measured_fps, measured_p95;
} dm_tuning_snapshot;

void dm_tuning_init(void *page, unsigned capabilities, int width, int height);
int dm_tuning_set(const char *key, double value); // rejects invalid/incompatible requests
void dm_tuning_tick(uint64_t now, double gpu_ms, double frame_ms, double compile_ms, int movie);
void dm_tuning_system(uint64_t headroom, int thermal, int low_power);
void dm_tuning_limits(int effective_cap, int cap_reasons, int memory_level, int memory_pressure);
void dm_tuning_boundary(void); // foreground/background or loading/menu boundary
void dm_tuning_present(uint64_t timestamp); // actual drawable presentation, not guest FPS
void dm_tuning_measure(void); // a bounded 30-second real presentation sample
dm_tuning_snapshot dm_tuning_read(void);
void dm_tuning_describe(char *text, size_t capacity);
int dm_tuning_texture(void); // atomic query; 0 leaves the game's samplers unchanged
int dm_tuning_output(void);
int dm_tuning_upscale(void); // -1 until initialized; then 0 Standard / 1 spatial MetalFX
int dm_tuning_active(void);
