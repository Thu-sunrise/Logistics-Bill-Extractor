import re
from .base_extractor import BaseExtractor

class SchenkerExtractor(BaseExtractor):

    @classmethod
    def is_match(cls, text_upper):
        return 'SCHENKER' in text_upper or 'THE GREAT OCEAN LINE' in text_upper or 'TGOL' in text_upper

    def __init__(self, pdf_path):
        super().__init__(pdf_path)
        self.carrier_name = "Schenker / TGOL"
        self.asterisk_note = ""

    def extract_headers(self, pdf, row):
        page1 = pdf.pages[0]

        # Fixed bounding boxes based on Schenker / TGOL standard template
        # format: (x0, top, x1, bottom)
        boxes = {
            'Shipper': (30, 115, 280, 180),
            'Consignee': (30, 190, 280, 265),
            'Notify party 1': (30, 265, 280, 335),
            'Bill no.': (285, 115, 500, 140),
            'Vessel_Voyage': (30, 320, 260, 350),
            'POL': (30, 350, 160, 370),
            'POD': (160, 350, 500, 370)
        }

        def get_text(page, bbox):
            text = page.within_bbox(bbox).extract_text()
            return text.strip() if text else ""

        # Shipper
        row["Shipper"] = get_text(page1, boxes['Shipper'])
        
        # Consignee
        row["Consignee"] = get_text(page1, boxes['Consignee'])
        
        # Notify
        row["Notify party 1"] = get_text(page1, boxes['Notify party 1'])
        
        # Bill no
        row["Bill no."] = get_text(page1, boxes['Bill no.'])
        
        # Vessel / Voyage
        vessel_voyage_text = get_text(page1, boxes['Vessel_Voyage'])
        if vessel_voyage_text and '/' in vessel_voyage_text:
            parts = vessel_voyage_text.split('/')
            row["Vessel name"] = parts[0].strip()
            if len(parts) > 1:
                row["Voyage number"] = parts[1].strip()
        else:
            row["Vessel name"] = vessel_voyage_text

        # POL
        row["POL"] = get_text(page1, boxes['POL']).strip()
        
        # POD
        row["POD"] = get_text(page1, boxes['POD']).strip()

    def extract_footers(self, pdf, row):
        page1 = pdf.pages[0]
        words = page1.extract_words()
        
        # ATD
        for w in words:
            if "DATE:" in w['text']:
                bbox = (w['x1'], w['top'] - 2, page1.width, w['bottom'] + 2)
                text = page1.within_bbox(bbox).extract_text()
                row["ATD"] = text.strip() if text else ""
                break
                
        # Freight
        for w in words:
            if "FREIGHT" in w['text']:
                bbox = (w['x0'], w['top'] - 2, w['x0'] + 150, w['bottom'] + 2)
                text = page1.within_bbox(bbox).extract_text()
                freight_text = (text.strip() if text else "").upper()
                if "PREPAID" in freight_text:
                    row["Freight"] = "FREIGHT PREPAID"
                elif "COLLECT" in freight_text:
                    row["Freight"] = "FREIGHT COLLECT"
                break

    def extract_containers(self, pdf):
        containers = []
        current_cont = {}
        desc_lines = []
        found_carton = False
        expect_seal = False

        for i, page in enumerate(pdf.pages):
            words = page.extract_words()
            
            # Skip Terms and Conditions pages
            page_text = " ".join([w['text'] for w in words[:50]]).upper()
            if "CONDITIONS OF CARRIAGE" in page_text or "TERMS AND CONDITIONS" in page_text:
                continue

            line_words = self.group_words_by_y(words)

            for top in sorted(line_words.keys()):
                if i == 0 and top < 370:  # Container section starts around Y=370 on page 1
                    continue
                if top > 680:  # Skip footers
                    break
                    
                line_str = " ".join([w['text'] for w in sorted(line_words[top], key=lambda x: x['x0'])]).upper()
                
                # Bottom boundaries
                if any(k in line_str for k in ["FREIGHT", "SHIPPED", "PLACE AND DATE", "ISSUED AS", "NO VALUE DECLARED"]):
                    break
                
                # Skip header lines on attachment pages
                if i > 0 and any(k in line_str for k in ["SEA WAYBILL ATTACHMENT", "B/L NO.", "STT NO.", "VESSEL", "VOYAGE", "KIND OF PACKAGES", "GROSS WEIGHT MEASUREMENT"]):
                    continue

                col_left = []
                col_type = []
                col_desc = []
                col_weight = []
                col_measure = []
                
                for w in line_words[top]:
                    x = (w['x0'] + w['x1']) / 2
                    if x < 140:
                        col_left.append(w['text'])
                    elif x < 220:
                        col_type.append(w['text'])
                    elif x < 350:
                        col_desc.append(w['text'])
                    elif x < 450:
                        col_weight.append(w['text'])
                    else:
                        col_measure.append(w['text'])
                        
                col_left_text = " ".join(col_left).strip()
                col_type_text = " ".join(col_type).strip()
                col_desc_text = " ".join(col_desc).strip()
                col_weight_text = " ".join(col_weight).strip()
                col_measure_text = " ".join(col_measure).strip()
                
                # Check for Cont no
                cont_no_match = re.search(r'[A-Z]{4}\s*\d{7}', col_left_text)
                if cont_no_match:
                    if "Cont no." in current_cont: 
                        current_cont["Description"] = "\n".join(desc_lines)
                        containers.append(current_cont)
                        current_cont = {}
                        desc_lines = []
                        found_carton = False
                        
                    current_cont["Cont no."] = cont_no_match.group(0).replace(" ", "")
                    
                    if col_type_text:
                        # Sometimes it has quantity "1 40HQ HC"
                        m = re.search(r'\d+\s+(.*)', col_type_text)
                        if m:
                            current_cont["Cont type"] = m.group(1).strip()
                        else:
                            current_cont["Cont type"] = col_type_text
                    
                # Seal no
                seal_match = re.search(r'SEAL:\s*([A-Za-z0-9]+)', col_left_text, re.IGNORECASE)
                if seal_match:
                    current_cont["Seal no."] = seal_match.group(1)
                    expect_seal = False
                elif "SEAL" in col_left_text.upper():
                    expect_seal = True
                elif expect_seal and re.search(r'[A-Za-z0-9]', col_left_text):
                    if not re.search(r'^[A-Z]{4}\s*\d{7}$', col_left_text):
                        current_cont["Seal no."] = col_left_text.strip()
                    expect_seal = False
                    
                # Description lines
                if col_desc_text:
                    if ("CARTON" in col_desc_text.upper() or "PKG" in col_desc_text.upper()) and not found_carton:
                        m = re.search(r'=\s*(.*)', col_desc_text)
                        if m:
                            current_cont["Total carton"] = m.group(1).strip()
                        else:
                            current_cont["Total carton"] = col_desc_text
                        found_carton = True
                        
                        if col_weight_text:
                            current_cont["Total GW"] = col_weight_text.strip()
                        if col_measure_text:
                            current_cont["Total CBM"] = col_measure_text.strip()
                            
                    elif found_carton:
                        cleaned_desc = " ".join(filter(None, [col_type_text, col_desc_text, col_weight_text, col_measure_text])).strip()
                        if cleaned_desc.startswith('*'):
                            self.asterisk_note = cleaned_desc.lstrip('*').strip()
                            break
                        if cleaned_desc:
                            desc_lines.append(cleaned_desc)
                            
        if current_cont:
            current_cont["Description"] = "\n".join(desc_lines)
            containers.append(current_cont)
            
        return containers
