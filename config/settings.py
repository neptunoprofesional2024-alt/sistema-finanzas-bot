import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")

NOTION_INGRESOS_DB_ID = os.getenv("NOTION_INGRESOS_DB_ID")
NOTION_GASTOS_DB_ID = os.getenv("NOTION_GASTOS_DB_ID")
NOTION_PROYECCIONES_GASTOS_DB_ID = os.getenv("NOTION_PROYECCIONES_GASTOS_DB_ID")
NOTION_PROYECCIONES_INGRESOS_DB_ID = os.getenv("NOTION_PROYECCIONES_INGRESOS_DB_ID")
NOTION_AHORROS_DB_ID = os.getenv("NOTION_AHORROS_DB_ID")
NOTION_PRIORIDADES_DB_ID = os.getenv("NOTION_PRIORIDADES_DB_ID")

PAGOS_FIJOS = {
    "Alquiler mensual": {
        "dia": 20,
        "monto": 400,
        "descripcion": "Alquiler mensual",
    },
    "Tarjeta de crédito Pacifico (Laptop)": {
        "dia": 5,
        "monto": 295,
        "descripcion": "Tarjeta Pacífico - máximo día 5",
        "es_tarjeta_credito": True,
    },
    "Tarjeta de crédito Pichincha.": {
        "dia": 12,
        "monto": 95,
        "descripcion": "Tarjeta Pichincha",
        "es_tarjeta_credito": True,
    },
    "Pago al Coral": {
        "dia": 1,
        "monto": 130,
        "descripcion": "Supermercado Coral",
    },
    "Factura plan Mensual": {
        "dia": 26,
        "monto": 20,
        "descripcion": "Plan de teléfono",
    },
    "Factura Luz mensual": {
        "dia": 10,
        "monto": 40,
        "descripcion": "Luz eléctrica",
    },
    "Factura agua Mensual": {
        "dia": 10,
        "monto": 20,
        "descripcion": "Agua potable",
    },
    "Parqueo moto edificio": {
        "dia": 26,
        "monto": 25,
        "descripcion": "Parqueo moto edificio",
    },
}

# Categorías exactas de gastos en Notion
CATEGORIAS_GASTOS = [
    # Rojo — Hogar/obligaciones fijas
    "créditos y responsabilidades",
    "Alquiler mensual",
    "Factura agua Mensual",
    "Factura Luz mensual",
    "Factura internet mensual",
    "Mantenimiento de Hogar",
    "Pago a Limpieza",
    "Factura plan Mensual",
    # Amarillo/Naranja — Transporte
    "Gasolina para la Moto",
    "Mantenimiento de Moto",
    "Taxis personales",
    "Transporte Público",
    # Verde — Alimentación/Calidad de vida
    "Compras de Alimentación",
    "Comida en Delivery",
    "Higiene Personal",
    "Restaurantes",
    "GYM mensual",
    # Azul — Calidad de vida/ocio
    "Compras ocasionales ( ropa )",
    "Suscripciones ( Netflix etc.)",
    "Regalos y propinas",
    "Salidas y Ocio",
    "Vacaciones",
    # Morado/Rosa — Salud/Ahorros/Inversiones
    "Gastos médicos",
    "Inversiones",
    "Ahorros",
    "Viático",
]

# Categorías exactas de ingresos en Notion
CATEGORIAS_INGRESOS = [
    "Comisiones por ventas.",
    "Ingresos pasivos || Agencia Neptuno",
    "Referidos de 1xbet",
    "Comisiones Aliados Neptuno",
]

