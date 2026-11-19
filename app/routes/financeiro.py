import csv
import io
import secrets
from uuid import uuid4
from decimal import Decimal
from functools import wraps

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for, Response, send_file
from flask_login import current_user, login_required
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy import func, or_

from app.extensions import db
from app.financeiro_importacao import LIMITE_ARQUIVO, chave_cliente, ler_clientes
from app.financeiro_models import CadastroFinanceiro, ClienteFinanceiro, ContratoFinanceiro, ParcelaFinanceira, RecebimentoFinanceiro, EventoFinanceiro
from app.models import Usuario
from app.financeiro_service import MODALIDADES, FORMAS_PAGAMENTO, FORNECEDORES, dinheiro, data_valida, gerar_parcelas, resumo, situacao
from app.utils.datas import hoje_local
from app.utils.busca import contem_busca

bp = Blueprint('financeiro', __name__, url_prefix='/financeiro')


@bp.app_template_filter('detalhe_financeiro')
def detalhe_financeiro(texto):
    import re
    def moeda(valor):
        return 'R$ ' + f'{Decimal(valor):,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')
    apuracao = re.fullmatch(r'Valor anterior: (None|[\d.]+); novo: ([\d.]+)\.\s*(.*)', texto)
    if apuracao:
        anterior, novo, motivo = apuracao.groups()
        descricao = ('Valor definido: ' + moeda(novo) if anterior == 'None'
                     else moeda(anterior) + ' → ' + moeda(novo))
        return descricao + ('. Motivo: ' + motivo if motivo and motivo != 'ND' else '')
    pagamento = re.fullmatch(r'Recebimento integral: ([\d.]+); data: (\d{4})-(\d{2})-(\d{2})\.', texto)
    if pagamento:
        valor, ano, mes, dia = pagamento.groups()
        return f'{moeda(valor)} recebido em {dia}/{mes}/{ano}.'
    return texto.replace('None', 'Não informado')
OPERACOES = {'consultar', 'cadastros', 'contratos', 'apurar', 'receber', 'relatorios', 'exportar'}
CADASTROS = {'fornecedores':'Fornecedores do kit','formas_pagamento':'Formas de pagamento'}


def opcoes_cadastro(tipo,padrao,usados):
    itens=CadastroFinanceiro.query.filter_by(tipo=tipo).all()
    inativos={i.nome.casefold() for i in itens if not i.ativo}
    return sorted({nome for nome in [*padrao,*usados,*[i.nome for i in itens if i.ativo]]
        if nome and nome.casefold() not in inativos},key=str.casefold)


def permitido(operacao):
    perfil = getattr(current_user, 'perfil', None)
    padrao = {'admin': OPERACOES, 'financeiro': OPERACOES, 'gerente': OPERACOES}
    permissoes = current_app.config.get('FINANCEIRO_PERMISSOES', padrao)
    return current_app.config.get('FINANCEIRO_HABILITADO', False) and operacao in permissoes.get(perfil, ())


def acesso(operacao):
    def decorator(func):
        @wraps(func)
        @login_required
        def wrapped(*args, **kwargs):
            if not current_app.config.get('FINANCEIRO_HABILITADO', False):
                abort(404)
            if not permitido(operacao):
                abort(403)
            if request.method == 'POST':
                esperado = session.get('financeiro_csrf', '')
                recebido = request.form.get('csrf_token', '')
                if not esperado or not secrets.compare_digest(esperado, recebido):
                    abort(400, 'Formulário expirado. Atualize a página.')
            return func(*args, **kwargs)
        return wrapped
    return decorator


@bp.app_context_processor
def contexto():
    def token():
        if 'financeiro_csrf' not in session:
            session['financeiro_csrf'] = secrets.token_urlsafe(32)
        return session['financeiro_csrf']
    return dict(financeiro_permitido=permitido, financeiro_token=token,
                modalidades_financeiras=MODALIDADES, situacao_financeira=situacao)


