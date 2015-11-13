__FILENAME__ = conf
# -*- coding: utf-8 -*-
#
# django-sekizai documentation build configuration file, created by
# sphinx-quickstart on Tue Jun 29 23:12:20 2010.
#
# This file is execfile()d with the current directory set to its containing dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out
# serve to show the default.

import sys, os

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#sys.path.append(os.path.abspath('.'))

# -- General configuration -----------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be extensions
# coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = []

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The encoding of source files.
#source_encoding = 'utf-8'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = u'django-sekizai'
copyright = u'2010, Jonas Obrist'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = '0.6'
# The full version, including alpha/beta/rc tags.
release = '0.6.1'

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#language = None

# There are two options for replacing |today|: either, you set today to some
# non-false value, then it is used:
#today = ''
# Else, today_fmt is used as the format for a strftime call.
#today_fmt = '%B %d, %Y'

# List of documents that shouldn't be included in the build.
#unused_docs = []

# List of directories, relative to source directory, that shouldn't be searched
# for source files.
exclude_trees = ['_build']

# The reST default role (used for this markup: `text`) to use for all documents.
#default_role = None

# If true, '()' will be appended to :func: etc. cross-reference text.
#add_function_parentheses = True

# If true, the current module name will be prepended to all description
# unit titles (such as .. function::).
#add_module_names = True

# If true, sectionauthor and moduleauthor directives will be shown in the
# output. They are ignored by default.
#show_authors = False

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# A list of ignored prefixes for module index sorting.
#modindex_common_prefix = []


# -- Options for HTML output ---------------------------------------------------

# The theme to use for HTML and HTML Help pages.  Major themes that come with
# Sphinx are currently 'default' and 'sphinxdoc'.
html_theme = 'default'

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
#html_theme_options = {}

# Add any paths that contain custom themes here, relative to this directory.
#html_theme_path = []

# The name for this set of Sphinx documents.  If None, it defaults to
# "<project> v<release> documentation".
#html_title = None

# A shorter title for the navigation bar.  Default is the same as html_title.
#html_short_title = None

# The name of an image file (relative to this directory) to place at the top
# of the sidebar.
#html_logo = None

# The name of an image file (within the static path) to use as favicon of the
# docs.  This file should be a Windows icon file (.ico) being 16x16 or 32x32
# pixels large.
#html_favicon = None

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# If not '', a 'Last updated on:' timestamp is inserted at every page bottom,
# using the given strftime format.
#html_last_updated_fmt = '%b %d, %Y'

# If true, SmartyPants will be used to convert quotes and dashes to
# typographically correct entities.
#html_use_smartypants = True

# Custom sidebar templates, maps document names to template names.
#html_sidebars = {}

# Additional templates that should be rendered to pages, maps page names to
# template names.
#html_additional_pages = {}

# If false, no module index is generated.
#html_use_modindex = True

# If false, no index is generated.
#html_use_index = True

# If true, the index is split into individual pages for each letter.
#html_split_index = False

# If true, links to the reST sources are added to the pages.
#html_show_sourcelink = True

# If true, an OpenSearch description file will be output, and all pages will
# contain a <link> tag referring to it.  The value of this option must be the
# base URL from which the finished HTML is served.
#html_use_opensearch = ''

# If nonempty, this is the file name suffix for HTML files (e.g. ".xhtml").
#html_file_suffix = ''

# Output file base name for HTML help builder.
htmlhelp_basename = 'django-sekizaidoc'


# -- Options for LaTeX output --------------------------------------------------

# The paper size ('letter' or 'a4').
#latex_paper_size = 'letter'

# The font size ('10pt', '11pt' or '12pt').
#latex_font_size = '10pt'

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass [howto/manual]).
latex_documents = [
  ('index', 'django-sekizai.tex', u'django-sekizai Documentation',
   u'Jonas Obrist', 'manual'),
]

# The name of an image file (relative to this directory) to place at the top of
# the title page.
#latex_logo = None

# For "manual" documents, if this is true, then toplevel headings are parts,
# not chapters.
#latex_use_parts = False

# Additional stuff for the LaTeX preamble.
#latex_preamble = ''

# Documents to append as an appendix to all manuals.
#latex_appendices = []

# If false, no module index is generated.
#latex_use_modindex = True

########NEW FILE########
__FILENAME__ = runtests
# -*- coding: utf-8 -*-
import os
import sys

urlpatterns = []

TEMPLATE_DEBUG = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:'
    }
}


