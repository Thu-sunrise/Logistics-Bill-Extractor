import pdfplumber
import json
from core.extractors.zim_extractor import ZimExtractor

# 1. Thay đường dẫn này bằng đường dẫn tới file PDF OOCL thực tế của bạn
pdf_path = r"C:\Users\ADMIN\Downloads\IKEA_SWB\SWB\ZIM\ZIM-041-TSO-S10000255336-061-DT-ZIMUHCM80653733-ZIMUHCM000302836-18937-ETD 04Jul ok.pdf"
# 2. Thay đường dẫn này bằng tên file TXT mà bạn muốn xuất ra
txt_output_path = r"output_first_page.txt"

def test_zim_extractor(path):
    print("Testing ZimExtractor...")
    try:
        extractor = ZimExtractor(path)
        result = extractor.extract()
        print(f"Extracted {len(result)} rows.")
        with open("test_output.json", "w", encoding="utf-8") as f:
            json.dump(result, f, indent=4, ensure_ascii=False)
        print("Output saved to test_output.json")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_zim_extractor(pdf_path)
