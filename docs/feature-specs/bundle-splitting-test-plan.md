# QA Test Plan: Bundle Splitting (Issue #16)

## Scope

Changes under test:
- `frontend/vite.config.ts` — `manualChunks` vendor splitting + `chunkSizeWarningLimit: 600`
- `frontend/src/App.tsx` — 11 static page imports → `React.lazy()` + `<Suspense>` + `<ChunkErrorBoundary>`
- `frontend/src/components/ChunkErrorBoundary.tsx` — new component

No backend changes. No Firestore, Gemini, or auth changes.

---

## Happy Path Tests

### HP-1: Build produces no chunk-size warnings
**File:** `frontend/vite.config.ts`
**Steps:** Run `npm run build` from `frontend/`.
**Expected:** Build completes with `✓ built in X.XXs`. No `chunk exceeded 500 kB` warning in output. All vendor chunks present: `vendor-react`, `vendor-firebase`, `vendor-router`, `vendor-icons`.

### HP-2: Largest chunk is under 600 kB
**Steps:** Inspect build output table printed by Vite.
**Expected:** No single `.js` chunk exceeds 600 kB (minified). `vendor-react` ≈ 193 kB, `vendor-firebase` ≈ 100 kB, `vendor-router` ≈ 19 kB, `vendor-icons` ≈ 11 kB.

### HP-3: App renders normally — public routes
**Steps:** Start dev server (`npm run dev`). Navigate to `/`, `/terms`, `/privacy`.
**Expected:** Each page renders without blank screen or visible loading flash. `NavBar` is present on all three.

### HP-4: App renders normally — protected routes (authenticated)
**Steps:** Sign in. Navigate to `/brands`, `/dashboard/:brandId`, `/edit/:brandId`, `/generate/:planId/:dayIndex`, `/export/:brandId`, `/brands/:brandId/history`, `/auth/notion/callback`, `/onboard`.
**Expected:** Each page loads correctly. `NavBar` stays mounted across navigations (no remount flash).

### HP-5: Suspense fallback shown during slow chunk load
**Steps:** In DevTools → Network → throttle to Slow 3G. Hard-reload on `/brands`.
**Expected:** "Loading..." text is briefly visible before the page content appears. No blank screen or error.

### HP-6: ChunkErrorBoundary renders reload UI on chunk failure
**Component:** `ChunkErrorBoundary`
**Unit test:** Render `<ChunkErrorBoundary>` with a child that throws a `ChunkLoadError`. Assert the error UI appears with the message "A new version of Amplispark was deployed. Reload to continue." and a "Reload" button.

### HP-7: ChunkErrorBoundary renders generic error UI for non-chunk errors
**Unit test:** Render `<ChunkErrorBoundary>` with a child that throws a generic `Error('boom')`. Assert the UI shows "Something went wrong loading this page." and a "Reload" button.

### HP-8: Reload button calls window.location.reload
**Unit test:** Mock `window.location.reload`. Render `<ChunkErrorBoundary>` in error state. Click "Reload". Assert `window.location.reload` was called once.

### HP-9: NavBar remains visible when Suspense is pending
**Unit test:** Render `<App>` with a route whose lazy component never resolves (pending promise). Assert `NavBar` elements are in the document while `<Suspense>` fallback is active.

---

## Edge Cases

### EC-1: Direct URL navigation to a protected route (unauthenticated)
**Steps:** Open browser to `/dashboard/some-brand-id` without being signed in.
**Expected:** `ProtectedRoute` redirects to `/`. No chunk load initiated for `DashboardPage` (redirect happens before render). No Suspense flash.

### EC-2: Direct URL navigation to unknown route
**Steps:** Navigate to `/does-not-exist`.
**Expected:** Wildcard `<Route path="*">` fires `<Navigate to="/" replace />`. `LandingPage` chunk loads. No error boundary triggered.

### EC-3: Rapid navigation between routes
**Steps:** Click rapidly between `/brands` → `/dashboard/:brandId` → `/edit/:brandId` before each page finishes loading.
**Expected:** No React state-update-on-unmounted-component errors in console. Final destination renders correctly.

### EC-4: Chunk fetch error mid-navigation (non-chunk error type)
**Unit test:** Throw a `TypeError('Failed to fetch')` (not a named `ChunkLoadError`) from a lazy component. Assert `ChunkErrorBoundary` catches it and shows "Something went wrong loading this page." (generic message, not the deploy message).

### EC-5: Vite dev server HMR — module hot replacement does not break lazy boundaries
**Steps:** While the dev server is running, make a trivial change to any page component. Save.
**Expected:** HMR updates without full page reload. No `ChunkErrorBoundary` triggered by HMR module invalidation.

### EC-6: `vendor-firebase` chunk loads once and is cached
**Steps:** Open DevTools → Network. Hard-reload. Navigate between pages.
**Expected:** `vendor-firebase-*.js` appears exactly once in the waterfall (on first load). Subsequent navigations do not re-fetch it (304 or served from disk cache).

---

## Error Cases

### ER-1: Chunk load fails with `ChunkLoadError` (Webpack-style)
**Unit test:** Throw `Object.assign(new Error('Loading chunk failed'), { name: 'ChunkLoadError' })` from inside a lazy component. Assert boundary state: `isChunkError = true`, message = "A new version of Amplispark was deployed. Reload to continue."

### ER-2: Chunk load fails with Vite/Chrome message
**Unit test:** Throw `new Error('Failed to fetch dynamically imported module: https://...')`. Assert `isChunkError = true`.

### ER-3: Chunk load fails with Safari message
**Unit test:** Throw `new Error('Importing a module script failed')`. Assert `isChunkError = true`.

### ER-4: Chunk load fails with Firefox message
**Unit test:** Throw `new Error('error loading dynamically imported module')`. Assert `isChunkError = true`.

### ER-5: Non-Error thrown (string)
**Unit test:** Render `<ChunkErrorBoundary>` with a child that throws the string `'something broke'`. Assert boundary catches it and shows generic error UI without crashing.

### ER-6: `componentDidCatch` logs to console on error
**Unit test:** Spy on `console.error`. Trigger an error inside `ChunkErrorBoundary`. Assert `console.error` was called with a message containing `'[ChunkErrorBoundary]'`.

---

## Integration Points

All changes are frontend-only. No backend, Firestore, Gemini, or Firebase auth mocking is required for these tests.

**Testing patterns to follow** (from `BrandsPage.test.tsx` and `LandingPage.test.tsx`):
- Wrap components in `<MemoryRouter>` for routing context
- Mock `useAuth` via `vi.mock('../../hooks/useAuth', ...)`
- Import page components statically in tests (bypasses `React.lazy()` — correct, tests the page behaviour not the loading boundary)
- For `ChunkErrorBoundary` unit tests, use a `ThrowingChild` helper component that throws on render

---

## Regression Risk

### Existing tests unaffected
All existing page tests (`LandingPage.test.tsx`, `BrandsPage.test.tsx`) import page components **directly** with static imports and wrap in `<MemoryRouter>`. They bypass `App.tsx` entirely — the lazy conversion is invisible to them. No changes needed.

### Coverage gap exposed by this change
`ChunkErrorBoundary` is a new component with no existing tests. All error boundary behaviour (error detection, message selection, reload trigger, console logging) must be covered by the new tests in HP-6 through ER-6 above.

### Build regression guard
The build output chunk sizes should be checked in CI. If a future dependency update causes `vendor-react` or another chunk to grow past 600 kB, the Vite warning threshold will fire and the CI build output will show the warning. This acts as a passive regression guard without needing an explicit CI assertion.
