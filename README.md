[![License](http://img.shields.io/:license-MIT-blue.svg)](https://github.com/yugr/ShlibVisibilityChecker/blob/master/LICENSE.txt)
[![Build Status](https://travis-ci.org/yugr/ShlibVisibilityChecker.svg?branch=master)](https://travis-ci.org/yugr/ShlibVisibilityChecker)

# What's this?

ShlibVisibilityChecker is a small tool which locates internal symbols
that are unnecessarily exported from shared libraries.
Such symbols are undesirable because they cause
* slower startup time (due to slower relocation processing by dynamic linker)
* performance slowdown (due to indirect function calls, compiler's inability to optimize exportable functions e.g. inline them, effective turnoff of `--gc-sections`)
* leak of implementation details (if some clients start to use private functions instead of regular APIs)
* bugs due to runtime symbol clashing (see [Flameeyes blog](https://flameeyes.blog/2008/02/09/flex-and-linking-conflicts-or-a-possible-reason-why-php-and-recode-are-so-crashy/) for real-world examples)

ShlibVisibilityChecker compares APIs declared in public headers against APIs exported from shared libraries
and warns about discrepancies.
In majority of cases such symbols are internal library symbols which should be hidden
(in rare cases these are internal symbols which are used by other libraries or executables
in the same package and `debiancheck` tries hard to not report such cases).

Such discrepancies should then be fixed by recompiling package
with `-fvisibility=hidden` (see [here](https://gcc.gnu.org/wiki/Visibility) for details).
A typical fix, for typical Autoconf project can be found [here](https://github.com/cacalabs/libcaca/issues/33#issuecomment-387656546).

ShlibVisibilityChecker _not_ meant to be 100% precise but rather provide assistance in locating packages
which may benefit the most from visibility annotations (and to understand how bad the situation
with visibility is in modern distros).

# How to use

Main tool is `scripts/debiancheck` script which locates symbols that are exported from
package's shared libraries but are not declared in it's headers.

To apply it to a package, run
```
$ scripts/debiancheck libacl1
Binary symbols not in public interface of acl:
  __acl_extended_file
  __acl_from_xattr
  __acl_to_xattr
  __bss_start
  closed
  _edata
  _end
  _fini
  head
  high_water_alloc
  _init
  next_line
  num_dir_handles
  walk_tree
For a total of 14 (25%).
```
Add `--permissive` to not display autogenerated symbols like `_init` or `_edata` (caused by [ld linker scripts](https://sourceware.org/ml/binutils/2018-04/msg00326.html) and [libgcc startup files](https://gcc.gnu.org/ml/gcc-help/2018-04/msg00097.html)).

A list of packages for analysis can be obtained from [Debian rating](https://popcon.debian.org/by_vote):
```
$ curl https://popcon.debian.org/by_vote 2>/dev/null | awk '/^[0-9]/{print $2}' | grep '^lib' > by_vote
$ scripts/debiancheck $(head -500 by_vote | tr '\n' ' ')
```

You can also collect interfaces from headers and shlibs manually and compare them:
```
$ bin/read_header_api --cflags="-I/usr/include -I$AUDIT_INSTALL/include -I/usr/lib/llvm-5.0/lib/clang/5.0.0/include" $AUDIT_INSTALL/include/*.h > public_api.txt
$ scripts/read_binary_api --permissive $AUDIT_INSTALL/lib/*.so* > exported_api.txt
$ comm -13 public_api.txt exported_api.txt
```

# How to install

To perform the analysis `debiancheck` installs new Debian packages so it's recommended to run it under chroot.
There are many instructions on setting up chroot e.g. [this one](https://github.com/yugr/debian_pkg_test).
To run analysis you'll need to install `file` and `aptitude`.

To build support tools you'll need to install `clang-5.0`, `llvm-5.0`, `libclang-5.0-dev`
(in addition to standard `gcc` and `make`). Then just do `make clean all` in tool's directory.

# Issues and limitations

At the moment tool works only on Debian-based systems (e.g. Ubuntu).
This should be fine as buildscripts are the same across all distros
so detecting issues on Ubuntu would serve everyone else too.

An important design issue is that the tool can not detect symbols which are used indirectly
i.e. not through an API but through `dlsym` or explicit out-of-header prototype declaration
in source file. This happens in plugins or tightly interconnected shlibs within the same project.
Such cases should hopefully be rare.

ShlibVisibilityChecker is a heuristic tool so it will not be able to analyze all packages.
Current success rate is around 60%.
Major reasons for errors are
* not well-structured headers i.e. headers which do not \#include all their dependencies 
  (e.g. `libatasmart` [fails to include `stddef.h`](https://github.com/Rupan/libatasmart/issues/1)
  and `tdb` [fails to include `sys/types.h`](https://bugzilla.samba.org/show_bug.cgi?id=13398)).
* internal headers which should not be \#included directly (e.g. `lzma/container.h`)

Other issues:
* TODOs are scattered all over the codebase
* would be interesting to go over dependent packages and check if they use invalid symbols
* the tool is much slower than needed (ideally needs to be rewritten in combination of Python and C++)

# Trophies

The tool found huge number of packages that lacked visibility annotations. Here are some which I tried to fix:

* Bzip2: [Hide unused symbols in libbz2](https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=896750)
* Expat: [Private symbols exported from shared library](https://github.com/libexpat/libexpat/issues/195) (fixed)
* Libaudit: [Exported private symbols in audit-userspace](https://www.redhat.com/archives/linux-audit/2018-April/msg00119.html) (partially fixed)
* Gdbm: [sr #347: Add visibility annotations to hide private symbols](https://puszcza.gnu.org.ua/support/index.php?347)
* Libnfnetfilter: [\[RFC\]\[PATCH\] Hide private symbols in libnfnetlink](https://marc.info/?l=netfilter-devel&m=152481166515881) (fixed)
* Libarchive: [Hide private symbols in libarchive.so](https://github.com/libarchive/libarchive/issues/1017)
* Libcaca: [Hide private symbols in libcaca](https://github.com/cacalabs/libcaca/issues/33) (fixed)
* Libgmp: [Building gmp with -fvisibility=hidden](https://gmplib.org/list-archives/gmp-discuss/2018-April/006229.html)
* Vorbis: [Remove private symbols from Vorbis shared libs](https://github.com/xiph/vorbis/issues/43)
