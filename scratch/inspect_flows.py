import os, sys, json, django
sys.path.insert(0, r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.stdout.reconfigure(encoding='utf-8')
django.setup()

from chat.models import AutomationFlow, UserFlowSession, AutomationExecution

f11 = AutomationFlow.objects.filter(id=11).first()
if f11:
    print(f"\n=== FLOW 11 DETAILS ({f11.name}) ===")
    fd = f11.flow_data or {}
    print("NODES:")
    for n in fd.get('nodes', []):
        title = n.get('title')
        ntype = n.get('type')
        nid = n.get('id')
        opts = n.get('options') or n.get('data', {}).get('options')
        sections = n.get('sections') or n.get('data', {}).get('sections')
        print(f"  [{ntype}] ID: {nid} | Title: {title} | Options: {opts} | Sections: {sections}")
    
    print("\nCONNECTIONS:")
    for c in fd.get('connections', []):
        src = c.get('source') or c.get('from')
        sport = c.get('source_port') or c.get('port') or 'default'
        tgt = c.get('target') or c.get('to')
        print(f"  {src} [{sport}] ---> {tgt}")

    from chat.automation.validator import validate_flow_graph
    val_res = validate_flow_graph(fd)
    print(f"\nVALIDATION RESULT: Valid={val_res.get('valid')}")
    print(f"Errors: {val_res.get('errors')}")
    print(f"Warnings: {val_res.get('warnings')}")

print("\n=== RECENT SESSIONS ===")
sessions = UserFlowSession.objects.all().order_by('-updated_at')[:8]
for s in sessions:
    print(f"Session #{s.id} | Flow: {s.flow_id} | Node: {s.current_node_id} | Status: {s.status} | Data: {s.collected_data} | Updated: {s.updated_at}")
