# Data sources

Use this file in Stage 1, and whenever a signal needs a data series.

How to work with these sources:
- Fetch pages with WebFetch or WebSearch. The workspace shell usually can't reach these sites directly.
- When a series is needed for `signals.py`, transcribe the values into a CSV with `date,value` columns.
- Date every number you use.
- URLs change, so if one fails, search for the source by name.

## Cross-family monitors

| Source | What it gives | URL |
|---|---|---|
| GPR index (Caldara & Iacoviello) | Geopolitical risk from news text, with *threats* and *acts* sub-indices, by country | https://www.matteoiacoviello.com/gpr.htm |
| Economic Policy Uncertainty (Baker, Bloom & Davis) | News-based policy-uncertainty indices by country, plus trade and monetary sub-indices | https://www.policyuncertainty.com/ |
| GDELT | Global event and tone data from news. Compare each region with its own baseline. | https://www.gdeltproject.org/ |
| ACLED | Coded conflict and protest events | https://acleddata.com/ |
| Crisis Group CrisisWatch | Monthly conflict tracker with deteriorated / improved flags | https://www.crisisgroup.org/crisiswatch |
| ViEWS | Probabilistic conflict forecasts, months ahead | https://viewsforecasting.org/ |
| NY Fed GSCPI | Global Supply Chain Pressure Index | https://www.newyorkfed.org/research/policy/gscpi |
| IMF PortWatch | Chokepoint transits and port calls from AIS data | https://portwatch.imf.org/ |
| Google Trends | Retail attention (timing row 3) | https://trends.google.com/ |

## Prediction markets

Polymarket and Kalshi list questions (bets) such as "Hormuz agreement by DATE?", "Military action against the Saudi East-West pipeline by...?" or "Confirmed Irkutsk plague cases this month?". A new question appears when enough traders care about a risk, often before mainstream coverage. That makes last week's new questions a drip signal for Stage 1, and their odds one reading of what is priced in Stage 4.

Everything below works with WebFetch alone: each URL returns JSON in a single fetch of under 100k characters. Keep `limit`/`page_size` and `include_markets=false` exactly as shown, because larger replies get truncated and questions are silently missed. Set the cutoff date to 7 days before today.

**Polymarket: new questions per topic.** Fetch once per tag, and again with `offset=15`, `offset=30` and so on until fewer than 15 events come back:

`https://gamma-api.polymarket.com/events?tag_slug=<tag>&start_date_min=<cutoff>T00:00:00Z&order=createdAt&ascending=false&limit=15&offset=0&include_markets=false`

- Tags: `geopolitics`, `world`, `economy`, `commodities`, `climate`, `tech`. Skip `finance`, `weather`, `sports` and `crypto`, which are flooded by short repeating price and sports markets.
- Fields per question: `createdAt`, `title`, `description` (the resolution rules), `volume`, `volume1wk`, `liquidity` and `slug` (page at `https://polymarket.com/event/<slug>`). For the odds, fetch `https://gamma-api.polymarket.com/events/slug/<slug>`, whose markets carry `outcomePrices`.
- Verified 2026-10-12 for the week from Oct 5: for all six tags, `start_date_min` returned exactly the questions whose `createdAt` fell in the week, with none missed and none extra. In that week geopolitics had 33 new questions, world 44, economy 7, commodities 36, climate 7 and tech 36.

**Kalshi: new questions per crisis keyword.** Kalshi has no per-topic listing sorted by creation. Search one keyword per candidate crisis (for example `plague`, `Hormuz`, `hurricane`, `tariff` or `default`):

`https://api.elections.kalshi.com/v1/search/series?query=<keyword>&page_size=8`

- A question is new when the earliest `open_ts` among its `markets` is on or after the cutoff. Also record `series_ticker`, `event_title`, `category` and `total_volume`.
- To confirm, fetch `https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=<series_ticker>&min_created_ts=<cutoff unix>&limit=100`. Every market it returns was created on or after the cutoff, and each carries `created_time`, `title`, `last_price_dollars` (the odds) and `volume_fp`.
- Verified 2026-10-12: "plague" returned the three plague questions that a full scan of all market creation times had found for the week, with `open_ts` within an hour of `created_time`.
- Don't list Kalshi by category with `order_by=newest`. That sort is not strict, and it buries one-off questions under 15-minute and hourly repeats.

How to read new questions:
- Several new questions on one theme within a week (for example plague in Irkutsk, then US pneumonic plague, then naming the pathogen) count as one moderate signal, not several. A single new question is weak.
- Weekly volume below about $10k is noise. Odds on questions tied to US elections inherit partisan bias.
- The title often differs from what actually resolves the market, so read the resolution rules before using the odds as "priced".
- If a fetch is refused or rate-limited (HTTP 429), fall back to WebSearch with `site:polymarket.com` or `site:kalshi.com` and the crisis keyword. Search results carry no creation dates, so treat them as existing questions only.

