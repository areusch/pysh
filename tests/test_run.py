
import subprocess
import sys
import six


def test_example_from_run():
  proc = subprocess.Popen(
    [sys.executable, '-mpysh', 'run', 'doc/example.pysh'],
    stdout=subprocess.PIPE)

  stdout, _ = proc.communicate()
  assert proc.returncode == 3
  assert stdout == (b"Hello from Python!\n"
                    b"test\n"
                    b"captured: 'foo\\n'\n"
                    b"foo foo\n")


def test_run_directly():
  proc = subprocess.Popen(
    ['doc/example.pysh'],
    stdout=subprocess.PIPE)

  stdout, _ = proc.communicate()
  assert proc.returncode == 3
  assert stdout == (b"Hello from Python!\n"
                    b"test\n"
                    b"captured: 'foo\\n'\n"
                    b"foo foo\n")
