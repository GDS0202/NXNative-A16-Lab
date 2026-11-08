#include "../nvn/nvn_sbw_sparse.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

// Compare the sparse write-page path with a brute-force page walk including
// disjoint 16-byte masks, unsorted page registration, and reports-only pages.
enum { N = 128 };
static nvn_sbw_page page[N];
static uint16_t index_[N];
static int reference(uint64_t lo, uint64_t hi, int fine, int *shared) {
    *shared = 0;
    if (hi <= lo) return 1;
    for (uint64_t pg = lo >> 12; pg <= (hi - 1) >> 12; pg++) {
        for (unsigned i = 0; i < N; i++) {
            const nvn_sbw_page *p = page + index_[i];
            if (p->page != pg || !(p->src & 1)) continue;
            *shared = 1;
            unsigned first = pg == (lo >> 12) ? (unsigned)(lo & 4095u) : 0u;
            unsigned end = pg == ((hi - 1) >> 12) ? (unsigned)((hi - 1) & 4095u) + 1u : 4096u;
            if (!fine || nvn_sbw_hits16(p->gpu_mask, first, end)) return 1;
        }
    }
    return 0;
}
int main(void) {
    for (unsigned i = 0; i < N; i++) {
        unsigned j = (i * 73u) & (N-1); // Deterministic permutation, unsorted.
        index_[i] = (uint16_t)j;
        page[j].page = 100 + (uint64_t)j * 31u;
        page[j].src = j % 5 ? 1 : 2;
        nvn_sbw_mark16(page[j].gpu_mask, (j * 19u) & 4095u,
                       ((j * 19u) & 4095u) + 1u);
    }
    assert(nvn_sbw_sparse_worthwhile(0, (1ull<<24), N));
    assert(!nvn_sbw_sparse_worthwhile(0, 4096, N));
    assert(!nvn_sbw_sparse_worthwhile(1, 1, N));
    for (int fine = 0; fine <= 1; fine++) {
        for (int q = 0; q < 100; q++) {
            uint64_t start = (uint64_t)(q*43u) * 4096u + (q*197u)%4096u;
            uint64_t end = start + (uint64_t)(q%7 ? 1240000u : 17000000u);
            int s1 = 0, s2 = 0;
            int expected = reference(start,end,fine,&s1);
            int actual = nvn_sbw_sparse_hits(page,index_,N,start,end,fine,&s2);
            assert(expected == actual && s1 == s2);
        }
    }
    // Last page of 64-bit address space: calculation must not wrap.
    page[0].page = UINT64_MAX >> 12; page[0].src = 1;
    nvn_sbw_mark16(page[0].gpu_mask, 4080, 4096);
    int shared = 0;
    assert(nvn_sbw_sparse_hits(page,index_,N,UINT64_MAX-15,UINT64_MAX,1,&shared));
    assert(shared);
    puts("NVN sparse GPU-write page scans: match full page scans, including high addresses PASS");
    return 0;
}
