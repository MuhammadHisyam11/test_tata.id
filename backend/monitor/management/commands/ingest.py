import csv
import json
from datetime import date, datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, transaction
from django.utils.timezone import make_aware

from monitor.models import ProductionRecord, Project, ProjectUpdate
from monitor.services import run_assessment

MASTER = "02_Project_Master.csv"
UPDATES = "03_Project_Updates.csv"
PRODUCTION = "04_Production_Data.json"


def blank(v):
    """CSV empty value -> None (Data Dictionary: field boleh kosong)."""
    v = (v or "").strip()
    return v or None


def num(v):
    v = blank(v)
    return float(v) if v is not None else None


def dt(v):
    """Timestamp sumber tidak punya zona waktu -> diasumsikan Asia/Jakarta (TIME_ZONE)."""
    v = blank(v)
    if not v:
        return None
    parsed = datetime.fromisoformat(v)
    return parsed if parsed.tzinfo else make_aware(parsed)


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class Command(BaseCommand):
    help = "Import file sumber ke raw tables, lalu bangun ulang hasil assessment."

    def add_arguments(self, parser):
        parser.add_argument("--data-dir", type=Path, default=settings.DATA_DIR)

    def handle(self, *args, data_dir, **options):
        data_dir = Path(data_dir)  # call_command() tidak melewati konversi argparse
        try:
            master = read_csv(data_dir / MASTER)
            updates = read_csv(data_dir / UPDATES)
            production = json.loads((data_dir / PRODUCTION).read_text(encoding="utf-8"))
            records = production["records"]
            as_of = dt(production["generated_at"])
        except (OSError, KeyError, ValueError) as e:
            raise CommandError(f"Gagal membaca data dari {data_dir}: {e}")

        # Semua-atau-tidak-sama-sekali: data lama tetap utuh bila ada yang gagal.
        try:
            summary = self._load(master, updates, records, as_of)
        except (KeyError, ValueError, TypeError, DatabaseError) as e:
            raise CommandError(f"Data sumber tidak valid, tidak ada yang diubah: {type(e).__name__}: {e}")

        for name, rows in ((MASTER, master), (UPDATES, updates), (PRODUCTION, records)):
            if not rows:
                self.stderr.write(f"WARNING: {name} tidak berisi data — pastikan file yang benar sudah diekspor.")

        known = {r["project_id"] for r in master}
        for kind, rows in (("update", updates), ("production", records)):
            for r in rows:
                if r["project_id"] not in known:
                    self.stderr.write(f"WARNING: {kind} {r.get('update_id') or r.get('source_record_id')} "
                                      f"merujuk project tak dikenal {r['project_id']}")

        self.stdout.write(self.style.SUCCESS(
            f"Ingest OK (as_of {as_of:%Y-%m-%d %H:%M}): {len(master)} projects, "
            f"{len(updates)} updates, {len(records)} production records"
        ))
        for line in summary:
            self.stdout.write(line)

    @transaction.atomic
    def _load(self, master, updates, records, as_of):
        ProjectUpdate.objects.all().delete()
        ProductionRecord.objects.all().delete()
        Project.objects.all().delete()  # cascade ke derived layer

        Project.objects.bulk_create(
            Project(
                project_id=r["project_id"],
                customer=r["customer"],
                project_name=r["project_name"],
                project_type=r["project_type"],
                pic=r["pic"],
                start_date=date.fromisoformat(r["start_date"]),
                deadline=date.fromisoformat(r["deadline"]),
                target=num(r["target"]),
                target_unit=r["target_unit"],
                reported_actual=num(r["reported_actual"]),
                reported_progress_pct=num(r["reported_progress_pct"]),
                reported_status=r["reported_status"],
                last_reported_update_at=dt(r["last_reported_update_at"]),
            )
            for r in master
        )
        ProjectUpdate.objects.bulk_create(
            ProjectUpdate(
                update_id=r["update_id"],
                project_id=r["project_id"],
                timestamp=dt(r["timestamp"]),
                source_type=r["source_type"],
                source_name=r["source_name"],
                message=r["message"],
            )
            for r in updates
        )
        ProductionRecord.objects.bulk_create(
            ProductionRecord(
                source_record_id=r["source_record_id"],
                project_id=r["project_id"],
                source_system=r["source_system"],
                record_type=r["record_type"],
                timestamp=dt(r["timestamp"]),
                payload=r,
            )
            for r in records
        )
        return run_assessment(as_of)
