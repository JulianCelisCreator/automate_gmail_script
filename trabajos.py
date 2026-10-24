"""Carpeta Trabajos: nombres de etiquetas y cómo reconocer a qué empresa pertenece un correo.

Las empresas y alertas se configuran en config_personal.py (ver config_ejemplo.py).
"""
from email.utils import parseaddr

try:
    import config_personal as config
except ImportError:
    print("Aviso: falta config_personal.py; usando config_ejemplo.py "
          "(cp config_ejemplo.py config_personal.py)")
    import config_ejemplo as config

CARPETA = "Trabajos"
ETIQUETA_ALERTAS = f"{CARPETA}/Alertas"
ETIQUETA_OTRAS = f"{CARPETA}/Otras empresas"

EMPRESAS = config.EMPRESAS
ALERTAS_GMAIL = config.ALERTAS_GMAIL


def empresa_de(c):
    """Nombre de la empresa en EMPRESAS, o None si no se reconoce."""
    texto = (parseaddr(c["de"])[1] + " " + c["asunto"]).lower()
    for nombre, conf in EMPRESAS.items():
        if any(k in texto for k in conf["claves"]):
            return nombre
    return None
