"""Adım 1: serbest ihtiyaç metni → yapılandırılmış brief (gerekirse takip sorularıyla).

Akış:
    route_entry ─┬─ extract_brief ──┐
                 └─ merge_answers ──┴─> check_completeness ─┬─ ask_followups → END (status=needs_input)
                                                            └─ finalize      → END (status=final)

Graf durumsuzdur: takip soruları ve cevaplar veritabanında saklanır, bir sonraki çağrıda
`answers` ile birlikte tekrar çalıştırılır.
"""

import json
from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.config import Settings, get_settings
from app.llm.client import StructuredLLM
from app.prompts import brief as prompts
from app.schemas import Brief, FollowUpQuestions


class BriefState(TypedDict, total=False):
    raw_text: str
    answers: dict[str, str]           # alan adı → kurumun cevabı
    asked_questions: list[dict]       # önceki turda sorulan sorular
    followup_rounds: int              # şimdiye kadar kaç tur takip sorusu soruldu
    brief: dict
    missing_fields: list[str]
    questions: list[dict]
    status: str                       # needs_input | final
    defaults: dict                    # firma profilinden gelen varsayılanlar (profile_defaults)


def profile_defaults(profile: dict | None) -> dict:
    """Firma profilini brief alanlarına çevirir. Yalnızca brief'te boş kalan alanları doldurmak için kullanılır."""
    if not profile:
        return {}
    defaults = {
        "sector": profile.get("sector"),
        "min_maturity": profile.get("preferred_maturity"),
        "budget": profile.get("budget_range"),
        "timeline": profile.get("pilot_duration"),
    }
    if profile.get("startup_location") == "ayni_sehir":
        defaults["location_preference"] = profile.get("city")
    return {key: value for key, value in defaults.items() if value}


def apply_defaults(brief: dict, defaults: dict) -> dict:
    """Metinde ya da cevaplarda geçen bilgiyi asla ezmez; sadece boş alanları doldurur."""
    return {**brief, **{key: value for key, value in defaults.items() if not brief.get(key)}}


def build_brief_graph(llm: StructuredLLM, settings: Settings | None = None):
    settings = settings or get_settings()
    max_rounds = 1  # en fazla bir tur takip sorusu: sonsuz döngü yok

    def extract_brief(state: BriefState) -> BriefState:
        brief = llm.invoke(
            Brief,
            system=prompts.EXTRACT_SYSTEM,
            user=prompts.EXTRACT_USER.format(raw_text=state["raw_text"], answers_block=""),
        )
        return {"brief": brief.model_dump(mode="json")}

    def merge_answers(state: BriefState) -> BriefState:
        questions = {q["field"]: q["question"] for q in state.get("asked_questions", [])}
        qa_lines = "\n".join(
            f"- Soru ({field}): {questions.get(field, field)}\n  Cevap: {answer}"
            for field, answer in state["answers"].items()
            if answer and answer.strip()
        )
        answers_block = prompts.ANSWERS_BLOCK.format(qa_lines=qa_lines) if qa_lines else ""
        brief = llm.invoke(
            Brief,
            system=prompts.EXTRACT_SYSTEM,
            user=prompts.EXTRACT_USER.format(raw_text=state["raw_text"], answers_block=answers_block),
        )
        return {"brief": brief.model_dump(mode="json")}

    def check_completeness(state: BriefState) -> BriefState:
        brief = Brief.model_validate(apply_defaults(state["brief"], state.get("defaults") or {}))
        missing = brief.computed_missing_fields()  # LLM'in beyanı değil, kodun hesabı
        brief.missing_fields = missing
        return {"brief": brief.model_dump(mode="json"), "missing_fields": missing}

    def ask_followups(state: BriefState) -> BriefState:
        result = llm.invoke(
            FollowUpQuestions,
            system=prompts.FOLLOWUP_SYSTEM.format(max_questions=settings.max_followup_questions),
            user=prompts.FOLLOWUP_USER.format(
                raw_text=state["raw_text"],
                brief_json=json.dumps(state["brief"], ensure_ascii=False),
                missing=", ".join(state["missing_fields"]),
            ),
        )
        allowed = set(state["missing_fields"])
        questions = [q.model_dump() for q in result.questions if q.field in allowed]
        questions = questions[: settings.max_followup_questions]
        return {
            "questions": questions,
            "followup_rounds": state.get("followup_rounds", 0) + 1,
            "status": "needs_input",
        }

    def finalize(state: BriefState) -> BriefState:
        return {"questions": [], "status": "final"}

    def route_entry(state: BriefState) -> str:
        return "merge_answers" if state.get("answers") else "extract_brief"

    def route_after_check(state: BriefState) -> str:
        if state["missing_fields"] and state.get("followup_rounds", 0) < max_rounds:
            return "ask_followups"
        return "finalize"

    graph = StateGraph(BriefState)
    graph.add_node("extract_brief", extract_brief)
    graph.add_node("merge_answers", merge_answers)
    graph.add_node("check_completeness", check_completeness)
    graph.add_node("ask_followups", ask_followups)
    graph.add_node("finalize", finalize)

    graph.set_conditional_entry_point(route_entry, {"extract_brief": "extract_brief", "merge_answers": "merge_answers"})
    graph.add_edge("extract_brief", "check_completeness")
    graph.add_edge("merge_answers", "check_completeness")
    graph.add_conditional_edges(
        "check_completeness", route_after_check, {"ask_followups": "ask_followups", "finalize": "finalize"}
    )
    graph.add_edge("ask_followups", END)
    graph.add_edge("finalize", END)
    return graph.compile()
