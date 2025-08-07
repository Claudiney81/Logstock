from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from datetime import datetime
from app import db
from app.models import Tecnico, TipoServico, SaldoTecnico, BaixaTecnica, BaixaTecnicaItem

bp_baixa_desktop = Blueprint("baixa_desktop", __name__, url_prefix="/baixa_desktop")

# --------------------------------------------------------------------
# NOVA BAIXA
# --------------------------------------------------------------------
@bp_baixa_desktop.route("/nova", methods=["GET", "POST"])
@login_required
def nova_baixa():
    tecnicos = Tecnico.query.order_by(Tecnico.nome).all()
    tipos_servico = TipoServico.query.order_by(TipoServico.nome).all()

    tecnico_id = request.args.get("tecnico_id", type=int)
    tipo_servico_id = request.args.get("tipo_servico_id", type=int)

    itens = []
    if tecnico_id and tipo_servico_id:
        itens = (
            SaldoTecnico.query
            .filter(
                SaldoTecnico.tecnico_id == tecnico_id,
                SaldoTecnico.tipo_servico_id == tipo_servico_id,
                SaldoTecnico.quantidade > 0
            )
            .all()
        )

    if request.method == "POST":
        tecnico_id = request.form.get("tecnico_id", type=int)
        tipo_servico_id = request.form.get("tipo_servico_id", type=int)
        responsavel = request.form.get("responsavel")
        observacao = request.form.get("observacao", "")

        itens_post = request.form.getlist("item_id[]")
        quantidades = request.form.getlist("quantidade[]")

        baixa = BaixaTecnica(
            tecnico_id=tecnico_id,
            tipo_servico_id=tipo_servico_id,
            responsavel=responsavel,
            observacao=observacao,
            status="pendente"
        )
        db.session.add(baixa)
        db.session.commit()

        for item_id, qtd in zip(itens_post, quantidades):
            qtd = int(qtd) if qtd else 0
            if qtd > 0:
                db.session.add(
                    BaixaTecnicaItem(
                        baixa_tecnica_id=baixa.id,
                        item_id=item_id,
                        quantidade=qtd
                    )
                )
        db.session.commit()
        flash("Baixa registrada com sucesso!", "success")
        return redirect(url_for("baixa_desktop.baixas_pendentes"))

    return render_template(
        "baixa_desktop/nova_baixa.html",
        tecnicos=tecnicos,
        tipos_servico=tipos_servico,
        tecnico_id=tecnico_id,
        tipo_servico_id=tipo_servico_id,
        itens=itens
    )

# --------------------------------------------------------------------
# BAIXAS PENDENTES (resumido)
# --------------------------------------------------------------------
@bp_baixa_desktop.route("/pendentes", methods=["GET"])
@login_required
def baixas_pendentes():
    baixas = BaixaTecnica.query.filter_by(status="pendente").order_by(BaixaTecnica.data_hora.desc()).all()
    return render_template("baixa_desktop/baixas_pendentes.html", baixas=baixas)

