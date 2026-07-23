import pytest

from leyllana.config import Config, EngineConfig
from leyllana.engine import ParseError, explain, parse
from leyllana.engine.base import ProviderError
from leyllana.engine.local import LocalProvider
from leyllana.engine.registry import get_provider
from leyllana.types import Explanation, Nivel


def test_registry_local_returns_local_provider():
    assert isinstance(get_provider(Config()), LocalProvider)


def test_registry_unknown_raises_value_error():
    cfg = Config(engine=EngineConfig(provider="acme"))
    with pytest.raises(ValueError):
        get_provider(cfg)


def test_registry_cloud_not_implemented():
    cfg = Config(engine=EngineConfig(provider="claude"))
    with pytest.raises(NotImplementedError):
        get_provider(cfg)


def test_explain_local_unconfigured_raises_provider_error():
    # Sin server_path ni modelo configurados, el proveedor local falla ruidosamente
    # en vez de continuar (ADR 0016).
    with pytest.raises(ProviderError):
        explain("texto", Nivel.PUBLICO)


def test_parse_splits_four_sections():
    raw = (
        "Que hace: regula algo.\n"
        "A quien afecta: a los organismos.\n"
        "Articulos clave: Articulo 1.\n"
        "En una frase: una ley sobre IA."
    )
    exp = parse(raw)
    assert isinstance(exp, Explanation)
    assert exp.que_hace == "regula algo."
    assert exp.a_quien_afecta == "a los organismos."
    assert exp.en_una_frase == "una ley sobre IA."


def test_parse_tolerates_accents_and_bullets():
    raw = (
        "## Qué hace: regula.\n"
        "- A quién afecta: a todos.\n"
        "Artículos clave: Art. 1.\n"
        "En una frase: sintesis."
    )
    exp = parse(raw)
    assert exp.que_hace == "regula."
    assert exp.a_quien_afecta == "a todos."


def test_parse_missing_section_raises():
    with pytest.raises(ParseError):
        parse("Que hace: solo esto.")
