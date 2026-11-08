#include "../nvn/nvn_ubd_envelope.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>

static int actual(uint64_t lo, uint64_t hi,
                  const uint64_t ranges[][2], unsigned count) {
    for (unsigned i = 0; i < count; i++)
        if (lo < ranges[i][1] && ranges[i][0] < hi) return 1;
    return 0;
}

int main(void) {
    nvn_ubd_envelope env = NVN_UBD_ENVELOPE_INITIALIZER;
    assert(!nvn_ubd_envelope_may_overlap(&env, 0, UINT64_MAX));
    const uint64_t ranges[][2] = {
        {4096, 4160}, {6000, 6176}, {16384, 20480},
        {UINT64_MAX - 1024, UINT64_MAX - 4}
    };
    for (unsigned i = 0; i < 3; i++) {
        nvn_ubd_envelope_add(&env, ranges[i][0], ranges[i][1]);
        // A wider envelope is legal (false positives); false negatives are not.
        for (uint64_t lo = 0; lo < 22000; lo += 13) {
            uint64_t hi = lo + 12;
            if (actual(lo, hi, ranges, i + 1))
                assert(nvn_ubd_envelope_may_overlap(&env, lo, hi));
        }
    }
    assert(!nvn_ubd_envelope_may_overlap(&env, 0, 4096));
    assert(!nvn_ubd_envelope_may_overlap(&env, 20480, 22000));
    assert(nvn_ubd_envelope_may_overlap(&env, 4160, 16384)); // gap: conservative
    nvn_ubd_envelope_reset(&env);
    assert(!nvn_ubd_envelope_may_overlap(&env, 4096, 4160));
    nvn_ubd_envelope_add(&env, ranges[3][0], ranges[3][1]);
    assert(nvn_ubd_envelope_may_overlap(&env, UINT64_MAX - 20, UINT64_MAX));
    assert(!nvn_ubd_envelope_may_overlap(&env, 0, UINT64_MAX - 1024));
    nvn_ubd_envelope_reset(&env);
    assert(!nvn_ubd_envelope_may_overlap(&env, 0, UINT64_MAX));
    puts("Deferred uniform envelope: no false negatives, sparse gaps, reset and high addresses PASS");
    return 0;
}
