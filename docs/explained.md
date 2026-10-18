# How it works, explained from scratch

If you have never built an LLM agent, start here. Every step below has a file you can open.

## 1. Sorting an email

A language model reads text and writes text. To use it for sorting, we ask it to answer in a
fixed shape (JSON) with a fixed list of choices:

```json
{"category": "booking", "money": "to_us", "confidence": 0.9, "reason": "wants a service slot"}
```

Code can read that. Code can't read "This looks like a booking to me!", so `parse_label` in
`classify.py` turns anything that isn't valid JSON with a known category into an error, and an
error goes to a person.

## 2. Rules the model can't talk its way past

`policy.py` takes the model's label and decides what happens: send it, draft it, give it to a
person, or ignore it. Take this email:

> Hi Kettle Lane, attached is our quote for 200 inner tubes at trade price.

A model may label it `quote`, because the word is right there. But it also says `money: from_us`:
if we said yes, we would be paying. A customer asking for a quote would pay *us*. The two don't
agree, so the rule sends it to a person:

```
labelled quote, but we would be paying: the label is wrong
```

## 3. Finding the right notes

The shop's facts live in `knowledge/*.md`, one section per `## ` heading. To answer
"Are you open this Saturday?", `notes.search` splits the question into words, drops the common
ones ("are", "you", "this"), and scores each section by the words it shares. Rare words count
more. "saturday" appears in one section out of 13, so it is worth log(1 + 13/1) = 2.6. "open"
appears in two, so it is worth log(1 + 13/2) = 2.0. The "Opening hours" section shares both, so it
wins.

## 4. Drafting and judging

The drafter gets the email and only the sections that matched, and is told to use only those
facts. Then a second call, the judge, scores the draft out of 10 and lists problems.

Models are inconsistent about their own rules. A judge told "7 or more is a pass" will sometimes
answer `"pass": true, "score": 6`. So `parse_verdict` decides from the score, not the boolean:
below 7, or no score at all, is a fail.

One more check needs no model. `judge.ungrounded` finds every price, time, duration and
percentage in the draft and checks each one is in the notes. A draft that offers "20% off" fails,
because no note mentions 20%.

If the draft fails, it is rewritten once with the judge's problems listed, and judged again.

## 5. Measuring it honestly

`evals/run_eval.py` runs the 51 labelled emails in `evals/cases.json` through the classifier
and the rules, and counts how many land on the right category and the right action.

A score means little on its own. Of the 51 cases, 22 should end as a draft. A program that
answers "draft" every time, with no model at all, would be right 22 / 51 = 43% of the time. So
the eval prints that beside the real score. If the agent gets 86%, it is 43 points better than
guessing, and that is the number that tells you the model is earning its cost.

The harness also refuses to run if the prompt doesn't contain the email it is meant to be
testing, and it fails any run where some calls errored. Both mistakes produce a confident number
that measures nothing.
