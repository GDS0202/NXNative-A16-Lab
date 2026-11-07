#include "../nvn/nvn_pretrim.h"
#include <assert.h>
#include <stdio.h>

static int sample(nvn_pretrim *s, unsigned sec, unsigned mib, int os_pressure) {
    return nvn_pretrim_tick(s, (uint64_t)sec * 1000000000ull,
                             (uint64_t)mib << 20, os_pressure);
}
int main(void) {
    nvn_pretrim p = {0};
    assert(!sample(&p, 1, 1500, 0));
    assert(!sample(&p, 2, 950, 0));
    assert(!sample(&p, 3, 950, 0));
    assert(sample(&p, 4, 950, 0)); // Early trim, not a 30-FPS safety cap.
    assert(sample(&p, 5, 1080, 0));
    for (unsigned i = 6; i <= 13; i++) assert(sample(&p, i, 1200, 0));
    assert(!sample(&p, 14, 1200, 0)); // Stable recovery after eight seconds.
    assert(!sample(&p, 15, 950, 0));
    assert(sample(&p, 16, 1500, 1)); // OS warning/critical: immediate.
    assert(sample(&p, 17, 1500, 0));
    assert(sample(&p, 25, 1500, 0)); // Long background gap is not observed recovery.
    for (unsigned i = 26; i <= 33; i++) assert(sample(&p, i, 1500, 0));
    assert(!sample(&p, 34, 1500, 0));
    assert(!sample(&p, 40, 950, 0));
    assert(!sample(&p, 39, 950, 0)); // Clock rollback resets the trend.
    assert(!sample(&p, 40, 950, 0));
    assert(sample(&p, 41, 950, 0));
    puts("Predictive A16 memory cleanup: sustained low headroom, OS emergency, hysteresis, pause and clock rollback PASS");
    return 0;
}
