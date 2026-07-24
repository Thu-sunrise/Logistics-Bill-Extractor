import re
import pdfplumber
from .base_extractor import BaseExtractor

class CoscoExtractor(BaseExtractor):

    @classmethod
    def is_match(cls, text_upper):
        return 'COSCO' in text_upper or 'COSU' in text_upper

    def __init__(self, pdf_path):
        super().__init__(pdf_path)
        self.carrier_name = "COSCO"

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

    def extract_headers(self, pdf, row):
        p1 = pdf.pages[0]
        
        booking_word = self.find_word_bbox(p1, 'Booking', x_range=(300, p1.width))
        x_max_left = booking_word['x0'] - 10 if booking_word else 350

        s_text = self.extract_dynamic_left_block(p1, 'Shipper', 'Consignee', x_min=0, x_max=x_max_left)
        row["Shipper"] = re.sub(r'^1\.\s*Shipper.*?\n', '', s_text, flags=re.IGNORECASE).strip()
        
        c_text = self.extract_dynamic_left_block(p1, 'Consignee', 'Notify', x_min=0, x_max=x_max_left)
        row["Consignee"] = re.sub(r'^2\.\s*Consignee.*?\n', '', c_text, flags=re.IGNORECASE).strip()
        
        n_text = self.extract_dynamic_left_block(p1, 'Notify', 'Combined', x_min=0, x_max=x_max_left - 150)
        row["Notify party 1"] = re.sub(r'^3\.\s*Notify Party.*?\n', '', n_text, flags=re.IGNORECASE).strip()
        
        if booking_word:
            bkg_box = (booking_word['x0'], booking_word['bottom'], p1.width, booking_word['bottom'] + 20)
            bkg_text = self.extract_text_by_bbox(p1, bkg_box)
            if bkg_text:
                bkg_line = bkg_text.split('\n')[0].strip()
                waybill_match = re.search(r'COSU\d+', bkg_line)
                if waybill_match:
                    row["Bill no."] = waybill_match.group()
                    before_bill = bkg_line[:waybill_match.start()]
                    digits = re.sub(r'\D', '', before_bill)
                    row["Booking"] = digits if digits else bkg_line
                else:
                    row["Booking"] = bkg_line
                    row["Bill no."] = bkg_line
            
        v_text = self.extract_dynamic_left_block(p1, 'Ocean', 'Discharge', x_min=0, x_max=x_max_left)
        v_text = re.sub(r'^6\.\s*Ocean Vessel.*?\n', '', v_text, flags=re.IGNORECASE).strip()
        v, voy, _ = self.parse_vessel_voyage(v_text)
        row["Vessel name"] = v
        row["Voyage number"] = voy
        
        pol_text = self.extract_dynamic_left_block(p1, 'Loading', 'Delivery', x_min=200, x_max=p1.width)
        pol_text = re.sub(r'^7\.\s*Port of Loading.*?\n', '', pol_text, flags=re.IGNORECASE).strip()
        row["POL"] = self.split_columns_by_spaces(pol_text)[0]
        
        pod_text = self.extract_dynamic_left_block(p1, 'Discharge', 'Marks', x_min=0, x_max=x_max_left)
        pod_text = re.sub(r'^8\.\s*Port of Discharge.*?\n', '', pod_text, flags=re.IGNORECASE).strip()
        row["POD"] = self.split_columns_by_spaces(pod_text)[0]
        
        del_text = self.extract_dynamic_left_block(p1, 'Delivery', 'Type', x_min=200, x_max=p1.width)
        if not del_text: del_text = self.extract_dynamic_left_block(p1, 'Delivery', 'Gross', x_min=200, x_max=p1.width)
        del_text = re.sub(r'^9\.\s*Combined Transport.*?\n', '', del_text, flags=re.IGNORECASE).strip()
        row["Place of delivery"] = self.split_columns_by_spaces(del_text)[0]

    def _get_col_ranges(self, p1):
        marks_header = self.find_word_bbox(p1, 'Marks', x_range=(0, 200))
        pkg_header = self.find_word_bbox(p1, 'Packages', x_range=(100, 300))
        desc_header = self.find_word_bbox(p1, 'Description', x_range=(200, 500))
        gw_header = self.find_word_bbox(p1, 'Gross', x_range=(400, p1.width))
        meas_header = self.find_word_bbox(p1, 'Measurement', x_range=(500, p1.width))
        
        x_marks = (0, pkg_header['x0'] - 5) if pkg_header else (0, 150)
        x_desc = (desc_header['x0'] - 50 if desc_header else 200, gw_header['x0'] - 10 if gw_header else 500)
        x_gw = (gw_header['x0'] - 5, meas_header['x0'] - 5 if meas_header else gw_header['x0'] + 100) if gw_header else (500, 600)
        x_meas = (meas_header['x0'] - 5, p1.width) if meas_header else (600, p1.width)
        
        return {
            'Marks': x_marks,
            'Desc': x_desc,
            'GW': x_gw,
            'CBM': x_meas
        }, marks_header

    def _parse_grid(self, pdf):
        if not pdf.pages: return [], "", "", "", "", ""
        p1 = pdf.pages[0]
        col_ranges, marks_header = self._get_col_ranges(p1)
        y_start = marks_header['bottom'] if marks_header else p1.height / 2
        
        containers = []
        desc_lines = []
        totals = {"cartons": "", "gw": "", "cbm": "", "freight": ""}
        atd = ""
        
        for page in pdf.pages:
            words = page.extract_words()
            desc_header_page = self.find_word_bbox(page, 'Description', x_range=(200, p1.width))
            start_y = desc_header_page['bottom'] if desc_header_page else 0
            if page.page_number == 1 and y_start > start_y:
                start_y = y_start
            
            end_y = page.height
            total_word = self.find_word_bbox(page, 'TOTAL:') or self.find_word_bbox(page, 'Declared Cargo Value')
            continued_word = self.find_word_bbox(page, 'CONTINUED')
            
            if total_word:
                end_y = total_word['top']
            elif continued_word:
                end_y = continued_word['top']
                
            lines = self._build_lines([w for w in words if start_y <= w['top'] < end_y])
            
            for line in lines:
                marks_text = " ".join([w['text'] for w in line['words'] if col_ranges['Marks'][0] <= (w['x0']+w['x1'])/2 <= col_ranges['Marks'][1]])
                desc_text = " ".join([w['text'] for w in line['words'] if col_ranges['Desc'][0] <= (w['x0']+w['x1'])/2 <= col_ranges['Desc'][1]])
                gw_text = " ".join([w['text'] for w in line['words'] if col_ranges['GW'][0] <= (w['x0']+w['x1'])/2 <= col_ranges['GW'][1]])
                cbm_text = " ".join([w['text'] for w in line['words'] if col_ranges['CBM'][0] <= (w['x0']+w['x1'])/2 <= col_ranges['CBM'][1]])
                
                cont_match = re.search(r'([A-Z]{4}\d{7})\s*/\s*([A-Za-z0-9]+)', marks_text)
                if cont_match:
                    cont_no = cont_match.group(1)
                    seal_no = cont_match.group(2)
                    
                    cont_type = ""
                    combined_gw_cbm = gw_text + " " + cbm_text
                    
                    ctype_match = re.search(r'/(20|40|45)[A-Z0-9]+/', combined_gw_cbm + ' ' + desc_text)
                    if ctype_match:
                        cont_type = ctype_match.group(0).strip('/')
                        
                    gw_match = re.search(r'([\d\.,]+\s*KGS)', combined_gw_cbm)
                    if gw_match:
                        gw_text = gw_match.group(1)
                        
                    cbm_match = re.search(r'([\d\.,]+\s*CBM)', combined_gw_cbm)
                    if cbm_match:
                        cbm_text = cbm_match.group(1)
                        
                    containers.append({
                        "Cont no.": cont_no,
                        "Seal no.": seal_no,
                        "Cont type": cont_type,
                        "GW": gw_text,
                        "CBM": cbm_text
                    })
                else:
                    clean_desc = desc_text.strip()
                    if clean_desc and not re.match(r'^[-_]+$', clean_desc) and clean_desc.lower() != 'total':
                        desc_lines.append(clean_desc)
                        
            if page.page_number == 1:
                atd_word = self.find_word_bbox(page, 'Laden', x_range=(p1.width/2, p1.width))
                if atd_word:
                    atd_box = (atd_word['x0'], atd_word['bottom'], p1.width, atd_word['bottom'] + 20)
                    atd_text = self.extract_text_by_bbox(page, atd_box)
                    if atd_text:
                        atd_line = atd_text.split('\n')[0].strip()
                        atd_match = re.search(r'\d{1,2}\s+(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s+\d{4}', atd_line, re.IGNORECASE)
                        if atd_match:
                            atd = atd_match.group(0).upper()
                        else:
                            atd = re.sub(r'(?i)Laden on Board\s*', '', atd_line).strip()

            if total_word:
                t_lines = self._build_lines([w for w in words if total_word['bottom'] <= w['top'] < total_word['bottom'] + 80])
                for t_line in t_lines:
                    text_up = t_line['text'].upper()
                    if 'FREIGHT COLLECT' in text_up: totals["freight"] = 'FREIGHT COLLECT'
                    elif 'FREIGHT PREPAID' in text_up: totals["freight"] = 'FREIGHT PREPAID'
                    
                    desc_t = " ".join([w['text'] for w in t_line['words'] if col_ranges['Desc'][0] <= (w['x0']+w['x1'])/2 <= col_ranges['Desc'][1]])
                    gw_t = " ".join([w['text'] for w in t_line['words'] if col_ranges['GW'][0] <= (w['x0']+w['x1'])/2 <= col_ranges['GW'][1]])
                    cbm_t = " ".join([w['text'] for w in t_line['words'] if col_ranges['CBM'][0] <= (w['x0']+w['x1'])/2 <= col_ranges['CBM'][1]])
                    
                    if re.search(r'\d', desc_t): totals["cartons"] = desc_t.strip()
                    if re.search(r'\d', gw_t): totals["gw"] = gw_t.strip()
                    if re.search(r'\d', cbm_t): totals["cbm"] = cbm_t.strip()
                    
        return containers, "\n".join(desc_lines), totals["freight"], totals["cartons"], totals["gw"], totals["cbm"], atd

    def extract_description(self, pdf):
        if not hasattr(self, '_cached_grid'):
            self._cached_grid = self._parse_grid(pdf)
        return self._cached_grid[1]

    def extract_footers(self, pdf, row):
        if not hasattr(self, '_cached_grid'):
            self._cached_grid = self._parse_grid(pdf)
        _, _, freight, cartons, gw, cbm, atd = self._cached_grid
        
        if atd: row["ATD"] = atd
        if freight: row["Freight"] = freight
        
        row["Total carton"] = cartons
        row["Total GW"] = gw
        row["Total CBM"] = cbm

    def extract_containers(self, pdf):
        if not hasattr(self, '_cached_grid'):
            self._cached_grid = self._parse_grid(pdf)
        containers, _, _, cartons, gw, cbm, _ = self._cached_grid
        
        for idx, cont in enumerate(containers):
            cont["Total GW"] = cont["GW"] if cont["GW"] else gw
            cont["Total CBM"] = cont["CBM"] if cont["CBM"] else cbm
            if idx == 0:
                cont["Total carton"] = cartons
                
        return containers
