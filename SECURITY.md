# Security and private material

The public repository and releases contain source/tools and synthetic test
fixtures. Game inputs, keys, saved games, proprietary shaders, RomFS images and
game-containing IPAs belong only in the owner's private builder and app storage.
Never paste tokens, key values, signed asset URLs or whole private logs into an
issue. Inspect diagnostics before sharing them.

Private builds require a full reviewed source SHA. The host-rebuild workflow
checks source CI before private asset use. A passing CI is not a substitute for
reviewing that source: the chosen code runs with access to the private build.
Do not dispatch private builds for arbitrary external PRs. Public upstream
monitoring reads metadata only and cannot access the private builder's inputs.

Public CI uses pinned actions and read-only contents permissions except the
trusted scheduled observation workflow, which can write its own report branch
and draft PR. There is no `pull_request_target` execution of contributed code,
no automatic merge and no long-lived personal token requirement.

Report a vulnerability through GitHub private vulnerability reporting when
available. If that channel is unavailable, request a private contact without
posting exploit secrets or game data publicly. Include affected source revisions
and a small synthetic reproducer whenever possible.
