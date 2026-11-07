#pragma once
#include <stddef.h>
// Recent upload demand replaces the historic maximum; decay needs sustained
// low usage, faster under pressure, preventing allocation/release thrashing.
static inline size_t nvn_upload_recent_want(size_t previous, size_t observed,
                                             unsigned *quiet, int pressure) {
    const size_t minimum = 4u << 20, maximum = 32u << 20;
    if (observed > maximum) observed = maximum;
    if (observed >= previous) {
        *quiet = 0;
        return observed;
    }
    if (previous > minimum && observed <= previous / 2) {
        if (++*quiet >= (pressure ? 2u : 8u)) {
            previous /= 2;
            if (previous < observed) previous = observed;
            if (previous < minimum) previous = minimum;
            *quiet = 0;
        }
    } else *quiet = 0;
    return previous;
}
