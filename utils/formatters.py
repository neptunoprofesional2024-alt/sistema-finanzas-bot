from datetime import datetime


def format_currency(amount: float) -> str:
    return f"${amount:,.2f}"


def format_date(date_str: str) -> str:
    """Convierte YYYY-MM-DD a formato legible: '18 mayo 2026'."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        meses = {
            1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
            5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
            9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
        }
        return f"{dt.day} {meses[dt.month]} {dt.year}"
    except ValueError:
        return date_str


def format_percentage(part: float, total: float) -> str:
    if total <= 0:
        return "0%"
    pct = (part / total) * 100
    return f"{pct:.1f}%"
