# NXNative A16 Lab

An experimental, multi-game NXNative fork for Apple hardware whose texture or
memory capabilities need extra care. **BOTW Switch 1.9.0 on a 6 GB iPad A16 is
the first test case.** Its first private build boots and plays according to the
user, with intermittent stalls. The user clarified on 2026-11-05 that purple
artifacts occurred only in MeloNX, never in this recompilation. There is no measured,
stable A16 60 fps result yet.

[Compatibility](docs/compatibility.md) · [Technical audit](docs/audit-2026-11-04.md) ·
[Performance recording and A/B tests](docs/performance.md) ·
[Cloud builds without local Xcode](docs/cloud-build.md) ·
[Live quality and controller prompts](docs/live-quality.md) ·
[Internal input detection](docs/input-detection.md) · [FAQ](docs/faq.md)

This fork adds bounded BC→ASTC conversion, exact faster ASTC packing, verified
texture conversion caching, fenced staging reuse, safe guest texture backing,
720p output defaults, actual-presentation metrics and an opt-in stutter trace.
It corrects a dirty-pool lifetime race, reports actual Metal/MetalFX capabilities
and uses an A14 host instruction-set floor with A16 tuning. Adjustable render
scale, 30/60 fps targets and optional spatial MetalFX remain available.
**Compilation and synthetic tests are distinct from device/game validation.**

The common engine and retained game profiles remain multi-game. A14/A15 and
other lower-memory devices are experimental and untested here; a feature query
or an instruction-set flag does not create a missing renderer or extra RAM.
The NVN path still needs iOS/iPadOS 26+ and Metal 4 command support. A16 lacks
native BC textures; the software compatibility path has open graphics limits,
especially GPU-written compressed targets. See the matrix before making a
support claim.

## How to play

The cloud builder uses [Xcode](https://developer.apple.com/xcode/) 27.1 on the
runner. Your Mac client needs Python, Git and authenticated `gh`; it does **not**
need Xcode. Use your own game inputs and keys in the separate **private** builder.
Nothing from a game is included in a public release of this fork.

The full builder produces an unsigned IPA and matching external `romfs.img`.
The host-only path can reuse an earlier private IPA's embedded code and shader
snapshot when its strict compatibility checks pass, and verifies the relinked
guest bytes. It does not require re-uploading keys or re-downloading the data
image. Full rebuilding remains necessary for changed rewriting/shader contracts.

Sign/install the private IPA with your own sideloading tool. In Files > On My
iPad > BOTW A16 Lab, the visible app folder already **is Documents**: put the
matching `romfs.img` directly there. Keep saves and previous working outputs.
For the next diagnostic trial enable **Record performance trace** before Play
and follow the [route](docs/performance.md).

## Project status and maintenance

- [Changelog](CHANGELOG.md), [roadmap and acceptance ledger](docs/audit-2026-11-04.md#next-experiments-ordered).
- [Controlled upstream observations](docs/upstream-maintenance.md): draft candidates, tests and explicit review; no automatic code merge.
- [Contributing](CONTRIBUTING.md), [security and private files](SECURITY.md), [licenses and provenance](THIRD_PARTY.md).
- [Previous A16 work and component measurements](docs/a16.md), [original NXNative guide](README.nxnative.md), [inherited Windows/Linux builder](win/README.md).

Based on [NXNativeWindows](https://github.com/zenvyzenshiro/NXNativeWindows) and
[seedds/nxnative](https://github.com/seedds/nxnative), preserving their history
and MIT notices. Vendored components retain their own licenses. The inherited
gallery is upstream evidence, not an A16 compatibility table.
