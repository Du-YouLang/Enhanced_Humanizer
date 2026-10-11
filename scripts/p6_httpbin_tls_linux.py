"""Same pinned HTTPBIN app on a local port supporting both HTTP and HTTPS."""
import json
import socket
import ssl
import sys
from werkzeug.serving import make_server,WSGIRequestHandler
from httpbin import app

class Handler(WSGIRequestHandler):
    def make_environ(self):
        value=super().make_environ()
        if isinstance(self.connection,ssl.SSLSocket):value['wsgi.url_scheme']='https'
        return value

if __name__=='__main__':
    spec=json.load(sys.stdin);address=socket.gethostbyname(socket.gethostname())
    if not address.startswith('127.'):raise RuntimeError('Fixture must resolve to loopback')
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(spec['cert'],spec['key'])
    server=make_server(address,0,app,threaded=True,request_handler=Handler);original=server.get_request
    def connection():
        sock,peer=original();sock.settimeout(5)
        if sock.recv(1,socket.MSG_PEEK)==b'\x16':sock=context.wrap_socket(sock,server_side=True)
        return sock,peer
    server.get_request=connection
    print(json.dumps({'fixture_url':f'http://{socket.gethostname().lower()}:{server.server_port}/'}),flush=True)
    server.serve_forever()
