# PROJECT 01 — NotePilot · Spec changelog

The history of `PROJECT_01_NOTEPILOT.md`: what changed in each version, and why. The spec
states what the system *is*; this file records how it got there. Newest first.

**Reading the ids.** `L#` is the delta ledger: one id per change, numbered continuously
across versions (v1.3's walkthrough opened it at L1; v1.3.1 continues at L68; v1.3.2 at L82; v1.3.3 at L94; v1.3.4 at L97; v1.3.5 at L98; v1.3.6 at L99; v1.3.7 at L100; v1.3.8 at L101; v1.3.9 at L102; v1.3.10 at L103; v1.3.11 at L104; v1.3.12 at L105; v1.3.13 at L106; v1.3.14 at L107; v1.3.15 at L111; v1.3.16 at L112; v1.3.17 at L113; v1.3.18 at L116; v1.3.19 at L118; v1.3.20 at L120; v1.3.21 at L122; v1.3.22 at L124; v1.3.23 at L128; v1.3.24 at L131; v1.3.25 at L134; v1.3.26 at L136; v1.3.27 at L139; v1.3.28 at L140; v1.3.29 at L141; v1.3.30 at L143; v1.3.31 at L144), so
an id never needs its version to be unambiguous. `D#` is a decision record, vetoable like every D.
Where a decision also has a DECISION block in the spec, the block is the current statement
and the entry here is its origin. Severity uses the project's own triage enum. v1.1 and v1.2
predate the ledger; their deltas are cited by section.

**Versioning.** Patch (v1.3.x): fills a detail the spec leaves unspecified, or resolves a
conflict between two spec statements, citing both and naming which wins. Minor (v1.x):
anything else. Every change gets the next `L#`.

---

## v1.3.31 — the dropped allergy (patch)

Theme: step 4b opens with `allergy_preserved`. A fill it needed, a conflict and a fill it
surfaced in §8.5, and a fill decided while drafting step 4 (#5) land with it. No invariant
moves; CLAUDE.md is unchanged.

**WARNING**
- **L144 §8.4, §8.6 — a dropped NKA is a WARNING, as a dropped NKDA.** Fill: §8.4's roster
  lowers a dropped NKDA to a WARNING (D10) and says nothing of NKA, which D10 keeps a
  separate fact, so `allergy_preserved`'s CRITICAL covered it by default. NKA is an
  allergy status, as NKDA is, not an allergy: dropped, it prompts the same re-ask, and a
  CRITICAL would be the false red D10 exists to prevent. Both lower to a WARNING, in
  §8.4's table and note and §8.6's triage. The check reads the two from the set
  `extract.py` already held as D10's statements, now public, so the extractor and the
  check name them once.

**INFO**
- **L145 §8.5, §8.7, §14 — the dropped-allergy twin expects `allergy_preserved` until
  2b.** Conflict: §8.5's fixture table gave `fidelity_dropped_allergy`'s injected twin the
  answer key `[allergy_preserved, must_preserve]`, and §8.7 had it pass when both fire;
  §14 schedules `must_preserve` for 2b, and the loader rejects an unregistered name
  (§8.5). §14 wins, as L137 decided for the model clause: the twin,
  `detect_dropped_allergy`, gets its own row and expects `[allergy_preserved]` in 2a, and
  §14's 2b list adds `must_preserve` to its answer key.
- **L146 §8.5 — the coverage rule's predicates for checks that compare no span.** Fill:
  L138 said what exercising a check means for the claim-local family only, a key a claim's
  text and its span both name. `hallucinated_medication` compares no span, and its test
  predicate, a claim naming a drug, has gone unstated since the check registered.
  `allergy_preserved` compares the raw text with the note, so a control exercises it when
  the raw text and a claim both state an allergy. §8.5 names both.
- **L147 §7, §8.5 — the terminator list names the line break.** Fill: §7's scope rule
  listed five of `TERMINATORS`' entries and omitted the line break, which L143's §8.5
  bullet cites §7 for. §7 names it and points at the table, the lexicon shape's comment
  follows, and §8.5 cites `TERMINATORS`.

---

## v1.3.30 — case line breaks (patch)

Theme: a fill found while drafting step 4a-iv closes step 4a's corpus before step 4b reads
raw text. No invariant moves; CLAUDE.md is unchanged.

**WARNING**
- **L143 §8.5 — a case's raw text breaks lines only where its source would.** Fill: §8.5's
  authoring rules never said where a case's raw text may break a line, and four cases from
  4a-i to 4a-iii wrapped mid-sentence to fit a width. A line break is a terminator (§7),
  so `detect_paraphrase_drug_swap`'s "start" at a line's end, over "azithromycin", read no
  new prescription; on one line, `new_prescriptions` reads azithromycin (measured), which
  step 4b's checks read from raw text. The other three breaks fell where they changed
  nothing. Each sentence of the four now sits on one line, re-signed by Cal, and §8.5
  states the rule beside D16, enforced in review: a section header over its list is a
  break a source makes, and no test can tell that from a wrap.

---

## v1.3.29 — doses compared (patch)

Theme: a fill decided while drafting step 4 lands with `dose_consistency`, and step 4a
closes: the six claim-local checks are registered. A wording conflict L140 left in §8.6 is
fixed with it. No invariant moves; CLAUDE.md is unchanged.

**WARNING**
- **L141 §7, §8.4 — doses compared.** Fill: §8.4's roster had `dose_consistency` compare
  parsed doses, and L133 left it two questions: whether 1 g is 1000 mg, and whether a dose
  charted without a frequency matches one charted with. Read strictly, "Acetaminophen 1 g"
  against a span's "1000 mg" and "Metformin 500 mg" against "metformin 500 mg bid" both
  fire on faithful claims. A mass now compares in micrograms through `DOSE_MASS_UG`, a
  signed table of g, mg, and μg; ml and units stay outside it, since mg to ml needs a
  concentration. The arithmetic runs in `Decimal`: in floats, 1.005 g is
  1004999.9999999999 μg (measured). A dose the claim charts without a frequency matches
  the span's at any; one charted with a frequency the span lacks still fires, since the
  claim says more than its source. A drug the span doesn't name is `drug_in_quote`'s, as
  presence is under D13. The step pointer L133 left ("4c") in §7, `lexicons.py`, and
  `test_extract.py` becomes the answer, as L101 asks.

**INFO**
- **L142 §8.6 — the excluded-diagnosis line, narrowed.** Conflict: L140 put "an excluded
  diagnosis asserted" in §8.6's CRITICAL list, while §8.4 makes that CRITICAL only as
  definite or probable, and §8.6's own WARNING list holds the reopened exclusion, possible
  or rule-out. The CRITICAL line now says definite or probable. Claude Code found it
  reviewing 4a-v's commit.

---

## v1.3.28 — exclusions (patch)

Theme: a fill decided while drafting step 4 lands with `diagnosis_in_quote`, the check it
completes; step 4a's claim-local checks are all registered but `dose_consistency`. No
invariant moves; CLAUDE.md is unchanged.

**CRITICAL**
- **L140 §7, §8.4, §8.6 — a negated diagnosis is read.** Fill: L135 made a negated
  diagnosis not asserted, and `diagnosis_in_quote` compared asserted ones only, so no
  check saw an exclusion. "r/o PE" written as "PE ruled out" compared ∅ ⊆ {rule_out} and
  passed (measured): premature closure, a patient sent home before the CTA. "pneumonia"
  written as "No pneumonia" passed the same way. L124 kept a negated drug visible for this
  reason. `extract_excluded_diagnoses` reads the negated mentions beside
  `extract_diagnoses`, and the check compares each diagnosis' reading, its certainties and
  whether it is excluded. An exclusion the span doesn't make is CRITICAL, whether the span
  rules the diagnosis out, asserts it, or never names it (an inferred exclusion, D7). A
  claim asserting a diagnosis its span excludes is CRITICAL as definite or probable and
  WARNING as possible or rule-out, which reopen the question as D12's downgrade does.
  D12's "never stronger" also needed a reading over L135's sets: strongest compares to
  strongest, so a span reading "r/o PE; PE likely given D-dimer" supports a claim of
  "Likely PE".

---

## v1.3.27 — negation, per finding (patch)

Theme: a fill decided while drafting step 4 lands with `negation_consistency`, the check
it defines. No invariant moves; CLAUDE.md is unchanged.

**WARNING**
- **L139 §8.4, §8.8 — negation compares the findings both sides name.** Fill: §8.4's
  roster had `negation_consistency` compare polarity(text) ⊆ polarity(span) and never said
  what a finding the span doesn't name does. Read as a violation, it fires CRITICAL on
  faithful claims: "No fever" against a span's "Temp 37.0, afebrile" compares
  `{fever: {False}}` with `{}` (measured), and so would any finding paraphrased past the
  lexicon. So the check compares per finding, for findings both sides name, as D13 does
  for status. The cost is recall, and §8.8 states it: a flip behind a name `FINDINGS`
  lacks ("denies CP" → "reports chest pain") reads nothing, an invented finding is left to
  the judge and `must_not_add`, and a span holding both polarities passes a claim that
  keeps either one.

---

## v1.3.26 — the first check and its corpus (patch)

Theme: two conflicts approved while planning phase 2a and a fill proposed then, each
settled in form while drafting step 4a; all three land with its first commit,
`drug_in_quote` and the injected corpus's harness. No invariant moves; CLAUDE.md is
unchanged.

**CRITICAL**
- **L136 §8.4 — presence reads every named drug.** Conflict: D13 gives presence to
  `drug_in_quote`, and §8.4's roster had it compare drugs(text) ⊆ drugs(span), where §7's
  `extract_drugs` keeps active mentions only. A swapped stop order read green:
  "Discontinue metformin" against a span's "discontinue lisinopril" compared ∅ ⊆ ∅,
  `med_status_consistency` saw no drug in both, and the quote grounds at Tier 1
  (measured), so the patient would keep the drug the clinician stopped and stop the one
  the clinician kept. `hallucinated_medication` had the same hole for an ungrounded
  "Discontinue apixaban". D13's split stands: both presence checks read `named_drugs`,
  `extract_med_status`'s keys, which hold every mention but an allergen, negated included.
  A negated mention is named because status keeps it (L124): read otherwise, "Continue
  apixaban" against "not on apixaban" would fire both checks for one error.

**WARNING**
- **L138 §8.5 — "exercises its extraction path", made mechanical.** Fill: the coverage
  rule asks each CRITICAL check for a control that exercises its extraction path and never
  says how a test would know. A control exercises a check when the check has something to
  compare on it: for the claim-local family, a key the check's extractor finds in both a
  claim's text and its span, since a key in the text alone leaves the comparison nothing
  to compare. The coverage test holds one predicate per CRITICAL check and fails when one
  is missing or when no CRITICAL check is registered.

**INFO**
- **L137 §8.5, §14 — the coverage rule's model clause waits for 2b.** Conflict: §8.5 asks
  every `origin="source"` check for a model detection trap, and model cases are 2b's
  (§14), so 2a's coverage line failed by construction. 2a's test checks the injected
  clauses, and §14's 2b list gains the model clause. Until the corpus's first model case
  lands, the test asserts there is none, so that case turns it red rather than leaving the
  clause to be remembered.

---

## v1.3.25 — diagnoses and certainty (patch)

Theme: two fills for phase 2a's step 3e, the diagnosis extractor and the certainty
lexicon, signed off by Cal; step 3, extraction, is complete. No invariant moves; CLAUDE.md
is unchanged.

**WARNING**
- **L134 §7 — diagnosis names.** Fill: §7 keys diagnoses by surface form, like `FINDINGS`,
  and `diagnosis_in_quote` compares keys, so a claim's "pulmonary embolism" against a
  span's "PE" would fire a CRITICAL on a faithful claim (L126's lesson). `DIAGNOSES` holds
  canonical names, `DIAGNOSIS_ALIASES` maps the other charted names onto them, and a test
  holds its values in `DIAGNOSES`; §7's example key becomes "pulmonary embolism". "PE"
  also charts the physical exam, an accepted cost a test pins; "CAP" stays out, since it
  also charts a capsule.
- **L135 §7 — certainty, negated diagnoses, and differentials.** Fill: §7 names
  `CERTAINTY_CUES` and its values, not the cues' reach, what a negated diagnosis asserts,
  or how "vs", the prompt's own certainty marker, reaches. Certainty cues work before a
  diagnosis (`CERTAINTY_CUES`) and after it (`CERTAINTY_POST`), a diagnosis no cue governs
  is definite, and a negated one isn't asserted; "ruled out" joins the negation cues. A
  differential cue governs the diagnosis immediately before it, unless another cue governs
  that one, and the window after it (measured: as a pre-cue alone, "PNA vs PE" read
  pneumonia as definite, so a note that dropped the differential would hide the upgrade).
  §7's sentence counting three cue classes, stale since L128, now names the classes the
  engine serves.

---

## v1.3.24 — doses (patch)

Theme: two conflicts and a fill for phase 2a's step 3d, the dose extractor and the dose
lexicon, signed off by Cal, with three plural denied-allergy entries that 3c's review
found. No invariant moves; CLAUDE.md's count of sanctioned exceptions moves with L132.

**WARNING**
- **L131 §7 — the dose pattern, split into signable tables.** Conflict: §7's shape typed
  `DOSE_PATTERN` a `re.Pattern` and said `lexicons.py` imports nothing, and a regex gives
  L120's sign-off no entries to attach to. `DOSE_UNITS` and `DOSE_FREQUENCIES` hold the
  knowledge, each charted form under its canonical one, and the number grammar lives in
  `extract.py`. The lexicon still imports nothing, as 3a's import test holds.
- **L133 §7 — the dose rules.** Fill: §7 says doses are parsed and that a titration keeps
  both, not how a dose finds its drug or its frequency. A dose is a number and a unit
  after a listed drug, in that drug's sentence; it belongs to the most recent drug,
  whatever its status. It takes the first frequency charted after its unit, before the
  next dose, drug, or terminator, and a prn yields to an interval in that reach (measured:
  as a plain first-phrase entry, prn made "prn q6h" and "q6h prn" read differently). Units
  are canonical, never converted. Neither number of a range is a dose; a hyphen joins a
  range, units or not, and "to" joins one only after a number without a unit, since "from
  500 mg to 1000 mg" is a titration. Costs: a dose before its drug, or in the next
  sentence, reads as nothing. Unit equivalence and a missing frequency are
  `dose_consistency`'s, in step 4c.

**INFO**
- **L132 §13 — extraction's result types, sanctioned.** Conflict: §13 allowed two kinds of
  shape outside `schemas.py`, and §7 puts `Dose` in `clinical/extract.py`, where
  invariant 13 keeps it, though `dose_consistency` reads it in `evals/`. A third
  exception: `Dose`, `MedStatus`, and `Certainty` live in `clinical/extract.py`, and
  `evals/` imports them from there. CLAUDE.md's count of the exceptions moves with it.

---

## v1.3.23 — allergies (patch)

Theme: three fills for phase 2a's step 3c, the allergy extractor and the first allergy
lexicon, signed off by Cal. The allergy-context scope rule was proposed while planning
phase 2a; the other two were found while drafting the step. No invariant moves; CLAUDE.md
is unchanged.

**WARNING**
- **L128 §7 — the allergy-context scope rule.** Fill: §7 says allergy context must keep
  "allergic to penicillin" from reaching the contraindication check, and never says how
  far it reaches. Allergy is a fourth cue class, before the allergen and after it, and a
  mention it governs is an allergen the drug extractors drop. An allergy header at a
  line's start opens a section that runs to a blank line or the next header (measured: by
  window alone, "Allergies:" over a vertical list read no allergen). Inside it, other cues
  still govern, so an order under the header stays an order. An allergy post-cue reaches
  back over the list before it (measured: one allergen per post-cue read "PCN and sulfa
  allergies" as sulfa alone, silently). Two costs, accepted because each fails loud
  through `allergy_preserved`: a bare medication line under a header reads as an allergen,
  and a list can reach back into a medication. A CRLF line break is now one token
  (measured: as two, CRLF text closed its section at once).
- **L129 §7 — allergen names.** Fill: §7 shows `ALLERGY_ALIASES` but not what may be a key
  or a value. It holds the classes and D10's statements, a canonical name mapping to
  itself as §7's "nka" -> "nka" does; drug allergens come through `GENERIC_DRUGS` and
  `BRAND_TO_GENERIC` (L30), and a test holds the values outside `GENERIC_DRUGS`. "nkda"
  and "nka" are allergy statements without a cue unless negated, "Allergies: none" is NKA,
  and denied allergies ("not allergic to") join the negation cues. As with L126, a listed
  allergen needs its common names, or a raw "penicillin allergy" against a note's unmapped
  "PCN allergy" fires `allergy_preserved` on a faithful note.

**INFO**
- **L130 §8.8 — allergens that aren't drugs, stated.** Fill: §7's allergy keys are drugs,
  classes, and D10's statements, so a latex or food allergy is never extracted and
  `allergy_preserved` can't see one dropped. L127's vocabulary bullet now says so.

---

## v1.3.22 — drugs, status, and new prescriptions (patch)

Theme: four fills found while drafting phase 2a's step 3b, landing as step 3b-ii with the
drug extractors and the first medication lexicon, all signed off by Cal. No invariant
moves; CLAUDE.md is unchanged.

**WARNING**
- **L124 §7 — medication cues, combined.** Fill: §7 has one scope engine serve three cue
  classes and never says how they combine in one string, or what status a negated drug
  has. Each cue carries its class, and the most recent pre-cue's window governs. A drug
  sees negation (the `FINDING_NEG_*` tables), stop, and start at once. A negated mention
  is "stopped", so a flip from "not on apixaban" to "Continue apixaban" stays visible to
  `med_status_consistency` (dropping negated mentions from status would hide it).
  `extract_drugs` keeps each drug with an active mention, and `new_prescriptions` each
  drug a start cue governs. The allergy-context exclusion stays with step 3c, whose scope
  rule decides both it and `extract_allergies`.
- **L125 §7 — post-position order cues.** Fill: §7's order cues are pre-cues only, and the
  common stop charting is post ("lisinopril discontinued due to cough"). Read as active,
  it would fire `med_status_consistency` on a faithful "Discontinue lisinopril" and pass a
  flipped "Continue lisinopril". `MED_STOP_POST` and `MED_START_POST` hold the post forms,
  as `FINDING_NEG_POST` does. Narrative past tense counts as a start (measured: as
  nothing, "held metformin, started apixaban" read apixaban stopped); the cost, an old
  start in `new_prescriptions`, lands on a WARNING.
- **L126 §7 — the drug vocabulary.** Fill: §7 named no drug vocabulary. `GENERIC_DRUGS` is
  it, and `BRAND_TO_GENERIC` maps every other name a listed drug is charted by (brands,
  abbreviations, spellings) onto it, a test holding its values in `GENERIC_DRUGS`.
  `DRUG_CLASS` keys aren't the vocabulary: that would make a vocabulary entry carry a
  class, which D9's rung 2 turns into a CRITICAL, before steps 3c and 4b decide classes. A
  listed drug needs its common names (measured: without "zestril", `extract_drugs` reads
  nothing in "Zestril 10 mg daily" and lisinopril in "Lisinopril 10 mg daily", so
  `drug_in_quote` would fire on a faithful claim).

**INFO**
- **L127 §8.8 — vocabulary coverage, stated.** Fill: §8.8 says lexicon recall on real
  phrasing is unmeasured. Coverage is a stronger fact: a drug the lexicon doesn't list is
  invisible to every drug check, which then passes, so its recall is zero.

---

## v1.3.21 — the scope rule, corrected (patch)

Theme: one conflict and one fill, both found while drafting phase 2a's step 3b. They land
as step 3b-i, ahead of the drug extractors the conflict would break. No invariant moves;
CLAUDE.md is unchanged.

**WARNING**
- **L122 §7 — a comma ends adjacency.** Conflict: L121 let "immediately before" skip every
  mark that isn't a terminator, commas included, so a post-cue reached back across a comma
  into the clause before it. Measured on v1.3.20, "endorses chest pain, denied fever" read
  chest pain negated and fever positive: `negation_consistency` would fire on a faithful
  "Denies fever" and pass a flipped "Reports fever", the catch §8.4's row names. Once stop
  cues have a post form (step 3b), the same crossing reads "Continued lisinopril, held
  metformin" as lisinopril held and metformin active. A comma now ends adjacency, as a
  word or a terminator does; "chest pain: denied" and "chest pain - denied" are unchanged.
  The cost: "fever, denied", a rare form, no longer negates.

**INFO**
- **L123 §7 — an underscore separates words.** Fill: L121 named a token's three kinds and
  left the underscore in none of them. The tokenizer treats it as whitespace, so
  "chest_pain" reads as chest pain and a template blank ("denies ___ fever") spends no
  window. A test now holds what the code already did.

---

## v1.3.20 — scoped negation as built (patch)

Theme: one fill approved while planning phase 2a and one found while drafting its step 3a;
both land with the first lexicon commit, step 3a's scope engine and `extract_findings`. No
invariant moves; CLAUDE.md is unchanged.

**WARNING**
- **L121 §7 — the scope rule, made exact.** Fill: §7 (L31) makes cue matching token-level
  and gives a pre-cue `NEGATION_WINDOW` tokens, but defines neither a token nor how the
  window counts, and the choices decide §7's own examples: once ":" is a token, "chest
  pain: denied" has no finding immediately before its cue. The engine's token is a word (a
  decimal number whole), one punctuation mark, or a line break, from the casefolded text,
  and lexicon phrases are tokenized the same way. Phrases match left to right, longest
  first. The window counts words, so punctuation spends none of it, and a finding is in
  scope when its first word falls inside it. "Immediately before" skips punctuation that
  isn't a terminator. A phrase in both cue classes, as "denied" is, is a post-cue when a
  finding is immediately before it and a pre-cue otherwise (measured: as a post-cue only,
  "pt denied chest pain" read positive; as both at once, "chest pain denied, fever"
  negated the fever).

