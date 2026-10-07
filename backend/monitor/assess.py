"""Metrik + rule engine + text signals.

Sengaja TIDAK meng-import Django: input/output berupa dict biasa supaya logika
bisa dites tanpa database dan dijelaskan terpisah dari framework.

Kontrak input (disiapkan oleh services.py):
- project: dict field master; datetime sudah aware dalam zona waktu lokal (Asia/Jakarta)
- updates: list dict {update_id, timestamp, source_type, source_name, message}
- records: list dict {source_record_id, source_system, record_type, timestamp, payload}
- as_of:   datetime aware (generated_at dari production data)
"""

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, time, timedelta

# ---------- Threshold (pilihan desain, lihat Tech Spec §6; perlu dikalibrasi bersama management) ----------
PCT_TOLERANCE_PTS = 1.0  # selisih poin persen reported vs hitungan sendiri
MISMATCH_MEDIUM = 0.01  # selisih reported vs observed, relatif terhadap target
MISMATCH_HIGH = 0.05
# laju dibutuhkan / laju historis. 1.0 = setiap perkiraan selesai yang lewat deadline menjadi temuan,
# supaya status selalu konsisten dengan kolom "N hari terlambat" di papan.
PACE_MEDIUM = 1.0
PACE_HIGH = 1.5
STALE_DAYS = 3
IMMINENT_DAYS = 7
FAILED_LOGIN_RATIO = 0.10
# Perkiraan selesai lebih dari ini tidak bermakna (dan bisa melampaui batas tanggal Python); PACE_RISK tetap HIGH via rasio.
MAX_FORECAST_DAYS = 3650

SEVERITY_RANK = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "INFO": 0}
# Urutan tampil untuk severity yang sama: temuan paling informatif bagi management lebih dulu
# (temuan teratas menjadi "Masalah utama" di papan).
RULE_ORDER = [
    "COMPLETION_NOT_SUPPORTED", "REPORTED_VS_OBSERVED", "PACE_RISK", "OVERDUE", "ENV_NOT_READY", "DEADLINE_IMMINENT_BLOCKED",
    "STALE_REPORT", "EQUIPMENT_DEGRADED", "DATA_QUALITY_SKIP", "SCOPE_GAP", "PCT_INCONSISTENT",
    "STATUS_CONTRADICTION", "POST_GO_LIVE_HEALTH", "INSUFFICIENT_DATA",
]
ATTENTION_RANK = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "OK": 0}


def finding_order(severity, rule):
    """Kunci urut findings: severity dulu, lalu RULE_ORDER (rule tak dikenal di akhir)."""
    return (-SEVERITY_RANK[severity], RULE_ORDER.index(rule) if rule in RULE_ORDER else len(RULE_ORDER))

# target_unit -> field quantity di production record yang dianggap "observed"
OBSERVED_FIELD = {
    "ML": "verified_quantity",
    "pages": "pages_processed_total",
    "boxes": "processed_boxes",
    "records": "records_verified",
    "endpoints": "production_tested_endpoints",  # "selesai" = sudah teruji di production
}
QUANTITY_UNITS = {"ML", "pages", "boxes", "records"}  # unit yang progress-nya dianggap linier terhadap waktu

# ponytail: regex sempit sesuai pola dataset; ganti dengan field terstruktur bila sumber menyediakan
CAPACITY_RE = re.compile(r"(\d[\d.,]*)\s*halaman per hari", re.IGNORECASE)

# Frasa sengaja spesifik: kata umum seperti "belum"/"kendala" dibuang karena "belum ada kendala" = kabar baik.
SIGNAL_PHRASES = ["hold", "error", "dicek kembali", "dilewati", "menunggu", "belum dapat", "terbatas"]
SIGNAL_RES = {p: re.compile(rf"\b{re.escape(p)}\b") for p in SIGNAL_PHRASES}  # kata utuh: "threshold" bukan "hold"

# Kosakata awam untuk field `summary` (tampilan utama); istilah teknis tetap di `explanation`.
UNIT_PLAIN = {"ML": "meter linear", "pages": "halaman", "boxes": "box", "records": "data", "endpoints": "endpoint"}
OBSERVED_PLAIN = {
    "ML": "terverifikasi", "pages": "tercatat di mesin scanner", "boxes": "tercatat di gudang",
    "records": "terverifikasi di aplikasi", "endpoints": "teruji di sistem customer",
}
BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


