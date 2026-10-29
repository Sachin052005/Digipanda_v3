import os

CRM_ROOT = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM"

# 1. templates/registration/login.html
login_html = os.path.join(CRM_ROOT, "templates", "registration", "login.html")
with open(login_html, "r", encoding="utf-8") as f:
    c = f.read()
c = c.replace("Username or Email", "Email Address")
c = c.replace('for="id_username"', 'for="id_email"')
c = c.replace("{{ form.username }}", "{{ form.email }}")
c = c.replace("Invalid username or password. Please try again.", "Invalid email address or password. Please try again.")
c = c.replace("Sign In - DigipandaCRM", "Sign In - DigiPanda CRM")
with open(login_html, "w", encoding="utf-8", newline="\n") as f:
    f.write(c)
print("Updated templates/registration/login.html")

# 2. templates/registration/admin_login.html
admin_login_html = os.path.join(CRM_ROOT, "templates", "registration", "admin_login.html")
with open(admin_login_html, "r", encoding="utf-8") as f:
    c = f.read()
c = c.replace("Admin Username", "Admin Email Address")
c = c.replace('for="id_username"', 'for="id_email"')
c = c.replace("{{ form.username }}", "{{ form.email }}")
c = c.replace("Admin Portal Login - DigipandaCRM", "Admin Portal Login - DigiPanda CRM")
with open(admin_login_html, "w", encoding="utf-8", newline="\n") as f:
    f.write(c)
print("Updated templates/registration/admin_login.html")

# 3. templates/registration/manager_login.html
manager_login_html = os.path.join(CRM_ROOT, "templates", "registration", "manager_login.html")
with open(manager_login_html, "r", encoding="utf-8") as f:
    c = f.read()
c = c.replace("Sales Head Username", "Sales Head Email Address")
c = c.replace('for="id_username"', 'for="id_email"')
c = c.replace("{{ form.username }}", "{{ form.email }}")
c = c.replace("Invalid username or password. Please verify your credentials.", "Invalid email address or password. Please verify your credentials.")
c = c.replace("Sales Head Portal - DigipandaCRM", "Sales Head Portal - DigiPanda CRM")
with open(manager_login_html, "w", encoding="utf-8", newline="\n") as f:
    f.write(c)
print("Updated templates/registration/manager_login.html")

# 4. templates/registration/telecaller_login.html
telecaller_login_html = os.path.join(CRM_ROOT, "templates", "registration", "telecaller_login.html")
with open(telecaller_login_html, "r", encoding="utf-8") as f:
    c = f.read()
c = c.replace("Telecaller Username", "Telecaller Email Address")
c = c.replace('for="id_username"', 'for="id_email"')
c = c.replace("{{ form.username }}", "{{ form.email }}")
c = c.replace("Please check your username and password", "Please check your email address and password")
c = c.replace("Telecaller Workspace - DigipandaCRM", "Telecaller Workspace - DigiPanda CRM")
with open(telecaller_login_html, "w", encoding="utf-8", newline="\n") as f:
    f.write(c)
print("Updated templates/registration/telecaller_login.html")

# 5. templates/finance/login.html
finance_login_html = os.path.join(CRM_ROOT, "templates", "finance", "login.html")
with open(finance_login_html, "r", encoding="utf-8") as f:
    c = f.read()
c = c.replace("Finance Portal Sign In - TechPanda CRM", "Finance Portal Sign In - DigiPanda CRM")
c = c.replace('alt="TechPanda CRM"', 'alt="DigiPanda CRM"')
c = c.replace("Username or Registered Email", "Email Address")
c = c.replace('for="id_username"', 'for="id_email"')
c = c.replace('name="username"', 'name="email"')
c = c.replace('id="id_username"', 'id="id_email"')
c = c.replace('type="text"', 'type="email"')
c = c.replace('placeholder="Enter username or email"', 'placeholder="Enter your email address"')
c = c.replace('autocomplete="username"', 'autocomplete="email"')
c = c.replace("Invalid username or password. Please verify your credentials.", "Invalid email address or password. Please verify your credentials.")
with open(finance_login_html, "w", encoding="utf-8", newline="\n") as f:
    f.write(c)
print("Updated templates/finance/login.html")
