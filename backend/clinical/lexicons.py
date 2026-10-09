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

# Clinical sign-off: Calvin Patel, 2026-10-08.
ALLERGY_ALIASES: dict[str, str] = {
    # The class an unspecified penicillin allergy names (D14: "PCN allergy" is the common form).
    "penicillin": "penicillin",
    # The plural, as charted ("allergic to penicillins").
    "penicillins": "penicillin",
    # §7's example: the charted abbreviation.
    "pcn": "penicillin",
    # The sulfonamide-antibiotic class, as charted.
    "sulfa": "sulfa",
    # §7's example, spelled out.
    "sulfa drugs": "sulfa",
    # The class's formal name.
    "sulfonamides": "sulfa",
    # The NSAID class.
    "nsaid": "nsaid",
    # The plural, as charted ("NSAIDs: GI bleed").
    "nsaids": "nsaid",
    # No known drug allergies (D10).
    "nkda": "nkda",
    # §7's example, spelled out.
    "no known drug allergies": "nkda",
    # The same statement, without "known".
    "no drug allergies": "nkda",
    # §7's example: no known allergies, food and environmental included (D10).
    "nka": "nka",
    # NKA, spelled out.
    "no known allergies": "nka",
    # The same statement, without "known".
    "no allergies": "nka",
    # The template's way of charting NKA.
    "allergies: none": "nka",
}

# Clinical sign-off: Calvin Patel, 2026-10-08.
ALLERGY_CUES: set[str] = {
    # The patient's own report ("allergic to penicillin").
    "allergic to",
    # As charted ("allergy to sulfa").
    "allergy to",
    # The plural ("allergies to PCN and sulfa").
    "allergies to",
    # The template header; at a line's start it opens an allergy section (L128).
    "allergies:",
    # The singular header, likewise.
    "allergy:",
    # The header without its colon, inline ("Allergies PCN, sulfa").
    "allergies",
    # §7's example: an adverse reaction charted as one ("reaction to Augmentin").
    "reaction to",
}

# Clinical sign-off: Calvin Patel, 2026-10-08.
ALLERGY_POST: set[str] = {
    # §7's example: after the allergen ("PCN allergy", "Augmentin allergy").
    "allergy",
    # After a list, it reaches every allergen the list joins ("PCN and sulfa allergies").
    "allergies",
    # The short form after the allergen ("penicillin allergic").
    "allergic",
}

# Clinical sign-off: Calvin Patel, 2026-10-08.
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
    # A denied allergy: the drug named is no allergen ("not allergic to amoxicillin").
    "not allergic to",
    # As charted ("no allergy to cephalosporins").
    "no allergy to",
    # The patient's own denial ("denies allergy to penicillin").
    "denies allergy to",
    # As "no allergy to" ("no known allergy to sulfa").
    "no known allergy to",
    # A denied allergy, plural: the drug named is no allergen ("no allergies to penicillin").
    "no allergies to",
    # As "no allergies to" ("no known allergies to sulfa"); without it, the NKA alias matches.
    "no known allergies to",
    # The patient's own denial, plural ("denies allergies to NSAIDs").
    "denies allergies to",
}

# Clinical sign-off: Calvin Patel, 2026-10-08.
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
    # Excluded, after the diagnosis ("PE ruled out"), unlike "rule out PE", a plan to exclude.
    "ruled out",
    # The copula form of "ruled out".
    "was ruled out",
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
    # A held drug charted after it ("metformin on hold for contrast").
    "on hold",
    # Discontinue's abbreviation, charted after the drug ("lisinopril d/c'd").
    "d/c'd",
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

# Clinical sign-off: Calvin Patel, 2026-10-08.
CERTAINTY_CUES: dict[str, str] = {
    # §7's example: the commonest hedge ("likely pneumonia").
    "likely": "probable",
    # As "likely".
    "probable": "probable",
    # As "likely".
    "probably": "probable",
    # Treated as the working diagnosis, not yet confirmed ("presumed pneumonia").
    "presumed": "probable",
    # The prompt's own example: findings fit it, short of confirmation.
    "consistent with": "probable",
    # Under consideration, not yet favored ("suspected PE").
    "suspected": "possible",
    # §7's example.
    "possible": "possible",
    # As "possible".
    "possibly": "possible",
    # Raised as a possibility ("concern for PE").
    "concern for": "possible",
    # As "concern for".
    "concerning for": "possible",
    # As "possible" ("may have pneumonia").
    "may have": "possible",
    # Not excluded: a possibility, not a plan to exclude; longer than "rule out", so it wins.
    "cannot rule out": "possible",
    # §7's example: a diagnosis to be excluded ("r/o PE").
    "r/o": "rule_out",
    # Spelled out.
    "rule out": "rule_out",
}

