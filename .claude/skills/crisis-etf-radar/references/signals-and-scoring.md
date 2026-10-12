# Signals, base rates and scoring

Use this file in Stage 4 (quantify) and Stage 6 (timing). The likelihood ratios below are **uncalibrated defaults**. Treat them as starting points to be tuned from the user's log (Brier scores), and never as published constants unless a source is given.

## Contents
1. Method in one box
2. Base-rate table
3. Likelihood ratios: how strong is a signal?
4. Noise-to-signal ratio ↔ likelihood ratio
5. Shock typing and Fermi sizing
6. Early-warning statistics (critical slowing down)
7. Bubble and crash-risk markers
8. Timing table (12 rows)
9. Formulas

---

## 1. Method in one box

1. **Resolvable question:** what, by when, and with what threshold. It must contrast with what is priced.
2. **Outside view:** the base rate from the closest reference class (Section 2). If none fits, use a neutral prior of 20–30% for "worse or longer than priced". Markets are right more often than not, so start below 50%.
3. **Inside view:** multiply the prior odds by the likelihood ratio (LR) of each independent signal (Section 3). Count correlated signals once. Cap the total update at ×10 or ÷10.
4. **Sanity checks:**
   - Would a smart, well-informed trader already know this?
   - What does the futures curve or the options market say?
   - Over 70% needs hard, multi-source evidence.
5. **Size the impact** (Section 5) and check the timing (Section 8).

`python scripts/signals.py bayes --prior 0.25 --lr 2.5 1.6 0.7` does the arithmetic.

---

## 2. Base-rate table

| Reference class | Base rate / pattern | Source |
|---|---|---|
| Financial crisis in a country within 3 years | ~7% unconditionally. **~40%** when both credit growth and asset-price growth are in the top tercile. | Greenwood, Hanson, Shleifer & Sørensen (2022), "Predictable Financial Crises", *JF* |
| Bank stocks after a credit boom | 3-year excess return of **−37.3%** (predicted) after a 95th-percentile bank-credit expansion. Bank equity does *not* price the crash risk. | Baron & Xiong (2017), *QJE* |
| Credit-intensive recessions | Deeper and longer than normal recessions, with the depth rising in the size of the prior credit boom | Jordà, Schularick & Taylor (2013), *JMCB* |
| Aftermath of a systemic banking crisis (averages) | Equities **−56% over ~3.4 years**; house prices −35% over ~6 years; unemployment +7pp over ~4.8 years; real public debt +86% within 3 years | Reinhart & Rogoff (2009), *AER P&P* |
| Industry crash (−40% within 2 years) after a 2-year run-up | Run-up >50%: ~20%. Run-up >100%: **~53%**. Run-up >150%: ~80%. Higher with volatility, turnover, issuance, young firms and an accelerating price path. | Greenwood, Shleifer & You (2019), "Bubbles for Fama", *JFE* |
| Recession signal: Sahm rule | Historically triggered in each US recession since about 1960, with very few false triggers (one in the 1970s in revised data). It also triggered in Aug 2024 without a recession following, as of mid-2026 (verify). It fires after recessions have started, so it is a confirmation signal, not a lead. | Sahm (2019), Brookings; FRED SAHMREALTIME |
| Recession signal: yield curve (10y–3m) | Inversion preceded US recessions with 6–24 months' lead. The 2022–24 inversion was not followed by an NBER recession as of mid-2026 (verify). | Estrella & Mishkin (1998), *REStat* |
| Recession signal: credit spreads | A rising excess bond premium predicts falling activity and equities over the next year | Gilchrist & Zakrajšek (2012), *AER* |
| Junk-issuance boom | A high share of low-quality issuance predicts low future excess returns on corporate bonds | Greenwood & Hanson (2013), *RFS* |
| African swine fever, China 2018–19 | Pork prices stayed elevated for **~14 months** and took **~38 months** to normalize. Herd rebuilding is the biological lag. | USDA ERS reports on ASF |
| Commodity and sector trends | Time-series momentum persists **1–12 months**, then partly reverses | Moskowitz, Ooi & Pedersen (2012), *JFE* |
| Commodity price cycles | Slumps tend to last longer than booms. Price cycles are asymmetric and mostly unpredictable in timing. | Cashin, McDermott & Scott (2002), *JDE* |
| Tanker spot freight | Close to a random walk in normal ranges, **with strong mean reversion only at extremes**. Record rates are fragile. | Adland & Cullinane (2006), *Transportation Research E* |
| Export restrictions (food) | One exporter's ban raises world prices, which triggers further bans. This multiplier explains a substantial part of the 2008 and 2010–11 food spikes. | Giordani, Rocha & Ruta (2016), *J. Int. Econ.* |
| Election surprises | Sector winners and losers reprice within **days** (2016 US). Months-long effects come only from implementation that the market underestimates. | Wagner, Zeckhauser & Ziegler (2018), *JFE* |
| Populist governments | ~10% lower GDP per capita after 15 years versus a synthetic control. A slow burn, so not a trade signal on its own. | Funke, Schularick & Trebesch (2023), *AER* |
| Politics after financial crises | Far-right vote share rises ~30% in the five years after a systemic financial crisis | Funke, Schularick & Trebesch (2016), *EER* |
| Pandemic onset (COVID-19, 2020) | Prices moved first on China exposure (January), then on the global "fever" phase from Feb 24. Investors underreact to exponential growth. | Ramelli & Wagner (2020), *RCFS*; Stango & Zinman (2009) on exponential-growth bias |
| Hot thematic ETF launches | Specialized ETFs launched after a theme gets hot underperform after launch. A launch wave is a late-phase sign. | Ben-David, Franzoni, Kim & Moussawi (2023), *RFS* |

