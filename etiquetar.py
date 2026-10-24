"""Fase 5: organiza los correos de empleo en la carpeta Trabajos de Gmail.

- Trabajos/<Empresa>: procesos de selección (se quedan también en la bandeja)
- Trabajos/Alertas: portales y convocatorias masivas (se archivan)
- Trabajos/Otras empresas: procesos detectados que no están en trabajos.EMPRESAS

Para cada empresa con búsqueda "gmail" crea además un filtro de Gmail, así los correos
nuevos se etiquetan solos. Usa datos/ (ejecuta antes extraer.py) para lo que no cubren los filtros.

Uso: .venv/bin/python etiquetar.py            (simulación: muestra qué haría)
     .venv/bin/python etiquetar.py --aplicar  (aplica los cambios en Gmail)
"""
import argparse
from collections import defaultdict

import analizar
import trabajos
from extraer import autenticar, ejecutar, listar

MAX_IDS = 1000  # límite de batchModify


class Plan:
    """Etiqueta -> ids a etiquetar, si se archiva y la búsqueda para el filtro."""

    def __init__(self):
        self.ids = defaultdict(set)
        self.archivar = set()
        self.filtros = {}

    def agregar(self, etiqueta, ids, archivar=False, filtro=None):
        self.ids[etiqueta] |= set(ids)
        if archivar:
            self.archivar.add(etiqueta)
        if filtro:
            self.filtros[etiqueta] = filtro


def armar_plan(gmail):
    plan = Plan()
    # 1. Búsquedas de Gmail: cubren todo el historial y sirven de filtro a futuro
    for empresa, conf in trabajos.EMPRESAS.items():
        if "gmail" in conf:
            print(f"Buscando {empresa}")
            ids = [m["id"] for m in listar(gmail, conf["gmail"])]
            plan.agregar(f"{trabajos.CARPETA}/{empresa}", ids, filtro=conf["gmail"])
    print("Buscando alertas")
    ids = [m["id"] for m in listar(gmail, trabajos.ALERTAS_GMAIL)]
    plan.agregar(trabajos.ETIQUETA_ALERTAS, ids, archivar=True, filtro=trabajos.ALERTAS_GMAIL)

    # 2. Clasificación local: lo que los filtros no alcanzan a cubrir
    _, recibidos, _, _ = analizar.clasificar_todo()
    otras = defaultdict(list)
    for c in recibidos:
        if c["categoria"] == "empleo":
            empresa = trabajos.empresa_de(c)
            if empresa:
                plan.agregar(f"{trabajos.CARPETA}/{empresa}", [c["id"]])
            else:
                plan.agregar(trabajos.ETIQUETA_OTRAS, [c["id"]])
                otras[c["de"]].append(c["asunto"])
        elif c["categoria"] == "oportunidad":
            plan.agregar(trabajos.ETIQUETA_ALERTAS, [c["id"]], archivar=True)

    # Un correo de una empresa no debe quedar también en Alertas
    en_empresas = set().union(*(ids for et, ids in plan.ids.items()
                                if et != trabajos.ETIQUETA_ALERTAS))
    plan.ids[trabajos.ETIQUETA_ALERTAS] -= en_empresas
    return plan, otras


def mostrar(plan, otras):
    print("\nPlan:")
    for etiqueta in sorted(plan.ids):
        extra = " (se archivan)" if etiqueta in plan.archivar else ""
        filtro = " + filtro automático" if etiqueta in plan.filtros else ""
        print(f"  {etiqueta:32} {len(plan.ids[etiqueta]):4} correos{extra}{filtro}")
    if otras:
        print("\nProcesos sin empresa reconocida (agrégalos a trabajos.EMPRESAS):")
        for de, asuntos in otras.items():
            print(f"  {de}: {asuntos[0][:60]}")


def obtener_etiquetas(gmail, nombres):
    existentes = {e["name"]: e["id"] for e in
                  ejecutar(gmail.users().labels().list(userId="me")).get("labels", [])}
    # crear primero la carpeta padre para que Gmail las anide
    for nombre in sorted({trabajos.CARPETA, *nombres}, key=len):
        if nombre not in existentes:
            creada = ejecutar(gmail.users().labels().create(userId="me", body={
                "name": nombre, "labelListVisibility": "labelShow",
                "messageListVisibility": "show"}))
            existentes[nombre] = creada["id"]
            print(f"  Etiqueta creada: {nombre}")
    return existentes


def aplicar(gmail, plan):
    etiquetas = obtener_etiquetas(gmail, plan.ids)
    for etiqueta, ids in plan.ids.items():
        cuerpo = {"addLabelIds": [etiquetas[etiqueta]]}
        if etiqueta in plan.archivar:
            cuerpo["removeLabelIds"] = ["INBOX"]
        ids = sorted(ids)
        for i in range(0, len(ids), MAX_IDS):
            ejecutar(gmail.users().messages().batchModify(
                userId="me", body={**cuerpo, "ids": ids[i:i + MAX_IDS]}))
        print(f"  {etiqueta}: {len(ids)} correos etiquetados")

    filtros_actuales = ejecutar(gmail.users().settings().filters().list(userId="me"))
    ya_existen = {f["criteria"].get("query") for f in filtros_actuales.get("filter", [])}
    for etiqueta, consulta in plan.filtros.items():
        if consulta in ya_existen:
            continue
        accion = {"addLabelIds": [etiquetas[etiqueta]]}
        if etiqueta in plan.archivar:
            accion["removeLabelIds"] = ["INBOX"]
        ejecutar(gmail.users().settings().filters().create(
            userId="me", body={"criteria": {"query": consulta}, "action": accion}))
        print(f"  Filtro creado para {etiqueta}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--aplicar", action="store_true", help="hacer los cambios en Gmail")
    args = p.parse_args()

    gmail = autenticar()
    plan, otras = armar_plan(gmail)
    mostrar(plan, otras)
    if not args.aplicar:
        print("\nSimulación: no se cambió nada. Ejecuta con --aplicar para hacerlo.")
        return
    print("\nAplicando en Gmail...")
    aplicar(gmail, plan)
    print("Listo.")


if __name__ == "__main__":
    main()