def filtros():
    query = ParcelaFinanceira.query.join(ContratoFinanceiro)
    contrato = request.args.get('contrato', '').strip()
    cliente_id = request.args.get('cliente_id', '').strip()
    modalidade = request.args.get('modalidade', '').strip()
    inicio = request.args.get('inicio', '').strip()
    fim = request.args.get('fim', '').strip()
    tipo = request.args.get('tipo', 'cobrancas')
    status = request.args.get('situacao', '')
    busca = request.args.get('busca','').strip()
    responsavel = request.args.get('responsavel_id','').strip()
    if busca:
        query=query.outerjoin(ClienteFinanceiro).filter(or_(
            contem_busca(ContratoFinanceiro.cliente,busca),contem_busca(ClienteFinanceiro.nome,busca),
            contem_busca(ClienteFinanceiro.documento,busca),contem_busca(ContratoFinanceiro.codigo,busca),
            contem_busca(ParcelaFinanceira.nota_kit,busca)))
    if responsavel:
        if not responsavel.isdigit():
            raise ValueError('Responsável inválido.')
        query=query.filter(ContratoFinanceiro.criado_por==int(responsavel))
    if tipo not in ('cobrancas', 'recebimentos', 'a_receber'):
        raise ValueError('Tipo de relatório inválido.')
    if status not in ('', 'Pago', 'Aguardando apuração', 'Atrasado', 'Vence hoje', 'A vencer'):
        raise ValueError('Situação inválida.')
    if contrato:
        if not contrato.isdigit():
            raise ValueError('Contrato inválido.')
        query = query.filter(ContratoFinanceiro.id == int(contrato))
    if cliente_id:
        if not cliente_id.isdigit():
            raise ValueError('Cliente inválido.')
        query = query.filter(ContratoFinanceiro.cliente_id == int(cliente_id))
    if modalidade:
        if modalidade not in MODALIDADES:
            raise ValueError('Modalidade inválida.')
        query = query.filter(ContratoFinanceiro.modalidade == modalidade)
    coluna = ParcelaFinanceira.vencimento
    if tipo == 'recebimentos':
        query = query.join(RecebimentoFinanceiro)
        coluna = RecebimentoFinanceiro.data_pagamento
    elif tipo == 'a_receber':
        query = query.filter(ParcelaFinanceira.valor_real.isnot(None), ~ParcelaFinanceira.recebimentos.any())
    di = data_valida(inicio) if inicio else None
    df = data_valida(fim) if fim else None
    if di and df and di > df:
        raise ValueError('O início deve ser anterior ou igual ao fim.')
    if di:
        query = query.filter(coluna >= di)
    if df:
        query = query.filter(coluna <= df)
    parcelas = query.order_by(ParcelaFinanceira.vencimento, ParcelaFinanceira.id).all()
    if status:
        parcelas = [p for p in parcelas if situacao(p) == status]
    return parcelas


@bp.get('/')
@acesso('consultar')
def index():
    parcelas=ParcelaFinanceira.query.all()
    return render_template('financeiro/painel.html',totais=resumo(parcelas),
        quantidade_clientes=ClienteFinanceiro.query.count(),quantidade_contratos=ContratoFinanceiro.query.count(),
        contratos=ContratoFinanceiro.query.order_by(ContratoFinanceiro.id.desc()).limit(5).all(),
        meus_registros=ContratoFinanceiro.query.filter_by(criado_por=current_user.id).count())


@bp.get('/contratos')
@acesso('consultar')
def contratos():
    query = ContratoFinanceiro.query.outerjoin(ClienteFinanceiro)
    busca = request.args.get('busca', '').strip()
    if busca:
        query = query.filter(or_(contem_busca(ContratoFinanceiro.cliente,busca),
            contem_busca(ClienteFinanceiro.nome,busca),contem_busca(ContratoFinanceiro.codigo,busca)))
    contratos = query.order_by(ContratoFinanceiro.id.desc()).all()
    return render_template('financeiro/index.html', contratos=contratos,
                           totais=resumo(ParcelaFinanceira.query.all()))


