__FILENAME__ = api
"""frosted/api.py.

Defines the api for the command-line frosted utility

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or
substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED
TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR

"""
import os
import re
import sys
import tokenize
from io import StringIO
from token import N_TOKENS

from pies.overrides import *

import _ast
from frosted import reporter as modReporter
from frosted import checker, settings
from frosted.messages import FileSkipped, PythonSyntaxError

__all__ = ['check', 'check_path', 'check_recursive', 'iter_source_code']

_re_noqa = re.compile(r'((frosted)[:=]\s*noqa)|(#\s*noqa)', re.I)


def _noqa_lines(codeString):
    line_nums = []
    g = tokenize.generate_tokens(StringIO(str(codeString)).readline)   # tokenize the string
    for toknum, tokval, begins, _, _ in g:
        lineno = begins[0]
        # not sure what N_TOKENS really means, but in testing, that was what comments were
        # tokenized as
        if toknum == N_TOKENS:
            if _re_noqa.search(tokval):
                line_nums.append(lineno)
    return line_nums


def _should_skip(filename, skip):
    if filename in skip:
        return True

    position = os.path.split(filename)
    while position[1]:
        if position[1] in skip:
            return True
        position = os.path.split(position[0])


def check(codeString, filename, reporter=modReporter.Default, settings_path=None, **setting_overrides):
    """Check the Python source given by codeString for unfrosted flakes."""

    if not settings_path and filename:
        settings_path = os.path.dirname(os.path.abspath(filename))
    settings_path = settings_path or os.getcwd()

    active_settings = settings.from_path(settings_path).copy()
    for key, value in itemsview(setting_overrides):
        access_key = key.replace('not_', '').lower()
        if type(active_settings.get(access_key)) in (list, tuple):
            if key.startswith('not_'):
                active_settings[access_key] = list(set(active_settings[access_key]).difference(value))
            else:
                active_settings[access_key] = list(set(active_settings[access_key]).union(value))
        else:
            active_settings[key] = value
    active_settings.update(setting_overrides)

    if _should_skip(filename, active_settings.get('skip', [])):
        if active_settings.get('directly_being_checked', None) == 1:
            reporter.flake(FileSkipped(filename))
            return 1
        elif active_settings.get('verbose', False):
            ignore = active_settings.get('ignore_frosted_errors', [])
            if(not "W200" in ignore and not "W201" in ignore):
                reporter.flake(FileSkipped(filename, None, verbose=active_settings.get('verbose')))
        return 0

    # First, compile into an AST and handle syntax errors.
    try:
        tree = compile(codeString, filename, "exec", _ast.PyCF_ONLY_AST)
    except SyntaxError:
        value = sys.exc_info()[1]
        msg = value.args[0]

        (lineno, offset, text) = value.lineno, value.offset, value.text

        # If there's an encoding problem with the file, the text is None.
        if text is None:
            # Avoid using msg, since for the only known case, it contains a
            # bogus message that claims the encoding the file declared was
            # unknown.
            reporter.unexpected_error(filename, 'problem decoding source')
        else:
            reporter.flake(PythonSyntaxError(filename, msg, lineno, offset, text,
                                             verbose=active_settings.get('verbose')))
        return 1
    except Exception:
        reporter.unexpected_error(filename, 'problem decoding source')
        return 1
    # Okay, it's syntactically valid.  Now check it.
    w = checker.Checker(tree, filename, None, ignore_lines=_noqa_lines(codeString), **active_settings)
    w.messages.sort(key=lambda m: m.lineno)
    for warning in w.messages:
        reporter.flake(warning)
    return len(w.messages)


def check_path(filename, reporter=modReporter.Default, settings_path=None, **setting_overrides):
    """Check the given path, printing out any warnings detected."""
    try:
        with open(filename, 'U') as f:
            codestr = f.read() + '\n'
    except UnicodeError:
        reporter.unexpected_error(filename, 'problem decoding source')
        return 1
    except IOError:
        msg = sys.exc_info()[1]
        reporter.unexpected_error(filename, msg.args[1])
        return 1
    return check(codestr, filename, reporter, settings_path, **setting_overrides)


def iter_source_code(paths):
    """Iterate over all Python source files defined in paths."""
    for path in paths:
        if os.path.isdir(path):
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    if filename.endswith('.py'):
                        yield os.path.join(dirpath, filename)
        else:
            yield path


def check_recursive(paths, reporter=modReporter.Default, settings_path=None, **setting_overrides):
    """Recursively check all source files defined in paths."""
    warnings = 0
    for source_path in iter_source_code(paths):
        warnings += check_path(source_path, reporter, settings_path=None, **setting_overrides)
    return warnings

########NEW FILE########
__FILENAME__ = checker
"""frosted/checker.py.

The core functionality of frosted lives here. Implements the core checking capability models Bindings and Scopes

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or
substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED
TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

"""
from __future__ import absolute_import, division, print_function, unicode_literals

import builtins
import doctest
import itertools
import os
import sys

from pies import ast
from pies.overrides import *

from frosted import messages

PY34_GTE = sys.version_info >= (3, 4)
FROSTED_BUILTINS = set(dir(builtins) + ['__file__', '__builtins__', '__debug__', '__name__', 'WindowsError',
                                        '__import__'] +
                       os.environ.get('PYFLAKES_BUILTINS', '').split(','))

def node_name(node):
    """
        Convenience function: Returns node.id, or node.name, or None
    """
    return hasattr(node, 'id') and node.id or hasattr(node, 'name') and node.name


class Binding(object):
    """Represents the binding of a value to a name.

    The checker uses this to keep track of which names have been bound and which names have not. See Assignment for a
    special type of binding that is checked with stricter rules.

    """
    __slots__ = ('name', 'source', 'used')

    def __init__(self, name, source):
        self.name = name
        self.source = source
        self.used = False

    def __str__(self):
        return self.name

    def __repr__(self):
        return '<%s object %r from line %r at 0x%x>' % (self.__class__.__name__,
                                                        self.name,
                                                        self.source.lineno,
                                                        id(self))


class Importation(Binding):
    """A binding created by an import statement."""
    __slots__ = ('fullName', )

    def __init__(self, name, source):
        self.fullName = name
        name = name.split('.')[0]
        super(Importation, self).__init__(name, source)


class Argument(Binding):
    """Represents binding a name as an argument."""
    __slots__ = ()


class Definition(Binding):
    """A binding that defines a function or a class."""
    __slots__ = ()


class Assignment(Binding):
    """Represents binding a name with an explicit assignment.

    The checker will raise warnings for any Assignment that isn't used. Also, the checker does not consider assignments
    in tuple/list unpacking to be Assignments, rather it treats them as simple Bindings.

    """
    __slots__ = ()


class FunctionDefinition(Definition):
    __slots__ = ('signature', )

    def __init__(self, name, source):
        super(FunctionDefinition, self).__init__(name, source)
        self.signature = FunctionSignature(source)


class ClassDefinition(Definition):
    __slots__ = ()


class ExportBinding(Binding):
    """A binding created by an __all__ assignment.  If the names in the list
    can be determined statically, they will be treated as names for export and
    additional checking applied to them.

    The only __all__ assignment that can be recognized is one which takes
    the value of a literal list containing literal strings.  For example:

        __all__ = ["foo", "bar"]

    Names which are imported and not otherwise used but appear in the value of
    __all__ will not have an unused import warning reported for them.

    """
    __slots__ = ()

    def names(self):
        """Return a list of the names referenced by this binding."""
        names = []
        if isinstance(self.source, ast.List):
            for node in self.source.elts:
                if isinstance(node, ast.Str):
                    names.append(node.s)
        return names


class Scope(dict):
    importStarred = False       # set to True when import * is found

    def __repr__(self):
        scope_cls = self.__class__.__name__
        return '<%s at 0x%x %s>' % (scope_cls, id(self), dict.__repr__(self))


class ClassScope(Scope):
    pass


class FunctionScope(Scope):
    """Represents the name scope for a function."""
    uses_locals = False
    always_used = set(['__tracebackhide__', '__traceback_info__', '__traceback_supplement__'])

    def __init__(self):
        Scope.__init__(self)
        self.globals = self.always_used.copy()

    def unusedAssignments(self):
        """Return a generator for the assignments which have not been used."""
        for name, binding in self.items():
            if (not binding.used and name not in self.globals
                    and not self.uses_locals
                    and isinstance(binding, Assignment)):
                yield name, binding


class GeneratorScope(Scope):
    pass


class ModuleScope(Scope):
    pass


class FunctionSignature(object):
    __slots__ = ('decorated', 'argument_names', 'default_count', 'kw_only_argument_names', 'default_count',
                 'kw_only_argument_names', 'kw_only_default_count', 'has_var_arg', 'has_kw_arg')

    def __init__(self, node):
        self.decorated = bool(any(node.decorator_list))
        self.argument_names = ast.argument_names(node)
        self.default_count = len(node.args.defaults)
        self.kw_only_argument_names = ast.kw_only_argument_names(node)
        self.kw_only_default_count = ast.kw_only_default_count(node)
        self.has_var_arg = node.args.vararg is not None
        self.has_kw_arg = node.args.kwarg is not None

    def min_argument_count(self):
        return len(self.argument_names) - self.default_count

    def maxArgumentCount(self):
        return len(self.argument_names)

    def checkCall(self, call_node, reporter, name):
        if self.decorated:
            return

        filledSlots = set()
        filledKwOnlySlots = set()
        for item, arg in enumerate(call_node.args):
            if item >= len(self.argument_names):
                if not self.has_var_arg:
                    return reporter.report(messages.TooManyArguments, call_node, name, self.maxArgumentCount())
                break
            filledSlots.add(item)

        for kw in call_node.keywords:
            slots = None
            try:
                argIndex = self.argument_names.index(kw.arg)
                slots = filledSlots
            except ValueError:
                try:
                    argIndex = self.kw_only_argument_names.index(kw.arg)
                    slots = filledKwOnlySlots
                except ValueError:
                    if self.has_kw_arg:
                        continue
                    else:
                        return reporter.report(messages.UnexpectedArgument, call_node, name, kw.arg)
            if argIndex in slots:
                return reporter.report(messages.MultipleValuesForArgument, call_node, name, kw.arg)
            slots.add(argIndex)

        filledSlots.update(range(len(self.argument_names) - self.default_count, len(self.argument_names)))
        filledKwOnlySlots.update(range(len(self.kw_only_argument_names) - self.kw_only_default_count,
                                       len(self.kw_only_argument_names)))

        if (len(filledSlots) < len(self.argument_names) and not call_node.starargs and not call_node.kwargs):
            return reporter.report(messages.TooFewArguments, call_node, name, self.min_argument_count())
        if (len(filledKwOnlySlots) < len(self.kw_only_argument_names) and not call_node.kwargs):
            missing_arguments = [repr(arg) for i, arg in enumerate(self.kw_only_argument_names)
                                if i not in filledKwOnlySlots]
            return reporter.report(messages.NeedKwOnlyArgument, call_node, name, ', '.join(missing_arguments))


