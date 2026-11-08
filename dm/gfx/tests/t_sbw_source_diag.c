#include "../nvn/nvn_sbw_source_diag.h"
#include <assert.h>
#include <stdio.h>

int main(void) {
    const uint64_t limit = 4096ull * 4096ull; // 16 MiB tracking limit
    assert(NVN_SBW_SOURCE_COUNTERS == 12);
    for (unsigned origin = 0; origin < NVN_SBW_FROM_COUNT; ++origin)
        for (unsigned field = 0; field < NVN_SBW_SRC_FIELDS; ++field)
            assert(nvn_sbw_source_counter(origin, field) == origin * 4 + field);

    assert(nvn_sbw_source_span_kind(4096, 4096, limit) == NVN_SBW_SRC_NOTES);
    assert(nvn_sbw_source_span_kind(4096, limit, limit) == NVN_SBW_SRC_NOTES);
    assert(nvn_sbw_source_span_kind(4096, limit + 1, limit) == NVN_SBW_SRC_LARGE);
    assert(nvn_sbw_source_span_kind(0, 0, limit) == NVN_SBW_SRC_UNKNOWN);
    assert(nvn_sbw_source_span_kind(UINT64_MAX - 1, 3, limit) == NVN_SBW_SRC_UNKNOWN);
    assert(nvn_sbw_source_span_kind(UINT64_MAX - 3, 3, limit) == NVN_SBW_SRC_NOTES);
    assert(nvn_sbw_source_span_kind(UINT64_MAX, UINT64_MAX, limit) == NVN_SBW_SRC_UNKNOWN);

    puts("NVN GPU-write source categories: bounded counters and overflow-safe classification PASS");
    return 0;
}