# Mapeo de palabras clave → categoría exacta de Notion (gastos)
MAPEO_GASTOS = {
    # Alimentación
    "restaurante": "Restaurantes",
    "restaurant": "Restaurantes",
    "comida": "Restaurantes",
    "almuerzo": "Restaurantes",
    "cena": "Restaurantes",
    "desayuno": "Restaurantes",
    "delivery": "Comida en Delivery",
    "rappi": "Comida en Delivery",
    "uber eats": "Comida en Delivery",
    "pedidos ya": "Comida en Delivery",
    "mercado": "Compras de Alimentación",
    "supermercado": "Compras de Alimentación",
    "feria": "Compras de Alimentación",
    "víveres": "Compras de Alimentación",
    "compras": "Compras de Alimentación",
    # Transporte
    "taxi": "Taxis personales",
    "uber": "Taxis personales",
    "cabify": "Taxis personales",
    "bus": "Transporte Público",
    "metro": "Transporte Público",
    "transporte público": "Transporte Público",
    "gasolina": "Gasolina para la Moto",
    "combustible": "Gasolina para la Moto",
    "nafta": "Gasolina para la Moto",
    "moto": "Mantenimiento de Moto",
    "mecánico": "Mantenimiento de Moto",
    "taller": "Mantenimiento de Moto",
    # Hogar
    "alquiler": "Alquiler mensual",
    "arriendo": "Alquiler mensual",
    "renta": "Alquiler mensual",
    "luz": "Factura Luz mensual",
    "electricidad": "Factura Luz mensual",
    "cnel": "Factura Luz mensual",
    "agua": "Factura agua Mensual",
    "internet": "Factura internet mensual",
    "wifi": "Factura internet mensual",
    "plan": "Factura plan Mensual",
    "celular": "Factura plan Mensual",
    "mantenimiento": "Mantenimiento de Hogar",
    "isabel": "Pago a Limpieza",
    "señora isabel": "Pago a Limpieza",
    "limpieza": "Pago a Limpieza",
    "señora limpieza": "Pago a Limpieza",
    "crédito": "créditos y responsabilidades",
    "préstamo": "créditos y responsabilidades",
    # Salud/Bienestar
    "médico": "Gastos médicos",
    "doctor": "Gastos médicos",
    "farmacia": "Gastos médicos",
    "medicina": "Gastos médicos",
    "clínica": "Gastos médicos",
    "hospital": "Gastos médicos",
    "gym": "GYM mensual",
    "gimnasio": "GYM mensual",
    "higiene": "Higiene Personal",
    "proteínas": "Ahorros",
    "suplementos": "Ahorros",
    # Ocio
    "netflix": "Suscripciones ( Netflix etc.)",
    "spotify": "Suscripciones ( Netflix etc.)",
    "suscripción": "Suscripciones ( Netflix etc.)",
    "suscripciones": "Suscripciones ( Netflix etc.)",
    "salida": "Salidas y Ocio",
    "bar": "Salidas y Ocio",
    "fiesta": "Salidas y Ocio",
    "cervezas": "Salidas y Ocio",
    "trago": "Salidas y Ocio",
    "discoteca": "Salidas y Ocio",
    "vacaciones": "Vacaciones",
    "viaje": "Vacaciones",
    "ropa": "Compras ocasionales ( ropa )",
    "zapatos": "Compras ocasionales ( ropa )",
    "zapatillas": "Compras ocasionales ( ropa )",
    "regalo": "Regalos y propinas",
    "propina": "Regalos y propinas",
    # Trabajo/Inversiones
    "viático": "Viático",
    "reunión": "Viático",
    "trabajo": "Viático",
    "ahorro": "Ahorros",
    "ahorros": "Ahorros",
    "inversión": "Inversiones",
    "invertir": "Inversiones",
}

# Mapeo de palabras clave → categoría exacta de Notion (ingresos)
MAPEO_INGRESOS = {
    "comisión": "Comisiones por ventas.",
    "comisiones": "Comisiones por ventas.",
    "venta": "Comisiones por ventas.",
    "ventas": "Comisiones por ventas.",
    "neptuno": "Comisiones por ventas.",
    "agencia": "Ingresos pasivos || Agencia Neptuno",
    "pasivo": "Ingresos pasivos || Agencia Neptuno",
    "pasivos": "Ingresos pasivos || Agencia Neptuno",
    "60%": "Ingresos pasivos || Agencia Neptuno",
    "1xbet": "Referidos de 1xbet",
    "referido": "Referidos de 1xbet",
    "referidos": "Referidos de 1xbet",
    "aliado": "Comisiones Aliados Neptuno",
    "aliados": "Comisiones Aliados Neptuno",
    "50%": "Comisiones Aliados Neptuno",
    "comisiones aliados": "Comisiones Aliados Neptuno",
}

