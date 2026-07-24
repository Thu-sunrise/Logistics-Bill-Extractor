# Logistics Bill Extractor Architecture

The project applies the **Strategy Pattern** combined with the **Factory Pattern** to ensure scalability and easy maintenance when supporting data extraction from various types of Bill of Lading across different carriers.

## 1. Core Components

### `base_extractor.py` (Base Class / Core Utilities)
- The parent class (`BaseExtractor`) defines the standard structure for all extraction results.
- Contains the `COLUMNS` list specifying mandatory information fields (including File name, Carrier, Booking, POL, POD, Description, etc.).
- Initializes an empty data frame through the `get_empty_row()` function.
- Defines powerful PDF coordinate processing utilities (Bounding Box Parsing) for more accurate extraction compared to regular regex:
  - `find_word_bbox`: Finds the coordinates of a keyword on a PDF page.
  - `get_dynamic_bbox`: Calculates the bounding area between 2 keywords (top and bottom anchors).
  - `extract_dynamic_left_block`: Extracts the text block on the left margin based on the dynamic bounding box.
  - `extract_text_by_bbox` and `extract_description_by_bbox`: Accurately extract text by coordinates, handling overprinted text or complex layouts well.
- Provides string processing utilities: `parse_vessel_voyage` (identifies Vessel/Voyage), `split_columns_by_spaces`.
- Has the `extract(self)` Template function, requiring child classes to override.

### Strategy Extractors
- Located in the `core/extractors/` directory. Current extractors include:
  - `one_extractor.py`, `msc_extractor.py`, `oocl_extractor.py`, `zim_extractor.py`
  - `sjj_extractor.py`, `hmm_extractor.py`, `cma_cgm_extractor.py`
  - `cosco_extractor.py`, `maersk_extractor.py`, `kn_extractor.py`
  - `hlo_extractor.py`, `schenker_extractor.py`
- Inherit from `BaseExtractor`.
- Responsible for containing specific extraction algorithms for the Bill form of EXACTLY 1 specific carrier (based on that carrier's layout or logic).

### `extractor_factory.py` (Router / Factory)
- Responsible for initializing the correct Extractor Class based on PDF content using a Registry Pattern.
- Takes the PDF file path as input, reads the first page's text, and dynamically iterates through the `EXTRACTORS` array.
- It calls the `@classmethod is_match(text_upper)` on each Extractor to ask if it can process the file.
- Returns the corresponding matched Extractor object for the system to perform extraction.

### `excel_exporter.py` (Data Exporter)
- Receives the result list (List of Dictionaries) from Extractors.
- Processes data columns according to the `COLUMNS` standard and exports results to an Excel file with a clear format, making it easy for users to monitor and verify.

## 2. Workflow
1. **Launch**: Users run `app.py` and select the folder containing PDF files via the UI (Tkinter).
2. **Scan files**: The system iterates through each `.pdf` file and passes the path to `extractor_factory.process_pdf(pdf_path)`.
3. **Routing**: `extractor_factory` reads the first page's text, identifies the carrier via keywords, and initializes the corresponding Extractor object (e.g., `MscExtractor(pdf_path)`).
4. **Extraction**: Calls the `extractor.extract()` method. This object scans through PDF pages, combining bounding boxes and string processing logic to collect full information into a list of row dictionaries.
5. **Aggregation**: Results from all files are aggregated into a single total List of Dict.
6. **Report Generation**: This total list is pushed through `excel_exporter.py` to create an Excel format report file (e.g., `logistics_extracted_data.xlsx`).

## 3. Procedure for adding a new carrier
To support a new carrier (e.g., COSCO), perform 3 simple steps without affecting or breaking the structure of existing carriers:
1. **Create Extractor**: Create a new file (e.g. `new_extractor.py`) in `core/extractors/` directory.
2. **Inherit & Logic**: Declare `class NewExtractor(BaseExtractor):` and override the `extract()` function (leveraging utility functions in `BaseExtractor`).
3. **Identification Logic**: Add an `@classmethod is_match(cls, text_upper)` that returns True if the text belongs to the carrier.
4. **Register Factory**: Open `core/extractor_factory.py`, import the new class, and add it to the `EXTRACTORS` array.
