# RUNBOOK — how to run this series with your agent

8 prompts. Run them **in order**. Do not skip, do not parallelise — each builds on the last.

---

## Before you start

Two things must be true:

1. **The Signal Ocean decision is made** — you approved full publication. Recorded, no
   longer a blocker.
2. **Prompt 02 has an external dependency on your scraping agent** (Guinea, Brazil,
   bunker forward, grain). Prompts 06 and 07 cannot finish honestly until that reports back.
   You can run 01 and 03–05 while that work happens.

---

## What to say, per prompt

Paste this each time, substituting the file:

> Read `docs/megaprompts/00-GUARDRAILS.md` in full, then read and execute
> `docs/megaprompts/<FILE>`.
>
> Work phase by phase. After **each** phase: write your ledger entries, run the phase
> verification, commit, then **STOP and wait for me**. Do not run two phases in one turn.
>
> If you cannot source a number, write null and record it. Never invent one. Never
> hardcode observation data. Never let an exception fall back to a literal.
>
> Everything you write in the ledger will be independently re-run in Prompt 08.

### Order

| # | File | Depends on | Notes |
|---|---|---|---|
| 1 | `01-foundation.md` | — | Do this first, completely. Everything else assumes it. |
| 2 | `02-data-purge-and-acquisition.md` | 01 | Where your scraping agent's findings land. |
| 3 | `03-signals.md` | 01, 02 | Strips Signals from 38 modules to ~15. |
| 4 | `04-broker-desk.md` | 01, 02, 03 | Receives 13 modules. |
| 5 | `05-tracking.md` | 01, 02, 03 | **Biggest single task.** Expect several sessions. |
| 6 | `06-bunkers.md` | 01, 02, 03 + Job C | Needs the bunker forward answer. |
| 7 | `07-cargo-trade-flows.md` | 01, 02, 03 + Jobs A/B/D | Needs Guinea + Brazil re-sourced. |
| 8 | `09-remaining-data-coverage.md` | 01–07 | **Run this BEFORE 08.** Assigns the 15 orphaned datasets, produces the coverage census and gap report. |
| 9 | `08-verification.md` | all incl. 09 | Run in a **fresh session** — see below. |

Note the numbering: `09` runs **before** `08`. The verification pass has to be last, and it
was written before the coverage gap was found.

---

## Running Prompt 08 correctly

Start a **new conversation** for it. If the same session that built also verifies, it will
confirm its own claims from memory rather than re-running them. A cold agent with only the
ledger and the repo is what you want.

Say:

> You are auditing work you did not do. Read `docs/megaprompts/00-GUARDRAILS.md`, then
> execute `docs/megaprompts/08-verification.md`. Assume every claim in the LEDGER files is
> a hypothesis until you have personally re-run its verify command. A verification that
> finds problems is a good verification.

---

## How to spot the agent drifting

Watch for these. They are the tells that preceded the last fabrication:

- **A phase completes suspiciously fast** with a large claimed scope.
- **Ledger entries with no `VERIFY COMMAND`**, or commands that can't fail
  (`ls` instead of a grep with an expected count).
- **The word "verified" / "authentic" / "genuine"** in new code or docstrings. Ask what
  network call backs it.
- **No `SKIPPED` or `BLOCKED` entries anywhere.** Real work of this size produces some.
  A perfect ledger is a warning sign, not a good sign.
- **A new `*_HISTORICAL` / `*_KT` / `*_MT` constant** appearing in a script.
- **A chart that suddenly has complete history** where the source was known to be patchy.

If you see any of these, the single most useful question is:

> Show me the exact network call that produced this number, and the raw response.

---

## Quick manual spot-checks

Run these yourself between phases — no agent involved:

```bash
# any new hardcoded year-keyed dicts?
grep -rnE "^\s*(19|20)[0-9]{2}: \{[0-9]+:" scripts/ bunker_pipeline/

# numbers transcribed from images?
grep -rniE "image [0-9]|green line|blue line|navy|read off|from the chart" scripts/

# silent literal fallbacks?
grep -rnE "if [a-z_]+ else -?[0-9]+\.[0-9]+" scripts/

# is anything quarantined still reachable from the UI?
grep -n "_quarantine" index.html

# text under 11px (paste in browser console) — must be 0
# [...document.querySelectorAll('*')].filter(e=>e.innerText&&!e.children.length&&parseFloat(getComputedStyle(e).fontSize)<11).length
```

---

## Decisions already locked (do not let the agent reopen these)

