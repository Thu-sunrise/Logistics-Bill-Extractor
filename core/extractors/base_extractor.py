import os
import re
import pdfplumber

# Các cột chuẩn của hệ thống
COLUMNS = [
    "File name", "Carrier", "Shipper", "Consignee", "Notify party 1",
    "POL", "Vessel name", "Voyage number", "POD", "Place of delivery",
    "Cont no.", "Seal no.", "Total carton", "Cont type",
    "Total GW", "Total CBM", "ATD", "Description"
]

class BaseExtractor:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.carrier_name = "UNKNOWN"

    def get_empty_row(self):
        """Khởi tạo một dòng trắng chuẩn theo COLUMNS, gán sẵn tên file và hãng."""
        row = {col: "" for col in COLUMNS}
        row["File name"] = os.path.basename(self.pdf_path)
        row["Carrier"] = self.carrier_name
        return row

    def parse_vessel_voyage(self, text):
        """Extracts Vessel Name, Voyage Number, and any leftover text."""
        words = text.split()
        voyage_idx = next((idx for idx in reversed(range(len(words))) if any(c.isdigit() for c in words[idx])), -1)

        if voyage_idx != -1:
            if voyage_idx + 1 < len(words) and len(words[voyage_idx+1]) <= 2:
                next_word = words[voyage_idx+1].upper()
                if not any(v in next_word for v in "AEIOUY") or next_word in ["E", "N", "S", "W", "NE", "NW", "SE", "SW", "C", "NC"]:
                    words[voyage_idx] += words.pop(voyage_idx + 1)
                    
            vessel_name = " ".join(words[:voyage_idx])
            voyage_number = words[voyage_idx]
            rest = " ".join(words[voyage_idx+1:])
            return vessel_name, voyage_number, rest
        return text, "", ""

    def split_columns_by_spaces(self, text):
        """Splits a string by multiple spaces (2 or more) to separate horizontally aligned columns."""
        parts = re.split(r'\s{2,}', text.strip())
        if len(parts) >= 2:
            return parts[0], parts[1]
        return text.strip(), ""

    def extract_left_block(self, lines, start_kw, end_kw, max_width=45):
        """Extracts text from a left-aligned block between start and end keywords."""
        block_lines = []
        in_block = False
        
        if isinstance(start_kw, str):
            start_kw = [start_kw]
        if isinstance(end_kw, str):
            end_kw = [end_kw]
            
        for line in lines:
            if any(kw in line for kw in start_kw):
                in_block = True
                continue
            if in_block:
                if any(kw in line for kw in end_kw):
                    break
                left_text = line[:max_width].strip()
                if left_text:
                    block_lines.append(left_text)
        return " | ".join(block_lines)

    def extract_description_by_bbox(self, top_kw_list, bottom_kw_list, x_range=(210, 460), pages_to_read=2):
        """Extracts description text using bounding boxes (Y-boundaries dynamically computed)."""
        desc_lines = []
        with pdfplumber.open(self.pdf_path) as pdf:
            pages_to_read = min(pages_to_read, len(pdf.pages))
            for page in pdf.pages[:pages_to_read]:
                words = page.extract_words()
                
                top_y = None
                bottom_y = None
                
                # Pass 1: Find header
                for w in words:
                    text_up = w['text'].upper()
                    if any(kw in text_up for kw in top_kw_list):
                        if top_y is None or w['bottom'] > top_y:
                            if w['bottom'] < page.height * 0.6: # Typically in upper half
                                top_y = w['bottom']
                
                # Pass 2: Find footer strictly below top_y
                if top_y:
                    for w in words:
                        text_up = w['text'].upper()
                        if any(k in text_up for k in bottom_kw_list):
                            if w['top'] > top_y + 10:
                                if bottom_y is None or w['top'] < bottom_y:
                                    bottom_y = w['top']
                
                if not top_y:
                    continue
                if not bottom_y:
                    bottom_y = page.height
                    
                top_y = max(0, top_y)
                bottom_y = min(page.height, bottom_y)
                
                # Group into lines
                line_words = {}
                for w in words:
                    if top_y <= w['top'] < bottom_y - 2:
                        matched_top = None
                        for t in line_words.keys():
                            if abs(t - w['top']) < 4:
                                matched_top = t
                                break
                        if matched_top is None:
                            matched_top = w['top']
                            line_words[matched_top] = []
                        line_words[matched_top].append(w)
                
                # Extract text within X range
                min_x, max_x = x_range
                for top in sorted(line_words.keys()):
                    sorted_words = sorted(line_words[top], key=lambda x: x['x0'])
                    full_line_text = ' '.join(w['text'] for w in sorted_words).upper()
                    
                    # Skip common noise
                    if re.match(r'^\s*-{3,}', full_line_text): continue
                    if any(kw in full_line_text for kw in top_kw_list): continue
                    if 'CONT NO' in full_line_text and 'SEAL NO' in full_line_text: continue
                    if 'TO BE CONTINUED' in full_line_text or 'ATTACHED LIST' in full_line_text: continue
                    if any(kw in full_line_text for kw in bottom_kw_list): continue
                    
                    # Skip container lines (specific to generic formats)
                    if re.match(r'^[A-Z]{4}[0-9]{7}', full_line_text) or '/FCL' in full_line_text: continue
                    if re.search(r'/\s*\d+\s*(CARTONS|PACKAGES)', full_line_text): continue
                        
                    desc_col_words = [w['text'] for w in sorted_words if min_x <= (w['x0'] + w['x1'])/2 <= max_x]
                    if desc_col_words:
                        line_str = ' '.join(desc_col_words)
                        line_str = re.sub(r'\s+', ' ', line_str).strip()
                        desc_lines.append(line_str)
                        
        return "\n".join(desc_lines)

    def extract(self):
        """
        Hàm bóc tách lõi: Các class con của từng hãng tàu (ONE, OOCL, v.v.)
        bắt buộc phải ghi đè (override) hàm này.
        """
        raise NotImplementedError("Phải ghi đè hàm extract() ở class con")
