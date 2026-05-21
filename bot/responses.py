from __future__ import annotations
from datetime import datetime
from utils.formatters import format_currency, format_date, format_percentage


def gasto_confirmado(transaccion: dict) -> str:
    return (
        f"✅ Gasto registrado\n\n"
        f"💸 {format_currency(transaccion['monto'])} — {transaccion['descripcion']}\n"
        f"📁 {transaccion['categoria_notion']}\n"
        f"📅 {format_date(transaccion['fecha'])}"
    )


def ingreso_confirmado(transaccion: dict) -> str:
    return (
        f"✅ Ingreso registrado\n\n"
        f"💰 {format_currency(transaccion['monto'])} — {transaccion['descripcion']}\n"
        f"📥 {transaccion['categoria_notion']}\n"
        f"📅 {format_date(transaccion['fecha'])}"
    )


def resumen_lote(transacciones: list[dict]) -> str:
    lineas = [f"🔍 Encontré {len(transacciones)} transacciones:\n"]
    for i, t in enumerate(transacciones, 1):
        emoji = "💸" if t["tipo"] == "gasto" else "💰"
        lineas.append(
            f"{i}. {emoji} {format_currency(t['monto'])} — {t['descripcion']}\n"
            f"   📁 {t['categoria_notion']} | 📅 {format_date(t['fecha'])}"
        )
    lineas.append("\n¿Las registro todas?")
    return "\n".join(lineas)


def confirmar_individual(transaccion: dict) -> str:
    emoji = "💸" if transaccion["tipo"] == "gasto" else "💰"
    tipo_str = "Gasto" if transaccion["tipo"] == "gasto" else "Ingreso"
    return (
        f"🤔 Confirma este {tipo_str.lower()}:\n\n"
        f"{emoji} {format_currency(transaccion['monto'])} — {transaccion['descripcion']}\n"
        f"📁 {transaccion['categoria_notion']}\n"
        f"📅 {format_date(transaccion['fecha'])}"
    )


def balance_mensaje(data: dict) -> str:
    mes = datetime.now().strftime("%B %Y").capitalize()
    ingresos_real = data["ingresos_real"]
    ingresos_meta = data["ingresos_meta"]
    gastos = data["gastos"]
    disponible = data["disponible"]
    ahorros = data["ahorros"]

    faltan = max(0, ingresos_meta - ingresos_real)
    pct_ingresos = format_percentage(ingresos_real, ingresos_meta) if ingresos_meta else "—"

    lineas = [
        f"📊 Balance {mes}\n",
        "💰 INGRESOS",
        f"  Real: {format_currency(ingresos_real)} | Meta: {format_currency(ingresos_meta)}",
        f"  Faltan: {format_currency(faltan)} ({pct_ingresos})\n",
        "💸 GASTOS DEL MES",
        f"  Ejecutado: {format_currency(gastos)}\n",
        f"💵 DISPONIBLE ESTIMADO: {format_currency(disponible)}\n",
    ]

    if ahorros:
        lineas.append("🏦 AHORROS")
        for a in ahorros:
            icono = "✅" if a["estado"] == "LISTO" else ("⏳" if a["estado"] == "INCOMPLETO" else "❌")
            lineas.append(
                f"  {a['nombre']}: {format_currency(a['ahorrado'])}/{format_currency(a['proyectado'])} "
                f"({a['porcentaje']}%) {icono}"
            )

    return "\n".join(lineas)


def pendientes_mensaje(pendientes: list[dict]) -> str:
    if not pendientes:
        return "✅ No hay gastos pendientes o en proceso."

    lineas = ["📋 Gastos pendientes / en proceso:\n"]
    for p in pendientes:
        etiqueta_emoji = "🔄" if p["etiqueta"] == "En proceso" else "⏰"
        lineas.append(
            f"{etiqueta_emoji} {p['nombre']}\n"
            f"   Proyectado: {format_currency(p['proyectado'])} | "
            f"Real: {format_currency(p['real'])} | {p['etiqueta']}"
        )
    return "\n".join(lineas)


def ahorros_mensaje(ahorros: list[dict]) -> str:
    if not ahorros:
        return "🏦 No hay metas de ahorro registradas."

    lineas = ["🏦 Estado de tus ahorros:\n"]
    for a in ahorros:
        icono = "✅" if a["estado"] == "LISTO" else ("⏳" if a["estado"] == "INCOMPLETO" else "❌")
        barra = _barra_progreso(a["porcentaje"])
        lineas.append(
            f"{icono} {a['nombre']}\n"
            f"   {barra} {a['porcentaje']}%\n"
            f"   Ahorrado: {format_currency(a['ahorrado'])} / Meta: {format_currency(a['proyectado'])}"
        )
    return "\n".join(lineas)


def _barra_progreso(pct: float, largo: int = 10) -> str:
    llenos = int(min(pct, 100) / 100 * largo)
    return "█" * llenos + "░" * (largo - llenos)


def _emoji_urgencia_dias(dias: int) -> str:
    if dias == 0:
        return "🔴"
    if dias <= 2:
        return "🟠"
    return "🟡"


def alertas_mensaje(alertas: list[dict]) -> str:
    """Formato para el envío automático de las 9:30 AM (máx 3 días)."""
    lineas = ["⏰ Recordatorio de pagos próximos\n"]
    for a in alertas:
        emoji = _emoji_urgencia_dias(a["dias"])
        if a["dias"] == 0:
            cuando = "Hoy"
        elif a["dias"] == 1:
            cuando = "Mañana"
        else:
            cuando = f"En {a['dias']} días"
        dia_str = a["fecha"].strftime("%d/%m")
        lineas.append(f"📅 {cuando} ({dia_str}):\n{emoji} {a['concepto']} — ${a['monto']:.0f}")
    return "\n\n".join(lineas)


