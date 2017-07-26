SET ROOT=c:\Users\Michael\dev\fman
SET GOPATH=%ROOT%\src\main\go
SET PATH=%ROOT%\lib\windows\Qt-5.6.1-1\bin;%GOPATH%\bin;%PATH%
CD %ROOT%
CALL venv\scripts\activate.bat
DOSKEY clean=python build.py clean
DOSKEY exe=python build.py exe $*
DOSKEY setup=python build.py setup $*
DOSKEY run=cmd /C "set "PYTHONPATH=src\main\python;src\main\resources\base\Plugins\Core" && python src\main\python\fman\main.py"