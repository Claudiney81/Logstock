from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from datetime import datetime
from io import BytesIO
from sqlalchemy import func, or_

from app.extensions import db
from app.utils.mailer import send_movimentacao_email, _build_movimentacao_pdf

from app.models import (
    MovimentacaoEstoque,
    MovimentacaoEstoqueItem,
    Tecnico,
    Empresa,
    TipoServico,
    Item,
    Estoque,
    SaldoTecnico
)

bp_movimentacao = Blueprint(
    'movimentacao_estoque',
    __name__,
    url_prefix='/movimentacao_estoque'
)


# ==================================================
# CONDIÇÃO DO MATERIAL
# ==================================================
CONDICOES_MATERIAL = {
    'USADO_BOM',
    'NOVO_DEF',
    'USADO_DEF'
}


def _normalizar_condicao_material(valor):
    valor = (valor or '').strip().upper()

    if valor in CONDICOES_MATERIAL:
        return valor

    return None


def _estoque_tem_condicao():
    return hasattr(Estoque, 'condicao_material')


def _filtro_condicao_estoque(query, condicao):
    """
    Aplica filtro de condição somente se a coluna já existir no model.
    condicao None significa estoque comum/disponível.
    """
    if not _estoque_tem_condicao():
        return query

    if condicao:
        return query.filter(Estoque.condicao_material == condicao)

    return query.filter(
        or_(
            Estoque.condicao_material.is_(None),
            Estoque.condicao_material == ''
        )
    )


def _atribuir_condicao_estoque(estoque, condicao):
    if _estoque_tem_condicao():
        estoque.condicao_material = condicao


def _buscar_ou_criar_estoque_empresa(item_id, tipo_servico_id, condicao):
    query = Estoque.query.filter_by(
        item_id=item_id,
        tipo_servico_id=tipo_servico_id,
        tipo_estoque='empresa'
    )

    query = _filtro_condicao_estoque(query, condicao)

    estoque = query.first()

    if estoque:
        return estoque

    estoque = Estoque(
        item_id=item_id,
        tipo_servico_id=tipo_servico_id,
        tipo_estoque='empresa',
        quantidade=0,
        quantidade_minima=0
    )

    _atribuir_condicao_estoque(estoque, condicao)

    db.session.add(estoque)
    db.session.flush()

    return estoque


def _consumir_estoque_empresa(item_id, tipo_servico_id, quantidade):
    """
    Saída Empresa -> Técnico.
    Consome primeiro estoque comum e depois Usado Bom, se existir.
    Não consome materiais classificados como defeito.
    """
    query = Estoque.query.filter(
        Estoque.item_id == item_id,
        Estoque.tipo_servico_id == tipo_servico_id,
        Estoque.tipo_estoque == 'empresa',
        Estoque.quantidade > 0
    )

    if _estoque_tem_condicao():
        query = query.filter(
            or_(
                Estoque.condicao_material.is_(None),
                Estoque.condicao_material == '',
                Estoque.condicao_material == 'USADO_BOM'
            )
        )

    registros = query.order_by(Estoque.id.asc()).all()

    saldo_total = sum(int(e.quantidade or 0) for e in registros)

    if saldo_total < quantidade:
        return False

    restante = int(quantidade)

    for estoque in registros:
        if restante <= 0:
            break

        saldo = int(estoque.quantidade or 0)
        baixa = min(saldo, restante)
        estoque.quantidade = saldo - baixa
        restante -= baixa

    return True


