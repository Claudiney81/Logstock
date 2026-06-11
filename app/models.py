from flask_login import UserMixin  # Se você tiver um modelo de usuário
from datetime import datetime
from app.extensions import db
import uuid

# 🔥 COLOCA AQUI NO TOPO
class Cliente(db.Model):
    __tablename__ = 'cliente'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)


# resto das classes abaixo...

class TokenAcessoTecnico(db.Model):
    __tablename__ = 'token_acesso_tecnico'

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(100), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    tecnico_id = db.Column(db.Integer, db.ForeignKey('tecnicos.id'), nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    tecnico = db.relationship('Tecnico', backref=db.backref('tokens_acesso', cascade='all, delete-orphan'))

# =======================
# MODELO DE TIPOS DE SERVIÇO
# =======================

class TipoServico(db.Model):
    __tablename__ = 'tipo_servico'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)

    # Define se o estoque pertence à empresa ou ao cliente
    tipo_estoque = db.Column(db.String(20), nullable=False, default='empresa')

    itens = db.relationship('Item', backref='tipo_servico_rel', lazy=True)
# =======================
# MODELO DE ITENS E ESTOQUE GERAL
# =======================

class Item(db.Model):
    __tablename__ = 'itens'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), unique=True, nullable=False)
    descricao = db.Column(db.String(200), nullable=False)
    unidade = db.Column(db.String(20), nullable=False)
    tipo_servico_id = db.Column(db.Integer, db.ForeignKey('tipo_servico.id'))
    valor = db.Column(db.Float, nullable=False)
    observacoes = db.Column(db.Text)
    eh_equipamento = db.Column(db.Boolean, default=False)
    categoria = db.Column(db.String(50), default='MATERIAL')

class Estoque(db.Model):
    __tablename__ = 'estoque'

    id = db.Column(db.Integer, primary_key=True)

    # Relacionamento com Item
    item_id = db.Column(
        db.Integer,
        db.ForeignKey('itens.id'),
        nullable=True
    )

    # Tipo de serviço
    tipo_servico_id = db.Column(
        db.Integer,
        db.ForeignKey(
            'tipo_servico.id',
            name='fk_estoque_tipo_servico'
        ),
        nullable=True
    )

    responsavel = db.Column(
        db.String(100)
    )

    # Dados principais
    quantidade = db.Column(
        db.Integer,
        default=0
    )

    quantidade_minima = db.Column(
        db.Integer,
        default=0
    )

    endereco = db.Column(
        db.String(100)
    )

    # empresa | cliente
    tipo_estoque = db.Column(
        db.String(20),
        default='empresa'
    )

    # Condição do material
    condicao_material = db.Column(
        db.String(30),
        nullable=True
    )

    # Cliente vinculado ao estoque
    cliente_id = db.Column(
        db.Integer,
        db.ForeignKey('empresas.id'),
        nullable=True
    )

    # Relacionamentos
    cliente = db.relationship(
        'Empresa',
        foreign_keys=[cliente_id],
        backref='estoques_cliente'
    )

    item = db.relationship(
        'Item',
        backref='estoques'
    )

    tipo_servico = db.relationship(
        'TipoServico',
        backref='estoques'
    )

    def __repr__(self):
        return f"<Estoque Item:{self.item_id} Qtd:{self.quantidade} Tipo:{self.tipo_estoque}>"


# =======================
# NOVA FUNCIONALIDADE: REQUISIÇÕES TÉCNICOS
# =======================

