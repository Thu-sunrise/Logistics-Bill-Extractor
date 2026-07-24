import re
import pdfplumber
from .base_extractor import BaseExtractor

class MaerskExtractor(BaseExtractor):

    @classmethod
    def is_match(cls, text_upper):
        return 'MAERSK' in text_upper

    def __init__(self, pdf_path):
        super().__init__(pdf_path)
        self.carrier_name = "MAERSK"

    def _build_lines(self, words, y_tolerance=4.0):
        lines = []
        words = sorted(words, key=lambda w: (w['top'], w['x0']))
        for w in words:
            added = False
            for line in lines:
                if abs(line['top'] - w['top']) <= y_tolerance:
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
            result.append({'top': line['top'], 'text': text, 'words': line['words']})
        return result

    def extract_text_by_bbox(self, page, bbox):
        x0, top, x1, bottom = bbox
        words = [w for w in page.extract_words() if x0 <= w['x0'] and w['x1'] <= x1 and top <= w['top'] and w['bottom'] <= bottom]
        lines = self._build_lines(words)
        return "\n".join([l['text'] for l in lines])

    def extract_headers(self, pdf, row):
        p1 = pdf.pages[0]
        
        # --- FIND VERTICAL DIVIDER ---
        booking_header = self.find_word_bbox(p1, 'Booking', x_range=(p1.width/2, p1.width))
        x_max_left = booking_header['x0'] - 5 if booking_header else 290
        
        # --- FILTER BOILERPLATE ---
        def filter_boilerplate(obj):
            if obj.get('object_type') == 'char':
                if obj['height'] < 7 and obj['x0'] > 250 and obj['top'] < 400:
                    return False
            return True
        
        p1_clean = p1.filter(filter_boilerplate)
        
        # --- PARTY INFO ---
        s_text = self.extract_dynamic_left_block(p1_clean, 'Shipper', 'Consignee', x_min=0, x_max=x_max_left, top_margin=-12)
        row["Shipper"] = re.sub(r'^(Shipper|As principal).*?(\n|$)', '', s_text, flags=re.IGNORECASE).strip()
        
        c_text = self.extract_dynamic_left_block(p1_clean, 'Consignee', 'Notify', x_min=0, x_max=p1.width, top_margin=-12)
        lines = c_text.split('\n')
        clean_c_lines = [l for l in lines if not l.lower().startswith("consignee") and not l.lower().startswith("as principal") and "negotiable only" not in l.lower()]
        row["Consignee"] = "\n".join(clean_c_lines).strip()
        
        n_text = self.extract_dynamic_left_block(p1_clean, 'Notify', 'Vessel', x_min=0, x_max=p1.width, top_margin=-12)
        clean_n_lines = [l for l in n_text.split('\n') if not l.lower().startswith("notify") and "see clause" not in l.lower()]
        row["Notify party 1"] = "\n".join(clean_n_lines).strip()
        
        # --- BOOKING & B/L NO ---
        if booking_header:
            bkg_box = (booking_header['x0'], booking_header['bottom'], p1.width, booking_header['bottom'] + 20)
            bkg_text = self.extract_text_by_bbox(p1, bkg_box)
            if bkg_text:
                b_match = re.search(r'([a-zA-Z0-9]{5,})', bkg_text.replace(' ', ''))
                row["Booking"] = b_match.group(1) if b_match else bkg_text.split('\n')[0].strip()
        
        bl_header = self.find_word_bbox(p1, 'B/L', x_range=(p1.width/2, p1.width))
        if bl_header:
            bl_box = (bl_header['x0'], bl_header['top'] - 5, p1.width, bl_header['bottom'] + 15)
            bl_text = self.extract_text_by_bbox(p1, bl_box)
            if bl_text:
                b_match = re.search(r'No\.?\s*([a-zA-Z0-9]+)', bl_text)
                row["Bill no."] = b_match.group(1) if b_match else bl_text.split('\n')[0].strip()
        
        # --- VESSEL, VOYAGE, POL, POD ---
        vessel_header = self.find_word_bbox(p1, 'Vessel', x_range=(0, p1.width/2))
        voyage_header = self.find_word_bbox(p1, 'Voyage', x_range=(0, p1.width/2))
        
        if vessel_header and voyage_header:
            v_box = (vessel_header['x0'], vessel_header['bottom'], voyage_header['x0'] - 2, vessel_header['bottom'] + 15)
            row["Vessel name"] = self.extract_text_by_bbox(p1, v_box).strip()
            
            voy_box = (voyage_header['x0'], voyage_header['bottom'], x_max_left, voyage_header['bottom'] + 15)
            row["Voyage number"] = self.extract_text_by_bbox(p1, voy_box).strip()
            
            pol_box = (0, vessel_header['bottom'] + 15, voyage_header['x0'] - 2, vessel_header['bottom'] + 40)
            pol_text = p1.crop(pol_box).extract_text(x_tolerance=2, y_tolerance=5, layout=False) or ""
            pol_lines = [line.strip() for line in pol_text.split('\n') if line.strip() and 'Port' not in line and 'Loading' not in line]
            if pol_lines:
                row["POL"] = pol_lines[0]
            
            pod_box = (voyage_header['x0'] - 20, voyage_header['bottom'] + 15, p1.width/2, voyage_header['bottom'] + 40)
            pod_text = p1.crop(pod_box).extract_text(x_tolerance=2, y_tolerance=5, layout=False) or ""
            pod_lines = [line.strip() for line in pod_text.split('\n') if line.strip() and 'Port' not in line and 'Discharge' not in line and 'PARTICULAR' not in line]
            if pod_lines:
                row["POD"] = pod_lines[0]
                row["Place of delivery"] = row["POD"]

    def extract_footers(self, pdf, row):
        p1 = pdf.pages[0]
        # ATD (usually page 1 bottom)
        atd_word = self.find_word_bbox(p1, 'Shipped', x_range=(0, p1.width/2))
        if atd_word:
            atd_box = (atd_word['x0'], atd_word['bottom'], p1.width/2, atd_word['bottom'] + 15)
            atd_text = self.extract_text_by_bbox(p1, atd_box)
            if atd_text:
                d_match = re.search(r'(\d{4}-\d{2}-\d{2})', atd_text)
                row["ATD"] = d_match.group(1) if d_match else atd_text.split('\n')[0].strip()
                
        # FREIGHT (usually page 2 under Freight & Charges)
        for page in pdf.pages:
            f_word = self.find_word_bbox(page, 'PREPAID', case_sensitive=True) or self.find_word_bbox(page, 'COLLECT', case_sensitive=True)
            if f_word and f_word['text'].upper() in ['PREPAID', 'COLLECT']:
                row["Freight"] = f"FREIGHT {f_word['text'].upper()}"
                break

    def _get_page_bounds(self, page, p1):
        # Start extracting below "PARTICULARS FURNISHED BY SHIPPER"
        particulars_word = self.find_word_bbox(p1, 'PARTICULARS')
        y_start = particulars_word['bottom'] if particulars_word else 340
        
        if page.page_number == 1:
            start_y = y_start
        else:
            w_hdr = self.find_word_bbox(page, 'Weight', x_range=(page.width/2, page.width))
            if w_hdr and w_hdr['top'] > page.height / 2:
                w_hdr = None
            if w_hdr:
                start_y = w_hdr['bottom']
            else:
                page_word = self.find_word_bbox(page, 'Page')
                start_y = page_word['bottom'] if (page_word and page_word['top'] < page.height / 2) else 0
                
        # Bottom boundary
        end_y = page.height
        declared_val = self.find_word_bbox(page, 'Declared')
        merchants_warn = self.find_word_bbox(page, 'Merchant(s)')
        above_part = self.find_word_bbox(page, 'Above')
        freight = self.find_word_bbox(page, 'Freight')
        
        stops = [y['top'] for y in [declared_val, merchants_warn, above_part, freight] if y and y['top'] > start_y]
        if stops:
            end_y = min(stops)
            
        return start_y, end_y

    def _get_col_ranges(self, p1):
        weight_header = self.find_word_bbox(p1, 'Weight', x_range=(p1.width/2, p1.width))
        meas_header = self.find_word_bbox(p1, 'Measurement', x_range=(p1.width/2, p1.width))
        
        w_start = weight_header['x0'] - 5 if weight_header else 410
        m_start = meas_header['x0'] - 5 if meas_header else 500
        
        return {
            'Desc': (0, w_start),
            'GW': (w_start, m_start),
            'CBM': (m_start, p1.width)
        }

    def _parse_grid(self, pdf):
        if not pdf.pages: return [], "", ""
        p1 = pdf.pages[0]
        col_ranges = self._get_col_ranges(p1)
        
        containers = []
        extracted_cont_nos = set()
        desc_lines = []
        found_container = False
        total_cartons = ""
        
        for page in pdf.pages:
            if page.page_number > 1:
                shipper_w = self.find_word_bbox(page, 'Shipper', x_range=(0, p1.width/2))
                vessel_w = self.find_word_bbox(page, 'Vessel', x_range=(0, p1.width/2))
                if (shipper_w and shipper_w['top'] < 200) and (vessel_w and vessel_w['top'] < 200):
                    break
                    
            start_y, end_y = self._get_page_bounds(page, p1)
            words = page.extract_words()
            lines = self._build_lines([w for w in words if start_y <= w['top'] < end_y])
            
            for line in lines:
                desc_text = " ".join([w['text'] for w in line['words'] if col_ranges['Desc'][0] <= (w['x0']+w['x1'])/2 <= col_ranges['Desc'][1]])
                gw_text = " ".join([w['text'] for w in line['words'] if col_ranges['GW'][0] <= (w['x0']+w['x1'])/2 <= col_ranges['GW'][1]])
                cbm_text = " ".join([w['text'] for w in line['words'] if col_ranges['CBM'][0] <= (w['x0']+w['x1'])/2 <= col_ranges['CBM'][1]])
                
                if "Said to Contain" in desc_text and not total_cartons:
                    t_match = re.search(r'Contain\s+(\d+\s*[A-Z]+)', desc_text, re.IGNORECASE)
                    if t_match: total_cartons = t_match.group(1)
                
                combined_text = f"{desc_text} {gw_text} {cbm_text}".strip()
                cont_match = re.search(r'([A-Z]{4}\d{7})\s+([\w\-]+)\s+(.*?)\s+(\d+\s*[A-Z]+)', combined_text)
                if cont_match:
                    found_container = True
                    cont_no = cont_match.group(1)
                    seal_no = cont_match.group(2)
                    cont_type = cont_match.group(3).strip()
                    pkg = cont_match.group(4)
                    
                    gw_match = re.search(r'([\d\.,]+\s*KGS)', combined_text)
                    c_gw = gw_match.group(1) if gw_match else gw_text.strip()
                    
                    cbm_match = re.search(r'([\d\.,]+\s*CBM)', combined_text)
                    c_cbm = cbm_match.group(1) if cbm_match else cbm_text.strip()
                    
                    if cont_no not in extracted_cont_nos:
                        extracted_cont_nos.add(cont_no)
                        containers.append({
                            "Cont no.": cont_no,
                            "Seal no.": seal_no,
                            "Cont type": cont_type,
                            "Total carton": pkg, # Use "Total carton" key to map seamlessly in _build_rows
                            "Total GW": c_gw,
                            "Total CBM": c_cbm
                        })
                else:
                    if not found_container:
                        clean_desc = desc_text.strip()
                        if clean_desc and "Description of goods" not in clean_desc and "Said to Contain" not in clean_desc:
                            if not re.match(r'^[-_]+$', clean_desc):
                                desc_lines.append(clean_desc)
                                
        return containers, "\n".join(desc_lines), total_cartons

    def extract_description(self, pdf):
        if not hasattr(self, '_cached_grid'):
            self._cached_grid = self._parse_grid(pdf)
        return self._cached_grid[1]

    def extract_containers(self, pdf):
        if not hasattr(self, '_cached_grid'):
            self._cached_grid = self._parse_grid(pdf)
        
        containers, _, total_cartons = self._cached_grid
        if not containers:
            if total_cartons:
                return [{"Total carton": total_cartons}]
            return []
            
        return containers
