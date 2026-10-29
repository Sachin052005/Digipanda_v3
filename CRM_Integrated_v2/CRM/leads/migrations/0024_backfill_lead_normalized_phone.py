import re
from django.db import migrations


def backfill_lead_normalized_phone(apps, schema_editor):
    Lead = apps.get_model('leads', 'Lead')
    for lead in Lead.objects.all().iterator(chunk_size=1000):
        raw = str(lead.phone or '').strip()
        if not raw or raw.startswith('NoPhone-'):
            if lead.normalized_phone != '':
                lead.normalized_phone = ''
                lead.save(update_fields=['normalized_phone'])
            continue
        digits = re.sub(r'\D', '', raw)
        if len(digits) == 12 and digits.startswith('91'):
            digits = digits[2:]
        elif len(digits) == 11 and digits.startswith('0'):
            digits = digits[1:]
        clean_10 = digits[-10:] if len(digits) >= 10 else digits
        if lead.normalized_phone != clean_10:
            lead.normalized_phone = clean_10
            lead.save(update_fields=['normalized_phone'])


def reverse_backfill(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0023_lead_normalized_phone'),
    ]

    operations = [
        migrations.RunPython(backfill_lead_normalized_phone, reverse_backfill),
    ]
