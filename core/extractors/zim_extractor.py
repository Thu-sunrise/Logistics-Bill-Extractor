import pdfplumber
import re
from .base_extractor import BaseExtractor

# Dynamic fields anchors for ZIM page 1
ZIM_DYNAMIC_FIELDS = {
    "Shipper": {
        "top_anchor": "SHIPPER",
        "bottom_anchor": "CONSIGNEE",
        "x_min": 30, "x_max": 270
    },
    "Consignee": {
        "top_anchor": "CONSIGNEE",
        "bottom_anchor": ["NON-NEGOTIABLE", "NOTIFY"],
        "x_min": 30, "x_max": 270
    },
    "Notify party 1": {
        "top_anchor": "NOTIFY",
        "bottom_anchor": "INITIAL", 
        "x_min": 30, "x_max": 270
    },
    "Booking": {
        "top_anchor": "BOOKING",
        "bottom_anchor": "EXPORT", 
        "x_min": 250, "x_max": 590
    },
    "Bill no.": {
        "top_anchor": ["WAYBILL", "B/L NO", "BILL OF LADING NO"],
        "bottom_anchor": "EXPORT", 
        "x_min": 250, "x_max": 590
    },
    "Vessel name": {
        "top_anchor": "VESSEL",
        "bottom_anchor": "FINAL",
        "x_min": 30, "x_max": 170,
        "anchor_x_range": (30, 350)
    },
    "POL": {
        "top_anchor": "LOADING",
        "bottom_anchor": "FINAL",
        "x_min": 170, "x_max": 350,
        "anchor_x_range": (30, 350)
    },
    "POD": {
        "top_anchor": "FINAL",
        "bottom_anchor": "MKS",
        "x_min": 30, "x_max": 300
    }
}

# Column X-ranges for Page 2
ZIM_PAGE2_COLS = {
    "Remark": (0, 135),
    "Description": (135, 450),
    "Weight": (450, 650),
    "Measurement": (650, 850)
}

