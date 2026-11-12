import re
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from googleapiclient.discovery import build

from core.timeutil import (combine_local, day_bounds, day_summary, parse_clock, parse_iso_local,
                           resolve_date_string)
from registry.permission import get_google_services      # (kept as in your project)
from registry.registry import tool

ACCOUNTS = ("personal", "business")
DAY_START, DAY_END = "08:00", "22:00"


def _tool(scope, risk, triggers=()):
    """@tool, tolerant of a registry that doesn't know `triggers` yet."""
    try:
        return tool(scope=scope, risk=risk, triggers=triggers)
    except TypeError:
        return tool(scope=scope, risk=risk)


# =====================================================================
# Helpers
# =====================================================================
def _service(api, version, account_type):
    return build(api, version, credentials=get_google_services(account_type=account_type), cache_discovery=False)


def _accounts(account_type):
    """'any' / 'all' / '' -> both accounts, otherwise just the one named."""
    name = (account_type or "any").strip().lower()
    return ACCOUNTS if name in ("any", "all", "both") else (name,)


def _usable(event):
    """Cancelled events and ones the user declined don't make them busy."""
    if event.get("status") == "cancelled":
        return False
    return not any(a.get("self") and a.get("responseStatus") == "declined" for a in event.get("attendees", []))


def _clock_or_default(text, default):
    clock = parse_clock(text)
    return clock.strftime("%H:%M") if clock else default


# =====================================================================
# Reading the calendar and tasks
# =====================================================================
def get_calendar_events_for_date(target_date, account_type="personal") -> list:
    """Events for one local day (target_date may be a date, an ISO string or words like 'next tuesday').
    Raises if Google can't be reached: returning [] instead would make a failed lookup look like a free day."""
    day = resolve_date_string(target_date)
    if day is None:
        raise ValueError(f"unreadable date: {target_date!r}")
    start, end = day_bounds(day)
    result = _service("calendar", "v3", account_type).events().list(
        calendarId="primary", timeMin=start, timeMax=end,
        singleEvents=True, orderBy="startTime", maxResults=50,
    ).execute()
    return [e for e in result.get("items", []) if _usable(e)]


def get_active_tasks(target_date=None, account_type="personal") -> list:
    """Open tasks. With a date, only the ones due that day; with None, all of them.
    Google stores a due date as a plain date at midnight UTC, so the date part is compared directly:
    converting it between timezones could shift it to the wrong day."""
    day = resolve_date_string(target_date) if target_date else None
    items = _service("tasks", "v1", account_type).tasks().list(
        tasklist="@default", maxResults=100, showCompleted=False).execute().get("items", [])
    if day is None:
        return items
    return [t for t in items if (t.get("due") or "")[:10] == day.isoformat()]


@_tool(scope="calendar.read", risk="read")
def get_agenda_for_date(date_query: str = "today", from_time: str = DAY_START, to_time: str = DAY_END) -> dict:
    """What's on and when the user is FREE on one day, across both their calendars, plus tasks due that day.
    date_query is the user's own words ("tomorrow", "next tuesday", "20 nov") or an ISO date: the code works
    out the date, so never calculate it yourself. Use for "am I free...", "what's on...", "what's my day like".
    Free windows are looked for between from_time and to_time (default 08:00 to 22:00); narrow them for
    questions like "am I free tuesday afternoon" (from_time="12:00", to_time="18:00")."""
    day = resolve_date_string(date_query)
    if day is None:
        return {"error": f"I couldn't understand the date '{date_query}'. Ask the user which day they mean."}

    start = _clock_or_default(from_time, DAY_START)
    end = _clock_or_default(to_time, DAY_END)
    if end <= start:
        start, end = DAY_START, DAY_END

    def fetch(account):
        try:
            return account, get_calendar_events_for_date(day, account), get_active_tasks(day, account), None
        except Exception as e:
            return account, [], [], f"{account}: {e}"

    with ThreadPoolExecutor(max_workers=len(ACCOUNTS)) as pool:          # both accounts at the same time
        results = list(pool.map(fetch, ACCOUNTS))

    errors = [r[3] for r in results if r[3]]
    if len(errors) == len(ACCOUNTS):
        return {"error": "Couldn't reach Google Calendar. " + "; ".join(errors)}

    events, seen = [], set()
    for _, account_events, _, _ in results:
        for e in account_events:                                         # an event on both calendars counts once
            key = (e.get("summary"), (e.get("start") or {}).get("dateTime") or (e.get("start") or {}).get("date"))
            if key not in seen:
                seen.add(key)
                events.append(e)
    tasks_due = [t.get("title", "Untitled") for r in results for t in r[2]]

    out = {"date": f"{day:%A} {day.day} {day:%B %Y}", **day_summary(events, day, start=start, end=end),
           "tasks_due": tasks_due}
    if errors:
        out["warning"] = "Couldn't read: " + "; ".join(errors) + ". Say the answer may be incomplete."
    return out


