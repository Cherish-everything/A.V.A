import re
from zoneinfo import ZoneInfo
from datetime import date, datetime, time, timedelta, timezone

def now():
    """Gets current time based on laptop timezone"""
    return datetime.now().astimezone()

def today():
    return now().date()

def to_local(dt):
    """Any date time turns to local timezone"""
    return dt.astimezone()

def parse_iso_local(value):
    """ISO 8601 text -> timezone aware"""
    return to_local(datetime.fromisoformat(str(value).strip().replace("Z", "+00:00")))

def parse_clock(text):
    """'15:00', '3pm', '3:30 pm', '0930' -> datetime.time, or None if it isn't a clock time."""
    m = re.fullmatch(r"\s*(\d{1,2})(?::?(\d{2}))?\s*(am|pm)?\s*", str(text or "").lower())
    if not m:
        return None
    hour, minute, ampm = int(m.group(1)), int(m.group(2) or 0), m.group(3)

    if ampm == "pm" and hour < 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0

    return time(hour, minute) if 0 <= hour < 24 and 0 <= minute < 60 else None

def combine_local(day, clock):
    return to_local(datetime.combine(day,clock))

_ZONES = {
    "new york": "America/New_York", "nyc": "America/New_York", "ny": "America/New_York", "eastern": "America/New_York",
    "est": "America/New_York", "edt": "America/New_York", "et": "America/New_York", "boston": "America/New_York",
    "miami": "America/New_York", "toronto": "America/Toronto", "chicago": "America/Chicago",
    "central": "America/Chicago", "denver": "America/Denver", "mountain": "America/Denver",
    "mst": "America/Denver", "mdt": "America/Denver", "los angeles": "America/Los_Angeles",
    "la": "America/Los_Angeles", "san francisco": "America/Los_Angeles", "sf": "America/Los_Angeles",
    "california": "America/Los_Angeles", "seattle": "America/Los_Angeles", "pacific": "America/Los_Angeles",
    "pst": "America/Los_Angeles", "pdt": "America/Los_Angeles", "pt": "America/Los_Angeles",
    "mexico city": "America/Mexico_City", "sao paulo": "America/Sao_Paulo", "brazil": "America/Sao_Paulo",
    "london": "Europe/London", "uk": "Europe/London", "paris": "Europe/Paris", "berlin": "Europe/Berlin",
    "madrid": "Europe/Madrid", "rome": "Europe/Rome", "amsterdam": "Europe/Amsterdam",
    "cet": "Europe/Paris", "cest": "Europe/Paris", "utc": "UTC", "gmt": "UTC", "z": "UTC",
    "dubai": "Asia/Dubai", "india": "Asia/Kolkata", "delhi": "Asia/Kolkata", "mumbai": "Asia/Kolkata",
    "bangkok": "Asia/Bangkok", "singapore": "Asia/Singapore", "sg": "Asia/Singapore", "sgt": "Asia/Singapore",
    "kuala lumpur": "Asia/Kuala_Lumpur", "hong kong": "Asia/Hong_Kong", "hkt": "Asia/Hong_Kong",
    "manila": "Asia/Manila", "jakarta": "Asia/Jakarta", "wib": "Asia/Jakarta", "bali": "Asia/Makassar",
    "makassar": "Asia/Makassar", "wita": "Asia/Makassar", "jayapura": "Asia/Jayapura", "wit": "Asia/Jayapura",
    "tokyo": "Asia/Tokyo", "japan": "Asia/Tokyo", "jst": "Asia/Tokyo", "seoul": "Asia/Seoul",
    "korea": "Asia/Seoul", "kst": "Asia/Seoul", "beijing": "Asia/Shanghai", "shanghai": "Asia/Shanghai",
    "china": "Asia/Shanghai", "taipei": "Asia/Taipei", "sydney": "Australia/Sydney",
    "melbourne": "Australia/Sydney", "aest": "Australia/Sydney", "aedt": "Australia/Sydney",
    "brisbane": "Australia/Brisbane", "perth": "Australia/Perth", "auckland": "Pacific/Auckland",
    "nz": "Pacific/Auckland", "johannesburg": "Africa/Johannesburg", "south africa": "Africa/Johannesburg",
    "cairo": "Africa/Cairo", "nairobi": "Africa/Nairobi", "lagos": "Africa/Lagos",
}
_OFFSET = re.compile(r"^(?:utc|gmt)\s*([+-])\s*(\d{1,2})(?::?(\d{2}))?$")

def _load_zone(iana):
    try:
        return ZoneInfo(iana)
    except Exception:
        try:
            ZoneInfo("Asia/Singapore")
        except Exception:
            raise ValueError("The timezone database isn't installed. Run: pip install tzdata")
        return None

def resolve_zone(name):
    s = re.sub(r"\b(time ?zone|time|zone|the|in|at)\b", " ", str(name or "").lower())
    s = " ".join(s.split())

    if not s:
        return None

    m = _OFFSET.match(s)

    if m:
        sign = 1 if m.group(1) == "+" else -1
        return timezone(sign * timedelta(hours=int(m.group(2)), minutes=int(m.group(3) or 0)))

    iana = _ZONES.get(s)
    if iana is None and "/" in s:
        iana = "/".join("_".join(w.capitalize() for w in part.split("_")) for part in s.split("/"))

    return _load_zone(iana) if iana else None

def combine(zone, day, clock):
    if zone is None:
        return combine_local(day, clock)
    return datetime.combine(day, clock, tzinfo=zone).astimezone()

