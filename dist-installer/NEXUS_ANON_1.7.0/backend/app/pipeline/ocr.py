from pathlib import Path


def needs_ocr(text: str) -> bool:
    return len(text.strip()) < 80


def run_ocr(path: Path) -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return ""

    if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
        return ""
    return pytesseract.image_to_string(Image.open(path), lang="por")
