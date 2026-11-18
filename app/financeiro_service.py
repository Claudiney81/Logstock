from calendar import monthrange
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from app.financeiro_models import ParcelaFinanceira
from app.utils.datas import hoje_local

MODALIDADES = {
    'comodato_variavel': 'Comodato',
    'venda': 'Venda',
    'manutencao': 'Manutenção',
    'manutencao_sfv': 'Manutenção SFV',
    'manutencao_joao': 'Manutenção João',
    'adequacao': 'Adequação',
    'venda_avulsa': 'Venda avulsa',
}
ZERO = Decimal('0.00')
FORMAS_PAGAMENTO = ['À vista', 'Parcelado', 'Financiado']
FORNECEDORES = ['Bel Energy', 'Soollar Dist', 'Sou Energy', 'Soollar / Fortlev',
                'Start', 'Edeltec', 'Belenergy / Fortlev']


def dinheiro(texto, opcional=False):
    texto = str(texto or '').strip()
    if not texto and opcional:
        return None
    if ',' in texto:
        texto = texto.replace('.', '').replace(',', '.')
    try:
        valor = Decimal(texto)
        if not valor.is_finite() or valor < 0 or valor > Decimal('999999999999.99'):
            raise ValueError()
        if valor != valor.quantize(Decimal('.01')):
            raise ValueError()
        return valor.quantize(Decimal('.01'))
    except (InvalidOperation, ValueError):
        raise ValueError('Informe um valor monetário válido, positivo ou zero, com até duas casas decimais.')


def data_valida(texto):
    try:
        return date.fromisoformat(texto or '')
    except (ValueError, TypeError):
        raise ValueError('Informe uma data válida.')


def vencimento_mensal(inicial, deslocamento):
    indice = inicial.year * 12 + inicial.month - 1 + deslocamento
    ano, mes = divmod(indice, 12)
    mes += 1
    return date(ano, mes, min(inicial.day, monthrange(ano, mes)[1]))


def gerar_parcelas(contrato):
    for numero in range(1, contrato.quantidade_parcelas + 1):
        valor = contrato.base_mensal
        variavel = contrato.modalidade == 'comodato_variavel'
        if variavel:
            valor = (valor * (Decimal('.70') if numero <= 36 else Decimal('.50'))).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        contrato.parcelas.append(ParcelaFinanceira(
            numero=numero, vencimento=vencimento_mensal(contrato.primeiro_vencimento, numero - 1),
            previsao=valor, valor_real=None if variavel else valor,
        ))


def situacao(parcela, hoje=None):
    hoje = hoje or hoje_local()
    if parcela.recebimentos:
        return 'Pago'
    if parcela.valor_real is None:
        return 'Aguardando apuração'
    if parcela.vencimento < hoje:
        return 'Atrasado'
    if parcela.vencimento == hoje:
        return 'Vence hoje'
    return 'A vencer'


def resumo(parcelas):
    hoje = hoje_local()
    return {
        'previsao': sum((p.previsao for p in parcelas), ZERO),
        'apurado': sum((p.valor_real for p in parcelas if p.valor_real is not None), ZERO),
        'recebido': sum((r.valor for p in parcelas for r in p.recebimentos), ZERO),
        'aberto': sum((p.valor_real for p in parcelas if p.valor_real is not None and not p.recebimentos), ZERO),
        'atrasado': sum((p.valor_real for p in parcelas if p.valor_real is not None and not p.recebimentos and p.vencimento < hoje), ZERO),
        'aguardando': sum(p.valor_real is None and not p.recebimentos for p in parcelas),
    }