class RequisicaoTecnico(db.Model):
    __tablename__ = 'requisicoes_tecnicos'

    id = db.Column(db.Integer, primary_key=True)

    # Dados do solicitante
    solicitante_responsavel = db.Column(db.String(100), nullable=False)
    solicitante_tecnico = db.Column(db.String(100), nullable=False)

    solicitante_tecnico_id = db.Column(
        db.Integer,
        db.ForeignKey('tecnicos.id'),
        nullable=True
    )

    tecnico_rel = db.relationship(
        'Tecnico',
        foreign_keys=[solicitante_tecnico_id]
    )

    # Origem do estoque
    tipo_estoque = db.Column(
        db.String(20),
        nullable=False,
        default='empresa'
    )

    # Cliente vinculado quando o estoque for do cliente
    cliente_id = db.Column(
        db.Integer,
        db.ForeignKey('empresas.id'),
        nullable=True
    )

    cliente = db.relationship(
        'Empresa',
        foreign_keys=[cliente_id]
    )

    # O.S aberta pelo cliente
    os_cliente = db.Column(db.String(100), nullable=True)

    # Tipo de serviço
    tipo_servico = db.Column(db.String(100), nullable=False)

    # Campos adicionais
    observacao = db.Column(db.Text)
    observacao_estoque = db.Column(db.Text)
    endereco = db.Column(db.String(255))
    bairro = db.Column(db.String(100))
    codigo_imovel = db.Column(db.String(50))
    resp_projeto = db.Column(db.String(100))

    # Identifica se veio da tela mobile do técnico
    origem_mobile = db.Column(db.Boolean, default=False)

    # Assinatura
    assinatura_path = db.Column(db.String(255))
    assinatura_base64 = db.Column(db.Text)

    # Status e data
    data_hora = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default="pendente")

    # Relacionamento com os itens
    itens = db.relationship(
        "RequisicaoTecnicoItem",
        backref="requisicao",
        lazy=True,
        cascade="all, delete-orphan"
    )


class RequisicaoTecnicoItem(db.Model):
    __tablename__ = 'requisicoes_tecnicos_itens'

    id = db.Column(db.Integer, primary_key=True)

    requisicao_id = db.Column(
        db.Integer,
        db.ForeignKey('requisicoes_tecnicos.id'),
        nullable=False
    )

    codigo = db.Column(db.String(50), nullable=False)
    descricao = db.Column(db.String(200), nullable=False)
    unidade = db.Column(db.String(20), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    valor = db.Column(db.Float, nullable=False)
    quantidade_estoque = db.Column(db.Integer)
    
# =======================
# NOTAS FISCAIS DE ENTRADA
# =======================

class NotaFiscalEntrada(db.Model):
    __tablename__ = 'notas_fiscais_entrada'

    id = db.Column(db.Integer, primary_key=True)

    numero_nf = db.Column(
        db.String(50),
        nullable=False
    )

    fornecedor = db.Column(
        db.String(150),
        nullable=False
    )

    tipo_estoque = db.Column(
        db.String(20),
        nullable=False,
        default='empresa'
    )

    cliente_id = db.Column(
        db.Integer,
        db.ForeignKey('empresas.id'),
        nullable=True
    )

    ordem_servico_id = db.Column(
        db.Integer,
        db.ForeignKey('ordens_servico.id'),
        nullable=True
    )

    tipo_servico = db.Column(
        db.String(100)
    )

    tipo_servico_id = db.Column(
        db.Integer,
        db.ForeignKey(
            'tipo_servico.id',
            name='fk_nota_tipo_servico'
        )
    )

    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey('usuarios.id'),
        nullable=True
    )

    observacao = db.Column(db.Text)

    data_hora = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    tipo_servico_ref = db.relationship(
        'TipoServico',
        backref='notas_fiscais'
    )

    cliente = db.relationship(
        'Empresa',
        foreign_keys=[cliente_id],
        backref='notas_fiscais_cliente'
    )

    ordem_servico = db.relationship(
        'OrdemServico',
        foreign_keys=[ordem_servico_id]
    )

    usuario = db.relationship(
        'Usuario',
        backref='notas_fiscais_registradas'
    )

    itens = db.relationship(
        'NotaFiscalItem',
        backref='nota_fiscal',
        cascade='all, delete-orphan'
    )

    @property
    def total_calculado(self):
        return sum(
            item.quantidade * item.valor_unitario
            for item in self.itens
        )


class NotaFiscalItem(db.Model):
    __tablename__ = 'notas_fiscais_itens'

    id = db.Column(db.Integer, primary_key=True)
    nota_fiscal_id = db.Column(db.Integer, db.ForeignKey('notas_fiscais_entrada.id'))
    item_id = db.Column(db.Integer, db.ForeignKey('itens.id'))
    quantidade = db.Column(db.Integer, nullable=False)
    valor_unitario = db.Column(db.Float, nullable=False)

    item = db.relationship('Item', backref='notas_fiscais_itens')
