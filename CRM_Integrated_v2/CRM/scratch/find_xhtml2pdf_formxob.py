import xhtml2pdf
import inspect
import os

print("xhtml2pdf path:", os.path.dirname(xhtml2pdf.__file__))

# Search for FormXob or hash in xhtml2pdf package
pkg_dir = os.path.dirname(xhtml2pdf.__file__)
for root, dirs, files in os.walk(pkg_dir):
    for f in files:
        if f.endswith('.py'):
            p = os.path.join(root, f)
            with open(p, 'r', encoding='utf-8', errors='ignore') as fh:
                txt = fh.read()
                if 'FormXob' in txt or 'getNamedImage' in txt:
                    print("Found in:", os.path.relpath(p, pkg_dir))
