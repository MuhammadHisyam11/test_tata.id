from django.db import models

# ---------- RAW LAYER: 1:1 dengan file sumber, tidak pernah "dibersihkan" ----------


class Project(models.Model):
    project_id = models.CharField(primary_key=True, max_length=20)
    customer = models.CharField(max_length=200)
    project_name = models.CharField(max_length=200)
    project_type = models.CharField(max_length=100)
    pic = models.CharField(max_length=100)
    start_date = models.DateField()
    deadline = models.DateField()
    target = models.FloatField(null=True)
    target_unit = models.CharField(max_length=20)
    reported_actual = models.FloatField(null=True)
    reported_progress_pct = models.FloatField(null=True)
    reported_status = models.CharField(max_length=30)
    last_reported_update_at = models.DateTimeField(null=True)

    def __str__(self):
        return f"{self.project_id} · {self.project_name}"


class ProjectUpdate(models.Model):
    update_id = models.CharField(primary_key=True, max_length=20)
    # Bukan FK: update yang merujuk project tak dikenal tetap disimpan (lihat Tech Spec §4).
    project_id = models.CharField(max_length=20, db_index=True)
    timestamp = models.DateTimeField()
    source_type = models.CharField(max_length=30)
    source_name = models.CharField(max_length=100)
    message = models.TextField()

    class Meta:
        ordering = ["timestamp"]


class ProductionRecord(models.Model):
    source_record_id = models.CharField(primary_key=True, max_length=40)
    project_id = models.CharField(max_length=20, db_index=True)
    source_system = models.CharField(max_length=50)
    record_type = models.CharField(max_length=50)
    timestamp = models.DateTimeField()
    payload = models.JSONField()  # record asli lengkap; field berbeda per record_type

    class Meta:
        ordering = ["timestamp"]


# ---------- DERIVED LAYER: dihapus & dihitung ulang setiap ingest ----------


class ProjectMetrics(models.Model):
    project = models.OneToOneField(Project, primary_key=True, on_delete=models.CASCADE, related_name="metrics")
    as_of = models.DateTimeField()
    computed_pct = models.FloatField(null=True)
    observed_actual = models.FloatField(null=True)
    observed_at = models.DateTimeField(null=True)
    observed_source_id = models.CharField(max_length=40, null=True)
    observed_pct = models.FloatField(null=True)
    days_remaining = models.IntegerField(null=True)
    historical_rate = models.FloatField(null=True)
    required_rate = models.FloatField(null=True)
    pace_ratio = models.FloatField(null=True)
    stated_capacity = models.FloatField(null=True)
    forecast_finish = models.DateTimeField(null=True)  # snapshot + sisa pekerjaan / laju historis
    forecast_delay_days = models.IntegerField(null=True)  # tanggal perkiraan - tanggal deadline (+ = terlambat)
    last_activity_at = models.DateTimeField(null=True)
    attention = models.CharField(max_length=10)


class Finding(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="findings")
    rule = models.CharField(max_length=40)
    severity = models.CharField(max_length=10)
    category = models.CharField(max_length=20)
    summary = models.TextField(default="")  # satu kalimat bahasa awam untuk management
    explanation = models.TextField()  # detail teknis: angka, field, timestamp
    verify = models.TextField(blank=True)
    follow_up = models.TextField(blank=True)
    evidence = models.JSONField()  # [{"ref_type": "master|update|production", "ref_id": "..."}]
