from datetime import datetime
from pathlib import Path
from textwrap import wrap
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = PROJECT_ROOT / "resources" / "templates"
DOCX_TEMPLATE = TEMPLATE_DIR / "modelo_raf.docx"
LOGO_PATH = TEMPLATE_DIR / "logo_pcpe_header.png"


def export_text(
    job_id: str,
    anonymized_text: str,
    original_filename: str = "documento",
    metadata: dict[str, Any] | None = None,
) -> dict[str, str]:
    export_dir = Path("data") / "exports" / job_id
    export_dir.mkdir(parents=True, exist_ok=True)

    txt_path = export_dir / "anonimizado.txt"
    docx_path = export_dir / "anonimizado.docx"
    pdf_path = export_dir / "anonimizado.pdf"

    metadata = metadata or {}
    _export_txt(txt_path, anonymized_text, original_filename, metadata)
    _export_docx(docx_path, anonymized_text, original_filename, metadata)
    _export_pdf(pdf_path, anonymized_text, original_filename, metadata)

    return {"txt": str(txt_path), "docx": str(docx_path), "pdf": str(pdf_path)}


def _summary_lines(original_filename: str, metadata: dict[str, Any]) -> list[str]:
    generated_at = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    return [
        "RESUMO OPERACIONAL",
        f"Solicitacao: {metadata.get('request_title') or 'Nao informada'}",
        f"Arquivo de origem: {original_filename}",
        f"Perfil documental: {metadata.get('document_kind') or 'auto'}",
        f"Modelo: {metadata.get('model') or 'Nao informado'}",
        f"Tempo de processamento: {metadata.get('processing_time_seconds', 'Nao informado')} s",
        f"OCR: {'Utilizado' if metadata.get('ocr_used') else 'Nao utilizado'}",
        f"Estrutura: {'Preservada' if metadata.get('structure_preserved') else 'Nao preservada'}",
        f"Validacao: {metadata.get('validation_status') or 'Nao informada'}",
        f"Hash SHA-256 original: {metadata.get('source_sha256') or 'Nao calculado'}",
        f"Entidades identificadas: {metadata.get('entities_found', 0)}",
        f"Substituicoes aplicadas: {metadata.get('replacements_applied', 0)}",
        f"Gerado em: {generated_at}",
    ]


def _export_txt(path: Path, text: str, original_filename: str, metadata: dict[str, Any]) -> None:
    lines = [
        "NEXUS ANON - DOCUMENTO ANONIMIZADO",
        "POLICIA CIVIL DO ESTADO DE PERNAMBUCO",
        "-" * 78,
        "",
        *_summary_lines(original_filename, metadata),
        "",
        "-" * 78,
        "PRODUTO FINAL DA ANONIMIZACAO DE DADOS",
        "O conteudo abaixo corresponde ao resultado desidentificado gerado pelo NEXUS ANON.",
        "-" * 78,
        "",
    ]
    for paragraph in text.splitlines():
        if not paragraph.strip():
            lines.append("")
            continue
        lines.extend(wrap(paragraph, width=110, replace_whitespace=False, drop_whitespace=False) or [""])
    lines.extend(["", "-" * 78, "FIM DO PRODUTO FINAL DA ANONIMIZACAO DE DADOS"])
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _export_docx(path: Path, text: str, original_filename: str, metadata: dict[str, Any]) -> None:
    try:
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Pt
    except ImportError:
        path.write_text(text, encoding="utf-8")
        return

    document = Document(DOCX_TEMPLATE) if DOCX_TEMPLATE.exists() else Document()
    _clear_docx_body_preserving_section(document)

    title = document.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("DOCUMENTO ANONIMIZADO")
    run.bold = True
    run.font.name = "Arial"
    run.font.size = Pt(14)

    subtitle = document.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle_run = subtitle.add_run("NEXUS ANON - POLICIA CIVIL DO ESTADO DE PERNAMBUCO")
    subtitle_run.bold = True
    subtitle_run.font.name = "Arial"
    subtitle_run.font.size = Pt(10)

    meta = document.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.LEFT
    meta.add_run("\n".join(_summary_lines(original_filename, metadata)))

    document.add_paragraph("")

    marker = document.add_paragraph()
    marker.alignment = WD_ALIGN_PARAGRAPH.LEFT
    marker_run = marker.add_run("PRODUTO FINAL DA ANONIMIZACAO DE DADOS")
    marker_run.bold = True
    marker_run.font.name = "Arial"
    marker_run.font.size = Pt(11)

    for line in text.splitlines():
        paragraph = document.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
        paragraph.paragraph_format.space_after = Pt(6)
        run = paragraph.add_run(line)
        run.font.name = "Arial"
        run.font.size = Pt(11)

    footer = document.add_paragraph()
    footer.alignment = WD_ALIGN_PARAGRAPH.LEFT
    footer.add_run("FIM DO PRODUTO FINAL DA ANONIMIZACAO DE DADOS").bold = True

    document.save(path)


def _clear_docx_body_preserving_section(document) -> None:
    body = document._body._element
    section_properties = None
    for child in list(body):
        if child.tag.endswith("}sectPr"):
            section_properties = child
        body.remove(child)
    if section_properties is not None:
        body.append(section_properties)


def _export_pdf(path: Path, text: str, original_filename: str, metadata: dict[str, Any]) -> None:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer
    except ImportError:
        path.write_text(text, encoding="utf-8")
        return

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title="Documento Anonimizado",
        author="NEXUS ANON",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "InstitutionalTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=14,
        alignment=1,
        textColor=colors.HexColor("#003B73"),
        spaceAfter=8,
    )
    meta_style = ParagraphStyle(
        "InstitutionalMeta",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        alignment=0,
        textColor=colors.HexColor("#172026"),
        spaceAfter=12,
    )
    body_style = ParagraphStyle(
        "InstitutionalBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        alignment=0,
        firstLineIndent=0,
        spaceAfter=6,
    )

    story = []
    if LOGO_PATH.exists():
        story.append(Image(str(LOGO_PATH), width=8.2 * cm, height=2.2 * cm, kind="proportional"))
        story.append(Spacer(1, 0.25 * cm))
    story.append(Paragraph("DOCUMENTO ANONIMIZADO", title_style))
    story.append(Paragraph("NEXUS ANON - POLICIA CIVIL DO ESTADO DE PERNAMBUCO", title_style))
    story.append(
        Paragraph(
            "<br/>".join(_escape_pdf_text(line) for line in _summary_lines(original_filename, metadata)),
            meta_style,
        )
    )
    story.append(Paragraph("PRODUTO FINAL DA ANONIMIZACAO DE DADOS", title_style))

    for line in text.splitlines():
        story.append(Paragraph(_escape_pdf_text(line) if line.strip() else "&nbsp;", body_style))

    story.append(Spacer(1, 0.25 * cm))
    story.append(Paragraph("FIM DO PRODUTO FINAL DA ANONIMIZACAO DE DADOS", meta_style))

    doc.build(story)


def _escape_pdf_text(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
