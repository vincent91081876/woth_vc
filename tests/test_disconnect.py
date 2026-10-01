import os
import sys
import unittest


HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import woth_scanner


class _AbortedWriter:
    def write(self, _body):
        raise ConnectionAbortedError(10053, "client disconnected")


class DisconnectTests(unittest.TestCase):
    def test_json_ignores_client_disconnect_while_writing_response(self):
        handler = object.__new__(woth_scanner.Handler)
        handler.wfile = _AbortedWriter()
        handler.send_response = lambda _code: None
        handler.send_header = lambda _name, _value: None
        handler.end_headers = lambda: None

        handler._json({"ok": True})


if __name__ == "__main__":
    unittest.main()