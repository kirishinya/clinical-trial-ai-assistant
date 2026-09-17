from __future__ import annotations

from pathlib import Path
import io

import pandas as pd
import streamlit as st

from core.ai_service import AIServiceError, explain_screening_with_ai, get_ai_status, load_server_env, parse_protocol_with_ai
from core.data_quality import compare_source_edc
from core.protocol import extract_pdf_text, parse_protocol_demo, screening_criteria
from core.sample_data import SIMULATION_NOTICE, generate_all
from core.screening import screen_all, screen_patient
from core.worklist import apply_status, build_worklist

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

st.set_page_config(page_title="Clinical Trial AI Assistant", page_icon="🧬", layout="wide", initial_sidebar_state="auto")
st.markdown(f"<style>{(ROOT / 'assets' / 'style.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

if not (DATA / "patient_data.csv").exists():
    generate_all(ROOT)
AI_STATUS = load_server_env(ROOT)


def disclaimer() -> None:
    st.markdown(
        "<div class='disclaimer'>本项目仅用于学习及求职作品展示。使用全部为模拟数据。"
        "AI 结果仅作为辅助信息，最终入排标准判断和医学判断必须由研究者完成。</div>",
        unsafe_allow_html=True,
    )


def hitl_note() -> None:
    st.markdown("<div class='hitl'>👩‍⚕️ Human-in-the-loop：系统只整理和提示信息，研究者必须完成最终医学审核。</div>", unsafe_allow_html=True)


def read_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA / name)


def mode_selector() -> str:
    choices = ["Demo 模式"] + (["真实 AI 模式"] if AI_STATUS["configured"] else [])
    mode = st.sidebar.selectbox("运行模式", choices, help="Demo 模式无需网络；真实 AI 模式在服务器端调用模型。")
    if AI_STATUS["configured"]:
        st.sidebar.success(f"真实 AI 已配置 · {AI_STATUS['model']}")
    else:
        st.sidebar.info("未配置 API Key，Demo 模式仍可完整使用")
    return mode


def workflow(title: str, nodes: list[str]) -> None:
    parts: list[str] = []
    for index, node in enumerate(nodes):
        node_class = "node human" if "人工" in node else "node"
        parts.append(f"<div class='{node_class}'>{node}</div>")
        if index < len(nodes) - 1:
            parts.append("<div class='arrow'>→</div>")
    html = "".join(parts)
    st.markdown(f"#### {title}<div class='flow'>{html}</div>", unsafe_allow_html=True)


def render_evidence(item: dict) -> None:
    badge = " <span class='review'>需要人工确认</span>" if item.get("needs_review") else ""
    st.markdown(f"**{item.get('value', '需要人工确认')}**{badge}", unsafe_allow_html=True)
    st.markdown(f"<div class='source'>依据：{item.get('source', '需要人工确认')}</div>", unsafe_allow_html=True)


