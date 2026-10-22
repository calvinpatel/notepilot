"""Clinical extraction: plain text to sets (spec §7).

Imports only lexicons.py (invariant 13): extraction takes plain strings and knows nothing of
the spine.

The scope engine is NegEx-shaped (L31), made exact by L121 and L122. Text is casefolded and
split into tokens: words, punctuation marks, and line breaks. Lexicon phrases are split the
same way and matched left to right, the longest first. Each cue carries its class as a label
(L124). A pre-cue governs the mentions that start within NEGATION_WINDOW words after it, and a
new pre-cue of any class replaces the open window, except that a start or stop cue a negation
directly precedes, across function words only, is refused (L271, L288): a refused start reads
negated, and a refused stop closes the window, its refusal reaching a stop cue joined after it.
A post-cue governs the mention immediately before it, across any mark but a comma or a
terminator, and "present" after a negation's second mention, across a comma and no "and" or
"or", takes that mention back (L291). A negation, stop, or start post-cue governs the whole list
before it when the list opens its clause: at the text's start, or after a period, a semicolon, a
line break, or a header's colon (L193). A cue in both a pre and a post table is a post-cue there
and a pre-cue anywhere else. A terminator closes the window.

A finding sees one class of cue, negation; after a drug in its clause, an indication cue opens
the list right after it, which reads no finding (L266, L280). A drug sees four at once:
negation, stop, start, and allergy (L124, L125, L128); then a restart that governs no mention
reaches back to the stopped drug before it, and a continue cue asserts continued (L262, L273), a
refused one reading stopped (L288). Allergy context reaches further than the others (L128): a
header at a line's start opens a section, and an allergy post-cue reaches back over any list,
not only one that opens its clause. A denied allergy reads no allergen and no status (L290). A
diagnosis sees negation and certainty, and a differential cue ("vs") governs both its sides
(L135). Every window keeps a repeat, and in a certainty or differential window a confirming cue
reads the repeat it governs definite (L265, L292).

Doses are read by a grammar over the same tokens (L131, L133): a number and a unit after a
drug, in the drug's sentence, and the frequency charted after it.

Dose, MedStatus, and Certainty are extraction's result types. They live here and evals imports
them from here, since clinical/ may not import the spine (§13's third exception, L132).
"""

import re
from collections.abc import Collection, Iterable, Iterator, Mapping, Sequence
from typing import Literal, NamedTuple

from backend.clinical.lexicons import (
    ABSENT_FINDINGS,
    AFFIRMING_POST,
    ALLERGY_ALIASES,
    ALLERGY_CUES,
    ALLERGY_POST,
    BRAND_TO_GENERIC,
    CERTAINTY_CUES,
    CERTAINTY_POST,
    CONFIRMING_CUES,
    CONFIRMING_POST,
    DENIED_ALLERGY_CUES,
    DIAGNOSES,
    DIAGNOSIS_ALIASES,
    DIFFERENTIAL_CUES,
    DOSE_FREQUENCIES,
    DOSE_UNITS,
    FINDING_ALIASES,
    FINDING_NEG_POST,
    FINDING_NEG_PRE,
    FINDINGS,
    FUNCTION_WORDS,
    GENERIC_DRUGS,
    INDICATION_CUES,
    MED_CONTINUE_CUES,
    MED_RESTART_CUES,
    MED_START_CUES,
    MED_START_POST,
    MED_STOP_CUES,
    MED_STOP_POST,
    NEGATION_WINDOW,
    PSEUDO_NEGATIONS,
    TERMINATORS,
)


class Dose(NamedTuple):
    value: float  # parsed, so "500mg TID" == "500 mg tid" (L33)
    unit: str  # canonical: "mg", "μg" (folded), "ml" ...
    freq: str | None  # the interval, canonical: "tid", "q6h", "daily" ... (L267)
    prn: bool = False  # as needed, beside any interval (L267)


MedStatus = Literal["active", "continued", "stopped"]  # continued: no interruption (L262)
Certainty = Literal["definite", "probable", "possible", "rule_out"]  # strongest first

# A decimal number whole, so "38.5" ends no sentence; a word; a line break; one mark.
_TOKEN = re.compile(r"\d+(?:\.\d+)+|[^\W_]+|\n|[^\w\s]")
# Curly single quotes read as the apostrophe, as §6.2's normalizer reads them (L170).
_APOSTROPHES = str.maketrans({"\u2018": "'", "\u2019": "'"})

type _Phrase = tuple[str, ...]
type _Label = Literal[
    "negated",
    "stopped",
    "started",
    "allergy",
    "denied",
    "probable",
    "possible",
    "rule_out",
    "indication",
    "confirmed",
]
type _Cues = Mapping[_Phrase, _Label]


