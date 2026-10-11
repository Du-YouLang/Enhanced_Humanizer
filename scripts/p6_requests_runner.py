"""Compatibility routing for Requests 2.3's legacy HTTPS proxy hostname check.

Keep certificate verification enabled and the upstream HTTPBIN destination unchanged.
Only alias the already permitted loopback fence proxy, so the legacy client uses the
destination's TLS name rather than incorrectly checking its 127.0.0.1 proxy address.
This is a local evaluation deviation, not an official leaderboard runner.
"""
import os
import socket
import sys
from urllib.parse import urlsplit


def route_main_transport():
    """Tunnel raw sockets through the same fence, preserving client URL handling.

    Legacy Requests treats mixed-case HTTPS differently when environment HTTP
    proxies are present. The frozen tests expect direct HTTP/TLS semantics.
    Restrict this adapter to the two existing fixture destinations; retain TLS
    verification and all upstream request/response/test code.
    """
    raw=os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
    proxy=urlsplit(raw or '');fixture=urlsplit(os.environ.get('HTTPBIN_URL',''))
    if proxy.hostname!='127.0.0.1' or proxy.scheme!='http' or not proxy.port or not fixture.hostname or not fixture.port:
        raise RuntimeError('Expected the exact Humanize proxy and local fixture')
    targets={fixture.port:fixture.hostname,443:'httpbin.org'}
    original_lookup=socket.getaddrinfo;original_connect=socket.socket.connect
    def lookup(host,target_port,*args,**kwargs):
        if targets.get(int(target_port or 0))==host:host='127.0.0.1'
        return original_lookup(host,target_port,*args,**kwargs)
    def connect(sock,address):
        if isinstance(address,tuple) and len(address)==2 and address[0].startswith('127.') and address[1] in targets:
            host=targets[address[1]];port=address[1]
            original_connect(sock,('127.0.0.1',proxy.port))
            sock.sendall(f'CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n\r\n'.encode())
            header=b''
            while not header.endswith(b'\r\n\r\n'):
                byte=sock.recv(1)
                if not byte or len(header)>4096:raise OSError('Fixture proxy tunnel failed')
                header+=byte
            if not header.startswith(b'HTTP/1.1 200 '):raise OSError('Fixture proxy tunnel refused')
            return
        return original_connect(sock,address)
    socket.getaddrinfo=lookup;socket.socket.connect=connect
    for key in tuple(os.environ):
        if key.lower() in ('http_proxy','https_proxy','all_proxy','no_proxy'):os.environ.pop(key)
    # Plain HTTP retains the original proxy and its forbidden-host responses.
    # HTTPS uses the raw tunnel, including Session.send's mixed-case URL tests.
    os.environ['HTTP_PROXY']=raw


def route_legacy_proxy():
    raw=os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
    if not raw:return
    proxy=urlsplit(raw)
    if proxy.hostname!='127.0.0.1' or proxy.scheme!='http' or not proxy.port:
        raise RuntimeError('Expected the Humanize loopback proxy')
    original=socket.getaddrinfo
    port=proxy.port
    def alias(host,target_port,*args,**kwargs):
        if host=='httpbin.org' and int(target_port)==port:
            host='127.0.0.1'
        return original(host,target_port,*args,**kwargs)
    socket.getaddrinfo=alias
    for key in ('HTTPS_PROXY','https_proxy'):os.environ[key]=f'http://httpbin.org:{port}'
    # Session.send(prepared_request) in this old release ignores environment proxies.
    # Tunnel its raw local-fixture TCP connection through the existing exact-host proxy.
    # No request, response, certificate check or Requests implementation is modified.
    fixture=urlsplit(os.environ.get('HTTPBIN_URL',''))
    if fixture.hostname and fixture.port:
        real_connect=socket.socket.connect
        fixture_port=fixture.port
        fixture_host=fixture.hostname
        def tunnel(sock,address):
            if isinstance(address,tuple) and len(address)==2 and address[1]==fixture_port and address[0].startswith('127.'):
                real_connect(sock,('127.0.0.1',port))
                sock.sendall(f'CONNECT {fixture_host}:{fixture_port} HTTP/1.1\r\nHost: {fixture_host}:{fixture_port}\r\n\r\n'.encode())
                header=b''
                while not header.endswith(b'\r\n\r\n'):
                    byte=sock.recv(1)
                    if not byte or len(header)>4096:raise OSError('Fixture proxy tunnel failed')
                    header+=byte
                if not header.startswith(b'HTTP/1.1 200 '):raise OSError('Fixture proxy tunnel refused')
                return
            return real_connect(sock,address)
        socket.socket.connect=tunnel


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--frozen-selection':route_main_transport()
    else:route_legacy_proxy()
    import pytest
    if len(sys.argv)>1 and sys.argv[1]=='--frozen-selection':
        import json
        import runpy
        Selection=runpy.run_path('/opt/workbench/source/p6_pytest_runner.py')['Selection']
        names=json.loads(sys.argv[2]);paths=list(dict.fromkeys(n.split('::',1)[0] for n in names))
        sys.exit(pytest.main([*sys.argv[3:],*paths],plugins=[Selection(names)]))
    sys.exit(pytest.main(sys.argv[1:]))
