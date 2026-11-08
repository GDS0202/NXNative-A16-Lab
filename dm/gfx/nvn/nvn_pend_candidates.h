#pragma once
#include <stdlib.h>

// A pending-buffer write may occur in several 4-KiB-page chains. Collect all
// matching indices into a bounded buffer BEFORE deduplication; a pathological
// collision/overlap must return "unknown" instead of corrupting memory.
static inline int nvn_pend_candidate_add(int *out, int count, int capacity, int entry) {
    if (count < 0 || count >= capacity) return -1;
    out[count] = entry;
    return count + 1;
}
static int nvn_pend_candidate_compare_desc(const void *aa, const void *bb) {
    int a = *(const int *)aa, b = *(const int *)bb;
    return (b > a) - (b < a);
}
static inline int nvn_pend_candidates_finish(int *out, int count, int needs_sort) {
    if (!needs_sort || count < 2) return count;
    // Insertion sort was quadratic when several thousand writes shared pages.
    // Keep its tiny-list locality, but use O(n log n) sorting for larger runs.
    if (count > 32) qsort(out, (size_t)count, sizeof *out, nvn_pend_candidate_compare_desc);
    else for (int i = 1; i < count; i++) {
        int v = out[i], j = i;
        while (j > 0 && out[j - 1] < v) { out[j] = out[j - 1]; j--; }
        out[j] = v;
    }
    int unique = 1;
    for (int i = 1; i < count; i++)
        if (out[i] != out[unique - 1]) out[unique++] = out[i];
    return unique;
}