@dataclass
class Finding:
    rule: str
    severity: str
    category: str
    explanation: str  # detail teknis
    verify: str = ""
    follow_up: str = ""
    evidence: list = field(default_factory=list)  # [{"ref_type": ..., "ref_id": ...}]
    summary: str = ""  # satu kalimat bahasa awam

    def to_dict(self):
        return asdict(self)


@dataclass
class Ctx:
    project: dict
    updates: list
    records: list
    metrics: dict
    as_of: datetime


# ---------- helpers ----------


def ev(ref_type, ref_id):
    return {"ref_type": ref_type, "ref_id": ref_id}


def master_ev(p):
    return ev("master", p["project_id"])


def rec_ev(r):
    return ev("production", r["source_record_id"])


def upd_ev(u):
    return ev("update", u["update_id"])


def dedup(evidence):
    seen, out = set(), []
    for e in evidence:
        key = (e["ref_type"], e["ref_id"])
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out


def latest(records, record_type=None, has_field=None):
    """Record terbaru yang cocok dengan record_type dan/atau memiliki field tertentu."""
    rows = [
        r for r in records
        if (record_type is None or r["record_type"] == record_type)
        and (has_field is None or r["payload"].get(has_field) is not None)
    ]
    return max(rows, key=lambda r: r["timestamp"]) if rows else None


def mentioning(updates, *words):
    """Update yang menyebut salah satu kata (di pesan atau nama sumber) — evidence pendukung, bukan penentu."""
    words = [w.lower() for w in words]
    return [u for u in updates if any(w in f"{u['message']} {u['source_name']}".lower() for w in words)]


def days_between(a, b):
    return (b - a).total_seconds() / 86400


def fmt_dt(d):
    return d.strftime("%Y-%m-%d %H:%M") if d else "-"


def fmt_day(d):
    return f"{d.day} {BULAN[d.month - 1]}"


def unit_plain(unit):
    return UNIT_PLAIN.get(unit, unit)


def fmt_num(x):
    """Maks. 1 desimal, tanpa '.0' — angka seperti 301.5 tidak boleh dibulatkan jadi 302."""
    s = f"{x:,.1f}"
    return s[:-2] if s.endswith(".0") else s


def parse_capacity(text):
    m = CAPACITY_RE.search(text)
    return float(re.sub(r"[.,]", "", m.group(1))) if m else None


# ---------- text signals (FR-8): hanya untuk dibaca manusia, tidak memengaruhi attention ----------


def text_signals(updates):
    out = []
    for u in updates:
        text = u["message"].lower()
        phrases = [p for p in SIGNAL_PHRASES if SIGNAL_RES[p].search(text)]
        if phrases:
            out.append({"update_id": u["update_id"], "phrases": phrases})
    return out


# ---------- metrik ----------


