"""Main HTTPS bytes stay in the local fixture while retaining logical TLS names."""
import os
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from p6_requests_runner import route_main_transport


class LocalTLSTests(unittest.TestCase):
    def test_https_tunnel_uses_only_frozen_local_fixture_without_touching_tls(self):
        connected=[]
        class Wire:
            def __init__(self):self.sent=[];self.reply=iter(b'HTTP/1.1 200 Connection Established\r\n\r\n')
            def sendall(self,data):self.sent.append(data)
            def recv(self,size):return bytes((next(self.reply),))
        env={'HTTPS_PROXY':'http://127.0.0.1:34567','HTTPBIN_URL':'http://fixture.test:45678/'}
        with patch.dict(os.environ,env,clear=True),patch.object(socket.socket,'connect',lambda wire,addr:connected.append(addr)),patch.object(socket,'getaddrinfo',return_value=[]) as lookup:
            route_main_transport()
            wire=Wire();socket.socket.connect(wire,('127.0.0.1',443))
            socket.getaddrinfo('httpbin.org',443)
            self.assertEqual(connected,[('127.0.0.1',34567)])
            self.assertIn(b'CONNECT fixture.test:45678 ',wire.sent[0])
            self.assertNotIn(b'CONNECT httpbin.org:443',wire.sent[0])
            lookup.assert_called_once_with('127.0.0.1',443)
            self.assertEqual(os.environ['HTTP_PROXY'],env['HTTPS_PROXY'])
            self.assertNotIn('HTTPS_PROXY',os.environ)


if __name__=='__main__':unittest.main()
