import pandas as pd

from core.data_quality import compare_source_edc
from core.sample_data import edc_rows, source_rows


def test_detects_expected_clinical_data_issues():
    result = compare_source_edc(pd.DataFrame(source_rows()), pd.DataFrame(edc_rows()))
    issue_types = set(result["问题类型"])
    expected = {"日期不一致", "实验室结果不一致", "缺失数据", "重复数据", "单位错误", "用药记录不一致", "AE 信息缺失", "知情同意日期异常"}
    assert expected.issubset(issue_types)
    assert set(result["风险等级"]).issubset({"High", "Medium", "Low"})
    assert (result["Patient ID"] == "P010").any()


def test_comparison_does_not_modify_source():
    source = pd.DataFrame(source_rows())
    before = source.copy(deep=True)
    compare_source_edc(source, pd.DataFrame(edc_rows()))
    pd.testing.assert_frame_equal(source, before)