def compute_metrics(p, updates, records, as_of):
    target, unit = p["target"], p["target_unit"]
    m = {
        "as_of": as_of,
        "computed_pct": p["reported_actual"] / target * 100 if target and p["reported_actual"] is not None else None,
        "observed_actual": None, "observed_at": None, "observed_source_id": None, "observed_pct": None,
        "observed_field": OBSERVED_FIELD.get(unit),
        "days_remaining": (p["deadline"] - as_of.date()).days,
        "historical_rate": None, "required_rate": None, "pace_ratio": None,
        "remaining_days_from_snapshot": None,
        "stated_capacity": None, "stated_capacity_source": None,
        "forecast_finish": None, "forecast_delay_days": None,
    }

    obs_field = OBSERVED_FIELD.get(unit)
    # Record yang mencantumkan unit berbeda dari target_unit tidak dibandingkan (-> INSUFFICIENT_DATA).
    same_unit = [r for r in records if r["payload"].get("unit") in (None, unit)]
    obs = latest(same_unit, has_field=obs_field) if obs_field else None
    if obs:
        m["observed_actual"] = float(obs["payload"][obs_field])
        m["observed_at"] = obs["timestamp"]
        m["observed_source_id"] = obs["source_record_id"]
        if target:
            m["observed_pct"] = m["observed_actual"] / target * 100

    for u in sorted(updates, key=lambda u: u["timestamp"], reverse=True) if unit == "pages" else []:
        cap = parse_capacity(u["message"])
        if cap:
            m["stated_capacity"], m["stated_capacity_source"] = cap, u["update_id"]
            break

    # Pace: dari timestamp snapshot, deadline inklusif (23:59:59), hari kalender pecahan.
    if obs and unit in QUANTITY_UNITS and target:
        tz = obs["timestamp"].tzinfo
        start = datetime.combine(p["start_date"], time.min, tzinfo=tz)
        deadline_end = datetime.combine(p["deadline"], time(23, 59, 59), tzinfo=tz)
        elapsed = days_between(start, obs["timestamp"])
        remaining = days_between(obs["timestamp"], deadline_end)
        if elapsed > 0:
            m["historical_rate"] = m["observed_actual"] / elapsed
        if remaining > 0:
            m["remaining_days_from_snapshot"] = remaining
            m["required_rate"] = max(target - m["observed_actual"], 0) / remaining
        if m["historical_rate"] and m["required_rate"] is not None:
            m["pace_ratio"] = m["required_rate"] / m["historical_rate"]
        # Perkiraan selesai jika kecepatan nyata dipertahankan; terlambat dihitung per tanggal kalender.
        if m["historical_rate"]:
            days_needed = max(target - m["observed_actual"], 0) / m["historical_rate"]
            if days_needed <= MAX_FORECAST_DAYS:
                m["forecast_finish"] = obs["timestamp"] + timedelta(days=days_needed)
                m["forecast_delay_days"] = (m["forecast_finish"].date() - p["deadline"]).days

    stamps = [u["timestamp"] for u in updates] + [r["timestamp"] for r in records]
    if p["last_reported_update_at"]:
        stamps.append(p["last_reported_update_at"])
    m["last_activity_at"] = max(stamps) if stamps else None
    return m


# ---------- rules: masing-masing mengembalikan list[Finding] ----------


def rule_pct_inconsistent(c):
    p, m = c.project, c.metrics
    rp, cp = p["reported_progress_pct"], m["computed_pct"]
    if rp is None or cp is None or abs(rp - cp) <= PCT_TOLERANCE_PTS:
        return []
    return [Finding(
        "PCT_INCONSISTENT", "MEDIUM", "DATA_MISMATCH",
        f"Progress di master tercatat {rp:g}%, padahal reported_actual {fmt_num(p['reported_actual'])} / "
        f"target {fmt_num(p['target'])} {p['target_unit']} = {cp:.1f}%.",
        summary=f"Persentase di laporan ({rp:g}%) tidak cocok dengan angkanya sendiri ({cp:.0f}%).",
        verify=f"Konfirmasi ke {p['pic']} angka mana yang benar dan bagaimana {rp:g}% dihitung.",
        follow_up=f"Minta {p['pic']} memperbaiki persentase progress di laporan agar sesuai dengan angkanya.",
        evidence=[master_ev(p)],
    )]


