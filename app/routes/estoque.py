from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app import db
from app.models import Item, Estoque, TipoServico
import pandas as pd
from flask_login import login_required

bp = Blueprint('estoque', __name__, url_prefix='/estoque')

# ------------------------
# Cadastro de Item Manual
# ------------------------
@bp.route('/cadastro', methods=['GET', 'POST'])
@login_required
def cadastrar_item():
    if request.method == 'POST':
        codigo = request.form['codigo']
        descricao = request.form['descricao']
        unidade = request.form['unidade']
        valor_str = request.form['valor'].replace('.', '').replace(',', '.')
        valor = float(valor_str)
        eh_equipamento = True if request.form.get('eh_equipamento') else False  # NOVO

        # Verifica duplicidade
        if Item.query.filter_by(codigo=codigo).first():
            flash('Já existe um item com este código.', 'warning')
            return redirect(url_for('estoque.cadastrar_item'))

        novo_item = Item(
            codigo=codigo,
            descricao=descricao,
            unidade=unidade,
            valor=valor,
            eh_equipamento=eh_equipamento  # NOVO
        )
        db.session.add(novo_item)
        db.session.commit()
        flash('Item cadastrado com sucesso!', 'success')
        return redirect(url_for('estoque.cadastrar_item'))

    return render_template('estoque/cadastro.html')

# ------------------------
# Listar Itens
# ------------------------
@bp.route('/listar', methods=['GET'])
@login_required
def listar_itens():
    codigo = request.args.get('codigo', '').strip()
    descricao = request.args.get('descricao', '').strip()

    query = Item.query
    if codigo:
        query = query.filter(Item.codigo.ilike(f'%{codigo}%'))
    if descricao:
        query = query.filter(Item.descricao.ilike(f'%{descricao}%'))

    itens = query.all()
    return render_template('estoque/listar.html', itens=itens, codigo=codigo, descricao=descricao)

# ------------------------
# Importar Itens via Excel (robusto e rápido)
# ------------------------
@bp.route('/importar', methods=['POST'])
@login_required
def importar_itens():
    arquivo = request.files.get('arquivo')
    if not arquivo:
        flash('Nenhum arquivo selecionado.', 'danger')
        return redirect(url_for('estoque.cadastrar_item'))

    try:
        # 1) Ler tudo como string para preservar zeros à esquerda
        df = pd.read_excel(arquivo, dtype=str)

        # 2) Normalizar nomes de colunas (aceita variações)
        colmap = {
            'codigo': 'Código', 'código': 'Código', 'cod': 'Código',
            'descrição': 'Descrição', 'descricao': 'Descrição', 'descriçao': 'Descrição',
            'un': 'Unidade', 'unidade': 'Unidade',
            'valor (r$)': 'Valor', 'valor r$': 'Valor', 'valor': 'Valor', 'preço': 'Valor', 'preco': 'Valor'
        }
        df.columns = [c.strip() for c in df.columns]
        lower_to_real = {c.lower(): c for c in df.columns}
        for k, std in colmap.items():
            if k in lower_to_real:
                df.rename(columns={lower_to_real[k]: std}, inplace=True)

        # 3) Garantir colunas obrigatórias
        obrig = ['Código', 'Descrição', 'Unidade', 'Valor']
        for c in obrig:
            if c not in df.columns:
                df[c] = ''

        # 4) Limpeza
        df = df[obrig].copy().fillna('')
        for c in obrig:
            df[c] = df[c].astype(str).str.strip()

        # 5) Valor BR -> float
        def parse_val(v: str) -> float:
            v = (v or '').strip()
            if not v:
                return 0.0
            v = v.replace('.', '').replace(',', '.')
            try:
                return float(v)
            except ValueError:
                return 0.0

        df['valor_float'] = df['Valor'].apply(parse_val)

        # 6) Linhas válidas e tirar duplicados no próprio arquivo
        df = df[(df['Código'] != '') & (df['Descrição'] != '')]
        df = df.drop_duplicates(subset=['Código'], keep='first')

        # 7) Buscar códigos já existentes EM LOTES (evita limite do SQLite)
        codigos = df['Código'].tolist()

        def fetch_existentes_em_lotes(lista, step=900):
            existentes = set()
            for i in range(0, len(lista), step):
                chunk = lista[i:i+step]
                rows = db.session.query(Item.codigo).filter(Item.codigo.in_(chunk)).all()
                existentes.update(c for (c,) in rows)
            return existentes

        existentes = fetch_existentes_em_lotes(codigos)

        # 8) Preparar inserções novas (com fallback de Unidade = 'Un')
        novos = []
        sem_unidade = 0
        ignorados_dup = 0

        for _, row in df.iterrows():
            codigo = row['Código']
            if codigo in existentes:
                ignorados_dup += 1
                continue

            unidade = row['Unidade'] or 'Un'
            if not row['Unidade']:
                sem_unidade += 1

            novos.append(Item(
                codigo=codigo,
                descricao=row['Descrição'],
                unidade=unidade,
                valor=row['valor_float'],
                eh_equipamento=False
            ))

        # 9) Persistir em lote (rápido)
        if novos:
            step = 1000
            for i in range(0, len(novos), step):
                db.session.bulk_save_objects(novos[i:i+step])
            db.session.commit()

        flash(
            f'Importação concluída. Linhas lidas: {len(df)}. '
            f'Criadas: {len(novos)}. Duplicadas ignoradas: {ignorados_dup}. '
            f'Linhas sem Unidade (usado "Un"): {sem_unidade}.',
            'success'
        )

    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao importar itens: {e}', 'danger')

    return redirect(url_for('estoque.cadastrar_item'))