INSTALLED_APPS = [
    'sekizai',
]

TEMPLATE_DIRS = [
    os.path.join(os.path.dirname(__file__), 'sekizai', 'test_templates'),
]

TEMPLATE_CONTEXT_PROCESSORS = [
    'sekizai.context_processors.sekizai',
]
    

ROOT_URLCONF = 'runtests'

def runtests():
    from django.conf import settings
    settings.configure(
        INSTALLED_APPS = INSTALLED_APPS,
        ROOT_URLCONF = ROOT_URLCONF,
        DATABASES = DATABASES,
        TEST_RUNNER = 'django.test.simple.DjangoTestSuiteRunner',
        TEMPLATE_DIRS = TEMPLATE_DIRS,
        TEMPLATE_CONTEXT_PROCESSORS = TEMPLATE_CONTEXT_PROCESSORS,
        TEMPLATE_DEBUG = TEMPLATE_DEBUG
    )

    # Run the test suite, including the extra validation tests.
    from django.test.utils import get_runner
    TestRunner = get_runner(settings)

    test_runner = TestRunner(verbosity=1, interactive=False, failfast=False)
    failures = test_runner.run_tests(INSTALLED_APPS)
    return failures

def main():
    failures = runtests()
    sys.exit(failures)


if __name__ == "__main__":
    main()

########NEW FILE########
__FILENAME__ = context
from django.template import Context
from sekizai.context_processors import sekizai

class SekizaiContext(Context):
    """
    An alternative context to be used instead of RequestContext in places where
    no request is available.
    """
    def __init__(self, *args, **kwargs):
        super(SekizaiContext, self).__init__(*args, **kwargs)
        self.update(sekizai())

########NEW FILE########
__FILENAME__ = context_processors
from sekizai.data import SekizaiDictionary
from sekizai.helpers import get_varname

def sekizai(request=None):
    """
    Simple context processor which makes sure that the SekizaiDictionary is
    available in all templates.
    """
    return {get_varname(): SekizaiDictionary()}

########NEW FILE########
__FILENAME__ = data
class SekizaiList(list):
    """
    A sekizai namespace in a template.
    """
    def __init__(self, namespace):
        self._namespace = namespace
        super(SekizaiList, self).__init__()

    def append(self, obj):
        """
        When content gets added, run the filters for this namespace.
        """
        if obj not in self:
            super(SekizaiList, self).append(obj)
        
    def render(self, between='\n'):
        """
        When the data get's rendered, run the postprocess filters.
        """
        return between.join(self)


class SekizaiDictionary(dict):
    """
    A dictionary which auto fills itself instead of raising key errors.
    """
    def __init__(self):
        super(SekizaiDictionary, self).__init__()

    def __getitem__(self, item):
        if item not in self:
            self[item] = SekizaiList(item)
        return super(SekizaiDictionary, self).__getitem__(item)

########NEW FILE########
__FILENAME__ = helpers
# -*- coding: utf-8 -*-
from django.conf import settings
from django.template import VariableNode, Variable
from django.template.loader import get_template
from django.template.loader_tags import BlockNode, ExtendsNode


def is_variable_extend_node(node):
    if hasattr(node, 'parent_name_expr') and node.parent_name_expr:
        return True
    if hasattr(node, 'parent_name') and hasattr(node.parent_name, 'filters'):
        if node.parent_name.filters or isinstance(node.parent_name.var, Variable):
            return True
    return False

def _extend_blocks(extend_node, blocks):
    """
    Extends the dictionary `blocks` with *new* blocks in the parent node (recursive)
    """
    # we don't support variable extensions
    if is_variable_extend_node(extend_node):
        return
    parent = extend_node.get_parent(None)
    # Search for new blocks
    for node in parent.nodelist.get_nodes_by_type(BlockNode):
        if not node.name in blocks:
            blocks[node.name] = node
        else:
            # set this node as the super node (for {{ block.super }})
            block = blocks[node.name]
            seen_supers = []
            while hasattr(block.super, 'nodelist') and block.super not in seen_supers:
                seen_supers.append(block.super)
                block = block.super
            block.super = node
    # search for further ExtendsNodes
    for node in parent.nodelist.get_nodes_by_type(ExtendsNode):
        _extend_blocks(node, blocks)
        break

