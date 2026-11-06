#pragma once
#include <stdint.h>

// Serialized by the platform's memory-pressure queue. Polling is not an OS
// NORMAL notification: process headroom and system pressure are separate facts.
enum { NVN_MEM_POLL, NVN_MEM_NORMAL, NVN_MEM_WARN, NVN_MEM_CRITICAL };
enum { NVN_MEM_OK, NVN_MEM_OS_CRITICAL, NVN_MEM_HEADROOM_CRITICAL,
       NVN_MEM_HEADROOM_LOW, NVN_MEM_OS_WARN, NVN_MEM_RECOVERING };
typedef struct {
    int level, pressure, reason;
    uint64_t calm_since, last_sample;
} nvn_memory;

static inline void nvn_memory_sample(nvn_memory *s, uint64_t now, uint64_t left, int event) {
    // A suspended process has not observed a continuous safe interval. Do not
    // count a long timer gap or a clock rollback as time spent in recovery.
    if (s->last_sample && (now < s->last_sample || now - s->last_sample > 2000000000ull)) s->calm_since = 0;
    s->last_sample = now;
    if (event != NVN_MEM_POLL) {
        s->pressure = event == NVN_MEM_CRITICAL ? 2 : event == NVN_MEM_WARN ? 1 : 0;
        if (s->pressure) s->calm_since = 0;
    }
    int needed = s->pressure == 2 || left < (300ull << 20) ? 2
        : left < (600ull << 20) || (s->pressure == 1 && left < (768ull << 20)) ? 1 : 0;
    if (needed > s->level) s->level = needed;
    if (s->level == 2 && needed < 2 && s->pressure < 2 && left >= (600ull << 20)) s->level = 1;
    // 168 MiB of hysteresis above the low-water mark. The former 1 GiB exit
    // threshold was unreachable in a healthy ~800 MiB steady-state session.
    // Never resume while iOS still reports warning/critical, or after a lone
    // high sample. Zero available bytes is an emergency on iOS, not "a Mac".
    if (s->level && !s->pressure && left >= (768ull << 20)) {
        if (!s->calm_since || now < s->calm_since) s->calm_since = now;
        if (now - s->calm_since >= 10000000000ull) s->level = 0;
    } else s->calm_since = 0;
    s->reason = s->pressure == 2 ? NVN_MEM_OS_CRITICAL : left < (300ull << 20) ? NVN_MEM_HEADROOM_CRITICAL
        : left < (600ull << 20) ? NVN_MEM_HEADROOM_LOW : s->pressure ? NVN_MEM_OS_WARN
        : s->level ? NVN_MEM_RECOVERING : NVN_MEM_OK;
}
static inline const char *nvn_memory_reason(int reason) {
    static const char *const names[] = {"normal", "os-critical", "headroom-critical", "headroom-low", "os-warning", "recovery-hysteresis"};
    return reason >= 0 && reason < (int)(sizeof names / sizeof *names) ? names[reason] : "unknown";
}
