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
