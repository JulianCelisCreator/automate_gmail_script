#!/bin/bash
# Ejecución automática (cron): descarga, analiza y etiqueta el correo.
# Log mensual en logs/AAAA-MM.log; si algo falla, muestra una notificación de escritorio.
cd "$(dirname "$0")" || exit 1
mkdir -p logs
LOG="logs/$(date +%Y-%m).log"
export ORGANIZADOR_NO_INTERACTIVO=1

{
  echo "=== $(date '+%F %T') ==="
  .venv/bin/python extraer.py && .venv/bin/python analizar.py && .venv/bin/python etiquetar.py --aplicar
} >> "$LOG" 2>&1
estado=$?
echo "Código de salida: $estado" >> "$LOG"

notificar() {
  # cron no tiene la sesión gráfica: apuntar al bus de escritorio del usuario
  DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u)/bus" \
    notify-send "Organizador de correo" "$1" 2>/dev/null
}
if tail -n 5 "$LOG" | grep -q "autorización de Google venció"; then
  notificar "La autorización de Google venció. Ejecuta: $(pwd)/reautorizar.sh"
elif [ $estado -ne 0 ]; then
  notificar "Falló la ejecución automática. Revisa $(pwd)/$LOG"
elif tail -n 40 "$LOG" | grep -q "Procesos sin empresa reconocida"; then
  notificar "Hay procesos de empresas nuevas en Trabajos/Otras empresas"
fi
exit $estado
