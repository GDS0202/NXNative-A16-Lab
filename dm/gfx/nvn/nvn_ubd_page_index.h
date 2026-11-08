#pragma once
#include <stdint.h>
#include <string.h>

// Conservative index of deferred uniform updates by 4 KiB guest pages.
// A full table must NEVER spin indefinitely: mark the index as wide and
// let the caller use its existing exact-range check for every candidate.
// Dropping an index entry is safe only when all lookups become positive.
enum { NVN_UBD_INDEX_N = 1024, NVN_UBD_INDEX_SPAN = 16 };
typedef struct {
    uint64_t pages[NVN_UBD_INDEX_N]; // page number + 1, zero means empty
    int wide;
} nvn_ubd_page_index;

static inline unsigned nvn_ubd_page_hash(uint64_t pg) {
    return (unsigned)((pg * UINT64_C(0x9E3779B97F4A7C15)) >> 54) & (NVN_UBD_INDEX_N - 1);
}
static inline void nvn_ubd_index_reset(nvn_ubd_page_index *idx) {
    memset(idx, 0, sizeof *idx);
}
static inline void nvn_ubd_index_add(nvn_ubd_page_index *idx, uint64_t lo, uint64_t hi) {
    if (hi <= lo || idx->wide) return;
    uint64_t first = lo >> 12, last = (hi - 1) >> 12;
    if (last - first > NVN_UBD_INDEX_SPAN) { idx->wide = 1; return; }
    for (uint64_t pg = first; pg <= last; pg++) {
        unsigned h = nvn_ubd_page_hash(pg);
        int found = 0;
        for (unsigned probe = 0; probe < NVN_UBD_INDEX_N; probe++, h = (h + 1) & (NVN_UBD_INDEX_N - 1)) {
            if (!idx->pages[h] || idx->pages[h] == pg + 1) {
                idx->pages[h] = pg + 1; found = 1; break;
            }
        }
        if (!found) {
            // A future lookup must conservatively claim a possible overlap.
            idx->wide = 1; return;
        }
    }
}
static inline int nvn_ubd_index_may_overlap(const nvn_ubd_page_index *idx, uint64_t lo, uint64_t hi) {
    if (hi <= lo) return 0;
    uint64_t first = lo >> 12, last = (hi - 1) >> 12;
    if (idx->wide || last - first > NVN_UBD_INDEX_SPAN) return 1;
    for (uint64_t pg = first; pg <= last; pg++) {
        unsigned h = nvn_ubd_page_hash(pg);
        for (unsigned probe = 0; probe < NVN_UBD_INDEX_N; probe++, h = (h + 1) & (NVN_UBD_INDEX_N - 1)) {
            if (!idx->pages[h]) break;
            if (idx->pages[h] == pg + 1) return 1;
        }
    }
    return 0;
}
