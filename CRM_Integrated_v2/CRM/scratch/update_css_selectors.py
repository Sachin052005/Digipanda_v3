path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\static\css\design-system.css"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

target = """.brand-logo-light {

  display: inline-block !important;

}

.brand-logo-dark {

  display: none !important;

}

[data-theme="dark"] .brand-logo-light {

  display: none !important;

}

[data-theme="dark"] .brand-logo-dark {

  display: inline-block !important;

}"""

replacement = """.brand-logo-light {

  display: inline-block !important;

}

.brand-logo-dark {

  display: none !important;

}

[data-theme="dark"] .brand-logo-light,
.dark-theme .brand-logo-light {

  display: none !important;

}

[data-theme="dark"] .brand-logo-dark,
.dark-theme .brand-logo-dark {

  display: inline-block !important;

}"""

if target in text:
    text = text.replace(target, replacement, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print("CSS updated successfully!")
else:
    print("Target not found!")
