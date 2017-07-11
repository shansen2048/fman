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

function build {
	python build.py "$@"
}

alias clean='python build.py clean'
alias exe='python build.py exe'
alias installer='python build.py installer'
alias publish='python build.py publish'
alias release='python build.py release'
alias app='python build.py app'
alias dmg='python build.py dmg'
alias deb='python build.py deb'
alias test='python build.py test'
alias arch-docker-image='python build.py arch_docker_image'
alias arch='python build.py arch'
alias ubuntu-docker-image='python build.py ubuntu_docker_image'
alias ubuntu='python build.py ubuntu'