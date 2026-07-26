"""Capa de prompt: arma el prompt en espanol con guardrail y disclaimer.

Pura, sin I/O (PRD seccion 7). Se sienta delante de todo proveedor por igual
(ADR 0003), lleva el guardrail anti-invencion (ADR 0008) y pide las cuatro
secciones fijas del contrato de salida (ADR 0007). El ``nivel`` cambia registro
y profundidad, nunca los hechos.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..types import DISCLAIMER, Nivel

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
_NIVEL_INSTRUCTIONS: dict[Nivel, str] = {
    Nivel.PUBLICO: (
        "Audiencia: publico general sin formacion juridica. Usa lenguaje llano y "
        "cotidiano, frases cortas, y evita tecnicismos; si un termino legal es "
        "inevitable, explicalo entre parentesis."
    ),
    Nivel.TECNICO: (
        "Audiencia: legisladores y asesores. Puedes usar el registro tecnico-"
        "legislativo, citar el articulado por su numero tal como aparece en el "
        "texto, y ser preciso y conciso."
    ),
}

# Cita verbatim acotada (ADR 0014): los identificadores (numero de articulo,
# fecha, monto, cifra) se copian tal como aparecen; el contenido se explica en
# lenguaje llano. Complementa el guardrail y hace cada mencion verificable por
# coincidencia de texto contra la fuente.
CITATION = (
    "Cuando nombres un articulo, una fecha, un monto o una cifra, escribe el numero "
    "o identificador tal como aparece en el texto (no lo renumeres ni redondees); "
    "explica su contenido en lenguaje llano."
)

# Las cuatro secciones fijas que debe devolver el modelo (ADR 0007).
_SECTIONS = (
    "Que hace: que hace la norma.",
    "A quien afecta: a quien obliga o afecta.",
    "Articulos clave: los articulos importantes, en lenguaje llano.",
    "En una frase: una sola frase con la idea central.",
)

# El contrato de salida es cerrado (ADR 0007): cuatro secciones y nada mas. Sin
# esto, un modelo conversacional responde con sus propios encabezados y agrega
# comentarios al lector, y el parseo no encuentra las secciones.
FORMATO = (
    "No agregues ninguna otra seccion, encabezado, introduccion ni cierre "
    "conversacional, y no te dirijas al lector con preguntas ni ofrecimientos. "
    "Si algo no esta en el texto, dilo dentro de la seccion que corresponda; no "
    "abras una seccion aparte para lo que falta."
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
    secciones = "\n".join(_SECTIONS)
    system = (
        "Eres leyllana, un asistente que explica leyes y boletines chilenos en "
        "lenguaje llano (espanol de Chile).\n\n"
        f"{GUARDRAIL}\n\n"
        f"{CITATION}\n\n"
        f"{_NIVEL_INSTRUCTIONS[nivel]}\n\n"
        "Responde SIEMPRE con estas cuatro secciones, en este orden, cada una "
        "empezando por su titulo exacto al inicio de una linea:\n"
        f"{secciones}\n\n"
        f"{FORMATO}\n\n"
        f"Cierra recordando al lector: {DISCLAIMER}"
    )
    user = f"Texto de la norma o boletin a explicar:\n\n{text}"
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


__all__ = ["Prompt", "build", "build_extract", "GUARDRAIL", "CITATION", "FORMATO"]
