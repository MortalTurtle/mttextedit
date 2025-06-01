import pytest
from core.text_exporter import TextExporter


@pytest.fixture
def text_exporter():
    return TextExporter(["line1", "line2", "line3"])


def test_to_doc_calls_open(text_exporter, mocker):
    mock_open = mocker.patch("builtins.open", mocker.mock_open())
    text_exporter.to_doc("test_doc")

    mock_open.assert_called_once_with("test_doc.doc", "w", encoding="utf-8")


def test_to_html_calls_open(text_exporter, mocker):
    mock_open = mocker.patch("builtins.open", mocker.mock_open())
    text_exporter.to_html("test_html")

    mock_open.assert_called_once_with("test_html.html", "w", encoding="utf-8")


def test_to_pdf_calls_open(text_exporter, mocker):
    mock_open = mocker.patch("builtins.open", mocker.mock_open())
    text_exporter.to_pdf("test_pdf")

    mock_open.assert_called_once_with("test_pdf.pdf", "wb")
