from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import (
    HRFlowable,
    Image,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from pypdf import PdfReader


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = PROJECT_ROOT / "docs" / "technical_report.md"
OUTPUT_PATH = PROJECT_ROOT / "output" / "pdf" / "NeuroChip_Copilot_Technical_Report.pdf"
INK = colors.HexColor("#20262A")
MUTED = colors.HexColor("#667078")
TEAL = colors.HexColor("#147F7A")
BLUE = colors.HexColor("#3166A8")
LINE = colors.HexColor("#D9DEE2")
SOFT = colors.HexColor("#F4F6F7")
RED = colors.HexColor("#A3453E")


def register_fonts() -> tuple[str, str]:
    candidates = [
        (Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")),
        (Path("C:/Windows/Fonts/calibri.ttf"), Path("C:/Windows/Fonts/calibrib.ttf")),
    ]
    for regular, bold in candidates:
        if regular.exists() and bold.exists():
            pdfmetrics.registerFont(TTFont("ReportSans", regular))
            pdfmetrics.registerFont(TTFont("ReportSans-Bold", bold))
            return "ReportSans", "ReportSans-Bold"
    return "Helvetica", "Helvetica-Bold"


REGULAR_FONT, BOLD_FONT = register_fonts()


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle(
            "CoverTitle",
            parent=base["Title"],
            fontName=BOLD_FONT,
            fontSize=25,
            leading=29,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=7 * mm,
        ),
        "cover_subtitle": ParagraphStyle(
            "CoverSubtitle",
            parent=base["Normal"],
            fontName=REGULAR_FONT,
            fontSize=12,
            leading=17,
            textColor=MUTED,
            spaceAfter=7 * mm,
        ),
        "h1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontName=BOLD_FONT,
            fontSize=16,
            leading=20,
            textColor=INK,
            spaceBefore=7 * mm,
            spaceAfter=3.2 * mm,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontName=BOLD_FONT,
            fontSize=11.5,
            leading=14,
            textColor=TEAL,
            spaceBefore=5 * mm,
            spaceAfter=2.2 * mm,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName=REGULAR_FONT,
            fontSize=9.1,
            leading=13.4,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=2.6 * mm,
            splitLongWords=True,
            allowWidows=0,
            allowOrphans=0,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base["BodyText"],
            fontName=REGULAR_FONT,
            fontSize=8.8,
            leading=12.5,
            textColor=INK,
            leftIndent=0,
            spaceAfter=1.1 * mm,
        ),
        "caption": ParagraphStyle(
            "Caption",
            parent=base["BodyText"],
            fontName=REGULAR_FONT,
            fontSize=7.6,
            leading=10.2,
            textColor=MUTED,
            spaceBefore=1.5 * mm,
            spaceAfter=4 * mm,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName=REGULAR_FONT,
            fontSize=7.5,
            leading=10.5,
            textColor=MUTED,
        ),
        "boundary": ParagraphStyle(
            "Boundary",
            parent=base["BodyText"],
            fontName=BOLD_FONT,
            fontSize=8.4,
            leading=12,
            textColor=RED,
            borderColor=colors.HexColor("#E2B8B4"),
            borderWidth=0.7,
            borderPadding=7,
            backColor=colors.HexColor("#FCF4F3"),
        ),
    }


STYLES = styles()


def inline_markup(text: str) -> str:
    escaped = html.escape(text.strip())
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", escaped)
    escaped = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', escaped)
    return escaped


def scaled_image(path: Path, max_width: float = 170 * mm, max_height: float = 112 * mm) -> Image:
    width, height = ImageReader(path).getSize()
    scale = min(max_width / width, max_height / height)
    return Image(str(path), width=width * scale, height=height * scale)


