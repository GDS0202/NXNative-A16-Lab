#pragma once
#import <Foundation/Foundation.h>
#include <CommonCrypto/CommonDigest.h>
#include <stdio.h>
// Avoid an array of every record and drain transient strings/hashes while
// scanning. The caller retains only selected lines; the source text still lives
// for the scan, as it did before ranking was introduced.
static inline void nvn_warm_lines(NSString *text, void (^consume)(NSString *)) {
    for (NSUInteger at = 0, end = 0; at < text.length; at = end) { @autoreleasepool {
        NSUInteger contents = 0;
        [text getLineStart:NULL end:&end contentsEnd:&contents forRange:NSMakeRange(at, 0)];
        NSString *line = [text substringWithRange:NSMakeRange(at, contents - at)];
        if (line.length && ![line hasPrefix:@"#"]) consume(line);
    } }
}
// Keep only the newest discovered records, in their original order. Storage
// stays bounded even when pso_user.tsv has grown through many play sessions.
static inline NSArray<NSString *> *nvn_warm_recent(NSString *text, NSUInteger limit) {
    if (!limit) return @[];
    NSMutableArray<NSString *> *ring = [NSMutableArray arrayWithCapacity:limit];
    __block NSUInteger seen = 0;
    nvn_warm_lines(text, ^(NSString *line) {
        if (ring.count < limit) [ring addObject:line]; else ring[seen % limit] = line;
        seen++;
    });
    if (seen <= limit) return ring;
    NSMutableArray<NSString *> *ordered = [NSMutableArray arrayWithCapacity:limit];
    for (NSUInteger i = 0; i < limit; i++) [ordered addObject:ring[(seen + i) % limit]];
    return ordered;
}
static inline NSString *nvn_warm_digest(NSString *line) {
    NSData *data = [line dataUsingEncoding:NSUTF8StringEncoding];
    if (data.length > UINT32_MAX) return @"";
    uint8_t hash[CC_SHA256_DIGEST_LENGTH]; CC_SHA256(data.bytes, (CC_LONG)data.length, hash);
    char hex[65]; for (unsigned i = 0; i < 32; i++) snprintf(hex + i * 2, 3, "%02x", hash[i]);
    return @(hex);
}
// Recency here means an actual on-demand miss in a recent play session, not
// merely the first time a pipeline was discovered years ago. The sidecar holds
// only hashes; every selected line must still exist in the original user list
// and pass the normal shader/build/descriptor validation in warm_parse.
static inline NSArray<NSString *> *nvn_warm_ranked(NSString *text, NSArray<NSString *> *recent, NSUInteger limit) {
    if (!limit) return @[];
    if (!recent.count) return nvn_warm_recent(text, limit);
    if (recent.count > 4096) recent = [recent subarrayWithRange:NSMakeRange(recent.count - 4096, 4096)];
    NSSet<NSString *> *wanted = [NSSet setWithArray:recent];
    NSMutableDictionary<NSString *, NSString *> *by_hash = [NSMutableDictionary dictionary];
    nvn_warm_lines(text, ^(NSString *line) {
        NSString *hash = nvn_warm_digest(line);
        if ([wanted containsObject:hash]) by_hash[hash] = line;
    });
    NSMutableOrderedSet<NSString *> *selected = [NSMutableOrderedSet orderedSet];
    for (NSString *hash in recent.reverseObjectEnumerator) {
        NSString *line = by_hash[hash]; if (line) [selected addObject:line];
        if (selected.count == limit) break;
    }
    if (selected.count < limit) {
        NSMutableArray<NSString *> *fill = [NSMutableArray array];
        for (NSString *line in nvn_warm_recent(text, limit).reverseObjectEnumerator) {
            if (![selected containsObject:line]) [fill addObject:line];
            if (selected.count + fill.count == limit) break;
        }
        // Keep discovery order inside the newest fallback subset, rather than
        // discarding its newest entries whenever hot records consume the budget.
        for (NSString *line in fill.reverseObjectEnumerator) [selected addObject:line];
    }
    return selected.array;
}