def _consumir_saldo_tecnico(
    tecnico_id,
    item_id,
    tipo_servico_id,
    quantidade,
    saldo_tecnico_tipo='empresa',
    cliente_id=None,
    ordem_servico_id=None
):
    """
    Devolução Técnico -> Empresa.
    Consome saldo do técnico por tipo empresa ou cliente.
    Para cliente, cliente/O.S são filtros opcionais.
    """
    query = SaldoTecnico.query.filter(
        SaldoTecnico.tecnico_id == tecnico_id,
        SaldoTecnico.item_id == item_id,
        SaldoTecnico.tipo_servico_id == tipo_servico_id,
        SaldoTecnico.tipo_estoque == saldo_tecnico_tipo,
        SaldoTecnico.quantidade > 0
    )

    if saldo_tecnico_tipo == 'empresa':
        query = query.filter(
            SaldoTecnico.cliente_id.is_(None),
            SaldoTecnico.ordem_servico_id.is_(None)
        )
    else:
        if cliente_id:
            query = query.filter(SaldoTecnico.cliente_id == cliente_id)

        if ordem_servico_id:
            query = query.filter(SaldoTecnico.ordem_servico_id == ordem_servico_id)

    registros = query.order_by(SaldoTecnico.id.asc()).all()

    saldo_total = sum(int(s.quantidade or 0) for s in registros)

    if saldo_total < quantidade:
        return False

    restante = int(quantidade)

    for saldo in registros:
        if restante <= 0:
            break

        saldo_atual = int(saldo.quantidade or 0)
        baixa = min(saldo_atual, restante)
        saldo.quantidade = saldo_atual - baixa
        restante -= baixa

    return True


