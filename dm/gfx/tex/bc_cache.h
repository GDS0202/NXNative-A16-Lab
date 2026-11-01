#pragma once
#include <stddef.h>
#include <stdint.h>

// Content-addressed BC -> ASTC cache. A miss always takes the normal decoder.
// Only cache data (never guest memory) can be evicted. Set DM_BC_CACHE=off to
// compare, or a directory for an isolated cache. The default is Library/Caches.
int nvn_bc_decode(uint32_t pf, const uint8_t *src, size_t src_pitch,
                  uint32_t w, uint32_t h, uint8_t *dst, size_t dst_pitch);
typedef struct { uint64_t hits, misses, writes, rejected, saved_bytes; } nvn_bc_cache_info;
nvn_bc_cache_info nvn_bc_cache_stats(void);
void nvn_bc_cache_pressure(int level);   // no asynchronous writes under memory pressure
void nvn_bc_cache_wait(void);           // tools/tests only; never called on a frame
