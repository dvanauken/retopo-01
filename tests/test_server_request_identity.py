"""Deterministic admission/cancellation controls for browser request identities.

The real HTTP handler and lock run; only scheduling is controlled so enqueue
counts and hostile interleavings can be asserted without inventing solver output.
"""
from concurrent.futures import ThreadPoolExecutor
import io,json,sys,threading,unittest,uuid
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import server

def post(path,body):
    handler=server.Handler.__new__(server.Handler);handler.path=path
    payload=json.dumps(body).encode();handler.headers={'Content-Type':'application/json','Content-Length':str(len(payload))}
    handler.rfile=io.BytesIO(payload);handler.respond=lambda data,status=200:(data,status)
    return handler.do_POST()

class RequestIdentity(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(server.JOBS,{},clear=True))
        self.enterContext(patch.dict(server.REQUESTS,{},clear=True))
        self.schedule=self.enterContext(patch.object(server.QUEUE,'submit'))
        self.request_id=uuid.uuid4().hex
        self.body=dict(requestId=self.request_id,meshId='toilet',target=1800,curves=[],guideMode=2)
    def cancel(self):return post('/api/requests/'+self.request_id+'/cancel',{})
    def test_cancellation_before_delivery_prevents_admission(self):
        first,status=self.cancel();self.assertEqual(status,200);self.assertIsNone(first['id'])
        for _ in range(3):
            reply,status=post('/api/remesh',self.body)
            self.assertEqual(status,202);self.assertEqual(reply['state'],'cancelled');self.assertIsNone(reply['id'])
        self.assertEqual(len(server.JOBS),0);self.schedule.assert_not_called()
    def test_eight_concurrent_replays_enqueue_exactly_once(self):
        barrier=threading.Barrier(8)
        def submit(_):barrier.wait(timeout=5);return post('/api/remesh',self.body)
        with ThreadPoolExecutor(max_workers=8) as pool:responses=list(pool.map(submit,range(8)))
        self.assertTrue(all(status==202 for _,status in responses))
        self.assertEqual(len({data['id'] for data,_ in responses}),1)
        self.assertEqual(len(server.JOBS),1);self.schedule.assert_called_once()
    def test_reused_id_with_different_parameters_conflicts(self):
        first,status=post('/api/remesh',self.body);self.assertEqual(status,202)
        _,status=post('/api/remesh',dict(self.body,target=600));self.assertEqual(status,409)
        self.assertEqual(server.JOBS[first['id']]['target'],1800);self.schedule.assert_called_once()
    def test_replay_does_not_consume_admission_capacity(self):
        first,_=post('/api/remesh',self.body)
        server.JOBS.update({uuid.uuid4().hex:dict(state='queued') for _ in range(2)})
        replay,status=post('/api/remesh',self.body)
        self.assertEqual(status,202);self.assertEqual(replay['id'],first['id']);self.schedule.assert_called_once()
        _,status=post('/api/remesh',dict(self.body,requestId=uuid.uuid4().hex));self.assertEqual(status,400)
    def test_cancel_after_admission_before_scheduling_never_spawns(self):
        def schedule(execute,job):
            self.cancel();execute(job)
        self.schedule.side_effect=schedule
        with patch.object(server.subprocess,'Popen') as spawn:reply,status=post('/api/remesh',self.body)
        self.assertEqual(status,202);self.assertEqual(reply['state'],'cancelled');spawn.assert_not_called()
    def test_invalid_id_values_cannot_allocate_jobs(self):
        for value in (None,True,17,[],{},'',uuid.uuid4().hex.upper(),'f'*31,'g'*32,'f'*33):
            with self.subTest(value=value):
                _,status=post('/api/remesh',dict(self.body,requestId=value));self.assertEqual(status,400)
        self.assertFalse(server.JOBS);self.assertFalse(server.REQUESTS);self.schedule.assert_not_called()
    def test_terminal_replay_returns_original_job_without_restarting(self):
        first,_=post('/api/remesh',self.body)
        for state in ('complete','failed','cancelled'):
            server.JOBS[first['id']]['state']=state
            reply,status=post('/api/remesh',self.body)
            self.assertEqual(status,202);self.assertEqual(reply['id'],first['id']);self.assertEqual(reply['state'],state)
        self.schedule.assert_called_once()
    def test_cancelled_request_retains_parameter_binding(self):
        self.cancel();post('/api/remesh',self.body)
        _,status=post('/api/remesh',dict(self.body,target=600));self.assertEqual(status,409)
        reply,status=self.cancel();self.assertEqual(status,200);self.assertEqual(reply['state'],'cancelled')
        self.assertFalse(server.JOBS);self.schedule.assert_not_called()

if __name__=='__main__':unittest.main()
