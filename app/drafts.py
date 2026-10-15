"""Browser draft lifecycle. Only an explicitly successful POST clears a draft."""
from flask import g, request, session, message_flashed
from flask_login import current_user
from secrets import token_hex


def draft_user(create_anonymous=False):
    mobile = (request.endpoint or '').startswith(('baixa_tecnico.', 'requisicao_mobile.', 'tecnico_mobile.'))
    if mobile and session.get('tecnico_id'):
        return f"tecnico-{session['tecnico_id']}"
    if current_user.is_authenticated:
        return f'usuario-{current_user.get_id()}'
    if session.get('tecnico_id'):
        return f"tecnico-{session['tecnico_id']}"
    if session.get('usuario_id'):
        return f"usuario-{session['usuario_id']}"
    if create_anonymous and not session.get('_draft_anonymous_id'):
        session['_draft_anonymous_id'] = token_hex(16)
    if session.get('_draft_anonymous_id'):
        return f"anon-{session['_draft_anonymous_id']}"
    return ''


def draft_saved():
    """Mark committed operations whose final notification is a warning."""
    g.draft_saved = True


def init_drafts(app):
    @app.before_request
    def prepare_draft():
        g.draft_result = None
        g.draft_saved = False

    def record_result(sender, message, category, **kwargs):
        if category in ('danger', 'error', 'warning'):
            g.draft_result = False
        elif category == 'success' and g.get('draft_result') is not False:
            g.draft_result = True

    message_flashed.connect(record_result, app, weak=False)

    @app.after_request
    def finish_draft(response):
        key = request.form.get('_draft_key', '') if request.method == 'POST' else ''
        owner = draft_user()
        owners = [owner] if owner else []
        if session.get('_draft_anonymous_id'):
            owners.append(f"anon-{session['_draft_anonymous_id']}")
        if (any(key.startswith(f'logistock:draft:v1:{candidate}:') for candidate in owners) and len(key) < 1500
                and (g.get('draft_saved') or g.get('draft_result') is True)
                and response.status_code < 400):
            completed = session.get('_completed_drafts', [])
            session['_completed_drafts'] = (completed + [key])[-20:]
        return response

    @app.context_processor
    def draft_context():
        # PDF/email templates also build a context; consume only when the browser
        # actually renders the draft script, so they cannot lose confirmations.
        return {'consume_completed_drafts': lambda: session.pop('_completed_drafts', []),
                'draft_user': draft_user(create_anonymous=True)}
