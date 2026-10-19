from contextlib import closing
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import agent
from translation import KoreanTranslator, TranslationBudgetReached, validate


class TranslationTests(unittest.TestCase):
    def test_changed_numbers_and_missing_negative_are_rejected(self):
        self.assertEqual(validate('Graduate in 2028.', '2028년 졸업 예정'), '2028년 졸업 예정')
        with self.assertRaises(RuntimeError):
            validate('Graduate in 2028.', '2027년 졸업 예정')
        with self.assertRaises(RuntimeError):
            validate('Visa sponsorship is not available.', '비자 지원 가능합니다.')
        self.assertEqual(validate('Visa sponsorship is not available.', '비자 지원은 불가합니다.'), '비자 지원은 불가합니다.')

    def test_sentence_cache_survives_new_process_without_model_load(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'state.db'
            with closing(agent.connect(path)) as db:
                translator=KoreanTranslator(db)
                with patch.object(translator,'_translate',return_value=['파이썬을 사용합니다.']) as run:
                    self.assertEqual(translator({'required':['Use Python.','Use Python.']})['required'],
                                     ['파이썬을 사용합니다.','파이썬을 사용합니다.'])
                    run.assert_called_once_with(['Use Python.'])
            with closing(agent.connect(path)) as db:
                translator=KoreanTranslator(db)
                with patch.object(translator,'_translate',side_effect=AssertionError('model should not run')):
                    self.assertEqual(translator({'required':['Use Python.']})['required'],['파이썬을 사용합니다.'])

    def test_budget_defers_unsent_jobs_and_korean_input_needs_no_model(self):
        with tempfile.TemporaryDirectory() as folder, closing(agent.connect(Path(folder)/'state.db')) as db:
            translator=KoreanTranslator(db,{'max_jobs_per_run':0})
            self.assertEqual(translator({'required':['파이썬 필수']})['required'],['파이썬 필수'])
            with self.assertRaises(TranslationBudgetReached):
                translator({'required':['Use Python.']})
            job={'id':'job','title':'Backend Intern','description':'Python required.'}
            agent.enqueue(db,'personal',job)
            sent=[]
            agent.deliver(db,'personal',sent.append,translator=translator)
            self.assertEqual(sent,[])
            self.assertEqual(db.execute('SELECT discord_sent FROM jobs').fetchone()[0],0)


if __name__ == '__main__':
    unittest.main()
