import re
from .base_extractor import BaseExtractor

class HloExtractor(BaseExtractor):

    @classmethod
    def is_match(cls, text_upper):
        return 'HAPAG-LLOYD' in text_upper

    def __init__(self, pdf_path):
        super().__init__(pdf_path)
        self.carrier_name = "Hapag-Lloyd"

    def extract_clean_text(self, page, bbox):
        try:
            text = page.crop(bbox).extract_text(layout=False)
            return text if text else ""
        except Exception:
            return ""

    def extract_headers(self, pdf, row):
        page1 = pdf.pages[0]
        
        row["Shipper"] = self.extract_dynamic_left_block(page1, "Shipper:", "Consignee:", x_min=40, x_max=300)
        row["Consignee"] = self.extract_dynamic_left_block(page1, "Consignee:", "Notify", x_min=40, x_max=300)
        row["Notify party 1"] = self.extract_dynamic_left_block(page1, "Notify", ["Vessel(s):", "Receipt:"], x_min=40, x_max=300)
        
        # Get Vessel and Voyage
        vessel_kw = self.find_word_bbox(page1, "Vessel(s):")
        voyage_kw = self.find_word_bbox(page1, "Voyage-No.:")
        loading_kw = self.find_word_bbox(page1, "Loading:")
        delivery_kw = self.find_word_bbox(page1, "Delivery:")
        receipt_kw = self.find_word_bbox(page1, "Receipt:")
        
        def clean_header_garbage(text):
            text = re.sub(r'([A-Za-z])\s+([a-z])', r'\1\2', text) # Fix "P or t" -> "Port"
            text = re.sub(r'(?i)(Port of Loading:|Port of Discharge:|Place of Receipt:|Place of Delivery:|Vessel\(s\):|Voyage-No\.:)', '', text)
            text = re.sub(r'(?i)(P\s*l\s*a\s*c\s*e\s*o\s*f\s*D\s*e\s*l\s*i\s*v\s*e\s*r\s*y\s*:)', '', text)
            text = re.sub(r'(?i)(P\s*o\s*r\s*t\s*o\s*f\s*D\s*i\s*s\s*c\s*h\s*a\s*r\s*g\s*e\s*:)', '', text)
            text = re.sub(r'(?i)(P\s*o\s*r\s*t\s*o\s*f\s*L\s*o\s*a\s*d\s*i\s*n\s*g\s*:)', '', text)
            text = re.sub(r'(?i)(V\s*e\s*s\s*s\s*e\s*l\s*\(\s*s\s*\)\s*:)', '', text)
            text = re.sub(r'(?i)(P\s*l\s*a\s*c\s*e\s*o\s*f\s*R\s*e\s*c\s*e\s*i\s*p\s*t\s*:)', '', text)
            text = re.sub(r'(?i)(V\s*o\s*y\s*a\s*g\s*e\s*-\s*N\s*o\s*\.\s*:)', '', text)
            text = re.sub(r'(?i)(Container.*)', '', text)
            text = re.sub(r'(?i)(Goods\s*Gross Weight.*)', '', text)
            text = re.sub(r'(?i)(aceo f Delivery)', '', text)
            text = re.sub(r'Page:.*', '', text, flags=re.IGNORECASE)
            text = text.replace(':', '').replace('\n', ' ').strip()
            # Hack to remove stray V from vessel
            if text.startswith('V ') and len(text) > 2:
                text = text[2:]
            return text.strip()

        if vessel_kw and loading_kw:
            bbox = (40, vessel_kw['bottom'] - 5, voyage_kw['x0'] if voyage_kw else 300, loading_kw['top'])
            vessel_text = self.extract_clean_text(page1, bbox)
            vessel_text = clean_header_garbage(vessel_text)
            row["Vessel name"] = vessel_text.split('\n')[-1].strip() if '\n' in vessel_text else vessel_text.strip()
            
        if voyage_kw and delivery_kw:
            bbox = (voyage_kw['x0'], voyage_kw['bottom'] - 5, 500, delivery_kw['top'])
            voyage_text = clean_header_garbage(self.extract_clean_text(page1, bbox))
            row["Voyage number"] = voyage_text.split('\n')[-1].strip() if '\n' in voyage_text else voyage_text.strip()
            
        if loading_kw:
            discharge_kw = self.find_word_bbox(page1, "Discharge:")
            bbox = (40, loading_kw['bottom'] - 5, 300, discharge_kw['top'] if discharge_kw else loading_kw['bottom'] + 30)
            pol_text = clean_header_garbage(self.extract_clean_text(page1, bbox))
            row["POL"] = pol_text.split('\n')[-1].strip() if '\n' in pol_text else pol_text.strip()
            
        if receipt_kw and vessel_kw:
            bbox = (receipt_kw['x0'] - 50, receipt_kw['bottom'] - 5, page1.width, vessel_kw['top'])
            por_text = clean_header_garbage(self.extract_clean_text(page1, bbox))
            row["POR"] = por_text.split('\n')[-1].strip() if '\n' in por_text else por_text.strip()
            
        cont_kw = self.find_word_bbox(page1, "Container")
        cont_top = cont_kw['top'] - 5 if cont_kw else (discharge_kw['bottom'] + 30 if discharge_kw else 400)
        
        discharge_kw = self.find_word_bbox(page1, "Discharge:")
        if discharge_kw:
            bbox = (40, discharge_kw['bottom'] - 5, 300, cont_top)
            pod_text = clean_header_garbage(self.extract_clean_text(page1, bbox))
            row["POD"] = pod_text.split('\n')[-1].strip() if '\n' in pod_text else pod_text.strip()
            
        if delivery_kw:
            bbox = (delivery_kw['x0'] - 20, delivery_kw['bottom'] - 5, page1.width, cont_top)
            deliv_text = clean_header_garbage(self.extract_clean_text(page1, bbox))
            deliv_text = re.sub(r'.*Delivery\s*:', '', deliv_text, flags=re.IGNORECASE)
            row["Place of delivery"] = deliv_text.split('\n')[-1].strip() if '\n' in deliv_text else deliv_text.strip()
            
        # Bill no
        bill_kw = self.find_word_bbox(page1, ["SWB-No.:", "B/L-No.:"])
        if bill_kw:
            # Extract text to the right and below, expanding to the left to capture prefix
            bbox = (bill_kw['x0'] - 50, bill_kw['top'] - 5, page1.width, bill_kw['bottom'] + 20)
            btext = clean_header_garbage(self.extract_clean_text(page1, bbox))
            
            matches = re.findall(r'[A-Z0-9]{8,}', btext)
            if matches:
                hlc_matches = [m for m in matches if m.startswith('HLC')]
                if hlc_matches:
                    row["Bill no."] = hlc_matches[0]
                else:
                    row["Bill no."] = max(matches, key=len)

    def extract_footers(self, pdf, row):
        # Freight
        page1 = pdf.pages[0]
        payable_kw = self.find_word_bbox(page1, "payable")
        if payable_kw:
            bbox = (payable_kw['x0'] - 50, payable_kw['bottom'], page1.width, payable_kw['bottom'] + 40)
            freight_text = self.extract_text_by_bbox(page1, bbox).upper()
            if "DESTINATION" in freight_text:
                row["Freight"] = "FREIGHT COLLECT"
            elif "ORIGIN" in freight_text:
                row["Freight"] = "FREIGHT PREPAID"

        # ATD (usually on last page)
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                match = re.search(r'SHIPPED\s+ON\s+BOARD,\s*DATE\s*:\s*([\d\.]+[A-Z]{3}[\d\.]+)', text, re.IGNORECASE)
                if match:
                    row["ATD"] = match.group(1).replace('.', ' ').strip()
                elif "SHIPPED ON BOARD" in text.upper():
                    # Fallback for line-by-line
                    for line in text.split('\n'):
                        if "SHIPPED ON BOARD" in line.upper() and "DATE" in line.upper():
                            m = re.search(r':\s*(.*)', line)
                            if m:
                                row["ATD"] = m.group(1).replace('.', ' ').strip()

    def extract_containers(self, pdf):
        containers = []
        current_cont = {}
        desc_lines = []
        found_carton = False
        expect_seal = False

        for page in pdf.pages:
            words = page.extract_words()
            line_words = self.group_words_by_y(words)
            
            # Find the header Y to start processing
            header_y = 0
            for w in words:
                if w['text'] in ["Container", "Cont/Seals/Marks"]:
                    header_y = w['bottom']
                    break
                    
            if header_y == 0:
                header_y = 100 # Default if not found

            for top in sorted(line_words.keys()):
                if top < header_y:
                    continue
                    
                line_str = " ".join([w['text'] for w in sorted(line_words[top], key=lambda x: x['x0'])]).upper()
                
                # Bottom bounds
                line_str_no_spaces = line_str.replace(" ", "")
                if "SHIPPER'S DECLARED VALUE" in line_str or "SHIPPER'SLOAD" in line_str_no_spaces or "SLAC=" in line_str_no_spaces:
                    break
                if "'S LOAD, STOW" in line_str or "WEIGHT AND COUNT" in line_str:
                    break
                if "ABOVE PARTICULARS AS DECLARED BY" in line_str or "PARTICULARS" in line_str and "DECLARED" in line_str:
                    break
                if "SHIPPED ON BOARD" in line_str or "RECEIVED BY THE CARRIER" in line_str:
                    break
                if "UNDERTAKES AND WARRANTS" in line_str or "RUSSIAN FEDERATION" in line_str:
                    break

                col_left = []
                col_desc = []
                col_weight = []
                col_measure = []
                
                for w in line_words[top]:
                    x = (w['x0'] + w['x1']) / 2
                    if x < 170:
                        col_left.append(w['text'])
                    elif x < 430:
                        col_desc.append(w['text'])
                    elif x < 480:
                        col_weight.append(w['text'])
                    else:
                        col_measure.append(w['text'])
                        
                col_left_text = " ".join(col_left)
                col_desc_text = " ".join(col_desc)
                col_weight_text = " ".join(col_weight)
                col_measure_text = " ".join(col_measure)
                
                # Check for Cont type
                if "CONT" in col_desc_text.upper() and re.search(r"20'|40'|45'", col_desc_text):
                    # If we already have a cont_no, save current and reset
                    if "Cont no." in current_cont:
                        current_cont["Description"] = "\n".join(desc_lines)
                        containers.append(current_cont)
                        current_cont = {}
                        desc_lines = []
                        found_carton = False
                        
                    # Extract the type (e.g. 1 CONT. 40'X9'6" HIGH CUBE CONT.)
                    # Just take everything after the quantity
                    m = re.search(r'\d+\s*[A-Z\.]+\s*(.*)', col_desc_text)
                    if m:
                        current_cont["Cont type"] = m.group(1).replace("SLAC*", "").strip()
                    else:
                        current_cont["Cont type"] = col_desc_text.replace("SLAC*", "").strip()
                        
                # Check for Cont no
                cont_no_match = re.search(r'[A-Z]{4}\s*\d{7}', col_left_text)
                if cont_no_match:
                    if "Cont no." in current_cont: # Rare case: type wasn't found but new cont no
                        current_cont["Description"] = "\n".join(desc_lines)
                        containers.append(current_cont)
                        current_cont = {}
                        desc_lines = []
                        found_carton = False
                        
                    current_cont["Cont no."] = cont_no_match.group(0).replace(" ", "")
                    
                    # Also extract carton/weight/measure from this line
                    if "CARTON" in col_desc_text.upper() or "PKG" in col_desc_text.upper():
                        current_cont["Total carton"] = col_desc_text.strip()
                        found_carton = True
                    
                    if col_weight_text and not re.search(r'[a-zA-Z]', col_weight_text):
                        current_cont["Total GW"] = col_weight_text.strip()
                    if col_measure_text and not re.search(r'[a-zA-Z]', col_measure_text):
                        current_cont["Total CBM"] = col_measure_text.strip()

                # Check for Seal no
                seal_match = re.search(r'SEAL:\s*([A-Za-z0-9]+)', col_left_text, re.IGNORECASE)
                if seal_match:
                    current_cont["Seal no."] = seal_match.group(1)
                    expect_seal = False
                elif "SEAL" in col_left_text.upper():
                    expect_seal = True
                elif expect_seal and re.search(r'[A-Za-z0-9]', col_left_text):
                    # Exclude if it looks like a container number
                    if not re.search(r'^[A-Z]{4}\s*\d{7}$', col_left_text):
                        current_cont["Seal no."] = col_left_text.strip()
                    expect_seal = False
                    
                # Description lines
                if col_desc_text:
                    if ("CARTON" in col_desc_text.upper() or "PKG" in col_desc_text.upper()) and not found_carton:
                        current_cont["Total carton"] = col_desc_text.strip()
                        found_carton = True
                        
                        # Sometimes GW and CBM are on the CARTON line instead of Cont no line
                        if col_weight_text and not re.search(r'[A-Za-z]', col_weight_text):
                            current_cont["Total GW"] = col_weight_text.strip()
                        if col_measure_text and not re.search(r'[A-Za-z]', col_measure_text):
                            current_cont["Total CBM"] = col_measure_text.strip()
                            
                    elif found_carton:
                        # Append to description
                        # Skip if it's the "SLAC*" part or just empty
                        if "SLAC" not in col_desc_text.upper():
                            # Remove garbage footer fragments
                            cleaned_desc = col_desc_text.strip()
                            if cleaned_desc and not re.search(r'(?i)(a nd 7 \(3 \)|warranty as to|RECEIVED by the|Currency:|TERMS AND CONDITIONS|loading, whichever|the Carrier)', cleaned_desc):
                                desc_lines.append(cleaned_desc)
                            
        if current_cont:
            current_cont["Description"] = "\n".join(desc_lines)
            containers.append(current_cont)

        return containers
