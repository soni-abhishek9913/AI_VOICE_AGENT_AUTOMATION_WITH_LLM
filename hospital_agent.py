#hospital_agent.py
import csv
import os
import re
import smtplib
from datetime import datetime
from email.message import EmailMessage

from twilio.rest import Client as TwilioClient

import llm_interface as llm
import patient_profiles as profiles


_TWILIO_SID    = ""
_TWILIO_TOKEN  = ""
_TWILIO_NUMBER = ""

CSV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "appointments.csv")

AVAILABLE_SLOTS = [
    "8:00 AM", "9:00 AM", "10:00 AM", "11:00 AM", "12:00 PM",
    "5:00 PM",  "6:00 PM",  "7:00 PM",  "8:00 PM",
]

DOCTORS = {
    "neurology":   ["Dr Shah",  "Dr Reddy"],
    "general":     ["Dr Mehta", "Dr Singh"],
    "gastro":      ["Dr Patel", "Dr Verma"],
    "dermatology": ["Dr Gupta", "Dr Kapoor"],
}

SYMPTOM_MAP = {
    # English
    "headache":     "neurology",
    "head ache":    "neurology",
    "migraine":     "neurology",
    "head pain":    "neurology",
    "fever":        "general",
    "cold":         "general",
    "flu":          "general",
    "cough":        "general",
    "body ache":    "general",
    "fatigue":      "general",
    "weakness":     "general",
    "sore throat":  "general",
    "back pain":    "general",
    "stomach":      "gastro",
    "stomach pain": "gastro",
    "gas":          "gastro",
    "nausea":       "gastro",
    "vomit":        "gastro",
    "vomiting":     "gastro",
    "acidity":      "gastro",
    "skin":         "dermatology",
    "rash":         "dermatology",
    "itching":      "dermatology",
    "acne":         "dermatology",
    "skin rash":    "dermatology",
    "bleeding":     "general",
    "blood":        "general",
    "injury":       "general",
    "wound":        "general",
    # Hindi
    "sar dard":       "neurology",
    "sir dard":       "neurology",
    "sir dad":        "neurology",
    "bukhar":         "general",
    "bukar":          "general",
    "sardi":          "general",
    "khansi":         "general",
    "kamar dard":     "general",
    "thakaan":        "general",
    "gale mein dard": "general",
    "body dard":      "general",
    "khoon":          "general",
    "pet dard":       "gastro",
    "pet":            "gastro",
    "ulti":           "gastro",
    "chamdi":         "dermatology",
    "khujli":         "dermatology",
    # STT aliases
    "sard":    "neurology",
    "shard":   "neurology",
    "sardine": "neurology",
    "sardin":  "neurology",
}

NUMBER_MAP = {
    "one": 1, "two": 2, "three": 3,
    "ek": 1,  "do": 2,  "teen": 3,
}

_BOOKING_PHRASES = [
    "want to book", "book an appointment", "make an appointment",
    "i want", "i would like", "i need to book", "need a doctor",
    "see a doctor", "visit the doctor", "appointment book",
    "book a slot", "schedule an appointment", "get an appointment",
    "appointment", "doctor chahiye", "doctor se milna", "milna hai",
    "milna chahta", "milna chahti", "appointment chahiye",
    "appointment leni", "appointment lena", "appointment book",
    "appointment karni", "appointment karna", "book karni", "book karna",
    "appointment karwani", "appointment karwana",
    "doctor se milna hai", "doctor ko dikhana", "doctor dikhana",
    "hospital aana", "hospital jana", "checkup", "check up",
    "theek nahi", "bimar", "bimari", "takleef", "problem hai",
    "madad chahiye", "help chahiye", "slot chahiye",
    "date chahiye", "time chahiye",
]

_CANCEL_PHRASES = [
    "cancel", "remove", "delete", "cancel my appointment",
    "want to cancel", "i need to cancel",
    "cancel karni", "cancel karna", "appointment cancel",
    "band karni", "band karna", "hatao", "nahi aana",
    "cancel karwani", "cancel karwana",
]

_RESCHEDULE_PHRASES = [
    "reschedule", "change my appointment", "change the appointment",
    "change date", "change time", "shift appointment",
    "move my appointment", "postpone", "different date",
    "different time", "another date", "new date",
    "date badlo", "time badlo", "appointment badlo",
    "phir se book karna", "reschedule karna", "date change karna",
    "time change karo", "doosri date", "doosra time",
    "appointment aage badao", "waqt badlo",
]

# ── Emergency phrases — trigger GP routing + 102/108 advice ───────────────
_EMERGENCY_PHRASES = [
    # English
    "bleeding", "blood", "can't breathe", "cannot breathe",
    "chest pain", "heart attack", "stroke", "unconscious",
    "fainted", "accident", "severe pain", "breathing problem",
    "not breathing", "emergency", "ambulance", "collapsing",
    "collapsed", "seizure", "overdose", "injured", "injury",
    "wound", "cut myself", "i fell", "i fainted",
    # Hindi
    "khoon", "khoon aa raha", "saans nahi", "saans nahi aa rahi",
    "seene mein dard", "dil ka dora", "behosh", "hosh nahi",
    "accident", "gir gaya", "gir gayi", "bahut dard",
    "ambulance chahiye", "emergency", "saans ruk gayi",
    "chot lagi", "zakhm",
]


def _is_emergency(text: str) -> bool:
    t = text.lower().strip()
    return any(p in t for p in _EMERGENCY_PHRASES)


def _is_booking_phrase(text: str) -> bool:
    t = text.lower().strip()
    return any(p in t for p in _BOOKING_PHRASES)


def _is_cancel_phrase(text: str) -> bool:
    t = text.lower().strip()
    return any(p in t for p in _CANCEL_PHRASES)


def _is_reschedule_phrase(text: str) -> bool:
    t = text.lower().strip()
    return any(p in t for p in _RESCHEDULE_PHRASES)


# ── Name parsing helpers ───────────────────────────────────────────────────

_NOT_A_NAME = {
    "vehicle", "vehicles", "animal", "animals", "table", "tables",
    "cable", "cables", "label", "labels", "stable", "marble",
    "apple", "amazon", "apollo", "above", "about", "public", "republic",
    "hospital", "doctor", "appointment", "booking",
    "hello", "hi", "yes", "no", "okay", "ok", "sure", "please",
    "thanks", "thank", "want", "need", "help", "call", "safe",
    "see", "will", "ill", "can", "be", "get", "let", "go",
    "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "first", "second", "third",
    "silence", "clearly", "obviously", "actually",
    "cancel", "reschedule", "book", "slot",
    "mera", "naam", "hai", "pehla", "aakhiri", "aur", "main",
    "aap", "haan", "nahi", "theek", "bilkul", "kripya",
    "mobile", "phone", "number", "address", "city", "street",
    "india", "delhi", "mumbai", "gujarat", "anand",
    "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday", "january", "february", "march",
    "april", "may", "june", "july", "august", "september",
    "october", "november", "december",
}

# Words that should NEVER be mistaken for a name even in multi-word phrases
_FILLER_WORDS = {
    "my", "name", "is", "first", "last", "am", "this", "its", "it",
    "the", "and", "for", "will", "ill", "be", "see", "safe", "call",
    "can", "get", "let", "go", "an", "a", "of", "in", "on", "at",
    "mera", "naam", "hai", "pehla", "aakhiri", "aur", "main",
    "aap", "haan", "nahi", "theek", "bilkul", "kripya",
    "obviously", "clearly", "public", "republic",
    "apollo", "apple", "amazon", "about", "above",
    "hello", "hi", "yes", "no", "okay", "sure",
    "please", "thanks", "thank", "want", "need",
    "book", "booking", "appointment", "doctor", "hospital",
}


def _is_clean_name(word: str) -> bool:
    """Return True if word is a plausible single name token."""
    return (
        len(word) >= 2
        and word.isalpha()
        and word.lower() not in _NOT_A_NAME
        and word.lower() not in _FILLER_WORDS
    )


def parse_spelled_name(text: str) -> str:
    """
    Robust name extractor v3 — handles every real STT variation:
      - "Rahul"                       → "Rahul"       (plain word)
      - "My name is Abhishek"         → "Abhishek"    (natural speech)
      - "mera naam Rahul hai"         → "Rahul"       (Hindi natural)
      - "A B H I S H E K"            → "Abhishek"    (spelled out)
      - "a, b, h, i, s, h, e, k"     → "Abhishek"    (spelled with commas)
      - "22, g. R. E e n"             → "Green"       (digit noise prefix)
      - "R A H U L"                   → "Rahul"       (uppercase spelled)
      - "S, s"  (STT duplicate)       → ""            (rejected)
      - "Abhishek Soni"               → "Abhishek"    (returns first word; caller
                                                        should ask last name separately)
    """
    if not text:
        return ""

    tl = text.strip().lower()

    # ── 1. Natural-speech extraction (highest priority) ───────────────────
    _NAT_PATS = [
        r"my (?:first |last )?name(?:'s| is)\s+([a-z]+)",
        r"(?:my )?name(?:'s| is)\s+([a-z]+)",
        r"(?:i(?:'m| am)|this is)\s+([a-z]+)",
        r"call me\s+([a-z]+)",
        r"mera naam(?:\s+hai)?\s+([a-z]+)",
        r"naam(?:\s+hai)?\s+([a-z]+)",
        r"naam\s+([a-z]+)\s+hai",
        r"(?:pehla|aakhiri) naam\s+([a-z]+)",
        r"i(?:'m| am)\s+([a-z]+)",
        r"it(?:'s| is)\s+([a-z]+)",
    ]
    for pat in _NAT_PATS:
        m = re.search(pat, tl)
        if m:
            candidate = m.group(1).strip()
            if _is_clean_name(candidate):
                return candidate.title()

    # ── 2. Pure-digit input → reject ──────────────────────────────────────
    if re.sub(r"[^0-9]", "", tl) and not re.sub(r"[^a-z]", "", tl):
        return ""

    # ── 3. Strip leading noise digits ─────────────────────────────────────
    tl = re.sub(r"^\d+[\s,.\-]*", "", tl).strip()

    # ── 4. Tokenise ───────────────────────────────────────────────────────
    tokens = [w for w in re.split(r"[\s,.\-]+", tl) if w]

    if not tokens:
        return ""

    # ── 5. Classify tokens ────────────────────────────────────────────────
    alpha_tokens   = [w for w in tokens if re.match(r"^[a-z]+$", w)]
    single_letters = [w for w in alpha_tokens if len(w) == 1]
    multi_words    = [w for w in alpha_tokens if len(w) > 1]

    # ── 6. Detect spelled-out input ───────────────────────────────────────
    # e.g. "A B H I S H E K" or "r a h u l"
    # Condition: at least 2 alpha tokens AND >= 60% are single letters
    is_spelling = (
        len(alpha_tokens) >= 2
        and len(single_letters) >= len(alpha_tokens) * 0.60
    )

    if is_spelling:
        result = "".join(single_letters).title()
        # Reject STT duplication artifacts like "Ss", "Rr"
        if len(result) >= 2 and len(set(result.lower())) == 1:
            return ""
        if len(result) == 2 and result[0].lower() == result[1].lower():
            return ""
        return result if len(result) >= 2 else ""

    # ── 7. Single clean word — accept directly ────────────────────────────
    # e.g. patient just says "Rahul" or "Soni"
    if len(tokens) == 1 and _is_clean_name(tokens[0]):
        return tokens[0].title()

    # ── 8. Multi-word: pick first clean name candidate ────────────────────
    candidates = [w for w in multi_words if _is_clean_name(w)]
    if candidates:
        return candidates[0].title()

    # ── 9. Last resort: assemble any single-letter run ────────────────────
    if len(single_letters) >= 2:
        result = "".join(single_letters).title()
        if len(result) >= 2 and len(set(result.lower())) == 1:
            return ""
        if len(result) == 2 and result[0].lower() == result[1].lower():
            return ""
        return result if len(result) >= 2 else ""

    return ""


