from __future__ import annotations

import math
from typing import Any

import pandas as pd

REQUIRED_COLUMNS = {
    "patient_id", "visit", "visit_date", "hemoglobin", "hemoglobin_unit",
    "ALT_U_L", "concomitant_medication", "AE_term", "AE_grade",
    "ae_seriousness", "informed_consent_date",
}

FIELD_LABELS = {
    "visit_date": "Visit Date", "hemoglobin": "Hemoglobin",
    "hemoglobin_unit": "Hemoglobin Unit", "ALT_U_L": "ALT",
    "concomitant_medication": "Concomitant Medication", "AE_term": "AE Term",
    "AE_grade": "AE Grade", "ae_seriousness": "AE Seriousness",
    "informed_consent_date": "Informed Consent Date",
}


def _blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return str(value).strip().lower() in {"", "nan", "none"}


def _same(left: Any, right: Any) -> bool:
    if _blank(left) and _blank(right):
        return True
    if _blank(left) or _blank(right):
        return False
    try:
        return abs(float(left) - float(right)) < 1e-9
    except (TypeError, ValueError):
        return str(left).strip().lower() == str(right).strip().lower()


def _issue(patient_id: str, field: str, source: Any, edc: Any, issue_type: str, risk: str, action: str) -> dict:
    def display(value: Any) -> str:
        return "<缺失>" if _blank(value) else str(value)
    return {
        "Patient ID": patient_id,
        "字段名称": FIELD_LABELS.get(field, field),
        "Source Data": display(source),
        "EDC Data": display(edc),
        "问题类型": issue_type,
        "风险等级": risk,
        "建议处理方式": action,
    }


def validate_columns(df: pd.DataFrame, label: str) -> None:
    missing = sorted(REQUIRED_COLUMNS - set(df.columns))
    if missing:
        raise ValueError(f"{label} 缺少必需字段：{', '.join(missing)}")


def compare_source_edc(source_df: pd.DataFrame, edc_df: pd.DataFrame) -> pd.DataFrame:
    validate_columns(source_df, "Source Data")
    validate_columns(edc_df, "EDC Data")
    issues: list[dict] = []
    keys = ["patient_id", "visit"]

    duplicates = edc_df[edc_df.duplicated(keys, keep=False)]
    for patient_id in duplicates["patient_id"].drop_duplicates():
        issues.append(_issue(patient_id, "record", "单条源记录", "EDC 存在重复记录", "重复数据", "Medium", "建议 CRC 核对重复 eCRF 记录，确认后按数据管理流程处理。"))

    source = source_df.drop_duplicates(keys, keep="first").set_index(keys)
    edc = edc_df.drop_duplicates(keys, keep="first").set_index(keys)
    all_keys = source.index.union(edc.index)
    fields = ["visit_date", "hemoglobin", "hemoglobin_unit", "ALT_U_L", "concomitant_medication", "AE_term", "AE_grade", "ae_seriousness", "informed_consent_date"]

    for key in all_keys:
        patient_id = key[0]
        if key not in source.index:
            issues.append(_issue(patient_id, "record", "<无源记录>", "存在 EDC 记录", "缺失源记录", "High", "建议 CRA / CRC 立即核对原始记录与录入依据。"))
            continue
        if key not in edc.index:
            issues.append(_issue(patient_id, "record", "存在源记录", "<无 EDC 记录>", "缺失 EDC 记录", "High", "建议 CRC 核对并按授权流程完成 EDC 录入。"))
            continue
        source_row, edc_row = source.loc[key], edc.loc[key]
        for field in fields:
            left, right = source_row[field], edc_row[field]
            if _same(left, right):
                continue
            if field == "visit_date":
                issues.append(_issue(patient_id, field, left, right, "日期不一致", "Medium", "建议 CRA / CRC 核对原始访视记录和 EDC 日期。"))
            elif field in {"hemoglobin", "ALT_U_L"}:
                issue_type = "缺失数据" if _blank(right) else "实验室结果不一致"
                issues.append(_issue(patient_id, field, left, right, issue_type, "Medium", "建议核对实验室报告、单位和 EDC 录入值。"))
            elif field == "hemoglobin_unit":
                issues.append(_issue(patient_id, field, left, right, "单位错误", "Medium", "建议实验室或 CRC 核对报告单位，禁止直接改写 Source Data。"))
            elif field == "concomitant_medication":
                issues.append(_issue(patient_id, field, left, right, "用药记录不一致", "Medium", "建议 CRC 核对合并用药原始记录、开始日期和剂量。"))
            elif field in {"AE_term", "AE_grade", "ae_seriousness"} and not _blank(left) and _blank(right):
                risk = "High" if str(source_row.get("ae_seriousness", "")).upper() == "SAE" else "Medium"
                issues.append(_issue(patient_id, field, left, right, "AE 信息缺失", risk, "建议立即联系研究者 / CRC 核对 AE/SAE 原始记录并按流程处理。"))
            elif field == "informed_consent_date":
                issues.append(_issue(patient_id, field, left, right, "知情同意日期异常", "High", "建议研究者和 CRA 优先核对知情同意原件及研究程序时间。"))
            else:
                issues.append(_issue(patient_id, field, left, right, "字段不一致", "Low", "建议 CRC 核对原始记录与 EDC。"))
    result = pd.DataFrame(issues)
    if result.empty:
        return pd.DataFrame(columns=["Patient ID", "字段名称", "Source Data", "EDC Data", "问题类型", "风险等级", "建议处理方式"])
    order = pd.Categorical(result["风险等级"], categories=["High", "Medium", "Low"], ordered=True)
    return result.assign(_risk_order=order).sort_values(["_risk_order", "Patient ID"]).drop(columns="_risk_order").reset_index(drop=True)