class Checker(object):
    """The core of frosted, checks the cleanliness and sanity of Python code."""

    node_depth = 0
    offset = None
    trace_tree = False
    frosted_builtins = FROSTED_BUILTINS

    def __init__(self, tree, filename='(none)', builtins=None, ignore_lines=(), **settings):
        self.settings = settings
        self.ignore_errors = settings.get('ignore_frosted_errors', [])
        self.ignore_lines = ignore_lines
        file_specifc_ignores = settings.get('ignore_frosted_errors_for_' + (os.path.basename(filename) or ""), None)
        if file_specifc_ignores:
            self.ignore_errors += file_specifc_ignores

        self._node_handlers = {}
        self._deferred_functions = []
        self._deferred_assignments = []
        self.dead_scopes = []
        self.messages = []
        self.filename = filename
        if builtins:
            self.frosted_builtins = self.frosted_builtins.union(builtins)
        self.scope_stack = [ModuleScope()]
        self.except_handlers = [()]
        self.futures_allowed = True
        self.root = tree
        self.handle_children(tree)
        self.run_deferred(self._deferred_functions)
        self._deferred_functions = None
        self.run_deferred(self._deferred_assignments)
        self._deferred_assignments = None
        del self.scope_stack[1:]
        self.pop_scope()
        self.check_dead_scopes()

    def defer_function(self, callable):
        """Schedule a function handler to be called just before completion.

        This is used for handling function bodies, which must be deferred because code later in the file might modify
        the global scope. When 'callable' is called, the scope at the time this is called will be restored, however it
        will contain any new bindings added to it.

        """
        self._deferred_functions.append((callable, self.scope_stack[:], self.offset))

    def defer_assignment(self, callable):
        """Schedule an assignment handler to be called just after deferred
        function handlers."""
        self._deferred_assignments.append((callable, self.scope_stack[:], self.offset))

    def run_deferred(self, deferred):
        """Run the callables in deferred using their associated scope stack."""
        for handler, scope, offset in deferred:
            self.scope_stack = scope
            self.offset = offset
            handler()

    @property
    def scope(self):
        return self.scope_stack[-1]

    def pop_scope(self):
        self.dead_scopes.append(self.scope_stack.pop())

    def check_dead_scopes(self):
        """Look at scopes which have been fully examined and report names in
        them which were imported but unused."""
        for scope in self.dead_scopes:
            export = isinstance(scope.get('__all__'), ExportBinding)
            if export:
                all = scope['__all__'].names()
                # Look for possible mistakes in the export list
                if not scope.importStarred and os.path.basename(self.filename) != '__init__.py':
                    undefined = set(all) - set(scope)
                    for name in undefined:
                        self.report(messages.UndefinedExport, scope['__all__'].source, name)
            else:
                all = []

            # Look for imported names that aren't used without checking imports in namespace definition
            for importation in scope.values():
                if isinstance(importation, Importation) and not importation.used and importation.name not in all:
                    self.report(messages.UnusedImport, importation.source, importation.name)

    def push_scope(self, scope_class=FunctionScope):
        self.scope_stack.append(scope_class())

    def push_function_scope(self):    # XXX Deprecated
        self.push_scope(FunctionScope)

    def push_class_scope(self):       # XXX Deprecated
        self.push_scope(ClassScope)

    def report(self, message_class, *args, **kwargs):
        error_code = message_class.error_code

        if(not error_code[:2] + "00" in self.ignore_errors and not error_code in self.ignore_errors and not
           str(message_class.error_number) in self.ignore_errors):
            kwargs['verbose'] = self.settings.get('verbose')
            message = message_class(self.filename, *args, **kwargs)
            if message.lineno not in self.ignore_lines:
                self.messages.append(message)

    def has_parent(self, node, kind):
        while hasattr(node, 'parent'):
            node = node.parent
            if isinstance(node, kind):
                return True

    def get_common_ancestor(self, lnode, rnode, stop=None):
        stop = stop or self.root
        if lnode is rnode:
            return lnode
        if stop in (lnode, rnode):
            return stop

        if not hasattr(lnode, 'parent') or not hasattr(rnode, 'parent'):
            return
        if (lnode.level > rnode.level):
            return self.get_common_ancestor(lnode.parent, rnode, stop)
        if (rnode.level > lnode.level):
            return self.get_common_ancestor(lnode, rnode.parent, stop)
        return self.get_common_ancestor(lnode.parent, rnode.parent, stop)

    def descendant_of(self, node, ancestors, stop=None):
        for ancestor in ancestors:
            if self.get_common_ancestor(node, ancestor, stop) not in (stop, None):
                return True
        return False

    def on_fork(self, parent, lnode, rnode, items):
        return (self.descendant_of(lnode, items, parent) ^ self.descendant_of(rnode, items, parent))

    def different_forks(self, lnode, rnode):
        """True, if lnode and rnode are located on different forks of
        IF/TRY."""
        ancestor = self.get_common_ancestor(lnode, rnode)
        if isinstance(ancestor, ast.If):
            for fork in (ancestor.body, ancestor.orelse):
                if self.on_fork(ancestor, lnode, rnode, fork):
                    return True
        elif isinstance(ancestor, ast.Try):
            body = ancestor.body + ancestor.orelse
            for fork in [body] + [[hdl] for hdl in ancestor.handlers]:
                if self.on_fork(ancestor, lnode, rnode, fork):
                    return True
        elif isinstance(ancestor, ast.TryFinally):
            if self.on_fork(ancestor, lnode, rnode, ancestor.body):
                return True
        return False

    def add_binding(self, node, value, report_redef=True):
        """Called when a binding is altered.

        - `node` is the statement responsible for the change
        - `value` is the optional new value, a Binding instance, associated
        with the binding; if None, the binding is deleted if it exists.
        - if `report_redef` is True (default), rebinding while unused will be
        reported.

        """
        redefinedWhileUnused = False
        if not isinstance(self.scope, ClassScope):
            for scope in self.scope_stack[::-1]:
                existing = scope.get(value.name)
                if (isinstance(existing, Importation)
                        and not existing.used
                        and (not isinstance(value, Importation) or
                             value.fullName == existing.fullName)
                        and report_redef
                        and not self.different_forks(node, existing.source)):
                    redefinedWhileUnused = True
                    self.report(messages.RedefinedWhileUnused,
                                node, value.name, existing.source)

        existing = self.scope.get(value.name)
        if not redefinedWhileUnused and self.has_parent(value.source, ast.ListComp):
            if (existing and report_redef
                    and not self.has_parent(existing.source, (ast.For, ast.ListComp))
                    and not self.different_forks(node, existing.source)):
                self.report(messages.RedefinedInListComp,
                            node, value.name, existing.source)

        if (isinstance(existing, Definition)
                and not existing.used
                and not self.different_forks(node, existing.source)):
            self.report(messages.RedefinedWhileUnused,
                        node, value.name, existing.source)
        else:
            self.scope[value.name] = value

    def get_node_handler(self, node_class):
        try:
            return self._node_handlers[node_class]
        except KeyError:
            nodeType = str(node_class.__name__).upper()
        self._node_handlers[node_class] = handler = getattr(self, nodeType)
        return handler

    def iter_visible_scopes(self):
        outerScopes = itertools.islice(self.scope_stack, len(self.scope_stack) - 1)
        scopes = [scope for scope in outerScopes
                  if isinstance(scope, (FunctionScope, ModuleScope))]
        if (isinstance(self.scope, GeneratorScope)
            and scopes[-1] != self.scope_stack[-2]):
            scopes.append(self.scope_stack[-2])
        scopes.append(self.scope_stack[-1])
        return iter(reversed(scopes))

    def handle_node_load(self, node):
        name = node_name(node)
        if not name:
            return

        importStarred = False
        for scope in self.iter_visible_scopes():
            importStarred = importStarred or scope.importStarred
            try:
                scope[name].used = (self.scope, node)
            except KeyError:
                pass
            else:
                return

        # look in the built-ins
        if importStarred or name in self.frosted_builtins:
            return
        if name == '__path__' and os.path.basename(self.filename) == '__init__.py':
            # the special name __path__ is valid only in packages
            return

        # protected with a NameError handler?
        if 'NameError' not in self.except_handlers[-1]:
            self.report(messages.UndefinedName, node, name)

    def handle_node_store(self, node):
        name = node_name(node)
        if not name:
            return
        # if the name hasn't already been defined in the current scope
        if isinstance(self.scope, FunctionScope) and name not in self.scope:
            # for each function or module scope above us
            for scope in self.scope_stack[:-1]:
                if not isinstance(scope, (FunctionScope, ModuleScope)):
                    continue
                # if the name was defined in that scope, and the name has
                # been accessed already in the current scope, and hasn't
                # been declared global
                used = name in scope and scope[name].used
                if used and used[0] is self.scope and name not in self.scope.globals:
                    # then it's probably a mistake
                    self.report(messages.UndefinedLocal,
                                scope[name].used[1], name, scope[name].source)
                    break

        parent = getattr(node, 'parent', None)
        if isinstance(parent, (ast.For, ast.comprehension, ast.Tuple, ast.List)):
            binding = Binding(name, node)
        elif (parent is not None and name == '__all__' and
              isinstance(self.scope, ModuleScope)):
            binding = ExportBinding(name, parent.value)
        else:
            binding = Assignment(name, node)
        if name in self.scope:
            binding.used = self.scope[name].used
        self.add_binding(node, binding)

    def handle_node_delete(self, node):
        name = node_name(node)
        if not name:
            return
        if isinstance(self.scope, FunctionScope) and name in self.scope.globals:
            self.scope.globals.remove(name)
        else:
            try:
                del self.scope[name]
            except KeyError:
                self.report(messages.UndefinedName, node, name)

    def handle_children(self, tree):
        for node in ast.iter_child_nodes(tree):
            self.handleNode(node, tree)

    def is_docstring(self, node):
        """Determine if the given node is a docstring, as long as it is at the
        correct place in the node tree."""
        return isinstance(node, ast.Str) or (isinstance(node, ast.Expr) and
                                             isinstance(node.value, ast.Str))

    def docstring(self, node):
        if isinstance(node, ast.Expr):
            node = node.value
        if not isinstance(node, ast.Str):
            return (None, None)
        # Computed incorrectly if the docstring has backslash
        doctest_lineno = node.lineno - node.s.count('\n') - 1
        return (node.s, doctest_lineno)

    def handleNode(self, node, parent):
        if node is None:
            return
        if self.offset and getattr(node, 'lineno', None) is not None:
            node.lineno += self.offset[0]
            node.col_offset += self.offset[1]
        if self.trace_tree:
            print('  ' * self.node_depth + node.__class__.__name__)
        if self.futures_allowed and not (isinstance(node, ast.ImportFrom) or
                                        self.is_docstring(node)):
            self.futures_allowed = False
        self.node_depth += 1
        node.level = self.node_depth
        node.parent = parent
        try:
            handler = self.get_node_handler(node.__class__)
            handler(node)
        finally:
            self.node_depth -= 1
        if self.trace_tree:
            print('  ' * self.node_depth + 'end ' + node.__class__.__name__)

    _get_doctest_examples = doctest.DocTestParser().get_examples

    def handle_doctests(self, node):
        try:
            docstring, node_lineno = self.docstring(node.body[0])
            if not docstring:
                return
            examples = self._get_doctest_examples(docstring)
        except (ValueError, IndexError):
            # e.g. line 6 of the docstring for <string> has inconsistent
            # leading whitespace: ...
            return
        node_offset = self.offset or (0, 0)
        self.push_scope()
        for example in examples:
            try:
                tree = compile(example.source, "<doctest>", "exec", ast.PyCF_ONLY_AST)
            except SyntaxError:
                e = sys.exc_info()[1]
                position = (node_lineno + example.lineno + e.lineno,
                            example.indent + 4 + (e.offset or 0))
                self.report(messages.DoctestSyntaxError, node, position)
            else:
                self.offset = (node_offset[0] + node_lineno + example.lineno,
                               node_offset[1] + example.indent + 4)
                self.handle_children(tree)
                self.offset = node_offset
        self.pop_scope()

    def find_return_with_argument(self, node):
        """Finds and returns a return statment that has an argument.

        Note that we should use node.returns in Python 3, but this method is never called in Python 3 so we don't bother
        checking.

        """
        for item in node.body:
            if isinstance(item, ast.Return) and item.value:
                return item
            elif not isinstance(item, ast.FunctionDef) and hasattr(item, 'body'):
                return_with_argument = self.find_return_with_argument(item)
                if return_with_argument:
                    return return_with_argument

    def is_generator(self, node):
        """Checks whether a function is a generator by looking for a yield
        statement or expression."""
        if not isinstance(node.body, list):
            # lambdas can not be generators
            return False
        for item in node.body:
            if isinstance(item, (ast.Assign, ast.Expr)):
                if isinstance(item.value, ast.Yield):
                    return True
            elif not isinstance(item, ast.FunctionDef) and hasattr(item, 'body'):
                if self.is_generator(item):
                    return True
        return False

    def ignore(self, node):
        pass

    # "stmt" type nodes
    RETURN = DELETE = PRINT = WHILE = IF = WITH = WITHITEM = RAISE = TRYFINALLY = ASSERT = EXEC = EXPR = handle_children

    CONTINUE = BREAK = PASS = ignore

    # "expr" type nodes
    BOOLOP = BINOP = UNARYOP = IFEXP = DICT = SET = YIELD = YIELDFROM = COMPARE = REPR = ATTRIBUTE = SUBSCRIPT = \
             LIST = TUPLE = STARRED = NAMECONSTANT = handle_children

    NUM = STR = BYTES = ELLIPSIS = ignore

    # "slice" type nodes
    SLICE = EXTSLICE = INDEX = handle_children

    # expression contexts are node instances too, though being constants
    LOAD = STORE = DEL = AUGLOAD = AUGSTORE = PARAM = ignore

    # same for operators
    AND = OR = ADD = SUB = MULT = DIV = MOD = POW = LSHIFT = RSHIFT = BITOR = BITXOR = BITAND = FLOORDIV = INVERT = \
          NOT = UADD = USUB = EQ = NOTEQ = LT = LTE = GT = GTE = IS = ISNOT = IN = NOTIN = ignore

    # additional node types
    COMPREHENSION = KEYWORD = handle_children

    def GLOBAL(self, node):
        """Keep track of globals declarations."""
        if isinstance(self.scope, FunctionScope):
            self.scope.globals.update(node.names)

    NONLOCAL = GLOBAL

    def LISTCOMP(self, node):
        # handle generators before element
        for gen in node.generators:
            self.handleNode(gen, node)
        self.handleNode(node.elt, node)

    def GENERATOREXP(self, node):
        self.push_scope(GeneratorScope)
        # handle generators before element
        for gen in node.generators:
            self.handleNode(gen, node)
        self.handleNode(node.elt, node)
        self.pop_scope()

    SETCOMP = GENERATOREXP

    def DICTCOMP(self, node):
        self.push_scope(GeneratorScope)
        for gen in node.generators:
            self.handleNode(gen, node)
        self.handleNode(node.key, node)
        self.handleNode(node.value, node)
        self.pop_scope()

    def FOR(self, node):
        """Process bindings for loop variables."""
        vars = []

        def collectLoopVars(n):
            if isinstance(n, ast.Name):
                vars.append(n.id)
            elif isinstance(n, ast.expr_context):
                return
            else:
                for c in ast.iter_child_nodes(n):
                    collectLoopVars(c)

        collectLoopVars(node.target)
        for varn in vars:
            if (isinstance(self.scope.get(varn), Importation)
                    # unused ones will get an unused import warning
                    and self.scope[varn].used):
                self.report(messages.ImportShadowedByLoopVar,
                            node, varn, self.scope[varn].source)

        self.handle_children(node)

    def NAME(self, node):
        """Handle occurrence of Name (which can be a load/store/delete
        access.)"""
        # Locate the name in locals / function / globals scopes.
        if isinstance(node.ctx, (ast.Load, ast.AugLoad)):
            self.handle_node_load(node)
            if (node.id == 'locals' and isinstance(self.scope, FunctionScope)
                    and isinstance(node.parent, ast.Call)):
                # we are doing locals() call in current scope
                self.scope.uses_locals = True
        elif isinstance(node.ctx, (ast.Store, ast.AugStore)):
            self.handle_node_store(node)
        elif isinstance(node.ctx, ast.Del):
            self.handle_node_delete(node)
        else:
            # must be a Param context -- this only happens for names in function
            # arguments, but these aren't dispatched through here
            raise RuntimeError("Got impossible expression context: %r" % (node.ctx,))

    def CALL(self, node):
        f = node.func
        if isinstance(f, ast.Name):
            for scope in self.iter_visible_scopes():
                definition = scope.get(f.id)
                if definition:
                    if isinstance(definition, FunctionDefinition):
                        definition.signature.checkCall(node, self, f.id)
                    break


        self.handle_children(node)

    def FUNCTIONDEF(self, node):
        for deco in node.decorator_list:
            self.handleNode(deco, node)
        self.add_binding(node, FunctionDefinition(node.name, node))
        self.LAMBDA(node)
        if self.settings.get('run_doctests', False):
            self.defer_function(lambda: self.handle_doctests(node))

    def LAMBDA(self, node):
        args = []
        annotations = []

        if PY2:
            def addArgs(arglist):
                for arg in arglist:
                    if isinstance(arg, ast.Tuple):
                        addArgs(arg.elts)
                    else:
                        if arg.id in args:
                            self.report(messages.DuplicateArgument,
                                        node, arg.id)
                        args.append(arg.id)
            addArgs(node.args.args)
            defaults = node.args.defaults
        else:
            for arg in node.args.args + node.args.kwonlyargs:
                annotations.append(arg.annotation)
                args.append(arg.arg)
            defaults = node.args.defaults + node.args.kw_defaults

        # Only for Python3 FunctionDefs
        is_py3_func = hasattr(node, 'returns')

        for arg_name in ('vararg', 'kwarg'):
            wildcard = getattr(node.args, arg_name)
            if not wildcard:
                continue
            args.append(getattr(wildcard, 'arg', wildcard))
            if is_py3_func:
                if PY34_GTE:
                    annotations.append(wildcard.annotation)
                else:
                    argannotation = arg_name + 'annotation'
                    annotations.append(getattr(node.args, argannotation))
        if is_py3_func:
            annotations.append(node.returns)

        if PY3:
            if len(set(args)) < len(args):
                for (idx, arg) in enumerate(args):
                    if arg in args[:idx]:
                        self.report(messages.DuplicateArgument, node, arg)

        for child in annotations + defaults:
            if child:
                self.handleNode(child, node)

        def runFunction():

            self.push_scope()
            for name in args:
                self.add_binding(node, Argument(name, node), report_redef=False)
            if isinstance(node.body, list):
                # case for FunctionDefs
                for stmt in node.body:
                    self.handleNode(stmt, node)
            else:
                # case for Lambdas
                self.handleNode(node.body, node)

            def checkUnusedAssignments():
                """Check to see if any assignments have not been used."""
                for name, binding in self.scope.unusedAssignments():
                    self.report(messages.UnusedVariable, binding.source, name)
            self.defer_assignment(checkUnusedAssignments)

            if PY2:
                def checkReturnWithArgumentInsideGenerator():
                    """Check to see if there are any return statements with
                    arguments but the function is a generator."""
                    if self.is_generator(node):
                        stmt = self.find_return_with_argument(node)
                        if stmt is not None:
                            self.report(messages.ReturnWithArgsInsideGenerator, stmt)
                self.defer_assignment(checkReturnWithArgumentInsideGenerator)
            self.pop_scope()

        self.defer_function(runFunction)

    def CLASSDEF(self, node):
        """Check names used in a class definition, including its decorators,
        base classes, and the body of its definition.

        Additionally, add its name to the current scope.

        """
        for deco in node.decorator_list:
            self.handleNode(deco, node)
        for baseNode in node.bases:
            self.handleNode(baseNode, node)
        if not PY2:
            for keywordNode in node.keywords:
                self.handleNode(keywordNode, node)
        self.push_scope(ClassScope)
        if self.settings.get('run_doctests', False):
            self.defer_function(lambda: self.handle_doctests(node))
        for stmt in node.body:
            self.handleNode(stmt, node)
        self.pop_scope()
        self.add_binding(node, ClassDefinition(node.name, node))

    def ASSIGN(self, node):
        self.handleNode(node.value, node)
        for target in node.targets:
            self.handleNode(target, node)

    def AUGASSIGN(self, node):
        self.handle_node_load(node.target)
        self.handleNode(node.value, node)
        self.handleNode(node.target, node)

    def IMPORT(self, node):
        for alias in node.names:
            name = alias.asname or alias.name
            importation = Importation(name, node)
            self.add_binding(node, importation)

    def IMPORTFROM(self, node):
        if node.module == '__future__':
            if not self.futures_allowed:
                self.report(messages.LateFutureImport,
                            node, [n.name for n in node.names])
        else:
            self.futures_allowed = False

        for alias in node.names:
            if alias.name == '*':
                self.scope.importStarred = True
                self.report(messages.ImportStarUsed, node, node.module)
                continue
            name = alias.asname or alias.name
            importation = Importation(name, node)
            if node.module == '__future__':
                importation.used = (self.scope, node)
            self.add_binding(node, importation)

    def TRY(self, node):
        handler_names = []
        # List the exception handlers
        for handler in node.handlers:
            if isinstance(handler.type, ast.Tuple):
                for exc_type in handler.type.elts:
                    handler_names.append(node_name(exc_type))
            elif handler.type:
                handler_names.append(node_name(handler.type))
        # Memorize the except handlers and process the body
        self.except_handlers.append(handler_names)
        for child in node.body:
            self.handleNode(child, node)
        self.except_handlers.pop()
        # Process the other nodes: "except:", "else:", "finally:"
        for child in ast.iter_child_nodes(node):
            if child not in node.body:
                self.handleNode(child, node)

    TRYEXCEPT = TRY

    def EXCEPTHANDLER(self, node):
        # 3.x: in addition to handling children, we must handle the name of
        # the exception, which is not a Name node, but a simple string.
        if node.type is None:
            self.report(messages.BareExcept, node)
        if isinstance(node.name, str):
            self.handle_node_store(node)
        self.handle_children(node)

