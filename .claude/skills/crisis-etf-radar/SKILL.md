---
name: crisis-etf-radar
description: Scans the news for developing crises (war and chokepoints, weather and climate, elections and policy shocks, pandemics, animal and crop disease, supply-chain breaks, corporate fraud and bankruptcies, credit bubbles, crashes and recessions) that are likely to turn out worse or last longer than markets price. It scores each crisis, maps it to the ETFs, ETCs and equity sectors it affects and in which direction, judges whether months of impact are still ahead, and drafts the order shape and exit conditions. Use it whenever the user asks what a crisis or news story means for ETFs or sectors, wants a crisis or opportunity scan, asks whether it is too late to get in, wants entry or exit rules for a crisis trade, or wants to review an open crisis position. Use it even if they only name an event or a ticker and ask "is there something here?"
---

# Crisis → ETF radar

Find crises the market is underpricing, work out which instruments they move and for how long, and turn that into a concrete order with pre-committed exits.

This is a research aid. It deals in probabilities, not certainties. Every output says it is not financial advice. The user decides and places the trade.

## Why this works at all (the one-paragraph theory)

Markets usually price the *first* move of a crisis quickly. They are slow on three things:
1. news that arrives in small, steady drips rather than one big jump (Da–Gurun–Warachka, "frog in the pan");
2. second-order links, such as suppliers, customers and substitutes (Cohen–Frazzini; Barrot–Sauvagnat);
3. structural fragility, where buffers drain quietly until they run out (critical slowing down, Scheffer et al. 2009).

Commodity and sector trends then tend to persist for 1–12 months and partly reverse afterwards (time-series momentum, Moskowitz–Ooi–Pedersen 2012). So the edge, when there is one, is:
- spot a crisis whose *mechanism* points to "worse or longer than priced" while it is still in the drip phase;
- ride the trend with pre-set exits;
- leave before the late-phase signs (front-page attention, record ETF inflows, repair of supply) take over.

## Files in this skill

| File | Read it when |
|---|---|
| `references/family-playbooks.md` | Always for Stages 3–5. It holds per-family signals, hallmarks, blind spots, instruments, analogues and scan queries, plus the cross-cutting patterns: conflict escalation and termination, structural fragility, financed booms, fraud and timing. |
| `references/signals-and-scoring.md` | Stage 4 (quantify) and Stage 6 (timing). It holds base rates, likelihood ratios, the timing table and the formulas. |
| `references/orders-and-exits.md` | Stage 7, and every time in Review mode. It covers instrument checks, entry, sizing, exits and monitoring. |
| `references/data-sources.md` | Stage 1, or when a signal needs a data series. |
| `references/example-setup-card.md` | Once, to see what a finished card looks like. It is a worked Hormuz/tanker example dated Oct 2026; don't reuse its facts. |
| `scripts/signals.py` | Run it for numbers rather than estimating in prose. Subcommands: `ews`, `trend`, `doubling`, `bayes`, `size`, `brier`. Run `python scripts/signals.py -h`. |

## Modes

Pick the mode from the request. If unsure, use Assess for a named event and Scan otherwise.

- **Scan:** "what crises should I watch?" or "anything brewing?". Run Stages 1–2 broadly. Give a ranked shortlist of 3–5 candidates, each with one line saying why it might be underpriced. Then run Stages 3–7 on the top one or two only. Breadth first, depth on the best.
- **Assess:** the user names an event, region, commodity or ETF. Skip the broad scan. Run Stages 1–7 on that crisis and produce the full setup card.
- **Review:** the user holds, or is about to hold, a crisis position. Re-check the thesis-break facts, the timing table and every exit condition in the card. Answer with one of hold, add, trim or exit, plus the triggering evidence. Also update the log entry. If the original card isn't in the conversation, ask for it or rebuild it from the user's entry details.

## User profile (ask once, then remember for the conversation)

