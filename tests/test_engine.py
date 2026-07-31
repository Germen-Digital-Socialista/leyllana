import pytest

from leyllana.config import Config, EngineConfig
from leyllana.engine import ParseError, explain, parse, parse_overview
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


def test_parse_overview_extracts_the_three_narrative_sections():
    raw = (
        "Que hace: regula el tratamiento de datos.\n"
        "A quien afecta: a los responsables de bases de datos.\n"
        "En una frase: una ley de proteccion de datos."
    )
    got = parse_overview(raw)
    assert got["que_hace"] == "regula el tratamiento de datos."
    assert got["a_quien_afecta"] == "a los responsables de bases de datos."
    assert got["en_una_frase"] == "una ley de proteccion de datos."
    assert "articulos_clave" not in got


def test_parse_overview_drops_a_stray_articulos_clave_block():
    # Si el modelo agrega "Articulos clave" pese a que el resumen no la pidio, se
    # trata como limite de seccion y su contenido se descarta: esa seccion se arma
    # aparte, articulo por articulo, y no debe contaminar "Que hace".
    raw = (
        "Que hace: regula.\n"
        "Articulos clave: Articulo 1, Articulo 2.\n"
        "A quien afecta: a todos.\n"
        "En una frase: sintesis."
    )
    got = parse_overview(raw)
    assert got["que_hace"] == "regula."
    assert "Articulo 1" not in got["que_hace"]


def test_parse_overview_missing_section_raises():
    with pytest.raises(ParseError):
        parse_overview("Que hace: solo esto.\nA quien afecta: y esto.")


_OVERVIEW_THREE = (
    "Que hace: regula el tratamiento de datos personales.\n"
    "A quien afecta: a los responsables de bases de datos.\n"
    "En una frase: una ley de proteccion de datos."
)


class _FakeLocal(LocalProvider):
    """Proveedor local falso: distingue la llamada de resumen (tres secciones) de
    las de gloss por un articulo, y registra que texto vio cada gloss."""

    def __init__(self):
        self.overview_calls = 0
        self.gloss_user_texts = []

    def generate(self, prompt, *, cancel=None):
        if "tres secciones" in prompt.system:
            self.overview_calls += 1
            return _OVERVIEW_THREE
        self.gloss_user_texts.append(prompt.user)
        return "explicacion llana del articulo."


def test_publico_local_isolates_each_article_and_stamps_the_label():
    # El nucleo del arreglo de mala atribucion: un articulo por llamada (el modelo
    # nunca ve dos a la vez) y el numero lo estampa el pipeline, no el modelo.
    fake = _FakeLocal()
    text = (
        "Articulo 16.- La infraccion se castiga con multa de dos a cincuenta UTM.\n"
        "Articulo 17.- La comunicacion de datos de obligaciones economicas.\n"
        "Articulo 18.- El plazo maximo de comunicacion es de cinco anios.\n"
    )
    exp = explain(text, Nivel.PUBLICO, Config(), provider=fake)

    assert fake.overview_calls == 1  # un solo resumen
    assert len(fake.gloss_user_texts) == 3  # un gloss por articulo
    # Aislamiento: cada gloss vio exactamente UN articulo, nunca dos concatenados.
    openers = ["Articulo 16", "Articulo 17", "Articulo 18"]
    for user in fake.gloss_user_texts:
        present = [o for o in openers if o in user]
        assert len(present) == 1, user
    # "Articulos clave" lo arma el pipeline: un bullet estampado por articulo.
    assert "- **Articulo 16:** explicacion llana del articulo." in exp.articulos_clave
    assert "- **Articulo 17:**" in exp.articulos_clave
    assert "- **Articulo 18:**" in exp.articulos_clave
    # Las tres secciones narrativas vienen del resumen.
    assert exp.que_hace == "regula el tratamiento de datos personales."
    assert exp.en_una_frase == "una ley de proteccion de datos."
