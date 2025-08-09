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
    token = request.args.get("token")
    if token != os.getenv("ADMIN_BOOTSTRAP_TOKEN"):
        return "Token inválido", 403

    # Verifica se já existe um admin
    if Usuario.query.filter_by(email="admin@logstock.com").first():
        return "Usuário admin já existe.", 200

    admin = Usuario(
        nome="Administrador",
        email="admin@logstock.com",
        perfil="admin",
        senha_hash=generate_password_hash("811401")  # corrigido para usar o campo certo
    )
    db.session.add(admin)
    db.session.commit()
    return "Usuário admin criado com sucesso!", 201


# Executa localmente
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
