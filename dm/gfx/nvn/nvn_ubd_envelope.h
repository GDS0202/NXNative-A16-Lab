#pragma once
#include <stdint.h>

// The envelope contains every deferred uniform update since the last flush.
// A query entirely outside it cannot overlap any of those writes, so it may
// skip the slower per-page filter. Gaps *inside* the envelope stay conservative:
// the existing per-page and exact-range checks still decide their overlap.
typedef struct { uint64_t lo, hi; } nvn_ubd_envelope;
#define NVN_UBD_ENVELOPE_INITIALIZER { UINT64_MAX, 0 }

static inline void nvn_ubd_envelope_reset(nvn_ubd_envelope *e) {
    e->lo = UINT64_MAX; e->hi = 0;
}
static inline void nvn_ubd_envelope_add(nvn_ubd_envelope *e, uint64_t lo, uint64_t hi) {
    if (hi <= lo) return;
    if (lo < e->lo) e->lo = lo;
    if (hi > e->hi) e->hi = hi;
}
static inline int nvn_ubd_envelope_may_overlap(const nvn_ubd_envelope *e,
                                                 uint64_t lo, uint64_t hi) {
    return hi > lo && hi > e->lo && lo < e->hi;
}
