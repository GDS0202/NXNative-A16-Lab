// Opt-in player builds ignore saved diagnostic overrides while retaining the
// FPS/HUD, controller, language and normal launcher settings. The game profile
// and bundle still supply the renderer's required paths and compatibility keys.
#pragma once
#include <string.h>
static inline int dm_player_diagnostic_key(const char *key) {
    // Encoding placement changes scheduling, not diagnostics or launcher state.
    if(!strcmp(key,"DM_NVN_ENC_THREAD"))return 0;
    // The A16 hazard A/B must be effective in player builds: 0 restores the
    // older, more conservative page-granular uniform-write check. Keeping
    // this single comparison switch does not permit unrelated diagnostics.
    if(!strcmp(key,"DM_NVN_SBW_FINE"))return 0;
    // Opt-in, counters-only source attribution. No pass dumps, guest addresses
    // or changed synchronization; disabled by default to avoid atomic overhead.
    if(!strcmp(key,"DM_NVN_SBW_TRACE"))return 0;
    // Experimental allocation-bounded hazard tracker; 0 restores global fail-closed.
    if(!strcmp(key,"DM_NVN_SBW_SCOPED"))return 0;
    // A/B: 0 preserves the original GPU-resident CPU read path.
    if(!strcmp(key,"DM_NVN_CPU_READ_NORES"))return 0;
    static const char *const prefixes[]={"DM_NVN_","DM_TEST_","MTL_DEBUG_","MTL_SHADER_VALIDATION"};
    for(unsigned i=0;i<sizeof prefixes/sizeof *prefixes;i++)
        if(!strncmp(key,prefixes[i],strlen(prefixes[i])))return 1;
    static const char *const names[]={"DM_CTL","DM_KEYS","DM_KBD","DM_DETCLOCK","DM_SLOWFRAME","DM_PROBE","DM_MSL_DIR"};
    for(unsigned i=0;i<sizeof names/sizeof *names;i++)if(!strcmp(key,names[i]))return 1;
    return 0;
}
