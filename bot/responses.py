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


_MESES_ES_LARGO = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio",
                   "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def reporte_mensual_mensaje(data: dict) -> str:
    mes = _MESES_ES_LARGO[data["month"]].upper()
    anio = data["year"]

    ti = data["total_ingresos"]
    mi = data["meta_ingresos"]
    pct_i = f"{ti / mi * 100:.0f}%" if mi > 0 else "—"

    tg = data["total_gastos"]
    mg = data["meta_gastos"]
    res = data["resultado"]

    lineas = [f"📊 *RESUMEN FINANCIERO — {mes} {anio}*\n"]

    lineas.append("💰 *INGRESOS*")
    lineas.append(f"Total real: *{_fmt_monto(ti)}* de {_fmt_monto(mi)} proyectados ({pct_i})")
    for cat, monto in sorted(data["ingresos_por_cat"].items(), key=lambda x: x[1], reverse=True):
        lineas.append(f"  • {cat}: {_fmt_monto(monto)}")

    lineas.append("\n💸 *GASTOS*")
    lineas.append(f"Total gastado: *{_fmt_monto(tg)}* de {_fmt_monto(mg)} proyectados")
    if data["top_gastos"]:
        lineas.append("Top 3 categorías:")
        for i, (cat, monto) in enumerate(data["top_gastos"], 1):
            lineas.append(f"  {i}. {cat}: {_fmt_monto(monto)}")

    if data["ahorros"]:
        lineas.append("\n🏦 *AHORROS*")
        for a in data["ahorros"]:
            icono = "✅" if a["estado"] == "LISTO" else ("🔄" if a["estado"] == "INCOMPLETO" else "❌")
            nombre = _nombre_limpio(a["nombre"])
            lineas.append(f"  {icono} {nombre}: {_fmt_monto(a['ahorrado'])}/{_fmt_monto(a['proyectado'])}")

    lineas.append("\n📈 *BALANCE FINAL*")
    lineas.append(f"Resultado: *{_fmt_monto(res)}*")
    lineas.append("Cerraste con superávit 💪" if res >= 0 else "Cerraste con déficit ⚠️")

    return "\n".join(lineas)


def gastos_analisis_mensaje(data: dict) -> str:
    filas = data["gastos_filas"]
    mes = data["mes_nombre"]
    dias_t = data["dias_transcurridos"]
    dias_r = data["dias_restantes"]

    if not filas:
        return f"📊 No hay datos de gastos para {mes}."

    total_real = sum(f["real"] for f in filas)
    total_proy = sum(f["proyectado"] for f in filas)
    excedidos = [f for f in filas if f["exceso"] > 0]
    al_limite = [f for f in filas if 80 <= f["pct_usado"] < 100 and f["exceso"] == 0]

    lineas = [f"📊 *Análisis de gastos — {mes}* (día {dias_t})\n"]
    lineas.append(f"Total ejecutado: *{_fmt_monto(total_real)}* de {_fmt_monto(total_proy)} proyectados "
                  f"({round(total_real / total_proy * 100) if total_proy else 0}%)\n")

    if excedidos:
        lineas.append("🔴 *Excedidos:*")
        for f in sorted(excedidos, key=lambda x: x["exceso"], reverse=True):
            lineas.append(f"  • {f['nombre_display']}: {_fmt_monto(f['real'])} "
                          f"(+{_fmt_monto(f['exceso'])} sobre {_fmt_monto(f['proyectado'])})")

    if al_limite:
        lineas.append("\n🟡 *Cerca del límite (>80%):*")
        for f in sorted(al_limite, key=lambda x: x["pct_usado"], reverse=True):
            lineas.append(f"  • {f['nombre_display']}: {f['pct_usado']}% usado")

    lineas.append(f"\n💡 Quedan {dias_r} días en el mes.")
    return "\n".join(lineas)


def ahorros_analisis_mensaje(data: dict) -> str:
    ahorros = data["ahorros"]
    mes = data["mes_nombre"]
    pct_total = data["pct_ahorro"]
    total_ahorrado = data["total_ahorrado"]
    total_meta = data["total_meta_ahorro"]

    if not ahorros:
        return "🏦 No hay metas de ahorro registradas."

    completos = [a for a in ahorros if a["estado"] == "LISTO"]
    en_proceso = [a for a in ahorros if a["estado"] == "INCOMPLETO"]
    sin_ahorro = [a for a in ahorros if a["estado"] == "NO AHORROS"]

    lineas = [f"🏦 *Análisis de ahorros — {mes}*\n"]
    lineas.append(f"Total: *{_fmt_monto(total_ahorrado)}* de {_fmt_monto(total_meta)} ({pct_total}%)\n")

    if completos:
        lineas.append("✅ *Completos:*")
        for a in completos:
            lineas.append(f"  • {_nombre_limpio(a['nombre'])}: {_fmt_monto(a['ahorrado'])}")

    if en_proceso:
        lineas.append("\n⏳ *En proceso:*")
        for a in en_proceso:
            falta = max(0, a["proyectado"] - a["ahorrado"])
            lineas.append(f"  • {_nombre_limpio(a['nombre'])}: {_fmt_monto(a['ahorrado'])}/{_fmt_monto(a['proyectado'])} "
                          f"(faltan {_fmt_monto(falta)})")

    if sin_ahorro:
        lineas.append("\n❌ *Sin ahorrar:*")
        for a in sin_ahorro:
            lineas.append(f"  • {_nombre_limpio(a['nombre'])}: meta {_fmt_monto(a['proyectado'])}")

    return "\n".join(lineas)


