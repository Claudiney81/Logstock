import secrets
from collections import defaultdict
from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError
from app.extensions import db
from app.models import Tecnico, SaldoTecnico, Item, MovimentacaoEstoque, MovimentacaoEstoqueItem

bp = Blueprint('transferencia_tecnicos', __name__, url_prefix='/movimentacao_estoque')
PERFIS = {'admin', 'estoque', 'gerente'}


def transferir(origem_id, destino_id, linhas, usuario_id, observacao):
    if origem_id == destino_id:
        raise ValueError('Selecione técnicos diferentes para origem e destino.')
    tecnicos = Tecnico.query.filter(Tecnico.id.in_([origem_id, destino_id])).order_by(Tecnico.id).with_for_update().all()
    if len(tecnicos) != 2 or any((t.status or '').lower() != 'ativo' for t in tecnicos):
        raise ValueError('Selecione dois técnicos ativos.')
    nomes = {t.id: t.nome for t in tecnicos}
    if not linhas:
        raise ValueError('Informe a quantidade de pelo menos um material.')
    ids = [saldo_id for saldo_id, quantidade in linhas]
    if len(ids) != len(set(ids)):
        raise ValueError('Um saldo foi informado mais de uma vez.')
    grupos = defaultdict(list)
    for saldo_id, quantidade in linhas:
        if quantidade <= 0:
            raise ValueError('A quantidade deve ser um número inteiro positivo.')
        saldo = SaldoTecnico.query.filter_by(id=saldo_id, tecnico_id=origem_id).populate_existing().with_for_update().first()
        if not saldo or (saldo.item.categoria or 'MATERIAL').upper() != 'MATERIAL':
            raise ValueError('Material não encontrado no saldo do técnico de origem.')
        if saldo.tipo_estoque not in ('empresa', 'cliente'):
            raise ValueError('Origem do material não identificada. Confira o saldo antes de transferir.')
        if saldo.tipo_estoque == 'cliente' and not saldo.cliente:
            raise ValueError('Saldo de cliente sem cliente vinculado. Regularize antes de transferir.')
        if quantidade > (saldo.quantidade or 0):
            raise ValueError(f'Saldo insuficiente para {saldo.item.codigo}. Nenhum material foi transferido.')
        grupos[(saldo.tipo_servico_id, saldo.tipo_estoque, saldo.cliente_id, saldo.ordem_servico_id)].append((saldo, quantidade))

    movimentos = []
    for (servico, tipo, cliente_id, os_id), itens in grupos.items():
        referencia = ('Empresa' if tipo == 'empresa' else f'Cliente: {itens[0][0].cliente.razao_social}')
        mov = MovimentacaoEstoque(origem_tipo='tecnico', origem_id=origem_id,
            destino_tipo='tecnico', destino_id=destino_id, tipo_servico_id=servico,
            ordem_servico_id=os_id, categoria_movimentacao='MATERIAL', tipo_movimentacao='transferencia',
            usuario_id=usuario_id, observacao=f'Transferência de {nomes[origem_id]} para {nomes[destino_id]}. Material de {referencia}. {observacao}'.strip())
        db.session.add(mov); db.session.flush()
        for saldo, quantidade in itens:
            # A condição no UPDATE também protege contra consumo simultâneo do mesmo saldo.
            alterados = SaldoTecnico.query.filter(SaldoTecnico.id == saldo.id,
                SaldoTecnico.quantidade >= quantidade).update(
                    {SaldoTecnico.quantidade: SaldoTecnico.quantidade - quantidade}, synchronize_session=False)
            if alterados != 1:
                raise ValueError('O saldo mudou durante a operação. Consulte novamente; nenhum material foi transferido.')
            campos = dict(tecnico_id=destino_id, item_id=saldo.item_id, tipo_servico_id=servico,
                tipo_estoque=tipo, cliente_id=cliente_id, ordem_servico_id=os_id,
                endereco=saldo.endereco, bairro=saldo.bairro, codigo_imovel=saldo.codigo_imovel,
                valor_unitario=saldo.valor_unitario)
            destino = SaldoTecnico.query.filter_by(**campos).with_for_update().first()
            if destino:
                SaldoTecnico.query.filter_by(id=destino.id).update(
                    {SaldoTecnico.quantidade: db.func.coalesce(SaldoTecnico.quantidade, 0) + quantidade},
                    synchronize_session=False)
            else:
                db.session.add(SaldoTecnico(**campos, quantidade=quantidade, quantidade_minima=0))
            db.session.add(MovimentacaoEstoqueItem(movimentacao_id=mov.id, item_id=saldo.item_id,
                quantidade=quantidade, valor_unitario=saldo.valor_unitario))
            db.session.flush()
        movimentos.append(mov)
    return movimentos


@bp.route('/entre-tecnicos', methods=['GET', 'POST'])
@login_required
def nova():
    if current_user.perfil not in PERFIS:
        abort(403)
    origem_id = request.values.get('origem_id', type=int)
    if request.method == 'POST':
        token = request.form.get('csrf_token', '')
        if not token or not secrets.compare_digest(token, session.get('transferencia_tecnicos_csrf', '')):
            abort(400, 'Formulário expirado. Consulte os materiais novamente.')
        try:
            destino_id = int(request.form.get('destino_id', ''))
            linhas = []
            for chave in request.form:
                if chave.startswith('quantidade_'):
                    valor = request.form[chave].strip()
                    if valor and valor != '0':
                        linhas.append((int(chave.removeprefix('quantidade_')), int(valor)))
            movimentos = transferir(origem_id, destino_id, linhas, current_user.id,
                request.form.get('observacao', '').strip()[:1000])
            db.session.commit()
            session.pop('transferencia_tecnicos_csrf', None)
            flash('Transferência concluída. Saldos dos dois técnicos atualizados.', 'success')
            return redirect(url_for('movimentacao_estoque.detalhes', id=movimentos[0].id) if len(movimentos) == 1
                            else url_for('movimentacao_estoque.historico'))
        except (ValueError, TypeError) as erro:
            db.session.rollback()
            flash(str(erro) if isinstance(erro, ValueError) and not str(erro).startswith('invalid literal')
                  else 'Informe técnicos e quantidades válidos.', 'danger')
        except SQLAlchemyError:
            db.session.rollback()
            from flask import current_app
            current_app.logger.exception('Falha na transferência entre técnicos')
            flash('Não foi possível concluir. Nenhum saldo foi alterado.', 'danger')
        return redirect(url_for('transferencia_tecnicos.nova', origem_id=origem_id))
    token = session.setdefault('transferencia_tecnicos_csrf', secrets.token_urlsafe(32))
    saldos = SaldoTecnico.query.join(Item).filter(SaldoTecnico.tecnico_id == origem_id,
        SaldoTecnico.quantidade > 0, db.func.upper(db.func.coalesce(Item.categoria, 'MATERIAL')) == 'MATERIAL').order_by(Item.codigo, SaldoTecnico.id).all() if origem_id else []
    return render_template('movimentacao_estoque/entre_tecnicos.html',
        tecnicos=Tecnico.query.filter(db.func.lower(Tecnico.status) == 'ativo').order_by(Tecnico.nome).all(),
        origem_id=origem_id, saldos=saldos, csrf_token=token)
