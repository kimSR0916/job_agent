from contextlib import closing
import json
from pathlib import Path
import tempfile
import unittest
import agent
import requirements


class RequirementsTests(unittest.TestCase):
    def test_required_preferred_and_negative_visa_condition_remain_distinct(self):
        job = {'sections':[
            {'heading':'Qualifications','text':'<ul><li>Python and SQL are required.</li><li>No prior experience is required.</li><li>Visa sponsorship is not available.</li></ul>'},
            {'heading':'Preferred qualifications','text':"<p>A master's degree is preferred.</p>"},
        ]}
        summary = requirements.summarize(job)
        self.assertEqual(summary['required'], ['Python and SQL are required.'])
        self.assertEqual(summary['experience'], ['No prior experience is required.'])
        self.assertEqual(summary['authorization'], ['Visa sponsorship is not available.'])
        self.assertEqual(summary['education'], [])
        self.assertEqual(summary['preferred'], ["A master's degree is preferred."])

    def test_missing_requirements_are_not_invented(self):
        summary = requirements.summarize({'description':'We build software for racing teams.'})
        self.assertTrue(all(not items for items in summary.values()))
        self.assertIn('원문 확인',requirements.render(summary))
        self.assertNotIn('비자 지원 불가',requirements.render(summary))

    def test_lever_value_heading_is_not_treated_as_mandatory(self):
        summary = requirements.summarize({'sections':[
            {'heading':'What We Require','text':'Python programming ability.'},
            {'heading':'What We Value','text':'Experience with distributed systems.'},
        ]})
        self.assertEqual(summary['required'],['Python programming ability.'])
        self.assertEqual(summary['preferred'],['Experience with distributed systems.'])

    def test_restored_operations_job_is_not_sent_under_new_filter(self):
        config = json.loads((Path(__file__).parent / 'config.json').read_text())
        with tempfile.TemporaryDirectory() as folder, closing(agent.connect(Path(folder) / 'jobs.db')) as db:
            agent.enqueue(db,'personal',{'id':'old','title':'Operations Intern','description':'Python SQL racing'})
            agent.enqueue(db,'personal',{'id':'new','title':'Junior Backend Engineer','description':'Python required.'})
            sent = []
            agent.deliver(db,'personal',sent.append,config)
            self.assertEqual([job['id'] for job in sent],['new'])
            self.assertIn('requirements_summary',sent[0])


if __name__ == '__main__':
    unittest.main()
