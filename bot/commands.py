from telegram import Update
from telegram.ext import ContextTypes
from notion.queries import get_balance, get_pendientes, get_ahorros
from notion.priorities import get_top_prioridades, get_all_prioridades
from bot.responses import balance_mensaje, pendientes_mensaje, ahorros_mensaje, prioridades_mensaje, bienvenida, error_notion


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from bot.scheduler import save_chat_id
    save_chat_id(update.effective_chat.id)
    await update.message.reply_text(bienvenida(), parse_mode="Markdown")


async def cmd_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(bienvenida(), parse_mode="Markdown")


async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("⏳ Consultando Notion...")
    try:
        data = get_balance()
        await update.message.reply_text(balance_mensaje(data))
    except RuntimeError:
        await update.message.reply_text(error_notion())


async def cmd_pendientes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("⏳ Consultando pendientes...")
    try:
        pendientes = get_pendientes()
        await update.message.reply_text(pendientes_mensaje(pendientes))
    except RuntimeError:
        await update.message.reply_text(error_notion())


async def cmd_ahorros(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("⏳ Consultando ahorros...")
    try:
        ahorros = get_ahorros()
        await update.message.reply_text(ahorros_mensaje(ahorros))
    except RuntimeError:
        await update.message.reply_text(error_notion())


async def cmd_prioridades(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    todas = bool(context.args and context.args[0].lower() == "todas")
    await update.message.reply_text("⏳ Consultando prioridades...")
    try:
        if todas:
            prioridades = get_all_prioridades()
        else:
            prioridades = get_top_prioridades(3)
        await update.message.reply_text(prioridades_mensaje(prioridades, todas=todas), parse_mode="Markdown")
    except RuntimeError:
        await update.message.reply_text(error_notion())
