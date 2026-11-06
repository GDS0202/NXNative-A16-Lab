#include "../nvn/nvn_memory.h"
#include <assert.h>
#include <stdio.h>
static void sample(nvn_memory *s, unsigned seconds, unsigned mib, int event) {
    nvn_memory_sample(s, (uint64_t)seconds * 1000000000ull, (uint64_t)mib << 20, event);
}
static void stable(nvn_memory *s, unsigned from, unsigned to, unsigned mib) {
    for (unsigned sec = from; sec <= to; sec++) sample(s, sec, mib, NVN_MEM_POLL);
}
int main(void) {
    nvn_memory s = {0};
    sample(&s, 1, 4096, NVN_MEM_POLL); assert(!s.level);
    sample(&s, 2, 818, NVN_MEM_CRITICAL); assert(s.level == 2 && s.reason == NVN_MEM_OS_CRITICAL);
    sample(&s, 30, 900, NVN_MEM_POLL); assert(s.level == 2); // A poll must not clear system pressure.
    sample(&s, 31, 818, NVN_MEM_NORMAL); assert(s.level == 1);
    stable(&s, 32, 40, 779); assert(s.level == 1);
    sample(&s, 41, 779, NVN_MEM_POLL); assert(s.level == 0); // Recorded steady-state range, below 1 GiB.
    sample(&s, 42, 599, NVN_MEM_POLL); assert(s.level == 1);
    sample(&s, 43, 700, NVN_MEM_POLL); assert(s.level == 1 && !s.calm_since);
    sample(&s, 44, 800, NVN_MEM_POLL); assert(s.level == 1);
    stable(&s, 45, 52, 800); sample(&s, 53, 767, NVN_MEM_POLL); assert(s.level == 1 && !s.calm_since);
    stable(&s, 54, 64, 800); assert(!s.level);
    sample(&s, 65, 0, NVN_MEM_POLL); assert(s.level == 2 && s.reason == NVN_MEM_HEADROOM_CRITICAL);
    sample(&s, 66, 800, NVN_MEM_NORMAL); stable(&s, 67, 74, 900); sample(&s, 75, 900, NVN_MEM_WARN); assert(s.level == 1);
    sample(&s, 95, 1500, NVN_MEM_POLL); assert(s.level == 1);
    sample(&s, 96, 900, NVN_MEM_NORMAL); stable(&s, 97, 106, 900); assert(!s.level);
    sample(&s, 107, 900, NVN_MEM_WARN); assert(!s.level && s.pressure == 1); // Healthy warning: trim, no forced cap.
    sample(&s, 108, 700, NVN_MEM_POLL); assert(s.level == 1);
    sample(&s, 109, 900, NVN_MEM_NORMAL); sample(&s, 108, 900, NVN_MEM_POLL); assert(s.level == 1);
    stable(&s, 109, 118, 900); assert(!s.level);
    sample(&s, 200, 818, NVN_MEM_CRITICAL); sample(&s, 201, 818, NVN_MEM_NORMAL);
    stable(&s, 202, 210, 818); assert(s.level == 1);
    sample(&s, 400, 818, NVN_MEM_POLL); assert(s.level == 1); // Background time is not observed safe time.
    stable(&s, 401, 409, 818); assert(s.level == 1);
    sample(&s, 410, 818, NVN_MEM_POLL); assert(!s.level);
    unsigned rng = 1; const unsigned mib[] = {0, 299, 300, 599, 600, 767, 768, 818, 4096};
    for (unsigned i = 0; i < 50000; i++) {
        rng = rng * 1664525u + 1013904223u;
        unsigned left = mib[(rng >> 8) % (sizeof mib / sizeof *mib)];
        int event = (int)((rng >> 20) % 4);
        nvn_memory_sample(&s, 500000000000ull + (uint64_t)i * 500000000ull, (uint64_t)left << 20, event);
        assert(s.level >= 0 && s.level <= 2);
        if (s.pressure == 2 || left < 300) assert(s.level == 2);
        if (left < 600) assert(s.level >= 1);
    }
    puts("Memory guard: critical, normal recovery, 0 bytes, hysteresis, suspension, clock rollback and transition invariants PASS");
    return 0;
}
