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
    puts("Learned prewarm budget: comments, empty, short, 10k records, bounded order PASS");
} return 0; }
