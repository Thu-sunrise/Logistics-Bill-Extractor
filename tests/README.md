# Automated Testing Guide

The `tests/` directory contains the complete automated testing system for the **Logistics Tool** project. This system is built on the `pytest` framework, which helps automate the validation of the accuracy of the PDF extraction algorithms (Extractors) without having to run the tool manually.

---

## Directory Structure

```text
tests/
├── README.md                           # This guide file
├── test_one_extractor.py               # Automated test for ONE shipping line
└── manual_sandbox/                     # Sandbox for manual test scripts
    └── run_manual_script.py            # Place for draft code, manual print logging
```

*   **`test_*.py` files:** These are automated test files. Any file starting with `test_` will be automatically collected and executed by `pytest`.
*   **`manual_sandbox/`:** The place for draft scripts and temporary test code. It ensures the root directory of the project remains clean at all times. `pytest` will ignore the files inside this directory.

---

## How to Run Tests

Open a Terminal (Command Prompt / PowerShell) at the project's root directory (`logistics_tool/`) and type:

```bash
pytest tests/
```

**Or:**
```bash
python -m pytest tests/
```

The system will automatically scan all sample PDF files, run the extraction algorithm, and cross-check with the assertions. You will receive a `PASS` (green) or `FAIL` (red) report right on the screen.

---

## Extension Guide (Adding a New Carrier)

The system is designed with a **Data-Driven** architecture. Once you finish developing the algorithm for a new carrier (e.g., CMA CGM, Hapag Lloyd...), you can add a test for that carrier extremely easily in 2 steps:

### Step 1: Create a new test file
Create a new file in the `tests/` directory, naming it with the prefix `test_` (Example: `test_cma_cgm_extractor.py`).

### Step 2: Copy the code template
Use the template below, changing the path to the directory containing sample PDFs and the Extractor Class name:

```python
import os
import sys
import pytest

# 1. Add the project to the environment variable for importing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 2. Import the new carrier's Extractor class
from core.extractors.cma_cgm_extractor import CMACGM_Extractor

def get_test_files():
    """Function to automatically scan and collect all sample PDF files."""
    # 3. Change this path to the directory containing the new carrier's PDFs
    test_dir = r"C:\Users\ADMIN\Subject_HCMUT\Nam_3\5. Macro check bill\SWB test tool\CMA_CGM"
    if not os.path.exists(test_dir):
        return []
    return [os.path.join(test_dir, f) for f in os.listdir(test_dir) if f.lower().endswith('.pdf')]

pdf_files = get_test_files()

# 4. Parametrization: Automatically duplicate this test function for each scanned PDF file
@pytest.mark.parametrize("pdf_path", pdf_files)
def test_cma_cgm_extraction(pdf_path):
    extractor = CMACGM_Extractor(pdf_path)
    extracted_data = extractor.extract()
    
    # 5. PROTECTIVE ASSERTIONS
    assert extracted_data is not None
    assert len(extracted_data) > 0
    main_data = extracted_data[0]
    
    # Check that mandatory fields are not empty
    assert main_data.get("Description") is not None
    assert main_data.get("Shipper") is not None
    
    # Check junk blocking (Replace with the respective carrier's junk text)
    remark = main_data.get("Remark", "")
    assert "CMA CGM FOOTER JUNK" not in remark.upper()
```

### Best Practices:
1. **Unlimited PDFs:** However many PDF files are in the `test_dir` directory, `pytest` will automatically generate that many independent test cases. Throw as many "difficult" or "weird" PDF files into that directory as possible.
2. **Regression Test:** Every time you modify a small line of code in `core/`, run `pytest` again. If the code you just modified accidentally breaks the results of an old PDF file, the system will report `FAIL` immediately!