# ------------------------
# Saldo de Estoque (corrigido)
# ------------------------
@bp.route('/saldo', methods=['GET'])
@login_required
def saldo_estoque():
    codigo = request.args.get('codigo', '').strip()
    descricao = request.args.get('descricao', '').strip()
    tipo_servico_id = request.args.get('tipo_servico', type=int)

    tipos_servico = TipoServico.query.all()

    # Agora retorna apenas Estoque e Item
    query = db.session.query(Estoque, Item).join(Item, Estoque.item_id == Item.id)

    if codigo:
        query = query.filter(Item.codigo.ilike(f'%{codigo}%'))
    if descricao:
        query = query.filter(Item.descricao.ilike(f'%{descricao}%'))
    if tipo_servico_id and tipo_servico_id > 0:
        query = query.filter(Estoque.tipo_servico_id == tipo_servico_id)

    resultados = query.all()

    responsavel = None
    if tipo_servico_id:
        ts = TipoServico.query.get(tipo_servico_id)
        responsavel = getattr(ts, "responsavel", None)

    return render_template(
        'estoque/saldo.html',
        resultados=resultados,
        tipos_servico=tipos_servico,
        tipo_servico=tipo_servico_id,
        responsavel=responsavel,
        codigo=codigo,
        descricao=descricao
    )

# ------------------------
# Alertas de Estoque
# ------------------------
@bp.route('/alertas')
@login_required
def alerta_estoque_baixo():
    query = db.session.query(Estoque, Item).join(Item, Estoque.item_id == Item.id)
    resultados = query.all()

    alertas = []
    for estoque, item in resultados:
        # Se tiver estoque mínimo definido pelo usuário
        if estoque.quantidade_minima is not None and estoque.quantidade <= estoque.quantidade_minima:
            alertas.append((estoque, item))

    return render_template('estoque/alertas.html', resultados=alertas)

# ------------------------
# API: Estoque
# ------------------------
@bp.route('/api/estoque_saldo')
@login_required
def api_estoque_saldo():
    query = db.session.query(Estoque, Item).join(Item, Estoque.item_id == Item.id)
    resultados = [{
        'codigo': item.codigo,
        'descricao': item.descricao,
        'unidade': item.unidade,
        'tipo_servico': estoque.tipo_servico.nome if estoque.tipo_servico else None,
        'responsavel': estoque.tipo_servico.responsavel if estoque.tipo_servico else None,
        'quantidade': estoque.quantidade,
        'valor': item.valor,
        'endereco': estoque.endereco
    } for estoque, item in query.all()]
    return jsonify(resultados)

# ------------------------
# Atualização de Estoque Mínimo
# ------------------------
@bp.route('/atualizar_minimos', methods=['POST'])
@login_required
def atualizar_minimos():
    for key in request.form:
        if key.startswith("minimos["):
            estoque_id = key[8:-1]
            valor_digitado = request.form[key].strip()
            try:
                estoque = Estoque.query.get(int(estoque_id))
                if not estoque:
                    continue
                if valor_digitado.endswith('%'):
                    percentual = int(valor_digitado.replace('%', '').strip())
                    estoque.quantidade_minima = round((percentual / 100) * estoque.quantidade)
                else:
                    estoque.quantidade_minima = int(valor_digitado)
            except (ValueError, TypeError):
                continue

    db.session.commit()
    flash('Estoque mínimo atualizado com sucesso!', 'success')
    return redirect(url_for('estoque.saldo_estoque'))

# ------------------------
# Atualização de Endereços
# ------------------------
@bp.route('/atualizar_enderecos', methods=['POST'])
@login_required
def atualizar_enderecos():
    for key in request.form:
        if key.startswith("enderecos["):
            estoque_id = key[10:-1]
            endereco_digitado = request.form[key].strip()
            try:
                estoque = Estoque.query.get(int(estoque_id))
                if not estoque:
                    continue
                estoque.endereco = endereco_digitado
            except Exception:
                continue

    db.session.commit()
    flash('Endereços atualizados com sucesso!', 'success')
    return redirect(url_for('estoque.saldo_estoque'))
