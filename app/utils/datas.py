"""UTC storage and explicit Sao Paulo presentation for operational timestamps."""
from datetime import datetime, timezone, timedelta, time
from zoneinfo import ZoneInfo

FUSO_LOCAL = ZoneInfo('America/Sao_Paulo')


def horario_local(valor):
    if valor is None:
        return None
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=timezone.utc)
    return valor.astimezone(FUSO_LOCAL)


def formatar_horario(valor, formato='%d/%m/%Y %H:%M'):
    return horario_local(valor).strftime(formato) if valor else '-'


def hoje_local():
    return datetime.now(FUSO_LOCAL).date()


def limites_dia_utc(dia):
    inicio = datetime.combine(dia, time.min, tzinfo=FUSO_LOCAL)
    fim = inicio + timedelta(days=1)
    return (inicio.astimezone(timezone.utc).replace(tzinfo=None),
            fim.astimezone(timezone.utc).replace(tzinfo=None))