# =======================
# EMPRESAS / PARCEIROS
# =======================
class Empresa(db.Model):
    __tablename__ = 'empresas'

    id = db.Column(db.Integer, primary_key=True)

    razao_social = db.Column(db.String(120), nullable=False)

    cnpj = db.Column(db.String(20), nullable=False)

    endereco = db.Column(db.String(255))

    contato = db.Column(db.String(100))

    email = db.Column(db.String(120))

    tipo_empresa = db.Column(db.String(20), nullable=False)

    observacoes = db.Column(db.Text)

    numero_os = db.Column(
        db.String(30),
        unique=True
    )

    status_os = db.Column(
        db.String(30),
        default='aberta'
    )

    transferencias = db.relationship(
        'TransferenciaExterna',
        back_populates='empresa',
        cascade='all, delete-orphan'
    )
# =======================
# TRANSFERÊNCIA EXTERNA
# =======================

from datetime import datetime
from app.extensions import db

class TransferenciaExterna(db.Model):
    __tablename__ = 'transferencias_externas'

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=False)
    autorizado_por = db.Column(db.String(100), nullable=False)
    retirado_por = db.Column(db.String(100), nullable=False)
    tipo_servico_id = db.Column(db.Integer, db.ForeignKey('tipo_servico.id'), nullable=False)
    data_hora = db.Column(db.DateTime, default=datetime.utcnow)

    # 🔹 NOVO CAMPO: DataURL completo do canvas ("data:image/png;base64,...")
    assinatura_base64 = db.Column(db.Text)

    # Relacionamentos
    empresa = db.relationship('Empresa', back_populates='transferencias')
    tipo_servico = db.relationship('TipoServico')
    itens = db.relationship('TransferenciaExternaItem', backref='transferencia', cascade='all, delete-orphan')

