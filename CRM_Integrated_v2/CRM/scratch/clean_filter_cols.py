import os

files = [
    r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\admin\calls_list.html',
    r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\admin\followups_list.html',
    r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\counselor\followups_list.html'
]

for p in files:
    if not os.path.exists(p):
        continue
    with open(p, 'r', encoding='utf-8') as f:
        c = f.read()
    c = c.replace('style="flex: 1 1 180px;"', 'style="flex: 0 0 auto; width: 220px;"')
    c = c.replace('style="min-width: 180px;"', 'style="flex: 0 0 auto; width: 220px;"')
    with open(p, 'w', encoding='utf-8') as f:
        f.write(c)
    print('Cleaned', p)