def home_page() -> None:
    st.markdown("""
    <div class="hero"><span class="eyebrow">CLINICAL OPERATIONS × AI PORTFOLIO</span>
    <h1>Clinical Trial AI Assistant<span>临床试验 AI 辅助助手</span></h1>
    <p>基于大语言模型与规则引擎的临床试验辅助 Demo</p>
    <p>本项目展示 AI 如何辅助完成 Protocol 信息提取、受试者初步筛选、临床数据质量检查以及 CRA 待办事项整理。</p></div>
    """, unsafe_allow_html=True)
    disclaimer()
    st.markdown("### 项目亮点")
    st.markdown("""
    <div class="highlight-grid">
      <div class="highlight"><span>HYBRID AI</span><b>规则引擎 + LLM 分工</b><p>确定性核查交给 Python 规则，长文本理解与辅助解释交给大模型。</p></div>
      <div class="highlight"><span>TRACEABLE</span><b>结果可追溯、可复核</b><p>Protocol 提取保留章节或原文依据，不确定内容明确要求人工确认。</p></div>
      <div class="highlight"><span>SAFETY BY DESIGN</span><b>医学判断权保留给人</b><p>AI 不决定最终入排资格，不修改 Source Data，关键步骤设置人工审核。</p></div>
      <div class="highlight"><span>END-TO-END</span><b>从发现问题到跟踪关闭</b><p>把数据异常转化为分级 CRA Worklist，并支持处理状态更新。</p></div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("### 核心功能")
    st.markdown("""
    <div class="grid4">
      <div class="feature"><span>01 · DOCUMENT</span><b>Protocol 智能解析</b><p>提取试验信息、入排标准、访视与安全性观察，并保留原文依据。</p></div>
      <div class="feature"><span>02 · SCREENING</span><b>模拟受试者初筛</b><p>逐条执行规则匹配，只提示可能匹配、需复核或可能不匹配。</p></div>
      <div class="feature"><span>03 · DATA QUALITY</span><b>临床数据质量检查</b><p>只读比较 Source Data 与 EDC，识别差异、缺失和风险。</p></div>
      <div class="feature"><span>04 · WORKLIST</span><b>CRA AI Worklist</b><p>把问题转化为分级待办、联系人和下一步动作。</p></div>
    </div>
    """, unsafe_allow_html=True)
    st.subheader("AI Agent Workflow")
    workflow("Protocol 与模拟初筛", ["Protocol", "文档解析", "入排标准提取", "患者数据读取", "规则匹配", "LLM 辅助解释", "人工审核", "初筛报告"])
    workflow("数据核查与问题关闭", ["Source + EDC", "数据读取", "字段比较", "异常检测", "风险分类", "CRA Worklist", "人工确认", "问题关闭"])


def protocol_page(mode: str) -> None:
    st.title("Protocol 智能解析")
    st.caption("上传 PDF 后提取结构化信息，并尽可能显示章节或原文依据。Demo 模式对示例 Protocol 提供稳定解析。")
    hitl_note()
    sample_bytes = (DATA / "sample_protocol.pdf").read_bytes()
    uploaded = st.file_uploader("上传模拟 Protocol PDF", type=["pdf"], help="请勿上传含真实患者信息的文件。")
    use_sample = st.checkbox("使用项目自带的完全虚构示例 Protocol", value=uploaded is None)
    active_bytes = uploaded.getvalue() if uploaded else (sample_bytes if use_sample else None)
    if active_bytes:
        st.download_button("下载示例 Protocol", sample_bytes, "sample_protocol.pdf", "application/pdf")
    if st.button("开始解析 Protocol", type="primary", disabled=active_bytes is None):
        try:
            text = extract_pdf_text(active_bytes)
            with st.spinner("AI 正在分析 Protocol…" if mode == "真实 AI 模式" else "正在读取并解析 Protocol…"):
                result = parse_protocol_with_ai(text) if mode == "真实 AI 模式" else parse_protocol_demo(text)
            st.session_state["protocol_result"] = result
            st.session_state["protocol_text"] = text
        except (ValueError, AIServiceError) as exc:
            st.error(str(exc))
    result = st.session_state.get("protocol_result")
    if not result:
        st.info("请选择示例文件或上传 PDF，然后点击“开始解析 Protocol”。")
        return
    st.success(f"解析完成 · {result.get('metadata', {}).get('mode', mode)}")
    st.subheader("试验基本信息")
    cols = st.columns(2)
    for index, (label, item) in enumerate(result["basic_info"].items()):
        with cols[index % 2]:
            with st.container(border=True):
                st.markdown(f"##### {label}")
                render_evidence(item)
    for title, key in [("入选标准", "inclusion"), ("排除标准", "exclusion"), ("访视计划", "visits"), ("安全性观察", "safety")]:
        st.subheader(title)
        for index, item in enumerate(result[key], 1):
            with st.container(border=True):
                st.markdown(f"**{index}.**")
                render_evidence(item)
    disclaimer()


def screening_page(mode: str) -> None:
    st.title("模拟受试者初筛")
    st.caption("所有受试者均为完全虚构数据。规则结果只用于整理信息，不代表最终资格判断。")
    hitl_note()
    patients = read_csv("patient_data.csv")
    patient_id = st.selectbox("选择模拟患者", patients["patient_id"].tolist())
    patient = patients.loc[patients["patient_id"] == patient_id].iloc[0].to_dict()
    with st.expander("查看模拟患者资料", expanded=True):
        st.dataframe(pd.DataFrame([patient]), use_container_width=True, hide_index=True)
    result = screen_patient(patient, screening_criteria())
    cls = {"Potential Match": "match", "Needs Review": "reviewing", "Potential Mismatch": "mismatch"}[result["status"]]
    st.markdown(f"### 初步状态：<span class='status {cls}'>{result['status']}</span>", unsafe_allow_html=True)
    left, right = st.columns(2)
    with left:
        st.markdown("#### 已支持的标准")
        for item in result["supported"]:
            st.success(item)
        st.markdown("#### 缺少的信息")
        for item in result["missing"] or ["未发现明显缺失项"]:
            if result["missing"]:
                st.warning(item)
            else:
                st.info(item)
    with right:
        st.markdown("#### 可能冲突的标准")
        for item in result["conflicts"] or ["规则未识别到明确冲突"]:
            if result["conflicts"]:
                st.error(item)
            else:
                st.info(item)
        st.markdown("#### 需要研究者确认的问题")
        for item in result["questions"]:
            st.write(f"- {item}")
    st.info(f"建议：{result['suggestion']}")
    if mode == "真实 AI 模式" and st.button("生成 AI 辅助解释"):
        try:
            with st.spinner("AI 正在整理需确认问题…"):
                explanation = explain_screening_with_ai(patient, result)
            st.write(explanation["summary"])
            for question in explanation["questions_for_investigator"]:
                st.write(f"- {question}")
            st.warning(explanation["caution"])
        except AIServiceError as exc:
            st.error(str(exc))
    summary = screen_all(patients)
    st.subheader("全部模拟患者概览")
    st.dataframe(summary[["patient_id", "status"]].rename(columns={"patient_id": "Patient ID", "status": "初步状态"}), use_container_width=True, hide_index=True)
    disclaimer()


def quality_page() -> None:
    st.title("临床数据质量检查")
    st.caption("使用 Pandas 只读比较 Source Data 与 EDC / eCRF 数据；程序不会修改任何原始数据。")
    hitl_note()
    source, edc = read_csv("source_data.csv"), read_csv("edc_data.csv")
    a, b = st.columns(2)
    with a:
        st.markdown("#### Source Data（模拟）")
        st.dataframe(source, use_container_width=True, hide_index=True, height=260)
        st.download_button("下载 source_data.csv", (DATA / "source_data.csv").read_bytes(), "source_data.csv", "text/csv")
    with b:
        st.markdown("#### EDC Data（模拟）")
        st.dataframe(edc, use_container_width=True, hide_index=True, height=260)
        st.download_button("下载 edc_data.csv", (DATA / "edc_data.csv").read_bytes(), "edc_data.csv", "text/csv")
    if st.button("开始数据质量检查", type="primary") or "quality_issues" in st.session_state:
        issues = compare_source_edc(source, edc)
        st.session_state["quality_issues"] = issues
        c1, c2, c3 = st.columns(3)
        c1.metric("发现问题", len(issues))
        c2.metric("High Risk", int((issues["风险等级"] == "High").sum()))
        c3.metric("涉及患者", issues["Patient ID"].nunique())
        st.dataframe(issues, use_container_width=True, hide_index=True)
        st.download_button("下载数据核查结果", issues.to_csv(index=False).encode("utf-8-sig"), "data_quality_issues.csv", "text/csv")
        st.warning("以上仅为异常提示。请由 CRA / CRC 核对原始记录，程序不会直接修改医学源数据。")


def worklist_page() -> None:
    st.title("CRA AI Worklist")
    st.caption("根据数据核查和模拟初筛结果自动整理待办。状态只保存在当前浏览器会话中。")
    hitl_note()
    issues = st.session_state.get("quality_issues")
    if issues is None:
        issues = compare_source_edc(read_csv("source_data.csv"), read_csv("edc_data.csv"))
    screenings = screen_all(read_csv("patient_data.csv"))
    base = build_worklist(issues, screenings)
    status_map = st.session_state.setdefault("worklist_status", {})
    worklist = apply_status(base, status_map)
    f1, f2 = st.columns(2)
    priority = f1.multiselect("优先级筛选", ["High Priority", "Medium Priority", "Low Priority"], default=["High Priority", "Medium Priority", "Low Priority"])
    status_filter = f2.multiselect("状态筛选", ["Open", "In Progress", "Closed"], default=["Open", "In Progress", "Closed"])
    visible = worklist[worklist["优先级"].isin(priority) & worklist["状态"].isin(status_filter)]
    metrics = st.columns(3)
    for col, name in zip(metrics, ["Open", "In Progress", "Closed"]):
        col.metric(name, int((worklist["状态"] == name).sum()))
    for index, item in visible.iterrows():
        with st.container(border=True):
            top, state = st.columns([4, 1])
            top.markdown(f"#### {item['优先级']} · {item['Patient ID']}")
            top.write(f"**问题：** {item['问题']}")
            top.write(f"**建议联系对象：** {item['建议联系对象']}")
            top.write(f"**下一步：** {item['建议下一步动作']}")
            selected = state.selectbox("状态", ["Open", "In Progress", "Closed"], index=["Open", "In Progress", "Closed"].index(item["状态"]), key=f"status_{index}")
            if selected != item["状态"]:
                status_map[index] = selected
                st.session_state["worklist_status"] = status_map
                st.rerun()
    st.download_button("下载当前 Worklist", worklist.to_csv(index=False).encode("utf-8-sig"), "cra_worklist.csv", "text/csv")


def portfolio_page() -> None:
    st.title("项目说明 / Portfolio")
    sections = {
        "项目背景": "临床试验中存在大量 Protocol 信息阅读、受试者资料整理、数据核查以及问题跟进工作。",
        "业务问题": "人工阅读 Protocol 耗时；初筛需要重复核对大量信息；Source 与 EDC 核查存在重复工作；CRA 需要持续跟踪多个问题。",
        "解决方案": "通过 Python + Pandas + LLM + Agent 工作流，辅助完成信息提取、初步匹配、数据质量检查和待办事项生成。",
        "技术实现": "Streamlit 提供交互界面，Pandas 负责表格处理，规则引擎处理确定性检查，LLM 仅用于长文本结构化和辅助解释。",
        "项目边界": "AI 不进行最终医学判断，不修改 Source Data，不决定受试者最终是否入组。所有医学判断均需研究者人工确认。",
        "项目价值": "把高频、重复、可标准化的临床运营步骤拆成可审计工作流，同时保留人工审核节点。",
    }
    for title, content in sections.items():
        st.markdown(f"<div class='portfolio-card'><h3>{title}</h3><p>{content}</p></div>", unsafe_allow_html=True)
    st.subheader("我在项目中展示的能力")
    st.write("Clinical Operations 业务理解 · Python 数据处理 · Prompt 标准化 · Agent 工作流 · Human-in-the-loop · 数据质量意识")
    disclaimer()


st.sidebar.markdown("## 🧬 Clinical Trial AI")
st.sidebar.caption("临床试验 AI 辅助助手")
page = st.sidebar.radio("功能导航", ["首页", "Protocol 智能解析", "模拟受试者初筛", "临床数据质量检查", "CRA AI Worklist", "项目说明 / Portfolio"])
mode = mode_selector()
st.sidebar.divider()
st.sidebar.caption(SIMULATION_NOTICE)

if page == "首页": home_page()
elif page == "Protocol 智能解析": protocol_page(mode)
elif page == "模拟受试者初筛": screening_page(mode)
elif page == "临床数据质量检查": quality_page()
elif page == "CRA AI Worklist": worklist_page()
else: portfolio_page()
