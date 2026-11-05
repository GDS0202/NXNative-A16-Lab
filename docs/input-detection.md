# Internal game input detection

Package identity is read from integrity-checked CNMT files inside meta NCAs.
The title ID, Application/Patch/AddOnContent type, package version, parent
application ID and the base's patch ID are authoritative. Filenames and ticket
rights IDs are not used to identify an application. An XCI may contain its base,
updates and DLC together. Multi-application input folders are rejected explicitly.

The metadata tool checks bounded table lengths, the CNMT digest, referenced
content IDs, uncompressed NCA sizes and primary Program NCA associations.
Missing content, conflicting metadata for one title/version, a patch without a
base, and mismatched base/patch associations stop before game rewriting. A
base named `[01007EF00011E800][BASE]` is still a base if its internal Application
record says `01007EF00011E000`. No rename is needed.

NSZ/XCZ inspection reads their uncompressed meta NCAs and preserved NCZ headers;
compressed game contents must still be decompressed before extraction. The
converted package is inspected again. A same-stem NSP is not trusted without
checking its metadata. Uppercase extensions work. A compressed meta NCA, a
Switch 2 content platform, delta-only updates, personalized tickets and packages
with renamed internal NCA IDs are rejected with an explicit limitation.

This is **metadata verification, not a full payload authenticity audit**. The
extractor still validates data sections with LibHac's `ErrorOnInvalid`; it does
not hash every multi-gigabyte NCA during a quick input scan. Strict game build
IDs remain an additional, independent gate before build-specific patches run.
Do not use `--allow-damaged` for a diagnostic baseline.

An explicitly trusted repacked input may have an NCA-valid CNMT whose internal
digest no longer matches. The default still rejects it. For such a known file,
`DM_CNMT_DIGEST_ALLOWLIST` accepts a comma-separated list of complete CNMT SHA-256
values. A pin exempts only that exact byte sequence from the internal-digest
comparison. Bounds, associations, referenced NCA sizes, NCA section integrity
and strict NSO build-ID gates still apply; the input and its digest are never
rewritten. Inspection reports `cnmt_digest_verified: false` and the builder logs
the explicit pin. This is an opt-in compatibility workaround, not proof of
Nintendo authenticity or permission to accept unknown corrupt packages.

The [BOTW input note](../dm/games/01007EF00011E000/README.md#input-metadata-compatibility)
records a private build using this option. No public game hashes or hard-coded
game exception is added to the parser.

The build needs .NET 10 on the machine doing extraction. Cloud builds install
it on the runner; the Mac client still needs only Python, Git and `gh`.
Inspection tools/logs live in `_nx_inputs/` beside the user's packages, outside
source control. The small extractor is reused only while its source fingerprint
matches. Diagnostics do not print key values or cryptographic stack traces.

Tests use synthetic wire records and container headers, never games or keys:

```sh
dotnet run --project dm/tools/tests/cnmt -c Release
python3 -m unittest dm/tools/tests/test_nsp_scan.py dm/tools/tests/test_nsp_nsz.py
```

The parser is an independent implementation of the packaged CNMT wire format.
The structural reference is Atmosphere's
[`ncm_content_meta.hpp`](https://github.com/Atmosphere-NX/Atmosphere/blob/master/libraries/libstratosphere/include/stratosphere/ncm/ncm_content_meta.hpp);
no GPL implementation code is incorporated. LibHac remains the existing MIT
container, NCA decryption and integrity-check dependency.