def _tokens(text: str) -> list[str]:
    """text, casefolded, as tokens.

    A carriage return, alone or before a line feed, reads as one line break (L128). An
    underscore, like whitespace, only separates words (L123). A curly single quote reads as
    the apostrophe (L170).
    """
    text = text.casefold().translate(_APOSTROPHES)
    return _TOKEN.findall(text.replace("\r\n", "\n").replace("\r", "\n"))


def _phrases(entries: Iterable[str]) -> dict[_Phrase, str]:
    """Each lexicon entry under its tokens, so it matches the text as the text is split."""
    return {tuple(_tokens(entry)): entry for entry in entries}


def _cues(label: _Label, entries: Iterable[str]) -> dict[_Phrase, _Label]:
    """Each cue under its tokens, labeled with its class (L124)."""
    return {phrase: label for phrase in _phrases(entries)}


_PSEUDO = _phrases(PSEUDO_NEGATIONS)
_TERMINATORS = _phrases(TERMINATORS)
# every name a finding is charted by: its own, an alias, or a word stating it absent (L173)
_FINDINGS = (
    _phrases(FINDINGS)
    | {tuple(_tokens(name)): name for name in FINDING_ALIASES}
    | {tuple(_tokens(word)): word for word in ABSENT_FINDINGS}
)
# the tokens of the words that state their finding absent: a span of them alone is a
# statement, as NKDA is (L174)
ABSENCE_WORDS = frozenset(token for word in ABSENT_FINDINGS for token in _tokens(word))
_NEG_PRE = _cues("negated", FINDING_NEG_PRE)
_NEG_POST = _cues("negated", FINDING_NEG_POST)
# what takes a negated list's second mention back out of its window (L291)
_AFFIRM_POST = _phrases(AFFIRMING_POST)
# every name a listed drug is charted by, under the generic it means (L126), and every
# allergen name under the class or statement it means (L129)
_DRUGS = _phrases(GENERIC_DRUGS) | {
    tuple(_tokens(name)): drug for name, drug in BRAND_TO_GENERIC.items()
}
# what opens an indication after a drug (L266, L280)
_INDICATIONS = _phrases(INDICATION_CUES)
_NAMES = _DRUGS | {tuple(_tokens(name)): key for name, key in ALLERGY_ALIASES.items()}
_DRUG_PRE = (
    _NEG_PRE
    | _cues("stopped", MED_STOP_CUES)
    | _cues("started", MED_START_CUES)
    | _cues("allergy", ALLERGY_CUES)
    | _cues("denied", DENIED_ALLERGY_CUES)  # no allergen and no status (L290)
)
_DRUG_POST = (
    _NEG_POST
    | _cues("stopped", MED_STOP_POST)
    | _cues("started", MED_START_POST)
    | _cues("allergy", ALLERGY_POST)
)
# the statements of D10, allergy information that needs no allergy cue
NO_ALLERGY_STATEMENTS = frozenset({"nkda", "nka"})
# a header is up to this many words and a colon (L128)
_HEADER_WORDS = 3
# the negated mention an affirming post-cue takes back: the window's second (L291)
_AFFIRMED_MENTION = 2
# the words that join a list a post-cue reaches back over (L128, L193). A mark joins by
# default: only a word, a terminator, or a comma ends a run, so "/" and "&" join already.
_JOINS = frozenset({(",",), ("and",), ("or",)})
# the post-cue labels that reach back over a list only when it opens its clause (L193); an
# allergy post-cue reaches every list (L128), and a certainty post-cue none
_LIST_REACH: frozenset[_Label] = frozenset({"negated", "stopped", "started"})
# what opens a clause, besides the text's start and a header's colon (L193); a word, an
# affirming terminator such as "reports" included, opens none
_CLAUSE_STARTS = frozenset({(".",), (";",), ("\n",)})
# the label each certainty a lexicon names becomes; a value it lacks fails at import (L135)
_CERTAINTY: Mapping[str, _Label] = {
    "probable": "probable",
    "possible": "possible",
    "rule_out": "rule_out",
}


def _certainty_cues(table: Mapping[str, str]) -> dict[_Phrase, _Label]:
    """Each certainty cue under its tokens, labeled with the certainty it asserts (L135)."""
    return {tuple(_tokens(cue)): _CERTAINTY[certainty] for cue, certainty in table.items()}


_DIAGNOSES = _phrases(DIAGNOSES) | {
    tuple(_tokens(name)): diagnosis for name, diagnosis in DIAGNOSIS_ALIASES.items()
}
# every entity a header's first word may not name, across the families (L128, L193)
_ENTITIES = _NAMES | _FINDINGS | _DIAGNOSES
# a workup's answer reads its diagnosis definite, a repeat in a window among them (L292)
_DX_PRE = _NEG_PRE | _certainty_cues(CERTAINTY_CUES) | _cues("confirmed", CONFIRMING_CUES)
_DX_POST = _NEG_POST | _certainty_cues(CERTAINTY_POST) | _cues("confirmed", CONFIRMING_POST)
_DIFFERENTIAL = _certainty_cues(DIFFERENTIAL_CUES)
_NO_CUES: _Cues = {}
_UNITS = {tuple(_tokens(name)): unit for name, unit in DOSE_UNITS.items()}
_FREQUENCIES = {tuple(_tokens(name)): freq for name, freq in DOSE_FREQUENCIES.items()}
# a number, and any letters fused to it ("500mg"); a decimal is one token already (L121)
_NUMBER = re.compile(r"(\d+(?:\.\d+)?)([^\W\d_]*)")


