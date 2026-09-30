import unittest

from codex_taskbar.model_proxy import ModelProxy, response_model


class ModelProxyTests(unittest.TestCase):
    def test_response_model_reads_header_only(self):
        raw = (b'HTTP/1.1 101 Switching Protocols\r\n'
               b'OpenAI-Model: gpt-6.1-sol\r\nConnection: Upgrade\r\n\r\n'
               b'{"model":"secret-body-value"}')
        self.assertEqual(response_model(raw), 'gpt-6.1-sol')

    def test_response_model_rejects_missing_or_oversized_header(self):
        self.assertIsNone(response_model(b'HTTP/1.1 200 OK\r\n\r\n'))
        self.assertIsNone(response_model(b'HTTP/1.1 200 OK\r\nOpenAI-Model: ' + b'x' * 161 + b'\r\n\r\n'))

    def test_proxy_uses_loopback_and_ephemeral_spki(self):
        values = []
        proxy = ModelProxy(lambda model, at: values.append((model, at)))
        try:
            proxy.start()
            self.assertEqual(proxy.address[0], '127.0.0.1')
            self.assertTrue(proxy.address[1] > 0)
            args = proxy.launch_args()
            self.assertTrue(args[0].startswith('--proxy-server=http://127.0.0.1:'))
            self.assertIn('--ignore-certificate-errors-spki-list=', args[1])
            self.assertTrue(proxy.environment()['NO_PROXY'].startswith('127.0.0.1'))
        finally:
            proxy.close()
        self.assertFalse(proxy.running)


if __name__ == '__main__':
    unittest.main()
