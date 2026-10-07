import re

from django.forms.models import model_to_dict
from django.http import JsonResponse
from django.utils.timezone import localtime
from django.views.decorators.http import require_GET

from . import assess
from .models import ProductionRecord, Project, ProjectUpdate

# Field umum production record; sisanya dianggap isi observasi untuk ringkasan timeline.
COMMON_FIELDS = {"source_record_id", "project_id", "source_system", "record_type", "timestamp"}
# ID project dari URL divalidasi dulu: karakter seperti NUL membuat Postgres error (500) alih-alih 404.
PROJECT_ID_RE = re.compile(r"[\w-]{1,20}")


def _local(d):
    return localtime(d) if d else None


def _findings(project):
    """Findings terurut severity (HIGH dulu), lalu RULE_ORDER — sama dengan assess.py."""
    return sorted(project.findings.all(), key=lambda f: assess.finding_order(f.severity, f.rule))


def _summarize_payload(payload):
    parts = []
    for key, val in payload.items():
        if key in COMMON_FIELDS:
            continue
        if key == "scanners":
            val = ", ".join(f"{s['scanner_id']} {s['status']}" for s in val)
        parts.append(f"{key}: {val}")
    return "; ".join(parts)


@require_GET
def project_list(request):
    rows = []
    for p in Project.objects.select_related("metrics").prefetch_related("findings"):
        m, findings = p.metrics, _findings(p)
        counts = {}
        for f in findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1
        rows.append({
            "project_id": p.project_id,
            "project_name": p.project_name,
            "customer": p.customer,
            "project_type": p.project_type,
            "pic": p.pic,
            "target_unit": p.target_unit,
            "is_active": p.reported_status != "COMPLETED",
            "deadline": p.deadline,
            "days_remaining": m.days_remaining,
            "reported_status": p.reported_status,
            "reported_pct": p.reported_progress_pct,
            "observed_pct": m.observed_pct,
            "forecast_finish": _local(m.forecast_finish),
            "forecast_delay_days": m.forecast_delay_days,
            "last_activity_at": _local(m.last_activity_at),
            "as_of": _local(m.as_of),
            "attention": m.attention,
            "finding_counts": counts,
            "headline": findings[0].summary if findings else "",  # kalimat awam temuan teratas
        })
    # project_id sebagai pemecah seri supaya urutan papan selalu sama.
    rows.sort(key=lambda r: (*assess.sort_key(r["attention"], r["finding_counts"].get("HIGH", 0), r["days_remaining"]),
                             r["project_id"]))
    return JsonResponse(rows, safe=False)


@require_GET
def project_detail(request, project_id):
    p = None
    if PROJECT_ID_RE.fullmatch(project_id):
        p = Project.objects.select_related("metrics").prefetch_related("findings").filter(pk=project_id).first()
    if p is None:
        return JsonResponse({"error": "not found"}, status=404)

    updates = list(ProjectUpdate.objects.filter(project_id=project_id))
    records = list(ProductionRecord.objects.filter(project_id=project_id))
    signals = assess.text_signals([{"update_id": u.update_id, "message": u.message} for u in updates])
    hints = {s["update_id"]: s["phrases"] for s in signals}
    by_update = {u.update_id: u for u in updates}

    timeline = [
        {"ts": _local(u.timestamp), "kind": "update", "ref_id": u.update_id,
         "source": f"{u.source_type} · {u.source_name}", "text": u.message,
         "hints": hints.get(u.update_id, []), "raw": {**model_to_dict(u), "timestamp": _local(u.timestamp)}}
        for u in updates
    ] + [
        {"ts": _local(r.timestamp), "kind": "production", "ref_id": r.source_record_id,
         "source": f"{r.source_system} · {r.record_type}", "text": _summarize_payload(r.payload),
         "hints": [], "raw": r.payload}
        for r in records
    ]
    timeline.sort(key=lambda t: (t["ts"], t["ref_id"]))

    integ = max((r for r in records if r.record_type == "integration_snapshot"), key=lambda r: r.timestamp, default=None)
    stages = []
    if integ:
        pl = integ.payload
        stages = [{"label": "developed", "value": pl.get("developed_endpoints")},
                  {"label": "configured", "value": pl.get("configured_endpoints")},
                  {"label": "production tested", "value": pl.get("production_tested_endpoints")},
                  {"label": "target", "value": pl.get("target_endpoints")}]

    findings = _findings(p)
    project = model_to_dict(p)
    project["last_reported_update_at"] = _local(p.last_reported_update_at)
    metrics = model_to_dict(p.metrics, exclude=["project"])
    for key in ("as_of", "observed_at", "last_activity_at", "forecast_finish"):
        metrics[key] = _local(getattr(p.metrics, key))

    return JsonResponse({
        "project": project,
        "metrics": metrics,
        "stages": stages,
        "conclusion": assess.conclusion(p.metrics.attention, findings),
        "findings": [model_to_dict(f, exclude=["project", "id"]) for f in findings],
        "signals": [{**s, "text": by_update[s["update_id"]].message} for s in signals],
        "timeline": timeline,
    })
