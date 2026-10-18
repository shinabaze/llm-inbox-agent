import json
import unittest

from inbox_agent.classify import Email
from inbox_agent.judge import FLOOR, judge, parse_verdict, ungrounded
from inbox_agent.llm import Scripted


class TheFloorIsInCode(unittest.TestCase):
    def test_floor_table(self):
        cases = [
            ({"pass": True, "score": 4}, False),
            ({"pass": True, "score": 6.9}, False),
            ({"pass": True, "score": None}, False),
            ({"pass": True}, False),
            ({"pass": True, "score": "high"}, False),
            ({"pass": True, "score": FLOOR}, True),
            ({"pass": True, "score": 9}, True),
            ({"pass": False, "score": 9}, False),
            ({"pass": "true", "score": 9}, False),   # a string is not a yes
        ]
        for verdict, want in cases:
            with self.subTest(verdict=verdict):
                self.assertEqual(parse_verdict(json.dumps(verdict)).passed, want)

    def test_cut_off_answer_fails(self):
        self.assertFalse(parse_verdict('{"pass": true, "score": 9', truncated=True).passed)

    def test_prose_fails(self):
        self.assertFalse(parse_verdict("Looks great to me!").passed)


class FactsMustComeFromTheNotes(unittest.TestCase):
    NOTES = "Saturday 9am to 4pm. General service $65, most are done in 2 working days."

    def test_facts_in_the_notes_pass(self):
        self.assertEqual(ungrounded("Open 9 am to 4pm, $65, ready in 2 days.", self.NOTES), [])

    def test_invented_price_is_caught(self):
        self.assertEqual(ungrounded("A service is $50.", self.NOTES), ["$50"])

    def test_invented_discount_is_caught(self):
        self.assertEqual(ungrounded("We'll take 20% off.", self.NOTES), ["20%"])

    def test_code_check_overrules_a_happy_judge(self):
        llm = Scripted(lambda prompt: '{"pass": true, "score": 10, "issues": []}')
        email = Email("1", "a@example.com", "price?", "How much is a service?")
        verdict = judge(email, "It's $50 and done in 1 hour.", self.NOTES, llm)
        self.assertFalse(verdict.passed)
        self.assertIn("not in the notes: $50, 1 hour", verdict.issues)


if __name__ == "__main__":
    unittest.main()
