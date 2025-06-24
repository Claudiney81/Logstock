from flask import Flask, redirect, url_for, has_request_context
from app.extensions import db, login_manager
from flask_migrate import Migrate

# Apenas esta linha fora da função (para registrar os modelos no alembic)
from app import models
from app.models import RequisicaoTecnico
from flask_login import current_user

# Importa todos os comandos CLI do app.cli
from app.cli import init_db, seed_dados, criar_usuario, editar_usuario, listar_usuarios, deletar_usuario