def rule_reported_vs_observed(c):
    p, m = c.project, c.metrics
    rep, obs, target = p["reported_actual"], m["observed_actual"], p["target"]
    if rep is None or obs is None or not target:
        return []
    gap = rep - obs
    rel = abs(gap) / target
    if rel <= MISMATCH_MEDIUM:
        return []

    unit = p["target_unit"]
    obs_rec = next(r for r in c.records if r["source_record_id"] == m["observed_source_id"])
    u_plain, label = unit_plain(unit), OBSERVED_PLAIN.get(unit, "tercatat di sistem")
    reported_at = p["last_reported_update_at"]
    unverified = reported_at is not None and reported_at > m["observed_at"]
    text = (
        f"Master mencatat {fmt_num(rep)} {unit} (update {fmt_dt(reported_at)}), sedangkan "
        f"{obs_rec['source_system']} mencatat {m['observed_field']} = {fmt_num(obs)} {unit} "
        f"(snapshot {fmt_dt(m['observed_at'])}). Selisih {fmt_num(gap)} {unit} ({rel:.1%} dari target)."
    )
    evidence = [master_ev(p), rec_ev(obs_rec)]

    pending_rec = latest(c.records, has_field="pending_internal_check_quantity")
    pending = pending_rec["payload"]["pending_internal_check_quantity"] if pending_rec else None
    if pending and abs(rep - (obs + pending)) <= 0.001 * target:
        text += f" Selisih ini persis sama dengan {fmt_num(pending)} {unit} yang masih PENDING_INTERNAL_CHECK: master menghitung pekerjaan yang belum terverifikasi."
        verify = f"Pastikan {fmt_num(pending)} {u_plain} yang masih dicek lolos pengecekan sebelum dihitung selesai."
        follow_up = "Minta laporan progress hanya menghitung pekerjaan yang sudah terverifikasi, dan percepat pengecekan yang tertunda."
        evidence.append(rec_ev(pending_rec))
    elif unverified:
        text += " Angka master lebih baru dari snapshot sistem, sehingga selisihnya belum terverifikasi sistem (belum tentu salah)."
        verify = f"Cek apakah selisih {fmt_num(gap)} {u_plain} sudah {label} pada catatan sistem berikutnya."
        follow_up = f"Minta {p['pic']} menyebutkan dari mana angka di laporannya berasal."
    else:
        verify = f"Tanyakan ke {p['pic']} dasar angka {fmt_num(rep)} {u_plain} di laporannya."
        follow_up = f"Gunakan angka sistem ({fmt_num(obs)} {u_plain}) sebagai acuan sampai selisihnya dijelaskan."

    if pending and abs(rep - (obs + pending)) <= 0.001 * target:
        summary = f"{fmt_num(pending)} {u_plain} yang dilaporkan selesai belum lolos pengecekan internal."
    elif obs == 0:
        summary = f"Dilaporkan {fmt_num(rep)} {u_plain} selesai, tetapi belum satu pun yang {label}."
    elif gap > 0:
        summary = f"Laporan PIC ({fmt_num(rep)} {u_plain}) lebih tinggi dari yang {label} ({fmt_num(obs)})."
    else:
        summary = f"Laporan PIC ({fmt_num(rep)} {u_plain}) lebih rendah dari yang {label} ({fmt_num(obs)})."
    sev = "HIGH" if rel > MISMATCH_HIGH else "MEDIUM"
    return [Finding("REPORTED_VS_OBSERVED", sev, "DATA_MISMATCH", text, verify, follow_up, evidence, summary)]


def rule_pace_risk(c):
    p, m = c.project, c.metrics
    if m["historical_rate"] == 0 and m["required_rate"]:
        return [rule_no_progress(c)]
    ratio = m["pace_ratio"]
    if ratio is None or ratio <= PACE_MEDIUM:
        return []
    unit, req, hist, cap = p["target_unit"], m["required_rate"], m["historical_rate"], m["stated_capacity"]
    high = ratio > PACE_HIGH or (cap is not None and req > cap)
    text = (
        f"Untuk selesai sebelum deadline {p['deadline']} ({m['remaining_days_from_snapshot']:.1f} hari dari snapshot "
        f"{fmt_dt(m['observed_at'])}) dibutuhkan {fmt_num(req)} {unit}/hari, sedangkan laju nyata sejauh ini "
        f"{fmt_num(hist)} {unit}/hari (rasio {ratio:.2f}x)."
    )
    evidence = [master_ev(p), ev("production", m["observed_source_id"])]
    if cap is not None:
        text += (f" Bahkan kapasitas yang diklaim ({fmt_num(cap)} {unit}/hari) tidak cukup." if req > cap
                 else f" Kapasitas yang diklaim ({fmt_num(cap)} {unit}/hari) secara teori cukup, tetapi belum pernah tercapai.")
        verify = f"Kapasitas {fmt_num(cap)} {unit_plain(unit)}/hari baru klaim dari PIC dan belum pernah tercapai menurut data."
        evidence.append(ev("update", m["stated_capacity_source"]))
    else:
        verify = "Data kapasitas harian tidak tersedia; minta rekap kapasitas harian ke PIC."
    finish, delay = m["forecast_finish"], m["forecast_delay_days"]
    if finish is not None and delay > 0:
        summary = (f"Dengan kecepatan sekarang, diperkirakan selesai ±{fmt_day(finish)} — "
                   f"{delay} hari setelah deadline ({fmt_day(p['deadline'])}).")
    else:
        summary = f"Tim perlu bekerja {ratio:.1f}x lebih cepat dari biasanya agar selesai tepat waktu."
    if cap is not None and req > cap:
        summary += " Kapasitas yang diklaim pun tidak cukup."
    return [Finding(
        "PACE_RISK", "HIGH" if high else "MEDIUM", "SCHEDULE", text, verify,
        f"Minta {p['pic']} rencana percepatan (tambah tim, shift, atau alat) atau usulkan perubahan deadline ke customer.",
        evidence, summary,
    )]


