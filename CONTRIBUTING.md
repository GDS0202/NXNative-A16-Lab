# Contributing

Use English for code, documentation, logs, issues and PRs. Read `AGENTS.md`, the
relevant subsystem guide and the game profile note before editing. Keep source,
private game builds and personal data separate. Do not upload keys, games,
RomFS images, saves, game-derived shader binaries or private IPAs.

Prefer a small root-cause change with a reproducer. General mechanisms belong
in the common engine; build-specific addresses stay behind exact NSO build IDs.
Preserve notices and review every imported component's license and provenance.
Do not copy GPL implementations into an MIT component without a compatible,
explicit distribution plan.

Run the relevant Python/C/texture/sanitizer checks and source CI. Renderer/chain
changes need `regress.py impact`, shader rebuilding when required and the five
relevant game routes where assets/hardware are available. Record unavailable
checks honestly. Never restamp old libraries or edit `validated.tsv` without
actual passing routes. See `docs/agents/06-dev-loop.md`.

For performance PRs give the source/game build, device/OS, resolution, save/route,
cold/warm cache state, repeated/counterbalanced trials, P95/P99/tail metrics,
memory and thermal observations, visual correctness and rollback. A synthetic
CPU speedup or a higher FPS average does not certify A16 gameplay. The
[recording guide](docs/performance.md) defines the metrics.

Experimental changes may be published with explicit limitations and private
build instructions. Beta requires repeated real-device acceptance. Stable
requires the claimed games/devices to have reproducible evidence and no known
blocking regressions. No automated upstream code merge is enabled.

## Reporting a problem

Use the source/tool bug form or the compatibility form. Include exact revisions,
a minimal reproduction and sanitized diagnostics. Follow the fixed-resolution
[performance route](docs/performance.md) for stalls; a frame-rate screenshot
alone cannot identify a cause. Keep game inputs, keys, saves and private IPAs out
of the report. Security issues follow [SECURITY.md](SECURITY.md).