# Clinical sign-off: Calvin Patel, 2026-10-08.
CERTAINTY_POST: dict[str, str] = {
    # After the diagnosis ("pneumonia likely").
    "likely": "probable",
    # After the diagnosis ("PE suspected").
    "suspected": "possible",
    # After the diagnosis ("pneumonia possible").
    "possible": "possible",
    # Not yet excluded; longer than the negation cue "not", so it wins.
    "not ruled out": "possible",
}

# Clinical sign-off: Calvin Patel, 2026-10-08.
DIFFERENTIAL_CUES: dict[str, str] = {
    # A differential: both sides are possibilities ("CAP vs PE") (L135).
    "vs": "possible",
    # With its period.
    "vs.": "possible",
    # Spelled out.
    "versus": "possible",
}

# Clinical sign-off: Calvin Patel, 2026-10-08.
DOSE_UNITS: dict[str, str] = {
    # Milligrams, the commonest oral dose unit.
    "mg": "mg",
    # Spelled out.
    "milligrams": "mg",
    # Grams ("ceftriaxone 1 g"), kept as grams: whether 1 g equals 1000 mg is 4c's call.
    "g": "g",
    # Spelled out.
    "gram": "g",
    # Spelled out, plural.
    "grams": "g",
    # Micrograms as charted ("levothyroxine 75 mcg"), folded to μg as §7's Dose does.
    "mcg": "μg",
    # The symbol; a micro sign casefolds to the same Greek mu.
    "μg": "μg",
    # The ASCII stand-in for μg.
    "ug": "μg",
    # Spelled out.
    "micrograms": "μg",
    # Milliliters, for liquids ("amoxicillin suspension 5 ml").
    "ml": "ml",
    # Spelled out.
    "milliliters": "ml",
    # Insulin and heparin units, spelled out; "U" is on ISMP's do-not-use list.
    "units": "unit",
    # The singular ("1 unit").
    "unit": "unit",
}

# Clinical sign-off: Calvin Patel, 2026-10-08.
DOSE_FREQUENCIES: dict[str, str] = {
    # Once a day.
    "daily": "daily",
    # As "daily".
    "once daily": "daily",
    # As "daily".
    "once a day": "daily",
    # Latin, on ISMP's do-not-use list and still charted.
    "qd": "daily",
    # As "daily".
    "every day": "daily",
    # Twice a day.
    "bid": "bid",
    # With its periods.
    "b.i.d.": "bid",
    # Spelled out.
    "twice daily": "bid",
    # Spelled out.
    "twice a day": "bid",
    # Three times a day.
    "tid": "tid",
    # With its periods.
    "t.i.d.": "tid",
    # Spelled out.
    "three times daily": "tid",
    # Spelled out.
    "three times a day": "tid",
    # Four times a day.
    "qid": "qid",
    # With its periods.
    "q.i.d.": "qid",
    # Spelled out.
    "four times daily": "qid",
    # At bedtime.
    "qhs": "qhs",
    # Spelled out.
    "at bedtime": "qhs",
    # Every 4 hours: an interval, kept apart from "qid", which follows waking hours.
    "q4h": "q4h",
    # Spelled out.
    "every 4 hours": "q4h",
    # Every 6 hours, kept apart from "qid" likewise.
    "q6h": "q6h",
    # Spelled out.
    "every 6 hours": "q6h",
    # Every 8 hours, kept apart from "tid" likewise.
    "q8h": "q8h",
    # Spelled out.
    "every 8 hours": "q8h",
    # As needed: the frequency only when no interval is charted with it (L133).
    "prn": "prn",
    # Spelled out.
    "as needed": "prn",
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

# Clinical sign-off: Calvin Patel, 2026-10-08.
DIAGNOSES: set[str] = {
    # D12's certainty trap: "r/o PE" written as "PE".
    "pulmonary embolism",
    # D7 and D12's invented-assessment trap: "BP 190/110" written as this.
    "hypertensive urgency",
    # The commonest hedged assessment ("likely pneumonia"), for D7's hedged control.
    "pneumonia",
}

# Clinical sign-off: Calvin Patel, 2026-10-08.
DIAGNOSIS_ALIASES: dict[str, str] = {
    # §7's example: PE as charted.
    "pe": "pulmonary embolism",
    # The singular clot.
    "pulmonary embolus": "pulmonary embolism",
    # As charted.
    "htn urgency": "hypertensive urgency",
    # Pneumonia's charted abbreviation.
    "pna": "pneumonia",
}
