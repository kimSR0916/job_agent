import tempfile
import unittest
from pathlib import Path
import agent
from unittest.mock import patch


class AgentTests(unittest.TestCase):
    def test_smartrecruiters_pagination_and_details(self):
        responses = [
            {"totalFound": 2, "content": [{"id": "1", "name": "Graduate Engineer", "location": {"city": "Grove"}}]},
            {"applyUrl": "https://example.test/1", "jobAd": {"sections": {"qualifications": {"text": "<p>Python</p>"}}}},
            {"totalFound": 2, "content": [{"id": "2", "name": "Operations Intern", "location": {"city": "Grove"}}]},
            {"applyUrl": "https://example.test/2", "jobAd": {"sections": {"jobDescription": {"text": "Operations"}}}},
        ]
        with patch.object(agent, "request_json", side_effect=responses) as request:
            jobs = list(agent.collect({"provider": "smartrecruiters", "company": "Example", "domain": "모터스포츠"}))
        self.assertEqual(len(jobs), 2)
        self.assertIn("offset=1", request.call_args_list[2].args[0])
        self.assertEqual(jobs[0]["description"], " Python ")
        self.assertEqual(jobs[0]["source_domain"], "모터스포츠")

    def test_filter(self):
        config = {"role_keywords": ["backend", "forward deployed"],
                  "level_keywords": ["intern", "new grad"],
                  "exclude_keywords": ["senior"]}
        job = {"title": "Forward Deployed Engineer, New Grad", "description": ""}
        self.assertTrue(agent.matches(job, config))
        job["description"] = "Requires 3+ years of professional experience"
        self.assertFalse(agent.matches(job, config))
        job["description"] = "Master's degree preferred"
        self.assertTrue(agent.matches(job, config))
        job["title"] = "Senior Backend Intern Mentor"
        self.assertFalse(agent.matches(job, config))

    def test_delivery_retry_and_user_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            with agent.connect(Path(directory) / "jobs.db") as db:
                job = {"id": "1", "title": "AI Intern"}
                agent.enqueue(db, "alice", job)
                agent.enqueue(db, "alice", job)
                agent.enqueue(db, "bob", job)
                def fail(_):
                    raise RuntimeError("network")
                with self.assertRaises(RuntimeError):
                    agent.deliver(db, "alice", fail)
                sent = []
                agent.deliver(db, "alice", sent.append)
                agent.enqueue(db, "alice", job)
                agent.deliver(db, "alice", sent.append)
                self.assertEqual(len(sent), 1)
                agent.deliver(db, "bob", sent.append)
                self.assertEqual(len(sent), 2)


if __name__ == "__main__":
    unittest.main()
