from typing import cast

from questionary import Question


def _ask(question: Question) -> object:
    return cast(object, question.ask())


def ask_text(question: Question) -> str | None:
    """ask a question and return its answer as an optional string"""
    value = _ask(question)
    return value if isinstance(value, str) else None


def ask_bool(question: Question) -> bool | None:
    """ask a confirmation question and return its answer as an optional bool"""
    value = _ask(question)
    return value if isinstance(value, bool) else None


def ask_list(question: Question) -> list[str] | None:
    """ask a checkbox question and return the selected values as strings"""
    value = _ask(question)
    if not isinstance(value, list):
        return None
    return [str(item) for item in cast(list[object], value)]
