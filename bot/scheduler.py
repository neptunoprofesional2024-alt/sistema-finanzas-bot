from __future__ import annotations
import calendar
import logging
import os
from datetime import date

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config.settings import PAGOS_FIJOS

logger = logging.getLogger(__name__)

# Ruta al archivo que persiste el chat_id entre reinicios del bot
CHAT_ID_FILE = os.path.join(os.path.dirname(__file__), "..", ".chat_id")


def load_chat_id() -> int | None:
    try:
        with open(CHAT_ID_FILE) as f:
            return int(f.read().strip())
    except Exception:
        return None


def save_chat_id(chat_id: int) -> None:
    try:
        with open(CHAT_ID_FILE, "w") as f:
            f.write(str(chat_id))
    except Exception as e:
        logger.warning(f"No se pudo guardar chat_id: {e}")


def _proxima_fecha_pago(dia: int) -> date:
    """Devuelve la próxima fecha de pago para un día del mes dado."""
    hoy = date.today()
    ultimo_dia_mes = calendar.monthrange(hoy.year, hoy.month)[1]
    dia_ajustado = min(dia, ultimo_dia_mes)
    fecha = hoy.replace(day=dia_ajustado)
    if fecha < hoy:
        # Ya pasó este mes → siguiente mes
        if hoy.month == 12:
            año, mes = hoy.year + 1, 1
        else:
            año, mes = hoy.year, hoy.month + 1
        ultimo_dia_sig = calendar.monthrange(año, mes)[1]
        fecha = date(año, mes, min(dia, ultimo_dia_sig))
    return fecha


def check_pagos_proximos(dias: int = 3) -> list[dict]:
    """Devuelve pagos que vencen dentro de los próximos `dias` días, ordenados por fecha."""
    hoy = date.today()
    alertas = []
    for concepto, info in PAGOS_FIJOS.items():
        fecha_pago = _proxima_fecha_pago(info["dia"])
        delta = (fecha_pago - hoy).days
        if 0 <= delta <= dias:
            alertas.append({
                "concepto": info["descripcion"],
                "monto": info["monto"],
                "fecha": fecha_pago,
                "dias": delta,
            })
    return sorted(alertas, key=lambda a: a["dias"])


async def send_alertas_diarias(bot, chat_id: int) -> None:
    alertas = check_pagos_proximos(dias=3)
    if not alertas:
        return
    from bot.responses import alertas_mensaje
    texto = alertas_mensaje(alertas)
    await bot.send_message(chat_id=chat_id, text=texto)
    logger.info(f"Alertas diarias enviadas a {chat_id}: {len(alertas)} pago(s).")


def build_scheduler(bot) -> AsyncIOScheduler:
    """Crea y configura el scheduler. Corre todos los días a las 9:30 AM Ecuador (UTC-5)."""
    scheduler = AsyncIOScheduler(timezone="America/Guayaquil")

    async def _job():
        chat_id = load_chat_id()
        if not chat_id:
            logger.warning("Scheduler: no hay chat_id guardado, omitiendo alerta.")
            return
        # Actualizar tabla de prioridades antes de enviar alertas
        try:
            from notion.priorities import update_tabla_prioridades
            update_tabla_prioridades()
        except Exception as e:
            logger.warning(f"Scheduler: no se pudo actualizar prioridades: {e}")
        await send_alertas_diarias(bot, chat_id)

    scheduler.add_job(
        _job,
        CronTrigger(hour=9, minute=30, timezone="America/Guayaquil"),
        id="alertas_diarias",
        replace_existing=True,
    )
    return scheduler
