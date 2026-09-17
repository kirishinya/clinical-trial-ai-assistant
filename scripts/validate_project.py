from __future__ import annotations

from pathlib import Path
import re
import sys

import pandas as pd
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate_files() -> None:
    required = [
        ROOT / "app.py",
        ROOT / "README.md",
        ROOT / "DEMO_GUIDE.md",
        ROOT / "PROJECT_EXPLANATION.md",
        DATA / "sample_protocol.pdf",
        DATA / "patient_data.csv",
        DATA / "source_data.csv",
        DATA / "edc_data.csv",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    require(not missing, f"缺少文件: {missing}")


def validate_simulated_data() -> None:
    patients = pd.read_csv(DATA / "patient_data.csv")
    source = pd.read_csv(DATA / "source_data.csv")
    edc = pd.read_csv(DATA / "edc_data.csv")
    require(len(patients) >= 10, "模拟患者少于 10 名")
    require(patients["patient_id"].astype(str).str.fullmatch(r"P\d{3}").all(), "存在非模拟格式 Patient ID")
    for name, frame in [("patient", patients), ("source", source), ("edc", edc)]:
        require("is_simulated" in frame.columns, f"{name} 缺少模拟数据标记")
        require(frame["is_simulated"].astype(str).str.lower().eq("true").all(), f"{name} 包含未标记为模拟的数据")


def validate_pdf() -> None:
    reader = PdfReader(str(DATA / "sample_protocol.pdf"))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    require(len(reader.pages) >= 2, "示例 Protocol 页数异常")
    require("CTA-DEMO-001" in text, "示例 Protocol 无法提取文本")
    require("模拟" in text, "示例 Protocol 未标注模拟性质")


def validate_no_committed_secret() -> None:
    excluded = {".env.local", ".env", "sample_protocol.pdf"}
    allowed_suffixes = {".py", ".md", ".txt", ".toml", ".yml", ".yaml", ".json", ".css", ".bat", ".example"}
    secret_pattern = re.compile(r"sk-[A-Za-z0-9_-]{20,}")
    leaks: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or ".venv" in path.parts or path.name in excluded:
            continue
        if path.suffix.lower() not in allowed_suffixes and path.name != ".env.example":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if secret_pattern.search(text):
            leaks.append(str(path.relative_to(ROOT)))
    require(not leaks, f"疑似密钥泄露: {leaks}")


def validate_portfolio_content() -> None:
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    demo_text = (ROOT / "DEMO_GUIDE.md").read_text(encoding="utf-8")
    require("项目亮点" in app_text and "规则引擎 + LLM 分工" in app_text, "首页缺少项目亮点")
    require("3 分钟演示顺序" in demo_text and "Human-in-the-loop" in demo_text, "演示顺序不完整")
    require(not (ROOT / "output").exists(), "仍存在重复输出目录")


def main() -> int:
    checks = [validate_files, validate_simulated_data, validate_pdf, validate_no_committed_secret, validate_portfolio_content]
    for check in checks:
        check()
        print(f"[PASS] {check.__name__}")
    print("[PASS] Project structure, simulated data, PDF, and secret checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
