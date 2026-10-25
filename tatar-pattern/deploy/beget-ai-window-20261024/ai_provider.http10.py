"""Bounded, server-only tp-ai-task/1.0 → tp-gpu-img2img/1.0 transport."""
from dataclasses import dataclass
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import re
import queue
import socket
import threading
import time
from typing import Literal, Protocol
from urllib.parse import urlsplit
from uuid import UUID

from PIL import Image
from . import ai_catalog

CONTRACT = 'tp-gpu-img2img/1.0'
WORKFLOW = 'tp-sdxl-composition-img2img/1.0.0'
MODEL = '378c08ff157660a3399573e1cd5918ad8f3aec344646c5336b027d63fe50ca42'
CATALOG = '2026-10-18.1'
MAX_IMAGE = 20 * 1024 * 1024
MAX_JSON = 256 * 1024
SHA = re.compile(r'^[0-9a-f]{64}$')
ERRORS = {
    'AUTH_REQUIRED': 'AI_PROVIDER_AUTH_FAILED',
    'INVALID_JSON': 'AI_GPU_REQUEST_REJECTED', 'PAYLOAD_TOO_LARGE': 'AI_GPU_REQUEST_REJECTED',
    'INVALID_PARAMETERS': 'AI_GPU_REQUEST_REJECTED', 'AI_BASE_UNKNOWN': 'AI_BASE_UNKNOWN',
    'AI_COMBINATION_UNAVAILABLE': 'AI_COMBINATION_UNAVAILABLE',
    'VERSION_MISMATCH': 'AI_GPU_VERSION_MISMATCH', 'IDEMPOTENCY_CONFLICT': 'AI_GPU_IDEMPOTENCY_CONFLICT',
    'REGISTRY_UNAVAILABLE': 'AI_GPU_UNAVAILABLE', 'GPU_UNAVAILABLE': 'AI_GPU_UNAVAILABLE',
    'SERVICE_DRAINING': 'AI_GPU_DRAINING', 'BUDGET_EXHAUSTED': 'AI_GPU_BUDGET_EXHAUSTED',
    'QUEUE_FULL': 'AI_GPU_QUEUE_FULL', 'JOB_NOT_FOUND': 'AI_GPU_JOB_NOT_FOUND',
    'RESULT_EXPIRED': 'AI_GPU_RESULT_EXPIRED', 'RESULT_NOT_READY': 'AI_GPU_RESULT_NOT_READY',
    'INFERENCE_FAILED': 'AI_CLOUD_FAILED', 'INFERENCE_TIMEOUT': 'AI_TIMEOUT',
    'INFERENCE_INTERRUPTED': 'AI_GPU_INTERRUPTED',
}


class ProviderError(Exception):
    def __init__(self, code, *, definitive=False, job_id=None):
        super().__init__(code)  # Never expose URLs, tokens or remote messages.
        self.code, self.definitive, self.job_id = code, definitive, job_id


@dataclass(frozen=True)
class CloudStatus:
    state: Literal['pending', 'done', 'failed']
    error_code: str | None = None
    metadata: dict | None = None


class Provider(Protocol):
    name: str
    model_version: str
    ready: bool
    contract_version: str
    def submit(self, payload: dict, *, request_id: str, timeout: int) -> str: ...
    def poll(self, job_id: str, *, timeout: int) -> CloudStatus: ...
    def download(self, job_id: str, *, timeout: int, max_bytes: int) -> bytes: ...


def job_uuid(value):
    try:
        if not isinstance(value, str) or str(UUID(value)) != value:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise ProviderError('AI_GPU_RESPONSE_INVALID') from None
    return value


def versions(body, workflow, model):
    return (body.get('contractVersion'), body.get('workflowVersion'), body.get('modelVersion'),
            body.get('catalogVersion')) == (CONTRACT, workflow, model, CATALOG)


