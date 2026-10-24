"""Fases 3-4: clasifica los correos descargados y genera los reportes.

Uso: .venv/bin/python analizar.py
Salida: reporte.html (para leer) y remitentes.csv (para marcar decisiones).
"""
import csv
import html
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from email.utils import getaddresses, parseaddr
from pathlib import Path

import resumen
import trabajos

BASE = Path(__file__).parent
DATOS = BASE / "datos"

# --- Reglas: ajústalas según lo que veas en el reporte ---
# Procesos de selección (se buscan en el asunto)
PALABRAS_EMPLEO = [
    "práctica", "practicante", "pasantía", "postulación", "postulaste", "candidat",
    "proceso de selección", "convocatoria", "assessment", "online test", "prueba técnica",
    "prueba en línea", "entrevista", "interview", "your application", "tu aplicación",
    "application to", "oferta laboral", "job offer", "vacante", "early talent", "internship",
]
# Remitentes típicos de reclutamiento
PATRON_EMPLEO = re.compile(r"recruit|talent|codesignal|hackerrank|careers|interns|seleccion", re.I)
# Alertas genéricas de portales de empleo: son notificaciones, no procesos
ALERTAS_EMPLEO = ["nuevos empleos", "new jobs", "empleos similares", "jobs you may",
                  "vacante no va a esperar", "solicita ya", "solicita el puesto", "busca personal"]
# Mensajes temporales que pierden vigencia en minutos
PALABRAS_TEMPORALES = [
    "código de verificación", "verification code", "verify your", "verifica tu",
    "please verify", "reset password", "restablec", "password was reset", "reset your password",
    "inicio de sesión en", "account verification", "actualizar contraseña", "cambia la contraseña",
]
PALABRAS_SEGURIDAD = ["security alert", "alerta de seguridad", "nuevo dispositivo",
                      "new sign-in", "oauth application has been added"]
DIAS_SEGURIDAD = 7  # una alerta de seguridad más vieja que esto ya no es pendiente
PALABRAS_URGENTES = [
    "fecha límite", "deadline", "vence", "vencimiento", "urgente", "urgent",
    "acción requerida", "action required", "pago pendiente", "factura vencida",
    "citación", "reunión", "meeting", "invitación:", "invitation:",
]
# Datos personales (universidad, remitentes importantes): en config_personal.py
DOMINIOS_UNIVERSIDAD = trabajos.config.DOMINIOS_UNIVERSIDAD
REMITENTES_IMPORTANTES = trabajos.config.REMITENTES_IMPORTANTES
# Un dominio que envía al menos esto en el periodo se considera masivo
UMBRAL_DOMINIO_MASIVO = 5
DOMINIOS_PUBLICOS = {"gmail.com", "hotmail.com", "outlook.com", "yahoo.com", "live.com",
                     "icloud.com", "hotmail.es", "yahoo.es"}
PATRON_AUTOMATICO = re.compile(
    r"no-?reply|do-?not-?reply|no-?responder|notifica|newsletter|news@|mailer|marketing"
    r"|bounce|info@|hello@|boletin",
    re.I)


def cargar(nombre):
    ruta = DATOS / f"{nombre}.jsonl"
    with open(ruta) as f:
        return [json.loads(linea) for linea in f]


def dominio_base(email):
    """ae-daily@deals.aliexpress.com -> aliexpress.com; x@r.mercadolibre.com.co -> mercadolibre.com.co"""
    partes = email.split("@")[-1].split(".")
    n = 3 if len(partes) >= 3 and len(partes[-1]) == 2 and partes[-2] in (
        "com", "edu", "gov", "org", "net", "co") else 2
    return ".".join(partes[-n:])


def es_masivo(c, email, dominios_frecuentes=frozenset()):
    return bool(c["list_unsubscribe"] or c["list_id"]
                or c["precedence"].lower() in ("bulk", "list", "junk")
                or PATRON_AUTOMATICO.search(email)
                or dominio_base(email) in dominios_frecuentes)


