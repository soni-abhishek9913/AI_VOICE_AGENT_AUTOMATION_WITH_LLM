# admin_backend.py - Flask backend for hospital appointment management and analytics

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import csv, os, hashlib, re
from datetime import datetime, timedelta
from collections import defaultdict

app = Flask(__name__, static_folder="static", static_url_path="/static")
CORS(app)

BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
CSV_FILE        = os.path.join(BASE_DIR, "appointments.csv")
TRANSCRIPT_FILE = os.path.join(BASE_DIR, "transcripts.txt")

ADMIN_USERNAME  = ""
ADMIN_PASS_HASH = hashlib.sha256("".encode()).hexdigest()

DEPT_MAP = {
    "Dr Shah":   "neurology",  "Dr Reddy":  "neurology",
    "Dr Mehta":  "general",    "Dr Singh":  "general",
    "Dr Patel":  "gastro",     "Dr Verma":  "gastro",
    "Dr Gupta":  "dermatology","Dr Kapoor": "dermatology",
}

SYMPTOM_DEPT_MAP = {
    "headache": "neurology", "migraine": "neurology", "seizure": "neurology",
    "sar dard": "neurology", "sir dard": "neurology",
    "stomach": "gastro", "gastro": "gastro", "acidity": "gastro",
    "skin": "dermatology", "rash": "dermatology", "acne": "dermatology",
    "fever": "general", "cold": "general", "cough": "general",
}


def read_appointments():
    rows = []
    if not os.path.exists(CSV_FILE):
        return rows
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            row_clean = {k.strip() if k else k: v for k, v in row.items()}
            doc = (row_clean.get("Doctor") or "").strip()
            rows.append({
                "id":         i + 1,
                "first_name": (row_clean.get("First Name") or "").strip(),
                "last_name":  (row_clean.get("Last Name") or "").strip(),
                "doctor":     doc,
                "date":       (row_clean.get("Date") or "").strip(),
                "time":       (row_clean.get("Time") or "").strip(),
                "booked_at":  (row_clean.get("Booked At") or "").strip(),
                "department": DEPT_MAP.get(doc, "general"),
                "status":     (row_clean.get("Status") or "active").strip(),
                "dob":        (row_clean.get("DOB") or "").strip(),
            })
    return rows


def write_appointments(rows):
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["First Name","Last Name","Doctor","Date","Time","Booked At","Status","DOB"]
        )
        writer.writeheader()
        for r in rows:
            writer.writerow({
                "First Name": r["first_name"],
                "Last Name":  r["last_name"],
                "Doctor":     r["doctor"],
                "Date":       r["date"],
                "Time":       r["time"],
                "Booked At":  r["booked_at"],
                "Status":     r.get("status", "active"),
                "DOB":        r.get("dob", ""),
            })


