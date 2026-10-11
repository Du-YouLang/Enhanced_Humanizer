"""Local dual-protocol fixture; its CA is scoped to this benchmark only."""
import contextlib
import json
from pathlib import Path
import selectors
import socket
import subprocess
import time
from p6_prepare_linux import BASE,setup_env
from p6_requests_linux import PREFIX

CA=BASE/'public-fixtures/httpbin-tls-v1/ca-bundle.pem'

@contextlib.contextmanager
def fixture():
    folder=BASE/'private/httpbin-tls-v1';folder.mkdir(parents=True,exist_ok=True)
    key=folder/'server.key';cert=folder/'server.crt';env=setup_env()
    if not key.exists():
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','365',
          '-keyout',str(key),'-out',str(cert),'-subj','/CN=Local Workbench HTTPBIN',
          '-addext','subjectAltName=DNS:httpbin.org,DNS:'+socket.gethostname().lower()+',DNS:localhost,IP:127.0.0.1'],
          env=env,capture_output=True,check=True,timeout=30)
        key.chmod(0o600)
    CA.parent.mkdir(parents=True,exist_ok=True)
    if not CA.exists():CA.write_bytes(Path('/etc/ssl/certs/ca-certificates.crt').read_bytes()+b'\n'+cert.read_bytes())
    with (folder/(str(time.time_ns())+'.private.log')).open('wb') as log:
        p=subprocess.Popen([str(PREFIX/'bin/python'),'-B','/opt/workbench/source/p6_httpbin_tls_linux.py'],
                           cwd=BASE,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log)
        try:
            p.stdin.write(json.dumps({'key':str(key),'cert':str(cert)}).encode());p.stdin.close()
            with selectors.DefaultSelector() as sel:
                sel.register(p.stdout,selectors.EVENT_READ)
                if not sel.select(20):raise RuntimeError('Local HTTP/TLS fixture did not start')
                value=json.loads(p.stdout.readline())
            yield value['fixture_url']
        finally:
            p.terminate()
            try:p.wait(timeout=5)
            except subprocess.TimeoutExpired:p.kill();p.wait()
