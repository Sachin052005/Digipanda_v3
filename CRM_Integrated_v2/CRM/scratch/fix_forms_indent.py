import py_compile

path = r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\leads\forms.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.startswith('class Meta:'):
        new_lines.append('    class Meta:\n')
    else:
        new_lines.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

try:
    py_compile.compile(path, doraise=True)
    print("forms.py compiled successfully with 0 syntax/indent errors!")
except Exception as e:
    print("Compile error:", e)

