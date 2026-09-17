from __future__ import annotations

from pathlib import Path
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

SIMULATION_NOTICE = "完全虚构的模拟数据，仅用于学习及求职作品展示，不代表任何真实患者或真实临床试验。"


def _font_name() -> str:
    candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
    ]
    for path in candidates:
        if path.exists():
            try:
                pdfmetrics.registerFont(TTFont("ClinicalChinese", str(path), subfontIndex=0))
                return "ClinicalChinese"
            except Exception:
                continue
    return "Helvetica"


def patient_rows() -> list[dict]:
    base = {
        "is_simulated": True,
        "diagnosis": "非小细胞肺癌",
        "stage": "IV",
        "ECOG": 1,
        "ANC_10e9_L": 2.4,
        "platelet_10e9_L": 165,
        "hemoglobin_g_L": 112,
        "ALT_ULN_ratio": 1.2,
        "creatinine_clearance_mL_min": 78,
        "measurable_lesion": "Yes",
        "previous_treatment": "含铂化疗",
        "days_since_last_treatment": 35,
        "current_medication": "无影响入排标准的合并用药",
        "medical_history": "高血压，控制稳定",
        "active_CNS_metastasis": "No",
        "informed_consent": "Yes",
        "pregnancy_status": "Not applicable",
    }
    overrides = [
        {"patient_id": "P001", "age": 58, "sex": "M", "ECOG": 0},
        {"patient_id": "P002", "age": 64, "sex": "F", "ECOG": 2},
        {"patient_id": "P003", "age": 55, "sex": "M", "ECOG": None, "days_since_last_treatment": None},
        {"patient_id": "P004", "age": 80, "sex": "M"},
        {"patient_id": "P005", "age": 49, "sex": "F", "active_CNS_metastasis": "Yes"},
        {"patient_id": "P006", "age": 67, "sex": "M", "creatinine_clearance_mL_min": 45},
        {"patient_id": "P007", "age": 61, "sex": "F", "stage": "IIIB", "ECOG": 1},
        {"patient_id": "P008", "age": 53, "sex": "M", "diagnosis": "小细胞肺癌"},
        {"patient_id": "P009", "age": 72, "sex": "F", "stage": "IIIA"},
        {"patient_id": "P010", "age": 45, "sex": "M", "measurable_lesion": "No"},
        {"patient_id": "P011", "age": 60, "sex": "F", "medical_history": "活动性自身免疫性疾病，近期需系统治疗", "current_medication": "泼尼松 20 mg/日"},
        {"patient_id": "P012", "age": 39, "sex": "F", "pregnancy_status": "Unknown", "informed_consent": "Unknown"},
    ]
    rows = []
    for item in overrides:
        row = {**base, **item}
        row["laboratory_results"] = (
            f"ANC={row['ANC_10e9_L']}x10^9/L; PLT={row['platelet_10e9_L']}x10^9/L; "
            f"Hb={row['hemoglobin_g_L']}g/L; ALT={row['ALT_ULN_ratio']}xULN; "
            f"CrCl={row['creatinine_clearance_mL_min']}mL/min"
        )
        rows.append(row)
    return rows


def source_rows() -> list[dict]:
    rows = []
    for index in range(1, 11):
        rows.append({
            "record_id": f"SRC-{index:03d}", "patient_id": f"P{index:03d}", "is_simulated": True,
            "visit": "Screening", "visit_date": f"2026-08-{9 + index:02d}",
            "hemoglobin": 108 + index, "hemoglobin_unit": "g/L", "ALT_U_L": 24 + index,
            "concomitant_medication": "无" if index != 7 else "氨氯地平 5 mg qd",
            "AE_term": "" if index != 8 else "恶心", "AE_grade": "" if index != 8 else "1",
            "ae_seriousness": "Not serious" if index != 10 else "SAE",
            "informed_consent_date": f"2026-08-{7 + index:02d}",
        })
    rows[9]["AE_term"] = "肺炎住院"
    rows[9]["AE_grade"] = "3"
    return rows


