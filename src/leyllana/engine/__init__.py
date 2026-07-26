"""Capa de engine: ``explain(text, nivel)`` sobre un proveedor swappable (ADR 0003).

Arma el prompt (con guardrail y disclaimer), elige el proveedor segun la config,
genera la respuesta cruda y la parsea en las cuatro secciones fijas del contrato
de salida (ADR 0007). El parseo es puro y testeable. El proveedor local corre un
``llama-server`` local (ADR 0016); un documento que no cabe en el contexto se
condensa antes con un map-reduce fiel (ADR 0017).
"""

from __future__ import annotations

import unicodedata

from ..config import Config
from ..prompt import build, build_extract
from ..types import Explanation, Nivel
from .base import ConsentRequired, Provider
from .chunking import chars_for_tokens, estimate_tokens, split_structural
from .registry import get_provider

# Reserva de tokens para el system prompt y sus instrucciones (fuera del texto).
_SYSTEM_RESERVE_TOKENS = 600
# Tope de niveles de reduccion jerarquica antes de conformarse (ADR 0017).
_MAX_REDUCE_DEPTH = 3


class ParseError(RuntimeError):
    """La respuesta del modelo no trae las cuatro secciones esperadas (ADR 0007)."""


# Encabezado de seccion (normalizado, sin acentos) -> campo de ``Explanation``.
_SECTION_FIELDS = (
    ("que hace", "que_hace"),
    ("a quien afecta", "a_quien_afecta"),
    ("articulos clave", "articulos_clave"),
    ("en una frase", "en_una_frase"),
)


def explain(
    text: str,
    nivel: Nivel,
    config: Config | None = None,
    consent: bool = False,
) -> Explanation:
    """Explica ``text`` en el ``nivel`` dado y devuelve una ``Explanation``.

    Orquesta prompt -> proveedor -> parseo. Si el texto no cabe en el contexto del
    modelo, primero se condensa con un map-reduce fiel (ADR 0017): se extraen puntos
    clave por fragmento y la sintesis final trabaja sobre esos puntos.

    ``consent`` es la accion afirmativa que exige ADR 0013: sin ella, un proveedor
    que saca el documento del equipo levanta ``ConsentRequired`` antes de enviar
    nada. El proveedor local no la necesita ni la mira.
    """
    cfg = config if config is not None else Config()
    provider = get_provider(cfg)
    _check_consent(provider, consent)
    condensed = _condense(text, provider, cfg)
    raw = provider.generate(build(condensed, nivel))
    return parse(raw)


def _check_consent(provider: Provider, consent: bool) -> None:
    """Corta el envio a la nube sin consentimiento explicito (ADR 0013).

    Corre antes de la primera llamada al proveedor, asi que tampoco se envia el
    primer fragmento del map-reduce.
    """
    if consent or not getattr(provider, "sends_to_cloud", False):
        return
    destino = getattr(provider, "destino", "un proveedor de nube")
    raise ConsentRequired(
        f"Este envio saca el documento de su equipo hacia {destino}. "
        "Se requiere su consentimiento explicito antes de enviar nada."
    )


def _budget_tokens(config: Config) -> int:
    """Tokens de texto que caben dejando espacio al system prompt y a la salida."""
    engine = config.engine
    return engine.default_model.ctx - engine.max_tokens - _SYSTEM_RESERVE_TOKENS


def _condense(
    text: str, provider: Provider, config: Config, _depth: int = 0
) -> str:
    """Devuelve texto que cabe en el contexto: el original, o puntos clave (ADR 0017).

    Si ``text`` cabe, se devuelve tal cual (pasada unica). Si no, se parte en
    fragmentos por estructura, se extraen puntos clave fieles de cada uno (map) y se
    juntan; si el conjunto aun no cabe, se reduce jerarquicamente hasta un tope.
    """
    budget = _budget_tokens(config)
    if estimate_tokens(text) <= budget or budget <= 0:
        return text

    max_chars = chars_for_tokens(budget)
    points = [
        provider.generate(build_extract(chunk)).strip()
        for chunk in split_structural(text, max_chars=max_chars)
    ]
    pooled = "\n".join(p for p in points if p)

    if (
        estimate_tokens(pooled) > budget
        and _depth < _MAX_REDUCE_DEPTH
        and len(pooled) < len(text)
    ):
        return _condense(pooled, provider, config, _depth + 1)
    return pooled


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


__all__ = ["explain", "parse", "ParseError", "ConsentRequired"]
