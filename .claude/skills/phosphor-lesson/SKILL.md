---
name: "phosphor-lesson"
description: "Builds an interactive Phosphor-style lesson for any concept (readings with embedded multiple-choice and Claude-graded free-answer drills, plus a cumulative module exam), seeded by running the syllabus skill first. Use for interactive lessons, courseware, quizzes, self-study modules."
---

# Phosphor-style interactive lesson

Build one interactive lesson page for any concept, in the pattern of Phosphor (Bard, iTextbooks'26 @ AIED 2026): short readings with embedded formative quizzes, free answers graded live by Claude against an instructor rubric, and a cumulative module exam. Publish it as an Artifact that calls Claude for grading.

Three findings from that pilot shape every content rule below. Keep them in mind when you make judgment calls:
- Quiz practice predicted exam gains only where students had to **construct** answers. Multiple-choice-only quizzes showed no dose effect. So free-answer items are the backbone, and multiple choice is a quick check.
- The **cumulative module review** was the single strongest lever. So the exam draws fresh items from every part and interleaves them.
- Students skipped the chat assistant. So the page has no chat; feedback arrives on the answer itself.

Workflow: **1. Seed with the syllabus → 2. Choose the module → 3. Write the content → 4. Fill course.json → 5. Build and validate → 6. Design pass and publish → 7. Deliver.** Put these on a task list.

## 1. Seed with the syllabus

Invoke the `syllabus` skill with the Skill tool (use the exact name from the skills listing; it may carry a plugin prefix, e.g. `anthropic-skills:syllabus`). Hand it the concept plus anything the user already said: starting level, target, hours, deadline, weak spots. Let it run its own intake, research and checks, and let it deliver its syllabus file. That file is the seed for the lesson.

- Do not end the turn when the syllabus is delivered. Its closing reply is not your final answer; continue with step 2.
- **Reuse instead of rerun** when a syllabus for the same topic, start and target is already in the conversation, attached, or in the working folder. Read it and skip to step 2.
- If no syllabus skill is listed, say so in one line and build a minimal seed yourself: 3–6 searches for the target's official spec, then 3–6 outcomes and a phase list with numbered one-line items, in the syllabus skill's format.

From the syllabus, carry forward: the learner profile, the phase list with item numbers, ⭐ and ◐ marks, each phase's *Why* line and exit check, the stated weakness, the language the learner writes in, and the sources (they back your content).

## 2. Choose the module

One lesson covers **one syllabus phase**, like one Phosphor module.

- If the user named a phase, item range or sub-topic, use it.
- Otherwise ask once with AskUserQuestion, listing up to four phases (name and item numbers). Recommend the first phase that has new material, preferring a ⭐ phase when two fit. If no one is there to answer, take that recommendation and say so in the final reply.
- Group the phase's items into **2–5 parts**; one part covers 1–2 consecutive, related items. If the phase holds more than about 8 items, build the first 3–5 coherent parts and name the rest as the next lesson.
- **Pass mark:** take it from the phase's exit check. Convert counts to a percentage (≥ 17 of 20 → 85). Use 70 when the exit check states none.
- Items marked ◐ (diagnostic) get at most one part, with a short reading and problem-first drills.

## 3. Write the content

Write everything from the syllabus items and its sources. Check facts the sources don't cover. **Compute every numeric answer in code** (Bash/python) before it goes into a key, a rubric or a model answer.

**Language.** Write readings, prompts and model answers in the subject language when the subject is a language and the learner is at B1 or above (a German B2 lesson is in German). In every other case, use the language the learner writes in. Set `uiLang` and the `ui` strings the same way; the template's defaults are English, so supply every `ui` key when the UI is in another language. `feedbackLanguage` is the learner's own language.

**Readings (per part).**
- 2–4 paragraphs, each under about 90 words, built on the concrete forms named in the syllabus item ("Vorgangspassiv: wird / wurde / ist … worden"; "`x̄ ± z*·σ/√n`").
- For new material, add an `example` block: a worked example in 3–6 short steps (expertise reversal: novices need the worked example).
- For material the learner partly knows, one short paragraph, then straight to drills.
- Inline markup is limited to `**bold**` and `` `code` ``. For longer code or formulas, put them in an item's `code` field, which renders as a preformatted block.

**Drills (per part).** 2–3 items: at least one `mcq` and at least one `crq`. Across the whole lesson and exam, at least half of the items should be `crq`.

- **mcq:** 3–5 options, exactly one defensible answer. Each distractor is a real, common error, not a joke option. `why` states the rule in one sentence. Re-read every key before building.
- **crq:** a narrow production task with a gradable target: transform this sentence, compute this value and show the step, explain X in one or two sentences, write the one line of code that does Y, produce a sentence using Z. Avoid open essays; the grader needs a clear target.
- **rubric** (read only by the grader, so write it in English): the expected answer and every accepted alternative; the single key skill being tested; explicit conditions for full marks, partial credit and incorrect; numeric tolerance or rounding where relevant. Model it on this one:

  > Expected: 'Das neue Museum wird von einem bekannten Architekten entworfen.' Require wird + entworfen and the agent as 'von einem bekannten Architekten' (dative, weak noun -en). Full marks only if all correct. Partial if agent dropped or ending wrong ('Architekt'). Incorrect if Zustandspassiv or still active.

- **model:** the model answer, shown when AI grading is unavailable and the learner marks themselves.

**Exam pool (per part).** The exam draws `examPerSection` items per part (default 3), always at least one `mcq` and one `crq`. Give each part **4–6 pool items** with at least 2 `crq`, so new draws differ.
- Every pool item is new. Never reuse or lightly paraphrase a lesson drill; the exam tests retrieval, not recognition.
- Pitch difficulty at the phase's exit check.
- Include confusable neighbours where the subject has them (Konjunktiv I vs II, L1 vs L2, P/E vs EV/EBITDA): the exam mixes parts in random order, and interleaving works best on similar categories.
- Test only this module's items and earlier ones, never later material.

## 4. Fill course.json

Write one JSON file in the scratchpad. Fields:

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | short slug; keys the learner's best score in their browser |
| `title` | yes | page heading, e.g. "Grammatikwerkstatt" |
| `pageTitle` | no | browser-tab and gallery name if it differs from `title`, e.g. "Grammatikwerkstatt B2" |
| `subtitle` | no | the parts' titles joined with " · " |
| `level` | no | badge text, e.g. "Niveau B2", "Intro statistics" |
| `subject` | yes | one line for the grader: subject, scope, level |
| `contentLang`, `uiLang` | yes | BCP-47 codes, e.g. "de", "en" |
| `feedbackLanguage` | yes | language name for grader feedback, e.g. "English" |
| `passMark` | yes | integer percent |
| `examPerSection` | no | items per part in each exam draw (default 3) |
| `examNote` | no | replaces the exam's one-line description |
| `graderTier` | no | "default" (use this) or "complex" for hard reasoning subjects |
| `ui` | when not English | overrides for UI strings; keys and English defaults are in `UI_DEFAULT` in the template |
| `sections[]` | yes | `{id, title, short?, gloss?, reading[], example?: {title, steps[]}, drills[]}`; `short` labels the part on exam chips and the score breakdown |
| `pool[]` | yes | exam items, each with `section` set to a section `id` |

Item fields: `id` (unique across the file), `type` ("mcq" or "crq"), `prompt`, optional `code`. For mcq: `options[]`, `answer` (0-based index), `why`. For crq: `rubric`, `model`, optional `mono: true` (monospace answer box for code or formulas), `rows`, `placeholder`.

## 5. Build and validate

The template and the build script are embedded at the end of this file. Extract them next to course.json (`SKILL_DIR` is the base directory shown when this skill loaded):

```bash
python3 - "$SKILL_DIR/SKILL.md" "$OUT" <<'EOF'
import re, sys, pathlib
src = pathlib.Path(sys.argv[1]).read_text(); out = pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
for name in ("template.html", "build.mjs"):
    body = re.search(r"<!-- BEGIN %s -->\n````[a-z]*\n(.*?)\n````\n<!-- END %s -->" % (re.escape(name), re.escape(name)), src, re.S).group(1)
    (out / name).write_text(body + "\n")
EOF
node "$OUT/build.mjs" "$OUT/template.html" "$OUT/course.json" "$OUT/lesson.html"
```

If the base directory isn't known, write the two files out with the Write tool, copied exactly from the blocks below.

`build.mjs` validates the course and writes the page. Fix every `error:` line in course.json and rebuild. Treat `warn:` lines as content problems to fix unless there is a reason not to (a tiny phase with nothing more to test).

## 6. Design pass and publish

1. Load the `artifact-design` skill before publishing; the Artifact tool requires it.
2. The template's layout and script stay as they are. The only design edits are in `lesson.html`'s `<style>` head: the color tokens (in all three blocks: `:root`, the dark media query, `[data-theme="dark"]`) and the Google Fonts link with the `--f-*` tokens. Pick them from the subject's world: a palette and a display/body face pair that fit the field, not the same look for every lesson. Keep contrast legible in both themes.
3. Take one preview look if the session offers one, fix what it shows, then publish:
   - `file_path`: the built `lesson.html`
   - `capabilities`: `{"sample": {}}` (this is what lets the page ask Claude to grade)
   - `icon`: one plain word, e.g. "book"
   - `description`: one sentence naming the subject, level and parts
4. To revise later, edit course.json, rebuild to the same path, redo the token edits, and publish the same `file_path` again.

You cannot exercise the grading yourself: it runs only after a viewer allows it. Say so in one line.

## 7. Deliver

Reply in two or three sentences:
- what the lesson covers: the syllabus phase, its parts, and the item numbers it draws on;
- that the first free answer asks the viewer to allow Claude, grading runs on their own Claude usage, and without it they get model answers to mark themselves;
- one next step, usually the next syllabus phase as the next lesson, or a larger exam pool.

Don't recap the steps, don't paste the URL (the artifact card carries it), and don't describe the page's layout.

## Embedded files

Copy these exactly. The template's `__TITLE__` and `__COURSE_JSON__` placeholders are filled by `build.mjs`; nothing else in the template changes except the design tokens in step 6.

<!-- BEGIN template.html -->
````html
<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Semi+Condensed:wght@500;600;700&family=Barlow:wght@400;500;600;700&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&family=JetBrains+Mono:wght@400;600&display=swap">
<style>
/* Layout: one reading column (~68ch) under a sticky tab bar; the module exam is a printed answer sheet with numbered tasks and a rubber-stamp verdict. */
:root{
  --paper:#ECEEF1; --sheet:#FAFBFC; --ink:#1A1E26; --ink-soft:#5C6370; --rule:#D3D8E0;
  --accent:#1F3FA3; --accent-soft:#E3E8F7; --on-accent:#FFFFFF;
  --ok:#2B6A40; --ok-soft:#E1EFE5; --part:#8A5A12; --part-soft:#F5EAD6; --bad:#A3271F; --bad-soft:#F6E1DF;
  --f-display:"Barlow Semi Condensed","Arial Narrow",system-ui,sans-serif;
  --f-body:"Source Serif 4",Charter,"Iowan Old Style",Georgia,serif;
  --f-ui:"Barlow","Segoe UI",system-ui,-apple-system,sans-serif;
  --f-mono:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}
@media (prefers-color-scheme: dark){ :root:not([data-theme="light"]){
  --paper:#12151B; --sheet:#1A1E26; --ink:#E4E7EC; --ink-soft:#9AA2AF; --rule:#2C323D;
  --accent:#8EA6F2; --accent-soft:#222B45; --on-accent:#0F1320;
  --ok:#7CC795; --ok-soft:#1C2E23; --part:#E0B46A; --part-soft:#33291A; --bad:#F08A80; --bad-soft:#3A1F1D;
  color-scheme:dark;
}}
:root[data-theme="dark"]{
  --paper:#12151B; --sheet:#1A1E26; --ink:#E4E7EC; --ink-soft:#9AA2AF; --rule:#2C323D;
  --accent:#8EA6F2; --accent-soft:#222B45; --on-accent:#0F1320;
  --ok:#7CC795; --ok-soft:#1C2E23; --part:#E0B46A; --part-soft:#33291A; --bad:#F08A80; --bad-soft:#3A1F1D;
  color-scheme:dark;
}
*{box-sizing:border-box}
body{background:var(--paper);color:var(--ink);font:16px/1.5 var(--f-ui);padding-inline:16px;padding-block:0 64px}
.wrap{max-width:720px;margin-inline:auto}
h1,h2,h3{text-wrap:balance;margin:0}
button{font:inherit;color:inherit}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
code{font:0.9em var(--f-mono);background:var(--accent-soft);padding:1px 5px;border-radius:4px}
pre{font:14px/1.5 var(--f-mono);background:var(--paper);border:1px solid var(--rule);border-radius:8px;padding:10px 12px;margin:0 0 12px;overflow-x:auto;white-space:pre}

.bar{position:sticky;top:env(safe-area-inset-top,0px);z-index:5;margin-inline:-16px;padding:10px 16px;background:var(--paper);border-bottom:1px solid var(--rule)}
.bar-in{max-width:720px;margin-inline:auto;display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.tabs{display:flex;gap:4px;background:var(--sheet);border:1px solid var(--rule);border-radius:999px;padding:3px}
.tab{border:0;background:transparent;padding:6px 14px;border-radius:999px;font:600 14px var(--f-ui);letter-spacing:.02em;color:var(--ink-soft);cursor:pointer}
.tab[aria-selected="true"]{background:var(--accent);color:var(--on-accent)}
.meter{display:flex;align-items:center;gap:10px;flex:1;min-width:180px}
.meter-track{flex:1;max-width:220px;height:6px;background:var(--rule);border-radius:999px;overflow:hidden}
.meter-fill{height:100%;width:0;background:var(--accent);transition:width .3s}
.meter-label{font:500 13px var(--f-ui);color:var(--ink-soft);font-variant-numeric:tabular-nums;white-space:nowrap}

.hero{padding-block:36px 28px}
.level{display:inline-block;font:700 12px var(--f-ui);letter-spacing:.16em;text-transform:uppercase;color:var(--paper);background:var(--ink);padding:3px 10px;border-radius:4px;margin-bottom:14px}
.hero h1{font:700 clamp(34px,8vw,52px)/1.02 var(--f-display);letter-spacing:-.005em}
.hero p{font:18px/1.45 var(--f-body);color:var(--ink-soft);margin:8px 0 0}

.section{padding-block:8px 36px}
.sec-head{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}
.sec-no{font:700 13px var(--f-ui);letter-spacing:.14em;text-transform:uppercase;color:var(--accent)}
.sec-head h2{font:600 28px/1.1 var(--f-display)}
.gloss{font:600 12px var(--f-ui);letter-spacing:.12em;text-transform:uppercase;color:var(--ink-soft);margin:6px 0 16px}
.reading p{font:17px/1.62 var(--f-body);margin:0 0 14px;max-width:68ch}
.reading b{font-weight:600}
.example{border-left:3px solid var(--accent);background:var(--sheet);border-radius:0 10px 10px 0;padding:12px 16px;margin:4px 0 16px}
.example h3{font:700 12px var(--f-ui);letter-spacing:.12em;text-transform:uppercase;color:var(--accent);margin-bottom:6px}
.example ol{margin:0;padding-left:20px;font:16px/1.55 var(--f-body)}
.example li{margin:2px 0}
.drill{display:grid;gap:14px;margin-top:18px}
.card{background:var(--sheet);border:1px solid var(--rule);border-radius:12px;padding:18px;min-width:0}
.kind{font:700 11px var(--f-ui);letter-spacing:.1em;text-transform:uppercase;color:var(--ink-soft)}
.kind.ai{color:var(--accent)}
.prompt{font:600 16px/1.45 var(--f-body);margin:8px 0 12px}
.opts{display:grid;gap:8px}
.opt{text-align:left;font:15px/1.4 var(--f-body);background:var(--paper);border:1.5px solid var(--rule);border-radius:9px;padding:10px 13px;cursor:pointer;transition:border-color .12s,background .12s}
.opt:hover:not(:disabled){border-color:var(--accent)}
.opt:disabled{cursor:default}
.opt.is-picked{border-color:var(--accent);background:var(--accent-soft)}
.opt.is-ok{border-color:var(--ok);background:var(--ok-soft);color:var(--ok)}
.opt.is-bad{border-color:var(--bad);background:var(--bad-soft);color:var(--bad)}
.why{font:14px/1.5 var(--f-ui);color:var(--ink-soft);margin:10px 0 0}
textarea{width:100%;font:15px/1.5 var(--f-body);color:var(--ink);background:var(--paper);border:1.5px solid var(--rule);border-radius:9px;padding:10px 13px;resize:vertical}
textarea.mono{font:14px/1.5 var(--f-mono)}
textarea:focus{border-color:var(--accent);outline:none}
textarea[readonly]{opacity:.85}
.row{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-top:10px}
.btn{border:0;background:var(--accent);color:var(--on-accent);font:600 14px var(--f-ui);letter-spacing:.02em;padding:9px 18px;border-radius:8px;cursor:pointer}
.btn:disabled{opacity:.55;cursor:default}
.status{font:14px/1.5 var(--f-ui);color:var(--ink-soft);margin:10px 0 0}
.status.err{color:var(--bad)}

.result{margin-top:12px;border:1px solid var(--rule);border-radius:10px;overflow:hidden;background:var(--sheet)}
.result-head{display:flex;align-items:center;gap:10px;padding:8px 13px;border-bottom:1px solid var(--rule)}
.pill{font:700 12px var(--f-ui);letter-spacing:.04em;padding:2px 10px;border-radius:999px}
.v-correct .pill{background:var(--ok-soft);color:var(--ok)}
.v-partial .pill{background:var(--part-soft);color:var(--part)}
.v-incorrect .pill{background:var(--bad-soft);color:var(--bad)}
.score{font:600 13px var(--f-ui);color:var(--ink-soft);font-variant-numeric:tabular-nums}
.fb{font:15px/1.55 var(--f-ui);margin:0;padding:11px 13px 0}
.corr{font:italic 15px/1.5 var(--f-body);color:var(--accent);margin:10px 13px 12px;padding-left:11px;border-left:2px solid var(--accent);white-space:pre-wrap;overflow-wrap:anywhere}
.self-note{font:14px/1.5 var(--f-ui);color:var(--ink-soft);margin:0;padding:11px 13px 0}
.self-btns{display:flex;gap:6px;flex-wrap:wrap;padding:0 13px 12px}
.chip{border:1.5px solid var(--rule);background:transparent;border-radius:999px;padding:4px 12px;font:600 13px var(--f-ui);cursor:pointer}
.chip.is-on{border-color:var(--accent);background:var(--accent-soft);color:var(--accent)}

.cta{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;border-top:2px solid var(--ink);padding-top:18px;margin-top:8px}
.cta p{font:16px/1.5 var(--f-body);margin:0;max-width:44ch}

.sheet{background:var(--sheet);border:1px solid var(--rule);border-radius:4px;margin-top:28px;box-shadow:0 1px 0 var(--rule),0 12px 28px -18px rgba(20,30,60,.35)}
.sheet-head{padding:22px 22px 18px;border-bottom:2px solid var(--ink)}
.sheet-head h2{font:700 30px/1.05 var(--f-display);letter-spacing:.01em}
.sheet-head .sub{font:15px/1.5 var(--f-body);color:var(--ink-soft);margin:6px 0 0;max-width:60ch}
.fields{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px 20px;margin:18px 0 0}
.field{min-width:0}
.field dt{font:600 11px var(--f-ui);letter-spacing:.12em;text-transform:uppercase;color:var(--ink-soft)}
.field dd{margin:2px 0 0;font:600 17px var(--f-display);border-bottom:1px solid var(--rule);padding-bottom:3px;font-variant-numeric:tabular-nums}
.verdict{display:none;padding:22px;border-bottom:1px solid var(--rule);gap:18px 28px;align-items:center;grid-template-columns:auto 1fr}
.verdict.on{display:grid}
.big{font:700 56px/1 var(--f-display);font-variant-numeric:tabular-nums}
.big small{font:600 14px var(--f-ui);color:var(--ink-soft);display:block;letter-spacing:.06em;margin-top:6px;text-transform:uppercase}
.stamp{justify-self:start;display:inline-flex;flex-direction:column;align-items:center;padding:6px 16px 7px;border:4px double currentColor;border-radius:6px;font:700 22px/1.1 var(--f-display);letter-spacing:.16em;text-transform:uppercase;transform:rotate(-7deg);animation:stampIn .45s cubic-bezier(.2,1.5,.4,1) both;text-align:center}
.stamp span{font:600 11px var(--f-ui);letter-spacing:.14em}
.stamp.pass{color:var(--ok)} .stamp.fail{color:var(--bad)}
.stamp.pending{color:var(--ink-soft);animation:none}
@keyframes stampIn{from{transform:rotate(-7deg) scale(1.7);opacity:0}to{transform:rotate(-7deg) scale(1);opacity:1}}
.topics{grid-column:1/-1;display:grid;gap:8px}
.trow{display:grid;grid-template-columns:minmax(0,160px) 1fr 48px;gap:10px;align-items:center;font:500 14px var(--f-ui)}
.trow > span:first-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ttrack{height:8px;background:var(--rule);border-radius:999px;overflow:hidden}
.tfill{height:100%;background:var(--accent)}
.tval{text-align:right;font-variant-numeric:tabular-nums;color:var(--ink-soft)}
.tasks{list-style:none;margin:0;padding:0}
.task{padding:20px 22px;border-bottom:1px solid var(--rule);min-width:0}
.task-head{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
.task-no{font:700 15px var(--f-display);letter-spacing:.06em;text-transform:uppercase}
.topic{font:600 12px var(--f-ui);color:var(--accent);background:var(--accent-soft);padding:1px 8px;border-radius:999px}
.sheet-foot{padding:18px 22px 22px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.sheet-foot .count{font:500 14px var(--f-ui);color:var(--ink-soft);font-variant-numeric:tabular-nums}
.note{font:13px/1.6 var(--f-ui);color:var(--ink-soft);margin-top:20px}
@media (max-width:520px){ .verdict{grid-template-columns:1fr} .trow{grid-template-columns:minmax(0,110px) 1fr 44px} .sheet-head,.task,.sheet-foot,.verdict{padding-inline:16px} }
@media (prefers-reduced-motion:reduce){ .stamp{animation:none} .meter-fill{transition:none} }
</style>

<div class="bar"><div class="bar-in">
  <div class="tabs" role="tablist">
    <button class="tab" role="tab" id="tab-lesson" aria-selected="true" aria-controls="pane-lesson"></button>
    <button class="tab" role="tab" id="tab-exam" aria-selected="false" aria-controls="pane-exam"></button>
  </div>
  <div class="meter"><div class="meter-track"><div class="meter-fill" id="meter-fill"></div></div><span class="meter-label" id="meter-label"></span></div>
</div></div>

<div class="wrap">
  <header class="hero">
    <span class="level" id="hero-level"></span>
    <h1 id="hero-title"></h1>
    <p id="hero-sub"></p>
  </header>
  <main>
    <section id="pane-lesson" role="tabpanel" aria-labelledby="tab-lesson"></section>
    <section id="pane-exam" role="tabpanel" aria-labelledby="tab-exam" hidden></section>
  </main>
  <p class="note" id="footnote"></p>
</div>

<!-- COURSE DATA: the only part to replace. Pure JSON; write "<\/" instead of "</" inside strings. -->
<script type="application/json" id="course">
__COURSE_JSON__
</script>

<script>
const COURSE = JSON.parse(document.getElementById("course").textContent);
const UI_DEFAULT = {
  tabLesson: "Lesson", tabExam: "Module exam", part: "Part",
  mcq: "Multiple choice", crq: "Free answer · AI-graded", mcqShort: "Choice", crqShort: "Free answer",
  placeholder: "Your answer …", submitAnswer: "Submit answer", grading: "Grading …",
  correct: "Correct", partial: "Partly correct", incorrect: "Not correct", noFeedback: "No feedback received.",
  selfNote: "Compare your answer with the model answer and mark yourself.", unanswered: "Not answered. Model answer:",
  selfRight: "Right", selfPartly: "Partly", selfWrong: "Wrong",
  meter: "{ok}/{n} correct · {done} attempted",
  ctaText: "Worked through every part? The module exam mixes new tasks from all parts.", goExam: "Go to the module exam",
  examTitle: "Module exam",
  examSub: "{n} tasks from all parts, mixed. Free answers are graded only after you submit, so you write without help, as in a real exam.",
  fDate: "Date", fTasks: "Tasks", fPass: "Pass mark", fBest: "Best result",
  task: "Task", answered: "{a} of {n} answered",
  submitExam: "Submit exam", gradingNote: "Claude grades all free answers together. This usually takes under a minute.",
  newDraw: "Draw a new exam", newDrawNote: "A new draw gives different tasks in a different order.",
  overall: "Overall score", passed: "Passed", failed: "Not passed", open: "Open",
  passLine: "Pass mark {p} %", selfMissing: "{k} still to self-mark",
  errRate: "Too many requests at once. Wait a moment, then submit again.",
  errSession: "Your session has expired. Sign in again, then submit.",
  errJson: "The grading came back incomplete. Submit again.",
  errRefused: "This answer could not be graded. Rephrase it and submit again.",
  errGeneric: "Grading failed. Submit again.",
  footnote: "Free answers are graded by Claude against a rubric; multiple-choice tasks are checked on the page. If AI grading is unavailable, you see the model answer and mark yourself.",
  dateLocale: "en-GB"
};
const UI = Object.assign({}, UI_DEFAULT, COURSE.ui || {});
const fmt = (s, v) => String(s).replace(/\{(\w+)\}/g, (_, k) => (k in v ? v[k] : ""));
const PASS = Number(COURSE.passMark) || 70;
const PER_SECTION = Number(COURSE.examPerSection) || 3;
const LANG = COURSE.contentLang || "en";
const SECTIONS = COURSE.sections;
const SEC_TITLE = Object.fromEntries(SECTIONS.map(s => [s.id, s.short || s.title]));
const STORE_KEY = "phx-best-" + (COURSE.id || COURSE.title);

/* ---------- helpers ---------- */
function el(tag, attrs, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === false || v == null) continue;
    if (k === "class") n.className = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v === true ? "" : v);
  }
  for (const c of kids.flat()) { if (c == null || c === false) continue; n.append(c instanceof Node ? c : document.createTextNode(String(c))); }
  return n;
}
/* Inline markup: **bold** and `code` only; everything else is plain text. */
function rich(text) {
  const out = [];
  String(text).split(/(\*\*[^*]+\*\*|`[^`]+`)/g).forEach(part => {
    if (!part) return;
    if (part.startsWith("**") && part.endsWith("**")) out.push(el("b", {}, part.slice(2, -2)));
    else if (part.startsWith("`") && part.endsWith("`")) out.push(el("code", {}, part.slice(1, -1)));
    else out.push(document.createTextNode(part));
  });
  return out;
}
const shuffle = a => { a = a.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch {} }
};
function promptBlock(item) {
  return [el("p", { class: "prompt", lang: LANG }, rich(item.prompt)), item.code ? el("pre", {}, item.code) : null];
}
function answerBox(item, id, label) {
  return el("textarea", { id, rows: String(item.rows || 3), lang: LANG, class: item.mono ? "mono" : null, placeholder: item.placeholder || UI.placeholder, "aria-label": label, spellcheck: item.mono ? "false" : null });
}

/* ---------- grading via Claude ---------- */
const samplePromise = (window.claude && window.claude.use) ? window.claude.use("sample").catch(() => null) : Promise.resolve(null);
const ABSENT = new Set(["not_granted", "sampling_disabled", "not_declared", "capability_disabled", "capability_removed"]);
const GRADER = [
  "You are a strict but fair examiner for: " + (COURSE.subject || COURSE.title) + (COURSE.level ? " (level: " + COURSE.level + ")" : "") + ".",
  "Grade each learner answer ONLY against its rubric. Accept any answer the rubric accepts, and any equivalent correct answer the rubric did not foresee.",
  "Reply with only a JSON array, one object per answer, in the same order as given:",
  '[{"id": "<id>", "verdict": "correct" | "partial" | "incorrect", "score": <integer 0-100>, "feedback": "<2-3 sentences addressed to the learner, naming the specific point>", "correction": "<the corrected version of THEIR answer, or the model answer if theirs is unusable>"}]',
  "Write feedback in " + (COURSE.feedbackLanguage || "English") + ". Keep subject-language examples in the subject language.",
  "Scores: correct 80-100, partial 40-79, incorrect 0-39."
].join("\n");

async function gradeBatch(sample, items) {
  const payload = items.map(it => ({ id: it.id, task: it.prompt + (it.code ? "\n" + it.code : ""), rubric: it.rubric, answer: it.answer }));
  const res = await sample.json(GRADER + "\n\nANSWERS:\n" + JSON.stringify(payload, null, 1), { modelTier: COURSE.graderTier || "default" });
  const arr = Array.isArray(res) ? res : (res && Array.isArray(res.results) ? res.results : []);
  return items.map((it, i) => normResult(arr.find(x => x && String(x.id) === it.id) || arr[i] || {}));
}
function normResult(r) {
  const score = Math.max(0, Math.min(100, Math.round(Number(r.score) || 0)));
  const verdict = ["correct", "partial", "incorrect"].includes(r.verdict) ? r.verdict : (score >= 80 ? "correct" : score >= 40 ? "partial" : "incorrect");
  return { verdict, score, feedback: String(r.feedback || ""), correction: String(r.correction || "") };
}
function errText(e) {
  const c = e && e.code;
  if (c === "rate_limited") return UI.errRate;
  if (c === "session_expired") return UI.errSession;
  if (c === "invalid_json" || c === "empty_completion") return UI.errJson;
  if (c === "refused") return UI.errRefused;
  return UI.errGeneric;
}
const VERDICT = () => ({ correct: UI.correct, partial: UI.partial, incorrect: UI.incorrect });
function resultCard(r) {
  return el("div", { class: "result v-" + r.verdict },
    el("div", { class: "result-head" }, el("span", { class: "pill" }, VERDICT()[r.verdict]), el("span", { class: "score" }, r.score + " / 100")),
    el("p", { class: "fb" }, r.feedback || UI.noFeedback),
    r.correction ? el("p", { class: "corr", lang: LANG }, r.correction) : el("div", { style: "height:12px" }));
}
function selfCheck(item, onScore, current, answered = true) {
  const btns = el("div", { class: "self-btns" });
  if (answered) {
    [[UI.selfRight, 100, "correct"], [UI.selfPartly, 50, "partial"], [UI.selfWrong, 0, "incorrect"]].forEach(([label, s, v]) => {
      const b = el("button", { class: "chip" + (current && current.verdict === v ? " is-on" : ""), type: "button" }, label);
      b.addEventListener("click", () => { [...btns.children].forEach(c => c.classList.remove("is-on")); b.classList.add("is-on"); onScore(s, v); });
      btns.append(b);
    });
  }
  return el("div", { class: "result" },
    el("p", { class: "self-note" }, answered ? UI.selfNote : UI.unanswered),
    el("p", { class: "corr", lang: LANG }, item.model),
    btns);
}

/* ---------- lesson ---------- */
const lessonScores = {};
const LESSON_TOTAL = SECTIONS.reduce((n, s) => n + s.drills.length, 0);

function lessonMCQ(item) {
  const box = el("div", { class: "opts" });
  const why = el("p", { class: "why", hidden: true }, rich(item.why || ""));
  item.options.forEach((o, i) => {
    const b = el("button", { class: "opt", type: "button", lang: LANG }, rich(o));
    b.addEventListener("click", () => {
      if (item.id in lessonScores) return;
      lessonScores[item.id] = i === item.answer;
      [...box.children].forEach((c, j) => { c.disabled = true; if (j === item.answer) c.classList.add("is-ok"); else if (j === i) c.classList.add("is-bad"); });
      why.hidden = false; updateMeter();
    });
    box.append(b);
  });
  return el("div", {}, box, why);
}
function lessonCRQ(item) {
  const ta = answerBox(item, "ta-" + item.id, UI.placeholder);
  const btn = el("button", { class: "btn", type: "button" }, UI.submitAnswer);
  const status = el("p", { class: "status", hidden: true });
  const out = el("div");
  const toSelf = () => {
    btn.hidden = true; status.hidden = true;
    out.replaceChildren(selfCheck(item, s => { lessonScores[item.id] = s >= 60; updateMeter(); }));
  };
  btn.addEventListener("click", async () => {
    const answer = ta.value.trim();
    if (!answer) { ta.focus(); return; }
    btn.disabled = true; ta.readOnly = true;
    status.hidden = false; status.className = "status"; status.textContent = UI.grading;
    const sample = await samplePromise;
    if (!sample) return toSelf();
    try {
      const [r] = await gradeBatch(sample, [{ ...item, answer }]);
      btn.hidden = true; status.hidden = true;
      out.replaceChildren(resultCard(r));
      lessonScores[item.id] = r.score >= 60; updateMeter();
    } catch (e) {
      if (ABSENT.has(e && e.code)) return toSelf();
      status.className = "status err"; status.textContent = errText(e);
      btn.disabled = false; ta.readOnly = false;
    }
  });
  return el("div", {}, ta, el("div", { class: "row" }, btn), status, out);
}
function renderLesson() {
  const pane = document.getElementById("pane-lesson");
  SECTIONS.forEach((s, idx) => {
    pane.append(el("article", { class: "section", id: "sec-" + s.id },
      el("div", { class: "sec-head" }, el("span", { class: "sec-no" }, UI.part + " " + (idx + 1)), el("h2", {}, s.title)),
      s.gloss ? el("p", { class: "gloss" }, s.gloss) : null,
      el("div", { class: "reading", lang: LANG }, s.reading.map(p => el("p", {}, rich(p)))),
      s.example ? el("div", { class: "example", lang: LANG }, el("h3", {}, s.example.title), el("ol", {}, s.example.steps.map(st => el("li", {}, rich(st))))) : null,
      el("div", { class: "drill" }, s.drills.map(item => el("div", { class: "card" },
        el("span", { class: "kind" + (item.type === "crq" ? " ai" : "") }, item.type === "crq" ? UI.crq : UI.mcq),
        promptBlock(item),
        item.type === "mcq" ? lessonMCQ(item) : lessonCRQ(item))))));
  });
  const go = el("button", { class: "btn", type: "button" }, UI.goExam);
  go.addEventListener("click", () => { selectTab("exam"); window.scrollTo({ top: 0 }); });
  pane.append(el("div", { class: "cta" }, el("p", {}, UI.ctaText), go));
}

/* ---------- module exam ---------- */
let exam = null;
function drawExam() {
  const items = [];
  for (const s of SECTIONS) {
    const mine = COURSE.pool.filter(p => p.section === s.id);
    const mcq = shuffle(mine.filter(p => p.type === "mcq"));
    const crq = shuffle(mine.filter(p => p.type === "crq"));
    const first = [mcq[0], crq[0]].filter(Boolean);
    const rest = shuffle([...mcq.slice(1), ...crq.slice(1)]);
    items.push(...first, ...rest.slice(0, Math.max(0, PER_SECTION - first.length)));
  }
  return shuffle(items);
}
function newExam() { exam = { items: drawExam(), answers: {}, results: {}, state: "open", self: false, err: "" }; renderExam(); }
function computeScore() {
  const per = {}; let sum = 0, pending = 0;
  for (const s of SECTIONS) per[s.id] = { n: 0, sum: 0 };
  for (const it of exam.items) {
    const r = exam.results[it.id];
    per[it.section].n++;
    if (!r) { pending++; continue; }
    per[it.section].sum += r.score; sum += r.score;
  }
  return { total: Math.round(sum / exam.items.length), per, pending };
}
function answeredCount() {
  return exam.items.filter(it => it.type === "mcq" ? exam.answers[it.id] !== undefined : (exam.answers[it.id] || "").trim()).length;
}
function bestScore() { const raw = store.get(STORE_KEY); const v = Number(raw); return raw !== null && Number.isFinite(v) ? v : null; }

function renderVerdict(box) {
  const { total, per, pending } = computeScore();
  box.className = "verdict on";
  const passed = total >= PASS;
  const stamp = pending
    ? el("div", { class: "stamp pending" }, UI.open, el("span", {}, fmt(UI.selfMissing, { k: pending })))
    : el("div", { class: "stamp " + (passed ? "pass" : "fail") }, passed ? UI.passed : UI.failed, el("span", {}, fmt(UI.passLine, { p: PASS })));
  box.replaceChildren(
    el("div", { class: "big" }, pending ? "—" : total + " %", el("small", {}, UI.overall)),
    stamp,
    el("div", { class: "topics" }, SECTIONS.map(s => {
      const p = per[s.id]; const pct = p.n ? Math.round(p.sum / p.n) : 0;
      return el("div", { class: "trow" }, el("span", { title: s.title }, SEC_TITLE[s.id]),
        el("div", { class: "ttrack" }, el("div", { class: "tfill", style: "width:" + pct + "%" })),
        el("span", { class: "tval" }, pct + " %"));
    })));
  if (!pending) {
    const best = bestScore();
    if (best === null || total > best) { store.set(STORE_KEY, String(total)); const f = document.getElementById("field-best"); if (f) f.textContent = total + " %"; }
  }
}
function examItem(item, n) {
  const done = exam.state === "done";
  const locked = exam.state !== "open";
  const head = el("div", { class: "task-head" },
    el("span", { class: "task-no" }, UI.task + " " + n),
    el("span", { class: "topic" }, SEC_TITLE[item.section]),
    el("span", { class: "kind" + (item.type === "crq" ? " ai" : "") }, item.type === "crq" ? UI.crqShort : UI.mcqShort));
  const body = el("div");
  if (item.type === "mcq") {
    const box = el("div", { class: "opts", role: "radiogroup", "aria-label": UI.task + " " + n });
    const sel = exam.answers[item.id];
    item.options.forEach((o, i) => {
      let cls = "opt";
      if (done) { if (i === item.answer) cls += " is-ok"; else if (sel === i) cls += " is-bad"; }
      else if (sel === i) cls += " is-picked";
      const b = el("button", { class: cls, type: "button", role: "radio", "aria-checked": String(sel === i), disabled: locked, lang: LANG }, rich(o));
      b.addEventListener("click", () => {
        exam.answers[item.id] = i;
        [...box.children].forEach((c, j) => { c.classList.toggle("is-picked", j === i); c.setAttribute("aria-checked", String(j === i)); });
        updateExamCount();
      });
      box.append(b);
    });
    body.append(box);
    if (done) body.append(el("p", { class: "why" }, rich(item.why || "")));
  } else {
    const ta = answerBox(item, "ex-" + item.id, UI.task + " " + n);
    if (locked) ta.readOnly = true;
    ta.value = exam.answers[item.id] || "";
    ta.addEventListener("input", () => { exam.answers[item.id] = ta.value; updateExamCount(); });
    body.append(ta);
    if (done) {
      const answered = !!(exam.answers[item.id] || "").trim();
      if (exam.self) body.append(selfCheck(item, (s, v) => { exam.results[item.id] = { score: s, verdict: v }; renderVerdict(document.getElementById("verdict")); }, exam.results[item.id], answered));
      else if (exam.results[item.id]) body.append(resultCard(exam.results[item.id]));
    }
  }
  return el("li", { class: "task" }, head, promptBlock(item), body);
}
function updateExamCount() {
  const c = document.getElementById("exam-count");
  if (c) c.textContent = fmt(UI.answered, { a: answeredCount(), n: exam.items.length });
}
function renderExam() {
  const pane = document.getElementById("pane-exam");
  const today = new Date().toLocaleDateString(UI.dateLocale, { day: "2-digit", month: "2-digit", year: "numeric" });
  const best = bestScore();
  const verdict = el("div", { class: "verdict", id: "verdict", "aria-live": "polite" });
  const foot = el("div", { class: "sheet-foot" });
  if (exam.state === "done") {
    const again = el("button", { class: "btn", type: "button" }, UI.newDraw);
    again.addEventListener("click", () => { newExam(); pane.scrollIntoView({ block: "start" }); });
    foot.append(again, el("span", { class: "count" }, UI.newDrawNote));
  } else {
    const submit = el("button", { class: "btn", type: "button", disabled: exam.state === "grading" }, exam.state === "grading" ? UI.grading : UI.submitExam);
    submit.addEventListener("click", submitExam);
    foot.append(submit, el("span", { class: "count", id: "exam-count" }));
    if (exam.state === "grading") foot.append(el("p", { class: "status", style: "flex-basis:100%;margin:0" }, UI.gradingNote));
    if (exam.err) foot.append(el("p", { class: "status err", style: "flex-basis:100%;margin:0" }, exam.err));
  }
  pane.replaceChildren(el("div", { class: "sheet" },
    el("div", { class: "sheet-head" },
      el("h2", {}, UI.examTitle),
      el("p", { class: "sub" }, COURSE.examNote || fmt(UI.examSub, { n: exam.items.length })),
      el("dl", { class: "fields" },
        el("div", { class: "field" }, el("dt", {}, UI.fDate), el("dd", {}, today)),
        el("div", { class: "field" }, el("dt", {}, UI.fTasks), el("dd", {}, String(exam.items.length))),
        el("div", { class: "field" }, el("dt", {}, UI.fPass), el("dd", {}, PASS + " %")),
        el("div", { class: "field" }, el("dt", {}, UI.fBest), el("dd", { id: "field-best" }, best === null ? "—" : best + " %")))),
    verdict,
    el("ol", { class: "tasks" }, exam.items.map((it, i) => examItem(it, i + 1))),
    foot));
  if (exam.state === "done") renderVerdict(verdict);
  updateExamCount();
}
async function submitExam() {
  exam.state = "grading"; exam.err = ""; renderExam();
  for (const it of exam.items) if (it.type === "mcq") {
    const ok = exam.answers[it.id] === it.answer;
    exam.results[it.id] = { score: ok ? 100 : 0, verdict: ok ? "correct" : "incorrect" };
  }
  const crqs = exam.items.filter(it => it.type === "crq");
  const toGrade = crqs.filter(it => (exam.answers[it.id] || "").trim());
  for (const it of crqs) if (!toGrade.includes(it)) exam.results[it.id] = { score: 0, verdict: "incorrect", feedback: UI.unanswered, correction: it.model };
  const sample = await samplePromise;
  if (!sample) { exam.self = true; exam.state = "done"; return renderExam(); }
  if (toGrade.length) {
    try {
      const rs = await gradeBatch(sample, toGrade.map(it => ({ ...it, answer: exam.answers[it.id].trim() })));
      toGrade.forEach((it, i) => { exam.results[it.id] = rs[i]; });
    } catch (e) {
      if (ABSENT.has(e && e.code)) exam.self = true;
      else { exam.state = "open"; exam.err = errText(e); return renderExam(); }
    }
  }
  exam.state = "done"; renderExam();
}

/* ---------- shell ---------- */
function updateMeter() {
  const ok = Object.values(lessonScores).filter(Boolean).length;
  document.getElementById("meter-fill").style.width = Math.round(ok / LESSON_TOTAL * 100) + "%";
  document.getElementById("meter-label").textContent = fmt(UI.meter, { ok, n: LESSON_TOTAL, done: Object.keys(lessonScores).length });
}
function selectTab(name) {
  for (const t of ["lesson", "exam"]) {
    document.getElementById("tab-" + t).setAttribute("aria-selected", String(t === name));
    document.getElementById("pane-" + t).hidden = t !== name;
  }
}
document.getElementById("tab-lesson").textContent = UI.tabLesson;
document.getElementById("tab-exam").textContent = UI.tabExam;
document.getElementById("tab-lesson").addEventListener("click", () => selectTab("lesson"));
document.getElementById("tab-exam").addEventListener("click", () => selectTab("exam"));
document.getElementById("hero-level").textContent = COURSE.level || "";
document.getElementById("hero-level").hidden = !COURSE.level;
document.getElementById("hero-title").textContent = COURSE.title;
document.getElementById("hero-sub").textContent = COURSE.subtitle || "";
document.getElementById("footnote").textContent = UI.footnote;
document.documentElement.lang = COURSE.uiLang || "en";

renderLesson();
updateMeter();
newExam();
if (location.hash === "#exam") selectTab("exam");
</script>
````
<!-- END template.html -->

<!-- BEGIN build.mjs -->
````js
// Usage: node build.mjs template.html course.json out.html
// Validates the course data, then writes the finished page.
import { readFileSync, writeFileSync } from "node:fs";
const [tplPath, coursePath, outPath] = process.argv.slice(2);
const tpl = readFileSync(tplPath, "utf8");
const c = JSON.parse(readFileSync(coursePath, "utf8"));
const errs = [], warns = [];
const need = (cond, msg) => { if (!cond) errs.push(msg); };
const ids = new Set();
const checkItem = (it, where) => {
  need(it.id && !ids.has(it.id), `${where}: missing or duplicate id "${it.id}"`); ids.add(it.id);
  need(it.type === "mcq" || it.type === "crq", `${it.id}: type must be mcq or crq`);
  need(typeof it.prompt === "string" && it.prompt.trim(), `${it.id}: prompt missing`);
  if (it.type === "mcq") {
    need(Array.isArray(it.options) && it.options.length >= 3 && it.options.length <= 5, `${it.id}: needs 3-5 options`);
    need(Number.isInteger(it.answer) && it.answer >= 0 && it.answer < (it.options || []).length, `${it.id}: answer index out of range`);
    need(new Set(it.options || []).size === (it.options || []).length, `${it.id}: duplicate options`);
    need(it.why, `${it.id}: why missing`);
  } else {
    need(it.rubric && it.rubric.length >= 60, `${it.id}: rubric missing or too thin`);
    need(it.model, `${it.id}: model answer missing`);
  }
};
need(c.title && c.subject, "title and subject are required");
need(Array.isArray(c.sections) && c.sections.length >= 2 && c.sections.length <= 5, "need 2-5 sections");
need(Array.isArray(c.pool), "pool missing");
const secIds = new Set();
for (const s of c.sections || []) {
  need(s.id && !secIds.has(s.id), `section id missing/duplicate: ${s.id}`); secIds.add(s.id);
  need(Array.isArray(s.reading) && s.reading.length >= 1, `${s.id}: reading missing`);
  need(Array.isArray(s.drills) && s.drills.some(d => d.type === "mcq") && s.drills.some(d => d.type === "crq"), `${s.id}: drills need at least one mcq and one crq`);
  (s.drills || []).forEach(d => checkItem(d, s.id));
  const mine = (c.pool || []).filter(p => p.section === s.id);
  need(mine.some(p => p.type === "mcq") && mine.some(p => p.type === "crq"), `${s.id}: exam pool needs at least one mcq and one crq`);
  const per = Number(c.examPerSection) || 3;
  if (mine.length < per) errs.push(`${s.id}: pool has ${mine.length} items, exam draws ${per}`);
  else if (mine.length < per + 1) warns.push(`${s.id}: pool has no spare items, so every exam draw is identical for this part`);
}
for (const p of c.pool || []) { need(secIds.has(p.section), `${p.id}: unknown section "${p.section}"`); checkItem(p, "pool"); }
const lessonPrompts = new Set((c.sections || []).flatMap(s => s.drills.map(d => d.prompt.trim())));
for (const p of c.pool || []) if (lessonPrompts.has(p.prompt.trim())) errs.push(`${p.id}: repeats a lesson drill verbatim`);
const crqShare = [...(c.sections || []).flatMap(s => s.drills), ...(c.pool || [])].filter(i => i.type === "crq").length / Math.max(1, ids.size);
if (crqShare < 0.4) warns.push(`only ${Math.round(crqShare * 100)}% free-answer items; aim for at least 40%`);
warns.forEach(w => console.log("warn: " + w));
if (errs.length) { console.error(errs.map(e => "error: " + e).join("\n")); process.exit(1); }
const esc = s => s.replace(/&/g, "&amp;").replace(/</g, "&lt;");
const json = JSON.stringify(c, null, 1).replace(/</g, "\\u003c");
writeFileSync(outPath, tpl.replace("__TITLE__", () => esc(c.pageTitle || c.title)).replace("__COURSE_JSON__", () => json));
console.log(`ok: ${c.sections.length} parts, ${ids.size} items (${Math.round(crqShare * 100)}% free answer) -> ${outPath}`);
````
<!-- END build.mjs -->