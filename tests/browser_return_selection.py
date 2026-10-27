"""Regression: batch deselection must not return previously inserted materials."""
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server
from test_retorno_material_cliente import RetornoMaterialClienteTests
from app.extensions import db
from app.models import SaldoTecnico, MovimentacaoEstoque


def run():
    fixture = RetornoMaterialClienteTests()
    fixture.setUp()
    server = None
    try:
        fixture.preparar()
        db.session.add(SaldoTecnico(tecnico_id=1, item_id=2, tipo_servico_id=1,
            tipo_estoque='cliente', cliente_id=1, ordem_servico_id=1, quantidade=17))
        db.session.commit()
        server = make_server('127.0.0.1', 0, fixture.app, threaded=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f'http://127.0.0.1:{server.server_port}'
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='chrome', headless=True)
            page = browser.new_page()
            # No production mail or CDN dependency in this isolated fixture.
            page.route('https://**/*', lambda route: route.abort())
            page.goto(base + '/__test/login/1')
            page.goto(base + '/movimentacao_estoque/nova')
            page.wait_for_function("!document.querySelector('form').inert")
            page.select_option('#origem_tipo', 'tecnico')
            page.select_option('#destino_tipo', 'cliente')
            page.select_option('#tecnico_id', '1')
            page.select_option('#cliente_id', '1')
            page.select_option('#os_id', '1')
            page.select_option('#tipo_servico_id', '1')
            page.wait_for_selector('#tabela-lote tr[data-codigo="TESTE02"]')
            page.on('dialog', lambda dialog: dialog.accept())
            page.evaluate('marcarItensLote(true); inserirSelecionadosLote()')
            assert page.locator('#tabela-itens .codigo-input').count() == 2
            page.locator('#tabela-lote tr[data-codigo="TESTE02"] .lote-check').uncheck()
            # A changed selection blocks submission of the previous, larger batch.
            blocked = page.evaluate("""() => {
                const e = new Event('submit', {bubbles: true, cancelable: true});
                document.querySelector('form').dispatchEvent(e);
                return e.defaultPrevented;
            }""")
            assert blocked
            page.evaluate('inserirSelecionadosLote()')
            assert page.locator('#tabela-itens .codigo-input').evaluate_all(
                '(inputs) => inputs.map(input => input.value)') == ['TESTE01']
            # Unchecking everything also blocks the already inserted batch.
            page.evaluate('marcarItensLote(false)')
            assert page.evaluate("""() => {
                const e = new Event('submit', {bubbles:true, cancelable:true});
                document.querySelector('form').dispatchEvent(e);
                return e.defaultPrevented;
            }""")
            page.locator('#tabela-lote tr[data-codigo="TESTE01"] .lote-check').check()
            # Submit exactly the single selected item to the real fixture backend.
            from unittest.mock import patch
            with patch('app.routes.movimentacao_estoque.send_movimentacao_email', return_value=False):
                with page.expect_navigation():
                    page.locator('button[type="submit"]').first.click()
            browser.close()
        db.session.expire_all()
        mov = MovimentacaoEstoque.query.one()
        assert [(i.item_id, i.quantidade) for i in mov.itens] == [(1, 10)]
        other = SaldoTecnico.query.filter_by(tecnico_id=1, item_id=2,
            tipo_estoque='cliente', cliente_id=1, ordem_servico_id=1).one()
        assert other.quantidade == 17
        print('OK: only selected material returned; other material remains with technician.')
    finally:
        if server:
            server.shutdown()
        fixture.tearDown()


if __name__ == '__main__':
    run()