Where no row fits, find 2–3 historical analogues with WebSearch and use their median outcome. Name them in the card.

---

## 3. Likelihood ratios: how strong is a signal?

| Strength | LR if present | What qualifies |
|---|---|---|
| **Strong** | ×2.5 | Hard, observable, multi-source fact acting *directly on the mechanism*. Examples: insurers cancel cover; physical flows below a threshold for 2 weeks or more; inventories outside the 5-year range and falling; official confirmation of spread to a new region; credit spreads breaking a multi-year range; a dated catalyst confirmed. |
| **Moderate** | ×1.6 | Credible intent or partial data. Examples: official threats with a deadline; early data points; specialist press consensus; a second exporter imposing a ban; buffers projected to run out. |
| **Weak** | ×1.2 | Rhetoric, a single source, early-warning statistics, social media, analogues that only loosely fit |
| Strong counter-signal | ×0.5 | *Repair* under way: flows restored, capacity added, a deal signed with a guarantor, a backstop announced. Also the market already prices the extreme case (curve or options at record levels). |
| Moderate counter-signal | ×0.7 | Ripeness or convergence indicators present; buffers being rebuilt; the substitute route shown to work at scale |
| Weak counter-signal | ×0.85 | Talk of talks; relief measures only; a single-source report of de-escalation |

Rules:
- **Count correlated signals once.** Three news stories about the same insurer decision are one signal.
- **Half-weight single-source items** by taking the square root of the LR.
- **Cap the product at ×10 or ÷10.** Beyond that, you are probably double-counting.
- **Record the LR for each signal in the card**, so that the log can recalibrate them later.

---

## 4. Noise-to-signal ratio ↔ likelihood ratio

For any indicator, tabulate past episodes:

|  | Crisis followed | No crisis |
|---|---|---|
| Signal on | A | B |
| Signal off | C | D |

- **Hit rate** = A/(A+C).
- **False-alarm rate** = B/(B+D).
- **Adjusted noise-to-signal ratio (NSR)** = false-alarm rate ÷ hit rate (Kaminsky & Reinhart 1999, *AER*). Lower is better.
- **LR+ = 1/NSR.**

So NSR 0.4 ≈ strong (×2.5), NSR 0.6 ≈ moderate (×1.6), and NSR 0.8 ≈ weak (×1.2). An indicator with NSR ≥ 1 is noise and gets dropped.

---

## 5. Shock typing and Fermi sizing

**Kilian (2009, *AER*) shock types.** Classify the shock first, because each implies a different persistence and set of winners.

