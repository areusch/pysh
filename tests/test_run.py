
import os
import subprocess
import shutil
import sys
import tempfile
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


def test_e2e_gen():
  temp_dir = tempfile.mkdtemp()
  try:
    script_file = '{}/test.sh'.format(temp_dir)
    with open(script_file, 'w') as script_f:
      script_f.write('print("Hello from Python!")\nimport sys\nsys.exit(3)')

    proc = subprocess.Popen([sys.executable, '-mpysh', 'gen', script_file])
    proc.wait()
    assert proc.returncode == 0

    proc = subprocess.Popen([script_file], stdout=subprocess.PIPE)
    out, _ = proc.communicate()
    assert proc.returncode == 3
    assert out == b'Hello from Python!\n'
  finally:
    shutil.rmtree(temp_dir)


def test_e2e_dist():
  two_three_arg = '--two' if sys.version_info[0] == 2 else '--three'
  pipenv_env = dict(list(os.environ.items()) +
                    [('PIPENV_IGNORE_VIRTUALENVS', '1')])
  try:
    temp_dir = tempfile.mkdtemp()
    script_file = '{}/test.sh'.format(temp_dir)
    with open(script_file, 'w') as script_f:
      script_f.write('print("Hello from Python!")\nimport sys\nsys.exit(3)')

    proc = subprocess.Popen([sys.executable, '-mpysh', 'dist', script_file])
    proc.wait()
    assert proc.returncode == 0
    with open(script_file) as script_f:
      lines = list(script_f)

    assert lines[0] == '#!/bin/sh -e\n'

    try:
      proc = subprocess.Popen(
        ['pipenv', 'install', two_three_arg],
        cwd=temp_dir,
        env=pipenv_env)
      proc.wait()
      assert proc.returncode == 0

      proc = subprocess.Popen(
        ['pipenv', 'run', script_file],
        cwd=temp_dir,
        stdout=subprocess.PIPE,
        env=pipenv_env)
      stdout, _ = proc.communicate()
      assert proc.returncode == 3
      assert stdout == b"Hello from Python!\n"
    finally:
      subprocess.Popen(['pipenv', '--rm'],
                       cwd=temp_dir,
                       env=pipenv_env).wait()
  finally:
    shutil.rmtree(temp_dir)
