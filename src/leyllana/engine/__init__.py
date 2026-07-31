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
from ..prompt import build, build_extract, build_gloss, build_overview
from ..types import Explanation, Nivel
from .base import ConsentRequired, Provider
from .chunking import chars_for_tokens, estimate_tokens, short_label, split_structural
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

# Las tres secciones narrativas (todas menos "Articulos clave"): las produce la
# llamada de resumen del camino de aislamiento por articulo (ADR/ROADMAP
# After-number). "Articulos clave" se arma aparte, articulo por articulo.
_OVERVIEW_FIELDS = tuple(
    (key, attr) for key, attr in _SECTION_FIELDS if key != "articulos clave"
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
        explanation = _explain_by_isolation(
            text, condensed, provider, cfg, nivel, progress=progress, cancel=cancel
        )
        report(progress, Stage.VERIFICANDO)
        return explanation
    raw = provider.generate(build(condensed, nivel), cancel=cancel)
    report(progress, Stage.VERIFICANDO)
    return parse(raw)


def _explain_by_isolation(
    text: str,
    condensed: str,
    provider: Provider,
    config: Config,
    nivel: Nivel,
    *,
    progress: ProgressFn | None = None,
    cancel: CancelToken | None = None,
) -> Explanation:
    """Camino PUBLICO local: arma "Articulos clave" articulo por articulo.

    Las tres secciones narrativas salen de una llamada de resumen; "Articulos
    clave" se arma explicando cada articulo preseleccionado en su propia llamada
    (viendo solo su texto) y estampando el numero con ``short_label``. Asi el modelo
    no ve dos articulos a la vez ni elige el numero, que es el modo por el que
    atribuia el contenido de un articulo al numero de otro (ROADMAP After-number,
    spec docs/superpowers/specs/2026-07-31-per-article-isolation-design.md).

    El bucle por articulo es trabajo contable: alimenta el "fragmento i de N" de
    FR-10 y es donde la cancelacion corta entre llamadas.
    """
    reranker = _reranker_for(config)
    try:
        # Presupuesto de tokens para los articulos, no solo cantidad: unos pocos
        # articulos largos pueden pesar mas que el presupuesto entero del prompt
        # (medido en una ley real). Ver el docstring de select_key_articles.
        articulo_budget = max(
            0, _budget_tokens(config, provider) - estimate_tokens(condensed)
        )
        articulos = select_key_articles(
            text, nivel, reranker=reranker, max_tokens=articulo_budget
        )
        narrativa = parse_overview(
            provider.generate(build_overview(condensed, articulos, nivel), cancel=cancel)
        )
        total = len(articulos)
        bullets: list[str] = []
        for i, art in enumerate(articulos, start=1):
            check(cancel)
            report(progress, Stage.GENERANDO, fragmento=i, total=total)
            gloss = provider.generate(build_gloss(art, nivel), cancel=cancel).strip()
            bullets.append(f"- **{short_label(art.label)}:** {gloss}")
    finally:
        if reranker is not None:
            reranker.close()
    return Explanation(articulos_clave="\n".join(bullets), **narrativa)


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


# Todas las claves de seccion conocidas son limite de seccion al parsear, aunque
# solo se pida un subconjunto: asi un "Articulos clave" que el modelo agregue de mas
# corta la seccion anterior y su contenido se descarta, en vez de contaminarla.
_ALL_SECTION_KEYS = [key for key, _ in _SECTION_FIELDS]


def _extract_sections(raw: str, want_keys: list[str]) -> dict[str, str]:
    """Devuelve el texto de cada seccion en ``want_keys``, tolerando acentos y
    vinetas. Cualquier encabezado conocido corta seccion; solo se exigen y se
    devuelven las de ``want_keys``. Si falta alguna, levanta ``ParseError`` en vez
    de rellenar con nada inventado."""
    found: dict[str, str] = {}
    current: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        if current is not None:
            found[current] = "\n".join(buffer).strip()

    for line in raw.splitlines():
        header = _match_header(line, _ALL_SECTION_KEYS)
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

    faltan = [key for key in want_keys if key not in found]
    if faltan:
        raise ParseError(
            "La respuesta del modelo no trae las secciones: " + ", ".join(faltan)
        )
    return {key: found[key] for key in want_keys}


def parse(raw: str) -> Explanation:
    """Parsea la respuesta cruda del modelo en las cuatro secciones (ADR 0007).

    Busca los cuatro encabezados conocidos, tolerando acentos y vinetas. Si falta
    alguna seccion, levanta ``ParseError`` en vez de rellenar con nada inventado.
    """
    sections = _extract_sections(raw, _ALL_SECTION_KEYS)
    valores = {campo: sections[key] for key, campo in _SECTION_FIELDS}
    return Explanation(**valores)


def parse_overview(raw: str) -> dict[str, str]:
    """Parsea la respuesta del resumen en las tres secciones narrativas.

    Devuelve ``{campo: texto}`` para ``que_hace``, ``a_quien_afecta`` y
    ``en_una_frase`` (los campos de ``Explanation`` que no son "Articulos clave").
    Un "Articulos clave" que el modelo agregue de mas se descarta. Misma disciplina
    anti-invencion que ``parse``: si falta una de las tres, levanta ``ParseError``.
    """
    sections = _extract_sections(raw, [key for key, _ in _OVERVIEW_FIELDS])
    return {campo: sections[key] for key, campo in _OVERVIEW_FIELDS}


__all__ = [
    "explain",
    "parse",
    "parse_overview",
    "ParseError",
    "ConsentRequired",
    "Cancelled",
    "CancelToken",
    "Progress",
    "Stage",
]