def _extend_nodelist(extend_node):
    """
    Returns a list of namespaces found in the parent template(s) of this
    ExtendsNode
    """
    # we don't support variable extensions (1.3 way)
    if is_variable_extend_node(extend_node):
        return []
    blocks = extend_node.blocks
    _extend_blocks(extend_node, blocks)
    found = []

    for block in blocks.values():
        found += _scan_namespaces(block.nodelist, block, blocks.keys())

    parent_template = extend_node.get_parent({})
    # if this is the topmost template, check for namespaces outside of blocks
    if not parent_template.nodelist.get_nodes_by_type(ExtendsNode):
        found += _scan_namespaces(parent_template.nodelist, None, blocks.keys())
    else:
        found += _scan_namespaces(parent_template.nodelist, extend_node, blocks.keys())
    return found

def _scan_namespaces(nodelist, current_block=None, ignore_blocks=None):
    from sekizai.templatetags.sekizai_tags import RenderBlock
    if ignore_blocks is None:
        ignore_blocks = []
    found = []

    for node in nodelist:
        # check if this is RenderBlock node
        if isinstance(node, RenderBlock):
            # resolve it's name against a dummy context
            found.append(node.kwargs['name'].resolve({}))
            found += _scan_namespaces(node.blocks['nodelist'], node)
        # handle {% extends ... %} tags if check_inheritance is True
        elif isinstance(node, ExtendsNode):
            found += _extend_nodelist(node)
        # in block nodes we have to scan for super blocks
        elif isinstance(node, VariableNode) and current_block:
            if node.filter_expression.token == 'block.super':
                if hasattr(current_block.super, 'nodelist'):
                    found += _scan_namespaces(current_block.super.nodelist, current_block.super)
    return found

def get_namespaces(template):
    compiled_template = get_template(template)
    return _scan_namespaces(compiled_template.nodelist)

def validate_template(template, namespaces):
    """
    Validates that a template (or it's parents if check_inheritance is True)
    contain all given namespaces
    """
    if getattr(settings, 'SEKIZAI_IGNORE_VALIDATION', False):
        return True
    found = get_namespaces(template)
    for namespace in namespaces:
        if namespace not in found:
            return False
    return True

def get_varname():
    return getattr(settings, 'SEKIZAI_VARNAME', 'SEKIZAI_CONTENT_HOLDER')


class Watcher(object):
    """
    Watches a context for changes to the sekizai data, so it can be replayed later.
    This is useful for caching.

    NOTE: This class assumes you ONLY ADD, NEVER REMOVE data from the context!
    """
    def __init__(self, context):
        self.context = context
        self.frozen = dict((key, list(value)) for key, value in self.data.items())

    @property
    def data(self):
        return self.context.get(get_varname(), {})

    def get_changes(self):
        sfrozen = set(self.frozen)
        sdata = set(self.data)
        new_keys = sfrozen ^ sdata
        changes = {}
        for key in new_keys:
            changes[key] = list(self.data[key])
        shared_keys = sfrozen & sdata
        for key in shared_keys:
            old_set = set(self.frozen[key])
            new_values = [item for item in self.data[key] if item not in old_set]
            changes[key] = new_values
        return changes



########NEW FILE########
__FILENAME__ = models

########NEW FILE########
__FILENAME__ = sekizai_tags
from classytags.arguments import Argument, Flag
from classytags.core import Tag, Options
from classytags.parser import Parser
from django import template
from django.conf import settings
from django.utils.importlib import import_module
from sekizai.helpers import get_varname

register = template.Library()

def validate_context(context):
    """
    Validates a given context.
    
    Returns True if the context is valid.
    
    Returns False if the context is invalid but the error should be silently
    ignored.
    
    Raises a TemplateSyntaxError if the context is invalid and we're in debug
    mode.
    """
    if get_varname() in context:
        return True
    if not settings.TEMPLATE_DEBUG:
        return False
    raise template.TemplateSyntaxError(
        "You must enable the 'sekizai.context_processors.sekizai' template "
        "context processor or use 'sekizai.context.SekizaiContext' to "
        "render your templates."
    )

def import_processor(import_path):
    if '.' not in import_path:
        raise TypeError("Import paths must contain at least one '.'")
    module_name, object_name = import_path.rsplit('.', 1)
    module = import_module(module_name)
    return getattr(module, object_name)


class SekizaiParser(Parser):
    def parse_blocks(self):
        super(SekizaiParser, self).parse_blocks()
        self.blocks['nodelist'] = self.parser.parse()


class AddtoblockParser(Parser):
    def parse_blocks(self):
        name = self.kwargs['name'].var.token
        self.blocks['nodelist'] = self.parser.parse(
            ('endaddtoblock', 'endaddtoblock %s' % name)
        )
        self.parser.delete_first_token()


