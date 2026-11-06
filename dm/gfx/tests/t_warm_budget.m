#include "../nvn/nvn_warm_budget.h"
#include <assert.h>
#include <stdio.h>
int main(void) { @autoreleasepool {
    assert(nvn_warm_recent(@"# only comments\n\n", 2).count == 0);
    assert(nvn_warm_recent(@"S\ta\n", 0).count == 0);
    NSArray *shorter = nvn_warm_recent(@"# comment\nS\ta\n\nC\tb\n", 4);
    assert(([shorter isEqual:@[@"S\ta", @"C\tb"]]));
    NSMutableString *large = [NSMutableString string];
    for (int i=0;i<10000;i++) [large appendFormat:@"# comment\nR\t%d\n\n",i];
    NSArray *last = nvn_warm_recent(large, 1024); assert(last.count == 1024);
    for (unsigned i=0;i<1024;i++) assert(([last[i] isEqual:[NSString stringWithFormat:@"R\t%u",8976+i]]));
    NSString *old = @"R\t5", *stalled = @"R\t17";
    NSArray *hot = nvn_warm_ranked(large, @[nvn_warm_digest(old), nvn_warm_digest(@"R\tstale"), nvn_warm_digest(stalled)], 2);
    assert(([hot isEqual:@[stalled, old]])); // Recent misses, not first-discovery order.
    NSArray *partial = nvn_warm_ranked(large, @[nvn_warm_digest(old)], 3);
    assert(([partial isEqual:@[old, @"R\t9998", @"R\t9999"]]));
    NSArray *overlap = nvn_warm_ranked(large, @[nvn_warm_digest(@"R\t9999")], 3);
    assert(([overlap isEqual:@[@"R\t9999", @"R\t9997", @"R\t9998"]]));
    assert(([nvn_warm_recent(@"#comment\r\nS\ta\r\nC\tb\n", 2) isEqual:@[@"S\ta", @"C\tb"]]));
    assert(([nvn_warm_ranked(large, @[], 1024) isEqual:last]));
    puts("Learned prewarm budget: 10k records, stale hashes, recent runtime misses, bounded fallback PASS");
} return 0; }
