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

_TEMPLATE_ID = "366ad4e6-2362-8070-84a7-f974ad50597f"
_PARENT_BUDGET_ID = "44ca7f3e-c806-4a86-a3a4-9a57d45c641d"

_MESES_ES_MAYUS = {
    1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL",
    5: "MAYO", 6: "JUNIO", 7: "JULIO", 8: "AGOSTO",
    9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE",
}
_FRASES_MES = [
    "Mes de éxito y abundancia",
    "Mes de más ganancias y crecimiento",
    "Mes de expansión financiera",
    "Mes de logros extraordinarios",
]

# Tipos de bloque que no se pueden copiar via API
_SKIP_BLOCK_TYPES = {"child_database", "unsupported", "template"}


# ── Helpers ──────────────────────────────────────────────────────────────────

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


def _limpiar_nulos(obj):
    """Elimina recursivamente claves con valor None (la API Notion las rechaza)."""
    if isinstance(obj, dict):
        return {k: _limpiar_nulos(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_limpiar_nulos(i) for i in obj]
    return obj


def _leer_bloques(client, block_id: str, depth: int = 0) -> list[dict]:
    """Lee bloques de una página Notion para duplicar (máx profundidad 2)."""
    if depth > 2:
        return []
    bloques = []
    cursor = None
    while True:
        params = {"block_id": block_id, "page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        try:
            resp = client.blocks.children.list(**params)
        except Exception as e:
            logger.warning(f"No se pudo leer bloques de {block_id}: {e}")
            break
        for b in resp.get("results", []):
            tipo = b.get("type", "")
            if tipo in _SKIP_BLOCK_TYPES:
                continue
            contenido = _limpiar_nulos(dict(b.get(tipo, {})))
            bloque: dict = {"type": tipo, tipo: contenido}
            if b.get("has_children") and depth < 2:
                hijos = _leer_bloques(client, b["id"], depth + 1)
                if hijos:
                    bloque["children"] = hijos
            bloques.append(bloque)
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return bloques


# ── Tarea: alertas diarias ────────────────────────────────────────────────────

def check_pagos_proximos(dias: int = 3) -> list[dict]:
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


# ── Tarea: reporte mensual ────────────────────────────────────────────────────

async def send_reporte_mensual(bot, chat_id: int) -> None:
    """Envía resumen del mes anterior el día 1 a las 8:00 AM."""
    from notion.queries import get_resumen_mes_anterior
    from bot.responses import reporte_mensual_mensaje
    try:
        data = get_resumen_mes_anterior()
        texto = reporte_mensual_mensaje(data)
        await bot.send_message(chat_id=chat_id, text=texto, parse_mode="Markdown")
        logger.info(f"Reporte mensual enviado a {chat_id}.")
    except Exception as e:
        logger.error(f"Error enviando reporte mensual: {e}")


# ── Tarea: crear página del mes nuevo ────────────────────────────────────────

async def _pagina_mes_existe(client, mes_nombre: str, año: int) -> bool:
    """Verifica si ya existe una página del mes actual bajo el parent de presupuesto."""
    busqueda = f"{mes_nombre} {año}"
    cursor = None
    while True:
        params = {"block_id": _PARENT_BUDGET_ID, "page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        try:
            resp = client.blocks.children.list(**params)
        except Exception:
            return False
        for b in resp.get("results", []):
            if b.get("type") == "child_page":
                titulo = b.get("child_page", {}).get("title", "")
                if busqueda in titulo:
                    return True
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return False


async def catchup_mes_nuevo() -> None:
    """
    Catch-up al arranque: si es día 1 y la página del mes no existe todavía,
    la crea. Evita que un reinicio del proceso en Railway pierda el trigger.
    """
    hoy = date.today()
    if hoy.day != 1:
        return
    from notion_client import Client
    from config.settings import NOTION_TOKEN
    client = Client(auth=NOTION_TOKEN)
    mes_nombre = _MESES_ES_MAYUS[hoy.month]
    if await _pagina_mes_existe(client, mes_nombre, hoy.year):
        logger.info(f"Catch-up: página de {mes_nombre} {hoy.year} ya existe, nada que hacer.")
        return
    logger.info(f"Catch-up: día 1 y no existe página de {mes_nombre} {hoy.year} — creando…")
    await crear_mes_nuevo()


async def crear_mes_nuevo() -> None:
    """
    Crea una nueva página mensual en Notion copiando la plantilla.
    Se ejecuta el día 1 a las 00:01 AM.
    """
    from notion_client import Client
    from config.settings import NOTION_TOKEN

    client = Client(auth=NOTION_TOKEN)
    hoy = date.today()

    mes_nombre = _MESES_ES_MAYUS[hoy.month]
    frase = _FRASES_MES[(hoy.month - 1) % len(_FRASES_MES)]
    titulo = f"FINANZAS DE {mes_nombre} {hoy.year} || {frase}"

    try:
        bloques = _leer_bloques(client, _TEMPLATE_ID)
        logger.info(f"Plantilla leída: {len(bloques)} bloques.")

        nueva = client.pages.create(
            parent={"page_id": _PARENT_BUDGET_ID},
            properties={"title": [{"text": {"content": titulo}}]},
            children=bloques[:100],
        )
        # Bloques adicionales si superan el límite de 100 por llamada
        for i in range(100, len(bloques), 100):
            client.blocks.children.append(
                block_id=nueva["id"],
                children=bloques[i:i + 100],
            )
        logger.info(f"Página del mes creada: '{titulo}' | id={nueva['id']}")
    except Exception as e:
        logger.error(f"Error creando página del mes nuevo: {e}")


# ── Scheduler principal ───────────────────────────────────────────────────────

def build_scheduler(bot) -> AsyncIOScheduler:
    """
    Configura el scheduler con 3 tareas:
    - Cada día 09:30 → alertas de pagos próximos + actualizar prioridades
    - Día 1 a las 00:01 → crear página del mes nuevo en Notion
    - Día 1 a las 08:00 → enviar reporte del mes anterior por Telegram
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

    # ── Job 2: crear página del mes nuevo ──────────────────────────────
    async def _job_mes_nuevo():
        await crear_mes_nuevo()

    scheduler.add_job(
        _job_mes_nuevo,
        CronTrigger(day=1, hour=0, minute=1, timezone="America/Guayaquil"),
        id="mes_nuevo",
        replace_existing=True,
    )

    # ── Job 3: reporte mensual ─────────────────────────────────────────
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
