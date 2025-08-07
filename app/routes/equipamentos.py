from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.extensions import db
from app.models import Item, Tecnico, TipoServico, Estoque, EquipamentoTecnico, HistoricoEquipamento
from datetime import datetime
from sqlalchemy import func

bp_equipamentos = Blueprint('equipamentos', __name__, url_prefix='/equipamentos')

# ➕ NOVA MOVIMENTAÇÃO
@bp_equipamentos.route('/nova', methods=['GET', 'POST'])
def nova_movimentacao():
    tecnicos = Tecnico.query.order_by(Tecnico.nome).all()
    tipos_servico = TipoServico.query.order_by(TipoServico.nome).all()

    if request.method == 'POST':
        tecnico_id = request.form.get('tecnico_id')
        tipo_servico_id = request.form.get('tipo_servico_id')
        local = request.form.get('local')
        observacao = request.form.get('observacao')

        codigos = request.form.getlist('codigo[]')
        quantidades = request.form.getlist('quantidade[]')
        status_lista = request.form.getlist('status[]')

        for i in range(len(codigos)):
            codigo = codigos[i]
            quantidade = int(quantidades[i])
            status = status_lista[i]

            item = Item.query.filter_by(codigo=codigo, eh_equipamento=True).first()
            if not item:
                continue

            # ➕ SAÍDA PARA TÉCNICO
            if status.lower() == 'tecnico':
                estoque = Estoque.query.filter_by(item_id=item.id, tipo_servico_id=tipo_servico_id).first()
                if estoque and estoque.quantidade >= quantidade:
                    estoque.quantidade -= quantidade

                    for _ in range(quantidade):
                        equipamento = EquipamentoTecnico(
                            item_id=item.id,
                            tecnico_id=tecnico_id,
                            local=local,
                            status='tecnico',
                            data_hora=datetime.utcnow()
                        )
                        db.session.add(equipamento)
                else:
                    flash(f"Estoque insuficiente para {item.descricao}", "warning")
                    continue

            # 🔁 DEVOLUÇÃO PARA O ESTOQUE
            elif status == 'almoxarifado':
                equipamentos = EquipamentoTecnico.query.filter_by(
                    item_id=item.id,
                    tecnico_id=tecnico_id,
                    status='tecnico'
                ).limit(quantidade).all()

                if len(equipamentos) < quantidade:
                    flash(f"Técnico não possui {quantidade} un. de {item.descricao} para devolução", "warning")
                    continue

                for equipamento in equipamentos:
                    equipamento.tecnico_id = None
                    equipamento.status = 'almoxarifado'
                    equipamento.local = local
                    equipamento.data_hora = datetime.utcnow()

                estoque = Estoque.query.filter_by(item_id=item.id, tipo_servico_id=tipo_servico_id).first()
                if estoque:
                    estoque.quantidade += quantidade
                else:
                    novo_estoque = Estoque(item_id=item.id, tipo_servico_id=tipo_servico_id, quantidade=quantidade)
                    db.session.add(novo_estoque)

            # 🕒 HISTÓRICO
            historico = HistoricoEquipamento(
                item_id=item.id,
                tecnico_id=tecnico_id if status == 'tecnico' else None,
                local=local,
                status=status,
                observacao=observacao,
                data_hora=datetime.utcnow()
            )
            db.session.add(historico)

        db.session.commit()
        flash("Movimentação registrada com sucesso!", "success")
        return redirect(url_for('equipamentos.nova_movimentacao'))

    return render_template('equipamentos/nova_movimentacao_equipamento.html', tecnicos=tecnicos, tipos_servico=tipos_servico)


# 📊 API - ITENS FILTRADOS POR TIPO DE SERVIÇO
@bp_equipamentos.route('/api/itens_equipamentos/<int:tipo_servico_id>')
def api_itens_equipamentos(tipo_servico_id):
    itens = Item.query.filter_by(eh_equipamento=True).all()
    resultado = [{"codigo": item.codigo, "descricao": item.descricao} for item in itens]
    return jsonify(resultado)


