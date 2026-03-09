from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('siren_web', '0153_celstagegridline_celstageterminal'),
    ]

    operations = [
        # GridLines: rename commissioned_date -> commissioning_date
        migrations.RenameField(
            model_name='gridlines',
            old_name='commissioned_date',
            new_name='commissioning_date',
        ),
        # GridLines: rename decommissioned_date -> decommissioning_date
        migrations.RenameField(
            model_name='gridlines',
            old_name='decommissioned_date',
            new_name='decommissioning_date',
        ),
        # GridLines: add status
        migrations.AddField(
            model_name='gridlines',
            name='status',
            field=models.CharField(
                choices=[
                    ('proposed', 'Proposed'),
                    ('planned', 'Planned'),
                    ('under_construction', 'Under Construction'),
                    ('commissioned', 'Commissioned'),
                    ('decommissioned', 'Decommissioned'),
                ],
                default='commissioned',
                help_text='Current lifecycle status of the grid line',
                max_length=20,
            ),
        ),
        # GridLines: add commissioning_probability
        migrations.AddField(
            model_name='gridlines',
            name='commissioning_probability',
            field=models.FloatField(
                blank=True,
                null=True,
                help_text='Probability of commissioning (0-1), relevant for proposed/planned lines',
                validators=[
                    django.core.validators.MinValueValidator(0.0),
                    django.core.validators.MaxValueValidator(1.0),
                ],
            ),
        ),
        # Terminals: rename commissioned_date -> commissioning_date
        migrations.RenameField(
            model_name='terminals',
            old_name='commissioned_date',
            new_name='commissioning_date',
        ),
        # Terminals: rename decommissioned_date -> decommissioning_date
        migrations.RenameField(
            model_name='terminals',
            old_name='decommissioned_date',
            new_name='decommissioning_date',
        ),
        # Terminals: add status
        migrations.AddField(
            model_name='terminals',
            name='status',
            field=models.CharField(
                choices=[
                    ('proposed', 'Proposed'),
                    ('planned', 'Planned'),
                    ('under_construction', 'Under Construction'),
                    ('commissioned', 'Commissioned'),
                    ('decommissioned', 'Decommissioned'),
                ],
                default='commissioned',
                help_text='Current lifecycle status of the terminal',
                max_length=20,
            ),
        ),
        # Terminals: add commissioning_probability
        migrations.AddField(
            model_name='terminals',
            name='commissioning_probability',
            field=models.FloatField(
                blank=True,
                null=True,
                help_text='Probability of commissioning (0-1), relevant for proposed/planned terminals',
                validators=[
                    django.core.validators.MinValueValidator(0.0),
                    django.core.validators.MaxValueValidator(1.0),
                ],
            ),
        ),
        # Terminals: remove operator
        migrations.RemoveField(
            model_name='terminals',
            name='operator',
        ),
        # Terminals: remove maintenance_zone
        migrations.RemoveField(
            model_name='terminals',
            name='maintenance_zone',
        ),
        # Terminals: remove control_center
        migrations.RemoveField(
            model_name='terminals',
            name='control_center',
        ),
    ]
