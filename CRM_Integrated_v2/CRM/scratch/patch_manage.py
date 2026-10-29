with open(r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\manage.py", "r", encoding="utf-8") as f:
    text = f.read()

target = "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')"
replacement = """extra_site = r"D:\\CRM_Integrated_v2\\CRM_Integrated_v2\\.venv\\Lib\\site-packages"
    if os.path.exists(extra_site) and extra_site not in sys.path:
        sys.path.insert(0, extra_site)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')"""

if target in text:
    text = text.replace(target, replacement, 1)
    with open(r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\manage.py", "w", encoding="utf-8") as f:
        f.write(text)
    print("Patched manage.py with extra site-packages!")
else:
    print("Target not found in manage.py")