def ingresos_analisis_mensaje(data: dict) -> str:
    ing = data["ingresos"]
    mes = data["mes_nombre"]
    dias_t = data["dias_transcurridos"]
    dias_r = data["dias_restantes"]

    total_real = ing["total_real"]
    total_meta = ing["total_meta"]
    pct = ing["pct"]
    proyectado_fin = ing["proyectado_fin"]
    necesario_dia = ing["necesario_dia"]

    lineas = [f"💰 *Análisis de ingresos — {mes}* (día {dias_t})\n"]
    lineas.append(f"Real: *{_fmt_monto(total_real)}* de {_fmt_monto(total_meta)} meta ({pct}%)")

    if proyectado_fin >= total_meta:
        lineas.append(f"📈 Al ritmo actual llegarías a *{_fmt_monto(proyectado_fin)}* al fin del mes ✅")
    else:
        lineas.append(f"⚠️ Al ritmo actual cerrarías en *{_fmt_monto(proyectado_fin)}*")
        lineas.append(f"   Necesitas {_fmt_monto(necesario_dia)}/día para alcanzar la meta\n")

    if ing["por_categoria"]:
        lineas.append("\n📋 *Por fuente:*")
        for cat in sorted(ing["por_categoria"], key=lambda x: x["real"], reverse=True):
            pct_cat = round(cat["real"] / cat["meta"] * 100) if cat["meta"] > 0 else 0
            lineas.append(f"  • {cat['categoria']}: {_fmt_monto(cat['real'])} / {_fmt_monto(cat['meta'])} ({pct_cat}%)")

    return "\n".join(lineas)


def resumen_financiero_mensaje(data: dict) -> str:
    mes = data["mes_nombre"]
    dias_t = data["dias_transcurridos"]
    dias_r = data["dias_restantes"]
    ing = data["ingresos"]

    total_real_ing = ing["total_real"]
    total_meta_ing = ing["total_meta"]
    pct_ing = ing["pct"]

    filas = data["gastos_filas"]
    total_real_gas = sum(f["real"] for f in filas)
    total_proy_gas = sum(f["proyectado"] for f in filas)
    pct_gas = round(total_real_gas / total_proy_gas * 100) if total_proy_gas > 0 else 0
    excedidos = [f for f in filas if f["exceso"] > 0]

    disponible = total_real_ing - total_real_gas
    pct_ahorro_g = data["pct_ahorro"]

    lineas = [f"📊 *Resumen financiero — {mes}* (día {dias_t}, faltan {dias_r})\n"]
    lineas.append(f"💰 Ingresos: *{_fmt_monto(total_real_ing)}* / {_fmt_monto(total_meta_ing)} ({pct_ing}%)")
    lineas.append(f"💸 Gastos: *{_fmt_monto(total_real_gas)}* / {_fmt_monto(total_proy_gas)} ({pct_gas}%)")
    lineas.append(f"💵 Disponible: *{_fmt_monto(disponible)}*")
    lineas.append(f"🏦 Ahorros: *{_fmt_monto(data['total_ahorrado'])}* / {_fmt_monto(data['total_meta_ahorro'])} ({pct_ahorro_g}%)")

    if excedidos:
        lineas.append(f"\n⚠️ {len(excedidos)} categoría(s) excedida(s): "
                      + ", ".join(f["nombre_display"] for f in excedidos[:3]))

    return "\n".join(lineas)


def categoria_analisis_mensaje(categoria: str, filas: list[dict], transacciones: list[dict],
                               modo_falta: bool = False) -> str:
    if not filas:
        return (
            f"📊 *{categoria}*\n"
            f"Esta categoría no tiene presupuesto proyectado para este mes.\n"
            f"Los gastos se registran en el detalle pero no afectan ninguna proyección."
        )

    fila = filas[0]
    real = fila["real"]
    proyectado = fila["proyectado"]
    pct = fila["pct_usado"]
    exceso = fila["exceso"]
    nombre = fila["nombre_display"]
    falta = max(0.0, proyectado - real)

    if exceso > 0:
        estado = f"🔴 Excedido en {_fmt_monto(exceso)}"
    elif pct >= 80:
        estado = f"🟡 Al {pct}% del límite"
    else:
        estado = f"🟢 {pct}% usado — quedan {_fmt_monto(falta)}"

    if modo_falta:
        if exceso > 0:
            return (f"📊 *{nombre}*\n\n"
                    f"Ya excediste el presupuesto en *{_fmt_monto(exceso)}*\n"
                    f"Gastado: {_fmt_monto(real)} / Proyectado: {_fmt_monto(proyectado)}")
        return (f"📊 *{nombre}*\n\n"
                f"Te falta: *{_fmt_monto(falta)}*\n"
                f"Pagado: {_fmt_monto(real)} de {_fmt_monto(proyectado)} ({pct}%)")

    lineas = [f"📊 *{nombre}*\n",
              f"Real: *{_fmt_monto(real)}* / Proyectado: {_fmt_monto(proyectado)}",
              estado]

    if transacciones:
        lineas.append("\n🧾 *Últimas transacciones:*")
        for t in transacciones:
            fecha = t["fecha"][:10] if t["fecha"] else ""
            lineas.append(f"  • {fecha} — {t['descripcion'] or '(sin descripción)'}: {_fmt_monto(t['monto'])}")

    return "\n".join(lineas)


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
