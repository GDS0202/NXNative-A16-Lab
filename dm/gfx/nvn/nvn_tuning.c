#include "nvn_tuning.h"
#include <math.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// Fixed-size observations, no file I/O, compiler invocation or GPU allocation.
// This is a feedback controller, not a promise that the requested FPS is possible.
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static dm_tuning_snapshot state;
static unsigned char *guest;
static _Atomic int initialized, detail, output_height = 720, upscale_mode = -1;
static _Atomic int measure_active;
static int changed, low_power, system_known;
static uint64_t last, window_start, last_change;
static double gpu_samples[120], frame_samples[120];
static unsigned samples;
static unsigned good_windows, bad_windows;
static uint64_t measure_first, measure_last;
static double measure_intervals[4096];
static unsigned measure_count;
static void cancel_measurement(void) {
    state.measuring = state.measured_complete = state.measured_frames = 0;
    state.measured_fps = state.measured_p95 = state.measured_seconds = 0;
    measure_first = measure_last = measure_count = 0;
    atomic_store(&measure_active, 0);
}

static int compare(const void *a, const void *b) {
    double x = *(const double *)a, y = *(const double *)b;
    return (x > y) - (x < y);
}
static double percentile(const double *v, unsigned n, double p) {
    double sorted[4096];
    if (!n) return 0;
    memcpy(sorted, v, n * sizeof *v);
    qsort(sorted, n, sizeof *v, compare);
    return sorted[(unsigned)ceil(p * n) - 1];
}
static int minimum(void) {
    // Round UP to a supported 5% step: a floor must never silently lose pixels.
    return ((state.requested.min_height * 20 + state.height - 1) / state.height) * 5;
}
static void word(unsigned off, uint32_t v) {
    if (guest) __atomic_store_n((uint32_t *)(guest + off), v, __ATOMIC_RELEASE);
}
static void scalar(unsigned off, float v) { uint32_t b; memcpy(&b, &v, 4); word(off, b); }
static void apply(void) {
    scalar(0, (float)state.requested.target);
    if (state.capabilities & DM_TUNE_SCALE) {
        scalar(0x10, state.scale / 100.0f);
        // New guest stubs read this flag. Old stubs never receive an undocumented sentinel.
        if (state.capabilities & DM_TUNE_FULL_SCALE) word(0x14, state.requested.automatic || state.requested.fixed);
    }
    if (state.capabilities & DM_TUNE_CLIP) scalar(0x18, (float)state.far_clip);
    atomic_store_explicit(&detail, state.texture, memory_order_release);
}
static int assign(const char *key, int v) {
    dm_tuning_config *c = &state.requested;
    if (!strcmp(key, "DM_AUTO_QUALITY")) { if (v < 0 || v > 1 || (v && (!(state.capabilities & DM_TUNE_SCALE) || !c->target))) return 0; c->automatic = v; }
    else if (!strcmp(key, "DM_FPS_TARGET")) { if ((v != 0 && v != 30 && v != 60) || (!v && c->automatic)) return 0; c->target = v; }
    else if (!strcmp(key, "DM_RENDER_FIXED")) { if (v < 0 || v > 1 || !(state.capabilities & DM_TUNE_FULL_SCALE)) return 0; c->fixed = v; }
    else if (!strcmp(key, "DM_RENDER_SCALE")) {
        if (!(state.capabilities & DM_TUNE_SCALE) || v < 50 || v > 100 || v % 5) return 0;
        if (v == 100 && !(state.capabilities & DM_TUNE_FULL_SCALE) && c->automatic) return 0;
        c->scale = v;
    }
    else if (!strcmp(key, "DM_AUTO_MIN_HEIGHT")) {
        if (v < state.height / 2 || v > state.height || !(state.capabilities & DM_TUNE_SCALE)) return 0;
        if (v == state.height && !(state.capabilities & DM_TUNE_FULL_SCALE)) return 0;
        c->min_height = v;
    }
    else if (!strcmp(key, "DM_TEXTURE_DETAIL")) { if (v < 0 || v > 2) return 0; c->texture = v; }
    else if (!strcmp(key, "DM_VIEW_DISTANCE")) { if (!(state.capabilities & DM_TUNE_CLIP) || (v && (v < 500 || v > 25000))) return 0; c->far_clip = v; }
    else if (!strcmp(key, "DM_AUTO_TEXTURE")) { if (v < 0 || v > 1) return 0; c->auto_texture = v; }
    else if (!strcmp(key, "DM_AUTO_VIEW")) { if (v < 0 || v > 1 || (v && !(state.capabilities & DM_TUNE_CLIP))) return 0; c->auto_clip = v; }
    else if (!strcmp(key, "DM_AUTO_VIEW_FLOOR")) { if (v < 500 || v > 25000) return 0; c->clip_floor = v; }
    else if (!strcmp(key, "DM_OUTPUT_HEIGHT")) { if (v && v != 720 && v != 900 && v != 1080) return 0; c->output = v; atomic_store(&output_height, v); }
    else if (!strcmp(key, "DM_PRESENT_UPSCALE")) { if (v != 0 && v != 1) return 0; c->upscale = v; atomic_store(&upscale_mode, v); }
    else return 0;
    changed = 1;
    return 1;
}
int dm_tuning_set(const char *key, double value) {
    if (!key || !isfinite(value) || !atomic_load(&initialized)) return 0;
    double v = !strcmp(key, "DM_RENDER_SCALE") ? value * 100 : value;
    if (v < 0 || v > 25000 || fabs(v - round(v)) > 0.001) return 0;
    pthread_mutex_lock(&lock); int ok = assign(key, (int)round(v));
    if (ok) cancel_measurement(); // A settings change invalidates a supposedly continuous benchmark.
    pthread_mutex_unlock(&lock);
    return ok;
}
void dm_tuning_init(void *page, unsigned caps, int width, int height) {
    pthread_mutex_lock(&lock);
    guest = page; state = (dm_tuning_snapshot){0};
    state.capabilities = page ? caps : 0; state.width = width; state.height = height;
    if (width < 1 || height < 1) { state.width = 1280; state.height = 720; state.capabilities &= ~(DM_TUNE_SCALE | DM_TUNE_FULL_SCALE); }
    state.requested = (dm_tuning_config){.target = 60, .scale = 100, .min_height = state.height * 4 / 5, .clip_floor = 2000, .output = 720};
    if (page) { float target; memcpy(&target, page, 4); if (target == 0 || target == 30 || target == 60) state.requested.target = (int)target; }
    last = window_start = last_change = samples = good_windows = bad_windows = 0;
    changed = 1; low_power = system_known = 0; measure_first = measure_last = measure_count = 0; atomic_store(&measure_active, 0);
    atomic_store(&detail, 0); atomic_store(&output_height, 720); atomic_store(&upscale_mode, 0);
    const char *keys[] = {"DM_FPS_TARGET", "DM_RENDER_SCALE", "DM_RENDER_FIXED", "DM_AUTO_MIN_HEIGHT", "DM_TEXTURE_DETAIL", "DM_VIEW_DISTANCE",
        "DM_AUTO_TEXTURE", "DM_AUTO_VIEW", "DM_AUTO_VIEW_FLOOR", "DM_OUTPUT_HEIGHT", "DM_PRESENT_UPSCALE", "DM_AUTO_QUALITY"};
    for (unsigned i = 0; i < sizeof keys / sizeof *keys; i++) {
        const char *e = getenv(keys[i]); if (!e || !*e) continue;
        if (!strcmp(keys[i], "DM_PRESENT_UPSCALE")) { assign(keys[i], !strcmp(e, "metalfx")); continue; }
        char *end; double v = strtod(e, &end);
        if (!strcmp(keys[i], "DM_RENDER_SCALE")) v *= 100;
        if (!*end && isfinite(v) && v >= 0 && v <= 25000 && fabs(v - round(v)) < 0.001) assign(keys[i], (int)round(v));
    }
    state.scale = state.requested.scale; state.texture = state.requested.texture; state.far_clip = state.requested.far_clip;
    atomic_store_explicit(&initialized, 1, memory_order_release);
    pthread_mutex_unlock(&lock);
}
int dm_tuning_active(void) { return atomic_load_explicit(&initialized, memory_order_acquire); }
int dm_tuning_texture(void) { return atomic_load_explicit(&detail, memory_order_acquire); }
int dm_tuning_output(void) { return atomic_load(&output_height); }
int dm_tuning_upscale(void) { return atomic_load(&upscale_mode); }
void dm_tuning_system(uint64_t headroom, int thermal, int low) {
    if (!dm_tuning_active()) return;
    pthread_mutex_lock(&lock); state.headroom = headroom; state.thermal = thermal; low_power = low; system_known = 1; pthread_mutex_unlock(&lock);
}
void dm_tuning_limits(int cap, int reasons, int level, int pressure) {
    if (!dm_tuning_active()) return;
    pthread_mutex_lock(&lock);
    state.effective_cap = cap; state.cap_reasons = reasons; state.memory_level = level; state.memory_pressure = pressure;
    pthread_mutex_unlock(&lock);
}
void dm_tuning_boundary(void) {
    if (!dm_tuning_active()) return;
    pthread_mutex_lock(&lock); last = window_start = last_change = 0; samples = good_windows = bad_windows = 0;
    // A benchmark interrupted by suspension is not a continuous 30-second sample.
    if (state.measuring) cancel_measurement();
    pthread_mutex_unlock(&lock);
}
void dm_tuning_tick(uint64_t now, double gpu, double frame, double compilation, int movie) {
    if (!dm_tuning_active()) return;
    pthread_mutex_lock(&lock);
    if (changed) {
        state.scale = state.requested.scale; state.texture = state.requested.texture; state.far_clip = state.requested.far_clip;
        if (state.requested.automatic && state.scale < minimum()) state.scale = minimum();
        if (state.requested.automatic && state.scale == 100 && !(state.capabilities & DM_TUNE_FULL_SCALE)) state.scale = 95;
        samples = good_windows = bad_windows = 0; window_start = last_change = now; changed = 0; apply();
    }
    state.gpu_ms = gpu; state.frame_ms = frame;
    // A memory-protection cap below the requested FPS is not a reason to
    // sacrifice quality when the GPU already fits the allowed frame budget.
    // But a 40-60 ms GPU frame still misses even a 30 FPS protective cap:
    // keep reducing GPU workload to the *attainable* capped budget, not to
    // the temporarily impossible 60 FPS target.
    int memory_limited = state.requested.automatic && state.effective_cap > 0 &&
        state.effective_cap < state.requested.target && (state.cap_reasons & 8);
    double allowed_gpu_ms = memory_limited ? 1000.0 / state.effective_cap : 0;
    if (memory_limited && (!isfinite(gpu) || gpu <= allowed_gpu_ms * .98)) {
        samples = good_windows = bad_windows = 0;
        window_start = last = now;
        state.status = DM_TUNE_MEMORY_CAP;
        goto done;
    }
    if (!state.requested.automatic) { state.status = DM_TUNE_MANUAL; last = now; goto done; }
    if (!last || now <= last || now - last > 250000000ull || movie || frame > 250 || compilation > 2) {
        samples = good_windows = bad_windows = 0; window_start = now; state.status = DM_TUNE_SETTLING; last = now; goto done;
    }
    last = now;
    if (!isfinite(gpu) || gpu <= 0 || !isfinite(frame) || frame <= 0) {
        // Unknown samples must break a sustained-overload/headroom decision;
        // combining windows from opposite sides of a gap can oscillate quality.
        samples = good_windows = bad_windows = 0; window_start = now;
        state.status = DM_TUNE_NO_GPU; goto done;
    }
    gpu_samples[samples] = gpu; frame_samples[samples++] = frame;
    if (samples < 120 && (now - window_start < 1000000000ull || samples < 20)) goto done;
    double g = percentile(gpu_samples, samples, .90), f = percentile(frame_samples, samples, .50);
    samples = 0; window_start = now;
    double budget = memory_limited ? allowed_gpu_ms : 1000.0 / state.requested.target;
    int overloaded = g > budget * .98, spare = g < budget * .75 && f <= budget * 1.12;
    bad_windows = overloaded ? bad_windows + 1 : 0;
    good_windows = spare ? good_windows + 1 : 0;
    state.status = f > budget * 1.15 && g < budget * .85 ? DM_TUNE_OTHER : DM_TUNE_GPU;
    if (bad_windows >= 2 && now - last_change >= 2000000000ull) {
        int floor = minimum();
        if (state.scale > floor) state.scale -= 5;
        else if (state.requested.auto_texture && state.texture < 2) state.texture++;
        else if (state.requested.auto_clip && (state.capabilities & DM_TUNE_CLIP)) {
            int original = state.requested.far_clip ? state.requested.far_clip : 25000;
            int limit = state.requested.clip_floor < original ? state.requested.clip_floor : original;
            int clip = state.far_clip ? state.far_clip : original;
            if (clip <= limit) { state.status = DM_TUNE_FLOOR; goto done; }
            state.far_clip = clip > 10000 ? 10000 : clip - 1000;
            if (state.far_clip < limit) state.far_clip = limit;
        } else { state.status = DM_TUNE_FLOOR; goto done; }
        // A live benchmark includes the controller's automatic quality changes;
        // only user setting changes and true scene/lifecycle boundaries cancel it.
        last_change = now; good_windows = bad_windows = 0; state.changes++; apply();
    } else if (good_windows >= 5 && now - last_change >= 5000000000ull) {
        // Restore visibility and texture quality before increasing scene resolution.
        if (state.thermal >= 2 || low_power || state.memory_level || state.memory_pressure || (system_known && state.headroom < (768ull << 20))) { state.status = DM_TUNE_THERMAL; goto done; }
        if (state.far_clip != state.requested.far_clip) {
            int original = state.requested.far_clip ? state.requested.far_clip : 25000;
            state.far_clip += 1000;
            if (state.far_clip >= original) state.far_clip = state.requested.far_clip;
        }
        else if (state.texture > state.requested.texture) state.texture--;
        else if (state.scale < ((state.capabilities & DM_TUNE_FULL_SCALE) ? 100 : 95)) state.scale += 5;
        else goto done;
        // A live benchmark includes the controller's automatic quality changes;
        // only user setting changes and true scene/lifecycle boundaries cancel it.
        last_change = now; good_windows = bad_windows = 0; state.changes++; apply();
    }
done:
    pthread_mutex_unlock(&lock);
}
void dm_tuning_measure(void) {
    pthread_mutex_lock(&lock); measure_first = measure_last = measure_count = 0;
    state.measuring = 1; state.measured_complete = 0; state.measured_frames = 0; state.measured_fps = state.measured_p95 = state.measured_seconds = 0;
    atomic_store(&measure_active, 1);
    pthread_mutex_unlock(&lock);
}
void dm_tuning_present(uint64_t timestamp) {
    if (!dm_tuning_active() || !atomic_load(&measure_active)) return;
    pthread_mutex_lock(&lock);
    if (state.measuring && timestamp > measure_last) {
        if (!measure_first) measure_first = timestamp;
        else {
            double ms = (timestamp - measure_last) / 1e6;
            if (measure_count < 4096) measure_intervals[measure_count++] = ms;
            state.measured_frames++;
            state.measured_seconds = (timestamp - measure_first) / 1e9;
            state.measured_fps = state.measured_frames / state.measured_seconds;
            if (timestamp - measure_first >= 30000000000ull) {
                state.measuring = 0; state.measured_complete = 1; state.measured_p95 = percentile(measure_intervals, measure_count, .95);
                atomic_store(&measure_active, 0);
            }
        }
        measure_last = timestamp;
    }
    pthread_mutex_unlock(&lock);
}
dm_tuning_snapshot dm_tuning_read(void) { pthread_mutex_lock(&lock); dm_tuning_snapshot s = state; pthread_mutex_unlock(&lock); return s; }
void dm_tuning_describe(char *text, size_t capacity) {
    dm_tuning_snapshot s = dm_tuning_read();
    const char *names[] = {"Manual", "Settling/loading", "GPU feedback", "CPU/streaming or other limit", "Quality floor reached", "Waiting for GPU samples", "Quality recovery paused", "Memory cap: quality held"};
    const char *limit = s.cap_reasons & 8 ? "Memory/recovery" : s.cap_reasons & 4 ? "Thermal/recovery" : s.cap_reasons & 2 ? "Movie" : s.cap_reasons & 1 ? "Selected target" : "Target active";
    const char *pressure = s.memory_pressure == 2 ? "critical" : s.memory_pressure == 1 ? "warning" : "normal";
    snprintf(text, capacity, "%s · %d%% (%d×%d nominal) · GPU %.1f ms\nFilter %d · visibility %d · %.2f GiB headroom\nTarget %d · cap %d · %s · OS pressure %s\n%s: %.1f/30 s · %d real frames · %.1f fps · p95 %.1f ms",
        names[s.status], s.scale, s.width * s.scale / 100, s.height * s.scale / 100, s.gpu_ms,
        s.texture, s.far_clip, s.headroom / 1073741824.0, s.requested.target, s.effective_cap, limit, pressure,
        s.measuring ? "Measuring" : s.measured_complete ? "Completed" : "Not measuring",
        s.measured_seconds, s.measured_frames, s.measured_fps, s.measured_p95);
}
