# certkit-3py — pin the mathlib rev in lakefile.toml

Status: **closed**. One-line fix, verified.

## The problem

`lean/lakefile.toml`'s `[[require]]` for mathlib had `git = "..."` but no
`rev`, so `lake-manifest.json` was the only pin and any `lake update` in any
session silently re-drifted it. It had drifted three times
(`67f608e6` → `9221f0553` → `5ba95124`), each time as undocumented
working-tree churn a human had to catch at commit time.

## The fix

A sandbox worker (claimed the bead, left it stranded without a handoff) added:

```toml
[[require]]
name = "mathlib"
git = "https://github.com/leanprover-community/mathlib4.git"
rev = "5ba95124681110751345e9bd360994de8541027c"
```

`5ba95124` is the rev already pinned in `lake-manifest.json` and already
checked out under `.lake/packages/mathlib` — the one every recent green build
ran against and that commit `1c509d3` committed. So this pins to what is
actually in use; it does not change which mathlib the project builds against.
`lake` also rewrote `lake-manifest.json`'s mathlib `inputRev` from `null` to
`5ba95124...` to match.

## Verification (this session)

```
$ cd lean && lake build Certkit
Build completed successfully (8804 jobs).
```

3 `sorry` (`residual_encloses_some_eigenvalue`, `temple_lower`, `weyl_shift`) —
unchanged, same as before the pin. A future `lake update` now requires
editing the `rev` line, which is the point.

## Not done

The other require blocks in `lakefile.toml` (batteries, aesop, etc. via
mathlib's own transitive deps) are still only pinned by `lake-manifest.json`.
mathlib was the one that drifted; pinning it is what the bead asked for.
Pinning the full transitive set would mean pinning every `[[require]]`, which
mathlib itself does not do — out of scope.
