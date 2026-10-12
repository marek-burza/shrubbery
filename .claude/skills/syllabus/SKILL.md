---
name: "syllabus"
description: "Builds a concise, evidence-based Markdown syllabus from a learner's current to target level in any field, with free drill platforms. Use for study plans, learning roadmaps, curricula, upskilling."
---

# Syllabus designer

Produce a dense, phase-structured self-study syllabus in Markdown that closes the gap between where a learner is and where they want to be, in any field: a language, a technical career, finance, an academic subject, a musical instrument, a sport. The target feel is the list a top instructor would hand over: short, complete, ordered, every item earning its place.

Workflow (section numbers match): **1. Intake → 2. Gap research → 3. Design → 4. Length budget → 5. Drill platforms → 6. Write → 7. Check and deliver.** Put these on a task list.

## 1. Intake

Three fields are required. Take whatever the conversation already gives you and ask only for the rest, in a single round.

| Field | Good answer | Vague answer → ask for |
|---|---|---|
| Topic | German; ML engineering; financial markets; jazz guitar | "AI", "finance" → which slice (research vs applied ML; investing vs trading vs corporate finance)? |
| Starting level | Evidence, not labels: "Goethe B1, reading B2 texts"; "staff SWE who productized models"; "buy index ETFs, never valued a company" | "intermediate" → what can you already do or prove? |
| Target level | A testable endpoint: "pass Goethe B2"; "senior ML engineer offer"; "pass CFA Level I"; "run my own portfolio with written rules"; "1800 Lichess rapid" | "fluent", "senior", "good at" → which exam, role, rating or task proves it? |

Also ask in the same round, offering sensible defaults: hours per week, deadline, how the target will be proven, known weak spots.

- Use AskUserQuestion when available (2–4 options per question, header ≤ 12 chars). Free-text answers come through its built-in "Other" option, so derive options from context.
- If unattended, take the most reasonable reading, record it under **Assumptions** in the document header, and continue. When the request clearly leans one way, take that reading. Only when two paths are genuinely equally likely (senior data scientist vs senior ML engineer), build a shared core plus a short track per path.

## 2. Gap research

Goal: an item-level list of what the target requires that the start doesn't already cover. Research it rather than recalling it: standards and role expectations change, and recall from memory leaves holes.

**a. Find the target specification.** Where it lives depends on the kind of field; many targets mix types (a senior role plus a certification).

| Field type | Where the target spec lives | How progress is proven |
|---|---|---|
| Examined / certified (languages, CFA, CPA, cloud certs, licences) | Official exam blueprint, sample papers and marking criteria, topic outline and weights, level descriptors | The exam's own tasks and pass mark |
| Professional role (ML engineer, equity analyst, product manager) | Career ladders and leveling guides, current job postings at the target level, interview-loop guides | Work-sample tasks, interview-style rounds, artefacts |
| Academic subject (statistics, macroeconomics) | University course syllabi (MIT OCW, Stanford, CMU), standard textbooks' contents, professional-body curricula | Problem sets and exams |
| Performance skill (music, chess, sport, speaking, cooking) | Graded exam syllabi and rating bands, coaching federation curricula, teacher method books and level ladders | Recorded performance against countable criteria, ratings, live performance |

