from __future__ import annotations
import logging
import os
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from ai.extractor import extract_from_text, extract_from_image, detectar_intencion
from notion.expenses import create_expense_entry
from notion.income import create_income_entry
from notion.queries import get_analisis_completo, get_transacciones_categoria
from bot.responses import (
    gasto_confirmado,
    ingreso_confirmado,
    resumen_lote,
    confirmar_individual,
    prioridades_mensaje,
    pagos_proximos_mensaje,
    sugerencias_ahorro_mensaje,
    gastos_analisis_mensaje,
    ahorros_analisis_mensaje,
    ingresos_analisis_mensaje,
    resumen_financiero_mensaje,
    categoria_analisis_mensaje,
    error_ia,
    error_notion,
)

_CHAT_ID_FILE = os.path.join(os.path.dirname(__file__), "..", ".chat_id")
_WS_RE = re.compile(r"[\s\xa0]+")

_PRIORIDADES_KEYWORDS = [
    "prioridad", "prioridades", "más urgente", "mas urgente",
    "qué debo pagar", "que debo pagar", "qué pago primero", "que pago primero",
    "más importante", "mas importante", "cosas importantes", "lo más urgente",
    "lo mas urgente",
]

_AHORRO_SUGERENCIAS_KEYWORDS = [
    "en qué debería ahorrar", "sugerencias de ahorro", "recomiendas ahorrar",
    "cómo mejorar mis ahorros", "como mejorar mis ahorros", "qué me recomiendas",
    "que me recomiendas", "mejorar ahorros", "consejos ahorro",
    "cómo ahorrar", "como ahorrar", "ayuda con ahorros", "dónde ahorrar",
    "donde ahorrar", "qué ahorrar", "que ahorrar",
]

_PAGOS_KEYWORDS = [
    "próximos pagos", "proximos pagos", "qué pagos", "que pagos",
    "pagos vienen", "toca pagar", "siguiente pago", "próximo pago",
    "proximo pago", "cuándo pago", "cuando pago", "cuándo es el",
    "cuando es el", "pagos esta semana", "pagos de esta semana",
    "qué toca", "que toca", "vencimientos", "pagos pendientes",
    "próximos 3", "proximos 3", "próximos 7", "proximos 7",
    "próximas cuotas", "proximas cuotas",
]

_GASTOS_ANALISIS_KEYWORDS = [
    "cómo van mis gastos", "como van mis gastos", "análisis de gastos",
    "analisis de gastos", "cuánto he gastado", "cuanto he gastado",
    "gastos del mes", "resumen de gastos", "en qué gasté", "en que gaste",
    "qué categorías", "que categorias", "gastos excedidos", "excedí", "excedi",
    "gasté mucho", "gaste mucho",
]

_INGRESOS_ANALISIS_KEYWORDS = [
    "cómo van mis ingresos", "como van mis ingresos", "análisis de ingresos",
    "analisis de ingresos", "cuánto he ganado", "cuanto he ganado",
    "ingresos del mes", "meta de ingresos", "mis ingresos", "cuánto gané",
    "cuanto gane", "ganancias del mes", "cómo voy con ingresos",
    "como voy con ingresos",
]

_AHORROS_ANALISIS_KEYWORDS = [
    "cómo van mis ahorros", "como van mis ahorros", "estado de ahorros",
    "mis ahorros", "cuánto he ahorrado", "cuanto he ahorrado",
    "metas de ahorro", "avance de ahorros", "cómo voy ahorrando",
    "como voy ahorrando",
]

_RESUMEN_KEYWORDS = [
    "resumen financiero", "cómo estoy financieramente", "como estoy financieramente",
    "resumen del mes", "resumen general", "estado financiero", "cómo voy",
    "como voy", "dame un resumen", "panorama financiero", "situación financiera",
    "situacion financiera",
]

logger = logging.getLogger(__name__)


def _load_authorized_id() -> int | None:
    try:
        with open(_CHAT_ID_FILE) as f:
            return int(f.read().strip())
    except Exception:
        return None


# Cache del chat_id autorizado — se lee del disco una sola vez al arrancar.
# Si .chat_id aún no existe (primer arranque), se recarga en cada mensaje
# hasta que /start lo cree, momento en que se fija para siempre.
_AUTHORIZED_CHAT_ID: int | None = _load_authorized_id()


