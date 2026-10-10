---
name: "etf-venue-check"
description: "Use whenever I consider buying an ETF or ask about one: asks broker and venue, breaks down all costs, flags percentage-based and FX fees, and recommends the best trading window."
---

# ETF cost, venue and timing check

Run this whenever the user mentions an ETF they are considering (by name, ticker or ISIN), or asks where, how or when to buy one. The output is a short, practical verdict:
1. a full breakdown of what the purchase and holding will cost at the user's broker and venue, with every cost charged as a percentage flagged;
2. warnings about high management fees, currency-conversion fees and other cost traps;
3. the best time window to place the order.

The user is a long-term investor based in Germany (CET/CEST), mostly using ETF savings plans plus occasional one-off purchases.

Guiding principle: costs you can control matter, so keep them separate from tax, which you can't. Be most suspicious of any cost charged as a percentage, because it grows with your money and compounds against you year after year. Flat fees in euros are far less dangerous for a long-term investor.

## Step 1 - Identify the ETF
- Resolve the exact fund: full name, ISIN, ticker, provider, **TER**, tracking difference if available, replication (physical/synthetic), distribution policy (accumulating/distributing), domicile, **fund size**, **fund currency**, and the trading currency of each listing.
- Good sources: justetf.com profile (search by ISIN), the provider's fund page and KID/PRIIPs document, boerse-frankfurt.de ETF page.
- If the name is ambiguous (several share classes or providers), list the candidates and ask which one, or pick the largest accumulating EUR-traded UCITS share class and say so.
- Check the **product type**: UCITS ETF, or an ETN/ETC/ETP (debt instrument with issuer counterparty risk), and whether it is **leveraged or inverse** (names or descriptions with 2x, 3x, -1x, Leveraged, Short, Daily, Bear/Bull). Record the leverage factor and the reset period.
- Check the **domicile and legal structure**: a UCITS fund domiciled in IE, LU or DE, or a fund domiciled anywhere else (e.g. US, CH, CA, UK, JP), and whether it is a corporate-style fund or a tax-transparent partnership, trust or pool that passes its income through to the holders (in the US: a **Schedule K-1** instead of a Form 1099; the prospectus says "taxed as a partnership", the fund page lists K-1 information). Record which it is, because it decides the foreign tax exposure (Step 5).
- Note what the ETF holds, by region, because this decides the best trading window (Step 5): US equities, European equities, global (e.g. MSCI World or ACWI, which are mostly US), Asia/EM, bonds, or commodities.

## Step 2 - Ask about broker AND venue (always ask both, do not assume)
Ask with AskUserQuestion (or in plain text if unavailable). Reuse anything already said in this conversation.
- **Broker and price model or tariff**: free text. Do not suggest or presume a particular broker.
- **Trading venue**: Xetra, gettex, European Investor Exchange (EIX), or Other (e.g. Tradegate, LS Exchange, a foreign exchange).
- **Order type and size**: savings plan (monthly amount) or one-off order (EUR amount).
- **Account wrapper**, if any: plain depot, managed or robo portfolio, insurance wrapper, or Altersvorsorgedepot. These can add their own percentage fees.

## Step 3 - Look up current costs
Fees change often, so never rely on memory. Search current sources and state the date of each figure.
1. **Tradability**: is the ISIN listed or quoted on the chosen venue and offered by the broker? If not, say so and name where it is available.
2. **Savings plan availability** (always check, even for a one-off order): is the ISIN in the broker's own savings plan list (Sparplan-Liste or the broker's ETF search with a savings plan filter)? Prefer the broker's list over third-party comparisons, which lag. Note the minimum rate, any minimum depot value required before a savings plan is allowed, the execution days and the **venue on which savings plans are executed**, which is often fixed by the broker and may differ from the venue the user chose. If it is not available, say so and name a similar savings-plan-eligible ETF at that broker (same or similar index, ISIN, TER).
3. **Broker order fee** for that venue and tariff, from the broker's current price list (Preis- und Leistungsverzeichnis) and recent news. Note that pricing changed after the EU payment-for-order-flow ban in mid-2026. Include minimum and maximum fees and minimum-volume conditions.
4. **Venue and third-party fees**: Handelsplatzentgelt, Börsengebühr, Fremdkosten or third-party flat fees.
5. **Savings plan fees**: execution fee and minimum rate.
6. **Custody or account fees** (Depotgebühr), especially if charged as a percentage.
7. **Spread**: the current or typical bid-ask spread. The Xetra page on boerse-frankfurt.de shows the spread and the Xetra Liquidity Measure (XLM). gettex and EIX quotes are set by market makers. During Xetra hours, large ETFs typically trade at about 0.02-0.10%.
8. **Currency conversion (FX)**: does buying this listing require converting EUR, e.g. a USD-traded line or a foreign exchange? If so, find the broker's FX fee or markup. Explain clearly: an ETF bought in EUR on a German venue needs no FX conversion by the broker, even if the fund holds US stocks or is denominated in USD. The currency risk of the holdings is market risk, not a fee.
9. **Wrapper or management fees** on top of the ETF (robo, managed portfolio, insurance or pension wrapper), if the user mentioned one. Add the ongoing costs of the funds inside the wrapper and compare only the total, because providers can shift costs between their own fee and the fund costs (e.g. rebates from the funds to the provider). Check the fee at the user's amount and for the exact strategy, since fees are often tiered. Ask for the ex-ante cost statement (Kosteninformation), which also shows transaction costs from rebalancing, and check whether any return projection is shown after costs.
10. **Product costs**: TER and the transaction costs (both from the KID), tracking difference, and any issue surcharge (Ausgabeaufschlag), which applies when buying funds directly from a fund company rather than on an exchange.

