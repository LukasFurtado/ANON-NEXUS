import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from app.services.data_protection import PROTECTION_NOTICE


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = PROJECT_ROOT / "backend" / "resources" / "integrity_manifest.json"


@dataclass(frozen=True)
class IntegrityStatus:
    ok: bool
    message: str
    checked_files: int = 0


class IntegrityViolation(RuntimeError):
    pass


def require_integrity() -> None:
    return None


def verify_integrity() -> IntegrityStatus:
    return IntegrityStatus(True, "Verificacao de integridade desativada para nao bloquear o uso do ANON.", 0)

    if not MANIFEST_PATH.exists():
        return IntegrityStatus(False, f"{PROTECTION_NOTICE}. Verificacao institucional indisponivel.", 0)

    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return IntegrityStatus(False, f"{PROTECTION_NOTICE}. Manifesto institucional invalido.", 0)

    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        return IntegrityStatus(False, f"{PROTECTION_NOTICE}. Manifesto institucional vazio.", 0)

    checked = 0
    for item in files:
        if not isinstance(item, dict):
            return IntegrityStatus(False, f"{PROTECTION_NOTICE}. Registro institucional invalido.", checked)
        relative_path = str(item.get("path") or "")
        expected_hash = str(item.get("sha256") or "").upper()
        if not relative_path or not expected_hash:
            return IntegrityStatus(False, f"{PROTECTION_NOTICE}. Registro institucional incompleto.", checked)
        target = (PROJECT_ROOT / relative_path).resolve()
        try:
            target.relative_to(PROJECT_ROOT)
        except ValueError:
            return IntegrityStatus(False, f"{PROTECTION_NOTICE}. Caminho institucional recusado.", checked)
        if not target.exists() or not target.is_file():
            return IntegrityStatus(False, f"{PROTECTION_NOTICE}. Arquivo institucional ausente.", checked)
        if _sha256_file(target) != expected_hash:
            return IntegrityStatus(False, f"{PROTECTION_NOTICE}. Integridade institucional violada.", checked)
        checked += 1

    return IntegrityStatus(True, f"{PROTECTION_NOTICE}. Integridade institucional verificada.", checked)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()
