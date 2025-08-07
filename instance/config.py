import os
from urllib.parse import quote_plus

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# URL do banco PostgreSQL hospedado na Render
SQLALCHEMY_DATABASE_URI = 'postgresql://logstock_db_user:nErIcMmMHmkHXTKcJVYYm1MU2TWUIkUq@dpg-d2afshk9c44c738qvek0-a.oregon-postgres.render.com/logstock_db'

SQLALCHEMY_TRACK_MODIFICATIONS = False

# Chave secreta para sessões Flask
SECRET_KEY = os.environ.get('SECRET_KEY') or 'logistock123'
