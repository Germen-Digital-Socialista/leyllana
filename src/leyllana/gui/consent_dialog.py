"""Aviso de consentimiento antes de que un documento salga del equipo (ADR 0013).

Aparece en **cada** corrida que use un proveedor de nube, no una vez por sesion y
no una vez al configurarlo. Esa es la decision de ADR 0013 tal cual: elegir un
proveedor en Ajustes no es consentir un envio, porque un ajuste olvidado no puede
terminar mandando solo un documento afuera.

Por eso tampoco hay casilla de "no volver a preguntar": seria exactamente la
puerta que ADR 0013 cierra.
"""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget


def pedir_consentimiento(parent: QWidget | None, destino: str) -> bool:
    """Pregunta si se puede enviar el documento a ``destino``. True si acepta.

    El boton por defecto es No: si alguien presiona Enter sin leer, no sale nada.
    """
    caja = QMessageBox(parent)
    caja.setIcon(QMessageBox.Icon.Warning)
    caja.setWindowTitle("El documento saldra de su equipo")
    caja.setText(f"Esta explicacion se generara enviando el documento a {destino}.")
    caja.setInformativeText(
        "El texto completo de la norma saldra de este equipo hacia ese servicio. "
        "Por defecto leyllana no envia nada a ninguna parte.\n\n"
        "Se le preguntara de nuevo en cada explicacion."
    )
    caja.setStandardButtons(
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    caja.button(QMessageBox.StandardButton.Yes).setText("Enviar")
    caja.button(QMessageBox.StandardButton.No).setText("No enviar")
    caja.setDefaultButton(QMessageBox.StandardButton.No)
    return caja.exec() == QMessageBox.StandardButton.Yes


__all__ = ["pedir_consentimiento"]
