#pragma once
#include <math.h>

// Anisotropy is a sampling-cost control, not a memory-quality control. Preserve
// the game's LOD range: explicit-level light/probe/data reads obey Metal's LOD
// clamps too. Never force them to a coarser mip as a global "texture detail".
static inline unsigned nvn_sampler_anisotropy(float requested, int quality, int minf, int magf,
                                               int compare, int reduction, float lod_min, float lod_max, float bias) {
    unsigned original = !isfinite(requested) || requested < 1 ? 1 : requested > 16 ? 16 : (unsigned)requested;
    int eligible = !compare && !reduction && minf == 5 && magf == 1 && lod_min == 0 && lod_max > 1 && bias == 0;
    if (!eligible || quality < 1 || quality > 2 || original <= 2) return original;
    return quality == 1 ? 2 : 1;
}