def cover_story(source_text: str) -> list:
    subtitle_match = re.search(r"## (Quality-Aware.+)", source_text)
    subtitle = subtitle_match.group(1) if subtitle_match else "Technical Report"
    version_match = re.search(r"\*\*Report version:\*\*\s*([^\r\n]+)", source_text)
    date_match = re.search(r"\*\*Date:\*\*\s*([^\r\n]+)", source_text)
    category_match = re.search(r"\*\*Submission category:\*\*\s*([^\r\n]+)", source_text)
    version = version_match.group(1).strip() if version_match else "unknown"
    report_date = date_match.group(1).strip() if date_match else "unknown"
    category = category_match.group(1).strip() if category_match else "undeclared"
    architecture = PROJECT_ROOT / "docs" / "assets" / "figure0_architecture.png"
    story: list = [
        Spacer(1, 10 * mm),
        Paragraph("NeuroChip Copilot", STYLES["cover_title"]),
        Paragraph(inline_markup(subtitle), STYLES["cover_subtitle"]),
        HRFlowable(width="100%", thickness=2.2, color=TEAL, spaceAfter=7 * mm),
    ]
    metadata = Table(
        [
            ["Team", "NeuroChip Copilot Team", "Version", version],
            ["Category", category, "Date", report_date],
            ["Artifact", "Runnable research system", "Code", "MIT"],
        ],
        colWidths=[25 * mm, 65 * mm, 20 * mm, 40 * mm],
    )
    metadata.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), REGULAR_FONT),
                ("FONTNAME", (0, 0), (0, -1), BOLD_FONT),
                ("FONTNAME", (2, 0), (2, -1), BOLD_FONT),
                ("FONTSIZE", (0, 0), (-1, -1), 8.2),
                ("TEXTCOLOR", (0, 0), (-1, -1), INK),
                ("BACKGROUND", (0, 0), (-1, -1), SOFT),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend([metadata, Spacer(1, 8 * mm), scaled_image(architecture, max_height=67 * mm), Spacer(1, 7 * mm)])
    evidence = Table(
        [
            ["SOURCE REPRODUCTION", "ANOMALY VALIDATION", "INTERVENTION WORKFLOW"],
            ["45 / 45 matched", "AUROC 0.858", "18 features / 5 domains"],
            ["max error < 1.0e-15", "95% CI 0.796-0.915", "aux transfer AUC .952 / .889"],
        ],
        colWidths=[53 * mm, 53 * mm, 53 * mm],
    )
    evidence.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), BOLD_FONT),
                ("FONTNAME", (0, 1), (-1, -1), REGULAR_FONT),
                ("FONTSIZE", (0, 0), (-1, 0), 7.2),
                ("FONTSIZE", (0, 1), (-1, 1), 11),
                ("FONTSIZE", (0, 2), (-1, 2), 7.6),
                ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
                ("TEXTCOLOR", (0, 1), (-1, 1), BLUE),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("BOX", (0, 0), (-1, -1), 0.7, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend(
        [
            evidence,
            Spacer(1, 8 * mm),
            Paragraph(
                "Boundary: event uploads cannot establish voltage quality or causal connectivity. Clinical, efficacy, and toxicological conclusions are outside scope.",
                STYLES["boundary"],
            ),
            PageBreak(),
        ]
    )
    return story


def flush_paragraph(buffer: list[str], story: list) -> None:
    if buffer:
        story.append(Paragraph(inline_markup(" ".join(line.strip() for line in buffer)), STYLES["body"]))
        buffer.clear()


def markdown_story(source_path: Path) -> list:
    lines = source_path.read_text(encoding="utf-8").splitlines()
    start = next(index for index, line in enumerate(lines) if line.strip() == "## Abstract")
    story: list = []
    paragraph: list[str] = []
    index = start
    while index < len(lines):
        raw = lines[index]
        stripped = raw.strip()
        if not stripped:
            flush_paragraph(paragraph, story)
            index += 1
            continue
        image_match = re.fullmatch(r"!\[(.+)]\((.+)\)", stripped)
        if image_match:
            flush_paragraph(paragraph, story)
            caption, relative = image_match.groups()
            image_path = (source_path.parent / relative).resolve()
            if not image_path.exists():
                raise FileNotFoundError(image_path)
            story.extend([scaled_image(image_path), Paragraph(inline_markup(caption), STYLES["caption"])])
            index += 1
            continue
        if stripped.startswith("### "):
            flush_paragraph(paragraph, story)
            story.append(Paragraph(inline_markup(stripped[4:]), STYLES["h2"]))
            index += 1
            continue
        if stripped.startswith("## "):
            flush_paragraph(paragraph, story)
            story.append(Paragraph(inline_markup(stripped[3:]), STYLES["h1"]))
            index += 1
            continue
        if stripped.startswith("- "):
            flush_paragraph(paragraph, story)
            items = []
            while index < len(lines) and lines[index].strip().startswith("- "):
                items.append(ListItem(Paragraph(inline_markup(lines[index].strip()[2:]), STYLES["bullet"]), leftIndent=4 * mm))
                index += 1
            story.append(ListFlowable(items, bulletType="bullet", bulletFontName=REGULAR_FONT, leftIndent=5 * mm, bulletOffsetY=1))
            story.append(Spacer(1, 1.5 * mm))
            continue
        if re.match(r"^\d+\. ", stripped):
            flush_paragraph(paragraph, story)
            items = []
            while index < len(lines) and re.match(r"^\d+\. ", lines[index].strip()):
                item_text = re.sub(r"^\d+\. ", "", lines[index].strip())
                items.append(ListItem(Paragraph(inline_markup(item_text), STYLES["bullet"]), leftIndent=5 * mm))
                index += 1
            story.append(ListFlowable(items, bulletType="1", start="1", leftIndent=6 * mm))
            story.append(Spacer(1, 1.5 * mm))
            continue
        paragraph.append(raw)
        index += 1
    flush_paragraph(paragraph, story)
    return story


def validate_claims(source_text: str) -> None:
    phenotype = json.loads((PROJECT_ROOT / "artifacts" / "results" / "phenotype" / "metrics.json").read_text(encoding="utf-8"))
    drug = json.loads((PROJECT_ROOT / "artifacts" / "results" / "drug_response" / "metrics.json").read_text(encoding="utf-8"))
    external = json.loads(
        (PROJECT_ROOT / "artifacts" / "results" / "external_validation" / "gin_metrics.json").read_text(encoding="utf-8")
    )
    source = json.loads((PROJECT_ROOT / "artifacts" / "results" / "source_validation" / "validation_metrics.json").read_text(encoding="utf-8"))
    required = {
        f"AUROC {phenotype['roc_auc']:.3f}": "phenotype AUROC",
        f"rho {drug['response_magnitude_dose_spearman']:.3f}": "drug Spearman",
        f"8.88e-16": "firing-rate reproduction error",
        f"1.11e-16": "STTC reproduction error",
        "45 reference recordings": "reference sample size",
        "19 diazepam conditions from four organoids": "drug sample size",
        "Submission category:** End-to-End System": "competition category declaration",
        "30/30/20/10/10": "official evaluation weights",
    }
    external_pharma = next(
        item
        for item in external["metrics"]
        if item["window_s"] == 180
        and item["dataset_id"] == "pooled"
        and item["comparison"] == "pharma_vs_baseline"
    )
    required[f"AUC {external_pharma['roc_auc']:.3f}"] = "external pharmacology AUC"
    if source["n_matched"] != 45:
        raise ValueError("Source validation no longer contains 45 matched rows")
    missing = [f"{label}: {token}" for token, label in required.items() if token not in source_text]
    if missing:
        raise ValueError("Technical report is stale or incomplete: " + "; ".join(missing))


def page_decor(canvas, document) -> None:
    canvas.saveState()
    width, _ = A4
    canvas.setStrokeColor(TEAL)
    canvas.setLineWidth(0.7)
    canvas.line(20 * mm, 14 * mm, width - 20 * mm, 14 * mm)
    canvas.setFont(REGULAR_FONT, 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(20 * mm, 9 * mm, "NeuroChip Copilot - Technical Report")
    canvas.drawRightString(width - 20 * mm, 9 * mm, str(document.page))
    canvas.restoreState()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and validate the NeuroChip Copilot technical report PDF")
    parser.add_argument("--source", type=Path, default=SOURCE_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()
    source_text = args.source.read_text(encoding="utf-8")
    validate_claims(source_text)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(args.output),
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title="NeuroChip Copilot Technical Report",
        author="NeuroChip Copilot Team",
        subject="AI + Organ-on-a-Chip competition technical report",
    )
    story = cover_story(source_text) + markdown_story(args.source)
    document.build(story, onFirstPage=page_decor, onLaterPages=page_decor)

    reader = PdfReader(args.output)
    if not 15 <= len(reader.pages) <= 20:
        raise RuntimeError(f"Unexpected report length: {len(reader.pages)} pages")
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    for token in ("NeuroChip Copilot", "0.858", "0.904", "0.952", "References"):
        if token not in text:
            raise RuntimeError(f"Rendered PDF is missing expected text: {token}")
    print(f"[complete] {len(reader.pages)} pages -> {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
