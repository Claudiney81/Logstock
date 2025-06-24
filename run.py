import os
from app import create_app

app = create_app()

# Cria as tabelas automaticamente no Railway
with app.app_context():
    from app.extensions import db
    db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

