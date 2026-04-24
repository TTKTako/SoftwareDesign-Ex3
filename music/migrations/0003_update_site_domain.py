"""
Data migration: update the Django Sites framework Site #1 domain from the
default 'example.com' to '127.0.0.1:8000'.

allauth uses request.build_absolute_uri() for the OAuth redirect_uri, so the
Sites domain does not control what is sent to Google. However, updating it
keeps the admin panel and any Sites-aware code consistent with the actual
development host.

This migration only runs the update if the domain is still the default
('example.com'), so it is safe to run against a database that has already
been customised.
"""
from django.db import migrations


def set_dev_site_domain(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    # Only update the placeholder default — don't clobber a custom domain.
    Site.objects.filter(id=1, domain="example.com").update(
        domain="127.0.0.1:8000",
        name="Cithara",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("music", "0002_generationjob"),
        ("sites", "0002_alter_domain_unique"),
    ]

    operations = [
        migrations.RunPython(set_dev_site_domain, migrations.RunPython.noop),
    ]
