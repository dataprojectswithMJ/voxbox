# Integrating `mockup/index.html` functionality into VoxBox

Scope: only the features actually present in the mockup — script history, voice
activation/deactivation, consent "scope," generation permissions, and dashboard
notices. Explicitly excluded (per instruction, even though the mockup's static
data hints at them): star ratings, generation-progress overlays, and popups/modals
beyond the existing script-submission modal.

This is a gap analysis against the real backend (`app/main.py`, `app/store.py`,
`app/screening.py`) and current frontend (`static/app.js`, `static/index.html`),
not a rebuild — a lot of what the mockup fakes with static JSON already exists
for real in the app.

## 1. Script history (Approvals Queue with status tabs)

**Already real:** `/api/rentals` stores every submission with `status`
(`pending_actor_review` / `approved` / `denied`), `decided_by`, `decided_at`,
`screening_note`, `flags`. `app.js` already renders a pending-review queue with
bulk approve/deny (`loadApprovals`, `bulkDecide`).

**Gap:** the mockup's queue is a *full history* with four tabs — All /
Auto-Approved / Needs Review / Auto-Denied — not just the pending list.

- Extend `GET /api/rentals` usage (already supports no filter) to fetch all
  statuses for the current owner, client-side.
- Derive "auto" vs "human" from the existing `decided_by` field
  (`"system"` = auto, a persona id = human decision) — no schema change needed.
- Add the tab/filter-chip UI and per-status counts client-side.

**Effort: small.** Backend already has everything needed; this is frontend-only.

## 2. Voice activation / deactivation (marketplace visibility toggle)

**Gap — genuinely new, but simpler than the mockup makes it look.** Every
voice a user creates is already fully set up at creation time (recorded,
consent declared, priced) — there's no incomplete/in-progress state, so
we're **not** building the mockup's "60% complete, finish personalizing"
draft concept. The toggle is purely a visibility switch: on = listed in the
marketplace, off = hidden from renters but still owned and manageable.

- Add a `visible` (or `status: "published" | "unpublished"`) boolean field to
  the voice entry in `store.py`, defaulting to `True`/`"published"` so
  existing voices behave exactly as they do today.
- Add `store.update_voice(voice_id, **fields)` (mirrors the existing
  `update_rental` pattern) and a route, e.g. `PATCH /api/voices/{id}/visibility`,
  restricted to the owner persona.
- `GET /api/marketplace` filters to visible voices only. `GET /api/voices`
  (used by "My Voices") is unaffected — owners always see all their voices
  regardless of toggle state.
- Renters who already rented a now-hidden voice should probably keep access
  to generate with it (the toggle affects discoverability, not existing
  rentals) — worth confirming, but that's the natural reading.
- Frontend: a single toggle switch per voice card in "My Voices," no
  progress bar, no "setup incomplete" messaging.

**Effort: small.** One field, one endpoint, one filter — smaller than
originally scoped since there's no draft/incomplete state to model.

## 3. Scope (consent label per voice)

**Already real, different shape.** The backend already enforces consent via
`consent_conditions` — a list of granular categories (`ads`, `political`,
`adult`, `medical_claims`, `financial_advice`, `hate_violence`,
`impersonation`) that `screening.py` actually checks scripts against. This is
more precise than the mockup, which just shows one static label like
"Full Commercial" or "Advertising Only" per voice card.

- No backend change required — the real enforcement already exists and is
  stronger than the mockup's version.
- Only need a small client-side mapping (declared conditions → a single
  display label) if you want the mockup's single-tag look on voice cards.
  Otherwise, the current per-condition pill list is a legitimate — arguably
  more honest — rendering of the same data.

**Effort: trivial.** Cosmetic only, no schema/endpoint work.

## 3b. Actor vs renter: one account, both abilities

**New requirement, backend already mostly supports it.** "Role" today is
just a label on the 5 fixed demo personas (`auth.PERSONAS`), used only to
decide which sidebar links render. No endpoint actually checks role — every
route checks ownership/access on a specific voice (`owner_persona_id`,
`store.has_access`), which already works fine per-account regardless of any
"role." The gap is that real signed-up accounts aren't wired into this at
all yet, and the nav hard-codes a role split that shouldn't exist.

