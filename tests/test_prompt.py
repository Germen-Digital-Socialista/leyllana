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


def test_publico_no_nombra_un_rol_concreto():
    # Nombrar un rol en la descripcion de audiencia ("la presidenta de una junta
    # de vecinos") hizo que un modelo chico lo tomara por materia de la norma y
    # explicara una ley inexistente, pasando el parseo sin fallar. La audiencia va
    # en abstracto; el tope de articulos, que es lo que hace legible la salida, se
    # mantiene.
    system = build("Articulo 1. Algo.", Nivel.PUBLICO).system
    for rol in ("junta de vecinos", "presidenta", "alcalde", "senador"):
        assert rol not in system.lower()
    assert "cinco o seis" in system


def test_build_is_pure():
    assert build("t", Nivel.TECNICO) == build("t", Nivel.TECNICO)


def test_nivel_changes_register():
    assert build("t", Nivel.PUBLICO).system != build("t", Nivel.TECNICO).system


def test_el_registro_llano_solo_aplica_al_nivel_publico():
    # La causa concreta de que las dos salidas fueran casi iguales: "lenguaje
    # llano" aparecia en el preambulo y en la descripcion de 'Articulos clave',
    # los dos fuera del switch de nivel, asi que el nivel tecnico recibia la orden
    # de escribir llano y solo tenia "permitido" no hacerlo.
    publico = build("Articulo 1. Algo.", Nivel.PUBLICO).system
    tecnico = build("Articulo 1. Algo.", Nivel.TECNICO).system
    assert "lenguaje llano" in publico
    assert "lenguaje llano" not in tecnico


def test_el_nivel_tecnico_manda_en_vez_de_autorizar():
    # "Puedes usar el registro tecnico-legislativo" no cambiaba nada: un permiso
    # no es una instruccion.
    tecnico = build("Articulo 1. Algo.", Nivel.TECNICO).system
    assert "puedes usar" not in tecnico.lower()
    assert "usa el registro tecnico-legislativo" in tecnico.lower()


def test_solo_el_nivel_publico_topea_los_articulos():
    # El tope hace legible la salida para quien no es abogado, y le quitaria a
    # quien trabaja el articulado justamente lo que necesita.
    assert "cinco o seis" in build("t", Nivel.PUBLICO).system
    assert "cinco o seis" not in build("t", Nivel.TECNICO).system
    assert "no hay tope" in build("t", Nivel.TECNICO).system


def test_el_nivel_tecnico_pide_los_puntos_de_una_norma_chilena():
    tecnico = build("t", Nivel.TECNICO).system.lower()
    for punto in (
        "ambito de aplicacion",
        "sujetos obligados",
        "plazos",
        "regimen sancionatorio",
        "fiscaliza",
        "control",
        "reglamento",
        "entrada en vigencia",
        "disposiciones transitorias",
        "derogan",
    ):
        assert punto in tecnico, punto


def test_la_lista_del_nivel_tecnico_va_condicionada_al_texto():
    # Una lista de puntos es una lista de casilleros, y un casillero vacio invita
    # a rellenarlo. Sin esta condicion el nivel tecnico inventaria el quorum o el
    # organo fiscalizador cuando la fuente no los menciona.
    tecnico = build("t", Nivel.TECNICO).system
    assert "Cuando el texto entregado lo diga" in tecnico
    assert "no lo pongas" in tecnico
    assert "para esta explicacion no existe" in tecnico


def test_las_cuatro_secciones_se_llaman_igual_en_los_dos_niveles():
    # Los nombres son el contrato de salida y lo que busca el parseo (ADR 0007);
    # lo que cambia es su descripcion, no su titulo.
    for titulo in ("Que hace", "A quien afecta", "Articulos clave", "En una frase"):
        assert titulo in build("t", Nivel.PUBLICO).system
        assert titulo in build("t", Nivel.TECNICO).system


def test_build_includes_scoped_verbatim_citation_clause():
    # ADR 0014: los identificadores citados van tal como aparecen en el texto.
    p = build("Articulo 5. Algo.", Nivel.PUBLICO)
    assert "tal como aparece" in p.system.lower()
