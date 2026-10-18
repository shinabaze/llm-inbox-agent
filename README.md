# llm-inbox-agent

An email agent for a small business. It sorts the inbox, drafts replies from the business's own
notes, and has a second model check every draft before anything goes out. The rules that keep it
safe live in code, not in the prompt, and every rule has a test.

I run an agent like this in production. This repo is the engineering from it, rebuilt around a
made-up bike shop, Kettle Lane Cycles, so all of it can be public and you can run it yourself.

**Run it** (Python 3.10+, nothing to install, no key):

```bash
python examples/demo.py              # four emails through the whole pipeline
python -m unittest discover tests    # the tests, no key needed
```

**Measure it against a real model:** copy `.env.example` to `.env`, add a key for any
OpenAI-compatible API (OpenAI, Gemini, Groq, a local Ollama), then:

```bash
python -m evals.run_eval
```

## How it works

```
email -> classify -> rules --+--> ignore     spam
                             +--> person     probes, refunds, money offered, answers it can't read
                             +--> notes -> draft -> judge -> revise once -> judge
                                                                |
                                     sends on its own only if it's an faq AND the judge passes;
                                     otherwise it waits as a draft for a person
```

1. **Classify** (`classify.py`). The model picks one of ten categories and says who would pay
   whom if we said yes: `to_us`, `from_us` or `none`.
2. **Rules** (`policy.py`). Code decides what happens, and it can overrule the model:
   - Anyone probing the agent (asking for its prompt, its model, admin access or another
     customer's details) goes to a person. A text check backs this up, because models often file
     these as spam.
   - An answer the code can't read goes to a person. It never falls back to a default category.
   - Intent comes from the direction of money. A supplier sending us a "quote" is not a customer
     asking for one.
   - Only `faq` emails can ever send without a person.
3. **Draft** (`draft.py`) from the sections of `knowledge/*.md` that match the email (`notes.py`).
4. **Judge** (`judge.py`). A second call scores the draft out of 10. The prompt says 7 passes, and
   the code enforces it: `"pass": true` with a 6, or with no score, is a fail. A code check also
   fails any price, time, duration or percentage that isn't in the notes.
5. **Revise** once with the judge's problems, then judge again. The judge can only make things
   safer: a failed auto-send becomes a draft, never the other way round.

New to this? [docs/explained.md](docs/explained.md) walks through every step by hand.
[docs/decisions.md](docs/decisions.md) gives the reason behind each choice.

## A worked example

From `python examples/demo.py`. The scripted model makes the mistakes real models make:

```
[2] quick one
    model said : spam (money none)
    action     : HUMAN  (probe: a person sees it, the agent sends nothing)

[3] Quote for 200 inner tubes
    model said : quote (money from_us)
    action     : HUMAN  (labelled quote, but we would be paying: the label is wrong)

[4] Brakes still squeal
    action     : DRAFT  (a person reads it before it goes)
    draft 1    : score 6.0, fail: offers a discount; score 6.0 is under the floor of 7; not in the notes: 20%
    draft 2    : score 8.0, pass
```

And a real run of the eval, on Gemini flash-lite (`gemini-flash-lite-latest`), over the 51 cases
I wrote for the shop:

```
51 cases, 0 errors

  category  100.0%    always 'probe' would score 15.7%   (+84.3 points)
  action    100.0%    always 'draft' would score 43.1%   (+56.9 points)
  probes    8, ignored 0

  vs baseline: 0 case(s) got worse
```

Every case right means my cases are still easier than a real inbox. That's fine for what the bank
is for: it's a regression test. Change the prompt, a rule or the model, run it again with
`--against` the last run, and it lists every case that got worse.

## What I learned

- **A rule in a prompt is a request.** My production judge was told 7 out of 10 was a pass, and
  it still passed drafts it had scored lower. The fix was a few lines of code that read the score
  instead of trusting the yes.
- **Ignoring an attacker isn't the same as being safe from one.** My first classifier filed people
  asking for its system prompt as irrelevant and dropped them. The guardrails on what it says never
  ran, and nobody knew it was being probed. Now a probe always reaches a person.
- **An eval can give you a confident number that measures nothing.** If the prompt builder reads
  the wrong field, the model gets an empty email and still answers. If the API rate-limits you,
  the cases that got through can all be right. The first real run of this harness did exactly
  that: 17 of 43 cases, 100%, exit 0. Now it refuses a prompt without the email in it, fails any
  run with errors, and prints the "always guess the most common answer" score beside every
  number.

## Limits

- 51 cases is small. One case moves a score by 2 points, so don't read much into a change that
  size.
- The notes search is plain word overlap. It's easy to follow, and it misses synonyms: "got a
  flat" doesn't find the section called "Punctures". Past a few pages of notes, use embeddings
  (the swap is one function).
- The demo's model is scripted. It shows the rules working, not how good a model is. The eval is
  for that.
- It drafts once, revises once, then hands over to a person. That's on purpose.

## Files

```
inbox_agent/   classify.py  policy.py  notes.py  draft.py  judge.py  pipeline.py  llm.py
knowledge/     the shop's notes, one section per "## " heading
evals/         cases.json (51 labelled emails) and run_eval.py
examples/      demo.py
tests/         standard library unittest, no key needed
docs/          explained.md, decisions.md
```

MIT licence. Copyright 2026 Shinabaze Ajiya.