def _is_word(token: str) -> bool:
    return token[0].isalnum()


def _split(
    tokens: Sequence[str], tables: Sequence[Collection[_Phrase]]
) -> Iterator[tuple[int, _Phrase]]:
    """tokens as phrases, left to right, each with its first token's index: the longest
    phrase a table holds, else one token."""
    most = max(len(phrase) for table in tables for phrase in table)
    i = 0
    while i < len(tokens):
        phrase: _Phrase = (tokens[i],)
        for n in range(most, 1, -1):
            if any(tuple(tokens[i : i + n]) in table for table in tables):
                phrase = tuple(tokens[i : i + n])
                break
        yield i, phrase
        i += len(phrase)


def _is_header(
    tokens: Sequence[str], j: int, at: Mapping[int, _Phrase], entities: Collection[_Phrase]
) -> bool:
    """Whether a header starts at token j: up to three words and a colon, the first naming
    no entity (L128). Where one may start, a line's start or a period, is the caller's."""
    k = j
    while k < len(tokens) and k - j < _HEADER_WORDS and _is_word(tokens[k]):
        k += 1
    return j < k < len(tokens) and tokens[k] == ":" and at.get(j) not in entities


def _header_ends_at(
    tokens: Sequence[str], k: int, at: Mapping[int, _Phrase], entities: Collection[_Phrase]
) -> bool:
    """Whether the colon at token k ends a header that starts a line or follows a period."""
    j = k
    while j > 0 and k - j < _HEADER_WORDS and _is_word(tokens[j - 1]):
        j -= 1
    return (j == 0 or tokens[j - 1] in ("\n", ".")) and _is_header(tokens, j, at, entities)


def _sections(
    tokens: Sequence[str],
    phrases: Sequence[tuple[int, _Phrase]],
    entities: Collection[_Phrase],
    pre: _Cues,
) -> set[int]:
    """The token indices inside an allergy section (L128).

    An allergy cue ending in a colon, at a line's start, opens a section. It runs to a blank
    line, or to the next header (up to three words and a colon, the first naming no entity)
    at a line's start or after a period.
    """
    starts = {
        i
        for i, phrase in phrases
        if pre.get(phrase) == "allergy" and phrase[-1] == ":" and (i == 0 or tokens[i - 1] == "\n")
    }
    if not starts:
        return set()
    at = dict(phrases)
    inside: set[int] = set()
    open_ = False
    for i, token in enumerate(tokens):
        if i in starts:
            open_ = True
        elif open_ and token == "\n" and tokens[i + 1 : i + 2] == ["\n"]:
            open_ = False
        elif (
            open_
            and token in ("\n", ".")
            and i + 1 not in starts
            and _is_header(tokens, i + 1, at, entities)
        ):
            open_ = False
        if open_:
            inside.add(i)
    return inside


class _Scoped(NamedTuple):
    tokens: list[str]
    phrases: list[tuple[int, _Phrase]]
    mentions: list[tuple[str, _Label | None]]
    starts: list[int]  # each mention's first token
    governing: set[int]  # the first token of each cue that governs a mention
    refused: set[int]  # the first token of each terminator a negation refuses (L288)


def _scope(
    text: str,
    entities: Mapping[_Phrase, str],
    pre: _Cues,
    post: _Cues,
    differential: _Cues = _NO_CUES,
    drugs: Collection[_Phrase] = (),
) -> list[tuple[str, _Label | None]]:
    """Each entity mention in text, in order, with the label of the cue that governs it, or
    None if none does (L31, L121, L122, L124, L128, L135, L193, L265, L266, L271, L280, L288,
    L290-L292).
    """
    return _scope_at(text, entities, pre, post, differential, drugs).mentions