@bp_movimentacao.route('/nova', methods=['GET', 'POST'])
@login_required
def nova_movimentacao():

    tecnicos = Tecnico.query.order_by(Tecnico.nome).all()
    tipos_servico = TipoServico.query.order_by(TipoServico.nome).all()

    from sqlalchemy import inspect

    colunas_empresa = [c.name for c in inspect(Empresa).columns]

    campo_tipo = None

    for campo in ['tipo_empresa', 'tipo_cadastro', 'categoria', 'classificacao', 'tipo']:
        if campo in colunas_empresa:
            campo_tipo = campo
            break

    if campo_tipo:
        empresas = Empresa.query.filter(
            getattr(Empresa, campo_tipo).ilike('%cliente%')
        ).order_by(Empresa.razao_social).all()
    else:
        empresas = Empresa.query.order_by(Empresa.razao_social).all()

    if request.method == 'POST':

        categoria_movimentacao = request.form.get(
            'categoria_movimentacao',
            'MATERIAL'
        ).strip().upper()

        if categoria_movimentacao not in ['MATERIAL', 'PATRIMONIO']:
            categoria_movimentacao = 'MATERIAL'

        origem_tipo = request.form.get('origem_tipo')
        destino_tipo = request.form.get('destino_tipo')

        tipo_movimentacao = request.form.get('tipo_movimentacao')
        motivo_retorno = request.form.get('motivo_retorno')
        assinatura = request.form.get('assinatura')

        saldo_tecnico_tipo = (
            request.form.get('saldo_tecnico_tipo') or 'empresa'
        ).strip().lower()

        if saldo_tecnico_tipo not in ['empresa', 'cliente']:
            saldo_tecnico_tipo = 'empresa'

        condicao_material = _normalizar_condicao_material(
            request.form.get('condicao_material')
        )

        tecnico_id = (
            request.form.get('tecnico_id')
            or request.form.get('tecnico_destino_id')
            or request.form.get('tecnico_origem_id')
        )

        cliente_os_id = (
            request.form.get('cliente_movimentacao_id')
            or request.form.get('cliente_os_id')
            or request.form.get('cliente_id')
        )

        cliente_os_id = cliente_os_id or None

        tipo_servico_id = request.form.get('tipo_servico_id')

        # ==================================================
        # ESTOQUE CENTRALIZADO EM INSTALAÇÃO
        # ==================================================
        tipo_servico_saldo = int(tipo_servico_id) if tipo_servico_id else None

        if tipo_servico_saldo and tipo_servico_saldo != 1:
            tipo_servico_saldo = 1

        observacao = request.form.get('observacao')

        ordem_servico_id = request.form.get(
            'ordem_servico_id',
            type=int
        )

        endereco_os = request.form.get(
            'endereco',
            ''
        ).strip()

        bairro_os = request.form.get(
            'bairro',
            ''
        ).strip()

        codigo_imovel_os = request.form.get(
            'codigo_imovel',
            ''
        ).strip()

        codigos = request.form.getlist('codigo[]')
        descricoes = request.form.getlist('descricao[]')
        quantidades = request.form.getlist('quantidade[]')
        valores = request.form.getlist('valor_unitario[]')
        minimos = request.form.getlist('quantidade_minima[]')

        if not any(codigos) and any(descricoes):
            codigos = descricoes

        if not origem_tipo:
            flash('Selecione a origem.', 'danger')
            return redirect(url_for('movimentacao_estoque.nova_movimentacao'))

        if not destino_tipo:
            flash('Selecione o destino.', 'danger')
            return redirect(url_for('movimentacao_estoque.nova_movimentacao'))

        if origem_tipo == destino_tipo:
            flash('Origem e destino não podem ser iguais.', 'danger')
            return redirect(url_for('movimentacao_estoque.nova_movimentacao'))

        # ==================================================
        # REGRAS MATERIAL
        # ==================================================
        if categoria_movimentacao == 'MATERIAL':

            tipo_movimentacao = None
            motivo_retorno = None

            if not tipo_servico_id:
                flash('Selecione o tipo de serviço.', 'danger')
                return redirect(url_for('movimentacao_estoque.nova_movimentacao'))

            if origem_tipo == 'empresa' and destino_tipo != 'tecnico':
                flash('Quando a origem for Empresa, o destino deve ser Técnico.', 'danger')
                return redirect(url_for('movimentacao_estoque.nova_movimentacao'))

            if origem_tipo == 'cliente' and destino_tipo != 'tecnico':
                flash('Quando a origem for Cliente, o destino deve ser Técnico.', 'danger')
                return redirect(url_for('movimentacao_estoque.nova_movimentacao'))

            if origem_tipo == 'tecnico' and destino_tipo != 'empresa':
                flash('Quando a origem for Técnico, o destino deve ser Empresa.', 'danger')
                return redirect(url_for('movimentacao_estoque.nova_movimentacao'))

            if destino_tipo == 'tecnico' and not tecnico_id:
                flash('Selecione o técnico que receberá o material.', 'danger')
                return redirect(url_for('movimentacao_estoque.nova_movimentacao'))

            if origem_tipo == 'tecnico' and not tecnico_id:
                flash('Selecione o técnico que fará a devolução.', 'danger')
                return redirect(url_for('movimentacao_estoque.nova_movimentacao'))

            if origem_tipo == 'cliente' and destino_tipo == 'tecnico' and not cliente_os_id:
                flash('Selecione o Cliente O.S.', 'danger')
                return redirect(url_for('movimentacao_estoque.nova_movimentacao'))

        # ==================================================
        # REGRAS FERRAMENTAS / EPIs
        # ==================================================
        else:
            tipo_servico_id = None
            cliente_os_id = None
            saldo_tecnico_tipo = 'empresa'
            condicao_material = None

            if origem_tipo not in ['empresa', 'tecnico']:
                flash('Para Ferramentas/EPIs, a origem deve ser Empresa ou Técnico.', 'danger')
                return redirect(url_for('movimentacao_estoque.nova_movimentacao'))

            if destino_tipo not in ['empresa', 'tecnico']:
                flash('Para Ferramentas/EPIs, o destino deve ser Empresa ou Técnico.', 'danger')
                return redirect(url_for('movimentacao_estoque.nova_movimentacao'))

            if origem_tipo == 'empresa' and destino_tipo != 'tecnico':
                flash('Para saída de Ferramenta/EPI, o destino deve ser Técnico.', 'danger')
                return redirect(url_for('movimentacao_estoque.nova_movimentacao'))

            if origem_tipo == 'tecnico' and destino_tipo != 'empresa':
                flash('Para retorno de Ferramenta/EPI, o destino deve ser Empresa.', 'danger')
                return redirect(url_for('movimentacao_estoque.nova_movimentacao'))

            if not tecnico_id:
                flash('Selecione o técnico.', 'danger')
                return redirect(url_for('movimentacao_estoque.nova_movimentacao'))

            if origem_tipo == 'empresa' and destino_tipo == 'tecnico':
                tipo_movimentacao = 'saida'
                motivo_retorno = None

            elif origem_tipo == 'tecnico' and destino_tipo == 'empresa':
                tipo_movimentacao = 'retorno'

                if not motivo_retorno:
                    flash('Selecione o motivo do retorno.', 'danger')
                    return redirect(url_for('movimentacao_estoque.nova_movimentacao'))

                if motivo_retorno not in ['devolucao', 'troca', 'extravio', 'perda', 'desgaste']:
                    flash('Motivo de retorno inválido.', 'danger')
                    return redirect(url_for('movimentacao_estoque.nova_movimentacao'))

            if not assinatura:
                flash('A assinatura é obrigatória para movimentação de Ferramentas/EPIs.', 'danger')
                return redirect(url_for('movimentacao_estoque.nova_movimentacao'))

        # ==================================================
        # DEFINIR ORIGEM / DESTINO
        # ==================================================

        if origem_tipo == 'empresa':
            origem_id = int(cliente_os_id) if cliente_os_id else 0

        elif origem_tipo == 'cliente':
            origem_id = int(cliente_os_id) if cliente_os_id else None

        elif origem_tipo == 'tecnico':
            origem_id = int(tecnico_id) if tecnico_id else None

        else:
            flash('Origem inválida.', 'danger')
            return redirect(url_for('movimentacao_estoque.nova_movimentacao'))

        if destino_tipo == 'empresa':
            destino_id = 0

        elif destino_tipo == 'tecnico':
            destino_id = int(tecnico_id) if tecnico_id else None

        else:
            flash('Destino inválido.', 'danger')
            return redirect(url_for('movimentacao_estoque.nova_movimentacao'))

        # ==================================================
        # CRIAR MOVIMENTAÇÃO
        # ==================================================

        nova_mov = MovimentacaoEstoque(
            origem_tipo=origem_tipo,
            origem_id=origem_id,

            destino_tipo=destino_tipo,
            destino_id=destino_id,

            tipo_servico_id=tipo_servico_id,

            ordem_servico_id=ordem_servico_id if ordem_servico_id else None,

            observacao=observacao,
            usuario_id=current_user.id,
            data_hora=datetime.utcnow(),

            categoria_movimentacao=categoria_movimentacao,
            tipo_movimentacao=tipo_movimentacao,
            motivo_retorno=motivo_retorno,

            assinatura=assinatura,

            assinado_por=(
                'tecnico'
                if tipo_movimentacao == 'saida'
                else 'logistica'
                if tipo_movimentacao == 'retorno'
                else None
            ),

            termo_pdf=None,
            email_enviado=False
        )

        db.session.add(nova_mov)
        db.session.flush()

        sucesso = False

        # ==================================================
        # PROCESSAR ITENS
        # ==================================================

        codigos_processados = set()

        for i in range(len(codigos)):

            codigo = codigos[i].strip() if codigos[i] else ''

            if codigo in codigos_processados:
                continue

            codigos_processados.add(codigo)

            if not codigo:
                continue

            try:
                quantidade = int(quantidades[i])
            except Exception:
                continue

            if quantidade <= 0:
                continue

            item = Item.query.filter_by(codigo=codigo).first()

            if not item:
                flash(f'Item {codigo} não encontrado.', 'danger')
                continue

            item_categoria = (item.categoria or 'MATERIAL').strip().upper()

            if categoria_movimentacao == 'PATRIMONIO':
                if item_categoria not in ['FERRAMENTA', 'EPI']:
                    flash(f'O item {item.codigo} não é Ferramenta/EPI.', 'danger')
                    continue
            else:
                if item_categoria in ['FERRAMENTA', 'EPI']:
                    flash(f'O item {item.codigo} é Ferramenta/EPI. Use Ferramentas & EPIs.', 'danger')
                    continue

            try:
                valor_unitario = float(str(valores[i]).replace(',', '.')) if valores[i] else 0
            except Exception:
                valor_unitario = 0

            try:
                quantidade_minima = int(minimos[i]) if minimos[i] else 0
            except Exception:
                quantidade_minima = 0

            # ==================================================
            # 1 - SAÍDA DA ORIGEM
            # ==================================================

            if origem_tipo == 'empresa':

                if not _consumir_estoque_empresa(
                    item_id=item.id,
                    tipo_servico_id=tipo_servico_saldo,
                    quantidade=quantidade
                ):
                    flash(f'Saldo insuficiente na empresa para o item {item.codigo}.', 'danger')
                    continue

            elif origem_tipo == 'cliente':

                estoque_origem = Estoque.query.filter_by(
                    item_id=item.id,
                    tipo_servico_id=tipo_servico_id,
                    tipo_estoque='cliente',
                    cliente_id=int(cliente_os_id) if cliente_os_id else None
                ).first()

                if not estoque_origem:
                    flash(f'Item {item.codigo} sem saldo no estoque do Cliente.', 'danger')
                    continue

                if int(estoque_origem.quantidade or 0) < int(quantidade or 0):
                    flash(f'Saldo insuficiente no Cliente para o item {item.codigo}.', 'danger')
                    continue

                estoque_origem.quantidade = int(estoque_origem.quantidade or 0) - int(quantidade or 0)

            elif origem_tipo == 'tecnico':

                if not _consumir_saldo_tecnico(
                    tecnico_id=int(tecnico_id),
                    item_id=item.id,
                    tipo_servico_id=tipo_servico_saldo,
                    quantidade=quantidade,
                    saldo_tecnico_tipo=saldo_tecnico_tipo,
                    cliente_id=int(cliente_os_id) if cliente_os_id else None,
                    ordem_servico_id=ordem_servico_id
                ):
                    flash(f'Saldo insuficiente do técnico para o item {item.codigo}.', 'danger')
                    continue

            # ==================================================
            # 2 - REGISTRAR ITEM DA MOVIMENTAÇÃO
            # ==================================================

            item_mov = MovimentacaoEstoqueItem(
                movimentacao_id=nova_mov.id,
                item_id=item.id,
                quantidade=quantidade,
                valor_unitario=valor_unitario,
                condicao_material=(
                    condicao_material
                    if origem_tipo == 'tecnico'
                    and destino_tipo == 'empresa'
                    else None
                )
            )

            db.session.add(item_mov)

            # ==================================================
            # 3 - ENTRADA NO DESTINO
            # ==================================================

            if destino_tipo == 'tecnico':

                if origem_tipo == 'empresa':

                    tipo_estoque_destino = 'empresa'
                    cliente_destino_id = None
                    ordem_servico_destino_id = None
                    endereco_destino = ""
                    bairro_destino = ""
                    codigo_imovel_destino = ""
                    tipo_servico_destino = tipo_servico_saldo

                elif origem_tipo == 'cliente':

                    tipo_estoque_destino = 'cliente'
                    cliente_destino_id = int(cliente_os_id) if cliente_os_id else None
                    ordem_servico_destino_id = ordem_servico_id
                    endereco_destino = endereco_os
                    bairro_destino = bairro_os
                    codigo_imovel_destino = codigo_imovel_os
                    tipo_servico_destino = int(tipo_servico_id)

                else:

                    tipo_estoque_destino = 'empresa'
                    cliente_destino_id = None
                    ordem_servico_destino_id = None
                    endereco_destino = ""
                    bairro_destino = ""
                    codigo_imovel_destino = ""
                    tipo_servico_destino = tipo_servico_saldo

                saldo_destino = SaldoTecnico.query.filter_by(
                    tecnico_id=int(tecnico_id),
                    item_id=item.id,
                    tipo_servico_id=tipo_servico_destino,
                    tipo_estoque=tipo_estoque_destino,
                    cliente_id=cliente_destino_id,
                    ordem_servico_id=ordem_servico_destino_id
                ).first()

                if saldo_destino:
                    saldo_destino.quantidade += quantidade
                    saldo_destino.quantidade_minima = (
                        quantidade_minima
                        if origem_tipo == 'empresa'
                        else saldo_destino.quantidade_minima
                    )
                    saldo_destino.endereco = endereco_destino
                    saldo_destino.bairro = bairro_destino
                    saldo_destino.codigo_imovel = codigo_imovel_destino

                else:
                    novo_saldo = SaldoTecnico(
                        tecnico_id=int(tecnico_id),
                        item_id=item.id,
                        tipo_servico_id=tipo_servico_destino,
                        quantidade=quantidade,
                        quantidade_minima=quantidade_minima if origem_tipo == 'empresa' else 0,
                        tipo_estoque=tipo_estoque_destino,
                        cliente_id=cliente_destino_id,
                        ordem_servico_id=ordem_servico_destino_id,
                        endereco=endereco_destino,
                        bairro=bairro_destino,
                        codigo_imovel=codigo_imovel_destino
                    )

                    db.session.add(novo_saldo)

            elif destino_tipo == 'empresa':

                volta_para_estoque = True

                if categoria_movimentacao == 'PATRIMONIO':
                    volta_para_estoque = motivo_retorno == 'devolucao'

                if volta_para_estoque:

                    estoque_destino = _buscar_ou_criar_estoque_empresa(
                        item_id=item.id,
                        tipo_servico_id=tipo_servico_saldo,
                        condicao=condicao_material
                    )

                    estoque_destino.quantidade = int(estoque_destino.quantidade or 0) + int(quantidade or 0)

            sucesso = True

        # ==================================================
        # FINALIZAÇÃO
        # ==================================================

        if not sucesso:
            db.session.rollback()
            flash('Nenhum item movimentado.', 'danger')
            return redirect(url_for('movimentacao_estoque.nova_movimentacao'))

        # ==================================================
        # ATUALIZA STATUS DA O.S SOMENTE MATERIAL
        # ==================================================

        if categoria_movimentacao == 'MATERIAL' and cliente_os_id:

            cliente_os = Empresa.query.get(cliente_os_id)

            if cliente_os:
                cliente_os.status_os = 'em_andamento'

        db.session.commit()

        try:
            enviado = send_movimentacao_email(
                nova_mov,
                attach_pdf=True
            )

            if enviado:
                nova_mov.email_enviado = True
                db.session.commit()

        except Exception as e:
            print(f'Erro ao enviar e-mail da movimentação: {e}')

        if categoria_movimentacao == 'PATRIMONIO':
            flash('Movimentação registrada e enviada ao e-mail do técnico.', 'success')
        else:
            flash('Movimentação realizada e enviada ao e-mail do técnico.', 'success')

        return redirect(
            url_for('movimentacao_estoque.historico')
        )

    return render_template(
        'movimentacao_estoque/nova.html',
        tecnicos=tecnicos,
        empresas=empresas,
        tipos_servico=tipos_servico
    )