def _is_authorized(update: Update) -> bool:
    global _AUTHORIZED_CHAT_ID
    chat_id = update.effective_chat.id if update.effective_chat else None
    if chat_id is None:
        return False
    if _AUTHORIZED_CHAT_ID is None:
        # Intentar cargar por si /start ya escribió el archivo
        _AUTHORIZED_CHAT_ID = _load_authorized_id()
        return True  # Permite hasta que se establezca
    return chat_id == _AUTHORIZED_CHAT_ID

def _normalizar_nombre(s: str) -> str:
    return _WS_RE.sub(" ", s).strip().lower()


_NUMERO_RE = re.compile(r"\d+")


_REGISTRO_VERBOS = [
    "gasté", "gaste", "pagué", "pague", "compré", "compre",
    "cobré", "cobre", "invertí", "inverti", "me costó", "me costo",
    "me cobró", "me cobro", "recibí", "recibi",
]


def _es_registro_ahorro(texto_lower: str) -> bool:
    """True cuando el mensaje describe ahorros con montos, no una consulta."""
    tiene_numero = bool(_NUMERO_RE.search(texto_lower))
    palabras_registro = ["ahorré", "ahorrando", "quiero ahorrar", "voy a ahorrar"]
    empieza_ahorro = texto_lower.strip().startswith("ahorro")
    return (empieza_ahorro and tiene_numero) or any(kw in texto_lower for kw in palabras_registro)


def _es_registro_gasto(texto_lower: str) -> bool:
    """True cuando el texto parece registro de transacción (verbo acción + monto), no consulta."""
    return bool(_NUMERO_RE.search(texto_lower)) and any(v in texto_lower for v in _REGISTRO_VERBOS)


# Palabras que indican "¿cuánto falta/me queda?" en vez de "¿cuánto llevo?"
_FALTA_KEYWORDS = [
    "cuánto falta", "cuanto falta", "me falta", "cuánto me falta", "cuanto me falta",
    "cuánto debo", "cuanto debo", "me queda", "cuánto queda", "cuanto queda",
    "queda pagar", "falta pagar",
]

