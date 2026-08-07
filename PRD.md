# OrbitGuard — Product Requirements & Overview (PRD)

*Living document. Last updated from the strategy pass on positioning + audience.*

---

## 1. One-line

**OrbitGuard is an open, transparent, reproducible reference implementation of an
autonomous orbital-conjunction-screening + collision-risk pipeline** — from a live
public satellite catalogue to a ranked, validated list of predicted close
approaches, with a learned risk model on top.

## 2. What it actually is (honest current state)

A working end-to-end system, public on GitHub + GitHub Pages:

- **Ingest** a live CelesTrak catalogue (~16k active objects) — dated TLE snapshots.
- **Propagate** every object with SGP4 onto one shared inertial frame.
- **Screen** the whole catalogue for close approaches with a KD-tree (verified
  equal to brute force), grouped into events across time.
- **Refine** each flag to a precise time-of-closest-approach + miss distance via the
  analytic close-approach solution (validated to <12 m vs. an independent search).
- **Rank** by a geometric risk *proxy* (closing speed / miss distance).
- **Visualize** on a live WebGL globe (in-browser SGP4 to the current instant,
  geo-accurate sub-points) + a data-dense operations console.
- **ML (Phase 3)** — gradient-boosted trees + a 1-D CNN trained on the ESA Kelvins
  Collision Avoidance Challenge CDM dataset to predict whether a conjunction
  escalates (PR-AUC 0.65, F2 0.65). Not yet wired to our own live events.
- **Validate** — a Methodology view recomputes the correctness claims from scratch.

## 3. The problem & why it matters

Low-Earth orbit holds tens of thousands of tracked objects and the count is
climbing fast. Operators need to know, days ahead, which pairs will pass
dangerously close so they can plan avoidance. That first-pass **screening** —
across the whole catalogue, fast, and turning a coarse flag into a trustworthy
number — is the problem OrbitGuard implements, end to end and in the open.

## 4. Market context (grounded)

Conjunction assessment is a real, growing industry — but it splits into layers,
and it matters which layer OrbitGuard is in.

| Layer | Who | Data | OrbitGuard's relation |
|---|---|---|---|
| **Operational, high-fidelity** | LeoLabs (Sapphire), Slingshot (CARA), COMSPOC, Kayhan (Satcat), ExoAnalytic, Kratos; US gov **TraCSS** (Office of Space Commerce) | Proprietary radar/optical tracks + operator ephemerides + **covariance** | **Not competing.** Life-of-mission decisions need covariance-based Pc + owned sensor data. |
| **Free first-pass screening** | **CelesTrak SOCRATES** (3×/day, all payloads vs full catalogue, 5 km TCA, 7-day lookahead) | Public **TLEs** | **This is OrbitGuard's layer** — a transparent, open re-implementation of exactly this. |
| **Open-source libraries** | poliastro, Orekit (low-level astrodynamics); SatGuard (SGP4 + Pc + CDM + Cesium) | Public | **Peers.** OrbitGuard differentiates on the ML-risk research angle + transparency, but currently *lags* on formal Pc. |

The SSA **software** market alone was ~$1.37B in 2025 (~65% of SSA spend). The
important nuance for us: even operators who buy that software **start from
TLE-based screening (SOCRATES-style) and then layer their own covariance** — so
free TLE screening is a genuine, used first stage, not a toy. OrbitGuard is a
credible, legible implementation of that first stage — it just must not overclaim
past it.

