#!/bin/bash
# Renueva la autorización de Google (vence cada 7 días mientras la app esté en modo Testing).
# Abre el navegador: elige tu cuenta y da "Permitir". Luego ejecuta el organizador completo.
cd "$(dirname "$0")" || exit 1
rm -f token.json
.venv/bin/python -c "import extraer; extraer.autenticar()" || exit 1
./ejecutar_diario.sh &&
  echo "Listo: autorización renovada y correo organizado." ||
  echo "Algo falló; revisa logs/$(date +%Y-%m).log"
