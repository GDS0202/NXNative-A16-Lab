// Cache the expensive, deterministic upload conversion, not a guest texture's
// identity or address: games reuse both. Exact source and layout + encoder
// revision are SHA-256 keyed; each cached result is integrity checked too.
#import <Foundation/Foundation.h>
#include <CommonCrypto/CommonDigest.h>
#include <dispatch/dispatch.h>
#include <stdatomic.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include "bc_cache.h"
#include "bc_soft.h"

// Increment when encoding semantics change. Current packing optimization is
// byte-identical to the inherited encoder. No chain/game shader data is cached.
#define BC_CACHE_REVISION 1u
#define BC_CACHE_MAX_ENTRY (16u << 20)
#define BC_CACHE_BUDGET (256u << 20)
static NSString *root;
static dispatch_queue_t writer;
static _Atomic int busy, pressure;
static _Atomic uint64_t hits, misses, writes, rejected, saved;
typedef struct { uint8_t magic[8]; uint64_t size; uint8_t digest[32]; } cache_header;
static const uint8_t magic[8] = {'N','X','B','C','A','S','T','1'};

static void digest(const void *p, size_t n, uint8_t out[32]) {
    CC_SHA256_CTX c; CC_SHA256_Init(&c);
    while (n) { CC_LONG k = (CC_LONG)MIN(n, (size_t)UINT32_MAX); CC_SHA256_Update(&c, p, k); p = (const uint8_t *)p + k; n -= k; }
    CC_SHA256_Final(out, &c);
}
static int io_all(int fd, void *data, size_t n, int writing) {
    uint8_t *p = data;
    while (n) {
        ssize_t k = writing ? write(fd, p, n) : read(fd, p, n);
        if (k < 0 && errno == EINTR) continue;
        if (k <= 0) return 0;
        p += k; n -= (size_t)k;
    }
    return 1;
}
// Runs only on the utility writer, including startup. 256 MiB disk budget;
// temporary output has one slot, at most 16 MiB. No unbounded work queue.
static void prune(void) {
    @autoreleasepool {
        NSArray<NSURL *> *files = [NSFileManager.defaultManager contentsOfDirectoryAtURL:[NSURL fileURLWithPath:root]
            includingPropertiesForKeys:@[NSURLContentModificationDateKey, NSURLFileSizeKey, NSURLIsRegularFileKey] options:NSDirectoryEnumerationSkipsHiddenFiles error:nil];
        NSMutableArray<NSDictionary *> *entries = [NSMutableArray array]; uint64_t total = 0;
        for (NSURL *u in files) {
            if (![u.pathExtension isEqualToString:@"astc"]) continue;
            NSNumber *regular = nil, *size = nil; NSDate *date = nil;
            [u getResourceValue:&regular forKey:NSURLIsRegularFileKey error:nil]; if (!regular.boolValue) continue;
            [u getResourceValue:&size forKey:NSURLFileSizeKey error:nil]; [u getResourceValue:&date forKey:NSURLContentModificationDateKey error:nil];
            total += size.unsignedLongLongValue;
            [entries addObject:@{@"url":u, @"size":size ?: @0, @"date":date ?: NSDate.distantPast}];
        }
        if (total <= BC_CACHE_BUDGET) return;
        [entries sortUsingComparator:^NSComparisonResult(NSDictionary *a, NSDictionary *b) { return [a[@"date"] compare:b[@"date"]]; }];
        for (NSDictionary *e in entries) {
            if (total <= BC_CACHE_BUDGET) break;
            if ([NSFileManager.defaultManager removeItemAtURL:e[@"url"] error:nil]) total -= [e[@"size"] unsignedLongLongValue];
        }
    }
}
static void init_cache(void) {
    static dispatch_once_t once;
    dispatch_once(&once, ^{
        const char *env = getenv("DM_BC_CACHE"); if (env && !strcmp(env, "off")) return;
        NSString *base = [NSFileManager.defaultManager URLsForDirectory:NSCachesDirectory inDomains:NSUserDomainMask].firstObject.path;
        root = env && strcmp(env, "on") ? @(env) : [base stringByAppendingPathComponent:@"NXNative/BC-ASTC-v1"];
        if (!root.length || ![NSFileManager.defaultManager createDirectoryAtPath:root withIntermediateDirectories:YES attributes:@{NSFilePosixPermissions:@0700} error:nil]) { root = nil; return; }
        dispatch_queue_attr_t a = dispatch_queue_attr_make_with_qos_class(DISPATCH_QUEUE_SERIAL, QOS_CLASS_UTILITY, 0);
        writer = dispatch_queue_create("nxnative.bc-cache", a);
        dispatch_async(writer, ^{ prune(); });
    });
}
static NSString *cache_path(uint32_t pf, const uint8_t *src, size_t sp, uint32_t w, uint32_t h, size_t dp) {
    uint64_t layout[] = {BC_CACHE_REVISION, pf, w, h, sp, dp};
    CC_SHA256_CTX c; CC_SHA256_Init(&c); CC_SHA256_Update(&c, layout, sizeof layout);
    size_t n = sp * (h / 4 + (h % 4 != 0));
    while (n) { CC_LONG k = (CC_LONG)MIN(n, (size_t)UINT32_MAX); CC_SHA256_Update(&c, src, k); src += k; n -= k; }
    uint8_t hash[32]; CC_SHA256_Final(hash, &c); char hex[65]; const char *digits = "0123456789abcdef";
    for (int i = 0; i < 32; i++) { hex[2*i] = digits[hash[i] >> 4]; hex[2*i+1] = digits[hash[i] & 15]; } hex[64] = 0;
    return [root stringByAppendingPathComponent:[@(hex) stringByAppendingString:@".astc"]];
}
static int load(NSString *path, uint8_t *dst, size_t n) {
    int fd = open(path.fileSystemRepresentation, O_RDONLY | O_NOFOLLOW | O_CLOEXEC); if (fd < 0) return 0;
    struct stat st; cache_header hd; uint8_t hash[32];
    int ok = !fstat(fd, &st) && S_ISREG(st.st_mode) && st.st_size == (off_t)(sizeof hd + n) && io_all(fd, &hd, sizeof hd, 0)
        && !memcmp(hd.magic, magic, 8) && hd.size == n && io_all(fd, dst, n, 0);
    close(fd);
    if (ok) { digest(dst, n, hash); ok = !memcmp(hash, hd.digest, 32); }
    if (!ok) { atomic_fetch_add(&rejected, 1); return 0; }
    atomic_fetch_add(&hits, 1); atomic_fetch_add(&saved, n); return 1;
}
static void store(NSString *path, const uint8_t *dst, size_t n) {
    if (atomic_load(&pressure)) return;
    int expected = 0; if (!atomic_compare_exchange_strong(&busy, &expected, 1)) return;
    uint8_t *copy = malloc(n); if (!copy) { atomic_store(&busy, 0); return; }
    memcpy(copy, dst, n);
    dispatch_async(writer, ^{ @autoreleasepool {
        if (!atomic_load(&pressure)) {
            cache_header hd; memcpy(hd.magic, magic, 8); hd.size = n; digest(copy, n, hd.digest);
            NSString *tmp = [path stringByAppendingFormat:@".%@.pending", NSUUID.UUID.UUIDString];
            int fd = open(tmp.fileSystemRepresentation, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
            if (fd >= 0) {
                int ok = io_all(fd, &hd, sizeof hd, 1) && io_all(fd, copy, n, 1); if (close(fd)) ok = 0;
                if (ok && !rename(tmp.fileSystemRepresentation, path.fileSystemRepresentation)) atomic_fetch_add(&writes, 1);
                else unlink(tmp.fileSystemRepresentation);
            }
            prune();
        }
        free(copy); atomic_store(&busy, 0);
    }});
}
int nvn_bc_decode(uint32_t pf, const uint8_t *src, size_t sp, uint32_t w, uint32_t h, uint8_t *dst, size_t dp) {
    uint32_t target = bc_soft_target(pf, NULL);
    // ASTC only; tiny levels are cheaper to encode than to open a file. Limit
    // both source and output before hashing. This wrapper never widens the
    // decoder's valid input contract or reads padding after the last block row.
    uint64_t bw = ((uint64_t)w + 3) / 4, bh = ((uint64_t)h + 3) / 4;
    uint64_t bsz = pf == 130 || pf == 131 ? 8 : 16;
    uint64_t n = (uint64_t)dp * bh;
    if ((target != 186 && target != 204) || !src || !dst || !w || !h || sp != bw * bsz || dp != bw * 16
        || n < (64u << 10) || n > BC_CACHE_MAX_ENTRY || sp > BC_CACHE_MAX_ENTRY / bh)
        return bc_soft_decode(pf, src, sp, w, h, dst, dp);
    init_cache(); if (!root) return bc_soft_decode(pf, src, sp, w, h, dst, dp);
    @autoreleasepool {
        NSString *path = cache_path(pf, src, sp, w, h, dp);
        if (load(path, dst, (size_t)n)) return 0;
        atomic_fetch_add(&misses, 1);
        int rc = bc_soft_decode(pf, src, sp, w, h, dst, dp);
        if (!rc) store(path, dst, (size_t)n);
        return rc;
    }
}
nvn_bc_cache_info nvn_bc_cache_stats(void) { return (nvn_bc_cache_info){atomic_load(&hits), atomic_load(&misses), atomic_load(&writes), atomic_load(&rejected), atomic_load(&saved)}; }
void nvn_bc_cache_pressure(int level) { atomic_store(&pressure, level); }
void nvn_bc_cache_wait(void) { init_cache(); if (writer) dispatch_sync(writer, ^{}); }
