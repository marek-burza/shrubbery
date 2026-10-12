# Orders and exits

Use this file in Stage 7, and every time in Review mode. Each rule cites its source, so the user can see why it is there.

## Contents
1. Instrument checks (run before recommending anything)
2. Setup type decides the stop policy
3. Entry
4. Sizing
5. Exits (pre-committed)
6. Monitoring cadence
7. Broker order vocabulary (German retail)

---

## 1. Instrument checks

Run every check on every instrument you might recommend. Look the data up on justETF, the issuer's site and the KID, and date it.

| Check | Why it matters | Rule |
|---|---|---|
| **PRIIPs / KID** | EU retail brokers block funds without an EU KID. That includes nearly all US-domiciled ETFs and ETNs (BWET, XLE, KRE and others). | US-domiciled funds are not available. Single stocks, including US-listed ones, don't need a KID and are available. Don't suggest "opting up" to professional status as a workaround. |
| **Domicile and structure** | UCITS funds domiciled in IE, LU or DE are the default. Replication can be physical or synthetic (swap-based); synthetic adds counterparty exposure, but it is collateralized. | State domicile and replication. |
| **What's really inside** | Sector ETFs are often dominated by a few mega-caps that are only weakly exposed to the crisis mechanism. A "World Energy" ETF, for example, is mostly integrated majors. | Read the top-10 holdings and the weights. Estimate how pure the exposure is. |
| **AUM and closure risk** | A fund that closes forces a sale at NAV. That crystallizes tax and costs at a time you didn't choose. | Flag AUM under €100m. Avoid AUM under €50m unless no alternative exists. |
| **Spread and premium to iNAV** (Petajisto 2017, *FAJ*) | Premiums and discounts are wider for illiquid underlyings and when the underlying market is closed. In crises they can blow out. | Trade only while the underlying market is open. Use limit orders priced from the iNAV. |
| **ETC/ETN structure** | These are debt securities, usually collateralized, so issuer risk applies. Futures-based ETCs earn or lose **roll yield**: backwardation helps long holders and contango drags (Gorton, Hayashi & Rouwenhorst 2013). | Check the futures curve. In contango, prefer "longer-dated" or optimized-roll variants where they exist. Note USD exposure, and whether a EUR-hedged share class exists. |
| **Leveraged or inverse, daily reset** (Cheng & Madhavan 2009, *JIM*) | Over multi-day holds, the return departs from L × index. The volatility drag is about ½(L² − L)σ² per unit time, so an inverse product (L = −1) loses about σ² per year. That drag is brutal in crisis-level volatility. | Don't use for holds longer than a few days. Default: excluded. |
| **Currency** | The underlying is often USD, and EUR/USD moves can swamp the thesis over months. | State the currency and the hedge status. |
| **German tax** (confirm with a tax adviser) | Equity funds with ≥51% equity get 30% partial exemption. ETCs get none. Single-stock losses can only be offset against single-stock gains. | Mention it when it changes the choice between instruments. |

**If no suitable UCITS product exists** (tanker freight is an example), say so plainly. Then offer the alternatives, in order:
1. single stocks with the purest exposure (listed on liquid venues, ideally 3–5 names to spread company-specific risk);
2. the broader UCITS sector ETF;
3. an ETC on the underlying commodity.

---

## 2. Setup type decides the stop policy

| Setup | When | Stop policy | Evidence |
|---|---|---|---|
| **Trend / persistence** | Drip-fed news; the price is trending with the mechanism; timing reads "months likely" | **Use a trailing volatility-width stop** | Stops add value when returns have momentum and lose value under random walks or mean reversion (Kaminski & Lo 2014, *J. Fin. Markets*). Stop-loss rules sharply reduce momentum-crash losses (Han, Zhou & Zhu 2016, "Taming Momentum Crashes", SSRN working paper). |
| **Mean-reversion / contrarian** | Fading an overpriced crisis; buying a loser after repair signs; fraud or bubble calls | **No tight price stop.** Use thesis-break and time stops, plus a wide "disaster" stop (e.g., 3–4× the usual width). Size smaller instead. | Tight stops whipsaw in mean-reverting markets (Kaminski & Lo 2014). Contrarians also need a catalyst (Abreu & Brunnermeier 2003). |
| **Binary event** | An election, summit, court ruling or OPEC meeting | A stop **can't** protect against an overnight gap. Size so that a full gap loss stays within budget, or enter *after* the event. | The event premium is visible in options (Kelly, Pástor & Veronesi 2016) |

---

## 3. Entry

**Triggers.** Use at least one, and state which:
1. *Fact confirmation:* a hallmark becomes observable. Examples: insurers withdraw cover; inventories breach the 5-year range; spread to a new region is confirmed.
2. *Price confirmation:* a close above the 50-day high, or the 12-month return turning positive (the time-series momentum sign; Moskowitz, Ooi & Pedersen 2012).
3. *Pullback in an established trend:* a pullback to around the 20-day average with no thesis-break fact.

**Tranches.**
- Default: ⅓ on the first trigger, ⅓ on a second, independent confirmation, ⅓ on a pullback or a third trigger.
- In trend setups, add to winners, not losers.
- Never add after a thesis-break fact.
- In contrarian setups, tranche by time (e.g., monthly), because the price will often move against you first.

**Order type and timing.**
- Always use a **limit order**. For ETFs and ETCs, set it from the iNAV: buy limit ≤ iNAV + half the normal spread.
- Avoid the first 15–30 minutes after the open, and any time the underlying market is closed.
- For US-underlying products, trade in the 15:30–17:30 CET overlap (see the etf-venue-check skill if available).
- On headline days, don't chase gap opens. Repeated stale news causes overreaction that reverses (Tetlock 2011). Wait for the first hour, or place the limit near the prior close.
- Savings plans suit the core portfolio, not crisis trades. They execute on a schedule and can't respond to triggers or exits.

