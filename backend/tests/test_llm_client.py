import pytest

from app.config import Settings
from app.llm.cache import DemoCacheMiss
from app.llm.client import StructuredLLM, StructuredOutputError, extract_json
from app.schemas import FollowUpQuestions
from tests.fakes import ScriptedBackend

VALID = '{"questions": [{"field": "timeline", "question": "Pilot ne kadar sürmeli?"}]}'


def make_llm(responses, tmp_path, mode="off", retries=2):
    settings = Settings(demo_mode=mode, demo_cache_dir=str(tmp_path), llm_max_retries=retries)
    backend = ScriptedBackend(responses)
    return StructuredLLM(backend, settings), backend


def test_extract_json_strips_markdown_fence():
    assert extract_json('Tabii:\n```json\n{"a": 1}\n```') == '{"a": 1}'


def test_valid_json_is_parsed(tmp_path):
    llm, _ = make_llm([VALID], tmp_path)
    result = llm.invoke(FollowUpQuestions, "sistem", "kullanıcı")
    assert result.questions[0].field == "timeline"


def test_invalid_json_is_retried_with_error_feedback(tmp_path):
    llm, backend = make_llm(["bozuk cevap", VALID], tmp_path)
    result = llm.invoke(FollowUpQuestions, "sistem", "kullanıcı")
    assert len(result.questions) == 1
    assert "şemaya uymadı" in backend.calls[1][-1]["content"]


def test_gives_up_after_max_retries(tmp_path):
    llm, _ = make_llm(["x", "y", "z"], tmp_path, retries=2)
    with pytest.raises(StructuredOutputError):
        llm.invoke(FollowUpQuestions, "sistem", "kullanıcı")


def test_record_then_replay_without_calling_model(tmp_path):
    recorder, _ = make_llm([VALID], tmp_path, mode="record")
    recorder.invoke(FollowUpQuestions, "sistem", "kullanıcı")

    replayer, backend = make_llm([], tmp_path, mode="replay")
    result = replayer.invoke(FollowUpQuestions, "sistem", "kullanıcı")
    assert result.questions[0].question == "Pilot ne kadar sürmeli?"
    assert backend.calls == []


def test_replay_miss_raises(tmp_path):
    llm, _ = make_llm([], tmp_path, mode="replay")
    with pytest.raises(DemoCacheMiss):
        llm.invoke(FollowUpQuestions, "sistem", "başka soru")