Before the first order shape, ask in one AskUserQuestion call, unless already known:
1. which instruments are allowed: UCITS ETFs only; plus ETCs/ETNs; plus single stocks; plus short or inverse products;
2. the risk budget per idea, as the % of portfolio lost if the stop hits (offer 0.5% / 1% / 2%);
3. the cap on the whole crisis book, as a % of the portfolio (offer 5% / 10% / 20%);
4. the broker or venue, if the etf-venue-check skill is unavailable.

**Defaults when unattended, or if the user skips:**
- EU retail investor in Germany, subject to PRIIPs;
- long-only UCITS ETFs, ETCs and single stocks, with no leverage or inverse products;
- risk per idea of 0.75% of the portfolio, and a crisis book capped at 10%;
- sizing shown as a formula, so the user can plug in their own numbers.

State the defaults used at the top of the card.

## The pipeline

### Stage 1: Scan

Goal: a raw list of candidate crises, each with dated sources.

- Run WebSearch across the families with the scan queries in `references/family-playbooks.md`. Send several searches in the same turn.
- Prefer the **specialist trade press** and primary sources (shipping, ag, energy, epidemiology and credit desks, regulators, central banks) over general news. Specialists report the drip; mainstream press reports the splash. A topic covered by specialists but not yet by mainstream outlets is itself a signal.
- Measure change **against the place's or market's own baseline**, not in absolute terms. A small rise in event counts somewhere usually quiet matters more than a large count in a chronic hotspot (Mueller–Rauh). Tag each candidate as a **chronic hotspot** or a **new onset**. New onsets are harder to predict, so lower your confidence.
- Pull hard data where it exists (see `references/data-sources.md`): freight indices, futures curves, inventories, case counts, credit spreads, port calls, GPR/EPU indices.
  - Save any series you will analyse to a CSV in the working directory.
  - Run `scripts/signals.py` on it rather than eyeballing it.

### Stage 2: Sift

Score each candidate from 0 to 2 on six screens and keep those scoring ≥7 of 12 for the deep dive.

| Screen | 0 | 1 | 2 |
|---|---|---|---|
| Novelty against own baseline | chronic, unchanged | elevated | sharp break from baseline |
| Threat vs act stage (Caldara–Iacoviello) | resolved or receding | acts happening, threats fading | threats escalating, or acts escalating beyond threats |
| Information arrival | one big jump, fully reported | mixed | small, steady, same-direction drips |
| Attention gap | front page, retail-flow spike | some mainstream coverage | mostly specialist or local press |
| Link complexity | direct, obvious exposure only | one hop to suppliers or customers | multi-hop or substitute effects few people are modelling |
| Buffer state | ample, being rebuilt | draining | thin, draining and no repair in sight |

This screen is a heuristic and not calibrated. It decides only where to spend research time; the probability work happens in Stage 4.

Tag each survivor with its **family**, using the playbooks. Use several tags if needed, such as conflict + supply chain.

### Stage 3: Situational awareness

For each survivor, build a short dated fact base with:
- actors and their incentives;
- the physical or financial mechanism;
- buffers (inventories, spare capacity, alternative routes, fiscal room, capital);
- what has happened, and what is scheduled to happen (catalysts).

Then run two checklists from `references/family-playbooks.md`:
- **Hallmarks of "worse or longer than priced"**: the family-specific list plus the cross-cutting ones (structural fragility, financed booms, escalation traps, fraud red flags).
- **Counter-signals**: ripeness and convergence in conflicts, buffers being rebuilt, policy repair rather than relief, the substitute route actually working, the market already pricing the extreme case.

Keep facts and inferences visibly separate. Mark each item with a date and a source. A hallmark that rests on a single source counts as half.

### Stage 4: Quantify

Do this in order. The method is outside view first (the Good Judgment approach), then updates.

1. **Define the question so it can be resolved.**
   - Example: "Will VLCC Middle-East→China rates still be above $X/day on DATE?"
   - Example: "Will the outbreak reach N countries by DATE?"
   - The question must contrast with what the market prices. Find what is priced: the futures curve, options-implied moves, analyst consensus, central-bank pricing, and what the instrument's manager says they expect.
