# NXNative A16 Lab

Experimental BOTW Switch 1.9.0 work for iPad A16 / 6 GB. **A16 BOTW gameplay
validation is pending. Stable 60 real fps is a target, not a promised result.**

[Changes, audit and measurement plan](docs/a16.md) ·
[Cloud IPA build without local Xcode](docs/cloud-build.md) ·
[Original NXNative guide](README.nxnative.md) ·
[Inherited Windows/Linux builder](win/README.md)

This fork adds bounded BC-to-ASTC conversion, exact faster ASTC packing,
verified persistent texture conversion caching, fenced staging reuse, safe
texture backing, 720p defaults and actual presentation metrics. Adjustable
resolution, a 30/60 fps target and MetalFX spatial upscaling are available in
the launcher. No game content or keys are included.

Based on [zenvyzenshiro/NXNativeWindows](https://github.com/zenvyzenshiro/NXNativeWindows)
and [seedds/nxnative](https://github.com/seedds/nxnative), with their history and
MIT license preserved. See [the audit](docs/a16.md) for the other projects
reviewed and for features intentionally not enabled without evidence.

The cloud builder uses [Xcode](https://developer.apple.com/xcode/) 27.1.
It is installed on the build runner; your Mac does not need Xcode.

## How to play

Build from your own base game and 1.9.0 update. The private cloud builder
will produce an unsigned IPA and a matching `romfs.img`. Sign/install the
IPA with your sideloading tool, then copy `romfs.img` to its Documents folder.
The launcher exposes settings before Play. In Files, the visible app folder
is already its Documents root; put the image directly there. See [the retained guide](README.nxnative.md)
for device requirements and signing; its gallery is upstream evidence, not A16 validation.
