import json
import os
import re
from datetime import datetime

_PROFILES_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "profiles.json"
)

# ── Months for DOB parsing ──────────────────────────────────────────────────
_MONTH_NAMES = {
    "january": 1,  "jan": 1,
    "february": 2, "feb": 2,
    "march": 3,    "mar": 3,
    "april": 4,    "apr": 4,
    "may": 5,
    "june": 6,     "jun": 6,
    "july": 7,     "jul": 7,
    "august": 8,   "aug": 8,
    "september": 9,"sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11,"nov": 11,
    "december": 12,"dec": 12,
    # Hindi month names (romanised)
    "januari": 1,  "janvari": 1,
    "farvari": 2,  "february": 2,
    "march": 3,    "maarsh": 3,
    "april": 4,    "mei": 5,
    "june": 6,     "july": 7,
    "august": 8,   "sitambar": 9, "october": 10,
    "navambar": 11,"disambar": 12,
}


# ── Internal I/O ────────────────────────────────────────────────────────────

def _load() -> dict:
    if not os.path.exists(_PROFILES_FILE):
        return {}
    try:
        with open(_PROFILES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict):
    with open(_PROFILES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Public API ──────────────────────────────────────────────────────────────

def get_profile(phone: str) -> dict | None:
    """
    Return stored profile dict for this phone number, or None if not found.
    phone must be a non-empty E.164 string (e.g. '+918140999769').
    """
    phone = (phone or "").strip()
    if not phone:
        return None
    data = _load()
    return data.get(phone)


def save_profile(phone: str, first_name: str, last_name: str, dob: str = ""):
    """
    Upsert a profile.  Increments booking count and stamps last_call.
    """
    phone = (phone or "").strip()
    if not phone:
        return
    data = _load()
    existing = data.get(phone, {})
    data[phone] = {
        "first_name": first_name.strip().title(),
        "last_name":  last_name.strip().title(),
        "dob":        dob.strip() if dob else existing.get("dob", ""),
        "bookings":   existing.get("bookings", 0) + 1,
        "last_call":  datetime.now().isoformat(timespec="seconds"),
    }
    _save(data)
    print(f"  [profile] Saved profile for {phone!r}: "
          f"{data[phone]['first_name']} {data[phone]['last_name']}, "
          f"DOB={data[phone]['dob']}, bookings={data[phone]['bookings']}")


def has_profile(phone: str) -> bool:
    """Return True if a profile exists for this phone."""
    return get_profile(phone) is not None


def increment_bookings(phone: str):
    """Just bump the booking counter without changing other fields."""
    phone = (phone or "").strip()
    if not phone:
        return
    data = _load()
    if phone in data:
        data[phone]["bookings"] = data[phone].get("bookings", 0) + 1
        data[phone]["last_call"] = datetime.now().isoformat(timespec="seconds")
        _save(data)


def find_profile_by_firstname(first_name: str) -> dict | None:
    """
    Look up a profile by first name alone (case-insensitive).
    Used for quick recognition when a returning patient says their name.
    If multiple profiles share the same first name, returns None (ambiguous).
    Returns the profile dict (including the _phone key) or None.
    """
    first_name = (first_name or "").strip().lower()
    if not first_name:
        return None
    data    = _load()
    matches = []
    for phone, prof in data.items():
        stored_fn = (prof.get("first_name", "") or "").strip().lower()
        if stored_fn == first_name:
            matches.append({**prof, "_phone": phone})
    if len(matches) == 1:
        return matches[0]
    return None  # 0 = unknown, 2+ = ambiguous


def find_profile_by_name_dob(first_name: str, dob: str) -> dict | None:
    """
    Look up a profile by first name + date of birth.
    Both must match (case-insensitive first name, exact DOB string).
    Returns the profile dict (including the _phone key) or None.
    This is the primary verification mechanism — does NOT rely on phone number.
    """
    first_name = (first_name or "").strip().lower()
    dob        = (dob or "").strip()
    if not first_name or not dob:
        return None
    data = _load()
    for phone, prof in data.items():
        stored_fn  = (prof.get("first_name", "") or "").strip().lower()
        stored_dob = (prof.get("dob", "") or "").strip()
        if stored_fn == first_name and stored_dob == dob:
            return {**prof, "_phone": phone}
    return None


# ── DOB Parsing & Validation ────────────────────────────────────────────────

def validate_dob(text: str) -> str | None:
    """
    Parse a spoken/typed date of birth from text.
    Handles all real-world STT variations:
      - "21/03/1990" or "21-03-1990"
      - "21 March 1990" or "21st March 1990"
      - "21st, March 1990"  (comma after ordinal — very common STT output)
      - "8, March 2006"     (comma after bare number)
      - "March 21 1990" or "March 21, 1990"
      - Pure digits "21031990" (DDMMYYYY, 8 digits)
      - 7-digit "0803206" → treated as DDMMYYY if year < 100, else DMMYYYY

    Returns "DD/MM/YYYY" string on success, or None if parsing fails.
    Returns None also if DOB implies age < 0 or > 120 years.
    """
    # ── Pre-process ────────────────────────────────────────────────────────
    text = text.strip().lower()
    # Strip trailing punctuation but NOT internal commas (they matter for parsing)
    text = text.rstrip(".,!? ")
    # Normalise ordinal suffixes: "21st" → "21", "8th" → "8"
    text_norm = re.sub(r'(\d+)(?:st|nd|rd|th)\b', r'\1', text)

    # ── Pattern 1: numeric separators DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY ──
    m = re.search(r'\b(\d{1,2})[/\-._ ](\d{1,2})[/\-._ ](\d{4})\b', text_norm)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return _make_dob(d, mo, y)

    # ── Pattern 2: "21 March 1990" or "21, March 1990" (comma allowed) ────
    # Handles: "21st March 1990", "21st, March 1990", "8, March 2006"
    m = re.search(
        r'\b(\d{1,2})\s*,?\s*([a-z]+)\s*,?\s*(\d{4})\b', text_norm
    )
    if m:
        d, mon_str, y = int(m.group(1)), m.group(2), int(m.group(3))
        mo = _MONTH_NAMES.get(mon_str)
        if mo:
            return _make_dob(d, mo, y)

    # ── Pattern 3: "March 21, 1990" or "March 21 1990" ────────────────────
    m = re.search(
        r'\b([a-z]+)\s+(\d{1,2})\s*,?\s*(\d{4})\b', text_norm
    )
    if m:
        mon_str, d, y = m.group(1), int(m.group(2)), int(m.group(3))
        mo = _MONTH_NAMES.get(mon_str)
        if mo:
            return _make_dob(d, mo, y)

    # ── Pattern 4: pure digits ─────────────────────────────────────────────
    # Extract all digit runs and try to form a date
    digits = re.sub(r'\D', '', text_norm)

    if len(digits) == 8:
        # DDMMYYYY
        d, mo, y = int(digits[:2]), int(digits[2:4]), int(digits[4:])
        result = _make_dob(d, mo, y)
        if result:
            return result

    if len(digits) == 7:
        # STT often drops a leading zero: "08031990" heard as "0803190" (7 digits)
        # Try padding: 0DDMMYYYY → DD = 0X, or DMMYYYY → day=D, month=MM, year=YYYY
        # Strategy: try DD=first2, MM=next2, YYYY=last4 after zero-padding
        padded = '0' + digits  # make it 8 digits
        d, mo, y = int(padded[:2]), int(padded[2:4]), int(padded[4:])
        result = _make_dob(d, mo, y)
        if result:
            return result
        # Also try as DMMYYYY (day=1 digit, month=2 digits, year=4 digits)
        d2, mo2, y2 = int(digits[0]), int(digits[1:3]), int(digits[3:])
        result = _make_dob(d2, mo2, y2)
        if result:
            return result

    if len(digits) == 6:
        # DDMMYY — try expanding year: 90→1990, 06→2006
        d, mo, yy = int(digits[:2]), int(digits[2:4]), int(digits[4:])
        y = 1900 + yy if yy >= 25 else 2000 + yy
        result = _make_dob(d, mo, y)
        if result:
            return result

    return None



def _make_dob(day: int, month: int, year: int) -> str | None:
    """Validate ranges and return 'DD/MM/YYYY' or None."""
    try:
        dt = datetime(year, month, day)
    except ValueError:
        return None
    # Sanity: age between 0 and 120
    age = (datetime.now() - dt).days / 365.25
    if age < 0 or age > 120:
        return None
    return f"{day:02d}/{month:02d}/{year:04d}"


# ── Quick test (run directly) ───────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        "21/03/1990", "21 March 1990", "March 21, 1990",
        "21st march 1990", "21031990", "born on 5 July 1985",
        "invalid text", "99/99/9999",
    ]
    print("DOB validation tests:")
    for t in tests:
        print(f"  {t!r:35s} -> {validate_dob(t)}")
