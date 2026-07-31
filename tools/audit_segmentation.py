"""Audita la segmentacion por articulo de ``split_by_article`` sobre un corpus.

Herramienta de desarrollo, no parte de la aplicacion. No carga ningun modelo y no
usa la red: corre el mismo ``split_by_article`` de produccion sobre texto ya en
disco y clasifica cada trozo que devuelve.

Existe por lo que midio la validacion del 2026-07-31: en una ley modificatoria el
mecanismo cito como "articulos clave" cadenas que en realidad eran referencias
cruzadas a otra ley y a la Constitucion. La causa esta aguas arriba del reranker.
``_STRUCTURE_RE`` ancla a inicio de linea con ``re.MULTILINE`` y el texto de BCN
viene con saltos duros cada ~55 caracteres, de modo que una referencia cruzada que
cae al principio de una linea envuelta entra como si abriera un articulo.

Clasifica cada trozo en:

- ``propio``:   abre de verdad un articulo de la norma (``Articulo 17.-``).
- ``espurio``:  es una referencia cruzada partida por el ajuste de linea.
- ``dudoso``:   no cae limpio en ninguno de los dos; se imprime para revisar a mano.

El criterio decisivo es si el trozo empieza una oracion nueva, no la mayuscula:
una referencia envuelta conserva su minuscula pero tambien puede aparecer tras un
punto. Se combina con la marca ``.-`` que la tecnica legislativa chilena pone
despues del numero del articulo.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from leyllana.engine.chunking import split_by_article

# "Articulo 17.-", "Articulo 7o.-", "Articulo 16 bis.-", "Art. 5.-"
_PROPIO_RE = re.compile(
    r"^(?:art[ií]culo|art\.)\s+"
    r"(?:\d+|primero|segundo|tercero|cuarto|quinto|sexto|s[eé]ptimo|octavo|noveno|d[eé]cimo)"
    r"\s*[º°]?\s*"
    r"(?:bis|ter|qu[áa]ter|quinquies|sexies|septies|octies|nonies|decies)?\s*"
    r"[.\-]",
    re.IGNORECASE,
)

# Marcadores estructurales que no son articulos: Titulo, Capitulo, Parrafo.
_ESTRUCTURA_RE = re.compile(r"^(?:t[ií]tulo|cap[ií]tulo|p[áa]rrafo)\b", re.IGNORECASE)

# Senales de referencia cruzada: sigue una coma/preposicion en vez de abrir texto.
_CRUZADA_RE = re.compile(
    r"^art[ií]culo\s+\d+\s*[º°]?\s*"
    r"(?:,|\s+(?:de|del|y|o|N[º°]|inciso|letra|numeral|ambos|precedente|anterior))",
    re.IGNORECASE,
)


def clasificar(chunk_label: str, texto_previo: str) -> str:
    """Clasifica un trozo por su etiqueta y por lo que lo precede en el documento.

    La senal decisiva es la mayuscula mas la marca ``.-``: BCN abre cada articulo
    con ``Articulo N.-`` en mayuscula, y una referencia cruzada partida por el
    ajuste de linea conserva la minuscula con que venia en medio de la oracion
    (``...que el\narticulo 19, N 4, de la Constitucion...``).

    La primera version de esta funcion decidia por la puntuacion de lo anterior y
    se equivocaba: el articulo 1 viene despues del epigrafe ``Disposiciones
    generales``, que no termina en punto, y quedaba marcado como espurio. La
    puntuacion queda como desempate, no como criterio principal.
    """
    etiqueta = chunk_label.strip()

    if _ESTRUCTURA_RE.match(etiqueta):
        return "estructura"

    empieza_mayuscula = etiqueta[:1].isupper()

    if _PROPIO_RE.match(etiqueta) and empieza_mayuscula:
        return "propio"
    if _CRUZADA_RE.match(etiqueta) or not empieza_mayuscula:
        return "espurio"

    # Forma de articulo, mayuscula, pero sin la marca ``.-``: desempata la
    # puntuacion de lo que viene antes.
    previo = texto_previo.rstrip()
    if (not previo) or previo[-1] in ".:;":
        return "propio"
    return "dudoso"


def auditar(texto: str) -> tuple[dict[str, int], list[tuple[str, str]]]:
    chunks = split_by_article(texto)
    cuenta = {"propio": 0, "espurio": 0, "estructura": 0, "dudoso": 0}
    ejemplos: list[tuple[str, str]] = []
    cursor = 0
    for c in chunks:
        inicio = texto.find(c.text, cursor)
        if inicio < 0:
            inicio = cursor
        previo = texto[max(0, inicio - 120) : inicio]
        cursor = inicio + len(c.text)
        clase = clasificar(c.label, previo)
        cuenta[clase] += 1
        if clase in ("espurio", "dudoso"):
            ejemplos.append((clase, c.label[:90]))
    return cuenta, ejemplos


def main() -> int:
    p = argparse.ArgumentParser(
        prog="audit_segmentation",
        description="Clasifica los trozos de split_by_article sobre uno o mas documentos.",
    )
    p.add_argument("docs", nargs="+", help="archivos de texto ya extraidos")
    p.add_argument(
        "--ejemplos", type=int, default=6, help="cuantos casos dudosos imprimir"
    )
    args = p.parse_args()

    total = {"propio": 0, "espurio": 0, "estructura": 0, "dudoso": 0}
    for ruta in args.docs:
        texto = Path(ruta).read_text(encoding="utf-8")
        cuenta, ejemplos = auditar(texto)
        for k, v in cuenta.items():
            total[k] += v
        trozos = sum(cuenta.values())
        arts = cuenta["propio"] + cuenta["espurio"]
        ruido = (cuenta["espurio"] / arts * 100) if arts else 0.0
        print(
            f"{Path(ruta).name:18} trozos={trozos:4}  propio={cuenta['propio']:4}  "
            f"espurio={cuenta['espurio']:4}  estructura={cuenta['estructura']:3}  "
            f"dudoso={cuenta['dudoso']:3}  ruido={ruido:5.1f}%"
        )
        for clase, ej in ejemplos[: args.ejemplos]:
            print(f"    [{clase}] {ej}")

    arts = total["propio"] + total["espurio"]
    ruido = (total["espurio"] / arts * 100) if arts else 0.0
    print(f"\nTOTAL propio={total['propio']} espurio={total['espurio']} ruido={ruido:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
