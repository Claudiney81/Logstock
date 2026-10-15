import time
from playwright.sync_api import sync_playwright
from browser_support import base, launch, configure_assets

with sync_playwright() as p:
    browser = launch(p)
    context = browser.new_context(ignore_https_errors=True)
    configure_assets(context)
    page = context.new_page()
    page.goto(base + '/__test/login/1')
    page.goto(base + '/nota/nova')
    page.wait_for_function("!document.querySelector('form').inert")
    page.locator('#numero_nf').fill('EDIT-QTY-' + str(time.time_ns()))
    page.locator('[name=fornecedor]').select_option('Fornecedor Teste')
    page.locator('#tipo_estoque').select_option('empresa')
    page.locator('#tipo_servico_id').select_option('1')
    page.evaluate("adicionarItemImportado('TESTE02', 'Conector teste', '2', '999.00')")
    quantity = page.locator('#tabela-itens [name="quantidade[]"]')
    assert quantity.get_attribute('type') == 'number'
    assert page.locator('#tabela-itens [name="valor[]"]').input_value() == '5.00'
    assert page.locator('#valor').evaluate('(el) => el.readOnly')
    assert page.locator('.nf-lote-valor').evaluate_all('(els) => els.every(el => el.readOnly)')
    quantity.fill('4')
    assert '20,00' in page.locator('#totalNotaFiscal').inner_text()
    quantity.fill('0')
    assert not quantity.evaluate('(el) => el.checkValidity()')
    quantity.fill('1.5')
    assert not quantity.evaluate('(el) => el.checkValidity()')
    quantity.fill('4')
    page.reload()
    page.wait_for_function("!document.querySelector('form').inert")
    assert quantity.input_value() == '4'
    assert '20,00' in page.locator('#totalNotaFiscal').inner_text()
    print('PASS inline quantity, live total, validation, refresh and locked registered price')

    # Upgrade work already saved by the version that displayed static quantities.
    page.evaluate('''() => {
      const input = document.querySelector('#tabela-itens [name="quantidade[]"]');
      input.type = 'hidden';
      input.parentElement.appendChild(document.createTextNode('4'));
      document.querySelector('[name=observacao]').dispatchEvent(new Event('input', {bubbles:true}));
    }''')
    page.reload()
    page.wait_for_function("!document.querySelector('form').inert")
    assert quantity.get_attribute('type') == 'number'
    assert quantity.input_value() == '4'
    print('PASS existing static-quantity draft is upgraded without losing its rows')

    registry = context.new_page()
    registry.goto(base + '/itens/editar/2')
    registry.wait_for_function("!document.querySelector('form').inert")
    registry.locator('[name=valor]').fill('6,25')
    with registry.expect_navigation():
        registry.locator('button[type=submit]').click()
    page.reload()
    page.wait_for_function("!document.querySelector('form').inert")
    assert quantity.input_value() == '4'
    assert page.locator('#tabela-itens [name="valor[]"]').input_value() == '6.25'
    assert '25,00' in page.locator('#totalNotaFiscal').inner_text()
    with page.expect_navigation():
        page.locator('#btnSalvarNotaFiscal').click()
    assert '/nota/nova' not in page.url
    print('PASS price edited in registry updates the open note on F5; edited quantity can be saved')
    browser.close()
