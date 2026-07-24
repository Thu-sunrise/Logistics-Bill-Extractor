import pdfplumber
import re
from .base_extractor import BaseExtractor

class KnExtractor(BaseExtractor):

    @classmethod
    def is_match(cls, text_upper):
        return 'BLUE ANCHOR LINE' in text_upper or 'KUEHNE' in text_upper or 'K&N' in text_upper

    def __init__(self, pdf_path):
        super().__init__(pdf_path)
        self.carrier_name = "K&N"
        self._parsed_data = None

    def _parse_all(self, pdf):
        if self._parsed_data: return self._parsed_data
        
        data = {}
        containers = []
        desc_lines = []
        total_gw = ""
        total_cbm = ""
        total_carton = ""
        
        if not pdf.pages:
            self._parsed_data = {"data": data, "containers": containers, "description": "", "total_gw": "", "total_cbm": "", "total_carton": ""}
            return self._parsed_data
            
        p1 = pdf.pages[0]
        
        # Headers from page 1
        s_text = self.extract_dynamic_left_block(p1, "Shipper", "Consignee", x_max=300)
        if s_text:
            s_lines = []
            for l in s_text.split('\n'):
                if "Shipper" in l: continue
                if "Consignee" in l: break
                s_lines.append(l)
            data["Shipper"] = "\n".join(s_lines).strip()
            
        c_text = self.extract_dynamic_left_block(p1, "Consignee", "Notify", x_max=300)
        if c_text:
            c_lines = []
            for l in c_text.split('\n'):
                if "Consignee" in l or "order of" in l.lower(): continue
                if "Notify" in l: break
                c_lines.append(l)
            data["Consignee"] = "\n".join(c_lines).strip()
            
        n_text = self.extract_dynamic_left_block(p1, "Notify", "Receipt", x_max=300)
        if n_text:
            n_lines = []
            for l in n_text.split('\n'):
                if "Notify" in l or "liability shall" in l or "Clause 14" in l: continue
                if "Receipt" in l or "Vessel" in l: break
                n_lines.append(l)
            data["Notify party 1"] = "\n".join(n_lines).strip()
        
        notify_word = self.find_word_bbox(p1, "Notify Party 2", x_range=(p1.width/2, p1.width))
        deliv_agent = self.find_word_bbox(p1, "Delivery Agent", x_range=(p1.width/2, p1.width))
        if notify_word and deliv_agent:
            bbox = (notify_word['x0'], notify_word['bottom'], p1.width, deliv_agent['top'])
            n2_text = p1.crop(bbox).extract_text()
            if n2_text: data["Notify party 2"] = n2_text.strip()
            
        vessel_word = self.find_word_bbox(p1, "Vessel", x_range=(0, p1.width/2))
        voy_word = self.find_word_bbox(p1, "Voyage", x_range=(0, p1.width/2))
        if vessel_word and voy_word:
            bbox_vessel = (vessel_word['x0'], vessel_word['bottom'] + 2, voy_word['x0'] - 2, vessel_word['bottom'] + 30)
            v_text = p1.crop(bbox_vessel).extract_text()
            if v_text: data["Vessel name"] = v_text.strip().split('\n')[0]
            
            bbox_voy = (voy_word['x0'], voy_word['bottom'] + 2, p1.width/2, voy_word['bottom'] + 30)
            voy_text = p1.crop(bbox_voy).extract_text()
            if voy_text: data["Voyage number"] = voy_text.strip().split('\n')[0]
            
        pol_word = self.find_word_bbox(p1, "Loading", x_range=(p1.width/2, p1.width))
        if pol_word:
            bbox_pol = (pol_word['x0'] - 20, pol_word['bottom'] + 2, p1.width, pol_word['bottom'] + 30)
            pol_text = p1.crop(bbox_pol).extract_text()
            if pol_text: 
                pol_str = pol_text.strip().split('\n')[0]
                pol_str = re.sub(r'(?i)B/L\s*No.*|Waybill.*', '', pol_str).strip()
                data["POL"] = pol_str
                
        pod_word = self.find_word_bbox(p1, "Discharge", x_range=(0, p1.width/2))
        if pod_word:
            bbox_pod = (pod_word['x0'] - 20, pod_word['bottom'] + 2, p1.width/2, pod_word['bottom'] + 30)
            pod_text = p1.crop(bbox_pod).extract_text()
            if pod_text: data["POD"] = pod_text.strip().split('\n')[0]
            
        deliv_word = self.find_word_bbox(p1, "Delivery", x_range=(100, 250))
        if deliv_word:
            bbox_del = (deliv_word['x0'] - 20, deliv_word['bottom'] + 2, p1.width, deliv_word['bottom'] + 30)
            del_text = p1.crop(bbox_del).extract_text()
            if del_text: data["Place of delivery"] = del_text.strip().split('\n')[0]
            
        payable_word = self.find_word_bbox(p1, "Payable", x_range=(p1.width/2, p1.width))
        if payable_word:
            bbox_freight = (payable_word['x0'] - 20, payable_word['bottom'], p1.width, payable_word['bottom'] + 20)
            freight_text = p1.crop(bbox_freight).extract_text()
            if freight_text:
                freight_str = freight_text.strip().split('\n')[0].upper()
                if "TION" in freight_str or "DEST" in freight_str:
                    data["Freight"] = "FREIGHT COLLECT"
                elif "GIN" in freight_str or "ORIG" in freight_str:
                    data["Freight"] = "FREIGHT PREPAID"
                else:
                    data["Freight"] = freight_str
            
        bl_word = self.find_word_bbox(p1, "Waybill-No.", x_range=(p1.width/2, p1.width))
        if not bl_word:
            bl_word = self.find_word_bbox(p1, "B/L", x_range=(p1.width/2, p1.width))
        if bl_word:
            bbox_bl = (bl_word['x0'] - 20, bl_word['bottom'] - 5, p1.width, bl_word['bottom'] + 30)
            bl_text = p1.crop(bbox_bl).extract_text()
            if bl_text:
                for line in bl_text.split('\n'):
                    match = re.search(r'\b[A-Z0-9]{8,15}\b', line)
                    if match and "WAYBILL" not in line.upper() and "B/L" not in line.upper():
                        data["Bill no."] = match.group(0)
                        break

        p1_text = p1.extract_text(layout=True)
        if not p1_text: p1_text = ""
        lines = p1_text.split('\n')
        
        for i, line in enumerate(lines):
            if "Place and date of issue:" in line or "HO CHI MINH CITY" in line:
                match = re.search(r'(\d{2}\.\d{2}\.\d{4})', line)
                if match: data["ATD"] = match.group(1)
                
            if "OCEANFREIGHT AND CHARGES" in line:
                if "Prepaid" in line and "Collect" in line:
                    if re.search(r'Prepaid\s+X', line, re.IGNORECASE) or re.search(r'X\s+Prepaid', line, re.IGNORECASE):
                        data["Freight"] = "FREIGHT PREPAID"
                    elif re.search(r'Collect\s+X', line, re.IGNORECASE) or re.search(r'X\s+Collect', line, re.IGNORECASE):
                        data["Freight"] = "FREIGHT COLLECT"

        ocean_word = self.find_word_bbox(p1, "OCEANFREIGHT", x_range=(0, p1.width/2))
        if ocean_word and not data.get("Freight"):
            bbox_fr = (ocean_word['x0'], ocean_word['bottom'], p1.width/2, p1.height)
            fr_text = p1.crop(bbox_fr).extract_text()
            if fr_text:
                if re.search(r'\bPrepaid\b', fr_text, re.IGNORECASE): data["Freight"] = "FREIGHT PREPAID"
                elif re.search(r'\bCollect\b', fr_text, re.IGNORECASE): data["Freight"] = "FREIGHT COLLECT"

        # Initialize fallback coordinates from page 1 headers
        p1_marks = self.find_word_bbox(p1, "Marks", x_range=(0, 200))
        p1_desc = self.find_word_bbox(p1, "Description", x_range=(200, 500))
        p1_wght = self.find_word_bbox(p1, "Weight", x_range=(400, p1.width))
        p1_vol = self.find_word_bbox(p1, "Measurement", x_range=(500, p1.width))

        desc_x0, desc_x1 = 300, 500
        cont_x0, cont_x1 = 0, 200
        type_x0, type_x1 = 200, 300
        wght_x0, wght_x1 = 500, 600
        vol_x0 = 600
        
        if p1_marks and p1_desc:
            # Dịch tọa độ chiều rộng của description sang trái
            desc_x0 = p1_desc['x0'] - 50
            desc_x1 = p1_wght['x0'] - 10 if p1_wght else p1.width - 150
            cont_x0 = p1_marks['x0'] - 10
            cont_x1 = desc_x0
            type_x0 = desc_x0
            type_x1 = desc_x0
            wght_x0 = p1_wght['x0'] - 10 if p1_wght else p1.width - 150
            wght_x1 = p1_vol['x0'] - 10 if p1_vol else p1.width - 80
            vol_x0 = p1_vol['x0'] - 10 if p1_vol else p1.width - 80

        stop_desc = False
        raw_desc_lines = []

        if len(pdf.pages) > 1:
            for page in pdf.pages[1:]:
                words = page.extract_words()
                page_text = page.extract_text()
                if page_text and "DEFINITIONS" in page_text and "Liability" in page_text:
                    continue

                marks_header = self.find_word_bbox(page, "MARKS", x_range=(0, 200))
                type_header = self.find_word_bbox(page, "TYPE", x_range=(200, 400))
                desc_header = self.find_word_bbox(page, "DESCRIPTION", x_range=(300, 600))
                wght_header = self.find_word_bbox(page, "WGHT", x_range=(500, p1.width))
                vol_header = self.find_word_bbox(page, "VOL", x_range=(600, p1.width))
                
                start_y = 0
                if marks_header and desc_header:
                    start_y = marks_header['bottom']
                    desc_x0 = desc_header['x0'] - 20
                    desc_x1 = wght_header['x0'] - 10 if wght_header else p1.width - 150
                    cont_x0 = marks_header['x0'] - 10
                    cont_x1 = type_header['x0'] - 10 if type_header else 250
                    type_x0 = type_header['x0'] - 10 if type_header else 250
                    type_x1 = desc_x0
                    wght_x0 = wght_header['x0'] - 10 if wght_header else p1.width - 150
                    wght_x1 = vol_header['x0'] - 10 if vol_header else p1.width - 80
                    vol_x0 = vol_header['x0'] - 10 if vol_header else p1.width - 80
                else:
                    attach_word = self.find_word_bbox(page, "ATTACHMENT", x_range=(0, 200))
                    if not attach_word: 
                        continue
                    date_word = self.find_word_bbox(page, "202", x_range=(p1.width/2, p1.width))
                    start_y = date_word['bottom'] + 10 if date_word else 150

                lines_grouped = {}
                for w in words:
                    if w['top'] >= start_y:
                        matched_y = None
                        for y in lines_grouped.keys():
                            if abs(y - w['top']) < 4:
                                matched_y = y
                                break
                        if matched_y is None:
                            matched_y = w['top']
                            lines_grouped[matched_y] = []
                        lines_grouped[matched_y].append(w)
                
                for y in sorted(lines_grouped.keys()):
                    line_words = sorted(lines_grouped[y], key=lambda x: x['x0'])
                    
                    cont_text = " ".join(w['text'] for w in line_words if cont_x0 <= (w['x0']+w['x1'])/2 <= cont_x1).strip()
                    type_text = " ".join(w['text'] for w in line_words if type_x0 <= (w['x0']+w['x1'])/2 <= type_x1).strip()
                    desc_text = " ".join(w['text'] for w in line_words if desc_x0 <= (w['x0']+w['x1'])/2 <= desc_x1).strip()
                    wght_text = " ".join(w['text'] for w in line_words if wght_x0 <= (w['x0']+w['x1'])/2 <= wght_x1).strip()
                    vol_text = " ".join(w['text'] for w in line_words if vol_x0 <= (w['x0']+w['x1'])/2).strip()
                    
                    full_line = " ".join(w['text'] for w in line_words).strip().upper()
                            
                    if full_line.startswith("TOTAL") and wght_text and vol_text:
                        # Extract directly using regex on full line to avoid coordinate shifts
                        t_match = re.search(r'([\d\.,]+)\s+([\d\.,]+)', " ".join(w['text'] for w in line_words).strip())
                        if t_match:
                            total_gw = t_match.group(1)
                            total_cbm = t_match.group(2)
                        else:
                            total_gw = wght_text
                            total_cbm = vol_text
                        continue
                            
                    cont_match = re.search(r'[A-Z]{4}\d{7}', cont_text)
                    if cont_match:
                        current_cont = {
                            "Cont no.": cont_match.group(0),
                            "Cont type": type_text,
                            "Total GW": wght_text,
                            "Total CBM": vol_text
                        }
                        if not current_cont.get("Cont type"):
                            type_match = re.search(r"\b(20|40|45)\s*'?(?:\s*(?:HC|ST|OT|FR|RF)\b)|\b(20|40|45)\s*'\b", full_line, re.IGNORECASE)
                            if type_match:
                                current_cont["Cont type"] = type_match.group(0).strip()
                        containers.append(current_cont)
                    elif cont_text.upper().startswith("SEAL:"):
                        seal_match = re.search(r'SEAL:\s*([A-Za-z0-9]+)', cont_text, re.IGNORECASE)
                        if seal_match and containers:
                            containers[-1]["Seal no."] = seal_match.group(1)
                                
                    if desc_text:
                        carton_match = re.search(r'^(\d+)\s*CARTON\(S\)', desc_text, re.IGNORECASE)
                        if carton_match:
                            if containers: containers[-1]["Total carton"] = carton_match.group(1)
                            total_carton = carton_match.group(1)
                        raw_desc_lines.append(desc_text)
                            
        # Post-process description
        start_idx = 0
        end_idx = len(raw_desc_lines)
        for i, line in enumerate(raw_desc_lines):
            line_up = line.upper()
            if "CARTON(S)" in line_up or "CONTAINER SAID TO CONTAIN" in line_up:
                start_idx = i + 1
            if "ALL MENTIONED CONTAINERS" in line_up or "FREIGHT COLLECT" in line_up or "SHIPPER'S LOAD" in line_up:
                if i < end_idx: end_idx = i
                
        final_desc_lines = [l for l in raw_desc_lines[start_idx:end_idx] if l.strip() and l.strip() != "N/M"]
        
        self._parsed_data = {
            "data": data,
            "containers": containers,
            "description": "\n".join(final_desc_lines).strip(),
            "total_gw": total_gw,
            "total_cbm": total_cbm,
            "total_carton": total_carton
        }
        return self._parsed_data

    def extract_headers(self, pdf, row):
        parsed = self._parse_all(pdf)
        data = parsed["data"]
        for k in ["Shipper", "Consignee", "Notify party 1", "Notify party 2", "Booking", "Bill no.", "Vessel name", "Voyage number", "POL", "POD", "Place of delivery", "ATD", "Freight"]:
            if data.get(k): row[k] = data[k]

    def extract_description(self, pdf):
        parsed = self._parse_all(pdf)
        return parsed["description"]

    def extract_footers(self, pdf, row):
        parsed = self._parse_all(pdf)
        if parsed.get("total_gw"): row["Total GW"] = parsed["total_gw"]
        if parsed.get("total_cbm"): row["Total CBM"] = parsed["total_cbm"]
        if parsed.get("total_carton"): row["Total carton"] = parsed["total_carton"]

    def extract_containers(self, pdf):
        parsed = self._parse_all(pdf)
        return parsed["containers"]
