__FILENAME__ = isort
"""isort.py.

Exposes a simple library to sort through imports within Python code

usage:
    SortImports(file_name)
or:
    sorted = SortImports(file_contents=file_contents).output

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

import codecs
import copy
import itertools
import os
from collections import namedtuple
from difflib import unified_diff
from sys import path as PYTHONPATH
from sys import stderr, stdout

from natsort import natsorted
from pies.overrides import *

from . import settings

SECTION_NAMES = ("FUTURE", "STDLIB", "THIRDPARTY", "FIRSTPARTY", "LOCALFOLDER")
SECTIONS = namedtuple('Sections', SECTION_NAMES)(*range(len(SECTION_NAMES)))


class SortImports(object):
    incorrectly_sorted = False

    def __init__(self, file_path=None, file_contents=None, write_to_stdout=False, check=False,
                 show_diff=False, settings_path=None, **setting_overrides):

        if not settings_path and file_path:
            settings_path = os.path.dirname(os.path.abspath(file_path))
        settings_path = settings_path or os.getcwd()

        self.config = settings.from_path(settings_path).copy()
        for key, value in itemsview(setting_overrides):
            access_key = key.replace('not_', '').lower()
            if type(self.config.get(access_key)) in (list, tuple):
                if key.startswith('not_'):
                    self.config[access_key] = list(set(self.config[access_key]).difference(value))
                else:
                    self.config[access_key] = list(set(self.config[access_key]).union(value))
            else:
                self.config[key] = value

        indent = str(self.config['indent'])
        if indent.isdigit():
            indent = " " * int(indent)
        else:
            indent = indent.strip("'").strip('"')
            if indent.lower() == "tab":
                indent = "\t"
        self.config['indent'] = indent

        self.remove_imports = [self._format_simplified(removal) for removal in self.config.get('remove_imports', [])]
        self.add_imports = [self._format_natural(addition) for addition in self.config.get('add_imports', [])]
        self._section_comments = ["# " + value for key, value in itemsview(self.config) if
                                  key.startswith('import_heading') and value]

        file_name = file_path
        self.file_path = file_path or ""
        if file_path:
            file_path = os.path.abspath(file_path)
            if self._should_skip(file_path):
                if self.config['verbose']:
                    print("WARNING: {0} was skipped as it's listed in 'skip' setting".format(file_path))
                file_contents = None
            else:
                self.file_path = file_path
                with open(file_path) as file_to_import_sort:
                    file_contents = file_to_import_sort.read()
                    file_contents = PY2 and file_contents.decode('utf8') or file_contents

        if file_contents is None or ("isort:" + "skip_file") in file_contents:
            return

        self.in_lines = file_contents.split("\n")
        self.original_length = len(self.in_lines)
        if (self.original_length > 1 or self.in_lines[:1] not in ([], [""])) or self.config.get('force_adds', False):
            for add_import in self.add_imports:
                self.in_lines.append(add_import)
        self.number_of_lines = len(self.in_lines)

        self.out_lines = []
        self.comments = {'from': {}, 'straight': {}, 'nested': {}}
        self.imports = {}
        self.as_map = {}
        for section in itertools.chain(SECTIONS, self.config['forced_separate']):
            self.imports[section] = {'straight': set(), 'from': {}}

        self.index = 0
        self.import_index = -1
        self._first_comment_index_start = -1
        self._first_comment_index_end = -1
        self._parse()
        if self.import_index != -1:
            self._add_formatted_imports()

        self.length_change = len(self.out_lines) - self.original_length
        while self.out_lines and self.out_lines[-1].strip() == "":
            self.out_lines.pop(-1)
        self.out_lines.append("")

        self.output = "\n".join(self.out_lines)
        if self.config.get('atomic', False):
            try:
                compile(self._strip_top_comments(self.out_lines), self.file_path, 'exec', 0, 1)
            except SyntaxError:
                self.output = file_contents
                self.incorrectly_sorted = True
                try:
                    compile(self._strip_top_comments(self.in_lines), self.file_path, 'exec', 0, 1)
                    print("ERROR: {0} isort would have introduced syntax errors, please report to the project!". \
                          format(self.file_path))
                except SyntaxError:
                    print("ERROR: {0} File contains syntax errors.".format(self.file_path))

                return
        if check:
            if self.output == file_contents:
                if self.config['verbose']:
                    print("SUCCESS: {0} Everything Looks Good!".format(self.file_path))
            else:
                print("ERROR: {0} Imports are incorrectly sorted.".format(self.file_path))
                self.incorrectly_sorted = True
            return

        if show_diff:
            for line in unified_diff(file_contents.splitlines(1), self.output.splitlines(1),
                                     fromfile=self.file_path + ':before', tofile=self.file_path + ':after'):
                stdout.write(line)
        elif write_to_stdout:
            stdout.write(self.output)
        elif file_name:
            with codecs.open(self.file_path, encoding='utf-8', mode='w') as output_file:
                output_file.write(self.output)

    @staticmethod
    def _strip_top_comments(lines):
        """Strips # comments that exist at the top of the given lines"""
        lines = copy.copy(lines)
        while lines and lines[0].startswith("#"):
            lines = lines[1:]
        return "\n".join(lines)

    def _should_skip(self, filename):
        """Returns True if the file should be skipped based on the loaded settings."""
        if filename in self.config['skip']:
            return True

        position = os.path.split(filename)
        while position[1]:
            if position[1] in self.config['skip']:
                return True
            position = os.path.split(position[0])

    def place_module(self, moduleName):
        """Tries to determine if a module is a python std import, third party import, or project code:

        if it can't determine - it assumes it is project code

        """
        if moduleName.startswith("."):
            return SECTIONS.LOCALFOLDER

        try:
            firstPart = moduleName.split('.')[0]
        except IndexError:
            firstPart = None

        for forced_separate in self.config['forced_separate']:
            if moduleName.startswith(forced_separate):
                return forced_separate

        if moduleName == "__future__" or (firstPart == "__future__"):
            return SECTIONS.FUTURE
        elif moduleName in self.config['known_standard_library'] or \
                (firstPart in self.config['known_standard_library']):
            return SECTIONS.STDLIB
        elif moduleName in self.config['known_third_party'] or (firstPart in self.config['known_third_party']):
            return SECTIONS.THIRDPARTY
        elif moduleName in self.config['known_first_party'] or (firstPart in self.config['known_first_party']):
            return SECTIONS.FIRSTPARTY

        for prefix in PYTHONPATH:
            module_path = "/".join((prefix, moduleName.replace(".", "/")))
            package_path = "/".join((prefix, moduleName.split(".")[0]))
            if (os.path.exists(module_path + ".py") or os.path.exists(module_path + ".so") or
               (os.path.exists(package_path) and os.path.isdir(package_path))):
                if "site-packages" in prefix or "dist-packages" in prefix:
                    return SECTIONS.THIRDPARTY
                elif "python2" in prefix.lower() or "python3" in prefix.lower():
                    return SECTIONS.STDLIB
                else:
                    return SECTIONS.FIRSTPARTY

        return SECTION_NAMES.index(self.config['default_section'])

    def _get_line(self):
        """Returns the current line from the file while incrementing the index."""
        line = self.in_lines[self.index]
        self.index += 1
        return line

    @staticmethod
    def _import_type(line):
        """If the current line is an import line it will return its type (from or straight)"""
        if "isort:skip" in line:
            return
        elif line.startswith('import '):
            return "straight"
        elif line.startswith('from '):
            return "from"

    def _at_end(self):
        """returns True if we are at the end of the file."""
        return self.index == self.number_of_lines

    @staticmethod
    def _module_key(module_name, config, sub_imports=False):
        prefix = ""
        module_name = str(module_name)
        if sub_imports and config['order_by_type']:
            if module_name.isupper():
                prefix = "A"
            elif module_name[0:1].isupper():
                prefix = "B"
            else:
                prefix = "C"
        module_name = module_name.lower()
        return "{0}{1}{2}".format(module_name in config['force_to_top'] and "A" or "B", prefix,
                                  config['length_sort'] and (str(len(module_name)) + ":" + module_name) or module_name)

    def _add_comments(self, comments, original_string=""):
        """
            Returns a string with comments added
        """
        return comments and "{0}  # {1}".format(self._strip_comments(original_string)[0],
                                                "; ".join(comments)) or original_string

    def _wrap(self, line):
        """
            Returns an import wrapped to the specified line-length, if possible.
        """
        if len(line) > self.config['line_length'] and "." in line:
            line_parts = line.split(".")
            next_line = []
            while (len(line) + 2) > self.config['line_length'] and line_parts:
                next_line.append(line_parts.pop())
                line = ".".join(line_parts)
            return "{0}. \\\n{1}".format(line, self._wrap(self.config['indent'] + ".".join(next_line)))

        return line

    def _add_formatted_imports(self):
        """Adds the imports back to the file.

        (at the index of the first import) sorted alphabetically and split between groups

        """
        output = []
        for section in itertools.chain(SECTIONS, self.config['forced_separate']):
            straight_modules = list(self.imports[section]['straight'])
            straight_modules = natsorted(straight_modules, key=lambda key: self._module_key(key, self.config))
            section_output = []

            for module in straight_modules:
                if module in self.remove_imports:
                    continue

                if module in self.as_map:
                    import_definition = "import {0} as {1}".format(module, self.as_map[module])
                else:
                    import_definition = "import {0}".format(module)

                section_output.append(self._add_comments(self.comments['straight'].get(module), import_definition))

            from_modules = list(self.imports[section]['from'].keys())
            from_modules = natsorted(from_modules, key=lambda key: self._module_key(key, self.config))
            for module in from_modules:
                if module in self.remove_imports:
                    continue

                import_start = "from {0} import ".format(module)
                from_imports = list(self.imports[section]['from'][module])
                from_imports = natsorted(from_imports, key=lambda key: self._module_key(key, self.config, True))
                if self.remove_imports:
                    from_imports = [line for line in from_imports if not "{0}.{1}".format(module, line) in
                                    self.remove_imports]

                for from_import in copy.copy(from_imports):
                    import_as = self.as_map.get(module + "." + from_import, False)
                    if import_as:
                        import_definition = "{0} as {1}".format(from_import, import_as)
                        if self.config['combine_as_imports'] and not ("*" in from_imports and
                                                                      self.config['combine_star']):
                            from_imports[from_imports.index(from_import)] = import_definition
                        else:
                            import_statement = self._wrap(import_start + import_definition)
                            section_output.append(import_statement)
                            from_imports.remove(from_import)

                if from_imports:
                    comments = self.comments['from'].get(module)
                    if "*" in from_imports and self.config['combine_star']:
                        import_statement = self._wrap(self._add_comments(comments, "{0}*".format(import_start)))
                    elif self.config['force_single_line']:
                        import_statements = []
                        for from_import in from_imports:
                            single_import_line = self._add_comments(comments, import_start + from_import)
                            comment = self.comments['nested'].get(module, {}).get(from_import, None)
                            if comment:
                                single_import_line += "{0} {1}".format(comments and ";" or "  #", comment)
                            import_statements.append(self._wrap(single_import_line))
                            comments = None
                        import_statement = "\n".join(import_statements)
                    else:
                        star_import = False
                        if "*" in from_imports:
                            section_output.append(self._add_comments(comments, "{0}*".format(import_start)))
                            from_imports.remove('*')
                            star_import = True
                            comments = None

                        for from_import in copy.copy(from_imports):
                            comment = self.comments['nested'].get(module, {}).get(from_import, None)
                            if comment:
                                single_import_line = self._add_comments(comments, import_start + from_import)
                                single_import_line += "{0} {1}".format(comments and ";" or "  #", comment)
                                section_output.append(self._wrap(single_import_line))
                                from_imports.remove(from_import)
                                comments = None

                        if star_import:
                            import_statement = import_start + (", ").join(from_imports)
                        else:
                            import_statement = self._add_comments(comments, import_start + (", ").join(from_imports))
                        if not from_imports:
                            import_statement = ""
                        if len(import_statement) > self.config['line_length']:
                            if len(from_imports) > 1:
                                output_mode = settings.WrapModes._fields[self.config.get('multi_line_output',
                                                                                         0)].lower()
                                formatter = getattr(self, "_output_" + output_mode, self._output_grid)
                                dynamic_indent = " " * (len(import_start) + 1)
                                indent = self.config['indent']
                                line_length = self.config['line_length']
                                import_statement = formatter(import_start, copy.copy(from_imports),
                                                            dynamic_indent, indent, line_length, comments)
                                if self.config['balanced_wrapping']:
                                    lines = import_statement.split("\n")
                                    line_count = len(lines)
                                    minimum_length = min([len(line) for line in lines[:-1]])
                                    new_import_statement = import_statement
                                    while (len(lines[-1]) < minimum_length and
                                           len(lines) == line_count and line_length > 10):
                                        import_statement = new_import_statement
                                        line_length -= 1
                                        new_import_statement = formatter(import_start, copy.copy(from_imports),
                                                                        dynamic_indent, indent, line_length, comments)
                                        lines = new_import_statement.split("\n")
                            else:
                                import_statement = self._wrap(import_statement)

                    if import_statement:
                        section_output.append(import_statement)

            if section_output:
                section_name = section
                if section in SECTIONS:
                    section_name = SECTION_NAMES[section]
                section_title = self.config.get('import_heading_' + str(section_name).lower(), '')
                if section_title:
                    section_output.insert(0, "# " + section_title)
                output += section_output + ['']

        while [character.strip() for character in output[-1:]] == [""]:
            output.pop()

        output_at = 0
        if self.import_index < self.original_length:
            output_at = self.import_index
        elif self._first_comment_index_end != -1 and self._first_comment_index_start <= 2:
            output_at = self._first_comment_index_end
        self.out_lines[output_at:0] = output

        imports_tail = output_at + len(output)
        while [character.strip() for character in self.out_lines[imports_tail: imports_tail + 1]] == [""]:
            self.out_lines.pop(imports_tail)

        if len(self.out_lines) > imports_tail:
            next_construct = ""
            self._in_quote = False
            for line in self.out_lines[imports_tail:]:
                if not self._skip_line(line) and not line.strip().startswith("#") and line.strip():
                    next_construct = line
                    break

            if self.config['lines_after_imports'] != -1:
                self.out_lines[imports_tail:0] = ["" for line in range(self.config['lines_after_imports'])]
            elif next_construct.startswith("def") or next_construct.startswith("class") or \
               next_construct.startswith("@"):
                self.out_lines[imports_tail:0] = ["", ""]
            else:
                self.out_lines[imports_tail:0] = [""]

    def _output_grid(self, statement, imports, white_space, indent, line_length, comments):
        statement += "(" + imports.pop(0)
        while imports:
            next_import = imports.pop(0)
            next_statement = self._add_comments(comments, statement + ", " + next_import)
            if len(next_statement.split("\n")[-1]) + 1 > line_length:
                next_statement = (self._add_comments(comments, "{0},".format(statement)) +
                                  "\n{0}{1}".format(white_space, next_import))
                comments = None
            statement = next_statement
        return statement + ")"

    def _output_vertical(self, statement, imports, white_space, indent, line_length, comments):
        first_import = self._add_comments(comments, imports.pop(0) + ",") + "\n" + white_space
        return "{0}({1}{2})".format(statement, first_import, (",\n" + white_space).join(imports))

    def _output_hanging_indent(self, statement, imports, white_space, indent, line_length, comments):
        statement += imports.pop(0)
        while imports:
            next_import = imports.pop(0)
            next_statement = self._add_comments(comments, statement + ", " + next_import)
            if len(next_statement.split("\n")[-1]) + 3 > line_length:
                next_statement = (self._add_comments(comments, "{0}, \\".format(statement)) +
                                  "\n{0}{1}".format(indent, next_import))
                comments = None
            statement = next_statement
        return statement

    def _output_vertical_hanging_indent(self, statement, imports, white_space, indent, line_length, comments):
        return "{0}({1}\n{2}{3}\n)".format(statement, self._add_comments(comments), indent,
                                           (",\n" + indent).join(imports))

    def _output_vertical_grid_common(self, statement, imports, white_space, indent, line_length, comments):
        statement += self._add_comments(comments, "(") + "\n" + indent + imports.pop(0)
        while imports:
            next_import = imports.pop(0)
            next_statement = "{0}, {1}".format(statement, next_import)
            if len(next_statement.split("\n")[-1]) + 1 > line_length:
                next_statement = "{0},\n{1}{2}".format(statement, indent, next_import)
            statement = next_statement
        return statement

    def _output_vertical_grid(self, statement, imports, white_space, indent, line_length, comments):
        return self._output_vertical_grid_common(statement, imports, white_space, indent, line_length, comments) + ")"

    def _output_vertical_grid_grouped(self, statement, imports, white_space, indent, line_length, comments):
        return self._output_vertical_grid_common(statement, imports, white_space, indent, line_length, comments) + "\n)"

    @staticmethod
    def _strip_comments(line, comments=None):
        """Removes comments from import line."""
        if comments is None:
            comments = []

        new_comments = False
        comment_start = line.find("#")
        if comment_start != -1:
            comments.append(line[comment_start + 1:].strip())
            new_comments = True
            line = line[:comment_start]

        return line, comments, new_comments

    @staticmethod
    def _format_simplified(import_line):
        import_line = import_line.strip()
        if import_line.startswith("from "):
            import_line = import_line.replace("from ", "")
            import_line = import_line.replace(" import ", ".")
        elif import_line.startswith("import "):
            import_line = import_line.replace("import ", "")

        return import_line

    @staticmethod
    def _format_natural(import_line):
        import_line = import_line.strip()
        if not import_line.startswith("from ") and not import_line.startswith("import "):
            if not "." in import_line:
                return "import {0}".format(import_line)
            parts = import_line.split(".")
            end = parts.pop(-1)
            return "from {0} import {1}".format(".".join(parts), end)

        return import_line

    def _skip_line(self, line):
        skip_line = self._in_quote
        if '"' in line or "'" in line:
            index = 0
            if self._first_comment_index_start == -1:
                self._first_comment_index_start = self.index
            while index < len(line):
                if line[index] == "\\":
                    index += 1
                elif self._in_quote:
                    if line[index:index + len(self._in_quote)] == self._in_quote:
                        self._in_quote = False
                        if self._first_comment_index_end == -1:
                            self._first_comment_index_end = self.index
                elif line[index] in ("'", '"'):
                    long_quote = line[index:index + 3]
                    if long_quote in ('"""', "'''"):
                        self._in_quote = long_quote
                        index += 2
                    else:
                        self._in_quote = line[index]
                elif line[index] == "#":
                    break
                index += 1

        return skip_line or self._in_quote

    def _strip_syntax(self, import_string):
        import_string = import_string.replace("_import", "[[i]]")
        for remove_syntax in ['\\', '(', ')', ",", 'from ', 'import ']:
            import_string = import_string.replace(remove_syntax, " ")
        import_string = import_string.replace("[[i]]", "_import")
        return import_string

    def _parse(self):
        """Parses a python file taking out and categorizing imports."""
        self._in_quote = False
        while not self._at_end():
            line = self._get_line()
            skip_line = self._skip_line(line)

            if line in self._section_comments and not skip_line:
                if self.import_index == -1:
                    self.import_index = self.index - 1
                continue

            import_type = self._import_type(line)
            if not import_type or skip_line:
                self.out_lines.append(line)
                continue

            if self.import_index == -1:
                self.import_index = self.index - 1

            nested_comments = {}
            import_string, comments, new_comments = self._strip_comments(line)
            stripped_line = [part for part in self._strip_syntax(import_string).strip().split(" ") if part]

            if import_type == "from" and len(stripped_line) == 2 and stripped_line[1] != "*" and new_comments:
                nested_comments[stripped_line[-1]] = comments[0]

            if "(" in line and not self._at_end():
                while not line.strip().endswith(")") and not self._at_end():
                    line, comments, new_comments = self._strip_comments(self._get_line(), comments)
                    stripped_line = self._strip_syntax(line).strip()
                    if import_type == "from" and stripped_line and not " " in stripped_line and new_comments:
                        nested_comments[stripped_line] = comments[-1]
                    import_string += "\n" + line
            else:
                while line.strip().endswith("\\"):
                    line, comments, new_comments = self._strip_comments(self._get_line(), comments)
                    stripped_line = self._strip_syntax(line).strip()
                    if import_type == "from" and stripped_line and not " " in stripped_line and new_comments:
                        nested_comments[stripped_line] = comments[-1]
                    if import_string.strip().endswith(" import") or line.strip().startswith("import "):
                        import_string += "\n" + line
                    else:
                        import_string = import_string.rstrip().rstrip("\\") + line.lstrip()

            if import_type == "from":
                parts = import_string.split(" import ")
                from_import = parts[0].split(" ")
                import_string = " import ".join([from_import[0] + " " + "".join(from_import[1:])] + parts[1:])

            imports = self._strip_syntax(import_string).split()
            if "as" in imports and (imports.index('as') + 1) < len(imports):
                while "as" in imports:
                    index = imports.index('as')
                    if import_type == "from":
                        self.as_map[imports[0] + "." + imports[index - 1]] = imports[index + 1]
                    else:
                        self.as_map[imports[index - 1]] = imports[index + 1]
                    del imports[index:index + 2]
            if import_type == "from":
                import_from = imports.pop(0)
                root = self.imports[self.place_module(import_from)][import_type]
                for import_name in imports:
                    associated_commment = nested_comments.get(import_name)
                    if associated_commment:
                        self.comments['nested'].setdefault(import_from, {})[import_name] = associated_commment
                        comments.pop(comments.index(associated_commment))
                if comments:
                    self.comments['from'].setdefault(import_from, []).extend(comments)
                if root.get(import_from, False):
                    root[import_from].update(imports)
                else:
                    root[import_from] = set(imports)
            else:
                for module in imports:
                    if comments:
                        self.comments['straight'][module] = comments
                        comments = None
                    self.imports[self.place_module(module)][import_type].add(module)