- **Drop the fixed persona list as an identity source.** Replace
  `owner_persona_id` / `renter_persona_id` / `decider_persona_id` params
  with the logged-in account's own user id (from `app/accounts.py`) instead
  of validating against `auth.PERSONAS`. The demo personas can stay as seed
  *accounts* (for quick manual testing) but stop being a separate concept
  from real users.
- **Un-gate the sidebar.** Every logged-in account sees Marketplace,
  Dashboard, Approvals, My Voices, and History — no role-based section
  hiding. If an account hasn't published a voice, "My Voices"/"Approvals"
  are just empty, not hidden.
- **History view (from §6 below) becomes two tabs on one page** rather than
  two different pages for two different account types — "Scripts submitted
  to my voices" and "Scripts I've generated" — populated independently per
  account.

**Effort: small.** Mostly deleting a validation constraint and un-gating
nav; the per-voice ownership/access checks that make this safe already exist.

## 4. Permissions of voices (who can generate)

**Already real, and already stricter than the mockup.** The backend already
enforces:
- Owner-only preview generation (`/api/generate`, checked against
  `owner_persona_id`).
- Rental/unlock gating for renters (`store.has_access`, enforced in
  `/api/rentals`).
- Only the voice's owner persona can approve/deny a pending script
  (`/api/rentals/{id}/decision`).

**Gap:** the mockup's UX skips the "rent to unlock" step entirely — clicking a
voice card goes straight to the script-submission modal. If the mockup flow is
adopted as-is, decide one of:
- (a) keep the explicit unlock step (current behavior, one extra click), or
- (b) auto-rent on first script submission if the renter has no access yet
  (a few lines in the `create_rental` route, wrapping the existing
  `rent_voice` logic).

**Effort: trivial–small**, and only if you want to change the existing (already
correct) UX rather than just visually restyle it.

## 5. Notices (dashboard "leaving money on the table" card) — DESCOPED

**Not being built.** There's no expiration feature in the app at all — no
`expires_at` concept, no time-boxed pending state — so the mockup's
loss-aversion card has no real data to show. Revisit only if/when an expiry
feature is separately designed and built; until then this section is dropped
from scope.

## 6. Central "History" section (role-dependent view)

**New requirement, not from the mockup directly, but builds on data that
already exists.** One history view whose content depends on how the current
account is acting:

- **As a voice actor** — history of everything submitted for their voices
  that required a manual decision, plus the outcome. This is essentially
  today's Approvals queue widened from "pending only" to "everything I've
  ever decided" — same `GET /api/rentals` data (filtered to
  `owner_persona_id`), same fields (`script`, `renter`, `decision`,
  `decided_at`).
- **As a renter** — every script they've ever generated, each entry showing
  the script text *and* its resulting audio together in one card (not two
  separate lookups). The backend already has both halves of this
  (`store.list_rentals` for the script/status, `output_id` linking to the
  generated file in `store.list_outputs`) — they just need to be joined into
  one response, e.g. `GET /api/rentals?renter_persona_id=...` returning the
  `output_id`'s filename inline, or a small join in the route.

**Effort: small.** No new fields — this is one new route (or one extended
existing route) plus one new frontend view that reuses data models already
in place from rentals/outputs.

## 7. Smaller mockup-only pieces worth listing

- **Marketplace category + filter chips** (Narration/Commercial/Character/
  e-Learning): no `category` field exists on voices today. Small addition —
  a form field at voice creation, stored, filtered client-side like the
  mockup does. **Effort: small.**
- **Sidebar "Approvals" badge count**: trivial — reuse the pending-count
  already computed for the dashboard/approvals view. **Effort: trivial.**

## Overall effort estimate

| Feature | Effort |
|---|---|
| Script history (tabs on existing rental data) | Small |
| Activate/deactivate voices (visibility toggle only) | Small |
| Scope display | Trivial |
| One account, both actor + renter abilities | Small |
| Generation permissions | Trivial–small (only if changing existing flow) |
| Dashboard notices | Descoped — not built |
| Central History view (actor decisions / renter generations) | Small |
| Category filter chips | Small |
| Approvals badge | Trivial |

**Total: roughly 1–1.5 focused days of work.** Most of the "hard" logic
(consent screening, rental approval, ownership permissions, bulk actions,
pricing, paralinguistic tags) already exists server-side and just needs the
mockup's visual treatment applied to real data. Everything remaining is
additive fields, one or two new endpoints, and frontend wiring to data that's
already correct.
