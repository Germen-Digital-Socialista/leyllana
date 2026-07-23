"""Capa de engine: ``explain(text, nivel)`` sobre un proveedor swappable (ADR 0003).

Arma el prompt (con guardrail y disclaimer), elige el proveedor segun la config,
genera la respuesta cruda y la parsea en las cuatro secciones fijas del contrato
de salida (ADR 0007). El parseo es puro y testeable; el proveedor local
(llama.cpp) es un stub de Fase 1 que levanta ``NotImplementedError`` al generar.
"""

from __future__ import annotations

import unicodedata

from ..config import Config
from ..prompt import build
from ..types import Explanation, Nivel
from .registry import get_provider


class ParseError(RuntimeError):
    """La respuesta del modelo no trae las cuatro secciones esperadas (ADR 0007)."""


# Encabezado de seccion (normalizado, sin acentos) -> campo de ``Explanation``.
_SECTION_FIELDS = (
    ("que hace", "que_hace"),
    ("a quien afecta", "a_quien_afecta"),
    ("articulos clave", "articulos_clave"),
    ("en una frase", "en_una_frase"),
)


def explain(text: str, nivel: Nivel, config: Config | None = None) -> Explanation:
    """Explica ``text`` en el ``nivel`` dado y devuelve una ``Explanation``.

    Orquesta prompt -> proveedor -> parseo. El proveedor por defecto (local
    llama.cpp) es un stub de Fase 1 y levanta ``NotImplementedError`` al generar.
    """
    cfg = config if config is not None else Config()
    prompt = build(text, nivel)
    provider = get_provider(cfg)
    raw = provider.generate(prompt)
    return parse(raw)


def _norm(line: str) -> str:
    """Minusculas sin acentos ni vinetas, para comparar encabezados con tolerancia."""
    nfkd = unicodedata.normalize("NFKD", line)
    sin_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sin_acentos.lower().lstrip("#-*. \t").strip()


def _match_header(line: str, keys: list[str]) -> str | None:
    """Si ``line`` empieza con un encabezado conocido, devuelve su clave normalizada."""
    norm = _norm(line)
    for key in keys:
        if norm.startswith(key):
            return key
    return None


def parse(raw: str) -> Explanation:
    """Parsea la respuesta cruda del modelo en las cuatro secciones (ADR 0007).

    Busca los cuatro encabezados conocidos, tolerando acentos y vinetas. Si falta
    alguna seccion, levanta ``ParseError`` en vez de rellenar con nada inventado.
    """
    keys = [key for key, _ in _SECTION_FIELDS]
    found: dict[str, str] = {}
    current: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        if current is not None:
            found[current] = "\n".join(buffer).strip()

    for line in raw.splitlines():
        header = _match_header(line, keys)
        if header is not None:
            flush()
            current = header
            buffer = []
            resto = line.split(":", 1)
            if len(resto) == 2 and resto[1].strip():
                buffer.append(resto[1].strip())
        elif current is not None:
            buffer.append(line)
    flush()

    faltan = [key for key in keys if key not in found]
    if faltan:
        raise ParseError(
            "La respuesta del modelo no trae las secciones: " + ", ".join(faltan)
        )
    valores = {campo: found[key] for key, campo in _SECTION_FIELDS}
    return Explanation(**valores)


__all__ = ["explain", "parse", "ParseError"]