@bp.route('/contratos/novo', methods=['GET', 'POST'])
@acesso('contratos')
def novo():
    if request.method == 'POST':
        try:
            codigo = request.form.get('codigo', '').strip() or ('CTR-' + uuid4().hex[:12].upper())
            cliente_id = request.form.get('cliente_id', '')
            cadastro = db.session.get(ClienteFinanceiro, int(cliente_id)) if cliente_id.isdigit() else None
            if not cadastro or not cadastro.ativo:
                raise ValueError('Selecione um cliente ativo do cadastro.')
            cliente = cadastro.nome
            modalidade = request.form.get('modalidade')
            if not codigo or len(codigo) > 80 or not cliente or len(cliente) > 160 or modalidade not in MODALIDADES:
                raise ValueError('Informe código, cliente e modalidade válidos.')
            quantidade = int(request.form.get('quantidade_parcelas', '0'))
            if not 1 <= quantidade <= 600:
                raise ValueError('O contrato deve ter entre 1 e 600 parcelas.')
            inicial = data_valida(request.form.get('primeiro_vencimento'))
            if inicial.year + quantidade // 12 > 9998:
                raise ValueError('Período do contrato inválido.')
            contrato = ContratoFinanceiro(
                codigo=codigo, cliente=cliente, cliente_id=cadastro.id, modalidade=modalidade,
                fornecedor=request.form.get('fornecedor', '').strip()[:160],
                forma_pagamento=request.form.get('forma_pagamento', '').strip()[:80],
                quantidade_parcelas=quantidade, primeiro_vencimento=inicial,
                base_mensal=dinheiro(request.form.get('base_mensal')),
                valor_total=dinheiro(request.form.get('valor_total'), opcional=True),
                observacao=request.form.get('observacao', '').strip(),
                criado_por=current_user.id,
                demonstracao=bool(current_app.config.get('FINANCEIRO_DEMONSTRACAO')),
            )
            gerar_parcelas(contrato)
            nota = request.form.get('nota_kit', '').strip()
            if len(nota) > 80:
                raise ValueError('A Nº NF deve ter até 80 caracteres.')
            for parcela in contrato.parcelas:
                parcela.nota_kit = nota or None
            db.session.add(contrato)
            db.session.commit()
            flash('Contrato criado com suas parcelas.', 'success')
            return redirect(url_for('financeiro.contrato', contrato_id=contrato.id))
        except (ValueError, IntegrityError) as erro:
            db.session.rollback()
            flash(str(erro) if isinstance(erro, ValueError) else 'Já existe um contrato com esse código.', 'danger')
    usados=db.session.query(ContratoFinanceiro.fornecedor,ContratoFinanceiro.forma_pagamento).distinct().all()
    fornecedores=opcoes_cadastro('fornecedores',FORNECEDORES,[f for f,_ in usados])
    formas=opcoes_cadastro('formas_pagamento',FORMAS_PAGAMENTO,[f for _,f in usados])
    return render_template('financeiro/novo.html',clientes=ClienteFinanceiro.query.filter_by(ativo=True).order_by(ClienteFinanceiro.nome).all(),
        fornecedores=sorted(fornecedores),formas_pagamento=sorted(formas))


@bp.get('/contratos/<int:contrato_id>')
@acesso('consultar')
def contrato(contrato_id):
    item = db.get_or_404(ContratoFinanceiro, contrato_id)
    eventos = EventoFinanceiro.query.join(ParcelaFinanceira).filter(
        ParcelaFinanceira.contrato_id == item.id).order_by(EventoFinanceiro.id.desc()).all()
    return render_template('financeiro/contrato.html', contrato=item, totais=resumo(item.parcelas), eventos=eventos)


def validar_versao(parcela):
    if request.form.get('versao') != str(parcela.versao):
        raise ValueError('A parcela foi alterada. Atualize a página antes de continuar.')