########NEW FILE########
__FILENAME__ = main
#! /usr/bin/env python
'''  Tool for sorting imports alphabetically, and automatically separated into sections.

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

'''
from __future__ import absolute_import, division, print_function, unicode_literals

import argparse
import os
import sys

from pies.overrides import *

from isort import SECTION_NAMES, SortImports, __version__


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


def main():
    parser = argparse.ArgumentParser(description='Sort Python import definitions alphabetically '
                                                 'within logical sections.')
    parser.add_argument('files', nargs='+', help='One or more Python source files that need their imports sorted.')
    parser.add_argument('-l', '--lines', help='The max length of an import line (used for wrapping long imports).',
                        dest='line_length', type=int)
    parser.add_argument('-s', '--skip', help='Files that sort imports should skip over.', dest='skip', action='append')
    parser.add_argument('-ns', '--dont-skip', help='Files that sort imports should never skip over.',
                        dest='not_skip', action='append')
    parser.add_argument('-t', '--top', help='Force specific imports to the top of their appropriate section.',
                        dest='force_to_top', action='append')
    parser.add_argument('-b', '--builtin', dest='known_standard_library', action='append',
                        help='Force sortImports to recognize a module as part of the python standard library.')
    parser.add_argument('-o', '--thirdparty', dest='known_third_party', action='append',
                        help='Force sortImports to recognize a module as being part of a third party library.')
    parser.add_argument('-p', '--project', dest='known_first_party', action='append',
                        help='Force sortImports to recognize a module as being part of the current python project.')
    parser.add_argument('-m', '--multi_line', dest='multi_line_output', type=int, choices=[0, 1, 2, 3, 4, 5],
                        help='Multi line output (0-grid, 1-vertical, 2-hanging, 3-vert-hanging, 4-vert-grid, '
                            '5-vert-grid-grouped).')
    parser.add_argument('-i', '--indent', help='String to place for indents defaults to "    " (4 spaces).',
                        dest='indent', type=str)
    parser.add_argument('-a', '--add_import', dest='add_imports', action='append',
                        help='Adds the specified import line to all files, '
                             'automatically determining correct placement.')
    parser.add_argument('-af', '--force_adds', dest='force_adds', action='store_true',
                        help='Forces import adds even if the original file is empty.')
    parser.add_argument('-r', '--remove_import', dest='remove_imports', action='append',
                        help='Removes the specified import from all files.')
    parser.add_argument('-ls', '--length_sort', help='Sort imports by their string length.',
                        dest='length_sort', action='store_true', default=False)
    parser.add_argument('-d', '--stdout', help='Force resulting output to stdout, instead of in-place.',
                        dest='write_to_stdout', action='store_true')
    parser.add_argument('-c', '--check-only', action='store_true', default=False, dest="check",
                        help='Checks the file for unsorted imports and prints them to the '
                             'command line without modifying the file.')
    parser.add_argument('-sl', '--force_single_line_imports', dest='force_single_line', action='store_true',
                        help='Forces all from imports to appear on their own line')
    parser.add_argument('-sd', '--section-default', dest='default_section',
                        help='Sets the default section for imports (by default FIRSTPARTY) options: ' +
                        str(SECTION_NAMES))
    parser.add_argument('-df', '--diff', dest='show_diff', default=False, action='store_true',
                        help="Prints a diff of all the changes isort would make to a file, instead of "
                             "changing it in place")
    parser.add_argument('-e', '--balanced', dest='balanced_wrapping', action='store_true',
                        help='Balances wrapping to produce the most consistent line length possible')
    parser.add_argument('-rc', '--recursive', dest='recursive', action='store_true',
                        help='Recursively look for Python files of which to sort imports')
    parser.add_argument('-ot', '--order-by-type', dest='order_by_type',
                        action='store_true', help='Order imports by type in addition to alphabetically')
    parser.add_argument('-ac', '--atomic', dest='atomic', action='store_true',
                        help="Ensures the output doesn't save if the resulting file contains syntax errors.")
    parser.add_argument('-cs', '--combine-star', dest='combine_star', action='store_true',
                        help="Ensures that if a star import is present, nothing else is imported from that namespace.")
    parser.add_argument('-v', '--version', action='version', version='isort {0}'.format(__version__))
    parser.add_argument('-vb', '--verbose', action='store_true', dest="verbose",
                        help='Shows verbose output, such as when files are skipped or when a check is successful.')

    arguments = dict((key, value) for (key, value) in itemsview(vars(parser.parse_args())) if value)
    file_names = arguments.pop('files', [])

    if file_names == ['-']:
        SortImports(file_contents=sys.stdin.read(), write_to_stdout=True, **arguments)
    else:
        wrong_sorted_files = False
        if arguments.get('recursive', False):
            file_names = iter_source_code(file_names)
        for file_name in file_names:
            try:
                incorrectly_sorted = SortImports(file_name, **arguments).incorrectly_sorted
                if arguments.get('check', False) and incorrectly_sorted:
                    wrong_sorted_files = True
            except IOError as e:
                print("WARNING: Unable to parse file {0} due to {1}".format(file_name, e))
        if wrong_sorted_files:
            exit(1)