def is_clean_word_name(text: str) -> bool:
    """
    Return True if the raw STT text is already a single clean name word.
    Used to skip the redundant spell-confirmation step.
    e.g. "Rahul" → True,  "R A H U L" → False,  "my name is Rahul" → False
    """
    stripped = text.strip()
    return (
        len(stripped.split()) == 1
        and stripped.isalpha()
        and len(stripped) >= 2
        and stripped.lower() not in _NOT_A_NAME
        and stripped.lower() not in _FILLER_WORDS
    )


def is_spelled_input(text: str) -> bool:
    """Return True if input looks like letter-by-letter spelling: 2+ single alpha tokens."""
    words  = text.strip().lower().split()
    single = [w for w in words if len(w) == 1 and w.isalpha()]
    # Lowered threshold from 3 to 2 so short names like "Ra" are caught
    return len(single) >= 2 and len(single) == len(words)

def format_date(text: str) -> str:
    """
    Normalise a spoken date into "D Month YYYY".
    Strips ordinal suffixes, capitalises month name, and appends the
    correct year.
    """
    from datetime import datetime
    text  = text.strip().rstrip(".,!?")
    
    # Try parsing first to see if it's already a valid date we can format
    dt = _parse_date_from_text(text)
    if dt:
        return dt.strftime("%d %B %Y")
        
    words = text.split()
    result = []
    has_year = False
    for w in words:
        w    = w.strip(".,!?")
        base = w.rstrip("stndrh")
        if base.isdigit():
            num = int(base)
            if num >= 1900:
                has_year = True
                result.append(str(num))
            else:
                # day number — keep clean integer
                result.append(str(int(base)))
        else:
            if "/" in w or "-" in w:
                for p in w.replace("-", "/").split("/"):
                    if p.isdigit() and int(p) >= 1900:
                        has_year = True
            result.append(w.capitalize())
    formatted = " ".join(result)
    # Auto-attach year if missing
    if not has_year:
        from datetime import datetime as _dt
        now = _dt.now()
        formatted = formatted + f" {now.year}"
    return formatted


def _parse_date_from_text(text: str):
    """
    Parse a formatted date string like "5 April 2026", "21 March", or "02/04/2026" into a datetime.
    Returns a datetime object or None. Always attaches the current year if missing.
    """
    from datetime import datetime
    text = text.strip().rstrip(".,!?")
    formats = (
        "%d %B %Y", "%d %b %Y", "%d %B", "%d %b", "%B %d %Y", "%B %d",
        "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d", "%d-%m-%Y"
    )
    for fmt in formats:
        try:
            dt = datetime.strptime(text, fmt)
            # If no year in format, attach current year
            if "%Y" not in fmt:
                now = datetime.now()
                dt = dt.replace(year=now.year)
            return dt
        except ValueError:
            continue
    return None


def is_past_date(text: str) -> bool:
    """Return True if the date is strictly in the past (before today)."""
    from datetime import datetime
    dt = _parse_date_from_text(text)
    if dt is None:
        return False  # can't parse → let is_valid_date handle it
    return dt.date() < datetime.now().date()


def is_valid_date(text: str) -> bool:
    """Return True only if text can be strictly parsed into a real calendar date.
    Random numbers (phone numbers, IDs, etc.) are always rejected."""
    dt = _parse_date_from_text(text)
    # Only accept if a structured date was successfully parsed.
    # We intentionally remove the loose numeric fallback so that random
    # numbers like '8354165731' are never treated as valid dates.
    return dt is not None


def normalize_time(text: str):
    t = text.lower().strip().replace(".", "").replace(",", "")
    hindi_time_map = {
        "subah": "9:00 AM", "suba": "9:00 AM", "savere": "9:00 AM",
        "dopahar": "12:00 PM", "dopaher": "12:00 PM", "duphar": "12:00 PM",
        "shaam": "5:00 PM", "sham": "5:00 PM",
        "raat": "8:00 PM", "rat": "8:00 PM",
    }
    for word, mapped in hindi_time_map.items():
        if word in t:
            return mapped
    suffix = "AM" if "am" in t else ("PM" if "pm" in t else None)
    if not suffix:
        return None
    digits_only = re.sub(r"[:\s]+", "", re.sub(r"[ap]m", "", t))
    m = re.search(r"\d+", digits_only)
    if not m:
        return None
    num  = int(m.group())
    hour = num // 100 if num > 12 else num
    if hour < 1 or hour > 12:
        return None
    return f"{hour}:00 {suffix}"


def parse_number(text: str, doctors: list = None) -> int:
    text_lower = text.lower()
    m = re.search(r"\b\d\b", text_lower)
    if m:
        return int(m.group())
    for word, num in NUMBER_MAP.items():
        if word in text_lower:
            return num
    if doctors:
        for i, doc in enumerate(doctors, 1):
            if doc.split()[-1].lower() in text_lower:
                return i
    return None


def _read_appointments() -> list:
    """Return all appointment rows as a list of dicts, or [] if none."""
    if not os.path.exists(CSV_FILE) or os.stat(CSV_FILE).st_size == 0:
        return []
    import io
    with open(CSV_FILE, "r", newline="", encoding="utf-8") as f:
        content_csv = f.read().strip()
    if not content_csv:
        return []
    reader = csv.DictReader(io.StringIO(content_csv))
    if not reader.fieldnames:
        return []
    return list(reader)


def get_booked_slots(doctor: str, date: str) -> list:
    """
    Return a list of time strings already booked for this doctor on this date.
    E.g. ["9:00 AM", "11:00 AM"]
    """
    booked = []
    norm_date = _parse_date_from_text(date)
    date_str_norm = norm_date.strftime("%d %B %Y") if norm_date else date.strip()

    for row in _read_appointments():
        row_doc  = row.get("Doctor", row.get("doctor", "")).strip()
        row_date = row.get("Date",   row.get("date",   "")).strip()
        row_time = row.get("Time",   row.get("time",   "")).strip()
        row_status = row.get("Status", "active").strip().lower()
        if row_status == "cancelled":
            continue
        
        row_norm_dt = _parse_date_from_text(row_date)
        row_date_str_norm = row_norm_dt.strftime("%d %B %Y") if row_norm_dt else row_date.strip()

        if row_doc == doctor and row_date_str_norm == date_str_norm and row_time:
            booked.append(row_time)
    return booked


def get_available_slots(doctor: str, date: str) -> list:
    """Return AVAILABLE_SLOTS minus already-booked ones for this doctor+date.
    When the date is TODAY, also filter out time slots that have already passed
    based on the current wall-clock time."""
    from datetime import datetime as _dt
    booked = get_booked_slots(doctor, date)
    available = [s for s in AVAILABLE_SLOTS if s not in booked]

    # Extra filter: if booking for today, remove slots whose time has passed
    parsed_date = _parse_date_from_text(date)
    now = _dt.now()
    if parsed_date and parsed_date.date() == now.date():
        current_minutes = now.hour * 60 + now.minute
        def _slot_minutes(slot_str):
            try:
                dt_slot = _dt.strptime(slot_str, "%I:%M %p")
                return dt_slot.hour * 60 + dt_slot.minute
            except ValueError:
                return 9999  # unparseable — keep it
        available = [s for s in available if _slot_minutes(s) > current_minutes]

    return available


def is_slot_available(data: dict) -> bool:
    """Return True if the doctor+date+time combination is not already booked."""
    booked = get_booked_slots(data.get("doctor", ""), data.get("date", ""))
    return data.get("time", "") not in booked


def save_appointment(data: dict):
    FIELDNAMES = ["First Name", "Last Name", "Doctor", "Date", "Time", "Booked At", "Status", "DOB"]

    # Read existing rows (if any) so we can rewrite cleanly when the header is missing
    existing_rows = []
    needs_repair  = False

    if os.path.exists(CSV_FILE) and os.stat(CSV_FILE).st_size > 0:
        with open(CSV_FILE, "r", newline="", encoding="utf-8") as f:
            first_line = f.readline().strip()

        if "First Name" not in first_line and "first" not in first_line.lower():
            # Header is absent — read raw rows and re-add header on rewrite
            needs_repair = True
            with open(CSV_FILE, "r", newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                for row in reader:
                    if row:
                        existing_rows.append(row)
        # else: file has a proper header; we will just append below

    new_row = [
        data.get("first_name", ""), data.get("last_name", ""),
        data.get("doctor", ""),     data.get("date", ""),
        data.get("time", ""),       datetime.now().strftime("%Y-%m-%d %H:%M"),
        "active",                   data.get("dob", "")
    ]

    try:
        if needs_repair:
            # Rewrite the whole file with a proper header + old rows + new row
            with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(FIELDNAMES)
                writer.writerows(existing_rows)
                writer.writerow(new_row)
        else:
            write_header = (not os.path.exists(CSV_FILE) or
                            os.stat(CSV_FILE).st_size == 0)
            with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if write_header:
                    writer.writerow(FIELDNAMES)
                writer.writerow(new_row)
    except PermissionError as e:
        print(f"\n[CRITICAL ERROR] Could not save appointment to {CSV_FILE}!")
        print(f"-> The file is currently OPEN IN ANOTHER PROGRAM (like Microsoft Excel).")
        print(f"-> PLEASE CLOSE EXCEL and try booking the appointment again.\n")
        raise e


def cancel_appointment(fname: str, lname: str) -> bool:
    if not os.path.exists(CSV_FILE):
        return False
    rows, removed = [], False
    with open(CSV_FILE, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return False
        for r in reader:
            fn = r.get("First Name", r.get("first_name", ""))
            ln = r.get("Last Name",  r.get("last_name",  ""))
            if fn.lower() == fname.lower() and ln.lower() == lname.lower():
                removed = True
            else:
                rows.append(r)
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "First Name", "Last Name", "Doctor", "Date", "Time", "Booked At", "Status", "DOB"])
        writer.writeheader()
        writer.writerows(rows)
    return removed


def reschedule_appointment(fname: str, lname: str,
                           new_date: str, new_time: str,
                           new_doctor: str = None) -> bool:
    if not os.path.exists(CSV_FILE):
        return False
    rows, found = [], False
    with open(CSV_FILE, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return False
        for r in reader:
            fn = r.get("First Name", r.get("first_name", ""))
            ln = r.get("Last Name",  r.get("last_name",  ""))
            if not found and fn.lower() == fname.lower() and ln.lower() == lname.lower():
                r["Date"]      = new_date
                r["Time"]      = new_time
                r["Status"]    = "active"
                if new_doctor:
                    r["Doctor"] = new_doctor
                r["Booked At"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                found = True
            rows.append(r)
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "First Name", "Last Name", "Doctor", "Date", "Time", "Booked At", "Status", "DOB"])
        writer.writeheader()
        writer.writerows(rows)
    return found


