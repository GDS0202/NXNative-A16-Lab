#include "nvn_stutter.h"
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <math.h>
#include <pthread.h>
#include <sched.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>
#ifdef __APPLE__
#include <pthread/qos.h>
#endif
#ifndef NVN_STUTTER_LIMIT
#define NVN_STUTTER_LIMIT (32u << 20)
#endif
#define JOURNAL_LIMIT (512u << 10)
#define CAPACITY 4096
typedef struct {
    enum { FRAME, PRESENT, SYSTEM, BOUNDARY, MEMORY, POLICY } kind;
    nvn_stutter_sample frame;
    uint64_t ticket, footprint, headroom;
    int thermal, low_power;
    int level, pressure, reason, target, cap, scale, texture, clip;
} event;
typedef struct { _Atomic uint64_t sequence; event value; } cell;
static cell *queue;
static pthread_once_t once = PTHREAD_ONCE_INIT;
static pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t condition = PTHREAD_COND_INITIALIZER;
static pthread_t thread;
static _Atomic int mode = -1;
static _Atomic uint64_t lost;
static uint64_t read_at;
static _Atomic uint64_t write_at;
static _Atomic unsigned producers;
static _Atomic int stopping;
static int started;
static FILE *output;
static FILE *journal;
static unsigned segment;
static _Atomic uint64_t session;
static void header(FILE *file, unsigned index, int events) {
    fprintf(file, "{\"kind\":\"header\",\"schema\":2,\"generated_fps\":0,\"session\":%" PRIu64 ",\"segment\":%u,\"events_only\":%s,\"limit_bytes\":%u,\"queue_capacity\":%u,\"identity_source\":\"capabilities.json\"}\n",
            session, index, events ? "true" : "false", events ? JOURNAL_LIMIT : NVN_STUTTER_LIMIT, CAPACITY);
}
static FILE *open_file(const char *path) {
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC | O_NOFOLLOW | O_CLOEXEC, 0600);
    FILE *file = fd >= 0 ? fdopen(fd, "w") : NULL;
    if (!file && fd >= 0) close(fd);
    return file;
}
static double number(double n) { return isfinite(n) && n >= -1 && n <= 3600000 ? n : -1; }
static void write_event(FILE *output, const event *e) {
    const nvn_stutter_sample *s = &e->frame;
    if (e->kind == FRAME) {
        fprintf(output, "{\"kind\":\"frame\",\"frame\":%" PRIu64 ",\"timestamp_ns\":%" PRIu64, s->frame, s->timestamp_ns);
#define WRITE_METRIC(name) fprintf(output, ",\"" #name "\":%.6f", number(s->name));
        NVN_STUTTER_METRICS(WRITE_METRIC)
#undef WRITE_METRIC
        fprintf(output, ",\"upload_bytes\":%" PRIu64 ",\"cache_hits\":%" PRIu64 ",\"cache_misses\":%" PRIu64
                ",\"pso_new\":%" PRIu64 ",\"library_new\":%" PRIu64 ",\"bc_calls\":%" PRIu64 "}\n",
                s->upload_bytes, s->cache_hits, s->cache_misses, s->pso_new, s->library_new, s->bc_calls);
    } else if (e->kind == PRESENT) {
        fprintf(output, "{\"kind\":\"present\",\"frame\":%" PRIu64 ",\"ticket\":%" PRIu64 ",\"timestamp_ns\":%" PRIu64 "}\n",
                s->frame, e->ticket, s->timestamp_ns);
    } else if (e->kind == SYSTEM) {
        fprintf(output, "{\"kind\":\"system\",\"timestamp_ns\":%" PRIu64 ",\"footprint_bytes\":%" PRIu64
                ",\"headroom_bytes\":%" PRIu64 ",\"thermal\":%d,\"low_power\":%d}\n",
                s->timestamp_ns, e->footprint, e->headroom, e->thermal, e->low_power);
    } else if (e->kind == MEMORY) {
        fprintf(output, "{\"kind\":\"memory\",\"timestamp_ns\":%" PRIu64 ",\"headroom_bytes\":%" PRIu64 ",\"level\":%d,\"os_pressure\":%d,\"reason\":%d,\"malloc_returned_bytes\":%" PRIu64 "}\n",
                s->timestamp_ns, e->headroom, e->level, e->pressure, e->reason, e->footprint);
    } else if (e->kind == POLICY) {
        fprintf(output, "{\"kind\":\"policy\",\"timestamp_ns\":%" PRIu64 ",\"requested_fps\":%d,\"effective_cap\":%d,\"cap_reasons\":%d,\"scale_percent\":%d,\"texture_filter\":%d,\"far_clip\":%d}\n",
                s->timestamp_ns, e->target, e->cap, e->reason, e->scale, e->texture, e->clip);
    } else fprintf(output, "{\"kind\":\"boundary\",\"timestamp_ns\":%" PRIu64 "}\n", s->timestamp_ns);
}
static void *writer(void *unused) {
    (void)unused;
#ifdef __APPLE__
    pthread_set_qos_class_self_np(QOS_CLASS_UTILITY, 0);
#endif
    // Rotation belongs to the utility writer, never a producer. Retain a
    // bounded recent window instead of disabling diagnostics mid-session.
    for (;;) {
        event batch[32]; unsigned n = 0;
        while (n < 32) {
            cell *slot = &queue[read_at % CAPACITY];
            if (atomic_load_explicit(&slot->sequence, memory_order_acquire) != read_at + 1) break;
            batch[n++] = slot->value;
            atomic_store_explicit(&slot->sequence, read_at + CAPACITY, memory_order_release); read_at++;
        }
        int done = atomic_load(&stopping) && !atomic_load(&producers) && read_at == atomic_load(&write_at);
        if (!n && !done) {
            struct timespec deadline; clock_gettime(CLOCK_REALTIME, &deadline); deadline.tv_sec++;
            pthread_mutex_lock(&mutex); pthread_cond_timedwait(&condition, &mutex, &deadline); pthread_mutex_unlock(&mutex);
            continue;
        }
        for (unsigned i = 0; i < n; i++) {
            long at = ftell(output);
            if (at < 0) { atomic_store(&mode, 0); goto finish; }
            if ((uint64_t)at + 2048 >= NVN_STUTTER_LIMIT) {
                fprintf(output, "{\"kind\":\"status\",\"capped\":false,\"rotated\":true,\"lost\":%" PRIu64 "}\n", atomic_load(&lost));
                int bad = fclose(output); output = NULL;
                if (bad || rename("stutter.jsonl", "stutter.1.jsonl") || !(output = open_file("stutter.jsonl"))) { atomic_store(&mode, 0); goto finish; }
                header(output, ++segment, 0);
            }
            write_event(output, &batch[i]);
            if (journal && (batch[i].kind == MEMORY || batch[i].kind == POLICY || batch[i].kind == BOUNDARY)) {
                long pos = ftell(journal);
                if (pos < 0 || (uint64_t)pos + 2048 >= JOURNAL_LIMIT) {
                    fclose(journal); journal = NULL;
                    if (!rename("performance-events.jsonl", "performance-events.1.jsonl")) journal = open_file("performance-events.jsonl");
                    if (journal) header(journal, segment, 1);
                }
                if (journal) { write_event(journal, &batch[i]); if (fflush(journal)) { fclose(journal); journal = NULL; } }
            }
        }
        fprintf(output, "{\"kind\":\"status\",\"capped\":false,\"lost\":%" PRIu64 "}\n", atomic_load(&lost));
        if (fflush(output) || ferror(output)) { atomic_store(&mode, 0); break; }
        if (done) break;
    }
finish:
    if (output) fclose(output);
    output = NULL;
    if (journal) fclose(journal);
    journal = NULL;
    return NULL;
}
static void initialize(void) {
    const char *v = getenv("DM_STUTTER");
    if (!v || v[0] != '1' || v[1]) { atomic_store(&mode, 0); return; }
    queue = calloc(CAPACITY, sizeof *queue);
    if (!queue) { atomic_store(&mode, 0); return; }
    for (unsigned i = 0; i < CAPACITY; i++) atomic_init(&queue[i].sequence, i);
    struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); session = (uint64_t)ts.tv_sec * 1000000000ull + ts.tv_nsec;
    unlink("stutter.prev.1.jsonl"); rename("stutter.1.jsonl", "stutter.prev.1.jsonl");
    rename("stutter.jsonl", "stutter.prev.jsonl");
    unlink("performance-events.prev.1.jsonl"); rename("performance-events.1.jsonl", "performance-events.prev.1.jsonl");
    rename("performance-events.jsonl", "performance-events.prev.jsonl");
    output = open_file("stutter.jsonl");
    if (!output) { free(queue); queue = NULL; atomic_store(&mode, 0); return; }
    header(output, 0, 0);
    journal = open_file("performance-events.jsonl"); if (journal) header(journal, 0, 1);
    if (pthread_create(&thread, NULL, writer, NULL)) {
        if (journal) fclose(journal);
        journal = NULL;
        fclose(output); output = NULL; free(queue); queue = NULL; atomic_store(&mode, 0); return;
    }
    started = 1; atomic_store(&mode, 1); atexit(nvn_stutter_stop);
}
int nvn_stutter_start(void) { pthread_once(&once, initialize); return nvn_stutter_enabled(); }
int nvn_stutter_enabled(void) { return atomic_load(&mode) > 0; }

