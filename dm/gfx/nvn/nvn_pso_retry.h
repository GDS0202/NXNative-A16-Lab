#pragma once
#include <stdint.h>
// One possible retry after a pipeline failure during OS/guard pressure.
// Permanent failures and failures during healthy memory have no retry.
static inline uint64_t nvn_pso_retry_deadline(uint64_t now, int pressure) {
    if (!pressure) return 0;
    return now > UINT64_MAX - 5000000000ull ? UINT64_MAX : now + 5000000000ull;
}
static inline int nvn_pso_retry_due(uint64_t now, uint64_t deadline, int pressure) {
    return deadline && !pressure && now >= deadline;
}
