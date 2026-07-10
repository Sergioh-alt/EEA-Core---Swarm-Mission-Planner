# Phase 10C.3 — Clean-Clone Fix & Validation Report

## Issue

A fresh clone of the repository (post-merge of Phase 10C.3, PR #37) failed to
compile with:

```
Module not found: Can't resolve "@/lib/mockDataProvider"
```

`ConnectionProvider.tsx` imports `startMockDataProvider`, `stopMockDataProvider`,
and `isMockRunning` from `@/lib/mockDataProvider`, but `orion-ui/src/lib/` in the
committed tree only contained `restClient.ts`, `wsClient.ts`, and `utils.ts`.

## Root Cause

The repository root `.gitignore` contains the standard Python packaging pattern:

```
lib/
```

This pattern is **unanchored**, so Git applies it at every directory depth — it
matched not only Python build output but also the Next.js UI source directory
`orion-ui/src/lib/`.

The pre-existing files (`restClient.ts`, `wsClient.ts`, `utils.ts`) had been
force-added during Phase 10C.2, so they were tracked despite the ignore rule.
`mockDataProvider.ts` was **new in Phase 10C.3** and was never force-added, so
`git add` silently skipped it and it never entered the commit. The local
workspace still had the file on disk, which is why local builds passed while a
fresh clone failed.

Verification:

```
$ git check-ignore -v orion-ui/src/lib/mockDataProvider.ts
.gitignore:12:lib/    orion-ui/src/lib/mockDataProvider.ts
```

## Resolution

The file should exist (the architecture did not change — the mock provider is
required by `ConnectionProvider`). Fix applied:

1. **Restored / committed** `orion-ui/src/lib/mockDataProvider.ts`.
2. **Fixed `.gitignore`** so the UI source directory can never be excluded again:

   ```gitignore
   # The Python build ignores above (e.g. `lib/`, `build/`) are unanchored and
   # would otherwise exclude the Next.js UI source directory `orion-ui/src/lib/`.
   # Re-include it so UI source is always tracked.
   !orion-ui/src/lib/
   !orion-ui/src/lib/**
   ```

After the fix:

```
$ git ls-files orion-ui/src/lib/
orion-ui/src/lib/mockDataProvider.ts
orion-ui/src/lib/restClient.ts
orion-ui/src/lib/utils.ts
orion-ui/src/lib/wsClient.ts
```

## Files Modified

| File | Change |
|------|--------|
| `orion-ui/src/lib/mockDataProvider.ts` | Added to version control (was untracked/ignored) |
| `.gitignore` | Added negation rules re-including `orion-ui/src/lib/` |

## Clean-Clone Validation

Performed exactly as another developer would use the repository — from a brand
new clone, not the existing workspace.

| Step | Command | Result |
|------|---------|--------|
| Fresh clone into new directory | `git clone --branch <fix> …` | PASS — all 4 `src/lib/*.ts` files present |
| Install dependencies | `npm install` | PASS — no missing-module errors |
| Production build | `npm run build` | PASS — `✓ Compiled successfully`, 15/15 pages generated, 0 type errors |
| Dev server | `npm run dev` | PASS — `✓ Ready in ~1s` |
| `/control` route | `curl localhost:3000/control` | PASS — HTTP 200 |
| Browser render | Load `/control` | PASS — 3 drones streaming, map + zone, telemetry charts, mission status, alerts, intent bar all render |
| Console / dev log | grep for errors | PASS — 0 errors, 0 "Module not found" |

## Confirmation

A fresh clone now **starts successfully** with no missing-module errors and all
Mission Control screens render correctly. The `.gitignore` negation prevents any
future UI source file under `orion-ui/src/lib/` from being silently dropped.
