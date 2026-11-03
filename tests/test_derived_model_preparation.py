"""The explicit preparation command cannot collect or use a paid provider."""
from contextlib import redirect_stderr
from io import StringIO
import socket
import unittest

from scripts.prepare_private_read_models import main, offline_preparation


class PreparationTests(unittest.TestCase):
    def test_writer_requires_the_explicit_prepare_argument(self):
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as error:
            main([])
        self.assertEqual(error.exception.code, 2)

    def test_preparation_blocks_network_and_restores_socket_apis(self):
        originals = (socket.socket.connect, socket.socket.connect_ex, socket.create_connection, socket.getaddrinfo)
        with offline_preparation():
            for function, args in [(socket.create_connection, (("example.test", 443),)),
                                   (socket.getaddrinfo, ("example.test", 443))]:
                with self.assertRaises(RuntimeError):
                    function(*args)
            with socket.socket() as handle:
                with self.assertRaises(RuntimeError):
                    handle.connect(("127.0.0.1", 1))
                with self.assertRaises(RuntimeError):
                    handle.connect_ex(("127.0.0.1", 1))
        self.assertEqual((socket.socket.connect, socket.socket.connect_ex, socket.create_connection, socket.getaddrinfo), originals)


if __name__ == "__main__":
    unittest.main()
