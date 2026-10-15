"""Regression: leave a note open, register an item in another tab, then F5."""
import time
from playwright.sync_api import sync_playwright
from browser_support import base, launch, configure_assets

with sync_playwright() as p:
    browser = launch(p)
    for initially_logged_in in (False, True):
        context = browser.new_context(ignore_https_errors=True)
        configure_assets(context)
        note = context.new_page()
        note.goto(base + ('/__test/login/1' if initially_logged_in else '/__test/login/0'))
        note.goto(base + '/nota/nova')
        note.wait_for_function("!document.querySelector('form').inert")
        number = 'HANDOFF-' + str(time.time_ns())
        note.locator('#numero_nf').fill(number)
        note.locator('[name=fornecedor]').select_option('Fornecedor Teste')
        note.locator('#tipo_estoque').select_option('empresa')
        note.locator('#tipo_servico_id').select_option('1')
        note.evaluate("adicionarItemImportado('TESTE01', 'Cabo teste', '3', '12.50')")
        if not initially_logged_in:
            key = note.locator('[name=_draft_key]').input_value()
            assert note.evaluate('(key) => !!sessionStorage.getItem(key)', key)
            assert note.evaluate('(key) => localStorage.getItem(key)', key) is None
        item = context.new_page()
        if not initially_logged_in:
            item.goto(base + '/__test/login/1')
        item.goto(base + '/estoque/cadastro')
        item.wait_for_function("!document.querySelector('form').inert")
        code = 'NOVO-' + str(time.time_ns())
        item.locator('[name=codigo]').fill(code)
        item.locator('[name=descricao]').fill('Item cadastrado com nota aberta ' + code)
        item.locator('[name=unidade]').fill('UN')
        item.locator('[name=valor]').fill('10,00')
        with item.expect_navigation():
            item.get_by_role('button', name='Cadastrar Item', exact=True).click()
        item.wait_for_function("!document.querySelector('form').inert")
        assert 'Item cadastrado com sucesso' in item.locator('body').inner_text()
        note.reload()
        note.wait_for_function("!document.querySelector('form').inert")
        assert note.locator('#numero_nf').input_value() == number, 'F5 erased a note after item registration in another tab'
        assert note.locator('[name=fornecedor]').input_value() == 'Fornecedor Teste'
        assert note.locator('#tipo_servico_id').input_value() == '1'
        assert note.locator('[name="quantidade[]"]').input_value() == '3'
        assert '37,50' in note.locator('#totalNotaFiscal').inner_text()
        assert note.locator(f'#descricao option[value="{code}"]').count() == 1
        assert note.locator('[data-draft-ui].alert').is_hidden(), 'Normal saving and recovery must not display a banner'
        print('PASS register item in another tab, F5 retains note and loads new item; initial login:', initially_logged_in)
        note.close()
        item.close()
        context.close()
    browser.close()
