import os
import sys
import pytest

# Add logistics_tool to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.extractors.one_extractor import OneExtractor

def get_test_files():
    """Retrieve all PDF files from the ONE test directory."""
    test_dir = r"C:\Users\ADMIN\Subject_HCMUT\Nam_3\5. Macro check bill\SWB test tool\ONE"
    if not os.path.exists(test_dir):
        return []
    return [os.path.join(test_dir, f) for f in os.listdir(test_dir) if f.lower().endswith('.pdf')]

# Generate parameterized tests for all files found
pdf_files = get_test_files()

@pytest.mark.parametrize("pdf_path", pdf_files)
def test_one_extraction(pdf_path):
    """
    Test extraction on ONE PDFs to ensure essential fields are not empty 
    and no fatal errors are raised during extraction.
    """
    extractor = OneExtractor(pdf_path)
    # The new base extractor structure returns a list of sheets/dictionaries,
    # where the first dictionary contains the main BL data.
    extracted_data = extractor.extract()
    
    assert extracted_data is not None
    assert isinstance(extracted_data, list)
    assert len(extracted_data) > 0
    
    main_data = extracted_data[0]
    
    # Assert critical fields are present and not empty
    assert main_data.get("Description") is not None
    assert main_data.get("Shipper") is not None
    assert main_data.get("Consignee") is not None
    
    # Remarks should be correctly cropped and not contain footer junk
    remark = main_data.get("Remark", "")
    assert "OCEAN FREIGHT PREPAID" not in remark
    
    # Description should be clean of continuation markers
    description = main_data.get("Description", "")
    assert "TO BE CONTINUED" not in description.upper()