| Type | Signature | Persistence | Equity read-through |
|---|---|---|---|
| Supply shock | Price ↑, volume ↓, activity ↓ | Depends on spare capacity and how long repair takes | Producers outside the disrupted area ↑; consumers ↓ |
| Aggregate demand | Price ↑ with activity ↑ | Lasts as long as the cycle | Broad cyclicals ↑ |
| Precautionary demand | Spike on uncertainty, inventories bought, futures curve backwardates | **Fades fast once uncertainty resolves** | Sharp reversal risk; prefer short horizons and tight exits |

**Theory of storage** (Gorton, Hayashi & Rouwenhorst 2013, *RoF*).
- Low inventories go with backwardation, a high convenience yield, higher volatility and higher futures risk premia. Shocks amplify when buffers are thin.
- Positive roll yield helps long ETC holders.
- High inventories and contango do the opposite: the shock gets absorbed and roll yield is a drag.

**Input specificity** (Barrot & Sauvagnat 2016, *QJE*). Disruptions to *specific*, hard-to-substitute inputs propagate to customers' sales and stock prices. Generic inputs don't. Ask: can buyers switch suppliers within a quarter?

**Fermi template.** Expected move ≈ disrupted share of supply × (1 / short-run price elasticity) × probability the disruption persists over the horizon, minus what is priced.

Use published short-run elasticities where available. For oil, short-run demand elasticity is very low, roughly −0.05 to −0.1 (verify for the case), which is why small supply losses move price a lot. State every input with its source, and give a range rather than a point.

---

## 6. Early-warning statistics (critical slowing down)

**Theory.** Scheffer et al. (2009, *Nature*) show that as a system approaches a tipping point it recovers more slowly from small shocks. That shows up as rising variance, rising lag-1 autocorrelation (AC1) and, often, changing skewness. The method follows Dakos et al. (2012, *PLoS ONE*):
1. detrend the series;
2. compute rolling indicators over a window of about half the series;
3. measure their trend with Kendall's τ.

`python scripts/signals.py ews series.csv --detrend ma` implements this.

**Read it carefully:**
- τ > 0.5 on two or more indicators counts as a weak-to-moderate signal (×1.2 to ×1.6), and never as a strong one.
- The method suits systems being pushed slowly toward a threshold: credit build-up, buffer depletion, gradual escalation. It is blind to sudden external shocks such as a surprise attack or an earthquake.
- Rising noise in the inputs can produce false positives. Check the result against the mechanism.
- Useful series include freight rates, credit spreads, case counts (log), commodity spreads, the event-count share for a region (GDELT) and FX volatility.

**Rising near-miss frequency** (from the structural-fragility patterns) is the qualitative version: more close calls per month means a system with less slack.

---

## 7. Bubble and crash-risk markers

Use these when the thesis is that a boom ends worse than priced (credit, financed booms, sector manias).

- **Run-up and its features** (Greenwood, Shleifer & You 2019): the table above. Crash risk rises with volatility, turnover, issuance, a young firm base and price acceleration. `python scripts/signals.py trend prices.csv` reports the 2-year run-up and the bucket it falls in.
- **Turnover and skew** (Chen, Hong & Stein 2001, *JFE*): high turnover relative to trend, after high past returns, predicts more negative skewness, meaning crash risk.
- **Credit plus asset prices together** (GHSS 2022): the strongest single crisis predictor in the base-rate table.
- **Issuer quality** (Greenwood & Hanson 2013): a rising junk share of issuance.
- **Log-periodic power law** (Sornette 2003, *Why Stock Markets Crash*): faster-than-exponential growth with accelerating oscillations. Weak evidence only, because the timing of the critical point is very uncertain.
- **Funding and collateral** (financed-boom pattern; see the playbooks): booms financed by vendors, by guarantees or against scarce collateral end when funding tightens or the collateral price falls. A *slowdown*, not a collapse, is enough to trigger it.

Timing caveat:
- Bubbles can run far longer than fundamentals justify, because arbitrageurs wait for each other (Abreu & Brunnermeier 2003, *Econometrica*).
- Without a synchronizing catalyst, a correct bubble call is unprofitable (Shleifer & Vishny 1997, *JF*).

