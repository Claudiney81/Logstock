from flask import Blueprint, render_template, request, send_file
from sqlalchemy import func
from app.models import Tecnico, SaldoTecnico, TipoServico, Item
from app.extensions import db
import pandas as pd
import io

bp = Blueprint('saldo_tecnico', __name__)

# Página principal com listagem dos técnicos
@bp.route('/saldo_tecnico')
def exibir_saldo():
    termo_busca = request.args.get('tecnico', '').strip()
    tecnicos = Tecnico.query.order_by(Tecnico.nome).all()

    if termo_busca:
        tecnicos = [t for t in tecnicos if termo_busca.lower() in t.nome.lower()]

    return render_template('saldo_tecnico.html', tecnicos=tecnicos, termo_busca=termo_busca)

# Página de saldo detalhado de um técnico (saldo geral)
@bp.route('/saldo_tecnico/<int:id_tecnico>', methods=['GET'])
def saldo_detalhado(id_tecnico):
    tecnico = Tecnico.query.get_or_404(id_tecnico)
    tipo_servico_id = request.args.get('tipo_servico_id', type=int)

    # Consulta saldos
    query = (
        db.session.query(
            Item.codigo.label('codigo'),
            Item.descricao.label('descricao'),
            Item.unidade.label('unidade'),
            func.sum(SaldoTecnico.quantidade).label('quantidade')
        )
        .join(Item, Item.id == SaldoTecnico.item_id)
        .filter(SaldoTecnico.tecnico_id == id_tecnico)
    )
    if tipo_servico_id:
        query = query.filter(SaldoTecnico.tipo_servico_id == tipo_servico_id)

    query = query.group_by(Item.codigo, Item.descricao, Item.unidade)
    saldos = query.all()

    tipos_servico = TipoServico.query.order_by(TipoServico.nome).all()

    # Novo: buscar o responsável do tipo de serviço
    responsavel = None
    if tipo_servico_id:
        tipo = TipoServico.query.get(tipo_servico_id)
        responsavel = tipo.responsavel if tipo and hasattr(tipo, 'responsavel') else None

    return render_template(
        'saldo_tecnico_detalhado.html',
        tecnico=tecnico,
        saldos=saldos,
        tipos_servico=tipos_servico,
        tipo_servico_id=tipo_servico_id,
        responsavel=responsavel
    )


# Exporta o saldo geral de um técnico para Excel (com filtro por tipo de serviço)
@bp.route('/saldo_tecnico/<int:id_tecnico>/exportar', methods=['GET'])
def exportar_saldo_tecnico(id_tecnico):
    tecnico = Tecnico.query.get_or_404(id_tecnico)
    tipo_servico_id = request.args.get('tipo_servico_id', type=int)

    query = (
        db.session.query(
            Item.codigo.label('Código'),
            Item.descricao.label('Descrição'),
            Item.unidade.label('Unidade'),
            func.sum(SaldoTecnico.quantidade).label('Quantidade')
        )
        .join(Item, Item.id == SaldoTecnico.item_id)
        .filter(SaldoTecnico.tecnico_id == id_tecnico)
    )
    if tipo_servico_id:
        query = query.filter(SaldoTecnico.tipo_servico_id == tipo_servico_id)

    query = query.group_by(Item.codigo, Item.descricao, Item.unidade)
    saldos = query.all()

    dados = [dict(row._mapping) for row in saldos]

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        pd.DataFrame(dados).to_excel(writer, index=False, sheet_name='Saldo Técnico')

    output.seek(0)
    nome_arquivo = f"saldo_tecnico_{tecnico.nome.replace(' ', '_')}.xlsx"
    return send_file(output, download_name=nome_arquivo, as_attachment=True)
