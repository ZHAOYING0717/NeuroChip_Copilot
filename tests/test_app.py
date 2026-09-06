from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def test_dashboard_modes_render_without_exceptions():
    app = AppTest.from_file(str(APP_PATH), default_timeout=60).run(timeout=60)
    assert not app.exception
    assert len(app.metric) >= 6
    assert len(app.tabs) == 5
    assert len(app.get("download_button")) == 2
    assert any(subheader.value == "系统级验证证据" for subheader in app.subheader)
    assert [option.content for option in app.get("button_group")[0].options] == ["单记录", "干预评价", "项目"]
    assert app.selectbox[0].label == "公共数据集（仅供示例）"
    assert app.selectbox[0].options == [
        "前脑类器官参考（45条）",
        "脑类器官地西泮（19条）",
        "GIN二维神经网络（198条）",
        "Trujillo皮层类器官（72条）",
    ]

    app.get("button_group")[0].set_value(["干预评价"]).run(timeout=120)
    assert not app.exception
    assert app.selectbox[0].label == "公共数据集（仅供示例）"
    assert [selectbox.label for selectbox in app.selectbox[1:3]] == ["选择基线记录", "选择处理后记录"]
    assert len(app.tabs) == 6
    assert any(metric.label == "多维影响幅度" for metric in app.metric)

    app.get("button_group")[0].set_value(["项目"]).run(timeout=60)
    assert not app.exception
    assert any(subheader.value == "新建项目" for subheader in app.subheader)


def test_public_demo_bundle_runs_without_interim_data(monkeypatch):
    monkeypatch.setenv("NEUROCHIP_DEMO_ONLY", "1")
    app = AppTest.from_file(str(APP_PATH), default_timeout=60).run(timeout=60)
    assert not app.exception
    assert app.selectbox[0].options == [
        "前脑类器官参考（演示1/完整45）",
        "脑类器官地西泮（演示2/完整19）",
        "GIN二维神经网络（演示1/完整198）",
        "Trujillo皮层类器官（演示2/完整72）",
    ]
    assert app.selectbox[1].value == "fs363-org0"
    assert len(app.metric) >= 6
