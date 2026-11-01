#pragma once
#import <Foundation/Foundation.h>
// Keep only the newest discovered records, in their original order. Storage
// stays bounded even when pso_user.tsv has grown through many play sessions.
static inline NSArray<NSString *> *nvn_warm_recent(NSString *text, NSUInteger limit) {
    if (!limit) return @[];
    NSMutableArray<NSString *> *ring = [NSMutableArray arrayWithCapacity:limit];
    __block NSUInteger seen = 0;
    [text enumerateLinesUsingBlock:^(NSString *line, BOOL *stop) {
        (void)stop; if (!line.length || [line hasPrefix:@"#"]) return;
        if (ring.count < limit) [ring addObject:line]; else ring[seen % limit] = line;
        seen++;
    }];
    if (seen <= limit) return ring;
    NSMutableArray<NSString *> *ordered = [NSMutableArray arrayWithCapacity:limit];
    for (NSUInteger i = 0; i < limit; i++) [ordered addObject:ring[(seen + i) % limit]];
    return ordered;
}
