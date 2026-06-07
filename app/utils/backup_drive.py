import os
from datetime import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def enviar_backup_google_drive(caminho_arquivo):

    credentials_file = os.getenv("GOOGLE_DRIVE_CREDENTIALS_FILE")
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

    if not credentials_file:
        raise Exception("Variável GOOGLE_DRIVE_CREDENTIALS_FILE não configurada")

    if not folder_id:
        raise Exception("Variável GOOGLE_DRIVE_FOLDER_ID não configurada")

    if not os.path.exists(credentials_file):
        raise Exception(f"Arquivo de credenciais não encontrado: {credentials_file}")

    if not os.path.exists(caminho_arquivo):
        raise Exception(f"Banco não encontrado: {caminho_arquivo}")

    credentials = service_account.Credentials.from_service_account_file(
        credentials_file,
        scopes=["https://www.googleapis.com/auth/drive.file"]
    )

    service = build(
        "drive",
        "v3",
        credentials=credentials
    )

    nome_backup = (
        f"logistock_backup_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    )

    metadata = {
        "name": nome_backup,
        "parents": [folder_id]
    }

    media = MediaFileUpload(
        caminho_arquivo,
        mimetype="application/octet-stream"
    )

    arquivo = service.files().create(
        body=metadata,
        media_body=media,
        fields="id"
    ).execute()

    return arquivo.get("id")