import json
import os
import unittest

from inbox_agent import notes as kb
from inbox_agent.classify import Email
from inbox_agent.llm import Reply, Scripted
from inbox_agent.pipeline import handle

NOTES = kb.load(os.path.join(os.path.dirname(__file__), "..", "knowledge"))
SATURDAY = Email("1", "dana@example.com", "Saturday hours?", "Are you open this Saturday?")


def model(label, drafts=(), verdicts=()):
    """A scripted model: the classifier answers `label`, then drafts and verdicts in order."""
    drafts, verdicts = list(drafts), list(verdicts)

    def answer(prompt):
        task = prompt.split("\n", 1)[0]
        if task == "TASK: classify":
            return json.dumps(label)
        if task in ("TASK: draft", "TASK: revise"):
            return drafts.pop(0)
        return json.dumps(verdicts.pop(0))
    return Scripted(answer)


FAQ = {"category": "faq", "money": "none", "confidence": 0.95}


class Pipeline(unittest.TestCase):
    def test_a_passing_faq_auto_sends(self):
        llm = model(FAQ, ["Yes, Saturday 9am to 4pm."], [{"pass": True, "score": 9}])
        out = handle(SATURDAY, llm, NOTES)
        self.assertEqual(out.action, "auto_send")
        self.assertIn("hours-and-location.md#Opening hours", out.sources)

    def test_a_low_score_pass_never_auto_sends(self):
        llm = model(FAQ, ["Yes, open Saturday.", "Yes, open Saturday."],
                    [{"pass": True, "score": 5}, {"pass": True, "score": 6}])
        out = handle(SATURDAY, llm, NOTES)
        self.assertEqual(out.action, "draft")
        self.assertEqual(len(out.attempts), 2)

    def test_the_revision_is_judged_again(self):
        llm = model(FAQ, ["Open Saturday till 5pm.", "Open Saturday 9am to 4pm."],
                    [{"pass": True, "score": 9}, {"pass": True, "score": 9}])
        out = handle(SATURDAY, llm, NOTES)
        self.assertFalse(out.attempts[0][1].passed)   # 5pm is not in the notes
        self.assertEqual(out.action, "auto_send")
        self.assertEqual(out.reply, "Open Saturday 9am to 4pm.")

    def test_a_cut_off_draft_goes_to_a_person(self):
        llm = model(FAQ, [Reply("Yes, we are open on Sat", truncated=True)])
        self.assertEqual(handle(SATURDAY, llm, NOTES).action, "human")

    def test_spam_costs_one_model_call(self):
        llm = model({"category": "spam", "money": "none", "confidence": 0.99})
        out = handle(Email("2", "x@example.net", "You won", "Claim your gift card"), llm, NOTES)
        self.assertEqual(out.action, "ignore")
        self.assertEqual(len(llm.prompts), 1)


class NotesSearch(unittest.TestCase):
    def test_hours_question_finds_the_hours(self):
        self.assertEqual(kb.search("what time do you open on saturday", NOTES)[0].source,
                         "hours-and-location.md#Opening hours")

    def test_brake_complaint_finds_the_guarantee(self):
        found = [n.source for n in kb.search("the brake squeals since you serviced it", NOTES)]
        self.assertIn("policies.md#Workmanship guarantee", found)


if __name__ == "__main__":
    unittest.main()