if __name__ == "__main__":
    main()

########NEW FILE########
__FILENAME__ = settings
"""isort/settings.py.

Defines how the default settings for isort should be loaded

(First from the default setting dictionary at the top of the file, then overridden by any settings
 in ~/.isort.cfg if there are any)

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
from collections import namedtuple

from pies.functools import lru_cache
from pies.overrides import *

try:
    import configparser
except ImportError:
    import ConfigParser as configparser

MAX_CONFIG_SEARCH_DEPTH = 25 # The number of parent directories isort will look for a config file within

WrapModes = ('GRID', 'VERTICAL', 'HANGING_INDENT', 'VERTICAL_HANGING_INDENT', 'VERTICAL_GRID', 'VERTICAL_GRID_GROUPED')
WrapModes = namedtuple('WrapModes', WrapModes)(*range(len(WrapModes)))

# Note that none of these lists must be complete as they are simply fallbacks for when included auto-detection fails.
default = {'force_to_top': [],
           'skip': ['__init__.py', ],
           'line_length': 80,
           'known_standard_library': ["abc", "anydbm", "argparse", "array", "asynchat", "asyncore", "atexit", "base64",
                                      "BaseHTTPServer", "bisect", "bz2", "calendar", "cgitb", "cmd", "codecs",
                                      "collections", "commands", "compileall", "ConfigParser", "contextlib", "Cookie",
                                      "copy", "cPickle", "cProfile", "cStringIO", "csv", "datetime", "dbhash", "dbm",
                                      "decimal", "difflib", "dircache", "dis", "doctest", "dumbdbm", "EasyDialogs",
                                      "errno", "exceptions", "filecmp", "fileinput", "fnmatch", "fractions",
                                      "functools", "gc", "gdbm", "getopt", "getpass", "gettext", "glob", "grp", "gzip",
                                      "hashlib", "heapq", "hmac", "imaplib", "imp", "inspect", "itertools", "json",
                                      "linecache", "locale", "logging", "mailbox", "math", "mhlib", "mmap",
                                      "multiprocessing", "operator", "optparse", "os", "pdb", "pickle", "pipes",
                                      "pkgutil", "platform", "plistlib", "pprint", "profile", "pstats", "pwd", "pyclbr",
                                      "pydoc", "Queue", "random", "re", "readline", "resource", "rlcompleter",
                                      "robotparser", "sched", "select", "shelve", "shlex", "shutil", "signal",
                                      "SimpleXMLRPCServer", "site", "sitecustomize", "smtpd", "smtplib", "socket",
                                      "SocketServer", "sqlite3", "string", "StringIO", "struct", "subprocess", "sys",
                                      "sysconfig", "tabnanny", "tarfile", "tempfile", "textwrap", "threading", "time",
                                      "timeit", "trace", "traceback", "unittest", "urllib", "urllib2", "urlparse",
                                      "usercustomize", "uuid", "warnings", "weakref", "webbrowser", "whichdb", "xml",
                                      "xmlrpclib", "zipfile", "zipimport", "zlib", 'builtins', '__builtin__', 'thread',
                                      "binascii"],
           'known_third_party': ['google.appengine.api'],
           'known_first_party': [],
           'multi_line_output': WrapModes.GRID,
           'forced_separate': [],
           'indent': ' ' * 4,
           'length_sort': False,
           'add_imports': [],
           'remove_imports': [],
           'force_single_line': False,
           'default_section': 'FIRSTPARTY',
           'import_heading_future': '',
           'import_heading_stdlib': '',
           'import_heading_thirdparty': '',
           'import_heading_firstparty': '',
           'import_heading_localfolder': '',
           'balanced_wrapping': False,
           'order_by_type': False,
           'atomic': False,
           'lines_after_imports': -1,
           'combine_as_imports': False,
           'combine_star': False,
           'verbose': False}


@lru_cache()
def from_path(path):
    computed_settings = default.copy()
    _update_settings_with_config(path, '.editorconfig', '~/.editorconfig', ('*', '*.py', '**.py'), computed_settings)
    _update_settings_with_config(path, '.isort.cfg', '~/.isort.cfg', ('settings', ), computed_settings)
    _update_settings_with_config(path, 'setup.cfg', None, ('isort', ), computed_settings)
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
        _update_with_config_file(editor_config_file, sections, computed_settings)


def _update_with_config_file(file_path, sections, computed_settings):
    settings = _get_config_data(file_path, sections).copy()
    if not settings:
        return

    if file_path.endswith(".editorconfig"):
        indent_style = settings.pop('indent_style', "").strip()
        indent_size = settings.pop('indent_size', "").strip()
        if indent_style == "space":
            computed_settings['indent'] = " " * (indent_size and int(indent_size) or 4)
        elif indent_style == "tab":
            computed_settings['indent'] = "\t" * (indent_size and int(indent_size) or 1)

        max_line_length = settings.pop('max_line_length', "").strip()
        if max_line_length:
            computed_settings['line_length'] = int(max_line_length)

    for key, value in itemsview(settings):
        access_key = key.replace('not_', '').lower()
        existing_value_type = type(default.get(access_key, ''))
        if existing_value_type in (list, tuple):
            existing_data = set(computed_settings.get(access_key, default.get(access_key)))
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

    return {}

########NEW FILE########
__FILENAME__ = isort_plugin
""" Sorts Python import definitions, and groups them based on type (stdlib, third-party, local).

