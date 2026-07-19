import pdfplumber
import re
from .base_extractor import BaseExtractor

class OoclExtractor(BaseExtractor):
    def __init__(self, pdf_path):
        super().__init__(pdf_path)
        self.carrier_name = "OOCL"

    def extract(self):
        data = self.get_empty_row()
        containers = []

        total_gw = ""
        total_cbm = ""

        with pdfplumber.open(self.pdf_path) as pdf:
            all_lines = []
            for page in pdf.pages:
                text = page.extract_text(layout=True)
                if text:
                    lines = text.split('\n')
                    all_lines.extend(lines)
                    
                    # Scan for TOTAL: at the end of the page to get Total GW and Total CBM
                    for line in lines:
                        if "TOTAL:" in line.upper() and ("KGS" in line.upper() or "CBM" in line.upper()):
                            gw_match = re.search(r'([\d.]+)\s*KGS', line.upper())
                            if gw_match:
                                total_gw = gw_match.group(1) + " KGS"
                            
                            cbm_match = re.search(r'([\d.]+)\s*CBM', line.upper())
                            if cbm_match:
                                total_cbm = cbm_match.group(1) + " CBM"
        
            first_page_text = pdf.pages[0].extract_text(layout=True)
            if first_page_text:
                fp_lines = first_page_text.split('\n')
                # 1. Customer blocks
                first_page = pdf.pages[0]
                data["Shipper"] = self.extract_dynamic_left_block(first_page, "SHIPPER/EXPORTER", "CONSIGNEE")
                data["Consignee"] = self.extract_dynamic_left_block(first_page, "CONSIGNEE", "NOTIFY")
                data["Notify party 1"] = self.extract_dynamic_left_block(first_page, "Clause", ["PRE-CARRIAGE", "VESSEL", "RECEIPT"])

                # 3. Booking & Bill no. - use bbox crop based on label coordinates
                booking_anchor = self.find_word_bbox(first_page, "BOOKING", x_range=(250, 450))
                sea_anchor = self.find_word_bbox(first_page, "SEA", x_range=(300, 500))
                if booking_anchor and sea_anchor:
                    # Booking: crop a 35px strip below the BOOKING label, left of SEA
                    b_bbox = (booking_anchor['x0'], booking_anchor['bottom'] + 2,
                              sea_anchor['x0'] - 2, booking_anchor['bottom'] + 35)
                    b_crop = first_page.crop(b_bbox)
                    b_text = b_crop.extract_text()
                    if b_text and b_text.strip():
                        data["Booking"] = b_text.strip().split()[0]
                    # Bill no.: crop a 35px strip below the SEA label, from SEA's x0 to the end of the page
                    w_bbox = (sea_anchor['x0'], sea_anchor['bottom'] + 2,
                              first_page.width, sea_anchor['bottom'] + 35)
                    w_crop = first_page.crop(w_bbox)
                    w_text = w_crop.extract_text()
                    if w_text and w_text.strip():
                        data["Bill no."] = w_text.strip().split()[0]

                # 4. Notify party 2 (ALSO NOTIFY PARTY → above LOADING PIER)
                notify2_word = self.find_word_bbox(first_page, "ALSO", x_range=(250, 600))
                loading_word = self.find_word_bbox(first_page, "LOADING", x_range=(250, 600))
                if notify2_word and loading_word:
                    x_right = min(first_page.width, first_page.width)
                    n2_bbox = (notify2_word['x0'], notify2_word['bottom'] + 2,
                               first_page.width, loading_word['top'] - 2)
                    n2_cropped = first_page.crop(n2_bbox)
                    n2_raw = n2_cropped.extract_text(layout=True)
                    if n2_raw:
                        data["Notify party 2"] = "\n".join(
                            l.strip() for l in n2_raw.split('\n') if l.strip()
                        )

                # 2. Vessel/Voyage info
                for i, line in enumerate(fp_lines):
                    if "VESSEL/VOYAGE" in line:
                        if i + 1 < len(fp_lines):
                            val = fp_lines[i + 1].strip()
                            vessel_voyage, pol = self.split_columns_by_spaces(val)
                            vessel_name, voyage_number, rest = self.parse_vessel_voyage(vessel_voyage)
                            data["Vessel name"] = vessel_name
                            data["Voyage number"] = voyage_number
                            data["POL"] = pol or rest

                    if "PORT OF DISCHARGE" in line and "PLACE OF DELIVERY" in line:
                        if i + 1 < len(fp_lines):
                            val = fp_lines[i + 1].strip()
                            pod, podel = self.split_columns_by_spaces(val)
                            data["POD"] = pod
                            data["Place of delivery"] = podel

                    if "LADEN ON BOARD" in line.upper():
                        if i + 1 < len(fp_lines):
                            data["ATD"] = fp_lines[i + 1].strip()

            # Container scanning
            for line in all_lines:
                if re.match(r'^\s*[A-Z]{4}\s*\d{7}', line):
                    cont = {col: "" for col in ["Cont no.", "Seal no.", "Total carton", "Cont type"]}
                    parts = line.split('/')
                    if len(parts) > 0:
                        cont_no_match = re.search(r'[A-Z]{4}\s*\d{7}', parts[0])
                        if cont_no_match:
                            cont["Cont no."] = cont_no_match.group(0).replace(" ", "")
                    if len(parts) > 1:
                        cont["Seal no."] = parts[1].strip()
                    line_up = line.upper()
                    carton_match = re.search(r'(\d+)\s*(PACKAGES|PCS|CARTONS|BOXES|PKGS|PIECES)', line_up)
                    if carton_match:
                        cont["Total carton"] = carton_match.group(0)
                    for t in ["40HQ", "20GP", "40GP", "45HQ", "RF", "OT", "FR"]:
                        if t in line_up:
                            cont["Cont type"] = t
                            break
                    containers.append(cont)

            # 5. Remarks: below cont line, above white space (Y-gap detection)
            first_page_full = pdf.pages[0]
            # Find anchor word MARK (in MARK & NUMBERS)
            mark_anchor = self.find_word_bbox(first_page_full, "MARK", x_range=(0, 400))
            start_y = mark_anchor['bottom'] if mark_anchor else 300
            
            # Extract FREIGHT words in the left column, below MARK
            freight_words = [w for w in first_page_full.extract_words() 
                             if "FREIGHT" in w['text'].upper() and w['x0'] < 250 and w['top'] > start_y]
            freight_words.sort(key=lambda w: w['top'])
            
            if freight_words:
                freight_word = freight_words[0]
                # Use x_max = 145 to only extract the left column (ignoring middle columns like PIECES, STORE, HS CODE)
                x_max = 145
                notice_word = self.find_word_bbox(first_page_full, "NOTICE", x_range=(0, 400))
                max_bottom = notice_word['top'] if notice_word else first_page_full.height
                
                # Find the end of the Remark block by detecting white space (gap > 15px)
                words_left = [w for w in first_page_full.extract_words()
                              if w['x0'] < x_max and freight_word['top'] - 2 <= w['top'] < max_bottom]
                words_left.sort(key=lambda w: (w['top'], w['x0']))
                
                remark_lines_map = {}
                prev_top = freight_word['top']
                
                for w in words_left:
                    # Ignore dashed lines to avoid text mixing
                    if '-' * 3 in w['text'] or '_' * 3 in w['text'] or set(w['text'].replace(' ', '')) == {'-'}:
                        continue
                    if w['top'] - prev_top > 15:
                        break
                    
                    y_key = round(w['top'])
                    remark_lines_map.setdefault(y_key, []).append(w)
                    prev_top = w['top']
                
                remark_lines = [
                    " ".join(ww['text'] for ww in sorted(remark_lines_map[y], key=lambda x: x['x0']))
                    for y in sorted(remark_lines_map)
                ]
                data["Remark"] = "\n".join(remark_lines)

            # 6. Description (ignore ---- lines)
            data["Description"] = self.extract_description_by_bbox(
                top_kw_list=["DESCRIPTION", "PARTICULARS"],
                bottom_kw_list=["CONTINUED", "NOTICE", "PAYABLE", "OCEAN"],
                x_range=(190, 400)
            )
            data["Description"] = re.sub(r'(?m)^[-_]{3,}.*$', '', data["Description"]).strip()

        result = []
        if not containers:
            data["Total GW"] = total_gw
            data["Total CBM"] = total_cbm
            result.append(data)
        else:
            for c in containers:
                row = data.copy()
                row.update(c)
                row["Total GW"] = total_gw
                row["Total CBM"] = total_cbm
                result.append(row)

        return result
