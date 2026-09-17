from __future__ import annotations

import math
from typing import Any

import pandas as pd

from .protocol import screening_criteria

ALLOWED_STATUSES = {"Potential Match", "Needs Review", "Potential Mismatch"}


def _missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return str(value).strip().lower() in {"", "nan", "none", "unknown", "not recorded"}


def _number(value: Any) -> float | None:
    if _missing(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def screen_patient(patient: dict, criteria: dict | None = None) -> dict:
    criteria = criteria or screening_criteria()
    supported: list[str] = []
    conflicts: list[str] = []
    missing: list[str] = []
    questions: list[str] = []

    age = _number(patient.get("age"))
    if age is None:
        missing.append("年龄记录缺失")
    elif criteria["age_min"] <= age <= criteria["age_max"]:
        supported.append("年龄在 18-75 周岁范围内")
    else:
        conflicts.append(f"年龄 {age:g} 岁超出 Protocol 范围")

    diagnosis = str(patient.get("diagnosis", "")).strip()
    if not diagnosis:
        missing.append("诊断记录缺失")
    elif diagnosis == criteria["diagnosis"]:
        supported.append("记录诊断为非小细胞肺癌")
    else:
        conflicts.append(f"记录诊断为“{diagnosis}”，与目标适应症不一致")

    stage = str(patient.get("stage", "")).strip()
    if not stage:
        missing.append("疾病分期缺失")
    elif stage in criteria["stages"]:
        supported.append(f"疾病分期记录为 {stage}")
    else:
        conflicts.append(f"疾病分期 {stage} 不在 IIIB/IIIC/IV 范围")

    ecog = _number(patient.get("ECOG"))
    if ecog is None:
        missing.append("ECOG 记录缺失")
        questions.append("请研究者确认筛选期 ECOG 评分及评估日期。")
    elif int(ecog) in criteria["ecog_allowed"]:
        supported.append(f"ECOG 记录为 {int(ecog)}")
    else:
        conflicts.append(f"ECOG 记录为 {ecog:g}，超出 Protocol 的 0-1 范围")

    lab_rules = [
        ("ANC_10e9_L", criteria["anc_min"], None, "ANC", "×10^9/L"),
        ("platelet_10e9_L", criteria["platelet_min"], None, "血小板", "×10^9/L"),
        ("hemoglobin_g_L", criteria["hemoglobin_min"], None, "血红蛋白", "g/L"),
        ("ALT_ULN_ratio", None, criteria["alt_uln_max"], "ALT", "×ULN"),
        ("creatinine_clearance_mL_min", criteria["crcl_min"], None, "肌酐清除率", "mL/min"),
    ]
    for field, minimum, maximum, label, unit in lab_rules:
        value = _number(patient.get(field))
        if value is None:
            missing.append(f"{label} 结果缺失")
            continue
        passed = (minimum is None or value >= minimum) and (maximum is None or value <= maximum)
        if passed:
            supported.append(f"{label} {value:g} {unit} 在方案阈值范围内")
        else:
            conflicts.append(f"{label} {value:g} {unit} 超出方案阈值")

    lesion = str(patient.get("measurable_lesion", "")).strip().lower()
    if lesion in {"", "unknown", "nan"}:
        missing.append("可测量病灶信息缺失")
    elif lesion == "yes":
        supported.append("记录存在可测量病灶")
    else:
        conflicts.append("记录提示无可测量病灶")

    washout = _number(patient.get("days_since_last_treatment"))
    if washout is None:
        missing.append("既往治疗结束日期或洗脱期缺失")
        questions.append("请研究者确认既往治疗末次日期及完整洗脱期。")
    elif washout >= criteria["washout_days_min"]:
        supported.append(f"既往治疗洗脱期记录为 {washout:g} 天")
    else:
        conflicts.append(f"既往治疗洗脱期记录仅 {washout:g} 天")

    if str(patient.get("active_CNS_metastasis", "")).strip().lower() == "yes":
        conflicts.append("记录存在活动性中枢神经系统转移")
    elif _missing(patient.get("active_CNS_metastasis")):
        missing.append("中枢神经系统转移状态缺失")
    else:
        supported.append("未记录活动性中枢神经系统转移")

    history = str(patient.get("medical_history", ""))
    if "活动性自身免疫" in history or "系统治疗" in history:
        conflicts.append("病史提示可能存在需要系统治疗的活动性自身免疫性疾病")

    consent = str(patient.get("informed_consent", "")).strip().lower()
    if consent == "yes":
        supported.append("记录已签署模拟知情同意")
    else:
        missing.append("模拟知情同意状态或日期需要确认")
        questions.append("请研究者核对知情同意签署时间是否早于研究程序。")

    pregnancy = str(patient.get("pregnancy_status", "")).strip().lower()
    if str(patient.get("sex", "")).upper() == "F" and pregnancy == "unknown":
        missing.append("妊娠状态需要确认")
        questions.append("请研究者确认是否需要妊娠检查及结果。")

    if conflicts:
        status = "Potential Mismatch"
    elif missing:
        status = "Needs Review"
    else:
        status = "Potential Match"
    assert status in ALLOWED_STATUSES
    suggestion = "交由研究者结合完整病历和原始资料确认。"
    if missing:
        suggestion = "补充缺失资料后，交由研究者进行人工审核。"
    if conflicts:
        suggestion = "优先请研究者核对潜在冲突及其临床背景，不得由系统作最终判断。"
    return {
        "patient_id": str(patient.get("patient_id", "Unknown")),
        "status": status,
        "supported": supported,
        "conflicts": conflicts,
        "missing": missing,
        "questions": questions or ["请研究者复核全部关键入排资料和原始记录。"],
        "suggestion": suggestion,
        "human_review_required": True,
    }


def screen_all(df: pd.DataFrame, criteria: dict | None = None) -> pd.DataFrame:
    results = [screen_patient(row.to_dict(), criteria) for _, row in df.iterrows()]
    return pd.DataFrame(results)

