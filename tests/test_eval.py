import json
import unittest

from evals.run_eval import PromptMissingEmail, exit_code, load_cases, regressions, run, score
from inbox_agent.classify import CATEGORIES, Email, build_prompt
from inbox_agent.llm import Scripted

ACTIONS = {"auto_send", "draft", "human", "ignore"}


def always(category, money="none"):
    return Scripted(lambda prompt: json.dumps({"category": category, "money": money, "confidence": 0.9}))


class TheHarnessCannotLie(unittest.TestCase):
    def test_refuses_when_the_prompt_lost_the_body(self):
        # The bug this guards: the builder reads the wrong field and every prompt has an
        # empty body. The model still answers, so the harness would still print a score.
        def broken(email):
            return build_prompt(Email(email.id, email.sender, email.subject, ""))
        with self.assertRaises(PromptMissingEmail):
            run(load_cases(), always("faq"), prompt_for=broken)

    def test_always_guessing_scores_the_baseline(self):
        cases = load_cases()
        s = score(run(cases, always("booking")))
        share = sum(c["category"] == "booking" for c in cases) / len(cases)
        self.assertAlmostEqual(s["category"], share)
        self.assertIn(s["baseline_category"][0], CATEGORIES)

    def test_ignored_probes_are_counted(self):
        cases = [c for c in load_cases() if c.get("probe")]
        s = score(run(cases, always("spam")))
        self.assertEqual(s["probes"], len(cases))
        # The text backstop catches the obvious ones; only the polite one gets through.
        self.assertEqual(s["probes_ignored"], 1)

    def test_network_errors_are_not_wrong_answers(self):
        def flaky(prompt):
            raise TimeoutError("read timed out")
        s = score(run(load_cases()[:3], Scripted(flaky)) + run(load_cases()[3:4], always("faq")))
        self.assertEqual(len(s["errors"]), 3)
        self.assertEqual(s["category"], 1.0)

    def test_a_run_with_errors_fails_however_good_it_looks(self):
        # The first real run hit a rate limit after 17 cases and still printed 100%.
        s = score(run(load_cases()[:3], Scripted(lambda p: 1 / 0)) + run(load_cases()[3:4], always("faq")))
        self.assertEqual(s["category"], 1.0)
        self.assertEqual(exit_code(s), 1)

    def test_a_clean_run_passes(self):
        self.assertEqual(exit_code(score(run(load_cases()[:4], always("faq")))), 0)


class Regressions(unittest.TestCase):
    def test_lost_cases_are_listed(self):
        self.assertEqual(regressions({"right": ["A"], "errors": []}, {"right": ["A", "B"]}), ["B"])

    def test_a_case_that_errored_is_not_a_regression(self):
        self.assertEqual(regressions({"right": ["A"], "errors": ["B"]}, {"right": ["A", "B"]}), [])


class TheCaseBank(unittest.TestCase):
    def test_every_case_is_well_formed(self):
        cases = load_cases()
        self.assertGreaterEqual(len(cases), 40)
        self.assertEqual(len({c["id"] for c in cases}), len(cases))
        for c in cases:
            with self.subTest(case=c["id"]):
                self.assertIn(c["category"], CATEGORIES)
                self.assertIn(c["action"], ACTIONS)
                if c.get("probe"):
                    self.assertEqual(c["action"], "human")


if __name__ == "__main__":
    unittest.main()
