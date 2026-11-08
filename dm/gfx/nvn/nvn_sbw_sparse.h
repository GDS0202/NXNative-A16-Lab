#pragma once
#include <stdint.h>
#include "nvn_sbw_range.h"

// Sparse-page lookup for huge reads: if only a few GPU-written pages are known,
// testing those pages beats probing every 4 KiB page in a large texture source.
// The table holds every active page of the submission, including counter-report
// pages, but only GPU-write pages with the requested overlap can cause a hazard.
// Masks and page bounds are still conservative at the original 16-byte scale.
typedef struct { uint64_t page, gpu_mask[4]; uint32_t gen; uint8_t src; } nvn_sbw_page;

static inline int nvn_sbw_sparse_worthwhile(uint64_t lo, uint64_t hi, unsigned tracked) {
    if (hi <= lo || !tracked) return 0;
    const uint64_t pages = ((hi - 1u) >> 12) - (lo >> 12) + 1u;
    return pages > 64u && pages > (uint64_t)tracked * 4u;
}
// Returns 1 on a true/assumed GPU-write hazard, 0 otherwise.
// 'shared_page' notes a GPU-written page in the range even if the 16-byte
// masks are disjoint, to retain the old diagnostics.
static inline int nvn_sbw_sparse_hits(const nvn_sbw_page *table,
                                      const uint16_t *indices, unsigned n,
                                      uint64_t lo, uint64_t hi, int fine,
                                      int *shared_page) {
    *shared_page = 0;
    if (hi <= lo) return 1; // Unknown read extent: conservative.
    const uint64_t first_page = lo >> 12, last_page = (hi - 1u) >> 12;
    for (unsigned i = 0; i < n; i++) {
        const nvn_sbw_page *p = table + indices[i];
        if (!(p->src & 1u) || p->page < first_page || p->page > last_page) continue;
        *shared_page = 1;
        if (!fine) return 1;  // Page-granular A/B fallback unchanged.
        unsigned first = p->page == first_page ? (unsigned)(lo & 4095u) : 0u;
        unsigned end = p->page == last_page ? (unsigned)((hi - 1u) & 4095u) + 1u : 4096u;
        if (nvn_sbw_hits16(p->gpu_mask, first, end)) return 1;
    }
    return 0;
}
