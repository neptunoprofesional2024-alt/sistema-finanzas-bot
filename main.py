import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from config.settings import TELEGRAM_BOT_TOKEN
from bot.handlers import handle_text, handle_photo, handle_callback
from bot.commands import cmd_start, cmd_ayuda, cmd_balance, cmd_pendientes, cmd_ahorros, cmd_prioridades
from bot.scheduler import build_scheduler

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def _start_health_server() -> None:
    """Servidor HTTP mínimo para satisfacer el health-check de Railway ($PORT)."""
    port = int(os.getenv("PORT", 8080))

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")

        def log_message(self, *args):
            pass

    class _ReuseHTTPServer(HTTPServer):
        allow_reuse_address = True

    server = _ReuseHTTPServer(("0.0.0.0", port), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Health-check server escuchando en puerto {port}.")


async def _post_init(app: Application) -> None:
    scheduler = build_scheduler(app.bot)
    scheduler.start()
    app.bot_data["scheduler"] = scheduler
    logger.info("Scheduler iniciado — alertas diarias a las 9:30 AM (Ecuador).")


async def _post_shutdown(app: Application) -> None:
    scheduler = app.bot_data.get("scheduler")
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler detenido.")


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN no está definido en el .env")

    _start_health_server()

    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )

    # Comandos
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("ayuda", cmd_ayuda))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("pendientes", cmd_pendientes))
    app.add_handler(CommandHandler("ahorros", cmd_ahorros))
    app.add_handler(CommandHandler("prioridades", cmd_prioridades))

    # Mensajes de texto (excluye comandos)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Fotos (capturas de Monefy)
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Botones inline
    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info("Bot iniciado. Esperando mensajes...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
