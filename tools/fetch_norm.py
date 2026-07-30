"""Baja una norma una sola vez y la deja en disco, para medir siempre lo mismo.

Herramienta de desarrollo, no parte de la aplicacion. Dos corridas que se comparan
tienen que haber visto exactamente los mismos bytes, asi que el fetch se hace aqui
y no dentro de cada medicion. Usa la misma capa de entrada que la app
(``resolve_with_source``), de modo que lo que se guarda es lo que la app habria
recibido, incluida la identificacion de la fuente.

Imprime tambien el tamano y los tokens estimados, que es lo que determina en
cuantos fragmentos caera el documento.

Ejemplo:

    uv run python tools/fetch_norm.py \
        "https://www.bcn.cl/leychile/navegar?idNorma=1202434" mediciones/ley.txt
"""

from __future__ import annotations

import argparse
from pathlib import Path

from leyllana.engine.chunking import estimate_tokens
from leyllana.input import resolve_with_source


def main() -> int:
    p = argparse.ArgumentParser(
        prog="fetch_norm",
        description="Resuelve una fuente a texto y la guarda para medir sobre ella.",
    )
    p.add_argument("fuente", help="URL, ruta de archivo, o paste:<texto>")
    p.add_argument("destino", help="archivo de texto a escribir")
    args = p.parse_args()

    texto, info = resolve_with_source(args.fuente)
    destino = Path(args.destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto, encoding="utf-8")

    print(f"fuente:     {args.fuente}")
    print(f"titulo:     {info.titulo}")
    print(f"tipo:       {info.tipo_norma}")
    print(f"organo:     {info.organo_emisor}")
    print(f"fecha:      {info.fecha}")
    print(f"consulta:   {info.fecha_consulta}")
    print(f"caracteres: {len(texto)}")
    print(f"tokens estimados: {estimate_tokens(texto)}")
    print(f"guardado en: {destino}")

    # Un fetch que devuelve poco texto casi nunca es una norma corta: suele ser una
    # pagina de error servida con HTTP 200. Conviene verlo aqui y no descubrirlo
    # despues en una explicacion que no cuadra.
    if len(texto) < 2000:
        print(
            "\nAVISO: el texto es sospechosamente corto para una norma. "
            "Revise que la URL sea la forma con idNorma= y no otra variante."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
