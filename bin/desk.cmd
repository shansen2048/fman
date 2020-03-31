SET ROOT=c:\Users\Michael\dev\fman
CD %ROOT%
CALL venv\scripts\activate.bat
DOSKEY run=python build.py run $*
DOSKEY clean=python build.py clean
DOSKEY freeze=python build.py freeze $*
DOSKEY installer=python build.py installer $*
DOSKEY sign_installer=python build.py sign_installer $*
DOSKEY tests=python build.py test $*
DOSKEY release=python build.py release $*