---

## 8. Timing table (12 rows)

Each row reads **E**arly, **N**eutral or **L**ate. Write the evidence next to each reading.

| # | Row | Early | Neutral | Late |
|---|---|---|---|---|
| 1 | Price move so far ÷ median analogue peak move | < ⅓ | ⅓–⅔ | > ⅔, or above the analogue maximum |
| 2 | Time since onset ÷ analogue elevated-phase duration | < ⅓ | ⅓–⅔ | > ⅔ |
| 3 | Attention: front pages, Google Trends (Da, Engelberg & Gao 2011) | specialist press only | rising mainstream | front page, Trends at its maximum, retail chatter |
| 4 | ETF flows and launches (Brown, Davies & Ringgenberg 2021; Ben-David et al. 2023) | flat or outflows despite a price rise | modest inflows | record inflows, AUM multiplying, new thematic launches |
| 5 | Futures curve and inventories (Gorton et al. 2013) | backwardation steepening, inventories falling below range | stable | backwardation easing, inventories rebuilding, contango returning |
| 6 | Positioning: CFTC managed-money net, short interest | not extended | moderately extended | above the 90th percentile of 3 years |
| 7 | Buffers (structural fragility) | draining, no repair | stabilizing | being rebuilt: new supply, rerouting complete, capacity added |
| 8 | Policy response | none, or relief only (caps, stock releases, subsidies) | mixed | structural repair under way |
| 9 | Resolution signals (conflict ripeness or convergence; outbreak Rt < 1; credit backstop) | absent | talk, but no valid spokesmen or no way out | mutually hurting stalemate, a way out and valid spokesmen together, or a backstop announced |
| 10 | Trend age, measured by a positive 12-month return (Moskowitz, Ooi & Pedersen 2012) | 1–6 months | 6–12 months | over 12 months, or the trend has broken |
| 11 | Volatility regime (realized against the 1-year median) | rising from a low base | elevated and stable | above 2× the median, or collapsing after a peak |
| 12 | Catalyst (Abreu & Brunnermeier 2003) | a dated catalyst within the horizon that forces recognition | vague | all known catalysts have passed |

**Verdict:**

| Reading | Verdict |
|---|---|
| ≥3 E and 0 L | Months likely |
| 1–2 L | Weeks to a few months; size down and scale out early |
| ≥3 L | Too late to chase |

A contrarian thesis needs row 12 to read E.

**Other things to note:**
- **Stale-news check** (Tetlock 2011, *RFS*): if prices jump on reports that repeat old facts, expect reversal. That counts as one L, on row 3.
- **Underreaction check** (Hong & Stein 1999; Da, Gurun & Warachka 2014): if the information has arrived in many small same-direction steps and the price has moved less than the fundamentals, that counts as one E, on row 1.
- **Political-event pricing** (Kelly, Pástor & Veronesi 2016, *JF*): options spanning an election or summit carry a premium. Read the implied move to see what is priced.

---

## 9. Formulas

- **Odds and posterior:** odds = p/(1−p); posterior odds = prior odds × Π LRᵢ (capped); p = odds/(1+odds).
- **Expected value per unit of risk:** EV/R = p·(target/stop) − (1−p). Proceed only if this is > 0, and prefer > 0.3.
- **Kelly fraction** of capital to put at risk (binary payoff approximation): f* = p − (1−p)/b, where b = target ÷ stop distance. Use ¼ to ½ of f* (MacLean, Thorp & Ziemba 2011), capped by the user's risk budget.
- **Doubling time:** t₂ = ln 2 / r, where r is the slope of ln(count) against time. Under exponential growth, case counts multiply by 2^(Δt/t₂). People systematically underestimate this (exponential-growth bias).
- **Volatility scaling:** weight = target vol ÷ realized vol (Moreira & Muir 2017, *JF*). Cut exposure when volatility jumps.
- **Brier score:** mean of (p − outcome)². Lower is better: 0.25 is coin-flipping at p = 0.5. Skill score = 1 − Brier ÷ Brier of always forecasting the base rate.
