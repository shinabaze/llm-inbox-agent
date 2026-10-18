"""Step 3: write a reply from the notes, and rewrite it once if the judge finds problems."""
from .classify import BUSINESS

WRITE = """TASK: draft
Write the reply {business} sends to this email.
Use only facts from the notes. If the notes do not answer it, say someone from the shop
will reply today. Do not promise refunds, discounts or dates the notes do not give.
Under 120 words. Sign off: {business}

--- notes ---
{notes}

--- email ---
From: {sender}
Subject: {subject}

{body}

Answer with the reply text only.
"""

REVISE = """TASK: revise
Your reply had these problems:
{issues}

Rewrite it to fix them. Same rules: only facts from the notes, under 120 words,
sign off: {business}

--- notes ---
{notes}

--- email ---
Subject: {subject}

{body}

--- your reply ---
{draft}

Answer with the new reply text only.
"""


def _text(reply):
    # A reply cut off at max_tokens reads fine until the last sentence. Treat it as missing.
    return None if reply.truncated or not reply.text.strip() else reply.text.strip()


def write(email, notes, llm):
    prompt = WRITE.format(business=BUSINESS, notes=notes, sender=email.sender,
                          subject=email.subject, body=email.body)
    return _text(llm.complete(prompt, max_tokens=400))


def revise(email, draft, issues, notes, llm):
    prompt = REVISE.format(business=BUSINESS, issues="\n".join(f"- {i}" for i in issues),
                           notes=notes, subject=email.subject, body=email.body, draft=draft)
    return _text(llm.complete(prompt, max_tokens=400))
