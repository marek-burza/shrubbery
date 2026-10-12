# Worked example: Hormuz tanker-freight card (as of 2026-10-10)

> **This example is time-bound.** It shows the *shape and reasoning* of a finished card. Don't reuse its facts; re-fetch everything for a live run. It was produced as the dry run of this skill.

---

# Strait of Hormuz disruption → tanker freight: setup card (as of 2026-10-10)

Not financial advice. Facts are dated; inferences are marked (inference). The profile uses the defaults: EU retail investor in Germany; long-only UCITS ETFs, ETCs and stocks; 0.75% risk per idea; a 10% crisis book.

**Verdict:** **Pass on a new long; scale out any existing tanker exposure.** The mechanism is real, but the trade is late: 6 of 12 timing rows read late, and at a fair probability the edge is negative.

**Thesis tested:** tanker freight (BWET, or tanker equities) keeps rising because the Hormuz disruption lasts longer than priced.

**Family / tags:**
- B1 conflict/chokepoint;
- A1.1 the substitute shares the risk;
- A1.3 relief is not repair.

**Phase:** acts escalating again, after a failed relief deal.

## Fact base (dated)
- **The war began at the end of Feb 2026.**
  - The Islamabad MoU of 17 Jun opened a 60-day safe-passage window.
  - Iran resumed attacks on 6–7 Jul, and the US declared the ceasefire over on 8 Jul (Hellenic Shipping News / Signal Ocean).
