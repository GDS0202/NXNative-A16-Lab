#include "../nvn/nvn_sbw_range.h"
#include <assert.h>
#include <stdio.h>
static void check(int begin, int end) {
    uint64_t bits[4]={0};
    nvn_sbw_mark16(bits, (unsigned)begin, (unsigned)end);
    for (int a=0;a<4096;a+=3) {
        int b=a+7; if(b>4096)b=4096;
        if(a<end&&begin<b) assert(nvn_sbw_hits16(bits,(unsigned)a,(unsigned)b));
    }
}
int main(void) {
    uint64_t bits[4]={0};
    nvn_sbw_mark16(bits,64,80);
    assert(nvn_sbw_hits16(bits,64,80));
    assert(!nvn_sbw_hits16(bits,80,96));
    assert(!nvn_sbw_hits16(bits,0,64));
    assert(nvn_sbw_hits16(bits,79,81));
    nvn_sbw_mark16(bits,4080,4096);
    assert(nvn_sbw_hits16(bits,4095,4096));
    assert(!nvn_sbw_hits16(bits,4064,4080));
    for (int start=0;start<4096;start+=137)for(int len=1;len<=80;len+=11) {
        int end=start+len;if(end>4096)end=4096;
        check(start,end);
    }
    assert(nvn_sbw_hits16(bits,4096,4096)); // conservative unknown range
    puts("NVN GPU-write ranges: conservative overlap and disjoint tiles PASS");
    return 0;
}
