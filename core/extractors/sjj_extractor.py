from .base_extractor import BaseExtractor

class SjjExtractor(BaseExtractor):
    def __init__(self, pdf_path):
        super().__init__(pdf_path)
        self.carrier_name = "SJJ"

    def extract(self):
        # TODO: Implement SJJ parsing logic later
        # For now, return an empty row
        return [self.get_empty_row()]
