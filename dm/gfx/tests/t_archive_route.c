#include "../nvn/nvn_archive_route.h"
#include <assert.h>
#include <stdio.h>
int main(void) {
    // The submitted session had 177 run files. Every valid/stale hint must
    // preserve complete fallback coverage without duplicate Metal lookups.
    for (uint32_t n = 1; n <= 177; n++) for (uint32_t hint = 0; hint <= n; hint++) {
        unsigned char seen[177] = {0};
        for (uint32_t i = 0; i < n; i++) {
            uint32_t at = nvn_archive_probe(i, n, hint);
            assert(at < n && !seen[at]); seen[at] = 1;
        }
        if (hint < n) assert(nvn_archive_probe(0, n, hint) == hint);
    }
    puts("Archive routing: every hint and full fallback across 1..177 archives PASS");
    return 0;
}
