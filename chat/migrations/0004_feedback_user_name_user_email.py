# Generated migration to add user_name and user_email fields to Feedback

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0003_feedback'),
    ]

    operations = [
        migrations.AddField(
            model_name='feedback',
            name='user_name',
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name='feedback',
            name='user_email',
            field=models.EmailField(blank=True, max_length=254),
        ),
    ]
