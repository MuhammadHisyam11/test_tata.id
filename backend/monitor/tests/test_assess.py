"""Unit test pure function di assess.py — tanpa database."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase

from monitor import assess

WIB = ZoneInfo("Asia/Jakarta")
AS_OF = datetime(2026, 10, 6, 17, 0, tzinfo=WIB)


def project(**kw):
    base = {
        "project_id": "PRJ-T", "pic": "Tester", "start_date": date(2026, 9, 1), "deadline": date(2026, 10, 15),
        "target": 400.0, "target_unit": "ML", "reported_actual": 318.0, "reported_progress_pct": 79.5,
        "reported_status": "ON TRACK", "last_reported_update_at": datetime(2026, 10, 6, 11, 32, tzinfo=WIB),
    }
    return {**base, **kw}


def record(rid, ts, record_type="production_snapshot", source_system="sys", **payload):
    return {"source_record_id": rid, "record_type": record_type, "source_system": source_system,
            "timestamp": ts, "payload": payload}


def update(uid, message, ts=datetime(2026, 10, 5, 9, 0, tzinfo=WIB), source_name="X"):
    return {"update_id": uid, "message": message, "timestamp": ts, "source_type": "OPERATOR", "source_name": source_name}


def ctx(p, updates=(), records=()):
    updates, records = list(updates), list(records)
    return assess.Ctx(p, updates, records, assess.compute_metrics(p, updates, records, AS_OF), AS_OF)


class PaceTests(SimpleTestCase):
    def test_pace_uses_snapshot_timestamp_and_inclusive_deadline(self):
        # Kasus PRJ-001: snapshot 10-05 18:00, deadline 10-15 inklusif (23:59:59).
        rec = record("R1", datetime(2026, 10, 5, 18, 0, tzinfo=WIB), verified_quantity=301.5, unit="ML")
        m = ctx(project(), records=[rec]).metrics
        self.assertAlmostEqual(m["historical_rate"], 301.5 / 34.75, places=4)
        self.assertAlmostEqual(m["remaining_days_from_snapshot"], 10.25, places=3)
        self.assertAlmostEqual(m["pace_ratio"], 1.1076, places=3)
        self.assertEqual(m["days_remaining"], 9)  # dari AS_OF, untuk tampilan

    def test_forecast_finish_and_delay(self):
        # 98.5 ML sisa / 8.676 ML/hari = 11.35 hari dari 10-05 18:00 -> 17 Okt, deadline 15 Okt -> +2 hari.
        rec = record("R1", datetime(2026, 10, 5, 18, 0, tzinfo=WIB), verified_quantity=301.5, unit="ML")
        m = ctx(project(), records=[rec]).metrics
        self.assertEqual(m["forecast_finish"].date(), date(2026, 10, 17))
        self.assertEqual(m["forecast_delay_days"], 2)

    def _pace_ctx(self, ratio, required, capacity=None):
        c = ctx(project())
        c.metrics.update(pace_ratio=ratio, required_rate=required, historical_rate=required / ratio,
                         stated_capacity=capacity, stated_capacity_source="UPD-X" if capacity else None,
                         remaining_days_from_snapshot=5.0, observed_at=AS_OF, observed_source_id="R1")
        return c

    def test_pace_thresholds(self):
        self.assertEqual(assess.rule_pace_risk(self._pace_ctx(1.0, 100)), [])  # batas tidak inklusif
        self.assertEqual(assess.rule_pace_risk(self._pace_ctx(1.01, 100))[0].severity, "MEDIUM")
        self.assertEqual(assess.rule_pace_risk(self._pace_ctx(1.51, 100))[0].severity, "HIGH")

    def test_pace_finding_iff_forecast_late(self):
        # Opsi (a): temuan keterlambatan muncul jika dan hanya jika perkiraan selesai lewat deadline,
        # supaya status tidak "Aman" sementara kolom perkiraan menulis "N hari terlambat".
        for verified in (290, 300, 303, 306, 308, 310, 340):  # rasio 1.25 → 0.6, termasuk rentang 1.0–1.1
            rec = record("R1", datetime(2026, 10, 5, 18, 0, tzinfo=WIB), verified_quantity=verified, unit="ML")
            c = ctx(project(reported_actual=float(verified)), records=[rec])
            with self.subTest(verified=verified, ratio=round(c.metrics["pace_ratio"], 3)):
                late = c.metrics["forecast_delay_days"] > 0
                self.assertEqual(bool(assess.rule_pace_risk(c)), late)

    def test_pace_high_when_claimed_capacity_insufficient(self):
        # Rasio hanya 1.3, tetapi laju yang dibutuhkan > kapasitas klaim -> HIGH.
        f = assess.rule_pace_risk(self._pace_ctx(1.3, 6000, capacity=4500))[0]
        self.assertEqual(f.severity, "HIGH")
        self.assertIn({"ref_type": "update", "ref_id": "UPD-X"}, f.evidence)

    def test_pace_without_capacity_asks_for_it(self):
        f = assess.rule_pace_risk(self._pace_ctx(1.3, 100))[0]
        self.assertEqual(f.severity, "MEDIUM")
        self.assertIn("kapasitas harian tidak tersedia", f.verify)

    def test_no_pace_for_non_quantity_units(self):
        p = project(target=10.0, target_unit="endpoints", reported_actual=9.0)
        rec = record("R1", AS_OF, "integration_snapshot", production_tested_endpoints=0, target_endpoints=10)
        self.assertIsNone(ctx(p, records=[rec]).metrics["pace_ratio"])


class ReportedVsObservedTests(SimpleTestCase):
    def _find(self, reported, observed, **pkw):
        rec = record("R1", datetime(2026, 10, 5, 18, 0, tzinfo=WIB), verified_quantity=observed, unit="ML")
        return assess.rule_reported_vs_observed(ctx(project(reported_actual=reported, **pkw), records=[rec]))

    def test_thresholds(self):
        self.assertEqual(self._find(304, 300), [])  # 1.0% -> tidak lebih dari batas
        self.assertEqual(self._find(310, 300)[0].severity, "MEDIUM")  # 2.5%
        self.assertEqual(self._find(330, 300)[0].severity, "HIGH")  # 7.5%

    def test_newer_report_is_labelled_unverified(self):
        f = self._find(310, 300)[0]  # master 10-06 11:32 lebih baru dari snapshot 10-05 18:00
        self.assertIn("belum terverifikasi sistem", f.explanation)

    def test_pending_breakdown_explains_gap(self):
        ts = datetime(2026, 10, 5, 18, 0, tzinfo=WIB)
        recs = [record("R1", ts, verified_quantity=301.5, unit="ML"),
                record("R2", ts, pending_internal_check_quantity=16.5, unit="ML")]
        f = assess.rule_reported_vs_observed(ctx(project(), records=recs))[0]
        self.assertIn("PENDING_INTERNAL_CHECK", f.explanation)
        self.assertIn("301.5", f.explanation)  # tidak boleh dibulatkan jadi 302
        self.assertEqual({e["ref_id"] for e in f.evidence}, {"PRJ-T", "R1", "R2"})


class TextSignalTests(SimpleTestCase):
    def test_good_news_messages_are_not_signals(self):
        # Regression: "belum ada kendala" dulu ikut tertangkap saat lexicon memakai kata "belum"/"kendala".
        ups = [update("U1", "Pekerjaan berjalan normal dan belum ada kendala signifikan."),
               update("U2", "Tidak ada kendala teknis yang dilaporkan.")]
        self.assertEqual(assess.text_signals(ups), [])

    def test_phrases_detected(self):
        ups = [update("U1", "Box kami HOLD dulu sambil menunggu arahan.")]
        self.assertEqual(assess.text_signals(ups), [{"update_id": "U1", "phrases": ["hold", "menunggu"]}])


class HelperTests(SimpleTestCase):
    def test_parse_capacity(self):
        self.assertEqual(assess.parse_capacity("Rata-rata kapasitas tim sekitar 4.500 halaman per hari."), 4500)
        self.assertIsNone(assess.parse_capacity("Produksi berjalan normal."))

    def test_fmt_num_keeps_decimals(self):
        self.assertEqual(assess.fmt_num(301.5), "301.5")
        self.assertEqual(assess.fmt_num(9.0), "9")
        self.assertEqual(assess.fmt_num(87240), "87,240")

    def test_attention_info_only_is_ok(self):
        info = assess.Finding("X", "INFO", "DATA_QUALITY", "x")
        self.assertEqual(assess.attention_of([info]), "OK")
        self.assertEqual(assess.attention_of([]), "OK")

    def test_sort_key(self):
        keys = {"a": assess.sort_key("MEDIUM", 0, 9), "b": assess.sort_key("HIGH", 2, 4),
                "c": assess.sort_key("HIGH", 4, 7), "d": assess.sort_key("OK", 0, None)}
        self.assertEqual(sorted(keys, key=keys.get), ["c", "b", "a", "d"])


class StatusRuleTests(SimpleTestCase):
    def test_overdue(self):
        f = assess.rule_overdue(ctx(project(deadline=date(2026, 10, 1))))
        self.assertEqual(f[0].severity, "HIGH")

    def test_completed_project_only_gets_health_check(self):
        p = project(reported_status="COMPLETED", deadline=date(2026, 9, 1))  # overdue diabaikan
        rec = record("R1", AS_OF, "usage_snapshot", application_status="ONLINE",
                     successful_logins_last_24h=21, failed_logins_last_24h=1, active_users_last_24h=14)
        metrics, findings = assess.assess_project(p, [], [rec], AS_OF)
        self.assertEqual([f.rule for f in findings], ["POST_GO_LIVE_HEALTH"])
        self.assertEqual(metrics["attention"], "OK")

    def test_status_contradiction_only_for_on_track(self):
        high = [assess.Finding("X", "HIGH", "SCHEDULE", "x", evidence=[])]
        self.assertEqual(len(assess.rule_status_contradiction(ctx(project()), high)), 1)
        self.assertEqual(assess.rule_status_contradiction(ctx(project(reported_status="AT RISK")), high), [])


class AuditRegressionTests(SimpleTestCase):
    """Bug yang ditemukan saat audit kode (setelah Fase 7b)."""

    def test_data_quality_uses_latest_snapshot_only(self):
        recs = [record("Q1", datetime(2026, 10, 5, 7, 0, tzinfo=WIB), "verification_quality_snapshot",
                       records_skipped_missing_region=1000, unit="records"),
                record("Q2", datetime(2026, 10, 6, 7, 0, tzinfo=WIB), "verification_quality_snapshot",
                       records_skipped_missing_region=3200, unit="records")]
        found = assess.rule_data_quality_skip(ctx(project(target_unit="records", target=100000.0), records=recs))
        self.assertEqual(len(found), 1)  # dulu: satu finding per snapshot historis
        self.assertEqual(found[0].evidence[0]["ref_id"], "Q2")

    def test_signal_phrases_match_whole_words(self):
        ups = [update("U1", "Threshold tercapai, household data normal."), update("U2", "Box kami hold dulu.")]
        self.assertEqual([s["update_id"] for s in assess.text_signals(ups)], ["U2"])

    def test_record_with_different_unit_is_not_compared(self):
        rec = record("R1", datetime(2026, 10, 5, 18, 0, tzinfo=WIB), verified_quantity=301.5, unit="boxes")
        c = ctx(project(), records=[rec])  # target_unit ML
        self.assertIsNone(c.metrics["observed_actual"])
        self.assertEqual([f.rule for f in assess.rule_insufficient_data(c)], ["INSUFFICIENT_DATA"])

    def test_page_capacity_ignored_for_other_units(self):
        ups = [update("U1", "Kapasitas tim sekitar 4.500 halaman per hari.")]
        self.assertIsNone(ctx(project(), updates=ups).metrics["stated_capacity"])  # project ML
        self.assertEqual(ctx(project(target_unit="pages"), updates=ups).metrics["stated_capacity"], 4500)

    def test_finding_order_unknown_rule_last(self):
        self.assertLess(assess.finding_order("MEDIUM", "PACE_RISK"), assess.finding_order("MEDIUM", "PCT_INCONSISTENT"))
        self.assertLess(assess.finding_order("MEDIUM", "INSUFFICIENT_DATA"), assess.finding_order("MEDIUM", "NEW_RULE"))
        self.assertLess(assess.finding_order("HIGH", "NEW_RULE"), assess.finding_order("MEDIUM", "PACE_RISK"))


class EdgeCaseTests(SimpleTestCase):
    """Audit putaran 2: kasus pinggir yang tidak ada di dataset."""

    def test_zero_progress_is_high_not_ok(self):
        rec = record("R1", datetime(2026, 10, 6, 9, 0, tzinfo=WIB), verified_quantity=0, unit="ML")
        m, f = assess.assess_project(project(reported_actual=0.0, reported_progress_pct=0.0), [], [rec], AS_OF)
        self.assertEqual(m["attention"], "HIGH")  # dulu: OK
        self.assertIn("Belum ada progress", f[0].summary)

    def test_no_system_data_is_low_not_ok(self):
        m, f = assess.assess_project(project(), [], [], AS_OF)
        self.assertEqual(m["attention"], "LOW")
        self.assertEqual([x.rule for x in f], ["INSUFFICIENT_DATA"])

    def test_missing_target_is_flagged(self):
        m, f = assess.assess_project(project(target=None, reported_progress_pct=None), [], [], AS_OF)
        self.assertEqual(m["attention"], "LOW")
        self.assertIn("Target project tidak tercatat", f[0].summary)

    def test_target_exceeded_is_ok(self):
        rec = record("R1", datetime(2026, 10, 6, 9, 0, tzinfo=WIB), verified_quantity=420, unit="ML")
        m, f = assess.assess_project(project(reported_actual=420.0, reported_progress_pct=105.0), [], [rec], AS_OF)
        self.assertEqual((m["attention"], f), ("OK", []))

    def test_absurd_forecast_does_not_crash(self):
        # Fuzz (audit putaran 3): 1 dari 120,000 halaman setelah ~35 hari -> perkiraan >10.000 tahun -> OverflowError.
        rec = record("R1", datetime(2026, 10, 6, 9, 0, tzinfo=WIB), pages_processed_total=1, unit="pages")
        m, f = assess.assess_project(project(target=120000.0, target_unit="pages", reported_actual=1.0), [], [rec], AS_OF)
        self.assertIsNone(m["forecast_finish"])
        self.assertEqual([x.severity for x in f if x.rule == "PACE_RISK"], ["HIGH"])

