from .base_extractor import BaseExtractor

class MscExtractor(BaseExtractor):
    def __init__(self, pdf_path):
        super().__init__(pdf_path)
        self.carrier_name = "MSC"

    def extract(self):
        # TODO: Implement MSC parsing logic later
        # For now, return an empty row
        return [self.get_empty_row()]
