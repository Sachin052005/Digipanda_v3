"""
Pure-Python Indian Currency Number-to-Words Converter for TechPanda CRM.
Converts numerical INR values into formal Indian English currency words (e.g. Crores, Lakhs, Thousands, Hundreds, Rupees, Paise).
Zero external dependencies.
"""

from decimal import Decimal, ROUND_HALF_UP

_ONES = [
    "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
    "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
    "Seventeen", "Eighteen", "Nineteen"
]

_TENS = [
    "", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"
]


def _two_digits_to_words(n: int) -> str:
    """Convert an integer 0 <= n < 100 to words."""
    if n < 20:
        return _ONES[n]
    ten = _TENS[n // 10]
    one = _ONES[n % 10]
    return f"{ten} {one}".strip() if one else ten


def _three_digits_to_words(n: int) -> str:
    """Convert an integer 0 <= n < 1000 to words."""
    hundred = n // 100
    rem = n % 100
    words = []
    if hundred > 0:
        words.append(f"{_ONES[hundred]} Hundred")
    if rem > 0:
        words.append(_two_digits_to_words(rem))
    return " ".join(words)


def _integer_to_inr_words(n: int) -> str:
    """
    Convert non-negative integer to Indian numbering format words:
    Crore (1,00,00,000), Lakh (1,00,000), Thousand (1,000), Hundred (100).
    """
    if n == 0:
        return "Zero"

    parts = []

    # Crores (10^7)
    crores = n // 10_000_000
    n %= 10_000_000
    if crores > 0:
        parts.append(f"{_integer_to_inr_words(crores)} Crore")

    # Lakhs (10^5)
    lakhs = n // 100_000
    n %= 100_000
    if lakhs > 0:
        parts.append(f"{_two_digits_to_words(lakhs)} Lakh")

    # Thousands (10^3)
    thousands = n // 1_000
    n %= 1_000
    if thousands > 0:
        parts.append(f"{_two_digits_to_words(thousands)} Thousand")

    # Hundreds and remainder
    if n > 0:
        parts.append(_three_digits_to_words(n))

    return " ".join(parts).strip()


def amount_to_inr_words(amount) -> str:
    """
    Convert an amount (float, int, Decimal, or str) into formal Indian currency words.
    
    Examples:
        41300      -> "Forty One Thousand Three Hundred Rupees Only"
        41300.50   -> "Forty One Thousand Three Hundred Rupees And Fifty Paise Only"
        0          -> "Zero Rupees Only"
        0.75       -> "Seventy Five Paise Only"
        105000     -> "One Lakh Five Thousand Rupees Only"
    """
    if amount is None or amount == "":
        return "Zero Rupees Only"

    try:
        dec = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return "Zero Rupees Only"

    if dec < 0:
        prefix = "Minus "
        dec = abs(dec)
    else:
        prefix = ""

    rupees = int(dec)
    paise = int((dec - Decimal(rupees)) * 100)

    rupee_words = _integer_to_inr_words(rupees) if rupees > 0 else ("Zero" if paise == 0 else "")
    paise_words = _two_digits_to_words(paise) if paise > 0 else ""

    result = []
    if rupee_words:
        result.append(f"{rupee_words} Rupees")

    if paise_words:
        if rupee_words:
            result.append(f"And {paise_words} Paise")
        else:
            result.append(f"{paise_words} Paise")

    final_str = f"{prefix}{' '.join(result)} Only".strip()
    return " ".join(final_str.split())
