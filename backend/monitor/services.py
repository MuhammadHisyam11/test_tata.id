from collections import defaultdict

from django.forms.models import model_to_dict
from django.utils.timezone import localtime

from . import assess
from .models import Finding, ProductionRecord, Project, ProjectMetrics, ProjectUpdate

METRIC_FIELDS = {f.name for f in ProjectMetrics._meta.fields} - {"project"}


def _local(d):
    # ORM mengembalikan datetime UTC; assess.py butuh waktu lokal agar "00:00 tanggal mulai" benar.
    return localtime(d) if d else None


def load_inputs():
    """Raw layer -> dict per project untuk assess.py (tanpa ORM)."""
    updates, records = defaultdict(list), defaultdict(list)
    for u in ProjectUpdate.objects.all():
        updates[u.project_id].append({**model_to_dict(u), "timestamp": _local(u.timestamp)})
    for r in ProductionRecord.objects.all():
        records[r.project_id].append({**model_to_dict(r), "timestamp": _local(r.timestamp)})
    projects = [
        {**model_to_dict(p), "last_reported_update_at": _local(p.last_reported_update_at)}
        for p in Project.objects.order_by("project_id")
    ]
    return projects, updates, records


def run_assessment(as_of):
    """Bangun ulang derived layer dari raw layer. Mengembalikan baris ringkasan untuk dicetak."""
    Finding.objects.all().delete()
    ProjectMetrics.objects.all().delete()

    projects, updates, records = load_inputs()
    as_of = _local(as_of)
    rows = []
    for p in projects:
        pid = p["project_id"]
        metrics, findings = assess.assess_project(p, updates[pid], records[pid], as_of)
        ProjectMetrics.objects.create(project_id=pid, **{k: v for k, v in metrics.items() if k in METRIC_FIELDS})
        Finding.objects.bulk_create(Finding(project_id=pid, **f.to_dict()) for f in findings)
        n_high = sum(f.severity == "HIGH" for f in findings)
        rows.append((assess.sort_key(metrics["attention"], n_high, metrics["days_remaining"]), pid, metrics, findings))

    lines = [f"{'PROJECT':<8} {'ATTENTION':<9} {'PACE':>5}  FINDINGS"]
    for _, pid, m, fs in sorted(rows, key=lambda r: r[0]):
        pace = f"{m['pace_ratio']:.2f}" if m["pace_ratio"] is not None else "-"
        lines.append(f"{pid:<8} {m['attention']:<9} {pace:>5}  " + ", ".join(f"{f.rule}[{f.severity[0]}]" for f in fs))
    return lines
