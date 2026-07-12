# Adopting the mockup's design language in the real app

Goal: replace the current dark, ad-hoc theme with the mockup's light,
purple/white, card-based system. This is a visual swap only — no functional
changes (those are tracked separately in `MOCKUP_INTEGRATION_PLAN.md`).

## Why this is a swap, not a tweak

The two stylesheets are unrelated token systems:

| | Current (`static/style.css`) | Mockup |
|---|---|---|
| Theme | Dark (`--bg: #0a0b10`) | Light (`--color-bg: #F8F9FB`) |
| Accent | Indigo/violet gradient | Purple gradient (`#5B4FCF → #7C6FE8`) |
| Spacing scale | `--sp-1..12` (4px grid, differently named) | `--sp-4..64` (4px grid, differently named) |
| Component classes | `.voice-card`, `.stat-tile`, `.pill`, `.status-badge`, `.tag-palette`, `.phrase-box` | `.voice-card`, `.stat-card`, `.tag`, `.badge`, `.tag-palette`, no phrase-box equivalent |

Class names overlap in places but mean different things — a naive CSS
replace would break layout. This has to be a deliberate pass, not a file swap.

## Surfaces that need restyling (from the real app, not the mockup)

The current app has more surface area than the mockup shows, because the
mockup never designed a few flows the real app already has:

**Covered by the mockup's design language directly:**
- Sidebar / nav
- Dashboard (stat cards, activity feed)
- Marketplace (voice grid, filter chips, search)
- Approvals queue (list items, bulk bar, status badges)
- My Voices (management cards, toggle switch)
- Script submission modal (textarea, tag palette, pricing contrast)
- Toasts

**Not covered by the mockup — needs new components in the same visual
language, extrapolated from its tokens/patterns:**
- Login / signup / email-verify screens
- The showcase/sample-card landing page (public preview before login)
- Role tabs (actor vs renter)
- The voice **recording** flow: phrase-box, record controls, waveform/record
  status — the mockup only has playback UI, not capture UI
- Cost estimate widget on the rental/generation form (mockup has an
  equivalent — `pricing-contrast` — reusable, but it's inside the modal
  and would need adapting to the standalone rental page)

## Two ways to do the migration

**Option A — Token swap + restyle in place (recommended).**
Keep the current CSS class names and HTML structure in `index.html`/`app.js`
templates; replace only the token values and component styling rules to match
the mockup's look (colors, radii, shadows, spacing values, card/button/badge
treatments). Lower risk — no JS template rewrites, `app.js` selectors keep
working. Slightly less pixel-perfect parity with the mockup's exact markup,
but visually equivalent.

**Option B — Adopt the mockup's actual markup/class names.**
Rewrite `index.html` static sections and every `app.js` template string to use
the mockup's class names and structure directly. Higher fidelity to the
mockup, but touches every render function in `app.js` (roughly a dozen —
`loadMyVoices`, `loadMarketplace`, `loadApprovals`, `loadDashboard`,
`loadVoiceSubmissions`, `loadVoiceOutputs`, `renderTagPalette`, etc.) and
carries more regression risk since markup and behavior change together.

Recommend **Option A**: swap the design system, not the DOM. Get the visual
result the user wants with a fraction of the risk.

## Scope of work (Option A)

1. **Token file** — replace `:root` in `style.css`: colors, spacing scale,
   radius, shadow, type scale, transitions. Mechanical, one pass.
2. **Base/layout** — body, sidebar, content/page containers, page headers.
3. **Core components** — buttons, cards, badges/pills, inputs, filter chips,
   tables/lists, checkboxes, bulk-action bar. These are shared across every
   page, so getting them right here cascades everywhere else for free.
4. **Page-specific styling** — dashboard stat tiles + activity feed,
   marketplace voice-card grid + audio player, approvals list + status
   badges, my-voices management cards + toggle switch, modal + tag palette +
   pricing contrast, toasts.
5. **Net-new components not in the mockup** — login/signup screens, role
   tabs, showcase/sample cards, recording flow (phrase box, record button,
   record status) — restyle using the mockup's visual vocabulary (same
   radii/shadows/spacing/color roles) since no direct template exists.
6. **Verify** — walk every view in both actor and renter personas, light
   only (drop the current `color-scheme: light dark` dark-mode support
   unless the user wants to keep a dark variant).

## Effort estimate

| Step | Effort |
|---|---|
| Token file swap | Trivial |
| Base/layout + core components | Small |
| Page-specific styling (5 pages) | Medium |
| Net-new components (login, recording flow, showcase) | Medium |
| Verification pass across all views/personas | Small |

**Total: roughly 1–1.5 days** for Option A. Option B (rewriting markup to
match the mockup exactly) would roughly double that, mostly in `app.js`
template rewrites and re-testing, for a fidelity gain that's mostly
imperceptible to end users.
