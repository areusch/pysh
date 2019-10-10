from __future__ import print_function
import os.path
import re
import subprocess
import sys

from .ipython import inputtransformer2
from .ipython import text


class CalledProcessError(Exception):
    """Raised when run() is called with check=True and the process
    returns a non-zero exit status.
    Attributes:
      cmd, returncode, stdout, stderr, output
    """
    def __init__(self, returncode, cmd, output=None, stderr=None):
        self.returncode = returncode
        self.cmd = cmd
        self.output = output
        self.stderr = stderr

    def __str__(self):
        if self.returncode and self.returncode < 0:
            try:
                return "Command '%s' died with %r." % (
                        self.cmd, signal.Signals(-self.returncode))
            except ValueError:
                return "Command '%s' died with unknown signal %d." % (
                        self.cmd, -self.returncode)
        else:
            return "Command '%s' returned non-zero exit status %d." % (
                    self.cmd, self.returncode)

    @property
    def stdout(self):
        """Alias for output attribute, to match stderr"""
        return self.output

    @stdout.setter
    def stdout(self, value):
        # There's no obvious reason to set this, but allow it anyway so
        # .stdout is a transparent alias for .output
        self.output = value


class IPythonStub:

  def __init__(self):
    self.user_ns = {}

  def var_expand(self, cmd, depth=0, formatter=text.DollarFormatter()):
    """Expand python variables in a string.

    The depth argument indicates how many frames above the caller should
    be walked to look for the local namespace where to expand variables.

    The global namespace for expansion is always the user's interactive
    namespace.
    """
    ns = self.user_ns.copy()
    try:
      frame = sys._getframe(depth+1)
    except ValueError:
      # This is thrown if there aren't that many frames on the stack,
      # e.g. if a script called run_line_magic() directly.
      pass
    else:
      ns.update(frame.f_locals)

    try:
      # We have to use .vformat() here, because 'self' is a valid and common
      # name, and expanding **ns for .format() would make it collide with
      # the 'self' argument of the method.
      cmd = formatter.vformat(cmd, args=[], kwargs=ns)
    except Exception:
      # if formatter couldn't format, just let it go untransformed
      pass

    return cmd

  def system(self, *args):
    depth = 1 if sys.version_info[0] == 2 else 2
    proc = subprocess.Popen([self.var_expand(a, depth=depth) for a in args],
                            shell=True)
    proc.wait()
    if proc.returncode != 0:
      raise subprocess.CalledProcessError(proc.returncode, args, out, None)

  def getoutput(self, *args):
    kw = dict(shell=True, stdout=subprocess.PIPE)
    if sys.version_info[0] == 3:
      kw['encoding'] = 'utf-8'

    proc = subprocess.Popen([self.var_expand(a, depth=2) for a in args], **kw)
    out, _ = proc.communicate()
    if proc.returncode != 0:
      raise subprocess.CalledProcessError(proc.returncode, args, out, None)

    return out

class Executor:

  def __init__(self, script):
    self.script = script
    self.transformer_manager = inputtransformer2.TransformerManager()

  def execute(self):
    with open(self.script) as script_f:
      script_text = script_f.read()

    transformed = self.transformer_manager.transform_cell(script_text)
    code = compile(transformed, filename=self.script, mode='exec')
    old_sys_path = sys.path

    package_dir = os.path.dirname(self.script) or os.getcwd()
    if sys.path and sys.path[0] == '':
      sys.path[0] = package_dir
    else:
      sys.path.insert(0, package_dir)

    globals_locals = {'get_ipython': IPythonStub,
                      '__name__': '__main__'}
    try:

      exec(code, globals_locals, globals_locals)
    except:
      sys.path = old_sys_path
      raise

def main(script):
  Executor(script).execute()
