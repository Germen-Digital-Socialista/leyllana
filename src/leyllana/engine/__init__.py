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
from ..prompt import build, build_extract, build_with_selection
from ..types import Explanation, Nivel
from .base import ConsentRequired, Provider
from .chunking import chars_for_tokens, estimate_tokens, split_structural
from .local import LocalProvider
from .progress import (
    Cancelled,
    CancelToken,
    Progress,
    ProgressFn,
    Stage,
    check,
    report,
)
from .ranking import RerankerClient, select_key_articles
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
    *,
    progress: ProgressFn | None = None,
    cancel: CancelToken | None = None,
    provider: Provider | None = None,
) -> Explanation:
    """Explica ``text`` en el ``nivel`` dado y devuelve una ``Explanation``.

    Orquesta prompt -> proveedor -> parseo. Si el texto no cabe en el contexto del
    modelo, primero se condensa con un map-reduce fiel (ADR 0017): se extraen puntos
    clave por fragmento y la sintesis final trabaja sobre esos puntos.

    ``consent`` es la accion afirmativa que exige ADR 0013: sin ella, un proveedor
    que saca el documento del equipo levanta ``ConsentRequired`` antes de enviar
    nada. El proveedor local no la necesita ni la mira.

    Los tres parametros de palabra clave son para la GUI (ADR 0019) y son
    opcionales: omitidos, esta funcion se comporta exactamente como antes.

    - ``progress`` recibe un ``Progress`` en cada etapa y en cada fragmento.
    - ``cancel`` se consulta antes de cada llamada al proveedor; si el usuario
      cancelo, se levanta ``Cancelled``.
    - ``provider`` reutiliza un proveedor ya construido en vez de crear uno. Es lo
      que permite a la GUI mantener el ``llama-server`` caliente entre corridas,
      en lugar de recargar el GGUF cada vez.
    """
    cfg = config if config is not None else Config()
    check(cancel)
    if provider is None:
        report(progress, Stage.CARGANDO)
        provider = get_provider(cfg)
    _check_consent(provider, consent)
    condensed = _condense(text, provider, cfg, progress=progress, cancel=cancel)
    check(cancel)
    report(progress, Stage.GENERANDO)
    if nivel == Nivel.PUBLICO and isinstance(provider, LocalProvider):
        reranker = _reranker_for(cfg)
        try:
            articulos = select_key_articles(text, nivel, reranker=reranker)
            raw = provider.generate(
                build_with_selection(condensed, articulos, nivel), cancel=cancel
            )
        finally:
            if reranker is not None:
                reranker.close()
    else:
        raw = provider.generate(build(condensed, nivel), cancel=cancel)
    report(progress, Stage.VERIFICANDO)
    return parse(raw)


def _reranker_for(config: Config) -> RerankerClient | None:
    """Construye un ``RerankerClient`` si hay un modelo re-rankeador configurado.

    Sin ``reranker_model.path``, ``select_key_articles`` sigue funcionando con
    BM25 solo (ADR-style graceful degrade, no un error)."""
    engine = config.engine
    if not engine.reranker_model.path or not engine.server_path:
        return None
    return RerankerClient(
        engine.server_path, engine.reranker_model.path, ctx=engine.reranker_model.ctx
    )


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


def _budget_tokens(config: Config, provider: Provider) -> int:
    """Tokens de texto que caben dejando espacio al system prompt y a la salida.

    El contexto lo pone el proveedor cuando lo declara (un CLI de nube tiene mucho
    mas que el modelo local, ADR 0018); si no, manda el del modelo local.
    """
    engine = config.engine
    ctx = getattr(provider, "ctx_tokens", None) or engine.default_model.ctx
    return ctx - engine.max_tokens - _SYSTEM_RESERVE_TOKENS


def _condense(
    text: str,
    provider: Provider,
    config: Config,
    _depth: int = 0,
    *,
    progress: ProgressFn | None = None,
    cancel: CancelToken | None = None,
) -> str:
    """Devuelve texto que cabe en el contexto: el original, o puntos clave (ADR 0017).

    Si ``text`` cabe, se devuelve tal cual (pasada unica). Si no, se parte en
    fragmentos por estructura, se extraen puntos clave fieles de cada uno (map) y se
    juntan; si el conjunto aun no cabe, se reduce jerarquicamente hasta un tope.

    El bucle del map es el unico trabajo contable de toda la corrida, asi que es de
    aqui que sale el "fragmento 3 de 13" que pide FR-10, y es aqui donde la
    cancelacion corta entre fragmentos.
    """
    budget = _budget_tokens(config, provider)
    if estimate_tokens(text) <= budget or budget <= 0:
        return text

    max_chars = chars_for_tokens(budget)
    chunks = split_structural(text, max_chars=max_chars)
    total = len(chunks)
    points: list[str] = []
    for i, chunk in enumerate(chunks, start=1):
        check(cancel)
        report(progress, Stage.ANALIZANDO, fragmento=i, total=total)
        points.append(provider.generate(build_extract(chunk), cancel=cancel).strip())
    pooled = "\n".join(p for p in points if p)

    if (
        estimate_tokens(pooled) > budget
        and _depth < _MAX_REDUCE_DEPTH
        and len(pooled) < len(text)
    ):
        report(progress, Stage.ANALIZANDO, detalle=f"reduccion {_depth + 1}")
        return _condense(
            pooled, provider, config, _depth + 1, progress=progress, cancel=cancel
        )
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


__all__ = [
    "explain",
    "parse",
    "ParseError",
    "ConsentRequired",
    "Cancelled",
    "CancelToken",
    "Progress",
    "Stage",
]
