import hashlib

from app.version import APP_VERSION


PROTECTION_NOTICE = "Protecao de dados: ativa"


def build_protection_marker(*, source_sha256: str, request_title: str | None, original_filename: str) -> str:
    material = "|".join(
        [
            "ANON",
            "POLICIA_CIVIL_PERNAMBUCO",
            "LUKAS_FURTADO",
            APP_VERSION,
            source_sha256,
            request_title or "",
            original_filename,
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest().upper()


def protection_metadata(marker: str) -> dict[str, str]:
    return {
        "notice": PROTECTION_NOTICE,
        "marker": marker,
    }
