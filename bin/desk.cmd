SET ROOT=c:\Users\Michael\dev\fman
CD %ROOT%
CALL venv\scripts\activate.bat
DOSKEY clean=python build.py clean
DOSKEY freeze=python build.py freeze $*
DOSKEY installer=python build.py installer $*
DOSKEY test=python build.py test $*
DOSKEY release=python build.py release $*
DOSKEY run=python build.py run $*