## Step 4 - Cost breakdown
Present a table, splitting one-off from running costs, and mark every cost charged as a percentage:

| Cost item | Type | Amount | As EUR for this order/year | % based? |
|---|---|---|---|---|
| Broker order fee | one-off | ... | ... | yes/no |
| Venue / third-party fees | one-off | ... | ... | ... |
| Est. half-spread (spread x amount / 2) | one-off, hidden | ... | ... | yes |
| FX conversion | one-off, hidden | ... | ... | yes |
| Savings plan fee | per execution | ... | ... (per year) | ... |
| TER | running | ... | ... per year on the holding | yes |
| Custody / wrapper / management fee | running | ... | ... per year | ... |

Then add:
- **Total one-off cost** in EUR and as a % of the order.
- **Total running cost per year** in EUR and %.
- **Compounding illustration for every running cost charged as a percentage**: show the EUR drag over 10 and 20 years on the user's amount or savings rate, assuming a stated gross return (e.g. 7%). For example, 1% a year over ~20 years takes roughly the equivalent of one year's contributions or more. Compare this with a 0.1-0.2% broad-index ETF.

## Step 5 - Warnings (always include the relevant ones)
- **Leveraged or inverse products** (strong warning, put first): they reset daily, so over longer periods volatility decay makes the return deviate from, and often fall far below, the leverage factor times the index return, even when the index ends higher. They are trading instruments, not suited to long-term holding or savings plans. ETNs and ETCs also carry issuer default risk, as they are not segregated fund assets. Name the unleveraged UCITS ETF on the same index (ISIN, TER) as the alternative.
- **Management fee (TER)**: flag above about **0.30%** for a broad index ETF, and strongly flag above **0.50%**. Active funds at 1-2% a year usually lose to cheap index ETFs after costs. If a cheaper ETF on the same or a very similar index exists, name it with its TER and ISIN.
- **Any cost charged as a percentage**: percentage order fees, percentage savings plan fees, custody fees, robo/advisory or wrapper fees, insurance wrappers. Say clearly that these scale with the money and compound. Prefer flat EUR fees or zero. For robo or managed portfolios, Stiftung Warentest (Finanzen 7/2026, costs as of 31 Jan 2026) rated a provider fee of 1% a year or more as poor (mangelhaft); the cheapest well-rated offers cost about 0.3-0.65% a year in total including fund costs, against about 0.1-0.2% for a do-it-yourself ETF portfolio.
- **Foreign tax obligations** (strong warning for tax-transparent funds, put right after leveraged products): any fund domiciled outside IE, LU and DE, or structured as a partnership, trust or pool, can bring tax obligations in its home country on top of German tax. Unlike German tax, these are avoidable by choosing an IE, LU or DE UCITS fund, so treat them as a trap, not as background. For the fund's domicile, check and report:
  - **Filing obligations**: does a foreign shareholder have to file a tax return there?
  - **Withholding tax** on distributions and, in some countries, on sale proceeds, the treaty rate with Germany, the form needed to get it, and whether and how the excess can be reclaimed (often slow and paid for). Only the treaty rate is creditable against German tax, the rest is lost unless reclaimed. Example: Swiss funds deduct 35% Verrechnungssteuer, of which 20% must be reclaimed from Switzerland.
  - **Phantom income**: for tax-transparent structures, tax due on income that was never paid out.
  - **Estate or inheritance tax** in the fund's country, and **transaction taxes** or stamp duties on trades there.
  - IE and LU UCITS funds normally create none of these for a German investor; check rather than assume.
  The US is the most common case:
  - **US partnerships and commodity pools issuing a K-1** (many futures-based commodity, volatility and freight ETFs): each shareholder is taxed on their share of the fund's income whether or not anything is paid out, so the tax bill can exceed the cash received. A non-US shareholder may have to file a US tax return (Form 1040-NR) and can be subject to US withholding on allocated income and, under Section 1446(f), 10% withholding on the gross proceeds of a sale, not just the gain, unless the fund publishes a qualified notice that an exception applies. Check the fund's tax page and its latest qualified notice, and say whether withholding on sale proceeds applies. Many brokers refuse K-1 funds for non-US clients for these reasons.
  - **Ordinary US 1940 Act ETFs**: no US return is needed, but US withholding tax applies to dividends (15% with a W-8BEN under the German-US treaty, 30% without one) and is only partly creditable against German tax.
  - **All US-domiciled funds**: shares are US-situs assets for US estate tax; for a German resident the German-US estate tax treaty usually gives relief, but heirs may face US paperwork.
  - Funds domiciled outside the EU usually have no PRIIPs KID, so German brokers often block retail purchases anyway. Name the IE, LU or DE UCITS equivalent (ISIN, TER) if one exists, and say that the German treatment of a foreign partnership or trust is a question for a tax adviser.
