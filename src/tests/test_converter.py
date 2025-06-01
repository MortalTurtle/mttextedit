import unittest
from unittest import mock
from core.text_exporter import TextExporter


class TestConverter(unittest.TestCase):
    def setUp(self):
        self.converter = TextExporter(["qwer", "qwer", "qwer"])

    @mock.patch('builtins.open', new_callable=mock.mock_open)
    def test_converter(self, mock_open):
        self.converter.to_doc("./testfile")
        self.converter.to_html("./testfile")
        self.converter.to_pdf("./testfile")
        mock_open.assert_called()


if __name__ == '__main__':
    unittest.main()
