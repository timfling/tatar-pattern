"""Real HTTP parser/socket EOF regression; socketpair avoids listening TCP ports."""
import ast
import hashlib
import http.client
import json
from pathlib import Path
import queue
import socket
import threading
import time
import types
import unittest
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parent


def client_namespace(path):
    nodes=[]
    for node in ast.parse(path.read_text()).body:
        if isinstance(node,ast.ClassDef) and node.name=='ProviderError':nodes.append(node)
        if isinstance(node,ast.ClassDef) and node.name=='HTTPProvider':
            node.body=[x for x in node.body if isinstance(x,ast.FunctionDef) and x.name in ('__init__','_request')]
            nodes.append(node)
    ns=dict(http=types.SimpleNamespace(client=http.client),socket=socket,threading=threading,time=time,
        queue=queue,json=json,hashlib=hashlib,urlsplit=urlsplit,Path=Path,MAX_JSON=256*1024,
        WORKFLOW='w',MODEL='m',ai_catalog=types.SimpleNamespace(TASK_SCHEMA='t'))
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),ns)
    return ns


def exchange(path,body=b'{"ok":true}',version='1.0',length=None,status=200,delay=0,timeout=1,limit=256*1024):
    ns=client_namespace(path);a,b=socket.socketpair()
    class Adapter:
        def __getattr__(self,name):return getattr(a,name)
        def setsockopt(self,*args):pass # TCP_NODELAY has no equivalent on AF_UNIX.
    def server():
        try:
            received=b''
            while b'\r\n\r\n' not in received:
                chunk=b.recv(4096)
                if not chunk:return
                received+=chunk
            header=('HTTP/'+version+' '+str(status)+' OK\r\nContent-Type: application/json\r\nContent-Length: '+str(len(body) if length is None else length)+'\r\n\r\n').encode()
            b.sendall(header)
            if delay:time.sleep(delay)
            b.sendall(body)
        except OSError:pass
        finally:b.close()
    thread=threading.Thread(target=server,daemon=True);thread.start()
    ns['deadline_socket']=lambda *args:Adapter()
    provider=ns['HTTPProvider']('http://localhost:1','x'*32,'w','m')
    try:return provider._request('GET','/v1/health',timeout=timeout,limit=limit)
    except Exception as error:return getattr(error,'code',type(error).__name__)
    finally:a.close();thread.join(timeout=2)


class HTTP10(unittest.TestCase):
    fixed=ROOT/'beget-ai-window-20261024/ai_provider.http10.py'
    sealed=ROOT.parents[2]/'Выпуски/guest-20261020-1/backend/app/ai_provider.py'
    def test_original_http10_fails(self):
        self.assertEqual(exchange(self.sealed),'AI_GPU_TRANSPORT_ERROR')
    def test_http10_and_http11_complete(self):
        for version in ('1.0','1.1'):
            with self.subTest(version=version):self.assertEqual(exchange(self.fixed,version=version)[2],b'{"ok":true}')
    def test_multichunk_png_sized_body(self):
        body=b'x'*(1024*1024)
        self.assertEqual(exchange(self.fixed,body=body,limit=2**21)[2],body)
    def test_truncated_body_rejected(self):
        self.assertEqual(exchange(self.fixed,length=100),'AI_GPU_RESPONSE_INVALID')
    def test_oversized_header_rejected(self):
        self.assertEqual(exchange(self.fixed,length=1024*1024),'AI_GPU_RESPONSE_TOO_LARGE')
    def test_redirect_rejected(self):
        self.assertEqual(exchange(self.fixed,status=302),'AI_GPU_REDIRECT_REJECTED')
    def test_slow_body_deadline(self):
        self.assertEqual(exchange(self.fixed,delay=.4,timeout=.1),'AI_GPU_TRANSPORT_ERROR')


if __name__=='__main__':unittest.main()
