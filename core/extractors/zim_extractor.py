from .base_extractor import BaseExtractor

class ZimExtractor(BaseExtractor):
    def __init__(self, pdf_path):
        super().__init__(pdf_path)
        self.carrier_name = "ZIM"

    def extract(self):
        # TODO: Implement ZIM parsing logic later
        # For now, return an empty row
        return [self.get_empty_row()]