def send_sms(to_number: str, data: dict, lang: str = "en"):
    to_number = (to_number or "").strip()
    if not to_number:
        print("  [sms] No phone number — skipping SMS.")
        return
    fname  = data.get("first_name", "") or ""
    lname  = data.get("last_name",  "") or ""
    doctor = data.get("doctor",     "") or ""
    date   = data.get("date",       "") or ""
    time_  = data.get("time",       "") or ""
    if lang == "hi":
        body = (
            f"Priya {fname} {lname} ji,\n"
            f"Anand Hospital mein aapki appointment confirm ho gayi hai!\n"
            f"Doctor  : {doctor}\n"
            f"Tarikh  : {date}\n"
            f"Samay   : {time_}\n"
            f"Kripya 10 minute pehle aa jayein. Dhanyavaad!"
        )
    else:
        body = (
            f"Dear {fname} {lname},\n"
            f"Your appointment at Anand Hospital is confirmed!\n"
            f"Doctor : {doctor}\n"
            f"Date   : {date}\n"
            f"Time   : {time_}\n"
            f"Please arrive 10 minutes early. Thank you!"
        )
    print(f"  [sms] Attempting to send to {to_number!r} ...")
    try:
        client  = TwilioClient(_TWILIO_SID, _TWILIO_TOKEN)
        message = client.messages.create(body=body, from_=_TWILIO_NUMBER, to=to_number)
        print(f"  [sms] SUCCESS — SID: {message.sid}  status: {message.status}")
    except Exception as e:
        print(f"  [sms] ERROR sending SMS to {to_number!r}: {type(e).__name__}: {e}")


def send_sms_reschedule(to_number: str, data: dict, lang: str = "en"):
    to_number = (to_number or "").strip()
    if not to_number:
        return
    fname  = data.get("first_name", "") or ""
    doctor = data.get("doctor",     "") or ""
    date   = data.get("date",       "") or ""
    time_  = data.get("time",       "") or ""
    if lang == "hi":
        body = (
            f"Priya {fname} ji, aapki appointment reschedule ho gayi hai.\n"
            f"Nayi tarikh: {date}, samay: {time_}, doctor: {doctor}.\n"
            f"Kripya 10 minute pehle aa jayein. Anand Hospital."
        )
    else:
        body = (
            f"Dear {fname}, your appointment has been rescheduled.\n"
            f"New date: {date}, Time: {time_}, Doctor: {doctor}.\n"
            f"Please arrive 10 minutes early. Anand Hospital."
        )
    try:
        client = TwilioClient(_TWILIO_SID, _TWILIO_TOKEN)
        client.messages.create(body=body, from_=_TWILIO_NUMBER, to=to_number)
        print(f"  [sms-reschedule] sent to {to_number!r}")
    except Exception as e:
        print(f"  [sms-reschedule] ERROR: {e}")


def send_email(subject: str = "Appointments Update",
               body: str = "Updated appointments attached."):
    EMAIL    = ""
    PASSWORD = ""
    TO       = ""
    msg      = EmailMessage()
    msg["Subject"] = subject
    msg["From"]    = EMAIL
    msg["To"]      = TO
    msg.set_content(body)
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, "rb") as f:
            msg.add_attachment(f.read(), maintype="application",
                               subtype="csv", filename="appointments.csv")
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as s:
            s.login(EMAIL, PASSWORD)
            s.send_message(msg)
            print(f"  [email] Sent to {TO}")
    except Exception as e:
        print(f"  [email] ERROR: {e}")
        raise


# ══════════════════════════════════════════════════════════════════════════
#  HospitalAgent — FIXED v4
# ══════════════════════════════════════════════════════════════════════════

