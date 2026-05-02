"""
PF Fidelity evaluator.

For every tutor *feedback* utterance during the struggle phase (i.e. before
consolidation fires), we check four rule-based criteria that operationalise
the Productive Failure system prompt in `backend/pf/service.py`:

  F1. NO answer leak       — feedback does not reveal the canonical answer
                             that subsequently appears in the problem's
                             consolidation message.
  F2. Generative question  — feedback contains at least one '?' (the prompt
                             requires "ONE generative question").
  F3. Brevity              — feedback is <= 3 sentences (per the system
                             prompt rule "Keep the whole response to 3
                             sentences maximum").
  F4. Motivational opener  — feedback begins with positive acknowledgement
                             vocabulary (Great / Nice / Good / Well done /
                             Awesome / I appreciate ...).

A struggle-phase feedback message is "fidelity-passing" if all four
criteria are met. We report per-criterion pass rate and an overall pass
rate. The "Nice work — that's correct!" template that fires on a correct
answer is excluded from the denominator (it's a different code path).

Output: dict ready to JSON-dump and a printable report.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from data_loader import Problem, Session, load_sessions


CORRECT_TEMPLATES = (
    "Nice work — that's correct",
    "Nice work - that's correct",
    "Nice work, that's correct",
)
CONSOLIDATION_OPENERS = (
    "You've put in real effort",
    "You've put in strong effort",
    "Let's consolidate this one",
)


_MOTIVATIONAL_OPENERS = (
    "great",
    "nice",
    "good",
    "well done",
    "awesome",
    "i appreciate",
    "i see",
    "you've",
    "you're",
    "way to",
    "keep",
    "fantastic",
    "excellent",
    "interesting",
    "it's ok",
    "it's okay",
    "it's great",
    "it's nice",
    "that's a",
    "that's great",
    "let's",
)


_QUESTION_RE = re.compile(r"\?")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
# Spanish answer leak heuristic: 4+ consecutive Spanish-looking tokens.
_SPANISH_TOKEN_RE = re.compile(
    r"\b(?:el|la|los|las|un|una|unos|unas|de|del|al|que|y|o|pero|porque|cuando"
    r"|donde|como|muy|mas|menos|si|no|me|te|se|nos|os|le|les|lo|mi|tu|su"
    r"|ser|estar|tener|ir|hacer|poder|querer|saber|decir|haber|gustar"
    r"|hola|gracias|buenos|tienda|libro|libros|hermano|hermana|familia|casa|comer"
    r"|hablo|hablas|habla|hablamos|hablan|quiero|quieres|quiere|quieren"
    r"|tengo|tienes|tiene|tenemos|tienen|voy|vas|va|vamos|van|soy|eres|es|somos|son"
    r"|estoy|estas|esta|estamos|estan|hace|hacen|hizo|hicieron|fue|fueron|fui)\b",
    re.IGNORECASE,
)


@dataclass
class FidelityResult:
    total_feedback: int
    excluded_correct_template: int
    excluded_consolidation_opener: int
    counts: dict
    rates: dict
    examples_failing: list[dict]


def _count_sentences(text: str) -> int:
    parts = [p for p in _SENTENCE_SPLIT.split(text.strip()) if p.strip()]
    return len(parts)


def _looks_motivational(text: str) -> bool:
    head = text.strip().lower()
    return any(head.startswith(opener) for opener in _MOTIVATIONAL_OPENERS)


def _has_question(text: str) -> bool:
    return bool(_QUESTION_RE.search(text))


def _leaks_canonical_answer(feedback: str, canonical_answer: str | None) -> bool:
    """
    Strict leak check: if the canonical Spanish answer (or its core phrase)
    from the consolidation message appears verbatim in the struggle-phase
    feedback, that's a fidelity violation.
    """
    if not canonical_answer:
        return False
    answer = canonical_answer.strip().rstrip(".!?")
    if len(answer) < 6:
        return False
    return answer.lower() in feedback.lower()


def _heuristic_spanish_leak(feedback: str) -> bool:
    """
    Backup leak check when no canonical answer is available: a struggle-phase
    feedback message containing 4+ Spanish content tokens (excluding the
    student's own attempt) likely demonstrates the answer.
    """
    matches = _SPANISH_TOKEN_RE.findall(feedback)
    return len(matches) >= 4


def _extract_canonical_answer(consolidation: str | None) -> str | None:
    if not consolidation:
        return None
    # Pattern used in PFService._build_consolidation: "Correct answer: <answer>"
    m = re.search(r"correct answer\s*:\s*([^\n]+)", consolidation, re.IGNORECASE)
    if not m:
        return None
    return m.group(1).strip()


def evaluate(sessions: list[Session]) -> FidelityResult:
    total = 0
    excluded_correct = 0
    excluded_consol = 0
    pass_no_leak = 0
    pass_question = 0
    pass_brevity = 0
    pass_motivational = 0
    pass_all = 0
    failures: list[dict] = []

    for sess in sessions:
        for prob in sess.problems:
            canonical = _extract_canonical_answer(prob.consolidation)
            for fb in prob.tutor_feedback:
                if any(tpl in fb for tpl in CORRECT_TEMPLATES):
                    excluded_correct += 1
                    continue
                if any(op in fb for op in CONSOLIDATION_OPENERS):
                    excluded_consol += 1
                    continue
                total += 1

                no_leak = not (
                    _leaks_canonical_answer(fb, canonical)
                    or _heuristic_spanish_leak(fb)
                )
                has_q = _has_question(fb)
                brief = _count_sentences(fb) <= 3
                motiv = _looks_motivational(fb)

                pass_no_leak += int(no_leak)
                pass_question += int(has_q)
                pass_brevity += int(brief)
                pass_motivational += int(motiv)

                all_ok = no_leak and has_q and brief and motiv
                pass_all += int(all_ok)
                if not all_ok and len(failures) < 12:
                    failures.append(
                        {
                            "session_id": sess.session_id,
                            "problem_index": prob.problem_index,
                            "task_type": prob.task_type,
                            "feedback": fb,
                            "violations": [
                                v
                                for v, ok in [
                                    ("answer_leak", not no_leak),
                                    ("missing_question", not has_q),
                                    ("too_long", not brief),
                                    ("not_motivational", not motiv),
                                ]
                                if ok
                            ],
                        }
                    )

    counts = {
        "no_answer_leak": pass_no_leak,
        "generative_question": pass_question,
        "brevity_le3_sentences": pass_brevity,
        "motivational_opener": pass_motivational,
        "all_four_pass": pass_all,
    }

    def rate(n: int) -> float:
        return round(n / total, 3) if total else 0.0

    rates = {k: rate(v) for k, v in counts.items()}
    return FidelityResult(
        total_feedback=total,
        excluded_correct_template=excluded_correct,
        excluded_consolidation_opener=excluded_consol,
        counts=counts,
        rates=rates,
        examples_failing=failures,
    )


def to_dict(result: FidelityResult) -> dict:
    return asdict(result)


def render_markdown(result: FidelityResult) -> str:
    lines = ["## PF Fidelity (rule-based)", ""]
    lines.append(
        f"Evaluated **{result.total_feedback}** struggle-phase tutor messages "
        f"(excluded: {result.excluded_correct_template} correctness templates, "
        f"{result.excluded_consolidation_opener} consolidation openers).",
    )
    lines.append("")
    lines.append("| Criterion | Pass | Rate |")
    lines.append("|---|---:|---:|")
    label = {
        "no_answer_leak": "No answer leak",
        "generative_question": "Contains generative question",
        "brevity_le3_sentences": "Brevity (≤ 3 sentences)",
        "motivational_opener": "Motivational opener",
        "all_four_pass": "**All four pass**",
    }
    for key in ("no_answer_leak", "generative_question", "brevity_le3_sentences", "motivational_opener", "all_four_pass"):
        lines.append(
            f"| {label[key]} | {result.counts[key]}/{result.total_feedback} | "
            f"{result.rates[key]:.1%} |"
        )
    if result.examples_failing:
        lines.append("")
        lines.append("Sample violations:")
        for ex in result.examples_failing[:5]:
            lines.append(
                f"- *{ex['session_id']}* problem {ex['problem_index']} "
                f"({ex['task_type']}) — "
                f"violations: {', '.join(ex['violations'])}"
            )
            lines.append(f"  > {ex['feedback']}")
    return "\n".join(lines)


if __name__ == "__main__":
    sessions = load_sessions()
    result = evaluate(sessions)
    print(render_markdown(result))