Sources: [SSA market](https://www.marketsandmarkets.com/Market-Reports/space-situational-awareness-market-150269456.html) ·
[TraCSS / Consolidated Pathfinder](https://space.commerce.gov/office-of-space-commerce-extends-tracss-consolidated-pathfinder/) ·
[CelesTrak SOCRATES](https://celestrak.org/SOCRATES/) · [poliastro](https://github.com/poliastro/poliastro).

## 5. Purpose

OrbitGuard exists to **demonstrate a complete, correct, and transparent autonomous
conjunction pipeline** — and to serve as the artifact that proves the builder can
take a hard, real-world systems + ML problem from raw data to a validated,
shippable product. Its value is **method, rigor, and reproducibility**, not
operational risk numbers.

## 6. Target audience

Confirmed direction: the people who judge the **method**, not those who *operate*
on the output.

1. **Technical reviewers** (college admissions, recruiters, mentors) — *primary.*
   Want to see an end-to-end system, honest validation, and a real ML result.
2. **Researchers & students** (astrodynamics + ML) — a reproducible baseline and a
   clean reference; the ESA Kelvins CNN work is a genuine contribution.
3. **Agency research / education arms** (e.g. the ESA teams behind the Kelvins
   challenge; NASA open-source SSA/education) — a legible open reference for R&D
   and outreach. *Not* their operational conjunction desks.

**Explicit non-audience:** operational satellite operators / agency ops making
maneuver decisions. We don't have covariance or owned sensor data; claiming this
audience *hurts* credibility with audience #1–3.

## 7. Positioning statement

> For **technical reviewers, researchers, and agency R&D/education teams** who need
> to understand and trust *how* orbital conjunction screening works, **OrbitGuard**
> is an **open, validated reference implementation** of a full screening + ML-risk
> pipeline. Unlike commercial SSA platforms (operational, closed, covariance-based)
> or bare astrodynamics libraries (no end-to-end product), OrbitGuard is a
> transparent, reproducible, end-to-end system whose correctness is shown, not
> asserted — with a learned risk model as its research frontier.

## 8. Principles

- **Transparency > polish.** Every number is reproducible; the method is visible.
- **Honesty about limits is a feature.** State the TLE/covariance gap plainly.
- **Validate, don't assert.** Independent cross-checks in the product.
- **Reproducible by one command.** Anyone can rerun and get the same result.

---

## 9. Gap analysis — where we're misaligned with purpose + audience

Ordered by how much a knowledgeable reviewer/researcher would care.

1. **No formal probability of collision (Pc).** *(Biggest gap.)* We rank by a
   geometric proxy. A credible conjunction reference is expected to compute a real
   Pc (Foster 2D / Chan / Alfano) from covariance. TLEs lack covariance, but the
   standard, honest move is to compute Pc under a *stated assumed* covariance +
   hard-body radius. This is exactly what peers (SatGuard) and SOCRATES do, and it
   also gives the ML model a physically meaningful target to connect to.
2. **No external / physical validation.** We validate the *math* (vs. our own
   ground truth) but not the *physics* against an authoritative source. A SOCRATES
   cross-check turns "our math is right" into "and it agrees with the reference."
3. **ML not connected to our own catalogue.** The Kelvins model is impressive but
   scores Kelvins CDMs, not OrbitGuard's live events — so a visitor can't see the
   ML "do anything" on the globe. Phase 4.
4. **Hosted site data can go stale.** The globe propagates live, but from TLEs
   baked in at the last pipeline run. Client-side TLE fetch keeps it always-current.
5. **Discoverability / narrative.** No top-level quickstart, methodology writeup, or
   "why this is hard" framing aimed at the reviewer audience.

---

## 10. Plan

### P0 — Credibility (do first)
- **P0.1 · Real Pc.** Implement Foster's 2D Pc (add Chan/Alfano as cross-checks) in
  a new `risk_pc.py`, using a documented assumed covariance + hard-body radius.
  Surface Pc alongside the proxy in the report, globe, and table; document the
  assumptions on the Methodology page. *This is the single highest-leverage change.*
- **P0.2 · Live TLE fetch.** Fetch current TLEs client-side from CelesTrak so the
  hosted globe is always current (graceful fallback to the baked snapshot offline).

### P1 — Trust & the ML payoff
- **P1.1 · SOCRATES validation.** Pull a few current SOCRATES conjunctions,
  reproduce them, and show the agreement (order-of-magnitude) in the Methodology
  view — physical validation against the authoritative source.
- **P1.2 · Phase 4: ML on live events.** Build the `features.bridge_from_screener`
  path: derive the CDM-like features our screener *can* produce (geometry + assumed
  covariance from P0.1), score live conjunctions with the trained model, and show a
  learned risk on the globe — clearly labeled as a research demonstration.

### P2 — Reach & polish
- **P2.1 · Methodology writeup** (short doc/blog): the problem, the pipeline, the
  validation, the ML head-to-head, and honest limits. The reviewer-facing narrative.
- **P2.2 · Repro polish:** top-level README quickstart, one-command repro, test/CI
  badge, tagged releases.
- **P2.3 · UX niceties:** light theme, accessibility, the pipeline-row layout nit.

### Non-goals (explicit)
- Operational conjunction assessment / maneuver planning / alerting-as-a-service.
- Competing with commercial SSA or replacing SOCRATES/TraCSS.
- Proprietary sensor data or covariance we don't have.

---

## 11. Success metrics (for *this* audience)

- **Reproducibility:** a stranger can `git clone` + run and reproduce every number.
- **Validation depth:** screening = brute force; refinement < ~15 m; **Pc agrees
  with SOCRATES order-of-magnitude** (after P1.1).
- **ML result stands up:** honest CV metrics, beatable baseline, documented.
- **Legibility:** a non-expert reviewer understands what/why/how in ~60 seconds.
- **External signal:** GitHub stars/forks, a citation or classroom use, or its role
  in an admissions/portfolio outcome.

## 12. Open questions

- How much covariance realism to assume for Pc (single default vs. per-object by
  object type / size)?
- Is a "watch my satellite" workflow worth building for the small-operator adjacency,
  or does it pull us toward the non-audience?
- Space-Track integration (higher fidelity) — worth the auth complexity for this
  audience, or a distraction from the reference-implementation goal?
