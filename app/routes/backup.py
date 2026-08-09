import os
import io
import sqlite3
import tempfile
from datetime import datetime

from flask import Blueprint, jsonify, current_app, send_file
from flask_login import login_required, current_user

from app.extensions import db
from app.utils.backup_drive import enviar_backup_google_drive

bp_backup = Blueprint(
    "backup",
    __name__,
    url_prefix="/backup"
)


def localizar_banco_sqlite():
    caminho_configurado = db.engine.url.database

    if caminho_configurado:
        caminho_configurado = os.path.abspath(caminho_configurado)

        if os.path.exists(caminho_configurado):
            return caminho_configurado

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


@bp_backup.route("/download")
@login_required
def download_backup():
    if getattr(current_user, "perfil", None) != "admin":
        return jsonify({"status": "erro", "mensagem": "Acesso apenas para admin"}), 403

    caminho_banco = localizar_banco_sqlite()
    arquivo_temporario = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    arquivo_temporario.close()

    origem = sqlite3.connect(caminho_banco)
    destino = sqlite3.connect(arquivo_temporario.name)
    try:
        origem.backup(destino)
    finally:
        destino.close()
        origem.close()

    try:
        with open(arquivo_temporario.name, "rb") as arquivo:
            conteudo = io.BytesIO(arquivo.read())
    finally:
        os.remove(arquivo_temporario.name)

    conteudo.seek(0)
    nome = f"logistock_render_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    return send_file(
        conteudo,
        as_attachment=True,
        download_name=nome,
        mimetype="application/x-sqlite3",
    )
