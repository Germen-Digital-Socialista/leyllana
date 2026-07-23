from leyllana.types import DISCLAIMER, Explanation, Nivel, SourceInfo


def test_explanation_markdown_has_four_sections_and_disclaimer():
    exp = Explanation(
        que_hace="Hace algo.",
        a_quien_afecta="A todos.",
        articulos_clave="Art. 1.",
        en_una_frase="Una frase.",
    )
    md = exp.to_markdown()
    assert "## Que hace" in md
    assert "## A quien afecta" in md
    assert "## Articulos clave" in md
    assert "## En una frase" in md
    assert DISCLAIMER in md


def test_nivel_values():
    assert Nivel.PUBLICO.value == "publico"
    assert Nivel.TECNICO.value == "tecnico"


def test_sourceinfo_empty_by_default():
    assert SourceInfo().is_empty()


def test_sourceinfo_not_empty_with_any_field():
    assert SourceInfo(titulo="Ley 21.000").is_empty() is False