class TransferenciaExternaItem(db.Model):
    __tablename__ = 'transferencias_externas_itens'
    id = db.Column(db.Integer, primary_key=True)
    transferencia_id = db.Column(db.Integer, db.ForeignKey('transferencias_externas.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('itens.id'), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    valor_unitario = db.Column(db.Float, nullable=False)

    item = db.relationship('Item')

# =======================
# TECNICOS
# =======================

class Tecnico(db.Model):
    __tablename__ = 'tecnicos'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    matricula = db.Column(db.String(20), unique=True, nullable=False)
    cpf = db.Column(db.String(14), unique=True, nullable=False)
    telefone = db.Column(db.String(20))
    email = db.Column(db.String(100))

    # NOVO CAMPO
    funcao = db.Column(db.String(100))

    status = db.Column(db.String(10), default='Ativo')
    token = db.Column(db.String(100))

    tipo_servico_id = db.Column(db.Integer, db.ForeignKey('tipo_servico.id'))
    tipo_servico_rel = db.relationship('TipoServico')

    saldos = db.relationship(
        'SaldoTecnico',
        back_populates='tecnico',
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f"<Tecnico {self.nome} - {self.matricula}>"
# =======================
# KIT INICIAL
# =======================

class KitInicial(db.Model):
    __tablename__ = 'kits_iniciais'

    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(150), nullable=False)

    tecnico_id = db.Column(
        db.Integer,
        db.ForeignKey('tecnicos.id'),
        nullable=False
    )

    tipo_servico_id = db.Column(
        db.Integer,
        db.ForeignKey('tipo_servico.id'),
        nullable=False
    )

    observacao = db.Column(db.String(255))
    data_hora = db.Column(db.DateTime, default=datetime.utcnow)

    assinatura_base64 = db.Column(db.Text)

    tecnico = db.relationship('Tecnico')
    tipo_servico = db.relationship('TipoServico')

    itens = db.relationship(
        'KitInicialItem',
        backref='kit',
        cascade='all, delete-orphan'
    )


class KitInicialItem(db.Model):
    __tablename__ = 'kits_iniciais_itens'

    id = db.Column(db.Integer, primary_key=True)

    kit_inicial_id = db.Column(
        db.Integer,
        db.ForeignKey('kits_iniciais.id'),
        nullable=False
    )

    item_id = db.Column(
        db.Integer,
        db.ForeignKey('itens.id'),
        nullable=False
    )

    quantidade = db.Column(db.Integer, nullable=False, default=0)
    valor_unitario = db.Column(db.Float, nullable=False, default=0)

    item = db.relationship('Item')

# =======================
# MOVIMENTAÇÃO DE ESTOQUE
# =======================

class MovimentacaoEstoque(db.Model):
    __tablename__ = 'movimentacoes_estoque'

    id = db.Column(db.Integer, primary_key=True)

    origem_tipo = db.Column(db.String(20), nullable=False)
    origem_id = db.Column(db.Integer, nullable=True)

    destino_tipo = db.Column(db.String(20), nullable=False)
    destino_id = db.Column(db.Integer, nullable=True)

    tipo_servico_id = db.Column(
        db.Integer,
        db.ForeignKey('tipo_servico.id'),
        nullable=True
    )
    
    ordem_servico_id = db.Column(
    db.Integer,
    db.ForeignKey('ordens_servico.id'),
    nullable=True
    )

    ordem_servico = db.relationship(
        'OrdemServico',
        foreign_keys=[ordem_servico_id]
    )

    categoria_movimentacao = db.Column(db.String(30), nullable=True)

    categoria_movimentacao = db.Column(db.String(30), nullable=True)
    tipo_movimentacao = db.Column(db.String(30), nullable=True)
    motivo_retorno = db.Column(db.String(255), nullable=True)

    assinatura = db.Column(db.Text, nullable=True)
    assinado_por = db.Column(db.String(50), nullable=True)
    termo_pdf = db.Column(db.String(255), nullable=True)

    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey('usuarios.id'),
        nullable=True
    )

    observacao = db.Column(db.Text)
    data_hora = db.Column(db.DateTime, default=datetime.utcnow)

    email_enviado = db.Column(db.Boolean, default=False)
    data_envio_email = db.Column(db.DateTime)

    tipo_servico = db.relationship('TipoServico')
    usuario = db.relationship('Usuario')

    itens = db.relationship(
        'MovimentacaoEstoqueItem',
        backref='movimentacao',
        cascade='all, delete-orphan'
    )


class MovimentacaoEstoqueItem(db.Model):
    __tablename__ = 'movimentacoes_estoque_itens'

    id = db.Column(db.Integer, primary_key=True)

    movimentacao_id = db.Column(
        db.Integer,
        db.ForeignKey('movimentacoes_estoque.id'),
        nullable=False
    )

    item_id = db.Column(
        db.Integer,
        db.ForeignKey('itens.id'),
        nullable=False
    )

    quantidade = db.Column(db.Integer, nullable=False)

    valor_unitario = db.Column(
        db.Float,
        nullable=False,
        default=0
    )

    condicao_material = db.Column(
        db.String(30),
        nullable=True
    )

    item = db.relationship('Item')

# =======================
# USUÁRIOS DO SISTEMA
# =======================

class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)
    perfil = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='Ativo')

    tecnico_id = db.Column(db.Integer, db.ForeignKey('tecnicos.id'))  # ← ADICIONAR ISSO
    tecnico = db.relationship('Tecnico')  # ← RELACIONAMENTO OPCIONAL

    def __repr__(self):
        return f"<Usuario {self.nome} ({self.email})>"

# =======================
# BAIXAS MANUAIS / MOBILE DO SALDO TÉCNICO
# =======================

class BaixaTecnica(db.Model):
    __tablename__ = 'baixas_tecnicas'

    id = db.Column(db.Integer, primary_key=True)

    tecnico_id = db.Column(
        db.Integer,
        db.ForeignKey('tecnicos.id'),
        nullable=False
    )

    tipo_servico_id = db.Column(
        db.Integer,
        db.ForeignKey('tipo_servico.id'),
        nullable=False
    )

    cliente_id = db.Column(
        db.Integer,
        db.ForeignKey('empresas.id'),
        nullable=True
    )

    ordem_servico_id = db.Column(
        db.Integer,
        db.ForeignKey('ordens_servico.id'),
        nullable=True
    )

    ordem_servico = db.relationship(
        'OrdemServico',
        foreign_keys=[ordem_servico_id]
    )
    os_cliente = db.Column(db.String(150), nullable=True)

    endereco = db.Column(db.String(200), nullable=True)
    bairro = db.Column(db.String(100), nullable=True)
    codigo_imovel = db.Column(db.String(100), nullable=True)

    responsavel = db.Column(db.String(100))
    observacao = db.Column(db.Text)

    data_hora = db.Column(db.DateTime, default=datetime.utcnow)

    status = db.Column(db.String(30), default="pendente")
    motivo_recusa = db.Column(db.Text, nullable=True)
    visualizado_tecnico = db.Column(db.Boolean, default=False)

    origem_mobile = db.Column(db.Boolean, default=False)

    tecnico = db.relationship('Tecnico', backref='baixas_tecnicas')
    tipo_servico = db.relationship('TipoServico')
    cliente = db.relationship('Empresa')

    itens = db.relationship(
        'BaixaTecnicaItem',
        backref='baixa_tecnica',
        cascade='all, delete-orphan'
    )


