"""Main entry point for pysh."""

import argparse
import os
import os.path
import sys
from . import generator
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

  dist = subparsers.add_parser(
    'dist',
    help=('add header and a copy of pysh module to a pysh script, for '
          'standalone distribution to systems without pysh'))
  dist.add_argument('script_path', help='path to the script')

  gen = subparsers.add_parser('gen', help='add header to pysh script')
  gen.add_argument('script_path', help='path to the script')

  run = subparsers.add_parser('run', help='run a pysh script')
  run.add_argument('script_path', help='path to the script')
  run.add_argument('args', nargs='*')

  argv = argv if argv is not None else sys.argv[1:]
  if sys.argv[0] not in ('run', 'gen') and os.path.exists(argv[0]):
    sys.argv.insert(0, 'run')

  return parser.parse_args(argv)


def _GenCommand(args):
  generator.generate(args.script_path, dist=False)


def _DistCommand(args):
  generator.generate(args.script_path, dist=True)


def _RunCommand(args):
  sys.argv = [args.script_path] + args.args
  pysh.main(args.script_path)


COMMAND_MAP = {
  'gen': _GenCommand,
  'dist': _DistCommand,
  'run': _RunCommand,
}


def main():
  args = parse_args()
  COMMAND_MAP[args.subcommand](args)


if __name__ == '__main__':
  main()