def edc_rows() -> list[dict]:
    rows = [dict(row) for row in source_rows()]
    for index, row in enumerate(rows, start=1):
        row["record_id"] = f"EDC-{index:03d}"
    rows[1]["visit_date"] = "2026-08-21"            # 日期不一致
    rows[2]["hemoglobin"] = 126                       # 实验室结果不一致
    rows[3]["hemoglobin"] = None                      # 缺失数据
    rows[5]["hemoglobin_unit"] = "g/dL"              # 单位错误
    rows[6]["concomitant_medication"] = "无"         # 用药不一致
    rows[7]["AE_term"] = ""                          # AE 信息缺失
    rows[8]["informed_consent_date"] = "2026-08-25"  # 知情同意日期异常
    rows[9]["AE_term"] = ""
    rows[9]["AE_grade"] = ""
    rows[9]["ae_seriousness"] = ""
    rows.append(dict(rows[4]))                          # 重复数据
    rows[-1]["record_id"] = "EDC-011"
    return rows


def _draw_page_number(canvas, doc, font: str) -> None:
    canvas.saveState()
    canvas.setFont(font, 8)
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.drawString(20 * mm, 12 * mm, "SIMULATED PROTOCOL - NOT FOR CLINICAL USE")
    canvas.drawRightString(190 * mm, 12 * mm, f"Page {doc.page}")
    canvas.restoreState()