isort/isort_kate_plugin.py

Provides a simple kate plugin that enables the use of isort to sort Python imports
in the currently open kate file.

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
import os

import kate

from isort import SortImports

try:
    from PySide import QtGui
except ImportError:
    from PyQt4 import QtGui


def sort_kate_imports(add_imports=(), remove_imports=()):
    """Sorts imports within Kate while maintaining cursor position and selection, even if length of file changes."""
    document = kate.activeDocument()
    view = document.activeView()
    position = view.cursorPosition()
    selection = view.selectionRange()
    sorter = SortImports(file_contents=document.text(), add_imports=add_imports, remove_imports=remove_imports,
                         settings_path=os.path.dirname(os.path.abspath(str(document.url().path()))))
    document.setText(sorter.output)
    position.setLine(position.line() + sorter.length_change)
    if selection:
        start = selection.start()
        start.setLine(start.line() + sorter.length_change)
        end = selection.end()
        end.setLine(end.line() + sorter.length_change)
        selection.setRange(start, end)
        view.setSelection(selection)
    view.setCursorPosition(position)


@kate.action
def sort_imports():
    """Sort Imports"""
    sort_kate_imports()


@kate.action
def add_imports():
    """Add Imports"""
    text, ok = QtGui.QInputDialog.getText(None,
                                          'Add Import',
                                          'Enter an import line to add (example: from os import path or os.path):')
    if ok:
        sort_kate_imports(add_imports=text.split(";"))


@kate.action
def remove_imports():
    """Remove Imports"""
    text, ok = QtGui.QInputDialog.getText(None,
                                          'Remove Import',
                                          'Enter an import line to remove (example: os.path or from os import path):')
    if ok:
        sort_kate_imports(remove_imports=text.split(";"))

