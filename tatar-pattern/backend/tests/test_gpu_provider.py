"""New adapter checks only. Mock transport; no sockets, GPU or readiness qualification."""
import copy
import hashlib
import io
import json
import time
from uuid import uuid4

from PIL import Image
import pytest

from app import ai_catalog
from app.ai_provider import (HTTPProvider, ProviderError, configured_provider, CONTRACT,
                             WORKFLOW, MODEL, CATALOG, MAX_JSON)


@pytest.fixture
def task():
    base, profile = ai_catalog.select_profile('f10-wreath', 'graphic', '2026-10-18.local-v1')
    return ai_catalog.task_payload(base, profile, 20261008)


@pytest.fixture
def provider():
    return HTTPProvider('http://gpu-tunnel:18765', 'x' * 32, WORKFLOW, MODEL)


def remote_pair(task):
    p = task['profile']
    return dict(baseId=p['baseId'], baseSha256=p['baseSha256'], ornamentStyle=p['ornamentStyle'],
                profileVersion=p['version'], profileDigest=p['gpuProfileDigest'],
                promptVersion=p['promptVersion'], qualified=True)


def health(task):
    return dict(contractVersion=CONTRACT, workflowVersion=WORKFLOW, modelVersion=MODEL,
                catalogVersion=CATALOG, status='ready', qualificationMode=False, draining=False,
                deploymentDigest='a' * 64, bootId=str(uuid4()), queueDepth=0, profiles=[remote_pair(task)])


