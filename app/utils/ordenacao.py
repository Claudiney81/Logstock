"""Presentation order only; preserve the original order within each origin."""


def cliente_primeiro(itens):
    return sorted(itens, key=lambda item: 0 if (
        str(getattr(item, 'tipo_estoque', '') or '').strip().lower() == 'cliente'
    ) else 1)
