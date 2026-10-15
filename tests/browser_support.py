import os
from pathlib import Path

base = os.environ['DRAFT_TEST_URL']


def launch(playwright):
    return playwright.chromium.launch(channel=os.getenv('DRAFT_TEST_BROWSER', 'chrome'), headless=True)


def configure_assets(target):
    """Optional local copies of the exact production CDN libraries for offline tests."""
    directory = os.getenv('DRAFT_TEST_ASSET_DIR')
    if not directory:
        return
    assets = [
        ('**/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js', 'bootstrap-test.js'),
        ('**/signature_pad@4.0.0/dist/signature_pad.umd.min.js', 'signature-pad-test.js'),
    ]
    for pattern, filename in assets:
        path = str(Path(directory, filename).resolve())
        target.route(pattern, lambda route, request, path=path: route.fulfill(path=path, content_type='application/javascript'))
