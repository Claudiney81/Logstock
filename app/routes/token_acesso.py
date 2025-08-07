from flask import Blueprint, render_template, redirect, abort
from app.extensions import db
from app.models import TokenAcessoTecnico, Tecnico
from flask_login import login_user
from app.models import Usuario

token_acesso = Blueprint('token_acesso', __name__)

@token_acesso.route('/baixa-mobile/token/<token>')
def acesso_por_token(token):
    token_obj = Token
