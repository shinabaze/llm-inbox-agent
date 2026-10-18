import http.client
import io
import unittest
import urllib.error

from inbox_agent.llm import worth_retrying


def http_error(code):
    return urllib.error.HTTPError("https://api.example.com", code, "x", {}, io.BytesIO())


class Retries(unittest.TestCase):
    def test_wait_and_retry(self):
        for err in (http_error(429), http_error(503), http.client.RemoteDisconnected("closed"),
                    TimeoutError("read timed out"), urllib.error.URLError("dns")):
            with self.subTest(err=repr(err)):
                self.assertTrue(worth_retrying(err))

    def test_give_up_at_once(self):
        # A bad request or a bad key will fail the same way every time.
        for err in (http_error(400), http_error(401), http_error(404), ValueError("bad json")):
            with self.subTest(err=repr(err)):
                self.assertFalse(worth_retrying(err))


if __name__ == "__main__":
    unittest.main()
