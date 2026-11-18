import unicodedata

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import FunctionElement
from sqlalchemy import String
import sqlite3


def normalizar_busca(valor):
    return ''.join(c for c in unicodedata.normalize('NFD', str(valor or '').casefold())
                   if not unicodedata.combining(c))


@event.listens_for(Engine, 'connect')
def registrar_normalizacao(conexao, registro):
    if isinstance(conexao, sqlite3.Connection):
        conexao.create_function('normalizar_busca', 1, normalizar_busca, deterministic=True)


class TextoBusca(FunctionElement):
    type = String()
    inherit_cache = True


@compiles(TextoBusca, 'sqlite')
def compilar_sqlite(elemento, compilador, **kwargs):
    return 'normalizar_busca(%s)' % compilador.process(list(elemento.clauses)[0], **kwargs)


@compiles(TextoBusca)
def compilar_padrao(elemento, compilador, **kwargs):
    coluna = compilador.process(list(elemento.clauses)[0], **kwargs)
    return "lower(translate(%s, 'ÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑáàâãäéèêëíìîïóòôõöúùûüçñ', 'AAAAAEEEEIIIIOOOOOUUUUCNaaaaaeeeeiiiiooooouuuucn'))" % coluna


def contem_busca(coluna, termo):
    return TextoBusca(coluna).contains(normalizar_busca(termo), autoescape=True)
