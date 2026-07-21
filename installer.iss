[Setup]
AppName=LogisticsBillExtractor
AppVersion=1.0.2
DefaultDirName={pf}\LogisticsBillExtractor
DefaultGroupName=LogisticsBillExtractor
OutputDir=.\Output
OutputBaseFilename=Setup_LogisticsBillExtractor_v1.0.2
Compression=lzma
SolidCompression=yes
SetupIconFile=icon.ico

[Files]
; Đường dẫn này trỏ vào thư mục app.dist mà Nuitka sinh ra
Source: "app.dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\LogisticsBillExtractor"; Filename: "{app}\LogisticsBillExtractor.exe"
Name: "{commondesktop}\LogisticsBillExtractor"; Filename: "{app}\LogisticsBillExtractor.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Tạo biểu tượng trên màn hình Desktop"; GroupDescription: "Additional icons:"