# Mapa: palabras clave → (nombre_fila_proyeccion, categoria_notion_gastos)
# Más específico primero para evitar falsos positivos con substrings cortas.
_CATEGORIA_KEYWORDS: list[tuple[list[str], str, str]] = [
    (["señora isabel", "señora de limpieza", "limpieza isabel", "pago limpieza",
      "isabel", "limpieza", "empleada", "aseo"],
     "Pago a Limpieza Sr. Isabel.", "Pago a Limpieza Sr. Isabel."),
    (["restaurante", "restaurantes", "comida fuera", "comer afuera", "almuerzo fuera", "almuerzo"],
     "Restaurants\xa0", "Restaurantes"),
    (["uber eats", "delivery", "rappi", "pedido"],
     "Comida en Delivery", "Comida en Delivery"),
    (["entrada casa", "casa propia", "nueva casa", "ahorro casa"],
     "AHORRO PARA ENTRADA DE CASA:", "Ahorros"),
    (["alquiler", "arriendo", "renta mensual", "habitación", "habitacion", "renta", "casa"],
     "Alquiler o Hipoteca", "Alquiler mensual"),
    (["agua potable", "factura agua", "agua"],
     "Factura de agua", "Factura agua Mensual"),
    (["electricidad", "eléctrica", "electrica", "energía electrica", "factura luz", "luz"],
     "Electricidad y gas", "Factura Luz mensual"),
    (["factura internet", "wifi", "fibra", "internet"],
     "Factura Internet y TV", "Factura internet mensual"),
    (["plan celular", "celular", "móvil", "movil", "recarga", "teléfono", "telefono"],
     "Recarga o plan", "Factura plan Mensual"),
    (["supermercado coral", "mercado", "supermercado", "alimentación", "alimentacion",
      "comida casa", "comida del mes", "alimentación mensual", "feria"],
     "Alimentación\xa0Mensual", "Compras de Alimentación"),
    (["taxi", "taxis", "uber", "cabify"],
     "Taxis personales\xa0", "Taxis personales"),
    (["transporte público", "transporte publico", "bus", "metro", "buseta"],
     "Tranporte Público ", "Transporte Público"),
    (["gasolina moto", "transporte moto", "gasolina", "combustible", "tanquear", "moto"],
     "Transporte en moto ", "Gasolina para la Moto"),
    (["tarjeta pacífico", "tarjeta pacifico", "banco pacífico", "banco pacifico",
      "crédito pacífico", "credito pacifico", "pacífico", "pacifico", "laptop", "cuota laptop"],
     "Tarjeta de crédito Pacifico (Laptop)", "créditos y responsabilidades"),
    (["tarjeta pichincha", "banco pichincha", "pichincha"],
     "Tarjeta de crédito Pichincha.", "créditos y responsabilidades"),
    (["pago coral", "coral"],
     "Pago al Coral", "créditos y responsabilidades"),
    (["entretenimiento", "ocio", "diversión", "diversion", "salidas y ocio", "salidas"],
     "Gastos de Entretenimiento\xa0", "Salidas y Ocio"),
    (["netflix", "suscripción", "suscripcion", "spotify", "suscripciones"],
     "Suscripciones", "Suscripciones ( Netflix etc.)"),
    (["gastos médicos", "médico", "medico", "salud", "farmacia", "medicina"],
     "Salud + suplementos y vitaminas", "Gastos médicos"),
    (["higiene personal", "aseo personal", "cuidado personal", "shampoo", "jabón", "jabon", "higiene"],
     "Higiene Personal.", "Higiene Personal"),
    (["gym", "gimnasio"],
     "Gimnasio\xa0o GYM ", "GYM mensual"),
    (["ropa nueva", "ropa", "zapatos", "calzado", "tienda"],
     "Compras ocasionales", "Compras ocasionales ( ropa )"),
    (["mantenimiento", "reparación", "reparacion", "herramientas"],
     "Mantenimiento de Hogar:", "Mantenimiento de Hogar:"),
    (["regalo", "regalos", "propina", "propinas", "donación", "donacion"],
     "Regalos y propinas", "Regalos y propinas"),
    (["inversión", "inversion", "inversiones", "capacitación", "capacitacion",
      "seminario", "taller", "curso", "libro"],
     "INVERSIONES - CRECIMIENTO PERSONAL", "Inversiones"),
    (["vacaciones", "viaje", "paseo", "turismo"],
     "VIAJE A LA PLAYA CON AMIGOS ", "Vacaciones"),
    (["colchón financiero", "colchon financiero", "ahorro colchón", "ahorro colchon",
      "colchón", "colchon", "fondo emergencia"],
     "COLCHÓN FINANCIERO", "Ahorros"),
    (["viaje playa", "amigos playa", "playa"],
     "VIAJE A LA PLAYA CON AMIGOS", "Ahorros"),
    (["proteína", "proteina", "proteínas", "entrenamiento"],
     "AHOOROS PARA PROTEÍNAS Y ENTRENAMIENTO:", "Ahorros"),
]


# Reverse-lookup: cat_notion → nombre_proy  (para el fallback de intención IA)
_CAT_NOTION_TO_PROY: dict[str, str] = {
    cat_notion: nombre_proy
    for _, nombre_proy, cat_notion in _CATEGORIA_KEYWORDS
}


def _detectar_categoria(texto_lower: str) -> tuple[str, str] | None:
    """Primera entrada cuya keyword sea substring del texto. Más específico → primero en la lista."""
    for keywords, nombre_proy, cat_notion in _CATEGORIA_KEYWORDS:
        if any(kw in texto_lower for kw in keywords):
            return (nombre_proy, cat_notion)
    return None


_COMPLETAR_PAGO_KEYWORDS = [
    "ya pagué", "ya pague", "ya está pagado", "ya esta pagado",
    "ya lo pagué", "ya lo pague", "ya completé", "ya complete",
    "este pago ya se completó", "este pago ya se completo",
    "ya completé este pago", "ya complete este pago",
    "sácalo de prioridades", "sacalo de prioridades",
    "quitar de prioridades", "ya no hay que pagar",
    "marcar como pagado", "márcar como pagado",
]

