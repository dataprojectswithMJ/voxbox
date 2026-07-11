# Build Doc — Consentic (AMD Developer Hackathon: Act II)

Stack: **FastAPI (single service) + server-rendered/static HTML + vanilla JS.** No frontend framework, no build step, no bundler. This is a deliberate choice, not a shortcut — see "Why one service" below.

Guiding rule for every decision in this doc: **if it doesn't get us to a working, demoable safety loop, don't build it.** The judging criteria are creativity, product-market potential, completeness, and use of AMD platforms — none of those need a payments system or a login page.

---

## 1. Architecture (single glance)

```
Browser (HTML/CSS/vanilla JS, no build step)
        │  fetch() JSON calls
        ▼
FastAPI app  ──────────────► Fireworks API (Gemma) — script screening + daily report
   │
   ├── SQLite (vault.db)  — actors, voices, rentals, verdicts, ledger
   └── Chatterbox TTS (in-process, loaded once at startup) ── runs on AMD MI300X / ROCm
```

One process. One container. One GPU. That's the whole system.

### Why one service, not microservices
Splitting the TTS renderer into its own service is the "correct" production architecture, but it buys you nothing in a timed hackathon except an extra container, an extra network hop, and an extra thing that can fail during the demo. FastAPI can run the blocking Chatterbox call in a threadpool (`run_in_threadpool`) so it doesn't block other requests. Note this tradeoff explicitly in your README as a "next step for production" — judges read that as maturity, not laziness.

---

## 2. Build order, and why this order specifically

The riskiest unknown in this whole project is **not** the business logic — it's whether Chatterbox runs cleanly on ROCm on your first try. Business logic is fully within your control and predictable to estimate. GPU/driver/library compatibility is not. De-risk the unknown first.

1. **GPU + model validation** (do this before writing a single route) — confirm Chatterbox loads and generates audio on the MI300X instance. If it fights you, you still have time to fall back to CPU inference for the demo or swap to Qwen3-TTS.
2. **Data model + vault** — everything else depends on having somewhere to write to.
3. **Recording + consent conditions** — the voice actor side; needed before anything can be rented.
4. **Rental request + Gemma screening + approval routing** — this is the actual pitch. Get it rock solid before touching styling.
5. **TTS generation wired to approval** — connects the safety loop to real audio output.
6. **Revenue ledger** — trivial once rentals exist; a few lines of arithmetic.
7. **Daily usage report** — nice-to-have, cheap once screening works, second visible Gemma use case.
8. **Frontend polish + Docker packaging** — last, because judges score a working demo over a pretty one.

---

## 3. Component matrix

| Component | Where | How | Why |
|---|---|---|---|
| **GPU/model check** | `scripts/check_gpu.py` (throwaway) | Load Chatterbox, run one `model.generate()` call, confirm `torch.cuda.is_available()` is `True` on ROCm | Validates the highest-risk unknown before you build on top of it |
| **Data model** | `app/db.py`, `app/models.py` | SQLite file (`vault.db`) via SQLModel or raw `sqlite3`. Tables: `actors`, `voices`, `rentals`, `ledger` | No external DB service to install, configure, or lose to a network blip mid-demo. A file you can literally open and show judges *is* the audit-trail story |
| **Mock auth** | `app/auth.py` | No passwords. A dropdown of 2–3 seeded personas (`actor_id` in a cookie or query param) | Real auth is a multi-hour sink that doesn't touch the pitch. You're demoing consent architecture, not an identity system |
| **Phrase issuance** | `POST /api/phrase` | Server returns a random phrase + nonce + timestamp, stored server-side against that request | Anchors the "you can't upload a pre-recorded voice" claim — the phrase didn't exist until you asked for it |
| **Voice recording** | `static/record.html` + `static/app.js` | Browser `MediaRecorder` API records against the issued phrase, uploads blob to `POST /api/voices` | Core to your differentiation claim: live capture, not file upload |
| **Consent conditions** | Part of `POST /api/voices` payload | Fixed checklist, not freeform text: `ads`, `political`, `adult`, `medical_claims`, `financial_advice`, `hate_violence`, `impersonation` | Freeform conditions are unparseable by an LLM reliably in the time you have. A fixed enum is checkable, both by Gemma and by a human glancing at the vault |
| **Voice listing** | `GET /api/voices`, `static/browse.html` | Simple table/grid render from JSON | Needed for a renter to pick a voice — don't over-design this page |
| **Rental + script submit** | `POST /api/rentals` | Stores script text, `voice_id`, `renter_id`, status `pending` | Entry point to the safety loop |
| **Script screening** | `app/screening.py` | Call Fireworks (`accounts/fireworks/models/<gemma-model-id>`) with the actor's declared conditions + script, force JSON output: `{flags: [...], matches_declared_condition: bool, verdict: "auto_approve" \| "auto_deny" \| "needs_review"}` | This *is* the pitch. Everything else supports this call |
| **Approval routing** | Same `POST /api/rentals` handler | `auto_deny` → rental rejected immediately. `needs_review` → status `pending_actor_review`, appears in actor's queue. `auto_approve` → proceeds to render | Encodes the "flagged but not covered by declared conditions → human decides" rule from your spec |
| **Actor review queue** | `GET /api/rentals?status=pending_actor_review`, `static/dashboard.html` | Actor sees script + flags, clicks Approve/Deny, hits `POST /api/rentals/{id}/decision` | The human-in-the-loop half of the safety story — don't skip building the UI for this, it's the part judges will want to see live |
| **Vault logging** | Insert-only rows on `rentals` (never `UPDATE`/`DELETE` exposed via API) | Every decision — auto or manual — writes `decided_by`, `verdict`, `timestamp` | "Immutable" doesn't need a blockchain here — it needs the app layer to simply never expose a delete/edit route |
| **TTS generation** | `app/tts.py`, called on approval | Chatterbox loaded once at app startup (`@app.on_event("startup")`), `generate(text, audio_prompt_path=voice.sample_path)` run via threadpool | Loading the model per-request would be far too slow for a live demo; load once, reuse |
| **Watermark** | Built into Chatterbox by default | Nothing extra to build | Free credibility point for your safety narrative — mention it explicitly in the pitch |
| **Revenue ledger** | `app/models.py` `ledger` table, computed on approval | `gross = rate * (word_count/100)`, `platform_cut = gross * fee_pct`, `actor_cut = gross - platform_cut` | Matches the pricing page; trivial arithmetic, don't overbuild with a payments provider |
| **Daily usage report** | `POST /api/admin/report` (manually triggered, not a real cron) | Aggregate script categories/flags from the vault, send to Gemma to summarize into a short paragraph + counts | Second distinct Gemma use case for the pitch; "manually triggered" is fine for a demo — you don't need a scheduler |
| **Frontend pages** | `static/*.html` + one `static/app.js` | Plain HTML forms, `fetch()` to the API, template literals to render JSON into the DOM | No React, no build step, no npm install failing on you at 3am |

