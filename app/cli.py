import click
import os
import shutil
from datetime import datetime
from flask.cli import with_appcontext
from sqlalchemy import inspect, text
from app.extensions import db
from app.utils.backup_drive import enviar_backup_google_drive
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


def _database_path():
    database_path = db.engine.url.database

    if not database_path:
        return None

    return os.path.abspath(database_path)


def _backup_drive_status():
    database_path = _database_path()
    credentials_file = os.getenv("GOOGLE_DRIVE_CREDENTIALS_FILE")
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

    return {
        "database_path": database_path,
        "database_exists": bool(database_path and os.path.exists(database_path)),
        "credentials_file": credentials_file,
        "credentials_exists": bool(
            credentials_file and os.path.exists(credentials_file)
        ),
        "folder_id_configured": bool(folder_id),
    }


@click.command("auditar-backup-drive")
@with_appcontext
def auditar_backup_drive():
    status = _backup_drive_status()

    click.echo("Auditoria do backup Google Drive:")
    click.echo(f"Banco: {status['database_path']}")
    click.echo(f"Banco existe: {status['database_exists']}")
    click.echo(f"Credenciais: {status['credentials_file']}")
    click.echo(f"Credenciais existem: {status['credentials_exists']}")
    click.echo(f"Pasta do Drive configurada: {status['folder_id_configured']}")


@click.command("backup-drive")
@with_appcontext
def backup_drive():
    status = _backup_drive_status()

    if not status["database_exists"]:
        raise click.ClickException(
            f"Banco não encontrado: {status['database_path']}"
        )

    arquivo_id = enviar_backup_google_drive(status["database_path"])

    click.echo("Backup enviado para o Google Drive.")
    click.echo(f"Banco: {status['database_path']}")
    click.echo(f"Arquivo ID: {arquivo_id}")


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


OPERATIONAL_TABLES = [
    "vistorias_veiculos_fotos",
    "vistorias_veiculos_itens",
    "vistorias_veiculos",
    "documentos_veiculos",
    "abastecimentos_veiculos",
    "manutencoes_veiculos",
    "veiculos",
    "transferencias_internas_itens",
    "transferencias_internas",
    "transferencias_externas_itens",
    "transferencias_externas",
    "kits_iniciais_itens",
    "kits_iniciais",
    "inventario_estoque_item",
    "inventario_estoque",
    "inventarios_tecnicos_itens",
    "inventarios_tecnicos",
    "notas_fiscais_itens",
    "notas_fiscais_entrada",
    "requisicoes_tecnicos_itens",
    "requisicoes_tecnicos",
    "baixas_tecnicas_fotos",
    "baixas_tecnicas_itens",
    "baixas_tecnicas",
    "movimentacoes_estoque_itens",
    "movimentacoes_estoque",
    "historico_equipamento_itens",
    "historico_equipamentos",
    "equipamentos_tecnicos",
    "saldo_tecnico",
    "estoque",
    "ordens_servico",
    "cliente",
]


PRESERVED_TABLES = {
    "alembic_version",
    "empresas",
    "itens",
    "tecnicos",
    "tipo_servico",
    "token_acesso_tecnico",
    "usuarios",
}


def _existing_tables():
    return set(inspect(db.engine).get_table_names())


def _is_operational_table(table_name):
    return table_name not in PRESERVED_TABLES


def _table_delete_priority(table_name, dependency_depths=None):
    child_markers = ("_itens", "_item", "_fotos", "_foto", "_documentos")
    child_score = any(marker in table_name for marker in child_markers)
    dependency_depth = (dependency_depths or {}).get(table_name, 0)
    return (-dependency_depth, 0 if child_score else 1, -len(table_name), table_name)


def _dependency_depths(table_names):
    tables = set(table_names)
    inspector = inspect(db.engine)
    dependencies = {}

    for table_name in tables:
        dependencies[table_name] = {
            fk["referred_table"]
            for fk in inspector.get_foreign_keys(table_name)
            if fk.get("referred_table") in tables
        }

    cache = {}

    def depth(table_name, visiting=None):
        if table_name in cache:
            return cache[table_name]

        visiting = visiting or set()
        if table_name in visiting:
            return 0

        visiting.add(table_name)
        value = 0

        for parent_table in dependencies.get(table_name, set()):
            value = max(value, 1 + depth(parent_table, visiting))

        visiting.remove(table_name)
        cache[table_name] = value
        return value

    return {
        table_name: depth(table_name)
        for table_name in tables
    }


def _operational_tables_to_clean():
    tables = _existing_tables()
    ordered_tables = [
        table_name
        for table_name in OPERATIONAL_TABLES
        if table_name in tables
    ]

    dynamic_table_names = {
        table_name
        for table_name in tables
        if _is_operational_table(table_name)
        and table_name not in ordered_tables
    }

    dependency_depths = _dependency_depths(dynamic_table_names)
    dynamic_tables = sorted(
        dynamic_table_names,
        key=lambda table_name: _table_delete_priority(
            table_name,
            dependency_depths,
        ),
    )

    return ordered_tables + dynamic_tables


def _table_count(table_name):
    return db.session.execute(
        text(f'SELECT COUNT(*) FROM "{table_name}"')
    ).scalar()


def _delete_table(table_name):
    db.session.execute(text(f'DELETE FROM "{table_name}"'))


def _count_empresas_por_tipo(tipo_empresa):
    if "empresas" not in _existing_tables():
        return 0

    return db.session.execute(
        text(
            "SELECT COUNT(*) FROM empresas "
            "WHERE lower(coalesce(tipo_empresa, '')) = :tipo_empresa"
        ),
        {"tipo_empresa": tipo_empresa},
    ).scalar()


def _auditoria_preparar_empresa():
    counts = {}

    for table_name in _operational_tables_to_clean():
        counts[table_name] = _table_count(table_name)

    tables = _existing_tables()
    for table_name in ["usuarios", "tecnicos", "empresas", "itens", "tipo_servico"]:
        if table_name in tables:
            counts[table_name] = _table_count(table_name)

    if "empresas" in tables:
        counts["empresas_cliente"] = _count_empresas_por_tipo("cliente")
        counts["empresas_fornecedor"] = _count_empresas_por_tipo("fornecedor")

    return counts


@click.command("auditar-preparar-empresa")
@with_appcontext
def auditar_preparar_empresa():
    click.echo("Auditoria do banco para preparar uso da empresa:")

    for table_name, count in _auditoria_preparar_empresa().items():
        click.echo(f"{table_name}: {count}")


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
    before_counts = _auditoria_preparar_empresa()
    deleted_counts = {}

    try:
        for table_name in _operational_tables_to_clean():
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

    after_counts = _auditoria_preparar_empresa()

    click.echo("Limpeza concluída.")

    if backup_path:
        click.echo(f"Backup criado em: {backup_path}")

    click.echo("Preservado: fornecedores, itens, tipos de serviço, admins e Fernando/Instalador.")
    click.echo(f"Técnicos removidos: {tecnicos_removidos}")
    click.echo(f"Usuários removidos: {usuarios_removidos}")

    click.echo("Antes:")
    for table_name, count in before_counts.items():
        click.echo(f"{table_name}: {count}")

    click.echo("Depois:")
    for table_name, count in after_counts.items():
        click.echo(f"{table_name}: {count}")

    click.echo("Removidos:")
    for table_name, count in deleted_counts.items():
        click.echo(f"{table_name}: {count}")
