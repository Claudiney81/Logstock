import os

from flask import Blueprint, jsonify
from flask_login import login_required

from app.utils.backup_drive import enviar_backup_google_drive

bp_backup = Blueprint(
    "backup",
    __name__,
    url_prefix="/backup"
)


@bp_backup.route("/executar")
@login_required
def executar_backup():

    try:
        caminho_banco = os.path.join(
            os.getcwd(),
            "logistock.db"
        )

        arquivo_id = enviar_backup_google_drive(
            caminho_banco
        )

        return jsonify({
            "status": "ok",
            "mensagem": "Backup enviado para o Google Drive",
            "arquivo_id": arquivo_id
        })

    except Exception as e:
        return jsonify({
            "status": "erro",
            "mensagem": str(e)
        }), 500