class BaixaTecnicaItem(db.Model):
    __tablename__ = 'baixas_tecnicas_itens'

    id = db.Column(db.Integer, primary_key=True)

    baixa_tecnica_id = db.Column(
        db.Integer,
        db.ForeignKey('baixas_tecnicas.id'),
        nullable=False
    )

    item_id = db.Column(
        db.Integer,
        db.ForeignKey('itens.id'),
        nullable=False
    )

    quantidade = db.Column(db.Integer, nullable=False)
    quantidade_aprovada = db.Column(db.Integer, default=0)

    valor_unitario = db.Column(db.Numeric(10, 2), default=0)
    valor_total = db.Column(db.Numeric(10, 2), default=0)

    tipo_estoque = db.Column(db.String(20), default='empresa')

    cliente_estoque_id = db.Column(
        db.Integer,
        db.ForeignKey('empresas.id'),
        nullable=True
    )

    status = db.Column(db.String(30), default="pendente")
    motivo_recusa = db.Column(db.Text, nullable=True)

    item = db.relationship('Item')
    cliente_estoque = db.relationship('Empresa')
    
class BaixaTecnicaFoto(db.Model):
    __tablename__ = 'baixas_tecnicas_fotos'

    id = db.Column(db.Integer, primary_key=True)

    baixa_tecnica_id = db.Column(
        db.Integer,
        db.ForeignKey('baixas_tecnicas.id'),
        nullable=False
    )

    caminho_arquivo = db.Column(db.String(255), nullable=False)
    legenda = db.Column(db.String(150), nullable=True)
    data_upload = db.Column(db.DateTime, default=datetime.utcnow)

    baixa_tecnica = db.relationship(
        'BaixaTecnica',
        backref=db.backref(
            'fotos',
            cascade='all, delete-orphan'
        )
    )
    
    # NOVO VÍNCULO COM O.S
class OrdemServico(db.Model):
    __tablename__ = 'ordens_servico'

    id = db.Column(db.Integer, primary_key=True)

    numero_os = db.Column(
        db.String(30),
        unique=True,
        nullable=False
    )

    cliente_id = db.Column(
        db.Integer,
        db.ForeignKey('empresas.id'),
        nullable=True
    )

    tipo_servico_id = db.Column(
        db.Integer,
        db.ForeignKey('tipo_servico.id'),
        nullable=True
    )

    endereco = db.Column(db.String(200), nullable=True)
    responsavel = db.Column(db.String(100), nullable=True)
    observacao = db.Column(db.Text, nullable=True)

    status = db.Column(
        db.String(30),
        default='aberta'
    )

    data_abertura = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    cliente = db.relationship(
        'Empresa',
        foreign_keys=[cliente_id],
        backref='ordens_servico'
    )

    tipo_servico = db.relationship(
        'TipoServico',
        foreign_keys=[tipo_servico_id],
        backref='ordens_servico'
    )  
    


# ✅ INVENTÁRIO TÉCNICO (deixe como está para localizar melhor)
class InventarioTecnico(db.Model):
    __tablename__ = 'inventarios_tecnicos'

    id = db.Column(db.Integer, primary_key=True)

    tecnico_id = db.Column(db.Integer, db.ForeignKey('tecnicos.id'), nullable=False)
    tipo_servico_id = db.Column(db.Integer, db.ForeignKey('tipo_servico.id'), nullable=False)

    data = db.Column(db.DateTime, default=datetime.utcnow)
    responsavel = db.Column(db.String(100))
    observacao = db.Column(db.String(255))

    tecnico = db.relationship('Tecnico', backref='inventarios')
    tipo_servico = db.relationship('TipoServico')

    itens = db.relationship(
        'InventarioTecnicoItem',
        backref='inventario',
        cascade='all, delete-orphan'
    )


