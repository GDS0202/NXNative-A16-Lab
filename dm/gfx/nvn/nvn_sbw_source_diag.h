#pragma once
#include <stdint.h>

// Source-only diagnostics for guest-visible GPU writes. All decisions remain
// in the renderer's existing sbw_note()/ubp_get() safety checks.
// A "note" is a binding/copy observation, not a distinct draw or memory write.
enum {
    NVN_SBW_FROM_STORAGE = 0,    // Bound storage buffer, explicit guest span
    NVN_SBW_FROM_BINDLESS = 1,   // GPU address read from a uniform, unknown span
    NVN_SBW_FROM_COPY = 2,       // Texture-to-buffer copy, explicit destination
    NVN_SBW_FROM_COUNT = 3,
    NVN_SBW_FROM_NONE = -1       // Counter reports are not shadow hazards
};
enum {
    NVN_SBW_SRC_NOTES = 0,
    NVN_SBW_SRC_UNKNOWN = 1,
    NVN_SBW_SRC_LARGE = 2,
    NVN_SBW_SRC_CAPACITY = 3,
    NVN_SBW_SRC_FIELDS = 4
};
enum { NVN_SBW_SOURCE_COUNTERS = NVN_SBW_FROM_COUNT * NVN_SBW_SRC_FIELDS };

static inline unsigned nvn_sbw_source_counter(unsigned source, unsigned field) {
    return source * NVN_SBW_SRC_FIELDS + field;
}
// UNKNOWN includes zero-length writes and address+size overflow. LARGE is
// strictly above the trackable 16 MiB span, not an ordinary page conflict.
static inline unsigned nvn_sbw_source_span_kind(uint64_t addr, uint64_t size,
                                                uint64_t maximum) {
    if (!size || addr > UINT64_MAX - size) return NVN_SBW_SRC_UNKNOWN;
    return size > maximum ? NVN_SBW_SRC_LARGE : NVN_SBW_SRC_NOTES;
}
