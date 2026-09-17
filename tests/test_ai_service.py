import json
import os
from pathlib import Path

from core.ai_service import explain_screening_with_ai, get_ai_status, load_server_env, parse_protocol_with_ai


class FakeResponse:
    model = "test-model"
    output_text = json.dumps({
        "basic_info": {
            "试验名称": {"value": "模拟研究", "source": "第1章", "needs_review": False},
            "适应症": {"value": "需要人工确认", "source": "未找到", "needs_review": True},
            "研究阶段": {"value": "II期", "source": "第1章", "needs_review": False},
            "主要研究目的": {"value": "模拟目的", "source": "第2章", "needs_review": False},
        },
        "inclusion": [], "exclusion": [], "visits": [], "safety": [],
    }, ensure_ascii=False)


class FakeResponses:
    def create(self, **kwargs):
        assert kwargs["text"]["format"]["strict"] is True
        assert "不得补充" in kwargs["instructions"]
        return FakeResponse()


class FakeClient:
    responses = FakeResponses()


def test_loads_raw_server_key_without_exposing_it(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    fake_key = "".join(["s", "k-test-only-not-a-real-secret"])
    (tmp_path / ".env.local").write_text(fake_key, encoding="utf-8")
    status = load_server_env(tmp_path)
    assert status["configured"] is True
    assert get_ai_status()["configured"] is True
    assert fake_key not in str(status)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def test_ai_protocol_parser_requires_evidence_and_human_review():
    result = parse_protocol_with_ai("模拟 Protocol 文本" * 20, client=FakeClient())
    assert result["basic_info"]["适应症"]["needs_review"] is True
    assert result["metadata"]["requires_human_review"] is True


def test_screening_guardrail_replaces_forbidden_conclusion():
    unsafe_summaries = [
        "模型错误地给出了不符合入组的结论",
        "该患者可以入组",
        "The patient is eligible for the study.",
        "该患者可以参加研究",
    ]
    for unsafe_summary in unsafe_summaries:
        class UnsafeResponse:
            output_text = json.dumps({
                "summary": unsafe_summary,
                "questions_for_investigator": [],
                "caution": "需要复核",
            }, ensure_ascii=False)

        class UnsafeClient:
            class responses:
                @staticmethod
                def create(**kwargs):
                    return UnsafeResponse()

        result = explain_screening_with_ai(
            {"patient_id": "P003"},
            {"status": "Needs Review", "questions": ["请确认 ECOG。"]},
            client=UnsafeClient(),
        )
        serialized = json.dumps(result, ensure_ascii=False)
        assert unsafe_summary not in serialized
        assert result["questions_for_investigator"] == ["请确认 ECOG。"]
