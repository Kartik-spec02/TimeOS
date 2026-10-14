import sqlite3
import json
from datetime import datetime, timedelta
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
import uvicorn

mcp = FastMCP(
    "TimeOS",
    host="127.0.0.1",
    port=8765,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False)
)

DB_PATH = "data/timeos.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            movable INTEGER DEFAULT 1
        )
    """)
    conn.commit()
    conn.close()


def get_all_events():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, start_time, end_time, movable FROM events")
    rows = cursor.fetchall()
    conn.close()
    events = []
    for row in rows:
        events.append({
            "id": row[0],
            "title": row[1],
            "start_time": row[2],
            "end_time": row[3],
            "movable": bool(row[4])
        })
    return events


def find_conflicts(new_start, new_end, exclude_id=None):
    conflicts = []
    for event in get_all_events():
        if exclude_id is not None and event["id"] == exclude_id:
            continue
        existing_start = datetime.fromisoformat(event["start_time"])
        existing_end = datetime.fromisoformat(event["end_time"])
        if new_start < existing_end and existing_start < new_end:
            conflicts.append(event)
    return conflicts


@mcp.tool()
def add_event(title: str, start_time: str, end_time: str, movable: bool = True) -> str:
    """Add an event. Returns a clash payload if it conflicts with an existing event."""
    try:
        new_start = datetime.fromisoformat(start_time)
        new_end = datetime.fromisoformat(end_time)
    except ValueError:
        return "Error: Use ISO format like 2026-10-20T05:00:00"

    conflicts = find_conflicts(new_start, new_end)

    if conflicts:
        conflict_details = []
        for c in conflicts:
            tag = " [movable]" if c["movable"] else " [fixed]"
            conflict_details.append(
                f"'{c['title']}' (ID {c['id']}) from {c['start_time']} to {c['end_time']}{tag}"
            )
        return (
            f"CONFLICT: '{title}' from {start_time} to {end_time} clashes with: "
            f"{conflict_details}. "
            f"Options: (1) move a conflicting event using update_event, "
            f"(2) pick a free slot using find_free_slots, "
            f"or (3) accept the overlap by calling force_add_event. "
            f"Nothing was created yet."
        )

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO events (title, start_time, end_time, movable) VALUES (?, ?, ?, ?)",
        (title, start_time, end_time, 1 if movable else 0)
    )
    conn.commit()
    event_id = cursor.lastrowid
    conn.close()
    return f"Event '{title}' created with ID {event_id}."


@mcp.tool()
def force_add_event(title: str, start_time: str, end_time: str) -> str:
    """Add an event even if it overlaps with an existing event."""
    try:
        datetime.fromisoformat(start_time)
        datetime.fromisoformat(end_time)
    except ValueError:
        return "Error: Use ISO format like 2026-10-20T05:00:00"

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO events (title, start_time, end_time, movable) VALUES (?, ?, ?, ?)",
        (title, start_time, end_time, 1)
    )
    conn.commit()
    event_id = cursor.lastrowid
    conn.close()
    return f"Event '{title}' force-created with ID {event_id} (overlap accepted)."


@mcp.tool()
def update_event(event_id: int, new_start_time: str, new_end_time: str) -> str:
    """Move an existing event to a new time."""
    try:
        new_start = datetime.fromisoformat(new_start_time)
        new_end = datetime.fromisoformat(new_end_time)
    except ValueError:
        return "Error: Use ISO format like 2026-10-20T05:00:00"

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, start_time, end_time, movable FROM events WHERE id = ?", (event_id,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return f"Error: No event with ID {event_id}."

    if not row[4]:
        return f"Error: Event '{row[1]}' is marked as fixed and cannot be moved."

    conflicts = find_conflicts(new_start, new_end, exclude_id=event_id)
    if conflicts:
        conflict_titles = [f"'{c['title']}' (ID {c['id']})" for c in conflicts]
        return (
            f"CONFLICT: Moving '{row[1]}' to {new_start_time} to {new_end_time} clashes with: "
            f"{conflict_titles}. Nothing was moved yet."
        )

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE events SET start_time = ?, end_time = ? WHERE id = ?",
        (new_start_time, new_end_time, event_id)
    )
    conn.commit()
    conn.close()
    return f"Event '{row[1]}' (ID {event_id}) moved to {new_start_time} to {new_end_time}."


@mcp.tool()
def delete_event(event_id: int) -> str:
    """Delete an event by ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT title FROM events WHERE id = ?", (event_id,))
    row = cursor.fetchone()
    if row is None:
        conn.close()
        return f"Error: No event with ID {event_id}."
    cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()
    return f"Event '{row[0]}' (ID {event_id}) deleted."


@mcp.tool()
def get_events(date: str) -> str:
    """Get all events on a specific date (YYYY-MM-DD)."""
    all_events = [e for e in get_all_events() if e["start_time"].startswith(date)]
    all_events.sort(key=lambda e: e["start_time"])
    if not all_events:
        return f"No events on {date}."
    return json.dumps(all_events, indent=2)


@mcp.tool()
def find_free_slots(date: str, duration_minutes: int) -> str:
    """Find free time slots on a date (within 08:00-22:00)."""
    all_events = [e for e in get_all_events() if e["start_time"].startswith(date)]
    all_events.sort(key=lambda e: e["start_time"])

    day_start = datetime.fromisoformat(f"{date}T08:00:00")
    day_end = datetime.fromisoformat(f"{date}T22:00:00")

    free_slots = []
    cursor_time = day_start

    for event in all_events:
        event_start = datetime.fromisoformat(event["start_time"])
        event_end = datetime.fromisoformat(event["end_time"])

        if event_end <= day_start or event_start >= day_end:
            continue

        if event_start > cursor_time:
            gap_minutes = (event_start - cursor_time).total_seconds() / 60
            if gap_minutes >= duration_minutes:
                free_slots.append(f"{cursor_time.isoformat()} to {event_start.isoformat()}")

        if event_end > cursor_time:
            cursor_time = event_end

    if cursor_time < day_end:
        gap_minutes = (day_end - cursor_time).total_seconds() / 60
        if gap_minutes >= duration_minutes:
            free_slots.append(f"{cursor_time.isoformat()} to {day_end.isoformat()}")

    if not free_slots:
        return f"No free slots of {duration_minutes} minutes on {date}."
    return f"Free slots on {date}: {free_slots}"


