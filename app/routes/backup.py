from flask import Blueprint, jsonify
from flask_login import login_required
import os

bp_backup = Blueprint(
    "backup",
    __name__,
    url_prefix="/backup"
)


@bp_backup.route("/executar")
@login_required
def executar_backup():

    return jsonify({
        "cwd": os.getcwd(),
        "arquivos": os.listdir(".")
    })