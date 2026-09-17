from pathlib import Path

from streamlit.testing.v1 import AppTest

def test_streamlit_home_renders(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = AppTest.from_file(str(root / "app.py"), default_timeout=20).run()
    assert not app.exception
    markdown = "\n".join(element.value for element in app.markdown)
    assert "Clinical Trial AI Assistant" in markdown
    assert "本项目仅用于学习及求职作品展示" in markdown
    assert "项目亮点" in markdown
    assert "规则引擎 + LLM 分工" in markdown


def test_all_feature_pages_render(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = AppTest.from_file(str(root / "app.py"), default_timeout=30).run()

    for page in [
        "Protocol 智能解析",
        "模拟受试者初筛",
        "临床数据质量检查",
        "CRA AI Worklist",
        "项目说明 / Portfolio",
    ]:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, f"页面运行失败: {page}"


def test_protocol_and_quality_buttons(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = AppTest.from_file(str(root / "app.py"), default_timeout=30).run()

    app.sidebar.radio[0].set_value("Protocol 智能解析").run()
    next(button for button in app.button if button.label == "开始解析 Protocol").click().run()
    assert not app.exception
    assert any(success.value.startswith("解析完成") for success in app.success)

    app.sidebar.radio[0].set_value("临床数据质量检查").run()
    next(button for button in app.button if button.label == "开始数据质量检查").click().run()
    assert not app.exception
    assert any(metric.label == "发现问题" and int(metric.value) > 0 for metric in app.metric)