---

## 4. Explicit cut list — do not build these

| Cut | Why |
|---|---|
| Real payment processing (Stripe, etc.) | The ledger numbers prove the model works; wiring real money moves zero points and burns hours |
| Real user auth / OAuth / password reset | Mock personas demonstrate the flow just as well |
| Multi-GPU / horizontal scaling | One MI300X, one demo audience. Note it as a production roadmap item instead |
| Real liveness/anti-deepfake detection | Full spoof-detection is a research problem. A server-issued phrase + nonce is a reasonable MVP signal — say so honestly in your pitch rather than overclaiming |
| Multi-language TTS | Stick to Chatterbox/English unless there's slack time on day 2. Mention Qwen3-TTS multilingual support as roadmap, don't build it under time pressure |
| Email/SMS notifications | An in-app pending queue the actor checks is enough for a demo |
| Admin analytics dashboard | The daily report endpoint returning readable JSON/text is enough — don't build charts nobody asked for |
| A real cron scheduler | A button that triggers report generation on demand works fine live |

---

## 5. File structure

```
consentic/
├── app/
│   ├── main.py          # FastAPI app, route registration, startup model load
│   ├── db.py             # SQLite connection/session setup
│   ├── models.py         # actors, voices, rentals, ledger
│   ├── auth.py            # mock persona selection
│   ├── screening.py       # Fireworks/Gemma call + JSON schema
│   ├── tts.py              # Chatterbox load + generate wrapper
│   └── reports.py          # daily usage report generation
├── static/
│   ├── index.html          # links to record/browse/dashboard (or reuse the pitch page)
│   ├── record.html         # phrase + MediaRecorder flow
│   ├── browse.html         # voice listing + rental submission
│   ├── dashboard.html      # actor's pending-review queue
│   ├── styles.css
│   └── app.js
├── vault.db                 # created at runtime, gitignored
├── Dockerfile
├── requirements.txt
├── .env.example              # FIREWORKS_API_KEY, etc.
└── README.md
```

---

## 6. Environment checklist

- `FIREWORKS_API_KEY` — from your hackathon $50 credit
- AMD Developer Cloud instance up, PyTorch/ROCm Quick Start image, `chatterbox-tts` installed
- `pip install fastapi uvicorn python-multipart sqlmodel chatterbox-tts httpx`
- One `Dockerfile` (single stage is fine — this doesn't need multi-stage optimization for a hackathon submission, just needs to build and run)

---

## 7. Demo script (once built)

1. Record a voice live against an issued phrase, set conditions, set a price.
2. Submit a clean script as a renter → watch it auto-approve and render.
3. Submit a script that trips an undeclared flag → show it land in the actor's review queue → approve it live.
4. Show the vault row for both — same data, different `decided_by`.
5. Show the ledger split.
6. Trigger the daily report, show Gemma's summary of usage patterns.

That's the whole story, and it's the whole app. Nothing in this doc exists that isn't on that list.