def _scope_at(
    text: str,
    entities: Mapping[_Phrase, str],
    pre: _Cues,
    post: _Cues,
    differential: _Cues = _NO_CUES,
    drugs: Collection[_Phrase] = (),
) -> _Scoped:
    """_scope's reading, with where each mention starts and which cues govern one. Given the
    drugs' names, an indication cue after one in its clause opens an indication (L266, L280).
    """
    tokens = _tokens(text)
    tables = (
        _PSEUDO,
        _TERMINATORS,
        entities,
        pre,
        post,
        differential,
        drugs,
        _INDICATIONS,
        _AFFIRM_POST,
    )
    phrases = list(_split(tokens, tables))
    sections = _sections(tokens, phrases, entities, pre)
    at = dict(phrases)
    mentions: list[tuple[str, _Label | None]] = []
    starts: list[int] = []
    governing: set[int] = set()
    refused: set[int] = set()
    window = 0  # the words the open pre-cue still governs
    label: _Label | None = None  # the open pre-cue's class
    opener = 0  # the open pre-cue's first token
    refusing = False  # a negation pre-cue, or a refused stop, with only function words since
    stop_list = False  # the open refusal is a refused stop's, which a list's marks carry on
    before: int | None = None  # the mention immediately before, past any mark but a comma
    run: list[int] = []  # the mentions a list joins, ending at `before` (L128)
    clause_open = True  # no word yet since the clause opened: a list starting here is bare
    run_bare = False  # the open run began its clause (L193)
    drug_named = False  # a drug named since the clause opened (L266)
    indicating = False  # the list right after an indication cue is open (L280)
    allergy_run: list[int] = []  # the mentions the allergy cue just before governs (L290)
    pre_comma = False  # a comma since the open pre-cue (L290)
    pre_joined = False  # an "and" or "or" since the open pre-cue (L291)
    pre_read = 0  # the mentions the open pre-cue's window has read negated (L291)
    for i, phrase in phrases:
        words = sum(map(_is_word, phrase))
        in_window = window > 0
        window = max(window - words, 0)
        stop_refused = False
        if phrase in _TERMINATORS:
            window = 0
            if refusing:  # L288: "do not continue" is a stop, which _med_readings reads
                refused.add(i)
        elif phrase in differential:  # both sides: the mention before, unless governed, and after
            # a confirming cue asserts what a bare mention does, so it governs nothing here
            # ("CT shows PE vs atelectasis") (L302)
            if before is not None and mentions[before][1] in (None, "confirmed"):
                mentions[before] = (mentions[before][0], differential[phrase])
                governing.add(i)
            window, label, opener = NEGATION_WINDOW, differential[phrase], i
        elif phrase in _AFFIRM_POST and before is not None:
            # L291: "present" after the second mention a negation reads, across a comma and no
            # "and" or "or", takes it back ("No fever, chills present")
            if (
                mentions[before][1] == "negated"
                and pre_comma
                and not pre_joined
                and pre_read == _AFFIRMED_MENTION
            ):
                mentions[before] = (mentions[before][0], None)
                governing.add(i)
        elif phrase in post and post[phrase] == "negated" and allergy_run:
            # L290: a negation post-cue directly after an allergy cue denies its allergens
            for m in allergy_run:
                mentions[m] = (mentions[m][0], "denied")
            governing.add(i)
        elif phrase in post and before is not None:  # tested ahead of pre, per L121
            cue = post[phrase]
            listed = cue == "allergy" or (cue in _LIST_REACH and run_bare)
            reach = run if listed else [before]
            denied = False
            for m in reach:  # a list's earlier mentions only where no other cue governs
                if cue == "allergy" and mentions[m][1] == "negated" and not pre_comma:
                    # L290: a negation with no comma before the allergy cue denies it, and
                    # the denial ends the negation's window
                    mentions[m] = (mentions[m][0], "denied")
                    denied = True
                elif m == before or mentions[m][1] is None:
                    mentions[m] = (mentions[m][0], cue)
            if cue == "allergy":
                allergy_run = [m for m in reach if mentions[m][1] == "allergy"]
            if denied:
                window = 0
            governing.add(i)
        elif phrase in pre:
            if pre[phrase] == "allergy" and phrase[-1] == ":" and before is not None:
                # L277: before its colon, "allergy:" reads as the post-cue it ends with,
                # reaching back over the run where no other cue governs (L128)
                for m in run:
                    if m == before or mentions[m][1] is None:
                        mentions[m] = (mentions[m][0], "allergy")
                allergy_run = [m for m in run if mentions[m][1] == "allergy"]  # L290
                governing.add(i)
            # L271, L288: a start or stop a negation directly precedes is refused ("Not
            # starting metformin", "Do not hold apixaban"). A refused start is negated; a
            # refused stop closes the window, so the drug reads as charted. Past a content word
            # or a mark, either replaces the window, as any pre-cue does (L124)
            if refusing and pre[phrase] == "stopped":
                window = 0
                stop_refused = True
            else:
                negated = refusing and pre[phrase] == "started"
                window, label, opener = NEGATION_WINDOW, "negated" if negated else pre[phrase], i
                pre_comma = pre_joined = False
                pre_read = 0
        elif phrase in entities:
            entity = entities[phrase]
            # L292: a window keeps a repeat; a confirming cue answers a certainty's workup
            governing_label = label if in_window else "allergy" if i in sections else None
            if indicating:  # L266: why the drug is given, not a finding the note asserts
                governing_label = "indication"
            if in_window:
                governing.add(opener)
            mentions.append((entity, governing_label))
            if governing_label == "negated":
                pre_read += 1
            starts.append(i)
        # adjacency: a mention opens it; a word, a terminator, or a comma ends it (L122). A
        # list's run survives a join and a mark, and ends where adjacency ends otherwise.
        if phrase in entities:
            allergy_run = []  # a mention between the allergy cue and a negation ends it (L290)
            before = len(mentions) - 1
            if not run:
                run_bare = clause_open
            run.append(before)
        elif words or phrase in _TERMINATORS or phrase == (",",):
            before = None
            if phrase not in _JOINS:
                run = []
            if post.get(phrase) != "allergy" and not (
                pre.get(phrase) == "allergy" and phrase[-1] == ":"
            ):
                allergy_run = []  # an allergy cue's allergens stay open across marks alone
        if phrase == (",",):
            pre_comma = True
        elif phrase in _JOINS:
            pre_joined = True
        # L193: a clause opens after . ; or a line break, or after a header's colon (a header
        # at a line's start or after a period); any word closes it
        if phrase in _CLAUSE_STARTS or (
            phrase == (":",) and _header_ends_at(tokens, i, at, entities)
        ):
            clause_open = True
            drug_named = False
        elif words:
            clause_open = False
        # L280: an indication is the list right after its cue, findings, joins, and marks, as
        # a run reaches (L193); any other word or a terminator ends it
        if phrase in drugs:
            drug_named = True
        if phrase in _INDICATIONS and drug_named:
            indicating = True
        elif phrase not in entities and phrase not in _JOINS and (words or phrase in _TERMINATORS):
            indicating = False
        if (phrase in pre and pre[phrase] == "negated") or stop_refused:
            refusing = True  # a refused stop refuses a stop joined after it (L288)
            stop_list = stop_refused
        elif stop_list and not words and phrase not in _TERMINATORS:
            pass  # "Do not stop/hold apixaban": a mark joins the refused stops, as in a run
        elif not (words and all(token in FUNCTION_WORDS for token in phrase)):
            refusing = stop_list = False
    _allergy_lists(phrases, entities, post, mentions, starts)
    return _Scoped(tokens, phrases, mentions, starts, governing, refused)


