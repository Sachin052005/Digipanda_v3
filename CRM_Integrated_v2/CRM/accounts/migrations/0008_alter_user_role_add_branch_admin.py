# Generated for TECHPANDA CRM Branch Admin role addition

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_alter_user_managers_alter_user_role'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(
                choices=[
                    ('SUPERADMIN', 'Superadmin'),
                    ('ADMIN', 'Admin'),
                    ('SALES_HEAD', 'Sales Head'),
                    ('BRANCH_HEAD', 'Branch Head'),
                    ('BRANCH_ADMIN', 'Branch Admin'),
                    ('COUNSELOR', 'Counselor'),
                    ('TELECALLER', 'Telecaller'),
                    ('RECEPTIONIST', 'Receptionist'),
                    ('ACCOUNTANT', 'Accountant'),
                ],
                default='TELECALLER',
                help_text='Application access role',
                max_length=20,
            ),
        ),
    ]
