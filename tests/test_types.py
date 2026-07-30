from leyllana.types import DISCLAIMER, ArticleChunk, Explanation, Nivel, SourceInfo


def test_article_chunk_is_frozen():
    chunk = ArticleChunk(label="Articulo 1", text="Articulo 1. Texto.")
    assert chunk.label == "Articulo 1"
    assert chunk.text == "Articulo 1. Texto."


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


def test_sourceinfo_to_markdown_empty_is_blank():
    assert SourceInfo().to_markdown() == ""


def test_sourceinfo_to_markdown_renders_known_fields_only():
    info = SourceInfo(
        titulo="ESTABLECE BASES", tipo_norma="Ley 19880", url="https://x"
    )
    md = info.to_markdown()
    assert md.startswith("## Fuente")
    assert "ESTABLECE BASES" in md
    assert "Ley 19880" in md
    assert "https://x" in md
    assert "emisor" not in md.lower()  # un campo None no aparece