########NEW FILE########
__FILENAME__ = isort_plugin_old
""" Sorts Python import definitions, and groups them based on type (stdlib, third-party, local).

isort/isort_kate_plugin.py

Provides a simple kate plugin that enables the use of isort to sort Python imports
in the currently open kate file.

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
import os

import kate

from isort import SortImports

try:
    from PySide import QtGui
except ImportError:
    from PyQt4 import QtGui


def sort_kate_imports(add_imports=(), remove_imports=()):
    """Sorts imports within Kate while maintaining cursor position and selection, even if length of file changes."""
    document = kate.activeDocument()
    view = document.activeView()
    position = view.cursorPosition()
    selection = view.selectionRange()
    sorter = SortImports(file_contents=document.text(), add_imports=add_imports, remove_imports=remove_imports,
                         settings_path=os.path.dirname(os.path.abspath(str(document.url().path()))))
    document.setText(sorter.output)
    position.setLine(position.line() + sorter.length_change)
    if selection:
        start = selection.start()
        start.setLine(start.line() + sorter.length_change)
        end = selection.end()
        end.setLine(end.line() + sorter.length_change)
        selection.setRange(start, end)
        view.setSelection(selection)
    view.setCursorPosition(position)


@kate.action(text="Sort Imports", shortcut="Ctrl+[", menu="Python")
def sort_imports():
    sort_kate_imports()


@kate.action(text="Add Import", shortcut="Ctrl+]", menu="Python")
def add_imports():
    text, ok = QtGui.QInputDialog.getText(None,
                                          'Add Import',
                                          'Enter an import line to add (example: from os import path or os.path):')
    if ok:
        sort_kate_imports(add_imports=text.split(";"))


@kate.action(text="Remove Import", shortcut="Ctrl+Shift+]", menu="Python")
def remove_imports():
    text, ok = QtGui.QInputDialog.getText(None,
                                          'Remove Import',
                                          'Enter an import line to remove (example: os.path or from os import path):')
    if ok:
        sort_kate_imports(remove_imports=text.split(";"))

########NEW FILE########
__FILENAME__ = runtests
#! /usr/bin/env python

sources = """
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
QXr8Oyz+AQhx7I8=
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
__FILENAME__ = test_isort
"""test_isort.py.

Tests all major functionality of the isort library
Should be ran using py.test by simply running by.test in the isort project directory

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

from pies.overrides import *

from isort.isort import SortImports
from isort.settings import WrapModes

REALLY_LONG_IMPORT = ("from third_party import lib1, lib2, lib3, lib4, lib5, lib6, lib7, lib8, lib9, lib10, lib11,"
                      "lib12, lib13, lib14, lib15, lib16, lib17, lib18, lib20, lib21, lib22")
REALLY_LONG_IMPORT_WITH_COMMENT = ("from third_party import lib1, lib2, lib3, lib4, lib5, lib6, lib7, lib8, lib9, "
                                   "lib10, lib11, lib12, lib13, lib14, lib15, lib16, lib17, lib18, lib20, lib21, lib22"
                                   " # comment")


def test_happy_path():
    """Test the most basic use case, straight imports no code, simply not organized by category."""
    test_input = ("import sys\n"
                  "import os\n"
                  "import myproject.test\n"
                  "import django.settings")
    test_output = SortImports(file_contents=test_input, known_third_party=['django']).output
    assert test_output == ("import os\n"
                           "import sys\n"
                           "\n"
                           "import django.settings\n"
                           "\n"
                           "import myproject.test\n")


def test_code_intermixed():
    """Defines what should happen when isort encounters imports intermixed with
    code.

    (it should pull them all to the top)

    """
    test_input = ("import sys\n"
                  "print('yo')\n"
                  "print('I like to put code between imports cause I want stuff to break')\n"
                  "import myproject.test\n")
    test_output = SortImports(file_contents=test_input).output
    assert test_output == ("import sys\n"
                           "\n"
                           "import myproject.test\n"
                           "\n"
                           "print('yo')\n"
                           "print('I like to put code between imports cause I want stuff to break')\n")


def test_correct_space_between_imports():
    """Ensure after imports a correct amount of space (in newlines) is
    enforced.

    (2 for method, class, or decorator definitions 1 for anything else)

    """
    test_input_method = ("import sys\n"
                         "def my_method():\n"
                         "    print('hello world')\n")
    test_output_method = SortImports(file_contents=test_input_method).output
    assert test_output_method == ("import sys\n"
                                  "\n"
                                  "\n"
                                  "def my_method():\n"
                                  "    print('hello world')\n")

    test_input_decorator = ("import sys\n"
                            "@my_decorator\n"
                            "def my_method():\n"
                            "    print('hello world')\n")
    test_output_decorator = SortImports(file_contents=test_input_decorator).output
    assert test_output_decorator == ("import sys\n"
                                     "\n"
                                     "\n"
                                     "@my_decorator\n"
                                     "def my_method():\n"
                                     "    print('hello world')\n")

    test_input_class = ("import sys\n"
                        "class MyClass(object):\n"
                        "    pass\n")
    test_output_class = SortImports(file_contents=test_input_class).output
    assert test_output_class == ("import sys\n"
                                 "\n"
                                 "\n"
                                 "class MyClass(object):\n"
                                 "    pass\n")

    test_input_other = ("import sys\n"
                        "print('yo')\n")
    test_output_other = SortImports(file_contents=test_input_other).output
    assert test_output_other == ("import sys\n"
                                 "\n"
                                 "print('yo')\n")


def test_sort_on_number():
    """Ensure numbers get sorted logically (10 > 9 not the other way around)"""
    test_input = ("import lib10\n"
                  "import lib9\n")
    test_output = SortImports(file_contents=test_input).output
    assert test_output == ("import lib9\n"
                           "import lib10\n")


def test_line_length():
    """Ensure isort enforces the set line_length."""
    assert len(SortImports(file_contents=REALLY_LONG_IMPORT, line_length=80).output.split("\n")[0]) <= 80
    assert len(SortImports(file_contents=REALLY_LONG_IMPORT, line_length=120).output.split("\n")[0]) <= 120

    test_output = SortImports(file_contents=REALLY_LONG_IMPORT, line_length=42).output
    assert test_output == ("from third_party import (lib1, lib2, lib3,\n"
                           "                         lib4, lib5, lib6,\n"
                           "                         lib7, lib8, lib9,\n"
                           "                         lib10, lib11,\n"
                           "                         lib12, lib13,\n"
                           "                         lib14, lib15,\n"
                           "                         lib16, lib17,\n"
                           "                         lib18, lib20,\n"
                           "                         lib21, lib22)\n")


def test_output_modes():
    """Test setting isort to use various output modes works as expected"""
    test_output_grid = SortImports(file_contents=REALLY_LONG_IMPORT,
                                   multi_line_output=WrapModes.GRID, line_length=40).output
    assert test_output_grid == ("from third_party import (lib1, lib2,\n"
                                "                         lib3, lib4,\n"
                                "                         lib5, lib6,\n"
                                "                         lib7, lib8,\n"
                                "                         lib9, lib10,\n"
                                "                         lib11, lib12,\n"
                                "                         lib13, lib14,\n"
                                "                         lib15, lib16,\n"
                                "                         lib17, lib18,\n"
                                "                         lib20, lib21,\n"
                                "                         lib22)\n")

    test_output_vertical = SortImports(file_contents=REALLY_LONG_IMPORT,
                                       multi_line_output=WrapModes.VERTICAL, line_length=40).output
    assert test_output_vertical == ("from third_party import (lib1,\n"
                                    "                         lib2,\n"
                                    "                         lib3,\n"
                                    "                         lib4,\n"
                                    "                         lib5,\n"
                                    "                         lib6,\n"
                                    "                         lib7,\n"
                                    "                         lib8,\n"
                                    "                         lib9,\n"
                                    "                         lib10,\n"
                                    "                         lib11,\n"
                                    "                         lib12,\n"
                                    "                         lib13,\n"
                                    "                         lib14,\n"
                                    "                         lib15,\n"
                                    "                         lib16,\n"
                                    "                         lib17,\n"
                                    "                         lib18,\n"
                                    "                         lib20,\n"
                                    "                         lib21,\n"
                                    "                         lib22)\n")

    comment_output_vertical = SortImports(file_contents=REALLY_LONG_IMPORT_WITH_COMMENT,
                                          multi_line_output=WrapModes.VERTICAL, line_length=40).output
    assert comment_output_vertical == ("from third_party import (lib1,  # comment\n"
                                       "                         lib2,\n"
                                       "                         lib3,\n"
                                       "                         lib4,\n"
                                       "                         lib5,\n"
                                       "                         lib6,\n"
                                       "                         lib7,\n"
                                       "                         lib8,\n"
                                       "                         lib9,\n"
                                       "                         lib10,\n"
                                       "                         lib11,\n"
                                       "                         lib12,\n"
                                       "                         lib13,\n"
                                       "                         lib14,\n"
                                       "                         lib15,\n"
                                       "                         lib16,\n"
                                       "                         lib17,\n"
                                       "                         lib18,\n"
                                       "                         lib20,\n"
                                       "                         lib21,\n"
                                       "                         lib22)\n")

    test_output_hanging_indent = SortImports(file_contents=REALLY_LONG_IMPORT,
                                             multi_line_output=WrapModes.HANGING_INDENT,
                                             line_length=40, indent="    ").output
    assert test_output_hanging_indent == ("from third_party import lib1, lib2, \\\n"
                                          "    lib3, lib4, lib5, lib6, lib7, \\\n"
                                          "    lib8, lib9, lib10, lib11, lib12, \\\n"
                                          "    lib13, lib14, lib15, lib16, lib17, \\\n"
                                          "    lib18, lib20, lib21, lib22\n")

    comment_output_hanging_indent = SortImports(file_contents=REALLY_LONG_IMPORT_WITH_COMMENT,
                                                multi_line_output=WrapModes.HANGING_INDENT,
                                                line_length=40, indent="    ").output
    assert comment_output_hanging_indent == ("from third_party import lib1, \\  # comment\n"
                                             "    lib2, lib3, lib4, lib5, lib6, \\\n"
                                             "    lib7, lib8, lib9, lib10, lib11, \\\n"
                                             "    lib12, lib13, lib14, lib15, lib16, \\\n"
                                             "    lib17, lib18, lib20, lib21, lib22\n")

    test_output_vertical_indent = SortImports(file_contents=REALLY_LONG_IMPORT,
                                              multi_line_output=WrapModes.VERTICAL_HANGING_INDENT,
                                              line_length=40, indent="    ").output
    assert test_output_vertical_indent == ("from third_party import (\n"
                                           "    lib1,\n"
                                           "    lib2,\n"
                                           "    lib3,\n"
                                           "    lib4,\n"
                                           "    lib5,\n"
                                           "    lib6,\n"
                                           "    lib7,\n"
                                           "    lib8,\n"
                                           "    lib9,\n"
                                           "    lib10,\n"
                                           "    lib11,\n"
                                           "    lib12,\n"
                                           "    lib13,\n"
                                           "    lib14,\n"
                                           "    lib15,\n"
                                           "    lib16,\n"
                                           "    lib17,\n"
                                           "    lib18,\n"
                                           "    lib20,\n"
                                           "    lib21,\n"
                                           "    lib22\n"
                                           ")\n")

    comment_output_vertical_indent = SortImports(file_contents=REALLY_LONG_IMPORT_WITH_COMMENT,
                                                 multi_line_output=WrapModes.VERTICAL_HANGING_INDENT,
                                                 line_length=40, indent="    ").output
    assert comment_output_vertical_indent == ("from third_party import (  # comment\n"
                                              "    lib1,\n"
                                              "    lib2,\n"
                                              "    lib3,\n"
                                              "    lib4,\n"
                                              "    lib5,\n"
                                              "    lib6,\n"
                                              "    lib7,\n"
                                              "    lib8,\n"
                                              "    lib9,\n"
                                              "    lib10,\n"
                                              "    lib11,\n"
                                              "    lib12,\n"
                                              "    lib13,\n"
                                              "    lib14,\n"
                                              "    lib15,\n"
                                              "    lib16,\n"
                                              "    lib17,\n"
                                              "    lib18,\n"
                                              "    lib20,\n"
                                              "    lib21,\n"
                                              "    lib22\n"
                                              ")\n")

    test_output_vertical_grid = SortImports(file_contents=REALLY_LONG_IMPORT,
                                            multi_line_output=WrapModes.VERTICAL_GRID,
                                            line_length=40, indent="    ").output
    assert test_output_vertical_grid == ("from third_party import (\n"
                                         "    lib1, lib2, lib3, lib4, lib5, lib6,\n"
                                         "    lib7, lib8, lib9, lib10, lib11,\n"
                                         "    lib12, lib13, lib14, lib15, lib16,\n"
                                         "    lib17, lib18, lib20, lib21, lib22)\n")

    comment_output_vertical_grid = SortImports(file_contents=REALLY_LONG_IMPORT_WITH_COMMENT,
                                               multi_line_output=WrapModes.VERTICAL_GRID,
                                               line_length=40, indent="    ").output
    assert comment_output_vertical_grid == ("from third_party import (  # comment\n"
                                            "    lib1, lib2, lib3, lib4, lib5, lib6,\n"
                                            "    lib7, lib8, lib9, lib10, lib11,\n"
                                            "    lib12, lib13, lib14, lib15, lib16,\n"
                                            "    lib17, lib18, lib20, lib21, lib22)\n")

    test_output_vertical_grid_grouped = SortImports(file_contents=REALLY_LONG_IMPORT,
                                                    multi_line_output=WrapModes.VERTICAL_GRID_GROUPED,
                                                    line_length=40, indent="    ").output
    assert test_output_vertical_grid_grouped == ("from third_party import (\n"
                                                 "    lib1, lib2, lib3, lib4, lib5, lib6,\n"
                                                 "    lib7, lib8, lib9, lib10, lib11,\n"
                                                 "    lib12, lib13, lib14, lib15, lib16,\n"
                                                 "    lib17, lib18, lib20, lib21, lib22\n"
                                                 ")\n")

    comment_output_vertical_grid_grouped = SortImports(file_contents=REALLY_LONG_IMPORT_WITH_COMMENT,
                                                       multi_line_output=WrapModes.VERTICAL_GRID_GROUPED,
                                                       line_length=40, indent="    ").output
    assert comment_output_vertical_grid_grouped == ("from third_party import (  # comment\n"
                                                    "    lib1, lib2, lib3, lib4, lib5, lib6,\n"
                                                    "    lib7, lib8, lib9, lib10, lib11,\n"
                                                    "    lib12, lib13, lib14, lib15, lib16,\n"
                                                    "    lib17, lib18, lib20, lib21, lib22\n"
                                                    ")\n")


def test_length_sort():
    """Test setting isort to sort on length instead of alphabetically."""
    test_input = ("import medium_sizeeeeeeeeeeeeee\n"
                  "import shortie\n"
                  "import looooooooooooooooooooooooooooooooooooooong\n"
                  "import medium_sizeeeeeeeeeeeeea\n")
    test_output = SortImports(file_contents=test_input, length_sort=True).output
    assert test_output == ("import shortie\n"
                           "import medium_sizeeeeeeeeeeeeea\n"
                           "import medium_sizeeeeeeeeeeeeee\n"
                           "import looooooooooooooooooooooooooooooooooooooong\n")


def test_convert_hanging():
    """Ensure that isort will convert hanging indents to correct indent
    method."""
    test_input = ("from third_party import lib1, lib2, \\\n"
                  "    lib3, lib4, lib5, lib6, lib7, \\\n"
                  "    lib8, lib9, lib10, lib11, lib12, \\\n"
                  "    lib13, lib14, lib15, lib16, lib17, \\\n"
                  "    lib18, lib20, lib21, lib22\n")
    test_output = SortImports(file_contents=test_input, multi_line_output=WrapModes.GRID,
                              line_length=40).output
    assert test_output == ("from third_party import (lib1, lib2,\n"
                           "                         lib3, lib4,\n"
                           "                         lib5, lib6,\n"
                           "                         lib7, lib8,\n"
                           "                         lib9, lib10,\n"
                           "                         lib11, lib12,\n"
                           "                         lib13, lib14,\n"
                           "                         lib15, lib16,\n"
                           "                         lib17, lib18,\n"
                           "                         lib20, lib21,\n"
                           "                         lib22)\n")


def test_custom_indent():
    """Ensure setting a custom indent will work as expected."""
    test_output = SortImports(file_contents=REALLY_LONG_IMPORT, multi_line_output=WrapModes.HANGING_INDENT,
                              line_length=40, indent="   ", balanced_wrapping=False).output
    assert test_output == ("from third_party import lib1, lib2, \\\n"
                           "   lib3, lib4, lib5, lib6, lib7, lib8, \\\n"
                           "   lib9, lib10, lib11, lib12, lib13, \\\n"
                           "   lib14, lib15, lib16, lib17, lib18, \\\n"
                           "   lib20, lib21, lib22\n")

    test_output = SortImports(file_contents=REALLY_LONG_IMPORT, multi_line_output=WrapModes.HANGING_INDENT,
                              line_length=40, indent="'  '", balanced_wrapping=False).output
    assert test_output == ("from third_party import lib1, lib2, \\\n"
                           "  lib3, lib4, lib5, lib6, lib7, lib8, \\\n"
                           "  lib9, lib10, lib11, lib12, lib13, \\\n"
                           "  lib14, lib15, lib16, lib17, lib18, \\\n"
                           "  lib20, lib21, lib22\n")

    test_output = SortImports(file_contents=REALLY_LONG_IMPORT, multi_line_output=WrapModes.HANGING_INDENT,
                              line_length=40, indent="tab", balanced_wrapping=False).output
    assert test_output == ("from third_party import lib1, lib2, \\\n"
                           "\tlib3, lib4, lib5, lib6, lib7, lib8, \\\n"
                           "\tlib9, lib10, lib11, lib12, lib13, \\\n"
                           "\tlib14, lib15, lib16, lib17, lib18, \\\n"
                           "\tlib20, lib21, lib22\n")

    test_output = SortImports(file_contents=REALLY_LONG_IMPORT, multi_line_output=WrapModes.HANGING_INDENT,
                              line_length=40, indent=2, balanced_wrapping=False).output
    assert test_output == ("from third_party import lib1, lib2, \\\n"
                           "  lib3, lib4, lib5, lib6, lib7, lib8, \\\n"
                           "  lib9, lib10, lib11, lib12, lib13, \\\n"
                           "  lib14, lib15, lib16, lib17, lib18, \\\n"
                           "  lib20, lib21, lib22\n")


def test_skip():
    """Ensure skipping a single import will work as expected."""
    test_input = ("import myproject\n"
                  "import django\n"
                  "print('hey')\n"
                  "import sys  # isort:skip this import needs to be placed here\n\n\n\n\n\n\n")

    test_output = SortImports(file_contents=test_input, known_third_party=['django']).output
    assert test_output == ("import django\n"
                           "\n"
                           "import myproject\n"
                           "\n"
                           "print('hey')\n"
                           "import sys  # isort:skip this import needs to be placed here\n")


def test_force_to_top():
    """Ensure forcing a single import to the top of its category works as expected."""
    test_input = ("import lib6\n"
                  "import lib2\n"
                  "import lib5\n"
                  "import lib1\n")
    test_output = SortImports(file_contents=test_input, force_to_top=['lib5']).output
    assert test_output == ("import lib5\n"
                           "import lib1\n"
                           "import lib2\n"
                           "import lib6\n")


def test_add_imports():
    """Ensures adding imports works as expected."""
    test_input = ("import lib6\n"
                  "import lib2\n"
                  "import lib5\n"
                  "import lib1\n\n")
    test_output = SortImports(file_contents=test_input, add_imports=['import lib4', 'import lib7']).output
    assert test_output == ("import lib1\n"
                           "import lib2\n"
                           "import lib4\n"
                           "import lib5\n"
                           "import lib6\n"
                           "import lib7\n")

    # Using simplified syntax
    test_input = ("import lib6\n"
                  "import lib2\n"
                  "import lib5\n"
                  "import lib1\n\n")
    test_output = SortImports(file_contents=test_input, add_imports=['lib4', 'lib7', 'lib8.a']).output
    assert test_output == ("import lib1\n"
                           "import lib2\n"
                           "import lib4\n"
                           "import lib5\n"
                           "import lib6\n"
                           "import lib7\n"
                           "from lib8 import a\n")

    # On a file that has no pre-existing imports
    test_input = ('"""Module docstring"""\n'
                  '\n'
                  'class MyClass(object):\n'
                  '    pass\n')
    test_output = SortImports(file_contents=test_input, add_imports=['from __future__ import print_function']).output
    assert test_output == ('"""Module docstring"""\n'
                           'from __future__ import print_function\n'
                           '\n'
                           '\n'
                           'class MyClass(object):\n'
                           '    pass\n')

    # On a file that has no pre-existing imports, and no doc-string
    test_input = ('class MyClass(object):\n'
                  '    pass\n')
    test_output = SortImports(file_contents=test_input, add_imports=['from __future__ import print_function']).output
    assert test_output == ('from __future__ import print_function\n'
                           '\n'
                           '\n'
                           'class MyClass(object):\n'
                           '    pass\n')

    # On a file with no content what so ever
    test_input = ("")
    test_output = SortImports(file_contents=test_input, add_imports=['lib4']).output
    assert test_output == ("")

    # On a file with no content what so ever, after force_adds is set to True
    test_input = ("")
    test_output = SortImports(file_contents=test_input, add_imports=['lib4'], force_adds=True).output
    assert test_output == ("import lib4\n")


def test_remove_imports():
    """Ensures removing imports works as expected."""
    test_input = ("import lib6\n"
                  "import lib2\n"
                  "import lib5\n"
                  "import lib1")
    test_output = SortImports(file_contents=test_input, remove_imports=['lib2', 'lib6']).output
    assert test_output == ("import lib1\n"
                           "import lib5\n")

    # Using natural syntax
    test_input = ("import lib6\n"
                  "import lib2\n"
                  "import lib5\n"
                  "import lib1\n"
                  "from lib8 import a")
    test_output = SortImports(file_contents=test_input, remove_imports=['import lib2', 'import lib6',
                                                                        'from lib8 import a']).output
    assert test_output == ("import lib1\n"
                           "import lib5\n")



def test_explicitly_local_import():
    """Ensure that explicitly local imports are separated."""
    test_input = ("import lib1\n"
                  "import lib2\n"
                  "import .lib6\n"
                  "from . import lib7")
    assert SortImports(file_contents=test_input).output == ("import lib1\n"
                                                            "import lib2\n"
                                                            "\n"
                                                            "import .lib6\n"
                                                            "from . import lib7\n")


def test_quotes_in_file():
    """Ensure imports within triple quotes don't get imported."""
    test_input = ('import os\n'
                  '\n'
                  '"""\n'
                  'Let us\n'
                  'import foo\n'
                  'okay?\n'
                  '"""\n')
    assert SortImports(file_contents=test_input).output == test_input

    test_input = ('import os\n'
                  '\n'
                  "'\"\"\"'\n"
                  'import foo\n')
    assert SortImports(file_contents=test_input).output == ('import os\n'
                                                            '\n'
                                                            'import foo\n'
                                                            '\n'
                                                            "'\"\"\"'\n")

    test_input = ('import os\n'
                  '\n'
                  '"""Let us"""\n'
                  'import foo\n'
                  '"""okay?"""\n')
    assert SortImports(file_contents=test_input).output == ('import os\n'
                                                            '\n'
                                                            'import foo\n'
                                                            '\n'
                                                            '"""Let us"""\n'
                                                            '"""okay?"""\n')

    test_input = ('import os\n'
                  '\n'
                  '#"""\n'
                  'import foo\n'
                  '#"""')
    assert SortImports(file_contents=test_input).output == ('import os\n'
                                                            '\n'
                                                            'import foo\n'
                                                            '\n'
                                                            '#"""\n'
                                                            '#"""\n')

    test_input = ('import os\n'
                  '\n'
                  "'\\\n"
                  "import foo'\n")
    assert SortImports(file_contents=test_input).output == test_input

    test_input = ('import os\n'
                  '\n'
                  "'''\n"
                  "\\'''\n"
                  'import junk\n'
                  "'''\n")
    assert SortImports(file_contents=test_input).output == test_input


