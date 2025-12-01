from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0003_review'),
    ]

    operations = [
        migrations.CreateModel(
            name='CounsellorAvailability',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('start_time', models.TimeField()),
                ('end_time', models.TimeField()),
                ('duration_minutes', models.PositiveIntegerField(default=45)),
                ('is_booked', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('counsellor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='availability_slots', to='accounts.counsellor')),
            ],
            options={
                'ordering': ['date', 'start_time'],
            },
        ),
        migrations.AddIndex(
            model_name='counselloravailability',
            index=models.Index(fields=['counsellor', 'date'], name='therapists_counsel_date_idx'),
        ),
        migrations.AddIndex(
            model_name='counselloravailability',
            index=models.Index(fields=['counsellor', 'is_booked'], name='therapists_counsel_booked_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='counselloravailability',
            unique_together={('counsellor', 'date', 'start_time')},
        ),
    ]