@bp.post('/parcelas/<int:parcela_id>/apurar')
@acesso('apurar')
def apurar(parcela_id):
    parcela = db.get_or_404(ParcelaFinanceira, parcela_id)
    contrato_id = parcela.contrato_id
    try:
        validar_versao(parcela)
        if parcela.recebimentos:
            raise ValueError('Parcela paga não pode ter seu valor alterado.')
        valor = dinheiro(request.form.get('valor_real'))
        motivo = request.form.get('observacao', '').strip()
        nota = request.form.get('nota_kit', '').strip()[:80]
        if parcela.valor_real == valor and (parcela.nota_kit or '') == nota:
            flash('Nenhuma alteração: valor e nota já estão salvos.', 'info')
            destino = ('financeiro.lancamento' if request.form.get('destino') == 'lancamento'
                       else 'financeiro.contrato')
            return redirect(url_for(destino, **({'parcela_id': parcela_id} if destino.endswith('lancamento')
                                                else {'contrato_id': contrato_id})))
        if parcela.valor_real is not None and not motivo:
            raise ValueError('Informe o motivo da alteração do valor já apurado.')
        anterior = parcela.valor_real
        parcela.valor_real = valor
        parcela.nota_kit = nota
        parcela.observacao = motivo
        parcela.versao += 1
        db.session.add(EventoFinanceiro(parcela_id=parcela.id, usuario_id=current_user.id,
            acao='apuracao', detalhe=f'Valor anterior: {anterior}; novo: {valor}. {motivo}'))
        db.session.commit()
        flash('Valor final registrado. A previsão foi preservada.', 'success')
    except (ValueError, StaleDataError) as erro:
        db.session.rollback()
        flash(str(erro) if isinstance(erro, ValueError) else 'A parcela foi alterada por outro operador. Atualize a página.', 'danger')
    if request.form.get('destino') == 'lancamento':
        return redirect(url_for('financeiro.lancamento',parcela_id=parcela_id))
    return redirect(url_for('financeiro.contrato', contrato_id=contrato_id))


@bp.post('/parcelas/<int:parcela_id>/receber')
@acesso('receber')
def receber(parcela_id):
    parcela = db.get_or_404(ParcelaFinanceira, parcela_id)
    contrato_id = parcela.contrato_id
    try:
        validar_versao(parcela)
        if parcela.valor_real is None:
            raise ValueError('Informe o valor real antes de registrar o recebimento.')
        if parcela.recebimentos:
            raise ValueError('Esta parcela já está paga.')
        valor = dinheiro(request.form.get('valor'))
        if valor != parcela.valor_real:
            raise ValueError('O recebimento deve corresponder ao valor integral da parcela.')
        data = data_valida(request.form.get('data_pagamento'))
        if data > hoje_local():
            raise ValueError('A data de pagamento não pode estar no futuro.')
        parcela.versao += 1
        db.session.add(RecebimentoFinanceiro(parcela_id=parcela.id, valor=valor,
            data_pagamento=data, criado_por=current_user.id))
        db.session.add(EventoFinanceiro(parcela_id=parcela.id, usuario_id=current_user.id,
            acao='recebimento', detalhe=f'Recebimento integral: {valor}; data: {data.isoformat()}.'))
        db.session.commit()
        flash('Recebimento registrado.', 'success')
    except (ValueError, IntegrityError, StaleDataError) as erro:
        db.session.rollback()
        flash(str(erro) if isinstance(erro, ValueError) else 'Parcela já processada por outro operador. Atualize a página.', 'danger')
    if request.form.get('destino') == 'lancamento':
        return redirect(url_for('financeiro.lancamento',parcela_id=parcela_id))
    return redirect(url_for('financeiro.contrato', contrato_id=contrato_id))


@bp.get('/relatorios')
@acesso('relatorios')
def relatorios():
    try:
        parcelas = filtros()
    except ValueError as erro:
        flash(str(erro), 'danger')
        parcelas = []
    por_cliente = {}
    por_mes = {}
    for p in parcelas:
        chave = p.contrato.cliente_id or ('legado', p.contrato.cliente)
        por_cliente.setdefault(chave, {'nome':p.contrato.nome_cliente, 'parcelas':[]})['parcelas'].append(p)
        data = p.recebimentos[0].data_pagamento if request.args.get('tipo') == 'recebimentos' and p.recebimentos else p.vencimento
        por_mes.setdefault(data.strftime('%Y-%m'),[]).append(p)
    clientes_resumo = [{'nome':v['nome'], 'totais':resumo(v['parcelas'])} for v in por_cliente.values()]
    meses_resumo = [{'mes':m, 'totais':resumo(ps)} for m,ps in sorted(por_mes.items())]
    return render_template('financeiro/relatorios.html', parcelas=parcelas,
        totais=resumo(parcelas), contratos=ContratoFinanceiro.query.order_by(ContratoFinanceiro.cliente).all(),
        clientes=ClienteFinanceiro.query.order_by(ClienteFinanceiro.nome).all(),
        clientes_resumo=clientes_resumo,meses_resumo=meses_resumo)


