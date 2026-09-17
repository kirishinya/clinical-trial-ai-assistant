import pandas as pd

from core.data_quality import compare_source_edc
from core.sample_data import edc_rows, source_rows
from core.worklist import apply_status, build_worklist


def test_worklist_maps_priority_contact_and_status():
    issues = compare_source_edc(pd.DataFrame(source_rows()), pd.DataFrame(edc_rows()))
    worklist = build_worklist(issues)
    assert {"High Priority", "Medium Priority"}.issubset(set(worklist["优先级"]))
    assert worklist["状态"].eq("Open").all()
    assert worklist["建议联系对象"].str.len().gt(0).all()


def test_status_management_is_explicit_and_non_destructive():
    issues = compare_source_edc(pd.DataFrame(source_rows()), pd.DataFrame(edc_rows()))
    worklist = build_worklist(issues)
    updated = apply_status(worklist, {0: "In Progress", 1: "Closed"})
    assert updated.loc[0, "状态"] == "In Progress"
    assert updated.loc[1, "状态"] == "Closed"
    assert worklist.loc[0, "状态"] == "Open"