def deadline_socket(address, remaining, source_address=None):
    """Bound DNS separately: OS getaddrinfo has no socket timeout.

    A timed-out daemon resolver cannot send HTTP or keep worker shutdown alive.
    Each candidate TCP address shares the original absolute request budget.
    """
    resolved = queue.Queue(maxsize=1)
    def resolve():
        try:
            resolved.put(socket.getaddrinfo(*address, type=socket.SOCK_STREAM))
        except Exception as exc:
            resolved.put(exc)
    threading.Thread(target=resolve, daemon=True).start()
    try:
        addresses = resolved.get(timeout=remaining())
    except queue.Empty:
        raise TimeoutError() from None
    if isinstance(addresses, Exception):
        raise addresses
    for family, kind, proto, _, target in addresses:
        sock = socket.socket(family, kind, proto)
        try:
            sock.settimeout(remaining())
            if source_address:
                sock.bind(source_address)
            sock.connect(target)
            sock.settimeout(remaining())
            return sock
        except OSError:
            sock.close()
    raise ConnectionError('GPU connection unavailable')


class HTTPProvider:
    name = 'tp-gpu-img2img'
    contract_version = ai_catalog.TASK_SCHEMA

    def __init__(self, base_url, token, workflow_version, model_version, proof_file=None):
        if any(ord(c) < 33 for c in base_url):
            raise ValueError('AI_GPU_CONFIGURATION_INVALID')
        url = urlsplit(base_url)
        url.port  # Validate the configured port before any task is accepted.
        if (url.scheme not in ('http', 'https') or not url.hostname or url.username is not None
                or url.password is not None or url.path not in ('', '/') or url.query or url.fragment):
            raise ValueError('AI_GPU_CONFIGURATION_INVALID')
        if (workflow_version != WORKFLOW or model_version != MODEL or len(token) < 32
                or any(ord(c) < 33 or ord(c) > 126 for c in token)):
            raise ValueError('AI_GPU_CONFIGURATION_INVALID')
        self.base_url = base_url.rstrip('/')
        self._url, self._token = url, token
        self.workflow_version, self.model_version = workflow_version, model_version
        self.proof_file = Path(proof_file) if proof_file else None
        self._health = None
        self._health_at = 0
        self._health_lock = threading.Lock()
        self._tasks, self._results = {}, {}

    def _request(self, method, route, *, timeout, limit=MAX_JSON, payload=None, request_id=None):
        """Direct connections ignore proxy env. Redirects are never followed.

        One absolute budget across connect, headers and streamed body, including
        slow trickles. No retries. Caller supplies only fixed routes and UUIDs.
        """
        deadline = time.monotonic() + timeout
        cls = http.client.HTTPSConnection if self._url.scheme == 'https' else http.client.HTTPConnection
        conn = cls(self._url.hostname, self._url.port, timeout=timeout)
        headers = {'Authorization': 'Bearer ' + self._token, 'Accept': 'application/json',
                   'Accept-Encoding': 'identity'}
        raw = None
        if payload is not None:
            raw = json.dumps(payload, separators=(',', ':')).encode()
            headers['Content-Type'] = 'application/json'
        if request_id is not None:
            headers['Idempotency-Key'] = job_uuid(request_id)
        def remaining():
            value = deadline - time.monotonic()
            if value <= 0:
                raise TimeoutError()
            return value
        # HTTPConnection uses this hook for both HTTP and HTTPS (TLS retains hostname validation).
        conn._create_connection = lambda address, timeout, source_address=None: deadline_socket(address, remaining, source_address)
        timer = None
        try:
            conn.connect()
            sock = conn.sock
            def interrupt_io():
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            # Socket timeouts alone do not bound slow trickles inside header parsing.
            timer = threading.Timer(remaining(), interrupt_io)
            timer.daemon = True
            timer.start()
            sock.settimeout(remaining())
            conn.request(method, route, body=raw, headers=headers)
            sock.settimeout(remaining())
            response = conn.getresponse()
            if 300 <= response.status < 400:
                raise ProviderError('AI_GPU_REDIRECT_REJECTED')
            if response.getheader('Content-Encoding', 'identity') != 'identity':
                raise ProviderError('AI_GPU_RESPONSE_INVALID')
            length = response.getheader('Content-Length')
            cap = limit if response.status in (200, 202) else MAX_JSON
            if length is not None and (not length.isdigit() or int(length) > cap):
                raise ProviderError('AI_GPU_RESPONSE_TOO_LARGE')
            chunks, count = [], 0
            while True:
                sock.settimeout(remaining())
                chunk = response.read1(min(65536, cap + 1 - count))
                if not chunk:
                    break
                chunks.append(chunk)
                count += len(chunk)
                if count > cap:
                    raise ProviderError('AI_GPU_RESPONSE_TOO_LARGE')
                # HTTP/1.0 closes its socket when the complete body is consumed.
                # Do not touch the saved socket after HTTPResponse closes its file.
                if response.isclosed():
                    break
            remaining()
            data = b''.join(chunks)
            if length is not None and len(data) != int(length):
                raise ProviderError('AI_GPU_RESPONSE_INVALID')
            return response.status, response.getheader('Content-Type', '').split(';')[0], data
        except ProviderError:
            raise
        except Exception:
            raise ProviderError('AI_GPU_TRANSPORT_ERROR') from None
        finally:
            if timer is not None:
                timer.cancel()
            conn.close()

    def _json(self, method, route, *, timeout, expected=200, **kwargs):
        status, mime, raw = self._request(method, route, timeout=timeout, **kwargs)
        try:
            body = json.loads(raw)
            if mime != 'application/json' or not isinstance(body, dict):
                raise ValueError()
        except (ValueError, UnicodeError):
            raise ProviderError('AI_GPU_RESPONSE_INVALID') from None
        if status != expected:
            error = body.get('error')
            code = error.get('code') if isinstance(error, dict) else None
            raise ProviderError(ERRORS.get(code, 'AI_PROVIDER_ERRORS'),
                                definitive=((status in (400, 401, 409, 413, 422, 429, 503) or (method == 'GET' and status == 404)) and code in ERRORS))
        return body

    def health(self, *, refresh=False):
        # Concurrent callers fail closed while the single bounded probe runs.
        if not self._health_lock.acquire(blocking=False):
            raise ProviderError('AI_GPU_UNAVAILABLE')
        try:
            return self._cached_health(refresh=refresh)
        finally:
            self._health_lock.release()

    def _cached_health(self, *, refresh=False):
        if refresh or time.monotonic() - self._health_at >= 5:
            self._health = None
            try:
                body = self._json('GET', '/v1/health', timeout=5)
            finally:
                # Cache refusal from completion, not from the start of a timeout.
                self._health_at = time.monotonic()
            if (not versions(body, self.workflow_version, self.model_version)
                    or body.get('status') != 'ready' or body.get('qualificationMode') is not False
                    or body.get('draining') is not False or not SHA.fullmatch(str(body.get('deploymentDigest', '')))
                    or type(body.get('queueDepth')) is not int or body['queueDepth'] < 0
                    or not isinstance(body.get('profiles'), list)):
                raise ProviderError('AI_GPU_VERSION_MISMATCH')
            job_uuid(body.get('bootId'))
            self._health = body
        if self._health is None:
            raise ProviderError('AI_GPU_UNAVAILABLE')
        return self._health

    def _proof(self, health):
        if not self.proof_file or os.getenv('TP_ENVIRONMENT') in ('local_project', 'isolated_test'):
            return None
        try:
            if self.proof_file.stat().st_size > MAX_JSON:
                return None
            proof = json.loads(self.proof_file.read_text())
            age = time.time() - proof['checkedAt']
            if (proof['schemaVersion'] != 'tp-gpu-worker-proof/1.0' or proof['baseUrl'] != self.base_url
                    or not versions(proof, self.workflow_version, self.model_version)
                    or proof['deploymentDigest'] != health['deploymentDigest'] or proof['bootId'] != health['bootId']
                    or proof['workerNamespace'] is not True or not 0 <= age <= 86400):
                return None
            if not isinstance(proof.get('profiles'), list) or not isinstance(proof.get('results'), list) or not proof['results']:
                return None
            return proof
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def _proof_possible(self):
        return (self.proof_file is not None and self.proof_file.is_file()
                and os.getenv('TP_ENVIRONMENT') not in ('local_project', 'isolated_test'))

    @property
    def ready(self):
        return self.readiness_snapshot().ready

    def readiness_snapshot(self):
        pairs=()
        try:
            if self._proof_possible():
                health=self.health()
                proof=self._proof(health)
                if proof:
                    pairs=tuple(q for q in health['profiles'] if q in proof['profiles'])
        except (ProviderError, ValueError, KeyError, TypeError, OSError):
            pass
        return ReadinessSnapshot(pairs)

    @staticmethod
    def _pair_matches(profile, remote):
        if not isinstance(remote, dict):
            return False
        expected = {'baseId': profile['baseId'], 'baseSha256': profile['baseSha256'],
                    'ornamentStyle': profile['ornamentStyle'], 'profileVersion': profile['version'],
                    'profileDigest': profile.get('gpuProfileDigest'), 'promptVersion': profile.get('promptVersion'),
                    'qualified': True}
        return bool(expected['profileDigest'] and remote.get('qualified') is True
                    and all(remote.get(k) == v for k, v in expected.items()))

    def ready_for(self, base, profile):
        return self.readiness_snapshot().ready_for(base,profile)

    def wire_payload(self, payload):
        ai_catalog.validate_task(payload)
        base, profile = ai_catalog.select_profile(payload['baseId'], payload['ornamentStyle'], payload['profileVersion'])
        if profile != payload['profile'] or not profile.get('gpuProfileDigest'):
            raise ProviderError('AI_PROFILE_CHANGED', definitive=True)
        return dict(contractVersion=CONTRACT, workflowVersion=self.workflow_version, modelVersion=self.model_version,
                    catalogVersion=CATALOG, baseId=base['id'], baseSha256=payload['inputArtifact']['sha256'],
                    ornamentStyle=payload['ornamentStyle'], profileVersion=payload['profileVersion'], seed=payload['seed'])

    def bind_task(self, job_id, payload):
        self._tasks[job_uuid(job_id)] = payload

    def submit(self, payload, *, request_id, timeout):
        try:
            wire = self.wire_payload(payload)
        except ai_catalog.APIError as exc:
            raise ProviderError(exc.payload['error']['code'], definitive=True) from None
        if not self.ready_for(ai_catalog.find_base(payload['baseId']), payload['profile']):
            raise ProviderError('AI_RELEASE_NOT_READY', definitive=True)
        body = self._json('POST', '/v1/jobs', timeout=min(timeout, 30), expected=202,
                          payload=wire, request_id=request_id)
        job_id = job_uuid(body.get('jobId'))
        self.bind_task(job_id, payload)
        if ((body.get('workflowVersion'), body.get('modelVersion')) != (self.workflow_version, self.model_version)
                or body.get('status') not in ('queued', 'running', 'done', 'failed')):
            raise ProviderError('AI_GPU_VERSION_MISMATCH', job_id=job_id)
        return job_id

    def _metadata(self, meta, job_id):
        if not isinstance(meta, dict) or not versions(meta, self.workflow_version, self.model_version):
            raise ProviderError('AI_GPU_VERSION_MISMATCH', definitive=True)
        try:
            base, profile = ai_catalog.select_profile(meta['baseId'], meta['ornamentStyle'], meta['profileVersion'])
            expected = dict(baseSha256=base['sha256'], recipeSha256=base['recipeSha256'],
                            profileDigest=profile['gpuProfileDigest'], promptVersion=profile['promptVersion'],
                            strength=profile['strength'], steps=profile['steps'], width=1024, height=1024,
                            guidanceScale=5.0, loraScale=1.0, scheduler='EulerAncestralDiscreteScheduler',
                            negativePrompt=None, forceZerosForEmptyPrompt=True, clipSkip=None,
                            control=False, refiner=False, seamless=False)
            task = self._tasks.get(job_id)
            if task:
                expected.update(baseId=task['baseId'], ornamentStyle=task['ornamentStyle'],
                                profileVersion=task['profileVersion'], seed=task['seed'],
                                profileDigest=task['profile']['gpuProfileDigest'])
            if (any(k not in meta or meta[k] != v or isinstance(meta[k], bool) != isinstance(v, bool)
                    for k, v in expected.items()) or type(meta['seed']) is not int or not 0 <= meta['seed'] <= 2147483647
                    or not SHA.fullmatch(meta['deploymentDigest']) or not isinstance(meta['prompt'], str)
                    or len(meta['prompt']) > 8192
                    or hashlib.sha256(meta['prompt'].encode()).hexdigest() != profile['gpuPromptSha256']):
                raise ValueError()
        except (KeyError, ValueError, TypeError, ai_catalog.APIError):
            raise ProviderError('AI_GPU_METADATA_MISMATCH', definitive=True) from None
        keys = set(expected) | {'contractVersion', 'workflowVersion', 'modelVersion', 'catalogVersion',
                               'baseId', 'ornamentStyle', 'profileVersion', 'seed', 'deploymentDigest', 'prompt'}
        return {k: meta[k] for k in keys}

    def forget_job(self, job_id):
        self._tasks.pop(job_id, None)
        self._results.pop(job_id, None)

    def poll(self, job_id, *, timeout):
        job_id = job_uuid(job_id)
        body = self._json('GET', '/v1/jobs/' + job_id, timeout=min(timeout, 15))
        if body.get('jobId') != job_id or body.get('status') not in ('queued', 'running', 'done', 'failed'):
            raise ProviderError('AI_GPU_RESPONSE_INVALID')
        state = body['status']
        meta = self._metadata(body.get('metadata'), job_id)
        if state == 'failed':
            error = body.get('error')
            if not isinstance(error, dict):
                raise ProviderError('AI_GPU_RESPONSE_INVALID')
            return CloudStatus('failed', ERRORS.get(error.get('code'), 'AI_CLOUD_FAILED'), metadata=meta)
        if state in ('queued', 'running'):
            return CloudStatus('pending')
        result = body.get('result')
        if result is None:
            raise ProviderError('AI_GPU_RESULT_EXPIRED', definitive=True)
        if (not isinstance(result, dict) or not SHA.fullmatch(str(result.get('sha256', '')))
                or result.get('mimeType') != 'image/png' or type(result.get('bytes')) is not int
                or not 0 < result['bytes'] <= MAX_IMAGE or type(result.get('width')) is not int
                or type(result.get('height')) is not int or (result['width'], result['height']) != (1024, 1024)):
            raise ProviderError('AI_GPU_RESULT_INVALID', definitive=True)
        self._results[job_id] = result
        return CloudStatus('done', metadata=meta)

    def download(self, job_id, *, timeout, max_bytes):
        job_id = job_uuid(job_id)
        result = self._results.get(job_id)
        if result is None:
            raise ProviderError('AI_GPU_RESULT_NOT_READY')
        status, mime, data = self._request('GET', '/v1/jobs/' + job_id + '/image',
                                         timeout=min(timeout, 30), limit=min(max_bytes, MAX_IMAGE))
        if status != 200:
            try:
                error = json.loads(data)['error']['code']
            except (ValueError, KeyError, TypeError):
                error = None
            raise ProviderError(ERRORS.get(error, 'AI_PROVIDER_ERRORS'), definitive=status == 404)
        if (mime != 'image/png' or len(data) != result['bytes']
                or hashlib.sha256(data).hexdigest() != result['sha256']):
            raise ProviderError('AI_GPU_RESULT_INVALID', definitive=True)
        try:
            with Image.open(io.BytesIO(data)) as image:
                if image.format != 'PNG' or image.mode != 'RGB' or image.size != (1024, 1024) or getattr(image, 'n_frames', 1) != 1:
                    raise ValueError()
                image.verify()
            with Image.open(io.BytesIO(data)) as image:
                image.load()
        except Exception:
            raise ProviderError('AI_GPU_RESULT_INVALID', definitive=True) from None
        return data


