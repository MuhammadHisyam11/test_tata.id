"""Integration test: ingest dataset asli ke test DB, lalu cocokkan dengan expected output (Tech Spec §6)."""

import re
from io import StringIO

# Kalimat awam: tanpa nama rule/field (snake_case), ID (SCN-B, UPD-008), kode status (LIMITED),
# dan istilah teknis yang sudah diganti di Fase 8a (production -> "sistem customer", go-live -> "mulai dipakai").
JARGON = re.compile(r"\b[A-Za-z]+_[A-Za-z_]+\b|\b[A-Z]{2,}-[A-Z0-9]+|\b[A-Z]{4,}\b"
                    r"|\b(?i:production|go-live|environment|deployment|snapshot)\b")

from django.core.management import call_command
from django.test import TestCase
from django.utils.timezone import localtime

from monitor import assess
from monitor.models import Finding, ProductionRecord, Project, ProjectMetrics, ProjectUpdate

EXPECTED = {
    "PRJ-001": ("MEDIUM", {"REPORTED_VS_OBSERVED", "PACE_RISK"}),
    "PRJ-002": ("HIGH", {"PACE_RISK", "STATUS_CONTRADICTION", "REPORTED_VS_OBSERVED", "EQUIPMENT_DEGRADED"}),
    "PRJ-003": ("MEDIUM", {"PCT_INCONSISTENT", "STALE_REPORT"}),
    "PRJ-004": ("MEDIUM", {"PCT_INCONSISTENT", "PACE_RISK", "DATA_QUALITY_SKIP"}),
    "PRJ-005": ("HIGH", {"ENV_NOT_READY", "REPORTED_VS_OBSERVED", "DEADLINE_IMMINENT_BLOCKED",
                         "STATUS_CONTRADICTION", "SCOPE_GAP"}),
    "PRJ-006": ("OK", {"POST_GO_LIVE_HEALTH"}),
}

EXPECTED_SIGNALS = [
    {"update_id": "UPD-006", "phrases": ["belum dapat"]},
    {"update_id": "UPD-011", "phrases": ["dilewati"]},
    {"update_id": "UPD-012", "phrases": ["dicek kembali"]},
    {"update_id": "UPD-013", "phrases": ["error"]},
    {"update_id": "UPD-016", "phrases": ["menunggu"]},
    {"update_id": "UPD-017", "phrases": ["belum dapat"]},
    {"update_id": "UPD-019", "phrases": ["hold", "menunggu"]},
    {"update_id": "UPD-022", "phrases": ["terbatas"]},
]


class IngestDatasetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("ingest", stdout=StringIO())

    def test_raw_counts_and_idempotent(self):
        call_command("ingest", stdout=StringIO())  # dijalankan kedua kali
        self.assertEqual(Project.objects.count(), 6)
        self.assertEqual(ProjectUpdate.objects.count(), 23)
        self.assertEqual(ProductionRecord.objects.count(), 12)

    def test_attention_and_rules_per_project(self):
        for pid, (attention, rules) in EXPECTED.items():
            with self.subTest(pid):
                self.assertEqual(ProjectMetrics.objects.get(pk=pid).attention, attention)
                self.assertEqual(set(Finding.objects.filter(project_id=pid).values_list("rule", flat=True)), rules)

    def test_key_severities(self):
        sev = {(f.project_id, f.rule): f.severity for f in Finding.objects.all()}
        self.assertEqual(sev[("PRJ-002", "PACE_RISK")], "HIGH")
        self.assertEqual(sev[("PRJ-001", "PACE_RISK")], "MEDIUM")
        self.assertEqual(sev[("PRJ-005", "REPORTED_VS_OBSERVED")], "HIGH")
        self.assertEqual(sev[("PRJ-006", "POST_GO_LIVE_HEALTH")], "INFO")

    def test_every_finding_has_valid_evidence(self):
        valid = (
            {("master", pk) for pk in Project.objects.values_list("pk", flat=True)}
            | {("update", pk) for pk in ProjectUpdate.objects.values_list("pk", flat=True)}
            | {("production", pk) for pk in ProductionRecord.objects.values_list("pk", flat=True)}
        )
        for f in Finding.objects.all():
            with self.subTest(f"{f.project_id} {f.rule}"):
                self.assertTrue(f.evidence)
                for e in f.evidence:
                    self.assertIn((e["ref_type"], e["ref_id"]), valid)

    def test_pace_ratios(self):
        ratios = dict(ProjectMetrics.objects.values_list("project_id", "pace_ratio"))
        self.assertAlmostEqual(ratios["PRJ-001"], 1.108, places=3)
        self.assertAlmostEqual(ratios["PRJ-002"], 1.952, places=3)
        self.assertAlmostEqual(ratios["PRJ-004"], 1.405, places=3)
        self.assertIsNone(ratios["PRJ-005"])

    def test_invalid_source_data_fails_cleanly_and_keeps_old_data(self):
        import shutil, tempfile
        from django.conf import settings
        from django.core.management.base import CommandError
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("02_Project_Master.csv", "03_Project_Updates.csv", "04_Production_Data.json"):
                shutil.copy(settings.DATA_DIR / name, tmp)
            path = f"{tmp}/02_Project_Master.csv"
            text = open(path, encoding="utf-8").read().replace("2026-10-15", "15/10/2026")  # format tanggal salah
            open(path, "w", encoding="utf-8").write(text)
            with self.assertRaisesMessage(CommandError, "Data sumber tidak valid"):
                call_command("ingest", data_dir=tmp, stdout=StringIO())
        self.assertEqual(Project.objects.count(), 6)  # data lama utuh (transaksi di-rollback)
        self.assertEqual(Finding.objects.filter(project_id="PRJ-002").count(), 4)

    def test_text_signals_on_dataset(self):
        ups = [{"update_id": u.pk, "message": u.message} for u in ProjectUpdate.objects.order_by("update_id")]
        self.assertEqual(assess.text_signals(ups), EXPECTED_SIGNALS)


class ApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("ingest", stdout=StringIO())

    def test_list_order_and_shape(self):
        res = self.client.get("/api/projects")
        self.assertEqual(res.status_code, 200)
        rows = res.json()
        self.assertEqual([r["project_id"] for r in rows],
                         ["PRJ-005", "PRJ-002", "PRJ-001", "PRJ-003", "PRJ-004", "PRJ-006"])
        prj2 = rows[1]
        self.assertEqual(prj2["finding_counts"], {"HIGH": 2, "MEDIUM": 2})
        self.assertTrue(prj2["is_active"])
        self.assertFalse(rows[-1]["is_active"])
        self.assertIn("5 hari setelah deadline", prj2["headline"])  # headline = summary finding teratas (PACE_RISK)
        self.assertEqual(prj2["forecast_delay_days"], 5)
        self.assertTrue(prj2["forecast_finish"].startswith("2026-10-15"))

    def test_detail_shape(self):
        data = self.client.get("/api/projects/PRJ-005").json()
        self.assertEqual(set(data), {"project", "metrics", "stages", "conclusion", "findings", "signals", "timeline"})
        self.assertEqual([s["value"] for s in data["stages"]], [9, 9, 0, 10])
        self.assertEqual(data["findings"][0]["severity"], "HIGH")
        self.assertEqual({s["update_id"] for s in data["signals"]}, {"UPD-006", "UPD-016"})
        # timeline: 3 update (UPD-006, 010, 016) + 2 record, terurut waktu, timestamp dalam WIB
        self.assertEqual([t["ref_id"] for t in data["timeline"]],
                         ["UPD-006", "UPD-010", "API-EPS-001", "UPD-016", "API-EPS-002"])  # 07:30 seri -> urut ref_id
        stamps = [t["ts"] for t in data["timeline"]]
        self.assertEqual(stamps, sorted(stamps))
        self.assertTrue(stamps[0].endswith("+07:00"))

    def test_evidence_resolvable_in_timeline(self):
        # Setiap evidence update/production harus bisa ditemukan di timeline project yang sama (dipakai UI).
        for pid in EXPECTED:
            data = self.client.get(f"/api/projects/{pid}").json()
            refs = {t["ref_id"] for t in data["timeline"]}
            for f in data["findings"]:
                for e in f["evidence"]:
                    if e["ref_type"] != "master":
                        self.assertIn(e["ref_id"], refs, f"{pid} {f['rule']}")

    def test_list_has_no_n_plus_one(self):
        # Skala 100 project (audit putaran 3): jumlah query list endpoint harus konstan.
        from datetime import date, datetime, timezone
        for i in range(94):
            p = Project.objects.create(project_id=f"SCALE-{i:03}", customer="C", project_name="N", project_type="T",
                                       pic="P", start_date=date(2026, 9, 1), deadline=date(2026, 12, 1), target_unit="ML")
            ProjectMetrics.objects.create(project=p, as_of=datetime(2026, 10, 6, tzinfo=timezone.utc), attention="MEDIUM")
            Finding.objects.create(project=p, rule="PACE_RISK", severity="MEDIUM", category="SCHEDULE",
                                   summary="s", explanation="e", evidence=[])
        with self.assertNumQueries(2):
            rows = self.client.get("/api/projects").json()
        self.assertEqual(len(rows), 100)

    def test_not_found_and_method(self):
        for bad in ("PRJ-002%00", "%3Cscript%3E", "x" * 300):  # audit putaran 3: dulu NUL -> 500
            self.assertEqual(self.client.get(f"/api/projects/{bad}").json(), {"error": "not found"})
        res = self.client.get("/api/projects/PRJ-999")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json(), {"error": "not found"})
        self.assertEqual(self.client.post("/api/projects").status_code, 405)


