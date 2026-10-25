import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from compiler_studio.profiles import Profile,calculator_profile
from compiler_studio.worker import AnalysisWorker


class WorkerIntegrityTests(unittest.TestCase):
    def test_invalid_deadlines_never_start_a_process(self):
        worker=AnalysisWorker()
        for value in [0,-1,float('nan'),float('inf'),True,'12']:
            with self.subTest(timeout=value),patch('compiler_studio.worker.mp.get_context') as context:
                with self.assertRaisesRegex(ValueError,'positive, finite'):
                    worker.submit('1+2',calculator_profile(),timeout=value)
                context.assert_not_called()
                self.assertIsNone(worker.active)

    def test_invalid_source_and_unserializable_profile_do_not_occupy_worker(self):
        worker=AnalysisWorker()
        with self.assertRaisesRegex(ValueError,'text'):worker.submit(None,calculator_profile())
        with self.assertRaisesRegex(ValueError,'serializable'):worker.submit('1',None)
        class Invalid:
            def to_dict(self):return {'bad':lambda:None}
        with self.assertRaisesRegex(ValueError,'serializable'):worker.submit('1',Invalid())
        self.assertIsNone(worker.process)
        self.assertIsNone(worker.active)

    def test_failed_process_start_is_cleaned_up_without_masking_error(self):
        worker=AnalysisWorker()
        with patch('compiler_studio.worker.mp.get_context') as context:
            process=context.return_value.Process.return_value
            process.pid=None;process.is_alive.return_value=False
            process.start.side_effect=OSError('Cannot start worker')
            with self.assertRaisesRegex(OSError,'Cannot start worker'):
                worker.submit('1',calculator_profile())
            process.join.assert_not_called()
        self.assertIsNone(worker.process)
        self.assertIsNone(worker.requests)
        self.assertIsNone(worker.active)

    def test_duplicate_json_fields_are_rejected_not_silently_overridden(self):
        data=calculator_profile().to_json()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'profile.json'
            path.write_text(data.replace('"version": 1','"version": 1, "version": 1'),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Duplicate JSON'):
                Profile.load(path)
            path.write_text(data,encoding='utf-8-sig')
            self.assertEqual(Profile.load(path).to_dict(),calculator_profile().to_dict())


if __name__=='__main__':unittest.main()
