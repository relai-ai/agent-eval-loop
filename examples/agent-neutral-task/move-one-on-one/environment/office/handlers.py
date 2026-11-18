"""Email and calendar handlers for the office service, served by mcp_service.py. ToolError is provided by the service."""

from __future__ import annotations

import re

TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$")
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def new_id(state: dict, prefix: str) -> str:
    """The next id with this prefix that no seeded or created record already uses."""
    taken = {item["id"] for key in ("inbox", "sent", "events") for item in state.get(key, [])}
    while True:
        number = state["next_id"]
        state["next_id"] = number + 1
        if f"{prefix}-{number}" not in taken:
            return f"{prefix}-{number}"


def summary(message: dict) -> dict:
    return {"id": message["id"], "from": message["from"], "subject": message["subject"], "date": message["date"],
            "snippet": message["body"][:80]}


def search_email(state: dict, arguments: dict) -> list:
    words = str(arguments.get("query") or "").lower().split()
    found = [m for m in state["inbox"]
             if all(w in f"{m['from']} {m['subject']} {m['body']}".lower() for w in words)]
    return [summary(m) for m in sorted(found, key=lambda m: m["date"], reverse=True)]


def read_email(state: dict, arguments: dict) -> dict:
    for message in state["inbox"] + state["sent"]:
        if message["id"] == arguments.get("id"):
            return message
    raise ToolError(f"no message with id {arguments.get('id')!r}")


def send_email(state: dict, arguments: dict) -> dict:
    to = arguments.get("to")
    if not isinstance(to, list) or not to or not all(isinstance(a, str) and "@" in a for a in to):
        raise ToolError("to must be a list of email addresses")
    message = {"id": new_id(state, "sent"), "from": state["user"], "to": to,
               "subject": str(arguments.get("subject") or ""), "body": str(arguments.get("body") or ""),
               "in_reply_to": arguments.get("in_reply_to"), "date": f"{state['today']}T12:00"}
    state["sent"].append(message)
    return {"id": message["id"], "status": "sent"}


def list_events(state: dict, arguments: dict) -> list:
    start, end = arguments.get("start_date"), arguments.get("end_date")
    if not (isinstance(start, str) and DAY.match(start) and isinstance(end, str) and DAY.match(end)):
        raise ToolError("start_date and end_date must be dates as YYYY-MM-DD")
    return sorted((e for e in state["events"] if start <= e["start"][:10] <= end), key=lambda e: e["start"])


def check_times(start, end) -> None:
    if not (isinstance(start, str) and TIME.match(start) and isinstance(end, str) and TIME.match(end)):
        raise ToolError("start and end must be local times as YYYY-MM-DDTHH:MM")
    if end <= start:
        raise ToolError("end must be after start")


def create_event(state: dict, arguments: dict) -> dict:
    check_times(arguments.get("start"), arguments.get("end"))
    event = {"id": new_id(state, "evt"), "title": str(arguments.get("title") or ""),
             "start": arguments["start"], "end": arguments["end"],
             "attendees": list(arguments.get("attendees") or [state["user"]])}
    state["events"].append(event)
    return event


def update_event(state: dict, arguments: dict) -> dict:
    for event in state["events"]:
        if event["id"] == arguments.get("id"):
            start, end = arguments.get("start", event["start"]), arguments.get("end", event["end"])
            check_times(start, end)
            event.update(start=start, end=end)
            if "title" in arguments:
                event["title"] = str(arguments["title"])
            if "attendees" in arguments:
                event["attendees"] = list(arguments["attendees"] or [])
            return event
    raise ToolError(f"no event with id {arguments.get('id')!r}")


def delete_event(state: dict, arguments: dict) -> dict:
    for index, event in enumerate(state["events"]):
        if event["id"] == arguments.get("id"):
            del state["events"][index]
            return {"id": event["id"], "status": "deleted"}
    raise ToolError(f"no event with id {arguments.get('id')!r}")
