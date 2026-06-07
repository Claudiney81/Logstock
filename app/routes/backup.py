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
        sucesso = enviar_backup_google_drive(
            "logistock.db"
        )

        if sucesso:
            return jsonify({
                "status": "ok",
                "mensagem": "Backup enviado para o Google Drive"
            })

        return jsonify({
            "status": "erro",
            "mensagem": "Falha ao enviar backup"
        }), 500

    except Exception as e:
        return jsonify({
            "status": "erro",
            "mensagem": str(e)
        }), 500