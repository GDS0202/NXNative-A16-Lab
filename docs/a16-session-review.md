# A16 runtime follow-up: source candidate and acceptance

This is the follow-up to the installed Switch BOTW 1.9.0 IPA. The complete
[device baseline](../dm/games/01007EF00011E000/README.md#a16-diagnostic-baseline-2026-11-06)
records provenance, measurements and limitations once. New source work lives on
`feature/a16-stutter-recovery`, above `feature/adaptive-graphics-controller`.
It preserves the verified guest stubs and their build gates; it does not claim
new device results. The CPU build target and shader translation chain are unchanged.

## Goal and decisions

Target 60 **real** frames per second, fixed 1920x1080 display output, handheld
scene base 1280x720 and automatic internal scale from 100% down to a configurable
80% floor (1024x576). Spatial upscaling presents the requested output; it does
not make the scene detail equivalent to native 1080p. Saves, timing, movie/VFR
steps, memory and thermal protection retain priority over displaying a target
number. No generated or repeated frame is counted as a rendered real frame.

| Workstream | Implemented source change | Evidence still needed |
|---|---|---|
| Memory cap | Separate OS state and process headroom; subscribe to NORMAL; recover with hysteresis; treat zero bytes as critical | Actual NORMAL delivery, safe recovery and later-session pressure on iPad |
| Reclamation | Retire only completed cold upload/frame scratch; pause optional prewarm/cache writes | Measured footprint/headroom change and absence of churn |
| Pipeline hitches | Bundle/cache-ready hybrid first when run files fragment; native-layout lookup in existing bounded background queue; exhaustive fallback and archive routing hints | Metal tests and same-route iPad P95/P99/stall counts |
| Preparation | Per-key in-flight shader loading, bounded runtime worker count, recent runtime-miss hash sidecar | Cold/warm startup and runtime comparison with 1/2/4 workers |
| Filtering | Preserve every guest LOD clamp and protected data samplers; fence old sampler lifetimes | Character captures with Original, 2x, 1x and auto filtering |
| Controller prompts | Fit complete labels to CWDH sampled width; retain full LB/RB/L1/R1 text and font metrics | Visual menu/prompt confirmation; action-guide layouts stay unchanged |
| Diagnostics | Rolling trace, separate state journal, source/main/chain/stamp identities, effective quality/cap reasons | Long-session capture, overhead on/off measurement |
| Settings/benchmark | Clarify fixed-selected-scale semantics, show cap reasons, invalidate interrupted/settings-changed measurements | In-game persistence and suspend/resume checks |
| Archive compaction | Retain existing original-function capture and crash/interruption guard; preserve valid files | Root cause of the later guarded interruption remains unknown |
| BC uploads | Preserve existing content-keyed ASTC cache and byte-compatible conversion | Upload/cache/readback profiling; no speculative encoder rewrite |
| GPU-generated compressed targets | Root cause distinguished from filtering; no blanket format override | Open rendering work below |
| Packaging | Record exact source/game/main metadata in full and host builds; preserve bundle/data gates | Successful private build and verified release assets |

The new archive-order option is enabled only where a bundled variant and a
fragmented run archive exist. Missing or unsupported variants retain the
original full lookup/render path. It uses real matching shaders, not frame
generation or missing draws. The temporary pulling path can increase vertex
GPU work; `DM_PSO_ARCH_ASYNC=0` is the A/B control.

The learned sidecar stores only up to 4096 record hashes and batches its writes
on a utility queue. It prioritizes misses encountered during recent runtime
work, including lookahead; it is not yet a universal frequency/cost predictor.
No existing pipeline archive, converted texture cache or guest resource is
deleted to make the benchmark look better.

## Memory and cap policy

The detailed mechanism is in [memory pressure recovery](reference/frame-rate.md#memory-pressure-cap-recovery).
OS pressure is not inferred from the process's remaining allocation allowance.
A critical signal can be genuine while process headroom remains positive.
The baseline lacks raw flags and NORMAL records, so it cannot prove the kernel's
internal reason for each signal. The new recorder supplies those observations.

Protection remains active under continued OS pressure or genuinely low headroom.
Quality reduction is not a replacement for reclamation: it does not automatically
shrink every guest allocation, cached pipeline/library, retained texture or
full-size intermediate. Sampler filtering changes sampling cost, not allocated
texture storage. Cold scratch retirement is bounded and waits for completion;
private render-target history and guest-readable bytes are not considered disposable.

`DM_FPS_HOLD=off` disables extra lateness holds; it does not override the requested
target, movie rate, thermal recovery or memory protection. Frame-step reason
bits are diagnostic data; the UI uses readable labels. Existing movie/VFR
fixed-step semantics remain unchanged rather than guessed from unrelated stutters.

## Open rendering work

The two observed attachment warnings differ from the filter bug:

- A decoded R8 backing is asked to provide an RGBA16UI compressed-block view.
- An ASTC backing is asked to provide an RGBA32UI render-target view.

The native-BC shadow path expects encoded blocks compatible with the texture's
backing. A16's decoded/ASTC substitute does not meet that contract. Merely adding
format-view usage or copying BC bytes into ASTC cannot repair it. A correct
future implementation needs a separately validated GPU decode/transcode path
for generated blocks, with ordering and consumer-format tests. A synchronous
CPU readback/transcode in the frame loop would introduce a new stall and is
not enabled as a speed fix. The logs establish declined attachments, not the
visible extent of their effect on characters or frame pacing.

`kCFRunLoopCommonModes` is reported during startup. Repository calls were searched;
the host does not call `CFRunLoopRunSpecific`/`CFRunLoopRunInMode` with that pseudo-mode.
Using CommonModes to schedule an input source is valid and is not evidence of
this warning's caller. A symbolicated runtime stack is still needed before
changing unrelated event-loop code. No causal link to the later memory cap is established.

Purple artifacts were a MeloNX report, never a defect observed in this native
build. No blanket visual workaround is added or reverted for that report.

## Primary research and what applies

- [Apple's memory guidance](https://developer.apple.com/documentation/metal/reducing-the-memory-footprint-of-metal-apps)
  and [XNU notifications](https://github.com/apple-oss-distributions/xnu/blob/main/doc/vm/memorystatus_notify.md)
  distinguish working set, process allowance, system pressure and jetsam.
  Reclaim only resources whose contents can safely be recreated; avoid walking
  the whole object graph or making guest storage purgeable.
- [Metal sampler LOD](https://developer.apple.com/documentation/metal/mtlsamplerdescriptor/lodminclamp)
  also constrains explicit-level reads. This makes the removed blanket mip floor
  a correctness problem, not just a visual-quality preference.
- [MoltenVK's pipeline-cache guide](https://github.com/KhronosGroup/MoltenVK/blob/main/Docs/MoltenVK_Runtime_UserGuide.md)
  separates reusable conversion products from driver compilation. NXNative
  already translates game shaders offline; adding another MSL-conversion cache
  does not address the measured archive-lookup stall. Per-key in-flight work
  avoids both duplicate loads and a global compile lock.
- [Dolphin's hybrid shader design](https://dolphin-emu.org/blog/2017/07/30/ubershaders/)
  explains the useful principle of rendering with a prepared compatible variant
  while specializing. NXNative already has a pulling/hybrid implementation;
  this change uses it before an expensive synchronous archive search.
- [Upstream archive issue #342](https://github.com/seedds/nxnative/issues/342)
  explains why retrying serialization or removing recovery markers blindly is
  unsafe. Its original-function capture correction is already in the baseline.

Only owned resources are used. No third-party cache is downloaded or imported.
Reusable archives must match game/module inputs, shader chain, relevant function
constants, GPU architecture and compatible OS/compiler binaries, with integrity
checks. An unrelated emulator's cache is not automatically a Metal 4 archive.
Keep pipeline prebuild enabled: the current bundled-coverage path already avoids
redundant work; disabling it is not a demonstrated FPS improvement. MetalFX
interpolation/temporal API support alone does not supply the motion/depth/history
inputs and integration needed for correct frame generation. The current path is spatial only.

## Checks and limits

Locally executed on Linux:

- GCC ASan/UBSan with warnings as errors: memory policy, sampler semantics,
  exhaustive archive routing, adaptive controller and concurrent rolling trace
  in disabled, ordinary and saturated modes. LeakSanitizer is disabled because
  this container cannot support its process inspection; ASan/UBSan remain active.
- 29 targeted Python tests for controller resources, trace analysis, host reuse
  safety and launcher settings.
- Exact installed-IPA asset checksum and fourteen owned-font structural repairs:
  all non-texture sections/headers preserved, existing manifests verified;
  no game assets are part of this PR.
- Pinned ruff/pyright baseline check: no new findings.

Mac-only tests were extended for concurrent shared/failed shader loading and
archive-only quick-probe/fallback behavior. They are **not** claimed executed
by Linux. The actual iOS host must compile/link in source CI. No new A16 FPS,
visual, thermal or long-session result is claimed.

The required five-game regression route is BOTW, TOTK and Wonder (NVN), Hades
(Vulkan) and Digimon Cyber Sleuth (OpenGL). Local `regress.py` cannot start on
Linux because `/usr/lib/libproc.dylib` is unavailable; owned game builds and a
Mac/GPU are also absent. No `validated.tsv` entry is added. Private build
infrastructure did not start the requested runner; details remain private.
No new IPA is represented as built.

## Build, update and rollback

The public PR is a source candidate. Changes to the resource generator trigger
the conservative host-reuse guard, so the next private IPA must use the existing
full-input cloud workflow. The guard is not weakened. The owned inputs already
exist privately; no new Mac Xcode installation or game/key upload is required.

Before delivery, require source CI success, real private job success, final IPA
ZIP/arm64/source/main/chain checks, controller-font revision 2 and manifest
checksums. Compare both action-guide pack hashes with the installed build, and
compare the complete RomFS identity/hash: if identical, retain the existing
data image instead of making the player download it again. Keep bundle
`org.gds0202.botw.a16`; preserve the signing identity/sideload workflow and
back up saves. Update the existing app rather than deleting it. Retain the old
IPA for rollback. A failed/blocked job is not a downloadable candidate.

## Device acceptance route

Use Handheld, 1080p output, spatial MetalFX, 60 FPS target, internal starting
scale 100%, automatic quality on and minimum 576p. Begin with Original filtering
to isolate sampler correctness, then test eligible 2x/1x and optional auto
filtering. Visibility reduction is optional and has a configurable floor;
it is a camera clip, not actor/terrain streaming distance.

First compare cache warm/cold and archive-async on/off on the same save, route,
time of day and settings. Preserve caches for warm runs. Try shader workers
1/2/4 with a fixed BC worker count, then compare BC 2/4 with the best measured
shader budget. Include initial loading, a repeated traversal, a genuinely new
area, menus, cutscenes, travel and at least one session beyond the old trace cap.
Do not certify a gain from different routes, a different actual scale, a capped
or lossy trace, or a one-off FPS peak.

Acceptance needs fewer >50/>100 ms real presentation intervals, improved P95/P99
and tail FPS, bounded footprint and safe cap recovery without oscillation. Check
menu LB/RB and all controller prompts; confirm the action-guide diamond, saves,
physics and movie speed. Compare trace on/off overhead separately. Retained
windows and incomplete 30-second measurements are labeled, not called full tests.
