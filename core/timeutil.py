import re
from datetime import date, datetime, time, timedelta

def now():
    """Current time as an aware datetime in the laptop's timezone."""
    return datetime.now().astimezone()


def today():
    return now().date()


def to_local(dt):
    """Any datetime -> the laptop's timezone. A naive datetime is taken to already be local time."""
    return dt.astimezone()


def parse_iso_local(value):
    """ISO 8601 text (with or without an offset, 'Z' allowed) -> aware datetime in the laptop's timezone."""
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
    """A date plus a clock time -> aware datetime in the laptop's timezone."""
    return to_local(datetime.combine(day, clock))


def day_bounds(day):
    """(start, end) of a local day as ISO strings with the offset, for Google Calendar's timeMin/timeMax."""
    start = to_local(datetime.combine(day, time(0, 0, 0)))
    end = to_local(datetime.combine(day, time(23, 59, 59)))
    return start.isoformat(), end.isoformat()


def utc_label(dt=None):
    """'UTC+7', 'UTC+8', 'UTC+5:30' ... for the current local offset."""
    minutes = int((dt or now()).utcoffset().total_seconds() // 60)
    sign = "+" if minutes >= 0 else "-"
    h, m = divmod(abs(minutes), 60)
    return f"UTC{sign}{h}" + (f":{m:02d}" if m else "")


# ---------------------------------------------------------------- turning words into a date
_WEEKDAYS = {"monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1, "wednesday": 2, "wed": 2,
             "thursday": 3, "thu": 3, "thur": 3, "thurs": 3, "friday": 4, "fri": 4,
             "saturday": 5, "sat": 5, "sunday": 6, "sun": 6}


def _weekday_date(target, modifier, base):
    """'tuesday'/'this tuesday' = the next one counting today. 'next tuesday' = the one in NEXT week
    (weeks run Monday to Sunday). 'last tuesday' = the most recent one before today."""
    if modifier == "last":
        back = (base.weekday() - target) % 7 or 7
        return base - timedelta(days=back)
    d = base + timedelta(days=(target - base.weekday()) % 7)
    if modifier == "next":
        next_monday = base + timedelta(days=7 - base.weekday())
        if d < next_monday:                      # that Tuesday is still in the current week, so jump a week
            d += timedelta(days=7)
    return d


def resolve_date_string(date_input=None, base=None):
    """Words or an ISO date -> a date. Returns None if it can't be understood (never silently 'today')."""
    base = base or today()
    if isinstance(date_input, datetime):
        return date_input.date()
    if isinstance(date_input, date):
        return date_input

    s = str(date_input or "").strip().lower()
    if not s or s in ("today", "now", "tonight"):
        return base
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):                       # fast path: already an ISO date
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

    try:                                                              # anything else: "20 nov", "in 3 days", "13/11"
        import dateparser
        parsed = dateparser.parse(s, settings={
            "PREFER_DATES_FROM": "future",
            "RELATIVE_BASE": datetime.combine(base, now().time()),   # naive, local
            "DATE_ORDER": "DMY",                                      # Singapore and Indonesia write day first
        })
        return parsed.date() if parsed else None
    except ImportError:
        return None


# ---------------------------------------------------------------- one cheap line of context for the prompt
def daypart(hour):
    if hour < 5:
        return "late night"
    if hour < 9:
        return "early morning"
    if hour < 12:
        return "morning"
    if hour < 17:
        return "afternoon"
    if hour < 21:
        return "evening"
    return "night"


_DATE_WORDS = re.compile(
    r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|tues?|thu(rs?)?|fri)\b|"
    r"today|tonight|tomorrow|tmr|week|month|free|busy|available|schedule|calendar|meeting|deadline|due|"
    r"january|february|march|april|may|june|july|august|september|october|november|december|"
    r"\d{1,2}\s*(st|nd|rd|th)?\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)|"
    r"\d{1,2}[/-]\d{1,2}|\bin \d+ (day|week)", re.I)


def needs_dates(text):
    """Cheap check: does this message talk about dates at all?"""
    return bool(_DATE_WORDS.search(text or ""))


def time_context(user_text=""):
    """About 25 tokens normally. Only when the message mentions dates does it add the next 14 days,
    so the model can read a weekday off a list instead of calculating it."""
    n = now()
    line = f"Now: {n:%A} {n.day} {n:%B %Y}, {n:%H:%M} ({daypart(n.hour)}), local time ({utc_label(n)})."
    if needs_dates(user_text):
        days = [n.date() + timedelta(days=i) for i in range(1, 15)]
        line += " Coming days: " + ", ".join(f"{d:%a} {d.day} {d:%b}" for d in days) + "."
    return line


# ---------------------------------------------------------------- free time from calendar events
def day_summary(events, day, start="08:00", end="22:00", min_minutes=30):
    """Google Calendar events for one day -> answer-ready data: timed events, all-day events and FREE windows
    (gaps of at least min_minutes between `start` and `end`). The model reads the result; it never does the maths."""
    day_start = to_local(datetime.combine(day, time.fromisoformat(start)))
    day_end = to_local(datetime.combine(day, time.fromisoformat(end)))

    timed, all_day = [], []
    for ev in events:
        name = ev.get("summary", "Untitled")
        s, e = ev.get("start", {}), ev.get("end", {})
        if "dateTime" in s:
            a = parse_iso_local(s["dateTime"])
            b = parse_iso_local(e.get("dateTime", s["dateTime"]))
            timed.append((a, max(a, b), name, ev.get("transparency") != "transparent"))
        else:
            all_day.append(name)
    timed.sort()

    busy = []                                                        # merge overlapping events, clip to the window
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
            free.append((cursor, a))
        cursor = max(cursor, b)
    if day_end - cursor >= timedelta(minutes=min_minutes):
        free.append((cursor, day_end))

    hm = lambda d: d.strftime("%H:%M")
    return {
        "events": [{"start": hm(a), "end": hm(b), "summary": n, **({} if blocks else {"counts_as_busy": False})}
                   for a, b, n, blocks in timed],
        "all_day": all_day,
        "free": [f"{hm(a)}-{hm(b)}" for a, b in free],
        "free_window": f"{start}-{end}",
    }