def contiene(texto, palabras):
    return any(p in texto for p in palabras)


def clasificar(c, contactos, hilos_respondidos, dominios_frecuentes, ahora):
    """Devuelve (categoría, razón)."""
    email = parseaddr(c["de"])[1].lower()
    dominio = email.split("@")[-1]
    etq = set(c["etiquetas"])
    asunto = c["asunto"].lower()
    masivo = es_masivo(c, email, dominios_frecuentes)

    if "SPAM" in etq:
        return "spam", "marcado como spam por Gmail"
    if email in REMITENTES_IMPORTANTES:
        return "atencion", "remitente en lista de importantes"
    if contiene(asunto, PALABRAS_TEMPORALES):
        return "informativo", "código o verificación temporal"
    if contiene(asunto, PALABRAS_SEGURIDAD):
        if ahora - c["fecha"] < DIAS_SEGURIDAD * 86400:
            return "atencion", "alerta de seguridad reciente"
        return "informativo", "alerta de seguridad antigua"
    if contiene(asunto, ALERTAS_EMPLEO):
        return "oportunidad", "alerta de portal de empleo"
    if PATRON_EMPLEO.search(email):
        return "empleo", "remitente de reclutamiento"
    if contiene(asunto, PALABRAS_EMPLEO):
        # con lista de correo es una convocatoria/boletín; sin ella, un proceso tuyo
        if c["list_unsubscribe"] or c["list_id"]:
            return "oportunidad", "convocatoria o boletín de empleo"
        return "empleo", "proceso de selección"
    if email in contactos:
        return "atencion", "persona a la que le has escrito"
    if c["hilo"] in hilos_respondidos and not masivo:
        return "atencion", "conversación en la que participas"
    if any(dominio.endswith(d) for d in DOMINIOS_UNIVERSIDAD):
        if masivo or PATRON_AUTOMATICO.search(email):
            return "universidad", "comunicado institucional"
        return "atencion", f"persona de la universidad ({dominio})"
    if not masivo and contiene(asunto, PALABRAS_URGENTES):
        return "atencion", "persona + asunto urgente"
    if not masivo and "CATEGORY_PERSONAL" in etq:
        return "atencion", "correo personal (no masivo)"
    if masivo or etq & {"CATEGORY_SOCIAL", "CATEGORY_PROMOTIONS", "CATEGORY_FORUMS"}:
        return "notificacion", "envío masivo / promociones / redes"
    return "informativo", "automático sin lista de correo"


def enlaces_baja(c):
    enlaces = re.findall(r"<([^>]+)>", c["list_unsubscribe"])
    web = next((e for e in enlaces if e.startswith("http")), "")
    correo = next((e for e in enlaces if e.startswith("mailto:")), "")
    return web, correo


def sugerir(email, leidos_pct, categoria, tiene_baja):
    if leidos_pct >= 50:
        return "mantener"
    # avisos de cuenta/seguridad: no se puede (ni conviene) desuscribirse
    if categoria in ("oportunidad", "universidad") or re.search(r"accounts|security|seguridad", email):
        return "filtrar"  # útil pero no debe llenar la bandeja
    if leidos_pct <= 15 and tiene_baja:
        return "desuscribir"
    return "revisar"


