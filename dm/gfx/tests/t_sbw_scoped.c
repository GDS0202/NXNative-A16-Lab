#include "../nvn/nvn_sbw_scoped.h"
#include <assert.h>
#include <stdio.h>

static uint32_t rng = 0xC001C0DEu;
static uint32_t next(void) { rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5; return rng; }

int main(void) {
    uint64_t lo, hi;
    assert(nvn_sbw_scope_resolve(100, 64, 256, &lo, &hi) && lo == 64 && hi == 320);
    assert(!nvn_sbw_scope_resolve(63, 64, 256, &lo, &hi));
    assert(!nvn_sbw_scope_resolve(320, 64, 256, &lo, &hi));
    assert(!nvn_sbw_scope_resolve(100, 64, 0, &lo, &hi));
    assert(!nvn_sbw_scope_resolve(UINT64_MAX, UINT64_MAX-2, 4, &lo, &hi));
    nvn_sbw_scope a[3] = {{0}}; unsigned n = 0;
    assert(nvn_sbw_scope_add(a, &n, 3, 64, 320, 0) && n == 1);
    assert(nvn_sbw_scope_add(a, &n, 3, 64, 320, 0) && n == 1);
    assert(!nvn_sbw_scope_hits(a, n, 0, 64, 0));
    assert(nvn_sbw_scope_hits(a, n, 320-1, 321, 0));
    assert(nvn_sbw_scope_add(a, &n, 3, 512, 768, 9));
    assert(nvn_sbw_scope_add(a, &n, 3, 900, 1000, 11));
    assert(!nvn_sbw_scope_add(a, &n, 3, 1100, 1200, 12));
    assert(nvn_sbw_scope_hits(a, n, 700, 701, 8));
    assert(!nvn_sbw_scope_hits(a, n, 700, 701, 9));
    assert(nvn_sbw_scope_hits(a, n, 950, 951, 10));
    assert(!nvn_sbw_scope_hits(a, n, 950, 951, 11));
    assert(nvn_sbw_scope_add(a, &n, 3, 512, 768, 17));
    assert(nvn_sbw_scope_hits(a, n, 700, 701, 9));
    nvn_sbw_scope_prune(a, n, 17);

    // Differential randomized range oracle, including partial overlaps and
    // generations of completed work. Never accept a false negative.
    for (int trial=0; trial<4000; trial++) {
        nvn_sbw_scope entries[64]={{0}}; unsigned count=0;
        for (int i=0; i<48; i++) {
            uint64_t begin=next()%4096, len=1+next()%512;
            uint64_t fence=1+next()%30;
            assert(nvn_sbw_scope_add(entries,&count,64,begin,begin+len,fence));
        }
        uint64_t done=next()%30;
        for (int j=0; j<20; j++) {
            uint64_t begin=next()%4096, end=begin+1+next()%512;
            int oracle=0;
            for (unsigned k=0; k<count; k++)
                oracle|=entries[k].fence>done && begin<entries[k].hi && entries[k].lo<end;
            assert(nvn_sbw_scope_hits(entries,count,begin,end,done)==oracle);
        }
        count=nvn_sbw_scope_prune(entries,count,done);
        for(unsigned k=0;k<count;k++) assert(entries[k].fence>done);
    }
    puts("bounded unknown GPU-write allocation scopes: PASS");
    return 0;
}
