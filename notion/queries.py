from __future__ import annotations
from datetime import datetime, date
from config.settings import (
    NOTION_INGRESOS_DB_ID,
    NOTION_GASTOS_DB_ID,
    NOTION_PROYECCIONES_GASTOS_DB_ID,
    NOTION_PROYECCIONES_INGRESOS_DB_ID,
    NOTION_AHORROS_DB_ID,
    NOTION_PRIORIDADES_DB_ID,
)
from notion.client import safe_query, update_page


def _month_filter(date_prop: str) -> dict:
    """Filtro para el mes actual."""
    now = date.today()
    start = f"{now.year}-{now.month:02d}-01"
    # último día del mes
    if now.month == 12:
        end = f"{now.year + 1}-01-01"
    else:
        end = f"{now.year}-{now.month + 1:02d}-01"

    return {
        "and": [
            {"property": date_prop, "date": {"on_or_after": start}},
            {"property": date_prop, "date": {"before": end}},
        ]
    }


_SORT_FECHA_ASC = [{"property": "Fecha", "direction": "ascending"}]


def get_ingresos_mes() -> float:
    """Suma de ingresos reales del mes actual."""
    pages = safe_query(NOTION_INGRESOS_DB_ID, filter=_month_filter("Fecha"), sorts=_SORT_FECHA_ASC)
    total = 0.0
    for page in pages:
        monto = page["properties"].get("Monto", {}).get("number") or 0
        total += monto
    return total


def get_gastos_mes() -> float:
    """Suma de gastos del mes actual."""
    pages = safe_query(NOTION_GASTOS_DB_ID, filter=_month_filter("Fecha"), sorts=_SORT_FECHA_ASC)
    total = 0.0
    for page in pages:
        cantidad = page["properties"].get("Cantidad ", {}).get("number") or 0
        total += cantidad
    return total


def get_meta_ingresos_mes() -> float:
    """Suma de 'Monto Proyectado' de BASE 4."""
    pages = safe_query(NOTION_PROYECCIONES_INGRESOS_DB_ID)
    total = 0.0
    for page in pages:
        monto = page["properties"].get("Monto Proyectado.", {}).get("number") or 0
        total += monto
    return total


def get_pendientes() -> list[dict]:
    """
    Gastos de proyecciones con estado 'En proceso' o 'Pendiente'.
    Devuelve lista de dicts con nombre, proyectado, real, etiqueta.
    """
    pages = safe_query(
        NOTION_PROYECCIONES_GASTOS_DB_ID,
        filter={
            "or": [
                {"property": "Etiquetas", "status": {"equals": "En proceso"}},
                {"property": "Etiquetas", "status": {"equals": "Sin empezar"}},
            ]
        },
    )

    pendientes = []
    for page in pages:
        props = page["properties"]

        # título (Egreso determinado)
        title_parts = props.get("Egreso determinado ", {}).get("title", [])
        nombre = title_parts[0]["plain_text"] if title_parts else "Sin nombre"

        proyectado = props.get("$ Proyección", {}).get("number") or 0
        real = props.get("$ Real ", {}).get("number") or 0
        etiqueta_data = props.get("Etiquetas", {}).get("status") or {}
        etiqueta = etiqueta_data.get("name", "—")

        pendientes.append({
            "nombre": nombre,
            "proyectado": proyectado,
            "real": real,
            "etiqueta": etiqueta,
        })

    return pendientes


def get_ahorros() -> list[dict]:
    """Estado de metas de ahorro de BASE 5."""
    pages = safe_query(NOTION_AHORROS_DB_ID)
    ahorros = []
    for page in pages:
        props = page["properties"]

        title_parts = props.get("Nombre", {}).get("title", [])
        nombre = title_parts[0]["plain_text"] if title_parts else "Sin nombre"

        proyectado = props.get("CANTIDAD PROYECTADA", {}).get("number") or 0
        ahorrado = props.get("AHORRADO ", {}).get("number") or 0
        seleccion_data = props.get("Selección", {}).get("select") or {}
        estado = seleccion_data.get("name", "—")

        porcentaje = round((ahorrado / proyectado * 100), 1) if proyectado > 0 else 0

        ahorros.append({
            "nombre": nombre,
            "proyectado": proyectado,
            "ahorrado": ahorrado,
            "estado": estado,
            "porcentaje": porcentaje,
        })

    return ahorros


