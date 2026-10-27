"""Read actual Excel files while all external network requests are blocked."""
from io import BytesIO
from openpyxl import Workbook
from playwright.sync_api import sync_playwright
from browser_support import base, launch


def workbook_bytes(rows):
    book = Workbook()
    for row in rows:
        book.active.append(row)
    output = BytesIO()
    book.save(output)
    return output.getvalue()


with sync_playwright() as p:
    browser = launch(p)
    context = browser.new_context()
    context.route('https://**/*', lambda route: route.abort())
    page = context.new_page()
    dialogs = []
    page.on('dialog', lambda dialog: (dialogs.append(dialog.message), dialog.accept()))
    page.goto(base + '/__test/login/1')
    page.goto(base + '/nota/nova')
    page.wait_for_function("!document.querySelector('form').inert")
    assert page.evaluate('XLSX.version') == '0.18.5'

    def upload(name, content):
        previous = len(dialogs)
        page.locator('#importarExcel').set_input_files(dict(name=name, mimeType='application/octet-stream', buffer=content))
        page.wait_for_function('''() => !document.querySelector('#importarExcel').value''')
        assert len(dialogs) > previous

    upload('materiais.xlsx', workbook_bytes([
        ['Código', 'Descrição', 'Quantidade', 'Valor Unitário'],
        ['00012', 'Parafuso', 3, 12.5],
    ]))
    assert '1 item(ns) carregado(s)' in dialogs[-1]
    assert page.evaluate('itensImportadosPendentes[0].codigo') == '00012'
    assert page.evaluate('itensImportadosPendentes[0].valor') == '12.50'
    page.reload()
    page.wait_for_function("!document.querySelector('form').inert")
    assert page.evaluate('itensImportadosPendentes.length') == 1
    page.get_by_role('button', name='Adicionar selecionados', exact=True).click()
    assert page.locator('[name="quantidade[]"]').input_value() == '3'
    assert '37,50' in page.locator('#totalNotaFiscal').inner_text()
    print('PASS actual XLSX file, leading zero code, preview recovery, selection and total without CDN')

    upload('orcamento.xlsx', workbook_bytes([
        ['Orçamento de materiais'], ['Item', 'Qtd.', 'Valor estimado'],
        ['Cabo teste', '2 UN', 'R$ 1.234,56'],
    ]))
    assert page.evaluate('itensImportadosPendentes[0].codigo') == 'TESTE01'
    assert page.evaluate('itensImportadosPendentes[0].valor') == '12.50', 'Existing item must keep its registered price'
    print('PASS actual budget XLSX with title, catalogue match, unit quantity and Brazilian currency')

    legacy = bytes(page.evaluate('''() => {
      const book = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(book, XLSX.utils.aoa_to_sheet([
        ['Código','Descrição','Quantidade','Valor Unitário'], ['TESTE02','Conector teste',4,3.75]
      ]), 'Itens');
      return Array.from(new Uint8Array(XLSX.write(book, {bookType:'biff8', type:'array'})));
    }'''))
    upload('legado.xls', legacy)
    assert page.evaluate('itensImportadosPendentes[0].codigo') == 'TESTE02'
    assert page.evaluate('itensImportadosPendentes[0].valor') == '5.00'
    print('PASS actual legacy XLS file')

    upload('abreviacoes.xlsx', workbook_bytes([
        ['Cód.', 'Descrição', 'Qtde.', 'Valor Unit.'], ['ALIAS-01', 'Item abreviado', 2, 18.75]
    ]))
    assert page.evaluate('itensImportadosPendentes[0].codigo') == 'ALIAS-01'
    assert page.evaluate('itensImportadosPendentes[0].valor') == '18.75'
    print('PASS common abbreviated quantity and unit-price headers')

    upload('colunas-invalidas.xlsx', workbook_bytes([['Não é uma lista de materiais'], ['Outra coluna', 'Sem quantidade']]))
    assert 'Cabeçalho não encontrado' in dialogs[-1]
    assert page.evaluate('itensImportadosPendentes[0].codigo') == 'ALIAS-01', 'A failed file must not erase the previous preview'
    print('PASS clear header error and previous preview preserved')

    page.evaluate('window.XLSX = undefined')
    upload('materiais.xlsx', workbook_bytes([['Item','Qtd'], ['Material',1]]))
    assert 'leitor de Excel não carregou' in dialogs[-1]
    print('PASS specific message when Excel reader is unavailable')
    browser.close()