def test_check_newline_in_imports(capsys):
    """Ensure tests works correctly when new lines are in imports."""
    test_input = ('from lib1 import (\n'
                  '    sub1,\n'
                  '    sub2,\n'
                  '    sub3\n)\n')

    SortImports(file_contents=test_input, multi_line_output=WrapModes.VERTICAL_HANGING_INDENT, line_length=20,
                check=True, verbose=True)
    out, err = capsys.readouterr()
    assert 'SUCCESS' in out


def test_forced_separate():
    """Ensure that forcing certain sub modules to show separately works as expected."""
    test_input = ('import sys\n'
                  'import warnings\n'
                  'from collections import OrderedDict\n'
                  '\n'
                  'from django.core.exceptions import ImproperlyConfigured, SuspiciousOperation\n'
                  'from django.core.paginator import InvalidPage\n'
                  'from django.core.urlresolvers import reverse\n'
                  'from django.db import models\n'
                  'from django.db.models.fields import FieldDoesNotExist\n'
                  'from django.utils import six\n'
                  'from django.utils.deprecation import RenameMethodsBase\n'
                  'from django.utils.encoding import force_str, force_text\n'
                  'from django.utils.http import urlencode\n'
                  'from django.utils.translation import ugettext, ugettext_lazy\n'
                  '\n'
                  'from django.contrib.admin import FieldListFilter\n'
                  'from django.contrib.admin.exceptions import DisallowedModelAdminLookup\n'
                  'from django.contrib.admin.options import IncorrectLookupParameters, IS_POPUP_VAR, TO_FIELD_VAR\n')
    assert SortImports(file_contents=test_input, forced_separate=['django.contrib'],
                       known_third_party=['django'], line_length=120, order_by_type=False).output == test_input