# Mapa de categoría Notion → nombre exacto de fila en proyecciones de gastos.
# Nombres con \xa0 (non-breaking space) y espacios finales exactos de Notion.
_GASTO_PROYECCION_MAP: dict = {
    # Transporte
    "Gasolina para la Moto":          "Transporte en moto ",
    "Mantenimiento de Moto":          "Transporte en moto ",
    "Taxis personales":               "Taxis personales\xa0",
    "Transporte Público":             "Tranporte Público ",       # typo en Notion
    # Alimentación
    "Restaurantes":                   "Restaurants\xa0",
    "Comida en Delivery":             "Restaurants\xa0",
    "Compras de Alimentación":        "Alimentación\xa0de Hogar ",
    # Hogar
    "Alquiler mensual":               "Alquiler o Hipoteca ",
    "Factura agua Mensual":           "Factura de agua",
    "Factura Luz mensual":            "Electricidad y gas\xa0",
    "Factura internet mensual":       "Factura Internet\xa0y TV ",
    "Factura plan Mensual":           "Recarga o plan ",
    "Mantenimiento de Hogar":         "Mantenimiento de Hogar: ",
    # Calidad de vida — nombres corregidos con repr() exacto de Notion
    "GYM mensual":                    "Gimnasio\xa0o GYM ",
    "Higiene Personal":               "Higiene\xa0Personal. ",
    # Ocio / entretenimiento
    "Salidas y Ocio":                 "Entretenimiento\xa0",
    # Trabajo
    "Viático":                        "Viaticos y Reuniones",
    # Salud
    "Gastos médicos":                 "Salud + suplementos y vitaminas",
    # Hogar — limpieza
    "Pago a Limpieza":                "Pago a Limpieza Sr. Isabel. ",
    # Sin fila directa — manejados contextualmente o en update_ahorro
    "Ahorros":                        None,
    "Inversiones":                    None,   # ver lógica contextual en update_proyeccion_gasto
    "Suscripciones ( Netflix etc.)":  None,
    "Compras ocasionales ( ropa )":   None,
    "Regalos y propinas":             None,
    # Sección OTROS — búsqueda por nombre (contains fallback si hay variaciones Unicode)
    "Vacaciones":                     "VIAJE A LA PLAYA CON AMIGOS",
}

# Mapeo de keywords en descripción → fila exacta en PROYECCIONES para categoria "Ahorros"
# Nombres con chars exactos del repr() leído en vivo.
_AHORRO_PROYECCION_MAP: list = [
    (["proteína", "proteina", "entrenamiento"],  "AHOOROS PARA PROTEÍNAS Y ENTRENAMIENTO: "),
    (["playa", "amigos"],                         "VIAJE A LA PLAYA CON AMIGOS "),
    (["casa", "entrada"],                          "AHORRO PARA ENTRADA DE CASA: "),
    (["deseos", "compras deseos"],                "COMPRAS O DESEOS "),
]

# Palabras clave en descripción → fila de deuda específica
_DEUDA_MAP: dict = {
    "pacifico":  "Tarjeta de crédito Pacifico (Laptop)",
    "pacífico":  "Tarjeta de crédito Pacifico (Laptop)",
    "pichincha": "Tarjeta de crédito Pichincha.",
    "coral":     "Pago al Coral",
}

# Palabras clave en descripción → nombre normalizado de fila en tabla de ahorros
_AHORRO_KEYWORD_MAP: list = [
    (["proteína", "proteina", "entrenamiento"],  "AHOOROS PARA PROTEÍNAS Y ENTRENAMIENTO: "),
    (["colchón", "colchon", "financiero"],        "AHORROS:\t\t\nCOLCHÓN FINANCIERO"),
    (["playa", "amigos"],                          "VIAJE A LA PLAYA CON AMIGOS"),
    (["casa", "entrada"],                           "AHORRO PARA ENTRADA DE CASA: "),
    (["deseos", "compras"],                         "GENEROSIDAD:\t\t\nCOMPRAS O DESEOS "),
]


