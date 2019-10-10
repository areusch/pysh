"""Main entry point for pysh."""

import argparse
import os
import os.path
import sys
from . import pysh

USAGE = """\
PySH extends Python scripts just enough such that it's easy to run bash scripts.
They are executable files that depend only on what you'd expect:
 * A POSIX-compliant shell
 * Python 2.7 or 3.5+

Before PySH scripts can be run, the `pysh` package needs to be installed. The
incantation in the script header installs pip and pysh if needed.
"""


def parse_args(argv=None):
  parser = argparse.ArgumentParser(usage=USAGE)
  subparsers = parser.add_subparsers(dest='subcommand')

  run = subparsers.add_parser('run', help='run a pysh script')
  run.add_argument('script_path', help='path to the script')
  run.add_argument('args', nargs='*')

  gen = subparsers.add_parser('gen', help='add header to pysh script')
  gen.add_argument('script_path', help='path to the script')

  argv = argv if argv is not None else sys.argv[1:]
  if sys.argv[0] not in ('run', 'gen') and os.path.exists(argv[0]):
    sys.argv.insert(0, 'run')

  return parser.parse_args(argv)


def _GenCommand(args):
  if args.script_path == '-':
    script_f = sys.stdin
  else:
    script_f = open(args.script_path)

  try:
    parser = generator.Parser(script_f)
    script = generator.ParsedScript.parse(parser)
  finally:
    script_f.close()

  script.normalize()

  if args.script_path == '-':
    script_f = sys.stdout
  else:
    tmp_name = '{}.tmp'.format(args.script_path)
    while os.path.exists(tmp_name):
      tmp_name = '{}.tmp.{}'.format(args.script_path, random.randint(0,100))

    script_f = open(tmp_name, 'w')

  try:
    script.write(script_f)
  finally:
    script_f.close()

  if args.script_path != '-':
    os.unlink(args.script_path)
    os.rename(tmp_name, args.script_path)


def _RunCommand(args):
  sys.argv = [args.script_path] + args.args
  pysh.main(args.script_path)


COMMAND_MAP = {
  'gen': _GenCommand,
  'run': _RunCommand,
}


def main():
  args = parse_args()
  COMMAND_MAP[args.subcommand](args)


if __name__ == '__main__':
  main()
