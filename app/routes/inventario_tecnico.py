from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from datetime import datetime
from app.models import Tecnico, TipoServico, Item, InventarioTecnico, InventarioTecnicoItem, SaldoTecnico
from app.extensions import db
import pandas as pd
import io

bp_inventario = Blueprint('inventario_tecnico', __name__, url_prefix='/inventario_tecnico')

# ========== NOVO INVENTÁRIO (SALDO BASE) ==========
@bp_inventario.route('/novo', methods=['GET', 'POST'])
def registrar_inventario():
    tecnicos = Tecnico.query.all()
    tipos_servico = TipoServico.query.all()

    tecnico_id = request.form.get('tecnico_id', type=int)
    tipo_servico_id = request.form.get('tipo_servico_id', type=int)
    responsavel = request.form.get('responsavel', '')

    saldo_tecnico = []
    if tecnico_id and tipo_servico_id:
        saldo_tecnico = SaldoTecnico.query.filter_by(
            tecnico_id=tecnico_id,
            tipo_servico_id=tipo_servico_id
        ).all()

    # PROCESSA INVENTÁRIO
    if request.method == 'POST' and request.form.getlist('quantidade_contada[]'):
        codigos = request.form.getlist('codigo[]')
        quantidades = request.form.getlist('quantidade_contada[]')

        # Verifica se há ao menos um item com quantidade informada
        itens_preenchidos = [q for q in quantidades if q.strip() != '']
        if not itens_preenchidos:
            flash('Nenhum item informado para contagem.', 'warning')
            return redirect(url_for('inventario_tecnico.registrar_inventario'))

        data = datetime.utcnow()
        inventario = InventarioTecnico(
            tecnico_id=tecnico_id,
            tipo_servico_id=tipo_servico_id,
            data=data,
            responsavel=responsavel
        )
        db.session.add(inventario)
        db.session.flush()

        # Percorre os itens informados
        for i in range(len(codigos)):
            if not quantidades[i].strip():  # pula campos vazios
                continue

            codigo = codigos[i]
            quantidade = int(quantidades[i])

            item = Item.query.filter_by(codigo=codigo).first()
            if item:
                inv_item = InventarioTecnicoItem(
                    inventario_id=inventario.id,
                    item_id=item.id,
                    quantidade_contada=quantidade
                )
                db.session.add(inv_item)

                # Atualiza ou cria saldo técnico
                estoque = SaldoTecnico.query.filter_by(
                    tecnico_id=tecnico_id,
                    item_id=item.id,
                    tipo_servico_id=tipo_servico_id
                ).first()

                if estoque:
                    estoque.quantidade = quantidade
                else:
                    novo_estoque = SaldoTecnico(
                        tecnico_id=tecnico_id,
                        item_id=item.id,
                        tipo_servico_id=tipo_servico_id,
                        quantidade=quantidade
                    )
                    db.session.add(novo_estoque)

        db.session.commit()
        flash('Inventário registrado com sucesso.', 'success')
        return redirect(url_for('inventario_tecnico.historico_inventarios'))

    return render_template(
        'inventario_tecnico/novo.html',
        tecnicos=tecnicos,
        tipos_servico=tipos_servico,
        tecnico_id=tecnico_id,
        tipo_servico_id=tipo_servico_id,
        responsavel=responsavel,
        saldo_tecnico=saldo_tecnico
    )

# ========== HISTÓRICO ==========
@bp_inventario.route('/historico')
def historico_inventarios():
    inventarios = InventarioTecnico.query.order_by(InventarioTecnico.data.desc()).all()
    return render_template('inventario_tecnico/historico.html', inventarios=inventarios)

# ========== DETALHES ==========
@bp_inventario.route('/detalhes/<int:id>')
def detalhes_inventario(id):
    inventario = InventarioTecnico.query.get_or_404(id)
    return render_template('inventario_tecnico/detalhes.html', inventario=inventario)

# ========== EXPORTAR ==========
@bp_inventario.route('/exportar/<int:id>')
def exportar_inventario(id):
    inventario = InventarioTecnico.query.get_or_404(id)

    dados = []
    for item in inventario.itens:
        dados.append({
            'Código': item.item.codigo,
            'Descrição': item.item.descricao,
            'Quantidade Contada': item.quantidade_contada
        })

    df = pd.DataFrame(dados)
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Inventário', index=False)
        workbook = writer.book
        worksheet = writer.sheets['Inventário']
        rodape_format = workbook.add_format({'bold': True, 'bg_color': '#F2F2F2', 'border': 1})
        linha_final = len(df) + 3
        worksheet.write(linha_final, 0, f"Responsável: {inventario.responsavel or '---'}", rodape_format)
        worksheet.write(linha_final + 1, 0, f"Data: {inventario.data.strftime('%d/%m/%Y %H:%M')}", rodape_format)
        header_df = pd.DataFrame([{
            'Técnico': inventario.tecnico.nome,
            'Tipo de Serviço': inventario.tipo_servico.nome,
            'Data': inventario.data.strftime('%d/%m/%Y %H:%M'),
            'Responsável': inventario.responsavel or ''
        }])
        header_df.to_excel(writer, sheet_name='Cabeçalho', index=False)

    output.seek(0)
    nome_arquivo = f"inventario_tecnico_{inventario.tecnico.nome.replace(' ', '_')}.xlsx"
    return send_file(output, download_name=nome_arquivo, as_attachment=True)

# ========== FORMULÁRIO DE IMPRESSÃO ==========
@bp_inventario.route('/formulario/<int:id>')
def formulario_inventario(id):
    inventario = InventarioTecnico.query.get_or_404(id)
    return render_template('inventario_tecnico/formulario.html', inventario=inventario)
