import os
import zipfile
from datetime import datetime

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


ARQUIVO_TOKEN = "token_drive.json"
PASTA_BACKUP = "backups"
PASTA_DRIVE = "Backups LogiStock"


def criar_zip_backup():
    os.makedirs(PASTA_BACKUP, exist_ok=True)

    data = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    nome_zip = f"backup_logistock_{data}.zip"
    caminho_zip = os.path.join(PASTA_BACKUP, nome_zip)

    ignorar = {
        "venv",
        "__pycache__",
        ".git",
        "backups",
    }

    with zipfile.ZipFile(caminho_zip, "w", zipfile.ZIP_DEFLATED, strict_timestamps=False) as zipf:
        for raiz, pastas, arquivos in os.walk("."):
            pastas[:] = [p for p in pastas if p not in ignorar]

            for arquivo in arquivos:
                if arquivo.endswith(".pyc"):
                    continue

                caminho = os.path.join(raiz, arquivo)
                nome_no_zip = os.path.relpath(caminho, ".")

                zipf.write(caminho, nome_no_zip)

    return caminho_zip


def obter_ou_criar_pasta_drive(service):
    consulta = (
        f"name='{PASTA_DRIVE}' "
        "and mimeType='application/vnd.google-apps.folder' "
        "and trashed=false"
    )

    resultado = service.files().list(
        q=consulta,
        spaces="drive",
        fields="files(id, name)"
    ).execute()

    arquivos = resultado.get("files", [])

    if arquivos:
        return arquivos[0]["id"]

    metadata = {
        "name": PASTA_DRIVE,
        "mimeType": "application/vnd.google-apps.folder"
    }

    pasta = service.files().create(
        body=metadata,
        fields="id"
    ).execute()

    return pasta["id"]


def enviar_para_drive(caminho_arquivo):
    creds = Credentials.from_authorized_user_file(
        ARQUIVO_TOKEN,
        ["https://www.googleapis.com/auth/drive.file"]
    )

    service = build("drive", "v3", credentials=creds)

    pasta_id = obter_ou_criar_pasta_drive(service)

    nome_arquivo = os.path.basename(caminho_arquivo)

    metadata = {
        "name": nome_arquivo,
        "parents": [pasta_id]
    }

    media = MediaFileUpload(
        caminho_arquivo,
        mimetype="application/zip",
        resumable=True
    )

    arquivo = service.files().create(
        body=metadata,
        media_body=media,
        fields="id, name"
    ).execute()

    return arquivo


if __name__ == "__main__":
    print("Gerando backup...")
    caminho_zip = criar_zip_backup()

    print(f"Backup criado: {caminho_zip}")

    print("Enviando para o Google Drive...")
    arquivo = enviar_para_drive(caminho_zip)

    print("Backup enviado com sucesso!")
    print(f"Arquivo: {arquivo['name']}")
    print(f"ID Drive: {arquivo['id']}")