- **Currency conversion fees**: warn if the chosen listing or venue triggers FX conversion. Recommend the EUR listing on a German venue where one exists.
- **Issue surcharges** (Ausgabeaufschlag, up to ~5%) if buying via a fund company instead of an exchange.
- **Small or illiquid funds**: fund size under about EUR 100 million (closure or merger risk), wide spread, high XLM, few market makers.
- **Synthetic replication or unusual structures**: mention them as a note, not an alarm.
- **Frequent trading**: every extra trade adds fees and spread. For long-term saving, fewer instruments and fewer trades cost less.
- **Tax** (Germany): keep it separate from costs. Mention briefly where it matters: Vorabpauschale on accumulating funds, 30% Teilfreistellung for equity funds, Sparerpauschbetrag. Tax is not something you can choose away by picking a cheaper product.

## Step 6 - Trading times and the best window
State the venue's trading hours and the window to aim for. Always mention the **EU/US overlap** explicitly.

Venue hours (Mon-Fri, CET/CEST). Verify them, because they change:
- Xetra: 09:00-17:30 (with opening and closing auctions)
- gettex: roughly 07:30/08:00-22:00/23:00
- EIX: roughly early morning to 23:00
- Tradegate: roughly 07:30/08:00-22:00

Best window by what the ETF holds:
- **US equities** (S&P 500, Nasdaq-100, US sectors, semiconductors with a US majority): **15:30-17:30 CET**, when the US market and Xetra are both open and market makers can hedge directly.
  - DST mismatch: the US switches to summer time on the 2nd Sunday of March and back on the 1st Sunday of November; the EU switches on the last Sundays of March and October. In those weeks the overlap is **14:30-17:30 CET**. Check today's date.
- **Global equities** (MSCI World, ACWI, FTSE All-World; about 60-70% US): the EU/US overlap is best; otherwise 09:15-17:15.
- **European equities**: 09:15-17:15.
- **Asian equities** (Korea, Taiwan, Japan, China) and EM-Asia: their home markets are closed during the whole Xetra day, so spreads are structurally wider. Use Xetra hours and avoid evenings. If the ETF is mixed US and Asia, prefer the EU/US overlap.
- **Bond ETFs**: 09:15-17:15; for US-dollar bonds, prefer the EU/US overlap.
- **Gold, commodity ETCs**: 09:15-17:15, ideally during the EU/US overlap.

Always warn against:
- the first and last ~15 minutes of Xetra trading
- evenings, early mornings and weekend order entry on extended-hours venues, when spreads widen
- US holidays and very volatile days
- market orders for one-off purchases: suggest a **limit order** near the current ask instead

For **savings plans**, the broker usually sets the execution time, so timing advice mostly doesn't apply; say so briefly.

## Step 7 - Report back (keep it compact)
1. ETF identified: name, ISIN, product type (UCITS ETF or ETN/ETC/ETP, leveraged or inverse), domicile and, if not an IE, LU or DE UCITS fund, its foreign tax treatment (e.g. K-1 or 1099 in the US), TER, fund size, what it holds.
2. Broker and venue checked: tradable yes/no, savings-plan eligible yes/no with minimum rate and execution venue.
3. The cost breakdown table, totals, and the compounding illustration for any cost charged as a percentage.
4. Warnings, in order of how much money they cost.
5. Best time window, with the EU/US overlap stated (and the DST caveat if relevant).
6. A cheaper alternative, if one exists: same index, lower TER, or a better venue or listing.
7. Sources with dates.

If the user compares several venues or brokers, show them side by side: venue/broker | tradable | order fee | venue fees | typical spread | FX needed | hours | best window | total one-off cost.