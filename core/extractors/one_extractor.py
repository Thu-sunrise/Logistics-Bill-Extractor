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

        lines = full_text.split('\n')
        data = self.get_empty_row()

        # 1. Left blocks (Shipper, Consignee, Notify)
        data["Shipper"] = self.extract_left_block(lines, "SHIPPER", "CONSIGNEE", 45)
        data["Consignee"] = self.extract_left_block(lines, "CONSIGNEE", "NOTIFY PARTY", 45)
        
        notify = self.extract_left_block(lines, "NOTIFY PARTY", "PRE-CARRIAGE BY", 45)
        if not notify:
            notify = self.extract_left_block(lines, "NOTIFY PARTY", "OCEAN VESSEL", 45)
        data["Notify party 1"] = notify

        # 2. Vessel, Voyage, POL, POD, ATD
        for i, line in enumerate(lines):
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
                    if any(x in p_up for x in ["40HQ","20GP","40GP","45HQ","RF","OT","FR"]):
                        cont["Cont type"] = p.strip()
                    if re.search(r'[\d.]+\s*KGS', p_up):
                        cont["Total GW"] = p.strip()
                    if re.search(r'[\d.]+\s*(M3|CBM)', p_up):
                        cont["Total CBM"] = p.strip()

                conts.append(cont)

        # 4. Description (Bounding Box via BaseExtractor)
        full_desc = self.extract_description_by_bbox(
            top_kw_list=['PARTICULARS', 'DESCRIPTION'],
            bottom_kw_list=['FREIGHT', 'DECLARED', 'OCEAN', 'DESTINATION', 'SIGNED', 'CONTINUED'],
            x_range=(210, 460),
            pages_to_read=pages_to_read
        )

        if not conts:
            conts.append({})

        results = []
        for c in conts:
            row = data.copy()
            row.update(c)
            row["Description"] = full_desc
            results.append(row)

        return results