class ZimExtractor(BaseExtractor):
    def __init__(self, pdf_path):
        super().__init__(pdf_path)
        self.carrier_name = "ZIM"

    def extract(self):
        """
        Extract data from ZIM PDF file.
        - Page 1: Scan static fields (Shipper, Consignee, Vessel, POL, POD...) using dynamic bounding box (bbox) coordinates.
        - Page 1 & 2+: Scan all to get Container info and Total GW/CBM.
        - Page 2+: Extract text blocks for Remark and Description.
        """
        data = self.get_empty_row()
        
        with pdfplumber.open(self.pdf_path) as pdf:
            if not pdf.pages:
                return [data]
                
            first_page = pdf.pages[0]
            
            # 1. Extract and clean static data (Page 1)
            self._extract_static_fields(first_page, data)
            self._cleanup_static_fields(data)
            
            # 2. Get all text lines from all pages
            all_lines = self._extract_all_lines(pdf)
            
            # 3. Scan dynamic text columns (Page 2+)
            remark_list, desc_list, weight_list, measure_list = self._extract_dynamic_columns(pdf, data)
            
            # 4. Process business logic for Remark & Description
            data["Remark"] = self._process_remark(remark_list)
            self._process_description_and_notifications(desc_list, data)
            
            # 5. Extract Containers & Totals
            containers, total_gw, total_cbm = self._extract_containers_and_totals(all_lines, weight_list, measure_list)
            
            # 6. Assemble data into final rows
            return self._assemble_final_rows(data, containers, total_gw, total_cbm)

    def _extract_static_fields(self, first_page, data):
        """Scan page 1 to extract static fields based on dynamic BBOX."""
        for field, config in ZIM_DYNAMIC_FIELDS.items():
            bbox = self.get_dynamic_bbox(
                first_page, 
                config["top_anchor"], 
                config["bottom_anchor"], 
                config["x_min"], 
                config["x_max"],
                config.get("anchor_x_range")
            )
            if bbox:
                text = self.extract_text_by_bbox(first_page, bbox)
                # Cleanup: Remove the line containing the anchor keyword
                if field in ["Vessel name", "POD", "POL"]:
                    text = re.sub(r'(?i).*' + config["top_anchor"] + r'[^\n]*\n?', '', text)
                data[field] = text.strip()
                
        # ATD (Static coordinates as it's usually at the bottom right corner)
        atd_bbox = (350, 600, 590, 800)
        atd_text = self.extract_text_by_bbox(first_page, atd_bbox)
        atd_match = re.search(r'(\d{2}/\d{2}/\d{4})', atd_text)
        if atd_match:
            data["ATD"] = atd_match.group(1)

    def _cleanup_static_fields(self, data):
        """Clean and parse complex static fields."""
        # Split Booking No and Bill no (they might be scanned together)
        b_text = data.get("Booking", "") + " " + data.get("Bill no.", "")
        b_matches = re.findall(r'(ZIM[A-Z0-9]+)', b_text)
        
        if b_matches:
            unique_b_matches = list(dict.fromkeys(b_matches))
            if len(unique_b_matches) >= 2:
                data["Booking"] = unique_b_matches[0]
                data["Bill no."] = unique_b_matches[1]
            else:
                data["Booking"] = unique_b_matches[0]
                data["Bill no."] = unique_b_matches[0]
        
        # Clean Vessel, Voyage
        if data.get("Vessel name"):
            vessel_text = data["Vessel name"].strip()
            vessel_name, voyage_number, _ = self.parse_vessel_voyage(vessel_text)
            data["Vessel name"] = vessel_name.split('\n')[0].strip() if vessel_name else ""
            data["Voyage number"] = voyage_number.split('\n')[0].strip() if voyage_number else ""
        
        # Clean POL
        if data.get("POL"):
            pol = data["POL"].split('\n')[0].strip()
            pol = re.split(r'\s{2,}', pol)[0]
            pol = pol.replace("**", "")
            data["POL"] = pol
        
        # Clean POD and assign to Place of delivery
        if data.get("POD"):
            pod_text = data["POD"]
            pod_text = pod_text.replace("(IF CONTRACTED FOR)", "").strip()
            pod_text = re.sub(r'^F\s+', '', pod_text)
            data["POD"] = pod_text.split('\n')[0].strip()
            data["Place of delivery"] = data["POD"]

    def _extract_all_lines(self, pdf):
        """Extract all text lines from all pages."""
        all_lines = []
        for page in pdf.pages:
            text = page.extract_text(layout=True)
            if text:
                all_lines.extend(text.split('\n'))
        return all_lines

    def _extract_dynamic_columns(self, pdf, data):
        """Scan from page 2 onwards by X-ranges columns to extract Remark, Description, Weight, Measure."""
        remark_text_list = []
        desc_text_list = []
        weight_text_list = []
        measure_text_list = []
        
        for page_idx in range(1, len(pdf.pages)):
            page = pdf.pages[page_idx]
            
            extracted_cols = self.extract_columns_by_x_ranges(
                page, 
                col_x_ranges=ZIM_PAGE2_COLS,
                y_range=(100, page.height - 100) # Exclude header/footer part
            )
            
            for row_dict in extracted_cols:
                rmk = row_dict.get("Remark", "")
                dsc = row_dict.get("Description", "")
                
                if rmk and "MKS & NOS" not in rmk and "SEAL NO" not in rmk:
                    remark_text_list.append(rmk)
                
                if dsc and "DESCRIPTION OF GOODS" not in dsc and "WEIGHT" not in dsc:
                    if dsc.strip() not in ["KGS", "CBM", "MEASURE", "MEASUREMENT"]:
                        desc_text_list.append(dsc)
                    
                wgt = row_dict.get("Weight", "")
                if wgt and not any(kw in wgt.upper() for kw in ["WEIGHT", "KGS", "TOTAL"]):
                    wgt_clean = re.sub(r'[^\d.]', '', wgt)
                    if wgt_clean:
                        weight_text_list.append(wgt_clean)
                        
                mea = row_dict.get("Measurement", "")
                if mea and not any(kw in mea.upper() for kw in ["MEASUREMENT", "M3", "TOTAL"]):
                    mea_clean = re.sub(r'[^\d.]', '', mea)
                    if mea_clean:
                        measure_text_list.append(mea_clean)
                        
        return remark_text_list, desc_text_list, weight_text_list, measure_text_list

    def _process_remark(self, remark_text_list):
        """Filter and join Remark lines."""
        if not remark_text_list:
            return ""
            
        remark_lines = []
        cont_no_pattern = r'\b[A-Z]{4}\s*\d{7}\b'
        for text in remark_text_list:
            if text.strip():
                # Stop if hitting container summary or footer terms
                if (re.search(cont_no_pattern, text) or 
                    text.startswith("SEAL:") or 
                    text.startswith("SHIPPER'S") or 
                    text.startswith("CLAUSES:")):
                    break
                text_clean = text.replace("(CY/CY SBL)", "").replace("IKEA", "").strip()
                if text_clean:
                    remark_lines.append(text_clean)
        return "\n".join(remark_lines)

    def _process_description_and_notifications(self, desc_text_list, data):
        """Separate Description and Notify Parties (which are grouped at the bottom of Description)."""
        if not desc_text_list:
            return
            
        full_desc = "\n".join(desc_text_list)
        
        n2_match = re.search(r'NOTIFY\s+PARTY\s+2[:\s]*', full_desc)
        notify_2_idx = n2_match.start() if n2_match else -1
        
        n3_match = re.search(r'NOTIFY\s+PARTY\s+3[:\s]*', full_desc)
        notify_3_idx = n3_match.start() if n3_match else -1
        
        declared_idx = full_desc.find("DECLARED BY")
        
        # Additional content for Notify 1 usually starts with # (e.g., #PHU QUOI COMMUNE)
        # or contains the keyword CUSTOMS DEPARTMENT. It is located between Description and Notify 2.
        customs_idx = -1
        hash_match = re.search(r'^#', full_desc, flags=re.MULTILINE)
        if hash_match:
            customs_idx = hash_match.start()
        else:
            c_idx = full_desc.find("CUSTOMS DEPARTMENT")
            if c_idx != -1:
                line_start = full_desc.rfind('\n', 0, c_idx)
                customs_idx = line_start + 1 if line_start != -1 else 0
                
        # Find the actual end point of the text (removing mixed in Container summary / Footer)
        footer_idx = len(full_desc)
        footer_patterns = [
            r'^SHIPPER\'S', r'^SEAL:', r'^CLAUSES:', r'^TOTAL:', 
            r'CONT\s+TARE\s+WEIGHT', r'\b[A-Z]{4}\s*\d{7}\b',
            r'^COUNT:', r'CONT\s+TOT\.?\s+TARE'
        ]
        for pattern in footer_patterns:
            match = re.search(pattern, full_desc, flags=re.MULTILINE)
            if match and match.start() < footer_idx:
                # Ensure no accidental cut if the container number appears too early (at the very beginning)
                # Only cut if this anchor is after Notify or Description
                if match.start() > 10:
                    footer_idx = match.start()
        
        # Default Description ends at the first special notification that appears
        desc_end_idx = footer_idx
        if customs_idx != -1 and customs_idx < desc_end_idx:
            desc_end_idx = customs_idx
        if notify_2_idx != -1 and notify_2_idx < desc_end_idx:
            desc_end_idx = notify_2_idx
        if notify_3_idx != -1 and notify_3_idx < desc_end_idx:
            desc_end_idx = notify_3_idx
        if declared_idx != -1 and declared_idx < desc_end_idx:
            desc_end_idx = declared_idx
            
        data["Description"] = full_desc[:desc_end_idx].strip()
        
        # Extract the continuation of Notify 1
        if customs_idx != -1:
            customs_end = footer_idx
            if notify_2_idx != -1 and notify_2_idx > customs_idx:
                customs_end = notify_2_idx
            if notify_3_idx != -1 and notify_3_idx > customs_idx and customs_end == footer_idx:
                customs_end = notify_3_idx
            if declared_idx != -1 and declared_idx > customs_idx and customs_end == footer_idx:
                customs_end = declared_idx
            
            cont_notify_1 = full_desc[customs_idx:customs_end].strip()
            if data["Notify party 1"]:
                data["Notify party 1"] += "\n" + cont_notify_1
            else:
                data["Notify party 1"] = cont_notify_1
        
        # Extract Notify 2
        if notify_2_idx != -1:
            n2_end = notify_3_idx if notify_3_idx != -1 else (declared_idx if declared_idx != -1 else footer_idx)
            data["Notify party 2"] = re.sub(r'^NOTIFY\s+PARTY\s+2[:\s]*', '', full_desc[notify_2_idx:n2_end]).strip()
            
        # Extract Notify 3
        if notify_3_idx != -1:
            n3_end = declared_idx if declared_idx != -1 else footer_idx
            data["Notify party 3"] = re.sub(r'^NOTIFY\s+PARTY\s+3[:\s]*', '', full_desc[notify_3_idx:n3_end]).strip()

    def _extract_containers_and_totals(self, all_lines, weight_text_list, measure_text_list):
        """Scan regex to extract Container, Seal, Cont type, and Total GW/CBM."""
        containers = []
        total_gw = ""
        total_cbm = ""
        
        cont_no_pattern = r'\b[A-Z]{4}\s*\d{7}\b'
        current_cont = None
        
        for line in all_lines:
            line_up = line.upper()
            
            # Scan Container code
            cont_match = re.search(cont_no_pattern, line_up)
            if cont_match:
                if current_cont:
                    containers.append(current_cont)
                current_cont = {col: "" for col in ["Cont no.", "Seal no.", "Total carton", "Cont type"]}
                current_cont["Cont no."] = cont_match.group(0).replace(" ", "")
                
            # Scan Seal code (stop at / to remove suffixes like /H)
            if "SEAL" in line_up and current_cont and not current_cont.get("Seal no."):
                seal_match = re.search(r'SEAL[:\s]*([A-Z0-9]+)', line_up)
                if seal_match:
                    current_cont["Seal no."] = seal_match.group(1)
                    
            # Scan Container Type (support attached cases like /HC40 or /C40)
            if current_cont and not current_cont.get("Cont type"):
                for t in ["C40", "40HQ", "20GP", "40GP", "45HQ", "RF", "OT", "FR"]:
                    if re.search(rf'(?:\b|/H?){t}\b', line_up):
                        current_cont["Cont type"] = t
                        break

            # Scan Totals (Prioritize scanning lines by standard keywords)
            if "CARGO W" in line_up:
                gw_match = re.search(r'CARGO\s*W\s*[:\s]*([\d,.]+)', line_up)
                if gw_match:
                    total_gw = gw_match.group(1)
                
                cbm_match = re.search(r'CARGO\s*W\s*[:\s]*[\d,.]+\s+([\d,.]+)', line_up)
                if cbm_match:
                    total_cbm = cbm_match.group(1)
            elif "TOTAL:" in line_up and not total_gw:
                # Heuristic for older ZIM formats
                parts = line_up[line_up.find("TOTAL:"):].split()
                for p in parts:
                    if p.replace(",", "").replace(".", "").isdigit():
                        val = float(p.replace(",", ""))
                        if val >= 100:  # GW is usually large
                            total_gw = p
                        elif val < 100 and val > 0:  # CBM is usually small
                            total_cbm = p

        if current_cont:
            containers.append(current_cont)

        # Filter duplicate containers
        unique_conts = []
        seen_conts = set()
        for c in containers:
            if c["Cont no."] and c["Cont no."] not in seen_conts:
                unique_conts.append(c)
                seen_conts.add(c["Cont no."])
                
        # Only use column scanning fallback if Regex does not find to avoid accidental overwriting (e.g., Tare Weight)
        if not total_gw and weight_text_list:
            total_gw = weight_text_list[-1]
        if not total_cbm and measure_text_list:
            total_cbm = measure_text_list[-1]
            
        return unique_conts, total_gw, total_cbm

    def _assemble_final_rows(self, data, containers, total_gw, total_cbm):
        """Attach Totals to data and duplicate rows corresponding to the number of containers."""
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
