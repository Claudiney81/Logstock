"""Optional integration checks: pip install playwright; python tests/browser_drafts.py."""
import os
from pathlib import Path
import runpy
import sys
from tempfile import TemporaryDirectory
from threading import Thread
from unittest.mock import patch

from werkzeug.serving import make_server, WSGIRequestHandler

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / 'tests'))
from browser_fixture import build_app

suites = ('browser_core.py', 'browser_modules.py', 'browser_safety.py', 'browser_excel.py', 'browser_handoff.py', 'browser_note_quantity.py')
selected = sys.argv[1:] or suites
if any(suite not in suites for suite in selected):
    raise SystemExit('Escolha uma destas suites: ' + ', '.join(suites))


class QuietHandler(WSGIRequestHandler):
    def log(self, *args, **kwargs):
        pass


with TemporaryDirectory(prefix='logistock-drafts-') as directory:
    with patch.dict(os.environ, {'LOGISTOCK_ADMIN_EMAIL': '', 'LOGISTOCK_ADMIN_PASSWORD': ''}):
        app = build_app(Path(directory, 'browser.db'))
    server = make_server('127.0.0.1', 0, app, threaded=True, request_handler=QuietHandler)
    os.environ['DRAFT_TEST_URL'] = f'http://127.0.0.1:{server.server_port}'
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for suite in selected:
            runpy.run_path(str(root / 'tests' / suite), run_name='__main__')
    finally:
        server.shutdown()
        thread.join(timeout=5)
        with app.app_context():
            from app.extensions import db
            db.session.remove()
            db.engine.dispose()