# what opens the list an allergy post-cue governs right after it (L264): a parenthesis, a
# hyphen, or an en dash
_ALLERGY_LIST_OPENERS = frozenset({("(",), ("-",), ("–",)})


def _allergy_lists(
    phrases: Sequence[tuple[int, _Phrase]],
    entities: Mapping[_Phrase, str],
    post: _Cues,
    mentions: list[tuple[str, _Label | None]],
    starts: Sequence[int],
) -> None:
    """L264: "PCN allergy (amoxicillin)" and "PCN allergy - amoxicillin" make both drugs
    allergens. After a mention an allergy post-cue governs, a list in parentheses, or after a
    dash to its clause's end, reads as allergens when it holds mentions and joins alone: a
    reaction ("(hives)"), a dose, or any other word leaves it as it reads, since reading a
    planned drug as an allergen would hide it from every drug check. The colon form ("PCN
    allergy: amoxicillin") is the scope engine's (L277). Labels mentions in place."""
    at = {start: k for k, start in enumerate(starts)}
    for n, (_, phrase) in enumerate(phrases):
        before = at.get(phrases[n - 1][0]) if n and phrases[n - 1][1] in entities else None
        if before is None:
            continue
        if post.get(phrase) != "allergy":
            continue
        if n + 1 == len(phrases) or phrases[n + 1][1] not in _ALLERGY_LIST_OPENERS:
            continue
        close = (")",) if phrases[n + 1][1] == ("(",) else None
        listed: list[int] = []
        for i, item in phrases[n + 2 :]:
            if item == close or item in _CLAUSE_STARTS:
                break
            if item in entities:
                listed.append(at[i])
            elif item not in _JOINS:
                listed = []  # not a list of allergens: leave every mention as it reads
                break
        for m in listed:
            mentions[m] = (mentions[m][0], "allergy")


def _drug_mentions(text: str) -> list[tuple[str, _Label | None]]:
    """Each drug and allergen mention in text, with the label of the cue that governs it."""
    return _scope(text, _NAMES, _DRUG_PRE, _DRUG_POST)


# what each label asserts: a started drug is active and a negated one isn't taken (L124); an
# allergen asserts no status at all (L128), so "allergy" has no entry
_STATUS: Mapping[_Label | None, MedStatus] = {
    None: "active",
    "started": "active",
    "stopped": "stopped",
    "negated": "stopped",
}


def extract_drugs(text: str) -> set[str]:
    """Generic names mentioned as active, brand->generic (L126): each drug with an active
    mention. Negated and stopped mentions are not active ones, and an allergen is no
    medication (L128)."""
    return {drug for drug, statuses in extract_med_status(text).items() if "active" in statuses}


