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

export PYTHONPATH="$PROJECT_DIR/src/main/python:$PROJECT_DIR/src/unittest/python:$PROJECT_DIR/src/integrationtest/python"

# git status
alias status='git status'

# git add
alias add='git add'

# git commit
alias commit='git commit'

# git push
alias push='git push'

compile() {
	pyinstaller -y \
		--distpath "$PROJECT_DIR/target/dist" \
		--workpath "$PROJECT_DIR/target/build" \
		"$PROJECT_DIR/src/main/fman.spec"
}

test() {
	python -m unittest fman_unittest fman_integrationtest
}

alias run='target/dist/fman/fman'

alias clean='rm -rf target'