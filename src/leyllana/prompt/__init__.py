"""Capa de prompt: arma el prompt en espanol con guardrail y disclaimer.

Pura, sin I/O (PRD seccion 7). Se sienta delante de todo proveedor por igual
(ADR 0003), lleva el guardrail anti-invencion (ADR 0008) y pide las cuatro
secciones fijas del contrato de salida (ADR 0007). El ``nivel`` cambia registro
y profundidad, nunca los hechos.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..types import ArticleChunk, Nivel

# Guardrail anti-invencion (ADR 0008): el modelo solo puede resumir lo que esta
# en el texto. Si el texto no alcanza, lo dice en vez de adivinar.
GUARDRAIL = (
    "Regla absoluta: explica UNICAMENTE lo que aparece en el texto entregado. "
    "No inventes articulos, numeros, citas, fechas, montos ni obligaciones. "
    "No agregues informacion externa ni interpretaciones legales. "
    "Si el texto no alcanza para responder una seccion, escribe exactamente "
    "'No se puede determinar a partir del texto entregado.' en esa seccion."
)

# Instrucciones de registro por nivel de audiencia (ADR 0007). Cambian tono y
# profundidad, no los hechos.
#
# Los dos niveles estan modelados sobre los dos registros que la Biblioteca del
# Congreso Nacional ya publica: las guias de lenguaje claro dirigidas a la
# ciudadania, y las minutas de asesoria tecnica dirigidas a quien trabaja el
# articulado. La idea es no inventar un formato: imitar los que existen.
#
# Ninguno de los dos nombra su fuente ni un rol concreto dentro del prompt. Ver
# el comentario de abajo sobre por que.
_NIVEL_INSTRUCTIONS: dict[Nivel, str] = {
    # El tope de articulos es deliberado: sin el, una ley larga produce un
    # catalogo de todo el articulado, fiel pero ilegible para quien no es
    # abogado, que es justamente el lector de este nivel.
    #
    # La audiencia se describe en abstracto a proposito. Nombrar un rol concreto
    # aqui ("la presidenta de una junta de vecinos") hizo que un modelo chico lo
    # tomara por materia de la norma y explicara una ley que no existe, con el
    # rol inventado dentro de las cuatro secciones y sin que nada fallara.
    Nivel.PUBLICO: (
        "Audiencia: una persona sin formacion juridica. Usa lenguaje llano y "
        "cotidiano, frases cortas, y evita tecnicismos; si un termino legal es "
        "inevitable, explicalo entre parentesis. Responde lo que esa persona "
        "necesita saber: si la norma la obliga a ella, que tendria que hacer y "
        "desde cuando, y que consecuencia hay si no lo hace. No enumeres todo el "
        "articulado: en 'Articulos clave' elige a lo mas cinco o seis articulos, "
        "los que de verdad le cambian algo a una persona comun, y deja fuera el "
        "resto. Si la norma no obliga a la gente comun sino al Estado o a cierto "
        "tipo de empresas, dilo claramente en 'A quien afecta' en vez de dar a "
        "entender que le aplica a cualquiera."
    ),
    # Este nivel manda, no autoriza. La version anterior decia "puedes usar el
    # registro tecnico-legislativo" y el resultado era practicamente el mismo que
    # el nivel publico: un permiso no cambia nada, y encima competia contra dos
    # instrucciones de "lenguaje llano" que estaban fuera de este switch.
    #
    # La lista de puntos sale de lo que un analisis de una norma chilena mira de
    # verdad. Va explicitamente condicionada a que el texto lo diga, porque una
    # lista de casilleros es justo lo que invita a rellenar el que falta: el
    # riesgo que corre este nivel no es quedarse corto, es completar de memoria.
    Nivel.TECNICO: (
        "Audiencia: quien tiene que trabajar la norma en detalle. Usa el registro "
        "tecnico-legislativo, se preciso y conciso, y no simplifiques el "
        "vocabulario juridico ni parafrasees el numero de un articulo. En "
        "'Articulos clave' no hay tope: cita todos los articulos que impongan una "
        "obligacion, un plazo, una sancion o una competencia.\n"
        "Cuando el texto entregado lo diga, deja constancia tambien de: el ambito "
        "de aplicacion y las definiciones; quienes son los sujetos obligados y "
        "desde cuando lo son; los plazos, con su forma de computo tal como "
        "aparezca; el regimen sancionatorio con sus montos y tramos; el organo que "
        "fiscaliza y sus facultades; los mecanismos de reclamo o de control "
        "judicial; lo que queda remitido a un reglamento; la entrada en vigencia y "
        "las disposiciones transitorias; y las normas que se modifican, sustituyen, "
        "intercalan o derogan.\n"
        "Lo que de esa lista el texto NO diga, no lo pongas: no completes con lo "
        "que suele ocurrir en otras leyes ni con lo que parezca razonable. Si el "
        "texto no lo dice, para esta explicacion no existe.\n"
        "Si no alcanzas a cubrir todo, prioriza en este orden: obligaciones, "
        "plazos, sanciones, quien fiscaliza. Es mejor una explicacion completa de "
        "lo importante que una lista cortada a la mitad."
    ),
}

# Cita verbatim acotada (ADR 0014): los identificadores (numero de articulo,
# fecha, monto, cifra) se copian tal como aparecen; el contenido se explica en
# lenguaje llano. Complementa el guardrail y hace cada mencion verificable por
# coincidencia de texto contra la fuente.
# No fija registro. Terminaba en "explica su contenido en lenguaje llano", y como
# esta constante corre para los dos niveles, era la tercera instruccion de registro
# llano que recibia el nivel tecnico. Lo que aqui importa es la distincion entre el
# identificador, que va literal, y el contenido, que va explicado: eso se conserva
# sin decir en que registro.
CITATION = (
    "Cuando nombres un articulo, una fecha, un monto o una cifra, escribe el numero "
    "o identificador tal como aparece en el texto (no lo renumeres ni redondees), y "
    "explica su contenido con tus palabras en vez de copiarlo entero."
)

# Las cuatro secciones fijas que debe devolver el modelo (ADR 0007). Los nombres
# son identicos en los dos niveles porque son el contrato de salida y lo que busca
# el parseo; lo que cambia es la descripcion de una linea de cada uno.
#
# La descripcion de 'Articulos clave' decia "en lenguaje llano" para los dos
# niveles. Estando fuera del switch de nivel, le ordenaba registro llano tambien
# al nivel tecnico, que solo lo tenia "permitido" no serlo. Era una de las dos
# razones por las que las dos salidas terminaban casi iguales.
_SECTIONS: dict[Nivel, tuple[str, ...]] = {
    Nivel.PUBLICO: (
        "Que hace: que hace la norma.",
        "A quien afecta: a quien obliga o afecta.",
        "Articulos clave: los articulos importantes, en lenguaje llano.",
        "En una frase: una sola frase con la idea central.",
    ),
    Nivel.TECNICO: (
        "Que hace: el objeto de la norma y lo que establece.",
        "A quien afecta: los sujetos obligados y el ambito de aplicacion.",
        "Articulos clave: el articulado relevante, citado por su numero.",
        "En una frase: una sola frase con la idea central.",
    ),
}

# El contrato de salida es cerrado (ADR 0007): cuatro secciones y nada mas. Sin
# esto, un modelo conversacional responde con sus propios encabezados y agrega
# comentarios al lector, y el parseo no encuentra las secciones.
FORMATO = (
    "No agregues ninguna otra seccion, encabezado, introduccion ni cierre "
    "conversacional, y no te dirijas al lector con preguntas ni ofrecimientos. "
    "Si algo no esta en el texto, dilo dentro de la seccion que corresponda; no "
    "abras una seccion aparte para lo que falta. Tampoco escribas un descargo de "
    "responsabilidad al final: la aplicacion lo agrega sola."
)


@dataclass(frozen=True)
class Prompt:
    """Prompt listo para un proveedor: mensaje de sistema + mensaje de usuario."""

    system: str
    user: str


def build(text: str, nivel: Nivel) -> Prompt:
    """Arma el ``Prompt`` en espanol para ``text`` en el ``nivel`` dado.

    Pura: mismas entradas -> mismo prompt, sin I/O.
    """
    secciones = "\n".join(_SECTIONS[nivel])
    system = (
        # El preambulo no fija registro. Antes decia "en lenguaje llano" aqui, y
        # como corre para los dos niveles, era la segunda instruccion que empujaba
        # al nivel tecnico de vuelta al registro del nivel publico. El registro lo
        # decide _NIVEL_INSTRUCTIONS y solo ahi.
        "Eres leyllana, un asistente que explica leyes y boletines chilenos "
        "(espanol de Chile).\n\n"
        f"{GUARDRAIL}\n\n"
        f"{CITATION}\n\n"
        f"{_NIVEL_INSTRUCTIONS[nivel]}\n\n"
        "Responde SIEMPRE con estas cuatro secciones, en este orden, cada una "
        "empezando por su titulo exacto al inicio de una linea:\n"
        f"{secciones}\n\n"
        f"{FORMATO}"
    )
    user = f"Texto de la norma o boletin a explicar:\n\n{text}"
    return Prompt(system=system, user=user)


# Se antepone a la instruccion de nivel existente: le dice al modelo que la
# eleccion de "elige a lo mas cinco o seis" ya esta resuelta, en vez de duplicar
# o contradecir esa frase dentro de _NIVEL_INSTRUCTIONS.
_SELECTION_INSTRUCTION = (
    "Los articulos de la seccion 'Articulos clave' YA fueron preseleccionados por un "
    "sistema de busqueda, y vienen listados abajo bajo 'Articulos preseleccionados'. "
    "La instruccion de 'elige a lo mas cinco o seis articulos' de mas arriba ya esta "
    "resuelta: explica esos articulos y solo esos, en el mismo orden en que aparecen. "
    "No elijas otros articulos, no agregues los que falten, no dejes ninguno de estos "
    "fuera."
)


def build_with_selection(
    overview: str, articles: list[ArticleChunk], nivel: Nivel
) -> Prompt:
    """Arma el ``Prompt`` cuando los articulos clave ya fueron preseleccionados
    (BM25 + reranker opcional, engine/ranking.py) en vez de dejar que el modelo
    elija.

    Solo tiene sentido para PUBLICO (el unico nivel con tope de articulos); ver
    docs/superpowers/specs/2026-07-30-fallback-article-selection-design.md.
    """
    secciones = "\n".join(_SECTIONS[nivel])
    system = (
        "Eres leyllana, un asistente que explica leyes y boletines chilenos "
        "(espanol de Chile).\n\n"
        f"{GUARDRAIL}\n\n"
        f"{CITATION}\n\n"
        f"{_NIVEL_INSTRUCTIONS[nivel]}\n\n"
        f"{_SELECTION_INSTRUCTION}\n\n"
        "Responde SIEMPRE con estas cuatro secciones, en este orden, cada una "
        "empezando por su titulo exacto al inicio de una linea:\n"
        f"{secciones}\n\n"
        f"{FORMATO}"
    )
    articulos_texto = "\n\n".join(f"{a.label}\n{a.text}" for a in articles)
    user = (
        f"Resumen de la norma o boletin:\n\n{overview}\n\n"
        f"Articulos preseleccionados:\n\n{articulos_texto}"
    )
    return Prompt(system=system, user=user)


def build_extract(chunk: str) -> Prompt:
    """Prompt para extraer puntos clave fieles de un FRAGMENTO (map de ADR 0017).

    No pide las cuatro secciones: pide vinetas fieles con la cita del articulo tal
    como aparece, para que la sintesis posterior trabaje sobre hechos anclados al
    texto y no sobre invenciones (ADR 0008, 0014).
    """
    system = (
        "Eres leyllana. Extrae los puntos clave de un FRAGMENTO de un texto legal "
        "chileno, de forma fiel y en espanol de Chile.\n\n"
        f"{GUARDRAIL}\n\n"
        "Devuelve solo una lista de vinetas concisas. En cada punto que corresponda "
        "a un articulo, cita su numero tal como aparece (por ejemplo 'Articulo 5'). "
        "No agregues nada que no este en el fragmento ni intentes resumir la norma "
        "completa: es solo un fragmento."
    )
    user = f"Fragmento del texto legal:\n\n{chunk}"
    return Prompt(system=system, user=user)


__all__ = [
    "Prompt",
    "build",
    "build_extract",
    "build_with_selection",
    "GUARDRAIL",
    "CITATION",
    "FORMATO",
]
