from app import create_app, db
from app.models import NotaFiscalEntrada, NotaFiscalItem

app = create_app()

with app.app_context():
    notas = NotaFiscalEntrada.query.all()
    alterados = 0

    for nota in notas:
        for item in nota.itens:
            # Se o valor unitário parece errado (ex: está 2290 em vez de 22.90)
            if item.valor_unitario > 100:
                print(f"Corrigindo item {item.id}: {item.valor_unitario} -> {item.valor_unitario / 100}")
                item.valor_unitario = item.valor_unitario / 100
                alterados += 1

        # não precisa salvar total_nota, pois já é calculado dinamicamente

    db.session.commit()
    print(f"Correção concluída! {alterados} itens atualizados.")
