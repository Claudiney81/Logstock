from app import create_app, db
from app.models import Usuario
from flask import request
from werkzeug.security import generate_password_hash
import os

# Cria a aplicação
app = create_app()

# Rota temporária para criar o admin
@app.get("/_bootstrap_admin")
def _bootstrap_admin():
    expected_token = os.getenv("ADMIN_BOOTSTRAP_TOKEN")
    token = request.args.get("token")

    if not expected_token or token != expected_token:
        return "Token inválido", 403

    admin_email = os.getenv("ADMIN_BOOTSTRAP_EMAIL", "admin@logstock.com")
    admin_password = os.getenv("ADMIN_BOOTSTRAP_PASSWORD")
    admin_name = os.getenv("ADMIN_BOOTSTRAP_NAME", "Administrador")

    if not admin_password:
        return "ADMIN_BOOTSTRAP_PASSWORD não configurada", 400

    if Usuario.query.filter_by(email=admin_email).first():
        return "Usuário admin já existe.", 200

    admin = Usuario(
        nome=admin_name,
        email=admin_email,
        perfil="admin",
        senha_hash=generate_password_hash(admin_password)
    )

    db.session.add(admin)
    db.session.commit()

    return "Usuário admin criado com sucesso!", 201


# Executa localmente
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