def update_proyeccion_ingreso(categoria: str, monto: float) -> None:
    """
    Suma monto a 'Ganancias Reales ' en la fila de proyecciones de ingresos
    cuyo select 'Descripción de Ingreso' coincida con la categoría.
    Fallback: si el select exacto no matchea (ej. IA omitió el punto final),
    busca la fila cuyo select contenga las primeras palabras de la categoría.
    """
    # Notion lanza 400 si el valor no existe como opción → capturar y hacer scan completo
    try:
        pages = safe_query(
            NOTION_PROYECCIONES_INGRESOS_DB_ID,
            filter={"property": "Descripción de Ingreso", "select": {"equals": categoria}},
        )
    except RuntimeError:
        pages = []

    if not pages:
        cat_norm = categoria.rstrip(". ").lower()
        for p in safe_query(NOTION_PROYECCIONES_INGRESOS_DB_ID):
            sel = (p["properties"].get("Descripción de Ingreso", {}).get("select") or {}).get("name", "")
            if sel.rstrip(". ").lower() == cat_norm:
                pages = [p]
                break

    if not pages:
        return

    page = pages[0]
    actual = page["properties"].get("Ganancias Reales ", {}).get("number") or 0
    update_page(page["id"], {"Ganancias Reales ": {"number": round(actual + monto, 2)}})


def _buscar_fila_proyeccion(keyword: str) -> list[dict]:
    """Búsqueda por título que CONTIENE keyword (fallback a equals)."""
    return safe_query(
        NOTION_PROYECCIONES_GASTOS_DB_ID,
        filter={"property": "Egreso determinado ", "title": {"contains": keyword}},
    )


def _semaforo(nuevo_real: float, proyectado: float) -> str:
    if nuevo_real <= 0:
        return "Sin empezar"
    if proyectado > 0 and nuevo_real < proyectado:
        return "En proceso"
    return "Pagado"


def _query_fila(egreso_nombre: str) -> list[dict]:
    """Busca fila por título exacto; si no encuentra, intenta contains con palabras largas."""
    pages = safe_query(
        NOTION_PROYECCIONES_GASTOS_DB_ID,
        filter={"property": "Egreso determinado ", "title": {"equals": egreso_nombre}},
    )
    if pages:
        return pages
    for palabra in (w for w in egreso_nombre.split() if len(w) >= 4):
        pages = _buscar_fila_proyeccion(palabra)
        if pages:
            return pages
    return []


def update_proyeccion_gasto(categoria: str, monto: float, descripcion: str = "") -> None:
    """
    Suma monto a '$ Real ' en la fila de proyecciones correspondiente.
    - Usa _GASTO_PROYECCION_MAP para el mapeo directo.
    - 'créditos y responsabilidades': detecta tarjeta por keyword en descripción.
    - 'Inversiones': detecta si es curso/libro o seminario/taller.
    - None-mapeados: intenta búsqueda por contiene usando palabras de la categoría.
    - Actualiza Etiquetas semáforo: Sin empezar / En proceso / Pagado.
    - Escribe 'Exceso $X' si real > proyectado, 'Ahorro $X' si está por debajo.
    """
    desc_lower = descripcion.lower()

    if categoria == "créditos y responsabilidades":
        egreso_nombre = next(
            (row for kw, row in _DEUDA_MAP.items() if kw in desc_lower), None
        )
        if not egreso_nombre:
            return
        pages = _query_fila(egreso_nombre)
    elif categoria == "Inversiones":
        if any(kw in desc_lower for kw in ("curso", "libro", "libros", "lectura")):
            egreso_nombre = "Cursos o Libros. "
        elif any(kw in desc_lower for kw in ("seminario", "taller", "capacitación", "capacitacion")):
            egreso_nombre = "Seminarios o talleres. "
        else:
            return
        pages = _query_fila(egreso_nombre)
    else:
        if categoria in _GASTO_PROYECCION_MAP:
            egreso_nombre = _GASTO_PROYECCION_MAP[categoria]
            if egreso_nombre is None:
                # Categoría explícitamente sin fila directa.
                # "Ahorros": rutear por keywords de descripción usando _AHORRO_PROYECCION_MAP
                if categoria == "Ahorros":
                    fila_ahorro = next(
                        (row for kws, row in _AHORRO_PROYECCION_MAP
                         if any(kw in desc_lower for kw in kws)),
                        None,
                    )
                    if not fila_ahorro:
                        return
                    pages = _query_fila(fila_ahorro)
                else:
                    return
            else:
                pages = _query_fila(egreso_nombre)
        else:
            # Categoría fuera del mapa → búsqueda fuzzy por palabras del nombre
            pages = _query_fila(categoria)
            if not pages:
                for palabra in (w for w in categoria.split() if len(w) >= 4):
                    pages = _buscar_fila_proyeccion(palabra)
                    if pages:
                        break

    if not pages:
        return

    page = pages[0]
    props = page["properties"]
    real_actual = props.get("$ Real ", {}).get("number") or 0
    proyectado = props.get("$ Proyección", {}).get("number") or 0
    nuevo_real = round(real_actual + monto, 2)

    updates: dict = {
        "$ Real ": {"number": nuevo_real},
        "Etiquetas": {"status": {"name": _semaforo(nuevo_real, proyectado)}},
    }

    if categoria == "Ahorros" and descripcion:
        updates["Descripción opcional "] = {
            "rich_text": [{"text": {"content": descripcion[:2000]}}]
        }
    elif proyectado > 0:
        if nuevo_real > proyectado:
            diferencia = round(nuevo_real - proyectado, 2)
            updates["Descripción opcional "] = {
                "rich_text": [{"text": {"content": f"Exceso ${diferencia:.2f}"}}]
            }
        else:
            ahorro = round(proyectado - nuevo_real, 2)
            updates["Descripción opcional "] = {
                "rich_text": [{"text": {"content": f"Ahorro ${ahorro:.2f}"}}]
            }

    update_page(page["id"], updates)


