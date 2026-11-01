#include "../nvn/nvn_frame_metrics.h"
#include <assert.h>
#include <pthread.h>
#include <stdio.h>
static void *reader(void *p) { (void)p; for (int i=0;i<10000;i++) { nvn_frame_metrics x=nvn_frame_metrics_snapshot(); assert(x.samples<=256); } return NULL; }
int main(void) {
    nvn_frame_metrics_reset(); assert(!nvn_frame_metrics_snapshot().samples);
    uint64_t now=1000000000ull; nvn_frame_metrics_record(now);
    for (unsigned i=0;i<100;i++) { now += i < 94 ? 16666667ull : 80000000ull; nvn_frame_metrics_record(now); }
    nvn_frame_metrics x=nvn_frame_metrics_snapshot(); assert(x.samples==100 && x.stalls50==6 && x.p95_ms==80 && x.p99_ms==80);
    nvn_frame_metrics_record(now); nvn_frame_metrics_record(now-1); assert(nvn_frame_metrics_snapshot().samples==100);
    pthread_t t; assert(!pthread_create(&t,NULL,reader,NULL));
    for (int i=0;i<1000;i++) { now += 33333333; nvn_frame_metrics_record(now); }
    pthread_join(t,NULL); x=nvn_frame_metrics_snapshot(); assert(x.samples==256 && x.stalls50==0 && x.p95_ms>33 && x.p95_ms<34);
    nvn_frame_metrics_reset(); assert(!nvn_frame_metrics_snapshot().samples);
    puts("Presentation metrics: percentiles, stalls, rollover, callback order, concurrency PASS");
}
