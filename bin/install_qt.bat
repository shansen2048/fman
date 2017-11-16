set _QT_SRC_ROOT=C:\Users\Michael\Temp\qt-everywhere-opensource-src-5.6.2
set INSTALL_LOCATION=C:\Users\Michael\dev\fman\cache\Qt-5.6.2

CALL "c:\Program Files (x86)\Microsoft Visual Studio 14.0\VC\vcvarsall.bat"
SET PATH=%_QT_SRC_ROOT%\qtbase\bin;%_QT_SRC_ROOT%\gnuwin32\bin;C:\Users\Michael\AppData\Local\Programs\Python\Python35-32;%PATH%
cd %_QT_SRC_ROOT%
set _QT_SRC_ROOT=

configure -prefix %INSTALL_LOCATION% -release -opensource -no-accessibility -nomake examples -nomake tests
jom module-qtbase
jom module-qtbase-install_subtargets