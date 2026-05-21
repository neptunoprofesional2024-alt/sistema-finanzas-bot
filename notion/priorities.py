from __future__ import annotations
from datetime import date
from notion.client import safe_query, update_page
from config.settings import NOTION_PRIORIDADES_DB_ID


_MESES_ES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio",
             "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

# Fuente de verdad de todos los conceptos de prioridades
_CONCEPTO_CONFIG: dict = {
    "Alquiler": {
        "dia_vencimiento": 20,
        "tipo": "hogar",
        "proyeccion_fila": "Alquiler o Hipoteca ",
        "monto_fijo": 400,
    },
    "Tarjeta Pacífico (Laptop)": {
        "dia_vencimiento": 5,
        "tipo": "deuda",
        "proyeccion_fila": "Tarjeta de crédito Pacifico (Laptop)",
        "monto_fijo": 205,
    },
    "Tarjeta Pichincha": {
        "dia_vencimiento": 12,
        "tipo": "deuda",
        "proyeccion_fila": "Tarjeta de crédito Pichincha.",
        "monto_fijo": 95,
    },
    "Pago Coral": {
        "dia_vencimiento": 1,
        "tipo": "alimentacion",
        "proyeccion_fila": "Pago al Coral",
        "monto_fijo": 130,
    },
    "Alimentación hogar": {
        "dia_vencimiento": None,
        "tipo": "alimentacion",
        "proyeccion_fila": "Alimentación\xa0de Hogar ",
        "monto_fijo": 212,
    },
    "Recarga/plan": {
        "dia_vencimiento": 26,
        "tipo": "hogar",
        "proyeccion_fila": "Recarga o plan ",
        "monto_fijo": 20,
    },
    "Higiene": {
        "dia_vencimiento": None,
        "tipo": "otros",
        "proyeccion_fila": "Higiene\xa0Personal. ",
        "monto_fijo": 72,
    },
    "Salud + suplementos": {
        "dia_vencimiento": None,
        "tipo": "otros",
        "proyeccion_fila": "Salud + suplementos y vitaminas",
        "monto_fijo": 131,
    },
    "Viáticos/reuniones": {
        "dia_vencimiento": None,
        "tipo": "otros",
        "proyeccion_fila": "Viaticos y Reuniones",
        "monto_fijo": 48,
    },
    "Transporte total restante": {
        "dia_vencimiento": None,
        "tipo": "transporte",
        "proyeccion_fila": None,
        "proyeccion_filas": ["Transporte en moto ", "Taxis personales\xa0", "Tranporte Público "],
        "monto_fijo": 110,
    },
    "Proteínas/entrenamiento": {
        "dia_vencimiento": None,
        "tipo": "otros",
        "proyeccion_fila": "AHOOROS PARA PROTEÍNAS Y ENTRENAMIENTO: ",
        "monto_fijo": 400,
    },
    "Viaje playa": {
        "dia_vencimiento": None,
        "tipo": "otros",
        "proyeccion_fila": "VIAJE A LA PLAYA CON AMIGOS ",
        "monto_fijo": 400,
    },
    "Compras/deseos": {
        "dia_vencimiento": None,
        "tipo": "otros",
        "proyeccion_fila": "COMPRAS O DESEOS ",
        "monto_fijo": 400,
    },
    "Cursos/libros": {
        "dia_vencimiento": None,
        "tipo": "otros",
        "proyeccion_fila": "Cursos o Libros. ",
        "monto_fijo": 20,
    },
    "Seminarios/talleres": {
        "dia_vencimiento": None,
        "tipo": "otros",
        "proyeccion_fila": "Seminarios o talleres. ",
        "monto_fijo": 50,
    },
    "Ahorro casa": {
        "dia_vencimiento": None,
        "tipo": "otros",
        "proyeccion_fila": "AHORRO PARA ENTRADA DE CASA: ",
        "monto_fijo": 800,
    },
}

# Compatibilidad con update_prioridad() en queries.py
_MONTO_INICIAL: dict = {k: v["monto_fijo"] for k, v in _CONCEPTO_CONFIG.items()}


# ── Score helpers ────────────────────────────────────────────────────────────

def _peso_fecha(dias: int) -> float:
    if dias <= 3:
        return 10.0
    if dias <= 7:
        return 7.0
    if dias <= 15:
        return 5.0
    return 2.0


def _peso_monto(falta: float) -> float:
    if falta > 300:
        return 10.0
    if falta >= 100:
        return 7.0
    if falta >= 50:
        return 5.0
    return 2.0


def _peso_tipo(tipo: str) -> float:
    return {"deuda": 10.0, "hogar": 8.0, "alimentacion": 7.0, "transporte": 5.0, "otros": 3.0}.get(tipo, 3.0)


def _emoji_score(score: float) -> str:
    if score >= 8.0:
        return "🔴"
    if score >= 5.0:
        return "🟠"
    return "🟡"


# ── Fecha de vencimiento ─────────────────────────────────────────────────────

