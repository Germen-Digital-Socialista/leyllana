from leyllana.prompt import GUARDRAIL, build
from leyllana.types import DISCLAIMER, Nivel


def test_build_includes_guardrail_sections_and_disclaimer():
    p = build("texto de la norma", Nivel.PUBLICO)
    assert GUARDRAIL in p.system
    assert DISCLAIMER in p.system
    for titulo in ("Que hace", "A quien afecta", "Articulos clave", "En una frase"):
        assert titulo in p.system
    assert "texto de la norma" in p.user


def test_build_is_pure():
    assert build("t", Nivel.TECNICO) == build("t", Nivel.TECNICO)


def test_nivel_changes_register():
    assert build("t", Nivel.PUBLICO).system != build("t", Nivel.TECNICO).system
