import sys
sys.path.insert(0, 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM')
from leads.utils_currency import amount_to_inr_words

tests = [
    (41300, "Forty One Thousand Three Hundred Rupees Only"),
    (0, "Zero Rupees Only"),
    (0.50, "Fifty Paise Only"),
    (105000.50, "One Lakh Five Thousand Rupees And Fifty Paise Only"),
    (2500000, "Twenty Five Lakh Rupees Only"),
    (10000000, "One Crore Rupees Only"),
    (12345678, "One Crore Twenty Three Lakh Forty Five Thousand Six Hundred Seventy Eight Rupees Only"),
    (100, "One Hundred Rupees Only"),
    (5, "Five Rupees Only"),
]

all_passed = True
for val, expected in tests:
    actual = amount_to_inr_words(val)
    if actual != expected:
        print(f"FAILED for {val}: got '{actual}', expected '{expected}'")
        all_passed = False
    else:
        print(f"PASS: {val} -> {actual}")

if all_passed:
    print("ALL CURRENCY CONVERTER TESTS PASSED!")
