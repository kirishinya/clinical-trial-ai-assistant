from __future__ import annotations

import io
import re
from typing import Callable

from pypdf import PdfReader


def extract_pdf_text(pdf_bytes: bytes) -> str:
    if not pdf_bytes:
        raise ValueError("PDF 文件为空")
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = "\n".join((page.extract_text() or "") for page in reader.pages).strip()
    except Exception as exc:
        raise ValueError("无法读取 PDF，请确认文件未加密且格式完整") from exc
    if len(text) < 80:
        raise ValueError("PDF 中没有足够的可提取文字，可能是扫描版；请人工确认或先进行 OCR")
    return text


def _item(value: str, source: str, needs_review: bool = False) -> dict:
    return {"value": value, "source": source, "needs_review": needs_review}


def default_protocol_result() -> dict:
    return {
        "basic_info": {
            "试验名称": _item("CTA-101 用于晚期非小细胞肺癌的疗效与安全性研究（完全虚构）", "1. 试验基本信息：试验名称"),
            "适应症": _item("不可手术的局部晚期或转移性非小细胞肺癌（NSCLC）", "1. 试验基本信息：适应症"),
            "研究阶段": _item("II 期、单臂、开放标签、模拟研究", "1. 试验基本信息：研究阶段"),
            "主要研究目的": _item("探索性评估 CTA-101 的客观缓解率，并描述安全性与耐受性。", "1. 试验基本信息：主要研究目的"),
        },
        "inclusion": [
            _item("已签署模拟知情同意，且日期早于研究程序", "2. 主要入选标准，第 1 条"),
            _item("年龄 18 至 75 周岁（含边界）", "2. 主要入选标准，第 2 条"),
            _item("组织学或细胞学确认的非小细胞肺癌", "2. 主要入选标准，第 3 条"),
            _item("疾病分期为 IIIB、IIIC 或 IV 期", "2. 主要入选标准，第 4 条"),
            _item("ECOG 体能状态评分为 0 或 1", "2. 主要入选标准，第 5 条"),
            _item("至少一个可测量病灶", "2. 主要入选标准，第 6 条"),
            _item("ANC≥1.5×10^9/L，血小板≥100×10^9/L，血红蛋白≥90 g/L，ALT≤2.5×ULN，肌酐清除率≥50 mL/min", "2. 主要入选标准，第 7 条"),
            _item("既往系统抗肿瘤治疗结束至少 28 天", "2. 主要入选标准，第 8 条"),
        ],
        "exclusion": [
            _item("活动性或需要立即治疗的中枢神经系统转移", "3. 主要排除标准，第 1 条"),
            _item("过去 2 年内需要系统治疗的活动性自身免疫性疾病", "3. 主要排除标准，第 2 条"),
            _item("未控制的活动性感染", "3. 主要排除标准，第 3 条"),
            _item("既往接受过 CTA-101", "3. 主要排除标准，第 4 条"),
            _item("妊娠或哺乳期；育龄受试者妊娠状态无法确认", "3. 主要排除标准，第 5 条"),
            _item("筛选期 QTcF 大于 470 ms", "3. 主要排除标准，第 6 条"),
        ],
        "visits": [
            _item("筛选期：D-28 至 D-1；知情同意、病史、ECOG、实验室、心电图、影像、妊娠检查", "4. 访视计划：筛选期"),
            _item("C1D1：资格复核、生命体征、实验室、给药、AE 与合并用药", "4. 访视计划：C1D1"),
            _item("C1D8：±1 天；生命体征、实验室、AE 与合并用药", "4. 访视计划：C1D8"),
            _item("后续周期 D1：每 21 天 ±2 天", "4. 访视计划：后续周期"),
            _item("肿瘤评估：每 6 周 ±7 天；治疗结束访视；末次给药后 30±3 天安全随访", "4. 访视计划：肿瘤评估及随访"),
        ],
        "safety": [
            _item("记录 AE/SAE 的术语、日期、严重程度、严重性、相关性、处理及转归", "5. 安全性观察，第 1 段"),
            _item("血常规、生化、尿常规、生命体征、12 导联心电图和妊娠检查", "5. 安全性观察，第 2 段"),
            _item("记录合并用药；SAE 在知悉后 24 小时内按模拟流程上报", "5. 安全性观察，第 3 段"),
        ],
        "metadata": {"mode": "Demo 规则解析", "requires_human_review": True},
    }


def parse_protocol_demo(text: str) -> dict:
    normalized = re.sub(r"\s+", " ", text)
    if "CTA-101" not in normalized or "非小细胞肺癌" not in normalized:
        unknown = _item("需要人工确认", "未在可提取文本中找到明确依据", True)
        return {
            "basic_info": {key: dict(unknown) for key in ["试验名称", "适应症", "研究阶段", "主要研究目的"]},
            "inclusion": [dict(unknown)], "exclusion": [dict(unknown)],
            "visits": [dict(unknown)], "safety": [dict(unknown)],
            "metadata": {"mode": "Demo 规则解析", "requires_human_review": True},
        }
    result = default_protocol_result()
    # Demo 解析只呈现能在原文中找到关键词的已知字段，其余必须人工确认。
    checks = {
        "试验名称": "CTA-101", "适应症": "非小细胞肺癌", "研究阶段": "II 期", "主要研究目的": "客观缓解率"
    }
    for field, keyword in checks.items():
        if keyword not in normalized:
            result["basic_info"][field] = _item("需要人工确认", f"未找到关键词：{keyword}", True)
    return result


def parse_protocol_ai(text: str, ai_callable: Callable[[str], dict]) -> dict:
    """Call an injected server-side AI parser; keeps protocol parsing testable."""
    result = ai_callable(text)
    if not isinstance(result, dict):
        raise ValueError("AI 返回结果格式不正确")
    result.setdefault("metadata", {})
    result["metadata"]["requires_human_review"] = True
    return result


def screening_criteria() -> dict:
    return {
        "age_min": 18, "age_max": 75,
        "diagnosis": "非小细胞肺癌", "stages": {"IIIB", "IIIC", "IV"},
        "ecog_allowed": {0, 1}, "anc_min": 1.5, "platelet_min": 100,
        "hemoglobin_min": 90, "alt_uln_max": 2.5, "crcl_min": 50,
        "washout_days_min": 28, "requires_measurable_lesion": True,
        "excludes_active_cns": True, "requires_consent": True,
    }

