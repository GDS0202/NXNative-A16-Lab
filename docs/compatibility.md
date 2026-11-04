# Compatibility and validation matrix

A source build is not a game test. Status terms: **verified** requires a device,
game build, route and evidence; **experimental** is incomplete validation;
**not tested** makes no boot/gameplay claim. Results from other emulators or
stronger Macs are not entered as this fork's A16 results.

| Device / SoC / RAM | OS | Game / version | Boot / gameplay | Graphics | Audio / crashes | Measured FPS | Status / evidence |
|---|---|---|---|---|---|---|---|
| iPad 2025, iPad15,7 / A16 / about 6 GB | User's iPadOS 27.x environment | BOTW Switch, 1.9.0 / v1114112 | Boot and gameplay reported | Purple artifacts; intermittent stalls | No reliable audio/crash dataset | Not measured | Experimental; user's private build run 41364325695 |
| Same iPad | Same device | Next lab revision | Awaiting device trace | Not yet checked | Not yet checked | Not measured | Source/CPU/synthetic iOS CI only |
| iPhone A16 / model-dependent RAM | 26+ required for current NVN path | Retained profiles | Not tested here | BC fallback and memory budget need validation | Not tested | Not measured | Experimental |
| A15 / model-dependent RAM | 26+ for current NVN path | Retained profiles | Not tested | Apple8 capabilities do not guarantee sufficient process memory | Not tested | Not measured | Not tested |
| A14 / model-dependent RAM | 26+ for current NVN path | Retained profiles | Not tested | A14 ISA floor and capability reporting are preparation only | Not tested | Not measured | Not tested |
| Other Apple Silicon | Depends on API/backend | Retained NVN/Vulkan/GL profiles | See upstream per-game notes; no new lab device claim | Per-game/backend limits | Per-game notes | No new lab numbers | Inherited evidence, not blanket lab support |

The runtime queries GPU families, native BC, MetalFX support, unified memory,
resource limits, physical memory and actual process headroom. It does not
select support solely by a model name. NVN Metal 4, older-OS Metal 3 ports and
classic Vulkan/GL paths are distinct implementations, not a launcher toggle.
Some games need features not available on Apple7/8; adding a fallback requires
its own correctness and performance work.

The iPad's initial report gave roughly 5914 MiB physical RAM and 4036 MiB
available to the app. That is a report from one process state, not a fixed
entitlement or a universally available allocation budget. Record current
`capabilities.json`, headroom and the source SHA for every new result.

To contribute a result use the compatibility issue template, the exact game
package/build ID, a repeated route, visual/audio/crash notes and the bounded
trace. Keep saves, games, keys and private build assets out of public reports.