def fecha(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


def clasificar_todo():
    """Carga los datos descargados y agrega 'categoria' y 'razon' a cada correo recibido."""
    meta = json.loads((DATOS / "meta.json").read_text())
    recibidos, enviados = cargar("recibidos"), cargar("enviados")
    yo = meta["cuenta"].lower()

    contactos = {e.lower() for c in enviados
                 for _, e in getaddresses([c["para"], c["cc"]]) if e} - {yo}
    hilos_respondidos = {c["hilo"] for c in enviados}
    por_dominio = Counter(dominio_base(parseaddr(c["de"])[1].lower()) for c in recibidos)
    dominios_frecuentes = {d for d, n in por_dominio.items()
                           if n >= UMBRAL_DOMINIO_MASIVO and d not in DOMINIOS_PUBLICOS}
    ahora = datetime.now().timestamp()

    for c in recibidos:
        c["categoria"], c["razon"] = clasificar(
            c, contactos, hilos_respondidos, dominios_frecuentes, ahora)
    return meta, recibidos, hilos_respondidos, dominios_frecuentes


def main():
    meta, recibidos, hilos_respondidos, dominios_frecuentes = clasificar_todo()

    # Pendientes: atención y empleo que no has respondido
    pendientes = sorted(
        (c for c in recibidos if c["categoria"] in ("atencion", "empleo")
         and c["hilo"] not in hilos_respondidos),
        key=lambda c: (c["categoria"] != "empleo", -c["fecha"]))

    # Ranking de remitentes masivos
    grupos = defaultdict(list)
    for c in recibidos:
        email = parseaddr(c["de"])[1].lower()
        if c["categoria"] in ("notificacion", "oportunidad", "universidad", "spam", "informativo") \
                or es_masivo(c, email, dominios_frecuentes):
            grupos[email].append(c)
    meses = max(meta["dias"] / 30, 1)
    remitentes = []
    for email, cs in grupos.items():
        if len(cs) < 2:
            continue
        web, correo = next((enlaces_baja(c) for c in sorted(cs, key=lambda c: -c["fecha"])
                            if c["list_unsubscribe"]), ("", ""))
        cat_gmail = Counter(e for c in cs for e in c["etiquetas"] if e.startswith("CATEGORY_"))
        leidos_pct = round(100 * sum("UNREAD" not in c["etiquetas"] for c in cs) / len(cs))
        categoria = Counter(c["categoria"] for c in cs).most_common(1)[0][0]
        remitentes.append({
            "remitente": parseaddr(cs[0]["de"])[0] or email,
            "email": email,
            "dominio": email.split("@")[-1],
            "total": len(cs),
            "por_mes": round(len(cs) / meses, 1),
            "leidos_pct": leidos_pct,
            "categoria": categoria,
            "sugerencia": sugerir(email, leidos_pct, categoria, web or correo),
            "ultimo": fecha(max(c["fecha"] for c in cs)),
            "categoria_gmail": (cat_gmail.most_common(1)[0][0].removeprefix("CATEGORY_").lower()
                                if cat_gmail else ""),
            "un_clic": "sí" if any(c["list_unsubscribe_post"] for c in cs) else "",
            "baja_web": web,
            "baja_correo": correo,
            "ejemplo_asunto": cs[0]["asunto"],
            "decision": "",
        })
    remitentes.sort(key=lambda r: -r["total"])

    with open(BASE / "remitentes.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(remitentes[0]) if remitentes else ["email"])
        w.writeheader()
        w.writerows(remitentes)

    conteo = Counter(c["categoria"] for c in recibidos)
    (BASE / "reporte.html").write_text(generar_html(meta, conteo, pendientes, remitentes))
    (BASE / "resumen.html").write_text(
        resumen.generar(meta, recibidos, pendientes, remitentes, CATEGORIAS))

    print(f"Correos analizados: {len(recibidos)}")
    for cat in CATEGORIAS:
        print(f"  {cat:13} {conteo.get(cat, 0)}")
    print(f"Pendientes (empleo + atención sin responder): {len(pendientes)}")
    print(f"Remitentes masivos frecuentes: {len(remitentes)}")
    print(f"Resumen: {BASE / 'resumen.html'}")
    print(f"Detalle: {BASE / 'reporte.html'}")


CATEGORIAS = {"empleo": "procesos de empleo", "atencion": "requieren atención",
              "oportunidad": "oportunidades", "universidad": "universidad",
              "informativo": "informativos", "notificacion": "notificaciones", "spam": "spam"}


def celda_baja(r):
    if r["baja_web"]:
        texto = f"<a href='{html.escape(r['baja_web'])}' target='_blank' rel='noreferrer'>enlace</a>"
    else:
        texto = "mailto" if r["baja_correo"] else "—"
    return texto + (" (1 clic)" if r["un_clic"] else "")


def generar_html(meta, conteo, pendientes, remitentes):
    e = html.escape
    filas_p = "\n".join(
        f"<tr><td>{fecha(c['fecha'])}</td><td>{e(c['de'])}</td>"
        f"<td><a href='https://mail.google.com/mail/u/0/#all/{c['hilo']}' target='_blank'>"
        f"{e(c['asunto'] or '(sin asunto)')}</a><div class='frag'>{e(c['fragmento'][:160])}</div></td>"
        f"<td>{'●' if 'UNREAD' in c['etiquetas'] else ''}</td>"
        f"<td><span class='tag {c['categoria']}'>{CATEGORIAS[c['categoria']]}</span>"
        f"<div class='razon'>{e(c['razon'])}</div></td></tr>"
        for c in pendientes)
    filas_r = "\n".join(
        f"<tr><td>{e(r['remitente'])}<div class='frag'>{e(r['email'])}</div></td>"
        f"<td class='n'>{r['total']}</td><td class='n'>{r['por_mes']}</td>"
        f"<td class='n'>{r['leidos_pct']}%</td><td>{r['ultimo']}</td><td>{e(r['categoria_gmail'])}</td>"
        f"<td>{celda_baja(r)}</td>"
        f"<td class='frag'>{e(r['ejemplo_asunto'][:80])}</td></tr>"
        for r in remitentes)
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Reporte de correo</title>
<style>
:root{{--bg:#fafaf9;--fg:#1c1917;--mut:#78716c;--line:#e7e5e4;--acc:#b45309;--card:#fff}}
@media (prefers-color-scheme:dark){{:root{{--bg:#1c1917;--fg:#f5f5f4;--mut:#a8a29e;--line:#44403c;--acc:#f59e0b;--card:#292524}}}}
body{{background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif;margin:0;padding:24px 16px}}
main{{max-width:1200px;margin:auto}} h1{{margin:0 0 4px}} .mut,.frag,.razon{{color:var(--mut)}}
.frag{{font-size:12px}} .razon{{font-size:12px}}
.kpis{{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0 28px}}
.kpi{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 16px}}
.kpi b{{display:block;font-size:22px}}
.tabla{{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:8px}}
table{{border-collapse:collapse;width:100%}} th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}}
th{{position:sticky;top:0;background:var(--card);font-size:12px;text-transform:uppercase;color:var(--mut)}}
td.n{{text-align:right;font-variant-numeric:tabular-nums}} a{{color:var(--acc)}}
.tag{{font-size:12px;padding:1px 8px;border-radius:999px;border:1px solid var(--line);white-space:nowrap}}
.tag.empleo{{border-color:var(--acc);color:var(--acc)}}
</style></head><body><main>
<h1>Reporte de correo</h1>
<div class="mut">{e(meta['cuenta'])} · últimos {meta['dias']} días · generado {datetime.now():%Y-%m-%d %H:%M}</div>
<div class="kpis">
{''.join(f"<div class='kpi'><b>{conteo.get(k, 0)}</b>{v}</div>" for k, v in CATEGORIAS.items())}</div>
<h2>Pendientes ({len(pendientes)})</h2>
<p class="mut">Empleo primero, luego lo que requiere atención; sin respuesta tuya. ● = no leído.</p>
<div class="tabla"><table><tr><th>Fecha</th><th>De</th><th>Asunto</th><th></th><th>Tipo</th></tr>
{filas_p}</table></div>
<h2>Remitentes masivos frecuentes ({len(remitentes)})</h2>
<p class="mut">Ordenados por volumen. Marca tu decisión (desuscribir / mantener / filtrar) en la columna <code>decision</code> de remitentes.csv.</p>
<div class="tabla"><table><tr><th>Remitente</th><th>Total</th><th>/mes</th><th>Leídos</th><th>Último</th><th>Pestaña Gmail</th><th>Baja</th><th>Ejemplo</th></tr>
{filas_r}</table></div>
</main></body></html>"""


if __name__ == "__main__":
    main()