# L262, L274: a restart that is also a start post-cue is done ("restarted", "was resumed");
# one that is only a start pre-cue is planned ("resume")
_RESTARTS = set(_phrases(MED_RESTART_CUES))
_RESTARTS_DONE = _RESTARTS & set(_phrases(MED_START_POST))
_CONTINUES = _phrases(MED_CONTINUE_CUES)


def _clauses(scoped: _Scoped) -> list[int]:
    """Each token's clause, numbered from 0: L193's clauses, which open after . ; or a line
    break, or after a header's colon."""
    at = dict(scoped.phrases)
    clause, clauses = 0, []
    for k, token in enumerate(scoped.tokens):
        clauses.append(clause)
        if (token,) in _CLAUSE_STARTS or (
            token == ":" and _header_ends_at(scoped.tokens, k, at, _NAMES)
        ):
            clause += 1
    return clauses


def _med_readings(text: str) -> list[tuple[str, set[MedStatus]]]:
    """Each drug mention in text with the statuses it asserts (D13, L124, L262).

    A mention asserts its governing cue's status. Then a restart or resumption cue that
    governs no mention reaches the nearest drug before it in its clause that reads stopped:
    done, it replaces the stop; planned, it adds active beside it. A continue cue asserts
    continued, beside active, for the drug directly before it (L273), else for the drug in its
    window, else for the drug before it when the cue ends its clause. A mention in allergy
    context asserts nothing (L128).
    """
    scoped = _scope_at(text, _NAMES, _DRUG_PRE, _DRUG_POST)
    clauses = _clauses(scoped)
    readings: list[tuple[str, set[MedStatus]]] = [
        (drug, {_STATUS[label]} if drug in GENERIC_DRUGS and label in _STATUS else set())
        for drug, label in scoped.mentions
    ]
    drugs = [k for k, (drug, statuses) in enumerate(readings) if statuses]

    def before(i: int) -> list[int]:  # the drug mentions before token i, in its clause
        return [
            k for k in drugs if scoped.starts[k] < i and clauses[scoped.starts[k]] == clauses[i]
        ]

    for n, (i, phrase) in enumerate(scoped.phrases):
        if phrase in _RESTARTS and i not in scoped.governing:
            stopped = [k for k in before(i) if "stopped" in readings[k][1]]
            if stopped:
                statuses = readings[stopped[-1]][1]
                if phrase in _RESTARTS_DONE:
                    statuses.discard("stopped")
                statuses.add("active")
        elif phrase in _CONTINUES:
            # directly after a drug it is that drug's, as any post-cue is (L122, L273); else
            # it governs its window, or the drug before it when it ends its clause (L262)
            target = _adjacent(scoped, drugs, n) or _continued(scoped, clauses, drugs, n)
            if not target and _ends_clause(scoped, clauses, n):
                target = before(i)[-1:]
            for k in target:
                if i in scoped.refused:  # L288: a refused continue is a stop
                    readings[k][1].clear()
                    readings[k][1].add("stopped")
                else:
                    readings[k][1].update(("active", "continued"))
    return readings


def _adjacent(scoped: _Scoped, drugs: list[int], n: int) -> list[int]:
    """The drug mention immediately before the cue at phrases[n], across any mark but a
    comma (L122), as a list of at most one."""
    for j, phrase in reversed(scoped.phrases[:n]):
        if phrase in _NAMES:
            return [k for k in drugs if scoped.starts[k] == j]
        if any(map(_is_word, phrase)) or phrase == (",",) or phrase in _TERMINATORS:
            return []
    return []


def _continued(scoped: _Scoped, clauses: list[int], drugs: list[int], n: int) -> list[int]:
    """The drug mention in the window of the continue cue at phrases[n], as a list of at most
    one: within NEGATION_WINDOW words, in the cue's clause, before a terminator or a pre-cue."""
    i = scoped.phrases[n][0]
    words = 0
    for j, phrase in scoped.phrases[n + 1 :]:
        if clauses[j] != clauses[i] or phrase in _TERMINATORS or phrase in _DRUG_PRE:
            return []
        if phrase in _NAMES:
            return [k for k in drugs if scoped.starts[k] == j]
        words += sum(map(_is_word, phrase))
        if words >= NEGATION_WINDOW:
            return []
    return []


def _ends_clause(scoped: _Scoped, clauses: list[int], n: int) -> bool:
    """Whether no word follows the cue at phrases[n] in its clause."""
    i = scoped.phrases[n][0]
    return not any(
        _is_word(token)
        for j, token in enumerate(scoped.tokens)
        if j > i and clauses[j] == clauses[i]
    )