def test_default_section():
    """Test to ensure changing the default section works as expected."""
    test_input = ("import sys\n"
                  "import os\n"
                  "import myproject.test\n"
                  "import django.settings")
    test_output = SortImports(file_contents=test_input, known_third_party=['django'],
                              default_section="FIRSTPARTY").output
    assert test_output == ("import os\n"
                           "import sys\n"
                           "\n"
                           "import django.settings\n"
                           "\n"
                           "import myproject.test\n")

    test_output_custom = SortImports(file_contents=test_input, known_third_party=['django'],
                                     default_section="STDLIB").output
    assert test_output_custom == ("import myproject.test\n"
                                  "import os\n"
                                  "import sys\n"
                                  "\n"
                                  "import django.settings\n")


def test_force_single_line_imports():
    """Test to ensure forcing imports to each have their own line works as expected."""
    test_input = ("from third_party import lib1, lib2, \\\n"
                  "    lib3, lib4, lib5, lib6, lib7, \\\n"
                  "    lib8, lib9, lib10, lib11, lib12, \\\n"
                  "    lib13, lib14, lib15, lib16, lib17, \\\n"
                  "    lib18, lib20, lib21, lib22\n")
    test_output = SortImports(file_contents=test_input, multi_line_output=WrapModes.GRID,
                              line_length=40, force_single_line=True).output
    assert test_output == ("from third_party import lib1\n"
                           "from third_party import lib2\n"
                           "from third_party import lib3\n"
                           "from third_party import lib4\n"
                           "from third_party import lib5\n"
                           "from third_party import lib6\n"
                           "from third_party import lib7\n"
                           "from third_party import lib8\n"
                           "from third_party import lib9\n"
                           "from third_party import lib10\n"
                           "from third_party import lib11\n"
                           "from third_party import lib12\n"
                           "from third_party import lib13\n"
                           "from third_party import lib14\n"
                           "from third_party import lib15\n"
                           "from third_party import lib16\n"
                           "from third_party import lib17\n"
                           "from third_party import lib18\n"
                           "from third_party import lib20\n"
                           "from third_party import lib21\n"
                           "from third_party import lib22\n")


def test_titled_imports():
    """Tests setting custom titled/commented import sections."""
    test_input = ("import sys\n"
                  "import os\n"
                  "import myproject.test\n"
                  "import django.settings")
    test_output = SortImports(file_contents=test_input, known_third_party=['django'],
                              import_heading_stdlib="Standard Library", import_heading_firstparty="My Stuff").output
    assert test_output == ("# Standard Library\n"
                           "import os\n"
                           "import sys\n"
                           "\n"
                           "import django.settings\n"
                           "\n"
                           "# My Stuff\n"
                           "import myproject.test\n")
    test_second_run = SortImports(file_contents=test_output, known_third_party=['django'],
                                  import_heading_stdlib="Standard Library", import_heading_firstparty="My Stuff").output
    assert test_second_run == test_output


def test_balanced_wrapping():
    """Tests balanced wrapping mode, where the length of individual lines maintain width."""
    test_input = ("from __future__ import (absolute_import, division, print_function,\n"
                  "                        unicode_literals)")
    test_output = SortImports(file_contents=test_input, line_length=70, balanced_wrapping=True).output
    assert test_output == ("from __future__ import (absolute_import, division,\n"
                           "                        print_function, unicode_literals)\n")


def test_relative_import_with_space():
    """Tests the case where the relation and the module that is being imported from is separated with a space."""
    test_input = ("from ... fields.sproqet import SproqetCollection")
    assert SortImports(file_contents=test_input).output == ("from ...fields.sproqet import SproqetCollection\n")


def test_multiline_import():
    """Test the case where import spawns multiple lines with inconsistent indentation."""
    test_input = ("from pkg \\\n"
                  "    import stuff, other_suff \\\n"
                  "               more_stuff")
    assert SortImports(file_contents=test_input).output == ("from pkg import more_stuff, other_suff, stuff\n")

    # test again with a custom configuration
    custom_configuration = {'force_single_line': True,
                            'line_length': 120,
                            'known_first_party': ['asdf', 'qwer'],
                            'default_section': 'THIRDPARTY',
                            'forced_separate': 'asdf'}
    expected_output = ("from pkg import more_stuff\n"
                       "from pkg import other_suff\n"
                       "from pkg import stuff\n")
    assert SortImports(file_contents=test_input, **custom_configuration).output == expected_output


def test_atomic_mode():
    # without syntax error, everything works OK
    test_input = ("from b import d, c\n"
                  "from a import f, e\n")
    assert SortImports(file_contents=test_input, atomic=True).output == ("from a import e, f\n"
                                                                          "from b import c, d\n")

    # with syntax error content is not changed
    test_input += "while True print 'Hello world'" # blatant syntax error
    assert SortImports(file_contents=test_input, atomic=True).output == test_input


def test_order_by_type():
    test_input = "from module import Class, CONSTANT, function"
    assert SortImports(file_contents=test_input,
                       order_by_type=True).output == ("from module import CONSTANT, Class, function\n")

    # More complex sample data
    test_input = "from module import Class, CONSTANT, function, BASIC, Apple"
    assert SortImports(file_contents=test_input,
                       order_by_type=True).output == ("from module import BASIC, CONSTANT, Apple, Class, function\n")

    # Really complex sample data, to verify we don't mess with top level imports, only nested ones
    test_input = ("import StringIO\n"
                  "import glob\n"
                  "import os\n"
                  "import shutil\n"
                  "import tempfile\n"
                  "import time\n"
                  "from subprocess import PIPE, Popen, STDOUT\n")

    assert SortImports(file_contents=test_input, order_by_type=True).output == \
                ("import glob\n"
                 "import os\n"
                 "import shutil\n"
                 "import StringIO\n"
                 "import tempfile\n"
                 "import time\n"
                 "from subprocess import PIPE, STDOUT, Popen\n")


def test_custom_lines_after_import_section():
    """Test the case where the number of lines to output after imports has been explicitly set."""
    test_input = ("from a import b\n"
                  "foo = 'bar'\n")

    # default case is one space if not method or class after imports
    assert SortImports(file_contents=test_input).output == ("from a import b\n"
                                                            "\n"
                                                            "foo = 'bar'\n")

    # test again with a custom number of lines after the import section
    assert SortImports(file_contents=test_input, lines_after_imports=2).output == ("from a import b\n"
                                                                                   "\n"
                                                                                   "\n"
                                                                                   "foo = 'bar'\n")


