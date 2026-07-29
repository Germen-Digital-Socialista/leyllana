"""Tests del avance y la cancelacion de explain() (PRD FR-10, ADR 0019).

Hermeticos: proveedor falso inyectado por el parametro ``provider``, sin modelo ni
red. Lo que se comprueba es lo que la GUI necesita poder prometer: que el conteo
de fragmentos es real y que cancelar detiene el trabajo de verdad, no despues.
"""

import pytest

from leyllana.config import Config
from leyllana.engine import explain
from leyllana.engine.progress import (
    Cancelled,
    CancelToken,
    Progress,
    Stage,
    check,
    report,
)
from leyllana.types import Explanation, Nivel

_FOUR_SECTIONS = (
    "Que hace: regula algo.\n"
    "A quien afecta: a los organismos.\n"
    "Articulos clave: Articulo 1.\n"
    "En una frase: una ley."
)

# Suficientemente largo para no caber en el contexto por defecto (4096 tokens) y
# forzar el map-reduce, que es donde vive el conteo de fragmentos.
_LONG_TEXT = "".join(f"Articulo {i}. " + "palabra " * 80 + "\n" for i in range(1, 60))


class _FakeProvider:
    """Proveedor falso que distingue map de reduce por el system prompt."""

    def __init__(self, cancel_after: int | None = None, token=None):
        self.calls = 0
        self._cancel_after = cancel_after
        self._token = token

    def generate(self, prompt, *, cancel=None):
        self.calls += 1
        if self._cancel_after is not None and self.calls >= self._cancel_after:
            self._token.cancel()
        if "Extrae los puntos clave" in prompt.system:
            return f"- Punto clave {self.calls} (Articulo {self.calls})."
        return _FOUR_SECTIONS


def _run(text, provider, **kwargs):
    eventos: list[Progress] = []
    exp = explain(
        text,
        Nivel.PUBLICO,
        Config(),
        provider=provider,
        progress=eventos.append,
        **kwargs,
    )
    return exp, eventos


def test_explain_sin_progreso_ni_cancel_se_comporta_igual():
    # El contrato de la Fase 1: omitir los parametros nuevos no cambia nada.
    exp = explain(
        "Articulo 1. Texto breve.", Nivel.PUBLICO, Config(), provider=_FakeProvider()
    )
    assert isinstance(exp, Explanation)


def test_pasada_unica_no_reporta_fragmentos():
    exp, eventos = _run("Articulo 1. Texto breve que cabe sobrado.", _FakeProvider())
    assert isinstance(exp, Explanation)
    etapas = [e.stage for e in eventos]
    assert Stage.ANALIZANDO not in etapas  # no hubo map: nada que contar
    assert Stage.GENERANDO in etapas
    assert all(e.fragmento is None for e in eventos)


def test_documento_largo_reporta_fragmento_de_total():
    _, eventos = _run(_LONG_TEXT, _FakeProvider())
    fragmentos = [e for e in eventos if e.fragmento is not None]
    assert len(fragmentos) >= 2
    total = fragmentos[0].total
    # El total es el mismo en todos y los fragmentos van 1..total, sin saltos.
    assert [e.fragmento for e in fragmentos] == list(range(1, len(fragmentos) + 1))
    assert all(e.total == total for e in fragmentos)
    assert all(e.stage is Stage.ANALIZANDO for e in fragmentos)
    assert len(fragmentos) == total


def test_las_etapas_llegan_en_orden():
    _, eventos = _run(_LONG_TEXT, _FakeProvider())
    etapas = [e.stage for e in eventos]
    assert etapas.index(Stage.ANALIZANDO) < etapas.index(Stage.GENERANDO)
    assert etapas.index(Stage.GENERANDO) < etapas.index(Stage.VERIFICANDO)


def test_cancelar_antes_de_empezar_no_llama_al_proveedor():
    token = CancelToken()
    token.cancel()
    fake = _FakeProvider()
    with pytest.raises(Cancelled):
        explain(_LONG_TEXT, Nivel.PUBLICO, Config(), provider=fake, cancel=token)
    assert fake.calls == 0


def test_cancelar_a_medio_camino_detiene_el_map():
    # Cancela en la segunda llamada; el bucle no debe seguir pidiendo fragmentos.
    token = CancelToken()
    fake = _FakeProvider(cancel_after=2, token=token)
    with pytest.raises(Cancelled):
        explain(_LONG_TEXT, Nivel.PUBLICO, Config(), provider=fake, cancel=token)
    assert fake.calls == 2  # se detuvo donde se pidio, no al final


def test_cancel_token_es_idempotente():
    token = CancelToken()
    assert not token.is_cancelled()
    token.cancel()
    token.cancel()
    assert token.is_cancelled()
    with pytest.raises(Cancelled):
        token.raise_if_cancelled()


def test_check_y_report_sin_destinatario_no_hacen_nada():
    check(None)
    report(None, Stage.CARGANDO)


def test_texto_de_progreso_no_inventa_porcentaje():
    assert Progress(Stage.ANALIZANDO).texto() == "analizando"
    assert Progress(Stage.ANALIZANDO, 3, 13).texto() == (
        "analizando (fragmento 3 de 13)"
    )
    assert Progress(Stage.EXTRAYENDO).texto() == "extrayendo texto"
    assert Progress(Stage.ANALIZANDO, detalle="reduccion 1").texto() == (
        "analizando: reduccion 1"
    )
