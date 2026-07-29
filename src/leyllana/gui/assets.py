"""Localizacion de los archivos de marca (logo e icono).

Los SVG viven en ``assets/`` en la raiz del repo, que es su lugar canonico y
donde ya estaba el logo de Germen Digital Socialista. En una instalacion armada
llegan dentro del paquete (ver ``force-include`` en ``pyproject.toml``), asi que
se busca primero al lado de este modulo y despues subiendo hasta la raiz.

Si no aparece, se devuelve ``None`` y la ventana se abre igual sin icono: faltar
un adorno no es motivo para no arrancar.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

# El icono es la variante simplificada, legible a 16x16; el logo es el detallado.
ICONO = "icon-leyllana.svg"
LOGO = "logo-leyllana.svg"


@lru_cache(maxsize=8)
def ruta(nombre: str) -> Path | None:
    """Ruta absoluta del archivo de marca ``nombre``, o ``None`` si no esta."""
    aqui = Path(__file__).resolve().parent
    candidatos = [aqui / "assets" / nombre, aqui / nombre]
    # Subiendo desde src/leyllana/gui hasta la raiz del repo.
    for padre in aqui.parents:
        candidatos.append(padre / "assets" / nombre)
    for candidato in candidatos:
        if candidato.is_file():
            return candidato
    return None


__all__ = ["ICONO", "LOGO", "ruta"]
