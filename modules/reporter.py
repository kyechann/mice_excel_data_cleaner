# modules/reporter.py
from io import BytesIO
import os
import pandas as pd

from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def plotly_to_png_bytes(fig, scale: int = 2) -> bytes:
    """Requires kaleido."""
    return fig.to_image(format="png", scale=scale, engine="kaleido")


def mpl_to_png_bytes(fig, dpi: int = 150) -> bytes:
    bio = BytesIO()
    fig.savefig(bio, format="png", dpi=dpi, bbox_inches="tight")
    bio.seek(0)
    return bio.getvalue()


def _register_font(font_path: str | None):
    if not font_path:
        return None
    if os.path.exists(font_path):
        try:
            pdfmetrics.registerFont(TTFont("NanumGothic", font_path))
            return "NanumGothic"
        except Exception:
            return None
    return None


def _df_to_rl_table(df: pd.DataFrame, max_cols: int = 12):
    """DataFrame -> ReportLab Table (너무 넓으면 컬럼 제한)"""
    if df is None or df.empty:
        return None

    _df = df.copy()
    if _df.shape[1] > max_cols:
        _df = _df.iloc[:, :max_cols]

    data = [_df.columns.astype(str).tolist()] + _df.astype(str).values.tolist()
    tbl = Table(data, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#0b1220")),
        ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#e5e7eb")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#334155")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return tbl


def create_pdf_report(
    stats: dict,
    cleaned_data: dict,
    assets: list | None = None,
    title: str = "Data Cleaner Pro Report",
    font_path: str | None = None,
):
    """
    assets: list of tuples
      - ("img", "섹션 제목", png_bytes)
      - ("table", "표 제목", dataframe)
      - ("pagebreak", "", None)  ✅ 추가
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.6 * cm,
        rightMargin=1.6 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm
    )

    styles = getSampleStyleSheet()
    base_font = _register_font(font_path)

    if base_font:
        styles.add(ParagraphStyle(
            name="KTitle",
            parent=styles["Title"],
            fontName=base_font,
            fontSize=20,
            leading=24,
            textColor=colors.HexColor("#111827")
        ))
        styles.add(ParagraphStyle(
            name="KBody",
            parent=styles["BodyText"],
            fontName=base_font,
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#111827")
        ))
        h1 = styles["KTitle"]
        body = styles["KBody"]
    else:
        h1 = styles["Title"]
        body = styles["BodyText"]

    story = []

    # Title
    story.append(Paragraph(title, h1))
    story.append(Spacer(1, 10))

    # Summary stats
    story.append(Paragraph("요약", styles["Heading2"]))
    total = stats.get("total_rows", "-")
    removed = stats.get("removed_rows", "-")
    missing = stats.get("missing_info_rows", "-")
    story.append(Paragraph(f"• 전체 행: {total}", body))
    story.append(Paragraph(f"• 제거/중복: {removed}", body))
    story.append(Paragraph(f"• 결측/미기입: {missing}", body))
    story.append(Spacer(1, 12))

    # Cleaned sheets overview
    story.append(Paragraph("정제 결과(시트별)", styles["Heading2"]))
    if isinstance(cleaned_data, dict) and cleaned_data:
        ov = []
        for k, v in cleaned_data.items():
            try:
                ov.append([str(k), f"{len(v):,}"])
            except Exception:
                ov.append([str(k), "-"])
        ov_tbl = Table([["Sheet", "Rows"]] + ov, repeatRows=1, colWidths=[10*cm, 4*cm])
        ov_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#334155")),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(ov_tbl)
    else:
        story.append(Paragraph("정제 데이터가 없습니다.", body))

    story.append(PageBreak())

    # Assets (Charts / Tables)
    if assets:
        story.append(Paragraph("분석 자료 (그래프/요약표)", styles["Heading2"]))
        story.append(Spacer(1, 8))

        for item in assets:
            if not item or len(item) < 3:
                continue

            kind, sec_title, payload = item[0], item[1], item[2]

            if kind == "pagebreak":
                story.append(PageBreak())
                continue

            story.append(Paragraph(str(sec_title), styles["Heading3"]))
            story.append(Spacer(1, 6))

            if kind == "img":
                try:
                    img_bio = BytesIO(payload)
                    img = Image(img_bio)
                    img._restrictSize(18*cm, 24*cm)
                    story.append(img)
                    story.append(Spacer(1, 12))
                except Exception:
                    story.append(Paragraph("이미지 삽입 실패", body))
                    story.append(Spacer(1, 10))

            elif kind == "table":
                df = payload
                if df is None or (hasattr(df, "empty") and df.empty):
                    story.append(Paragraph("표 데이터가 없습니다.", body))
                    story.append(Spacer(1, 10))
                    continue

                tbl = _df_to_rl_table(df)
                if tbl:
                    story.append(tbl)
                story.append(Spacer(1, 12))

            else:
                story.append(Paragraph("알 수 없는 자산 타입", body))
                story.append(Spacer(1, 10))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()