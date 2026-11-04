# Changelog

## Unreleased

- Correct benchmark resolution claims: BOTW scale 1.0 preserves the game's
  dynamic resolution. Remove the NieR-only dynamic toggle from BOTW profiles;
  a nominal 720p output is not proof of a fixed internal 720p scene.

## 0.2.0 — Experimental (2026-11-04)

- Classify internal Application/Patch/AddOnContent metadata, versions and
  associations, independent of NSP/XCI filenames. Validate bounds, digest,
  referenced content and primary program identity; keep strict build-ID gates.
- Correct dirty-page protection racing pool retirement, with a deterministic
  CPU fixture and retained existing race tests.
- Add opt-in bounded, asynchronous stutter recording, actual displayed-frame
  joins, conversion/cache timings, system/headroom/thermal samples and an
  offline percentile/tail analyzer with controlled A/B profiles.
- Start recording after launcher choices are applied. Extend the HUD with P99,
  actual displayed guest-frame GPU time, thermal state and trace-loss counts.
- Query actual hardware/MetalFX capabilities; compile the iOS host for an A14
  instruction-set floor with A16 tuning. Other devices remain untested.
- Add guarded private host-only IPA rebuilding, byte-identical guest round-trip
  checks, selective output downloads and immutable references to existing data.
- Add controlled upstream observation drafts, compatibility/benchmark/security
  documentation, contribution guidance and license provenance.

Known limits: A16 purple artifacts and intermittent stalls need device traces;
there is no measured 60 fps guarantee. GPU-written BC4 semantics and optional
frame generation remain open. Source/synthetic validation is not gameplay proof.

## 0.1 — Previous A16 lab baseline

Bounded BC conversion, exact ASTC packing improvements, verified persistent
texture cache, fenced staging reuse, pressure guard, bounded learned prep,
720p output defaults and private cloud building. The user's private BOTW 1.9.0
build reached gameplay with unresolved artifacts/stalls.
