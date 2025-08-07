from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.extensions import db
from app.models import Tecnico, TipoServico, Item, Estoque, SaldoTecnico, KitInicial, KitInicialItem
from datetime import datetime
import json

kit_inicial_bp = Blueprint('kit_inicial', __name__, url_prefix='/kit_inicial')


# --- FORMULÁRIO DE CRIAÇÃO DO KIT ---
@kit_inicial_bp.route('/cadastrar', methods=['GET', 'POST'])
def cadastrar_kit():
    tecnicos = Tecnico.query.order_by(Tecnico.nome).all()
    tipos_servico = TipoServico.query.order_by(TipoServico.nome).all()

    if request.method == 'POST':
        data = request.form
        nome_kit = data.get('nome_kit')
        tecnico_id = data.get('tecnico_id')
        tipo_servico_id = data.get('tipo_servico_id')
        observacao = data.get('observacao')
        itens_json = data.get('itens_json')

        if not nome_kit or not tecnico_id or not tipo_servico_id or not itens_json:
            flash('Preencha todos os campos obrigatórios e insira itens.', 'danger')
            return redirect(url_for('kit_inicial.cadastrar_kit'))

        try:
            itens = json.loads(itens_json)
        except json.JSONDecodeError:
            flash('Erro ao processar os itens enviados.', 'danger')
            return redirect(url_for('kit_inicial.cadastrar_kit'))

        # Cria kit inicial
        novo_kit = KitInicial(
            nome_kit=nome_kit,
            tecnico_id=tecnico_id,
            tipo_servico_id=tipo_servico_id,
            observacao=observacao,
            data_hora=datetime.utcnow()
        )
        db.session.add(novo_kit)
        db.session.flush()  # para pegar o ID

        sucesso = False

        for i in itens:
            codigo = i.get('codigo')
            quantidade = int(i.get('quantidade', 0))
            valor = float(i.get('valor', 0))

            if not codigo or quantidade <= 0:
                continue

            item_obj = Item.query.filter_by(codigo=codigo).first()
            if not item_obj:
                continue

            # Baixa do estoque central
            estoque = Estoque.query.filter_by(item_id=item_obj.id, tipo_servico_id=tipo_servico_id).first()
            if estoque:
                if estoque.quantidade < quantidade:
                    flash(f"Saldo insuficiente para o item {codigo}. Saldo disponível: {estoque.quantidade}", "danger")
                    db.session.rollback()
                    return redirect(url_for('kit_inicial.cadastrar_kit'))
                estoque.quantidade -= quantidade

            # Cria item do kit
            kit_item = KitInicialItem(
                kit_inicial_id=novo_kit.id,
                item_id=item_obj.id,
                quantidade=quantidade,
                valor_unitario=valor
            )
            db.session.add(kit_item)

            # Atualiza saldo técnico
            saldo_tec = SaldoTecnico.query.filter_by(
                tecnico_id=tecnico_id,
                item_id=item_obj.id,
                tipo_servico_id=tipo_servico_id
            ).first()
            if saldo_tec:
                saldo_tec.quantidade += quantidade
            else:
                saldo_tec = SaldoTecnico(
                    tecnico_id=tecnico_id,
                    item_id=item_obj.id,
                    tipo_servico_id=tipo_servico_id,
                    quantidade=quantidade,
                    endereco='',
                    bairro='',
                    codigo_imovel=''
                )
                db.session.add(saldo_tec)

            sucesso = True

        if not sucesso:
            db.session.rollback()
            flash('Nenhum item válido foi adicionado ao kit.', 'danger')
            return redirect(url_for('kit_inicial.cadastrar_kit'))

        db.session.commit()
        flash('Kit inicial transferido com sucesso!', 'success')
        return redirect(url_for('kit_inicial.historico_kits'))

    return render_template('kit_inicial/cadastrar.html', tecnicos=tecnicos, tipos_servico=tipos_servico)


# --- HISTÓRICO ---
@kit_inicial_bp.route('/historico')
def historico_kits():
    tecnico_id = request.args.get('tecnico_id', type=int)
    tipo_servico_id = request.args.get('tipo_servico_id', type=int)

    query = KitInicial.query
    if tecnico_id:
        query = query.filter_by(tecnico_id=tecnico_id)
    if tipo_servico_id:
        query = query.filter_by(tipo_servico_id=tipo_servico_id)

    kits = query.order_by(KitInicial.data_hora.desc()).all()
    tecnicos = Tecnico.query.order_by(Tecnico.nome).all()
    tipos_servico = TipoServico.query.order_by(TipoServico.nome).all()

    return render_template(
        'kit_inicial/historico.html',
        kits=kits,
        tecnicos=tecnicos,
        tipos_servico=tipos_servico,
        tecnico_id=tecnico_id,
        tipo_servico_id=tipo_servico_id
    )


# --- DETALHES ---
@kit_inicial_bp.route('/detalhes/<int:id>')
def detalhes_kit(id):
    kit = KitInicial.query.get_or_404(id)
    return render_template('kit_inicial/detalhes.html', kit=kit)


# --- API PARA ITENS POR TIPO DE SERVIÇO (igual interna) ---
@kit_inicial_bp.route('/api/itens_por_tipo_servico/<int:tipo_servico_id>')
def api_itens_por_tipo_servico(tipo_servico_id):
    itens = (
        db.session.query(Item, Estoque)
        .join(Estoque, Item.id == Estoque.item_id)
        .filter(Estoque.tipo_servico_id == tipo_servico_id, Estoque.quantidade > 0)
        .order_by(Item.descricao)
        .all()
    )

    resultado = [
        {
            'codigo': item.codigo,
            'descricao': item.descricao,
            'unidade': item.unidade,
            'quantidade_disponivel': estoque.quantidade,
            'valor': item.valor
        }
        for item, estoque in itens
    ]
    return jsonify(resultado)
