"""Pinned upstream HTTPBIN WSGI fixture, loopback only; no model execution."""
import json
import socket
import sys
from werkzeug.serving import make_server
from httpbin import app

if __name__=='__main__':
    address=socket.gethostbyname(socket.gethostname())
    if not address.startswith('127.'):raise RuntimeError('Fixture must resolve to loopback')
    server=make_server(address,0,app,threaded=True)
    print(json.dumps({'fixture_url':f'http://{socket.gethostname().lower()}:{server.server_port}/'}),flush=True)
    server.serve_forever()
