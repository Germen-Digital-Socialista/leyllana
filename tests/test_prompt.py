from leyllana.prompt import GUARDRAIL, build
from leyllana.types import DISCLAIMER, Explanation, Nivel


def test_build_includes_guardrail_and_sections():
    p = build("texto de la norma", Nivel.PUBLICO)
    assert GUARDRAIL in p.system
    for titulo in ("Que hace", "A quien afecta", "Articulos clave", "En una frase"):
        assert titulo in p.system
    assert "texto de la norma" in p.user


def test_disclaimer_is_rendered_not_asked_of_the_model():
    # El disclaimer lo garantiza el render (ADR 0008), no la obediencia del
    # modelo: pedirlo tambien en el prompt lo duplicaba y lo metia dentro de la
    # ultima seccion parseada.
    assert DISCLAIMER not in build("t", Nivel.PUBLICO).system
    assert DISCLAIMER in Explanation("q", "a", "art", "f").to_markdown()


def test_build_is_pure():
    assert build("t", Nivel.TECNICO) == build("t", Nivel.TECNICO)


def test_nivel_changes_register():
    assert build("t", Nivel.PUBLICO).system != build("t", Nivel.TECNICO).system


def test_build_includes_scoped_verbatim_citation_clause():
    # ADR 0014: los identificadores citados van tal como aparecen en el texto.
    p = build("Articulo 5. Algo.", Nivel.PUBLICO)
    assert "tal como aparece" in p.system.lower()
