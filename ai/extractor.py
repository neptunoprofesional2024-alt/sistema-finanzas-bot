import base64
import json
import re
from datetime import date, timedelta
from openai import OpenAI
from config.settings import OPENAI_API_KEY, EXTRACTION_PROMPT, CATEGORIAS_GASTOS, CATEGORIAS_INGRESOS

client = OpenAI(api_key=OPENAI_API_KEY)


def _build_prompt() -> str:
    hoy = date.today()
    return EXTRACTION_PROMPT.format(
        categorias_gastos="\n".join(f"  - {c}" for c in CATEGORIAS_GASTOS),
        categorias_ingresos="\n".join(f"  - {c}" for c in CATEGORIAS_INGRESOS),
        fecha_hoy=hoy.isoformat(),
        anio_hoy=hoy.year,
    )


def _parse_json(raw: str) -> dict:
    """Extrae el JSON de la respuesta aunque venga con texto extra."""
    raw = raw.strip()
    # intenta directo
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # busca bloque JSON entre llaves
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError(f"No se pudo parsear JSON de la respuesta: {raw[:300]}")


def detectar_intencion(texto: str) -> dict:
    """
    Clasifica la intención del mensaje con gpt-4o-mini (barato, rápido).
    Se usa cuando ninguna keyword local matcheó y antes de llamar al extractor
    completo de transacciones.

    Retorna dict con claves:
      intencion, categoria_especifica, filtros, presupuesto, confianza
    """
    categorias_str = "\n".join(f"  - {c}" for c in CATEGORIAS_GASTOS)

    system_prompt = f"""Eres un clasificador de intenciones para un bot de finanzas personales.
Dado un mensaje, determina su intención. Responde SOLO JSON sin markdown.

CATEGORÍAS DE GASTOS VÁLIDAS (usa estos nombres exactos en categoria_especifica):
{categorias_str}

INTENCIONES:
"consulta_gastos"         - análisis general de gastos del mes
"consulta_ingresos"       - ver ingresos o ganancias del mes
"consulta_ahorros"        - ver estado o avance de ahorros
"consulta_prioridades"    - ver qué debe pagar / prioridades de pago
"consulta_pagos_proximos" - ver próximos pagos o vencimientos
"consulta_resumen"        - resumen financiero general
"consulta_categoria"      - pregunta sobre una categoría específica de gasto
"marcar_pagado"           - marcar un pago como completado
"registro_transaccion"    - registrar un gasto o ingreso nuevo
"otro"                    - nada de lo anterior

ESQUEMA:
{{"intencion":"<valor>","categoria_especifica":"<cat exacta o null>","filtros":["x","y"] o null,"presupuesto":<número o null>,"confianza":"alta"|"media"|"baja"}}

EJEMPLOS:
"cual es el avance de mis ahorros"   → {{"intencion":"consulta_ahorros","categoria_especifica":null,"filtros":null,"presupuesto":null,"confianza":"alta"}}
"que tal los gastos del mes"         → {{"intencion":"consulta_gastos","categoria_especifica":null,"filtros":null,"presupuesto":null,"confianza":"alta"}}
"que me falta pagar este mes"        → {{"intencion":"consulta_pagos_proximos","categoria_especifica":null,"filtros":null,"presupuesto":null,"confianza":"alta"}}
"en que estoy gastando mas"          → {{"intencion":"consulta_gastos","categoria_especifica":null,"filtros":null,"presupuesto":null,"confianza":"alta"}}
"cuanto he ganado este mes"          → {{"intencion":"consulta_ingresos","categoria_especifica":null,"filtros":null,"presupuesto":null,"confianza":"alta"}}
"dime las prioridades"               → {{"intencion":"consulta_prioridades","categoria_especifica":null,"filtros":null,"presupuesto":null,"confianza":"alta"}}
"como voy con el gym"                → {{"intencion":"consulta_categoria","categoria_especifica":"GYM mensual","filtros":null,"presupuesto":null,"confianza":"alta"}}
"cuanto llevo en taxi"               → {{"intencion":"consulta_categoria","categoria_especifica":"Taxis personales","filtros":null,"presupuesto":null,"confianza":"alta"}}
"omite alimentacion, despues de coral cuales siguen" → {{"intencion":"consulta_prioridades","categoria_especifica":null,"filtros":["alimentacion","coral"],"presupuesto":null,"confianza":"alta"}}
"tengo 50 dolares disponibles que me recomiendas pagar" → {{"intencion":"consulta_prioridades","categoria_especifica":null,"filtros":null,"presupuesto":50,"confianza":"alta"}}
"gasté 15 en taxi"                   → {{"intencion":"registro_transaccion","categoria_especifica":null,"filtros":null,"presupuesto":null,"confianza":"alta"}}
"ya pagué el coral"                  → {{"intencion":"marcar_pagado","categoria_especifica":null,"filtros":null,"presupuesto":null,"confianza":"alta"}}
"hola"                               → {{"intencion":"otro","categoria_especifica":null,"filtros":null,"presupuesto":null,"confianza":"alta"}}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": texto},
        ],
        temperature=0,
        max_tokens=150,
    )
    raw = response.choices[0].message.content
    try:
        return _parse_json(raw)
    except Exception:
        return {"intencion": "otro", "confianza": "baja"}


def extract_from_text(texto: str) -> dict:
    """Extrae transacciones de texto libre del usuario."""
    prompt = _build_prompt()

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Texto del usuario: {texto}"},
        ],
        temperature=0,
        max_tokens=1000,
    )

    raw = response.choices[0].message.content
    return _parse_json(raw)


def extract_from_image(image_bytes: bytes) -> dict:
    """Extrae transacciones de una captura de pantalla de Monefy."""
    prompt = _build_prompt()
    b64 = base64.b64encode(image_bytes).decode("utf-8")

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Esta es una captura de pantalla de la app Monefy. "
                            f"La fecha de HOY es {date.today().isoformat()}. "
                            f"Extrae TODAS las transacciones visibles siguiendo estas reglas:\n\n"
                            "FORMATO VISUAL DE MONEFY:\n"
                            "- Cada grupo de transacciones tiene un ENCABEZADO DE FECHA visible arriba\n"
                            "- El encabezado puede ser: 'Hoy', 'Ayer', '17 may', '3 jun', etc.\n"
                            "- Cada transacción tiene un círculo de color a la izquierda: "
                            "VERDE = ingreso, ROJO/NARANJA = gasto\n"
                            "- La categoría aparece en texto grande\n"
                            "- Una subcategoría o descripción puede aparecer en texto más pequeño debajo\n"
                            "- El monto aparece a la derecha (ej: '14.00', '$9.75')\n\n"
                            "INSTRUCCIONES DE FECHA (CRÍTICO):\n"
                            f"1. Lee el encabezado de fecha de CADA grupo y asígnalo a TODAS las transacciones de ese grupo\n"
                            f"2. Conversión de fechas (año actual = {date.today().year}):\n"
                            f"   - 'Hoy' → {date.today().isoformat()}\n"
                            f"   - 'Ayer' → {(date.today() - timedelta(days=1)).isoformat()}\n"
                            "   - 'N may' / 'N mayo' → YYYY-05-0N (ej: '17 may' → año actual-05-17)\n"
                            "   - 'N jun' / 'N julio' etc. → el mes correspondiente\n"
                            "3. NUNCA uses la fecha de hoy para transacciones que tienen otro encabezado de fecha\n"
                            "4. Si hay múltiples bloques con distintas fechas, cada bloque mantiene su fecha\n"
                            "5. Si no puedes leer la fecha de un grupo, usa null\n\n"
                            "INSTRUCCIONES GENERALES:\n"
                            "1. Extrae TODAS las transacciones visibles\n"
                            "2. Determina ingreso/gasto por el color del círculo (verde=ingreso, rojo=gasto)\n"
                            "3. Usa la categoría visible para mapear a categoria_notion\n"
                            "4. Extrae el monto numérico exacto que aparece a la derecha"
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{b64}",
                            "detail": "high",
                        },
                    },
                ],
            },
        ],
        temperature=0,
        max_tokens=2000,
    )

    raw = response.choices[0].message.content
    return _parse_json(raw)
