from __future__ import annotations

import pandas as pd

PRIORITY_MAP = {"High": "High Priority", "Medium": "Medium Priority", "Low": "Low Priority"}


def _contact(issue_type: str, field: str) -> str:
    combined = f"{issue_type} {field}"
    if "SAE" in combined or "AE" in combined or "知情同意" in combined:
        return "研究者 + CRC"
    if "实验室" in combined or "Hemoglobin" in combined or "ALT" in combined or "单位" in combined:
        return "实验室 + CRC"
    if "用药" in combined or "Medication" in combined:
        return "CRC / 药房"
    return "CRC"


def build_worklist(issues_df: pd.DataFrame, screening_df: pd.DataFrame | None = None) -> pd.DataFrame:
    rows: list[dict] = []
    for _, item in issues_df.iterrows():
        rows.append({
            "Patient ID": item["Patient ID"],
            "优先级": PRIORITY_MAP.get(item["风险等级"], "Low Priority"),
            "问题": f"{item['问题类型']}：{item['字段名称']}",
            "建议联系对象": _contact(str(item["问题类型"]), str(item["字段名称"])),
            "建议下一步动作": item["建议处理方式"],
            "状态": "Open",
            "来源": "Source vs EDC 数据核查",
        })
    if screening_df is not None and not screening_df.empty:
        for _, item in screening_df.iterrows():
            if item["status"] == "Potential Match":
                continue
            missing = item["missing"] if isinstance(item["missing"], list) else []
            conflicts = item["conflicts"] if isinstance(item["conflicts"], list) else []
            detail = (conflicts + missing)[0] if conflicts or missing else "关键入排资料需要复核"
            rows.append({
                "Patient ID": item["patient_id"],
                "优先级": "High Priority" if conflicts else "Medium Priority",
                "问题": f"初筛人工审核：{detail}",
                "建议联系对象": "研究者 + CRC",
                "建议下一步动作": "补充原始资料并由研究者逐条确认入排标准；系统不得作最终判断。",
                "状态": "Open",
                "来源": "模拟受试者初筛",
            })
    columns = ["Patient ID", "优先级", "问题", "建议联系对象", "建议下一步动作", "状态", "来源"]
    if not rows:
        return pd.DataFrame(columns=columns)
    result = pd.DataFrame(rows, columns=columns)
    rank = {"High Priority": 0, "Medium Priority": 1, "Low Priority": 2}
    return result.assign(_rank=result["优先级"].map(rank)).sort_values(["_rank", "Patient ID"]).drop(columns="_rank").reset_index(drop=True)


def apply_status(worklist: pd.DataFrame, status_map: dict[int, str]) -> pd.DataFrame:
    result = worklist.copy()
    for index, status in status_map.items():
        if index in result.index and status in {"Open", "In Progress", "Closed"}:
            result.at[index, "状态"] = status
    return result