@_tool(scope="tasks.read", risk="read")
def view_active_tasks(due: str = "", account_type: str = "any") -> dict:
    """The user's open tasks, soonest due first. Put a day in `due` (words or ISO date) to see only the
    tasks due then; leave it empty for all open tasks."""
    day = None
    if due.strip():
        day = resolve_date_string(due)
        if day is None:
            return {"error": f"I couldn't understand the date '{due}'."}

    tasks, errors = [], []
    for account in _accounts(account_type):
        try:
            for t in get_active_tasks(day, account):
                tasks.append({"title": t.get("title", "Untitled"), "due": (t.get("due") or "")[:10] or None,
                              "account": account})
        except Exception as e:
            errors.append(f"{account}: {e}")
    tasks.sort(key=lambda t: (t["due"] is None, t["due"] or ""))

    out = {"count": len(tasks), "tasks": tasks}
    if errors:
        out["warning"] = "Couldn't read: " + "; ".join(errors)
    return out


# =====================================================================
# Changing things (additive only: nothing here deletes or overwrites)
# =====================================================================
def _when(day_text, start, end):
    """Words + clock times (or full ISO datetimes) -> (start, end) as local datetimes. Raises ValueError."""
    start, end = (start or "").strip(), (end or "").strip()
    iso = r"\d{4}-\d{2}-\d{2}[T ].*"
    if not start:
        raise ValueError("I need a start time.")
    if re.fullmatch(iso, start):
        s = parse_iso_local(start)
    else:
        day = resolve_date_string(day_text)
        if day is None:
            raise ValueError(f"I couldn't understand the date '{day_text}'.")
        clock = parse_clock(start)
        if clock is None:
            raise ValueError(f"I couldn't understand the start time '{start}'.")
        s = combine_local(day, clock)

    if not end:
        e = s + timedelta(hours=1)
    elif re.fullmatch(iso, end):
        e = parse_iso_local(end)
    else:
        clock = parse_clock(end)
        if clock is None:
            raise ValueError(f"I couldn't understand the end time '{end}'.")
        e = combine_local(s.date(), clock)
    if e <= s:
        e = s + timedelta(hours=1)
    return s, e


@_tool(scope="calendar.create", risk="additive",
       triggers=("schedule", "calendar", "meeting", "event", "book", "appointment", "remind", "add", "put",
                 "block", "set up", "plan", "invite"))