def _proxima_fecha_vencimiento(dia_mes: int, hoy: date) -> date:
    try:
        venc = hoy.replace(day=dia_mes)
    except ValueError:
        return hoy  # día inválido para el mes (ej. 31 en febrero)
    if venc < hoy:
        if hoy.month == 12:
            venc = venc.replace(year=hoy.year + 1, month=1)
        else:
            venc = venc.replace(month=hoy.month + 1)
    return venc


# ── Datos de proyecciones ────────────────────────────────────────────────────

def _get_proyecciones_data() -> dict:
    """Retorna {titulo_fila: {real, proyectado}} leyendo proyecciones de egresos una sola vez."""
    from config.settings import NOTION_PROYECCIONES_GASTOS_DB_ID
    pages = safe_query(NOTION_PROYECCIONES_GASTOS_DB_ID)
    result: dict = {}
    for p in pages:
        props = p["properties"]
        title_parts = props.get("Egreso determinado ", {}).get("title", [])
        titulo = title_parts[0]["plain_text"] if title_parts else ""
        real = props.get("$ Real ", {}).get("number") or 0.0
        proyectado = props.get("$ Proyección", {}).get("number") or 0.0
        result[titulo] = {"real": real, "proyectado": proyectado}
    return result


def _calcular_falta_concepto(concepto: str, cfg: dict, proyecciones: dict) -> tuple[float, float, float]:
    """Retorna (falta, real, proyectado) para un concepto."""
    monto_fijo = float(cfg["monto_fijo"])

    if concepto == "Transporte total restante":
        filas = cfg.get("proyeccion_filas", [])
        total_real = sum(proyecciones.get(f, {}).get("real", 0.0) for f in filas)
        total_proy = sum(proyecciones.get(f, {}).get("proyectado", 0.0) for f in filas)
        proy_ref = total_proy if total_proy > 0 else monto_fijo
        return round(max(0.0, proy_ref - total_real), 2), round(total_real, 2), round(proy_ref, 2)

    fila = cfg.get("proyeccion_fila")
    if fila and fila in proyecciones:
        datos = proyecciones[fila]
        real = datos["real"]
        proy = datos["proyectado"] if datos["proyectado"] > 0 else monto_fijo
        return round(max(0.0, proy - real), 2), round(real, 2), round(proy, 2)

    return monto_fijo, 0.0, monto_fijo


# ── API pública ──────────────────────────────────────────────────────────────

def calcular_prioridades() -> list[dict]:
    """
    Calcula dinámicamente el ranking de prioridades financieras.
    Fuente de datos: proyecciones de egresos + PAGOS_FIJOS.
    Excluye conceptos con falta <= 0 (ya cubiertos).
    """
    hoy = date.today()
    proyecciones = _get_proyecciones_data()

    items = []
    for concepto, cfg in _CONCEPTO_CONFIG.items():
        falta, real, proyectado = _calcular_falta_concepto(concepto, cfg, proyecciones)
        if falta <= 0:
            continue

        dia_venc = cfg.get("dia_vencimiento")
        if dia_venc is not None:
            venc_fecha = _proxima_fecha_vencimiento(dia_venc, hoy)
            dias = (venc_fecha - hoy).days
        else:
            venc_fecha = None
            dias = 30

        pf = _peso_fecha(dias)
        pm = _peso_monto(falta)
        pt = _peso_tipo(cfg["tipo"])
        score = round(pf * 0.5 + pm * 0.3 + pt * 0.2, 3)

        items.append({
            "concepto": concepto,
            "falta": falta,
            "real": real,
            "proyectado": proyectado,
            "dias": dias,
            "dia_vencimiento": dia_venc,
            "vencimiento_fecha": venc_fecha,
            "tipo": cfg["tipo"],
            "score": score,
            "urgencia": _emoji_score(score),
        })

    items.sort(key=lambda x: x["score"], reverse=True)
    for i, item in enumerate(items, 1):
        item["numero"] = i

    return items


def update_tabla_prioridades() -> None:
    """
    Sincroniza NOTION_PRIORIDADES_DB_ID con los valores calculados:
    - 'Falta' (number): monto pendiente real desde proyecciones
    - 'Prioridad' (title): nuevo número de ranking
    Solo actualiza filas que ya existen en Notion (match por Concepto).
    """
    try:
        prioridades = calcular_prioridades()
        pages = safe_query(NOTION_PRIORIDADES_DB_ID)
    except Exception:
        return

    notion_por_concepto: dict = {}
    for page in pages:
        props = page["properties"]
        concepto_parts = props.get("Concepto", {}).get("rich_text", [])
        concepto = concepto_parts[0]["plain_text"].strip() if concepto_parts else ""
        if concepto:
            notion_por_concepto[concepto] = page

    for item in prioridades:
        page = notion_por_concepto.get(item["concepto"])
        if not page:
            continue
        try:
            update_page(page["id"], {
                "Falta": {"number": item["falta"]},
                "Prioridad": {"title": [{"text": {"content": str(item["numero"])}}]},
            })
        except Exception:
            pass


def get_all_prioridades() -> list[dict]:
    return calcular_prioridades()


def get_top_prioridades(n: int = 3) -> list[dict]:
    return calcular_prioridades()[:n]
