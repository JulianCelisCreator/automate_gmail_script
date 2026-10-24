"""Configuración de ejemplo. Cópiala a config_personal.py y ajústala a tu correo:

    cp config_ejemplo.py config_personal.py

config_personal.py está en .gitignore: ahí van tus empresas y dominios reales.
"""

# Empresas a las que aplicaste. Cada una tendrá su carpeta Trabajos/<Empresa>.
#   - "claves": textos que la identifican en remitente + asunto (para el análisis local)
#   - "gmail": búsqueda de Gmail con la que se crea el filtro automático (opcional)
EMPRESAS = {
    "Empresa Ejemplo": {
        "claves": ["empresaejemplo", "talento@empresa-ejemplo.com"],
        "gmail": "from:empresa-ejemplo.com",
    },
    # Plataformas de pruebas (CodeSignal, HackerRank...) envían a nombre de otras empresas:
    # combina remitente y asunto para no mezclar procesos.
    "Otra Empresa": {
        "claves": ["otra empresa"],
        "gmail": "from:(codesignal.com OR hackerrank.com) subject:(\"Otra Empresa\")",
    },
}

# Portales y convocatorias masivas: se etiquetan como Trabajos/Alertas y se archivan
ALERTAS_GMAIL = ("from:(jobs-noreply@linkedin.com) "
                 "-subject:(\"tu solicitud\" OR \"your application\")")

# Dominios institucionales: lo personal es importante, lo masivo va a "universidad"
DOMINIOS_UNIVERSIDAD = ["universidad-ejemplo.edu.co"]

# Remitentes que siempre son importantes aunque sean masivos
REMITENTES_IMPORTANTES = []