# 📅 HISTÓRICO COMPLETO
@bp_equipamentos.route('/historico')
def historico_equipamentos():
    historico = HistoricoEquipamento.query.order_by(HistoricoEquipamento.data_hora.desc()).all()
    return render_template('equipamentos/historico_equipamento.html', historico=historico)


# 🛠️ SALDO AGRUPADO POR TÉCNICO/ITEM
@bp_equipamentos.route('/saldo')
def saldo_tecnico():
    saldos = (
        db.session.query(
            EquipamentoTecnico.item_id,
            EquipamentoTecnico.tecnico_id,
            func.count(EquipamentoTecnico.id).label('quantidade'),
            Item.codigo,
            Item.descricao,
            Tecnico.nome.label('tecnico_nome')
        )
        .join(Item, EquipamentoTecnico.item_id == Item.id)
        .join(Tecnico, EquipamentoTecnico.tecnico_id == Tecnico.id)
        .filter(EquipamentoTecnico.status == 'tecnico')
        .group_by(EquipamentoTecnico.item_id, EquipamentoTecnico.tecnico_id, Item.codigo, Item.descricao, Tecnico.nome)
        .order_by(Tecnico.nome)
        .all()
    )
    return render_template('equipamentos/saldo_tecnico_equipamento.html', saldos=saldos)


# 🔁 DEVOLUÇÃO DIRETA
@bp_equipamentos.route('/devolver', methods=['POST'])
def devolver_ferramenta():
    data = request.get_json()

    item_id = data.get('item_id')
    tecnico_id = data.get('tecnico_id')
    qtd = int(data.get('quantidade', 0))
    local = data.get('local', 'DEVOLVIDO VIA SALDO')

    if qtd <= 0:
        return jsonify(success=False, message="Quantidade inválida.")

    equipamentos = EquipamentoTecnico.query.filter_by(
        item_id=item_id,
        tecnico_id=tecnico_id,
        status='tecnico'
    ).limit(qtd).all()

    if len(equipamentos) < qtd:
        return jsonify(success=False, message="Técnico não possui essa quantidade para devolução.")

    for equipamento in equipamentos:
        equipamento.tecnico_id = None
        equipamento.status = 'almoxarifado'
        equipamento.local = local
        equipamento.data_hora = datetime.utcnow()

    estoque = Estoque.query.filter_by(item_id=item_id).first()
    if estoque:
        estoque.quantidade += qtd
    else:
        novo = Estoque(item_id=item_id, quantidade=qtd)
        db.session.add(novo)

    historico = HistoricoEquipamento(
        item_id=item_id,
        tecnico_id=None,
        local=local,
        status='almoxarifado',
        observacao=f"Devolvido via saldo do técnico {tecnico_id}",
        data_hora=datetime.utcnow()
    )
    db.session.add(historico)

    db.session.commit()
    return jsonify(success=True)

# 🔁 DEVOLUÇÃO VIA HISTÓRICO
@bp_equipamentos.route('/devolver_historico', methods=['POST'])
def devolver_historico():
    data = request.get_json()
    id = data.get('id')

    equipamento = EquipamentoTecnico.query.get(id)
    if not equipamento or equipamento.status != 'tecnico':
        return jsonify(success=False, message="Equipamento não encontrado ou já devolvido.")

    equipamento.status = 'almoxarifado'
    equipamento.tecnico_id = None
    equipamento.local = 'DEVOLVIDO VIA HISTÓRICO'
    equipamento.data_hora = datetime.utcnow()

    estoque = Estoque.query.filter_by(item_id=equipamento.item_id).first()
    if estoque:
        estoque.quantidade += 1
    else:
        novo = Estoque(item_id=equipamento.item_id, quantidade=1)
        db.session.add(novo)

    historico = HistoricoEquipamento(
        item_id=equipamento.item_id,
        tecnico_id=None,
        local='DEVOLVIDO VIA HISTÓRICO',
        status='almoxarifado',
        observacao='Devolvido manualmente via histórico',
        data_hora=datetime.utcnow()
    )
    db.session.add(historico)

    db.session.commit()
    return jsonify(success=True)

