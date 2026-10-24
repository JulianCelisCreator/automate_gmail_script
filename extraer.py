"""Fases 1-2: descarga metadatos de Gmail (solo lectura) a datos/.

Uso: .venv/bin/python extraer.py [--dias 90]
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

BASE = Path(__file__).parent
# Un solo token para todo (modify incluye lectura): así reautorizar es un solo paso
SCOPES = ["https://www.googleapis.com/auth/gmail.modify",
          "https://www.googleapis.com/auth/gmail.settings.basic"]
CREDENCIALES = BASE / "credentials.json"
TOKEN = BASE / "token.json"
DATOS = BASE / "datos"
CABECERAS = ["From", "To", "Cc", "Subject", "Date", "List-Unsubscribe",
             "List-Unsubscribe-Post", "List-Id", "Precedence"]
LOTE = 10  # peticiones por lote; la cuota por minuto de proyectos nuevos es baja
PAUSA = 1.0  # segundos entre lotes
MAX_REINTENTOS = 10


def autenticar(scopes=SCOPES, token=TOKEN):
    """Cada conjunto de permisos usa su propio archivo de token."""
    creds = None
    if token.exists():
        creds = Credentials.from_authorized_user_file(str(token), scopes)
    if creds and not creds.valid and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:
            creds = None  # autorización vencida o revocada: hay que volver a autorizar
    if not creds or not creds.valid:
        if os.environ.get("ORGANIZADOR_NO_INTERACTIVO"):  # cron: no hay navegador
            sys.exit("La autorización de Google venció. Para renovarla ejecuta a mano: "
                     "./reautorizar.sh")
        if not CREDENCIALES.exists():
            sys.exit("Falta credentials.json. Revisa README.md, paso 1.")
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENCIALES), scopes)
        creds = flow.run_local_server(port=0)
    token.write_text(creds.to_json())
    token.chmod(0o600)
    return build("gmail", "v1", credentials=creds)


def ejecutar(peticion):
    """Ejecuta una petición esperando a que se libere la cuota si hace falta."""
    for intento in range(MAX_REINTENTOS):
        try:
            return peticion.execute()
        except HttpError as e:
            if e.resp.status not in (403, 429) or intento == MAX_REINTENTOS - 1:
                raise
            print("\n  Límite de cuota; esperando 60s")
            time.sleep(60)


def listar(gmail, consulta):
    mensajes, pagina = [], None
    while True:
        r = ejecutar(gmail.users().messages().list(
            userId="me", q=consulta, maxResults=500, pageToken=pagina))
        mensajes += r.get("messages", [])
        pagina = r.get("nextPageToken")
        print(f"\r  {len(mensajes)} encontrados...", end="", flush=True)
        if not pagina:
            break
    print()
    return mensajes


def descargar(gmail, ids):
    resultados, pendientes = {}, list(ids)
    for _ in range(MAX_REINTENTOS):
        fallidos = []

        def guardar(req_id, resp, exc):
            if exc:
                fallidos.append(req_id)
            else:
                resultados[req_id] = resp

        for i in range(0, len(pendientes), LOTE):
            lote = gmail.new_batch_http_request(callback=guardar)
            for mid in pendientes[i:i + LOTE]:
                lote.add(gmail.users().messages().get(
                    userId="me", id=mid, format="metadata",
                    metadataHeaders=CABECERAS), request_id=mid)
            lote.execute()
            print(f"\r  {len(resultados)}/{len(ids)} descargados...", end="", flush=True)
            time.sleep(PAUSA)
        print()
        if not fallidos:
            break
        # la cuota se mide por minuto: esperar a que se renueve
        print(f"  {len(fallidos)} fallaron (límite de cuota); reintentando en 60s")
        time.sleep(60)
        pendientes = fallidos
    else:
        print(f"  Aviso: {len(pendientes)} correos no se pudieron descargar")
    return list(resultados.values())


def resumir(msg):
    h = {x["name"].lower(): x["value"] for x in msg["payload"].get("headers", [])}
    return {
        "id": msg["id"],
        "hilo": msg["threadId"],
        "fecha": int(msg["internalDate"]) // 1000,
        "etiquetas": msg.get("labelIds", []),
        "de": h.get("from", ""),
        "para": h.get("to", ""),
        "cc": h.get("cc", ""),
        "asunto": h.get("subject", ""),
        "list_unsubscribe": h.get("list-unsubscribe", ""),
        "list_unsubscribe_post": h.get("list-unsubscribe-post", ""),
        "list_id": h.get("list-id", ""),
        "precedence": h.get("precedence", ""),
        "fragmento": msg.get("snippet", ""),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dias", type=int, default=90)
    args = p.parse_args()

    gmail = autenticar()
    perfil = gmail.users().getProfile(userId="me").execute()
    print(f"Cuenta: {perfil['emailAddress']}")
    DATOS.mkdir(exist_ok=True)

    for nombre, consulta in [("recibidos", f"newer_than:{args.dias}d -in:sent -in:chats"),
                             ("enviados", f"newer_than:{args.dias}d in:sent")]:
        print(f"Listando {nombre} de los últimos {args.dias} días")
        ruta = DATOS / f"{nombre}.jsonl"
        previos = {}
        if ruta.exists():  # reanudar: no volver a descargar lo que ya está
            with open(ruta) as f:
                previos = {c["id"]: c for c in map(json.loads, f)}
        ids = [m["id"] for m in listar(gmail, consulta)]
        nuevos = [i for i in ids if i not in previos]
        print(f"  {len(ids) - len(nuevos)} ya descargados, faltan {len(nuevos)}")
        correos = [previos[i] for i in ids if i in previos]
        correos += [resumir(m) for m in descargar(gmail, nuevos)]
        with open(ruta, "w") as f:
            for c in correos:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
        print(f"  Guardado datos/{nombre}.jsonl ({len(correos)})")

    (DATOS / "meta.json").write_text(json.dumps(
        {"cuenta": perfil["emailAddress"], "dias": args.dias, "extraido": int(time.time())}))
    print("Listo. Ahora ejecuta: .venv/bin/python analizar.py")


if __name__ == "__main__":
    main()
