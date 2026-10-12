import tempfile
import unittest
from pathlib import Path
import agent


class AgentTests(unittest.TestCase):
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
