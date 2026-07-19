from .base_extractor import BaseExtractor
import pdfplumber
import re

class MscExtractor(BaseExtractor):
    def __init__(self, pdf_path):
        super().__init__(pdf_path)
        self.carrier_name = "MSC"

    def _build_lines(self, words, tolerance=3):
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

    def extract(self):
        row = self.get_empty_row()
        with pdfplumber.open(self.pdf_path) as pdf:
            if not pdf.pages: return [row]
            p1 = pdf.pages[0]

            s = self.extract_dynamic_left_block(p1, 'SHIPPER:', 'CONSIGNEE:', x_min=0, x_max=300)
            row["Shipper"] = re.sub(r'^SHIPPER:\s*', '', s).strip()
            
            c = self.extract_dynamic_left_block(p1, 'CONSIGNEE:', 'NOTIFY', x_min=0, x_max=300)
            row["Consignee"] = re.sub(r'^CONSIGNEE:\s*', '', c).strip()
            
            n1 = self.extract_dynamic_left_block(p1, 'NOTIFY', 'VESSEL', x_min=0, x_max=300)
            if 'CONTINUED IN CARRIER' in n1:
                n1 = n1.split('CONTINUED IN CARRIER')[0]
            n1_lines = [ln for ln in n1.split('\n') if 'NOTIFY' not in ln.upper() and 'Clause 20' not in ln]
            row["Notify party 1"] = '\n'.join(n1_lines).strip()
            
            n2_word = self.find_word_bbox(p1, 'CONTINUED', x_range=(300, 600))
            if n2_word:
                b_word = self.find_word_bbox(p1, 'DISCHARGE', x_range=(300, 600))
                max_y = b_word['top'] if b_word else p1.height
                n2_text = self.extract_text_by_bbox(p1, (300, n2_word['bottom'], 600, max_y))
                disc = "Any dispute arising out of or in connection with this Bill of Lading"
                if disc in n2_text: n2_text = n2_text.split(disc)[0].strip()
                row["Notify party 2"] = n2_text
            
            v_text = self.extract_dynamic_left_block(p1, 'VESSEL', 'BOOKING', x_min=0, x_max=300)
            v_text = re.sub(r'VESSEL AND VOYAGE NO\s*(\(see Clause 8 & 9\))?', '', v_text).strip()
            v, voy, _ = self.parse_vessel_voyage(v_text)
            row["Vessel name"] = v.rstrip('-').strip()
            row["Voyage number"] = voy
    
            l_word = self.find_word_bbox(p1, 'LOADING', x_range=(200, p1.width))
            if l_word:
                words = p1.extract_words()
                d_words = [w for w in words if 'DISCHARGE' in w['text'] and w['top'] > l_word['bottom'] and 200 <= w['x0'] <= p1.width]
                if d_words:
                    d_word = min(d_words, key=lambda w: w['top'])
                    pol_bbox = (215, l_word['bottom'] + 2, 350, d_word['top'] - 2)
                    pol_text = p1.crop(pol_bbox).extract_text()
                    if pol_text:
                        row["POL"] = pol_text.split('\n')[0].strip()
                    
                    pod_bbox = (215, d_word['bottom'] + 2, 380, d_word['bottom'] + 15)
                    pod_text = p1.crop(pod_bbox).extract_text()
                    if pod_text:
                        row["POD"] = pod_text.split('\n')[0].replace('XX', '').strip()
            
            w_word = self.find_word_bbox(p1, 'WAYBILL')
            if w_word:
                for w in p1.extract_words():
                    if w['top'] >= w_word['top'] - 5 and w['bottom'] <= w_word['bottom'] + 5 and w['x0'] > w_word['x1']:
                        if 'MEDU' in w['text'] or w['text'].isalnum():
                            row["Bill no."] = w['text']
                            break
                            
            p1_text = p1.extract_text()
            qty_m = re.search(r'Total Items\s*:\s*(\d+)', p1_text)
            if qty_m: row["Total carton"] = qty_m.group(1)
            gw_m = re.search(r'Total Gross Weight\s*:\s*([\d\.]+\s*(Kgs\.|kgs))', p1_text, re.IGNORECASE)
            if gw_m: row["Total GW"] = gw_m.group(1)

            if len(pdf.pages) > 1:
                p2 = pdf.pages[1]
                words2 = p2.extract_words()
                d_head = self.find_word_bbox(p2, 'Description', x_range=(150, 450))
                h_y = d_head['bottom'] if d_head else 100
                
                l_w, m_w, r_w = [], [], []
                for w in words2:
                    if w['top'] < h_y or w['top'] > p2.height - 100: continue
                    if w['x0'] < 140: l_w.append(w)
                    elif 140 <= w['x0'] < 450: m_w.append(w)
                    else: r_w.append(w)
                
                l_lines = self._build_lines(l_w)
                c_type = ""
                rmk = []
                in_rmk = False
                for i, ln in enumerate(l_lines):
                    t = ln['text']
                    if re.match(r'^[A-Z]{4}[0-9]{7}', t):
                        row["Cont no."] = t
                        if i+1 < len(l_lines) and any(x in l_lines[i+1]['text'] for x in ['40', '20', 'CUBE']):
                            c_type = l_lines[i+1]['text']
                    elif 'Carrier' in t or 'FX' in t:
                        sm = re.search(r'FX\d+', t)
                        if sm: row["Seal no."] = sm.group(0)
                        elif len(t.split()) > 1: row["Seal no."] = t.split()[-1]
                    elif 'Marks and Numbers' in t:
                        in_rmk = True
                        rt = t.replace('Marks and Numbers:', '').strip()
                        if rt: rmk.append(rt)
                    elif in_rmk: rmk.append(t)
                row["Cont type"] = c_type
                row["Remark"] = "\n".join(rmk).strip()
                
                m_lines = self._build_lines(m_w)
                d_text = "\n".join([l['text'] for l in m_lines])
                s_str = "The Goods detailed herein"
                if s_str in d_text: d_text = d_text.split(s_str)[0].strip()
                
                if '# Customs Department' in d_text:
                    pts = d_text.split('# Customs Department')
                    d_text = pts[0].strip()
                    n_pt = '# Customs Department' + pts[1]
                    if 'Notify Party 3:' in n_pt:
                        n3_pts = n_pt.split('Notify Party 3:')
                        row["Notify party 1"] += "\n" + n3_pts[0].strip()
                        row["Notify party 3"] = n3_pts[1].strip()
                    else:
                        row["Notify party 1"] += "\n" + n_pt.strip()
                d_str = "(Continued on attached Bill of Lading Rider pages(s), if applicable)"
                if d_str in d_text:
                    d_text = d_text.split(d_str)[-1].strip()
                row["Description"] = d_text
                
                r_lines = self._build_lines(r_w)
                for ln in r_lines:
                    t = ln['text']
                    cm = re.search(r'([\d\.]+)\s*(cu\.\s*m\.)', t, re.IGNORECASE)
                    if cm: row["Total CBM"] = cm.group(0)
        return [row]
