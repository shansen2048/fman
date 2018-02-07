-----BEGIN PGP SIGNED MESSAGE-----
Hash: SHA256

Format: 3.0 (quilt)
Source: python3.5
Binary: python3.5, python3.5-venv, libpython3.5-stdlib, python3.5-minimal, libpython3.5-minimal, libpython3.5, python3.5-examples, python3.5-dev, libpython3.5-dev, libpython3.5-testsuite, idle-python3.5, python3.5-doc, python3.5-dbg, libpython3.5-dbg
Architecture: any all
Version: 3.5.3-1
Maintainer: Matthias Klose <doko@debian.org>
Standards-Version: 3.9.8
Vcs-Browser: https://code.launchpad.net/~doko/python/pkg3.5-debian
Vcs-Bzr: http://bazaar.launchpad.net/~doko/python/pkg3.5-debian
Testsuite: autopkgtest
Testsuite-Triggers: build-essential, gdb, locales, python3-gdbm, python3-gdbm-dbg
Build-Depends: debhelper (>= 9), dpkg-dev (>= 1.17.11), quilt, autoconf, lsb-release, sharutils, libreadline-dev, libncursesw5-dev (>= 5.3), gcc (>= 4:6.3), zlib1g-dev, libbz2-dev, liblzma-dev, libgdbm-dev, libdb-dev, tk-dev, blt-dev (>= 2.4z), libssl-dev, libexpat1-dev, libmpdec-dev (>= 2.4), libbluetooth-dev [!hurd-i386 !kfreebsd-i386 !kfreebsd-amd64], locales [!armel !avr32 !hppa !ia64 !mipsel], libsqlite3-dev, libffi-dev (>= 3.0.5) [!or1k !avr32], libgpm2 [!hurd-i386 !kfreebsd-i386 !kfreebsd-amd64], mime-support, netbase, bzip2, time, python3:any, net-tools, xvfb, xauth
Build-Depends-Indep: python3-sphinx
Package-List:
 idle-python3.5 deb python optional arch=all
 libpython3.5 deb libs optional arch=any
 libpython3.5-dbg deb debug extra arch=any
 libpython3.5-dev deb libdevel optional arch=any
 libpython3.5-minimal deb python optional arch=any
 libpython3.5-stdlib deb python optional arch=any
 libpython3.5-testsuite deb libdevel optional arch=all
 python3.5 deb python optional arch=any
 python3.5-dbg deb debug extra arch=any
 python3.5-dev deb python optional arch=any
 python3.5-doc deb doc optional arch=all
 python3.5-examples deb python optional arch=all
 python3.5-minimal deb python optional arch=any
 python3.5-venv deb python optional arch=any
Checksums-Sha1:
 127121fdca11e735b3686e300d66f73aba663e93 15213396 python3.5_3.5.3.orig.tar.xz
 52193e4ceaaab7fe27fda950bd55020de6dbf844 218268 python3.5_3.5.3-1.debian.tar.xz
Checksums-Sha256:
 eefe2ad6575855423ab630f5b51a8ef6e5556f774584c06beab4926f930ddbb0 15213396 python3.5_3.5.3.orig.tar.xz
 fc344383001555ff33b9509879d809e3c3749de32c052d8e24b23b2b2486ff6e 218268 python3.5_3.5.3-1.debian.tar.xz
Files:
 57d1f8bfbabf4f2500273fb0706e6f21 15213396 python3.5_3.5.3.orig.tar.xz
 47efd4b4a13c6887fe19c6a004f9d4f5 218268 python3.5_3.5.3-1.debian.tar.xz

-----BEGIN PGP SIGNATURE-----

iQJEBAEBCAAuFiEE1WVxuIqLuvFAv2PWvX6qYHePpvUFAliA0OcQHGRva29AZGVi
aWFuLm9yZwAKCRC9fqpgd4+m9fZSD/9RgXH6VBWOQZ1oNQfufU+Ami8hc2MDwUs2
WTDmhfDcenFc1uEdmXsZkC6eWALwMAIrfhtKwsLfeb8Yl4Q2EPvYZdagjW9j91Ww
tVQF68LHrWoqCthjcn8fbV5PR3KU9Nkbo8IKX8lmtVqipr9aNVfM+/z2mCMKkNCj
WeUUGHF2kAZ0PphUPZeTD3ITzXEHr6puLIrBcN3GYSSIcyrPrWEwU0jcWwMpOtaq
oKdt7Jn2QBtsHCZEm5Zau1Yx140bBAmrnKpJGsZWCjBtC6FCGN/wYB4MtAdlLACi
SvVm2Pe66qx97s0tD58T8/H0eEtbFFusLqpZTuKrzqA2iVaHkXlnY44sqJxlTxst
8Ftjh8Ma1eahXgAhBN31LPCHjJVy0V+VkKpVBEr88M1Lbcvr/m9MeEC8FblsXxNp
79serJY2rPcD23wWRuHL8HRb08/6O3akAarVEzoPU8NrGnVL0yVr3CvsVJkhqEXM
B+1TuFoA9I4gR0JkX7D9g7lAcVtShoMal/jkkA6NtXZ9fBfonSiODiJBJuafjQFT
i6BOA9NwTdItV3kr9Sp1+CMnzVgHIeEvMpFofiVcqkiM4BUeCf+TvcohPfF7LiVK
B+gpQicjVn09C9uwQYBVdkzMt4mS161x6LWaeaGOp4awQP5GXffjeb+o1YDsASGq
FJ1Z/oKhFA==
=ms50
-----END PGP SIGNATURE-----