# --------------------------------------------------------------------
# DETALHE DA BAIXA (aprovação parcial)
# --------------------------------------------------------------------
@bp_baixa_desktop.route("/detalhe/<int:baixa_id>", methods=["GET", "POST"])
@login_required
def detalhe_baixa(baixa_id):
    baixa = BaixaTecnica.query.get_or_404(baixa_id)

    # Itens + saldo atual do técnico
    itens = db.session.query(
        BaixaTecnicaItem,
        SaldoTecnico.quantidade.label("saldo_atual")
    ).join(
        SaldoTecnico,
        (SaldoTecnico.item_id == BaixaTecnicaItem.item_id) &
        (SaldoTecnico.tecnico_id == baixa.tecnico_id) &
        (SaldoTecnico.tipo_servico_id == baixa.tipo_servico_id),
        isouter=True
    ).filter(
        BaixaTecnicaItem.baixa_tecnica_id == baixa.id
    ).all()

    if request.method == "POST":
        itens_marcados = request.form.getlist("itens")
        if "aprovar" in request.form:
            for item, saldo_atual in itens:
                if str(item.id) in itens_marcados and (saldo_atual is None or saldo_atual >= item.quantidade):
                    saldo_tecnico = SaldoTecnico.query.filter_by(
                        tecnico_id=baixa.tecnico_id,
                        item_id=item.item_id,
                        tipo_servico_id=baixa.tipo_servico_id
                    ).first()
                    if saldo_tecnico:
                        saldo_tecnico.quantidade -= item.quantidade
                    db.session.delete(item)
            restantes = BaixaTecnicaItem.query.filter_by(baixa_tecnica_id=baixa.id).count()
            if restantes == 0:
                baixa.status = "confirmado"
            db.session.commit()
            flash("Itens aprovados com sucesso!", "success")

        elif "recusar" in request.form:
            baixa.status = "recusado"
            db.session.commit()
            flash("Baixa recusada!", "warning")

        return redirect(url_for("baixa_desktop.baixas_pendentes"))

    return render_template("baixa_desktop/detalhe_baixa.html", baixa=baixa, itens=itens)


# --------------------------------------------------------------------
# HISTÓRICO
# --------------------------------------------------------------------
@bp_baixa_desktop.route("/historico", methods=["GET"])
@login_required
def historico_baixas():
    tecnicos = Tecnico.query.order_by(Tecnico.nome).all()
    tecnico_id = request.args.get("tecnico_id", type=int)
    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")

    query = BaixaTecnica.query
    if tecnico_id:
        query = query.filter(BaixaTecnica.tecnico_id == tecnico_id)
    if data_inicio:
        data_inicio_dt = datetime.strptime(data_inicio, "%Y-%m-%d")
        query = query.filter(BaixaTecnica.data_hora >= data_inicio_dt)
    if data_fim:
        data_fim_dt = datetime.strptime(data_fim, "%Y-%m-%d")
        query = query.filter(BaixaTecnica.data_hora <= data_fim_dt)

    historico = query.order_by(BaixaTecnica.data_hora.desc()).all()

    return render_template(
        "baixa_desktop/historico_baixas.html",
        historico=historico,
        tecnicos=tecnicos,
        tecnico_id=tecnico_id,
        data_inicio=data_inicio,
        data_fim=data_fim
    )

# --------------------------------------------------------------------
# BAIXAS REALIZADAS
# --------------------------------------------------------------------
@bp_baixa_desktop.route("/realizadas", methods=["GET"])
@login_required
def baixas_realizadas():
    tecnicos = Tecnico.query.order_by(Tecnico.nome).all()
    tecnico_id = request.args.get("tecnico_id", type=int)
    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")

    query = BaixaTecnica.query.filter_by(status="confirmado")
    if tecnico_id:
        query = query.filter(BaixaTecnica.tecnico_id == tecnico_id)
    if data_inicio:
        data_inicio_obj = datetime.strptime(data_inicio, "%Y-%m-%d")
        query = query.filter(BaixaTecnica.data_hora >= data_inicio_obj)
    if data_fim:
        data_fim_obj = datetime.strptime(data_fim, "%Y-%m-%d")
        query = query.filter(BaixaTecnica.data_hora <= data_fim_obj)

    baixas = query.order_by(BaixaTecnica.data_hora.desc()).all()

    return render_template(
        "baixa_desktop/baixas_realizadas.html",
        baixas=baixas,
        tecnicos=tecnicos,
        tecnico_id=tecnico_id,
        data_inicio=data_inicio,
        data_fim=data_fim
    )

# --------------------------------------------------------------------
# API Contador Baixas Pendentes
# --------------------------------------------------------------------
@bp_baixa_desktop.route("/api/pendentes/count")
def api_baixas_pendentes_count():
    count = BaixaTecnica.query.filter_by(status="pendente").count()
    return {"count": count}