@bp.get('/clientes')
@acesso('consultar')
def clientes():
    busca = request.args.get('busca','').strip()
    query = ClienteFinanceiro.query
    if busca:
        query = query.filter(or_(contem_busca(ClienteFinanceiro.nome,busca), contem_busca(ClienteFinanceiro.documento,busca)))
    return render_template('financeiro/clientes.html',clientes=query.order_by(ClienteFinanceiro.nome).all())


@bp.before_request
def limitar_upload_clientes():
    if request.endpoint == 'financeiro.importar_clientes':
        request.max_content_length = LIMITE_ARQUIVO + 1024 * 1024


@bp.route('/clientes/importar', methods=['GET', 'POST'])
@acesso('cadastros')
def importar_clientes():
    if request.method == 'GET':
        return render_template('financeiro/importar_clientes.html')

    assinatura = URLSafeTimedSerializer(current_app.secret_key, salt='financeiro-importar-clientes')
    token = request.form.get('previa')
    existentes = {chave_cliente(nome) for nome, in db.session.query(ClienteFinanceiro.nome)}

    if token:
        try:
            dados = assinatura.loads(token, max_age=1800)
            if dados['usuario'] != current_user.id:
                raise BadSignature('Usuário diferente')
        except BadSignature:
            flash('A prévia expirou. Selecione a planilha novamente.', 'danger')
            return redirect(url_for('financeiro.importar_clientes'))

        nomes = dados['nomes']
        novos = [nome for nome in nomes if chave_cliente(nome) not in existentes]
        db.session.add_all(
            ClienteFinanceiro(nome=nome, ativo=True, criado_por=current_user.id)
            for nome in novos
        )
        db.session.commit()
        flash(f'Importação concluída. Novos cadastros: {len(novos)}. Já existentes: {len(nomes) - len(novos)}.', 'success')
        return redirect(url_for('financeiro.clientes'))

    planilha = request.files.get('planilha')
    if not planilha or not planilha.filename.lower().endswith('.xlsx'):
        flash('Selecione um arquivo Excel .xlsx.', 'danger')
        return render_template('financeiro/importar_clientes.html'), 400
    try:
        nomes, repetidos, invalidos = ler_clientes(planilha.stream)
    except ValueError as erro:
        flash(str(erro), 'danger')
        return render_template('financeiro/importar_clientes.html'), 400

    novos, cadastrados = [], []
    for linha, nome in nomes:
        grupo = cadastrados if chave_cliente(nome) in existentes else novos
        grupo.append((linha, nome))
    previa = assinatura.dumps({'usuario': current_user.id, 'nomes': [nome for _, nome in novos]})
    return render_template(
        'financeiro/importar_clientes.html', previa=previa, novos=novos,
        cadastrados=cadastrados, repetidos=repetidos, invalidos=invalidos,
    )


def salvar_cliente(item):
    nome = request.form.get('nome','').strip()
    documento = ''.join(c for c in request.form.get('documento','') if c.isdigit()) or None
    email = request.form.get('email','').strip()
    if not nome or len(nome)>160:
        raise ValueError('Informe o nome do cliente, com até 160 caracteres.')
    if documento and len(documento) not in (11,14):
        raise ValueError('Informe CPF com 11 dígitos ou CNPJ com 14 dígitos, ou deixe em branco.')
    if email and ('@' not in email or len(email)>160):
        raise ValueError('Informe um e-mail válido.')
    duplicado = ClienteFinanceiro.query.filter(func.lower(ClienteFinanceiro.nome)==nome.lower())
    if item.id:
        duplicado = duplicado.filter(ClienteFinanceiro.id != item.id)
    if not documento and duplicado.first():
        raise ValueError('Já existe um cliente com esse nome. Confira o cadastro ou informe o documento para diferenciá-lo.')
    item.nome=nome
    item.documento=documento
    item.email=email
    item.telefone=request.form.get('telefone','').strip()[:40]
    item.endereco=request.form.get('endereco','').strip()[:240]
    item.observacao=request.form.get('observacao','').strip()
    item.ativo=request.form.get('ativo')=='1'
    item.atualizado_por=current_user.id
    db.session.add(item)
    db.session.commit()


