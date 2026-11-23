# registry/topics.py
# Decides which groups of tools ("topics") are worth sending to the model for THIS message.
# Tool schemas are sent with every request and cost tokens, so calendar tools only travel with calendar talk,
# media tools with music talk, and so on. Tools with no topic (think_harder, memory_read, request_tools) always go.
#
# Matching is deliberately generous: a false match only costs a few hundred tokens, while a miss would hide a
# tool. And if a miss does happen, the model can call request_tools(topic) to load the group itself.
import re

_DAYS = r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|tues?|thu(?:rs?)?|fri"
_MONTHS = r"january|february|march|april|may|june|july|august|september|october|november|december"

TOPICS = {
    "calendar": (
        r"\b(?:calendar|agenda|schedule[sd]?|timetable|meetings?|appointments?|events?|class(?:es)?|lessons?|"
        r"exams?|deadlines?|due|free|busy|available|availability|plans|booked|book|invite|reschedule|"
        r"what'?s on|do i have|anything on)\b"
        rf"|\b(?:today|tonight|tomorrow|tmr|tmrw|yesterday|week|weekend|month|{_DAYS}|{_MONTHS})\b"
        r"|\b\d{1,2}\s*(?:st|nd|rd|th)?\s*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b"
        r"|\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b|\b\d{1,2}[/-]\d{1,2}\b"
        r"|\b(?:time ?zone|new york|nyc|london|tokyo|sydney|utc|gmt|est|edt|pst|pdt)\b"
    ),
    "tasks": (
        r"\b(?:tasks?|to-?do|to do|remind(?:er|ers)?|checklist|check (?:it )?off|cross (?:it )?off|"
        r"tick (?:it )?off|mark (?:it )?(?:as )?(?:done|complete)|done|finished|completed?)\b"
    ),
    "media": (
        r"\b(?:play(?:ing)?|music|songs?|tracks?|albums?|artists?|spotify|youtube|playlists?|listen(?:ing)?|"
        r"put on|watch(?:ing)?|documentar(?:y|ies)|vibes?|mood|mix|queue|lofi|jazz|chill|sth|something to)\b"
    ),
    "files": (
        r"\b(?:files?|folders?|documents?|downloads?|downloaded|pdfs?|docx?|essays?|notes|slides|spreadsheets?|"
        r"my (?:laptop|computer|pc)|find my|where(?:'s| is| did)|that (?:file|doc|document|pdf|essay)|"
        r"i (?:saved|wrote|downloaded)|open (?:the|my|that)|read (?:it|that|the|my))\b"
    ),
    "screen": (
        r"\b(?:screen|window|tab|error|this (?:page|code|file|tab|email|message|article|doc|video|site)|"
        r"looking at|watching|reading|working on|clipboard|copied|selected|highlighted|what am i|"
        r"summari[sz]e this|explain this|read this|fix this|what'?s this|what is this)\b"
    ),
    "docs": (
        r"\b(?:google\s*docs?|gdocs?|docs?|documents?|write|draft|outline|notes|summary|report|append|add to)\b"
    )
}

_COMPILED = {name: re.compile(pattern, re.I) for name, pattern in TOPICS.items()}


def active_topics(*texts):
    """Topics mentioned in the given texts (pass the last few messages plus the new one)."""
    blob = " ".join(t for t in texts if t)
    return {name for name, rx in _COMPILED.items() if rx.search(blob)}