| Decision | Ruling |
|---|---|
| Signal Ocean data | **Publish fully** |
| Signals duplicate modules | **Delete**, do not keep both |
| Cargo & Trade Flows tab | **Approved**, sits between Tracking and Bunkers |
| Ton-Mile Absorption Simulator | **Deleted** — circular output, fabricated input |
| Guinea / Brazil envelope / freight-driver CSVs | **Quarantined**, never reconstructed |
| Type floor | **11px**, 7-step scale |
| Tooltip standard | **Intelligence tab pattern**, all rewritten |
| `data/views/` build artifacts | **Approved**, committed to repo |
| Untouched tabs | Dashboard, Yearly, Seasonality, Indices, ETFs, Intelligence, Offshore |
| PDF processing / knowledge graph | **Out of scope** for this entire series |

---

---

## ROUND 2 — after prompts 01–09 shipped (HEAD `3820c1a47`)

An independent audit of the shipped work produced four more prompts. **Run them in this
order — the numbering is not the running order:**

| Run | File | Why this order |
|---|---|---|
| 1st | `13-scraper-targets.md` | ✅ **Done** (2026-09-11). Get the data first. Target 1 alone (one URL parameter) unlocked 28 years of C3 and 27 of C5. (BDI was already held from 1985 — Fearnpulse is cross-validation only.) |
| 1b | `13B-prompt13-corrections.md` | ✅ **Done** (2026-09-11, HEAD `637bc180a`). Fixed fabricated Pilbara rows, dead Guinea citations, the Comtrade parser bug, the fleet table, the taxonomy test and the detector allowlist. |
| 1c | `13C-prompt13B-followups.md` | ✅ **Done** (2026-09-11, staged, uncommitted). Full suite 249 green; S4A/S4B, Guinea, Brazil gaps fixed. |
| **1d** | **`14-ship-round2-to-screen.md`** | **Run next.** Round 2's seven new datasets are on disk but **none are on screen**. Puts them into Cargo and Broker Desk, loads Hedland, gets China customs tonnage, and removes the synthesized port queues and the bunker port swap. (Replaces the withdrawn 13D, which was mostly audit hygiene with nothing visible.) |
| 2nd | `10-data-currency-and-truth-in-labelling.md` | Adds computed `data_through` / `staleness_state`, which is what makes Target 1's gains measurable and stops "LIVE" meaning "we ran the script". |
| 3rd | `12-tooltips-and-view-layer.md` | Finishes the two half-built systems. |
| — | `11-acquisition-round-2.md` | **Mostly superseded by 13.** Only Job B (Brazil) and Job F (minor bulks) remain, and both are folded into 13 as Targets 11 and 10. Skip unless you want the redundancy. |

Known corrections carried into those prompts, so the agent does not re-inherit them:
- Fearnleys tsIds **1, 2, 3, 5, 6, 7, 8, 9 are dead since 2023-05-22**; tsId 4 is alive.
  Earlier specs wrongly said the tanker columns run 2018→2026.
- The Barchart suggestion for C3 history is **retracted** — the cited symbol is an expired
  contract and the site is bot-protected. Fearnpulse supersedes it.
- `signal_map_ports_master.json` is byte-identical to the LNG file (silent fetch failure).
- Row counts in all prompts are 2026-09-10 snapshots; re-measure, never hardcode.

---

## Starting a fresh agent that only knows the repo

If your agent has general familiarity with the repo but has not seen this work, give it
this once, at the start:

> This repo is getting a structured rebuild. The full specification is in
> `docs/megaprompts/`. Read `00-GUARDRAILS.md` and `RUNBOOK.md` now, and confirm you
> understand the anti-fabrication rules and the phase-stop protocol. Do not start any
> work yet — I will hand you one prompt file at a time.

Then hand it `01-foundation.md` and nothing else.

**Do not tell it to read everything and run continuously.** Three reasons:
1. Nine prompts is far more than fits usefully in one context — quality collapses partway
   through and it starts summarising instead of doing.
2. The phase stops are the control mechanism. An agent running unattended for nine prompts
   is exactly the condition under which the last fabrication happened.
3. Prompts 06 and 07 are blocked on your scraping agent. An agent running straight through
   will invent its way past the block rather than wait.

## Final architecture

```
DASHBOARD · YEARLY · SEASONALITY · INDICES · ETFS      ← untouched
SIGNALS          what the market is pricing, and how stretched
BROKER DESK      rates, fixtures, assets, S&P, newbuilding  ← the house standard
TRACKING         vessels, ports, chokepoints, routing
CARGO & TRADE    what physically moves, from where          ← NEW
BUNKERS          fuel economics, carbon, scrubber
INTELLIGENCE · OFFSHORE                                 ← untouched
```