def rule_no_progress(c):
    """Laju historis 0: rasio tidak terdefinisi, tetapi justru risiko jadwal terbesar."""
    p, m = c.project, c.metrics
    days = (m["observed_at"].date() - p["start_date"]).days
    unit = p["target_unit"]
    return Finding(
        "PACE_RISK", "HIGH", "SCHEDULE",
        f"{m['observed_field']} = 0 pada snapshot {fmt_dt(m['observed_at'])}, {days} hari setelah mulai; "
        f"dibutuhkan {fmt_num(m['required_rate'])} {unit}/hari sampai deadline {p['deadline']}.",
        summary=f"Belum ada progress yang tercatat di sistem, padahal project sudah berjalan {days} hari.",
        verify="Apakah pekerjaan memang belum dimulai, atau datanya belum masuk ke sistem?",
        follow_up=f"Minta {p['pic']} menjelaskan status pekerjaan dan rencana sampai deadline.",
        evidence=[master_ev(p), ev("production", m["observed_source_id"])],
    )


def rule_overdue(c):
    p, d = c.project, c.metrics["days_remaining"]
    if d >= 0:
        return []
    return [Finding(
        "OVERDUE", "HIGH", "SCHEDULE",
        f"Deadline {p['deadline']} sudah lewat {-d} hari, status master masih {p['reported_status']}.",
        summary=f"Sudah lewat deadline {-d} hari, tetapi project belum dinyatakan selesai.",
        verify="Apakah ada perpanjangan deadline yang belum tercatat di master?",
        follow_up=f"Minta {p['pic']} tanggal penyelesaian baru dan update master.",
        evidence=[master_ev(p)],
    )]


def rule_equipment_degraded(c):
    rec = latest(c.records, record_type="scanner_status")
    if not rec:
        return []
    bad = [s for s in rec["payload"].get("scanners", []) if s.get("status") != "RUNNING"]
    if not bad:
        return []
    total = len(rec["payload"]["scanners"])
    sev = "HIGH" if any(s["status"] == "OUT_OF_SERVICE" for s in bad) else "MEDIUM"
    listing = ", ".join(f"{s['scanner_id']} {s['status']}" for s in bad)
    history = [r for r in c.records if r["record_type"] == "scanner_status"]
    return [Finding(
        "EQUIPMENT_DEGRADED", sev, "BLOCKER",
        f"Status scanner terbaru ({fmt_dt(rec['timestamp'])}): {listing} — {total - len(bad)} dari {total} unit berjalan normal.",
        summary=f"{len(bad)} dari {total} scanner belum berfungsi normal.",
        verify="Minta estimasi pemulihan penuh dari vendor dan dampaknya ke kapasitas harian.",
        follow_up="Siapkan unit cadangan atau shift tambahan selama scanner belum normal.",
        evidence=dedup([rec_ev(r) for r in history] + [upd_ev(u) for u in mentioning(c.updates, "scanner")]),
    )]


def rule_env_not_ready(c):
    env = latest(c.records, record_type="environment_check")
    integ = latest(c.records, record_type="integration_snapshot")
    env_bad = env is not None and env["payload"].get("connection_status") != "CONNECTED"
    untested = integ is not None and integ["payload"].get("production_tested_endpoints") == 0
    if not (env_bad or untested):
        return []
    parts, evidence = [], []
    if env:
        last_ok = env["payload"].get("last_successful_connection")
        parts.append(f"koneksi {env['payload'].get('environment')} berstatus {env['payload'].get('connection_status')} "
                     f"(koneksi sukses terakhir: {last_ok or 'belum pernah'})")
        evidence.append(rec_ev(env))
    if integ:
        pl = integ["payload"]
        parts.append(f"{pl.get('production_tested_endpoints')} dari {pl.get('target_endpoints')} endpoint sudah diuji di production")
        evidence.append(rec_ev(integ))
    return [Finding(
        "ENV_NOT_READY", "HIGH", "BLOCKER",
        "Environment production belum siap: " + "; ".join(parts) + ".",
        summary=("Belum bisa diuji di sistem customer karena akses koneksinya belum diberikan." if env_bad
                 else "Belum ada endpoint yang diuji di sistem customer."),
        verify="Kapan customer memberikan akses ke sistemnya? Pastikan ada tanggal yang disepakati.",
        follow_up="Eskalasi ke PIC customer di level management; sepakati tanggal akses atau penyesuaian deadline.",
        evidence=evidence + [upd_ev(u) for u in mentioning(c.updates, "credential", "production")],
    )]