########NEW FILE########
__FILENAME__ = main
#!/usr/bin/env python
""" Implementation of the command-line frosted tool.

"""
from __future__ import absolute_import, division, print_function, unicode_literals

import argparse
import sys

from pies.overrides import *

from frosted import __version__
from frosted.api import check, check_path, check_recursive


def main():
    warnings = 0

    parser = argparse.ArgumentParser(description='Quickly check the correctness of your Python scripts.')
    parser.add_argument('files', nargs='+', help='One file or a list of Python source files to check the syntax of.')
    parser.add_argument('-r', '--recursive', dest='recursive', action='store_true',
                        help='Recursively look for Python files to check')
    parser.add_argument('-s', '--skip', help='Files that frosted should skip over.', dest='skip', action='append')
    parser.add_argument('-d', '--with-doctests', help='Run frosted against doctests', dest='run_doctests',
                        action='store_true')
    parser.add_argument('-i', '--ignore', help='Specify error codes that should be ignored.',
                        dest='ignore_frosted_errors', action='append')
    parser.add_argument('-di', '--dont-ignore', help='Specify error codes that should not be ignored in any case.',
                        dest='not_ignore_frosted_errors', action='append')
    parser.add_argument('-vb', '--verbose', help='Explicitly separate each section of data when displaying errors.',
                        dest='verbose', action='store_true')
    parser.add_argument('-v', '--version', action='version', version='frosted {0}'.format(__version__))
    arguments = dict((key, value) for (key, value) in itemsview(vars(parser.parse_args())) if value)
    file_names = arguments.pop('files', [])
    if file_names == ['-']:
        check(sys.stdin.read(), '<stdin>', **arguments)
    elif arguments.get('recursive'):
        warnings = check_recursive(file_names, **arguments)
    else:
        warnings = 0
        for file_path in file_names:
            try:
                warnings += check_path(file_path, directly_being_checked=len(file_names), **arguments)
            except IOError as e:
                print("WARNING: Unable to parse file {0} due to {1}".format(file_name, e))

    raise SystemExit(warnings > 0)


if __name__ == "__main__":
    main()

########NEW FILE########
__FILENAME__ = messages
"""frosted/reporter.py.

Defines the error messages that frosted can output

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or
substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED
TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR

"""

from __future__ import absolute_import, division, print_function, unicode_literals

import re
from collections import namedtuple

from pies.overrides import *

BY_CODE = {}
_ERROR_INDEX = 100

AbstractMessageType = namedtuple('AbstractMessageType', ('error_code', 'name', 'template',
                                                         'keyword', 'error_number'))


class MessageType(AbstractMessageType):

    class Message(namedtuple('Message', ('message', 'type', 'lineno', 'col'))):

        def __str__(self):
            return self.message

    def __new__(cls, error_code, name, template, keyword='{0!s}'):
        global _ERROR_INDEX
        new_instance = AbstractMessageType.__new__(cls, error_code, name, template,
                                                   keyword, _ERROR_INDEX)
        _ERROR_INDEX += 1
        BY_CODE[error_code] = new_instance
        return new_instance

    def __call__(self, filename, loc=None, *kargs, **kwargs):
        values = {'filename': filename, 'lineno': 0, 'col': 0}
        if loc:
            values['lineno'] = loc.lineno
            values['col'] = getattr(loc, 'col_offset', 0)
        values.update(kwargs)

        message = self.template.format(*kargs, **values)
        if kwargs.get('verbose', False):
            keyword = self.keyword.format(*kargs, **values)
            return self.Message('{0}:{1}:{2}:{3}:{4}:{5}'.format(filename, values['lineno'], values['col'],
                                                                 self.error_code, keyword, message),
                                self, values['lineno'], values['col'])
        return self.Message('{0}:{1}: {2}'.format(filename, values['lineno'], message),
                            self, values['lineno'], values['col'])



class OffsetMessageType(MessageType):
    def __call__(self, filename, loc, position=None, *kargs, **kwargs):
        if position:
            kwargs.update({'lineno': position[0], 'col': position[1]})
        return MessageType.__call__(self, filename, loc, *kargs, **kwargs)


class SyntaxErrorType(MessageType):
    def __call__(self, filename, msg, lineno, offset, text, *kargs, **kwargs):
        kwargs['lineno'] = lineno
        line = text.splitlines()[-1]
        msg += "\n" + str(line)
        if offset is not None:
            offset = offset - (len(text) - len(line))
            kwargs['col'] = offset
            msg += "\n" + re.sub(r'\S',' ', line[:offset]) + "^"

        return MessageType.__call__(self, filename, None, msg, *kargs, **kwargs)


Message = MessageType('I101', 'Generic', '{0}', '')
UnusedImport = MessageType('E101', 'UnusedImport', '{0} imported but unused')
RedefinedWhileUnused = MessageType('E301', 'RedefinedWhileUnused',
                                   'redefinition of {0!r} from line {1.lineno!r}')
RedefinedInListComp = MessageType('E302', 'RedefinedInListComp',
                                  'list comprehension redefines {0!r} from line {1.lineno!r}')
ImportShadowedByLoopVar = MessageType('E102', 'ImportShadowedByLoopVar',
                                      'import {0!r} from line {1.lineno!r} shadowed by loop variable')
ImportStarUsed = MessageType('E103', 'ImportStarUsed',
                             "'from {0!s} import *' used; unable to detect undefined names", '*')
UndefinedName = MessageType('E303', 'UndefinedName', "undefined name {0!r}")
DoctestSyntaxError = OffsetMessageType('E401', 'DoctestSyntaxError', "syntax error in doctest", '')
UndefinedExport = MessageType('E304', 'UndefinedExport', "undefined name {0!r} in __all__")
UndefinedLocal = MessageType('E305', 'UndefinedLocal',
                  'local variable {0!r} (defined in enclosing scope on line {1.lineno!r}) referenced before assignment')
DuplicateArgument = MessageType('E206', 'DuplicateArgument', "duplicate argument {0!r} in function definition")
Redefined = MessageType('E306', 'Redefined', "redefinition of {0!r} from line {1.lineno!r}")
LateFutureImport = MessageType('E207', 'LateFutureImport', "future import(s) {0!r} after other statements")
UnusedVariable = MessageType('E307', 'UnusedVariable', "local variable {0!r} is assigned to but never used")
MultipleValuesForArgument = MessageType('E201', 'MultipleValuesForArgument',
                                        "{0!s}() got multiple values for argument {1!r}")
TooFewArguments = MessageType('E202', 'TooFewArguments', "{0!s}() takes at least {1:d} argument(s)")
TooManyArguments = MessageType('E203', 'TooManyArguments', "{0!s}() takes at most {1:d} argument(s)")
UnexpectedArgument = MessageType('E204', 'UnexpectedArgument', "{0!s}() got unexpected keyword argument: {1!r}")
NeedKwOnlyArgument = MessageType('E205', 'NeedKwOnlyArgument', "{0!s}() needs kw-only argument(s): {1!s}")
ReturnWithArgsInsideGenerator = MessageType('E208', 'ReturnWithArgsInsideGenerator',
                                            "'return' with argument inside generator", 'return')
BareExcept = MessageType('W101', 'BareExcept', "bare except used: this is dangerous and should be avoided", 'except')
FileSkipped = MessageType('W201', 'FileSkipped', "Skipped because of the current configuration", 'skipped')
PythonSyntaxError = SyntaxErrorType('E402', 'PythonSyntaxError', "{0!s}", "")

########NEW FILE########
__FILENAME__ = reporter
"""frosted/reporter.py.

Defines how errors found by frosted should be displayed to the user

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or
substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED
TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR

"""
from __future__ import absolute_import, division, print_function, unicode_literals

import sys
from collections import namedtuple

from pies.overrides import *


class Reporter(namedtuple('Reporter', ('stdout', 'stderr'))):
    """Formats the results of frosted checks and then presents them to the user."""

    def unexpected_error(self, filename, msg):
        """Output an unexpected_error specific to the provided filename."""
        self.stderr.write("%s: %s\n" % (filename, msg))

    def flake(self, message):
        """Print an error message to stdout."""
        self.stdout.write(str(message))
        self.stdout.write('\n')

Default = Reporter(sys.stdout, sys.stderr)

########NEW FILE########
__FILENAME__ = settings
"""frosted/settings.py.

Defines how the default settings for frosted should be loaded

(First from the default setting dictionary at the top of the file, then overridden by any settings
 in ~/.frosted.conf if there are any)

Copyright (C) 2013  Timothy Edmund Crosley

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or
substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED
TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

"""
from __future__ import absolute_import, division, print_function, unicode_literals

import os

from pies.functools import lru_cache
from pies.overrides import *

try:
    import configparser
except ImportError:
    import ConfigParser as configparser

MAX_CONFIG_SEARCH_DEPTH = 25 # The number of parent directories frosted will look for a config file within

# Note that none of these lists must be complete as they are simply fallbacks for when included auto-detection fails.
default = {'skip': [],
           'ignore_frosted_errors': ['W201'],
           'ignore_frosted_errors_for__init__.py': ['E101', 'E103'],
           'verbose': False,
           'run_doctests': False}


@lru_cache()
def from_path(path):
    computed_settings = default.copy()
    _update_settings_with_config(path, '.editorconfig', '~/.editorconfig', ('*', '*.py', '**.py'), computed_settings)
    _update_settings_with_config(path, '.frosted.cfg', '~/.frosted.cfg', ('settings', ), computed_settings)
    _update_settings_with_config(path, 'setup.cfg', None, ('frosted', ), computed_settings)
    return computed_settings


def _update_settings_with_config(path, name, default, sections, computed_settings):
    editor_config_file = default and os.path.expanduser(default)
    tries = 0
    current_directory = path
    while current_directory and tries < MAX_CONFIG_SEARCH_DEPTH:
        potential_path = os.path.join(current_directory, native_str(name))
        if os.path.exists(potential_path):
            editor_config_file = potential_path
            break

        current_directory = os.path.split(current_directory)[0]
        tries += 1

    if editor_config_file and os.path.exists(editor_config_file):
        _update_with_config_file(computed_settings, editor_config_file, sections)


def _update_with_config_file(computed_settings, file_path, sections):
    settings = _get_config_data(file_path, sections)
    if not settings:
        return

    for key, value in settings.items():
        access_key = key.replace('not_', '').lower()
        if key.startswith('ignore_frosted_errors_for'):
            existing_value_type = list
        else:
            existing_value_type = type(default.get(access_key, ''))
        if existing_value_type in (list, tuple):
            existing_data = set(computed_settings.get(access_key, default.get(access_key)) or ())
            if key.startswith('not_'):
                computed_settings[access_key] = list(existing_data.difference(value.split(",")))
            else:
                computed_settings[access_key] = list(existing_data.union(value.split(",")))
        elif existing_value_type == bool and value.lower().strip() == "false":
            computed_settings[access_key] = False
        else:
            computed_settings[access_key] = existing_value_type(value)