def update_ahorro(monto: float, descripcion: str = "", fallback_a_incompleto: bool = True) -> None:
    """
    Suma monto a 'AHORRADO ' de la meta de ahorro correcta según keywords en descripción.
    - Si fallback_a_incompleto=True (default): usa primera fila INCOMPLETO si no hay match.
    - Si fallback_a_incompleto=False: solo actualiza si hay keyword match exacto.
    """
    pages = safe_query(NOTION_AHORROS_DB_ID)
    if not pages:
        return

    # Construir lookup nombre_normalizado → página
    def _normalizar(s: str) -> str:
        return s.replace("\t", "").replace("\n", "").strip().upper()

    page_by_nombre_norm = {}
    for page in pages:
        title_parts = page["properties"].get("Nombre", {}).get("title", [])
        nombre = title_parts[0]["plain_text"] if title_parts else ""
        if nombre:
            page_by_nombre_norm[_normalizar(nombre)] = page

    target = None
    if descripcion:
        desc_lower = descripcion.lower()
        for keywords, nombre_objetivo in _AHORRO_KEYWORD_MAP:
            if any(kw in desc_lower for kw in keywords):
                objetivo_norm = _normalizar(nombre_objetivo)
                target = page_by_nombre_norm.get(objetivo_norm)
                break

    if not target and fallback_a_incompleto:
        for page in pages:
            estado = (page["properties"].get("Selección", {}).get("select") or {}).get("name", "")
            if estado == "INCOMPLETO":
                target = page
                break

    if not target:
        return

    props = target["properties"]
    ahorrado_actual = props.get("AHORRADO ", {}).get("number") or 0
    proyectado = props.get("CANTIDAD PROYECTADA", {}).get("number") or 0
    nuevo_ahorrado = round(ahorrado_actual + monto, 2)

    updates: dict = {"AHORRADO ": {"number": nuevo_ahorrado}}
    if proyectado > 0:
        if nuevo_ahorrado >= proyectado:
            updates["Selección"] = {"select": {"name": "LISTO"}}
        elif nuevo_ahorrado > 0:
            updates["Selección"] = {"select": {"name": "INCOMPLETO"}}
        else:
            updates["Selección"] = {"select": {"name": "NO AHORROS"}}

    update_page(target["id"], updates)


# Mapa keyword → concepto exacto en NOTION_PRIORIDADES_DB_ID
# Los conceptos son los plain_text reales leídos con repr() en vivo.
_PRIORIDAD_KEYWORD_MAP: list = [
    (["pacifico", "pacífico", "laptop"],                    "Tarjeta Pacífico (Laptop)"),
    (["pichincha"],                                         None),  # no existe fila en prioridades
    (["coral"],                                             "Pago Coral"),
    (["alquiler", "arriendo"],                              None),  # no existe fila en prioridades
    (["plan", "teléfono", "telefono", "recarga", "claro", "cnt"],  "Recarga/plan"),
    (["luz", "electricidad", "cnel"],                       None),  # no existe fila en prioridades
    (["agua"],                                              None),  # no existe fila en prioridades
    (["alimentaci", "hogar", "limpieza", "isabel"],         "Alimentación hogar"),
    (["higiene"],                                           "Higiene"),
    (["salud", "suplemento", "vitamina", "médico", "medico", "farmacia"], "Salud + suplementos"),
    (["viático", "viatico", "reunión", "reunion"],          "Viáticos/reuniones"),
    (["transporte", "moto", "taxi", "bus", "gasolina"],     "Transporte total restante"),
    (["proteína", "proteina", "entrenamiento"],             "Proteínas/entrenamiento"),
    (["playa", "viaje playa"],                              "Viaje playa"),
    (["deseos", "compras deseos"],                          "Compras/deseos"),
    (["curso", "libro"],                                    "Cursos/libros"),
    (["seminario", "taller"],                               "Seminarios/talleres"),
    (["casa entrada", "ahorro casa"],                       "Ahorro casa"),
]


