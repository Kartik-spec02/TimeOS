# TimeOS — Clash-Aware Calendar for Alexa+

TimeOS is an MCP (Model Context Protocol) server that gives Alexa+ a smarter calendar. When you try to schedule something that clashes with an existing event, TimeOS doesn't just book it — it pauses, shows you what's in the way, and asks how you want to resolve the conflict.

Built for **Build, Ship, Shape: Amazon Developer Hackathon 2026** — Alexa+ track.

## The Problem

Voice assistants book calendar events blindly. Say "add a meeting at 10am" and it's done — even if you already have something at 10am. You only find out later, when it's too late.

## The Fix

TimeOS treats every scheduling request as a decision point. If there's a clash, it returns a **structured clash payload** — not an error, not a silent booking. The payload lists the conflicting events, marks each as movable or fixed, and offers three options:

1. **Move** a conflicting event (via `update_event`)
2. **Pick a free slot** (via `find_free_slots`)
3. **Accept the overlap** (via `force_add_event`)

Nothing is created until you choose. This is "bounded autonomy" — the agent acts, but only within limits you approve.

## Tools Exposed

| Tool | What it does |
|---|---|
| `add_event` | Add an event. Returns a clash payload if it conflicts. |
| `force_add_event` | Add an event even if it overlaps (after explicit user consent). |
| `update_event` | Move an existing event to a new time. Refuses if the new time clashes. |
| `delete_event` | Remove an event by ID. |
| `get_events` | List all events on a given date. |
| `find_free_slots` | Find free time gaps on a date that fit a given duration. |
| `suggest_resolution` | When a clash exists, recommend which event to move and where. |

## How It Works

- **Python MCP server** using `mcp` v1.x (FastMCP).
- **SQLite** for persistent event storage (`data/timeos.db`).
- **Streamable HTTP** transport so the server is reachable over the network.
- **CORS wrapper** so browser-based clients can call it.
- **Web simulator** (`alexa_sim.html`) that acts as the Alexa+ stand-in, since Amazon's MCP Toolkit is partner-only.

## Running It

### First-time setup

```powershell
cd D:\TimeOS
python -m venv venv
venv\Scripts\activate
pip install "mcp<2"
pip install uvicorn