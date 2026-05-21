from __future__ import annotations
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from ai.extractor import extract_from_text, extract_from_image
from notion.expenses import create_expense_entry
from notion.income import create_income_entry
from bot.responses import (
    gasto_confirmado,
    ingreso_confirmado,
    resumen_lote,
    confirmar_individual,
    prioridades_mensaje,
    pagos_proximos_mensaje,
    sugerencias_ahorro_mensaje,
    error_ia,
    error_notion,
)

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
    "qué toca", "que toca", "vencimientos",
]

logger = logging.getLogger(__name__)

# Claves de contexto para el flujo de confirmación
CTX_PENDIENTES = "transacciones_pendientes"
CTX_INDIVIDUAL = "transaccion_individual"


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
    texto = update.message.text.strip()
    texto_lower = texto.lower()

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
        transacciones = context.user_data.get(CTX_PENDIENTES, [])
        if not transacciones:
            await query.edit_message_text("⚠️ No hay transacciones pendientes.")
            return
        # Mostrar la primera para revisión individual
        t = transacciones[0]
        context.user_data[CTX_INDIVIDUAL] = t
        context.user_data[CTX_PENDIENTES] = transacciones[1:]  # cola restante
        await query.edit_message_text(
            confirmar_individual(t),
            reply_markup=_teclado_confirmacion_individual(),
        )

    # ── Flujo individual ──
    elif data == "ind_confirmar":
        t = context.user_data.pop(CTX_INDIVIDUAL, None)
        if not t:
            await query.edit_message_text("⚠️ No hay transacción pendiente.")
            return
        try:
            await _registrar_transaccion(t)
            respuesta = gasto_confirmado(t) if t["tipo"] == "gasto" else ingreso_confirmado(t)
            await query.edit_message_text(respuesta)
        except RuntimeError:
            await query.edit_message_text(error_notion())

        # Si hay más en la cola (venía de "Revisar")
        cola = context.user_data.get(CTX_PENDIENTES, [])
        if cola:
            siguiente = cola[0]
            context.user_data[CTX_INDIVIDUAL] = siguiente
            context.user_data[CTX_PENDIENTES] = cola[1:]
            await query.message.reply_text(
                confirmar_individual(siguiente),
                reply_markup=_teclado_confirmacion_individual(),
            )

    elif data == "ind_cancelar":
        context.user_data.pop(CTX_INDIVIDUAL, None)
        await query.edit_message_text("❌ Transacción cancelada.")