Prefer official and institutional sources. If none matches the target exactly (no exam covers "sit in at a jam"), combine the nearest ones (a graded syllabus, an entry audition requirement, a teacher's level ladder) and say so in Appendix B. Use practitioner consensus only to fill what remains. Use a jobs connector for postings if one is available.

For an exam target, record its structure: parts, timings, scoring weights, pass mark. These drive time allocation (§3) and exit checks.

**b. Map the starting level**, including strengths that transfer from adjacent fields (an engineer who productized models knows serving and monitoring; an ETF investor knows diversification and costs). Note the learner's **stated weakness** verbatim ("my grammar falls apart when I write"); §3 gives it special treatment. If they name none, use the largest gap your research found and record that under Assumptions. A limitation the target doesn't require ("I can't read music" when the goal is playing by ear) isn't a weakness to drill.

**c. Classify every target item:**
- **New** → teach fully.
- **Partial** → consolidate and drill.
- **Known** → omit, or list once marked ◐ (diagnostic) so the learner verifies fast instead of restudying.

Aim for about 8–20 research calls (searches plus fetches) on the content gap. Drill-platform lookups (§5) are separate and should stay light. Keep the sources for Appendix B.

## 3. Design principles (evidence base)

Design backward and keep everything aligned, then choose activities the learning-science literature supports. The rationale is here so you can apply each with judgment rather than mechanically.

| Principle | Apply as | Evidence |
|---|---|---|
| Backward design / constructive alignment | Outcomes first → how each is proven (exit checks) → only then items and activities. Every item serves an outcome; every outcome has an exit check. | Biggs 1996; Wiggins & McTighe 1998 |
| Measurable outcomes | 3–6 outcomes, each with an observable verb at the right cognitive level (explain, apply, analyse, design, critique, perform), never "understand". | Bloom's revised taxonomy (Anderson & Krathwohl 2001) |
| Mastery gates | Each phase ends with a targeted exit check (a standalone exercise testing that phase's items); pass before advancing, otherwise loop back on the missed items. Pass mark: the exam's own mark for exam-format checks (Goethe modules: 60/100), or ~70% where no mark is published (CFA); ~80% for drills and quizzes; for performance or written work, a countable criterion ("≥ 7 of 8 choruses without losing the form", "≤ 4 errors per 100 words"). | Kulik, Kulik & Bangert-Drowns 1990: 108 studies, mean d ≈ 0.52 |
| Retrieval practice | Default activity is producing answers (drills, self-quizzes, writing, explaining or performing from memory), not rereading or watching. | Dunlosky et al. 2013 rated practice testing and spacing the only "high utility" techniques; Adesope et al. 2017 meta-analysis: practice tests beat restudying |
| Spacing | Revisit each phase's items later, at a gap of ≈ 10–20% of how long they must be retained. For an exam N weeks away, review earlier phases every 1–3 weeks; for open-ended goals, a weekly mixed review plus re-running one earlier exit check every ~4 weeks. | Cepeda et al. 2008 |
| Interleaving | Introduce a topic blocked, then mix it with confusable neighbours in later drills (Konjunktiv I vs II; L1 vs L2 regularization; P/E vs EV/EBITDA). Use less for plain vocabulary or expository reading. | Brunmair & Richter 2019: g = 0.42, strongest for similar categories |
| Expertise reversal | Worked examples and step-by-step explanations for genuinely new material; problem-first and faded examples where the learner has prior knowledge. Don't make experts sit through novice scaffolding. | Kalyuga et al. 2003 |
| Transparent, learner-centred framing | One-line *why* per phase, state how progress is checked, address the learner as "you". | Palmer et al. 2016; Eslami et al. 2024 (PLoS ONE) |
| Transfer task | Finish with a capstone matching how the target is proven: timed mock exam, interview-style round, portfolio project, recorded performance, rated games. | Constructive alignment: assess what they must actually do |

**Targeting the learner, not just the topic**
- **Stated weakness → standing routine.** The weakness the learner named gets a recurring routine in the Weekly rhythm that runs through *every* phase (e.g. weekly text → correction → rewrite from memory, with an error count tracked), not a single phase or item.
- **Productive skills run throughout.** Skills the target tests as performance (writing, speaking, playing, interviewing) appear in the Weekly rhythm from week 1, growing in difficulty, rather than being massed into one late phase.
- **Weight by the target.** Allocate time in proportion to what the exam, role or rating rewards (e.g. the exam part worth 60% of a module gets ~60% of that module's practice).
- **Protect the capstone.** Keep at least one official mock or sample set unseen for the capstone; use other or older sets for earlier exit checks. If the target has no mock material (a live jam, a real talk), the capstone is the closest full rehearsal before the real event.
- **Test only what's taught.** An exit check tests items from its own phase or earlier, never skills taught later.

**Sequencing rules**
1. Prerequisites before dependents (case endings before adjective endings; accounting statements before valuation; scales before improvisation).
2. If the start is uneven, open with a short diagnostic and consolidation phase.
3. Within those constraints, order by payoff: what the target weights most.
4. Mark the 2–4 highest-leverage phases ⭐ and give them more time. Phases can also be long simply because they hold a lot of material; ⭐ marks leverage, not length.
5. Last phase is polish and transfer: style, edge cases, exam technique, capstone.

## 4. Length budget

Concision is a feature, but completeness comes first: never drop an item the target spec requires just to fit a band. Size the syllabus to the gap.

| Gap | Signs | Items | Phases |
|---|---|---|---|
| Small | One sub-level or adjacent role, ≲ 150 h of work | 20–35 | 3–5 |
| Medium | One full level or exam band, a role step-up, ~150–400 h | 30–50 | 5–8 |
| Large | Several levels, a career change, > 400 h | 45–70 (hard ceiling) | 6–9 |

- Judge the gap from what must be learned, not from the hours the learner has. If it's on a boundary, pick the larger band.
- If the gap needs more than 70 items, it is too big for one document: write the syllabus for the first milestone (B1→B2 of B1→C1) and name what follows on a **Next milestone** line.
- An item is one line, ≲ 25 words including its examples. Lists of concrete forms are fine (they are the point); split an item rather than let it sprawl.
- Optional tracks count toward the band only for the track the learner will do. Number items in the order they appear, tracks included.
- Outcomes 3–6. Appendix A ≤ 10 rows, Appendix B ≤ 10 sources. Whole document ≲ 300 lines.
- Sanity check: total hours ÷ items should land around 3–12 h. Far below means the plan is crammed; far above means items are too coarse.
- If the learner's hours can't realistically close the gap (use official guided-hour estimates where they exist), say so under Pacing and give a realistic estimate, a fallback (e.g. sit exam modules separately) or a reduced target. Don't silently cram.

## 5. Drill platforms (Appendix A)

Retrieval and mastery need somewhere to practise with feedback, so give every phase at least one free option. This appendix is secondary to the syllabus itself: spend few calls on it. Not every field has auto-graded drills; work down this ladder and note the tier:

1. **Auto-graded drills** with instant feedback.
2. **Simulators and sandboxes**: paper trading, flight or clinical sims, coding sandboxes.
3. **Problem sets, past papers, quizzes with worked solutions**: official samples, OCW problem sets.
4. **Self-built retrieval**: an Anki deck made from the numbered items, or an AI tutor quizzing item ranges.
5. **Feedback loops for performance skills**: record → compare against a reference or rubric; correction communities; a conversation partner; a coach.

Criteria: free or a substantial free tier; actually covers the items it's mapped to (a Keras course doesn't drill a PyTorch item); reputable. Confirm a platform exists and is free with one search when you aren't already sure; if a page can't be reached but the platform is well known, keep it, otherwise drop it. List paid-only tools only under "Optional (paid)".

Reference-quality examples to calibrate against:
- **German** — [DeutschAkademie grammar trainer](https://www.deutschakademie.de/en/learn-german-online/#trainer) (tier 1): 25,000+ free teacher-written exercises, CEFR A1–C1, browsable [by level](https://www.deutschakademie.de/online-deutschkurs/nach-level/) and [by topic](https://www.deutschakademie.de/online-deutschkurs/nach-thema/).
- **SWE → data science / ML** — [Deep-ML](https://www.deep-ml.com) (tier 1): LeetCode-style ML problems in the browser with instant test feedback, from linear algebra to deep learning. Pair with [Kaggle Learn](https://www.kaggle.com/learn) (tier 1, in-browser notebook exercises) and [Tensor Puzzles](https://github.com/srush/Tensor-Puzzles) (tier 1, 21 PyTorch puzzles).
- **Financial markets** — [Investopedia Stock Simulator](https://www.investopedia.com/simulator/) (tier 2): free paper trading including options. [Damodaran Online](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/home.htm) (tier 3): free NYU valuation and corporate finance classes, valuation spreadsheets and market datasets to practise on real companies.

Map each platform to the item numbers it drills, so the learner knows where to practise item 22.

## 6. Write the document

Follow this skeleton. Density is the point: an item is a line, not a paragraph. Write in the user's language; keep subject terms in the target language where that is the subject (German grammar terms stay German).

```markdown
# Syllabus: <Topic> — <Start> → <Target>

**For:** <one-line learner profile> · **Horizon:** <N weeks × H h/week ≈ T h> · **Proof of target:** <exam / role / rating / portfolio>
**Assumptions:** <only if any were made>

## Gap at a glance
| Area | Now | Target | Phase |
|---|---|---|---|
| <area> | <evidence of current level> | <what the target requires> | <n> |
(3–7 rows; include the stated weakness)

## Outcomes
By the end you can:
1. <observable verb> …
(3–6 outcomes)

## How to use this syllabus
- Work phases in order; pass each exit check before moving on (pass marks are stated per check).
- Per session: ~70% retrieval (drills, recall, producing, performing), ~30% new input.
- ⭐ highest leverage · ◐ diagnostic only (you likely know it — verify fast, move on) · Tiers in Appendix A: 1 auto-graded · 2 simulator · 3 problem sets · 4 self-built flashcards · 5 feedback loop

## Weekly rhythm
- <standing routine for the stated weakness, with what is tracked>
- <productive-skill practice, growing across phases>
- <spaced, mixed review of earlier phases at the interval from §3>
(3–5 lines; these routines sit inside each phase's hours, and a week's hours sum to H)

## Phase 1 — <Name> (≈ <weeks>, <hours> h)
*Why first: <one line>*
1. <Item> — <concrete forms or examples>
2. …
**Exit check:** <targeted, testable exercise> · pass: <mark> (Outcome <n>)

## Phase 2 — <Name> ⭐ (≈ <weeks>, <hours> h)
… numbering continues across phases …

## Capstone
<transfer task matching how the target is proven, using material reserved for it> · pass: <mark>

## Pacing
<total hours, per-phase split incl. capstone, why the ⭐ phases get more; realism note and fallback if needed — 2–5 lines>
**Next milestone:** <the natural next step after this target>

## Appendix A — Free drill platforms
| Platform | Tier | Drills items | Notes |
|---|---|---|---|
| [Name](url) | 1 | 1–5, 18–21 | free tier, format |

## Appendix B — Sources
- [Title](url) — what it established (target spec, exam facts, gap evidence, or research that shaped the design)
```

Rules:
- Number items continuously across phases (1 … N) so they can be referenced by number; outcomes are numbered separately.
- Items are content or skills to master; standing routines and exam-technique habits go in the Weekly rhythm or the final phase.
- Name concrete forms over categories ("je…desto, entweder…oder"; "bias–variance, L1/L2, early stopping"; "FCFF, WACC, terminal value").
- Phase hours plus capstone hours equal the horizon.
- No filler: no motivational paragraphs, no generic study tips beyond "How to use" and "Weekly rhythm".

**Excerpt — German B1 → B2 (examined field)**
```markdown
## Phase 4 — Passive voice ⭐ (≈ 2 weeks, 16 h)
*Why here: builds on Phase 3's werden and Partizip II; heavily tested in B2 reading and writing.*
18. Vorgangspassiv, all tenses (wird / wurde / ist … worden)
19. Passive with modal verbs (muss gemacht werden)
20. Zustandspassiv vs Vorgangspassiv (ist geöffnet vs wird geöffnet)
21. Passive alternatives: man, sich lassen + Inf., sein + zu + Inf., -bar adjectives
**Exit check:** rewrite 20 active sentences mixing all four forms · pass: ≥ 17 correct (Outcome 2)
```

**Excerpt — chess 1200 → 1600 (performance skill)**
```markdown
## Phase 2 — Tactical pattern recognition ⭐ (≈ 6 weeks, 36 h)
*Why here: at this rating most games are decided by a missed two-move tactic.*
7. Forks, pins, skewers, discovered attacks — spot them in under 30 s
8. Removing the defender, overloading, deflection
9. Back-rank and smothered mates; mating nets with Q + N, R + R
10. Blunder check before every move: checks, captures, threats (yours and theirs)
**Exit check:** 30 mixed puzzles rated 1500–1700 · pass: ≥ 24 solved, untimed first attempt (Outcome 1)
```

## 7. Check and deliver

Before delivering, confirm:
- Every outcome has phases serving it and an exit check proving it; no item serves no outcome; no exit check tests a later phase's items.
- The stated weakness has a standing routine across all phases; productive skills are not massed into one phase.
- Known items are omitted or marked ◐; nothing the target spec requires is missing. Exam facts (parts, weights, pass marks) match the official source.
- Item and phase counts sit inside the band; hours ÷ items is plausible; hours add up.
- Every phase has at least one Appendix A row.

Unless the user gave a path, save as `syllabus-<topic>-<start>-to-<target>.md` (kebab-case) and send it with SendUserFile (if unavailable, give the path). Reply in one or two sentences: the plan's shape (phases, items, total hours) and one useful next step, such as a week-by-week calendar or an Anki deck of the items.