def pagos_proximos_mensaje(alertas: list[dict]) -> str:
    """Formato para respuesta a lenguaje natural (hasta 7 días)."""
    if not alertas:
        return "✅ No tienes pagos en los próximos 7 días."
    lineas = ["📆 Próximos pagos:\n"]
    for a in alertas:
        emoji = _emoji_urgencia_dias(a["dias"])
        if a["dias"] == 0:
            cuando = "Hoy"
        elif a["dias"] == 1:
            cuando = "Mañana"
        else:
            cuando = f"En {a['dias']} días"
        dia_str = a["fecha"].strftime("%d/%m")
        lineas.append(f"{emoji} {cuando} ({dia_str}) — {a['concepto']}: ${a['monto']:.0f}")
    return "\n".join(lineas)


def _nombre_limpio(nombre: str) -> str:
    """Normaliza nombres de Notion con tabs/newlines para mostrar en Telegram."""
    import re
    return re.sub(r"\s+", " ", nombre).strip()


def sugerencias_ahorro_mensaje(data: dict) -> str:
    pendientes = data["pendientes"]
    total_diario = data["total_diario"]
    dias_restantes = data["dias_restantes"]

    if not pendientes:
        return "✅ Todas tus metas de ahorro del mes están completas."

    lineas = [f"💡 Sugerencias de ahorro ({dias_restantes} días restantes en el mes)\n"]
    for i, a in enumerate(pendientes, 1):
        nombre = _nombre_limpio(a["nombre"])
        lineas.append(
            f"🎯 Prioridad {i}: {nombre}\n"
            f"   Falta: ${a['falta']:.0f} — Ahorra ${a['diario']:.2f}/día"
        )
    lineas.append(f"\n💪 Si ahorras ${total_diario:.2f}/día cumples todas tus metas este mes.")
    return "\n\n".join(lineas)


_MESES_CORTOS = ["", "ene", "feb", "mar", "abr", "may", "jun",
                 "jul", "ago", "sep", "oct", "nov", "dic"]


def _fmt_monto(valor: float) -> str:
    return f"${int(valor)}" if valor == int(valor) else f"${valor:.2f}"


def prioridades_mensaje(prioridades: list[dict], todas: bool = False) -> str:
    if not prioridades:
        return "✅ No hay prioridades financieras pendientes."

    from datetime import date
    hoy = date.today()
    dia_str = f"{hoy.day} {_MESES_CORTOS[hoy.month]}"
    bloques = [f"🎯 *Tus prioridades ahora mismo — {dia_str}*"]

    for p in prioridades:
        falta = p["falta"]
        real = p.get("real", 0.0)
        proyectado = p.get("proyectado", 0.0)
        dia_venc = p.get("dia_vencimiento")
        dias = p.get("dias", 30)
        venc_fecha = p.get("vencimiento_fecha")

        # Línea de monto
        if dia_venc is not None and real > 0:
            monto_str = f"{_fmt_monto(falta)} restante"
        elif dia_venc is not None:
            monto_str = _fmt_monto(falta)
        else:
            monto_str = f"{_fmt_monto(falta)} restante de {_fmt_monto(proyectado)}"

        header = f"{p['urgencia']} *#{p['numero']} — {p['concepto']}* ({monto_str})"

        # Línea de vencimiento / progreso
        if dia_venc is not None:
            mes_nombre = _MESES_CORTOS[venc_fecha.month] if venc_fecha else ""
            if dias == 0:
                detalle = f"   Vence *HOY* (día {dia_venc})"
            elif dias == 1:
                detalle = f"   Vence *MAÑANA* (día {dia_venc} {mes_nombre})"
            else:
                detalle = f"   Vence en {dias} días (día {dia_venc} {mes_nombre})"
        else:
            detalle = f"   Mes en curso — llevas {_fmt_monto(real)}/{_fmt_monto(proyectado)}"

        bloques.append(f"{header}\n{detalle}")

    if not todas:
        bloques.append("_Escribe /prioridades todas para ver la lista completa._")

    return "\n\n".join(bloques)


def error_notion() -> str:
    return "⚠️ No pude conectar con Notion ahora mismo. Intenta de nuevo en un momento."


def error_ia() -> str:
    return "⚠️ No pude procesar eso. ¿Puedes escribirlo de otra forma? Ejemplo: 'gasté 25 en taxi'"


def bienvenida() -> str:
    return (
        "👋 ¡Hola! Soy tu asistente financiero personal.\n\n"
        "Puedo registrar tus gastos e ingresos directamente en Notion.\n\n"
        "📝 *Cómo usarme:*\n"
        "• Escríbeme: `gasté 14 en restaurantes`\n"
        "• Escríbeme: `cobré 400 de 1xbet`\n"
        "• Envíame una captura de Monefy\n\n"
        "📊 *Comandos:*\n"
        "/balance — Ver tu estado financiero del mes\n"
        "/pendientes — Gastos pendientes/en proceso\n"
        "/ahorros — Estado de tus metas de ahorro\n"
        "/prioridades — Tus 3 prioridades más urgentes\n"
        "/prioridades todas — Lista completa de prioridades\n"
        "/ayuda — Ver esta ayuda\n"
    )
