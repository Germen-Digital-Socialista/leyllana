"""Objetos de dominio de leyllana: nivel de audiencia y resultado estructurado.

Puros, sin I/O. Los usan por igual el ``engine``, la futura GUI y los tests.
Las secciones fijas provienen del contrato de salida (ADR 0007).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

# Disclaimer visible en cada explicacion (PRD FR-7, ADR 0008). No es asesoria
# legal; es una ayuda de lectura.
DISCLAIMER = (
    "Esta explicacion es una ayuda de lectura generada automaticamente a partir "
    "del texto entregado. No es asesoria legal ni una interpretacion oficial. "
    "Ante cualquier duda, consulte el texto original y a un profesional."
)


class Nivel(StrEnum):
    """Registro de audiencia. Cambia tono y profundidad, nunca los hechos (ADR 0007)."""

    PUBLICO = "publico"
    TECNICO = "tecnico"


@dataclass(frozen=True)
class ArticleChunk:
    """Un articulo (u otro marcador estructural) con su etiqueta, para trazabilidad.

    A diferencia de los trozos de ``chunking.split_structural``, cada ``ArticleChunk``
    es exactamente un marcador, sin agrupar varios juntos: el ranking
    (engine/ranking.py) necesita poder puntuar y citar cada articulo por separado.
    Vive aqui (no en engine/chunking.py) porque tanto ``engine`` como ``prompt`` lo
    necesitan, y ``engine/__init__.py`` ya importa de ``prompt`` -- ponerlo en
    ``engine.chunking`` habria armado un ciclo de imports.
    """

    label: str
    text: str


@dataclass(frozen=True)
class Explanation:
    """Salida estructurada: cuatro secciones fijas + disclaimer (ADR 0007)."""

    que_hace: str
    a_quien_afecta: str
    articulos_clave: str
    en_una_frase: str
    disclaimer: str = DISCLAIMER

    def to_markdown(self) -> str:
        """Renderiza la explicacion como Markdown (PRD FR-8)."""
        return (
            f"## Que hace\n\n{self.que_hace}\n\n"
            f"## A quien afecta\n\n{self.a_quien_afecta}\n\n"
            f"## Articulos clave\n\n{self.articulos_clave}\n\n"
            f"## En una frase\n\n{self.en_una_frase}\n\n"
            f"---\n\n_{self.disclaimer}_\n"
        )


@dataclass(frozen=True)
class SourceInfo:
    """Identificacion de la fuente (PRD FR-7.1).

    Solo se muestra lo que se puede extraer; nunca se inventa (misma regla que el
    guardrail anti-invencion, ADR 0008). Todos los campos son opcionales: un campo
    en ``None`` significa "no se pudo determinar", no un dato inventado.
    """

    titulo: str | None = None
    tipo_norma: str | None = None
    organo_emisor: str | None = None
    fecha: str | None = None
    version: str | None = None
    url: str | None = None
    fecha_consulta: str | None = None

    def _campos(self) -> tuple[tuple[str, str | None], ...]:
        return (
            ("Titulo", self.titulo),
            ("Tipo de norma", self.tipo_norma),
            ("Organo emisor", self.organo_emisor),
            ("Fecha", self.fecha),
            ("Version", self.version),
            ("URL", self.url),
            ("Fecha de consulta", self.fecha_consulta),
        )

    def is_empty(self) -> bool:
        """True si no se identifico ningun dato de la fuente."""
        return all(valor is None for _, valor in self._campos())

    def to_markdown(self) -> str:
        """Renderiza el bloque de Fuente con los campos identificados (FR-7.1).

        Solo muestra los campos no vacios; un campo en ``None`` (no determinado)
        no aparece, nunca se inventa. Devuelve ``""`` si no hay nada que mostrar.
        """
        lineas = [f"- **{etq}:** {val}" for etq, val in self._campos() if val]
        if not lineas:
            return ""
        return "## Fuente\n\n" + "\n".join(lineas) + "\n"