- **September 2026:** at least 477 non-Iranian-linked transits, the most since the war began. Yet there were at least 13 attacks on tankers and gas carriers from 28 Sep, a seven-month high. The JMIC threat level is "severe", and the US blockade of Iranian ports continues (Lloyd's List Intelligence, 8 Oct).
- **Global crude export volumes are back near pre-crisis levels** through costly shuttle workarounds. Crude exports are concentrated among a few operators (LLI, 8 Oct).
- **TD3C (MEG→China) at WS372, about $369k/day TCE**, up week on week (Hellenic Shipping News, undated weekly report from early Oct).
- **A reported VLCC record of about $860k/day on 10 Sep.** The BWET manager expects rates to fall if the strait reopens. Both points come from the "September 2026" essay (user-supplied); the route isn't specified, so verify.
- **BWET:**
  - AUM was $8.5m on 16 Feb 2026 (MarketBeat via Nasdaq) and **$246.8m on 7 Oct 2026**, about 29× higher;
  - the 1-month return was about +90% (P&I ETF page, 7 Oct);
  - the expense ratio is 3.5%;
  - it holds VLCC-weighted freight futures 1–6 months forward.
- **Political news, 4–8 Oct:**
  - Iran's negotiator said Hormuz stays closed (4 Oct);
  - Iran's oil minister resigned (4 Oct);
  - the IRGC turned back a tanker (5 Oct);
  - the US President showed a chart claiming flows are back (8 Oct).

  These were gathered in the original research session; re-verify them.

## What's priced vs what we expect
- **Priced:** the freight forward (FFA) curve is a **data gap**. Baltic FFA quotes are paid, so check BWET's holdings page for the contract months and prices. Indirectly, BWET's +90% month says forwards have repriced sharply upward (inference).
- **Question:** will TD3C TCE still be above $200k/day on 2027-01-31?
- **Prior:** 25%. Spot freight mean-reverts strongly at extremes (Adland & Cullinane 2006).
- **Updates:**

| Signal | LR |
|---|---|
| Attacks at a seven-month high, with JMIC "severe" (two sources) | ×1.6 |
| No face-saving exit, from the negotiator's statement (single source) | √1.6 |
| Crude volumes restored via workarounds | ×0.7 |
| VLCC availability rising | ×0.85 |
| Combined | ×1.20 |

- **Posterior: 29%** (`signals.py bayes`).
- **If right:** maybe +25% in tanker equities over 3–4 months. **If wrong:** −12% at the stop, and in practice more, given gap risk at extreme rates.

## Instruments
| Rung | Instrument | Dir | Mechanism | Access | Notes | Use? |
|---|---|---|---|---|---|---|
| Direct | BWET (freight futures) | ↑ | VLCC FFAs | **US-domiciled, no KID, so not available to EU retail** | 3.5% TER; AUM ×29 this year | No |
| Direct | Crude-tanker stocks (e.g., Frontline, DHT, Okeanis), as a 3–5 name basket | ↑ | spot exposure, ton-miles | single stocks, available | high beta to spot; check venue liquidity | Only if the timing resets |
| Sector | UCITS World/Europe energy ETFs | ↑ | oil price | UCITS | mostly integrated majors, so the crisis exposure is diluted | Not a freight proxy |
| Direct | Brent ETC | ↑ | supply risk | ETC | roll yield depends on the curve; check it | Separate thesis |
| Second-order | Gulf-exposed petrochemicals and fertilizer, Asian importers' equities | mixed | input and flow costs | various | **next to assess**, since there may be less attention there | Run Stages 3–6 |

## Timing: **Too late to chase** (6 late, 2 early)
| Row | Reading | Evidence |
|---|---|---|
| 1 Move vs analogue | L | spot is far above the 2019 and 2020 tanker spikes |
| 2 Time since onset | L | 7.5 months, against analogue spikes lasting weeks to a few months |
| 3 Attention | L | mainstream "top-performing ETF" coverage since February |
| 4 ETF flows | L | BWET AUM ×29 in 8 months |
| 5 Curve | N | data gap |
| 6 Positioning | N | no COT data for FFAs |
| 7 Buffers | N | crude flows restored via costly workarounds; partial repair |
| 8 Policy | E | blockade continues; no repair deal |
| 9 Resolution | E | no ripeness: no valid spokesmen and no accepted formula; the MoU failed after 3 weeks |
| 10 Trend age | L | BWET's 12-month trend has been positive since 2025 |
| 11 Vol regime | L (likely) | +90% in one month; confirm with `signals.py trend` |
| 12 Catalyst | N | none dated; the next LLI brief is on 22 Oct |

## Order shape
- **Now:** none. The edge is negative at p = 0.29: `signals.py size … --p 0.29 --target 125` gives f* = −0.05, which means no trade.
- **Re-entry setup** (only if the timing resets: a pullback of 30% or more in tanker equities while attacks persist and no repair deal exists):
  - **Setup type:** trend, so a trailing stop applies.
  - **Instrument:** a basket of 3–5 crude-tanker stocks.
  - **Entry:** limit orders in the 15:30–17:30 CET window for US listings; the etf-venue-check skill covers the venue. Tranches of ⅓ / ⅓ / ⅓ on (1) a new escalation fact, (2) a close above the 50-day high, (3) a pullback to the 20-day average.
  - **Size** (illustration, with capital 100k, entry 100, ATR 4, k = 3, volatility 65%): the volatility cap gives about €3.1k, which binds before the risk budget (€6.25k).

## Exit conditions (for anyone already holding tanker exposure)
- **Thesis-break facts:**
  - (1) transits by transparent-ownership tonnage above 70% of the pre-war norm for 2 weeks;
  - (2) a signed deal with a third-party guarantor;
  - (3) war-risk premiums falling for 2 weeks;
  - (4) VLCC ballasters to the Gulf rising while TD3C falls (inference).
- **Price stop:** trailing, highest close − 3 × ATR(20), on a close basis. Use alerts plus manual limit orders rather than stop-market orders.
- **Scale-out:** ≥3 late rows are already present, so sell ⅔ now and let ⅓ ride the trailing stop.
- **Volatility rule:** if 20-day volatility exceeds 2× the volatility at entry, cut the position to restore the entry risk.
- **Time stop:** 2027-01-31.
- **Relief vs repair:** talks or announcements mean tighten the stop. Transits by mainstream owners mean exit.

## Watch list
| Indicator | Threshold | Source | Cadence |
|---|---|---|---|
| Non-Iranian transits per week | above ~200/week sustained (verify the pre-war baseline) | LLI brief, PortWatch | weekly |
| Attacks on merchant ships | zero for 2 weeks | LLI, UKMTO | weekly |
| TD3C TCE | below $150k/day | Hellenic Shipping News weekly | weekly |
| BWET AUM and flows | outflows after the peak | issuer site, P&I | weekly |
| Mediation | a named guarantor and a formula | wire services | daily headline check |

## What would change my mind
- A new escalation that hits the workaround itself (the shuttle routes or terminals), per A1.1.
- A demonstrated collapse of transits by mainstream owners. That would mean buffers are failing rather than being repaired, and the timing would reset.

## Log line
```
2026-10-10,Hormuz,TD3C,up,"TD3C TCE > $200k/day on 2027-01-31",0.29,2027-01-31,
```

## Sources
- [Lloyd's List Intelligence: Strait of Hormuz Brief, 8 Oct 2026](https://www.lloydslistintelligence.com/resources/blog/strait-of-hormuz-brief-8-october-2026)
- [Hellenic Shipping News: tanker count on both sides of Hormuz exceeds 700](https://www.hellenicshippingnews.com/?p=1141520)
- [Hellenic Shipping News: VLCC tanker rates on the rise](https://www.hellenicshippingnews.com/?p=1141383)
- [P&I ETF page: BWET (as of 7 Oct 2026)](https://etf.pionline.com/fund/BWET)
- [Nasdaq/MarketBeat: one of the top-performing ETFs of 2026 so far (16 Feb 2026)](https://www.nasdaq.com/articles/one-top-performing-etfs-2026-so-far-may-surprise-you)
- "September 2026" essay (user-supplied PDF)
