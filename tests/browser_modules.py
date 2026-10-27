from playwright.sync_api import sync_playwright
import base64

from browser_support import base, launch, configure_assets
with sync_playwright() as p:
    browser = launch(p)
    context = browser.new_context(ignore_https_errors=True)
    configure_assets(context)
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    def goto(path):
        page.goto(base + path)
        page.wait_for_function("document.querySelector('input[name=_draft_key]') && [...document.forms].every(f => !f.inert)")
    def refresh():
        page.reload()
        page.wait_for_function("[...document.forms].every(f => !f.inert)")
    page.goto(base + '/__test/login/1')
    goto('/estoque/cadastro')
    page.locator('[name=codigo]').fill('RASCUNHO-NOVO')
    page.locator('[name=descricao]').fill('Item em preenchimento')
    refresh()
    assert page.locator('[name=codigo]').input_value() == 'RASCUNHO-NOVO'
    print('PASS item registration draft')
    goto('/inventario_estoque/?tipo_estoque=empresa')
    field = page.locator('.quantidade-contada').first
    field.fill('7')
    expected_difference = field.locator('xpath=ancestor::tr').locator('.diferenca').inner_text()
    refresh()
    assert page.locator('.quantidade-contada').first.input_value() == '7'
    assert page.locator('.quantidade-contada').first.locator('xpath=ancestor::tr').locator('.diferenca').inner_text() == expected_difference
    print('PASS inventory count and difference')
    goto('/baixa_desktop/nova')
    for ident, value in [('tecnico_id','1'),('tipo_servico_id','1'),('cliente_id','1'),('ordem_servico_id','1'),('tipo_estoque','empresa')]:
        page.locator('#' + ident).select_option(value)
        page.wait_for_timeout(150)
    page.wait_for_selector('.qtd-disponivel')
    page.locator('.qtd-disponivel').first.fill('3')
    page.evaluate('adicionarItensInformadosAoResumo()')
    page.wait_for_timeout(100)
    refresh()
    assert page.locator('[name="resumo_quantidade[]"]').input_value() == '3'
    page.locator('#tbodyResumoBaixa button').click()
    assert page.locator('[name="resumo_quantidade[]"]').count() == 0
    print('PASS desktop write-off model and removal')
    goto('/ferramentas-epis/transferencia')
    page.locator('#tecnico_id').select_option('1')
    page.wait_for_timeout(200)
    page.evaluate("adicionarItemNaTabela({item_id:3,codigo:'FERR01',descricao:'Alicate teste',categoria:'FERRAMENTA',quantidade:50},2)")
    page.locator('#quantidade').fill('1')
    canvas = page.locator('#signature-pad-tecnico')
    canvas.scroll_into_view_if_needed()
    box = canvas.bounding_box()
    page.mouse.move(box['x'] + 20, box['y'] + 20)
    page.mouse.down()
    page.mouse.move(box['x'] + 80, box['y'] + 45, steps=10)
    page.mouse.up()
    page.wait_for_timeout(100)
    refresh()
    assert page.locator('[name="quantidade[]"]').input_value() == '2'
    assert not page.evaluate('signaturePadTecnico.isEmpty()')
    page.locator('#tabelaItens .btnRemover').click()
    assert page.locator('[name="quantidade[]"]').count() == 0
    print('PASS tools table, signature, removal')
    goto('/frota/vistorias/nova')
    page.locator('[name=local_vistoria]').fill('Patio teste')
    payload = dict(name='foto-teste.png', mimeType='image/png', buffer=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a2ioAAAAASUVORK5CYII='))
    page.locator('#inputFotos').set_input_files(payload)
    page.locator('[name=descricao_foto_0]').fill('Foto em rascunho')
    page.wait_for_timeout(300)
    refresh()
    assert page.locator('[name=local_vistoria]').input_value() == 'Patio teste'
    assert page.locator('[name=descricao_foto_0]').input_value() == 'Foto em rascunho'
    assert page.evaluate('fotosSelecionadas[0].name') == 'foto-teste.png'
    print('PASS inspection photo file and description')
    # Confirm identity isolation and explicit discard.
    goto('/estoque/cadastro')
    assert page.locator('[name=codigo]').input_value() == 'RASCUNHO-NOVO'
    page.goto(base + '/__test/login/3')
    goto('/estoque/cadastro')
    assert page.locator('[name=codigo]').input_value() == ''
    page.goto(base + '/__test/login/1')
    goto('/estoque/cadastro')
    assert page.locator('[name=codigo]').input_value() == 'RASCUNHO-NOVO'
    page.once('dialog', lambda dialog: dialog.accept())
    page.get_by_role('button', name='Limpar preenchimento').first.click()
    page.wait_for_load_state('networkidle')
    assert page.locator('[name=codigo]').input_value() == ''
    print('PASS user isolation and explicit discard')
    page.goto(base + '/__test/login/2')
    goto('/requisicao_mobile/nova')
    page.locator('#tipo-servico-select').select_option('1')
    page.get_by_role('button', name='Adicionar Item', exact=False).click()
    page.locator('select[name="item_id[]"]').select_option('1')
    page.locator('input[name="quantidade[]"]').fill('4')
    refresh()
    assert page.locator('select[name="item_id[]"]').input_value() == '1'
    assert page.locator('input[name="quantidade[]"]').input_value() == '4'
    page.locator('.btn-remove-row').click()
    assert page.locator('select[name="item_id[]"]').count() == 0
    print('PASS mobile request and restored row handlers')
    page.get_by_role('button', name='Adicionar Item', exact=False).click()
    page.locator('select[name="item_id[]"]').select_option('1')
    page.locator('input[name="quantidade[]"]').fill('4')
    key = page.locator('[name=_draft_key]').input_value()
    page.get_by_role('button', name='Enviar Requisição', exact=False).click()
    page.get_by_role('button', name='Sim, Enviar').click()
    page.wait_for_url('**/tecnico-mobile/home?sucesso=requisicao_enviada')
    assert page.evaluate('(key) => localStorage.getItem(key)', key) is None
    print('PASS successful mobile request clears draft')
    goto('/baixa_tecnico/mobile')
    for ident, value in [('cliente_id','1'),('ordem_servico','1'),('tipo_estoque','empresa'),('tipo_servico_id','1')]:
        page.locator('#' + ident).select_option(value)
        page.wait_for_timeout(150)
    page.wait_for_selector('#tbodyItens input[type=number]')
    page.locator('#tbodyItens input[type=number]').first.fill('2')
    page.locator('#btnAdicionar').click()
    page.wait_for_timeout(100)
    refresh()
    assert page.locator('#hiddenInputs [name="quantidade[]"]').input_value() == '2'
    page.locator('#btnAdicionarFoto').click()
    page.locator('.foto-input').first.set_input_files(payload)
    page.locator('[name="legenda_foto[]"]').first.fill('Foto baixa')
    page.wait_for_timeout(300)
    refresh()
    assert page.locator('#hiddenInputs [name="quantidade[]"]').input_value() == '2'
    assert page.locator('[name="legenda_foto[]"]').first.input_value() == 'Foto baixa'
    assert page.locator('.foto-input').first.evaluate('(el)=>el.files[0].name') == 'foto-teste.png'
    page.locator('#tbodyResumo button').click()
    assert page.locator('#hiddenInputs [name="quantidade[]"]').count() == 0
    print('PASS mobile write-off summary, photo, caption, removal')
    print('BROWSER ERRORS', errors)
    assert not errors
    browser.close()
