import click
import os
import shutil
from datetime import datetime
from flask.cli import with_appcontext
from sqlalchemy import text
from app.extensions import db
from app.models import (
    AbastecimentoVeiculo,
    BaixaTecnica,
    BaixaTecnicaFoto,
    BaixaTecnicaItem,
    DocumentoVeiculo,
    Empresa,
    EquipamentoTecnico,
    Estoque,
    HistoricoEquipamento,
    HistoricoEquipamentoItem,
    InventarioEstoque,
    InventarioEstoqueItem,
    InventarioTecnico,
    InventarioTecnicoItem,
    Item,
    KitInicial,
    KitInicialItem,
    ManutencaoVeiculo,
    MovimentacaoEstoque,
    MovimentacaoEstoqueItem,
    NotaFiscalEntrada,
    NotaFiscalItem,
    OrdemServico,
    RequisicaoTecnico,
    RequisicaoTecnicoItem,
    SaldoTecnico,
    Tecnico,
    TipoServico,
    TokenAcessoTecnico,
    TransferenciaExterna,
    TransferenciaExternaItem,
    Usuario,
    Veiculo,
    VistoriaVeiculo,
    VistoriaVeiculoFoto,
    VistoriaVeiculoItem,
)
from werkzeug.security import generate_password_hash

@click.command("init-db")
@with_appcontext
def init_db():
    db.create_all()
    click.echo("Tabelas criadas com sucesso.")

@click.command("seed-dados")
@with_appcontext
def seed_dados():
    if not TipoServico.query.filter_by(nome='GPON MDU F').first():
        tipo1 = TipoServico(nome='GPON MDU F', empresa='Empresa A')
        tipo2 = TipoServico(nome='REDE INTERNA', empresa='Empresa B')
        db.session.add_all([tipo1, tipo2])
        db.session.commit()
        click.echo("Tipos de serviço adicionados.")

    tipo_fibra = TipoServico.query.filter_by(nome='GPON MDU F').first()

    if not Item.query.filter_by(codigo='A123').first():
        item1 = Item(codigo='A123', descricao='Cabo de Fibra', unidade='m', tipo_servico_id=tipo_fibra.id, valor=10.5)
        item2 = Item(codigo='B456', descricao='Conector Óptico', unidade='un', tipo_servico_id=tipo_fibra.id, valor=2.75)
        db.session.add_all([item1, item2])
        click.echo("Itens adicionados.")

    if not Empresa.query.filter_by(cnpj='12.345.678/0001-90').first():
        empresa1 = Empresa(
            razao_social='Parceiro Instalações LTDA',
            cnpj='12.345.678/0001-90',
            endereco='Rua das Instalações, 123',
            contato='(11) 99999-0001',
            tipo_servico='instalação',
            observacoes='Empresa terceirizada de instalação'
        )
        empresa2 = Empresa(
            razao_social='Manutenção Total ME',
            cnpj='98.765.432/0001-10',
            endereco='Av. Manutenção, 456',
            contato='(11) 88888-0002',
            tipo_servico='manutenção',
            observacoes='Responsável por manutenção preventiva'
        )
        db.session.add_all([empresa1, empresa2])
        click.echo("Empresas adicionadas.")

    db.session.commit()
    click.echo("Seed concluído.")

@click.command("criar-usuario")
@with_appcontext
def criar_usuario():
    nome = click.prompt("Nome completo")
    email = click.prompt("Email")
    senha = click.prompt("Senha", hide_input=True, confirmation_prompt=True)
    perfil = click.prompt("Perfil", type=click.Choice(['admin', 'estoque', 'tecnico'], case_sensitive=False))

    if Usuario.query.filter_by(email=email).first():
        click.echo("Esse e-mail já está em uso.")
        return

    novo = Usuario(
        nome=nome,
        email=email,
        senha_hash=generate_password_hash(senha),
        perfil=perfil
    )
    db.session.add(novo)
    db.session.commit()
    click.echo(f"Usuário '{email}' criado com sucesso.")

@click.command("editar-usuario")
@click.argument("email")
@with_appcontext
def editar_usuario(email):
    usuario = Usuario.query.filter_by(email=email).first()
    if not usuario:
        click.echo(f"Usuário com e-mail '{email}' não encontrado.")
        return

    novo_nome = click.prompt("Novo nome", default=usuario.nome)
    nova_senha = click.prompt("Nova senha", hide_input=True, confirmation_prompt=True)
    novo_perfil = click.prompt("Novo perfil", type=click.Choice(['admin', 'estoque', 'tecnico'], case_sensitive=False), default=usuario.perfil)

    usuario.nome = novo_nome
    usuario.senha_hash = generate_password_hash(nova_senha)
    usuario.perfil = novo_perfil

    db.session.commit()
    click.echo(f"Usuário '{email}' atualizado com sucesso.")

@click.command("listar-usuarios")
@with_appcontext
def listar_usuarios():
    usuarios = Usuario.query.all()
    if not usuarios:
        click.echo("Nenhum usuário encontrado.")
        return
    for u in usuarios:
        click.echo(f"Email: {u.email}, Nome: {u.nome}, Perfil: {u.perfil}")

