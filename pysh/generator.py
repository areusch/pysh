"""Defines code that generates the script header."""

import collections
import os
import re


SHBANG_LINE = "#!/bin/sh -e"


PYSH_INFO_SECTION_NAME = 'PySH Information'

PYSH_INFO_SECTION = """\
# This is a PySH script, a shell script written in Python.
# It requires Python 3 and the `pysh` package.
""".split('\n')


PYSH_BOOTSTRAP_SECTION_NAME = 'PySH Bootstrap'


PYSH_BOOTSTRAP_SECTION = """\
"eval" "echo" "\\"import sys\\ntry:\\n  import pysh\\n  pysh.main(\\\"$0\\\")\nexcept ImportError:\\n  print(\\\"pysh: error: pip not installed :(\\\", file=sys.stderr)\\"" "|" "python3" "-" "$@"
"eval" "exit" "$?"
""".split('\n')


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
        self._last_newline = line[-1] == '\n'
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

  def __init__(self, metadata, content):
    self._metadata = collections.OrderedDict(metadata)
    self._content = content

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

    # is_executable_file = False
    # if hasattr(script_f, 'fileno'):
    #   f_stat = os.fstat(script_f.fileno())
    #   is_executable_file = (f_stat.st_mode & (stat.ST_IXUSR |
    #                                           stat.ST_IXOTH)) != 0

    shbang = next(parser)
    missing_shbang = not shbang.startswith('#!')
    if not missing_shbang:
      if shbang != SHBANG_LINE:
        self._raise_or_warn(UnrecognizedScriptError(
          parser.line_number, 0,
          'Shbang line is for a different parser'))

    # Throw away the recognized shbang part.
    _, f_shbang_lines = parser.fetch()

    # Parse metadata.
    metadata = collections.OrderedDict()
    while True:
      md = cls._parse_one_metadata(parser)
      if md is None:
        break

      metadata[md.name] = md

    _, content = parser.fetch()

    if missing_shbang and not metadata:
      content = f_shbang_lines + content

    return cls(metadata, content)

  def normalize(self):
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

    self.metadata[PYSH_BOOTSTRAP_SECTION_NAME] = Metadata(
      leading=[''], name=PYSH_BOOTSTRAP_SECTION_NAME,
      content=PYSH_BOOTSTRAP_SECTION)

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


def generate(script_path):
  with open(script_path) as script_f:
    script = ParsedScript.parse(script_f)

  script.normalize()

  with open(script_path, 'w') as script_f:
    script.write(script_f)
