#pragma once
#include <stdint.h>

// A hint only changes search order, never archive eligibility. All archives
// are still probed exactly once on a miss, including after a stale hint.
static inline uint32_t nvn_archive_probe(uint32_t position, uint32_t count, uint32_t hint) {
    if (hint >= count) return position;
    if (!position) return hint;
    uint32_t index = position - 1;
    return index >= hint ? index + 1 : index;
}
