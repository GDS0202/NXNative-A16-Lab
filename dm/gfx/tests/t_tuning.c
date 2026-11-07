#include "../nvn/nvn_tuning.h"
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static _Alignas(16) uint32_t page[64];
static uint64_t now;
static float value(unsigned off) { float f; memcpy(&f, (char *)page + off, 4); return f; }
static void init(void) {
    const char *keys[] = {"DM_AUTO_QUALITY", "DM_FPS_TARGET", "DM_RENDER_SCALE", "DM_RENDER_FIXED", "DM_AUTO_MIN_HEIGHT",
        "DM_TEXTURE_DETAIL", "DM_VIEW_DISTANCE", "DM_AUTO_TEXTURE", "DM_AUTO_VIEW", "DM_AUTO_VIEW_FLOOR", "DM_OUTPUT_HEIGHT", "DM_PRESENT_UPSCALE"};
    for (unsigned i = 0; i < sizeof keys / sizeof *keys; i++) unsetenv(keys[i]);
    memset(page, 0, sizeof page); float t = 60; memcpy(page, &t, 4); now = 1000000000;
    dm_tuning_init(page, 7, 1280, 720);
}
static void frames(int n, double gpu, double frame, double compilation) {
    for (int i = 0; i < n; i++) { now += (uint64_t)(frame * 1e6); dm_tuning_tick(now, gpu, frame, compilation, 0); }
}
int main(void) {
    init();
    assert(!dm_tuning_set("DM_RENDER_SCALE", NAN));
    assert(!dm_tuning_set("DM_RENDER_SCALE", INFINITY));
    assert(!dm_tuning_set("DM_RENDER_SCALE", .49));
    assert(!dm_tuning_set("DM_RENDER_SCALE", 1.01));
    assert(!dm_tuning_set("DM_AUTO_MIN_HEIGHT", 900));
    assert(!dm_tuning_set("DM_TEXTURE_DETAIL", 3));
    assert(!dm_tuning_set("unrecognized", 1));
    assert(dm_tuning_set("DM_RENDER_SCALE", .8));
    frames(1, 12, 16.666667, 0);
    assert(fabsf(value(0x10) - .8f) < 1e-6f && page[0x14/4] == 0);
    assert(dm_tuning_set("DM_RENDER_SCALE", 1));
    assert(dm_tuning_set("DM_RENDER_FIXED", 1));
    frames(1, 12, 16.666667, 0);
    assert(value(0x10) == 1 && page[0x14/4] == 1);
    assert(dm_tuning_set("DM_VIEW_DISTANCE", 5000));
    assert(dm_tuning_set("DM_TEXTURE_DETAIL", 2));
    frames(1, 12, 16.666667, 0);
    assert(value(0x18) == 5000 && dm_tuning_texture() == 2);
    assert(dm_tuning_set("DM_VIEW_DISTANCE", 0)); frames(1, 12, 16.666667, 0); assert(value(0x18) == 0);

    init(); assert(dm_tuning_set("DM_AUTO_QUALITY", 1));
    frames(1500, 24, 25, 0);
    assert(dm_tuning_read().scale == 80); // never sacrifices the requested 576p floor
    assert(dm_tuning_read().status == DM_TUNE_FLOOR);
    assert(dm_tuning_texture() == 0 && value(0x18) == 0); // optional quality domains stay untouched
    frames(1800, 8, 16.666667, 0); assert(dm_tuning_read().scale == 100);

    init(); assert(dm_tuning_set("DM_AUTO_MIN_HEIGHT", 720)); assert(dm_tuning_set("DM_AUTO_QUALITY", 1));
    frames(900, 24, 25, 0); assert(dm_tuning_read().scale == 100 && page[0x14/4] == 1);

    init(); assert(dm_tuning_set("DM_AUTO_QUALITY", 1));
    frames(900, 7, 35, 0); assert(dm_tuning_read().scale == 100 && dm_tuning_read().status == DM_TUNE_OTHER);
    frames(900, 24, 25, 4); assert(dm_tuning_read().scale == 100); // compilation spikes are not GPU pressure
    frames(900, -1, 25, 0); assert(dm_tuning_read().scale == 100);

    init(); assert(dm_tuning_set("DM_AUTO_QUALITY", 1));
    frames(50, 24, 25, 0); frames(1, NAN, 25, 0); frames(50, 24, 25, 0);
    assert(dm_tuning_read().scale == 100); // Unknown GPU time breaks consecutive overload evidence.

    init(); assert(dm_tuning_set("DM_AUTO_QUALITY", 1)); frames(1200, 24, 25, 0);
    dm_tuning_system(1100000000, 2, 0); frames(1200, 8, 16.666667, 0); assert(dm_tuning_read().scale == 80);
    dm_tuning_system(1100000000, 0, 0); frames(1800, 8, 16.666667, 0); assert(dm_tuning_read().scale == 100);
    frames(1200, 24, 25, 0); assert(dm_tuning_read().scale == 80);
    dm_tuning_system(0, 0, 0); frames(1200, 8, 16.666667, 0); assert(dm_tuning_read().scale == 80);
    dm_tuning_system(1100000000, 0, 1); frames(1200, 8, 16.666667, 0); assert(dm_tuning_read().scale == 80);
    dm_tuning_system(1100000000, 0, 0); dm_tuning_limits(30, 8, 2, 2);
    frames(1200, 8, 16.666667, 0); assert(dm_tuning_read().scale == 80); // Healthy process headroom cannot clear an OS pressure hold.
    dm_tuning_limits(60, 0, 0, 0);
    dm_tuning_system(1100000000, 0, 0); frames(1800, 8, 16.666667, 0); assert(dm_tuning_read().scale == 100);
    dm_tuning_boundary(); now += 20000000000ull; frames(1, 24, 25, 0); assert(dm_tuning_read().scale == 100);

    // A protection-induced 30 FPS must not trigger unnecessary quality loss.
    init(); assert(dm_tuning_set("DM_AUTO_QUALITY", 1)); assert(dm_tuning_set("DM_AUTO_TEXTURE", 1));
    assert(dm_tuning_set("DM_AUTO_VIEW", 1));
    dm_tuning_system(818ull << 20, 0, 0); dm_tuning_limits(30, 8, 2, 2);
    frames(1500, 25, 34, 0);
    assert(dm_tuning_read().scale == 100 && dm_tuning_read().texture == 0 &&
           dm_tuning_read().far_clip == 0 && dm_tuning_read().status == DM_TUNE_MEMORY_CAP);
    dm_tuning_limits(60, 0, 0, 0); dm_tuning_system(1100000000, 0, 0);
    frames(1200, 24, 25, 0); assert(dm_tuning_read().scale < 100);

    init(); assert(dm_tuning_set("DM_AUTO_QUALITY", 1)); assert(dm_tuning_set("DM_AUTO_TEXTURE", 1));
    assert(dm_tuning_set("DM_AUTO_VIEW", 1)); frames(2500, 24, 25, 0);
    assert(dm_tuning_read().texture == 2 && dm_tuning_read().far_clip == 2000);
    assert(dm_tuning_read().scale == 80);

    init(); dm_tuning_measure();
    uint64_t stamp = 1000000000;
    for (int i = 0; i < 1802; i++) { dm_tuning_present(stamp); dm_tuning_present(stamp); stamp += 16666667; }
    dm_tuning_snapshot s = dm_tuning_read();
    assert(!s.measuring && s.measured_complete && s.measured_frames == 1800);
    assert(fabs(s.measured_fps - 60) < .001 && fabs(s.measured_p95 - 16.666667) < .001);
    dm_tuning_measure(); dm_tuning_present(stamp); dm_tuning_boundary(); assert(!dm_tuning_read().measuring && !dm_tuning_read().measured_complete);
    dm_tuning_measure(); dm_tuning_present(stamp); assert(dm_tuning_set("DM_TEXTURE_DETAIL", 1));
    assert(!dm_tuning_read().measuring && !dm_tuning_read().measured_complete && !dm_tuning_read().measured_frames);

    init(); assert(dm_tuning_set("DM_AUTO_QUALITY", 1));
    dm_tuning_measure(); dm_tuning_present(now); frames(1200, 24, 25, 0);
    assert(dm_tuning_read().scale == 80 && !dm_tuning_read().measuring && !dm_tuning_read().measured_complete);
    dm_tuning_measure(); dm_tuning_present(now); frames(1800, 8, 16.666667, 0);
    assert(dm_tuning_read().scale == 100 && !dm_tuning_read().measuring && !dm_tuning_read().measured_complete);

    init(); dm_tuning_init(NULL, 0, 0, 0); assert(!dm_tuning_set("DM_AUTO_QUALITY", 1));
    assert(!dm_tuning_set("DM_VIEW_DISTANCE", 1000));
    assert(dm_tuning_set("DM_TEXTURE_DETAIL", 1)); frames(1, 8, 16.666667, 0); assert(dm_tuning_texture() == 1);
    puts("live tuning: bounds, guest state, hysteresis, CPU/compile rejection, pressure and actual presentation measurements passed");
    return 0;
}
