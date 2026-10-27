from playwright.sync_api import sync_playwright
import json
import time

from browser_support import base, launch, configure_assets
nf = 'NF-TESTE-' + str(time.time_ns())
with sync_playwright() as p:
    browser = launch(p)
    page = browser.new_page(ignore_https_errors=True)
    configure_assets(page)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(base + '/__test/login/1')
    page.goto(base + '/nota/nova')
    page.wait_for_selector('input[name="_draft_key"]', state='attached')
    page.wait_for_function("!document.querySelector('form').inert")
    page.locator('#numero_nf').fill(nf)
    page.locator('[name=fornecedor]').select_option('Fornecedor Teste')
    page.locator('#tipo_estoque').select_option('empresa')
    page.locator('#tipo_servico_id').select_option('1')
    page.evaluate("adicionarItemImportado('TESTE01', 'Cabo teste', '3', '12.50')")
    page.wait_for_timeout(100)
    before = page.locator('#tabela-itens').inner_text()
    page.reload()
    page.wait_for_function("!document.querySelector('form').inert")
    assert page.locator('#numero_nf').input_value() == nf
    assert page.locator('[name=fornecedor]').input_value() == 'Fornecedor Teste'
    assert page.locator('#tabela-itens').inner_text() == before
    assert '37,50' in page.locator('#totalNotaFiscal').inner_text()
    page.locator('#tabela-itens button').click()
    assert page.locator('#tabela-itens tr').count() == 0
    page.reload()
    page.wait_for_function("!document.querySelector('form').inert")
    assert page.locator('#tabela-itens tr').count() == 0
    print('PASS NF refresh + total + remove restored row')
    page.evaluate("adicionarItemImportado('TESTE01', 'Cabo teste', '3', '12.50')")
    page.wait_for_timeout(100)
    page.goto(base + '/tecnicos/listagem')
    page.goto(base + '/nota/nova')
    page.wait_for_function("!document.querySelector('form').inert")
    assert page.locator('[name="quantidade[]"]').input_value() == '3'
    print('PASS navigate away and return')
    # Force server validation failure, which must retain the draft.
    page.evaluate("document.querySelector('[name=fornecedor]').value = ''; document.getElementById('formNotaFiscal').noValidate = true")
    page.locator('#btnSalvarNotaFiscal').click()
    page.wait_for_load_state('networkidle')
    page.wait_for_function("!document.querySelector('form').inert")
    assert page.locator('#numero_nf').input_value() == nf
    assert page.locator('[name="quantidade[]"]').input_value() == '3'
    print('PASS validation failure retains operation')
    page.locator('[name=fornecedor]').select_option('Fornecedor Teste')
    key = page.locator('[name=_draft_key]').input_value()
    page.locator('#btnSalvarNotaFiscal').click()
    page.wait_for_load_state('networkidle')
    assert page.evaluate('(key) => localStorage.getItem(key)', key) is None
    page.goto(base + '/nota/nova')
    page.wait_for_function("!document.querySelector('form').inert")
    assert page.locator('#numero_nf').input_value() == ''
    assert page.locator('#tabela-itens tr').count() == 0
    print('PASS successful save clears draft')
    page.goto(base + '/movimentacao_estoque/nova')
    page.wait_for_function("!document.querySelector('form').inert")
    page.locator('#origem_tipo').select_option('empresa')
    page.locator('#tipo_servico_id').select_option('1')
    page.locator('#tecnico_id').select_option('1')
    page.wait_for_timeout(500)
    page.locator('.descricao-select').first.select_option('TESTE01')
    page.locator('.quantidade-input').first.fill('4')
    page.evaluate('inserirLinha()')
    page.locator('.descricao-select').nth(1).select_option('TESTE02')
    page.locator('.quantidade-input').nth(1).fill('2')
    page.reload()
    page.wait_for_function("!document.querySelector('form').inert")
    assert page.locator('.quantidade-input').evaluate_all('(els) => els.map(el => el.value)') == ['4', '2']
    assert page.locator('.descricao-select').evaluate_all('(els) => els.map(el => el.value)') == ['TESTE01', 'TESTE02']
    page.locator('.excluir-btn').nth(1).click()
    assert page.locator('.quantidade-input').count() == 1
    print('PASS movement multirow + remove restored row')
    page.goto(base + '/tecnicos/editar/1')
    page.wait_for_function("!document.querySelector('form').inert")
    page.locator('#nome').fill('Tecnico Alterado')
    page.locator('#email').fill('alterado@teste.local')
    page.get_by_role('button', name='Salvar alterações').click()
    page.wait_for_url('**/tecnicos/listagem')
    assert 'Tecnico Alterado' in page.locator('body').inner_text()
    print('PASS technician edit')
    print('BROWSER ERRORS', json.dumps(errors))
    assert not errors, errors
    browser.close()
