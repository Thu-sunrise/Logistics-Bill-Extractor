import os
import re
import pdfplumber

COLUMNS = [
    "File name", "Carrier", "Booking", "Bill no.", "Shipper", "Consignee", 
    "Notify party 1", "Notify party 2", "Notify party 3", "Remark",
    "POR", "POL", "Vessel name", "Voyage number", "POD", "Place of delivery",
    "Cont no.", "Seal no.", "Total carton", "Cont type",
    "Total GW", "Tare", "Total CBM", "ATD", "Freight", "Description"
]

class BaseExtractor:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.carrier_name = "UNKNOWN"
        self.asterisk_note = ""

    def get_empty_row(self):
        """Initialize an empty row according to COLUMNS, with pre-assigned file name and carrier."""
        row = {col: "" for col in COLUMNS}
        row["File name"] = os.path.basename(self.pdf_path)
        row["Carrier"] = self.carrier_name
        return row

    def parse_vessel_voyage(self, text):
        """Extract Vessel Name, Voyage Number, and any remaining text."""
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
        """Split a string based on multiple spaces (2 or more) to separate horizontally aligned columns."""
        parts = re.split(r'\s{2,}', text.strip())
        if len(parts) >= 2:
            return parts[0], parts[1]
        return text.strip(), ""

    def extract_dynamic_left_block(self, page, top_keyword, bottom_keyword, x_min=0, x_max=230, anchor_x_range=None, top_margin=5):
        """
        Extract a text block from a left-aligned area using dynamic bounding boxes 
        (Dynamic BBox) based on top and bottom anchor keywords.
        """
        bbox = self.get_dynamic_bbox(page, top_keyword, bottom_keyword, x_min, x_max, anchor_x_range, top_margin)
        if bbox:
            text = self.extract_text_by_bbox(page, bbox)
            return text if text else ""
        return ""

    def extract_description_by_bbox(self, top_kw_list, bottom_kw_list, x_range=(210, 460), pages_to_read=2):
        """Extract the description block using bounding boxes with dynamically calculated Y-axis boundaries."""
        desc_lines = []
        with pdfplumber.open(self.pdf_path) as pdf:
            pages_to_read = min(pages_to_read, len(pdf.pages))
            for page in pdf.pages[:pages_to_read]:
                if page.page_number > 1:
                    if self.find_word_bbox(page, 'Shipper', x_range=(0, page.width/2)) or self.find_word_bbox(page, 'Vessel', x_range=(0, page.width/2)):
                        break
                        
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
                
                # Pass 2: Find footer
                if top_y:
                    for w in words:
                        text_up = w['text'].upper()
                        if any(k in text_up for k in bottom_kw_list):
                            if w['top'] > top_y + 10:
                                if bottom_y is None or w['top'] < bottom_y:
                                    bottom_y = w['top']
                
                    if bottom_y is None:
                        bottom_y = page.height - 50

                    min_x, max_x = x_range
                    
                    extracted_cols = self.extract_columns_by_x_ranges(
                        page,
                        col_x_ranges={"Description": (min_x, max_x)},
                        y_range=(top_y, bottom_y)
                    )
                    
                    for row in extracted_cols:
                        text = row.get("Description", "")
                        if text:
                            # Skip container lines (specific to generic formats)
                            if re.match(r'^[A-Z]{4}[0-9]{7}', text) or '/FCL' in text: continue
                            if re.search(r'/\s*\d+\s*(CARTONS|PACKAGES)', text): continue
                            desc_lines.append(text)
                        
        return "\n".join(desc_lines)

    def find_word_bbox(self, page, keyword, x_range=None, case_sensitive=False, exact_match=False):
        """
        Find the first word containing the keyword.
        An optional x_range (min_x, max_x) can be used to narrow the search area.
        Accepts a string or a list of strings (as fallback keywords).
        """
        words = page.extract_words()
        
        if isinstance(keyword, str):
            keywords = [keyword]
        else:
            keywords = keyword
            
        for w in words:
            for kw in keywords:
                text_to_check = w['text'] if case_sensitive else w['text'].upper()
                kw_to_check = kw if case_sensitive else kw.upper()
                
                match = (kw_to_check == text_to_check) if exact_match else (kw_to_check in text_to_check)
                
                if match:
                    if x_range:
                        min_x, max_x = x_range
                        if not (min_x <= w['x0'] <= max_x):
                            continue
                    return w
        return None

    def get_dynamic_bbox(self, page, top_keyword, bottom_keyword, x_min, x_max, anchor_x_range=None, top_margin=5):
        """
        Calculate a dynamic bounding box based on 2 anchor keywords.
        The bottom of the top_keyword becomes y_min (plus a margin to avoid capturing overprinted headers).
        The top of the bottom_keyword becomes y_max.
        anchor_x_range allows overriding the search area for anchors.
        """
        search_range = anchor_x_range if anchor_x_range else (x_min, x_max)
        top_word = self.find_word_bbox(page, top_keyword, x_range=search_range)
        bottom_word = self.find_word_bbox(page, bottom_keyword, x_range=search_range)
        
        if top_word and bottom_word:
            bbox = (x_min, top_word['bottom'] + top_margin, x_max, bottom_word['top'] - 2)
        elif top_word:
            # If bottom not found, extend to a max height of 100 to avoid capturing the whole page
            bbox = (x_min, top_word['bottom'] + top_margin, x_max, top_word['bottom'] + 100)
        elif bottom_word:
            # If top not found, start from top of page
            bbox = (x_min, 50, x_max, bottom_word['top'] - 2)
        else:
            bbox = None
            
        return bbox

    def extract_text_by_bbox(self, page, bbox):
        """
        Extract text from a specific bounding box (x0, top, x1, bottom).
        Uses layout=True to handle deduplication of overprinted (bold) text.
        """
        try:
            cropped = page.crop(bbox)
            text = cropped.extract_text(layout=True)
            if text:
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                return '\n'.join(lines)
            return ""
        except ValueError:
            # Bbox might be outside page dimensions
            return ""

    def group_words_by_y(self, words, y_tolerance=4.0):
        """
        Group words into lines based on their Y (top) coordinates in O(N log N) time.
        """
        if not words:
            return {}
            
        sorted_words = sorted(words, key=lambda w: w['top'])
        line_words = {}
        
        current_top = sorted_words[0]['top']
        line_words[current_top] = [sorted_words[0]]
        
        for w in sorted_words[1:]:
            if abs(current_top - w['top']) < y_tolerance:
                line_words[current_top].append(w)
            else:
                current_top = w['top']
                line_words[current_top] = [w]
                
        return line_words

    def clean_header(self, text, keyword_pattern):
        """
        Removes matched headers from the start of the text string.
        keyword_pattern should be a regex string, e.g. r'^(Shipper/Exporter|Shipper)'
        """
        import re
        if not text: return ""
        pattern = keyword_pattern + r'.*?\n'
        return re.sub(pattern, '', text, flags=re.IGNORECASE).strip()

    def extract_container_no(self, text):
        """
        Extracts a container number (4 letters + 7 digits) from the text.
        """
        import re
        if not text: return None
        match = re.search(r'[A-Z]{4}\s*\d{7}', text.upper())
        if match:
            return match.group(0).replace(" ", "")
        return None

    def extract_columns_by_x_ranges(self, page, col_x_ranges, y_range=None):
        """
        Extract text grouped by X coordinate ranges (columns).
        col_x_ranges: dict containing {column_name: (min_x, max_x)}
        y_range: tuple containing (min_y, max_y) to limit the search area
        Returns: a list of dictionaries [{"column_name": "text", ...}, ...] for each line
        """
        words = page.extract_words()
        if y_range:
            min_y, max_y = y_range
            words = [w for w in words if min_y <= w['top'] and w['top'] < max_y]
            
        line_words = self.group_words_by_y(words)
        
        extracted_lines = []
        for top in sorted(line_words.keys()):
            sorted_words = sorted(line_words[top], key=lambda x: x['x0'])
            
            line_data = {col_name: "" for col_name in col_x_ranges.keys()}
            has_text = False
            
            for col_name, (min_x, max_x) in col_x_ranges.items():
                col_words = [w['text'] for w in sorted_words if min_x <= (w['x0'] + w['x1'])/2 <= max_x]
                if col_words:
                    text = ' '.join(col_words)
                    text = re.sub(r'\s+', ' ', text).strip()
                    if text:
                        line_data[col_name] = text
                        has_text = True
                        
            if has_text:
                extracted_lines.append(line_data)
                
        return extracted_lines

    def extract_headers(self, pdf, row):
        """Hook method to extract header fields (Shipper, Consignee, Voyage, POL, POD, etc.)"""
        pass

    def extract_footers(self, pdf, row):
        """Hook method to extract footer fields (Freight, ATD, Totals, etc.)"""
        pass

    def extract_description(self, pdf):
        """Hook method to extract the description block. Returns a string."""
        return ""

    def extract_containers(self, pdf):
        """Hook method to extract container data. Returns a list of dicts."""
        return []

    def _build_rows(self, base_row, containers):
        """Helper to multiply the base_row by the number of containers."""
        if not containers:
            return [base_row]
            
        all_rows = []
        for idx, cont in enumerate(containers):
            new_row = base_row.copy()
            new_row.update(cont) # Merge container specific keys (Cont no., Seal no., etc.)
            
            # Clear totals for subsequent rows if the container didn't explicitly provide them
            if idx > 0:
                if "Total carton" not in cont: new_row["Total carton"] = ""
                if "Total GW" not in cont: new_row["Total GW"] = ""
                if "Total CBM" not in cont: new_row["Total CBM"] = ""
                
            all_rows.append(new_row)
            
        return all_rows

    def extract(self):
        """
        Template method for extraction. 
        Child classes should override the hook methods instead of this one.
        """
        row = self.get_empty_row()
        self.asterisk_note = ""
        
        with pdfplumber.open(self.pdf_path) as pdf:
            if not pdf.pages:
                return [row]
                
            self.extract_headers(pdf, row)
            self.extract_footers(pdf, row)
            row["Description"] = self.extract_description(pdf)
            containers = self.extract_containers(pdf)
            
        rows = self._build_rows(row, containers)
        
        if self.asterisk_note:
            for r in rows:
                for key, val in r.items():
                    if isinstance(val, str) and '*' in val:
                        val = val.replace('*', ' ' + self.asterisk_note).strip()
                        r[key] = __import__('re').sub(r'\s+', ' ', val)
                        
        return rows
