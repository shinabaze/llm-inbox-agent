"""Step 2: the rules that decide what happens to an email. They live in code, not in the prompt.

A rule in a prompt is a request. The model can ignore it and you find out from a customer.
Every rule here can overrule the model, and each one has a test.
"""
import re
from dataclasses import dataclass

AUTO_SEND = {"faq"}   # the only kind of email that may go out without a person reading it
MIN_CONFIDENCE = 0.6

# A text backstop for probes. Models often file these as spam, and an ignored probe is one
# nobody hears about. Kept narrow on purpose: "which model of tyre" is a normal question.
PROBE_TEXT = re.compile(
    r"system prompt|your (instructions|prompt|rules)|ignore (all |any |your |the )?previous"
    r"|(what|which) (ai|llm|chatbot)\b|developer mode|jailbreak"
    r"|admin (access|login|password|panel)",
    re.I)


@dataclass
class Decision:
    action: str   # auto_send | draft | human | ignore
    why: str


def decide(label, email):
    text = f"{email.subject}\n{email.body}"
    if label.category == "probe" or PROBE_TEXT.search(text):
        return Decision("human", "probe: a person sees it, the agent sends nothing")
    if label.error:
        return Decision("human", f"model answer unusable ({label.error})")
    if label.confidence < MIN_CONFIDENCE:
        return Decision("human", f"low confidence ({label.confidence:.2f})")
    if label.category == "spam":
        return Decision("ignore", "spam")

    # Read intent from the direction of money, not the words: a supplier sending us a
    # "quote" is not a customer asking for one.
    if label.money == "from_us" and label.category in ("faq", "booking", "quote", "repair_status"):
        return Decision("human", f"labelled {label.category}, but we would be paying: the label is wrong")
    if label.category == "sponsorship" and label.money == "to_us":
        return Decision("human", "someone is offering us money: the owner answers")
    if label.category in ("refund", "vendor"):
        return Decision("human", f"{label.category}: money would leave the shop, the owner decides")

    if label.category in AUTO_SEND:
        return Decision("auto_send", "a plain question the notes answer")
    return Decision("draft", "a person reads it before it goes")
