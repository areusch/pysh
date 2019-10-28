"""Defines code that generates the script header."""

from __future__ import print_function
import base64
import collections
import os
import re
import stat
import sys
import zipfile

if sys.version_info[0] == 3:
  import io
  BytesIO = io.BytesIO
else:
  import cStringIO
  BytesIO = cStringIO.StringIO



SHBANG_LINE = "#!/bin/sh -e"


PYSH_INFO_SECTION_NAME = 'PySH Information'

PYSH_INFO_SECTION = """\
# This is a PySH script, a shell script written in Python.
# It requires Python 3 and the `pysh` package.
""".split('\n')


PYSH_BOOTSTRAP_SECTION_NAME = 'PySH Bootstrap'


_EMBEDDED_MODULE_NOTICE = '# PySH: Module embedded below'


_NORMAL_PY_SCRIPT = """\
from __future__ import print_function
import sys
try:
  import pysh
except ImportError as e:
  sys.exit(253)
pysh.main('$0')
"""


_DISTRIBUTABLE_PY_SCRIPT = """\
from base64 import b64decode
import sys
import tempfile
with open('$0') as script_f:
  with tempfile.NamedTemporaryFile(suffix='.zip') as f:
    f.write(b64decode(eval(script_f.read().split('{_EMBEDDED_MODULE_NOTICE}\\n', 1)[1])))
    f.flush()
    sys.path.append(f.name)
    import pysh
    pysh.main('$0')
""".format(_EMBEDDED_MODULE_NOTICE=_EMBEDDED_MODULE_NOTICE)


_ESCAPE_SEQ = re.compile(r'\\(?P<char>.)')


def make_bootstrap_lines(dist):
  script = _DISTRIBUTABLE_PY_SCRIPT if dist else _NORMAL_PY_SCRIPT
#  script = "'foo\\n'"
#  m = _ESCAPE_SEQ.search(script)
#  print('m={!r} {!r}'.format(m.group(1), m.groupdict()))
  _py = _ESCAPE_SEQ.sub(r'\\\\\\\1', script).replace('\n', '\\n')
#  print('py={!s}'.format(_py), file=sys.stderr)

  sh_evals = (
    ('py="{_py}"'.format(_py=_py), 'code=0; set -o pipefail'),
    ('python_bin=`which python3`;',),
    ('if [ -n \"${python_bin}\" ]; then ',
     '(', 'echo', '\"${py}\"', '|', '(', '${python_bin}',
     '/dev/fd/3', '$@', '0<&4', ')', '3<&0', '; exit $?)', '4<&0 || code=$?;',
     'if [ $code -ne 253 ]; then exit $code; fi; fi'),
    ('python_bin=`which python`;', 'code=0'),
    ('(', 'echo', '\"${py}\"', '|', '(', '${python_bin}',
     '/dev/fd/3', '$@', '0<&4', ')', '3<&0', ')', '4<&0 || code=$?;'),
    ('if [ $code -eq 253 ]; then',
     'echo "pysh: script $0 requires the pysh package. Install it with:" >&2',
     'echo "      $ pip install https://github.com/areusch/pysh/archive/master.zip"; ',
     'fi'),
    ('exit', '$code'),
  )
#  print('shevals={!s}'.format(sh_evals[1][1]), file=sys.stderr)

  return [' '.join(['"{}"'.format(_ESCAPE_SEQ.sub(r'\\\\\\\1', x).replace('"', '\\"').replace('$', '\$'))
                    for x in ["eval"] + list(e)])
    for e in sh_evals]


Metadata = collections.namedtuple('Metadata', ('leading', 'name', 'content'))


class ScriptError(Exception):
  def __init__(self, line_number, col_number, message):
    self.line_number = line_number
    self.col_number = col_number
    self.message = message

  def __str__(self):
    if self.line_number is None:
      return self.message
    return '{}: {}: {}'.format(self.line_number, self.col_number, self.message)


class Parser:

  def __init__(self, f):
    self._peek_line_number = 0
    self._peek_line = None
    self._last_newline = False
    self._stack_start_line_number = None
    self._stack = []
    self._rewind_peek_line = False
    self._f = f

  def __iter__(self):
    return self

  def _commit_peek_line(self):
    if self._peek_line is not None:
      self._stack.append(self._peek_line)

      if self._stack_start_line_number is None:
        self._stack_start_line_number = self._peek_line_number

      self._peek_line = None

  def peek(self):
    if not self.is_peek_line_valid:
      line = '' if self._last_newline else None
      try:
        line = next(self._f)
        self._last_newline = line and line[-1] == '\n'
        line = line.rstrip('\r\n')
        self._peek_line_number += 1
      finally:
        self._peek_line = line

    return self._peek_line

  @property
  def is_peek_line_valid(self):
    return self._peek_line is not None

  def next(self):
    if self._rewind_peek_line:
      self._rewind_peek_line = False
      return self._peek_line

    if self.is_peek_line_valid:
      self._commit_peek_line()

    line = self.peek()

    return line

  def __next__(self):
    return self.next()

  @property
  def stack_start_line_number(self):
    return self._stack_start_line_number

  @property
  def peek_line_number(self):
    return self._peek_line_number

  def fetch(self, include_peek_line=True):
    if include_peek_line and self.is_peek_line_valid:
      self._commit_peek_line()

    to_return = (self._stack_start_line_number, self._stack)
    self._stack = []
    self._stack_start_line_number = None

    if not include_peek_line:
      self._rewind_peek_line = True

    return to_return