**INFO**
- **L120 §7, §14 — the sign-off's form.** Fill: §14 asked each clinical entry to carry
  "its rationale and Cal's sign-off" and named no form, and D14 put the rationale "beside"
  each entry, where a 100-column line has no room for it. Each table in `lexicons.py`, and
  `NEGATION_WINDOW`, is headed by a `# Clinical sign-off: <name>, <date>.` line covering
  the entries beneath it, and each entry carries its rationale in a comment on the line
  above it. When a table changes, the line's date moves with it. A test holds the form.
  CLAUDE.md's "Clinical entries arrive VERBATIM" names the same sign-off line and
  rationale comment.

---

## v1.3.19 — the loader as built (patch)

Theme: two fills, approved while planning phase 2a's step 2c; they land with the case
loader in step 2c-ii, which adds ruamel.yaml as a runtime dependency. No invariant moves;
CLAUDE.md is unchanged.

**WARNING**
- **L118 §8.5 — a duplicate key is a load error.** Fill: §8.5 loads each case with
  `EvalCase.model_validate` but names no parser, and the usual one, PyYAML's `safe_load`,
  keeps the last of two equal keys without a word (measured, 6.0.3). A second
  `expected_flags:` then replaces the first answer key, and the trap tests a check its
  author didn't name; `EvalCase`'s validator catches only a detection trap's key left
  empty. The loader parses with ruamel.yaml's safe loader (`>=0.19.1,<0.20`, a new runtime
  dependency), which raises on a duplicate key and reads YAML 1.2, so `no` stays a string
  instead of becoming False. It is L103's rule, a typo is a load error, one layer down.
