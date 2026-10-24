"""Página de resumen (resumen.html): lo esencial del análisis en una sola vista."""
import html
from collections import defaultdict
from datetime import datetime
from email.utils import parseaddr

import trabajos

COLORES = {"empleo": "var(--c1)", "atencion": "var(--c2)", "oportunidad": "var(--c3)",
           "universidad": "var(--c4)", "informativo": "var(--c5)",
           "notificacion": "var(--c6)", "spam": "var(--c6)"}
SUGERENCIAS = {"desuscribir": "Desuscribir", "filtrar": "Filtrar", "mantener": "Mantener",
               "revisar": "Revisar"}

e = html.escape


def empresa_de(c):
    return trabajos.empresa_de(c) or parseaddr(c["de"])[1].split("@")[-1]


def enlace_gmail(c, texto):
    return (f"<a href='https://mail.google.com/mail/u/0/#all/{c['hilo']}' "
            f"target='_blank' rel='noreferrer'>{e(texto)}</a>")


def fecha_corta(ts):
    return datetime.fromtimestamp(ts).strftime("%d %b")


def tarjetas_empleo(recibidos):
    procesos = defaultdict(list)
    for c in recibidos:
        if c["categoria"] == "empleo":
            procesos[empresa_de(c)].append(c)
    orden = sorted(procesos.items(), key=lambda kv: -max(c["fecha"] for c in kv[1]))
    tarjetas = []
    for empresa, cs in orden:
        cs.sort(key=lambda c: -c["fecha"])
        ultimo = cs[0]
        sin_leer = sum("UNREAD" in c["etiquetas"] for c in cs)
        tarjetas.append(f"""<article class="proc">
  <header><h3>{e(empresa)}</h3><span class="mut">{fecha_corta(ultimo['fecha'])}</span></header>
  <p>{enlace_gmail(ultimo, ultimo['asunto'] or '(sin asunto)')}</p>
  <footer class="mut">{len(cs)} correo{'s' if len(cs) != 1 else ''}
  {f"· <b class='nuevo'>{sin_leer} sin leer</b>" if sin_leer else ''}</footer>
</article>""")
    return "\n".join(tarjetas)


def lista_atencion(pendientes):
    filas = [f"<li><span class='mut'>{fecha_corta(c['fecha'])}</span> "
             f"<b>{e(parseaddr(c['de'])[0] or parseaddr(c['de'])[1])}</b> — "
             f"{enlace_gmail(c, c['asunto'] or '(sin asunto)')}"
             f"<div class='mut peq'>{e(c['razon'])}</div></li>"
             for c in pendientes if c["categoria"] == "atencion"]
    return "\n".join(filas) or "<li class='mut'>Nada pendiente.</li>"


def barra_distribucion(conteo, total, categorias):
    segmentos, leyenda = [], []
    for k, nombre in categorias.items():
        n = conteo.get(k, 0)
        if not n:
            continue
        pct = 100 * n / total
        segmentos.append(f"<span style='width:{pct:.2f}%;background:{COLORES[k]}' "
                         f"title='{e(nombre)}: {n}'></span>")
        leyenda.append(f"<li><i style='background:{COLORES[k]}'></i>{e(nombre)} "
                       f"<b>{n}</b> <span class='mut'>({pct:.0f}%)</span></li>")
    return f"<div class='dist'>{''.join(segmentos)}</div><ul class='leyenda'>{''.join(leyenda)}</ul>"


def tabla_remitentes(remitentes, limite=20):
    filas = []
    for r in remitentes[:limite]:
        baja = r["baja_web"] or ""
        accion = (f"<a href='{e(baja)}' target='_blank' rel='noreferrer'>darse de baja</a>"
                  if baja and r["sugerencia"] == "desuscribir" else "")
        filas.append(f"""<tr>
  <td><b>{e(r['remitente'])}</b><div class="mut peq">{e(r['email'])}</div></td>
  <td class="n">{r['por_mes']}</td>
  <td><div class="leido"><span style="width:{r['leidos_pct']}%"></span></div>
      <span class="mut peq">{r['leidos_pct']}%</span></td>
  <td><span class="sug {r['sugerencia']}">{SUGERENCIAS[r['sugerencia']]}</span></td>
  <td class="peq">{accion}</td>
</tr>""")
    return "\n".join(filas)


def generar(meta, recibidos, pendientes, remitentes, categorias):
    total = len(recibidos)
    conteo = defaultdict(int)
    for c in recibidos:
        conteo[c["categoria"]] += 1
    n_empleo = sum(c["categoria"] == "empleo" for c in pendientes)
    n_atencion = sum(c["categoria"] == "atencion" for c in pendientes)
    pct_ruido = round(100 * (conteo["notificacion"] + conteo["oportunidad"]) / max(total, 1))
    a_desuscribir = [r for r in remitentes if r["sugerencia"] == "desuscribir"]
    ahorro = round(sum(r["por_mes"] for r in a_desuscribir))

    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Resumen de correo</title>
