from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from io import BytesIO
from typing import Any

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .schema import SpikeRecording


def _format(value: Any, digits: int = 3) -> str:
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def build_html_report(
    recording: SpikeRecording,
    features: dict[str, Any],
    quality: dict[str, Any],
    model_result: dict[str, Any] | None = None,
    deviations: list[dict[str, Any]] | None = None,
) -> str:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    phenotype = model_result or {}
    rows = [
        ("Duration", f"{recording.duration_s:.1f} s"),
        ("Channels", recording.n_channels),
        ("Detected spikes", recording.n_spikes),
        ("Mean firing rate", f"{features['firing_rate_mean_hz']:.3f} Hz"),
        ("Mean STTC (20 ms)", f"{features['sttc_mean']:.3f}"),
        ("Network burst rate", f"{features['network_burst_rate_per_min']:.3f} /min"),
        ("Active channel fraction", f"{features['active_channel_fraction']:.1%}"),
        ("Event quality", f"{quality['quality_score']:.1f}/100 ({quality['quality_grade']})"),
    ]
    if phenotype:
        rows.extend(
            [
                ("Reference phenotype-axis percentile", f"P{phenotype['functional_phenotype_index']:.1f}"),
                ("Reference-deviation percentile", f"P{phenotype['anomaly_percentile']:.1f}"),
            ]
        )
    table = "".join(f"<tr><th>{escape(str(label))}</th><td>{escape(_format(value))}</td></tr>" for label, value in rows)
    deviation_rows = ""
    for item in deviations or []:
        deviation_rows += f"<tr><td>{escape(str(item['feature']))}</td><td>{float(item['robust_z']):.2f}</td><td>{escape(str(item['direction']))}</td></tr>"
    deviations_html = (
        f"<h2>Largest deviations from the reference cohort</h2><table><tr><th>Feature</th><th>Robust z</th><th>Direction</th></tr>{deviation_rows}</table>"
        if deviation_rows
        else ""
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>NeuroChip Copilot report</title>
<style>body{{font:14px Arial,sans-serif;color:#1e2428;max-width:860px;margin:36px auto;line-height:1.5}}h1{{font-size:24px;margin-bottom:4px}}h2{{font-size:17px;margin-top:28px}}.meta{{color:#667078}}table{{border-collapse:collapse;width:100%;margin-top:12px}}th,td{{padding:9px 10px;border-bottom:1px solid #d9dee2;text-align:left}}th{{width:45%;font-weight:600}}.notice{{margin-top:28px;padding:12px 14px;border-left:4px solid #d49b27;background:#fff8e8}}</style></head>
<body><h1>NeuroChip Copilot</h1><p class="meta">Recording: {escape(recording.recording_id)} | Generated {generated}</p>
<h2>Functional electrophysiology summary</h2><table>{table}</table>{deviations_html}
<div class="notice"><strong>Interpretation boundary.</strong> This report evaluates detected spike events. It does not assess raw-voltage noise, waveform morphology, clinical efficacy, or toxicological safety. Anomaly scores are relative to the 45-recording public brain-organoid reference cohort.</div>
</body></html>"""


def build_pdf_report(
    recording: SpikeRecording,
    features: dict[str, Any],
    quality: dict[str, Any],
    model_result: dict[str, Any] | None = None,
    explanation: pd.DataFrame | None = None,
    project_name: str | None = None,
    sample_name: str | None = None,
) -> bytes:
    """Build a compact research PDF report from one analyzed recording."""

    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=17 * mm,
        rightMargin=17 * mm,
        topMargin=17 * mm,
        bottomMargin=16 * mm,
        title=f"NeuroChip Report - {recording.recording_id}",
        author="NeuroChip Copilot",
    )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=19,
            leading=23,
            textColor=colors.HexColor("#1E2A2E"),
            alignment=TA_LEFT,
            spaceAfter=3 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13,
            textColor=colors.HexColor("#147F7A"),
            spaceBefore=4 * mm,
            spaceAfter=2 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SmallMuted",
            parent=styles["BodyText"],
            fontSize=7.7,
            leading=10,
            textColor=colors.HexColor("#667078"),
        )
    )
    story: list[Any] = [
        Paragraph("NeuroChip Functional Electrophysiology Report", styles["ReportTitle"]),
        Paragraph(
            f"Project: {escape(project_name or 'Unassigned')} &nbsp;&nbsp; Sample: "
            f"{escape(sample_name or recording.recording_id)} &nbsp;&nbsp; Recording: {escape(recording.recording_id)}",
            styles["SmallMuted"],
        ),
        Spacer(1, 3 * mm),
    ]
    status_color = {
        "pass": colors.HexColor("#147F7A"),
        "review": colors.HexColor("#B77C14"),
        "fail": colors.HexColor("#BD473E"),
    }.get(str(quality.get("quality_grade")), colors.HexColor("#667078"))
    phenotype = model_result or {}
    headline = [
        ["Event QC", "Stability", "Phenotype axis", "Ref. deviation"],
        [
            f"{float(quality['quality_score']):.0f}/100\n{str(quality['quality_grade']).upper()}",
            str(quality.get("stability_grade", "N/A")).upper(),
            f"P{float(phenotype.get('functional_phenotype_index', 0)):.1f}" if phenotype else "N/A",
            f"P{float(phenotype.get('anomaly_percentile', 0)):.1f}" if phenotype else "N/A",
        ],
    ]
    headline_table = Table(headline, colWidths=[42 * mm] * 4, rowHeights=[7 * mm, 15 * mm])
    headline_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF2F3")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#536068")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 7.5),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 1), (-1, 1), 11),
                ("TEXTCOLOR", (0, 1), (0, 1), status_color),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D9DEE2")),
            ]
        )
    )
    story.append(headline_table)

    def metric_table(title: str, rows: list[tuple[str, str]]) -> KeepTogether:
        table_data = [[Paragraph(label, styles["SmallMuted"]), value] for label, value in rows]
        table = Table(table_data, colWidths=[75 * mm, 93 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.2),
                    ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#1E2A2E")),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#E3E7E9")),
                ]
            )
        )
        return KeepTogether([Paragraph(title, styles["SectionTitle"]), table])

    story.append(
        metric_table(
            "Recording and quality control",
            [
                ("Duration", f"{recording.duration_s:.1f} s"),
                ("Channels / detected events", f"{recording.n_channels} / {recording.n_spikes:,}"),
                ("Active channel fraction", f"{float(features['active_channel_fraction']):.1%}"),
                ("Inactive channel candidates", str(quality.get("inactive_channel_candidates", 0))),
                ("Review / excluded candidates", f"{quality.get('review_channel_candidates', 0)} / {quality.get('excluded_channel_candidates', 0)}"),
                ("Firing stability CV", f"{float(features.get('firing_stability_cv', 0)):.3f}"),
                ("Last-to-first activity change", f"{float(features.get('activity_decay_log2_ratio', 0)):+.3f} log2"),
                ("Raw-voltage QC", "Available" if quality.get("raw_voltage_qc_available") else "Not available from event input"),
            ],
        )
    )
    story.append(
        metric_table(
            "Activity, criticality, and connectivity",
            [
                ("Mean firing rate", f"{float(features['firing_rate_mean_hz']):.4f} Hz"),
                ("Network burst rate", f"{float(features['network_burst_rate_per_min']):.3f} /min"),
                ("Mean STTC (20 ms)", f"{float(features['sttc_mean']):.4f}"),
                ("Avalanche rate", f"{float(features.get('avalanche_rate_per_min', 0)):.3f} /min"),
                ("Avalanche mean size", f"{float(features.get('avalanche_size_mean', 0)):.3f} events"),
                ("Avalanche branching ratio", f"{float(features.get('avalanche_branching_ratio', 0)):.3f}"),
                ("Bias-corrected mutual information", f"{float(features.get('mutual_information_mean_bits', 0)):.6f} bits"),
                ("Bias-corrected transfer entropy", f"{float(features.get('transfer_entropy_mean_bits', 0)):.6f} bits"),
                ("Pairwise predictive GC score", f"{float(features.get('granger_log_variance_ratio_mean', 0)):.6f}"),
            ],
        )
    )
    if explanation is not None and not explanation.empty:
        ranked = explanation.assign(abs_contribution=explanation["anomaly_shap_value"].abs()).nlargest(6, "abs_contribution")
        explanation_rows = [
            (
                str(row.feature),
                f"{float(row.anomaly_shap_value):+.5f} (scaled value {float(row.scaled_value):+.2f})",
            )
            for row in ranked.itertuples()
        ]
        story.append(metric_table("Largest reference-deviation Shapley contributions", explanation_rows))
    story.extend(
        [
            Paragraph("Interpretation boundary", styles["SectionTitle"]),
            Paragraph(
                "This report evaluates detected extracellular spike events. A silent event channel is an inactive "
                "candidate, not a confirmed dead electrode. Raw-voltage noise, line interference, saturation, "
                "baseline drift, and waveform morphology require raw voltage. Transfer entropy and Granger scores "
                "describe statistical information flow or predictive direction and do not prove synaptic causality. "
                "Phenotype-axis and reference-deviation percentiles are relative to the 45-recording forebrain-organoid "
                "cohort. The phenotype axis is not a health or maturity score, and reference deviation is not a disease, "
                "efficacy, toxicity, or safety probability.",
                styles["SmallMuted"],
            ),
        ]
    )

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def footer(canvas, doc) -> None:
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D9DEE2"))
        canvas.line(17 * mm, 12 * mm, 193 * mm, 12 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#667078"))
        canvas.drawString(17 * mm, 8 * mm, f"Generated {generated} | Feature schema {features.get('feature_schema_version', '1.0')}")
        canvas.drawRightString(193 * mm, 8 * mm, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
