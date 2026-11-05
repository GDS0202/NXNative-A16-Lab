# Licenses and provenance

The fork preserves NXNative/NXNativeWindows history and the root MIT license.
This is a component inventory, not a claim that every vendored item is MIT.
Original notices remain beside their components. Nintendo games/keys/assets
are not licensed or supplied by this project and do not belong in public builds.

| Component | License / retained notice | Use |
|---|---|---|
| NXNative, Windows fork and original d2r-mobile lineage | Root `LICENSE` (MIT), original README | Native rewriting/Horizon/Metal foundation |
| Reviewed dirty-pool retirement fix and fixture | MIT; `widmonstertony/nxnative` commit `3d2c3805`; original NXNative notices retained | Common NVN lifetime correctness; see audit/reference entry |
| MacNativeGames adaptations | `dm/third_party/macnativegames/LICENSE` (MIT) | Existing GPU index widening, clears and counter lowering |
| Ryujinx shader libraries | `dm/third_party/ryujinx/LICENSE.txt` (MIT); Spv.Generator has its own notice | Existing shader translation; no version update in this revision |
| LibHac 0.19.0 | Existing MIT NuGet dependency in `nx_extract.csproj` | Container/NCA decryption and integrity checks |
| SPIRV-Cross bundle | `dm/gfx/tools/spirv_cross_bin/LICENSE` and `LICENSES/` | Apache-2.0 core plus bundled notices; exact binary remains pinned |
| libvpx | BSD 3-Clause `LICENSE` and `PATENTS` | Existing movie decoding |
| stb_vorbis | MIT/public-domain notice | Existing audio decoding |
| Vulkan headers | Apache-2.0 or MIT notice | Existing Vulkan backend |
| deko3d layout algorithm | zlib notice in the existing texture-layout implementation | Existing block-linear layout |
| FLIP verification tools | BSD 3-Clause and bundled single-header notices | Optional image verification |
| Arm astcenc / Compressonator | Research only; their own upstream licenses | No encoder SDK newly incorporated |
| Atmosphere CNMT structures | GPL source used only as a wire-format reference | Independent parser; no GPL implementation copied |
| MacNativeGames controller layout helpers | MIT, copyright 2026 MacNativeGames contributors; [license](dm/third_party/licenses/MacNativeGames.txt) | Dependency-free SARC/BFFNT/BFLYT/Yaz0 helpers from `games/totk/scripts/make_botw_button_icons.py`, blob `6ff3511b7a4b5938d0babe7c27d4e0f3627133a3`; glyph drawing and the NXNative adapter are separate |

See [the vendored inventory](dm/third_party/README.md) and the
[dated research ledger](docs/audit-2026-11-04.md#research-and-provenance) for
specific revisions and integration/rejection decisions. Keep license review
part of each upstream source PR. Public source releases must not attach private
builder artifacts, game shader caches, data images or signed user logs.