- **L119 §8.5 — every entry in `evals/cases/` is a case.** Fill: §8.5 says one YAML file
  per case, filename = `id`, but not what becomes of anything else in the directory. A
  loader globbing `*.yaml` would skip a `case.yml`, and a skipped file is a case that
  never runs: no failure, just coverage that silently isn't there. Every entry must be
  `<id>.yaml`; a `.yml` file, any other file, or a subdirectory is a load error. Dotfiles
  are skipped: `.DS_Store` is one, and `.gitignore` keeps it out of the repo.

---

## v1.3.18 — case_verdict as built (patch)

Theme: one conflict approved while planning phase 2a, and one found while prototyping its
step 2c-i; both land with `case_verdict` there, and the loader follows in 2c-ii. No
invariant's law changes: CLAUDE.md's phase list moves the loader and `case_verdict` to 2a,
and invariant 12 lists L117 among the law's roads.

**WARNING**
- **L117 §8.7, §4.2, §11, §14 — a case scored on a report that ran no check is
  `not_applicable`.** Conflict: §8.7's `case_verdict` passed a control or fidelity case
  whose report ran nothing (measured: `passed`, while the same report's
  `all_critical_passed` is False), since its empty answer key is a subset of anything.
  Invariant 12 says "not checked" never renders as "passed" and a metric over an empty
  denominator is `None` (§4.2), and a control passed on nothing would feed
  `control_specificity` a perfect score for measuring nothing. An empty roster gets there:
  drop `runner.py`'s import of `checks.py`, and every detection trap goes `not_applicable`
  while every control reads `passed`. Invariant 12 wins: `case_verdict` returns
  `not_applicable` first when `checks_run` is empty, whatever the species. §8.7's snippet
  and verdict table carry it; §4.2's `CaseResult.status` comment, §11's fail-closed tests,
  and §14's 2a line name it beside L44; invariant 12 in CLAUDE.md lists it. A run that
  selected checks but no CRITICAL one stays out of scope: the coverage rule (§8.5)
  guarantees CRITICAL checks.

**INFO**
- **L116 §14, §11, §8.5 — the injected corpus needs the loader and `case_verdict`.**
  Conflict: §14's 2a block requires the injected corpus green in pytest, and §11 defines
  that tier as ground, `run_checks`, and `case_verdict` over §8.5's YAML cases, but §14
  listed the loader and `case_verdict` in 2b's block, as did CLAUDE.md's phase list. 2a
  could then score its corpus only with a second, hand-rolled verdict in test code, which
  drifts from the real one (invariant 11), or with Python fixtures in place of §8.5's
  YAML. §11 and §8.5 win: the loader, without `corpus_version`, and `case_verdict` move to
  2a; 2b keeps `corpus_version`, `score_corpus`, the metrics, the records, and the model
  cases. CLAUDE.md's phase list moves with them.