def _parsear_falta(texto: str) -> float | None:
    """Extrae el número de cadenas como '$205', '~$110', '$400 aprox'."""
    limpio = texto.replace("$", "").replace("~", "").replace("aprox", "").strip()
    try:
        return float(limpio)
    except ValueError:
        return None


def _formatear_falta(valor: float) -> str:
    if valor <= 0:
        return "$0"
    if valor == int(valor):
        return f"${int(valor)}"
    return f"${valor:.2f}"


def update_prioridad(descripcion: str, monto_pagado: float) -> None:
    """
    Busca en NOTION_PRIORIDADES_DB_ID la fila cuyo Concepto coincide con
    keywords de la descripción, resta monto_pagado del campo 'Falta' y
    actualiza la fila. Si Falta llega a 0 escribe '$0'.
    """
    if not descripcion or monto_pagado <= 0:
        return

    desc_lower = descripcion.lower()

    # Encontrar el concepto objetivo
    concepto_objetivo = None
    for keywords, concepto in _PRIORIDAD_KEYWORD_MAP:
        if concepto and any(kw in desc_lower for kw in keywords):
            concepto_objetivo = concepto
            break

    if not concepto_objetivo:
        return

    # Buscar la página por Concepto
    pages = safe_query(NOTION_PRIORIDADES_DB_ID)
    target = None
    for page in pages:
        concepto_parts = page["properties"].get("Concepto", {}).get("rich_text", [])
        concepto_texto = concepto_parts[0]["plain_text"] if concepto_parts else ""
        if concepto_texto.strip().lower() == concepto_objetivo.lower():
            target = page
            break

    if not target:
        return

    props = target["properties"]
    falta_actual = props.get("Falta", {}).get("number")

    if falta_actual is None:
        from notion.priorities import _MONTO_INICIAL
        inicial = _MONTO_INICIAL.get(concepto_objetivo)
        if inicial is None:
            return
        falta_actual = float(inicial)

    nuevo_falta = max(0.0, round(falta_actual - monto_pagado, 2))
    update_page(target["id"], {"Falta": {"number": nuevo_falta}})


def get_sugerencias_ahorro() -> dict:
    """Analiza metas incompletas y devuelve sugerencias de ahorro diario para el mes."""
    import calendar
    hoy = date.today()
    dias_en_mes = calendar.monthrange(hoy.year, hoy.month)[1]
    dias_restantes = max(dias_en_mes - hoy.day + 1, 1)

    ahorros = get_ahorros()
    pendientes = [
        a for a in ahorros if a["estado"] in ("INCOMPLETO", "NO AHORROS")
    ]

    for a in pendientes:
        a["falta"] = round(max(0.0, a["proyectado"] - a["ahorrado"]), 2)
        a["diario"] = round(a["falta"] / dias_restantes, 2)

    # Ordenar: primero los más cercanos a completarse (menor falta)
    pendientes.sort(key=lambda a: a["falta"])

    total_diario = round(sum(a["diario"] for a in pendientes), 2)

    return {
        "pendientes": pendientes,
        "total_diario": total_diario,
        "dias_restantes": dias_restantes,
    }


def get_balance() -> dict:
    """Resumen completo del mes para /balance."""
    ingresos_real = get_ingresos_mes()
    ingresos_meta = get_meta_ingresos_mes()
    gastos = get_gastos_mes()
    disponible = ingresos_real - gastos
    ahorros = get_ahorros()

    return {
        "ingresos_real": ingresos_real,
        "ingresos_meta": ingresos_meta,
        "gastos": gastos,
        "disponible": disponible,
        "ahorros": ahorros,
        "mes": datetime.now().strftime("%B %Y").capitalize(),
    }