# keywords en texto → nombre de concepto en _CONCEPTO_CONFIG
_COMPLETAR_CONCEPTO_MAP: list[tuple[list[str], str]] = [
    (["coral"],                                           "Pago Coral"),
    (["pichincha"],                                       "Tarjeta Pichincha"),
    (["pacífico", "pacifico", "laptop"],                  "Tarjeta Pacífico (Laptop)"),
    (["alquiler", "arriendo"],                            "Alquiler"),
    (["alimentación", "alimentacion", "mercado", "supermercado"], "Alimentación hogar"),
    (["celular", "recarga", "plan celular"],              "Recarga/plan"),
    (["higiene"],                                         "Higiene"),
    (["salud", "suplementos", "vitaminas"],               "Salud + suplementos"),
    (["viático", "viatico", "reunión", "reunion"],        "Viáticos/reuniones"),
    (["proteína", "proteina", "entrenamiento"],           "Proteínas/entrenamiento"),
    (["playa"],                                           "Viaje playa"),
    (["deseos", "compras deseos"],                        "Compras/deseos"),
    (["cursos", "libros"],                                "Cursos/libros"),
    (["seminarios", "talleres"],                          "Seminarios/talleres"),
    (["ahorro casa", "entrada casa"],                     "Ahorro casa"),
]


def _detectar_concepto_completar(texto_lower: str) -> str | None:
    """Retorna el nombre del concepto si hay keyword match, None si no."""
    for keywords, concepto in _COMPLETAR_CONCEPTO_MAP:
        if any(kw in texto_lower for kw in keywords):
            return concepto
    return None


async def _marcar_completado_y_responder(update: Update, concepto: str) -> None:
    """Llama a marcar_prioridad_completada y envía la respuesta apropiada."""
    try:
        from notion.priorities import marcar_prioridad_completada
        resultado = marcar_prioridad_completada(concepto)
    except Exception as e:
        logger.error(f"Error marcando prioridad completada: {e}")
        await update.message.reply_text(error_notion())
        return
    if resultado:
        await update.message.reply_text(
            f"✅ *{resultado}* marcado como completado.\nYa no aparecerá en tus prioridades.",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            "⚠️ No encontré ese pago en tus prioridades. "
            "Prueba con: coral, pichincha, alquiler, playa..."
        )


# Claves de contexto para el flujo de confirmación
CTX_PENDIENTES = "transacciones_pendientes"
CTX_INDIVIDUAL = "transaccion_individual"
CTX_COMPLETAR_PAGO = "completar_pago"


def _teclado_confirmacion_lote() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Sí, registrar todas", callback_data="lote_confirmar"),
            InlineKeyboardButton("👀 Revisar", callback_data="lote_revisar"),
        ]
    ])


def _teclado_confirmacion_individual() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Correcto", callback_data="ind_confirmar"),
            InlineKeyboardButton("❌ Cancelar", callback_data="ind_cancelar"),
        ]
    ])


