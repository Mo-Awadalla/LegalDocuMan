from unittest.mock import MagicMock

from legaldocuman.intake import DocumentIntake


def test_unreadable_pdf_is_rejected_before_classification(tmp_path):
    corrupt = tmp_path / "corrupt.pdf"
    corrupt.write_bytes(b"%PDF-1.7\nno-xref")
    text_extractor = MagicMock()
    text_extractor.page_renderer.total_pages.return_value = 0
    intake = DocumentIntake(
        text_extractor=text_extractor,
        date_extractor=MagicMock(),
        doc_type_classifier=MagicMock(),
        status_classifier=MagicMock(),
        small_lm=MagicMock(),
        smart_reader=MagicMock(),
    )

    record = intake.analyze(str(corrupt), "")

    assert record.error == "PDF could not be parsed"
    intake.smart_reader.read.assert_not_called()