class SekizaiTag(Tag):
    def render(self, context):
        if validate_context(context):
            return super(SekizaiTag, self).render(context)
        return ''


class RenderBlock(Tag):
    name = 'render_block'
    
    options = Options(
        Argument('name'),
        'postprocessor',
        Argument('postprocessor', required=False, default=None, resolve=False),
        parser_class=SekizaiParser,
    )
        
    def render_tag(self, context, name, postprocessor, nodelist):
        if not validate_context(context):
            return nodelist.render(context)
        rendered_contents = nodelist.render(context)
        varname = get_varname()
        data = context[varname][name].render()
        if postprocessor:
            func = import_processor(postprocessor)
            data = func(context, data, name)
        return '%s\n%s' % (data, rendered_contents)
register.tag(RenderBlock)


class AddData(SekizaiTag):
    name = 'add_data'
    
    options = Options(
        Argument('key'),
        Argument('value'),
    )
    
    def render_tag(self, context, key, value):
        varname = get_varname()
        context[varname][key].append(value)
        return ''
register.tag(AddData)


class WithData(SekizaiTag):
    name = 'with_data'
    
    options = Options(
        Argument('name'),
        'as', 
        Argument('variable', resolve=False),
        blocks=[
            ('end_with_data', 'inner_nodelist'),
        ],
        parser_class=SekizaiParser,
    )
    
    def render_tag(self, context, name, variable, inner_nodelist, nodelist):
        rendered_contents = nodelist.render(context)
        varname = get_varname()
        data = context[varname][name]
        context.push()
        context[variable] = data
        inner_contents = inner_nodelist.render(context)
        context.pop()
        return '%s\n%s' % (inner_contents, rendered_contents)
register.tag(WithData)


class Addtoblock(SekizaiTag):
    name = 'addtoblock'
    
    options = Options(
        Argument('name'),
        Flag('strip', default=False, true_values=['strip']),
        parser_class=AddtoblockParser,
    )
    
    def render_tag(self, context, name, strip, nodelist):
        rendered_contents = nodelist.render(context)
        if strip:
            rendered_contents = rendered_contents.strip()
        varname = get_varname()
        context[varname][name].append(rendered_contents)
        return ""
register.tag(Addtoblock)

########NEW FILE########
__FILENAME__ = tests
from __future__ import with_statement
from difflib import SequenceMatcher
from django import template
from django.conf import settings
from django.template.loader import render_to_string
from sekizai.context import SekizaiContext
from sekizai.helpers import validate_template, get_namespaces, Watcher, get_varname
from sekizai.templatetags.sekizai_tags import (validate_context, 
    import_processor)
from unittest import TestCase

try:
    unicode_compat = unicode
except NameError:
    unicode_compat = str


def null_processor(context, data, namespace):
    return ''

def namespace_processor(context, data, namespace):
    return namespace


class SettingsOverride(object):
    """
    Overrides Django settings within a context and resets them to their inital
    values on exit.
    
    Example:
    
        with SettingsOverride(DEBUG=True):
            # do something
    """
    class NULL: pass
    
    def __init__(self, **overrides):
        self.overrides = overrides
        
    def __enter__(self):
        self.old = {}
        for key, value in self.overrides.items():
            self.old[key] = getattr(settings, key, self.NULL)
            setattr(settings, key, value)
        
    def __exit__(self, type, value, traceback):
        for key, value in self.old.items():
            if value is self.NULL:
                delattr(settings, key)
            else:
                setattr(settings, key, value)


class Match(tuple): # pragma: no cover
    @property
    def a(self):
        return self[0]
    
    @property
    def b(self):
        return self[1]
    
    @property
    def size(self):
        return self[2]


def _backwards_compat_match(thing): # pragma: no cover
    if isinstance(thing, tuple):
        return Match(thing)
    return thing

class BitDiffResult(object):
    def __init__(self, status, message):
        self.status = status
        self.message = message


