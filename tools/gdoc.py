import re
from googleapiclient.discovery import build
from registry.permission import get_google_services
from registry.registry import tool

ACCOUNTS = ("personal", "business")
FOLDER_NAME = "A.V.A"
MARK_KEY, MARK_VALUE = "ava", "1"

DOC_MIME = "application/vnd.google-apps.document"
FOLDER_MIME = "application/vnd.google-apps.folder"
MAX_CHARS = 50_000
READ_CHARS = 12_000

ALLOWED_REQUESTS = {"insertText", "updateParagraphStyle", "deleteParagraphBullets", "createParagraphBullets"}

_folder_ids = {}

def _tool(scope, risk, topic="docs", triggers=()):
    """@tool, tolerant of a registry that doesn't know `topic` / `triggers` yet."""
    for extra in ({"triggers": triggers, "topic": topic}, {"triggers": triggers}, {}):
        try:
            return tool(scope=scope, risk=risk, **extra)
        except TypeError:
            continue

# set up ===============================================================================

def _services(account):
    creds = get_google_services(account_type=account)
    return (build("drive", "v3", credentials=creds, cache_discovery=False),
            build("docs", "v1", credentials=creds, cache_discovery=False))

def _account(account_type):
    name = (account_type or "personal").strip().lower()
    if name not in ACCOUNTS:
        raise ValueError(f"account_type must be one of {', '.join(ACCOUNTS)}.")
    return name

def _friendly(err):
    """Turns Google's errors into something safe and useful to say out loud."""
    text = str(err)
    if "insufficient" in text.lower() and ("scope" in text.lower() or "permission" in text.lower()):
        return ("Google Docs access isn't set up yet. Add the drive.file scope in permissions.py" "and sign in again.")
    if "404" in text or "notFound" in text or "File not found" in text:
        return "I can only open documents I created myself, and I can't find that one."
    if "has not been used" in text or "accessNotConfigured" in text or "disabled" in text.lower():
        return "The Google Docs or Drive API isn't enabled for this project in Google Cloud Console."
    return f"Google said no: {text[:120]}"

def _q(text):
    """Escapes a value for a Drive search query."""
    return str(text).replace("\\", "\\\\").replace("'", "\\'")

def _ava_folder(drive, account):
    """The 'A.V.A' folder (found, or created once). Cached per account."""
    if account in _folder_ids:
        return _folder_ids[account]
    found = drive.files().list(q=(f"mimeType='{FOLDER_MIME}' and trashed=false and appProperties has "
           f"{{ key='{MARK_KEY}' and value='folder' }}"),
        fields="files(id)", pageSize=1).execute().get("files", [])

    if found:
        _folder_ids[account] = found[0]["id"]
    else:
        made = drive.files().create(
            body={"name": FOLDER_NAME, "mimeType": FOLDER_MIME, "appProperties": {MARK_KEY: "folder"}},
            fields="id"
        ).execute()
        _folder_ids[account] = made["id"]

    return _folder_ids[account]

def _verify_mine(drive, doc_id):
    """The marker check. Raises unless this is a Google Doc that A.V.A herself created."""
    meta = drive.files().get(fileId=doc_id, fields="id,name,mimeType,appProperties,trashed,webViewLink").execute()
    props = meta.get("appProperties") or {}
    if meta.get("mimeType") != DOC_MIME or props.get(MARK_KEY) != MARK_VALUE or meta.get("trashed"):
        raise PermissionError("I can only open documents I created myself.")
    return meta

def _find_mine(drive, words, limit=10):
    """Documents she created, newest first, optionally narrowed by words from the title."""
    q = (f"mimeType='{DOC_MIME}' and trashed=False and appProperties has "f"{{key='{MARK_KEY}' and value='{MARK_VALUE}' }}")
    for w in re.findall(r"\w+", words or "")[:6]:
        q += f" and name contains'{_q(w)}'"
    return drive.files().list(q=q, orderBy = "modifiedTime desc", pageSize = limit, fields = "files(id,name,modifiedTime,webViewLink)").execute().get("files", [])

def _resolve(drive, doc):
    """An id, or words from a title -> one verified document. Returns (meta, None) or (None, error dict)."""
    doc = (doc or "").strip()
    if re.fullmatch(r"[\w-]{20,}", doc):
        return _verify_mine(drive, doc), None
    matches = _find_mine(drive, doc)
    if not matches:
        return None, {"error": f"I haven't made a document matching '{doc}'."}
    if len(matches) > 1:
        return None, {"ambiguous": [{"id": m["id"], "name": m["name"]} for m in matches[:6]],
                      "note": "Ask the user which one."}
    return _verify_mine(drive, matches[0]["id"]), None

# text & doc requests ==================================================================================

def _u16(text):
    """Length in UTF-16 code units, which is how the Docs API counts positions (emoji count as 2)."""
    return len(text.encode("utf-16-le")) // 2

def _plan(markdown):
    """Simple markdown ('# Heading', '- bullet') -> (plain lines, heading ranges, bullet ranges),
    with positions relative to the start of the inserted text."""
    lines, headings, bullets = [], [], []
    pos = 0
    for raw in markdown.replace("\r\n", "\n").split("\n"):
        text, style, bullet = raw, None, False
        m = re.match(r"^(#{1,3})\s+(.*)$", raw)
        if m:
            style, text = f"HEADING_{len(m.group(1))}", m.group(2)
        else:
            m = re.match(r"^\s*[-*\u2022]\s+(.*)$", raw)
            if m:
                bullet, text = True, m.group(1)
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)                        # bold markers are dropped, not shown
        end = pos + _u16(text) + 1                                          # +1 for the paragraph's newline
        if style:
            headings.append((pos, end, style))
        if bullet:
            bullets.append((pos, end))
        lines.append(text)
        pos = end
    return lines, headings, bullets