@mcp.tool()
def suggest_resolution(conflicting_title: str, start_time: str, end_time: str, date: str) -> str:
    """When a clash exists, suggest which event to move and where."""
    try:
        new_start = datetime.fromisoformat(start_time)
        new_end = datetime.fromisoformat(end_time)
    except ValueError:
        return "Error: Use ISO format like 2026-10-20T05:00:00"

    duration = (new_end - new_start).total_seconds() / 60
    conflicts = find_conflicts(new_start, new_end)

    movable_conflicts = [c for c in conflicts if c["movable"]]
    fixed_conflicts = [c for c in conflicts if not c["movable"]]

    lines = []
    lines.append(f"Analyzing clash for '{conflicting_title}' ({start_time} to {end_time}).")

    if fixed_conflicts:
        fixed_names = [f"'{c['title']}' (ID {c['id']})" for c in fixed_conflicts]
        lines.append(f"Fixed events in the way: {fixed_names}. These cannot be moved.")

    if movable_conflicts:
        movable_names = [f"'{c['title']}' (ID {c['id']})" for c in movable_conflicts]
        lines.append(f"Movable events in the way: {movable_names}.")
        lines.append(f"Recommended: call find_free_slots for {date} with duration_minutes={int(duration)}, then update_event to move one of the movable events.")
    else:
        lines.append("No movable events to shift. Recommend calling force_add_event to accept the overlap, or choosing a different time.")

    return "\n".join(lines)


@mcp.tool()
def resolve_conflict(
    blocked_title: str,
    blocked_start: str,
    blocked_end: str,
    conflict_event_id: int
) -> str:
    """Move a conflicting event to the next available slot, then add the blocked event."""
    try:
        blocked_s = datetime.fromisoformat(blocked_start)
        blocked_e = datetime.fromisoformat(blocked_end)
    except ValueError:
        return "Error: Use ISO format like 2026-10-20T05:00:00"

    date = blocked_start[:10]

    all_events = [e for e in get_all_events() if e["start_time"].startswith(date)]
    all_events.sort(key=lambda e: e["start_time"])

    day_start = datetime.fromisoformat(f"{date}T08:00:00")
    day_end = datetime.fromisoformat(f"{date}T22:00:00")

    busy = [(datetime.fromisoformat(e["start_time"]), datetime.fromisoformat(e["end_time"])) for e in all_events]

    def free_slots():
        slots = []
        cursor = day_start
        for s, e in busy:
            if e <= day_start or s >= day_end:
                continue
            if s > cursor:
                slots.append((cursor, s))
            cursor = max(cursor, e)
        if cursor < day_end:
            slots.append((cursor, day_end))
        return slots

    conflict_event = None
    for e in all_events:
        if e["id"] == conflict_event_id:
            conflict_event = e
            break

    if conflict_event is None:
        return f"Error: No event with ID {conflict_event_id}."

    if not conflict_event["movable"]:
        return f"Error: Event '{conflict_event['title']}' is fixed and cannot be moved."

    orig_dur = (
        datetime.fromisoformat(conflict_event["end_time"])
        - datetime.fromisoformat(conflict_event["start_time"])
    ).total_seconds() / 60

    new_start = None
    new_end = None
    for s, e in free_slots():
        if (e - s).total_seconds() / 60 >= orig_dur:
            new_start = s
            new_end = s + timedelta(minutes=orig_dur)
            break

    if new_start is None:
        return f"Could not find a new slot for '{conflict_event['title']}'."

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE events SET start_time = ?, end_time = ? WHERE id = ?",
        (new_start.isoformat(), new_end.isoformat(), conflict_event_id)
    )
    conn.commit()
    conn.close()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO events (title, start_time, end_time, movable) VALUES (?, ?, ?, ?)",
        (blocked_title, blocked_start, blocked_end, 1)
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()

    return (
        f"Moved '{conflict_event['title']}' to "
        f"{new_start.isoformat()}-{new_end.isoformat()}, "
        f"and created '{blocked_title}' (ID {new_id}) at "
        f"{blocked_start}-{blocked_end}."
    )


class CORSWrapper:
    """ASGI middleware that adds CORS headers and handles OPTIONS preflight."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if scope["method"] == "OPTIONS":
            headers = [
                (b"access-control-allow-origin", b"*"),
                (b"access-control-allow-methods", b"GET, POST, OPTIONS"),
                (b"access-control-allow-headers", b"*"),
                (b"access-control-expose-headers", b"mcp-session-id"),
                (b"access-control-max-age", b"86400"),
            ]
            await send({
                "type": "http.response.start",
                "status": 204,
                "headers": headers,
            })
            await send({"type": "http.response.body", "body": b""})
            return

        async def wrapped_send(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"access-control-allow-origin", b"*"))
                headers.append((b"access-control-expose-headers", b"mcp-session-id"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, wrapped_send)


if __name__ == "__main__":
    init_db()
    app = mcp.streamable_http_app()
    wrapped = CORSWrapper(app)
    uvicorn.run(wrapped, host="127.0.0.1", port=8765)