def extract_med_status(text: str) -> dict[str, set[MedStatus]]:
    """drug -> the statuses asserted for it (D13).

    "apixaban 5 mg" -> {"active"}; "continue apixaban" -> {"active", "continued"} (L262);
    "discontinue apixaban" -> {"stopped"}. A negated mention is stopped: "not on apixaban"
    asserts the drug isn't taken (L124). A mention in allergy context asserts no status
    (L128).
    """
    statuses: dict[str, set[MedStatus]] = {}
    for drug, asserted in _med_readings(text):
        if asserted:
            statuses.setdefault(drug, set()).update(asserted)
    return statuses


def new_prescriptions(text: str) -> set[str]:
    """Drugs started at this visit: the mentions a start cue governs, before or after the drug
    (L41, L125). "mom takes metformin" and "tried ibuprofen last year" name no start."""
    mentions = _drug_mentions(text)
    return {drug for drug, label in mentions if label == "started" and drug in GENERIC_DRUGS}


def extract_allergies(text: str) -> set[str]:
    """Allergens, normalized: brand->generic, aliases resolved ("PCN" -> "penicillin") (L30).

    A key is a generic drug ("amoxicillin"), a class ("penicillin", "sulfa", "nsaid"),
    "nkda", or "nka" (D10). A mention is an allergen where allergy context governs it
    (L128), unless a negation denies it (L290); "nkda" and "nka" are allergy statements
    wherever they aren't negated (L129).
    """
    return {
        name
        for name, label in _drug_mentions(text)
        if label == "allergy" or (name in NO_ALLERGY_STATEMENTS and label != "negated")
    }


def _number_at(phrases: Sequence[_Phrase], i: int) -> tuple[str, str | None, int] | None:
    """The number that starts at phrases[i]: its digits, the unit fused to it or written after
    it (None if neither), and how many phrases it spans; None if no number starts there. A
    thousands comma joins, with or without a unit fused to the last group ("1,000mg")."""
    number = _NUMBER.fullmatch(phrases[i][0]) if len(phrases[i]) == 1 else None
    if number is None:
        return None
    digits, fused = number.groups()
    width = 1
    while not fused and (group := _thousands(phrases[i + width : i + width + 2])) is not None:
        digits += group.group(1)
        fused = group.group(2)
        width += 2
    if fused:
        return digits, _UNITS.get((fused,)), width
    unit = _UNITS.get(phrases[i + width]) if i + width < len(phrases) else None
    return digits, unit, width if unit is None else width + 1


def _thousands(pair: Sequence[_Phrase]) -> re.Match[str] | None:
    """After a thousands comma, its three digits and any letters fused to them; else None."""
    if len(pair) != 2 or pair[0] != (",",) or len(pair[1]) != 1:
        return None
    group = _NUMBER.fullmatch(pair[1][0])
    return (
        group
        if group is not None and len(group.group(1)) == 3 and group.group(1).isdecimal()
        else None
    )


def _dose_at(phrases: Sequence[_Phrase], i: int) -> tuple[float, str, int] | None:
    """The dose that starts at phrases[i] (L133): its value, its unit, and how many phrases it
    spans; None if none starts there. Neither number of a range is a dose: a hyphen joins one
    whether or not its numbers carry units ("5-10 mg", "5mg-10mg"), and "to" joins one only
    after a number without a unit ("5 to 10 mg"), since "from 500 mg to 1000 mg" is a
    titration."""
    number = _number_at(phrases, i)
    if number is None:
        return None
    digits, unit, width = number
    if unit is None:
        return None
    first = _number_at(phrases, i - 2) if i >= 2 else None
    ends = i >= 2 and (
        (phrases[i - 1] == ("-",) and (first is not None or phrases[i - 2] in _UNITS))
        or (phrases[i - 1] == ("to",) and first is not None and first[1] is None)
    )
    second = _number_at(phrases, i + width + 1) if i + width + 1 < len(phrases) else None
    starts = (
        phrases[i + width : i + width + 1] == [("-",)]
        and second is not None
        and second[1] is not None
    )
    if ends or starts:
        return None
    return float(digits), unit, width