2. **Base rate** from the nearest analogue class, using the table in `references/signals-and-scoring.md`. State the reference class.
3. **Update with likelihood ratios** for each hallmark or counter-signal present, using the default strengths in the reference file.
   - Count correlated signals once.
   - Cap the combined update at ×10 either way.
   - Compute with `python scripts/signals.py bayes --prior P --lr ...`.
4. **Fermi-size the impact.** Use a decomposition such as lost volume × price elasticity × duration. Classify the shock with Kilian's types (supply, aggregate demand, precautionary demand), because each implies a different persistence and set of winners.
5. **Early-warning statistics.** Where a relevant series exists (freight, spreads, case counts, prices), run `python scripts/signals.py ews data.csv`. Rising variance, autocorrelation and skew add only a weak-to-moderate likelihood ratio, never proof. For outbreaks, run `doubling`.

Output: the posterior probability that the crisis is worse or longer than priced, plus the expected move in the main instrument if right and if wrong.

### Stage 5: Map to instruments

Build the instrument ladder from the family playbook. For each rung, give the direction (↑ or ↓) and the mechanism in one line:
1. **Direct:** the commodity, freight rate or asset itself, via an ETC, an ETF or the nearest liquid proxy.
2. **Sector:** the equity sector ETFs on the front line, both winners and losers.
3. **Second-order:** suppliers, customers, substitutes, and the regions most exposed. This is where underreaction is largest.
4. **Losers and hedges:** what gets hurt, and anything that protects the user's existing core portfolio.

Then run the **availability and mechanics checks** in `references/orders-and-exits.md` on every instrument you might recommend:
- UCITS/KID status, since US-domiciled ETFs are not buyable by EU retail;
- domicile, replication, AUM and closure risk;
- spread and premium to iNAV;
- roll yield or contango for futures-based ETCs;
- daily-reset decay for leveraged or inverse products;
- currency and its hedging.

Look the numbers up and date them. Never state AUM, TER, ISIN or spreads from memory. If no suitable UCITS product exists, say so and offer the nearest alternatives:
- the broader sector;
- single stocks, which EU retail can buy even when US-listed;
- an ETC on the underlying.

If the etf-venue-check skill is available, hand the final shortlist to it for venue, costs and trading window. Otherwise apply its basics: limit orders, liquid hours, and the 15:30–17:30 CET overlap for US-underlying products.

### Stage 6: Timing (is it still early enough for months?)

Fill in the timing table in `references/signals-and-scoring.md`. It has 12 rows (price move vs analogue, time since onset, attention, ETF flows, futures curve, positioning, buffers, policy response, resolution signals, trend age, vol regime, catalyst), and each row reads **early**, **neutral** or **late**. Use `python scripts/signals.py trend prices.csv` for the trend, run-up and volatility rows.

| Reading | Verdict |
|---|---|
| ≥3 rows early and 0 rows late | **Months likely**: full setup. |
| 1–2 rows late | **Weeks to a few months**: smaller size, tighter exits, scale out early. |
| ≥3 rows late | **Too late to chase**. Either pass, or flag a possible fade only if a public catalyst is identified. |

The catalyst row works differently. A contrarian thesis (the market is wrong *against* a popular view, or a fraud) needs a dated, public catalyst that would force recognition: an audit, a court date, an OPEC meeting, an inventory report, an election. Without one, mark it "right but unpaid risk" and size down or pass. Being right too early is indistinguishable from being wrong (Shleifer–Vishny; Abreu–Brunnermeier; the Wirecard case).

### Stage 7: Order shape and exits

Use `references/orders-and-exits.md`. It covers products, entry, sizing, exits and monitoring. The card must contain:
- **Setup type:** trend-following (riding persistence) or mean-reversion/contrarian. This decides whether price stops are used. Stops help in trending markets and hurt in mean-reverting ones (Kaminski–Lo 2014).
- **Entry:**
  - the trigger;
  - order type, which is always a limit order near iNAV for ETFs and ETCs;
  - tranches, such as ⅓ now, ⅓ on confirmation, ⅓ on pullback or second confirmation;
  - the venue and time window.
