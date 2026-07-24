import re
import pdfplumber
from .base_extractor import BaseExtractor

class OneExtractor(BaseExtractor):

    @classmethod
    def is_match(cls, text_upper):
        return 'OCEAN NETWORK EXPRESS' in text_upper or '(ONE), AS CARRIER' in text_upper

    def __init__(self, pdf_path):
        super().__init__(pdf_path)
        self.carrier_name = "ONE"
        self._parsed_data = None

    def _parse_all(self, pdf):
        if self._parsed_data: return self._parsed_data
        
        if not pdf.pages:
            self._parsed_data = {"pages_to_read": 0, "full_text": "", "remarks_extracted": [], "Shipper": "", "Consignee": "", "Notify party 1": ""}
            return self._parsed_data

        total_pages = len(pdf.pages)
        pages_to_read = 2
        
        first_page_text = pdf.pages[0].extract_text(layout=True) or ""
        if first_page_text:
            m = re.search(r'PAGE\s*[:]?\s*1\s*(?:OF|O F|/)?\s*(\d+)', first_page_text, re.IGNORECASE)
            if m:
                pages_to_read = int(m.group(1))
        pages_to_read = min(pages_to_read, total_pages)

        full_text = first_page_text + "\n"
        for i in range(1, pages_to_read):
            text = pdf.pages[i].extract_text(layout=True)
            if text:
                full_text += text + "\n"

        first_page = pdf.pages[0]
        data = {"pages_to_read": pages_to_read, "full_text": full_text, "remarks_extracted": []}
        
        data["Shipper"] = self.extract_dynamic_left_block(first_page, "SHIPPER", "CONSIGNEE")
        data["Consignee"] = self.extract_dynamic_left_block(first_page, "CONSIGNEE", "NOTIFY")
        data["Notify party 1"] = self.extract_dynamic_left_block(first_page, "NOTIFY", ["PRE-CARRIAGE", "OCEAN"])
        
        try:
            for page_idx in range(pages_to_read):
                page = pdf.pages[page_idx]
                top_y, bottom_y = None, None
                for kw in ['PARTICULARS', 'DESCRIPTION']:
                    word = self.find_word_bbox(page, kw)
                    if word: top_y = word['bottom']; break
                for kw in ['LIABILITY', 'VALOREM']:
                    word = self.find_word_bbox(page, kw)
                    if word: bottom_y = word['top']; break
                if not top_y or not bottom_y: continue
                    
                right_x = 175
                possible_lines = [line['x0'] for line in page.lines if line.get('width', 1) < 1 and line.get('x0', 0) > 100]
                if possible_lines:
                    possible_lines.sort()
                    right_x = possible_lines[0] - 2
                else:
                    for w in page.extract_words():
                        if 340 < w['top'] < 380 and w['text'] == 'NO.':
                            right_x = w['x0'] - 2
                            break

                cropped = page.crop((0, top_y, right_x, bottom_y))
                col_text = cropped.extract_text(layout=True)
                if not col_text: continue
                    
                lines_col = col_text.split('\n')
                page_remarks = []
                for line in lines_col:
                    line_stripped = line.strip()
                    if 'DE C L A R' in line.upper() or 'DECLARATION' in line.upper() or line_stripped == '**': continue
                    if re.match(r'^[A-Z]{4}[0-9]{7}', line_stripped) or '/FCL' in line_stripped or re.match(r'^-+$', line_stripped):
                        page_remarks = [] 
                        continue
                    if any(kw in line_stripped.upper() for kw in ['OCEAN FREIGHT', 'DESTINATION CHARGES', 'PARTY WHO', 'SHIPPER\'S LOAD']):
                        break
                    if not line_stripped:
                        if page_remarks: break 
                        else: continue
                    page_remarks.append(line_stripped)
                if page_remarks:
                    data["remarks_extracted"].extend(page_remarks)
        except Exception:
            pass

        self._parsed_data = data
        return data

    def extract_headers(self, pdf, row):
        data = self._parse_all(pdf)
        if not data.get("full_text"): return
        
        row["Shipper"] = data["Shipper"]
        row["Consignee"] = data["Consignee"]
        row["Notify party 1"] = data["Notify party 1"]
        
        for field, tags in [("Shipper", ["SH>", "SP>"]), ("Consignee", ["CN>"]), ("Notify party 1", ["NP>"])]:
            if row[field]:
                for tag in tags:
                    row[field] = row[field].replace(tag, "").strip()

        lines = data["full_text"].split('\n')
        for i, line in enumerate(lines):
            if "BOOKING NO" in line and ("WAYBILL NO" in line or "B/L NO" in line):
                if i + 1 < len(lines):
                    parts = lines[i + 1].split()
                    if len(parts) >= 2:
                        row["Bill no."] = parts[-1].strip()
                        row["Booking"] = parts[-2].strip()
                        
            if "OCEAN VESSEL" in line and "VOYAGE" in line and "PORT OF LOADING" in line:
                if i + 1 < len(lines):
                    val = lines[i + 1].replace("Vessel & Voy", "").strip()
                    vessel_voyage, pol = self.split_columns_by_spaces(val)
                    vessel_name, voyage_number, rest = self.parse_vessel_voyage(vessel_voyage)
                    
                    row["POL"] = pol or rest
                    row["Vessel name"] = vessel_name
                    row["Voyage number"] = voyage_number
                    
            if "PORT OF DISCHARGE" in line and "PLACE OF DELIVERY" in line:
                if i + 1 < len(lines):
                    row["POD"], row["Place of delivery"] = self.split_columns_by_spaces(lines[i + 1])

            if "DATE LADEN ON BOARD" in line:
                if i + 1 < len(lines):
                    row["ATD"] = lines[i + 1].strip()

        full_desc = self.extract_description_by_bbox(
            top_kw_list=['PARTICULARS', 'DESCRIPTION'],
            bottom_kw_list=['LIABILITY', 'VALOREM'],
            x_range=(210, 460),
            pages_to_read=data["pages_to_read"]
        )
        
        desc_match = re.search(r'(?i)(.*?TOTAL\s+[\d,.]+\s*(?:PCS|PIECES|PKGS|PACKAGES|CARTONS|UNITS|BOXES))', full_desc, flags=re.DOTALL)
        remaining_text = ""
        
        if desc_match:
            remaining_text = full_desc[desc_match.end():].strip()
            footer_keywords = ["LINE TARIFF", "DELIVERY OF THE CARGO", "PREJUDICE", "OCEAN NETWORK EXPRESS", "DECLARED CARGO VALUE", "FREIGHT & CHARGES"]
            for kw in footer_keywords:
                idx = remaining_text.upper().find(kw)
                if idx != -1:
                    remaining_text = remaining_text[:idx].strip()
        else:
            split_match = re.search(r'(SP>|SH>|CN>|NP>|ALSO\s+NOTIFY\s+PARTY)', full_desc, re.IGNORECASE)
            if split_match:
                split_idx = split_match.start()
                remaining_text = full_desc[split_idx:].strip()

        if remaining_text:
            tags_to_find = [
                (r'SP>|SH>', 'Shipper'),
                (r'CN>', 'Consignee'),
                (r'NP>', 'Notify party 1'),
                (r'ALSO\s+NOTIFY\s+PARTY\s*:?', 'Notify party 2')
            ]
            
            found_tags = []
            for pattern, field in tags_to_find:
                for m in re.finditer(pattern, remaining_text, re.IGNORECASE):
                    found_tags.append((m.start(), m.end(), field))
            
            found_tags.sort(key=lambda x: x[0])
            
            for idx, (start_idx, end_idx, field) in enumerate(found_tags):
                next_start = found_tags[idx+1][0] if idx + 1 < len(found_tags) else len(remaining_text)
                content = remaining_text[end_idx:next_start].strip()
                content = re.sub(r'(?m)^[-_]{3,}.*$', '', content).strip()
                if content:
                    if row.get(field):
                        row[field] += "\n" + content
                    else:
                        row[field] = content

    def extract_description(self, pdf):
        data = self._parse_all(pdf)
        if not data.get("full_text"): return ""
        
        full_desc = self.extract_description_by_bbox(
            top_kw_list=['PARTICULARS', 'DESCRIPTION'],
            bottom_kw_list=['LIABILITY', 'VALOREM'],
            x_range=(210, 460),
            pages_to_read=data["pages_to_read"]
        )
        
        desc_match = re.search(r'(?i)(.*?TOTAL\s+[\d,.]+\s*(?:PCS|PIECES|PKGS|PACKAGES|CARTONS|UNITS|BOXES))', full_desc, flags=re.DOTALL)
        true_desc = full_desc
        
        if desc_match:
            true_desc = desc_match.group(1).strip()
            true_desc = re.sub(r'(?i)\**\s*TO BE CONTINUED ON ATTACHED LIST\s*\**', '', true_desc).strip()
        else:
            split_match = re.search(r'(SP>|SH>|CN>|NP>|ALSO\s+NOTIFY\s+PARTY)', full_desc, re.IGNORECASE)
            if split_match:
                split_idx = split_match.start()
                true_desc = full_desc[:split_idx].strip()
            true_desc = re.sub(r'(?i)\**\s*TO BE CONTINUED ON ATTACHED LIST\s*\**', '', true_desc).strip()

        full_desc = re.sub(r'(?m)^[-_]{3,}.*$', '', true_desc).strip()
        return full_desc

    def extract_footers(self, pdf, row):
        data = self._parse_all(pdf)
        if data.get("remarks_extracted"):
            row["Remark"] = "\n".join(data["remarks_extracted"])

    def extract_containers(self, pdf):
        data = self._parse_all(pdf)
        if not data.get("full_text"): return []
        
        lines = data["full_text"].split('\n')
        in_cargo = False
        conts = []
        
        for line in lines:
            if "PARTICULARS DECLARED BY SHIPPER" in line or ("DESCRIPTION OF GOODS" in line and "GROSS WEIGHT" in line):
                in_cargo = True
                continue
            if not in_cargo: continue

            stop_keywords = [
                "Declared Cargo Value", "FREIGHT & CHARGES", "OCEAN FREIGHT COLLECT",
                "DESTINATION CHARGES COLLECT", "SIGNED", "Ocean Network Express",
                "(ONE), AS CARRIER", "DATE CARGO RECEIVED"
            ]
            if any(kw in line for kw in stop_keywords):
                in_cargo = False
                continue

            if re.match(r'\s*-{10,}', line):
                continue

            if re.match(r'\s*[A-Z]{4}[0-9]{7}\s*/', line):
                parts = [p.strip() for p in line.split('/')]
                cont = {}
                cont["Cont no."] = re.search(r'[A-Z]{4}[0-9]{7}', parts[0]).group(0) if re.search(r'[A-Z]{4}[0-9]{7}', parts[0]) else parts[0].strip()
                if len(parts) > 1: cont["Seal no."] = parts[1]
                if len(parts) > 2: cont["Total carton"] = parts[2].strip()

                for p in parts:
                    p_up = p.upper()
                    type_match = re.search(r'(40HQ|20GP|40GP|45HQ|20RF|40RF|OT|FR|20HC|40HC)', p_up)
                    if type_match: cont["Cont type"] = type_match.group(1)
                    gw_match = re.search(r'([\d.,]+)\s*KGS', p_up)
                    if gw_match: cont["Total GW"] = gw_match.group(1)
                    cbm_match = re.search(r'([\d.,]+)\s*(M3|CBM)', p_up)
                    if cbm_match: cont["Total CBM"] = cbm_match.group(1)

                conts.append(cont)
                
        return conts
