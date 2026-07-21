# Version Update Guide (Release Guide)

This document notes the necessary steps whenever you want to release a new update for the **Logistics Bill Extractor** software so that users can receive the update automatically.

## BEFORE BUILDING THE .EXE FILE

Every time you update to a new version (for example, from `1.0.1` to `1.0.2`), you **MUST** change the version number in the following 3 files to ensure consistency:

1. **`updater.py`**
   Find the `CURRENT_VERSION` line and modify it:
   ```python
   CURRENT_VERSION = "1.0.2"
   ```

2. **`installer.iss`** (If you use Inno Setup to create the installation file)
   Modify the following 2 lines to match the new version:
   ```ini
   AppVersion=1.0.2
   OutputBaseFilename=Setup_LogisticsBillExtractor_v1.0.2
   ```

3. **`version.json`**
   Update the version, download link, and release notes:
   ```json
   {
     "version": "1.0.2",
     "download_url": "https://github.com/Thu-sunrise/Logistics-Bill-Extractor/releases/download/v1.0.2/LogisticsBillExtractor.exe",
     "changelog": "- Feature A\n- Bug fix B"
   }
   ```

---

## RELEASE PROCESS

After changing the version number in the 3 files above, follow these steps in order:

**Step 1: Build (package) the application**
- Run the PyInstaller or Nuitka command (the tool you are using) to package the source code into a new `.exe` file.
- If using Inno Setup, run the `installer.iss` file to create the complete `.exe` installation file.

**Step 2: Push code to GitHub**
- Commit all changes (including the new code and the updated `version.json` file).
- Push to the `main` branch.
*(At this point, the user's app will scan the `version.json` file on Git and know there is a new version).*

**Step 3: Create a Release on GitHub**
1. Access the GitHub repo, go to the **Releases** section > **Draft a new release**.
2. Create a tag that matches the download link, for example: `v1.0.2`.
3. Set the **Release title** (Example: *Logistics Bill Extractor v1.0.2*).
4. Enter a description of the new features (copy from the changelog).
5. **Drag and drop the new `.exe` file (from Step 1) into the attachment box (Assets).** Make sure the file name matches the name in your `download_url`.
6. Click **Publish release**.

Done! Now when users open the app, they will receive a notification of the new update.
