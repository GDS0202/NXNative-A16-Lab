# Build the A16 IPA without local Xcode

The Mac client needs Python and GitHub CLI. The Xcode/Metal compilation runs
on GitHub. The owner's private builder is
[GDS0202/NXNative-A16-Build](https://github.com/GDS0202/NXNative-A16-Build).
The reusable workflow is [private-build.yml](../dm/ci/private-build.yml).

## Inputs

Put your own BOTW base NSP (or base XCI), update **1.9.0** NSP and any own DLC
NSPs together in one folder outside the source checkout. Keep your `prod.keys`
outside the checkout as well. The cloud build requires title
`01007EF00011E000`, package `v1114112`, and the exact module build IDs in the
registered profile. It stops instead of guessing patches for a different build.

On the Mac:

```sh
brew install gh python@3.14
gh auth login
gh repo clone GDS0202/NXNative-A16-Lab
cd NXNative-A16-Lab
python3 scripts/cloud_ipa.py upload --repo GDS0202/NXNative-A16-Build --nsp-folder "/path/to/BOTW" --keys "/path/to/prod.keys" --start
```

Use the actual paths on your Mac. The uploader checks that the destination is
private, stores files as private draft release assets, then dispatches the build
with the full source SHA of your checkout. No game content enters Git history.
The temporary client copy is at most one 1.9 GB part. Whole-file and part
SHA-256 hashes verify reconstruction; the completion manifest is uploaded last.

Private Actions uses the account's compute allowance. Check the remaining
allowance before a long real build. A standard Mac runner guarantees limited
disk space. The workflow removes other Xcode versions only on its disposable
GitHub VM, keeps Xcode 27.1, and checks free space before downloading inputs.
If it still cannot fit the job, it stops before the large transfer. Nothing
from this cleanup runs on the user's Mac.

## Outputs

The workflow writes a private output release tag in its summary. Download it
into a new/empty folder:

```sh
python3 scripts/cloud_ipa.py download --repo GDS0202/NXNative-A16-Build --tag botw-output-RUN_ID --out "/path/to/BOTW-A16-output"
```

Output contains `BOTW-A16.ipa`, matching `romfs.img`, and `build.json` with
source/compiler information. The app and its large data image are separate,
so repeated app updates need not repackage the whole game. Private release
parts also avoid putting a large copyrighted game into public CI artifacts.

Sign/install the IPA with your sideloading tool. In Files, copy `romfs.img`
directly into **On My iPad / BOTW A16 Lab**. That visible app folder is its
Documents root; do not create another Documents folder inside it. Close and
reopen the app. Open the
launcher, verify handheld mode and 100% internal render scale (nominally 1280x720), and
start the [device acceptance route](a16.md#device-acceptance-route).

This static native path does not need JIT. The signing tool's entitlement
handling and the process's actual available memory still matter. Source CI
can verify compilation without any dump, but cannot establish BOTW playability
or 60 fps on an A16. Those checks require the real build and device.

## Host-only experimental rebuilding from an existing private output

The new private `rebuild.yml` workflow is separate from the full-input builder.
It checks source CI, then downloads **only the previous IPA and build metadata**.
It does not download keys, original NSP/XCI or the external data image. The old
output release remains unchanged.

`scripts/rebuild_host.py` recovers the already rewritten module pieces from the
old arm64 Mach-O using its fixups layout. It rejects changed rewrite/loader/ABI/
profile/shader contracts, mismatched build IDs, missing shader stamps, packed
NROs, symlinked resources and incomplete images. It keeps the original shader
stamps and `romfs.id`, relinks the new host and recovers the modules again. Every
relinked guest module must match its recovered original SHA-256 byte for byte.
There is no false restamping or conversion of old shader caches to a new chain.

The private output uses a version-2 manifest: the new IPA and metadata have new
verified assets, while `romfs.img` references the unchanged original release's
parts. References are confined to the same private repository, digest checked
on download, and flattened across successive host rebuilds. Keep the referenced
original release. Full-input builds still support the original version-1 format.

From an updated clone on the Mac, download just the new install package:

```sh
python3 scripts/cloud_ipa.py download --repo GDS0202/NXNative-A16-Build \
  --tag botw-output-RUN_ID --out ~/BOTW-A16-experimental \
  --only BOTW-A16.ipa --only build.json
```

Replace `RUN_ID` with the successful private rebuild's run ID. No local Xcode is
needed. The existing matching `romfs.img` can remain in the app's Documents; its
identity is preserved. Keep the previous IPA and saves. The install tool replaces
the executable's ad-hoc signature and must preserve the increased-memory-limit
request; the OS still decides actual process headroom.

The checked-in workflow template is `dm/ci/private-rebuild.yml`. Copy it only to
the private repository as `.github/workflows/rebuild.yml`. Choose a full reviewed
source SHA with passing tests, A16 validation and Python lint; never choose an
unreviewed external PR. If compatibility checks refuse reuse, run the existing
full build with the **already uploaded private input tag**. Do not re-upload it
or install Xcode on the Mac just to work around that refusal.

Source tests include synthetic front/trailing patch layouts and malformed
archives. The real synthetic iOS link job also checks recovery against its actual
Mach-O. A successful host rebuild proves byte preservation and linking, not
A16 gameplay, graphics correctness, latency or 60 fps.
