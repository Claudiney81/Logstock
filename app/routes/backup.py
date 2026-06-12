import os

from flask import Blueprint, jsonify, current_app
from flask_login import login_required, current_user

from app.utils.backup_drive import enviar_backup_google_drive

bp_backup = Blueprint(
    "backup",
    __name__,
    url_prefix="/backup"
)


def localizar_banco_sqlite():
    candidatos = [
        os.path.join(os.getcwd(), "logistock.db"),
        os.path.join(os.getcwd(), "instance", "logistock.db"),
        os.path.join(current_app.root_path, "..", "logistock.db"),
        os.path.join(current_app.instance_path, "logistock.db"),
    ]

    for caminho in candidatos:
        caminho_absoluto = os.path.abspath(caminho)

        if os.path.exists(caminho_absoluto):
            return caminho_absoluto

    raise Exception(
        "Banco não encontrado. Caminhos testados: "
        + " | ".join(os.path.abspath(c) for c in candidatos)
    )


@bp_backup.route("/executar")
@login_required
def executar_backup():

    if getattr(current_user, "perfil", None) not in ["admin", "estoque"]:
        return jsonify({
            "status": "erro",
            "mensagem": "Acesso permitido apenas para admin ou estoque"
        }), 403

    try:
        caminho_banco = localizar_banco_sqlite()

        arquivo_id = enviar_backup_google_drive(
            caminho_banco
        )

        return jsonify({
            "status": "ok",
            "mensagem": "Backup enviado para o Google Drive",
            "caminho_banco": caminho_banco,
            "arquivo_id": arquivo_id
        })

    except Exception as e:
        return jsonify({
            "status": "erro",
            "mensagem": str(e)
        }), 500
