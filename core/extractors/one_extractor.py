import re
import pdfplumber
from .base_extractor import BaseExtractor

class OneExtractor(BaseExtractor):
    def __init__(self, pdf_path):
        super().__init__(pdf_path)
        self.carrier_name = "ONE"

    def extract(self):
        """Extracts data from ONE bills of lading, supporting multi-page descriptions."""
        
        with pdfplumber.open(self.pdf_path) as pdf:
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

            # 1. Left blocks (Shipper, Consignee, Notify)
            first_page = pdf.pages[0]
            data = self.get_empty_row()
            data["Shipper"] = self.extract_dynamic_left_block(first_page, "SHIPPER", "CONSIGNEE")
            data["Consignee"] = self.extract_dynamic_left_block(first_page, "CONSIGNEE", "NOTIFY")
            data["Notify party 1"] = self.extract_dynamic_left_block(first_page, "NOTIFY", ["PRE-CARRIAGE", "OCEAN"])
            
            # 5. Remarks: Use find_word_bbox to find exact Y anchor
            try:
                target_page = pdf.pages[-1]
                # Find the words "OCEAN" and "DESTINATION" on the last page (left column, x < 200)
                ocean_word = self.find_word_bbox(target_page, "OCEAN", x_range=(0, 200))
                dest_word = self.find_word_bbox(target_page, "DESTINATION", x_range=(0, 200))
                if ocean_word and dest_word:
                    remark_bbox = (0, ocean_word['bottom'] + 2, 200, dest_word['top'] - 2)
                    cropped = target_page.crop(remark_bbox)
                    remark_raw = cropped.extract_text(layout=True)
                    if remark_raw:
                        data["Remark"] = "\n".join(
                            l.strip() for l in remark_raw.split('\n') if l.strip()
                        )
            except Exception:
                pass

        lines = full_text.split('\n')
        
        # Cleanup SH> in Shipper
        if data["Shipper"]:
            data["Shipper"] = data["Shipper"].replace("SH>", "").strip()

        # 2. Vessel, Voyage, POL, POD, ATD, Booking, Bill no.
        for i, line in enumerate(lines):
            if "BOOKING NO" in line and ("WAYBILL NO" in line or "B/L NO" in line):
                if i + 1 < len(lines):
                    parts = lines[i + 1].split()
                    if len(parts) >= 2:
                        data["Bill no."] = parts[-1].strip()
                        data["Booking"] = parts[-2].strip()
                        
            if "OCEAN VESSEL" in line and "VOYAGE" in line and "PORT OF LOADING" in line:
                if i + 1 < len(lines):
                    val = lines[i + 1].replace("Vessel & Voy", "").strip()
                    vessel_voyage, pol = self.split_columns_by_spaces(val)
                    vessel_name, voyage_number, rest = self.parse_vessel_voyage(vessel_voyage)
                    
                    data["POL"] = pol or rest
                    data["Vessel name"] = vessel_name
                    data["Voyage number"] = voyage_number
                    
            if "PORT OF DISCHARGE" in line and "PLACE OF DELIVERY" in line:
                if i + 1 < len(lines):
                    data["POD"], data["Place of delivery"] = self.split_columns_by_spaces(lines[i + 1])

            if "DATE LADEN ON BOARD" in line:
                if i + 1 < len(lines):
                    data["ATD"] = lines[i + 1].strip()

        # 3. Container & Gross Weight (Specific to ONE)
        in_cargo  = False
        conts     = []
        
        for line in lines:
            if "PARTICULARS DECLARED BY SHIPPER" in line or ("DESCRIPTION OF GOODS" in line and "GROSS WEIGHT" in line):
                in_cargo = True
                continue

            if not in_cargo:
                continue

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
                cont = {col: "" for col in ["Cont no.", "Seal no.", "Total carton", "Cont type", "Total GW", "Total CBM"]}
                cont["Cont no."] = re.search(r'[A-Z]{4}[0-9]{7}', parts[0]).group(0) if re.search(r'[A-Z]{4}[0-9]{7}', parts[0]) else parts[0].strip()
                if len(parts) > 1: cont["Seal no."]    = parts[1]
                if len(parts) > 2: cont["Total carton"] = parts[2].strip()

                for p in parts:
                    p_up = p.upper()
                    type_match = re.search(r'(40HQ|20GP|40GP|45HQ|20RF|40RF|OT|FR|20HC|40HC)', p_up)
                    if type_match:
                        cont["Cont type"] = type_match.group(1)
                    gw_match = re.search(r'([\d.,]+)\s*KGS', p_up)
                    if gw_match:
                        cont["Total GW"] = gw_match.group(1)
                    cbm_match = re.search(r'([\d.,]+)\s*(M3|CBM)', p_up)
                    if cbm_match:
                        cont["Total CBM"] = cbm_match.group(1)

                conts.append(cont)

        # 4. Description (Bounding Box via BaseExtractor)
        full_desc = self.extract_description_by_bbox(
            top_kw_list=['PARTICULARS', 'DESCRIPTION'],
            bottom_kw_list=['FREIGHT', 'DECLARED', 'OCEAN', 'DESTINATION', 'SIGNED', 'CONTINUED'],
            x_range=(210, 460),
            pages_to_read=pages_to_read
        )
        
        # Filter Continuous Shipper info from Description by dynamically zoning the Y-gap
        for i in range(pages_to_read):
            page = pdf.pages[i]
            words = page.extract_words()
            desc_words = [w for w in words if 210 <= (w['x0']+w['x1'])/2 <= 460]
            line_words = self.group_words_by_y(desc_words)
            tops = sorted(line_words.keys())
            
            shipper_start_top = None
            shipper_end_top = None
            for j, top in enumerate(tops):
                text = ' '.join(w['text'] for w in sorted(line_words[top], key=lambda x: x['x0']))
                if "SH>" in text or "TAX IDENTIFICATION" in text:
                    if shipper_start_top is None:
                        shipper_start_top = top
                
                if shipper_start_top is not None:
                    if j + 1 < len(tops):
                        next_top = tops[j+1]
                        if next_top - top > 15: # Y-gap > 15 pixels (white space)
                            shipper_end_top = top
                            break
                    else:
                        shipper_end_top = top
            
            if shipper_start_top is not None and shipper_end_top is not None:
                shipper_lines = []
                for top in tops:
                    if shipper_start_top <= top <= shipper_end_top:
                        text = ' '.join(w['text'] for w in sorted(line_words[top], key=lambda x: x['x0']))
                        text = re.sub(r'\s+', ' ', text).strip()
                        shipper_lines.append(text)
                
                cont_shipper = "\n".join(shipper_lines)
                if data["Shipper"]:
                    data["Shipper"] += "\n" + cont_shipper
                else:
                    data["Shipper"] = cont_shipper
                    
                # Remove the shipper part from full_desc
                for line in shipper_lines:
                    full_desc = full_desc.replace(line, "").strip()
                    
        notify_match = re.search(r'((?:ALSO\s+)?NOTIFY\s+PARTY\s*:)', full_desc, re.IGNORECASE)
        if notify_match:
            notify_2_idx = notify_match.start()
            notify_2_text = full_desc[notify_2_idx:].replace(notify_match.group(1), "").strip()
            data["Notify party 2"] = re.sub(r'(?m)^[-_]{3,}.*$', '', notify_2_text).strip()
            full_desc = full_desc[:notify_2_idx].strip()
            
        full_desc = re.sub(r'(?m)^[-_]{3,}.*$', '', full_desc).strip()

        if not conts:
            conts.append({})

        results = []
        for c in conts:
            row = data.copy()
            row.update(c)
            row["Description"] = full_desc
            results.append(row)

        return results
