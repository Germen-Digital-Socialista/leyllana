"""Tests de la lectura en streaming del llama-server (ADR 0020).

Hermeticos: se sustituye ``urlopen`` por un objeto que devuelve tramas SSE ya
escritas, sin binario ni red. Lo que importa aqui es que una trama rota no tumbe
la corrida y que cancelar corte de verdad a media respuesta.
"""

import json

import pytest

from leyllana.engine.base import ProviderError
from leyllana.engine.progress import Cancelled, CancelToken
from leyllana.engine.server import chat_completion, sse_delta


def _trama(texto: str) -> bytes:
    payload = {"choices": [{"delta": {"content": texto}}]}
    return f"data: {json.dumps(payload)}\n".encode()


class _FakeResponse:
    """Respuesta iterable por lineas, como la de ``urlopen``."""

    def __init__(self, lineas, al_leer=None):
        self._lineas = list(lineas)
        self._al_leer = al_leer
        self.cerrada = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.cerrada = True
        return False

    def __iter__(self):
        for i, linea in enumerate(self._lineas, start=1):
            if self._al_leer is not None:
                self._al_leer(i)
            yield linea


def _use_response(monkeypatch, resp):
    monkeypatch.setattr(
        "leyllana.engine.server.urllib.request.urlopen",
        lambda req, timeout=None: resp,
    )


def _call(**kwargs):
    return chat_completion(
        "http://127.0.0.1:1", [{"role": "user", "content": "x"}],
        temperature=0.2, max_tokens=64, **kwargs,
    )


def test_sse_delta_extrae_el_contenido():
    assert sse_delta(_trama("hola")) == "hola"


@pytest.mark.parametrize(
    "linea",
    [
        b"\n",
        b": keepalive\n",
        b"data: [DONE]\n",
        b"data: {no es json}\n",
        b'data: {"choices": []}\n',
        b'data: {"choices": [{"delta": {}}]}\n',
        b'data: {"choices": [{"delta": {"content": ""}}]}\n',
    ],
)
def test_sse_delta_devuelve_none_en_lo_que_no_trae_texto(linea):
    assert sse_delta(linea) is None


def test_arma_el_texto_completo_desde_las_tramas(monkeypatch):
    _use_response(
        monkeypatch,
        _FakeResponse([_trama("Que hace: "), _trama("regula."), b"data: [DONE]\n"]),
    )
    assert _call() == "Que hace: regula."


def test_una_trama_rota_no_tumba_la_corrida(monkeypatch):
    # Se pierde un token, no la explicacion entera.
    _use_response(
        monkeypatch,
        _FakeResponse([_trama("uno "), b"data: {roto\n", _trama("dos")]),
    )
    assert _call() == "uno dos"


def test_on_token_recibe_cada_trozo(monkeypatch):
    _use_response(monkeypatch, _FakeResponse([_trama("a"), _trama("b")]))
    vistos = []
    assert _call(on_token=vistos.append) == "ab"
    assert vistos == ["a", "b"]


def test_cancelar_corta_a_media_respuesta(monkeypatch):
    token = CancelToken()
    # Cancela justo despues de leer la segunda linea de cinco.
    resp = _FakeResponse(
        [_trama(str(i)) for i in range(5)],
        al_leer=lambda i: token.cancel() if i == 2 else None,
    )
    _use_response(monkeypatch, resp)
    with pytest.raises(Cancelled):
        _call(cancel=token)
    # Salir del contexto cierra la conexion: el llama-server deja de generar.
    assert resp.cerrada


def test_respuesta_sin_texto_es_un_error_visible(monkeypatch):
    # Nunca devolver "" en silencio: aguas abajo el parseo diria "faltan
    # secciones" y el usuario no sabria que el modelo no dijo nada.
    _use_response(monkeypatch, _FakeResponse([b"data: [DONE]\n"]))
    with pytest.raises(ProviderError):
        _call()


def test_fallo_de_red_se_reporta_como_provider_error(monkeypatch):
    def _explota(req, timeout=None):
        raise OSError("conexion rechazada")

    monkeypatch.setattr(
        "leyllana.engine.server.urllib.request.urlopen", _explota
    )
    with pytest.raises(ProviderError):
        _call()