<style>
:root{{--bg:#f7f6f3;--card:#fff;--fg:#1f1d1a;--mut:#77716a;--line:#e6e2dc;--acc:#a24a12;
  --c1:#c2571a;--c2:#b8323a;--c3:#d39a2c;--c4:#3d7a8a;--c5:#8a8f98;--c6:#cfcac2;
  --ok:#2f7d4f;--warn:#b26a00;--bad:#b8323a}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#171614;--card:#211f1c;
  --fg:#f1eee9;--mut:#a39d95;--line:#37332e;--acc:#f0a060;--c1:#e07a3a;--c2:#e0626a;
  --c3:#e8b850;--c4:#6fb0c0;--c5:#8e939b;--c6:#4a4640;--ok:#5fbf86;--warn:#e8a840;--bad:#e0626a}}}}
:root[data-theme="dark"]{{--bg:#171614;--card:#211f1c;--fg:#f1eee9;--mut:#a39d95;--line:#37332e;
  --acc:#f0a060;--c1:#e07a3a;--c2:#e0626a;--c3:#e8b850;--c4:#6fb0c0;--c5:#8e939b;--c6:#4a4640;
  --ok:#5fbf86;--warn:#e8a840;--bad:#e0626a}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:1080px;margin:0 auto;padding:32px 16px 64px}}
h1{{font-size:28px;margin:0}} h2{{font-size:18px;margin:40px 0 4px}} h3{{font-size:15px;margin:0}}
.mut{{color:var(--mut)}} .peq{{font-size:12.5px}} a{{color:var(--acc)}}
.sub{{margin:4px 0 0}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-top:24px}}
.kpi,.proc,.panel{{background:var(--card);border:1px solid var(--line);border-radius:12px}}
.kpi{{padding:14px 16px}} .kpi b{{display:block;font-size:30px;line-height:1.1;font-variant-numeric:tabular-nums}}
.kpi.dest b{{color:var(--acc)}}
.dist{{display:flex;height:14px;border-radius:7px;overflow:hidden;margin:14px 0 10px;background:var(--line)}}
.dist span{{display:block;height:100%}}
.leyenda{{list-style:none;padding:0;margin:0;display:flex;flex-wrap:wrap;gap:6px 18px;font-size:13.5px}}
.leyenda i{{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px}}
.procs{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px;margin-top:12px}}
.proc{{padding:14px 16px;display:flex;flex-direction:column;gap:6px;border-top:3px solid var(--c1)}}
.proc header{{display:flex;justify-content:space-between;gap:8px;align-items:baseline}}
.proc p{{margin:0;font-size:13.5px}} .proc footer{{font-size:12.5px;margin-top:auto}}
.nuevo{{color:var(--acc)}}
.panel{{padding:4px 16px;margin-top:12px}}
.panel ul{{list-style:none;padding:0;margin:0}} .panel li{{padding:10px 0;border-bottom:1px solid var(--line)}}
.panel li:last-child{{border:0}}
.tabla{{overflow-x:auto;margin-top:12px;background:var(--card);border:1px solid var(--line);border-radius:12px}}
table{{border-collapse:collapse;width:100%;min-width:560px}}
th,td{{padding:9px 12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:middle}}
tr:last-child td{{border:0}}
th{{font-size:12px;font-weight:600;color:var(--mut);text-transform:uppercase;letter-spacing:.03em}}
td.n,th.n{{text-align:right;font-variant-numeric:tabular-nums}}
.leido{{display:inline-block;width:70px;height:6px;border-radius:3px;background:var(--line);
  vertical-align:middle;margin-right:6px;overflow:hidden}}
.leido span{{display:block;height:100%;background:var(--mut)}}
.sug{{font-size:12px;font-weight:600;padding:2px 9px;border-radius:999px;border:1px solid currentColor;white-space:nowrap}}
.sug.desuscribir{{color:var(--bad)}} .sug.filtrar{{color:var(--warn)}} .sug.mantener{{color:var(--ok)}}
.sug.revisar{{color:var(--mut)}}
.pie{{margin-top:40px;font-size:13px}}
</style></head><body><main>

<h1>Resumen de tu correo</h1>
<p class="mut sub">{e(meta['cuenta'])} · últimos {meta['dias']} días ·
actualizado {datetime.now():%d/%m/%Y %H:%M}</p>

<section class="kpis">
  <div class="kpi"><b>{total}</b><span class="mut">correos recibidos</span></div>
  <div class="kpi dest"><b>{n_empleo}</b><span class="mut">correos de procesos de empleo</span></div>
  <div class="kpi"><b>{n_atencion}</b><span class="mut">otros que requieren atención</span></div>
  <div class="kpi"><b>{pct_ruido}%</b><span class="mut">es notificación o alerta</span></div>
  <div class="kpi"><b>−{ahorro}</b><span class="mut">correos/mes si te desuscribes de lo sugerido</span></div>
</section>

<h2>¿Qué llega a tu bandeja?</h2>
{barra_distribucion(conteo, total, categorias)}

<h2>Tus procesos de empleo</h2>
<p class="mut">Agrupados por empresa, el más reciente primero. El enlace abre el último correo en Gmail.</p>
<div class="procs">{tarjetas_empleo(recibidos)}</div>

<h2>Otros pendientes</h2>
<div class="panel"><ul>{lista_atencion(pendientes)}</ul></div>

<h2>Remitentes que más escriben</h2>
<p class="mut">Los 20 con más volumen y lo que sugiero hacer con cada uno.
{len(a_desuscribir)} remitentes en total son candidatos a desuscribir.</p>
<div class="tabla"><table>
<tr><th>Remitente</th><th class="n">Por mes</th><th>Los abres</th><th>Sugerencia</th><th></th></tr>
{tabla_remitentes(remitentes)}
</table></div>

<p class="pie mut">Detalle completo en <a href="reporte.html">reporte.html</a>;
lista de todos los remitentes en <code>remitentes.csv</code>.</p>
</main></body></html>"""
