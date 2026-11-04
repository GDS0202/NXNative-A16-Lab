# Controlled upstream maintenance

The daily GitHub Actions workflow (04:17 UTC) and its manual trigger inspect
public repository metadata and up to 20 recently updated open PRs for each
configured source. `docs/upstreams.json` records the exact reviewed reference
points. Observation state is separate from integrated code. A changed head or
candidate creates a **draft observation PR**, with no imported code and no
auto-merge. Unavailable/deleted branches retain their last known state.

The monitor runs only from this repository's trusted default-branch schedule
or a manually chosen workflow ref. It never checks out, downloads or executes
an upstream candidate. It does not commit remote PR bodies/titles; only fixed
categories, validated IDs, hashes and repository-scoped links. No private game
builder token or data enters the public workflow. The write permission is for
its own observation branch and PR, not permission to import source automatically.

For each actual integration:

1. Pin the candidate commit/PR, compare its license and retained notices, and
   record which problem it addresses. A keyword match is only a review hint.
2. Create a source branch from the current experimental baseline. Port the
   smallest root-cause change; keep game/build-specific patches gated.
3. Run the applicable source/texture/shader/sanitizer checks, `regress.py impact`,
   then the five relevant game routes where assets/hardware are available.
   Record untested devices, visual differences and P95/P99/memory regressions.
4. Open a source PR with before/after evidence and a rollback commit. Shader
   chain or serialized input changes require shader rebuilding; old library
   stamps must never be edited to make a test pass.
5. Merge only after review; publish an experimental private game build when
   device acceptance is pending. Stable requires repeated device results.

GitHub must allow Actions to create pull requests for automatic draft PR
creation. The observation artifact and checks remain useful if repository
policy blocks that write; inspect the failed step and enable the repository
setting deliberately. No workflow requests a long-lived personal token.
