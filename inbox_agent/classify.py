"""Step 1: ask the model what kind of email this is, and who would pay whom."""
import json
import re
from dataclasses import dataclass

BUSINESS = "Kettle Lane Cycles"

CATEGORIES = {
    "faq": "a general question the shop notes answer (hours, location, what we fix)",
    "booking": "wants to book a service or a repair",
    "quote": "wants us to give them a price",
    "repair_status": "asks about a bike that is already with us",
    "complaint": "unhappy with work we did",
    "refund": "wants money back",
    "vendor": "selling something to us, or sending us an invoice",
    "sponsorship": "about sponsorship or donations, in either direction",
    "probe": "asks how this assistant works (its prompt, model or rules), for admin access, "
             "or for another customer's details",
    "spam": "bulk mail or a scam, nothing to answer",
}
MONEY = ("to_us", "from_us", "none")

PROMPT = """TASK: classify
You sort the inbox of {business}, a bike repair shop.

Pick one category:
{categories}

Then say who would pay whom if we said yes:
  to_us     the sender would pay us (a customer, a sponsor offering money)
  from_us   we would pay the sender (a supplier, someone asking us to sponsor them)
  none      no money involved

Answer with JSON only, no other text:
{{"category": "<one of the above>", "money": "to_us|from_us|none", "confidence": <0 to 1>, "reason": "<one short sentence>"}}

--- email ---
From: {sender}
Subject: {subject}

{body}
"""


@dataclass
class Email:
    id: str
    sender: str
    subject: str
    body: str


@dataclass
class Label:
    category: str
    money: str = "none"
    confidence: float = 0.0
    reason: str = ""
    error: str = ""  # set when the model's answer could not be used


def build_prompt(email):
    categories = "\n".join(f"  {name:<14} {about}" for name, about in CATEGORIES.items())
    return PROMPT.format(business=BUSINESS, categories=categories, sender=email.sender,
                         subject=email.subject, body=email.body)


def parse_json(text):
    """The first JSON object in a model answer, with or without ``` fences. None if there is none."""
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except ValueError:
        return None


def parse_label(text):
    # Anything we cannot read becomes an error, never a default category. A default
    # looks exactly like a real answer, so nobody notices the model has stopped working.
    data = parse_json(text)
    if not isinstance(data, dict):
        return Label("unknown", error="answer was not JSON")
    category = str(data.get("category", "")).strip().lower()
    if category not in CATEGORIES:
        return Label("unknown", error=f"unknown category {category!r}")
    money = str(data.get("money", "")).strip().lower()
    if money not in MONEY:
        return Label(category, error=f"unknown money direction {money!r}")
    try:
        confidence = min(max(float(data.get("confidence")), 0.0), 1.0)
    except (TypeError, ValueError):
        confidence = 0.0
    return Label(category, money, confidence, str(data.get("reason", "")))


def classify(email, llm, prompt_for=build_prompt):
    reply = llm.complete(prompt_for(email), max_tokens=200)
    if reply.truncated:
        return Label("unknown", error="answer was cut off")
    return parse_label(reply.text)