---

## 4. Sizing

Compute with `python scripts/signals.py size --capital C --risk-pct R --entry E --stop S [--vol V] [--p P --target T]`.

1. **Risk-budget size:** position value = (R% × capital) ÷ stop distance %. The default R is 0.75% of the portfolio per idea.
2. **Volatility cap** (Moreira & Muir 2017): position weight ≤ idea volatility budget ÷ annualized volatility.
   - Default budget: 2% of the portfolio, annualized.
   - A 100%-volatility instrument gets at most a 2% weight; a 40%-volatility one at most 5%.
3. **Kelly cap** (MacLean, Thorp & Ziemba 2011): the risk fraction must not exceed ¼ × f*, where f* = p − (1−p)/b and b = target distance ÷ stop distance.
   - If f* ≤ 0, there is no trade.
   - Full Kelly is far too aggressive given estimation error in p.
4. **Correlation:** ideas that share a mechanism (e.g., Hormuz oil, Hormuz tankers and Gulf petrochemicals) share **one** risk budget.
5. **Crisis-book cap:** the total across all crisis trades is ≤10% of the portfolio by default.

Report the binding constraint. If the volatility or Kelly cap binds well below the risk budget, the instrument is too volatile or the edge too thin. Say so.

---

## 5. Exits (pre-committed, written before entry)

**(a) Thesis-break facts.** Name 2–4 observable events per card. This is the most important exit.
- **Repair means exit:**
  - physical flows restored (e.g., above 70% of normal for 2 weeks);
  - capacity back online;
  - inventories rebuilt to the 5-year average;
  - a deal signed *with a guarantor*;
  - outbreak Rt < 1 for 2 weeks or more;
  - a policy reversal *enacted*;
  - a lender-of-last-resort backstop.
- **Relief means tighten, don't exit:**
  - talks or talks about talks;
  - price caps;
  - strategic-stock releases;
  - announced pauses.

  Relief lowers prices temporarily without restoring supply. When it runs out, a second leg is common (see the structural-fragility patterns). Move the stop up, but stay in.
- Conflict endings: use the termination checklist in `family-playbooks.md`. Exit when ripeness and convergence signals line up.

**(b) Price stop** (trend setups only):
- **Initial stop:** entry − k × ATR(20), with k = 2.5–3. If only closes are available, use k × σ_daily × entry, with k ≈ 3–4.
- **Trailing stop:** highest close since entry − k × ATR(20).
- Evaluate on daily **closes**, not intraday ticks.
- In illiquid ETFs and ETCs, or in fast markets, stop-market orders can fill far below the trigger. Use a **stop-limit** with room below, or a close-based **price alert** and execute manually in liquid hours.

**(c) Time stop.**
- Re-underwrite or exit by a fixed date: at most 12 months after entry, because time-series momentum partly reverses beyond 12 months (Moskowitz, Ooi & Pedersen 2012).
- Exit earlier if the catalyst date passes without effect.

**(d) Late-phase scale-out:**

| When | Action |
|---|---|
| Timing table shows 1–2 L rows | Sell ⅓ |
| Timing table shows ≥3 L rows, **or** the price reaches the median analogue peak | Sell another ⅓ |
| — | The last ⅓ rides the trailing stop |

Extreme freight rates mean-revert fast (Adland & Cullinane 2006), so scale out *into* record prints.

**(e) Volatility rule** (Moreira & Muir 2017):
- If 20-day realized volatility exceeds 2× the volatility at entry, cut the position so that weight × volatility returns to its entry level.
- **Momentum-crash rule** (Daniel & Moskowitz 2016, *JFE*): after a large market drawdown with high volatility (a panic state), loser, short and inverse legs face violent rebounds. Cut them first.

**(f) Product exits.** Exit on any of:
- a closure or merger notice;
- AUM falling below €50m;
- KID withdrawal or a trading suspension;
- a persistent premium or discount above 2%;
- a swap-counterparty or ETC-issuer credit event;
- an index methodology change that dilutes the exposure.

**(g) Disposition guard** (Odean 1998, *JF*: investors sell winners too early and hold losers too long):
- Exits are written down before entry.
- At each review, ask: "Would I open this position today, at this price, with this evidence?" If not, exit, whatever the P&L.
- Never widen a stop after entry.

**(h) Thesis drift.** If the reason for holding changes, treat it as a new trade: re-run Stages 4–7 and resize.

---

## 6. Monitoring cadence

| Cadence | What to check |
|---|---|
| Daily (5 minutes) | Close against the stop; a headline scan for thesis-break facts; a volatility check |
| Weekly | Watch-list indicators (inventories on EIA Wednesdays, CFTC on Fridays, freight, flows). Re-score the timing table. |
| Monthly | Full Review mode: re-run the Stage 4 posterior, update the log line, check product health |
| Catalyst dates | Review the same day |

Offer the user a weekly scheduled review task for open positions.

---

## 7. Broker order vocabulary (German retail)

| Term | Meaning |
|---|---|
| *Limit-Order* | Buy or sell at the limit price or better. The default for ETFs and ETCs. |
| *Stop-Loss / Stop-Market* | Becomes a market order once triggered. Dangerous in gaps and thin books. |
| *Stop-Limit* | Becomes a limit order once triggered. It may not fill, but it can't fill at a disastrous price. |
| *Trailing-Stop* | The stop follows the price by an absolute or percentage distance. On some venues it triggers on market-maker quotes, including outside the underlying's hours, so prefer close-based alerts during crises. |
| *Handelsplatz* | The trading venue (Xetra, gettex, Tradegate and others). The etf-venue-check skill covers the choice and the costs. |