def parse_transcripts():
    if not os.path.exists(TRANSCRIPT_FILE):
        return []
    with open(TRANSCRIPT_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    SEP = "=" * 60
    blocks = content.split(SEP)
    calls = []
    for i in range(0, len(blocks) - 1, 2):
        header_block = blocks[i].strip()
        body_block   = blocks[i + 1].strip() if i + 1 < len(blocks) else ""
        if not body_block:
            continue
        call = {
            "sid": "", "datetime": "", "language": "EN",
            "turns": [], "outcome": "incomplete",
            "patient_name": "", "doctor": "",
            "duration_turns": 0, "symptoms": [],
        }
        for line in header_block.splitlines():
            line = line.strip()
            if line.startswith("Call SID"):
                call["sid"] = line.split(":", 1)[-1].strip()
            elif line.startswith("Date/Time"):
                call["datetime"] = line.split(":", 1)[-1].strip()
            elif line.startswith("Language"):
                call["language"] = line.split(":", 1)[-1].strip()
        for line in body_block.splitlines():
            line = line.strip()
            if not line: continue
            if line.startswith("[ADAM]"):
                call["turns"].append({"role": "adam", "text": line[7:].strip()})
            elif line.startswith("[USER]"):
                call["turns"].append({"role": "user", "text": line[7:].strip()})
        call["duration_turns"] = len(call["turns"])
        full_text_original = " ".join(t["text"] for t in call["turns"])
        full_text = full_text_original.lower()
        for symptom in SYMPTOM_DEPT_MAP:
            if symptom in full_text:
                call["symptoms"].append(symptom)
        if any(w in full_text for w in ["confirmed","confirm ho gayi","confirm ho gaya","appointment confirmed","booking confirmed"]):
            call["outcome"] = "booked"
        elif any(w in full_text for w in ["cancelled","cancel kar di","cancel ho gayi","cancel ho gaya"]):
            call["outcome"] = "cancelled"
        elif len(call["turns"]) <= 2:
            call["outcome"] = "dropped"
        else:
            call["outcome"] = "incomplete"
        # ── Patient name extraction (multiple patterns) ──────────────
        # 1) "Thank you, FirstName LastName" pattern
        name_match = re.search(
            r"Thank you,?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)[\.,]",
            full_text_original, re.IGNORECASE
        )
        if name_match:
            call["patient_name"] = name_match.group(1).title()
        else:
            # 2) "Shukriya, Name" (Hindi calls)
            name_match = re.search(
                r"Shukriya,?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)[\.,]",
                full_text_original, re.IGNORECASE
            )
            if name_match:
                call["patient_name"] = name_match.group(1).title()
            else:
                # 3) Scan ADAM turns for "Thank you <Name>" or confirmation lines
                for turn in call["turns"]:
                    if turn["role"] != "adam":
                        continue
                    m = re.search(
                        r"(?:Thank you|Shukriya),?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)(?:[\.!,]|$)",
                        turn["text"], re.IGNORECASE
                    )
                    if m:
                        call["patient_name"] = m.group(1).title()
                        break
                # 4) Look for "appointment confirmed" line with name
                if not call["patient_name"]:
                    m = re.search(
                        r"appointment.*?(?:confirmed|confirm ho gay[ia]).*?(?:Thank you|Shukriya),?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)[\.,]",
                        full_text_original, re.IGNORECASE | re.DOTALL
                    )
                    if m:
                        call["patient_name"] = m.group(1).title()

        # ── Doctor extraction (case-insensitive) ─────────────────────
        for doc in DEPT_MAP:
            if re.search(re.escape(doc), full_text_original, re.IGNORECASE):
                call["doctor"] = doc
                break
        calls.append(call)
    return calls


def build_stats(rows, calls):
    doc_counts   = {}
    time_counts  = {}
    dept_counts  = {}
    day_counts   = {}
    patient_counts = {}
    doc_status   = defaultdict(lambda: {"total": 0, "cancelled": 0, "active": 0})
    weekly       = {"Mon": 0, "Tue": 0, "Wed": 0, "Thu": 0, "Fri": 0, "Sat": 0, "Sun": 0}
    heatmap      = defaultdict(lambda: defaultdict(int))
    daily_trend  = {}
    hourly_trend = defaultdict(int)
    dept_daily   = defaultdict(lambda: defaultdict(int))

    for r in rows:
        doc  = r["doctor"]
        dept = r["department"]
        t    = r["time"]
        booked_at = r["booked_at"] or ""
        day  = booked_at[:10] if booked_at else "unknown"
        name = (r["first_name"] + " " + r["last_name"]).strip()
        status = r.get("status", "active")

        doc_counts[doc]   = doc_counts.get(doc, 0) + 1
        time_counts[t]    = time_counts.get(t, 0) + 1
        dept_counts[dept] = dept_counts.get(dept, 0) + 1
        day_counts[day]   = day_counts.get(day, 0) + 1
        patient_counts[name] = patient_counts.get(name, 0) + 1
        daily_trend[day]  = daily_trend.get(day, 0) + 1
        heatmap[doc][t]  += 1
        dept_daily[dept][day] += 1

        if len(booked_at) >= 16:
            try:
                hr = int(booked_at[11:13])
                hourly_trend[hr] += 1
            except Exception:
                pass

        doc_status[doc]["total"] += 1
        if status == "cancelled":
            doc_status[doc]["cancelled"] += 1
        else:
            doc_status[doc]["active"] += 1

        if len(booked_at) >= 10:
            try:
                wd = datetime.strptime(booked_at[:10], "%Y-%m-%d").strftime("%a")
                if wd in weekly:
                    weekly[wd] += 1
            except Exception:
                pass

    doctor_stats = {}
    for doc, s in doc_status.items():
        rate = round(s["cancelled"] / s["total"] * 100, 1) if s["total"] else 0
        efficiency = round(max(0, 100 - rate * 1.5), 1)
        doctor_stats[doc] = {
            **s, "cancel_rate": rate,
            "efficiency_score": efficiency,
            "department": DEPT_MAP.get(doc, "general"),
        }

    patients    = set((r["first_name"] + " " + r["last_name"]).strip() for r in rows)
    active_days = len(day_counts)
    total       = len(rows)
    cancelled   = sum(1 for r in rows if r.get("status") == "cancelled")
    active      = total - cancelled
    cancel_rate = round(cancelled / total * 100, 1) if total else 0
    top_doc     = max(doc_counts, key=doc_counts.get) if doc_counts else ""
    avg_per_day = round(total / active_days, 1) if active_days else 0
    peak_time   = max(time_counts, key=time_counts.get) if time_counts else ""
    top_dept    = max(dept_counts, key=dept_counts.get) if dept_counts else ""
    repeat_pts  = sum(1 for v in patient_counts.values() if v > 1)

    top_patients = sorted(
        [{"name": k, "count": v} for k, v in patient_counts.items()],
        key=lambda x: x["count"], reverse=True
    )[:5]

    sorted_days = sorted(k for k in daily_trend if k != "unknown")[-30:]
    daily_trend_sorted = {d: daily_trend[d] for d in sorted_days}

    # 7-day linear regression forecast
    forecast = {}
    last_14 = sorted_days[-14:]
    if len(last_14) >= 3:
        vals = [daily_trend[d] for d in last_14]
        n = len(vals)
        xs = list(range(n))
        mean_x = sum(xs) / n
        mean_y = sum(vals) / n
        num = sum((xs[i] - mean_x) * (vals[i] - mean_y) for i in range(n))
        den = sum((xs[i] - mean_x) ** 2 for i in range(n))
        slope = num / den if den else 0
        intercept = mean_y - slope * mean_x
        try:
            last_date = datetime.strptime(last_14[-1], "%Y-%m-%d")
            for j in range(1, 8):
                fd = last_date + timedelta(days=j)
                predicted = max(0, round(slope * (n - 1 + j) + intercept, 1))
                forecast[fd.strftime("%Y-%m-%d")] = predicted
        except Exception:
            pass

    # Call stats
    outcomes = {"booked": 0, "cancelled": 0, "incomplete": 0, "dropped": 0}
    lang_counts = {"EN": 0, "HI": 0}
    avg_turns_by_outcome = defaultdict(list)
    symptoms_freq = defaultdict(int)
    call_hourly = defaultdict(int)

    for c in calls:
        outcomes[c["outcome"]] = outcomes.get(c["outcome"], 0) + 1
        lang = c.get("language", "EN")
        lang_counts[lang] = lang_counts.get(lang, 0) + 1
        avg_turns_by_outcome[c["outcome"]].append(c["duration_turns"])
        for sym in c.get("symptoms", []):
            symptoms_freq[sym] += 1
        if c.get("datetime") and len(c["datetime"]) >= 13:
            try:
                hr = int(c["datetime"][11:13])
                call_hourly[hr] += 1
            except Exception:
                pass

    total_calls = len(calls)
    booked_calls = outcomes.get("booked", 0)
    conversion_rate = round(booked_calls / total_calls * 100, 1) if total_calls else 0

    avg_turns_outcome = {k: round(sum(v) / len(v), 1) if v else 0 for k, v in avg_turns_by_outcome.items()}

    funnel = {
        "total_calls": total_calls,
        "reached_booking": total_calls - outcomes.get("dropped", 0),
        "completed": total_calls - outcomes.get("dropped", 0) - outcomes.get("incomplete", 0),
        "booked": booked_calls,
        "conversion_rate": conversion_rate,
    }

    dept_trend = {}
    for dept, dmap in dept_daily.items():
        dept_trend[dept] = {d: dmap.get(d, 0) for d in sorted_days[-14:]}

    visit_distribution = defaultdict(int)
    for v in patient_counts.values():
        bucket = str(min(v, 5))
        visit_distribution[bucket] += 1

    hourly_counts = {str(h): hourly_trend.get(h, 0) for h in range(8, 21)}

    return {
        "total": total, "active_count": active, "cancelled_count": cancelled,
        "cancel_rate": cancel_rate, "unique_patients": len(patients),
        "top_doctor": top_doc, "repeat_patients": repeat_pts,
        "avg_per_day": avg_per_day, "peak_time": peak_time, "top_dept": top_dept,
        "doc_counts": doc_counts, "time_counts": time_counts,
        "dept_counts": dept_counts, "day_counts": day_counts,
        "patient_counts": patient_counts, "doctor_stats": doctor_stats,
        "weekly_pattern": weekly,
        "heatmap": {doc: dict(slots) for doc, slots in heatmap.items()},
        "daily_trend": daily_trend_sorted, "top_patients": top_patients,
        "total_calls": total_calls, "call_outcomes": outcomes,
        "lang_counts": lang_counts,
        "avg_turns": round(sum(c["duration_turns"] for c in calls) / len(calls), 1) if calls else 0,
        # Advanced
        "forecast": forecast, "funnel": funnel,
        "conversion_rate": conversion_rate,
        "avg_turns_by_outcome": avg_turns_outcome,
        "symptoms_freq": dict(symptoms_freq),
        "dept_trend": dept_trend,
        "visit_distribution": dict(visit_distribution),
        "hourly_counts": hourly_counts,
        "call_hourly": {str(k): v for k, v in call_hourly.items()},
    }


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    ph   = hashlib.sha256(data.get("password","").encode()).hexdigest()
    if data.get("username","") == ADMIN_USERNAME and ph == ADMIN_PASS_HASH:
        return jsonify({"ok": True, "token": "demo-token-abc123"})
    return jsonify({"ok": False, "error": "Invalid credentials"}), 401


@app.route("/api/appointments", methods=["GET"])
def get_appointments():
    rows   = read_appointments()
    doctor = request.args.get("doctor","")
    time_  = request.args.get("time","")
    search = request.args.get("search","").lower()
    if doctor: rows = [r for r in rows if r["doctor"] == doctor]
    if time_:  rows = [r for r in rows if r["time"]   == time_]
    if search: rows = [r for r in rows if search in
                       (r["first_name"]+" "+r["last_name"]+" "+r["doctor"]+" "+r["date"]).lower()]
    return jsonify(rows)


@app.route("/api/appointments", methods=["POST"])
def add_appointment():
    data = request.get_json() or {}
    rows = read_appointments()
    doc  = data.get("doctor","")
    new_row = {
        "id": len(rows) + 1, "first_name": data.get("first_name",""),
        "last_name": data.get("last_name",""), "doctor": doc,
        "date": data.get("date",""), "time": data.get("time",""),
        "booked_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "department": DEPT_MAP.get(doc, "general"), "status": "active",
        "dob": data.get("dob",""),
    }
    rows.append(new_row)
    write_appointments(rows)
    return jsonify({"ok": True, "appointment": new_row}), 201


@app.route("/api/appointments/<int:apt_id>", methods=["DELETE"])
def delete_appointment(apt_id):
    rows = read_appointments()
    new  = [r for r in rows if r["id"] != apt_id]
    if len(new) == len(rows):
        return jsonify({"ok": False, "error": "Not found"}), 404
    write_appointments(new)
    return jsonify({"ok": True, "deleted": apt_id})


@app.route("/api/appointments/<int:apt_id>/cancel", methods=["POST"])
def cancel_appointment(apt_id):
    rows = read_appointments()
    found = False
    for r in rows:
        if r["id"] == apt_id:
            r["status"] = "cancelled"; found = True; break
    if not found:
        return jsonify({"ok": False, "error": "Not found"}), 404
    write_appointments(rows)
    return jsonify({"ok": True, "cancelled": apt_id})


@app.route("/api/appointments/bulk-delete", methods=["POST"])
def bulk_delete_appointments():
    data = request.get_json() or {}
    ids  = set(int(i) for i in data.get("ids", []))
    if not ids: return jsonify({"ok": False, "error": "No ids provided"}), 400
    rows = read_appointments()
    new  = [r for r in rows if r["id"] not in ids]
    write_appointments(new)
    return jsonify({"ok": True, "deleted": len(rows) - len(new)})


@app.route("/api/appointments/bulk-cancel", methods=["POST"])
def bulk_cancel_appointments():
    data = request.get_json() or {}
    ids  = set(int(i) for i in data.get("ids", []))
    if not ids: return jsonify({"ok": False, "error": "No ids provided"}), 400
    rows = read_appointments()
    cancelled = 0
    for r in rows:
        if r["id"] in ids and r.get("status") != "cancelled":
            r["status"] = "cancelled"; cancelled += 1
    write_appointments(rows)
    return jsonify({"ok": True, "cancelled": cancelled})


@app.route("/api/appointments/<int:apt_id>/reschedule", methods=["POST"])
def reschedule_appointment(apt_id):
    data = request.get_json() or {}
    rows = read_appointments()
    found = False
    for r in rows:
        if r["id"] == apt_id:
            doc = data.get("doctor", r["doctor"])
            r["doctor"] = doc; r["date"] = data.get("date", r["date"])
            r["time"] = data.get("time", r["time"])
            r["department"] = DEPT_MAP.get(doc, "general")
            r["status"] = "active"; found = True; break
    if not found: return jsonify({"ok": False, "error": "Not found"}), 404
    write_appointments(rows)
    return jsonify({"ok": True, "rescheduled": apt_id})


@app.route("/api/stats", methods=["GET"])
def get_stats():
    rows  = read_appointments()
    calls = parse_transcripts()
    return jsonify(build_stats(rows, calls))


@app.route("/api/insights", methods=["GET"])
def get_insights():
    rows  = read_appointments()
    calls = parse_transcripts()
    stats = build_stats(rows, calls)
    insights = []

    if stats["cancel_rate"] > 20:
        insights.append({"type": "warning", "title": "High Cancellation Rate",
            "body": f"Overall cancellation rate is {stats['cancel_rate']}%. Consider SMS reminders 24h before appointments.",
            "metric": f"{stats['cancel_rate']}%"})

    if stats["doc_counts"]:
        top = max(stats["doc_counts"], key=stats["doc_counts"].get)
        top_v = stats["doc_counts"][top]
        avg_v = sum(stats["doc_counts"].values()) / len(stats["doc_counts"])
        if top_v > avg_v * 1.8:
            insights.append({"type": "warning", "title": "Doctor Overload Detected",
                "body": f"{top} has {top_v} appointments — {round(top_v/avg_v,1)}× the average. Consider redistributing.",
                "metric": f"{top_v} apts"})

    cr = stats.get("conversion_rate", 0)
    if cr < 60:
        insights.append({"type": "warning", "title": "Low Call Conversion",
            "body": f"Only {cr}% of calls result in a booking. Review ADAM's dialogue flow.",
            "metric": f"{cr}%"})
    else:
        insights.append({"type": "success", "title": "Strong Call Conversion",
            "body": f"ADAM is converting {cr}% of calls to bookings. Excellent!",
            "metric": f"{cr}%"})

    if stats["peak_time"]:
        insights.append({"type": "info", "title": "Peak Booking Slot",
            "body": f"Most appointments are at {stats['peak_time']}. Ensure adequate staffing.",
            "metric": stats["peak_time"]})

    lc = stats.get("lang_counts", {})
    hi = lc.get("HI", 0); en = lc.get("EN", 0); total_lang = hi + en
    if total_lang > 0 and hi / total_lang > 0.4:
        insights.append({"type": "info", "title": "Hindi Usage High",
            "body": f"{round(hi/total_lang*100)}% of calls are in Hindi. Consider Hindi appointment reminders.",
            "metric": f"{round(hi/total_lang*100)}% HI"})

    return jsonify({"insights": insights, "generated_at": datetime.now().isoformat()})


@app.route("/api/transcripts", methods=["GET"])
def get_transcripts():
    calls = parse_transcripts()
    limit = request.args.get("limit")
    if limit is not None:
        try:
            calls = calls[:int(limit)]
        except ValueError:
            pass
    return jsonify({"calls": calls, "total": len(calls)})


@app.route("/api/transcripts/<sid>", methods=["GET"])
def get_transcript(sid):
    calls = parse_transcripts()
    match = next((c for c in calls if c["sid"] == sid), None)
    if not match: return jsonify({"error": "Not found"}), 404
    return jsonify(match)


@app.route("/api/doctors", methods=["GET"])
def get_doctors():
    rows = read_appointments()
    counts = {}
    for r in rows:
        counts[r["doctor"]] = counts.get(r["doctor"], 0) + 1
    doctors = [
        {"name": "Dr Shah",   "dept": "Neurology",        "bookings": counts.get("Dr Shah", 0)},
        {"name": "Dr Reddy",  "dept": "Neurology",        "bookings": counts.get("Dr Reddy", 0)},
        {"name": "Dr Mehta",  "dept": "General",          "bookings": counts.get("Dr Mehta", 0)},
        {"name": "Dr Singh",  "dept": "General",          "bookings": counts.get("Dr Singh", 0)},
        {"name": "Dr Patel",  "dept": "Gastroenterology", "bookings": counts.get("Dr Patel", 0)},
        {"name": "Dr Verma",  "dept": "Gastroenterology", "bookings": counts.get("Dr Verma", 0)},
        {"name": "Dr Gupta",  "dept": "Dermatology",      "bookings": counts.get("Dr Gupta", 0)},
        {"name": "Dr Kapoor", "dept": "Dermatology",      "bookings": counts.get("Dr Kapoor", 0)},
    ]
    return jsonify(doctors)


_csv_mtime = 0
_txt_mtime = 0

@app.route("/api/poll", methods=["GET"])
def poll():
    global _csv_mtime, _txt_mtime
    csv_mt = os.path.getmtime(CSV_FILE)        if os.path.exists(CSV_FILE)        else 0
    txt_mt = os.path.getmtime(TRANSCRIPT_FILE) if os.path.exists(TRANSCRIPT_FILE) else 0
    changed = (csv_mt != _csv_mtime) or (txt_mt != _txt_mtime)
    if changed:
        _csv_mtime = csv_mt; _txt_mtime = txt_mt
    
    active_sessions = 0
    import requests
    try:
        r = requests.get("http://localhost:/api/active_sessions", timeout=1)
        if r.status_code == 200:
            active_sessions = r.json().get("active_sessions", 0)
    except:
        pass
        
    return jsonify({"changed": changed, "csv_mtime": csv_mt, "txt_mtime": txt_mt, "active_sessions": active_sessions})


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok", "timestamp": datetime.now().isoformat(),
        "csv_exists": os.path.exists(CSV_FILE),
        "transcript_exists": os.path.exists(TRANSCRIPT_FILE),
        "csv_path": CSV_FILE, "transcript_path": TRANSCRIPT_FILE,
    })


@app.route("/")
def serve_dashboard():
    return send_from_directory(".", "admin_dashboard.html")


if __name__ == "__main__":
    app.run(host="", port=, debug=True)
