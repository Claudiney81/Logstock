import os
from datetime import datetime

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from app import create_app
from app.extensions import db
from app.utils.backup_drive import enviar_backup_google_drive


ARQUIVO_TOKEN = "token_drive.json"
PASTA_DRIVE = "Backups LogiStock"


def banco_ativo():
    database_path = db.engine.url.database

    if not database_path:
        raise RuntimeError("Banco ativo não encontrado na configuração.")

    database_path = os.path.abspath(database_path)

    if not os.path.exists(database_path):
        raise FileNotFoundError(f"Banco ativo não encontrado: {database_path}")

    return database_path


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


def enviar_com_token_usuario(caminho_banco):
    creds = Credentials.from_authorized_user_file(
        ARQUIVO_TOKEN,
        ["https://www.googleapis.com/auth/drive.file"]
    )

    service = build("drive", "v3", credentials=creds)
    pasta_id = obter_ou_criar_pasta_drive(service)

    nome_backup = (
        "logistock_backup_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    )

    metadata = {
        "name": nome_backup,
        "parents": [pasta_id]
    }

    media = MediaFileUpload(
        caminho_banco,
        mimetype="application/octet-stream",
        resumable=True
    )

    arquivo = service.files().create(
        body=metadata,
        media_body=media,
        fields="id, name"
    ).execute()

    return arquivo


def enviar_backup(caminho_banco):
    if (
        os.getenv("GOOGLE_DRIVE_CREDENTIALS_FILE")
        and os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    ):
        arquivo_id = enviar_backup_google_drive(caminho_banco)
        return {
            "id": arquivo_id,
            "name": os.path.basename(caminho_banco)
        }

    if os.path.exists(ARQUIVO_TOKEN):
        return enviar_com_token_usuario(caminho_banco)

    raise RuntimeError(
        "Backup Google Drive não configurado. Configure "
        "GOOGLE_DRIVE_CREDENTIALS_FILE/GOOGLE_DRIVE_FOLDER_ID ou token_drive.json."
    )


if __name__ == "__main__":
    app = create_app()

    with app.app_context():
        print("Localizando banco ativo...")
        caminho_banco = banco_ativo()
        print(f"Banco ativo: {caminho_banco}")

        print("Enviando backup para o Google Drive...")
        arquivo = enviar_backup(caminho_banco)

        print("Backup enviado com sucesso!")
        print(f"Arquivo: {arquivo.get('name', 'logistock_backup.db')}")
        print(f"ID Drive: {arquivo['id']}")
