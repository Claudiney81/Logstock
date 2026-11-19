from zipfile import BadZipFile, ZipFile
from xml.etree.ElementTree import ParseError

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException


LIMITE_ARQUIVO = 25 * 1024 * 1024


def chave_cliente(nome):
    return ' '.join(nome.split()).casefold()


def ler_clientes(planilha):
    planilha.seek(0, 2)
    tamanho = planilha.tell()
    planilha.seek(0)
    if tamanho > LIMITE_ARQUIVO:
        raise ValueError('Selecione um arquivo Excel de até 25 MiB.')

    try:
        with ZipFile(planilha) as arquivo:
            if sum(item.file_size for item in arquivo.infolist()) > 384 * 1024 * 1024:
                raise ValueError('A planilha é grande demais para processamento.')
        planilha.seek(0)
        livro = load_workbook(planilha, read_only=True, data_only=True, keep_links=False)
        try:
            if 'Cadastro' not in livro.sheetnames:
                raise ValueError('A planilha precisa conter a aba Cadastro.')
            aba = livro['Cadastro']
            cabecalho = next(aba.values, ())
            colunas = [
                indice for indice, valor in enumerate(cabecalho, 1)
                if isinstance(valor, str) and chave_cliente(valor) == 'clientes'
            ]
            if len(colunas) != 1:
                raise ValueError('A aba Cadastro precisa ter uma coluna Clientes na primeira linha.')

            coluna = colunas[0]
            nomes, repetidos, invalidos = {}, [], []
            linhas = aba.iter_rows(min_row=2, min_col=coluna, max_col=coluna, values_only=True)
            for numero, (valor,) in enumerate(linhas, 2):
                if valor is None or isinstance(valor, str) and not valor.strip():
                    continue
                if not isinstance(valor, str) or len(valor.strip()) > 160 or valor.startswith(('#REF!', '#N/A')):
                    invalidos.append(numero)
                    continue
                nome = valor.strip()
                chave = chave_cliente(nome)
                if chave in nomes:
                    repetidos.append((numero, nome))
                else:
                    nomes[chave] = (numero, nome)
            return list(nomes.values()), repetidos, invalidos
        finally:
            livro.close()
    except (BadZipFile, InvalidFileException, KeyError, OSError, ParseError) as erro:
        raise ValueError('Não foi possível ler o arquivo Excel. Confira se ele está íntegro.') from erro