class PlainLanguageTests(TestCase):
    """Fase 7a: kalimat awam + perkiraan tanggal selesai."""

    @classmethod
    def setUpTestData(cls):
        call_command("ingest", stdout=StringIO())

    def test_forecast_per_project(self):
        expected = {"PRJ-001": ("2026-10-17", 2), "PRJ-002": ("2026-10-15", 5), "PRJ-003": ("2026-10-04", -16),
                    "PRJ-004": ("2026-11-18", 13), "PRJ-005": (None, None), "PRJ-006": (None, None)}
        for m in ProjectMetrics.objects.all():
            with self.subTest(m.project_id):
                finish = str(localtime(m.forecast_finish).date()) if m.forecast_finish else None
                self.assertEqual((finish, m.forecast_delay_days), expected[m.project_id])

    def test_every_finding_has_jargon_free_plain_text(self):
        for f in Finding.objects.all():
            with self.subTest(f"{f.project_id} {f.rule}"):
                self.assertTrue(f.summary)
                # verify & follow_up juga tampil di tampilan utama ("Yang perlu dilakukan").
                for text in (f.summary, f.verify, f.follow_up):
                    self.assertIsNone(JARGON.search(text), text)

    def test_headline_is_most_informative_finding(self):
        rows = {r["project_id"]: r["headline"] for r in self.client.get("/api/projects").json()}
        self.assertIn("seharusnya sudah selesai", rows["PRJ-003"])  # bukan "persentase tidak cocok"
        self.assertIn("13 hari setelah deadline", rows["PRJ-004"])

    def test_key_summaries(self):
        s = {(f.project_id, f.rule): f.summary for f in Finding.objects.all()}
        self.assertIn("belum lolos pengecekan internal", s[("PRJ-001", "REPORTED_VS_OBSERVED")])
        self.assertIn("belum satu pun yang teruji di sistem customer", s[("PRJ-005", "REPORTED_VS_OBSERVED")])
        self.assertIn("meter linear", s[("PRJ-001", "REPORTED_VS_OBSERVED")])
        self.assertIn("seharusnya sudah selesai ±4 Okt", s[("PRJ-003", "STALE_REPORT")])

    def test_conclusion_per_project(self):
        """Fase 8a: paragraf Kesimpulan — pembuka sesuai status, maksimal 2 masalah, langkah pertama, bebas jargon."""
        c = {pid: self.client.get(f"/api/projects/{pid}").json()["conclusion"] for pid in EXPECTED}
        self.assertTrue(c["PRJ-002"]["text"].startswith("Project ini perlu tindakan segera."))
        self.assertIn("5 hari setelah deadline", c["PRJ-002"]["text"])
        self.assertIn('masih melaporkan project ini "sesuai rencana"', c["PRJ-002"]["text"])
        self.assertIn("rencana percepatan", c["PRJ-002"]["first_step"])
        self.assertIn("Eskalasi", c["PRJ-005"]["first_step"])  # hambatan didahulukan
        self.assertIn("kabar terbaru", c["PRJ-003"]["first_step"])
        self.assertTrue(c["PRJ-006"]["text"].startswith("Tidak ada masalah"))
        self.assertEqual(c["PRJ-006"]["first_step"], "")
        for pid, item in c.items():
            with self.subTest(pid):
                self.assertIsNone(JARGON.search(item["text"] + " " + item["first_step"]))