class ParsedScript:
  """Encodes a parsed PySH script."""

  def __init__(self, metadata, content, dist):
    self._metadata = collections.OrderedDict(metadata)
    self._content = content
    self._dist = dist

  @property
  def metadata(self):
    return self._metadata

  @property
  def content(self):
    return self._content

  METADATA_START_RE = re.compile(r'^# ([A-Za-z 0-9-]+) -->$')
  METADATA_START_FMT = '# {} -->\n'
  METADATA_END_RE = re.compile(r'^# <-- ([A-Za-z 0-9-]+)$')
  METADATA_END_FMT = '# <-- {}\n'

  @classmethod
  def _parse_one_metadata(cls, parser):
    for line in parser:
      m = cls.METADATA_START_RE.match(line)
      if m:
        section_name = m.group(1)

        _, leading = parser.fetch()
        leading = leading[:-1]  # Strip starting line

        break

    else:
      return None

    for line in parser:
      m = cls.METADATA_END_RE.match(line)

      if not m:
        continue

      if m.group(1) != section_name:
        raise ScriptError(
          parser.start_line_number, m.start,
          'Section end name ("%s") doesn\'t match start name ("%s")' % (
            m.group(1), section_name))

      _, lines = parser.fetch()
      return Metadata(leading=leading,
                      name=section_name,
                      content=lines[:-1])

    else:
      raise ScriptError(
        None, 0,
        'Reached end of file when looking for section "%s" end marker' % (
          section))

  @classmethod
  def parse(cls, script_f, force=False):
    parser = Parser(script_f)

    shbang = next(parser)
    missing_shbang = not shbang.startswith('#!')
    if not missing_shbang:
      if shbang != SHBANG_LINE and force:
        raise UnrecognizedScriptError(
          parser.line_number, 0,
          'Shbang line is for a different parser')

    # Throw away the recognized shbang part.
    _, f_shbang_lines = parser.fetch()

    # Parse metadata.
    metadata = collections.OrderedDict()
    while True:
      md = cls._parse_one_metadata(parser)
      if md is None:
        break

      metadata[md.name] = md

    dist = False
    _, content = parser.fetch()
    for i, line in enumerate(content):
      if line == _EMBEDDED_MODULE_NOTICE:
        content = content[:i]
        dist = True
        break

    if missing_shbang and not metadata:
      content = f_shbang_lines + content

    return cls(metadata, content, dist)

  def normalize(self, dist):
    """Add required sections to the pysh file."""
    old_md = self._metadata
    self._metadata = collections.OrderedDict()

    exclude_sections = (PYSH_INFO_SECTION_NAME, PYSH_BOOTSTRAP_SECTION_NAME)
    self.metadata[PYSH_INFO_SECTION_NAME] = Metadata(
      leading=['#'], name=PYSH_INFO_SECTION_NAME, content=PYSH_INFO_SECTION)

    for s in old_md:
      if s not in exclude_sections:
        old = old_md[s]
        if not old.leading:
          old = Metadata(leading=[''], name=old.name, content=old.content)

        self.metadata[s] = old_md[s]

    bootstrap_section_lines = make_bootstrap_lines(dist)
    self.metadata[PYSH_BOOTSTRAP_SECTION_NAME] = Metadata(
      leading=[''], name=PYSH_BOOTSTRAP_SECTION_NAME,
      content=bootstrap_section_lines)
    self._dist = dist

  def write(self, script_f):
    script_f.write('{}\n'.format(SHBANG_LINE))
    for name, metadata in self._metadata.items():
      script_f.write('\n'.join(metadata.leading))
      script_f.write('\n')
      script_f.write(self.METADATA_START_FMT.format(name))
      script_f.write('\n'.join(metadata.content))
      script_f.write('\n')
      script_f.write(self.METADATA_END_FMT.format(name))

    script_f.write('\n'.join(self._content))
    if self._dist:
      script_f.write('{}\n'.format(_EMBEDDED_MODULE_NOTICE))
      module_f = BytesIO()
      zip_f = zipfile.ZipFile(module_f, 'w', zipfile.ZIP_DEFLATED)
      top = os.path.dirname(__file__)
      for dirpath, _, files in os.walk(top):
        for file_name in files:
          if not file_name.endswith('.py'):
            continue

          zip_path = os.path.relpath(
            os.path.realpath('{}/{}'.format(dirpath, file_name)),
            os.path.dirname(top))
          with open(os.path.sep.join([dirpath, file_name]), 'rb') as f:
            zip_f.writestr(zip_path, f.read())

      zip_f.close()

      script_f.write('"""')
      b64_encoded = base64.b64encode(module_f.getvalue())
      if sys.version_info[0] == 3:
        b64_encoded = str(b64_encoded, 'utf-8')
      script_f.write(b64_encoded)
      script_f.write('"""\n')


def generate(script_path_arg, dist=False):
  if script_path_arg == '-':
    script_f = sys.stdin
  else:
    script_f = open(script_path_arg)

  try:
    parser = Parser(script_f)
    script = ParsedScript.parse(parser)
  finally:
    script_f.close()

  script.normalize(dist)

  if script_path_arg == '-':
    script_f = sys.stdout
  else:
    tmp_name = '{}.tmp'.format(script_path_arg)
    while os.path.exists(tmp_name):
      tmp_name = '{}.tmp.{}'.format(script_path_arg, random.randint(0,100))

    script_f = open(tmp_name, 'w')

  try:
    script.write(script_f)
  finally:
    script_f.close()

  if script_path_arg != '-':
    os.unlink(script_path_arg)
    os.rename(tmp_name, script_path_arg)

    st = os.stat(script_path_arg)
    if (st.st_mode & stat.S_IXUSR) == 0:
      new_mode = st.st_mode | stat.S_IXUSR
      os.chmod(script_path_arg, new_mode)
