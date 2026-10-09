import json

from app.config import Settings
from app.graphs.brief_graph import build_brief_graph
from app.llm.client import StructuredLLM
from tests.fakes import ScriptedBackend

RAW = "Sahadaki bayilerimizden gelen şikayetleri daha hızlı sınıflandırmak istiyoruz, çok manuel gidiyor."

PARTIAL_BRIEF = json.dumps(
    {
        "title": "Bayi şikayetlerinin otomatik sınıflandırılması",
        "problem": "Bayilerden gelen şikayetler elle sınıflandırılıyor ve yavaş",
        "scope": None,
        "required_capabilities": ["Türkçe metin sınıflandırma", "şikayet ve talep kategorizasyonu"],
        "success_criteria": None,
        "timeline": None,
        "missing_fields": [],
    },
    ensure_ascii=False,
)

QUESTIONS = json.dumps(
    {
        "questions": [
            {"field": "scope", "question": "Ayda kaç şikayet geliyor, hangi kanaldan?"},
            {"field": "success_criteria", "question": "Hangi doğrulukta başarılı sayarsınız?"},
            {"field": "timeline", "question": "Pilot 3 ay mı, 6 ay mı sürmeli?"},
            {"field": "budget", "question": "Bütçe nedir?"},
        ]
    },
    ensure_ascii=False,
)

COMPLETE_BRIEF = json.dumps(
    {
        "title": "Bayi şikayetlerinin otomatik sınıflandırılması",
        "problem": "Bayilerden gelen şikayetler elle sınıflandırılıyor ve yavaş",
        "scope": "Ayda ~3.000 şikayet, bayi portalı ve e-posta",
        "required_capabilities": ["Türkçe metin sınıflandırma"],
        "success_criteria": "%85 doğru kategori",
        "timeline": "3 ay",
    },
    ensure_ascii=False,
)


def run(state, responses, tmp_path):
    backend = ScriptedBackend(responses)
    graph = build_brief_graph(StructuredLLM(backend, Settings(demo_cache_dir=str(tmp_path))))
    return graph.invoke(state), backend


def test_incomplete_text_produces_followup_questions(tmp_path):
    result, _ = run({"raw_text": RAW}, [PARTIAL_BRIEF, QUESTIONS], tmp_path)
    assert result["status"] == "needs_input"
    assert result["missing_fields"] == ["scope", "success_criteria", "timeline"]
    assert [q["field"] for q in result["questions"]] == ["scope", "success_criteria", "timeline"]
    assert result["followup_rounds"] == 1


def test_complete_text_is_finalized_without_questions(tmp_path):
    result, backend = run({"raw_text": RAW}, [COMPLETE_BRIEF], tmp_path)
    assert result["status"] == "final"
    assert result["questions"] == []
    assert len(backend.calls) == 1


def test_answers_are_merged_into_the_brief(tmp_path):
    state = {
        "raw_text": RAW,
        "answers": {"scope": "Ayda 3.000 şikayet", "success_criteria": "%85", "timeline": "3 ay"},
        "asked_questions": json.loads(QUESTIONS)["questions"][:3],
        "followup_rounds": 1,
    }
    result, backend = run(state, [COMPLETE_BRIEF], tmp_path)
    assert result["status"] == "final"
    assert result["brief"]["timeline"] == "3 ay"
    prompt = backend.calls[0][1]["content"]
    assert "Ayda 3.000 şikayet" in prompt and "takip sorularını" in prompt


def test_no_second_round_of_questions(tmp_path):
    state = {"raw_text": RAW, "answers": {"scope": ""}, "asked_questions": [], "followup_rounds": 1}
    result, _ = run(state, [PARTIAL_BRIEF], tmp_path)
    assert result["status"] == "final"
    assert result["brief"]["missing_fields"] == ["scope", "success_criteria", "timeline"]
