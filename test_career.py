from pathlib import Path
import unittest
import career


class CareerTests(unittest.TestCase):
    def setUp(self):
        self.goal = career.load_goal(Path(__file__).parent / "career-goal.example.json")

    def test_final_goal_not_first_role(self):
        report = career.roadmap(self.goal)
        self.assertIn("모터스포츠·야구·스포츠 업계에서 일하기", report)
        self.assertIn("이력서 미입력", report)
        self.assertIn("모터스포츠 → 야구 → 기타 스포츠", report)
        self.assertIn("경로의 한계", report)
        self.assertNotIn("합격 확률", report)

    def test_resume_mentions_are_not_skills_claims(self):
        results = career.resume_evidence("Python은 아직 배우는 중입니다.", self.goal["competencies"])
        self.assertEqual(results[0]["status"], "언급 있음 · 수준 확인 필요")
        self.assertEqual(results[0]["evidence"], ["Python은 아직 배우는 중입니다."])
        self.assertEqual(next(item for item in results if item["name"] == "SQL과 데이터 모델")["status"], "이력서에서 미확인")

    def test_goal_connection_priorities(self):
        direct = {"company": "Sports Lab", "title": "Junior Data Analyst", "description": "Python SQL"}
        bridge = {"company": "Example", "title": "Junior Backend Engineer", "description": "Python API"}
        self.assertGreater(career.connection(direct, self.goal)["priority"], career.connection(bridge, self.goal)["priority"])
        self.assertEqual(career.keywords("software-f123", ["f1"]), [])
        jobs = [{"company": company, "title": "Junior Data Analyst", "description": "Python"}
                for company in ("Sports Lab", "Baseball Lab", "F1 Racing Lab")]
        for job in jobs:
            job["career_connection"] = career.connection(job, self.goal)
        jobs.sort(key=career.job_sort_key, reverse=True)
        self.assertEqual([job["career_connection"]["preferred_domain"] for job in jobs],
                         ["모터스포츠", "야구", "기타 스포츠"])
        mixed = {"company": "Sports Baseball Racing", "title": "Junior Data Analyst", "description": ""}
        self.assertEqual(career.connection(mixed, self.goal)["preferred_domain"], "모터스포츠")

    def test_industry_does_not_bypass_analysis_development_filter(self):
        developer = {"company": "Baseball Lab", "title": "Junior Backend Engineer", "description": "Python"}
        analyst = {"company": "Baseball Lab", "title": "Junior Data Analyst", "description": "SQL"}
        operations = {"company": "F1 Racing", "title": "Operations Intern", "description": "Team operations"}
        self.assertEqual(career.connection(developer, self.goal)["priority"], career.connection(analyst, self.goal)["priority"])
        self.assertEqual(career.connection(developer, self.goal)["category"], "희망 업계 분석·개발 후보")
        import agent
        config = {"role_keywords": ["backend"], "level_keywords": ["intern", "junior"], "exclude_keywords": ["senior"]}
        self.assertFalse(agent.matches(operations, config, self.goal))
        operations["title"] = "Operations Associate"
        operations["work_type"] = "Associate/Co-op/Intern"
        self.assertFalse(agent.matches(operations, config, self.goal))
        operations["company"] = "Example"
        operations["description"] = "Baseball benefits"
        operations["source_domain"] = "모터스포츠"
        self.assertEqual(career.connection(operations, self.goal)["preferred_domain"], "모터스포츠")
        operations["title"] = "Senior Operations Manager"
        self.assertFalse(agent.matches(operations, config, self.goal))


if __name__ == "__main__":
    unittest.main()