@lru_cache()
def _get_config_data(file_path, sections):
    with open(file_path) as config_file:
        if file_path.endswith(".editorconfig"):
            line = "\n"
            last_position = config_file.tell()
            while line:
                line = config_file.readline()
                if "[" in line:
                    config_file.seek(last_position)
                    break
                last_position = config_file.tell()

        config = configparser.SafeConfigParser()
        config.readfp(config_file)
        settings = dict()
        for section in sections:
            if config.has_section(section):
                settings.update(dict(config.items(section)))

        return settings

    return None

########NEW FILE########
__FILENAME__ = test_api
"""frosted/test/test_api.py.

Tests all major functionality of the Frosted API

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or
substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED
TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

"""
from __future__ import absolute_import, division, print_function, unicode_literals

import os
import sys
import tempfile
from io import StringIO

import pytest
from pies.overrides import *

from frosted.api import check_path, check_recursive
from frosted.messages import PythonSyntaxError, UnusedImport
from frosted.reporter import Reporter

from .utils import LoggingReporter, Node


def test_syntax_error():
    """syntax_error reports that there was a syntax error in the source file.

    It reports to the error stream and includes the filename, line number, error message, actual line of source and a
    caret pointing to where the error is

    """
    err = StringIO()
    reporter = Reporter(err, err)
    reporter.flake(PythonSyntaxError('foo.py', 'a problem', 3, 7, 'bad line of source', verbose=True))
    assert ("foo.py:3:7:E402::a problem\n"
            "bad line of source\n"
            "       ^\n") == err.getvalue()


def test_syntax_errorNoOffset():
    """syntax_error doesn't include a caret pointing to the error if offset is passed as None."""
    err = StringIO()
    reporter = Reporter(err, err)
    reporter.flake(PythonSyntaxError('foo.py', 'a problem', 3, None, 'bad line of source', verbose=True))
    assert ("foo.py:3:0:E402::a problem\n"
            "bad line of source\n") == err.getvalue()


def test_multiLineSyntaxError():
    """ If there's a multi-line syntax error, then we only report the last line.

    The offset is adjusted so that it is relative to the start of the last line

    """
    err = StringIO()
    lines = ['bad line of source', 'more bad lines of source']
    reporter = Reporter(err, err)
    reporter.flake(PythonSyntaxError('foo.py', 'a problem', 3, len(lines[0]) + 7, '\n'.join(lines), verbose=True))
    assert ("foo.py:3:6:E402::a problem\n" +
            lines[-1] + "\n" +
            "      ^\n") == err.getvalue()


def test_unexpected_error():
    """unexpected_error reports an error processing a source file."""
    err = StringIO()
    reporter = Reporter(None, err)
    reporter.unexpected_error('source.py', 'error message')
    assert 'source.py: error message\n' == err.getvalue()


def test_flake():
    """flake reports a code warning from Frosted.

    It is exactly the str() of a frosted.messages.Message

    """
    out = StringIO()
    reporter = Reporter(out, None)
    message = UnusedImport('foo.py', Node(42), 'bar')
    reporter.flake(message)
    assert out.getvalue() == "%s\n" % (message,)


def make_temp_file(content):
    """Make a temporary file containing C{content} and return a path to it."""
    _, fpath = tempfile.mkstemp()
    if not hasattr(content, 'decode'):
        content = content.encode('ascii')
    fd = open(fpath, 'wb')
    fd.write(content)
    fd.close()
    return fpath


def assert_contains_output(path, flakeList):
    """Assert that provided causes at minimal the errors provided in the error list."""
    out = StringIO()
    count = check_path(path, Reporter(out, out), verbose=True)
    out_string = out.getvalue()
    assert len(flakeList) >= count
    for flake in flakeList:
        assert flake in out_string


def get_errors(path):
    """Get any warnings or errors reported by frosted for the file at path."""
    log = []
    reporter = LoggingReporter(log)
    count = check_path(path, reporter)
    return count, log


def test_missingTrailingNewline():
    """Source which doesn't end with a newline shouldn't cause any exception to

    be raised nor an error indicator to be returned by check.

    """
    fName = make_temp_file("def foo():\n\tpass\n\t")
    assert_contains_output(fName, [])


def test_check_pathNonExisting():
    """check_path handles non-existing files"""
    count, errors = get_errors('extremo')
    assert count == 1
    assert errors == [('unexpected_error', 'extremo', 'No such file or directory')]


def test_multilineSyntaxError():
    """Source which includes a syntax error which results in the raised SyntaxError.

    text containing multiple lines of source are reported with only
    the last line of that source.

    """
    source = """\
def foo():
    '''

def bar():
    pass

def baz():
    '''quux'''
"""
    # Sanity check - SyntaxError.text should be multiple lines, if it
    # isn't, something this test was unprepared for has happened.
    def evaluate(source):
        exec(source)
    try:
        evaluate(source)
    except SyntaxError:
        e = sys.exc_info()[1]
        assert e.text.count('\n') > 1
    else:
        assert False

    sourcePath = make_temp_file(source)
    assert_contains_output(
        sourcePath,
        ["""\
%s:8:10:E402::invalid syntax
    '''quux'''
          ^
""" % (sourcePath,)])


def test_eofSyntaxError():
    """The error reported for source files which end prematurely causing a
    syntax error reflects the cause for the syntax error.

    """
    sourcePath = make_temp_file("def foo(")
    assert_contains_output(sourcePath, ["""\
%s:1:8:E402::unexpected EOF while parsing
def foo(
        ^
""" % (sourcePath,)])


def test_nonDefaultFollowsDefaultSyntaxError():
    """ Source which has a non-default argument following a default argument

    should include the line number of the syntax error
    However these exceptions do not include an offset

    """
    source = """\
def foo(bar=baz, bax):
    pass
"""
    sourcePath = make_temp_file(source)
    last_line = '       ^\n' if sys.version_info >= (3, 2) else ''
    column = '7:' if sys.version_info >= (3, 2) else '0:'
    assert_contains_output(sourcePath, ["""\
%s:1:%sE402::non-default argument follows default argument
def foo(bar=baz, bax):
%s""" % (sourcePath, column, last_line)])


def test_nonKeywordAfterKeywordSyntaxError():
    """Source which has a non-keyword argument after a keyword argument

    should include the line number of the syntax error
    However these exceptions do not include an offset
    """
    source = """\
foo(bar=baz, bax)
"""
    sourcePath = make_temp_file(source)
    last_line = '            ^\n' if sys.version_info >= (3, 2) else ''
    column = '12:' if sys.version_info >= (3, 2) else '0:'
    assert_contains_output(
        sourcePath,
        ["""\
%s:1:%sE402::non-keyword arg after keyword arg
foo(bar=baz, bax)
%s""" % (sourcePath, column, last_line)])


def test_invalidEscape():
    """The invalid escape syntax raises ValueError in Python 2."""
    sourcePath = make_temp_file(r"foo = '\xyz'")
    if PY2:
        decoding_error = "%s: problem decoding source\n" % (sourcePath,)
    else:
        decoding_error = "(unicode error) 'unicodeescape' codec can't decode bytes"
    assert_contains_output(sourcePath, (decoding_error, ))


def test_permissionDenied():
    """If the source file is not readable, this is reported on standard error."""
    sourcePath = make_temp_file('')
    os.chmod(sourcePath, 0)
    count, errors = get_errors(sourcePath)
    assert count == 1
    assert errors == [('unexpected_error', sourcePath, "Permission denied")]


def test_frostedWarning():
    """If the source file has a frosted warning, this is reported as a 'flake'."""
    sourcePath = make_temp_file("import foo")
    count, errors = get_errors(sourcePath)
    assert count == 1
    assert errors == [('flake', str(UnusedImport(sourcePath, Node(1), 'foo')))]


@pytest.mark.skipif("PY3")
def test_misencodedFileUTF8():
    """If a source file contains bytes which cannot be decoded, this is reported on stderr."""
    SNOWMAN = chr(0x2603)
    source = ("""\
# coding: ascii
x = "%s"
""" % SNOWMAN).encode('utf-8')
    sourcePath = make_temp_file(source)
    assert_contains_output(sourcePath, ["%s: problem decoding source\n" % (sourcePath, )])


def test_misencodedFileUTF16():
    """If a source file contains bytes which cannot be decoded, this is reported on stderr."""
    SNOWMAN = chr(0x2603)
    source = ("""\
# coding: ascii
x = "%s"
""" % SNOWMAN).encode('utf-16')
    sourcePath = make_temp_file(source)
    assert_contains_output(sourcePath, ["%s: problem decoding source\n" % (sourcePath,)])


def test_check_recursive():
    """check_recursive descends into each directory, finding Python files and reporting problems."""
    tempdir = tempfile.mkdtemp()
    os.mkdir(os.path.join(tempdir, 'foo'))
    file1 = os.path.join(tempdir, 'foo', 'bar.py')
    fd = open(file1, 'wb')
    fd.write("import baz\n".encode('ascii'))
    fd.close()
    file2 = os.path.join(tempdir, 'baz.py')
    fd = open(file2, 'wb')
    fd.write("import contraband".encode('ascii'))
    fd.close()
    log = []
    reporter = LoggingReporter(log)
    warnings = check_recursive([tempdir], reporter)
    assert warnings == 2
    assert sorted(log) == sorted([('flake', str(UnusedImport(file1, Node(1), 'baz'))),
                                  ('flake', str(UnusedImport(file2, Node(1), 'contraband')))])

########NEW FILE########
__FILENAME__ = test_doctests
from __future__ import absolute_import, division, print_function, unicode_literals

import textwrap

import pytest
from pies.overrides import *

from frosted import messages as m

from .utils import flakes


def doctestify(input):
    lines = []
    for line in textwrap.dedent(input).splitlines():
        if line.strip() == '':
            pass
        elif (line.startswith(' ') or
                line.startswith('except:') or
                line.startswith('except ') or
                line.startswith('finally:') or
                line.startswith('else:') or
                line.startswith('elif ')):
            line = "... %s" % line
        else:
            line = ">>> %s" % line
        lines.append(line)
    doctestificator = textwrap.dedent('''\
                def doctest_something():
                    """
                        %s
                    """
                ''')
    return doctestificator % "\n       ".join(lines)


def test_doubleNestingReportsClosestName():
    """Lines in doctest are a bit different so we can't use the test from TestUndefinedNames."""
    exc = flakes('''
        def doctest_stuff():
            """
                >>> def a():
                ...     x = 1
                ...     def b():
                ...         x = 2 # line 7 in the file
                ...         def c():
                ...             x
                ...             x = 3
                ...             return x
                ...         return x
                ...     return x

            """
        ''', m.UndefinedLocal, run_doctests=True).messages[0]

    assert "local variable 'x'" in exc.message and 'line 7' in exc.message


def test_importBeforeDoctest():
    flakes("""
            import foo

            def doctest_stuff():
                '''
                    >>> foo
                '''
            """, run_doctests=True)


@pytest.mark.skipif("'todo'")
def test_importBeforeAndInDoctest():
    flakes('''
            import foo

            def doctest_stuff():
                """
                    >>> import foo
                    >>> foo
                """

            foo
            ''', m.Redefined, run_doctests=True)


def test_importInDoctestAndAfter():
    flakes('''
            def doctest_stuff():
                """
                    >>> import foo
                    >>> foo
                """

            import foo
            foo()
            ''', run_doctests=True)


def test_offsetInDoctests():
    exc = flakes('''

            def doctest_stuff():
                """
                    >>> x # line 5
                """

            ''', m.UndefinedName, run_doctests=True).messages[0]
    assert exc.lineno == 5
    assert exc.col == 12


def test_ignoreErrorsByDefault():
    flakes('''

            def doctest_stuff():
                """
                    >>> x # line 5
                """

            ''')

def test_offsetInLambdasInDoctests():
    exc = flakes('''

            def doctest_stuff():
                """
                    >>> lambda: x # line 5
                """

            ''', m.UndefinedName, run_doctests=True).messages[0]
    assert exc.lineno == 5
    assert exc.col == 20


def test_offsetAfterDoctests():
    exc = flakes('''

            def doctest_stuff():
                """
                    >>> x = 5
                """

            x

            ''', m.UndefinedName, run_doctests=True).messages[0]
    assert exc.lineno == 8
    assert exc.col == 0


def test_syntax_errorInDoctest():
    exceptions = flakes(
            '''
            def doctest_stuff():
                """
                    >>> from # line 4
                    >>> fortytwo = 42
                    >>> except Exception:
                """
            ''',
            m.DoctestSyntaxError,
            m.DoctestSyntaxError, run_doctests=True).messages
    exc = exceptions[0]
    assert exc.lineno == 4
    assert exc.col == 26
    exc = exceptions[1]
    assert exc.lineno == 6
    assert exc.col == 18


def test_indentationErrorInDoctest():
    exc = flakes('''
            def doctest_stuff():
                """
                    >>> if True:
                    ... pass
                """
            ''', m.DoctestSyntaxError, run_doctests=True).messages[0]
    assert exc.lineno == 5
    assert exc.col == 16


def test_offsetWithMultiLineArgs():
    (exc1, exc2) = flakes(
            '''
            def doctest_stuff(arg1,
                                arg2,
                                arg3):
                """
                    >>> assert
                    >>> this
                """
            ''',
        m.DoctestSyntaxError,
        m.UndefinedName, run_doctests=True).messages
    assert exc1.lineno == 6
    assert exc1.col == 19
    assert exc2.lineno == 7
    assert exc2.col == 12


def test_doctestCanReferToFunction():
    flakes("""
            def foo():
                '''
                    >>> foo
                '''
            """, run_doctests=True)


def test_doctestCanReferToClass():
    flakes("""
            class Foo():
                '''
                    >>> Foo
                '''
                def bar(self):
                    '''
                        >>> Foo
                    '''
            """, run_doctests=True)


def test_noOffsetSyntaxErrorInDoctest():
    exceptions = flakes('''
            def buildurl(base, *args, **kwargs):
                """
                >>> buildurl('/blah.php', ('a', '&'), ('b', '=')
                '/blah.php?a=%26&b=%3D'
                >>> buildurl('/blah.php', a='&', 'b'='=')
                '/blah.php?b=%3D&a=%26'
                """
                pass
            ''',
        m.DoctestSyntaxError,
        m.DoctestSyntaxError, run_doctests=True).messages
    exc = exceptions[0]
    assert exc.lineno == 4
    exc = exceptions[1]
    assert exc.lineno == 6

########NEW FILE########
__FILENAME__ = test_function_calls
#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function, unicode_literals

import sys

from pies.overrides import *

from frosted import messages as m

from .utils import flakes


def test_ok():
    flakes('''
    def foo(a):
        pass
    foo(5)
    ''')

    flakes('''
    def foo(a, b=2):
        pass
    foo(5, b=1)
    ''')


