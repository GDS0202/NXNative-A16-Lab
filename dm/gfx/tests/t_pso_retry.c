#include "../nvn/nvn_pso_retry.h"
#include <assert.h>
#include <stdio.h>
int main(void) {
    uint64_t at = nvn_pso_retry_deadline(2000000000ull,1);
    assert(at == 7000000000ull);
    assert(!nvn_pso_retry_due(at,at,1)); // Never while the memory guard is active.
    assert(!nvn_pso_retry_due(at-1,at,0));
    assert(nvn_pso_retry_due(at,at,0));
    assert(nvn_pso_retry_deadline(1000000000ull,0)==0);
    assert(!nvn_pso_retry_due(UINT64_MAX,0,0));
    assert(nvn_pso_retry_deadline(UINT64_MAX-1,1)==UINT64_MAX);
    puts("Bounded one-shot pipeline retry after memory-pressure recovery PASS");
    return 0;
}
