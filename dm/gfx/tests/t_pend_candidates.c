#include "../nvn/nvn_pend_candidates.h"
#include <assert.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>

int main(void) {
    int small[] = {5, 2, 5, 8, 1, 2};
    int n = nvn_pend_candidates_finish(small, 6, 1);
    assert(n == 4 && small[0] == 8 && small[1] == 5 &&
           small[2] == 2 && small[3] == 1);

    int extremes[] = {INT_MIN, INT_MAX, 0, INT_MIN, INT_MAX};
    n = nvn_pend_candidates_finish(extremes, 5, 1);
    assert(n == 3 && extremes[0] == INT_MAX &&
           extremes[1] == 0 && extremes[2] == INT_MIN);

    enum { CANDIDATES = 16384, ENTRIES = 8192 };
    int *many = malloc((CANDIDATES + 1u) * sizeof *many);
    assert(many);
    n = 0;
    for (int e = 0; e < ENTRIES; e++) {
        n = nvn_pend_candidate_add(many, n, CANDIDATES, e);
        assert(n > 0);
        n = nvn_pend_candidate_add(many, n, CANDIDATES, e);
        assert(n > 0);
    }
    // One more append must fail rather than overwrite the sentinel.
    many[CANDIDATES] = INT_MAX;
    assert(n == CANDIDATES);
    assert(nvn_pend_candidate_add(many, n, CANDIDATES, 17) == -1);
    assert(many[CANDIDATES] == INT_MAX);
    n = nvn_pend_candidates_finish(many, n, 1);
    assert(n == ENTRIES);
    for (int i = 0; i < n; i++) assert(many[i] == ENTRIES - i - 1);

    // A single hash chain is already newest-first; do not mutate it.
    int single[] = {7, 5, 4, 2};
    n = nvn_pend_candidates_finish(single, 4, 0);
    assert(n == 4 && single[0] == 7 && single[3] == 2);
    free(many);
    puts("Pending GPU write candidates: full buffer bounded, 16k duplicate entries deduped, ordering preserved PASS");
    return 0;
}
