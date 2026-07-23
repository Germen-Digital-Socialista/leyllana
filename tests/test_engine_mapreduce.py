"""Tests del map-reduce de documentos largos en explain() (ADR 0017).

Hermeticos: se inyecta un proveedor falso via get_provider, que distingue las
llamadas de extraccion (map) de la de sintesis (reduce) por el texto del system
prompt. Sin modelo ni red.
"""

from leyllana.config import Config
from leyllana.engine import explain
from leyllana.types import Explanation, Nivel

_FOUR_SECTIONS = (
    "Que hace: regula algo.\n"
    "A quien afecta: a los organismos.\n"
    "Articulos clave: Articulo 1.\n"
    "En una frase: una ley."
)


class _FakeProvider:
    def __init__(self):
        self.extract_calls = 0
        self.synth_calls = 0
        self.last_synth_user = None

    def generate(self, prompt):
        if "Extrae los puntos clave" in prompt.system:
            n = self.extract_calls = self.extract_calls + 1
            return f"- Punto clave {n} (Articulo {n})."
        self.synth_calls += 1
        self.last_synth_user = prompt.user
        return _FOUR_SECTIONS


def _use_fake(monkeypatch, fake):
    monkeypatch.setattr("leyllana.engine.get_provider", lambda cfg: fake)


def test_explain_single_pass_when_text_fits(monkeypatch):
    fake = _FakeProvider()
    _use_fake(monkeypatch, fake)
    exp = explain("Articulo 1. Texto breve que cabe sobrado.", Nivel.PUBLICO, Config())
    assert isinstance(exp, Explanation)
    assert fake.extract_calls == 0  # no hubo map
    assert fake.synth_calls == 1  # una sola pasada


def test_explain_map_reduces_long_text(monkeypatch):
    fake = _FakeProvider()
    _use_fake(monkeypatch, fake)
    long_text = "".join(
        f"Articulo {i}. " + "palabra " * 80 + "\n" for i in range(1, 60)
    )
    exp = explain(long_text, Nivel.PUBLICO, Config())
    assert isinstance(exp, Explanation)
    assert fake.extract_calls >= 2  # se dividio en varios chunks (map)
    assert fake.synth_calls == 1  # una sola sintesis final (reduce)


def test_synthesis_runs_over_extracted_points_not_raw(monkeypatch):
    fake = _FakeProvider()
    _use_fake(monkeypatch, fake)
    long_text = "".join(
        f"Articulo {i}. " + "palabra " * 80 + "\n" for i in range(1, 60)
    )
    explain(long_text, Nivel.PUBLICO, Config())
    # La sintesis final recibe los puntos clave extraidos, no el texto crudo enorme.
    assert "Punto clave" in fake.last_synth_user
    assert "palabra palabra palabra" not in fake.last_synth_user
