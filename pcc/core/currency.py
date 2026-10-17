"""Currency list and money formatting."""

CURRENCIES: list[tuple[str, str, str]] = [
    ("PHP", "₱", "Philippine Peso"),
    ("USD", "$", "US Dollar"),
    ("EUR", "€", "Euro"),
    ("GBP", "£", "British Pound"),
    ("JPY", "¥", "Japanese Yen"),
    ("AUD", "A$", "Australian Dollar"),
    ("CAD", "C$", "Canadian Dollar"),
    ("SGD", "S$", "Singapore Dollar"),
    ("INR", "₹", "Indian Rupee"),
    ("IDR", "Rp", "Indonesian Rupiah"),
    ("MYR", "RM", "Malaysian Ringgit"),
    ("THB", "฿", "Thai Baht"),
    ("KRW", "₩", "South Korean Won"),
    ("CNY", "¥", "Chinese Yuan"),
]


def format_money(amount: float, symbol: str) -> str:
    sign = "-" if round(amount, 2) < 0 else ""
    return f"{sign}{symbol}{abs(amount):,.2f}"


def excel_money_format(symbol: str) -> str:
    return f'"{symbol}"#,##0.00'