class ReadinessSnapshot:
    """Request-local proof/boot/deployment/pair decision; no network methods."""
    contract_version = ai_catalog.TASK_SCHEMA

    def __init__(self,pairs):
        self.pairs=pairs
        self.ready=any(HTTPProvider._pair_matches(p,q) for p in ai_catalog.profiles() for q in pairs)

    def ready_for(self,base,profile):
        return bool(profile and profile['baseSha256']==base['sha256']
                    and any(HTTPProvider._pair_matches(profile,q) for q in self.pairs))


def configured_provider():
    base_url = os.getenv('AI_GPU_BASE_URL')
    if not base_url:
        return None
    token, token_file = os.getenv('AI_GPU_TOKEN'), os.getenv('AI_GPU_TOKEN_FILE')
    if bool(token) == bool(token_file):
        raise ValueError('Exactly one of AI_GPU_TOKEN / AI_GPU_TOKEN_FILE is required')
    if token_file:
        with Path(token_file).open('r') as source:
            token = source.read(4097).strip()
        if len(token) > 4096:
            raise ValueError('AI_GPU_CONFIGURATION_INVALID')
    return HTTPProvider(base_url, token, os.environ.get('GPU_EXPECTED_WORKFLOW_VERSION'),
                        os.environ.get('GPU_EXPECTED_MODEL_VERSION'), os.getenv('AI_GPU_HTTP_PROOF_FILE'))
