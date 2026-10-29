from reportlab.pdfgen import canvas
import inspect

c = canvas.Canvas("dummy.pdf")
print(inspect.getsource(c.drawImage))
