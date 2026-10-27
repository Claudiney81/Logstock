from playwright.sync_api import sync_playwright
from browser_support import base, launch, configure_assets

with sync_playwright() as p:
    browser = launch(p)
    context = browser.new_context(ignore_https_errors=True)
    configure_assets(context)
    left = context.new_page()
    left.goto(base + '/__test/login/1')
    left.goto(base + '/estoque/cadastro')
    left.wait_for_function("document.querySelector('[name=_draft_key]') && !document.querySelector('form').inert")
    left.locator('[name=codigo]').fill('TWO-TABS')
    left.locator('[name=descricao]').fill('Primeira versão')
    key = left.locator('[name=_draft_key]').first.input_value()
    right = context.new_page()
    right.goto(base + '/estoque/cadastro')
    right.wait_for_function("document.querySelector('[name=_draft_key]') && !document.querySelector('form').inert")
    assert right.locator('[name=descricao]').input_value() == 'Primeira versão'
    right.wait_for_timeout(2300)
    assert right.get_by_role('button', name='Carregar versão atual').first.is_hidden()
    right.locator('[name=descricao]').fill('Versão da segunda aba')
    left.get_by_role('button', name='Carregar versão atual').first.wait_for(state='visible')
    left.locator('[name=descricao]').fill('Alteração desatualizada')
    left.wait_for_timeout(100)
    assert 'Versão da segunda aba' in left.evaluate('(key) => localStorage.getItem(key)', key)
    dialogs = []
    left.on('dialog', lambda dialog: (dialogs.append(dialog.message), dialog.dismiss()))
    left.evaluate('document.querySelector("form").submit()')
    assert dialogs and 'outra aba' in dialogs[0]
    assert left.url.endswith('/estoque/cadastro')
    print('PASS two-tab conflict prevents overwrite and programmatic submission')

    # Local storage is untrusted; rebuilding a draft must not execute its markup.
    page = context.new_page()
    page.goto(base + '/nota/nova')
    page.wait_for_function("!document.querySelector('form').inert")
    page.locator('#numero_nf').fill('UNTRUSTED-DRAFT')
    page.evaluate("adicionarItemImportado('TESTE01', 'Cabo teste', '2', '12.50')")
    page.wait_for_timeout(100)
    page.evaluate('''() => {
      const key = document.querySelector('[name=_draft_key]').value;
      const snapshot = JSON.parse(localStorage.getItem(key));
      snapshot.regions[0].children.push({tag:'SCRIPT', attributes:{}, children:["alert('unsafe')"]});
      snapshot.regions[0].children.push({tag:'IMG', attributes:{src:'invalid', onerror:"alert('unsafe')"}, children:[]});
      localStorage.setItem(key, JSON.stringify(snapshot));
    }''')
    attacks = []
    attack_handler = lambda dialog: (attacks.append(dialog.message), dialog.dismiss())
    page.on('dialog', attack_handler)
    page.reload()
    page.wait_for_function("!document.querySelector('form').inert")
    assert page.locator('#tabela-itens script').count() == 0
    assert page.locator('#tabela-itens img').get_attribute('onerror') is None
    assert not attacks
    page.remove_listener('dialog', attack_handler)
    print('PASS untrusted draft markup is sanitized')
    page.evaluate('''() => {
      const key = document.querySelector('[name=_draft_key]').value;
      localStorage.setItem(key, JSON.stringify({version:1, fields:null}));
    }''')
    page.reload()
    page.wait_for_function("!document.querySelector('form').inert")
    assert 'Não foi possível recuperar' in page.locator('[role=status]').inner_text()
    page.once('dialog', lambda dialog: dialog.accept())
    page.get_by_role('button', name='Limpar preenchimento').click()
    page.wait_for_load_state('networkidle')
    assert page.locator('#numero_nf').input_value() == ''
    print('PASS corrupted draft can be explicitly discarded')
    browser.close()