def rule_scope_gap(c):
    integ = latest(c.records, record_type="integration_snapshot")
    if not integ:
        return []
    pl = integ["payload"]
    dev, target = pl.get("developed_endpoints"), pl.get("target_endpoints")
    if dev is None or target is None or dev >= target:
        return []
    return [Finding(
        "SCOPE_GAP", "MEDIUM", "DATA_MISMATCH",
        f"Baru {dev} dari {target} endpoint selesai development; {target - dev} endpoint belum dikembangkan.",
        summary=f"{target - dev} dari {target} endpoint belum dikerjakan.",
        verify=f"Konfirmasi status {target - dev} endpoint sisanya: masih dalam scope atau sudah dikeluarkan?",
        follow_up="Minta PIC konfirmasi scope final dan rencana untuk endpoint yang belum dikembangkan.",
        evidence=[rec_ev(integ)] + [upd_ev(u) for u in mentioning(c.updates, "endpoint")],
    )]


def rule_data_quality_skip(c):
    out = []
    keys = sorted({k for r in c.records for k in r["payload"] if k.startswith("records_skipped")})
    for key in keys:
        r = latest(c.records, has_field=key)  # hanya snapshot terbaru, bukan setiap snapshot historis
        val = r["payload"][key]
        if val:
            obs = c.metrics["observed_actual"]
            share = f", setara {val / obs:.1%} dari record terverifikasi" if obs else ""
            out.append(Finding(
                "DATA_QUALITY_SKIP", "MEDIUM", "DATA_QUALITY",
                f"{fmt_num(val)} record dilewati per {fmt_dt(r['timestamp'])} (field {key}){share}. "
                "Record ini belum terverifikasi dan tetap menjadi sisa pekerjaan.",
                summary=f"{fmt_num(val)} data dilewati karena datanya tidak lengkap; data ini tetap harus diselesaikan.",
                verify="Apakah keputusan melewati record ini sudah disetujui PM dan customer?",
                follow_up="Tetapkan penanganan record yang dilewati (mis. minta data pelengkap ke customer) dan masukkan ke rencana sisa pekerjaan.",
                evidence=[rec_ev(r)] + [upd_ev(u) for u in mentioning(c.updates, "dilewati")],
            ))
    return out


def rule_stale_report(c):
    last = c.metrics["last_activity_at"]
    if last is None:
        return []
    age = days_between(last, c.as_of)
    if age <= STALE_DAYS:
        return []
    evidence = [master_ev(c.project)]
    if c.updates:
        evidence.append(upd_ev(max(c.updates, key=lambda u: u["timestamp"])))
    if c.records:
        evidence.append(rec_ev(max(c.records, key=lambda r: r["timestamp"])))
    summary = f"Tidak ada kabar dari project ini selama {age:.0f} hari."
    finish = c.metrics["forecast_finish"]
    if finish is not None and finish < c.as_of:
        summary += f" Menurut kecepatan sebelumnya seharusnya sudah selesai ±{fmt_day(finish)}, tetapi belum dilaporkan."
    return [Finding(
        "STALE_REPORT", "MEDIUM", "STALE",
        f"Tidak ada informasi baru dari sumber mana pun sejak {fmt_dt(last)} ({age:.0f} hari sebelum {fmt_dt(c.as_of)}). "
        "Kondisi project saat ini tidak diketahui.",
        summary=summary,
        verify="Apakah angka terakhir masih berlaku?",
        follow_up=f"Minta kabar terbaru dari {c.project['pic']} beserta data produksi terakhir.",
        evidence=evidence,
    )]


def rule_post_go_live_health(c):
    rec = latest(c.records, record_type="usage_snapshot")
    if not rec:
        return []
    pl = rec["payload"]
    ok, failed = pl.get("successful_logins_last_24h") or 0, pl.get("failed_logins_last_24h") or 0
    ratio = failed / (ok + failed) if ok + failed else 0
    status = pl.get("application_status")
    bad = status != "ONLINE" or ratio > FAILED_LOGIN_RATIO
    return [Finding(
        "POST_GO_LIVE_HEALTH", "MEDIUM" if bad else "INFO", "BLOCKER" if bad else "DATA_QUALITY",
        f"Pasca go-live ({fmt_dt(rec['timestamp'])}): aplikasi {status}, {pl.get('active_users_last_24h')} user aktif 24 jam, "
        f"login gagal {failed}/{ok + failed} ({ratio:.1%}).",
        summary=("Ada gangguan pada sistem sejak mulai dipakai." if bad
                 else f"Sistem berjalan normal dan dipakai {pl.get('active_users_last_24h')} orang dalam 24 jam terakhir."),
        verify="" if not bad else "Cek penyebab gangguan aplikasi/login.",
        follow_up="Tidak perlu tindakan." if not bad else "Koordinasikan perbaikan dengan tim teknis.",
        evidence=[rec_ev(rec)],
    )]


