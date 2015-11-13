__FILENAME__ = buildbot_run
#!/usr/bin/env python
# Copyright (c) 2012 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


"""Argument-less script to select what to run on the buildbots."""


import os
import shutil
import subprocess
import sys


if sys.platform in ['win32', 'cygwin']:
  EXE_SUFFIX = '.exe'
else:
  EXE_SUFFIX = ''


BUILDBOT_DIR = os.path.dirname(os.path.abspath(__file__))
TRUNK_DIR = os.path.dirname(BUILDBOT_DIR)
ROOT_DIR = os.path.dirname(TRUNK_DIR)
OUT_DIR = os.path.join(TRUNK_DIR, 'out')


def GypTestFormat(title, format=None, msvs_version=None):
  """Run the gyp tests for a given format, emitting annotator tags.

  See annotator docs at:
    https://sites.google.com/a/chromium.org/dev/developers/testing/chromium-build-infrastructure/buildbot-annotations
  Args:
    format: gyp format to test.
  Returns:
    0 for sucesss, 1 for failure.
  """
  if not format:
    format = title

  print '@@@BUILD_STEP ' + title + '@@@'
  sys.stdout.flush()
  env = os.environ.copy()
  # TODO(bradnelson): remove this when this issue is resolved:
  #     http://code.google.com/p/chromium/issues/detail?id=108251
  if format == 'ninja':
    env['NOGOLD'] = '1'
  if msvs_version:
    env['GYP_MSVS_VERSION'] = msvs_version
  retcode = subprocess.call(' '.join(
      [sys.executable, 'trunk/gyptest.py',
       '--all',
       '--passed',
       '--format', format,
       '--chdir', 'trunk',
       '--path', '../scons']),
      cwd=ROOT_DIR, env=env, shell=True)
  if retcode:
    # Emit failure tag, and keep going.
    print '@@@STEP_FAILURE@@@'
    return 1
  return 0


def GypBuild():
  # Dump out/ directory.
  print '@@@BUILD_STEP cleanup@@@'
  print 'Removing %s...' % OUT_DIR
  shutil.rmtree(OUT_DIR, ignore_errors=True)
  print 'Done.'

  retcode = 0
  if sys.platform.startswith('linux'):
    retcode += GypTestFormat('ninja')
    retcode += GypTestFormat('scons')
    retcode += GypTestFormat('make')
  elif sys.platform == 'darwin':
    retcode += GypTestFormat('ninja')
    retcode += GypTestFormat('xcode')
    retcode += GypTestFormat('make')
  elif sys.platform == 'win32':
    retcode += GypTestFormat('ninja')
    retcode += GypTestFormat('msvs-2008', format='msvs', msvs_version='2008')
    if os.environ['BUILDBOT_BUILDERNAME'] == 'gyp-win64':
      retcode += GypTestFormat('msvs-2010', format='msvs', msvs_version='2010')
  else:
    raise Exception('Unknown platform')
  if retcode:
    # TODO(bradnelson): once the annotator supports a postscript (section for
    #     after the build proper that could be used for cumulative failures),
    #     use that instead of this. This isolates the final return value so
    #     that it isn't misattributed to the last stage.
    print '@@@BUILD_STEP failures@@@'
    sys.exit(retcode)


if __name__ == '__main__':
  GypBuild()

########NEW FILE########
__FILENAME__ = gyptest
#!/usr/bin/env python

# Copyright (c) 2012 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

__doc__ = """
gyptest.py -- test runner for GYP tests.
"""

import os
import optparse
import subprocess
import sys

class CommandRunner:
  """
  Executor class for commands, including "commands" implemented by
  Python functions.
  """
  verbose = True
  active = True

  def __init__(self, dictionary={}):
    self.subst_dictionary(dictionary)

  def subst_dictionary(self, dictionary):
    self._subst_dictionary = dictionary

  def subst(self, string, dictionary=None):
    """
    Substitutes (via the format operator) the values in the specified
    dictionary into the specified command.

    The command can be an (action, string) tuple.  In all cases, we
    perform substitution on strings and don't worry if something isn't
    a string.  (It's probably a Python function to be executed.)
    """
    if dictionary is None:
      dictionary = self._subst_dictionary
    if dictionary:
      try:
        string = string % dictionary
      except TypeError:
        pass
    return string

  def display(self, command, stdout=None, stderr=None):
    if not self.verbose:
      return
    if type(command) == type(()):
      func = command[0]
      args = command[1:]
      s = '%s(%s)' % (func.__name__, ', '.join(map(repr, args)))
    if type(command) == type([]):
      # TODO:  quote arguments containing spaces
      # TODO:  handle meta characters?
      s = ' '.join(command)
    else:
      s = self.subst(command)
    if not s.endswith('\n'):
      s += '\n'
    sys.stdout.write(s)
    sys.stdout.flush()

  def execute(self, command, stdout=None, stderr=None):
    """
    Executes a single command.
    """
    if not self.active:
      return 0
    if type(command) == type(''):
      command = self.subst(command)
      cmdargs = shlex.split(command)
      if cmdargs[0] == 'cd':
         command = (os.chdir,) + tuple(cmdargs[1:])
    if type(command) == type(()):
      func = command[0]
      args = command[1:]
      return func(*args)
    else:
      if stdout is sys.stdout:
        # Same as passing sys.stdout, except python2.4 doesn't fail on it.
        subout = None
      else:
        # Open pipe for anything else so Popen works on python2.4.
        subout = subprocess.PIPE
      if stderr is sys.stderr:
        # Same as passing sys.stderr, except python2.4 doesn't fail on it.
        suberr = None
      elif stderr is None:
        # Merge with stdout if stderr isn't specified.
        suberr = subprocess.STDOUT
      else:
        # Open pipe for anything else so Popen works on python2.4.
        suberr = subprocess.PIPE
      p = subprocess.Popen(command,
                           shell=(sys.platform == 'win32'),
                           stdout=subout,
                           stderr=suberr)
      p.wait()
      if stdout is None:
        self.stdout = p.stdout.read()
      elif stdout is not sys.stdout:
        stdout.write(p.stdout.read())
      if stderr not in (None, sys.stderr):
        stderr.write(p.stderr.read())
      return p.returncode

  def run(self, command, display=None, stdout=None, stderr=None):
    """
    Runs a single command, displaying it first.
    """
    if display is None:
      display = command
    self.display(display)
    return self.execute(command, stdout, stderr)


class Unbuffered:
  def __init__(self, fp):
    self.fp = fp
  def write(self, arg):
    self.fp.write(arg)
    self.fp.flush()
  def __getattr__(self, attr):
    return getattr(self.fp, attr)

sys.stdout = Unbuffered(sys.stdout)
sys.stderr = Unbuffered(sys.stderr)


def find_all_gyptest_files(directory):
    result = []
    for root, dirs, files in os.walk(directory):
      if '.svn' in dirs:
        dirs.remove('.svn')
      result.extend([ os.path.join(root, f) for f in files
                     if f.startswith('gyptest') and f.endswith('.py') ])
    result.sort()
    return result


def main(argv=None):
  if argv is None:
    argv = sys.argv

  usage = "gyptest.py [-ahlnq] [-f formats] [test ...]"
  parser = optparse.OptionParser(usage=usage)
  parser.add_option("-a", "--all", action="store_true",
            help="run all tests")
  parser.add_option("-C", "--chdir", action="store", default=None,
            help="chdir to the specified directory")
  parser.add_option("-f", "--format", action="store", default='',
            help="run tests with the specified formats")
  parser.add_option("-G", '--gyp_option', action="append", default=[],
            help="Add -G options to the gyp command line")
  parser.add_option("-l", "--list", action="store_true",
            help="list available tests and exit")
  parser.add_option("-n", "--no-exec", action="store_true",
            help="no execute, just print the command line")
  parser.add_option("--passed", action="store_true",
            help="report passed tests")
  parser.add_option("--path", action="append", default=[],
            help="additional $PATH directory")
  parser.add_option("-q", "--quiet", action="store_true",
            help="quiet, don't print test command lines")
  opts, args = parser.parse_args(argv[1:])

  if opts.chdir:
    os.chdir(opts.chdir)

  if opts.path:
    extra_path = [os.path.abspath(p) for p in opts.path]
    extra_path = os.pathsep.join(extra_path)
    os.environ['PATH'] += os.pathsep + extra_path

  if not args:
    if not opts.all:
      sys.stderr.write('Specify -a to get all tests.\n')
      return 1
    args = ['test']

  tests = []
  for arg in args:
    if os.path.isdir(arg):
      tests.extend(find_all_gyptest_files(os.path.normpath(arg)))
    else:
      tests.append(arg)

  if opts.list:
    for test in tests:
      print test
    sys.exit(0)

  CommandRunner.verbose = not opts.quiet
  CommandRunner.active = not opts.no_exec
  cr = CommandRunner()

  os.environ['PYTHONPATH'] = os.path.abspath('test/lib')
  if not opts.quiet:
    sys.stdout.write('PYTHONPATH=%s\n' % os.environ['PYTHONPATH'])

  passed = []
  failed = []
  no_result = []

  if opts.format:
    format_list = opts.format.split(',')
  else:
    # TODO:  not duplicate this mapping from pylib/gyp/__init__.py
    format_list = {
      'freebsd7': ['make'],
      'freebsd8': ['make'],
      'cygwin':   ['msvs'],
      'win32':    ['msvs', 'ninja'],
      'linux2':   ['make', 'ninja'],
      'linux3':   ['make', 'ninja'],
      'darwin':   ['make', 'ninja', 'xcode'],
    }[sys.platform]

  for format in format_list:
    os.environ['TESTGYP_FORMAT'] = format
    if not opts.quiet:
      sys.stdout.write('TESTGYP_FORMAT=%s\n' % format)

    gyp_options = []
    for option in opts.gyp_option:
      gyp_options += ['-G', option]
    if gyp_options and not opts.quiet:
      sys.stdout.write('Extra Gyp options: %s\n' % gyp_options)

    for test in tests:
      status = cr.run([sys.executable, test] + gyp_options,
                      stdout=sys.stdout,
                      stderr=sys.stderr)
      if status == 2:
        no_result.append(test)
      elif status:
        failed.append(test)
      else:
        passed.append(test)

  if not opts.quiet:
    def report(description, tests):
      if tests:
        if len(tests) == 1:
          sys.stdout.write("\n%s the following test:\n" % description)
        else:
          fmt = "\n%s the following %d tests:\n"
          sys.stdout.write(fmt % (description, len(tests)))
        sys.stdout.write("\t" + "\n\t".join(tests) + "\n")

    if opts.passed:
      report("Passed", passed)
    report("Failed", failed)
    report("No result from", no_result)

  if failed:
    return 1
  else:
    return 0


if __name__ == "__main__":
  sys.exit(main())

########NEW FILE########
__FILENAME__ = PRESUBMIT
# Copyright (c) 2012 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


"""Top-level presubmit script for GYP.

See http://dev.chromium.org/developers/how-tos/depottools/presubmit-scripts
for more details about the presubmit API built into gcl.
"""


PYLINT_BLACKLIST = [
    # TODO: fix me.
    # From SCons, not done in google style.
    'test/lib/TestCmd.py',
    'test/lib/TestCommon.py',
    'test/lib/TestGyp.py',
    # Needs style fix.
    'pylib/gyp/generator/scons.py',
    'pylib/gyp/generator/xcode.py',
]


PYLINT_DISABLED_WARNINGS = [
    # TODO: fix me.
    # Many tests include modules they don't use.
    'W0611',
    # Include order doesn't properly include local files?
    'F0401',
    # Some use of built-in names.
    'W0622',
    # Some unused variables.
    'W0612',
    # Operator not preceded/followed by space.
    'C0323',
    'C0322',
    # Unnecessary semicolon.
    'W0301',
    # Unused argument.
    'W0613',
    # String has no effect (docstring in wrong place).
    'W0105',
    # Comma not followed by space.
    'C0324',
    # Access to a protected member.
    'W0212',
    # Bad indent.
    'W0311',
    # Line too long.
    'C0301',
    # Undefined variable.
    'E0602',
    # Not exception type specified.
    'W0702',
    # No member of that name.
    'E1101',
    # Dangerous default {}.
    'W0102',
    # Others, too many to sort.
    'W0201', 'W0232', 'E1103', 'W0621', 'W0108', 'W0223', 'W0231',
    'R0201', 'E0101', 'C0321',
    # ************* Module copy
    # W0104:427,12:_test.odict.__setitem__: Statement seems to have no effect
    'W0104',
]


def CheckChangeOnUpload(input_api, output_api):
  report = []
  report.extend(input_api.canned_checks.PanProjectChecks(
      input_api, output_api))
  return report


def CheckChangeOnCommit(input_api, output_api):
  report = []
  license = (
      r'.*? Copyright \(c\) %(year)s Google Inc\. All rights reserved\.\n'
      r'.*? Use of this source code is governed by a BSD-style license that '
        r'can be\n'
      r'.*? found in the LICENSE file\.\n'
  ) % {
      'year': input_api.time.strftime('%Y'),
  }

  report.extend(input_api.canned_checks.PanProjectChecks(
      input_api, output_api, license_header=license))
  report.extend(input_api.canned_checks.CheckTreeIsOpen(
      input_api, output_api,
      'http://gyp-status.appspot.com/status',
      'http://gyp-status.appspot.com/current'))

  import sys
  old_sys_path = sys.path
  try:
    sys.path = ['pylib', 'test/lib'] + sys.path
    report.extend(input_api.canned_checks.RunPylint(
        input_api,
        output_api,
        black_list=PYLINT_BLACKLIST,
        disabled_warnings=PYLINT_DISABLED_WARNINGS))
  finally:
    sys.path = old_sys_path
  return report


def GetPreferredTrySlaves():
  return ['gyp-win32', 'gyp-win64', 'gyp-linux', 'gyp-mac']

########NEW FILE########
__FILENAME__ = common
# Copyright (c) 2012 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import with_statement

import errno
import filecmp
import os.path
import re
import tempfile
import sys


# A minimal memoizing decorator. It'll blow up if the args aren't immutable,
# among other "problems".
class memoize(object):
  def __init__(self, func):
    self.func = func
    self.cache = {}
  def __call__(self, *args):
    try:
      return self.cache[args]
    except KeyError:
      result = self.func(*args)
      self.cache[args] = result
      return result


class GypError(Exception):
  """Error class representing an error, which is to be presented
  to the user.  The main entry point will catch and display this.
  """
  pass


def ExceptionAppend(e, msg):
  """Append a message to the given exception's message."""
  if not e.args:
    e.args = (msg,)
  elif len(e.args) == 1:
    e.args = (str(e.args[0]) + ' ' + msg,)
  else:
    e.args = (str(e.args[0]) + ' ' + msg,) + e.args[1:]


def ParseQualifiedTarget(target):
  # Splits a qualified target into a build file, target name and toolset.

  # NOTE: rsplit is used to disambiguate the Windows drive letter separator.
  target_split = target.rsplit(':', 1)
  if len(target_split) == 2:
    [build_file, target] = target_split
  else:
    build_file = None

  target_split = target.rsplit('#', 1)
  if len(target_split) == 2:
    [target, toolset] = target_split
  else:
    toolset = None

  return [build_file, target, toolset]


def ResolveTarget(build_file, target, toolset):
  # This function resolves a target into a canonical form:
  # - a fully defined build file, either absolute or relative to the current
  # directory
  # - a target name
  # - a toolset
  #
  # build_file is the file relative to which 'target' is defined.
  # target is the qualified target.
  # toolset is the default toolset for that target.
  [parsed_build_file, target, parsed_toolset] = ParseQualifiedTarget(target)

  if parsed_build_file:
    if build_file:
      # If a relative path, parsed_build_file is relative to the directory
      # containing build_file.  If build_file is not in the current directory,
      # parsed_build_file is not a usable path as-is.  Resolve it by
      # interpreting it as relative to build_file.  If parsed_build_file is
      # absolute, it is usable as a path regardless of the current directory,
      # and os.path.join will return it as-is.
      build_file = os.path.normpath(os.path.join(os.path.dirname(build_file),
                                                 parsed_build_file))
      # Further (to handle cases like ../cwd), make it relative to cwd)
      if not os.path.isabs(build_file):
        build_file = RelativePath(build_file, '.')
    else:
      build_file = parsed_build_file

  if parsed_toolset:
    toolset = parsed_toolset

  return [build_file, target, toolset]


def BuildFile(fully_qualified_target):
  # Extracts the build file from the fully qualified target.
  return ParseQualifiedTarget(fully_qualified_target)[0]


def GetEnvironFallback(var_list, default):
  """Look up a key in the environment, with fallback to secondary keys
  and finally falling back to a default value."""
  for var in var_list:
    if var in os.environ:
      return os.environ[var]
  return default


def QualifiedTarget(build_file, target, toolset):
  # "Qualified" means the file that a target was defined in and the target
  # name, separated by a colon, suffixed by a # and the toolset name:
  # /path/to/file.gyp:target_name#toolset
  fully_qualified = build_file + ':' + target
  if toolset:
    fully_qualified = fully_qualified + '#' + toolset
  return fully_qualified


@memoize
def RelativePath(path, relative_to):
  # Assuming both |path| and |relative_to| are relative to the current
  # directory, returns a relative path that identifies path relative to
  # relative_to.

  # Convert to absolute (and therefore normalized paths).
  path = os.path.abspath(path)
  relative_to = os.path.abspath(relative_to)

  # Split the paths into components.
  path_split = path.split(os.path.sep)
  relative_to_split = relative_to.split(os.path.sep)

  # Determine how much of the prefix the two paths share.
  prefix_len = len(os.path.commonprefix([path_split, relative_to_split]))

  # Put enough ".." components to back up out of relative_to to the common
  # prefix, and then append the part of path_split after the common prefix.
  relative_split = [os.path.pardir] * (len(relative_to_split) - prefix_len) + \
                   path_split[prefix_len:]

  if len(relative_split) == 0:
    # The paths were the same.
    return ''

  # Turn it back into a string and we're done.
  return os.path.join(*relative_split)


def FixIfRelativePath(path, relative_to):
  # Like RelativePath but returns |path| unchanged if it is absolute.
  if os.path.isabs(path):
    return path
  return RelativePath(path, relative_to)


def UnrelativePath(path, relative_to):
  # Assuming that |relative_to| is relative to the current directory, and |path|
  # is a path relative to the dirname of |relative_to|, returns a path that
  # identifies |path| relative to the current directory.
  rel_dir = os.path.dirname(relative_to)
  return os.path.normpath(os.path.join(rel_dir, path))


# re objects used by EncodePOSIXShellArgument.  See IEEE 1003.1 XCU.2.2 at
# http://www.opengroup.org/onlinepubs/009695399/utilities/xcu_chap02.html#tag_02_02
# and the documentation for various shells.

# _quote is a pattern that should match any argument that needs to be quoted
# with double-quotes by EncodePOSIXShellArgument.  It matches the following
# characters appearing anywhere in an argument:
#   \t, \n, space  parameter separators
#   #              comments
#   $              expansions (quoted to always expand within one argument)
#   %              called out by IEEE 1003.1 XCU.2.2
#   &              job control
#   '              quoting
#   (, )           subshell execution
#   *, ?, [        pathname expansion
#   ;              command delimiter
#   <, >, |        redirection
#   =              assignment
#   {, }           brace expansion (bash)
#   ~              tilde expansion
# It also matches the empty string, because "" (or '') is the only way to
# represent an empty string literal argument to a POSIX shell.
#
# This does not match the characters in _escape, because those need to be
# backslash-escaped regardless of whether they appear in a double-quoted
# string.
_quote = re.compile('[\t\n #$%&\'()*;<=>?[{|}~]|^$')

# _escape is a pattern that should match any character that needs to be
# escaped with a backslash, whether or not the argument matched the _quote
# pattern.  _escape is used with re.sub to backslash anything in _escape's
# first match group, hence the (parentheses) in the regular expression.
#
# _escape matches the following characters appearing anywhere in an argument:
#   "  to prevent POSIX shells from interpreting this character for quoting
#   \  to prevent POSIX shells from interpreting this character for escaping
#   `  to prevent POSIX shells from interpreting this character for command
#      substitution
# Missing from this list is $, because the desired behavior of
# EncodePOSIXShellArgument is to permit parameter (variable) expansion.
#
# Also missing from this list is !, which bash will interpret as the history
# expansion character when history is enabled.  bash does not enable history
# by default in non-interactive shells, so this is not thought to be a problem.
# ! was omitted from this list because bash interprets "\!" as a literal string
# including the backslash character (avoiding history expansion but retaining
# the backslash), which would not be correct for argument encoding.  Handling
# this case properly would also be problematic because bash allows the history
# character to be changed with the histchars shell variable.  Fortunately,
# as history is not enabled in non-interactive shells and
# EncodePOSIXShellArgument is only expected to encode for non-interactive
# shells, there is no room for error here by ignoring !.
_escape = re.compile(r'(["\\`])')

def EncodePOSIXShellArgument(argument):
  """Encodes |argument| suitably for consumption by POSIX shells.

  argument may be quoted and escaped as necessary to ensure that POSIX shells
  treat the returned value as a literal representing the argument passed to
  this function.  Parameter (variable) expansions beginning with $ are allowed
  to remain intact without escaping the $, to allow the argument to contain
  references to variables to be expanded by the shell.
  """

  if not isinstance(argument, str):
    argument = str(argument)

  if _quote.search(argument):
    quote = '"'
  else:
    quote = ''

  encoded = quote + re.sub(_escape, r'\\\1', argument) + quote

  return encoded


def EncodePOSIXShellList(list):
  """Encodes |list| suitably for consumption by POSIX shells.

  Returns EncodePOSIXShellArgument for each item in list, and joins them
  together using the space character as an argument separator.
  """

  encoded_arguments = []
  for argument in list:
    encoded_arguments.append(EncodePOSIXShellArgument(argument))
  return ' '.join(encoded_arguments)


def DeepDependencyTargets(target_dicts, roots):
  """Returns the recursive list of target dependencies."""
  dependencies = set()
  pending = set(roots)
  while pending:
    # Pluck out one.
    r = pending.pop()
    # Skip if visited already.
    if r in dependencies:
      continue
    # Add it.
    dependencies.add(r)
    # Add its children.
    spec = target_dicts[r]
    pending.update(set(spec.get('dependencies', [])))
    pending.update(set(spec.get('dependencies_original', [])))
  return list(dependencies - set(roots))


def BuildFileTargets(target_list, build_file):
  """From a target_list, returns the subset from the specified build_file.
  """
  return [p for p in target_list if BuildFile(p) == build_file]


def AllTargets(target_list, target_dicts, build_file):
  """Returns all targets (direct and dependencies) for the specified build_file.
  """
  bftargets = BuildFileTargets(target_list, build_file)
  deptargets = DeepDependencyTargets(target_dicts, bftargets)
  return bftargets + deptargets


def WriteOnDiff(filename):
  """Write to a file only if the new contents differ.

  Arguments:
    filename: name of the file to potentially write to.
  Returns:
    A file like object which will write to temporary file and only overwrite
    the target if it differs (on close).
  """

  class Writer:
    """Wrapper around file which only covers the target if it differs."""
    def __init__(self):
      # Pick temporary file.
      tmp_fd, self.tmp_path = tempfile.mkstemp(
          suffix='.tmp',
          prefix=os.path.split(filename)[1] + '.gyp.',
          dir=os.path.split(filename)[0])
      try:
        self.tmp_file = os.fdopen(tmp_fd, 'wb')
      except Exception:
        # Don't leave turds behind.
        os.unlink(self.tmp_path)
        raise

    def __getattr__(self, attrname):
      # Delegate everything else to self.tmp_file
      return getattr(self.tmp_file, attrname)

    def close(self):
      try:
        # Close tmp file.
        self.tmp_file.close()
        # Determine if different.
        same = False
        try:
          same = filecmp.cmp(self.tmp_path, filename, False)
        except OSError, e:
          if e.errno != errno.ENOENT:
            raise

        if same:
          # The new file is identical to the old one, just get rid of the new
          # one.
          os.unlink(self.tmp_path)
        else:
          # The new file is different from the old one, or there is no old one.
          # Rename the new file to the permanent name.
          #
          # tempfile.mkstemp uses an overly restrictive mode, resulting in a
          # file that can only be read by the owner, regardless of the umask.
          # There's no reason to not respect the umask here, which means that
          # an extra hoop is required to fetch it and reset the new file's mode.
          #
          # No way to get the umask without setting a new one?  Set a safe one
          # and then set it back to the old value.
          umask = os.umask(077)
          os.umask(umask)
          os.chmod(self.tmp_path, 0666 & ~umask)
          if sys.platform == 'win32' and os.path.exists(filename):
            # NOTE: on windows (but not cygwin) rename will not replace an
            # existing file, so it must be preceded with a remove. Sadly there
            # is no way to make the switch atomic.
            os.remove(filename)
          os.rename(self.tmp_path, filename)
      except Exception:
        # Don't leave turds behind.
        os.unlink(self.tmp_path)
        raise

  return Writer()


def GetFlavor(params):
  """Returns |params.flavor| if it's set, the system's default flavor else."""
  flavors = {
    'cygwin': 'win',
    'win32': 'win',
    'darwin': 'mac',
  }

  if 'flavor' in params:
    return params['flavor']
  if sys.platform in flavors:
    return flavors[sys.platform]
  if sys.platform.startswith('sunos'):
    return 'solaris'
  if sys.platform.startswith('freebsd'):
    return 'freebsd'

  return 'linux'


def CopyTool(flavor, out_path):
  """Finds (mac|sun|win)_tool.gyp in the gyp directory and copies it
  to |out_path|."""
  prefix = { 'solaris': 'sun', 'mac': 'mac', 'win': 'win' }.get(flavor, None)
  if not prefix:
    return

  # Slurp input file.
  source_path = os.path.join(
      os.path.dirname(os.path.abspath(__file__)), '%s_tool.py' % prefix)
  with open(source_path) as source_file:
    source = source_file.readlines()

  # Add header and write it out.
  tool_path = os.path.join(out_path, 'gyp-%s-tool' % prefix)
  with open(tool_path, 'w') as tool_file:
    tool_file.write(
        ''.join([source[0], '# Generated by gyp. Do not edit.\n'] + source[1:]))

  # Make file executable.
  os.chmod(tool_path, 0755)


# From Alex Martelli,
# http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/52560
# ASPN: Python Cookbook: Remove duplicates from a sequence
# First comment, dated 2001/10/13.
# (Also in the printed Python Cookbook.)

def uniquer(seq, idfun=None):
    if idfun is None:
        idfun = lambda x: x
    seen = {}
    result = []
    for item in seq:
        marker = idfun(item)
        if marker in seen: continue
        seen[marker] = 1
        result.append(item)
    return result


class CycleError(Exception):
  """An exception raised when an unexpected cycle is detected."""
  def __init__(self, nodes):
    self.nodes = nodes
  def __str__(self):
    return 'CycleError: cycle involving: ' + str(self.nodes)


def TopologicallySorted(graph, get_edges):
  """Topologically sort based on a user provided edge definition.

  Args:
    graph: A list of node names.
    get_edges: A function mapping from node name to a hashable collection
               of node names which this node has outgoing edges to.
  Returns:
    A list containing all of the node in graph in topological order.
    It is assumed that calling get_edges once for each node and caching is
    cheaper than repeatedly calling get_edges.
  Raises:
    CycleError in the event of a cycle.
  Example:
    graph = {'a': '$(b) $(c)', 'b': 'hi', 'c': '$(b)'}
    def GetEdges(node):
      return re.findall(r'\$\(([^))]\)', graph[node])
    print TopologicallySorted(graph.keys(), GetEdges)
    ==>
    ['a', 'c', b']
  """
  get_edges = memoize(get_edges)
  visited = set()
  visiting = set()
  ordered_nodes = []
  def Visit(node):
    if node in visiting:
      raise CycleError(visiting)
    if node in visited:
      return
    visited.add(node)
    visiting.add(node)
    for neighbor in get_edges(node):
      Visit(neighbor)
    visiting.remove(node)
    ordered_nodes.insert(0, node)
  for node in sorted(graph):
    Visit(node)
  return ordered_nodes

########NEW FILE########
__FILENAME__ = common_test
#!/usr/bin/env python

# Copyright (c) 2012 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for the common.py file."""

import gyp.common
import unittest
import sys


class TestTopologicallySorted(unittest.TestCase):
  def test_Valid(self):
    """Test that sorting works on a valid graph with one possible order."""
    graph = {
        'a': ['b', 'c'],
        'b': [],
        'c': ['d'],
        'd': ['b'],
        }
    def GetEdge(node):
      return tuple(graph[node])
    self.assertEqual(
      gyp.common.TopologicallySorted(graph.keys(), GetEdge),
      ['a', 'c', 'd', 'b'])

  def test_Cycle(self):
    """Test that an exception is thrown on a cyclic graph."""
    graph = {
        'a': ['b'],
        'b': ['c'],
        'c': ['d'],
        'd': ['a'],
        }
    def GetEdge(node):
      return tuple(graph[node])
    self.assertRaises(
      gyp.common.CycleError, gyp.common.TopologicallySorted,
      graph.keys(), GetEdge)


class TestGetFlavor(unittest.TestCase):
  """Test that gyp.common.GetFlavor works as intended"""
  original_platform = ''

  def setUp(self):
    self.original_platform = sys.platform

  def tearDown(self):
    sys.platform = self.original_platform

  def assertFlavor(self, expected, argument, param):
    sys.platform = argument
    self.assertEqual(expected, gyp.common.GetFlavor(param))

  def test_platform_default(self):
    self.assertFlavor('freebsd', 'freebsd9' , {})
    self.assertFlavor('freebsd', 'freebsd10', {})
    self.assertFlavor('solaris', 'sunos5'   , {});
    self.assertFlavor('solaris', 'sunos'    , {});
    self.assertFlavor('linux'  , 'linux2'   , {});
    self.assertFlavor('linux'  , 'linux3'   , {});

  def test_param(self):
    self.assertFlavor('foobar', 'linux2' , {'flavor': 'foobar'})


if __name__ == '__main__':
  unittest.main()

########NEW FILE########
__FILENAME__ = easy_xml
# Copyright (c) 2011 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re
import os


def XmlToString(content, encoding='utf-8', pretty=False):
  """ Writes the XML content to disk, touching the file only if it has changed.

  Visual Studio files have a lot of pre-defined structures.  This function makes
  it easy to represent these structures as Python data structures, instead of
  having to create a lot of function calls.

  Each XML element of the content is represented as a list composed of:
  1. The name of the element, a string,
  2. The attributes of the element, a dictionary (optional), and
  3+. The content of the element, if any.  Strings are simple text nodes and
      lists are child elements.

  Example 1:
      <test/>
  becomes
      ['test']

  Example 2:
      <myelement a='value1' b='value2'>
         <childtype>This is</childtype>
         <childtype>it!</childtype>
      </myelement>

  becomes
      ['myelement', {'a':'value1', 'b':'value2'},
         ['childtype', 'This is'],
         ['childtype', 'it!'],
      ]

  Args:
    content:  The structured content to be converted.
    encoding: The encoding to report on the first XML line.
    pretty: True if we want pretty printing with indents and new lines.

  Returns:
    The XML content as a string.
  """
  # We create a huge list of all the elements of the file.
  xml_parts = ['<?xml version="1.0" encoding="%s"?>' % encoding]
  if pretty:
    xml_parts.append('\n')
  _ConstructContentList(xml_parts, content, pretty)

  # Convert it to a string
  return ''.join(xml_parts)


def _ConstructContentList(xml_parts, specification, pretty, level=0):
  """ Appends the XML parts corresponding to the specification.

  Args:
    xml_parts: A list of XML parts to be appended to.
    specification:  The specification of the element.  See EasyXml docs.
    pretty: True if we want pretty printing with indents and new lines.
    level: Indentation level.
  """
  # The first item in a specification is the name of the element.
  if pretty:
    indentation = '  ' * level
    new_line = '\n'
  else:
    indentation = ''
    new_line = ''
  name = specification[0]
  if not isinstance(name, str):
    raise Exception('The first item of an EasyXml specification should be '
                    'a string.  Specification was ' + str(specification))
  xml_parts.append(indentation + '<' + name)

  # Optionally in second position is a dictionary of the attributes.
  rest = specification[1:]
  if rest and isinstance(rest[0], dict):
    for at, val in sorted(rest[0].iteritems()):
      xml_parts.append(' %s="%s"' % (at, _XmlEscape(val, attr=True)))
    rest = rest[1:]
  if rest:
    xml_parts.append('>')
    all_strings = reduce(lambda x, y: x and isinstance(y, str), rest, True)
    multi_line = not all_strings
    if multi_line and new_line:
      xml_parts.append(new_line)
    for child_spec in rest:
      # If it's a string, append a text node.
      # Otherwise recurse over that child definition
      if isinstance(child_spec, str):
       xml_parts.append(_XmlEscape(child_spec))
      else:
        _ConstructContentList(xml_parts, child_spec, pretty, level + 1)
    if multi_line and indentation:
      xml_parts.append(indentation)
    xml_parts.append('</%s>%s' % (name, new_line))
  else:
    xml_parts.append('/>%s' % new_line)


def WriteXmlIfChanged(content, path, encoding='utf-8', pretty=False,
                      win32=False):
  """ Writes the XML content to disk, touching the file only if it has changed.

  Args:
    content:  The structured content to be written.
    path: Location of the file.
    encoding: The encoding to report on the first line of the XML file.
    pretty: True if we want pretty printing with indents and new lines.
  """
  xml_string = XmlToString(content, encoding, pretty)
  if win32 and os.linesep != '\r\n':
    xml_string = xml_string.replace('\n', '\r\n')

  # Get the old content
  try:
    f = open(path, 'r')
    existing = f.read()
    f.close()
  except:
    existing = None

  # It has changed, write it
  if existing != xml_string:
    f = open(path, 'w')
    f.write(xml_string)
    f.close()


_xml_escape_map = {
    '"': '&quot;',
    "'": '&apos;',
    '<': '&lt;',
    '>': '&gt;',
    '&': '&amp;',
    '\n': '&#xA;',
    '\r': '&#xD;',
}


_xml_escape_re = re.compile(
    "(%s)" % "|".join(map(re.escape, _xml_escape_map.keys())))


def _XmlEscape(value, attr=False):
  """ Escape a string for inclusion in XML."""
  def replace(match):
    m = match.string[match.start() : match.end()]
    # don't replace single quotes in attrs
    if attr and m == "'":
      return m
    return _xml_escape_map[m]
  return _xml_escape_re.sub(replace, value)

########NEW FILE########
__FILENAME__ = easy_xml_test
#!/usr/bin/env python

# Copyright (c) 2011 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" Unit tests for the easy_xml.py file. """

import gyp.easy_xml as easy_xml
import unittest
import StringIO


class TestSequenceFunctions(unittest.TestCase):

  def setUp(self):
    self.stderr = StringIO.StringIO()

  def test_EasyXml_simple(self):
    self.assertEqual(
      easy_xml.XmlToString(['test']),
      '<?xml version="1.0" encoding="utf-8"?><test/>')

    self.assertEqual(
      easy_xml.XmlToString(['test'], encoding='Windows-1252'),
      '<?xml version="1.0" encoding="Windows-1252"?><test/>')

  def test_EasyXml_simple_with_attributes(self):
    self.assertEqual(
      easy_xml.XmlToString(['test2', {'a': 'value1', 'b': 'value2'}]),
      '<?xml version="1.0" encoding="utf-8"?><test2 a="value1" b="value2"/>')

  def test_EasyXml_escaping(self):
    original = '<test>\'"\r&\nfoo'
    converted = '&lt;test&gt;\'&quot;&#xD;&amp;&#xA;foo'
    converted_apos = converted.replace("'", '&apos;')
    self.assertEqual(
      easy_xml.XmlToString(['test3', {'a': original}, original]),
      '<?xml version="1.0" encoding="utf-8"?><test3 a="%s">%s</test3>' %
      (converted, converted_apos))

  def test_EasyXml_pretty(self):
    self.assertEqual(
      easy_xml.XmlToString(
          ['test3',
            ['GrandParent',
              ['Parent1',
                ['Child']
              ],
              ['Parent2']
            ]
          ],
          pretty=True),
      '<?xml version="1.0" encoding="utf-8"?>\n'
      '<test3>\n'
      '  <GrandParent>\n'
      '    <Parent1>\n'
      '      <Child/>\n'
      '    </Parent1>\n'
      '    <Parent2/>\n'
      '  </GrandParent>\n'
      '</test3>\n')


  def test_EasyXml_complex(self):
    # We want to create:
    target = (
      '<?xml version="1.0" encoding="utf-8"?>'
      '<Project>'
        '<PropertyGroup Label="Globals">'
          '<ProjectGuid>{D2250C20-3A94-4FB9-AF73-11BC5B73884B}</ProjectGuid>'
          '<Keyword>Win32Proj</Keyword>'
          '<RootNamespace>automated_ui_tests</RootNamespace>'
        '</PropertyGroup>'
        '<Import Project="$(VCTargetsPath)\\Microsoft.Cpp.props"/>'
        '<PropertyGroup '
            'Condition="\'$(Configuration)|$(Platform)\'=='
                       '\'Debug|Win32\'" Label="Configuration">'
          '<ConfigurationType>Application</ConfigurationType>'
          '<CharacterSet>Unicode</CharacterSet>'
        '</PropertyGroup>'
      '</Project>')

    xml = easy_xml.XmlToString(
        ['Project',
          ['PropertyGroup', {'Label': 'Globals'},
            ['ProjectGuid', '{D2250C20-3A94-4FB9-AF73-11BC5B73884B}'],
            ['Keyword', 'Win32Proj'],
            ['RootNamespace', 'automated_ui_tests']
          ],
          ['Import', {'Project': '$(VCTargetsPath)\\Microsoft.Cpp.props'}],
          ['PropertyGroup',
            {'Condition': "'$(Configuration)|$(Platform)'=='Debug|Win32'",
             'Label': 'Configuration'},
            ['ConfigurationType', 'Application'],
            ['CharacterSet', 'Unicode']
          ]
        ])
    self.assertEqual(xml, target)


if __name__ == '__main__':
  unittest.main()

########NEW FILE########
__FILENAME__ = android
# Copyright (c) 2012 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Notes:
#
# This generates makefiles suitable for inclusion into the Android build system
# via an Android.mk file. It is based on make.py, the standard makefile
# generator.
#
# The code below generates a separate .mk file for each target, but
# all are sourced by the top-level GypAndroid.mk.  This means that all
# variables in .mk-files clobber one another, and furthermore that any
# variables set potentially clash with other Android build system variables.
# Try to avoid setting global variables where possible.

import gyp
import gyp.common
import gyp.generator.make as make  # Reuse global functions from make backend.
import os
import re

generator_default_variables = {
  'OS': 'android',
  'EXECUTABLE_PREFIX': '',
  'EXECUTABLE_SUFFIX': '',
  'STATIC_LIB_PREFIX': 'lib',
  'SHARED_LIB_PREFIX': 'lib',
  'STATIC_LIB_SUFFIX': '.a',
  'SHARED_LIB_SUFFIX': '.so',
  'INTERMEDIATE_DIR': '$(gyp_intermediate_dir)',
  'SHARED_INTERMEDIATE_DIR': '$(gyp_shared_intermediate_dir)',
  'PRODUCT_DIR': '$(gyp_shared_intermediate_dir)',
  'SHARED_LIB_DIR': '$(builddir)/lib.$(TOOLSET)',
  'LIB_DIR': '$(obj).$(TOOLSET)',
  'RULE_INPUT_ROOT': '%(INPUT_ROOT)s',  # This gets expanded by Python.
  'RULE_INPUT_DIRNAME': '%(INPUT_DIRNAME)s',  # This gets expanded by Python.
  'RULE_INPUT_PATH': '$(RULE_SOURCES)',
  'RULE_INPUT_EXT': '$(suffix $<)',
  'RULE_INPUT_NAME': '$(notdir $<)',
  'CONFIGURATION_NAME': 'NOT_USED_ON_ANDROID',
}

# Make supports multiple toolsets
generator_supports_multiple_toolsets = True


# Generator-specific gyp specs.
generator_additional_non_configuration_keys = [
    # Boolean to declare that this target does not want its name mangled.
    'android_unmangled_name',
]
generator_additional_path_sections = []
generator_extra_sources_for_rules = []


SHARED_FOOTER = """\
# "gyp_all_modules" is a concatenation of the "gyp_all_modules" targets from
# all the included sub-makefiles. This is just here to clarify.
gyp_all_modules:
"""

header = """\
# This file is generated by gyp; do not edit.

"""

android_standard_include_paths = set([
    # JNI_H_INCLUDE in build/core/binary.mk
    'dalvik/libnativehelper/include/nativehelper',
    # from SRC_HEADERS in build/core/config.mk
    'system/core/include',
    'hardware/libhardware/include',
    'hardware/libhardware_legacy/include',
    'hardware/ril/include',
    'dalvik/libnativehelper/include',
    'frameworks/native/include',
    'frameworks/native/opengl/include',
    'frameworks/base/include',
    'frameworks/base/opengl/include',
    'frameworks/base/native/include',
    'external/skia/include',
    # TARGET_C_INCLUDES in build/core/combo/TARGET_linux-arm.mk
    'bionic/libc/arch-arm/include',
    'bionic/libc/include',
    'bionic/libstdc++/include',
    'bionic/libc/kernel/common',
    'bionic/libc/kernel/arch-arm',
    'bionic/libm/include',
    'bionic/libm/include/arm',
    'bionic/libthread_db/include',
    ])


# Map gyp target types to Android module classes.
MODULE_CLASSES = {
    'static_library': 'STATIC_LIBRARIES',
    'shared_library': 'SHARED_LIBRARIES',
    'executable': 'EXECUTABLES',
}


def IsCPPExtension(ext):
  return make.COMPILABLE_EXTENSIONS.get(ext) == 'cxx'


def Sourceify(path):
  """Convert a path to its source directory form. The Android backend does not
     support options.generator_output, so this function is a noop."""
  return path


# Map from qualified target to path to output.
# For Android, the target of these maps is a tuple ('static', 'modulename'),
# ('dynamic', 'modulename'), or ('path', 'some/path') instead of a string,
# since we link by module.
target_outputs = {}
# Map from qualified target to any linkable output.  A subset
# of target_outputs.  E.g. when mybinary depends on liba, we want to
# include liba in the linker line; when otherbinary depends on
# mybinary, we just want to build mybinary first.
target_link_deps = {}


class AndroidMkWriter(object):
  """AndroidMkWriter packages up the writing of one target-specific Android.mk.

  Its only real entry point is Write(), and is mostly used for namespacing.
  """

  def __init__(self, android_top_dir):
    self.android_top_dir = android_top_dir

  def Write(self, qualified_target, base_path, output_filename, spec, configs,
            part_of_all):
    """The main entry point: writes a .mk file for a single target.

    Arguments:
      qualified_target: target we're generating
      base_path: path relative to source root we're building in, used to resolve
                 target-relative paths
      output_filename: output .mk file name to write
      spec, configs: gyp info
      part_of_all: flag indicating this target is part of 'all'
    """
    make.ensure_directory_exists(output_filename)

    self.fp = open(output_filename, 'w')

    self.fp.write(header)

    self.qualified_target = qualified_target
    self.path = base_path
    self.target = spec['target_name']
    self.type = spec['type']
    self.toolset = spec['toolset']

    deps, link_deps = self.ComputeDeps(spec)

    # Some of the generation below can add extra output, sources, or
    # link dependencies.  All of the out params of the functions that
    # follow use names like extra_foo.
    extra_outputs = []
    extra_sources = []

    self.android_class = MODULE_CLASSES.get(self.type, 'GYP')
    self.android_module = self.ComputeAndroidModule(spec)
    (self.android_stem, self.android_suffix) = self.ComputeOutputParts(spec)
    self.output = self.output_binary = self.ComputeOutput(spec)

    # Standard header.
    self.WriteLn('include $(CLEAR_VARS)\n')

    # Module class and name.
    self.WriteLn('LOCAL_MODULE_CLASS := ' + self.android_class)
    self.WriteLn('LOCAL_MODULE := ' + self.android_module)
    # Only emit LOCAL_MODULE_STEM if it's different to LOCAL_MODULE.
    # The library module classes fail if the stem is set. ComputeOutputParts
    # makes sure that stem == modulename in these cases.
    if self.android_stem != self.android_module:
      self.WriteLn('LOCAL_MODULE_STEM := ' + self.android_stem)
    self.WriteLn('LOCAL_MODULE_SUFFIX := ' + self.android_suffix)
    self.WriteLn('LOCAL_MODULE_TAGS := optional')
    if self.toolset == 'host':
      self.WriteLn('LOCAL_IS_HOST_MODULE := true')

    # Grab output directories; needed for Actions and Rules.
    self.WriteLn('gyp_intermediate_dir := $(call local-intermediates-dir)')
    self.WriteLn('gyp_shared_intermediate_dir := '
                 '$(call intermediates-dir-for,GYP,shared)')
    self.WriteLn()

    # List files this target depends on so that actions/rules/copies/sources
    # can depend on the list.
    # TODO: doesn't pull in things through transitive link deps; needed?
    target_dependencies = [x[1] for x in deps if x[0] == 'path']
    self.WriteLn('# Make sure our deps are built first.')
    self.WriteList(target_dependencies, 'GYP_TARGET_DEPENDENCIES',
                   local_pathify=True)

    # Actions must come first, since they can generate more OBJs for use below.
    if 'actions' in spec:
      self.WriteActions(spec['actions'], extra_sources, extra_outputs)

    # Rules must be early like actions.
    if 'rules' in spec:
      self.WriteRules(spec['rules'], extra_sources, extra_outputs)

    if 'copies' in spec:
      self.WriteCopies(spec['copies'], extra_outputs)

    # GYP generated outputs.
    self.WriteList(extra_outputs, 'GYP_GENERATED_OUTPUTS', local_pathify=True)

    # Set LOCAL_ADDITIONAL_DEPENDENCIES so that Android's build rules depend
    # on both our dependency targets and our generated files.
    self.WriteLn('# Make sure our deps and generated files are built first.')
    self.WriteLn('LOCAL_ADDITIONAL_DEPENDENCIES := $(GYP_TARGET_DEPENDENCIES) '
                 '$(GYP_GENERATED_OUTPUTS)')
    self.WriteLn()

    # Sources.
    if spec.get('sources', []) or extra_sources:
      self.WriteSources(spec, configs, extra_sources)

    self.WriteTarget(spec, configs, deps, link_deps, part_of_all)

    # Update global list of target outputs, used in dependency tracking.
    target_outputs[qualified_target] = ('path', self.output_binary)

    # Update global list of link dependencies.
    if self.type == 'static_library':
      target_link_deps[qualified_target] = ('static', self.android_module)
    elif self.type == 'shared_library':
      target_link_deps[qualified_target] = ('shared', self.android_module)

    self.fp.close()
    return self.android_module


  def WriteActions(self, actions, extra_sources, extra_outputs):
    """Write Makefile code for any 'actions' from the gyp input.

    extra_sources: a list that will be filled in with newly generated source
                   files, if any
    extra_outputs: a list that will be filled in with any outputs of these
                   actions (used to make other pieces dependent on these
                   actions)
    """
    for action in actions:
      name = make.StringToMakefileVariable('%s_%s' % (self.qualified_target,
                                                      action['action_name']))
      self.WriteLn('### Rules for action "%s":' % action['action_name'])
      inputs = action['inputs']
      outputs = action['outputs']

      # Build up a list of outputs.
      # Collect the output dirs we'll need.
      dirs = set()
      for out in outputs:
        if not out.startswith('$'):
          print ('WARNING: Action for target "%s" writes output to local path '
                 '"%s".' % (self.target, out))
        dir = os.path.split(out)[0]
        if dir:
          dirs.add(dir)
      if int(action.get('process_outputs_as_sources', False)):
        extra_sources += outputs

      # Prepare the actual command.
      command = gyp.common.EncodePOSIXShellList(action['action'])
      if 'message' in action:
        quiet_cmd = 'Gyp action: %s ($@)' % action['message']
      else:
        quiet_cmd = 'Gyp action: %s ($@)' % name
      if len(dirs) > 0:
        command = 'mkdir -p %s' % ' '.join(dirs) + '; ' + command

      cd_action = 'cd $(gyp_local_path)/%s; ' % self.path
      command = cd_action + command

      # The makefile rules are all relative to the top dir, but the gyp actions
      # are defined relative to their containing dir.  This replaces the gyp_*
      # variables for the action rule with an absolute version so that the
      # output goes in the right place.
      # Only write the gyp_* rules for the "primary" output (:1);
      # it's superfluous for the "extra outputs", and this avoids accidentally
      # writing duplicate dummy rules for those outputs.
      main_output = make.QuoteSpaces(self.LocalPathify(outputs[0]))
      self.WriteLn('%s: gyp_local_path := $(LOCAL_PATH)' % main_output)
      self.WriteLn('%s: gyp_intermediate_dir := '
                   '$(GYP_ABS_ANDROID_TOP_DIR)/$(gyp_intermediate_dir)' %
                   main_output)
      self.WriteLn('%s: gyp_shared_intermediate_dir := '
                   '$(GYP_ABS_ANDROID_TOP_DIR)/$(gyp_shared_intermediate_dir)' %
                   main_output)

      for input in inputs:
        assert ' ' not in input, (
            "Spaces in action input filenames not supported (%s)"  % input)
      for output in outputs:
        assert ' ' not in output, (
            "Spaces in action output filenames not supported (%s)"  % output)

      self.WriteLn('%s: %s $(GYP_TARGET_DEPENDENCIES)' %
                   (main_output, ' '.join(map(self.LocalPathify, inputs))))
      self.WriteLn('\t@echo "%s"' % quiet_cmd)
      self.WriteLn('\t$(hide)%s\n' % command)
      for output in outputs[1:]:
        # Make each output depend on the main output, with an empty command
        # to force make to notice that the mtime has changed.
        self.WriteLn('%s: %s ;' % (self.LocalPathify(output), main_output))

      extra_outputs += outputs
      self.WriteLn()

    self.WriteLn()


  def WriteRules(self, rules, extra_sources, extra_outputs):
    """Write Makefile code for any 'rules' from the gyp input.

    extra_sources: a list that will be filled in with newly generated source
                   files, if any
    extra_outputs: a list that will be filled in with any outputs of these
                   rules (used to make other pieces dependent on these rules)
    """
    if len(rules) == 0:
      return
    rule_trigger = '%s_rule_trigger' % self.android_module

    did_write_rule = False
    for rule in rules:
      if len(rule.get('rule_sources', [])) == 0:
        continue
      did_write_rule = True
      name = make.StringToMakefileVariable('%s_%s' % (self.qualified_target,
                                                      rule['rule_name']))
      self.WriteLn('\n### Generated for rule "%s":' % name)
      self.WriteLn('# "%s":' % rule)

      inputs = rule.get('inputs')
      for rule_source in rule.get('rule_sources', []):
        (rule_source_dirname, rule_source_basename) = os.path.split(rule_source)
        (rule_source_root, rule_source_ext) = \
            os.path.splitext(rule_source_basename)

        outputs = [self.ExpandInputRoot(out, rule_source_root,
                                        rule_source_dirname)
                   for out in rule['outputs']]

        dirs = set()
        for out in outputs:
          if not out.startswith('$'):
            print ('WARNING: Rule for target %s writes output to local path %s'
                   % (self.target, out))
          dir = os.path.dirname(out)
          if dir:
            dirs.add(dir)
        extra_outputs += outputs
        if int(rule.get('process_outputs_as_sources', False)):
          extra_sources.extend(outputs)

        components = []
        for component in rule['action']:
          component = self.ExpandInputRoot(component, rule_source_root,
                                           rule_source_dirname)
          if '$(RULE_SOURCES)' in component:
            component = component.replace('$(RULE_SOURCES)',
                                          rule_source)
          components.append(component)

        command = gyp.common.EncodePOSIXShellList(components)
        cd_action = 'cd $(gyp_local_path)/%s; ' % self.path
        command = cd_action + command
        if dirs:
          command = 'mkdir -p %s' % ' '.join(dirs) + '; ' + command

        # We set up a rule to build the first output, and then set up
        # a rule for each additional output to depend on the first.
        outputs = map(self.LocalPathify, outputs)
        main_output = outputs[0]
        self.WriteLn('%s: gyp_local_path := $(LOCAL_PATH)' % main_output)
        self.WriteLn('%s: gyp_intermediate_dir := '
                     '$(GYP_ABS_ANDROID_TOP_DIR)/$(gyp_intermediate_dir)'
                     % main_output)
        self.WriteLn('%s: gyp_shared_intermediate_dir := '
                     '$(GYP_ABS_ANDROID_TOP_DIR)/$(gyp_shared_intermediate_dir)'
                     % main_output)

        main_output_deps = self.LocalPathify(rule_source)
        if inputs:
          main_output_deps += ' '
          main_output_deps += ' '.join([self.LocalPathify(f) for f in inputs])

        self.WriteLn('%s: %s $(GYP_TARGET_DEPENDENCIES)' %
                     (main_output, main_output_deps))
        self.WriteLn('\t%s\n' % command)
        for output in outputs[1:]:
          self.WriteLn('%s: %s' % (output, main_output))
        self.WriteLn('.PHONY: %s' % (rule_trigger))
        self.WriteLn('%s: %s' % (rule_trigger, main_output))
        self.WriteLn('')
    if did_write_rule:
      extra_sources.append(rule_trigger)  # Force all rules to run.
      self.WriteLn('### Finished generating for all rules')
      self.WriteLn('')


  def WriteCopies(self, copies, extra_outputs):
    """Write Makefile code for any 'copies' from the gyp input.

    extra_outputs: a list that will be filled in with any outputs of this action
                   (used to make other pieces dependent on this action)
    """
    self.WriteLn('### Generated for copy rule.')

    variable = make.StringToMakefileVariable(self.qualified_target + '_copies')
    outputs = []
    for copy in copies:
      for path in copy['files']:
        # The Android build system does not allow generation of files into the
        # source tree. The destination should start with a variable, which will
        # typically be $(gyp_intermediate_dir) or
        # $(gyp_shared_intermediate_dir). Note that we can't use an assertion
        # because some of the gyp tests depend on this.
        if not copy['destination'].startswith('$'):
          print ('WARNING: Copy rule for target %s writes output to '
                 'local path %s' % (self.target, copy['destination']))

        # LocalPathify() calls normpath, stripping trailing slashes.
        path = Sourceify(self.LocalPathify(path))
        filename = os.path.split(path)[1]
        output = Sourceify(self.LocalPathify(os.path.join(copy['destination'],
                                                          filename)))

        self.WriteLn('%s: %s $(GYP_TARGET_DEPENDENCIES) | $(ACP)' %
                     (output, path))
        self.WriteLn('\t@echo Copying: $@')
        self.WriteLn('\t$(hide) mkdir -p $(dir $@)')
        self.WriteLn('\t$(hide) $(ACP) -r $< $@')
        self.WriteLn()
        outputs.append(output)
    self.WriteLn('%s = %s' % (variable,
                              ' '.join(map(make.QuoteSpaces, outputs))))
    extra_outputs.append('$(%s)' % variable)
    self.WriteLn()


  def WriteSourceFlags(self, spec, configs):
    """Write out the flags and include paths used to compile source files for
    the current target.

    Args:
      spec, configs: input from gyp.
    """
    config = configs[spec['default_configuration']]
    extracted_includes = []

    self.WriteLn('\n# Flags passed to both C and C++ files.')
    cflags, includes_from_cflags = self.ExtractIncludesFromCFlags(
        config.get('cflags'))
    extracted_includes.extend(includes_from_cflags)
    self.WriteList(cflags, 'MY_CFLAGS')

    cflags_c, includes_from_cflags_c = self.ExtractIncludesFromCFlags(
        config.get('cflags_c'))
    extracted_includes.extend(includes_from_cflags_c)
    self.WriteList(cflags_c, 'MY_CFLAGS_C')

    self.WriteList(config.get('defines'), 'MY_DEFS', prefix='-D',
                   quoter=make.EscapeCppDefine)
    self.WriteLn('LOCAL_CFLAGS := $(MY_CFLAGS_C) $(MY_CFLAGS) $(MY_DEFS)')

    # Undefine ANDROID for host modules
    # TODO: the source code should not use macro ANDROID to tell if it's host or
    # target module.
    if self.toolset == 'host':
      self.WriteLn('# Undefine ANDROID for host modules')
      self.WriteLn('LOCAL_CFLAGS += -UANDROID')

    self.WriteLn('\n# Include paths placed before CFLAGS/CPPFLAGS')
    includes = list(config.get('include_dirs', []))
    includes.extend(extracted_includes)
    includes = map(Sourceify, map(self.LocalPathify, includes))
    includes = self.NormalizeIncludePaths(includes)
    self.WriteList(includes, 'LOCAL_C_INCLUDES')
    self.WriteLn('LOCAL_C_INCLUDES := $(GYP_COPIED_SOURCE_ORIGIN_DIRS) '
                                     '$(LOCAL_C_INCLUDES)')

    self.WriteLn('\n# Flags passed to only C++ (and not C) files.')
    self.WriteList(config.get('cflags_cc'), 'LOCAL_CPPFLAGS')


  def WriteSources(self, spec, configs, extra_sources):
    """Write Makefile code for any 'sources' from the gyp input.
    These are source files necessary to build the current target.
    We need to handle shared_intermediate directory source files as
    a special case by copying them to the intermediate directory and
    treating them as a genereated sources. Otherwise the Android build
    rules won't pick them up.

    Args:
      spec, configs: input from gyp.
      extra_sources: Sources generated from Actions or Rules.
    """
    sources = filter(make.Compilable, spec.get('sources', []))
    generated_not_sources = [x for x in extra_sources if not make.Compilable(x)]
    extra_sources = filter(make.Compilable, extra_sources)

    # Determine and output the C++ extension used by these sources.
    # We simply find the first C++ file and use that extension.
    all_sources = sources + extra_sources
    local_cpp_extension = '.cpp'
    for source in all_sources:
      (root, ext) = os.path.splitext(source)
      if IsCPPExtension(ext):
        local_cpp_extension = ext
        break
    if local_cpp_extension != '.cpp':
      self.WriteLn('LOCAL_CPP_EXTENSION := %s' % local_cpp_extension)

    # We need to move any non-generated sources that are coming from the
    # shared intermediate directory out of LOCAL_SRC_FILES and put them
    # into LOCAL_GENERATED_SOURCES. We also need to move over any C++ files
    # that don't match our local_cpp_extension, since Android will only
    # generate Makefile rules for a single LOCAL_CPP_EXTENSION.
    local_files = []
    for source in sources:
      (root, ext) = os.path.splitext(source)
      if '$(gyp_shared_intermediate_dir)' in source:
        extra_sources.append(source)
      elif '$(gyp_intermediate_dir)' in source:
        extra_sources.append(source)
      elif IsCPPExtension(ext) and ext != local_cpp_extension:
        extra_sources.append(source)
      else:
        local_files.append(os.path.normpath(os.path.join(self.path, source)))

    # For any generated source, if it is coming from the shared intermediate
    # directory then we add a Make rule to copy them to the local intermediate
    # directory first. This is because the Android LOCAL_GENERATED_SOURCES
    # must be in the local module intermediate directory for the compile rules
    # to work properly. If the file has the wrong C++ extension, then we add
    # a rule to copy that to intermediates and use the new version.
    final_generated_sources = []
    # If a source file gets copied, we still need to add the orginal source
    # directory as header search path, for GCC searches headers in the
    # directory that contains the source file by default.
    origin_src_dirs = []
    for source in extra_sources:
      local_file = source
      if not '$(gyp_intermediate_dir)/' in local_file:
        basename = os.path.basename(local_file)
        local_file = '$(gyp_intermediate_dir)/' + basename
      (root, ext) = os.path.splitext(local_file)
      if IsCPPExtension(ext) and ext != local_cpp_extension:
        local_file = root + local_cpp_extension
      if local_file != source:
        self.WriteLn('%s: %s' % (local_file, self.LocalPathify(source)))
        self.WriteLn('\tmkdir -p $(@D); cp $< $@')
        origin_src_dirs.append(os.path.dirname(source))
      final_generated_sources.append(local_file)

    # We add back in all of the non-compilable stuff to make sure that the
    # make rules have dependencies on them.
    final_generated_sources.extend(generated_not_sources)
    self.WriteList(final_generated_sources, 'LOCAL_GENERATED_SOURCES')

    origin_src_dirs = gyp.common.uniquer(origin_src_dirs)
    origin_src_dirs = map(Sourceify, map(self.LocalPathify, origin_src_dirs))
    self.WriteList(origin_src_dirs, 'GYP_COPIED_SOURCE_ORIGIN_DIRS')

    self.WriteList(local_files, 'LOCAL_SRC_FILES')

    # Write out the flags used to compile the source; this must be done last
    # so that GYP_COPIED_SOURCE_ORIGIN_DIRS can be used as an include path.
    self.WriteSourceFlags(spec, configs)


  def ComputeAndroidModule(self, spec):
    """Return the Android module name used for a gyp spec.

    We use the complete qualified target name to avoid collisions between
    duplicate targets in different directories. We also add a suffix to
    distinguish gyp-generated module names.
    """

    if int(spec.get('android_unmangled_name', 0)):
      assert self.type != 'shared_library' or self.target.startswith('lib')
      return self.target

    if self.type == 'shared_library':
      # For reasons of convention, the Android build system requires that all
      # shared library modules are named 'libfoo' when generating -l flags.
      prefix = 'lib_'
    else:
      prefix = ''

    if spec['toolset'] == 'host':
      suffix = '_host_gyp'
    else:
      suffix = '_gyp'

    if self.path:
      name = '%s%s_%s%s' % (prefix, self.path, self.target, suffix)
    else:
      name = '%s%s%s' % (prefix, self.target, suffix)

    return make.StringToMakefileVariable(name)


  def ComputeOutputParts(self, spec):
    """Return the 'output basename' of a gyp spec, split into filename + ext.

    Android libraries must be named the same thing as their module name,
    otherwise the linker can't find them, so product_name and so on must be
    ignored if we are building a library, and the "lib" prepending is
    not done for Android.
    """
    assert self.type != 'loadable_module' # TODO: not supported?

    target = spec['target_name']
    target_prefix = ''
    target_ext = ''
    if self.type == 'static_library':
      target = self.ComputeAndroidModule(spec)
      target_ext = '.a'
    elif self.type == 'shared_library':
      target = self.ComputeAndroidModule(spec)
      target_ext = '.so'
    elif self.type == 'none':
      target_ext = '.stamp'
    elif self.type != 'executable':
      print ("ERROR: What output file should be generated?",
             "type", self.type, "target", target)

    if self.type != 'static_library' and self.type != 'shared_library':
      target_prefix = spec.get('product_prefix', target_prefix)
      target = spec.get('product_name', target)
      product_ext = spec.get('product_extension')
      if product_ext:
        target_ext = '.' + product_ext

    target_stem = target_prefix + target
    return (target_stem, target_ext)


  def ComputeOutputBasename(self, spec):
    """Return the 'output basename' of a gyp spec.

    E.g., the loadable module 'foobar' in directory 'baz' will produce
      'libfoobar.so'
    """
    return ''.join(self.ComputeOutputParts(spec))


  def ComputeOutput(self, spec):
    """Return the 'output' (full output path) of a gyp spec.

    E.g., the loadable module 'foobar' in directory 'baz' will produce
      '$(obj)/baz/libfoobar.so'
    """
    if self.type == 'executable' and self.toolset == 'host':
      # We install host executables into shared_intermediate_dir so they can be
      # run by gyp rules that refer to PRODUCT_DIR.
      path = '$(gyp_shared_intermediate_dir)'
    elif self.type == 'shared_library':
      if self.toolset == 'host':
        path = '$(HOST_OUT_INTERMEDIATE_LIBRARIES)'
      else:
        path = '$(TARGET_OUT_INTERMEDIATE_LIBRARIES)'
    else:
      # Other targets just get built into their intermediate dir.
      if self.toolset == 'host':
        path = '$(call intermediates-dir-for,%s,%s,true)' % (self.android_class,
                                                            self.android_module)
      else:
        path = '$(call intermediates-dir-for,%s,%s)' % (self.android_class,
                                                        self.android_module)

    assert spec.get('product_dir') is None # TODO: not supported?
    return os.path.join(path, self.ComputeOutputBasename(spec))


  def NormalizeLdFlags(self, ld_flags):
    """ Clean up ldflags from gyp file.
    Remove any ldflags that contain android_top_dir.

    Args:
      ld_flags: ldflags from gyp files.

    Returns:
      clean ldflags
    """
    clean_ldflags = []
    for flag in ld_flags:
      if self.android_top_dir in flag:
        continue
      clean_ldflags.append(flag)
    return clean_ldflags

  def NormalizeIncludePaths(self, include_paths):
    """ Normalize include_paths.
    Convert absolute paths to relative to the Android top directory;
    filter out include paths that are already brought in by the Android build
    system.

    Args:
      include_paths: A list of unprocessed include paths.
    Returns:
      A list of normalized include paths.
    """
    normalized = []
    for path in include_paths:
      if path[0] == '/':
        path = gyp.common.RelativePath(path, self.android_top_dir)

      # Filter out the Android standard search path.
      if path not in android_standard_include_paths:
        normalized.append(path)
    return normalized

  def ExtractIncludesFromCFlags(self, cflags):
    """Extract includes "-I..." out from cflags

    Args:
      cflags: A list of compiler flags, which may be mixed with "-I.."
    Returns:
      A tuple of lists: (clean_clfags, include_paths). "-I.." is trimmed.
    """
    clean_cflags = []
    include_paths = []
    if cflags:
      for flag in cflags:
        if flag.startswith('-I'):
          include_paths.append(flag[2:])
        else:
          clean_cflags.append(flag)

    return (clean_cflags, include_paths)

  def ComputeAndroidLibraryModuleNames(self, libraries):
    """Compute the Android module names from libraries, ie spec.get('libraries')

    Args:
      libraries: the value of spec.get('libraries')
    Returns:
      A tuple (static_lib_modules, dynamic_lib_modules)
    """
    static_lib_modules = []
    dynamic_lib_modules = []
    for libs in libraries:
      # Libs can have multiple words.
      for lib in libs.split():
        # Filter the system libraries, which are added by default by the Android
        # build system.
        if (lib == '-lc' or lib == '-lstdc++' or lib == '-lm' or
            lib.endswith('libgcc.a')):
          continue
        match = re.search(r'([^/]+)\.a$', lib)
        if match:
          static_lib_modules.append(match.group(1))
          continue
        match = re.search(r'([^/]+)\.so$', lib)
        if match:
          dynamic_lib_modules.append(match.group(1))
          continue
        # "-lstlport" -> libstlport
        if lib.startswith('-l'):
          if lib.endswith('_static'):
            static_lib_modules.append('lib' + lib[2:])
          else:
            dynamic_lib_modules.append('lib' + lib[2:])
    return (static_lib_modules, dynamic_lib_modules)


  def ComputeDeps(self, spec):
    """Compute the dependencies of a gyp spec.

    Returns a tuple (deps, link_deps), where each is a list of
    filenames that will need to be put in front of make for either
    building (deps) or linking (link_deps).
    """
    deps = []
    link_deps = []
    if 'dependencies' in spec:
      deps.extend([target_outputs[dep] for dep in spec['dependencies']
                   if target_outputs[dep]])
      for dep in spec['dependencies']:
        if dep in target_link_deps:
          link_deps.append(target_link_deps[dep])
      deps.extend(link_deps)
    return (gyp.common.uniquer(deps), gyp.common.uniquer(link_deps))


  def WriteTargetFlags(self, spec, configs, link_deps):
    """Write Makefile code to specify the link flags and library dependencies.

    spec, configs: input from gyp.
    link_deps: link dependency list; see ComputeDeps()
    """
    config = configs[spec['default_configuration']]

    # LDFLAGS
    ldflags = list(config.get('ldflags', []))
    static_flags, dynamic_flags = self.ComputeAndroidLibraryModuleNames(
        ldflags)
    self.WriteLn('')
    self.WriteList(self.NormalizeLdFlags(ldflags), 'LOCAL_LDFLAGS')

    # Libraries (i.e. -lfoo)
    libraries = gyp.common.uniquer(spec.get('libraries', []))
    static_libs, dynamic_libs = self.ComputeAndroidLibraryModuleNames(
        libraries)

    # Link dependencies (i.e. libfoo.a, libfoo.so)
    static_link_deps = [x[1] for x in link_deps if x[0] == 'static']
    shared_link_deps = [x[1] for x in link_deps if x[0] == 'shared']
    self.WriteLn('')
    self.WriteList(static_flags + static_libs + static_link_deps,
                   'LOCAL_STATIC_LIBRARIES')
    self.WriteLn('# Enable grouping to fix circular references')
    self.WriteLn('LOCAL_GROUP_STATIC_LIBRARIES := true')
    self.WriteLn('')
    self.WriteList(dynamic_flags + dynamic_libs + shared_link_deps,
                   'LOCAL_SHARED_LIBRARIES')


  def WriteTarget(self, spec, configs, deps, link_deps, part_of_all):
    """Write Makefile code to produce the final target of the gyp spec.

    spec, configs: input from gyp.
    deps, link_deps: dependency lists; see ComputeDeps()
    part_of_all: flag indicating this target is part of 'all'
    """
    self.WriteLn('### Rules for final target.')

    if self.type != 'none':
      self.WriteTargetFlags(spec, configs, link_deps)

    # Add to the set of targets which represent the gyp 'all' target. We use the
    # name 'gyp_all_modules' as the Android build system doesn't allow the use
    # of the Make target 'all' and because 'all_modules' is the equivalent of
    # the Make target 'all' on Android.
    if part_of_all:
      self.WriteLn('# Add target alias to "gyp_all_modules" target.')
      self.WriteLn('.PHONY: gyp_all_modules')
      self.WriteLn('gyp_all_modules: %s' % self.android_module)
      self.WriteLn('')

    # Add an alias from the gyp target name to the Android module name. This
    # simplifies manual builds of the target, and is required by the test
    # framework.
    if self.target != self.android_module:
      self.WriteLn('# Alias gyp target name.')
      self.WriteLn('.PHONY: %s' % self.target)
      self.WriteLn('%s: %s' % (self.target, self.android_module))
      self.WriteLn('')

    # Add the command to trigger build of the target type depending
    # on the toolset. Ex: BUILD_STATIC_LIBRARY vs. BUILD_HOST_STATIC_LIBRARY
    # NOTE: This has to come last!
    modifier = ''
    if self.toolset == 'host':
      modifier = 'HOST_'
    if self.type == 'static_library':
      self.WriteLn('include $(BUILD_%sSTATIC_LIBRARY)' % modifier)
    elif self.type == 'shared_library':
      self.WriteLn('LOCAL_PRELINK_MODULE := false')
      self.WriteLn('include $(BUILD_%sSHARED_LIBRARY)' % modifier)
    elif self.type == 'executable':
      if self.toolset == 'host':
        self.WriteLn('LOCAL_MODULE_PATH := $(gyp_shared_intermediate_dir)')
      else:
        # Don't install target executables for now, as it results in them being
        # included in ROM. This can be revisited if there's a reason to install
        # them later.
        self.WriteLn('LOCAL_UNINSTALLABLE_MODULE := true')
      self.WriteLn('include $(BUILD_%sEXECUTABLE)' % modifier)
    else:
      self.WriteLn('LOCAL_MODULE_PATH := $(PRODUCT_OUT)/gyp_stamp')
      self.WriteLn('LOCAL_UNINSTALLABLE_MODULE := true')
      self.WriteLn()
      self.WriteLn('include $(BUILD_SYSTEM)/base_rules.mk')
      self.WriteLn()
      self.WriteLn('$(LOCAL_BUILT_MODULE): $(LOCAL_ADDITIONAL_DEPENDENCIES)')
      self.WriteLn('\t$(hide) echo "Gyp timestamp: $@"')
      self.WriteLn('\t$(hide) mkdir -p $(dir $@)')
      self.WriteLn('\t$(hide) touch $@')


  def WriteList(self, value_list, variable=None, prefix='',
                quoter=make.QuoteIfNecessary, local_pathify=False):
    """Write a variable definition that is a list of values.

    E.g. WriteList(['a','b'], 'foo', prefix='blah') writes out
         foo = blaha blahb
    but in a pretty-printed style.
    """
    values = ''
    if value_list:
      value_list = [quoter(prefix + l) for l in value_list]
      if local_pathify:
        value_list = [self.LocalPathify(l) for l in value_list]
      values = ' \\\n\t' + ' \\\n\t'.join(value_list)
    self.fp.write('%s :=%s\n\n' % (variable, values))


  def WriteLn(self, text=''):
    self.fp.write(text + '\n')


  def LocalPathify(self, path):
    """Convert a subdirectory-relative path into a normalized path which starts
    with the make variable $(LOCAL_PATH) (i.e. the top of the project tree).
    Absolute paths, or paths that contain variables, are just normalized."""
    if '$(' in path or os.path.isabs(path):
      # path is not a file in the project tree in this case, but calling
      # normpath is still important for trimming trailing slashes.
      return os.path.normpath(path)
    local_path = os.path.join('$(LOCAL_PATH)', self.path, path)
    local_path = os.path.normpath(local_path)
    # Check that normalizing the path didn't ../ itself out of $(LOCAL_PATH)
    # - i.e. that the resulting path is still inside the project tree. The
    # path may legitimately have ended up containing just $(LOCAL_PATH), though,
    # so we don't look for a slash.
    assert local_path.startswith('$(LOCAL_PATH)'), (
           'Path %s attempts to escape from gyp path %s !)' % (path, self.path))
    return local_path


  def ExpandInputRoot(self, template, expansion, dirname):
    if '%(INPUT_ROOT)s' not in template and '%(INPUT_DIRNAME)s' not in template:
      return template
    path = template % {
        'INPUT_ROOT': expansion,
        'INPUT_DIRNAME': dirname,
        }
    return path


def WriteAutoRegenerationRule(params, root_makefile, makefile_name,
                              build_files):
  """Write the target to regenerate the Makefile."""
  options = params['options']
  # Sort to avoid non-functional changes to makefile.
  build_files = sorted([os.path.join('$(LOCAL_PATH)', f) for f in build_files])
  build_files_args = [gyp.common.RelativePath(filename, options.toplevel_dir)
                      for filename in params['build_files_arg']]
  build_files_args = [os.path.join('$(PRIVATE_LOCAL_PATH)', f)
                      for f in build_files_args]
  gyp_binary = gyp.common.FixIfRelativePath(params['gyp_binary'],
                                            options.toplevel_dir)
  makefile_path = os.path.join('$(LOCAL_PATH)', makefile_name)
  if not gyp_binary.startswith(os.sep):
    gyp_binary = os.path.join('.', gyp_binary)
  root_makefile.write('GYP_FILES := \\\n  %s\n\n' %
                      '\\\n  '.join(map(Sourceify, build_files)))
  root_makefile.write('%s: PRIVATE_LOCAL_PATH := $(LOCAL_PATH)\n' %
                      makefile_path)
  root_makefile.write('%s: $(GYP_FILES)\n' % makefile_path)
  root_makefile.write('\techo ACTION Regenerating $@\n\t%s\n\n' %
      gyp.common.EncodePOSIXShellList([gyp_binary, '-fandroid'] +
                                      gyp.RegenerateFlags(options) +
                                      build_files_args))


def GenerateOutput(target_list, target_dicts, data, params):
  options = params['options']
  generator_flags = params.get('generator_flags', {})
  builddir_name = generator_flags.get('output_dir', 'out')
  limit_to_target_all = generator_flags.get('limit_to_target_all', False)
  android_top_dir = os.environ.get('ANDROID_BUILD_TOP')
  assert android_top_dir, '$ANDROID_BUILD_TOP not set; you need to run lunch.'

  def CalculateMakefilePath(build_file, base_name):
    """Determine where to write a Makefile for a given gyp file."""
    # Paths in gyp files are relative to the .gyp file, but we want
    # paths relative to the source root for the master makefile.  Grab
    # the path of the .gyp file as the base to relativize against.
    # E.g. "foo/bar" when we're constructing targets for "foo/bar/baz.gyp".
    base_path = gyp.common.RelativePath(os.path.dirname(build_file),
                                        options.depth)
    # We write the file in the base_path directory.
    output_file = os.path.join(options.depth, base_path, base_name)
    assert not options.generator_output, (
        'The Android backend does not support options.generator_output.')
    base_path = gyp.common.RelativePath(os.path.dirname(build_file),
                                        options.toplevel_dir)
    return base_path, output_file

  # TODO:  search for the first non-'Default' target.  This can go
  # away when we add verification that all targets have the
  # necessary configurations.
  default_configuration = None
  toolsets = set([target_dicts[target]['toolset'] for target in target_list])
  for target in target_list:
    spec = target_dicts[target]
    if spec['default_configuration'] != 'Default':
      default_configuration = spec['default_configuration']
      break
  if not default_configuration:
    default_configuration = 'Default'

  srcdir = '.'
  makefile_name = 'GypAndroid.mk' + options.suffix
  makefile_path = os.path.join(options.toplevel_dir, makefile_name)
  assert not options.generator_output, (
      'The Android backend does not support options.generator_output.')
  make.ensure_directory_exists(makefile_path)
  root_makefile = open(makefile_path, 'w')

  root_makefile.write(header)

  # We set LOCAL_PATH just once, here, to the top of the project tree. This
  # allows all the other paths we use to be relative to the Android.mk file,
  # as the Android build system expects.
  root_makefile.write('\nLOCAL_PATH := $(call my-dir)\n')

  # Find the list of targets that derive from the gyp file(s) being built.
  needed_targets = set()
  for build_file in params['build_files']:
    for target in gyp.common.AllTargets(target_list, target_dicts, build_file):
      needed_targets.add(target)

  build_files = set()
  include_list = set()
  android_modules = {}
  for qualified_target in target_list:
    build_file, target, toolset = gyp.common.ParseQualifiedTarget(
        qualified_target)
    build_files.add(gyp.common.RelativePath(build_file, options.toplevel_dir))
    included_files = data[build_file]['included_files']
    for included_file in included_files:
      # The included_files entries are relative to the dir of the build file
      # that included them, so we have to undo that and then make them relative
      # to the root dir.
      relative_include_file = gyp.common.RelativePath(
          gyp.common.UnrelativePath(included_file, build_file),
          options.toplevel_dir)
      abs_include_file = os.path.abspath(relative_include_file)
      # If the include file is from the ~/.gyp dir, we should use absolute path
      # so that relocating the src dir doesn't break the path.
      if (params['home_dot_gyp'] and
          abs_include_file.startswith(params['home_dot_gyp'])):
        build_files.add(abs_include_file)
      else:
        build_files.add(relative_include_file)

    base_path, output_file = CalculateMakefilePath(build_file,
        target + '.' + toolset + options.suffix + '.mk')

    spec = target_dicts[qualified_target]
    configs = spec['configurations']

    part_of_all = (qualified_target in needed_targets and
                   not int(spec.get('suppress_wildcard', False)))
    if limit_to_target_all and not part_of_all:
      continue
    writer = AndroidMkWriter(android_top_dir)
    android_module = writer.Write(qualified_target, base_path, output_file,
                                  spec, configs, part_of_all=part_of_all)
    if android_module in android_modules:
      print ('ERROR: Android module names must be unique. The following '
             'targets both generate Android module name %s.\n  %s\n  %s' %
             (android_module, android_modules[android_module],
              qualified_target))
      return
    android_modules[android_module] = qualified_target

    # Our root_makefile lives at the source root.  Compute the relative path
    # from there to the output_file for including.
    mkfile_rel_path = gyp.common.RelativePath(output_file,
                                              os.path.dirname(makefile_path))
    include_list.add(mkfile_rel_path)

  # Some tools need to know the absolute path of the top directory.
  root_makefile.write('GYP_ABS_ANDROID_TOP_DIR := $(shell pwd)\n')

  # Write out the sorted list of includes.
  root_makefile.write('\n')
  for include_file in sorted(include_list):
    root_makefile.write('include $(LOCAL_PATH)/' + include_file + '\n')
  root_makefile.write('\n')

  if generator_flags.get('auto_regeneration', True):
    WriteAutoRegenerationRule(params, root_makefile, makefile_name, build_files)

  root_makefile.write(SHARED_FOOTER)

  root_makefile.close()

########NEW FILE########
__FILENAME__ = dump_dependency_json
# Copyright (c) 2012 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import os
import gyp
import gyp.common
import gyp.msvs_emulation
import json
import sys

generator_supports_multiple_toolsets = True

generator_wants_static_library_dependencies_adjusted = False

generator_default_variables = {
}
for dirname in ['INTERMEDIATE_DIR', 'SHARED_INTERMEDIATE_DIR', 'PRODUCT_DIR',
                'LIB_DIR', 'SHARED_LIB_DIR']:
  # Some gyp steps fail if these are empty(!).
  generator_default_variables[dirname] = 'dir'
for unused in ['RULE_INPUT_PATH', 'RULE_INPUT_ROOT', 'RULE_INPUT_NAME',
               'RULE_INPUT_DIRNAME', 'RULE_INPUT_EXT',
               'EXECUTABLE_PREFIX', 'EXECUTABLE_SUFFIX',
               'STATIC_LIB_PREFIX', 'STATIC_LIB_SUFFIX',
               'SHARED_LIB_PREFIX', 'SHARED_LIB_SUFFIX',
               'CONFIGURATION_NAME']:
  generator_default_variables[unused] = ''


def CalculateVariables(default_variables, params):
  generator_flags = params.get('generator_flags', {})
  for key, val in generator_flags.items():
    default_variables.setdefault(key, val)
  default_variables.setdefault('OS', gyp.common.GetFlavor(params))

  flavor = gyp.common.GetFlavor(params)
  if flavor =='win':
    # Copy additional generator configuration data from VS, which is shared
    # by the Windows Ninja generator.
    import gyp.generator.msvs as msvs_generator
    generator_additional_non_configuration_keys = getattr(msvs_generator,
        'generator_additional_non_configuration_keys', [])
    generator_additional_path_sections = getattr(msvs_generator,
        'generator_additional_path_sections', [])

    # Set a variable so conditions can be based on msvs_version.
    msvs_version = gyp.msvs_emulation.GetVSVersion(generator_flags)
    default_variables['MSVS_VERSION'] = msvs_version.ShortName()

    # To determine processor word size on Windows, in addition to checking
    # PROCESSOR_ARCHITECTURE (which reflects the word size of the current
    # process), it is also necessary to check PROCESSOR_ARCHITEW6432 (which
    # contains the actual word size of the system when running thru WOW64).
    if ('64' in os.environ.get('PROCESSOR_ARCHITECTURE', '') or
        '64' in os.environ.get('PROCESSOR_ARCHITEW6432', '')):
      default_variables['MSVS_OS_BITS'] = 64
    else:
      default_variables['MSVS_OS_BITS'] = 32


def CalculateGeneratorInputInfo(params):
  """Calculate the generator specific info that gets fed to input (called by
  gyp)."""
  generator_flags = params.get('generator_flags', {})
  if generator_flags.get('adjust_static_libraries', False):
    global generator_wants_static_library_dependencies_adjusted
    generator_wants_static_library_dependencies_adjusted = True


def GenerateOutput(target_list, target_dicts, data, params):
  # Map of target -> list of targets it depends on.
  edges = {}

  # Queue of targets to visit.
  targets_to_visit = target_list[:]

  while len(targets_to_visit) > 0:
    target = targets_to_visit.pop()
    if target in edges:
      continue
    edges[target] = []

    for dep in target_dicts[target].get('dependencies', []):
      edges[target].append(dep)
      targets_to_visit.append(dep)

  filename = 'dump.json'
  f = open(filename, 'w')
  json.dump(edges, f)
  f.close()
  print 'Wrote json to %s.' % filename

########NEW FILE########
__FILENAME__ = eclipse
# Copyright (c) 2012 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""GYP backend that generates Eclipse CDT settings files.

This backend DOES NOT generate Eclipse CDT projects. Instead, it generates XML
files that can be imported into an Eclipse CDT project. The XML file contains a
list of include paths and symbols (i.e. defines).

Because a full .cproject definition is not created by this generator, it's not
possible to properly define the include dirs and symbols for each file
individually.  Instead, one set of includes/symbols is generated for the entire
project.  This works fairly well (and is a vast improvement in general), but may
still result in a few indexer issues here and there.

This generator has no automated tests, so expect it to be broken.
"""

from xml.sax.saxutils import escape
import os.path
import subprocess
import gyp
import gyp.common
import shlex

generator_wants_static_library_dependencies_adjusted = False

generator_default_variables = {
}

for dirname in ['INTERMEDIATE_DIR', 'PRODUCT_DIR', 'LIB_DIR', 'SHARED_LIB_DIR']:
  # Some gyp steps fail if these are empty(!).
  generator_default_variables[dirname] = 'dir'

for unused in ['RULE_INPUT_PATH', 'RULE_INPUT_ROOT', 'RULE_INPUT_NAME',
               'RULE_INPUT_DIRNAME', 'RULE_INPUT_EXT',
               'EXECUTABLE_PREFIX', 'EXECUTABLE_SUFFIX',
               'STATIC_LIB_PREFIX', 'STATIC_LIB_SUFFIX',
               'SHARED_LIB_PREFIX', 'SHARED_LIB_SUFFIX',
               'CONFIGURATION_NAME']:
  generator_default_variables[unused] = ''

# Include dirs will occasionaly use the SHARED_INTERMEDIATE_DIR variable as
# part of the path when dealing with generated headers.  This value will be
# replaced dynamically for each configuration.
generator_default_variables['SHARED_INTERMEDIATE_DIR'] = \
    '$SHARED_INTERMEDIATES_DIR'


def CalculateVariables(default_variables, params):
  generator_flags = params.get('generator_flags', {})
  for key, val in generator_flags.items():
    default_variables.setdefault(key, val)
  default_variables.setdefault('OS', gyp.common.GetFlavor(params))


def CalculateGeneratorInputInfo(params):
  """Calculate the generator specific info that gets fed to input (called by
  gyp)."""
  generator_flags = params.get('generator_flags', {})
  if generator_flags.get('adjust_static_libraries', False):
    global generator_wants_static_library_dependencies_adjusted
    generator_wants_static_library_dependencies_adjusted = True


def GetAllIncludeDirectories(target_list, target_dicts,
                             shared_intermediates_dir, config_name):
  """Calculate the set of include directories to be used.

  Returns:
    A list including all the include_dir's specified for every target followed
    by any include directories that were added as cflag compiler options.
  """

  gyp_includes_set = set()
  compiler_includes_list = []

  for target_name in target_list:
    target = target_dicts[target_name]
    if config_name in target['configurations']:
      config = target['configurations'][config_name]

      # Look for any include dirs that were explicitly added via cflags. This
      # may be done in gyp files to force certain includes to come at the end.
      # TODO(jgreenwald): Change the gyp files to not abuse cflags for this, and
      # remove this.
      cflags = config['cflags']
      for cflag in cflags:
        include_dir = ''
        if cflag.startswith('-I'):
          include_dir = cflag[2:]
        if include_dir and not include_dir in compiler_includes_list:
          compiler_includes_list.append(include_dir)

      # Find standard gyp include dirs.
      if config.has_key('include_dirs'):
        include_dirs = config['include_dirs']
        for include_dir in include_dirs:
          include_dir = include_dir.replace('$SHARED_INTERMEDIATES_DIR',
                                            shared_intermediates_dir)
          if not os.path.isabs(include_dir):
            base_dir = os.path.dirname(target_name)

            include_dir = base_dir + '/' + include_dir
            include_dir = os.path.abspath(include_dir)

          if not include_dir in gyp_includes_set:
            gyp_includes_set.add(include_dir)


  # Generate a list that has all the include dirs.
  all_includes_list = list(gyp_includes_set)
  all_includes_list.sort()
  for compiler_include in compiler_includes_list:
    if not compiler_include in gyp_includes_set:
      all_includes_list.append(compiler_include)

  # All done.
  return all_includes_list


def GetCompilerPath(target_list, target_dicts, data):
  """Determine a command that can be used to invoke the compiler.

  Returns:
    If this is a gyp project that has explicit make settings, try to determine
    the compiler from that.  Otherwise, see if a compiler was specified via the
    CC_target environment variable.
  """

  # First, see if the compiler is configured in make's settings.
  build_file, _, _ = gyp.common.ParseQualifiedTarget(target_list[0])
  make_global_settings_dict = data[build_file].get('make_global_settings', {})
  for key, value in make_global_settings_dict:
    if key in ['CC', 'CXX']:
      return value

  # Check to see if the compiler was specified as an environment variable.
  for key in ['CC_target', 'CC', 'CXX']:
    compiler = os.environ.get(key)
    if compiler:
      return compiler

  return 'gcc'


def GetAllDefines(target_list, target_dicts, data, config_name):
  """Calculate the defines for a project.

  Returns:
    A dict that includes explict defines declared in gyp files along with all of
    the default defines that the compiler uses.
  """

  # Get defines declared in the gyp files.
  all_defines = {}
  for target_name in target_list:
    target = target_dicts[target_name]

    if config_name in target['configurations']:
      config = target['configurations'][config_name]
      for define in config['defines']:
        split_define = define.split('=', 1)
        if len(split_define) == 1:
          split_define.append('1')
        if split_define[0].strip() in all_defines:
          # Already defined
          continue

        all_defines[split_define[0].strip()] = split_define[1].strip()

  # Get default compiler defines (if possible).
  cc_target = GetCompilerPath(target_list, target_dicts, data)
  if cc_target:
    command = shlex.split(cc_target)
    command.extend(['-E', '-dM', '-'])
    cpp_proc = subprocess.Popen(args=command, cwd='.',
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    cpp_output = cpp_proc.communicate()[0]
    cpp_lines = cpp_output.split('\n')
    for cpp_line in cpp_lines:
      if not cpp_line.strip():
        continue
      cpp_line_parts = cpp_line.split(' ', 2)
      key = cpp_line_parts[1]
      if len(cpp_line_parts) >= 3:
        val = cpp_line_parts[2]
      else:
        val = '1'
      all_defines[key] = val

  return all_defines


def WriteIncludePaths(out, eclipse_langs, include_dirs):
  """Write the includes section of a CDT settings export file."""

  out.write('  <section name="org.eclipse.cdt.internal.ui.wizards.' \
            'settingswizards.IncludePaths">\n')
  out.write('    <language name="holder for library settings"></language>\n')
  for lang in eclipse_langs:
    out.write('    <language name="%s">\n' % lang)
    for include_dir in include_dirs:
      out.write('      <includepath workspace_path="false">%s</includepath>\n' %
                include_dir)
    out.write('    </language>\n')
  out.write('  </section>\n')


def WriteMacros(out, eclipse_langs, defines):
  """Write the macros section of a CDT settings export file."""

  out.write('  <section name="org.eclipse.cdt.internal.ui.wizards.' \
            'settingswizards.Macros">\n')
  out.write('    <language name="holder for library settings"></language>\n')
  for lang in eclipse_langs:
    out.write('    <language name="%s">\n' % lang)
    for key in sorted(defines.iterkeys()):
      out.write('      <macro><name>%s</name><value>%s</value></macro>\n' %
                (escape(key), escape(defines[key])))
    out.write('    </language>\n')
  out.write('  </section>\n')


def GenerateOutputForConfig(target_list, target_dicts, data, params,
                            config_name):
  options = params['options']
  generator_flags = params.get('generator_flags', {})

  # build_dir: relative path from source root to our output files.
  # e.g. "out/Debug"
  build_dir = os.path.join(generator_flags.get('output_dir', 'out'),
                           config_name)

  toplevel_build = os.path.join(options.toplevel_dir, build_dir)
  shared_intermediate_dir = os.path.join(toplevel_build, 'obj', 'gen')

  if not os.path.exists(toplevel_build):
    os.makedirs(toplevel_build)
  out = open(os.path.join(toplevel_build, 'eclipse-cdt-settings.xml'), 'w')

  out.write('<?xml version="1.0" encoding="UTF-8"?>\n')
  out.write('<cdtprojectproperties>\n')

  eclipse_langs = ['C++ Source File', 'C Source File', 'Assembly Source File',
                   'GNU C++', 'GNU C', 'Assembly']
  include_dirs = GetAllIncludeDirectories(target_list, target_dicts,
                                          shared_intermediate_dir, config_name)
  WriteIncludePaths(out, eclipse_langs, include_dirs)
  defines = GetAllDefines(target_list, target_dicts, data, config_name)
  WriteMacros(out, eclipse_langs, defines)

  out.write('</cdtprojectproperties>\n')
  out.close()


def GenerateOutput(target_list, target_dicts, data, params):
  """Generate an XML settings file that can be imported into a CDT project."""

  if params['options'].generator_output:
    raise NotImplementedError, "--generator_output not implemented for eclipse"

  user_config = params.get('generator_flags', {}).get('config', None)
  if user_config:
    GenerateOutputForConfig(target_list, target_dicts, data, params,
                            user_config)
  else:
    config_names = target_dicts[target_list[0]]['configurations'].keys()
    for config_name in config_names:
      GenerateOutputForConfig(target_list, target_dicts, data, params,
                              config_name)


########NEW FILE########
__FILENAME__ = gypd
# Copyright (c) 2011 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""gypd output module

This module produces gyp input as its output.  Output files are given the
.gypd extension to avoid overwriting the .gyp files that they are generated
from.  Internal references to .gyp files (such as those found in
"dependencies" sections) are not adjusted to point to .gypd files instead;
unlike other paths, which are relative to the .gyp or .gypd file, such paths
are relative to the directory from which gyp was run to create the .gypd file.

This generator module is intended to be a sample and a debugging aid, hence
the "d" for "debug" in .gypd.  It is useful to inspect the results of the
various merges, expansions, and conditional evaluations performed by gyp
and to see a representation of what would be fed to a generator module.

It's not advisable to rename .gypd files produced by this module to .gyp,
because they will have all merges, expansions, and evaluations already
performed and the relevant constructs not present in the output; paths to
dependencies may be wrong; and various sections that do not belong in .gyp
files such as such as "included_files" and "*_excluded" will be present.
Output will also be stripped of comments.  This is not intended to be a
general-purpose gyp pretty-printer; for that, you probably just want to
run "pprint.pprint(eval(open('source.gyp').read()))", which will still strip
comments but won't do all of the other things done to this module's output.

The specific formatting of the output generated by this module is subject
to change.
"""


import gyp.common
import errno
import os
import pprint


# These variables should just be spit back out as variable references.
_generator_identity_variables = [
  'EXECUTABLE_PREFIX',
  'EXECUTABLE_SUFFIX',
  'INTERMEDIATE_DIR',
  'PRODUCT_DIR',
  'RULE_INPUT_ROOT',
  'RULE_INPUT_DIRNAME',
  'RULE_INPUT_EXT',
  'RULE_INPUT_NAME',
  'RULE_INPUT_PATH',
  'SHARED_INTERMEDIATE_DIR',
]

# gypd doesn't define a default value for OS like many other generator
# modules.  Specify "-D OS=whatever" on the command line to provide a value.
generator_default_variables = {
}

# gypd supports multiple toolsets
generator_supports_multiple_toolsets = True

# TODO(mark): This always uses <, which isn't right.  The input module should
# notify the generator to tell it which phase it is operating in, and this
# module should use < for the early phase and then switch to > for the late
# phase.  Bonus points for carrying @ back into the output too.
for v in _generator_identity_variables:
  generator_default_variables[v] = '<(%s)' % v


def GenerateOutput(target_list, target_dicts, data, params):
  output_files = {}
  for qualified_target in target_list:
    [input_file, target] = \
        gyp.common.ParseQualifiedTarget(qualified_target)[0:2]

    if input_file[-4:] != '.gyp':
      continue
    input_file_stem = input_file[:-4]
    output_file = input_file_stem + params['options'].suffix + '.gypd'

    if not output_file in output_files:
      output_files[output_file] = input_file

  for output_file, input_file in output_files.iteritems():
    output = open(output_file, 'w')
    pprint.pprint(data[input_file], output)
    output.close()

########NEW FILE########
__FILENAME__ = gypsh
# Copyright (c) 2011 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""gypsh output module

gypsh is a GYP shell.  It's not really a generator per se.  All it does is
fire up an interactive Python session with a few local variables set to the
variables passed to the generator.  Like gypd, it's intended as a debugging
aid, to facilitate the exploration of .gyp structures after being processed
by the input module.

The expected usage is "gyp -f gypsh -D OS=desired_os".
"""


import code
import sys


# All of this stuff about generator variables was lovingly ripped from gypd.py.
# That module has a much better description of what's going on and why.
_generator_identity_variables = [
  'EXECUTABLE_PREFIX',
  'EXECUTABLE_SUFFIX',
  'INTERMEDIATE_DIR',
  'PRODUCT_DIR',
  'RULE_INPUT_ROOT',
  'RULE_INPUT_DIRNAME',
  'RULE_INPUT_EXT',
  'RULE_INPUT_NAME',
  'RULE_INPUT_PATH',
  'SHARED_INTERMEDIATE_DIR',
]

generator_default_variables = {
}

for v in _generator_identity_variables:
  generator_default_variables[v] = '<(%s)' % v


def GenerateOutput(target_list, target_dicts, data, params):
  locals = {
        'target_list':  target_list,
        'target_dicts': target_dicts,
        'data':         data,
      }

  # Use a banner that looks like the stock Python one and like what
  # code.interact uses by default, but tack on something to indicate what
  # locals are available, and identify gypsh.
  banner='Python %s on %s\nlocals.keys() = %s\ngypsh' % \
         (sys.version, sys.platform, repr(sorted(locals.keys())))

  code.interact(banner, local=locals)

########NEW FILE########
__FILENAME__ = make
# Copyright (c) 2012 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Notes:
#
# This is all roughly based on the Makefile system used by the Linux
# kernel, but is a non-recursive make -- we put the entire dependency
# graph in front of make and let it figure it out.
#
# The code below generates a separate .mk file for each target, but
# all are sourced by the top-level Makefile.  This means that all
# variables in .mk-files clobber one another.  Be careful to use :=
# where appropriate for immediate evaluation, and similarly to watch
# that you're not relying on a variable value to last beween different
# .mk files.
#
# TODOs:
#
# Global settings and utility functions are currently stuffed in the
# toplevel Makefile.  It may make sense to generate some .mk files on
# the side to keep the the files readable.

import os
import re
import sys
import subprocess
import gyp
import gyp.common
import gyp.xcode_emulation
from gyp.common import GetEnvironFallback

generator_default_variables = {
  'EXECUTABLE_PREFIX': '',
  'EXECUTABLE_SUFFIX': '',
  'STATIC_LIB_PREFIX': 'lib',
  'SHARED_LIB_PREFIX': 'lib',
  'STATIC_LIB_SUFFIX': '.a',
  'INTERMEDIATE_DIR': '$(obj).$(TOOLSET)/$(TARGET)/geni',
  'SHARED_INTERMEDIATE_DIR': '$(obj)/gen',
  'PRODUCT_DIR': '$(builddir)',
  'RULE_INPUT_ROOT': '%(INPUT_ROOT)s',  # This gets expanded by Python.
  'RULE_INPUT_DIRNAME': '%(INPUT_DIRNAME)s',  # This gets expanded by Python.
  'RULE_INPUT_PATH': '$(abspath $<)',
  'RULE_INPUT_EXT': '$(suffix $<)',
  'RULE_INPUT_NAME': '$(notdir $<)',
  'CONFIGURATION_NAME': '$(BUILDTYPE)',
}

# Make supports multiple toolsets
generator_supports_multiple_toolsets = True

# Request sorted dependencies in the order from dependents to dependencies.
generator_wants_sorted_dependencies = False

# Placates pylint.
generator_additional_non_configuration_keys = []
generator_additional_path_sections = []
generator_extra_sources_for_rules = []


def CalculateVariables(default_variables, params):
  """Calculate additional variables for use in the build (called by gyp)."""
  flavor = gyp.common.GetFlavor(params)
  if flavor == 'mac':
    default_variables.setdefault('OS', 'mac')
    default_variables.setdefault('SHARED_LIB_SUFFIX', '.dylib')
    default_variables.setdefault('SHARED_LIB_DIR',
                                 generator_default_variables['PRODUCT_DIR'])
    default_variables.setdefault('LIB_DIR',
                                 generator_default_variables['PRODUCT_DIR'])

    # Copy additional generator configuration data from Xcode, which is shared
    # by the Mac Make generator.
    import gyp.generator.xcode as xcode_generator
    global generator_additional_non_configuration_keys
    generator_additional_non_configuration_keys = getattr(xcode_generator,
        'generator_additional_non_configuration_keys', [])
    global generator_additional_path_sections
    generator_additional_path_sections = getattr(xcode_generator,
        'generator_additional_path_sections', [])
    global generator_extra_sources_for_rules
    generator_extra_sources_for_rules = getattr(xcode_generator,
        'generator_extra_sources_for_rules', [])
    COMPILABLE_EXTENSIONS.update({'.m': 'objc', '.mm' : 'objcxx'})
  else:
    operating_system = flavor
    if flavor == 'android':
      operating_system = 'linux'  # Keep this legacy behavior for now.
    default_variables.setdefault('OS', operating_system)
    default_variables.setdefault('SHARED_LIB_SUFFIX', '.so')
    default_variables.setdefault('SHARED_LIB_DIR','$(builddir)/lib.$(TOOLSET)')
    default_variables.setdefault('LIB_DIR', '$(obj).$(TOOLSET)')


def CalculateGeneratorInputInfo(params):
  """Calculate the generator specific info that gets fed to input (called by
  gyp)."""
  generator_flags = params.get('generator_flags', {})
  android_ndk_version = generator_flags.get('android_ndk_version', None)
  # Android NDK requires a strict link order.
  if android_ndk_version:
    global generator_wants_sorted_dependencies
    generator_wants_sorted_dependencies = True


def ensure_directory_exists(path):
  dir = os.path.dirname(path)
  if dir and not os.path.exists(dir):
    os.makedirs(dir)


# The .d checking code below uses these functions:
# wildcard, sort, foreach, shell, wordlist
# wildcard can handle spaces, the rest can't.
# Since I could find no way to make foreach work with spaces in filenames
# correctly, the .d files have spaces replaced with another character. The .d
# file for
#     Chromium\ Framework.framework/foo
# is for example
#     out/Release/.deps/out/Release/Chromium?Framework.framework/foo
# This is the replacement character.
SPACE_REPLACEMENT = '?'


LINK_COMMANDS_LINUX = """\
quiet_cmd_alink = AR($(TOOLSET)) $@
cmd_alink = rm -f $@ && $(AR.$(TOOLSET)) crs $@ $(filter %.o,$^)

quiet_cmd_alink_thin = AR($(TOOLSET)) $@
cmd_alink_thin = rm -f $@ && $(AR.$(TOOLSET)) crsT $@ $(filter %.o,$^)

# Due to circular dependencies between libraries :(, we wrap the
# special "figure out circular dependencies" flags around the entire
# input list during linking.
quiet_cmd_link = LINK($(TOOLSET)) $@
cmd_link = $(LINK.$(TOOLSET)) $(GYP_LDFLAGS) $(LDFLAGS.$(TOOLSET)) -o $@ -Wl,--start-group $(LD_INPUTS) -Wl,--end-group $(LIBS)

# We support two kinds of shared objects (.so):
# 1) shared_library, which is just bundling together many dependent libraries
# into a link line.
# 2) loadable_module, which is generating a module intended for dlopen().
#
# They differ only slightly:
# In the former case, we want to package all dependent code into the .so.
# In the latter case, we want to package just the API exposed by the
# outermost module.
# This means shared_library uses --whole-archive, while loadable_module doesn't.
# (Note that --whole-archive is incompatible with the --start-group used in
# normal linking.)

# Other shared-object link notes:
# - Set SONAME to the library filename so our binaries don't reference
# the local, absolute paths used on the link command-line.
quiet_cmd_solink = SOLINK($(TOOLSET)) $@
cmd_solink = $(LINK.$(TOOLSET)) -shared $(GYP_LDFLAGS) $(LDFLAGS.$(TOOLSET)) -Wl,-soname=$(@F) -o $@ -Wl,--whole-archive $(LD_INPUTS) -Wl,--no-whole-archive $(LIBS)

quiet_cmd_solink_module = SOLINK_MODULE($(TOOLSET)) $@
cmd_solink_module = $(LINK.$(TOOLSET)) -shared $(GYP_LDFLAGS) $(LDFLAGS.$(TOOLSET)) -Wl,-soname=$(@F) -o $@ -Wl,--start-group $(filter-out FORCE_DO_CMD, $^) -Wl,--end-group $(LIBS)
"""

LINK_COMMANDS_MAC = """\
quiet_cmd_alink = LIBTOOL-STATIC $@
cmd_alink = rm -f $@ && ./gyp-mac-tool filter-libtool libtool $(GYP_LIBTOOLFLAGS) -static -o $@ $(filter %.o,$^)

quiet_cmd_link = LINK($(TOOLSET)) $@
cmd_link = $(LINK.$(TOOLSET)) $(GYP_LDFLAGS) $(LDFLAGS.$(TOOLSET)) -o "$@" $(LD_INPUTS) $(LIBS)

# TODO(thakis): Find out and document the difference between shared_library and
# loadable_module on mac.
quiet_cmd_solink = SOLINK($(TOOLSET)) $@
cmd_solink = $(LINK.$(TOOLSET)) -shared $(GYP_LDFLAGS) $(LDFLAGS.$(TOOLSET)) -o "$@" $(LD_INPUTS) $(LIBS)

# TODO(thakis): The solink_module rule is likely wrong. Xcode seems to pass
# -bundle -single_module here (for osmesa.so).
quiet_cmd_solink_module = SOLINK_MODULE($(TOOLSET)) $@
cmd_solink_module = $(LINK.$(TOOLSET)) -shared $(GYP_LDFLAGS) $(LDFLAGS.$(TOOLSET)) -o $@ $(filter-out FORCE_DO_CMD, $^) $(LIBS)
"""

LINK_COMMANDS_ANDROID = """\
quiet_cmd_alink = AR($(TOOLSET)) $@
cmd_alink = rm -f $@ && $(AR.$(TOOLSET)) crs $@ $(filter %.o,$^)

quiet_cmd_alink_thin = AR($(TOOLSET)) $@
cmd_alink_thin = rm -f $@ && $(AR.$(TOOLSET)) crsT $@ $(filter %.o,$^)

# Due to circular dependencies between libraries :(, we wrap the
# special "figure out circular dependencies" flags around the entire
# input list during linking.
quiet_cmd_link = LINK($(TOOLSET)) $@
quiet_cmd_link_host = LINK($(TOOLSET)) $@
cmd_link = $(LINK.$(TOOLSET)) $(GYP_LDFLAGS) $(LDFLAGS.$(TOOLSET)) -o $@ -Wl,--start-group $(LD_INPUTS) -Wl,--end-group $(LIBS)
cmd_link_host = $(LINK.$(TOOLSET)) $(GYP_LDFLAGS) $(LDFLAGS.$(TOOLSET)) -o $@ $(LD_INPUTS) $(LIBS)

# Other shared-object link notes:
# - Set SONAME to the library filename so our binaries don't reference
# the local, absolute paths used on the link command-line.
quiet_cmd_solink = SOLINK($(TOOLSET)) $@
cmd_solink = $(LINK.$(TOOLSET)) -shared $(GYP_LDFLAGS) $(LDFLAGS.$(TOOLSET)) -Wl,-soname=$(@F) -o $@ -Wl,--whole-archive $(LD_INPUTS) -Wl,--no-whole-archive $(LIBS)

quiet_cmd_solink_module = SOLINK_MODULE($(TOOLSET)) $@
cmd_solink_module = $(LINK.$(TOOLSET)) -shared $(GYP_LDFLAGS) $(LDFLAGS.$(TOOLSET)) -Wl,-soname=$(@F) -o $@ -Wl,--start-group $(filter-out FORCE_DO_CMD, $^) -Wl,--end-group $(LIBS)
quiet_cmd_solink_module_host = SOLINK_MODULE($(TOOLSET)) $@
cmd_solink_module_host = $(LINK.$(TOOLSET)) -shared $(GYP_LDFLAGS) $(LDFLAGS.$(TOOLSET)) -Wl,-soname=$(@F) -o $@ $(filter-out FORCE_DO_CMD, $^) $(LIBS)
"""


# Header of toplevel Makefile.
# This should go into the build tree, but it's easier to keep it here for now.
SHARED_HEADER = ("""\
# We borrow heavily from the kernel build setup, though we are simpler since
# we don't have Kconfig tweaking settings on us.

# The implicit make rules have it looking for RCS files, among other things.
# We instead explicitly write all the rules we care about.
# It's even quicker (saves ~200ms) to pass -r on the command line.
MAKEFLAGS=-r

# The source directory tree.
srcdir := %(srcdir)s
abs_srcdir := $(abspath $(srcdir))

# The name of the builddir.
builddir_name ?= %(builddir)s

# The V=1 flag on command line makes us verbosely print command lines.
ifdef V
  quiet=
else
  quiet=quiet_
endif

# Specify BUILDTYPE=Release on the command line for a release build.
BUILDTYPE ?= %(default_configuration)s

# Directory all our build output goes into.
# Note that this must be two directories beneath src/ for unit tests to pass,
# as they reach into the src/ directory for data with relative paths.
builddir ?= $(builddir_name)/$(BUILDTYPE)
abs_builddir := $(abspath $(builddir))
depsdir := $(builddir)/.deps

# Object output directory.
obj := $(builddir)/obj
abs_obj := $(abspath $(obj))

# We build up a list of every single one of the targets so we can slurp in the
# generated dependency rule Makefiles in one pass.
all_deps :=

%(make_global_settings)s

# C++ apps need to be linked with g++.
#
# Note: flock is used to seralize linking. Linking is a memory-intensive
# process so running parallel links can often lead to thrashing.  To disable
# the serialization, override LINK via an envrionment variable as follows:
#
#   export LINK=g++
#
# This will allow make to invoke N linker processes as specified in -jN.
LINK ?= %(flock)s $(builddir)/linker.lock $(CXX)

CC.target ?= %(CC.target)s
CFLAGS.target ?= $(CFLAGS)
CXX.target ?= %(CXX.target)s
CXXFLAGS.target ?= $(CXXFLAGS)
LINK.target ?= %(LINK.target)s
LDFLAGS.target ?= $(LDFLAGS)
AR.target ?= $(AR)

# TODO(evan): move all cross-compilation logic to gyp-time so we don't need
# to replicate this environment fallback in make as well.
CC.host ?= %(CC.host)s
CFLAGS.host ?=
CXX.host ?= %(CXX.host)s
CXXFLAGS.host ?=
LINK.host ?= %(LINK.host)s
LDFLAGS.host ?=
AR.host ?= %(AR.host)s

# Define a dir function that can handle spaces.
# http://www.gnu.org/software/make/manual/make.html#Syntax-of-Functions
# "leading spaces cannot appear in the text of the first argument as written.
# These characters can be put into the argument value by variable substitution."
empty :=
space := $(empty) $(empty)

# http://stackoverflow.com/questions/1189781/using-make-dir-or-notdir-on-a-path-with-spaces
replace_spaces = $(subst $(space),""" + SPACE_REPLACEMENT + """,$1)
unreplace_spaces = $(subst """ + SPACE_REPLACEMENT + """,$(space),$1)
dirx = $(call unreplace_spaces,$(dir $(call replace_spaces,$1)))

# Flags to make gcc output dependency info.  Note that you need to be
# careful here to use the flags that ccache and distcc can understand.
# We write to a dep file on the side first and then rename at the end
# so we can't end up with a broken dep file.
depfile = $(depsdir)/$(call replace_spaces,$@).d
DEPFLAGS = -MMD -MF $(depfile).raw

# We have to fixup the deps output in a few ways.
# (1) the file output should mention the proper .o file.
# ccache or distcc lose the path to the target, so we convert a rule of
# the form:
#   foobar.o: DEP1 DEP2
# into
#   path/to/foobar.o: DEP1 DEP2
# (2) we want missing files not to cause us to fail to build.
# We want to rewrite
#   foobar.o: DEP1 DEP2 \\
#               DEP3
# to
#   DEP1:
#   DEP2:
#   DEP3:
# so if the files are missing, they're just considered phony rules.
# We have to do some pretty insane escaping to get those backslashes
# and dollar signs past make, the shell, and sed at the same time.
# Doesn't work with spaces, but that's fine: .d files have spaces in
# their names replaced with other characters."""
r"""
define fixup_dep
# The depfile may not exist if the input file didn't have any #includes.
touch $(depfile).raw
# Fixup path as in (1).
sed -e "s|^$(notdir $@)|$@|" $(depfile).raw >> $(depfile)
# Add extra rules as in (2).
# We remove slashes and replace spaces with new lines;
# remove blank lines;
# delete the first line and append a colon to the remaining lines.
sed -e 's|\\||' -e 'y| |\n|' $(depfile).raw |\
  grep -v '^$$'                             |\
  sed -e 1d -e 's|$$|:|'                     \
    >> $(depfile)
rm $(depfile).raw
endef
"""
"""
# Command definitions:
# - cmd_foo is the actual command to run;
# - quiet_cmd_foo is the brief-output summary of the command.

quiet_cmd_cc = CC($(TOOLSET)) $@
cmd_cc = $(CC.$(TOOLSET)) $(GYP_CFLAGS) $(DEPFLAGS) $(CFLAGS.$(TOOLSET)) -c -o $@ $<

quiet_cmd_cxx = CXX($(TOOLSET)) $@
cmd_cxx = $(CXX.$(TOOLSET)) $(GYP_CXXFLAGS) $(DEPFLAGS) $(CXXFLAGS.$(TOOLSET)) -c -o $@ $<
%(extra_commands)s
quiet_cmd_touch = TOUCH $@
cmd_touch = touch $@

quiet_cmd_copy = COPY $@
# send stderr to /dev/null to ignore messages when linking directories.
cmd_copy = ln -f "$<" "$@" 2>/dev/null || (rm -rf "$@" && cp -af "$<" "$@")

%(link_commands)s
"""

r"""
# Define an escape_quotes function to escape single quotes.
# This allows us to handle quotes properly as long as we always use
# use single quotes and escape_quotes.
escape_quotes = $(subst ','\'',$(1))
# This comment is here just to include a ' to unconfuse syntax highlighting.
# Define an escape_vars function to escape '$' variable syntax.
# This allows us to read/write command lines with shell variables (e.g.
# $LD_LIBRARY_PATH), without triggering make substitution.
escape_vars = $(subst $$,$$$$,$(1))
# Helper that expands to a shell command to echo a string exactly as it is in
# make. This uses printf instead of echo because printf's behaviour with respect
# to escape sequences is more portable than echo's across different shells
# (e.g., dash, bash).
exact_echo = printf '%%s\n' '$(call escape_quotes,$(1))'
"""
"""
# Helper to compare the command we're about to run against the command
# we logged the last time we ran the command.  Produces an empty
# string (false) when the commands match.
# Tricky point: Make has no string-equality test function.
# The kernel uses the following, but it seems like it would have false
# positives, where one string reordered its arguments.
#   arg_check = $(strip $(filter-out $(cmd_$(1)), $(cmd_$@)) \\
#                       $(filter-out $(cmd_$@), $(cmd_$(1))))
# We instead substitute each for the empty string into the other, and
# say they're equal if both substitutions produce the empty string.
# .d files contain """ + SPACE_REPLACEMENT + \
                   """ instead of spaces, take that into account.
command_changed = $(or $(subst $(cmd_$(1)),,$(cmd_$(call replace_spaces,$@))),\\
                       $(subst $(cmd_$(call replace_spaces,$@)),,$(cmd_$(1))))

# Helper that is non-empty when a prerequisite changes.
# Normally make does this implicitly, but we force rules to always run
# so we can check their command lines.
#   $? -- new prerequisites
#   $| -- order-only dependencies
prereq_changed = $(filter-out FORCE_DO_CMD,$(filter-out $|,$?))

# Helper that executes all postbuilds, and deletes the output file when done
# if any of the postbuilds failed.
define do_postbuilds
  @E=0;\\
  for p in $(POSTBUILDS); do\\
    eval $$p;\\
    F=$$?;\\
    if [ $$F -ne 0 ]; then\\
      E=$$F;\\
    fi;\\
  done;\\
  if [ $$E -ne 0 ]; then\\
    rm -rf "$@";\\
    exit $$E;\\
  fi
endef

# do_cmd: run a command via the above cmd_foo names, if necessary.
# Should always run for a given target to handle command-line changes.
# Second argument, if non-zero, makes it do asm/C/C++ dependency munging.
# Third argument, if non-zero, makes it do POSTBUILDS processing.
# Note: We intentionally do NOT call dirx for depfile, since it contains """ + \
                                                     SPACE_REPLACEMENT + """ for
# spaces already and dirx strips the """ + SPACE_REPLACEMENT + \
                                     """ characters.
define do_cmd
$(if $(or $(command_changed),$(prereq_changed)),
  @$(call exact_echo,  $($(quiet)cmd_$(1)))
  @mkdir -p "$(call dirx,$@)" "$(dir $(depfile))"
  $(if $(findstring flock,$(word %(flock_index)d,$(cmd_$1))),
    @$(cmd_$(1))
    @echo "  $(quiet_cmd_$(1)): Finished",
    @$(cmd_$(1))
  )
  @$(call exact_echo,$(call escape_vars,cmd_$(call replace_spaces,$@) := $(cmd_$(1)))) > $(depfile)
  @$(if $(2),$(fixup_dep))
  $(if $(and $(3), $(POSTBUILDS)),
    $(call do_postbuilds)
  )
)
endef

# Declare the "%(default_target)s" target first so it is the default,
# even though we don't have the deps yet.
.PHONY: %(default_target)s
%(default_target)s:

# make looks for ways to re-generate included makefiles, but in our case, we
# don't have a direct way. Explicitly telling make that it has nothing to do
# for them makes it go faster.
%%.d: ;

# Use FORCE_DO_CMD to force a target to run.  Should be coupled with
# do_cmd.
.PHONY: FORCE_DO_CMD
FORCE_DO_CMD:

""")

SHARED_HEADER_MAC_COMMANDS = """
quiet_cmd_objc = CXX($(TOOLSET)) $@
cmd_objc = $(CC.$(TOOLSET)) $(GYP_OBJCFLAGS) $(DEPFLAGS) -c -o $@ $<

quiet_cmd_objcxx = CXX($(TOOLSET)) $@
cmd_objcxx = $(CXX.$(TOOLSET)) $(GYP_OBJCXXFLAGS) $(DEPFLAGS) -c -o $@ $<

# Commands for precompiled header files.
quiet_cmd_pch_c = CXX($(TOOLSET)) $@
cmd_pch_c = $(CC.$(TOOLSET)) $(GYP_PCH_CFLAGS) $(DEPFLAGS) $(CXXFLAGS.$(TOOLSET)) -c -o $@ $<
quiet_cmd_pch_cc = CXX($(TOOLSET)) $@
cmd_pch_cc = $(CC.$(TOOLSET)) $(GYP_PCH_CXXFLAGS) $(DEPFLAGS) $(CXXFLAGS.$(TOOLSET)) -c -o $@ $<
quiet_cmd_pch_m = CXX($(TOOLSET)) $@
cmd_pch_m = $(CC.$(TOOLSET)) $(GYP_PCH_OBJCFLAGS) $(DEPFLAGS) -c -o $@ $<
quiet_cmd_pch_mm = CXX($(TOOLSET)) $@
cmd_pch_mm = $(CC.$(TOOLSET)) $(GYP_PCH_OBJCXXFLAGS) $(DEPFLAGS) -c -o $@ $<

# gyp-mac-tool is written next to the root Makefile by gyp.
# Use $(4) for the command, since $(2) and $(3) are used as flag by do_cmd
# already.
quiet_cmd_mac_tool = MACTOOL $(4) $<
cmd_mac_tool = ./gyp-mac-tool $(4) $< "$@"

quiet_cmd_mac_package_framework = PACKAGE FRAMEWORK $@
cmd_mac_package_framework = ./gyp-mac-tool package-framework "$@" $(4)

quiet_cmd_infoplist = INFOPLIST $@
cmd_infoplist = $(CC.$(TOOLSET)) -E -P -Wno-trigraphs -x c $(INFOPLIST_DEFINES) "$<" -o "$@"
"""

SHARED_HEADER_SUN_COMMANDS = """
# gyp-sun-tool is written next to the root Makefile by gyp.
# Use $(4) for the command, since $(2) and $(3) are used as flag by do_cmd
# already.
quiet_cmd_sun_tool = SUNTOOL $(4) $<
cmd_sun_tool = ./gyp-sun-tool $(4) $< "$@"
"""


def WriteRootHeaderSuffixRules(writer):
  extensions = sorted(COMPILABLE_EXTENSIONS.keys(), key=str.lower)

  writer.write('# Suffix rules, putting all outputs into $(obj).\n')
  for ext in extensions:
    writer.write('$(obj).$(TOOLSET)/%%.o: $(srcdir)/%%%s FORCE_DO_CMD\n' % ext)
    writer.write('\t@$(call do_cmd,%s,1)\n' % COMPILABLE_EXTENSIONS[ext])

  writer.write('\n# Try building from generated source, too.\n')
  for ext in extensions:
    writer.write(
        '$(obj).$(TOOLSET)/%%.o: $(obj).$(TOOLSET)/%%%s FORCE_DO_CMD\n' % ext)
    writer.write('\t@$(call do_cmd,%s,1)\n' % COMPILABLE_EXTENSIONS[ext])
  writer.write('\n')
  for ext in extensions:
    writer.write('$(obj).$(TOOLSET)/%%.o: $(obj)/%%%s FORCE_DO_CMD\n' % ext)
    writer.write('\t@$(call do_cmd,%s,1)\n' % COMPILABLE_EXTENSIONS[ext])
  writer.write('\n')


SHARED_HEADER_SUFFIX_RULES_COMMENT1 = ("""\
# Suffix rules, putting all outputs into $(obj).
""")


SHARED_HEADER_SUFFIX_RULES_COMMENT2 = ("""\
# Try building from generated source, too.
""")


SHARED_FOOTER = """\
# "all" is a concatenation of the "all" targets from all the included
# sub-makefiles. This is just here to clarify.
all:

# Add in dependency-tracking rules.  $(all_deps) is the list of every single
# target in our tree. Only consider the ones with .d (dependency) info:
d_files := $(wildcard $(foreach f,$(all_deps),$(depsdir)/$(f).d))
ifneq ($(d_files),)
  include $(d_files)
endif
"""

header = """\
# This file is generated by gyp; do not edit.

"""

# Maps every compilable file extension to the do_cmd that compiles it.
COMPILABLE_EXTENSIONS = {
  '.c': 'cc',
  '.cc': 'cxx',
  '.cpp': 'cxx',
  '.cxx': 'cxx',
  '.s': 'cc',
  '.S': 'cc',
}

def Compilable(filename):
  """Return true if the file is compilable (should be in OBJS)."""
  for res in (filename.endswith(e) for e in COMPILABLE_EXTENSIONS):
    if res:
      return True
  return False


def Linkable(filename):
  """Return true if the file is linkable (should be on the link line)."""
  return filename.endswith('.o')


def Target(filename):
  """Translate a compilable filename to its .o target."""
  return os.path.splitext(filename)[0] + '.o'


def EscapeShellArgument(s):
  """Quotes an argument so that it will be interpreted literally by a POSIX
     shell. Taken from
     http://stackoverflow.com/questions/35817/whats-the-best-way-to-escape-ossystem-calls-in-python
     """
  return "'" + s.replace("'", "'\\''") + "'"


def EscapeMakeVariableExpansion(s):
  """Make has its own variable expansion syntax using $. We must escape it for
     string to be interpreted literally."""
  return s.replace('$', '$$')


def EscapeCppDefine(s):
  """Escapes a CPP define so that it will reach the compiler unaltered."""
  s = EscapeShellArgument(s)
  s = EscapeMakeVariableExpansion(s)
  # '#' characters must be escaped even embedded in a string, else Make will
  # treat it as the start of a comment.
  return s.replace('#', r'\#')


def QuoteIfNecessary(string):
  """TODO: Should this ideally be replaced with one or more of the above
     functions?"""
  if '"' in string:
    string = '"' + string.replace('"', '\\"') + '"'
  return string


def StringToMakefileVariable(string):
  """Convert a string to a value that is acceptable as a make variable name."""
  return re.sub('[^a-zA-Z0-9_]', '_', string)


srcdir_prefix = ''
def Sourceify(path):
  """Convert a path to its source directory form."""
  if '$(' in path:
    return path
  if os.path.isabs(path):
    return path
  return srcdir_prefix + path


def QuoteSpaces(s, quote=r'\ '):
  return s.replace(' ', quote)


def InvertRelativePath(path):
  """Given a relative path like foo/bar, return the inverse relative path:
  the path from the relative path back to the origin dir.

  E.g. os.path.normpath(os.path.join(path, InvertRelativePath(path)))
  should always produce the empty string."""

  if not path:
    return path
  # Only need to handle relative paths into subdirectories for now.
  assert '..' not in path, path
  depth = len(path.split(os.path.sep))
  return os.path.sep.join(['..'] * depth)


# Map from qualified target to path to output.
target_outputs = {}
# Map from qualified target to any linkable output.  A subset
# of target_outputs.  E.g. when mybinary depends on liba, we want to
# include liba in the linker line; when otherbinary depends on
# mybinary, we just want to build mybinary first.
target_link_deps = {}


class MakefileWriter:
  """MakefileWriter packages up the writing of one target-specific foobar.mk.

  Its only real entry point is Write(), and is mostly used for namespacing.
  """

  def __init__(self, generator_flags, flavor):
    self.generator_flags = generator_flags
    self.flavor = flavor

    self.suffix_rules_srcdir = {}
    self.suffix_rules_objdir1 = {}
    self.suffix_rules_objdir2 = {}

    # Generate suffix rules for all compilable extensions.
    for ext in COMPILABLE_EXTENSIONS.keys():
      # Suffix rules for source folder.
      self.suffix_rules_srcdir.update({ext: ("""\
$(obj).$(TOOLSET)/$(TARGET)/%%.o: $(srcdir)/%%%s FORCE_DO_CMD
	@$(call do_cmd,%s,1)
""" % (ext, COMPILABLE_EXTENSIONS[ext]))})

      # Suffix rules for generated source files.
      self.suffix_rules_objdir1.update({ext: ("""\
$(obj).$(TOOLSET)/$(TARGET)/%%.o: $(obj).$(TOOLSET)/%%%s FORCE_DO_CMD
	@$(call do_cmd,%s,1)
""" % (ext, COMPILABLE_EXTENSIONS[ext]))})
      self.suffix_rules_objdir2.update({ext: ("""\
$(obj).$(TOOLSET)/$(TARGET)/%%.o: $(obj)/%%%s FORCE_DO_CMD
	@$(call do_cmd,%s,1)
""" % (ext, COMPILABLE_EXTENSIONS[ext]))})


  def Write(self, qualified_target, base_path, output_filename, spec, configs,
            part_of_all):
    """The main entry point: writes a .mk file for a single target.

    Arguments:
      qualified_target: target we're generating
      base_path: path relative to source root we're building in, used to resolve
                 target-relative paths
      output_filename: output .mk file name to write
      spec, configs: gyp info
      part_of_all: flag indicating this target is part of 'all'
    """
    ensure_directory_exists(output_filename)

    self.fp = open(output_filename, 'w')

    self.fp.write(header)

    self.qualified_target = qualified_target
    self.path = base_path
    self.target = spec['target_name']
    self.type = spec['type']
    self.toolset = spec['toolset']

    self.is_mac_bundle = gyp.xcode_emulation.IsMacBundle(self.flavor, spec)
    if self.flavor == 'mac':
      self.xcode_settings = gyp.xcode_emulation.XcodeSettings(spec)
    else:
      self.xcode_settings = None

    deps, link_deps = self.ComputeDeps(spec)

    # Some of the generation below can add extra output, sources, or
    # link dependencies.  All of the out params of the functions that
    # follow use names like extra_foo.
    extra_outputs = []
    extra_sources = []
    extra_link_deps = []
    extra_mac_bundle_resources = []
    mac_bundle_deps = []

    if self.is_mac_bundle:
      self.output = self.ComputeMacBundleOutput(spec)
      self.output_binary = self.ComputeMacBundleBinaryOutput(spec)
    else:
      self.output = self.output_binary = self.ComputeOutput(spec)

    self.is_standalone_static_library = bool(
        spec.get('standalone_static_library', 0))
    self._INSTALLABLE_TARGETS = ('executable', 'loadable_module',
                                 'shared_library')
    if (self.is_standalone_static_library or
        self.type in self._INSTALLABLE_TARGETS):
      self.alias = os.path.basename(self.output)
      install_path = self._InstallableTargetInstallPath()
    else:
      self.alias = self.output
      install_path = self.output

    self.WriteLn("TOOLSET := " + self.toolset)
    self.WriteLn("TARGET := " + self.target)

    # Actions must come first, since they can generate more OBJs for use below.
    if 'actions' in spec:
      self.WriteActions(spec['actions'], extra_sources, extra_outputs,
                        extra_mac_bundle_resources, part_of_all)

    # Rules must be early like actions.
    if 'rules' in spec:
      self.WriteRules(spec['rules'], extra_sources, extra_outputs,
                      extra_mac_bundle_resources, part_of_all)

    if 'copies' in spec:
      self.WriteCopies(spec['copies'], extra_outputs, part_of_all)

    # Bundle resources.
    if self.is_mac_bundle:
      all_mac_bundle_resources = (
          spec.get('mac_bundle_resources', []) + extra_mac_bundle_resources)
      self.WriteMacBundleResources(all_mac_bundle_resources, mac_bundle_deps)
      self.WriteMacInfoPlist(mac_bundle_deps)

    # Sources.
    all_sources = spec.get('sources', []) + extra_sources
    if all_sources:
      self.WriteSources(
          configs, deps, all_sources, extra_outputs,
          extra_link_deps, part_of_all,
          gyp.xcode_emulation.MacPrefixHeader(
              self.xcode_settings, lambda p: Sourceify(self.Absolutify(p)),
              self.Pchify))
      sources = filter(Compilable, all_sources)
      if sources:
        self.WriteLn(SHARED_HEADER_SUFFIX_RULES_COMMENT1)
        extensions = set([os.path.splitext(s)[1] for s in sources])
        for ext in extensions:
          if ext in self.suffix_rules_srcdir:
            self.WriteLn(self.suffix_rules_srcdir[ext])
        self.WriteLn(SHARED_HEADER_SUFFIX_RULES_COMMENT2)
        for ext in extensions:
          if ext in self.suffix_rules_objdir1:
            self.WriteLn(self.suffix_rules_objdir1[ext])
        for ext in extensions:
          if ext in self.suffix_rules_objdir2:
            self.WriteLn(self.suffix_rules_objdir2[ext])
        self.WriteLn('# End of this set of suffix rules')

        # Add dependency from bundle to bundle binary.
        if self.is_mac_bundle:
          mac_bundle_deps.append(self.output_binary)

    self.WriteTarget(spec, configs, deps, extra_link_deps + link_deps,
                     mac_bundle_deps, extra_outputs, part_of_all)

    # Update global list of target outputs, used in dependency tracking.
    target_outputs[qualified_target] = install_path

    # Update global list of link dependencies.
    if self.type in ('static_library', 'shared_library'):
      target_link_deps[qualified_target] = self.output_binary

    # Currently any versions have the same effect, but in future the behavior
    # could be different.
    if self.generator_flags.get('android_ndk_version', None):
      self.WriteAndroidNdkModuleRule(self.target, all_sources, link_deps)

    self.fp.close()


  def WriteSubMake(self, output_filename, makefile_path, targets, build_dir):
    """Write a "sub-project" Makefile.

    This is a small, wrapper Makefile that calls the top-level Makefile to build
    the targets from a single gyp file (i.e. a sub-project).

    Arguments:
      output_filename: sub-project Makefile name to write
      makefile_path: path to the top-level Makefile
      targets: list of "all" targets for this sub-project
      build_dir: build output directory, relative to the sub-project
    """
    ensure_directory_exists(output_filename)
    self.fp = open(output_filename, 'w')
    self.fp.write(header)
    # For consistency with other builders, put sub-project build output in the
    # sub-project dir (see test/subdirectory/gyptest-subdir-all.py).
    self.WriteLn('export builddir_name ?= %s' %
                 os.path.join(os.path.dirname(output_filename), build_dir))
    self.WriteLn('.PHONY: all')
    self.WriteLn('all:')
    if makefile_path:
      makefile_path = ' -C ' + makefile_path
    self.WriteLn('\t$(MAKE)%s %s' % (makefile_path, ' '.join(targets)))
    self.fp.close()


  def WriteActions(self, actions, extra_sources, extra_outputs,
                   extra_mac_bundle_resources, part_of_all):
    """Write Makefile code for any 'actions' from the gyp input.

    extra_sources: a list that will be filled in with newly generated source
                   files, if any
    extra_outputs: a list that will be filled in with any outputs of these
                   actions (used to make other pieces dependent on these
                   actions)
    part_of_all: flag indicating this target is part of 'all'
    """
    env = self.GetSortedXcodeEnv()
    for action in actions:
      name = StringToMakefileVariable('%s_%s' % (self.qualified_target,
                                                 action['action_name']))
      self.WriteLn('### Rules for action "%s":' % action['action_name'])
      inputs = action['inputs']
      outputs = action['outputs']

      # Build up a list of outputs.
      # Collect the output dirs we'll need.
      dirs = set()
      for out in outputs:
        dir = os.path.split(out)[0]
        if dir:
          dirs.add(dir)
      if int(action.get('process_outputs_as_sources', False)):
        extra_sources += outputs
      if int(action.get('process_outputs_as_mac_bundle_resources', False)):
        extra_mac_bundle_resources += outputs

      # Write the actual command.
      action_commands = action['action']
      if self.flavor == 'mac':
        action_commands = [gyp.xcode_emulation.ExpandEnvVars(command, env)
                          for command in action_commands]
      command = gyp.common.EncodePOSIXShellList(action_commands)
      if 'message' in action:
        self.WriteLn('quiet_cmd_%s = ACTION %s $@' % (name, action['message']))
      else:
        self.WriteLn('quiet_cmd_%s = ACTION %s $@' % (name, name))
      if len(dirs) > 0:
        command = 'mkdir -p %s' % ' '.join(dirs) + '; ' + command

      cd_action = 'cd %s; ' % Sourceify(self.path or '.')

      # command and cd_action get written to a toplevel variable called
      # cmd_foo. Toplevel variables can't handle things that change per
      # makefile like $(TARGET), so hardcode the target.
      command = command.replace('$(TARGET)', self.target)
      cd_action = cd_action.replace('$(TARGET)', self.target)

      # Set LD_LIBRARY_PATH in case the action runs an executable from this
      # build which links to shared libs from this build.
      # actions run on the host, so they should in theory only use host
      # libraries, but until everything is made cross-compile safe, also use
      # target libraries.
      # TODO(piman): when everything is cross-compile safe, remove lib.target
      self.WriteLn('cmd_%s = LD_LIBRARY_PATH=$(builddir)/lib.host:'
                   '$(builddir)/lib.target:$$LD_LIBRARY_PATH; '
                   'export LD_LIBRARY_PATH; '
                   '%s%s'
                   % (name, cd_action, command))
      self.WriteLn()
      outputs = map(self.Absolutify, outputs)
      # The makefile rules are all relative to the top dir, but the gyp actions
      # are defined relative to their containing dir.  This replaces the obj
      # variable for the action rule with an absolute version so that the output
      # goes in the right place.
      # Only write the 'obj' and 'builddir' rules for the "primary" output (:1);
      # it's superfluous for the "extra outputs", and this avoids accidentally
      # writing duplicate dummy rules for those outputs.
      # Same for environment.
      self.WriteLn("%s: obj := $(abs_obj)" % QuoteSpaces(outputs[0]))
      self.WriteLn("%s: builddir := $(abs_builddir)" % QuoteSpaces(outputs[0]))
      self.WriteSortedXcodeEnv(outputs[0], self.GetSortedXcodeEnv())

      for input in inputs:
        assert ' ' not in input, (
            "Spaces in action input filenames not supported (%s)"  % input)
      for output in outputs:
        assert ' ' not in output, (
            "Spaces in action output filenames not supported (%s)"  % output)

      # See the comment in WriteCopies about expanding env vars.
      outputs = [gyp.xcode_emulation.ExpandEnvVars(o, env) for o in outputs]
      inputs = [gyp.xcode_emulation.ExpandEnvVars(i, env) for i in inputs]

      self.WriteDoCmd(outputs, map(Sourceify, map(self.Absolutify, inputs)),
                      part_of_all=part_of_all, command=name)

      # Stuff the outputs in a variable so we can refer to them later.
      outputs_variable = 'action_%s_outputs' % name
      self.WriteLn('%s := %s' % (outputs_variable, ' '.join(outputs)))
      extra_outputs.append('$(%s)' % outputs_variable)
      self.WriteLn()

    self.WriteLn()


  def WriteRules(self, rules, extra_sources, extra_outputs,
                 extra_mac_bundle_resources, part_of_all):
    """Write Makefile code for any 'rules' from the gyp input.

    extra_sources: a list that will be filled in with newly generated source
                   files, if any
    extra_outputs: a list that will be filled in with any outputs of these
                   rules (used to make other pieces dependent on these rules)
    part_of_all: flag indicating this target is part of 'all'
    """
    env = self.GetSortedXcodeEnv()
    for rule in rules:
      name = StringToMakefileVariable('%s_%s' % (self.qualified_target,
                                                 rule['rule_name']))
      count = 0
      self.WriteLn('### Generated for rule %s:' % name)

      all_outputs = []

      for rule_source in rule.get('rule_sources', []):
        dirs = set()
        (rule_source_dirname, rule_source_basename) = os.path.split(rule_source)
        (rule_source_root, rule_source_ext) = \
            os.path.splitext(rule_source_basename)

        outputs = [self.ExpandInputRoot(out, rule_source_root,
                                        rule_source_dirname)
                   for out in rule['outputs']]

        for out in outputs:
          dir = os.path.dirname(out)
          if dir:
            dirs.add(dir)
        if int(rule.get('process_outputs_as_sources', False)):
          extra_sources += outputs
        if int(rule.get('process_outputs_as_mac_bundle_resources', False)):
          extra_mac_bundle_resources += outputs
        inputs = map(Sourceify, map(self.Absolutify, [rule_source] +
                                    rule.get('inputs', [])))
        actions = ['$(call do_cmd,%s_%d)' % (name, count)]

        if name == 'resources_grit':
          # HACK: This is ugly.  Grit intentionally doesn't touch the
          # timestamp of its output file when the file doesn't change,
          # which is fine in hash-based dependency systems like scons
          # and forge, but not kosher in the make world.  After some
          # discussion, hacking around it here seems like the least
          # amount of pain.
          actions += ['@touch --no-create $@']

        # See the comment in WriteCopies about expanding env vars.
        outputs = [gyp.xcode_emulation.ExpandEnvVars(o, env) for o in outputs]
        inputs = [gyp.xcode_emulation.ExpandEnvVars(i, env) for i in inputs]

        outputs = map(self.Absolutify, outputs)
        all_outputs += outputs
        # Only write the 'obj' and 'builddir' rules for the "primary" output
        # (:1); it's superfluous for the "extra outputs", and this avoids
        # accidentally writing duplicate dummy rules for those outputs.
        self.WriteLn('%s: obj := $(abs_obj)' % outputs[0])
        self.WriteLn('%s: builddir := $(abs_builddir)' % outputs[0])
        self.WriteMakeRule(outputs, inputs + ['FORCE_DO_CMD'], actions)
        for output in outputs:
          assert ' ' not in output, (
              "Spaces in rule filenames not yet supported (%s)"  % output)
        self.WriteLn('all_deps += %s' % ' '.join(outputs))

        action = [self.ExpandInputRoot(ac, rule_source_root,
                                       rule_source_dirname)
                  for ac in rule['action']]
        mkdirs = ''
        if len(dirs) > 0:
          mkdirs = 'mkdir -p %s; ' % ' '.join(dirs)
        cd_action = 'cd %s; ' % Sourceify(self.path or '.')

        # action, cd_action, and mkdirs get written to a toplevel variable
        # called cmd_foo. Toplevel variables can't handle things that change
        # per makefile like $(TARGET), so hardcode the target.
        if self.flavor == 'mac':
          action = [gyp.xcode_emulation.ExpandEnvVars(command, env)
                    for command in action]
        action = gyp.common.EncodePOSIXShellList(action)
        action = action.replace('$(TARGET)', self.target)
        cd_action = cd_action.replace('$(TARGET)', self.target)
        mkdirs = mkdirs.replace('$(TARGET)', self.target)

        # Set LD_LIBRARY_PATH in case the rule runs an executable from this
        # build which links to shared libs from this build.
        # rules run on the host, so they should in theory only use host
        # libraries, but until everything is made cross-compile safe, also use
        # target libraries.
        # TODO(piman): when everything is cross-compile safe, remove lib.target
        self.WriteLn(
            "cmd_%(name)s_%(count)d = LD_LIBRARY_PATH="
              "$(builddir)/lib.host:$(builddir)/lib.target:$$LD_LIBRARY_PATH; "
              "export LD_LIBRARY_PATH; "
              "%(cd_action)s%(mkdirs)s%(action)s" % {
          'action': action,
          'cd_action': cd_action,
          'count': count,
          'mkdirs': mkdirs,
          'name': name,
        })
        self.WriteLn(
            'quiet_cmd_%(name)s_%(count)d = RULE %(name)s_%(count)d $@' % {
          'count': count,
          'name': name,
        })
        self.WriteLn()
        count += 1

      outputs_variable = 'rule_%s_outputs' % name
      self.WriteList(all_outputs, outputs_variable)
      extra_outputs.append('$(%s)' % outputs_variable)

      self.WriteLn('### Finished generating for rule: %s' % name)
      self.WriteLn()
    self.WriteLn('### Finished generating for all rules')
    self.WriteLn('')


  def WriteCopies(self, copies, extra_outputs, part_of_all):
    """Write Makefile code for any 'copies' from the gyp input.

    extra_outputs: a list that will be filled in with any outputs of this action
                   (used to make other pieces dependent on this action)
    part_of_all: flag indicating this target is part of 'all'
    """
    self.WriteLn('### Generated for copy rule.')

    variable = StringToMakefileVariable(self.qualified_target + '_copies')
    outputs = []
    for copy in copies:
      for path in copy['files']:
        # Absolutify() may call normpath, and will strip trailing slashes.
        path = Sourceify(self.Absolutify(path))
        filename = os.path.split(path)[1]
        output = Sourceify(self.Absolutify(os.path.join(copy['destination'],
                                                        filename)))

        # If the output path has variables in it, which happens in practice for
        # 'copies', writing the environment as target-local doesn't work,
        # because the variables are already needed for the target name.
        # Copying the environment variables into global make variables doesn't
        # work either, because then the .d files will potentially contain spaces
        # after variable expansion, and .d file handling cannot handle spaces.
        # As a workaround, manually expand variables at gyp time. Since 'copies'
        # can't run scripts, there's no need to write the env then.
        # WriteDoCmd() will escape spaces for .d files.
        env = self.GetSortedXcodeEnv()
        output = gyp.xcode_emulation.ExpandEnvVars(output, env)
        path = gyp.xcode_emulation.ExpandEnvVars(path, env)
        self.WriteDoCmd([output], [path], 'copy', part_of_all)
        outputs.append(output)
    self.WriteLn('%s = %s' % (variable, ' '.join(map(QuoteSpaces, outputs))))
    extra_outputs.append('$(%s)' % variable)
    self.WriteLn()


  def WriteMacBundleResources(self, resources, bundle_deps):
    """Writes Makefile code for 'mac_bundle_resources'."""
    self.WriteLn('### Generated for mac_bundle_resources')

    for output, res in gyp.xcode_emulation.GetMacBundleResources(
        generator_default_variables['PRODUCT_DIR'], self.xcode_settings,
        map(Sourceify, map(self.Absolutify, resources))):
      self.WriteDoCmd([output], [res], 'mac_tool,,,copy-bundle-resource',
                      part_of_all=True)
      bundle_deps.append(output)


  def WriteMacInfoPlist(self, bundle_deps):
    """Write Makefile code for bundle Info.plist files."""
    info_plist, out, defines, extra_env = gyp.xcode_emulation.GetMacInfoPlist(
        generator_default_variables['PRODUCT_DIR'], self.xcode_settings,
        lambda p: Sourceify(self.Absolutify(p)))
    if not info_plist:
      return
    if defines:
      # Create an intermediate file to store preprocessed results.
      intermediate_plist = ('$(obj).$(TOOLSET)/$(TARGET)/' +
          os.path.basename(info_plist))
      self.WriteList(defines, intermediate_plist + ': INFOPLIST_DEFINES', '-D',
          quoter=EscapeCppDefine)
      self.WriteMakeRule([intermediate_plist], [info_plist],
          ['$(call do_cmd,infoplist)',
           # "Convert" the plist so that any weird whitespace changes from the
           # preprocessor do not affect the XML parser in mac_tool.
           '@plutil -convert xml1 $@ $@'])
      info_plist = intermediate_plist
    # plists can contain envvars and substitute them into the file.
    self.WriteSortedXcodeEnv(
        out, self.GetSortedXcodeEnv(additional_settings=extra_env))
    self.WriteDoCmd([out], [info_plist], 'mac_tool,,,copy-info-plist',
                    part_of_all=True)
    bundle_deps.append(out)


  def WriteSources(self, configs, deps, sources,
                   extra_outputs, extra_link_deps,
                   part_of_all, precompiled_header):
    """Write Makefile code for any 'sources' from the gyp input.
    These are source files necessary to build the current target.

    configs, deps, sources: input from gyp.
    extra_outputs: a list of extra outputs this action should be dependent on;
                   used to serialize action/rules before compilation
    extra_link_deps: a list that will be filled in with any outputs of
                     compilation (to be used in link lines)
    part_of_all: flag indicating this target is part of 'all'
    """

    # Write configuration-specific variables for CFLAGS, etc.
    for configname in sorted(configs.keys()):
      config = configs[configname]
      self.WriteList(config.get('defines'), 'DEFS_%s' % configname, prefix='-D',
          quoter=EscapeCppDefine)

      if self.flavor == 'mac':
        cflags = self.xcode_settings.GetCflags(configname)
        cflags_c = self.xcode_settings.GetCflagsC(configname)
        cflags_cc = self.xcode_settings.GetCflagsCC(configname)
        cflags_objc = self.xcode_settings.GetCflagsObjC(configname)
        cflags_objcc = self.xcode_settings.GetCflagsObjCC(configname)
      else:
        cflags = config.get('cflags')
        cflags_c = config.get('cflags_c')
        cflags_cc = config.get('cflags_cc')

      self.WriteLn("# Flags passed to all source files.");
      self.WriteList(cflags, 'CFLAGS_%s' % configname)
      self.WriteLn("# Flags passed to only C files.");
      self.WriteList(cflags_c, 'CFLAGS_C_%s' % configname)
      self.WriteLn("# Flags passed to only C++ files.");
      self.WriteList(cflags_cc, 'CFLAGS_CC_%s' % configname)
      if self.flavor == 'mac':
        self.WriteLn("# Flags passed to only ObjC files.");
        self.WriteList(cflags_objc, 'CFLAGS_OBJC_%s' % configname)
        self.WriteLn("# Flags passed to only ObjC++ files.");
        self.WriteList(cflags_objcc, 'CFLAGS_OBJCC_%s' % configname)
      includes = config.get('include_dirs')
      if includes:
        includes = map(Sourceify, map(self.Absolutify, includes))
      self.WriteList(includes, 'INCS_%s' % configname, prefix='-I')

    compilable = filter(Compilable, sources)
    objs = map(self.Objectify, map(self.Absolutify, map(Target, compilable)))
    self.WriteList(objs, 'OBJS')

    for obj in objs:
      assert ' ' not in obj, (
          "Spaces in object filenames not supported (%s)"  % obj)
    self.WriteLn('# Add to the list of files we specially track '
                 'dependencies for.')
    self.WriteLn('all_deps += $(OBJS)')
    self.WriteLn()

    # Make sure our dependencies are built first.
    if deps:
      self.WriteMakeRule(['$(OBJS)'], deps,
                         comment = 'Make sure our dependencies are built '
                                   'before any of us.',
                         order_only = True)

    # Make sure the actions and rules run first.
    # If they generate any extra headers etc., the per-.o file dep tracking
    # will catch the proper rebuilds, so order only is still ok here.
    if extra_outputs:
      self.WriteMakeRule(['$(OBJS)'], extra_outputs,
                         comment = 'Make sure our actions/rules run '
                                   'before any of us.',
                         order_only = True)

    pchdeps = precompiled_header.GetObjDependencies(compilable, objs )
    if pchdeps:
      self.WriteLn('# Dependencies from obj files to their precompiled headers')
      for source, obj, gch in pchdeps:
        self.WriteLn('%s: %s' % (obj, gch))
      self.WriteLn('# End precompiled header dependencies')

    if objs:
      extra_link_deps.append('$(OBJS)')
      self.WriteLn("""\
# CFLAGS et al overrides must be target-local.
# See "Target-specific Variable Values" in the GNU Make manual.""")
      self.WriteLn("$(OBJS): TOOLSET := $(TOOLSET)")
      self.WriteLn("$(OBJS): GYP_CFLAGS := "
                   "$(DEFS_$(BUILDTYPE)) "
                   "$(INCS_$(BUILDTYPE)) "
                   "%s " % precompiled_header.GetInclude('c') +
                   "$(CFLAGS_$(BUILDTYPE)) "
                   "$(CFLAGS_C_$(BUILDTYPE))")
      self.WriteLn("$(OBJS): GYP_CXXFLAGS := "
                   "$(DEFS_$(BUILDTYPE)) "
                   "$(INCS_$(BUILDTYPE)) "
                   "%s " % precompiled_header.GetInclude('cc') +
                   "$(CFLAGS_$(BUILDTYPE)) "
                   "$(CFLAGS_CC_$(BUILDTYPE))")
      if self.flavor == 'mac':
        self.WriteLn("$(OBJS): GYP_OBJCFLAGS := "
                     "$(DEFS_$(BUILDTYPE)) "
                     "$(INCS_$(BUILDTYPE)) "
                     "%s " % precompiled_header.GetInclude('m') +
                     "$(CFLAGS_$(BUILDTYPE)) "
                     "$(CFLAGS_C_$(BUILDTYPE)) "
                     "$(CFLAGS_OBJC_$(BUILDTYPE))")
        self.WriteLn("$(OBJS): GYP_OBJCXXFLAGS := "
                     "$(DEFS_$(BUILDTYPE)) "
                     "$(INCS_$(BUILDTYPE)) "
                     "%s " % precompiled_header.GetInclude('mm') +
                     "$(CFLAGS_$(BUILDTYPE)) "
                     "$(CFLAGS_CC_$(BUILDTYPE)) "
                     "$(CFLAGS_OBJCC_$(BUILDTYPE))")

    self.WritePchTargets(precompiled_header.GetPchBuildCommands())

    # If there are any object files in our input file list, link them into our
    # output.
    extra_link_deps += filter(Linkable, sources)

    self.WriteLn()

  def WritePchTargets(self, pch_commands):
    """Writes make rules to compile prefix headers."""
    if not pch_commands:
      return

    for gch, lang_flag, lang, input in pch_commands:
      extra_flags = {
        'c': '$(CFLAGS_C_$(BUILDTYPE))',
        'cc': '$(CFLAGS_CC_$(BUILDTYPE))',
        'm': '$(CFLAGS_C_$(BUILDTYPE)) $(CFLAGS_OBJC_$(BUILDTYPE))',
        'mm': '$(CFLAGS_CC_$(BUILDTYPE)) $(CFLAGS_OBJCC_$(BUILDTYPE))',
      }[lang]
      var_name = {
        'c': 'GYP_PCH_CFLAGS',
        'cc': 'GYP_PCH_CXXFLAGS',
        'm': 'GYP_PCH_OBJCFLAGS',
        'mm': 'GYP_PCH_OBJCXXFLAGS',
      }[lang]
      self.WriteLn("%s: %s := %s " % (gch, var_name, lang_flag) +
                   "$(DEFS_$(BUILDTYPE)) "
                   "$(INCS_$(BUILDTYPE)) "
                   "$(CFLAGS_$(BUILDTYPE)) " +
                   extra_flags)

      self.WriteLn('%s: %s FORCE_DO_CMD' % (gch, input))
      self.WriteLn('\t@$(call do_cmd,pch_%s,1)' % lang)
      self.WriteLn('')
      assert ' ' not in gch, (
          "Spaces in gch filenames not supported (%s)"  % gch)
      self.WriteLn('all_deps += %s' % gch)
      self.WriteLn('')


  def ComputeOutputBasename(self, spec):
    """Return the 'output basename' of a gyp spec.

    E.g., the loadable module 'foobar' in directory 'baz' will produce
      'libfoobar.so'
    """
    assert not self.is_mac_bundle

    if self.flavor == 'mac' and self.type in (
        'static_library', 'executable', 'shared_library', 'loadable_module'):
      return self.xcode_settings.GetExecutablePath()

    target = spec['target_name']
    target_prefix = ''
    target_ext = ''
    if self.type == 'static_library':
      if target[:3] == 'lib':
        target = target[3:]
      target_prefix = 'lib'
      target_ext = '.a'
    elif self.type in ('loadable_module', 'shared_library'):
      if target[:3] == 'lib':
        target = target[3:]
      target_prefix = 'lib'
      target_ext = '.so'
    elif self.type == 'none':
      target = '%s.stamp' % target
    elif self.type != 'executable':
      print ("ERROR: What output file should be generated?",
             "type", self.type, "target", target)

    target_prefix = spec.get('product_prefix', target_prefix)
    target = spec.get('product_name', target)
    product_ext = spec.get('product_extension')
    if product_ext:
      target_ext = '.' + product_ext

    return target_prefix + target + target_ext


  def _InstallImmediately(self):
    return self.toolset == 'target' and self.flavor == 'mac' and self.type in (
          'static_library', 'executable', 'shared_library', 'loadable_module')


  def ComputeOutput(self, spec):
    """Return the 'output' (full output path) of a gyp spec.

    E.g., the loadable module 'foobar' in directory 'baz' will produce
      '$(obj)/baz/libfoobar.so'
    """
    assert not self.is_mac_bundle

    path = os.path.join('$(obj).' + self.toolset, self.path)
    if self.type == 'executable' or self._InstallImmediately():
      path = '$(builddir)'
    path = spec.get('product_dir', path)
    return os.path.join(path, self.ComputeOutputBasename(spec))


  def ComputeMacBundleOutput(self, spec):
    """Return the 'output' (full output path) to a bundle output directory."""
    assert self.is_mac_bundle
    path = generator_default_variables['PRODUCT_DIR']
    return os.path.join(path, self.xcode_settings.GetWrapperName())


  def ComputeMacBundleBinaryOutput(self, spec):
    """Return the 'output' (full output path) to the binary in a bundle."""
    path = generator_default_variables['PRODUCT_DIR']
    return os.path.join(path, self.xcode_settings.GetExecutablePath())


  def ComputeDeps(self, spec):
    """Compute the dependencies of a gyp spec.

    Returns a tuple (deps, link_deps), where each is a list of
    filenames that will need to be put in front of make for either
    building (deps) or linking (link_deps).
    """
    deps = []
    link_deps = []
    if 'dependencies' in spec:
      deps.extend([target_outputs[dep] for dep in spec['dependencies']
                   if target_outputs[dep]])
      for dep in spec['dependencies']:
        if dep in target_link_deps:
          link_deps.append(target_link_deps[dep])
      deps.extend(link_deps)
      # TODO: It seems we need to transitively link in libraries (e.g. -lfoo)?
      # This hack makes it work:
      # link_deps.extend(spec.get('libraries', []))
    return (gyp.common.uniquer(deps), gyp.common.uniquer(link_deps))


  def WriteDependencyOnExtraOutputs(self, target, extra_outputs):
    self.WriteMakeRule([self.output_binary], extra_outputs,
                       comment = 'Build our special outputs first.',
                       order_only = True)


  def WriteTarget(self, spec, configs, deps, link_deps, bundle_deps,
                  extra_outputs, part_of_all):
    """Write Makefile code to produce the final target of the gyp spec.

    spec, configs: input from gyp.
    deps, link_deps: dependency lists; see ComputeDeps()
    extra_outputs: any extra outputs that our target should depend on
    part_of_all: flag indicating this target is part of 'all'
    """

    self.WriteLn('### Rules for final target.')

    if extra_outputs:
      self.WriteDependencyOnExtraOutputs(self.output_binary, extra_outputs)
      self.WriteMakeRule(extra_outputs, deps,
                         comment=('Preserve order dependency of '
                                  'special output on deps.'),
                         order_only = True)

    target_postbuilds = {}
    if self.type != 'none':
      for configname in sorted(configs.keys()):
        config = configs[configname]
        if self.flavor == 'mac':
          ldflags = self.xcode_settings.GetLdflags(configname,
              generator_default_variables['PRODUCT_DIR'],
              lambda p: Sourceify(self.Absolutify(p)))

          # TARGET_POSTBUILDS_$(BUILDTYPE) is added to postbuilds later on.
          gyp_to_build = InvertRelativePath(self.path)
          target_postbuild = self.xcode_settings.GetTargetPostbuilds(
              configname,
              QuoteSpaces(os.path.normpath(os.path.join(gyp_to_build,
                                                        self.output))),
              QuoteSpaces(os.path.normpath(os.path.join(gyp_to_build,
                                                        self.output_binary))))
          if target_postbuild:
            target_postbuilds[configname] = target_postbuild
        else:
          ldflags = config.get('ldflags', [])
          # Compute an rpath for this output if needed.
          if any(dep.endswith('.so') for dep in deps):
            # We want to get the literal string "$ORIGIN" into the link command,
            # so we need lots of escaping.
            ldflags.append(r'-Wl,-rpath=\$$ORIGIN/lib.%s/' % self.toolset)
            ldflags.append(r'-Wl,-rpath-link=\$(builddir)/lib.%s/' %
                           self.toolset)
        self.WriteList(ldflags, 'LDFLAGS_%s' % configname)
        if self.flavor == 'mac':
          self.WriteList(self.xcode_settings.GetLibtoolflags(configname),
                         'LIBTOOLFLAGS_%s' % configname)
      libraries = spec.get('libraries')
      if libraries:
        # Remove duplicate entries
        libraries = gyp.common.uniquer(libraries)
        if self.flavor == 'mac':
          libraries = self.xcode_settings.AdjustLibraries(libraries)
      self.WriteList(libraries, 'LIBS')
      self.WriteLn('%s: GYP_LDFLAGS := $(LDFLAGS_$(BUILDTYPE))' %
          QuoteSpaces(self.output_binary))
      self.WriteLn('%s: LIBS := $(LIBS)' % QuoteSpaces(self.output_binary))

      if self.flavor == 'mac':
        self.WriteLn('%s: GYP_LIBTOOLFLAGS := $(LIBTOOLFLAGS_$(BUILDTYPE))' %
            QuoteSpaces(self.output_binary))

    # Postbuild actions. Like actions, but implicitly depend on the target's
    # output.
    postbuilds = []
    if self.flavor == 'mac':
      if target_postbuilds:
        postbuilds.append('$(TARGET_POSTBUILDS_$(BUILDTYPE))')
      postbuilds.extend(
          gyp.xcode_emulation.GetSpecPostbuildCommands(spec))

    if postbuilds:
      # Envvars may be referenced by TARGET_POSTBUILDS_$(BUILDTYPE),
      # so we must output its definition first, since we declare variables
      # using ":=".
      self.WriteSortedXcodeEnv(self.output, self.GetSortedXcodePostbuildEnv())

      for configname in target_postbuilds:
        self.WriteLn('%s: TARGET_POSTBUILDS_%s := %s' %
            (QuoteSpaces(self.output),
             configname,
             gyp.common.EncodePOSIXShellList(target_postbuilds[configname])))

      # Postbuilds expect to be run in the gyp file's directory, so insert an
      # implicit postbuild to cd to there.
      postbuilds.insert(0, gyp.common.EncodePOSIXShellList(['cd', self.path]))
      for i in xrange(len(postbuilds)):
        if not postbuilds[i].startswith('$'):
          postbuilds[i] = EscapeShellArgument(postbuilds[i])
      self.WriteLn('%s: builddir := $(abs_builddir)' % QuoteSpaces(self.output))
      self.WriteLn('%s: POSTBUILDS := %s' % (
          QuoteSpaces(self.output), ' '.join(postbuilds)))

    # A bundle directory depends on its dependencies such as bundle resources
    # and bundle binary. When all dependencies have been built, the bundle
    # needs to be packaged.
    if self.is_mac_bundle:
      # If the framework doesn't contain a binary, then nothing depends
      # on the actions -- make the framework depend on them directly too.
      self.WriteDependencyOnExtraOutputs(self.output, extra_outputs)

      # Bundle dependencies. Note that the code below adds actions to this
      # target, so if you move these two lines, move the lines below as well.
      self.WriteList(map(QuoteSpaces, bundle_deps), 'BUNDLE_DEPS')
      self.WriteLn('%s: $(BUNDLE_DEPS)' % QuoteSpaces(self.output))

      # After the framework is built, package it. Needs to happen before
      # postbuilds, since postbuilds depend on this.
      if self.type in ('shared_library', 'loadable_module'):
        self.WriteLn('\t@$(call do_cmd,mac_package_framework,,,%s)' %
            self.xcode_settings.GetFrameworkVersion())

      # Bundle postbuilds can depend on the whole bundle, so run them after
      # the bundle is packaged, not already after the bundle binary is done.
      if postbuilds:
        self.WriteLn('\t@$(call do_postbuilds)')
      postbuilds = []  # Don't write postbuilds for target's output.

      # Needed by test/mac/gyptest-rebuild.py.
      self.WriteLn('\t@true  # No-op, used by tests')

      # Since this target depends on binary and resources which are in
      # nested subfolders, the framework directory will be older than
      # its dependencies usually. To prevent this rule from executing
      # on every build (expensive, especially with postbuilds), expliclity
      # update the time on the framework directory.
      self.WriteLn('\t@touch -c %s' % QuoteSpaces(self.output))

    if postbuilds:
      assert not self.is_mac_bundle, ('Postbuilds for bundles should be done '
          'on the bundle, not the binary (target \'%s\')' % self.target)
      assert 'product_dir' not in spec, ('Postbuilds do not work with '
          'custom product_dir')

    if self.type == 'executable':
      self.WriteLn('%s: LD_INPUTS := %s' % (
          QuoteSpaces(self.output_binary),
          ' '.join(map(QuoteSpaces, link_deps))))
      if self.toolset == 'host' and self.flavor == 'android':
        self.WriteDoCmd([self.output_binary], link_deps, 'link_host',
                        part_of_all, postbuilds=postbuilds)
      else:
        self.WriteDoCmd([self.output_binary], link_deps, 'link', part_of_all,
                        postbuilds=postbuilds)

    elif self.type == 'static_library':
      for link_dep in link_deps:
        assert ' ' not in link_dep, (
            "Spaces in alink input filenames not supported (%s)"  % link_dep)
      if (self.flavor not in ('mac', 'win') and not
          self.is_standalone_static_library):
        self.WriteDoCmd([self.output_binary], link_deps, 'alink_thin',
                        part_of_all, postbuilds=postbuilds)
      else:
        self.WriteDoCmd([self.output_binary], link_deps, 'alink', part_of_all,
                        postbuilds=postbuilds)
    elif self.type == 'shared_library':
      self.WriteLn('%s: LD_INPUTS := %s' % (
            QuoteSpaces(self.output_binary),
            ' '.join(map(QuoteSpaces, link_deps))))
      self.WriteDoCmd([self.output_binary], link_deps, 'solink', part_of_all,
                      postbuilds=postbuilds)
    elif self.type == 'loadable_module':
      for link_dep in link_deps:
        assert ' ' not in link_dep, (
            "Spaces in module input filenames not supported (%s)"  % link_dep)
      if self.toolset == 'host' and self.flavor == 'android':
        self.WriteDoCmd([self.output_binary], link_deps, 'solink_module_host',
                        part_of_all, postbuilds=postbuilds)
      else:
        self.WriteDoCmd(
            [self.output_binary], link_deps, 'solink_module', part_of_all,
            postbuilds=postbuilds)
    elif self.type == 'none':
      # Write a stamp line.
      self.WriteDoCmd([self.output_binary], deps, 'touch', part_of_all,
                      postbuilds=postbuilds)
    else:
      print "WARNING: no output for", self.type, target

    # Add an alias for each target (if there are any outputs).
    # Installable target aliases are created below.
    if ((self.output and self.output != self.target) and
        (self.type not in self._INSTALLABLE_TARGETS)):
      self.WriteMakeRule([self.target], [self.output],
                         comment='Add target alias', phony = True)
      if part_of_all:
        self.WriteMakeRule(['all'], [self.target],
                           comment = 'Add target alias to "all" target.',
                           phony = True)

    # Add special-case rules for our installable targets.
    # 1) They need to install to the build dir or "product" dir.
    # 2) They get shortcuts for building (e.g. "make chrome").
    # 3) They are part of "make all".
    if (self.type in self._INSTALLABLE_TARGETS or
        self.is_standalone_static_library):
      if self.type == 'shared_library':
        file_desc = 'shared library'
      elif self.type == 'static_library':
        file_desc = 'static library'
      else:
        file_desc = 'executable'
      install_path = self._InstallableTargetInstallPath()
      installable_deps = [self.output]
      if (self.flavor == 'mac' and not 'product_dir' in spec and
          self.toolset == 'target'):
        # On mac, products are created in install_path immediately.
        assert install_path == self.output, '%s != %s' % (
            install_path, self.output)

      # Point the target alias to the final binary output.
      self.WriteMakeRule([self.target], [install_path],
                         comment='Add target alias', phony = True)
      if install_path != self.output:
        assert not self.is_mac_bundle  # See comment a few lines above.
        self.WriteDoCmd([install_path], [self.output], 'copy',
                        comment = 'Copy this to the %s output path.' %
                        file_desc, part_of_all=part_of_all)
        installable_deps.append(install_path)
      if self.output != self.alias and self.alias != self.target:
        self.WriteMakeRule([self.alias], installable_deps,
                           comment = 'Short alias for building this %s.' %
                           file_desc, phony = True)
      if part_of_all:
        self.WriteMakeRule(['all'], [install_path],
                           comment = 'Add %s to "all" target.' % file_desc,
                           phony = True)


  def WriteList(self, value_list, variable=None, prefix='',
                quoter=QuoteIfNecessary):
    """Write a variable definition that is a list of values.

    E.g. WriteList(['a','b'], 'foo', prefix='blah') writes out
         foo = blaha blahb
    but in a pretty-printed style.
    """
    values = ''
    if value_list:
      value_list = [quoter(prefix + l) for l in value_list]
      values = ' \\\n\t' + ' \\\n\t'.join(value_list)
    self.fp.write('%s :=%s\n\n' % (variable, values))


  def WriteDoCmd(self, outputs, inputs, command, part_of_all, comment=None,
                 postbuilds=False):
    """Write a Makefile rule that uses do_cmd.

    This makes the outputs dependent on the command line that was run,
    as well as support the V= make command line flag.
    """
    suffix = ''
    if postbuilds:
      assert ',' not in command
      suffix = ',,1'  # Tell do_cmd to honor $POSTBUILDS
    self.WriteMakeRule(outputs, inputs,
                       actions = ['$(call do_cmd,%s%s)' % (command, suffix)],
                       comment = comment,
                       force = True)
    # Add our outputs to the list of targets we read depfiles from.
    # all_deps is only used for deps file reading, and for deps files we replace
    # spaces with ? because escaping doesn't work with make's $(sort) and
    # other functions.
    outputs = [QuoteSpaces(o, SPACE_REPLACEMENT) for o in outputs]
    self.WriteLn('all_deps += %s' % ' '.join(outputs))


  def WriteMakeRule(self, outputs, inputs, actions=None, comment=None,
                    order_only=False, force=False, phony=False):
    """Write a Makefile rule, with some extra tricks.

    outputs: a list of outputs for the rule (note: this is not directly
             supported by make; see comments below)
    inputs: a list of inputs for the rule
    actions: a list of shell commands to run for the rule
    comment: a comment to put in the Makefile above the rule (also useful
             for making this Python script's code self-documenting)
    order_only: if true, makes the dependency order-only
    force: if true, include FORCE_DO_CMD as an order-only dep
    phony: if true, the rule does not actually generate the named output, the
           output is just a name to run the rule
    """
    outputs = map(QuoteSpaces, outputs)
    inputs = map(QuoteSpaces, inputs)

    if comment:
      self.WriteLn('# ' + comment)
    if phony:
      self.WriteLn('.PHONY: ' + ' '.join(outputs))
    # TODO(evanm): just make order_only a list of deps instead of these hacks.
    if order_only:
      order_insert = '| '
      pick_output = ' '.join(outputs)
    else:
      order_insert = ''
      pick_output = outputs[0]
    if force:
      force_append = ' FORCE_DO_CMD'
    else:
      force_append = ''
    if actions:
      self.WriteLn("%s: TOOLSET := $(TOOLSET)" % outputs[0])
    self.WriteLn('%s: %s%s%s' % (pick_output, order_insert, ' '.join(inputs),
                                 force_append))
    if actions:
      for action in actions:
        self.WriteLn('\t%s' % action)
    if not order_only and len(outputs) > 1:
      # If we have more than one output, a rule like
      #   foo bar: baz
      # that for *each* output we must run the action, potentially
      # in parallel.  That is not what we're trying to write -- what
      # we want is that we run the action once and it generates all
      # the files.
      # http://www.gnu.org/software/hello/manual/automake/Multiple-Outputs.html
      # discusses this problem and has this solution:
      # 1) Write the naive rule that would produce parallel runs of
      # the action.
      # 2) Make the outputs seralized on each other, so we won't start
      # a parallel run until the first run finishes, at which point
      # we'll have generated all the outputs and we're done.
      self.WriteLn('%s: %s' % (' '.join(outputs[1:]), outputs[0]))
      # Add a dummy command to the "extra outputs" rule, otherwise make seems to
      # think these outputs haven't (couldn't have?) changed, and thus doesn't
      # flag them as changed (i.e. include in '$?') when evaluating dependent
      # rules, which in turn causes do_cmd() to skip running dependent commands.
      self.WriteLn('%s: ;' % (' '.join(outputs[1:])))
    self.WriteLn()


  def WriteAndroidNdkModuleRule(self, module_name, all_sources, link_deps):
    """Write a set of LOCAL_XXX definitions for Android NDK.

    These variable definitions will be used by Android NDK but do nothing for
    non-Android applications.

    Arguments:
      module_name: Android NDK module name, which must be unique among all
          module names.
      all_sources: A list of source files (will be filtered by Compilable).
      link_deps: A list of link dependencies, which must be sorted in
          the order from dependencies to dependents.
    """
    if self.type not in ('executable', 'shared_library', 'static_library'):
      return

    self.WriteLn('# Variable definitions for Android applications')
    self.WriteLn('include $(CLEAR_VARS)')
    self.WriteLn('LOCAL_MODULE := ' + module_name)
    self.WriteLn('LOCAL_CFLAGS := $(CFLAGS_$(BUILDTYPE)) '
                 '$(DEFS_$(BUILDTYPE)) '
                 # LOCAL_CFLAGS is applied to both of C and C++.  There is
                 # no way to specify $(CFLAGS_C_$(BUILDTYPE)) only for C
                 # sources.
                 '$(CFLAGS_C_$(BUILDTYPE)) '
                 # $(INCS_$(BUILDTYPE)) includes the prefix '-I' while
                 # LOCAL_C_INCLUDES does not expect it.  So put it in
                 # LOCAL_CFLAGS.
                 '$(INCS_$(BUILDTYPE))')
    # LOCAL_CXXFLAGS is obsolete and LOCAL_CPPFLAGS is preferred.
    self.WriteLn('LOCAL_CPPFLAGS := $(CFLAGS_CC_$(BUILDTYPE))')
    self.WriteLn('LOCAL_C_INCLUDES :=')
    self.WriteLn('LOCAL_LDLIBS := $(LDFLAGS_$(BUILDTYPE)) $(LIBS)')

    # Detect the C++ extension.
    cpp_ext = {'.cc': 0, '.cpp': 0, '.cxx': 0}
    default_cpp_ext = '.cpp'
    for filename in all_sources:
      ext = os.path.splitext(filename)[1]
      if ext in cpp_ext:
        cpp_ext[ext] += 1
        if cpp_ext[ext] > cpp_ext[default_cpp_ext]:
          default_cpp_ext = ext
    self.WriteLn('LOCAL_CPP_EXTENSION := ' + default_cpp_ext)

    self.WriteList(map(self.Absolutify, filter(Compilable, all_sources)),
                   'LOCAL_SRC_FILES')

    # Filter out those which do not match prefix and suffix and produce
    # the resulting list without prefix and suffix.
    def DepsToModules(deps, prefix, suffix):
      modules = []
      for filepath in deps:
        filename = os.path.basename(filepath)
        if filename.startswith(prefix) and filename.endswith(suffix):
          modules.append(filename[len(prefix):-len(suffix)])
      return modules

    # Retrieve the default value of 'SHARED_LIB_SUFFIX'
    params = {'flavor': 'linux'}
    default_variables = {}
    CalculateVariables(default_variables, params)

    self.WriteList(
        DepsToModules(link_deps,
                      generator_default_variables['SHARED_LIB_PREFIX'],
                      default_variables['SHARED_LIB_SUFFIX']),
        'LOCAL_SHARED_LIBRARIES')
    self.WriteList(
        DepsToModules(link_deps,
                      generator_default_variables['STATIC_LIB_PREFIX'],
                      generator_default_variables['STATIC_LIB_SUFFIX']),
        'LOCAL_STATIC_LIBRARIES')

    if self.type == 'executable':
      self.WriteLn('include $(BUILD_EXECUTABLE)')
    elif self.type == 'shared_library':
      self.WriteLn('include $(BUILD_SHARED_LIBRARY)')
    elif self.type == 'static_library':
      self.WriteLn('include $(BUILD_STATIC_LIBRARY)')
    self.WriteLn()


  def WriteLn(self, text=''):
    self.fp.write(text + '\n')


  def GetSortedXcodeEnv(self, additional_settings=None):
    return gyp.xcode_emulation.GetSortedXcodeEnv(
        self.xcode_settings, "$(abs_builddir)",
        os.path.join("$(abs_srcdir)", self.path), "$(BUILDTYPE)",
        additional_settings)


  def GetSortedXcodePostbuildEnv(self):
    # CHROMIUM_STRIP_SAVE_FILE is a chromium-specific hack.
    # TODO(thakis): It would be nice to have some general mechanism instead.
    strip_save_file = self.xcode_settings.GetPerTargetSetting(
        'CHROMIUM_STRIP_SAVE_FILE', '')
    # Even if strip_save_file is empty, explicitly write it. Else a postbuild
    # might pick up an export from an earlier target.
    return self.GetSortedXcodeEnv(
        additional_settings={'CHROMIUM_STRIP_SAVE_FILE': strip_save_file})


  def WriteSortedXcodeEnv(self, target, env):
    for k, v in env:
      # For
      #  foo := a\ b
      # the escaped space does the right thing. For
      #  export foo := a\ b
      # it does not -- the backslash is written to the env as literal character.
      # So don't escape spaces in |env[k]|.
      self.WriteLn('%s: export %s := %s' % (QuoteSpaces(target), k, v))


  def Objectify(self, path):
    """Convert a path to its output directory form."""
    if '$(' in path:
      path = path.replace('$(obj)/', '$(obj).%s/$(TARGET)/' % self.toolset)
    if not '$(obj)' in path:
      path = '$(obj).%s/$(TARGET)/%s' % (self.toolset, path)
    return path


  def Pchify(self, path, lang):
    """Convert a prefix header path to its output directory form."""
    path = self.Absolutify(path)
    if '$(' in path:
      path = path.replace('$(obj)/', '$(obj).%s/$(TARGET)/pch-%s' %
                          (self.toolset, lang))
      return path
    return '$(obj).%s/$(TARGET)/pch-%s/%s' % (self.toolset, lang, path)


  def Absolutify(self, path):
    """Convert a subdirectory-relative path into a base-relative path.
    Skips over paths that contain variables."""
    if '$(' in path:
      # Don't call normpath in this case, as it might collapse the
      # path too aggressively if it features '..'. However it's still
      # important to strip trailing slashes.
      return path.rstrip('/')
    return os.path.normpath(os.path.join(self.path, path))


  def ExpandInputRoot(self, template, expansion, dirname):
    if '%(INPUT_ROOT)s' not in template and '%(INPUT_DIRNAME)s' not in template:
      return template
    path = template % {
        'INPUT_ROOT': expansion,
        'INPUT_DIRNAME': dirname,
        }
    return path


  def _InstallableTargetInstallPath(self):
    """Returns the location of the final output for an installable target."""
    # Xcode puts shared_library results into PRODUCT_DIR, and some gyp files
    # rely on this. Emulate this behavior for mac.
    if (self.type == 'shared_library' and
        (self.flavor != 'mac' or self.toolset != 'target')):
      # Install all shared libs into a common directory (per toolset) for
      # convenient access with LD_LIBRARY_PATH.
      return '$(builddir)/lib.%s/%s' % (self.toolset, self.alias)
    return '$(builddir)/' + self.alias


def WriteAutoRegenerationRule(params, root_makefile, makefile_name,
                              build_files):
  """Write the target to regenerate the Makefile."""
  options = params['options']
  build_files_args = [gyp.common.RelativePath(filename, options.toplevel_dir)
                      for filename in params['build_files_arg']]
  gyp_binary = gyp.common.FixIfRelativePath(params['gyp_binary'],
                                            options.toplevel_dir)
  if not gyp_binary.startswith(os.sep):
    gyp_binary = os.path.join('.', gyp_binary)
  root_makefile.write(
      "quiet_cmd_regen_makefile = ACTION Regenerating $@\n"
      "cmd_regen_makefile = %(cmd)s\n"
      "%(makefile_name)s: %(deps)s\n"
      "\t$(call do_cmd,regen_makefile)\n\n" % {
          'makefile_name': makefile_name,
          'deps': ' '.join(map(Sourceify, build_files)),
          'cmd': gyp.common.EncodePOSIXShellList(
                     [gyp_binary, '-fmake'] +
                     gyp.RegenerateFlags(options) +
                     build_files_args)})


def PerformBuild(data, configurations, params):
  options = params['options']
  for config in configurations:
    arguments = ['make']
    if options.toplevel_dir and options.toplevel_dir != '.':
      arguments += '-C', options.toplevel_dir
    arguments.append('BUILDTYPE=' + config)
    print 'Building [%s]: %s' % (config, arguments)
    subprocess.check_call(arguments)


def GenerateOutput(target_list, target_dicts, data, params):
  options = params['options']
  flavor = gyp.common.GetFlavor(params)
  generator_flags = params.get('generator_flags', {})
  builddir_name = generator_flags.get('output_dir', 'out')
  android_ndk_version = generator_flags.get('android_ndk_version', None)
  default_target = generator_flags.get('default_target', 'all')

  def CalculateMakefilePath(build_file, base_name):
    """Determine where to write a Makefile for a given gyp file."""
    # Paths in gyp files are relative to the .gyp file, but we want
    # paths relative to the source root for the master makefile.  Grab
    # the path of the .gyp file as the base to relativize against.
    # E.g. "foo/bar" when we're constructing targets for "foo/bar/baz.gyp".
    base_path = gyp.common.RelativePath(os.path.dirname(build_file),
                                        options.depth)
    # We write the file in the base_path directory.
    output_file = os.path.join(options.depth, base_path, base_name)
    if options.generator_output:
      output_file = os.path.join(options.generator_output, output_file)
    base_path = gyp.common.RelativePath(os.path.dirname(build_file),
                                        options.toplevel_dir)
    return base_path, output_file

  # TODO:  search for the first non-'Default' target.  This can go
  # away when we add verification that all targets have the
  # necessary configurations.
  default_configuration = None
  toolsets = set([target_dicts[target]['toolset'] for target in target_list])
  for target in target_list:
    spec = target_dicts[target]
    if spec['default_configuration'] != 'Default':
      default_configuration = spec['default_configuration']
      break
  if not default_configuration:
    default_configuration = 'Default'

  srcdir = '.'
  makefile_name = 'Makefile' + options.suffix
  makefile_path = os.path.join(options.toplevel_dir, makefile_name)
  if options.generator_output:
    global srcdir_prefix
    makefile_path = os.path.join(options.generator_output, makefile_path)
    srcdir = gyp.common.RelativePath(srcdir, options.generator_output)
    srcdir_prefix = '$(srcdir)/'

  flock_command= 'flock'
  header_params = {
      'default_target': default_target,
      'builddir': builddir_name,
      'default_configuration': default_configuration,
      'flock': flock_command,
      'flock_index': 1,
      'link_commands': LINK_COMMANDS_LINUX,
      'extra_commands': '',
      'srcdir': srcdir,
    }
  if flavor == 'mac':
    flock_command = './gyp-mac-tool flock'
    header_params.update({
        'flock': flock_command,
        'flock_index': 2,
        'link_commands': LINK_COMMANDS_MAC,
        'extra_commands': SHARED_HEADER_MAC_COMMANDS,
    })
  elif flavor == 'android':
    header_params.update({
        'link_commands': LINK_COMMANDS_ANDROID,
    })
  elif flavor == 'solaris':
    header_params.update({
        'flock': './gyp-sun-tool flock',
        'flock_index': 2,
        'extra_commands': SHARED_HEADER_SUN_COMMANDS,
    })
  elif flavor == 'freebsd':
    header_params.update({
        'flock': 'lockf',
    })

  header_params.update({
    'CC.target':   GetEnvironFallback(('CC_target', 'CC'), '$(CC)'),
    'AR.target':   GetEnvironFallback(('AR_target', 'AR'), '$(AR)'),
    'CXX.target':  GetEnvironFallback(('CXX_target', 'CXX'), '$(CXX)'),
    'LINK.target': GetEnvironFallback(('LD_target', 'LD'), '$(LINK)'),
    'CC.host':     GetEnvironFallback(('CC_host',), 'gcc'),
    'AR.host':     GetEnvironFallback(('AR_host',), 'ar'),
    'CXX.host':    GetEnvironFallback(('CXX_host',), 'g++'),
    'LINK.host':   GetEnvironFallback(('LD_host',), 'g++'),
  })

  build_file, _, _ = gyp.common.ParseQualifiedTarget(target_list[0])
  make_global_settings_array = data[build_file].get('make_global_settings', [])
  make_global_settings = ''
  for key, value in make_global_settings_array:
    if value[0] != '$':
      value = '$(abspath %s)' % value
    if key == 'LINK':
      make_global_settings += ('%s ?= %s $(builddir)/linker.lock %s\n' %
                               (key, flock_command, value))
    elif key in ('CC', 'CC.host', 'CXX', 'CXX.host'):
      make_global_settings += (
          'ifneq (,$(filter $(origin %s), undefined default))\n' % key)
      # Let gyp-time envvars win over global settings.
      if key in os.environ:
        value = os.environ[key]
      make_global_settings += '  %s = %s\n' % (key, value)
      make_global_settings += 'endif\n'
    else:
      make_global_settings += '%s ?= %s\n' % (key, value)
  header_params['make_global_settings'] = make_global_settings

  ensure_directory_exists(makefile_path)
  root_makefile = open(makefile_path, 'w')
  root_makefile.write(SHARED_HEADER % header_params)
  # Currently any versions have the same effect, but in future the behavior
  # could be different.
  if android_ndk_version:
    root_makefile.write(
        '# Define LOCAL_PATH for build of Android applications.\n'
        'LOCAL_PATH := $(call my-dir)\n'
        '\n')
  for toolset in toolsets:
    root_makefile.write('TOOLSET := %s\n' % toolset)
    WriteRootHeaderSuffixRules(root_makefile)

  # Put build-time support tools next to the root Makefile.
  dest_path = os.path.dirname(makefile_path)
  gyp.common.CopyTool(flavor, dest_path)

  # Find the list of targets that derive from the gyp file(s) being built.
  needed_targets = set()
  for build_file in params['build_files']:
    for target in gyp.common.AllTargets(target_list, target_dicts, build_file):
      needed_targets.add(target)

  build_files = set()
  include_list = set()
  for qualified_target in target_list:
    build_file, target, toolset = gyp.common.ParseQualifiedTarget(
        qualified_target)

    this_make_global_settings = data[build_file].get('make_global_settings', [])
    assert make_global_settings_array == this_make_global_settings, (
        "make_global_settings needs to be the same for all targets.")

    build_files.add(gyp.common.RelativePath(build_file, options.toplevel_dir))
    included_files = data[build_file]['included_files']
    for included_file in included_files:
      # The included_files entries are relative to the dir of the build file
      # that included them, so we have to undo that and then make them relative
      # to the root dir.
      relative_include_file = gyp.common.RelativePath(
          gyp.common.UnrelativePath(included_file, build_file),
          options.toplevel_dir)
      abs_include_file = os.path.abspath(relative_include_file)
      # If the include file is from the ~/.gyp dir, we should use absolute path
      # so that relocating the src dir doesn't break the path.
      if (params['home_dot_gyp'] and
          abs_include_file.startswith(params['home_dot_gyp'])):
        build_files.add(abs_include_file)
      else:
        build_files.add(relative_include_file)

    base_path, output_file = CalculateMakefilePath(build_file,
        target + '.' + toolset + options.suffix + '.mk')

    spec = target_dicts[qualified_target]
    configs = spec['configurations']

    if flavor == 'mac':
      gyp.xcode_emulation.MergeGlobalXcodeSettingsToSpec(data[build_file], spec)

    writer = MakefileWriter(generator_flags, flavor)
    writer.Write(qualified_target, base_path, output_file, spec, configs,
                 part_of_all=qualified_target in needed_targets)

    # Our root_makefile lives at the source root.  Compute the relative path
    # from there to the output_file for including.
    mkfile_rel_path = gyp.common.RelativePath(output_file,
                                              os.path.dirname(makefile_path))
    include_list.add(mkfile_rel_path)

  # Write out per-gyp (sub-project) Makefiles.
  depth_rel_path = gyp.common.RelativePath(options.depth, os.getcwd())
  for build_file in build_files:
    # The paths in build_files were relativized above, so undo that before
    # testing against the non-relativized items in target_list and before
    # calculating the Makefile path.
    build_file = os.path.join(depth_rel_path, build_file)
    gyp_targets = [target_dicts[target]['target_name'] for target in target_list
                   if target.startswith(build_file) and
                   target in needed_targets]
    # Only generate Makefiles for gyp files with targets.
    if not gyp_targets:
      continue
    base_path, output_file = CalculateMakefilePath(build_file,
        os.path.splitext(os.path.basename(build_file))[0] + '.Makefile')
    makefile_rel_path = gyp.common.RelativePath(os.path.dirname(makefile_path),
                                                os.path.dirname(output_file))
    writer.WriteSubMake(output_file, makefile_rel_path, gyp_targets,
                        builddir_name)


  # Write out the sorted list of includes.
  root_makefile.write('\n')
  for include_file in sorted(include_list):
    # We wrap each .mk include in an if statement so users can tell make to
    # not load a file by setting NO_LOAD.  The below make code says, only
    # load the .mk file if the .mk filename doesn't start with a token in
    # NO_LOAD.
    root_makefile.write(
        "ifeq ($(strip $(foreach prefix,$(NO_LOAD),\\\n"
        "    $(findstring $(join ^,$(prefix)),\\\n"
        "                 $(join ^," + include_file + ")))),)\n")
    root_makefile.write("  include " + include_file + "\n")
    root_makefile.write("endif\n")
  root_makefile.write('\n')

  if (not generator_flags.get('standalone')
      and generator_flags.get('auto_regeneration', True)):
    WriteAutoRegenerationRule(params, root_makefile, makefile_name, build_files)

  root_makefile.write(SHARED_FOOTER)

  root_makefile.close()

########NEW FILE########
__FILENAME__ = msvs
# Copyright (c) 2012 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import ntpath
import os
import posixpath
import re
import subprocess
import sys

import gyp.common
import gyp.easy_xml as easy_xml
import gyp.MSVSNew as MSVSNew
import gyp.MSVSProject as MSVSProject
import gyp.MSVSSettings as MSVSSettings
import gyp.MSVSToolFile as MSVSToolFile
import gyp.MSVSUserFile as MSVSUserFile
import gyp.MSVSVersion as MSVSVersion
from gyp.common import GypError


# Regular expression for validating Visual Studio GUIDs.  If the GUID
# contains lowercase hex letters, MSVS will be fine. However,
# IncrediBuild BuildConsole will parse the solution file, but then
# silently skip building the target causing hard to track down errors.
# Note that this only happens with the BuildConsole, and does not occur
# if IncrediBuild is executed from inside Visual Studio.  This regex
# validates that the string looks like a GUID with all uppercase hex
# letters.
VALID_MSVS_GUID_CHARS = re.compile('^[A-F0-9\-]+$')


generator_default_variables = {
    'EXECUTABLE_PREFIX': '',
    'EXECUTABLE_SUFFIX': '.exe',
    'STATIC_LIB_PREFIX': '',
    'SHARED_LIB_PREFIX': '',
    'STATIC_LIB_SUFFIX': '.lib',
    'SHARED_LIB_SUFFIX': '.dll',
    'INTERMEDIATE_DIR': '$(IntDir)',
    'SHARED_INTERMEDIATE_DIR': '$(OutDir)obj/global_intermediate',
    'OS': 'win',
    'PRODUCT_DIR': '$(OutDir)',
    'LIB_DIR': '$(OutDir)lib',
    'RULE_INPUT_ROOT': '$(InputName)',
    'RULE_INPUT_DIRNAME': '$(InputDir)',
    'RULE_INPUT_EXT': '$(InputExt)',
    'RULE_INPUT_NAME': '$(InputFileName)',
    'RULE_INPUT_PATH': '$(InputPath)',
    'CONFIGURATION_NAME': '$(ConfigurationName)',
}


# The msvs specific sections that hold paths
generator_additional_path_sections = [
    'msvs_cygwin_dirs',
    'msvs_props',
]


generator_additional_non_configuration_keys = [
    'msvs_cygwin_dirs',
    'msvs_cygwin_shell',
    'msvs_shard',
]


# List of precompiled header related keys.
precomp_keys = [
    'msvs_precompiled_header',
    'msvs_precompiled_source',
]


cached_username = None


cached_domain = None


# TODO(gspencer): Switch the os.environ calls to be
# win32api.GetDomainName() and win32api.GetUserName() once the
# python version in depot_tools has been updated to work on Vista
# 64-bit.
def _GetDomainAndUserName():
  if sys.platform not in ('win32', 'cygwin'):
    return ('DOMAIN', 'USERNAME')
  global cached_username
  global cached_domain
  if not cached_domain or not cached_username:
    domain = os.environ.get('USERDOMAIN')
    username = os.environ.get('USERNAME')
    if not domain or not username:
      call = subprocess.Popen(['net', 'config', 'Workstation'],
                              stdout=subprocess.PIPE)
      config = call.communicate()[0]
      username_re = re.compile('^User name\s+(\S+)', re.MULTILINE)
      username_match = username_re.search(config)
      if username_match:
        username = username_match.group(1)
      domain_re = re.compile('^Logon domain\s+(\S+)', re.MULTILINE)
      domain_match = domain_re.search(config)
      if domain_match:
        domain = domain_match.group(1)
    cached_domain = domain
    cached_username = username
  return (cached_domain, cached_username)

fixpath_prefix = None


def _NormalizedSource(source):
  """Normalize the path.

  But not if that gets rid of a variable, as this may expand to something
  larger than one directory.

  Arguments:
      source: The path to be normalize.d

  Returns:
      The normalized path.
  """
  normalized = os.path.normpath(source)
  if source.count('$') == normalized.count('$'):
    source = normalized
  return source


def _FixPath(path):
  """Convert paths to a form that will make sense in a vcproj file.

  Arguments:
    path: The path to convert, may contain / etc.
  Returns:
    The path with all slashes made into backslashes.
  """
  if fixpath_prefix and path and not os.path.isabs(path) and not path[0] == '$':
    path = os.path.join(fixpath_prefix, path)
  path = path.replace('/', '\\')
  path = _NormalizedSource(path)
  if path and path[-1] == '\\':
    path = path[:-1]
  return path


def _FixPaths(paths):
  """Fix each of the paths of the list."""
  return [_FixPath(i) for i in paths]


def _ConvertSourcesToFilterHierarchy(sources, prefix=None, excluded=None,
                                     list_excluded=True):
  """Converts a list split source file paths into a vcproj folder hierarchy.

  Arguments:
    sources: A list of source file paths split.
    prefix: A list of source file path layers meant to apply to each of sources.
    excluded: A set of excluded files.

  Returns:
    A hierarchy of filenames and MSVSProject.Filter objects that matches the
    layout of the source tree.
    For example:
    _ConvertSourcesToFilterHierarchy([['a', 'bob1.c'], ['b', 'bob2.c']],
                                     prefix=['joe'])
    -->
    [MSVSProject.Filter('a', contents=['joe\\a\\bob1.c']),
     MSVSProject.Filter('b', contents=['joe\\b\\bob2.c'])]
  """
  if not prefix: prefix = []
  result = []
  excluded_result = []
  folders = dict()
  # Gather files into the final result, excluded, or folders.
  for s in sources:
    if len(s) == 1:
      filename = _NormalizedSource('\\'.join(prefix + s))
      if filename in excluded:
        excluded_result.append(filename)
      else:
        result.append(filename)
    else:
      if not folders.get(s[0]):
        folders[s[0]] = []
      folders[s[0]].append(s[1:])
  # Add a folder for excluded files.
  if excluded_result and list_excluded:
    excluded_folder = MSVSProject.Filter('_excluded_files',
                                         contents=excluded_result)
    result.append(excluded_folder)
  # Populate all the folders.
  for f in folders:
    contents = _ConvertSourcesToFilterHierarchy(folders[f], prefix=prefix + [f],
                                                excluded=excluded,
                                                list_excluded=list_excluded)
    contents = MSVSProject.Filter(f, contents=contents)
    result.append(contents)

  return result


def _ToolAppend(tools, tool_name, setting, value, only_if_unset=False):
  if not value: return
  # TODO(bradnelson): ugly hack, fix this more generally!!!
  if 'Directories' in setting or 'Dependencies' in setting:
    if type(value) == str:
      value = value.replace('/', '\\')
    else:
      value = [i.replace('/', '\\') for i in value]
  if not tools.get(tool_name):
    tools[tool_name] = dict()
  tool = tools[tool_name]
  if tool.get(setting):
    if only_if_unset: return
    if type(tool[setting]) == list:
      tool[setting] += value
    else:
      raise TypeError(
          'Appending "%s" to a non-list setting "%s" for tool "%s" is '
          'not allowed, previous value: %s' % (
              value, setting, tool_name, str(tool[setting])))
  else:
    tool[setting] = value


def _ConfigPlatform(config_data):
  return config_data.get('msvs_configuration_platform', 'Win32')


def _ConfigBaseName(config_name, platform_name):
  if config_name.endswith('_' + platform_name):
    return config_name[0:-len(platform_name)-1]
  else:
    return config_name


def _ConfigFullName(config_name, config_data):
  platform_name = _ConfigPlatform(config_data)
  return '%s|%s' % (_ConfigBaseName(config_name, platform_name), platform_name)


def _BuildCommandLineForRuleRaw(spec, cmd, cygwin_shell, has_input_path,
                                quote_cmd, do_setup_env):

  if [x for x in cmd if '$(InputDir)' in x]:
    input_dir_preamble = (
      'set INPUTDIR=$(InputDir)\n'
      'set INPUTDIR=%INPUTDIR:$(ProjectDir)=%\n'
      'set INPUTDIR=%INPUTDIR:~0,-1%\n'
      )
  else:
    input_dir_preamble = ''

  if cygwin_shell:
    # Find path to cygwin.
    cygwin_dir = _FixPath(spec.get('msvs_cygwin_dirs', ['.'])[0])
    # Prepare command.
    direct_cmd = cmd
    direct_cmd = [i.replace('$(IntDir)',
                            '`cygpath -m "${INTDIR}"`') for i in direct_cmd]
    direct_cmd = [i.replace('$(OutDir)',
                            '`cygpath -m "${OUTDIR}"`') for i in direct_cmd]
    direct_cmd = [i.replace('$(InputDir)',
                            '`cygpath -m "${INPUTDIR}"`') for i in direct_cmd]
    if has_input_path:
      direct_cmd = [i.replace('$(InputPath)',
                              '`cygpath -m "${INPUTPATH}"`')
                    for i in direct_cmd]
    direct_cmd = ['\\"%s\\"' % i.replace('"', '\\\\\\"') for i in direct_cmd]
    #direct_cmd = gyp.common.EncodePOSIXShellList(direct_cmd)
    direct_cmd = ' '.join(direct_cmd)
    # TODO(quote):  regularize quoting path names throughout the module
    cmd = ''
    if do_setup_env:
      cmd += 'call "$(ProjectDir)%(cygwin_dir)s\\setup_env.bat" && '
    cmd += 'set CYGWIN=nontsec&& '
    if direct_cmd.find('NUMBER_OF_PROCESSORS') >= 0:
      cmd += 'set /a NUMBER_OF_PROCESSORS_PLUS_1=%%NUMBER_OF_PROCESSORS%%+1&& '
    if direct_cmd.find('INTDIR') >= 0:
      cmd += 'set INTDIR=$(IntDir)&& '
    if direct_cmd.find('OUTDIR') >= 0:
      cmd += 'set OUTDIR=$(OutDir)&& '
    if has_input_path and direct_cmd.find('INPUTPATH') >= 0:
      cmd += 'set INPUTPATH=$(InputPath) && '
    cmd += 'bash -c "%(cmd)s"'
    cmd = cmd % {'cygwin_dir': cygwin_dir,
                 'cmd': direct_cmd}
    return input_dir_preamble + cmd
  else:
    # Convert cat --> type to mimic unix.
    if cmd[0] == 'cat':
      command = ['type']
    else:
      command = [cmd[0].replace('/', '\\')]
    # Add call before command to ensure that commands can be tied together one
    # after the other without aborting in Incredibuild, since IB makes a bat
    # file out of the raw command string, and some commands (like python) are
    # actually batch files themselves.
    command.insert(0, 'call')
    # Fix the paths
    # TODO(quote): This is a really ugly heuristic, and will miss path fixing
    #              for arguments like "--arg=path" or "/opt:path".
    # If the argument starts with a slash or dash, it's probably a command line
    # switch
    arguments = [i if (i[:1] in "/-") else _FixPath(i) for i in cmd[1:]]
    arguments = [i.replace('$(InputDir)','%INPUTDIR%') for i in arguments]
    arguments = [MSVSSettings.FixVCMacroSlashes(i) for i in arguments]
    if quote_cmd:
      # Support a mode for using cmd directly.
      # Convert any paths to native form (first element is used directly).
      # TODO(quote):  regularize quoting path names throughout the module
      arguments = ['"%s"' % i for i in arguments]
    # Collapse into a single command.
    return input_dir_preamble + ' '.join(command + arguments)


def _BuildCommandLineForRule(spec, rule, has_input_path, do_setup_env):
  # Currently this weird argument munging is used to duplicate the way a
  # python script would need to be run as part of the chrome tree.
  # Eventually we should add some sort of rule_default option to set this
  # per project. For now the behavior chrome needs is the default.
  mcs = rule.get('msvs_cygwin_shell')
  if mcs is None:
    mcs = int(spec.get('msvs_cygwin_shell', 1))
  elif isinstance(mcs, str):
    mcs = int(mcs)
  quote_cmd = int(rule.get('msvs_quote_cmd', 1))
  return _BuildCommandLineForRuleRaw(spec, rule['action'], mcs, has_input_path,
                                     quote_cmd, do_setup_env=do_setup_env)


def _AddActionStep(actions_dict, inputs, outputs, description, command):
  """Merge action into an existing list of actions.

  Care must be taken so that actions which have overlapping inputs either don't
  get assigned to the same input, or get collapsed into one.

  Arguments:
    actions_dict: dictionary keyed on input name, which maps to a list of
      dicts describing the actions attached to that input file.
    inputs: list of inputs
    outputs: list of outputs
    description: description of the action
    command: command line to execute
  """
  # Require there to be at least one input (call sites will ensure this).
  assert inputs

  action = {
      'inputs': inputs,
      'outputs': outputs,
      'description': description,
      'command': command,
  }

  # Pick where to stick this action.
  # While less than optimal in terms of build time, attach them to the first
  # input for now.
  chosen_input = inputs[0]

  # Add it there.
  if chosen_input not in actions_dict:
    actions_dict[chosen_input] = []
  actions_dict[chosen_input].append(action)


def _AddCustomBuildToolForMSVS(p, spec, primary_input,
                               inputs, outputs, description, cmd):
  """Add a custom build tool to execute something.

  Arguments:
    p: the target project
    spec: the target project dict
    primary_input: input file to attach the build tool to
    inputs: list of inputs
    outputs: list of outputs
    description: description of the action
    cmd: command line to execute
  """
  inputs = _FixPaths(inputs)
  outputs = _FixPaths(outputs)
  tool = MSVSProject.Tool(
      'VCCustomBuildTool',
      {'Description': description,
       'AdditionalDependencies': ';'.join(inputs),
       'Outputs': ';'.join(outputs),
       'CommandLine': cmd,
      })
  # Add to the properties of primary input for each config.
  for config_name, c_data in spec['configurations'].iteritems():
    p.AddFileConfig(_FixPath(primary_input),
                    _ConfigFullName(config_name, c_data), tools=[tool])


def _AddAccumulatedActionsToMSVS(p, spec, actions_dict):
  """Add actions accumulated into an actions_dict, merging as needed.

  Arguments:
    p: the target project
    spec: the target project dict
    actions_dict: dictionary keyed on input name, which maps to a list of
        dicts describing the actions attached to that input file.
  """
  for primary_input in actions_dict:
    inputs = set()
    outputs = set()
    descriptions = []
    commands = []
    for action in actions_dict[primary_input]:
      inputs.update(set(action['inputs']))
      outputs.update(set(action['outputs']))
      descriptions.append(action['description'])
      commands.append(action['command'])
    # Add the custom build step for one input file.
    description = ', and also '.join(descriptions)
    command = '\r\n'.join(commands)
    _AddCustomBuildToolForMSVS(p, spec,
                               primary_input=primary_input,
                               inputs=inputs,
                               outputs=outputs,
                               description=description,
                               cmd=command)


def _RuleExpandPath(path, input_file):
  """Given the input file to which a rule applied, string substitute a path.

  Arguments:
    path: a path to string expand
    input_file: the file to which the rule applied.
  Returns:
    The string substituted path.
  """
  path = path.replace('$(InputName)',
                      os.path.splitext(os.path.split(input_file)[1])[0])
  path = path.replace('$(InputDir)', os.path.dirname(input_file))
  path = path.replace('$(InputExt)',
                      os.path.splitext(os.path.split(input_file)[1])[1])
  path = path.replace('$(InputFileName)', os.path.split(input_file)[1])
  path = path.replace('$(InputPath)', input_file)
  return path


def _FindRuleTriggerFiles(rule, sources):
  """Find the list of files which a particular rule applies to.

  Arguments:
    rule: the rule in question
    sources: the set of all known source files for this project
  Returns:
    The list of sources that trigger a particular rule.
  """
  rule_ext = rule['extension']
  return [s for s in sources if s.endswith('.' + rule_ext)]


def _RuleInputsAndOutputs(rule, trigger_file):
  """Find the inputs and outputs generated by a rule.

  Arguments:
    rule: the rule in question.
    trigger_file: the main trigger for this rule.
  Returns:
    The pair of (inputs, outputs) involved in this rule.
  """
  raw_inputs = _FixPaths(rule.get('inputs', []))
  raw_outputs = _FixPaths(rule.get('outputs', []))
  inputs = set()
  outputs = set()
  inputs.add(trigger_file)
  for i in raw_inputs:
    inputs.add(_RuleExpandPath(i, trigger_file))
  for o in raw_outputs:
    outputs.add(_RuleExpandPath(o, trigger_file))
  return (inputs, outputs)


def _GenerateNativeRulesForMSVS(p, rules, output_dir, spec, options):
  """Generate a native rules file.

  Arguments:
    p: the target project
    rules: the set of rules to include
    output_dir: the directory in which the project/gyp resides
    spec: the project dict
    options: global generator options
  """
  rules_filename = '%s%s.rules' % (spec['target_name'],
                                   options.suffix)
  rules_file = MSVSToolFile.Writer(os.path.join(output_dir, rules_filename),
                                   spec['target_name'])
  # Add each rule.
  for r in rules:
    rule_name = r['rule_name']
    rule_ext = r['extension']
    inputs = _FixPaths(r.get('inputs', []))
    outputs = _FixPaths(r.get('outputs', []))
    # Skip a rule with no action and no inputs.
    if 'action' not in r and not r.get('rule_sources', []):
      continue
    cmd = _BuildCommandLineForRule(spec, r, has_input_path=True,
                                   do_setup_env=True)
    rules_file.AddCustomBuildRule(name=rule_name,
                                  description=r.get('message', rule_name),
                                  extensions=[rule_ext],
                                  additional_dependencies=inputs,
                                  outputs=outputs,
                                  cmd=cmd)
  # Write out rules file.
  rules_file.WriteIfChanged()

  # Add rules file to project.
  p.AddToolFile(rules_filename)


def _Cygwinify(path):
  path = path.replace('$(OutDir)', '$(OutDirCygwin)')
  path = path.replace('$(IntDir)', '$(IntDirCygwin)')
  return path


def _GenerateExternalRules(rules, output_dir, spec,
                           sources, options, actions_to_add):
  """Generate an external makefile to do a set of rules.

  Arguments:
    rules: the list of rules to include
    output_dir: path containing project and gyp files
    spec: project specification data
    sources: set of sources known
    options: global generator options
    actions_to_add: The list of actions we will add to.
  """
  filename = '%s_rules%s.mk' % (spec['target_name'], options.suffix)
  mk_file = gyp.common.WriteOnDiff(os.path.join(output_dir, filename))
  # Find cygwin style versions of some paths.
  mk_file.write('OutDirCygwin:=$(shell cygpath -u "$(OutDir)")\n')
  mk_file.write('IntDirCygwin:=$(shell cygpath -u "$(IntDir)")\n')
  # Gather stuff needed to emit all: target.
  all_inputs = set()
  all_outputs = set()
  all_output_dirs = set()
  first_outputs = []
  for rule in rules:
    trigger_files = _FindRuleTriggerFiles(rule, sources)
    for tf in trigger_files:
      inputs, outputs = _RuleInputsAndOutputs(rule, tf)
      all_inputs.update(set(inputs))
      all_outputs.update(set(outputs))
      # Only use one target from each rule as the dependency for
      # 'all' so we don't try to build each rule multiple times.
      first_outputs.append(list(outputs)[0])
      # Get the unique output directories for this rule.
      output_dirs = [os.path.split(i)[0] for i in outputs]
      for od in output_dirs:
        all_output_dirs.add(od)
  first_outputs_cyg = [_Cygwinify(i) for i in first_outputs]
  # Write out all: target, including mkdir for each output directory.
  mk_file.write('all: %s\n' % ' '.join(first_outputs_cyg))
  for od in all_output_dirs:
    if od:
      mk_file.write('\tmkdir -p `cygpath -u "%s"`\n' % od)
  mk_file.write('\n')
  # Define how each output is generated.
  for rule in rules:
    trigger_files = _FindRuleTriggerFiles(rule, sources)
    for tf in trigger_files:
      # Get all the inputs and outputs for this rule for this trigger file.
      inputs, outputs = _RuleInputsAndOutputs(rule, tf)
      inputs = [_Cygwinify(i) for i in inputs]
      outputs = [_Cygwinify(i) for i in outputs]
      # Prepare the command line for this rule.
      cmd = [_RuleExpandPath(c, tf) for c in rule['action']]
      cmd = ['"%s"' % i for i in cmd]
      cmd = ' '.join(cmd)
      # Add it to the makefile.
      mk_file.write('%s: %s\n' % (' '.join(outputs), ' '.join(inputs)))
      mk_file.write('\t%s\n\n' % cmd)
  # Close up the file.
  mk_file.close()

  # Add makefile to list of sources.
  sources.add(filename)
  # Add a build action to call makefile.
  cmd = ['make',
         'OutDir=$(OutDir)',
         'IntDir=$(IntDir)',
         '-j', '${NUMBER_OF_PROCESSORS_PLUS_1}',
         '-f', filename]
  cmd = _BuildCommandLineForRuleRaw(spec, cmd, True, False, True, True)
  # Insert makefile as 0'th input, so it gets the action attached there,
  # as this is easier to understand from in the IDE.
  all_inputs = list(all_inputs)
  all_inputs.insert(0, filename)
  _AddActionStep(actions_to_add,
                 inputs=_FixPaths(all_inputs),
                 outputs=_FixPaths(all_outputs),
                 description='Running external rules for %s' %
                     spec['target_name'],
                 command=cmd)


def _EscapeEnvironmentVariableExpansion(s):
  """Escapes % characters.

  Escapes any % characters so that Windows-style environment variable
  expansions will leave them alone.
  See http://connect.microsoft.com/VisualStudio/feedback/details/106127/cl-d-name-text-containing-percentage-characters-doesnt-compile
  to understand why we have to do this.

  Args:
      s: The string to be escaped.

  Returns:
      The escaped string.
  """
  s = s.replace('%', '%%')
  return s


quote_replacer_regex = re.compile(r'(\\*)"')


def _EscapeCommandLineArgumentForMSVS(s):
  """Escapes a Windows command-line argument.

  So that the Win32 CommandLineToArgv function will turn the escaped result back
  into the original string.
  See http://msdn.microsoft.com/en-us/library/17w5ykft.aspx
  ("Parsing C++ Command-Line Arguments") to understand why we have to do
  this.

  Args:
      s: the string to be escaped.
  Returns:
      the escaped string.
  """

  def _Replace(match):
    # For a literal quote, CommandLineToArgv requires an odd number of
    # backslashes preceding it, and it produces half as many literal backslashes
    # (rounded down). So we need to produce 2n+1 backslashes.
    return 2 * match.group(1) + '\\"'

  # Escape all quotes so that they are interpreted literally.
  s = quote_replacer_regex.sub(_Replace, s)
  # Now add unescaped quotes so that any whitespace is interpreted literally.
  s = '"' + s + '"'
  return s


delimiters_replacer_regex = re.compile(r'(\\*)([,;]+)')


def _EscapeVCProjCommandLineArgListItem(s):
  """Escapes command line arguments for MSVS.

  The VCProj format stores string lists in a single string using commas and
  semi-colons as separators, which must be quoted if they are to be
  interpreted literally. However, command-line arguments may already have
  quotes, and the VCProj parser is ignorant of the backslash escaping
  convention used by CommandLineToArgv, so the command-line quotes and the
  VCProj quotes may not be the same quotes. So to store a general
  command-line argument in a VCProj list, we need to parse the existing
  quoting according to VCProj's convention and quote any delimiters that are
  not already quoted by that convention. The quotes that we add will also be
  seen by CommandLineToArgv, so if backslashes precede them then we also have
  to escape those backslashes according to the CommandLineToArgv
  convention.

  Args:
      s: the string to be escaped.
  Returns:
      the escaped string.
  """

  def _Replace(match):
    # For a non-literal quote, CommandLineToArgv requires an even number of
    # backslashes preceding it, and it produces half as many literal
    # backslashes. So we need to produce 2n backslashes.
    return 2 * match.group(1) + '"' + match.group(2) + '"'

  segments = s.split('"')
  # The unquoted segments are at the even-numbered indices.
  for i in range(0, len(segments), 2):
    segments[i] = delimiters_replacer_regex.sub(_Replace, segments[i])
  # Concatenate back into a single string
  s = '"'.join(segments)
  if len(segments) % 2 == 0:
    # String ends while still quoted according to VCProj's convention. This
    # means the delimiter and the next list item that follow this one in the
    # .vcproj file will be misinterpreted as part of this item. There is nothing
    # we can do about this. Adding an extra quote would correct the problem in
    # the VCProj but cause the same problem on the final command-line. Moving
    # the item to the end of the list does works, but that's only possible if
    # there's only one such item. Let's just warn the user.
    print >> sys.stderr, ('Warning: MSVS may misinterpret the odd number of ' +
                          'quotes in ' + s)
  return s


def _EscapeCppDefineForMSVS(s):
  """Escapes a CPP define so that it will reach the compiler unaltered."""
  s = _EscapeEnvironmentVariableExpansion(s)
  s = _EscapeCommandLineArgumentForMSVS(s)
  s = _EscapeVCProjCommandLineArgListItem(s)
  # cl.exe replaces literal # characters with = in preprocesor definitions for
  # some reason. Octal-encode to work around that.
  s = s.replace('#', '\\%03o' % ord('#'))
  return s


quote_replacer_regex2 = re.compile(r'(\\+)"')


def _EscapeCommandLineArgumentForMSBuild(s):
  """Escapes a Windows command-line argument for use by MSBuild."""

  def _Replace(match):
    return (len(match.group(1))/2*4)*'\\' + '\\"'

  # Escape all quotes so that they are interpreted literally.
  s = quote_replacer_regex2.sub(_Replace, s)
  return s


def _EscapeMSBuildSpecialCharacters(s):
  escape_dictionary = {
      '%': '%25',
      '$': '%24',
      '@': '%40',
      "'": '%27',
      ';': '%3B',
      '?': '%3F',
      '*': '%2A'
      }
  result = ''.join([escape_dictionary.get(c, c) for c in s])
  return result


def _EscapeCppDefineForMSBuild(s):
  """Escapes a CPP define so that it will reach the compiler unaltered."""
  s = _EscapeEnvironmentVariableExpansion(s)
  s = _EscapeCommandLineArgumentForMSBuild(s)
  s = _EscapeMSBuildSpecialCharacters(s)
  # cl.exe replaces literal # characters with = in preprocesor definitions for
  # some reason. Octal-encode to work around that.
  s = s.replace('#', '\\%03o' % ord('#'))
  return s


def _GenerateRulesForMSVS(p, output_dir, options, spec,
                          sources, excluded_sources,
                          actions_to_add):
  """Generate all the rules for a particular project.

  Arguments:
    p: the project
    output_dir: directory to emit rules to
    options: global options passed to the generator
    spec: the specification for this project
    sources: the set of all known source files in this project
    excluded_sources: the set of sources excluded from normal processing
    actions_to_add: deferred list of actions to add in
  """
  rules = spec.get('rules', [])
  rules_native = [r for r in rules if not int(r.get('msvs_external_rule', 0))]
  rules_external = [r for r in rules if int(r.get('msvs_external_rule', 0))]

  # Handle rules that use a native rules file.
  if rules_native:
    _GenerateNativeRulesForMSVS(p, rules_native, output_dir, spec, options)

  # Handle external rules (non-native rules).
  if rules_external:
    _GenerateExternalRules(rules_external, output_dir, spec,
                           sources, options, actions_to_add)
  _AdjustSourcesForRules(rules, sources, excluded_sources)


def _AdjustSourcesForRules(rules, sources, excluded_sources):
  # Add outputs generated by each rule (if applicable).
  for rule in rules:
    # Done if not processing outputs as sources.
    if int(rule.get('process_outputs_as_sources', False)):
      # Add in the outputs from this rule.
      trigger_files = _FindRuleTriggerFiles(rule, sources)
      for trigger_file in trigger_files:
        inputs, outputs = _RuleInputsAndOutputs(rule, trigger_file)
        inputs = set(_FixPaths(inputs))
        outputs = set(_FixPaths(outputs))
        inputs.remove(_FixPath(trigger_file))
        sources.update(inputs)
        excluded_sources.update(inputs)
        sources.update(outputs)


def _FilterActionsFromExcluded(excluded_sources, actions_to_add):
  """Take inputs with actions attached out of the list of exclusions.

  Arguments:
    excluded_sources: list of source files not to be built.
    actions_to_add: dict of actions keyed on source file they're attached to.
  Returns:
    excluded_sources with files that have actions attached removed.
  """
  must_keep = set(_FixPaths(actions_to_add.keys()))
  return [s for s in excluded_sources if s not in must_keep]


def _GetDefaultConfiguration(spec):
  return spec['configurations'][spec['default_configuration']]


def _GetGuidOfProject(proj_path, spec):
  """Get the guid for the project.

  Arguments:
    proj_path: Path of the vcproj or vcxproj file to generate.
    spec: The target dictionary containing the properties of the target.
  Returns:
    the guid.
  Raises:
    ValueError: if the specified GUID is invalid.
  """
  # Pluck out the default configuration.
  default_config = _GetDefaultConfiguration(spec)
  # Decide the guid of the project.
  guid = default_config.get('msvs_guid')
  if guid:
    if VALID_MSVS_GUID_CHARS.match(guid) is None:
      raise ValueError('Invalid MSVS guid: "%s".  Must match regex: "%s".' %
                       (guid, VALID_MSVS_GUID_CHARS.pattern))
    guid = '{%s}' % guid
  guid = guid or MSVSNew.MakeGuid(proj_path)
  return guid


def _GetMsbuildToolsetOfProject(proj_path, spec, version):
  """Get the platform toolset for the project.

  Arguments:
    proj_path: Path of the vcproj or vcxproj file to generate.
    spec: The target dictionary containing the properties of the target.
    version: The MSVSVersion object.
  Returns:
    the platform toolset string or None.
  """
  # Pluck out the default configuration.
  default_config = _GetDefaultConfiguration(spec)
  toolset = default_config.get('msbuild_toolset')
  if not toolset and version.DefaultToolset():
    toolset = version.DefaultToolset()
  return toolset


def _GenerateProject(project, options, version, generator_flags):
  """Generates a vcproj file.

  Arguments:
    project: the MSVSProject object.
    options: global generator options.
    version: the MSVSVersion object.
    generator_flags: dict of generator-specific flags.
  Returns:
    A list of source files that cannot be found on disk.
  """
  default_config = _GetDefaultConfiguration(project.spec)

  # Skip emitting anything if told to with msvs_existing_vcproj option.
  if default_config.get('msvs_existing_vcproj'):
    return []

  if version.UsesVcxproj():
    return _GenerateMSBuildProject(project, options, version, generator_flags)
  else:
    return _GenerateMSVSProject(project, options, version, generator_flags)


def _GenerateMSVSProject(project, options, version, generator_flags):
  """Generates a .vcproj file.  It may create .rules and .user files too.

  Arguments:
    project: The project object we will generate the file for.
    options: Global options passed to the generator.
    version: The VisualStudioVersion object.
    generator_flags: dict of generator-specific flags.
  """
  spec = project.spec
  vcproj_dir = os.path.dirname(project.path)
  if vcproj_dir and not os.path.exists(vcproj_dir):
    os.makedirs(vcproj_dir)

  platforms = _GetUniquePlatforms(spec)
  p = MSVSProject.Writer(project.path, version, spec['target_name'],
                         project.guid, platforms)

  # Get directory project file is in.
  project_dir = os.path.split(project.path)[0]
  gyp_path = _NormalizedSource(project.build_file)
  relative_path_of_gyp_file = gyp.common.RelativePath(gyp_path, project_dir)

  config_type = _GetMSVSConfigurationType(spec, project.build_file)
  for config_name, config in spec['configurations'].iteritems():
    _AddConfigurationToMSVSProject(p, spec, config_type, config_name, config)

  # Prepare list of sources and excluded sources.
  gyp_file = os.path.split(project.build_file)[1]
  sources, excluded_sources = _PrepareListOfSources(spec, generator_flags,
                                                    gyp_file)

  # Add rules.
  actions_to_add = {}
  _GenerateRulesForMSVS(p, project_dir, options, spec,
                        sources, excluded_sources,
                        actions_to_add)
  list_excluded = generator_flags.get('msvs_list_excluded_files', True)
  sources, excluded_sources, excluded_idl = (
      _AdjustSourcesAndConvertToFilterHierarchy(
          spec, options, project_dir, sources, excluded_sources, list_excluded))

  # Add in files.
  missing_sources = _VerifySourcesExist(sources, project_dir)
  p.AddFiles(sources)

  _AddToolFilesToMSVS(p, spec)
  _HandlePreCompiledHeaders(p, sources, spec)
  _AddActions(actions_to_add, spec, relative_path_of_gyp_file)
  _AddCopies(actions_to_add, spec)
  _WriteMSVSUserFile(project.path, version, spec)

  # NOTE: this stanza must appear after all actions have been decided.
  # Don't excluded sources with actions attached, or they won't run.
  excluded_sources = _FilterActionsFromExcluded(
      excluded_sources, actions_to_add)
  _ExcludeFilesFromBeingBuilt(p, spec, excluded_sources, excluded_idl,
                              list_excluded)
  _AddAccumulatedActionsToMSVS(p, spec, actions_to_add)

  # Write it out.
  p.WriteIfChanged()

  return missing_sources


def _GetUniquePlatforms(spec):
  """Returns the list of unique platforms for this spec, e.g ['win32', ...].

  Arguments:
    spec: The target dictionary containing the properties of the target.
  Returns:
    The MSVSUserFile object created.
  """
  # Gather list of unique platforms.
  platforms = set()
  for configuration in spec['configurations']:
    platforms.add(_ConfigPlatform(spec['configurations'][configuration]))
  platforms = list(platforms)
  return platforms


def _CreateMSVSUserFile(proj_path, version, spec):
  """Generates a .user file for the user running this Gyp program.

  Arguments:
    proj_path: The path of the project file being created.  The .user file
               shares the same path (with an appropriate suffix).
    version: The VisualStudioVersion object.
    spec: The target dictionary containing the properties of the target.
  Returns:
    The MSVSUserFile object created.
  """
  (domain, username) = _GetDomainAndUserName()
  vcuser_filename = '.'.join([proj_path, domain, username, 'user'])
  user_file = MSVSUserFile.Writer(vcuser_filename, version,
                                  spec['target_name'])
  return user_file


def _GetMSVSConfigurationType(spec, build_file):
  """Returns the configuration type for this project.

  It's a number defined by Microsoft.  May raise an exception.

  Args:
      spec: The target dictionary containing the properties of the target.
      build_file: The path of the gyp file.
  Returns:
      An integer, the configuration type.
  """
  try:
    config_type = {
        'executable': '1',  # .exe
        'shared_library': '2',  # .dll
        'loadable_module': '2',  # .dll
        'static_library': '4',  # .lib
        'none': '10',  # Utility type
        }[spec['type']]
  except KeyError:
    if spec.get('type'):
      raise Exception('Target type %s is not a valid target type for '
                      'target %s in %s.' %
                      (spec['type'], spec['target_name'], build_file))
    else:
      raise Exception('Missing type field for target %s in %s.' %
                      (spec['target_name'], build_file))
  return config_type


def _AddConfigurationToMSVSProject(p, spec, config_type, config_name, config):
  """Adds a configuration to the MSVS project.

  Many settings in a vcproj file are specific to a configuration.  This
  function the main part of the vcproj file that's configuration specific.

  Arguments:
    p: The target project being generated.
    spec: The target dictionary containing the properties of the target.
    config_type: The configuration type, a number as defined by Microsoft.
    config_name: The name of the configuration.
    config: The dictionnary that defines the special processing to be done
            for this configuration.
  """
  # Get the information for this configuration
  include_dirs, resource_include_dirs = _GetIncludeDirs(config)
  libraries = _GetLibraries(spec)
  out_file, vc_tool, _ = _GetOutputFilePathAndTool(spec, msbuild=False)
  defines = _GetDefines(config)
  defines = [_EscapeCppDefineForMSVS(d) for d in defines]
  disabled_warnings = _GetDisabledWarnings(config)
  prebuild = config.get('msvs_prebuild')
  postbuild = config.get('msvs_postbuild')
  def_file = _GetModuleDefinition(spec)
  precompiled_header = config.get('msvs_precompiled_header')

  # Prepare the list of tools as a dictionary.
  tools = dict()
  # Add in user specified msvs_settings.
  msvs_settings = config.get('msvs_settings', {})
  MSVSSettings.ValidateMSVSSettings(msvs_settings)
  for tool in msvs_settings:
    settings = config['msvs_settings'][tool]
    for setting in settings:
      _ToolAppend(tools, tool, setting, settings[setting])
  # Add the information to the appropriate tool
  _ToolAppend(tools, 'VCCLCompilerTool',
              'AdditionalIncludeDirectories', include_dirs)
  _ToolAppend(tools, 'VCResourceCompilerTool',
              'AdditionalIncludeDirectories', resource_include_dirs)
  # Add in libraries.
  _ToolAppend(tools, 'VCLinkerTool', 'AdditionalDependencies', libraries)
  if out_file:
    _ToolAppend(tools, vc_tool, 'OutputFile', out_file, only_if_unset=True)
  # Add defines.
  _ToolAppend(tools, 'VCCLCompilerTool', 'PreprocessorDefinitions', defines)
  _ToolAppend(tools, 'VCResourceCompilerTool', 'PreprocessorDefinitions',
              defines)
  # Change program database directory to prevent collisions.
  _ToolAppend(tools, 'VCCLCompilerTool', 'ProgramDataBaseFileName',
              '$(IntDir)$(ProjectName)\\vc80.pdb', only_if_unset=True)
  # Add disabled warnings.
  _ToolAppend(tools, 'VCCLCompilerTool',
              'DisableSpecificWarnings', disabled_warnings)
  # Add Pre-build.
  _ToolAppend(tools, 'VCPreBuildEventTool', 'CommandLine', prebuild)
  # Add Post-build.
  _ToolAppend(tools, 'VCPostBuildEventTool', 'CommandLine', postbuild)
  # Turn on precompiled headers if appropriate.
  if precompiled_header:
    precompiled_header = os.path.split(precompiled_header)[1]
    _ToolAppend(tools, 'VCCLCompilerTool', 'UsePrecompiledHeader', '2')
    _ToolAppend(tools, 'VCCLCompilerTool',
                'PrecompiledHeaderThrough', precompiled_header)
    _ToolAppend(tools, 'VCCLCompilerTool',
                'ForcedIncludeFiles', precompiled_header)
  # Loadable modules don't generate import libraries;
  # tell dependent projects to not expect one.
  if spec['type'] == 'loadable_module':
    _ToolAppend(tools, 'VCLinkerTool', 'IgnoreImportLibrary', 'true')
  # Set the module definition file if any.
  if def_file:
    _ToolAppend(tools, 'VCLinkerTool', 'ModuleDefinitionFile', def_file)

  _AddConfigurationToMSVS(p, spec, tools, config, config_type, config_name)


def _GetIncludeDirs(config):
  """Returns the list of directories to be used for #include directives.

  Arguments:
    config: The dictionnary that defines the special processing to be done
            for this configuration.
  Returns:
    The list of directory paths.
  """
  # TODO(bradnelson): include_dirs should really be flexible enough not to
  #                   require this sort of thing.
  include_dirs = (
      config.get('include_dirs', []) +
      config.get('msvs_system_include_dirs', []))
  resource_include_dirs = config.get('resource_include_dirs', include_dirs)
  include_dirs = _FixPaths(include_dirs)
  resource_include_dirs = _FixPaths(resource_include_dirs)
  return include_dirs, resource_include_dirs


def _GetLibraries(spec):
  """Returns the list of libraries for this configuration.

  Arguments:
    spec: The target dictionary containing the properties of the target.
  Returns:
    The list of directory paths.
  """
  libraries = spec.get('libraries', [])
  # Strip out -l, as it is not used on windows (but is needed so we can pass
  # in libraries that are assumed to be in the default library path).
  # Also remove duplicate entries, leaving only the last duplicate, while
  # preserving order.
  found = set()
  unique_libraries_list = []
  for entry in reversed(libraries):
    library = re.sub('^\-l', '', entry)
    if not os.path.splitext(library)[1]:
      library += '.lib'
    if library not in found:
      found.add(library)
      unique_libraries_list.append(library)
  unique_libraries_list.reverse()
  return unique_libraries_list


def _GetOutputFilePathAndTool(spec, msbuild):
  """Returns the path and tool to use for this target.

  Figures out the path of the file this spec will create and the name of
  the VC tool that will create it.

  Arguments:
    spec: The target dictionary containing the properties of the target.
  Returns:
    A triple of (file path, name of the vc tool, name of the msbuild tool)
  """
  # Select a name for the output file.
  out_file = ''
  vc_tool = ''
  msbuild_tool = ''
  output_file_map = {
      'executable': ('VCLinkerTool', 'Link', '$(OutDir)', '.exe'),
      'shared_library': ('VCLinkerTool', 'Link', '$(OutDir)', '.dll'),
      'loadable_module': ('VCLinkerTool', 'Link', '$(OutDir)', '.dll'),
      'static_library': ('VCLibrarianTool', 'Lib', '$(OutDir)lib\\', '.lib'),
  }
  output_file_props = output_file_map.get(spec['type'])
  if output_file_props and int(spec.get('msvs_auto_output_file', 1)):
    vc_tool, msbuild_tool, out_dir, suffix = output_file_props
    if spec.get('standalone_static_library', 0):
      out_dir = '$(OutDir)'
    out_dir = spec.get('product_dir', out_dir)
    product_extension = spec.get('product_extension')
    if product_extension:
      suffix = '.' + product_extension
    elif msbuild:
      suffix = '$(TargetExt)'
    prefix = spec.get('product_prefix', '')
    product_name = spec.get('product_name', '$(ProjectName)')
    out_file = ntpath.join(out_dir, prefix + product_name + suffix)
  return out_file, vc_tool, msbuild_tool


def _GetDefines(config):
  """Returns the list of preprocessor definitions for this configuation.

  Arguments:
    config: The dictionnary that defines the special processing to be done
            for this configuration.
  Returns:
    The list of preprocessor definitions.
  """
  defines = []
  for d in config.get('defines', []):
    if type(d) == list:
      fd = '='.join([str(dpart) for dpart in d])
    else:
      fd = str(d)
    defines.append(fd)
  return defines


def _GetDisabledWarnings(config):
  return [str(i) for i in config.get('msvs_disabled_warnings', [])]


def _GetModuleDefinition(spec):
  def_file = ''
  if spec['type'] in ['shared_library', 'loadable_module', 'executable']:
    def_files = [s for s in spec.get('sources', []) if s.endswith('.def')]
    if len(def_files) == 1:
      def_file = _FixPath(def_files[0])
    elif def_files:
      raise ValueError(
          'Multiple module definition files in one target, target %s lists '
          'multiple .def files: %s' % (
              spec['target_name'], ' '.join(def_files)))
  return def_file


def _ConvertToolsToExpectedForm(tools):
  """Convert tools to a form expected by Visual Studio.

  Arguments:
    tools: A dictionnary of settings; the tool name is the key.
  Returns:
    A list of Tool objects.
  """
  tool_list = []
  for tool, settings in tools.iteritems():
    # Collapse settings with lists.
    settings_fixed = {}
    for setting, value in settings.iteritems():
      if type(value) == list:
        if ((tool == 'VCLinkerTool' and
             setting == 'AdditionalDependencies') or
            setting == 'AdditionalOptions'):
          settings_fixed[setting] = ' '.join(value)
        else:
          settings_fixed[setting] = ';'.join(value)
      else:
        settings_fixed[setting] = value
    # Add in this tool.
    tool_list.append(MSVSProject.Tool(tool, settings_fixed))
  return tool_list


def _AddConfigurationToMSVS(p, spec, tools, config, config_type, config_name):
  """Add to the project file the configuration specified by config.

  Arguments:
    p: The target project being generated.
    spec: the target project dict.
    tools: A dictionnary of settings; the tool name is the key.
    config: The dictionnary that defines the special processing to be done
            for this configuration.
    config_type: The configuration type, a number as defined by Microsoft.
    config_name: The name of the configuration.
  """
  attributes = _GetMSVSAttributes(spec, config, config_type)
  # Add in this configuration.
  tool_list = _ConvertToolsToExpectedForm(tools)
  p.AddConfig(_ConfigFullName(config_name, config),
              attrs=attributes, tools=tool_list)


def _GetMSVSAttributes(spec, config, config_type):
  # Prepare configuration attributes.
  prepared_attrs = {}
  source_attrs = config.get('msvs_configuration_attributes', {})
  for a in source_attrs:
    prepared_attrs[a] = source_attrs[a]
  # Add props files.
  vsprops_dirs = config.get('msvs_props', [])
  vsprops_dirs = _FixPaths(vsprops_dirs)
  if vsprops_dirs:
    prepared_attrs['InheritedPropertySheets'] = ';'.join(vsprops_dirs)
  # Set configuration type.
  prepared_attrs['ConfigurationType'] = config_type
  output_dir = prepared_attrs.get('OutputDirectory',
                                  '$(SolutionDir)$(ConfigurationName)')
  prepared_attrs['OutputDirectory'] = _FixPath(output_dir) + '\\'
  if 'IntermediateDirectory' not in prepared_attrs:
    intermediate = '$(ConfigurationName)\\obj\\$(ProjectName)'
    prepared_attrs['IntermediateDirectory'] = _FixPath(intermediate) + '\\'
  else:
    intermediate = _FixPath(prepared_attrs['IntermediateDirectory']) + '\\'
    intermediate = MSVSSettings.FixVCMacroSlashes(intermediate)
    prepared_attrs['IntermediateDirectory'] = intermediate
  return prepared_attrs


def _AddNormalizedSources(sources_set, sources_array):
  sources = [_NormalizedSource(s) for s in sources_array]
  sources_set.update(set(sources))


def _PrepareListOfSources(spec, generator_flags, gyp_file):
  """Prepare list of sources and excluded sources.

  Besides the sources specified directly in the spec, adds the gyp file so
  that a change to it will cause a re-compile. Also adds appropriate sources
  for actions and copies. Assumes later stage will un-exclude files which
  have custom build steps attached.

  Arguments:
    spec: The target dictionary containing the properties of the target.
    gyp_file: The name of the gyp file.
  Returns:
    A pair of (list of sources, list of excluded sources).
    The sources will be relative to the gyp file.
  """
  sources = set()
  _AddNormalizedSources(sources, spec.get('sources', []))
  excluded_sources = set()
  # Add in the gyp file.
  if not generator_flags.get('standalone'):
    sources.add(gyp_file)

  # Add in 'action' inputs and outputs.
  for a in spec.get('actions', []):
    inputs = a['inputs']
    inputs = [_NormalizedSource(i) for i in inputs]
    # Add all inputs to sources and excluded sources.
    inputs = set(inputs)
    sources.update(inputs)
    excluded_sources.update(inputs)
    if int(a.get('process_outputs_as_sources', False)):
      _AddNormalizedSources(sources, a.get('outputs', []))
  # Add in 'copies' inputs and outputs.
  for cpy in spec.get('copies', []):
    _AddNormalizedSources(sources, cpy.get('files', []))
  return (sources, excluded_sources)


def _AdjustSourcesAndConvertToFilterHierarchy(
    spec, options, gyp_dir, sources, excluded_sources, list_excluded):
  """Adjusts the list of sources and excluded sources.

  Also converts the sets to lists.

  Arguments:
    spec: The target dictionary containing the properties of the target.
    options: Global generator options.
    gyp_dir: The path to the gyp file being processed.
    sources: A set of sources to be included for this project.
    excluded_sources: A set of sources to be excluded for this project.
  Returns:
    A trio of (list of sources, list of excluded sources,
               path of excluded IDL file)
  """
  # Exclude excluded sources coming into the generator.
  excluded_sources.update(set(spec.get('sources_excluded', [])))
  # Add excluded sources into sources for good measure.
  sources.update(excluded_sources)
  # Convert to proper windows form.
  # NOTE: sources goes from being a set to a list here.
  # NOTE: excluded_sources goes from being a set to a list here.
  sources = _FixPaths(sources)
  # Convert to proper windows form.
  excluded_sources = _FixPaths(excluded_sources)

  excluded_idl = _IdlFilesHandledNonNatively(spec, sources)

  precompiled_related = _GetPrecompileRelatedFiles(spec)
  # Find the excluded ones, minus the precompiled header related ones.
  fully_excluded = [i for i in excluded_sources if i not in precompiled_related]

  # Convert to folders and the right slashes.
  sources = [i.split('\\') for i in sources]
  sources = _ConvertSourcesToFilterHierarchy(sources, excluded=fully_excluded,
                                             list_excluded=list_excluded)

  return sources, excluded_sources, excluded_idl


def _IdlFilesHandledNonNatively(spec, sources):
  # If any non-native rules use 'idl' as an extension exclude idl files.
  # Gather a list here to use later.
  using_idl = False
  for rule in spec.get('rules', []):
    if rule['extension'] == 'idl' and int(rule.get('msvs_external_rule', 0)):
      using_idl = True
      break
  if using_idl:
    excluded_idl = [i for i in sources if i.endswith('.idl')]
  else:
    excluded_idl = []
  return excluded_idl


def _GetPrecompileRelatedFiles(spec):
  # Gather a list of precompiled header related sources.
  precompiled_related = []
  for _, config in spec['configurations'].iteritems():
    for k in precomp_keys:
      f = config.get(k)
      if f:
        precompiled_related.append(_FixPath(f))
  return precompiled_related


def _ExcludeFilesFromBeingBuilt(p, spec, excluded_sources, excluded_idl,
                                list_excluded):
  exclusions = _GetExcludedFilesFromBuild(spec, excluded_sources, excluded_idl)
  for file_name, excluded_configs in exclusions.iteritems():
    if (not list_excluded and
            len(excluded_configs) == len(spec['configurations'])):
      # If we're not listing excluded files, then they won't appear in the
      # project, so don't try to configure them to be excluded.
      pass
    else:
      for config_name, config in excluded_configs:
        p.AddFileConfig(file_name, _ConfigFullName(config_name, config),
                        {'ExcludedFromBuild': 'true'})


def _GetExcludedFilesFromBuild(spec, excluded_sources, excluded_idl):
  exclusions = {}
  # Exclude excluded sources from being built.
  for f in excluded_sources:
    excluded_configs = []
    for config_name, config in spec['configurations'].iteritems():
      precomped = [_FixPath(config.get(i, '')) for i in precomp_keys]
      # Don't do this for ones that are precompiled header related.
      if f not in precomped:
        excluded_configs.append((config_name, config))
    exclusions[f] = excluded_configs
  # If any non-native rules use 'idl' as an extension exclude idl files.
  # Exclude them now.
  for f in excluded_idl:
    excluded_configs = []
    for config_name, config in spec['configurations'].iteritems():
      excluded_configs.append((config_name, config))
    exclusions[f] = excluded_configs
  return exclusions


def _AddToolFilesToMSVS(p, spec):
  # Add in tool files (rules).
  tool_files = set()
  for _, config in spec['configurations'].iteritems():
    for f in config.get('msvs_tool_files', []):
      tool_files.add(f)
  for f in tool_files:
    p.AddToolFile(f)


def _HandlePreCompiledHeaders(p, sources, spec):
  # Pre-compiled header source stubs need a different compiler flag
  # (generate precompiled header) and any source file not of the same
  # kind (i.e. C vs. C++) as the precompiled header source stub needs
  # to have use of precompiled headers disabled.
  extensions_excluded_from_precompile = []
  for config_name, config in spec['configurations'].iteritems():
    source = config.get('msvs_precompiled_source')
    if source:
      source = _FixPath(source)
      # UsePrecompiledHeader=1 for if using precompiled headers.
      tool = MSVSProject.Tool('VCCLCompilerTool',
                              {'UsePrecompiledHeader': '1'})
      p.AddFileConfig(source, _ConfigFullName(config_name, config),
                      {}, tools=[tool])
      basename, extension = os.path.splitext(source)
      if extension == '.c':
        extensions_excluded_from_precompile = ['.cc', '.cpp', '.cxx']
      else:
        extensions_excluded_from_precompile = ['.c']
  def DisableForSourceTree(source_tree):
    for source in source_tree:
      if isinstance(source, MSVSProject.Filter):
        DisableForSourceTree(source.contents)
      else:
        basename, extension = os.path.splitext(source)
        if extension in extensions_excluded_from_precompile:
          for config_name, config in spec['configurations'].iteritems():
            tool = MSVSProject.Tool('VCCLCompilerTool',
                                    {'UsePrecompiledHeader': '0',
                                     'ForcedIncludeFiles': '$(NOINHERIT)'})
            p.AddFileConfig(_FixPath(source),
                            _ConfigFullName(config_name, config),
                            {}, tools=[tool])
  # Do nothing if there was no precompiled source.
  if extensions_excluded_from_precompile:
    DisableForSourceTree(sources)


def _AddActions(actions_to_add, spec, relative_path_of_gyp_file):
  # Add actions.
  actions = spec.get('actions', [])
  # Don't setup_env every time. When all the actions are run together in one
  # batch file in VS, the PATH will grow too long.
  # Membership in this set means that the cygwin environment has been set up,
  # and does not need to be set up again.
  have_setup_env = set()
  for a in actions:
    # Attach actions to the gyp file if nothing else is there.
    inputs = a.get('inputs') or [relative_path_of_gyp_file]
    attached_to = inputs[0]
    need_setup_env = attached_to not in have_setup_env
    cmd = _BuildCommandLineForRule(spec, a, has_input_path=False,
                                   do_setup_env=need_setup_env)
    have_setup_env.add(attached_to)
    # Add the action.
    _AddActionStep(actions_to_add,
                   inputs=inputs,
                   outputs=a.get('outputs', []),
                   description=a.get('message', a['action_name']),
                   command=cmd)


def _WriteMSVSUserFile(project_path, version, spec):
  # Add run_as and test targets.
  if 'run_as' in spec:
    run_as = spec['run_as']
    action = run_as.get('action', [])
    environment = run_as.get('environment', [])
    working_directory = run_as.get('working_directory', '.')
  elif int(spec.get('test', 0)):
    action = ['$(TargetPath)', '--gtest_print_time']
    environment = []
    working_directory = '.'
  else:
    return  # Nothing to add
  # Write out the user file.
  user_file = _CreateMSVSUserFile(project_path, version, spec)
  for config_name, c_data in spec['configurations'].iteritems():
    user_file.AddDebugSettings(_ConfigFullName(config_name, c_data),
                               action, environment, working_directory)
  user_file.WriteIfChanged()


def _AddCopies(actions_to_add, spec):
  copies = _GetCopies(spec)
  for inputs, outputs, cmd, description in copies:
    _AddActionStep(actions_to_add, inputs=inputs, outputs=outputs,
                   description=description, command=cmd)


def _GetCopies(spec):
  copies = []
  # Add copies.
  for cpy in spec.get('copies', []):
    for src in cpy.get('files', []):
      dst = os.path.join(cpy['destination'], os.path.basename(src))
      # _AddCustomBuildToolForMSVS() will call _FixPath() on the inputs and
      # outputs, so do the same for our generated command line.
      if src.endswith('/'):
        src_bare = src[:-1]
        base_dir = posixpath.split(src_bare)[0]
        outer_dir = posixpath.split(src_bare)[1]
        cmd = 'xcopy /e /f /y "%s\\%s" "%s\\%s\\"' % (
            _FixPath(base_dir), outer_dir, _FixPath(dst), outer_dir)
        copies.append(([src], ['dummy_copies', dst], cmd,
                       'Copying %s to %s' % (src, dst)))
      else:
        cmd = 'mkdir "%s" 2>nul & set ERRORLEVEL=0 & copy /Y "%s" "%s"' % (
            _FixPath(cpy['destination']), _FixPath(src), _FixPath(dst))
        copies.append(([src], [dst], cmd, 'Copying %s to %s' % (src, dst)))
  return copies


def _GetPathDict(root, path):
  # |path| will eventually be empty (in the recursive calls) if it was initially
  # relative; otherwise it will eventually end up as '\', 'D:\', etc.
  if not path or path.endswith(os.sep):
    return root
  parent, folder = os.path.split(path)
  parent_dict = _GetPathDict(root, parent)
  if folder not in parent_dict:
    parent_dict[folder] = dict()
  return parent_dict[folder]


def _DictsToFolders(base_path, bucket, flat):
  # Convert to folders recursively.
  children = []
  for folder, contents in bucket.iteritems():
    if type(contents) == dict:
      folder_children = _DictsToFolders(os.path.join(base_path, folder),
                                        contents, flat)
      if flat:
        children += folder_children
      else:
        folder_children = MSVSNew.MSVSFolder(os.path.join(base_path, folder),
                                             name='(' + folder + ')',
                                             entries=folder_children)
        children.append(folder_children)
    else:
      children.append(contents)
  return children


def _CollapseSingles(parent, node):
  # Recursively explorer the tree of dicts looking for projects which are
  # the sole item in a folder which has the same name as the project. Bring
  # such projects up one level.
  if (type(node) == dict and
      len(node) == 1 and
      node.keys()[0] == parent + '.vcproj'):
    return node[node.keys()[0]]
  if type(node) != dict:
    return node
  for child in node:
    node[child] = _CollapseSingles(child, node[child])
  return node


def _GatherSolutionFolders(sln_projects, project_objects, flat):
  root = {}
  # Convert into a tree of dicts on path.
  for p in sln_projects:
    gyp_file, target = gyp.common.ParseQualifiedTarget(p)[0:2]
    gyp_dir = os.path.dirname(gyp_file)
    path_dict = _GetPathDict(root, gyp_dir)
    path_dict[target + '.vcproj'] = project_objects[p]
  # Walk down from the top until we hit a folder that has more than one entry.
  # In practice, this strips the top-level "src/" dir from the hierarchy in
  # the solution.
  while len(root) == 1 and type(root[root.keys()[0]]) == dict:
    root = root[root.keys()[0]]
  # Collapse singles.
  root = _CollapseSingles('', root)
  # Merge buckets until everything is a root entry.
  return _DictsToFolders('', root, flat)


def _GetPathOfProject(qualified_target, spec, options, msvs_version):
  default_config = _GetDefaultConfiguration(spec)
  proj_filename = default_config.get('msvs_existing_vcproj')
  if not proj_filename:
    proj_filename = (spec['target_name'] + options.suffix +
                     msvs_version.ProjectExtension())

  build_file = gyp.common.BuildFile(qualified_target)
  proj_path = os.path.join(os.path.dirname(build_file), proj_filename)
  fix_prefix = None
  if options.generator_output:
    project_dir_path = os.path.dirname(os.path.abspath(proj_path))
    proj_path = os.path.join(options.generator_output, proj_path)
    fix_prefix = gyp.common.RelativePath(project_dir_path,
                                         os.path.dirname(proj_path))
  return proj_path, fix_prefix


def _GetPlatformOverridesOfProject(spec):
  # Prepare a dict indicating which project configurations are used for which
  # solution configurations for this target.
  config_platform_overrides = {}
  for config_name, c in spec['configurations'].iteritems():
    config_fullname = _ConfigFullName(config_name, c)
    platform = c.get('msvs_target_platform', _ConfigPlatform(c))
    fixed_config_fullname = '%s|%s' % (
        _ConfigBaseName(config_name, _ConfigPlatform(c)), platform)
    config_platform_overrides[config_fullname] = fixed_config_fullname
  return config_platform_overrides


def _CreateProjectObjects(target_list, target_dicts, options, msvs_version):
  """Create a MSVSProject object for the targets found in target list.

  Arguments:
    target_list: the list of targets to generate project objects for.
    target_dicts: the dictionary of specifications.
    options: global generator options.
    msvs_version: the MSVSVersion object.
  Returns:
    A set of created projects, keyed by target.
  """
  global fixpath_prefix
  # Generate each project.
  projects = {}
  for qualified_target in target_list:
    spec = target_dicts[qualified_target]
    if spec['toolset'] != 'target':
      raise Exception(
          'Multiple toolsets not supported in msvs build (target %s)' %
          qualified_target)
    proj_path, fixpath_prefix = _GetPathOfProject(qualified_target, spec,
                                                  options, msvs_version)
    guid = _GetGuidOfProject(proj_path, spec)
    overrides = _GetPlatformOverridesOfProject(spec)
    build_file = gyp.common.BuildFile(qualified_target)
    # Create object for this project.
    obj = MSVSNew.MSVSProject(
        proj_path,
        name=spec['target_name'],
        guid=guid,
        spec=spec,
        build_file=build_file,
        config_platform_overrides=overrides,
        fixpath_prefix=fixpath_prefix)
    # Set project toolset if any (MS build only)
    if msvs_version.UsesVcxproj():
      obj.set_msbuild_toolset(
          _GetMsbuildToolsetOfProject(proj_path, spec, msvs_version))
    projects[qualified_target] = obj
  # Set all the dependencies
  for project in projects.values():
    deps = project.spec.get('dependencies', [])
    deps = [projects[d] for d in deps]
    project.set_dependencies(deps)
  return projects


def CalculateVariables(default_variables, params):
  """Generated variables that require params to be known."""

  generator_flags = params.get('generator_flags', {})

  # Select project file format version (if unset, default to auto detecting).
  msvs_version = MSVSVersion.SelectVisualStudioVersion(
      generator_flags.get('msvs_version', 'auto'))
  # Stash msvs_version for later (so we don't have to probe the system twice).
  params['msvs_version'] = msvs_version

  # Set a variable so conditions can be based on msvs_version.
  default_variables['MSVS_VERSION'] = msvs_version.ShortName()

  # To determine processor word size on Windows, in addition to checking
  # PROCESSOR_ARCHITECTURE (which reflects the word size of the current
  # process), it is also necessary to check PROCESSOR_ARCITEW6432 (which
  # contains the actual word size of the system when running thru WOW64).
  if (os.environ.get('PROCESSOR_ARCHITECTURE', '').find('64') >= 0 or
      os.environ.get('PROCESSOR_ARCHITEW6432', '').find('64') >= 0):
    default_variables['MSVS_OS_BITS'] = 64
  else:
    default_variables['MSVS_OS_BITS'] = 32


def _ShardName(name, number):
  """Add a shard number to the end of a target.

  Arguments:
    name: name of the target (foo#target)
    number: shard number
  Returns:
    Target name with shard added (foo_1#target)
  """
  parts = name.rsplit('#', 1)
  parts[0] = '%s_%d' % (parts[0], number)
  return '#'.join(parts)


def _ShardTargets(target_list, target_dicts):
  """Shard some targets apart to work around the linkers limits.

  Arguments:
    target_list: List of target pairs: 'base/base.gyp:base'.
    target_dicts: Dict of target properties keyed on target pair.
  Returns:
    Tuple of the new sharded versions of the inputs.
  """
  # Gather the targets to shard, and how many pieces.
  targets_to_shard = {}
  for t in target_dicts:
    shards = int(target_dicts[t].get('msvs_shard', 0))
    if shards:
      targets_to_shard[t] = shards
  # Shard target_list.
  new_target_list = []
  for t in target_list:
    if t in targets_to_shard:
      for i in range(targets_to_shard[t]):
        new_target_list.append(_ShardName(t, i))
    else:
      new_target_list.append(t)
  # Shard target_dict.
  new_target_dicts = {}
  for t in target_dicts:
    if t in targets_to_shard:
      for i in range(targets_to_shard[t]):
        name = _ShardName(t, i)
        new_target_dicts[name] = copy.copy(target_dicts[t])
        new_target_dicts[name]['target_name'] = _ShardName(
             new_target_dicts[name]['target_name'], i)
        sources = new_target_dicts[name].get('sources', [])
        new_sources = []
        for pos in range(i, len(sources), targets_to_shard[t]):
          new_sources.append(sources[pos])
        new_target_dicts[name]['sources'] = new_sources
    else:
      new_target_dicts[t] = target_dicts[t]
  # Shard dependencies.
  for t in new_target_dicts:
    dependencies = copy.copy(new_target_dicts[t].get('dependencies', []))
    new_dependencies = []
    for d in dependencies:
      if d in targets_to_shard:
        for i in range(targets_to_shard[d]):
          new_dependencies.append(_ShardName(d, i))
      else:
        new_dependencies.append(d)
    new_target_dicts[t]['dependencies'] = new_dependencies

  return (new_target_list, new_target_dicts)


def PerformBuild(data, configurations, params):
  options = params['options']
  msvs_version = params['msvs_version']
  devenv = os.path.join(msvs_version.path, 'Common7', 'IDE', 'devenv.com')

  for build_file, build_file_dict in data.iteritems():
    (build_file_root, build_file_ext) = os.path.splitext(build_file)
    if build_file_ext != '.gyp':
      continue
    sln_path = build_file_root + options.suffix + '.sln'
    if options.generator_output:
      sln_path = os.path.join(options.generator_output, sln_path)

  for config in configurations:
    arguments = [devenv, sln_path, '/Build', config]
    print 'Building [%s]: %s' % (config, arguments)
    rtn = subprocess.check_call(arguments)


def GenerateOutput(target_list, target_dicts, data, params):
  """Generate .sln and .vcproj files.

  This is the entry point for this generator.
  Arguments:
    target_list: List of target pairs: 'base/base.gyp:base'.
    target_dicts: Dict of target properties keyed on target pair.
    data: Dictionary containing per .gyp data.
  """
  global fixpath_prefix

  options = params['options']

  # Get the project file format version back out of where we stashed it in
  # GeneratorCalculatedVariables.
  msvs_version = params['msvs_version']

  generator_flags = params.get('generator_flags', {})

  # Optionally shard targets marked with 'msvs_shard': SHARD_COUNT.
  (target_list, target_dicts) = _ShardTargets(target_list, target_dicts)

  # Prepare the set of configurations.
  configs = set()
  for qualified_target in target_list:
    spec = target_dicts[qualified_target]
    for config_name, config in spec['configurations'].iteritems():
      configs.add(_ConfigFullName(config_name, config))
  configs = list(configs)

  # Figure out all the projects that will be generated and their guids
  project_objects = _CreateProjectObjects(target_list, target_dicts, options,
                                          msvs_version)

  # Generate each project.
  missing_sources = []
  for project in project_objects.values():
    fixpath_prefix = project.fixpath_prefix
    missing_sources.extend(_GenerateProject(project, options, msvs_version,
                                            generator_flags))
  fixpath_prefix = None

  for build_file in data:
    # Validate build_file extension
    if not build_file.endswith('.gyp'):
      continue
    sln_path = os.path.splitext(build_file)[0] + options.suffix + '.sln'
    if options.generator_output:
      sln_path = os.path.join(options.generator_output, sln_path)
    # Get projects in the solution, and their dependents.
    sln_projects = gyp.common.BuildFileTargets(target_list, build_file)
    sln_projects += gyp.common.DeepDependencyTargets(target_dicts, sln_projects)
    # Create folder hierarchy.
    root_entries = _GatherSolutionFolders(
        sln_projects, project_objects, flat=msvs_version.FlatSolution())
    # Create solution.
    sln = MSVSNew.MSVSSolution(sln_path,
                               entries=root_entries,
                               variants=configs,
                               websiteProperties=False,
                               version=msvs_version)
    sln.Write()

  if missing_sources:
    error_message = "Missing input files:\n" + \
                    '\n'.join(set(missing_sources))
    if generator_flags.get('msvs_error_on_missing_sources', False):
      raise Exception(error_message)
    else:
      print >>sys.stdout, "Warning: " + error_message


def _GenerateMSBuildFiltersFile(filters_path, source_files,
                                extension_to_rule_name):
  """Generate the filters file.

  This file is used by Visual Studio to organize the presentation of source
  files into folders.

  Arguments:
      filters_path: The path of the file to be created.
      source_files: The hierarchical structure of all the sources.
      extension_to_rule_name: A dictionary mapping file extensions to rules.
  """
  filter_group = []
  source_group = []
  _AppendFiltersForMSBuild('', source_files, extension_to_rule_name,
                           filter_group, source_group)
  if filter_group:
    content = ['Project',
               {'ToolsVersion': '4.0',
                'xmlns': 'http://schemas.microsoft.com/developer/msbuild/2003'
               },
               ['ItemGroup'] + filter_group,
               ['ItemGroup'] + source_group
              ]
    easy_xml.WriteXmlIfChanged(content, filters_path, pretty=True, win32=True)
  elif os.path.exists(filters_path):
    # We don't need this filter anymore.  Delete the old filter file.
    os.unlink(filters_path)


def _AppendFiltersForMSBuild(parent_filter_name, sources,
                             extension_to_rule_name,
                             filter_group, source_group):
  """Creates the list of filters and sources to be added in the filter file.

  Args:
      parent_filter_name: The name of the filter under which the sources are
          found.
      sources: The hierarchy of filters and sources to process.
      extension_to_rule_name: A dictionary mapping file extensions to rules.
      filter_group: The list to which filter entries will be appended.
      source_group: The list to which source entries will be appeneded.
  """
  for source in sources:
    if isinstance(source, MSVSProject.Filter):
      # We have a sub-filter.  Create the name of that sub-filter.
      if not parent_filter_name:
        filter_name = source.name
      else:
        filter_name = '%s\\%s' % (parent_filter_name, source.name)
      # Add the filter to the group.
      filter_group.append(
          ['Filter', {'Include': filter_name},
           ['UniqueIdentifier', MSVSNew.MakeGuid(source.name)]])
      # Recurse and add its dependents.
      _AppendFiltersForMSBuild(filter_name, source.contents,
                               extension_to_rule_name,
                               filter_group, source_group)
    else:
      # It's a source.  Create a source entry.
      _, element = _MapFileToMsBuildSourceType(source, extension_to_rule_name)
      source_entry = [element, {'Include': source}]
      # Specify the filter it is part of, if any.
      if parent_filter_name:
        source_entry.append(['Filter', parent_filter_name])
      source_group.append(source_entry)


def _MapFileToMsBuildSourceType(source, extension_to_rule_name):
  """Returns the group and element type of the source file.

  Arguments:
      source: The source file name.
      extension_to_rule_name: A dictionary mapping file extensions to rules.

  Returns:
      A pair of (group this file should be part of, the label of element)
  """
  _, ext = os.path.splitext(source)
  if ext in extension_to_rule_name:
    group = 'rule'
    element = extension_to_rule_name[ext]
  elif ext in ['.cc', '.cpp', '.c', '.cxx']:
    group = 'compile'
    element = 'ClCompile'
  elif ext in ['.h', '.hxx']:
    group = 'include'
    element = 'ClInclude'
  elif ext == '.rc':
    group = 'resource'
    element = 'ResourceCompile'
  elif ext == '.idl':
    group = 'midl'
    element = 'Midl'
  else:
    group = 'none'
    element = 'None'
  return (group, element)


def _GenerateRulesForMSBuild(output_dir, options, spec,
                             sources, excluded_sources,
                             props_files_of_rules, targets_files_of_rules,
                             actions_to_add, extension_to_rule_name):
  # MSBuild rules are implemented using three files: an XML file, a .targets
  # file and a .props file.
  # See http://blogs.msdn.com/b/vcblog/archive/2010/04/21/quick-help-on-vs2010-custom-build-rule.aspx
  # for more details.
  rules = spec.get('rules', [])
  rules_native = [r for r in rules if not int(r.get('msvs_external_rule', 0))]
  rules_external = [r for r in rules if int(r.get('msvs_external_rule', 0))]

  msbuild_rules = []
  for rule in rules_native:
    # Skip a rule with no action and no inputs.
    if 'action' not in rule and not rule.get('rule_sources', []):
      continue
    msbuild_rule = MSBuildRule(rule, spec)
    msbuild_rules.append(msbuild_rule)
    extension_to_rule_name[msbuild_rule.extension] = msbuild_rule.rule_name
  if msbuild_rules:
    base = spec['target_name'] + options.suffix
    props_name = base + '.props'
    targets_name = base + '.targets'
    xml_name = base + '.xml'

    props_files_of_rules.add(props_name)
    targets_files_of_rules.add(targets_name)

    props_path = os.path.join(output_dir, props_name)
    targets_path = os.path.join(output_dir, targets_name)
    xml_path = os.path.join(output_dir, xml_name)

    _GenerateMSBuildRulePropsFile(props_path, msbuild_rules)
    _GenerateMSBuildRuleTargetsFile(targets_path, msbuild_rules)
    _GenerateMSBuildRuleXmlFile(xml_path, msbuild_rules)

  if rules_external:
    _GenerateExternalRules(rules_external, output_dir, spec,
                           sources, options, actions_to_add)
  _AdjustSourcesForRules(rules, sources, excluded_sources)


class MSBuildRule(object):
  """Used to store information used to generate an MSBuild rule.

  Attributes:
    rule_name: The rule name, sanitized to use in XML.
    target_name: The name of the target.
    after_targets: The name of the AfterTargets element.
    before_targets: The name of the BeforeTargets element.
    depends_on: The name of the DependsOn element.
    compute_output: The name of the ComputeOutput element.
    dirs_to_make: The name of the DirsToMake element.
    inputs: The name of the _inputs element.
    tlog: The name of the _tlog element.
    extension: The extension this rule applies to.
    description: The message displayed when this rule is invoked.
    additional_dependencies: A string listing additional dependencies.
    outputs: The outputs of this rule.
    command: The command used to run the rule.
  """

  def __init__(self, rule, spec):
    self.display_name = rule['rule_name']
    # Assure that the rule name is only characters and numbers
    self.rule_name = re.sub(r'\W', '_', self.display_name)
    # Create the various element names, following the example set by the
    # Visual Studio 2008 to 2010 conversion.  I don't know if VS2010
    # is sensitive to the exact names.
    self.target_name = '_' + self.rule_name
    self.after_targets = self.rule_name + 'AfterTargets'
    self.before_targets = self.rule_name + 'BeforeTargets'
    self.depends_on = self.rule_name + 'DependsOn'
    self.compute_output = 'Compute%sOutput' % self.rule_name
    self.dirs_to_make = self.rule_name + 'DirsToMake'
    self.inputs = self.rule_name + '_inputs'
    self.tlog = self.rule_name + '_tlog'
    self.extension = rule['extension']
    if not self.extension.startswith('.'):
      self.extension = '.' + self.extension

    self.description = MSVSSettings.ConvertVCMacrosToMSBuild(
        rule.get('message', self.rule_name))
    old_additional_dependencies = _FixPaths(rule.get('inputs', []))
    self.additional_dependencies = (
        ';'.join([MSVSSettings.ConvertVCMacrosToMSBuild(i)
                  for i in old_additional_dependencies]))
    old_outputs = _FixPaths(rule.get('outputs', []))
    self.outputs = ';'.join([MSVSSettings.ConvertVCMacrosToMSBuild(i)
                             for i in old_outputs])
    old_command = _BuildCommandLineForRule(spec, rule, has_input_path=True,
                                           do_setup_env=True)
    self.command = MSVSSettings.ConvertVCMacrosToMSBuild(old_command)


def _GenerateMSBuildRulePropsFile(props_path, msbuild_rules):
  """Generate the .props file."""
  content = ['Project',
             {'xmlns': 'http://schemas.microsoft.com/developer/msbuild/2003'}]
  for rule in msbuild_rules:
    content.extend([
        ['PropertyGroup',
         {'Condition': "'$(%s)' == '' and '$(%s)' == '' and "
          "'$(ConfigurationType)' != 'Makefile'" % (rule.before_targets,
                                                    rule.after_targets)
         },
         [rule.before_targets, 'Midl'],
         [rule.after_targets, 'CustomBuild'],
        ],
        ['PropertyGroup',
         [rule.depends_on,
          {'Condition': "'$(ConfigurationType)' != 'Makefile'"},
          '_SelectedFiles;$(%s)' % rule.depends_on
         ],
        ],
        ['ItemDefinitionGroup',
         [rule.rule_name,
          ['CommandLineTemplate', rule.command],
          ['Outputs', rule.outputs],
          ['ExecutionDescription', rule.description],
          ['AdditionalDependencies', rule.additional_dependencies],
         ],
        ]
    ])
  easy_xml.WriteXmlIfChanged(content, props_path, pretty=True, win32=True)


def _GenerateMSBuildRuleTargetsFile(targets_path, msbuild_rules):
  """Generate the .targets file."""
  content = ['Project',
             {'xmlns': 'http://schemas.microsoft.com/developer/msbuild/2003'
             }
            ]
  item_group = [
      'ItemGroup',
      ['PropertyPageSchema',
       {'Include': '$(MSBuildThisFileDirectory)$(MSBuildThisFileName).xml'}
      ]
    ]
  for rule in msbuild_rules:
    item_group.append(
        ['AvailableItemName',
         {'Include': rule.rule_name},
         ['Targets', rule.target_name],
        ])
  content.append(item_group)

  for rule in msbuild_rules:
    content.append(
        ['UsingTask',
         {'TaskName': rule.rule_name,
          'TaskFactory': 'XamlTaskFactory',
          'AssemblyName': 'Microsoft.Build.Tasks.v4.0'
         },
         ['Task', '$(MSBuildThisFileDirectory)$(MSBuildThisFileName).xml'],
        ])
  for rule in msbuild_rules:
    rule_name = rule.rule_name
    target_outputs = '%%(%s.Outputs)' % rule_name
    target_inputs = ('%%(%s.Identity);%%(%s.AdditionalDependencies);'
                     '$(MSBuildProjectFile)') % (rule_name, rule_name)
    rule_inputs = '%%(%s.Identity)' % rule_name
    extension_condition = ("'%(Extension)'=='.obj' or "
                           "'%(Extension)'=='.res' or "
                           "'%(Extension)'=='.rsc' or "
                           "'%(Extension)'=='.lib'")
    remove_section = [
        'ItemGroup',
        {'Condition': "'@(SelectedFiles)' != ''"},
        [rule_name,
         {'Remove': '@(%s)' % rule_name,
          'Condition': "'%(Identity)' != '@(SelectedFiles)'"
         }
        ]
    ]
    inputs_section = [
        'ItemGroup',
        [rule.inputs, {'Include': '%%(%s.AdditionalDependencies)' % rule_name}]
    ]
    logging_section = [
        'ItemGroup',
        [rule.tlog,
         {'Include': '%%(%s.Outputs)' % rule_name,
          'Condition': ("'%%(%s.Outputs)' != '' and "
                        "'%%(%s.ExcludedFromBuild)' != 'true'" %
                        (rule_name, rule_name))
         },
         ['Source', "@(%s, '|')" % rule_name],
         ['Inputs', "@(%s -> '%%(Fullpath)', ';')" % rule.inputs],
        ],
    ]
    message_section = [
        'Message',
        {'Importance': 'High',
         'Text': '%%(%s.ExecutionDescription)' % rule_name
        }
    ]
    write_tlog_section = [
        'WriteLinesToFile',
        {'Condition': "'@(%s)' != '' and '%%(%s.ExcludedFromBuild)' != "
         "'true'" % (rule.tlog, rule.tlog),
         'File': '$(IntDir)$(ProjectName).write.1.tlog',
         'Lines': "^%%(%s.Source);@(%s->'%%(Fullpath)')" % (rule.tlog,
                                                            rule.tlog)
        }
    ]
    read_tlog_section = [
        'WriteLinesToFile',
        {'Condition': "'@(%s)' != '' and '%%(%s.ExcludedFromBuild)' != "
         "'true'" % (rule.tlog, rule.tlog),
         'File': '$(IntDir)$(ProjectName).read.1.tlog',
         'Lines': "^%%(%s.Source);%%(%s.Inputs)" % (rule.tlog, rule.tlog)
        }
    ]
    command_and_input_section = [
        rule_name,
        {'Condition': "'@(%s)' != '' and '%%(%s.ExcludedFromBuild)' != "
         "'true'" % (rule_name, rule_name),
         'CommandLineTemplate': '%%(%s.CommandLineTemplate)' % rule_name,
         'AdditionalOptions': '%%(%s.AdditionalOptions)' % rule_name,
         'Inputs': rule_inputs
        }
    ]
    content.extend([
        ['Target',
         {'Name': rule.target_name,
          'BeforeTargets': '$(%s)' % rule.before_targets,
          'AfterTargets': '$(%s)' % rule.after_targets,
          'Condition': "'@(%s)' != ''" % rule_name,
          'DependsOnTargets': '$(%s);%s' % (rule.depends_on,
                                            rule.compute_output),
          'Outputs': target_outputs,
          'Inputs': target_inputs
         },
         remove_section,
         inputs_section,
         logging_section,
         message_section,
         write_tlog_section,
         read_tlog_section,
         command_and_input_section,
        ],
        ['PropertyGroup',
         ['ComputeLinkInputsTargets',
          '$(ComputeLinkInputsTargets);',
          '%s;' % rule.compute_output
         ],
         ['ComputeLibInputsTargets',
          '$(ComputeLibInputsTargets);',
          '%s;' % rule.compute_output
         ],
        ],
        ['Target',
         {'Name': rule.compute_output,
          'Condition': "'@(%s)' != ''" % rule_name
         },
         ['ItemGroup',
          [rule.dirs_to_make,
           {'Condition': "'@(%s)' != '' and "
            "'%%(%s.ExcludedFromBuild)' != 'true'" % (rule_name, rule_name),
            'Include': '%%(%s.Outputs)' % rule_name
           }
          ],
          ['Link',
           {'Include': '%%(%s.Identity)' % rule.dirs_to_make,
            'Condition': extension_condition
           }
          ],
          ['Lib',
           {'Include': '%%(%s.Identity)' % rule.dirs_to_make,
            'Condition': extension_condition
           }
          ],
          ['ImpLib',
           {'Include': '%%(%s.Identity)' % rule.dirs_to_make,
            'Condition': extension_condition
           }
          ],
         ],
         ['MakeDir',
          {'Directories': ("@(%s->'%%(RootDir)%%(Directory)')" %
                           rule.dirs_to_make)
          }
         ]
        ],
    ])
  easy_xml.WriteXmlIfChanged(content, targets_path, pretty=True, win32=True)


def _GenerateMSBuildRuleXmlFile(xml_path, msbuild_rules):
  # Generate the .xml file
  content = [
      'ProjectSchemaDefinitions',
      {'xmlns': ('clr-namespace:Microsoft.Build.Framework.XamlTypes;'
                 'assembly=Microsoft.Build.Framework'),
       'xmlns:x': 'http://schemas.microsoft.com/winfx/2006/xaml',
       'xmlns:sys': 'clr-namespace:System;assembly=mscorlib',
       'xmlns:transformCallback':
       'Microsoft.Cpp.Dev10.ConvertPropertyCallback'
      }
  ]
  for rule in msbuild_rules:
    content.extend([
        ['Rule',
         {'Name': rule.rule_name,
          'PageTemplate': 'tool',
          'DisplayName': rule.display_name,
          'Order': '200'
         },
         ['Rule.DataSource',
          ['DataSource',
           {'Persistence': 'ProjectFile',
            'ItemType': rule.rule_name
           }
          ]
         ],
         ['Rule.Categories',
          ['Category',
           {'Name': 'General'},
           ['Category.DisplayName',
            ['sys:String', 'General'],
           ],
          ],
          ['Category',
           {'Name': 'Command Line',
            'Subtype': 'CommandLine'
           },
           ['Category.DisplayName',
            ['sys:String', 'Command Line'],
           ],
          ],
         ],
         ['StringListProperty',
          {'Name': 'Inputs',
           'Category': 'Command Line',
           'IsRequired': 'true',
           'Switch': ' '
          },
          ['StringListProperty.DataSource',
           ['DataSource',
            {'Persistence': 'ProjectFile',
             'ItemType': rule.rule_name,
             'SourceType': 'Item'
            }
           ]
          ],
         ],
         ['StringProperty',
          {'Name': 'CommandLineTemplate',
           'DisplayName': 'Command Line',
           'Visible': 'False',
           'IncludeInCommandLine': 'False'
          }
         ],
         ['DynamicEnumProperty',
          {'Name': rule.before_targets,
           'Category': 'General',
           'EnumProvider': 'Targets',
           'IncludeInCommandLine': 'False'
          },
          ['DynamicEnumProperty.DisplayName',
           ['sys:String', 'Execute Before'],
          ],
          ['DynamicEnumProperty.Description',
           ['sys:String', 'Specifies the targets for the build customization'
            ' to run before.'
           ],
          ],
          ['DynamicEnumProperty.ProviderSettings',
           ['NameValuePair',
            {'Name': 'Exclude',
             'Value': '^%s|^Compute' % rule.before_targets
            }
           ]
          ],
          ['DynamicEnumProperty.DataSource',
           ['DataSource',
            {'Persistence': 'ProjectFile',
             'HasConfigurationCondition': 'true'
            }
           ]
          ],
         ],
         ['DynamicEnumProperty',
          {'Name': rule.after_targets,
           'Category': 'General',
           'EnumProvider': 'Targets',
           'IncludeInCommandLine': 'False'
          },
          ['DynamicEnumProperty.DisplayName',
           ['sys:String', 'Execute After'],
          ],
          ['DynamicEnumProperty.Description',
           ['sys:String', ('Specifies the targets for the build customization'
                           ' to run after.')
           ],
          ],
          ['DynamicEnumProperty.ProviderSettings',
           ['NameValuePair',
            {'Name': 'Exclude',
             'Value': '^%s|^Compute' % rule.after_targets
            }
           ]
          ],
          ['DynamicEnumProperty.DataSource',
           ['DataSource',
            {'Persistence': 'ProjectFile',
             'ItemType': '',
             'HasConfigurationCondition': 'true'
            }
           ]
          ],
         ],
         ['StringListProperty',
          {'Name': 'Outputs',
           'DisplayName': 'Outputs',
           'Visible': 'False',
           'IncludeInCommandLine': 'False'
          }
         ],
         ['StringProperty',
          {'Name': 'ExecutionDescription',
           'DisplayName': 'Execution Description',
           'Visible': 'False',
           'IncludeInCommandLine': 'False'
          }
         ],
         ['StringListProperty',
          {'Name': 'AdditionalDependencies',
           'DisplayName': 'Additional Dependencies',
           'IncludeInCommandLine': 'False',
           'Visible': 'false'
          }
         ],
         ['StringProperty',
          {'Subtype': 'AdditionalOptions',
           'Name': 'AdditionalOptions',
           'Category': 'Command Line'
          },
          ['StringProperty.DisplayName',
           ['sys:String', 'Additional Options'],
          ],
          ['StringProperty.Description',
           ['sys:String', 'Additional Options'],
          ],
         ],
        ],
        ['ItemType',
         {'Name': rule.rule_name,
          'DisplayName': rule.display_name
         }
        ],
        ['FileExtension',
         {'Name': '*' + rule.extension,
          'ContentType': rule.rule_name
         }
        ],
        ['ContentType',
         {'Name': rule.rule_name,
          'DisplayName': '',
          'ItemType': rule.rule_name
         }
        ]
    ])
  easy_xml.WriteXmlIfChanged(content, xml_path, pretty=True, win32=True)


def _GetConfigurationAndPlatform(name, settings):
  configuration = name.rsplit('_', 1)[0]
  platform = settings.get('msvs_configuration_platform', 'Win32')
  return (configuration, platform)


def _GetConfigurationCondition(name, settings):
  return (r"'$(Configuration)|$(Platform)'=='%s|%s'" %
          _GetConfigurationAndPlatform(name, settings))


def _GetMSBuildProjectConfigurations(configurations):
  group = ['ItemGroup', {'Label': 'ProjectConfigurations'}]
  for (name, settings) in sorted(configurations.iteritems()):
    configuration, platform = _GetConfigurationAndPlatform(name, settings)
    designation = '%s|%s' % (configuration, platform)
    group.append(
        ['ProjectConfiguration', {'Include': designation},
         ['Configuration', configuration],
         ['Platform', platform]])
  return [group]


def _GetMSBuildGlobalProperties(spec, guid, gyp_file_name):
  namespace = os.path.splitext(gyp_file_name)[0]
  return [
      ['PropertyGroup', {'Label': 'Globals'},
       ['ProjectGuid', guid],
       ['Keyword', 'Win32Proj'],
       ['RootNamespace', namespace],
      ]
  ]


def _GetMSBuildConfigurationDetails(spec, build_file):
  properties = {}
  for name, settings in spec['configurations'].iteritems():
    msbuild_attributes = _GetMSBuildAttributes(spec, settings, build_file)
    condition = _GetConfigurationCondition(name, settings)
    character_set = msbuild_attributes.get('CharacterSet')
    _AddConditionalProperty(properties, condition, 'ConfigurationType',
                            msbuild_attributes['ConfigurationType'])
    if character_set:
      _AddConditionalProperty(properties, condition, 'CharacterSet',
                              character_set)
  return _GetMSBuildPropertyGroup(spec, 'Configuration', properties)


def _GetMSBuildLocalProperties(msbuild_toolset):
  # Currently the only local property we support is PlatformToolset
  properties = {}
  if msbuild_toolset:
    properties = [
        ['PropertyGroup', {'Label': 'Locals'},
          ['PlatformToolset', msbuild_toolset],
        ]
      ]
  return properties


def _GetMSBuildPropertySheets(configurations):
  user_props = r'$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props'
  additional_props = {}
  props_specified = False
  for name, settings in sorted(configurations.iteritems()):
    configuration = _GetConfigurationCondition(name, settings)
    if settings.has_key('msbuild_props'):
      additional_props[configuration] = _FixPaths(settings['msbuild_props'])
      props_specified = True
    else:
     additional_props[configuration] = ''

  if not props_specified:
    return [
        ['ImportGroup',
         {'Label': 'PropertySheets'},
         ['Import',
          {'Project': user_props,
           'Condition': "exists('%s')" % user_props,
           'Label': 'LocalAppDataPlatform'
          }
         ]
        ]
    ]
  else:
    sheets = []
    for condition, props in additional_props.iteritems():
      import_group = [
        'ImportGroup',
        {'Label': 'PropertySheets',
         'Condition': condition
        },
        ['Import',
         {'Project': user_props,
          'Condition': "exists('%s')" % user_props,
          'Label': 'LocalAppDataPlatform'
         }
        ]
      ]
      for props_file in props:
        import_group.append(['Import', {'Project':props_file}])
      sheets.append(import_group)
    return sheets

def _ConvertMSVSBuildAttributes(spec, config, build_file):
  config_type = _GetMSVSConfigurationType(spec, build_file)
  msvs_attributes = _GetMSVSAttributes(spec, config, config_type)
  msbuild_attributes = {}
  for a in msvs_attributes:
    if a in ['IntermediateDirectory', 'OutputDirectory']:
      directory = MSVSSettings.ConvertVCMacrosToMSBuild(msvs_attributes[a])
      if not directory.endswith('\\'):
        directory += '\\'
      msbuild_attributes[a] = directory
    elif a == 'CharacterSet':
      msbuild_attributes[a] = _ConvertMSVSCharacterSet(msvs_attributes[a])
    elif a == 'ConfigurationType':
      msbuild_attributes[a] = _ConvertMSVSConfigurationType(msvs_attributes[a])
    else:
      print 'Warning: Do not know how to convert MSVS attribute ' + a
  return msbuild_attributes


def _ConvertMSVSCharacterSet(char_set):
  if char_set.isdigit():
    char_set = {
        '0': 'MultiByte',
        '1': 'Unicode',
        '2': 'MultiByte',
    }[char_set]
  return char_set


def _ConvertMSVSConfigurationType(config_type):
  if config_type.isdigit():
    config_type = {
        '1': 'Application',
        '2': 'DynamicLibrary',
        '4': 'StaticLibrary',
        '10': 'Utility'
    }[config_type]
  return config_type


def _GetMSBuildAttributes(spec, config, build_file):
  if 'msbuild_configuration_attributes' not in config:
    msbuild_attributes = _ConvertMSVSBuildAttributes(spec, config, build_file)

  else:
    config_type = _GetMSVSConfigurationType(spec, build_file)
    config_type = _ConvertMSVSConfigurationType(config_type)
    msbuild_attributes = config.get('msbuild_configuration_attributes', {})
    msbuild_attributes.setdefault('ConfigurationType', config_type)
    output_dir = msbuild_attributes.get('OutputDirectory',
                                      '$(SolutionDir)$(Configuration)')
    msbuild_attributes['OutputDirectory'] = _FixPath(output_dir) + '\\'
    if 'IntermediateDirectory' not in msbuild_attributes:
      intermediate = _FixPath('$(Configuration)') + '\\'
      msbuild_attributes['IntermediateDirectory'] = intermediate
    if 'CharacterSet' in msbuild_attributes:
      msbuild_attributes['CharacterSet'] = _ConvertMSVSCharacterSet(
          msbuild_attributes['CharacterSet'])
  if 'TargetName' not in msbuild_attributes:
    prefix = spec.get('product_prefix', '')
    product_name = spec.get('product_name', '$(ProjectName)')
    target_name = prefix + product_name
    msbuild_attributes['TargetName'] = target_name

  # Make sure that 'TargetPath' matches 'Lib.OutputFile' or 'Link.OutputFile'
  # (depending on the tool used) to avoid MSB8012 warning.
  msbuild_tool_map = {
      'executable': 'Link',
      'shared_library': 'Link',
      'loadable_module': 'Link',
      'static_library': 'Lib',
  }
  msbuild_tool = msbuild_tool_map.get(spec['type'])
  if msbuild_tool:
    msbuild_settings = config['finalized_msbuild_settings']
    out_file = msbuild_settings[msbuild_tool].get('OutputFile')
    if out_file:
      msbuild_attributes['TargetPath'] = _FixPath(out_file)

  return msbuild_attributes


def _GetMSBuildConfigurationGlobalProperties(spec, configurations, build_file):
  # TODO(jeanluc) We could optimize out the following and do it only if
  # there are actions.
  # TODO(jeanluc) Handle the equivalent of setting 'CYGWIN=nontsec'.
  new_paths = []
  cygwin_dirs = spec.get('msvs_cygwin_dirs', ['.'])[0]
  if cygwin_dirs:
    cyg_path = '$(MSBuildProjectDirectory)\\%s\\bin\\' % _FixPath(cygwin_dirs)
    new_paths.append(cyg_path)
    # TODO(jeanluc) Change the convention to have both a cygwin_dir and a
    # python_dir.
    python_path = cyg_path.replace('cygwin\\bin', 'python_26')
    new_paths.append(python_path)
    if new_paths:
      new_paths = '$(ExecutablePath);' + ';'.join(new_paths)

  properties = {}
  for (name, configuration) in sorted(configurations.iteritems()):
    condition = _GetConfigurationCondition(name, configuration)
    attributes = _GetMSBuildAttributes(spec, configuration, build_file)
    msbuild_settings = configuration['finalized_msbuild_settings']
    _AddConditionalProperty(properties, condition, 'IntDir',
                            attributes['IntermediateDirectory'])
    _AddConditionalProperty(properties, condition, 'OutDir',
                            attributes['OutputDirectory'])
    _AddConditionalProperty(properties, condition, 'TargetName',
                            attributes['TargetName'])

    if attributes.get('TargetPath'):
      _AddConditionalProperty(properties, condition, 'TargetPath',
                              attributes['TargetPath'])

    if new_paths:
      _AddConditionalProperty(properties, condition, 'ExecutablePath',
                              new_paths)
    tool_settings = msbuild_settings.get('', {})
    for name, value in sorted(tool_settings.iteritems()):
      formatted_value = _GetValueFormattedForMSBuild('', name, value)
      _AddConditionalProperty(properties, condition, name, formatted_value)
  return _GetMSBuildPropertyGroup(spec, None, properties)


def _AddConditionalProperty(properties, condition, name, value):
  """Adds a property / conditional value pair to a dictionary.

  Arguments:
    properties: The dictionary to be modified.  The key is the name of the
        property.  The value is itself a dictionary; its key is the value and
        the value a list of condition for which this value is true.
    condition: The condition under which the named property has the value.
    name: The name of the property.
    value: The value of the property.
  """
  if name not in properties:
    properties[name] = {}
  values = properties[name]
  if value not in values:
    values[value] = []
  conditions = values[value]
  conditions.append(condition)


# Regex for msvs variable references ( i.e. $(FOO) ).
MSVS_VARIABLE_REFERENCE = re.compile('\$\(([a-zA-Z_][a-zA-Z0-9_]*)\)')


def _GetMSBuildPropertyGroup(spec, label, properties):
  """Returns a PropertyGroup definition for the specified properties.

  Arguments:
    spec: The target project dict.
    label: An optional label for the PropertyGroup.
    properties: The dictionary to be converted.  The key is the name of the
        property.  The value is itself a dictionary; its key is the value and
        the value a list of condition for which this value is true.
  """
  group = ['PropertyGroup']
  if label:
    group.append({'Label': label})
  num_configurations = len(spec['configurations'])
  def GetEdges(node):
    # Use a definition of edges such that user_of_variable -> used_varible.
    # This happens to be easier in this case, since a variable's
    # definition contains all variables it references in a single string.
    edges = set()
    for value in sorted(properties[node].keys()):
      # Add to edges all $(...) references to variables.
      #
      # Variable references that refer to names not in properties are excluded
      # These can exist for instance to refer built in definitions like
      # $(SolutionDir).
      #
      # Self references are ignored. Self reference is used in a few places to
      # append to the default value. I.e. PATH=$(PATH);other_path
      edges.update(set([v for v in MSVS_VARIABLE_REFERENCE.findall(value)
                        if v in properties and v != node]))
    return edges
  properties_ordered = gyp.common.TopologicallySorted(
      properties.keys(), GetEdges)
  # Walk properties in the reverse of a topological sort on
  # user_of_variable -> used_variable as this ensures variables are
  # defined before they are used.
  # NOTE: reverse(topsort(DAG)) = topsort(reverse_edges(DAG))
  for name in reversed(properties_ordered):
    values = properties[name]
    for value, conditions in sorted(values.iteritems()):
      if len(conditions) == num_configurations:
        # If the value is the same all configurations,
        # just add one unconditional entry.
        group.append([name, value])
      else:
        for condition in conditions:
          group.append([name, {'Condition': condition}, value])
  return [group]


def _GetMSBuildToolSettingsSections(spec, configurations):
  groups = []
  for (name, configuration) in sorted(configurations.iteritems()):
    msbuild_settings = configuration['finalized_msbuild_settings']
    group = ['ItemDefinitionGroup',
             {'Condition': _GetConfigurationCondition(name, configuration)}
            ]
    for tool_name, tool_settings in sorted(msbuild_settings.iteritems()):
      # Skip the tool named '' which is a holder of global settings handled
      # by _GetMSBuildConfigurationGlobalProperties.
      if tool_name:
        if tool_settings:
          tool = [tool_name]
          for name, value in sorted(tool_settings.iteritems()):
            formatted_value = _GetValueFormattedForMSBuild(tool_name, name,
                                                           value)
            tool.append([name, formatted_value])
          group.append(tool)
    groups.append(group)
  return groups


def _FinalizeMSBuildSettings(spec, configuration):
  if 'msbuild_settings' in configuration:
    converted = False
    msbuild_settings = configuration['msbuild_settings']
    MSVSSettings.ValidateMSBuildSettings(msbuild_settings)
  else:
    converted = True
    msvs_settings = configuration.get('msvs_settings', {})
    msbuild_settings = MSVSSettings.ConvertToMSBuildSettings(msvs_settings)
  include_dirs, resource_include_dirs = _GetIncludeDirs(configuration)
  libraries = _GetLibraries(spec)
  out_file, _, msbuild_tool = _GetOutputFilePathAndTool(spec, msbuild=True)
  defines = _GetDefines(configuration)
  if converted:
    # Visual Studio 2010 has TR1
    defines = [d for d in defines if d != '_HAS_TR1=0']
    # Warn of ignored settings
    ignored_settings = ['msvs_prebuild', 'msvs_postbuild', 'msvs_tool_files']
    for ignored_setting in ignored_settings:
      value = configuration.get(ignored_setting)
      if value:
        print ('Warning: The automatic conversion to MSBuild does not handle '
               '%s.  Ignoring setting of %s' % (ignored_setting, str(value)))

  defines = [_EscapeCppDefineForMSBuild(d) for d in defines]
  disabled_warnings = _GetDisabledWarnings(configuration)
  # TODO(jeanluc) Validate & warn that we don't translate
  # prebuild = configuration.get('msvs_prebuild')
  # postbuild = configuration.get('msvs_postbuild')
  def_file = _GetModuleDefinition(spec)
  precompiled_header = configuration.get('msvs_precompiled_header')

  # Add the information to the appropriate tool
  # TODO(jeanluc) We could optimize and generate these settings only if
  # the corresponding files are found, e.g. don't generate ResourceCompile
  # if you don't have any resources.
  _ToolAppend(msbuild_settings, 'ClCompile',
              'AdditionalIncludeDirectories', include_dirs)
  _ToolAppend(msbuild_settings, 'ResourceCompile',
              'AdditionalIncludeDirectories', resource_include_dirs)
  # Add in libraries.
  _ToolAppend(msbuild_settings, 'Link', 'AdditionalDependencies', libraries)
  if out_file:
    _ToolAppend(msbuild_settings, msbuild_tool, 'OutputFile', out_file,
                only_if_unset=True)
  # Add defines.
  _ToolAppend(msbuild_settings, 'ClCompile',
              'PreprocessorDefinitions', defines)
  _ToolAppend(msbuild_settings, 'ResourceCompile',
              'PreprocessorDefinitions', defines)
  # Add disabled warnings.
  _ToolAppend(msbuild_settings, 'ClCompile',
              'DisableSpecificWarnings', disabled_warnings)
  # Turn on precompiled headers if appropriate.
  if precompiled_header:
    precompiled_header = os.path.split(precompiled_header)[1]
    _ToolAppend(msbuild_settings, 'ClCompile', 'PrecompiledHeader', 'Use')
    _ToolAppend(msbuild_settings, 'ClCompile',
                'PrecompiledHeaderFile', precompiled_header)
    _ToolAppend(msbuild_settings, 'ClCompile',
                'ForcedIncludeFiles', precompiled_header)
  # Loadable modules don't generate import libraries;
  # tell dependent projects to not expect one.
  if spec['type'] == 'loadable_module':
    _ToolAppend(msbuild_settings, '', 'IgnoreImportLibrary', 'true')
  # Set the module definition file if any.
  if def_file:
    _ToolAppend(msbuild_settings, 'Link', 'ModuleDefinitionFile', def_file)
  configuration['finalized_msbuild_settings'] = msbuild_settings


def _GetValueFormattedForMSBuild(tool_name, name, value):
  if type(value) == list:
    # For some settings, VS2010 does not automatically extends the settings
    # TODO(jeanluc) Is this what we want?
    if name in ['AdditionalDependencies',
                'AdditionalIncludeDirectories',
                'AdditionalLibraryDirectories',
                'AdditionalOptions',
                'DelayLoadDLLs',
                'DisableSpecificWarnings',
                'PreprocessorDefinitions']:
      value.append('%%(%s)' % name)
    # For most tools, entries in a list should be separated with ';' but some
    # settings use a space.  Check for those first.
    exceptions = {
        'ClCompile': ['AdditionalOptions'],
        'Link': ['AdditionalOptions'],
        'Lib': ['AdditionalOptions']}
    if tool_name in exceptions and name in exceptions[tool_name]:
      char = ' '
    else:
      char = ';'
    formatted_value = char.join(
        [MSVSSettings.ConvertVCMacrosToMSBuild(i) for i in value])
  else:
    formatted_value = MSVSSettings.ConvertVCMacrosToMSBuild(value)
  return formatted_value


def _VerifySourcesExist(sources, root_dir):
  """Verifies that all source files exist on disk.

  Checks that all regular source files, i.e. not created at run time,
  exist on disk.  Missing files cause needless recompilation but no otherwise
  visible errors.

  Arguments:
    sources: A recursive list of Filter/file names.
    root_dir: The root directory for the relative path names.
  Returns:
    A list of source files that cannot be found on disk.
  """
  missing_sources = []
  for source in sources:
    if isinstance(source, MSVSProject.Filter):
      missing_sources.extend(_VerifySourcesExist(source.contents, root_dir))
    else:
      if '$' not in source:
        full_path = os.path.join(root_dir, source)
        if not os.path.exists(full_path):
          missing_sources.append(full_path)
  return missing_sources


def _GetMSBuildSources(spec, sources, exclusions, extension_to_rule_name,
                       actions_spec, sources_handled_by_action, list_excluded):
  groups = ['none', 'midl', 'include', 'compile', 'resource', 'rule']
  grouped_sources = {}
  for g in groups:
    grouped_sources[g] = []

  _AddSources2(spec, sources, exclusions, grouped_sources,
               extension_to_rule_name, sources_handled_by_action, list_excluded)
  sources = []
  for g in groups:
    if grouped_sources[g]:
      sources.append(['ItemGroup'] + grouped_sources[g])
  if actions_spec:
    sources.append(['ItemGroup'] + actions_spec)
  return sources


def _AddSources2(spec, sources, exclusions, grouped_sources,
                 extension_to_rule_name, sources_handled_by_action,
                 list_excluded):
  extensions_excluded_from_precompile = []
  for source in sources:
    if isinstance(source, MSVSProject.Filter):
      _AddSources2(spec, source.contents, exclusions, grouped_sources,
                   extension_to_rule_name, sources_handled_by_action,
                   list_excluded)
    else:
      if not source in sources_handled_by_action:
        detail = []
        excluded_configurations = exclusions.get(source, [])
        if len(excluded_configurations) == len(spec['configurations']):
          detail.append(['ExcludedFromBuild', 'true'])
        else:
          for config_name, configuration in sorted(excluded_configurations):
            condition = _GetConfigurationCondition(config_name, configuration)
            detail.append(['ExcludedFromBuild',
                           {'Condition': condition},
                           'true'])
        # Add precompile if needed
        for config_name, configuration in spec['configurations'].iteritems():
          precompiled_source = configuration.get('msvs_precompiled_source', '')
          if precompiled_source != '':
            precompiled_source = _FixPath(precompiled_source)
            if not extensions_excluded_from_precompile:
              # If the precompiled header is generated by a C source, we must
              # not try to use it for C++ sources, and vice versa.
              basename, extension = os.path.splitext(precompiled_source)
              if extension == '.c':
                extensions_excluded_from_precompile = ['.cc', '.cpp', '.cxx']
              else:
                extensions_excluded_from_precompile = ['.c']

          if precompiled_source == source:
            condition = _GetConfigurationCondition(config_name, configuration)
            detail.append(['PrecompiledHeader',
                           {'Condition': condition},
                           'Create'
                          ])
          else:
            # Turn off precompiled header usage for source files of a
            # different type than the file that generated the
            # precompiled header.
            for extension in extensions_excluded_from_precompile:
              if source.endswith(extension):
                detail.append(['PrecompiledHeader', ''])
                detail.append(['ForcedIncludeFiles', ''])

        group, element = _MapFileToMsBuildSourceType(source,
                                                     extension_to_rule_name)
        grouped_sources[group].append([element, {'Include': source}] + detail)


def _GetMSBuildProjectReferences(project):
  references = []
  if project.dependencies:
    group = ['ItemGroup']
    for dependency in project.dependencies:
      guid = dependency.guid
      project_dir = os.path.split(project.path)[0]
      relative_path = gyp.common.RelativePath(dependency.path, project_dir)
      project_ref = ['ProjectReference',
          {'Include': relative_path},
          ['Project', guid],
          ['ReferenceOutputAssembly', 'false']
          ]
      for config in dependency.spec.get('configurations', {}).itervalues():
        # If it's disabled in any config, turn it off in the reference.
        if config.get('msvs_2010_disable_uldi_when_referenced', 0):
          project_ref.append(['UseLibraryDependencyInputs', 'false'])
          break
      group.append(project_ref)
    references.append(group)
  return references


def _GenerateMSBuildProject(project, options, version, generator_flags):
  spec = project.spec
  configurations = spec['configurations']
  project_dir, project_file_name = os.path.split(project.path)
  msbuildproj_dir = os.path.dirname(project.path)
  if msbuildproj_dir and not os.path.exists(msbuildproj_dir):
    os.makedirs(msbuildproj_dir)
  # Prepare list of sources and excluded sources.
  gyp_path = _NormalizedSource(project.build_file)
  relative_path_of_gyp_file = gyp.common.RelativePath(gyp_path, project_dir)

  gyp_file = os.path.split(project.build_file)[1]
  sources, excluded_sources = _PrepareListOfSources(spec, generator_flags,
                                                    gyp_file)
  # Add rules.
  actions_to_add = {}
  props_files_of_rules = set()
  targets_files_of_rules = set()
  extension_to_rule_name = {}
  list_excluded = generator_flags.get('msvs_list_excluded_files', True)
  _GenerateRulesForMSBuild(project_dir, options, spec,
                           sources, excluded_sources,
                           props_files_of_rules, targets_files_of_rules,
                           actions_to_add, extension_to_rule_name)
  sources, excluded_sources, excluded_idl = (
      _AdjustSourcesAndConvertToFilterHierarchy(spec, options,
                                                project_dir, sources,
                                                excluded_sources,
                                                list_excluded))
  _AddActions(actions_to_add, spec, project.build_file)
  _AddCopies(actions_to_add, spec)

  # NOTE: this stanza must appear after all actions have been decided.
  # Don't excluded sources with actions attached, or they won't run.
  excluded_sources = _FilterActionsFromExcluded(
      excluded_sources, actions_to_add)

  exclusions = _GetExcludedFilesFromBuild(spec, excluded_sources, excluded_idl)
  actions_spec, sources_handled_by_action = _GenerateActionsForMSBuild(
      spec, actions_to_add)

  _GenerateMSBuildFiltersFile(project.path + '.filters', sources,
                              extension_to_rule_name)
  missing_sources = _VerifySourcesExist(sources, project_dir)

  for configuration in configurations.itervalues():
    _FinalizeMSBuildSettings(spec, configuration)

  # Add attributes to root element

  import_default_section = [
      ['Import', {'Project': r'$(VCTargetsPath)\Microsoft.Cpp.Default.props'}]]
  import_cpp_props_section = [
      ['Import', {'Project': r'$(VCTargetsPath)\Microsoft.Cpp.props'}]]
  import_cpp_targets_section = [
      ['Import', {'Project': r'$(VCTargetsPath)\Microsoft.Cpp.targets'}]]
  macro_section = [['PropertyGroup', {'Label': 'UserMacros'}]]

  content = [
      'Project',
      {'xmlns': 'http://schemas.microsoft.com/developer/msbuild/2003',
       'ToolsVersion': version.ProjectVersion(),
       'DefaultTargets': 'Build'
      }]

  content += _GetMSBuildProjectConfigurations(configurations)
  content += _GetMSBuildGlobalProperties(spec, project.guid, project_file_name)
  content += import_default_section
  content += _GetMSBuildConfigurationDetails(spec, project.build_file)
  content += _GetMSBuildLocalProperties(project.msbuild_toolset)
  content += import_cpp_props_section
  content += _GetMSBuildExtensions(props_files_of_rules)
  content += _GetMSBuildPropertySheets(configurations)
  content += macro_section
  content += _GetMSBuildConfigurationGlobalProperties(spec, configurations,
                                                      project.build_file)
  content += _GetMSBuildToolSettingsSections(spec, configurations)
  content += _GetMSBuildSources(
      spec, sources, exclusions, extension_to_rule_name, actions_spec,
      sources_handled_by_action, list_excluded)
  content += _GetMSBuildProjectReferences(project)
  content += import_cpp_targets_section
  content += _GetMSBuildExtensionTargets(targets_files_of_rules)

  # TODO(jeanluc) File a bug to get rid of runas.  We had in MSVS:
  # has_run_as = _WriteMSVSUserFile(project.path, version, spec)

  easy_xml.WriteXmlIfChanged(content, project.path, pretty=True, win32=True)

  return missing_sources


def _GetMSBuildExtensions(props_files_of_rules):
  extensions = ['ImportGroup', {'Label': 'ExtensionSettings'}]
  for props_file in props_files_of_rules:
    extensions.append(['Import', {'Project': props_file}])
  return [extensions]


def _GetMSBuildExtensionTargets(targets_files_of_rules):
  targets_node = ['ImportGroup', {'Label': 'ExtensionTargets'}]
  for targets_file in sorted(targets_files_of_rules):
    targets_node.append(['Import', {'Project': targets_file}])
  return [targets_node]


def _GenerateActionsForMSBuild(spec, actions_to_add):
  """Add actions accumulated into an actions_to_add, merging as needed.

  Arguments:
    spec: the target project dict
    actions_to_add: dictionary keyed on input name, which maps to a list of
        dicts describing the actions attached to that input file.

  Returns:
    A pair of (action specification, the sources handled by this action).
  """
  sources_handled_by_action = set()
  actions_spec = []
  for primary_input, actions in actions_to_add.iteritems():
    inputs = set()
    outputs = set()
    descriptions = []
    commands = []
    for action in actions:
      inputs.update(set(action['inputs']))
      outputs.update(set(action['outputs']))
      descriptions.append(action['description'])
      cmd = action['command']
      # For most actions, add 'call' so that actions that invoke batch files
      # return and continue executing.  msbuild_use_call provides a way to
      # disable this but I have not seen any adverse effect from doing that
      # for everything.
      if action.get('msbuild_use_call', True):
        cmd = 'call ' + cmd
      commands.append(cmd)
    # Add the custom build action for one input file.
    description = ', and also '.join(descriptions)

    # We can't join the commands simply with && because the command line will
    # get too long. See also _AddActions: cygwin's setup_env mustn't be called
    # for every invocation or the command that sets the PATH will grow too
    # long.
    command = (
        '\r\nif %errorlevel% neq 0 exit /b %errorlevel%\r\n'.join(commands))
    _AddMSBuildAction(spec,
                      primary_input,
                      inputs,
                      outputs,
                      command,
                      description,
                      sources_handled_by_action,
                      actions_spec)
  return actions_spec, sources_handled_by_action


def _AddMSBuildAction(spec, primary_input, inputs, outputs, cmd, description,
                      sources_handled_by_action, actions_spec):
  command = MSVSSettings.ConvertVCMacrosToMSBuild(cmd)
  primary_input = _FixPath(primary_input)
  inputs_array = _FixPaths(inputs)
  outputs_array = _FixPaths(outputs)
  additional_inputs = ';'.join([i for i in inputs_array
                                if i != primary_input])
  outputs = ';'.join(outputs_array)
  sources_handled_by_action.add(primary_input)
  action_spec = ['CustomBuild', {'Include': primary_input}]
  action_spec.extend(
      # TODO(jeanluc) 'Document' for all or just if as_sources?
      [['FileType', 'Document'],
       ['Command', command],
       ['Message', description],
       ['Outputs', outputs]
      ])
  if additional_inputs:
    action_spec.append(['AdditionalInputs', additional_inputs])
  actions_spec.append(action_spec)

########NEW FILE########
__FILENAME__ = msvs_test
#!/usr/bin/env python
# Copyright (c) 2012 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" Unit tests for the msvs.py file. """

import gyp.generator.msvs as msvs
import unittest
import StringIO


class TestSequenceFunctions(unittest.TestCase):

  def setUp(self):
    self.stderr = StringIO.StringIO()

  def test_GetLibraries(self):
    self.assertEqual(
      msvs._GetLibraries({}),
      [])
    self.assertEqual(
      msvs._GetLibraries({'libraries': []}),
      [])
    self.assertEqual(
      msvs._GetLibraries({'other':'foo', 'libraries': ['a.lib']}),
      ['a.lib'])
    self.assertEqual(
      msvs._GetLibraries({'libraries': ['-la']}),
      ['a.lib'])
    self.assertEqual(
      msvs._GetLibraries({'libraries': ['a.lib', 'b.lib', 'c.lib', '-lb.lib',
                                   '-lb.lib', 'd.lib', 'a.lib']}),
      ['c.lib', 'b.lib', 'd.lib', 'a.lib'])

if __name__ == '__main__':
  unittest.main()

########NEW FILE########
__FILENAME__ = ninja
# Copyright (c) 2012 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import hashlib
import multiprocessing
import os.path
import re
import signal
import subprocess
import sys
import gyp
import gyp.common
import gyp.msvs_emulation
import gyp.MSVSVersion
import gyp.xcode_emulation

from gyp.common import GetEnvironFallback
import gyp.ninja_syntax as ninja_syntax

generator_default_variables = {
  'EXECUTABLE_PREFIX': '',
  'EXECUTABLE_SUFFIX': '',
  'STATIC_LIB_PREFIX': 'lib',
  'STATIC_LIB_SUFFIX': '.a',
  'SHARED_LIB_PREFIX': 'lib',

  # Gyp expects the following variables to be expandable by the build
  # system to the appropriate locations.  Ninja prefers paths to be
  # known at gyp time.  To resolve this, introduce special
  # variables starting with $! and $| (which begin with a $ so gyp knows it
  # should be treated specially, but is otherwise an invalid
  # ninja/shell variable) that are passed to gyp here but expanded
  # before writing out into the target .ninja files; see
  # ExpandSpecial.
  # $! is used for variables that represent a path and that can only appear at
  # the start of a string, while $| is used for variables that can appear
  # anywhere in a string.
  'INTERMEDIATE_DIR': '$!INTERMEDIATE_DIR',
  'SHARED_INTERMEDIATE_DIR': '$!PRODUCT_DIR/gen',
  'PRODUCT_DIR': '$!PRODUCT_DIR',
  'CONFIGURATION_NAME': '$|CONFIGURATION_NAME',

  # Special variables that may be used by gyp 'rule' targets.
  # We generate definitions for these variables on the fly when processing a
  # rule.
  'RULE_INPUT_ROOT': '${root}',
  'RULE_INPUT_DIRNAME': '${dirname}',
  'RULE_INPUT_PATH': '${source}',
  'RULE_INPUT_EXT': '${ext}',
  'RULE_INPUT_NAME': '${name}',
}

# Placates pylint.
generator_additional_non_configuration_keys = []
generator_additional_path_sections = []
generator_extra_sources_for_rules = []

# TODO: figure out how to not build extra host objects in the non-cross-compile
# case when this is enabled, and enable unconditionally.
generator_supports_multiple_toolsets = (
  os.environ.get('GYP_CROSSCOMPILE') or
  os.environ.get('AR_host') or
  os.environ.get('CC_host') or
  os.environ.get('CXX_host') or
  os.environ.get('AR_target') or
  os.environ.get('CC_target') or
  os.environ.get('CXX_target'))


def StripPrefix(arg, prefix):
  if arg.startswith(prefix):
    return arg[len(prefix):]
  return arg


def QuoteShellArgument(arg, flavor):
  """Quote a string such that it will be interpreted as a single argument
  by the shell."""
  # Rather than attempting to enumerate the bad shell characters, just
  # whitelist common OK ones and quote anything else.
  if re.match(r'^[a-zA-Z0-9_=.\\/-]+$', arg):
    return arg  # No quoting necessary.
  if flavor == 'win':
    return gyp.msvs_emulation.QuoteForRspFile(arg)
  return "'" + arg.replace("'", "'" + '"\'"' + "'")  + "'"


def Define(d, flavor):
  """Takes a preprocessor define and returns a -D parameter that's ninja- and
  shell-escaped."""
  if flavor == 'win':
    # cl.exe replaces literal # characters with = in preprocesor definitions for
    # some reason. Octal-encode to work around that.
    d = d.replace('#', '\\%03o' % ord('#'))
  return QuoteShellArgument(ninja_syntax.escape('-D' + d), flavor)


def InvertRelativePath(path):
  """Given a relative path like foo/bar, return the inverse relative path:
  the path from the relative path back to the origin dir.

  E.g. os.path.normpath(os.path.join(path, InvertRelativePath(path)))
  should always produce the empty string."""

  if not path:
    return path
  # Only need to handle relative paths into subdirectories for now.
  assert '..' not in path, path
  depth = len(path.split(os.path.sep))
  return os.path.sep.join(['..'] * depth)


class Target:
  """Target represents the paths used within a single gyp target.

  Conceptually, building a single target A is a series of steps:

  1) actions/rules/copies  generates source/resources/etc.
  2) compiles              generates .o files
  3) link                  generates a binary (library/executable)
  4) bundle                merges the above in a mac bundle

  (Any of these steps can be optional.)

  From a build ordering perspective, a dependent target B could just
  depend on the last output of this series of steps.

  But some dependent commands sometimes need to reach inside the box.
  For example, when linking B it needs to get the path to the static
  library generated by A.

  This object stores those paths.  To keep things simple, member
  variables only store concrete paths to single files, while methods
  compute derived values like "the last output of the target".
  """
  def __init__(self, type):
    # Gyp type ("static_library", etc.) of this target.
    self.type = type
    # File representing whether any input dependencies necessary for
    # dependent actions have completed.
    self.preaction_stamp = None
    # File representing whether any input dependencies necessary for
    # dependent compiles have completed.
    self.precompile_stamp = None
    # File representing the completion of actions/rules/copies, if any.
    self.actions_stamp = None
    # Path to the output of the link step, if any.
    self.binary = None
    # Path to the file representing the completion of building the bundle,
    # if any.
    self.bundle = None
    # On Windows, incremental linking requires linking against all the .objs
    # that compose a .lib (rather than the .lib itself). That list is stored
    # here.
    self.component_objs = None
    # Windows only. The import .lib is the output of a build step, but
    # because dependents only link against the lib (not both the lib and the
    # dll) we keep track of the import library here.
    self.import_lib = None

  def Linkable(self):
    """Return true if this is a target that can be linked against."""
    return self.type in ('static_library', 'shared_library')

  def UsesToc(self, flavor):
    """Return true if the target should produce a restat rule based on a TOC
    file."""
    # For bundles, the .TOC should be produced for the binary, not for
    # FinalOutput(). But the naive approach would put the TOC file into the
    # bundle, so don't do this for bundles for now.
    if flavor == 'win' or self.bundle:
      return False
    return self.type in ('shared_library', 'loadable_module')

  def PreActionInput(self, flavor):
    """Return the path, if any, that should be used as a dependency of
    any dependent action step."""
    if self.UsesToc(flavor):
      return self.FinalOutput() + '.TOC'
    return self.FinalOutput() or self.preaction_stamp

  def PreCompileInput(self):
    """Return the path, if any, that should be used as a dependency of
    any dependent compile step."""
    return self.actions_stamp or self.precompile_stamp

  def FinalOutput(self):
    """Return the last output of the target, which depends on all prior
    steps."""
    return self.bundle or self.binary or self.actions_stamp


# A small discourse on paths as used within the Ninja build:
# All files we produce (both at gyp and at build time) appear in the
# build directory (e.g. out/Debug).
#
# Paths within a given .gyp file are always relative to the directory
# containing the .gyp file.  Call these "gyp paths".  This includes
# sources as well as the starting directory a given gyp rule/action
# expects to be run from.  We call the path from the source root to
# the gyp file the "base directory" within the per-.gyp-file
# NinjaWriter code.
#
# All paths as written into the .ninja files are relative to the build
# directory.  Call these paths "ninja paths".
#
# We translate between these two notions of paths with two helper
# functions:
#
# - GypPathToNinja translates a gyp path (i.e. relative to the .gyp file)
#   into the equivalent ninja path.
#
# - GypPathToUniqueOutput translates a gyp path into a ninja path to write
#   an output file; the result can be namespaced such that it is unique
#   to the input file name as well as the output target name.

class NinjaWriter:
  def __init__(self, qualified_target, target_outputs, base_dir, build_dir,
               output_file, flavor, abs_build_dir=None):
    """
    base_dir: path from source root to directory containing this gyp file,
              by gyp semantics, all input paths are relative to this
    build_dir: path from source root to build output
    abs_build_dir: absolute path to the build directory
    """

    self.qualified_target = qualified_target
    self.target_outputs = target_outputs
    self.base_dir = base_dir
    self.build_dir = build_dir
    self.ninja = ninja_syntax.Writer(output_file)
    self.flavor = flavor
    self.abs_build_dir = abs_build_dir
    self.obj_ext = '.obj' if flavor == 'win' else '.o'
    if flavor == 'win':
      # See docstring of msvs_emulation.GenerateEnvironmentFiles().
      self.win_env = {}
      for arch in ('x86', 'x64'):
        self.win_env[arch] = 'environment.' + arch

    # Relative path from build output dir to base dir.
    self.build_to_base = os.path.join(InvertRelativePath(build_dir), base_dir)
    # Relative path from base dir to build dir.
    self.base_to_build = os.path.join(InvertRelativePath(base_dir), build_dir)

  def ExpandSpecial(self, path, product_dir=None):
    """Expand specials like $!PRODUCT_DIR in |path|.

    If |product_dir| is None, assumes the cwd is already the product
    dir.  Otherwise, |product_dir| is the relative path to the product
    dir.
    """

    PRODUCT_DIR = '$!PRODUCT_DIR'
    if PRODUCT_DIR in path:
      if product_dir:
        path = path.replace(PRODUCT_DIR, product_dir)
      else:
        path = path.replace(PRODUCT_DIR + '/', '')
        path = path.replace(PRODUCT_DIR + '\\', '')
        path = path.replace(PRODUCT_DIR, '.')

    INTERMEDIATE_DIR = '$!INTERMEDIATE_DIR'
    if INTERMEDIATE_DIR in path:
      int_dir = self.GypPathToUniqueOutput('gen')
      # GypPathToUniqueOutput generates a path relative to the product dir,
      # so insert product_dir in front if it is provided.
      path = path.replace(INTERMEDIATE_DIR,
                          os.path.join(product_dir or '', int_dir))

    CONFIGURATION_NAME = '$|CONFIGURATION_NAME'
    path = path.replace(CONFIGURATION_NAME, self.config_name)

    return path

  def ExpandRuleVariables(self, path, root, dirname, source, ext, name):
    if self.flavor == 'win':
      path = self.msvs_settings.ConvertVSMacros(
          path, config=self.config_name)
    path = path.replace(generator_default_variables['RULE_INPUT_ROOT'], root)
    path = path.replace(generator_default_variables['RULE_INPUT_DIRNAME'],
                        dirname)
    path = path.replace(generator_default_variables['RULE_INPUT_PATH'], source)
    path = path.replace(generator_default_variables['RULE_INPUT_EXT'], ext)
    path = path.replace(generator_default_variables['RULE_INPUT_NAME'], name)
    return path

  def GypPathToNinja(self, path, env=None):
    """Translate a gyp path to a ninja path, optionally expanding environment
    variable references in |path| with |env|.

    See the above discourse on path conversions."""
    if env:
      if self.flavor == 'mac':
        path = gyp.xcode_emulation.ExpandEnvVars(path, env)
      elif self.flavor == 'win':
        path = gyp.msvs_emulation.ExpandMacros(path, env)
    if path.startswith('$!'):
      expanded = self.ExpandSpecial(path)
      if self.flavor == 'win':
        expanded = os.path.normpath(expanded)
      return expanded
    if '$|' in path:
      path =  self.ExpandSpecial(path)
    assert '$' not in path, path
    return os.path.normpath(os.path.join(self.build_to_base, path))

  def GypPathToUniqueOutput(self, path, qualified=True):
    """Translate a gyp path to a ninja path for writing output.

    If qualified is True, qualify the resulting filename with the name
    of the target.  This is necessary when e.g. compiling the same
    path twice for two separate output targets.

    See the above discourse on path conversions."""

    path = self.ExpandSpecial(path)
    assert not path.startswith('$'), path

    # Translate the path following this scheme:
    #   Input: foo/bar.gyp, target targ, references baz/out.o
    #   Output: obj/foo/baz/targ.out.o (if qualified)
    #           obj/foo/baz/out.o (otherwise)
    #     (and obj.host instead of obj for cross-compiles)
    #
    # Why this scheme and not some other one?
    # 1) for a given input, you can compute all derived outputs by matching
    #    its path, even if the input is brought via a gyp file with '..'.
    # 2) simple files like libraries and stamps have a simple filename.

    obj = 'obj'
    if self.toolset != 'target':
      obj += '.' + self.toolset

    path_dir, path_basename = os.path.split(path)
    if qualified:
      path_basename = self.name + '.' + path_basename
    return os.path.normpath(os.path.join(obj, self.base_dir, path_dir,
                                         path_basename))

  def WriteCollapsedDependencies(self, name, targets):
    """Given a list of targets, return a path for a single file
    representing the result of building all the targets or None.

    Uses a stamp file if necessary."""

    assert targets == filter(None, targets), targets
    if len(targets) == 0:
      return None
    if len(targets) > 1:
      stamp = self.GypPathToUniqueOutput(name + '.stamp')
      targets = self.ninja.build(stamp, 'stamp', targets)
      self.ninja.newline()
    return targets[0]

  def WriteSpec(self, spec, config_name, generator_flags,
      case_sensitive_filesystem):
    """The main entry point for NinjaWriter: write the build rules for a spec.

    Returns a Target object, which represents the output paths for this spec.
    Returns None if there are no outputs (e.g. a settings-only 'none' type
    target)."""

    self.config_name = config_name
    self.name = spec['target_name']
    self.toolset = spec['toolset']
    config = spec['configurations'][config_name]
    self.target = Target(spec['type'])
    self.is_standalone_static_library = bool(
        spec.get('standalone_static_library', 0))

    self.is_mac_bundle = gyp.xcode_emulation.IsMacBundle(self.flavor, spec)
    self.xcode_settings = self.msvs_settings = None
    if self.flavor == 'mac':
      self.xcode_settings = gyp.xcode_emulation.XcodeSettings(spec)
    if self.flavor == 'win':
      self.msvs_settings = gyp.msvs_emulation.MsvsSettings(spec,
                                                           generator_flags)
      arch = self.msvs_settings.GetArch(config_name)
      self.ninja.variable('arch', self.win_env[arch])

    # Compute predepends for all rules.
    # actions_depends is the dependencies this target depends on before running
    # any of its action/rule/copy steps.
    # compile_depends is the dependencies this target depends on before running
    # any of its compile steps.
    actions_depends = []
    compile_depends = []
    # TODO(evan): it is rather confusing which things are lists and which
    # are strings.  Fix these.
    if 'dependencies' in spec:
      for dep in spec['dependencies']:
        if dep in self.target_outputs:
          target = self.target_outputs[dep]
          actions_depends.append(target.PreActionInput(self.flavor))
          compile_depends.append(target.PreCompileInput())
      actions_depends = filter(None, actions_depends)
      compile_depends = filter(None, compile_depends)
      actions_depends = self.WriteCollapsedDependencies('actions_depends',
                                                        actions_depends)
      compile_depends = self.WriteCollapsedDependencies('compile_depends',
                                                        compile_depends)
      self.target.preaction_stamp = actions_depends
      self.target.precompile_stamp = compile_depends

    # Write out actions, rules, and copies.  These must happen before we
    # compile any sources, so compute a list of predependencies for sources
    # while we do it.
    extra_sources = []
    mac_bundle_depends = []
    self.target.actions_stamp = self.WriteActionsRulesCopies(
        spec, extra_sources, actions_depends, mac_bundle_depends)

    # If we have actions/rules/copies, we depend directly on those, but
    # otherwise we depend on dependent target's actions/rules/copies etc.
    # We never need to explicitly depend on previous target's link steps,
    # because no compile ever depends on them.
    compile_depends_stamp = (self.target.actions_stamp or compile_depends)

    # Write out the compilation steps, if any.
    link_deps = []
    sources = spec.get('sources', []) + extra_sources
    if sources:
      pch = None
      if self.flavor == 'win':
        gyp.msvs_emulation.VerifyMissingSources(
            sources, self.abs_build_dir, generator_flags, self.GypPathToNinja)
        pch = gyp.msvs_emulation.PrecompiledHeader(
            self.msvs_settings, config_name, self.GypPathToNinja)
      else:
        pch = gyp.xcode_emulation.MacPrefixHeader(
            self.xcode_settings, self.GypPathToNinja,
            lambda path, lang: self.GypPathToUniqueOutput(path + '-' + lang))
      link_deps = self.WriteSources(
          config_name, config, sources, compile_depends_stamp, pch,
          case_sensitive_filesystem, spec)
      # Some actions/rules output 'sources' that are already object files.
      link_deps += [self.GypPathToNinja(f)
          for f in sources if f.endswith(self.obj_ext)]

    if self.flavor == 'win' and self.target.type == 'static_library':
      self.target.component_objs = link_deps

    # Write out a link step, if needed.
    output = None
    if link_deps or self.target.actions_stamp or actions_depends:
      output = self.WriteTarget(spec, config_name, config, link_deps,
                                self.target.actions_stamp or actions_depends)
      if self.is_mac_bundle:
        mac_bundle_depends.append(output)

    # Bundle all of the above together, if needed.
    if self.is_mac_bundle:
      output = self.WriteMacBundle(spec, mac_bundle_depends)

    if not output:
      return None

    assert self.target.FinalOutput(), output
    return self.target

  def _WinIdlRule(self, source, prebuild, outputs):
    """Handle the implicit VS .idl rule for one source file. Fills |outputs|
    with files that are generated."""
    outdir, output, vars, flags = self.msvs_settings.GetIdlBuildData(
        source, self.config_name)
    outdir = self.GypPathToNinja(outdir)
    def fix_path(path, rel=None):
      path = os.path.join(outdir, path)
      dirname, basename = os.path.split(source)
      root, ext = os.path.splitext(basename)
      path = self.ExpandRuleVariables(
          path, root, dirname, source, ext, basename)
      if rel:
        path = os.path.relpath(path, rel)
      return path
    vars = [(name, fix_path(value, outdir)) for name, value in vars]
    output = [fix_path(p) for p in output]
    vars.append(('outdir', outdir))
    vars.append(('idlflags', flags))
    input = self.GypPathToNinja(source)
    self.ninja.build(output, 'idl', input,
        variables=vars, order_only=prebuild)
    outputs.extend(output)

  def WriteWinIdlFiles(self, spec, prebuild):
    """Writes rules to match MSVS's implicit idl handling."""
    assert self.flavor == 'win'
    if self.msvs_settings.HasExplicitIdlRules(spec):
      return []
    outputs = []
    for source in filter(lambda x: x.endswith('.idl'), spec['sources']):
      self._WinIdlRule(source, prebuild, outputs)
    return outputs

  def WriteActionsRulesCopies(self, spec, extra_sources, prebuild,
                              mac_bundle_depends):
    """Write out the Actions, Rules, and Copies steps.  Return a path
    representing the outputs of these steps."""
    outputs = []
    extra_mac_bundle_resources = []

    if 'actions' in spec:
      outputs += self.WriteActions(spec['actions'], extra_sources, prebuild,
                                   extra_mac_bundle_resources)
    if 'rules' in spec:
      outputs += self.WriteRules(spec['rules'], extra_sources, prebuild,
                                 extra_mac_bundle_resources)
    if 'copies' in spec:
      outputs += self.WriteCopies(spec['copies'], prebuild, mac_bundle_depends)

    if 'sources' in spec and self.flavor == 'win':
      outputs += self.WriteWinIdlFiles(spec, prebuild)

    stamp = self.WriteCollapsedDependencies('actions_rules_copies', outputs)

    if self.is_mac_bundle:
      mac_bundle_resources = spec.get('mac_bundle_resources', []) + \
                             extra_mac_bundle_resources
      self.WriteMacBundleResources(mac_bundle_resources, mac_bundle_depends)
      self.WriteMacInfoPlist(mac_bundle_depends)

    return stamp

  def GenerateDescription(self, verb, message, fallback):
    """Generate and return a description of a build step.

    |verb| is the short summary, e.g. ACTION or RULE.
    |message| is a hand-written description, or None if not available.
    |fallback| is the gyp-level name of the step, usable as a fallback.
    """
    if self.toolset != 'target':
      verb += '(%s)' % self.toolset
    if message:
      return '%s %s' % (verb, self.ExpandSpecial(message))
    else:
      return '%s %s: %s' % (verb, self.name, fallback)

  def WriteActions(self, actions, extra_sources, prebuild,
                   extra_mac_bundle_resources):
    # Actions cd into the base directory.
    env = self.GetSortedXcodeEnv()
    if self.flavor == 'win':
      env = self.msvs_settings.GetVSMacroEnv(
          '$!PRODUCT_DIR', config=self.config_name)
    all_outputs = []
    for action in actions:
      # First write out a rule for the action.
      name = '%s_%s' % (action['action_name'],
                        hashlib.md5(self.qualified_target).hexdigest())
      description = self.GenerateDescription('ACTION',
                                             action.get('message', None),
                                             name)
      is_cygwin = (self.msvs_settings.IsRuleRunUnderCygwin(action)
                   if self.flavor == 'win' else False)
      args = action['action']
      rule_name, _ = self.WriteNewNinjaRule(name, args, description,
                                            is_cygwin, env=env)

      inputs = [self.GypPathToNinja(i, env) for i in action['inputs']]
      if int(action.get('process_outputs_as_sources', False)):
        extra_sources += action['outputs']
      if int(action.get('process_outputs_as_mac_bundle_resources', False)):
        extra_mac_bundle_resources += action['outputs']
      outputs = [self.GypPathToNinja(o, env) for o in action['outputs']]

      # Then write out an edge using the rule.
      self.ninja.build(outputs, rule_name, inputs,
                       order_only=prebuild)
      all_outputs += outputs

      self.ninja.newline()

    return all_outputs

  def WriteRules(self, rules, extra_sources, prebuild,
                 extra_mac_bundle_resources):
    env = self.GetSortedXcodeEnv()
    all_outputs = []
    for rule in rules:
      # First write out a rule for the rule action.
      name = '%s_%s' % (rule['rule_name'],
                        hashlib.md5(self.qualified_target).hexdigest())
      # Skip a rule with no action and no inputs.
      if 'action' not in rule and not rule.get('rule_sources', []):
        continue
      args = rule['action']
      description = self.GenerateDescription(
          'RULE',
          rule.get('message', None),
          ('%s ' + generator_default_variables['RULE_INPUT_PATH']) % name)
      is_cygwin = (self.msvs_settings.IsRuleRunUnderCygwin(rule)
                   if self.flavor == 'win' else False)
      rule_name, args = self.WriteNewNinjaRule(
          name, args, description, is_cygwin, env=env)

      # TODO: if the command references the outputs directly, we should
      # simplify it to just use $out.

      # Rules can potentially make use of some special variables which
      # must vary per source file.
      # Compute the list of variables we'll need to provide.
      special_locals = ('source', 'root', 'dirname', 'ext', 'name')
      needed_variables = set(['source'])
      for argument in args:
        for var in special_locals:
          if ('${%s}' % var) in argument:
            needed_variables.add(var)

      def cygwin_munge(path):
        if is_cygwin:
          return path.replace('\\', '/')
        return path

      # For each source file, write an edge that generates all the outputs.
      for source in rule.get('rule_sources', []):
        dirname, basename = os.path.split(source)
        root, ext = os.path.splitext(basename)

        # Gather the list of inputs and outputs, expanding $vars if possible.
        outputs = [self.ExpandRuleVariables(o, root, dirname,
                                            source, ext, basename)
                   for o in rule['outputs']]
        inputs = [self.ExpandRuleVariables(i, root, dirname,
                                           source, ext, basename)
                  for i in rule.get('inputs', [])]

        if int(rule.get('process_outputs_as_sources', False)):
          extra_sources += outputs
        if int(rule.get('process_outputs_as_mac_bundle_resources', False)):
          extra_mac_bundle_resources += outputs

        extra_bindings = []
        for var in needed_variables:
          if var == 'root':
            extra_bindings.append(('root', cygwin_munge(root)))
          elif var == 'dirname':
            extra_bindings.append(('dirname', cygwin_munge(dirname)))
          elif var == 'source':
            # '$source' is a parameter to the rule action, which means
            # it shouldn't be converted to a Ninja path.  But we don't
            # want $!PRODUCT_DIR in there either.
            source_expanded = self.ExpandSpecial(source, self.base_to_build)
            extra_bindings.append(('source', cygwin_munge(source_expanded)))
          elif var == 'ext':
            extra_bindings.append(('ext', ext))
          elif var == 'name':
            extra_bindings.append(('name', cygwin_munge(basename)))
          else:
            assert var == None, repr(var)

        inputs = [self.GypPathToNinja(i, env) for i in inputs]
        outputs = [self.GypPathToNinja(o, env) for o in outputs]
        extra_bindings.append(('unique_name',
            hashlib.md5(outputs[0]).hexdigest()))
        self.ninja.build(outputs, rule_name, self.GypPathToNinja(source),
                         implicit=inputs,
                         order_only=prebuild,
                         variables=extra_bindings)

        all_outputs.extend(outputs)

    return all_outputs

  def WriteCopies(self, copies, prebuild, mac_bundle_depends):
    outputs = []
    env = self.GetSortedXcodeEnv()
    for copy in copies:
      for path in copy['files']:
        # Normalize the path so trailing slashes don't confuse us.
        path = os.path.normpath(path)
        basename = os.path.split(path)[1]
        src = self.GypPathToNinja(path, env)
        dst = self.GypPathToNinja(os.path.join(copy['destination'], basename),
                                  env)
        outputs += self.ninja.build(dst, 'copy', src, order_only=prebuild)
        if self.is_mac_bundle:
          # gyp has mac_bundle_resources to copy things into a bundle's
          # Resources folder, but there's no built-in way to copy files to other
          # places in the bundle. Hence, some targets use copies for this. Check
          # if this file is copied into the current bundle, and if so add it to
          # the bundle depends so that dependent targets get rebuilt if the copy
          # input changes.
          if dst.startswith(self.xcode_settings.GetBundleContentsFolderPath()):
            mac_bundle_depends.append(dst)

    return outputs

  def WriteMacBundleResources(self, resources, bundle_depends):
    """Writes ninja edges for 'mac_bundle_resources'."""
    for output, res in gyp.xcode_emulation.GetMacBundleResources(
        self.ExpandSpecial(generator_default_variables['PRODUCT_DIR']),
        self.xcode_settings, map(self.GypPathToNinja, resources)):
      self.ninja.build(output, 'mac_tool', res,
                       variables=[('mactool_cmd', 'copy-bundle-resource')])
      bundle_depends.append(output)

  def WriteMacInfoPlist(self, bundle_depends):
    """Write build rules for bundle Info.plist files."""
    info_plist, out, defines, extra_env = gyp.xcode_emulation.GetMacInfoPlist(
        self.ExpandSpecial(generator_default_variables['PRODUCT_DIR']),
        self.xcode_settings, self.GypPathToNinja)
    if not info_plist:
      return
    if defines:
      # Create an intermediate file to store preprocessed results.
      intermediate_plist = self.GypPathToUniqueOutput(
          os.path.basename(info_plist))
      defines = ' '.join([Define(d, self.flavor) for d in defines])
      info_plist = self.ninja.build(intermediate_plist, 'infoplist', info_plist,
                                    variables=[('defines',defines)])

    env = self.GetSortedXcodeEnv(additional_settings=extra_env)
    env = self.ComputeExportEnvString(env)

    self.ninja.build(out, 'mac_tool', info_plist,
                     variables=[('mactool_cmd', 'copy-info-plist'),
                                ('env', env)])
    bundle_depends.append(out)

  def WriteSources(self, config_name, config, sources, predepends,
                   precompiled_header, case_sensitive_filesystem, spec):
    """Write build rules to compile all of |sources|."""
    if self.toolset == 'host':
      self.ninja.variable('ar', '$ar_host')
      self.ninja.variable('cc', '$cc_host')
      self.ninja.variable('cxx', '$cxx_host')
      self.ninja.variable('ld', '$ld_host')

    extra_defines = []
    if self.flavor == 'mac':
      cflags = self.xcode_settings.GetCflags(config_name)
      cflags_c = self.xcode_settings.GetCflagsC(config_name)
      cflags_cc = self.xcode_settings.GetCflagsCC(config_name)
      cflags_objc = ['$cflags_c'] + \
                    self.xcode_settings.GetCflagsObjC(config_name)
      cflags_objcc = ['$cflags_cc'] + \
                     self.xcode_settings.GetCflagsObjCC(config_name)
    elif self.flavor == 'win':
      cflags = self.msvs_settings.GetCflags(config_name)
      cflags_c = self.msvs_settings.GetCflagsC(config_name)
      cflags_cc = self.msvs_settings.GetCflagsCC(config_name)
      extra_defines = self.msvs_settings.GetComputedDefines(config_name)
      self.WriteVariableList('pdbname', [self.name + '.pdb'])
      self.WriteVariableList('pchprefix', [self.name])
    else:
      cflags = config.get('cflags', [])
      cflags_c = config.get('cflags_c', [])
      cflags_cc = config.get('cflags_cc', [])

    defines = config.get('defines', []) + extra_defines
    self.WriteVariableList('defines', [Define(d, self.flavor) for d in defines])
    if self.flavor == 'win':
      self.WriteVariableList('rcflags',
          [QuoteShellArgument(self.ExpandSpecial(f), self.flavor)
           for f in self.msvs_settings.GetRcflags(config_name,
                                                  self.GypPathToNinja)])

    include_dirs = config.get('include_dirs', [])
    if self.flavor == 'win':
      include_dirs = self.msvs_settings.AdjustIncludeDirs(include_dirs,
                                                          config_name)
    self.WriteVariableList('includes',
        [QuoteShellArgument('-I' + self.GypPathToNinja(i), self.flavor)
         for i in include_dirs])

    pch_commands = precompiled_header.GetPchBuildCommands()
    if self.flavor == 'mac':
      self.WriteVariableList('cflags_pch_c',
                             [precompiled_header.GetInclude('c')])
      self.WriteVariableList('cflags_pch_cc',
                             [precompiled_header.GetInclude('cc')])
      self.WriteVariableList('cflags_pch_objc',
                             [precompiled_header.GetInclude('m')])
      self.WriteVariableList('cflags_pch_objcc',
                             [precompiled_header.GetInclude('mm')])

    self.WriteVariableList('cflags', map(self.ExpandSpecial, cflags))
    self.WriteVariableList('cflags_c', map(self.ExpandSpecial, cflags_c))
    self.WriteVariableList('cflags_cc', map(self.ExpandSpecial, cflags_cc))
    if self.flavor == 'mac':
      self.WriteVariableList('cflags_objc', map(self.ExpandSpecial,
                                                cflags_objc))
      self.WriteVariableList('cflags_objcc', map(self.ExpandSpecial,
                                                 cflags_objcc))
    self.ninja.newline()
    outputs = []
    for source in sources:
      filename, ext = os.path.splitext(source)
      ext = ext[1:]
      obj_ext = self.obj_ext
      if ext in ('cc', 'cpp', 'cxx'):
        command = 'cxx'
      elif ext == 'c' or (ext == 'S' and self.flavor != 'win'):
        command = 'cc'
      elif ext == 's' and self.flavor != 'win':  # Doesn't generate .o.d files.
        command = 'cc_s'
      elif (self.flavor == 'win' and ext == 'asm' and
            self.msvs_settings.GetArch(config_name) == 'x86' and
            not self.msvs_settings.HasExplicitAsmRules(spec)):
        # Asm files only get auto assembled for x86 (not x64).
        command = 'asm'
        # Add the _asm suffix as msvs is capable of handling .cc and
        # .asm files of the same name without collision.
        obj_ext = '_asm.obj'
      elif self.flavor == 'mac' and ext == 'm':
        command = 'objc'
      elif self.flavor == 'mac' and ext == 'mm':
        command = 'objcxx'
      elif self.flavor == 'win' and ext == 'rc':
        command = 'rc'
        obj_ext = '.res'
      else:
        # Ignore unhandled extensions.
        continue
      input = self.GypPathToNinja(source)
      output = self.GypPathToUniqueOutput(filename + obj_ext)
      # Ninja's depfile handling gets confused when the case of a filename
      # changes on a case-insensitive file system. To work around that, always
      # convert .o filenames to lowercase on such file systems. See
      # https://github.com/martine/ninja/issues/402 for details.
      if not case_sensitive_filesystem:
        output = output.lower()
      implicit = precompiled_header.GetObjDependencies([input], [output])
      self.ninja.build(output, command, input,
                       implicit=[gch for _, _, gch in implicit],
                       order_only=predepends)
      outputs.append(output)

    self.WritePchTargets(pch_commands)

    self.ninja.newline()
    return outputs

  def WritePchTargets(self, pch_commands):
    """Writes ninja rules to compile prefix headers."""
    if not pch_commands:
      return

    for gch, lang_flag, lang, input in pch_commands:
      var_name = {
        'c': 'cflags_pch_c',
        'cc': 'cflags_pch_cc',
        'm': 'cflags_pch_objc',
        'mm': 'cflags_pch_objcc',
      }[lang]

      map = { 'c': 'cc', 'cc': 'cxx', 'm': 'objc', 'mm': 'objcxx', }
      if self.flavor == 'win':
        map.update({'c': 'cc_pch', 'cc': 'cxx_pch'})
      cmd = map.get(lang)
      self.ninja.build(gch, cmd, input, variables=[(var_name, lang_flag)])

  def WriteLink(self, spec, config_name, config, link_deps):
    """Write out a link step. Fills out target.binary. """

    command = {
      'executable':      'link',
      'loadable_module': 'solink_module',
      'shared_library':  'solink',
    }[spec['type']]

    implicit_deps = set()
    solibs = set()

    if 'dependencies' in spec:
      # Two kinds of dependencies:
      # - Linkable dependencies (like a .a or a .so): add them to the link line.
      # - Non-linkable dependencies (like a rule that generates a file
      #   and writes a stamp file): add them to implicit_deps
      extra_link_deps = set()
      for dep in spec['dependencies']:
        target = self.target_outputs.get(dep)
        if not target:
          continue
        linkable = target.Linkable()
        if linkable:
          if (self.flavor == 'win' and
              target.component_objs and
              self.msvs_settings.IsUseLibraryDependencyInputs(config_name)):
            extra_link_deps |= set(target.component_objs)
          elif self.flavor == 'win' and target.import_lib:
            extra_link_deps.add(target.import_lib)
          elif target.UsesToc(self.flavor):
            solibs.add(target.binary)
            implicit_deps.add(target.binary + '.TOC')
          else:
            extra_link_deps.add(target.binary)

        final_output = target.FinalOutput()
        if not linkable or final_output != target.binary:
          implicit_deps.add(final_output)

      link_deps.extend(list(extra_link_deps))

    extra_bindings = []
    if self.is_mac_bundle:
      output = self.ComputeMacBundleBinaryOutput()
    else:
      output = self.ComputeOutput(spec)
      extra_bindings.append(('postbuilds',
                             self.GetPostbuildCommand(spec, output, output)))

    if self.flavor == 'mac':
      ldflags = self.xcode_settings.GetLdflags(config_name,
          self.ExpandSpecial(generator_default_variables['PRODUCT_DIR']),
          self.GypPathToNinja)
    elif self.flavor == 'win':
      libflags = self.msvs_settings.GetLibFlags(config_name,
                                                self.GypPathToNinja)
      self.WriteVariableList(
          'libflags', gyp.common.uniquer(map(self.ExpandSpecial, libflags)))
      is_executable = spec['type'] == 'executable'
      manifest_name = self.GypPathToUniqueOutput(
          self.ComputeOutputFileName(spec))
      ldflags, manifest_files = self.msvs_settings.GetLdflags(config_name,
          self.GypPathToNinja, self.ExpandSpecial, manifest_name, is_executable)
      self.WriteVariableList('manifests', manifest_files)
    else:
      ldflags = config.get('ldflags', [])
    self.WriteVariableList('ldflags',
                           gyp.common.uniquer(map(self.ExpandSpecial,
                                                  ldflags)))

    libraries = gyp.common.uniquer(map(self.ExpandSpecial,
                                       spec.get('libraries', [])))
    if self.flavor == 'mac':
      libraries = self.xcode_settings.AdjustLibraries(libraries)
    elif self.flavor == 'win':
      libraries = self.msvs_settings.AdjustLibraries(libraries)
    self.WriteVariableList('libs', libraries)

    self.target.binary = output

    if command in ('solink', 'solink_module'):
      extra_bindings.append(('soname', os.path.split(output)[1]))
      extra_bindings.append(('lib',
                            gyp.common.EncodePOSIXShellArgument(output)))
      if self.flavor == 'win':
        extra_bindings.append(('dll', output))
        if '/NOENTRY' not in ldflags:
          self.target.import_lib = output + '.lib'
          extra_bindings.append(('implibflag',
                                 '/IMPLIB:%s' % self.target.import_lib))
          output = [output, self.target.import_lib]
      else:
        output = [output, output + '.TOC']

    if len(solibs):
      extra_bindings.append(('solibs', gyp.common.EncodePOSIXShellList(solibs)))

    self.ninja.build(output, command, link_deps,
                     implicit=list(implicit_deps),
                     variables=extra_bindings)

  def WriteTarget(self, spec, config_name, config, link_deps, compile_deps):
    if spec['type'] == 'none':
      # TODO(evan): don't call this function for 'none' target types, as
      # it doesn't do anything, and we fake out a 'binary' with a stamp file.
      self.target.binary = compile_deps
    elif spec['type'] == 'static_library':
      self.target.binary = self.ComputeOutput(spec)
      variables = []
      postbuild = self.GetPostbuildCommand(
          spec, self.target.binary, self.target.binary)
      if postbuild:
        variables.append(('postbuilds', postbuild))
      if self.xcode_settings:
        variables.append(('libtool_flags',
                          self.xcode_settings.GetLibtoolflags(config_name)))
      if (self.flavor not in ('mac', 'win') and not
          self.is_standalone_static_library):
        self.ninja.build(self.target.binary, 'alink_thin', link_deps,
                         order_only=compile_deps, variables=variables)
      else:
        self.ninja.build(self.target.binary, 'alink', link_deps,
                         order_only=compile_deps, variables=variables)
    else:
      self.WriteLink(spec, config_name, config, link_deps)
    return self.target.binary

  def WriteMacBundle(self, spec, mac_bundle_depends):
    assert self.is_mac_bundle
    package_framework = spec['type'] in ('shared_library', 'loadable_module')
    output = self.ComputeMacBundleOutput()
    postbuild = self.GetPostbuildCommand(spec, output, self.target.binary,
                                         is_command_start=not package_framework)
    variables = []
    if postbuild:
      variables.append(('postbuilds', postbuild))
    if package_framework:
      variables.append(('version', self.xcode_settings.GetFrameworkVersion()))
      self.ninja.build(output, 'package_framework', mac_bundle_depends,
                       variables=variables)
    else:
      self.ninja.build(output, 'stamp', mac_bundle_depends,
                       variables=variables)
    self.target.bundle = output
    return output

  def GetSortedXcodeEnv(self, additional_settings=None):
    """Returns the variables Xcode would set for build steps."""
    assert self.abs_build_dir
    abs_build_dir = self.abs_build_dir
    return gyp.xcode_emulation.GetSortedXcodeEnv(
        self.xcode_settings, abs_build_dir,
        os.path.join(abs_build_dir, self.build_to_base), self.config_name,
        additional_settings)

  def GetSortedXcodePostbuildEnv(self):
    """Returns the variables Xcode would set for postbuild steps."""
    postbuild_settings = {}
    # CHROMIUM_STRIP_SAVE_FILE is a chromium-specific hack.
    # TODO(thakis): It would be nice to have some general mechanism instead.
    strip_save_file = self.xcode_settings.GetPerTargetSetting(
        'CHROMIUM_STRIP_SAVE_FILE')
    if strip_save_file:
      postbuild_settings['CHROMIUM_STRIP_SAVE_FILE'] = strip_save_file
    return self.GetSortedXcodeEnv(additional_settings=postbuild_settings)

  def GetPostbuildCommand(self, spec, output, output_binary,
                          is_command_start=False):
    """Returns a shell command that runs all the postbuilds, and removes
    |output| if any of them fails. If |is_command_start| is False, then the
    returned string will start with ' && '."""
    if not self.xcode_settings or spec['type'] == 'none' or not output:
      return ''
    output = QuoteShellArgument(output, self.flavor)
    target_postbuilds = self.xcode_settings.GetTargetPostbuilds(
        self.config_name,
        os.path.normpath(os.path.join(self.base_to_build, output)),
        QuoteShellArgument(
            os.path.normpath(os.path.join(self.base_to_build, output_binary)),
            self.flavor),
        quiet=True)
    postbuilds = gyp.xcode_emulation.GetSpecPostbuildCommands(spec, quiet=True)
    postbuilds = target_postbuilds + postbuilds
    if not postbuilds:
      return ''
    # Postbuilds expect to be run in the gyp file's directory, so insert an
    # implicit postbuild to cd to there.
    postbuilds.insert(0, gyp.common.EncodePOSIXShellList(
        ['cd', self.build_to_base]))
    env = self.ComputeExportEnvString(self.GetSortedXcodePostbuildEnv())
    # G will be non-null if any postbuild fails. Run all postbuilds in a
    # subshell.
    commands = env + ' (F=0; ' + \
        ' '.join([ninja_syntax.escape(command) + ' || F=$$?;'
                                 for command in postbuilds])
    command_string = (commands + ' exit $$F); G=$$?; '
                      # Remove the final output if any postbuild failed.
                      '((exit $$G) || rm -rf %s) ' % output + '&& exit $$G)')
    if is_command_start:
      return '(' + command_string + ' && '
    else:
      return '$ && (' + command_string

  def ComputeExportEnvString(self, env):
    """Given an environment, returns a string looking like
        'export FOO=foo; export BAR="${FOO} bar;'
    that exports |env| to the shell."""
    export_str = []
    for k, v in env:
      export_str.append('export %s=%s;' %
          (k, ninja_syntax.escape(gyp.common.EncodePOSIXShellArgument(v))))
    return ' '.join(export_str)

  def ComputeMacBundleOutput(self):
    """Return the 'output' (full output path) to a bundle output directory."""
    assert self.is_mac_bundle
    path = self.ExpandSpecial(generator_default_variables['PRODUCT_DIR'])
    return os.path.join(path, self.xcode_settings.GetWrapperName())

  def ComputeMacBundleBinaryOutput(self):
    """Return the 'output' (full output path) to the binary in a bundle."""
    assert self.is_mac_bundle
    path = self.ExpandSpecial(generator_default_variables['PRODUCT_DIR'])
    return os.path.join(path, self.xcode_settings.GetExecutablePath())

  def ComputeOutputFileName(self, spec, type=None):
    """Compute the filename of the final output for the current target."""
    if not type:
      type = spec['type']

    default_variables = copy.copy(generator_default_variables)
    CalculateVariables(default_variables, {'flavor': self.flavor})

    # Compute filename prefix: the product prefix, or a default for
    # the product type.
    DEFAULT_PREFIX = {
      'loadable_module': default_variables['SHARED_LIB_PREFIX'],
      'shared_library': default_variables['SHARED_LIB_PREFIX'],
      'static_library': default_variables['STATIC_LIB_PREFIX'],
      'executable': default_variables['EXECUTABLE_PREFIX'],
      }
    prefix = spec.get('product_prefix', DEFAULT_PREFIX.get(type, ''))

    # Compute filename extension: the product extension, or a default
    # for the product type.
    DEFAULT_EXTENSION = {
        'loadable_module': default_variables['SHARED_LIB_SUFFIX'],
        'shared_library': default_variables['SHARED_LIB_SUFFIX'],
        'static_library': default_variables['STATIC_LIB_SUFFIX'],
        'executable': default_variables['EXECUTABLE_SUFFIX'],
      }
    extension = spec.get('product_extension')
    if extension:
      extension = '.' + extension
    else:
      extension = DEFAULT_EXTENSION.get(type, '')

    if 'product_name' in spec:
      # If we were given an explicit name, use that.
      target = spec['product_name']
    else:
      # Otherwise, derive a name from the target name.
      target = spec['target_name']
      if prefix == 'lib':
        # Snip out an extra 'lib' from libs if appropriate.
        target = StripPrefix(target, 'lib')

    if type in ('static_library', 'loadable_module', 'shared_library',
                        'executable'):
      return '%s%s%s' % (prefix, target, extension)
    elif type == 'none':
      return '%s.stamp' % target
    else:
      raise Exception('Unhandled output type %s' % type)

  def ComputeOutput(self, spec, type=None):
    """Compute the path for the final output of the spec."""
    assert not self.is_mac_bundle or type

    if not type:
      type = spec['type']

    if self.flavor == 'win':
      override = self.msvs_settings.GetOutputName(self.config_name,
                                                  self.ExpandSpecial)
      if override:
        return override

    if self.flavor == 'mac' and type in (
        'static_library', 'executable', 'shared_library', 'loadable_module'):
      filename = self.xcode_settings.GetExecutablePath()
    else:
      filename = self.ComputeOutputFileName(spec, type)

    if 'product_dir' in spec:
      path = os.path.join(spec['product_dir'], filename)
      return self.ExpandSpecial(path)

    # Some products go into the output root, libraries go into shared library
    # dir, and everything else goes into the normal place.
    type_in_output_root = ['executable', 'loadable_module']
    if self.flavor == 'mac' and self.toolset == 'target':
      type_in_output_root += ['shared_library', 'static_library']
    elif self.flavor == 'win' and self.toolset == 'target':
      type_in_output_root += ['shared_library']

    if type in type_in_output_root or self.is_standalone_static_library:
      return filename
    elif type == 'shared_library':
      libdir = 'lib'
      if self.toolset != 'target':
        libdir = os.path.join('lib', '%s' % self.toolset)
      return os.path.join(libdir, filename)
    else:
      return self.GypPathToUniqueOutput(filename, qualified=False)

  def WriteVariableList(self, var, values):
    assert not isinstance(values, str)
    if values is None:
      values = []
    self.ninja.variable(var, ' '.join(values))

  def WriteNewNinjaRule(self, name, args, description, is_cygwin, env):
    """Write out a new ninja "rule" statement for a given command.

    Returns the name of the new rule, and a copy of |args| with variables
    expanded."""

    if self.flavor == 'win':
      args = [self.msvs_settings.ConvertVSMacros(
                  arg, self.base_to_build, config=self.config_name)
              for arg in args]
      description = self.msvs_settings.ConvertVSMacros(
          description, config=self.config_name)
    elif self.flavor == 'mac':
      # |env| is an empty list on non-mac.
      args = [gyp.xcode_emulation.ExpandEnvVars(arg, env) for arg in args]
      description = gyp.xcode_emulation.ExpandEnvVars(description, env)

    # TODO: we shouldn't need to qualify names; we do it because
    # currently the ninja rule namespace is global, but it really
    # should be scoped to the subninja.
    rule_name = self.name
    if self.toolset == 'target':
      rule_name += '.' + self.toolset
    rule_name += '.' + name
    rule_name = re.sub('[^a-zA-Z0-9_]', '_', rule_name)

    # Remove variable references, but not if they refer to the magic rule
    # variables.  This is not quite right, as it also protects these for
    # actions, not just for rules where they are valid. Good enough.
    protect = [ '${root}', '${dirname}', '${source}', '${ext}', '${name}' ]
    protect = '(?!' + '|'.join(map(re.escape, protect)) + ')'
    description = re.sub(protect + r'\$', '_', description)

    # gyp dictates that commands are run from the base directory.
    # cd into the directory before running, and adjust paths in
    # the arguments to point to the proper locations.
    rspfile = None
    rspfile_content = None
    args = [self.ExpandSpecial(arg, self.base_to_build) for arg in args]
    if self.flavor == 'win':
      rspfile = rule_name + '.$unique_name.rsp'
      # The cygwin case handles this inside the bash sub-shell.
      run_in = '' if is_cygwin else ' ' + self.build_to_base
      if is_cygwin:
        rspfile_content = self.msvs_settings.BuildCygwinBashCommandLine(
            args, self.build_to_base)
      else:
        rspfile_content = gyp.msvs_emulation.EncodeRspFileList(args)
      command = ('%s gyp-win-tool action-wrapper $arch ' % sys.executable +
                 rspfile + run_in)
    else:
      env = self.ComputeExportEnvString(env)
      command = gyp.common.EncodePOSIXShellList(args)
      command = 'cd %s; ' % self.build_to_base + env + command

    # GYP rules/actions express being no-ops by not touching their outputs.
    # Avoid executing downstream dependencies in this case by specifying
    # restat=1 to ninja.
    self.ninja.rule(rule_name, command, description, restat=True,
                    rspfile=rspfile, rspfile_content=rspfile_content)
    self.ninja.newline()

    return rule_name, args


def CalculateVariables(default_variables, params):
  """Calculate additional variables for use in the build (called by gyp)."""
  global generator_additional_non_configuration_keys
  global generator_additional_path_sections
  flavor = gyp.common.GetFlavor(params)
  if flavor == 'mac':
    default_variables.setdefault('OS', 'mac')
    default_variables.setdefault('SHARED_LIB_SUFFIX', '.dylib')
    default_variables.setdefault('SHARED_LIB_DIR',
                                 generator_default_variables['PRODUCT_DIR'])
    default_variables.setdefault('LIB_DIR',
                                 generator_default_variables['PRODUCT_DIR'])

    # Copy additional generator configuration data from Xcode, which is shared
    # by the Mac Ninja generator.
    import gyp.generator.xcode as xcode_generator
    generator_additional_non_configuration_keys = getattr(xcode_generator,
        'generator_additional_non_configuration_keys', [])
    generator_additional_path_sections = getattr(xcode_generator,
        'generator_additional_path_sections', [])
    global generator_extra_sources_for_rules
    generator_extra_sources_for_rules = getattr(xcode_generator,
        'generator_extra_sources_for_rules', [])
  elif flavor == 'win':
    default_variables.setdefault('OS', 'win')
    default_variables['EXECUTABLE_SUFFIX'] = '.exe'
    default_variables['STATIC_LIB_PREFIX'] = ''
    default_variables['STATIC_LIB_SUFFIX'] = '.lib'
    default_variables['SHARED_LIB_PREFIX'] = ''
    default_variables['SHARED_LIB_SUFFIX'] = '.dll'
    generator_flags = params.get('generator_flags', {})

    # Copy additional generator configuration data from VS, which is shared
    # by the Windows Ninja generator.
    import gyp.generator.msvs as msvs_generator
    generator_additional_non_configuration_keys = getattr(msvs_generator,
        'generator_additional_non_configuration_keys', [])
    generator_additional_path_sections = getattr(msvs_generator,
        'generator_additional_path_sections', [])

    # Set a variable so conditions can be based on msvs_version.
    msvs_version = gyp.msvs_emulation.GetVSVersion(generator_flags)
    default_variables['MSVS_VERSION'] = msvs_version.ShortName()

    # To determine processor word size on Windows, in addition to checking
    # PROCESSOR_ARCHITECTURE (which reflects the word size of the current
    # process), it is also necessary to check PROCESSOR_ARCHITEW6432 (which
    # contains the actual word size of the system when running thru WOW64).
    if ('64' in os.environ.get('PROCESSOR_ARCHITECTURE', '') or
        '64' in os.environ.get('PROCESSOR_ARCHITEW6432', '')):
      default_variables['MSVS_OS_BITS'] = 64
    else:
      default_variables['MSVS_OS_BITS'] = 32
  else:
    operating_system = flavor
    if flavor == 'android':
      operating_system = 'linux'  # Keep this legacy behavior for now.
    default_variables.setdefault('OS', operating_system)
    default_variables.setdefault('SHARED_LIB_SUFFIX', '.so')
    default_variables.setdefault('SHARED_LIB_DIR',
                                 os.path.join('$!PRODUCT_DIR', 'lib'))
    default_variables.setdefault('LIB_DIR',
                                 os.path.join('$!PRODUCT_DIR', 'obj'))


def OpenOutput(path, mode='w'):
  """Open |path| for writing, creating directories if necessary."""
  try:
    os.makedirs(os.path.dirname(path))
  except OSError:
    pass
  return open(path, mode)


def GenerateOutputForConfig(target_list, target_dicts, data, params,
                            config_name):
  options = params['options']
  flavor = gyp.common.GetFlavor(params)
  generator_flags = params.get('generator_flags', {})

  # generator_dir: relative path from pwd to where make puts build files.
  # Makes migrating from make to ninja easier, ninja doesn't put anything here.
  generator_dir = os.path.relpath(params['options'].generator_output or '.')

  # output_dir: relative path from generator_dir to the build directory.
  output_dir = generator_flags.get('output_dir', 'out')

  # build_dir: relative path from source root to our output files.
  # e.g. "out/Debug"
  build_dir = os.path.normpath(os.path.join(generator_dir,
                                            output_dir,
                                            config_name))

  toplevel_build = os.path.join(options.toplevel_dir, build_dir)

  master_ninja = ninja_syntax.Writer(
      OpenOutput(os.path.join(toplevel_build, 'build.ninja')),
      width=120)
  case_sensitive_filesystem = not os.path.exists(
      os.path.join(toplevel_build, 'BUILD.NINJA'))

  # Put build-time support tools in out/{config_name}.
  gyp.common.CopyTool(flavor, toplevel_build)

  # Grab make settings for CC/CXX.
  # The rules are
  # - The priority from low to high is gcc/g++, the 'make_global_settings' in
  #   gyp, the environment variable.
  # - If there is no 'make_global_settings' for CC.host/CXX.host or
  #   'CC_host'/'CXX_host' enviroment variable, cc_host/cxx_host should be set
  #   to cc/cxx.
  if flavor == 'win':
    cc = 'cl.exe'
    cxx = 'cl.exe'
    ld = 'link.exe'
    gyp.msvs_emulation.GenerateEnvironmentFiles(
        toplevel_build, generator_flags, OpenOutput)
    ld_host = '$ld'
  else:
    cc = 'gcc'
    cxx = 'g++'
    ld = '$cxx'
    ld_host = '$cxx_host'

  cc_host = None
  cxx_host = None
  cc_host_global_setting = None
  cxx_host_global_setting = None

  build_file, _, _ = gyp.common.ParseQualifiedTarget(target_list[0])
  make_global_settings = data[build_file].get('make_global_settings', [])
  build_to_root = InvertRelativePath(build_dir)
  for key, value in make_global_settings:
    if key == 'CC':
      cc = os.path.join(build_to_root, value)
    if key == 'CXX':
      cxx = os.path.join(build_to_root, value)
    if key == 'LD':
      ld = os.path.join(build_to_root, value)
    if key == 'CC.host':
      cc_host = os.path.join(build_to_root, value)
      cc_host_global_setting = value
    if key == 'CXX.host':
      cxx_host = os.path.join(build_to_root, value)
      cxx_host_global_setting = value
    if key == 'LD.host':
      ld_host = os.path.join(build_to_root, value)

  flock = 'flock'
  if flavor == 'mac':
    flock = './gyp-mac-tool flock'
  cc = GetEnvironFallback(['CC_target', 'CC'], cc)
  master_ninja.variable('cc', cc)
  cxx = GetEnvironFallback(['CXX_target', 'CXX'], cxx)
  master_ninja.variable('cxx', cxx)
  ld = GetEnvironFallback(['LD_target', 'LD'], ld)

  if not cc_host:
    cc_host = cc
  if not cxx_host:
    cxx_host = cxx

  if flavor == 'win':
    master_ninja.variable('ld', ld)
    master_ninja.variable('idl', 'midl.exe')
    master_ninja.variable('ar', 'lib.exe')
    master_ninja.variable('rc', 'rc.exe')
    master_ninja.variable('asm', 'ml.exe')
    master_ninja.variable('mt', 'mt.exe')
    master_ninja.variable('use_dep_database', '1')
  else:
    master_ninja.variable('ld', flock + ' linker.lock ' + ld)
    master_ninja.variable('ar', GetEnvironFallback(['AR_target', 'AR'], 'ar'))

  master_ninja.variable('ar_host', GetEnvironFallback(['AR_host'], 'ar'))
  cc_host = GetEnvironFallback(['CC_host'], cc_host)
  cxx_host = GetEnvironFallback(['CXX_host'], cxx_host)
  ld_host = GetEnvironFallback(['LD_host'], ld_host)

  # The environment variable could be used in 'make_global_settings', like
  # ['CC.host', '$(CC)'] or ['CXX.host', '$(CXX)'], transform them here.
  if '$(CC)' in cc_host and cc_host_global_setting:
    cc_host = cc_host_global_setting.replace('$(CC)', cc)
  if '$(CXX)' in cxx_host and cxx_host_global_setting:
    cxx_host = cxx_host_global_setting.replace('$(CXX)', cxx)
  master_ninja.variable('cc_host', cc_host)
  master_ninja.variable('cxx_host', cxx_host)
  if flavor == 'win':
    master_ninja.variable('ld_host', ld_host)
  else:
    master_ninja.variable('ld_host', flock + ' linker.lock ' + ld_host)

  master_ninja.newline()

  if flavor != 'win':
    master_ninja.rule(
      'cc',
      description='CC $out',
      command=('$cc -MMD -MF $out.d $defines $includes $cflags $cflags_c '
              '$cflags_pch_c -c $in -o $out'),
      depfile='$out.d')
    master_ninja.rule(
      'cc_s',
      description='CC $out',
      command=('$cc $defines $includes $cflags $cflags_c '
              '$cflags_pch_c -c $in -o $out'))
    master_ninja.rule(
      'cxx',
      description='CXX $out',
      command=('$cxx -MMD -MF $out.d $defines $includes $cflags $cflags_cc '
              '$cflags_pch_cc -c $in -o $out'),
      depfile='$out.d')
  else:
    # Template for compile commands mostly shared between compiling files
    # and generating PCH. In the case of PCH, the "output" is specified by /Fp
    # rather than /Fo (for object files), but we still need to specify an /Fo
    # when compiling PCH.
    cc_template = ('ninja -t msvc -r . -o $out -e $arch '
                   '-- '
                   '$cc /nologo /showIncludes /FC '
                   '@$out.rsp '
                   '$cflags_pch_c /c $in %(outspec)s /Fd$pdbname ')
    cxx_template = ('ninja -t msvc -r . -o $out -e $arch '
                    '-- '
                    '$cxx /nologo /showIncludes /FC '
                    '@$out.rsp '
                    '$cflags_pch_cc /c $in %(outspec)s $pchobj /Fd$pdbname ')
    master_ninja.rule(
      'cc',
      description='CC $out',
      command=cc_template % {'outspec': '/Fo$out'},
      depfile='$out.d',
      rspfile='$out.rsp',
      rspfile_content='$defines $includes $cflags $cflags_c')
    master_ninja.rule(
      'cc_pch',
      description='CC PCH $out',
      command=cc_template % {'outspec': '/Fp$out /Fo$out.obj'},
      depfile='$out.d',
      rspfile='$out.rsp',
      rspfile_content='$defines $includes $cflags $cflags_c')
    master_ninja.rule(
      'cxx',
      description='CXX $out',
      command=cxx_template % {'outspec': '/Fo$out'},
      depfile='$out.d',
      rspfile='$out.rsp',
      rspfile_content='$defines $includes $cflags $cflags_cc')
    master_ninja.rule(
      'cxx_pch',
      description='CXX PCH $out',
      command=cxx_template % {'outspec': '/Fp$out /Fo$out.obj'},
      depfile='$out.d',
      rspfile='$out.rsp',
      rspfile_content='$defines $includes $cflags $cflags_cc')
    master_ninja.rule(
      'idl',
      description='IDL $in',
      command=('%s gyp-win-tool midl-wrapper $arch $outdir '
               '$tlb $h $dlldata $iid $proxy $in '
               '$idlflags' % sys.executable))
    master_ninja.rule(
      'rc',
      description='RC $in',
      # Note: $in must be last otherwise rc.exe complains.
      command=('%s gyp-win-tool rc-wrapper '
               '$arch $rc $defines $includes $rcflags /fo$out $in' %
               sys.executable))
    master_ninja.rule(
      'asm',
      description='ASM $in',
      command=('%s gyp-win-tool asm-wrapper '
               '$arch $asm $defines $includes /c /Fo $out $in' %
               sys.executable))

  if flavor != 'mac' and flavor != 'win':
    master_ninja.rule(
      'alink',
      description='AR $out',
      command='rm -f $out && $ar rcs $out $in')
    master_ninja.rule(
      'alink_thin',
      description='AR $out',
      command='rm -f $out && $ar rcsT $out $in')

    # This allows targets that only need to depend on $lib's API to declare an
    # order-only dependency on $lib.TOC and avoid relinking such downstream
    # dependencies when $lib changes only in non-public ways.
    # The resulting string leaves an uninterpolated %{suffix} which
    # is used in the final substitution below.
    mtime_preserving_solink_base = (
        'if [ ! -e $lib -o ! -e ${lib}.TOC ]; then '
        '%(solink)s && %(extract_toc)s > ${lib}.TOC; else '
        '%(solink)s && %(extract_toc)s > ${lib}.tmp && '
        'if ! cmp -s ${lib}.tmp ${lib}.TOC; then mv ${lib}.tmp ${lib}.TOC ; '
        'fi; fi'
        % { 'solink':
              '$ld -shared $ldflags -o $lib -Wl,-soname=$soname %(suffix)s',
            'extract_toc':
              ('{ readelf -d ${lib} | grep SONAME ; '
               'nm -gD -f p ${lib} | cut -f1-2 -d\' \'; }')})

    master_ninja.rule(
      'solink',
      description='SOLINK $lib',
      restat=True,
      command=(mtime_preserving_solink_base % {
          'suffix': '-Wl,--whole-archive $in $solibs -Wl,--no-whole-archive '
          '$libs'}))
    master_ninja.rule(
      'solink_module',
      description='SOLINK(module) $lib',
      restat=True,
      command=(mtime_preserving_solink_base % {
          'suffix': '-Wl,--start-group $in $solibs -Wl,--end-group $libs'}))
    master_ninja.rule(
      'link',
      description='LINK $out',
      command=('$ld $ldflags -o $out -Wl,-rpath=\$$ORIGIN/lib '
               '-Wl,--start-group $in $solibs -Wl,--end-group $libs'))
  elif flavor == 'win':
    master_ninja.rule(
        'alink',
        description='LIB $out',
        command=('%s gyp-win-tool link-wrapper $arch '
                 '$ar /nologo /ignore:4221 /OUT:$out @$out.rsp' %
                 sys.executable),
        rspfile='$out.rsp',
        rspfile_content='$in_newline $libflags')
    dlldesc = 'LINK(DLL) $dll'
    dllcmd = ('%s gyp-win-tool link-wrapper $arch '
              '$ld /nologo $implibflag /DLL /OUT:$dll '
              '/PDB:$dll.pdb @$dll.rsp' % sys.executable)
    dllcmd += (' && %s gyp-win-tool manifest-wrapper $arch '
               '$mt -nologo -manifest $manifests -out:$dll.manifest' %
               sys.executable)
    master_ninja.rule('solink', description=dlldesc, command=dllcmd,
                      rspfile='$dll.rsp',
                      rspfile_content='$libs $in_newline $ldflags',
                      restat=True)
    master_ninja.rule('solink_module', description=dlldesc, command=dllcmd,
                      rspfile='$dll.rsp',
                      rspfile_content='$libs $in_newline $ldflags',
                      restat=True)
    # Note that ldflags goes at the end so that it has the option of
    # overriding default settings earlier in the command line.
    master_ninja.rule(
        'link',
        description='LINK $out',
        command=('%s gyp-win-tool link-wrapper $arch '
                 '$ld /nologo /OUT:$out /PDB:$out.pdb @$out.rsp && '
                 '%s gyp-win-tool manifest-wrapper $arch '
                 '$mt -nologo -manifest $manifests -out:$out.manifest' %
                 (sys.executable, sys.executable)),
        rspfile='$out.rsp',
        rspfile_content='$in_newline $libs $ldflags')
  else:
    master_ninja.rule(
      'objc',
      description='OBJC $out',
      command=('$cc -MMD -MF $out.d $defines $includes $cflags $cflags_objc '
               '$cflags_pch_objc -c $in -o $out'),
      depfile='$out.d')
    master_ninja.rule(
      'objcxx',
      description='OBJCXX $out',
      command=('$cxx -MMD -MF $out.d $defines $includes $cflags $cflags_objcc '
               '$cflags_pch_objcc -c $in -o $out'),
      depfile='$out.d')
    master_ninja.rule(
      'alink',
      description='LIBTOOL-STATIC $out, POSTBUILDS',
      command='rm -f $out && '
              './gyp-mac-tool filter-libtool libtool $libtool_flags '
              '-static -o $out $in'
              '$postbuilds')

    # Record the public interface of $lib in $lib.TOC. See the corresponding
    # comment in the posix section above for details.
    mtime_preserving_solink_base = (
        'if [ ! -e $lib -o ! -e ${lib}.TOC ] || '
             # Always force dependent targets to relink if this library
             # reexports something. Handling this correctly would require
             # recursive TOC dumping but this is rare in practice, so punt.
             'otool -l $lib | grep -q LC_REEXPORT_DYLIB ; then '
          '%(solink)s && %(extract_toc)s > ${lib}.TOC; '
        'else '
          '%(solink)s && %(extract_toc)s > ${lib}.tmp && '
          'if ! cmp -s ${lib}.tmp ${lib}.TOC; then '
            'mv ${lib}.tmp ${lib}.TOC ; '
          'fi; '
        'fi'
        % { 'solink': '$ld -shared $ldflags -o $lib %(suffix)s',
            'extract_toc':
              '{ otool -l $lib | grep LC_ID_DYLIB -A 5; '
              'nm -gP $lib | cut -f1-2 -d\' \' | grep -v U$$; true; }'})

    # TODO(thakis): The solink_module rule is likely wrong. Xcode seems to pass
    # -bundle -single_module here (for osmesa.so).
    master_ninja.rule(
      'solink',
      description='SOLINK $lib, POSTBUILDS',
      restat=True,
      command=(mtime_preserving_solink_base % {
          'suffix': '$in $solibs $libs$postbuilds'}))
    master_ninja.rule(
      'solink_module',
      description='SOLINK(module) $lib, POSTBUILDS',
      restat=True,
      command=(mtime_preserving_solink_base % {
          'suffix': '$in $solibs $libs$postbuilds'}))

    master_ninja.rule(
      'link',
      description='LINK $out, POSTBUILDS',
      command=('$ld $ldflags -o $out '
               '$in $solibs $libs$postbuilds'))
    master_ninja.rule(
      'infoplist',
      description='INFOPLIST $out',
      command=('$cc -E -P -Wno-trigraphs -x c $defines $in -o $out && '
               'plutil -convert xml1 $out $out'))
    master_ninja.rule(
      'mac_tool',
      description='MACTOOL $mactool_cmd $in',
      command='$env ./gyp-mac-tool $mactool_cmd $in $out')
    master_ninja.rule(
      'package_framework',
      description='PACKAGE FRAMEWORK $out, POSTBUILDS',
      command='./gyp-mac-tool package-framework $out $version$postbuilds '
              '&& touch $out')
  if flavor == 'win':
    master_ninja.rule(
      'stamp',
      description='STAMP $out',
      command='%s gyp-win-tool stamp $out' % sys.executable)
    master_ninja.rule(
      'copy',
      description='COPY $in $out',
      command='%s gyp-win-tool recursive-mirror $in $out' % sys.executable)
  else:
    master_ninja.rule(
      'stamp',
      description='STAMP $out',
      command='${postbuilds}touch $out')
    master_ninja.rule(
      'copy',
      description='COPY $in $out',
      command='ln -f $in $out 2>/dev/null || (rm -rf $out && cp -af $in $out)')
  master_ninja.newline()

  all_targets = set()
  for build_file in params['build_files']:
    for target in gyp.common.AllTargets(target_list,
                                        target_dicts,
                                        os.path.normpath(build_file)):
      all_targets.add(target)
  all_outputs = set()

  # target_outputs is a map from qualified target name to a Target object.
  target_outputs = {}
  # target_short_names is a map from target short name to a list of Target
  # objects.
  target_short_names = {}
  for qualified_target in target_list:
    # qualified_target is like: third_party/icu/icu.gyp:icui18n#target
    build_file, name, toolset = \
        gyp.common.ParseQualifiedTarget(qualified_target)

    this_make_global_settings = data[build_file].get('make_global_settings', [])
    assert make_global_settings == this_make_global_settings, (
        "make_global_settings needs to be the same for all targets.")

    spec = target_dicts[qualified_target]
    if flavor == 'mac':
      gyp.xcode_emulation.MergeGlobalXcodeSettingsToSpec(data[build_file], spec)

    build_file = gyp.common.RelativePath(build_file, options.toplevel_dir)

    base_path = os.path.dirname(build_file)
    obj = 'obj'
    if toolset != 'target':
      obj += '.' + toolset
    output_file = os.path.join(obj, base_path, name + '.ninja')

    abs_build_dir = os.path.abspath(toplevel_build)
    writer = NinjaWriter(qualified_target, target_outputs, base_path, build_dir,
                         OpenOutput(os.path.join(toplevel_build, output_file)),
                         flavor, abs_build_dir=abs_build_dir)
    master_ninja.subninja(output_file)

    target = writer.WriteSpec(
        spec, config_name, generator_flags, case_sensitive_filesystem)
    if target:
      if name != target.FinalOutput() and spec['toolset'] == 'target':
        target_short_names.setdefault(name, []).append(target)
      target_outputs[qualified_target] = target
      if qualified_target in all_targets:
        all_outputs.add(target.FinalOutput())

  if target_short_names:
    # Write a short name to build this target.  This benefits both the
    # "build chrome" case as well as the gyp tests, which expect to be
    # able to run actions and build libraries by their short name.
    master_ninja.newline()
    master_ninja.comment('Short names for targets.')
    for short_name in target_short_names:
      master_ninja.build(short_name, 'phony', [x.FinalOutput() for x in
                                               target_short_names[short_name]])

  if all_outputs:
    master_ninja.newline()
    master_ninja.build('all', 'phony', list(all_outputs))
    master_ninja.default(generator_flags.get('default_target', 'all'))


def PerformBuild(data, configurations, params):
  options = params['options']
  for config in configurations:
    builddir = os.path.join(options.toplevel_dir, 'out', config)
    arguments = ['ninja', '-C', builddir]
    print 'Building [%s]: %s' % (config, arguments)
    subprocess.check_call(arguments)


def CallGenerateOutputForConfig(arglist):
  # Ignore the interrupt signal so that the parent process catches it and
  # kills all multiprocessing children.
  signal.signal(signal.SIGINT, signal.SIG_IGN)

  (target_list, target_dicts, data, params, config_name) = arglist
  GenerateOutputForConfig(target_list, target_dicts, data, params, config_name)


def GenerateOutput(target_list, target_dicts, data, params):
  user_config = params.get('generator_flags', {}).get('config', None)
  if user_config:
    GenerateOutputForConfig(target_list, target_dicts, data, params,
                            user_config)
  else:
    config_names = target_dicts[target_list[0]]['configurations'].keys()
    if params['parallel']:
      try:
        pool = multiprocessing.Pool(len(config_names))
        arglists = []
        for config_name in config_names:
          arglists.append(
              (target_list, target_dicts, data, params, config_name))
          pool.map(CallGenerateOutputForConfig, arglists)
      except KeyboardInterrupt, e:
        pool.terminate()
        raise e
    else:
      for config_name in config_names:
        GenerateOutputForConfig(target_list, target_dicts, data, params,
                                config_name)

########NEW FILE########
__FILENAME__ = ninja_test
#!/usr/bin/env python

# Copyright (c) 2012 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" Unit tests for the ninja.py file. """

import gyp.generator.ninja as ninja
import unittest
import StringIO
import sys
import TestCommon


class TestPrefixesAndSuffixes(unittest.TestCase):
  if sys.platform in ('win32', 'cygwin'):
    def test_BinaryNamesWindows(self):
      writer = ninja.NinjaWriter('foo', 'wee', '.', '.', 'ninja.build', 'win')
      spec = { 'target_name': 'wee' }
      self.assertTrue(writer.ComputeOutputFileName(spec, 'executable').
          endswith('.exe'))
      self.assertTrue(writer.ComputeOutputFileName(spec, 'shared_library').
          endswith('.dll'))
      self.assertTrue(writer.ComputeOutputFileName(spec, 'static_library').
          endswith('.lib'))

  if sys.platform == 'linux2':
    def test_BinaryNamesLinux(self):
      writer = ninja.NinjaWriter('foo', 'wee', '.', '.', 'ninja.build', 'linux')
      spec = { 'target_name': 'wee' }
      self.assertTrue('.' not in writer.ComputeOutputFileName(spec,
                                                              'executable'))
      self.assertTrue(writer.ComputeOutputFileName(spec, 'shared_library').
          startswith('lib'))
      self.assertTrue(writer.ComputeOutputFileName(spec, 'static_library').
          startswith('lib'))
      self.assertTrue(writer.ComputeOutputFileName(spec, 'shared_library').
          endswith('.so'))
      self.assertTrue(writer.ComputeOutputFileName(spec, 'static_library').
          endswith('.a'))

if __name__ == '__main__':
  unittest.main()

########NEW FILE########
__FILENAME__ = scons
# Copyright (c) 2012 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import gyp
import gyp.common
import gyp.SCons as SCons
import os.path
import pprint
import re
import subprocess


# TODO:  remove when we delete the last WriteList() call in this module
WriteList = SCons.WriteList


generator_default_variables = {
    'EXECUTABLE_PREFIX': '',
    'EXECUTABLE_SUFFIX': '',
    'STATIC_LIB_PREFIX': '${LIBPREFIX}',
    'SHARED_LIB_PREFIX': '${SHLIBPREFIX}',
    'STATIC_LIB_SUFFIX': '${LIBSUFFIX}',
    'SHARED_LIB_SUFFIX': '${SHLIBSUFFIX}',
    'INTERMEDIATE_DIR': '${INTERMEDIATE_DIR}',
    'SHARED_INTERMEDIATE_DIR': '${SHARED_INTERMEDIATE_DIR}',
    'OS': 'linux',
    'PRODUCT_DIR': '$TOP_BUILDDIR',
    'SHARED_LIB_DIR': '$LIB_DIR',
    'LIB_DIR': '$LIB_DIR',
    'RULE_INPUT_ROOT': '${SOURCE.filebase}',
    'RULE_INPUT_DIRNAME': '${SOURCE.dir}',
    'RULE_INPUT_EXT': '${SOURCE.suffix}',
    'RULE_INPUT_NAME': '${SOURCE.file}',
    'RULE_INPUT_PATH': '${SOURCE.abspath}',
    'CONFIGURATION_NAME': '${CONFIG_NAME}',
}

# Tell GYP how to process the input for us.
generator_handles_variants = True
generator_wants_absolute_build_file_paths = True


def FixPath(path, prefix):
  if not os.path.isabs(path) and not path[0] == '$':
    path = prefix + path
  return path


header = """\
# This file is generated; do not edit.
"""


_alias_template = """
if GetOption('verbose'):
  _action = Action([%(action)s])
else:
  _action = Action([%(action)s], %(message)s)
_outputs = env.Alias(
  ['_%(target_name)s_action'],
  %(inputs)s,
  _action
)
env.AlwaysBuild(_outputs)
"""

_run_as_template = """
if GetOption('verbose'):
  _action = Action([%(action)s])
else:
  _action = Action([%(action)s], %(message)s)
"""

_run_as_template_suffix = """
_run_as_target = env.Alias('run_%(target_name)s', target_files, _action)
env.Requires(_run_as_target, [
    Alias('%(target_name)s'),
])
env.AlwaysBuild(_run_as_target)
"""

_command_template = """
if GetOption('verbose'):
  _action = Action([%(action)s])
else:
  _action = Action([%(action)s], %(message)s)
_outputs = env.Command(
  %(outputs)s,
  %(inputs)s,
  _action
)
"""

# This is copied from the default SCons action, updated to handle symlinks.
_copy_action_template = """
import shutil
import SCons.Action

def _copy_files_or_dirs_or_symlinks(dest, src):
  SCons.Node.FS.invalidate_node_memos(dest)
  if SCons.Util.is_List(src) and os.path.isdir(dest):
    for file in src:
      shutil.copy2(file, dest)
    return 0
  elif os.path.islink(src):
    linkto = os.readlink(src)
    os.symlink(linkto, dest)
    return 0
  elif os.path.isfile(src):
    return shutil.copy2(src, dest)
  else:
    return shutil.copytree(src, dest, 1)

def _copy_files_or_dirs_or_symlinks_str(dest, src):
  return 'Copying %s to %s ...' % (src, dest)

GYPCopy = SCons.Action.ActionFactory(_copy_files_or_dirs_or_symlinks,
                                     _copy_files_or_dirs_or_symlinks_str,
                                     convert=str)
"""

_rule_template = """
%(name)s_additional_inputs = %(inputs)s
%(name)s_outputs = %(outputs)s
def %(name)s_emitter(target, source, env):
  return (%(name)s_outputs, source + %(name)s_additional_inputs)
if GetOption('verbose'):
  %(name)s_action = Action([%(action)s])
else:
  %(name)s_action = Action([%(action)s], %(message)s)
env['BUILDERS']['%(name)s'] = Builder(action=%(name)s_action,
                                      emitter=%(name)s_emitter)

_outputs = []
_processed_input_files = []
for infile in input_files:
  if (type(infile) == type('')
      and not os.path.isabs(infile)
      and not infile[0] == '$'):
    infile = %(src_dir)r + infile
  if str(infile).endswith('.%(extension)s'):
    _generated = env.%(name)s(infile)
    env.Precious(_generated)
    _outputs.append(_generated)
    %(process_outputs_as_sources_line)s
  else:
    _processed_input_files.append(infile)
prerequisites.extend(_outputs)
input_files = _processed_input_files
"""

_spawn_hack = """
import re
import SCons.Platform.posix
needs_shell = re.compile('["\\'><!^&]')
def gyp_spawn(sh, escape, cmd, args, env):
  def strip_scons_quotes(arg):
    if arg[0] == '"' and arg[-1] == '"':
      return arg[1:-1]
    return arg
  stripped_args = [strip_scons_quotes(a) for a in args]
  if needs_shell.search(' '.join(stripped_args)):
    return SCons.Platform.posix.exec_spawnvpe([sh, '-c', ' '.join(args)], env)
  else:
    return SCons.Platform.posix.exec_spawnvpe(stripped_args, env)
"""


def EscapeShellArgument(s):
  """Quotes an argument so that it will be interpreted literally by a POSIX
     shell. Taken from
     http://stackoverflow.com/questions/35817/whats-the-best-way-to-escape-ossystem-calls-in-python
     """
  return "'" + s.replace("'", "'\\''") + "'"


def InvertNaiveSConsQuoting(s):
  """SCons tries to "help" with quoting by naively putting double-quotes around
     command-line arguments containing space or tab, which is broken for all
     but trivial cases, so we undo it. (See quote_spaces() in Subst.py)"""
  if ' ' in s or '\t' in s:
    # Then SCons will put double-quotes around this, so add our own quotes
    # to close its quotes at the beginning and end.
    s = '"' + s + '"'
  return s


def EscapeSConsVariableExpansion(s):
  """SCons has its own variable expansion syntax using $. We must escape it for
    strings to be interpreted literally. For some reason this requires four
    dollar signs, not two, even without the shell involved."""
  return s.replace('$', '$$$$')


def EscapeCppDefine(s):
  """Escapes a CPP define so that it will reach the compiler unaltered."""
  s = EscapeShellArgument(s)
  s = InvertNaiveSConsQuoting(s)
  s = EscapeSConsVariableExpansion(s)
  return s


def GenerateConfig(fp, config, indent='', src_dir=''):
  """
  Generates SCons dictionary items for a gyp configuration.

  This provides the main translation between the (lower-case) gyp settings
  keywords and the (upper-case) SCons construction variables.
  """
  var_mapping = {
      'ASFLAGS' : 'asflags',
      'CCFLAGS' : 'cflags',
      'CFLAGS' : 'cflags_c',
      'CXXFLAGS' : 'cflags_cc',
      'CPPDEFINES' : 'defines',
      'CPPPATH' : 'include_dirs',
      # Add the ldflags value to $LINKFLAGS, but not $SHLINKFLAGS.
      # SCons defines $SHLINKFLAGS to incorporate $LINKFLAGS, so
      # listing both here would case 'ldflags' to get appended to
      # both, and then have it show up twice on the command line.
      'LINKFLAGS' : 'ldflags',
  }
  postamble='\n%s],\n' % indent
  for scons_var in sorted(var_mapping.keys()):
      gyp_var = var_mapping[scons_var]
      value = config.get(gyp_var)
      if value:
        if gyp_var in ('defines',):
          value = [EscapeCppDefine(v) for v in value]
        if gyp_var in ('include_dirs',):
          if src_dir and not src_dir.endswith('/'):
            src_dir += '/'
          result = []
          for v in value:
            v = FixPath(v, src_dir)
            # Force SCons to evaluate the CPPPATH directories at
            # SConscript-read time, so delayed evaluation of $SRC_DIR
            # doesn't point it to the --generator-output= directory.
            result.append('env.Dir(%r)' % v)
          value = result
        else:
          value = map(repr, value)
        WriteList(fp,
                  value,
                  prefix=indent,
                  preamble='%s%s = [\n    ' % (indent, scons_var),
                  postamble=postamble)


def GenerateSConscript(output_filename, spec, build_file, build_file_data):
  """
  Generates a SConscript file for a specific target.

  This generates a SConscript file suitable for building any or all of
  the target's configurations.

  A SConscript file may be called multiple times to generate targets for
  multiple configurations.  Consequently, it needs to be ready to build
  the target for any requested configuration, and therefore contains
  information about the settings for all configurations (generated into
  the SConscript file at gyp configuration time) as well as logic for
  selecting (at SCons build time) the specific configuration being built.

  The general outline of a generated SConscript file is:

    --  Header

    --  Import 'env'.  This contains a $CONFIG_NAME construction
        variable that specifies what configuration to build
        (e.g. Debug, Release).

    --  Configurations.  This is a dictionary with settings for
        the different configurations (Debug, Release) under which this
        target can be built.  The values in the dictionary are themselves
        dictionaries specifying what construction variables should added
        to the local copy of the imported construction environment
        (Append), should be removed (FilterOut), and should outright
        replace the imported values (Replace).

    --  Clone the imported construction environment and update
        with the proper configuration settings.

    --  Initialize the lists of the targets' input files and prerequisites.

    --  Target-specific actions and rules.  These come after the
        input file and prerequisite initializations because the
        outputs of the actions and rules may affect the input file
        list (process_outputs_as_sources) and get added to the list of
        prerequisites (so that they're guaranteed to be executed before
        building the target).

    --  Call the Builder for the target itself.

    --  Arrange for any copies to be made into installation directories.

    --  Set up the {name} Alias (phony Node) for the target as the
        primary handle for building all of the target's pieces.

    --  Use env.Require() to make sure the prerequisites (explicitly
        specified, but also including the actions and rules) are built
        before the target itself.

    --  Return the {name} Alias to the calling SConstruct file
        so it can be added to the list of default targets.
  """
  scons_target = SCons.Target(spec)

  gyp_dir = os.path.dirname(output_filename)
  if not gyp_dir:
      gyp_dir = '.'
  gyp_dir = os.path.abspath(gyp_dir)

  output_dir = os.path.dirname(output_filename)
  src_dir = build_file_data['_DEPTH']
  src_dir_rel = gyp.common.RelativePath(src_dir, output_dir)
  subdir = gyp.common.RelativePath(os.path.dirname(build_file), src_dir)
  src_subdir = '$SRC_DIR/' + subdir
  src_subdir_ = src_subdir + '/'

  component_name = os.path.splitext(os.path.basename(build_file))[0]
  target_name = spec['target_name']

  if not os.path.exists(gyp_dir):
    os.makedirs(gyp_dir)
  fp = open(output_filename, 'w')
  fp.write(header)

  fp.write('\nimport os\n')
  fp.write('\nImport("env")\n')

  #
  fp.write('\n')
  fp.write('env = env.Clone(COMPONENT_NAME=%s,\n' % repr(component_name))
  fp.write('                TARGET_NAME=%s)\n' % repr(target_name))

  #
  for config in spec['configurations'].itervalues():
    if config.get('scons_line_length'):
      fp.write(_spawn_hack)
      break

  #
  indent = ' ' * 12
  fp.write('\n')
  fp.write('configurations = {\n')
  for config_name, config in spec['configurations'].iteritems():
    fp.write('    \'%s\' : {\n' % config_name)

    fp.write('        \'Append\' : dict(\n')
    GenerateConfig(fp, config, indent, src_subdir)
    libraries = spec.get('libraries')
    if libraries:
      WriteList(fp,
                map(repr, libraries),
                prefix=indent,
                preamble='%sLIBS = [\n    ' % indent,
                postamble='\n%s],\n' % indent)
    fp.write('        ),\n')

    fp.write('        \'FilterOut\' : dict(\n' )
    for key, var in config.get('scons_remove', {}).iteritems():
      fp.write('             %s = %s,\n' % (key, repr(var)))
    fp.write('        ),\n')

    fp.write('        \'Replace\' : dict(\n' )
    scons_settings = config.get('scons_variable_settings', {})
    for key in sorted(scons_settings.keys()):
      val = pprint.pformat(scons_settings[key])
      fp.write('             %s = %s,\n' % (key, val))
    if 'c++' in spec.get('link_languages', []):
      fp.write('             %s = %s,\n' % ('LINK', repr('$CXX')))
    if config.get('scons_line_length'):
      fp.write('             SPAWN = gyp_spawn,\n')
    fp.write('        ),\n')

    fp.write('        \'ImportExternal\' : [\n' )
    for var in config.get('scons_import_variables', []):
      fp.write('             %s,\n' % repr(var))
    fp.write('        ],\n')

    fp.write('        \'PropagateExternal\' : [\n' )
    for var in config.get('scons_propagate_variables', []):
      fp.write('             %s,\n' % repr(var))
    fp.write('        ],\n')

    fp.write('    },\n')
  fp.write('}\n')

  fp.write('\n'
           'config = configurations[env[\'CONFIG_NAME\']]\n'
           'env.Append(**config[\'Append\'])\n'
           'env.FilterOut(**config[\'FilterOut\'])\n'
           'env.Replace(**config[\'Replace\'])\n')

  fp.write('\n'
           '# Scons forces -fPIC for SHCCFLAGS on some platforms.\n'
           '# Disable that so we can control it from cflags in gyp.\n'
           '# Note that Scons itself is inconsistent with its -fPIC\n'
           '# setting. SHCCFLAGS forces -fPIC, and SHCFLAGS does not.\n'
           '# This will make SHCCFLAGS consistent with SHCFLAGS.\n'
           'env[\'SHCCFLAGS\'] = [\'$CCFLAGS\']\n')

  fp.write('\n'
           'for _var in config[\'ImportExternal\']:\n'
           '  if _var in ARGUMENTS:\n'
           '    env[_var] = ARGUMENTS[_var]\n'
           '  elif _var in os.environ:\n'
           '    env[_var] = os.environ[_var]\n'
           'for _var in config[\'PropagateExternal\']:\n'
           '  if _var in ARGUMENTS:\n'
           '    env[_var] = ARGUMENTS[_var]\n'
           '  elif _var in os.environ:\n'
           '    env[\'ENV\'][_var] = os.environ[_var]\n')

  fp.write('\n'
           "env['ENV']['LD_LIBRARY_PATH'] = env.subst('$LIB_DIR')\n")

  #
  #fp.write("\nif env.has_key('CPPPATH'):\n")
  #fp.write("  env['CPPPATH'] = map(env.Dir, env['CPPPATH'])\n")

  variants = spec.get('variants', {})
  for setting in sorted(variants.keys()):
    if_fmt = 'if ARGUMENTS.get(%s) not in (None, \'0\'):\n'
    fp.write('\n')
    fp.write(if_fmt % repr(setting.upper()))
    fp.write('  env.AppendUnique(\n')
    GenerateConfig(fp, variants[setting], indent, src_subdir)
    fp.write('  )\n')

  #
  scons_target.write_input_files(fp)

  fp.write('\n')
  fp.write('target_files = []\n')
  prerequisites = spec.get('scons_prerequisites', [])
  fp.write('prerequisites = %s\n' % pprint.pformat(prerequisites))

  actions = spec.get('actions', [])
  for action in actions:
    a = ['cd', src_subdir, '&&'] + action['action']
    message = action.get('message')
    if message:
      message = repr(message)
    inputs = [FixPath(f, src_subdir_) for f in action.get('inputs', [])]
    outputs = [FixPath(f, src_subdir_) for f in action.get('outputs', [])]
    if outputs:
      template = _command_template
    else:
      template = _alias_template
    fp.write(template % {
                 'inputs' : pprint.pformat(inputs),
                 'outputs' : pprint.pformat(outputs),
                 'action' : pprint.pformat(a),
                 'message' : message,
                 'target_name': target_name,
             })
    if int(action.get('process_outputs_as_sources', 0)):
      fp.write('input_files.extend(_outputs)\n')
    fp.write('prerequisites.extend(_outputs)\n')
    fp.write('target_files.extend(_outputs)\n')

  rules = spec.get('rules', [])
  for rule in rules:
    name = re.sub('[^a-zA-Z0-9_]', '_', rule['rule_name'])
    message = rule.get('message')
    if message:
        message = repr(message)
    if int(rule.get('process_outputs_as_sources', 0)):
      poas_line = '_processed_input_files.extend(_generated)'
    else:
      poas_line = '_processed_input_files.append(infile)'
    inputs = [FixPath(f, src_subdir_) for f in rule.get('inputs', [])]
    outputs = [FixPath(f, src_subdir_) for f in rule.get('outputs', [])]
    # Skip a rule with no action and no inputs.
    if 'action' not in rule and not rule.get('rule_sources', []):
      continue
    a = ['cd', src_subdir, '&&'] + rule['action']
    fp.write(_rule_template % {
                 'inputs' : pprint.pformat(inputs),
                 'outputs' : pprint.pformat(outputs),
                 'action' : pprint.pformat(a),
                 'extension' : rule['extension'],
                 'name' : name,
                 'message' : message,
                 'process_outputs_as_sources_line' : poas_line,
                 'src_dir' : src_subdir_,
             })

  scons_target.write_target(fp, src_subdir)

  copies = spec.get('copies', [])
  if copies:
    fp.write(_copy_action_template)
  for copy in copies:
    destdir = None
    files = None
    try:
      destdir = copy['destination']
    except KeyError, e:
      gyp.common.ExceptionAppend(
        e,
        "Required 'destination' key missing for 'copies' in %s." % build_file)
      raise
    try:
      files = copy['files']
    except KeyError, e:
      gyp.common.ExceptionAppend(
        e, "Required 'files' key missing for 'copies' in %s." % build_file)
      raise
    if not files:
      # TODO:  should probably add a (suppressible) warning;
      # a null file list may be unintentional.
      continue
    if not destdir:
      raise Exception(
        "Required 'destination' key is empty for 'copies' in %s." % build_file)

    fmt = ('\n'
           '_outputs = env.Command(%s,\n'
           '    %s,\n'
           '    GYPCopy(\'$TARGET\', \'$SOURCE\'))\n')
    for f in copy['files']:
      # Remove trailing separators so basename() acts like Unix basename and
      # always returns the last element, whether a file or dir. Without this,
      # only the contents, not the directory itself, are copied (and nothing
      # might be copied if dest already exists, since scons thinks nothing needs
      # to be done).
      dest = os.path.join(destdir, os.path.basename(f.rstrip(os.sep)))
      f = FixPath(f, src_subdir_)
      dest = FixPath(dest, src_subdir_)
      fp.write(fmt % (repr(dest), repr(f)))
      fp.write('target_files.extend(_outputs)\n')

  run_as = spec.get('run_as')
  if run_as:
    action = run_as.get('action', [])
    working_directory = run_as.get('working_directory')
    if not working_directory:
      working_directory = gyp_dir
    else:
      if not os.path.isabs(working_directory):
        working_directory = os.path.normpath(os.path.join(gyp_dir,
                                                          working_directory))
    if run_as.get('environment'):
      for (key, val) in run_as.get('environment').iteritems():
        action = ['%s="%s"' % (key, val)] + action
    action = ['cd', '"%s"' % working_directory, '&&'] + action
    fp.write(_run_as_template % {
      'action' : pprint.pformat(action),
      'message' : run_as.get('message', ''),
    })

  fmt = "\ngyp_target = env.Alias('%s', target_files)\n"
  fp.write(fmt % target_name)

  dependencies = spec.get('scons_dependencies', [])
  if dependencies:
    WriteList(fp, dependencies, preamble='dependencies = [\n    ',
                                postamble='\n]\n')
    fp.write('env.Requires(target_files, dependencies)\n')
    fp.write('env.Requires(gyp_target, dependencies)\n')
    fp.write('for prerequisite in prerequisites:\n')
    fp.write('  env.Requires(prerequisite, dependencies)\n')
  fp.write('env.Requires(gyp_target, prerequisites)\n')

  if run_as:
    fp.write(_run_as_template_suffix % {
      'target_name': target_name,
    })

  fp.write('Return("gyp_target")\n')

  fp.close()


#############################################################################
# TEMPLATE BEGIN

_wrapper_template = """\

__doc__ = '''
Wrapper configuration for building this entire "solution,"
including all the specific targets in various *.scons files.
'''

import os
import sys

import SCons.Environment
import SCons.Util

def GetProcessorCount():
  '''
  Detects the number of CPUs on the system. Adapted form:
  http://codeliberates.blogspot.com/2008/05/detecting-cpuscores-in-python.html
  '''
  # Linux, Unix and Mac OS X:
  if hasattr(os, 'sysconf'):
    if os.sysconf_names.has_key('SC_NPROCESSORS_ONLN'):
      # Linux and Unix or Mac OS X with python >= 2.5:
      return os.sysconf('SC_NPROCESSORS_ONLN')
    else:  # Mac OS X with Python < 2.5:
      return int(os.popen2("sysctl -n hw.ncpu")[1].read())
  # Windows:
  if os.environ.has_key('NUMBER_OF_PROCESSORS'):
    return max(int(os.environ.get('NUMBER_OF_PROCESSORS', '1')), 1)
  return 1  # Default

# Support PROGRESS= to show progress in different ways.
p = ARGUMENTS.get('PROGRESS')
if p == 'spinner':
  Progress(['/\\r', '|\\r', '\\\\\\r', '-\\r'],
           interval=5,
           file=open('/dev/tty', 'w'))
elif p == 'name':
  Progress('$TARGET\\r', overwrite=True, file=open('/dev/tty', 'w'))

# Set the default -j value based on the number of processors.
SetOption('num_jobs', GetProcessorCount() + 1)

# Have SCons use its cached dependency information.
SetOption('implicit_cache', 1)

# Only re-calculate MD5 checksums if a timestamp has changed.
Decider('MD5-timestamp')

# Since we set the -j value by default, suppress SCons warnings about being
# unable to support parallel build on versions of Python with no threading.
default_warnings = ['no-no-parallel-support']
SetOption('warn', default_warnings + GetOption('warn'))

AddOption('--mode', nargs=1, dest='conf_list', default=[],
          action='append', help='Configuration to build.')

AddOption('--verbose', dest='verbose', default=False,
          action='store_true', help='Verbose command-line output.')


#
sconscript_file_map = %(sconscript_files)s

class LoadTarget:
  '''
  Class for deciding if a given target sconscript is to be included
  based on a list of included target names, optionally prefixed with '-'
  to exclude a target name.
  '''
  def __init__(self, load):
    '''
    Initialize a class with a list of names for possible loading.

    Arguments:
      load:  list of elements in the LOAD= specification
    '''
    self.included = set([c for c in load if not c.startswith('-')])
    self.excluded = set([c[1:] for c in load if c.startswith('-')])

    if not self.included:
      self.included = set(['all'])

  def __call__(self, target):
    '''
    Returns True if the specified target's sconscript file should be
    loaded, based on the initialized included and excluded lists.
    '''
    return (target in self.included or
            ('all' in self.included and not target in self.excluded))

if 'LOAD' in ARGUMENTS:
  load = ARGUMENTS['LOAD'].split(',')
else:
  load = []
load_target = LoadTarget(load)

sconscript_files = []
for target, sconscript in sconscript_file_map.iteritems():
  if load_target(target):
    sconscript_files.append(sconscript)


target_alias_list= []

conf_list = GetOption('conf_list')
if conf_list:
    # In case the same --mode= value was specified multiple times.
    conf_list = list(set(conf_list))
else:
    conf_list = [%(default_configuration)r]

sconsbuild_dir = Dir(%(sconsbuild_dir)s)


def FilterOut(self, **kw):
  kw = SCons.Environment.copy_non_reserved_keywords(kw)
  for key, val in kw.items():
    envval = self.get(key, None)
    if envval is None:
      # No existing variable in the environment, so nothing to delete.
      continue

    for vremove in val:
      # Use while not if, so we can handle duplicates.
      while vremove in envval:
        envval.remove(vremove)

    self[key] = envval

    # TODO(sgk): SCons.Environment.Append() has much more logic to deal
    # with various types of values.  We should handle all those cases in here
    # too.  (If variable is a dict, etc.)


non_compilable_suffixes = {
    'LINUX' : set([
        '.bdic',
        '.css',
        '.dat',
        '.fragment',
        '.gperf',
        '.h',
        '.hh',
        '.hpp',
        '.html',
        '.hxx',
        '.idl',
        '.in',
        '.in0',
        '.in1',
        '.js',
        '.mk',
        '.rc',
        '.sigs',
        '',
    ]),
    'WINDOWS' : set([
        '.h',
        '.hh',
        '.hpp',
        '.dat',
        '.idl',
        '.in',
        '.in0',
        '.in1',
    ]),
}

def compilable(env, file):
  base, ext = os.path.splitext(str(file))
  if ext in non_compilable_suffixes[env['TARGET_PLATFORM']]:
    return False
  return True

def compilable_files(env, sources):
  return [x for x in sources if compilable(env, x)]

def GypProgram(env, target, source, *args, **kw):
  source = compilable_files(env, source)
  result = env.Program(target, source, *args, **kw)
  if env.get('INCREMENTAL'):
    env.Precious(result)
  return result

def GypTestProgram(env, target, source, *args, **kw):
  source = compilable_files(env, source)
  result = env.Program(target, source, *args, **kw)
  if env.get('INCREMENTAL'):
    env.Precious(*result)
  return result

def GypLibrary(env, target, source, *args, **kw):
  source = compilable_files(env, source)
  result = env.Library(target, source, *args, **kw)
  return result

def GypLoadableModule(env, target, source, *args, **kw):
  source = compilable_files(env, source)
  result = env.LoadableModule(target, source, *args, **kw)
  return result

def GypStaticLibrary(env, target, source, *args, **kw):
  source = compilable_files(env, source)
  result = env.StaticLibrary(target, source, *args, **kw)
  return result

def GypSharedLibrary(env, target, source, *args, **kw):
  source = compilable_files(env, source)
  result = env.SharedLibrary(target, source, *args, **kw)
  if env.get('INCREMENTAL'):
    env.Precious(result)
  return result

def add_gyp_methods(env):
  env.AddMethod(GypProgram)
  env.AddMethod(GypTestProgram)
  env.AddMethod(GypLibrary)
  env.AddMethod(GypLoadableModule)
  env.AddMethod(GypStaticLibrary)
  env.AddMethod(GypSharedLibrary)

  env.AddMethod(FilterOut)

  env.AddMethod(compilable)


base_env = Environment(
    tools = %(scons_tools)s,
    INTERMEDIATE_DIR='$OBJ_DIR/${COMPONENT_NAME}/_${TARGET_NAME}_intermediate',
    LIB_DIR='$TOP_BUILDDIR/lib',
    OBJ_DIR='$TOP_BUILDDIR/obj',
    SCONSBUILD_DIR=sconsbuild_dir.abspath,
    SHARED_INTERMEDIATE_DIR='$OBJ_DIR/_global_intermediate',
    SRC_DIR=Dir(%(src_dir)r),
    TARGET_PLATFORM='LINUX',
    TOP_BUILDDIR='$SCONSBUILD_DIR/$CONFIG_NAME',
    LIBPATH=['$LIB_DIR'],
)

if not GetOption('verbose'):
  base_env.SetDefault(
      ARCOMSTR='Creating library $TARGET',
      ASCOMSTR='Assembling $TARGET',
      CCCOMSTR='Compiling $TARGET',
      CONCATSOURCECOMSTR='ConcatSource $TARGET',
      CXXCOMSTR='Compiling $TARGET',
      LDMODULECOMSTR='Building loadable module $TARGET',
      LINKCOMSTR='Linking $TARGET',
      MANIFESTCOMSTR='Updating manifest for $TARGET',
      MIDLCOMSTR='Compiling IDL $TARGET',
      PCHCOMSTR='Precompiling $TARGET',
      RANLIBCOMSTR='Indexing $TARGET',
      RCCOMSTR='Compiling resource $TARGET',
      SHCCCOMSTR='Compiling $TARGET',
      SHCXXCOMSTR='Compiling $TARGET',
      SHLINKCOMSTR='Linking $TARGET',
      SHMANIFESTCOMSTR='Updating manifest for $TARGET',
  )

add_gyp_methods(base_env)

for conf in conf_list:
  env = base_env.Clone(CONFIG_NAME=conf)
  SConsignFile(env.File('$TOP_BUILDDIR/.sconsign').abspath)
  for sconscript in sconscript_files:
    target_alias = env.SConscript(sconscript, exports=['env'])
    if target_alias:
      target_alias_list.extend(target_alias)

Default(Alias('all', target_alias_list))

help_fmt = '''
Usage: hammer [SCONS_OPTIONS] [VARIABLES] [TARGET] ...

Local command-line build options:
  --mode=CONFIG             Configuration to build:
                              --mode=Debug [default]
                              --mode=Release
  --verbose                 Print actual executed command lines.

Supported command-line build variables:
  LOAD=[module,...]         Comma-separated list of components to load in the
                              dependency graph ('-' prefix excludes)
  PROGRESS=type             Display a progress indicator:
                              name:  print each evaluated target name
                              spinner:  print a spinner every 5 targets

The following TARGET names can also be used as LOAD= module names:

%%s
'''

if GetOption('help'):
  def columnar_text(items, width=78, indent=2, sep=2):
    result = []
    colwidth = max(map(len, items)) + sep
    cols = (width - indent) / colwidth
    if cols < 1:
      cols = 1
    rows = (len(items) + cols - 1) / cols
    indent = '%%*s' %% (indent, '')
    sep = indent
    for row in xrange(0, rows):
      result.append(sep)
      for i in xrange(row, len(items), rows):
        result.append('%%-*s' %% (colwidth, items[i]))
      sep = '\\n' + indent
    result.append('\\n')
    return ''.join(result)

  load_list = set(sconscript_file_map.keys())
  target_aliases = set(map(str, target_alias_list))

  common = load_list and target_aliases
  load_only = load_list - common
  target_only = target_aliases - common
  help_text = [help_fmt %% columnar_text(sorted(list(common)))]
  if target_only:
    fmt = "The following are additional TARGET names:\\n\\n%%s\\n"
    help_text.append(fmt %% columnar_text(sorted(list(target_only))))
  if load_only:
    fmt = "The following are additional LOAD= module names:\\n\\n%%s\\n"
    help_text.append(fmt %% columnar_text(sorted(list(load_only))))
  Help(''.join(help_text))
"""

# TEMPLATE END
#############################################################################


def GenerateSConscriptWrapper(build_file, build_file_data, name,
                              output_filename, sconscript_files,
                              default_configuration):
  """
  Generates the "wrapper" SConscript file (analogous to the Visual Studio
  solution) that calls all the individual target SConscript files.
  """
  output_dir = os.path.dirname(output_filename)
  src_dir = build_file_data['_DEPTH']
  src_dir_rel = gyp.common.RelativePath(src_dir, output_dir)
  if not src_dir_rel:
    src_dir_rel = '.'
  scons_settings = build_file_data.get('scons_settings', {})
  sconsbuild_dir = scons_settings.get('sconsbuild_dir', '#')
  scons_tools = scons_settings.get('tools', ['default'])

  sconscript_file_lines = ['dict(']
  for target in sorted(sconscript_files.keys()):
    sconscript = sconscript_files[target]
    sconscript_file_lines.append('    %s = %r,' % (target, sconscript))
  sconscript_file_lines.append(')')

  fp = open(output_filename, 'w')
  fp.write(header)
  fp.write(_wrapper_template % {
               'default_configuration' : default_configuration,
               'name' : name,
               'scons_tools' : repr(scons_tools),
               'sconsbuild_dir' : repr(sconsbuild_dir),
               'sconscript_files' : '\n'.join(sconscript_file_lines),
               'src_dir' : src_dir_rel,
           })
  fp.close()

  # Generate the SConstruct file that invokes the wrapper SConscript.
  dir, fname = os.path.split(output_filename)
  SConstruct = os.path.join(dir, 'SConstruct')
  fp = open(SConstruct, 'w')
  fp.write(header)
  fp.write('SConscript(%s)\n' % repr(fname))
  fp.close()


def TargetFilename(target, build_file=None, output_suffix=''):
  """Returns the .scons file name for the specified target.
  """
  if build_file is None:
    build_file, target = gyp.common.ParseQualifiedTarget(target)[:2]
  output_file = os.path.join(os.path.dirname(build_file),
                             target + output_suffix + '.scons')
  return output_file


def PerformBuild(data, configurations, params):
  options = params['options']

  # Due to the way we test gyp on the chromium typbots
  # we need to look for 'scons.py' as well as the more common 'scons'
  # TODO(sbc): update the trybots to have a more normal install
  # of scons.
  scons = 'scons'
  paths = os.environ['PATH'].split(os.pathsep)
  for scons_name in ['scons', 'scons.py']:
    for path in paths:
      test_scons = os.path.join(path, scons_name)
      print 'looking for: %s' % test_scons
      if os.path.exists(test_scons):
        print "found scons: %s" % scons
        scons = test_scons
        break

  for config in configurations:
    arguments = [scons, '-C', options.toplevel_dir, '--mode=%s' % config]
    print "Building [%s]: %s" % (config, arguments)
    subprocess.check_call(arguments)


def GenerateOutput(target_list, target_dicts, data, params):
  """
  Generates all the output files for the specified targets.
  """
  options = params['options']

  if options.generator_output:
    def output_path(filename):
      return filename.replace(params['cwd'], options.generator_output)
  else:
    def output_path(filename):
      return filename

  default_configuration = None

  for qualified_target in target_list:
    spec = target_dicts[qualified_target]
    if spec['toolset'] != 'target':
      raise Exception(
          'Multiple toolsets not supported in scons build (target %s)' %
          qualified_target)
    scons_target = SCons.Target(spec)
    if scons_target.is_ignored:
      continue

    # TODO:  assumes the default_configuration of the first target
    # non-Default target is the correct default for all targets.
    # Need a better model for handle variation between targets.
    if (not default_configuration and
        spec['default_configuration'] != 'Default'):
      default_configuration = spec['default_configuration']

    build_file, target = gyp.common.ParseQualifiedTarget(qualified_target)[:2]
    output_file = TargetFilename(target, build_file, options.suffix)
    if options.generator_output:
      output_file = output_path(output_file)

    if not spec.has_key('libraries'):
      spec['libraries'] = []

    # Add dependent static library targets to the 'libraries' value.
    deps = spec.get('dependencies', [])
    spec['scons_dependencies'] = []
    for d in deps:
      td = target_dicts[d]
      target_name = td['target_name']
      spec['scons_dependencies'].append("Alias('%s')" % target_name)
      if td['type'] in ('static_library', 'shared_library'):
        libname = td.get('product_name', target_name)
        spec['libraries'].append('lib' + libname)
      if td['type'] == 'loadable_module':
        prereqs = spec.get('scons_prerequisites', [])
        # TODO:  parameterize with <(SHARED_LIBRARY_*) variables?
        td_target = SCons.Target(td)
        td_target.target_prefix = '${SHLIBPREFIX}'
        td_target.target_suffix = '${SHLIBSUFFIX}'

    GenerateSConscript(output_file, spec, build_file, data[build_file])

  if not default_configuration:
    default_configuration = 'Default'

  for build_file in sorted(data.keys()):
    path, ext = os.path.splitext(build_file)
    if ext != '.gyp':
      continue
    output_dir, basename = os.path.split(path)
    output_filename  = path + '_main' + options.suffix + '.scons'

    all_targets = gyp.common.AllTargets(target_list, target_dicts, build_file)
    sconscript_files = {}
    for t in all_targets:
      scons_target = SCons.Target(target_dicts[t])
      if scons_target.is_ignored:
        continue
      bf, target = gyp.common.ParseQualifiedTarget(t)[:2]
      target_filename = TargetFilename(target, bf, options.suffix)
      tpath = gyp.common.RelativePath(target_filename, output_dir)
      sconscript_files[target] = tpath

    output_filename = output_path(output_filename)
    if sconscript_files:
      GenerateSConscriptWrapper(build_file, data[build_file], basename,
                                output_filename, sconscript_files,
                                default_configuration)

########NEW FILE########
__FILENAME__ = xcode
# Copyright (c) 2012 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import filecmp
import gyp.common
import gyp.xcodeproj_file
import errno
import os
import sys
import posixpath
import re
import shutil
import subprocess
import tempfile


# Project files generated by this module will use _intermediate_var as a
# custom Xcode setting whose value is a DerivedSources-like directory that's
# project-specific and configuration-specific.  The normal choice,
# DERIVED_FILE_DIR, is target-specific, which is thought to be too restrictive
# as it is likely that multiple targets within a single project file will want
# to access the same set of generated files.  The other option,
# PROJECT_DERIVED_FILE_DIR, is unsuitable because while it is project-specific,
# it is not configuration-specific.  INTERMEDIATE_DIR is defined as
# $(PROJECT_DERIVED_FILE_DIR)/$(CONFIGURATION).
_intermediate_var = 'INTERMEDIATE_DIR'

# SHARED_INTERMEDIATE_DIR is the same, except that it is shared among all
# targets that share the same BUILT_PRODUCTS_DIR.
_shared_intermediate_var = 'SHARED_INTERMEDIATE_DIR'

_library_search_paths_var = 'LIBRARY_SEARCH_PATHS'

generator_default_variables = {
  'EXECUTABLE_PREFIX': '',
  'EXECUTABLE_SUFFIX': '',
  'STATIC_LIB_PREFIX': 'lib',
  'SHARED_LIB_PREFIX': 'lib',
  'STATIC_LIB_SUFFIX': '.a',
  'SHARED_LIB_SUFFIX': '.dylib',
  # INTERMEDIATE_DIR is a place for targets to build up intermediate products.
  # It is specific to each build environment.  It is only guaranteed to exist
  # and be constant within the context of a project, corresponding to a single
  # input file.  Some build environments may allow their intermediate directory
  # to be shared on a wider scale, but this is not guaranteed.
  'INTERMEDIATE_DIR': '$(%s)' % _intermediate_var,
  'OS': 'mac',
  'PRODUCT_DIR': '$(BUILT_PRODUCTS_DIR)',
  'LIB_DIR': '$(BUILT_PRODUCTS_DIR)',
  'RULE_INPUT_ROOT': '$(INPUT_FILE_BASE)',
  'RULE_INPUT_EXT': '$(INPUT_FILE_SUFFIX)',
  'RULE_INPUT_NAME': '$(INPUT_FILE_NAME)',
  'RULE_INPUT_PATH': '$(INPUT_FILE_PATH)',
  'RULE_INPUT_DIRNAME': '$(INPUT_FILE_DIRNAME)',
  'SHARED_INTERMEDIATE_DIR': '$(%s)' % _shared_intermediate_var,
  'CONFIGURATION_NAME': '$(CONFIGURATION)',
}

# The Xcode-specific sections that hold paths.
generator_additional_path_sections = [
  'mac_bundle_resources',
  'mac_framework_headers',
  'mac_framework_private_headers',
  # 'mac_framework_dirs', input already handles _dirs endings.
]

# The Xcode-specific keys that exist on targets and aren't moved down to
# configurations.
generator_additional_non_configuration_keys = [
  'mac_bundle',
  'mac_bundle_resources',
  'mac_framework_headers',
  'mac_framework_private_headers',
  'xcode_create_dependents_test_runner',
]

# We want to let any rules apply to files that are resources also.
generator_extra_sources_for_rules = [
  'mac_bundle_resources',
  'mac_framework_headers',
  'mac_framework_private_headers',
]

# Xcode's standard set of library directories, which don't need to be duplicated
# in LIBRARY_SEARCH_PATHS. This list is not exhaustive, but that's okay.
xcode_standard_library_dirs = frozenset([
  '$(SDKROOT)/usr/lib',
  '$(SDKROOT)/usr/local/lib',
])

def CreateXCConfigurationList(configuration_names):
  xccl = gyp.xcodeproj_file.XCConfigurationList({'buildConfigurations': []})
  if len(configuration_names) == 0:
    configuration_names = ['Default']
  for configuration_name in configuration_names:
    xcbc = gyp.xcodeproj_file.XCBuildConfiguration({
        'name': configuration_name})
    xccl.AppendProperty('buildConfigurations', xcbc)
  xccl.SetProperty('defaultConfigurationName', configuration_names[0])
  return xccl


class XcodeProject(object):
  def __init__(self, gyp_path, path, build_file_dict):
    self.gyp_path = gyp_path
    self.path = path
    self.project = gyp.xcodeproj_file.PBXProject(path=path)
    projectDirPath = gyp.common.RelativePath(
                         os.path.dirname(os.path.abspath(self.gyp_path)),
                         os.path.dirname(path) or '.')
    self.project.SetProperty('projectDirPath', projectDirPath)
    self.project_file = \
        gyp.xcodeproj_file.XCProjectFile({'rootObject': self.project})
    self.build_file_dict = build_file_dict

    # TODO(mark): add destructor that cleans up self.path if created_dir is
    # True and things didn't complete successfully.  Or do something even
    # better with "try"?
    self.created_dir = False
    try:
      os.makedirs(self.path)
      self.created_dir = True
    except OSError, e:
      if e.errno != errno.EEXIST:
        raise

  def Finalize1(self, xcode_targets, serialize_all_tests):
    # Collect a list of all of the build configuration names used by the
    # various targets in the file.  It is very heavily advised to keep each
    # target in an entire project (even across multiple project files) using
    # the same set of configuration names.
    configurations = []
    for xct in self.project.GetProperty('targets'):
      xccl = xct.GetProperty('buildConfigurationList')
      xcbcs = xccl.GetProperty('buildConfigurations')
      for xcbc in xcbcs:
        name = xcbc.GetProperty('name')
        if name not in configurations:
          configurations.append(name)

    # Replace the XCConfigurationList attached to the PBXProject object with
    # a new one specifying all of the configuration names used by the various
    # targets.
    try:
      xccl = CreateXCConfigurationList(configurations)
      self.project.SetProperty('buildConfigurationList', xccl)
    except:
      sys.stderr.write("Problem with gyp file %s\n" % self.gyp_path)
      raise

    # The need for this setting is explained above where _intermediate_var is
    # defined.  The comments below about wanting to avoid project-wide build
    # settings apply here too, but this needs to be set on a project-wide basis
    # so that files relative to the _intermediate_var setting can be displayed
    # properly in the Xcode UI.
    #
    # Note that for configuration-relative files such as anything relative to
    # _intermediate_var, for the purposes of UI tree view display, Xcode will
    # only resolve the configuration name once, when the project file is
    # opened.  If the active build configuration is changed, the project file
    # must be closed and reopened if it is desired for the tree view to update.
    # This is filed as Apple radar 6588391.
    xccl.SetBuildSetting(_intermediate_var,
                         '$(PROJECT_DERIVED_FILE_DIR)/$(CONFIGURATION)')
    xccl.SetBuildSetting(_shared_intermediate_var,
                         '$(SYMROOT)/DerivedSources/$(CONFIGURATION)')

    # Set user-specified project-wide build settings and config files.  This
    # is intended to be used very sparingly.  Really, almost everything should
    # go into target-specific build settings sections.  The project-wide
    # settings are only intended to be used in cases where Xcode attempts to
    # resolve variable references in a project context as opposed to a target
    # context, such as when resolving sourceTree references while building up
    # the tree tree view for UI display.
    # Any values set globally are applied to all configurations, then any
    # per-configuration values are applied.
    for xck, xcv in self.build_file_dict.get('xcode_settings', {}).iteritems():
      xccl.SetBuildSetting(xck, xcv)
    if 'xcode_config_file' in self.build_file_dict:
      config_ref = self.project.AddOrGetFileInRootGroup(
          self.build_file_dict['xcode_config_file'])
      xccl.SetBaseConfiguration(config_ref)
    build_file_configurations = self.build_file_dict.get('configurations', {})
    if build_file_configurations:
      for config_name in configurations:
        build_file_configuration_named = \
            build_file_configurations.get(config_name, {})
        if build_file_configuration_named:
          xcc = xccl.ConfigurationNamed(config_name)
          for xck, xcv in build_file_configuration_named.get('xcode_settings',
                                                             {}).iteritems():
            xcc.SetBuildSetting(xck, xcv)
          if 'xcode_config_file' in build_file_configuration_named:
            config_ref = self.project.AddOrGetFileInRootGroup(
                build_file_configurations[config_name]['xcode_config_file'])
            xcc.SetBaseConfiguration(config_ref)

    # Sort the targets based on how they appeared in the input.
    # TODO(mark): Like a lot of other things here, this assumes internal
    # knowledge of PBXProject - in this case, of its "targets" property.

    # ordinary_targets are ordinary targets that are already in the project
    # file. run_test_targets are the targets that run unittests and should be
    # used for the Run All Tests target.  support_targets are the action/rule
    # targets used by GYP file targets, just kept for the assert check.
    ordinary_targets = []
    run_test_targets = []
    support_targets = []

    # targets is full list of targets in the project.
    targets = []

    # does the it define it's own "all"?
    has_custom_all = False

    # targets_for_all is the list of ordinary_targets that should be listed
    # in this project's "All" target.  It includes each non_runtest_target
    # that does not have suppress_wildcard set.
    targets_for_all = []

    for target in self.build_file_dict['targets']:
      target_name = target['target_name']
      toolset = target['toolset']
      qualified_target = gyp.common.QualifiedTarget(self.gyp_path, target_name,
                                                    toolset)
      xcode_target = xcode_targets[qualified_target]
      # Make sure that the target being added to the sorted list is already in
      # the unsorted list.
      assert xcode_target in self.project._properties['targets']
      targets.append(xcode_target)
      ordinary_targets.append(xcode_target)
      if xcode_target.support_target:
        support_targets.append(xcode_target.support_target)
        targets.append(xcode_target.support_target)

      if not int(target.get('suppress_wildcard', False)):
        targets_for_all.append(xcode_target)

      if target_name.lower() == 'all':
        has_custom_all = True;

      # If this target has a 'run_as' attribute, add its target to the
      # targets, and add it to the test targets.
      if target.get('run_as'):
        # Make a target to run something.  It should have one
        # dependency, the parent xcode target.
        xccl = CreateXCConfigurationList(configurations)
        run_target = gyp.xcodeproj_file.PBXAggregateTarget({
              'name':                   'Run ' + target_name,
              'productName':            xcode_target.GetProperty('productName'),
              'buildConfigurationList': xccl,
            },
            parent=self.project)
        run_target.AddDependency(xcode_target)

        command = target['run_as']
        script = ''
        if command.get('working_directory'):
          script = script + 'cd "%s"\n' % \
                   gyp.xcodeproj_file.ConvertVariablesToShellSyntax(
                       command.get('working_directory'))

        if command.get('environment'):
          script = script + "\n".join(
            ['export %s="%s"' %
             (key, gyp.xcodeproj_file.ConvertVariablesToShellSyntax(val))
             for (key, val) in command.get('environment').iteritems()]) + "\n"

        # Some test end up using sockets, files on disk, etc. and can get
        # confused if more then one test runs at a time.  The generator
        # flag 'xcode_serialize_all_test_runs' controls the forcing of all
        # tests serially.  It defaults to True.  To get serial runs this
        # little bit of python does the same as the linux flock utility to
        # make sure only one runs at a time.
        command_prefix = ''
        if serialize_all_tests:
          command_prefix = \
"""python -c "import fcntl, subprocess, sys
file = open('$TMPDIR/GYP_serialize_test_runs', 'a')
fcntl.flock(file.fileno(), fcntl.LOCK_EX)
sys.exit(subprocess.call(sys.argv[1:]))" """

        # If we were unable to exec for some reason, we want to exit
        # with an error, and fixup variable references to be shell
        # syntax instead of xcode syntax.
        script = script + 'exec ' + command_prefix + '%s\nexit 1\n' % \
                 gyp.xcodeproj_file.ConvertVariablesToShellSyntax(
                     gyp.common.EncodePOSIXShellList(command.get('action')))

        ssbp = gyp.xcodeproj_file.PBXShellScriptBuildPhase({
              'shellScript':      script,
              'showEnvVarsInLog': 0,
            })
        run_target.AppendProperty('buildPhases', ssbp)

        # Add the run target to the project file.
        targets.append(run_target)
        run_test_targets.append(run_target)
        xcode_target.test_runner = run_target


    # Make sure that the list of targets being replaced is the same length as
    # the one replacing it, but allow for the added test runner targets.
    assert len(self.project._properties['targets']) == \
      len(ordinary_targets) + len(support_targets)

    self.project._properties['targets'] = targets

    # Get rid of unnecessary levels of depth in groups like the Source group.
    self.project.RootGroupsTakeOverOnlyChildren(True)

    # Sort the groups nicely.  Do this after sorting the targets, because the
    # Products group is sorted based on the order of the targets.
    self.project.SortGroups()

    # Create an "All" target if there's more than one target in this project
    # file and the project didn't define its own "All" target.  Put a generated
    # "All" target first so that people opening up the project for the first
    # time will build everything by default.
    if len(targets_for_all) > 1 and not has_custom_all:
      xccl = CreateXCConfigurationList(configurations)
      all_target = gyp.xcodeproj_file.PBXAggregateTarget(
          {
            'buildConfigurationList': xccl,
            'name':                   'All',
          },
          parent=self.project)

      for target in targets_for_all:
        all_target.AddDependency(target)

      # TODO(mark): This is evil because it relies on internal knowledge of
      # PBXProject._properties.  It's important to get the "All" target first,
      # though.
      self.project._properties['targets'].insert(0, all_target)

    # The same, but for run_test_targets.
    if len(run_test_targets) > 1:
      xccl = CreateXCConfigurationList(configurations)
      run_all_tests_target = gyp.xcodeproj_file.PBXAggregateTarget(
          {
            'buildConfigurationList': xccl,
            'name':                   'Run All Tests',
          },
          parent=self.project)
      for run_test_target in run_test_targets:
        run_all_tests_target.AddDependency(run_test_target)

      # Insert after the "All" target, which must exist if there is more than
      # one run_test_target.
      self.project._properties['targets'].insert(1, run_all_tests_target)

  def Finalize2(self, xcode_targets, xcode_target_to_target_dict):
    # Finalize2 needs to happen in a separate step because the process of
    # updating references to other projects depends on the ordering of targets
    # within remote project files.  Finalize1 is responsible for sorting duty,
    # and once all project files are sorted, Finalize2 can come in and update
    # these references.

    # To support making a "test runner" target that will run all the tests
    # that are direct dependents of any given target, we look for
    # xcode_create_dependents_test_runner being set on an Aggregate target,
    # and generate a second target that will run the tests runners found under
    # the marked target.
    for bf_tgt in self.build_file_dict['targets']:
      if int(bf_tgt.get('xcode_create_dependents_test_runner', 0)):
        tgt_name = bf_tgt['target_name']
        toolset = bf_tgt['toolset']
        qualified_target = gyp.common.QualifiedTarget(self.gyp_path,
                                                      tgt_name, toolset)
        xcode_target = xcode_targets[qualified_target]
        if isinstance(xcode_target, gyp.xcodeproj_file.PBXAggregateTarget):
          # Collect all the run test targets.
          all_run_tests = []
          pbxtds = xcode_target.GetProperty('dependencies')
          for pbxtd in pbxtds:
            pbxcip = pbxtd.GetProperty('targetProxy')
            dependency_xct = pbxcip.GetProperty('remoteGlobalIDString')
            if hasattr(dependency_xct, 'test_runner'):
              all_run_tests.append(dependency_xct.test_runner)

          # Directly depend on all the runners as they depend on the target
          # that builds them.
          if len(all_run_tests) > 0:
            run_all_target = gyp.xcodeproj_file.PBXAggregateTarget({
                  'name':        'Run %s Tests' % tgt_name,
                  'productName': tgt_name,
                },
                parent=self.project)
            for run_test_target in all_run_tests:
              run_all_target.AddDependency(run_test_target)

            # Insert the test runner after the related target.
            idx = self.project._properties['targets'].index(xcode_target)
            self.project._properties['targets'].insert(idx + 1, run_all_target)

    # Update all references to other projects, to make sure that the lists of
    # remote products are complete.  Otherwise, Xcode will fill them in when
    # it opens the project file, which will result in unnecessary diffs.
    # TODO(mark): This is evil because it relies on internal knowledge of
    # PBXProject._other_pbxprojects.
    for other_pbxproject in self.project._other_pbxprojects.keys():
      self.project.AddOrGetProjectReference(other_pbxproject)

    self.project.SortRemoteProductReferences()

    # Give everything an ID.
    self.project_file.ComputeIDs()

    # Make sure that no two objects in the project file have the same ID.  If
    # multiple objects wind up with the same ID, upon loading the file, Xcode
    # will only recognize one object (the last one in the file?) and the
    # results are unpredictable.
    self.project_file.EnsureNoIDCollisions()

  def Write(self):
    # Write the project file to a temporary location first.  Xcode watches for
    # changes to the project file and presents a UI sheet offering to reload
    # the project when it does change.  However, in some cases, especially when
    # multiple projects are open or when Xcode is busy, things don't work so
    # seamlessly.  Sometimes, Xcode is able to detect that a project file has
    # changed but can't unload it because something else is referencing it.
    # To mitigate this problem, and to avoid even having Xcode present the UI
    # sheet when an open project is rewritten for inconsequential changes, the
    # project file is written to a temporary file in the xcodeproj directory
    # first.  The new temporary file is then compared to the existing project
    # file, if any.  If they differ, the new file replaces the old; otherwise,
    # the new project file is simply deleted.  Xcode properly detects a file
    # being renamed over an open project file as a change and so it remains
    # able to present the "project file changed" sheet under this system.
    # Writing to a temporary file first also avoids the possible problem of
    # Xcode rereading an incomplete project file.
    (output_fd, new_pbxproj_path) = \
        tempfile.mkstemp(suffix='.tmp', prefix='project.pbxproj.gyp.',
                         dir=self.path)

    try:
      output_file = os.fdopen(output_fd, 'wb')

      self.project_file.Print(output_file)
      output_file.close()

      pbxproj_path = os.path.join(self.path, 'project.pbxproj')

      same = False
      try:
        same = filecmp.cmp(pbxproj_path, new_pbxproj_path, False)
      except OSError, e:
        if e.errno != errno.ENOENT:
          raise

      if same:
        # The new file is identical to the old one, just get rid of the new
        # one.
        os.unlink(new_pbxproj_path)
      else:
        # The new file is different from the old one, or there is no old one.
        # Rename the new file to the permanent name.
        #
        # tempfile.mkstemp uses an overly restrictive mode, resulting in a
        # file that can only be read by the owner, regardless of the umask.
        # There's no reason to not respect the umask here, which means that
        # an extra hoop is required to fetch it and reset the new file's mode.
        #
        # No way to get the umask without setting a new one?  Set a safe one
        # and then set it back to the old value.
        umask = os.umask(077)
        os.umask(umask)

        os.chmod(new_pbxproj_path, 0666 & ~umask)
        os.rename(new_pbxproj_path, pbxproj_path)

    except Exception:
      # Don't leave turds behind.  In fact, if this code was responsible for
      # creating the xcodeproj directory, get rid of that too.
      os.unlink(new_pbxproj_path)
      if self.created_dir:
        shutil.rmtree(self.path, True)
      raise


cached_xcode_version = None
def InstalledXcodeVersion():
  """Fetches the installed version of Xcode, returns empty string if it is
  unable to figure it out."""

  global cached_xcode_version
  if not cached_xcode_version is None:
    return cached_xcode_version

  # Default to an empty string
  cached_xcode_version = ''

  # Collect the xcodebuild's version information.
  try:
    import subprocess
    cmd = ['/usr/bin/xcodebuild', '-version']
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    xcodebuild_version_info = proc.communicate()[0]
    # Any error, return empty string
    if proc.returncode:
      xcodebuild_version_info = ''
  except OSError:
    # We failed to launch the tool
    xcodebuild_version_info = ''

  # Pull out the Xcode version itself.
  match_line = re.search('^Xcode (.*)$', xcodebuild_version_info, re.MULTILINE)
  if match_line:
    cached_xcode_version = match_line.group(1)
  # Done!
  return cached_xcode_version


def AddSourceToTarget(source, type, pbxp, xct):
  # TODO(mark): Perhaps source_extensions and library_extensions can be made a
  # little bit fancier.
  source_extensions = ['c', 'cc', 'cpp', 'cxx', 'm', 'mm', 's']

  # .o is conceptually more of a "source" than a "library," but Xcode thinks
  # of "sources" as things to compile and "libraries" (or "frameworks") as
  # things to link with. Adding an object file to an Xcode target's frameworks
  # phase works properly.
  library_extensions = ['a', 'dylib', 'framework', 'o']

  basename = posixpath.basename(source)
  (root, ext) = posixpath.splitext(basename)
  if ext:
    ext = ext[1:].lower()

  if ext in source_extensions and type != 'none':
    xct.SourcesPhase().AddFile(source)
  elif ext in library_extensions and type != 'none':
    xct.FrameworksPhase().AddFile(source)
  else:
    # Files that aren't added to a sources or frameworks build phase can still
    # go into the project file, just not as part of a build phase.
    pbxp.AddOrGetFileInRootGroup(source)


def AddResourceToTarget(resource, pbxp, xct):
  # TODO(mark): Combine with AddSourceToTarget above?  Or just inline this call
  # where it's used.
  xct.ResourcesPhase().AddFile(resource)


def AddHeaderToTarget(header, pbxp, xct, is_public):
  # TODO(mark): Combine with AddSourceToTarget above?  Or just inline this call
  # where it's used.
  settings = '{ATTRIBUTES = (%s, ); }' % ('Private', 'Public')[is_public]
  xct.HeadersPhase().AddFile(header, settings)


_xcode_variable_re = re.compile('(\$\((.*?)\))')
def ExpandXcodeVariables(string, expansions):
  """Expands Xcode-style $(VARIABLES) in string per the expansions dict.

  In some rare cases, it is appropriate to expand Xcode variables when a
  project file is generated.  For any substring $(VAR) in string, if VAR is a
  key in the expansions dict, $(VAR) will be replaced with expansions[VAR].
  Any $(VAR) substring in string for which VAR is not a key in the expansions
  dict will remain in the returned string.
  """

  matches = _xcode_variable_re.findall(string)
  if matches == None:
    return string

  matches.reverse()
  for match in matches:
    (to_replace, variable) = match
    if not variable in expansions:
      continue

    replacement = expansions[variable]
    string = re.sub(re.escape(to_replace), replacement, string)

  return string


def EscapeXCodeArgument(s):
  """We must escape the arguments that we give to XCode so that it knows not to
     split on spaces and to respect backslash and quote literals."""
  s = s.replace('\\', '\\\\')
  s = s.replace('"', '\\"')
  return '"' + s + '"'



def PerformBuild(data, configurations, params):
  options = params['options']

  for build_file, build_file_dict in data.iteritems():
    (build_file_root, build_file_ext) = os.path.splitext(build_file)
    if build_file_ext != '.gyp':
      continue
    xcodeproj_path = build_file_root + options.suffix + '.xcodeproj'
    if options.generator_output:
      xcodeproj_path = os.path.join(options.generator_output, xcodeproj_path)

  for config in configurations:
    arguments = ['xcodebuild', '-project', xcodeproj_path]
    arguments += ['-configuration', config]
    print "Building [%s]: %s" % (config, arguments)
    subprocess.check_call(arguments)


def GenerateOutput(target_list, target_dicts, data, params):
  options = params['options']
  generator_flags = params.get('generator_flags', {})
  parallel_builds = generator_flags.get('xcode_parallel_builds', True)
  serialize_all_tests = \
      generator_flags.get('xcode_serialize_all_test_runs', True)
  project_version = generator_flags.get('xcode_project_version', None)
  skip_excluded_files = \
      not generator_flags.get('xcode_list_excluded_files', True)
  xcode_projects = {}
  for build_file, build_file_dict in data.iteritems():
    (build_file_root, build_file_ext) = os.path.splitext(build_file)
    if build_file_ext != '.gyp':
      continue
    xcodeproj_path = build_file_root + options.suffix + '.xcodeproj'
    if options.generator_output:
      xcodeproj_path = os.path.join(options.generator_output, xcodeproj_path)
    xcp = XcodeProject(build_file, xcodeproj_path, build_file_dict)
    xcode_projects[build_file] = xcp
    pbxp = xcp.project

    if parallel_builds:
      pbxp.SetProperty('attributes',
                       {'BuildIndependentTargetsInParallel': 'YES'})
    if project_version:
      xcp.project_file.SetXcodeVersion(project_version)

    # Add gyp/gypi files to project
    if not generator_flags.get('standalone'):
      main_group = pbxp.GetProperty('mainGroup')
      build_group = gyp.xcodeproj_file.PBXGroup({'name': 'Build'})
      main_group.AppendChild(build_group)
      for included_file in build_file_dict['included_files']:
        build_group.AddOrGetFileByPath(included_file, False)

  xcode_targets = {}
  xcode_target_to_target_dict = {}
  for qualified_target in target_list:
    [build_file, target_name, toolset] = \
        gyp.common.ParseQualifiedTarget(qualified_target)

    spec = target_dicts[qualified_target]
    if spec['toolset'] != 'target':
      raise Exception(
          'Multiple toolsets not supported in xcode build (target %s)' %
          qualified_target)
    configuration_names = [spec['default_configuration']]
    for configuration_name in sorted(spec['configurations'].keys()):
      if configuration_name not in configuration_names:
        configuration_names.append(configuration_name)
    xcp = xcode_projects[build_file]
    pbxp = xcp.project

    # Set up the configurations for the target according to the list of names
    # supplied.
    xccl = CreateXCConfigurationList(configuration_names)

    # Create an XCTarget subclass object for the target. The type with
    # "+bundle" appended will be used if the target has "mac_bundle" set.
    # loadable_modules not in a mac_bundle are mapped to
    # com.googlecode.gyp.xcode.bundle, a pseudo-type that xcode.py interprets
    # to create a single-file mh_bundle.
    _types = {
      'executable':             'com.apple.product-type.tool',
      'loadable_module':        'com.googlecode.gyp.xcode.bundle',
      'shared_library':         'com.apple.product-type.library.dynamic',
      'static_library':         'com.apple.product-type.library.static',
      'executable+bundle':      'com.apple.product-type.application',
      'loadable_module+bundle': 'com.apple.product-type.bundle',
      'shared_library+bundle':  'com.apple.product-type.framework',
    }

    target_properties = {
      'buildConfigurationList': xccl,
      'name':                   target_name,
    }

    type = spec['type']
    is_bundle = int(spec.get('mac_bundle', 0))
    if type != 'none':
      type_bundle_key = type
      if is_bundle:
        type_bundle_key += '+bundle'
      xctarget_type = gyp.xcodeproj_file.PBXNativeTarget
      try:
        target_properties['productType'] = _types[type_bundle_key]
      except KeyError, e:
        gyp.common.ExceptionAppend(e, "-- unknown product type while "
                                   "writing target %s" % target_name)
        raise
    else:
      xctarget_type = gyp.xcodeproj_file.PBXAggregateTarget
      assert not is_bundle, (
          'mac_bundle targets cannot have type none (target "%s")' %
          target_name)

    target_product_name = spec.get('product_name')
    if target_product_name is not None:
      target_properties['productName'] = target_product_name

    xct = xctarget_type(target_properties, parent=pbxp,
                        force_outdir=spec.get('product_dir'),
                        force_prefix=spec.get('product_prefix'),
                        force_extension=spec.get('product_extension'))
    pbxp.AppendProperty('targets', xct)
    xcode_targets[qualified_target] = xct
    xcode_target_to_target_dict[xct] = spec

    spec_actions = spec.get('actions', [])
    spec_rules = spec.get('rules', [])

    # Xcode has some "issues" with checking dependencies for the "Compile
    # sources" step with any source files/headers generated by actions/rules.
    # To work around this, if a target is building anything directly (not
    # type "none"), then a second target is used to run the GYP actions/rules
    # and is made a dependency of this target.  This way the work is done
    # before the dependency checks for what should be recompiled.
    support_xct = None
    if type != 'none' and (spec_actions or spec_rules):
      support_xccl = CreateXCConfigurationList(configuration_names);
      support_target_properties = {
        'buildConfigurationList': support_xccl,
        'name':                   target_name + ' Support',
      }
      if target_product_name:
        support_target_properties['productName'] = \
            target_product_name + ' Support'
      support_xct = \
          gyp.xcodeproj_file.PBXAggregateTarget(support_target_properties,
                                                parent=pbxp)
      pbxp.AppendProperty('targets', support_xct)
      xct.AddDependency(support_xct)
    # Hang the support target off the main target so it can be tested/found
    # by the generator during Finalize.
    xct.support_target = support_xct

    prebuild_index = 0

    # Add custom shell script phases for "actions" sections.
    for action in spec_actions:
      # There's no need to write anything into the script to ensure that the
      # output directories already exist, because Xcode will look at the
      # declared outputs and automatically ensure that they exist for us.

      # Do we have a message to print when this action runs?
      message = action.get('message')
      if message:
        message = 'echo note: ' + gyp.common.EncodePOSIXShellArgument(message)
      else:
        message = ''

      # Turn the list into a string that can be passed to a shell.
      action_string = gyp.common.EncodePOSIXShellList(action['action'])

      # Convert Xcode-type variable references to sh-compatible environment
      # variable references.
      message_sh = gyp.xcodeproj_file.ConvertVariablesToShellSyntax(message)
      action_string_sh = gyp.xcodeproj_file.ConvertVariablesToShellSyntax(
        action_string)

      script = ''
      # Include the optional message
      if message_sh:
        script += message_sh + '\n'
      # Be sure the script runs in exec, and that if exec fails, the script
      # exits signalling an error.
      script += 'exec ' + action_string_sh + '\nexit 1\n'
      ssbp = gyp.xcodeproj_file.PBXShellScriptBuildPhase({
            'inputPaths': action['inputs'],
            'name': 'Action "' + action['action_name'] + '"',
            'outputPaths': action['outputs'],
            'shellScript': script,
            'showEnvVarsInLog': 0,
          })

      if support_xct:
        support_xct.AppendProperty('buildPhases', ssbp)
      else:
        # TODO(mark): this assumes too much knowledge of the internals of
        # xcodeproj_file; some of these smarts should move into xcodeproj_file
        # itself.
        xct._properties['buildPhases'].insert(prebuild_index, ssbp)
        prebuild_index = prebuild_index + 1

      # TODO(mark): Should verify that at most one of these is specified.
      if int(action.get('process_outputs_as_sources', False)):
        for output in action['outputs']:
          AddSourceToTarget(output, type, pbxp, xct)

      if int(action.get('process_outputs_as_mac_bundle_resources', False)):
        for output in action['outputs']:
          AddResourceToTarget(output, pbxp, xct)

    # tgt_mac_bundle_resources holds the list of bundle resources so
    # the rule processing can check against it.
    if is_bundle:
      tgt_mac_bundle_resources = spec.get('mac_bundle_resources', [])
    else:
      tgt_mac_bundle_resources = []

    # Add custom shell script phases driving "make" for "rules" sections.
    #
    # Xcode's built-in rule support is almost powerful enough to use directly,
    # but there are a few significant deficiencies that render them unusable.
    # There are workarounds for some of its inadequacies, but in aggregate,
    # the workarounds added complexity to the generator, and some workarounds
    # actually require input files to be crafted more carefully than I'd like.
    # Consequently, until Xcode rules are made more capable, "rules" input
    # sections will be handled in Xcode output by shell script build phases
    # performed prior to the compilation phase.
    #
    # The following problems with Xcode rules were found.  The numbers are
    # Apple radar IDs.  I hope that these shortcomings are addressed, I really
    # liked having the rules handled directly in Xcode during the period that
    # I was prototyping this.
    #
    # 6588600 Xcode compiles custom script rule outputs too soon, compilation
    #         fails.  This occurs when rule outputs from distinct inputs are
    #         interdependent.  The only workaround is to put rules and their
    #         inputs in a separate target from the one that compiles the rule
    #         outputs.  This requires input file cooperation and it means that
    #         process_outputs_as_sources is unusable.
    # 6584932 Need to declare that custom rule outputs should be excluded from
    #         compilation.  A possible workaround is to lie to Xcode about a
    #         rule's output, giving it a dummy file it doesn't know how to
    #         compile.  The rule action script would need to touch the dummy.
    # 6584839 I need a way to declare additional inputs to a custom rule.
    #         A possible workaround is a shell script phase prior to
    #         compilation that touches a rule's primary input files if any
    #         would-be additional inputs are newer than the output.  Modifying
    #         the source tree - even just modification times - feels dirty.
    # 6564240 Xcode "custom script" build rules always dump all environment
    #         variables.  This is a low-prioroty problem and is not a
    #         show-stopper.
    rules_by_ext = {}
    for rule in spec_rules:
      rules_by_ext[rule['extension']] = rule

      # First, some definitions:
      #
      # A "rule source" is a file that was listed in a target's "sources"
      # list and will have a rule applied to it on the basis of matching the
      # rule's "extensions" attribute.  Rule sources are direct inputs to
      # rules.
      #
      # Rule definitions may specify additional inputs in their "inputs"
      # attribute.  These additional inputs are used for dependency tracking
      # purposes.
      #
      # A "concrete output" is a rule output with input-dependent variables
      # resolved.  For example, given a rule with:
      #   'extension': 'ext', 'outputs': ['$(INPUT_FILE_BASE).cc'],
      # if the target's "sources" list contained "one.ext" and "two.ext",
      # the "concrete output" for rule input "two.ext" would be "two.cc".  If
      # a rule specifies multiple outputs, each input file that the rule is
      # applied to will have the same number of concrete outputs.
      #
      # If any concrete outputs are outdated or missing relative to their
      # corresponding rule_source or to any specified additional input, the
      # rule action must be performed to generate the concrete outputs.

      # concrete_outputs_by_rule_source will have an item at the same index
      # as the rule['rule_sources'] that it corresponds to.  Each item is a
      # list of all of the concrete outputs for the rule_source.
      concrete_outputs_by_rule_source = []

      # concrete_outputs_all is a flat list of all concrete outputs that this
      # rule is able to produce, given the known set of input files
      # (rule_sources) that apply to it.
      concrete_outputs_all = []

      # messages & actions are keyed by the same indices as rule['rule_sources']
      # and concrete_outputs_by_rule_source.  They contain the message and
      # action to perform after resolving input-dependent variables.  The
      # message is optional, in which case None is stored for each rule source.
      messages = []
      actions = []

      for rule_source in rule.get('rule_sources', []):
        rule_source_dirname, rule_source_basename = \
            posixpath.split(rule_source)
        (rule_source_root, rule_source_ext) = \
            posixpath.splitext(rule_source_basename)

        # These are the same variable names that Xcode uses for its own native
        # rule support.  Because Xcode's rule engine is not being used, they
        # need to be expanded as they are written to the makefile.
        rule_input_dict = {
          'INPUT_FILE_BASE':   rule_source_root,
          'INPUT_FILE_SUFFIX': rule_source_ext,
          'INPUT_FILE_NAME':   rule_source_basename,
          'INPUT_FILE_PATH':   rule_source,
          'INPUT_FILE_DIRNAME': rule_source_dirname,
        }

        concrete_outputs_for_this_rule_source = []
        for output in rule.get('outputs', []):
          # Fortunately, Xcode and make both use $(VAR) format for their
          # variables, so the expansion is the only transformation necessary.
          # Any remaning $(VAR)-type variables in the string can be given
          # directly to make, which will pick up the correct settings from
          # what Xcode puts into the environment.
          concrete_output = ExpandXcodeVariables(output, rule_input_dict)
          concrete_outputs_for_this_rule_source.append(concrete_output)

          # Add all concrete outputs to the project.
          pbxp.AddOrGetFileInRootGroup(concrete_output)

        concrete_outputs_by_rule_source.append( \
            concrete_outputs_for_this_rule_source)
        concrete_outputs_all.extend(concrete_outputs_for_this_rule_source)

        # TODO(mark): Should verify that at most one of these is specified.
        if int(rule.get('process_outputs_as_sources', False)):
          for output in concrete_outputs_for_this_rule_source:
            AddSourceToTarget(output, type, pbxp, xct)

        # If the file came from the mac_bundle_resources list or if the rule
        # is marked to process outputs as bundle resource, do so.
        was_mac_bundle_resource = rule_source in tgt_mac_bundle_resources
        if was_mac_bundle_resource or \
            int(rule.get('process_outputs_as_mac_bundle_resources', False)):
          for output in concrete_outputs_for_this_rule_source:
            AddResourceToTarget(output, pbxp, xct)

        # Do we have a message to print when this rule runs?
        message = rule.get('message')
        if message:
          message = gyp.common.EncodePOSIXShellArgument(message)
          message = ExpandXcodeVariables(message, rule_input_dict)
        messages.append(message)

        # Turn the list into a string that can be passed to a shell.
        action_string = gyp.common.EncodePOSIXShellList(rule['action'])

        action = ExpandXcodeVariables(action_string, rule_input_dict)
        actions.append(action)

      if len(concrete_outputs_all) > 0:
        # TODO(mark): There's a possibilty for collision here.  Consider
        # target "t" rule "A_r" and target "t_A" rule "r".
        makefile_name = '%s.make' % re.sub(
            '[^a-zA-Z0-9_]', '_' , '%s_%s' % (target_name, rule['rule_name']))
        makefile_path = os.path.join(xcode_projects[build_file].path,
                                     makefile_name)
        # TODO(mark): try/close?  Write to a temporary file and swap it only
        # if it's got changes?
        makefile = open(makefile_path, 'wb')

        # make will build the first target in the makefile by default.  By
        # convention, it's called "all".  List all (or at least one)
        # concrete output for each rule source as a prerequisite of the "all"
        # target.
        makefile.write('all: \\\n')
        for concrete_output_index in \
            xrange(0, len(concrete_outputs_by_rule_source)):
          # Only list the first (index [0]) concrete output of each input
          # in the "all" target.  Otherwise, a parallel make (-j > 1) would
          # attempt to process each input multiple times simultaneously.
          # Otherwise, "all" could just contain the entire list of
          # concrete_outputs_all.
          concrete_output = \
              concrete_outputs_by_rule_source[concrete_output_index][0]
          if concrete_output_index == len(concrete_outputs_by_rule_source) - 1:
            eol = ''
          else:
            eol = ' \\'
          makefile.write('    %s%s\n' % (concrete_output, eol))

        for (rule_source, concrete_outputs, message, action) in \
            zip(rule['rule_sources'], concrete_outputs_by_rule_source,
                messages, actions):
          makefile.write('\n')

          # Add a rule that declares it can build each concrete output of a
          # rule source.  Collect the names of the directories that are
          # required.
          concrete_output_dirs = []
          for concrete_output_index in xrange(0, len(concrete_outputs)):
            concrete_output = concrete_outputs[concrete_output_index]
            if concrete_output_index == 0:
              bol = ''
            else:
              bol = '    '
            makefile.write('%s%s \\\n' % (bol, concrete_output))

            concrete_output_dir = posixpath.dirname(concrete_output)
            if (concrete_output_dir and
                concrete_output_dir not in concrete_output_dirs):
              concrete_output_dirs.append(concrete_output_dir)

          makefile.write('    : \\\n')

          # The prerequisites for this rule are the rule source itself and
          # the set of additional rule inputs, if any.
          prerequisites = [rule_source]
          prerequisites.extend(rule.get('inputs', []))
          for prerequisite_index in xrange(0, len(prerequisites)):
            prerequisite = prerequisites[prerequisite_index]
            if prerequisite_index == len(prerequisites) - 1:
              eol = ''
            else:
              eol = ' \\'
            makefile.write('    %s%s\n' % (prerequisite, eol))

          # Make sure that output directories exist before executing the rule
          # action.
          if len(concrete_output_dirs) > 0:
            makefile.write('\t@mkdir -p "%s"\n' %
                           '" "'.join(concrete_output_dirs))

          # The rule message and action have already had the necessary variable
          # substitutions performed.
          if message:
            # Mark it with note: so Xcode picks it up in build output.
            makefile.write('\t@echo note: %s\n' % message)
          makefile.write('\t%s\n' % action)

        makefile.close()

        # It might be nice to ensure that needed output directories exist
        # here rather than in each target in the Makefile, but that wouldn't
        # work if there ever was a concrete output that had an input-dependent
        # variable anywhere other than in the leaf position.

        # Don't declare any inputPaths or outputPaths.  If they're present,
        # Xcode will provide a slight optimization by only running the script
        # phase if any output is missing or outdated relative to any input.
        # Unfortunately, it will also assume that all outputs are touched by
        # the script, and if the outputs serve as files in a compilation
        # phase, they will be unconditionally rebuilt.  Since make might not
        # rebuild everything that could be declared here as an output, this
        # extra compilation activity is unnecessary.  With inputPaths and
        # outputPaths not supplied, make will always be called, but it knows
        # enough to not do anything when everything is up-to-date.

        # To help speed things up, pass -j COUNT to make so it does some work
        # in parallel.  Don't use ncpus because Xcode will build ncpus targets
        # in parallel and if each target happens to have a rules step, there
        # would be ncpus^2 things going.  With a machine that has 2 quad-core
        # Xeons, a build can quickly run out of processes based on
        # scheduling/other tasks, and randomly failing builds are no good.
        script = \
"""JOB_COUNT="$(/usr/sbin/sysctl -n hw.ncpu)"
if [ "${JOB_COUNT}" -gt 4 ]; then
  JOB_COUNT=4
fi
exec "${DEVELOPER_BIN_DIR}/make" -f "${PROJECT_FILE_PATH}/%s" -j "${JOB_COUNT}"
exit 1
""" % makefile_name
        ssbp = gyp.xcodeproj_file.PBXShellScriptBuildPhase({
              'name': 'Rule "' + rule['rule_name'] + '"',
              'shellScript': script,
              'showEnvVarsInLog': 0,
            })

        if support_xct:
          support_xct.AppendProperty('buildPhases', ssbp)
        else:
          # TODO(mark): this assumes too much knowledge of the internals of
          # xcodeproj_file; some of these smarts should move into xcodeproj_file
          # itself.
          xct._properties['buildPhases'].insert(prebuild_index, ssbp)
          prebuild_index = prebuild_index + 1

      # Extra rule inputs also go into the project file.  Concrete outputs were
      # already added when they were computed.
      groups = ['inputs', 'inputs_excluded']
      if skip_excluded_files:
        groups = [x for x in groups if not x.endswith('_excluded')]
      for group in groups:
        for item in rule.get(group, []):
          pbxp.AddOrGetFileInRootGroup(item)

    # Add "sources".
    for source in spec.get('sources', []):
      (source_root, source_extension) = posixpath.splitext(source)
      if source_extension[1:] not in rules_by_ext:
        # AddSourceToTarget will add the file to a root group if it's not
        # already there.
        AddSourceToTarget(source, type, pbxp, xct)
      else:
        pbxp.AddOrGetFileInRootGroup(source)

    # Add "mac_bundle_resources" and "mac_framework_private_headers" if
    # it's a bundle of any type.
    if is_bundle:
      for resource in tgt_mac_bundle_resources:
        (resource_root, resource_extension) = posixpath.splitext(resource)
        if resource_extension[1:] not in rules_by_ext:
          AddResourceToTarget(resource, pbxp, xct)
        else:
          pbxp.AddOrGetFileInRootGroup(resource)

      for header in spec.get('mac_framework_private_headers', []):
        AddHeaderToTarget(header, pbxp, xct, False)

    # Add "mac_framework_headers". These can be valid for both frameworks
    # and static libraries.
    if is_bundle or type == 'static_library':
      for header in spec.get('mac_framework_headers', []):
        AddHeaderToTarget(header, pbxp, xct, True)

    # Add "copies".
    for copy_group in spec.get('copies', []):
      pbxcp = gyp.xcodeproj_file.PBXCopyFilesBuildPhase({
            'name': 'Copy to ' + copy_group['destination']
          },
          parent=xct)
      dest = copy_group['destination']
      if dest[0] not in ('/', '$'):
        # Relative paths are relative to $(SRCROOT).
        dest = '$(SRCROOT)/' + dest
      pbxcp.SetDestination(dest)

      # TODO(mark): The usual comment about this knowing too much about
      # gyp.xcodeproj_file internals applies.
      xct._properties['buildPhases'].insert(prebuild_index, pbxcp)

      for file in copy_group['files']:
        pbxcp.AddFile(file)

    # Excluded files can also go into the project file.
    if not skip_excluded_files:
      for key in ['sources', 'mac_bundle_resources', 'mac_framework_headers',
                  'mac_framework_private_headers']:
        excluded_key = key + '_excluded'
        for item in spec.get(excluded_key, []):
          pbxp.AddOrGetFileInRootGroup(item)

    # So can "inputs" and "outputs" sections of "actions" groups.
    groups = ['inputs', 'inputs_excluded', 'outputs', 'outputs_excluded']
    if skip_excluded_files:
      groups = [x for x in groups if not x.endswith('_excluded')]
    for action in spec.get('actions', []):
      for group in groups:
        for item in action.get(group, []):
          # Exclude anything in BUILT_PRODUCTS_DIR.  They're products, not
          # sources.
          if not item.startswith('$(BUILT_PRODUCTS_DIR)/'):
            pbxp.AddOrGetFileInRootGroup(item)

    for postbuild in spec.get('postbuilds', []):
      action_string_sh = gyp.common.EncodePOSIXShellList(postbuild['action'])
      script = 'exec ' + action_string_sh + '\nexit 1\n'

      # Make the postbuild step depend on the output of ld or ar from this
      # target. Apparently putting the script step after the link step isn't
      # sufficient to ensure proper ordering in all cases. With an input
      # declared but no outputs, the script step should run every time, as
      # desired.
      ssbp = gyp.xcodeproj_file.PBXShellScriptBuildPhase({
            'inputPaths': ['$(BUILT_PRODUCTS_DIR)/$(EXECUTABLE_PATH)'],
            'name': 'Postbuild "' + postbuild['postbuild_name'] + '"',
            'shellScript': script,
            'showEnvVarsInLog': 0,
          })
      xct.AppendProperty('buildPhases', ssbp)

    # Add dependencies before libraries, because adding a dependency may imply
    # adding a library.  It's preferable to keep dependencies listed first
    # during a link phase so that they can override symbols that would
    # otherwise be provided by libraries, which will usually include system
    # libraries.  On some systems, ld is finicky and even requires the
    # libraries to be ordered in such a way that unresolved symbols in
    # earlier-listed libraries may only be resolved by later-listed libraries.
    # The Mac linker doesn't work that way, but other platforms do, and so
    # their linker invocations need to be constructed in this way.  There's
    # no compelling reason for Xcode's linker invocations to differ.

    if 'dependencies' in spec:
      for dependency in spec['dependencies']:
        xct.AddDependency(xcode_targets[dependency])
        # The support project also gets the dependencies (in case they are
        # needed for the actions/rules to work).
        if support_xct:
          support_xct.AddDependency(xcode_targets[dependency])

    if 'libraries' in spec:
      for library in spec['libraries']:
        xct.FrameworksPhase().AddFile(library)
        # Add the library's directory to LIBRARY_SEARCH_PATHS if necessary.
        # I wish Xcode handled this automatically.
        library_dir = posixpath.dirname(library)
        if library_dir not in xcode_standard_library_dirs and (
            not xct.HasBuildSetting(_library_search_paths_var) or
            library_dir not in xct.GetBuildSetting(_library_search_paths_var)):
          xct.AppendBuildSetting(_library_search_paths_var, library_dir)

    for configuration_name in configuration_names:
      configuration = spec['configurations'][configuration_name]
      xcbc = xct.ConfigurationNamed(configuration_name)
      for include_dir in configuration.get('mac_framework_dirs', []):
        xcbc.AppendBuildSetting('FRAMEWORK_SEARCH_PATHS', include_dir)
      for include_dir in configuration.get('include_dirs', []):
        xcbc.AppendBuildSetting('HEADER_SEARCH_PATHS', include_dir)
      if 'defines' in configuration:
        for define in configuration['defines']:
          set_define = EscapeXCodeArgument(define)
          xcbc.AppendBuildSetting('GCC_PREPROCESSOR_DEFINITIONS', set_define)
      if 'xcode_settings' in configuration:
        for xck, xcv in configuration['xcode_settings'].iteritems():
          xcbc.SetBuildSetting(xck, xcv)
      if 'xcode_config_file' in configuration:
        config_ref = pbxp.AddOrGetFileInRootGroup(
            configuration['xcode_config_file'])
        xcbc.SetBaseConfiguration(config_ref)

  build_files = []
  for build_file, build_file_dict in data.iteritems():
    if build_file.endswith('.gyp'):
      build_files.append(build_file)

  for build_file in build_files:
    xcode_projects[build_file].Finalize1(xcode_targets, serialize_all_tests)

  for build_file in build_files:
    xcode_projects[build_file].Finalize2(xcode_targets,
                                         xcode_target_to_target_dict)

  for build_file in build_files:
    xcode_projects[build_file].Write()

########NEW FILE########
__FILENAME__ = input
# Copyright (c) 2012 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from compiler.ast import Const
from compiler.ast import Dict
from compiler.ast import Discard
from compiler.ast import List
from compiler.ast import Module
from compiler.ast import Node
from compiler.ast import Stmt
import compiler
import copy
import gyp.common
import multiprocessing
import optparse
import os.path
import re
import shlex
import signal
import subprocess
import sys
import threading
import time
from gyp.common import GypError


# A list of types that are treated as linkable.
linkable_types = ['executable', 'shared_library', 'loadable_module']

# A list of sections that contain links to other targets.
dependency_sections = ['dependencies', 'export_dependent_settings']

# base_path_sections is a list of sections defined by GYP that contain
# pathnames.  The generators can provide more keys, the two lists are merged
# into path_sections, but you should call IsPathSection instead of using either
# list directly.
base_path_sections = [
  'destination',
  'files',
  'include_dirs',
  'inputs',
  'libraries',
  'outputs',
  'sources',
]
path_sections = []


def IsPathSection(section):
  # If section ends in one of these characters, it's applied to a section
  # without the trailing characters.  '/' is notably absent from this list,
  # because there's no way for a regular expression to be treated as a path.
  while section[-1:] in ('=', '+', '?', '!'):
    section = section[0:-1]

  if section in path_sections or \
     section.endswith('_dir') or section.endswith('_dirs') or \
     section.endswith('_file') or section.endswith('_files') or \
     section.endswith('_path') or section.endswith('_paths'):
    return True
  return False


# base_non_configuraiton_keys is a list of key names that belong in the target
# itself and should not be propagated into its configurations.  It is merged
# with a list that can come from the generator to
# create non_configuration_keys.
base_non_configuration_keys = [
  # Sections that must exist inside targets and not configurations.
  'actions',
  'configurations',
  'copies',
  'default_configuration',
  'dependencies',
  'dependencies_original',
  'link_languages',
  'libraries',
  'postbuilds',
  'product_dir',
  'product_extension',
  'product_name',
  'product_prefix',
  'rules',
  'run_as',
  'sources',
  'standalone_static_library',
  'suppress_wildcard',
  'target_name',
  'toolset',
  'toolsets',
  'type',
  'variants',

  # Sections that can be found inside targets or configurations, but that
  # should not be propagated from targets into their configurations.
  'variables',
]
non_configuration_keys = []

# Keys that do not belong inside a configuration dictionary.
invalid_configuration_keys = [
  'actions',
  'all_dependent_settings',
  'configurations',
  'dependencies',
  'direct_dependent_settings',
  'libraries',
  'link_settings',
  'sources',
  'standalone_static_library',
  'target_name',
  'type',
]

# Controls how the generator want the build file paths.
absolute_build_file_paths = False

# Controls whether or not the generator supports multiple toolsets.
multiple_toolsets = False


def GetIncludedBuildFiles(build_file_path, aux_data, included=None):
  """Return a list of all build files included into build_file_path.

  The returned list will contain build_file_path as well as all other files
  that it included, either directly or indirectly.  Note that the list may
  contain files that were included into a conditional section that evaluated
  to false and was not merged into build_file_path's dict.

  aux_data is a dict containing a key for each build file or included build
  file.  Those keys provide access to dicts whose "included" keys contain
  lists of all other files included by the build file.

  included should be left at its default None value by external callers.  It
  is used for recursion.

  The returned list will not contain any duplicate entries.  Each build file
  in the list will be relative to the current directory.
  """

  if included == None:
    included = []

  if build_file_path in included:
    return included

  included.append(build_file_path)

  for included_build_file in aux_data[build_file_path].get('included', []):
    GetIncludedBuildFiles(included_build_file, aux_data, included)

  return included


def CheckedEval(file_contents):
  """Return the eval of a gyp file.

  The gyp file is restricted to dictionaries and lists only, and
  repeated keys are not allowed.

  Note that this is slower than eval() is.
  """

  ast = compiler.parse(file_contents)
  assert isinstance(ast, Module)
  c1 = ast.getChildren()
  assert c1[0] is None
  assert isinstance(c1[1], Stmt)
  c2 = c1[1].getChildren()
  assert isinstance(c2[0], Discard)
  c3 = c2[0].getChildren()
  assert len(c3) == 1
  return CheckNode(c3[0], [])


def CheckNode(node, keypath):
  if isinstance(node, Dict):
    c = node.getChildren()
    dict = {}
    for n in range(0, len(c), 2):
      assert isinstance(c[n], Const)
      key = c[n].getChildren()[0]
      if key in dict:
        raise GypError("Key '" + key + "' repeated at level " +
              repr(len(keypath) + 1) + " with key path '" +
              '.'.join(keypath) + "'")
      kp = list(keypath)  # Make a copy of the list for descending this node.
      kp.append(key)
      dict[key] = CheckNode(c[n + 1], kp)
    return dict
  elif isinstance(node, List):
    c = node.getChildren()
    children = []
    for index, child in enumerate(c):
      kp = list(keypath)  # Copy list.
      kp.append(repr(index))
      children.append(CheckNode(child, kp))
    return children
  elif isinstance(node, Const):
    return node.getChildren()[0]
  else:
    raise TypeError, "Unknown AST node at key path '" + '.'.join(keypath) + \
         "': " + repr(node)


def LoadOneBuildFile(build_file_path, data, aux_data, variables, includes,
                     is_target, check):
  if build_file_path in data:
    return data[build_file_path]

  if os.path.exists(build_file_path):
    build_file_contents = open(build_file_path).read()
  else:
    raise GypError("%s not found (cwd: %s)" % (build_file_path, os.getcwd()))

  build_file_data = None
  try:
    if check:
      build_file_data = CheckedEval(build_file_contents)
    else:
      build_file_data = eval(build_file_contents, {'__builtins__': None},
                             None)
  except SyntaxError, e:
    e.filename = build_file_path
    raise
  except Exception, e:
    gyp.common.ExceptionAppend(e, 'while reading ' + build_file_path)
    raise

  data[build_file_path] = build_file_data
  aux_data[build_file_path] = {}

  # Scan for includes and merge them in.
  try:
    if is_target:
      LoadBuildFileIncludesIntoDict(build_file_data, build_file_path, data,
                                    aux_data, variables, includes, check)
    else:
      LoadBuildFileIncludesIntoDict(build_file_data, build_file_path, data,
                                    aux_data, variables, None, check)
  except Exception, e:
    gyp.common.ExceptionAppend(e,
                               'while reading includes of ' + build_file_path)
    raise

  return build_file_data


def LoadBuildFileIncludesIntoDict(subdict, subdict_path, data, aux_data,
                                  variables, includes, check):
  includes_list = []
  if includes != None:
    includes_list.extend(includes)
  if 'includes' in subdict:
    for include in subdict['includes']:
      # "include" is specified relative to subdict_path, so compute the real
      # path to include by appending the provided "include" to the directory
      # in which subdict_path resides.
      relative_include = \
          os.path.normpath(os.path.join(os.path.dirname(subdict_path), include))
      includes_list.append(relative_include)
    # Unhook the includes list, it's no longer needed.
    del subdict['includes']

  # Merge in the included files.
  for include in includes_list:
    if not 'included' in aux_data[subdict_path]:
      aux_data[subdict_path]['included'] = []
    aux_data[subdict_path]['included'].append(include)

    gyp.DebugOutput(gyp.DEBUG_INCLUDES, "Loading Included File: '%s'" % include)

    MergeDicts(subdict,
               LoadOneBuildFile(include, data, aux_data, variables, None,
                                False, check),
               subdict_path, include)

  # Recurse into subdictionaries.
  for k, v in subdict.iteritems():
    if v.__class__ == dict:
      LoadBuildFileIncludesIntoDict(v, subdict_path, data, aux_data, variables,
                                    None, check)
    elif v.__class__ == list:
      LoadBuildFileIncludesIntoList(v, subdict_path, data, aux_data, variables,
                                    check)


# This recurses into lists so that it can look for dicts.
def LoadBuildFileIncludesIntoList(sublist, sublist_path, data, aux_data,
                                  variables, check):
  for item in sublist:
    if item.__class__ == dict:
      LoadBuildFileIncludesIntoDict(item, sublist_path, data, aux_data,
                                    variables, None, check)
    elif item.__class__ == list:
      LoadBuildFileIncludesIntoList(item, sublist_path, data, aux_data,
                                    variables, check)

# Processes toolsets in all the targets. This recurses into condition entries
# since they can contain toolsets as well.
def ProcessToolsetsInDict(data):
  if 'targets' in data:
    target_list = data['targets']
    new_target_list = []
    for target in target_list:
      # If this target already has an explicit 'toolset', and no 'toolsets'
      # list, don't modify it further.
      if 'toolset' in target and 'toolsets' not in target:
        new_target_list.append(target)
        continue
      if multiple_toolsets:
        toolsets = target.get('toolsets', ['target'])
      else:
        toolsets = ['target']
      # Make sure this 'toolsets' definition is only processed once.
      if 'toolsets' in target:
        del target['toolsets']
      if len(toolsets) > 0:
        # Optimization: only do copies if more than one toolset is specified.
        for build in toolsets[1:]:
          new_target = copy.deepcopy(target)
          new_target['toolset'] = build
          new_target_list.append(new_target)
        target['toolset'] = toolsets[0]
        new_target_list.append(target)
    data['targets'] = new_target_list
  if 'conditions' in data:
    for condition in data['conditions']:
      if isinstance(condition, list):
        for condition_dict in condition[1:]:
          ProcessToolsetsInDict(condition_dict)


# TODO(mark): I don't love this name.  It just means that it's going to load
# a build file that contains targets and is expected to provide a targets dict
# that contains the targets...
def LoadTargetBuildFile(build_file_path, data, aux_data, variables, includes,
                        depth, check, load_dependencies):
  # If depth is set, predefine the DEPTH variable to be a relative path from
  # this build file's directory to the directory identified by depth.
  if depth:
    # TODO(dglazkov) The backslash/forward-slash replacement at the end is a
    # temporary measure. This should really be addressed by keeping all paths
    # in POSIX until actual project generation.
    d = gyp.common.RelativePath(depth, os.path.dirname(build_file_path))
    if d == '':
      variables['DEPTH'] = '.'
    else:
      variables['DEPTH'] = d.replace('\\', '/')

  # If the generator needs absolue paths, then do so.
  if absolute_build_file_paths:
    build_file_path = os.path.abspath(build_file_path)

  if build_file_path in data['target_build_files']:
    # Already loaded.
    return False
  data['target_build_files'].add(build_file_path)

  gyp.DebugOutput(gyp.DEBUG_INCLUDES,
                  "Loading Target Build File '%s'" % build_file_path)

  build_file_data = LoadOneBuildFile(build_file_path, data, aux_data, variables,
                                     includes, True, check)

  # Store DEPTH for later use in generators.
  build_file_data['_DEPTH'] = depth

  # Set up the included_files key indicating which .gyp files contributed to
  # this target dict.
  if 'included_files' in build_file_data:
    raise GypError(build_file_path + ' must not contain included_files key')

  included = GetIncludedBuildFiles(build_file_path, aux_data)
  build_file_data['included_files'] = []
  for included_file in included:
    # included_file is relative to the current directory, but it needs to
    # be made relative to build_file_path's directory.
    included_relative = \
        gyp.common.RelativePath(included_file,
                                os.path.dirname(build_file_path))
    build_file_data['included_files'].append(included_relative)

  # Do a first round of toolsets expansion so that conditions can be defined
  # per toolset.
  ProcessToolsetsInDict(build_file_data)

  # Apply "pre"/"early" variable expansions and condition evaluations.
  ProcessVariablesAndConditionsInDict(
      build_file_data, PHASE_EARLY, variables, build_file_path)

  # Since some toolsets might have been defined conditionally, perform
  # a second round of toolsets expansion now.
  ProcessToolsetsInDict(build_file_data)

  # Look at each project's target_defaults dict, and merge settings into
  # targets.
  if 'target_defaults' in build_file_data:
    if 'targets' not in build_file_data:
      raise GypError("Unable to find targets in build file %s" %
                     build_file_path)

    index = 0
    while index < len(build_file_data['targets']):
      # This procedure needs to give the impression that target_defaults is
      # used as defaults, and the individual targets inherit from that.
      # The individual targets need to be merged into the defaults.  Make
      # a deep copy of the defaults for each target, merge the target dict
      # as found in the input file into that copy, and then hook up the
      # copy with the target-specific data merged into it as the replacement
      # target dict.
      old_target_dict = build_file_data['targets'][index]
      new_target_dict = copy.deepcopy(build_file_data['target_defaults'])
      MergeDicts(new_target_dict, old_target_dict,
                 build_file_path, build_file_path)
      build_file_data['targets'][index] = new_target_dict
      index += 1

    # No longer needed.
    del build_file_data['target_defaults']

  # Look for dependencies.  This means that dependency resolution occurs
  # after "pre" conditionals and variable expansion, but before "post" -
  # in other words, you can't put a "dependencies" section inside a "post"
  # conditional within a target.

  dependencies = []
  if 'targets' in build_file_data:
    for target_dict in build_file_data['targets']:
      if 'dependencies' not in target_dict:
        continue
      for dependency in target_dict['dependencies']:
        dependencies.append(
            gyp.common.ResolveTarget(build_file_path, dependency, None)[0])

  if load_dependencies:
    for dependency in dependencies:
      try:
        LoadTargetBuildFile(dependency, data, aux_data, variables,
                            includes, depth, check, load_dependencies)
      except Exception, e:
        gyp.common.ExceptionAppend(
          e, 'while loading dependencies of %s' % build_file_path)
        raise
  else:
    return (build_file_path, dependencies)


def CallLoadTargetBuildFile(global_flags,
                            build_file_path, data,
                            aux_data, variables,
                            includes, depth, check):
  """Wrapper around LoadTargetBuildFile for parallel processing.

     This wrapper is used when LoadTargetBuildFile is executed in
     a worker process.
  """

  try:
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    # Apply globals so that the worker process behaves the same.
    for key, value in global_flags.iteritems():
      globals()[key] = value

    # Save the keys so we can return data that changed.
    data_keys = set(data)
    aux_data_keys = set(aux_data)

    result = LoadTargetBuildFile(build_file_path, data,
                                 aux_data, variables,
                                 includes, depth, check, False)
    if not result:
      return result

    (build_file_path, dependencies) = result

    data_out = {}
    for key in data:
      if key == 'target_build_files':
        continue
      if key not in data_keys:
        data_out[key] = data[key]
    aux_data_out = {}
    for key in aux_data:
      if key not in aux_data_keys:
        aux_data_out[key] = aux_data[key]

    # This gets serialized and sent back to the main process via a pipe.
    # It's handled in LoadTargetBuildFileCallback.
    return (build_file_path,
            data_out,
            aux_data_out,
            dependencies)
  except Exception, e:
    print "Exception: ", e
    return None


class ParallelProcessingError(Exception):
  pass


class ParallelState(object):
  """Class to keep track of state when processing input files in parallel.

  If build files are loaded in parallel, use this to keep track of
  state during farming out and processing parallel jobs. It's stored
  in a global so that the callback function can have access to it.
  """

  def __init__(self):
    # The multiprocessing pool.
    self.pool = None
    # The condition variable used to protect this object and notify
    # the main loop when there might be more data to process.
    self.condition = None
    # The "data" dict that was passed to LoadTargetBuildFileParallel
    self.data = None
    # The "aux_data" dict that was passed to LoadTargetBuildFileParallel
    self.aux_data = None
    # The number of parallel calls outstanding; decremented when a response
    # was received.
    self.pending = 0
    # The set of all build files that have been scheduled, so we don't
    # schedule the same one twice.
    self.scheduled = set()
    # A list of dependency build file paths that haven't been scheduled yet.
    self.dependencies = []
    # Flag to indicate if there was an error in a child process.
    self.error = False

  def LoadTargetBuildFileCallback(self, result):
    """Handle the results of running LoadTargetBuildFile in another process.
    """
    self.condition.acquire()
    if not result:
      self.error = True
      self.condition.notify()
      self.condition.release()
      return
    (build_file_path0, data0, aux_data0, dependencies0) = result
    self.data['target_build_files'].add(build_file_path0)
    for key in data0:
      self.data[key] = data0[key]
    for key in aux_data0:
      self.aux_data[key] = aux_data0[key]
    for new_dependency in dependencies0:
      if new_dependency not in self.scheduled:
        self.scheduled.add(new_dependency)
        self.dependencies.append(new_dependency)
    self.pending -= 1
    self.condition.notify()
    self.condition.release()


def LoadTargetBuildFileParallel(build_file_path, data, aux_data,
                                variables, includes, depth, check):
  parallel_state = ParallelState()
  parallel_state.condition = threading.Condition()
  parallel_state.dependencies = [build_file_path]
  parallel_state.scheduled = set([build_file_path])
  parallel_state.pending = 0
  parallel_state.data = data
  parallel_state.aux_data = aux_data

  try:
    parallel_state.condition.acquire()
    while parallel_state.dependencies or parallel_state.pending:
      if parallel_state.error:
        break
      if not parallel_state.dependencies:
        parallel_state.condition.wait()
        continue

      dependency = parallel_state.dependencies.pop()

      parallel_state.pending += 1
      data_in = {}
      data_in['target_build_files'] = data['target_build_files']
      aux_data_in = {}
      global_flags = {
        'path_sections': globals()['path_sections'],
        'non_configuration_keys': globals()['non_configuration_keys'],
        'absolute_build_file_paths': globals()['absolute_build_file_paths'],
        'multiple_toolsets': globals()['multiple_toolsets']}

      if not parallel_state.pool:
        parallel_state.pool = multiprocessing.Pool(8)
      parallel_state.pool.apply_async(
          CallLoadTargetBuildFile,
          args = (global_flags, dependency,
                  data_in, aux_data_in,
                  variables, includes, depth, check),
          callback = parallel_state.LoadTargetBuildFileCallback)
  except KeyboardInterrupt, e:
    parallel_state.pool.terminate()
    raise e

  parallel_state.condition.release()
  if parallel_state.error:
    sys.exit()


# Look for the bracket that matches the first bracket seen in a
# string, and return the start and end as a tuple.  For example, if
# the input is something like "<(foo <(bar)) blah", then it would
# return (1, 13), indicating the entire string except for the leading
# "<" and trailing " blah".
def FindEnclosingBracketGroup(input):
  brackets = { '}': '{',
               ']': '[',
               ')': '(', }
  stack = []
  count = 0
  start = -1
  for char in input:
    if char in brackets.values():
      stack.append(char)
      if start == -1:
        start = count
    if char in brackets.keys():
      try:
        last_bracket = stack.pop()
      except IndexError:
        return (-1, -1)
      if last_bracket != brackets[char]:
        return (-1, -1)
      if len(stack) == 0:
        return (start, count + 1)
    count = count + 1
  return (-1, -1)


canonical_int_re = re.compile('^(0|-?[1-9][0-9]*)$')


def IsStrCanonicalInt(string):
  """Returns True if |string| is in its canonical integer form.

  The canonical form is such that str(int(string)) == string.
  """
  if not isinstance(string, str) or not canonical_int_re.match(string):
    return False

  return True


# This matches things like "<(asdf)", "<!(cmd)", "<!@(cmd)", "<|(list)",
# "<!interpreter(arguments)", "<([list])", and even "<([)" and "<(<())".
# In the last case, the inner "<()" is captured in match['content'].
early_variable_re = re.compile(
    '(?P<replace>(?P<type><(?:(?:!?@?)|\|)?)'
    '(?P<command_string>[-a-zA-Z0-9_.]+)?'
    '\((?P<is_array>\s*\[?)'
    '(?P<content>.*?)(\]?)\))')

# This matches the same as early_variable_re, but with '>' instead of '<'.
late_variable_re = re.compile(
    '(?P<replace>(?P<type>>(?:(?:!?@?)|\|)?)'
    '(?P<command_string>[-a-zA-Z0-9_.]+)?'
    '\((?P<is_array>\s*\[?)'
    '(?P<content>.*?)(\]?)\))')

# This matches the same as early_variable_re, but with '^' instead of '<'.
latelate_variable_re = re.compile(
    '(?P<replace>(?P<type>[\^](?:(?:!?@?)|\|)?)'
    '(?P<command_string>[-a-zA-Z0-9_.]+)?'
    '\((?P<is_array>\s*\[?)'
    '(?P<content>.*?)(\]?)\))')

# Global cache of results from running commands so they don't have to be run
# more then once.
cached_command_results = {}


def FixupPlatformCommand(cmd):
  if sys.platform == 'win32':
    if type(cmd) == list:
      cmd = [re.sub('^cat ', 'type ', cmd[0])] + cmd[1:]
    else:
      cmd = re.sub('^cat ', 'type ', cmd)
  return cmd


PHASE_EARLY = 0
PHASE_LATE = 1
PHASE_LATELATE = 2


def ExpandVariables(input, phase, variables, build_file):
  # Look for the pattern that gets expanded into variables
  if phase == PHASE_EARLY:
    variable_re = early_variable_re
    expansion_symbol = '<'
  elif phase == PHASE_LATE:
    variable_re = late_variable_re
    expansion_symbol = '>'
  elif phase == PHASE_LATELATE:
    variable_re = latelate_variable_re
    expansion_symbol = '^'
  else:
    assert False

  input_str = str(input)
  if IsStrCanonicalInt(input_str):
    return int(input_str)

  # Do a quick scan to determine if an expensive regex search is warranted.
  if expansion_symbol not in input_str:
    return input_str

  # Get the entire list of matches as a list of MatchObject instances.
  # (using findall here would return strings instead of MatchObjects).
  matches = [match for match in variable_re.finditer(input_str)]
  if not matches:
    return input_str

  output = input_str
  # Reverse the list of matches so that replacements are done right-to-left.
  # That ensures that earlier replacements won't mess up the string in a
  # way that causes later calls to find the earlier substituted text instead
  # of what's intended for replacement.
  matches.reverse()
  for match_group in matches:
    match = match_group.groupdict()
    gyp.DebugOutput(gyp.DEBUG_VARIABLES,
                    "Matches: %s" % repr(match))
    # match['replace'] is the substring to look for, match['type']
    # is the character code for the replacement type (< > <! >! <| >| <@
    # >@ <!@ >!@), match['is_array'] contains a '[' for command
    # arrays, and match['content'] is the name of the variable (< >)
    # or command to run (<! >!). match['command_string'] is an optional
    # command string. Currently, only 'pymod_do_main' is supported.

    # run_command is true if a ! variant is used.
    run_command = '!' in match['type']
    command_string = match['command_string']

    # file_list is true if a | variant is used.
    file_list = '|' in match['type']

    # Capture these now so we can adjust them later.
    replace_start = match_group.start('replace')
    replace_end = match_group.end('replace')

    # Find the ending paren, and re-evaluate the contained string.
    (c_start, c_end) = FindEnclosingBracketGroup(input_str[replace_start:])

    # Adjust the replacement range to match the entire command
    # found by FindEnclosingBracketGroup (since the variable_re
    # probably doesn't match the entire command if it contained
    # nested variables).
    replace_end = replace_start + c_end

    # Find the "real" replacement, matching the appropriate closing
    # paren, and adjust the replacement start and end.
    replacement = input_str[replace_start:replace_end]

    # Figure out what the contents of the variable parens are.
    contents_start = replace_start + c_start + 1
    contents_end = replace_end - 1
    contents = input_str[contents_start:contents_end]

    # Do filter substitution now for <|().
    # Admittedly, this is different than the evaluation order in other
    # contexts. However, since filtration has no chance to run on <|(),
    # this seems like the only obvious way to give them access to filters.
    if file_list:
      processed_variables = copy.deepcopy(variables)
      ProcessListFiltersInDict(contents, processed_variables)
      # Recurse to expand variables in the contents
      contents = ExpandVariables(contents, phase,
                                 processed_variables, build_file)
    else:
      # Recurse to expand variables in the contents
      contents = ExpandVariables(contents, phase, variables, build_file)

    # Strip off leading/trailing whitespace so that variable matches are
    # simpler below (and because they are rarely needed).
    contents = contents.strip()

    # expand_to_list is true if an @ variant is used.  In that case,
    # the expansion should result in a list.  Note that the caller
    # is to be expecting a list in return, and not all callers do
    # because not all are working in list context.  Also, for list
    # expansions, there can be no other text besides the variable
    # expansion in the input string.
    expand_to_list = '@' in match['type'] and input_str == replacement

    if run_command or file_list:
      # Find the build file's directory, so commands can be run or file lists
      # generated relative to it.
      build_file_dir = os.path.dirname(build_file)
      if build_file_dir == '':
        # If build_file is just a leaf filename indicating a file in the
        # current directory, build_file_dir might be an empty string.  Set
        # it to None to signal to subprocess.Popen that it should run the
        # command in the current directory.
        build_file_dir = None

    # Support <|(listfile.txt ...) which generates a file
    # containing items from a gyp list, generated at gyp time.
    # This works around actions/rules which have more inputs than will
    # fit on the command line.
    if file_list:
      if type(contents) == list:
        contents_list = contents
      else:
        contents_list = contents.split(' ')
      replacement = contents_list[0]
      path = replacement
      if not os.path.isabs(path):
        path = os.path.join(build_file_dir, path)
      f = gyp.common.WriteOnDiff(path)
      for i in contents_list[1:]:
        f.write('%s\n' % i)
      f.close()

    elif run_command:
      use_shell = True
      if match['is_array']:
        contents = eval(contents)
        use_shell = False

      # Check for a cached value to avoid executing commands, or generating
      # file lists more than once.
      # TODO(http://code.google.com/p/gyp/issues/detail?id=112): It is
      # possible that the command being invoked depends on the current
      # directory. For that case the syntax needs to be extended so that the
      # directory is also used in cache_key (it becomes a tuple).
      # TODO(http://code.google.com/p/gyp/issues/detail?id=111): In theory,
      # someone could author a set of GYP files where each time the command
      # is invoked it produces different output by design. When the need
      # arises, the syntax should be extended to support no caching off a
      # command's output so it is run every time.
      cache_key = str(contents)
      cached_value = cached_command_results.get(cache_key, None)
      if cached_value is None:
        gyp.DebugOutput(gyp.DEBUG_VARIABLES,
                        "Executing command '%s' in directory '%s'" %
                        (contents,build_file_dir))

        replacement = ''

        if command_string == 'pymod_do_main':
          # <!pymod_do_main(modulename param eters) loads |modulename| as a
          # python module and then calls that module's DoMain() function,
          # passing ["param", "eters"] as a single list argument. For modules
          # that don't load quickly, this can be faster than
          # <!(python modulename param eters). Do this in |build_file_dir|.
          oldwd = os.getcwd()  # Python doesn't like os.open('.'): no fchdir.
          if not build_file_dir is None:
            os.chdir(build_file_dir)

          parsed_contents = shlex.split(contents)
          py_module = __import__(parsed_contents[0])
          replacement = str(py_module.DoMain(parsed_contents[1:])).rstrip()

          os.chdir(oldwd)
          assert replacement != None
        elif command_string:
          raise GypError("Unknown command string '%s' in '%s'." %
                         (command_string, contents))
        else:
          # Fix up command with platform specific workarounds.
          contents = FixupPlatformCommand(contents)
          p = subprocess.Popen(contents, shell=use_shell,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               stdin=subprocess.PIPE,
                               cwd=build_file_dir)

          p_stdout, p_stderr = p.communicate('')

          if p.wait() != 0 or p_stderr:
            sys.stderr.write(p_stderr)
            # Simulate check_call behavior, since check_call only exists
            # in python 2.5 and later.
            raise GypError("Call to '%s' returned exit status %d." %
                           (contents, p.returncode))
          replacement = p_stdout.rstrip()

        cached_command_results[cache_key] = replacement
      else:
        gyp.DebugOutput(gyp.DEBUG_VARIABLES,
                        "Had cache value for command '%s' in directory '%s'" %
                        (contents,build_file_dir))
        replacement = cached_value

    else:
      if not contents in variables:
        if contents[-1] in ['!', '/']:
          # In order to allow cross-compiles (nacl) to happen more naturally,
          # we will allow references to >(sources/) etc. to resolve to
          # and empty list if undefined. This allows actions to:
          # 'action!': [
          #   '>@(_sources!)',
          # ],
          # 'action/': [
          #   '>@(_sources/)',
          # ],
          replacement = []
        else:
          raise GypError('Undefined variable ' + contents +
                         ' in ' + build_file)
      else:
        replacement = variables[contents]

    if isinstance(replacement, list):
      for item in replacement:
        if (not contents[-1] == '/' and
            not isinstance(item, str) and not isinstance(item, int)):
          raise GypError('Variable ' + contents +
                         ' must expand to a string or list of strings; ' +
                         'list contains a ' +
                         item.__class__.__name__)
      # Run through the list and handle variable expansions in it.  Since
      # the list is guaranteed not to contain dicts, this won't do anything
      # with conditions sections.
      ProcessVariablesAndConditionsInList(replacement, phase, variables,
                                          build_file)
    elif not isinstance(replacement, str) and \
         not isinstance(replacement, int):
          raise GypError('Variable ' + contents +
                         ' must expand to a string or list of strings; ' +
                         'found a ' + replacement.__class__.__name__)

    if expand_to_list:
      # Expanding in list context.  It's guaranteed that there's only one
      # replacement to do in |input_str| and that it's this replacement.  See
      # above.
      if isinstance(replacement, list):
        # If it's already a list, make a copy.
        output = replacement[:]
      else:
        # Split it the same way sh would split arguments.
        output = shlex.split(str(replacement))
    else:
      # Expanding in string context.
      encoded_replacement = ''
      if isinstance(replacement, list):
        # When expanding a list into string context, turn the list items
        # into a string in a way that will work with a subprocess call.
        #
        # TODO(mark): This isn't completely correct.  This should
        # call a generator-provided function that observes the
        # proper list-to-argument quoting rules on a specific
        # platform instead of just calling the POSIX encoding
        # routine.
        encoded_replacement = gyp.common.EncodePOSIXShellList(replacement)
      else:
        encoded_replacement = replacement

      output = output[:replace_start] + str(encoded_replacement) + \
               output[replace_end:]
    # Prepare for the next match iteration.
    input_str = output

  # Look for more matches now that we've replaced some, to deal with
  # expanding local variables (variables defined in the same
  # variables block as this one).
  gyp.DebugOutput(gyp.DEBUG_VARIABLES,
                  "Found output %s, recursing." % repr(output))
  if isinstance(output, list):
    if output and isinstance(output[0], list):
      # Leave output alone if it's a list of lists.
      # We don't want such lists to be stringified.
      pass
    else:
      new_output = []
      for item in output:
        new_output.append(
            ExpandVariables(item, phase, variables, build_file))
      output = new_output
  else:
    output = ExpandVariables(output, phase, variables, build_file)

  # Convert all strings that are canonically-represented integers into integers.
  if isinstance(output, list):
    for index in xrange(0, len(output)):
      if IsStrCanonicalInt(output[index]):
        output[index] = int(output[index])
  elif IsStrCanonicalInt(output):
    output = int(output)

  return output


def ProcessConditionsInDict(the_dict, phase, variables, build_file):
  # Process a 'conditions' or 'target_conditions' section in the_dict,
  # depending on phase.
  # early -> conditions
  # late -> target_conditions
  # latelate -> no conditions
  #
  # Each item in a conditions list consists of cond_expr, a string expression
  # evaluated as the condition, and true_dict, a dict that will be merged into
  # the_dict if cond_expr evaluates to true.  Optionally, a third item,
  # false_dict, may be present.  false_dict is merged into the_dict if
  # cond_expr evaluates to false.
  #
  # Any dict merged into the_dict will be recursively processed for nested
  # conditionals and other expansions, also according to phase, immediately
  # prior to being merged.

  if phase == PHASE_EARLY:
    conditions_key = 'conditions'
  elif phase == PHASE_LATE:
    conditions_key = 'target_conditions'
  elif phase == PHASE_LATELATE:
    return
  else:
    assert False

  if not conditions_key in the_dict:
    return

  conditions_list = the_dict[conditions_key]
  # Unhook the conditions list, it's no longer needed.
  del the_dict[conditions_key]

  for condition in conditions_list:
    if not isinstance(condition, list):
      raise GypError(conditions_key + ' must be a list')
    if len(condition) != 2 and len(condition) != 3:
      # It's possible that condition[0] won't work in which case this
      # attempt will raise its own IndexError.  That's probably fine.
      raise GypError(conditions_key + ' ' + condition[0] +
                     ' must be length 2 or 3, not ' + str(len(condition)))

    [cond_expr, true_dict] = condition[0:2]
    false_dict = None
    if len(condition) == 3:
      false_dict = condition[2]

    # Do expansions on the condition itself.  Since the conditon can naturally
    # contain variable references without needing to resort to GYP expansion
    # syntax, this is of dubious value for variables, but someone might want to
    # use a command expansion directly inside a condition.
    cond_expr_expanded = ExpandVariables(cond_expr, phase, variables,
                                         build_file)
    if not isinstance(cond_expr_expanded, str) and \
       not isinstance(cond_expr_expanded, int):
      raise ValueError, \
            'Variable expansion in this context permits str and int ' + \
            'only, found ' + expanded.__class__.__name__

    try:
      ast_code = compile(cond_expr_expanded, '<string>', 'eval')

      if eval(ast_code, {'__builtins__': None}, variables):
        merge_dict = true_dict
      else:
        merge_dict = false_dict
    except SyntaxError, e:
      syntax_error = SyntaxError('%s while evaluating condition \'%s\' in %s '
                                 'at character %d.' %
                                 (str(e.args[0]), e.text, build_file, e.offset),
                                 e.filename, e.lineno, e.offset, e.text)
      raise syntax_error
    except NameError, e:
      gyp.common.ExceptionAppend(e, 'while evaluating condition \'%s\' in %s' %
                                 (cond_expr_expanded, build_file))
      raise

    if merge_dict != None:
      # Expand variables and nested conditinals in the merge_dict before
      # merging it.
      ProcessVariablesAndConditionsInDict(merge_dict, phase,
                                          variables, build_file)

      MergeDicts(the_dict, merge_dict, build_file, build_file)


def LoadAutomaticVariablesFromDict(variables, the_dict):
  # Any keys with plain string values in the_dict become automatic variables.
  # The variable name is the key name with a "_" character prepended.
  for key, value in the_dict.iteritems():
    if isinstance(value, str) or isinstance(value, int) or \
       isinstance(value, list):
      variables['_' + key] = value


def LoadVariablesFromVariablesDict(variables, the_dict, the_dict_key):
  # Any keys in the_dict's "variables" dict, if it has one, becomes a
  # variable.  The variable name is the key name in the "variables" dict.
  # Variables that end with the % character are set only if they are unset in
  # the variables dict.  the_dict_key is the name of the key that accesses
  # the_dict in the_dict's parent dict.  If the_dict's parent is not a dict
  # (it could be a list or it could be parentless because it is a root dict),
  # the_dict_key will be None.
  for key, value in the_dict.get('variables', {}).iteritems():
    if not isinstance(value, str) and not isinstance(value, int) and \
       not isinstance(value, list):
      continue

    if key.endswith('%'):
      variable_name = key[:-1]
      if variable_name in variables:
        # If the variable is already set, don't set it.
        continue
      if the_dict_key is 'variables' and variable_name in the_dict:
        # If the variable is set without a % in the_dict, and the_dict is a
        # variables dict (making |variables| a varaibles sub-dict of a
        # variables dict), use the_dict's definition.
        value = the_dict[variable_name]
    else:
      variable_name = key

    variables[variable_name] = value


def ProcessVariablesAndConditionsInDict(the_dict, phase, variables_in,
                                        build_file, the_dict_key=None):
  """Handle all variable and command expansion and conditional evaluation.

  This function is the public entry point for all variable expansions and
  conditional evaluations.  The variables_in dictionary will not be modified
  by this function.
  """

  # Make a copy of the variables_in dict that can be modified during the
  # loading of automatics and the loading of the variables dict.
  variables = variables_in.copy()
  LoadAutomaticVariablesFromDict(variables, the_dict)

  if 'variables' in the_dict:
    # Make sure all the local variables are added to the variables
    # list before we process them so that you can reference one
    # variable from another.  They will be fully expanded by recursion
    # in ExpandVariables.
    for key, value in the_dict['variables'].iteritems():
      variables[key] = value

    # Handle the associated variables dict first, so that any variable
    # references within can be resolved prior to using them as variables.
    # Pass a copy of the variables dict to avoid having it be tainted.
    # Otherwise, it would have extra automatics added for everything that
    # should just be an ordinary variable in this scope.
    ProcessVariablesAndConditionsInDict(the_dict['variables'], phase,
                                        variables, build_file, 'variables')

  LoadVariablesFromVariablesDict(variables, the_dict, the_dict_key)

  for key, value in the_dict.iteritems():
    # Skip "variables", which was already processed if present.
    if key != 'variables' and isinstance(value, str):
      expanded = ExpandVariables(value, phase, variables, build_file)
      if not isinstance(expanded, str) and not isinstance(expanded, int):
        raise ValueError, \
              'Variable expansion in this context permits str and int ' + \
              'only, found ' + expanded.__class__.__name__ + ' for ' + key
      the_dict[key] = expanded

  # Variable expansion may have resulted in changes to automatics.  Reload.
  # TODO(mark): Optimization: only reload if no changes were made.
  variables = variables_in.copy()
  LoadAutomaticVariablesFromDict(variables, the_dict)
  LoadVariablesFromVariablesDict(variables, the_dict, the_dict_key)

  # Process conditions in this dict.  This is done after variable expansion
  # so that conditions may take advantage of expanded variables.  For example,
  # if the_dict contains:
  #   {'type':       '<(library_type)',
  #    'conditions': [['_type=="static_library"', { ... }]]},
  # _type, as used in the condition, will only be set to the value of
  # library_type if variable expansion is performed before condition
  # processing.  However, condition processing should occur prior to recursion
  # so that variables (both automatic and "variables" dict type) may be
  # adjusted by conditions sections, merged into the_dict, and have the
  # intended impact on contained dicts.
  #
  # This arrangement means that a "conditions" section containing a "variables"
  # section will only have those variables effective in subdicts, not in
  # the_dict.  The workaround is to put a "conditions" section within a
  # "variables" section.  For example:
  #   {'conditions': [['os=="mac"', {'variables': {'define': 'IS_MAC'}}]],
  #    'defines':    ['<(define)'],
  #    'my_subdict': {'defines': ['<(define)']}},
  # will not result in "IS_MAC" being appended to the "defines" list in the
  # current scope but would result in it being appended to the "defines" list
  # within "my_subdict".  By comparison:
  #   {'variables': {'conditions': [['os=="mac"', {'define': 'IS_MAC'}]]},
  #    'defines':    ['<(define)'],
  #    'my_subdict': {'defines': ['<(define)']}},
  # will append "IS_MAC" to both "defines" lists.

  # Evaluate conditions sections, allowing variable expansions within them
  # as well as nested conditionals.  This will process a 'conditions' or
  # 'target_conditions' section, perform appropriate merging and recursive
  # conditional and variable processing, and then remove the conditions section
  # from the_dict if it is present.
  ProcessConditionsInDict(the_dict, phase, variables, build_file)

  # Conditional processing may have resulted in changes to automatics or the
  # variables dict.  Reload.
  variables = variables_in.copy()
  LoadAutomaticVariablesFromDict(variables, the_dict)
  LoadVariablesFromVariablesDict(variables, the_dict, the_dict_key)

  # Recurse into child dicts, or process child lists which may result in
  # further recursion into descendant dicts.
  for key, value in the_dict.iteritems():
    # Skip "variables" and string values, which were already processed if
    # present.
    if key == 'variables' or isinstance(value, str):
      continue
    if isinstance(value, dict):
      # Pass a copy of the variables dict so that subdicts can't influence
      # parents.
      ProcessVariablesAndConditionsInDict(value, phase, variables,
                                          build_file, key)
    elif isinstance(value, list):
      # The list itself can't influence the variables dict, and
      # ProcessVariablesAndConditionsInList will make copies of the variables
      # dict if it needs to pass it to something that can influence it.  No
      # copy is necessary here.
      ProcessVariablesAndConditionsInList(value, phase, variables,
                                          build_file)
    elif not isinstance(value, int):
      raise TypeError, 'Unknown type ' + value.__class__.__name__ + \
                       ' for ' + key


def ProcessVariablesAndConditionsInList(the_list, phase, variables,
                                        build_file):
  # Iterate using an index so that new values can be assigned into the_list.
  index = 0
  while index < len(the_list):
    item = the_list[index]
    if isinstance(item, dict):
      # Make a copy of the variables dict so that it won't influence anything
      # outside of its own scope.
      ProcessVariablesAndConditionsInDict(item, phase, variables, build_file)
    elif isinstance(item, list):
      ProcessVariablesAndConditionsInList(item, phase, variables, build_file)
    elif isinstance(item, str):
      expanded = ExpandVariables(item, phase, variables, build_file)
      if isinstance(expanded, str) or isinstance(expanded, int):
        the_list[index] = expanded
      elif isinstance(expanded, list):
        the_list[index:index+1] = expanded
        index += len(expanded)

        # index now identifies the next item to examine.  Continue right now
        # without falling into the index increment below.
        continue
      else:
        raise ValueError, \
              'Variable expansion in this context permits strings and ' + \
              'lists only, found ' + expanded.__class__.__name__ + ' at ' + \
              index
    elif not isinstance(item, int):
      raise TypeError, 'Unknown type ' + item.__class__.__name__ + \
                       ' at index ' + index
    index = index + 1


def BuildTargetsDict(data):
  """Builds a dict mapping fully-qualified target names to their target dicts.

  |data| is a dict mapping loaded build files by pathname relative to the
  current directory.  Values in |data| are build file contents.  For each
  |data| value with a "targets" key, the value of the "targets" key is taken
  as a list containing target dicts.  Each target's fully-qualified name is
  constructed from the pathname of the build file (|data| key) and its
  "target_name" property.  These fully-qualified names are used as the keys
  in the returned dict.  These keys provide access to the target dicts,
  the dicts in the "targets" lists.
  """

  targets = {}
  for build_file in data['target_build_files']:
    for target in data[build_file].get('targets', []):
      target_name = gyp.common.QualifiedTarget(build_file,
                                               target['target_name'],
                                               target['toolset'])
      if target_name in targets:
        raise GypError('Duplicate target definitions for ' + target_name)
      targets[target_name] = target

  return targets


def QualifyDependencies(targets):
  """Make dependency links fully-qualified relative to the current directory.

  |targets| is a dict mapping fully-qualified target names to their target
  dicts.  For each target in this dict, keys known to contain dependency
  links are examined, and any dependencies referenced will be rewritten
  so that they are fully-qualified and relative to the current directory.
  All rewritten dependencies are suitable for use as keys to |targets| or a
  similar dict.
  """

  all_dependency_sections = [dep + op
                             for dep in dependency_sections
                             for op in ('', '!', '/')]

  for target, target_dict in targets.iteritems():
    target_build_file = gyp.common.BuildFile(target)
    toolset = target_dict['toolset']
    for dependency_key in all_dependency_sections:
      dependencies = target_dict.get(dependency_key, [])
      for index in xrange(0, len(dependencies)):
        dep_file, dep_target, dep_toolset = gyp.common.ResolveTarget(
            target_build_file, dependencies[index], toolset)
        if not multiple_toolsets:
          # Ignore toolset specification in the dependency if it is specified.
          dep_toolset = toolset
        dependency = gyp.common.QualifiedTarget(dep_file,
                                                dep_target,
                                                dep_toolset)
        dependencies[index] = dependency

        # Make sure anything appearing in a list other than "dependencies" also
        # appears in the "dependencies" list.
        if dependency_key != 'dependencies' and \
           dependency not in target_dict['dependencies']:
          raise GypError('Found ' + dependency + ' in ' + dependency_key +
                         ' of ' + target + ', but not in dependencies')


def ExpandWildcardDependencies(targets, data):
  """Expands dependencies specified as build_file:*.

  For each target in |targets|, examines sections containing links to other
  targets.  If any such section contains a link of the form build_file:*, it
  is taken as a wildcard link, and is expanded to list each target in
  build_file.  The |data| dict provides access to build file dicts.

  Any target that does not wish to be included by wildcard can provide an
  optional "suppress_wildcard" key in its target dict.  When present and
  true, a wildcard dependency link will not include such targets.

  All dependency names, including the keys to |targets| and the values in each
  dependency list, must be qualified when this function is called.
  """

  for target, target_dict in targets.iteritems():
    toolset = target_dict['toolset']
    target_build_file = gyp.common.BuildFile(target)
    for dependency_key in dependency_sections:
      dependencies = target_dict.get(dependency_key, [])

      # Loop this way instead of "for dependency in" or "for index in xrange"
      # because the dependencies list will be modified within the loop body.
      index = 0
      while index < len(dependencies):
        (dependency_build_file, dependency_target, dependency_toolset) = \
            gyp.common.ParseQualifiedTarget(dependencies[index])
        if dependency_target != '*' and dependency_toolset != '*':
          # Not a wildcard.  Keep it moving.
          index = index + 1
          continue

        if dependency_build_file == target_build_file:
          # It's an error for a target to depend on all other targets in
          # the same file, because a target cannot depend on itself.
          raise GypError('Found wildcard in ' + dependency_key + ' of ' +
                         target + ' referring to same build file')

        # Take the wildcard out and adjust the index so that the next
        # dependency in the list will be processed the next time through the
        # loop.
        del dependencies[index]
        index = index - 1

        # Loop through the targets in the other build file, adding them to
        # this target's list of dependencies in place of the removed
        # wildcard.
        dependency_target_dicts = data[dependency_build_file]['targets']
        for dependency_target_dict in dependency_target_dicts:
          if int(dependency_target_dict.get('suppress_wildcard', False)):
            continue
          dependency_target_name = dependency_target_dict['target_name']
          if (dependency_target != '*' and
              dependency_target != dependency_target_name):
            continue
          dependency_target_toolset = dependency_target_dict['toolset']
          if (dependency_toolset != '*' and
              dependency_toolset != dependency_target_toolset):
            continue
          dependency = gyp.common.QualifiedTarget(dependency_build_file,
                                                  dependency_target_name,
                                                  dependency_target_toolset)
          index = index + 1
          dependencies.insert(index, dependency)

        index = index + 1


def Unify(l):
  """Removes duplicate elements from l, keeping the first element."""
  seen = {}
  return [seen.setdefault(e, e) for e in l if e not in seen]


def RemoveDuplicateDependencies(targets):
  """Makes sure every dependency appears only once in all targets's dependency
  lists."""
  for target_name, target_dict in targets.iteritems():
    for dependency_key in dependency_sections:
      dependencies = target_dict.get(dependency_key, [])
      if dependencies:
        target_dict[dependency_key] = Unify(dependencies)


class DependencyGraphNode(object):
  """

  Attributes:
    ref: A reference to an object that this DependencyGraphNode represents.
    dependencies: List of DependencyGraphNodes on which this one depends.
    dependents: List of DependencyGraphNodes that depend on this one.
  """

  class CircularException(GypError):
    pass

  def __init__(self, ref):
    self.ref = ref
    self.dependencies = []
    self.dependents = []

  def FlattenToList(self):
    # flat_list is the sorted list of dependencies - actually, the list items
    # are the "ref" attributes of DependencyGraphNodes.  Every target will
    # appear in flat_list after all of its dependencies, and before all of its
    # dependents.
    flat_list = []

    # in_degree_zeros is the list of DependencyGraphNodes that have no
    # dependencies not in flat_list.  Initially, it is a copy of the children
    # of this node, because when the graph was built, nodes with no
    # dependencies were made implicit dependents of the root node.
    in_degree_zeros = set(self.dependents[:])

    while in_degree_zeros:
      # Nodes in in_degree_zeros have no dependencies not in flat_list, so they
      # can be appended to flat_list.  Take these nodes out of in_degree_zeros
      # as work progresses, so that the next node to process from the list can
      # always be accessed at a consistent position.
      node = in_degree_zeros.pop()
      flat_list.append(node.ref)

      # Look at dependents of the node just added to flat_list.  Some of them
      # may now belong in in_degree_zeros.
      for node_dependent in node.dependents:
        is_in_degree_zero = True
        for node_dependent_dependency in node_dependent.dependencies:
          if not node_dependent_dependency.ref in flat_list:
            # The dependent one or more dependencies not in flat_list.  There
            # will be more chances to add it to flat_list when examining
            # it again as a dependent of those other dependencies, provided
            # that there are no cycles.
            is_in_degree_zero = False
            break

        if is_in_degree_zero:
          # All of the dependent's dependencies are already in flat_list.  Add
          # it to in_degree_zeros where it will be processed in a future
          # iteration of the outer loop.
          in_degree_zeros.add(node_dependent)

    return flat_list

  def DirectDependencies(self, dependencies=None):
    """Returns a list of just direct dependencies."""
    if dependencies == None:
      dependencies = []

    for dependency in self.dependencies:
      # Check for None, corresponding to the root node.
      if dependency.ref != None and dependency.ref not in dependencies:
        dependencies.append(dependency.ref)

    return dependencies

  def _AddImportedDependencies(self, targets, dependencies=None):
    """Given a list of direct dependencies, adds indirect dependencies that
    other dependencies have declared to export their settings.

    This method does not operate on self.  Rather, it operates on the list
    of dependencies in the |dependencies| argument.  For each dependency in
    that list, if any declares that it exports the settings of one of its
    own dependencies, those dependencies whose settings are "passed through"
    are added to the list.  As new items are added to the list, they too will
    be processed, so it is possible to import settings through multiple levels
    of dependencies.

    This method is not terribly useful on its own, it depends on being
    "primed" with a list of direct dependencies such as one provided by
    DirectDependencies.  DirectAndImportedDependencies is intended to be the
    public entry point.
    """

    if dependencies == None:
      dependencies = []

    index = 0
    while index < len(dependencies):
      dependency = dependencies[index]
      dependency_dict = targets[dependency]
      # Add any dependencies whose settings should be imported to the list
      # if not already present.  Newly-added items will be checked for
      # their own imports when the list iteration reaches them.
      # Rather than simply appending new items, insert them after the
      # dependency that exported them.  This is done to more closely match
      # the depth-first method used by DeepDependencies.
      add_index = 1
      for imported_dependency in \
          dependency_dict.get('export_dependent_settings', []):
        if imported_dependency not in dependencies:
          dependencies.insert(index + add_index, imported_dependency)
          add_index = add_index + 1
      index = index + 1

    return dependencies

  def DirectAndImportedDependencies(self, targets, dependencies=None):
    """Returns a list of a target's direct dependencies and all indirect
    dependencies that a dependency has advertised settings should be exported
    through the dependency for.
    """

    dependencies = self.DirectDependencies(dependencies)
    return self._AddImportedDependencies(targets, dependencies)

  def DeepDependencies(self, dependencies=None):
    """Returns a list of all of a target's dependencies, recursively."""
    if dependencies == None:
      dependencies = []

    for dependency in self.dependencies:
      # Check for None, corresponding to the root node.
      if dependency.ref != None and dependency.ref not in dependencies:
        dependencies.append(dependency.ref)
        dependency.DeepDependencies(dependencies)

    return dependencies

  def LinkDependencies(self, targets, dependencies=None, initial=True):
    """Returns a list of dependency targets that are linked into this target.

    This function has a split personality, depending on the setting of
    |initial|.  Outside callers should always leave |initial| at its default
    setting.

    When adding a target to the list of dependencies, this function will
    recurse into itself with |initial| set to False, to collect dependencies
    that are linked into the linkable target for which the list is being built.
    """
    if dependencies == None:
      dependencies = []

    # Check for None, corresponding to the root node.
    if self.ref == None:
      return dependencies

    # It's kind of sucky that |targets| has to be passed into this function,
    # but that's presently the easiest way to access the target dicts so that
    # this function can find target types.

    if 'target_name' not in targets[self.ref]:
      raise GypError("Missing 'target_name' field in target.")

    if 'type' not in targets[self.ref]:
      raise GypError("Missing 'type' field in target %s" %
                     targets[self.ref]['target_name'])

    target_type = targets[self.ref]['type']

    is_linkable = target_type in linkable_types

    if initial and not is_linkable:
      # If this is the first target being examined and it's not linkable,
      # return an empty list of link dependencies, because the link
      # dependencies are intended to apply to the target itself (initial is
      # True) and this target won't be linked.
      return dependencies

    # Don't traverse 'none' targets if explicitly excluded.
    if (target_type == 'none' and
        not targets[self.ref].get('dependencies_traverse', True)):
      if self.ref not in dependencies:
        dependencies.append(self.ref)
      return dependencies

    # Executables and loadable modules are already fully and finally linked.
    # Nothing else can be a link dependency of them, there can only be
    # dependencies in the sense that a dependent target might run an
    # executable or load the loadable_module.
    if not initial and target_type in ('executable', 'loadable_module'):
      return dependencies

    # The target is linkable, add it to the list of link dependencies.
    if self.ref not in dependencies:
      dependencies.append(self.ref)
      if initial or not is_linkable:
        # If this is a subsequent target and it's linkable, don't look any
        # further for linkable dependencies, as they'll already be linked into
        # this target linkable.  Always look at dependencies of the initial
        # target, and always look at dependencies of non-linkables.
        for dependency in self.dependencies:
          dependency.LinkDependencies(targets, dependencies, False)

    return dependencies


def BuildDependencyList(targets):
  # Create a DependencyGraphNode for each target.  Put it into a dict for easy
  # access.
  dependency_nodes = {}
  for target, spec in targets.iteritems():
    if target not in dependency_nodes:
      dependency_nodes[target] = DependencyGraphNode(target)

  # Set up the dependency links.  Targets that have no dependencies are treated
  # as dependent on root_node.
  root_node = DependencyGraphNode(None)
  for target, spec in targets.iteritems():
    target_node = dependency_nodes[target]
    target_build_file = gyp.common.BuildFile(target)
    dependencies = spec.get('dependencies')
    if not dependencies:
      target_node.dependencies = [root_node]
      root_node.dependents.append(target_node)
    else:
      for dependency in dependencies:
        dependency_node = dependency_nodes.get(dependency)
        if not dependency_node:
          raise GypError("Dependency '%s' not found while "
                         "trying to load target %s" % (dependency, target))
        target_node.dependencies.append(dependency_node)
        dependency_node.dependents.append(target_node)

  flat_list = root_node.FlattenToList()

  # If there's anything left unvisited, there must be a circular dependency
  # (cycle).  If you need to figure out what's wrong, look for elements of
  # targets that are not in flat_list.
  if len(flat_list) != len(targets):
    raise DependencyGraphNode.CircularException(
        'Some targets not reachable, cycle in dependency graph detected: ' +
        ' '.join(set(flat_list) ^ set(targets)))

  return [dependency_nodes, flat_list]


def VerifyNoGYPFileCircularDependencies(targets):
  # Create a DependencyGraphNode for each gyp file containing a target.  Put
  # it into a dict for easy access.
  dependency_nodes = {}
  for target in targets.iterkeys():
    build_file = gyp.common.BuildFile(target)
    if not build_file in dependency_nodes:
      dependency_nodes[build_file] = DependencyGraphNode(build_file)

  # Set up the dependency links.
  for target, spec in targets.iteritems():
    build_file = gyp.common.BuildFile(target)
    build_file_node = dependency_nodes[build_file]
    target_dependencies = spec.get('dependencies', [])
    for dependency in target_dependencies:
      try:
        dependency_build_file = gyp.common.BuildFile(dependency)
      except GypError, e:
        gyp.common.ExceptionAppend(
            e, 'while computing dependencies of .gyp file %s' % build_file)
        raise

      if dependency_build_file == build_file:
        # A .gyp file is allowed to refer back to itself.
        continue
      dependency_node = dependency_nodes.get(dependency_build_file)
      if not dependency_node:
        raise GypError("Dependancy '%s' not found" % dependency_build_file)
      if dependency_node not in build_file_node.dependencies:
        build_file_node.dependencies.append(dependency_node)
        dependency_node.dependents.append(build_file_node)


  # Files that have no dependencies are treated as dependent on root_node.
  root_node = DependencyGraphNode(None)
  for build_file_node in dependency_nodes.itervalues():
    if len(build_file_node.dependencies) == 0:
      build_file_node.dependencies.append(root_node)
      root_node.dependents.append(build_file_node)

  flat_list = root_node.FlattenToList()

  # If there's anything left unvisited, there must be a circular dependency
  # (cycle).
  if len(flat_list) != len(dependency_nodes):
    bad_files = []
    for file in dependency_nodes.iterkeys():
      if not file in flat_list:
        bad_files.append(file)
    raise DependencyGraphNode.CircularException, \
        'Some files not reachable, cycle in .gyp file dependency graph ' + \
        'detected involving some or all of: ' + \
        ' '.join(bad_files)


def DoDependentSettings(key, flat_list, targets, dependency_nodes):
  # key should be one of all_dependent_settings, direct_dependent_settings,
  # or link_settings.

  for target in flat_list:
    target_dict = targets[target]
    build_file = gyp.common.BuildFile(target)

    if key == 'all_dependent_settings':
      dependencies = dependency_nodes[target].DeepDependencies()
    elif key == 'direct_dependent_settings':
      dependencies = \
          dependency_nodes[target].DirectAndImportedDependencies(targets)
    elif key == 'link_settings':
      dependencies = dependency_nodes[target].LinkDependencies(targets)
    else:
      raise GypError("DoDependentSettings doesn't know how to determine "
                      'dependencies for ' + key)

    for dependency in dependencies:
      dependency_dict = targets[dependency]
      if not key in dependency_dict:
        continue
      dependency_build_file = gyp.common.BuildFile(dependency)
      MergeDicts(target_dict, dependency_dict[key],
                 build_file, dependency_build_file)


def AdjustStaticLibraryDependencies(flat_list, targets, dependency_nodes,
                                    sort_dependencies):
  # Recompute target "dependencies" properties.  For each static library
  # target, remove "dependencies" entries referring to other static libraries,
  # unless the dependency has the "hard_dependency" attribute set.  For each
  # linkable target, add a "dependencies" entry referring to all of the
  # target's computed list of link dependencies (including static libraries
  # if no such entry is already present.
  for target in flat_list:
    target_dict = targets[target]
    target_type = target_dict['type']

    if target_type == 'static_library':
      if not 'dependencies' in target_dict:
        continue

      target_dict['dependencies_original'] = target_dict.get(
          'dependencies', [])[:]

      # A static library should not depend on another static library unless
      # the dependency relationship is "hard," which should only be done when
      # a dependent relies on some side effect other than just the build
      # product, like a rule or action output. Further, if a target has a
      # non-hard dependency, but that dependency exports a hard dependency,
      # the non-hard dependency can safely be removed, but the exported hard
      # dependency must be added to the target to keep the same dependency
      # ordering.
      dependencies = \
          dependency_nodes[target].DirectAndImportedDependencies(targets)
      index = 0
      while index < len(dependencies):
        dependency = dependencies[index]
        dependency_dict = targets[dependency]

        # Remove every non-hard static library dependency and remove every
        # non-static library dependency that isn't a direct dependency.
        if (dependency_dict['type'] == 'static_library' and \
            not dependency_dict.get('hard_dependency', False)) or \
           (dependency_dict['type'] != 'static_library' and \
            not dependency in target_dict['dependencies']):
          # Take the dependency out of the list, and don't increment index
          # because the next dependency to analyze will shift into the index
          # formerly occupied by the one being removed.
          del dependencies[index]
        else:
          index = index + 1

      # Update the dependencies. If the dependencies list is empty, it's not
      # needed, so unhook it.
      if len(dependencies) > 0:
        target_dict['dependencies'] = dependencies
      else:
        del target_dict['dependencies']

    elif target_type in linkable_types:
      # Get a list of dependency targets that should be linked into this
      # target.  Add them to the dependencies list if they're not already
      # present.

      link_dependencies = dependency_nodes[target].LinkDependencies(targets)
      for dependency in link_dependencies:
        if dependency == target:
          continue
        if not 'dependencies' in target_dict:
          target_dict['dependencies'] = []
        if not dependency in target_dict['dependencies']:
          target_dict['dependencies'].append(dependency)
      # Sort the dependencies list in the order from dependents to dependencies.
      # e.g. If A and B depend on C and C depends on D, sort them in A, B, C, D.
      # Note: flat_list is already sorted in the order from dependencies to
      # dependents.
      if sort_dependencies and 'dependencies' in target_dict:
        target_dict['dependencies'] = [dep for dep in reversed(flat_list)
                                       if dep in target_dict['dependencies']]


# Initialize this here to speed up MakePathRelative.
exception_re = re.compile(r'''["']?[-/$<>^]''')


def MakePathRelative(to_file, fro_file, item):
  # If item is a relative path, it's relative to the build file dict that it's
  # coming from.  Fix it up to make it relative to the build file dict that
  # it's going into.
  # Exception: any |item| that begins with these special characters is
  # returned without modification.
  #   /   Used when a path is already absolute (shortcut optimization;
  #       such paths would be returned as absolute anyway)
  #   $   Used for build environment variables
  #   -   Used for some build environment flags (such as -lapr-1 in a
  #       "libraries" section)
  #   <   Used for our own variable and command expansions (see ExpandVariables)
  #   >   Used for our own variable and command expansions (see ExpandVariables)
  #   ^   Used for our own variable and command expansions (see ExpandVariables)
  #
  #   "/' Used when a value is quoted.  If these are present, then we
  #       check the second character instead.
  #
  if to_file == fro_file or exception_re.match(item):
    return item
  else:
    # TODO(dglazkov) The backslash/forward-slash replacement at the end is a
    # temporary measure. This should really be addressed by keeping all paths
    # in POSIX until actual project generation.
    ret = os.path.normpath(os.path.join(
        gyp.common.RelativePath(os.path.dirname(fro_file),
                                os.path.dirname(to_file)),
                                item)).replace('\\', '/')
    if item[-1] == '/':
      ret += '/'
    return ret

def MergeLists(to, fro, to_file, fro_file, is_paths=False, append=True):
  def is_hashable(x):
    try:
      hash(x)
    except TypeError:
      return False
    return True
  # If x is hashable, returns whether x is in s. Else returns whether x is in l.
  def is_in_set_or_list(x, s, l):
    if is_hashable(x):
      return x in s
    return x in l

  prepend_index = 0

  # Make membership testing of hashables in |to| (in particular, strings)
  # faster.
  hashable_to_set = set([x for x in to if is_hashable(x)])

  for item in fro:
    singleton = False
    if isinstance(item, str) or isinstance(item, int):
      # The cheap and easy case.
      if is_paths:
        to_item = MakePathRelative(to_file, fro_file, item)
      else:
        to_item = item

      if not isinstance(item, str) or not item.startswith('-'):
        # Any string that doesn't begin with a "-" is a singleton - it can
        # only appear once in a list, to be enforced by the list merge append
        # or prepend.
        singleton = True
    elif isinstance(item, dict):
      # Make a copy of the dictionary, continuing to look for paths to fix.
      # The other intelligent aspects of merge processing won't apply because
      # item is being merged into an empty dict.
      to_item = {}
      MergeDicts(to_item, item, to_file, fro_file)
    elif isinstance(item, list):
      # Recurse, making a copy of the list.  If the list contains any
      # descendant dicts, path fixing will occur.  Note that here, custom
      # values for is_paths and append are dropped; those are only to be
      # applied to |to| and |fro|, not sublists of |fro|.  append shouldn't
      # matter anyway because the new |to_item| list is empty.
      to_item = []
      MergeLists(to_item, item, to_file, fro_file)
    else:
      raise TypeError, \
          'Attempt to merge list item of unsupported type ' + \
          item.__class__.__name__

    if append:
      # If appending a singleton that's already in the list, don't append.
      # This ensures that the earliest occurrence of the item will stay put.
      if not singleton or not is_in_set_or_list(to_item, hashable_to_set, to):
        to.append(to_item)
        if is_hashable(to_item):
          hashable_to_set.add(to_item)
    else:
      # If prepending a singleton that's already in the list, remove the
      # existing instance and proceed with the prepend.  This ensures that the
      # item appears at the earliest possible position in the list.
      while singleton and to_item in to:
        to.remove(to_item)

      # Don't just insert everything at index 0.  That would prepend the new
      # items to the list in reverse order, which would be an unwelcome
      # surprise.
      to.insert(prepend_index, to_item)
      if is_hashable(to_item):
        hashable_to_set.add(to_item)
      prepend_index = prepend_index + 1


def MergeDicts(to, fro, to_file, fro_file):
  # I wanted to name the parameter "from" but it's a Python keyword...
  for k, v in fro.iteritems():
    # It would be nice to do "if not k in to: to[k] = v" but that wouldn't give
    # copy semantics.  Something else may want to merge from the |fro| dict
    # later, and having the same dict ref pointed to twice in the tree isn't
    # what anyone wants considering that the dicts may subsequently be
    # modified.
    if k in to:
      bad_merge = False
      if isinstance(v, str) or isinstance(v, int):
        if not (isinstance(to[k], str) or isinstance(to[k], int)):
          bad_merge = True
      elif v.__class__ != to[k].__class__:
        bad_merge = True

      if bad_merge:
        raise TypeError, \
            'Attempt to merge dict value of type ' + v.__class__.__name__ + \
            ' into incompatible type ' + to[k].__class__.__name__ + \
            ' for key ' + k
    if isinstance(v, str) or isinstance(v, int):
      # Overwrite the existing value, if any.  Cheap and easy.
      is_path = IsPathSection(k)
      if is_path:
        to[k] = MakePathRelative(to_file, fro_file, v)
      else:
        to[k] = v
    elif isinstance(v, dict):
      # Recurse, guaranteeing copies will be made of objects that require it.
      if not k in to:
        to[k] = {}
      MergeDicts(to[k], v, to_file, fro_file)
    elif isinstance(v, list):
      # Lists in dicts can be merged with different policies, depending on
      # how the key in the "from" dict (k, the from-key) is written.
      #
      # If the from-key has          ...the to-list will have this action
      # this character appended:...     applied when receiving the from-list:
      #                           =  replace
      #                           +  prepend
      #                           ?  set, only if to-list does not yet exist
      #                      (none)  append
      #
      # This logic is list-specific, but since it relies on the associated
      # dict key, it's checked in this dict-oriented function.
      ext = k[-1]
      append = True
      if ext == '=':
        list_base = k[:-1]
        lists_incompatible = [list_base, list_base + '?']
        to[list_base] = []
      elif ext == '+':
        list_base = k[:-1]
        lists_incompatible = [list_base + '=', list_base + '?']
        append = False
      elif ext == '?':
        list_base = k[:-1]
        lists_incompatible = [list_base, list_base + '=', list_base + '+']
      else:
        list_base = k
        lists_incompatible = [list_base + '=', list_base + '?']

      # Some combinations of merge policies appearing together are meaningless.
      # It's stupid to replace and append simultaneously, for example.  Append
      # and prepend are the only policies that can coexist.
      for list_incompatible in lists_incompatible:
        if list_incompatible in fro:
          raise GypError('Incompatible list policies ' + k + ' and ' +
                         list_incompatible)

      if list_base in to:
        if ext == '?':
          # If the key ends in "?", the list will only be merged if it doesn't
          # already exist.
          continue
        if not isinstance(to[list_base], list):
          # This may not have been checked above if merging in a list with an
          # extension character.
          raise TypeError, \
              'Attempt to merge dict value of type ' + v.__class__.__name__ + \
              ' into incompatible type ' + to[list_base].__class__.__name__ + \
              ' for key ' + list_base + '(' + k + ')'
      else:
        to[list_base] = []

      # Call MergeLists, which will make copies of objects that require it.
      # MergeLists can recurse back into MergeDicts, although this will be
      # to make copies of dicts (with paths fixed), there will be no
      # subsequent dict "merging" once entering a list because lists are
      # always replaced, appended to, or prepended to.
      is_paths = IsPathSection(list_base)
      MergeLists(to[list_base], v, to_file, fro_file, is_paths, append)
    else:
      raise TypeError, \
          'Attempt to merge dict value of unsupported type ' + \
          v.__class__.__name__ + ' for key ' + k


def MergeConfigWithInheritance(new_configuration_dict, build_file,
                               target_dict, configuration, visited):
  # Skip if previously visted.
  if configuration in visited:
    return

  # Look at this configuration.
  configuration_dict = target_dict['configurations'][configuration]

  # Merge in parents.
  for parent in configuration_dict.get('inherit_from', []):
    MergeConfigWithInheritance(new_configuration_dict, build_file,
                               target_dict, parent, visited + [configuration])

  # Merge it into the new config.
  MergeDicts(new_configuration_dict, configuration_dict,
             build_file, build_file)

  # Drop abstract.
  if 'abstract' in new_configuration_dict:
    del new_configuration_dict['abstract']


def SetUpConfigurations(target, target_dict):
  # key_suffixes is a list of key suffixes that might appear on key names.
  # These suffixes are handled in conditional evaluations (for =, +, and ?)
  # and rules/exclude processing (for ! and /).  Keys with these suffixes
  # should be treated the same as keys without.
  key_suffixes = ['=', '+', '?', '!', '/']

  build_file = gyp.common.BuildFile(target)

  # Provide a single configuration by default if none exists.
  # TODO(mark): Signal an error if default_configurations exists but
  # configurations does not.
  if not 'configurations' in target_dict:
    target_dict['configurations'] = {'Default': {}}
  if not 'default_configuration' in target_dict:
    concrete = [i for i in target_dict['configurations'].keys()
                if not target_dict['configurations'][i].get('abstract')]
    target_dict['default_configuration'] = sorted(concrete)[0]

  for configuration in target_dict['configurations'].keys():
    old_configuration_dict = target_dict['configurations'][configuration]
    # Skip abstract configurations (saves work only).
    if old_configuration_dict.get('abstract'):
      continue
    # Configurations inherit (most) settings from the enclosing target scope.
    # Get the inheritance relationship right by making a copy of the target
    # dict.
    new_configuration_dict = copy.deepcopy(target_dict)

    # Take out the bits that don't belong in a "configurations" section.
    # Since configuration setup is done before conditional, exclude, and rules
    # processing, be careful with handling of the suffix characters used in
    # those phases.
    delete_keys = []
    for key in new_configuration_dict:
      key_ext = key[-1:]
      if key_ext in key_suffixes:
        key_base = key[:-1]
      else:
        key_base = key
      if key_base in non_configuration_keys:
        delete_keys.append(key)

    for key in delete_keys:
      del new_configuration_dict[key]

    # Merge in configuration (with all its parents first).
    MergeConfigWithInheritance(new_configuration_dict, build_file,
                               target_dict, configuration, [])

    # Put the new result back into the target dict as a configuration.
    target_dict['configurations'][configuration] = new_configuration_dict

  # Now drop all the abstract ones.
  for configuration in target_dict['configurations'].keys():
    old_configuration_dict = target_dict['configurations'][configuration]
    if old_configuration_dict.get('abstract'):
      del target_dict['configurations'][configuration]

  # Now that all of the target's configurations have been built, go through
  # the target dict's keys and remove everything that's been moved into a
  # "configurations" section.
  delete_keys = []
  for key in target_dict:
    key_ext = key[-1:]
    if key_ext in key_suffixes:
      key_base = key[:-1]
    else:
      key_base = key
    if not key_base in non_configuration_keys:
      delete_keys.append(key)
  for key in delete_keys:
    del target_dict[key]

  # Check the configurations to see if they contain invalid keys.
  for configuration in target_dict['configurations'].keys():
    configuration_dict = target_dict['configurations'][configuration]
    for key in configuration_dict.keys():
      if key in invalid_configuration_keys:
        raise GypError('%s not allowed in the %s configuration, found in '
                       'target %s' % (key, configuration, target))



def ProcessListFiltersInDict(name, the_dict):
  """Process regular expression and exclusion-based filters on lists.

  An exclusion list is in a dict key named with a trailing "!", like
  "sources!".  Every item in such a list is removed from the associated
  main list, which in this example, would be "sources".  Removed items are
  placed into a "sources_excluded" list in the dict.

  Regular expression (regex) filters are contained in dict keys named with a
  trailing "/", such as "sources/" to operate on the "sources" list.  Regex
  filters in a dict take the form:
    'sources/': [ ['exclude', '_(linux|mac|win)\\.cc$'],
                  ['include', '_mac\\.cc$'] ],
  The first filter says to exclude all files ending in _linux.cc, _mac.cc, and
  _win.cc.  The second filter then includes all files ending in _mac.cc that
  are now or were once in the "sources" list.  Items matching an "exclude"
  filter are subject to the same processing as would occur if they were listed
  by name in an exclusion list (ending in "!").  Items matching an "include"
  filter are brought back into the main list if previously excluded by an
  exclusion list or exclusion regex filter.  Subsequent matching "exclude"
  patterns can still cause items to be excluded after matching an "include".
  """

  # Look through the dictionary for any lists whose keys end in "!" or "/".
  # These are lists that will be treated as exclude lists and regular
  # expression-based exclude/include lists.  Collect the lists that are
  # needed first, looking for the lists that they operate on, and assemble
  # then into |lists|.  This is done in a separate loop up front, because
  # the _included and _excluded keys need to be added to the_dict, and that
  # can't be done while iterating through it.

  lists = []
  del_lists = []
  for key, value in the_dict.iteritems():
    operation = key[-1]
    if operation != '!' and operation != '/':
      continue

    if not isinstance(value, list):
      raise ValueError, name + ' key ' + key + ' must be list, not ' + \
                        value.__class__.__name__

    list_key = key[:-1]
    if list_key not in the_dict:
      # This happens when there's a list like "sources!" but no corresponding
      # "sources" list.  Since there's nothing for it to operate on, queue up
      # the "sources!" list for deletion now.
      del_lists.append(key)
      continue

    if not isinstance(the_dict[list_key], list):
      raise ValueError, name + ' key ' + list_key + \
                        ' must be list, not ' + \
                        value.__class__.__name__ + ' when applying ' + \
                        {'!': 'exclusion', '/': 'regex'}[operation]

    if not list_key in lists:
      lists.append(list_key)

  # Delete the lists that are known to be unneeded at this point.
  for del_list in del_lists:
    del the_dict[del_list]

  for list_key in lists:
    the_list = the_dict[list_key]

    # Initialize the list_actions list, which is parallel to the_list.  Each
    # item in list_actions identifies whether the corresponding item in
    # the_list should be excluded, unconditionally preserved (included), or
    # whether no exclusion or inclusion has been applied.  Items for which
    # no exclusion or inclusion has been applied (yet) have value -1, items
    # excluded have value 0, and items included have value 1.  Includes and
    # excludes override previous actions.  All items in list_actions are
    # initialized to -1 because no excludes or includes have been processed
    # yet.
    list_actions = list((-1,) * len(the_list))

    exclude_key = list_key + '!'
    if exclude_key in the_dict:
      for exclude_item in the_dict[exclude_key]:
        for index in xrange(0, len(the_list)):
          if exclude_item == the_list[index]:
            # This item matches the exclude_item, so set its action to 0
            # (exclude).
            list_actions[index] = 0

      # The "whatever!" list is no longer needed, dump it.
      del the_dict[exclude_key]

    regex_key = list_key + '/'
    if regex_key in the_dict:
      for regex_item in the_dict[regex_key]:
        [action, pattern] = regex_item
        pattern_re = re.compile(pattern)

        if action == 'exclude':
          # This item matches an exclude regex, so set its value to 0 (exclude).
          action_value = 0
        elif action == 'include':
          # This item matches an include regex, so set its value to 1 (include).
          action_value = 1
        else:
          # This is an action that doesn't make any sense.
          raise ValueError, 'Unrecognized action ' + action + ' in ' + name + \
                            ' key ' + regex_key

        for index in xrange(0, len(the_list)):
          list_item = the_list[index]
          if list_actions[index] == action_value:
            # Even if the regex matches, nothing will change so continue (regex
            # searches are expensive).
            continue
          if pattern_re.search(list_item):
            # Regular expression match.
            list_actions[index] = action_value

      # The "whatever/" list is no longer needed, dump it.
      del the_dict[regex_key]

    # Add excluded items to the excluded list.
    #
    # Note that exclude_key ("sources!") is different from excluded_key
    # ("sources_excluded").  The exclude_key list is input and it was already
    # processed and deleted; the excluded_key list is output and it's about
    # to be created.
    excluded_key = list_key + '_excluded'
    if excluded_key in the_dict:
      raise GypError(name + ' key ' + excluded_key +
                     ' must not be present prior '
                     ' to applying exclusion/regex filters for ' + list_key)

    excluded_list = []

    # Go backwards through the list_actions list so that as items are deleted,
    # the indices of items that haven't been seen yet don't shift.  That means
    # that things need to be prepended to excluded_list to maintain them in the
    # same order that they existed in the_list.
    for index in xrange(len(list_actions) - 1, -1, -1):
      if list_actions[index] == 0:
        # Dump anything with action 0 (exclude).  Keep anything with action 1
        # (include) or -1 (no include or exclude seen for the item).
        excluded_list.insert(0, the_list[index])
        del the_list[index]

    # If anything was excluded, put the excluded list into the_dict at
    # excluded_key.
    if len(excluded_list) > 0:
      the_dict[excluded_key] = excluded_list

  # Now recurse into subdicts and lists that may contain dicts.
  for key, value in the_dict.iteritems():
    if isinstance(value, dict):
      ProcessListFiltersInDict(key, value)
    elif isinstance(value, list):
      ProcessListFiltersInList(key, value)


def ProcessListFiltersInList(name, the_list):
  for item in the_list:
    if isinstance(item, dict):
      ProcessListFiltersInDict(name, item)
    elif isinstance(item, list):
      ProcessListFiltersInList(name, item)


def ValidateTargetType(target, target_dict):
  """Ensures the 'type' field on the target is one of the known types.

  Arguments:
    target: string, name of target.
    target_dict: dict, target spec.

  Raises an exception on error.
  """
  VALID_TARGET_TYPES = ('executable', 'loadable_module',
                        'static_library', 'shared_library',
                        'none')
  target_type = target_dict.get('type', None)
  if target_type not in VALID_TARGET_TYPES:
    raise GypError("Target %s has an invalid target type '%s'.  "
                   "Must be one of %s." %
                   (target, target_type, '/'.join(VALID_TARGET_TYPES)))
  if (target_dict.get('standalone_static_library', 0) and
      not target_type == 'static_library'):
    raise GypError('Target %s has type %s but standalone_static_library flag is'
                   ' only valid for static_library type.' % (target,
                                                             target_type))


def ValidateSourcesInTarget(target, target_dict, build_file):
  # TODO: Check if MSVC allows this for non-static_library targets.
  if target_dict.get('type', None) != 'static_library':
    return
  sources = target_dict.get('sources', [])
  basenames = {}
  for source in sources:
    name, ext = os.path.splitext(source)
    is_compiled_file = ext in [
        '.c', '.cc', '.cpp', '.cxx', '.m', '.mm', '.s', '.S']
    if not is_compiled_file:
      continue
    basename = os.path.basename(name)  # Don't include extension.
    basenames.setdefault(basename, []).append(source)

  error = ''
  for basename, files in basenames.iteritems():
    if len(files) > 1:
      error += '  %s: %s\n' % (basename, ' '.join(files))

  if error:
    print('static library %s has several files with the same basename:\n' %
          target + error + 'Some build systems, e.g. MSVC08, '
          'cannot handle that.')
    raise GypError('Duplicate basenames in sources section, see list above')


def ValidateRulesInTarget(target, target_dict, extra_sources_for_rules):
  """Ensures that the rules sections in target_dict are valid and consistent,
  and determines which sources they apply to.

  Arguments:
    target: string, name of target.
    target_dict: dict, target spec containing "rules" and "sources" lists.
    extra_sources_for_rules: a list of keys to scan for rule matches in
        addition to 'sources'.
  """

  # Dicts to map between values found in rules' 'rule_name' and 'extension'
  # keys and the rule dicts themselves.
  rule_names = {}
  rule_extensions = {}

  rules = target_dict.get('rules', [])
  for rule in rules:
    # Make sure that there's no conflict among rule names and extensions.
    rule_name = rule['rule_name']
    if rule_name in rule_names:
      raise GypError('rule %s exists in duplicate, target %s' %
                     (rule_name, target))
    rule_names[rule_name] = rule

    rule_extension = rule['extension']
    if rule_extension in rule_extensions:
      raise GypError(('extension %s associated with multiple rules, ' +
                      'target %s rules %s and %s') %
                     (rule_extension, target,
                      rule_extensions[rule_extension]['rule_name'],
                      rule_name))
    rule_extensions[rule_extension] = rule

    # Make sure rule_sources isn't already there.  It's going to be
    # created below if needed.
    if 'rule_sources' in rule:
      raise GypError(
            'rule_sources must not exist in input, target %s rule %s' %
            (target, rule_name))
    extension = rule['extension']

    rule_sources = []
    source_keys = ['sources']
    source_keys.extend(extra_sources_for_rules)
    for source_key in source_keys:
      for source in target_dict.get(source_key, []):
        (source_root, source_extension) = os.path.splitext(source)
        if source_extension.startswith('.'):
          source_extension = source_extension[1:]
        if source_extension == extension:
          rule_sources.append(source)

    if len(rule_sources) > 0:
      rule['rule_sources'] = rule_sources


def ValidateRunAsInTarget(target, target_dict, build_file):
  target_name = target_dict.get('target_name')
  run_as = target_dict.get('run_as')
  if not run_as:
    return
  if not isinstance(run_as, dict):
    raise GypError("The 'run_as' in target %s from file %s should be a "
                   "dictionary." %
                   (target_name, build_file))
  action = run_as.get('action')
  if not action:
    raise GypError("The 'run_as' in target %s from file %s must have an "
                   "'action' section." %
                   (target_name, build_file))
  if not isinstance(action, list):
    raise GypError("The 'action' for 'run_as' in target %s from file %s "
                   "must be a list." %
                   (target_name, build_file))
  working_directory = run_as.get('working_directory')
  if working_directory and not isinstance(working_directory, str):
    raise GypError("The 'working_directory' for 'run_as' in target %s "
                   "in file %s should be a string." %
                   (target_name, build_file))
  environment = run_as.get('environment')
  if environment and not isinstance(environment, dict):
    raise GypError("The 'environment' for 'run_as' in target %s "
                   "in file %s should be a dictionary." %
                   (target_name, build_file))


def ValidateActionsInTarget(target, target_dict, build_file):
  '''Validates the inputs to the actions in a target.'''
  target_name = target_dict.get('target_name')
  actions = target_dict.get('actions', [])
  for action in actions:
    action_name = action.get('action_name')
    if not action_name:
      raise GypError("Anonymous action in target %s.  "
                     "An action must have an 'action_name' field." %
                     target_name)
    inputs = action.get('inputs', None)
    if inputs is None:
      raise GypError('Action in target %s has no inputs.' % target_name)
    action_command = action.get('action')
    if action_command and not action_command[0]:
      raise GypError("Empty action as command in target %s." % target_name)


def TurnIntIntoStrInDict(the_dict):
  """Given dict the_dict, recursively converts all integers into strings.
  """
  # Use items instead of iteritems because there's no need to try to look at
  # reinserted keys and their associated values.
  for k, v in the_dict.items():
    if isinstance(v, int):
      v = str(v)
      the_dict[k] = v
    elif isinstance(v, dict):
      TurnIntIntoStrInDict(v)
    elif isinstance(v, list):
      TurnIntIntoStrInList(v)

    if isinstance(k, int):
      the_dict[str(k)] = v
      del the_dict[k]


def TurnIntIntoStrInList(the_list):
  """Given list the_list, recursively converts all integers into strings.
  """
  for index in xrange(0, len(the_list)):
    item = the_list[index]
    if isinstance(item, int):
      the_list[index] = str(item)
    elif isinstance(item, dict):
      TurnIntIntoStrInDict(item)
    elif isinstance(item, list):
      TurnIntIntoStrInList(item)


def VerifyNoCollidingTargets(targets):
  """Verify that no two targets in the same directory share the same name.

  Arguments:
    targets: A list of targets in the form 'path/to/file.gyp:target_name'.
  """
  # Keep a dict going from 'subdirectory:target_name' to 'foo.gyp'.
  used = {}
  for target in targets:
    # Separate out 'path/to/file.gyp, 'target_name' from
    # 'path/to/file.gyp:target_name'.
    path, name = target.rsplit(':', 1)
    # Separate out 'path/to', 'file.gyp' from 'path/to/file.gyp'.
    subdir, gyp = os.path.split(path)
    # Use '.' for the current directory '', so that the error messages make
    # more sense.
    if not subdir:
      subdir = '.'
    # Prepare a key like 'path/to:target_name'.
    key = subdir + ':' + name
    if key in used:
      # Complain if this target is already used.
      raise GypError('Duplicate target name "%s" in directory "%s" used both '
                     'in "%s" and "%s".' % (name, subdir, gyp, used[key]))
    used[key] = gyp


def Load(build_files, variables, includes, depth, generator_input_info, check,
         circular_check, parallel):
  # Set up path_sections and non_configuration_keys with the default data plus
  # the generator-specifc data.
  global path_sections
  path_sections = base_path_sections[:]
  path_sections.extend(generator_input_info['path_sections'])

  global non_configuration_keys
  non_configuration_keys = base_non_configuration_keys[:]
  non_configuration_keys.extend(generator_input_info['non_configuration_keys'])

  # TODO(mark) handle variants if the generator doesn't want them directly.
  generator_handles_variants = \
      generator_input_info['generator_handles_variants']

  global absolute_build_file_paths
  absolute_build_file_paths = \
      generator_input_info['generator_wants_absolute_build_file_paths']

  global multiple_toolsets
  multiple_toolsets = generator_input_info[
      'generator_supports_multiple_toolsets']

  # A generator can have other lists (in addition to sources) be processed
  # for rules.
  extra_sources_for_rules = generator_input_info['extra_sources_for_rules']

  # Load build files.  This loads every target-containing build file into
  # the |data| dictionary such that the keys to |data| are build file names,
  # and the values are the entire build file contents after "early" or "pre"
  # processing has been done and includes have been resolved.
  # NOTE: data contains both "target" files (.gyp) and "includes" (.gypi), as
  # well as meta-data (e.g. 'included_files' key). 'target_build_files' keeps
  # track of the keys corresponding to "target" files.
  data = {'target_build_files': set()}
  aux_data = {}
  for build_file in build_files:
    # Normalize paths everywhere.  This is important because paths will be
    # used as keys to the data dict and for references between input files.
    build_file = os.path.normpath(build_file)
    try:
      if parallel:
        print >>sys.stderr, 'Using parallel processing (experimental).'
        LoadTargetBuildFileParallel(build_file, data, aux_data,
                                    variables, includes, depth, check)
      else:
        LoadTargetBuildFile(build_file, data, aux_data,
                            variables, includes, depth, check, True)
    except Exception, e:
      gyp.common.ExceptionAppend(e, 'while trying to load %s' % build_file)
      raise

  # Build a dict to access each target's subdict by qualified name.
  targets = BuildTargetsDict(data)

  # Fully qualify all dependency links.
  QualifyDependencies(targets)

  # Expand dependencies specified as build_file:*.
  ExpandWildcardDependencies(targets, data)

  # Apply exclude (!) and regex (/) list filters only for dependency_sections.
  for target_name, target_dict in targets.iteritems():
    tmp_dict = {}
    for key_base in dependency_sections:
      for op in ('', '!', '/'):
        key = key_base + op
        if key in target_dict:
          tmp_dict[key] = target_dict[key]
          del target_dict[key]
    ProcessListFiltersInDict(target_name, tmp_dict)
    # Write the results back to |target_dict|.
    for key in tmp_dict:
      target_dict[key] = tmp_dict[key]

  # Make sure every dependency appears at most once.
  RemoveDuplicateDependencies(targets)

  if circular_check:
    # Make sure that any targets in a.gyp don't contain dependencies in other
    # .gyp files that further depend on a.gyp.
    VerifyNoGYPFileCircularDependencies(targets)

  [dependency_nodes, flat_list] = BuildDependencyList(targets)

  # Check that no two targets in the same directory have the same name.
  VerifyNoCollidingTargets(flat_list)

  # Handle dependent settings of various types.
  for settings_type in ['all_dependent_settings',
                        'direct_dependent_settings',
                        'link_settings']:
    DoDependentSettings(settings_type, flat_list, targets, dependency_nodes)

    # Take out the dependent settings now that they've been published to all
    # of the targets that require them.
    for target in flat_list:
      if settings_type in targets[target]:
        del targets[target][settings_type]

  # Make sure static libraries don't declare dependencies on other static
  # libraries, but that linkables depend on all unlinked static libraries
  # that they need so that their link steps will be correct.
  gii = generator_input_info
  if gii['generator_wants_static_library_dependencies_adjusted']:
    AdjustStaticLibraryDependencies(flat_list, targets, dependency_nodes,
                                    gii['generator_wants_sorted_dependencies'])

  # Apply "post"/"late"/"target" variable expansions and condition evaluations.
  for target in flat_list:
    target_dict = targets[target]
    build_file = gyp.common.BuildFile(target)
    ProcessVariablesAndConditionsInDict(
        target_dict, PHASE_LATE, variables, build_file)

  # Move everything that can go into a "configurations" section into one.
  for target in flat_list:
    target_dict = targets[target]
    SetUpConfigurations(target, target_dict)

  # Apply exclude (!) and regex (/) list filters.
  for target in flat_list:
    target_dict = targets[target]
    ProcessListFiltersInDict(target, target_dict)

  # Apply "latelate" variable expansions and condition evaluations.
  for target in flat_list:
    target_dict = targets[target]
    build_file = gyp.common.BuildFile(target)
    ProcessVariablesAndConditionsInDict(
        target_dict, PHASE_LATELATE, variables, build_file)

  # Make sure that the rules make sense, and build up rule_sources lists as
  # needed.  Not all generators will need to use the rule_sources lists, but
  # some may, and it seems best to build the list in a common spot.
  # Also validate actions and run_as elements in targets.
  for target in flat_list:
    target_dict = targets[target]
    build_file = gyp.common.BuildFile(target)
    ValidateTargetType(target, target_dict)
    # TODO(thakis): Get vpx_scale/arm/scalesystemdependent.c to be renamed to
    #               scalesystemdependent_arm_additions.c or similar.
    if 'arm' not in variables.get('target_arch', ''):
      ValidateSourcesInTarget(target, target_dict, build_file)
    ValidateRulesInTarget(target, target_dict, extra_sources_for_rules)
    ValidateRunAsInTarget(target, target_dict, build_file)
    ValidateActionsInTarget(target, target_dict, build_file)

  # Generators might not expect ints.  Turn them into strs.
  TurnIntIntoStrInDict(data)

  # TODO(mark): Return |data| for now because the generator needs a list of
  # build files that came in.  In the future, maybe it should just accept
  # a list, and not the whole data dict.
  return [flat_list, targets, data]

########NEW FILE########
__FILENAME__ = mac_tool
#!/usr/bin/env python
# Copyright (c) 2012 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utility functions to perform Xcode-style build steps.

These functions are executed via gyp-mac-tool when using the Makefile generator.
"""

import fcntl
import os
import plistlib
import re
import shutil
import string
import subprocess
import sys


def main(args):
  executor = MacTool()
  exit_code = executor.Dispatch(args)
  if exit_code is not None:
    sys.exit(exit_code)


class MacTool(object):
  """This class performs all the Mac tooling steps. The methods can either be
  executed directly, or dispatched from an argument list."""

  def Dispatch(self, args):
    """Dispatches a string command to a method."""
    if len(args) < 1:
      raise Exception("Not enough arguments")

    method = "Exec%s" % self._CommandifyName(args[0])
    return getattr(self, method)(*args[1:])

  def _CommandifyName(self, name_string):
    """Transforms a tool name like copy-info-plist to CopyInfoPlist"""
    return name_string.title().replace('-', '')

  def ExecCopyBundleResource(self, source, dest):
    """Copies a resource file to the bundle/Resources directory, performing any
    necessary compilation on each resource."""
    extension = os.path.splitext(source)[1].lower()
    if os.path.isdir(source):
      # Copy tree.
      if os.path.exists(dest):
        shutil.rmtree(dest)
      shutil.copytree(source, dest)
    elif extension == '.xib':
      return self._CopyXIBFile(source, dest)
    elif extension == '.strings':
      self._CopyStringsFile(source, dest)
    else:
      shutil.copyfile(source, dest)

  def _CopyXIBFile(self, source, dest):
    """Compiles a XIB file with ibtool into a binary plist in the bundle."""
    tools_dir = os.environ.get('DEVELOPER_BIN_DIR', '/usr/bin')
    args = [os.path.join(tools_dir, 'ibtool'), '--errors', '--warnings',
        '--notices', '--output-format', 'human-readable-text', '--compile',
        dest, source]
    ibtool_section_re = re.compile(r'/\*.*\*/')
    ibtool_re = re.compile(r'.*note:.*is clipping its content')
    ibtoolout = subprocess.Popen(args, stdout=subprocess.PIPE)
    current_section_header = None
    for line in ibtoolout.stdout:
      if ibtool_section_re.match(line):
        current_section_header = line
      elif not ibtool_re.match(line):
        if current_section_header:
          sys.stdout.write(current_section_header)
          current_section_header = None
        sys.stdout.write(line)
    return ibtoolout.returncode

  def _CopyStringsFile(self, source, dest):
    """Copies a .strings file using iconv to reconvert the input into UTF-16."""
    input_code = self._DetectInputEncoding(source) or "UTF-8"
    fp = open(dest, 'w')
    args = ['/usr/bin/iconv', '--from-code', input_code, '--to-code',
        'UTF-16', source]
    subprocess.call(args, stdout=fp)
    fp.close()

  def _DetectInputEncoding(self, file_name):
    """Reads the first few bytes from file_name and tries to guess the text
    encoding. Returns None as a guess if it can't detect it."""
    fp = open(file_name, 'rb')
    try:
      header = fp.read(3)
    except e:
      fp.close()
      return None
    fp.close()
    if header.startswith("\xFE\xFF"):
      return "UTF-16BE"
    elif header.startswith("\xFF\xFE"):
      return "UTF-16LE"
    elif header.startswith("\xEF\xBB\xBF"):
      return "UTF-8"
    else:
      return None

  def ExecCopyInfoPlist(self, source, dest):
    """Copies the |source| Info.plist to the destination directory |dest|."""
    # Read the source Info.plist into memory.
    fd = open(source, 'r')
    lines = fd.read()
    fd.close()

    # Go through all the environment variables and replace them as variables in
    # the file.
    for key in os.environ:
      if key.startswith('_'):
        continue
      evar = '${%s}' % key
      lines = string.replace(lines, evar, os.environ[key])

    # Write out the file with variables replaced.
    fd = open(dest, 'w')
    fd.write(lines)
    fd.close()

    # Now write out PkgInfo file now that the Info.plist file has been
    # "compiled".
    self._WritePkgInfo(dest)

  def _WritePkgInfo(self, info_plist):
    """This writes the PkgInfo file from the data stored in Info.plist."""
    plist = plistlib.readPlist(info_plist)
    if not plist:
      return

    # Only create PkgInfo for executable types.
    package_type = plist['CFBundlePackageType']
    if package_type != 'APPL':
      return

    # The format of PkgInfo is eight characters, representing the bundle type
    # and bundle signature, each four characters. If that is missing, four
    # '?' characters are used instead.
    signature_code = plist.get('CFBundleSignature', '????')
    if len(signature_code) != 4:  # Wrong length resets everything, too.
      signature_code = '?' * 4

    dest = os.path.join(os.path.dirname(info_plist), 'PkgInfo')
    fp = open(dest, 'w')
    fp.write('%s%s' % (package_type, signature_code))
    fp.close()

  def ExecFlock(self, lockfile, *cmd_list):
    """Emulates the most basic behavior of Linux's flock(1)."""
    # Rely on exception handling to report errors.
    fd = os.open(lockfile, os.O_RDONLY|os.O_NOCTTY|os.O_CREAT, 0o666)
    fcntl.flock(fd, fcntl.LOCK_EX)
    return subprocess.call(cmd_list)

  def ExecFilterLibtool(self, *cmd_list):
    """Calls libtool and filters out 'libtool: file: foo.o has no symbols'."""
    libtool_re = re.compile(r'^libtool: file: .* has no symbols$')
    libtoolout = subprocess.Popen(cmd_list, stderr=subprocess.PIPE)
    _, err = libtoolout.communicate()
    for line in err.splitlines():
      if not libtool_re.match(line):
        print >>sys.stderr, line
    return libtoolout.returncode

  def ExecPackageFramework(self, framework, version):
    """Takes a path to Something.framework and the Current version of that and
    sets up all the symlinks."""
    # Find the name of the binary based on the part before the ".framework".
    binary = os.path.basename(framework).split('.')[0]

    CURRENT = 'Current'
    RESOURCES = 'Resources'
    VERSIONS = 'Versions'

    if not os.path.exists(os.path.join(framework, VERSIONS, version, binary)):
      # Binary-less frameworks don't seem to contain symlinks (see e.g.
      # chromium's out/Debug/org.chromium.Chromium.manifest/ bundle).
      return

    # Move into the framework directory to set the symlinks correctly.
    pwd = os.getcwd()
    os.chdir(framework)

    # Set up the Current version.
    self._Relink(version, os.path.join(VERSIONS, CURRENT))

    # Set up the root symlinks.
    self._Relink(os.path.join(VERSIONS, CURRENT, binary), binary)
    self._Relink(os.path.join(VERSIONS, CURRENT, RESOURCES), RESOURCES)

    # Back to where we were before!
    os.chdir(pwd)

  def _Relink(self, dest, link):
    """Creates a symlink to |dest| named |link|. If |link| already exists,
    it is overwritten."""
    if os.path.lexists(link):
      os.remove(link)
    os.symlink(dest, link)


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))

########NEW FILE########
__FILENAME__ = MSVSNew
# Copyright (c) 2012 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""New implementation of Visual Studio project generation for SCons."""

import os
import random

import gyp.common

# hashlib is supplied as of Python 2.5 as the replacement interface for md5
# and other secure hashes.  In 2.6, md5 is deprecated.  Import hashlib if
# available, avoiding a deprecation warning under 2.6.  Import md5 otherwise,
# preserving 2.4 compatibility.
try:
  import hashlib
  _new_md5 = hashlib.md5
except ImportError:
  import md5
  _new_md5 = md5.new


# Initialize random number generator
random.seed()

# GUIDs for project types
ENTRY_TYPE_GUIDS = {
    'project': '{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}',
    'folder': '{2150E333-8FDC-42A3-9474-1A3956D46DE8}',
}

#------------------------------------------------------------------------------
# Helper functions


def MakeGuid(name, seed='msvs_new'):
  """Returns a GUID for the specified target name.

  Args:
    name: Target name.
    seed: Seed for MD5 hash.
  Returns:
    A GUID-line string calculated from the name and seed.

  This generates something which looks like a GUID, but depends only on the
  name and seed.  This means the same name/seed will always generate the same
  GUID, so that projects and solutions which refer to each other can explicitly
  determine the GUID to refer to explicitly.  It also means that the GUID will
  not change when the project for a target is rebuilt.
  """
  # Calculate a MD5 signature for the seed and name.
  d = _new_md5(str(seed) + str(name)).hexdigest().upper()
  # Convert most of the signature to GUID form (discard the rest)
  guid = ('{' + d[:8] + '-' + d[8:12] + '-' + d[12:16] + '-' + d[16:20]
          + '-' + d[20:32] + '}')
  return guid

#------------------------------------------------------------------------------


class MSVSSolutionEntry(object):
  def __cmp__(self, other):
    # Sort by name then guid (so things are in order on vs2008).
    return cmp((self.name, self.get_guid()), (other.name, other.get_guid()))


class MSVSFolder(MSVSSolutionEntry):
  """Folder in a Visual Studio project or solution."""

  def __init__(self, path, name = None, entries = None,
               guid = None, items = None):
    """Initializes the folder.

    Args:
      path: Full path to the folder.
      name: Name of the folder.
      entries: List of folder entries to nest inside this folder.  May contain
          Folder or Project objects.  May be None, if the folder is empty.
      guid: GUID to use for folder, if not None.
      items: List of solution items to include in the folder project.  May be
          None, if the folder does not directly contain items.
    """
    if name:
      self.name = name
    else:
      # Use last layer.
      self.name = os.path.basename(path)

    self.path = path
    self.guid = guid

    # Copy passed lists (or set to empty lists)
    self.entries = sorted(list(entries or []))
    self.items = list(items or [])

    self.entry_type_guid = ENTRY_TYPE_GUIDS['folder']

  def get_guid(self):
    if self.guid is None:
      # Use consistent guids for folders (so things don't regenerate).
      self.guid = MakeGuid(self.path, seed='msvs_folder')
    return self.guid


#------------------------------------------------------------------------------


class MSVSProject(MSVSSolutionEntry):
  """Visual Studio project."""

  def __init__(self, path, name = None, dependencies = None, guid = None,
               spec = None, build_file = None, config_platform_overrides = None,
               fixpath_prefix = None):
    """Initializes the project.

    Args:
      path: Absolute path to the project file.
      name: Name of project.  If None, the name will be the same as the base
          name of the project file.
      dependencies: List of other Project objects this project is dependent
          upon, if not None.
      guid: GUID to use for project, if not None.
      spec: Dictionary specifying how to build this project.
      build_file: Filename of the .gyp file that the vcproj file comes from.
      config_platform_overrides: optional dict of configuration platforms to
          used in place of the default for this target.
      fixpath_prefix: the path used to adjust the behavior of _fixpath
    """
    self.path = path
    self.guid = guid
    self.spec = spec
    self.build_file = build_file
    # Use project filename if name not specified
    self.name = name or os.path.splitext(os.path.basename(path))[0]

    # Copy passed lists (or set to empty lists)
    self.dependencies = list(dependencies or [])

    self.entry_type_guid = ENTRY_TYPE_GUIDS['project']

    if config_platform_overrides:
      self.config_platform_overrides = config_platform_overrides
    else:
      self.config_platform_overrides = {}
    self.fixpath_prefix = fixpath_prefix
    self.msbuild_toolset = None

  def set_dependencies(self, dependencies):
    self.dependencies = list(dependencies or [])

  def get_guid(self):
    if self.guid is None:
      # Set GUID from path
      # TODO(rspangler): This is fragile.
      # 1. We can't just use the project filename sans path, since there could
      #    be multiple projects with the same base name (for example,
      #    foo/unittest.vcproj and bar/unittest.vcproj).
      # 2. The path needs to be relative to $SOURCE_ROOT, so that the project
      #    GUID is the same whether it's included from base/base.sln or
      #    foo/bar/baz/baz.sln.
      # 3. The GUID needs to be the same each time this builder is invoked, so
      #    that we don't need to rebuild the solution when the project changes.
      # 4. We should be able to handle pre-built project files by reading the
      #    GUID from the files.
      self.guid = MakeGuid(self.name)
    return self.guid

  def set_msbuild_toolset(self, msbuild_toolset):
    self.msbuild_toolset = msbuild_toolset

#------------------------------------------------------------------------------


class MSVSSolution:
  """Visual Studio solution."""

  def __init__(self, path, version, entries=None, variants=None,
               websiteProperties=True):
    """Initializes the solution.

    Args:
      path: Path to solution file.
      version: Format version to emit.
      entries: List of entries in solution.  May contain Folder or Project
          objects.  May be None, if the folder is empty.
      variants: List of build variant strings.  If none, a default list will
          be used.
      websiteProperties: Flag to decide if the website properties section
          is generated.
    """
    self.path = path
    self.websiteProperties = websiteProperties
    self.version = version

    # Copy passed lists (or set to empty lists)
    self.entries = list(entries or [])

    if variants:
      # Copy passed list
      self.variants = variants[:]
    else:
      # Use default
      self.variants = ['Debug|Win32', 'Release|Win32']
    # TODO(rspangler): Need to be able to handle a mapping of solution config
    # to project config.  Should we be able to handle variants being a dict,
    # or add a separate variant_map variable?  If it's a dict, we can't
    # guarantee the order of variants since dict keys aren't ordered.


    # TODO(rspangler): Automatically write to disk for now; should delay until
    # node-evaluation time.
    self.Write()


  def Write(self, writer=gyp.common.WriteOnDiff):
    """Writes the solution file to disk.

    Raises:
      IndexError: An entry appears multiple times.
    """
    # Walk the entry tree and collect all the folders and projects.
    all_entries = set()
    entries_to_check = self.entries[:]
    while entries_to_check:
      e = entries_to_check.pop(0)

      # If this entry has been visited, nothing to do.
      if e in all_entries:
        continue

      all_entries.add(e)

      # If this is a folder, check its entries too.
      if isinstance(e, MSVSFolder):
        entries_to_check += e.entries

    all_entries = sorted(all_entries)

    # Open file and print header
    f = writer(self.path)
    f.write('Microsoft Visual Studio Solution File, '
            'Format Version %s\r\n' % self.version.SolutionVersion())
    f.write('# %s\r\n' % self.version.Description())

    # Project entries
    sln_root = os.path.split(self.path)[0]
    for e in all_entries:
      relative_path = gyp.common.RelativePath(e.path, sln_root)
      # msbuild does not accept an empty folder_name.
      # use '.' in case relative_path is empty.
      folder_name = relative_path.replace('/', '\\') or '.'
      f.write('Project("%s") = "%s", "%s", "%s"\r\n' % (
          e.entry_type_guid,          # Entry type GUID
          e.name,                     # Folder name
          folder_name,                # Folder name (again)
          e.get_guid(),               # Entry GUID
      ))

      # TODO(rspangler): Need a way to configure this stuff
      if self.websiteProperties:
        f.write('\tProjectSection(WebsiteProperties) = preProject\r\n'
                '\t\tDebug.AspNetCompiler.Debug = "True"\r\n'
                '\t\tRelease.AspNetCompiler.Debug = "False"\r\n'
                '\tEndProjectSection\r\n')

      if isinstance(e, MSVSFolder):
        if e.items:
          f.write('\tProjectSection(SolutionItems) = preProject\r\n')
          for i in e.items:
            f.write('\t\t%s = %s\r\n' % (i, i))
          f.write('\tEndProjectSection\r\n')

      if isinstance(e, MSVSProject):
        if e.dependencies:
          f.write('\tProjectSection(ProjectDependencies) = postProject\r\n')
          for d in e.dependencies:
            f.write('\t\t%s = %s\r\n' % (d.get_guid(), d.get_guid()))
          f.write('\tEndProjectSection\r\n')

      f.write('EndProject\r\n')

    # Global section
    f.write('Global\r\n')

    # Configurations (variants)
    f.write('\tGlobalSection(SolutionConfigurationPlatforms) = preSolution\r\n')
    for v in self.variants:
      f.write('\t\t%s = %s\r\n' % (v, v))
    f.write('\tEndGlobalSection\r\n')

    # Sort config guids for easier diffing of solution changes.
    config_guids = []
    config_guids_overrides = {}
    for e in all_entries:
      if isinstance(e, MSVSProject):
        config_guids.append(e.get_guid())
        config_guids_overrides[e.get_guid()] = e.config_platform_overrides
    config_guids.sort()

    f.write('\tGlobalSection(ProjectConfigurationPlatforms) = postSolution\r\n')
    for g in config_guids:
      for v in self.variants:
        nv = config_guids_overrides[g].get(v, v)
        # Pick which project configuration to build for this solution
        # configuration.
        f.write('\t\t%s.%s.ActiveCfg = %s\r\n' % (
            g,              # Project GUID
            v,              # Solution build configuration
            nv,             # Project build config for that solution config
        ))

        # Enable project in this solution configuration.
        f.write('\t\t%s.%s.Build.0 = %s\r\n' % (
            g,              # Project GUID
            v,              # Solution build configuration
            nv,             # Project build config for that solution config
        ))
    f.write('\tEndGlobalSection\r\n')

    # TODO(rspangler): Should be able to configure this stuff too (though I've
    # never seen this be any different)
    f.write('\tGlobalSection(SolutionProperties) = preSolution\r\n')
    f.write('\t\tHideSolutionNode = FALSE\r\n')
    f.write('\tEndGlobalSection\r\n')

    # Folder mappings
    # TODO(rspangler): Should omit this section if there are no folders
    f.write('\tGlobalSection(NestedProjects) = preSolution\r\n')
    for e in all_entries:
      if not isinstance(e, MSVSFolder):
        continue        # Does not apply to projects, only folders
      for subentry in e.entries:
        f.write('\t\t%s = %s\r\n' % (subentry.get_guid(), e.get_guid()))
    f.write('\tEndGlobalSection\r\n')

    f.write('EndGlobal\r\n')

    f.close()

########NEW FILE########
__FILENAME__ = MSVSProject
# Copyright (c) 2012 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Visual Studio project reader/writer."""

import gyp.common
import gyp.easy_xml as easy_xml

#------------------------------------------------------------------------------


class Tool(object):
  """Visual Studio tool."""

  def __init__(self, name, attrs=None):
    """Initializes the tool.

    Args:
      name: Tool name.
      attrs: Dict of tool attributes; may be None.
    """
    self._attrs = attrs or {}
    self._attrs['Name'] = name

  def _GetSpecification(self):
    """Creates an element for the tool.

    Returns:
      A new xml.dom.Element for the tool.
    """
    return ['Tool', self._attrs]

class Filter(object):
  """Visual Studio filter - that is, a virtual folder."""

  def __init__(self, name, contents=None):
    """Initializes the folder.

    Args:
      name: Filter (folder) name.
      contents: List of filenames and/or Filter objects contained.
    """
    self.name = name
    self.contents = list(contents or [])


#------------------------------------------------------------------------------


class Writer(object):
  """Visual Studio XML project writer."""

  def __init__(self, project_path, version, name, guid=None, platforms=None):
    """Initializes the project.

    Args:
      project_path: Path to the project file.
      version: Format version to emit.
      name: Name of the project.
      guid: GUID to use for project, if not None.
      platforms: Array of string, the supported platforms.  If null, ['Win32']
    """
    self.project_path = project_path
    self.version = version
    self.name = name
    self.guid = guid

    # Default to Win32 for platforms.
    if not platforms:
      platforms = ['Win32']

    # Initialize the specifications of the various sections.
    self.platform_section = ['Platforms']
    for platform in platforms:
      self.platform_section.append(['Platform', {'Name': platform}])
    self.tool_files_section = ['ToolFiles']
    self.configurations_section = ['Configurations']
    self.files_section = ['Files']

    # Keep a dict keyed on filename to speed up access.
    self.files_dict = dict()

  def AddToolFile(self, path):
    """Adds a tool file to the project.

    Args:
      path: Relative path from project to tool file.
    """
    self.tool_files_section.append(['ToolFile', {'RelativePath': path}])

  def _GetSpecForConfiguration(self, config_type, config_name, attrs, tools):
    """Returns the specification for a configuration.

    Args:
      config_type: Type of configuration node.
      config_name: Configuration name.
      attrs: Dict of configuration attributes; may be None.
      tools: List of tools (strings or Tool objects); may be None.
    Returns:
    """
    # Handle defaults
    if not attrs:
      attrs = {}
    if not tools:
      tools = []

    # Add configuration node and its attributes
    node_attrs = attrs.copy()
    node_attrs['Name'] = config_name
    specification = [config_type, node_attrs]

    # Add tool nodes and their attributes
    if tools:
      for t in tools:
        if isinstance(t, Tool):
          specification.append(t._GetSpecification())
        else:
          specification.append(Tool(t)._GetSpecification())
    return specification


  def AddConfig(self, name, attrs=None, tools=None):
    """Adds a configuration to the project.

    Args:
      name: Configuration name.
      attrs: Dict of configuration attributes; may be None.
      tools: List of tools (strings or Tool objects); may be None.
    """
    spec = self._GetSpecForConfiguration('Configuration', name, attrs, tools)
    self.configurations_section.append(spec)

  def _AddFilesToNode(self, parent, files):
    """Adds files and/or filters to the parent node.

    Args:
      parent: Destination node
      files: A list of Filter objects and/or relative paths to files.

    Will call itself recursively, if the files list contains Filter objects.
    """
    for f in files:
      if isinstance(f, Filter):
        node = ['Filter', {'Name': f.name}]
        self._AddFilesToNode(node, f.contents)
      else:
        node = ['File', {'RelativePath': f}]
        self.files_dict[f] = node
      parent.append(node)

  def AddFiles(self, files):
    """Adds files to the project.

    Args:
      files: A list of Filter objects and/or relative paths to files.

    This makes a copy of the file/filter tree at the time of this call.  If you
    later add files to a Filter object which was passed into a previous call
    to AddFiles(), it will not be reflected in this project.
    """
    self._AddFilesToNode(self.files_section, files)
    # TODO(rspangler) This also doesn't handle adding files to an existing
    # filter.  That is, it doesn't merge the trees.

  def AddFileConfig(self, path, config, attrs=None, tools=None):
    """Adds a configuration to a file.

    Args:
      path: Relative path to the file.
      config: Name of configuration to add.
      attrs: Dict of configuration attributes; may be None.
      tools: List of tools (strings or Tool objects); may be None.

    Raises:
      ValueError: Relative path does not match any file added via AddFiles().
    """
    # Find the file node with the right relative path
    parent = self.files_dict.get(path)
    if not parent:
      raise ValueError('AddFileConfig: file "%s" not in project.' % path)

    # Add the config to the file node
    spec = self._GetSpecForConfiguration('FileConfiguration', config, attrs,
                                         tools)
    parent.append(spec)

  def WriteIfChanged(self):
    """Writes the project file."""
    # First create XML content definition
    content = [
        'VisualStudioProject',
        {'ProjectType': 'Visual C++',
         'Version': self.version.ProjectVersion(),
         'Name': self.name,
         'ProjectGUID': self.guid,
         'RootNamespace': self.name,
         'Keyword': 'Win32Proj'
        },
        self.platform_section,
        self.tool_files_section,
        self.configurations_section,
        ['References'],  # empty section
        self.files_section,
        ['Globals']  # empty section
    ]
    easy_xml.WriteXmlIfChanged(content, self.project_path,
                               encoding="Windows-1252")

########NEW FILE########
__FILENAME__ = MSVSSettings
# Copyright (c) 2012 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Code to validate and convert settings of the Microsoft build tools.

This file contains code to validate and convert settings of the Microsoft
build tools.  The function ConvertToMSBuildSettings(), ValidateMSVSSettings(),
and ValidateMSBuildSettings() are the entry points.

This file was created by comparing the projects created by Visual Studio 2008
and Visual Studio 2010 for all available settings through the user interface.
The MSBuild schemas were also considered.  They are typically found in the
MSBuild install directory, e.g. c:\Program Files (x86)\MSBuild
"""

import sys
import re

# Dictionaries of settings validators. The key is the tool name, the value is
# a dictionary mapping setting names to validation functions.
_msvs_validators = {}
_msbuild_validators = {}


# A dictionary of settings converters. The key is the tool name, the value is
# a dictionary mapping setting names to conversion functions.
_msvs_to_msbuild_converters = {}


# Tool name mapping from MSVS to MSBuild.
_msbuild_name_of_tool = {}


class _Tool(object):
  """Represents a tool used by MSVS or MSBuild.

  Attributes:
      msvs_name: The name of the tool in MSVS.
      msbuild_name: The name of the tool in MSBuild.
  """

  def __init__(self, msvs_name, msbuild_name):
    self.msvs_name = msvs_name
    self.msbuild_name = msbuild_name


def _AddTool(tool):
  """Adds a tool to the four dictionaries used to process settings.

  This only defines the tool.  Each setting also needs to be added.

  Args:
    tool: The _Tool object to be added.
  """
  _msvs_validators[tool.msvs_name] = {}
  _msbuild_validators[tool.msbuild_name] = {}
  _msvs_to_msbuild_converters[tool.msvs_name] = {}
  _msbuild_name_of_tool[tool.msvs_name] = tool.msbuild_name


def _GetMSBuildToolSettings(msbuild_settings, tool):
  """Returns an MSBuild tool dictionary.  Creates it if needed."""
  return msbuild_settings.setdefault(tool.msbuild_name, {})


class _Type(object):
  """Type of settings (Base class)."""

  def ValidateMSVS(self, value):
    """Verifies that the value is legal for MSVS.

    Args:
      value: the value to check for this type.

    Raises:
      ValueError if value is not valid for MSVS.
    """

  def ValidateMSBuild(self, value):
    """Verifies that the value is legal for MSBuild.

    Args:
      value: the value to check for this type.

    Raises:
      ValueError if value is not valid for MSBuild.
    """

  def ConvertToMSBuild(self, value):
    """Returns the MSBuild equivalent of the MSVS value given.

    Args:
      value: the MSVS value to convert.

    Returns:
      the MSBuild equivalent.

    Raises:
      ValueError if value is not valid.
    """
    return value


class _String(_Type):
  """A setting that's just a string."""

  def ValidateMSVS(self, value):
    if not isinstance(value, basestring):
      raise ValueError('expected string; got %r' % value)

  def ValidateMSBuild(self, value):
    if not isinstance(value, basestring):
      raise ValueError('expected string; got %r' % value)

  def ConvertToMSBuild(self, value):
    # Convert the macros
    return ConvertVCMacrosToMSBuild(value)


class _StringList(_Type):
  """A settings that's a list of strings."""

  def ValidateMSVS(self, value):
    if not isinstance(value, basestring) and not isinstance(value, list):
      raise ValueError('expected string list; got %r' % value)

  def ValidateMSBuild(self, value):
    if not isinstance(value, basestring) and not isinstance(value, list):
      raise ValueError('expected string list; got %r' % value)

  def ConvertToMSBuild(self, value):
    # Convert the macros
    if isinstance(value, list):
      return [ConvertVCMacrosToMSBuild(i) for i in value]
    else:
      return ConvertVCMacrosToMSBuild(value)


class _Boolean(_Type):
  """Boolean settings, can have the values 'false' or 'true'."""

  def _Validate(self, value):
    if value != 'true' and value != 'false':
      raise ValueError('expected bool; got %r' % value)

  def ValidateMSVS(self, value):
    self._Validate(value)

  def ValidateMSBuild(self, value):
    self._Validate(value)

  def ConvertToMSBuild(self, value):
    self._Validate(value)
    return value


class _Integer(_Type):
  """Integer settings."""

  def __init__(self, msbuild_base=10):
    _Type.__init__(self)
    self._msbuild_base = msbuild_base

  def ValidateMSVS(self, value):
    # Try to convert, this will raise ValueError if invalid.
    self.ConvertToMSBuild(value)

  def ValidateMSBuild(self, value):
    # Try to convert, this will raise ValueError if invalid.
    int(value, self._msbuild_base)

  def ConvertToMSBuild(self, value):
    msbuild_format = (self._msbuild_base == 10) and '%d' or '0x%04x'
    return msbuild_format % int(value)


class _Enumeration(_Type):
  """Type of settings that is an enumeration.

  In MSVS, the values are indexes like '0', '1', and '2'.
  MSBuild uses text labels that are more representative, like 'Win32'.

  Constructor args:
    label_list: an array of MSBuild labels that correspond to the MSVS index.
        In the rare cases where MSVS has skipped an index value, None is
        used in the array to indicate the unused spot.
    new: an array of labels that are new to MSBuild.
  """

  def __init__(self, label_list, new=None):
    _Type.__init__(self)
    self._label_list = label_list
    self._msbuild_values = set(value for value in label_list
                               if value is not None)
    if new is not None:
      self._msbuild_values.update(new)

  def ValidateMSVS(self, value):
    # Try to convert.  It will raise an exception if not valid.
    self.ConvertToMSBuild(value)

  def ValidateMSBuild(self, value):
    if value not in self._msbuild_values:
      raise ValueError('unrecognized enumerated value %s' % value)

  def ConvertToMSBuild(self, value):
    index = int(value)
    if index < 0 or index >= len(self._label_list):
      raise ValueError('index value (%d) not in expected range [0, %d)' %
                       (index, len(self._label_list)))
    label = self._label_list[index]
    if label is None:
      raise ValueError('converted value for %s not specified.' % value)
    return label


# Instantiate the various generic types.
_boolean = _Boolean()
_integer = _Integer()
# For now, we don't do any special validation on these types:
_string = _String()
_file_name = _String()
_folder_name = _String()
_file_list = _StringList()
_folder_list = _StringList()
_string_list = _StringList()
# Some boolean settings went from numerical values to boolean.  The
# mapping is 0: default, 1: false, 2: true.
_newly_boolean = _Enumeration(['', 'false', 'true'])


def _Same(tool, name, setting_type):
  """Defines a setting that has the same name in MSVS and MSBuild.

  Args:
    tool: a dictionary that gives the names of the tool for MSVS and MSBuild.
    name: the name of the setting.
    setting_type: the type of this setting.
  """
  _Renamed(tool, name, name, setting_type)


def _Renamed(tool, msvs_name, msbuild_name, setting_type):
  """Defines a setting for which the name has changed.

  Args:
    tool: a dictionary that gives the names of the tool for MSVS and MSBuild.
    msvs_name: the name of the MSVS setting.
    msbuild_name: the name of the MSBuild setting.
    setting_type: the type of this setting.
  """

  def _Translate(value, msbuild_settings):
    msbuild_tool_settings = _GetMSBuildToolSettings(msbuild_settings, tool)
    msbuild_tool_settings[msbuild_name] = setting_type.ConvertToMSBuild(value)

  _msvs_validators[tool.msvs_name][msvs_name] = setting_type.ValidateMSVS
  _msbuild_validators[tool.msbuild_name][msbuild_name] = (
      setting_type.ValidateMSBuild)
  _msvs_to_msbuild_converters[tool.msvs_name][msvs_name] = _Translate


def _Moved(tool, settings_name, msbuild_tool_name, setting_type):
  _MovedAndRenamed(tool, settings_name, msbuild_tool_name, settings_name,
                   setting_type)


def _MovedAndRenamed(tool, msvs_settings_name, msbuild_tool_name,
                     msbuild_settings_name, setting_type):
  """Defines a setting that may have moved to a new section.

  Args:
    tool: a dictionary that gives the names of the tool for MSVS and MSBuild.
    msvs_settings_name: the MSVS name of the setting.
    msbuild_tool_name: the name of the MSBuild tool to place the setting under.
    msbuild_settings_name: the MSBuild name of the setting.
    setting_type: the type of this setting.
  """

  def _Translate(value, msbuild_settings):
    tool_settings = msbuild_settings.setdefault(msbuild_tool_name, {})
    tool_settings[msbuild_settings_name] = setting_type.ConvertToMSBuild(value)

  _msvs_validators[tool.msvs_name][msvs_settings_name] = (
      setting_type.ValidateMSVS)
  validator = setting_type.ValidateMSBuild
  _msbuild_validators[msbuild_tool_name][msbuild_settings_name] = validator
  _msvs_to_msbuild_converters[tool.msvs_name][msvs_settings_name] = _Translate


def _MSVSOnly(tool, name, setting_type):
  """Defines a setting that is only found in MSVS.

  Args:
    tool: a dictionary that gives the names of the tool for MSVS and MSBuild.
    name: the name of the setting.
    setting_type: the type of this setting.
  """

  def _Translate(unused_value, unused_msbuild_settings):
    # Since this is for MSVS only settings, no translation will happen.
    pass

  _msvs_validators[tool.msvs_name][name] = setting_type.ValidateMSVS
  _msvs_to_msbuild_converters[tool.msvs_name][name] = _Translate


def _MSBuildOnly(tool, name, setting_type):
  """Defines a setting that is only found in MSBuild.

  Args:
    tool: a dictionary that gives the names of the tool for MSVS and MSBuild.
    name: the name of the setting.
    setting_type: the type of this setting.
  """
  _msbuild_validators[tool.msbuild_name][name] = setting_type.ValidateMSBuild


def _ConvertedToAdditionalOption(tool, msvs_name, flag):
  """Defines a setting that's handled via a command line option in MSBuild.

  Args:
    tool: a dictionary that gives the names of the tool for MSVS and MSBuild.
    msvs_name: the name of the MSVS setting that if 'true' becomes a flag
    flag: the flag to insert at the end of the AdditionalOptions
  """

  def _Translate(value, msbuild_settings):
    if value == 'true':
      tool_settings = _GetMSBuildToolSettings(msbuild_settings, tool)
      if 'AdditionalOptions' in tool_settings:
        new_flags = '%s %s' % (tool_settings['AdditionalOptions'], flag)
      else:
        new_flags = flag
      tool_settings['AdditionalOptions'] = new_flags
  _msvs_validators[tool.msvs_name][msvs_name] = _boolean.ValidateMSVS
  _msvs_to_msbuild_converters[tool.msvs_name][msvs_name] = _Translate


def _CustomGeneratePreprocessedFile(tool, msvs_name):
  def _Translate(value, msbuild_settings):
    tool_settings = _GetMSBuildToolSettings(msbuild_settings, tool)
    if value == '0':
      tool_settings['PreprocessToFile'] = 'false'
      tool_settings['PreprocessSuppressLineNumbers'] = 'false'
    elif value == '1':  # /P
      tool_settings['PreprocessToFile'] = 'true'
      tool_settings['PreprocessSuppressLineNumbers'] = 'false'
    elif value == '2':  # /EP /P
      tool_settings['PreprocessToFile'] = 'true'
      tool_settings['PreprocessSuppressLineNumbers'] = 'true'
    else:
      raise ValueError('value must be one of [0, 1, 2]; got %s' % value)
  # Create a bogus validator that looks for '0', '1', or '2'
  msvs_validator = _Enumeration(['a', 'b', 'c']).ValidateMSVS
  _msvs_validators[tool.msvs_name][msvs_name] = msvs_validator
  msbuild_validator = _boolean.ValidateMSBuild
  msbuild_tool_validators = _msbuild_validators[tool.msbuild_name]
  msbuild_tool_validators['PreprocessToFile'] = msbuild_validator
  msbuild_tool_validators['PreprocessSuppressLineNumbers'] = msbuild_validator
  _msvs_to_msbuild_converters[tool.msvs_name][msvs_name] = _Translate


fix_vc_macro_slashes_regex_list = ('IntDir', 'OutDir')
fix_vc_macro_slashes_regex = re.compile(
  r'(\$\((?:%s)\))(?:[\\/]+)' % "|".join(fix_vc_macro_slashes_regex_list)
)

def FixVCMacroSlashes(s):
  """Replace macros which have excessive following slashes.

  These macros are known to have a built-in trailing slash. Furthermore, many
  scripts hiccup on processing paths with extra slashes in the middle.

  This list is probably not exhaustive.  Add as needed.
  """
  if '$' in s:
    s = fix_vc_macro_slashes_regex.sub(r'\1', s)
  return s


def ConvertVCMacrosToMSBuild(s):
  """Convert the the MSVS macros found in the string to the MSBuild equivalent.

  This list is probably not exhaustive.  Add as needed.
  """
  if '$' in s:
    replace_map = {
        '$(ConfigurationName)': '$(Configuration)',
        '$(InputDir)': '%(RootDir)%(Directory)',
        '$(InputExt)': '%(Extension)',
        '$(InputFileName)': '%(Filename)%(Extension)',
        '$(InputName)': '%(Filename)',
        '$(InputPath)': '%(FullPath)',
        '$(ParentName)': '$(ProjectFileName)',
        '$(PlatformName)': '$(Platform)',
        '$(SafeInputName)': '%(Filename)',
    }
    for old, new in replace_map.iteritems():
      s = s.replace(old, new)
    s = FixVCMacroSlashes(s)
  return s


def ConvertToMSBuildSettings(msvs_settings, stderr=sys.stderr):
  """Converts MSVS settings (VS2008 and earlier) to MSBuild settings (VS2010+).

  Args:
      msvs_settings: A dictionary.  The key is the tool name.  The values are
          themselves dictionaries of settings and their values.
      stderr: The stream receiving the error messages.

  Returns:
      A dictionary of MSBuild settings.  The key is either the MSBuild tool name
      or the empty string (for the global settings).  The values are themselves
      dictionaries of settings and their values.
  """
  msbuild_settings = {}
  for msvs_tool_name, msvs_tool_settings in msvs_settings.iteritems():
    if msvs_tool_name in _msvs_to_msbuild_converters:
      msvs_tool = _msvs_to_msbuild_converters[msvs_tool_name]
      for msvs_setting, msvs_value in msvs_tool_settings.iteritems():
        if msvs_setting in msvs_tool:
          # Invoke the translation function.
          try:
            msvs_tool[msvs_setting](msvs_value, msbuild_settings)
          except ValueError, e:
            print >> stderr, ('Warning: while converting %s/%s to MSBuild, '
                              '%s' % (msvs_tool_name, msvs_setting, e))
        else:
          # We don't know this setting.  Give a warning.
          print >> stderr, ('Warning: unrecognized setting %s/%s '
                            'while converting to MSBuild.' %
                            (msvs_tool_name, msvs_setting))
    else:
      print >> stderr, ('Warning: unrecognized tool %s while converting to '
                        'MSBuild.' % msvs_tool_name)
  return msbuild_settings


def ValidateMSVSSettings(settings, stderr=sys.stderr):
  """Validates that the names of the settings are valid for MSVS.

  Args:
      settings: A dictionary.  The key is the tool name.  The values are
          themselves dictionaries of settings and their values.
      stderr: The stream receiving the error messages.
  """
  _ValidateSettings(_msvs_validators, settings, stderr)


def ValidateMSBuildSettings(settings, stderr=sys.stderr):
  """Validates that the names of the settings are valid for MSBuild.

  Args:
      settings: A dictionary.  The key is the tool name.  The values are
          themselves dictionaries of settings and their values.
      stderr: The stream receiving the error messages.
  """
  _ValidateSettings(_msbuild_validators, settings, stderr)


def _ValidateSettings(validators, settings, stderr):
  """Validates that the settings are valid for MSBuild or MSVS.

  We currently only validate the names of the settings, not their values.

  Args:
      validators: A dictionary of tools and their validators.
      settings: A dictionary.  The key is the tool name.  The values are
          themselves dictionaries of settings and their values.
      stderr: The stream receiving the error messages.
  """
  for tool_name in settings:
    if tool_name in validators:
      tool_validators = validators[tool_name]
      for setting, value in settings[tool_name].iteritems():
        if setting in tool_validators:
          try:
            tool_validators[setting](value)
          except ValueError, e:
            print >> stderr, ('Warning: for %s/%s, %s' %
                              (tool_name, setting, e))
        else:
          print >> stderr, ('Warning: unrecognized setting %s/%s' %
                            (tool_name, setting))
    else:
      print >> stderr, ('Warning: unrecognized tool %s' % tool_name)


# MSVS and MBuild names of the tools.
_compile = _Tool('VCCLCompilerTool', 'ClCompile')
_link = _Tool('VCLinkerTool', 'Link')
_midl = _Tool('VCMIDLTool', 'Midl')
_rc = _Tool('VCResourceCompilerTool', 'ResourceCompile')
_lib = _Tool('VCLibrarianTool', 'Lib')
_manifest = _Tool('VCManifestTool', 'Manifest')


_AddTool(_compile)
_AddTool(_link)
_AddTool(_midl)
_AddTool(_rc)
_AddTool(_lib)
_AddTool(_manifest)
# Add sections only found in the MSBuild settings.
_msbuild_validators[''] = {}
_msbuild_validators['ProjectReference'] = {}
_msbuild_validators['ManifestResourceCompile'] = {}

# Descriptions of the compiler options, i.e. VCCLCompilerTool in MSVS and
# ClCompile in MSBuild.
# See "c:\Program Files (x86)\MSBuild\Microsoft.Cpp\v4.0\1033\cl.xml" for
# the schema of the MSBuild ClCompile settings.

# Options that have the same name in MSVS and MSBuild
_Same(_compile, 'AdditionalIncludeDirectories', _folder_list)  # /I
_Same(_compile, 'AdditionalOptions', _string_list)
_Same(_compile, 'AdditionalUsingDirectories', _folder_list)  # /AI
_Same(_compile, 'AssemblerListingLocation', _file_name)  # /Fa
_Same(_compile, 'BrowseInformationFile', _file_name)
_Same(_compile, 'BufferSecurityCheck', _boolean)  # /GS
_Same(_compile, 'DisableLanguageExtensions', _boolean)  # /Za
_Same(_compile, 'DisableSpecificWarnings', _string_list)  # /wd
_Same(_compile, 'EnableFiberSafeOptimizations', _boolean)  # /GT
_Same(_compile, 'EnablePREfast', _boolean)  # /analyze Visible='false'
_Same(_compile, 'ExpandAttributedSource', _boolean)  # /Fx
_Same(_compile, 'FloatingPointExceptions', _boolean)  # /fp:except
_Same(_compile, 'ForceConformanceInForLoopScope', _boolean)  # /Zc:forScope
_Same(_compile, 'ForcedIncludeFiles', _file_list)  # /FI
_Same(_compile, 'ForcedUsingFiles', _file_list)  # /FU
_Same(_compile, 'GenerateXMLDocumentationFiles', _boolean)  # /doc
_Same(_compile, 'IgnoreStandardIncludePath', _boolean)  # /X
_Same(_compile, 'MinimalRebuild', _boolean)  # /Gm
_Same(_compile, 'OmitDefaultLibName', _boolean)  # /Zl
_Same(_compile, 'OmitFramePointers', _boolean)  # /Oy
_Same(_compile, 'PreprocessorDefinitions', _string_list)  # /D
_Same(_compile, 'ProgramDataBaseFileName', _file_name)  # /Fd
_Same(_compile, 'RuntimeTypeInfo', _boolean)  # /GR
_Same(_compile, 'ShowIncludes', _boolean)  # /showIncludes
_Same(_compile, 'SmallerTypeCheck', _boolean)  # /RTCc
_Same(_compile, 'StringPooling', _boolean)  # /GF
_Same(_compile, 'SuppressStartupBanner', _boolean)  # /nologo
_Same(_compile, 'TreatWChar_tAsBuiltInType', _boolean)  # /Zc:wchar_t
_Same(_compile, 'UndefineAllPreprocessorDefinitions', _boolean)  # /u
_Same(_compile, 'UndefinePreprocessorDefinitions', _string_list)  # /U
_Same(_compile, 'UseFullPaths', _boolean)  # /FC
_Same(_compile, 'WholeProgramOptimization', _boolean)  # /GL
_Same(_compile, 'XMLDocumentationFileName', _file_name)

_Same(_compile, 'AssemblerOutput',
      _Enumeration(['NoListing',
                    'AssemblyCode',  # /FA
                    'All',  # /FAcs
                    'AssemblyAndMachineCode',  # /FAc
                    'AssemblyAndSourceCode']))  # /FAs
_Same(_compile, 'BasicRuntimeChecks',
      _Enumeration(['Default',
                    'StackFrameRuntimeCheck',  # /RTCs
                    'UninitializedLocalUsageCheck',  # /RTCu
                    'EnableFastChecks']))  # /RTC1
_Same(_compile, 'BrowseInformation',
      _Enumeration(['false',
                    'true',  # /FR
                    'true']))  # /Fr
_Same(_compile, 'CallingConvention',
      _Enumeration(['Cdecl',  # /Gd
                    'FastCall',  # /Gr
                    'StdCall']))  # /Gz
_Same(_compile, 'CompileAs',
      _Enumeration(['Default',
                    'CompileAsC',  # /TC
                    'CompileAsCpp']))  # /TP
_Same(_compile, 'DebugInformationFormat',
      _Enumeration(['',  # Disabled
                    'OldStyle',  # /Z7
                    None,
                    'ProgramDatabase',  # /Zi
                    'EditAndContinue']))  # /ZI
_Same(_compile, 'EnableEnhancedInstructionSet',
      _Enumeration(['NotSet',
                    'StreamingSIMDExtensions',  # /arch:SSE
                    'StreamingSIMDExtensions2']))  # /arch:SSE2
_Same(_compile, 'ErrorReporting',
      _Enumeration(['None',  # /errorReport:none
                    'Prompt',  # /errorReport:prompt
                    'Queue'],  # /errorReport:queue
                   new=['Send']))  # /errorReport:send"
_Same(_compile, 'ExceptionHandling',
      _Enumeration(['false',
                    'Sync',  # /EHsc
                    'Async'],  # /EHa
                   new=['SyncCThrow']))  # /EHs
_Same(_compile, 'FavorSizeOrSpeed',
      _Enumeration(['Neither',
                    'Speed',  # /Ot
                    'Size']))  # /Os
_Same(_compile, 'FloatingPointModel',
      _Enumeration(['Precise',  # /fp:precise
                    'Strict',  # /fp:strict
                    'Fast']))  # /fp:fast
_Same(_compile, 'InlineFunctionExpansion',
      _Enumeration(['Default',
                    'OnlyExplicitInline',  # /Ob1
                    'AnySuitable'],  # /Ob2
                   new=['Disabled']))  # /Ob0
_Same(_compile, 'Optimization',
      _Enumeration(['Disabled',  # /Od
                    'MinSpace',  # /O1
                    'MaxSpeed',  # /O2
                    'Full']))  # /Ox
_Same(_compile, 'RuntimeLibrary',
      _Enumeration(['MultiThreaded',  # /MT
                    'MultiThreadedDebug',  # /MTd
                    'MultiThreadedDLL',  # /MD
                    'MultiThreadedDebugDLL']))  # /MDd
_Same(_compile, 'StructMemberAlignment',
      _Enumeration(['Default',
                    '1Byte',  # /Zp1
                    '2Bytes',  # /Zp2
                    '4Bytes',  # /Zp4
                    '8Bytes',  # /Zp8
                    '16Bytes']))  # /Zp16
_Same(_compile, 'WarningLevel',
      _Enumeration(['TurnOffAllWarnings',  # /W0
                    'Level1',  # /W1
                    'Level2',  # /W2
                    'Level3',  # /W3
                    'Level4'],  # /W4
                   new=['EnableAllWarnings']))  # /Wall

# Options found in MSVS that have been renamed in MSBuild.
_Renamed(_compile, 'EnableFunctionLevelLinking', 'FunctionLevelLinking',
         _boolean)  # /Gy
_Renamed(_compile, 'EnableIntrinsicFunctions', 'IntrinsicFunctions',
         _boolean)  # /Oi
_Renamed(_compile, 'KeepComments', 'PreprocessKeepComments', _boolean)  # /C
_Renamed(_compile, 'ObjectFile', 'ObjectFileName', _file_name)  # /Fo
_Renamed(_compile, 'OpenMP', 'OpenMPSupport', _boolean)  # /openmp
_Renamed(_compile, 'PrecompiledHeaderThrough', 'PrecompiledHeaderFile',
         _file_name)  # Used with /Yc and /Yu
_Renamed(_compile, 'PrecompiledHeaderFile', 'PrecompiledHeaderOutputFile',
         _file_name)  # /Fp
_Renamed(_compile, 'UsePrecompiledHeader', 'PrecompiledHeader',
         _Enumeration(['NotUsing',  # VS recognized '' for this value too.
                       'Create',   # /Yc
                       'Use']))  # /Yu
_Renamed(_compile, 'WarnAsError', 'TreatWarningAsError', _boolean)  # /WX

_ConvertedToAdditionalOption(_compile, 'DefaultCharIsUnsigned', '/J')

# MSVS options not found in MSBuild.
_MSVSOnly(_compile, 'Detect64BitPortabilityProblems', _boolean)
_MSVSOnly(_compile, 'UseUnicodeResponseFiles', _boolean)

# MSBuild options not found in MSVS.
_MSBuildOnly(_compile, 'BuildingInIDE', _boolean)
_MSBuildOnly(_compile, 'CompileAsManaged',
             _Enumeration([], new=['false',
                                   'true',  # /clr
                                   'Pure',  # /clr:pure
                                   'Safe',  # /clr:safe
                                   'OldSyntax']))  # /clr:oldSyntax
_MSBuildOnly(_compile, 'CreateHotpatchableImage', _boolean)  # /hotpatch
_MSBuildOnly(_compile, 'MultiProcessorCompilation', _boolean)  # /MP
_MSBuildOnly(_compile, 'PreprocessOutputPath', _string)  # /Fi
_MSBuildOnly(_compile, 'ProcessorNumber', _integer)  # the number of processors
_MSBuildOnly(_compile, 'TrackerLogDirectory', _folder_name)
_MSBuildOnly(_compile, 'TreatSpecificWarningsAsErrors', _string_list)  # /we
_MSBuildOnly(_compile, 'UseUnicodeForAssemblerListing', _boolean)  # /FAu

# Defines a setting that needs very customized processing
_CustomGeneratePreprocessedFile(_compile, 'GeneratePreprocessedFile')


# Directives for converting MSVS VCLinkerTool to MSBuild Link.
# See "c:\Program Files (x86)\MSBuild\Microsoft.Cpp\v4.0\1033\link.xml" for
# the schema of the MSBuild Link settings.

# Options that have the same name in MSVS and MSBuild
_Same(_link, 'AdditionalDependencies', _file_list)
_Same(_link, 'AdditionalLibraryDirectories', _folder_list)  # /LIBPATH
#  /MANIFESTDEPENDENCY:
_Same(_link, 'AdditionalManifestDependencies', _file_list)
_Same(_link, 'AdditionalOptions', _string_list)
_Same(_link, 'AddModuleNamesToAssembly', _file_list)  # /ASSEMBLYMODULE
_Same(_link, 'AllowIsolation', _boolean)  # /ALLOWISOLATION
_Same(_link, 'AssemblyLinkResource', _file_list)  # /ASSEMBLYLINKRESOURCE
_Same(_link, 'BaseAddress', _string)  # /BASE
_Same(_link, 'CLRUnmanagedCodeCheck', _boolean)  # /CLRUNMANAGEDCODECHECK
_Same(_link, 'DelayLoadDLLs', _file_list)  # /DELAYLOAD
_Same(_link, 'DelaySign', _boolean)  # /DELAYSIGN
_Same(_link, 'EmbedManagedResourceFile', _file_list)  # /ASSEMBLYRESOURCE
_Same(_link, 'EnableUAC', _boolean)  # /MANIFESTUAC
_Same(_link, 'EntryPointSymbol', _string)  # /ENTRY
_Same(_link, 'ForceSymbolReferences', _file_list)  # /INCLUDE
_Same(_link, 'FunctionOrder', _file_name)  # /ORDER
_Same(_link, 'GenerateDebugInformation', _boolean)  # /DEBUG
_Same(_link, 'GenerateMapFile', _boolean)  # /MAP
_Same(_link, 'HeapCommitSize', _string)
_Same(_link, 'HeapReserveSize', _string)  # /HEAP
_Same(_link, 'IgnoreAllDefaultLibraries', _boolean)  # /NODEFAULTLIB
_Same(_link, 'IgnoreEmbeddedIDL', _boolean)  # /IGNOREIDL
_Same(_link, 'ImportLibrary', _file_name)  # /IMPLIB
_Same(_link, 'KeyContainer', _file_name)  # /KEYCONTAINER
_Same(_link, 'KeyFile', _file_name)  # /KEYFILE
_Same(_link, 'ManifestFile', _file_name)  # /ManifestFile
_Same(_link, 'MapExports', _boolean)  # /MAPINFO:EXPORTS
_Same(_link, 'MapFileName', _file_name)
_Same(_link, 'MergedIDLBaseFileName', _file_name)  # /IDLOUT
_Same(_link, 'MergeSections', _string)  # /MERGE
_Same(_link, 'MidlCommandFile', _file_name)  # /MIDL
_Same(_link, 'ModuleDefinitionFile', _file_name)  # /DEF
_Same(_link, 'OutputFile', _file_name)  # /OUT
_Same(_link, 'PerUserRedirection', _boolean)
_Same(_link, 'Profile', _boolean)  # /PROFILE
_Same(_link, 'ProfileGuidedDatabase', _file_name)  # /PGD
_Same(_link, 'ProgramDatabaseFile', _file_name)  # /PDB
_Same(_link, 'RegisterOutput', _boolean)
_Same(_link, 'SetChecksum', _boolean)  # /RELEASE
_Same(_link, 'StackCommitSize', _string)
_Same(_link, 'StackReserveSize', _string)  # /STACK
_Same(_link, 'StripPrivateSymbols', _file_name)  # /PDBSTRIPPED
_Same(_link, 'SupportUnloadOfDelayLoadedDLL', _boolean)  # /DELAY:UNLOAD
_Same(_link, 'SuppressStartupBanner', _boolean)  # /NOLOGO
_Same(_link, 'SwapRunFromCD', _boolean)  # /SWAPRUN:CD
_Same(_link, 'TurnOffAssemblyGeneration', _boolean)  # /NOASSEMBLY
_Same(_link, 'TypeLibraryFile', _file_name)  # /TLBOUT
_Same(_link, 'TypeLibraryResourceID', _integer)  # /TLBID
_Same(_link, 'UACUIAccess', _boolean)  # /uiAccess='true'
_Same(_link, 'Version', _string)  # /VERSION

_Same(_link, 'EnableCOMDATFolding', _newly_boolean)  # /OPT:ICF
_Same(_link, 'FixedBaseAddress', _newly_boolean)  # /FIXED
_Same(_link, 'LargeAddressAware', _newly_boolean)  # /LARGEADDRESSAWARE
_Same(_link, 'OptimizeReferences', _newly_boolean)  # /OPT:REF
_Same(_link, 'RandomizedBaseAddress', _newly_boolean)  # /DYNAMICBASE
_Same(_link, 'TerminalServerAware', _newly_boolean)  # /TSAWARE

_subsystem_enumeration = _Enumeration(
    ['NotSet',
     'Console',  # /SUBSYSTEM:CONSOLE
     'Windows',  # /SUBSYSTEM:WINDOWS
     'Native',  # /SUBSYSTEM:NATIVE
     'EFI Application',  # /SUBSYSTEM:EFI_APPLICATION
     'EFI Boot Service Driver',  # /SUBSYSTEM:EFI_BOOT_SERVICE_DRIVER
     'EFI ROM',  # /SUBSYSTEM:EFI_ROM
     'EFI Runtime',  # /SUBSYSTEM:EFI_RUNTIME_DRIVER
     'WindowsCE'],  # /SUBSYSTEM:WINDOWSCE
    new=['POSIX'])  # /SUBSYSTEM:POSIX

_target_machine_enumeration = _Enumeration(
    ['NotSet',
     'MachineX86',  # /MACHINE:X86
     None,
     'MachineARM',  # /MACHINE:ARM
     'MachineEBC',  # /MACHINE:EBC
     'MachineIA64',  # /MACHINE:IA64
     None,
     'MachineMIPS',  # /MACHINE:MIPS
     'MachineMIPS16',  # /MACHINE:MIPS16
     'MachineMIPSFPU',  # /MACHINE:MIPSFPU
     'MachineMIPSFPU16',  # /MACHINE:MIPSFPU16
     None,
     None,
     None,
     'MachineSH4',  # /MACHINE:SH4
     None,
     'MachineTHUMB',  # /MACHINE:THUMB
     'MachineX64'])  # /MACHINE:X64

_Same(_link, 'AssemblyDebug',
      _Enumeration(['',
                    'true',  # /ASSEMBLYDEBUG
                    'false']))  # /ASSEMBLYDEBUG:DISABLE
_Same(_link, 'CLRImageType',
      _Enumeration(['Default',
                    'ForceIJWImage',  # /CLRIMAGETYPE:IJW
                    'ForcePureILImage',  # /Switch="CLRIMAGETYPE:PURE
                    'ForceSafeILImage']))  # /Switch="CLRIMAGETYPE:SAFE
_Same(_link, 'CLRThreadAttribute',
      _Enumeration(['DefaultThreadingAttribute',  # /CLRTHREADATTRIBUTE:NONE
                    'MTAThreadingAttribute',  # /CLRTHREADATTRIBUTE:MTA
                    'STAThreadingAttribute']))  # /CLRTHREADATTRIBUTE:STA
_Same(_link, 'DataExecutionPrevention',
      _Enumeration(['',
                    'false',  # /NXCOMPAT:NO
                    'true']))  # /NXCOMPAT
_Same(_link, 'Driver',
      _Enumeration(['NotSet',
                    'Driver',  # /Driver
                    'UpOnly',  # /DRIVER:UPONLY
                    'WDM']))  # /DRIVER:WDM
_Same(_link, 'LinkTimeCodeGeneration',
      _Enumeration(['Default',
                    'UseLinkTimeCodeGeneration',  # /LTCG
                    'PGInstrument',  # /LTCG:PGInstrument
                    'PGOptimization',  # /LTCG:PGOptimize
                    'PGUpdate']))  # /LTCG:PGUpdate
_Same(_link, 'ShowProgress',
      _Enumeration(['NotSet',
                    'LinkVerbose',  # /VERBOSE
                    'LinkVerboseLib'],  # /VERBOSE:Lib
                   new=['LinkVerboseICF',  # /VERBOSE:ICF
                        'LinkVerboseREF',  # /VERBOSE:REF
                        'LinkVerboseSAFESEH',  # /VERBOSE:SAFESEH
                        'LinkVerboseCLR']))  # /VERBOSE:CLR
_Same(_link, 'SubSystem', _subsystem_enumeration)
_Same(_link, 'TargetMachine', _target_machine_enumeration)
_Same(_link, 'UACExecutionLevel',
      _Enumeration(['AsInvoker',  # /level='asInvoker'
                    'HighestAvailable',  # /level='highestAvailable'
                    'RequireAdministrator']))  # /level='requireAdministrator'


# Options found in MSVS that have been renamed in MSBuild.
_Renamed(_link, 'ErrorReporting', 'LinkErrorReporting',
         _Enumeration(['NoErrorReport',  # /ERRORREPORT:NONE
                       'PromptImmediately',  # /ERRORREPORT:PROMPT
                       'QueueForNextLogin'],  # /ERRORREPORT:QUEUE
                      new=['SendErrorReport']))  # /ERRORREPORT:SEND
_Renamed(_link, 'IgnoreDefaultLibraryNames', 'IgnoreSpecificDefaultLibraries',
         _file_list)  # /NODEFAULTLIB
_Renamed(_link, 'ResourceOnlyDLL', 'NoEntryPoint', _boolean)  # /NOENTRY
_Renamed(_link, 'SwapRunFromNet', 'SwapRunFromNET', _boolean)  # /SWAPRUN:NET

_Moved(_link, 'GenerateManifest', '', _boolean)
_Moved(_link, 'IgnoreImportLibrary', '', _boolean)
_Moved(_link, 'LinkIncremental', '', _newly_boolean)
_Moved(_link, 'LinkLibraryDependencies', 'ProjectReference', _boolean)
_Moved(_link, 'UseLibraryDependencyInputs', 'ProjectReference', _boolean)

# MSVS options not found in MSBuild.
_MSVSOnly(_link, 'OptimizeForWindows98', _newly_boolean)
_MSVSOnly(_link, 'UseUnicodeResponseFiles', _boolean)
# TODO(jeanluc) I don't think these are genuine settings but byproducts of Gyp.
_MSVSOnly(_link, 'AdditionalLibraryDirectories_excluded', _folder_list)

# MSBuild options not found in MSVS.
_MSBuildOnly(_link, 'BuildingInIDE', _boolean)
_MSBuildOnly(_link, 'ImageHasSafeExceptionHandlers', _boolean)  # /SAFESEH
_MSBuildOnly(_link, 'LinkDLL', _boolean)  # /DLL Visible='false'
_MSBuildOnly(_link, 'LinkStatus', _boolean)  # /LTCG:STATUS
_MSBuildOnly(_link, 'PreventDllBinding', _boolean)  # /ALLOWBIND
_MSBuildOnly(_link, 'SupportNobindOfDelayLoadedDLL', _boolean)  # /DELAY:NOBIND
_MSBuildOnly(_link, 'TrackerLogDirectory', _folder_name)
_MSBuildOnly(_link, 'TreatLinkerWarningAsErrors', _boolean)  # /WX
_MSBuildOnly(_link, 'MinimumRequiredVersion', _string)
_MSBuildOnly(_link, 'MSDOSStubFileName', _file_name)  # /STUB Visible='false'
_MSBuildOnly(_link, 'SectionAlignment', _integer)  # /ALIGN
_MSBuildOnly(_link, 'SpecifySectionAttributes', _string)  # /SECTION
_MSBuildOnly(_link, 'ForceFileOutput',
             _Enumeration([], new=['Enabled',  # /FORCE
                                   # /FORCE:MULTIPLE
                                   'MultiplyDefinedSymbolOnly',
                                   'UndefinedSymbolOnly']))  # /FORCE:UNRESOLVED
_MSBuildOnly(_link, 'CreateHotPatchableImage',
             _Enumeration([], new=['Enabled',  # /FUNCTIONPADMIN
                                   'X86Image',  # /FUNCTIONPADMIN:5
                                   'X64Image',  # /FUNCTIONPADMIN:6
                                   'ItaniumImage']))  # /FUNCTIONPADMIN:16
_MSBuildOnly(_link, 'CLRSupportLastError',
             _Enumeration([], new=['Enabled',  # /CLRSupportLastError
                                   'Disabled',  # /CLRSupportLastError:NO
                                   # /CLRSupportLastError:SYSTEMDLL
                                   'SystemDlls']))


# Directives for converting VCResourceCompilerTool to ResourceCompile.
# See "c:\Program Files (x86)\MSBuild\Microsoft.Cpp\v4.0\1033\rc.xml" for
# the schema of the MSBuild ResourceCompile settings.

_Same(_rc, 'AdditionalOptions', _string_list)
_Same(_rc, 'AdditionalIncludeDirectories', _folder_list)  # /I
_Same(_rc, 'Culture', _Integer(msbuild_base=16))
_Same(_rc, 'IgnoreStandardIncludePath', _boolean)  # /X
_Same(_rc, 'PreprocessorDefinitions', _string_list)  # /D
_Same(_rc, 'ResourceOutputFileName', _string)  # /fo
_Same(_rc, 'ShowProgress', _boolean)  # /v
# There is no UI in VisualStudio 2008 to set the following properties.
# However they are found in CL and other tools.  Include them here for
# completeness, as they are very likely to have the same usage pattern.
_Same(_rc, 'SuppressStartupBanner', _boolean)  # /nologo
_Same(_rc, 'UndefinePreprocessorDefinitions', _string_list)  # /u

# MSBuild options not found in MSVS.
_MSBuildOnly(_rc, 'NullTerminateStrings', _boolean)  # /n
_MSBuildOnly(_rc, 'TrackerLogDirectory', _folder_name)


# Directives for converting VCMIDLTool to Midl.
# See "c:\Program Files (x86)\MSBuild\Microsoft.Cpp\v4.0\1033\midl.xml" for
# the schema of the MSBuild Midl settings.

_Same(_midl, 'AdditionalIncludeDirectories', _folder_list)  # /I
_Same(_midl, 'AdditionalOptions', _string_list)
_Same(_midl, 'CPreprocessOptions', _string)  # /cpp_opt
_Same(_midl, 'ErrorCheckAllocations', _boolean)  # /error allocation
_Same(_midl, 'ErrorCheckBounds', _boolean)  # /error bounds_check
_Same(_midl, 'ErrorCheckEnumRange', _boolean)  # /error enum
_Same(_midl, 'ErrorCheckRefPointers', _boolean)  # /error ref
_Same(_midl, 'ErrorCheckStubData', _boolean)  # /error stub_data
_Same(_midl, 'GenerateStublessProxies', _boolean)  # /Oicf
_Same(_midl, 'GenerateTypeLibrary', _boolean)
_Same(_midl, 'HeaderFileName', _file_name)  # /h
_Same(_midl, 'IgnoreStandardIncludePath', _boolean)  # /no_def_idir
_Same(_midl, 'InterfaceIdentifierFileName', _file_name)  # /iid
_Same(_midl, 'MkTypLibCompatible', _boolean)  # /mktyplib203
_Same(_midl, 'OutputDirectory', _string)  # /out
_Same(_midl, 'PreprocessorDefinitions', _string_list)  # /D
_Same(_midl, 'ProxyFileName', _file_name)  # /proxy
_Same(_midl, 'RedirectOutputAndErrors', _file_name)  # /o
_Same(_midl, 'SuppressStartupBanner', _boolean)  # /nologo
_Same(_midl, 'TypeLibraryName', _file_name)  # /tlb
_Same(_midl, 'UndefinePreprocessorDefinitions', _string_list)  # /U
_Same(_midl, 'WarnAsError', _boolean)  # /WX

_Same(_midl, 'DefaultCharType',
      _Enumeration(['Unsigned',  # /char unsigned
                    'Signed',  # /char signed
                    'Ascii']))  # /char ascii7
_Same(_midl, 'TargetEnvironment',
      _Enumeration(['NotSet',
                    'Win32',  # /env win32
                    'Itanium',  # /env ia64
                    'X64']))  # /env x64
_Same(_midl, 'EnableErrorChecks',
      _Enumeration(['EnableCustom',
                    'None',  # /error none
                    'All']))  # /error all
_Same(_midl, 'StructMemberAlignment',
      _Enumeration(['NotSet',
                    '1',  # Zp1
                    '2',  # Zp2
                    '4',  # Zp4
                    '8']))  # Zp8
_Same(_midl, 'WarningLevel',
      _Enumeration(['0',  # /W0
                    '1',  # /W1
                    '2',  # /W2
                    '3',  # /W3
                    '4']))  # /W4

_Renamed(_midl, 'DLLDataFileName', 'DllDataFileName', _file_name)  # /dlldata
_Renamed(_midl, 'ValidateParameters', 'ValidateAllParameters',
         _boolean)  # /robust

# MSBuild options not found in MSVS.
_MSBuildOnly(_midl, 'ApplicationConfigurationMode', _boolean)  # /app_config
_MSBuildOnly(_midl, 'ClientStubFile', _file_name)  # /cstub
_MSBuildOnly(_midl, 'GenerateClientFiles',
             _Enumeration([], new=['Stub',  # /client stub
                                   'None']))  # /client none
_MSBuildOnly(_midl, 'GenerateServerFiles',
             _Enumeration([], new=['Stub',  # /client stub
                                   'None']))  # /client none
_MSBuildOnly(_midl, 'LocaleID', _integer)  # /lcid DECIMAL
_MSBuildOnly(_midl, 'ServerStubFile', _file_name)  # /sstub
_MSBuildOnly(_midl, 'SuppressCompilerWarnings', _boolean)  # /no_warn
_MSBuildOnly(_midl, 'TrackerLogDirectory', _folder_name)
_MSBuildOnly(_midl, 'TypeLibFormat',
             _Enumeration([], new=['NewFormat',  # /newtlb
                                   'OldFormat']))  # /oldtlb


# Directives for converting VCLibrarianTool to Lib.
# See "c:\Program Files (x86)\MSBuild\Microsoft.Cpp\v4.0\1033\lib.xml" for
# the schema of the MSBuild Lib settings.

_Same(_lib, 'AdditionalDependencies', _file_list)
_Same(_lib, 'AdditionalLibraryDirectories', _folder_list)  # /LIBPATH
_Same(_lib, 'AdditionalOptions', _string_list)
_Same(_lib, 'ExportNamedFunctions', _string_list)  # /EXPORT
_Same(_lib, 'ForceSymbolReferences', _string)  # /INCLUDE
_Same(_lib, 'IgnoreAllDefaultLibraries', _boolean)  # /NODEFAULTLIB
_Same(_lib, 'IgnoreSpecificDefaultLibraries', _file_list)  # /NODEFAULTLIB
_Same(_lib, 'ModuleDefinitionFile', _file_name)  # /DEF
_Same(_lib, 'OutputFile', _file_name)  # /OUT
_Same(_lib, 'SuppressStartupBanner', _boolean)  # /NOLOGO
_Same(_lib, 'UseUnicodeResponseFiles', _boolean)
_Same(_lib, 'LinkTimeCodeGeneration', _boolean)  # /LTCG

# TODO(jeanluc) _link defines the same value that gets moved to
# ProjectReference.  We may want to validate that they are consistent.
_Moved(_lib, 'LinkLibraryDependencies', 'ProjectReference', _boolean)

# TODO(jeanluc) I don't think these are genuine settings but byproducts of Gyp.
_MSVSOnly(_lib, 'AdditionalLibraryDirectories_excluded', _folder_list)

_MSBuildOnly(_lib, 'DisplayLibrary', _string)  # /LIST Visible='false'
_MSBuildOnly(_lib, 'ErrorReporting',
             _Enumeration([], new=['PromptImmediately',  # /ERRORREPORT:PROMPT
                                   'QueueForNextLogin',  # /ERRORREPORT:QUEUE
                                   'SendErrorReport',  # /ERRORREPORT:SEND
                                   'NoErrorReport']))  # /ERRORREPORT:NONE
_MSBuildOnly(_lib, 'MinimumRequiredVersion', _string)
_MSBuildOnly(_lib, 'Name', _file_name)  # /NAME
_MSBuildOnly(_lib, 'RemoveObjects', _file_list)  # /REMOVE
_MSBuildOnly(_lib, 'SubSystem', _subsystem_enumeration)
_MSBuildOnly(_lib, 'TargetMachine', _target_machine_enumeration)
_MSBuildOnly(_lib, 'TrackerLogDirectory', _folder_name)
_MSBuildOnly(_lib, 'TreatLibWarningAsErrors', _boolean)  # /WX
_MSBuildOnly(_lib, 'Verbose', _boolean)


# Directives for converting VCManifestTool to Mt.
# See "c:\Program Files (x86)\MSBuild\Microsoft.Cpp\v4.0\1033\mt.xml" for
# the schema of the MSBuild Lib settings.

# Options that have the same name in MSVS and MSBuild
_Same(_manifest, 'AdditionalManifestFiles', _file_list)  # /manifest
_Same(_manifest, 'AdditionalOptions', _string_list)
_Same(_manifest, 'AssemblyIdentity', _string)  # /identity:
_Same(_manifest, 'ComponentFileName', _file_name)  # /dll
_Same(_manifest, 'GenerateCatalogFiles', _boolean)  # /makecdfs
_Same(_manifest, 'InputResourceManifests', _string)  # /inputresource
_Same(_manifest, 'OutputManifestFile', _file_name)  # /out
_Same(_manifest, 'RegistrarScriptFile', _file_name)  # /rgs
_Same(_manifest, 'ReplacementsFile', _file_name)  # /replacements
_Same(_manifest, 'SuppressStartupBanner', _boolean)  # /nologo
_Same(_manifest, 'TypeLibraryFile', _file_name)  # /tlb:
_Same(_manifest, 'UpdateFileHashes', _boolean)  # /hashupdate
_Same(_manifest, 'UpdateFileHashesSearchPath', _file_name)
_Same(_manifest, 'VerboseOutput', _boolean)  # /verbose

# Options that have moved location.
_MovedAndRenamed(_manifest, 'ManifestResourceFile',
                 'ManifestResourceCompile',
                 'ResourceOutputFileName',
                 _file_name)
_Moved(_manifest, 'EmbedManifest', '', _boolean)

# MSVS options not found in MSBuild.
_MSVSOnly(_manifest, 'DependencyInformationFile', _file_name)
_MSVSOnly(_manifest, 'UseFAT32Workaround', _boolean)
_MSVSOnly(_manifest, 'UseUnicodeResponseFiles', _boolean)

# MSBuild options not found in MSVS.
_MSBuildOnly(_manifest, 'EnableDPIAwareness', _boolean)
_MSBuildOnly(_manifest, 'GenerateCategoryTags', _boolean)  # /category
_MSBuildOnly(_manifest, 'ManifestFromManagedAssembly',
             _file_name)  # /managedassemblyname
_MSBuildOnly(_manifest, 'OutputResourceManifests', _string)  # /outputresource
_MSBuildOnly(_manifest, 'SuppressDependencyElement', _boolean)  # /nodependency
_MSBuildOnly(_manifest, 'TrackerLogDirectory', _folder_name)

########NEW FILE########
__FILENAME__ = MSVSSettings_test
#!/usr/bin/env python

# Copyright (c) 2012 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for the MSVSSettings.py file."""

import StringIO
import unittest
import gyp.MSVSSettings as MSVSSettings


class TestSequenceFunctions(unittest.TestCase):

  def setUp(self):
    self.stderr = StringIO.StringIO()

  def _ExpectedWarnings(self, expected):
    """Compares recorded lines to expected warnings."""
    self.stderr.seek(0)
    actual = self.stderr.read().split('\n')
    actual = [line for line in actual if line]
    self.assertEqual(sorted(expected), sorted(actual))

  def testValidateMSVSSettings_tool_names(self):
    """Tests that only MSVS tool names are allowed."""
    MSVSSettings.ValidateMSVSSettings(
        {'VCCLCompilerTool': {},
         'VCLinkerTool': {},
         'VCMIDLTool': {},
         'foo': {},
         'VCResourceCompilerTool': {},
         'VCLibrarianTool': {},
         'VCManifestTool': {},
         'ClCompile': {}},
        self.stderr)
    self._ExpectedWarnings([
        'Warning: unrecognized tool foo',
        'Warning: unrecognized tool ClCompile'])

  def testValidateMSVSSettings_settings(self):
    """Tests that for invalid MSVS settings."""
    MSVSSettings.ValidateMSVSSettings(
        {'VCCLCompilerTool': {
            'AdditionalIncludeDirectories': 'folder1;folder2',
            'AdditionalOptions': ['string1', 'string2'],
            'AdditionalUsingDirectories': 'folder1;folder2',
            'AssemblerListingLocation': 'a_file_name',
            'AssemblerOutput': '0',
            'BasicRuntimeChecks': '5',
            'BrowseInformation': 'fdkslj',
            'BrowseInformationFile': 'a_file_name',
            'BufferSecurityCheck': 'true',
            'CallingConvention': '-1',
            'CompileAs': '1',
            'DebugInformationFormat': '2',
            'DefaultCharIsUnsigned': 'true',
            'Detect64BitPortabilityProblems': 'true',
            'DisableLanguageExtensions': 'true',
            'DisableSpecificWarnings': 'string1;string2',
            'EnableEnhancedInstructionSet': '1',
            'EnableFiberSafeOptimizations': 'true',
            'EnableFunctionLevelLinking': 'true',
            'EnableIntrinsicFunctions': 'true',
            'EnablePREfast': 'true',
            'Enableprefast': 'bogus',
            'ErrorReporting': '1',
            'ExceptionHandling': '1',
            'ExpandAttributedSource': 'true',
            'FavorSizeOrSpeed': '1',
            'FloatingPointExceptions': 'true',
            'FloatingPointModel': '1',
            'ForceConformanceInForLoopScope': 'true',
            'ForcedIncludeFiles': 'file1;file2',
            'ForcedUsingFiles': 'file1;file2',
            'GeneratePreprocessedFile': '1',
            'GenerateXMLDocumentationFiles': 'true',
            'IgnoreStandardIncludePath': 'true',
            'InlineFunctionExpansion': '1',
            'KeepComments': 'true',
            'MinimalRebuild': 'true',
            'ObjectFile': 'a_file_name',
            'OmitDefaultLibName': 'true',
            'OmitFramePointers': 'true',
            'OpenMP': 'true',
            'Optimization': '1',
            'PrecompiledHeaderFile': 'a_file_name',
            'PrecompiledHeaderThrough': 'a_file_name',
            'PreprocessorDefinitions': 'string1;string2',
            'ProgramDataBaseFileName': 'a_file_name',
            'RuntimeLibrary': '1',
            'RuntimeTypeInfo': 'true',
            'ShowIncludes': 'true',
            'SmallerTypeCheck': 'true',
            'StringPooling': 'true',
            'StructMemberAlignment': '1',
            'SuppressStartupBanner': 'true',
            'TreatWChar_tAsBuiltInType': 'true',
            'UndefineAllPreprocessorDefinitions': 'true',
            'UndefinePreprocessorDefinitions': 'string1;string2',
            'UseFullPaths': 'true',
            'UsePrecompiledHeader': '1',
            'UseUnicodeResponseFiles': 'true',
            'WarnAsError': 'true',
            'WarningLevel': '1',
            'WholeProgramOptimization': 'true',
            'XMLDocumentationFileName': 'a_file_name',
            'ZZXYZ': 'bogus'},
         'VCLinkerTool': {
             'AdditionalDependencies': 'file1;file2',
             'AdditionalLibraryDirectories': 'folder1;folder2',
             'AdditionalManifestDependencies': 'file1;file2',
             'AdditionalOptions': 'a string1',
             'AddModuleNamesToAssembly': 'file1;file2',
             'AllowIsolation': 'true',
             'AssemblyDebug': '2',
             'AssemblyLinkResource': 'file1;file2',
             'BaseAddress': 'a string1',
             'CLRImageType': '2',
             'CLRThreadAttribute': '2',
             'CLRUnmanagedCodeCheck': 'true',
             'DataExecutionPrevention': '2',
             'DelayLoadDLLs': 'file1;file2',
             'DelaySign': 'true',
             'Driver': '2',
             'EmbedManagedResourceFile': 'file1;file2',
             'EnableCOMDATFolding': '2',
             'EnableUAC': 'true',
             'EntryPointSymbol': 'a string1',
             'ErrorReporting': '2',
             'FixedBaseAddress': '2',
             'ForceSymbolReferences': 'file1;file2',
             'FunctionOrder': 'a_file_name',
             'GenerateDebugInformation': 'true',
             'GenerateManifest': 'true',
             'GenerateMapFile': 'true',
             'HeapCommitSize': 'a string1',
             'HeapReserveSize': 'a string1',
             'IgnoreAllDefaultLibraries': 'true',
             'IgnoreDefaultLibraryNames': 'file1;file2',
             'IgnoreEmbeddedIDL': 'true',
             'IgnoreImportLibrary': 'true',
             'ImportLibrary': 'a_file_name',
             'KeyContainer': 'a_file_name',
             'KeyFile': 'a_file_name',
             'LargeAddressAware': '2',
             'LinkIncremental': '2',
             'LinkLibraryDependencies': 'true',
             'LinkTimeCodeGeneration': '2',
             'ManifestFile': 'a_file_name',
             'MapExports': 'true',
             'MapFileName': 'a_file_name',
             'MergedIDLBaseFileName': 'a_file_name',
             'MergeSections': 'a string1',
             'MidlCommandFile': 'a_file_name',
             'ModuleDefinitionFile': 'a_file_name',
             'OptimizeForWindows98': '1',
             'OptimizeReferences': '2',
             'OutputFile': 'a_file_name',
             'PerUserRedirection': 'true',
             'Profile': 'true',
             'ProfileGuidedDatabase': 'a_file_name',
             'ProgramDatabaseFile': 'a_file_name',
             'RandomizedBaseAddress': '2',
             'RegisterOutput': 'true',
             'ResourceOnlyDLL': 'true',
             'SetChecksum': 'true',
             'ShowProgress': '2',
             'StackCommitSize': 'a string1',
             'StackReserveSize': 'a string1',
             'StripPrivateSymbols': 'a_file_name',
             'SubSystem': '2',
             'SupportUnloadOfDelayLoadedDLL': 'true',
             'SuppressStartupBanner': 'true',
             'SwapRunFromCD': 'true',
             'SwapRunFromNet': 'true',
             'TargetMachine': '2',
             'TerminalServerAware': '2',
             'TurnOffAssemblyGeneration': 'true',
             'TypeLibraryFile': 'a_file_name',
             'TypeLibraryResourceID': '33',
             'UACExecutionLevel': '2',
             'UACUIAccess': 'true',
             'UseLibraryDependencyInputs': 'true',
             'UseUnicodeResponseFiles': 'true',
             'Version': 'a string1'},
         'VCMIDLTool': {
             'AdditionalIncludeDirectories': 'folder1;folder2',
             'AdditionalOptions': 'a string1',
             'CPreprocessOptions': 'a string1',
             'DefaultCharType': '1',
             'DLLDataFileName': 'a_file_name',
             'EnableErrorChecks': '1',
             'ErrorCheckAllocations': 'true',
             'ErrorCheckBounds': 'true',
             'ErrorCheckEnumRange': 'true',
             'ErrorCheckRefPointers': 'true',
             'ErrorCheckStubData': 'true',
             'GenerateStublessProxies': 'true',
             'GenerateTypeLibrary': 'true',
             'HeaderFileName': 'a_file_name',
             'IgnoreStandardIncludePath': 'true',
             'InterfaceIdentifierFileName': 'a_file_name',
             'MkTypLibCompatible': 'true',
             'notgood': 'bogus',
             'OutputDirectory': 'a string1',
             'PreprocessorDefinitions': 'string1;string2',
             'ProxyFileName': 'a_file_name',
             'RedirectOutputAndErrors': 'a_file_name',
             'StructMemberAlignment': '1',
             'SuppressStartupBanner': 'true',
             'TargetEnvironment': '1',
             'TypeLibraryName': 'a_file_name',
             'UndefinePreprocessorDefinitions': 'string1;string2',
             'ValidateParameters': 'true',
             'WarnAsError': 'true',
             'WarningLevel': '1'},
         'VCResourceCompilerTool': {
             'AdditionalOptions': 'a string1',
             'AdditionalIncludeDirectories': 'folder1;folder2',
             'Culture': '1003',
             'IgnoreStandardIncludePath': 'true',
             'notgood2': 'bogus',
             'PreprocessorDefinitions': 'string1;string2',
             'ResourceOutputFileName': 'a string1',
             'ShowProgress': 'true',
             'SuppressStartupBanner': 'true',
             'UndefinePreprocessorDefinitions': 'string1;string2'},
         'VCLibrarianTool': {
             'AdditionalDependencies': 'file1;file2',
             'AdditionalLibraryDirectories': 'folder1;folder2',
             'AdditionalOptions': 'a string1',
             'ExportNamedFunctions': 'string1;string2',
             'ForceSymbolReferences': 'a string1',
             'IgnoreAllDefaultLibraries': 'true',
             'IgnoreSpecificDefaultLibraries': 'file1;file2',
             'LinkLibraryDependencies': 'true',
             'ModuleDefinitionFile': 'a_file_name',
             'OutputFile': 'a_file_name',
             'SuppressStartupBanner': 'true',
             'UseUnicodeResponseFiles': 'true'},
         'VCManifestTool': {
             'AdditionalManifestFiles': 'file1;file2',
             'AdditionalOptions': 'a string1',
             'AssemblyIdentity': 'a string1',
             'ComponentFileName': 'a_file_name',
             'DependencyInformationFile': 'a_file_name',
             'GenerateCatalogFiles': 'true',
             'InputResourceManifests': 'a string1',
             'ManifestResourceFile': 'a_file_name',
             'OutputManifestFile': 'a_file_name',
             'RegistrarScriptFile': 'a_file_name',
             'ReplacementsFile': 'a_file_name',
             'SuppressStartupBanner': 'true',
             'TypeLibraryFile': 'a_file_name',
             'UpdateFileHashes': 'truel',
             'UpdateFileHashesSearchPath': 'a_file_name',
             'UseFAT32Workaround': 'true',
             'UseUnicodeResponseFiles': 'true',
             'VerboseOutput': 'true'}},
        self.stderr)
    self._ExpectedWarnings([
        'Warning: for VCCLCompilerTool/BasicRuntimeChecks, '
        'index value (5) not in expected range [0, 4)',
        'Warning: for VCCLCompilerTool/BrowseInformation, '
        "invalid literal for int() with base 10: 'fdkslj'",
        'Warning: for VCCLCompilerTool/CallingConvention, '
        'index value (-1) not in expected range [0, 3)',
        'Warning: for VCCLCompilerTool/DebugInformationFormat, '
        'converted value for 2 not specified.',
        'Warning: unrecognized setting VCCLCompilerTool/Enableprefast',
        'Warning: unrecognized setting VCCLCompilerTool/ZZXYZ',
        'Warning: for VCLinkerTool/TargetMachine, '
        'converted value for 2 not specified.',
        'Warning: unrecognized setting VCMIDLTool/notgood',
        'Warning: unrecognized setting VCResourceCompilerTool/notgood2',
        'Warning: for VCManifestTool/UpdateFileHashes, '
        "expected bool; got 'truel'"
        ''])

  def testValidateMSBuildSettings_settings(self):
    """Tests that for invalid MSBuild settings."""
    MSVSSettings.ValidateMSBuildSettings(
        {'ClCompile': {
            'AdditionalIncludeDirectories': 'folder1;folder2',
            'AdditionalOptions': ['string1', 'string2'],
            'AdditionalUsingDirectories': 'folder1;folder2',
            'AssemblerListingLocation': 'a_file_name',
            'AssemblerOutput': 'NoListing',
            'BasicRuntimeChecks': 'StackFrameRuntimeCheck',
            'BrowseInformation': 'false',
            'BrowseInformationFile': 'a_file_name',
            'BufferSecurityCheck': 'true',
            'BuildingInIDE': 'true',
            'CallingConvention': 'Cdecl',
            'CompileAs': 'CompileAsC',
            'CompileAsManaged': 'Pure',
            'CreateHotpatchableImage': 'true',
            'DebugInformationFormat': 'ProgramDatabase',
            'DisableLanguageExtensions': 'true',
            'DisableSpecificWarnings': 'string1;string2',
            'EnableEnhancedInstructionSet': 'StreamingSIMDExtensions',
            'EnableFiberSafeOptimizations': 'true',
            'EnablePREfast': 'true',
            'Enableprefast': 'bogus',
            'ErrorReporting': 'Prompt',
            'ExceptionHandling': 'SyncCThrow',
            'ExpandAttributedSource': 'true',
            'FavorSizeOrSpeed': 'Neither',
            'FloatingPointExceptions': 'true',
            'FloatingPointModel': 'Precise',
            'ForceConformanceInForLoopScope': 'true',
            'ForcedIncludeFiles': 'file1;file2',
            'ForcedUsingFiles': 'file1;file2',
            'FunctionLevelLinking': 'false',
            'GenerateXMLDocumentationFiles': 'true',
            'IgnoreStandardIncludePath': 'true',
            'InlineFunctionExpansion': 'OnlyExplicitInline',
            'IntrinsicFunctions': 'false',
            'MinimalRebuild': 'true',
            'MultiProcessorCompilation': 'true',
            'ObjectFileName': 'a_file_name',
            'OmitDefaultLibName': 'true',
            'OmitFramePointers': 'true',
            'OpenMPSupport': 'true',
            'Optimization': 'Disabled',
            'PrecompiledHeader': 'NotUsing',
            'PrecompiledHeaderFile': 'a_file_name',
            'PrecompiledHeaderOutputFile': 'a_file_name',
            'PreprocessKeepComments': 'true',
            'PreprocessorDefinitions': 'string1;string2',
            'PreprocessOutputPath': 'a string1',
            'PreprocessSuppressLineNumbers': 'false',
            'PreprocessToFile': 'false',
            'ProcessorNumber': '33',
            'ProgramDataBaseFileName': 'a_file_name',
            'RuntimeLibrary': 'MultiThreaded',
            'RuntimeTypeInfo': 'true',
            'ShowIncludes': 'true',
            'SmallerTypeCheck': 'true',
            'StringPooling': 'true',
            'StructMemberAlignment': '1Byte',
            'SuppressStartupBanner': 'true',
            'TrackerLogDirectory': 'a_folder',
            'TreatSpecificWarningsAsErrors': 'string1;string2',
            'TreatWarningAsError': 'true',
            'TreatWChar_tAsBuiltInType': 'true',
            'UndefineAllPreprocessorDefinitions': 'true',
            'UndefinePreprocessorDefinitions': 'string1;string2',
            'UseFullPaths': 'true',
            'UseUnicodeForAssemblerListing': 'true',
            'WarningLevel': 'TurnOffAllWarnings',
            'WholeProgramOptimization': 'true',
            'XMLDocumentationFileName': 'a_file_name',
            'ZZXYZ': 'bogus'},
         'Link': {
             'AdditionalDependencies': 'file1;file2',
             'AdditionalLibraryDirectories': 'folder1;folder2',
             'AdditionalManifestDependencies': 'file1;file2',
             'AdditionalOptions': 'a string1',
             'AddModuleNamesToAssembly': 'file1;file2',
             'AllowIsolation': 'true',
             'AssemblyDebug': '',
             'AssemblyLinkResource': 'file1;file2',
             'BaseAddress': 'a string1',
             'BuildingInIDE': 'true',
             'CLRImageType': 'ForceIJWImage',
             'CLRSupportLastError': 'Enabled',
             'CLRThreadAttribute': 'MTAThreadingAttribute',
             'CLRUnmanagedCodeCheck': 'true',
             'CreateHotPatchableImage': 'X86Image',
             'DataExecutionPrevention': 'false',
             'DelayLoadDLLs': 'file1;file2',
             'DelaySign': 'true',
             'Driver': 'NotSet',
             'EmbedManagedResourceFile': 'file1;file2',
             'EnableCOMDATFolding': 'false',
             'EnableUAC': 'true',
             'EntryPointSymbol': 'a string1',
             'FixedBaseAddress': 'false',
             'ForceFileOutput': 'Enabled',
             'ForceSymbolReferences': 'file1;file2',
             'FunctionOrder': 'a_file_name',
             'GenerateDebugInformation': 'true',
             'GenerateMapFile': 'true',
             'HeapCommitSize': 'a string1',
             'HeapReserveSize': 'a string1',
             'IgnoreAllDefaultLibraries': 'true',
             'IgnoreEmbeddedIDL': 'true',
             'IgnoreSpecificDefaultLibraries': 'a_file_list',
             'ImageHasSafeExceptionHandlers': 'true',
             'ImportLibrary': 'a_file_name',
             'KeyContainer': 'a_file_name',
             'KeyFile': 'a_file_name',
             'LargeAddressAware': 'false',
             'LinkDLL': 'true',
             'LinkErrorReporting': 'SendErrorReport',
             'LinkStatus': 'true',
             'LinkTimeCodeGeneration': 'UseLinkTimeCodeGeneration',
             'ManifestFile': 'a_file_name',
             'MapExports': 'true',
             'MapFileName': 'a_file_name',
             'MergedIDLBaseFileName': 'a_file_name',
             'MergeSections': 'a string1',
             'MidlCommandFile': 'a_file_name',
             'MinimumRequiredVersion': 'a string1',
             'ModuleDefinitionFile': 'a_file_name',
             'MSDOSStubFileName': 'a_file_name',
             'NoEntryPoint': 'true',
             'OptimizeReferences': 'false',
             'OutputFile': 'a_file_name',
             'PerUserRedirection': 'true',
             'PreventDllBinding': 'true',
             'Profile': 'true',
             'ProfileGuidedDatabase': 'a_file_name',
             'ProgramDatabaseFile': 'a_file_name',
             'RandomizedBaseAddress': 'false',
             'RegisterOutput': 'true',
             'SectionAlignment': '33',
             'SetChecksum': 'true',
             'ShowProgress': 'LinkVerboseREF',
             'SpecifySectionAttributes': 'a string1',
             'StackCommitSize': 'a string1',
             'StackReserveSize': 'a string1',
             'StripPrivateSymbols': 'a_file_name',
             'SubSystem': 'Console',
             'SupportNobindOfDelayLoadedDLL': 'true',
             'SupportUnloadOfDelayLoadedDLL': 'true',
             'SuppressStartupBanner': 'true',
             'SwapRunFromCD': 'true',
             'SwapRunFromNET': 'true',
             'TargetMachine': 'MachineX86',
             'TerminalServerAware': 'false',
             'TrackerLogDirectory': 'a_folder',
             'TreatLinkerWarningAsErrors': 'true',
             'TurnOffAssemblyGeneration': 'true',
             'TypeLibraryFile': 'a_file_name',
             'TypeLibraryResourceID': '33',
             'UACExecutionLevel': 'AsInvoker',
             'UACUIAccess': 'true',
             'Version': 'a string1'},
         'ResourceCompile': {
             'AdditionalIncludeDirectories': 'folder1;folder2',
             'AdditionalOptions': 'a string1',
             'Culture': '0x236',
             'IgnoreStandardIncludePath': 'true',
             'NullTerminateStrings': 'true',
             'PreprocessorDefinitions': 'string1;string2',
             'ResourceOutputFileName': 'a string1',
             'ShowProgress': 'true',
             'SuppressStartupBanner': 'true',
             'TrackerLogDirectory': 'a_folder',
             'UndefinePreprocessorDefinitions': 'string1;string2'},
         'Midl': {
             'AdditionalIncludeDirectories': 'folder1;folder2',
             'AdditionalOptions': 'a string1',
             'ApplicationConfigurationMode': 'true',
             'ClientStubFile': 'a_file_name',
             'CPreprocessOptions': 'a string1',
             'DefaultCharType': 'Signed',
             'DllDataFileName': 'a_file_name',
             'EnableErrorChecks': 'EnableCustom',
             'ErrorCheckAllocations': 'true',
             'ErrorCheckBounds': 'true',
             'ErrorCheckEnumRange': 'true',
             'ErrorCheckRefPointers': 'true',
             'ErrorCheckStubData': 'true',
             'GenerateClientFiles': 'Stub',
             'GenerateServerFiles': 'None',
             'GenerateStublessProxies': 'true',
             'GenerateTypeLibrary': 'true',
             'HeaderFileName': 'a_file_name',
             'IgnoreStandardIncludePath': 'true',
             'InterfaceIdentifierFileName': 'a_file_name',
             'LocaleID': '33',
             'MkTypLibCompatible': 'true',
             'OutputDirectory': 'a string1',
             'PreprocessorDefinitions': 'string1;string2',
             'ProxyFileName': 'a_file_name',
             'RedirectOutputAndErrors': 'a_file_name',
             'ServerStubFile': 'a_file_name',
             'StructMemberAlignment': 'NotSet',
             'SuppressCompilerWarnings': 'true',
             'SuppressStartupBanner': 'true',
             'TargetEnvironment': 'Itanium',
             'TrackerLogDirectory': 'a_folder',
             'TypeLibFormat': 'NewFormat',
             'TypeLibraryName': 'a_file_name',
             'UndefinePreprocessorDefinitions': 'string1;string2',
             'ValidateAllParameters': 'true',
             'WarnAsError': 'true',
             'WarningLevel': '1'},
         'Lib': {
             'AdditionalDependencies': 'file1;file2',
             'AdditionalLibraryDirectories': 'folder1;folder2',
             'AdditionalOptions': 'a string1',
             'DisplayLibrary': 'a string1',
             'ErrorReporting': 'PromptImmediately',
             'ExportNamedFunctions': 'string1;string2',
             'ForceSymbolReferences': 'a string1',
             'IgnoreAllDefaultLibraries': 'true',
             'IgnoreSpecificDefaultLibraries': 'file1;file2',
             'LinkTimeCodeGeneration': 'true',
             'MinimumRequiredVersion': 'a string1',
             'ModuleDefinitionFile': 'a_file_name',
             'Name': 'a_file_name',
             'OutputFile': 'a_file_name',
             'RemoveObjects': 'file1;file2',
             'SubSystem': 'Console',
             'SuppressStartupBanner': 'true',
             'TargetMachine': 'MachineX86i',
             'TrackerLogDirectory': 'a_folder',
             'TreatLibWarningAsErrors': 'true',
             'UseUnicodeResponseFiles': 'true',
             'Verbose': 'true'},
         'Manifest': {
             'AdditionalManifestFiles': 'file1;file2',
             'AdditionalOptions': 'a string1',
             'AssemblyIdentity': 'a string1',
             'ComponentFileName': 'a_file_name',
             'EnableDPIAwareness': 'fal',
             'GenerateCatalogFiles': 'truel',
             'GenerateCategoryTags': 'true',
             'InputResourceManifests': 'a string1',
             'ManifestFromManagedAssembly': 'a_file_name',
             'notgood3': 'bogus',
             'OutputManifestFile': 'a_file_name',
             'OutputResourceManifests': 'a string1',
             'RegistrarScriptFile': 'a_file_name',
             'ReplacementsFile': 'a_file_name',
             'SuppressDependencyElement': 'true',
             'SuppressStartupBanner': 'true',
             'TrackerLogDirectory': 'a_folder',
             'TypeLibraryFile': 'a_file_name',
             'UpdateFileHashes': 'true',
             'UpdateFileHashesSearchPath': 'a_file_name',
             'VerboseOutput': 'true'},
         'ProjectReference': {
             'LinkLibraryDependencies': 'true',
             'UseLibraryDependencyInputs': 'true'},
         'ManifestResourceCompile': {
             'ResourceOutputFileName': 'a_file_name'},
         '': {
             'EmbedManifest': 'true',
             'GenerateManifest': 'true',
             'IgnoreImportLibrary': 'true',
             'LinkIncremental': 'false'}},
        self.stderr)
    self._ExpectedWarnings([
        'Warning: unrecognized setting ClCompile/Enableprefast',
        'Warning: unrecognized setting ClCompile/ZZXYZ',
        'Warning: unrecognized setting Manifest/notgood3',
        'Warning: for Manifest/GenerateCatalogFiles, '
        "expected bool; got 'truel'",
        'Warning: for Lib/TargetMachine, unrecognized enumerated value '
        'MachineX86i',
        "Warning: for Manifest/EnableDPIAwareness, expected bool; got 'fal'"])

  def testConvertToMSBuildSettings_empty(self):
    """Tests an empty conversion."""
    msvs_settings = {}
    expected_msbuild_settings = {}
    actual_msbuild_settings = MSVSSettings.ConvertToMSBuildSettings(
        msvs_settings,
        self.stderr)
    self.assertEqual(expected_msbuild_settings, actual_msbuild_settings)
    self._ExpectedWarnings([])

  def testConvertToMSBuildSettings_minimal(self):
    """Tests a minimal conversion."""
    msvs_settings = {
        'VCCLCompilerTool': {
            'AdditionalIncludeDirectories': 'dir1',
            'AdditionalOptions': '/foo',
            'BasicRuntimeChecks': '0',
            },
        'VCLinkerTool': {
            'LinkTimeCodeGeneration': '1',
            'ErrorReporting': '1',
            'DataExecutionPrevention': '2',
            },
        }
    expected_msbuild_settings = {
        'ClCompile': {
            'AdditionalIncludeDirectories': 'dir1',
            'AdditionalOptions': '/foo',
            'BasicRuntimeChecks': 'Default',
            },
        'Link': {
            'LinkTimeCodeGeneration': 'UseLinkTimeCodeGeneration',
            'LinkErrorReporting': 'PromptImmediately',
            'DataExecutionPrevention': 'true',
            },
        }
    actual_msbuild_settings = MSVSSettings.ConvertToMSBuildSettings(
        msvs_settings,
        self.stderr)
    self.assertEqual(expected_msbuild_settings, actual_msbuild_settings)
    self._ExpectedWarnings([])

  def testConvertToMSBuildSettings_warnings(self):
    """Tests conversion that generates warnings."""
    msvs_settings = {
        'VCCLCompilerTool': {
            'AdditionalIncludeDirectories': '1',
            'AdditionalOptions': '2',
            # These are incorrect values:
            'BasicRuntimeChecks': '12',
            'BrowseInformation': '21',
            'UsePrecompiledHeader': '13',
            'GeneratePreprocessedFile': '14'},
        'VCLinkerTool': {
            # These are incorrect values:
            'Driver': '10',
            'LinkTimeCodeGeneration': '31',
            'ErrorReporting': '21',
            'FixedBaseAddress': '6'},
        'VCResourceCompilerTool': {
            # Custom
            'Culture': '1003'}}
    expected_msbuild_settings = {
        'ClCompile': {
            'AdditionalIncludeDirectories': '1',
            'AdditionalOptions': '2'},
        'Link': {},
        'ResourceCompile': {
            # Custom
            'Culture': '0x03eb'}}
    actual_msbuild_settings = MSVSSettings.ConvertToMSBuildSettings(
        msvs_settings,
        self.stderr)
    self.assertEqual(expected_msbuild_settings, actual_msbuild_settings)
    self._ExpectedWarnings([
        'Warning: while converting VCCLCompilerTool/BasicRuntimeChecks to '
        'MSBuild, index value (12) not in expected range [0, 4)',
        'Warning: while converting VCCLCompilerTool/BrowseInformation to '
        'MSBuild, index value (21) not in expected range [0, 3)',
        'Warning: while converting VCCLCompilerTool/UsePrecompiledHeader to '
        'MSBuild, index value (13) not in expected range [0, 3)',
        'Warning: while converting VCCLCompilerTool/GeneratePreprocessedFile to '
        'MSBuild, value must be one of [0, 1, 2]; got 14',

        'Warning: while converting VCLinkerTool/Driver to '
        'MSBuild, index value (10) not in expected range [0, 4)',
        'Warning: while converting VCLinkerTool/LinkTimeCodeGeneration to '
        'MSBuild, index value (31) not in expected range [0, 5)',
        'Warning: while converting VCLinkerTool/ErrorReporting to '
        'MSBuild, index value (21) not in expected range [0, 3)',
        'Warning: while converting VCLinkerTool/FixedBaseAddress to '
        'MSBuild, index value (6) not in expected range [0, 3)',
        ])

  def testConvertToMSBuildSettings_full_synthetic(self):
    """Tests conversion of all the MSBuild settings."""
    msvs_settings = {
        'VCCLCompilerTool': {
            'AdditionalIncludeDirectories': 'folder1;folder2;folder3',
            'AdditionalOptions': 'a_string',
            'AdditionalUsingDirectories': 'folder1;folder2;folder3',
            'AssemblerListingLocation': 'a_file_name',
            'AssemblerOutput': '0',
            'BasicRuntimeChecks': '1',
            'BrowseInformation': '2',
            'BrowseInformationFile': 'a_file_name',
            'BufferSecurityCheck': 'true',
            'CallingConvention': '0',
            'CompileAs': '1',
            'DebugInformationFormat': '4',
            'DefaultCharIsUnsigned': 'true',
            'Detect64BitPortabilityProblems': 'true',
            'DisableLanguageExtensions': 'true',
            'DisableSpecificWarnings': 'd1;d2;d3',
            'EnableEnhancedInstructionSet': '0',
            'EnableFiberSafeOptimizations': 'true',
            'EnableFunctionLevelLinking': 'true',
            'EnableIntrinsicFunctions': 'true',
            'EnablePREfast': 'true',
            'ErrorReporting': '1',
            'ExceptionHandling': '2',
            'ExpandAttributedSource': 'true',
            'FavorSizeOrSpeed': '0',
            'FloatingPointExceptions': 'true',
            'FloatingPointModel': '1',
            'ForceConformanceInForLoopScope': 'true',
            'ForcedIncludeFiles': 'file1;file2;file3',
            'ForcedUsingFiles': 'file1;file2;file3',
            'GeneratePreprocessedFile': '1',
            'GenerateXMLDocumentationFiles': 'true',
            'IgnoreStandardIncludePath': 'true',
            'InlineFunctionExpansion': '2',
            'KeepComments': 'true',
            'MinimalRebuild': 'true',
            'ObjectFile': 'a_file_name',
            'OmitDefaultLibName': 'true',
            'OmitFramePointers': 'true',
            'OpenMP': 'true',
            'Optimization': '3',
            'PrecompiledHeaderFile': 'a_file_name',
            'PrecompiledHeaderThrough': 'a_file_name',
            'PreprocessorDefinitions': 'd1;d2;d3',
            'ProgramDataBaseFileName': 'a_file_name',
            'RuntimeLibrary': '0',
            'RuntimeTypeInfo': 'true',
            'ShowIncludes': 'true',
            'SmallerTypeCheck': 'true',
            'StringPooling': 'true',
            'StructMemberAlignment': '1',
            'SuppressStartupBanner': 'true',
            'TreatWChar_tAsBuiltInType': 'true',
            'UndefineAllPreprocessorDefinitions': 'true',
            'UndefinePreprocessorDefinitions': 'd1;d2;d3',
            'UseFullPaths': 'true',
            'UsePrecompiledHeader': '1',
            'UseUnicodeResponseFiles': 'true',
            'WarnAsError': 'true',
            'WarningLevel': '2',
            'WholeProgramOptimization': 'true',
            'XMLDocumentationFileName': 'a_file_name'},
        'VCLinkerTool': {
            'AdditionalDependencies': 'file1;file2;file3',
            'AdditionalLibraryDirectories': 'folder1;folder2;folder3',
            'AdditionalLibraryDirectories_excluded': 'folder1;folder2;folder3',
            'AdditionalManifestDependencies': 'file1;file2;file3',
            'AdditionalOptions': 'a_string',
            'AddModuleNamesToAssembly': 'file1;file2;file3',
            'AllowIsolation': 'true',
            'AssemblyDebug': '0',
            'AssemblyLinkResource': 'file1;file2;file3',
            'BaseAddress': 'a_string',
            'CLRImageType': '1',
            'CLRThreadAttribute': '2',
            'CLRUnmanagedCodeCheck': 'true',
            'DataExecutionPrevention': '0',
            'DelayLoadDLLs': 'file1;file2;file3',
            'DelaySign': 'true',
            'Driver': '1',
            'EmbedManagedResourceFile': 'file1;file2;file3',
            'EnableCOMDATFolding': '0',
            'EnableUAC': 'true',
            'EntryPointSymbol': 'a_string',
            'ErrorReporting': '0',
            'FixedBaseAddress': '1',
            'ForceSymbolReferences': 'file1;file2;file3',
            'FunctionOrder': 'a_file_name',
            'GenerateDebugInformation': 'true',
            'GenerateManifest': 'true',
            'GenerateMapFile': 'true',
            'HeapCommitSize': 'a_string',
            'HeapReserveSize': 'a_string',
            'IgnoreAllDefaultLibraries': 'true',
            'IgnoreDefaultLibraryNames': 'file1;file2;file3',
            'IgnoreEmbeddedIDL': 'true',
            'IgnoreImportLibrary': 'true',
            'ImportLibrary': 'a_file_name',
            'KeyContainer': 'a_file_name',
            'KeyFile': 'a_file_name',
            'LargeAddressAware': '2',
            'LinkIncremental': '1',
            'LinkLibraryDependencies': 'true',
            'LinkTimeCodeGeneration': '2',
            'ManifestFile': 'a_file_name',
            'MapExports': 'true',
            'MapFileName': 'a_file_name',
            'MergedIDLBaseFileName': 'a_file_name',
            'MergeSections': 'a_string',
            'MidlCommandFile': 'a_file_name',
            'ModuleDefinitionFile': 'a_file_name',
            'OptimizeForWindows98': '1',
            'OptimizeReferences': '0',
            'OutputFile': 'a_file_name',
            'PerUserRedirection': 'true',
            'Profile': 'true',
            'ProfileGuidedDatabase': 'a_file_name',
            'ProgramDatabaseFile': 'a_file_name',
            'RandomizedBaseAddress': '1',
            'RegisterOutput': 'true',
            'ResourceOnlyDLL': 'true',
            'SetChecksum': 'true',
            'ShowProgress': '0',
            'StackCommitSize': 'a_string',
            'StackReserveSize': 'a_string',
            'StripPrivateSymbols': 'a_file_name',
            'SubSystem': '2',
            'SupportUnloadOfDelayLoadedDLL': 'true',
            'SuppressStartupBanner': 'true',
            'SwapRunFromCD': 'true',
            'SwapRunFromNet': 'true',
            'TargetMachine': '3',
            'TerminalServerAware': '2',
            'TurnOffAssemblyGeneration': 'true',
            'TypeLibraryFile': 'a_file_name',
            'TypeLibraryResourceID': '33',
            'UACExecutionLevel': '1',
            'UACUIAccess': 'true',
            'UseLibraryDependencyInputs': 'false',
            'UseUnicodeResponseFiles': 'true',
            'Version': 'a_string'},
        'VCResourceCompilerTool': {
            'AdditionalIncludeDirectories': 'folder1;folder2;folder3',
            'AdditionalOptions': 'a_string',
            'Culture': '1003',
            'IgnoreStandardIncludePath': 'true',
            'PreprocessorDefinitions': 'd1;d2;d3',
            'ResourceOutputFileName': 'a_string',
            'ShowProgress': 'true',
            'SuppressStartupBanner': 'true',
            'UndefinePreprocessorDefinitions': 'd1;d2;d3'},
        'VCMIDLTool': {
            'AdditionalIncludeDirectories': 'folder1;folder2;folder3',
            'AdditionalOptions': 'a_string',
            'CPreprocessOptions': 'a_string',
            'DefaultCharType': '0',
            'DLLDataFileName': 'a_file_name',
            'EnableErrorChecks': '2',
            'ErrorCheckAllocations': 'true',
            'ErrorCheckBounds': 'true',
            'ErrorCheckEnumRange': 'true',
            'ErrorCheckRefPointers': 'true',
            'ErrorCheckStubData': 'true',
            'GenerateStublessProxies': 'true',
            'GenerateTypeLibrary': 'true',
            'HeaderFileName': 'a_file_name',
            'IgnoreStandardIncludePath': 'true',
            'InterfaceIdentifierFileName': 'a_file_name',
            'MkTypLibCompatible': 'true',
            'OutputDirectory': 'a_string',
            'PreprocessorDefinitions': 'd1;d2;d3',
            'ProxyFileName': 'a_file_name',
            'RedirectOutputAndErrors': 'a_file_name',
            'StructMemberAlignment': '3',
            'SuppressStartupBanner': 'true',
            'TargetEnvironment': '1',
            'TypeLibraryName': 'a_file_name',
            'UndefinePreprocessorDefinitions': 'd1;d2;d3',
            'ValidateParameters': 'true',
            'WarnAsError': 'true',
            'WarningLevel': '4'},
        'VCLibrarianTool': {
            'AdditionalDependencies': 'file1;file2;file3',
            'AdditionalLibraryDirectories': 'folder1;folder2;folder3',
            'AdditionalLibraryDirectories_excluded': 'folder1;folder2;folder3',
            'AdditionalOptions': 'a_string',
            'ExportNamedFunctions': 'd1;d2;d3',
            'ForceSymbolReferences': 'a_string',
            'IgnoreAllDefaultLibraries': 'true',
            'IgnoreSpecificDefaultLibraries': 'file1;file2;file3',
            'LinkLibraryDependencies': 'true',
            'ModuleDefinitionFile': 'a_file_name',
            'OutputFile': 'a_file_name',
            'SuppressStartupBanner': 'true',
            'UseUnicodeResponseFiles': 'true'},
        'VCManifestTool': {
            'AdditionalManifestFiles': 'file1;file2;file3',
            'AdditionalOptions': 'a_string',
            'AssemblyIdentity': 'a_string',
            'ComponentFileName': 'a_file_name',
            'DependencyInformationFile': 'a_file_name',
            'EmbedManifest': 'true',
            'GenerateCatalogFiles': 'true',
            'InputResourceManifests': 'a_string',
            'ManifestResourceFile': 'my_name',
            'OutputManifestFile': 'a_file_name',
            'RegistrarScriptFile': 'a_file_name',
            'ReplacementsFile': 'a_file_name',
            'SuppressStartupBanner': 'true',
            'TypeLibraryFile': 'a_file_name',
            'UpdateFileHashes': 'true',
            'UpdateFileHashesSearchPath': 'a_file_name',
            'UseFAT32Workaround': 'true',
            'UseUnicodeResponseFiles': 'true',
            'VerboseOutput': 'true'}}
    expected_msbuild_settings = {
        'ClCompile': {
            'AdditionalIncludeDirectories': 'folder1;folder2;folder3',
            'AdditionalOptions': 'a_string /J',
            'AdditionalUsingDirectories': 'folder1;folder2;folder3',
            'AssemblerListingLocation': 'a_file_name',
            'AssemblerOutput': 'NoListing',
            'BasicRuntimeChecks': 'StackFrameRuntimeCheck',
            'BrowseInformation': 'true',
            'BrowseInformationFile': 'a_file_name',
            'BufferSecurityCheck': 'true',
            'CallingConvention': 'Cdecl',
            'CompileAs': 'CompileAsC',
            'DebugInformationFormat': 'EditAndContinue',
            'DisableLanguageExtensions': 'true',
            'DisableSpecificWarnings': 'd1;d2;d3',
            'EnableEnhancedInstructionSet': 'NotSet',
            'EnableFiberSafeOptimizations': 'true',
            'EnablePREfast': 'true',
            'ErrorReporting': 'Prompt',
            'ExceptionHandling': 'Async',
            'ExpandAttributedSource': 'true',
            'FavorSizeOrSpeed': 'Neither',
            'FloatingPointExceptions': 'true',
            'FloatingPointModel': 'Strict',
            'ForceConformanceInForLoopScope': 'true',
            'ForcedIncludeFiles': 'file1;file2;file3',
            'ForcedUsingFiles': 'file1;file2;file3',
            'FunctionLevelLinking': 'true',
            'GenerateXMLDocumentationFiles': 'true',
            'IgnoreStandardIncludePath': 'true',
            'InlineFunctionExpansion': 'AnySuitable',
            'IntrinsicFunctions': 'true',
            'MinimalRebuild': 'true',
            'ObjectFileName': 'a_file_name',
            'OmitDefaultLibName': 'true',
            'OmitFramePointers': 'true',
            'OpenMPSupport': 'true',
            'Optimization': 'Full',
            'PrecompiledHeader': 'Create',
            'PrecompiledHeaderFile': 'a_file_name',
            'PrecompiledHeaderOutputFile': 'a_file_name',
            'PreprocessKeepComments': 'true',
            'PreprocessorDefinitions': 'd1;d2;d3',
            'PreprocessSuppressLineNumbers': 'false',
            'PreprocessToFile': 'true',
            'ProgramDataBaseFileName': 'a_file_name',
            'RuntimeLibrary': 'MultiThreaded',
            'RuntimeTypeInfo': 'true',
            'ShowIncludes': 'true',
            'SmallerTypeCheck': 'true',
            'StringPooling': 'true',
            'StructMemberAlignment': '1Byte',
            'SuppressStartupBanner': 'true',
            'TreatWarningAsError': 'true',
            'TreatWChar_tAsBuiltInType': 'true',
            'UndefineAllPreprocessorDefinitions': 'true',
            'UndefinePreprocessorDefinitions': 'd1;d2;d3',
            'UseFullPaths': 'true',
            'WarningLevel': 'Level2',
            'WholeProgramOptimization': 'true',
            'XMLDocumentationFileName': 'a_file_name'},
        'Link': {
            'AdditionalDependencies': 'file1;file2;file3',
            'AdditionalLibraryDirectories': 'folder1;folder2;folder3',
            'AdditionalManifestDependencies': 'file1;file2;file3',
            'AdditionalOptions': 'a_string',
            'AddModuleNamesToAssembly': 'file1;file2;file3',
            'AllowIsolation': 'true',
            'AssemblyDebug': '',
            'AssemblyLinkResource': 'file1;file2;file3',
            'BaseAddress': 'a_string',
            'CLRImageType': 'ForceIJWImage',
            'CLRThreadAttribute': 'STAThreadingAttribute',
            'CLRUnmanagedCodeCheck': 'true',
            'DataExecutionPrevention': '',
            'DelayLoadDLLs': 'file1;file2;file3',
            'DelaySign': 'true',
            'Driver': 'Driver',
            'EmbedManagedResourceFile': 'file1;file2;file3',
            'EnableCOMDATFolding': '',
            'EnableUAC': 'true',
            'EntryPointSymbol': 'a_string',
            'FixedBaseAddress': 'false',
            'ForceSymbolReferences': 'file1;file2;file3',
            'FunctionOrder': 'a_file_name',
            'GenerateDebugInformation': 'true',
            'GenerateMapFile': 'true',
            'HeapCommitSize': 'a_string',
            'HeapReserveSize': 'a_string',
            'IgnoreAllDefaultLibraries': 'true',
            'IgnoreEmbeddedIDL': 'true',
            'IgnoreSpecificDefaultLibraries': 'file1;file2;file3',
            'ImportLibrary': 'a_file_name',
            'KeyContainer': 'a_file_name',
            'KeyFile': 'a_file_name',
            'LargeAddressAware': 'true',
            'LinkErrorReporting': 'NoErrorReport',
            'LinkTimeCodeGeneration': 'PGInstrument',
            'ManifestFile': 'a_file_name',
            'MapExports': 'true',
            'MapFileName': 'a_file_name',
            'MergedIDLBaseFileName': 'a_file_name',
            'MergeSections': 'a_string',
            'MidlCommandFile': 'a_file_name',
            'ModuleDefinitionFile': 'a_file_name',
            'NoEntryPoint': 'true',
            'OptimizeReferences': '',
            'OutputFile': 'a_file_name',
            'PerUserRedirection': 'true',
            'Profile': 'true',
            'ProfileGuidedDatabase': 'a_file_name',
            'ProgramDatabaseFile': 'a_file_name',
            'RandomizedBaseAddress': 'false',
            'RegisterOutput': 'true',
            'SetChecksum': 'true',
            'ShowProgress': 'NotSet',
            'StackCommitSize': 'a_string',
            'StackReserveSize': 'a_string',
            'StripPrivateSymbols': 'a_file_name',
            'SubSystem': 'Windows',
            'SupportUnloadOfDelayLoadedDLL': 'true',
            'SuppressStartupBanner': 'true',
            'SwapRunFromCD': 'true',
            'SwapRunFromNET': 'true',
            'TargetMachine': 'MachineARM',
            'TerminalServerAware': 'true',
            'TurnOffAssemblyGeneration': 'true',
            'TypeLibraryFile': 'a_file_name',
            'TypeLibraryResourceID': '33',
            'UACExecutionLevel': 'HighestAvailable',
            'UACUIAccess': 'true',
            'Version': 'a_string'},
        'ResourceCompile': {
            'AdditionalIncludeDirectories': 'folder1;folder2;folder3',
            'AdditionalOptions': 'a_string',
            'Culture': '0x03eb',
            'IgnoreStandardIncludePath': 'true',
            'PreprocessorDefinitions': 'd1;d2;d3',
            'ResourceOutputFileName': 'a_string',
            'ShowProgress': 'true',
            'SuppressStartupBanner': 'true',
            'UndefinePreprocessorDefinitions': 'd1;d2;d3'},
        'Midl': {
            'AdditionalIncludeDirectories': 'folder1;folder2;folder3',
            'AdditionalOptions': 'a_string',
            'CPreprocessOptions': 'a_string',
            'DefaultCharType': 'Unsigned',
            'DllDataFileName': 'a_file_name',
            'EnableErrorChecks': 'All',
            'ErrorCheckAllocations': 'true',
            'ErrorCheckBounds': 'true',
            'ErrorCheckEnumRange': 'true',
            'ErrorCheckRefPointers': 'true',
            'ErrorCheckStubData': 'true',
            'GenerateStublessProxies': 'true',
            'GenerateTypeLibrary': 'true',
            'HeaderFileName': 'a_file_name',
            'IgnoreStandardIncludePath': 'true',
            'InterfaceIdentifierFileName': 'a_file_name',
            'MkTypLibCompatible': 'true',
            'OutputDirectory': 'a_string',
            'PreprocessorDefinitions': 'd1;d2;d3',
            'ProxyFileName': 'a_file_name',
            'RedirectOutputAndErrors': 'a_file_name',
            'StructMemberAlignment': '4',
            'SuppressStartupBanner': 'true',
            'TargetEnvironment': 'Win32',
            'TypeLibraryName': 'a_file_name',
            'UndefinePreprocessorDefinitions': 'd1;d2;d3',
            'ValidateAllParameters': 'true',
            'WarnAsError': 'true',
            'WarningLevel': '4'},
        'Lib': {
            'AdditionalDependencies': 'file1;file2;file3',
            'AdditionalLibraryDirectories': 'folder1;folder2;folder3',
            'AdditionalOptions': 'a_string',
            'ExportNamedFunctions': 'd1;d2;d3',
            'ForceSymbolReferences': 'a_string',
            'IgnoreAllDefaultLibraries': 'true',
            'IgnoreSpecificDefaultLibraries': 'file1;file2;file3',
            'ModuleDefinitionFile': 'a_file_name',
            'OutputFile': 'a_file_name',
            'SuppressStartupBanner': 'true',
            'UseUnicodeResponseFiles': 'true'},
        'Manifest': {
            'AdditionalManifestFiles': 'file1;file2;file3',
            'AdditionalOptions': 'a_string',
            'AssemblyIdentity': 'a_string',
            'ComponentFileName': 'a_file_name',
            'GenerateCatalogFiles': 'true',
            'InputResourceManifests': 'a_string',
            'OutputManifestFile': 'a_file_name',
            'RegistrarScriptFile': 'a_file_name',
            'ReplacementsFile': 'a_file_name',
            'SuppressStartupBanner': 'true',
            'TypeLibraryFile': 'a_file_name',
            'UpdateFileHashes': 'true',
            'UpdateFileHashesSearchPath': 'a_file_name',
            'VerboseOutput': 'true'},
        'ManifestResourceCompile': {
            'ResourceOutputFileName': 'my_name'},
        'ProjectReference': {
            'LinkLibraryDependencies': 'true',
            'UseLibraryDependencyInputs': 'false'},
        '': {
            'EmbedManifest': 'true',
            'GenerateManifest': 'true',
            'IgnoreImportLibrary': 'true',
            'LinkIncremental': 'false'}}
    actual_msbuild_settings = MSVSSettings.ConvertToMSBuildSettings(
        msvs_settings,
        self.stderr)
    self.assertEqual(expected_msbuild_settings, actual_msbuild_settings)
    self._ExpectedWarnings([])

  def testConvertToMSBuildSettings_actual(self):
    """Tests the conversion of an actual project.

    A VS2008 project with most of the options defined was created through the
    VS2008 IDE.  It was then converted to VS2010.  The tool settings found in
    the .vcproj and .vcxproj files were converted to the two dictionaries
    msvs_settings and expected_msbuild_settings.

    Note that for many settings, the VS2010 converter adds macros like
    %(AdditionalIncludeDirectories) to make sure than inherited values are
    included.  Since the Gyp projects we generate do not use inheritance,
    we removed these macros.  They were:
        ClCompile:
            AdditionalIncludeDirectories:  ';%(AdditionalIncludeDirectories)'
            AdditionalOptions:  ' %(AdditionalOptions)'
            AdditionalUsingDirectories:  ';%(AdditionalUsingDirectories)'
            DisableSpecificWarnings: ';%(DisableSpecificWarnings)',
            ForcedIncludeFiles:  ';%(ForcedIncludeFiles)',
            ForcedUsingFiles:  ';%(ForcedUsingFiles)',
            PreprocessorDefinitions:  ';%(PreprocessorDefinitions)',
            UndefinePreprocessorDefinitions:
                ';%(UndefinePreprocessorDefinitions)',
        Link:
            AdditionalDependencies:  ';%(AdditionalDependencies)',
            AdditionalLibraryDirectories:  ';%(AdditionalLibraryDirectories)',
            AdditionalManifestDependencies:
                ';%(AdditionalManifestDependencies)',
            AdditionalOptions:  ' %(AdditionalOptions)',
            AddModuleNamesToAssembly:  ';%(AddModuleNamesToAssembly)',
            AssemblyLinkResource:  ';%(AssemblyLinkResource)',
            DelayLoadDLLs:  ';%(DelayLoadDLLs)',
            EmbedManagedResourceFile:  ';%(EmbedManagedResourceFile)',
            ForceSymbolReferences:  ';%(ForceSymbolReferences)',
            IgnoreSpecificDefaultLibraries:
                ';%(IgnoreSpecificDefaultLibraries)',
        ResourceCompile:
            AdditionalIncludeDirectories:  ';%(AdditionalIncludeDirectories)',
            AdditionalOptions:  ' %(AdditionalOptions)',
            PreprocessorDefinitions:  ';%(PreprocessorDefinitions)',
        Manifest:
            AdditionalManifestFiles:  ';%(AdditionalManifestFiles)',
            AdditionalOptions:  ' %(AdditionalOptions)',
            InputResourceManifests:  ';%(InputResourceManifests)',
    """
    msvs_settings = {
        'VCCLCompilerTool': {
            'AdditionalIncludeDirectories': 'dir1',
            'AdditionalOptions': '/more',
            'AdditionalUsingDirectories': 'test',
            'AssemblerListingLocation': '$(IntDir)\\a',
            'AssemblerOutput': '1',
            'BasicRuntimeChecks': '3',
            'BrowseInformation': '1',
            'BrowseInformationFile': '$(IntDir)\\e',
            'BufferSecurityCheck': 'false',
            'CallingConvention': '1',
            'CompileAs': '1',
            'DebugInformationFormat': '4',
            'DefaultCharIsUnsigned': 'true',
            'Detect64BitPortabilityProblems': 'true',
            'DisableLanguageExtensions': 'true',
            'DisableSpecificWarnings': 'abc',
            'EnableEnhancedInstructionSet': '1',
            'EnableFiberSafeOptimizations': 'true',
            'EnableFunctionLevelLinking': 'true',
            'EnableIntrinsicFunctions': 'true',
            'EnablePREfast': 'true',
            'ErrorReporting': '2',
            'ExceptionHandling': '2',
            'ExpandAttributedSource': 'true',
            'FavorSizeOrSpeed': '2',
            'FloatingPointExceptions': 'true',
            'FloatingPointModel': '1',
            'ForceConformanceInForLoopScope': 'false',
            'ForcedIncludeFiles': 'def',
            'ForcedUsingFiles': 'ge',
            'GeneratePreprocessedFile': '2',
            'GenerateXMLDocumentationFiles': 'true',
            'IgnoreStandardIncludePath': 'true',
            'InlineFunctionExpansion': '1',
            'KeepComments': 'true',
            'MinimalRebuild': 'true',
            'ObjectFile': '$(IntDir)\\b',
            'OmitDefaultLibName': 'true',
            'OmitFramePointers': 'true',
            'OpenMP': 'true',
            'Optimization': '3',
            'PrecompiledHeaderFile': '$(IntDir)\\$(TargetName).pche',
            'PrecompiledHeaderThrough': 'StdAfx.hd',
            'PreprocessorDefinitions': 'WIN32;_DEBUG;_CONSOLE',
            'ProgramDataBaseFileName': '$(IntDir)\\vc90b.pdb',
            'RuntimeLibrary': '3',
            'RuntimeTypeInfo': 'false',
            'ShowIncludes': 'true',
            'SmallerTypeCheck': 'true',
            'StringPooling': 'true',
            'StructMemberAlignment': '3',
            'SuppressStartupBanner': 'false',
            'TreatWChar_tAsBuiltInType': 'false',
            'UndefineAllPreprocessorDefinitions': 'true',
            'UndefinePreprocessorDefinitions': 'wer',
            'UseFullPaths': 'true',
            'UsePrecompiledHeader': '0',
            'UseUnicodeResponseFiles': 'false',
            'WarnAsError': 'true',
            'WarningLevel': '3',
            'WholeProgramOptimization': 'true',
            'XMLDocumentationFileName': '$(IntDir)\\c'},
        'VCLinkerTool': {
            'AdditionalDependencies': 'zx',
            'AdditionalLibraryDirectories': 'asd',
            'AdditionalManifestDependencies': 's2',
            'AdditionalOptions': '/mor2',
            'AddModuleNamesToAssembly': 'd1',
            'AllowIsolation': 'false',
            'AssemblyDebug': '1',
            'AssemblyLinkResource': 'd5',
            'BaseAddress': '23423',
            'CLRImageType': '3',
            'CLRThreadAttribute': '1',
            'CLRUnmanagedCodeCheck': 'true',
            'DataExecutionPrevention': '0',
            'DelayLoadDLLs': 'd4',
            'DelaySign': 'true',
            'Driver': '2',
            'EmbedManagedResourceFile': 'd2',
            'EnableCOMDATFolding': '1',
            'EnableUAC': 'false',
            'EntryPointSymbol': 'f5',
            'ErrorReporting': '2',
            'FixedBaseAddress': '1',
            'ForceSymbolReferences': 'd3',
            'FunctionOrder': 'fssdfsd',
            'GenerateDebugInformation': 'true',
            'GenerateManifest': 'false',
            'GenerateMapFile': 'true',
            'HeapCommitSize': '13',
            'HeapReserveSize': '12',
            'IgnoreAllDefaultLibraries': 'true',
            'IgnoreDefaultLibraryNames': 'flob;flok',
            'IgnoreEmbeddedIDL': 'true',
            'IgnoreImportLibrary': 'true',
            'ImportLibrary': 'f4',
            'KeyContainer': 'f7',
            'KeyFile': 'f6',
            'LargeAddressAware': '2',
            'LinkIncremental': '0',
            'LinkLibraryDependencies': 'false',
            'LinkTimeCodeGeneration': '1',
            'ManifestFile':
            '$(IntDir)\\$(TargetFileName).2intermediate.manifest',
            'MapExports': 'true',
            'MapFileName': 'd5',
            'MergedIDLBaseFileName': 'f2',
            'MergeSections': 'f5',
            'MidlCommandFile': 'f1',
            'ModuleDefinitionFile': 'sdsd',
            'OptimizeForWindows98': '2',
            'OptimizeReferences': '2',
            'OutputFile': '$(OutDir)\\$(ProjectName)2.exe',
            'PerUserRedirection': 'true',
            'Profile': 'true',
            'ProfileGuidedDatabase': '$(TargetDir)$(TargetName).pgdd',
            'ProgramDatabaseFile': 'Flob.pdb',
            'RandomizedBaseAddress': '1',
            'RegisterOutput': 'true',
            'ResourceOnlyDLL': 'true',
            'SetChecksum': 'false',
            'ShowProgress': '1',
            'StackCommitSize': '15',
            'StackReserveSize': '14',
            'StripPrivateSymbols': 'd3',
            'SubSystem': '1',
            'SupportUnloadOfDelayLoadedDLL': 'true',
            'SuppressStartupBanner': 'false',
            'SwapRunFromCD': 'true',
            'SwapRunFromNet': 'true',
            'TargetMachine': '1',
            'TerminalServerAware': '1',
            'TurnOffAssemblyGeneration': 'true',
            'TypeLibraryFile': 'f3',
            'TypeLibraryResourceID': '12',
            'UACExecutionLevel': '2',
            'UACUIAccess': 'true',
            'UseLibraryDependencyInputs': 'true',
            'UseUnicodeResponseFiles': 'false',
            'Version': '333'},
        'VCResourceCompilerTool': {
            'AdditionalIncludeDirectories': 'f3',
            'AdditionalOptions': '/more3',
            'Culture': '3084',
            'IgnoreStandardIncludePath': 'true',
            'PreprocessorDefinitions': '_UNICODE;UNICODE2',
            'ResourceOutputFileName': '$(IntDir)/$(InputName)3.res',
            'ShowProgress': 'true'},
        'VCManifestTool': {
            'AdditionalManifestFiles': 'sfsdfsd',
            'AdditionalOptions': 'afdsdafsd',
            'AssemblyIdentity': 'sddfdsadfsa',
            'ComponentFileName': 'fsdfds',
            'DependencyInformationFile': '$(IntDir)\\mt.depdfd',
            'EmbedManifest': 'false',
            'GenerateCatalogFiles': 'true',
            'InputResourceManifests': 'asfsfdafs',
            'ManifestResourceFile':
            '$(IntDir)\\$(TargetFileName).embed.manifest.resfdsf',
            'OutputManifestFile': '$(TargetPath).manifestdfs',
            'RegistrarScriptFile': 'sdfsfd',
            'ReplacementsFile': 'sdffsd',
            'SuppressStartupBanner': 'false',
            'TypeLibraryFile': 'sfsd',
            'UpdateFileHashes': 'true',
            'UpdateFileHashesSearchPath': 'sfsd',
            'UseFAT32Workaround': 'true',
            'UseUnicodeResponseFiles': 'false',
            'VerboseOutput': 'true'}}
    expected_msbuild_settings = {
        'ClCompile': {
            'AdditionalIncludeDirectories': 'dir1',
            'AdditionalOptions': '/more /J',
            'AdditionalUsingDirectories': 'test',
            'AssemblerListingLocation': '$(IntDir)a',
            'AssemblerOutput': 'AssemblyCode',
            'BasicRuntimeChecks': 'EnableFastChecks',
            'BrowseInformation': 'true',
            'BrowseInformationFile': '$(IntDir)e',
            'BufferSecurityCheck': 'false',
            'CallingConvention': 'FastCall',
            'CompileAs': 'CompileAsC',
            'DebugInformationFormat': 'EditAndContinue',
            'DisableLanguageExtensions': 'true',
            'DisableSpecificWarnings': 'abc',
            'EnableEnhancedInstructionSet': 'StreamingSIMDExtensions',
            'EnableFiberSafeOptimizations': 'true',
            'EnablePREfast': 'true',
            'ErrorReporting': 'Queue',
            'ExceptionHandling': 'Async',
            'ExpandAttributedSource': 'true',
            'FavorSizeOrSpeed': 'Size',
            'FloatingPointExceptions': 'true',
            'FloatingPointModel': 'Strict',
            'ForceConformanceInForLoopScope': 'false',
            'ForcedIncludeFiles': 'def',
            'ForcedUsingFiles': 'ge',
            'FunctionLevelLinking': 'true',
            'GenerateXMLDocumentationFiles': 'true',
            'IgnoreStandardIncludePath': 'true',
            'InlineFunctionExpansion': 'OnlyExplicitInline',
            'IntrinsicFunctions': 'true',
            'MinimalRebuild': 'true',
            'ObjectFileName': '$(IntDir)b',
            'OmitDefaultLibName': 'true',
            'OmitFramePointers': 'true',
            'OpenMPSupport': 'true',
            'Optimization': 'Full',
            'PrecompiledHeader': 'NotUsing',  # Actual conversion gives ''
            'PrecompiledHeaderFile': 'StdAfx.hd',
            'PrecompiledHeaderOutputFile': '$(IntDir)$(TargetName).pche',
            'PreprocessKeepComments': 'true',
            'PreprocessorDefinitions': 'WIN32;_DEBUG;_CONSOLE',
            'PreprocessSuppressLineNumbers': 'true',
            'PreprocessToFile': 'true',
            'ProgramDataBaseFileName': '$(IntDir)vc90b.pdb',
            'RuntimeLibrary': 'MultiThreadedDebugDLL',
            'RuntimeTypeInfo': 'false',
            'ShowIncludes': 'true',
            'SmallerTypeCheck': 'true',
            'StringPooling': 'true',
            'StructMemberAlignment': '4Bytes',
            'SuppressStartupBanner': 'false',
            'TreatWarningAsError': 'true',
            'TreatWChar_tAsBuiltInType': 'false',
            'UndefineAllPreprocessorDefinitions': 'true',
            'UndefinePreprocessorDefinitions': 'wer',
            'UseFullPaths': 'true',
            'WarningLevel': 'Level3',
            'WholeProgramOptimization': 'true',
            'XMLDocumentationFileName': '$(IntDir)c'},
        'Link': {
            'AdditionalDependencies': 'zx',
            'AdditionalLibraryDirectories': 'asd',
            'AdditionalManifestDependencies': 's2',
            'AdditionalOptions': '/mor2',
            'AddModuleNamesToAssembly': 'd1',
            'AllowIsolation': 'false',
            'AssemblyDebug': 'true',
            'AssemblyLinkResource': 'd5',
            'BaseAddress': '23423',
            'CLRImageType': 'ForceSafeILImage',
            'CLRThreadAttribute': 'MTAThreadingAttribute',
            'CLRUnmanagedCodeCheck': 'true',
            'DataExecutionPrevention': '',
            'DelayLoadDLLs': 'd4',
            'DelaySign': 'true',
            'Driver': 'UpOnly',
            'EmbedManagedResourceFile': 'd2',
            'EnableCOMDATFolding': 'false',
            'EnableUAC': 'false',
            'EntryPointSymbol': 'f5',
            'FixedBaseAddress': 'false',
            'ForceSymbolReferences': 'd3',
            'FunctionOrder': 'fssdfsd',
            'GenerateDebugInformation': 'true',
            'GenerateMapFile': 'true',
            'HeapCommitSize': '13',
            'HeapReserveSize': '12',
            'IgnoreAllDefaultLibraries': 'true',
            'IgnoreEmbeddedIDL': 'true',
            'IgnoreSpecificDefaultLibraries': 'flob;flok',
            'ImportLibrary': 'f4',
            'KeyContainer': 'f7',
            'KeyFile': 'f6',
            'LargeAddressAware': 'true',
            'LinkErrorReporting': 'QueueForNextLogin',
            'LinkTimeCodeGeneration': 'UseLinkTimeCodeGeneration',
            'ManifestFile': '$(IntDir)$(TargetFileName).2intermediate.manifest',
            'MapExports': 'true',
            'MapFileName': 'd5',
            'MergedIDLBaseFileName': 'f2',
            'MergeSections': 'f5',
            'MidlCommandFile': 'f1',
            'ModuleDefinitionFile': 'sdsd',
            'NoEntryPoint': 'true',
            'OptimizeReferences': 'true',
            'OutputFile': '$(OutDir)$(ProjectName)2.exe',
            'PerUserRedirection': 'true',
            'Profile': 'true',
            'ProfileGuidedDatabase': '$(TargetDir)$(TargetName).pgdd',
            'ProgramDatabaseFile': 'Flob.pdb',
            'RandomizedBaseAddress': 'false',
            'RegisterOutput': 'true',
            'SetChecksum': 'false',
            'ShowProgress': 'LinkVerbose',
            'StackCommitSize': '15',
            'StackReserveSize': '14',
            'StripPrivateSymbols': 'd3',
            'SubSystem': 'Console',
            'SupportUnloadOfDelayLoadedDLL': 'true',
            'SuppressStartupBanner': 'false',
            'SwapRunFromCD': 'true',
            'SwapRunFromNET': 'true',
            'TargetMachine': 'MachineX86',
            'TerminalServerAware': 'false',
            'TurnOffAssemblyGeneration': 'true',
            'TypeLibraryFile': 'f3',
            'TypeLibraryResourceID': '12',
            'UACExecutionLevel': 'RequireAdministrator',
            'UACUIAccess': 'true',
            'Version': '333'},
        'ResourceCompile': {
            'AdditionalIncludeDirectories': 'f3',
            'AdditionalOptions': '/more3',
            'Culture': '0x0c0c',
            'IgnoreStandardIncludePath': 'true',
            'PreprocessorDefinitions': '_UNICODE;UNICODE2',
            'ResourceOutputFileName': '$(IntDir)%(Filename)3.res',
            'ShowProgress': 'true'},
        'Manifest': {
            'AdditionalManifestFiles': 'sfsdfsd',
            'AdditionalOptions': 'afdsdafsd',
            'AssemblyIdentity': 'sddfdsadfsa',
            'ComponentFileName': 'fsdfds',
            'GenerateCatalogFiles': 'true',
            'InputResourceManifests': 'asfsfdafs',
            'OutputManifestFile': '$(TargetPath).manifestdfs',
            'RegistrarScriptFile': 'sdfsfd',
            'ReplacementsFile': 'sdffsd',
            'SuppressStartupBanner': 'false',
            'TypeLibraryFile': 'sfsd',
            'UpdateFileHashes': 'true',
            'UpdateFileHashesSearchPath': 'sfsd',
            'VerboseOutput': 'true'},
        'ProjectReference': {
            'LinkLibraryDependencies': 'false',
            'UseLibraryDependencyInputs': 'true'},
        '': {
            'EmbedManifest': 'false',
            'GenerateManifest': 'false',
            'IgnoreImportLibrary': 'true',
            'LinkIncremental': ''
            },
        'ManifestResourceCompile': {
            'ResourceOutputFileName':
            '$(IntDir)$(TargetFileName).embed.manifest.resfdsf'}
        }
    actual_msbuild_settings = MSVSSettings.ConvertToMSBuildSettings(
        msvs_settings,
        self.stderr)
    self.assertEqual(expected_msbuild_settings, actual_msbuild_settings)
    self._ExpectedWarnings([])


if __name__ == '__main__':
  unittest.main()

########NEW FILE########
__FILENAME__ = MSVSToolFile
# Copyright (c) 2012 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Visual Studio project reader/writer."""

import gyp.common
import gyp.easy_xml as easy_xml


class Writer(object):
  """Visual Studio XML tool file writer."""

  def __init__(self, tool_file_path, name):
    """Initializes the tool file.

    Args:
      tool_file_path: Path to the tool file.
      name: Name of the tool file.
    """
    self.tool_file_path = tool_file_path
    self.name = name
    self.rules_section = ['Rules']

  def AddCustomBuildRule(self, name, cmd, description,
                         additional_dependencies,
                         outputs, extensions):
    """Adds a rule to the tool file.

    Args:
      name: Name of the rule.
      description: Description of the rule.
      cmd: Command line of the rule.
      additional_dependencies: other files which may trigger the rule.
      outputs: outputs of the rule.
      extensions: extensions handled by the rule.
    """
    rule = ['CustomBuildRule',
            {'Name': name,
             'ExecutionDescription': description,
             'CommandLine': cmd,
             'Outputs': ';'.join(outputs),
             'FileExtensions': ';'.join(extensions),
             'AdditionalDependencies':
                 ';'.join(additional_dependencies)
            }]
    self.rules_section.append(rule)

  def WriteIfChanged(self):
    """Writes the tool file."""
    content = ['VisualStudioToolFile',
               {'Version': '8.00',
                'Name': self.name
               },
               self.rules_section
               ]
    easy_xml.WriteXmlIfChanged(content, self.tool_file_path,
                               encoding="Windows-1252")

########NEW FILE########
__FILENAME__ = MSVSUserFile
# Copyright (c) 2012 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Visual Studio user preferences file writer."""

import os
import re
import socket # for gethostname

import gyp.common
import gyp.easy_xml as easy_xml


#------------------------------------------------------------------------------

def _FindCommandInPath(command):
  """If there are no slashes in the command given, this function
     searches the PATH env to find the given command, and converts it
     to an absolute path.  We have to do this because MSVS is looking
     for an actual file to launch a debugger on, not just a command
     line.  Note that this happens at GYP time, so anything needing to
     be built needs to have a full path."""
  if '/' in command or '\\' in command:
    # If the command already has path elements (either relative or
    # absolute), then assume it is constructed properly.
    return command
  else:
    # Search through the path list and find an existing file that
    # we can access.
    paths = os.environ.get('PATH','').split(os.pathsep)
    for path in paths:
      item = os.path.join(path, command)
      if os.path.isfile(item) and os.access(item, os.X_OK):
        return item
  return command

def _QuoteWin32CommandLineArgs(args):
  new_args = []
  for arg in args:
    # Replace all double-quotes with double-double-quotes to escape
    # them for cmd shell, and then quote the whole thing if there
    # are any.
    if arg.find('"') != -1:
      arg = '""'.join(arg.split('"'))
      arg = '"%s"' % arg

    # Otherwise, if there are any spaces, quote the whole arg.
    elif re.search(r'[ \t\n]', arg):
      arg = '"%s"' % arg
    new_args.append(arg)
  return new_args

class Writer(object):
  """Visual Studio XML user user file writer."""

  def __init__(self, user_file_path, version, name):
    """Initializes the user file.

    Args:
      user_file_path: Path to the user file.
      version: Version info.
      name: Name of the user file.
    """
    self.user_file_path = user_file_path
    self.version = version
    self.name = name
    self.configurations = {}

  def AddConfig(self, name):
    """Adds a configuration to the project.

    Args:
      name: Configuration name.
    """
    self.configurations[name] = ['Configuration', {'Name': name}]

  def AddDebugSettings(self, config_name, command, environment = {},
                       working_directory=""):
    """Adds a DebugSettings node to the user file for a particular config.

    Args:
      command: command line to run.  First element in the list is the
        executable.  All elements of the command will be quoted if
        necessary.
      working_directory: other files which may trigger the rule. (optional)
    """
    command = _QuoteWin32CommandLineArgs(command)

    abs_command = _FindCommandInPath(command[0])

    if environment and isinstance(environment, dict):
      env_list = ['%s="%s"' % (key, val)
                  for (key,val) in environment.iteritems()]
      environment = ' '.join(env_list)
    else:
      environment = ''

    n_cmd = ['DebugSettings',
             {'Command': abs_command,
              'WorkingDirectory': working_directory,
              'CommandArguments': " ".join(command[1:]),
              'RemoteMachine': socket.gethostname(),
              'Environment': environment,
              'EnvironmentMerge': 'true',
              # Currently these are all "dummy" values that we're just setting
              # in the default manner that MSVS does it.  We could use some of
              # these to add additional capabilities, I suppose, but they might
              # not have parity with other platforms then.
              'Attach': 'false',
              'DebuggerType': '3',  # 'auto' debugger
              'Remote': '1',
              'RemoteCommand': '',
              'HttpUrl': '',
              'PDBPath': '',
              'SQLDebugging': '',
              'DebuggerFlavor': '0',
              'MPIRunCommand': '',
              'MPIRunArguments': '',
              'MPIRunWorkingDirectory': '',
              'ApplicationCommand': '',
              'ApplicationArguments': '',
              'ShimCommand': '',
              'MPIAcceptMode': '',
              'MPIAcceptFilter': ''
             }]

    # Find the config, and add it if it doesn't exist.
    if config_name not in self.configurations:
      self.AddConfig(config_name)

    # Add the DebugSettings onto the appropriate config.
    self.configurations[config_name].append(n_cmd)

  def WriteIfChanged(self):
    """Writes the user file."""
    configs = ['Configurations']
    for config, spec in sorted(self.configurations.iteritems()):
      configs.append(spec)

    content = ['VisualStudioUserFile',
               {'Version': self.version.ProjectVersion(),
                'Name': self.name
               },
               configs]
    easy_xml.WriteXmlIfChanged(content, self.user_file_path,
                               encoding="Windows-1252")

########NEW FILE########
__FILENAME__ = MSVSVersion
# Copyright (c) 2012 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Handle version information related to Visual Stuio."""

import errno
import os
import re
import subprocess
import sys
import gyp


class VisualStudioVersion(object):
  """Information regarding a version of Visual Studio."""

  def __init__(self, short_name, description,
               solution_version, project_version, flat_sln, uses_vcxproj,
               path, sdk_based, default_toolset=None):
    self.short_name = short_name
    self.description = description
    self.solution_version = solution_version
    self.project_version = project_version
    self.flat_sln = flat_sln
    self.uses_vcxproj = uses_vcxproj
    self.path = path
    self.sdk_based = sdk_based
    self.default_toolset = default_toolset

  def ShortName(self):
    return self.short_name

  def Description(self):
    """Get the full description of the version."""
    return self.description

  def SolutionVersion(self):
    """Get the version number of the sln files."""
    return self.solution_version

  def ProjectVersion(self):
    """Get the version number of the vcproj or vcxproj files."""
    return self.project_version

  def FlatSolution(self):
    return self.flat_sln

  def UsesVcxproj(self):
    """Returns true if this version uses a vcxproj file."""
    return self.uses_vcxproj

  def ProjectExtension(self):
    """Returns the file extension for the project."""
    return self.uses_vcxproj and '.vcxproj' or '.vcproj'

  def Path(self):
    """Returns the path to Visual Studio installation."""
    return self.path

  def ToolPath(self, tool):
    """Returns the path to a given compiler tool. """
    return os.path.normpath(os.path.join(self.path, "VC/bin", tool))

  def DefaultToolset(self):
    """Returns the msbuild toolset version that will be used in the absence
    of a user override."""
    return self.default_toolset

  def SetupScript(self, target_arch):
    """Returns a command (with arguments) to be used to set up the
    environment."""
    # Check if we are running in the SDK command line environment and use
    # the setup script from the SDK if so. |target_arch| should be either
    # 'x86' or 'x64'.
    assert target_arch in ('x86', 'x64')
    sdk_dir = os.environ.get('WindowsSDKDir')
    if self.sdk_based and sdk_dir:
      return [os.path.normpath(os.path.join(sdk_dir, 'Bin/SetEnv.Cmd')),
              '/' + target_arch]
    else:
      # We don't use VC/vcvarsall.bat for x86 because vcvarsall calls
      # vcvars32, which it can only find if VS??COMNTOOLS is set, which it
      # isn't always.
      if target_arch == 'x86':
        return [os.path.normpath(
          os.path.join(self.path, 'Common7/Tools/vsvars32.bat'))]
      else:
        assert target_arch == 'x64'
        arg = 'x86_amd64'
        if (os.environ.get('PROCESSOR_ARCHITECTURE') == 'AMD64' or
            os.environ.get('PROCESSOR_ARCHITEW6432') == 'AMD64'):
          # Use the 64-on-64 compiler if we can.
          arg = 'amd64'
        return [os.path.normpath(
            os.path.join(self.path, 'VC/vcvarsall.bat')), arg]


def _RegistryQueryBase(sysdir, key, value):
  """Use reg.exe to read a particular key.

  While ideally we might use the win32 module, we would like gyp to be
  python neutral, so for instance cygwin python lacks this module.

  Arguments:
    sysdir: The system subdirectory to attempt to launch reg.exe from.
    key: The registry key to read from.
    value: The particular value to read.
  Return:
    stdout from reg.exe, or None for failure.
  """
  # Skip if not on Windows or Python Win32 setup issue
  if sys.platform not in ('win32', 'cygwin'):
    return None
  # Setup params to pass to and attempt to launch reg.exe
  cmd = [os.path.join(os.environ.get('WINDIR', ''), sysdir, 'reg.exe'),
         'query', key]
  if value:
    cmd.extend(['/v', value])
  p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  # Obtain the stdout from reg.exe, reading to the end so p.returncode is valid
  # Note that the error text may be in [1] in some cases
  text = p.communicate()[0]
  # Check return code from reg.exe; officially 0==success and 1==error
  if p.returncode:
    return None
  return text


def _RegistryQuery(key, value=None):
  """Use reg.exe to read a particular key through _RegistryQueryBase.

  First tries to launch from %WinDir%\Sysnative to avoid WoW64 redirection. If
  that fails, it falls back to System32.  Sysnative is available on Vista and
  up and available on Windows Server 2003 and XP through KB patch 942589. Note
  that Sysnative will always fail if using 64-bit python due to it being a
  virtual directory and System32 will work correctly in the first place.

  KB 942589 - http://support.microsoft.com/kb/942589/en-us.

  Arguments:
    key: The registry key.
    value: The particular registry value to read (optional).
  Return:
    stdout from reg.exe, or None for failure.
  """
  text = None
  try:
    text = _RegistryQueryBase('Sysnative', key, value)
  except OSError, e:
    if e.errno == errno.ENOENT:
      text = _RegistryQueryBase('System32', key, value)
    else:
      raise
  return text


def _RegistryGetValue(key, value):
  """Use reg.exe to obtain the value of a registry key.

  Args:
    key: The registry key.
    value: The particular registry value to read.
  Return:
    contents of the registry key's value, or None on failure.
  """
  text = _RegistryQuery(key, value)
  if not text:
    return None
  # Extract value.
  match = re.search(r'REG_\w+\s+([^\r]+)\r\n', text)
  if not match:
    return None
  return match.group(1)


def _RegistryKeyExists(key):
  """Use reg.exe to see if a key exists.

  Args:
    key: The registry key to check.
  Return:
    True if the key exists
  """
  if not _RegistryQuery(key):
    return False
  return True


def _CreateVersion(name, path, sdk_based=False):
  """Sets up MSVS project generation.

  Setup is based off the GYP_MSVS_VERSION environment variable or whatever is
  autodetected if GYP_MSVS_VERSION is not explicitly specified. If a version is
  passed in that doesn't match a value in versions python will throw a error.
  """
  if path:
    path = os.path.normpath(path)
  versions = {
      '2012': VisualStudioVersion('2012',
                                  'Visual Studio 2012',
                                  solution_version='12.00',
                                  project_version='4.0',
                                  flat_sln=False,
                                  uses_vcxproj=True,
                                  path=path,
                                  sdk_based=sdk_based,
                                  default_toolset='v110'),
      '2012e': VisualStudioVersion('2012e',
                                   'Visual Studio 2012',
                                   solution_version='12.00',
                                   project_version='4.0',
                                   flat_sln=True,
                                   uses_vcxproj=True,
                                   path=path,
                                   sdk_based=sdk_based,
                                   default_toolset='v110'),
      '2010': VisualStudioVersion('2010',
                                  'Visual Studio 2010',
                                  solution_version='11.00',
                                  project_version='4.0',
                                  flat_sln=False,
                                  uses_vcxproj=True,
                                  path=path,
                                  sdk_based=sdk_based),
      '2010e': VisualStudioVersion('2010e',
                                   'Visual Studio 2010',
                                   solution_version='11.00',
                                   project_version='4.0',
                                   flat_sln=True,
                                   uses_vcxproj=True,
                                   path=path,
                                   sdk_based=sdk_based),
      '2008': VisualStudioVersion('2008',
                                  'Visual Studio 2008',
                                  solution_version='10.00',
                                  project_version='9.00',
                                  flat_sln=False,
                                  uses_vcxproj=False,
                                  path=path,
                                  sdk_based=sdk_based),
      '2008e': VisualStudioVersion('2008e',
                                   'Visual Studio 2008',
                                   solution_version='10.00',
                                   project_version='9.00',
                                   flat_sln=True,
                                   uses_vcxproj=False,
                                   path=path,
                                   sdk_based=sdk_based),
      '2005': VisualStudioVersion('2005',
                                  'Visual Studio 2005',
                                  solution_version='9.00',
                                  project_version='8.00',
                                  flat_sln=False,
                                  uses_vcxproj=False,
                                  path=path,
                                  sdk_based=sdk_based),
      '2005e': VisualStudioVersion('2005e',
                                   'Visual Studio 2005',
                                   solution_version='9.00',
                                   project_version='8.00',
                                   flat_sln=True,
                                   uses_vcxproj=False,
                                   path=path,
                                   sdk_based=sdk_based),
  }
  return versions[str(name)]


def _ConvertToCygpath(path):
  """Convert to cygwin path if we are using cygwin."""
  if sys.platform == 'cygwin':
    p = subprocess.Popen(['cygpath', path], stdout=subprocess.PIPE)
    path = p.communicate()[0].strip()
  return path


def _DetectVisualStudioVersions(versions_to_check, force_express):
  """Collect the list of installed visual studio versions.

  Returns:
    A list of visual studio versions installed in descending order of
    usage preference.
    Base this on the registry and a quick check if devenv.exe exists.
    Only versions 8-10 are considered.
    Possibilities are:
      2005(e) - Visual Studio 2005 (8)
      2008(e) - Visual Studio 2008 (9)
      2010(e) - Visual Studio 2010 (10)
      2012(e) - Visual Studio 2012 (11)
    Where (e) is e for express editions of MSVS and blank otherwise.
  """
  version_to_year = {
      '8.0': '2005', '9.0': '2008', '10.0': '2010', '11.0': '2012'}
  versions = []
  for version in versions_to_check:
    # Old method of searching for which VS version is installed
    # We don't use the 2010-encouraged-way because we also want to get the
    # path to the binaries, which it doesn't offer.
    keys = [r'HKLM\Software\Microsoft\VisualStudio\%s' % version,
            r'HKLM\Software\Wow6432Node\Microsoft\VisualStudio\%s' % version,
            r'HKLM\Software\Microsoft\VCExpress\%s' % version,
            r'HKLM\Software\Wow6432Node\Microsoft\VCExpress\%s' % version]
    for index in range(len(keys)):
      path = _RegistryGetValue(keys[index], 'InstallDir')
      if not path:
        continue
      path = _ConvertToCygpath(path)
      # Check for full.
      full_path = os.path.join(path, 'devenv.exe')
      express_path = os.path.join(path, 'vcexpress.exe')
      if not force_express and os.path.exists(full_path):
        # Add this one.
        versions.append(_CreateVersion(version_to_year[version],
            os.path.join(path, '..', '..')))
      # Check for express.
      elif os.path.exists(express_path):
        # Add this one.
        versions.append(_CreateVersion(version_to_year[version] + 'e',
            os.path.join(path, '..', '..')))

    # The old method above does not work when only SDK is installed.
    keys = [r'HKLM\Software\Microsoft\VisualStudio\SxS\VC7',
            r'HKLM\Software\Wow6432Node\Microsoft\VisualStudio\SxS\VC7']
    for index in range(len(keys)):
      path = _RegistryGetValue(keys[index], version)
      if not path:
        continue
      path = _ConvertToCygpath(path)
      versions.append(_CreateVersion(version_to_year[version] + 'e',
          os.path.join(path, '..'), sdk_based=True))

  return versions


def SelectVisualStudioVersion(version='auto'):
  """Select which version of Visual Studio projects to generate.

  Arguments:
    version: Hook to allow caller to force a particular version (vs auto).
  Returns:
    An object representing a visual studio project format version.
  """
  # In auto mode, check environment variable for override.
  if version == 'auto':
    version = os.environ.get('GYP_MSVS_VERSION', 'auto')
  version_map = {
    'auto': ('10.0', '9.0', '8.0', '11.0'),
    '2005': ('8.0',),
    '2005e': ('8.0',),
    '2008': ('9.0',),
    '2008e': ('9.0',),
    '2010': ('10.0',),
    '2010e': ('10.0',),
    '2012': ('11.0',),
    '2012e': ('11.0',),
  }
  version = str(version)
  versions = _DetectVisualStudioVersions(version_map[version], 'e' in version)
  if not versions:
    if version == 'auto':
      # Default to 2005 if we couldn't find anything
      return _CreateVersion('2005', None)
    else:
      return _CreateVersion(version, None)
  return versions[0]

########NEW FILE########
__FILENAME__ = msvs_emulation
# Copyright (c) 2012 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
This module helps emulate Visual Studio 2008 behavior on top of other
build systems, primarily ninja.
"""

import os
import re
import subprocess
import sys

import gyp.MSVSVersion

windows_quoter_regex = re.compile(r'(\\*)"')

def QuoteForRspFile(arg):
  """Quote a command line argument so that it appears as one argument when
  processed via cmd.exe and parsed by CommandLineToArgvW (as is typical for
  Windows programs)."""
  # See http://goo.gl/cuFbX and http://goo.gl/dhPnp including the comment
  # threads. This is actually the quoting rules for CommandLineToArgvW, not
  # for the shell, because the shell doesn't do anything in Windows. This
  # works more or less because most programs (including the compiler, etc.)
  # use that function to handle command line arguments.

  # For a literal quote, CommandLineToArgvW requires 2n+1 backslashes
  # preceding it, and results in n backslashes + the quote. So we substitute
  # in 2* what we match, +1 more, plus the quote.
  arg = windows_quoter_regex.sub(lambda mo: 2 * mo.group(1) + '\\"', arg)

  # %'s also need to be doubled otherwise they're interpreted as batch
  # positional arguments. Also make sure to escape the % so that they're
  # passed literally through escaping so they can be singled to just the
  # original %. Otherwise, trying to pass the literal representation that
  # looks like an environment variable to the shell (e.g. %PATH%) would fail.
  arg = arg.replace('%', '%%')

  # These commands are used in rsp files, so no escaping for the shell (via ^)
  # is necessary.

  # Finally, wrap the whole thing in quotes so that the above quote rule
  # applies and whitespace isn't a word break.
  return '"' + arg + '"'


def EncodeRspFileList(args):
  """Process a list of arguments using QuoteCmdExeArgument."""
  # Note that the first argument is assumed to be the command. Don't add
  # quotes around it because then built-ins like 'echo', etc. won't work.
  # Take care to normpath only the path in the case of 'call ../x.bat' because
  # otherwise the whole thing is incorrectly interpreted as a path and not
  # normalized correctly.
  if not args: return ''
  if args[0].startswith('call '):
    call, program = args[0].split(' ', 1)
    program = call + ' ' + os.path.normpath(program)
  else:
    program = os.path.normpath(args[0])
  return program + ' ' + ' '.join(QuoteForRspFile(arg) for arg in args[1:])


def _GenericRetrieve(root, default, path):
  """Given a list of dictionary keys |path| and a tree of dicts |root|, find
  value at path, or return |default| if any of the path doesn't exist."""
  if not root:
    return default
  if not path:
    return root
  return _GenericRetrieve(root.get(path[0]), default, path[1:])


def _AddPrefix(element, prefix):
  """Add |prefix| to |element| or each subelement if element is iterable."""
  if element is None:
    return element
  # Note, not Iterable because we don't want to handle strings like that.
  if isinstance(element, list) or isinstance(element, tuple):
    return [prefix + e for e in element]
  else:
    return prefix + element


def _DoRemapping(element, map):
  """If |element| then remap it through |map|. If |element| is iterable then
  each item will be remapped. Any elements not found will be removed."""
  if map is not None and element is not None:
    if not callable(map):
      map = map.get # Assume it's a dict, otherwise a callable to do the remap.
    if isinstance(element, list) or isinstance(element, tuple):
      element = filter(None, [map(elem) for elem in element])
    else:
      element = map(element)
  return element


def _AppendOrReturn(append, element):
  """If |append| is None, simply return |element|. If |append| is not None,
  then add |element| to it, adding each item in |element| if it's a list or
  tuple."""
  if append is not None and element is not None:
    if isinstance(element, list) or isinstance(element, tuple):
      append.extend(element)
    else:
      append.append(element)
  else:
    return element


def _FindDirectXInstallation():
  """Try to find an installation location for the DirectX SDK. Check for the
  standard environment variable, and if that doesn't exist, try to find
  via the registry. May return None if not found in either location."""
  # Return previously calculated value, if there is one
  if hasattr(_FindDirectXInstallation, 'dxsdk_dir'):
    return _FindDirectXInstallation.dxsdk_dir

  dxsdk_dir = os.environ.get('DXSDK_DIR')
  if not dxsdk_dir:
    # Setup params to pass to and attempt to launch reg.exe.
    cmd = ['reg.exe', 'query', r'HKLM\Software\Microsoft\DirectX', '/s']
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for line in p.communicate()[0].splitlines():
      if 'InstallPath' in line:
        dxsdk_dir = line.split('    ')[3] + "\\"

  # Cache return value
  _FindDirectXInstallation.dxsdk_dir = dxsdk_dir
  return dxsdk_dir


class MsvsSettings(object):
  """A class that understands the gyp 'msvs_...' values (especially the
  msvs_settings field). They largely correpond to the VS2008 IDE DOM. This
  class helps map those settings to command line options."""

  def __init__(self, spec, generator_flags):
    self.spec = spec
    self.vs_version = GetVSVersion(generator_flags)
    self.dxsdk_dir = _FindDirectXInstallation()

    # Try to find an installation location for the Windows DDK by checking
    # the WDK_DIR environment variable, may be None.
    self.wdk_dir = os.environ.get('WDK_DIR')

    supported_fields = [
        ('msvs_configuration_attributes', dict),
        ('msvs_settings', dict),
        ('msvs_system_include_dirs', list),
        ('msvs_disabled_warnings', list),
        ('msvs_precompiled_header', str),
        ('msvs_precompiled_source', str),
        ('msvs_configuration_platform', str),
        ('msvs_target_platform', str),
        ]
    configs = spec['configurations']
    for field, default in supported_fields:
      setattr(self, field, {})
      for configname, config in configs.iteritems():
        getattr(self, field)[configname] = config.get(field, default())

    self.msvs_cygwin_dirs = spec.get('msvs_cygwin_dirs', ['.'])

  def GetVSMacroEnv(self, base_to_build=None, config=None):
    """Get a dict of variables mapping internal VS macro names to their gyp
    equivalents."""
    target_platform = 'Win32' if self.GetArch(config) == 'x86' else 'x64'
    replacements = {
        '$(VSInstallDir)': self.vs_version.Path(),
        '$(VCInstallDir)': os.path.join(self.vs_version.Path(), 'VC') + '\\',
        '$(OutDir)\\': base_to_build + '\\' if base_to_build else '',
        '$(IntDir)': '$!INTERMEDIATE_DIR',
        '$(InputPath)': '${source}',
        '$(InputName)': '${root}',
        '$(ProjectName)': self.spec['target_name'],
        '$(PlatformName)': target_platform,
        '$(ProjectDir)\\': '',
    }
    # Chromium uses DXSDK_DIR in include/lib paths, but it may or may not be
    # set. This happens when the SDK is sync'd via src-internal, rather than
    # by typical end-user installation of the SDK. If it's not set, we don't
    # want to leave the unexpanded variable in the path, so simply strip it.
    replacements['$(DXSDK_DIR)'] = self.dxsdk_dir if self.dxsdk_dir else ''
    replacements['$(WDK_DIR)'] = self.wdk_dir if self.wdk_dir else ''
    return replacements

  def ConvertVSMacros(self, s, base_to_build=None, config=None):
    """Convert from VS macro names to something equivalent."""
    env = self.GetVSMacroEnv(base_to_build, config=config)
    return ExpandMacros(s, env)

  def AdjustLibraries(self, libraries):
    """Strip -l from library if it's specified with that."""
    return [lib[2:] if lib.startswith('-l') else lib for lib in libraries]

  def _GetAndMunge(self, field, path, default, prefix, append, map):
    """Retrieve a value from |field| at |path| or return |default|. If
    |append| is specified, and the item is found, it will be appended to that
    object instead of returned. If |map| is specified, results will be
    remapped through |map| before being returned or appended."""
    result = _GenericRetrieve(field, default, path)
    result = _DoRemapping(result, map)
    result = _AddPrefix(result, prefix)
    return _AppendOrReturn(append, result)

  class _GetWrapper(object):
    def __init__(self, parent, field, base_path, append=None):
      self.parent = parent
      self.field = field
      self.base_path = [base_path]
      self.append = append
    def __call__(self, name, map=None, prefix='', default=None):
      return self.parent._GetAndMunge(self.field, self.base_path + [name],
          default=default, prefix=prefix, append=self.append, map=map)

  def GetArch(self, config):
    """Get architecture based on msvs_configuration_platform and
    msvs_target_platform. Returns either 'x86' or 'x64'."""
    configuration_platform = self.msvs_configuration_platform.get(config, '')
    platform = self.msvs_target_platform.get(config, '')
    if not platform: # If no specific override, use the configuration's.
      platform = configuration_platform
    # Map from platform to architecture.
    return {'Win32': 'x86', 'x64': 'x64'}.get(platform, 'x86')

  def _TargetConfig(self, config):
    """Returns the target-specific configuration."""
    # There's two levels of architecture/platform specification in VS. The
    # first level is globally for the configuration (this is what we consider
    # "the" config at the gyp level, which will be something like 'Debug' or
    # 'Release_x64'), and a second target-specific configuration, which is an
    # override for the global one. |config| is remapped here to take into
    # account the local target-specific overrides to the global configuration.
    arch = self.GetArch(config)
    if arch == 'x64' and not config.endswith('_x64'):
      config += '_x64'
    if arch == 'x86' and config.endswith('_x64'):
      config = config.rsplit('_', 1)[0]
    return config

  def _Setting(self, path, config,
              default=None, prefix='', append=None, map=None):
    """_GetAndMunge for msvs_settings."""
    return self._GetAndMunge(
        self.msvs_settings[config], path, default, prefix, append, map)

  def _ConfigAttrib(self, path, config,
                   default=None, prefix='', append=None, map=None):
    """_GetAndMunge for msvs_configuration_attributes."""
    return self._GetAndMunge(
        self.msvs_configuration_attributes[config],
        path, default, prefix, append, map)

  def AdjustIncludeDirs(self, include_dirs, config):
    """Updates include_dirs to expand VS specific paths, and adds the system
    include dirs used for platform SDK and similar."""
    config = self._TargetConfig(config)
    includes = include_dirs + self.msvs_system_include_dirs[config]
    includes.extend(self._Setting(
      ('VCCLCompilerTool', 'AdditionalIncludeDirectories'), config, default=[]))
    return [self.ConvertVSMacros(p, config=config) for p in includes]

  def GetComputedDefines(self, config):
    """Returns the set of defines that are injected to the defines list based
    on other VS settings."""
    config = self._TargetConfig(config)
    defines = []
    if self._ConfigAttrib(['CharacterSet'], config) == '1':
      defines.extend(('_UNICODE', 'UNICODE'))
    if self._ConfigAttrib(['CharacterSet'], config) == '2':
      defines.append('_MBCS')
    defines.extend(self._Setting(
        ('VCCLCompilerTool', 'PreprocessorDefinitions'), config, default=[]))
    return defines

  def GetOutputName(self, config, expand_special):
    """Gets the explicitly overridden output name for a target or returns None
    if it's not overridden."""
    config = self._TargetConfig(config)
    type = self.spec['type']
    root = 'VCLibrarianTool' if type == 'static_library' else 'VCLinkerTool'
    # TODO(scottmg): Handle OutputDirectory without OutputFile.
    output_file = self._Setting((root, 'OutputFile'), config)
    if output_file:
      output_file = expand_special(self.ConvertVSMacros(
          output_file, config=config))
    return output_file

  def GetPDBName(self, config, expand_special):
    """Gets the explicitly overridden pdb name for a target or returns None
    if it's not overridden."""
    config = self._TargetConfig(config)
    output_file = self._Setting(('VCLinkerTool', 'ProgramDatabaseFile'), config)
    if output_file:
      output_file = expand_special(self.ConvertVSMacros(
          output_file, config=config))
    return output_file

  def GetCflags(self, config):
    """Returns the flags that need to be added to .c and .cc compilations."""
    config = self._TargetConfig(config)
    cflags = []
    cflags.extend(['/wd' + w for w in self.msvs_disabled_warnings[config]])
    cl = self._GetWrapper(self, self.msvs_settings[config],
                          'VCCLCompilerTool', append=cflags)
    cl('Optimization',
       map={'0': 'd', '1': '1', '2': '2', '3': 'x'}, prefix='/O')
    cl('InlineFunctionExpansion', prefix='/Ob')
    cl('OmitFramePointers', map={'false': '-', 'true': ''}, prefix='/Oy')
    cl('FavorSizeOrSpeed', map={'1': 't', '2': 's'}, prefix='/O')
    cl('WholeProgramOptimization', map={'true': '/GL'})
    cl('WarningLevel', prefix='/W')
    cl('WarnAsError', map={'true': '/WX'})
    cl('DebugInformationFormat',
        map={'1': '7', '3': 'i', '4': 'I'}, prefix='/Z')
    cl('RuntimeTypeInfo', map={'true': '/GR', 'false': '/GR-'})
    cl('EnableFunctionLevelLinking', map={'true': '/Gy', 'false': '/Gy-'})
    cl('MinimalRebuild', map={'true': '/Gm'})
    cl('BufferSecurityCheck', map={'true': '/GS', 'false': '/GS-'})
    cl('BasicRuntimeChecks', map={'1': 's', '2': 'u', '3': '1'}, prefix='/RTC')
    cl('RuntimeLibrary',
        map={'0': 'T', '1': 'Td', '2': 'D', '3': 'Dd'}, prefix='/M')
    cl('ExceptionHandling', map={'1': 'sc','2': 'a'}, prefix='/EH')
    cl('EnablePREfast', map={'true': '/analyze'})
    cl('AdditionalOptions', prefix='')
    # ninja handles parallelism by itself, don't have the compiler do it too.
    cflags = filter(lambda x: not x.startswith('/MP'), cflags)
    return cflags

  def GetPrecompiledHeader(self, config, gyp_to_build_path):
    """Returns an object that handles the generation of precompiled header
    build steps."""
    config = self._TargetConfig(config)
    return _PchHelper(self, config, gyp_to_build_path)

  def _GetPchFlags(self, config, extension):
    """Get the flags to be added to the cflags for precompiled header support.
    """
    config = self._TargetConfig(config)
    # The PCH is only built once by a particular source file. Usage of PCH must
    # only be for the same language (i.e. C vs. C++), so only include the pch
    # flags when the language matches.
    if self.msvs_precompiled_header[config]:
      source_ext = os.path.splitext(self.msvs_precompiled_source[config])[1]
      if _LanguageMatchesForPch(source_ext, extension):
        pch = os.path.split(self.msvs_precompiled_header[config])[1]
        return ['/Yu' + pch, '/FI' + pch, '/Fp${pchprefix}.' + pch + '.pch']
    return  []

  def GetCflagsC(self, config):
    """Returns the flags that need to be added to .c compilations."""
    config = self._TargetConfig(config)
    return self._GetPchFlags(config, '.c')

  def GetCflagsCC(self, config):
    """Returns the flags that need to be added to .cc compilations."""
    config = self._TargetConfig(config)
    return ['/TP'] + self._GetPchFlags(config, '.cc')

  def _GetAdditionalLibraryDirectories(self, root, config, gyp_to_build_path):
    """Get and normalize the list of paths in AdditionalLibraryDirectories
    setting."""
    config = self._TargetConfig(config)
    libpaths = self._Setting((root, 'AdditionalLibraryDirectories'),
                             config, default=[])
    libpaths = [os.path.normpath(
                    gyp_to_build_path(self.ConvertVSMacros(p, config=config)))
                for p in libpaths]
    return ['/LIBPATH:"' + p + '"' for p in libpaths]

  def GetLibFlags(self, config, gyp_to_build_path):
    """Returns the flags that need to be added to lib commands."""
    config = self._TargetConfig(config)
    libflags = []
    lib = self._GetWrapper(self, self.msvs_settings[config],
                          'VCLibrarianTool', append=libflags)
    libflags.extend(self._GetAdditionalLibraryDirectories(
        'VCLibrarianTool', config, gyp_to_build_path))
    lib('AdditionalOptions')
    return libflags

  def _GetDefFileAsLdflags(self, spec, ldflags, gyp_to_build_path):
    """.def files get implicitly converted to a ModuleDefinitionFile for the
    linker in the VS generator. Emulate that behaviour here."""
    def_file = ''
    if spec['type'] in ('shared_library', 'loadable_module', 'executable'):
      def_files = [s for s in spec.get('sources', []) if s.endswith('.def')]
      if len(def_files) == 1:
        ldflags.append('/DEF:"%s"' % gyp_to_build_path(def_files[0]))
      elif len(def_files) > 1:
        raise Exception("Multiple .def files")

  def GetLdflags(self, config, gyp_to_build_path, expand_special,
                 manifest_base_name, is_executable):
    """Returns the flags that need to be added to link commands, and the
    manifest files."""
    config = self._TargetConfig(config)
    ldflags = []
    ld = self._GetWrapper(self, self.msvs_settings[config],
                          'VCLinkerTool', append=ldflags)
    self._GetDefFileAsLdflags(self.spec, ldflags, gyp_to_build_path)
    ld('GenerateDebugInformation', map={'true': '/DEBUG'})
    ld('TargetMachine', map={'1': 'X86', '17': 'X64'}, prefix='/MACHINE:')
    ldflags.extend(self._GetAdditionalLibraryDirectories(
        'VCLinkerTool', config, gyp_to_build_path))
    ld('DelayLoadDLLs', prefix='/DELAYLOAD:')
    out = self.GetOutputName(config, expand_special)
    if out:
      ldflags.append('/OUT:' + out)
    pdb = self.GetPDBName(config, expand_special)
    if pdb:
      ldflags.append('/PDB:' + pdb)
    ld('AdditionalOptions', prefix='')
    ld('SubSystem', map={'1': 'CONSOLE', '2': 'WINDOWS'}, prefix='/SUBSYSTEM:')
    ld('LinkIncremental', map={'1': ':NO', '2': ''}, prefix='/INCREMENTAL')
    ld('FixedBaseAddress', map={'1': ':NO', '2': ''}, prefix='/FIXED')
    ld('RandomizedBaseAddress',
        map={'1': ':NO', '2': ''}, prefix='/DYNAMICBASE')
    ld('DataExecutionPrevention',
        map={'1': ':NO', '2': ''}, prefix='/NXCOMPAT')
    ld('OptimizeReferences', map={'1': 'NOREF', '2': 'REF'}, prefix='/OPT:')
    ld('EnableCOMDATFolding', map={'1': 'NOICF', '2': 'ICF'}, prefix='/OPT:')
    ld('LinkTimeCodeGeneration', map={'1': '/LTCG'})
    ld('IgnoreDefaultLibraryNames', prefix='/NODEFAULTLIB:')
    ld('ResourceOnlyDLL', map={'true': '/NOENTRY'})
    ld('EntryPointSymbol', prefix='/ENTRY:')
    ld('Profile', map={ 'true': '/PROFILE'})
    # TODO(scottmg): This should sort of be somewhere else (not really a flag).
    ld('AdditionalDependencies', prefix='')
    # TODO(scottmg): These too.
    ldflags.extend(('kernel32.lib', 'user32.lib', 'gdi32.lib', 'winspool.lib',
        'comdlg32.lib', 'advapi32.lib', 'shell32.lib', 'ole32.lib',
        'oleaut32.lib', 'uuid.lib', 'odbc32.lib', 'DelayImp.lib'))

    # If the base address is not specifically controlled, DYNAMICBASE should
    # be on by default.
    base_flags = filter(lambda x: 'DYNAMICBASE' in x or x == '/FIXED',
                        ldflags)
    if not base_flags:
      ldflags.append('/DYNAMICBASE')

    # If the NXCOMPAT flag has not been specified, default to on. Despite the
    # documentation that says this only defaults to on when the subsystem is
    # Vista or greater (which applies to the linker), the IDE defaults it on
    # unless it's explicitly off.
    if not filter(lambda x: 'NXCOMPAT' in x, ldflags):
      ldflags.append('/NXCOMPAT')

    have_def_file = filter(lambda x: x.startswith('/DEF:'), ldflags)
    manifest_flags, intermediate_manifest_file = self._GetLdManifestFlags(
        config, manifest_base_name, is_executable and not have_def_file)
    ldflags.extend(manifest_flags)
    manifest_files = self._GetAdditionalManifestFiles(config, gyp_to_build_path)
    manifest_files.append(intermediate_manifest_file)

    return ldflags, manifest_files

  def _GetLdManifestFlags(self, config, name, allow_isolation):
    """Returns the set of flags that need to be added to the link to generate
    a default manifest, as well as the name of the generated file."""
    # Add manifest flags that mirror the defaults in VS. Chromium dev builds
    # do not currently use any non-default settings, but we could parse
    # VCManifestTool blocks if Chromium or other projects need them in the
    # future. Of particular note, we do not yet support EmbedManifest because
    # it complicates incremental linking.
    output_name = name + '.intermediate.manifest'
    flags = [
      '/MANIFEST',
      '/ManifestFile:' + output_name,
      '''/MANIFESTUAC:"level='asInvoker' uiAccess='false'"'''
    ]
    if allow_isolation:
      flags.append('/ALLOWISOLATION')
    return flags, output_name

  def _GetAdditionalManifestFiles(self, config, gyp_to_build_path):
    """Gets additional manifest files that are added to the default one
    generated by the linker."""
    files = self._Setting(('VCManifestTool', 'AdditionalManifestFiles'), config,
                          default=[])
    if (self._Setting(
        ('VCManifestTool', 'EmbedManifest'), config, default='') == 'true'):
      print 'gyp/msvs_emulation.py: "EmbedManifest: true" not yet supported.'
    if isinstance(files, str):
      files = files.split(';')
    return [os.path.normpath(
                gyp_to_build_path(self.ConvertVSMacros(f, config=config)))
            for f in files]

  def IsUseLibraryDependencyInputs(self, config):
    """Returns whether the target should be linked via Use Library Dependency
    Inputs (using component .objs of a given .lib)."""
    config = self._TargetConfig(config)
    uldi = self._Setting(('VCLinkerTool', 'UseLibraryDependencyInputs'), config)
    return uldi == 'true'

  def GetRcflags(self, config, gyp_to_ninja_path):
    """Returns the flags that need to be added to invocations of the resource
    compiler."""
    config = self._TargetConfig(config)
    rcflags = []
    rc = self._GetWrapper(self, self.msvs_settings[config],
        'VCResourceCompilerTool', append=rcflags)
    rc('AdditionalIncludeDirectories', map=gyp_to_ninja_path, prefix='/I')
    rcflags.append('/I' + gyp_to_ninja_path('.'))
    rc('PreprocessorDefinitions', prefix='/d')
    # /l arg must be in hex without leading '0x'
    rc('Culture', prefix='/l', map=lambda x: hex(int(x))[2:])
    return rcflags

  def BuildCygwinBashCommandLine(self, args, path_to_base):
    """Build a command line that runs args via cygwin bash. We assume that all
    incoming paths are in Windows normpath'd form, so they need to be
    converted to posix style for the part of the command line that's passed to
    bash. We also have to do some Visual Studio macro emulation here because
    various rules use magic VS names for things. Also note that rules that
    contain ninja variables cannot be fixed here (for example ${source}), so
    the outer generator needs to make sure that the paths that are written out
    are in posix style, if the command line will be used here."""
    cygwin_dir = os.path.normpath(
        os.path.join(path_to_base, self.msvs_cygwin_dirs[0]))
    cd = ('cd %s' % path_to_base).replace('\\', '/')
    args = [a.replace('\\', '/').replace('"', '\\"') for a in args]
    args = ["'%s'" % a.replace("'", "'\\''") for a in args]
    bash_cmd = ' '.join(args)
    cmd = (
        'call "%s\\setup_env.bat" && set CYGWIN=nontsec && ' % cygwin_dir +
        'bash -c "%s ; %s"' % (cd, bash_cmd))
    return cmd

  def IsRuleRunUnderCygwin(self, rule):
    """Determine if an action should be run under cygwin. If the variable is
    unset, or set to 1 we use cygwin."""
    return int(rule.get('msvs_cygwin_shell',
                        self.spec.get('msvs_cygwin_shell', 1))) != 0

  def _HasExplicitRuleForExtension(self, spec, extension):
    """Determine if there's an explicit rule for a particular extension."""
    for rule in spec.get('rules', []):
      if rule['extension'] == extension:
        return True
    return False

  def HasExplicitIdlRules(self, spec):
    """Determine if there's an explicit rule for idl files. When there isn't we
    need to generate implicit rules to build MIDL .idl files."""
    return self._HasExplicitRuleForExtension(spec, 'idl')

  def HasExplicitAsmRules(self, spec):
    """Determine if there's an explicit rule for asm files. When there isn't we
    need to generate implicit rules to assemble .asm files."""
    return self._HasExplicitRuleForExtension(spec, 'asm')

  def GetIdlBuildData(self, source, config):
    """Determine the implicit outputs for an idl file. Returns output
    directory, outputs, and variables and flags that are required."""
    config = self._TargetConfig(config)
    midl_get = self._GetWrapper(self, self.msvs_settings[config], 'VCMIDLTool')
    def midl(name, default=None):
      return self.ConvertVSMacros(midl_get(name, default=default),
                                  config=config)
    tlb = midl('TypeLibraryName', default='${root}.tlb')
    header = midl('HeaderFileName', default='${root}.h')
    dlldata = midl('DLLDataFileName', default='dlldata.c')
    iid = midl('InterfaceIdentifierFileName', default='${root}_i.c')
    proxy = midl('ProxyFileName', default='${root}_p.c')
    # Note that .tlb is not included in the outputs as it is not always
    # generated depending on the content of the input idl file.
    outdir = midl('OutputDirectory', default='')
    output = [header, dlldata, iid, proxy]
    variables = [('tlb', tlb),
                 ('h', header),
                 ('dlldata', dlldata),
                 ('iid', iid),
                 ('proxy', proxy)]
    # TODO(scottmg): Are there configuration settings to set these flags?
    flags = ['/char', 'signed', '/env', 'win32', '/Oicf']
    return outdir, output, variables, flags


def _LanguageMatchesForPch(source_ext, pch_source_ext):
  c_exts = ('.c',)
  cc_exts = ('.cc', '.cxx', '.cpp')
  return ((source_ext in c_exts and pch_source_ext in c_exts) or
          (source_ext in cc_exts and pch_source_ext in cc_exts))

class PrecompiledHeader(object):
  """Helper to generate dependencies and build rules to handle generation of
  precompiled headers. Interface matches the GCH handler in xcode_emulation.py.
  """
  def __init__(self, settings, config, gyp_to_build_path):
    self.settings = settings
    self.config = config
    self.gyp_to_build_path = gyp_to_build_path

  def _PchHeader(self):
    """Get the header that will appear in an #include line for all source
    files."""
    return os.path.split(self.settings.msvs_precompiled_header[self.config])[1]

  def _PchSource(self):
    """Get the source file that is built once to compile the pch data."""
    return self.gyp_to_build_path(
        self.settings.msvs_precompiled_source[self.config])

  def _PchOutput(self):
    """Get the name of the output of the compiled pch data."""
    return '${pchprefix}.' + self._PchHeader() + '.pch'

  def GetObjDependencies(self, sources, objs):
    """Given a list of sources files and the corresponding object files,
    returns a list of the pch files that should be depended upon. The
    additional wrapping in the return value is for interface compatability
    with make.py on Mac, and xcode_emulation.py."""
    if not self._PchHeader():
      return []
    source = self._PchSource()
    assert source
    pch_ext = os.path.splitext(self._PchSource())[1]
    for source in sources:
      if _LanguageMatchesForPch(os.path.splitext(source)[1], pch_ext):
        return [(None, None, self._PchOutput())]
    return []

  def GetPchBuildCommands(self):
    """Returns [(path_to_pch, language_flag, language, header)].
    |path_to_gch| and |header| are relative to the build directory."""
    header = self._PchHeader()
    source = self._PchSource()
    if not source or not header:
      return []
    ext = os.path.splitext(source)[1]
    lang = 'c' if ext == '.c' else 'cc'
    return [(self._PchOutput(), '/Yc' + header, lang, source)]


vs_version = None
def GetVSVersion(generator_flags):
  global vs_version
  if not vs_version:
    vs_version = gyp.MSVSVersion.SelectVisualStudioVersion(
        generator_flags.get('msvs_version', 'auto'))
  return vs_version

def _GetVsvarsSetupArgs(generator_flags, arch):
  vs = GetVSVersion(generator_flags)
  return vs.SetupScript()

def ExpandMacros(string, expansions):
  """Expand $(Variable) per expansions dict. See MsvsSettings.GetVSMacroEnv
  for the canonical way to retrieve a suitable dict."""
  if '$' in string:
    for old, new in expansions.iteritems():
      assert '$(' not in new, new
      string = string.replace(old, new)
  return string

def _ExtractImportantEnvironment(output_of_set):
  """Extracts environment variables required for the toolchain to run from
  a textual dump output by the cmd.exe 'set' command."""
  envvars_to_save = (
      'goma_.*', # TODO(scottmg): This is ugly, but needed for goma.
      'include',
      'lib',
      'libpath',
      'path',
      'pathext',
      'systemroot',
      'temp',
      'tmp',
      )
  env = {}
  for line in output_of_set.splitlines():
    for envvar in envvars_to_save:
      if re.match(envvar + '=', line.lower()):
        var, setting = line.split('=', 1)
        if envvar == 'path':
          # Our own rules (for running gyp-win-tool) and other actions in
          # Chromium rely on python being in the path. Add the path to this
          # python here so that if it's not in the path when ninja is run
          # later, python will still be found.
          setting = os.path.dirname(sys.executable) + os.pathsep + setting
        env[var.upper()] = setting
        break
  for required in ('SYSTEMROOT', 'TEMP', 'TMP'):
    if required not in env:
      raise Exception('Environment variable "%s" '
                      'required to be set to valid path' % required)
  return env

def _FormatAsEnvironmentBlock(envvar_dict):
  """Format as an 'environment block' directly suitable for CreateProcess.
  Briefly this is a list of key=value\0, terminated by an additional \0. See
  CreateProcess documentation for more details."""
  block = ''
  nul = '\0'
  for key, value in envvar_dict.iteritems():
    block += key + '=' + value + nul
  block += nul
  return block

def GenerateEnvironmentFiles(toplevel_build_dir, generator_flags, open_out):
  """It's not sufficient to have the absolute path to the compiler, linker,
  etc. on Windows, as those tools rely on .dlls being in the PATH. We also
  need to support both x86 and x64 compilers within the same build (to support
  msvs_target_platform hackery). Different architectures require a different
  compiler binary, and different supporting environment variables (INCLUDE,
  LIB, LIBPATH). So, we extract the environment here, wrap all invocations
  of compiler tools (cl, link, lib, rc, midl, etc.) via win_tool.py which
  sets up the environment, and then we do not prefix the compiler with
  an absolute path, instead preferring something like "cl.exe" in the rule
  which will then run whichever the environment setup has put in the path."""
  vs = GetVSVersion(generator_flags)
  for arch in ('x86', 'x64'):
    args = vs.SetupScript(arch)
    args.extend(('&&', 'set'))
    popen = subprocess.Popen(
        args, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    variables, _ = popen.communicate()
    env = _ExtractImportantEnvironment(variables)
    env_block = _FormatAsEnvironmentBlock(env)
    f = open_out(os.path.join(toplevel_build_dir, 'environment.' + arch), 'wb')
    f.write(env_block)
    f.close()

def VerifyMissingSources(sources, build_dir, generator_flags, gyp_to_ninja):
  """Emulate behavior of msvs_error_on_missing_sources present in the msvs
  generator: Check that all regular source files, i.e. not created at run time,
  exist on disk. Missing files cause needless recompilation when building via
  VS, and we want this check to match for people/bots that build using ninja,
  so they're not surprised when the VS build fails."""
  if int(generator_flags.get('msvs_error_on_missing_sources', 0)):
    no_specials = filter(lambda x: '$' not in x, sources)
    relative = [os.path.join(build_dir, gyp_to_ninja(s)) for s in no_specials]
    missing = filter(lambda x: not os.path.exists(x), relative)
    if missing:
      # They'll look like out\Release\..\..\stuff\things.cc, so normalize the
      # path for a slightly less crazy looking output.
      cleaned_up = [os.path.normpath(x) for x in missing]
      raise Exception('Missing input files:\n%s' % '\n'.join(cleaned_up))

########NEW FILE########
__FILENAME__ = ninja_syntax
# This file comes from
#   https://github.com/martine/ninja/blob/master/misc/ninja_syntax.py
# Do not edit!  Edit the upstream one instead.

"""Python module for generating .ninja files.

Note that this is emphatically not a required piece of Ninja; it's
just a helpful utility for build-file-generation systems that already
use Python.
"""

import textwrap
import re

def escape_path(word):
    return word.replace('$ ','$$ ').replace(' ','$ ').replace(':', '$:')

class Writer(object):
    def __init__(self, output, width=78):
        self.output = output
        self.width = width

    def newline(self):
        self.output.write('\n')

    def comment(self, text):
        for line in textwrap.wrap(text, self.width - 2):
            self.output.write('# ' + line + '\n')

    def variable(self, key, value, indent=0):
        if value is None:
            return
        if isinstance(value, list):
            value = ' '.join(filter(None, value))  # Filter out empty strings.
        self._line('%s = %s' % (key, value), indent)

    def rule(self, name, command, description=None, depfile=None,
             generator=False, restat=False, rspfile=None, rspfile_content=None):
        self._line('rule %s' % name)
        self.variable('command', command, indent=1)
        if description:
            self.variable('description', description, indent=1)
        if depfile:
            self.variable('depfile', depfile, indent=1)
        if generator:
            self.variable('generator', '1', indent=1)
        if restat:
            self.variable('restat', '1', indent=1)
        if rspfile:
            self.variable('rspfile', rspfile, indent=1)
        if rspfile_content:
            self.variable('rspfile_content', rspfile_content, indent=1)

    def build(self, outputs, rule, inputs=None, implicit=None, order_only=None,
              variables=None):
        outputs = self._as_list(outputs)
        all_inputs = self._as_list(inputs)[:]
        out_outputs = list(map(escape_path, outputs))
        all_inputs = list(map(escape_path, all_inputs))

        if implicit:
            implicit = map(escape_path, self._as_list(implicit))
            all_inputs.append('|')
            all_inputs.extend(implicit)
        if order_only:
            order_only = map(escape_path, self._as_list(order_only))
            all_inputs.append('||')
            all_inputs.extend(order_only)

        self._line('build %s: %s %s' % (' '.join(out_outputs),
                                        rule,
                                        ' '.join(all_inputs)))

        if variables:
            if isinstance(variables, dict):
                iterator = variables.iteritems()
            else:
                iterator = iter(variables)

            for key, val in iterator:
                self.variable(key, val, indent=1)

        return outputs

    def include(self, path):
        self._line('include %s' % path)

    def subninja(self, path):
        self._line('subninja %s' % path)

    def default(self, paths):
        self._line('default %s' % ' '.join(self._as_list(paths)))

    def _count_dollars_before_index(self, s, i):
      """Returns the number of '$' characters right in front of s[i]."""
      dollar_count = 0
      dollar_index = i - 1
      while dollar_index > 0 and s[dollar_index] == '$':
        dollar_count += 1
        dollar_index -= 1
      return dollar_count

    def _line(self, text, indent=0):
        """Write 'text' word-wrapped at self.width characters."""
        leading_space = '  ' * indent
        while len(leading_space) + len(text) > self.width:
            # The text is too wide; wrap if possible.

            # Find the rightmost space that would obey our width constraint and
            # that's not an escaped space.
            available_space = self.width - len(leading_space) - len(' $')
            space = available_space
            while True:
              space = text.rfind(' ', 0, space)
              if space < 0 or \
                 self._count_dollars_before_index(text, space) % 2 == 0:
                break

            if space < 0:
                # No such space; just use the first unescaped space we can find.
                space = available_space - 1
                while True:
                  space = text.find(' ', space + 1)
                  if space < 0 or \
                     self._count_dollars_before_index(text, space) % 2 == 0:
                    break
            if space < 0:
                # Give up on breaking.
                break

            self.output.write(leading_space + text[0:space] + ' $\n')
            text = text[space+1:]

            # Subsequent lines are continuations, so indent them.
            leading_space = '  ' * (indent+2)

        self.output.write(leading_space + text + '\n')

    def _as_list(self, input):
        if input is None:
            return []
        if isinstance(input, list):
            return input
        return [input]


def escape(string):
    """Escape a string such that it can be embedded into a Ninja file without
    further interpretation."""
    assert '\n' not in string, 'Ninja syntax does not allow newlines'
    # We only have one special metacharacter: '$'.
    return string.replace('$', '$$')

########NEW FILE########
__FILENAME__ = SCons
# Copyright (c) 2012 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
SCons generator.

This contains class definitions and supporting functions for generating
pieces of SCons files for the different types of GYP targets.
"""

import os


def WriteList(fp, list, prefix='',
                        separator=',\n    ',
                        preamble=None,
                        postamble=None):
  fp.write(preamble or '')
  fp.write((separator or ' ').join([prefix + l for l in list]))
  fp.write(postamble or '')


class TargetBase(object):
  """
  Base class for a SCons representation of a GYP target.
  """
  is_ignored = False
  target_prefix = ''
  target_suffix = ''
  def __init__(self, spec):
    self.spec = spec
  def full_product_name(self):
    """
    Returns the full name of the product being built:

      * Uses 'product_name' if it's set, else prefix + 'target_name'.
      * Prepends 'product_dir' if set.
      * Appends SCons suffix variables for the target type (or
        product_extension).
    """
    suffix = self.target_suffix
    product_extension = self.spec.get('product_extension')
    if product_extension:
      suffix = '.' + product_extension
    prefix = self.spec.get('product_prefix', self.target_prefix)
    name = self.spec['target_name']
    name = prefix + self.spec.get('product_name', name) + suffix
    product_dir = self.spec.get('product_dir')
    if product_dir:
      name = os.path.join(product_dir, name)
    else:
      name = os.path.join(self.out_dir, name)
    return name

  def write_input_files(self, fp):
    """
    Writes the definition of the input files (sources).
    """
    sources = self.spec.get('sources')
    if not sources:
      fp.write('\ninput_files = []\n')
      return
    preamble = '\ninput_files = [\n    '
    postamble = ',\n]\n'
    WriteList(fp, map(repr, sources), preamble=preamble, postamble=postamble)

  def builder_call(self):
    """
    Returns the actual SCons builder call to build this target.
    """
    name = self.full_product_name()
    return 'env.%s(env.File(%r), input_files)' % (self.builder_name, name)
  def write_target(self, fp, src_dir='', pre=''):
    """
    Writes the lines necessary to build this target.
    """
    fp.write('\n' + pre)
    fp.write('_outputs = %s\n' % self.builder_call())
    fp.write('target_files.extend(_outputs)\n')


class NoneTarget(TargetBase):
  """
  A GYP target type of 'none', implicitly or explicitly.
  """
  def write_target(self, fp, src_dir='', pre=''):
    fp.write('\ntarget_files.extend(input_files)\n')


class SettingsTarget(TargetBase):
  """
  A GYP target type of 'settings'.
  """
  is_ignored = True


compilable_sources_template = """
_result = []
for infile in input_files:
  if env.compilable(infile):
    if (type(infile) == type('')
        and (infile.startswith(%(src_dir)r)
             or not os.path.isabs(env.subst(infile)))):
      # Force files below the build directory by replacing all '..'
      # elements in the path with '__':
      base, ext = os.path.splitext(os.path.normpath(infile))
      base = [d == '..' and '__' or d for d in base.split('/')]
      base = os.path.join(*base)
      object = '${OBJ_DIR}/${COMPONENT_NAME}/${TARGET_NAME}/' + base
      if not infile.startswith(%(src_dir)r):
        infile = %(src_dir)r + infile
      infile = env.%(name)s(object, infile)[0]
    else:
      infile = env.%(name)s(infile)[0]
  _result.append(infile)
input_files = _result
"""

class CompilableSourcesTargetBase(TargetBase):
  """
  An abstract base class for targets that compile their source files.

  We explicitly transform compilable files into object files,
  even though SCons could infer that for us, because we want
  to control where the object file ends up.  (The implicit rules
  in SCons always put the object file next to the source file.)
  """
  intermediate_builder_name = None
  def write_target(self, fp, src_dir='', pre=''):
    if self.intermediate_builder_name is None:
      raise NotImplementedError
    if src_dir and not src_dir.endswith('/'):
      src_dir += '/'
    variables = {
        'src_dir': src_dir,
        'name': self.intermediate_builder_name,
    }
    fp.write(compilable_sources_template % variables)
    super(CompilableSourcesTargetBase, self).write_target(fp)


class ProgramTarget(CompilableSourcesTargetBase):
  """
  A GYP target type of 'executable'.
  """
  builder_name = 'GypProgram'
  intermediate_builder_name = 'StaticObject'
  target_prefix = '${PROGPREFIX}'
  target_suffix = '${PROGSUFFIX}'
  out_dir = '${TOP_BUILDDIR}'


class StaticLibraryTarget(CompilableSourcesTargetBase):
  """
  A GYP target type of 'static_library'.
  """
  builder_name = 'GypStaticLibrary'
  intermediate_builder_name = 'StaticObject'
  target_prefix = '${LIBPREFIX}'
  target_suffix = '${LIBSUFFIX}'
  out_dir = '${LIB_DIR}'


class SharedLibraryTarget(CompilableSourcesTargetBase):
  """
  A GYP target type of 'shared_library'.
  """
  builder_name = 'GypSharedLibrary'
  intermediate_builder_name = 'SharedObject'
  target_prefix = '${SHLIBPREFIX}'
  target_suffix = '${SHLIBSUFFIX}'
  out_dir = '${LIB_DIR}'


class LoadableModuleTarget(CompilableSourcesTargetBase):
  """
  A GYP target type of 'loadable_module'.
  """
  builder_name = 'GypLoadableModule'
  intermediate_builder_name = 'SharedObject'
  target_prefix = '${SHLIBPREFIX}'
  target_suffix = '${SHLIBSUFFIX}'
  out_dir = '${TOP_BUILDDIR}'


TargetMap = {
  None : NoneTarget,
  'none' : NoneTarget,
  'settings' : SettingsTarget,
  'executable' : ProgramTarget,
  'static_library' : StaticLibraryTarget,
  'shared_library' : SharedLibraryTarget,
  'loadable_module' : LoadableModuleTarget,
}


def Target(spec):
  return TargetMap[spec.get('type')](spec)

########NEW FILE########
__FILENAME__ = sun_tool
#!/usr/bin/env python
# Copyright (c) 2011 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""These functions are executed via gyp-sun-tool when using the Makefile
generator."""

import fcntl
import os
import struct
import subprocess
import sys


def main(args):
  executor = SunTool()
  executor.Dispatch(args)


class SunTool(object):
  """This class performs all the SunOS tooling steps. The methods can either be
  executed directly, or dispatched from an argument list."""

  def Dispatch(self, args):
    """Dispatches a string command to a method."""
    if len(args) < 1:
      raise Exception("Not enough arguments")

    method = "Exec%s" % self._CommandifyName(args[0])
    getattr(self, method)(*args[1:])

  def _CommandifyName(self, name_string):
    """Transforms a tool name like copy-info-plist to CopyInfoPlist"""
    return name_string.title().replace('-', '')

  def ExecFlock(self, lockfile, *cmd_list):
    """Emulates the most basic behavior of Linux's flock(1)."""
    # Rely on exception handling to report errors.
    # Note that the stock python on SunOS has a bug
    # where fcntl.flock(fd, LOCK_EX) always fails
    # with EBADF, that's why we use this F_SETLK
    # hack instead.
    fd = os.open(lockfile, os.O_WRONLY|os.O_NOCTTY|os.O_CREAT, 0666)
    op = struct.pack('hhllhhl', fcntl.F_WRLCK, 0, 0, 0, 0, 0, 0)
    fcntl.fcntl(fd, fcntl.F_SETLK, op)
    return subprocess.call(cmd_list)


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))

########NEW FILE########
__FILENAME__ = win_tool
#!/usr/bin/env python

# Copyright (c) 2012 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utility functions for Windows builds.

These functions are executed via gyp-win-tool when using the ninja generator.
"""

from ctypes import windll, wintypes
import os
import shutil
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def main(args):
  executor = WinTool()
  exit_code = executor.Dispatch(args)
  if exit_code is not None:
    sys.exit(exit_code)


class LinkLock(object):
  """A flock-style lock to limit the number of concurrent links to one.

  Uses a session-local mutex based on the file's directory.
  """
  def __enter__(self):
    name = 'Local\\%s' % BASE_DIR.replace('\\', '_').replace(':', '_')
    self.mutex = windll.kernel32.CreateMutexW(
        wintypes.c_int(0),
        wintypes.c_int(0),
        wintypes.create_unicode_buffer(name))
    assert self.mutex
    result = windll.kernel32.WaitForSingleObject(
        self.mutex, wintypes.c_int(0xFFFFFFFF))
    # 0x80 means another process was killed without releasing the mutex, but
    # that this process has been given ownership. This is fine for our
    # purposes.
    assert result in (0, 0x80), (
        "%s, %s" % (result, windll.kernel32.GetLastError()))

  def __exit__(self, type, value, traceback):
    windll.kernel32.ReleaseMutex(self.mutex)
    windll.kernel32.CloseHandle(self.mutex)


class WinTool(object):
  """This class performs all the Windows tooling steps. The methods can either
  be executed directly, or dispatched from an argument list."""

  def Dispatch(self, args):
    """Dispatches a string command to a method."""
    if len(args) < 1:
      raise Exception("Not enough arguments")

    method = "Exec%s" % self._CommandifyName(args[0])
    return getattr(self, method)(*args[1:])

  def _CommandifyName(self, name_string):
    """Transforms a tool name like recursive-mirror to RecursiveMirror."""
    return name_string.title().replace('-', '')

  def _GetEnv(self, arch):
    """Gets the saved environment from a file for a given architecture."""
    # The environment is saved as an "environment block" (see CreateProcess
    # and msvs_emulation for details). We convert to a dict here.
    # Drop last 2 NULs, one for list terminator, one for trailing vs. separator.
    pairs = open(arch).read()[:-2].split('\0')
    kvs = [item.split('=', 1) for item in pairs]
    return dict(kvs)

  def ExecStamp(self, path):
    """Simple stamp command."""
    open(path, 'w').close()

  def ExecRecursiveMirror(self, source, dest):
    """Emulation of rm -rf out && cp -af in out."""
    if os.path.exists(dest):
      if os.path.isdir(dest):
        shutil.rmtree(dest)
      else:
        os.unlink(dest)
    if os.path.isdir(source):
      shutil.copytree(source, dest)
    else:
      shutil.copy2(source, dest)

  def ExecLinkWrapper(self, arch, *args):
    """Filter diagnostic output from link that looks like:
    '   Creating library ui.dll.lib and object ui.dll.exp'
    This happens when there are exports from the dll or exe.
    """
    with LinkLock():
      env = self._GetEnv(arch)
      popen = subprocess.Popen(args, shell=True, env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
      out, _ = popen.communicate()
      for line in out.splitlines():
        if not line.startswith('   Creating library '):
          print line
      return popen.returncode

  def ExecManifestWrapper(self, arch, *args):
    """Run manifest tool with environment set. Strip out undesirable warning
    (some XML blocks are recognized by the OS loader, but not the manifest
    tool)."""
    env = self._GetEnv(arch)
    popen = subprocess.Popen(args, shell=True, env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, _ = popen.communicate()
    for line in out.splitlines():
      if line and 'manifest authoring warning 81010002' not in line:
        print line
    return popen.returncode

  def ExecMidlWrapper(self, arch, outdir, tlb, h, dlldata, iid, proxy, idl,
                      *flags):
    """Filter noisy filenames output from MIDL compile step that isn't
    quietable via command line flags.
    """
    args = ['midl', '/nologo'] + list(flags) + [
        '/out', outdir,
        '/tlb', tlb,
        '/h', h,
        '/dlldata', dlldata,
        '/iid', iid,
        '/proxy', proxy,
        idl]
    env = self._GetEnv(arch)
    popen = subprocess.Popen(args, shell=True, env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, _ = popen.communicate()
    # Filter junk out of stdout, and write filtered versions. Output we want
    # to filter is pairs of lines that look like this:
    # Processing C:\Program Files (x86)\Microsoft SDKs\...\include\objidl.idl
    # objidl.idl
    lines = out.splitlines()
    prefix = 'Processing '
    processing = set(os.path.basename(x) for x in lines if x.startswith(prefix))
    for line in lines:
      if not line.startswith(prefix) and line not in processing:
        print line
    return popen.returncode

  def ExecAsmWrapper(self, arch, *args):
    """Filter logo banner from invocations of asm.exe."""
    env = self._GetEnv(arch)
    # MSVS doesn't assemble x64 asm files.
    if arch == 'environment.x64':
      return 0
    popen = subprocess.Popen(args, shell=True, env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, _ = popen.communicate()
    for line in out.splitlines():
      if (not line.startswith('Copyright (C) Microsoft Corporation') and
          not line.startswith('Microsoft (R) Macro Assembler') and
          not line.startswith(' Assembling: ') and
          line):
        print line
    return popen.returncode

  def ExecRcWrapper(self, arch, *args):
    """Filter logo banner from invocations of rc.exe. Older versions of RC
    don't support the /nologo flag."""
    env = self._GetEnv(arch)
    popen = subprocess.Popen(args, shell=True, env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, _ = popen.communicate()
    for line in out.splitlines():
      if (not line.startswith('Microsoft (R) Windows (R) Resource Compiler') and
          not line.startswith('Copyright (C) Microsoft Corporation') and
          line):
        print line
    return popen.returncode

  def ExecActionWrapper(self, arch, rspfile, *dir):
    """Runs an action command line from a response file using the environment
    for |arch|. If |dir| is supplied, use that as the working directory."""
    env = self._GetEnv(arch)
    args = open(rspfile).read()
    dir = dir[0] if dir else None
    popen = subprocess.Popen(args, shell=True, env=env, cwd=dir)
    popen.wait()
    return popen.returncode

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))

########NEW FILE########
__FILENAME__ = xcodeproj_file
# Copyright (c) 2012 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Xcode project file generator.

This module is both an Xcode project file generator and a documentation of the
Xcode project file format.  Knowledge of the project file format was gained
based on extensive experience with Xcode, and by making changes to projects in
Xcode.app and observing the resultant changes in the associated project files.

XCODE PROJECT FILES

The generator targets the file format as written by Xcode 3.2 (specifically,
3.2.6), but past experience has taught that the format has not changed
significantly in the past several years, and future versions of Xcode are able
to read older project files.

Xcode project files are "bundled": the project "file" from an end-user's
perspective is actually a directory with an ".xcodeproj" extension.  The
project file from this module's perspective is actually a file inside this
directory, always named "project.pbxproj".  This file contains a complete
description of the project and is all that is needed to use the xcodeproj.
Other files contained in the xcodeproj directory are simply used to store
per-user settings, such as the state of various UI elements in the Xcode
application.

The project.pbxproj file is a property list, stored in a format almost
identical to the NeXTstep property list format.  The file is able to carry
Unicode data, and is encoded in UTF-8.  The root element in the property list
is a dictionary that contains several properties of minimal interest, and two
properties of immense interest.  The most important property is a dictionary
named "objects".  The entire structure of the project is represented by the
children of this property.  The objects dictionary is keyed by unique 96-bit
values represented by 24 uppercase hexadecimal characters.  Each value in the
objects dictionary is itself a dictionary, describing an individual object.

Each object in the dictionary is a member of a class, which is identified by
the "isa" property of each object.  A variety of classes are represented in a
project file.  Objects can refer to other objects by ID, using the 24-character
hexadecimal object key.  A project's objects form a tree, with a root object
of class PBXProject at the root.  As an example, the PBXProject object serves
as parent to an XCConfigurationList object defining the build configurations
used in the project, a PBXGroup object serving as a container for all files
referenced in the project, and a list of target objects, each of which defines
a target in the project.  There are several different types of target object,
such as PBXNativeTarget and PBXAggregateTarget.  In this module, this
relationship is expressed by having each target type derive from an abstract
base named XCTarget.

The project.pbxproj file's root dictionary also contains a property, sibling to
the "objects" dictionary, named "rootObject".  The value of rootObject is a
24-character object key referring to the root PBXProject object in the
objects dictionary.

In Xcode, every file used as input to a target or produced as a final product
of a target must appear somewhere in the hierarchy rooted at the PBXGroup
object referenced by the PBXProject's mainGroup property.  A PBXGroup is
generally represented as a folder in the Xcode application.  PBXGroups can
contain other PBXGroups as well as PBXFileReferences, which are pointers to
actual files.

Each XCTarget contains a list of build phases, represented in this module by
the abstract base XCBuildPhase.  Examples of concrete XCBuildPhase derivations
are PBXSourcesBuildPhase and PBXFrameworksBuildPhase, which correspond to the
"Compile Sources" and "Link Binary With Libraries" phases displayed in the
Xcode application.  Files used as input to these phases (for example, source
files in the former case and libraries and frameworks in the latter) are
represented by PBXBuildFile objects, referenced by elements of "files" lists
in XCTarget objects.  Each PBXBuildFile object refers to a PBXBuildFile
object as a "weak" reference: it does not "own" the PBXBuildFile, which is
owned by the root object's mainGroup or a descendant group.  In most cases, the
layer of indirection between an XCBuildPhase and a PBXFileReference via a
PBXBuildFile appears extraneous, but there's actually one reason for this:
file-specific compiler flags are added to the PBXBuildFile object so as to
allow a single file to be a member of multiple targets while having distinct
compiler flags for each.  These flags can be modified in the Xcode applciation
in the "Build" tab of a File Info window.

When a project is open in the Xcode application, Xcode will rewrite it.  As
such, this module is careful to adhere to the formatting used by Xcode, to
avoid insignificant changes appearing in the file when it is used in the
Xcode application.  This will keep version control repositories happy, and
makes it possible to compare a project file used in Xcode to one generated by
this module to determine if any significant changes were made in the
application.

Xcode has its own way of assigning 24-character identifiers to each object,
which is not duplicated here.  Because the identifier only is only generated
once, when an object is created, and is then left unchanged, there is no need
to attempt to duplicate Xcode's behavior in this area.  The generator is free
to select any identifier, even at random, to refer to the objects it creates,
and Xcode will retain those identifiers and use them when subsequently
rewriting the project file.  However, the generator would choose new random
identifiers each time the project files are generated, leading to difficulties
comparing "used" project files to "pristine" ones produced by this module,
and causing the appearance of changes as every object identifier is changed
when updated projects are checked in to a version control repository.  To
mitigate this problem, this module chooses identifiers in a more deterministic
way, by hashing a description of each object as well as its parent and ancestor
objects.  This strategy should result in minimal "shift" in IDs as successive
generations of project files are produced.

THIS MODULE

This module introduces several classes, all derived from the XCObject class.
Nearly all of the "brains" are built into the XCObject class, which understands
how to create and modify objects, maintain the proper tree structure, compute
identifiers, and print objects.  For the most part, classes derived from
XCObject need only provide a _schema class object, a dictionary that
expresses what properties objects of the class may contain.

Given this structure, it's possible to build a minimal project file by creating
objects of the appropriate types and making the proper connections:

  config_list = XCConfigurationList()
  group = PBXGroup()
  project = PBXProject({'buildConfigurationList': config_list,
                        'mainGroup': group})

With the project object set up, it can be added to an XCProjectFile object.
XCProjectFile is a pseudo-class in the sense that it is a concrete XCObject
subclass that does not actually correspond to a class type found in a project
file.  Rather, it is used to represent the project file's root dictionary.
Printing an XCProjectFile will print the entire project file, including the
full "objects" dictionary.

  project_file = XCProjectFile({'rootObject': project})
  project_file.ComputeIDs()
  project_file.Print()

Xcode project files are always encoded in UTF-8.  This module will accept
strings of either the str class or the unicode class.  Strings of class str
are assumed to already be encoded in UTF-8.  Obviously, if you're just using
ASCII, you won't encounter difficulties because ASCII is a UTF-8 subset.
Strings of class unicode are handled properly and encoded in UTF-8 when
a project file is output.
"""

import gyp.common
import posixpath
import re
import struct
import sys

# hashlib is supplied as of Python 2.5 as the replacement interface for sha
# and other secure hashes.  In 2.6, sha is deprecated.  Import hashlib if
# available, avoiding a deprecation warning under 2.6.  Import sha otherwise,
# preserving 2.4 compatibility.
try:
  import hashlib
  _new_sha1 = hashlib.sha1
except ImportError:
  import sha
  _new_sha1 = sha.new


# See XCObject._EncodeString.  This pattern is used to determine when a string
# can be printed unquoted.  Strings that match this pattern may be printed
# unquoted.  Strings that do not match must be quoted and may be further
# transformed to be properly encoded.  Note that this expression matches the
# characters listed with "+", for 1 or more occurrences: if a string is empty,
# it must not match this pattern, because it needs to be encoded as "".
_unquoted = re.compile('^[A-Za-z0-9$./_]+$')

# Strings that match this pattern are quoted regardless of what _unquoted says.
# Oddly, Xcode will quote any string with a run of three or more underscores.
_quoted = re.compile('___')

# This pattern should match any character that needs to be escaped by
# XCObject._EncodeString.  See that function.
_escaped = re.compile('[\\\\"]|[^ -~]')


# Used by SourceTreeAndPathFromPath
_path_leading_variable = re.compile('^\$\((.*?)\)(/(.*))?$')

def SourceTreeAndPathFromPath(input_path):
  """Given input_path, returns a tuple with sourceTree and path values.

  Examples:
    input_path     (source_tree, output_path)
    '$(VAR)/path'  ('VAR', 'path')
    '$(VAR)'       ('VAR', None)
    'path'         (None, 'path')
  """

  source_group_match = _path_leading_variable.match(input_path)
  if source_group_match:
    source_tree = source_group_match.group(1)
    output_path = source_group_match.group(3)  # This may be None.
  else:
    source_tree = None
    output_path = input_path

  return (source_tree, output_path)

def ConvertVariablesToShellSyntax(input_string):
  return re.sub('\$\((.*?)\)', '${\\1}', input_string)

class XCObject(object):
  """The abstract base of all class types used in Xcode project files.

  Class variables:
    _schema: A dictionary defining the properties of this class.  The keys to
             _schema are string property keys as used in project files.  Values
             are a list of four or five elements:
             [ is_list, property_type, is_strong, is_required, default ]
             is_list: True if the property described is a list, as opposed
                      to a single element.
             property_type: The type to use as the value of the property,
                            or if is_list is True, the type to use for each
                            element of the value's list.  property_type must
                            be an XCObject subclass, or one of the built-in
                            types str, int, or dict.
             is_strong: If property_type is an XCObject subclass, is_strong
                        is True to assert that this class "owns," or serves
                        as parent, to the property value (or, if is_list is
                        True, values).  is_strong must be False if
                        property_type is not an XCObject subclass.
             is_required: True if the property is required for the class.
                          Note that is_required being True does not preclude
                          an empty string ("", in the case of property_type
                          str) or list ([], in the case of is_list True) from
                          being set for the property.
             default: Optional.  If is_requried is True, default may be set
                      to provide a default value for objects that do not supply
                      their own value.  If is_required is True and default
                      is not provided, users of the class must supply their own
                      value for the property.
             Note that although the values of the array are expressed in
             boolean terms, subclasses provide values as integers to conserve
             horizontal space.
    _should_print_single_line: False in XCObject.  Subclasses whose objects
                               should be written to the project file in the
                               alternate single-line format, such as
                               PBXFileReference and PBXBuildFile, should
                               set this to True.
    _encode_transforms: Used by _EncodeString to encode unprintable characters.
                        The index into this list is the ordinal of the
                        character to transform; each value is a string
                        used to represent the character in the output.  XCObject
                        provides an _encode_transforms list suitable for most
                        XCObject subclasses.
    _alternate_encode_transforms: Provided for subclasses that wish to use
                                  the alternate encoding rules.  Xcode seems
                                  to use these rules when printing objects in
                                  single-line format.  Subclasses that desire
                                  this behavior should set _encode_transforms
                                  to _alternate_encode_transforms.
    _hashables: A list of XCObject subclasses that can be hashed by ComputeIDs
                to construct this object's ID.  Most classes that need custom
                hashing behavior should do it by overriding Hashables,
                but in some cases an object's parent may wish to push a
                hashable value into its child, and it can do so by appending
                to _hashables.
  Attributes:
    id: The object's identifier, a 24-character uppercase hexadecimal string.
        Usually, objects being created should not set id until the entire
        project file structure is built.  At that point, UpdateIDs() should
        be called on the root object to assign deterministic values for id to
        each object in the tree.
    parent: The object's parent.  This is set by a parent XCObject when a child
            object is added to it.
    _properties: The object's property dictionary.  An object's properties are
                 described by its class' _schema variable.
  """

  _schema = {}
  _should_print_single_line = False

  # See _EncodeString.
  _encode_transforms = []
  i = 0
  while i < ord(' '):
    _encode_transforms.append('\\U%04x' % i)
    i = i + 1
  _encode_transforms[7] = '\\a'
  _encode_transforms[8] = '\\b'
  _encode_transforms[9] = '\\t'
  _encode_transforms[10] = '\\n'
  _encode_transforms[11] = '\\v'
  _encode_transforms[12] = '\\f'
  _encode_transforms[13] = '\\n'

  _alternate_encode_transforms = list(_encode_transforms)
  _alternate_encode_transforms[9] = chr(9)
  _alternate_encode_transforms[10] = chr(10)
  _alternate_encode_transforms[11] = chr(11)

  def __init__(self, properties=None, id=None, parent=None):
    self.id = id
    self.parent = parent
    self._properties = {}
    self._hashables = []
    self._SetDefaultsFromSchema()
    self.UpdateProperties(properties)

  def __repr__(self):
    try:
      name = self.Name()
    except NotImplementedError:
      return '<%s at 0x%x>' % (self.__class__.__name__, id(self))
    return '<%s %r at 0x%x>' % (self.__class__.__name__, name, id(self))

  def Copy(self):
    """Make a copy of this object.

    The new object will have its own copy of lists and dicts.  Any XCObject
    objects owned by this object (marked "strong") will be copied in the
    new object, even those found in lists.  If this object has any weak
    references to other XCObjects, the same references are added to the new
    object without making a copy.
    """

    that = self.__class__(id=self.id, parent=self.parent)
    for key, value in self._properties.iteritems():
      is_strong = self._schema[key][2]

      if isinstance(value, XCObject):
        if is_strong:
          new_value = value.Copy()
          new_value.parent = that
          that._properties[key] = new_value
        else:
          that._properties[key] = value
      elif isinstance(value, str) or isinstance(value, unicode) or \
           isinstance(value, int):
        that._properties[key] = value
      elif isinstance(value, list):
        if is_strong:
          # If is_strong is True, each element is an XCObject, so it's safe to
          # call Copy.
          that._properties[key] = []
          for item in value:
            new_item = item.Copy()
            new_item.parent = that
            that._properties[key].append(new_item)
        else:
          that._properties[key] = value[:]
      elif isinstance(value, dict):
        # dicts are never strong.
        if is_strong:
          raise TypeError, 'Strong dict for key ' + key + ' in ' + \
                           self.__class__.__name__
        else:
          that._properties[key] = value.copy()
      else:
        raise TypeError, 'Unexpected type ' + value.__class__.__name__ + \
                         ' for key ' + key + ' in ' + self.__class__.__name__

    return that

  def Name(self):
    """Return the name corresponding to an object.

    Not all objects necessarily need to be nameable, and not all that do have
    a "name" property.  Override as needed.
    """

    # If the schema indicates that "name" is required, try to access the
    # property even if it doesn't exist.  This will result in a KeyError
    # being raised for the property that should be present, which seems more
    # appropriate than NotImplementedError in this case.
    if 'name' in self._properties or \
        ('name' in self._schema and self._schema['name'][3]):
      return self._properties['name']

    raise NotImplementedError, \
          self.__class__.__name__ + ' must implement Name'

  def Comment(self):
    """Return a comment string for the object.

    Most objects just use their name as the comment, but PBXProject uses
    different values.

    The returned comment is not escaped and does not have any comment marker
    strings applied to it.
    """

    return self.Name()

  def Hashables(self):
    hashables = [self.__class__.__name__]

    name = self.Name()
    if name != None:
      hashables.append(name)

    hashables.extend(self._hashables)

    return hashables

  def HashablesForChild(self):
    return None

  def ComputeIDs(self, recursive=True, overwrite=True, seed_hash=None):
    """Set "id" properties deterministically.

    An object's "id" property is set based on a hash of its class type and
    name, as well as the class type and name of all ancestor objects.  As
    such, it is only advisable to call ComputeIDs once an entire project file
    tree is built.

    If recursive is True, recurse into all descendant objects and update their
    hashes.

    If overwrite is True, any existing value set in the "id" property will be
    replaced.
    """

    def _HashUpdate(hash, data):
      """Update hash with data's length and contents.

      If the hash were updated only with the value of data, it would be
      possible for clowns to induce collisions by manipulating the names of
      their objects.  By adding the length, it's exceedingly less likely that
      ID collisions will be encountered, intentionally or not.
      """

      hash.update(struct.pack('>i', len(data)))
      hash.update(data)

    if seed_hash is None:
      seed_hash = _new_sha1()

    hash = seed_hash.copy()

    hashables = self.Hashables()
    assert len(hashables) > 0
    for hashable in hashables:
      _HashUpdate(hash, hashable)

    if recursive:
      hashables_for_child = self.HashablesForChild()
      if hashables_for_child is None:
        child_hash = hash
      else:
        assert len(hashables_for_child) > 0
        child_hash = seed_hash.copy()
        for hashable in hashables_for_child:
          _HashUpdate(child_hash, hashable)

      for child in self.Children():
        child.ComputeIDs(recursive, overwrite, child_hash)

    if overwrite or self.id is None:
      # Xcode IDs are only 96 bits (24 hex characters), but a SHA-1 digest is
      # is 160 bits.  Instead of throwing out 64 bits of the digest, xor them
      # into the portion that gets used.
      assert hash.digest_size % 4 == 0
      digest_int_count = hash.digest_size / 4
      digest_ints = struct.unpack('>' + 'I' * digest_int_count, hash.digest())
      id_ints = [0, 0, 0]
      for index in xrange(0, digest_int_count):
        id_ints[index % 3] ^= digest_ints[index]
      self.id = '%08X%08X%08X' % tuple(id_ints)

  def EnsureNoIDCollisions(self):
    """Verifies that no two objects have the same ID.  Checks all descendants.
    """

    ids = {}
    descendants = self.Descendants()
    for descendant in descendants:
      if descendant.id in ids:
        other = ids[descendant.id]
        raise KeyError, \
              'Duplicate ID %s, objects "%s" and "%s" in "%s"' % \
              (descendant.id, str(descendant._properties),
               str(other._properties), self._properties['rootObject'].Name())
      ids[descendant.id] = descendant

  def Children(self):
    """Returns a list of all of this object's owned (strong) children."""

    children = []
    for property, attributes in self._schema.iteritems():
      (is_list, property_type, is_strong) = attributes[0:3]
      if is_strong and property in self._properties:
        if not is_list:
          children.append(self._properties[property])
        else:
          children.extend(self._properties[property])
    return children

  def Descendants(self):
    """Returns a list of all of this object's descendants, including this
    object.
    """

    children = self.Children()
    descendants = [self]
    for child in children:
      descendants.extend(child.Descendants())
    return descendants

  def PBXProjectAncestor(self):
    # The base case for recursion is defined at PBXProject.PBXProjectAncestor.
    if self.parent:
      return self.parent.PBXProjectAncestor()
    return None

  def _EncodeComment(self, comment):
    """Encodes a comment to be placed in the project file output, mimicing
    Xcode behavior.
    """

    # This mimics Xcode behavior by wrapping the comment in "/*" and "*/".  If
    # the string already contains a "*/", it is turned into "(*)/".  This keeps
    # the file writer from outputting something that would be treated as the
    # end of a comment in the middle of something intended to be entirely a
    # comment.

    return '/* ' + comment.replace('*/', '(*)/') + ' */'

  def _EncodeTransform(self, match):
    # This function works closely with _EncodeString.  It will only be called
    # by re.sub with match.group(0) containing a character matched by the
    # the _escaped expression.
    char = match.group(0)

    # Backslashes (\) and quotation marks (") are always replaced with a
    # backslash-escaped version of the same.  Everything else gets its
    # replacement from the class' _encode_transforms array.
    if char == '\\':
      return '\\\\'
    if char == '"':
      return '\\"'
    return self._encode_transforms[ord(char)]

  def _EncodeString(self, value):
    """Encodes a string to be placed in the project file output, mimicing
    Xcode behavior.
    """

    # Use quotation marks when any character outside of the range A-Z, a-z, 0-9,
    # $ (dollar sign), . (period), and _ (underscore) is present.  Also use
    # quotation marks to represent empty strings.
    #
    # Escape " (double-quote) and \ (backslash) by preceding them with a
    # backslash.
    #
    # Some characters below the printable ASCII range are encoded specially:
    #     7 ^G BEL is encoded as "\a"
    #     8 ^H BS  is encoded as "\b"
    #    11 ^K VT  is encoded as "\v"
    #    12 ^L NP  is encoded as "\f"
    #   127 ^? DEL is passed through as-is without escaping
    #  - In PBXFileReference and PBXBuildFile objects:
    #     9 ^I HT  is passed through as-is without escaping
    #    10 ^J NL  is passed through as-is without escaping
    #    13 ^M CR  is passed through as-is without escaping
    #  - In other objects:
    #     9 ^I HT  is encoded as "\t"
    #    10 ^J NL  is encoded as "\n"
    #    13 ^M CR  is encoded as "\n" rendering it indistinguishable from
    #              10 ^J NL
    # All other nonprintable characters within the ASCII range (0 through 127
    # inclusive) are encoded as "\U001f" referring to the Unicode code point in
    # hexadecimal.  For example, character 14 (^N SO) is encoded as "\U000e".
    # Characters above the ASCII range are passed through to the output encoded
    # as UTF-8 without any escaping.  These mappings are contained in the
    # class' _encode_transforms list.

    if _unquoted.search(value) and not _quoted.search(value):
      return value

    return '"' + _escaped.sub(self._EncodeTransform, value) + '"'

  def _XCPrint(self, file, tabs, line):
    file.write('\t' * tabs + line)

  def _XCPrintableValue(self, tabs, value, flatten_list=False):
    """Returns a representation of value that may be printed in a project file,
    mimicing Xcode's behavior.

    _XCPrintableValue can handle str and int values, XCObjects (which are
    made printable by returning their id property), and list and dict objects
    composed of any of the above types.  When printing a list or dict, and
    _should_print_single_line is False, the tabs parameter is used to determine
    how much to indent the lines corresponding to the items in the list or
    dict.

    If flatten_list is True, single-element lists will be transformed into
    strings.
    """

    printable = ''
    comment = None

    if self._should_print_single_line:
      sep = ' '
      element_tabs = ''
      end_tabs = ''
    else:
      sep = '\n'
      element_tabs = '\t' * (tabs + 1)
      end_tabs = '\t' * tabs

    if isinstance(value, XCObject):
      printable += value.id
      comment = value.Comment()
    elif isinstance(value, str):
      printable += self._EncodeString(value)
    elif isinstance(value, unicode):
      printable += self._EncodeString(value.encode('utf-8'))
    elif isinstance(value, int):
      printable += str(value)
    elif isinstance(value, list):
      if flatten_list and len(value) <= 1:
        if len(value) == 0:
          printable += self._EncodeString('')
        else:
          printable += self._EncodeString(value[0])
      else:
        printable = '(' + sep
        for item in value:
          printable += element_tabs + \
                       self._XCPrintableValue(tabs + 1, item, flatten_list) + \
                       ',' + sep
        printable += end_tabs + ')'
    elif isinstance(value, dict):
      printable = '{' + sep
      for item_key, item_value in sorted(value.iteritems()):
        printable += element_tabs + \
            self._XCPrintableValue(tabs + 1, item_key, flatten_list) + ' = ' + \
            self._XCPrintableValue(tabs + 1, item_value, flatten_list) + ';' + \
            sep
      printable += end_tabs + '}'
    else:
      raise TypeError, "Can't make " + value.__class__.__name__ + ' printable'

    if comment != None:
      printable += ' ' + self._EncodeComment(comment)

    return printable

  def _XCKVPrint(self, file, tabs, key, value):
    """Prints a key and value, members of an XCObject's _properties dictionary,
    to file.

    tabs is an int identifying the indentation level.  If the class'
    _should_print_single_line variable is True, tabs is ignored and the
    key-value pair will be followed by a space insead of a newline.
    """

    if self._should_print_single_line:
      printable = ''
      after_kv = ' '
    else:
      printable = '\t' * tabs
      after_kv = '\n'

    # Xcode usually prints remoteGlobalIDString values in PBXContainerItemProxy
    # objects without comments.  Sometimes it prints them with comments, but
    # the majority of the time, it doesn't.  To avoid unnecessary changes to
    # the project file after Xcode opens it, don't write comments for
    # remoteGlobalIDString.  This is a sucky hack and it would certainly be
    # cleaner to extend the schema to indicate whether or not a comment should
    # be printed, but since this is the only case where the problem occurs and
    # Xcode itself can't seem to make up its mind, the hack will suffice.
    #
    # Also see PBXContainerItemProxy._schema['remoteGlobalIDString'].
    if key == 'remoteGlobalIDString' and isinstance(self,
                                                    PBXContainerItemProxy):
      value_to_print = value.id
    else:
      value_to_print = value

    # PBXBuildFile's settings property is represented in the output as a dict,
    # but a hack here has it represented as a string. Arrange to strip off the
    # quotes so that it shows up in the output as expected.
    if key == 'settings' and isinstance(self, PBXBuildFile):
      strip_value_quotes = True
    else:
      strip_value_quotes = False

    # In another one-off, let's set flatten_list on buildSettings properties
    # of XCBuildConfiguration objects, because that's how Xcode treats them.
    if key == 'buildSettings' and isinstance(self, XCBuildConfiguration):
      flatten_list = True
    else:
      flatten_list = False

    try:
      printable_key = self._XCPrintableValue(tabs, key, flatten_list)
      printable_value = self._XCPrintableValue(tabs, value_to_print,
                                               flatten_list)
      if strip_value_quotes and len(printable_value) > 1 and \
          printable_value[0] == '"' and printable_value[-1] == '"':
        printable_value = printable_value[1:-1]
      printable += printable_key + ' = ' + printable_value + ';' + after_kv
    except TypeError, e:
      gyp.common.ExceptionAppend(e,
                                 'while printing key "%s"' % key)
      raise

    self._XCPrint(file, 0, printable)

  def Print(self, file=sys.stdout):
    """Prints a reprentation of this object to file, adhering to Xcode output
    formatting.
    """

    self.VerifyHasRequiredProperties()

    if self._should_print_single_line:
      # When printing an object in a single line, Xcode doesn't put any space
      # between the beginning of a dictionary (or presumably a list) and the
      # first contained item, so you wind up with snippets like
      #   ...CDEF = {isa = PBXFileReference; fileRef = 0123...
      # If it were me, I would have put a space in there after the opening
      # curly, but I guess this is just another one of those inconsistencies
      # between how Xcode prints PBXFileReference and PBXBuildFile objects as
      # compared to other objects.  Mimic Xcode's behavior here by using an
      # empty string for sep.
      sep = ''
      end_tabs = 0
    else:
      sep = '\n'
      end_tabs = 2

    # Start the object.  For example, '\t\tPBXProject = {\n'.
    self._XCPrint(file, 2, self._XCPrintableValue(2, self) + ' = {' + sep)

    # "isa" isn't in the _properties dictionary, it's an intrinsic property
    # of the class which the object belongs to.  Xcode always outputs "isa"
    # as the first element of an object dictionary.
    self._XCKVPrint(file, 3, 'isa', self.__class__.__name__)

    # The remaining elements of an object dictionary are sorted alphabetically.
    for property, value in sorted(self._properties.iteritems()):
      self._XCKVPrint(file, 3, property, value)

    # End the object.
    self._XCPrint(file, end_tabs, '};\n')

  def UpdateProperties(self, properties, do_copy=False):
    """Merge the supplied properties into the _properties dictionary.

    The input properties must adhere to the class schema or a KeyError or
    TypeError exception will be raised.  If adding an object of an XCObject
    subclass and the schema indicates a strong relationship, the object's
    parent will be set to this object.

    If do_copy is True, then lists, dicts, strong-owned XCObjects, and
    strong-owned XCObjects in lists will be copied instead of having their
    references added.
    """

    if properties is None:
      return

    for property, value in properties.iteritems():
      # Make sure the property is in the schema.
      if not property in self._schema:
        raise KeyError, property + ' not in ' + self.__class__.__name__

      # Make sure the property conforms to the schema.
      (is_list, property_type, is_strong) = self._schema[property][0:3]
      if is_list:
        if value.__class__ != list:
          raise TypeError, \
                property + ' of ' + self.__class__.__name__ + \
                ' must be list, not ' + value.__class__.__name__
        for item in value:
          if not isinstance(item, property_type) and \
             not (item.__class__ == unicode and property_type == str):
            # Accept unicode where str is specified.  str is treated as
            # UTF-8-encoded.
            raise TypeError, \
                  'item of ' + property + ' of ' + self.__class__.__name__ + \
                  ' must be ' + property_type.__name__ + ', not ' + \
                  item.__class__.__name__
      elif not isinstance(value, property_type) and \
           not (value.__class__ == unicode and property_type == str):
        # Accept unicode where str is specified.  str is treated as
        # UTF-8-encoded.
        raise TypeError, \
              property + ' of ' + self.__class__.__name__ + ' must be ' + \
              property_type.__name__ + ', not ' + value.__class__.__name__

      # Checks passed, perform the assignment.
      if do_copy:
        if isinstance(value, XCObject):
          if is_strong:
            self._properties[property] = value.Copy()
          else:
            self._properties[property] = value
        elif isinstance(value, str) or isinstance(value, unicode) or \
             isinstance(value, int):
          self._properties[property] = value
        elif isinstance(value, list):
          if is_strong:
            # If is_strong is True, each element is an XCObject, so it's safe
            # to call Copy.
            self._properties[property] = []
            for item in value:
              self._properties[property].append(item.Copy())
          else:
            self._properties[property] = value[:]
        elif isinstance(value, dict):
          self._properties[property] = value.copy()
        else:
          raise TypeError, "Don't know how to copy a " + \
                           value.__class__.__name__ + ' object for ' + \
                           property + ' in ' + self.__class__.__name__
      else:
        self._properties[property] = value

      # Set up the child's back-reference to this object.  Don't use |value|
      # any more because it may not be right if do_copy is true.
      if is_strong:
        if not is_list:
          self._properties[property].parent = self
        else:
          for item in self._properties[property]:
            item.parent = self

  def HasProperty(self, key):
    return key in self._properties

  def GetProperty(self, key):
    return self._properties[key]

  def SetProperty(self, key, value):
    self.UpdateProperties({key: value})

  def DelProperty(self, key):
    if key in self._properties:
      del self._properties[key]

  def AppendProperty(self, key, value):
    # TODO(mark): Support ExtendProperty too (and make this call that)?

    # Schema validation.
    if not key in self._schema:
      raise KeyError, key + ' not in ' + self.__class__.__name__

    (is_list, property_type, is_strong) = self._schema[key][0:3]
    if not is_list:
      raise TypeError, key + ' of ' + self.__class__.__name__ + ' must be list'
    if not isinstance(value, property_type):
      raise TypeError, 'item of ' + key + ' of ' + self.__class__.__name__ + \
                       ' must be ' + property_type.__name__ + ', not ' + \
                       value.__class__.__name__

    # If the property doesn't exist yet, create a new empty list to receive the
    # item.
    if not key in self._properties:
      self._properties[key] = []

    # Set up the ownership link.
    if is_strong:
      value.parent = self

    # Store the item.
    self._properties[key].append(value)

  def VerifyHasRequiredProperties(self):
    """Ensure that all properties identified as required by the schema are
    set.
    """

    # TODO(mark): A stronger verification mechanism is needed.  Some
    # subclasses need to perform validation beyond what the schema can enforce.
    for property, attributes in self._schema.iteritems():
      (is_list, property_type, is_strong, is_required) = attributes[0:4]
      if is_required and not property in self._properties:
        raise KeyError, self.__class__.__name__ + ' requires ' + property

  def _SetDefaultsFromSchema(self):
    """Assign object default values according to the schema.  This will not
    overwrite properties that have already been set."""

    defaults = {}
    for property, attributes in self._schema.iteritems():
      (is_list, property_type, is_strong, is_required) = attributes[0:4]
      if is_required and len(attributes) >= 5 and \
          not property in self._properties:
        default = attributes[4]

        defaults[property] = default

    if len(defaults) > 0:
      # Use do_copy=True so that each new object gets its own copy of strong
      # objects, lists, and dicts.
      self.UpdateProperties(defaults, do_copy=True)


class XCHierarchicalElement(XCObject):
  """Abstract base for PBXGroup and PBXFileReference.  Not represented in a
  project file."""

  # TODO(mark): Do name and path belong here?  Probably so.
  # If path is set and name is not, name may have a default value.  Name will
  # be set to the basename of path, if the basename of path is different from
  # the full value of path.  If path is already just a leaf name, name will
  # not be set.
  _schema = XCObject._schema.copy()
  _schema.update({
    'comments':       [0, str, 0, 0],
    'fileEncoding':   [0, str, 0, 0],
    'includeInIndex': [0, int, 0, 0],
    'indentWidth':    [0, int, 0, 0],
    'lineEnding':     [0, int, 0, 0],
    'sourceTree':     [0, str, 0, 1, '<group>'],
    'tabWidth':       [0, int, 0, 0],
    'usesTabs':       [0, int, 0, 0],
    'wrapsLines':     [0, int, 0, 0],
  })

  def __init__(self, properties=None, id=None, parent=None):
    # super
    XCObject.__init__(self, properties, id, parent)
    if 'path' in self._properties and not 'name' in self._properties:
      path = self._properties['path']
      name = posixpath.basename(path)
      if name != '' and path != name:
        self.SetProperty('name', name)

    if 'path' in self._properties and \
        (not 'sourceTree' in self._properties or \
         self._properties['sourceTree'] == '<group>'):
      # If the pathname begins with an Xcode variable like "$(SDKROOT)/", take
      # the variable out and make the path be relative to that variable by
      # assigning the variable name as the sourceTree.
      (source_tree, path) = SourceTreeAndPathFromPath(self._properties['path'])
      if source_tree != None:
        self._properties['sourceTree'] = source_tree
      if path != None:
        self._properties['path'] = path
      if source_tree != None and path is None and \
         not 'name' in self._properties:
        # The path was of the form "$(SDKROOT)" with no path following it.
        # This object is now relative to that variable, so it has no path
        # attribute of its own.  It does, however, keep a name.
        del self._properties['path']
        self._properties['name'] = source_tree

  def Name(self):
    if 'name' in self._properties:
      return self._properties['name']
    elif 'path' in self._properties:
      return self._properties['path']
    else:
      # This happens in the case of the root PBXGroup.
      return None

  def Hashables(self):
    """Custom hashables for XCHierarchicalElements.

    XCHierarchicalElements are special.  Generally, their hashes shouldn't
    change if the paths don't change.  The normal XCObject implementation of
    Hashables adds a hashable for each object, which means that if
    the hierarchical structure changes (possibly due to changes caused when
    TakeOverOnlyChild runs and encounters slight changes in the hierarchy),
    the hashes will change.  For example, if a project file initially contains
    a/b/f1 and a/b becomes collapsed into a/b, f1 will have a single parent
    a/b.  If someone later adds a/f2 to the project file, a/b can no longer be
    collapsed, and f1 winds up with parent b and grandparent a.  That would
    be sufficient to change f1's hash.

    To counteract this problem, hashables for all XCHierarchicalElements except
    for the main group (which has neither a name nor a path) are taken to be
    just the set of path components.  Because hashables are inherited from
    parents, this provides assurance that a/b/f1 has the same set of hashables
    whether its parent is b or a/b.

    The main group is a special case.  As it is permitted to have no name or
    path, it is permitted to use the standard XCObject hash mechanism.  This
    is not considered a problem because there can be only one main group.
    """

    if self == self.PBXProjectAncestor()._properties['mainGroup']:
      # super
      return XCObject.Hashables(self)

    hashables = []

    # Put the name in first, ensuring that if TakeOverOnlyChild collapses
    # children into a top-level group like "Source", the name always goes
    # into the list of hashables without interfering with path components.
    if 'name' in self._properties:
      # Make it less likely for people to manipulate hashes by following the
      # pattern of always pushing an object type value onto the list first.
      hashables.append(self.__class__.__name__ + '.name')
      hashables.append(self._properties['name'])

    # NOTE: This still has the problem that if an absolute path is encountered,
    # including paths with a sourceTree, they'll still inherit their parents'
    # hashables, even though the paths aren't relative to their parents.  This
    # is not expected to be much of a problem in practice.
    path = self.PathFromSourceTreeAndPath()
    if path != None:
      components = path.split(posixpath.sep)
      for component in components:
        hashables.append(self.__class__.__name__ + '.path')
        hashables.append(component)

    hashables.extend(self._hashables)

    return hashables

  def Compare(self, other):
    # Allow comparison of these types.  PBXGroup has the highest sort rank;
    # PBXVariantGroup is treated as equal to PBXFileReference.
    valid_class_types = {
      PBXFileReference: 'file',
      PBXGroup:         'group',
      PBXVariantGroup:  'file',
    }
    self_type = valid_class_types[self.__class__]
    other_type = valid_class_types[other.__class__]

    if self_type == other_type:
      # If the two objects are of the same sort rank, compare their names.
      return cmp(self.Name(), other.Name())

    # Otherwise, sort groups before everything else.
    if self_type == 'group':
      return -1
    return 1

  def CompareRootGroup(self, other):
    # This function should be used only to compare direct children of the
    # containing PBXProject's mainGroup.  These groups should appear in the
    # listed order.
    # TODO(mark): "Build" is used by gyp.generator.xcode, perhaps the
    # generator should have a way of influencing this list rather than having
    # to hardcode for the generator here.
    order = ['Source', 'Intermediates', 'Projects', 'Frameworks', 'Products',
             'Build']

    # If the groups aren't in the listed order, do a name comparison.
    # Otherwise, groups in the listed order should come before those that
    # aren't.
    self_name = self.Name()
    other_name = other.Name()
    self_in = isinstance(self, PBXGroup) and self_name in order
    other_in = isinstance(self, PBXGroup) and other_name in order
    if not self_in and not other_in:
      return self.Compare(other)
    if self_name in order and not other_name in order:
      return -1
    if other_name in order and not self_name in order:
      return 1

    # If both groups are in the listed order, go by the defined order.
    self_index = order.index(self_name)
    other_index = order.index(other_name)
    if self_index < other_index:
      return -1
    if self_index > other_index:
      return 1
    return 0

  def PathFromSourceTreeAndPath(self):
    # Turn the object's sourceTree and path properties into a single flat
    # string of a form comparable to the path parameter.  If there's a
    # sourceTree property other than "<group>", wrap it in $(...) for the
    # comparison.
    components = []
    if self._properties['sourceTree'] != '<group>':
      components.append('$(' + self._properties['sourceTree'] + ')')
    if 'path' in self._properties:
      components.append(self._properties['path'])

    if len(components) > 0:
      return posixpath.join(*components)

    return None

  def FullPath(self):
    # Returns a full path to self relative to the project file, or relative
    # to some other source tree.  Start with self, and walk up the chain of
    # parents prepending their paths, if any, until no more parents are
    # available (project-relative path) or until a path relative to some
    # source tree is found.
    xche = self
    path = None
    while isinstance(xche, XCHierarchicalElement) and \
          (path is None or \
           (not path.startswith('/') and not path.startswith('$'))):
      this_path = xche.PathFromSourceTreeAndPath()
      if this_path != None and path != None:
        path = posixpath.join(this_path, path)
      elif this_path != None:
        path = this_path
      xche = xche.parent

    return path


class PBXGroup(XCHierarchicalElement):
  """
  Attributes:
    _children_by_path: Maps pathnames of children of this PBXGroup to the
      actual child XCHierarchicalElement objects.
    _variant_children_by_name_and_path: Maps (name, path) tuples of
      PBXVariantGroup children to the actual child PBXVariantGroup objects.
  """

  _schema = XCHierarchicalElement._schema.copy()
  _schema.update({
    'children': [1, XCHierarchicalElement, 1, 1, []],
    'name':     [0, str,                   0, 0],
    'path':     [0, str,                   0, 0],
  })

  def __init__(self, properties=None, id=None, parent=None):
    # super
    XCHierarchicalElement.__init__(self, properties, id, parent)
    self._children_by_path = {}
    self._variant_children_by_name_and_path = {}
    for child in self._properties.get('children', []):
      self._AddChildToDicts(child)

  def Hashables(self):
    # super
    hashables = XCHierarchicalElement.Hashables(self)

    # It is not sufficient to just rely on name and parent to build a unique
    # hashable : a node could have two child PBXGroup sharing a common name.
    # To add entropy the hashable is enhanced with the names of all its
    # children.
    for child in self._properties.get('children', []):
      child_name = child.Name()
      if child_name != None:
        hashables.append(child_name)

    return hashables

  def HashablesForChild(self):
    # To avoid a circular reference the hashables used to compute a child id do
    # not include the child names.
    return XCHierarchicalElement.Hashables(self)

  def _AddChildToDicts(self, child):
    # Sets up this PBXGroup object's dicts to reference the child properly.
    child_path = child.PathFromSourceTreeAndPath()
    if child_path:
      if child_path in self._children_by_path:
        raise ValueError, 'Found multiple children with path ' + child_path
      self._children_by_path[child_path] = child

    if isinstance(child, PBXVariantGroup):
      child_name = child._properties.get('name', None)
      key = (child_name, child_path)
      if key in self._variant_children_by_name_and_path:
        raise ValueError, 'Found multiple PBXVariantGroup children with ' + \
                          'name ' + str(child_name) + ' and path ' + \
                          str(child_path)
      self._variant_children_by_name_and_path[key] = child

  def AppendChild(self, child):
    # Callers should use this instead of calling
    # AppendProperty('children', child) directly because this function
    # maintains the group's dicts.
    self.AppendProperty('children', child)
    self._AddChildToDicts(child)

  def GetChildByName(self, name):
    # This is not currently optimized with a dict as GetChildByPath is because
    # it has few callers.  Most callers probably want GetChildByPath.  This
    # function is only useful to get children that have names but no paths,
    # which is rare.  The children of the main group ("Source", "Products",
    # etc.) is pretty much the only case where this likely to come up.
    #
    # TODO(mark): Maybe this should raise an error if more than one child is
    # present with the same name.
    if not 'children' in self._properties:
      return None

    for child in self._properties['children']:
      if child.Name() == name:
        return child

    return None

  def GetChildByPath(self, path):
    if not path:
      return None

    if path in self._children_by_path:
      return self._children_by_path[path]

    return None

  def GetChildByRemoteObject(self, remote_object):
    # This method is a little bit esoteric.  Given a remote_object, which
    # should be a PBXFileReference in another project file, this method will
    # return this group's PBXReferenceProxy object serving as a local proxy
    # for the remote PBXFileReference.
    #
    # This function might benefit from a dict optimization as GetChildByPath
    # for some workloads, but profiling shows that it's not currently a
    # problem.
    if not 'children' in self._properties:
      return None

    for child in self._properties['children']:
      if not isinstance(child, PBXReferenceProxy):
        continue

      container_proxy = child._properties['remoteRef']
      if container_proxy._properties['remoteGlobalIDString'] == remote_object:
        return child

    return None

  def AddOrGetFileByPath(self, path, hierarchical):
    """Returns an existing or new file reference corresponding to path.

    If hierarchical is True, this method will create or use the necessary
    hierarchical group structure corresponding to path.  Otherwise, it will
    look in and create an item in the current group only.

    If an existing matching reference is found, it is returned, otherwise, a
    new one will be created, added to the correct group, and returned.

    If path identifies a directory by virtue of carrying a trailing slash,
    this method returns a PBXFileReference of "folder" type.  If path
    identifies a variant, by virtue of it identifying a file inside a directory
    with an ".lproj" extension, this method returns a PBXVariantGroup
    containing the variant named by path, and possibly other variants.  For
    all other paths, a "normal" PBXFileReference will be returned.
    """

    # Adding or getting a directory?  Directories end with a trailing slash.
    is_dir = False
    if path.endswith('/'):
      is_dir = True
    path = posixpath.normpath(path)
    if is_dir:
      path = path + '/'

    # Adding or getting a variant?  Variants are files inside directories
    # with an ".lproj" extension.  Xcode uses variants for localization.  For
    # a variant path/to/Language.lproj/MainMenu.nib, put a variant group named
    # MainMenu.nib inside path/to, and give it a variant named Language.  In
    # this example, grandparent would be set to path/to and parent_root would
    # be set to Language.
    variant_name = None
    parent = posixpath.dirname(path)
    grandparent = posixpath.dirname(parent)
    parent_basename = posixpath.basename(parent)
    (parent_root, parent_ext) = posixpath.splitext(parent_basename)
    if parent_ext == '.lproj':
      variant_name = parent_root
    if grandparent == '':
      grandparent = None

    # Putting a directory inside a variant group is not currently supported.
    assert not is_dir or variant_name is None

    path_split = path.split(posixpath.sep)
    if len(path_split) == 1 or \
       ((is_dir or variant_name != None) and len(path_split) == 2) or \
       not hierarchical:
      # The PBXFileReference or PBXVariantGroup will be added to or gotten from
      # this PBXGroup, no recursion necessary.
      if variant_name is None:
        # Add or get a PBXFileReference.
        file_ref = self.GetChildByPath(path)
        if file_ref != None:
          assert file_ref.__class__ == PBXFileReference
        else:
          file_ref = PBXFileReference({'path': path})
          self.AppendChild(file_ref)
      else:
        # Add or get a PBXVariantGroup.  The variant group name is the same
        # as the basename (MainMenu.nib in the example above).  grandparent
        # specifies the path to the variant group itself, and path_split[-2:]
        # is the path of the specific variant relative to its group.
        variant_group_name = posixpath.basename(path)
        variant_group_ref = self.AddOrGetVariantGroupByNameAndPath(
            variant_group_name, grandparent)
        variant_path = posixpath.sep.join(path_split[-2:])
        variant_ref = variant_group_ref.GetChildByPath(variant_path)
        if variant_ref != None:
          assert variant_ref.__class__ == PBXFileReference
        else:
          variant_ref = PBXFileReference({'name': variant_name,
                                          'path': variant_path})
          variant_group_ref.AppendChild(variant_ref)
        # The caller is interested in the variant group, not the specific
        # variant file.
        file_ref = variant_group_ref
      return file_ref
    else:
      # Hierarchical recursion.  Add or get a PBXGroup corresponding to the
      # outermost path component, and then recurse into it, chopping off that
      # path component.
      next_dir = path_split[0]
      group_ref = self.GetChildByPath(next_dir)
      if group_ref != None:
        assert group_ref.__class__ == PBXGroup
      else:
        group_ref = PBXGroup({'path': next_dir})
        self.AppendChild(group_ref)
      return group_ref.AddOrGetFileByPath(posixpath.sep.join(path_split[1:]),
                                          hierarchical)

  def AddOrGetVariantGroupByNameAndPath(self, name, path):
    """Returns an existing or new PBXVariantGroup for name and path.

    If a PBXVariantGroup identified by the name and path arguments is already
    present as a child of this object, it is returned.  Otherwise, a new
    PBXVariantGroup with the correct properties is created, added as a child,
    and returned.

    This method will generally be called by AddOrGetFileByPath, which knows
    when to create a variant group based on the structure of the pathnames
    passed to it.
    """

    key = (name, path)
    if key in self._variant_children_by_name_and_path:
      variant_group_ref = self._variant_children_by_name_and_path[key]
      assert variant_group_ref.__class__ == PBXVariantGroup
      return variant_group_ref

    variant_group_properties = {'name': name}
    if path != None:
      variant_group_properties['path'] = path
    variant_group_ref = PBXVariantGroup(variant_group_properties)
    self.AppendChild(variant_group_ref)

    return variant_group_ref

  def TakeOverOnlyChild(self, recurse=False):
    """If this PBXGroup has only one child and it's also a PBXGroup, take
    it over by making all of its children this object's children.

    This function will continue to take over only children when those children
    are groups.  If there are three PBXGroups representing a, b, and c, with
    c inside b and b inside a, and a and b have no other children, this will
    result in a taking over both b and c, forming a PBXGroup for a/b/c.

    If recurse is True, this function will recurse into children and ask them
    to collapse themselves by taking over only children as well.  Assuming
    an example hierarchy with files at a/b/c/d1, a/b/c/d2, and a/b/c/d3/e/f
    (d1, d2, and f are files, the rest are groups), recursion will result in
    a group for a/b/c containing a group for d3/e.
    """

    # At this stage, check that child class types are PBXGroup exactly,
    # instead of using isinstance.  The only subclass of PBXGroup,
    # PBXVariantGroup, should not participate in reparenting in the same way:
    # reparenting by merging different object types would be wrong.
    while len(self._properties['children']) == 1 and \
          self._properties['children'][0].__class__ == PBXGroup:
      # Loop to take over the innermost only-child group possible.

      child = self._properties['children'][0]

      # Assume the child's properties, including its children.  Save a copy
      # of this object's old properties, because they'll still be needed.
      # This object retains its existing id and parent attributes.
      old_properties = self._properties
      self._properties = child._properties
      self._children_by_path = child._children_by_path

      if not 'sourceTree' in self._properties or \
         self._properties['sourceTree'] == '<group>':
        # The child was relative to its parent.  Fix up the path.  Note that
        # children with a sourceTree other than "<group>" are not relative to
        # their parents, so no path fix-up is needed in that case.
        if 'path' in old_properties:
          if 'path' in self._properties:
            # Both the original parent and child have paths set.
            self._properties['path'] = posixpath.join(old_properties['path'],
                                                      self._properties['path'])
          else:
            # Only the original parent has a path, use it.
            self._properties['path'] = old_properties['path']
        if 'sourceTree' in old_properties:
          # The original parent had a sourceTree set, use it.
          self._properties['sourceTree'] = old_properties['sourceTree']

      # If the original parent had a name set, keep using it.  If the original
      # parent didn't have a name but the child did, let the child's name
      # live on.  If the name attribute seems unnecessary now, get rid of it.
      if 'name' in old_properties and old_properties['name'] != None and \
         old_properties['name'] != self.Name():
        self._properties['name'] = old_properties['name']
      if 'name' in self._properties and 'path' in self._properties and \
         self._properties['name'] == self._properties['path']:
        del self._properties['name']

      # Notify all children of their new parent.
      for child in self._properties['children']:
        child.parent = self

    # If asked to recurse, recurse.
    if recurse:
      for child in self._properties['children']:
        if child.__class__ == PBXGroup:
          child.TakeOverOnlyChild(recurse)

  def SortGroup(self):
    self._properties['children'] = \
        sorted(self._properties['children'], cmp=lambda x,y: x.Compare(y))

    # Recurse.
    for child in self._properties['children']:
      if isinstance(child, PBXGroup):
        child.SortGroup()


class XCFileLikeElement(XCHierarchicalElement):
  # Abstract base for objects that can be used as the fileRef property of
  # PBXBuildFile.

  def PathHashables(self):
    # A PBXBuildFile that refers to this object will call this method to
    # obtain additional hashables specific to this XCFileLikeElement.  Don't
    # just use this object's hashables, they're not specific and unique enough
    # on their own (without access to the parent hashables.)  Instead, provide
    # hashables that identify this object by path by getting its hashables as
    # well as the hashables of ancestor XCHierarchicalElement objects.

    hashables = []
    xche = self
    while xche != None and isinstance(xche, XCHierarchicalElement):
      xche_hashables = xche.Hashables()
      for index in xrange(0, len(xche_hashables)):
        hashables.insert(index, xche_hashables[index])
      xche = xche.parent
    return hashables


class XCContainerPortal(XCObject):
  # Abstract base for objects that can be used as the containerPortal property
  # of PBXContainerItemProxy.
  pass


class XCRemoteObject(XCObject):
  # Abstract base for objects that can be used as the remoteGlobalIDString
  # property of PBXContainerItemProxy.
  pass


class PBXFileReference(XCFileLikeElement, XCContainerPortal, XCRemoteObject):
  _schema = XCFileLikeElement._schema.copy()
  _schema.update({
    'explicitFileType':  [0, str, 0, 0],
    'lastKnownFileType': [0, str, 0, 0],
    'name':              [0, str, 0, 0],
    'path':              [0, str, 0, 1],
  })

  # Weird output rules for PBXFileReference.
  _should_print_single_line = True
  # super
  _encode_transforms = XCFileLikeElement._alternate_encode_transforms

  def __init__(self, properties=None, id=None, parent=None):
    # super
    XCFileLikeElement.__init__(self, properties, id, parent)
    if 'path' in self._properties and self._properties['path'].endswith('/'):
      self._properties['path'] = self._properties['path'][:-1]
      is_dir = True
    else:
      is_dir = False

    if 'path' in self._properties and \
        not 'lastKnownFileType' in self._properties and \
        not 'explicitFileType' in self._properties:
      # TODO(mark): This is the replacement for a replacement for a quick hack.
      # It is no longer incredibly sucky, but this list needs to be extended.
      extension_map = {
        'a':           'archive.ar',
        'app':         'wrapper.application',
        'bdic':        'file',
        'bundle':      'wrapper.cfbundle',
        'c':           'sourcecode.c.c',
        'cc':          'sourcecode.cpp.cpp',
        'cpp':         'sourcecode.cpp.cpp',
        'css':         'text.css',
        'cxx':         'sourcecode.cpp.cpp',
        'dylib':       'compiled.mach-o.dylib',
        'framework':   'wrapper.framework',
        'h':           'sourcecode.c.h',
        'hxx':         'sourcecode.cpp.h',
        'icns':        'image.icns',
        'java':        'sourcecode.java',
        'js':          'sourcecode.javascript',
        'm':           'sourcecode.c.objc',
        'mm':          'sourcecode.cpp.objcpp',
        'nib':         'wrapper.nib',
        'o':           'compiled.mach-o.objfile',
        'pdf':         'image.pdf',
        'pl':          'text.script.perl',
        'plist':       'text.plist.xml',
        'pm':          'text.script.perl',
        'png':         'image.png',
        'py':          'text.script.python',
        'r':           'sourcecode.rez',
        'rez':         'sourcecode.rez',
        's':           'sourcecode.asm',
        'strings':     'text.plist.strings',
        'ttf':         'file',
        'xcconfig':    'text.xcconfig',
        'xcdatamodel': 'wrapper.xcdatamodel',
        'xib':         'file.xib',
        'y':           'sourcecode.yacc',
      }

      if is_dir:
        file_type = 'folder'
      else:
        basename = posixpath.basename(self._properties['path'])
        (root, ext) = posixpath.splitext(basename)
        # Check the map using a lowercase extension.
        # TODO(mark): Maybe it should try with the original case first and fall
        # back to lowercase, in case there are any instances where case
        # matters.  There currently aren't.
        if ext != '':
          ext = ext[1:].lower()

        # TODO(mark): "text" is the default value, but "file" is appropriate
        # for unrecognized files not containing text.  Xcode seems to choose
        # based on content.
        file_type = extension_map.get(ext, 'text')

      self._properties['lastKnownFileType'] = file_type


class PBXVariantGroup(PBXGroup, XCFileLikeElement):
  """PBXVariantGroup is used by Xcode to represent localizations."""
  # No additions to the schema relative to PBXGroup.
  pass


# PBXReferenceProxy is also an XCFileLikeElement subclass.  It is defined below
# because it uses PBXContainerItemProxy, defined below.


class XCBuildConfiguration(XCObject):
  _schema = XCObject._schema.copy()
  _schema.update({
    'baseConfigurationReference': [0, PBXFileReference, 0, 0],
    'buildSettings':              [0, dict, 0, 1, {}],
    'name':                       [0, str,  0, 1],
  })

  def HasBuildSetting(self, key):
    return key in self._properties['buildSettings']

  def GetBuildSetting(self, key):
    return self._properties['buildSettings'][key]

  def SetBuildSetting(self, key, value):
    # TODO(mark): If a list, copy?
    self._properties['buildSettings'][key] = value

  def AppendBuildSetting(self, key, value):
    if not key in self._properties['buildSettings']:
      self._properties['buildSettings'][key] = []
    self._properties['buildSettings'][key].append(value)

  def DelBuildSetting(self, key):
    if key in self._properties['buildSettings']:
      del self._properties['buildSettings'][key]

  def SetBaseConfiguration(self, value):
    self._properties['baseConfigurationReference'] = value

class XCConfigurationList(XCObject):
  # _configs is the default list of configurations.
  _configs = [ XCBuildConfiguration({'name': 'Debug'}),
               XCBuildConfiguration({'name': 'Release'}) ]

  _schema = XCObject._schema.copy()
  _schema.update({
    'buildConfigurations':           [1, XCBuildConfiguration, 1, 1, _configs],
    'defaultConfigurationIsVisible': [0, int,                  0, 1, 1],
    'defaultConfigurationName':      [0, str,                  0, 1, 'Release'],
  })

  def Name(self):
    return 'Build configuration list for ' + \
           self.parent.__class__.__name__ + ' "' + self.parent.Name() + '"'

  def ConfigurationNamed(self, name):
    """Convenience accessor to obtain an XCBuildConfiguration by name."""
    for configuration in self._properties['buildConfigurations']:
      if configuration._properties['name'] == name:
        return configuration

    raise KeyError, name

  def DefaultConfiguration(self):
    """Convenience accessor to obtain the default XCBuildConfiguration."""
    return self.ConfigurationNamed(self._properties['defaultConfigurationName'])

  def HasBuildSetting(self, key):
    """Determines the state of a build setting in all XCBuildConfiguration
    child objects.

    If all child objects have key in their build settings, and the value is the
    same in all child objects, returns 1.

    If no child objects have the key in their build settings, returns 0.

    If some, but not all, child objects have the key in their build settings,
    or if any children have different values for the key, returns -1.
    """

    has = None
    value = None
    for configuration in self._properties['buildConfigurations']:
      configuration_has = configuration.HasBuildSetting(key)
      if has is None:
        has = configuration_has
      elif has != configuration_has:
        return -1

      if configuration_has:
        configuration_value = configuration.GetBuildSetting(key)
        if value is None:
          value = configuration_value
        elif value != configuration_value:
          return -1

    if not has:
      return 0

    return 1

  def GetBuildSetting(self, key):
    """Gets the build setting for key.

    All child XCConfiguration objects must have the same value set for the
    setting, or a ValueError will be raised.
    """

    # TODO(mark): This is wrong for build settings that are lists.  The list
    # contents should be compared (and a list copy returned?)

    value = None
    for configuration in self._properties['buildConfigurations']:
      configuration_value = configuration.GetBuildSetting(key)
      if value is None:
        value = configuration_value
      else:
        if value != configuration_value:
          raise ValueError, 'Variant values for ' + key

    return value

  def SetBuildSetting(self, key, value):
    """Sets the build setting for key to value in all child
    XCBuildConfiguration objects.
    """

    for configuration in self._properties['buildConfigurations']:
      configuration.SetBuildSetting(key, value)

  def AppendBuildSetting(self, key, value):
    """Appends value to the build setting for key, which is treated as a list,
    in all child XCBuildConfiguration objects.
    """

    for configuration in self._properties['buildConfigurations']:
      configuration.AppendBuildSetting(key, value)

  def DelBuildSetting(self, key):
    """Deletes the build setting key from all child XCBuildConfiguration
    objects.
    """

    for configuration in self._properties['buildConfigurations']:
      configuration.DelBuildSetting(key)

  def SetBaseConfiguration(self, value):
    """Sets the build configuration in all child XCBuildConfiguration objects.
    """

    for configuration in self._properties['buildConfigurations']:
      configuration.SetBaseConfiguration(value)


class PBXBuildFile(XCObject):
  _schema = XCObject._schema.copy()
  _schema.update({
    'fileRef':  [0, XCFileLikeElement, 0, 1],
    'settings': [0, str,               0, 0],  # hack, it's a dict
  })

  # Weird output rules for PBXBuildFile.
  _should_print_single_line = True
  _encode_transforms = XCObject._alternate_encode_transforms

  def Name(self):
    # Example: "main.cc in Sources"
    return self._properties['fileRef'].Name() + ' in ' + self.parent.Name()

  def Hashables(self):
    # super
    hashables = XCObject.Hashables(self)

    # It is not sufficient to just rely on Name() to get the
    # XCFileLikeElement's name, because that is not a complete pathname.
    # PathHashables returns hashables unique enough that no two
    # PBXBuildFiles should wind up with the same set of hashables, unless
    # someone adds the same file multiple times to the same target.  That
    # would be considered invalid anyway.
    hashables.extend(self._properties['fileRef'].PathHashables())

    return hashables


class XCBuildPhase(XCObject):
  """Abstract base for build phase classes.  Not represented in a project
  file.

  Attributes:
    _files_by_path: A dict mapping each path of a child in the files list by
      path (keys) to the corresponding PBXBuildFile children (values).
    _files_by_xcfilelikeelement: A dict mapping each XCFileLikeElement (keys)
      to the corresponding PBXBuildFile children (values).
  """

  # TODO(mark): Some build phase types, like PBXShellScriptBuildPhase, don't
  # actually have a "files" list.  XCBuildPhase should not have "files" but
  # another abstract subclass of it should provide this, and concrete build
  # phase types that do have "files" lists should be derived from that new
  # abstract subclass.  XCBuildPhase should only provide buildActionMask and
  # runOnlyForDeploymentPostprocessing, and not files or the various
  # file-related methods and attributes.

  _schema = XCObject._schema.copy()
  _schema.update({
    'buildActionMask':                    [0, int,          0, 1, 0x7fffffff],
    'files':                              [1, PBXBuildFile, 1, 1, []],
    'runOnlyForDeploymentPostprocessing': [0, int,          0, 1, 0],
  })

  def __init__(self, properties=None, id=None, parent=None):
    # super
    XCObject.__init__(self, properties, id, parent)

    self._files_by_path = {}
    self._files_by_xcfilelikeelement = {}
    for pbxbuildfile in self._properties.get('files', []):
      self._AddBuildFileToDicts(pbxbuildfile)

  def FileGroup(self, path):
    # Subclasses must override this by returning a two-element tuple.  The
    # first item in the tuple should be the PBXGroup to which "path" should be
    # added, either as a child or deeper descendant.  The second item should
    # be a boolean indicating whether files should be added into hierarchical
    # groups or one single flat group.
    raise NotImplementedError, \
          self.__class__.__name__ + ' must implement FileGroup'

  def _AddPathToDict(self, pbxbuildfile, path):
    """Adds path to the dict tracking paths belonging to this build phase.

    If the path is already a member of this build phase, raises an exception.
    """

    if path in self._files_by_path:
      raise ValueError, 'Found multiple build files with path ' + path
    self._files_by_path[path] = pbxbuildfile

  def _AddBuildFileToDicts(self, pbxbuildfile, path=None):
    """Maintains the _files_by_path and _files_by_xcfilelikeelement dicts.

    If path is specified, then it is the path that is being added to the
    phase, and pbxbuildfile must contain either a PBXFileReference directly
    referencing that path, or it must contain a PBXVariantGroup that itself
    contains a PBXFileReference referencing the path.

    If path is not specified, either the PBXFileReference's path or the paths
    of all children of the PBXVariantGroup are taken as being added to the
    phase.

    If the path is already present in the phase, raises an exception.

    If the PBXFileReference or PBXVariantGroup referenced by pbxbuildfile
    are already present in the phase, referenced by a different PBXBuildFile
    object, raises an exception.  This does not raise an exception when
    a PBXFileReference or PBXVariantGroup reappear and are referenced by the
    same PBXBuildFile that has already introduced them, because in the case
    of PBXVariantGroup objects, they may correspond to multiple paths that are
    not all added simultaneously.  When this situation occurs, the path needs
    to be added to _files_by_path, but nothing needs to change in
    _files_by_xcfilelikeelement, and the caller should have avoided adding
    the PBXBuildFile if it is already present in the list of children.
    """

    xcfilelikeelement = pbxbuildfile._properties['fileRef']

    paths = []
    if path != None:
      # It's best when the caller provides the path.
      if isinstance(xcfilelikeelement, PBXVariantGroup):
        paths.append(path)
    else:
      # If the caller didn't provide a path, there can be either multiple
      # paths (PBXVariantGroup) or one.
      if isinstance(xcfilelikeelement, PBXVariantGroup):
        for variant in xcfilelikeelement._properties['children']:
          paths.append(variant.FullPath())
      else:
        paths.append(xcfilelikeelement.FullPath())

    # Add the paths first, because if something's going to raise, the
    # messages provided by _AddPathToDict are more useful owing to its
    # having access to a real pathname and not just an object's Name().
    for a_path in paths:
      self._AddPathToDict(pbxbuildfile, a_path)

    # If another PBXBuildFile references this XCFileLikeElement, there's a
    # problem.
    if xcfilelikeelement in self._files_by_xcfilelikeelement and \
       self._files_by_xcfilelikeelement[xcfilelikeelement] != pbxbuildfile:
      raise ValueError, 'Found multiple build files for ' + \
                        xcfilelikeelement.Name()
    self._files_by_xcfilelikeelement[xcfilelikeelement] = pbxbuildfile

  def AppendBuildFile(self, pbxbuildfile, path=None):
    # Callers should use this instead of calling
    # AppendProperty('files', pbxbuildfile) directly because this function
    # maintains the object's dicts.  Better yet, callers can just call AddFile
    # with a pathname and not worry about building their own PBXBuildFile
    # objects.
    self.AppendProperty('files', pbxbuildfile)
    self._AddBuildFileToDicts(pbxbuildfile, path)

  def AddFile(self, path, settings=None):
    (file_group, hierarchical) = self.FileGroup(path)
    file_ref = file_group.AddOrGetFileByPath(path, hierarchical)

    if file_ref in self._files_by_xcfilelikeelement and \
       isinstance(file_ref, PBXVariantGroup):
      # There's already a PBXBuildFile in this phase corresponding to the
      # PBXVariantGroup.  path just provides a new variant that belongs to
      # the group.  Add the path to the dict.
      pbxbuildfile = self._files_by_xcfilelikeelement[file_ref]
      self._AddBuildFileToDicts(pbxbuildfile, path)
    else:
      # Add a new PBXBuildFile to get file_ref into the phase.
      if settings is None:
        pbxbuildfile = PBXBuildFile({'fileRef': file_ref})
      else:
        pbxbuildfile = PBXBuildFile({'fileRef': file_ref, 'settings': settings})
      self.AppendBuildFile(pbxbuildfile, path)


class PBXHeadersBuildPhase(XCBuildPhase):
  # No additions to the schema relative to XCBuildPhase.

  def Name(self):
    return 'Headers'

  def FileGroup(self, path):
    return self.PBXProjectAncestor().RootGroupForPath(path)


class PBXResourcesBuildPhase(XCBuildPhase):
  # No additions to the schema relative to XCBuildPhase.

  def Name(self):
    return 'Resources'

  def FileGroup(self, path):
    return self.PBXProjectAncestor().RootGroupForPath(path)


class PBXSourcesBuildPhase(XCBuildPhase):
  # No additions to the schema relative to XCBuildPhase.

  def Name(self):
    return 'Sources'

  def FileGroup(self, path):
    return self.PBXProjectAncestor().RootGroupForPath(path)


class PBXFrameworksBuildPhase(XCBuildPhase):
  # No additions to the schema relative to XCBuildPhase.

  def Name(self):
    return 'Frameworks'

  def FileGroup(self, path):
    (root, ext) = posixpath.splitext(path)
    if ext != '':
      ext = ext[1:].lower()
    if ext == 'o':
      # .o files are added to Xcode Frameworks phases, but conceptually aren't
      # frameworks, they're more like sources or intermediates. Redirect them
      # to show up in one of those other groups.
      return self.PBXProjectAncestor().RootGroupForPath(path)
    else:
      return (self.PBXProjectAncestor().FrameworksGroup(), False)


class PBXShellScriptBuildPhase(XCBuildPhase):
  _schema = XCBuildPhase._schema.copy()
  _schema.update({
    'inputPaths':       [1, str, 0, 1, []],
    'name':             [0, str, 0, 0],
    'outputPaths':      [1, str, 0, 1, []],
    'shellPath':        [0, str, 0, 1, '/bin/sh'],
    'shellScript':      [0, str, 0, 1],
    'showEnvVarsInLog': [0, int, 0, 0],
  })

  def Name(self):
    if 'name' in self._properties:
      return self._properties['name']

    return 'ShellScript'


class PBXCopyFilesBuildPhase(XCBuildPhase):
  _schema = XCBuildPhase._schema.copy()
  _schema.update({
    'dstPath':          [0, str, 0, 1],
    'dstSubfolderSpec': [0, int, 0, 1],
    'name':             [0, str, 0, 0],
  })

  # path_tree_re matches "$(DIR)/path" or just "$(DIR)".  Match group 1 is
  # "DIR", match group 3 is "path" or None.
  path_tree_re = re.compile('^\\$\\((.*)\\)(/(.*)|)$')

  # path_tree_to_subfolder maps names of Xcode variables to the associated
  # dstSubfolderSpec property value used in a PBXCopyFilesBuildPhase object.
  path_tree_to_subfolder = {
    'BUILT_PRODUCTS_DIR': 16,  # Products Directory
    # Other types that can be chosen via the Xcode UI.
    # TODO(mark): Map Xcode variable names to these.
    # : 1,  # Wrapper
    # : 6,  # Executables: 6
    # : 7,  # Resources
    # : 15,  # Java Resources
    # : 10,  # Frameworks
    # : 11,  # Shared Frameworks
    # : 12,  # Shared Support
    # : 13,  # PlugIns
  }

  def Name(self):
    if 'name' in self._properties:
      return self._properties['name']

    return 'CopyFiles'

  def FileGroup(self, path):
    return self.PBXProjectAncestor().RootGroupForPath(path)

  def SetDestination(self, path):
    """Set the dstSubfolderSpec and dstPath properties from path.

    path may be specified in the same notation used for XCHierarchicalElements,
    specifically, "$(DIR)/path".
    """

    path_tree_match = self.path_tree_re.search(path)
    if path_tree_match:
      # Everything else needs to be relative to an Xcode variable.
      path_tree = path_tree_match.group(1)
      relative_path = path_tree_match.group(3)

      if path_tree in self.path_tree_to_subfolder:
        subfolder = self.path_tree_to_subfolder[path_tree]
        if relative_path is None:
          relative_path = ''
      else:
        # The path starts with an unrecognized Xcode variable
        # name like $(SRCROOT).  Xcode will still handle this
        # as an "absolute path" that starts with the variable.
        subfolder = 0
        relative_path = path
    elif path.startswith('/'):
      # Special case.  Absolute paths are in dstSubfolderSpec 0.
      subfolder = 0
      relative_path = path[1:]
    else:
      raise ValueError, 'Can\'t use path %s in a %s' % \
                        (path, self.__class__.__name__)

    self._properties['dstPath'] = relative_path
    self._properties['dstSubfolderSpec'] = subfolder


class PBXBuildRule(XCObject):
  _schema = XCObject._schema.copy()
  _schema.update({
    'compilerSpec': [0, str, 0, 1],
    'filePatterns': [0, str, 0, 0],
    'fileType':     [0, str, 0, 1],
    'isEditable':   [0, int, 0, 1, 1],
    'outputFiles':  [1, str, 0, 1, []],
    'script':       [0, str, 0, 0],
  })

  def Name(self):
    # Not very inspired, but it's what Xcode uses.
    return self.__class__.__name__

  def Hashables(self):
    # super
    hashables = XCObject.Hashables(self)

    # Use the hashables of the weak objects that this object refers to.
    hashables.append(self._properties['fileType'])
    if 'filePatterns' in self._properties:
      hashables.append(self._properties['filePatterns'])
    return hashables


class PBXContainerItemProxy(XCObject):
  # When referencing an item in this project file, containerPortal is the
  # PBXProject root object of this project file.  When referencing an item in
  # another project file, containerPortal is a PBXFileReference identifying
  # the other project file.
  #
  # When serving as a proxy to an XCTarget (in this project file or another),
  # proxyType is 1.  When serving as a proxy to a PBXFileReference (in another
  # project file), proxyType is 2.  Type 2 is used for references to the
  # producs of the other project file's targets.
  #
  # Xcode is weird about remoteGlobalIDString.  Usually, it's printed without
  # a comment, indicating that it's tracked internally simply as a string, but
  # sometimes it's printed with a comment (usually when the object is initially
  # created), indicating that it's tracked as a project file object at least
  # sometimes.  This module always tracks it as an object, but contains a hack
  # to prevent it from printing the comment in the project file output.  See
  # _XCKVPrint.
  _schema = XCObject._schema.copy()
  _schema.update({
    'containerPortal':      [0, XCContainerPortal, 0, 1],
    'proxyType':            [0, int,               0, 1],
    'remoteGlobalIDString': [0, XCRemoteObject,    0, 1],
    'remoteInfo':           [0, str,               0, 1],
  })

  def __repr__(self):
    props = self._properties
    name = '%s.gyp:%s' % (props['containerPortal'].Name(), props['remoteInfo'])
    return '<%s %r at 0x%x>' % (self.__class__.__name__, name, id(self))

  def Name(self):
    # Admittedly not the best name, but it's what Xcode uses.
    return self.__class__.__name__

  def Hashables(self):
    # super
    hashables = XCObject.Hashables(self)

    # Use the hashables of the weak objects that this object refers to.
    hashables.extend(self._properties['containerPortal'].Hashables())
    hashables.extend(self._properties['remoteGlobalIDString'].Hashables())
    return hashables


class PBXTargetDependency(XCObject):
  # The "target" property accepts an XCTarget object, and obviously not
  # NoneType.  But XCTarget is defined below, so it can't be put into the
  # schema yet.  The definition of PBXTargetDependency can't be moved below
  # XCTarget because XCTarget's own schema references PBXTargetDependency.
  # Python doesn't deal well with this circular relationship, and doesn't have
  # a real way to do forward declarations.  To work around, the type of
  # the "target" property is reset below, after XCTarget is defined.
  #
  # At least one of "name" and "target" is required.
  _schema = XCObject._schema.copy()
  _schema.update({
    'name':        [0, str,                   0, 0],
    'target':      [0, None.__class__,        0, 0],
    'targetProxy': [0, PBXContainerItemProxy, 1, 1],
  })

  def __repr__(self):
    name = self._properties.get('name') or self._properties['target'].Name()
    return '<%s %r at 0x%x>' % (self.__class__.__name__, name, id(self))

  def Name(self):
    # Admittedly not the best name, but it's what Xcode uses.
    return self.__class__.__name__

  def Hashables(self):
    # super
    hashables = XCObject.Hashables(self)

    # Use the hashables of the weak objects that this object refers to.
    hashables.extend(self._properties['targetProxy'].Hashables())
    return hashables


class PBXReferenceProxy(XCFileLikeElement):
  _schema = XCFileLikeElement._schema.copy()
  _schema.update({
    'fileType':  [0, str,                   0, 1],
    'path':      [0, str,                   0, 1],
    'remoteRef': [0, PBXContainerItemProxy, 1, 1],
  })


class XCTarget(XCRemoteObject):
  # An XCTarget is really just an XCObject, the XCRemoteObject thing is just
  # to allow PBXProject to be used in the remoteGlobalIDString property of
  # PBXContainerItemProxy.
  #
  # Setting a "name" property at instantiation may also affect "productName",
  # which may in turn affect the "PRODUCT_NAME" build setting in children of
  # "buildConfigurationList".  See __init__ below.
  _schema = XCRemoteObject._schema.copy()
  _schema.update({
    'buildConfigurationList': [0, XCConfigurationList, 1, 1,
                               XCConfigurationList()],
    'buildPhases':            [1, XCBuildPhase,        1, 1, []],
    'dependencies':           [1, PBXTargetDependency, 1, 1, []],
    'name':                   [0, str,                 0, 1],
    'productName':            [0, str,                 0, 1],
  })

  def __init__(self, properties=None, id=None, parent=None,
               force_outdir=None, force_prefix=None, force_extension=None):
    # super
    XCRemoteObject.__init__(self, properties, id, parent)

    # Set up additional defaults not expressed in the schema.  If a "name"
    # property was supplied, set "productName" if it is not present.  Also set
    # the "PRODUCT_NAME" build setting in each configuration, but only if
    # the setting is not present in any build configuration.
    if 'name' in self._properties:
      if not 'productName' in self._properties:
        self.SetProperty('productName', self._properties['name'])

    if 'productName' in self._properties:
      if 'buildConfigurationList' in self._properties:
        configs = self._properties['buildConfigurationList']
        if configs.HasBuildSetting('PRODUCT_NAME') == 0:
          configs.SetBuildSetting('PRODUCT_NAME',
                                  self._properties['productName'])

  def AddDependency(self, other):
    pbxproject = self.PBXProjectAncestor()
    other_pbxproject = other.PBXProjectAncestor()
    if pbxproject == other_pbxproject:
      # Add a dependency to another target in the same project file.
      container = PBXContainerItemProxy({'containerPortal':      pbxproject,
                                         'proxyType':            1,
                                         'remoteGlobalIDString': other,
                                         'remoteInfo':           other.Name()})
      dependency = PBXTargetDependency({'target':      other,
                                        'targetProxy': container})
      self.AppendProperty('dependencies', dependency)
    else:
      # Add a dependency to a target in a different project file.
      other_project_ref = \
          pbxproject.AddOrGetProjectReference(other_pbxproject)[1]
      container = PBXContainerItemProxy({
            'containerPortal':      other_project_ref,
            'proxyType':            1,
            'remoteGlobalIDString': other,
            'remoteInfo':           other.Name(),
          })
      dependency = PBXTargetDependency({'name':        other.Name(),
                                        'targetProxy': container})
      self.AppendProperty('dependencies', dependency)

  # Proxy all of these through to the build configuration list.

  def ConfigurationNamed(self, name):
    return self._properties['buildConfigurationList'].ConfigurationNamed(name)

  def DefaultConfiguration(self):
    return self._properties['buildConfigurationList'].DefaultConfiguration()

  def HasBuildSetting(self, key):
    return self._properties['buildConfigurationList'].HasBuildSetting(key)

  def GetBuildSetting(self, key):
    return self._properties['buildConfigurationList'].GetBuildSetting(key)

  def SetBuildSetting(self, key, value):
    return self._properties['buildConfigurationList'].SetBuildSetting(key, \
                                                                      value)

  def AppendBuildSetting(self, key, value):
    return self._properties['buildConfigurationList'].AppendBuildSetting(key, \
                                                                         value)

  def DelBuildSetting(self, key):
    return self._properties['buildConfigurationList'].DelBuildSetting(key)


# Redefine the type of the "target" property.  See PBXTargetDependency._schema
# above.
PBXTargetDependency._schema['target'][1] = XCTarget


class PBXNativeTarget(XCTarget):
  # buildPhases is overridden in the schema to be able to set defaults.
  #
  # NOTE: Contrary to most objects, it is advisable to set parent when
  # constructing PBXNativeTarget.  A parent of an XCTarget must be a PBXProject
  # object.  A parent reference is required for a PBXNativeTarget during
  # construction to be able to set up the target defaults for productReference,
  # because a PBXBuildFile object must be created for the target and it must
  # be added to the PBXProject's mainGroup hierarchy.
  _schema = XCTarget._schema.copy()
  _schema.update({
    'buildPhases':      [1, XCBuildPhase,     1, 1,
                         [PBXSourcesBuildPhase(), PBXFrameworksBuildPhase()]],
    'buildRules':       [1, PBXBuildRule,     1, 1, []],
    'productReference': [0, PBXFileReference, 0, 1],
    'productType':      [0, str,              0, 1],
  })

  # Mapping from Xcode product-types to settings.  The settings are:
  #  filetype : used for explicitFileType in the project file
  #  prefix : the prefix for the file name
  #  suffix : the suffix for the filen ame
  _product_filetypes = {
    'com.apple.product-type.application':     ['wrapper.application',
                                               '', '.app'],
    'com.apple.product-type.bundle':          ['wrapper.cfbundle',
                                               '', '.bundle'],
    'com.apple.product-type.framework':       ['wrapper.framework',
                                               '', '.framework'],
    'com.apple.product-type.library.dynamic': ['compiled.mach-o.dylib',
                                               'lib', '.dylib'],
    'com.apple.product-type.library.static':  ['archive.ar',
                                               'lib', '.a'],
    'com.apple.product-type.tool':            ['compiled.mach-o.executable',
                                               '', ''],
    'com.googlecode.gyp.xcode.bundle':        ['compiled.mach-o.dylib',
                                               '', '.so'],
  }

  def __init__(self, properties=None, id=None, parent=None,
               force_outdir=None, force_prefix=None, force_extension=None):
    # super
    XCTarget.__init__(self, properties, id, parent)

    if 'productName' in self._properties and \
       'productType' in self._properties and \
       not 'productReference' in self._properties and \
       self._properties['productType'] in self._product_filetypes:
      products_group = None
      pbxproject = self.PBXProjectAncestor()
      if pbxproject != None:
        products_group = pbxproject.ProductsGroup()

      if products_group != None:
        (filetype, prefix, suffix) = \
            self._product_filetypes[self._properties['productType']]
        # Xcode does not have a distinct type for loadable modules that are
        # pure BSD targets (not in a bundle wrapper). GYP allows such modules
        # to be specified by setting a target type to loadable_module without
        # having mac_bundle set. These are mapped to the pseudo-product type
        # com.googlecode.gyp.xcode.bundle.
        #
        # By picking up this special type and converting it to a dynamic
        # library (com.apple.product-type.library.dynamic) with fix-ups,
        # single-file loadable modules can be produced.
        #
        # MACH_O_TYPE is changed to mh_bundle to produce the proper file type
        # (as opposed to mh_dylib). In order for linking to succeed,
        # DYLIB_CURRENT_VERSION and DYLIB_COMPATIBILITY_VERSION must be
        # cleared. They are meaningless for type mh_bundle.
        #
        # Finally, the .so extension is forcibly applied over the default
        # (.dylib), unless another forced extension is already selected.
        # .dylib is plainly wrong, and .bundle is used by loadable_modules in
        # bundle wrappers (com.apple.product-type.bundle). .so seems an odd
        # choice because it's used as the extension on many other systems that
        # don't distinguish between linkable shared libraries and non-linkable
        # loadable modules, but there's precedent: Python loadable modules on
        # Mac OS X use an .so extension.
        if self._properties['productType'] == 'com.googlecode.gyp.xcode.bundle':
          self._properties['productType'] = \
              'com.apple.product-type.library.dynamic'
          self.SetBuildSetting('MACH_O_TYPE', 'mh_bundle')
          self.SetBuildSetting('DYLIB_CURRENT_VERSION', '')
          self.SetBuildSetting('DYLIB_COMPATIBILITY_VERSION', '')
          if force_extension is None:
            force_extension = suffix[1:]

        if force_extension is not None:
          # If it's a wrapper (bundle), set WRAPPER_EXTENSION.
          if filetype.startswith('wrapper.'):
            self.SetBuildSetting('WRAPPER_EXTENSION', force_extension)
          else:
            # Extension override.
            suffix = '.' + force_extension
            self.SetBuildSetting('EXECUTABLE_EXTENSION', force_extension)

          if filetype.startswith('compiled.mach-o.executable'):
            product_name = self._properties['productName']
            product_name += suffix
            suffix = ''
            self.SetProperty('productName', product_name)
            self.SetBuildSetting('PRODUCT_NAME', product_name)

        # Xcode handles most prefixes based on the target type, however there
        # are exceptions.  If a "BSD Dynamic Library" target is added in the
        # Xcode UI, Xcode sets EXECUTABLE_PREFIX.  This check duplicates that
        # behavior.
        if force_prefix is not None:
          prefix = force_prefix
        if filetype.startswith('wrapper.'):
          self.SetBuildSetting('WRAPPER_PREFIX', prefix)
        else:
          self.SetBuildSetting('EXECUTABLE_PREFIX', prefix)

        if force_outdir is not None:
          self.SetBuildSetting('TARGET_BUILD_DIR', force_outdir)

        # TODO(tvl): Remove the below hack.
        #    http://code.google.com/p/gyp/issues/detail?id=122

        # Some targets include the prefix in the target_name.  These targets
        # really should just add a product_name setting that doesn't include
        # the prefix.  For example:
        #  target_name = 'libevent', product_name = 'event'
        # This check cleans up for them.
        product_name = self._properties['productName']
        prefix_len = len(prefix)
        if prefix_len and (product_name[:prefix_len] == prefix):
          product_name = product_name[prefix_len:]
          self.SetProperty('productName', product_name)
          self.SetBuildSetting('PRODUCT_NAME', product_name)

        ref_props = {
          'explicitFileType': filetype,
          'includeInIndex':   0,
          'path':             prefix + product_name + suffix,
          'sourceTree':       'BUILT_PRODUCTS_DIR',
        }
        file_ref = PBXFileReference(ref_props)
        products_group.AppendChild(file_ref)
        self.SetProperty('productReference', file_ref)

  def GetBuildPhaseByType(self, type):
    if not 'buildPhases' in self._properties:
      return None

    the_phase = None
    for phase in self._properties['buildPhases']:
      if isinstance(phase, type):
        # Some phases may be present in multiples in a well-formed project file,
        # but phases like PBXSourcesBuildPhase may only be present singly, and
        # this function is intended as an aid to GetBuildPhaseByType.  Loop
        # over the entire list of phases and assert if more than one of the
        # desired type is found.
        assert the_phase is None
        the_phase = phase

    return the_phase

  def HeadersPhase(self):
    headers_phase = self.GetBuildPhaseByType(PBXHeadersBuildPhase)
    if headers_phase is None:
      headers_phase = PBXHeadersBuildPhase()

      # The headers phase should come before the resources, sources, and
      # frameworks phases, if any.
      insert_at = len(self._properties['buildPhases'])
      for index in xrange(0, len(self._properties['buildPhases'])):
        phase = self._properties['buildPhases'][index]
        if isinstance(phase, PBXResourcesBuildPhase) or \
           isinstance(phase, PBXSourcesBuildPhase) or \
           isinstance(phase, PBXFrameworksBuildPhase):
          insert_at = index
          break

      self._properties['buildPhases'].insert(insert_at, headers_phase)
      headers_phase.parent = self

    return headers_phase

  def ResourcesPhase(self):
    resources_phase = self.GetBuildPhaseByType(PBXResourcesBuildPhase)
    if resources_phase is None:
      resources_phase = PBXResourcesBuildPhase()

      # The resources phase should come before the sources and frameworks
      # phases, if any.
      insert_at = len(self._properties['buildPhases'])
      for index in xrange(0, len(self._properties['buildPhases'])):
        phase = self._properties['buildPhases'][index]
        if isinstance(phase, PBXSourcesBuildPhase) or \
           isinstance(phase, PBXFrameworksBuildPhase):
          insert_at = index
          break

      self._properties['buildPhases'].insert(insert_at, resources_phase)
      resources_phase.parent = self

    return resources_phase

  def SourcesPhase(self):
    sources_phase = self.GetBuildPhaseByType(PBXSourcesBuildPhase)
    if sources_phase is None:
      sources_phase = PBXSourcesBuildPhase()
      self.AppendProperty('buildPhases', sources_phase)

    return sources_phase

  def FrameworksPhase(self):
    frameworks_phase = self.GetBuildPhaseByType(PBXFrameworksBuildPhase)
    if frameworks_phase is None:
      frameworks_phase = PBXFrameworksBuildPhase()
      self.AppendProperty('buildPhases', frameworks_phase)

    return frameworks_phase

  def AddDependency(self, other):
    # super
    XCTarget.AddDependency(self, other)

    static_library_type = 'com.apple.product-type.library.static'
    shared_library_type = 'com.apple.product-type.library.dynamic'
    framework_type = 'com.apple.product-type.framework'
    if isinstance(other, PBXNativeTarget) and \
       'productType' in self._properties and \
       self._properties['productType'] != static_library_type and \
       'productType' in other._properties and \
       (other._properties['productType'] == static_library_type or \
        ((other._properties['productType'] == shared_library_type or \
          other._properties['productType'] == framework_type) and \
         ((not other.HasBuildSetting('MACH_O_TYPE')) or
          other.GetBuildSetting('MACH_O_TYPE') != 'mh_bundle'))):

      file_ref = other.GetProperty('productReference')

      pbxproject = self.PBXProjectAncestor()
      other_pbxproject = other.PBXProjectAncestor()
      if pbxproject != other_pbxproject:
        other_project_product_group = \
            pbxproject.AddOrGetProjectReference(other_pbxproject)[0]
        file_ref = other_project_product_group.GetChildByRemoteObject(file_ref)

      self.FrameworksPhase().AppendProperty('files',
                                            PBXBuildFile({'fileRef': file_ref}))


class PBXAggregateTarget(XCTarget):
  pass


class PBXProject(XCContainerPortal):
  # A PBXProject is really just an XCObject, the XCContainerPortal thing is
  # just to allow PBXProject to be used in the containerPortal property of
  # PBXContainerItemProxy.
  """

  Attributes:
    path: "sample.xcodeproj".  TODO(mark) Document me!
    _other_pbxprojects: A dictionary, keyed by other PBXProject objects.  Each
                        value is a reference to the dict in the
                        projectReferences list associated with the keyed
                        PBXProject.
  """

  _schema = XCContainerPortal._schema.copy()
  _schema.update({
    'attributes':             [0, dict,                0, 0],
    'buildConfigurationList': [0, XCConfigurationList, 1, 1,
                               XCConfigurationList()],
    'compatibilityVersion':   [0, str,                 0, 1, 'Xcode 3.2'],
    'hasScannedForEncodings': [0, int,                 0, 1, 1],
    'mainGroup':              [0, PBXGroup,            1, 1, PBXGroup()],
    'projectDirPath':         [0, str,                 0, 1, ''],
    'projectReferences':      [1, dict,                0, 0],
    'projectRoot':            [0, str,                 0, 1, ''],
    'targets':                [1, XCTarget,            1, 1, []],
  })

  def __init__(self, properties=None, id=None, parent=None, path=None):
    self.path = path
    self._other_pbxprojects = {}
    # super
    return XCContainerPortal.__init__(self, properties, id, parent)

  def Name(self):
    name = self.path
    if name[-10:] == '.xcodeproj':
      name = name[:-10]
    return posixpath.basename(name)

  def Path(self):
    return self.path

  def Comment(self):
    return 'Project object'

  def Children(self):
    # super
    children = XCContainerPortal.Children(self)

    # Add children that the schema doesn't know about.  Maybe there's a more
    # elegant way around this, but this is the only case where we need to own
    # objects in a dictionary (that is itself in a list), and three lines for
    # a one-off isn't that big a deal.
    if 'projectReferences' in self._properties:
      for reference in self._properties['projectReferences']:
        children.append(reference['ProductGroup'])

    return children

  def PBXProjectAncestor(self):
    return self

  def _GroupByName(self, name):
    if not 'mainGroup' in self._properties:
      self.SetProperty('mainGroup', PBXGroup())

    main_group = self._properties['mainGroup']
    group = main_group.GetChildByName(name)
    if group is None:
      group = PBXGroup({'name': name})
      main_group.AppendChild(group)

    return group

  # SourceGroup and ProductsGroup are created by default in Xcode's own
  # templates.
  def SourceGroup(self):
    return self._GroupByName('Source')

  def ProductsGroup(self):
    return self._GroupByName('Products')

  # IntermediatesGroup is used to collect source-like files that are generated
  # by rules or script phases and are placed in intermediate directories such
  # as DerivedSources.
  def IntermediatesGroup(self):
    return self._GroupByName('Intermediates')

  # FrameworksGroup and ProjectsGroup are top-level groups used to collect
  # frameworks and projects.
  def FrameworksGroup(self):
    return self._GroupByName('Frameworks')

  def ProjectsGroup(self):
    return self._GroupByName('Projects')

  def RootGroupForPath(self, path):
    """Returns a PBXGroup child of this object to which path should be added.

    This method is intended to choose between SourceGroup and
    IntermediatesGroup on the basis of whether path is present in a source
    directory or an intermediates directory.  For the purposes of this
    determination, any path located within a derived file directory such as
    PROJECT_DERIVED_FILE_DIR is treated as being in an intermediates
    directory.

    The returned value is a two-element tuple.  The first element is the
    PBXGroup, and the second element specifies whether that group should be
    organized hierarchically (True) or as a single flat list (False).
    """

    # TODO(mark): make this a class variable and bind to self on call?
    # Also, this list is nowhere near exhaustive.
    # INTERMEDIATE_DIR and SHARED_INTERMEDIATE_DIR are used by
    # gyp.generator.xcode.  There should probably be some way for that module
    # to push the names in, rather than having to hard-code them here.
    source_tree_groups = {
      'DERIVED_FILE_DIR':         (self.IntermediatesGroup, True),
      'INTERMEDIATE_DIR':         (self.IntermediatesGroup, True),
      'PROJECT_DERIVED_FILE_DIR': (self.IntermediatesGroup, True),
      'SHARED_INTERMEDIATE_DIR':  (self.IntermediatesGroup, True),
    }

    (source_tree, path) = SourceTreeAndPathFromPath(path)
    if source_tree != None and source_tree in source_tree_groups:
      (group_func, hierarchical) = source_tree_groups[source_tree]
      group = group_func()
      return (group, hierarchical)

    # TODO(mark): make additional choices based on file extension.

    return (self.SourceGroup(), True)

  def AddOrGetFileInRootGroup(self, path):
    """Returns a PBXFileReference corresponding to path in the correct group
    according to RootGroupForPath's heuristics.

    If an existing PBXFileReference for path exists, it will be returned.
    Otherwise, one will be created and returned.
    """

    (group, hierarchical) = self.RootGroupForPath(path)
    return group.AddOrGetFileByPath(path, hierarchical)

  def RootGroupsTakeOverOnlyChildren(self, recurse=False):
    """Calls TakeOverOnlyChild for all groups in the main group."""

    for group in self._properties['mainGroup']._properties['children']:
      if isinstance(group, PBXGroup):
        group.TakeOverOnlyChild(recurse)

  def SortGroups(self):
    # Sort the children of the mainGroup (like "Source" and "Products")
    # according to their defined order.
    self._properties['mainGroup']._properties['children'] = \
        sorted(self._properties['mainGroup']._properties['children'],
               cmp=lambda x,y: x.CompareRootGroup(y))

    # Sort everything else by putting group before files, and going
    # alphabetically by name within sections of groups and files.  SortGroup
    # is recursive.
    for group in self._properties['mainGroup']._properties['children']:
      if not isinstance(group, PBXGroup):
        continue

      if group.Name() == 'Products':
        # The Products group is a special case.  Instead of sorting
        # alphabetically, sort things in the order of the targets that
        # produce the products.  To do this, just build up a new list of
        # products based on the targets.
        products = []
        for target in self._properties['targets']:
          if not isinstance(target, PBXNativeTarget):
            continue
          product = target._properties['productReference']
          # Make sure that the product is already in the products group.
          assert product in group._properties['children']
          products.append(product)

        # Make sure that this process doesn't miss anything that was already
        # in the products group.
        assert len(products) == len(group._properties['children'])
        group._properties['children'] = products
      else:
        group.SortGroup()

  def AddOrGetProjectReference(self, other_pbxproject):
    """Add a reference to another project file (via PBXProject object) to this
    one.

    Returns [ProductGroup, ProjectRef].  ProductGroup is a PBXGroup object in
    this project file that contains a PBXReferenceProxy object for each
    product of each PBXNativeTarget in the other project file.  ProjectRef is
    a PBXFileReference to the other project file.

    If this project file already references the other project file, the
    existing ProductGroup and ProjectRef are returned.  The ProductGroup will
    still be updated if necessary.
    """

    if not 'projectReferences' in self._properties:
      self._properties['projectReferences'] = []

    product_group = None
    project_ref = None

    if not other_pbxproject in self._other_pbxprojects:
      # This project file isn't yet linked to the other one.  Establish the
      # link.
      product_group = PBXGroup({'name': 'Products'})

      # ProductGroup is strong.
      product_group.parent = self

      # There's nothing unique about this PBXGroup, and if left alone, it will
      # wind up with the same set of hashables as all other PBXGroup objects
      # owned by the projectReferences list.  Add the hashables of the
      # remote PBXProject that it's related to.
      product_group._hashables.extend(other_pbxproject.Hashables())

      # The other project reports its path as relative to the same directory
      # that this project's path is relative to.  The other project's path
      # is not necessarily already relative to this project.  Figure out the
      # pathname that this project needs to use to refer to the other one.
      this_path = posixpath.dirname(self.Path())
      projectDirPath = self.GetProperty('projectDirPath')
      if projectDirPath:
        if posixpath.isabs(projectDirPath[0]):
          this_path = projectDirPath
        else:
          this_path = posixpath.join(this_path, projectDirPath)
      other_path = gyp.common.RelativePath(other_pbxproject.Path(), this_path)

      # ProjectRef is weak (it's owned by the mainGroup hierarchy).
      project_ref = PBXFileReference({
            'lastKnownFileType': 'wrapper.pb-project',
            'path':              other_path,
            'sourceTree':        'SOURCE_ROOT',
          })
      self.ProjectsGroup().AppendChild(project_ref)

      ref_dict = {'ProductGroup': product_group, 'ProjectRef': project_ref}
      self._other_pbxprojects[other_pbxproject] = ref_dict
      self.AppendProperty('projectReferences', ref_dict)

      # Xcode seems to sort this list case-insensitively
      self._properties['projectReferences'] = \
          sorted(self._properties['projectReferences'], cmp=lambda x,y:
                 cmp(x['ProjectRef'].Name().lower(),
                     y['ProjectRef'].Name().lower()))
    else:
      # The link already exists.  Pull out the relevnt data.
      project_ref_dict = self._other_pbxprojects[other_pbxproject]
      product_group = project_ref_dict['ProductGroup']
      project_ref = project_ref_dict['ProjectRef']

    self._SetUpProductReferences(other_pbxproject, product_group, project_ref)

    return [product_group, project_ref]

  def _SetUpProductReferences(self, other_pbxproject, product_group,
                              project_ref):
    # TODO(mark): This only adds references to products in other_pbxproject
    # when they don't exist in this pbxproject.  Perhaps it should also
    # remove references from this pbxproject that are no longer present in
    # other_pbxproject.  Perhaps it should update various properties if they
    # change.
    for target in other_pbxproject._properties['targets']:
      if not isinstance(target, PBXNativeTarget):
        continue

      other_fileref = target._properties['productReference']
      if product_group.GetChildByRemoteObject(other_fileref) is None:
        # Xcode sets remoteInfo to the name of the target and not the name
        # of its product, despite this proxy being a reference to the product.
        container_item = PBXContainerItemProxy({
              'containerPortal':      project_ref,
              'proxyType':            2,
              'remoteGlobalIDString': other_fileref,
              'remoteInfo':           target.Name()
            })
        # TODO(mark): Does sourceTree get copied straight over from the other
        # project?  Can the other project ever have lastKnownFileType here
        # instead of explicitFileType?  (Use it if so?)  Can path ever be
        # unset?  (I don't think so.)  Can other_fileref have name set, and
        # does it impact the PBXReferenceProxy if so?  These are the questions
        # that perhaps will be answered one day.
        reference_proxy = PBXReferenceProxy({
              'fileType':   other_fileref._properties['explicitFileType'],
              'path':       other_fileref._properties['path'],
              'sourceTree': other_fileref._properties['sourceTree'],
              'remoteRef':  container_item,
            })

        product_group.AppendChild(reference_proxy)

  def SortRemoteProductReferences(self):
    # For each remote project file, sort the associated ProductGroup in the
    # same order that the targets are sorted in the remote project file.  This
    # is the sort order used by Xcode.

    def CompareProducts(x, y, remote_products):
      # x and y are PBXReferenceProxy objects.  Go through their associated
      # PBXContainerItem to get the remote PBXFileReference, which will be
      # present in the remote_products list.
      x_remote = x._properties['remoteRef']._properties['remoteGlobalIDString']
      y_remote = y._properties['remoteRef']._properties['remoteGlobalIDString']
      x_index = remote_products.index(x_remote)
      y_index = remote_products.index(y_remote)

      # Use the order of each remote PBXFileReference in remote_products to
      # determine the sort order.
      return cmp(x_index, y_index)

    for other_pbxproject, ref_dict in self._other_pbxprojects.iteritems():
      # Build up a list of products in the remote project file, ordered the
      # same as the targets that produce them.
      remote_products = []
      for target in other_pbxproject._properties['targets']:
        if not isinstance(target, PBXNativeTarget):
          continue
        remote_products.append(target._properties['productReference'])

      # Sort the PBXReferenceProxy children according to the list of remote
      # products.
      product_group = ref_dict['ProductGroup']
      product_group._properties['children'] = sorted(
          product_group._properties['children'],
          cmp=lambda x, y: CompareProducts(x, y, remote_products))


class XCProjectFile(XCObject):
  _schema = XCObject._schema.copy()
  _schema.update({
    'archiveVersion': [0, int,        0, 1, 1],
    'classes':        [0, dict,       0, 1, {}],
    'objectVersion':  [0, int,        0, 1, 45],
    'rootObject':     [0, PBXProject, 1, 1],
  })

  def SetXcodeVersion(self, version):
    version_to_object_version = {
      '2.4': 45,
      '3.0': 45,
      '3.1': 45,
      '3.2': 46,
    }
    if not version in version_to_object_version:
      supported_str = ', '.join(sorted(version_to_object_version.keys()))
      raise Exception(
          'Unsupported Xcode version %s (supported: %s)' %
          ( version, supported_str ) )
    compatibility_version = 'Xcode %s' % version
    self._properties['rootObject'].SetProperty('compatibilityVersion',
                                               compatibility_version)
    self.SetProperty('objectVersion', version_to_object_version[version]);

  def ComputeIDs(self, recursive=True, overwrite=True, hash=None):
    # Although XCProjectFile is implemented here as an XCObject, it's not a
    # proper object in the Xcode sense, and it certainly doesn't have its own
    # ID.  Pass through an attempt to update IDs to the real root object.
    if recursive:
      self._properties['rootObject'].ComputeIDs(recursive, overwrite, hash)

  def Print(self, file=sys.stdout):
    self.VerifyHasRequiredProperties()

    # Add the special "objects" property, which will be caught and handled
    # separately during printing.  This structure allows a fairly standard
    # loop do the normal printing.
    self._properties['objects'] = {}
    self._XCPrint(file, 0, '// !$*UTF8*$!\n')
    if self._should_print_single_line:
      self._XCPrint(file, 0, '{ ')
    else:
      self._XCPrint(file, 0, '{\n')
    for property, value in sorted(self._properties.iteritems(),
                                  cmp=lambda x, y: cmp(x, y)):
      if property == 'objects':
        self._PrintObjects(file)
      else:
        self._XCKVPrint(file, 1, property, value)
    self._XCPrint(file, 0, '}\n')
    del self._properties['objects']

  def _PrintObjects(self, file):
    if self._should_print_single_line:
      self._XCPrint(file, 0, 'objects = {')
    else:
      self._XCPrint(file, 1, 'objects = {\n')

    objects_by_class = {}
    for object in self.Descendants():
      if object == self:
        continue
      class_name = object.__class__.__name__
      if not class_name in objects_by_class:
        objects_by_class[class_name] = []
      objects_by_class[class_name].append(object)

    for class_name in sorted(objects_by_class):
      self._XCPrint(file, 0, '\n')
      self._XCPrint(file, 0, '/* Begin ' + class_name + ' section */\n')
      for object in sorted(objects_by_class[class_name],
                           cmp=lambda x, y: cmp(x.id, y.id)):
        object.Print(file)
      self._XCPrint(file, 0, '/* End ' + class_name + ' section */\n')

    if self._should_print_single_line:
      self._XCPrint(file, 0, '}; ')
    else:
      self._XCPrint(file, 1, '};\n')

########NEW FILE########
__FILENAME__ = xcode_emulation
# Copyright (c) 2012 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
This module contains classes that help to emulate xcodebuild behavior on top of
other build systems, such as make and ninja.
"""

import gyp.common
import os.path
import re
import shlex

class XcodeSettings(object):
  """A class that understands the gyp 'xcode_settings' object."""

  # Computed lazily by _GetSdkBaseDir(). Shared by all XcodeSettings, so cached
  # at class-level for efficiency.
  _sdk_base_dir = None

  def __init__(self, spec):
    self.spec = spec

    # Per-target 'xcode_settings' are pushed down into configs earlier by gyp.
    # This means self.xcode_settings[config] always contains all settings
    # for that config -- the per-target settings as well. Settings that are
    # the same for all configs are implicitly per-target settings.
    self.xcode_settings = {}
    configs = spec['configurations']
    for configname, config in configs.iteritems():
      self.xcode_settings[configname] = config.get('xcode_settings', {})

    # This is only non-None temporarily during the execution of some methods.
    self.configname = None

    # Used by _AdjustLibrary to match .a and .dylib entries in libraries.
    self.library_re = re.compile(r'^lib([^/]+)\.(a|dylib)$')

  def _Settings(self):
    assert self.configname
    return self.xcode_settings[self.configname]

  def _Test(self, test_key, cond_key, default):
    return self._Settings().get(test_key, default) == cond_key

  def _Appendf(self, lst, test_key, format_str, default=None):
    if test_key in self._Settings():
      lst.append(format_str % str(self._Settings()[test_key]))
    elif default:
      lst.append(format_str % str(default))

  def _WarnUnimplemented(self, test_key):
    if test_key in self._Settings():
      print 'Warning: Ignoring not yet implemented key "%s".' % test_key

  def _IsBundle(self):
    return int(self.spec.get('mac_bundle', 0)) != 0

  def GetFrameworkVersion(self):
    """Returns the framework version of the current target. Only valid for
    bundles."""
    assert self._IsBundle()
    return self.GetPerTargetSetting('FRAMEWORK_VERSION', default='A')

  def GetWrapperExtension(self):
    """Returns the bundle extension (.app, .framework, .plugin, etc).  Only
    valid for bundles."""
    assert self._IsBundle()
    if self.spec['type'] in ('loadable_module', 'shared_library'):
      default_wrapper_extension = {
        'loadable_module': 'bundle',
        'shared_library': 'framework',
      }[self.spec['type']]
      wrapper_extension = self.GetPerTargetSetting(
          'WRAPPER_EXTENSION', default=default_wrapper_extension)
      return '.' + self.spec.get('product_extension', wrapper_extension)
    elif self.spec['type'] == 'executable':
      return '.app'
    else:
      assert False, "Don't know extension for '%s', target '%s'" % (
          self.spec['type'], self.spec['target_name'])

  def GetProductName(self):
    """Returns PRODUCT_NAME."""
    return self.spec.get('product_name', self.spec['target_name'])

  def GetFullProductName(self):
    """Returns FULL_PRODUCT_NAME."""
    if self._IsBundle():
      return self.GetWrapperName()
    else:
      return self._GetStandaloneBinaryPath()

  def GetWrapperName(self):
    """Returns the directory name of the bundle represented by this target.
    Only valid for bundles."""
    assert self._IsBundle()
    return self.GetProductName() + self.GetWrapperExtension()

  def GetBundleContentsFolderPath(self):
    """Returns the qualified path to the bundle's contents folder. E.g.
    Chromium.app/Contents or Foo.bundle/Versions/A. Only valid for bundles."""
    assert self._IsBundle()
    if self.spec['type'] == 'shared_library':
      return os.path.join(
          self.GetWrapperName(), 'Versions', self.GetFrameworkVersion())
    else:
      # loadable_modules have a 'Contents' folder like executables.
      return os.path.join(self.GetWrapperName(), 'Contents')

  def GetBundleResourceFolder(self):
    """Returns the qualified path to the bundle's resource folder. E.g.
    Chromium.app/Contents/Resources. Only valid for bundles."""
    assert self._IsBundle()
    return os.path.join(self.GetBundleContentsFolderPath(), 'Resources')

  def GetBundlePlistPath(self):
    """Returns the qualified path to the bundle's plist file. E.g.
    Chromium.app/Contents/Info.plist. Only valid for bundles."""
    assert self._IsBundle()
    if self.spec['type'] in ('executable', 'loadable_module'):
      return os.path.join(self.GetBundleContentsFolderPath(), 'Info.plist')
    else:
      return os.path.join(self.GetBundleContentsFolderPath(),
                          'Resources', 'Info.plist')

  def GetProductType(self):
    """Returns the PRODUCT_TYPE of this target."""
    if self._IsBundle():
      return {
        'executable': 'com.apple.product-type.application',
        'loadable_module': 'com.apple.product-type.bundle',
        'shared_library': 'com.apple.product-type.framework',
      }[self.spec['type']]
    else:
      return {
        'executable': 'com.apple.product-type.tool',
        'loadable_module': 'com.apple.product-type.library.dynamic',
        'shared_library': 'com.apple.product-type.library.dynamic',
        'static_library': 'com.apple.product-type.library.static',
      }[self.spec['type']]

  def GetMachOType(self):
    """Returns the MACH_O_TYPE of this target."""
    # Weird, but matches Xcode.
    if not self._IsBundle() and self.spec['type'] == 'executable':
      return ''
    return {
      'executable': 'mh_execute',
      'static_library': 'staticlib',
      'shared_library': 'mh_dylib',
      'loadable_module': 'mh_bundle',
    }[self.spec['type']]

  def _GetBundleBinaryPath(self):
    """Returns the name of the bundle binary of by this target.
    E.g. Chromium.app/Contents/MacOS/Chromium. Only valid for bundles."""
    assert self._IsBundle()
    if self.spec['type'] in ('shared_library'):
      path = self.GetBundleContentsFolderPath()
    elif self.spec['type'] in ('executable', 'loadable_module'):
      path = os.path.join(self.GetBundleContentsFolderPath(), 'MacOS')
    return os.path.join(path, self.GetExecutableName())

  def _GetStandaloneExecutableSuffix(self):
    if 'product_extension' in self.spec:
      return '.' + self.spec['product_extension']
    return {
      'executable': '',
      'static_library': '.a',
      'shared_library': '.dylib',
      'loadable_module': '.so',
    }[self.spec['type']]

  def _GetStandaloneExecutablePrefix(self):
    return self.spec.get('product_prefix', {
      'executable': '',
      'static_library': 'lib',
      'shared_library': 'lib',
      # Non-bundled loadable_modules are called foo.so for some reason
      # (that is, .so and no prefix) with the xcode build -- match that.
      'loadable_module': '',
    }[self.spec['type']])

  def _GetStandaloneBinaryPath(self):
    """Returns the name of the non-bundle binary represented by this target.
    E.g. hello_world. Only valid for non-bundles."""
    assert not self._IsBundle()
    assert self.spec['type'] in (
        'executable', 'shared_library', 'static_library', 'loadable_module'), (
        'Unexpected type %s' % self.spec['type'])
    target = self.spec['target_name']
    if self.spec['type'] == 'static_library':
      if target[:3] == 'lib':
        target = target[3:]
    elif self.spec['type'] in ('loadable_module', 'shared_library'):
      if target[:3] == 'lib':
        target = target[3:]

    target_prefix = self._GetStandaloneExecutablePrefix()
    target = self.spec.get('product_name', target)
    target_ext = self._GetStandaloneExecutableSuffix()
    return target_prefix + target + target_ext

  def GetExecutableName(self):
    """Returns the executable name of the bundle represented by this target.
    E.g. Chromium."""
    if self._IsBundle():
      return self.spec.get('product_name', self.spec['target_name'])
    else:
      return self._GetStandaloneBinaryPath()

  def GetExecutablePath(self):
    """Returns the directory name of the bundle represented by this target. E.g.
    Chromium.app/Contents/MacOS/Chromium."""
    if self._IsBundle():
      return self._GetBundleBinaryPath()
    else:
      return self._GetStandaloneBinaryPath()

  def _GetSdkBaseDir(self):
    """Returns the root of the 'Developer' directory. On Xcode 4.2 and prior,
    this is usually just /Developer. Xcode 4.3 moved that folder into the Xcode
    bundle."""
    if not XcodeSettings._sdk_base_dir:
      import subprocess
      job = subprocess.Popen(['xcode-select', '-print-path'],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
      out, err = job.communicate()
      if job.returncode != 0:
        print out
        raise Exception('Error %d running xcode-select' % job.returncode)
      # The Developer folder moved in Xcode 4.3.
      xcode43_sdk_path = os.path.join(
          out.rstrip(), 'Platforms/MacOSX.platform/Developer/SDKs')
      if os.path.isdir(xcode43_sdk_path):
        XcodeSettings._sdk_base_dir = xcode43_sdk_path
      else:
        XcodeSettings._sdk_base_dir = os.path.join(out.rstrip(), 'SDKs')
    return XcodeSettings._sdk_base_dir

  def _SdkPath(self):
    sdk_root = self.GetPerTargetSetting('SDKROOT', default='macosx10.5')
    if sdk_root.startswith('macosx'):
      return os.path.join(self._GetSdkBaseDir(),
                          'MacOSX' + sdk_root[len('macosx'):] + '.sdk')
    return sdk_root

  def GetCflags(self, configname):
    """Returns flags that need to be added to .c, .cc, .m, and .mm
    compilations."""
    # This functions (and the similar ones below) do not offer complete
    # emulation of all xcode_settings keys. They're implemented on demand.

    self.configname = configname
    cflags = []

    sdk_root = self._SdkPath()
    if 'SDKROOT' in self._Settings():
      cflags.append('-isysroot %s' % sdk_root)

    if self._Test('GCC_CHAR_IS_UNSIGNED_CHAR', 'YES', default='NO'):
      cflags.append('-funsigned-char')

    if self._Test('GCC_CW_ASM_SYNTAX', 'YES', default='YES'):
      cflags.append('-fasm-blocks')

    if 'GCC_DYNAMIC_NO_PIC' in self._Settings():
      if self._Settings()['GCC_DYNAMIC_NO_PIC'] == 'YES':
        cflags.append('-mdynamic-no-pic')
    else:
      pass
      # TODO: In this case, it depends on the target. xcode passes
      # mdynamic-no-pic by default for executable and possibly static lib
      # according to mento

    if self._Test('GCC_ENABLE_PASCAL_STRINGS', 'YES', default='YES'):
      cflags.append('-mpascal-strings')

    self._Appendf(cflags, 'GCC_OPTIMIZATION_LEVEL', '-O%s', default='s')

    if self._Test('GCC_GENERATE_DEBUGGING_SYMBOLS', 'YES', default='YES'):
      dbg_format = self._Settings().get('DEBUG_INFORMATION_FORMAT', 'dwarf')
      if dbg_format == 'dwarf':
        cflags.append('-gdwarf-2')
      elif dbg_format == 'stabs':
        raise NotImplementedError('stabs debug format is not supported yet.')
      elif dbg_format == 'dwarf-with-dsym':
        cflags.append('-gdwarf-2')
      else:
        raise NotImplementedError('Unknown debug format %s' % dbg_format)

    if self._Test('GCC_SYMBOLS_PRIVATE_EXTERN', 'YES', default='NO'):
      cflags.append('-fvisibility=hidden')

    if self._Test('GCC_TREAT_WARNINGS_AS_ERRORS', 'YES', default='NO'):
      cflags.append('-Werror')

    if self._Test('GCC_WARN_ABOUT_MISSING_NEWLINE', 'YES', default='NO'):
      cflags.append('-Wnewline-eof')

    self._Appendf(cflags, 'MACOSX_DEPLOYMENT_TARGET', '-mmacosx-version-min=%s')

    # TODO:
    if self._Test('COPY_PHASE_STRIP', 'YES', default='NO'):
      self._WarnUnimplemented('COPY_PHASE_STRIP')
    self._WarnUnimplemented('GCC_DEBUGGING_SYMBOLS')
    self._WarnUnimplemented('GCC_ENABLE_OBJC_EXCEPTIONS')

    # TODO: This is exported correctly, but assigning to it is not supported.
    self._WarnUnimplemented('MACH_O_TYPE')
    self._WarnUnimplemented('PRODUCT_TYPE')

    archs = self._Settings().get('ARCHS', ['i386'])
    if len(archs) != 1:
      # TODO: Supporting fat binaries will be annoying.
      self._WarnUnimplemented('ARCHS')
      archs = ['i386']
    cflags.append('-arch ' + archs[0])

    if archs[0] in ('i386', 'x86_64'):
      if self._Test('GCC_ENABLE_SSE3_EXTENSIONS', 'YES', default='NO'):
        cflags.append('-msse3')
      if self._Test('GCC_ENABLE_SUPPLEMENTAL_SSE3_INSTRUCTIONS', 'YES',
                    default='NO'):
        cflags.append('-mssse3')  # Note 3rd 's'.
      if self._Test('GCC_ENABLE_SSE41_EXTENSIONS', 'YES', default='NO'):
        cflags.append('-msse4.1')
      if self._Test('GCC_ENABLE_SSE42_EXTENSIONS', 'YES', default='NO'):
        cflags.append('-msse4.2')

    cflags += self._Settings().get('WARNING_CFLAGS', [])

    config = self.spec['configurations'][self.configname]
    framework_dirs = config.get('mac_framework_dirs', [])
    for directory in framework_dirs:
      cflags.append('-F' + directory.replace('$(SDKROOT)', sdk_root))

    self.configname = None
    return cflags

  def GetCflagsC(self, configname):
    """Returns flags that need to be added to .c, and .m compilations."""
    self.configname = configname
    cflags_c = []
    self._Appendf(cflags_c, 'GCC_C_LANGUAGE_STANDARD', '-std=%s')
    cflags_c += self._Settings().get('OTHER_CFLAGS', [])
    self.configname = None
    return cflags_c

  def GetCflagsCC(self, configname):
    """Returns flags that need to be added to .cc, and .mm compilations."""
    self.configname = configname
    cflags_cc = []
    if self._Test('GCC_ENABLE_CPP_RTTI', 'NO', default='YES'):
      cflags_cc.append('-fno-rtti')
    if self._Test('GCC_ENABLE_CPP_EXCEPTIONS', 'NO', default='YES'):
      cflags_cc.append('-fno-exceptions')
    if self._Test('GCC_INLINES_ARE_PRIVATE_EXTERN', 'YES', default='NO'):
      cflags_cc.append('-fvisibility-inlines-hidden')
    if self._Test('GCC_THREADSAFE_STATICS', 'NO', default='YES'):
      cflags_cc.append('-fno-threadsafe-statics')
    if self._Test('GCC_WARN_ABOUT_INVALID_OFFSETOF_MACRO', 'NO', default='YES'):
      cflags_cc.append('-Wno-invalid-offsetof')

    other_ccflags = []

    for flag in self._Settings().get('OTHER_CPLUSPLUSFLAGS', ['$(inherited)']):
      # TODO: More general variable expansion. Missing in many other places too.
      if flag in ('$inherited', '$(inherited)', '${inherited}'):
        flag = '$OTHER_CFLAGS'
      if flag in ('$OTHER_CFLAGS', '$(OTHER_CFLAGS)', '${OTHER_CFLAGS}'):
        other_ccflags += self._Settings().get('OTHER_CFLAGS', [])
      else:
        other_ccflags.append(flag)
    cflags_cc += other_ccflags

    self.configname = None
    return cflags_cc

  def _AddObjectiveCGarbageCollectionFlags(self, flags):
    gc_policy = self._Settings().get('GCC_ENABLE_OBJC_GC', 'unsupported')
    if gc_policy == 'supported':
      flags.append('-fobjc-gc')
    elif gc_policy == 'required':
      flags.append('-fobjc-gc-only')

  def GetCflagsObjC(self, configname):
    """Returns flags that need to be added to .m compilations."""
    self.configname = configname
    cflags_objc = []

    self._AddObjectiveCGarbageCollectionFlags(cflags_objc)

    self.configname = None
    return cflags_objc

  def GetCflagsObjCC(self, configname):
    """Returns flags that need to be added to .mm compilations."""
    self.configname = configname
    cflags_objcc = []
    self._AddObjectiveCGarbageCollectionFlags(cflags_objcc)
    if self._Test('GCC_OBJC_CALL_CXX_CDTORS', 'YES', default='NO'):
      cflags_objcc.append('-fobjc-call-cxx-cdtors')
    self.configname = None
    return cflags_objcc

  def GetInstallNameBase(self):
    """Return DYLIB_INSTALL_NAME_BASE for this target."""
    # Xcode sets this for shared_libraries, and for nonbundled loadable_modules.
    if (self.spec['type'] != 'shared_library' and
        (self.spec['type'] != 'loadable_module' or self._IsBundle())):
      return None
    install_base = self.GetPerTargetSetting(
        'DYLIB_INSTALL_NAME_BASE',
        default='/Library/Frameworks' if self._IsBundle() else '/usr/local/lib')
    return install_base

  def _StandardizePath(self, path):
    """Do :standardizepath processing for path."""
    # I'm not quite sure what :standardizepath does. Just call normpath(),
    # but don't let @executable_path/../foo collapse to foo.
    if '/' in path:
      prefix, rest = '', path
      if path.startswith('@'):
        prefix, rest = path.split('/', 1)
      rest = os.path.normpath(rest)  # :standardizepath
      path = os.path.join(prefix, rest)
    return path

  def GetInstallName(self):
    """Return LD_DYLIB_INSTALL_NAME for this target."""
    # Xcode sets this for shared_libraries, and for nonbundled loadable_modules.
    if (self.spec['type'] != 'shared_library' and
        (self.spec['type'] != 'loadable_module' or self._IsBundle())):
      return None

    default_install_name = \
        '$(DYLIB_INSTALL_NAME_BASE:standardizepath)/$(EXECUTABLE_PATH)'
    install_name = self.GetPerTargetSetting(
        'LD_DYLIB_INSTALL_NAME', default=default_install_name)

    # Hardcode support for the variables used in chromium for now, to
    # unblock people using the make build.
    if '$' in install_name:
      assert install_name in ('$(DYLIB_INSTALL_NAME_BASE:standardizepath)/'
          '$(WRAPPER_NAME)/$(PRODUCT_NAME)', default_install_name), (
          'Variables in LD_DYLIB_INSTALL_NAME are not generally supported '
          'yet in target \'%s\' (got \'%s\')' %
              (self.spec['target_name'], install_name))

      install_name = install_name.replace(
          '$(DYLIB_INSTALL_NAME_BASE:standardizepath)',
          self._StandardizePath(self.GetInstallNameBase()))
      if self._IsBundle():
        # These are only valid for bundles, hence the |if|.
        install_name = install_name.replace(
            '$(WRAPPER_NAME)', self.GetWrapperName())
        install_name = install_name.replace(
            '$(PRODUCT_NAME)', self.GetProductName())
      else:
        assert '$(WRAPPER_NAME)' not in install_name
        assert '$(PRODUCT_NAME)' not in install_name

      install_name = install_name.replace(
          '$(EXECUTABLE_PATH)', self.GetExecutablePath())
    return install_name

  def _MapLinkerFlagFilename(self, ldflag, gyp_to_build_path):
    """Checks if ldflag contains a filename and if so remaps it from
    gyp-directory-relative to build-directory-relative."""
    # This list is expanded on demand.
    # They get matched as:
    #   -exported_symbols_list file
    #   -Wl,exported_symbols_list file
    #   -Wl,exported_symbols_list,file
    LINKER_FILE = '(\S+)'
    WORD = '\S+'
    linker_flags = [
      ['-exported_symbols_list', LINKER_FILE],    # Needed for NaCl.
      ['-unexported_symbols_list', LINKER_FILE],
      ['-reexported_symbols_list', LINKER_FILE],
      ['-sectcreate', WORD, WORD, LINKER_FILE],   # Needed for remoting.
    ]
    for flag_pattern in linker_flags:
      regex = re.compile('(?:-Wl,)?' + '[ ,]'.join(flag_pattern))
      m = regex.match(ldflag)
      if m:
        ldflag = ldflag[:m.start(1)] + gyp_to_build_path(m.group(1)) + \
                 ldflag[m.end(1):]
    # Required for ffmpeg (no idea why they don't use LIBRARY_SEARCH_PATHS,
    # TODO(thakis): Update ffmpeg.gyp):
    if ldflag.startswith('-L'):
      ldflag = '-L' + gyp_to_build_path(ldflag[len('-L'):])
    return ldflag

  def GetLdflags(self, configname, product_dir, gyp_to_build_path):
    """Returns flags that need to be passed to the linker.

    Args:
        configname: The name of the configuration to get ld flags for.
        product_dir: The directory where products such static and dynamic
            libraries are placed. This is added to the library search path.
        gyp_to_build_path: A function that converts paths relative to the
            current gyp file to paths relative to the build direcotry.
    """
    self.configname = configname
    ldflags = []

    # The xcode build is relative to a gyp file's directory, and OTHER_LDFLAGS
    # can contain entries that depend on this. Explicitly absolutify these.
    for ldflag in self._Settings().get('OTHER_LDFLAGS', []):
      ldflags.append(self._MapLinkerFlagFilename(ldflag, gyp_to_build_path))

    if self._Test('DEAD_CODE_STRIPPING', 'YES', default='NO'):
      ldflags.append('-Wl,-dead_strip')

    if self._Test('PREBINDING', 'YES', default='NO'):
      ldflags.append('-Wl,-prebind')

    self._Appendf(
        ldflags, 'DYLIB_COMPATIBILITY_VERSION', '-compatibility_version %s')
    self._Appendf(
        ldflags, 'DYLIB_CURRENT_VERSION', '-current_version %s')
    self._Appendf(
        ldflags, 'MACOSX_DEPLOYMENT_TARGET', '-mmacosx-version-min=%s')
    if 'SDKROOT' in self._Settings():
      ldflags.append('-isysroot ' + self._SdkPath())

    for library_path in self._Settings().get('LIBRARY_SEARCH_PATHS', []):
      ldflags.append('-L' + gyp_to_build_path(library_path))

    if 'ORDER_FILE' in self._Settings():
      ldflags.append('-Wl,-order_file ' +
                     '-Wl,' + gyp_to_build_path(
                                  self._Settings()['ORDER_FILE']))

    archs = self._Settings().get('ARCHS', ['i386'])
    if len(archs) != 1:
      # TODO: Supporting fat binaries will be annoying.
      self._WarnUnimplemented('ARCHS')
      archs = ['i386']
    ldflags.append('-arch ' + archs[0])

    # Xcode adds the product directory by default.
    ldflags.append('-L' + product_dir)

    install_name = self.GetInstallName()
    if install_name:
      ldflags.append('-install_name ' + install_name.replace(' ', r'\ '))

    for rpath in self._Settings().get('LD_RUNPATH_SEARCH_PATHS', []):
      ldflags.append('-Wl,-rpath,' + rpath)

    config = self.spec['configurations'][self.configname]
    framework_dirs = config.get('mac_framework_dirs', [])
    for directory in framework_dirs:
      ldflags.append('-F' + directory.replace('$(SDKROOT)', self._SdkPath()))

    self.configname = None
    return ldflags

  def GetLibtoolflags(self, configname):
    """Returns flags that need to be passed to the static linker.

    Args:
        configname: The name of the configuration to get ld flags for.
    """
    self.configname = configname
    libtoolflags = []

    for libtoolflag in self._Settings().get('OTHER_LDFLAGS', []):
      libtoolflags.append(libtoolflag)
    # TODO(thakis): ARCHS?

    self.configname = None
    return libtoolflags

  def GetPerTargetSettings(self):
    """Gets a list of all the per-target settings. This will only fetch keys
    whose values are the same across all configurations."""
    first_pass = True
    result = {}
    for configname in sorted(self.xcode_settings.keys()):
      if first_pass:
        result = dict(self.xcode_settings[configname])
        first_pass = False
      else:
        for key, value in self.xcode_settings[configname].iteritems():
          if key not in result:
            continue
          elif result[key] != value:
            del result[key]
    return result

  def GetPerTargetSetting(self, setting, default=None):
    """Tries to get xcode_settings.setting from spec. Assumes that the setting
       has the same value in all configurations and throws otherwise."""
    first_pass = True
    result = None
    for configname in sorted(self.xcode_settings.keys()):
      if first_pass:
        result = self.xcode_settings[configname].get(setting, None)
        first_pass = False
      else:
        assert result == self.xcode_settings[configname].get(setting, None), (
            "Expected per-target setting for '%s', got per-config setting "
            "(target %s)" % (setting, spec['target_name']))
    if result is None:
      return default
    return result

  def _GetStripPostbuilds(self, configname, output_binary, quiet):
    """Returns a list of shell commands that contain the shell commands
    neccessary to strip this target's binary. These should be run as postbuilds
    before the actual postbuilds run."""
    self.configname = configname

    result = []
    if (self._Test('DEPLOYMENT_POSTPROCESSING', 'YES', default='NO') and
        self._Test('STRIP_INSTALLED_PRODUCT', 'YES', default='NO')):

      default_strip_style = 'debugging'
      if self._IsBundle():
        default_strip_style = 'non-global'
      elif self.spec['type'] == 'executable':
        default_strip_style = 'all'

      strip_style = self._Settings().get('STRIP_STYLE', default_strip_style)
      strip_flags = {
        'all': '',
        'non-global': '-x',
        'debugging': '-S',
      }[strip_style]

      explicit_strip_flags = self._Settings().get('STRIPFLAGS', '')
      if explicit_strip_flags:
        strip_flags += ' ' + _NormalizeEnvVarReferences(explicit_strip_flags)

      if not quiet:
        result.append('echo STRIP\\(%s\\)' % self.spec['target_name'])
      result.append('strip %s %s' % (strip_flags, output_binary))

    self.configname = None
    return result

  def _GetDebugInfoPostbuilds(self, configname, output, output_binary, quiet):
    """Returns a list of shell commands that contain the shell commands
    neccessary to massage this target's debug information. These should be run
    as postbuilds before the actual postbuilds run."""
    self.configname = configname

    # For static libraries, no dSYMs are created.
    result = []
    if (self._Test('GCC_GENERATE_DEBUGGING_SYMBOLS', 'YES', default='YES') and
        self._Test(
            'DEBUG_INFORMATION_FORMAT', 'dwarf-with-dsym', default='dwarf') and
        self.spec['type'] != 'static_library'):
      if not quiet:
        result.append('echo DSYMUTIL\\(%s\\)' % self.spec['target_name'])
      result.append('dsymutil %s -o %s' % (output_binary, output + '.dSYM'))

    self.configname = None
    return result

  def GetTargetPostbuilds(self, configname, output, output_binary, quiet=False):
    """Returns a list of shell commands that contain the shell commands
    to run as postbuilds for this target, before the actual postbuilds."""
    # dSYMs need to build before stripping happens.
    return (
        self._GetDebugInfoPostbuilds(configname, output, output_binary, quiet) +
        self._GetStripPostbuilds(configname, output_binary, quiet))

  def _AdjustLibrary(self, library):
    if library.endswith('.framework'):
      l = '-framework ' + os.path.splitext(os.path.basename(library))[0]
    else:
      m = self.library_re.match(library)
      if m:
        l = '-l' + m.group(1)
      else:
        l = library
    return l.replace('$(SDKROOT)', self._SdkPath())

  def AdjustLibraries(self, libraries):
    """Transforms entries like 'Cocoa.framework' in libraries into entries like
    '-framework Cocoa', 'libcrypto.dylib' into '-lcrypto', etc.
    """
    libraries = [ self._AdjustLibrary(library) for library in libraries]
    return libraries


class MacPrefixHeader(object):
  """A class that helps with emulating Xcode's GCC_PREFIX_HEADER feature.

  This feature consists of several pieces:
  * If GCC_PREFIX_HEADER is present, all compilations in that project get an
    additional |-include path_to_prefix_header| cflag.
  * If GCC_PRECOMPILE_PREFIX_HEADER is present too, then the prefix header is
    instead compiled, and all other compilations in the project get an
    additional |-include path_to_compiled_header| instead.
    + Compiled prefix headers have the extension gch. There is one gch file for
      every language used in the project (c, cc, m, mm), since gch files for
      different languages aren't compatible.
    + gch files themselves are built with the target's normal cflags, but they
      obviously don't get the |-include| flag. Instead, they need a -x flag that
      describes their language.
    + All o files in the target need to depend on the gch file, to make sure
      it's built before any o file is built.

  This class helps with some of these tasks, but it needs help from the build
  system for writing dependencies to the gch files, for writing build commands
  for the gch files, and for figuring out the location of the gch files.
  """
  def __init__(self, xcode_settings,
               gyp_path_to_build_path, gyp_path_to_build_output):
    """If xcode_settings is None, all methods on this class are no-ops.

    Args:
        gyp_path_to_build_path: A function that takes a gyp-relative path,
            and returns a path relative to the build directory.
        gyp_path_to_build_output: A function that takes a gyp-relative path and
            a language code ('c', 'cc', 'm', or 'mm'), and that returns a path
            to where the output of precompiling that path for that language
            should be placed (without the trailing '.gch').
    """
    # This doesn't support per-configuration prefix headers. Good enough
    # for now.
    self.header = None
    self.compile_headers = False
    if xcode_settings:
      self.header = xcode_settings.GetPerTargetSetting('GCC_PREFIX_HEADER')
      self.compile_headers = xcode_settings.GetPerTargetSetting(
          'GCC_PRECOMPILE_PREFIX_HEADER', default='NO') != 'NO'
    self.compiled_headers = {}
    if self.header:
      if self.compile_headers:
        for lang in ['c', 'cc', 'm', 'mm']:
          self.compiled_headers[lang] = gyp_path_to_build_output(
              self.header, lang)
      self.header = gyp_path_to_build_path(self.header)

  def GetInclude(self, lang):
    """Gets the cflags to include the prefix header for language |lang|."""
    if self.compile_headers and lang in self.compiled_headers:
      return '-include %s' % self.compiled_headers[lang]
    elif self.header:
      return '-include %s' % self.header
    else:
      return ''

  def _Gch(self, lang):
    """Returns the actual file name of the prefix header for language |lang|."""
    assert self.compile_headers
    return self.compiled_headers[lang] + '.gch'

  def GetObjDependencies(self, sources, objs):
    """Given a list of source files and the corresponding object files, returns
    a list of (source, object, gch) tuples, where |gch| is the build-directory
    relative path to the gch file each object file depends on.  |compilable[i]|
    has to be the source file belonging to |objs[i]|."""
    if not self.header or not self.compile_headers:
      return []

    result = []
    for source, obj in zip(sources, objs):
      ext = os.path.splitext(source)[1]
      lang = {
        '.c': 'c',
        '.cpp': 'cc', '.cc': 'cc', '.cxx': 'cc',
        '.m': 'm',
        '.mm': 'mm',
      }.get(ext, None)
      if lang:
        result.append((source, obj, self._Gch(lang)))
    return result

  def GetPchBuildCommands(self):
    """Returns [(path_to_gch, language_flag, language, header)].
    |path_to_gch| and |header| are relative to the build directory.
    """
    if not self.header or not self.compile_headers:
      return []
    return [
      (self._Gch('c'), '-x c-header', 'c', self.header),
      (self._Gch('cc'), '-x c++-header', 'cc', self.header),
      (self._Gch('m'), '-x objective-c-header', 'm', self.header),
      (self._Gch('mm'), '-x objective-c++-header', 'mm', self.header),
    ]


def MergeGlobalXcodeSettingsToSpec(global_dict, spec):
  """Merges the global xcode_settings dictionary into each configuration of the
  target represented by spec. For keys that are both in the global and the local
  xcode_settings dict, the local key gets precendence.
  """
  # The xcode generator special-cases global xcode_settings and does something
  # that amounts to merging in the global xcode_settings into each local
  # xcode_settings dict.
  global_xcode_settings = global_dict.get('xcode_settings', {})
  for config in spec['configurations'].values():
    if 'xcode_settings' in config:
      new_settings = global_xcode_settings.copy()
      new_settings.update(config['xcode_settings'])
      config['xcode_settings'] = new_settings


def IsMacBundle(flavor, spec):
  """Returns if |spec| should be treated as a bundle.

  Bundles are directories with a certain subdirectory structure, instead of
  just a single file. Bundle rules do not produce a binary but also package
  resources into that directory."""
  is_mac_bundle = (int(spec.get('mac_bundle', 0)) != 0 and flavor == 'mac')
  if is_mac_bundle:
    assert spec['type'] != 'none', (
        'mac_bundle targets cannot have type none (target "%s")' %
        spec['target_name'])
  return is_mac_bundle


def GetMacBundleResources(product_dir, xcode_settings, resources):
  """Yields (output, resource) pairs for every resource in |resources|.
  Only call this for mac bundle targets.

  Args:
      product_dir: Path to the directory containing the output bundle,
          relative to the build directory.
      xcode_settings: The XcodeSettings of the current target.
      resources: A list of bundle resources, relative to the build directory.
  """
  dest = os.path.join(product_dir,
                      xcode_settings.GetBundleResourceFolder())
  for res in resources:
    output = dest

    # The make generator doesn't support it, so forbid it everywhere
    # to keep the generators more interchangable.
    assert ' ' not in res, (
      "Spaces in resource filenames not supported (%s)"  % res)

    # Split into (path,file).
    res_parts = os.path.split(res)

    # Now split the path into (prefix,maybe.lproj).
    lproj_parts = os.path.split(res_parts[0])
    # If the resource lives in a .lproj bundle, add that to the destination.
    if lproj_parts[1].endswith('.lproj'):
      output = os.path.join(output, lproj_parts[1])

    output = os.path.join(output, res_parts[1])
    # Compiled XIB files are referred to by .nib.
    if output.endswith('.xib'):
      output = output[0:-3] + 'nib'

    yield output, res


def GetMacInfoPlist(product_dir, xcode_settings, gyp_path_to_build_path):
  """Returns (info_plist, dest_plist, defines, extra_env), where:
  * |info_plist| is the sourc plist path, relative to the
    build directory,
  * |dest_plist| is the destination plist path, relative to the
    build directory,
  * |defines| is a list of preprocessor defines (empty if the plist
    shouldn't be preprocessed,
  * |extra_env| is a dict of env variables that should be exported when
    invoking |mac_tool copy-info-plist|.

  Only call this for mac bundle targets.

  Args:
      product_dir: Path to the directory containing the output bundle,
          relative to the build directory.
      xcode_settings: The XcodeSettings of the current target.
      gyp_to_build_path: A function that converts paths relative to the
          current gyp file to paths relative to the build direcotry.
  """
  info_plist = xcode_settings.GetPerTargetSetting('INFOPLIST_FILE')
  if not info_plist:
    return None, None, [], {}

  # The make generator doesn't support it, so forbid it everywhere
  # to keep the generators more interchangable.
  assert ' ' not in info_plist, (
    "Spaces in Info.plist filenames not supported (%s)"  % info_plist)

  info_plist = gyp_path_to_build_path(info_plist)

  # If explicitly set to preprocess the plist, invoke the C preprocessor and
  # specify any defines as -D flags.
  if xcode_settings.GetPerTargetSetting(
      'INFOPLIST_PREPROCESS', default='NO') == 'YES':
    # Create an intermediate file based on the path.
    defines = shlex.split(xcode_settings.GetPerTargetSetting(
        'INFOPLIST_PREPROCESSOR_DEFINITIONS', default=''))
  else:
    defines = []

  dest_plist = os.path.join(product_dir, xcode_settings.GetBundlePlistPath())
  extra_env = xcode_settings.GetPerTargetSettings()

  return info_plist, dest_plist, defines, extra_env


def _GetXcodeEnv(xcode_settings, built_products_dir, srcroot, configuration,
                additional_settings=None):
  """Return the environment variables that Xcode would set. See
  http://developer.apple.com/library/mac/#documentation/DeveloperTools/Reference/XcodeBuildSettingRef/1-Build_Setting_Reference/build_setting_ref.html#//apple_ref/doc/uid/TP40003931-CH3-SW153
  for a full list.

  Args:
      xcode_settings: An XcodeSettings object. If this is None, this function
          returns an empty dict.
      built_products_dir: Absolute path to the built products dir.
      srcroot: Absolute path to the source root.
      configuration: The build configuration name.
      additional_settings: An optional dict with more values to add to the
          result.
  """
  if not xcode_settings: return {}

  # This function is considered a friend of XcodeSettings, so let it reach into
  # its implementation details.
  spec = xcode_settings.spec

  # These are filled in on a as-needed basis.
  env = {
    'BUILT_PRODUCTS_DIR' : built_products_dir,
    'CONFIGURATION' : configuration,
    'PRODUCT_NAME' : xcode_settings.GetProductName(),
    # See /Developer/Platforms/MacOSX.platform/Developer/Library/Xcode/Specifications/MacOSX\ Product\ Types.xcspec for FULL_PRODUCT_NAME
    'SRCROOT' : srcroot,
    'SOURCE_ROOT': '${SRCROOT}',
    # This is not true for static libraries, but currently the env is only
    # written for bundles:
    'TARGET_BUILD_DIR' : built_products_dir,
    'TEMP_DIR' : '${TMPDIR}',
  }
  if xcode_settings.GetPerTargetSetting('SDKROOT'):
    env['SDKROOT'] = xcode_settings._SdkPath()
  else:
    env['SDKROOT'] = ''

  if spec['type'] in (
      'executable', 'static_library', 'shared_library', 'loadable_module'):
    env['EXECUTABLE_NAME'] = xcode_settings.GetExecutableName()
    env['EXECUTABLE_PATH'] = xcode_settings.GetExecutablePath()
    env['FULL_PRODUCT_NAME'] = xcode_settings.GetFullProductName()
    mach_o_type = xcode_settings.GetMachOType()
    if mach_o_type:
      env['MACH_O_TYPE'] = mach_o_type
    env['PRODUCT_TYPE'] = xcode_settings.GetProductType()
  if xcode_settings._IsBundle():
    env['CONTENTS_FOLDER_PATH'] = \
      xcode_settings.GetBundleContentsFolderPath()
    env['UNLOCALIZED_RESOURCES_FOLDER_PATH'] = \
        xcode_settings.GetBundleResourceFolder()
    env['INFOPLIST_PATH'] = xcode_settings.GetBundlePlistPath()
    env['WRAPPER_NAME'] = xcode_settings.GetWrapperName()

  install_name = xcode_settings.GetInstallName()
  if install_name:
    env['LD_DYLIB_INSTALL_NAME'] = install_name
  install_name_base = xcode_settings.GetInstallNameBase()
  if install_name_base:
    env['DYLIB_INSTALL_NAME_BASE'] = install_name_base

  if not additional_settings:
    additional_settings = {}
  else:
    # Flatten lists to strings.
    for k in additional_settings:
      if not isinstance(additional_settings[k], str):
        additional_settings[k] = ' '.join(additional_settings[k])
  additional_settings.update(env)

  for k in additional_settings:
    additional_settings[k] = _NormalizeEnvVarReferences(additional_settings[k])

  return additional_settings


def _NormalizeEnvVarReferences(str):
  """Takes a string containing variable references in the form ${FOO}, $(FOO),
  or $FOO, and returns a string with all variable references in the form ${FOO}.
  """
  # $FOO -> ${FOO}
  str = re.sub(r'\$([a-zA-Z_][a-zA-Z0-9_]*)', r'${\1}', str)

  # $(FOO) -> ${FOO}
  matches = re.findall(r'(\$\(([a-zA-Z0-9\-_]+)\))', str)
  for match in matches:
    to_replace, variable = match
    assert '$(' not in match, '$($(FOO)) variables not supported: ' + match
    str = str.replace(to_replace, '${' + variable + '}')

  return str


def ExpandEnvVars(string, expansions):
  """Expands ${VARIABLES}, $(VARIABLES), and $VARIABLES in string per the
  expansions list. If the variable expands to something that references
  another variable, this variable is expanded as well if it's in env --
  until no variables present in env are left."""
  for k, v in reversed(expansions):
    string = string.replace('${' + k + '}', v)
    string = string.replace('$(' + k + ')', v)
    string = string.replace('$' + k, v)
  return string


def _TopologicallySortedEnvVarKeys(env):
  """Takes a dict |env| whose values are strings that can refer to other keys,
  for example env['foo'] = '$(bar) and $(baz)'. Returns a list L of all keys of
  env such that key2 is after key1 in L if env[key2] refers to env[key1].

  Throws an Exception in case of dependency cycles.
  """
  # Since environment variables can refer to other variables, the evaluation
  # order is important. Below is the logic to compute the dependency graph
  # and sort it.
  regex = re.compile(r'\$\{([a-zA-Z0-9\-_]+)\}')
  def GetEdges(node):
    # Use a definition of edges such that user_of_variable -> used_varible.
    # This happens to be easier in this case, since a variable's
    # definition contains all variables it references in a single string.
    # We can then reverse the result of the topological sort at the end.
    # Since: reverse(topsort(DAG)) = topsort(reverse_edges(DAG))
    matches = set([v for v in regex.findall(env[node]) if v in env])
    for dependee in matches:
      assert '${' not in dependee, 'Nested variables not supported: ' + dependee
    return matches

  try:
    # Topologically sort, and then reverse, because we used an edge definition
    # that's inverted from the expected result of this function (see comment
    # above).
    order = gyp.common.TopologicallySorted(env.keys(), GetEdges)
    order.reverse()
    return order
  except gyp.common.CycleError, e:
    raise Exception(
        'Xcode environment variables are cyclically dependent: ' + str(e.nodes))


def GetSortedXcodeEnv(xcode_settings, built_products_dir, srcroot,
                      configuration, additional_settings=None):
  env = _GetXcodeEnv(xcode_settings, built_products_dir, srcroot, configuration,
                    additional_settings)
  return [(key, env[key]) for key in _TopologicallySortedEnvVarKeys(env)]


def GetSpecPostbuildCommands(spec, quiet=False):
  """Returns the list of postbuilds explicitly defined on |spec|, in a form
  executable by a shell."""
  postbuilds = []
  for postbuild in spec.get('postbuilds', []):
    if not quiet:
      postbuilds.append('echo POSTBUILD\\(%s\\) %s' % (
            spec['target_name'], postbuild['postbuild_name']))
    postbuilds.append(gyp.common.EncodePOSIXShellList(postbuild['action']))
  return postbuilds

########NEW FILE########
__FILENAME__ = xml_fix
# Copyright (c) 2011 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Applies a fix to CR LF TAB handling in xml.dom.

Fixes this: http://code.google.com/p/chromium/issues/detail?id=76293
Working around this: http://bugs.python.org/issue5752
TODO(bradnelson): Consider dropping this when we drop XP support.
"""


import xml.dom.minidom


def _Replacement_write_data(writer, data, is_attrib=False):
  """Writes datachars to writer."""
  data = data.replace("&", "&amp;").replace("<", "&lt;")
  data = data.replace("\"", "&quot;").replace(">", "&gt;")
  if is_attrib:
    data = data.replace(
        "\r", "&#xD;").replace(
        "\n", "&#xA;").replace(
        "\t", "&#x9;")
  writer.write(data)


def _Replacement_writexml(self, writer, indent="", addindent="", newl=""):
  # indent = current indentation
  # addindent = indentation to add to higher levels
  # newl = newline string
  writer.write(indent+"<" + self.tagName)

  attrs = self._get_attributes()
  a_names = attrs.keys()
  a_names.sort()

  for a_name in a_names:
    writer.write(" %s=\"" % a_name)
    _Replacement_write_data(writer, attrs[a_name].value, is_attrib=True)
    writer.write("\"")
  if self.childNodes:
    writer.write(">%s" % newl)
    for node in self.childNodes:
      node.writexml(writer, indent + addindent, addindent, newl)
    writer.write("%s</%s>%s" % (indent, self.tagName, newl))
  else:
    writer.write("/>%s" % newl)


class XmlFix(object):
  """Object to manage temporary patching of xml.dom.minidom."""

  def __init__(self):
    # Preserve current xml.dom.minidom functions.
    self.write_data = xml.dom.minidom._write_data
    self.writexml = xml.dom.minidom.Element.writexml
    # Inject replacement versions of a function and a method.
    xml.dom.minidom._write_data = _Replacement_write_data
    xml.dom.minidom.Element.writexml = _Replacement_writexml

  def Cleanup(self):
    if self.write_data:
      xml.dom.minidom._write_data = self.write_data
      xml.dom.minidom.Element.writexml = self.writexml
      self.write_data = None

  def __del__(self):
    self.Cleanup()

########NEW FILE########