class InventarioTecnicoItem(db.Model):
    __tablename__ = 'inventarios_tecnicos_itens'

    id = db.Column(db.Integer, primary_key=True)

    inventario_id = db.Column(
        db.Integer,
        db.ForeignKey('inventarios_tecnicos.id'),
        nullable=False
    )

    item_id = db.Column(
        db.Integer,
        db.ForeignKey('itens.id'),
        nullable=False
    )

    # NOVO
    quantidade_existente = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    quantidade_contada = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    item = db.relationship('Item')

class InventarioEstoque(db.Model):
    __tablename__ = 'inventario_estoque'

    id = db.Column(db.Integer, primary_key=True)
    data_hora = db.Column(db.DateTime, default=datetime.utcnow)
    responsavel = db.Column(db.String(100), nullable=False)
    observacao = db.Column(db.String(255), nullable=True)

    tipo_estoque = db.Column(db.String(20), nullable=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=True)
    cliente = db.relationship('Empresa', foreign_keys=[cliente_id])

    tipo_servico_id = db.Column(db.Integer, db.ForeignKey('tipo_servico.id'), nullable=True)
    tipo_servico = db.relationship('TipoServico', foreign_keys=[tipo_servico_id])

    itens = db.relationship(
        'InventarioEstoqueItem',
        backref='inventario',
        cascade='all, delete-orphan'
    )

