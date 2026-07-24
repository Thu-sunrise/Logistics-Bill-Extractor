import pdfplumber
from .extractors.one_extractor import OneExtractor
from .extractors.msc_extractor import MscExtractor
from .extractors.oocl_extractor import OoclExtractor
from .extractors.zim_extractor import ZimExtractor
from .extractors.sjj_extractor import SjjExtractor
from .extractors.hmm_extractor import HmmExtractor
from .extractors.cma_cgm_extractor import CmaCgmExtractor
from .extractors.cosco_extractor import CoscoExtractor
from .extractors.maersk_extractor import MaerskExtractor
from .extractors.kn_extractor import KnExtractor
from .extractors.hlo_extractor import HloExtractor
from .extractors.schenker_extractor import SchenkerExtractor

EXTRACTORS = [
    OneExtractor,
    MscExtractor,
    OoclExtractor,
    ZimExtractor,
    SjjExtractor,
    HmmExtractor,
    CmaCgmExtractor,
    CoscoExtractor,
    MaerskExtractor,
    KnExtractor,
    HloExtractor,
    SchenkerExtractor
]

def process_pdf(pdf_path):
    """
    Factory function: Reads the first page of the PDF to identify the shipping 
    carrier and returns the corresponding list of extracted data (List of Dict).
    """
    with pdfplumber.open(pdf_path) as pdf:
        if not pdf.pages:
            print(f"[*] Warning: File {pdf_path} has no pages.")
            return [], None
            
        # Read text from the first page to identify the carrier
        text = pdf.pages[0].extract_text()
        text_upper = text.upper() if text else ""

    # Detect carrier using registered classes
    extractor = None
    for ExtractorClass in EXTRACTORS:
        if ExtractorClass.is_match(text_upper):
            extractor = ExtractorClass(pdf_path)
            break
            
    if not extractor:
        print(f"[*] Warning: Could not identify carrier for file {pdf_path}. Skipping.")
        return [], None

    return extractor.extract(), extractor.carrier_name
