from __future__ import annotations
import calendar
import logging
import os
from datetime import date

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config.settings import PAGOS_FIJOS

logger = logging.getLogger(__name__)

CHAT_ID_FILE = os.path.join(os.path.dirname(__file__), "..", ".chat_id")

_MESES_ES_MAYUS = {
    1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL",
    5: "MAYO", 6: "JUNIO", 7: "JULIO", 8: "AGOSTO",
    9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE",
}

# Montos "Falta" iniciales por concepto al arrancar el mes nuevo.
# Coinciden con el $ Proyección de cada fila en la tabla de prioridades.
_PRIORIDADES_FALTA_INICIAL: list[tuple[str, float]] = [
    ("Tarjeta Pacífico (Laptop)", 205),
    ("Pago Coral",                130),
    ("Alimentación hogar",        212),
    ("Recarga/plan",               20),
    ("Higiene",                    72),
    ("Salud + suplementos",       131),
    ("Transporte total restante", 110),
    ("Viáticos/reuniones",         48),
    ("Cursos/libros",              20),
    ("Seminarios/talleres",        50),
    ("Compras/deseos",            400),
    ("Viaje playa",               400),
    ("Proteínas/entrenamiento",   400),
    ("Ahorro casa",               800),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_chat_id() -> int | None:
    # Prioridad: env var (persiste en Railway) > archivo en disco
    env_val = os.getenv("TELEGRAM_CHAT_ID")
    if env_val:
        try:
            return int(env_val.strip())
        except ValueError:
            pass
    try:
        with open(CHAT_ID_FILE) as f:
            return int(f.read().strip())
    except Exception:
        return None


def save_chat_id(chat_id: int) -> None:
    # Actualiza caché en handlers para que surta efecto sin reiniciar
    try:
        import bot.handlers as _h
        _h._AUTHORIZED_CHAT_ID = chat_id
    except Exception:
        pass
    try:
        with open(CHAT_ID_FILE, "w") as f:
            f.write(str(chat_id))
    except Exception as e:
        logger.warning(f"No se pudo guardar chat_id en disco: {e}")


def _proxima_fecha_pago(dia: int) -> date:
    hoy = date.today()
    ultimo_dia_mes = calendar.monthrange(hoy.year, hoy.month)[1]
    dia_ajustado = min(dia, ultimo_dia_mes)
    fecha = hoy.replace(day=dia_ajustado)
    if fecha < hoy:
        if hoy.month == 12:
            año, mes = hoy.year + 1, 1
        else:
            año, mes = hoy.year, hoy.month + 1
        ultimo_dia_sig = calendar.monthrange(año, mes)[1]
        fecha = date(año, mes, min(dia, ultimo_dia_sig))
    return fecha


# ── Tarea: alertas diarias ────────────────────────────────────────────────────

def check_pagos_proximos(dias: int = 3) -> list[dict]:
    """
    Devuelve los pagos que vencen dentro de `dias` días.
    Las tarjetas de crédito solo aparecen si su fecha de vencimiento
    está en el mes siguiente al actual (son deudas del gasto del mes en curso).
    """
    hoy = date.today()
    mes_siguiente = (hoy.month % 12) + 1
    alertas = []
    for concepto, info in PAGOS_FIJOS.items():
        fecha_pago = _proxima_fecha_pago(info["dia"])
        delta = (fecha_pago - hoy).days
        if not (0 <= delta <= dias):
            continue
        # Tarjetas de crédito: solo alertar cuando el vencimiento cae en el mes siguiente
        if info.get("es_tarjeta_credito") and fecha_pago.month != mes_siguiente:
            continue
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


# ── Tarea: reporte mensual ────────────────────────────────────────────────────

async def send_reporte_mensual(bot, chat_id: int) -> None:
    """Envía resumen del mes que acaba de terminar (día 1, 08:00 AM)."""
    from notion.queries import get_resumen_mes_anterior
    from bot.responses import reporte_mensual_mensaje
    try:
        data = get_resumen_mes_anterior()
        texto = reporte_mensual_mensaje(data)
        await bot.send_message(chat_id=chat_id, text=texto, parse_mode="Markdown")
        logger.info(f"Reporte mensual enviado a {chat_id}.")
    except Exception as e:
        logger.error(f"Error enviando reporte mensual: {e}")


# ── Tarea: reset mensual de la página maestra ────────────────────────────────

def _archivar_registros(client, db_id: str) -> int:
    """Archiva todos los registros activos de una base de datos. Retorna el total."""
    cursor = None
    total = 0
    while True:
        params = {"database_id": db_id, "page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        resp = client.databases.query(**params)
        for p in resp.get("results", []):
            if p.get("archived"):
                continue
            try:
                client.pages.update(p["id"], archived=True)
                total += 1
            except Exception:
                pass
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return total


def _resetear_filas(client, db_id: str, props: dict) -> int:
    """Actualiza todas las filas activas de una DB con las props dadas. Retorna el total."""
    cursor = None
    total = 0
    while True:
        params = {"database_id": db_id, "page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        resp = client.databases.query(**params)
        for p in resp.get("results", []):
            if p.get("archived"):
                continue
            try:
                client.pages.update(p["id"], properties=props)
                total += 1
            except Exception as e:
                logger.warning(f"Error reseteando fila {p['id'][:8]}: {e}")
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return total


def _restaurar_prioridades(client, db_id: str) -> int:
    """Restaura el campo Falta en la tabla de prioridades usando _PRIORIDADES_FALTA_INICIAL."""
    cursor = None
    total = 0
    while True:
        params = {"database_id": db_id, "page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        resp = client.databases.query(**params)
        for p in resp.get("results", []):
            if p.get("archived"):
                continue
            pr = p.get("properties", {})
            concepto = "".join(
                t.get("plain_text", "") for t in pr.get("Concepto", {}).get("rich_text", [])
            ).lower()
            falta = next(
                (monto for kw, monto in _PRIORIDADES_FALTA_INICIAL
                 if kw.lower() in concepto),
                None,
            )
            if falta is not None:
                try:
                    client.pages.update(p["id"], properties={"Falta": {"number": falta}})
                    total += 1
                except Exception as e:
                    logger.warning(f"Error restaurando prioridad {concepto!r}: {e}")
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return total


async def reset_mes_nuevo(bot=None) -> bool:
    """
    Resetea la página maestra para el mes nuevo:
      1. Archiva todos los registros de gastos e ingresos detallados
      2. Resetea $ Real y Etiquetas en proyecciones de egresos
      3. Resetea Ganancias Reales en proyecciones de ingresos
      4. Resetea AHORRADO y Selección en ahorros
      5. Restaura Falta en prioridades a los montos proyectados
      6. Notifica por Telegram
    """
    from notion_client import Client
    from config.settings import (
        NOTION_TOKEN,
        NOTION_GASTOS_DB_ID, NOTION_INGRESOS_DB_ID,
        NOTION_PROYECCIONES_GASTOS_DB_ID, NOTION_PROYECCIONES_INGRESOS_DB_ID,
        NOTION_AHORROS_DB_ID, NOTION_PRIORIDADES_DB_ID,
    )

    client = Client(auth=NOTION_TOKEN)
    hoy = date.today()
    mes = _MESES_ES_MAYUS[hoy.month]
    logger.info(f"Iniciando reset mensual para {mes} {hoy.year}…")

    try:
        g = _archivar_registros(client, NOTION_GASTOS_DB_ID)
        i = _archivar_registros(client, NOTION_INGRESOS_DB_ID)
        logger.info(f"Archivados: {g} gastos, {i} ingresos")

        pg = _resetear_filas(client, NOTION_PROYECCIONES_GASTOS_DB_ID, {
            "$ Real ": {"number": 0},
            "Descripción opcional ": {"rich_text": []},
            "Etiquetas": {"status": {"name": "Sin empezar"}},
        })
        pi = _resetear_filas(client, NOTION_PROYECCIONES_INGRESOS_DB_ID, {
            "Ganancias Reales ": {"number": 0},
        })
        ah = _resetear_filas(client, NOTION_AHORROS_DB_ID, {
            "AHORRADO ": {"number": 0},
            "Selección": {"select": {"name": "NO AHORROS"}},
        })
        pr = _restaurar_prioridades(client, NOTION_PRIORIDADES_DB_ID)
        logger.info(f"Reset: proy_gastos={pg}, proy_ing={pi}, ahorros={ah}, prioridades={pr}")

        if bot:
            chat_id = load_chat_id()
            if chat_id:
                await bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"🗓️ ¡Nuevo mes iniciado!\n"
                        f"Todas las tablas reseteadas para *{mes} {hoy.year}*.\n"
                        f"Los valores proyectados se mantienen.\n"
                        f"¡A darle con todo! 💪"
                    ),
                    parse_mode="Markdown",
                )
        return True

    except Exception as e:
        logger.error(f"Error en reset_mes_nuevo: {e}")
        return False


# ── Scheduler principal ───────────────────────────────────────────────────────

def build_scheduler(bot) -> AsyncIOScheduler:
    """
    Configura el scheduler con 3 tareas:
    - Cada día 09:30 → alertas de pagos próximos + actualizar prioridades
    - Día 1 a las 00:01 → reset mensual de la página maestra
    - Día 1 a las 08:00 → reporte del mes anterior por Telegram
    """
    scheduler = AsyncIOScheduler(timezone="America/Guayaquil")

    # ── Job 1: alertas diarias ──────────────────────────────────────────
    async def _job_alertas():
        chat_id = load_chat_id()
        if not chat_id:
            logger.warning("Scheduler: no hay chat_id guardado, omitiendo alerta.")
            return
        try:
            from notion.priorities import update_tabla_prioridades
            update_tabla_prioridades()
        except Exception as e:
            logger.warning(f"Scheduler: no se pudo actualizar prioridades: {e}")
        await send_alertas_diarias(bot, chat_id)

    scheduler.add_job(
        _job_alertas,
        CronTrigger(hour=9, minute=30, timezone="America/Guayaquil"),
        id="alertas_diarias",
        replace_existing=True,
    )

    # ── Job 2: reset mensual ────────────────────────────────────────────
    async def _job_reset():
        await reset_mes_nuevo(bot)

    scheduler.add_job(
        _job_reset,
        CronTrigger(day=1, hour=0, minute=1, timezone="America/Guayaquil"),
        id="reset_mensual",
        replace_existing=True,
    )

    # ── Job 3: reporte mensual ──────────────────────────────────────────
    async def _job_reporte():
        chat_id = load_chat_id()
        if not chat_id:
            return
        await send_reporte_mensual(bot, chat_id)

    scheduler.add_job(
        _job_reporte,
        CronTrigger(day=1, hour=8, minute=0, timezone="America/Guayaquil"),
        id="reporte_mensual",
        replace_existing=True,
    )

    return scheduler
