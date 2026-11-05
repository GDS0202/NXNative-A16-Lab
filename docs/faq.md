# FAQ and troubleshooting

**Can I get a public ready-made BOTW IPA?** No. The public project distributes
source/tools. Game-containing IPAs, images and keys stay in the owner's private
builder. Builds use the user's own inputs.

**Do I need Xcode on my 8 GB M1 Air?** No for the cloud client. Python and `gh`
transfer/verify private files and start GitHub Actions; Xcode 27.1 is on the
runner. Host-only reuse can transfer just the previous IPA and metadata.

**Will this remove every hitch or guarantee 60 real fps on A16?** No such result
has been measured. CPU/GPU work must fit the real display budget, and memory,
shader creation and thermals matter. The diagnostic route establishes where to
optimize next. A stable 30 fps option remains useful at fixed 720p.

**Is frame generation enabled?** No. API support is queried, but coherent motion,
depth, UI and latency handling have not been validated for BOTW. Generated frames
would be reported separately from real frames.

**Does A14 compilation mean A14/A15 support is verified?** No. It avoids an
A16-only host instruction-set requirement. GPU capabilities, OS, game features,
process memory and sustained device behavior still need tests.

**Were purple artifacts reported for this recompilation?** No. On 2026-11-05
the user clarified that they occurred only in the earlier MeloNX project.
The lab does not enable a speculative visual workaround for that report.
General [rendering diagnostics](performance.md#historical-rendering-diagnostics)
remain available for a separately evidenced problem.

**Why does the builder call my base an update?** The new reader uses internal
Application/Patch/AddOnContent CNMTs, not `[BASE]`, `[vN]` or title tags in the
filename. A real Patch without a base is rejected. See [input detection](input-detection.md)
for completeness checks and unsupported cases. Never fix identity by renaming.

**Why does a launcher choice stay fixed?** An explicit `Documents/env.txt` value
has priority and is shown as fixed. Stop the app, change/remove that override,
then restart. Worker/cache choices and trace recording apply at launch, not in
an already running guest. The trace starts after Play has applied choices.

**Where are the data/log files?** The app folder visible in Files is Documents.
Put `romfs.img` directly in it. Do not create another Documents directory.
`log.txt`, `log.prev.txt`, `stutter.jsonl` and `capabilities.json` live there.
Copy diagnostics before a new launch replaces the current session.

**Why did host-only rebuilding stop?** It deliberately refuses a changed guest
rewrite/ABI/profile/shader contract, missing/mismatched stamps, packed NROs,
symlinked resources, an invalid Mach-O or altered relinked guest bytes. Use the
existing private inputs for a full build; never change a stamp to bypass it.

**Can I delete the previous output release?** Keep it while a newer manifest
references its `romfs.img` parts. New host builds preserve the matching data
identity. Selective IPA downloads still work without re-downloading that image.
