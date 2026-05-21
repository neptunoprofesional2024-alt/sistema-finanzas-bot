import logging
from config.settings import NOTION_INGRESOS_DB_ID
from notion.client import create_page

logger = logging.getLogger(__name__)


def create_income_entry(
    categoria: str,
    monto: float,
    fecha: str,
    descripcion: str = "",
) -> dict:
    """
    Registra un ingreso en BASE 1 — INGRESOS DETALLADOS y actualiza
    la base de proyecciones de ingresos en cascada.
    """
    properties = {
        "Descripción ": {
            "title": [{"text": {"content": descripcion[:2000] if descripcion else categoria}}]
        },
        "Descripción de Ingreso": {
            "select": {"name": categoria}
        },
        "Monto": {
            "number": monto
        },
        "Fecha": {
            "date": {"start": fecha}
        },
    }

    page = create_page(NOTION_INGRESOS_DB_ID, properties)

    from notion.queries import update_proyeccion_ingreso

    try:
        update_proyeccion_ingreso(categoria, monto)
    except Exception as e:
        logger.warning(f"No se pudo actualizar proyección de ingreso para '{categoria}': {e}")

    return page
