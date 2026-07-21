from .base_extractor import BaseExtractor
import pdfplumber
import re

class CmaCgmExtractor(BaseExtractor):
    def __init__(self, pdf_path):
        super().__init__(pdf_path)
        self.carrier_name = "CMA CGM"

    def _build_lines(self, words, tolerance=4):
        lines = []
        words = sorted(words, key=lambda w: (w['top'], w['x0']))
        for w in words:
            added = False
            for line in lines:
                if abs(line['top'] - w['top']) <= tolerance:
                    line['words'].append(w)
                    line['top'] = min(line['top'], w['top'])
                    added = True
                    break
            if not added:
                lines.append({'top': w['top'], 'words': [w]})
        result = []
        for line in lines:
            line['words'].sort(key=lambda w: w['x0'])
            text = " ".join([w['text'] for w in line['words']])
            result.append({'top': line['top'], 'text': text})
        return result

    def find_phrase_bbox(self, page, phrase):
        words = page.extract_words()
        target_words = phrase.upper().split()
        for i in range(len(words) - len(target_words) + 1):
            match = True
            for j, tw in enumerate(target_words):
                if tw not in words[i+j]['text'].upper():
                    match = False
                    break
            if match:
                if abs(words[i]['top'] - words[i+len(target_words)-1]['top']) < 5:
                    return {
                        'x0': words[i]['x0'],
                        'x1': words[i+len(target_words)-1]['x1'],
                        'top': min(w['top'] for w in words[i:i+len(target_words)]),
                        'bottom': max(w['bottom'] for w in words[i:i+len(target_words)])
                    }
        return None

    def get_cell_bounds(self, page, word_bbox):
        if not word_bbox:
            return 0, page.width
        v_lines = [e['x0'] for e in page.edges if e['width'] < 2 and e['top'] <= word_bbox['bottom'] and e['bottom'] >= word_bbox['top']]
        v_lines = sorted(set(v_lines))
        
        left_bound = 0
        right_bound = page.width
        
        for x in v_lines:
            if x < word_bbox['x0'] - 2:
                left_bound = max(left_bound, x)
            elif x > word_bbox['x1'] + 2:
                right_bound = min(right_bound, x)
        
        return left_bound + 1, right_bound - 1

    def extract(self):
        row = self.get_empty_row()
        rows = []

        with pdfplumber.open(self.pdf_path) as pdf:
            if not pdf.pages: return [row]
            
            p1 = pdf.pages[0]

            # 1. Voyage and Bill number
            voy_word = self.find_word_bbox(p1, 'VOYAGE', x_range=(400, p1.width))
            if voy_word:
                for w in p1.extract_words():
                    if w['top'] > voy_word['bottom'] and w['x0'] >= voy_word['x0'] - 20:
                        row["Voyage number"] = w['text']
                        break
                        
            waybill_word = self.find_word_bbox(p1, 'WAYBILL', x_range=(400, p1.width))
            if waybill_word:
                for w in p1.extract_words():
                    if w['top'] > waybill_word['bottom'] and w['x0'] >= waybill_word['x0'] - 20:
                        row["Bill no."] = w['text']
                        break

            # 2. Left block details
            s = self.extract_dynamic_left_block(p1, 'SHIPPER', 'CONSIGNEE', x_min=0, x_max=250)
            row["Shipper"] = re.sub(r'^SHIPPER:?\s*', '', s, flags=re.IGNORECASE).strip()
            
            c = self.extract_dynamic_left_block(p1, 'CONSIGNEE', 'NOTIFY', x_min=0, x_max=250)
            row["Consignee"] = re.sub(r'^CONSIGNEE:?\s*', '', c, flags=re.IGNORECASE).strip()
            
            n1 = self.extract_dynamic_left_block(p1, 'NOTIFY', 'PRE', x_min=0, x_max=250)
            n1_lines = [ln for ln in n1.split('\n') if 'NOTIFY' not in ln.upper() and 'Carrier not to be responsible' not in ln]
            row["Notify party 1"] = '\n'.join(n1_lines).strip()

            # 3. Ports and Vessel
            por_word = self.find_phrase_bbox(p1, 'PLACE OF RECEIPT')
            pol_word = self.find_phrase_bbox(p1, 'PORT OF LOADING')
            vessel_word = self.find_word_bbox(p1, 'VESSEL')
            pod_word = self.find_phrase_bbox(p1, 'PORT OF DISCHARGE')
            fpod_word = self.find_phrase_bbox(p1, 'FINAL PLACE OF DELIVERY')
            
            marks_word_p1 = self.find_word_bbox(p1, 'MARKS')
            
            if por_word and pol_word:
                x0, x1 = self.get_cell_bounds(p1, por_word)
                bbox = (x0, por_word['bottom'] + 2, x1, pol_word['top'] - 2)
                row["POR"] = self.extract_text_by_bbox(p1, bbox).strip()
            
            if vessel_word:
                x0, x1 = self.get_cell_bounds(p1, vessel_word)
                y1 = marks_word_p1['top'] - 2 if marks_word_p1 else vessel_word['bottom'] + 20
                if pod_word and abs(pod_word['top'] - vessel_word['top']) > 10:
                    y1 = pod_word['top'] - 2
                bbox = (x0, vessel_word['bottom'] + 2, x1, y1)
                row["Vessel name"] = self.extract_text_by_bbox(p1, bbox).strip()

            if pol_word:
                x0, x1 = self.get_cell_bounds(p1, pol_word)
                y1 = marks_word_p1['top'] - 2 if marks_word_p1 else pol_word['bottom'] + 20
                if fpod_word and abs(fpod_word['top'] - pol_word['top']) > 10:
                    y1 = fpod_word['top'] - 2
                bbox = (x0, pol_word['bottom'] + 2, x1, y1)
                row["POL"] = self.extract_text_by_bbox(p1, bbox).strip()

            if pod_word:
                x0, x1 = self.get_cell_bounds(p1, pod_word)
                y1 = marks_word_p1['top'] - 2 if marks_word_p1 else pod_word['bottom'] + 20
                bbox = (x0, pod_word['bottom'] + 2, x1, y1)
                row["POD"] = self.extract_text_by_bbox(p1, bbox).strip()

            if fpod_word:
                x0, x1 = self.get_cell_bounds(p1, fpod_word)
                y1 = marks_word_p1['top'] - 2 if marks_word_p1 else fpod_word['bottom'] + 20
                bbox = (x0, fpod_word['bottom'] + 2, x1, y1)
                row["Place of delivery"] = self.extract_text_by_bbox(p1, bbox).strip()

            # 4. Containers and Description
            current_cont = None
            desc_lines = []
            remark_lines = []
            in_remark = False
            
            for p_num, p in enumerate(pdf.pages):
                words = p.extract_words()
                
                # Find start of table
                marks_word = self.find_word_bbox(p, 'MARKS')
                top_y = marks_word['bottom'] + 15 if marks_word else 150
                if p_num > 0: 
                    top_y = marks_word['bottom'] + 15 if marks_word else 100
                
                # Find column boundaries dynamically
                _, left_split = self.get_cell_bounds(p, marks_word)
                if left_split >= p.width - 2: # Fallback if edges not found
                    kind_word = self.find_word_bbox(p, 'KIND')
                    left_split = kind_word['x0'] - 10 if kind_word else 130
                
                gross_word = self.find_word_bbox(p, 'GROSS')
                right_split, _ = self.get_cell_bounds(p, gross_word)
                if right_split <= 2: # Fallback if edges not found
                    right_split = gross_word['x0'] - 10 if gross_word else 450

                bottom_y = p.height - 50
                
                l_w, m_w, r_w = [], [], []
                for w in words:
                    if w['top'] < top_y or w['top'] > bottom_y: continue
                    if w['x0'] < left_split: l_w.append(w)
                    elif left_split <= w['x0'] < right_split: m_w.append(w)
                    else: r_w.append(w)
                
                # Left side: Marks, Container No, Seal No
                l_lines = self._build_lines(l_w)
                for i, ln in enumerate(l_lines):
                    t = ln['text']
                    
                    # Clean up random characters like 'C o n t n o .'
                    cont_match = re.search(r'([A-Z]{4}\s*?[0-9]{7})', t)
                    if cont_match:
                        if current_cont is not None:
                            rows.append(current_cont)
                        current_cont = self.get_empty_row()
                        # Copy common data
                        for k, v in row.items():
                            if k not in ["Cont no.", "Seal no.", "Cont type", "Total carton", "Total GW", "Tare", "Total CBM", "Description", "Remark", "Freight"]:
                                current_cont[k] = v
                                
                        current_cont["Cont no."] = cont_match.group(1).replace(' ', '')
                    
                    elif 'SEAL' in t.upper() and current_cont is not None:
                        current_cont["Seal no."] = t.replace('SEAL', '').strip()
                
                if current_cont is None:
                    current_cont = row
                
                # Middle side: Description, Pkgs, Type
                m_lines = self._build_lines(m_w)
                for ln in m_lines:
                    t = ln['text']
                    
                    # Check for container type like 1x40HC or 1 x 40HC
                    type_match = re.search(r'\d+\s*[xX]\s*\d+[A-Z]+', t)
                    if type_match and current_cont:
                        current_cont["Cont type"] = type_match.group(0).replace(' ', '')
                        
                    # Check for cartons like 880 CARTONS
                    carton_match = re.search(r'\d+\s*(CARTONS|PACKAGES|PCS|UNITS)', t, re.IGNORECASE)
                    if carton_match and current_cont:
                        current_cont["Total carton"] = carton_match.group(0)
                        
                    # Add to description if it's not type/cartons
                    if not type_match and not carton_match:
                        t_upper = t.upper()
                        
                        if 'CONTINUED ON NEXT SHEET' in t_upper:
                            break
                            
                        if 'PARTICULARS DECLARED' in t_upper or 'ADDITIONAL CLAUSES' in t_upper or 'SHEET' in t_upper:
                            break
                            
                        skip_phrases = ['DESCRIPTION OF PACKAGES', "SHIPPER'S LOAD", 'SAID TO CONTAIN', 'WEIGHT IN KGS']
                        if any(sp in t_upper for sp in skip_phrases):
                            continue
                            
                        if re.search(r'(FREIGHT\s+(COLLECT|PREPAID|PAYABLE)|(?:SHIPPED|CLEAN)\s+ON\s+BOARD|AS\s+AGENT\s+FOR\s+THE\s+CARRIER)', t_upper):
                            in_remark = True
                            
                        if in_remark:
                            remark_lines.append(t)
                        else:
                            desc_lines.append(t)
                
                # Right side: Weight, Tare, Measurement
                r_lines = self._build_lines(r_w)
                for ln in r_lines:
                    t = ln['text']
                    vals = re.findall(r'[\d\.]+', t)
                    if len(vals) >= 3 and current_cont:
                        current_cont["Total GW"] = vals[0]
                        current_cont["Tare"] = vals[1]
                        current_cont["Total CBM"] = vals[2]
                    elif len(vals) == 2 and current_cont:
                        if not current_cont["Total GW"]: current_cont["Total GW"] = vals[0]
                        if not current_cont["Tare"]: current_cont["Tare"] = vals[1]
                    elif len(vals) == 1 and current_cont:
                        if not current_cont["Total GW"]: current_cont["Total GW"] = vals[0]
                
                # Footer: ATD
                issue_word = self.find_word_bbox(p, 'ISSUE')
                if issue_word:
                    issue_bbox = (0, issue_word['bottom'], p.width, issue_word['bottom'] + 30)
                    issue_txt = self.extract_text_by_bbox(p, issue_bbox)
                    if issue_txt:
                        date_match = re.search(r'\d{1,2}\s+[A-Z]{3}\s+\d{4}', issue_txt, re.IGNORECASE)
                        if date_match:
                            row["ATD"] = date_match.group(0)
                            if current_cont: current_cont["ATD"] = date_match.group(0)

            if current_cont:
                current_cont["Description"] = "\n".join(desc_lines).strip()
                current_cont["Remark"] = remark_lines[0].strip() if remark_lines else ""
                if current_cont not in rows:
                    rows.append(current_cont)
            
            if not rows:
                row["Description"] = "\n".join(desc_lines).strip()
                row["Remark"] = remark_lines[0].strip() if remark_lines else ""
                rows.append(row)
                
            # Apply common fields that might have been updated at the end
            for r in rows:
                rem = r.get("Remark", "").upper()
                if "FREIGHT COLLECT" in rem:
                    r["Freight"] = "FREIGHT COLLECT"
                elif "FREIGHT PREPAID" in rem:
                    r["Freight"] = "FREIGHT PREPAID"
                elif not r["Freight"]:
                    r["Freight"] = row["Freight"]
                    
                if not r["ATD"]: r["ATD"] = row["ATD"]

        return rows
