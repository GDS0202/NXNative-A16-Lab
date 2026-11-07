#include "../nvn/nvn_upload_window.h"
#include <assert.h>
#include <stdio.h>
int main(void){
    size_t w=0; unsigned q=0;
    w=nvn_upload_recent_want(w,32u<<20,&q,0);assert(w==(32u<<20));
    for(int i=0;i<7;i++)w=nvn_upload_recent_want(w,1u<<20,&q,0);
    assert(w==(32u<<20));
    w=nvn_upload_recent_want(w,1u<<20,&q,0);assert(w==(16u<<20));
    w=nvn_upload_recent_want(w,32u<<20,&q,1);assert(w==(32u<<20));
    for(int i=0;i<6;i++)w=nvn_upload_recent_want(w,1u<<20,&q,1);
    assert(w==(4u<<20));
    w=nvn_upload_recent_want(w,20u<<20,&q,1);assert(w==(20u<<20));
    w=nvn_upload_recent_want(w,20u<<20,&q,1);assert(w==(20u<<20));
    puts("NVN staging demand: pressure-aware decay without hot thrash PASS");
    return 0;
}
