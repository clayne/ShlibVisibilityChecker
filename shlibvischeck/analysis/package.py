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
import magic

from shlibvischeck.analysis.header import *
from shlibvischeck.analysis.elf import *
from shlibvischeck.common.error import error

def analyze_package(pkg, files, cflags, permissive, v=0):
  """ Returns erroneously exported private symbols in package shlibs. """

  shlibs = []
  hdrs = []
  elfs = []

  for f in files:
    if os.path.isfile(f):
      _, ext = os.path.splitext(f)
      if ext in ['.h', '.hpp', '.H']:
        hdrs.append(f)
      typ = magic.from_file(f)
      if (re.search(r'^ELF.*shared object', typ)
          # Need more checks to avoid PIEs
          and '/bin/' not in f):
        shlibs.append(f)
      if re.search(r'^ELF.*(shared object|executable)', typ):
        elfs.append(f)

  if not hdrs:
    error("failed to locate headers")
  if not shlibs:
    error("failed to locate any shared libs")

  if v > 0:
    print("Package headers: %s" % ' '.join(hdrs))
    print("Package shlibs: %s" % ' '.join(shlibs))

  # Collect header interfaces
  public_api = set()
  for h in hdrs:
    public_api.update(read_header_api(h, hdrs, cflags, v))

  # Collect binary interfaces
  exported_api = set()
  for f in shlibs:
    exported_api.update(read_binary_api(f, True, permissive, v))
  if v > 0:
    print("All exported APIs in package '%s':\n  %s" % (pkg, '\n  '.join(exported_api)))

  # Ignore private interfaces used by other modules in same package
  imported_api = set()
  for f in elfs:
    imported_api.update(read_binary_api(f, False, permissive))
  if v > 0:
    print("All imported APIs in package '%s':\n  %s" % (pkg, '\n  '.join(imported_api)))
  exported_api.difference_update(imported_api)

  # TODO: for C++ we may want to ignore vtables, RTTI and C++ default methods
  # (as libclang does not report them).
  # TODO: warn about missing APIs?

  return sorted(list(exported_api - public_api))
