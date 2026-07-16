import pdfplumber
from .extractors.one_extractor import OneExtractor
from .extractors.msc_extractor import MscExtractor
from .extractors.oocl_extractor import OoclExtractor
from .extractors.sjj_extractor import SjjExtractor
from .extractors.zim_extractor import ZimExtractor

def process_pdf(pdf_path):
    """
    Factory function: Đọc trang đầu tiên của file PDF, nhận diện hãng tàu
    và trả về danh sách dữ liệu (List of Dict) tương ứng.
    """
    with pdfplumber.open(pdf_path) as pdf:
        # Đọc text trang đầu tiên để nhận diện hãng tàu
        text = pdf.pages[0].extract_text()
        text_upper = text.upper() if text else ""

    # Dò từ khóa của từng hãng (theo thứ tự ưu tiên)
    if "OCEAN NETWORK EXPRESS" in text_upper or "(ONE), AS CARRIER" in text_upper:
        extractor = OneExtractor(pdf_path)
    elif "MEDITERRANEAN SHIPPING" in text_upper or "MSC" in text_upper:
        extractor = MscExtractor(pdf_path)
    elif "ORIENT OVERSEAS" in text_upper or "OOCL" in text_upper:
        extractor = OoclExtractor(pdf_path)
    elif "ZIM INTEGRATED SHIPPING" in text_upper or "ZIM" in text_upper:
        extractor = ZimExtractor(pdf_path)
    elif "SJJ" in text_upper:  # Cập nhật từ khóa nhận diện thật của SJJ sau này
        extractor = SjjExtractor(pdf_path)
    else:
        # Nếu không nhận diện được, mặc định coi như ONE hoặc raise Exception
        # Tạm thời log ra terminal và trả về kết quả rỗng
        print(f"[*] Cảnh báo: Không thể nhận diện hãng tàu cho file {pdf_path}. Bỏ qua.")
        return []

    # Tiến hành bóc tách bằng class chuyên biệt
    return extractor.extract()
