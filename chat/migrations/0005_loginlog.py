# Generated migration for LoginLog model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('chat', '0004_feedback_user_name_user_email'),
    ]

    operations = [
        migrations.CreateModel(
            name='LoginLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ip_address', models.GenericIPAddressField(blank=True, db_column='IPaddr', null=True)),
                ('user_agent', models.TextField(blank=True)),
                ('device_id', models.CharField(blank=True, db_column='MAC', max_length=255)),
                ('logged_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='login_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Login Log',
                'verbose_name_plural': 'Login Logs',
                'ordering': ['-logged_at'],
            },
        ),
    ]
