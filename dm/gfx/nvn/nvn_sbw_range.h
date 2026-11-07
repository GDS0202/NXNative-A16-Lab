#pragma once
#include <stdint.h>
// Conservative 16-byte tiles in one 4 KiB page. Mark all tiles touched by
// GPU writes; disjoint tiles do not invalidate uniform-buffer shadows.
static inline void nvn_sbw_mark16(uint64_t bits[4], unsigned begin, unsigned end) {
    if (begin >= end || end > 4096u) return;
    unsigned first = begin >> 4, last = (end - 1u) >> 4;
    for (unsigned word = first >> 6; word <= (last >> 6); word++) {
        unsigned lo = word == (first >> 6) ? (first & 63u) : 0u;
        unsigned hi = word == (last >> 6) ? (last & 63u) : 63u;
        bits[word] |= (UINT64_MAX << lo) & (UINT64_MAX >> (63u - hi));
    }
}
static inline int nvn_sbw_hits16(const uint64_t bits[4], unsigned begin, unsigned end) {
    if (begin >= end || end > 4096u) return 1; // ambiguous: fail closed
    unsigned first = begin >> 4, last = (end - 1u) >> 4;
    for (unsigned word = first >> 6; word <= (last >> 6); word++) {
        unsigned lo = word == (first >> 6) ? (first & 63u) : 0u;
        unsigned hi = word == (last >> 6) ? (last & 63u) : 63u;
        if (bits[word] & ((UINT64_MAX << lo) & (UINT64_MAX >> (63u - hi)))) return 1;
    }
    return 0;
}
