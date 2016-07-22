;--------------------------------
;Include Modern UI

  !include "MUI2.nsh"
  !include "FileFunc.nsh"

;--------------------------------
;General

  Name "fman"
  OutFile "..\..\target\fman Setup.exe"

  ;Default installation folder
  InstallDir "$PROGRAMFILES64\fman"
  
  ;Get installation folder from registry if available
  InstallDirRegKey HKCU "Software\fman" ""

  ;Request application privileges for Windows Vista
  RequestExecutionLevel user

;--------------------------------
;Interface Settings

  !define MUI_ABORTWARNING

;--------------------------------
;Pages

  !define MUI_WELCOMEPAGE_TEXT "This wizard will guide you through the installation of fman.$\r$\n$\r$\n$\r$\nClick Next to continue."
  !insertmacro MUI_PAGE_WELCOME
  !insertmacro MUI_PAGE_DIRECTORY
  !insertmacro MUI_PAGE_INSTFILES
    !define MUI_FINISHPAGE_NOAUTOCLOSE
    !define MUI_FINISHPAGE_RUN
    !define MUI_FINISHPAGE_RUN_CHECKED
    !define MUI_FINISHPAGE_RUN_TEXT "Run fman"
    !define MUI_FINISHPAGE_RUN_FUNCTION "LaunchLink"
  !insertmacro MUI_PAGE_FINISH

  !insertmacro MUI_UNPAGE_CONFIRM
  !insertmacro MUI_UNPAGE_INSTFILES

;--------------------------------
;Languages

  !insertmacro MUI_LANGUAGE "English"

;--------------------------------
;Installer Sections

Section

  SetOutPath "$INSTDIR"
  File /r "..\..\target\fman\*"
  WriteRegStr HKCU "Software\fman" "" $INSTDIR
  WriteUninstaller "$INSTDIR\uninstall.exe"
  CreateShortCut "$SMPROGRAMS\fman.lnk" "$INSTDIR\fman.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\fman" \
                   "DisplayName" "fman"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\fman" \
                   "UninstallString" "$\"$INSTDIR\uninstall.exe$\""
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\fman" \
                   "QuietUninstallString" "$\"$INSTDIR\uninstall.exe$\" /S"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\fman" \
                   "Publisher" "Michael Herrmann"
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\fman" "EstimatedSize" "$0"

SectionEnd

;--------------------------------
;Uninstaller Section

Section "Uninstall"

  RMDir /r "$INSTDIR"
  Delete "$SMPROGRAMS\fman.lnk"
  DeleteRegKey /ifempty HKCU "Software\fman"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\fman"

SectionEnd

Function LaunchLink
  ExecShell "" "$SMPROGRAMS\fman.lnk"
FunctionEnd