@bp_movimentacao.route('/historico')
@login_required
def historico():

    movimentacoes = MovimentacaoEstoque.query.order_by(
        MovimentacaoEstoque.data_hora.desc()
    ).all()

    tecnicos = Tecnico.query.all()
    empresas = Empresa.query.all()

    tecnicos_dict = {
        t.id: t.nome
        for t in tecnicos
    }

    empresas_dict = {
        e.id: e.razao_social
        for e in empresas
    }

    for m in movimentacoes:

        condicoes = [
            item.condicao_material
            for item in m.itens
            if item.condicao_material
        ]

        if not condicoes:
            m.condicao_material_resumo = None

        elif len(set(condicoes)) == 1:
            m.condicao_material_resumo = condicoes[0]

        else:
            m.condicao_material_resumo = "MISTO"

    return render_template(
        'movimentacao_estoque/historico.html',
        movimentacoes=movimentacoes,
        tecnicos_dict=tecnicos_dict,
        empresas_dict=empresas_dict
    )


@bp_movimentacao.route('/detalhes/<int:id>')
@login_required
def detalhes(id):

    movimentacao = MovimentacaoEstoque.query.get_or_404(id)

    itens = (
        MovimentacaoEstoqueItem.query
        .filter(
            MovimentacaoEstoqueItem.movimentacao_id == id
        )
        .all()
    )

    tecnicos = Tecnico.query.all()
    empresas = Empresa.query.all()

    tecnicos_dict = {
        t.id: t.nome
        for t in tecnicos
    }

    empresas_dict = {
        e.id: e.razao_social
        for e in empresas
    }

    return render_template(
        'movimentacao_estoque/detalhes.html',
        movimentacao=movimentacao,
        itens=itens,
        tecnicos_dict=tecnicos_dict,
        empresas_dict=empresas_dict
    )


