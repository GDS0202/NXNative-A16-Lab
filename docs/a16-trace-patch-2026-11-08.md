# A16 BOTW — storage-write and memory iteration (8 Nov 2026)

## Device evidence
From the 2026-11-08 TRACE run on an A16 iPad (iPadOS 27.2, BOTW 1.9):
- 4,596 unknown-size notes among 2,095,149 bound storage notes in 160 logged windows. **Bindless unknown = 0**. Per-window shrine peak: 900 storage unknown notes, ~72,300 conservative shadow refusals, ~49–63 ms GPU time. These are correlated observations, not a proven FPS gain.
- Resident memory climbed to 3,281 MiB, memory pressure forced a protective 30-fps cap near the end. Source case at the scene transition grew from 2,122 to 2,752 MiB as guest memory pools increased from 907 to 3,084. No permission to discard live guest storage or remove the memory guard.
- Separately, a ~400 ms hitch contained ~312 ms of upload CPU time; PSO compilation was not the main bottleneck.

## Changes in this iteration (draft PR #5)
1. **Experiment DM_NVN_SBW_SCOPED=1**: a zero-length writable **storage** binding conservatively marks its *entire backing MTLBuffer*, not the entire GPU address space and never an invented byte extent. Its range is checked against uniform-shadow reads within the submission and against prior in-flight submissions until GPU fences complete. Bounded sets and a global fallback handle exhaustion. Sparse/VM-remapped pools and unknown/invalid allocation bounds always use the old global fail-closed behavior. Default OFF pending visual on-device validation. DM_NVN_SBW_SCOPED=0 restores old behavior; DM_NVN_SBW_FINE=1 preserves 16-byte tracking for known-size writes.
2. **Trace hot slots**: with DM_NVN_SBW_TRACE=1, the log prints the top stage/register pairs with zero-sized writable storage bindings and scoped hit/fallback totals. No guest addresses, shader content or per-draw dumps are logged.
3. **Alias takeover cleanup**: drain all eligible overlapping stale GPU-texture aliases in 16-key batches. Before, a single takeover only checked the first 16, leaving potentially eligible stale entries. Each eviction still obeys the existing serial, ghost, and last-use safety checks.
4. **CPU-only constant/handle lookup without GPU residency**: a separate generation-validated CPU pool cache copies a few guest bytes without registering that backing pool with the Metal residency set. *Actual GPU bindings* keep the original mtl_addr/mtl_gpu_addr registration. DM_NVN_CPU_READ_NORES=0 restores the old path; default ON.
5. **Early optional cache-write backpressure**: with process headroom below 1 GiB, suppress new BC→ASTC *disk cache writes* and their temporary copies, without blocking decoding or clearing valid disk entries. The existing iOS critical memory guard and 30-fps safety limit remain intact.
6. New portable C differential/property test for ranges, fences, overflows and bounded capacity; the portable A16 validation workflow runs it under AddressSanitizer and UndefinedBehaviorSanitizer.

## Required CI and device gates
- First require GitHub Actions **A16 validation / tests** green, particularly iOS-source compile and portable sanitizer checks. CI is not a real iPad gameplay performance test.
- Next Codemagic build should pin the exact **new tested commit**; do not build from the previously pinned c993cfd source by mistake.
- For an A/B test, use the SAME IPA and scene, save, aspect/scale, cache warm state, iPadOS and temperature. First run `DM_NVN_SBW_SCOPED=0`, `DM_NVN_CPU_READ_NORES=0`, `DM_NVN_SBW_TRACE=0`; then scoped-only; then CPU-residency-only; finally both. Restart the app between runs.
- Collect actual display intervals (average, 1% low, 0.1% low), GPU p50/p95, partial-shadow refusals, pass load/store MiB, headroom, Metal allocated bytes, live/unreferenced aliases, render correctness, screenshots and crashes. Repeat outdoor, shrine and >30-minute traversal. Treat any black/purple textures, invalid memory access, missing draws or screen corruption as failure and return to the prior configuration.
- If a scene stays slow despite fewer refusals, the bottleneck may be legitimate fragment/attachment bandwidth or shader cost. Reassess instead of disabling more barriers.
- Do not delete `save`, `romfs.img`, private keys or licensed assets. Keep all private build inputs on private CI.

## Next high-impact work not yet implemented
1. Characterize actual stage/register zero-size RW bindings; when supported, use shader-derived access bounds to reduce whole-backing conservative masks even further.
2. Precise per-category memory ownership accounting, plus GPU-fence-safe eviction of proven rebuildable resources; never indiscriminately drop GPU-written render targets.
3. Bounded asynchronous BC texture preparation and disk-cache read budget. Existing ~312 ms synchronous upload peaks remain unresolved.
4. Correct compressed-format render-target attachment and image view compatibility, currently logged as lost draw calls.
5. A/B dynamic resolution with actual internal dimensions and strict no-below-720p when that user constraint is enabled.