def create_google_calendar_event(title: str, day: str = "today", start: str = "", end: str = "",
                                 notes: str = "", account_type: str = "personal") -> dict:
    """Add an event to the user's calendar. day is their words ("tomorrow", "next tuesday", "20 nov") or an
    ISO date; start and end are clock times like "15:00" or "3pm" (end is optional and defaults to one hour
    after start). You may instead put a full ISO datetime in start. account_type is "personal" or "business"
    (use "business" for work). Reports if the time overlaps something and skips exact duplicates."""
    account = (account_type or "personal").strip().lower()
    if account not in ACCOUNTS:
        return {"error": f"account_type must be one of {', '.join(ACCOUNTS)}."}
    try:
        s, e = _when(day, start, end)
    except ValueError as err:
        return {"error": str(err)}

    title = (title or "").strip() or "A.V.A Scheduled Task"
    try:
        service = _service("calendar", "v3", account)
        nearby = service.events().list(calendarId="primary", timeMin=s.isoformat(), timeMax=e.isoformat(),
                                       singleEvents=True, maxResults=20).execute().get("items", [])
        overlaps = []
        for ev in filter(_usable, nearby):
            ev_start = (ev.get("start") or {}).get("dateTime")
            if not ev_start:                                             # all-day events don't count as clashes
                continue
            name = ev.get("summary", "Untitled")
            if parse_iso_local(ev_start) == s and name.strip().lower() == title.lower():
                return {"ok": True, "skipped": "already on the calendar", "link": ev.get("htmlLink")}
            if ev.get("transparency") != "transparent":
                overlaps.append(name)

        description = "Generated automatically by A.V.A"
        body = {"summary": title,
                "description": f"{notes.strip()}\n\n{description}" if notes.strip() else description,
                "start": {"dateTime": s.isoformat()},                    # carries the offset, so no timeZone needed
                "end": {"dateTime": e.isoformat()}}
        created = service.events().insert(calendarId="primary", body=body).execute()
    except Exception as err:
        return {"error": f"Couldn't create the event: {err}"}

    out = {"ok": True, "created": title, "when": f"{s:%A} {s.day} {s:%B}, {s:%H:%M}-{e:%H:%M}",
           "link": created.get("htmlLink")}
    if overlaps:
        out["overlaps_with"] = overlaps
    return out


@_tool(scope="tasks.create", risk="additive",
       triggers=("task", "todo", "to-do", "remind", "reminder", "add", "note", "don't forget", "dont forget"))
def add_google_task(title: str, due: str = "", notes: str = "", account_type: str = "personal") -> dict:
    """Add a task to the user's to-do list. due is optional: their words ("friday", "20 nov") or an ISO date.
    account_type is "personal" or "business"."""
    account = (account_type or "personal").strip().lower()
    if account not in ACCOUNTS:
        return {"error": f"account_type must be one of {', '.join(ACCOUNTS)}."}
    body = {"title": (title or "").strip()}
    if not body["title"]:
        return {"error": "The task needs a title."}
    if notes.strip():
        body["notes"] = notes.strip()
    if due.strip():
        day = resolve_date_string(due)
        if day is None:
            return {"error": f"I couldn't understand the due date '{due}'."}
        body["due"] = f"{day.isoformat()}T00:00:00.000Z"                 # Google keeps due dates as UTC midnight
    try:
        result = _service("tasks", "v1", account).tasks().insert(tasklist="@default", body=body).execute()
    except Exception as err:
        return {"error": f"Couldn't add the task: {err}"}
    return {"ok": True, "added": result.get("title", body["title"]), "due": (body.get("due") or "")[:10] or None}


@_tool(scope="tasks.complete", risk="additive",
       triggers=("done", "finished", "finish", "complete", "completed", "tick off", "check off", "cross off", "mark"))
def complete_google_task(task: str, account_type: str = "any") -> dict:
    """Mark ONE open task as done. task is some words from its title. If several tasks match, it returns the
    list so you can ask the user which one they mean."""
    target = (task or "").strip().lower()
    if not target:
        return {"error": "Which task?"}

    matches, errors = [], []
    for account in _accounts(account_type):
        try:
            for item in get_active_tasks(None, account):
                if target in (item.get("title") or "").lower():
                    matches.append((account, item))
        except Exception as err:
            errors.append(f"{account}: {err}")

    exact = [m for m in matches if (m[1].get("title") or "").strip().lower() == target]
    if len(exact) == 1:
        matches = exact
    if len(matches) > 1:
        return {"ambiguous": [m[1].get("title") for m in matches[:6]], "note": "Ask the user which one."}
    if not matches:
        out = {"error": f"No open task matches '{task}'."}
        if errors:
            out["warning"] = "Couldn't read: " + "; ".join(errors)
        return out

    account, item = matches[0]
    try:
        _service("tasks", "v1", account).tasks().patch(
            tasklist="@default", task=item["id"], body={"status": "completed"}).execute()
    except Exception as err:
        return {"error": f"Couldn't mark it done: {err}"}
    return {"ok": True, "completed": item.get("title")}