def _requests(markdown, insert_at, doc_has_text):
    """Docs requests that add the text at `insert_at` (the index just before the document's final newline)."""
    lines, headings, bullets = _plan(markdown)
    prefix = "\n" if doc_has_text else ""                                   # start on a fresh paragraph
    body = "\n".join(lines)
    start = insert_at + _u16(prefix)
    end = start + _u16(body) + 1
    reqs = [{"insertText": {"location": {"index": insert_at}, "text": prefix + body}},
            # new paragraphs inherit the style/bullets of the paragraph they were typed into: reset, then apply
            {"updateParagraphStyle": {"range": {"startIndex": start, "endIndex": end},
                                      "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"}, "fields": "namedStyleType"}},
            {"deleteParagraphBullets": {"range": {"startIndex": start, "endIndex": end}}}]
    for a, b, style in headings:
        reqs.append({"updateParagraphStyle": {"range": {"startIndex": start + a, "endIndex": start + b},
                                              "paragraphStyle": {"namedStyleType": style}, "fields": "namedStyleType"}})
    merged = []                                                           
    for a, b in bullets:
        if merged and merged[-1][1] == a:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    for a, b in merged:
        reqs.append({"createParagraphBullets": {"range": {"startIndex": start + a, "endIndex": start + b},
                                                "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"}})
    assert all(next(iter(r)) in ALLOWED_REQUESTS for r in reqs)
    return reqs


def _doc_text(doc):
    """All the text of a Docs document, tables included."""
    def walk(content):
        parts = []
        for el in content or []:
            if "paragraph" in el:
                parts.append("".join(e.get("textRun", {}).get("content", "")
                                     for e in el["paragraph"].get("elements", [])))
            elif "table" in el:
                for row in el["table"].get("tableRows", []):
                    parts.append(" | ".join(walk(c.get("content")).strip().replace("\n", " ")
                                            for c in row.get("tableCells", [])) + "\n")
        return "".join(parts)
    return walk(doc.get("body", {}).get("content"))


def _end_index(doc):
    content = doc.get("body", {}).get("content") or [{"endIndex": 2}]
    return content[-1]["endIndex"]


def _write(docs, doc_id, markdown):
    doc = docs.documents().get(documentId=doc_id).execute()
    end = _end_index(doc)
    has_text = bool(_doc_text(doc).strip())
    docs.documents().batchUpdate(documentId=doc_id,
                                 body={"requests": _requests(markdown, end - 1, has_text)}).execute()


# tools ====================================================================================
@_tool(scope="docs.create", risk="additive",
       triggers=("doc", "docs", "document", "write", "draft", "outline", "notes", "summary", "report", "plan"))
def create_google_doc(title: str, content: str = "", account_type: str = "personal") -> dict:
    """Create a NEW Google Doc. content is optional and may use simple markdown: "# Heading", "## Subheading",
    "- bullet". It is saved in the user's "A.V.A" folder. I can only create new documents; I can never open
    or change any other document the user owns."""
    try:
        account = _account(account_type)
        title = " ".join((title or "").split())[:200] or "Untitled"
        content = (content or "")[:MAX_CHARS]
        drive, docs = _services(account)
        made = drive.files().create(
            body={"name": title, "mimeType": DOC_MIME, "parents": [_ava_folder(drive, account)],
                  "appProperties": {MARK_KEY: MARK_VALUE}},
            fields="id,webViewLink").execute()
        if content.strip():
            _write(docs, made["id"], content)
        return {"ok": True, "created": title, "link": made.get("webViewLink"), "id": made["id"]}
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": _friendly(e)}


@_tool(scope="docs.read", risk="read")
def read_google_doc(doc: str = "", account_type: str = "personal") -> dict:
    """Read a Google Doc that A.V.A created. doc is its id or some words from its title. Leave doc empty to list
    the documents I've made, newest first. I can only read documents I created myself."""
    try:
        account = _account(account_type)
        drive, docs = _services(account)
        if not (doc or "").strip():
            mine = _find_mine(drive, "")
            return {"count": len(mine), "documents": [{"id": d["id"], "name": d["name"],
                                                       "modified": d["modifiedTime"][:10]} for d in mine]}
        meta, problem = _resolve(drive, doc)
        if problem:
            return problem
        text = _doc_text(docs.documents().get(documentId=meta["id"]).execute()).strip()
        out = {"name": meta["name"], "link": meta.get("webViewLink"), "text": text[:READ_CHARS],
               "truncated": len(text) > READ_CHARS}
        if not text:
            out["note"] = "The document is empty."
        return out
    except ValueError as e:
        return {"error": str(e)}
    except PermissionError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": _friendly(e)}


@_tool(scope="docs.append", risk="additive",
       triggers=("add", "append", "doc", "docs", "document", "update", "write", "continue"))
def append_to_google_doc(doc: str, content: str, account_type: str = "personal") -> dict:
    """Add text to the END of a Google Doc that A.V.A created (doc is its id or words from its title).
    content may use simple markdown ("# Heading", "- bullet"). Nothing already in the document is changed or
    removed. I can only add to documents I created myself."""
    try:
        account = _account(account_type)
        content = (content or "")[:MAX_CHARS]
        if not content.strip():
            return {"error": "There's nothing to add."}
        drive, docs = _services(account)
        meta, problem = _resolve(drive, doc)
        if problem:
            return problem
        _write(docs, meta["id"], content)
        return {"ok": True, "added_to": meta["name"], "link": meta.get("webViewLink")}
    except ValueError as e:
        return {"error": str(e)}
    except PermissionError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": _friendly(e)}
