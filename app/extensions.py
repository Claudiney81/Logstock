from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail

# Banco de dados
db = SQLAlchemy()

# Autenticação
login_manager = LoginManager()
login_manager.login_view = 'auth.login'  # rota para redirecionar quem não estiver logado
login_manager.login_message_category = 'info'

# E-mail
mail = Mail()
