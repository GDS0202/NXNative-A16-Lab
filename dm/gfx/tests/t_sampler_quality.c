#include "../nvn/nvn_sampler_quality.h"
#include <assert.h>
#include <stdio.h>
int main(void) {
    for (int q = 0; q <= 2; q++) {
        assert(nvn_sampler_anisotropy(8, q, 5, 1, 1, 0, 0, 12, 0) == 8); // Shadow compare.
        assert(nvn_sampler_anisotropy(8, q, 5, 1, 0, 1, 0, 12, 0) == 8); // Reduction data.
        assert(nvn_sampler_anisotropy(8, q, 5, 1, 0, 0, 1, 12, 0) == 8); // Explicit LOD range.
        assert(nvn_sampler_anisotropy(8, q, 5, 1, 0, 0, 0, 1, 0) == 8); // Single/two-level data.
        assert(nvn_sampler_anisotropy(8, q, 5, 1, 0, 0, 0, 12, 1) == 8); // Guest bias.
        assert(nvn_sampler_anisotropy(8, q, 1, 1, 0, 0, 0, 12, 0) == 8); // Nonmipmapped.
        assert(nvn_sampler_anisotropy(1, q, 5, 1, 0, 0, 0, 12, 0) == 1); // Lighting/data stays original.
    }
    assert(nvn_sampler_anisotropy(8, 0, 5, 1, 0, 0, 0, 12, 0) == 8);
    assert(nvn_sampler_anisotropy(8, 1, 5, 1, 0, 0, 0, 12, 0) == 2);
    assert(nvn_sampler_anisotropy(8, 2, 5, 1, 0, 0, 0, 12, 0) == 1);
    assert(nvn_sampler_anisotropy(NAN, 2, 5, 1, 0, 0, 0, 12, 0) == 1);
    puts("Sampler quality: original, eligible cost limits, protected data/shadow/LOD semantics PASS");
    return 0;
}