@bp.route('/clientes/novo',methods=['GET','POST'])
@acesso('cadastros')
def novo_cliente():
    item=ClienteFinanceiro(ativo=True,criado_por=current_user.id)
    if request.method=='POST':
        try:
            salvar_cliente(item)
            flash('Cliente cadastrado. Agora você pode criar o contrato e seus lançamentos.','success')
            if request.form.get('proximo') == 'contrato' and permitido('contratos') and item.ativo:
                return redirect(url_for('financeiro.novo',cliente_id=item.id))
            return redirect(url_for('financeiro.cliente',cliente_id=item.id))
        except (ValueError,IntegrityError) as erro:
            db.session.rollback()
            flash(str(erro) if isinstance(erro,ValueError) else 'CPF/CNPJ já cadastrado.','danger')
    return render_template('financeiro/cliente_form.html',cliente=item)


@bp.route('/clientes/<int:cliente_id>/editar',methods=['GET','POST'])
@acesso('cadastros')
def editar_cliente(cliente_id):
    item=db.get_or_404(ClienteFinanceiro,cliente_id)
    if request.method=='POST':
        try:
            salvar_cliente(item)
            flash('Cadastro do cliente atualizado.','success')
            return redirect(url_for('financeiro.cliente',cliente_id=item.id))
        except (ValueError,IntegrityError) as erro:
            db.session.rollback()
            flash(str(erro) if isinstance(erro,ValueError) else 'CPF/CNPJ já cadastrado.','danger')
    return render_template('financeiro/cliente_form.html',cliente=item)


@bp.get('/clientes/<int:cliente_id>')
@acesso('consultar')
def cliente(cliente_id):
    item=db.get_or_404(ClienteFinanceiro,cliente_id)
    parcelas=[p for c in item.contratos for p in c.parcelas]
    return render_template('financeiro/cliente.html',cliente=item,totais=resumo(parcelas))


@bp.get('/lancamentos')
@acesso('consultar')
def lancamentos():
    try:
        parcelas=filtros()
    except ValueError as erro:
        flash(str(erro),'danger');parcelas=[]
    return render_template('financeiro/lancamentos.html',parcelas=parcelas,totais=resumo(parcelas),
        clientes=ClienteFinanceiro.query.order_by(ClienteFinanceiro.nome).all(),
        contratos=ContratoFinanceiro.query.order_by(ContratoFinanceiro.cliente).all())


@bp.get('/parcelas/<int:parcela_id>/lancamento')
@acesso('consultar')
def lancamento(parcela_id):
    item=db.get_or_404(ParcelaFinanceira,parcela_id)
    eventos=EventoFinanceiro.query.filter_by(parcela_id=item.id).order_by(EventoFinanceiro.id.desc()).all()
    return render_template('financeiro/lancamento.html',p=item,eventos=eventos)


@bp.post('/parcelas/<int:parcela_id>/dados')
@acesso('apurar')
def dados_parcela(parcela_id):
    parcela=db.get_or_404(ParcelaFinanceira,parcela_id)
    try:
        validar_versao(parcela)
        if parcela.recebimentos:
            raise ValueError('Parcela paga não pode ser alterada.')
        vencimento=data_valida(request.form.get('vencimento'))
        nota=request.form.get('nota_kit','').strip()
        observacao=request.form.get('observacao','').strip()
        motivo=request.form.get('motivo','').strip()
        if len(nota)>80:
            raise ValueError('A Nº NF deve ter até 80 caracteres.')
        if not motivo:
            raise ValueError('Informe o motivo para registrar a alteração dos dados da parcela.')
        anterior=f'Vencimento: {parcela.vencimento}; nota: {parcela.nota_kit or ""}; observação: {parcela.observacao or ""}.'
        parcela.vencimento=vencimento
        parcela.nota_kit=nota or None
        parcela.observacao=observacao
        parcela.versao+=1
        db.session.add(EventoFinanceiro(parcela_id=parcela.id,usuario_id=current_user.id,acao='dados_parcela',
            detalhe=f'{anterior} Novo vencimento: {vencimento}; nota: {nota}; observação: {observacao}. Motivo: {motivo}'))
        db.session.commit()
        flash('Dados da parcela atualizados. A previsão e o valor real foram preservados.','success')
    except (ValueError,StaleDataError) as erro:
        db.session.rollback()
        flash(str(erro) if isinstance(erro,ValueError) else 'A parcela foi alterada. Atualize a página.','danger')
    return redirect(url_for('financeiro.lancamento',parcela_id=parcela_id))


