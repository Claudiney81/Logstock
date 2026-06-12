from datetime import datetime, timedelta

from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import func, or_

from app.extensions import db
from app.models import (
    BaixaTecnica,
    Estoque,
    Item,
    MovimentacaoEstoque,
    NotaFiscalEntrada,
    RequisicaoTecnico,
    Tecnico,
)

home_bp = Blueprint('home', __name__)


def db_count(column):
    return db.session.query(func.count(column))

@home_bp.route('/')
@login_required
def home():
    hoje = datetime.utcnow()
    inicio_30_dias = hoje - timedelta(days=30)

    estoque_baixo = (
        db_count(Estoque.id)
        .filter(
            Estoque.quantidade_minima > 0,
            Estoque.quantidade <= Estoque.quantidade_minima
        )
        .scalar()
        or 0
    )

    indicadores = {
        "itens": db_count(Item.id).scalar() or 0,
        "tecnicos_ativos": db_count(Tecnico.id).filter(
            or_(Tecnico.status.is_(None), Tecnico.status == "Ativo")
        ).scalar() or 0,
        "estoque_baixo": estoque_baixo,
        "requisicoes_pendentes": db_count(RequisicaoTecnico.id).filter_by(
            status="pendente"
        ).scalar() or 0,
        "baixas_pendentes": db_count(BaixaTecnica.id).filter(
            BaixaTecnica.status.in_(["pendente", "pendente_ajuste"])
        ).scalar() or 0,
        "notas_30_dias": db_count(NotaFiscalEntrada.id).filter(
            NotaFiscalEntrada.data_hora >= inicio_30_dias
        ).scalar() or 0,
    }

    movimentacoes_recentes = (
        MovimentacaoEstoque.query
        .order_by(MovimentacaoEstoque.data_hora.desc())
        .limit(5)
        .all()
    )

    notas_recentes = (
        NotaFiscalEntrada.query
        .order_by(NotaFiscalEntrada.data_hora.desc())
        .limit(5)
        .all()
    )

    baixas_recentes = (
        BaixaTecnica.query
        .order_by(BaixaTecnica.data_hora.desc())
        .limit(5)
        .all()
    )

    return render_template(
        'home.html',
        indicadores=indicadores,
        movimentacoes_recentes=movimentacoes_recentes,
        notas_recentes=notas_recentes,
        baixas_recentes=baixas_recentes
    )
