SET ROOT=c:\Users\Michael\dev\fman
CD %ROOT%
CALL venv\scripts\activate.bat
DOSKEY clean=python build.py clean
DOSKEY exe=python build.py exe $*
DOSKEY installer=python build.py installer $*
DOSKEY test=python build.py test $*
DOSKEY run=python build.py run $*