import collections
import six
import pytest

from pysh import generator


def test_parser_class():
  s = six.StringIO('\n'.join([str(x) for x in range(1, 11)]) + '\n')

  p = generator.Parser(s)
  assert p.peek() == '1'
  assert p.peek_line_number == 1
  assert p.stack_start_line_number is None

  for i in range(4):
    assert p.next() == str(i + 2)
    assert p.peek_line_number == i + 2
    assert p.stack_start_line_number == 1

  assert p.fetch() == (1, ['1', '2', '3', '4', '5'])
  assert p.fetch() == (None, [])

  for i in range(2):
    assert p.peek() == str(i + 6)
    assert p.peek_line_number == i + 6
    p.next()

  assert p.fetch(include_peek_line=False) == (6, ['6', '7'])
  assert p.is_peek_line_valid == True
  assert p.peek() == '8'
  assert p.peek_line_number == 8

  for i in range(3):
    p.next()
    # NOTE: the first iterated item should still be the peek'd one from before.
    assert p.peek() == str(i + 8)
    assert p.peek_line_number == i + 8

  with pytest.raises(StopIteration):
    p.next()

  assert p.fetch() == (8, ['8', '9', '10', ''])


def test_parser_no_newline():
  s = six.StringIO('foo\nbar')
  p = generator.Parser(s)
  lines = list(p)

  assert lines == ['foo', 'bar']
  assert p.fetch() == (1, ['foo', 'bar'])


def _parse_string(s):
  return generator.ParsedScript.parse(six.StringIO(s))


basic_content = ('import foo\n'
                '\n'
                'print("blah")\n')

well_formed_header = (('#!/bin/sh -e\n'
                       '#\n'
                       '# PySH Information -->\n') +
                      '\n'.join(generator.PYSH_INFO_SECTION) + '\n' +
                      ('# <-- PySH Information\n'
                       '\n'
                       '# PySH Bootstrap -->\n') +
                      '\n'.join(generator.PYSH_BOOTSTRAP_SECTION) + '\n' +
                      ('# <-- PySH Bootstrap\n'))

well_formed = well_formed_header + basic_content

TESTS = {
  'no_shbang': ('',
                basic_content,
                '#!/bin/sh -e\n' + basic_content,
                well_formed),
  'no_info_or_bootstrap': ('#!/bin/sh -e\n',
                           basic_content,
                           '#!/bin/sh -e\n' + basic_content,
                           well_formed),
  'well_formed': (well_formed_header, basic_content, well_formed, well_formed),
}


@pytest.mark.parametrize("case_name", TESTS.keys())
def test_parse_and_generate(case_name):
  header, content, expected_out, expected_normalized_out = TESTS[case_name]

  script = header + content
  p = _parse_string(script)
  assert p.content == content.split('\n')

  out = six.StringIO()
  p.write(out)

  assert out.getvalue() == expected_out

  p.normalize()
  out = six.StringIO()
  p.write(out)

  assert out.getvalue() == expected_normalized_out
