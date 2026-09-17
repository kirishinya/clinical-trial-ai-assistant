import pandas as pd

from core.sample_data import patient_rows
from core.screening import ALLOWED_STATUSES, screen_all, screen_patient


def test_screening_produces_only_three_non_final_statuses():
    results = screen_all(pd.DataFrame(patient_rows()))
    assert set(results["status"]).issubset(ALLOWED_STATUSES)
    assert {"Potential Match", "Needs Review", "Potential Mismatch"}.issubset(set(results["status"]))
    forbidden = " ".join(results.astype(str).to_numpy().flatten())
    assert "符合入组" not in forbidden
    assert "不符合入组" not in forbidden


def test_missing_ecog_and_washout_requires_review():
    patient = next(row for row in patient_rows() if row["patient_id"] == "P003")
    result = screen_patient(patient)
    assert result["status"] == "Needs Review"
    assert any("ECOG" in item for item in result["missing"])
    assert any("洗脱期" in item for item in result["missing"])


def test_potential_conflict_is_explained_without_final_decision():
    patient = next(row for row in patient_rows() if row["patient_id"] == "P005")
    result = screen_patient(patient)
    assert result["status"] == "Potential Mismatch"
    assert any("中枢神经" in item for item in result["conflicts"])
    assert result["human_review_required"] is True

