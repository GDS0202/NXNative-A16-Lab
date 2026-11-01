#include "nvn_frame_metrics.h"
#include <pthread.h>
#include <stdlib.h>
#include <string.h>
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static uint64_t intervals[256], last;
static unsigned count, cursor;
void nvn_frame_metrics_record(uint64_t ns) {
    if (!ns) return;
    pthread_mutex_lock(&lock);
    if (last && ns > last) { intervals[cursor++ % 256] = ns - last; if (count < 256) count++; }
    if (ns > last) last = ns;   // ignore duplicate/out-of-order callbacks
    pthread_mutex_unlock(&lock);
}
void nvn_frame_metrics_reset(void) { pthread_mutex_lock(&lock); count = cursor = 0; last = 0; pthread_mutex_unlock(&lock); }
static int compare(const void *a, const void *b) { uint64_t x = *(const uint64_t *)a, y = *(const uint64_t *)b; return x > y ? 1 : x < y ? -1 : 0; }
nvn_frame_metrics nvn_frame_metrics_snapshot(void) {
    uint64_t sorted[256]; nvn_frame_metrics out = {0};
    pthread_mutex_lock(&lock); unsigned n = count; memcpy(sorted, intervals, n * sizeof *sorted); pthread_mutex_unlock(&lock);
    if (!n) return out;
    qsort(sorted, n, sizeof *sorted, compare); out.samples = n;
    out.p95_ms = sorted[(95 * n + 99) / 100 - 1] / 1e6;
    out.p99_ms = sorted[(99 * n + 99) / 100 - 1] / 1e6; out.worst_ms = sorted[n - 1] / 1e6;
    for (unsigned i = 0; i < n; i++) out.stalls50 += sorted[i] >= 50000000ull;
    return out;
}
