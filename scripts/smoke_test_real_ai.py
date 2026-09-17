from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.ai_service import explain_screening_with_ai, load_server_env, parse_protocol_with_ai  # noqa: E402
from core.protocol import extract_pdf_text, screening_criteria  # noqa: E402
from core.screening import screen_patient  # noqa: E402


def main() -> None:
    status = load_server_env(ROOT)
    if not status["configured"]:
        raise RuntimeError("OPENAI_API_KEY is not configured on the server.")

    protocol_bytes = (ROOT / "data" / "sample_protocol.pdf").read_bytes()
    protocol_result = parse_protocol_with_ai(extract_pdf_text(protocol_bytes))
    required_sections = {"basic_info", "inclusion", "exclusion", "visits", "safety", "metadata"}
    assert required_sections.issubset(protocol_result)
    assert protocol_result["metadata"]["requires_human_review"] is True

    patient = pd.read_csv(ROOT / "data" / "patient_data.csv").iloc[2].to_dict()
    rules = screen_patient(patient, screening_criteria())
    explanation = explain_screening_with_ai(patient, rules)
    assert explanation["summary"]
    assert isinstance(explanation["questions_for_investigator"], list)
    assert explanation["caution"]

    print(f"Real AI smoke test passed. Model: {status['model']}")
    print("Protocol extraction: PASS")
    print("Screening explanation: PASS")


if __name__ == "__main__":
    main()
