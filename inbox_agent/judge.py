"""Step 4: score the draft. The model gives a verdict, and the code decides what it means."""
import re
from dataclasses import dataclass, field

from .classify import BUSINESS, parse_json

FLOOR = 7   # out of 10

PROMPT = """TASK: judge
Score this reply from {business}, 0 to 10.
It passes only if it answers what was asked, uses only facts from the notes, promises
nothing the notes do not, and is polite and short. 7 or more is a pass.

--- notes ---
{notes}

--- email ---
Subject: {subject}

{body}

--- reply ---
{draft}

Answer with JSON only:
{{"pass": true or false, "score": <0 to 10>, "issues": ["<short problem>", ...]}}
"""

# Prices, clock times, durations and percentages: the facts a customer acts on.
FACT = re.compile(r"\$\s?\d+(?:\.\d\d)?|\b\d{1,2}(?::\d\d)?\s?(?:am|pm)\b"
                  r"|\b\d+\s?(?:working |business )?(?:days?|weeks?|hours?)\b|\b\d+\s?%", re.I)


@dataclass
class Verdict:
    passed: bool
    score: float | None = None
    issues: list = field(default_factory=list)


def parse_verdict(text, truncated=False):
    if truncated:
        return Verdict(False, issues=["judge answer was cut off"])
    data = parse_json(text)
    if not isinstance(data, dict):
        return Verdict(False, issues=["judge answer was not JSON"])
    try:
        score = float(data["score"])
    except (KeyError, TypeError, ValueError):
        score = None
    issues = [str(i) for i in data.get("issues") or []]
    passed = data.get("pass") is True
    # The prompt says 7 is a pass. Models still answer pass: true with a 4, or with no score.
    if passed and (score is None or score < FLOOR):
        passed = False
        issues.append(f"score {score} is under the floor of {FLOOR}")
    return Verdict(passed, score, issues)


def _norm(fact):
    fact = re.sub(r"\s|working|business", "", fact.lower())
    return fact[:-1] if fact.endswith("s") else fact   # "2 days" is the same fact as "2 day"


def ungrounded(draft, notes):
    """Facts in the draft that appear nowhere in the notes the drafter was given."""
    known = {_norm(f) for f in FACT.findall(notes)}
    return [f for f in FACT.findall(draft) if _norm(f) not in known]


def judge(email, draft, notes, llm):
    prompt = PROMPT.format(business=BUSINESS, notes=notes, subject=email.subject,
                           body=email.body, draft=draft)
    reply = llm.complete(prompt, max_tokens=300)
    verdict = parse_verdict(reply.text, reply.truncated)
    # This check is code, so it runs even when the judge model misses an invented price.
    invented = ungrounded(draft, notes)
    if invented:
        verdict.passed = False
        verdict.issues.append("not in the notes: " + ", ".join(invented))
    return verdict
