path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\static\css\design-system.css"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

idx = text.find(".brand-logo-light")
if idx != -1:
    print("Found at index:", idx)
    print("Exact snippet:")
    print(repr(text[idx:idx+350]))