class BitDiff(object):
    """
    Visual aid for failing tests
    """
    def __init__(self, expected):
        self.expected = [repr(unicode_compat(bit)) for bit in expected]
        
    def test(self, result):
        result = [repr(unicode_compat(bit)) for bit in result]
        if self.expected == result:
            return BitDiffResult(True, "success")
        else: # pragma: no cover
            longest = max([len(x) for x in self.expected] + [len(x) for x in result] + [len('Expected')])
            sm = SequenceMatcher()
            sm.set_seqs(self.expected, result)
            matches = sm.get_matching_blocks()
            lasta = 0
            lastb = 0
            data = []
            for match in [_backwards_compat_match(match) for match in matches]:
                unmatcheda = self.expected[lasta:match.a]
                unmatchedb = result[lastb:match.b]
                unmatchedlen = max([len(unmatcheda), len(unmatchedb)])
                unmatcheda += ['' for x in range(unmatchedlen)]
                unmatchedb += ['' for x in range(unmatchedlen)]
                for i in range(unmatchedlen):
                    data.append((False, unmatcheda[i], unmatchedb[i]))
                for i in range(match.size):
                    data.append((True, self.expected[match.a + i], result[match.b + i]))
                lasta = match.a + match.size
                lastb = match.b + match.size
            padlen = (longest - len('Expected'))
            padding = ' ' * padlen
            line1 = '-' * padlen
            line2 = '-' * (longest - len('Result'))
            msg = '\nExpected%s |   | Result' % padding
            msg += '\n--------%s-|---|-------%s' % (line1, line2)
            for success, a, b in data:
                pad = ' ' * (longest - len(a))
                if success:
                    msg += '\n%s%s |   | %s' % (a, pad, b)
                else:
                    msg += '\n%s%s | ! | %s' % (a, pad, b)
            return BitDiffResult(False, msg)


class SekizaiTestCase(TestCase):
    def _render(self, tpl, ctx={}, ctxclass=SekizaiContext):
        return render_to_string(tpl, ctxclass(ctx))
    
    def _get_bits(self, tpl, ctx={}, ctxclass=SekizaiContext):
        rendered = self._render(tpl, ctx, ctxclass)
        bits = [bit for bit in [bit.strip('\n') for bit in rendered.split('\n')] if bit]
        return bits, rendered
        
    def _test(self, tpl, res, ctx={}, ctxclass=SekizaiContext):
        """
        Helper method to render template and compare it's bits
        """
        bits, rendered = self._get_bits(tpl, ctx, ctxclass)
        differ = BitDiff(res)
        result = differ.test(bits)
        self.assertTrue(result.status, result.message)
        return rendered
        
    def test_basic_dual_block(self):
        """
        Basic dual block testing
        """
        bits = ['my css file', 'some content', 'more content', 
            'final content', 'my js file']
        self._test('basic.html', bits)

    def test_named_endaddtoblock(self):
        """
        Testing with named endaddblock
        """
        bits = ["mycontent"]
        self._test('named_end.html', bits)

    def test_eat_content_before_render_block(self):
        """
        Testing that content get's eaten if no render_blocks is available
        """
        bits = ["mycontent"]
        self._test("eat.html", bits)
        
    def test_sekizai_context_required(self):
        """
        Test that the template tags properly fail if not used with either 
        SekizaiContext or the context processor.
        """
        self.assertRaises(template.TemplateSyntaxError, self._render, 'basic.html', {}, template.Context)
        
    def test_complex_template_inheritance(self):
        """
        Test that (complex) template inheritances work properly
        """
        bits = [
            "head start",
            "some css file",
            "head end",
            "include start",
            "inc add js",
            "include end",
            "block main start",
            "extinc",
            "block main end",
            "body pre-end",
            "inc js file",
            "body end"
        ]
        self._test("inherit/extend.html", bits)
        """
        Test that blocks (and block.super) work properly with sekizai
        """
        bits = [
            "head start",
            "visible css file",
            "some css file",
            "head end",
            "include start",
            "inc add js",
            "include end",
            "block main start",
            "block main base contents",
            "more contents",
            "block main end",
            "body pre-end",
            "inc js file",
            "body end"
        ]
        self._test("inherit/super_blocks.html", bits)
        
    def test_namespace_isolation(self):
        """
        Tests that namespace isolation works
        """
        bits = ["the same file", "the same file"]
        self._test('namespaces.html', bits)
        
    def test_variable_namespaces(self):
        """
        Tests variables and filtered variables as block names.
        """
        bits = ["file one", "file two"]
        self._test('variables.html', bits, {'blockname': 'one'})

    def test_invalid_addtoblock(self):
        """
        Tests that template syntax errors are raised properly in templates
        rendered by sekizai tags
        """
        self.assertRaises(template.TemplateSyntaxError, self._render, 'errors/failadd.html')
    
    def test_invalid_renderblock(self):
        self.assertRaises(template.TemplateSyntaxError, self._render, 'errors/failrender.html')
    
    def test_invalid_include(self):
        self.assertRaises(template.TemplateSyntaxError, self._render, 'errors/failinc.html')
        
    def test_invalid_basetemplate(self):
        self.assertRaises(template.TemplateSyntaxError, self._render, 'errors/failbase.html')
        
    def test_invalid_basetemplate_two(self):
        self.assertRaises(template.TemplateSyntaxError, self._render, 'errors/failbase2.html')
        
    def test_with_data(self):
        """
        Tests the with_data/add_data tags.
        """
        bits = ["1", "2"]
        self._test('with_data.html', bits)
        
    def test_easy_inheritance(self):
        self.assertEqual('content', self._render("easy_inherit.html").strip())
        
    def test_validate_context(self):
        sekizai_ctx = SekizaiContext()
        django_ctx = template.Context()
        self.assertRaises(template.TemplateSyntaxError, validate_context, django_ctx)
        self.assertEqual(validate_context(sekizai_ctx), True)
        with SettingsOverride(TEMPLATE_DEBUG=False):
            self.assertEqual(validate_context(django_ctx), False)
            self.assertEqual(validate_context(sekizai_ctx), True)
            bits = ['some content', 'more content', 'final content']
            self._test('basic.html', bits, ctxclass=template.Context)
            
    def test_post_processor_null(self):
        bits = ['header', 'footer']
        self._test('processors/null.html', bits)
            
    def test_post_processor_namespace(self):
        bits = ['header', 'footer', 'js']
        self._test('processors/namespace.html', bits)
        
    def test_import_processor_failfast(self):
        self.assertRaises(TypeError, import_processor, 'invalidpath')
        
    def test_unique(self):
        bits = ['unique data']
        self._test('unique.html', bits)

    def test_strip(self):
        tpl = template.Template("""
            {% load sekizai_tags %}
            {% addtoblock 'a' strip %} test{% endaddtoblock %}
            {% addtoblock 'a' strip %}test {% endaddtoblock %}
            {% render_block 'a' %}""")
        context = SekizaiContext()
        output = tpl.render(context)
        self.assertEqual(output.count('test'), 1, output)