@bp.get('/cadastros')
@acesso('consultar')
def cadastros():
    return render_template('financeiro/cadastros.html',tipos=CADASTROS)


@bp.route('/cadastros/<tipo>',methods=['GET','POST'])
@acesso('cadastros')
def cadastro_auxiliar(tipo):
    if tipo not in CADASTROS:
        abort(404)
    if request.method=='POST':
        try:
            nome=request.form.get('nome','').strip()
            if not nome or len(nome)>160:
                raise ValueError('Informe um nome com até 160 caracteres.')
            existente=CadastroFinanceiro.query.filter_by(tipo=tipo).filter(func.lower(CadastroFinanceiro.nome)==nome.lower()).first()
            if existente:
                raise ValueError('Esse cadastro já existe. Utilize a opção de editar.')
            db.session.add(CadastroFinanceiro(tipo=tipo,nome=nome,ativo=True,criado_por=current_user.id))
            db.session.commit()
            flash('Cadastro incluído e disponível para novas negociações.','success')
            return redirect(url_for('financeiro.cadastro_auxiliar',tipo=tipo))
        except (ValueError,IntegrityError) as erro:
            db.session.rollback()
            flash(str(erro) if isinstance(erro,ValueError) else 'Esse cadastro já existe.','danger')
    padrao=FORNECEDORES if tipo=='fornecedores' else FORMAS_PAGAMENTO
    coluna=ContratoFinanceiro.fornecedor if tipo=='fornecedores' else ContratoFinanceiro.forma_pagamento
    usados=[r[0] for r in db.session.query(coluna).distinct().all()]
    return render_template('financeiro/cadastro_auxiliar.html',tipo=tipo,titulo=CADASTROS[tipo],
        itens=CadastroFinanceiro.query.filter_by(tipo=tipo).order_by(CadastroFinanceiro.nome).all(),
        sugestoes=opcoes_cadastro(tipo,padrao,usados))


@bp.post('/cadastros/<tipo>/<int:item_id>/editar')
@acesso('cadastros')
def editar_cadastro_auxiliar(tipo,item_id):
    if tipo not in CADASTROS:
        abort(404)
    item=db.get_or_404(CadastroFinanceiro,item_id)
    if item.tipo!=tipo:
        abort(404)
    try:
        # Nome preservado: contratos anteriores mantêm exatamente a informação registrada.
        item.ativo=request.form.get('ativo')=='1'
        item.atualizado_por=current_user.id
        db.session.commit()
        flash('Situação atualizada. Os registros anteriores foram preservados.','success')
    except IntegrityError:
        db.session.rollback()
        flash('Não foi possível atualizar o cadastro.','danger')
    return redirect(url_for('financeiro.cadastro_auxiliar',tipo=tipo))


@bp.get('/registros/novo')
@acesso('contratos')
def novo_registro():
    return render_template('financeiro/novo_registro.html',clientes=ClienteFinanceiro.query.filter_by(ativo=True).order_by(ClienteFinanceiro.nome).all())


@bp.get('/consultas')
@acesso('consultar')
def consultas():
    try:
        parcelas=filtros()
    except ValueError as erro:
        flash(str(erro),'danger');parcelas=[]
    return render_template('financeiro/consultas.html',parcelas=parcelas,totais=resumo(parcelas),
        responsaveis=Usuario.query.filter(Usuario.id.in_(db.session.query(ContratoFinanceiro.criado_por))).order_by(Usuario.nome).all())


@bp.get('/exportacoes')
@acesso('exportar')
def exportacoes():
    return redirect(url_for('financeiro.relatorios'))