async def _registrar_transaccion(transaccion: dict) -> None:
    """Registra una sola transacción en la base de Notion correcta."""
    descripcion_ai = transaccion.get("descripcion") or ""
    notas = transaccion.get("notas") or ""
    descripcion = " — ".join(filter(None, [descripcion_ai, notas]))

    if transaccion["tipo"] == "gasto":
        create_expense_entry(
            categoria=transaccion["categoria_notion"],
            cantidad=transaccion["monto"],
            fecha=transaccion["fecha"],
            descripcion=descripcion,
        )
    else:
        create_income_entry(
            categoria=transaccion["categoria_notion"],
            monto=transaccion["monto"],
            fecha=transaccion["fecha"],
            descripcion=descripcion,
        )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        await update.message.reply_text("Este bot es privado. No tienes acceso.")
        return

    texto = update.message.text.strip()
    texto_lower = texto.lower()

    # ── Estado: esperando que el usuario diga qué pago completó ──
    if context.user_data.get(CTX_COMPLETAR_PAGO):
        context.user_data.pop(CTX_COMPLETAR_PAGO)
        concepto = _detectar_concepto_completar(texto_lower)
        if concepto:
            await _marcar_completado_y_responder(update, concepto)
        else:
            await update.message.reply_text(
                "🤔 No reconocí ese pago. Prueba con: coral, pichincha, alquiler, playa, proteínas..."
            )
        return

    # ── Marcar pago como completado ──
    if any(kw in texto_lower for kw in _COMPLETAR_PAGO_KEYWORDS):
        concepto = _detectar_concepto_completar(texto_lower)
        if concepto:
            await _marcar_completado_y_responder(update, concepto)
        else:
            context.user_data[CTX_COMPLETAR_PAGO] = True
            await update.message.reply_text(
                "¿Cuál pago completaste? Dime el nombre:\n"
                "(coral, pichincha, alquiler, playa, proteínas...)"
            )
        return

    # Natural language shortcut for priorities
    if any(kw in texto_lower for kw in _PRIORIDADES_KEYWORDS):
        from notion.priorities import get_top_prioridades, get_all_prioridades
        todas = "todas" in texto_lower
        try:
            prioridades = get_all_prioridades() if todas else get_top_prioridades(3)
            await update.message.reply_text(prioridades_mensaje(prioridades, todas=todas), parse_mode="Markdown")
        except RuntimeError:
            await update.message.reply_text(error_notion())
        return

    # Natural language shortcut for savings suggestions
    if any(kw in texto_lower for kw in _AHORRO_SUGERENCIAS_KEYWORDS):
        from notion.queries import get_sugerencias_ahorro
        try:
            data = get_sugerencias_ahorro()
            await update.message.reply_text(sugerencias_ahorro_mensaje(data))
        except RuntimeError:
            await update.message.reply_text(error_notion())
        return

    # Natural language shortcut for upcoming payments
    if any(kw in texto_lower for kw in _PAGOS_KEYWORDS):
        from bot.scheduler import check_pagos_proximos
        alertas = check_pagos_proximos(dias=7)
        await update.message.reply_text(pagos_proximos_mensaje(alertas))
        return

    # Analytics: categoría específica  ← va ANTES del análisis general para que
    # "cómo van mis gastos médicos" no sea capturado por "cómo van mis gastos"
    _es_registro = _es_registro_ahorro(texto_lower) or _es_registro_gasto(texto_lower)
    categoria_detectada = None if _es_registro else _detectar_categoria(texto_lower)
    if categoria_detectada:
        try:
            data = get_analisis_completo()
            nombre_proy, cat_notion = categoria_detectada
            filas = [f for f in data["gastos_filas"]
                     if _normalizar_nombre(f["nombre"]) == _normalizar_nombre(nombre_proy)]
            modo_falta = any(kw in texto_lower for kw in _FALTA_KEYWORDS)
            transacciones = [] if modo_falta else get_transacciones_categoria(cat_notion)
            await update.message.reply_text(
                categoria_analisis_mensaje(cat_notion, filas, transacciones, modo_falta=modo_falta),
                parse_mode="Markdown",
            )
        except RuntimeError:
            await update.message.reply_text(error_notion())
        return

    # Analytics: gastos / ingresos / ahorros / resumen  (general — sin categoría específica)
    _analisis_routing = [
        (_GASTOS_ANALISIS_KEYWORDS,   gastos_analisis_mensaje),
        (_INGRESOS_ANALISIS_KEYWORDS, ingresos_analisis_mensaje),
        (_AHORROS_ANALISIS_KEYWORDS,  ahorros_analisis_mensaje),
        (_RESUMEN_KEYWORDS,           resumen_financiero_mensaje),
    ]
    for kw_list, formatter in _analisis_routing:
        if any(kw in texto_lower for kw in kw_list):
            try:
                await update.message.reply_text(
                    formatter(get_analisis_completo()), parse_mode="Markdown"
                )
            except RuntimeError:
                await update.message.reply_text(error_notion())
            return

    # ── Fallback IA: detectar intención cuando ninguna keyword local matcheó ──
    # Solo si el texto NO parece un registro directo de transacción.
    if not _es_registro:
        try:
            intencion_data = detectar_intencion(texto)
        except Exception as e:
            logger.warning(f"detectar_intencion falló: {e}")
            intencion_data = {"intencion": "otro"}

        intencion  = intencion_data.get("intencion", "otro")
        filtros    = intencion_data.get("filtros") or []
        cat_ia     = intencion_data.get("categoria_especifica")
        presupuesto = intencion_data.get("presupuesto")

        try:
            if intencion == "consulta_ahorros":
                await update.message.reply_text(
                    ahorros_analisis_mensaje(get_analisis_completo()), parse_mode="Markdown"
                )
                return

            elif intencion == "consulta_gastos":
                await update.message.reply_text(
                    gastos_analisis_mensaje(get_analisis_completo()), parse_mode="Markdown"
                )
                return

            elif intencion == "consulta_ingresos":
                await update.message.reply_text(
                    ingresos_analisis_mensaje(get_analisis_completo()), parse_mode="Markdown"
                )
                return

            elif intencion == "consulta_resumen":
                await update.message.reply_text(
                    resumen_financiero_mensaje(get_analisis_completo()), parse_mode="Markdown"
                )
                return

            elif intencion == "consulta_prioridades":
                from notion.priorities import get_all_prioridades
                prioridades = get_all_prioridades()
                if filtros:
                    prioridades = [
                        p for p in prioridades
                        if not any(f.lower() in p.get("concepto", "").lower() for f in filtros)
                    ]
                if presupuesto is not None:
                    prioridades = [p for p in prioridades if p.get("falta", 0) <= presupuesto]
                await update.message.reply_text(
                    prioridades_mensaje(prioridades[:10], todas=bool(filtros or presupuesto)),
                    parse_mode="Markdown",
                )
                return

            elif intencion == "consulta_pagos_proximos":
                from bot.scheduler import check_pagos_proximos
                alertas = check_pagos_proximos(dias=15)
                await update.message.reply_text(pagos_proximos_mensaje(alertas))
                return

            elif intencion == "consulta_categoria" and cat_ia:
                nombre_proy = _CAT_NOTION_TO_PROY.get(cat_ia, cat_ia)
                data = get_analisis_completo()
                filas = [f for f in data["gastos_filas"]
                         if _normalizar_nombre(f["nombre"]) == _normalizar_nombre(nombre_proy)]
                modo_falta = any(kw in texto_lower for kw in _FALTA_KEYWORDS)
                transacciones = [] if modo_falta else get_transacciones_categoria(cat_ia)
                await update.message.reply_text(
                    categoria_analisis_mensaje(cat_ia, filas, transacciones, modo_falta=modo_falta),
                    parse_mode="Markdown",
                )
                return

            elif intencion == "marcar_pagado":
                concepto = _detectar_concepto_completar(texto_lower)
                if concepto:
                    await _marcar_completado_y_responder(update, concepto)
                else:
                    context.user_data[CTX_COMPLETAR_PAGO] = True
                    await update.message.reply_text(
                        "¿Cuál pago completaste? Dime el nombre:\n"
                        "(coral, pichincha, alquiler, playa...)"
                    )
                return

            # intencion == "registro_transaccion" o "otro" → cae al extractor
        except RuntimeError:
            await update.message.reply_text(error_notion())
            return

    await update.message.reply_text("🤖 Procesando...")

    try:
        resultado = extract_from_text(texto)
    except Exception as e:
        logger.error(f"Error en extractor: {e}")
        await update.message.reply_text(error_ia())
        return

    transacciones = resultado.get("transacciones", [])
    if not transacciones:
        await update.message.reply_text(
            "🤔 No entendí eso como un movimiento financiero.\n"
            "Prueba: `gasté 25 en taxi` o `cobré 400 de 1xbet`",
            parse_mode="Markdown",
        )
        return

    # Texto produce normalmente 1 transacción
    if len(transacciones) == 1:
        t = transacciones[0]
        if t.get("confianza") == "alta":
            try:
                await _registrar_transaccion(t)
                respuesta = gasto_confirmado(t) if t["tipo"] == "gasto" else ingreso_confirmado(t)
                await update.message.reply_text(respuesta)
            except RuntimeError as e:
                logger.error(f"Error Notion al registrar: {e}")
                await update.message.reply_text(error_notion())
        else:
            # confianza media/baja: pedir confirmación
            context.user_data[CTX_INDIVIDUAL] = t
            await update.message.reply_text(
                confirmar_individual(t),
                reply_markup=_teclado_confirmacion_individual(),
            )
    else:
        # Múltiples transacciones desde texto (raro pero posible)
        context.user_data[CTX_PENDIENTES] = transacciones
        await update.message.reply_text(
            resumen_lote(transacciones),
            reply_markup=_teclado_confirmacion_lote(),
        )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        await update.message.reply_text("Este bot es privado. No tienes acceso.")
        return

    await update.message.reply_text("📷 Analizando imagen de Monefy...")

    try:
        photo = update.message.photo[-1]  # mayor resolución
        file = await context.bot.get_file(photo.file_id)
        image_bytes = await file.download_as_bytearray()
        resultado = extract_from_image(bytes(image_bytes))
    except Exception as e:
        logger.error(f"Error procesando imagen: {e}")
        await update.message.reply_text(error_ia())
        return

    transacciones = resultado.get("transacciones", [])
    if not transacciones:
        await update.message.reply_text(
            "😕 No encontré transacciones en esta imagen.\n"
            "Asegúrate de que sea una captura de Monefy con transacciones visibles."
        )
        return

    if len(transacciones) == 1:
        t = transacciones[0]
        try:
            await _registrar_transaccion(t)
            respuesta = gasto_confirmado(t) if t["tipo"] == "gasto" else ingreso_confirmado(t)
            await update.message.reply_text(respuesta)
        except RuntimeError:
            await update.message.reply_text(error_notion())
    else:
        context.user_data[CTX_PENDIENTES] = transacciones
        await update.message.reply_text(
            resumen_lote(transacciones),
            reply_markup=_teclado_confirmacion_lote(),
        )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        return

    query = update.callback_query
    await query.answer()
    data = query.data

    # ── Flujo lote (imagen o múltiples del texto) ──
    if data == "lote_confirmar":
        transacciones = context.user_data.pop(CTX_PENDIENTES, [])
        if not transacciones:
            await query.edit_message_text("⚠️ No hay transacciones pendientes.")
            return

        errores = 0
        for t in transacciones:
            try:
                await _registrar_transaccion(t)
            except RuntimeError:
                errores += 1

        if errores == 0:
            await query.edit_message_text(
                f"✅ {len(transacciones)} transacciones registradas en Notion."
            )
        else:
            await query.edit_message_text(
                f"⚠️ Se registraron {len(transacciones) - errores}/{len(transacciones)}. "
                f"{errores} fallaron — revisa Notion."
            )

    elif data == "lote_revisar":
        # Solo muestra el resumen de nuevo — NO inicia revisión individual.
        # Evita el flujo uno-a-uno que causaba duplicados.
        transacciones = context.user_data.get(CTX_PENDIENTES, [])
        if not transacciones:
            await query.edit_message_text("⚠️ No hay transacciones pendientes.")
            return
        teclado = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Registrar todas", callback_data="lote_confirmar"),
            InlineKeyboardButton("❌ Cancelar", callback_data="lote_cancelar"),
        ]])
        await query.edit_message_text(
            resumen_lote(transacciones),
            reply_markup=teclado,
        )

    elif data == "lote_cancelar":
        context.user_data.pop(CTX_PENDIENTES, None)
        await query.edit_message_text("❌ Registro cancelado.")

    # ── Flujo individual (solo para 1 transacción de texto con baja confianza) ──
    elif data == "ind_confirmar":
        t = context.user_data.pop(CTX_INDIVIDUAL, None)
        # Limpia también cualquier lote pendiente para evitar doble-registro
        context.user_data.pop(CTX_PENDIENTES, None)
        if not t:
            await query.edit_message_text("⚠️ No hay transacción pendiente.")
            return
        try:
            await _registrar_transaccion(t)
            respuesta = gasto_confirmado(t) if t["tipo"] == "gasto" else ingreso_confirmado(t)
            await query.edit_message_text(respuesta)
        except RuntimeError:
            await query.edit_message_text(error_notion())

    elif data == "ind_cancelar":
        context.user_data.pop(CTX_INDIVIDUAL, None)
        await query.edit_message_text("❌ Transacción cancelada.")