def rule_completion_not_supported(c):
    """Project dilaporkan COMPLETED, tetapi data sistem masih jauh di bawah target."""
    p, m = c.project, c.metrics
    obs, target = m["observed_actual"], p["target"]
    if obs is None or not target:
        return []
    gap = target - obs
    rel = gap / target
    if rel <= MISMATCH_MEDIUM:
        return []
    unit = p["target_unit"]
    u_plain, label = unit_plain(unit), OBSERVED_PLAIN.get(unit, "tercatat di sistem")
    obs_rec = next(r for r in c.records if r["source_record_id"] == m["observed_source_id"])
    return [Finding(
        "COMPLETION_NOT_SUPPORTED", "HIGH" if rel > MISMATCH_HIGH else "MEDIUM", "DATA_MISMATCH",
        f"Master berstatus COMPLETED, tetapi {obs_rec['source_system']} mencatat {m['observed_field']} = {fmt_num(obs)} {unit} "
        f"(snapshot {fmt_dt(m['observed_at'])}) = {m['observed_pct']:.1f}% dari target {fmt_num(target)} {unit}. "
        f"Kurang {fmt_num(gap)} {unit} ({rel:.1%} dari target).",
        summary=f"Dilaporkan selesai, tetapi baru {m['observed_pct']:.1f}% yang {label} "
                f"({fmt_num(obs)} dari {fmt_num(target)} {u_plain}).",
        verify=f"Apakah {fmt_num(gap)} {u_plain} sisanya sudah dikerjakan tetapi belum tercatat di sistem, "
               "atau project ditutup sebelum target tercapai?",
        follow_up=f"Minta {p['pic']} bukti penyelesaian, atau kembalikan status project menjadi belum selesai.",
        evidence=[master_ev(p), rec_ev(obs_rec)],
    )]


def rule_insufficient_data(c):
    """LOW, bukan INFO: tanpa data, sistem tidak bisa menyatakan project aman."""
    p, m = c.project, c.metrics
    if not p["target"]:
        return [Finding(
            "INSUFFICIENT_DATA", "LOW", "DATA_QUALITY",
            "Field target kosong di master; progress dan jadwal tidak bisa dinilai.",
            summary="Target project tidak tercatat, sehingga progress tidak bisa dinilai.",
            follow_up=f"Minta {p['pic']} melengkapi target project di master.",
            evidence=[master_ev(p)],
        )]
    if m["observed_field"] and m["observed_actual"] is None:
        return [Finding(
            "INSUFFICIENT_DATA", "LOW", "DATA_QUALITY",
            f"Tidak ada data {m['observed_field']} dari production system; progress hanya berdasar laporan master.",
            summary="Tidak ada data dari sistem untuk dibandingkan dengan laporan PIC.",
            follow_up="Pastikan sistem produksi mengirim data untuk project ini.",
            evidence=[master_ev(p)],
        )]
    return []


def rule_deadline_imminent_blocked(c, findings):
    d = c.metrics["days_remaining"]
    blockers = [f for f in findings
                if f.rule == "ENV_NOT_READY" or (f.rule == "EQUIPMENT_DEGRADED" and f.severity == "HIGH")]
    if not (0 <= d <= IMMINENT_DAYS and blockers):
        return []
    return [Finding(
        "DEADLINE_IMMINENT_BLOCKED", "HIGH", "SCHEDULE",
        f"Deadline {c.project['deadline']} tinggal {d} hari, dan masih ada blocker aktif: "
        + ", ".join(f.rule for f in blockers) + ".",
        summary=f"Deadline tinggal {d} hari, tetapi pekerjaan masih terhambat.",
        verify="Apakah deadline masih realistis jika blocker baru selesai mendekati tanggal tersebut?",
        follow_up="Putuskan sekarang: eskalasi blocker atau negosiasi ulang deadline dengan customer.",
        evidence=dedup([e for f in blockers for e in f.evidence]),
    )]