class InventarioEstoqueItem(db.Model):
    __tablename__ = 'inventario_estoque_item'

    id = db.Column(db.Integer, primary_key=True)
    inventario_id = db.Column(db.Integer, db.ForeignKey('inventario_estoque.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('itens.id'), nullable=False)
    quantidade_estoque = db.Column(db.Integer, nullable=False)
    quantidade_contada = db.Column(db.Integer, nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))

    item = db.relationship('Item')
    usuario = db.relationship('Usuario')

# =======================
# SALDO TÉCNICO
# =======================

class SaldoTecnico(db.Model):
    __tablename__ = 'saldo_tecnico'

    id = db.Column(db.Integer, primary_key=True)

    tecnico_id = db.Column(
        db.Integer,
        db.ForeignKey('tecnicos.id'),
        nullable=False
    )

    item_id = db.Column(
        db.Integer,
        db.ForeignKey('itens.id'),
        nullable=False
    )

    tipo_servico_id = db.Column(
        db.Integer,
        db.ForeignKey('tipo_servico.id'),
        nullable=False
    )

    # Quantidade atual em posse do técnico
    quantidade = db.Column(
        db.Integer,
        default=0
    )

    # Quantidade mínima para reposição
    quantidade_minima = db.Column(
        db.Integer,
        default=0
    )

    # Origem do saldo
    # empresa | cliente
    tipo_estoque = db.Column(
        db.String(20),
        default='empresa'
    )

    # Cliente vinculado ao saldo
    cliente_id = db.Column(
        db.Integer,
        db.ForeignKey('empresas.id'),
        nullable=True
    )

    # O.S vinculada ao saldo
    ordem_servico_id = db.Column(
        db.Integer,
        db.ForeignKey('ordens_servico.id'),
        nullable=True
    )

    # Dados da obra
    endereco = db.Column(
        db.String(200)
    )

    bairro = db.Column(
        db.String(100)
    )

    codigo_imovel = db.Column(
        db.String(100)
    )

    tecnico = db.relationship(
        'Tecnico',
        back_populates='saldos'
    )

    item = db.relationship(
        'Item'
    )

    tipo_servico = db.relationship(
        'TipoServico'
    )

    cliente = db.relationship(
        'Empresa'
    )

    ordem_servico = db.relationship(
        'OrdemServico'
    )
    
# =======================
# CONTROLE DE FERRAMENTAS / EPIs
# =======================

class EquipamentoTecnico(db.Model):
    __tablename__ = 'equipamentos_tecnicos'

    id = db.Column(db.Integer, primary_key=True)

    item_id = db.Column(db.Integer, db.ForeignKey('itens.id'), nullable=False)
    tecnico_id = db.Column(db.Integer, db.ForeignKey('tecnicos.id'), nullable=True)

    categoria = db.Column(db.String(20), default='ferramenta')
    local = db.Column(db.String(100))

    status = db.Column(db.String(30), default='almoxarifado')
    quantidade = db.Column(db.Integer, default=1)

    valor_unitario = db.Column(db.Float, default=0)
    valor_total = db.Column(db.Float, default=0)

    data_hora = db.Column(db.DateTime, default=datetime.utcnow)

    item = db.relationship('Item')
    tecnico = db.relationship('Tecnico')

    def __repr__(self):
        return f"<EquipamentoTecnico {self.item.descricao if self.item else '-'} - {self.status}>"


class HistoricoEquipamento(db.Model):
    __tablename__ = 'historico_equipamentos'

    id = db.Column(db.Integer, primary_key=True)

    item_id = db.Column(db.Integer, db.ForeignKey('itens.id'), nullable=True)
    tecnico_id = db.Column(db.Integer, db.ForeignKey('tecnicos.id'), nullable=True)

    categoria = db.Column(db.String(20), default='ferramenta')

    tipo_movimentacao = db.Column(db.String(30), nullable=False)
    local = db.Column(db.String(100))
    status = db.Column(db.String(30), nullable=False)

    motivo = db.Column(db.String(150), nullable=True)
    observacao = db.Column(db.Text)

    quantidade = db.Column(db.Integer, default=1)

    valor_unitario = db.Column(db.Float, default=0)
    valor_total = db.Column(db.Float, default=0)
    valor_desconto = db.Column(db.Float, default=0)

    termo_pdf = db.Column(db.String(255), nullable=True)
    assinatura_tecnico = db.Column(db.Text, nullable=True)
    assinatura_logistica = db.Column(db.Text, nullable=True)
    email_enviado = db.Column(db.Boolean, default=False)

    data_hora = db.Column(db.DateTime, default=datetime.utcnow)

    item = db.relationship('Item')
    tecnico = db.relationship('Tecnico')

    itens = db.relationship(
        'HistoricoEquipamentoItem',
        back_populates='historico',
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f"<HistoricoEquipamento {self.id} - {self.tipo_movimentacao}>"


class HistoricoEquipamentoItem(db.Model):
    __tablename__ = 'historico_equipamento_itens'

    id = db.Column(db.Integer, primary_key=True)

    historico_id = db.Column(
        db.Integer,
        db.ForeignKey('historico_equipamentos.id'),
        nullable=False
    )

    item_id = db.Column(
        db.Integer,
        db.ForeignKey('itens.id'),
        nullable=False
    )

    categoria = db.Column(db.String(20))
    quantidade = db.Column(db.Integer, default=1)

    valor_unitario = db.Column(db.Float, default=0)
    valor_total = db.Column(db.Float, default=0)

    historico = db.relationship(
        'HistoricoEquipamento',
        back_populates='itens'
    )

    item = db.relationship('Item')
    
    # ==================================================
# MÓDULO FROTA
# ==================================================

class Veiculo(db.Model):
    __tablename__ = 'veiculos'

    id = db.Column(db.Integer, primary_key=True)

    placa = db.Column(db.String(20), nullable=False, unique=True)
    marca = db.Column(db.String(100), nullable=False)
    modelo = db.Column(db.String(100), nullable=False)
    ano = db.Column(db.Integer, nullable=True)
    cor = db.Column(db.String(50), nullable=True)

    tipo = db.Column(db.String(50), nullable=True)
    quilometragem_atual = db.Column(db.Integer, default=0)

    responsavel = db.Column(db.String(150), nullable=True)

    status = db.Column(db.String(30), default='ativo')
    observacao = db.Column(db.Text, nullable=True)

    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)

    manutencoes = db.relationship(
        'ManutencaoVeiculo',
        backref='veiculo',
        lazy=True,
        cascade='all, delete-orphan'
    )

    abastecimentos = db.relationship(
        'AbastecimentoVeiculo',
        backref='veiculo',
        lazy=True,
        cascade='all, delete-orphan'
    )


class ManutencaoVeiculo(db.Model):
    __tablename__ = 'manutencoes_veiculos'

    id = db.Column(db.Integer, primary_key=True)

    veiculo_id = db.Column(
        db.Integer,
        db.ForeignKey('veiculos.id'),
        nullable=False
    )

    tipo_manutencao = db.Column(db.String(100), nullable=False)
    data_manutencao = db.Column(db.Date, nullable=False)

    quilometragem = db.Column(db.Integer, nullable=True)
    valor = db.Column(db.Numeric(10, 2), default=0)

    oficina = db.Column(db.String(150), nullable=True)
    responsavel = db.Column(db.String(150), nullable=True)

    observacao = db.Column(db.Text, nullable=True)

    data_registro = db.Column(db.DateTime, default=datetime.utcnow)


class AbastecimentoVeiculo(db.Model):
    __tablename__ = 'abastecimentos_veiculos'

    id = db.Column(db.Integer, primary_key=True)

    veiculo_id = db.Column(
        db.Integer,
        db.ForeignKey('veiculos.id'),
        nullable=False
    )

    data_abastecimento = db.Column(
        db.Date,
        nullable=False
    )

    quilometragem = db.Column(
        db.Integer,
        nullable=True
    )

    litros = db.Column(
        db.Numeric(10, 2),
        nullable=True
    )

    valor_total = db.Column(
        db.Numeric(10, 2),
        nullable=True
    )

    posto = db.Column(
        db.String(150),
        nullable=True
    )

    responsavel = db.Column(
        db.String(150),
        nullable=True
    )

    observacao = db.Column(
        db.Text,
        nullable=True
    )

    data_registro = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


# ==================================================
# DOCUMENTOS DA FROTA
# ==================================================

class DocumentoVeiculo(db.Model):
    __tablename__ = 'documentos_veiculos'

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    veiculo_id = db.Column(
        db.Integer,
        db.ForeignKey('veiculos.id'),
        nullable=False
    )

    tipo_documento = db.Column(
        db.String(100),
        nullable=False
    )

    descricao = db.Column(
        db.String(200),
        nullable=True
    )

    nome_arquivo = db.Column(
        db.String(255),
        nullable=False
    )

    caminho_arquivo = db.Column(
        db.String(255),
        nullable=False
    )

    data_emissao = db.Column(
        db.Date,
        nullable=True
    )

    data_validade = db.Column(
        db.Date,
        nullable=True
    )

    observacao = db.Column(
        db.Text,
        nullable=True
    )

    data_upload = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    veiculo = db.relationship(
        'Veiculo',
        backref=db.backref(
            'documentos',
            lazy=True,
            cascade='all, delete-orphan'
        )
    )
    
    # ==================================================
# VISTORIA DE VEÍCULO
# ==================================================

class VistoriaVeiculo(db.Model):
    __tablename__ = "vistorias_veiculos"

    id = db.Column(db.Integer, primary_key=True)

    veiculo_id = db.Column(
        db.Integer,
        db.ForeignKey("veiculos.id"),
        nullable=False
    )

    tecnico_id = db.Column(
        db.Integer,
        db.ForeignKey("tecnicos.id"),
        nullable=False
    )

    tipo_vistoria = db.Column(db.String(20), nullable=False)

    responsavel = db.Column(db.String(150), nullable=False)

    data_hora = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    km_atual = db.Column(db.Integer, nullable=True)
    combustivel = db.Column(db.String(50), nullable=True)
    local_vistoria = db.Column(db.String(150), nullable=True)

    observacao_geral = db.Column(db.Text, nullable=True)

    assinatura_tecnico = db.Column(db.Text, nullable=True)
    assinatura_responsavel = db.Column(db.Text, nullable=True)

    veiculo = db.relationship("Veiculo", backref="vistorias")
    tecnico = db.relationship("Tecnico", backref="vistorias_veiculo")


class VistoriaVeiculoItem(db.Model):
    __tablename__ = "vistorias_veiculos_itens"

    id = db.Column(db.Integer, primary_key=True)

    vistoria_id = db.Column(
        db.Integer,
        db.ForeignKey("vistorias_veiculos.id"),
        nullable=False
    )

    item = db.Column(db.String(120), nullable=False)

    status = db.Column(db.String(30), nullable=False)

    observacao = db.Column(db.Text, nullable=True)

    vistoria = db.relationship(
        "VistoriaVeiculo",
        backref=db.backref(
            "itens",
            cascade="all, delete-orphan"
        )
    )


class VistoriaVeiculoFoto(db.Model):
    __tablename__ = "vistorias_veiculos_fotos"

    id = db.Column(db.Integer, primary_key=True)

    vistoria_id = db.Column(
        db.Integer,
        db.ForeignKey("vistorias_veiculos.id"),
        nullable=False
    )

    descricao = db.Column(db.String(120), nullable=True)
    caminho_arquivo = db.Column(db.String(255), nullable=False)

    vistoria = db.relationship(
        "VistoriaVeiculo",
        backref=db.backref(
            "fotos",
            cascade="all, delete-orphan"
        )
    )