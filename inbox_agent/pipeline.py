"""One email in, one outcome out: classify, apply the rules, then draft, judge and revise."""
from dataclasses import dataclass, field

from . import draft as drafting
from .classify import classify
from .judge import judge
from .notes import search
from .policy import decide


@dataclass
class Outcome:
    action: str        # auto_send | draft | human | ignore
    why: str
    label: object
    reply: str = ""
    sources: list = field(default_factory=list)    # which notes the reply was built from
    attempts: list = field(default_factory=list)   # (draft, verdict) for every draft judged


def handle(email, llm, notes):
    label = classify(email, llm)
    decision = decide(label, email)
    out = Outcome(decision.action, decision.why, label)
    if decision.action not in ("auto_send", "draft"):
        return out

    found = search(f"{email.subject} {email.body}", notes)
    out.sources = [note.source for note in found]
    notes_text = "\n\n".join(note.text for note in found) or "(nothing in the notes matches)"

    reply = drafting.write(email, notes_text, llm)
    if not reply:
        out.action, out.why = "human", "the draft came back empty or cut off"
        return out
    verdict = judge(email, reply, notes_text, llm)
    out.attempts.append((reply, verdict))
    if not verdict.passed:
        fixed = drafting.revise(email, reply, verdict.issues, notes_text, llm)
        if fixed:
            reply, verdict = fixed, judge(email, fixed, notes_text, llm)
            out.attempts.append((reply, verdict))
    out.reply = reply

    # The judge can only make things safer: a failed auto-send becomes a draft, never the reverse.
    if not verdict.passed:
        if out.action == "auto_send":
            out.action = "draft"
        out.why = "judge: " + "; ".join(verdict.issues)
    return out
