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

    exports = {"txt": str(txt_path), "docx": str(docx_path), "pdf": str(pdf_path)}
    if Path(original_filename).suffix.lower() == ".csv":
        csv_path = export_dir / "anonimizado.csv"
        _export_csv(csv_path, anonymized_text)
        exports["csv"] = str(csv_path)

    return exports


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


def _control_rows(metadata: dict[str, Any]) -> list[Any]:
    rows = metadata.get("control_table") or []
    return rows if isinstance(rows, list) else []


def _row_value(row: Any, key: str) -> Any:
    if isinstance(row, dict):
        return row.get(key, "")
    return getattr(row, key, "")


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
        if _looks_like_delimited_row(paragraph):
            lines.append(paragraph)
            continue
        lines.extend(wrap(paragraph, width=110, replace_whitespace=False, drop_whitespace=False) or [""])
    lines.extend(["", "-" * 78, "FIM DO PRODUTO FINAL DA ANONIMIZACAO DE DADOS"])
    rows = _control_rows(metadata)
    if rows:
        lines.extend(
            [
                "",
                "-" * 78,
                "TABELA DE CONTROLE DE ANONIMIZACAO - USO INTERNO",
                "Esta secao contem valores originais e deve ser usada apenas para auditoria e revisao interna.",
                "-" * 78,
                "Valor Original\tTipo da Entidade\tIdentificador Anonimo\tOcorrencias",
            ]
        )
        for row in rows:
            lines.append(
                "\t".join(
                    [
                        str(_row_value(row, "original_value")),
                        str(_row_value(row, "entity_type")),
                        str(_row_value(row, "anonymous_id")),
                        str(_row_value(row, "occurrences")),
                    ]
                )
            )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _looks_like_delimited_row(value: str) -> bool:
    return value.count(";") >= 2 or value.count(",") >= 5 or "\t" in value


def _export_csv(path: Path, text: str) -> None:
    path.write_text(text.rstrip("\r\n") + "\n", encoding="utf-8-sig")


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

    rows = _control_rows(metadata)
    if rows:
        document.add_page_break()
        control_title = document.add_paragraph()
        control_title.alignment = WD_ALIGN_PARAGRAPH.LEFT
        control_run = control_title.add_run("TABELA DE CONTROLE DE ANONIMIZACAO - USO INTERNO")
        control_run.bold = True
        control_run.font.name = "Arial"
        control_run.font.size = Pt(11)

        notice = document.add_paragraph()
        notice.alignment = WD_ALIGN_PARAGRAPH.LEFT
        notice_run = notice.add_run(
            "Esta secao contem valores originais e deve ser usada apenas para auditoria, conferencia e revisao interna."
        )
        notice_run.font.name = "Arial"
        notice_run.font.size = Pt(9)

        table = document.add_table(rows=1, cols=4)
        table.style = "Table Grid"
        headers = ["Valor Original", "Tipo da Entidade", "Identificador Anonimo", "Ocorrencias"]
        for index, header in enumerate(headers):
            cell = table.rows[0].cells[index]
            cell.text = header
            for paragraph in cell.paragraphs:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
                for run in paragraph.runs:
                    run.bold = True
                    run.font.name = "Arial"
                    run.font.size = Pt(8)
        for row in rows:
            cells = table.add_row().cells
            values = [
                _row_value(row, "original_value"),
                _row_value(row, "entity_type"),
                _row_value(row, "anonymous_id"),
                _row_value(row, "occurrences"),
            ]
            for index, value in enumerate(values):
                cells[index].text = str(value)
                for paragraph in cells[index].paragraphs:
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
                    for run in paragraph.runs:
                        run.font.name = "Arial"
                        run.font.size = Pt(7)

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
        from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
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
        logo = Image(str(LOGO_PATH), width=8.2 * cm, height=2.2 * cm, kind="proportional")
        logo.hAlign = "CENTER"
        story.append(logo)
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

    rows = _control_rows(metadata)
    if rows:
        story.append(Spacer(1, 0.45 * cm))
        story.append(Paragraph("TABELA DE CONTROLE DE ANONIMIZACAO - USO INTERNO", title_style))
        story.append(
            Paragraph(
                "Esta secao contem valores originais e deve ser usada apenas para auditoria, conferencia e revisao interna.",
                meta_style,
            )
        )
        table_data = [["Valor Original", "Tipo", "Identificador", "Ocorrencias"]]
        for row in rows:
            table_data.append(
                [
                    Paragraph(_escape_pdf_text(str(_row_value(row, "original_value"))), meta_style),
                    Paragraph(_escape_pdf_text(str(_row_value(row, "entity_type"))), meta_style),
                    Paragraph(_escape_pdf_text(str(_row_value(row, "anonymous_id"))), meta_style),
                    str(_row_value(row, "occurrences")),
                ]
            )
        control_table = Table(table_data, colWidths=[7.0 * cm, 3.2 * cm, 4.0 * cm, 2.0 * cm], repeatRows=1)
        control_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#003B73")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B8C3CF")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(control_table)

    doc.build(story)


