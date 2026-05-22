from __future__ import annotations
from notion_client import Client
from notion_client.errors import APIResponseError
from config.settings import NOTION_TOKEN

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = Client(auth=NOTION_TOKEN)
    return _client


def safe_query(db_id: str, **kwargs) -> list[dict]:
    """Ejecuta query con paginación automática y manejo de errores."""
    client = get_client()
    results = []
    cursor = None

    try:
        while True:
            params = {"database_id": db_id, **{k: v for k, v in kwargs.items() if v is not None}}
            if cursor:
                params["start_cursor"] = cursor

            response = client.databases.query(**params)
            results.extend(response.get("results", []))

            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")

    except APIResponseError as e:
        raise RuntimeError(f"Error consultando Notion (DB: {db_id}): {e}") from e

    return results


def create_page(db_id: str, properties: dict) -> dict:
    """Crea una página en una base de Notion."""
    client = get_client()
    try:
        return client.pages.create(
            parent={"database_id": db_id},
            properties=properties,
        )
    except APIResponseError as e:
        raise RuntimeError(f"Error creando página en Notion (DB: {db_id}): {e}") from e


def update_page(page_id: str, properties: dict) -> dict:
    """Actualiza propiedades de una página existente en Notion."""
    client = get_client()
    try:
        return client.pages.update(page_id=page_id, properties=properties)
    except APIResponseError as e:
        raise RuntimeError(f"Error actualizando página {page_id}: {e}") from e