def test_noCheckDecorators():
    flakes('''
    def decorator(f):
        return f
    @decorator
    def foo():
        pass
    foo(42)
    ''')


def test_tooManyArguments():
    flakes('''
    def foo():
        pass
    foo(5)
    ''', m.TooManyArguments)
    flakes('''
    def foo(a, b):
        pass
    foo(5, 6, 7)
    ''', m.TooManyArguments)


def test_tooManyArgumentsVarargs():
    flakes('''
    def foo(a, *args):
        pass
    foo(1, 2, 3)
    ''')


def test_unexpectedArgument():
    flakes('''
    def foo(a):
        pass
    foo(1, b=3)
    ''', m.UnexpectedArgument)

    flakes('''
    def foo(a, *args):
        pass
    foo(1, b=3)
    ''', m.UnexpectedArgument)

    flakes('''
    def foo(a, **kwargs):
        pass
    foo(1, b=3)
    ''')


def test_multipleValuesForArgument():
    flakes('''
    def foo(a):
        pass
    foo(5, a=5)
    ''', m.MultipleValuesForArgument)


def test_tooFewArguments():
    flakes('''
    def foo(a):
        pass
    foo()
    ''', m.TooFewArguments)

    flakes('''
    def foo(a):
        pass
    foo(*[])
    ''')

    flakes('''
    def foo(a):
        pass
    foo(**{})
    ''')


def test_tooFewArgumentsVarArgs():
    flakes('''
    def foo(a, b, *args):
        pass
    foo(1)
    ''', m.TooFewArguments)


if PY3:
    def test_kwOnlyArguments():
        flakes('''
        def foo(a, *, b=0):
            pass
        foo(5, b=2)
        ''')

        flakes('''
        def foo(a, *, b=0):
            pass
        foo(5)
        ''')

        flakes('''
        def foo(a, *, b):
            pass
        foo(5, b=2)
        ''')

        flakes('''
        def foo(a, *, b):
            pass
        foo(5, **{})
        ''')

        flakes('''
        def foo(a, *, b):
            pass
        foo(1)
        ''', m.NeedKwOnlyArgument)

        flakes('''
        def foo(a, *args, b):
            pass
        foo(1, 2, 3, 4)
        ''', m.NeedKwOnlyArgument)
elif PY2:
    def test_compoundArguments():
        flakes('''
        def foo(a, (b, c)):
            pass
        foo(1, [])''')

        flakes('''
        def foo(a, (b, c)):
            pass
        foo(1, 2, 3)''', m.TooManyArguments)

        flakes('''
        def foo(a, (b, c)):
            pass
        foo(1)''', m.TooFewArguments)

        flakes('''
        def foo(a, (b, c)):
            pass
        foo(1, b=2, c=3)''', m.UnexpectedArgument)

########NEW FILE########
__FILENAME__ = test_imports

from __future__ import absolute_import, division, print_function, unicode_literals

from sys import version_info

import pytest
from pies.overrides import *

from frosted import messages as m

from .utils import flakes


def test_unusedImport():
    flakes('import fu, bar', m.UnusedImport, m.UnusedImport)
    flakes('from baz import fu, bar', m.UnusedImport, m.UnusedImport)


def test_aliasedImport():
    flakes('import fu as FU, bar as FU',
                m.RedefinedWhileUnused, m.UnusedImport)
    flakes('from moo import fu as FU, bar as FU',
                m.RedefinedWhileUnused, m.UnusedImport)


def test_usedImport():
    flakes('import fu; print(fu)')
    flakes('from baz import fu; print(fu)')
    flakes('import fu; del fu')


def test_redefinedWhileUnused():
    flakes('import fu; fu = 3', m.RedefinedWhileUnused)
    flakes('import fu; fu, bar = 3', m.RedefinedWhileUnused)
    flakes('import fu; [fu, bar] = 3', m.RedefinedWhileUnused)


def test_redefinedIf():
    """Test that importing a module twice within an if block does raise a warning."""
    flakes('''
    i = 2
    if i==1:
        import os
        import os
    os.path''', m.RedefinedWhileUnused)


def test_redefinedIfElse():
    """Test that importing a module twice in if and else blocks does not raise a warning."""
    flakes('''
    i = 2
    if i==1:
        import os
    else:
        import os
    os.path''')


def test_redefinedTry():
    """Test that importing a module twice in an try block does raise a warning."""
    flakes('''
    try:
        import os
        import os
    except Exception:
        pass
    os.path''', m.RedefinedWhileUnused)


def test_redefinedTryExcept():
    """Test that importing a module twice in an try and except block does not raise a warning."""
    flakes('''
    try:
        import os
    except Exception:
        import os
    os.path''')


def test_redefinedTryNested():
    """Test that importing a module twice using a nested try/except and if blocks does not issue a warning."""
    flakes('''
    try:
        if True:
            if True:
                import os
    except Exception:
        import os
    os.path''')


def test_redefinedTryExceptMulti():
    flakes("""
    try:
        from aa import mixer
    except AttributeError:
        from bb import mixer
    except RuntimeError:
        from cc import mixer
    except Exception:
        from dd import mixer
    mixer(123)
    """)


def test_redefinedTryElse():
    flakes("""
    try:
        from aa import mixer
    except ImportError:
        pass
    else:
        from bb import mixer
    mixer(123)
    """, m.RedefinedWhileUnused)


def test_redefinedTryExceptElse():
    flakes("""
    try:
        import funca
    except ImportError:
        from bb import funca
        from bb import funcb
    else:
        from bbb import funcb
    print(funca, funcb)
    """)


def test_redefinedTryExceptFinally():
    flakes("""
    try:
        from aa import a
    except ImportError:
        from bb import a
    finally:
        a = 42
    print(a)
    """)


def test_redefinedTryExceptElseFinally():
    flakes("""
    try:
        import b
    except ImportError:
        b = Ellipsis
        from bb import a
    else:
        from aa import a
    finally:
        a = 42
    print(a, b)
    """)


def test_redefinedByFunction():
    flakes('''
    import fu
    def fu():
        pass
    ''', m.RedefinedWhileUnused)


def test_redefinedInNestedFunction():
    """Test that shadowing a global name with a nested function definition generates a warning."""
    flakes('''
    import fu
    def bar():
        def baz():
            def fu():
                pass
    ''', m.RedefinedWhileUnused, m.UnusedImport)


def test_redefinedByClass():
    flakes('''
    import fu
    class fu:
        pass
    ''', m.RedefinedWhileUnused)


def test_redefinedBySubclass():
    """If an imported name is redefined by a class statement

    which also uses that name in the bases list, no warning is emitted.

    """
    flakes('''
    from fu import bar
    class bar(bar):
        pass
    ''')


def test_redefinedInClass():
    """Test that shadowing a global with a class attribute does not produce a warning."""
    flakes('''
    import fu
    class bar:
        fu = 1
    print(fu)
    ''')


def test_usedInFunction():
    flakes('''
    import fu
    def fun():
        print(fu)
    ''')


def test_shadowedByParameter():
    flakes('''
    import fu
    def fun(fu):
        print(fu)
    ''', m.UnusedImport)

    flakes('''
    import fu
    def fun(fu):
        print(fu)
    print(fu)
    ''')


def test_newAssignment():
    flakes('fu = None')


def test_usedInGetattr():
    flakes('import fu; fu.bar.baz')
    flakes('import fu; "bar".fu.baz', m.UnusedImport)


def test_usedInSlice():
    flakes('import fu; print(fu.bar[1:])')


def test_usedInIfBody():
    flakes('''
    import fu
    if True: print(fu)
    ''')


def test_usedInIfConditional():
    flakes('''
    import fu
    if fu: pass
    ''')


def test_usedInElifConditional():
    flakes('''
    import fu
    if False: pass
    elif fu: pass
    ''')


def test_usedInElse():
    flakes('''
    import fu
    if False: pass
    else: print(fu)
    ''')


def test_usedInCall():
    flakes('import fu; fu.bar()')


def test_usedInClass():
    flakes('''
    import fu
    class bar:
        bar = fu
    ''')


def test_usedInClassBase():
    flakes('''
    import fu
    class bar(object, fu.baz):
        pass
    ''')


def test_notUsedInNestedScope():
    flakes('''
    import fu
    def bleh():
        pass
    print(fu)
    ''')


def test_usedInFor():
    flakes('''
    import fu
    for bar in range(9):
        print(fu)
    ''')


def test_usedInForElse():
    flakes('''
    import fu
    for bar in range(10):
        pass
    else:
        print(fu)
    ''')


def test_redefinedByFor():
    flakes('''
    import fu
    for fu in range(2):
        pass
    ''', m.RedefinedWhileUnused)


def test_shadowedByFor():
    """Test that shadowing a global name with a for loop variable generates a warning."""
    flakes('''
    import fu
    fu.bar()
    for fu in ():
        pass
    ''', m.ImportShadowedByLoopVar)


def test_shadowedByForDeep():
    """Test that shadowing a global name with a for loop variable nested in a tuple unpack generates a warning."""
    flakes('''
    import fu
    fu.bar()
    for (x, y, z, (a, b, c, (fu,))) in ():
        pass
    ''', m.ImportShadowedByLoopVar)


def test_usedInReturn():
    flakes('''
    import fu
    def fun():
        return fu
    ''')


def test_usedInOperators():
    flakes('import fu; 3 + fu.bar')
    flakes('import fu; 3 % fu.bar')
    flakes('import fu; 3 - fu.bar')
    flakes('import fu; 3 * fu.bar')
    flakes('import fu; 3 ** fu.bar')
    flakes('import fu; 3 / fu.bar')
    flakes('import fu; 3 // fu.bar')
    flakes('import fu; -fu.bar')
    flakes('import fu; ~fu.bar')
    flakes('import fu; 1 == fu.bar')
    flakes('import fu; 1 | fu.bar')
    flakes('import fu; 1 & fu.bar')
    flakes('import fu; 1 ^ fu.bar')
    flakes('import fu; 1 >> fu.bar')
    flakes('import fu; 1 << fu.bar')


def test_usedInAssert():
    flakes('import fu; assert fu.bar')


def test_usedInSubscript():
    flakes('import fu; fu.bar[1]')


def test_usedInLogic():
    flakes('import fu; fu and False')
    flakes('import fu; fu or False')
    flakes('import fu; not fu.bar')


def test_usedInList():
    flakes('import fu; [fu]')


def test_usedInTuple():
    flakes('import fu; (fu,)')


def test_usedInTry():
    flakes('''
    import fu
    try: fu
    except Exception: pass
    ''')


def test_usedInExcept():
    flakes('''
    import fu
    try: fu
    except Exception: pass
    ''')


def test_redefinedByExcept():
    as_exc = ', ' if version_info < (2, 6) else ' as '
    flakes('''
    import fu
    try: pass
    except Exception%sfu: pass
    ''' % as_exc, m.RedefinedWhileUnused)


def test_usedInRaise():
    flakes('''
    import fu
    raise fu.bar
    ''')


def test_usedInYield():
    flakes('''
    import fu
    def gen():
        yield fu
    ''')


def test_usedInDict():
    flakes('import fu; {fu:None}')
    flakes('import fu; {1:fu}')


def test_usedInParameterDefault():
    flakes('''
    import fu
    def f(bar=fu):
        pass
    ''')


def test_usedInAttributeAssign():
    flakes('import fu; fu.bar = 1')


def test_usedInKeywordArg():
    flakes('import fu; fu.bar(stuff=fu)')


def test_usedInAssignment():
    flakes('import fu; bar=fu')
    flakes('import fu; n=0; n+=fu')


def test_usedInListComp():
    flakes('import fu; [fu for _ in range(1)]')
    flakes('import fu; [1 for _ in range(1) if fu]')


def test_redefinedByListComp():
    flakes('import fu; [1 for fu in range(1)]', m.RedefinedWhileUnused)


def test_usedInTryFinally():
    flakes('''
    import fu
    try: pass
    finally: fu
    ''')

    flakes('''
    import fu
    try: fu
    finally: pass
    ''')


def test_usedInWhile():
    flakes('''
    import fu
    while 0:
        fu
    ''')

    flakes('''
    import fu
    while fu: pass
    ''')


def test_usedInGlobal():
    flakes('''
    import fu
    def f(): global fu
    ''', m.UnusedImport)


@pytest.mark.skipif("version_info >= (3,)")
def test_usedInBackquote():
    flakes('import fu; `fu`')


def test_usedInExec():
    if version_info < (3,):
        exec_stmt = 'exec "print 1" in fu.bar'
    else:
        exec_stmt = 'exec("print(1)", fu.bar)'
    flakes('import fu; %s' % exec_stmt)


def test_usedInLambda():
    flakes('import fu; lambda: fu')


def test_shadowedByLambda():
    flakes('import fu; lambda fu: fu', m.UnusedImport)


def test_usedInSliceObj():
    flakes('import fu; "meow"[::fu]')


def test_unusedInNestedScope():
    flakes('''
    def bar():
        import fu
    fu
    ''', m.UnusedImport, m.UndefinedName)


def test_methodsDontUseClassScope():
    flakes('''
    class bar:
        import fu
        def fun():
            fu
    ''', m.UnusedImport, m.UndefinedName)


def test_nestedFunctionsNestScope():
    flakes('''
    def a():
        def b():
            fu
        import fu
    ''')


def test_nestedClassAndFunctionScope():
    flakes('''
    def a():
        import fu
        class b:
            def c():
                print(fu)
    ''')


def test_importStar():
    flakes('from fu import *', m.ImportStarUsed, ignore_frosted_errors=[])


def test_packageImport():
    """If a dotted name is imported and used, no warning is reported."""
    flakes('''
    import fu.bar
    fu.bar
    ''')


def test_unusedPackageImport():
    """If a dotted name is imported and not used, an unused import warning is reported."""
    flakes('import fu.bar', m.UnusedImport)


def test_duplicateSubmoduleImport():
    """If a submodule of a package is imported twice, an unused

    import warning and a redefined while unused warning are reported.

    """
    flakes('''
    import fu.bar, fu.bar
    fu.bar
    ''', m.RedefinedWhileUnused)
    flakes('''
    import fu.bar
    import fu.bar
    fu.bar
    ''', m.RedefinedWhileUnused)


def test_differentSubmoduleImport():
    """If two different submodules of a package are imported,

    no duplicate import warning is reported for the package.

    """
    flakes('''
    import fu.bar, fu.baz
    fu.bar, fu.baz
    ''')
    flakes('''
    import fu.bar
    import fu.baz
    fu.bar, fu.baz
    ''')


def test_assignRHSFirst():
    flakes('import fu; fu = fu')
    flakes('import fu; fu, bar = fu')
    flakes('import fu; [fu, bar] = fu')
    flakes('import fu; fu += fu')


