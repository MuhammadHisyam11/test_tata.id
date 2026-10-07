"""Fuzz test (audit putaran 3): project acak tidak boleh membuat rule engine crash atau menghasilkan
finding yang tidak bisa dipertanggungjawabkan. Seed tetap supaya hasil bisa diulang."""

import random
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase

from monitor import assess

WIB = ZoneInfo("Asia/Jakarta")
AS_OF = datetime(2026, 10, 6, 17, 0, tzinfo=WIB)
UNITS = ["ML", "pages", "boxes", "records", "endpoints", "system"]
RECORD_KINDS = {
    "production_snapshot": lambda rnd, unit: {assess.OBSERVED_FIELD.get(unit, "verified_quantity"):
                                              rnd.choice([0, 1, 50, 300, 130000]), "unit": rnd.choice([unit, unit, "boxes"])},
    "scanner_status": lambda rnd, unit: {"scanners": [{"scanner_id": "SCN-A",
                                                       "status": rnd.choice(["RUNNING", "LIMITED", "OUT_OF_SERVICE"])}]},
    "environment_check": lambda rnd, unit: {"environment": "production", "last_successful_connection": None,
                                            "connection_status": rnd.choice(["NOT_CONFIGURED", "CONNECTED"])},
    "integration_snapshot": lambda rnd, unit: {"developed_endpoints": rnd.randint(0, 10), "configured_endpoints": 3,
                                               "production_tested_endpoints": rnd.randint(0, 10), "target_endpoints": 10},
    "usage_snapshot": lambda rnd, unit: {"application_status": rnd.choice(["ONLINE", "OFFLINE"]), "active_users_last_24h": 3,
                                         "successful_logins_last_24h": rnd.randint(0, 30), "failed_logins_last_24h": rnd.randint(0, 30)},
    "verification_quality_snapshot": lambda rnd, unit: {"records_skipped_missing_region": rnd.randint(0, 5000)},
}


def random_project(rnd, i):
    maybe = lambda v: None if rnd.random() < 0.15 else v  # noqa: E731 — field kosong seperti CSV
    unit = rnd.choice(UNITS)
    start = date(2026, rnd.randint(6, 10), rnd.randint(1, 28))
    p = {"project_id": f"F{i}", "pic": "X", "start_date": start, "deadline": start + timedelta(days=rnd.randint(-5, 120)),
         "target": maybe(float(rnd.choice([0, 1, 10, 400, 120000]))), "target_unit": unit,
         "reported_actual": maybe(float(rnd.randint(0, 130000))), "reported_progress_pct": maybe(rnd.uniform(0, 120)),
         "reported_status": rnd.choice(["ON TRACK", "COMPLETED", "AT RISK", ""]),
         "last_reported_update_at": maybe(AS_OF - timedelta(days=rnd.randint(0, 20)))}
    records = []
    for j in range(rnd.randint(0, 4)):
        kind = rnd.choice(list(RECORD_KINDS))
        records.append({"source_record_id": f"R{i}-{j}", "record_type": kind, "source_system": "s",
                        "timestamp": AS_OF - timedelta(hours=rnd.randint(0, 24 * 60)), "payload": RECORD_KINDS[kind](rnd, unit)})
    updates = [{"update_id": f"U{i}-{k}", "timestamp": AS_OF - timedelta(days=k), "source_type": "OPERATOR", "source_name": "Op",
                "message": rnd.choice(["ok", "Box di hold", "scanner error", "belum ada kendala", "4.500 halaman per hari"])}
               for k in range(rnd.randint(0, 3))]
    return p, updates, records


class FuzzTests(SimpleTestCase):
    def test_random_projects_keep_invariants(self):
        rnd = random.Random(42)
        for i in range(500):
            p, updates, records = random_project(rnd, i)
            with self.subTest(i=i):
                metrics, findings = assess.assess_project(p, updates, records, AS_OF)  # tidak boleh crash
                self.assertIn(metrics["attention"], assess.ATTENTION_RANK)
                known = {r["source_record_id"] for r in records} | {u["update_id"] for u in updates} | {p["project_id"]}
                for f in findings:
                    self.assertIn(f.rule, assess.RULE_ORDER)
                    self.assertTrue(f.summary)
                    self.assertNotIn("None", f.summary)
                    self.assertTrue(f.evidence)
                    self.assertTrue({e["ref_id"] for e in f.evidence} <= known)
                concl = assess.conclusion(metrics["attention"], findings)  # tidak boleh crash
                self.assertTrue(concl["text"])
                self.assertNotIn("None", concl["text"] + concl["first_step"])
                obs, target = metrics["observed_actual"], p["target"]
                if p["reported_status"] == "COMPLETED" and obs is not None and target and obs < target * 0.95:
                    # Klaim "selesai" padahal data sistem jauh di bawah target tidak boleh berstatus "Aman".
                    self.assertEqual(metrics["attention"], "HIGH")
                late = metrics["forecast_delay_days"] is not None and metrics["forecast_delay_days"] > 0
                if late and p["reported_status"] != "COMPLETED":
                    # Kolom "N hari terlambat" tidak boleh berdampingan dengan status "Aman":
                    # selalu ada temuan jadwal (PACE_RISK, atau OVERDUE jika deadline sudah lewat).
                    self.assertTrue({"PACE_RISK", "OVERDUE"} & {f.rule for f in findings})
                    self.assertNotEqual(metrics["attention"], "OK")
