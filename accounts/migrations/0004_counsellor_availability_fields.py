from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_review'),
    ]

    operations = [
        migrations.AddField(
            model_name='counsellor',
            name='default_break_duration',
            field=models.PositiveIntegerField(default=5),
        ),
        migrations.AddField(
            model_name='counsellor',
            name='default_session_duration',
            field=models.PositiveIntegerField(default=45),
        ),
    ]

