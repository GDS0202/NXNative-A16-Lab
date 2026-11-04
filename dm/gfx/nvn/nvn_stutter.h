#pragma once
#include <stdint.h>

// Wall-clock spans and counter deltas observed during one guest present interval.
// Work can overlap across threads: these are evidence, not additive root causes.
#define NVN_STUTTER_METRICS(X) \
    X(frame_ms) X(work_ms) X(nvn_ms) X(gpu_ms) X(compile_ms) \
    X(upload_ms) X(upload_gpu_ms) X(sync_ms) X(acquire_ms) X(present_wait_ms) \
    X(drawable_ms) X(sub_wall_ms) X(sub_cpu_ms) X(process_cpu_ms) \
    X(bc_decode_ms) X(bc_cache_ms) X(expected_ms)
typedef struct {
    uint64_t frame, timestamp_ns;
#define NVN_STUTTER_FIELD(name) double name;
    NVN_STUTTER_METRICS(NVN_STUTTER_FIELD)
#undef NVN_STUTTER_FIELD
    uint64_t upload_bytes, cache_hits, cache_misses, pso_new, library_new, bc_calls;
} nvn_stutter_sample;

// DM_STUTTER=1: at most 64 MiB per session plus one previous file, a bounded
// queue, no allocations or disk I/O on producers. Saturation is counted, never
// hidden; an incomplete trace cannot certify performance.
int nvn_stutter_start(void);  // call only after launcher/env choices are applied
int nvn_stutter_enabled(void);  // pure query; early device/UI setup must not freeze defaults
void nvn_stutter_frame(const nvn_stutter_sample *sample);
void nvn_stutter_present(uint64_t frame, uint64_t ticket, uint64_t timestamp_ns);
void nvn_stutter_system(uint64_t timestamp_ns, uint64_t footprint, uint64_t headroom, int thermal, int low_power);
void nvn_stutter_boundary(uint64_t timestamp_ns);  // pause/resume; do not join display intervals across it
uint64_t nvn_stutter_lost(void);
void nvn_stutter_stop(void);  // exit/tests only; never in a frame or presentation callback
