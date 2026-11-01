#import <Foundation/Foundation.h>
#include <assert.h>
#include <stdio.h>
#include <unistd.h>
#include "../bc_soft.h"
#include "../bc_cache.h"
int main(void) { @autoreleasepool {
    NSString *dir = [NSTemporaryDirectory() stringByAppendingPathComponent:NSUUID.UUID.UUIDString];
    setenv("DM_BC_CACHE", dir.fileSystemRepresentation, 1);
    size_t n = 512 * 512; uint8_t *src = malloc(n), *out = malloc(n), *ref = malloc(n);
    assert(src && out && ref); uint32_t rng = 918;
    for (size_t i = 0; i < n; i++) { rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5; src[i] = (uint8_t)rng; }
    assert(!bc_soft_decode(134, src, 2048, 512, 512, ref, 2048));
    assert(!nvn_bc_decode(134, src, 2048, 512, 512, out, 2048)); assert(!memcmp(out, ref, n));
    memset(out, 0, n); nvn_bc_cache_wait();
    nvn_bc_cache_info a = nvn_bc_cache_stats(); assert(a.misses == 1 && a.writes == 1);
    assert(!nvn_bc_decode(134, src, 2048, 512, 512, out, 2048)); assert(!memcmp(out, ref, n));
    a = nvn_bc_cache_stats(); assert(a.hits == 1 && a.saved_bytes == n);
    NSArray *files = [NSFileManager.defaultManager contentsOfDirectoryAtPath:dir error:nil]; assert(files.count == 1);
    NSString *path = [dir stringByAppendingPathComponent:files[0]];
    NSMutableData *bad = [NSMutableData dataWithContentsOfFile:path]; ((uint8_t *)bad.mutableBytes)[bad.length - 1] ^= 0x80;
    assert([bad writeToFile:path atomically:YES]);
    assert(!nvn_bc_decode(134, src, 2048, 512, 512, out, 2048)); assert(!memcmp(out, ref, n));
    nvn_bc_cache_wait(); assert(nvn_bc_cache_stats().rejected == 1);
    // A truncated entry also falls back; no partial cached result is accepted.
    assert(truncate(path.fileSystemRepresentation, 20) == 0);
    assert(!nvn_bc_decode(134, src, 2048, 512, 512, out, 2048)); assert(!memcmp(out, ref, n));
    nvn_bc_cache_wait(); assert(nvn_bc_cache_stats().rejected == 2);
    // Different source bytes and sRGB are different keys. A queued write owns
    // a copy even when the caller immediately reuses its staging memory.
    src[71] ^= 3; assert(!bc_soft_decode(134, src, 2048, 512, 512, ref, 2048));
    assert(!nvn_bc_decode(134, src, 2048, 512, 512, out, 2048)); memset(out, 0, n); nvn_bc_cache_wait();
    assert(!nvn_bc_decode(134, src, 2048, 512, 512, out, 2048)); assert(!memcmp(out, ref, n));
    nvn_bc_cache_pressure(2); uint64_t before = nvn_bc_cache_stats().writes;
    assert(!nvn_bc_decode(135, src, 2048, 512, 512, out, 2048)); nvn_bc_cache_wait();
    assert(nvn_bc_cache_stats().writes == before); nvn_bc_cache_pressure(0);
    free(src); free(out); free(ref); [NSFileManager.defaultManager removeItemAtPath:dir error:nil];
    puts("BC cache: cold/warm, content keys, corruption, truncation, owned writes, pressure PASS");
} return 0; }
