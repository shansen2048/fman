# fman.sh
#
# Description: desk for doing work on fman.
# (see https://github.com/jamesob/desk)

# To install this file, symlink it to your local desks directory:
#   ln -s <ABSOLUTE PATH TO THIS FILE> ~/.desk/desks/fman.sh
# You can then switch to the desk with the command:
#   desk . fman

# Find the directory this script lies in, even when the script is called via a
# symlink, as per the installation instructions above. Copied from
# http://stackoverflow.com/a/246128/1839209:
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  DIR="$( cd -P "$( dirname "$SOURCE" )" && pwd )"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
THIS_SCRIPT_DIR="$( cd -P "$( dirname "$SOURCE" )" && pwd )"

PROJECT_DIR="$THIS_SCRIPT_DIR/.."

cd "$PROJECT_DIR"
source venv/bin/activate

PS1="(fman) \h:\W \u\$ "

MAIN_PYTHON_PATH=$PROJECT_DIR/src/main/python
TEST_PYTHON_PATH=$MAIN_PYTHON_PATH:$PROJECT_DIR/src/unittest/python:$PROJECT_DIR/src/integrationtest/python

alias compile='cx_Freeze build'

alias package='cx_Freeze bdist_dmg'

test() {
	PYTHONPATH=$TEST_PYTHON_PATH python -m unittest fman_unittest fman_integrationtest
}

alias run='$PROJECT_DIR/build/exe.macosx-10.6-intel-3.4/fman'

alias shell='PYTHONPATH=$MAIN_PYTHON_PATH python'

alias clean='rm -rf "$PROJECT_DIR/build"'

function cx_Freeze {
	# Because of cx_Freeze bug #128
	# (https://bitbucket.org/anthony_tuininga/cx_freeze/issues/128), we can't
	# specify cx_Freeze's output directory via option 'build_exe' wihout
	# breaking bdist_mac. cx_Freeze thus always produces its output in the
	# build/ subdirectory of the current directory. Ensure that this directory
	# is inside $PROJECT_DIR at least by spawning a sub-shell (cd ...; ...):
	(cd $PROJECT_DIR; PYTHONPATH=$MAIN_PYTHON_PATH python src/main/python/setup.py $1)
}