# Decisions

Short reasons for the choices that look odd at first.

**The rules are in code, not in the prompt.** A prompt rule is a request. The model follows it
most of the time, and you find out about the other times from a customer. Every rule in
`policy.py` and `judge.py` runs after the model answers and can overrule it.

**An answer we can't read goes to a person.** The tempting fix for a bad JSON answer is a default
category. A default looks exactly like a real answer, so when the model breaks (a changed API,
a bad key, a new model that wraps JSON in prose) nothing looks wrong. You just get a lot of one
category. Sending it to a person makes the failure visible on the first email.

**The classifier says who would pay whom.** Words mislead. A supplier's "quote" uses the same
word as a customer asking for a price, and "sponsorship" can mean we pay or we get paid. One extra
field, `to_us` / `from_us` / `none`, settles both, and the rules check that the category and the
money agree.

**Only `faq` can send on its own.** Everything else can cost money, a customer or trust if it is
wrong. A one-line change in `AUTO_SEND` widens this, and that should feel like a decision, not
a default.

**The judge can only make things safer.** A failed judge turns an auto-send into a draft. Nothing
the judge says can turn a draft into an auto-send.

**The grounding check is code.** Prices, times, durations and percentages are the facts a customer
acts on. A regex finds them in the draft and checks each one is in the notes the drafter was
given. It's crude, and it catches the worst mistake (an invented price) every time, which the
judge model does not.

**One revision, then a person.** A second and third rewrite rarely fix what the first didn't,
and they cost a call each. The person sees every draft and every verdict in `Outcome.attempts`.

**Word overlap, not embeddings.** For a few pages of notes, word overlap finds the right section,
and you can always see why it picked one. Embeddings are better past that, and the swap is one
function (`notes.search`).

**A run with errors fails.** When some calls fail, the score covers only the cases that got
through, so it is not the bank's score. The first real run here was rate-limited after 17 of 43
cases, printed 100%, and exited 0. Now that run exits 1 and says it is incomplete.

**Standard library only.** You can read every line, and nothing needs installing to run the
tests or the demo. The model client is 30 lines of `urllib` and works with any
OpenAI-compatible API.
