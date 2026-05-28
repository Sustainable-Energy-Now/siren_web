from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("siren_web", "0161_remove_monthlyreperformance_emissions_intensity_kg_mwh_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="facilities",
            name="ppa_status",
            field=models.CharField(
                blank=True,
                choices=[("none", "None"), ("hoa", "Heads of Agreement"), ("signed", "Signed")],
                default="none",
                help_text="Power Purchase Agreement status",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="facilities",
            name="ppa_counterparty",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Name of the PPA counterparty (e.g. Synergy, AGL)",
                max_length=100,
            ),
        ),
        migrations.AddField(
            model_name="facilities",
            name="fid_expected_date",
            field=models.DateField(
                blank=True,
                null=True,
                help_text="Expected Final Investment Decision date",
            ),
        ),
        migrations.AddField(
            model_name="facilities",
            name="epc_status",
            field=models.CharField(
                blank=True,
                choices=[("none", "Not Started"), ("progressing", "Progressing"), ("locked", "Locked")],
                default="none",
                help_text="EPC contract status: not started, in negotiation, or locked",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="facilities",
            name="developer_strength",
            field=models.CharField(
                blank=True,
                choices=[
                    ("weak", "Weak"),
                    ("moderate", "Moderate"),
                    ("strong", "Strong"),
                    ("very_strong", "Very Strong"),
                ],
                default="moderate",
                help_text="Developer's assessed financial strength and track record",
                max_length=15,
            ),
        ),
        migrations.AddField(
            model_name="facilities",
            name="revenue_stack",
            field=models.CharField(
                blank=True,
                choices=[
                    ("merchant", "Merchant"),
                    ("cis_merchant", "CIS + Merchant"),
                    ("ppa_cis", "PPA + CIS"),
                    ("ppa", "PPA"),
                    ("capacity", "Capacity-style"),
                ],
                default="merchant",
                help_text="Revenue certainty classification",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="facilities",
            name="community_fn_status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("unknown", "Unknown"),
                    ("typical", "Typical"),
                    ("active", "Active Engagement"),
                    ("opposition", "Known Opposition"),
                ],
                default="unknown",
                help_text="First Nations and community engagement status",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="facilities",
            name="portfolio_priority",
            field=models.CharField(
                blank=True,
                choices=[("low", "Low"), ("medium", "Medium"), ("high", "High")],
                default="medium",
                help_text="Developer's internal priority for this project",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="facilities",
            name="coal_retirement_alignment",
            field=models.CharField(
                blank=True,
                choices=[
                    ("none", "None"),
                    ("ok", "OK"),
                    ("good", "Good"),
                    ("strong", "Strong"),
                    ("critical", "Critical"),
                ],
                default="none",
                help_text="Strategic alignment with WA coal plant retirement schedule",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="facilities",
            name="tech_complexity",
            field=models.CharField(
                blank=True,
                choices=[
                    ("simple", "Simple (wind or solar)"),
                    ("moderate", "Moderate"),
                    ("hybrid", "Hybrid (wind+BESS or solar+BESS)"),
                    ("high", "High complexity"),
                ],
                default="simple",
                help_text="Execution risk tier of the technology configuration",
                max_length=10,
            ),
        ),
    ]
