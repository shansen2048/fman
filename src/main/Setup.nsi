;--------------------------------
;Include Modern UI

  !include "MUI2.nsh"

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
  File /r "..\..\target\exploded\*"
  WriteRegStr HKCU "Software\fman" "" $INSTDIR
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateShortCut "$SMPROGRAMS\fman.lnk" "$INSTDIR\fman.exe"

SectionEnd

;--------------------------------
;Uninstaller Section

Section "Uninstall"

  RMDir /r "$INSTDIR"
  Delete "$SMPROGRAMS\fman.lnk"
  DeleteRegKey /ifempty HKCU "Software\fman"

SectionEnd

Function LaunchLink
  ExecShell "" "$SMPROGRAMS\fman.lnk"
FunctionEnd