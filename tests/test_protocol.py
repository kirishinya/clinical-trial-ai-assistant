from pathlib import Path

from core.protocol import extract_pdf_text, parse_protocol_demo
from core.sample_data import generate_all


def test_sample_protocol_extracts_sections_and_sources(tmp_path: Path):
    protocol = generate_all(tmp_path)["protocol"]
    text = extract_pdf_text(protocol.read_bytes())
    result = parse_protocol_demo(text)
    assert "非小细胞肺癌" in result["basic_info"]["适应症"]["value"]
    assert len(result["inclusion"]) >= 8
    assert len(result["exclusion"]) >= 6
    assert result["visits"][0]["source"].startswith("4.")
    assert result["safety"][0]["source"].startswith("5.")
    assert result["metadata"]["requires_human_review"] is True


def test_unknown_protocol_never_invents_information():
    result = parse_protocol_demo("这是一份没有明确试验信息的普通文档。" * 10)
    assert result["basic_info"]["试验名称"]["value"] == "需要人工确认"
    assert result["basic_info"]["试验名称"]["needs_review"] is True