class HelperTests(TestCase):
    def test_validate_template_js_css(self):
        self.assertTrue(validate_template('basic.html', ['js', 'css']))
    
    def test_validate_template_js(self):
        self.assertTrue(validate_template('basic.html', ['js']))
        
    def test_validate_template_css(self):
        self.assertTrue(validate_template('basic.html', ['css']))
        
    def test_validate_template_empty(self):
        self.assertTrue(validate_template('basic.html', []))
        
    def test_validate_template_notfound(self):
        self.assertFalse(validate_template('basic.html', ['notfound']))

    def test_get_namespaces_easy_inherit(self):
        self.assertEqual(get_namespaces('easy_inherit.html'), ['css'])

    def test_get_namespaces_chain_inherit(self):
        self.assertEqual(get_namespaces('inherit/chain.html'), ['css', 'js'])

    def test_get_namespaces_space_chain_inherit(self):
        self.assertEqual(get_namespaces('inherit/spacechain.html'), ['css', 'js'])

    def test_get_namespaces_var_inherit(self):
        self.assertEqual(get_namespaces('inherit/varchain.html'), [])

    def test_get_namespaces_sub_var_inherit(self):
        self.assertEqual(get_namespaces('inherit/subvarchain.html'), [])

    def test_get_namespaces_null_ext(self):
        self.assertEqual(get_namespaces('inherit/nullext.html'), [])
        
    def test_deactivate_validate_template(self):
        with SettingsOverride(SEKIZAI_IGNORE_VALIDATION=True):
            self.assertTrue(validate_template('basic.html', ['js', 'css']))
            self.assertTrue(validate_template('basic.html', ['js']))
            self.assertTrue(validate_template('basic.html', ['css']))
            self.assertTrue(validate_template('basic.html', []))
            self.assertTrue(validate_template('basic.html', ['notfound']))

    def test_watcher_add_namespace(self):
        context = SekizaiContext()
        watcher = Watcher(context)
        varname = get_varname()
        context[varname]['key'].append('value')
        changes = watcher.get_changes()
        self.assertEqual(changes, {'key': ['value']})

    def test_watcher_add_data(self):
        context = SekizaiContext()
        varname = get_varname()
        context[varname]['key'].append('value')
        watcher = Watcher(context)
        context[varname]['key'].append('value2')
        changes = watcher.get_changes()
        self.assertEqual(changes, {'key': ['value2']})

########NEW FILE########