class HospitalAgent:

    def __init__(self, call_id: str = ''):
        self._call_id = call_id
        self.reset(call_id)

    def reset(self, call_id: str = ''):
        self.state        = "CHOOSE_LANG"
        self.lang         = None
        self.temp_doctors = []
        self.data = {
            "first_name": None,
            "last_name":  None,
            "doctor":     None,
            "date":       None,
            "time":       None,
            "phone":      None,
            "dob":        None,
        }
        self._profile_loaded            = False
        self._new_patient               = True
        self._reschedule_data           = {}
        self._tentative_profile         = None
        self._stored_profile_firstname  = ""
        self._stored_profile_lastname   = ""
        self._csv_matches               = []   # holds CSV rows during VERIFY_CSV_DOB
        llm.reset_history(call_id)

    def set_language(self, lang: str):
        self.lang  = lang
        self.state = "START"
        llm.set_lang(lang)

    def set_phone(self, phone: str):
        """Store phone. Pre-load profile silently — only fires greeting in ASK_FIRST."""
        self.data["phone"] = phone
        if not phone:
            return
        prof = profiles.get_profile(phone)
        if prof:
            self._profile_loaded           = True
            self._new_patient              = False
            self._stored_profile_firstname = prof.get("first_name", "")
            self._stored_profile_lastname  = prof.get("last_name",  "")
            self.data["dob"]               = prof.get("dob", "")

    def load_profile_by_dob(self, first_name: str, dob: str):
        prof = profiles.find_profile_by_name_dob(first_name, dob)
        if prof:
            self.data["last_name"]         = prof.get("last_name", "")
            self.data["dob"]               = dob
            self._profile_loaded           = True
            self._new_patient              = False
            self._stored_profile_firstname = first_name
            self._stored_profile_lastname  = prof.get("last_name", "")
            print(f"  [profile] Verified: {first_name} {self.data['last_name']} DOB={dob}")
            return prof
        return None

    def _t(self, en: str, hi: str) -> str:
        return hi if self.lang == "hi" else en

    def _gen(self, task: str, hint: str, max_tokens: int = 30) -> str:
        llm.set_context(self.data)
        return llm.generate_response(task, hint, max_new_tokens=max_tokens)

    def get_repeat_prompt(self) -> str:
        hi = self.lang == "hi"
        s  = self.state
        d1 = self.temp_doctors[0] if self.temp_doctors else "doctor 1"
        d2 = self.temp_doctors[1] if len(self.temp_doctors) > 1 else "doctor 2"
        slots = ", ".join(AVAILABLE_SLOTS)

        if s == "START":
            return ("Kya aap appointment book karni hai, reschedule karni hai, ya cancel karni hai?"
                    if hi else
                    "Would you like to book, reschedule, or cancel an appointment?")
        if s == "ASK_FIRST":
            return ("Apna pehla naam batayein." if hi else "Please say your first name.")
        if s == "SPELL_FIRST":
            return ("Apna pehla naam ek ek akshar mein bolein. Jaise: A M I T."
                    if hi else
                    "Please spell your first name letter by letter. For example: A M I T.")
        if s == "ASK_LAST":
            return ("Apna aakhiri naam batayein." if hi else "Please say your last name.")
        if s == "SPELL_LAST":
            return ("Apna aakhiri naam ek ek akshar mein bolein. Jaise: S H A H."
                    if hi else
                    "Please spell your last name letter by letter. For example: S H A H.")
        if s == "ASK_DOB":
            return ("Apni janm tithi batayein. Jaise: 21 March 1990."
                    if hi else
                    "Please say your date of birth. For example: 21 March 1990.")
        if s == "VERIFY_PROFILE_DOB":
            return ("Apni janm tithi batayein. Jaise: 21 March 1990."
                    if hi else
                    "Please say your date of birth to verify. For example: 21 March 1990.")
        if s == "VERIFY_CSV_DOB":
            return ("Pehchaan ke liye apni janm tithi batayein. Jaise: 21 March 1990."
                    if hi else
                    "To confirm your identity, please say your date of birth. For example: 21 March 1990.")
        if s == "GREET_RETURNING":
            return ("Kya appointment book karni hai, reschedule karni hai, ya cancel?"
                    if hi else
                    "Would you like to book, reschedule, or cancel?")
        if s == "ASK_SYMPTOM":
            return ("Apna lakshan batayein. Jaise: sar dard, bukhar, ya pet dard."
                    if hi else
                    "Please describe your symptom. For example: headache, fever, or stomach pain.")
        if s == "SELECT_DOCTOR":
            return (f"{d1} ke liye 1 kahein, ya {d2} ke liye 2 kahein."
                    if hi else
                    f"Please say 1 for {d1} or 2 for {d2}.")
        if s == "ASK_DATE":
            return ("Kaunsi date ko aana chahenge? Jaise: 21 March."
                    if hi else
                    "Please say your preferred date. For example: 21 March.")
        if s == "ASK_TIME":
            return (f"Kaunsa samay chahiye? Upalabdh slots: {slots}."
                    if hi else
                    f"Please choose a time. Available slots: {slots}.")
        if s == "CONFIRM":
            return ("Haan kahein confirm ke liye, ya nahi kahein cancel ke liye."
                    if hi else
                    "Please say yes to confirm or no to cancel.")
        if s in ("CANCEL_FIRST", "CANCEL_LAST"):
            return "Apna naam batayein." if hi else "Please say your name."
        if s in ("CANCEL_SPELL_FIRST", "CANCEL_SPELL_LAST"):
            return "Apna naam ek ek akshar mein bolein." if hi else "Please spell your name letter by letter."
        if s in ("RESCHEDULE_FIRST", "RESCHEDULE_LAST"):
            return "Apna naam batayein." if hi else "Please say your name."
        if s in ("RESCHEDULE_SPELL_FIRST", "RESCHEDULE_SPELL_LAST"):
            return "Apna naam ek ek akshar mein bolein." if hi else "Please spell your name letter by letter."
        if s == "RESCHEDULE_DATE":
            return ("Nayi date batayein. Jaise: 10 May."
                    if hi else
                    "Please say a new date. For example: 10 May.")
        if s == "RESCHEDULE_TIME":
            return (f"Nayi time batayein. Slots: {slots}."
                    if hi else
                    f"Please choose a new time. Available slots: {slots}.")
        if s == "RESCHEDULE_CONFIRM":
            return ("Haan kahein confirm ke liye, ya nahi kahein cancel ke liye."
                    if hi else
                    "Please say yes to confirm or no to cancel.")
        return "Kripya dobara bolein." if hi else "Please speak again."

    def _detect_symptom(self, text: str):
        import difflib
        cleaned = text.lower().strip().rstrip(".,!?")
        for filler in ["i have ", "i am having ", "i am feeling ",
                       "mujhe ", "mujhe hai ", "the ", "main ",
                       "mere ko ", "suffering from ", "feeling ",
                       "mujhe ho raha hai", "ho rahi hai"]:
            cleaned = cleaned.replace(filler, " ")
        cleaned = " ".join(cleaned.split())

        for k in sorted(SYMPTOM_MAP.keys(), key=len, reverse=True):
            if k in cleaned or k in text.lower():
                return k

        words = cleaned.split()
        for word in words:
            if word in SYMPTOM_MAP:
                return word
            for k in sorted(SYMPTOM_MAP.keys(), key=len, reverse=True):
                if len(word) >= 3 and (word in k or k in word):
                    return k

        if len(words) <= 2:
            matches = difflib.get_close_matches(
                cleaned, list(SYMPTOM_MAP.keys()), n=1, cutoff=0.65)
            if matches:
                return matches[0]
        return None

    def _detect_language(self, text: str):
        t = text.lower().strip()
        if any(w in t for w in ["english", "1", "one", "angreji"]):
            return "en"
        if any(w in t for w in ["hindi", "2", "two", "hindi mein", "hindi me"]):
            return "hi"
        return None

    def _is_yes(self, text: str) -> bool:
        yes_words = [
            "yes", "confirm", "correct", "ok", "okay", "sure",
            "go ahead", "please", "yep", "yeah", "right",
            "haan", "han", "haa", "bilkul", "bilkula",
            "theek hai", "theek", "thik", "thik hai",
            "acha", "accha", "ache", "aage", "sahi", "haan ji", "ji",
        ]
        s = text.strip()
        import re as _re
        _bare_ha = bool(_re.match(r'^ha[.!?]?\s*$', s, _re.IGNORECASE))
        for w in yes_words:
            pat = r'(?<![a-z])' + _re.escape(w) + r'(?![a-z])'
            if _re.search(pat, s, _re.IGNORECASE):
                return True
        return _bare_ha

    def _is_no(self, text: str) -> bool:
        no_words = [
            "no", "cancel", "don't", "dont", "wrong",
            "change", "nope", "not",
            "nahi", "nahin", "band", "mat karo", "mat",
            "rok", "roko", "galat", "badlo",
        ]
        s = text.strip()
        import re as _re
        for w in no_words:
            pat = r'(?<![a-z])' + _re.escape(w) + r'(?![a-z])'
            if _re.search(pat, s, _re.IGNORECASE):
                return True
        return False

    # ════════════════════════════════════════════════════════════════════
    #  Correction helpers
    # ════════════════════════════════════════════════════════════════════

    # Patterns that signal a name correction mid-flow
    _NAME_CORRECTION_PATS = [
        r"(?:wait|actually|hold on|no)[,\s]+(?:my name is|i am|i'm|naam hai)\s+([a-z]+)",
        r"(?:my name is|i am|i'm|naam hai|naam)\s+([a-z]+)\s*$",
        r"(?:call me|it's|its)\s+([a-z]+)\s*$",
    ]

    def _check_name_correction(self, text: str) -> str:
        """Return corrected first name if user says 'wait my name is X' etc., else empty string."""
        t = text.lower().strip()
        import re as _re
        for pat in self._NAME_CORRECTION_PATS:
            m = _re.search(pat, t)
            if m:
                candidate = m.group(1).strip()
                if _is_clean_name(candidate):
                    return candidate.title()
        return ""

    def _find_in_appointments(self, first_name: str, last_name: str) -> dict:
        """
        Search appointments.csv for a patient by first + last name (case-insensitive).
        Returns the FIRST matching row dict (with DOB if present) or None.
        Only considers active (non-cancelled) appointments.
        """
        matches = self._find_all_in_appointments(first_name, last_name)
        return matches[0] if matches else None

    def _find_all_in_appointments(self, first_name: str, last_name: str) -> list:
        """
        Return ALL active appointment rows matching first + last name (case-insensitive).
        Used to detect duplicate names and enforce DOB verification.
        """
        fn_lower = first_name.strip().lower()
        ln_lower = last_name.strip().lower()
        results = []
        for row in _read_appointments():
            row_fn = (row.get("First Name", row.get("first_name", "")) or "").strip().lower()
            row_ln = (row.get("Last Name",  row.get("last_name",  "")) or "").strip().lower()
            row_status = (row.get("Status", "active") or "active").strip().lower()
            if row_status == "cancelled":
                continue
            if row_fn == fn_lower and row_ln == ln_lower:
                results.append(row)
        return results

    def _try_date_correction(self, text: str) -> str:
        """
        Return a formatted date if user says 'actually make it Thursday' /
        'change it to 25 April' / 'make it next Monday' etc.
        Returns empty string if no correction detected.
        """
        import re as _re
        t = text.lower().strip()
        # Trigger words that indicate a date/day change request
        _triggers = [
            r"(?:actually|make it|change it to|change to|how about|let's do|let us do|"  
            r"reschedule to|move to|shift to|book for)\s+(.+)",
            r"(?:thursday|friday|monday|tuesday|wednesday|saturday|sunday)",
        ]
        # Day-of-week → next occurrence mapping
        _DOW = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6,
        }
        from datetime import datetime as _dt, timedelta as _td
        # Check for day-of-week mention
        for day_name, dow in _DOW.items():
            if day_name in t:
                today = _dt.now()
                days_ahead = (dow - today.weekday() + 7) % 7
                if days_ahead == 0:
                    days_ahead = 7  # next week if same day
                target = today + _td(days=days_ahead)
                return target.strftime("%d %B %Y")
        # Check for explicit date after trigger word
        for pat in _triggers[:1]:
            m = _re.search(pat, t)
            if m:
                candidate = m.group(1).strip()
                try:
                    fmt = format_date(candidate)
                    if is_valid_date(fmt):
                        return fmt
                except Exception:
                    pass
        return ""

    def _try_time_correction(self, text: str) -> str:
        """
        Return a normalized time string if user says 'actually at 10 am' /
        'make it 5 pm' / 'change to morning' etc.
        Returns empty string if nothing found.
        """
        import re as _re
        t = text.lower().strip()
        _triggers = [
            r"(?:actually|make it|change it to|change to|how about|at)\s+(.+)",
        ]
        for pat in _triggers:
            m = _re.search(pat, t)
            if m:
                candidate = m.group(1).strip()
                result = normalize_time(candidate)
                if result:
                    return result
        # Also try plain time parse on the whole text
        result = normalize_time(text)
        if result:
            return result
        return ""

    # ════════════════════════════════════════════════════════════════════
    #  handle() — main dispatcher
    # ════════════════════════════════════════════════════════════════════

    def handle(self, user_input: str) -> str:
        llm.add_user_turn(user_input)
        text = user_input.lower().strip()

        # ── Universal mid-flow correction handler ─────────────────────────
        # Intercepts unexpected corrections at any state AFTER language is set
        if self.state not in (
            "CHOOSE_LANG", "START", "ASK_FIRST", "SPELL_FIRST",
            "CANCEL_FIRST", "CANCEL_SPELL_FIRST", "CANCEL_LAST", "CANCEL_SPELL_LAST",
            "RESCHEDULE_FIRST", "RESCHEDULE_SPELL_FIRST",
            "RESCHEDULE_LAST", "RESCHEDULE_SPELL_LAST",
            "VERIFY_CSV_DOB", "VERIFY_PROFILE_DOB",
        ) and self.lang:
            # 1. Name correction: "wait my name is Abhishek"
            name_fix = self._check_name_correction(user_input)
            if name_fix and self.state in (
                "ASK_LAST", "SPELL_LAST", "ASK_DOB", "VERIFY_PROFILE_DOB",
                "ASK_SYMPTOM", "SELECT_DOCTOR", "ASK_DATE", "ASK_TIME", "CONFIRM",
                "GREET_RETURNING",
            ):
                # Restart booking from first name
                old_state = self.state
                self.data["first_name"] = name_fix
                self.data["last_name"]  = None
                self.data["dob"]        = None
                self.data["doctor"]     = None
                self.data["date"]       = None
                self.data["time"]       = None
                self._profile_loaded    = False
                self._new_patient       = True
                self.state = "SPELL_FIRST"
                print(f"  [correction] Name corrected to {name_fix!r} from state={old_state}")
                hint = self._t(
                    f"No problem! Let me update that. Could you spell {name_fix} letter by letter to confirm?",
                    f"Bilkul! {name_fix} — kripya ek ek akshar mein spell karein confirm karne ke liye."
                )
                return self._gen(f"mid-flow name correction to {name_fix}", hint)

            # 2. Date correction: "actually make it Thursday" / "change to 25 April"
            if self.state in ("ASK_DATE", "ASK_TIME", "CONFIRM", "RESCHEDULE_DATE", "RESCHEDULE_TIME", "RESCHEDULE_CONFIRM"):
                date_fix = self._try_date_correction(user_input)
                if date_fix and self.state in ("ASK_TIME", "CONFIRM"):
                    if not is_past_date(date_fix):
                        self.data["date"] = date_fix
                        self.data["time"] = None
                        self.state = "ASK_TIME"
                        avail = get_available_slots(self.data.get("doctor", ""), date_fix)
                        slots_str = ", ".join(avail) if avail else "no slots available"
                        print(f"  [correction] Date changed to {date_fix!r}")
                        hint = self._t(
                            f"No problem! I have updated the date to {date_fix}. "
                            f"Please choose a time. Available slots: {slots_str}.",
                            f"Bilkul! Tarikh {date_fix} kar di. "
                            f"Kaunsa samay chahiye? Upalabdh slots: {slots_str}."
                        )
                        return self._gen(f"mid-flow date correction to {date_fix}", hint)

            # 3. Time correction: "make it at 10 am" / "actually 5 pm"
            if self.state in ("ASK_TIME", "CONFIRM"):
                time_fix = self._try_time_correction(user_input)
                if time_fix and time_fix in AVAILABLE_SLOTS:
                    self.data["time"] = time_fix
                    # Check availability
                    if not is_slot_available(self.data):
                        self.data["time"] = None
                        avail = get_available_slots(self.data.get("doctor", ""), self.data.get("date", ""))
                        slots_str = ", ".join(avail) if avail else "no slots"
                        hint = self._t(
                            f"I am sorry, {time_fix} is already taken. Available: {slots_str}.",
                            f"Kshama karein, {time_fix} pehle se book hai. Upalabdh: {slots_str}."
                        )
                        return self._gen("time correction: slot taken", hint)
                    self.state = "CONFIRM"
                    d = self.data
                    print(f"  [correction] Time changed to {time_fix!r}")
                    hint = self._t(
                        f"Updated! Your appointment: {d['doctor']} on {d['date']} at {time_fix}. "
                        f"Shall I confirm? Please say yes or no.",
                        f"Theek hai! Appointment: {d['doctor']} ke saath {d['date']} ko {time_fix} baje. "
                        f"Confirm karein? Haan ya nahi."
                    )
                    return self._gen(f"mid-flow time correction to {time_fix}", hint)

        # ── EMERGENCY / random urgent complaint ──────────────────────────
        # Instead of just warning, we offer to book with a General Physician
        # so the user can still get help through the system.
        if _is_emergency(text):
            d1, d2 = DOCTORS["general"]
            self.temp_doctors = DOCTORS["general"]
            # Advise to call 102/108 AND offer to book GP
            if self.lang == "hi":
                advice = (
                    "Yeh ek gambhir sthiti lag rahi hai. "
                    "Kripya turant 102 ya 108 par ambulance ke liye call karein. "
                    f"Agar aap intezaar kar sakte hain, main aapko General Physician "
                    f"{d1} ya {d2} se appointment de sakta hoon. "
                    f"{d1} ke liye 1 kahein, ya {d2} ke liye 2 kahein."
                )
            else:
                advice = (
                    "This sounds serious. Please call 102 or 108 immediately for an ambulance. "
                    f"If you are able to wait, I can book you with our General Physician. "
                    f"Say 1 for {d1} or 2 for {d2}."
                )
            # We move to SELECT_DOCTOR so if they choose, we can continue booking
            # But we need a name first — if none, stay at emergency advice
            if self.data.get("first_name"):
                self.state = "SELECT_DOCTOR"
            else:
                # No name yet — give advice and go to START so they can proceed
                self.state = "START"
            return self._gen("emergency detected, advising 102/108 + offering GP booking", advice, max_tokens=10)

        # ── CHOOSE LANGUAGE ───────────────────────────────────────────────
        if self.state == "CHOOSE_LANG":
            if self.lang in ("en", "hi"):
                self.state = "START"
            else:
                lang = self._detect_language(user_input)
                if lang == "en":
                    self.lang  = "en"
                    llm.set_lang("en")
                    self.state = "START"
                    hint = "Thank you for choosing English. How may I assist you today?"
                    return self._gen("language confirmed English, greeting", hint)
                if lang == "hi":
                    self.lang  = "hi"
                    llm.set_lang("hi")
                    self.state = "START"
                    hint = "Shukriya. Hum Hindi mein baat karenge. Main aapki kaise madad kar sakta hoon?"
                    return self._gen("language confirmed Hindi, greeting", hint)
                hint = "I am sorry, I did not catch that. Please say English or Hindi."
                return self._gen("asking patient to choose language", hint)

        # ── START: detect intent ──────────────────────────────────────────
        if self.state == "START":
            t_lower = text.lower().strip()
            is_cancel     = _is_cancel_phrase(t_lower)
            is_reschedule = _is_reschedule_phrase(t_lower)
            is_book       = (
                _is_booking_phrase(t_lower)
                or t_lower in ("appointment", "appointment.", "appointment!")
                or (self.lang == "hi" and any(w in t_lower for w in [
                    "appointment", "doctor", "milna", "booking",
                    "bimari", "bimar", "takleef", "problem", "dard",
                    "bukhar", "khansi", "pet", "sar", "sir",
                ]))
            )

            if is_reschedule:
                self.state = "RESCHEDULE_FIRST"
                hint = self._t(
                    "I can help you reschedule your appointment. May I have your first name please?",
                    "Main aapki appointment reschedule karne mein madad karoonga. Apna pehla naam batayein."
                )
                return self._gen("reschedule intent, asking first name", hint)

            if is_cancel:
                self.state = "CANCEL_FIRST"
                hint = self._t(
                    "Of course. May I have your first name please?",
                    "Bilkul. Apna pehla naam batayein."
                )
                return self._gen("patient wants to cancel, asking for first name", hint)

            if is_book:
                # Always ask for first name — profile recognition fires in ASK_FIRST
                # after the patient actually speaks their name.  We never skip name
                # collection based on phone number alone.
                self.state = "ASK_FIRST"
                hint = self._t(
                    "I would be happy to help. What is your first name please?",
                    "Main khushi se madad karoonga. Apna pehla naam batayein."
                )
                return self._gen("patient wants to book, asking for first name", hint)

            info = llm.extract_info(user_input)
            if info.get("intent") == "BOOK":
                # Same rule — always go through ASK_FIRST
                self.state = "ASK_FIRST"
                hint = self._t(
                    "I would be happy to help. What is your first name please?",
                    "Main khushi se madad karoonga. Apna pehla naam batayein."
                )
                return self._gen("patient wants to book, asking for first name", hint)

            if info.get("intent") == "CANCEL":
                self.state = "CANCEL_FIRST"
                hint = self._t(
                    "Of course. May I have your first name please?",
                    "Bilkul. Apna pehla naam batayein."
                )
                return self._gen("patient wants to cancel, asking for first name", hint)

            # Fallthrough — could be a symptom or vague complaint
            single_word = len(text.split()) <= 2
            looks_like_noise = any(w in text for w in [
                "hello", "hi", "haan", "yes", "no", "nahi", "okay", "ok"
            ])
            if single_word and not looks_like_noise:
                # Even vague/single-word inputs go through ASK_FIRST
                self.state = "ASK_FIRST"
                hint = self._t(
                    "I would be happy to help you book an appointment. What is your first name please?",
                    "Main aapki appointment book karne mein madad karoonga. Apna pehla naam batayein."
                )
                return self._gen("implicit booking intent, asking first name", hint)

            hint = self._t(
                "Would you like to book, reschedule, or cancel an appointment?",
                "Kya aap appointment book karni hai, reschedule karni hai, ya cancel karni hai?"
            )
            return self._gen("patient intent unclear, asking to clarify", hint)


        # ── GREET_RETURNING: returning patient has been welcomed ──────────
        elif self.state == "GREET_RETURNING":
            fn = self.data.get("first_name", "")
            ln = self.data.get("last_name",  "") or self._stored_profile_lastname
            t_lower = text.lower().strip()

            is_cancel     = _is_cancel_phrase(t_lower)
            is_reschedule = _is_reschedule_phrase(t_lower)
            is_book       = _is_booking_phrase(t_lower) or self._is_yes(text)

            if is_cancel:
                self.state             = "CANCEL_LAST"
                self.data["last_name"] = ln
                hint = self._t(
                    f"Of course, {fn}. Let me look up your appointment and cancel it right away.",
                    f"Bilkul, {fn} ji. Main aapki appointment dhundh kar abhi cancel karta hoon."
                )
                return self._gen(f"returning patient {fn} wants cancel — profile loaded", hint)

            if is_reschedule:
                self.state             = "RESCHEDULE_DATE"
                self.data["last_name"] = ln
                hint = self._t(
                    f"Of course, {fn}. What new date would you prefer for your appointment?",
                    f"Bilkul, {fn} ji. Kaunsi nayi date chahiye aapko?"
                )
                return self._gen(f"returning patient {fn} wants reschedule — asking new date", hint)

            if is_book or not t_lower:
                self.state = "ASK_SYMPTOM"
                hint = self._t(
                    f"What symptoms are you experiencing today, {fn}?",
                    f"{fn} ji, aaj aapko kya takleef ho rahi hai?"
                )
                return self._gen(f"returning patient {fn} wants booking — asking symptom", hint)

            hint = self._t(
                f"I am sorry, {fn}, I did not quite catch that. "
                f"Would you like to book, reschedule, or cancel?",
                f"Kshama karein, {fn} ji, kuch samajh nahi aaya. "
                f"Kya appointment book karni hai, reschedule karni hai, ya cancel?"
            )
            return self._gen("returning patient — intent unclear", hint)

        # ── ASK_FIRST: collect first name ─────────────────────────────────
        # Flow:
        #   clean single word  → accept, check profile, go to SPELL_FIRST for confirmation
        #   spelled letters    → assemble, check profile
        #   natural speech     → extract, check profile
        #   unclear            → ask to spell
        elif self.state == "ASK_FIRST":
            # Try to extract the name from what the user actually said
            spoken = parse_spelled_name(user_input)
            if spoken and len(spoken.strip()) >= 2:
                # Got a name — store it and ask to spell to confirm
                self.data["first_name"] = spoken
                self.state = "SPELL_FIRST"
                hint = self._t(
                    f"Thank you, {spoken}. Could you please spell your first name letter by letter? For example: A M I T.",
                    f"Shukriya, {spoken}. Kripya apna pehla naam ek ek akshar karke spell karein. Jaise: A M I T."
                )
                return self._gen("got first name, asking to spell for confirmation", hint)
            else:
                # Could not parse a name — go straight to SPELL_FIRST
                self.state = "SPELL_FIRST"
                hint = self._t(
                    "Could you please spell your first name letter by letter? For example: A M I T.",
                    "Kripya apna pehla naam ek ek akshar karke spell karein. Jaise: A M I T."
                )
                return self._gen("asking to spell first name", hint)

        elif self.state == "SPELL_FIRST":
            # Check if user is correcting their name mid-flow: "wait my name is Abhishek"
            correction = self._check_name_correction(user_input)
            if correction:
                spoken = correction
                self.data["first_name"] = spoken
                # Reset last name / dob if user is starting over
                self.data["last_name"] = None
                hint = self._t(
                    f"No problem. So your first name is {spoken}. Could you please spell it to confirm? For example: A M I T.",
                    f"Theek hai. Toh aapka pehla naam {spoken} hai. Kripya confirm karne ke liye spell karein. Jaise: A M I T."
                )
                return self._gen(f"name correction received: {spoken}, re-asking spell", hint)

            name = parse_spelled_name(user_input)
            if not name or len(name.strip()) < 2:
                hint = self._t(
                    "I did not catch your name. Please spell it letter by letter. For example: R A H U L.",
                    "Naam samajh nahi aaya. Kripya ek ek akshar mein bolein. Jaise: R A H U L."
                )
                return self._gen("first name spelling unclear, asking to spell", hint)

            self.data["first_name"] = name

            # ── PROFILE RECOGNITION ───────────────────────────────────────
            if self._profile_loaded:
                stored_fn = (self._stored_profile_firstname or "").strip().lower()
                spoken_fn = name.strip().lower()
                if stored_fn and stored_fn == spoken_fn:
                    # First name matches phone profile — verify DOB before welcoming back
                    self._tentative_profile = profiles.get_profile(self.data.get("phone", ""))
                    fn = name
                    self.state = "VERIFY_PROFILE_DOB"
                    hint = self._t(
                        f"Hello, {fn}! I have your profile on file. "
                        f"For security, could you please confirm your date of birth? "
                        f"For example: 21 March 1990.",
                        f"Namaste, {fn} ji! Aapki profile mil gayi. "
                        f"Suraksha ke liye apni janm tithi confirm karein. Jaise: 21 March 1990."
                    )
                    return self._gen(f"name matches phone profile — asking DOB to verify before welcoming {fn}", hint)
                else:
                    # Name mismatch — treat as new patient
                    self._profile_loaded           = False
                    self._new_patient              = True
                    self.data["last_name"]         = None
                    self.data["dob"]               = None
                    self._stored_profile_firstname = ""
                    self._stored_profile_lastname  = ""

            if not self._profile_loaded:
                # Check if ANY profile exists with this first name (unique or not)
                prof = profiles.find_profile_by_firstname(name)
                has_any = profiles._load()  # check raw data for any match
                any_match = any(
                    (v.get("first_name", "") or "").strip().lower() == name.strip().lower()
                    for v in has_any.values()
                )
                if any_match:
                    self._tentative_profile = prof  # may be None if ambiguous
                    self.state              = "VERIFY_PROFILE_DOB"
                    hint = self._t(
                        f"Hello, {name}! I have your profile on file. "
                        f"Could you please confirm your date of birth to verify? "
                        f"For example: 20 April 2003.",
                        f"Namaste, {name} ji! Aapki profile mil gayi. "
                        f"Pehchaan ke liye apni janm tithi batayein. Jaise: 20 April 2003."
                    )
                    return self._gen(f"found profile by first name {name} — asking DOB to verify", hint)

            self.state = "ASK_LAST"
            hint = self._t(
                f"Thank you, {name}. And your last name please?",
                f"Shukriya, {name}. Apna aakhiri naam batayein."
            )
            return self._gen(f"got first name {name}, asking for last name", hint)

        # ── VERIFY_PROFILE_DOB ────────────────────────────────────────────
        elif self.state == "VERIFY_PROFILE_DOB":
            from patient_profiles import validate_dob
            dob = validate_dob(user_input)
            fn  = self.data.get("first_name", "")
            if dob:
                prof = self.load_profile_by_dob(fn, dob)
                if prof:
                    fn = self.data["first_name"]
                    self.state = "GREET_RETURNING"
                    hint = self._t(
                        f"Welcome back, {fn}! Great to have you with us again. "
                        f"Would you like to book a new appointment, reschedule, or cancel?",
                        f"Dobara milke khushi hui, {fn} ji! "
                        f"Kya nayi appointment book karni hai, reschedule karni hai, ya cancel?"
                    )
                    return self._gen(f"DOB verified for {fn}, asking intent", hint)
                else:
                    # DOB does not match any existing profile with this first name
                    # → treat as a NEW patient, but still need their DOB for the new profile
                    self._tentative_profile = None
                    self._new_patient       = True
                    self.state              = "ASK_LAST"
                    # Store the entered DOB as the new patient's DOB
                    self.data["dob"]        = dob
                    hint = self._t(
                        f"I could not match that date of birth for {fn}. "
                        f"No problem — let me create a new profile for you. "
                        f"Could I have your last name please?",
                        f"Kshama karein, {fn} ji ki profile se woh janm tithi match nahi hui. "
                        f"Hum aapki nayi profile banate hain. Apna aakhiri naam batayein."
                    )
                    return self._gen("DOB mismatch — new patient, asking last name (DOB already stored)", hint)
            hint = self._t(
                "I am sorry, I could not catch that date. "
                "Please say your date of birth clearly — for example: 21 March 1990.",
                "Kshama karein, woh date samajh nahi aayi. "
                "Kripya apni janm tithi clearly bolein — jaise: 21 March 1990."
            )
            return self._gen("VERIFY_PROFILE_DOB: DOB not understood", hint)

        # ── SPELL_FIRST ── (fallback: only reached if VERIFY_PROFILE_DOB DOB mismatch
        #                    wanted an explicit re-spell, kept for safety) ──
        elif self.state == "SPELL_FIRST":
            spelled = parse_spelled_name(user_input)
            if not spelled or len(spelled) < 2:
                hint = self._t(
                    "Please spell your first name letter by letter. For example: A M I T.",
                    "Apna pehla naam ek ek akshar mein bolein. Jaise: A M I T."
                )
                return self._gen("spelling of first name unclear, asking again", hint)
            self.data["first_name"] = spelled
            self.state = "ASK_LAST"
            hint = self._t(
                f"Thank you, {spelled}. And your last name please? Please spell it letter by letter.",
                f"Shukriya, {spelled}. Apna aakhiri naam batayein, aur kripya isey ek ek akshar karke spell karein."
            )
            return self._gen(f"confirmed spelled first name {spelled}, asking for last name", hint)

        # ── ASK_LAST ──────────────────────────────────────────────────────
        # Same logic as ASK_FIRST: accept clean word directly, no redundant spelling step
        elif self.state == "ASK_LAST":
            self.state = "SPELL_LAST"
            hint = self._t(
                "Thank you. Could you please spell your last name letter by letter? For example: S H A H.",
                "Shukriya. Kripya apna aakhiri naam ek ek akshar karke spell karein. Jaise: S H A H."
            )
            return self._gen("asking to spell last name", hint)

        elif self.state == "SPELL_LAST":
            name = parse_spelled_name(user_input)
            if not name or len(name.strip()) < 2:
                hint = self._t(
                    "I did not catch your last name. Please spell it letter by letter. For example: S H A H.",
                    "Aakhiri naam samajh nahi aaya. Kripya ek ek akshar mein bolein. Jaise: S H A H."
                )
                return self._gen("last name spelling not understood, asking to spell", hint)

            self.data["last_name"] = name
            fn = self.data.get("first_name", "")

            # ── Check appointments.csv for returning patients who aren't in profiles.json ──
            # This catches patients like Riya Rathod who booked via admin or a prior system
            # and therefore exist in appointments.csv but not profiles.json.
            if self._new_patient and not self.data.get("dob"):
                csv_matches = self._find_all_in_appointments(fn, name)
                if csv_matches:
                    # Found in CSV — ALWAYS verify DOB before granting returning-patient access.
                    # This prevents confusion when two patients share the same first + last name.
                    self._csv_matches = csv_matches  # store for VERIFY_CSV_DOB handler
                    has_duplicate = len(csv_matches) > 1
                    print(
                        f"  [profile] Found {len(csv_matches)} record(s) for {fn} {name} in appointments.csv "
                        f"— asking DOB to {'disambiguate' if has_duplicate else 'verify'}"
                    )
                    self.state = "VERIFY_CSV_DOB"
                    hint = self._t(
                        f"I found a record for {fn} {name}. "
                        f"To confirm your identity, could you please tell me your date of birth? "
                        f"For example: 21 March 1990.",
                        f"{fn} {name} ji ki record mil gayi. "
                        f"Pehchaan ke liye apni janm tithi batayein. Jaise: 21 March 1990."
                    )
                    return self._gen(
                        f"found {fn} {name} in CSV ({'duplicate' if has_duplicate else 'single'}) — asking DOB to verify",
                        hint
                    )

            # If still new patient (no CSV match either), collect DOB for profile creation
            # BUT skip if DOB was already captured during VERIFY_PROFILE_DOB mismatch
            if self._new_patient and not self.data.get("dob"):
                self.state = "ASK_DOB"
                hint = self._t(
                    f"Thank you, {fn} {name}. "
                    f"To complete your profile, please share your date of birth. "
                    f"For example: 21 March 1990.",
                    f"Shukriya, {fn} {name} ji. "
                    f"Profile ke liye apni janm tithi batayein. Jaise: 21 March 1990."
                )
                return self._gen(f"got last name {name}, asking DOB for new patient", hint)

            if self._new_patient and self.data.get("dob"):
                # DOB already captured (from VERIFY_PROFILE_DOB mismatch) — go straight to symptom
                self.state = "ASK_SYMPTOM"
                hint = self._t(
                    f"Thank you, {fn} {name}. What symptoms are you experiencing today?",
                    f"Shukriya, {fn} {name} ji. Aaj aapko kya takleef ho rahi hai?"
                )
                return self._gen(f"got last name {name} (DOB already set), asking symptom", hint)

            # Returning patient (verified by DOB earlier or by CSV match)
            self.state = "ASK_SYMPTOM"
            hint = self._t(
                f"Welcome back, {fn} {name}! What symptoms are you experiencing today?",
                f"Dobara milke khushi hui, {fn} {name} ji! Aaj aapko kya takleef ho rahi hai?"
            )
            return self._gen(f"confirmed full name {fn} {name}, asking for symptoms", hint)

        # ── VERIFY_CSV_DOB ─────────────────────────────────────────────────
        # Triggered after a name match in appointments.csv.
        # We ALWAYS ask DOB here to:
        #   (a) confirm identity for a single match, and
        #   (b) disambiguate between two patients with the same name.
        elif self.state == "VERIFY_CSV_DOB":
            from patient_profiles import validate_dob
            dob = validate_dob(user_input)
            fn  = self.data.get("first_name", "")
            ln  = self.data.get("last_name",  "")

            if dob:
                csv_matches = getattr(self, "_csv_matches", [])
                if not csv_matches:
                    # Safety fallback: re-fetch matches
                    csv_matches = self._find_all_in_appointments(fn, ln)

                # Try to find a row whose DOB matches what the patient just said
                matched_row = None
                from patient_profiles import validate_dob as _val_dob
                for row in csv_matches:
                    row_dob = (row.get("DOB", row.get("dob", "")) or "").strip()
                    norm_row_dob = _val_dob(row_dob) if row_dob else None
                    if norm_row_dob and norm_row_dob == dob:
                        matched_row = row
                        break

                if matched_row:
                    # ✅ DOB verified — treat as returning patient
                    self._new_patient = False
                    self.data["dob"]  = dob
                    self._csv_matches = []
                    print(f"  [profile] DOB verified for {fn} {ln} via CSV — returning patient")
                    self.state = "ASK_SYMPTOM"
                    hint = self._t(
                        f"Welcome back, {fn} {ln}! Great to have you with us again. "
                        f"What symptoms are you experiencing today?",
                        f"Dobara milke khushi hui, {fn} {ln} ji! "
                        f"Aaj aapko kya takleef ho rahi hai?"
                    )
                    return self._gen(f"CSV DOB verified for {fn} {ln} — returning patient, asking symptom", hint)

                else:
                    # ❌ DOB does NOT match any record for this name
                    # → New patient; store this DOB and continue booking
                    self._new_patient  = True
                    self.data["dob"]   = dob
                    self._csv_matches  = []
                    print(
                        f"  [profile] DOB mismatch for {fn} {ln} in CSV "
                        f"— treating as new patient (DOB={dob})"
                    )
                    self.state = "ASK_SYMPTOM"
                    hint = self._t(
                        f"I could not match that date of birth with our records for {fn} {ln}. "
                        f"No problem — I will create a new profile for you. "
                        f"What symptoms are you experiencing today?",
                        f"Kshama karein, {fn} {ln} ji ki record se woh janm tithi match nahi hui. "
                        f"Hum aapki nayi profile banate hain. Aaj aapko kya takleef ho rahi hai?"
                    )
                    return self._gen(
                        f"CSV DOB mismatch for {fn} {ln} — new patient (DOB stored), asking symptom",
                        hint
                    )

            # DOB not understood — ask again
            hint = self._t(
                "I am sorry, I could not catch that date. "
                "Please say your date of birth clearly — for example: 21 March 1990.",
                "Kshama karein, woh date samajh nahi aayi. "
                "Kripya apni janm tithi clearly bolein — jaise: 21 March 1990."
            )
            return self._gen("VERIFY_CSV_DOB: DOB not understood, asking again", hint)

        # ── ASK_DOB (new patient only) ────────────────────────────────────
        elif self.state == "ASK_DOB":
            from patient_profiles import validate_dob
            dob = validate_dob(user_input)
            if dob:
                self.data["dob"] = dob
                self._new_patient = True   # still new — profile will be saved on confirm
                self.state = "ASK_SYMPTOM"
                fn = self.data["first_name"]
                hint = self._t(
                    f"Thank you, {fn}. Your date of birth has been noted. "
                    f"Now, what symptoms are you experiencing today?",
                    f"Shukriya, {fn} ji. Janm tithi note ho gayi. "
                    f"Aaj aapko kya takleef ho rahi hai?"
                )
                return self._gen(f"DOB {dob} confirmed, asking symptom", hint)
            hint = self._t(
                "I am sorry, I could not catch that. Please say your date of birth "
                "like this: 21 March 1990. Or say the day, month, and year clearly.",
                "Kshama karein, woh date samajh nahi aayi. Kripya apni janm tithi "
                "aise bolein: 21 March 1990. Din, mahina, aur saal clearly bolein."
            )
            return self._gen("DOB not understood, asking with clear spoken example", hint)

        # ── ASK_SYMPTOM ───────────────────────────────────────────────────
        elif self.state == "ASK_SYMPTOM":
            symptom = self._detect_symptom(text)
            if symptom:
                dept              = SYMPTOM_MAP[symptom]
                self.temp_doctors = DOCTORS[dept]
                d1, d2            = self.temp_doctors[0], self.temp_doctors[1]
                self.state        = "SELECT_DOCTOR"
                hint = self._t(
                    f"I understand. For {symptom}, I recommend {d1} or {d2}. "
                    f"Please say 1 for {d1} or 2 for {d2}.",
                    f"Samajh gaya. {symptom} ke liye {d1} ya {d2} se milna accha rahega. "
                    f"{d1} ke liye 1 kahein ya {d2} ke liye 2."
                )
                return self._gen(f"detected symptom '{symptom}' — offering doctor choice", hint)

            
            _pure_noise = {
                "yes", "no", "okay", "ok", "hello", "hi",
                "haan", "nahi", "na", "yeah", "nope",
                "thanks", "thank you", "sorry", "silence",
            }
            if text.strip().lower() not in _pure_noise:
                self.temp_doctors = DOCTORS["general"]
                d1, d2 = self.temp_doctors[0], self.temp_doctors[1]
                self.state = "SELECT_DOCTOR"
                hint = self._t(
                    f"I understand you are not feeling well. "
                    f"I recommend seeing our General Physician who can help with a wide range of concerns. "
                    f"Please say 1 for {d1} or 2 for {d2}.",
                    f"Samajh gaya, aap theek nahi hain. "
                    f"General Physician aapki madad kar sakenge. "
                    f"{d1} ke liye 1 kahein, ya {d2} ke liye 2."
                )
                return self._gen("unrecognised symptom — routing to general physician", hint)

            # Pure noise / silence → prompt once more
            hint = self._t(
                "Could you please describe your main symptom? "
                "For example: headache, fever, cough, stomach pain, or skin rash.",
                "Kripya apna mukhya lakshan batayein. "
                "Jaise: sar dard, bukhar, khansi, pet dard, ya khujli."
            )
            return self._gen("could not detect symptom, asking again", hint)

        # ── SELECT_DOCTOR ─────────────────────────────────────────────────
        elif self.state == "SELECT_DOCTOR":
            num = parse_number(user_input, self.temp_doctors)
            if not num or num > len(self.temp_doctors):
                d1, d2 = self.temp_doctors[0], self.temp_doctors[1]
                hint = self._t(
                    f"Please choose: say 1 for {d1} or 2 for {d2}.",
                    f"Kripya chunein: {d1} ke liye 1, ya {d2} ke liye 2."
                )
                return self._gen("doctor selection unclear, re-asking", hint)
            self.data["doctor"] = self.temp_doctors[num - 1]
            self.state          = "ASK_DATE"
            hint = self._t(
                f"Which date would you like to visit? Please say a date, for example: 21 March.",
                f"Aap kaunsi tarikh ko aana chahenge? Jaise: 21 March."
            )
            return self._gen(f"patient chose {self.data['doctor']}, asking preferred date", hint)

        # ── ASK_DATE ──────────────────────────────────────────────────────
        elif self.state == "ASK_DATE":
            # Intercept day-of-week: "actually make it Thursday"
            date_fix = self._try_date_correction(user_input)
            if date_fix:
                user_input = date_fix  # let normal ASK_DATE flow handle it
            from datetime import datetime as _dt, timedelta as _td

            
            _raw = user_input.strip()
            _month_words = [
                "january","february","march","april","may","june",
                "july","august","september","october","november","december",
                "jan","feb","mar","apr","jun","jul","aug","sep","oct","nov","dec",
            ]
            _has_month = any(m in _raw.lower() for m in _month_words)
            _digit_only = re.sub(r"[^0-9/\-\s]", "", _raw).strip()
            
            _looks_like_date_pattern = bool(re.match(r"^\d{1,2}[/\-]\d{1,2}([/\-]\d{2,4})?$", _raw.strip()))
            _all_digits_no_sep = bool(re.match(r"^\d+$", _raw.strip()))
            if _all_digits_no_sep and not _has_month:
                hint = self._t(
                    "Please say a date with a month name. For example: 21 March or 5 April.",
                    "Kripya mahine ka naam bhi bolein. Jaise: 21 March ya 5 April."
                )
                return self._gen("date invalid — no month name, asking to repeat", hint)

            formatted = format_date(user_input)
            if not is_valid_date(formatted):
                hint = self._t(
                    "Please say a valid date. For example: 21 March or 5 April.",
                    "Ek sahi date batayein. Jaise: 21 March ya 5 April."
                )
                return self._gen("date invalid, asking to repeat", hint)

            # ── Past-date check ───────────────────────────────────────────
            if is_past_date(formatted):
                try:
                    today_str = _dt.now().strftime("%-d %B %Y")
                except ValueError:
                    today_str = _dt.now().strftime("%d %B %Y").lstrip("0")
                hint = self._t(
                    f"I am sorry, {formatted} has already passed. "
                    f"Today is {today_str}. Please choose a future date.",
                    f"Kshama karein, {formatted} beet chuki hai. "
                    f"Aaj {today_str} hai. Kripya aane wali koi date chunein."
                )
                return self._gen("past date entered, asking for future date", hint)

            self.data["date"] = formatted
            self.state        = "ASK_TIME"

            # Show only slots not yet booked for this doctor on this date
            # (also excludes past time-slots when date == today)
            avail_slots = get_available_slots(self.data.get("doctor", ""), formatted)

            if not avail_slots:
                # No slots on this date — suggest next available day
                parsed_dt = _parse_date_from_text(formatted)
                next_date = (parsed_dt + _td(days=1)) if parsed_dt else None
                next_date_str = next_date.strftime("%d %B %Y") if next_date else None
                next_avail = (
                    get_available_slots(self.data.get("doctor", ""), next_date_str)
                    if next_date_str else []
                )
                self.data["date"] = None
                self.state = "ASK_DATE"
                if next_date_str and next_avail:
                    next_slots = ", ".join(next_avail)
                    hint = self._t(
                        f"I am sorry, no time slots are available for {formatted}. "
                        f"The next available date is {next_date_str} with slots: {next_slots}. "
                        f"Would you like to book for {next_date_str}, or choose a different date?",
                        f"Kshama karein, {formatted} ke liye koi slot nahi hai. "
                        f"Agla upalabdh din {next_date_str} hai, slots: {next_slots}. "
                        f"Kya {next_date_str} ke liye book karein, ya koi aur date chunein?"
                    )
                else:
                    hint = self._t(
                        f"I am sorry, all time slots are fully booked for {formatted}. "
                        f"Please choose a different date.",
                        f"Kshama karein, {formatted} ke saare slots book ho chuke hain. "
                        f"Kripya doosri date chunein."
                    )
                return self._gen("all slots booked for chosen date, asking different date", hint)

            slots = ", ".join(avail_slots)
            hint = self._t(
                f"Please choose a time. Available slots for {formatted} are: {slots}.",
                f"Samay chunein. {formatted} ke liye upalabdh slots hain: {slots}."
            )
            return self._gen(f"date {formatted} confirmed, listing available time slots", hint, max_tokens=25)

        # ── ASK_TIME ──────────────────────────────────────────────────────
        elif self.state == "ASK_TIME":
            avail_slots = get_available_slots(self.data.get("doctor", ""), self.data.get("date", ""))
            # Intercept "make it at 10 am" / "actually 5 pm"
            time_fix = self._try_time_correction(user_input)
            if time_fix:
                user_input = time_fix
            t = normalize_time(user_input)
            if not t:
                if any(w in text for w in ["no", "nahi", "nope", "change",
                                            "badlo", "dobara", "different"]):
                    self.state        = "ASK_DATE"
                    self.data["date"] = None
                    hint = self._t(
                        "No problem. Which date would you prefer?",
                        "Theek hai. Kaunsi date prefer karenge?"
                    )
                    return self._gen("patient wants to change date", hint)
                slots = ", ".join(avail_slots) if avail_slots else "no slots available"
                hint = self._t(
                    f"Please choose from these available times: {slots}. Which time do you prefer?",
                    f"Kripya in upalabdh samay mein se chunein: {slots}. Kaunsa samay chahiye?"
                )
                return self._gen("time not understood, listing available slots again", hint)

            if t not in AVAILABLE_SLOTS:
                slots = ", ".join(avail_slots) if avail_slots else "no slots available"
                hint = self._t(
                    f"I am sorry, {t} is not one of our clinic hours. "
                    f"Please choose from: {slots}.",
                    f"Kshama karein, {t} hamare clinic hours mein nahi hai. "
                    f"Kripya chunein: {slots}."
                )
                return self._gen(f"time {t} not in clinic hours", hint)

            # ── Slot availability check ───────────────────────────────────
            self.data["time"] = t
            if not is_slot_available(self.data):
                self.data["time"] = None
                avail_slots = get_available_slots(self.data.get("doctor", ""), self.data.get("date", ""))
                doctor = self.data.get("doctor", "that doctor")
                date   = self.data.get("date",   "that date")
                if avail_slots:
                    slots = ", ".join(avail_slots)
                    hint = self._t(
                        f"I am sorry, {t} is already booked for {doctor} on {date}. "
                        f"The remaining available times are: {slots}. Which would you prefer?",
                        f"Kshama karein, {t} ka slot {doctor} ke liye {date} ko pehle se book hai. "
                        f"Baaki upalabdh slots hain: {slots}. Kaunsa chahiye?"
                    )
                    return self._gen(f"slot {t} already booked — listing remaining available slots", hint)
                else:
                    hint = self._t(
                        f"I am sorry, all time slots for {doctor} on {date} are now fully booked. "
                        f"Would you like to choose a different date?",
                        f"Kshama karein, {doctor} ke saare slots {date} ko book ho chuke hain. "
                        f"Kya koi doosri date chunenge?"
                    )
                    self.data["date"] = None
                    self.state = "ASK_DATE"
                    return self._gen("all slots fully booked for doctor+date, asking new date", hint)

            # ── Slot is available — ask for confirmation ──────────────────
            self.state = "CONFIRM"
            d = self.data
            hint = self._t(
                f"To confirm: your appointment with {d['doctor']} "
                f"on {d['date']} at {t}. "
                f"Shall I go ahead? Please say yes or no.",
                f"Confirm karte hain: {d['first_name']} ji, aapki appointment "
                f"{d['doctor']} ke saath {d['date']} ko {t} baje. "
                f"Kya main aage badhoon? Haan ya nahi."
            )
            return self._gen(f"all details ready — asking confirmation", hint)

        # ── CONFIRM ───────────────────────────────────────────────────────
        elif self.state == "CONFIRM":
            if self._is_yes(text):
                save_appointment(self.data)
                try:
                    profiles.save_profile(
                        self.data.get("phone", ""),
                        self.data["first_name"],
                        self.data["last_name"],
                        self.data.get("dob", ""),
                    )
                except Exception as e:
                    print(f"  [profile save failed: {e}]")
                try:
                    send_email()
                except Exception as e:
                    print(f"  [email failed: {e}]")
                try:
                    send_sms(self.data.get("phone"), self.data, lang=self.lang)
                except Exception as e:
                    print(f"  [sms failed: {e}]")
                d = self.data
                hint = self._t(
                    f"Your appointment with {d['doctor']} on {d['date']} at {d['time']} "
                    f"is confirmed. We look forward to seeing you, {d['first_name']}. "
                    f"Thank you for calling Anand Hospital.",
                    f"Aapki appointment {d['doctor']} ke saath {d['date']} ko "
                    f"{d['time']} baje confirm ho gayi. "
                    f"Aapka intezaar rahega, {d['first_name']} ji. "
                    f"Anand Hospital mein call karne ka shukriya."
                )
                reply = self._gen(f"appointment confirmed", hint, max_tokens=10)
                self.reset()
                return reply

            if self._is_no(text):
                hint = self._t(
                    "No problem. The booking has been cancelled. "
                    "Is there anything else I can help you with?",
                    "Theek hai. Booking cancel kar di gayi. "
                    "Kya main aur kuch madad kar sakta hoon?"
                )
                reply = self._gen("patient said no at confirmation — cancelling", hint)
                self.reset()
                return reply

            hint = self._t(
                "Please say yes to confirm your appointment or no to cancel.",
                "Haan kahein appointment confirm karne ke liye, ya nahi kahein cancel ke liye."
            )
            return self._gen("unclear response at confirmation, asking yes or no", hint)

        
        elif self.state == "CANCEL_FIRST":
            self.state = "CANCEL_SPELL_FIRST"
            hint = self._t(
                "Thank you. Could you please spell your first name letter by letter?",
                "Shukriya. Kripya apna pehla naam ek ek akshar karke spell karein."
            )
            return self._gen("asking to spell first name for cancel", hint)

        elif self.state == "CANCEL_SPELL_FIRST":
            name = parse_spelled_name(user_input)
            if not name or len(name) < 2:
                hint = self._t(
                    "Please spell your first name letter by letter.",
                    "Apna pehla naam ek ek akshar mein bolein."
                )
                return self._gen("spelling of first name unclear", hint)
            self.data["first_name"] = name
            self.state = "CANCEL_LAST"
            hint = self._t(
                f"Thank you, {name}. May I have your last name please?",
                f"Shukriya, {name}. Apna aakhiri naam batayein."
            )
            return self._gen("asking last name for cancel", hint)

        elif self.state == "CANCEL_LAST":
            self.state = "CANCEL_SPELL_LAST"
            hint = self._t(
                "Thank you. Could you please spell your last name letter by letter?",
                "Shukriya. Kripya apna aakhiri naam ek ek akshar karke spell karein."
            )
            return self._gen("asking to spell last name for cancel", hint)

        elif self.state == "CANCEL_SPELL_LAST":
            if not self.data.get("last_name"):
                self.data["last_name"] = parse_spelled_name(user_input)
            success = cancel_appointment(
                self.data["first_name"], self.data["last_name"])
            try:
                send_email()
            except Exception as e:
                print(f"  [email failed: {e}]")
            name = self.data["first_name"]
            self.reset()
            if success:
                hint = self._t(
                    f"Your appointment has been successfully cancelled, {name}. "
                    f"Thank you for letting us know. Take care.",
                    f"Aapki appointment safaltapoorvak cancel kar di gayi, {name} ji. "
                    f"Shukriya. Apna dhyan rakhein."
                )
                return self._gen(f"appointment for {name} cancelled successfully", hint)
            hint = self._t(
                "I could not find an appointment under that name. "
                "Please check the name and call us again.",
                "Us naam se koi appointment nahi mili. "
                "Naam check karke dobara call karein."
            )
            return self._gen("appointment not found", hint)

        
        elif self.state == "RESCHEDULE_FIRST":
            self.state = "RESCHEDULE_SPELL_FIRST"
            hint = self._t(
                "Thank you. Could you please spell your first name letter by letter?",
                "Shukriya. Kripya apna pehla naam ek ek akshar karke spell karein."
            )
            return self._gen("asking to spell first name for reschedule", hint)

        elif self.state == "RESCHEDULE_SPELL_FIRST":
            name = parse_spelled_name(user_input)
            if not name or len(name) < 2:
                hint = self._t(
                    "Please spell your first name letter by letter.",
                    "Apna pehla naam ek ek akshar mein bolein."
                )
                return self._gen("reschedule: first name spelling not clear", hint)
            self.data["first_name"] = name
            self.state = "RESCHEDULE_LAST"
            hint = self._t(
                f"Thank you, {name}. And your last name please?",
                f"Shukriya, {name}. Apna aakhiri naam batayein."
            )
            return self._gen(f"reschedule: got first name {name}, asking last name", hint)

        elif self.state == "RESCHEDULE_LAST":
            self.state = "RESCHEDULE_SPELL_LAST"
            hint = self._t(
                "Thank you. Could you please spell your last name letter by letter?",
                "Shukriya. Kripya apna aakhiri naam ek ek akshar karke spell karein."
            )
            return self._gen("asking to spell last name for reschedule", hint)

        elif self.state == "RESCHEDULE_SPELL_LAST":
            name = parse_spelled_name(user_input)
            if not name or len(name) < 2:
                hint = self._t(
                    "Please spell your last name letter by letter.",
                    "Apna aakhiri naam ek ek akshar mein bolein."
                )
                return self._gen("reschedule: last name spelling not clear", hint)
            self.data["last_name"] = name
            self.state = "RESCHEDULE_DATE"
            hint = self._t(
                f"Got it, {self.data['first_name']} {name}. What new date would you like?",
                f"Samajh gaya, {self.data['first_name']} {name}. Nayi date kya chahiye?"
            )
            return self._gen(f"reschedule: got full name, asking new date", hint)

        elif self.state == "RESCHEDULE_DATE":
            # ── Reject bare random numbers (same guard as ASK_DATE) ────────────
            _raw_r = user_input.strip()
            _month_words_r = [
                "january","february","march","april","may","june",
                "july","august","september","october","november","december",
                "jan","feb","mar","apr","jun","jul","aug","sep","oct","nov","dec",
            ]
            _has_month_r = any(m in _raw_r.lower() for m in _month_words_r)
            if re.match(r"^\d+$", _raw_r.strip()) and not _has_month_r:
                hint = self._t(
                    "Please say a date with a month name. For example: 10 May or 21 March.",
                    "Kripya mahine ka naam bhi bolein. Jaise: 10 May ya 21 March."
                )
                return self._gen("reschedule: date invalid — no month name", hint)
            formatted = format_date(user_input)
            if not is_valid_date(formatted):
                hint = self._t(
                    "Please say a valid date. For example: 10 May or 21 March.",
                    "Sahi date batayein. Jaise: 10 May ya 21 March."
                )
                return self._gen("reschedule: invalid date", hint)
            
            if is_past_date(formatted):
                from datetime import datetime as _dt
                try:
                    today_str = _dt.now().strftime("%-d %B %Y")
                except ValueError:
                    today_str = _dt.now().strftime("%d %B %Y").lstrip("0")
                hint = self._t(
                    f"I am sorry, {formatted} has already passed. Today is {today_str}. Please choose a future date.",
                    f"Kshama karein, {formatted} beet chuki hai. Aaj {today_str} hai. Kripya aane wali koi date chunein."
                )
                return self._gen("reschedule: past date entered", hint)

            self._reschedule_data["new_date"] = formatted
            self.state = "RESCHEDULE_TIME"

            fn = self.data.get("first_name", "")
            ln = self.data.get("last_name", "")
            doctor = None
            for row in _read_appointments():
                row_fn = row.get("First Name", row.get("first_name", ""))
                row_ln = row.get("Last Name", row.get("last_name", ""))
                row_status = row.get("Status", "active").strip().lower()
                if row_status == "cancelled": continue
                if row_fn.lower() == fn.lower() and row_ln.lower() == ln.lower():
                    doctor = row.get("Doctor", row.get("doctor", ""))
                    break
            
            self._reschedule_data["doctor"] = doctor
            
            avail_slots = get_available_slots(doctor, formatted) if doctor else AVAILABLE_SLOTS

            if not avail_slots:
                hint = self._t(
                    f"I am sorry, all time slots are fully booked for {formatted}. Please choose a different date.",
                    f"Kshama karein, {formatted} ke saare slots book ho chuke hain. Kripya doosri date chunein."
                )
                self._reschedule_data["new_date"] = None
                self.state = "RESCHEDULE_DATE"
                return self._gen("reschedule: all slots booked", hint)

            slots = ", ".join(avail_slots)
            hint = self._t(
                f"And what time on {formatted}? Available: {slots}.",
                f"{formatted} ko kaunsa samay chahiye? Slots: {slots}."
            )
            return self._gen(f"reschedule: new date {formatted}, asking time", hint)

        elif self.state == "RESCHEDULE_TIME":
            t = normalize_time(user_input)
            doctor = self._reschedule_data.get("doctor", "")
            new_date = self._reschedule_data.get("new_date", "")
            avail_slots = get_available_slots(doctor, new_date) if doctor else AVAILABLE_SLOTS

            if not t or t not in AVAILABLE_SLOTS:
                slots = ", ".join(avail_slots) if avail_slots else "no slots available"
                hint = self._t(
                    f"Please choose from: {slots}.",
                    f"Kripya in slots mein se chunein: {slots}."
                )
                return self._gen("reschedule: time not valid", hint)
            
            if t not in avail_slots:
                slots = ", ".join(avail_slots) if avail_slots else "no slots available"
                hint = self._t(
                    f"I am sorry, {t} is already booked. Available times are: {slots}. Which would you prefer?",
                    f"Kshama karein, {t} ka slot pehle se book hai. Upalabdh slots hain: {slots}. Kaunsa chahiye?"
                )
                return self._gen(f"reschedule: slot {t} already booked", hint)
            self._reschedule_data["new_time"] = t
            new_date = self._reschedule_data["new_date"]
            fn       = self.data.get("first_name", "")
            self.state = "RESCHEDULE_CONFIRM"
            hint = self._t(
                f"To confirm, {fn}: I will reschedule your appointment to {new_date} at {t}. "
                f"Shall I go ahead? Please say yes or no.",
                f"Confirm karte hain, {fn} ji: appointment {new_date} ko {t} baje reschedule hogi. "
                f"Kya aage badhoon? Haan ya nahi."
            )
            return self._gen(f"reschedule confirmation: {new_date} at {t}", hint)

        elif self.state == "RESCHEDULE_CONFIRM":
            if self._is_yes(text):
                new_date   = self._reschedule_data.get("new_date", "")
                new_time   = self._reschedule_data.get("new_time", "")
                fn         = self.data.get("first_name", "")
                ln         = self.data.get("last_name",  "")
                success    = reschedule_appointment(fn, ln, new_date, new_time)
                self.data["date"] = new_date
                self.data["time"] = new_time
                try:
                    send_email("Appointment Rescheduled",
                               f"{fn} {ln} rescheduled to {new_date} at {new_time}.")
                except Exception as e:
                    print(f"  [email failed: {e}]")
                try:
                    send_sms_reschedule(self.data.get("phone"), self.data, lang=self.lang)
                except Exception as e:
                    print(f"  [sms-reschedule failed: {e}]")
                reply_hint = self._t(
                    f"Your appointment has been rescheduled to {new_date} at {new_time}. "
                    f"Thank you, {fn}. We look forward to seeing you then.",
                    f"Aapki appointment {new_date} ko {new_time} baje reschedule ho gayi. "
                    f"Shukriya, {fn} ji. Aapka intezaar rahega."
                ) if success else self._t(
                    "I could not find your appointment. Please check your name and call again.",
                    "Appointment nahi mili. Naam check karke dobara call karein."
                )
                reply = self._gen("reschedule complete", reply_hint, max_tokens=10)
                self.reset()
                return reply

            if self._is_no(text):
                self.state            = "RESCHEDULE_DATE"
                self._reschedule_data = {}
                hint = self._t(
                    "No problem. What new date would you prefer?",
                    "Theek hai. Kaunsi nayi date chahiye?"
                )
                return self._gen("reschedule: patient said no — asking date again", hint)

            hint = self._t(
                "Please say yes to confirm the reschedule or no to change.",
                "Haan kahein confirm ke liye, ya nahi kahein date/time badalne ke liye."
            )
            return self._gen("reschedule confirm: unclear yes/no", hint)

        
        hint = self._t(
            "How may I help you today? I can book, reschedule, or cancel an appointment.",
            "Main aapki kaise madad kar sakta hoon? Appointment book, reschedule ya cancel kar sakta hoon."
        )
