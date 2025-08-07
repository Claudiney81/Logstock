from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app import db
from app.models import Tecnico, SaldoTecnico, BaixaTecnica, BaixaTecnicaItem, TipoServico

bp_baixa_tecnico = Blueprint("baixa_tecnico", __name__, url_prefix="/baixa_tecnico")

# --- REDIRECIONA LINKS ANTIGOS ---
@bp_baixa_tecnico.route("/formulario", methods=["GET"])
def formulario_baixa():
    tecnico_id = request.args.get("tecnico_id", type=int)
    if not tecnico_id:
        return "Técnico não informado.", 400
    return redirect(url_for("baixa_tecnico.formulario_mobile_dedicado", tecnico_id=tecnico_id))

# --- FORMULÁRIO MOBILE ---
@bp_baixa_tecnico.route("/mobile/<int:tecnico_id>")
def formulario_mobile_dedicado(tecnico_id):
    tecnico = Tecnico.query.get(tecnico_id)
    if not tecnico:
        return "Técnico não encontrado.", 404

    # Lista todos os tipos de serviço (mesma lógica usada no desktop)
    tipos_servico = TipoServico.query.order_by(TipoServico.nome.asc()).all()

    return render_template(
        "baixa_tecnico/formulario_mobile_dedicado.html",
        tecnico_id=tecnico.id,
        tecnico_nome=tecnico.nome,
        tipos_servico=tipos_servico
    )

# --- API ITENS DO TÉCNICO (PEGA SALDO ATUAL) ---
@bp_baixa_tecnico.route("/api/itens/<int:tecnico_id>/<int:tipo_servico_id>")
def api_itens_por_tipo_servico(tecnico_id, tipo_servico_id):
    # Busca os itens do saldo técnico filtrando por técnico e tipo de serviço
    saldos = (
        SaldoTecnico.query
        .filter(
            SaldoTecnico.tecnico_id == tecnico_id,
            SaldoTecnico.tipo_servico_id == tipo_servico_id,
            SaldoTecnico.quantidade > 0
        )
        .all()
    )
    itens = [
        {
            "item_id": s.item.id,
            "codigo": s.item.codigo,
            "descricao": s.item.descricao,
            "unidade": s.item.unidade,
            "saldo": s.quantidade
        }
        for s in saldos
    ]
    return jsonify({"itens": itens})

# --- REGISTRAR BAIXA (SEM MEXER NO SALDO, SÓ GRAVA PARA APROVAÇÃO) ---
@bp_baixa_tecnico.route("/registrar", methods=["POST"])
def registrar():
    tecnico_id = request.form.get("tecnico_id", type=int)
    tipo_servico_id = request.form.get("tipo_servico_id", type=int)
    responsavel = request.form.get("responsavel")
    observacao = request.form.get("observacao", "")

    item_ids = request.form.getlist("item_id[]")
    quantidades = request.form.getlist("quantidade[]")

    if not tecnico_id or not tipo_servico_id:
        flash("Preencha todos os campos obrigatórios!", "warning")
        return redirect(url_for("baixa_tecnico.formulario_mobile_dedicado", tecnico_id=tecnico_id))

    if not item_ids or not any(q for q in quantidades if q and int(q) > 0):
        flash("Adicione ao menos um item com quantidade!", "warning")
        return redirect(url_for("baixa_tecnico.formulario_mobile_dedicado", tecnico_id=tecnico_id))

    try:
        baixa = BaixaTecnica(
            tecnico_id=tecnico_id,
            tipo_servico_id=tipo_servico_id,
            endereco="",   # Mobile não usa endereço no momento
            bairro="",
            codigo_imovel="",
            responsavel=responsavel,
            observacao=observacao,
            status="pendente"
        )
        db.session.add(baixa)
        db.session.commit()

        for item_id, qtd in zip(item_ids, quantidades):
            quantidade = int(qtd) if qtd else 0
            if quantidade > 0:
                db.session.add(
                    BaixaTecnicaItem(
                        baixa_tecnica_id=baixa.id,
                        item_id=item_id,
                        quantidade=quantidade
                    )
                )
        db.session.commit()
        flash("✅ Baixa registrada com sucesso! Aguarde aprovação da equipe técnica.", "success")

    except Exception as e:
        db.session.rollback()
        flash("Erro ao registrar baixa. Tente novamente.", "danger")
        print(e)

    return redirect(url_for("baixa_tecnico.formulario_mobile_dedicado", tecnico_id=tecnico_id))
