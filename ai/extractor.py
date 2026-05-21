import base64
import json
import re
from datetime import date
from openai import OpenAI
from config.settings import OPENAI_API_KEY, EXTRACTION_PROMPT, CATEGORIAS_GASTOS, CATEGORIAS_INGRESOS

client = OpenAI(api_key=OPENAI_API_KEY)


def _build_prompt() -> str:
    return EXTRACTION_PROMPT.format(
        categorias_gastos="\n".join(f"  - {c}" for c in CATEGORIAS_GASTOS),
        categorias_ingresos="\n".join(f"  - {c}" for c in CATEGORIAS_INGRESOS),
        fecha_hoy=date.today().isoformat(),
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
                            "Esta es una captura de pantalla de la app Monefy. "
                            "Extrae TODAS las transacciones visibles siguiendo estas reglas:\n\n"
                            "FORMATO VISUAL DE MONEFY:\n"
                            "- La fecha del día aparece como encabezado (ej: '17 mayo', 'Hoy', 'Ayer')\n"
                            "- Cada transacción tiene un círculo de color a la izquierda: "
                            "VERDE = ingreso, ROJO/NARANJA = gasto\n"
                            "- La categoría aparece en texto grande\n"
                            "- Una subcategoría o descripción puede aparecer en texto más pequeño debajo\n"
                            "- El monto aparece a la derecha (ej: '14.00', '$9.75')\n\n"
                            "INSTRUCCIONES:\n"
                            "1. Lee la fecha del encabezado y aplícala a todas las transacciones de ese bloque\n"
                            "2. Determina ingreso/gasto por el color del círculo (verde=ingreso, rojo=gasto)\n"
                            "3. Usa la categoría visible para mapear a categoria_notion\n"
                            "4. Extrae el monto numérico exacto que aparece a la derecha\n"
                            "5. Si hay múltiples bloques de fechas, respeta cada fecha"
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