---

## v1.3.17 — the engine as built (patch)

Theme: one conflict and two fills, approved while planning phase 2a; they land with
`run_checks` in step 2b-iii. No invariant moves; CLAUDE.md's invariants 15 and 19 now
state the hash's inputs (L114) and a crashed check's log form (L113).

**CRITICAL**
- **L113 §8.7, §9.8 — a crashed check is logged in L69's form.** Conflict: §8.7's
  `run_checks` logged a crashed check with `logger.exception`, which attaches `exc_info`:
  the traceback with the exception's message and its chained cause. A check reads the
  note, so its exception can carry note content (measured: a check raising with a sentinel
  message puts the sentinel in the captured log). §9.8 (L53) and invariant 19 say no log
  line carries it, and they win. The line logs `code=check_errored`, the check's name,
  `exc_type`, and frames (L69, rendered by `tracebacks.py`, L112), never the message or
  `exc_info`. `score_corpus`'s per-case line, which phase 2b implements, takes the same
  form, and its comment, cut off mid-sentence, is completed.

**WARNING**
- **L115 §8.7, §9.10 — a finding naming a claim the note lacks errors its check.** Fill:
  §9.10's UI joins findings to claim cards by `claim.id` and shows the note-level ones,
  `claim_ids == ()`, in the banner, but nothing checked that a finding's ids exist. A
  finding naming an id the note lacks matches no card and isn't note-level, so it renders
  nowhere; a CRITICAL one would hide. `run_checks` errors that check instead: one errored
  result, which the banner shows (invariant 12).

**INFO**
- **L114 §8.7 — `CHECKS_VERSION` hashes Python source.** Fill: §8.7 hashed "the source of
  `evals/`, `clinical/`, and `grounding.py`" without saying what source is, and `evals/`
  also holds the case YAMLs, which `corpus_version` covers, and `runs/corpus_runs.jsonl`,
  which every corpus run appends to. Hashing those would move `checks_version` on a run
  that changed no check. Source is the `.py` files. Each enters with its path relative to
  `backend/` and its content's hash, sorted by path, so a moved or renamed file moves the
  version; twelve hex digits, as `prompt_version`. CLAUDE.md's invariant 15 now says so.

---

## v1.3.16 — L69's frames leave api.py (patch)

Theme: one fill, approved while planning phase 2a's step 2b; it lands in step 2b-ii. No
invariant moves; CLAUDE.md's invariant 1 lists the new module among the DOMAIN modules.

**INFO**
- **L112 §9.4, §13 — the frame formatter is a DOMAIN module.** Fill: §9.4 specifies the
  500 path's frames as `file:line:function` (L69), and §13 gives the code that renders
  them no home of its own; it lived in `api.py`, which the domain can't import (invariant
  1). It moves to `tracebacks.py`, which imports nothing from `backend/` and knows no
  vendor, so §13 labels it DOMAIN and a domain module can log a failure in L69's form
  without importing the edge. The rendering is unchanged.

---

## v1.3.15 — the Judge protocol lands in 2a (patch)

Theme: one conflict, approved while planning phase 2a; it lands with the protocol, in step
2b-i. No invariant moves; CLAUDE.md is unchanged.

**INFO**
- **L111 §8.7, §13, §14 — the Judge protocol lands in 2a.** Conflict: §8.7's `run_checks`
  takes `judge: Judge | None`, and §14 lands `run_checks` in 2a, but §13 marked
  `evals/judge.py` as phase 2c and §14 listed it in 2c's block. Typing the parameter
  `None` in 2a would mean changing its signature, and every caller's, in 2c: the cost
  §14's preamble avoids by landing `run_checks` async in 2a. §8.7 wins: the protocol lands
  in 2a, ahead of `run_checks`. `judge_client.py`, the judge check, and real judge usage
  stay 2c.

---

## v1.3.14 — the ladder as built (patch)

Theme: the grounding ladder lands in phase 2a's step 1b-iii, with the three patches it
depends on and one correction. No invariant moves; CLAUDE.md is unchanged.

**WARNING**
- **L107 §4.1, §6.1, §6.3, §6.5, §11, §14, §17 — Tier 0 goes.** Conflict: §6.3's Tier 0
  returned `ClinicalClaim(**base, flags=(SafetyFlag.UNSUPPORTED,))` for a blank quote, but
  §4.1's `ClinicalClaim` inherits the boundary's non-blank `source_quote`, so that
  construction raises: the guard could never produce its output. §4.1 wins. With L106, a
  blank quote is unrepresentable on both sides of grounding; a draft built around one
  without validation is a programming error, and grounding raises when it builds the claim
  (tested). Tiers 1–4 keep their numbers.
- **L108 §6.3, §6.4 — Tier 3's span snaps to whole words.** Conflict: §6.3 mapped
  `partial_ratio_alignment`'s window straight back to the raw text, but the window is
  exactly as long as the normalized quote, so a source that says the same thing in more
  characters gets a span cut mid-word (measured: `ncrease metformin to 1000 mg BID`,
  `75 mcg dail`). §6.4 hands the span to the consistency family as what the source says
  (L35), and a cut word is a mismatch the source doesn't contain. §6.4 wins: the span
  widens to whole words before the numeric guard reads it. Widening only adds characters,
  so the guard loses no digit.

**INFO**
- **L109 §6.2 — `to_original` rejects an empty slice.** Fill: an empty slice has no last
  character, and at 0 `index_map[-1]` wraps to the end, returning the whole text as the
  span (measured). No caller passes one: Tier 2's normalized quote is never empty, and
  Tier 3 checks `src_end > src_start`. So `to_original` raises `ValueError` rather than
  return a plausible span.
- **L110 §6.3 — the guard's example scores 90.0.** Correction: §6.3 said
  `partial_ratio("BP 130/110", "BP 190/110")` scores in the high 80s. It scores 90.0
  (measured), exactly the default cutoff (L105), so the example clears the cutoff and it
  is the guard that demotes it; the test that pins the guard includes it.

---

## v1.3.13 — the boundary's whitespace is grounding's (patch)

Theme: one conflict, measured while drafting phase 2a's step 1b. No invariant moves;
CLAUDE.md is unchanged.

**WARNING**
- **L106 §4.1, §6.2, §6.3, §11 — the boundary's whitespace is grounding's.** Conflict:
  §4.1's `NonBlankStr` stripped with pydantic's `strip_whitespace`, while §6.2 collapses
  what `str.isspace()` calls whitespace, and §6.3's Tier 0 and L62's first property strip
  with `str.strip()`. The two disagree on U+001C–U+001F, which Python calls whitespace and
  pydantic does not (measured). So `source_quote="\x1c"` passed the boundary as non-blank
  and reached Tier 0's guard; without Tier 0 it would normalize to a space and ground
  cleanly at Tier 2 on the note's first whitespace. L62's first property was false for a
  quote ending in one of them (hypothesis found `"İ\x1c"`). §6.2 wins: it is grounding's
  definition. `NonBlankStr` strips with `str.strip()` in a `BeforeValidator` that wraps
  the str schema, so a blank string still fails as `string_too_short` and a non-string as
  `string_type`. The str schema is strict: a lax one decodes bytes after the strip, so
  `b"   "` would pass as a blank string, where main rejected it (measured). The tool
  schema is unchanged, so `PROMPT_VERSION` is too. A blank quote is now unrepresentable on
  both sides of grounding.

---

## v1.3.12 — the fuzzy cutoff's default (patch)

Theme: one fill, measured while drafting phase 2a's step 1b. No invariant moves; CLAUDE.md
is unchanged.

**WARNING**
- **L105 §6.3, §10 — `fuzzy_score_cutoff` defaults to 90.** Fill: §6.3 reads the knob and
  §10 lists it, but neither gave it a default or a domain. Measured on 65 synthetic quotes
  (31 honest paraphrases, 34 fabrications) through §6.3's Tier 3 with rapidfuzz 3.14.6: at
  90, 14 paraphrases stay PARAPHRASED and 8 fabrications leak as PARAPHRASED; at 85, 17
  and 11; at 95, 8 and 2. The leaks at 90 are one-token swaps no usable cutoff stops: two
  sides, `mcg` for `mg`, a look-alike drug, three negations, and a lateral-for-medial
  finding. A leaked claim keeps its span, and the consistency family compares its drugs,
  doses, and negations against that span (L35); no §8.4 check reads a side or that
  finding. So the cutoff routes rather than detects, and 90 errs red, as the numeric guard
  does. Domain `ge=0, le=100`, finite: a rapidfuzz score. The sample is synthetic and
  small; L8's kept scores are the data that retunes it.

