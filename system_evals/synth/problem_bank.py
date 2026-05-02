"""
Problem bank for synthetic session generation.

Each problem carries:
  - the prompt text the student sees
  - the canonical correct answer (used in consolidation messages)
  - a set of plausible misconception tags a learner might exhibit
  - per-misconception "wrong attempt" templates so we can deterministically
    inject a labelled error into a generated attempt string

Misconception tag set is identical to eval_misconception_detection.py.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Problem:
    task_type: str
    difficulty: int
    prompt: str            # what the student sees
    answer: str            # canonical solution
    answer_partial: str    # short fragment used for partial-progress attempts
    misconceptions: list[str]
    # Map: misconception tag -> list[wrong-answer string templates]
    error_attempts: dict[str, list[str]]


PROBLEMS: list[Problem] = [
    # ------------------------------------------------------------------
    # Translation, difficulty 1-2
    # ------------------------------------------------------------------
    Problem(
        task_type="translation",
        difficulty=1,
        prompt="English: I want to go to the store.",
        answer="Quiero ir a la tienda.",
        answer_partial="quiero ir",
        misconceptions=["VOCABULARY", "PREPOSITION", "ENGLISH_INTRUSION"],
        error_attempts={
            "VOCABULARY": ["quiero ir a la equipo", "quiero ir a la libro"],
            "PREPOSITION": ["quiero ir la tienda", "quiero ir tienda"],
            "ENGLISH_INTRUSION": ["I want ir a la store", "quiero ir a la store"],
            "STUCK": ["i don't know", "no idea", "idk"],
        },
    ),
    Problem(
        task_type="translation",
        difficulty=1,
        prompt="English: My name is Maria.",
        answer="Me llamo Maria.",
        answer_partial="llamo maria",
        misconceptions=["REFLEXIVE", "ENGLISH_INTRUSION"],
        error_attempts={
            "REFLEXIVE": ["llamo maria", "yo llamo maria"],
            "ENGLISH_INTRUSION": ["my name is maria", "me llamo Maria is"],
            "STUCK": ["i don't know"],
        },
    ),
    Problem(
        task_type="translation",
        difficulty=2,
        prompt="English: I have two brothers.",
        answer="Tengo dos hermanos.",
        answer_partial="tengo dos",
        misconceptions=["VERB_CONJUGATION", "GENDER_AGREEMENT", "ENGLISH_INTRUSION"],
        error_attempts={
            "VERB_CONJUGATION": ["yo tienes dos hermanos", "yo tiene dos hermanos"],
            "GENDER_AGREEMENT": ["tengo dos hermanas", "tengo dos las hermanos"],
            "ENGLISH_INTRUSION": ["tengo two hermanos", "I have dos brothers"],
            "STUCK": ["no idea"],
        },
    ),
    Problem(
        task_type="translation",
        difficulty=2,
        prompt="English: She is happy.",
        answer="Ella está feliz.",
        answer_partial="ella feliz",
        misconceptions=["SER_VS_ESTAR", "GENDER_AGREEMENT"],
        error_attempts={
            "SER_VS_ESTAR": ["ella es feliz", "ella es contenta"],
            "GENDER_AGREEMENT": ["ella está felizo"],
            "ENGLISH_INTRUSION": ["she is feliz", "ella is feliz"],
            "STUCK": ["i don't know"],
        },
    ),
    Problem(
        task_type="translation",
        difficulty=3,
        prompt="English: She washes her hands every morning.",
        answer="Ella se lava las manos cada mañana.",
        answer_partial="lava las manos",
        misconceptions=["REFLEXIVE", "VERB_CONJUGATION"],
        error_attempts={
            "REFLEXIVE": ["ella lava las manos cada mañana", "ella lava sus manos"],
            "VERB_CONJUGATION": ["ella se lavo las manos cada mañana"],
            "ENGLISH_INTRUSION": ["she se lava the hands every morning"],
            "STUCK": ["i don't know"],
        },
    ),
    # ------------------------------------------------------------------
    # Translation, difficulty 4-5 (preterite, subjunctive)
    # ------------------------------------------------------------------
    Problem(
        task_type="translation",
        difficulty=4,
        prompt="English: Yesterday I ate dinner with my family.",
        answer="Ayer comí la cena con mi familia.",
        answer_partial="ayer comi",
        misconceptions=["TENSE", "PREPOSITION", "VERB_CONJUGATION"],
        error_attempts={
            "TENSE": ["ayer como la cena con mi familia", "ayer comemos la cena con mi familia"],
            "PREPOSITION": ["ayer comí la cena mi familia"],
            "VERB_CONJUGATION": ["ayer comiste la cena con mi familia"],
            "ENGLISH_INTRUSION": ["yesterday comí dinner con mi familia"],
            "STUCK": ["i don't know"],
        },
    ),
    Problem(
        task_type="translation",
        difficulty=4,
        prompt="English: Last week we visited our grandparents.",
        answer="La semana pasada visitamos a nuestros abuelos.",
        answer_partial="visitamos abuelos",
        misconceptions=["TENSE", "PREPOSITION", "GENDER_AGREEMENT"],
        error_attempts={
            "TENSE": ["la semana pasada visitamos nuestros abuelos", "visitamos nuestros abuelos"],
            "PREPOSITION": ["la semana pasada visitamos nuestros abuelos"],
            "GENDER_AGREEMENT": ["la semana pasada visitamos a nuestras abuelos"],
            "ENGLISH_INTRUSION": ["last week visitamos a nuestros grandparents"],
            "STUCK": ["idk"],
        },
    ),
    Problem(
        task_type="translation",
        difficulty=5,
        prompt="English: I hope that my brother arrives on time.",
        answer="Espero que mi hermano llegue a tiempo.",
        answer_partial="espero que",
        misconceptions=["SUBJUNCTIVE", "VERB_CONJUGATION"],
        error_attempts={
            "SUBJUNCTIVE": ["espero que mi hermano llega a tiempo", "espero que mi hermano llegará a tiempo"],
            "VERB_CONJUGATION": ["espero que mi hermano lleguemos a tiempo"],
            "ENGLISH_INTRUSION": ["I hope que mi hermano llega on time"],
            "STUCK": ["i don't know"],
        },
    ),
    # ------------------------------------------------------------------
    # Error correction
    # ------------------------------------------------------------------
    Problem(
        task_type="error_correction",
        difficulty=2,
        prompt="Find and correct the error(s): Yo tienes dos hermanos.",
        answer="Yo tengo dos hermanos.",
        answer_partial="yo tengo",
        misconceptions=["VERB_CONJUGATION"],
        error_attempts={
            "VERB_CONJUGATION": ["yo tienes dos hermanos", "yo tiene dos hermanos"],
            "STUCK": ["i don't know", "there is no error"],
            "ENGLISH_INTRUSION": ["I have dos hermanos"],
        },
    ),
    Problem(
        task_type="error_correction",
        difficulty=2,
        prompt="Find and correct the error(s): La libro es interesante.",
        answer="El libro es interesante.",
        answer_partial="el libro",
        misconceptions=["GENDER_AGREEMENT"],
        error_attempts={
            "GENDER_AGREEMENT": ["la libro es interesante", "la libra es interesante"],
            "STUCK": ["no idea"],
            "ENGLISH_INTRUSION": ["the libro is interesante"],
        },
    ),
    Problem(
        task_type="error_correction",
        difficulty=3,
        prompt="Find and correct the error(s): Ella es enferma hoy.",
        answer="Ella está enferma hoy.",
        answer_partial="ella esta enferma",
        misconceptions=["SER_VS_ESTAR"],
        error_attempts={
            "SER_VS_ESTAR": ["ella es enferma hoy", "ella son enferma hoy"],
            "STUCK": ["i don't know"],
            "ENGLISH_INTRUSION": ["she is sick today"],
        },
    ),
    Problem(
        task_type="error_correction",
        difficulty=3,
        prompt="Find and correct the error(s): Yo lavo las manos cada mañana.",
        answer="Yo me lavo las manos cada mañana.",
        answer_partial="me lavo las manos",
        misconceptions=["REFLEXIVE"],
        error_attempts={
            "REFLEXIVE": ["yo lavo las manos cada mañana", "yo lavo mis manos cada mañana"],
            "STUCK": ["idk"],
            "ENGLISH_INTRUSION": ["I lavo my hands every morning"],
        },
    ),
    Problem(
        task_type="error_correction",
        difficulty=4,
        prompt="Find and correct the error(s): Ayer ella come pizza con sus amigas.",
        answer="Ayer ella comió pizza con sus amigas.",
        answer_partial="ella comio",
        misconceptions=["TENSE"],
        error_attempts={
            "TENSE": ["ayer ella come pizza con sus amigas", "ella come pizza con sus amigas"],
            "STUCK": ["no idea"],
            "ENGLISH_INTRUSION": ["yesterday ella eats pizza con sus amigas"],
        },
    ),
    # ------------------------------------------------------------------
    # Conversation completion
    # ------------------------------------------------------------------
    Problem(
        task_type="conversation_completion",
        difficulty=1,
        prompt="Complete the conversation:\nA: ¿Cómo te llamas?\nB: ___",
        answer="Me llamo Carlos.",
        answer_partial="me llamo",
        misconceptions=["REFLEXIVE", "ENGLISH_INTRUSION"],
        error_attempts={
            "REFLEXIVE": ["llamo carlos", "yo llamo carlos"],
            "ENGLISH_INTRUSION": ["my name is carlos", "I am carlos"],
            "STUCK": ["i don't know"],
        },
    ),
    Problem(
        task_type="conversation_completion",
        difficulty=2,
        prompt="Complete the conversation:\nA: ¿Qué haces los fines de semana?\nB: ___",
        answer="Me gusta ir al parque.",
        answer_partial="me gusta",
        misconceptions=["VERB_CONJUGATION", "PREPOSITION"],
        error_attempts={
            "VERB_CONJUGATION": ["me gustas ir al parque", "me gusto ir al parque"],
            "PREPOSITION": ["me gusta ir parque", "me gusta ir el parque"],
            "ENGLISH_INTRUSION": ["I like ir al park", "me gusta go al parque"],
            "STUCK": ["i don't know"],
        },
    ),
    Problem(
        task_type="conversation_completion",
        difficulty=3,
        prompt="Complete the conversation:\nA: ¿Cómo estás hoy?\nB: ___",
        answer="Estoy muy feliz hoy.",
        answer_partial="estoy",
        misconceptions=["SER_VS_ESTAR", "GENDER_AGREEMENT"],
        error_attempts={
            "SER_VS_ESTAR": ["soy muy feliz hoy", "yo es feliz"],
            "GENDER_AGREEMENT": ["estoy muy feliza hoy"],
            "ENGLISH_INTRUSION": ["I am muy feliz today"],
            "STUCK": ["no idea"],
        },
    ),
    Problem(
        task_type="conversation_completion",
        difficulty=4,
        prompt="Complete the conversation:\nA: ¿Qué hiciste ayer?\nB: ___",
        answer="Ayer fui al cine con mi hermana.",
        answer_partial="ayer fui",
        misconceptions=["TENSE", "PREPOSITION"],
        error_attempts={
            "TENSE": ["ayer voy al cine", "voy al cine con mi hermana"],
            "PREPOSITION": ["ayer fui cine con mi hermana"],
            "ENGLISH_INTRUSION": ["yesterday I went al cine"],
            "STUCK": ["i don't know"],
        },
    ),
    Problem(
        task_type="conversation_completion",
        difficulty=5,
        prompt="Complete the conversation:\nA: Quiero que vengas a la fiesta. ¿Puedes venir?\nB: ___",
        answer="Sí, espero que sea divertido.",
        answer_partial="espero que",
        misconceptions=["SUBJUNCTIVE"],
        error_attempts={
            "SUBJUNCTIVE": ["si, espero que es divertido", "si, creo que es divertido"],
            "ENGLISH_INTRUSION": ["yes, espero que it is fun"],
            "STUCK": ["i don't know"],
        },
    ),
]


def by_task_and_difficulty() -> dict[tuple[str, int], list[Problem]]:
    out: dict[tuple[str, int], list[Problem]] = {}
    for p in PROBLEMS:
        out.setdefault((p.task_type, p.difficulty), []).append(p)
    return out
