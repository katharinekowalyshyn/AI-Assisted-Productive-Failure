"""
Misconception-detection harness.

The system slide claims "Misconception detection (F1 ≥ 0.75)" but the
production code at `backend/pf/service.py` always passes
`misconceptions=[]` to the analytics logger. This eval implements a
real heuristic detector and benchmarks it against silver-standard labels
extracted from the consolidation messages, which explicitly name the
underlying error.

Taxonomy (Spanish A1/A2):
  STUCK              -- student gave up or said 'I don't know'
  ENGLISH_INTRUSION  -- English content words in the Spanish attempt
  VOCABULARY         -- wrong content word for the target meaning
  VERB_CONJUGATION   -- wrong person/number/aspect on a verb
  GENDER_AGREEMENT   -- noun-adjective gender mismatch
  SER_VS_ESTAR       -- chose ser when estar (or vice versa)
  PREPOSITION        -- missing/wrong preposition (a, de, en, ...)
  REFLEXIVE          -- missing reflexive pronoun
  TENSE              -- wrong tense (e.g. preterite vs present vs imperfect)
  SUBJUNCTIVE        -- subjunctive required but indicative used

Pipeline:
  1. Build SILVER labels per problem by parsing the consolidation message
     for tag-specific keywords.
  2. Build PRED labels per problem by running the detector on the student
     attempts only (no consolidation visibility).
  3. Compute precision / recall / F1 per tag, plus micro and macro F1.

Only problems that triggered a consolidation are scored (that's the only
place silver labels are obtainable).
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import asdict, dataclass

from data_loader import Problem, Session, load_sessions


TAGS = (
    "STUCK",
    "ENGLISH_INTRUSION",
    "VOCABULARY",
    "VERB_CONJUGATION",
    "GENDER_AGREEMENT",
    "SER_VS_ESTAR",
    "PREPOSITION",
    "REFLEXIVE",
    "TENSE",
    "SUBJUNCTIVE",
)


# ---------------------------------------------------------------------------
# Silver-label extraction (from consolidation text)
# ---------------------------------------------------------------------------

_SILVER_PATTERNS: dict[str, list[str]] = {
    "STUCK": [r"don[' ]?t know", r"give up", r"no idea", r"unsure"],
    "VOCABULARY": [
        r"\b(means|word for|vocabulary|wrong word|incorrect (word|term))\b",
        r"\bequipo\b.*\bteam\b",
    ],
    "VERB_CONJUGATION": [
        r"conjugat", r"first person", r"third person", r"agreement.*verb",
    ],
    "GENDER_AGREEMENT": [
        r"\bgender\b", r"masculin", r"feminin", r"\b(el|la|los|las)\b.*agree",
    ],
    "SER_VS_ESTAR": [
        r"\bser\b.*\bestar\b", r"\bestar\b.*\bser\b", r"ser vs estar",
    ],
    "PREPOSITION": [
        r"\bpreposition\b",
        r"\bneed (the )?(a|de|en|al|del)\b",
        r"\buse (a|de|en)\b before",
    ],
    "REFLEXIVE": [r"reflexive"],
    "TENSE": [
        r"preterite", r"past tense", r"imperfect", r"present tense", r"\btense\b",
        r"future tense",
    ],
    "SUBJUNCTIVE": [r"subjunctive"],
    "ENGLISH_INTRUSION": [
        r"english word", r"in english", r"didn'?t translate",
    ],
}


def silver_labels_from_consolidation(consolidation: str) -> set[str]:
    if not consolidation:
        return set()
    text = consolidation.lower()
    out: set[str] = set()
    for tag, pats in _SILVER_PATTERNS.items():
        if any(re.search(p, text) for p in pats):
            out.add(tag)
    return out


def silver_labels_for_problem(p: Problem) -> set[str]:
    """
    STUCK is a meta-state visible in the attempts themselves; all other
    tags are derived from the consolidation message. We combine the two.
    """
    out = silver_labels_from_consolidation(p.consolidation or "")
    if any(_has_stuck(a) for a in p.student_attempts):
        out.add("STUCK")
    return out


# ---------------------------------------------------------------------------
# Predictor: heuristics over the raw student attempts
# ---------------------------------------------------------------------------

# Common English content words a Spanish A1/A2 learner might leak.
_ENGLISH_CONTENT = {
    "the", "is", "are", "was", "were", "store", "team", "book", "house",
    "school", "brother", "sister", "family", "spring", "summer", "winter",
    "fall", "autumn", "want", "go", "to", "have", "has", "do", "does",
    "i", "you", "we", "they", "she", "he", "it", "what", "how", "why",
    "no", "yes", "this", "that", "these", "those", "with", "without",
    "and", "or", "but",
}

_STUCK_TOKENS = ("i dont know", "i don't know", "no idea", "idk", "i give up")

_REFLEXIVE_VERBS = {
    "llamar": "llamarse",
    "levantar": "levantarse",
    "vestir": "vestirse",
    "lavar": "lavarse",
    "acostar": "acostarse",
    "sentir": "sentirse",
    "ir": "irse",
}

_PRETERITE_TRIGGERS = {
    "yesterday", "ayer", "last night", "anoche", "last week", "la semana pasada",
}

_SUBJUNCTIVE_TRIGGERS_EN = (
    "i hope", "i want him to", "i want her to", "tell him to", "tell her to",
    "before he", "until she", "so that",
)

_SER_ESTAR_TOKENS = ("soy", "eres", "es", "somos", "son", "estoy", "estas", "está", "estamos", "estan", "están")

_VERB_FORMS_PRESENT = {
    "hablo", "hablas", "habla", "hablamos", "hablan",
    "como", "comes", "come", "comemos", "comen",
    "vivo", "vives", "vive", "vivimos", "viven",
    "tengo", "tienes", "tiene", "tenemos", "tienen",
    "voy", "vas", "va", "vamos", "van",
    "quiero", "quieres", "quiere", "queremos", "quieren",
    "hago", "haces", "hace", "hacemos", "hacen",
}


def _has_english_intrusion(answer: str) -> bool:
    tokens = re.findall(r"[A-Za-z']+", answer.lower())
    if not tokens:
        return False
    english = sum(1 for t in tokens if t in _ENGLISH_CONTENT)
    return english >= 2 or (len(tokens) >= 3 and english / len(tokens) >= 0.5)


def _has_stuck(answer: str) -> bool:
    return any(tok in answer.lower() for tok in _STUCK_TOKENS)


def _has_gender_mismatch(answer: str) -> bool:
    """Very rough: 'el <noun-ending-in-a>' or 'la <noun-ending-in-o>'."""
    pairs = re.findall(r"\b(el|la|los|las)\s+([a-záéíóúñ]+)", answer.lower())
    for art, noun in pairs:
        if not noun:
            continue
        last = noun[-1]
        if art in ("el", "los") and last == "a" and noun not in {"problema", "tema", "mapa", "dia", "día"}:
            return True
        if art in ("la", "las") and last == "o" and noun not in {"foto", "moto", "mano"}:
            return True
    return False


def _has_ser_estar_collision(answer: str) -> bool:
    a = answer.lower()
    has_ser = any(re.search(rf"\b{w}\b", a) for w in ("soy", "eres", "es", "somos", "son"))
    has_estar = any(re.search(rf"\b{w}\b", a) for w in ("estoy", "estas", "está", "estamos", "están", "estan"))
    return has_ser and has_estar


def _missing_preposition(answer: str) -> bool:
    """Heuristic: 'voy/quiero ir <noun>' without 'a'."""
    a = answer.lower()
    if re.search(r"\b(quiero|voy|vamos|vas)\s+ir\b", a):
        if not re.search(r"\bir\s+(a|al|a la|a los|a las)\b", a):
            return True
    if re.search(r"\bvoy\b\s+(?!a\b)[a-z]+", a) and not re.search(r"\bvoy\s+a\b", a):
        return True
    return False


def _missing_reflexive(answer: str, problem_text: str) -> bool:
    a = answer.lower()
    p = (problem_text or "").lower()
    if "name" in p or "called" in p:
        if "llamo" in a or "llamas" in a or "llama" in a:
            if not re.search(r"\b(me|te|se|nos|os)\b", a):
                return True
    return False


def _wrong_tense(answer: str, problem_text: str) -> bool:
    a = answer.lower()
    p = (problem_text or "").lower()
    needs_preterite = any(trig in p for trig in _PRETERITE_TRIGGERS) or "yesterday" in p
    if needs_preterite:
        if any(v in a.split() for v in _VERB_FORMS_PRESENT):
            return True
    return False


def _missing_subjunctive(answer: str, problem_text: str) -> bool:
    a = answer.lower()
    p = (problem_text or "").lower()
    if any(trig in p for trig in _SUBJUNCTIVE_TRIGGERS_EN):
        # Indicative present forms appearing where subjunctive is needed.
        if any(v in a.split() for v in _VERB_FORMS_PRESENT):
            return True
    return False


def _has_vocabulary_error(answer: str) -> bool:
    """Crude: very short single-word 'guess' answers, or English content words used in place of Spanish."""
    tokens = answer.strip().split()
    if not tokens:
        return False
    if len(tokens) <= 2 and any(t.lower() in _ENGLISH_CONTENT for t in tokens):
        return True
    return False


def _has_verb_conjugation(answer: str) -> bool:
    """Very rough: detect 'yo <V-non-yo-form>' or 'el/ella <V-yo-form>' style mismatches."""
    a = answer.lower()
    if re.search(r"\byo\s+(hablas|habla|hablamos|hablan|comes|come|comemos|comen|vives|vive|vivimos|viven)\b", a):
        return True
    if re.search(r"\b(el|ella|usted)\s+(hablo|como|vivo|tengo|voy|quiero|hago)\b", a):
        return True
    if re.search(r"\b(nosotros|nosotras)\s+(hablo|hablas|habla|hablan)\b", a):
        return True
    return False


def predict_for_problem(p: Problem) -> set[str]:
    out: set[str] = set()
    problem_text = p.problem_text
    for ans in p.student_attempts:
        if _has_stuck(ans):
            out.add("STUCK")
        if _has_english_intrusion(ans):
            out.add("ENGLISH_INTRUSION")
        if _has_vocabulary_error(ans):
            out.add("VOCABULARY")
        if _has_gender_mismatch(ans):
            out.add("GENDER_AGREEMENT")
        if _has_ser_estar_collision(ans):
            out.add("SER_VS_ESTAR")
        if _missing_preposition(ans):
            out.add("PREPOSITION")
        if _missing_reflexive(ans, problem_text):
            out.add("REFLEXIVE")
        if _wrong_tense(ans, problem_text):
            out.add("TENSE")
        if _missing_subjunctive(ans, problem_text):
            out.add("SUBJUNCTIVE")
        if _has_verb_conjugation(ans):
            out.add("VERB_CONJUGATION")
    return out


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

@dataclass
class TagScore:
    tag: str
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return round(p, 3), round(r, 3), round(f, 3)


def evaluate(sessions: list[Session]) -> dict:
    pairs: list[tuple[set[str], set[str], dict]] = []
    for sess in sessions:
        for p in sess.problems:
            if not p.consolidated:
                continue
            silver = silver_labels_for_problem(p)
            pred = predict_for_problem(p)
            pairs.append(
                (
                    silver,
                    pred,
                    {
                        "session_id": sess.session_id,
                        "problem_index": p.problem_index,
                        "task_type": p.task_type,
                        "attempts": p.student_attempts,
                        "silver": sorted(silver),
                        "pred": sorted(pred),
                    },
                )
            )

    if not pairs:
        return {"n": 0}

    counts = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    for silver, pred, _meta in pairs:
        for tag in TAGS:
            in_silver = tag in silver
            in_pred = tag in pred
            if in_silver and in_pred:
                counts[tag]["tp"] += 1
            elif in_pred and not in_silver:
                counts[tag]["fp"] += 1
            elif in_silver and not in_pred:
                counts[tag]["fn"] += 1

    per_tag: list[TagScore] = []
    for tag in TAGS:
        c = counts[tag]
        p, r, f = _prf(c["tp"], c["fp"], c["fn"])
        per_tag.append(TagScore(tag, c["tp"], c["fp"], c["fn"], p, r, f))

    micro_tp = sum(c["tp"] for c in counts.values())
    micro_fp = sum(c["fp"] for c in counts.values())
    micro_fn = sum(c["fn"] for c in counts.values())
    micro_p, micro_r, micro_f = _prf(micro_tp, micro_fp, micro_fn)
    macro_f = round(
        sum(t.f1 for t in per_tag) / len(per_tag), 3
    ) if per_tag else 0.0

    return {
        "n": len(pairs),
        "tags": [asdict(t) for t in per_tag],
        "micro": {"precision": micro_p, "recall": micro_r, "f1": micro_f},
        "macro_f1": macro_f,
        "examples": [m for _s, _p, m in pairs[:8]],
    }


def render_markdown(result: dict) -> str:
    if not result.get("n"):
        return "## Misconception Detection\n\n_No consolidations available to label._"
    lines = ["## Misconception Detection", ""]
    lines.append(
        f"Heuristic detector evaluated against silver labels parsed from "
        f"consolidation messages on **{result['n']}** problems."
    )
    lines.append("")
    lines.append(
        f"- Micro-averaged F1: **{result['micro']['f1']}** "
        f"(P {result['micro']['precision']}, R {result['micro']['recall']})"
    )
    lines.append(f"- Macro-averaged F1: **{result['macro_f1']}**")
    lines.append("")
    lines.append("| Tag | TP | FP | FN | Precision | Recall | F1 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for t in result["tags"]:
        lines.append(
            f"| {t['tag']} | {t['tp']} | {t['fp']} | {t['fn']} | "
            f"{t['precision']} | {t['recall']} | {t['f1']} |"
        )
    target = 0.75
    macro_meets = result["macro_f1"] >= target
    micro_meets = result["micro"]["f1"] >= target
    lines.append("")
    lines.append(
        f"Target from system slide: **F1 ≥ 0.75**. "
        f"Micro F1 {'✓ meets' if micro_meets else '✗ misses'}, "
        f"Macro F1 {'✓ meets' if macro_meets else '✗ misses'} the bar."
    )
    return "\n".join(lines)


if __name__ == "__main__":
    sessions = load_sessions()
    out = evaluate(sessions)
    print(render_markdown(out))