def test_tryingMultipleImports():
    flakes('''
    try:
        import fu
    except ImportError:
        import bar as fu
    fu
    ''')


def test_nonGlobalDoesNotRedefine():
    flakes('''
    import fu
    def a():
        fu = 3
        return fu
    fu
    ''')


def test_functionsRunLater():
    flakes('''
    def a():
        fu
    import fu
    ''')


def test_functionNamesAreBoundNow():
    flakes('''
    import fu
    def fu():
        fu
    fu
    ''', m.RedefinedWhileUnused)


def test_ignoreNonImportRedefinitions():
    flakes('a = 1; a = 2')


@pytest.mark.skipif("'todo'")
def test_importingForImportError():
    flakes('''
    try:
        import fu
    except ImportError:
        pass
    ''')


@pytest.mark.skipif("'todo: requires evaluating attribute access'")
def test_importedInClass():
    """Imports in class scope can be used through."""
    flakes('''
    class c:
        import i
        def __init__():
            i
    ''')


def test_futureImport():
    """__future__ is special."""
    flakes('from __future__ import division')
    flakes('''
    "docstring is allowed before future import"
    from __future__ import division
    ''')


def test_futureImportFirst():
    """__future__ imports must come before anything else."""
    flakes('''
    x = 5
    from __future__ import division
    ''', m.LateFutureImport)
    flakes('''
    from foo import bar
    from __future__ import division
    bar
    ''', m.LateFutureImport)


def test_ignoredInFunction():
    """An C{__all__} definition does not suppress unused import warnings in a function scope."""
    flakes('''
    def foo():
        import bar
        __all__ = ["bar"]
    ''', m.UnusedImport, m.UnusedVariable)


def test_ignoredInClass():
    """An C{__all__} definition does not suppress unused import warnings in a class scope."""
    flakes('''
    class foo:
        import bar
        __all__ = ["bar"]
    ''', m.UnusedImport)


def test_warningSuppressed():
    """If a name is imported and unused but is named in C{__all__}, no warning is reported."""
    flakes('''
    import foo
    __all__ = ["foo"]
    ''')


def test_unrecognizable():
    """If C{__all__} is defined in a way that can't be recognized statically, it is ignored."""
    flakes('''
    import foo
    __all__ = ["f" + "oo"]
    ''', m.UnusedImport)
    flakes('''
    import foo
    __all__ = [] + ["foo"]
    ''', m.UnusedImport)


def test_unboundExported():
    """If C{__all__} includes a name which is not bound, a warning is emitted."""
    flakes('''
    __all__ = ["foo"]
    ''', m.UndefinedExport)

    # Skip this in __init__.py though, since the rules there are a little
    # different.
    for filename in ["foo/__init__.py", "__init__.py"]:
        flakes('''
        __all__ = ["foo"]
        ''', filename=filename, **{'ignore_frosted_errors_for___init__.py': ['E101', 'E103']})


def test_importStarExported():
    """Do not report undefined if import * is used"""
    flakes('''
    from foolib import *
    __all__ = ["foo"]
    ''', m.ImportStarUsed)


def test_usedInGenExp():
    """Using a global in a generator expression results in no warnings."""
    flakes('import fu; (fu for _ in range(1))')
    flakes('import fu; (1 for _ in range(1) if fu)')


def test_redefinedByGenExp():
    """ Re-using a global name as the loop variable for a generator

    expression results in a redefinition warning.

    """
    flakes('import fu; (1 for fu in range(1))', m.RedefinedWhileUnused, m.UnusedImport)


def test_usedAsDecorator():
    """Using a global name in a decorator statement results in no warnings, but

    using an undefined name in a decorator statement results in an undefined
    name warning.

    """
    flakes('''
    from interior import decorate
    @decorate
    def f():
        return "hello"
    ''')

    flakes('''
    from interior import decorate
    @decorate('value')
    def f():
        return "hello"
    ''')

    flakes('''
    @decorate
    def f():
        return "hello"
    ''', m.UndefinedName)


def test_usedAsClassDecorator():
    """Using an imported name as a class decorator results in no warnings

    but using an undefined name as a class decorator results in an undefined name warning.

    """
    flakes('''
    from interior import decorate
    @decorate
    class foo:
        pass
    ''')

    flakes('''
    from interior import decorate
    @decorate("foo")
    class bar:
        pass
    ''')

    flakes('''
    @decorate
    class foo:
        pass
    ''', m.UndefinedName)

########NEW FILE########
__FILENAME__ = test_noqa
from frosted import messages as m
from frosted.api import _noqa_lines, _re_noqa, check
from frosted.reporter import Reporter

from .utils import LoggingReporter, flakes


def test_regex():
    # simple format
    assert _re_noqa.search('#noqa')
    assert _re_noqa.search('# noqa')
    # simple format is strict, must be at start of comment
    assert not _re_noqa.search('# foo noqa')

    # verbose format (not strict like simple format)
    assert _re_noqa.search('#frosted:noqa')
    assert _re_noqa.search('# frosted: noqa')
    assert _re_noqa.search('# foo frosted: noqa')


def test_checker_ignore_lines():
    # ignore same line
    flakes('from fu import *', ignore_lines=[1])
    # don't ignore different line
    flakes('from fu import *', m.ImportStarUsed, ignore_lines=[2])


def test_noqa_lines():
    assert _noqa_lines('from fu import bar; bar') == []
    assert _noqa_lines('from fu import * # noqa; bar') == [1]
    assert _noqa_lines('from fu import * #noqa\nbar\nfoo # frosted: noqa') == [1, 3]


def test_check_integration():
    """ make sure all the above logic comes together correctly in the check() function """
    output = []
    reporter = LoggingReporter(output)

    result = check('from fu import *', 'test', reporter, not_ignore_frosted_errors=['E103'])

    # errors reported
    assert result == 1
    assert "unable to detect undefined names" in output.pop(0)[1]

    # same test, but with ignore set
    output = []
    reporter = LoggingReporter(output)

    result = check('from fu import * # noqa', 'test', reporter)

    # errors reported
    assert result == 0
    assert len(output) == 0

########NEW FILE########
__FILENAME__ = test_other
"""Tests for various Frosted behavior."""

from __future__ import absolute_import, division, print_function, unicode_literals

from sys import version_info

import pytest
from pies.overrides import *

from frosted import messages as m

from .utils import flakes


def test_duplicateArgs():
    flakes('def fu(bar, bar): pass', m.DuplicateArgument)


@pytest.mark.skipif("'todo: this requires finding all assignments in the function body first'")
def test_localReferencedBeforeAssignment():
    flakes('''
    a = 1
    def f():
        a; a=1
    f()
    ''', m.UndefinedName)


def test_redefinedInListComp():
    """Test that shadowing a variable in a list comprehension raises a warning."""
    flakes('''
    a = 1
    [1 for a, b in [(1, 2)]]
    ''', m.RedefinedInListComp)
    flakes('''
    class A:
        a = 1
        [1 for a, b in [(1, 2)]]
    ''', m.RedefinedInListComp)
    flakes('''
    def f():
        a = 1
        [1 for a, b in [(1, 2)]]
    ''', m.RedefinedInListComp)
    flakes('''
    [1 for a, b in [(1, 2)]]
    [1 for a, b in [(1, 2)]]
    ''')
    flakes('''
    for a, b in [(1, 2)]:
        pass
    [1 for a, b in [(1, 2)]]
    ''')


def test_redefinedInGenerator():
    """Test that reusing a variable in a generator does not raise a warning."""
    flakes('''
    a = 1
    (1 for a, b in [(1, 2)])
    ''')
    flakes('''
    class A:
        a = 1
        list(1 for a, b in [(1, 2)])
    ''')
    flakes('''
    def f():
        a = 1
        (1 for a, b in [(1, 2)])
    ''', m.UnusedVariable)
    flakes('''
    (1 for a, b in [(1, 2)])
    (1 for a, b in [(1, 2)])
    ''')
    flakes('''
    for a, b in [(1, 2)]:
        pass
    (1 for a, b in [(1, 2)])
    ''')


@pytest.mark.skipif('''version_info < (2, 7)''')
def test_redefinedInSetComprehension():
    """Test that reusing a variable in a set comprehension does not raise a warning."""
    flakes('''
    a = 1
    {1 for a, b in [(1, 2)]}
    ''')
    flakes('''
    class A:
        a = 1
        {1 for a, b in [(1, 2)]}
    ''')
    flakes('''
    def f():
        a = 1
        {1 for a, b in [(1, 2)]}
    ''', m.UnusedVariable)
    flakes('''
    {1 for a, b in [(1, 2)]}
    {1 for a, b in [(1, 2)]}
    ''')
    flakes('''
    for a, b in [(1, 2)]:
        pass
    {1 for a, b in [(1, 2)]}
    ''')


@pytest.mark.skipif('''version_info < (2, 7)''')
def test_redefinedInDictComprehension():
    """Test that reusing a variable in a dict comprehension does not raise a warning."""
    flakes('''
    a = 1
    {1: 42 for a, b in [(1, 2)]}
    ''')
    flakes('''
    class A:
        a = 1
        {1: 42 for a, b in [(1, 2)]}
    ''')
    flakes('''
    def f():
        a = 1
        {1: 42 for a, b in [(1, 2)]}
    ''', m.UnusedVariable)
    flakes('''
    {1: 42 for a, b in [(1, 2)]}
    {1: 42 for a, b in [(1, 2)]}
    ''')
    flakes('''
    for a, b in [(1, 2)]:
        pass
    {1: 42 for a, b in [(1, 2)]}
    ''')


def test_redefinedFunction():
    """Test that shadowing a function definition with another one raises a warning."""
    flakes('''
    def a(): pass
    def a(): pass
    ''', m.RedefinedWhileUnused)


def test_redefinedClassFunction():
    """Test that shadowing a function definition in a class suite with another one raises a warning."""
    flakes('''
    class A:
        def a(): pass
        def a(): pass
    ''', m.RedefinedWhileUnused)


def test_redefinedIfElseFunction():
    """Test that shadowing a function definition twice in an if and else block does not raise a warning."""
    flakes('''
    if True:
        def a(): pass
    else:
        def a(): pass
    ''')


def test_redefinedIfFunction():
    """Test that shadowing a function definition within an if block raises a warning."""
    flakes('''
    if True:
        def a(): pass
        def a(): pass
    ''', m.RedefinedWhileUnused)


def test_redefinedTryExceptFunction():
    """Test that shadowing a function definition twice in try and except block does not raise a warning."""
    flakes('''
    try:
        def a(): pass
    except Exception:
        def a(): pass
    ''')


def test_redefinedTryFunction():
    """Test that shadowing a function definition within a try block raises a warning."""
    flakes('''
    try:
        def a(): pass
        def a(): pass
    except Exception:
        pass
    ''', m.RedefinedWhileUnused)


def test_redefinedIfElseInListComp():
    """Test that shadowing a variable in a list comprehension in an if and else block does not raise a warning."""
    flakes('''
    if False:
        a = 1
    else:
        [a for a in '12']
    ''')


def test_redefinedElseInListComp():
    """Test that shadowing a variable in a list comprehension in an else (or if) block raises a warning."""
    flakes('''
    if False:
        pass
    else:
        a = 1
        [a for a in '12']
    ''', m.RedefinedInListComp)


def test_functionDecorator():
    """Test that shadowing a function definition with a decorated version of that function does not raise a warning."""
    flakes('''
    from somewhere import somedecorator

    def a(): pass
    a = somedecorator(a)
    ''')


def test_classFunctionDecorator():
    """Test that shadowing a function definition in a class suite with a
    decorated version of that function does not raise a warning.

    """
    flakes('''
    class A:
        def a(): pass
        a = classmethod(a)
    ''')


@pytest.mark.skipif('''version_info < (2, 6)''')
def test_modernProperty():
    flakes("""
    class A:
        @property
        def t():
            pass
        @t.setter
        def t(self, value):
            pass
        @t.deleter
        def t():
            pass
    """)


def test_unaryPlus():
    """Don't die on unary +."""
    flakes('+1')


def test_undefinedBaseClass():
    """If a name in the base list of a class definition is undefined, a warning is emitted."""
    flakes('''
    class foo(foo):
        pass
    ''', m.UndefinedName)


def test_classNameUndefinedInClassBody():
    """If a class name is used in the body of that class's definition and the

    name is not already defined, a warning is emitted.

    """
    flakes('''
    class foo:
        foo
    ''', m.UndefinedName)


def test_classNameDefinedPreviously():
    """If a class name is used in the body of that class's definition and the
    name was previously defined in some other way, no warning is emitted.

    """
    flakes('''
    foo = None
    class foo:
        foo
    ''')


def test_classRedefinition():
    """If a class is defined twice in the same module, a warning is emitted."""
    flakes('''
    class Foo:
        pass
    class Foo:
        pass
    ''', m.RedefinedWhileUnused)


def test_functionRedefinedAsClass():
    """If a function is redefined as a class, a warning is emitted."""
    flakes('''
    def Foo():
        pass
    class Foo:
        pass
    ''', m.RedefinedWhileUnused)


def test_classRedefinedAsFunction():
    """If a class is redefined as a function, a warning is emitted."""
    flakes('''
    class Foo:
        pass
    def Foo():
        pass
    ''', m.RedefinedWhileUnused)


@pytest.mark.skipif("'todo: Too hard to make this warn but other cases stay silent'")
def test_doubleAssignment():
    """If a variable is re-assigned to without being used, no warning is emitted."""
    flakes('''
    x = 10
    x = 20
    ''', m.RedefinedWhileUnused)


def test_doubleAssignmentConditionally():
    """If a variable is re-assigned within a conditional, no warning is emitted."""
    flakes('''
    x = 10
    if True:
        x = 20
    ''')


def test_doubleAssignmentWithUse():
    """If a variable is re-assigned to after being used, no warning is emitted."""
    flakes('''
    x = 10
    y = x * 2
    x = 20
    ''')


def test_comparison():
    """If a defined name is used on either side of any of the six comparison operators, no warning is emitted."""
    flakes('''
    x = 10
    y = 20
    x < y
    x <= y
    x == y
    x != y
    x >= y
    x > y
    ''')


def test_identity():
    """If a defined name is used on either side of an identity test, no warning is emitted."""
    flakes('''
    x = 10
    y = 20
    x is y
    x is not y
    ''')


def test_containment():
    """If a defined name is used on either side of a containment test, no warning is emitted."""
    flakes('''
    x = 10
    y = 20
    x in y
    x not in y
    ''')


def test_loopControl():
    """break and continue statements are supported."""
    flakes('''
    for x in [1, 2]:
        break
    ''')
    flakes('''
    for x in [1, 2]:
        continue
    ''')


