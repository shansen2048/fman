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

SRC_DIR="$THIS_SCRIPT_DIR/.."

cd "$SRC_DIR"
source venv/bin/activate

PS1="(fman) \h:\W \u\$ "

# git status
alias status='git status'

# git add
alias add='git add'

# git commit
alias commit='git commit'

# git push
alias push='git push'

compile() {
	pyinstaller -y --distpath target/dist --workpath target/build src/main/fman.spec
}

alias clean='rm -rf target'