# The MIT License (MIT)
# 
# Copyright (c) 2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

import sys
import os
import os.path
import re

from shlibvischeck.common.error import error
from shlibvischeck.common.process import *
from shlibvischeck.analysis.package import *

def _get_installed_packages():
  """ Returns installed Debian packages. """
  pkgs = set()
  _, out, _ = run('dpkg --get-selections')
  for l in out.split('\n'):
    name = re.split(r'\s+', l)[0]
    name = re.sub(r':.*', '', name)
    pkgs.add(name)
  return pkgs

def get_pkg_attribute(pkg, attr, src, last):
  """ Returns attribute of Debian package. """
  # Parse e.g. "Depends: libc6-dev | libc-dev, libacl1 (= 2.2.52-3), libattr1-dev (>= 1:2.4.46-8)"
  _, out, _ = run('apt-cache -q %s %s' % ('showsrc' if src else 'show', pkg))
  lines = list(filter(lambda l: l.startswith(attr + ':'), out.split('\n')))
  if last:
    lines = [lines[-1]]
  vals = []
  for l in lines:
    l = re.sub(r'^[^:]*: *', '', l)
    l = re.sub(r'\([^)]*\)', '', l)
    l = l.strip()
    vals += re.split(r' *, *', l)
  return sorted(vals)

def _get_pkg_files(pkg):
  """ Returns list of files that belong to a package. """
  # Avoid large files and dummy /.
  _, out, _ = run('dpkg -L %s' % pkg)
  return list(filter(lambda f: not re.search(r'(\.gz|\.html?|\.)$', f),
                     out.split('\n')))

# TODO: sys/types.h ?
_stdinc = ['',
           '-include stdint.h -include stddef.h',
           '-include stdio.h']

def _get_paths(lang):
  """ Returns standard compiler paths. """
#  cc = 'clang++-5.0'
  cc = 'g++'
  _, _, err = run('%s -E -v -x %s /dev/null' % (cc, lang))
  in_paths = False
  paths = []
  for l in err.split('\n'):
    if 'search starts here' in l:
      in_paths = True
    if 'End of search list' in l:
      break
    if in_paths and l[0] == ' ':
      paths.append('-I' + l[1:])
  return ' '.join(paths)

def _get_cflags(files, v=0):
  """ Collect CFLAGS from pkgconfigs. """

  cflags = []

  c_paths = _get_paths('c')
  cxx_paths = _get_paths('c++')

  def add_variants(f):
    for lang in [c_paths, cxx_paths + ' -x c++']:
      for add_incs in ['', _stdinc]:
        cflags.append(' '.join([lang, add_incs, f]))

  for pc in filter(lambda pkg: pkg.endswith('.pc'), files):
    stem, _ = os.path.splitext(os.path.basename(pc))
    os.environ['PKG_CONFIG_PATH'] = os.path.dirname(pc)
    _, out, _ = run('pkg-config --print-errors --cflags %s' % stem)
    out = out.strip()  # Trailing \n
    if out:
      add_variants(out)
  # In case no .pc files are present
  if not cflags:
    add_variants('')

  return cflags

def analyze_debian_package(pkg, permissive, v=0):
  """ Retuns erroneously exported private package symbolds. """

  for exe in ['aptitude', 'apt-cache', 'pkg-config']:
    if not is_runnable(exe):
      error("'%s' not installed" % exe)

  # Install all binary packages
  pkgs = get_pkg_attribute(pkg, 'Binary', True, True)
  pkgs = list(filter(lambda p: not p.endswith('-udeb'), pkgs))
  pkgs = list(filter(lambda p: not p.endswith('-doc'), pkgs))
  pkgs = list(filter(lambda p: not p.endswith('-dbg'), pkgs))
  dev_pkgs = list(filter(lambda p: p.endswith('-dev'), pkgs))
  if v > 0:
    print("%s packages: %s" % (pkg, ' '.join(pkgs)))
    print("%s dev packages: %s" % (pkg, ' '.join(dev_pkgs)))

  installed_pkgs = _get_installed_packages()

  files = []
  for p in pkgs:  # Install single package at a time, in case some of them are missing
    if p in installed_pkgs:
      if v > 0:
        print("Not installing package '%s' (already installed)" % p)
    else:
      if v > 0:
        print("Installing package '%s'..." % p)
      # Use Aptitude to automatically resolve conflicts.
      run('sudo aptitude install -y -q=2 %s' % p)  # sudo apt-get install -qq -y $p
    files += _get_pkg_files(p)

  # TODO: use dedicated flags for files from each package
  cflags = _get_cflags(files, v)

  spurious_syms = analyze_package(pkg, files, cflags, permissive, v)
  if spurious_syms:
    print("The following exported symbols in package '%s' are private:\n  %s"
          % (pkg, '\n  '.join(spurious_syms)))
  else:
    print("No private exports in package '%s'" % pkg)

  return True
