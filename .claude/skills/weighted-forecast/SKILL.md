---
name: "weighted-forecast"
description: "Use when I ask what will happen, who will win, whether I should do something, or how much something will be: research it and give a weighted-outcome forecast with a verdict."
---

# Weighted Forecast

Turn an uncertain question into an evidence-based forecast with explicit weights, a plain verdict, and a record that can be checked later. Works for sports, markets, business decisions and personal choices.

## 1. Pin down the question

A forecast must answer the exact question asked. Check that it has:
- **A resolvable outcome**: something that will clearly be true or false, or a number.
- **A resolution date**: when we will know.
- **The decision context** (for "should I" questions): what the user cares about, constraints, money at stake.

If something essential is missing, ask ONE short clarifying question at a time (max 3 total), and tell the user they can say "skip" and you'll make a reasonable assumption. If they skip, state the assumption at the top of the report.

Classify the question type, since it decides the verdict format:
- **Which**: the verdict is the pick (team, option, candidate).
- **Will / yes-no**: the verdict is yes or no with a probability.
- **Should I**: the verdict is do it / don't / wait, tied to the user's goals.
- **How much / when**: the verdict is a number or date with a range.

## 2. Research before judging

Never assign weights before gathering facts.
- Use anything the user attached or told you.
- Search the web for current facts the outcome depends on: latest scores, injuries, prices, polls, filings, schedules, recent news. Use the sports data tool for games when available. Prefer primary sources and things dated in the last few weeks.
- Find a **base rate**: how often does this kind of thing happen in general? (Favorites at these odds win X%; startups in this stage survive Y%; this stock moves more than Z% in a month W% of the time.)
- If prediction markets or bookmaker odds exist for the question, find them. They are a strong prior; note them and explain any disagreement.
- Search past chats for earlier forecasts on related questions and how they resolved, and learn from misses.

Keep notes of the 3 to 6 **key drivers**: the facts that would move the forecast most.

## 3. Simulate and weight outcomes

1. List 3 to 6 realistic, mutually exclusive scenarios that cover the space (for numeric questions, use ranges/buckets). Include an "other / surprise" bucket if tail risk is real.
2. **Pass A, outside view**: divide 100 points across scenarios using the base rate and market odds only.
3. **Pass B, inside view**: divide 100 points again using the specific evidence and drivers.
4. **Pass C, devil's advocate**: argue for the least-weighted plausible scenario, then re-weight.
5. Final weights = roughly the average of the three passes, adjusted with judgment. Show your reasoning briefly.

Calibration rules:
- Never put 0 or 100 on anything that hasn't already happened. Stay between 3 and 97 unless the evidence is overwhelming.
- Don't round a 60/40 into false certainty. If it's close, say it's close.
- Weights are comparative estimates, not guarantees. Say so once, plainly.

## 4. Write the report

Lead with the verdict. Keep the top short (it may be read on a phone).

```
**Verdict:** <the pick / yes-no / do-don't / number>
**Confidence:** <weight of top outcome>%  ·  **Resolves:** <date>
<One or two sentences on why.>

**Outcomes**
- <Scenario A>: 55
- <Scenario B>: 30
- <Scenario C>: 15

**Key drivers:** <3 to 6 bullets, each a fact with its direction>
**What would change my mind:** <1 to 3 signals to watch>
**Suggested actions:** <1 to 3 concrete next steps>
```

When money is involved, add an **Upside / Downside** line: the plausible gain and loss range, derived from the same weighted outcomes (an expected value plus best and worst realistic case). Always show the downside next to the upside.

For personal or emotional questions, keep the same structure but write it warmly, and focus suggested actions on what the user controls.

End with Sources (links to what you used) and, for markets, betting, health or legal questions, one line noting this is a forecast, not professional financial, betting, medical or legal advice.

## 5. Keep an accuracy record

Offer to log the forecast. If the user agrees:
- Look for an existing prediction-log artifact (Artifact list, e.g. a Sheets artifact named "Prediction Log"). If none exists, create one from the Sheets type if it's listed; otherwise an HTML artifact with a shared database.
- Columns: date, question, type, outcomes and weights, verdict, confidence, resolution date, actual outcome, Brier score.
- Offer to create a scheduled task or reminder on the resolution date to come back and record what happened.

When the user reports an outcome, record it and compute the Brier score: sum over outcomes of (weight/100 - actual)^2, where actual is 1 for what happened and 0 otherwise. Lower is better; 0 is perfect. Once there are 10+ resolved forecasts, summarize calibration: are 70% verdicts right about 70% of the time? Mention any systematic over- or under-confidence and adjust future forecasts accordingly.