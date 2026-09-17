from __future__ import annotations

import json
import os
from pathlib import Path
import re
from typing import Any


class AIServiceError(RuntimeError):
    pass


def load_server_env(project_root: Path) -> dict:
    for filename in (".env.local", ".env"):
        path = project_root / filename
        if not path.exists():
            continue
        raw = path.read_text(encoding="utf-8-sig").strip()
        if raw.startswith("sk-") and "=" not in raw and "\n" not in raw:
            os.environ.setdefault("OPENAI_API_KEY", raw)
            continue
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key and value:
                os.environ.setdefault(key, value)
    return get_ai_status()


def get_ai_status() -> dict:
    return {
        "configured": bool(os.getenv("OPENAI_API_KEY")),
        "model": os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
    }


def create_client():
    if not os.getenv("OPENAI_API_KEY"):
        raise AIServiceError("真实 AI 模式尚未配置 API Key，请使用 Demo 模式。")
    try:
        from openai import OpenAI
        return OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=os.getenv("OPENAI_API_BASE_URL", "https://api.openai.com/v1"))
    except Exception as exc:
        raise AIServiceError("无法初始化 AI 客户端，请检查服务器配置。") from exc


PROTOCOL_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "basic_info": {
            "type": "object", "additionalProperties": False,
            "properties": {key: {"$ref": "#/$defs/evidence"} for key in ["试验名称", "适应症", "研究阶段", "主要研究目的"]},
            "required": ["试验名称", "适应症", "研究阶段", "主要研究目的"],
        },
        "inclusion": {"type": "array", "items": {"$ref": "#/$defs/evidence"}},
        "exclusion": {"type": "array", "items": {"$ref": "#/$defs/evidence"}},
        "visits": {"type": "array", "items": {"$ref": "#/$defs/evidence"}},
        "safety": {"type": "array", "items": {"$ref": "#/$defs/evidence"}},
    },
    "required": ["basic_info", "inclusion", "exclusion", "visits", "safety"],
    "$defs": {
        "evidence": {
            "type": "object", "additionalProperties": False,
            "properties": {"value": {"type": "string"}, "source": {"type": "string"}, "needs_review": {"type": "boolean"}},
            "required": ["value", "source", "needs_review"],
        }
    },
}


def _response_text(response: Any) -> str:
    if getattr(response, "output_text", None):
        return response.output_text
    chunks = []
    for output in getattr(response, "output", []) or []:
        for content in getattr(output, "content", []) or []:
            text = getattr(content, "text", None)
            if text:
                chunks.append(text)
    return "".join(chunks)


def parse_protocol_with_ai(text: str, client=None) -> dict:
    if len(text) > 120_000:
        text = text[:120_000]
    client = client or create_client()
    try:
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
            instructions=(
                "你是临床试验文档整理助手。只能提取用户提供的 Protocol 原文，不得补充常识或猜测。"
                "每项必须给出章节或原文短片段。无法确认时 value 必须为‘需要人工确认’，needs_review=true。"
                "不得给出受试者最终入组判断或医学建议。"
            ),
            input=f"请结构化提取以下模拟 Protocol：\n\n{text}",
            store=False,
            reasoning={"effort": "low"},
            max_output_tokens=6000,
            text={"format": {"type": "json_schema", "name": "protocol_extraction", "strict": True, "schema": PROTOCOL_SCHEMA}},
        )
        payload = json.loads(_response_text(response))
    except Exception as exc:
        raise AIServiceError("AI 解析失败，请稍后重试或切换 Demo 模式。") from exc
    payload["metadata"] = {"mode": "真实 AI 辅助解析", "requires_human_review": True, "model": getattr(response, "model", get_ai_status()["model"])}
    return payload


def explain_screening_with_ai(patient: dict, rule_result: dict, client=None) -> dict:
    client = client or create_client()
    schema = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "summary": {"type": "string"},
            "questions_for_investigator": {"type": "array", "items": {"type": "string"}},
            "caution": {"type": "string"},
        },
        "required": ["summary", "questions_for_investigator", "caution"],
    }
    try:
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
            instructions=(
                "你是临床试验初筛信息整理助手。规则引擎已经给出初步结果。"
                "只能解释现有结果和提出研究者确认问题，不能补充患者信息。"
                "状态名称只能原样使用 Potential Match、Needs Review 或 Potential Mismatch。"
                "不要写任何最终资格结论，也不要在警示语中复述被禁止的结论表达。"
            ),
            input=json.dumps({"patient": patient, "rule_result": rule_result}, ensure_ascii=False, default=str),
            store=False,
            reasoning={"effort": "low"}, max_output_tokens=1600,
            text={"format": {"type": "json_schema", "name": "screening_explanation", "strict": True, "schema": schema}},
        )
        payload = json.loads(_response_text(response))
    except Exception as exc:
        raise AIServiceError("AI 辅助解释失败，请保留规则结果并由研究者确认。") from exc
    joined = json.dumps(payload, ensure_ascii=False)
    forbidden_patterns = (
        r"不?符合.{0,4}入组",
        r"(?:可以|可|建议|应当|应该|确定|准予).{0,4}入组",
        r"(?:可以|不适合).{0,5}(?:参加|进入).{0,3}(?:研究|试验)",
        r"\b(?:eligible|ineligible)\b",
    )
    if any(re.search(pattern, joined, flags=re.IGNORECASE) for pattern in forbidden_patterns):
        # Never show an unsafe model conclusion. Fall back to the audited rule
        # result and retain the human-review questions instead of weakening the guardrail.
        payload = {
            "summary": f"规则引擎的初步状态为 {rule_result.get('status', 'Needs Review')}。AI 原始说明已由安全护栏替换。",
            "questions_for_investigator": rule_result.get("questions") or ["请研究者结合完整原始资料进行确认。"],
            "caution": "本结果仅用于资料整理，不代表受试者资格结论，必须由研究者人工审核。",
        }
    return payload