static void push(const event *e) {
    atomic_fetch_add(&producers, 1);
    if (!nvn_stutter_enabled()) { atomic_fetch_sub(&producers, 1); return; }
    // Bounded MPSC sequence queue: a preempted writer cannot lock a renderer.
    // A producer publishes only after its copy; the consumer releases a slot
    // only after reading it. Full queues/contention are counted explicitly.
    uint64_t pos = atomic_load(&write_at); int published = 0;
    for (unsigned retry = 0; retry < 8; retry++) {
        cell *slot = &queue[pos % CAPACITY];
        uint64_t seq = atomic_load_explicit(&slot->sequence, memory_order_acquire);
        if (seq == pos) {
            if (atomic_compare_exchange_weak(&write_at, &pos, pos + 1)) {
                slot->value = *e; atomic_store_explicit(&slot->sequence, pos + 1, memory_order_release);
                if (pos % 64 == 63) pthread_cond_signal(&condition);
                published = 1; break;
            }
            continue;
        }
        if (seq < pos) break;
        pos = atomic_load(&write_at);
    }
    if (!published) atomic_fetch_add(&lost, 1);
    atomic_fetch_sub(&producers, 1);
}

void nvn_stutter_frame(const nvn_stutter_sample *s) { if (!s || !s->timestamp_ns || !nvn_stutter_enabled()) return; event e = {.kind = FRAME, .frame = *s}; push(&e); }
void nvn_stutter_present(uint64_t frame, uint64_t ticket, uint64_t ns) { if (!ns || !nvn_stutter_enabled()) return; event e = {.kind = PRESENT, .frame = {.frame = frame, .timestamp_ns = ns}, .ticket = ticket}; push(&e); }
void nvn_stutter_system(uint64_t ns, uint64_t footprint, uint64_t headroom, int thermal, int low_power) {
    if (!ns || !nvn_stutter_enabled()) return;
    event e = {.kind = SYSTEM, .frame = {.timestamp_ns = ns}, .footprint = footprint, .headroom = headroom, .thermal = thermal, .low_power = low_power}; push(&e);
}
void nvn_stutter_boundary(uint64_t ns) { if (!ns) return; event e = {.kind = BOUNDARY, .frame = {.timestamp_ns = ns}}; push(&e); }
void nvn_stutter_memory(uint64_t ns, uint64_t left, int level, int pressure, int reason, uint64_t returned) {
    if (!ns || !nvn_stutter_enabled()) return;
    event e = {.kind = MEMORY, .frame = {.timestamp_ns = ns}, .headroom = left, .level = level, .pressure = pressure, .reason = reason, .footprint = returned}; push(&e);
}
void nvn_stutter_policy(uint64_t ns, int target, int cap, int reasons, int scale, int texture, int clip) {
    if (!ns || !nvn_stutter_enabled()) return;
    event e = {.kind = POLICY, .frame = {.timestamp_ns = ns}, .target = target, .cap = cap, .reason = reasons, .scale = scale, .texture = texture, .clip = clip}; push(&e);
}
uint64_t nvn_stutter_session(void) { return session; } // initialized before the trace's producers start
uint64_t nvn_stutter_lost(void) { return atomic_load(&lost); }
void nvn_stutter_stop(void) {
    if (!started) return;
    atomic_store(&mode, 0);
    atomic_store(&stopping, 1); pthread_cond_signal(&condition);
    pthread_join(thread, NULL);
    while (atomic_load(&producers)) sched_yield();  // exit only; a capped writer may have exited before a producer
    started = 0; free(queue); queue = NULL;
}