@click.command("deletar-usuario")
@click.argument("email")
@with_appcontext
def deletar_usuario(email):
    usuario = Usuario.query.filter_by(email=email).first()
    if not usuario:
        click.echo("Usuário não encontrado.")
        return
    db.session.delete(usuario)
    db.session.commit()
    click.echo(f"Usuário '{email}' excluído.")


def _backup_sqlite_database():
    database_path = db.engine.url.database

    if not database_path:
        return None

    if not os.path.isabs(database_path):
        database_path = os.path.abspath(database_path)

    if not os.path.exists(database_path):
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(
        os.getcwd(),
        "backups",
        f"producao_preparar_empresa_{timestamp}",
    )
    os.makedirs(backup_dir, exist_ok=True)

    backup_path = os.path.join(
        backup_dir,
        os.path.basename(database_path),
    )
    shutil.copy2(database_path, backup_path)

    return backup_path


def _is_tecnico_preservado(tecnico):
    texto = " ".join(
        [
            tecnico.nome or "",
            tecnico.email or "",
            tecnico.funcao or "",
            tecnico.matricula or "",
        ]
    ).lower()

    return "fernando" in texto or "instalador" in texto


def _table_count(table_name):
    return db.session.execute(
        text(f'SELECT COUNT(*) FROM "{table_name}"')
    ).scalar()


def _delete_table(table_name):
    db.session.execute(text(f'DELETE FROM "{table_name}"'))


@click.command("preparar-empresa")
@click.option(
    "--confirm",
    default="",
    help="Use --confirm PREPARAR_EMPRESA para executar a limpeza.",
)
@with_appcontext
def preparar_empresa(confirm):
    if confirm != "PREPARAR_EMPRESA":
        click.echo("Nada executado.")
        click.echo("Para limpar, rode: flask preparar-empresa --confirm PREPARAR_EMPRESA")
        return

    backup_path = _backup_sqlite_database()

    delete_order = [
        VistoriaVeiculoFoto,
        VistoriaVeiculoItem,
        VistoriaVeiculo,
        DocumentoVeiculo,
        AbastecimentoVeiculo,
        ManutencaoVeiculo,
        Veiculo,
        TransferenciaExternaItem,
        TransferenciaExterna,
        KitInicialItem,
        KitInicial,
        InventarioEstoqueItem,
        InventarioEstoque,
        InventarioTecnicoItem,
        InventarioTecnico,
        NotaFiscalItem,
        NotaFiscalEntrada,
        RequisicaoTecnicoItem,
        RequisicaoTecnico,
        BaixaTecnicaFoto,
        BaixaTecnicaItem,
        BaixaTecnica,
        MovimentacaoEstoqueItem,
        MovimentacaoEstoque,
        HistoricoEquipamentoItem,
        HistoricoEquipamento,
        EquipamentoTecnico,
        SaldoTecnico,
        Estoque,
        OrdemServico,
    ]

    deleted_counts = {}

    try:
        for model in delete_order:
            table_name = model.__tablename__
            count = _table_count(table_name)
            if count:
                _delete_table(table_name)
            deleted_counts[table_name] = count

        clientes = Empresa.query.filter(
            db.func.lower(Empresa.tipo_empresa) == "cliente"
        ).all()

        deleted_counts["empresas_cliente"] = len(clientes)

        for cliente in clientes:
            db.session.delete(cliente)

        tecnicos = Tecnico.query.all()
        tecnicos_preservados = [
            tecnico for tecnico in tecnicos if _is_tecnico_preservado(tecnico)
        ]

        preserve_tecnico_ids = {
            tecnico.id for tecnico in tecnicos_preservados
        }

        usuarios_removidos = 0

        for usuario in Usuario.query.all():
            perfil = (usuario.perfil or "").lower()

            if perfil == "admin":
                continue

            if perfil == "tecnico" and usuario.tecnico_id in preserve_tecnico_ids:
                continue

            db.session.delete(usuario)
            usuarios_removidos += 1

        tecnicos_removidos = 0

        for tecnico in tecnicos:
            if tecnico.id in preserve_tecnico_ids:
                continue

            TokenAcessoTecnico.query.filter_by(tecnico_id=tecnico.id).delete(
                synchronize_session=False
            )
            db.session.delete(tecnico)
            tecnicos_removidos += 1

        db.session.commit()

    except Exception:
        db.session.rollback()
        raise

    click.echo("Limpeza concluída.")

    if backup_path:
        click.echo(f"Backup criado em: {backup_path}")

    click.echo("Preservado: fornecedores, itens, tipos de serviço, admins e Fernando/Instalador.")
    click.echo(f"Técnicos removidos: {tecnicos_removidos}")
    click.echo(f"Usuários removidos: {usuarios_removidos}")

    for table_name, count in deleted_counts.items():
        click.echo(f"{table_name}: {count}")
