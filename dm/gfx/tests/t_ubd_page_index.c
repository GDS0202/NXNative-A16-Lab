#include "../nvn/nvn_ubd_page_index.h"
#include "../nvn/nvn_ubd_envelope.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>

// The real pipeline may reject an overlap in its exact-range filter, but must
// never miss a truly deferred update even when this page table saturates.
static int may_overlap(nvn_ubd_page_index *idx, nvn_ubd_envelope *env,
                       uint64_t a, uint64_t b) {
    return nvn_ubd_envelope_may_overlap(env, a, b) &&
           nvn_ubd_index_may_overlap(idx, a, b);
}
static void add(nvn_ubd_page_index *idx, nvn_ubd_envelope *env, uint64_t lo, uint64_t hi) {
    nvn_ubd_envelope_add(env, lo, hi);
    nvn_ubd_index_add(idx, lo, hi);
}
int main(void) {
    nvn_ubd_page_index idx = {0};
    nvn_ubd_envelope env = NVN_UBD_ENVELOPE_INITIALIZER;
    assert(!may_overlap(&idx, &env, 0, UINT64_MAX));
    // 1024 disjoint pages fill the hash completely without wide writes. The
    // next unsuccessful lookup previously probed indefinitely.
    for (uint64_t pg = 0; pg < NVN_UBD_INDEX_N; pg++) {
        uint64_t lo = pg * 4096u + 32u;
        add(&idx, &env, lo, lo + 64);
        assert(!idx.wide);
        assert(may_overlap(&idx, &env, lo, lo + 64));
    }
    // Probe a missing page against a completely full table. Before the fix
    // the index lookup never terminated, even though the page was absent.
    // The new write to that page then forces conservative wide fallback.
    assert(!nvn_ubd_index_may_overlap(&idx, 1024ull * 4096u, 1024ull * 4096u + 1));
    assert(may_overlap(&idx, &env, 4096u - 32u, 4096u + 64u)); // adjacent real page
    add(&idx, &env, 1024ull * 4096u, 1024ull * 4096u + 64u);
    assert(idx.wide); // no more room: fail closed
    assert(may_overlap(&idx, &env, 2000, 2048)); // gap in first page: false-positive acceptable
    assert(may_overlap(&idx, &env, 1024ull * 4096u, 1024ull * 4096u + 64u));
    assert(!may_overlap(&idx, &env, 5000ull * 4096u, 5000ull * 4096u + 64u));

    nvn_ubd_index_reset(&idx);
    nvn_ubd_envelope_reset(&env);
    assert(!idx.wide);
    assert(!may_overlap(&idx, &env, 0, UINT64_MAX));

    // Wide-range writes must still force a conservative positive lookup.
    add(&idx, &env, 0x1000000ull, 0x1000000ull + 19u * 4096u);
    assert(idx.wide);
    assert(may_overlap(&idx, &env, 0x1000000ull + 1000, 0x1000000ull + 1010));
    assert(!may_overlap(&idx, &env, 0, 4096));

    nvn_ubd_index_reset(&idx); nvn_ubd_envelope_reset(&env);
    add(&idx, &env, UINT64_MAX - 511, UINT64_MAX);
    assert(may_overlap(&idx, &env, UINT64_MAX - 5, UINT64_MAX));
    assert(!may_overlap(&idx, &env, UINT64_MAX - 1024, UINT64_MAX - 512));

    puts("Deferred uniform page index: saturated negative lookup, safe global fallback, reset, and 64-bit bounds PASS");
    return 0;
}
