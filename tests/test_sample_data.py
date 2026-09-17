from pathlib import Path

import pandas as pd

from core.sample_data import SIMULATION_NOTICE, generate_all


def test_generate_all_simulated_files(tmp_path: Path):
    paths = generate_all(tmp_path)
    assert all(path.exists() for path in paths.values())
    patients = pd.read_csv(paths["patient_data"])
    assert len(patients) >= 10
    assert patients["patient_id"].str.fullmatch(r"P\d{3}").all()
    assert patients["is_simulated"].astype(str).str.lower().eq("true").all()
    assert not patients.astype(str).apply(lambda col: col.str.contains(r"姓名|身份证|手机号", regex=True)).any().any()
    assert "完全虚构" in SIMULATION_NOTICE

