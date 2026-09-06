"""Create the static 16:9 slides used by the competition demo video."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "video" / "slides"
ASSETS = ROOT / "docs" / "assets"

WIDTH = 1280
HEIGHT = 720
BG = "#f7f8fa"
PAPER = "#ffffff"
INK = "#20262c"
MUTED = "#59636d"
LINE = "#d8dde2"
CORAL = "#d94f45"
TEAL = "#177681"
BLUE = "#2f67ad"
GOLD = "#b67808"
GREEN = "#507d34"

FONT_REGULAR = Path("C:/Windows/Fonts/msyh.ttc")
FONT_BOLD = Path("C:/Windows/Fonts/msyhbd.ttc")
FONT_MONO = Path("C:/Windows/Fonts/consola.ttf")


def font(size: int, *, bold: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_MONO if mono else (FONT_BOLD if bold else FONT_REGULAR)
    return ImageFont.truetype(str(path), size=size)


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    return image, ImageDraw.Draw(image)


def text_width(draw: ImageDraw.ImageDraw, text: str, selected_font: ImageFont.FreeTypeFont) -> float:
    return draw.textlength(text, font=selected_font)


def wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    selected_font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        current = ""
        for char in paragraph:
            candidate = current + char
            if current and text_width(draw, candidate, selected_font) > max_width:
                lines.append(current.rstrip())
                current = char.lstrip()
            else:
                current = candidate
        lines.append(current.rstrip())
    return lines


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    selected_font: ImageFont.FreeTypeFont,
    fill: str,
    max_width: int,
    line_gap: int = 8,
) -> int:
    x, y = xy
    line_height = selected_font.size + line_gap
    for line in wrap_text(draw, text, selected_font, max_width):
        draw.text((x, y), line, font=selected_font, fill=fill)
        y += line_height
    return y


def header(
    draw: ImageDraw.ImageDraw,
    title: str,
    subtitle: str = "",
    kicker: str = "NEUROCHIP COPILOT",
) -> None:
    draw.rectangle((48, 42, 58, 112), fill=CORAL)
    draw.text((78, 38), kicker, font=font(16, bold=True), fill=CORAL)
    draw.text((78, 64), title, font=font(38, bold=True), fill=INK)
    if subtitle:
        draw.text((78, 113), subtitle, font=font(19), fill=MUTED)


def footer(draw: ImageDraw.ImageDraw, section: str) -> None:
    draw.line((48, 682, 1232, 682), fill=LINE, width=2)
    draw.text((48, 691), "AI4S · END-TO-END SYSTEM", font=font(13, bold=True), fill=MUTED)
    label_width = text_width(draw, section, font(13, bold=True))
    draw.text((1232 - label_width, 691), section, font=font(13, bold=True), fill=MUTED)


def paste_contain(
    target: Image.Image,
    source: Image.Image,
    box: tuple[int, int, int, int],
    *,
    background: str = PAPER,
) -> None:
    x0, y0, x1, y1 = box
    width = x1 - x0
    height = y1 - y0
    scale = min(width / source.width, height / source.height)
    resized = source.resize(
        (max(1, round(source.width * scale)), max(1, round(source.height * scale))),
        Image.Resampling.LANCZOS,
    )
    holder = Image.new("RGB", (width, height), background)
    holder.paste(resized, ((width - resized.width) // 2, (height - resized.height) // 2))
    target.paste(holder, (x0, y0))


def metric(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    label: str,
    value: str,
    detail: str,
    color: str,
) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=8, fill=PAPER, outline=LINE, width=2)
    draw.rectangle((x0, y0, x0 + 8, y1), fill=color)
    draw.text((x0 + 26, y0 + 20), label, font=font(17, bold=True), fill=MUTED)
    draw.text((x0 + 26, y0 + 58), value, font=font(40, bold=True), fill=INK)
    draw_wrapped(draw, (x0 + 26, y0 + 115), detail, font(16), MUTED, x1 - x0 - 52, 5)


def slide_intro() -> Image.Image:
    image, draw = canvas()
    header(
        draw,
        "NeuroChip Copilot",
        "End-to-End System：从检测后 MEA 事件到质量控制、功能表型、多维干预评价与报告",
        "COMPETITION DEMO",
    )
    architecture = Image.open(ASSETS / "figure0_architecture.png").convert("RGB")
    architecture = architecture.crop((0, 94, architecture.width, architecture.height))
    paste_contain(image, architecture, (48, 172, 1232, 638))
    draw.rounded_rectangle((48, 636, 1232, 666), radius=5, fill="#fbeceb")
    draw.text(
        (66, 640),
        "从数据可用性到功能状态、异常优先级和目标相关干预效应，形成可复现研究流程",
        font=font(16, bold=True),
        fill="#9b342d",
    )
    footer(draw, "01 / OVERVIEW")
    return image


def slide_results() -> Image.Image:
    image, draw = canvas()
    header(draw, "四套公开数据，五层证据", "源值复现、分组留出、留一类器官和两类冻结外部检验")
    boxes = [
        (48, 177, 330, 390),
        (348, 177, 630, 390),
        (648, 177, 930, 390),
        (948, 177, 1230, 390),
    ]
    metric(draw, boxes[0], "源数据复现", "< 1.1e-15", "放电率与 20 ms STTC\n最大绝对误差", TEAL)
    metric(draw, boxes[1], "异常检测", "AUROC 0.858", "16 组五折留出\n95% CI 0.796-0.915", BLUE)
    metric(draw, boxes[2], "辅助响应 v2", "ρ 0.904", "留一类器官验证\n高剂量 AUC 0.964", GOLD)
    metric(draw, boxes[3], "冻结外部检验", ".952 / .889", "二维网络药理\n独立皮层类器官 AUC", CORAL)
    draw.rounded_rectangle((48, 425, 1230, 640), radius=8, fill=PAPER, outline=LINE, width=2)
    draw.text((76, 451), "验证结构", font=font(20, bold=True), fill=INK)
    steps = [
        ("45 条记录", "发布者特征逐项复现", TEAL),
        ("45 + 135", "来源组隔离异常检验", BLUE),
        ("19 个条件", "四次留一类器官外推", GOLD),
        ("66 个孔", "冻结二维网络检验", CORAL),
        ("12 个配对", "冻结类器官协议检验", GREEN),
    ]
    x = 70
    for index, (name, detail, color) in enumerate(steps):
        draw.ellipse((x, 514, x + 38, 552), fill=color)
        number = str(index + 1)
        number_width = text_width(draw, number, font(18, bold=True))
        draw.text((x + (38 - number_width) / 2, 520), number, font=font(18, bold=True), fill=PAPER)
        draw.text((x + 48, 503), name, font=font(17, bold=True), fill=INK)
        draw_wrapped(draw, (x + 48, 536), detail, font(13), MUTED, 158, 4)
        x += 226
    footer(draw, "02 / RESULTS")
    return image


def slide_data() -> Image.Image:
    image, draw = canvas()
    header(draw, "公开、可追溯、边界清楚的数据基础", "下载地址、许可、文件大小与校验值均由机器可读清单管理")
    cards = [
        (48, 166, 625, 350, TEAL, "数据集 A", "前脑类器官 MEA", "45 条 · 参考与异常验证", "10.5281/zenodo.20286251", "CC BY 4.0"),
        (655, 166, 1232, 350, GOLD, "数据集 B", "脑类器官地西泮", "4 个类器官 · 19 个条件", "10.25349/D9031Z", "CC0"),
        (48, 373, 625, 557, CORAL, "数据集 C", "人源与大鼠二维网络", "66 个孔 · 药理与 TTX", "10.12751/g-node.wvr3jf", "CC BY 4.0"),
        (655, 373, 1232, 557, BLUE, "数据集 D", "独立皮层类器官", "12 对 · 处理与自然漂移", "10.5281/zenodo.4751759", "CC BY 4.0"),
    ]
    for x0, y0, x1, y1, color, label, title, count, doi, license_name in cards:
        draw.rounded_rectangle((x0, y0, x1, y1), radius=8, fill=PAPER, outline=LINE, width=2)
        draw.rectangle((x0, y0, x0 + 8, y1), fill=color)
        draw.text((x0 + 24, y0 + 18), label, font=font(14, bold=True), fill=color)
        draw.text((x0 + 24, y0 + 50), title, font=font(21, bold=True), fill=INK)
        draw.text((x0 + 24, y0 + 91), count, font=font(16), fill=MUTED)
        draw.text((x0 + 24, y0 + 128), doi, font=font(12, mono=True), fill=INK)
        draw.rounded_rectangle((x1 - 130, y0 + 132, x1 - 20, y0 + 164), radius=5, fill="#eef1f3")
        draw.text((x1 - 118, y0 + 138), license_name, font=font(13, bold=True), fill=MUTED)
    draw.rounded_rectangle((48, 580, 1232, 660), radius=8, fill="#fff0ef", outline="#efb3ae", width=2)
    draw.text((70, 597), "分析边界", font=font(17, bold=True), fill="#a73931")
    draw_wrapped(
        draw,
        (190, 596),
        "事件输入不证明原始电压质量；目标相关评价不构成临床、药效或毒理安全结论。",
        font(17),
        "#71312d",
        1000,
        8,
    )
    footer(draw, "04 / DATA & SCOPE")
    return image


def slide_model() -> Image.Image:
    image, draw = canvas()
    draw.rectangle((0, 0, WIDTH, 72), fill=PAPER)
    draw.rectangle((0, 0, 10, 72), fill=BLUE)
    draw.text((34, 15), "分组留出异常检测与精确源值复现", font=font(31, bold=True), fill=INK)
    draw.text((939, 23), "Isolation Forest · 500 trees", font=font(16, bold=True), fill=BLUE)
    figure = Image.open(ASSETS / "figure1_validation.png").convert("RGB")
    paste_contain(image, figure, (116, 77, 1164, 672), background=PAPER)
    footer(draw, "05 / MODEL VALIDATION")
    return image


def slide_reproduce() -> Image.Image:
    image, draw = canvas()
    header(draw, "一条命令启动评委演示", "轻量样本直接运行；完整流程另行完成数据校验、断点续跑、训练与测试")
    draw.rounded_rectangle((48, 180, 1232, 284), radius=8, fill="#20262c")
    draw.text((78, 203), "$", font=font(26, bold=True, mono=True), fill="#77d1b2")
    draw.text((112, 207), "python demo.py --demo-only", font=font(24, mono=True), fill=PAPER)
    stages = [
        ("01", "清单校验", "URL · MD5 · 许可", TEAL),
        ("02", "特征构建", "逐记录断点", BLUE),
        ("03", "模型验证", "分组外推", GOLD),
        ("04", "交付导出", "SVG · PDF · TIFF", CORAL),
        ("05", "自动检查", "完整测试 + 浏览器 QA", GREEN),
    ]
    x = 48
    for number, title, detail, color in stages:
        draw.rounded_rectangle((x, 335, x + 214, 541), radius=8, fill=PAPER, outline=LINE, width=2)
        draw.text((x + 22, 357), number, font=font(18, bold=True), fill=color)
        draw.text((x + 22, 403), title, font=font(23, bold=True), fill=INK)
        draw_wrapped(draw, (x + 22, 449), detail, font(16), MUTED, 170, 5)
        if x < 1010:
            draw.line((x + 214, 438, x + 242, 438), fill="#9aa3aa", width=4)
            draw.polygon(((x + 242, 438), (x + 232, 431), (x + 232, 445)), fill="#9aa3aa")
        x += 242
    draw.text((48, 575), "完整证据重建：", font=font(18, bold=True), fill=INK)
    draw.text((206, 576), "python scripts/reproduce_all.py --resume", font=font(17, mono=True), fill=INK)
    draw.text((48, 613), "桌面与手机浏览器检查：无脚本错误、空白图表或横向溢出", font=font(18, bold=True), fill=TEAL)
    footer(draw, "07 / REPRODUCIBILITY")
    return image


def slide_close() -> Image.Image:
    image, draw = canvas()
    header(draw, "从一次分析，变成可核验的研究工作流", "NeuroChip Copilot 将功能状态、异常优先级和多维干预效应连接到同一证据链")
    pillars = [
        (48, 190, 418, 456, TEAL, "可复现", "公开数据与许可\n校验和与断点\n一键重建全部结果"),
        (455, 190, 825, 456, BLUE, "可解释", "固定功能特征\n来源分组验证\n阈值与消融透明"),
        (862, 190, 1232, 456, CORAL, "可使用", "上传或公共样例\n图表、模型和报告\n桌面与移动端界面"),
    ]
    for x0, y0, x1, y1, color, title, body in pillars:
        draw.rounded_rectangle((x0, y0, x1, y1), radius=8, fill=PAPER, outline=LINE, width=2)
        draw.rectangle((x0, y0, x1, y0 + 10), fill=color)
        draw.text((x0 + 28, y0 + 39), title, font=font(31, bold=True), fill=color)
        draw_wrapped(draw, (x0 + 28, y0 + 103), body, font(20), INK, x1 - x0 - 56, 14)
    draw.rounded_rectangle((48, 493, 1232, 648), radius=8, fill="#eef4f0", outline="#b9cbbd", width=2)
    draw.text((76, 518), "下一步验证", font=font(20, bold=True), fill=GREEN)
    draw_wrapped(
        draw,
        (76, 558),
        "在包含原始电压、更多芯片与更多化合物的前瞻性盲法数据上，继续验证泛化能力与实验价值。",
        font(22),
        INK,
        1090,
        8,
    )
    footer(draw, "08 / CONCLUSION")
    return image


def make_slides() -> list[Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    slides = {
        "01_intro": slide_intro,
        "02_results": slide_results,
        "03_data": slide_data,
        "05_model": slide_model,
        "07_reproduce": slide_reproduce,
        "08_close": slide_close,
    }
    outputs: list[Path] = []
    for name, builder in slides.items():
        target = OUT / f"{name}.png"
        builder().save(target, format="PNG", optimize=True)
        outputs.append(target)
        print(f"Created {target.relative_to(ROOT)}")
    return outputs


if __name__ == "__main__":
    make_slides()
