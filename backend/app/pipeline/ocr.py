from pathlib import Path


def needs_ocr(text: str) -> bool:
    stripped = text.strip()
    alnum = "".join(char for char in stripped if char.isalnum())
    if len(alnum) < 80:
        return True
    return len(alnum) / max(len(stripped), 1) < 0.18


def run_ocr(path: Path) -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return ""

    if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
        if path.suffix.lower() == ".pdf":
            return _ocr_pdf(path, pytesseract)
        return ""
    return pytesseract.image_to_string(Image.open(path), lang="por")


def _ocr_pdf(path: Path, pytesseract_module) -> str:
    try:
        import fitz
    except ImportError:
        return ""

    pages: list[str] = []
    try:
        with fitz.open(path) as document:
            for page in list(document)[:5]:
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                image = _image_from_pixmap(pixmap)
                text = pytesseract_module.image_to_string(image, lang="por")
                if text.strip():
                    pages.append(text.strip())
    except Exception:
        return ""
    return "\n".join(pages)


def _image_from_pixmap(pixmap):
    from PIL import Image

    mode = "RGB" if pixmap.n < 4 else "RGBA"
    return Image.frombytes(mode, [pixmap.width, pixmap.height], pixmap.samples)
