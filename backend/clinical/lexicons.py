"""Clinical knowledge as data (spec §7).

Imports nothing (invariant 13). Each definition here is headed by a clinical sign-off line,
and each entry carries its rationale on the line above it (L120).
"""

# Clinical sign-off: Calvin Patel, 2026-10-08.
GENERIC_DRUGS: set[str] = {
    # An analgesic charted by brand ("Tylenol") as often as by name.
    "acetaminophen",
    # A penicillin: the allergy and cross-reactivity cases start from it.
    "amoxicillin",
    # The combination product, matched as one name ahead of "amoxicillin" alone.
    "amoxicillin-clavulanate",
    # D13's example: an anticoagulant whose continue/discontinue swap is the dangerous one.
    "apixaban",
    # §8.4's Tier 3 example: the drug a fabricated amoxicillin is read against.
    "azithromycin",
    # A cephalosporin: D9's cross-reactivity cases read it against a penicillin allergy.
    "cephalexin",
    # An NSAID charted by brand ("Advil", "Motrin") as often as by name.
    "ibuprofen",
    # §7's status example ("discontinue lisinopril"), and a common stop for ACE-inhibitor cough.
    "lisinopril",
    # A long-term home medication, the kind D17's continued-home-med row is about.
    "metformin",
}

# Clinical sign-off: Calvin Patel, 2026-10-08.
BRAND_TO_GENERIC: dict[str, str] = {
    # Acetaminophen's brand.
    "tylenol": "acetaminophen",
    # Acetaminophen's order abbreviation ("APAP 650 mg q6h prn").
    "apap": "acetaminophen",
    # Acetaminophen's international name, in notes written outside the US.
    "paracetamol": "acetaminophen",
    # Amoxicillin's brand.
    "amoxil": "amoxicillin",
    # §7's example: an Augmentin allergy is an amoxicillin-clavulanate allergy.
    "augmentin": "amoxicillin-clavulanate",
    # The combination's shorthand ("amox-clav 875 mg bid").
    "amox-clav": "amoxicillin-clavulanate",
    # The same shorthand, with a slash.
    "amox/clav": "amoxicillin-clavulanate",
    # The full name, with a slash where the generic has a hyphen.
    "amoxicillin/clavulanate": "amoxicillin-clavulanate",
    # Apixaban's brand, common in medication lists.
    "eliquis": "apixaban",
    # Azithromycin's brand.
    "zithromax": "azithromycin",
    # Azithromycin's five-day dose pack, charted as the drug ("start Z-Pak").
    "z-pak": "azithromycin",
    # Cephalexin's brand.
    "keflex": "cephalexin",
    # Ibuprofen's brand.
    "advil": "ibuprofen",
    # Ibuprofen's other common brand.
    "motrin": "ibuprofen",
    # Lisinopril's brand.
    "zestril": "lisinopril",
    # Lisinopril's other brand.
    "prinivil": "lisinopril",
    # Metformin's brand; "Glucophage XR" matches it too.
    "glucophage": "metformin",
}

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

# Clinical sign-off: Calvin Patel, 2026-10-08.
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
    # A continued order starts its own statement, so a stop's window can't reach its drug.
    "continue",
    # The charted past tense ("continued home lisinopril").
    "continued",
    # A resumed drug is active, as "continue" ("resume metformin tomorrow").
    "resume",
    # A refused stop is a continue order ("do not stop apixaban").
    "not stop",
    # As "not stop" ("do not discontinue apixaban").
    "not discontinue",
    # As "not stop" ("do not hold apixaban").
    "not hold",
}

# Clinical sign-off: Calvin Patel, 2026-10-07.
# Word tokens a pre-negation cue governs. A negated ROS list puts its cue at its head, so this
# bounds the list one cue can negate: "denies fever, chills, nausea, vomiting, diarrhea,
# headache, or chest pain" puts chest pain at word 8.
NEGATION_WINDOW: int = 8

# Clinical sign-off: Calvin Patel, 2026-10-08.
MED_STOP_CUES: set[str] = {
    # The stop order, written before the drug ("discontinue lisinopril").
    "discontinue",
    # The plain stop order ("stop metformin").
    "stop",
    # A temporary stop ("hold metoprolol for HR < 60").
    "hold",
    # Discontinue's abbreviation ("d/c lisinopril").
    "d/c",
    # A stop in progress ("stopping metformin").
    "stopping",
    # The charted past tense, written before the drug ("discontinued lisinopril").
    "discontinued",
    # The charted past tense of "stop" ("stopped metformin last week").
    "stopped",
    # The charted past tense of "hold" ("held metformin this morning").
    "held",
    # A refused start leaves the drug inactive, not started ("do not start metformin").
    "not start",
}

# Clinical sign-off: Calvin Patel, 2026-10-08.
MED_STOP_POST: set[str] = {
    # The common stop charting, after the drug ("lisinopril discontinued due to cough").
    "discontinued",
    # After the drug ("metformin stopped").
    "stopped",
    # After the drug ("metformin held for contrast").
    "held",
    # The copula form, which would otherwise separate the cue from its drug.
    "was discontinued",
    # The copula form of "stopped".
    "was stopped",
    # The copula form of "held".
    "was held",
}

# Clinical sign-off: Calvin Patel, 2026-10-08.
MED_START_CUES: set[str] = {
    # The plan verb of a start at this visit ("start metformin 500 mg daily").
    "start",
    # A start being made ("starting amoxicillin today").
    "starting",
    # As "start".
    "begin",
    # As "start".
    "initiate",
    # A prescription written at this visit ("prescribe amoxicillin").
    "prescribe",
    # The prescription abbreviation ("Rx: amoxicillin").
    "rx",
    # A drug restarted at this visit is started at this visit.
    "restart",
    # The charted past tense, written before the drug ("started apixaban for new AF").
    "started",
    # The charted past tense of "initiate".
    "initiated",
    # The charted past tense of "prescribe".
    "prescribed",
}

# Clinical sign-off: Calvin Patel, 2026-10-08.
MED_START_POST: set[str] = {
    # After the drug ("amoxicillin started for otitis").
    "started",
    # After the drug ("insulin initiated").
    "initiated",
    # After the drug ("azithromycin prescribed").
    "prescribed",
    # The copula form, which would otherwise separate the cue from its drug.
    "was started",
    # The copula form of "prescribed".
    "was prescribed",
}

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