def test_ellipsis():
    """Ellipsis in a slice is supported."""
    flakes('''
    [1, 2][...]
    ''')


def test_extendedSlice():
    """Extended slices are supported."""
    flakes('''
    x = 3
    [1, 2][x,:]
    ''')


def test_varAugmentedAssignment():
    """Augmented assignment of a variable is supported.

    We don't care about var refs.

    """
    flakes('''
    foo = 0
    foo += 1
    ''')


def test_attrAugmentedAssignment():
    """Augmented assignment of attributes is supported.

    We don't care about attr refs.

    """
    flakes('''
    foo = None
    foo.bar += foo.baz
    ''')


def test_unusedVariable():
    """Warn when a variable in a function is assigned a value that's never used."""
    flakes('''
    def a():
        b = 1
    ''', m.UnusedVariable)


def test_unusedVariableAsLocals():
    """Using locals() it is perfectly valid to have unused variables."""
    flakes('''
    def a():
        b = 1
        return locals()
    ''')


def test_unusedVariableNoLocals():
    """Using locals() in wrong scope should not matter."""
    flakes('''
    def a():
        locals()
        def a():
            b = 1
            return
    ''', m.UnusedVariable)


def test_assignToGlobal():
    """Assigning to a global and then not using that global is perfectly
    acceptable.

    Do not mistake it for an unused local variable.

    """
    flakes('''
    b = 0
    def a():
        global b
        b = 1
    ''')


@pytest.mark.skipif('''version_info < (3,)''')
def test_assignToNonlocal():
    """Assigning to a nonlocal and then not using that binding is perfectly
    acceptable.

    Do not mistake it for an unused local variable.

    """
    flakes('''
    b = b'0'
    def a():
        nonlocal b
        b = b'1'
    ''')


def test_assignToMember():
    """Assigning to a member of another object and then not using that member
    variable is perfectly acceptable.

    Do not mistake it for an unused local variable.

    """
    # XXX: Adding this test didn't generate a failure. Maybe not
    # necessary?
    flakes('''
    class b:
        pass
    def a():
        b.foo = 1
    ''')


def test_assignInForLoop():
    """Don't warn when a variable in a for loop is assigned to but not used."""
    flakes('''
    def f():
        for i in range(10):
            pass
    ''')


def test_assignInListComprehension():
    """Don't warn when a variable in a list comprehension is assigned to but not used."""
    flakes('''
    def f():
        [None for i in range(10)]
    ''')


def test_generatorExpression():
    """Don't warn when a variable in a generator expression is assigned to but not used."""
    flakes('''
    def f():
        (None for i in range(10))
    ''')


def test_assignmentInsideLoop():
    """Don't warn when a variable assignment occurs lexically after its use."""
    flakes('''
    def f():
        x = None
        for i in range(10):
            if i > 2:
                return x
            x = i * 2
    ''')


def test_tupleUnpacking():
    """Don't warn when a variable included in tuple unpacking is unused.

    It's very common for variables in a tuple unpacking assignment to be unused in good Python code, so warning will
    only create false positives.

    """
    flakes('''
    def f():
        (x, y) = 1, 2
    ''')


def test_listUnpacking():
    """Don't warn when a variable included in list unpacking is unused."""
    flakes('''
    def f():
        [x, y] = [1, 2]
    ''')


def test_closedOver():
    """Don't warn when the assignment is used in an inner function."""
    flakes('''
    def barMaker():
        foo = 5
        def bar():
            return foo
        return bar
    ''')


def test_doubleClosedOver():
    """Don't warn when the assignment is used in an inner function, even if
    that inner function itself is in an inner function."""
    flakes('''
    def barMaker():
        foo = 5
        def bar():
            def baz():
                return foo
        return bar
    ''')


def test_tracebackhideSpecialVariable():
    """Do not warn about unused local variable __tracebackhide__, which is a
    special variable for py.test."""
    flakes("""
        def helper():
            __tracebackhide__ = True
    """)


def test_ifexp():
    """Test C{foo if bar else baz} statements."""
    flakes("a = 'moo' if True else 'oink'")
    flakes("a = foo if True else 'oink'", m.UndefinedName)
    flakes("a = 'moo' if True else bar", m.UndefinedName)


def test_withStatementNoNames():
    """No warnings are emitted for using inside or after a nameless  statement a name defined beforehand."""
    flakes('''
    from __future__ import with_statement
    bar = None
    with open("foo"):
        bar
    bar
    ''')


def test_withStatementSingleName():
    """No warnings are emitted for using a name defined by a  statement within the suite or afterwards."""
    flakes('''
    from __future__ import with_statement
    with open('foo') as bar:
        bar
    bar
    ''')


def test_withStatementAttributeName():
    """No warnings are emitted for using an attribute as the target of a  statement."""
    flakes('''
    from __future__ import with_statement
    import foo
    with open('foo') as foo.bar:
        pass
    ''')


def test_withStatementSubscript():
    """No warnings are emitted for using a subscript as the target of a  statement."""
    flakes('''
    from __future__ import with_statement
    import foo
    with open('foo') as foo[0]:
        pass
    ''')


def test_withStatementSubscriptUndefined():
    """An undefined name warning is emitted if the subscript used as the target of a with statement is not defined."""
    flakes('''
    from __future__ import with_statement
    import foo
    with open('foo') as foo[bar]:
        pass
    ''', m.UndefinedName)


def test_withStatementTupleNames():
    """No warnings are emitted for using any of the tuple of names defined

    by a statement within the suite or afterwards.

    """
    flakes('''
    from __future__ import with_statement
    with open('foo') as (bar, baz):
        bar, baz
    bar, baz
    ''')


def test_withStatementListNames():
    """No warnings are emitted for using any of the list of names defined by

    a statement within the suite or afterwards.

    """
    flakes('''
    from __future__ import with_statement
    with open('foo') as [bar, baz]:
        bar, baz
    bar, baz
    ''')


def test_withStatementComplicatedTarget():
    """ If the target of a  statement uses any or all of the valid forms
    for that part of the grammar
    (See: http://docs.python.org/reference/compound_stmts.html#the-with-statement),
    the names involved are checked both for definedness and any bindings
    created are respected in the suite of the statement and afterwards.

    """
    flakes('''
    from __future__ import with_statement
    c = d = e = g = h = i = None
    with open('foo') as [(a, b), c[d], e.f, g[h:i]]:
        a, b, c, d, e, g, h, i
    a, b, c, d, e, g, h, i
    ''')


def test_withStatementSingleNameUndefined():
    """An undefined name warning is emitted if the name first defined by a statement is used before the  statement."""
    flakes('''
    from __future__ import with_statement
    bar
    with open('foo') as bar:
        pass
    ''', m.UndefinedName)


def test_withStatementTupleNamesUndefined():
    """ An undefined name warning is emitted if a name first defined by a the
    tuple-unpacking form of the  statement is used before the statement.

    """
    flakes('''
    from __future__ import with_statement
    baz
    with open('foo') as (bar, baz):
        pass
    ''', m.UndefinedName)


def test_withStatementSingleNameRedefined():
    """A redefined name warning is emitted if a name bound by an import is
    rebound by the name defined by a  statement.

    """
    flakes('''
    from __future__ import with_statement
    import bar
    with open('foo') as bar:
        pass
    ''', m.RedefinedWhileUnused)


def test_withStatementTupleNamesRedefined():
    """ A redefined name warning is emitted if a name bound by an import is
    rebound by one of the names defined by the tuple-unpacking form of a
    statement.

    """
    flakes('''
    from __future__ import with_statement
    import bar
    with open('foo') as (bar, baz):
        pass
    ''', m.RedefinedWhileUnused)


def test_withStatementUndefinedInside():
    """An undefined name warning is emitted if a name is used inside the body
    of a  statement without first being bound.

    """
    flakes('''
    from __future__ import with_statement
    with open('foo') as bar:
        baz
    ''', m.UndefinedName)


def test_withStatementNameDefinedInBody():
    """A name defined in the body of a  statement can be used after the body ends without warning."""
    flakes('''
    from __future__ import with_statement
    with open('foo') as bar:
        baz = 10
    baz
    ''')


def test_withStatementUndefinedInExpression():
    """An undefined name warning is emitted if a name in the I{test} expression of a  statement is undefined."""
    flakes('''
    from __future__ import with_statement
    with bar as baz:
        pass
    ''', m.UndefinedName)

    flakes('''
    from __future__ import with_statement
    with bar as bar:
        pass
    ''', m.UndefinedName)


@pytest.mark.skipif('''version_info < (2, 7)''')
def test_dictComprehension():
    """Dict comprehensions are properly handled."""
    flakes('''
    a = {1: x for x in range(10)}
    ''')


@pytest.mark.skipif('''version_info < (2, 7)''')
def test_setComprehensionAndLiteral():
    """Set comprehensions are properly handled."""
    flakes('''
    a = {1, 2, 3}
    b = {x for x in range(10)}
    ''')


def test_exceptionUsedInExcept():
    as_exc = ', ' if version_info < (2, 6) else ' as '
    flakes('''
    try: pass
    except Exception%se: e
    ''' % as_exc)

    flakes('''
    def download_review():
        try: pass
        except Exception%se: e
    ''' % as_exc)


def test_exceptWithoutNameInFunction():
    """Don't issue false warning when an unnamed exception is used.

    Previously, there would be a false warning, but only when the try..except was in a function

    """
    flakes('''
    import tokenize
    def foo():
        try: pass
        except tokenize.TokenError: pass
    ''')


def test_exceptWithoutNameInFunctionTuple():
    """Don't issue false warning when an unnamed exception is used.

    This example catches a tuple of exception types.

    """
    flakes('''
    import tokenize
    def foo():
        try: pass
        except (tokenize.TokenError, IndentationError): pass
    ''')


def test_augmentedAssignmentImportedFunctionCall():
    """Consider a function that is called on the right part of an augassign operation to be used."""
    flakes('''
    from foo import bar
    baz = 0
    baz += bar()
    ''')


@pytest.mark.skipif('''version_info < (3, 3)''')
def test_yieldFromUndefined():
    """Test yield from statement."""
    flakes('''
    def bar():
        yield from foo()
    ''', m.UndefinedName)


def test_bareExcept():
    """
        Issue a warning when using bare except:.
    """
    flakes('''
        try:
            pass
        except:
            pass
        ''', m.BareExcept)


def test_access_debug():
    """Test accessing __debug__ returns no errors"""
    flakes('''
    if __debug__:
        print("success!")
        print(__debug__)
    ''')

########NEW FILE########
__FILENAME__ = test_return_with_arguments_inside_generator
from __future__ import absolute_import, division, print_function, unicode_literals

from sys import version_info

import pytest
from pies.overrides import *

from frosted import messages as m

from .utils import flakes


@pytest.mark.skipif("version_info >= (3,)")
def test_return():
    flakes('''
    class a:
        def b():
            for x in a.c:
                if x:
                    yield x
            return a
    ''', m.ReturnWithArgsInsideGenerator)


@pytest.mark.skipif("version_info >= (3,)")
def test_returnNone():
    flakes('''
    def a():
        yield 12
        return None
    ''', m.ReturnWithArgsInsideGenerator)


@pytest.mark.skipif("version_info >= (3,)")
def test_returnYieldExpression():
    flakes('''
    def a():
        b = yield a
        return b
    ''', m.ReturnWithArgsInsideGenerator)


@pytest.mark.skipif("version_info >= (3,)")
def test_return_with_args_inside_generator_not_duplicated():
    # doubly nested - should still only complain once
    flakes('''
    def f0():
        def f1():
            yield None
            return None
    ''', m.ReturnWithArgsInsideGenerator)

    # triple nested - should still only complain once
    flakes('''
    def f0():
        def f1():
            def f2():
                yield None
                return None
    ''', m.ReturnWithArgsInsideGenerator)


@pytest.mark.skipif("version_info >= (3,)")
def test_no_false_positives_for_return_inside_generator():
    # doubly nested - should still only complain once
    flakes('''
    def f():
        def g():
            yield None
        return g
    ''')

########NEW FILE########
__FILENAME__ = test_script
"""frosted/test/test_script.py.

Tests functionality (integration testing) that require starting a full frosted instance against input files

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or
substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED
TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

"""

from __future__ import absolute_import, division, print_function

import os
import shutil
import subprocess
import sys
import tempfile

import pytest
from pies.overrides import *

import frosted
from frosted.api import iter_source_code
from frosted.messages import UnusedImport

from .utils import Node

FROSTED_BINARY = os.path.join(os.path.dirname(frosted.__file__), 'main.py')


def setup_function(function):
    globals()['TEMP_DIR'] = tempfile.mkdtemp()
    globals()['TEMP_FILE_PATH'] = os.path.join(TEMP_DIR, 'temp')


def teardown_function(function):
    shutil.rmtree(TEMP_DIR)


def make_empty_file(*parts):
    assert parts
    fpath = os.path.join(TEMP_DIR, *parts)
    fd = open(fpath, 'a')
    fd.close()
    return fpath


def test_emptyDirectory():
    """There are no Python files in an empty directory."""
    assert list(iter_source_code([TEMP_DIR])) == []


def test_singleFile():
    """If the directory contains one Python file - iter_source_code will find it"""
    childpath = make_empty_file('foo.py')
    assert list(iter_source_code([TEMP_DIR])) == [childpath]


def test_onlyPythonSource():
    """Files that are not Python source files are not included."""
    make_empty_file('foo.pyc')
    assert list(iter_source_code([TEMP_DIR])) == []


def test_recurses():
    """If the Python files are hidden deep down in child directories, we will find them."""
    os.mkdir(os.path.join(TEMP_DIR, 'foo'))
    apath = make_empty_file('foo', 'a.py')
    os.mkdir(os.path.join(TEMP_DIR, 'bar'))
    bpath = make_empty_file('bar', 'b.py')
    cpath = make_empty_file('c.py')
    assert sorted(iter_source_code([TEMP_DIR])) == sorted([apath, bpath, cpath])


def test_multipleDirectories():
    """iter_source_code can be given multiple directories - it will recurse into each of them"""
    foopath = os.path.join(TEMP_DIR, 'foo')
    barpath = os.path.join(TEMP_DIR, 'bar')
    os.mkdir(foopath)
    apath = make_empty_file('foo', 'a.py')
    os.mkdir(barpath)
    bpath = make_empty_file('bar', 'b.py')
    assert sorted(iter_source_code([foopath, barpath])) == sorted([apath, bpath])


def test_explicitFiles():
    """If one of the paths given to iter_source_code is not a directory but a
    file, it will include that in its output."""
    epath = make_empty_file('e.py')
    assert list(iter_source_code([epath])) == [epath]


