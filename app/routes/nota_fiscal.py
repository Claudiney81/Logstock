from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app import db
from app.models import NotaFiscalEntrada, NotaFiscalItem, Item, Estoque, TipoServico
from datetime import datetime

bp = Blueprint('nota_fiscal', __name__, url_prefix='/nota')

# ------------------------
# Função auxiliar para converter valores BR
# ------------------------
def parse_valor_br(valor_str):
    """Converte valores brasileiros (1.234,56) em float corretamente"""
    valor_str = str(valor_str).replace('R$', '').strip()
    if ',' in valor_str:
        valor_str = valor_str.replace('.', '').replace(',', '.')
    return float(valor_str)

# ------------------------
# Nova Nota Fiscal
# ------------------------
@bp.route('/nova', methods=['GET', 'POST'])
def nova_nota():
    if request.method == 'POST':
        numero_nf = request.form['numero_nf']
        reserva = request.form['reserva']
        tipo_servico_id = request.form['tipo_servico_id']
        responsavel = request.form['responsavel']
        observacao = request.form['observacao']

        # Itens recebidos (listas)
        codigos = request.form.getlist('codigo[]')
        quantidades = request.form.getlist('quantidade[]')
        valores = request.form.getlist('valor[]')
        enderecos = request.form.getlist('endereco[]') if 'endereco[]' in request.form else [''] * len(codigos)

        # Verifica duplicidade da nota
        if NotaFiscalEntrada.query.filter_by(numero_nf=numero_nf).first():
            flash('Já existe uma nota fiscal com este número.', 'danger')
            return redirect(url_for('nota_fiscal.nova_nota'))

        tipo_servico_obj = TipoServico.query.get(tipo_servico_id)
        tipo_servico_nome = tipo_servico_obj.nome if tipo_servico_obj else ''

        # Cria registro da nota
        nova_nota = NotaFiscalEntrada(
            numero_nf=numero_nf,
            reserva=reserva,
            tipo_servico=tipo_servico_nome,
            responsavel=responsavel,
            observacao=observacao,
            data_hora=datetime.utcnow()
        )
        db.session.add(nova_nota)
        db.session.flush()

        # Adiciona itens na nota + atualiza estoque
        for codigo, qtd, val, endereco in zip(codigos, quantidades, valores, enderecos):
            item = Item.query.filter_by(codigo=codigo).first()
            if not item:
                continue

            try:
                valor_convertido = parse_valor_br(val)
            except:
                valor_convertido = 0.0

            # Cria item da nota
            nota_item = NotaFiscalItem(
                nota_fiscal_id=nova_nota.id,
                item_id=item.id,
                quantidade=int(qtd),
                valor_unitario=valor_convertido
            )
            db.session.add(nota_item)

            # Atualiza estoque vinculado ao tipo de serviço
            estoque = Estoque.query.filter_by(item_id=item.id, tipo_servico_id=tipo_servico_id).first()
            if estoque:
                estoque.quantidade += int(qtd)
                if endereco.strip():
                    estoque.endereco = endereco.strip()
            else:
                novo_estoque = Estoque(
                    item_id=item.id,
                    quantidade=int(qtd),
                    quantidade_minima=0,
                    endereco=endereco.strip(),
                    tipo_servico_id=tipo_servico_id
                )
                db.session.add(novo_estoque)

        db.session.commit()
        flash('Nota fiscal registrada com sucesso! ✅ Saldo atualizado.', 'success')
        return redirect(url_for('nota_fiscal.historico'))

    itens = Item.query.all()
    tipos_servico = TipoServico.query.all()
    return render_template('nota_fiscal/nova.html', itens=itens, tipos_servico=tipos_servico)

# ------------------------
# Histórico
# ------------------------
@bp.route('/historico')
def historico():
    tipo_servico_id = request.args.get('tipo_servico', type=int)
    query = NotaFiscalEntrada.query
    tipo_servico_nome = None

    if tipo_servico_id:
        ts = TipoServico.query.get(tipo_servico_id)
        if ts:
            tipo_servico_nome = ts.nome
            query = query.filter(NotaFiscalEntrada.tipo_servico == ts.nome)

    notas = query.order_by(NotaFiscalEntrada.data_hora.desc()).all()
    tipos_servico = TipoServico.query.all()

    return render_template(
        'nota_fiscal/historico.html',
        notas=notas,
        tipos_servico=tipos_servico,
        tipo_servico_id=tipo_servico_id,
        tipo_servico_nome=tipo_servico_nome
    )

# ------------------------
# Detalhes
# ------------------------
@bp.route('/<int:id>')
def detalhes(id):
    nota = NotaFiscalEntrada.query.get_or_404(id)
    itens = NotaFiscalItem.query.filter_by(nota_fiscal_id=nota.id).all()

    # Calcula o total da nota
    total_nota = sum(item.quantidade * item.valor_unitario for item in itens)

    return render_template(
        'nota_fiscal/detalhes.html',
        nota=nota,
        itens=itens,
        total_nota=total_nota
    )

# ------------------------
# Pesquisar Nota Fiscal
# ------------------------
@bp.route('/pesquisar', methods=['GET'])
def pesquisar():
    termo = request.args.get('query', '').strip()
    query = NotaFiscalEntrada.query
    if termo:
        query = query.filter(
            (NotaFiscalEntrada.numero_nf.ilike(f'%{termo}%')) |
            (NotaFiscalEntrada.reserva.ilike(f'%{termo}%'))
        )
    notas = query.order_by(NotaFiscalEntrada.data_hora.desc()).all()

    # --- Monta uma lista com totais sem alterar a propriedade ---
    notas_com_totais = []
    for nota in notas:
        itens = NotaFiscalItem.query.filter_by(nota_fiscal_id=nota.id).all()
        total_nota = sum(i.quantidade * i.valor_unitario for i in itens)
        notas_com_totais.append({
            'nota': nota,
            'total_nota': total_nota
        })

    return render_template('nota_fiscal/pesquisar.html',
                           notas=notas_com_totais,
                           termo=termo)

# ------------------------
# API: Buscar Item
# ------------------------
@bp.route('/api/item/<codigo>')
def api_buscar_item(codigo):
    item = Item.query.filter_by(codigo=codigo).first()
    if item:
        return jsonify({
            'success': True,
            'descricao': item.descricao,
            'valor': item.valor
        })
    return jsonify({'success': False})

# ------------------------
# API: Buscar responsável do projeto
# ------------------------
@bp.route('/api/responsavel/<int:tipo_servico_id>')
def api_responsavel(tipo_servico_id):
    tipo = TipoServico.query.get(tipo_servico_id)
    return jsonify({'responsavel': tipo.responsavel if tipo and tipo.responsavel else ''})

# ------------------------
# Excluir Nota Fiscal
# ------------------------
@bp.route('/excluir/<int:id>', methods=['POST'])
def excluir_nota(id):
    nota = NotaFiscalEntrada.query.get_or_404(id)

    # Exclui todos os itens vinculados à nota
    itens = NotaFiscalItem.query.filter_by(nota_fiscal_id=nota.id).all()
    for item in itens:
        db.session.delete(item)

    # Exclui a nota em si
    db.session.delete(nota)
    db.session.commit()

    flash('Nota fiscal excluída com sucesso!', 'success')
    return redirect(url_for('nota_fiscal.historico'))

# ------------------------
# API: Listar todos os itens cadastrados
# ------------------------
@bp.route('/api/itens')
def api_itens():
    itens = Item.query.all()
    return jsonify([
        {
            'codigo': item.codigo,
            'descricao': item.descricao,
            'valor': item.valor
        } for item in itens
    ])
