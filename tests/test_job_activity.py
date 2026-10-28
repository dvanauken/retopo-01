from pathlib import Path
import io, json, sys, tempfile, unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from job_progress import emit, read_events
from job_diagnostics import summarize
import server


class JobActivity(unittest.TestCase):
    def test_partial_record_is_retried_without_duplicate_or_missing_events(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'runs') as tmp:
            folder=Path(tmp);emit(folder,'Building layout');first=read_events(folder)
            with (folder/'events.jsonl').open('ab') as stream:stream.write(b'{"message":"Checking boundary","time":1')
            partial=read_events(folder,first['eventCursor'])
            self.assertEqual(partial['events'],[]);self.assertFalse(partial['moreEvents']);self.assertEqual(partial['eventCursor'],first['eventCursor'])
            with (folder/'events.jsonl').open('ab') as stream:stream.write(b'}\n')
            completed=read_events(folder,partial['eventCursor']);self.assertEqual([e['message'] for e in completed['events']],['Checking boundary'])
            self.assertEqual(read_events(folder,completed['eventCursor'])['events'],[])

    def test_event_batches_can_be_drained_to_completion(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'runs') as tmp:
            folder=Path(tmp)
            for i in range(5):emit(folder,f'Pass {i}')
            cursor=0;messages=[]
            while True:
                batch=read_events(folder,cursor,limit=2);messages.extend(e['message'] for e in batch['events']);cursor=batch['eventCursor']
                if not batch['moreEvents']:break
            self.assertEqual(messages,[f'Pass {i}' for i in range(5)])

    def test_best_failure_reports_the_specific_gate_and_preserves_its_measurements(self):
        rows=[dict(attempt=0,iteration=0,passed=False,quality=dict(passed=False,failures=['minimumAngleDegrees below limit'])),
              dict(attempt=0,iteration=1,passed=False,quality=dict(passed=True),feature=dict(passed=False,failures=['edgeMax'],values=dict(edgeMax=.0048),limits=dict(edgeMax=.0027)),surface=dict(passed=True),contacts=dict(passed=True),guidesPassed=True)]
        result=summarize(rows)
        self.assertIn('failed source crease preservation',result['message']);self.assertIn('Passed: quad shape/count',result['message'])
        self.assertEqual(result['bestCandidate']['measurements'],[dict(check='edgeMax',value=.0048,limit=.0027)])

    def test_failed_saved_job_survives_restart_with_recovered_candidate_events(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'runs') as tmp:
            root=Path(tmp);id='a'*32;folder=root/'runs'/id;(folder/'open-surface').mkdir(parents=True)
            (folder/'execution.json').write_text(json.dumps(dict(id=id,state='failed',stage='Could not generate',startedAt=10,finishedAt=20,error='old generic error')))
            (folder/'settings.json').write_text(json.dumps(dict(sourceSha256='source')))
            (folder/'open-surface/history.json').write_text(json.dumps([dict(attempt=0,iteration=0,quality=dict(passed=False,failures=['minimumAngleDegrees below limit']))]))
            with patch.object(server,'ROOT',root):
                job=server.persisted_job(id);status=server.job_status(job)
                self.assertIn('quad shape/count',status['error']);self.assertEqual(status['elapsedSeconds'],10)
                self.assertEqual(status['events'][0]['time'],None)
                self.assertEqual(server.job_status(job,status['eventCursor'])['events'],[])
                self.assertIsNone(server.persisted_job('../outside'))

    def test_nonterminal_disk_state_is_not_resurrected(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'runs') as tmp:
            root=Path(tmp);id='b'*32;folder=root/'runs'/id;folder.mkdir(parents=True)
            (folder/'execution.json').write_text(json.dumps(dict(id=id,state='running')))
            with patch.object(server,'ROOT',root):self.assertIsNone(server.persisted_job(id))


if __name__=='__main__':unittest.main()
