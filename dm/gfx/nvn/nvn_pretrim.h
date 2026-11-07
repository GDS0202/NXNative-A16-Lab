#pragma once
#include <stdint.h>

// Predictive cleanup is deliberately independent of the safety FPS cap.
// Called on the sole submission thread at most once per second.
typedef struct {
    uint64_t low_since, high_since, last_sample;
    int active;
} nvn_pretrim;

static inline int nvn_pretrim_tick(nvn_pretrim *s, uint64_t now, uint64_t headroom, int os_pressure) {
    // Suspension or a reversed clock cannot count as observed safe/low time.
    if (s->last_sample && (now <= s->last_sample || now - s->last_sample > 3000000000ull)) {
        s->low_since = s->high_since = 0;
    }
    s->last_sample = now;
    if (os_pressure) { s->active = 1; s->high_since = 0; return 1; }
    if (headroom < (1024ull << 20)) {
        s->high_since = 0;
        if (!s->low_since) s->low_since = now;
        if (now >= s->low_since && now - s->low_since >= 2000000000ull) s->active = 1;
    } else if (headroom >= (1152ull << 20)) {
        s->low_since = 0;
        if (!s->high_since) s->high_since = now;
        if (now >= s->high_since && now - s->high_since >= 8000000000ull) s->active = 0;
    } else {
        // Middle band neither starts an intervention nor proves sustained safety.
        s->low_since = s->high_since = 0;
    }
    return s->active;
}
