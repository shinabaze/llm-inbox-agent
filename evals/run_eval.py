"""Measure the classifier and the rules on a bank of labelled emails.

    python -m evals.run_eval                              # needs LLM_API_KEY (see .env.example)
    python -m evals.run_eval --save results/base.json     # keep this run to compare against
    python -m evals.run_eval --against results/base.json  # exit 1 if any case got worse

Each accuracy is printed beside the score of always guessing the most common answer,
because a number on its own says nothing about whether the model helps.
"""
import argparse
import collections
import json
import os
import sys

from inbox_agent.classify import Email, build_prompt, classify
from inbox_agent.llm import from_env
from inbox_agent.policy import decide

CASES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cases.json")


class PromptMissingEmail(Exception):
    pass


def checked(prompt_for):
    """Wrap a prompt builder so it stops the run when the email body is not in the prompt.

    A harness that sends the model an empty body still prints numbers. They measure nothing.
    """
    def build(email):
        prompt = prompt_for(email)
        tail = " ".join(email.body.split()[-6:])
        if tail and tail not in " ".join(prompt.split()):
            raise PromptMissingEmail(f"case {email.id}: the prompt does not contain the email body")
        return prompt
    return build


def load_cases(path=CASES):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def run(cases, llm, prompt_for=build_prompt):
    build = checked(prompt_for)
    results = []
    for case in cases:
        email = Email(case["id"], case["sender"], case["subject"], case["body"])
        row = {"id": case["id"], "subject": case["subject"], "probe": case.get("probe", False),
               "want_category": case["category"], "want_action": case["action"]}
        try:
            label = classify(email, llm, prompt_for=build)
        except PromptMissingEmail:
            raise
        except Exception as exc:   # a network error is not a wrong answer, so count it apart
            row["error"] = f"{type(exc).__name__}: {exc}"[:120]
        else:
            row.update(category=label.category, action=decide(label, email).action)
        results.append(row)
    return results


def majority(values):
    value, count = collections.Counter(values).most_common(1)[0]
    return value, count / len(values)


def correct(row):
    return row["category"] == row["want_category"] and row["action"] == row["want_action"]


def score(results):
    scored = [r for r in results if "error" not in r]
    if not scored:
        raise SystemExit("every case errored; check the API settings")
    n = len(scored)
    return {
        "cases": len(results),
        "errors": sorted(r["id"] for r in results if "error" in r),
        "category": sum(r["category"] == r["want_category"] for r in scored) / n,
        "action": sum(r["action"] == r["want_action"] for r in scored) / n,
        "baseline_category": majority([r["want_category"] for r in scored]),
        "baseline_action": majority([r["want_action"] for r in scored]),
        "probes": sum(r["probe"] for r in scored),
        "probes_ignored": sum(r["probe"] and r["action"] == "ignore" for r in scored),
        "right": sorted(r["id"] for r in scored if correct(r)),
    }


def regressions(now, base):
    """Cases right in the baseline and wrong now. A case that errored this run is not counted."""
    return sorted(set(base["right"]) - set(now["right"]) - set(now["errors"]))


def report(results, s):
    print(f"{s['cases']} cases, {len(s['errors'])} errors\n")
    for name in ("category", "action"):
        guess, share = s[f"baseline_{name}"]
        lift = (s[name] - share) * 100
        print(f"  {name:<9} {s[name]:6.1%}    always '{guess}' would score {share:.1%}   ({lift:+.1f} points)")
    print(f"  probes    {s['probes']}, ignored {s['probes_ignored']}\n")
    misses = [r for r in results if "error" not in r and not correct(r)]
    for r in misses:
        print(f"  {r['id']:<4} got {r['category']}/{r['action']}, want {r['want_category']}/{r['want_action']}"
              f"   \"{r['subject']}\"")
    for r in results:
        if "error" in r:
            print(f"  {r['id']:<4} error: {r['error']}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--save", help="write this run to a JSON file")
    parser.add_argument("--against", help="compare with a saved run and fail on regressions")
    args = parser.parse_args(argv)

    llm = from_env()
    if llm is None:
        sys.exit("Set LLM_API_KEY first (and LLM_BASE_URL / LLM_MODEL). See .env.example.")
    results = run(load_cases(), llm)
    s = score(results)
    report(results, s)

    if args.save:
        os.makedirs(os.path.dirname(os.path.abspath(args.save)), exist_ok=True)
        with open(args.save, "w", encoding="utf-8") as fh:
            json.dump(s, fh, indent=1)
    if args.against:
        with open(args.against, encoding="utf-8") as fh:
            lost = regressions(s, json.load(fh))
        print(f"\n  vs baseline: {len(lost)} case(s) got worse {' '.join(lost)}")
        if lost:
            return 1
    return 1 if s["probes_ignored"] else 0


if __name__ == "__main__":
    sys.exit(main())