---

## v1.3.11 — layer-internal shapes are sanctioned (patch)

Theme: one conflict found while prototyping phase 2a's step 1. No invariant moves;
CLAUDE.md is unchanged.

**INFO**
- **L104 §13, §6.2, §5.2 — layer-internal shapes are sanctioned.** Conflict: §13
  sanctioned two kinds of shape outside `schemas.py`, HTTP edge shapes and check-internal
  ones, and called anything else drift. §6.2 defines `NormalizedText` for the ladder and
  §5.2 the orchestrator's `SamplingBody` and `CallConfig`, which `orchestrator.py` already
  holds; none is either kind. §6.2 and §5.2 win. None of these shapes crosses a layer
  boundary, and `NormalizedText` in `schemas.py` would put normalization, which decides a
  claim's tier, outside the files `checks_version` hashes (§8.7). §13's check-internal
  exception becomes layer-internal and names all four, so the count stays two and
  CLAUDE.md's sentence on the sanctioned exceptions stays true.

---

## v1.3.10 — a misspelled case key is a load error (patch)

Theme: one fill found while planning phase 2a. No invariant moves; CLAUDE.md is unchanged.

**WARNING**
- **L103 §4.2, §8.5 — the case contract forbids unknown keys.** Fill: §8.5 makes a
  misspelled `expected_flags` entry a load error, but `EvalCase`, `PreserveItem`, and
  `NotAddItem` declared no `extra` policy, and Pydantic ignores unknown keys by default. A
  misspelled `draft:` left `draft=None`, silently turning an injected case into a model
  case: skipped by the free tier, then billed by the corpus run. A misspelled
  `must_preserve:` left a fidelity trap with nothing to check, a vacuous pass. All three
  forbid extra keys, as `ClaimDraft` and `SOAPNoteDraft` already do. `PreserveItem` and
  `NotAddItem` take it when they land, with the reference checks.

---

## v1.3.9 — the verdict is on the wire (patch)

Theme: one fill found while planning phase 2a. No invariant moves; CLAUDE.md is unchanged.

**WARNING**
- **L102 §4.2, §9.3 — `all_critical_passed` is serialized.** Fill: §4.2 declared the
  verdict a plain `@property`, which Pydantic does not serialize, so the response would
  carry `results` without the verdict. Every consumer (the 2a page, the phase-3 UI, a
  persisted report) would recompute it, and a recomputation is free to drop the
  vacuous-truth guard that keeps an empty or warning-only report from reading as passed
  (invariant 12). It is now a `computed_field`: in the body, and in the serialization
  schema `openapi-typescript` reads. mypy rejects decorators stacked on `@property`, so
  the line carries `# type: ignore[prop-decorator]`, the form Pydantic documents; strict
  mode reports the ignore if mypy ever stops needing it.

---

## v1.3.8 — the spec stops tracking the build (patch)

Theme: one conflict found at the phase-1 close. No invariant moves. CLAUDE.md changes in
the same commit for the close itself (its "Current phase" line), not for this patch.

**INFO**
- **L101 header, §14 — the spec stops tracking the build.** Conflict: the header's status,
  "skeleton / pre-build," and §14's Phase 1 note, "closest to done," vs §14's close
  procedure, which records build state in CLAUDE.md's "Current phase" line and a tag per
  phase. Only §14's record has a step that keeps it current; the other two go stale as the
  build moves. §14 wins: the header states the design's status and points at §14's record,
  and the Phase 1 note is removed.

---

## v1.3.7 — the static page has no blank outcome (patch)

Theme: one fill found while designing step 5's page. No invariant moves; CLAUDE.md is
unchanged.

**INFO**
- **L100 §9.10 — the static page has no blank outcome.** Fill: L92 covered a non-2xx whose
  body carries `error` and `request_id`. Two outcomes had no state: a fetch that rejects,
  which has no status and no body, and a response whose body lacks those fields. Anything
  but a result now renders its HTTP status, plus the code and request id when the body has
  both; a fetch with no response renders a fixed line that names no code, so it can't be
  read as one of §9.4's. §9.10's phase-1 paragraph cites ledger ids, not versions.

---

## v1.3.6 — the upstream status handler is total (patch)

Theme: one fill found while designing step 4c's handlers. No invariant moves; CLAUDE.md is
unchanged.

**INFO**
- **L99 §9.4, §11, §14 — the upstream status handler is total.** Fill: L71 mapped 4xx
  except 429, 5xx except 529, and 529, leaving the `APIStatusError` handler undefined for a
  429 that arrives as the base class and for any status outside 4xx/5xx. The SDK's factory
  builds `RateLimitError` for every 429, but the handler still needs an answer for each
  status it can receive. 429 joins 529 at 503 `upstream_busy`, checked first because 429 is
  also a 4xx; anything outside 4xx/5xx → 502 `upstream_error`. The handler branches on the
  status, never the subclass. Measured on SDK 1.9: the factory never builds
  `ServiceUnavailableError` or `DeadlineExceededError`, so an upstream 503 or 504 arrives as
  `InternalServerError` and maps to 502; 504 `upstream_timeout` stays our own client's
  timeout (L54). The status handler forwards no headers: `Retry-After` stays on
  `RateLimitError`'s row, the one behavior its handler does not share with the status
  handler. L71's test gains a base-class 429, 399 and 600, the factory's 503 and 504, a
  529 with `Retry-After` that the response drops, and a `RateLimitError` with and without
  it.

---

## v1.3.5 — framework error headers (patch)

Theme: one fill found while designing step 4b's handler. No invariant moves; CLAUDE.md is
unchanged.

**INFO**
- **L98 §9.4, §11, §14 — framework errors keep their headers.** Fill: L80 named the status
  the replacement handler keeps and was silent on headers, while FastAPI's default handler
  forwards `exc.headers`. A literal reading drops them and sends a 405 without `Allow`,
  which RFC 9110 requires. The handler forwards the exception's headers, as §9.4 already
  does for `Retry-After`. L80's test gains `Allow: POST` on the 405 and a 400 `http_error`
  case (a JSON body that is not valid UTF-8, which FastAPI raises as an `HTTPException`),
  so each of the handler's three branches has a test. "Routing codes" becomes "framework
  codes," since the 400 is not a routing error.

---

## v1.3.4 — refusal stop reason (patch)

Theme: one fill found while designing step 3c's loop. No statement changes, and no
invariant moves; CLAUDE.md is unchanged.

**WARNING**
- **L97 §5.4, §11, §14 — a refusal fails fast before the block lookup.** Fill: §5.4 handled
  both truncation stop reasons and a missing block, and §9.4 (L73) pinned a refusal with no
  block. A refusal *with* a tool block was unspecified: the loop would validate output the
  API had cut off, returning it as a success if it happened to validate, or buying
  validation retries against a classifier that fires again on the same input. Gated first,
  the block is never validated and the retry would be identical (invariant 16 as written).
  Same exception and code as L73's case; §9.4 is unchanged. `pause_turn`, `stop_sequence`
  and `end_turn` need no branch; a test pins every `StopReason` value to a decided path.

**Housekeeping (no ledger id — no behavior changes)**
- L49's v1.3 summary line names two of its three changes. It also covered §4.2 and §5.4:
  `OrchestratorError` carries the `usage` spent, failed attempts included — the meaning
  §4.2, §5.4, and §14 cite it for.

---

## v1.3.3 — Phase 1 build fills (patch)

Theme: three details the Phase 1 build would otherwise have decided silently, found while
sequencing the build. All three are fills; no statement changes and no invariant moves.
CLAUDE.md's CI sentence is updated in the same commit (L96); nothing else in it changes.

**WARNING**
- **L94 §5.2, §10, §14 — the output/input ratio is a knob, and the derived value is not.**
  Fill: §5.2 derived `max_output_tokens` as `≈ max_input_chars / 2`, "tunable," while
  invariant 10 bans magic numbers and §10 named no knob for the ratio — `config.py` could
  only hardcode the 2 or invent an unnamed knob. Now `output_tokens_per_input_char`
  (`gt=0`, default `0.5`, so behavior is unchanged) and
  `max_output_tokens = math.ceil(max_input_chars * ratio)`, a read-only property: as a field
  it could be set from the environment on its own, reopening "two knobs that must move
  together." Tests: a non-positive ratio raises at construction; the derived value is not
  in `Settings.model_fields`. (Rejected: a module constant — "tunable" makes it operational,
  and operational knobs live in `config.py`.)

**INFO**
- **L95 §5.2, §13, §14 — `get_client` lives in `orchestrator.py`.** Fill: §5.2 and §5.5
  specified its behavior and no module. It sits beside the `LLMClient` Protocol it returns,
  as a plain cached factory with no FastAPI import; `api.py` applies `Depends`. The module
  that owns the vendor format constructs the vendor client, and the orchestrator stays
  framework-free.
