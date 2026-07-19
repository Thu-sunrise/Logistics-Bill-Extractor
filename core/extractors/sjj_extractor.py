import pdfplumber
import re
from .base_extractor import BaseExtractor

class SjjExtractor(BaseExtractor):
    def __init__(self, pdf_path):
        super().__init__(pdf_path)
        self.carrier_name = "SJJ"

    def extract(self):
        data = self.get_empty_row()
        containers = []

        total_gw = ""
        total_cbm = ""
        bl_no = ""

        with pdfplumber.open(self.pdf_path) as pdf:
            # Page 1 contains voyage & container information
            first_page = pdf.pages[0]
            words = first_page.extract_words()
            first_page_text = first_page.extract_text(layout=True) or ""
            fp_lines = first_page_text.split('\n')

            # 1. Extract B/L No (e.g. JJDHPNSBK60069)
            for line in fp_lines:
                bl_match = re.search(r'\b(JJD[A-Z0-9]+)\b', line)
                if bl_match:
                    bl_no = bl_match.group(1)
                    break

            # 2. Customer blocks (Shipper, Consignee, Notify Party) using Y coordinates
            # Due to the lack of clear text labels separating on page 1
            data["Shipper"] = self.extract_left_block_by_y(words, 15, 90, 300)
            data["Consignee"] = self.extract_left_block_by_y(words, 90, 175, 300)
            data["Notify party 1"] = self.extract_left_block_by_y(words, 175, 270, 300)

            # 3. Vessel info & POL, POD, Place of Delivery using Y coordinates (270 <= Y < 320)
            vessel_words = []
            pol_words = []
            pod_words = []
            deliv_words = []

            for w in words:
                if 270 <= w['top'] < 320:
                    if w['x0'] < 160:  # Left column (Vessel, POD)
                        if w['top'] < 290:
                            vessel_words.append(w)
                        else:
                            pod_words.append(w)
                    else:  # Right column (POL, Place of Delivery)
                        if w['top'] < 290:
                            pol_words.append(w)
                        else:
                            deliv_words.append(w)

            vessel_voyage = " ".join(w['text'] for w in sorted(vessel_words, key=lambda x: x['x0'])).strip()
            data["POL"] = " ".join(w['text'] for w in sorted(pol_words, key=lambda x: x['x0'])).strip()
            data["POD"] = " ".join(w['text'] for w in sorted(pod_words, key=lambda x: x['x0'])).strip()
            data["Place of delivery"] = " ".join(w['text'] for w in sorted(deliv_words, key=lambda x: x['x0'])).strip()

            vessel_name, voyage_number, _ = self.parse_vessel_voyage(vessel_voyage)
            data["Vessel name"] = vessel_name
            data["Voyage number"] = voyage_number

            # 4. Extract ATD (LADEN ON BOARD)
            for i, line in enumerate(fp_lines):
                if "LADEN ON BOARD" in line.upper():
                    if i + 1 < len(fp_lines):
                        atd_line = fp_lines[i + 1].strip()
                        atd_match = re.search(r'DATE\s+([A-Za-z]+\s+\d{1,2},\s*\d{4})', atd_line, re.IGNORECASE)
                        if atd_match:
                            data["ATD"] = atd_match.group(1)
                        else:
                            data["ATD"] = atd_line.replace("DATE", "").split("BY")[0].strip()

            # 5. Container information
            # Format: TWCU8164002/SJJD375699/40'HC/133 PACKAGES/G.W.12,568.700 KGS/63.316 CBM CY-CY
            for line in fp_lines:
                if re.search(r'\b[A-Z]{4}\d{7}\b', line):
                    parts = line.split('/')
                    if len(parts) >= 3:
                        cont = {col: "" for col in ["Cont no.", "Seal no.", "Total carton", "Cont type", "Total GW", "Total CBM"]}
                        
                        # Cont no
                        cont_no_match = re.search(r'\b([A-Z]{4}\d{7})\b', parts[0])
                        if cont_no_match:
                            cont["Cont no."] = cont_no_match.group(1)
                        
                        # Seal no
                        if len(parts) > 1:
                            cont["Seal no."] = parts[1].strip()
                            
                        # Cont type
                        if len(parts) > 2:
                            cont["Cont type"] = parts[2].strip()
                            
                        # Total carton
                        if len(parts) > 3:
                            cont["Total carton"] = parts[3].strip()
                            
                        # Total GW
                        if len(parts) > 4:
                            gw_str = parts[4].strip()
                            gw_str = re.sub(r'^G\.?W\.?\s*', '', gw_str, flags=re.IGNORECASE)
                            cont["Total GW"] = gw_str
                            
                        # Total CBM
                        if len(parts) > 5:
                            cbm_str = parts[5].strip()
                            cbm_match = re.search(r'^([\d.,]+)\s*(CBM|M3)?', cbm_str, re.IGNORECASE)
                            if cbm_match:
                                cont["Total CBM"] = cbm_match.group(0).strip()
                            else:
                                cont["Total CBM"] = cbm_str.split()[0].strip()

                        if cont["Total GW"]:
                            total_gw = cont["Total GW"]
                        if cont["Total CBM"]:
                            total_cbm = cont["Total CBM"]
                            
                        containers.append(cont)

            # 6. Description (Goods) and Remark (MARKS AND NUMBERS)
            # For SJJ, the detailed description is in the Attached Sheet (page 2 onwards)
            if len(pdf.pages) > 1:
                desc_lines = []
                remark_lines = []
                found_total = False
                
                for page in pdf.pages[1:]:
                    page_words = page.extract_words()
                    
                    # --- Find Y of MARKS AND NUMBERS ---
                    marks_y = 0
                    for w in page_words:
                        if "MARKS" in w['text'].upper():
                            marks_y = w['top']
                            break
                            
                    # --- Extract Description (x >= 220) ---
                    if not found_total:
                        desc_words = [w for w in page_words if w['x0'] >= 220]
                        lines_dict = {}
                        for w in desc_words:
                            matched_y = None
                            for y in lines_dict.keys():
                                if abs(y - w['top']) < 3:
                                    matched_y = y
                                    break
                            if matched_y is None:
                                matched_y = w['top']
                                lines_dict[matched_y] = []
                            lines_dict[matched_y].append(w)
                        
                        for y in sorted(lines_dict.keys()):
                            sorted_w = sorted(lines_dict[y], key=lambda x: x['x0'])
                            line_str = " ".join(item['text'] for item in sorted_w).strip()
                            
                            # Stop at TOTAL
                            if re.match(r'^TOTAL\s+\d+\s*(PCS|PIECES|PKGS|PACKAGES|CTNS)', line_str.upper()) or line_str.upper().startswith("TOTAL "):
                                desc_lines.append(line_str)
                                found_total = True
                                break
                                
                            # Remove junk header lines of the Attached Sheet
                            if "ATTACHED SHEET" in line_str.upper() or "PAGE" in line_str.upper():
                                continue
                            if "DESCRIPTION OF GOODS" in line_str.upper() or "MARKS AND NUMBERS" in line_str.upper():
                                continue
                            if "SHIPPER" in line_str.upper() or "CONSIGNEE" in line_str.upper():
                                continue
                            if "TEL:" in line_str.upper() or "EMAIL:" in line_str.upper():
                                continue
                                
                            if line_str:
                                desc_lines.append(line_str)
                                
                    # --- Extract Remark (x < 220) ---
                    if marks_y > 0:
                        rem_words = [w for w in page_words if w['x0'] < 220 and w['top'] > marks_y + 2]
                        rem_dict = {}
                        for w in rem_words:
                            matched_y = None
                            for y in rem_dict.keys():
                                if abs(y - w['top']) < 3:
                                    matched_y = y
                                    break
                            if matched_y is None:
                                matched_y = w['top']
                                rem_dict[matched_y] = []
                            rem_dict[matched_y].append(w)
                            
                        for y in sorted(rem_dict.keys()):
                            sorted_w = sorted(rem_dict[y], key=lambda x: x['x0'])
                            line_str = " ".join(item['text'] for item in sorted_w).strip()
                            
                            if "USCI CODE" in line_str.upper():
                                break
                                
                            if line_str and not line_str.startswith("EMAIL:") and not line_str.startswith("TEL:") and "NOTIFY" not in line_str.upper():
                                remark_lines.append(line_str)
                            
                data["Description"] = "\n".join(desc_lines)
                if remark_lines:
                    data["Remark"] = "\n".join(remark_lines)
            else:
                # Fallback to using Bounding Box on page 1 if there is only 1 page
                data["Description"] = self.extract_description_by_bbox(
                    top_kw_list=["DESCRIPTION", "PARTICULARS"],
                    bottom_kw_list=["CTNR", "TWCU", "CONTAINER"],
                    x_range=(150, 400)
                )

        # Return the result
        result = []
        if not containers:
            data["Total GW"] = total_gw
            data["Total CBM"] = total_cbm
            result.append(data)
        else:
            for c in containers:
                row = data.copy()
                row.update(c)
                if not row["Total GW"]:
                    row["Total GW"] = total_gw
                if not row["Total CBM"]:
                    row["Total CBM"] = total_cbm
                result.append(row)

        return result

    def extract_left_block_by_y(self, words, min_y, max_y, max_x=300):
        # Filter words
        block_words = [w for w in words if min_y <= w['top'] < max_y and w['x1'] <= max_x]
        
        # Group lines based on Y
        lines = {}
        for w in block_words:
            matched_y = None
            for y in lines.keys():
                if abs(y - w['top']) < 4:
                    matched_y = y
                    break
            if matched_y is None:
                matched_y = w['top']
                lines[matched_y] = []
            lines[matched_y].append(w)
        
        # Join lines
        line_texts = []
        for y in sorted(lines.keys()):
            sorted_w = sorted(lines[y], key=lambda x: x['x0'])
            line_str = " ".join(item['text'] for item in sorted_w).strip()
            if line_str:
                line_texts.append(line_str)
        return "\n".join(line_texts)