- **Size**, from `python scripts/signals.py size ...`: risk budget ÷ stop distance, capped by a volatility budget and by quarter-Kelly. Show which constraint binds.
- **Exit conditions**, all written in advance:
  - (a) thesis-break facts: named, observable events that mean the mechanism has stopped, especially *repair* rather than relief;
  - (b) a price stop, for trend setups only, set as a volatility-width trailing stop;
  - (c) a time stop of 12 months or less;
  - (d) late-phase scale-out triggers;
  - (e) a volatility rule;
  - (f) product exits, such as fund closure, a premium blow-out or KID withdrawal.
- **Watch list:** each indicator with its threshold, source and check cadence.

## Output: the setup card

Use this exact structure. Keep it tight. Put tables where the reader compares, and sentences elsewhere.

```
# [Crisis] — setup card (as of YYYY-MM-DD)
Not financial advice. Facts dated; inferences marked (inference). Profile: [defaults or user's].

**Verdict:** [Pass | Watch | Starter | Full setup] — one sentence why.
**Thesis:** [Instrument] will move [↑/↓] because [mechanism] makes [crisis] worse/longer than the [priced expectation] implies.
**Family / tags:** … | **Phase:** threat / act / drip / splash / repair

## What's priced vs what we expect
- Priced: … (curve, options, consensus — with sources)
- Our view: P(worse/longer than priced) = X% (base rate Y% from [class] → updates [list with LRs])
- If right: ~+A% over N months; if wrong: ~−B% (stop)

## Instruments
| Rung | Instrument (ISIN/ticker) | Dir | Mechanism | Access (UCITS/KID) | AUM · spread · roll | Use? |

## Timing — [Months likely | Weeks–months | Too late]
| Row | Reading | Evidence |

## Order shape
- Setup type: trend / contrarian → stop policy
- Entry: trigger · limit order rule · tranches · venue/window
- Size: formula and worked example → binding constraint
## Exit conditions (pre-committed)
- Thesis-break facts: …
- Price stop: … (or "none — contrarian; using time/thesis stops")
- Time stop: … | Scale-out: … | Vol rule: … | Product exits: …
## Watch list
| Indicator | Threshold | Source | Cadence |
## What would change my mind
## Log line
date,crisis,instrument,direction,question,p,resolve_by,outcome
## Sources
```

In Scan mode, give the ranked shortlist first, with one row per candidate showing family, sift score, one-line thesis and the main instrument. Then give full cards for the top one or two.

## Logging and calibration

End every card with a CSV log line containing the resolvable question, the probability and the resolve-by date. The user keeps the log; this workspace doesn't persist between sessions. When the user brings back resolved entries, run `python scripts/signals.py brier log.csv` and report the calibration. The likelihood-ratio defaults are uncalibrated starting points, and the log is how they get tuned.

## Guardrails

- **Look up, don't recall.** Prices, AUM, ISINs, TERs, spreads, availability and the latest news must be fetched and dated each time. Anything from memory is labelled as such.
- **Separate fact from inference** everywhere. When evidence is thin, say so and lower the probability. Don't fill gaps with confident prose.
- **No single-source theses.** A thesis needs at least two independent sources for its key facts.
- **Products:**
  - Never recommend daily-reset leveraged or inverse ETPs for holds longer than a few days.
  - Never recommend shorting to a retail user unless they have enabled it in their profile.
  - Note the Daniel–Moskowitz rebound risk for any short or loser leg after a big market fall.
- **Respect PRIIPs.** Don't route the user to US-domiciled ETFs. Offer UCITS products, ETCs or single stocks instead.
- **Keep the user's core portfolio first.** Crisis trades are a satellite and stay within the crisis-book cap. Flag when a new idea correlates with ones the user already holds, because several crisis trades can be one bet.
- **German tax pointers**, flagged as needing confirmation with a tax adviser:
  - equity funds with ≥51% equity get 30% partial exemption (Teilfreistellung);
  - ETCs are not funds and get none;
  - single-stock losses offset only single-stock gains.
- **Hard limits.** No market manipulation, no trading on non-public information, and no help profiting from facilitating harm. Covering events that involve human suffering is legitimate; the card stays factual and sober.
