# Live quality and controller prompts (experimental)

These are source features, not measured iPad FPS improvements. No final IPA is
created by the source tests. BOTW's new guest stubs require rewriting its own
verified 1.9.0 main module; rebuilding only an old IPA's host does not install
them. An old fixups table exposes none of the new guest-address controls.

## Graphics while playing

The gear at the upper right remains available with a physical controller.
Its changes apply on the next game present and are saved for the next launch.
Values fixed by `env.txt` or the launch environment remain locked.

| Control | Actual effect |
|---|---|
| FPS target | The existing verified 30/60 fps frame-step controller; preserves movie, thermal and memory guards |
| Internal scale | A fraction of the current console mode's scene base, independent of output size |
| Lock full scale | New verified BOTW flag that applies 100% every frame; off preserves native dynamic scaling in manual mode |
| Display output | 720p, 900p, 1080p or the display's size; never silently lowered by automatic quality |
| Upscaling | Standard bilinear or the existing spatial MetalFX pass, with capability fallback |
| Texture filtering | Original, anisotropy capped at 2x, or 1x plus mip floor 1; compare/reduction/nonmip samplers are excluded |
| Camera visibility | Optional active-camera far clip; zero preserves the original game value |

Texture filtering does **not** discard or resize the textures' allocated
storage, reduce their decode work, or guarantee a RAM saving. A camera clip is
**not** the distance at which actors spawn, terrain LOD, or grass traversal.
No unsupported per-game effect is represented by a nonfunctional switch.

Changed samplers invalidate descriptor/argument caches and keep their old GPU
IDs alive through the submission fence. Runtime settings never rewrite code
pages. Scale, full-scale flag and clip are aligned state-page stores consumed
by build-gated guest stubs. The zero clip path preserves the original camera
store and its registers/flags.

## Automatic mode

Choose the FPS target, display output and minimum **internal** height. The
minimum is rounded upward to a supported 5% scale. In handheld BOTW, 80% is
nominally 1024x576; 100% is 1280x720. Docked uses a 1600x900 scene base.
The engine can round individual buffers; these are not captures proving every
pass's pixel dimensions. Upscaling 576p to 1080p is not native 1080p.

The controller observes completed guest GPU work and frame-production times.
It uses bounded one-second windows, drops scale by 5% only after repeated GPU
overload, and restores quality after sustained headroom. Missing GPU samples,
movie overrides, suspension/loading gaps and significant synchronous pipeline
compilations do not train the controller. GPU headroom with slow production
is reported as a CPU/streaming/other limit; it is not proof of one root cause.

Optional texture and visibility reduction are separately opt-in. They run only
after the internal-resolution floor has been reached. Their requested values
remain the manual baseline. The output size never changes automatically.
If the allowed quality range cannot meet the target, the menu says the floor
has been reached rather than inventing 60 fps or lowering the floor.

Recovery is paused at serious thermal state, Low Power Mode or less than
512 MiB of process headroom. More available RAM does not prove more compiler
or texture workers improve frame pacing. Shader preparation timing now has a
launcher choice: device default, before gameplay, or background. The selected
shader worker count applies to the before-gameplay path.

**Measure current scene** records actual drawable presentation callbacks for
30 seconds, including stalls, with a bounded buffer. It shows real FPS and P95
separately from guest production. Suspension cancels the measurement. A stationary
or menu sample does not certify a demanding world route. Use the
[recorded A16 route](performance.md) for device comparisons.

No frame generation is enabled. The current presentation interface lacks
validated matching motion/depth/UI inputs; generated or duplicated frames must
not be reported as real gameplay FPS.

## Controller prompts

BOTW 1.9.0 can generate both Xbox and PlayStation versions of its font glyphs
and action-guide layout from the player's own RomFS. The public repository
contains only the generator and original monochrome glyph drawing code.

```sh
python3 scripts/make_controller_icons.py --romfs /path/to/romfs.img \
  --out /path/to/ControllerIcons --build-id cd57b23fa4bbad65803d9788c01821ee
```

The iOS resource staging step generates these assets for this exact build.
The source image is read-only; no original game archive is edited. A previously
generated destination can be replaced only when its ownership marker matches.
The app selects Original, Xbox or PlayStation at the next launch. Automatic
selection recognizes GameController's Xbox/DualShock/DualSense profiles; unknown
controllers keep original icons. Changing controller after fonts are loaded
requires restarting the game for its prompts to change.

The input mapping itself is unchanged: Nintendo A is east, B south, X north,
Y west. Thus a Nintendo A action shows Xbox B or PlayStation circle, which is
the physical button the app uses for that action. This is not a remapper for
arbitrary external iPadOS controller customizations. Other games need their
own verified font/layout adapters; there is no universal prompt replacement.

User RomFS overrides precede generated controller assets. Overlay paths reject
traversal, symlinks and special files and never redirect save mounts. The new
files and PlayStation font references need an actual device visual/gameplay
check; archive validation alone is not that check.

## Correction of the purple-artifact report

On 2026-11-05 the user clarified that purple artifacts occurred in **MeloNX**,
never in the NXNative recompilation. Earlier lab notes conflated those reports.
There is no verified NXNative purple-artifact bug to fix. No BOTW shader fact,
same-pass snapshot rule, barrier, or blanket visual workaround was introduced
for that report, so none is reverted here.

The independent dirty-pool lifetime correction and preservation of readable
guest texture backing remain: a GPU upload fence does not authorize destroying
bytes the guest may read or partially update later. Preserving them can use
more RAM than destructive discard, but is a data-lifetime requirement rather
than a purple-color workaround. The user currently reports about 2.85 GiB used
and 1.15 GiB process headroom; peaks and sustained thermal behavior remain unmeasured.

## Validation limits

Portable tests execute the feedback controller and synthetic AArch64 stubs,
exercise invalid settings and pressure/gap cases, and validate generated SARC,
Yaz0, BFFNT, BNTX and BFLYT structures. Source CI must compile/link the actual
iOS project. Actual private resource inspection establishes format/layout
metadata only. The five-game gameplay route remains BOTW, TOTK, Wonder, Hades
and Digimon Cyber Sleuth, chosen for shared NVN, Vulkan and OpenGL coverage.
No game-free Linux or CI runner can certify their rendering or iPad performance.