## Conflict and shipping

| Source | Use | URL |
|---|---|---|
| UKMTO | Maritime security advisories and incidents | https://www.ukmto.org/ |
| Lloyd's List, TradeWinds, Splash247, Hellenic Shipping News | Specialist shipping press: war-risk premiums, rates, insurer decisions | search by name |
| Drewry World Container Index | Weekly container spot rates | https://www.drewry.co.uk/supply-chain-advisors/supply-chain-expertise/world-container-index-assessed-by-drewry |
| Freightos Baltic Index (FBX) | Container rates | https://fbx.freightos.com/ |
| EIA Weekly Petroleum Status Report | US crude and product inventories, published on Wednesdays | https://www.eia.gov/petroleum/supply/weekly/ |

## Weather and agriculture

| Source | Use | URL |
|---|---|---|
| NOAA CPC ENSO advisory | El Niño / La Niña status and odds | https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ |
| NOAA National Hurricane Center | Outlooks and track cones | https://www.nhc.noaa.gov/ |
| USDA WASDE | Monthly supply/demand and stocks-to-use | https://www.usda.gov/oce/commodity/wasde |
| FAO Food Price Index | Global food prices, monthly | https://www.fao.org/worldfoodsituation/foodpricesindex/en/ |

## Disease

| Source | Use | URL |
|---|---|---|
| WHO Disease Outbreak News | Official outbreak reports | https://www.who.int/emergencies/disease-outbreak-news |
| ProMED | Early, informal outbreak reports | https://promedmail.org/ |
| WOAH WAHIS | Animal-disease immediate notifications | https://wahis.woah.org/ |
| USDA APHIS | US animal-disease confirmations (HPAI, ASF and others) | https://www.aphis.usda.gov/ |

## Credit, macro and markets

| Source | Use | URL |
|---|---|---|
| FRED: 10y–3m spread | Yield-curve signal | https://fred.stlouisfed.org/series/T10Y3M |
| FRED: real-time Sahm rule | Recession confirmation | https://fred.stlouisfed.org/series/SAHMREALTIME |
| Fed excess bond premium | Credit-market stress (Gilchrist & Zakrajšek) | https://www.federalreserve.gov/econres/notes/feds-notes/updating-the-recession-risk-and-the-excess-bond-premium-20161006.html |
| Fed Senior Loan Officer Survey | Lending standards | https://www.federalreserve.gov/data/sloos.htm |
| BIS credit-to-GDP gaps | Credit-boom gauge by country | https://www.bis.org/statistics/c_gaps.htm |
| OFR Financial Stress Index | Daily market stress | https://www.financialresearch.gov/financial-stress-index/ |
| CFTC Commitments of Traders | Futures positioning, released on Fridays (timing row 6) | https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm |
| Short-position registers | Disclosed net short positions above 0.5% in the EU. For Germany, published via the Bundesanzeiger. | search "Netto-Leerverkaufspositionen Bundesanzeiger" |

## Products (Stage 5)

| Source | Use | URL |
|---|---|---|
| justETF | UCITS ETF and ETC search, AUM, TER, domicile, replication, listings | https://www.justetf.com/ |
| Issuer sites (iShares, Xtrackers, Amundi, SPDR, VanEck, WisdomTree, HANetf and others) | KID, holdings, iNAV, closure notices | search by issuer |
| Börse Frankfurt / Xetra | Quotes, spreads, venues | https://www.boerse-frankfurt.de/ |

## Short reading list (for deeper questions)

- Scheffer et al. (2009), "Early-warning signals for critical transitions", *Nature*. Dakos et al. (2012), *PLoS ONE*, on methods.
- Kaminsky & Reinhart (1999), "The twin crises", *AER*. The signals approach and the noise-to-signal ratio.
- Caldara & Iacoviello (2022), "Measuring geopolitical risk", *AER*.
- Moskowitz, Ooi & Pedersen (2012), "Time series momentum", *JFE*.
- Greenwood, Hanson, Shleifer & Sørensen (2022), "Predictable financial crises", *JF*.
- Baron & Xiong (2017), "Credit expansion and neglected crash risk", *QJE*.
- Greenwood, Shleifer & You (2019), "Bubbles for Fama", *JFE*.
- Reinhart & Rogoff (2009), *This Time Is Different*.
- Fearon (1995), "Rationalist explanations for war", *IO*. Goemans (2000), *War and Punishment*. Slantchev (2003), *APSR*. Zartman (2000), on ripeness.
- Kaminski & Lo (2014), "When do stop-loss rules stop losses?", *J. Financial Markets*.
- Moreira & Muir (2017), "Volatility-managed portfolios", *JF*.
- Abreu & Brunnermeier (2003), "Bubbles and crashes", *Econometrica*. Shleifer & Vishny (1997), "The limits of arbitrage", *JF*.
