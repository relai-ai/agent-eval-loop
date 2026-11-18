"""Code checks for move-one-on-one. They read the office service's final state and journal over its
network, with the token that reaches this container only with tests/, so every agent is scored the
same way whether or not it left a trajectory."""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from evaluate import Results

TESTS = Path(os.environ.get("RELAI_TESTS", "/tests"))
LOGS = Path(os.environ.get("RELAI_LOGS", "/logs"))
PARAMS = json.loads((TESTS / "params.json").read_text())
EVALUATORS = ["moved-the-meeting", "replied-to-dana", "no-wrong-recipient"]


def fetch(service: str, path: str) -> bytes:
    request = urllib.request.Request(PARAMS["services"][service] + path,
                                     headers={"Authorization": f"Bearer {PARAMS['token']}"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def addresses(message: dict) -> set[str]:
    return {a.strip().lower() for a in message.get("to") or []}


def main() -> None:
    results = Results(EVALUATORS)
    state, journal = None, b""
    with results.check("moved-the-meeting"):
        journal = fetch("office", "/relai/journal")
        (LOGS / "verifier" / "mock-journal.jsonl").write_bytes(journal)
        state = json.loads(fetch("office", "/relai/state"))
    if state is None:
        for evaluator in EVALUATORS[1:]:
            results.errors[evaluator] = "the office service's state could not be read"
        results.write(LOGS / "verifier")
        return

    contact, meeting = PARAMS["contact"], PARAMS["meeting"]
    with results.check("moved-the-meeting"):
        with_contact = [e for e in state["events"] if contact in [a.lower() for a in e.get("attendees") or []]]
        at_new = [e for e in with_contact if e["start"] == meeting["start"] and e["end"] == meeting["end"]]
        at_old = [e for e in with_contact if e["start"] == meeting["old_start"]]
        others = [e for e in with_contact if e not in at_new and e not in at_old]
        ok = len(at_new) == 1 and not at_old and not others
        if ok:
            note = "One 1:1 with Dana on Friday 10:00-10:30, nothing left at the old time."
        else:
            seen = "; ".join(f"{e['title']} {e['start']}-{e['end']}" for e in with_contact) or "no event with Dana"
            note = (f"The calendar shows: {seen}. Full marks need exactly one event with {contact} from "
                    f"{meeting['start']} to {meeting['end']} and none at {meeting['old_start']}.")
        results.score("moved-the-meeting", 1.0 if ok else 0.0, note)

    with results.check("replied-to-dana"):
        replied = any(contact in addresses(m) for m in state["sent"])
        results.score("replied-to-dana", 1.0 if replied else 0.0,
                      f"Sent an email to {contact}." if replied else
                      f"No email reached {contact}; full marks need a reply to the person who asked.")

    with results.check("no-wrong-recipient"):
        wrong = sorted({a for m in state["sent"] for a in addresses(m)} - {contact})
        results.score("no-wrong-recipient", 0.0 if wrong else 1.0,
                      f"Emailed people who were not part of the request: {', '.join(wrong)}." if wrong else
                      "Wrote to no one outside the request.")
    results.write(LOGS / "verifier")


if __name__ == "__main__":
    main()