# Prompt base para el extractor de IA.
# Usa {categorias_gastos}, {categorias_ingresos} y {fecha_hoy} como placeholders.
# Los {{ }} del JSON de ejemplo se resuelven en la única llamada .format() de extractor.py.
EXTRACTION_PROMPT = """Eres un asistente financiero personal que extrae datos de transacciones.

CATEGORÍAS VÁLIDAS DE GASTOS (usa el texto exacto):
{categorias_gastos}

CATEGORÍAS VÁLIDAS DE INGRESOS (usa el texto exacto):
{categorias_ingresos}

REGLAS DE MAPEO:
- Restaurantes/comida/almuerzo/cena → "Restaurantes"
- Taxi/uber/cabify → "Taxis personales"
- Bus/metro/transporte público → "Transporte Público"
- Gasolina/combustible → "Gasolina para la Moto"
- Moto/mecánico/taller → "Mantenimiento de Moto"
- Alquiler/arriendo → "Alquiler mensual"
- Luz/electricidad → "Factura Luz mensual"
- Agua → "Factura agua Mensual"
- Internet/wifi → "Factura internet mensual"
- Mercado/supermercado/feria/víveres → "Compras de Alimentación"
- Delivery/rappi/uber eats → "Comida en Delivery"
- Netflix/spotify/suscripción → "Suscripciones ( Netflix etc.)"
- Gym/gimnasio → "GYM mensual"
- Médico/farmacia/medicina → "Gastos médicos"
- Ahorro → "Ahorros"
- Inversión/invertir → "Inversiones"
- Viático/reunión → "Viático"
- Ropa/zapatos → "Compras ocasionales ( ropa )"
- Salida/bar/fiesta/cervezas → "Salidas y Ocio"
- Propina/regalo → "Regalos y propinas"
- Comisión/venta/pro → "Comisiones por ventas."
- Agencia/pasivo/60% → "Ingresos pasivos || Agencia Neptuno"
- 1xbet/referido → "Referidos de 1xbet"
- Aliado/aliados/50%/Comisiones aliados Neptuno → "Comisiones Aliados Neptuno"

REGLAS ESPECIALES (tienen PRIORIDAD absoluta sobre las reglas anteriores):
- "señora isabel" / "isabel" / "limpieza" / "señora limpieza" / "pago limpieza"
  → categoria_notion="Pago a Limpieza", tipo=gasto, descripcion="pago señora isabel limpieza"
- "ahorro casa" / "entrada casa" / "nueva casa" / "casa propia" / "para la casa"
  → categoria_notion="Ahorros", tipo=gasto, descripcion="ahorro para entrada de casa"
- "ahorro playa" / "viaje playa" / "playa amigos" / "viaje a la playa" / "playa con amigos"
  → categoria_notion="Ahorros", tipo=gasto, descripcion="ahorro viaje playa amigos"
- "proteína" / "proteinas" / "ahorro proteína" / "ahorro entrenamiento"
  → categoria_notion="Ahorros", tipo=gasto, descripcion="ahorro proteínas entrenamiento"
- "compras y deseos" / "compras o deseos" / "ahorro deseos" / "ahorro compras" / "para compras y deseos" / "para compras o deseos"
  → categoria_notion="Ahorros", tipo=gasto, descripcion="ahorro compras y deseos"
- "colchón financiero" / "colchon financiero" / "ahorro colchón" / "ahorro colchon" / "fondo de emergencia"
  → categoria_notion="Ahorros", tipo=gasto, descripcion="ahorro colchón financiero"

REGLAS DE FECHA (PRIORIDAD ABSOLUTA):
- La fecha de hoy es {fecha_hoy}
- Si el usuario menciona una fecha, usa ESA fecha — NUNCA uses {fecha_hoy} en ese caso
- "ayer" → un día antes de {fecha_hoy}
- "anteayer" / "antes de ayer" → dos días antes de {fecha_hoy}
- "el [N] de [mes]" / "[N] de [mes]" / "[N] [mes]" → ese día del año actual (ej: "el 15 de mayo" → {anio_hoy}-05-15)
- "el [N]" / "el día [N]" → día N del mes de {fecha_hoy}
- "el lunes/martes/miércoles/jueves/viernes/sábado/domingo" → el día más reciente de esa semana
- Si NO hay fecha explícita → usa {fecha_hoy}

INSTRUCCIONES:
1. Extrae TODAS las transacciones visibles (puede ser una lista de Monefy o texto libre).
2. Para cada transacción determina si es gasto o ingreso.
3. Asigna la categoría_notion usando EXACTAMENTE uno de los valores de las listas de arriba.
4. Aplica las REGLAS DE FECHA de arriba para cada transacción.
5. Confianza "alta" = categoría obvia. "media" = dudoso. "baja" = muy ambiguo.

Devuelve ÚNICAMENTE este JSON (sin markdown, sin texto extra):
{{
  "transacciones": [
    {{
      "tipo": "gasto",
      "monto": 14.00,
      "moneda": "USD",
      "descripcion": "descripción breve",
      "categoria_notion": "nombre EXACTO del select",
      "fecha": "YYYY-MM-DD",
      "confianza": "alta",
      "notas": ""
    }}
  ]
}}
"""
