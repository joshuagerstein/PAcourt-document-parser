import re
from pathlib import Path

import pytest
from pypdf.errors import PdfReadError

from docket_parser import test_data_path, document_types
from docket_parser.extraction import DocketReader, logger as extraction_logger

DATA_PATH = test_data_path
MODIFIED_PDFS_PATH = DATA_PATH / "modified_pdfs"


def get_pdf_paths() -> tuple[list[Path], list[str]]:
    pdf_paths = []
    for document_type in document_types:
        paths = (DATA_PATH / document_type / 'pdfs').glob("*.pdf")
        pdf_paths.extend(paths)
    ids = [path.stem for path in pdf_paths]
    return pdf_paths, ids


class TestExtraction:
    def test_warn_not_crystal_report(self, caplog):
        """Ensure that there is a logged warning when trying to extract text from a pdf not generated by
         Crystal Reports. 'Crystal Reports' should be in that warning message."""
        for modified_pdf in MODIFIED_PDFS_PATH.glob('*.pdf'):
            with caplog.at_level("WARNING", extraction_logger.name):
                DocketReader(modified_pdf)
            assert any("crystal reports" in msg.lower() for msg in caplog.messages), \
                "DocketReader should warn when metadata does not indicate the file is generated by Crystal Reports"

    def test_proper_output_format(self):
        """Check that every line/segment of extracted text has the format expected by the grammar."""
        document_paths = get_pdf_paths()[0]
        for test_file_path in document_paths:
            reader = DocketReader(test_file_path)
            extracted_text = reader.extract_text()
            lines = extracted_text.split(reader.terminator)
            assert lines[-1] == '', "Extracted text should end with terminator character"

            escaped_close = re.escape(reader.properties_close)
            properties_regex = r"[0-9]{3}\.[0-9]{2},[0-9]{3}\.[0-9]{2},(normal|bold)" + escaped_close
            for line in lines[:-1]:
                split_line = line.split(reader.properties_open)
                assert len(split_line) == 2, \
                    "Reader properties_open character should appear exactly once in each segment"
                content, properties = split_line
                assert reader.properties_close not in content, \
                    "Reader properties_close should not appear before properties_open"

                match = re.match(properties_regex, properties)
                assert len(match.groups()) == 1, "Correctly formatted properties should appear once in each segment."

    def test_error_if_special_char_in_pdf(self):
        """Check that DocketReader throws an error if one of its special characters appears in a PDF it tries to read"""
        original_tab = DocketReader.tab
        test_content_characters = ' aA,.:'
        for test_file in get_pdf_paths()[0]:
            for test_content_character in test_content_characters:
                DocketReader.tab = test_content_character
                with pytest.raises(expected_exception=PdfReadError):
                    DocketReader(test_file)
                    DocketReader.tab = original_tab
        # This feels very hacky.
        DocketReader.tab = original_tab

    @pytest.mark.parametrize('pdf_path', get_pdf_paths()[0], ids=get_pdf_paths()[1])
    def test_documents(self, data_regression, pdf_path):
        """Regression test, check that the extracted text from given document matches expected text."""
        reader = DocketReader(pdf_path)
        result = {"extracted text": reader.extract_text()}
        data_regression.check(result)