def run_frosted(paths, stdin=None):
    """Launch a subprocess running frosted."""
    env = native_dict(os.environ)
    env['PYTHONPATH'] = os.pathsep.join(sys.path)
    command = [sys.executable, FROSTED_BINARY]
    command.extend(paths)
    if stdin:
        p = subprocess.Popen(command, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (stdout, stderr) = p.communicate(stdin)
    else:
        p = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (stdout, stderr) = p.communicate()
    rv = p.wait()
    if PY3:
        stdout = stdout.decode('utf-8')
        stderr = stderr.decode('utf-8')

    return (stdout, stderr, rv)


def test_goodFile():
    """When a Python source file is all good, the return code is zero and no

    messages are printed to either stdout or stderr.

    """
    fd = open(TEMP_FILE_PATH, 'a')
    fd.close()
    d = run_frosted([TEMP_FILE_PATH])
    assert d == ('', '', 0)


def test_fileWithFlakes():
    """ When a Python source file has warnings,

    the return code is non-zero and the warnings are printed to stdout

    """
    fd = open(TEMP_FILE_PATH, 'wb')
    fd.write("import contraband\n".encode('ascii'))
    fd.close()
    d = run_frosted([TEMP_FILE_PATH])
    expected = UnusedImport(TEMP_FILE_PATH, Node(1), 'contraband')
    assert d[0].strip() == expected.message.strip()


@pytest.mark.skipif("sys.version_info >= (3,)")
def test_non_unicode_slash_u():
    """ Ensure \ u doesn't cause a unicode decode error """
    fd = open(TEMP_FILE_PATH, 'wb')
    fd.write('"""Example: C:\\foobar\\unit-tests\\test.py"""'.encode('ascii'))
    fd.close()
    d = run_frosted([TEMP_FILE_PATH])
    assert d == ('', '', 0)


def test_errors():
    """ When frosted finds errors with the files it's given, (if they don't exist, say),

    then the return code is non-zero and the errors are printed to stderr

    """
    d = run_frosted([TEMP_FILE_PATH, '-r'])
    error_msg = '%s: No such file or directory\n' % (TEMP_FILE_PATH,)
    assert d == ('', error_msg, 1)


def test_readFromStdin():
    """If no arguments are passed to C{frosted} then it reads from stdin."""
    d = run_frosted(['-'], stdin='import contraband'.encode('ascii'))

    expected = UnusedImport('<stdin>', Node(1), 'contraband')
    assert d[0].strip() == expected.message.strip()


@pytest.mark.skipif("sys.version_info >= (3,)")
def test_print_statement_python2():
    d = run_frosted(['-'], stdin='print "Hello, Frosted"'.encode('ascii'))
    assert d == ('', '', 0)

########NEW FILE########
__FILENAME__ = test_undefined_names
from __future__ import absolute_import, division, print_function, unicode_literals

from sys import version_info

import pytest
from pies.overrides import *

from _ast import PyCF_ONLY_AST
from frosted import messages as m
from frosted import checker

from.utils import flakes


def test_undefined():
    flakes('bar', m.UndefinedName)


def test_definedInListComp():
    flakes('[a for a in range(10) if a]')


def test_functionsNeedGlobalScope():
    flakes('''
    class a:
        def b():
            fu
    fu = 1
    ''')


def test_builtins():
    flakes('range(10)')


def test_builtinWindowsError():
    """WindowsError is sometimes a builtin name, so no warning is emitted for using it."""
    flakes('WindowsError')


def test_magicGlobalsFile():
    """Use of the __file magic global should not emit an undefined name
    warning."""
    flakes('__file__')


def test_magicGlobalsBuiltins():
    """Use of the __builtins magic global should not emit an undefined name warning."""
    flakes('__builtins__')


def test_magicGlobalImport():
    """Use of the __import__ magic global should not emit an undefined name warning."""
    flakes('__import__')

def test_magicGlobalsName():
    """Use of the __name magic global should not emit an undefined name warning."""
    flakes('__name__')


def test_magicGlobalsPath():
    """Use of the __path magic global should not emit an undefined name warning,

    if you refer to it from a file called __init__.py.

    """
    flakes('__path__', m.UndefinedName)
    flakes('__path__', filename='package/__init__.py')


def test_globalImportStar():
    """Can't find undefined names with import *."""
    flakes('from fu import *; bar', m.ImportStarUsed)


def test_localImportStar():
    """A local import * still allows undefined names to be found in upper scopes."""
    flakes('''
    def a():
        from fu import *
    bar
    ''', m.ImportStarUsed, m.UndefinedName)


@pytest.mark.skipif("version_info >= (3,)")
def test_unpackedParameter():
    """Unpacked function parameters create bindings."""
    flakes('''
    def a((bar, baz)):
        bar; baz
    ''')


@pytest.mark.skipif("'todo'")
def test_definedByGlobal():
    """"global" can make an otherwise undefined name in another function defined."""
    flakes('''
    def a(): global fu; fu = 1
    def b(): fu
    ''')


def test_globalInGlobalScope():
    """A global statement in the global scope is ignored."""
    flakes('''
    global x
    def foo():
        print(x)
    ''', m.UndefinedName)


def test_del():
    """Del deletes bindings."""
    flakes('a = 1; del a; a', m.UndefinedName)


def test_delGlobal():
    """Del a global binding from a function."""
    flakes('''
    a = 1
    def f():
        global a
        del a
    a
    ''')


def test_delUndefined():
    """Del an undefined name."""
    flakes('del a', m.UndefinedName)


def test_globalFromNestedScope():
    """Global names are available from nested scopes."""
    flakes('''
    a = 1
    def b():
        def c():
            a
    ''')


def test_laterRedefinedGlobalFromNestedScope():
    """Test that referencing a local name that shadows a global, before it is
    defined, generates a warning."""
    flakes('''
    a = 1
    def fun():
        a
        a = 2
        return a
    ''', m.UndefinedLocal)


def test_laterRedefinedGlobalFromNestedScope2():
    """Test that referencing a local name in a nested scope that shadows a
    global declared in an enclosing scope, before it is defined, generates a
    warning."""
    flakes('''
        a = 1
        def fun():
            global a
            def fun2():
                a
                a = 2
                return a
    ''', m.UndefinedLocal)


def test_intermediateClassScopeIgnored():
    """If a name defined in an enclosing scope is shadowed by a local variable
    and the name is used locally before it is bound, an unbound local warning
    is emitted, even if there is a class scope between the enclosing scope and
    the local scope."""
    flakes('''
    def f():
        x = 1
        class g:
            def h():
                a = x
                x = None
                print(x, a)
        print(x)
    ''', m.UndefinedLocal)


def test_doubleNestingReportsClosestName():
    """Test that referencing a local name in a nested scope that shadows a
    variable declared in two different outer scopes before it is defined in the
    innermost scope generates an UnboundLocal warning which refers to the
    nearest shadowed name."""
    exc = flakes('''
        def a():
            x = 1
            def b():
                x = 2 # line 5
                def c():
                    x
                    x = 3
                    return x
                return x
            return x
    ''', m.UndefinedLocal).messages[0]
    assert 'x' in exc.message
    assert str(5) in exc.message


def test_laterRedefinedGlobalFromNestedScope3():
    """Test that referencing a local name in a nested scope that shadows a
    global, before it is defined, generates a warning."""
    flakes('''
        def fun():
            a = 1
            def fun2():
                a
                a = 1
                return a
            return a
    ''', m.UndefinedLocal)


def test_undefinedAugmentedAssignment():
    flakes(
        '''
        def f(seq):
            a = 0
            seq[a] += 1
            seq[b] /= 2
            c[0] *= 2
            a -= 3
            d += 4
            e[any] = 5
        ''',
        m.UndefinedName,    # b
        m.UndefinedName,    # c
        m.UndefinedName, m.UnusedVariable,  # d
        m.UndefinedName,    # e
    )


def test_nestedClass():
    """Nested classes can access enclosing scope."""
    flakes('''
    def f(foo):
        class C:
            bar = foo
            def f():
                return foo
        return C()

    f(123).f()
    ''')


def test_badNestedClass():
    """Free variables in nested classes must bind at class creation."""
    flakes('''
    def f():
        class C:
            bar = foo
        foo = 456
        return foo
    f()
    ''', m.UndefinedName)


def test_definedAsStarArgs():
    """Star and double-star arg names are defined."""
    flakes('''
    def f(a, *b, **c):
        print(a, b, c)
    ''')


@pytest.mark.skipif("version_info < (3,)")
def test_definedAsStarUnpack():
    """Star names in unpack are defined."""
    flakes('''
    a, *b = range(10)
    print(a, b)
    ''')
    flakes('''
    *a, b = range(10)
    print(a, b)
    ''')
    flakes('''
    a, *b, c = range(10)
    print(a, b, c)
    ''')


@pytest.mark.skipif("version_info < (3,)")
def test_keywordOnlyArgs():
    """Keyword-only arg names are defined."""
    flakes('''
    def f(*, a, b=None):
        print(a, b)
    ''')

    flakes('''
    import default_b
    def f(*, a, b=default_b):
        print(a, b)
    ''')


@pytest.mark.skipif("version_info < (3,)")
def test_keywordOnlyArgsUndefined():
    """Typo in kwonly name."""
    flakes('''
    def f(*, a, b=default_c):
        print(a, b)
    ''', m.UndefinedName)


@pytest.mark.skipif("version_info < (3,)")
def test_annotationUndefined():
    """Undefined annotations."""
    flakes('''
    from abc import note1, note2, note3, note4, note5
    def func(a: note1, *args: note2,
                b: note3=12, **kw: note4) -> note5: pass
    ''')

    flakes('''
    def func():
        d = e = 42
        def func(a: {1, d}) -> (lambda c: e): pass
    ''')


@pytest.mark.skipif("version_info < (3,)")
def test_metaClassUndefined():
    flakes('''
    from abc import ABCMeta
    class A(metaclass=ABCMeta): pass
    ''')


def test_definedInGenExp():
    """Using the loop variable of a generator expression results in no
    warnings."""
    flakes('(a for a in %srange(10) if a)' %
                ('x' if version_info < (3,) else ''))


def test_undefinedWithErrorHandler():
    """Some compatibility code checks explicitly for NameError.

    It should not trigger warnings.

    """
    flakes('''
    try:
        socket_map
    except NameError:
        socket_map = {}
    ''')
    flakes('''
    try:
        _memoryview.contiguous
    except (NameError, AttributeError):
        raise RuntimeError("Python >= 3.3 is required")
    ''')
    # If NameError is not explicitly handled, generate a warning
    flakes('''
    try:
        socket_map
    except Exception:
        socket_map = {}
    ''', m.UndefinedName)
    flakes('''
    try:
        socket_map
    except Exception:
        socket_map = {}
    ''', m.UndefinedName)


def test_definedInClass():
    """Defined name for generator expressions and dict/set comprehension."""
    flakes('''
    class A:
        T = range(10)

        Z = (x for x in T)
        L = [x for x in T]
        B = dict((i, str(i)) for i in T)
    ''')

    if version_info >= (2, 7):
        flakes('''
        class A:
            T = range(10)

            X = {x for x in T}
            Y = {x:x for x in T}
        ''')


def test_impossibleContext():
    """A Name node with an unrecognized context results in a RuntimeError being raised."""
    tree = compile("x = 10", "<test>", "exec", PyCF_ONLY_AST)
    # Make it into something unrecognizable.
    tree.body[0].targets[0].ctx = object()
    with pytest.raises(RuntimeError):
        checker.Checker(tree)

########NEW FILE########
__FILENAME__ = utils
from __future__ import absolute_import, division, print_function, unicode_literals

import textwrap
from collections import namedtuple

from pies.overrides import *

from frosted import checker

PyCF_ONLY_AST = 1024
__all__ = ['flakes', 'Node', 'LoggingReporter']


def flakes(input, *expectedOutputs, **kw):
    tree = compile(textwrap.dedent(input), "<test>", "exec", PyCF_ONLY_AST)
    results = checker.Checker(tree, **kw)
    outputs = [message.type for message in results.messages]
    expectedOutputs = list(expectedOutputs)
    outputs.sort(key=lambda t: t.name)
    expectedOutputs.sort(key=lambda t: t.name)
    assert outputs == expectedOutputs, ('\n'
                                        'for input:\n'
                                        '%s\n'
                                        'expected outputs:\n'
                                        '%r\n'
                                        'but got:\n'
                                        '%s') % (input, expectedOutputs,
                                                 '\n'.join([str(o) for o in results.messages]))
    return results


class Node(namedtuple('Node', ['lineno', 'col_offset'])):
    """A mock AST Node."""

    def __new__(cls, lineno, col_offset=0):
        return super(Node, cls).__new__(cls, lineno, col_offset)


class LoggingReporter(namedtuple('LoggingReporter', ['log'])):
    """A mock Reporter implementation."""

    def flake(self, message):
        self.log.append(('flake', str(message)))

    def unexpected_error(self, filename, message):
        self.log.append(('unexpected_error', filename, message))

    def syntax_error(self, filename, msg, lineno, offset, line):
        self.log.append(('syntax_error', filename, msg, lineno, offset, line))

########NEW FILE########
__FILENAME__ = runtests
#! /usr/bin/env python

sources = """
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
P/+6xX94b+yP
"""

import base64
import imp
import sys
import zlib


class DictImporter(object):
    def __init__(self, sources):
        self.sources = sources

    def find_module(self, fullname, path=None):
        if fullname in self.sources:
            return self
        if fullname + '.__init__' in self.sources:
            return self
        return None

    def load_module(self, fullname):
        # print "load_module:",  fullname
        from types import ModuleType
        try:
            s = self.sources[fullname]
            is_pkg = False
        except KeyError:
            s = self.sources[fullname + '.__init__']
            is_pkg = True

        co = compile(s, fullname, 'exec')
        module = sys.modules.setdefault(fullname, ModuleType(fullname))
        module.__file__ = "%s/%s" % (__file__, fullname)
        module.__loader__ = self
        if is_pkg:
            module.__path__ = [fullname]

        do_exec(co, module.__dict__)
        return sys.modules[fullname]

    def get_source(self, name):
        res = self.sources.get(name)
        if res is None:
            res = self.sources.get(name + '.__init__')
        return res

if __name__ == "__main__":
    if sys.version_info >= (3, 0):
        exec("def do_exec(co, loc): exec(co, loc)\n")
        import pickle
        sources = sources.encode("ascii") # ensure bytes
        sources = pickle.loads(zlib.decompress(base64.decodebytes(sources)))
    else:
        import cPickle as pickle
        exec("def do_exec(co, loc): exec co in loc\n")
        sources = pickle.loads(zlib.decompress(base64.decodestring(sources)))

    importer = DictImporter(sources)
    sys.meta_path.insert(0, importer)

    entry = "import py; raise SystemExit(py.test.cmdline.main())"
    do_exec(entry, locals())

########NEW FILE########