def _escape_pdf_text(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def export_processing_log(group_id: str, metadata: dict[str, Any]) -> str:
    export_dir = Path("data") / "exports" / group_id
    export_dir.mkdir(parents=True, exist_ok=True)
    log_path = export_dir / "log_processamento.pdf"
    _export_log_pdf(log_path, metadata)
    return str(log_path)


def _export_log_pdf(path: Path, metadata: dict[str, Any]) -> None:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError:
        lines = ["NEXUS ANON - LOG DE PROCESSAMENTO", *metadata.get("summary_lines", [])]
        path.write_text("\n".join(lines), encoding="utf-8")
        return

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=1.6 * cm,
        leftMargin=1.6 * cm,
        topMargin=1.7 * cm,
        bottomMargin=1.7 * cm,
        title="Log de Processamento - NEXUS ANON",
        author="NEXUS ANON",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "LogTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=14,
        alignment=1,
        textColor=colors.HexColor("#003B73"),
        spaceAfter=8,
    )
    body_style = ParagraphStyle(
        "LogBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        alignment=0,
        spaceAfter=4,
    )

    story = []
    if LOGO_PATH.exists():
        logo = Image(str(LOGO_PATH), width=8.2 * cm, height=2.2 * cm, kind="proportional")
        logo.hAlign = "CENTER"
        story.append(logo)
        story.append(Spacer(1, 0.25 * cm))
    story.append(Paragraph("LOG DE PROCESSAMENTO E CADEIA DE CUSTODIA", title_style))
    for line in metadata.get("summary_lines", []):
        story.append(Paragraph(_escape_pdf_text(str(line)), body_style))

    file_rows = metadata.get("files", [])
    if file_rows:
        story.append(Spacer(1, 0.25 * cm))
        story.append(Paragraph("Arquivos e hashes registrados", title_style))
        table_data = [["Arquivo", "Hash original", "TXT", "DOCX", "PDF", "CSV"]]
        for item in file_rows:
            table_data.append(
                [
                    Paragraph(_escape_pdf_text(str(item.get("filename", ""))), body_style),
                    Paragraph(_escape_pdf_text(str(item.get("source_sha256", ""))), body_style),
                    Paragraph(_escape_pdf_text(str(item.get("txt_sha256", ""))), body_style),
                    Paragraph(_escape_pdf_text(str(item.get("docx_sha256", ""))), body_style),
                    Paragraph(_escape_pdf_text(str(item.get("pdf_sha256", ""))), body_style),
                    Paragraph(_escape_pdf_text(str(item.get("csv_sha256", ""))), body_style),
                ]
            )
        table = Table(table_data, colWidths=[3.4 * cm, 3.6 * cm, 2.8 * cm, 2.8 * cm, 2.8 * cm, 2.8 * cm], repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#003B73")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 6),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B8C3CF")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(table)

    doc.build(story)
