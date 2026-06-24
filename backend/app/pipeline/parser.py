from pathlib import Path


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".rtf", ".csv"}


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Formato ainda nao suportado: {suffix}")

    if suffix in {".txt", ".csv"}:
        return _read_text_file(path)

    if suffix == ".rtf":
        return _extract_rtf(path)

    if suffix == ".docx":
        return _extract_docx(path)

    if suffix == ".pdf":
        return _extract_pdf(path)

    if suffix == ".doc":
        raise ValueError("DOC legado requer LibreOffice ou conversor local configurado.")

    return ""


def _extract_pdf(path: Path) -> str:
    try:
        import fitz
    except ImportError as exc:
        raise ValueError("PyMuPDF nao esta instalado no ambiente local.") from exc

    pages: list[str] = []
    with fitz.open(path) as document:
        for page in document:
            pages.append(page.get_text("text"))
    return "\n".join(pages)


def _read_text_file(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def _extract_docx(path: Path) -> str:
    try:
        from docx import Document
    except ImportError as exc:
        raise ValueError("python-docx nao esta instalado no ambiente local.") from exc

    document = Document(path)
    parts = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            parts.append("\t".join(cell.text for cell in row.cells))
    return "\n".join(parts)


def _extract_rtf(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    text = raw.replace("\\par", "\n")
    cleaned: list[str] = []
    skip = False
    for char in text:
        if char == "{":
            skip = True
            continue
        if char == "}":
            skip = False
            continue
        if not skip and char != "\\":
            cleaned.append(char)
    return "".join(cleaned)
