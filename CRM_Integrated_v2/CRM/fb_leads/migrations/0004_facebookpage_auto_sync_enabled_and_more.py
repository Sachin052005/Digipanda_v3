# Generated for Django 5.1.15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fb_leads', '0003_facebookaccount_facebooklead_account_facebookpage_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='facebookpage',
            name='auto_sync_enabled',
            field=models.BooleanField(
                default=True,
                help_text='Automatically synchronize leads periodically from Facebook'
            ),
        ),
        migrations.AddField(
            model_name='facebookpage',
            name='sync_interval_minutes',
            field=models.PositiveIntegerField(
                choices=[
                    (1, '1 Minute'),
                    (3, '3 Minutes (Recommended)'),
                    (5, '5 Minutes'),
                    (10, '10 Minutes'),
                    (15, '15 Minutes'),
                    (30, '30 Minutes'),
                    (60, '1 Hour')
                ],
                default=3,
                help_text='Auto-sync interval in minutes'
            ),
        ),
        migrations.AddField(
            model_name='facebookpage',
            name='next_sync_at',
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text='Next scheduled auto-sync timestamp',
                null=True
            ),
        ),
    ]
