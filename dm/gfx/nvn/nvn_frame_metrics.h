#pragma once
#include <stdint.h>
typedef struct { unsigned samples, stalls50; double p95_ms, p99_ms, worst_ms; } nvn_frame_metrics;
// Actual drawable presentation times, not encode/commit times or timer ticks.
// A bounded 256-interval window; callbacks may arrive on different threads.
void nvn_frame_metrics_record(uint64_t ns);
void nvn_frame_metrics_reset(void);
nvn_frame_metrics nvn_frame_metrics_snapshot(void);
