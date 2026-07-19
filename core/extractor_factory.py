import pdfplumber
from .extractors.one_extractor import OneExtractor
from .extractors.msc_extractor import MscExtractor
from .extractors.oocl_extractor import OoclExtractor
from .extractors.sjj_extractor import SjjExtractor
from .extractors.zim_extractor import ZimExtractor
from .extractors.hmm_extractor import HmmExtractor

def process_pdf(pdf_path):
    """
    Factory function: Reads the first page of the PDF to identify the shipping 
    carrier and returns the corresponding list of extracted data (List of Dict).
    """
    with pdfplumber.open(pdf_path) as pdf:
        # Read text from the first page to identify the carrier
        text = pdf.pages[0].extract_text()
        text_upper = text.upper() if text else ""

    # Detect carrier keywords (in order of priority)
    if "OCEAN NETWORK EXPRESS" in text_upper or "(ONE), AS CARRIER" in text_upper:
        extractor = OneExtractor(pdf_path)
    elif "MEDITERRANEAN SHIPPING" in text_upper or "MSC" in text_upper:
        extractor = MscExtractor(pdf_path)
    elif "ORIENT OVERSEAS" in text_upper or "OOCL" in text_upper:
        extractor = OoclExtractor(pdf_path)
    elif "ZIM INTEGRATED SHIPPING" in text_upper or "ZIM" in text_upper:
        extractor = ZimExtractor(pdf_path)
    elif "SJJ" in text_upper or "JJSHIPPING" in text_upper or "JINJIANG" in text_upper or "JJDH" in text_upper:
        extractor = SjjExtractor(pdf_path)
    elif "HMM" in text_upper or "HYUNDAI MERCHANT MARINE" in text_upper:
        extractor = HmmExtractor(pdf_path)
    else:
        print(f"[*] Warning: Could not identify carrier for file {pdf_path}. Skipping.")
        return [], None

    return extractor.extract(), extractor.carrier_name
