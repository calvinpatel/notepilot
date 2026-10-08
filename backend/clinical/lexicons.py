"""Clinical knowledge as data (spec §7).

Imports nothing (invariant 13). Each definition here is headed by a clinical sign-off line,
and each entry carries its rationale on the line above it (L120).
"""

# Clinical sign-off: Calvin Patel, 2026-10-07.
FINDING_NEG_PRE: set[str] = {
    # The patient's own negative report, the standard HPI and ROS cue.
    "denies",
    # The charted past tense, written before the finding ("pt denied chest pain").
    "denied",
    # Bare absence ("no fever", "no evidence of effusion"), in history and exam alike.
    "no",
    # Clausal negation ("does not have chest pain"); "not only" is its pseudo-negation.
    "not",
    # Absence attached to a presentation ("presents without fever").
    "without",
    # ROS and results phrasing ("negative for fever, chills").
    "negative for",
}

# Clinical sign-off: Calvin Patel, 2026-10-07.
FINDING_NEG_POST: set[str] = {
    # ROS template order ("Chest pain: denied").
    "denied",
    # Exam order ("pedal edema absent").
    "absent",
    # Result order ("Murphy's sign negative").
    "negative",
    # The copula form, which would otherwise separate the cue from its finding.
    "was denied",
    # The copula form of "absent".
    "is absent",
    # Exam order ("chest pain not present").
    "not present",
}

# Clinical sign-off: Calvin Patel, 2026-10-07.
PSEUDO_NEGATIONS: set[str] = {
    # "No increase in pain" charts pain that hasn't worsened: the pain is present.
    "no increase",
    # "No decrease in pain" charts pain that persists: the pain is present.
    "no decrease",
    # "No change in chest pain" charts a stable symptom: the symptom is present.
    "no change",
    # "No worsening of chest pain" charts a symptom that holds steady: it is present.
    "no worsening",
    # "No improvement in chest pain" charts a symptom unresolved under treatment: it is present.
    "no improvement",
    # "Not only fever but also chills" asserts both.
    "not only",
}

# Clinical sign-off: Calvin Patel, 2026-10-07.
TERMINATORS: set[str] = {
    # Contrast: what follows is asserted on its own ("no fever, but reports cough").
    "but",
    # Contrast, as "but".
    "however",
    # Concession: what follows is asserted on its own.
    "although",
    # Clause boundary.
    ";",
    # Sentence boundary.
    ".",
    # Line boundary: templated ROS and exam lines carry one statement each, often unpunctuated.
    "\n",
    # Affirmation: a positive report starts here ("denies chest pain at rest, reports chest pain
    # on exertion").
    "reports",
    # Affirmation, as "reports": the ROS counterpart of "denies".
    "endorses",
    # ROS phrasing ("negative for fever, positive for cough").
    "positive for",
    # Exception: the excepted finding is present ("denies all symptoms except chest pain").
    "except",
}

# Clinical sign-off: Calvin Patel, 2026-10-07.
# Word tokens a pre-negation cue governs. A negated ROS list puts its cue at its head, so this
# bounds the list one cue can negate: "denies fever, chills, nausea, vomiting, diarrhea,
# headache, or chest pain" puts chest pain at word 8.
NEGATION_WINDOW: int = 8

# Clinical sign-off: Calvin Patel, 2026-10-07.
FINDINGS: set[str] = {
    # The pertinent negative an acute-chest-pain workup turns on.
    "chest pain",
    # Pain without a site ("no increase in pain"); a sited pain listed here matches as itself.
    "pain",
    # The pertinent negative of an infectious workup.
    "fever",
    # Fever's companion in an infectious ROS.
    "chills",
    # GI ROS.
    "nausea",
    # GI ROS, usually charted with nausea ("denies nausea or vomiting").
    "vomiting",
}
