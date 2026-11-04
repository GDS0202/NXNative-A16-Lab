# Performance measurements and the A16 test route

The goal is sustained real-frame pacing and correct rendering. There is no
measured A16 60 fps guarantee. The earlier MeloNX frame rates are not NXNative
measurements. The current iPad report establishes boot/gameplay with purple
artifacts and intermittent stalls, without a trace or a measured baseline.

## Capture one useful baseline

1. In the new launcher's Performance section enable **Record performance
   trace**. The setting takes effect on the next game launch. Leave internal
   render scale at 100%, Handheld (1280x720), dynamic resolution off, output
   height 720 and Standard presentation. The HUD is optional.
2. Load the same save. Record 60 seconds standing still, 60 seconds moving and
   rotating the camera, inventory/map, fast travel, a new area, then at least
   ten minutes of play. Note when the gameplay route starts relative to launch.
3. After the route wait five seconds, leave the game and copy `stutter.jsonl`
   and `capabilities.json` from Files > On My iPad > BOTW A16 Lab. That visible
   app folder already **is Documents**. Copy before the next launch: one previous
   trace is kept as `stutter.prev.jsonl`. `log.txt` is useful for a crash or a
   rendering failure; never include games, saves or keys in a public report.
4. On the Mac (Python only):

   ```sh
   python3 scripts/stutter_analyze.py /path/to/stutter.jsonl
   python3 scripts/stutter_analyze.py /path/to/candidate.jsonl --compare /path/to/baseline.jsonl --start 45 --seconds 60
   ```

`--start` is seconds after the first actual presentation, not process launch.
Use it to keep loading, menus and gameplay separate. The reader emits numbers
and whitelisted evidence only. It does not copy arbitrary log strings or paths
into its output. A trace alone cannot certify visual correctness or a crash-free
session. Record those observations separately.

## What the recording measures

The collector has a fixed 4096-record sequence queue (about 1 MiB), a utility
writer, a 64 MiB file cap and one previous file. Producers do no file I/O, heap
allocation or mutex waiting. Full queues/contention are explicitly counted;
capped or lossy traces cannot certify an A/B gain. Ordinary recording is off.
The recording overhead still needs an on/off test on the iPad; low overhead is
a design property, **not a measured A16 result**.

Actual presentation callbacks provide display timestamps, guest frame IDs and
present tickets. Gaps between callbacks remain visible even when intermediate
tickets were discarded. Foreground/background boundaries split the intervals.
A delayed GPU sample is joined by guest frame ID, not by the latest FPS ticket.
The last eight guest records may not have GPU feedback before an abrupt exit.

Per-interval evidence includes total/work/submit wall times, process and submit
CPU time, acquire/present/drawable/sync waits, pipeline/library creation counts
and duration, upload CPU/GPU time, bytes, BC conversion duration and cache
lookup/hit/miss counts. Memory footprint, available process headroom, thermal
state and Low Power Mode are sampled once per second on iOS, independently of
the HUD. Hardware queries record actual GPU families and limits. Physical RAM,
GPU recommended working set and iOS process headroom are different quantities.
Thermal state is not a temperature in degrees and does not prove throttling.

A hitch's correlated evidence is **not an automatically proven root cause**.
CPU work overlaps GPU work and background jobs; cumulative durations must not
be added as if all were on the critical path. A high frame time alone does not
mean GPU-bound. Missing evidence is reported as unknown. Resource-loading and
input-to-photon latency need additional markers or an external measurement;
there is no fabricated loading or latency score.

## Definitions

| Metric | Definition |
|---|---|
| Displayed real FPS | 1000 / arithmetic mean of valid consecutive actual display intervals in ms |
| Guest-produced rate | Same calculation from guest present-loop intervals; kept separate from displayed rate |
| Generated FPS | Zero in this build; no interpolated frames are counted |
| P50/P95/P99 | Nearest rank: sorted interval at `ceil(p * N) - 1` |
| 1% low / 0.1% low | 1000 / mean of the slowest `ceil(0.01*N)` / `ceil(0.001*N)` intervals |
| Hitch counts | Strictly over 33.3333, 50, 100 and 250 ms; a regular 30 fps cadence is not called a dropped 60 fps frame |
| Ticket gaps | Missing tickets between observed presentations; not an input latency measurement |
| Memory / thermals | Peak footprint, minimum process headroom and highest observed thermal enum in the selected window |

The exact tail sample counts accompany the low-FPS figures. Short samples,
especially fewer than 1000 intervals, make 0.1% low unstable. Do not report a
single one-frame tail as an established sustained result.

## Controlled experiments

Generate only the variants needed for the current hypothesis:

```sh
python3 scripts/benchmark_plan.py --out a16-trials --variant baseline --variant bc-1 --variant bc-4
```

Each profile changes one variable from the fixed 720p baseline. Other available
variants cover preparation workers 1/2/4, learned budget 512/1024/2048, cache,
frame buffering, classic/Metal 4 **pipeline states**, full prebuild, late-frame
holds, Standard/MetalFX, 30 fps and recording overhead. `classic-pso` does not
port the NVN command renderer to Metal 3 or make iPadOS 17 supported.

Copy one profile as `env.txt` in the app's Documents and restart. Existing env
values override launcher choices and are shown as fixed there. Keep the
source/game build, save, scene, controller, power state, brightness and display
rate constant. Use A-B-B-A order, at least three repeated comparisons and
cool-downs to the same thermal state. Compare cold boot and warm boot separately.
Do not run the entire matrix before the first baseline identifies useful trials.

For BC cold/warm tests use a fresh cache directory through `DM_BC_CACHE=bench-cache/trial-name`
for the first launch, then the **same directory** for its warm repeat. Never mix
that with `off`, which deliberately bypasses the cache. Cache contents are not
portable precompiled game shaders. Preserve the same `pso_user.tsv` and archive
snapshot for comparisons of learned budgets; warm-up changes later trials.
Do not delete saves or reinstall the app to create a cold texture cache.

Two workers and a 1024 learned-record budget remain conservative experimental
defaults. There is no evidence yet that four workers or an adaptive manager is
better on this iPad. An adaptive controller is deferred until fixed settings
have device measurements. Likewise, the current learned list retains newest
first-discovered records, not measured most-used pipelines; usage-weighted
preparation needs reuse/cost data before replacing that policy.

On a 60 Hz display, 30 and 60 fps have regular refresh divisors. A 25 fps cap
cannot produce equally spaced refreshes on that display. Prefer a measured
stable 30 fps option over an unproven 60 fps claim, while keeping a 60 fps trial.

## Purple artifacts

There are at least two distinct mechanisms to separate: invalid/zero ASTC
blocks in streamed content and same-pass render feedback. GPU-written BC4
through an integer view is a third compatibility gap in the software-BC path.
A purple screenshot does not establish which one occurred.

Start with the unmodified rendering settings and the trace. `DM_NVN_ZBLOCK=1`
adds the existing zero-block diagnostic; it is not a fix. A same-scene cache
on/off comparison can exclude stale cache output. Do not enable snapshots for
every BOTW draw: this is known to add substantial work. A targeted shader-key
snapshot needs a pass trace identifying that shader. The Jeb0978 GPU BC shadow
implementation was reviewed, but its signed BC4 handling and skipped shadow
initial-content copy are not safe general replacements for our path. No such
untested decoder is enabled in the release.

See [the technical audit](audit-2026-11-04.md) for sources, rejected changes,
priorities and the measurements still required.
