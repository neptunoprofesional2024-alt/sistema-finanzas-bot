# Finanzas Bot

Bot de Telegram para gestión financiera personal integrado con Notion.

## Funcionalidades

- Registro de gastos e ingresos por texto o captura de Monefy (IA con GPT-4o Vision)
- Actualización automática en cascada: gastos detallados → proyecciones → ahorros → prioridades
- Prioridades financieras dinámicas con score de urgencia (fecha, monto, tipo)
- Alertas diarias a las 9:30 AM (hora Ecuador) con pagos próximos
- Comandos: `/balance`, `/pendientes`, `/ahorros`, `/prioridades`
- Lenguaje natural: "¿qué debo pagar?", "sugerencias de ahorro", "próximos pagos"

## Stack

- Python 3.11
- python-telegram-bot 20.7
- OpenAI GPT-4o (extracción de transacciones)
- Notion API (bases de datos financieras)
- APScheduler (alertas automáticas)

## Variables de entorno requeridas

```
TELEGRAM_BOT_TOKEN
OPENAI_API_KEY
NOTION_TOKEN
NOTION_INGRESOS_DB_ID
NOTION_GASTOS_DB_ID
NOTION_PROYECCIONES_GASTOS_DB_ID
NOTION_PROYECCIONES_INGRESOS_DB_ID
NOTION_AHORROS_DB_ID
NOTION_PRIORIDADES_DB_ID
```

## Despliegue

Configurado para Railway.app. Ver `Procfile` y `runtime.txt`.