def create_protocol_pdf(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    font = _font_name()
    styles = getSampleStyleSheet()
    title = ParagraphStyle("TitleCN", parent=styles["Title"], fontName=font, fontSize=22, leading=30, alignment=TA_CENTER, textColor=colors.HexColor("#0F4C5C"), spaceAfter=12)
    heading = ParagraphStyle("HeadingCN", parent=styles["Heading2"], fontName=font, fontSize=15, leading=22, textColor=colors.HexColor("#16697A"), spaceBefore=12, spaceAfter=8)
    body = ParagraphStyle("BodyCN", parent=styles["BodyText"], fontName=font, fontSize=10.5, leading=17, textColor=colors.HexColor("#253746"), spaceAfter=6)
    warning = ParagraphStyle("WarningCN", parent=body, backColor=colors.HexColor("#FFF4E5"), borderColor=colors.HexColor("#F59E0B"), borderWidth=1, borderPadding=8, textColor=colors.HexColor("#7C2D12"), alignment=TA_CENTER)

    story = [
        Spacer(1, 20 * mm), Paragraph("Clinical Trial AI Assistant", title),
        Paragraph("模拟临床试验方案 / Sample Protocol", title),
        Paragraph("方案编号：CTA-DEMO-001　版本：1.0　日期：2026-09-17", body),
        Spacer(1, 10 * mm), Paragraph(SIMULATION_NOTICE, warning),
        Spacer(1, 22 * mm), Paragraph("本文件禁止用于真实临床试验、受试者筛选或医疗决策。", warning),
        PageBreak(),
        Paragraph("1. 试验基本信息", heading),
        Paragraph("试验名称：CTA-101 用于晚期非小细胞肺癌的疗效与安全性研究（完全虚构）", body),
        Paragraph("适应症：不可手术的局部晚期或转移性非小细胞肺癌（NSCLC）", body),
        Paragraph("研究阶段：II 期、单臂、开放标签、模拟研究", body),
        Paragraph("主要研究目的：探索性评估 CTA-101 的客观缓解率，并描述安全性与耐受性。", body),
        Paragraph("2. 主要入选标准", heading),
        *[Paragraph(f"{i}. {text}", body) for i, text in enumerate([
            "签署模拟知情同意，且日期早于任何模拟研究程序。",
            "年龄 18 至 75 周岁（含边界）。",
            "经组织学或细胞学确认的非小细胞肺癌。",
            "疾病分期为 IIIB、IIIC 或 IV 期。",
            "ECOG 体能状态评分为 0 或 1。",
            "至少有一个符合 RECIST 1.1 的可测量病灶。",
            "器官功能：ANC ≥1.5×10^9/L；血小板 ≥100×10^9/L；血红蛋白 ≥90 g/L；ALT ≤2.5×ULN；肌酐清除率 ≥50 mL/min。",
            "既往系统抗肿瘤治疗结束至首次给药至少 28 天。",
        ], 1)],
        Paragraph("3. 主要排除标准", heading),
        *[Paragraph(f"{i}. {text}", body) for i, text in enumerate([
            "活动性或需要立即治疗的中枢神经系统转移。",
            "过去 2 年内需要系统治疗的活动性自身免疫性疾病。",
            "未控制的活动性感染。",
            "既往接受过 CTA-101。",
            "妊娠或哺乳期；育龄受试者妊娠状态无法确认。",
            "筛选期 QTcF 大于 470 ms。",
        ], 1)],
        PageBreak(),
        Paragraph("4. 访视计划", heading),
    ]
    table_data = [
        ["访视", "时间窗", "主要检查项目"],
        ["筛选期", "D-28 至 D-1", "模拟知情同意、病史、ECOG、实验室、心电图、影像、妊娠检查"],
        ["C1D1", "首次给药日", "资格复核、生命体征、实验室、给药、AE 与合并用药"],
        ["C1D8", "±1 天", "生命体征、实验室、AE 与合并用药"],
        ["后续周期 D1", "每 21 天 ±2 天", "ECOG、实验室、给药、AE 与合并用药"],
        ["肿瘤评估", "每 6 周 ±7 天", "CT/MRI 影像评估"],
        ["治疗结束", "末次给药后 7 天内", "体格检查、实验室、心电图、AE"],
        ["安全随访", "末次给药后 30±3 天", "AE/SAE、合并用药、生存状态"],
    ]
    table = Table([[Paragraph(str(cell), body) for cell in row] for row in table_data], colWidths=[30 * mm, 35 * mm, 105 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DFF3F5")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0F4C5C")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B7CED3")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([
        table,
        Paragraph("5. 安全性观察", heading),
        Paragraph("每次访视记录 AE/SAE 的术语、开始日期、严重程度、严重性、与研究药物关系、处理及转归。", body),
        Paragraph("定期检查血常规、生化、尿常规、生命体征和 12 导联心电图；育龄女性按访视计划进行妊娠检查。", body),
        Paragraph("合并用药需记录药名、剂量、频次、开始和结束日期及适应症。SAE 应在知悉后 24 小时内按模拟流程上报。", body),
        Paragraph("6. 人工审核要求", heading),
        Paragraph("所有入排标准和安全性信息必须由研究者结合完整原始资料确认。自动化工具仅用于提示可能匹配、可能冲突或信息缺失，不能作最终判断。", warning),
    ])
    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=18 * mm, bottomMargin=20 * mm, title="CTA-DEMO-001 Simulated Protocol", author="Clinical Trial AI Assistant")
    doc.build(story, onFirstPage=lambda c, d: _draw_page_number(c, d, font), onLaterPages=lambda c, d: _draw_page_number(c, d, font))
    return path


def generate_all(base_dir: Path) -> dict[str, Path]:
    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    patients = pd.DataFrame(patient_rows())
    source = pd.DataFrame(source_rows())
    edc = pd.DataFrame(edc_rows())
    paths = {
        "patient_data": data_dir / "patient_data.csv",
        "source_data": data_dir / "source_data.csv",
        "edc_data": data_dir / "edc_data.csv",
        "protocol": data_dir / "sample_protocol.pdf",
    }
    patients.to_csv(paths["patient_data"], index=False, encoding="utf-8-sig")
    source.to_csv(paths["source_data"], index=False, encoding="utf-8-sig")
    edc.to_csv(paths["edc_data"], index=False, encoding="utf-8-sig")
    create_protocol_pdf(paths["protocol"])
    return paths
