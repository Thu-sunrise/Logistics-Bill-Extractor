# Logistics Bill Extractor

**Author:** Thu-sunrise

**Logistics Bill Extractor** is a powerful Desktop software built with Python, assisting logistics companies in fully automating the data extraction process from PDF Bill of Lading files and accurately exporting to Excel format.

---

## Key Features

- **Multi-Carrier Support:** 
  The software uses Object-Oriented Programming (OOP) and the Factory Pattern to identify and extract data for many major global shipping lines including:
  - ONE (Ocean Network Express)
  - MSC (Mediterranean Shipping Company)
  - HMM (Hyundai Merchant Marine)
  - OOCL (Orient Overseas Container Line)
  - ZIM Integrated Shipping Services
  - SJJ
- **Batch Processing:** Select a folder and the software will automatically scan and process hundreds of PDF files in just a few seconds.
- **Auto-Update:** Integrated with an automatic mechanism connecting to GitHub Releases to download and upgrade the software without user intervention.
- **Easy to Use:** Simple Graphical User Interface (GUI) using Tkinter, allowing Non-Tech users to easily operate via the `.exe` installer.

---

## Documentation

Please refer to the following documents for detailed information:
- **[User Manual (How to Install & Use)](docs/user_manual.md)**
- **[Technical Architecture & File Structure](docs/architecture.md)**

---

## Development Guide (For Developers)

### 1. Environment Setup
Create a Virtual Environment and install the necessary libraries:
```bash
pip install -r requirements.txt
```
*(Core libraries include: `pdfplumber`, `pandas`, `openpyxl`)*

### 2. Run Application (Debug Mode)
```bash
python app.py
```

### 3. Packaging & Building `.exe` file
The project uses **Nuitka** to compile Python source code into C code to increase security, speed up performance, and avoid false positives by antivirus software (like Windows Defender).
```bash
python -m nuitka --standalone --mingw64 --plugin-enable=tk-inter --windows-console-mode=disable --windows-icon-from-ico=icon.ico --output-filename=LogisticsBillExtractor.exe app.py
```

---

## Deployment

The `installer.iss` (Inno Setup Script) file is used to compress the Nuitka build folder (`app.dist`) into a single installer (`Setup_LogisticsBillExtractor_v1.0.0.exe`).
- Open the `.iss` file with **Inno Setup**.
- Press **Compile** (F9) to export the installation file.

---

## Contributing

If you want to contribute a new extraction module for a new carrier, please:
1. Create a new Extractor class in the `core/extractors/` folder (inheriting from `BaseExtractor`).
2. Register that class in `core/extractor_factory.py`.
3. Test the results with a sample PDF file from that carrier.

## License
This project is licensed under the terms of the [MIT License](LICENSE).
