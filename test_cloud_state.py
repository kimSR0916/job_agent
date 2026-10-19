from contextlib import closing
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import agent
import cloud_state


class CloudStateTests(unittest.TestCase):
    def test_restore_preserves_sent_and_pending_jobs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            original = root / 'jobs.sqlite3'
            with closing(agent.connect(original)) as db:
                agent.enqueue(db, 'personal', {'id': 'sent'})
                agent.deliver(db, 'personal', lambda job: None)
                agent.enqueue(db, 'personal', {'id': 'pending'})
            archive = root / 'state.zip'
            with zipfile.ZipFile(archive, 'w') as bundle:
                bundle.write(original, 'jobs.sqlite3')
            destination = root / 'restored/jobs.sqlite3'
            cloud_state.restore(archive, destination)
            with closing(agent.connect(destination)) as db:
                sent = []
                agent.deliver(db, 'personal', sent.append)
                self.assertEqual([job['id'] for job in sent], ['pending'])

    def test_invalid_archive_does_not_replace_existing_state(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            destination = root / 'jobs.sqlite3'
            destination.write_bytes(b'existing-state')
            archive = root / 'state.zip'
            with zipfile.ZipFile(archive, 'w') as bundle:
                bundle.writestr('../jobs.sqlite3', b'unsafe')
            with self.assertRaises(ValueError):
                cloud_state.restore(archive, destination)
            self.assertEqual(destination.read_bytes(), b'existing-state')

    def test_delivery_failure_is_reported_and_keeps_unsent_state(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(agent, 'ROOT', Path(folder)):
            job = {'id': 'one', 'title': 'AI Intern', 'description': ''}
            config = {'user_id': 'personal', 'sources': [{'provider':'lever','company':'example'}]}
            with patch.object(agent, 'collect', return_value=iter([job])), patch.object(
                    agent, 'matches', return_value=True), patch.object(
                    agent, 'notify', side_effect=RuntimeError('HTTP 429')):
                with self.assertRaises(RuntimeError):
                    agent.run(config, False)
            with closing(agent.connect(Path(folder) / 'data/jobs.sqlite3')) as db:
                self.assertEqual(db.execute('SELECT discord_sent FROM jobs').fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()