- **L96 §11, §13, §14; CLAUDE.md CI — CI runs the format check.** Fill: the spec's workflow
  said "ruff," CLAUDE.md's commands ran both `ruff check` and `ruff format --check`, and
  nothing said which one CI enforces. Both run in CI; a commit that is clean locally is
  clean on push.

---

## v1.3.2 — Phase 1 pre-build pass (patch)

Theme: a last pass over Phase 1 content before any code. Two findings came from outside the
spec — the Python SDK's 1.0 release (Aug 2026) and Anthropic's model-id scheme — and the
rest are gaps and one self-conflict in the Phase 1 surface. No design changes: every
invariant holds as stated; L82 changes how invariant 3 reaches the wire, not what it says.
CLAUDE.md invariants 3 and 15 are updated in the same commit.

**CRITICAL**
- **L82 §5.2, §5.5, §8.2, §13, §14 — `temperature` travels in `extra_body`.** Fill: the spec
  never constrained the SDK version, and SDK 1.0 removed the typed `temperature` / `top_p` /
  `top_k` parameters (`TypeError` at the call). The API still accepts the field on the
  models this call shape targets. `CALL_CONFIG` carries `extra_body={"temperature": 0}`,
  typed on our side by `SamplingBody`; the `LLMClient` Protocol declares `extra_body`; a
  fake-client test pins the value on every attempt; the smoke run records the SDK version.
  `anthropic>=1.9,<2` in `pyproject.toml`. Guard in CLAUDE.md inv. 3: deleting the field to
  satisfy the SDK is a silent invariant violation. (Rejected: pinning `anthropic<1`, which
  keeps the typed kwarg but starts the repo on a superseded major.)

**WARNING**
- **L83 §5.1, §5.2, §5.4 — the call config is typed.** Conflict: §5.4's sample
  (`messages: list[dict]`, an untyped tool dict, `**CALL_CONFIG` inferred as
  `dict[str, object]`) vs L74's SDK-typed Protocol and §14's "mypy clean" — six errors under
  `--strict`. The seam wins: `CallConfig` TypedDict, `SUMMARY_TOOL: ToolParam`,
  `messages: list[MessageParam]`. Runtime values and the `PROMPT_VERSION` recipe unchanged.
- **L84 §4.2, §5.2, §5.5, §10, §14, §17; CLAUDE.md inv. 15 — "pinned," not "dated."** Fill:
  "dated snapshot id" glossed "never an alias," and the gloss is false from the Claude 4.6
  generation on, where the dateless id is the pinned snapshot. The rule is unchanged; the
  word is corrected, and a date-suffix validator is ruled out.
- **L85 §5.2, §14 — L72's rationale corrected; the smoke run verifies the ceiling.** Fill:
  L72 said the SDK exposes no output ceiling; the Models API reports `max_tokens`. The knob
  stays declared (a boot-time fetch would put the network in CI); the L81 smoke run
  compares it against `models.retrieve(settings.model).max_tokens`.
- **L86 §4.1 — the claim's text is non-blank, like its quote.** Fill: `text` used
  `min_length=1`, so `"   "` validated and rendered as an invisible claim; L25 had already
  ruled whitespace empty at this boundary for the quote. `Quote` → `NonBlankStr`, used by
  both. `strip_whitespace` is not in the JSON schema: the tool schema is unchanged.
- **L87 §9.1, §9.4, §10 — the degenerate-input guard counts content.** Fill: a
  whitespace-only paste longer than `min_input_chars` passed the guard and bought a paid
  call. A validator checks the stripped length without mutating `raw_text` (spans index the
  exact paste from 2a). L70's test gains the whitespace case.

**INFO**
- **L88 §5.4, §11 — `model_context_window_exceeded` fails fast.** Fill: a second truncation
  stop reason; with a partial tool block it would have retried with a larger context.
  `TRUNCATION_STOPS` covers both.
- **L89 §4.2 — spine types declare domains.** Fill: L77's rule, applied to config only, now
  covers `TokenUsage` (`ge=0`, frozen) and `RunMetadata.validation_attempts` (`ge=1`).
- **L90 §14 — the Phase 1 `schemas.py` fence names its aliases.** Fill: the "ONLY" list
  omitted `Section` and `NonBlankStr`; a literal audit would have failed it.
- **L91 §13, §14; CLAUDE.md Commands — mypy runs strict.** Fill: "mypy clean" had no
  configuration; default mode missed the bare `list[dict]` that `--strict` catches.
- **L92 §9.10 — the static page renders errors.** Fill: L68's page had no non-2xx state; it
  now shows the `error` code and `request_id`, so the smoke run can't fail blank.
- **L93 §13 — the repo tree names the three documents.** Fill: §13 listed every module but
  not CLAUDE.md, the spec, or this changelog — the files the build reads most. All three sit
  at the root: CLAUDE.md must, to auto-load, and it cites the other two by bare filename.

---

## v1.3.1 — implementation decisions absorbed (patch)

Theme: the first build-room pass against v1.3 found details the spec left open and places
where it contradicted itself. They lived in CLAUDE.md as "decisions beyond spec v1.3," where
the spec-wins precedence rule ranked them *below* the text they corrected. This patch moves
each into the section it belongs to. No design changes. `(was I#)` maps each entry to its
former CLAUDE.md id; the `I#` ids are retired.

**CRITICAL**
- **L69 (was I2) §9.4, §9.8 — the 500 path logs structure, never messages.** Conflict: the
  §9.4 table's "logged in full, internally" vs L53's PHI rule. L53 wins; the row is fixed.
  Catch-all middleware inside the request-id middleware, not an `Exception` handler.
- **L70 (was I3) §9.4 — the default 422 handler is replaced.** Fill: FastAPI's default body
  echoes the entire paste as `input`.
- **L77 (was I10) §5.2, §10 — configuration fails at boot; the key is passed explicitly.**
  Fill: pydantic-settings never exports `.env` to `os.environ`, so an implicit key 401s
  everywhere except a shell that exports it. Required `SecretStr`; every knob declares its
  domain.

**WARNING**
- **L71 (was I4) §9.4 — upstream failures are attributed by status.** Conflict: the single
  `APIError` → "not my bug" row vs §9.4's rule that each code says whose fault it was. The
  rule wins: 4xx except 429 → 500, 5xx except 529 → 502, 529 → 503.
- **L74 (was I7) §5.5 — `LLMClient` declares explicit kwargs.** Conflict: `**kwargs` vs "mypy
  checks the seam." No loose signature satisfies both; the seam wins.
- **L75 (was I8) §5.2 — parallel tool use is disabled.** Conflict: §5.4's tool_result pairing
  contract vs a loop that answers only the first block. Prevented in `CALL_CONFIG`.
- **L78 (was I11) §5.2 — the client is built once per process.** Fill: FastAPI calls
  dependencies per request; `@functools.cache` on `get_client`.
- **L79 (was I12) §9.4, §9.8 — log fields render in the message.** Conflict: §9.4's `extra=`
  sample vs the requirement that every log line carries code and request id. The requirement
  wins; the sample is fixed.
- **L81 (was I14) §14 — phase 1 closes with one live smoke run.** Fill: nothing verified the
  real request shape against the real API.

**INFO**
- **L68 (was I1) §9.10, §13, §14 — the phase-1 display is a static page.** Fill: §14's
  "minimal display." `backend/static/` is sanctioned until `frontend/` lands.
- **L72 (was I5) §5.2, §10 — the model's output ceiling is a config knob.** Fill: L16 named no
  source for the ceiling.
- **L73 (was I6) §9.4 — phase-1 HTTP reach is named.** Fill: "every §9.4 row reachable in
  phase 1"; request-id middleware; the refusal path pinned.
- **L76 (was I9) §9.1, §9.10 — the phase-1 response is an edge shape.** Fill: §9.1 named no
  type. Also reconciles §9.10, which placed `SummarizeResponse` in `schemas.py` against §9.1
  and CLAUDE.md's sanctioned list.
- **L80 (was I13) §9.4 — framework default error bodies are replaced.** Fill: "every body has
  one shape" vs FastAPI's `{"detail": ...}` on 404/405.

**Housekeeping (no ledger id — no behavior changes)**
- The changelogs moved out of the spec into this file. The spec header states where history
  lives and the versioning rule.
- The sanctioned-shapes rule moved from CLAUDE.md into §13; the two spec comments that cited
  CLAUDE.md for it now cite §13.
- The spec file drops the version from its name (`PROJECT_01_NOTEPILOT.md`); the header
  carries the version.

---

## v1.3 changelog (design-room walkthrough deltas)

