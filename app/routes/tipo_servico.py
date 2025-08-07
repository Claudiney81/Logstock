from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.extensions import db
from app.models import TipoServico

tipo_servico_bp = Blueprint('tipo_servico', __name__)

# Cadastro e listagem
@tipo_servico_bp.route('/cadastro/tipo-servico', methods=['GET', 'POST'])
def cadastrar_tipo_servico():
    if request.method == 'POST':
        nome = request.form.get('nome')
        empresa = request.form.get('empresa')

        if not nome:
            flash("O nome do tipo de serviço é obrigatório.", 'warning')
            return redirect(url_for('tipo_servico.cadastrar_tipo_servico'))

        # Verifica se já existe
        existente = TipoServico.query.filter_by(nome=nome).first()
        if existente:
            flash("Este tipo de serviço já está cadastrado.", 'danger')
            return redirect(url_for('tipo_servico.cadastrar_tipo_servico'))

        novo_tipo = TipoServico(nome=nome, empresa=empresa)
        db.session.add(novo_tipo)
        db.session.commit()
        flash("Tipo de serviço cadastrado com sucesso!", 'success')
        return redirect(url_for('tipo_servico.cadastrar_tipo_servico'))

    tipos = TipoServico.query.order_by(TipoServico.nome).all()
    return render_template('cadastros/tipo_servico.html', tipos=tipos)

# Edição
@tipo_servico_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar_tipo_servico(id):
    tipo = TipoServico.query.get_or_404(id)

    if request.method == 'POST':
        nome = request.form.get('nome')
        empresa = request.form.get('empresa')

        if not nome:
            flash("O nome do tipo de serviço é obrigatório.", 'warning')
            return redirect(url_for('tipo_servico.editar_tipo_servico', id=id))

        tipo.nome = nome
        tipo.empresa = empresa
        db.session.commit()
        flash("Tipo de serviço atualizado com sucesso!", 'success')
        return redirect(url_for('tipo_servico.cadastrar_tipo_servico'))

    return render_template('cadastros/editar_tipo_servico.html', tipo=tipo)

# Exclusão
@tipo_servico_bp.route('/excluir/<int:id>', methods=['POST'])
def excluir_tipo_servico(id):
    tipo = TipoServico.query.get_or_404(id)
    db.session.delete(tipo)
    db.session.commit()
    flash(f'Tipo de serviço "{tipo.nome}" excluído com sucesso.', 'success')
    return redirect(url_for('tipo_servico.cadastrar_tipo_servico'))
