export PATH=$PATH:$(ruby -rubygems -e "puts Gem.user_dir")/bin

# This is currently required for ZipFileSystemTest. It uses Python's
# ZipFile#extractall(...) to extract files containing special characters. If we
# don't set LANG (and thus, the locale), then sys.getfilesystemencoding()
# returns 'ascii' and #extractall(...) fails.
export LANG=en_US.UTF-8