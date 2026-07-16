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
                    
                    # Quét tìm TOTAL: ở cuối trang để lấy Total GW và Total CBM
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
                # 1. Khối khách hàng
                data["Shipper"] = self.extract_left_block(fp_lines, "SHIPPER/EXPORTER", "CONSIGNEE", 40)
                data["Consignee"] = self.extract_left_block(fp_lines, "CONSIGNEE", "NOTIFY PARTY", 40)
                data["Notify party 1"] = self.extract_left_block(fp_lines, "Clause 13 on reverse", ["PRE-CARRIAGE", "VESSEL/VOYAGE", "PLACE OF RECEIPT"], 40)

                # 2. Thông tin chuyến tàu
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

            # 3. Thông tin Container
            for line in all_lines:
                # OOCL format: CCLU7917354 /OOLLDH3312 / 88 PACKAGES /FCL/FCL /40HQ/
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

                    # Tìm loại container
                    for t in ["40HQ", "20GP", "40GP", "45HQ", "RF", "OT", "FR"]:
                        if t in line_up:
                            cont["Cont type"] = t
                            break
                            
                    containers.append(cont)

            # 4. Thông tin hàng hóa (Description)
            data["Description"] = self.extract_description_by_bbox(
                top_kw_list=["DESCRIPTION", "PARTICULARS"],
                bottom_kw_list=["CONTINUED", "NOTICE", "PAYABLE", "OCEAN"],
                x_range=(190, 400) 
            )

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

