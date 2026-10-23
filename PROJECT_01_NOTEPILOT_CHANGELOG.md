# PROJECT 01 — NotePilot · Spec changelog

The history of `PROJECT_01_NOTEPILOT.md`: what changed in each version, and why. The spec
states what the system *is*; this file records how it got there. Newest first.

**Reading the ids.** `L#` is the delta ledger: one id per change, numbered continuously
across versions (v1.3's walkthrough opened it at L1; v1.3.1 continues at L68; v1.3.2 at L82; v1.3.3 at L94; v1.3.4 at L97; v1.3.5 at L98; v1.3.6 at L99; v1.3.7 at L100; v1.3.8 at L101; v1.3.9 at L102; v1.3.10 at L103; v1.3.11 at L104; v1.3.12 at L105; v1.3.13 at L106; v1.3.14 at L107; v1.3.15 at L111; v1.3.16 at L112; v1.3.17 at L113; v1.3.18 at L116; v1.3.19 at L118; v1.3.20 at L120; v1.3.21 at L122; v1.3.22 at L124; v1.3.23 at L128; v1.3.24 at L131; v1.3.25 at L134; v1.3.26 at L136; v1.3.27 at L139; v1.3.28 at L140; v1.3.29 at L141; v1.3.30 at L143; v1.3.31 at L144; v1.3.32 at L148; v1.3.33 at L151; v1.3.34 at L156; v1.3.35 at L157; v1.3.36 at L164; v1.3.37 at L166; v1.3.38 at L167; v1.3.39 at L172; v1.3.40 at L176; v1.3.41 at L179; v1.4 at L180; v1.4.1 at L197; v1.4.2 at L200; v1.5 at L201; v1.6 at L214; v1.6.1 at L221; v1.6.2 at L222; v1.6.3 at L223; v1.6.4 at L224; v1.6.5 at L228; v1.6.6 at L232; v1.6.7 at L234; v1.6.8 at L235; v1.6.9 at L240; v1.6.10 at L244; v1.6.11 at L250; v1.7 at L252; v1.7.1 at L259; v1.8 at L261; v1.8.1 at L271; v1.8.2 at L275; v1.8.3 at L277; v1.8.4 at L278; v1.8.5 at L280; v1.8.6 at L281; v1.8.7 at L283; v1.9 at L285; v1.9.1 at L297; v1.9.2 at L298; v1.9.3 at L300; v1.9.4 at L301; v1.9.5 at L304; v1.9.6 at L307; v1.9.7 at L308; v1.9.8 at L310), so
an id never needs its version to be unambiguous. `D#` is a decision record, vetoable like every D.
Where a decision also has a DECISION block in the spec, the block is the current statement
and the entry here is its origin. Severity uses the project's own triage enum. v1.1 and v1.2
predate the ledger; their deltas are cited by section.

**Versioning.** Patch (v1.x.y): fills a detail the spec leaves unspecified, or resolves a
conflict between two spec statements, citing both and naming which wins. Minor (v1.x):
anything else. Every change gets the next `L#`.

---

## v1.9.8 — the judged check (patch)

Theme: 2c's first step builds `text_entailment_judge` (D8) in `evals/`, against the `Judge`
protocol (L111) and a fake judge; the judge's client is a later step. §8.2 sends the judge
every pair in one call (L40) and left two of the check's details open, filled here. No
invariant moves; CLAUDE.md is unchanged.

**INFO**
- **L310 §8.2 — the judge's pairs, and a note with none.** Fill: §8.2 named the pairs
  `(text, span)` and §8.4 reads a span in its clause (L261), but nothing said which claims
  make the pairs or what a note with none does. The pairs are the claims with a span, in
  claim order, each its text and its clause; a claim with no span is skipped, as the
  consistency family skips it (§8.4). A note with none makes no call, and the check passes:
  one call per note is no call on no pairs.
- **L311 §8.2 — a verdict count other than the pair count.** Fill: the protocol returns one
  verdict per pair, and nothing said what follows when a judge doesn't. Paired by position,
  a short or long list would hang a verdict on the wrong claim, so the check raises, and
  `run_checks` reports the raise as an errored result (invariant 12), never a pass.

## v1.9.7 — v1.9's re-baseline (patch)

Theme: v1.9's live measurement, recorded as v1.8.7 recorded v1.8's (L283, L284). The
re-baseline ran on `6870541`, v1.9's code complete, and §14 called for no smoke run. With
it, the laterality revision meets L256's gate, as the scope-rule revision did with v1.8's,
so phase 2c opens. No invariant moves; CLAUDE.md is unchanged.

**INFO**
- **L308 §14 — no smoke run for v1.9.** Fill: §14 repeats the smoke run at a change of
  request shape or of the pinned model (L81, L185), and v1.9 changes neither:
  `PROMPT_VERSION` is a99d6d205d0e, as at v1.7's smoke run (L259) and v1.8's re-baseline
  (L283), and `uv.lock`, `config.py`, `orchestrator.py`, and `pyproject.toml` are unchanged
  since `4877d3d` (measured).
- **L309 §5.3 — v1.9's re-baseline: all 72 repeats pass.** Measured: one run on `6870541`,
  `git_dirty` false, `prompt_version` a99d6d205d0e, `checks_version` 671078539429,
  `corpus_version` 040ccf7c0d67, 72 repeats, each in one validation attempt. Detection
  recall 1.0, control specificity 1.0, model fidelity 1.0, `fidelity_caught` None, pass rate
  1.0, no flaky case; 115,251 input and 15,398 output tokens. The verdicts are v1.8's, and
  neither revision's checks moved one: this run's drafts replay unmoved under v1.8's checks
  at `bfc9827`, and v1.8's drafts replay unmoved under v1.9's, so v1.9's readings and its
  laterality check change no verdict the corpus holds. `laterality_consistency` fired on no
  repeat, and no reference check fired on any. As under v1.8, `allergy_contraindication`
  fired on all 24 detection repeats and on the 3 of `control_pcn_allergy_cephalexin`, which
  pass. `quote_informativeness` (WARNING) fired on two repeats of `fidelity_no_htn_urgency`,
  whose claim "Asymptomatic" quoted the one word, against one under v1.8; the drafts moved
  it, since replayed under v1.8's checks they fire it on the same two. 14 of the 24 cases
  gave one draft across their repeats (11 under v1.8), and no case changed verdict across
  its repeats.

## v1.9.6 — entry 6's label (patch)

Theme: L286's label, built, with what Claude Code's review of the build found. §7 has
`must_preserve` read a laterality label and the note at the shorter width, which merges the
sites `SIDE_SITES` spells out on one side; changing that width is a decision, so §8.8 states
the cost and the deferred-amendments issue holds the fix (entry 37). Cal approved the patch
and signed `SITE_WORDS` on Oct 22, before the code that depends on it, which lands with it
in one commit. The committed records replay as at v1.9. No invariant moves; CLAUDE.md is
unchanged.

**CRITICAL**
- **L307 §8.8 — a label's site, one word wide.** Fill: §8.8 states it. `must_preserve` reads
  a laterality label and the note at `SITE_WORDS`' narrowest width, one word, where "lower
  quadrant", "lower lobe", and "lower extremity" all read "lower": a "RLQ" label is kept by
  "Right lower lobe consolidation" or "RLE edema", a "right lower lobe" label by "RLQ
  tenderness", and a "LUL" one by "Left upper extremity weakness" (measured on the build). A
  dropped side at one of those sites goes unflagged where the note charts the same side at
  another, a silent miss on a CRITICAL label. No case labels one, so the miss is latent;
  reading a label at the widest width it names a site at, and the note at that width, would
  close it at the cost of a label that names more than its site, so the deferred-amendments
  issue holds it (entry 37). A test pins the cost.

## v1.9.5 — entry 6's reading (patch)

Theme: L285, built, with what the adversarial pass found past part two's rows. Two details
§7 left open are filled, and two ways a side goes unread are stated, the deferred-amendments
issue holding the decisions (entry 36). The build adds "left-side" and "right-side" to
`SIDE_CUES`, as the "-sided" forms are. Cal approved the patch and signed the four side
tables on Oct 22, before the code that depends on them, which lands with them in one commit.
`extract_laterality` lands first; its label and its check land in later commits (L286,
L287), and `SITE_WORDS` with the first that reads it. The committed records replay as at
v1.9. No invariant moves; CLAUDE.md is unchanged.

**CRITICAL**
- **L305 §7 — a two-letter side takes its period.** Fill: §7 counts a bare letter before a
  word, which left the abbreviation's period unread, so "Rt. knee pain" named no side and
  "Left knee pain" citing it passed the prototype's check, a silent swap (prototyped). "Lt."
  and "rt." now read as "lt" and "rt" do. A lone "L." or "R." stays none, since it is also
  an initial: "Dr. R. Smith" names no side (measured).
- **L306 §8.8 — two ways a side goes unread.** Fill: §8.8 states them. "/" and "&" join no
  sides, since §7's joins are `_JOINS`, and a bare letter before a comma is none, since §7
  counts one only before a word, so "Left & right knee pain" and "L, R knee pain" read the
  right knee alone, and a faithful "Left knee pain" citing either fires the prototype's
  check, a loud false CRITICAL. A side charted after its site names none ("Chest pain on the
  left", "Edema in the lower extremity, left"), and a clause naming no side contradicts no
  claim, so "Right-sided chest pain" citing "Chest pain on the left" passes it, a silent
  swap (prototyped). Both are decisions, so the deferred-amendments issue holds them (entry
  36), and tests pin the readings.

**INFO**
- **L304 §7 — a site holds no function word.** Fill: §7 called a site the words after a side
  but not which words, and the prototype barred only a first function word, so "R knee and L
  ankle" read the right side at "knee and" at two words (measured on the build). A site now
  holds none, so a join or an article ends it: that row reads no two-word site, and "knee"
  and "ankle" at one word.

## v1.9.4 — entry 27's certainty (patch)

Theme: L292, built, with what the adversarial pass found past the sheet's rows. Retiring
L278's reread leaves L279's restating rule nothing to except, and a confirming pre-cue met
L135's differential; one is a fill and one a conflict, both §7's. The ruled "less likely"
also took away an accidental reading that comparatives leaned on, a decision §8.8 states and
the deferred-amendments issue holds (entry 35). The build adds the copula forms of L292's
two certainty cues ("is unlikely", "is less likely"), as "was confirmed" is
`CONFIRMING_POST`'s. Cal approved the patch and signed `CONFIRMING_CUES`, `CONFIRMING_POST`,
and `CERTAINTY_POST`'s new entries on Oct 21, before the code that depends on them, which
lands with them in one commit. The committed records replay as at v1.9. No invariant moves;
CLAUDE.md is unchanged.

**CRITICAL**
- **L302 §7 — a differential reweighs a confirmed mention.** Conflict: L292's confirming
  pre-cue labels the diagnosis after it, and L135's differential governs the mention before
  it only where no other cue does, so "CT shows PE vs atelectasis" read the embolism
  definite on the build (measured), a silent upgrade of everyday radiology wording;
  `b0e6ab2` read it possible. A confirming cue asserts what a bare mention does, so the
  differential reads a confirmed mention as it reads one no cue governs. A faithful
  "Pulmonary embolism" claim citing it fires `diagnosis_in_quote`, as at `b0e6ab2`
  (measured).
- **L303 §8.8 — a comparative.** Fill: §8.8 states it. At `b0e6ab2`, the "likely" inside "PE
  less likely" read as a pre-cue, so "PE less likely, PNA more likely" read the embolism
  definite and, by accident, the pneumonia probable. With L292's "less likely" read as one
  cue, the embolism reads possible and the pneumonia definite: a "Pneumonia" claim citing
  "PNA more likely" passes `diagnosis_in_quote`, where `b0e6ab2` fired it, and a faithful
  "Probable pneumonia" fires it (measured). Adding "more likely" as a probable post-cue
  reads that row right and "PNA more likely than PE" with the embolism definite, the
  diagnosis the note disfavors, where `b0e6ab2` read it probable (prototyped). A comparative
  is a decision, so the deferred-amendments issue holds it (entry 35), with "unlikely"
  before a diagnosis ("Unlikely PE" reads definite at both). A test pins the cost.

**INFO**
- **L301 §7 — a restatement is a repeat.** Fill: §7 says how L279's restatement reads once
  L292 retires L278's reread. L279 excepted a restatement from the reread ("r/o pulmonary
  embolism (PE)" reads rule-out alone); with every window keeping its repeats, a restatement
  is one of them, so the exception has nothing left to except. The code that ran it goes
  with the reread, and its tests read as before.

## v1.9.3 — entry 27's affirmation (patch)

Theme: L291, built. v1.9's docs commit stated L291 in the changelog and §8.8, and named §7
in its heading, but §7 never stated the rule and its lexicon block listed no table for the
cue; this patch fills both. The adversarial pass, run on the build past the sheet's rows (a
"/" or "&" list, a semicolon, a run-on header, a second negation, a colon form, a drug, a
diagnosis), found no new misreading. Cal signed `AFFIRMING_POST` on Oct 21, before the code
that depends on it, which lands with it in one commit. The committed records replay as at
v1.9. No invariant moves; CLAUDE.md is unchanged.

**INFO**
- **L300 §7 — an affirmation, stated.** Fill: §7 states L291's rule, and its lexicon block
  lists `AFFIRMING_POST`. An `AFFIRMING_POST` cue ("present") after the second mention a
  negation's window reads, across a comma and with no "and" or "or" since the negation,
  takes that mention back out of the window. "Not present" is a longer phrase in
  `FINDING_NEG_POST`, so it wins and negates. The rule is the scope engine's, so it reads
  findings, drugs, and diagnoses alike: "No metformin, lisinopril present" reads the
  lisinopril active, and "No PNA, PE present" the embolism definite (prototyped).

## v1.9.2 — entry 26's build (patch)

Theme: L290, built, with what the adversarial pass found past the sheet's rows. A post-cue
denial now reads as the pre-cue one has since L129, and so a contested allergy, documented
after the patient's denial, reads no allergen where `ca6dbdf` read one by accident. Keeping
a contested allergy is a decision, so §8.8 states the cost and the deferred-amendments issue
holds the fix (entry 34), as v1.9.1 did for a stop verb's object (L297). Cal approved the
fill, and signed `DENIED_ALLERGY_CUES`, on Oct 21, before the code that depends on them,
which lands with them in one commit. The committed records replay as at v1.9. No invariant
moves; CLAUDE.md is unchanged.

**CRITICAL**
- **L298 §8.8 — a contested allergy.** Fill: §8.8 states it. L290 reads a denied allergy in
  either form, and a denial reads before what follows it, so "Patient denies PCN allergy but
  chart lists it", "Patient denies PCN allergy, though listed in chart", and "PCN allergy:
  denied by patient, documented by pharmacy" read no allergen, where `ca6dbdf` read
  penicillin; "Denies allergy to penicillin but chart lists it" has read none since L129
  (measured). Beside "Start amoxicillin 500 mg tid", `ca6dbdf` fires
  `allergy_contraindication` and `allergy_preserved`, and this build fires neither
  (measured): a silent miss on an allergy the chart documents. Naming the allergen again
  keeps it ("Denies PCN allergy; chart lists PCN allergy"), and so does a denial after the
  allergy ("PCN allergy (patient denies)", "Chart lists PCN allergy; patient denies",
  measured). A test pins the cost.
- **L299 §8.8 — a denial's reach.** Fill: §8.8 states it. Claude Code's run of this build
  measured two loud costs past the sheet's rows. A denial ends its negation's window, so an
  allergy named after it with its own cue reads on its own: "No PCN allergy or sulfa
  allergy" and "Denies PCN allergy and sulfa allergy" read a sulfa allergy, and a faithful
  "No PCN or sulfa allergy" fires `allergy_preserved`, as at `ca6dbdf`, which read the
  penicillin too. A denied-allergy cue's window crosses a comma, as L276 states for a
  negation's: "Not allergic to PCN, on amoxicillin 500 mg tid" reads the amoxicillin with no
  status, where `ca6dbdf` read it stopped, and a faithful "On amoxicillin 500 mg tid" fires
  `drug_in_quote` where `ca6dbdf` fired `med_status_consistency` (measured). The run found
  one more, which this build fixes, since §7 has a negation post-cue deny only right after
  the allergy cue: a mention between them kept the cue's allergens open, so "PCN allergy:
  amoxicillin denied" denied the penicillin. Tests pin all three.

## v1.9.1 — entry 25's build (patch)

Theme: L288, built, with what the adversarial pass found past the sheet's rows. A stop verb
that names no drug reaches a drug after it in its sentence, and the four verbs L288 adds
carry that from v1.3's stop cues into everyday charting ("Interrupted sleep"). Narrowing a
stop verb's reach is a decision, so §8.8 states the cost and the deferred-amendments issue
holds the fix for every stop verb (entry 33), as v1.8.6 did for a prn's reach (L282). Cal
approved the fill, and signed L288's entries, on Oct 21, before the code that depends on
them, which lands with them in one commit. The committed records replay as at v1.9. No
invariant moves; CLAUDE.md is unchanged.

**CRITICAL**
- **L297 §8.8 — a stop verb's object.** Fill: §8.8 states it. A stop cue's window governs
  the drugs in it whatever the cue's own object, and L288 adds "holding", "interrupt",
  "interrupted", and "interrupting": "Interrupted sleep, takes metformin nightly",
  "Interrupted by pain, metformin given", "Pt holding her arm, on apixaban", "Holding
  pressure, takes apixaban", and "Interrupt the infusion if rash, apixaban tonight" read the
  drug stopped, where `edd6c05` read it active, and "Holding pressure on the site, apixaban
  continued" adds stopped (prototyped). v1.3's cues already read so ("Hold pressure, takes
  apixaban", "Held her breath, on metformin", measured at `edd6c05`). A faithful "Takes
  metformin nightly" citing "takes metformin nightly" there fires `med_status_consistency`,
  and "Metformin stopped" passes (measured). A stop verb that governs only the list right
  after it, as an indication cue does (L280), reads all six right and "Holding home
  apixaban" active, as `edd6c05` does (prototyped). A test pins the cost.

## v1.9 — the laterality revision (minor)

Theme: a wrong side gets a deterministic guard before 2c's judge, and §7's tables read what
the charting means. The input is #11, the deferred amendments, with Cal's rulings on Oct 20,
2026, posted on #11 under a decision sheet in two parts: part one for entries 29, 25, 26,
27, 28, and 30, probed on `bfc9827`; part two for entry 6, probed on the engine as part
one's rulings leave it. Each option went through the adversarial pass before its ruling,
since six of v1.8's seven reading changes needed a patch after theirs: four of #11's options
as written misread common charting (6, 25, 26, and 27's first half) and were replaced before
the ruling, and the pass filed three entries (30, 31, 32). Adopted: entries 6, 25, 26, 27,
28, 29, and 30. 31 and 32 wait on their triggers or the next minor revision; 2 and 15 keep
theirs; 1, 3, and 5 wait on phase 3 planning, and 12 on phase 4. No option touches the
prompt or the pinned model, so `PROMPT_VERSION` doesn't move (measured) and §14 calls for no
smoke run (L283). #11 closes with this revision. No invariant's wording moves, so CLAUDE.md
is unchanged.

**CRITICAL**
- **L285 §7, §8.8 — a side binds to its site.** Amendment (#11 entry 6, part two's rows 1 to
  3). No extractor read a side (L200), so "Right knee pain after a fall" citing "Left knee
  pain after a fall", verbatim, fired nothing. `extract_laterality` reads site to sides, a
  site being the words after a side, read at each width in `SITE_WORDS` (two words, then
  one), from four signed tables: the side cues (the words and the "-sided" forms), the bare
  letters L, R, LT, and RT, read before a word and not after a number, a side and its site
  in one token (the quadrants, the limbs, the lung lobes), its site spelled out, and the
  phrases where "left" or "right" names no side ("left AMA", "right away"). Sides joined by
  "and" or "or" share the site after them. Bilateral supports left and right, and left with
  right supports bilateral, as the family's text ⊆ span asks. #11 proposed one set of sides
  per text; it passed a swap in a clause naming both sides ("Left knee pain" citing "Right
  knee pain, left knee normal") and fired on "Pt left AMA with right knee pain" against
  "Signed out AMA, right knee pain" (prototyped). The tokenizer keeps "L4", "LAD", and "RA"
  whole, and "2 L NC" and "R/O PE" name no side. Claude Code's review of the first draft
  found an abbreviation's site written short ("RLQ" at "lq"), which no spelled-out charting
  meets, so a swap between the forms in a clause naming both sides passed; spelled out
  ("RLQ" at "lower quadrant"), the four forms measured fire, a quadrant each way, a lobe,
  and a limb (prototyped). Left out, and stated in §8.8: the eye and ear abbreviations (OD
  is also overdose, AS aortic stenosis), "both", and comparisons ("Edema L>R").
- **L286 §4.2, §8.4, §8.6 — `laterality_consistency`, CRITICAL, with its omission row.**
  Amendment (#11 entry 6, rows 1, 4, and 5). The consistency family gains
  `laterality_consistency`: at each `SITE_WORDS` width, the longer first, a claim's sides at
  a site its clause names among those the clause supports there; where they share no site at
  either width, the claim's sides against the clause's. All 30 probe rows read as expected,
  "Right otitis media" against "Acute otitis media, left ear" among them, firing; it fires
  on none of the 136 claims in the three committed records that carry a side in their text
  or clause (prototyped). CRITICAL: wrong-site is a never-event class (L256), and a
  deterministic check keeps invariant 7 by construction. A claim that drops the side names
  none, so the check passes. No live check reads a side, so the omission is a CI-only gap,
  and CI covers it once a label can state a side: `PreserveKind` gains `laterality`, one
  site at one side read at the shorter width, kept where some claim charts that side at that
  site. `PreserveKind` is no part of the tool schema, so `PROMPT_VERSION` doesn't move
  (measured).
- **L287 §8.5 — three injected laterality cases, and no model trap.** Amendment (#11 entry
  6, row 6). A CRITICAL check needs an injected detection trap, an injected control that
  exercises it, an exercise predicate, and an omission row; registered alone, the check
  failed those four tests (prototyped). `detect_laterality_swap` moves the knee pain to the
  other side under a verbatim quote of a clause naming both; `detect_laterality_dropped`
  drops the side, which `must_preserve`'s laterality label catches;
  `control_laterality_kept` keeps both sides and fires nothing. Injected cases are pytest's,
  so `corpus_version` doesn't move and v1.9's before and after keep one corpus; a model trap
  would give that delta a second cause. In the three runs, 73 claims restate a side, and
  none drops, swaps, or adds one.
- **L288 §7 — a refused stop is a continue order, as a rule.** Amendment (#11 entry 25, part
  one's 25B). L172 listed refused stops in `TERMINATORS`, so each phrasing it lacked read
  the stop: at `bfc9827`, "Do not d/c apixaban", "Denies stopping apixaban", "Without
  holding apixaban", and "No need to hold apixaban" read stopped, and "Do not continue
  metformin" read active and continued. L271's guard now runs both ways: a stop cue a
  negation directly precedes, past function words only, is refused and closes the window,
  and the refusal reaches a stop cue joined after it; a refused continue reads stopped. "No
  need to", "no reason to", and "not necessary to" are negation pre-cues; "no break", "no
  pause", and "without interruption" pseudo-negations; "interrupt", "interrupted",
  "interrupting", "holding", and "discontinuing" stop cues, with "holding", "interrupted",
  and "was interrupted" after the drug, so "Holding apixaban for surgery" reads stopped.
  L172's "not stop", "not hold", and "not discontinue" retire as redundant, and the six
  contracted orders with them once L289 reads "don't". #11's option as written read "Don't
  interrupt apixaban" stopped and fixed none of eight other refused or unmade stops
  (prototyped).
- **L289 §7 — a contracted negation, or "never", negates.** Amendment (#11 entry 30). The
  tokenizer splits a contraction at its apostrophe and no negation table held one, so
  "Doesn't have chest pain" read the pain present and "Doesn't have PNA" pneumonia definite,
  a claim of either passing its check (measured on one-claim notes at `bfc9827`). The nine
  contracted negations ("don't", "doesn't", "didn't", "hasn't", "haven't", "hadn't",
  "isn't", "wasn't", "won't") and "never" join `FINDING_NEG_PRE`, and "can't rule out" joins
  `CERTAINTY_CUES` as possible: each contracted row reads as its spelled-out form, that
  form's own misreads included (prototyped).
- **L290 §7, §8.8 — a denied allergy is neither an allergen nor a status.** Amendment (#11
  entry 26, part one's 26C). The post-cue form read the allergen ("No PCN allergy", "PCN
  allergy denied"), and the pre-cue form read a drug stopped ("Not allergic to amoxicillin.
  Start amoxicillin" read active and stopped). A denied allergy, in either form, now reads
  no allergen and no status, and the denial ends the negation's window; the denied-allergy
  pre-cues leave `FINDING_NEG_PRE` for a signed table of their own, and the colon form ("PCN
  allergy: denied") reads the same. A negation pre-cue denies only where no comma separates
  it from the allergy cue: #11's option as written read "No fever, PCN allergy" as no
  allergy at all, deleting a real allergy from both allergy checks, and the suite stayed
  green (prototyped). The cost is loud: "No PCN, sulfa allergies" still reads a sulfa
  allergy, so a faithful "No PCN or sulfa allergies" citing it fires `allergy_preserved`
  (prototyped).
- **L291 §7, §8.8 — an affirmation takes back a negation window's second mention.**
  Amendment (#11 entry 27, part one's 27(i)D). L121's window crosses a comma, so "No fever,
  chills present" read the chills absent (L276). "Present", after the second mention a
  negation's window reads, across a comma and no "and" or "or", takes that mention out of
  the window. #11's option ("present" and "noted", after any mention) read "No fever noted"
  as fever present, the commonest ROS form, with no test failing, and narrower forms flipped
  "No fever, chills, nausea present" (prototyped). "Denies fever and chills, nausea present"
  still reads the nausea absent, and "Not on metformin, lisinopril 10 mg daily", with no
  affirming cue, still reads both stopped: §8.8 keeps L276's cost for both.
- **L292 §7, §8.8 — a repeat keeps its window unless a confirming cue governs it.**
  Amendment (#11 entry 27, part one's 27(ii)A). L278 reread a repeat in a certainty window
  whatever its words, so "r/o PE, PE workup pending" and "r/o PE, PE not confirmed" read
  definite beside rule-out, and outside any window "PE unlikely" read definite: silent
  upgrades. A repeat in a certainty or differential window now keeps the window's reading
  unless a confirming cue governs it ("shows", "showed", "confirms", and "confirmed" before
  it, in `CONFIRMING_CUES`; "confirmed" and "was confirmed" after it, in `CONFIRMING_POST`),
  and "unlikely" and "less likely" join `CERTAINTY_POST` as possible, since no certainty
  sits lower. "PNA vs PE, PE confirmed" reads definite. L278's cost retires; the new one,
  loud, is §8.8's: "r/o PE, hx of PE", "Likely PNA, PNA treated", and "r/o PE, PE on CTA"
  lose their definite.

**WARNING**
- **L293 §7, §8.8 — past its interval, a prn counts across marks and routes only.**
  Amendment (#11 entry 28, part one's 28B). A prn anywhere in a dose's reach joined it
  (L267), so "Tylenol 650 mg q6h, Zofran prn nausea" read the acetaminophen as needed
  (L282). Past its interval, a prn now counts only across marks, commas among them, and
  route words, a signed `DOSE_ROUTES` table (po, iv, im, sq, sc, sl, pr, subq). #11's
  option, directly after the interval across no comma, lost a faithful prn in ten rows; this
  loses it in five ("q6h and prn", "q6h, then prn", "q6h x 3 days then prn", "q6h for pain,
  prn", "q6h, may take prn"), §8.8's cost now. L282's cost retires.

**INFO**
- **L294 §8.7, §11 — the committed records replay in CI.** Amendment (#11 entry 29). §8.7
  states that a run replays free (L203), and no test replayed one; the design room did, by
  hand. A free-tier test replays every committed record: a record whose `checks_version` is
  today's replays to its recorded verdicts and fired checks, and every record replays to a
  committed snapshot, so a change that moves a replayed verdict names it in its diff. Each
  assertion kills a mutation row the other can't (prototyped): the first, a recorded row
  that disagrees with its replay; the second, a checks change that moves a recorded verdict,
  which moves `CHECKS_VERSION` and so leaves the first no record to bind. Its case guard
  recomputes `corpus_version` over a record's own cases, so an added case leaves an old
  record replayable and an edited one refuses.
- **L295 §14 — the 2c gate names v1.9.** Amendment. §14's 2c list names v1.9's entries and
  ledger beside v1.8's (L270); with each revision's re-baseline, L256's gate is met and 2c
  opens.
- **L296 §8.8 — two misreadings the pass found, stated.** Amendment (#11 entries 31 and 32).
  The adversarial pass measured two misreadings no v1.9 option fixes, filed for the next
  minor revision; §8.8 states them meanwhile. A diagnosis naming a test, a workup, or a plan
  reads definite ("PE workup pending."), and an unlisted drug's dose joins the listed drug
  before it ("Lisinopril 10 mg daily, amlodipine 5 mg daily" reads lisinopril 5 mg daily), a
  claim of either passing its check (measured on one-claim notes at `bfc9827`).

## v1.8.7 — v1.8's re-baseline (patch)

Theme: v1.8's live measurement, recorded as v1.7.1 recorded v1.7's (L259, L260). The
re-baseline ran on `8f3d8dd`, v1.8's code complete, and §14 called for no smoke run. With
it, the scope-rule revision meets L256's gate; the laterality revision (v1.9) is next. No
invariant moves; CLAUDE.md is unchanged.

**INFO**
- **L283 §14 — no smoke run for v1.8.** Fill: §14 repeats the smoke run at a change of
  request shape or of the pinned model (L81, L185), and v1.8 changes neither:
  `PROMPT_VERSION` is a99d6d205d0e, as at v1.7's smoke run (L259), and `uv.lock`,
  `config.py`, `orchestrator.py`, and `pyproject.toml` are unchanged since `4877d3d`. 2b's
  close ran none for the same reason (L250).
- **L284 §5.3 — v1.8's re-baseline: all 72 repeats pass.** Measured: one run on `8f3d8dd`,
  `git_dirty` false, `prompt_version` a99d6d205d0e, `checks_version` 9e6fc18db331,
  `corpus_version` 040ccf7c0d67, 72 repeats, each in one validation attempt. Detection
  recall 1.0, control specificity 1.0, model fidelity 1.0, `fidelity_caught` None, pass rate
  1.0, no flaky case; 115,251 input and 15,558 output tokens. The 9 failures of the baseline
  and of v1.7 are gone, and the drafts didn't make it so: the model still splits the plan
  into a second claim with a short quote ("Resume metformin in 48 hours if creatinine is
  stable" citing "resume in 48 hours if creatinine is stable"), and replayed under v1.7's
  checks at `4877d3d`, this run's drafts fail the same 9 repeats on the same three cases,
  each by `drug_in_quote`. The checks moved the number: a claim's span read in its clause
  (L261), where a planned restart sits beside the hold (L262), as v1.7's own drafts already
  replayed at 72 of 72 on v1.8's code. No reference check fired on any repeat. As under
  v1.7, `allergy_contraindication` fired on all 24 detection repeats and on the 3 of
  `control_pcn_allergy_cephalexin`, which pass. `quote_informativeness` (WARNING) fired on
  one repeat of `fidelity_no_htn_urgency`, whose claim "Asymptomatic" quoted the one word,
  as on all three at the baseline and none under v1.7. 11 of the 24 cases gave one draft
  across their repeats (8 at the baseline, 14 under v1.7), and no case changed verdict
  across its repeats.

## v1.8.6 — a prn alone, and a prn's reach (patch)

Theme: L267, built, with what it left open. Its comparison never said whether a prn alone
charts a frequency, and its reach, now running past the interval, takes in a later order's
prn. Cal approved both fills and re-signed `DOSE_FREQUENCIES`' prn rationale on Oct 20,
before the code that depends on them, which lands with them in one commit. The five tests
that pinned prn in the frequency slot are rewritten, as L267 said. Both records replay as at
v1.8.5, 72 of 72 (prototyped). The smoke run and the re-baseline become v1.8.7, not v1.8.5's
v1.8.6.

**WARNING**
- **L281 §7, §8.4 — a prn alone charts a frequency.** Fill. L267 matches a dose charting no
  frequency at any (L141) and one charting a frequency only at its prn, and leaves open
  which a prn alone is. Read as no frequency, "Acetaminophen 650 mg prn" against
  "acetaminophen 650 mg q6h" passes, a schedule charted as needed: the added prn L267 exists
  to catch (prototyped). A dose charting no interval and no prn matches any; one charting
  either matches at its interval, if any, and at its prn, so that claim fires, and "650 mg
  prn" against "650 mg q6h prn" still passes, L267's own row. A `must_preserve` dose label
  is kept as `dose_consistency` matches one (§8.4), so a note dropping or adding a label's
  prn now misses it, and one charting the prn alone keeps it (measured). §7's dose paragraph
  says "the first interval", not "the first frequency", since a prn is no interval.
- **L282 §8.8 — a prn's reach.** Fill: §8.8 states it. L267's reach runs to the next dose,
  drug, or terminator, past the interval where a dose once settled (L133), so "Tylenol 650
  mg q6h scheduled, oxycodone prn breakthrough" reads the acetaminophen as needed, since
  oxycodone is no listed drug. A faithful "Tylenol 650 mg q6h" citing it fires
  `dose_consistency`, and one adding the prn passes it (measured). Ending the reach at the
  interval's neighbor would be a decision, for the deferred-amendments issue.

## v1.8.5 — an indication's list (patch)

Theme: L266, built, read past the decision sheet's rows. Built as written, an indication ran
to a terminator, the clause's end, or a comma no finding follows, so after an indication
that names no finding it took in the next statement's finding: the chest pain in "Apixaban
for afib, chest pain this morning" went unread. Cal approved the resolution and signed
`INDICATION_CUES` on Oct 20, before the code that depends on them, which lands with them in
one commit. Both records replay as at v1.8.4, 72 of 72 (prototyped). The smoke run and the
re-baseline become v1.8.6, not v1.8.4's v1.8.5.

**CRITICAL**
- **L280 §7, §8.8 — an indication is the list right after its cue.** Conflict: L266 defines
  an indication as why the drug is given, and ends it at a terminator, the clause's end, or
  a comma no finding follows; past a word that names no finding, that end takes in findings
  that aren't why the drug is given. The definition wins: the indication is the list right
  after the cue, its findings, joins, and marks, as a run reaches (L193), and any other word
  or a terminator ends it. Why: built as written (prototyped at `2a5d99b`), "Apixaban for
  afib, chest pain this morning", "On amoxicillin for strep throat, fever persists", "On
  lisinopril for years, chest pain since this morning", and "Metformin 500 mg bid for
  diabetes, nausea with it" read no finding, so "Denies chest pain" citing the first passed
  `negation_consistency`, which fires CRITICAL on it at `2a5d99b` (measured). Built as
  written, "Tylenol for fever, chills, and nausea" read the nausea present, since the comma
  before "and" ended the indication; the list reads none of the three. The cue is a signed
  table, `INDICATION_CUES`, holding "for" (invariant 10). The cost is §8.8's: a list that
  opens on any other word reads as before L266 ("Tylenol for the pain and fever", "Ibuprofen
  for knee pain"), and L266's own comma cost stands.

## v1.8.4 — a repeat in a certainty window (patch)

Theme: L265, built, read past what the decision sheet measured. Built as written, for every
cue class, it read a repeat in a negated or held list as ungoverned, and everyday charting
lost its negation. Cal approved the resolution and the fill on Oct 20 before the code that
depends on them, which lands with them in one commit; `_allergy_lists` drops the `pre`
parameter it never read, parked from v1.8.3's review. Both records replay as at v1.8.3, 72
of 72 (prototyped). The smoke run and the re-baseline become v1.8.5, not v1.8.3's v1.8.4.

**CRITICAL**
- **L278 §7, §8.8 — a repeat reads at its own cues in a certainty window only.** Conflict:
  L121 has a pre-cue govern every mention that starts in its window, and L265 has a mention
  of an entity an open pre-cue already governs read at its own cues, in every cue class.
  L121 wins, except in a certainty pre-cue's window. Why: under L265's wording a list's
  repeated entity left its window (each prototyped at `6541087`). "Denies abdominal pain,
  back pain, or joint pain" read pain present, since "pain" is one entity, and "Denies
  chest pain at rest or chest pain with exertion" read chest pain present, so "Reports
  chest pain with exertion" citing it passed `negation_consistency`; "Hold Eliquis
  (apixaban) 48 hours before the procedure" read apixaban active, so "Apixaban 5 mg bid"
  passed `med_status_consistency`. Each fires CRITICAL at `6541087`. In a certainty window
  the repeat still reads at its own cues, so entry 16's rows read both certainties: "r/o
  PE, PE confirmed", "r/o PE, then CTA shows PE", and "r/o pneumonia, pneumonia on CXR".
  A differential's window keeps its repeat too: let into the rule, it read "pneumonia vs
  PE, PE less likely" as definite PE (prototyped). L265's "Denies fever, chills, fever last
  week" now reads the fever absent alone. The cost the certainty window keeps is §8.8's: a
  repeat reads at its own cues whatever its words, so "r/o PE, CTA PE protocol ordered" and
  "r/o PE, PE less likely" read pulmonary embolism definite, and an upgraded "Pulmonary
  embolism" citing either passes `diagnosis_in_quote`, which fires on it at `6541087`
  (measured). Telling a workup's answer from another mention needs a confirming cue, a
  decision, so it goes to the deferred-amendments issue; a test pins the cost.
- **L279 §7 — a restated name is the mention it restates.** Fill. L265 doesn't say whether
  a second name for one mention is a repeat. Read as one, "r/o pulmonary embolism (PE)" and
  "r/o PE/pulmonary embolism" read pulmonary embolism definite beside rule-out, so an
  upgraded claim citing either passes `diagnosis_in_quote`, from charting that states a
  rule-out alone (prototyped). A name directly after a mention of the same entity, across
  any mark but a comma (L122), is that mention again and reads in its window: both read
  rule-out alone.

## v1.8.3 — an allergy list's bounds (patch)

Theme: L264, built, with its bounds. Building entry 7 showed L264 never says where a list
after a dash ends or what it may hold, and the first reading of it, any drug after the cue,
read "PCN allergy - amoxicillin 500 mg tid" as an allergy and hid a planned drug from
`allergy_contraindication`. Cal approved the fill on Oct 19 before the code that depends on
it, which lands with it in one commit; the three items parked from v1.8.2's review ride
along in `extract.py` and its tests. Both records replay as at v1.8.2, 72 of 72
(prototyped). The smoke run and the re-baseline become v1.8.4, not v1.8.2's v1.8.3.

**CRITICAL**
- **L277 §7 — an allergy list holds mentions and joins alone.** Fill. L264 has an allergy
  post-cue govern "a list right after it" when the list names a drug, without saying where
  the list ends or what else it may hold. Read as any drug after the cue, "PCN allergy -
  amoxicillin 500 mg tid" made amoxicillin an allergen, so `allergy_contraindication` stayed
  silent on a penicillin-allergic patient given amoxicillin (prototyped). After a dash or in
  parentheses the list now runs to its clause's end or its closing parenthesis and holds
  mentions and joins alone; a reaction, a dose, or any other word leaves every mention as it
  reads, so that line reads amoxicillin active and the check fires, while "PCN allergy -
  amoxicillin" and "PCN allergy (amoxicillin, cephalexin)" read allergens. In the colon form
  the cue is the pre-cue "allergy:". Before its colon it reads as the post-cue it ends with,
  in the scope engine: it governs the mention directly before it and each mention of the
  list it ends that no other cue governs (L122, L128), so "PCN/sulfa allergies: rash" reads
  both and "Start amoxicillin, PCN allergy: rash" leaves the amoxicillin started; a review
  build that walked back on its own read that amoxicillin an allergen and stopped at "/"
  (measured, found in review). A review build limited it to a clause-opening mention to
  spare a drug a header ran on after ("Takes metformin Allergies: PCN"), but that lost the
  penicillin of "Pt has PCN allergy: amoxicillin" and of "Hx of PCN allergy: anaphylaxis"
  and the list of "PCN and sulfa allergies: rash" (measured), while the post-cue alone has
  always read "Takes metformin allergies" that way; a test pins the cost. Its own window
  reads on after the colon as L128 has it, so "PCN allergy: amoxicillin 500 mg tid" still
  reads amoxicillin an allergen (measured); §7 states both.

## v1.8.2 — the clause's bounds and its cost (patch)

Theme: L261, built. Reading a span in its clause needs the clause's bounds in raw offsets,
which only extraction can compute, and the adversarial pass for it found a false CRITICAL
the clause brings back. Cal approved both fills on Oct 19 before the code that depends on
them, which lands with them in one commit. With this commit both records replay at 72 of 72,
only their nine failing rows moving and no other check changing, WARNING-level included
(prototyped). The smoke run and the re-baseline become v1.8.3, not v1.8.1's v1.8.2.

**WARNING**
- **L276 §8.8 — a window that crosses a comma.** Fill. A pre-cue's window runs across a
  comma (L121), so "Not on metformin, lisinopril 10 mg daily" reads the lisinopril stopped
  and "No fever, chills present" reads the chills absent (measured at `926c555`). A quote
  cut short of the cue used to hide that reach; reading the clause (L261) brings it back, so
  a faithful "Lisinopril 10 mg daily" citing "lisinopril 10 mg daily" there fires
  `med_status_consistency`, and "Chills" citing "chills present" fires
  `negation_consistency` (prototyped). Neither phrasing is in a case or a record draft. The
  window isn't cut at a comma, since that would unread "no fever, chills, or sweats"; §8.8
  states the cost, and a fix that closes the window at an affirmation would be a decision,
  for the deferred-amendments issue.

**INFO**
- **L275 §7, §8.4 — the clause's bounds live in extraction.** Fill. L261 has the consistency
  family read `clause_text`, the span widened as L193 opens a clause, but L193's clause is
  read over extraction's tokens, which `evals/` doesn't see, and `clause_text` takes a
  `ClinicalClaim`, which `clinical/` can't import (invariant 13).
  `clause_bounds(text, start, end)` in `extract.py` returns the clause's offsets in the raw
  text: a decimal's point opens no clause, a header's colon does and an entity's doesn't, a
  carriage return is a line break, and the span is never cut. §7's API block lists it, and
  §7's helper paragraph counts three helpers, which it had counted as two since v1.8.

## v1.8.1 — L262's reach, made exact (patch)

Theme: entry 11's rules, built, read past what the decision sheet measured. Building L262
ran adversarial rows the sheet hadn't, and two of its statements conflicted with older ones;
a third gap blocked the corpus from loading, and a fourth left a cue's class to code. Cal
approved all four resolutions on Oct 19 before the code that depends on them, which lands
with them in one commit, as patches do. Both records replay unmoved at this commit, since
the plan claims still quote no drug until L261 reads the clause. The smoke run and the
re-baseline follow v1.8's remaining code, as v1.8.2.

**CRITICAL**
- **L271 §7, §8.8 — a negation refuses a start only directly before it.** Conflict: L124 has
  a new pre-cue of any class replace an open window, and L262 made a start a negation's
  window reaches a stop. L124 wins, except where the negation directly precedes the start
  cue across function words only, the shape L167's spelled refusals take. Why: under L262's
  wording, a finding's negation reached across a comma to the drug, and ordinary charting
  read stopped: "No fever or chills, start amoxicillin 500 mg tid", "Not hypotensive,
  restart lisinopril", "Negative for cough, started lisinopril", and "No rash after starting
  amoxicillin" (each prototyped at `3a381b6`), each a false `med_status_consistency` on a
  faithful start and a pass on "Hold". The narrowed rule reads all four active and still
  refuses "Not starting metformin", "Not restarting lisinopril", and "Will not be starting
  metformin". The cost, "No plan to start metformin" reading active as it did before v1.8,
  is §8.8's.
- **L272 §8.4 — a continued label is one reading.** Fill. L214 has a label state one
  reading, and L262 made "continue apixaban" read active and continued, so
  `fidelity_apixaban_continued`'s label no longer read, and the corpus didn't load
  (prototyped). A medication label's continued stands for the active it implies, so it reads
  continued; a note keeps it with a reading of continued, or of active with no stop, as
  `med_status_consistency` lets a span support one, and a `must_not_add` medication label
  may read continued. "Hold Eliquis" misses a continued label, CRITICAL, and "Eliquis 5 mg
  bid" keeps it.
- **L273 §7, §8.8 — a continue cue directly after a drug is that drug's.** Conflict: L262
  has a continue cue govern the drug in its window first, and L122 has a cue directly after
  a mention govern that mention, the reading every post-cue takes. L122 wins: across any
  mark but a comma, a continue cue directly after a drug governs it, and otherwise L262's
  window and clause-end readings stand. Why: under L262's order, "Lisinopril continued,
  metformin held, resume in 48 hours" read metformin continued as well as stopped, and
  lisinopril without its continue (prototyped). §8.8's "apixaban continued, then held" now
  reads apixaban continued, the hold still unread.

**INFO**
- **L274 §7 — the restarts that reach back are a signed table.** Fill. L262 names "a restart
  or resumption cue" without saying where the class lives, and the first build picked those
  cues by stem in `extract.py`, so code, not a signed table, decided a cue's class, against
  invariant 10 (found in review). `MED_RESTART_CUES` holds the eight restart and resumption
  forms, each a start cue (L169); one that is also a start post-cue ("restarted", "was
  resumed") reads as done. The reading is unchanged (prototyped), and a test holds every
  restart cue to a start cue and every continue cue to a terminator.

## v1.8 — the scope-rule revision (minor)

Theme: the checks read the clause, and the prompt stays put. The input is #10, the deferred
amendments, with Cal's rulings on Oct 17, 2026, posted on #10 as the decision sheet and
amended the same day for entry 11, after rows the sheet hadn't measured showed its reach
misreading a negated finding as a stop. A live probe of three prompt wordings left v1.7's
split in place (L268). Reading each span in its clause, with a restart's reach and the "no
interruption" pseudo-negation, passes every probe draft and both records' 144 repeats with
the prompt unchanged, so `PROMPT_VERSION` doesn't move and the re-baseline confirms a
replay. Adopted: entries 10, 11, 24, 7, 16, 22, 9, and 23, which needs no prompt change.
Rejected: 13, with a test in its place. Laterality (entry 6) is v1.9, before any 2c step
(L256); 2 and 15 keep their triggers; 1, 3, and 5 wait on phase 3 planning, and 12 on
phase 4. #10 closes with this revision. Invariant 14's wording moves; its title doesn't, so
CLAUDE.md is unchanged.

**CRITICAL**
- **L261 §6.4, §7, §8.4, §8.8, invariant 14 — the consistency family reads the span in its
  clause.** Amendment (#10 entry 10). The family read `raw_text[source_span]` alone (L35),
  so a cue the quote cut off didn't exist for it: "Continue metformin" citing "metformin" in
  "Hold metformin.", "Fever" citing "fever" in "Denies fever.", and "PE" citing "PE" in "r/o
  PE." or "PE ruled out." fired only `quote_informativeness`, a WARNING, and "Reports chest
  pain" citing "chest pain" in "Denies chest pain." fired nothing (measured at `5fb422d`).
  `drug_in_quote`, `med_status_consistency`, `negation_consistency`, `diagnosis_in_quote`,
  and `dose_consistency` now read `clause_text`, the span widened to its clause as L193
  opens one; each of those fires at CRITICAL (prototyped), and "Denies chest pain at rest,
  reports chest pain on exertion" still passes a claim keeping either. The entry's
  "terminator to terminator" would cut at "continue" and "but", which are terminators, so
  the clause is L193's. `quote_informativeness` keeps the span, since D15 measures the
  quote; reading the clause broke `detect_degenerate_quote` (prototyped).
  `detect_added_medication` gains `med_status_consistency`, L157's trap now caught live.
  The cost, a quote borrowing its drug from its clause, is §8.8's; highlighting the clause
  is a patch on #3.
- **L262 §7, §8.4, §8.8, D13 — a restart reaches back, and a continue is a status.**
  Amendment (#10 entry 11, as amended on #10). A mention took one label, so "Apixaban held,
  then restarted" read stopped, and "Metformin held, resume in 48 hours" read the hold
  alone. Three readings were prototyped. The last cue winning, #10's option, fired on the
  status claims the model writes correctly and left `fidelity_metformin_held` unloadable,
  its label no longer the raw text's reading. Every cue adding its status let the case's
  trap, "Continue metformin", pass. The sheet's third reading let any cue governing no
  mention reach back, which read "Lisinopril 10 mg daily, no cough" as stopped, a false
  CRITICAL on "Continue lisinopril", and 7 of 23 rows went wrong. As ruled: only a restart
  or resumption cue reaches back, to the stopped drug before it in its clause; done
  ("restarted", "resumed"), it replaces the stop, and planned ("resume"), it adds active
  beside it. A negation before a start cue in its window negates it ("Not starting
  metformin"). `MedStatus` gains "continued", asserted by `MED_CONTINUE_CUES` for the drug
  in the cue's window or the one before a cue that ends its clause; a "continued" claim
  fires against a stop in its span, and a span reading active with no stop supports one.
  `new_prescriptions` reads only start cues that govern a mention: a planned restart is no
  start at this visit. With L261 and L263, 23 of 23 rows read right, entry 11's own example
  among them (prototyped). The cue entries are drafted with their code, each with Cal's
  sign-off (L120).
- **L263 §7 — "no interruption" is a pseudo-negation.** Amendment (#10 entry 24). "No" read
  as negating the next drug in its window, so "No interruption of Eliquis needed" read
  apixaban stopped (measured). Once L261 reads that claim's span in its clause, "Continue
  Eliquis, no interruption needed.", the claim reads stopped and the clause active, and
  `med_status_consistency` fires on a faithful claim (prototyped). `PSEUDO_NEGATIONS` gains
  the phrase, its siblings drafted with it.
- **L264 §7, §8.8 — an allergy post-cue governs the list right after it.** Amendment (#10
  entry 7). "PCN allergy (amoxicillin)" and "PCN allergy - amoxicillin" read amoxicillin
  active, a false `allergy_contraindication`, and "PCN allergy: amoxicillin" lost the
  penicillin (measured). A list in parentheses, after a dash, or after the cue's colon that
  names a drug now reads as allergens beside the cue's own; a list naming no drug is a
  reaction ("PCN allergy (hives)"), as every one in the corpus is, and reads as before.
  §8.8's bullet (L154) goes.
- **L265 §7 — a repeated mention reads at its own cues.** Amendment (#10 entry 16). A
  certainty pre-cue's window ran past a comma, so "r/o PE, PE confirmed" read rule-out
  alone. A mention of an entity an open pre-cue already governs now reads at its own cues,
  so both certainties read, as with a period (prototyped). Cal's ruling makes it the scope
  engine's rule for every cue class, not a diagnosis switch, so "Denies fever, chills, fever
  last week" reads the repeated fever at its own cue, present.
- **L266 §7, §8.8 — an indication isn't a finding.** Amendment (#10 entry 22). "Denies
  fever. Acetaminophen as needed for pain and fever." read fever absent and present
  (measured). "for" after a drug in its clause now opens an indication, which runs to a
  terminator, the clause's end, or a comma no finding follows, and no finding inside it is
  read; "Seen for chest pain" names no drug and reads as before. The cost, a finding after a
  comma joining the indication, is §8.8's.

**WARNING**
- **L267 §7, §8.4 — `Dose` carries prn beside its interval.** Amendment (#10 entry 9).
  "650 mg q6h prn" and "650 mg q6h" read the same `Dose`, since a prn yielded to an interval
  (L133), so a claim dropping or adding the prn passed `dose_consistency`, and "650 mg prn"
  against "650 mg q6h prn" fired, a false positive (measured). `Dose` gains `prn: bool` and
  `freq` holds only the interval; a claim charting no frequency still matches any (L141),
  and one charting a frequency matches only at its prn. Five tests pinning prn in the
  frequency slot are rewritten.
- **L268 §5.3 — the prompt stays; the split is read, not prevented.** Entry 23 resolved
  without a prompt amendment. Probed live on Oct 17, 27 calls on the three failing cases,
  three repeats each: A, a status-and-plan example in the one-fact rule, passed 3 of 9; B,
  dropping "Prefer the shortest span", 0 of 9; both, 3 of 9; v1.7's own drafts, 0 of 9
  (today's checks). The metformin case still quoted its plan as "resume in 48 hours if
  creatinine is stable" in 12 of 12 draws. Under L261, L262, and L263 every arm passes 9 of
  9, the control included, and both records replay at 72 of 72, with only their 9 failing
  rows moving and no WARNING-level change. A and B are rejected; L252's rule stays, since
  the whole-clause status claims it produces read right under L261.

**INFO**
- **L269 §7 — a cue's own colon.** #10 entry 13 rejected, with a test in its place.
  Opening a clause after "allergies:" changes nothing on the entry's example: "Allergies:
  PCN, sulfa denied" reads penicillin alone before and after (prototyped), since the cue
  governs penicillin and L193's post-cue reaches only ungoverned mentions. "Meds:
  lisinopril, metformin held" stops both because "Meds" is no cue. In an allergy list,
  "sulfa denied" is most plausibly a denied sulfa allergy, today's reading, which a test
  now pins.
- **L270 §14 — the 2c gate names v1.8's entries.** §14's opening 2c line listed the
  scope-rule revision's entries as L256 deferred them; it now names v1.8's (#10 entries 7,
  9, 10, 11, 16, 22, 23, and 24, with 13 rejected), and laterality stays next.

## v1.7.1 — v1.7's smoke run and re-baseline (patch)

Theme: v1.7's live measurements, recorded as v1.4.1 recorded v1.4's (L197–L199). Both ran on
`4877d3d`, v1.7's code complete. The smoke run and the re-baseline agree: the one-claim rule
(L252) is half kept, and the baseline's 9 failures stand. Recorded, not fixed (§14); the fix
goes to #10 for the next revision. No invariant moves; CLAUDE.md is unchanged.

**WARNING**
- **L260 §5.3 — v1.7's re-baseline: the one-claim rule is half kept.** Measured: one run on
  `4877d3d`, `git_dirty` false, `prompt_version` a99d6d205d0e, `checks_version`
  52f147266aef, `corpus_version` 040ccf7c0d67, 72 repeats. Detection recall 1.0, control
  specificity 0.875, model fidelity 0.75, `fidelity_caught` None, pass rate 0.875, no flaky
  case: the baseline's, as rescored under L253. The same 9 repeats fail, on the same three
  cases, each by `drug_in_quote`, and no reference check fired on any repeat of either run.
  The drafts show the rule half kept: the status claim now cites its whole sentence
  ("Metformin held" from "Metformin held, resume in 48 hours if creatinine is stable"), and
  a second claim still carries the plan with a short quote ("Resume metformin in 48 hours if
  creatinine is stable" from "resume in 48 hours if creatinine is stable"). 14 of the 24
  cases gave one draft across their repeats, against 8 at the baseline. §5.3 says so. The
  likelier conflict is §5.3's "One clinical fact per claim" and its splitting example, more
  than "Prefer the shortest span"; the next revision decides it, with a few live calls on
  the failing cases before any wording lands (#10). One other change, below any verdict: at
  the baseline `quote_informativeness` (WARNING) fired on all three repeats of
  `fidelity_no_htn_urgency`, whose claim "Asymptomatic" quoted the one word "asymptomatic";
  under v1.7 it fired on none, the claim citing "asymptomatic, denies chest pain". Longer
  quotes, consistent with the new bullet.

**INFO**
- **L259 §14 — v1.7's smoke run.** Fill: §14 runs one at a change of request shape (L81),
  and v1.7's prompt is one. Preflight on `4877d3d`: `settings.model` is `claude-haiku-5-5`,
  matching the pin (L199); `PROMPT_VERSION` is a99d6d205d0e and the SDK 1.9.0;
  `models.retrieve` reports `max_tokens` 128,000, matching `model_max_output_tokens` (L85).
  One synthetic encounter through `GET /`, outside the model corpus: `validation_attempts`
  1, 1,648 input and 291 output tokens, 1.71 s end to end. The finding: the model split
  "Lisinopril held for low blood pressure, restart 5 mg once SBP is above 120." into two
  claims, the second citing "restart 5 mg once SBP is above 120", and `drug_in_quote` fired
  at CRITICAL, the failure L252 aims at. A 291-token reply's time is mostly fixed latency,
  so it measures no throughput; L198's bound stands.

## v1.7 — what the baseline taught (minor)

Theme: what 2b's baseline taught, decided before any 2c step. The input is #9, the deferred
amendments, with the readings of 2b's baseline (`5825630`) and Cal's rulings on Oct 17,
2026, posted on #9 as the decision sheet; entry 20's ruling moved from Option A to the
one-claim rule after a replay of the baseline's drafts showed A alone moves its failures to
another check. Adopted: entries 20, 21, 18, and 4. Rejected: 19, and 8's freeze, with a test
in its place. Deferred, each with its deadline, to the next deferred-amendments issue: the
scope-rule entries 7, 9, 11, 13, and 16, and #6's undrafted indication entry, as entry 22,
before any 2c step; the laterality entry 6 after them, before any 2c step (L256); 2, 10, and
15 on a named trigger; 1, 3, 5, and 12 at their phase. #9 and #6 close with this revision.
#6's indication entry should have been ruled on at 2b's close (§14 audits against the
patched spec) and wasn't; it is ruled here. No invariant moves; CLAUDE.md is unchanged.

**WARNING**
- **L252 §5.3 — a medication's status and its plan are one claim.** Amendment (#9 entry 20).
  2b's baseline failed 9 of its 72 repeats on one pattern, and no reference check fired on
  any of them: the model split a sentence such as "Metformin held for CT with contrast
  today, resume in 48 hours" into two claims and wrote "Resume metformin in 48 hours" citing
  "resume in 48 hours", so `drug_in_quote` fired at CRITICAL on a correct claim. Measured by
  replaying the baseline's drafts on 9f011d6: widening each such quote to name its drug
  (#9's Option A) leaves 9 failures, now `med_status_consistency`, since the clause reads
  the hold and the claim the restart; keeping each such sentence as one claim, quoted whole,
  passes all 72. Six of seven paraphrases of the merged claims stay clean; the seventh leads
  with the planned restart and fires `med_status_consistency`, so the rule keeps the status
  first, as written. §5.3's prompt gains a bullet stating the one-claim rule with an example
  outside the model corpus (warfarin, surgery; injected cases never reach the model), and
  keeps A's sentence: a quote names every medication its claim names. Two tests: the
  bullet's content, and that no model case's raw text appears in the prompt, so the
  re-baseline measures the rule rather than memorized cases. `PROMPT_VERSION` moves, so a
  smoke run and a re-baseline follow.
- **L253 §4.2, §8.7 — `fidelity_caught` counts the model's labeled errors.** Amendment (#9
  entry 21). v1.6's denominator was every fidelity repeat that failed without a pipeline
  error, so the baseline's 6 failures, `drug_in_quote` firing on correct claims, scored 1.0
  as catches. The denominator is now the fidelity repeats where a reference check
  (`must_preserve`, `must_not_add`) fired at CRITICAL, so the model lost or added a labeled
  fact; the numerator, those where a live check fired at CRITICAL too, as L206 and L224 read
  it. §2's sentence asks exactly this: when the model drops something, does production see
  it. A failure no reference check explains is no catch; the README reads its drafts. §2's
  note on X says so. No schema field changes, so earlier records still parse and rescore
  from their rows. The baseline rescores to `None`: the model lost no labeled fact.

**INFO**
- **L254 §4.2, §8.7, D11 — `flaky_cases` reads repeats without a pipeline error.** Amendment
  (#9 entry 18). D11 asks whether replies vary; a repeat that failed on an upstream error
  answers another question, and gets likelier as `corpus_concurrency` rises (L202). A case's
  pass fraction for flakiness is now over its applicable repeats without an `error`; errored
  repeats stay failed in the rates (invariant 12), and the README reports them beside
  `flaky_cases`. The baseline had none, so its `flaky_cases` is unchanged. It changes
  `corpus_metrics` with L253, so `checks_version` moves once.
- **L255 §9.4 — 408 and 409 are an intermediary's.** Amendment (#9 entry 4). The SDK retries
  408 and 409 as transient, so when its retries run out they reached the 4xx row as 500
  `internal_error` at ERROR, but L71's 4xx is our schema, key, access, model id, or size,
  and neither is. They map to 502 `upstream_error` at WARNING, beside the other upstream
  failures; `upstream_busy` stays capacity-only (429, 529). §9.4's table and its prose
  bullet (L71, L99) both say so, and the bullet's test list gains a 408 and a 409.
- **L256 §14 — 2c opens after the scope and laterality revisions.** Amendment: §14's 2c list
  gains an opening line, as 2b's opened with v1.4 (L194): the scope-rule revision (deferred
  entries 7, 9, 11, 13, 16, and #6's indication entry, which the successor issue carries as
  entry 22), then the laterality revision (entry 6), each with its re-baseline, land before
  any 2c step. Laterality has been deferred twice, and wrong-site is a never-event class, so
  it gets a deadline in the build sequence, not only on an issue.
- **L257 §11 — the suite leaves the lexicon tables as it found them.** #9 entry 8 rejected,
  with a test in its place. Freezing the tables costs a reformat of 320 signed lines and an
  import against §7's "imports NOTHING" (measured at v1.4 drafting), and no test writes to
  one: measured on 9f011d6, all 28 tables, 14 sets and 14 dicts, hash the same before and
  after the full suite of 1420 tests. A session-scoped fixture hashes each module-level
  table in `lexicons.py` before the first test and checks it after the last, which catches
  the harm the freeze guards against.
- **L258 §8.7 — a run before its predecessor's record is committed reads dirty.** #9 entry
  19 rejected. `git_is_dirty` counts the appended record, so a second run on a clean HEAD
  with the first record uncommitted reads `git_dirty=True` (measured). The error is safe (a
  clean run reads dirty, never the reverse), and D5's discipline prevents it: 2b committed
  its record (`5825630`) before any further run. Excluding `runs_path` costs a branch for an
  absolute path outside the repo, where git's exclude pathspec is fatal. §8.7 states it.

## v1.6.11 — the 2b close (patch)

Theme: phase 2b closes. Its exit criteria were audited line by line against main at 5825630,
each against the code, the tests, or the record that holds it. CLAUDE.md's "Current phase"
line moves to 2c, and #9's entries 20 and 21 wait for the next minor revision, with their
re-baseline.

**INFO**
- **L250 §14 — the 2b close runs no smoke run.** Fill: §14 repeats the smoke run at a phase
  close that changes the request shape, and at a change of the pinned model (L185); 2b's
  close does neither. Measured at 5825630: no commit since the v1.4 smoke run (44bc4bb)
  touches `orchestrator.py` or the tool-schema snapshot, `PROMPT_VERSION` is f568c08861a1
  and the SDK 1.9.0 at both, and the model is `claude-haiku-5-5` (L180). The baseline's 72
  calls ran on that shape too (5825630's record).
- **L251 §14 — the 2b checklist cites its command's fills.** Fill: the line naming
  `python -m backend.corpus` cited only L210 and L211; it now cites the dry run (L240), the
  spend's usage line (L242), and the command's tests (L241). Found in step 5c's review,
  parked until 2b's close.

## v1.6.10 — the first model corpus (patch)

Theme: 2b's step 6 lands the first model corpus, 24 cases signed off by Calvin Patel, with
the free tests that check its answer keys before any run pays for them. Drafting it against
the checks found a model detection trap that couldn't fail and a naming conflict in the
fixture table. No invariant moves; CLAUDE.md is unchanged.

**WARNING**
- **L244 §8.5 — a model allergy trap labels both halves of its danger.** Fill: §8.5 asks
  every `origin="source"` check for a model detection trap, to ask whether a real model
  keeps the danger visible, and the trap couldn't ask it. `allergy_contraindication` reads
  allergies and new orders from the raw text (D17, L51), so it fires on any note. Measured
  on 7ea37c2 with `detect_ampicillin_allergy_keflex` unlabeled: a note that drops the Keflex
  order still fires it, and the trap passes. Each model trap expecting it now labels its
  allergy and its order for `must_preserve`; measured on all eight, a faithful note passes
  and a note hiding either half fails. A test holds the pair.
- **L245 §8.5 — a fidelity trap keeps a fact whose loss is CRITICAL.** Fill: a fidelity trap
  passes when nothing CRITICAL fires, and a dropped dose, NKDA, or NKA label, or a labeled
  downgrade, fires at WARNING (L217), so a trap labeling only those could never fail. Each
  fidelity trap labels an allergy, a medication, a finding, or a diagnosis to keep, and a
  test holds it. Measured on all eight: dropping the labeled fact fires `must_preserve` at
  CRITICAL, and most of the mistakes the traps invite are caught live as well: a dropped
  allergy by `allergy_preserved`, a flipped status by `med_status_consistency`, a flipped
  negative by `negation_consistency`, and an upgraded or invented diagnosis by
  `diagnosis_in_quote`.
- **L246 §11 — the model corpus's answer keys are tested free.** Fill: a model case has no
  draft, so its answer key was first exercised on a paid run, where a key no note can pass
  reads as the model failing. A test builds a faithful note, each sentence of the raw text a
  claim quoting itself, and requires every model case's verdict to be `passed`. Every claim
  is S: on this corpus the verdicts match those of the same note with its sections guessed
  sentence by sentence (measured), so the test guesses none.

**INFO**
- **L247 §8.5, §14 — a model twin takes its injected case's id plus `_model`.** Conflict:
  §8.5's fixture table listed `control_pcn_allergy_azithro`, `detect_same_drug_allergy`, and
  `control_hedged_assessment` as "model + injected", and §14 named the first and third as
  model cases, but an id is its file name (L119), so one id can't be both. The model twins
  are `control_pcn_allergy_azithro_model`, `detect_same_drug_allergy_model`,
  `control_hedged_assessment_model`, and `control_continue_and_hold_model`; each keeps its
  injected case's raw text, and a test holds it.
- **L248 §8.5, §11 — the model clause and the corpus's size are tested.** Fill: L137 left
  the model clause to join the coverage test with the first model case; it does, for each
  `origin="source"` check, with a test that one is registered. §8.5's size, ≥ 24 model cases
  and ≥ 6 per species, gains a test too, so the scorecard's n can't shrink unnoticed.
- **L249 §8.5 — the first model corpus.** 24 model cases, 8 per species, each signed off
  clinically by Calvin Patel (2026-10-16). Every drug and allergy it names is already in the
  lexicons, so no entry joins (L171). One trap labels a GI bleed charted under "Allergies:
  NSAIDs" as an NSAID allergy: a GI bleed is an adverse reaction, not an allergy, but a
  strong adverse reaction is treated at an allergy's level and the drug avoided, the
  conservative reading (Calvin Patel). `control_pcn_allergy_cephalexin` fires
  `allergy_contraindication` at WARNING only, an unspecified penicillin allergy against
  cephalexin (D9, D14), so the control passes.

## v1.6.9 — the dry run proves a corpus run before it spends (patch)

Theme: 2b's step 5c gives the corpus run its command, `python -m backend.corpus`. L210 said
what the dry run prints and not what it proves; a dry run that only prints can't predict a
spend that refuses. No invariant moves; CLAUDE.md is unchanged.

**WARNING**
- **L240 §8.7 — the dry run proves the run before the spend.** Fill: L210 had it print the
  planned calls and exit, so with no model case it would print 0 calls and exit 0 while
  `--spend` raised. It now runs `plan_run`, the function `score_corpus` runs before its
  first call, and prints the model and injected case counts, n × k and the ceiling with
  validation retries, the lineage the record would carry (`git_sha`, `git_dirty`, `model`,
  `prompt_version`, `corpus_version`, `checks_version`), and `runs_path`. It builds no
  client. A refusal raises: measured on e6e27c8's cases, all injected, both
  `python -m backend.corpus` and its `--spend` exit 1 on `ValueError: no model cases`, with
  no runs directory made and the tree clean; an unknown flag exits 2. The command imports
  only from the repo root, since the project isn't installed as a package (measured:
  `import backend.corpus` from `tests/` fails), so the relative `runs_path` (L232) and the
  git reads resolve against the checkout.
- **L241 §11 — the command's tests.** Fill: L211 named only the scorer's. Over case files
  under `tmp_path`, with both git reads stubbed: the dry run prints its plan with
  `get_client` and `score_corpus` stubbed to fail, its counts and ceiling read from
  non-default settings; both paths refuse a run with no model case before any call;
  `--spend` appends one record and prints its metrics, usage, and path, and the lineage the
  dry run printed equals the record's. The `__main__` line is untested: a process would read
  the real tree's git once model cases exist, which §11 forbids.

**INFO**
- **L242 §8.7 — the spend prints its token usage.** Fill: L210 printed the metrics and the
  path; the record's usage is the run's cost, and step 8's cost line reads it. The client
  `get_client()` returns is never closed: measured against a local server standing in for
  the API, `asyncio.run` over a `summarize` call on that client exits 0 with nothing on
  stderr under `-W default`.
- **L243 §8.7 — `RunPlan` carries `corpus_version`.** Fill: the dry run prints the version
  the record will carry, so it is computed once, in `plan_run`, and `score_corpus` records
  `plan.corpus_version` rather than computing it again.

## v1.6.8 — the scorer refuses before it spends (patch)

Theme: 2b's step 5 adds `corpus.py`. Reading §8.7's `score_corpus` against the code it calls
found raises that could come after the spend, helpers named but never specified, and
behaviors the existing fake client can't see. No invariant moves; CLAUDE.md is unchanged.

**WARNING**
- **L235 §8.7, §13 — every refusal comes before the first call, and none creates the
  record.** Conflict: L46 and L208 keep one case's failure from losing a paid run, and
  §8.7's code could still raise after `gather` on two inputs. Measured on 5b4dd03: two rows
  sharing an id make the record fail (`n_cases counts the distinct case ids`), and
  `score_corpus` took any list; a `runs_path` whose directory doesn't exist, or that is a
  directory, fails at `append_jsonl`, after the spend. L46 wins: `plan_run` holds every
  pre-spend step. It sorts the model cases by id, so a run's rows diff by (case, repeat)
  whatever order the caller passed; refuses no model case and a duplicated id; reads the
  tree (L207); and makes `runs_path`'s directory, refusing a path that exists and is not a
  file. It never creates the file. Measured with git 2.43.0: an empty directory is absent
  from `git status --porcelain`, and an empty untracked `corpus_runs.jsonl` lists as
  `?? backend/`, so a created record would read every first run as dirty. Unguarded: a full
  disk, and the directory removed or replaced between `plan_run` and the append. `plan_run`
  hands `score_corpus` a `RunPlan`, which never leaves `corpus.py`: a layer-internal shape
  (L104), so §13 names it beside `CallConfig` and its sanctioned exceptions stay three.
- **L236 §8.7 — the status read pins its untracked mode and takes no lock.** Fill: L207
  states what `git_is_dirty` counts and not the command. Measured with git 2.43.0, under
  `status.showUntrackedFiles=no` with an untracked `cases/new.yaml`:
  `git status --porcelain` prints nothing, and with `--untracked-files=normal` it prints
  `?? cases/`, L207's motivating case. Porcelain v1 ignores `status.branch` and
  `status.showStash` (measured), so no other config needs pinning. On a tracked file whose
  stat changed and bytes didn't, plain `status` rewrites the index and `--no-optional-locks`
  leaves it untouched (measured), so the read takes no `index.lock` while another git
  process works the same checkout. `current_git_sha` is `git rev-parse HEAD` with
  `check=True`.
- **L237 §11 — the scorer's tests can see its concurrency.** Fill: L211's list ran on a fake
  that never suspends. Measured on Python 3.14.4, three gathered calls: with a call that
  never suspends, the peak in flight is 1 with `Semaphore(1)` and 1 without it; with one
  that suspends once, 1 and 3. A clock started outside the semaphore is invisible the same
  way. The scorer's fake suspends once per call, and its scripts are keyed by raw text, so
  no test depends on the order `gather` schedules. §11 adds the semaphore's bound, the clock
  started inside it, the crashed case's log line in L113's form, and L235's refusals; the
  git reads run on a repository under `tmp_path`.

**INFO**
- **L238 §8.7 — `append_jsonl` writes one record per line.** Fill: §8.7 named the helper and
  nothing else. It opens the file to append, in UTF-8, and writes the record's
  `model_dump_json()` and a newline; JSON escapes the newlines inside strings, so a record
  is one line.
- **L239 §8.7 — the scorer's code passes the repo's lint.** Conflict: §11's free tier runs
  ruff on every push, and §8.7's `datetime.now(timezone.utc)` fails UP017 at
  `target-version = "py314"` (measured). The lint wins: `datetime.now(UTC)`. The judge
  factory is compared with `is not None`, as `judge_enabled` reads it.

## v1.6.7 — the import boundary refuses edge modules (patch)

Theme: 2b's step 5 adds `corpus.py`, an edge module that reads settings and calls the API,
beside `evals/runner.py`, which keeps its pure parts (L188). Reading §11's import-boundary
test against invariant 1 before that module lands found that the walk refuses three names,
not the edge. No invariant moves; CLAUDE.md is unchanged.

**INFO**
- **L234 §11 — the walk refuses every backend module outside the domain.**
  Conflict: invariant 1 has the domain modules read no settings and know no vendor, with an
  AST test holding the line (L188), and §11's walk refused `backend.config`, `anthropic`,
  and `fastapi` by name. An edge module reads settings and imports a vendor, so a domain
  module importing one reaches both through it. Measured at 2a0a4ae: the walk finds nothing
  to refuse in `from backend.orchestrator import summarize` inside `evals/`, and importing
  `backend.orchestrator` loads `backend.config` and `anthropic`. Invariant 1 wins: the walk
  refuses `anthropic`, `fastapi`, and any `backend` module outside §0's domain (`schemas`,
  `tracebacks`, `grounding`, `evals`, `clinical`), so one rule covers `backend.config` and
  every edge module, and a new edge module needs no entry in the test.

## v1.6.6 — the corpus knobs' domains (patch)

Theme: 2b's step 4 adds L209's three knobs to `config.py`. L77 has every knob declare its
domain, and L209 gave `runs_path` only a default; the two counts' bounds are declared twice,
in `Settings` and in the record, with nothing tying them. No invariant moves; CLAUDE.md is
unchanged.

**INFO**
- **L232 §10 — `runs_path` names a `.jsonl` file, checked at boot.** Conflict: L77's "every
  knob declares its domain" vs L209's `runs_path`, which declared none. Measured: from the
  environment, `RUNS_PATH=""` becomes `Path(".")`, the working directory;
  `backend/evals/runs/` loses its slash; `runs.json` passes as given. Nothing would reject
  any of them until `append_jsonl`, which `score_corpus` calls last, after the spend: the
  loss L205 and L208 guard against. L77 wins: a validator requires the `.jsonl` suffix, which
  rejects all three. The default stays relative: `backend` is not installed as a package
  (an import from `backend/` fails, measured), so `python -m backend.corpus` runs only from
  the repo root, where the default resolves.
- **L233 §10 — the corpus counts' bounds match the record's.** Fill: `corpus_repeats` and
  `corpus_concurrency` are `ge=1` in `Settings`, and `CorpusRunRecord.repeats` and
  `concurrency` are `ge=1` in §4.2. If the settings side were loosened, a run would start,
  spend, and fail the record's validation at its end. A test pins each pair's bounds equal,
  as L187's does for `ChecksConfig`.

## v1.6.5 — the run's rows and metrics, as built (patch)

Theme: 2b's step 3c builds `case_result`, `errored_case`, and `corpus_metrics` (§8.7) over
v1.6.4's shapes. What an errored row lists, the order of a row's lists, and the denominator
of a flaky case were unstated; whether an errored check counts as a catch was implied but not
said; and §13's tree left two of the functions out. No invariant moves; CLAUDE.md is
unchanged.

**INFO**
- **L228 §4.2, §8.7 — what a row's lists hold, and their order.** Fill: §8.7 named
  `errored_case`'s status (L205), cost, and draft (L186, L203), never its lists. No check
  result reaches an errored row, so it names no fired or errored check, and
  `missing_expected` holds every expected flag: a detection trap whose pipeline failed
  missed what it expected. Each list of check names in a row is sorted, so a committed run
  diffs cleanly and two runs' rows compare line by line.
- **L229 §4.2, §8.7, D11 — a flaky case's pass fraction is over its applicable repeats.**
  Fill: D11 named no denominator. The rates count a repeat unless it is `not_applicable`
  (L205), and so does the pass fraction; a case with no applicable repeat isn't flaky.
  `flaky_cases` is sorted by id. Whether an errored repeat should count is #9's entry 18.
- **L230 §8.7 — an errored live CRITICAL is not a catch.** Fill: L206 counts a live CRITICAL
  that fired. An errored one turns the note red in production (invariant 12), for the crash
  and not for what the model did, and `fired_critical` holds no errored check (L224), so it
  doesn't count. The row records it in `errored_checks`.
- **L231 §13 — runner.py's line names case_result and errored_case.** Conflict: §8.7 keeps
  `case_result` and `errored_case` in `evals/runner.py` with the other pure parts, and
  §13's tree listed `run_checks · case_verdict · corpus_metrics · CHECKS_VERSION`. §8.7
  wins: the tree names all six.

## v1.6.4 — the corpus record's rows (patch)

Theme: 2b's step 3 builds §4.2's record shapes. Reading them against the code that fills
them (Oct 15, at a7e62ca) found a metric the row can't compute, a validator that counts the
rows without checking which they are, and rules the comments state and the types don't. The
spec's models, run as written, accepted the rows and values L225 to L227 quote (measured).
No invariant moves; CLAUDE.md is unchanged.

**WARNING**
- **L224 §2, §4.2, §8.7 — a row records which checks fired at CRITICAL.** Conflict: L206
  counts a fidelity repeat as caught when a live CRITICAL fired, because production would
  have shown it, and production shows a result's severity. `CaseResult` recorded the fired
  checks by name, and `corpus_metrics` reads only the rows, so it could read only a check's
  registered severity. A live CRITICAL check can lower a finding to WARNING (L38):
  `diagnosis_in_quote`'s downgrade, `allergy_preserved`'s dropped NKDA,
  `allergy_contraindication`'s cross-class rung. Measured at a7e62ca: a fidelity case
  labeled `metformin` whose note drops it and writes "Possible pneumonia" citing "Pneumonia
  on CXR" fires `must_preserve` CRITICAL and `diagnosis_in_quote` WARNING, and fails. Read by
  name, a live CRITICAL fired; read by result, none did, and production showed no CRITICAL.
  That is the catch L206 declines, reached through a lowered finding. L206 wins:
  `CaseResult.fired_critical` names the fired checks with a CRITICAL result, and
  `fidelity_caught` reads it.

**INFO**
- **L225 §4.2 — one row per case and repeat.** Conflict: `n_cases` counts the distinct
  model cases and the rows are one per (case, repeat), while L212's validator compared only
  the count. It accepted `n_cases=2`, `repeats=2` with rows (a, 0), (a, 0), (a, 7), (b, 0).
  L203's replay and D11's `flaky_cases` read rows by case and repeat. The validator now
  requires `n_cases` distinct case ids, each with one row for every repeat from 0 to
  `repeats` - 1.
- **L226 §4.2 — a row's error rules are validated.** Fill: L205's "a case with an `error`
  is failed" was a comment, and the model accepted `error="APIError"` with `status`
  passed. A row without an error holds the draft and the cost `summarize` returned, since
  only a pipeline failure or a crash loses either (§8.7); that was unstated. Both are now
  validators, and the second means every row without an error replays (L203).
- **L227 §4.2 — the record's time and rates have domains.** Fill, beside L212: `ran_at` is
  timezone-aware, since a committed timestamp without a zone is ambiguous (a naive one was
  accepted). Each rate in `CorpusMetrics` is in [0, 1] when it isn't `None` (7.5 and -1
  were accepted); the bounds also reject NaN and infinity (measured). Declined: format
  patterns on `git_sha` and the three versions. Each is derived (invariant 15) and its
  producer is tested, so a pattern is a second copy of its format, and `git_sha`'s would
  have to choose between git's SHA-1 and SHA-256 object formats.

## v1.6.3 — must_not_add's omission row (patch)

Theme: `must_not_add` registers in 2b's step 2d. As a CRITICAL check it needs an omission
row (D17), and §8.4's table gave it the one `must_preserve` has, "omission is their
subject", which is false of a check whose subject is invention. No invariant moves;
CLAUDE.md is unchanged.

**INFO**
- **L223 §8.4, §8.5 — an omission gives must_not_add nothing to fire on.** Conflict: the
  omission table's shared row called omission the subject of both reference checks, while
  §8.4 point 4 has `must_not_add` fire on a claim that reads its label positively, so an
  omitted claim adds nothing and an omitted invention is the faithful note. The row splits:
  `must_preserve` fires on the omission it labels; `must_not_add` has nothing left to fire
  on. Its free-tier test pins both halves. §8.5's fixture table gains the injected trap
  `detect_added_medication`, where a stopped drug is written as taken from a span that cuts
  off its stop cue (L157): every live check passes, and `must_not_add` fires alone
  (measured). `control_pcn_allergy_azithro` labels its amoxicillin as `must_not_add`'s
  exercising control (L222), and neither reference check fires on it (measured).

---

## v1.6.2 — the coverage rule's reference predicates (patch)

Theme: `must_preserve` registers in 2b's step 2c. As a CRITICAL check it falls under §8.5's
coverage rule, which states what exercises each CRITICAL check and named nothing for the
reference checks. No invariant moves; CLAUDE.md is unchanged.

**INFO**
- **L222 §8.5 — a label exercises a reference check.** Fill: a control exercises a check
  when the check has something to compare on it, and `must_preserve` and `must_not_add`
  compare labels with the note, so a control exercises one by carrying a label of its list.
  The coverage test's predicates now take the case, since a label lives on the case, not
  the note. The injected `control_pcn_allergy_azithro` labels its amoxicillin allergy as
  `must_preserve`'s exercising control, and `detect_dropped_allergy` labels its penicillin
  allergy and expects `must_preserve` beside `allergy_preserved` (L145). §8.5's fixture
  table says both.

---

## v1.6.1 — the loader imports the label readers (patch)

Theme: 2b's reference-label code puts the label readers in checks.py, beside the helpers
they reuse, and the loader imports them to validate labels by the checks' own rule (L219).
That import registers the roster. §8.3's code comment named runner.py as checks.py's only
importer, and §13's tree had the loader validate expected_flags alone. No invariant moves;
CLAUDE.md is unchanged.

**INFO**
- **L221 §8.3, §13 — the loader imports checks.py.** Fill: the import registers the roster,
  so `load_cases` checks `expected_flags` against the full roster whatever imported the
  loader first; before it, a script that imported the loader alone rejected every detection
  case (measured at 3c11fff: 16 problems over the 16 detection cases, each an unregistered
  check; after, all 20 cases load). §8.3's comment names both importers; §13's tree names
  the readers in checks.py and the label validation in loader.py.

---

## v1.6 — what a reference label asserts (minor)

Theme: what a reference label asserts, decided before 2b builds the checks that read it.
§8.4 had `must_preserve` survive when a label's normalized text was in the kind's extractor
output, with polarity for findings alone. Designing 2b's reading functions showed that
leaves a status flip on a continued home medication, the CI-only gap D17 hands to
`must_preserve`, passing its own net, and a labeled "r/o PE" kept by a note that writes
"PE". A label now states one reading in its kind's extractor's terms, and the note must
keep it. The input is #8's entry 17, from the design room's prototype at 7833526, signed by
Cal on Oct 14, 2026. #8 closes with this revision; "spec: deferred amendments" opens with
its entries 1 to 13, 15, and 16. No invariant moves; CLAUDE.md is unchanged.

**WARNING**
- **L215 §8.4, §8.6 — a medication label carries its status.** Amendment (#8 entry 17): as
  membership in the extractor's output, a `metformin` label was kept by "Not on metformin",
  and a continued home medication written as discontinued passed `must_preserve`, D17's
  declared net for that omission; `med_status_consistency` sees the flip only when the
  claim's own span says otherwise. A label reads through `extract_med_status`: `metformin`
  is active, `metformin held` stopped, `Glucophage` metformin active. It is kept when some
  claim reads the drug at that status, so a hold-and-resume course keeps both readings.
  Measured at 7833526: "Hold metformin" and "Not on metformin" fail a `metformin` label,
  CRITICAL; "Continue metformin" fails `metformin held`.
- **L216 §8.4, §8.6 — a labeled diagnosis carries its certainty, compared note-wide.**
  Amendment (#8 entry 17): a label kept by membership let "PE" keep an "r/o PE" label. A
  label reads through the diagnosis extractors as a certainty or an exclusion, and the
  note's strongest certainty is compared with the label's: dropped, excluded against an
  asserted label, or upgraded, CRITICAL; downgraded, WARNING. An exclusion label is kept by
  the exclusion; asserting the diagnosis definite or probable, or never naming it, is
  CRITICAL, and reopening it as possible or rule-out without the exclusion is a WARNING.
  Reusing `diagnosis_in_quote`'s comparison was prototyped first and misfired: it compares
  one claim with its span, and a note across claims records a course, so "r/o PE in the ED"
  with "PE confirmed on CTA" read as a downgrade of a definite label. The note-wide rule
  keeps that course and keeps a rule-out ending in "PE ruled out" against an exclusion
  label (measured). "Possible PE" upgrades an "r/o" label, CRITICAL, since possible
  outranks rule-out, as in `diagnosis_in_quote`.
- **L219 §4.2, §8.5, §11 — reference labels are validated at load.** Fill: L116's reason
  holds for labels, since a label no check can read is a case that fails forever. Each
  label must read as one entity with one reading; `present` applies to findings and agrees
  with the text; the raw text keeps every `must_preserve` reading, by the check's rule; a
  `must_not_add` label reads positively and the raw text doesn't add it. Measured at
  7833526: a bare "penicillin" reads no allergen, "warfarin" and "CP" read nothing
  (unlisted), "Eliquis" reads apixaban, and "Mother on apixaban" reads apixaban active, so
  a family-history drug can't be a `must_not_add` label.

**INFO**
- **L214 §4.2, §8.4 — a label is read by its kind's extractor.** Amendment (#8 entry 17):
  §4.2's example label was a bare "penicillin", which `extract_allergies` reads as nothing
  without allergy context (measured), and §8.4 compared a label's normalized text. A
  label's text is now read by its kind's extractor and states one reading: `PCN allergy`,
  `metformin held`, `metformin 500 mg BID`, `denies chest pain`, `r/o pulmonary embolism`.
  A `must_not_add` label is read the same way and fires on a claim's positive reading, as
  before (L36).
- **L217 §4.2, §8.4, §8.6 — the reference findings' severities.** Amendment (#8 entry 17):
  §4.2 had severity follow kind, a dose WARNING and everything else CRITICAL. A dropped
  NKDA or NKA label is a WARNING, as `allergy_preserved` makes it (D10, L144), and a
  labeled downgrade or reopened exclusion is a WARNING, as `diagnosis_in_quote` makes it
  (D12, L140). Each is a finding lowering the check's CRITICAL (L38).
- **L218 §8.4 — the reference findings' claims, and a missing case.** Fill: a
  `must_preserve` finding is note-level, since what it misses is in no claim; a
  `must_not_add` finding names each claim that adds the item. Both checks raise when `case`
  is `None`, so a run without an answer key errors (invariant 12).
- **L220 §8.8 — labels read through the extractors.** Fill: the loader checks a label
  against the raw text through the check's own extractor (L219), so a label can't state
  what the extractor misreads, and a misread label loads. Measured: "metformin held, then
  restarted" reads stopped as label and source alike (L168).

---

## v1.5 — the corpus record and its scorer (minor)

Theme: what 2b's record keeps, decided before 2b builds it. #7's entry 14 was due before
`score_corpus`; the true deadline was earlier, the commit that adds `CaseResult`. Deciding
it showed the record couldn't serve the readings #7 schedules for 2b's baseline, and
walking §14's 2b checklist against main (Oct 14, at 9ff7f3c) found three ways §8.7's scorer
could lose its record, its lineage read after the run, and details it left unstated. The
input is that walk and its decisions, signed by Cal on Oct 14, 2026. #7 closes with this
revision; "spec: deferred amendments" opens with its entries 1 to 13 and 15. Invariant 15's
statement changes its wording (`corpus_version`'s inputs); no invariant is added, removed,
renumbered, or retitled, and no standing instruction changes, so CLAUDE.md is unchanged.

**WARNING**
- **L203 §4.2, §8.7 — a case keeps the model's draft.** Amendment (found deciding #7 entry
  14): #7 schedules entries 10, 11, and 15 to be read against 2b's baseline, and the record
  couldn't answer them. A bare-name quote that passes every check leaves no trace in a
  `CaseResult` (entry 10); an unexpected `med_status_consistency` can't be told true from
  false without its claim (entry 11); no span is recorded (entry 15). `CaseResult.draft`
  keeps what the model returned, `None` only when `summarize` returned no draft. Grounding
  and the checks are pure, so a committed run replays against the code at its commit (D5)
  with no API call. The cost is the record's size, which the baseline measures.
- **L205 §4.2, §8.7 — a pipeline failure is a failed case; `pass_rate` can be `None`.**
  Fill: `errored_case`'s status was unstated. `fidelity_caught`'s definition ("FAILED
  without a pipeline error") implies `failed`, and a case whose note never reached the
  checks must not read as safe (invariant 12). Conflict: `pass_rate: float` sat under the
  rule "None, not 1.0, over an empty denominator", and a run whose every repeat is
  `not_applicable` would divide by zero in `corpus_metrics`, after `gather`, losing the
  record the run paid for. The rule wins: `pass_rate` is `float | None`. A repeat is
  applicable unless it is `not_applicable`.
- **L206 §2, §4.2, §8.7 — `fidelity_caught` counts a live CRITICAL.** Fill: §8.7 said "at
  least one reference-free (live) check fired" and named no severity. The metric claims
  what production would have shown. Counting a WARNING lets an incidental one (a degenerate
  quote) score a catch on a fidelity failure, and that lands exactly on the CI-only gaps
  the omission table declares (D17), the gaps the metric exists to expose. Counting
  CRITICAL alone undercounts the narrow WARNING slice (`new_prescription_preserved`), which
  errs safe; a WARNING stays visible in `unexpected_fired`.
- **L207 §4.2, §8.7 — the lineage is read before the first call.** Conflict: L45 records
  `git_sha` and `git_dirty` so the record names the code that ran, and §8.7's code read
  both after `gather`, while `PROMPT_VERSION` and `CHECKS_VERSION` are fixed at import: a
  tree read after a long run can name code that never ran. Both are read before any spend.
  `git_is_dirty` counts untracked files and skips ignored ones; outside a git checkout
  `current_git_sha` raises, before anything is spent. Measured Oct 14:
  `git status --porcelain` lists an untracked case YAML
  (`?? backend/evals/cases/new_case.yaml`) and nothing for a file under the ignored
  `.venv/`; `git rev-parse HEAD` outside a repository exits 128.
- **L208 §8.7 — every per-case step is inside the `try`.** Conflict: L46 says one case's
  exception can't escape `gather` and discard the rest, and §8.7's code built the judge
  inside the semaphore but outside the `try`, and the case's result outside both. A raise
  in either discarded every row. The judge is now built after `summarize` returns (only
  `run_checks` needs it), and `case_result` runs inside the `try`. The judge's half is
  unreachable until 2c; `case_result`'s is reachable through any bug, which is why
  `run_checks` catches its own.

**INFO**
- **L201 §4.2, §8.7 — a case records summarize's wall time.** Amendment (#7 entry 14):
  L185's bound was measured once per pin, on one call (L198), while a corpus run makes
  every call the bound depends on and kept none of the timings.
  `CaseResult.summarize_wall_s` (finite, `ge=0`) is `time.perf_counter()` around the
  `await`, inside the semaphore. Measured Oct 14 on SDK 1.9.0 against a local server that
  never answers (`timeout=0.5`, `max_retries=2`): `APITimeoutError` after 2.81 s, three
  attempts starting at 0.05, 0.93, and 2.31 s. The timeout clocks each attempt, and the
  wall time also holds the SDK's retries and backoff (0.5 s initial, 8 s maximum, its
  constants). The bound is read from rows with no error and one validation attempt, naming
  its inputs; a hidden transport retry only lowers the throughput read, which errs safe.
  Corpus replies are short, so the samples sit far below the 20,000-token budget, and
  reading the bound from them assumes a steady rate. Declined: the entry's other half,
  throughput's distribution in `CorpusMetrics`, since those are L3's verdict numbers and a
  percentile there would freeze an analysis the rows already allow; and timing inside
  `summarize`, which would ride `RunMetadata` onto the wire (L76).
- **L202 §4.2, §8.7 — the record carries its concurrency.** Amendment (with L201):
  `CorpusRunRecord.concurrency` (`ge=1`) beside `repeats`. Contention lands in L201's wall
  times, as 429 retries and their backoff, and in how many cases fail upstream, so neither
  reads honestly without it.
- **L204 §3.1 inv. 15, §8.5, §8.7, §14 — `corpus_version` hashes the model cases a run
  scores.** Conflict: §8.5 hashed "the sorted contents of `evals/cases/`", invariant 15
  "hash(cases dir)"; §8.7 called `corpus_version(cases)` on parsed cases; §14 said "over
  the cases 2a's loader reads." The directory form moves a model run's lineage when an
  injected case changes, though the run never reads one. §8.7 wins, narrowed to the cases
  scored: each enters as its `model_dump_json()`, sorted by id, twelve hex digits. Measured
  Oct 14 over the 20 injected cases (the form doesn't depend on species): two loads agree;
  a YAML comment and two swapped top-level keys leave it unchanged; an edit to one case's
  raw text moves it.
- **L209 §10 — 2b's corpus knobs.** Fill: `corpus_repeats` `ge=1`, default 3 (D11);
  `corpus_concurrency` `ge=1`, default 1; `runs_path` defaults to
  `backend/evals/runs/corpus_runs.jsonl` (§13). Concurrency defaults to 1 because the
  account's rate limits for the pinned model aren't known in the design room, a 429 that
  outlasts the SDK's retries fails its case, and contention lands in L201's times. At the
  smoke run's 4.37 s a call (L198), 72 calls take about 5 minutes. Raise it in `.env` once
  the limits are known; the record says what ran (L202).
- **L210 §8.7 — a run starts from `python -m backend.corpus`, behind `--spend`.** Fill:
  §8.7 made `corpus.py` the place a real run gets its client and never said how a run
  starts. Without the flag the module loads the cases, prints the planned calls (n × k, and
  the ceiling with validation retries), and exits; with it, it runs `score_corpus` with
  `get_client()` and prints the record's metrics and its path. Spending is never a default.
- **L211 §11 — the scorer's free tests.** Fill: §11 named none, and with a fake client
  `score_corpus` is deterministic: L46's parity and recorded all-failed runs, L186's usage
  per path and its sum, L207's read order, L208's two holes, and L201's and L203's fields.
- **L212 §4.2 — the record's domains.** Fill: `CaseResult.repeat` `ge=0`;
  `CorpusRunRecord.repeats`, `concurrency`, and `n_cases` `ge=1`; `cases` holds `n_cases` ×
  `repeats` rows; `usage` and `validation_attempts` are `None` together, as L186's comment
  said, now a validator.
- **L213 §14 — the manual-dispatch workflow joins phase 3.** Fill: D5 and §11 describe a
  workflow that runs the model corpus on dispatch and uploads the record, and no phase's
  checklist built it. It needs the API key as a repository secret; §10's "CI needs no
  secret" stays true of `ci.yml`. Phase 3 is the phase that deploys.
---

## v1.4.2 — §8.8 states the laterality gap (patch)

Theme: v1.4 deferred laterality's check (#7, entry 6), and §8.8, which states what the
harness doesn't know, didn't name it. No invariant moves; CLAUDE.md is unchanged.

**INFO**
- **L200 §8.8 — laterality is unchecked, and §8.8 says so.** Fill: no extractor reads a
  side and no check compares one, and §8.8 named neither. Measured at 44bc4bb, in ci mode,
  cutoff 90: a claim reading "Right knee pain after a fall" under the verbatim quote "Left
  knee pain after a fall" grounds at Tier 1 and fires no check. A quote swapping the side
  clears the cutoff and fires none in most shapes (mid-note: "L arm" for "R arm" 96.9, a
  43-character left/right swap 93.0), but a short left/right swap can fall below it, since
  the words differ in length: "Left knee pain after a fall" mid-note scores 88.9,
  `UNSUPPORTED`, a flag the clinician sees (against the swapped sentence alone it scores
  92.3). The check itself is a minor amendment (#7, entry 6); stating the gap is a fill,
  since §8.8 exists to state what the harness can't see.

---

## v1.4.1 — v1.4's smoke run (patch)

Theme: the L81-form smoke run after v1.4's code passed on the pinned model, at `6200666`
on Oct 14: `claude-haiku-5-5`, `prompt_version` f568c08861a1, `checks_version`
c22202d58517, `validation_attempts` 1, 1,821 input and 1,195 output tokens, all 24 claims
grounded at Tier 1, and none of the 11 checks failed or errored. It recorded what L185 asks
for, and its preflight caught a gap §14 didn't name. No invariant moves; CLAUDE.md is
unchanged.

**INFO**
- **L197 §5.3 — the prompt's label names L191.** Fill: v1.4 changed the prompt's text
  (L191) and left the block introduced as "The clinical version (v1.3):". It reads
  "(v1.3, L191)". Found in step 2's review, Oct 13.
- **L198 §5.2 — the timeout bound, measured end to end.** Fill: L185 has the smoke run
  re-measure throughput at each pin change. The run took 4.37 s for 1,195 output tokens,
  with the prompt, the network, grounding, and the checks included: about 273 tokens/s, so
  a 20,000-token reply takes about 73 s, inside the 90 s timeout with about 19% to spare.
  The probe's ~320 tokens/s (about 63 s) is generation alone. The end-to-end figure is the
  one to bound by: it also counts grounding, the checks, and the browser's round trip, so
  it overstates the API call the timeout clocks, which errs safe. Output per input char was
  1.27 (1,195 / 943), inside the probe's 1.19 to 1.32.
- **L199 §14 — the smoke run checks the model id itself.** Fill: the id isn't hashed into
  `PROMPT_VERSION`, and the `models.retrieve` comparison (L85) reads `settings.model` on
  both sides, so a stale `MODEL=` line in `.env` passes both. v1.4's preflight caught
  exactly that, `claude-haiku-4-5-20251001` from a line that had matched the pin through
  2a, before any spend. The smoke run checks `settings.model` against the id `config.py`
  pins (L84) before its call.

---

## v1.4 — the call shape, verdict lineage, and the invariants (minor)

Theme: the revision 2b's baseline can't be honest without, cut before any 2b code (#4's
decision): the call shape the pinned model accepts, an output budget that fits its
timeout, verdict lineage that covers the knobs, the prompt the baseline measures, and a
post-cue fix for phrasing realistic notes hit constantly. The invariants' statements move
into the spec. The input is #1's decision comment and its addendum, each signed by Cal on
Oct 12, 2026; #1 closes with this revision, and "spec: deferred amendments" opens with
what it defers (entries 2, 3, 4, 5, 8, 10, 11, 13, 14, entry 9's dash half, the RAG
design, and entry 6's `EvalReport` question). Invariants 1, 3, 4, 15, 16, and 18 change
their wording; CLAUDE.md changes in the same commit.

**CRITICAL**
- **L193 §7, §8.8 — a post-cue reaches a list that opens its clause.** Amendment (#1
  entry 9): a post-negation cue negated only the finding before it, so "Fever, chills, and
  nausea denied." read fever and chills present, and a faithful "Denies fever" fired
  `negation_consistency`. A negation, stop, or start post-cue now reaches back over the
  coordinated run before it (joined by ",", "and", "or", "/", "&") when the run opens its
  clause: the text's start, or after ".", ";", a line break, or a header's colon;
  otherwise it reaches the adjacent mention. Prototyped Oct 12: the clause condition stops
  the over-reach a bare run had ("Continue lisinopril, metformin held" read the lisinopril
  stopped; "Reports fever, chills denied" read the fever absent), and on "ROS: fever,
  chills, and nausea denied" it clears v1.3's two false CRITICALs on faithful notes and
  catches the flipped claim v1.3 missed. Certainty post-cues stay adjacent; allergy
  post-cues keep L128. §8.8 states the cost (a list after a word reads adjacent-only), and
  the allergy dash/parenthetical half moves to the next revision.

**WARNING**
- **L180 §5.5, §10 — the pinned model is `claude-haiku-5-5`.** Amendment (#1 entry 1,
  #4): `model_max_output_tokens` is 128000 (`models.retrieve`). Measured Oct 12 at
  `aea0a22`, SDK 1.9.0, on the smoke encounter: v1.3's call shape gets a 400 on
  `temperature` alone; forced `tool_choice` with no sampling parameters is accepted, one
  `tool_use` block and zero thinking tokens per call; the candidate shape
  (`thinking: disabled`, `effort: low`) returns a draft that grounds clean and fires no
  check. Throughput ~320 output tokens/s. Request ids: #4's decision comment. Sonnet 5.5,
  Opus 5.5, and Fable 5.1 reject forced `tool_choice`, so the Sonnet comparison arm is
  decided at phase 3 planning, with the cost line.
- **L181 §3, §5.2, §5.5, §8.5, §8.7, §11, §13 — no sampling parameters; thinking and
  effort pinned.** Amendment (#1 entry 1): `CALL_CONFIG` carries forced `tool_choice`,
  `max_tokens`, `thinking: {"type": "disabled"}`, and `output_config: {"effort": "low"}`
  (provisional; the baseline's repeats test it). `SamplingBody` and `extra_body` go;
  `CallConfig` types the two new fields with the SDK's own param types, `thinking` narrowed
  to the disabled variant (mypy rejects an enabled config there, measured), and the
  `LLMClient` Protocol and the fake client type them too. L82's test is inverted: every
  attempt carries the pinned fields and no `temperature`, `top_p`, `top_k`, or
  `extra_body`. Variance is measured, not suppressed (§3's principle 3, D11, §8.5).
- **L184 §5.2 — the output budget is measured and sized to the timeout.** Amendment (#1
  entry 16): `max_input_chars` 12,500 and `output_tokens_per_input_char` 1.6, so
  `max_output_tokens` is 20,000 (`12500 * 1.6` is exactly 20000.0, measured). The old 0.5
  gave every request 10,000 tokens while the smoke encounter ran 1.19 to 1.40 output tokens
  per input char, so an encounter past about 7,600 chars truncated: a 502 on input the
  route accepted, which 2b's baseline would have scored as the model's failure.
- **L187 §0, §4.2, §6, §8, §8.7, §9, §10, inv. 1, inv. 15 — the verdict knobs are
  parameters, recorded with the run.** Amendment (#1 entry 6, option 2): two corpus runs
  with `FUZZY_SCORE_CUTOFF` exported differently recorded identical lineage and different
  verdicts, and `grounding.py` and `evals/checks.py` imported `backend.config`, which
  needs the API key at import. `ChecksConfig` (frozen, `schemas.py`) holds
  `fuzzy_score_cutoff` and `min_quote_content_tokens`; `ground(..., *, config)` and
  `run_checks(..., *, config)` take it with no default; `settings.checks_config()` builds
  it at the edge only (`api.py`, `corpus.py`); `CorpusRunRecord.checks_config` records it
  whole. `ChecksConfig` re-declares `Settings`' bounds, and a test pins the copies equal.
  `EvalReport` is unchanged: whether persisted reports need the config is phase 3's
  question, on the next revision's issue.
- **L191 §5.3, §8.4, inv. 18 — the prompt names NKA.** Amendment (#1 entry 12): L144 made
  a dropped NKA a WARNING, as a dropped NKDA, but the prompt named NKDA alone. NKA joins
  the absence examples and the never-omit clause, and invariant 18. Clinical sign-off:
  Cal, 2026-10-12. Moves `PROMPT_VERSION`; a test asserts the clause names both.

**INFO**
- **L182 inv. 3, §8.2, §14 — invariant 3 restated.** Amendment (#1 entry 1): "Every
  pipeline LLM call pins what shapes its output": tool choice, thinking, effort, and
  token budget in one hashed call config, nothing left to an API default, no sampling
  parameters. The judge pins its own call config; its fields are 2c's. Closed phases'
  checklists stay as audited.
- **L183 inv. 16, §5.4 — invariant 16 on its new ground.** Amendment (#1 entry 1): with no
  `temperature`, an identical request still reproduces its cause (the budget, the input,
  the forced call), not an identical reply, so the fail-fast rule stands. The truncation
  comment in `summarize` follows.
- **L185 §5.2, §14 — the budget must fit the timeout.** Amendment (#1 entry 16):
  `max_output_tokens` divided by measured throughput must fit inside `llm_timeout_s` with
  margin (20,000 tokens at ~320/s is about 63 s, inside 90 s). It can't be checked at
  boot; the smoke run records throughput and repeats at every pin change (L81, L85).
- **L186 §4.2, §5.4, §8.7, inv. 4 — each case carries its cost.** Amendment (#1 entry 16
  and its addendum): `CaseResult` gains `usage: TokenUsage | None` and
  `validation_attempts: int | None` (`ge=1`), `None` together only when a crash lost the
  case's cost; a crash after `summarize` returned keeps it. `OrchestratorError` carries
  `validation_attempts` beside `usage`. `CorpusRunRecord.usage` is the sum of the known
  usages, a floor.
- **L188 §0, §8.7, §11, §13, §14, §17, inv. 1 — `score_corpus` is an edge module.**
  Amendment (#1's addendum): §8.7 filed it in `evals/runner.py`, where it reads settings,
  calls `summarize`, runs git, and writes `runs/`, so entry 6's import boundary would fail
  on the spec's own design. It moves to `backend/corpus.py`; `evals/` keeps the pure
  parts. An AST test asserts `grounding.py`, `evals/`, `schemas.py`, and `tracebacks.py`
  import nothing from `backend.config`, `anthropic`, or `fastapi` (it fails at `690907f`).
- **L189 §8.7, inv. 15 — `CHECKS_VERSION` hashes `schemas.py`.** Amendment (#1 entry 6):
  `all_critical_passed` and `EvalResult`'s errored-never-passes validator live there. The
  version also moves on edits that change no verdict, which errs safe; `score_corpus`'s
  source leaves the hash with L188.
- **L190 §8.4, §8.7 — every check takes the config.** Amendment (#1's addendum): `CheckFn`
  is `(note, raw_text, case=None, *, config)`, plus `judge` for a judged check; no
  `needs_config` flag.
- **L192 §6.2 — `NormalizedText.index_map` is a tuple.** Amendment (#1 entry 7): a frozen
  dataclass holding a list allowed `append` and made `__hash__` raise (both measured).
  Built as a list and frozen once at the end of `of()`.
- **L194 §8.8, §14 — v1.4 lands before 2b; the RAG design moves.** Amendment (#4): §14's
  phase-4 line names a later minor revision for the RAG design; 2b's checklist opens with
  v1.4's code and an L81-form smoke run on the pinned model. §8.8's two "waits for v1.4"
  lines name a later minor revision.
- **L195 §0, CLAUDE.md — the patch label and the issue name.** Amendment (#1's addendum):
  a patch is v1.x.y, in the spec, this file, and CLAUDE.md. The deferred-amendments issue
  is "spec: deferred amendments", so no revision renames it again.
- **L196 §3.1, §13, CLAUDE.md — the invariants live in the spec.** Amendment (#1 entry
  15): the spec cited the invariants by number and defined none. §3.1 holds each
  statement, numbers unchanged, in its v1.4 wording. CLAUDE.md keeps each number and
  title with a pointer, and the standing instruction whole for 1, 3, 4, 6, 11, 16, and 18
  (16's names its referent, the SDK's transport retries). A plan names every invariant its
  step touches. CLAUDE.md changes with the spec only when an invariant is added, removed,
  renumbered, or retitled, or its standing instruction changes.

---

## v1.3.41 — the 2a close's smoke run (patch)

Theme: the 2a close runs §14's smoke run although its trigger doesn't fire. No invariant
moves; CLAUDE.md changes in the same commit for the close itself, not for this patch.

**INFO**
- **L179 §14 — the 2a close runs the smoke run.** Fill: §14 repeats the smoke run at a
  phase close that changes the request shape, and 2a's doesn't: `PROMPT_VERSION` is
  382f0436e52f and the SDK 1.9.0 at main and at `v0.1-spine`, and `orchestrator.py` and
  the tool-schema snapshot are untouched since (measured). Two things no test sees did
  change: the response and the page, which nothing has rendered live, and real model
  output, which has never met `ground()` and `run_checks`. One run, cents, confirmed by
  Cal; the tag records it, and a finding it shows is recorded, not fixed.

---

## v1.3.40 — the 2a page (patch)

Theme: step 5c gives the phase-1 page phase 2a's report, flat, and fills two lines phase
3's UI inherits: span offsets count code points, and the empty state says "recognized." No
invariant moves; CLAUDE.md is unchanged.

**WARNING**
- **L176 §9.10, §14 — the 2a page.** Fill: §9.10 specified phase 3's UI and phase 1's
  page, and §14 gives the join, the banner, and every state to phase 3's React, so the
  static page's 2a reach had no statement; since L166 it rendered the note and no check.
  It renders the report flat: a verdict line reading `all_critical_passed` (L102) with the
  count of checks that ran, ids and flags on each claim card, and each result by its own
  flags, fired, didn't run, or passed, so an errored check never reads as passed
  (invariant 12). CI runs no JavaScript: a test pins the two fields the rendering turns
  on, and the design room ran the page in jsdom against six bodies (fired, clean, an
  errored critical, an empty note, a 503, and a body without a report).
- **L177 §4.1, §9.10 — span offsets count code points.** Fill: `source_span` is a
  half-open range into the raw text, and nothing said in what unit. Python indexes code
  points and JavaScript's `slice` counts UTF-16 units, so a character past the BMP shifts
  every span after it (measured: an emoji's JavaScript length is 2). The unit is stated,
  and the UI slices by code point, from the text it sent. The 2a page slices no span;
  phase 3's highlight does.

**INFO**
- **L178 §9.10, §10 — the empty state says "recognized."** Fill: an empty note on a
  clinical source the lexicons can't read raises no WARNING (L165), so "no clinical
  content found" claims what the check can't know. The copy says "recognized," and §10
  states why.

---

## v1.3.39 — finding aliases (patch)

Theme: step 5b-ii fills the findings' other names. A contracted refused stop reads as a
continue, findings gain aliases and words that state an absence, `quote_informativeness`
reads such a word as a statement, and §8.8 states what a slash abbreviation counts. No
invariant moves; CLAUDE.md is unchanged.

**CRITICAL**
- **L172 §7 — a contracted refused stop leaves the drug active.** Fill: `TERMINATORS` held
  "not stop", "not discontinue", and "not hold", and no contraction. Measured while
  drafting L167, "Don't stop apixaban" read stopped, so "Stop apixaban" passed
  `med_status_consistency` and the faithful "Continue apixaban" fired it; "don't hold" and
  "don't discontinue" read the same. The three contractions join, and a curly apostrophe
  reaches them through L170.

**WARNING**
- **L173 §7, §8.8 — finding aliases and words that state an absence.** Fill: `FINDINGS`
  listed one name per finding, so L139's own example ("Temp 37.0, afebrile") read nothing
  and a flip to "Febrile" passed. `FINDING_ALIASES` maps other names onto `FINDINGS`, one
  name for two where charting has one ("N/V"), and `ABSENT_FINDINGS` maps a word that
  states its finding absent ("afebrile" → fever). Measured, a negation inverting the word
  flips it inside every negated list ("denies chills, afebrile" read fever present), and
  an immune word misreads a double negation ("not afebrile"), so the word is immune and
  the double negations are aliases, matched whole. A test holds every target to
  `FINDINGS`. What stays misread is §8.8's: a double negation no table spells, and the
  word cut from one.
- **L174 §8.4 — an absence word is a statement in one word.** Fill: #5 asked whether a
  polarity-bearing word joins L158's NKDA/NKA exception. It does: the word reads absent
  under any cue (L173), so a span of it says all it means, and a faithful "Afebrile"
  citing "afebrile" drew a WARNING (measured). The exception reads `ABSENT_FINDINGS`
  through `ABSENCE_WORDS`, not a literal, and exempts a span whose every content token is
  one. The cost is NKDA's: the word cut from a double negation passes (§8.8).

**INFO**
- **L175 §8.8 — a slash abbreviation counts two tokens.** Fill: L161 set the default to
  flag "a one-word span", and `content_tokens` splits a slash abbreviation ("N/V" → n, v),
  so one charted word counts two and passes (measured). §8.8's L157 bullet says one-token
  and states the case. Joining slash abbreviations would change L160's count for "r/o PE"
  and "d/c metformin" too, so the count stands.

---

## v1.3.38 — restart and resume (patch)

Theme: step 5b-i fills the restart cues. A refused restart read as a start, two signed
tables read restart and resume apart and resolve for the start, the extractors' tokens
fold curly single quotes as grounding does, a limitation no table entry can fix is stated,
and the drug vocabulary's scope is filled. No invariant moves; CLAUDE.md is unchanged.

**CRITICAL**
- **L167 §7 — a refused restart or resumption stops the drug.** Fill: `MED_STOP_CUES` held
  "not start", and no refusal of the restart `MED_START_CUES` listed. Measured, "Do not
  restart apixaban" read the drug started and active, so "Restart apixaban" passed
  `med_status_consistency` and the faithful "Hold apixaban" fired it. "Do not resume
  apixaban" read active too, the terminator closing the negation's window, so "Resume
  apixaban" passed the same way. "not restart" and "not resume" join, with the
  contractions "don't start", "don't restart", and "don't resume" ("Don't start metformin"
  read started).
- **L168 §8.8 — a cue the scope rule can't reach.** Fill: measured while drafting L167, a
  mention takes one label and a post-cue reaches only the mention directly before it
  (L122), so "Apixaban held, then restarted" reads stopped. A faithful "Continue apixaban"
  fires `med_status_consistency` and "Hold apixaban", which drops the restart, passes it.
  A negation before a start participle no table spells reads as the start ("Not starting
  metformin"). No table entry reaches either; the fix changes the scope rule, a minor
  revision, so §8.8 states the gap and #1 carries the fix (entry 14).

**WARNING**
- **L169 §7 — restart and resume start a drug.** Conflict: `MED_START_CUES` read "restart"
  as a start ("a drug restarted at this visit is started at this visit"), and
  `TERMINATORS` read "resume" as "continue", two clinical synonyms read apart. The start
  wins: taking a held drug up again changes it at this visit (invariant 18), and
  `new_prescription_preserved` is the one check that sees one dropped. "resume" moves to
  `MED_START_CUES`, where as a pre-cue it still ends a stop's window ("Hold metformin,
  resume lisinopril", measured); "restarted", "restarting", "resumed", and "resuming" join
  it, and "restarted", "was restarted", "resumed", and "was resumed" join
  `MED_START_POST`. A restart phrasing already read active, so the entries move
  `new_prescriptions` alone.
- **L170 §7 — a curly single quote reads as the apostrophe.** Fill: §6.2's normalizer
  folds U+2018 and U+2019 for grounding, and the extractors' tokens didn't, so "Lisinopril
  d/c’d." read active (measured). `_tokens` folds both, one character for one, and L167's
  contractions match either spelling.

**INFO**
- **L171 §7 — the drug vocabulary is closed.** Fill: #5 asked whether the vocabulary holds
  the corpus's drugs only or also the common drugs a live paste names. Neither as worded:
  no case names acetaminophen, amoxicillin-clavulanate, or ibuprofen (measured), and
  breadth is v2's (§7's MVP scope, RxNorm). The vocabulary is closed in the MVP; a drug
  joins with the case that exercises it, carrying its common names (L126) and its class
  (L149).

---

## v1.3.37 — the 2a route (patch)

Theme: step 5's first sub-step gives the route its 2a shape: it grounds the draft, checks
the note in production mode, and returns both, and the page reads the note. A fill says
which of §9.1's parts 2a's route carries and what its tests assert. No invariant moves;
CLAUDE.md is unchanged.

**INFO**
- **L166 §9.1, §9.10, §14 — the 2a route.** Fill: §9.1 gave the full route and phase 1's
  smaller one, and named phase 1's test alone, so 2a's route, which §14 audits, carried no
  statement of which of §9.1's parts it has. It has §9.1's route without a judge (2c), a
  budget reservation, or persist (phase 3): `run_checks` runs in production mode with no
  judge, so it selects no judged check, and `note_id` is minted though it names no row
  (L58). The happy-path test asserts the four keys and a span offset into a padded paste;
  a test that registers its own checks asserts the route checks the note it returns,
  against the exact paste. The phase-1 page reads `note.claims` from here: measured, the
  page as it stood rendered a 2a body as "unexpected response body."

---

## v1.3.36 — the empty note (patch)

Theme: step 4c's second sub-step registers `empty_note_on_clinical_input`, which completes
the reference-free roster but the judge. A fill says what counts as clinical input, and a
limitation measured while drafting it is stated. No invariant moves; CLAUDE.md is
unchanged.

**WARNING**
- **L164 §8.4 — clinical input is what five extractors read.** Fill: §8.4's row fired
  while the raw text "yields any extracted entity" and never said which extractors. It
  reads five: every drug the raw text names at any status (`named`, L136), its allergies
  with D10's statements, its findings of either polarity, and its diagnoses, asserted or
  excluded. Doses, starts, and active drugs add nothing, each a subset of `named`
  (measured). A pertinent negative, a stopped drug, or a lone NKDA is something a faithful
  note says, so each counts. The finding names the entities in name order, on the banner.
- **L165 §8.8 — an empty note on a source the lexicons can't read.** Fill: measured while
  drafting step 4c-ii, a clinical paste naming nothing the lexicons list ("HTN follow-up,
  BP 152/96 today. Start amlodipine 5 mg daily") extracts nothing, so an empty note on it
  raises no WARNING and renders as non-clinical (§10); a non-clinical paste naming a
  listed word ("pain") draws the WARNING. The check's recall is the vocabulary's (L127).
  §8.8 states the gap; the page's empty-state wording is step 5's (#5), and step 5's
  vocabulary fill narrows it.

---

## v1.3.35 — the degenerate quote (patch)

Theme: step 4c's first sub-step registers `quote_informativeness`. Its conflict with §6.5
resolves for §6.5, it reads the span, the function words become a signed table, and the
knob gets its default and domain. A limitation measured while drafting it is stated, and
two fills ride along: injected controls fire nothing, and the roster's `drugs` is defined.
No invariant moves; CLAUDE.md is unchanged.

**CRITICAL**
- **L157 §8.8 — a span that cuts off its cue.** Fill: measured while drafting step 4c, a
  quote that is a bare name ("metformin" in "Hold metformin", "fever" in "Denies fever",
  "PE" in "r/o PE" or "PE ruled out") grounds at Tier 1, and the claim-local family reads
  the span alone (L35), so the name reads at its defaults: active, present, definite. A
  flip away from stopped, denied, or hedged passes every deterministic check, the CRITICAL
  ones included; a flip toward them fires. `quote_informativeness` covers a one-word span
  at WARNING (L158), a two-word one ("chest pain" in "Denies chest pain") is uncovered,
  and the judge can't gate a CRITICAL (invariant 7). Reading a span in its sentence
  changes what L35 compares, so the fix waits for v1.4 (#1); §8.8 states the gap.

**WARNING**
- **L158 §6.5, §8.4 — a bare lexicon name is not informative.** Conflict: §6.5 calls
  `quote="pain"` degenerate, and §8.4's roster passed any span holding a lexicon entity,
  as "pain", a FINDINGS entry, is. §6.5 wins: a name alone grounds wherever the source
  names it and drops the cue beside it (L157), the quote the check exists to flag. The
  exception D15 named, "NKDA", stays: D10's statements, NKDA and NKA, say all they mean in
  one word.
- **L159 §8.4 — `quote_informativeness` reads the span.** Fill: the roster counted content
  tokens and never said of what. The check reads the span, as the consistency family does
  (L35): it is what the claim cites and what the card highlights. A claim with no span is
  skipped, the red badge's.
- **L160 §7 — `FUNCTION_WORDS` and `content_tokens`.** Fill: the roster counted content
  tokens and no table said which words aren't. `FUNCTION_WORDS` lists closed-class words
  that name nothing alone (articles, prepositions, conjunctions, copulas, auxiliaries,
  pronouns, demonstratives), signed as a clinical table, since what it leaves out counts:
  a modal hedges ("may represent PE"), and "on" states a drug taken. `content_tokens`
  returns a text's words, numbers included, less those. A test holds the table apart from
  every other table's phrases, so "but", a terminator, counts.
- **L161 §10 — `min_quote_content_tokens` defaults to 2, `ge=1`.** Fill: the knob had no
  default or domain. 2 flags a one-word span and passes a terse statement ("hold
  metformin", "denies fever"); 3 would flag those. The injected controls' smallest span
  has 3 (measured). Below 1 the check could never fire, so construction rejects it (L77).
- **L162 §8.5, §8.7, §14 — an injected control fires no check.** Fill: §8.7 keeps the
  verdict CRITICAL-scoped so a borderline WARNING can't fail a case, and §8.5 said nothing
  of a WARNING on an injected control. An injected draft is authored and deterministic, so
  nothing in it is borderline: a WARNING there is a false positive. A test holds each
  injected control to no fired check at any severity; the verdict is unchanged.

**INFO**
- **L163 §8.4 — the roster's `drugs`.** Fill: the roster defined `named` (L136) and used
  `drugs` undefined, three rows apart since L156. `drugs` is the active ones alone,
  `extract_drugs`'s set, as `allergy_contraindication`'s row reads them. Found in review
  of step 4b-iv.

---

## v1.3.34 — the dropped prescription (patch)

Theme: step 4b closes with `new_prescription_preserved`, the live slice of medication
omission, and a fill to what it reads. The reference-free roster now holds every check but
step 4c's two and the judge. No invariant moves; CLAUDE.md is unchanged.

**WARNING**
- **L156 §8.4 — a dropped prescription is read against every drug the note names.** Fill:
  §8.4's roster had `new_prescription_preserved` compare new_prescriptions(raw) against
  drugs(note), and never said which drugs. Read as active drugs, a note writing a started
  drug as held or stopped fired it beside `med_status_consistency`, two findings for one
  error, the split D13 and L136 drew for presence and status. The check reads `named`, as
  presence does: a drug the note names at any status was kept, and its status is the
  status check's. A drug the note turns into an allergy is not named, so it still fires.

---

## v1.3.33 — the contraindication (patch)

Theme: step 4b's third sub-step registers `allergy_contraindication`, the showpiece. A
conflict in its own example code, two fills to §8.5, a limitation measured while drafting
it, and a gloss L150 left stale land with it. No invariant moves; CLAUDE.md is unchanged.

**WARNING**
- **L151 §8.4 — a drug no claim names puts its finding on the banner.** Conflict: §8.4's
  showpiece docstring, D17's omission table, and §9.7 say a contraindication whose drug
  only the raw text starts is note-level (`claim_ids=()`) and goes to the banner; the
  showpiece's code added the allergy claim's id whenever a claim stated the allergy, which
  put that finding on the allergy claim's card instead (`detect_contra_omitted_rx`). The
  three statements win: the banner is where §9.7 shows what the note hides. The allergy
  claim's id joins a finding only when the drug has a claim (L37), and the showpiece's
  code says so.

**INFO**
- **L152 §8.5 — `allergy_contraindication`'s exercise predicate.** Fill: a control
  exercises it when the raw text or a claim states an allergy, other than D10's
  statements, and a claim or the raw text's new prescriptions name a drug, so the ladder
  has a pair to resolve; `control_pcn_allergy_azithro` satisfies it, and §8.5 names it
  beside L146's.
- **L153 §8.5 — the identical-side-chain trap joins the fixture table.** Fill:
  `detect_shared_side_chain`, cephalexin started on an ampicillin allergy, freezes a v1.2
  bug: the class-level table read it as a WARNING, as it read ceftriaxone (D9).
- **L154 §8.8 — a drug after an allergy post-cue.** Fill: measured while drafting step
  4b-iii, "PCN allergy (amoxicillin)" and "PCN allergy - amoxicillin" read the amoxicillin
  as active, since §7's post-cue labels only the mentions before it, so a faithful copy
  fires `allergy_contraindication`; "PCN allergy: amoxicillin" matches "allergy:" as a
  header and loses the penicillin. Both follow §7 as written, so the fix changes a stated
  rule and waits for v1.4 (#1); §8.8 states the cost, and the corpus avoids the phrasing.
- **L155 §7 — the shape's `CROSS_REACTIVITY` comment follows L150.** Fill: the comment
  still glossed the table as applying when the side chain is "dissimilar or unknown", the
  wording L150 retired; it now reads "when no R1 side chain is shared". Found in review of
  step 4b-ii.

---

## v1.3.32 — classes and side chains (patch)

Theme: step 4b's second sub-step lands D9's ladder as a pure function, with the tables it
reads: three fills decided while drafting step 4 (#5), each entry signed by Cal. No
invariant moves; CLAUDE.md is unchanged.

**WARNING**
- **L149 §7, §8.8 — the vocabulary's classes and side chains.** Fill: D9's ladder reads
  `DRUG_CLASS` and `R1_GROUP`, and §7's shape gave examples but no table held the
  vocabulary's entries. `DRUG_CLASS`: amoxicillin, amoxicillin-clavulanate, and ampicillin
  are penicillins, cephalexin a cephalosporin, azithromycin a macrolide, ibuprofen an
  NSAID, lisinopril an ACE inhibitor; acetaminophen, apixaban, and metformin have no
  entry. Class names are lowercase, as allergen keys are, and a class name is its own
  class, so no listed drug may share one. `R1_GROUP`: ampicillin with cephalexin, and
  amoxicillin with amoxicillin-clavulanate, a group no listed cephalosporin shares; it is
  D9's named pair, and it pins the class rung ahead of the side-chain rung for an
  Augmentin allergy and an amoxicillin order. D9 compares identical side chains, so
  amoxicillin's and cephalexin's, similar but not identical, read as not shared, a
  WARNING; §8.8 states it beside reaction type.
- **L150 §7 — cross-reactivity both ways, and rung 4's detail.** Fill:
  `CROSS_REACTIVITY` holds (penicillin, cephalosporin) and (cephalosporin, penicillin),
  each a WARNING (D9, D14). D14 worded the detail for an unspecified allergy and not for
  an allergy to a specific drug: that one reads "R1 side chain not shared". "Dissimilar"
  would misdescribe a similar side chain, and a drug without an `R1_GROUP` entry shares
  none across classes, so only a class allergy leaves the side chain unknown.

**INFO**
- **L148 §7 — ampicillin joins the vocabulary.** Fill: as listed, amoxicillin's and
  cephalexin's R1 side chains differ, so D9's identical-side-chain rung could fire on no
  pair. Ampicillin, whose side chain is cephalexin's, joins `GENERIC_DRUGS` with no other
  names: its brand is discontinued, "amp" reads as an ampule, and Unasyn is
  ampicillin-sulbactam, another product.

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