def extract_doses(text: str) -> dict[str, set[Dose]]:
    """drug -> parsed doses. A set, so a titration keeps both (D1, L33).

    A dose belongs to the most recent drug before it in the same sentence, whatever that
    mention's status, and takes the first interval charted after its unit before the next
    dose, drug, or terminator (L133); a prn in that reach sets its prn, beside any interval
    (L267).
    """
    phrases = [p for _, p in _split(_tokens(text), (_TERMINATORS, _NAMES, _UNITS, _FREQUENCIES))]
    doses: dict[str, set[Dose]] = {}
    drug: str | None = None  # the most recent drug in this sentence
    pending: tuple[str, float, str] | None = None  # a dose still reaching for its frequency
    freq: str | None = None  # the first interval charted in the pending dose's reach
    prn = False  # a prn charted in the pending dose's reach (L267)

    def settle() -> None:
        nonlocal pending, freq, prn
        if pending is not None:
            name, value, unit = pending
            doses.setdefault(name, set()).add(Dose(value, unit, freq, prn))
        pending, freq, prn = None, None, False

    i = 0
    while i < len(phrases):
        phrase = phrases[i]
        if phrase in _FREQUENCIES and pending is not None:
            if _FREQUENCIES[phrase] == "prn":
                prn = True
            elif freq is None:
                freq = _FREQUENCIES[phrase]
        elif phrase in _TERMINATORS:
            settle()
            drug = None
        elif _NAMES.get(phrase) in GENERIC_DRUGS:
            settle()
            drug = _NAMES[phrase]
        elif (dose := _dose_at(phrases, i)) is not None:
            settle()
            value, unit, width = dose
            pending = None if drug is None else (drug, value, unit)
            i += width
            continue
        i += 1
    settle()
    return doses


# what each label asserts of a diagnosis: no cue is a definite one, and a negated one isn't
# asserted at all, so "negated" has no entry (L135)
_ASSERTED: Mapping[_Label | None, Certainty] = {
    None: "definite",
    "confirmed": "definite",  # a workup's answer (L292)
    "probable": "probable",
    "possible": "possible",
    "rule_out": "rule_out",
}


def extract_diagnoses(text: str) -> dict[str, set[Certainty]]:
    """diagnosis -> certainties asserted (D12). "r/o PE" -> {"pulmonary embolism": {"rule_out"}}.

    Names resolve to their canonical diagnosis (L134). A diagnosis no cue governs is definite,
    and a negated one ("PE ruled out") isn't asserted (L135).
    """
    certainties: dict[str, set[Certainty]] = {}
    for diagnosis, label in _scope(text, _DIAGNOSES, _DX_PRE, _DX_POST, _DIFFERENTIAL):
        if label in _ASSERTED:
            certainties.setdefault(diagnosis, set()).add(_ASSERTED[label])
    return certainties


def extract_excluded_diagnoses(text: str) -> set[str]:
    """The diagnoses text excludes. "PE ruled out" -> {"pulmonary embolism"} (L140).

    extract_diagnoses' sibling: the negated mentions it drops, so a check can see an exclusion.
    One statement can both rule a diagnosis out and exclude it.
    """
    return {
        diagnosis
        for diagnosis, label in _scope(text, _DIAGNOSES, _DX_PRE, _DX_POST, _DIFFERENTIAL)
        if label == "negated"
    }


def extract_findings(text: str) -> dict[str, set[bool]]:
    """finding -> polarities asserted. "denies chest pain" -> {"chest pain": {False}}.

    Scoped negation (L31, L121, L122). A set, so a mixed statement keeps both (L33). An alias
    reads as its findings at its cue's polarity; a word stating its finding absent reads
    absent under any cue (L173). An indication ("for fever" after a drug) is no finding
    (L266, L280).
    """
    polarities: dict[str, set[bool]] = {}
    for name, label in _scope(text, _FINDINGS, _NEG_PRE, _NEG_POST, drugs=_DRUGS):
        if label == "indication":
            continue
        if name in ABSENT_FINDINGS:
            polarities.setdefault(ABSENT_FINDINGS[name], set()).add(False)
            continue
        for finding in FINDING_ALIASES.get(name, (name,)):
            polarities.setdefault(finding, set()).add(label is None)
    return polarities


def clause_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    """[start, end) widened to the clauses it touches in text (L193, L261, L275).

    A clause opens at the text's start and after a period, a semicolon, a line break, or a
    header's colon, as the scope engine reads one; a decimal's point opens none. The bounds
    leave the opening and closing marks out, but never cut into [start, end).
    """
    # not _tokens: casefolding the whole text ("ß" to "ss") or folding "\r\n" to one break
    # would move offsets. A lone "\r" becomes a break in place, each token is casefolded
    # after its offsets are taken, and curly apostrophes stay as written, which only a
    # header's first word could notice.
    found = list(_TOKEN.finditer(text.replace("\r", "\n")))
    tokens = [match.group().casefold() for match in found]
    at = dict(_split(tokens, (_PSEUDO, _TERMINATORS, _ENTITIES)))
    opens = [
        found[k]
        for k, token in enumerate(tokens)
        if (token,) in _CLAUSE_STARTS
        or (token == ":" and _header_ends_at(tokens, k, at, _ENTITIES))
    ]
    first = max((match.end() for match in opens if match.end() <= start), default=0)
    last = min((match.start() for match in opens if match.end() >= end), default=len(text))
    return first, max(last, end)


def content_tokens(text: str) -> list[str]:
    """text's words, numbers included, less FUNCTION_WORDS, in order (§8.4, D15, L160)."""
    return [token for token in _tokens(text) if _is_word(token) and token not in FUNCTION_WORDS]