def metadata(task):
    # Independent fixture from GPU contract (read-only); not imported runtime GPU code.
    from pathlib import Path
    gpu = json.loads((Path(__file__).resolve().parents[3] / 'ИИ/service/profiles.json').read_text())['profiles'][0]
    assert hashlib.sha256(json.dumps(gpu, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest() == task['profile']['gpuProfileDigest']
    base = ai_catalog.find_base(task['baseId'])
    return dict(contractVersion=CONTRACT, workflowVersion=WORKFLOW, modelVersion=MODEL, catalogVersion=CATALOG,
                baseId=task['baseId'], baseSha256=base['sha256'], recipeSha256=base['recipeSha256'],
                ornamentStyle=task['ornamentStyle'], profileVersion=task['profileVersion'],
                profileDigest=task['profile']['gpuProfileDigest'], promptVersion=task['profile']['promptVersion'],
                prompt=gpu['prompt'], seed=task['seed'], strength=.55, steps=30, width=1024, height=1024,
                guidanceScale=5., loraScale=1., scheduler='EulerAncestralDiscreteScheduler',
                negativePrompt=None, forceZerosForEmptyPrompt=True, clipSkip=None, control=False,
                refiner=False, seamless=False, deploymentDigest='a' * 64)


def png(mode='RGB', size=(1024, 1024)):
    buf = io.BytesIO()
    Image.new(mode, size).save(buf, 'PNG')
    return buf.getvalue()


def mock_transport(monkeypatch, replies):
    calls = []
    class Socket:
        def settimeout(self, value):
            assert 0 < value <= 30
    class Response:
        def __init__(self, status, mime, data, headers=None):
            self.status, self.mime, self.data = status, mime, io.BytesIO(data)
            self.headers = headers or {}
        def getheader(self, key, default=None):
            return {'Content-Type': self.mime, **self.headers}.get(key, default)
        def read1(self, size):
            return self.data.read(size)
    class Connection:
        def __init__(self, host, port, timeout):
            assert host == 'gpu-tunnel' and port == 18765
            self.sock = Socket()
        def connect(self): pass
        def request(self, method, route, body, headers):
            calls.append((method, route, json.loads(body) if body else None, headers))
        def getresponse(self):
            reply = replies.pop(0)
            if isinstance(reply, Exception): raise reply
            return Response(*reply)
        def close(self): pass
    monkeypatch.setattr('app.ai_provider.http.client.HTTPConnection', Connection)
    return calls


def json_reply(value, status=200):
    return (status, 'application/json', json.dumps(value).encode())


def test_wire_exact_nine_and_reject_mutated_snapshot(provider, task):
    wire = provider.wire_payload(task)
    assert wire == dict(contractVersion=CONTRACT, workflowVersion=WORKFLOW, modelVersion=MODEL,
                        catalogVersion=CATALOG, baseId=task['baseId'], baseSha256=task['inputArtifact']['sha256'],
                        ornamentStyle='graphic', profileVersion=task['profileVersion'], seed=20261008)
    assert len(wire) == 9
    for key, value in [('strength', .99), ('steps', 31), ('gpuProfileDigest', 'a' * 64)]:
        changed = copy.deepcopy(task); changed['profile'][key] = value
        with pytest.raises(ProviderError, match='AI_PROFILE_CHANGED'):
            provider.wire_payload(changed)


def test_submit_poll_download_preserves_png_and_ignores_proxy(provider, task, monkeypatch):
    monkeypatch.setenv('HTTP_PROXY', 'http://untrusted-proxy:9999')
    monkeypatch.setenv('HTTPS_PROXY', 'http://untrusted-proxy:9999')
    monkeypatch.setattr(provider, 'ready_for', lambda *_: True)  # Never sets ready.
    jid, rid = str(uuid4()), str(uuid4())
    data = png()
    result = dict(sha256=hashlib.sha256(data).hexdigest(), mimeType='image/png', bytes=len(data), width=1024, height=1024)
    calls = mock_transport(monkeypatch, [json_reply(dict(jobId=jid, status='queued', workflowVersion=WORKFLOW, modelVersion=MODEL), 202),
        json_reply(dict(jobId=jid, status='running', metadata=metadata(task))), json_reply(dict(jobId=jid, status='done', result=result, metadata=metadata(task))),
        (200, 'image/png', data)])
    assert provider.submit(task, request_id=rid, timeout=30) == jid
    assert calls[0][3]['Idempotency-Key'] == rid and calls[0][3]['Authorization'] == 'Bearer ' + 'x' * 32
    assert provider.poll(jid, timeout=15).state == 'pending'
    status = provider.poll(jid, timeout=15)
    assert status.state == 'done' and status.metadata['profileDigest'] == task['profile']['gpuProfileDigest']
    assert provider.download(jid, timeout=30, max_bytes=20 * 1024 * 1024) == data
    assert [c[1] for c in calls] == ['/v1/jobs', '/v1/jobs/'+jid, '/v1/jobs/'+jid, '/v1/jobs/'+jid+'/image']
    assert provider.ready is False


@pytest.mark.parametrize('value', ['../other', 'https://evil/image', '', None, 'not-uuid'])
def test_job_id_cannot_control_route(provider, value):
    with pytest.raises(ProviderError): provider.poll(value, timeout=15)


@pytest.mark.parametrize('reply,code', [
    ((302, 'text/plain', b'', {'Location':'http://evil/'}), 'AI_GPU_REDIRECT_REJECTED'),
    ((200, 'application/json', b'', {'Content-Length':str(MAX_JSON+1)}), 'AI_GPU_RESPONSE_TOO_LARGE'),
    ((200, 'application/json', b'x'*(MAX_JSON+1)), 'AI_GPU_RESPONSE_TOO_LARGE'),
    ((200, 'application/json', b'{}', {'Content-Encoding':'gzip'}), 'AI_GPU_RESPONSE_INVALID'),
    ((200, 'text/html', b'{}'), 'AI_GPU_RESPONSE_INVALID'),
    ((200, 'application/json', b'{}', {'Content-Length':'3'}), 'AI_GPU_RESPONSE_INVALID'),
])
def test_reject_redirect_large_json_encoding_and_truncated(provider, monkeypatch, reply, code):
    mock_transport(monkeypatch, [reply])
    with pytest.raises(ProviderError, match=code): provider.health(refresh=True)


def test_definite_reject_vs_uncertain_submit(provider, task, monkeypatch):
    monkeypatch.setattr(provider, 'ready_for', lambda *_: True)
    mock_transport(monkeypatch, [json_reply({'error':{'code':'QUEUE_FULL'}}, 429), TimeoutError(), (202, 'application/json', b'bad')])
    for code, definitive in [('AI_GPU_QUEUE_FULL', True), ('AI_GPU_TRANSPORT_ERROR', False), ('AI_GPU_RESPONSE_INVALID', False)]:
        with pytest.raises(ProviderError) as exc: provider.submit(task, request_id=str(uuid4()), timeout=30)
        assert exc.value.code == code and exc.value.definitive is definitive


def test_ack_with_known_id_preserves_recovery(provider, task, monkeypatch):
    monkeypatch.setattr(provider, 'ready_for', lambda *_: True)
    jid = str(uuid4())
    mock_transport(monkeypatch, [json_reply(dict(jobId=jid, status='queued', workflowVersion='old', modelVersion=MODEL), 202)])
    with pytest.raises(ProviderError) as exc: provider.submit(task, request_id=str(uuid4()), timeout=30)
    assert exc.value.job_id == jid and not exc.value.definitive


@pytest.mark.parametrize('change', [{'modelVersion':'old'}, {'seed':3}, {'steps':100}, {'baseSha256':'b'*64},
                                    {'profileDigest':'b'*64}, {'width':True}, {'prompt':'other prompt'}])
def test_reject_wrong_metadata(provider, task, monkeypatch, change):
    jid = str(uuid4()); provider.bind_task(jid, task)
    meta = metadata(task); meta.update(change)
    mock_transport(monkeypatch, [json_reply(dict(jobId=jid, status='done', metadata=meta, result=dict(sha256='a'*64,mimeType='image/png',bytes=100,width=1024,height=1024)))])
    with pytest.raises(ProviderError) as exc: provider.poll(jid, timeout=15)
    assert exc.value.definitive


@pytest.mark.parametrize('data,sha,size', [(b'not-png', None, None), (png('RGBA'), None, None), (png(size=(64,64)), None, None),
                                         (png(), 'b'*64, None), (png(), None, 1)])
def test_download_png_sha_size(provider, monkeypatch, data, sha, size):
    jid = str(uuid4())
    provider._results[jid] = dict(sha256=sha or hashlib.sha256(data).hexdigest(), bytes=size or len(data))
    mock_transport(monkeypatch, [(200, 'image/png', data)])
    with pytest.raises(ProviderError, match='AI_GPU_RESULT_INVALID'): provider.download(jid, timeout=30, max_bytes=20*1024*1024)


def test_stream_result_cap(provider, monkeypatch):
    jid = str(uuid4()); provider._results[jid] = dict(sha256='a'*64, bytes=3)
    mock_transport(monkeypatch, [(200, 'image/png', b'abcd')])
    with pytest.raises(ProviderError, match='AI_GPU_RESPONSE_TOO_LARGE'): provider.download(jid, timeout=30, max_bytes=3)


def test_missing_result_never_resubmits(provider, task, monkeypatch):
    jid = str(uuid4()); provider.bind_task(jid, task)
    calls = mock_transport(monkeypatch, [json_reply(dict(jobId=jid, status='done', metadata=metadata(task), result=None))])
    with pytest.raises(ProviderError, match='AI_GPU_RESULT_EXPIRED') as exc: provider.poll(jid, timeout=15)
    assert exc.value.definitive and [c[0] for c in calls] == ['GET']


def test_readiness_requires_proof_exact_identity_and_pair(provider, task, monkeypatch, tmp_path):
    body = health(task)
    monkeypatch.setattr(provider, '_json', lambda *a, **kw: body)
    monkeypatch.delenv('TP_ENVIRONMENT', raising=False)
    assert not provider.ready
    proof = dict(body, schemaVersion='tp-gpu-worker-proof/1.0', checkedAt=time.time(), workerNamespace=True,
                 baseUrl=provider.base_url, results=[{'jobId':str(uuid4()), 'sha256':'b'*64}])
    provider.proof_file = tmp_path/'proof.json'
    provider.proof_file.write_text(json.dumps(proof))
    # Synthetic in-memory fixture exercises matching; never writes a runtime proof.
    assert provider.ready_for(ai_catalog.find_base(task['baseId']), task['profile'])
    monkeypatch.setenv('TP_ENVIRONMENT', 'isolated_test')
    assert provider.ready is False
    monkeypatch.delenv('TP_ENVIRONMENT')
    for change in [{'bootId':str(uuid4())}, {'deploymentDigest':'b'*64}, {'checkedAt':0}, {'profiles':[]},
                   {'results':[]}, {'modelVersion':'old'}]:
        provider.proof_file.write_text(json.dumps({**proof, **change}))
        assert provider.ready is False
    provider.proof_file.write_text(json.dumps(proof))
    for key, value in [('qualified', False), ('profileDigest','b'*64), ('promptVersion','old')]:
        changed = copy.deepcopy(body);changed['profiles'][0][key] = value
        monkeypatch.setattr(provider, '_json', lambda *a, **kw: changed)
        provider._health_at = 0
        assert not provider.ready_for(ai_catalog.find_base(task['baseId']), task['profile'])
    other = ai_catalog.profiles()[1]
    assert not provider.ready_for(ai_catalog.find_base(other['baseId']), other)


def test_configuration_requires_one_secret_source(monkeypatch, tmp_path):
    monkeypatch.setenv('AI_GPU_BASE_URL', 'http://gpu-tunnel:18765')
    monkeypatch.setenv('GPU_EXPECTED_WORKFLOW_VERSION', WORKFLOW)
    monkeypatch.setenv('GPU_EXPECTED_MODEL_VERSION', MODEL)
    monkeypatch.delenv('AI_GPU_TOKEN', raising=False);monkeypatch.delenv('AI_GPU_TOKEN_FILE', raising=False)
    with pytest.raises(ValueError): configured_provider()
    secret = tmp_path/'secret';secret.write_text('x'*32+'\n')
    monkeypatch.setenv('AI_GPU_TOKEN_FILE', str(secret))
    assert configured_provider().ready is False  # No proof; must not access network below.
    monkeypatch.setenv('AI_GPU_TOKEN', 'y'*32)
    with pytest.raises(ValueError): configured_provider()
    for url in ['http://user:pass@host', 'http://host/prefix', 'ftp://host', 'http://host?token=x']:
        with pytest.raises(ValueError): HTTPProvider(url, 'x'*32, WORKFLOW, MODEL)


def test_absolute_network_budget_stops_trickle(provider, monkeypatch):
    # A stream making progress cannot reset the absolute request deadline.
    mock_transport(monkeypatch, [(200, 'application/json', b'{}')])
    ticks = iter([0, 0, 0, 0, 6])
    monkeypatch.setattr('app.ai_provider.time.monotonic', lambda: next(ticks))
    with pytest.raises(ProviderError, match='AI_GPU_TRANSPORT_ERROR'):
        provider._json('GET', '/v1/health', timeout=5)


def test_all_28_pinned_gpu_profiles_agree_with_canonical_registry():
    from pathlib import Path
    gpu = json.loads((Path(__file__).resolve().parents[3]/'ИИ/service/profiles.json').read_text())['profiles']
    profiles = ai_catalog.profiles()
    assert len(gpu) == len(profiles) == 28
    for profile in profiles:
        remote = next(g for g in gpu if (g['baseId'], g['ornamentStyle']) == (profile['baseId'], profile['ornamentStyle']))
        assert all(remote[k] == profile[k] for k in ['baseSha256', 'version', 'strength', 'steps'])
        assert profile['gpuProfileDigest'] == hashlib.sha256(json.dumps(remote, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
        assert profile['gpuPromptSha256'] == hashlib.sha256(remote['prompt'].encode()).hexdigest()
        assert not profile['releaseApproved']


def test_dns_resolution_has_absolute_budget(monkeypatch):
    import queue
    from app.ai_provider import deadline_socket
    class Resolution:
        def get(self, timeout):
            assert timeout == 2
            raise queue.Empty()
    class ResolverThread:
        def __init__(self, **kwargs): assert kwargs['daemon'] is True
        def start(self): pass
    monkeypatch.setattr('app.ai_provider.queue.Queue', lambda **kw: Resolution())
    monkeypatch.setattr('app.ai_provider.threading.Thread', ResolverThread)
    with pytest.raises(TimeoutError): deadline_socket(('gpu-tunnel', 18765), lambda: 2)


def test_io_watchdog_covers_header_parsing(provider, monkeypatch):
    triggered = []
    class Sock:
        def settimeout(self, timeout): pass
        def shutdown(self, how): triggered.append(how)
    class Timer:
        def __init__(self, timeout, callback): self.callback = callback
        def start(self): self.callback()
        def cancel(self): pass
    class Connection:
        sock = Sock()
        def __init__(self, *a, **kw): pass
        def connect(self): pass
        def request(self, *a, **kw): pass
        def getresponse(self):
            assert triggered
            raise OSError()
        def close(self): pass
    monkeypatch.setattr('app.ai_provider.threading.Timer', Timer)
    monkeypatch.setattr('app.ai_provider.http.client.HTTPConnection', Connection)
    with pytest.raises(ProviderError, match='AI_GPU_TRANSPORT_ERROR'):
        provider._json('GET', '/v1/health', timeout=5)


def test_owner_probe_validates_existing_results_only(provider, task, monkeypatch, tmp_path):
    from scripts.ai_gpu_probe import main
    monkeypatch.delenv('TP_ENVIRONMENT', raising=False)
    jid = str(uuid4()); body = health(task); data = png()
    result = dict(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data), mimeType='image/png', width=1024, height=1024)
    calls = mock_transport(monkeypatch, [json_reply(body),
        json_reply(dict(jobId=jid, status='done', metadata=metadata(task), result=result)),
        (200, 'image/png', data), json_reply(body)])
    provider.proof_file = tmp_path/'proof.json'
    monkeypatch.setattr('scripts.ai_gpu_probe.configured_provider', lambda: provider)
    monkeypatch.setattr('sys.argv', ['probe', '--owner-run', '--worker-namespace', '--job-id', jid])
    main()
    proof = json.loads(provider.proof_file.read_text())
    assert proof['profiles'] == body['profiles'] and proof['bootId'] == body['bootId']
    assert proof['results'][0]['sha256'] == result['sha256']
    assert all(c[0] == 'GET' for c in calls)
    monkeypatch.setenv('TP_ENVIRONMENT', 'isolated_test')
    assert provider.ready is False


def test_probe_refuses_local_environment(monkeypatch):
    from scripts.ai_gpu_probe import main
    monkeypatch.setenv('TP_ENVIRONMENT', 'isolated_test')
    monkeypatch.setattr('sys.argv', ['probe', '--owner-run', '--worker-namespace', '--job-id', str(uuid4())])
    with pytest.raises(SystemExit, match='local tests cannot qualify'):
        main()
