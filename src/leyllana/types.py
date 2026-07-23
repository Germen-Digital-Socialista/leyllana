"""Objetos de dominio de leyllana: nivel de audiencia y resultado estructurado.

Puros, sin I/O. Los usan por igual el ``engine``, la futura GUI y los tests.
Las secciones fijas provienen del contrato de salida (ADR 0007).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# Disclaimer visible en cada explicacion (PRD FR-7, ADR 0008). No es asesoria
# legal; es una ayuda de lectura.
DISCLAIMER = (
    "Esta explicacion es una ayuda de lectura generada automaticamente a partir "
    "del texto entregado. No es asesoria legal ni una interpretacion oficial. "
    "Ante cualquier duda, consulte el texto original y a un profesional."
)


class Nivel(str, Enum):
    """Registro de audiencia. Cambia tono y profundidad, nunca los hechos (ADR 0007)."""

    PUBLICO = "publico"
    TECNICO = "tecnico"


@dataclass(frozen=True)
class Explanation:
    """Salida estructurada en espanol. Cuatro secciones fijas + disclaimer (ADR 0007)."""

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

    def is_empty(self) -> bool:
        """True si no se identifico ningun dato de la fuente."""
        return all(
            valor is None
            for valor in (
                self.titulo,
                self.tipo_norma,
                self.organo_emisor,
                self.fecha,
                self.version,
                self.url,
                self.fecha_consulta,
            )
        )
