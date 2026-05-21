import logging
from config.settings import NOTION_GASTOS_DB_ID
from notion.client import create_page

logger = logging.getLogger(__name__)


def create_expense_entry(
    categoria: str,
    cantidad: float,
    fecha: str,
    descripcion: str = "",
) -> dict:
    """
    Registra un gasto en BASE 2 — GASTOS DETALLADOS y actualiza
    las bases de proyecciones y ahorros en cascada.
    """
    properties = {
        "Descripción ": {
            "title": [{"text": {"content": descripcion[:2000] if descripcion else categoria}}]
        },
        "Detalle del gasto. ": {
            "select": {"name": categoria}
        },
        "Cantidad ": {
            "number": cantidad
        },
        "Fecha": {
            "date": {"start": fecha}
        },
    }

    page = create_page(NOTION_GASTOS_DB_ID, properties)

    # Importación local para evitar circular import (queries importa de client, no de expenses)
    from notion.queries import update_proyeccion_gasto, update_ahorro, update_prioridad

    try:
        update_proyeccion_gasto(categoria, cantidad, descripcion)
    except Exception as e:
        logger.warning(f"No se pudo actualizar proyección de gasto para '{categoria}': {e}")

    # Siempre intentar actualizar ahorros.
    # fallback_a_incompleto=True solo para "Ahorros" (asigna a la primera meta incompleta
    # si no hay keyword match). Para otras categorías, solo actúa si hay keyword match.
    try:
        update_ahorro(cantidad, descripcion, fallback_a_incompleto=(categoria == "Ahorros"))
    except Exception as e:
        logger.warning(f"No se pudo actualizar ahorro: {e}")

    # Actualizar prioridades financieras según descripción del pago
    try:
        update_prioridad(descripcion, cantidad)
    except Exception as e:
        logger.warning(f"No se pudo actualizar prioridad para '{descripcion}': {e}")

    # Recalcular y sincronizar tabla de prioridades en Notion
    try:
        from notion.priorities import update_tabla_prioridades
        update_tabla_prioridades()
    except Exception as e:
        logger.warning(f"No se pudo actualizar tabla de prioridades: {e}")

    return page