def day_bounds(day):
    """start and end of day"""
    start = to_local(datetime.combine(day, time(0,0,0)))
    end = to_local(datetime.combine(day, time(23, 59, 59)))
    return start.isoformat(), end.isoformat()

def utc_label(dt=None):
    """'UTC+7', 'UTC+8', 'UTC+5:30' ... for the current local offset."""
    minutes =int((dt or now()).utcoffset().total_seconds() // 60)
    sign = "+" if minutes >= 0 else "-"
    h, m = divmod(abs(minutes), 60)
    return f"UTC{sign}{h}" + (f":{m:02d}" if m else "")

_WEEKDAYS = {"monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1, "wednesday": 2, "wed": 2,
             "thursday": 3, "thu": 3, "thur": 3, "thurs": 3, "friday": 4, "fri": 4,
             "saturday": 5, "sat": 5, "sunday": 6, "sun": 6}

def _weekday_date(target, modifier, base):
    if modifier == "last":
        back = (base.weekday() - target) % 7 or 7
        return base - timedelta(days=back)
    d = base + timedelta(days=(target - base.weekday()) % 7)
    if modifier == "next":
        next_monday = base + timedelta(days=7 - base.weekday())
        if d < next_monday: # still in current week
            d += timedelta(days=7)

    return d


def resolve_date_string(date_input=None, base=None):
    """Words or an ISO date -> a date. Returns None if it can't be understood."""
    base = base or today()
    if isinstance(date_input, datetime):
        return date_input.date()
    if isinstance(date_input, date):
        return date_input

    s = str(date_input or "").strip().lower()
    if not s in ("today", "now", "tonight", "this afternoon", "this evening"):
        return base
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        try:
            return date.fromisoformat(s)
        except ValueError:
            return None

    words = re.findall(r"[a-z]+", s)
    if "day after tomorrow" in s:
        return base + timedelta(days=2)
    if "tomorrow" in words or "tmr" in words or "tmrw" in words:
        return base + timedelta(days=1)
    if "yesterday" in words:
        return base - timedelta(days=1)

    for w in words:
        if w in _WEEKDAYS:
            modifier = "next" if "next" in words else "last" if ("last" in words or "previous" in words) else None
            return _weekday_date(_WEEKDAYS[w], modifier, base)
    try:
        import dateparser
        parsed = dateparser.parse(s, settings={
            "PREFER_DATES_FROM": "future",
            "RELATIVE_BASE": datetime.combine(base, now().time()),   # naive, local
            "DATE_ORDER": "DMY"})

        return parsed.date() if parsed else None
    except ImportError:
        return None



# CONTEXT ==============================================================================

def daypart(hour):
    if hour<5:
        return "dawn"
    if hour<9:
        return "early morning"
    if hour<12:
        return "morning"
    if hour<17:
        return "afternoon"
    if hour<21:
        return "evening"
    if hour<24:
        return "late night"

    return "night"

_DATE_WORDS = re.compile(r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|tues?|thu(rs?)?|fri)\b|"
    r"today|tonight|tomorrow|tmr|week|month|free|busy|available|schedule|calendar|meeting|deadline|due|"
    r"january|february|march|april|may|june|july|august|september|october|november|december|"
    r"\d{1,2}\s*(st|nd|rd|th)?\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)|"
    r"\d{1,2}[/-]\d{1,2}|\bin \d+ (day|week)", re.I)

def needs_dates(text):
    return bool(_DATE_WORDS.search(text or ""))

def time_context(user_text=""):
    n = now()
    line = f"Now: {n:%A} {n.day} {n:%B %Y}, {n:%H:%M} ({daypart(n.hour)}), local time ({utc_label(n)})."
    if needs_dates(user_text):
        days = [n.date() + timedelta(days=i) for i in range(1, 15)]
        line += " Coming days: " + ", ".join(f"{d:%a} {d.day} {d:%b}" for d in days) + "."
    return line

# free timee
def day_summary(events, day, start="08:00", end="22:00", min_minutes=30):
    day_start = to_local(datetime.combine(day,time.fromisoformat(start)))
    day_end = to_local(datetime.combine(day,time.fromisoformat(end)))

    timed, all_day = [], []
    for ev in events:
        name = ev.get("summary", "Untitled")
        s, e = ev.get("start", {}), ev.get("end", {})
        if "dateTime" in s:
            a = parse_iso_local(s["dateTime"])
            b = parse_iso_local(e.get("dateTime", s["dateTime"]))
            timed.append((a, max(a, b), name, ev.get("transparency") != "transparent"))
        else:
            all_day.append[name]
    timed.sort()

    busy = []
    for a, b, _, blocks in timed:
        if not blocks:                                               # marked "free" in Google Calendar
            continue
        a, b = max(a, day_start), min(b, day_end)
        if a >= b:
            continue
        if busy and a <= busy[-1][1]:
            busy[-1][1] = max(busy[-1][1], b)
        else:
            busy.append([a, b])

    free, cursor = [], day_start
    for a, b in busy:
        if a - cursor >= timedelta(minutes=min_minutes):
            free.append((cursor,a))
        cursor = max(cursor, b)
    if day_end -  cursor >= timedelta(minutes=min_minutes):
        free.append((cursor, day_end))

    hm = lambda d: d.strftime("%H:%M")
    return {
        "events": [{"start": hm(a), "end": hm(b), "summary": n, **({} if blocks else {"counts_as_busy": False})}
                   for a, b, n, blocks in timed],
        "all_day": all_day,
        "free": [f"{hm(a)}-{hm(b)}" for a, b in free],
        "free_window": f"{start}-{end}",
    }

