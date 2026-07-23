"""Tests de identificacion de la fuente (FR-7.1, ADR 0008).

Mapeadores puros: reciben artefactos ya obtenidos (XML de leychile, metadatos de
un PDF) y devuelven ``SourceInfo``. Nunca inventan: un campo ausente queda en
``None``. Sin red ni modelo.
"""

from leyllana.input import source
from leyllana.types import SourceInfo

_BCN_XML = (
    b'<Norma xmlns="http://www.leychile.cl/esquemas" normaId="210676" '
    b'fechaVersion="2026-02-05">'
    b'<Identificador fechaPromulgacion="2003-05-22" fechaPublicacion="2003-05-29">'
    b"<TiposNumeros><TipoNumero><Tipo>Ley</Tipo><Numero>19880</Numero>"
    b"</TipoNumero></TiposNumeros>"
    b"<Organismos><Organismo>MINISTERIO SECRETARIA GENERAL DE LA PRESIDENCIA"
    b"</Organismo></Organismos></Identificador>"
    b"<Metadatos><TituloNorma>ESTABLECE BASES DE LOS PROCEDIMIENTOS ADMINISTRATIVOS"
    b"</TituloNorma></Metadatos>"
    b"<Texto>Articulo 1.</Texto></Norma>"
)


def test_from_bcn_xml_maps_real_fields():
    url = "https://www.bcn.cl/leychile/navegar?idNorma=210676"
    info = source.from_bcn_xml(_BCN_XML, url)
    assert info.titulo == "ESTABLECE BASES DE LOS PROCEDIMIENTOS ADMINISTRATIVOS"
    assert info.tipo_norma == "Ley 19880"
    assert info.organo_emisor == "MINISTERIO SECRETARIA GENERAL DE LA PRESIDENCIA"
    assert info.fecha == "2003-05-29"
    assert info.version == "2026-02-05"
    assert info.url == url
    assert info.fecha_consulta  # se fija a hoy


def test_from_bcn_xml_missing_fields_stay_none():
    minimal = b'<Norma xmlns="http://www.leychile.cl/esquemas"><Texto>x</Texto></Norma>'
    info = source.from_bcn_xml(minimal, "https://x")
    assert info.titulo is None
    assert info.tipo_norma is None
    assert info.organo_emisor is None
    assert info.url == "https://x"


def test_from_pdf_metadata_maps_title_and_date():
    meta = {"title": "Mi Norma", "creationDate": "D:20030529120000+00'00'"}
    info = source.from_pdf_metadata(meta)
    assert info.titulo == "Mi Norma"
    assert info.fecha == "2003-05-29"
    assert info.fecha_consulta


def test_from_pdf_metadata_empty_when_no_real_data():
    assert source.from_pdf_metadata({"title": "", "creationDate": ""}).is_empty()
    assert source.from_pdf_metadata({}).is_empty()


def test_from_pdf_metadata_never_invents():
    # solo titulo, sin fecha parseable -> fecha None, no inventada
    info = source.from_pdf_metadata({"title": "Solo Titulo", "creationDate": "basura"})
    assert info.titulo == "Solo Titulo"
    assert info.fecha is None
    assert isinstance(info, SourceInfo)
