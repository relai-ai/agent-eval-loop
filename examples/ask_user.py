"""Handlers for an ask_user tool served by mcp_service.py: a simulated or scripted user answers the agent's questions.

Agents that take a single request (most agents Harbor installs) cannot hold a conversation with a
launcher, so an agent-neutral task gives every agent the same way to ask its user: an ask_user
tool. Copy this file as a service's handlers.py and add to the service's tools.json:

  {"name": "ask_user",
   "description": "Ask the user a question and wait for the answer. Use it when you need information or a decision only the user has.",
   "inputSchema": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]}}

The user answers in one of two ways, chosen by the service's state.json:

- Scripted: "replies" lists fixed answers. The first question gets the first reply, the second
  the second, and every later question the last one. No model is called, so the oracle run stays
  free and the test's verdict does not depend on a user model. Use it when the user's decision is
  fixed by the scenario, and write each reply so it settles every case the scoring depends on.

    {"request": "<the text of instruction.md>", "replies": ["<the user's decision>", "<later answers>"]}

- Simulated: a model plays the user from its goal and knowledge. Put launcher.py beside this file
  (its simulated_user_turn makes the model call). The model key comes from RELAI_USER_SIM_KEY in
  the service's environment, so it never enters the agent's container.

    {"request": "<the text of instruction.md>",
     "user": {"instructions": "You are ... Your goal ... You know ...", "model": "anthropic:<model id>"},
     "max_questions": 6}

Either way the conversation is kept in state["history"] and journaled like any other call, so the
verifier and judges can read every question and answer. When the scoring depends on what the
agent did before or after asking, serve ask_user from the same service as the tools it guards
(merge these handlers into that service's handlers.py), so one journal orders every call.
"""

from __future__ import annotations

import os

try:
    from launcher import simulated_user_turn
except ImportError:
    simulated_user_turn = None

NOTHING_TO_ADD = "The user has nothing more to add."


def ask_user(state: dict, arguments: dict) -> str:
    question = str(arguments.get("question") or "").strip()
    if not question:
        raise ToolError("ask_user needs a question")
    history = state.setdefault("history", [])
    if not history:
        history.append({"role": "user", "content": state.get("request", "")})
    asked = sum(1 for m in history if m["role"] == "assistant")
    replies = state.get("replies")
    if replies:
        history.append({"role": "assistant", "content": question})
        reply = str(replies[min(asked, len(replies) - 1)])
        history.append({"role": "user", "content": reply})
        return reply
    if asked >= int(state.get("max_questions", 6)):
        return NOTHING_TO_ADD
    history.append({"role": "assistant", "content": question})
    key = os.environ.get("RELAI_USER_SIM_KEY", "")
    if not key:
        raise RuntimeError("RELAI_USER_SIM_KEY is unset in the user service's environment")
    if simulated_user_turn is None:
        raise RuntimeError("launcher.py is missing beside handlers.py; a simulated user needs it")
    reply, done = simulated_user_turn(state["user"], history, key)
    if done:
        return NOTHING_TO_ADD
    history.append({"role": "user", "content": reply})
    return reply
