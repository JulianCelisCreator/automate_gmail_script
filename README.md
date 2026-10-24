# Organizador de correo (Gmail)

Scripts en Python que analizan tu Gmail y lo organizan, pensados para una búsqueda de empleo:

- **Clasifica** los correos: procesos de empleo, requieren atención, oportunidades, universidad,
  informativos, notificaciones y spam.
- **Genera un resumen** (`resumen.html`) con tus procesos por empresa, lo pendiente y los
  remitentes que más escriben, con una sugerencia para cada uno (desuscribir, filtrar o mantener).
- **Crea la carpeta `Trabajos` en Gmail** con una subcarpeta por empresa (`Trabajos/<Empresa>`)
  y `Trabajos/Alertas` para portales de empleo, más **filtros de Gmail** que clasifican solos
  los correos nuevos.
- **Se ejecuta a diario** con cron y avisa con una notificación de escritorio si algo requiere
  tu intervención.

Todo corre en tu computador y no usa IA ni servicios externos aparte de la API de Gmail, que
es gratuita. Los correos y tokens nunca salen de tu máquina.

## Requisitos

- Python 3.10 o superior
- Linux con `cron` y `notify-send` (las notificaciones son opcionales)
- Una cuenta de Gmail

## Instalación

```bash
python3 -m venv .venv
.venv/bin/pip install google-api-python-client google-auth-oauthlib
cp config_ejemplo.py config_personal.py   # luego edítalo con tus empresas
```

### Credenciales de Google (una sola vez, unos 5 minutos)

1. Entra a <https://console.cloud.google.com/> y crea un proyecto.
2. **APIs y servicios → Biblioteca**: busca **Gmail API** y haz clic en *Habilitar*.
   No confundir con "Gmail MCP API".
3. **Google Auth Platform → Branding**: nombre de la app y tu correo como contacto.
   Deja el logo vacío, porque subirlo obliga a verificar la app.
4. **Google Auth Platform → Audience**: tipo **External**, estado **Testing**. En
   **Test users** agrega tu propio correo. Sin esto, Google responde "Access blocked: 403".
5. **Google Auth Platform → Clients → Create client**: tipo **Desktop app**. Descarga el JSON
   y guárdalo en esta carpeta como `credentials.json`.

La primera vez que ejecutes un script se abrirá el navegador para autorizar. Google mostrará
"Google no verificó esta app": es normal, porque la app es tuya. Entra en *Configuración
avanzada → Ir a … (no seguro)* y da *Permitir*.

Permisos que se piden: `gmail.modify` (leer y etiquetar o archivar; **nunca borra ni envía**)
y `gmail.settings.basic` (crear filtros). Puedes revocarlos en
<https://myaccount.google.com/permissions>.

## Uso

```bash
.venv/bin/python extraer.py --dias 90     # descarga metadatos de los últimos 90 días a datos/
.venv/bin/python analizar.py              # clasifica y genera resumen.html, reporte.html y remitentes.csv
.venv/bin/python etiquetar.py             # simulación: muestra qué etiquetaría
.venv/bin/python etiquetar.py --aplicar   # crea las etiquetas Trabajos/... y los filtros en Gmail
```

- **`resumen.html`**: vista general para abrir en el navegador.
- **`reporte.html`**: detalle de todos los pendientes y remitentes.
- **`remitentes.csv`**: un remitente masivo por fila, con su enlace de desuscripción y una
  columna `decision` para que anotes qué hacer.

`extraer.py` solo descarga **metadatos** (remitente, asunto, etiquetas, cabeceras de
desuscripción y un fragmento corto), no el cuerpo de los correos. Además reanuda: no vuelve a
descargar lo que ya tiene.

## Configuración

### Empresas y alertas (`config_personal.py`)

Este archivo no se sube al repositorio. Usa `config_ejemplo.py` como plantilla.

```python
EMPRESAS = {
    "Empresa X": {
        "claves": ["empresax", "talento@empresax.com"],  # se buscan en remitente + asunto
        "gmail": "from:empresax.com",                    # búsqueda para el filtro de Gmail
    },
}
ALERTAS_GMAIL = "from:(jobs-noreply@linkedin.com)"       # van a Trabajos/Alertas y se archivan
DOMINIOS_UNIVERSIDAD = ["miuniversidad.edu.co"]
```

- Los procesos de empleo de **empresas que no estén en la lista** van a
  `Trabajos/Otras empresas`, y `etiquetar.py` te avisa para que las agregues.
- Las plataformas de pruebas (CodeSignal, Ashby…) escriben en nombre de otras empresas, así
  que conviene combinar remitente y asunto en la búsqueda: `from:codesignal.com subject:EmpresaX`.
- Los procesos con empresa **se quedan en la bandeja de entrada**. Las alertas se archivan.

### Reglas de clasificación (`analizar.py`)

Al inicio del archivo están las listas de palabras clave (empleo, urgencia, códigos
temporales, seguridad) y los umbrales. Cada correo del reporte muestra *por qué* se clasificó
así, lo que ayuda a ajustar las reglas.

## Ejecución automática (cron)

`ejecutar_diario.sh` corre `extraer → analizar → etiquetar --aplicar` y guarda el registro en
`logs/AAAA-MM.log`. Para programarlo todos los días a las 8 p. m.:

```bash
chmod +x ejecutar_diario.sh reautorizar.sh
(crontab -l 2>/dev/null; echo "0 20 * * * $(pwd)/ejecutar_diario.sh") | crontab -
crontab -l    # verificar
```

Muestra una notificación de escritorio cuando:

- la ejecución falla;
- aparece un proceso de una empresa que no está en `config_personal.py`;
- vence la autorización de Google (ver abajo).

Solo corre si el computador está encendido a esa hora. **Los filtros de Gmail funcionan
siempre**, aunque el computador esté apagado o la autorización haya vencido.

## Renovar la autorización cada semana

Mientras la app de Google esté en modo **Testing**, Google vence la autorización **cada 7
días**. Pasarla a producción exige publicar una página de inicio y una política de privacidad,
lo que para uso personal no vale la pena.

Cuando llegue la notificación *"La autorización de Google venció"*:

```bash
./reautorizar.sh
```

Se abre el navegador, das **Permitir** y el organizador corre de inmediato. Tarda menos de un
minuto.

## Estructura

| Archivo | Qué hace |
| --- | --- |
| `extraer.py` | Autenticación con Google y descarga de metadatos (solo lectura) |
| `analizar.py` | Reglas de clasificación, `reporte.html` y `remitentes.csv` |
| `resumen.py` | Genera `resumen.html` |
| `trabajos.py` | Etiquetas de la carpeta Trabajos y detección de empresa |
| `etiquetar.py` | Crea etiquetas y filtros en Gmail (simulación por defecto) |
| `config_ejemplo.py` | Plantilla de `config_personal.py` |
| `ejecutar_diario.sh` | Ejecución para cron, con registro y notificaciones |
| `reautorizar.sh` | Renueva la autorización de Google |

## Privacidad

`.gitignore` excluye todo lo sensible: `credentials.json`, `token.json`, `config_personal.py`,
`datos/`, `logs/` y los reportes generados (`resumen.html`, `reporte.html`,
`remitentes.csv`). Antes de cada commit, revisa con `git status` que no aparezca ninguno.
