"""Exercise worker-field insertion while the POST acknowledgement is copied."""
from pathlib import Path
import io
import json
import sys
import threading
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
import server


class AdmissionSnapshot(unittest.TestCase):
    def test_new_job_response_cannot_race_worker_field_insertion(self):
        entered,changed=threading.Event(),threading.Event(); threads=[]
        original_snapshot=server.snapshot
        class DelayedItems:
            def __init__(self,job): self.job=job
            def items(self):
                # Preserve the actual dictionary iterator. Pause after its
                # first item to force the genuine snapshot/mutation boundary.
                for index,pair in enumerate(self.job.items()):
                    if index==0:
                        entered.set(); changed.wait(.15)
                    yield pair
        def submit(_execute,job):
            def worker():
                entered.wait(2)
                with server.LOCK: job['actualExitCode']=17
                changed.set()
            thread=threading.Thread(target=worker); thread.start(); threads.append(thread)
        handler=server.Handler.__new__(server.Handler); handler.path='/api/remesh'
        body=json.dumps(dict(meshId='toilet',target=1800,guideMode=2,curves=[])).encode()
        handler.headers={'Content-Type':'application/json','Content-Length':str(len(body))}; handler.rfile=io.BytesIO(body)
        handler.respond=lambda data,status=200:(data,status)
        try:
            with patch.dict(server.JOBS,{},clear=True),patch.object(server.QUEUE,'submit',side_effect=submit),patch.object(server,'snapshot',side_effect=lambda job:original_snapshot(DelayedItems(job))):
                response,status=handler.do_POST()
            self.assertEqual(status,202)
            self.assertEqual(response['meshId'],'toilet')
            self.assertEqual(response['state'],'queued')
        finally:
            for thread in threads: thread.join(timeout=3)
        self.assertTrue(changed.is_set())
        self.assertTrue(all(not thread.is_alive() for thread in threads))


if __name__=='__main__': unittest.main()
