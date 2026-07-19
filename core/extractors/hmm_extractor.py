import re
import pdfplumber
from .base_extractor import BaseExtractor

class HmmExtractor(BaseExtractor):
    def __init__(self, pdf_path):
        super().__init__(pdf_path)
        self.carrier_name = "HMM"

    def extract(self):
        row = self.get_empty_row()
        with pdfplumber.open(self.pdf_path) as pdf:
            if not pdf.pages: return [row]
            p1 = pdf.pages[0]
            
            # Party Info (Left column is up to x=280)
            s = self.extract_dynamic_left_block(p1, 'SHIPPER/EXPORTER', 'CONSIGNEE', x_min=0, x_max=280)
            row["Shipper"] = re.sub(r'^(Shipper/Exporter\(complete name and address\)|Shipper).*?\n', '', s, flags=re.IGNORECASE).strip()
            
            c = self.extract_dynamic_left_block(p1, 'CONSIGNEE', 'NOTIFY', x_min=0, x_max=280)
            row["Consignee"] = re.sub(r'^(Consignee\(complete name and address\)|Consignee).*?\n', '', c, flags=re.IGNORECASE).strip()
            
            n1 = self.extract_dynamic_left_block(p1, 'NOTIFY', 'PRE-CARRIAGE', x_min=0, x_max=280)
            row["Notify party 1"] = re.sub(r'^(Notify Party\(complete name and address\)|Notify).*?\n', '', n1, flags=re.IGNORECASE).strip()
            
            # ATD via regex on normal text
            text = p1.extract_text()
            atd = re.search(r'(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\.\s*\d{1,2},\s*\d{4}', text, re.IGNORECASE)
            if atd: row["ATD"] = atd.group(0).upper()
            
            # Routing, Booking, Vessel via layout text
            layout_text = p1.extract_text(layout=True)
            if layout_text:
                lines = layout_text.split('\n')
                for i, line in enumerate(lines):
                    # Booking and B/L No
                    # Booking and B/L No
                    if 'Booking No.' in line and 'B/L No.' in line:
                        b_col = line.find('Booking No.')
                        bl_col = line.find('B/L No.')
                        
                        # First try to extract from the same line (e.g. Booking No. US2525133)
                        bk_match = re.search(r'Booking No\.\s*([A-Z0-9]+)', line)
                        b_val = bk_match.group(1) if bk_match else ""
                        bl_val = ""
                        
                        # Fallback to next line for both, but especially for B/L No which is often on next line
                        if i + 1 < len(lines):
                            b_start = max(0, b_col - 5)
                            bl_start = max(0, bl_col - 5)
                            if not b_val:
                                b_val = lines[i+1][b_start:bl_start].strip()
                                
                            bl_val_next = lines[i+1][bl_start:].strip()
                            if bl_val_next:
                                bl_val = bl_val_next
                            else:
                                bl_match = re.search(r'B/L No\.\s*([A-Z0-9]+)', line)
                                if bl_match:
                                    bl_val = bl_match.group(1)
                                
                        row["Booking"] = b_val
                        row["Bill no."] = bl_val

                    # Routing
                    if 'Pre-Carriage by' in line and 'Place of Receipt' in line and 'Port of Discharge' in line:
                        por_idx = line.find('Place of Receipt')
                        pod_idx = line.find('Port of Discharge')
                        if i + 1 < len(lines):
                            next_line = lines[i+1]
                            for p in re.split(r'\s{2,}', next_line.strip()):
                                p_idx = next_line.find(p)
                                if p_idx < por_idx - 10:
                                    pass # Pre-carriage value
                                elif p_idx < pod_idx - 10:
                                    row["POR"] = p
                                else:
                                    row["POD"] = p
                            
                    if 'Ocean Vessel' in line and 'Port of Loading' in line and 'Place of Delivery' in line:
                        pol_idx = line.find('Port of Loading')
                        del_idx = line.find('Place of Delivery')
                        if i + 1 < len(lines):
                            next_line = lines[i+1]
                            for p in re.split(r'\s{2,}', next_line.strip()):
                                p_idx = next_line.find(p)
                                if p_idx < pol_idx - 10:
                                    v_text = p
                                    v, voy, _ = self.parse_vessel_voyage(v_text)
                                    row["Vessel name"] = v
                                    row["Voyage number"] = voy
                                elif p_idx < del_idx - 10:
                                    row["POL"] = p
                                else:
                                    row["Place of delivery"] = p

            # Cont no. and Seal no. via regex on full text
            text = p1.extract_text()
            cont_matches = re.findall(r'([A-Z]{4}\d{7})\s*/\s*([A-Za-z0-9]+)', text)
            if cont_matches:
                row["Cont no."] = cont_matches[0][0]
                row["Seal no."] = cont_matches[0][1]
                
            # Description, Cont type, and Remarks
            dc_word = None
            total_word_p1 = None
            for w in p1.extract_words():
                if w['text'] == 'CONTAINER' and 300 < w['top'] < 450:
                    dc_word = w
                if w['text'] == 'TOTAL' and 400 < w['top'] < 600:
                    total_word_p1 = w
                    break
                    
            rmk = []
            d_lines = []
            
            def extract_from_page(page, y_start, y_end):
                cols = self.extract_columns_by_x_ranges(
                    page,
                    col_x_ranges={'Remark': (0, 110), 'Desc': (114, 380)},
                    y_range=(y_start, y_end)
                )
                for r in cols:
                    r_text = r.get('Remark', '').strip()
                    d_text = r.get('Desc', '').strip()
                    
                    if r_text:
                        if row.get("Cont no.") and row["Cont no."] in r_text: pass
                        else: rmk.append(r_text)
                        
                    if d_text and not re.search(r'DC CONTAINER', d_text): 
                        if not re.match(r'^(HDMU|SGNM\d+|Page \d+)', d_text):
                            if row.get("Seal no.") and row["Seal no."] in d_text: pass
                            else: d_lines.append(d_text)

            if dc_word:
                if total_word_p1:
                    extract_from_page(p1, dc_word['top'] - 2, total_word_p1['bottom'] + 2)
                else:
                    t_word_p1 = self.find_word_bbox(p1, 'TOTAL', x_range=(0, p1.width))
                    if t_word_p1:
                        extract_from_page(p1, dc_word['top'] - 2, t_word_p1['top'] - 2)
                    
                    if len(pdf.pages) > 1:
                        p2 = pdf.pages[1]
                        total_word_p2 = None
                        for w in p2.extract_words():
                            if w['text'] == 'TOTAL':
                                total_word_p2 = w
                                break
                        if total_word_p2:
                            extract_from_page(p2, 0, total_word_p2['bottom'] + 2)
                            
                # Filter out PART OF and anything above it
                if any("PART OF" in r for r in rmk):
                    new_rmk = []
                    found = False
                    for line in rmk:
                        if found:
                            new_rmk.append(line)
                        elif "PART OF" in line:
                            found = True
                    rmk = new_rmk
                            
                row["Remark"] = "\n".join(rmk)
                row["Description"] = "\n".join(d_lines)
                    
            # Extract Cont type from original text separately
            m_word = self.find_word_bbox(p1, 'MARKS', x_range=(0, p1.width))
            if m_word:
                c_bbox = (0, m_word['bottom'] + 2, p1.width, m_word['bottom'] + 100)
                c_text = self.extract_text_by_bbox(p1, c_bbox)
                for line in c_text.split('\n'):
                    if 'DC CONTAINER' in line or re.search(r"\d+\s*X\s*\d+'[A-Z]+", line):
                        m = re.search(r"(\d+\s*X\s*\d+'[A-Z]+)", line)
                        if m: 
                            row["Cont type"] = m.group(1)
                        break
                
            # Totals
            gw_word = self.find_word_bbox(p1, 'GROSS')
            m_meas_word = self.find_word_bbox(p1, 'MEASUREMENT')
            if gw_word and m_meas_word:
                tot_text = self.extract_text_by_bbox(p1, (gw_word['x0'] - 20, gw_word['bottom'], p1.width, gw_word['bottom'] + 50))
                for line in tot_text.split('\n'):
                    line = line.strip()
                    if 'KGS' in line or 'CBM' in line or re.search(r'\d+\.\d+', line):
                        parts = line.split()
                        nums = [p for p in parts if re.match(r'^\d+\.\d+$', p)]
                        if len(nums) >= 1: row["Total GW"] = nums[0] + " KGS"
                        if len(nums) >= 2: row["Total CBM"] = nums[1] + " CBM"
                        
            # Multi-page Notify Party
            if len(pdf.pages) > 1:
                p2 = pdf.pages[1]
                # Crop header from page 2 to avoid capturing Bill No on page 2
                p2_cropped = p2.crop((0, 80, p2.width, p2.height))
                p2_text = p2_cropped.extract_text(layout=True)
                if p2_text:
                    n2_idx = p2_text.find('NOTIFY PARTY 2:')
                    n3_idx = p2_text.find('NOTIFY PARTY 3:')
                    
                    plus_idx = p2_text.find('+')
                    if plus_idx != -1 and (n2_idx == -1 or plus_idx < n2_idx):
                        plus_text = p2_text[plus_idx:n2_idx if n2_idx != -1 else len(p2_text)]
                        # Extract lines starting with + and following lines
                        plus_lines = [l.strip() for l in plus_text.split('\n') if l.strip()]
                        # Remove the first + sign if it exists alone or in text
                        if plus_lines and plus_lines[0] == '+':
                            plus_lines.pop(0)
                        elif plus_lines and plus_lines[0].startswith('+'):
                            plus_lines[0] = plus_lines[0][1:].strip()
                            
                        # Remove + from row["Notify party 1"]
                        if row["Notify party 1"].endswith('+'):
                            row["Notify party 1"] = row["Notify party 1"][:-1].strip()
                            
                        row["Notify party 1"] += "\n" + "\n".join(plus_lines)
                        row["Notify party 1"] = row["Notify party 1"].strip()
                        
                    if n2_idx != -1:
                        n2_text = p2_text[n2_idx:n3_idx if n3_idx != -1 else len(p2_text)]
                        n2_lines = [l.strip() for l in re.sub(r'^NOTIFY PARTY 2:\s*', '', n2_text).split('\n') if l.strip()]
                        row["Notify party 2"] = "\n".join(n2_lines)
                    if n3_idx != -1:
                        n3_text = p2_text[n3_idx:]
                        n3_lines = [l.strip() for l in re.sub(r'^NOTIFY PARTY 3:\s*', '', n3_text).split('\n') if l.strip() and not re.match(r'^Page\s+\d+\s+of\s+\d+', l.strip(), re.IGNORECASE)]
                        row["Notify party 3"] = "\n".join(n3_lines)

            return [row]