def test_smart_lines_after_import_section():
    """Tests the default 'smart' behavior for dealing with lines after the import section"""
    # one space if not method or class after imports
    test_input = ("from a import b\n"
                  "foo = 'bar'\n")
    assert SortImports(file_contents=test_input).output == ("from a import b\n"
                                                            "\n"
                                                            "foo = 'bar'\n")

    # two spaces if a method or class after imports
    test_input = ("from a import b\n"
                  "def my_function():\n"
                  "    pass\n")
    assert SortImports(file_contents=test_input).output == ("from a import b\n"
                                                            "\n"
                                                            "\n"
                                                            "def my_function():\n"
                                                            "    pass\n")

    # two spaces if a method or class after imports - even if comment before function
    test_input = ("from a import b\n"
                  "# comment should be ignored\n"
                  "def my_function():\n"
                  "    pass\n")
    assert SortImports(file_contents=test_input).output == ("from a import b\n"
                                                            "\n"
                                                            "\n"
                                                            "# comment should be ignored\n"
                                                            "def my_function():\n"
                                                            "    pass\n")

    # ensure logic works with both style comments
    test_input = ("from a import b\n"
                  '"""\n'
                  "    comment should be ignored\n"
                  '"""\n'
                  "def my_function():\n"
                  "    pass\n")
    assert SortImports(file_contents=test_input).output == ("from a import b\n"
                                                            "\n"
                                                            "\n"
                                                            '"""\n'
                                                            "    comment should be ignored\n"
                                                            '"""\n'
                                                            "def my_function():\n"
                                                            "    pass\n")


def test_settings_combine_instead_of_overwrite():
    """Test to ensure settings combine logically, instead of fully overwriting."""
    assert set(SortImports(known_standard_library=['not_std_library']).config['known_standard_library']) == \
           set(SortImports().config['known_standard_library'] + ['not_std_library'])

    assert set(SortImports(not_known_standard_library=['thread']).config['known_standard_library']) == \
           set(item for item in SortImports().config['known_standard_library'] if item != 'thread')


def test_combined_from_and_as_imports():
    """Test to ensure it's possible to combine from and as imports."""
    test_input = ("from translate.misc.multistring import multistring\n"
                  "from translate.storage import base, factory\n"
                  "from translate.storage.placeables import general, parse as rich_parse\n")
    assert SortImports(file_contents=test_input, combine_as_imports=True).output == test_input


def test_as_imports_with_line_length():
    """Test to ensure it's possible to combine from and as imports."""
    test_input = ("from translate.storage import base as storage_base\n"
                  "from translate.storage.placeables import general, parse as rich_parse\n")
    assert SortImports(file_contents=test_input, combine_as_imports=False, line_length=40).output == \
                  ("from translate. \\\n    storage import base as storage_base\n"
                  "from translate.storage. \\\n    placeables import parse as rich_parse\n"
                  "from translate.storage. \\\n    placeables import general\n")


def test_keep_comments():
    """Test to ensure isort properly keeps comments in tact after sorting."""
    # Straight Import
    test_input = ("import foo  # bar\n")
    assert SortImports(file_contents=test_input, combine_as_imports=True).output == test_input

    # Star import
    test_input_star = ("from foo import *  # bar\n")
    assert SortImports(file_contents=test_input_star, combine_as_imports=True).output == test_input_star

    # Force Single Line From Import
    test_input = ("from foo import bar  # comment\n")
    assert SortImports(file_contents=test_input, combine_as_imports=True, force_single_line=True).output == test_input

    # From import
    test_input = ("from foo import bar  # My Comment\n")
    assert SortImports(file_contents=test_input, combine_as_imports=True).output == test_input

    # More complicated case
    test_input = ("from a import b  # My Comment1\n"
                  "from a import c  # My Comment2\n")
    assert SortImports(file_contents=test_input, combine_as_imports=True).output == \
                      ("from a import b  # My Comment1\n"
                       "from a import c  # My Comment2\n")

    # Test case where imports comments make imports extend pass the line length
    test_input = ("from a import b # My Comment1\n"
                  "from a import c # My Comment2\n"
                  "from a import d\n")
    assert SortImports(file_contents=test_input, combine_as_imports=True, line_length=45).output == \
                      ("from a import b  # My Comment1\n"
                       "from a import c  # My Comment2\n"
                       "from a import d\n")

    # Test case where imports with comments will be beyond line length limit
    test_input = ("from a import b, c  # My Comment1\n"
                  "from a import c, d # My Comment2 is really really really really long\n")
    assert SortImports(file_contents=test_input, combine_as_imports=True, line_length=45).output == \
                      ("from a import (b,  # My Comment1; My Comment2 is really really really really long\n"
                       "               c, d)\n")


def test_multiline_split_on_dot():
    """Test to ensure isort correctly handles multiline imports, even when split right after a '.'"""
    test_input = ("from my_lib.my_package.test.level_1.level_2.level_3.level_4.level_5.\\\n"
                  "    my_module import my_function")
    assert SortImports(file_contents=test_input, line_length=70).output == \
            ("from my_lib.my_package.test.level_1.level_2.level_3.level_4.level_5. \\\n"
             "    my_module import my_function\n")


def test_import_star():
    """Test to ensure isort handles star imports correctly"""
    test_input = ("from blah import *\n"
                  "from blah import _potato\n")
    assert SortImports(file_contents=test_input).output == ("from blah import *\n"
                                                            "from blah import _potato\n")
    assert SortImports(file_contents=test_input, combine_star=True).output == ("from blah import *\n")


def test_similar_to_std_library():
    """Test to ensure modules that are named similarly to a standard library import don't end up clobbered"""
    test_input = ("import datetime\n"
                  "\n"
                  "import requests\n"
                  "import times\n")
    assert SortImports(file_contents=test_input, known_third_party=["requests", "times"]).output == test_input


def test_correctly_placed_imports():
    """Test to ensure comments stay on correct placement after being sorted"""
    test_input = ("from a import b # comment for b\n"
                  "from a import c # comment for c\n")
    assert SortImports(file_contents=test_input, force_single_line=True).output == \
                      ("from a import b  # comment for b\n"
                       "from a import c  # comment for c\n")
    assert SortImports(file_contents=test_input).output == ("from a import b  # comment for b\n"
                                                            "from a import c  # comment for c\n")

    # Full example test from issue #143
    test_input = ("from itertools import chain\n"
                  "\n"
                  "from django.test import TestCase\n"
                  "from model_mommy import mommy\n"
                  "\n"
                  "from apps.clientman.commands.download_usage_rights import associate_right_for_item_product\n"
                  "from apps.clientman.commands.download_usage_rights import associate_right_for_item_product_d"
                  "efinition\n"
                  "from apps.clientman.commands.download_usage_rights import associate_right_for_item_product_d"
                  "efinition_platform\n"
                  "from apps.clientman.commands.download_usage_rights import associate_right_for_item_product_p"
                  "latform\n"
                  "from apps.clientman.commands.download_usage_rights import associate_right_for_territory_reta"
                  "il_model\n"
                  "from apps.clientman.commands.download_usage_rights import associate_right_for_territory_reta"
                  "il_model_definition_platform_provider  # noqa\n"
                  "from apps.clientman.commands.download_usage_rights import clear_right_for_item_product\n"
                  "from apps.clientman.commands.download_usage_rights import clear_right_for_item_product_defini"
                  "tion\n"
                  "from apps.clientman.commands.download_usage_rights import clear_right_for_item_product_defini"
                  "tion_platform\n"
                  "from apps.clientman.commands.download_usage_rights import clear_right_for_item_product_platfo"
                  "rm\n"
                  "from apps.clientman.commands.download_usage_rights import clear_right_for_territory_retail_mo"
                  "del\n"
                  "from apps.clientman.commands.download_usage_rights import clear_right_for_territory_retail_mo"
                  "del_definition_platform_provider  # noqa\n"
                  "from apps.clientman.commands.download_usage_rights import create_download_usage_right\n"
                  "from apps.clientman.commands.download_usage_rights import delete_download_usage_right\n"
                  "from apps.clientman.commands.download_usage_rights import disable_download_for_item_product\n"
                  "from apps.clientman.commands.download_usage_rights import disable_download_for_item_product_d"
                  "efinition\n"
                  "from apps.clientman.commands.download_usage_rights import disable_download_for_item_product_d"
                  "efinition_platform\n"
                  "from apps.clientman.commands.download_usage_rights import disable_download_for_item_product_p"
                  "latform\n"
                  "from apps.clientman.commands.download_usage_rights import disable_download_for_territory_reta"
                  "il_model\n"
                  "from apps.clientman.commands.download_usage_rights import disable_download_for_territory_reta"
                  "il_model_definition_platform_provider  # noqa\n"
                  "from apps.clientman.commands.download_usage_rights import get_download_rights_for_item\n"
                  "from apps.clientman.commands.download_usage_rights import get_right\n")
    assert SortImports(file_contents=test_input, force_single_line=True, line_length=140,
                       known_third_party=["django", "model_mommy"]).output == test_input


def test_auto_detection():
    """Initial test to ensure isort auto-detection works correctly - will grow over time as new issues are raised."""

    # Issue 157
    test_input = ("import binascii\n"
                  "import os\n"
                  "\n"
                  "import cv2\n"
                  "import requests\n")
    assert SortImports(file_contents=test_input, known_third_party=["cv2", "requests"]).output == test_input

    # alternative solution
    assert SortImports(file_contents=test_input, default_section="THIRDPARTY").output == test_input

########NEW FILE########
