#pragma once
#include <stdint.h>
#include <stddef.h>

// A zero-sized writable storage binding has UNKNOWN write extent. In the
// opt-in scoped experiment the only defensible approximation is its ENTIRE
// backing MTLBuffer allocation, never a guessed 1/4/4096-byte slice.
// The host refuses scoping on sparse/remapped memory, inaccessible allocations,
// arithmetic overflow or capacity exhaustion. Every failure falls back to the
// old submission-wide GPU-write hazard.
enum { NVN_SBW_SCOPE_CURRENT = 64, NVN_SBW_SCOPE_INFLIGHT = 128 };
typedef struct { uint64_t lo, hi, fence; } nvn_sbw_scope;

static inline int nvn_sbw_scope_resolve(uint64_t addr, uint64_t base,
                                        uint64_t bytes, uint64_t *lo, uint64_t *hi) {
    if (!bytes || base > UINT64_MAX - bytes || addr < base || addr >= base + bytes) return 0;
    *lo = base; *hi = base + bytes;
    return 1;
}
static inline int nvn_sbw_scope_add(nvn_sbw_scope *a, unsigned *n,
                                    unsigned cap, uint64_t lo, uint64_t hi, uint64_t fence) {
    if (hi <= lo) return 0;
    for (unsigned i = 0; i < *n; i++) {
        if (a[i].lo == lo && a[i].hi == hi) {
            if (fence > a[i].fence) a[i].fence = fence;
            return 1;
        }
    }
    if (*n >= cap) return 0;
    a[(*n)++] = (nvn_sbw_scope){lo, hi, fence};
    return 1;
}
static inline unsigned nvn_sbw_scope_prune(nvn_sbw_scope *a, unsigned n, uint64_t done) {
    unsigned w = 0;
    for (unsigned i = 0; i < n; i++)
        if (!a[i].fence || a[i].fence > done) a[w++] = a[i];
    return w;
}
static inline int nvn_sbw_scope_hits(const nvn_sbw_scope *a, unsigned n,
                                     uint64_t lo, uint64_t hi, uint64_t done) {
    if (hi <= lo) return 1;
    for (unsigned i = 0; i < n; i++)
        if ((!a[i].fence || a[i].fence > done) && lo < a[i].hi && a[i].lo < hi)
            return 1;
    return 0;
}