Severity uses the project's own triage enum. `L#` is the walkthrough ledger id; each delta
names the section it lands in. Theme of this pass: **v1.1 fixed the scoring; v1.2 fixed
what the checks can see; v1.3 fixes what the checks *assume* — where a danger comes from,
what the model is allowed to omit, and which question a test is actually asking.**

**DECISIONS (vetoable, like every D)**
- **D7 — the model is a scribe, not a consultant (§5.3).** Assessment records only what the
  clinician stated, certainty verbatim; a patient's self-diagnosis is Subjective; an empty A
  is a valid note. Reasons: authorship, product category (documentation, not decision
  support), and a prompt that no longer contradicts itself.
- **D8 — the judge stays, reframed as entailment (§8.2).** `text_entailment_judge`: is each
  claim's text entailed by its source span? One batched call, WARNING, behind an injected
  `Judge` protocol. v1.2's showcase ("BP 190/110 → hypertensive urgency") is now a
  detection trap, not sound inference.
- **D9 — cross-reactivity is keyed on the R1 side chain (§7).** The evidence the table cites
  is side-chain-level; now the table is too.
- **D10 — a dropped NKDA is a WARNING (§8.4).** Undocumented status prompts a re-ask; it is
  not a missed allergy. NKA ≠ NKDA in the lexicon.
- **D11 — corpus repeats (§8.7).** `corpus_repeats` (default 3), per-case pass fraction,
  flaky cases named, n and k beside every number.
- **D12 — `diagnosis_in_quote` ships (§8.4).** After D7 an invented assessment is a
  fabrication, and the judge can't gate a CRITICAL (inv. 7) — so a deterministic backstop.
  Certainty upgrade = CRITICAL, downgrade = WARNING.
- **D13 — `med_status_consistency` ships (§8.4).** Presence belongs to `drug_in_quote`;
  active-vs-stopped belongs to this check. One error, one finding.
- **D14 — the unspecified penicillin allergy, and reaction type (§7, §8.8).** "PCN allergy":
  penicillins CRITICAL, every cephalosporin WARNING ("specify to refine"). Reaction type is
  not extracted in v1 — a stated limitation.
- **D15 — `quote_informativeness` ships (§8.4).** A deterministic floor under the judge for
  degenerate quotes; lexicon entities count as informative ("NKDA").
- **D16 — one planted danger per trap (§8.5).** An authoring rule instead of an `about`
  field; the residual gap is stated in §8.8; `about` → backlog.
- **D17 — the omission law (§8.4; CLAUDE.md inv. 17).** Every CRITICAL check states, per
  input, what happens when the model omits it; an omission that silences the check is
  covered by another live check or declared a CI-only gap.

**CRITICAL**
- **§8.5, §4.2, §11 — injected-draft cases (L42).** v1.2 asked raw text to make a good model
  fabricate on cue; at `temperature=0` it mostly won't, so every fabrication trap would fail
  nearly every run. `EvalCase.draft` injects the planted mistake, skips the model, and runs
  free on every commit. The paid corpus now measures only model behavior.
- **§8.7, §4.2 — an error never satisfies an expectation (L43).** A crashed expected check
  was `passed=False`, therefore *fired*: the showpiece trap passed on a crash.
  `EvalResult.errored` replaces the magic `detail="check_error"`.
- **§6.4, §8.4 — consistency checks compare against the source span, not the model's quote
  (L35).** A Tier 3 quote could smuggle a swapped drug or a flipped "denies" under a yellow
  badge. `claim.text` vs `raw_text[source_span]`.
- **§7, §8.4 — the same-drug allergy was invisible (L30).** Allergens were matched as named
  against a class-keyed table: "allergic to amoxicillin" + amoxicillin passed. Allergens now
  normalize like drugs, and the check resolves drug → class → R1.
- **§8.4 — the contraindication survives the model dropping the drug (L51).** Drugs are read
  from the note ∪ `new_prescriptions(raw)`; a raw-only finding goes to the banner.

**WARNING**
- **§2, §4.2, §8.7, §17 — four metrics, never one (L3).** Detection recall, control
  specificity, model fidelity, fidelity caught. `pass_rate` is kept and never quoted alone.
- **§5.3 — never omit safety-critical facts (L50); D7's Assessment definition (L20).**
- **§5.4, §9.4 — the orchestrator boundary (L12, L13, L14).** The `try` wraps
  `model_validate` only; usage is summed across attempts, with `validation_attempts`;
  truncation on an input the route already accepted is `OutputTruncatedError` → 502, not 422.
- **§4.1 — D6 is enforced, not promised (L6).** Frozen `ClinicalClaim` / `SOAPNote`; flags
  and claims are tuples.
- **§4.2, §8.2, §9.5 — judge tokens have a write path (L7):** `EvalReport.judge_usage`.
- **§0, §13, CLAUDE.md inv. 1 — domain vs edge (L17).** The orchestrator and the judge
  client are edge adapters; evals call a `Judge` protocol, never the vendor format.
- **§6.2 — the index map survives Unicode (L26);** µ/μ folded. **§6.3 — Tier 3 runs in
  normalized space (L27).**
- **§7 — negation has a scope rule (L31),** and finding cues are split from
  medication-status cues. **`new_prescriptions` (L41)** powers live
  `new_prescription_preserved` (WARNING) and L51.
- **§8.4 — polarity in the reference checks (L36);** contraindication findings carry the
  allergy claim's id (L37).
- **§8.7 — tri-state `case_verdict` with not-applicable cases (L44); `checks_version` +
  `git_dirty` (L45); per-case catch parity and recorded all-failed runs (L46).**
- **§8.5 — Assessment fixtures (L23):** invented-A trap, hedged-A and empty-A controls.
- **§9.4, §9.8 — PHI-safe logs and error bodies (L53); LLM timeouts → 504 (L54); the spend
  cap reserves before spending (L56).**
- **§8.4, §10 — an empty note from clinical input is not green (L55).**
- **§9.5 — production lineage parity (L57).**
- **§5.2, §10 — `max_validation_retries` (L5).** Validation retries are ours; transport
  retries are the SDK's. Two loops, two names.
- **§14 — phase 2 split into 2a / 2b / 2c (L59); CI from phase 1 (L60); every phase has exit
  criteria (L61).**

**INFO**
- L1 §1 v1 is a review surface · L2 §1 unsourced market figure cut · L4 §3 principle 6
  named · L8 §4.1 `grounding_score` kept on near-misses · L9/L10 §4.2 explicit `species`,
  typed `must_not_add` · L11 §4.2 every `RunMetadata` field has a producer · L15 §5.4
  `PROMPT_VERSION` hashes the full call config · L16 §5.2 derived `max_output_tokens`
  validated at boot · L19 §5.5 the client is a `Protocol` · L24 §9.10 empty A renders ·
  L25 §4.1 quote stripped at the boundary · L29 §0 diagram fixed · L33 §7 parsed doses,
  multi-valued extractors · L38 §8.7 downgrade-only severity enforced · L40 §8.2 judge
  batched · L49 §8.6/§8.7 orphan tier entry removed, judge is a parameter · L58
  §9.8/§9.10 proxy headers, new UI states, edge-shape sanction · L62 §11 property tests
  restated · L63 §16 "Arc" vs "Phase" · L64 §17 DoD contradiction fixed.

**Found while drafting v1.3**
- **L65 (INFO) §7, §13:** `extract.py` necessarily imports `lexicons.py`; v1.2 said it
  "imports nothing." Now: `extract.py` imports only `lexicons.py`, and `lexicons.py`
  imports nothing — severities are stored as strings, so `clinical/` never imports the spine.
- **L66 (INFO) §8.5:** `detect_vital_drift` expected no eval check — it tests grounding's
  numeric guard. Moved to `tests/test_grounding.py`.
- **L67 (INFO) §7:** `ALLERGY_CLASSES` (class → members) and `DRUG_CLASSES` (member → class)
  were two encodings of one relation, free to disagree. One map: `DRUG_CLASS`.

---

## v1.2 changelog (second adversarial review deltas)

Severity uses the project's own triage enum. Each delta names the section it lands in.
Theme of this pass: **v1.1 fixed the scoring; v1.2 fixes what the checks can see.**

**CRITICAL**
- **§8.4, §8.5 — the reference-based checks now exist.** `must_preserve` /
  `must_not_add` had no consumer; the registry's `requires_reference` bit had zero
  members; omission — "the most dangerous error" — had no check. `check_must_preserve`
  and `check_must_not_add` specified. `must_preserve` entries are now typed
  (`PreserveItem`, DECISION D4) so a dropped allergy is CRITICAL and a dropped dose is
  WARNING.
