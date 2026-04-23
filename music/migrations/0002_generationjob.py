from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("music", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="GenerationJob",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("task_id", models.CharField(blank=True, max_length=255)),
                ("strategy", models.CharField(max_length=20)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("TEXT_SUCCESS", "Text Success"),
                            ("FIRST_SUCCESS", "First Success"),
                            ("SUCCESS", "Success"),
                            ("FAILED", "Failed"),
                        ],
                        default="PENDING",
                        max_length=20,
                    ),
                ),
                ("audio_url", models.URLField(blank=True, max_length=2048)),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "song",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="generation_job",
                        to="music.song",
                    ),
                ),
            ],
            options={
                "verbose_name": "Generation Job",
                "verbose_name_plural": "Generation Jobs",
            },
        ),
    ]