def rule_status_contradiction(c, findings):
    p = c.project
    high = [f for f in findings if f.severity == "HIGH"]
    if p["reported_status"] != "ON TRACK" or not high:
        return []
    return [Finding(
        "STATUS_CONTRADICTION", "HIGH", "DATA_MISMATCH",
        f"Master melaporkan status ON TRACK, tetapi ada {len(high)} temuan HIGH: " + ", ".join(f.rule for f in high) + ".",
        summary=f'PIC melaporkan "sesuai rencana", padahal ada {len(high)} masalah serius.',
        verify=f'Atas dasar apa {p["pic"]} menilai project "sesuai rencana"?',
        follow_up=f"Minta {p['pic']} memperbarui status project di laporan atau menjelaskan penilaiannya.",
        evidence=dedup([master_ev(p)] + [e for f in high for e in f.evidence]),
    )]


ACTIVE_RULES = [
    rule_reported_vs_observed, rule_pct_inconsistent, rule_pace_risk,
    rule_env_not_ready, rule_scope_gap, rule_equipment_degraded, rule_data_quality_skip,
    rule_stale_report, rule_overdue, rule_insufficient_data,
]
META_RULES = [rule_deadline_imminent_blocked, rule_status_contradiction]  # butuh hasil rule lain


def attention_of(findings):
    top = max((SEVERITY_RANK[f.severity] for f in findings), default=0)
    return {3: "HIGH", 2: "MEDIUM", 1: "LOW", 0: "OK"}[top]


def assess_project(project, updates, records, as_of):
    """-> (metrics dict, list[Finding]) untuk satu project."""
    metrics = compute_metrics(project, updates, records, as_of)
    c = Ctx(project, updates, records, metrics, as_of)
    if project["reported_status"] == "COMPLETED":
        # Aturan jadwal/progres tidak relevan lagi, tetapi klaim "selesai" tetap dicocokkan dengan data sistem.
        findings = rule_completion_not_supported(c) + rule_post_go_live_health(c)
    else:
        findings = [f for rule in ACTIVE_RULES for f in rule(c)]
        for meta in META_RULES:
            findings += meta(c, findings)
    findings.sort(key=lambda f: finding_order(f.severity, f.rule))
    metrics["attention"] = attention_of(findings)
    return metrics, findings


LEAD = {
    "HIGH": "Project ini perlu tindakan segera.",
    "MEDIUM": "Project ini perlu dipantau.",
    "LOW": "Data project ini belum cukup untuk dinilai.",
    "OK": "Tidak ada masalah yang ditemukan pada project ini.",
}


def conclusion(attention, findings):
    """Paragraf "Kesimpulan" untuk halaman detail, disusun dari kalimat awam findings yang sudah terurut.

    findings: objek/dict dengan severity, rule, category, summary, follow_up (Finding dataclass atau model).
    -> {"text": str, "first_step": str} — first_step kosong jika tidak ada yang perlu dilakukan.
    """
    get = lambda f, k: f[k] if isinstance(f, dict) else getattr(f, k)  # noqa: E731
    actionable = [f for f in findings if get(f, "severity") != "INFO"]
    shown = [f for f in actionable if get(f, "rule") != "STATUS_CONTRADICTION"][:2]
    if not actionable:
        shown = findings[:1]  # mis. ringkasan kesehatan project selesai
    sentences = [LEAD[attention]] + [get(f, "summary") for f in shown]
    if any(get(f, "rule") == "STATUS_CONTRADICTION" for f in actionable):
        sentences.append('Padahal, PIC masih melaporkan project ini "sesuai rencana".')
    # Langkah pertama: utamakan hambatan & jadwal, karena itu yang perlu diputuskan.
    urgent = [f for f in actionable if get(f, "category") in ("BLOCKER", "SCHEDULE")]
    first = (urgent or actionable or [None])[0]
    return {"text": " ".join(sentences), "first_step": get(first, "follow_up") if first else ""}


def sort_key(attention, n_high, days_remaining):
    """Urutan daftar: attention tertinggi, lalu jumlah HIGH terbanyak, lalu deadline terdekat."""
    return (-ATTENTION_RANK[attention], -n_high, days_remaining if days_remaining is not None else 10**6)