@bp_movimentacao.route('/api/itens')
@login_required
def api_itens_movimentacao():

    origem_tipo = request.args.get('origem_tipo')
    tipo_servico_id = request.args.get('tipo_servico_id', type=int)

    tipo_servico_consulta = tipo_servico_id
    if tipo_servico_consulta and tipo_servico_consulta != 1:
        tipo_servico_consulta = 1

    categoria_movimentacao = request.args.get(
        'categoria_movimentacao',
        'MATERIAL'
    ).strip().upper()

    tecnico_id = request.args.get('tecnico_id', type=int)

    saldo_tecnico_tipo = (
        request.args.get('saldo_tecnico_tipo') or 'empresa'
    ).strip().lower()

    if saldo_tecnico_tipo not in ['empresa', 'cliente']:
        saldo_tecnico_tipo = 'empresa'

    cliente_id = (
        request.args.get('cliente_id', type=int)
        or request.args.get('cliente_movimentacao_id', type=int)
        or request.args.get('origem_id', type=int)
    )

    ordem_servico_id = (
        request.args.get('ordem_servico_id', type=int)
        or request.args.get('cliente_os_id', type=int)
        or request.args.get('os_id', type=int)
    )

    if categoria_movimentacao not in ['MATERIAL', 'PATRIMONIO']:
        categoria_movimentacao = 'MATERIAL'

    if not origem_tipo:
        return jsonify([])

    if categoria_movimentacao == 'MATERIAL' and not tipo_servico_id:
        return jsonify([])

    resultados = []

    # ==================================================
    # ESTOQUE EMPRESA
    # ==================================================
    if origem_tipo == 'empresa':

        query = (
            db.session.query(
                Item.codigo,
                Item.descricao,
                Item.categoria,
                Item.unidade,
                Item.valor,
                func.sum(Estoque.quantidade).label('saldo')
            )
            .join(Item, Estoque.item_id == Item.id)
            .filter(
                Estoque.tipo_estoque == 'empresa',
                Estoque.quantidade > 0
            )
        )

        if categoria_movimentacao == 'PATRIMONIO':
            query = query.filter(
                Item.categoria.in_(['FERRAMENTA', 'EPI'])
            )
        else:
            query = query.filter(
                Item.categoria == 'MATERIAL',
                Estoque.tipo_servico_id == tipo_servico_consulta
            )

            if _estoque_tem_condicao():
                # Disponível para transferência: estoque comum + usado bom.
                # Defeitos ficam fora da saída operacional.
                query = query.filter(
                    or_(
                        Estoque.condicao_material.is_(None),
                        Estoque.condicao_material == '',
                        Estoque.condicao_material == 'USADO_BOM'
                    )
                )

        registros = (
            query
            .group_by(
                Item.codigo,
                Item.descricao,
                Item.categoria,
                Item.unidade,
                Item.valor
            )
            .order_by(Item.descricao)
            .all()
        )

        for row in registros:
            resultados.append({
                'codigo': row.codigo,
                'descricao': row.descricao,
                'categoria': row.categoria or 'MATERIAL',
                'unidade': row.unidade,
                'saldo': int(row.saldo or 0),
                'valor': float(row.valor or 0)
            })

        return jsonify(resultados)

    # ==================================================
    # ESTOQUE CLIENTE
    # ==================================================
    elif origem_tipo == 'cliente':

        if categoria_movimentacao == 'PATRIMONIO':
            return jsonify([])

        if not cliente_id:
            return jsonify([])

        query = (
            db.session.query(
                Item.codigo,
                Item.descricao,
                Item.categoria,
                Item.unidade,
                Item.valor,
                func.sum(Estoque.quantidade).label('saldo')
            )
            .join(Item, Estoque.item_id == Item.id)
            .filter(
                Estoque.tipo_estoque == 'cliente',
                Estoque.cliente_id == cliente_id,
                Estoque.tipo_servico_id == tipo_servico_id,
                Estoque.quantidade > 0,
                Item.categoria == 'MATERIAL'
            )
        )

        registros = (
            query
            .group_by(
                Item.codigo,
                Item.descricao,
                Item.categoria,
                Item.unidade,
                Item.valor
            )
            .order_by(Item.descricao)
            .all()
        )

        for row in registros:
            resultados.append({
                'codigo': row.codigo,
                'descricao': row.descricao,
                'categoria': row.categoria or 'MATERIAL',
                'unidade': row.unidade,
                'saldo': int(row.saldo or 0),
                'valor': float(row.valor or 0)
            })

        return jsonify(resultados)

    # ==================================================
    # SALDO TÉCNICO
    # ==================================================
    elif origem_tipo == 'tecnico':

        if not tecnico_id:
            return jsonify([])

        query = (
            db.session.query(
                Item.codigo,
                Item.descricao,
                Item.categoria,
                Item.unidade,
                Item.valor,
                func.sum(SaldoTecnico.quantidade).label('saldo')
            )
            .join(Item, SaldoTecnico.item_id == Item.id)
            .filter(
                SaldoTecnico.tecnico_id == tecnico_id,
                SaldoTecnico.quantidade > 0
            )
        )

        if categoria_movimentacao == 'PATRIMONIO':
            query = query.filter(
                Item.categoria.in_(['FERRAMENTA', 'EPI'])
            )
        else:
            query = query.filter(
                Item.categoria == 'MATERIAL',
                SaldoTecnico.tipo_servico_id == tipo_servico_consulta,
                SaldoTecnico.tipo_estoque == saldo_tecnico_tipo
            )

            if saldo_tecnico_tipo == 'empresa':
                query = query.filter(
                    SaldoTecnico.cliente_id.is_(None),
                    SaldoTecnico.ordem_servico_id.is_(None)
                )
            else:
                if cliente_id:
                    query = query.filter(SaldoTecnico.cliente_id == cliente_id)

                if ordem_servico_id:
                    query = query.filter(SaldoTecnico.ordem_servico_id == ordem_servico_id)

        registros = (
            query
            .group_by(
                Item.codigo,
                Item.descricao,
                Item.categoria,
                Item.unidade,
                Item.valor
            )
            .order_by(Item.descricao)
            .all()
        )

        for row in registros:
            resultados.append({
                'codigo': row.codigo,
                'descricao': row.descricao,
                'categoria': row.categoria or 'MATERIAL',
                'unidade': row.unidade,
                'saldo': int(row.saldo or 0),
                'valor': float(row.valor or 0)
            })

        return jsonify(resultados)

    return jsonify([])


@bp_movimentacao.route('/detalhes/<int:id>/pdf')
@login_required
def detalhes_pdf(id):

    movimentacao = (
        MovimentacaoEstoque.query
        .get_or_404(id)
    )

    itens = (
        MovimentacaoEstoqueItem.query
        .filter_by(
            movimentacao_id=id
        )
        .all()
    )

    empresas = Empresa.query.all()
    tecnicos = Tecnico.query.all()

    empresas_dict = {
        e.id: e.razao_social
        for e in empresas
    }

    tecnicos_dict = {
        t.id: t.nome
        for t in tecnicos
    }

    return render_template(
        'movimentacao_estoque/detalhes_pdf.html',
        movimentacao=movimentacao,
        itens=itens,
        empresas_dict=empresas_dict,
        tecnicos_dict=tecnicos_dict
    )