def arquivo_exportacao(cabecalho,linhas,nome):
    formato=request.args.get('formato','csv')
    if formato not in ('csv','xlsx'):
        abort(400,'Formato de exportação inválido.')
    def seguro(valor):
        if valor is None:
            return ''
        if isinstance(valor,Decimal):
            return float(valor) if formato=='xlsx' else format(valor,'.2f').replace('.',',')
        if isinstance(valor,(int,float)):
            return valor
        texto=str(valor)
        return "'"+texto if texto.lstrip().startswith(('=','+','-','@')) else texto
    linhas=[[seguro(v) for v in linha] for linha in linhas]
    if formato=='xlsx':
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
        workbook=Workbook()
        sheet=workbook.active;sheet.title=nome[:31]
        sheet.append(cabecalho)
        for row in linhas:
            sheet.append(row)
        for cell in sheet[1]:
            cell.font=Font(bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='193055')
        sheet.freeze_panes='A2';sheet.auto_filter.ref=sheet.dimensions
        for column in sheet.columns:
            sheet.column_dimensions[column[0].column_letter].width=min(45,max(15,max(len(str(c.value or '')) for c in column)+2))
        for row in sheet.iter_rows(min_row=2):
            for cell in row:
                if isinstance(cell.value,float):
                    cell.number_format='#,##0.00'
        output=io.BytesIO();workbook.save(output);output.seek(0)
        return send_file(output,as_attachment=True,download_name=nome+'.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    output=io.StringIO();writer=csv.writer(output,delimiter=';');writer.writerow(cabecalho);writer.writerows(linhas)
    return Response('\ufeff'+output.getvalue(),mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition':f'attachment; filename={nome}.csv'})


@bp.get('/exportacoes/cadastros')
@acesso('exportar')
def exportar_cadastros():
    conjunto=request.args.get('conjunto','clientes')
    cliente_id=request.args.get('cliente_id','').strip()
    if cliente_id and not cliente_id.isdigit():
        abort(400,'Cliente inválido.')
    if conjunto=='clientes':
        query=ClienteFinanceiro.query
        if cliente_id:
            query=query.filter_by(id=int(cliente_id))
        return arquivo_exportacao(['Cliente','CPF/CNPJ','Telefone','E-mail','Endereço','Situação','Observação'],
            [[c.nome,c.documento,c.telefone,c.email,c.endereco,'Ativo' if c.ativo else 'Inativo',c.observacao]
             for c in query.order_by(ClienteFinanceiro.nome).all()],'clientes_financeiro')
    if conjunto=='contratos':
        query=ContratoFinanceiro.query
        if cliente_id:
            query=query.filter_by(cliente_id=int(cliente_id))
        return arquivo_exportacao(['Contrato','Cliente','Modelo de negócio','Fornecedor do kit','Forma de pagamento',
            'Parcelas','Primeiro vencimento','Base mensal / parcela','Total contratado','Responsável','Criado em','Observação'],
            [[c.codigo,c.nome_cliente,MODALIDADES[c.modalidade],c.fornecedor,c.forma_pagamento,c.quantidade_parcelas,
              c.primeiro_vencimento.isoformat(),c.base_mensal,c.valor_total,
              c.autor.nome,c.criado_em.isoformat(),c.observacao]
             for c in query.order_by(ContratoFinanceiro.id).all()],'contratos_financeiro')
    abort(400,'Conjunto de dados inválido.')


@bp.get('/relatorios/exportar')
@acesso('exportar')
def exportar():
    try:
        parcelas = filtros()
    except ValueError as erro:
        abort(400, str(erro))
    cabecalho=['Contrato', 'Cliente', 'Modalidade', 'Parcela', 'Vencimento', 'Previsão',
                     'Valor real', 'Situação', 'Data pagamento', 'Recebido', 'Registrado por', 'Demonstração',
                     'Fornecedor do kit', 'Forma de pagamento', 'Nº NF', 'Valor mensal bruto do contrato', 'Observação', 'Competência']
    linhas=[]
    for p in parcelas:
        r = p.recebimentos[0] if p.recebimentos else None
        linhas.append([p.contrato.codigo,p.contrato.nome_cliente,MODALIDADES[p.contrato.modalidade],
            p.numero,p.vencimento.strftime('%d/%m/%Y'),p.previsao,p.valor_real,situacao(p),
            r.data_pagamento.strftime('%d/%m/%Y') if r else '',r.valor if r else '',r.autor.nome if r else '',
            'Sim' if p.contrato.demonstracao else 'Não',p.contrato.fornecedor,p.contrato.forma_pagamento,p.nota_kit,
            p.contrato.base_mensal,p.observacao,p.vencimento.strftime('%m/%Y')])
    return arquivo_exportacao(cabecalho,linhas,'financeiro')
