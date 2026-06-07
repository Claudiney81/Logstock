import os
from datetime import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def enviar_backup_google_drive(caminho_arquivo):
    try:

        credentials = service_account.Credentials.from_service_account_file(
            os.getenv("GOOGLE_DRIVE_CREDENTIALS_FILE")
        )

        service = build(
            "drive",
            "v3",
            credentials=credentials
        )

        folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

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

        print(
            f"Backup enviado com sucesso. ID: {arquivo.get('id')}"
        )

        return True

    except Exception as e:
        print(f"Erro ao enviar backup: {e}")
        return False