#include "../nvn/nvn_memory.h"
#include <assert.h>
#include <stdio.h>
static void sample(nvn_memory *s, unsigned seconds, unsigned mib, int event) {
    nvn_memory_sample(s, (uint64_t)seconds * 1000000000ull, (uint64_t)mib << 20, event);
}
int main(void) {
    nvn_memory s = {0};
    sample(&s, 1, 4096, NVN_MEM_POLL); assert(!s.level);
    sample(&s, 2, 818, NVN_MEM_CRITICAL); assert(s.level == 2 && s.reason == NVN_MEM_OS_CRITICAL);
    sample(&s, 30, 900, NVN_MEM_POLL); assert(s.level == 2); // A poll must not clear system pressure.
    sample(&s, 31, 818, NVN_MEM_NORMAL); assert(s.level == 1);
    sample(&s, 40, 779, NVN_MEM_POLL); assert(s.level == 1);
    sample(&s, 41, 779, NVN_MEM_POLL); assert(s.level == 0); // Recorded steady-state range, below 1 GiB.
    sample(&s, 42, 599, NVN_MEM_POLL); assert(s.level == 1);
    sample(&s, 43, 700, NVN_MEM_POLL); assert(s.level == 1 && !s.calm_since);
    sample(&s, 44, 800, NVN_MEM_POLL); assert(s.level == 1);
    sample(&s, 53, 767, NVN_MEM_POLL); assert(s.level == 1 && !s.calm_since);
    sample(&s, 54, 800, NVN_MEM_POLL); sample(&s, 64, 800, NVN_MEM_POLL); assert(!s.level);
    sample(&s, 65, 0, NVN_MEM_POLL); assert(s.level == 2 && s.reason == NVN_MEM_HEADROOM_CRITICAL);
    sample(&s, 66, 800, NVN_MEM_NORMAL); sample(&s, 75, 900, NVN_MEM_WARN); assert(s.level == 1);
    sample(&s, 95, 1500, NVN_MEM_POLL); assert(s.level == 1);
    sample(&s, 96, 900, NVN_MEM_NORMAL); sample(&s, 106, 900, NVN_MEM_POLL); assert(!s.level);
    sample(&s, 107, 900, NVN_MEM_WARN); assert(!s.level && s.pressure == 1); // Healthy warning: trim, no forced cap.
    sample(&s, 108, 700, NVN_MEM_POLL); assert(s.level == 1);
    sample(&s, 109, 900, NVN_MEM_NORMAL); sample(&s, 108, 900, NVN_MEM_POLL); assert(s.level == 1);
    sample(&s, 118, 900, NVN_MEM_POLL); assert(!s.level);
    puts("Memory guard: critical, normal recovery, 0 bytes, hysteresis, renewed pressure and clock rollback PASS");
    return 0;
}