- **§6, §7, §8.4 — the text-vs-quote gap closed.** Grounding proved the *quote* exists,
  not that the claim's *text* follows from it: `text="start amoxicillin"` /
  `quote="start antibiotics"` grounded clean at Tier 1. Same hole hosted negation flip
  and dose mismatch (listed in §8.6, never specified). New family of **claim-local
  consistency checks** — drugs, doses, and negated terms in `claim.text` must appear
  with the same value/polarity in `claim.source_quote`. The §7 primitives now operate
  on plain strings so one function serves text, quote, and raw source alike.
- **§6.3 — the empty quote no longer grounds clean.** `"abc".find("") == 0`: an empty
  `source_quote` earned span `(0, 0)` and no flag. The §6.5 guard now sits *before*
  Tier 1 in the code, and `ClaimDraft.source_quote` carries `min_length=1` so the
  tool schema itself rejects it.
- **§6.3 — fuzzy tier stops trusting numbers.** `"BP 130/110"` vs `"BP 190/110"`
  scored ≥ 85 → a PARAPHRASED span on the wrong vital, yellow instead of red. Tier 3
  now requires every digit token in the quote to appear verbatim in the aligned span,
  else demotes to Tier 4.
- **§7 — allergy-context exclusion.** "Allergic to penicillin" contains a drug name;
  naive `extract_drugs` fed it to the contraindication check, which then fired on every
  penicillin-allergic patient. Lexicon gains allergy-context cues as an exclusion class
  beside negation cues. The clean control that catches this regression is in the corpus.
- **§8.2, §8.7, §9.1 — the judge no longer breaks the engine.** `run_checks` was sync,
  §9.2 called evals "CPU-bound, inline," and D2 put a model call inside evals.
  `run_checks` is async; `Check` carries `severity` and `needs_client`; judge tokens
  land in `RunMetadata`.
- **§8.7 — fail closed on crashes.** One `OrchestratorError` aborted a whole corpus run
  with no record; an empty corpus divided by zero; a check that raised 500'd a
  production request. Per-case and per-check `try` boundaries; a crashed check is a
  `passed=False` result (invariant 12, applied to exceptions).

**WARNING**
- **§4.1, §4.2, §7, §9.7 — findings can anchor to claims.** Grounding stamps
  `ClinicalClaim.id`; `EvalResult.claim_ids`; extractors return mentions with their
  claim id. The two UI render channels are now derivable from the contract.
  DECISION D6: evals write to the *report*, never to `ClinicalClaim.flags`.
- **§8.7 — one name per check.** `EvalResult.check` and `fn.__name__` disagreed.
  `@register_check(name=, severity=)` stamps results; registry is a dict that rejects
  duplicates; the corpus loader validates every `expected_flags` entry against it.
- **§4.2, §5.4, §5.5, §8.7 — lineage can't lie.** `prompt_version` is a hash of the
  system prompt + tool schema; `corpus_version` a hash of the cases dir; model id is a
  dated snapshot; `CorpusRunRecord` gains `git_sha`, `judge_enabled`, token totals.
  DECISION D5: the jsonl is committed from local runs; CI dispatch uploads an artifact.
- **§8.7 — WARNING false positives are visible.** `CaseResult.unexpected_fired` (all
  severities) added as a diagnostic; the verdict stays CRITICAL-scoped and now says so.
- **§5.4 — retry policy made consistent.** Missing `tool_use` block now fails fast
  (identical retry at `temperature=0` is the same wasted spend as `max_tokens`).
  `max_tokens` coupled to `max_input_chars` in config (output copies input quotes).
- **§5.4, §9.4 — honest HTTP codes.** `OrchestratorError` split: `InputTooLongError`
  → 422, `ModelOutputError` → 502; upstream 429 → 503.
- **§9.1, §9.6 — persistence plumbing.** `persist` opens its own session (FastAPI
  ≥ 0.106 closes `yield` dependencies before background tasks run). Note `id` is
  generated in the route and returned in the response.
- **§9.8 — deployed-demo realities.** Rate limit + daily spend cap on `/summarize`;
  PHI banner + `persist_enabled` flag; the live demo is not a PHI sink.
- **§8.4 — allergy omission runs live.** `check_allergy_preserved` is reference-free:
  `allergies(raw) − allergies(note)` is a high-trust derivation by §8.1's own rule.
  `PENICILLIN_CLASS` → `ALLERGY_CLASSES` + `CROSS_REACTIVITY` with per-pair severity.
- **§9.10 (new), §15 — frontend contract + product drift.** Span rendering rule,
  UI states, `openapi-typescript`. Edit + sign-off persistence named in the backlog.

**INFO**
- **§6.3, §5.2 — magic numbers in spec code are `settings.*`.** Stated once, applied.
- **§8.4 — contraindication check reports all violations,** not the first.
- **§7 — lexicon classes are generic-only** post brand→generic normalization.
- **§8.5, §17 — corpus format (YAML per case), N set, per-species floor, coverage test.**
- **§8.7 — `score_corpus` runs cases concurrently** (`gather` + semaphore).
- **§11 — property-based round-trip on the index map; tool-schema snapshot test.**
- **§5.3 — prompt gaps closed** (contiguous span, shortest span, one fact per claim,
  negation/NKDA verbatim). **§4.1 — `grounding_score`** on PARAPHRASED claims.
- **§15 — prompt caching** added to the backlog. `timezone` import fixed.

---

## v1.1 changelog (adversarial review deltas)

Severity uses the project's own triage enum. Each delta names the section it lands in.

**CRITICAL**
- **§8.7 — corpus scoring semantics fixed.** `score_corpus` scored detection-style traps
  backwards: a fired CRITICAL flag (the pipeline *catching* the trap) counted as a case
  failure. New per-case verdict `case_passed()` consumes `expected_flags` — the answer
  key is now load-bearing, and clean controls get first-class false-positive accounting.
- **§5.4 — retry loop API contract fixed.** The correction message after a failed
  validation is now a `tool_result` block (`is_error=True`, referencing the
  `tool_use_id`). The prior plain-text user message violated the API's tool_use →
  tool_result pairing and would 400 on the first retry.
- **§4.2 — `all_critical_passed` vacuous-truth guard.** `all()` over zero CRITICAL
  results returned `True`; an unexamined note read as a safe note. Now requires at least
  one CRITICAL result to report green.
- **§8.4 — `EvalResult` instantiation fixed.** Pydantic models take keyword args only;
  the positional example crashed as written.
- **§5.4 — truncation + missing-tool-block handled.** `stop_reason == "max_tokens"` now
  raises immediately (at `temperature=0`, retrying identical input reproduces identical
  truncation — retries are wasted spend); an absent tool_use block retries instead of
  raising `StopIteration`.

**WARNING**
- **§4.1 — spine flattened.** `section` was double-encoded (a field on every claim AND
  four section-named lists — two encodings of one fact can disagree). Single encoding
  now: flat `claims` list; the `section` field is the sole source of truth; display
  groups via `by_section()`.
- **§8.7 — corpus runs are now persisted** (`evals/runs/corpus_runs.jsonl`, one
  `CorpusRunRecord` per run). The regression thesis has a queryable history for CI runs,
  not just production notes.
- **§3, §5.2 — determinism claim made honest.** `temperature=0` *minimizes variance*;
  it does not guarantee bit-identical outputs from a served API. The eval design already
  tolerates residual nondeterminism (pass-rates over a corpus, not golden-output diffs) —
  the spec now claims exactly that, no more.
- **§4.2, §5.4 — token usage captured.** `RunMetadata` carries
  `input_tokens`/`output_tokens` from `resp.usage`; the model-choice story gains a
  measured cost axis.
- **§7, §8.6 — dose extraction scoped in** (DECISION D1, vetoable). The dose-mismatch
  WARNING check had no extraction primitive; `extract_doses()` added as a
  regex/deterministic primitive.
- **§8.2, §14 — LLM-as-judge scoped** (DECISION D2, vetoable). One judge check
  (`check_assessment_support_judge`, WARNING tier, config-gated) ships in build phase 2.
- **§8.7 — check registry defined.** `evals/registry.py`: frozen `Check` dataclass +
  `@register_check` decorator. Adding a safety check is a documented one-step operation.

**INFO**
- **§9.1, §9.6 — persist is a literal sink** via FastAPI `BackgroundTasks`.
- **§9.5 — column renamed** `critical_passed` → `production_critical_passed` (per-note
  production verdict ≠ CI corpus rate; the name now says which one it is).
- **§9.8 — added:** CORS middleware, input max-length guard, logging/observability
  paragraph, migrations decision (DECISION D3: `create_all` phases 1–2 → Alembic in
  phase 3).
- **§6.2 — normalizer now delivers the §6.5 promise** (smart quotes / en-dashes mapped
  before comparison).
- **§11, §13, §14, §17 — CI made real:** GitHub Actions workflow, badge in the DoD,
  `pyproject.toml`/`uv.lock` shown in the tree (uv owns the env).
- **§4.1 — `Field(default_factory=list)`** convention for mutable defaults.
