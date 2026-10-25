"""Signal clock and hard process bound only; no DB, HTTP, GPU or cloud."""
import signal
import subprocess
import textwrap
from types import SimpleNamespace

from scripts import ai_worker


def test_first_signal_owns_deadlines_and_repeated_signals_do_not_extend(monkeypatch):
    now=[100.]
    handlers={};alarms=[]
    monkeypatch.setattr(ai_worker,'time',SimpleNamespace(monotonic=lambda:now[0]))
    monkeypatch.setattr(ai_worker.signal,'signal',lambda sig,handler:handlers.__setitem__(sig,handler))
    monkeypatch.setattr(ai_worker.signal,'setitimer',lambda kind,seconds:alarms.append((kind,seconds)))
    stop=ai_worker.Shutdown()
    ai_worker.install_shutdown_handlers(stop)
    handlers[signal.SIGTERM](signal.SIGTERM,None)
    now[0]=145.  # Current HTTP/file operation finishes 45 seconds after the signal.
    handlers[signal.SIGINT](signal.SIGINT,None)
    assert stop.requested_at==100 and stop.deadline==1030
    assert alarms==[(signal.ITIMER_REAL,950)]
    assert callable(handlers[signal.SIGALRM])


def child(code):
    result=subprocess.run([__import__('sys').executable,'-c',textwrap.dedent(code)],
                          capture_output=True,text=True,timeout=8)
    return result


def test_real_signal_hard_stops_inflight_call_without_success_ack():
    result=child('''
        import signal,time
        from scripts import ai_worker as w
        w.HARD_STOP_SECONDS=.2  # Short test-only watchdog; production stays 950.
        stop=w.Shutdown();w.install_shutdown_handlers(stop)
        def inflight_http():
            signal.raise_signal(signal.SIGTERM)
            print('SIGNAL_RECEIVED',flush=True)
            time.sleep(20)  # No socket: simulate a blocked operation.
        inflight_http()
        print('AI_WORKER_DRAINED',flush=True)
    ''')
    assert 'SIGNAL_RECEIVED' in result.stdout
    assert result.returncode==75
    assert 'AI_WORKER_DRAINED' not in result.stdout


def test_real_signal_normal_exit_ack_after_commit():
    result=child('''
        import signal
        from scripts import ai_worker as w
        w.HARD_STOP_SECONDS=2
        stop=w.Shutdown();w.install_shutdown_handlers(stop)
        class Connection:
            def execute(self,*args):return self
            def fetchone(self):return {'n':0}
            def commit(self):print('COMMIT',flush=True)
        w.step=lambda *a,**kw:False
        signal.raise_signal(signal.SIGTERM)
        w.run(Connection(),None,None,stop)
    ''')
    assert result.returncode==0,result.stderr
    assert result.stdout.index('COMMIT')<result.stdout.index('AI_WORKER_DRAINED')


def test_signal_during_poll_updates_download_budget(monkeypatch):
    from datetime import datetime,timedelta,timezone
    from app.ai_provider import CloudStatus,ProviderError
    now=[0.];stop=ai_worker.Shutdown();timeouts=[]
    job=dict(generation_id='test',state='polling',provider='test',model_version='test',
             provider_job_id='known',deadline=datetime.now(timezone.utc)+timedelta(seconds=2000),
             next_poll_at=datetime.now(timezone.utc)-timedelta(seconds=1),poll_errors=0,payload={},deleted_at=None,guest_expires_at=None,guest_process_id=None,provider_request_id='00000000-0000-4000-8000-000000000001')
    class Connection:
        def execute(self,*a):return self
        def fetchone(self):return job
        def commit(self):pass
        def rollback(self):pass
    class Provider:
        name=model_version='test'
        def poll(self,*a,**kw):
            stop.set();now[0]=929.
            return CloudStatus('done')
        def download(self,*a,**kw):
            timeouts.append(kw['timeout'])
            raise ProviderError('AI_GPU_TRANSPORT_ERROR')
    monkeypatch.setattr(ai_worker,'time',SimpleNamespace(monotonic=lambda:now[0]))
    ai_worker.step(Connection(),Provider(),None,stop_deadline=lambda:stop.deadline)
    assert timeouts==[1.]
