__FILENAME__ = conf
# -*- coding: utf-8 -*-
#
# flask-testing documentation build configuration file, created by
# sphinx-quickstart on Wed Jun 23 08:26:41 2010.
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
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath('_themes'))

# -- General configuration -----------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be extensions
# coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = ['sphinx.ext.autodoc', 'sphinx.ext.intersphinx']

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The encoding of source files.
#source_encoding = 'utf-8-sig'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = u'Flask-Testing'
copyright = u'2010, Dan Jacob'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = '0.3'
# The full version, including alpha/beta/rc tags.
release = '0.3'

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#language = None

# There are two options for replacing |today|: either, you set today to some
# non-false value, then it is used:
#today = ''
# Else, today_fmt is used as the format for a strftime call.
#today_fmt = '%B %d, %Y'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ['_build']

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
#pygments_style = 'sphinx'

# A list of ignored prefixes for module index sorting.
#modindex_common_prefix = []


# -- Options for HTML output ---------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
html_theme = 'flask_small'

html_theme_options = {
     'index_logo': 'flask-testing.png',
     'github_fork': 'jarus/flask-testing'
}
# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
#html_theme_options = {}

# Add any paths that contain custom themes here, relative to this directory.
html_theme_path = ['_themes']

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
#html_domain_indices = True

# If false, no index is generated.
#html_use_index = True

# If true, the index is split into individual pages for each letter.
#html_split_index = False

# If true, links to the reST sources are added to the pages.
#html_show_sourcelink = True

# If true, "Created using Sphinx" is shown in the HTML footer. Default is True.
#html_show_sphinx = True

# If true, "(C) Copyright ..." is shown in the HTML footer. Default is True.
#html_show_copyright = True

# If true, an OpenSearch description file will be output, and all pages will
# contain a <link> tag referring to it.  The value of this option must be the
# base URL from which the finished HTML is served.
#html_use_opensearch = ''

# If nonempty, this is the file name suffix for HTML files (e.g. ".xhtml").
#html_file_suffix = ''

# Output file base name for HTML help builder.
htmlhelp_basename = 'flask-testingdoc'


# -- Options for LaTeX output --------------------------------------------------

# The paper size ('letter' or 'a4').
#latex_paper_size = 'letter'

# The font size ('10pt', '11pt' or '12pt').
#latex_font_size = '10pt'

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass [howto/manual]).
latex_documents = [
  ('index', 'flask-testing.tex', u'Flask-Testing Documentation',
   u'Dan Jacob', 'manual'),
]

# The name of an image file (relative to this directory) to place at the top of
# the title page.
#latex_logo = None

# For "manual" documents, if this is true, then toplevel headings are parts,
# not chapters.
#latex_use_parts = False

# If true, show page references after internal links.
#latex_show_pagerefs = False

# If true, show URL addresses after external links.
#latex_show_urls = False

# Additional stuff for the LaTeX preamble.
#latex_preamble = ''

# Documents to append as an appendix to all manuals.
#latex_appendices = []

# If false, no module index is generated.
#latex_domain_indices = True


# -- Options for manual page output --------------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    ('index', 'flask-testing', u'Flask-Testing Documentation',
     [u'Dan Jacob'], 1)
]

########NEW FILE########
__FILENAME__ = flask_theme_support
# flasky extensions.  flasky pygments style based on tango style
from pygments.style import Style
from pygments.token import Keyword, Name, Comment, String, Error, \
     Number, Operator, Generic, Whitespace, Punctuation, Other, Literal


class FlaskyStyle(Style):
    background_color = "#f8f8f8"
    default_style = ""

    styles = {
        # No corresponding class for the following:
        #Text:                     "", # class:  ''
        Whitespace:                "underline #f8f8f8",      # class: 'w'
        Error:                     "#a40000 border:#ef2929", # class: 'err'
        Other:                     "#000000",                # class 'x'

        Comment:                   "italic #8f5902", # class: 'c'
        Comment.Preproc:           "noitalic",       # class: 'cp'

        Keyword:                   "bold #004461",   # class: 'k'
        Keyword.Constant:          "bold #004461",   # class: 'kc'
        Keyword.Declaration:       "bold #004461",   # class: 'kd'
        Keyword.Namespace:         "bold #004461",   # class: 'kn'
        Keyword.Pseudo:            "bold #004461",   # class: 'kp'
        Keyword.Reserved:          "bold #004461",   # class: 'kr'
        Keyword.Type:              "bold #004461",   # class: 'kt'

        Operator:                  "#582800",   # class: 'o'
        Operator.Word:             "bold #004461",   # class: 'ow' - like keywords

        Punctuation:               "bold #000000",   # class: 'p'

        # because special names such as Name.Class, Name.Function, etc.
        # are not recognized as such later in the parsing, we choose them
        # to look the same as ordinary variables.
        Name:                      "#000000",        # class: 'n'
        Name.Attribute:            "#c4a000",        # class: 'na' - to be revised
        Name.Builtin:              "#004461",        # class: 'nb'
        Name.Builtin.Pseudo:       "#3465a4",        # class: 'bp'
        Name.Class:                "#000000",        # class: 'nc' - to be revised
        Name.Constant:             "#000000",        # class: 'no' - to be revised
        Name.Decorator:            "#888",           # class: 'nd' - to be revised
        Name.Entity:               "#ce5c00",        # class: 'ni'
        Name.Exception:            "bold #cc0000",   # class: 'ne'
        Name.Function:             "#000000",        # class: 'nf'
        Name.Property:             "#000000",        # class: 'py'
        Name.Label:                "#f57900",        # class: 'nl'
        Name.Namespace:            "#000000",        # class: 'nn' - to be revised
        Name.Other:                "#000000",        # class: 'nx'
        Name.Tag:                  "bold #004461",   # class: 'nt' - like a keyword
        Name.Variable:             "#000000",        # class: 'nv' - to be revised
        Name.Variable.Class:       "#000000",        # class: 'vc' - to be revised
        Name.Variable.Global:      "#000000",        # class: 'vg' - to be revised
        Name.Variable.Instance:    "#000000",        # class: 'vi' - to be revised

        Number:                    "#990000",        # class: 'm'

        Literal:                   "#000000",        # class: 'l'
        Literal.Date:              "#000000",        # class: 'ld'

        String:                    "#4e9a06",        # class: 's'
        String.Backtick:           "#4e9a06",        # class: 'sb'
        String.Char:               "#4e9a06",        # class: 'sc'
        String.Doc:                "italic #8f5902", # class: 'sd' - like a comment
        String.Double:             "#4e9a06",        # class: 's2'
        String.Escape:             "#4e9a06",        # class: 'se'
        String.Heredoc:            "#4e9a06",        # class: 'sh'
        String.Interpol:           "#4e9a06",        # class: 'si'
        String.Other:              "#4e9a06",        # class: 'sx'
        String.Regex:              "#4e9a06",        # class: 'sr'
        String.Single:             "#4e9a06",        # class: 's1'
        String.Symbol:             "#4e9a06",        # class: 'ss'

        Generic:                   "#000000",        # class: 'g'
        Generic.Deleted:           "#a40000",        # class: 'gd'
        Generic.Emph:              "italic #000000", # class: 'ge'
        Generic.Error:             "#ef2929",        # class: 'gr'
        Generic.Heading:           "bold #000080",   # class: 'gh'
        Generic.Inserted:          "#00A000",        # class: 'gi'
        Generic.Output:            "#888",           # class: 'go'
        Generic.Prompt:            "#745334",        # class: 'gp'
        Generic.Strong:            "bold #000000",   # class: 'gs'
        Generic.Subheading:        "bold #800080",   # class: 'gu'
        Generic.Traceback:         "bold #a40000",   # class: 'gt'
    }

########NEW FILE########
__FILENAME__ = run
from todos import create_app

if __name__ == "__main__":
    app = create_app()
    app.run()

########NEW FILE########
__FILENAME__ = tests
from twill.browser import TwillException
from flask_testing import TestCase, Twill

from todos import create_app

class TestViews(TestCase):

    def create_app(self):
        app = create_app()
        self.twill = Twill(app)
        return app

    def test_manually(self):
        with self.twill as t:
            t.browser.go(self.twill.url("/"))
            t.browser.showforms()
            t.browser.submit(0)

    def test_bad_manually(self):
        with self.twill as t:
            t.browser.go(self.twill.url("/foo/"))
            t.browser.showforms()
            self.assertRaises(TwillException, t.browser.submit, 1)

########NEW FILE########
__FILENAME__ = twill
# -*- coding: utf-8 -*-
"""
    flask_testing.twill
    ~~~~~~~~~~~~~~~~~~~

    Flask unittest integration.

    :copyright: (c) 2010 by Dan Jacob.
    :license: BSD, see LICENSE for more details.
"""

from __future__ import absolute_import

import StringIO
import twill

from .utils import TestCase


class Twill(object):
    """

    :versionadded: 0.3

    Twill wrapper utility class.

    Creates a Twill ``browser`` instance and handles
    WSGI intercept.

    Usage::

        t = Twill(self.app)
        with t:
            t.browser.go("/")
            t.url("/")

    """
    def __init__(self, app, host='127.0.0.1', port=5000, scheme='http'):
        self.app = app
        self.host = host
        self.port = port
        self.scheme = scheme

        self.browser = twill.get_browser()

    def __enter__(self):
        twill.set_output(StringIO.StringIO())
        twill.commands.clear_cookies()
        twill.add_wsgi_intercept(self.host,
                                 self.port,
                                 lambda: self.app)

        return self

    def __exit__(self, exc_type, exc_value, tb):
        twill.remove_wsgi_intercept(self.host,
                                    self.port)

        twill.commands.reset_output()

    def url(self, url):
        """
        Makes complete URL based on host, port and scheme
        Twill settings.

        :param url: relative URL
        """
        return "%s://%s:%d%s" % (self.scheme,
                                 self.host,
                                 self.port,
                                 url)


class TwillTestCase(TestCase):
    """
    :deprecated: use Twill helper class instead.

    Creates a Twill ``browser`` instance and handles
    WSGI intercept.
    """

    twill_host = "127.0.0.1"
    twill_port = 5000
    twill_scheme = "http"

    def _pre_setup(self):
        super(TwillTestCase, self)._pre_setup()
        twill.set_output(StringIO.StringIO())
        twill.commands.clear_cookies()
        twill.add_wsgi_intercept(self.twill_host,
                                 self.twill_port,
                                 lambda: self.app)

        self.browser = twill.get_browser()

    def _post_teardown(self):

        twill.remove_wsgi_intercept(self.twill_host,
                                    self.twill_port)

        twill.commands.reset_output()

        super(TwillTestCase, self)._post_teardown()

    def make_twill_url(self, url):
        """
        Makes complete URL based on host, port and scheme
        Twill settings.

        :param url: relative URL
        """
        return "%s://%s:%d%s" % (self.twill_scheme,
                                 self.twill_host,
                                 self.twill_port,
                                 url)

########NEW FILE########
__FILENAME__ = utils
# -*- coding: utf-8 -*-
"""
    flask_testing.utils
    ~~~~~~~~~~~~~~~~~~~

    Flask unittest integration.

    :copyright: (c) 2010 by Dan Jacob.
    :license: BSD, see LICENSE for more details.
"""
from __future__ import absolute_import, with_statement

import gc
import time
try:
    import unittest2 as unittest
except ImportError:
    import unittest
import multiprocessing

from werkzeug import cached_property

# Use Flask's preferred JSON module so that our runtime behavior matches.
from flask import json_available, templating, template_rendered
if json_available:
    from flask import json

# we'll use signals for template-related tests if
# available in this version of Flask
try:
    import blinker
    _is_signals = True
except ImportError:  # pragma: no cover
    _is_signals = False

__all__ = ["TestCase"]


class ContextVariableDoesNotExist(Exception):
    pass


class JsonResponseMixin(object):
    """
    Mixin with testing helper methods
    """
    @cached_property
    def json(self):
        if not json_available:  # pragma: no cover
            raise NotImplementedError
        return json.loads(self.data)


def _make_test_response(response_class):
    class TestResponse(response_class, JsonResponseMixin):
        pass

    return TestResponse


def _empty_render(template, context, app):
    """
    Used to monkey patch the render_template flask method when
    the render_templates property is set to False in the TestCase
    """
    if _is_signals:
        template_rendered.send(app, template=template, context=context)

    return ""


class TestCase(unittest.TestCase):
    def create_app(self):
        """
        Create your Flask app here, with any
        configuration you need.
        """
        raise NotImplementedError

    def __call__(self, result=None):
        """
        Does the required setup, doing it here
        means you don't have to call super.setUp
        in subclasses.
        """
        self.app = self._ctx = self.client = self.templates = None
        try:
            self._pre_setup()
            super(TestCase, self).__call__(result)
        finally:
            self._post_teardown()

    def _pre_setup(self):
        self.app = self.create_app()

        self._orig_response_class = self.app.response_class
        self.app.response_class = _make_test_response(self.app.response_class)

        self.client = self.app.test_client()

        self._ctx = self.app.test_request_context()
        self._ctx.push()

        if self._is_not_render_templates():
            self._monkey_patch_render_template()

        self.templates = []
        if _is_signals:
            template_rendered.connect(self._add_template)

    def _add_template(self, app, template, context):
        if len(self.templates) > 0:
            self.templates = []
        self.templates.append((template, context))

    def _post_teardown(self):
        if self._ctx is not None:
            self._ctx.pop()
        if self.app is not None:
            self.app.response_class = self._orig_response_class
        if _is_signals:
            template_rendered.disconnect(self._add_template)
        if hasattr(self, '_true_render'):
            templating._render = self._true_render

        del self.app
        del self.client
        del self.templates
        del self._ctx

        gc.collect()

    def _is_not_render_templates(self):
        return hasattr(self, 'render_templates') and not self.render_templates

    def _monkey_patch_render_template(self):
        self._true_render = templating._render
        templating._render = _empty_render

    def assertTemplateUsed(self, name, tmpl_name_attribute='name'):
        """
        Checks if a given template is used in the request.
        Only works if your version of Flask has signals
        support (0.6+) and blinker is installed.
        If the template engine used is not Jinja2, provide
        ``tmpl_name_attribute`` with a value of its `Template`
        class attribute name which contains the provided ``name`` value.

        :versionadded: 0.2
        :param name: template name
        :param tmpl_name_attribute: template engine specific attribute name
        """
        if not _is_signals:
            raise RuntimeError("Signals not supported")

        for template, context in self.templates:
            if getattr(template, tmpl_name_attribute) == name:
                return True
        raise AssertionError("template %s not used" % name)

    assert_template_used = assertTemplateUsed

    def get_context_variable(self, name):
        """
        Returns a variable from the context passed to the
        template. Only works if your version of Flask
        has signals support (0.6+) and blinker is installed.

        Raises a ContextVariableDoesNotExist exception if does
        not exist in context.

        :versionadded: 0.2
        :param name: name of variable
        """
        if not _is_signals:
            raise RuntimeError("Signals not supported")

        for template, context in self.templates:
            if name in context:
                return context[name]
        raise ContextVariableDoesNotExist

    def assertContext(self, name, value):
        """
        Checks if given name exists in the template context
        and equals the given value.

        :versionadded: 0.2
        :param name: name of context variable
        :param value: value to check against
        """

        try:
            self.assertEqual(self.get_context_variable(name), value)
        except ContextVariableDoesNotExist:
            self.fail("Context variable does not exist: %s" % name)

    assert_context = assertContext

    def assertRedirects(self, response, location):
        """
        Checks if response is an HTTP redirect to the
        given location.

        :param response: Flask response
        :param location: relative URL (i.e. without **http://localhost**)
        """
        self.assertTrue(response.status_code in (301, 302))
        self.assertEqual(response.location, "http://localhost" + location)

    assert_redirects = assertRedirects

    def assertStatus(self, response, status_code):
        """
        Helper method to check matching response status.

        :param response: Flask response
        :param status_code: response status code (e.g. 200)
        """
        self.assertEqual(response.status_code, status_code)

    assert_status = assertStatus

    def assert200(self, response):
        """
        Checks if response status code is 200

        :param response: Flask response
        """

        self.assertStatus(response, 200)

    assert_200 = assert200

    def assert400(self, response):
        """
        Checks if response status code is 400

        :versionadded: 0.2.5
        :param response: Flask response
        """

        self.assertStatus(response, 400)

    assert_400 = assert400

    def assert401(self, response):
        """
        Checks if response status code is 401

        :versionadded: 0.2.1
        :param response: Flask response
        """

        self.assertStatus(response, 401)

    assert_401 = assert401

    def assert403(self, response):
        """
        Checks if response status code is 403

        :versionadded: 0.2
        :param response: Flask response
        """

        self.assertStatus(response, 403)

    assert_403 = assert403

    def assert404(self, response):
        """
        Checks if response status code is 404

        :param response: Flask response
        """

        self.assertStatus(response, 404)

    assert_404 = assert404

    def assert405(self, response):
        """
        Checks if response status code is 405

        :versionadded: 0.2
        :param response: Flask response
        """

        self.assertStatus(response, 405)

    assert_405 = assert405

    def assert500(self, response):
        """
        Checks if response status code is 500

        :versionadded: 0.4.1
        :param response: Flask response
        """

        self.assertStatus(response, 500)

    assert_500 = assert500


# A LiveServerTestCase useful with Selenium or headless browsers
# Inspired by https://docs.djangoproject.com/en/dev/topics/testing/#django.test.LiveServerTestCase

class LiveServerTestCase(unittest.TestCase):

    def create_app(self):
        """
        Create your Flask app here, with any
        configuration you need.
        """
        raise NotImplementedError

    def __call__(self, result=None):
        """
        Does the required setup, doing it here means you don't have to
        call super.setUp in subclasses.
        """

        # Get the app
        self.app = self.create_app()

        try:
            self._spawn_live_server()
            super(LiveServerTestCase, self).__call__(result)
        finally:
            self._terminate_live_server()

    def get_server_url(self):
        """
        Return the url of the test server
        """
        return 'http://localhost:%s' % self.port

    def _spawn_live_server(self):
        self._process = None
        self.port = self.app.config.get('LIVESERVER_PORT', 5000)

        worker = lambda app, port: app.run(port=port)

        self._process = multiprocessing.Process(
            target=worker, args=(self.app, self.port)
        )

        self._process.start()

        # we must wait the server start listening
        time.sleep(1)

    def _terminate_live_server(self):
        if self._process:
            self._process.terminate()

########NEW FILE########
__FILENAME__ = run
import sys
import unittest

try:
    from coverage import coverage
    coverage_available = True
except ImportError:
    coverage_available = False


def run():
    if coverage_available:
        cov = coverage(source=['flask_testing'])
        cov.start()

    from tests import suite
    result = unittest.TextTestRunner(verbosity=2).run(suite())
    if not result.wasSuccessful():
        sys.exit(1)

    if coverage_available:
        cov.stop()

        print("\nCode Coverage")
        cov.report()
        cov.html_report(directory='cover')
    else:
        print("\nTipp:\n\tUse 'pip install coverage' to get great code "
              "coverage stats")

if __name__ == '__main__':
    run()

########NEW FILE########
__FILENAME__ = test_twill
from __future__ import with_statement

from flask_testing import TestCase, TwillTestCase, Twill
from .flask_app import create_app


class TestTwill(TestCase):

    def create_app(self):
        app = create_app()
        app.config.from_object(self)
        return app

    def test_twill_setup(self):

        twill = Twill(self.app)

        self.assertEqual(twill.host, "127.0.0.1")
        self.assertEqual(twill.port, 5000)
        self.assertTrue(twill.browser is not None)

    def test_make_twill_url(self):
        with Twill(self.app) as t:
            self.assertEqual(t.url("/"), "http://127.0.0.1:5000/")


class TestTwillDeprecated(TwillTestCase):

    def create_app(self):
        app = create_app()
        app.config.from_object(self)
        return app

    def test_twill_setup(self):
        self.assertEqual(self.twill_host, '127.0.0.1')
        self.assertEqual(self.twill_port, 5000)
        self.assertTrue(self.browser is not None)

    def test_make_twill_url(self):
        self.assertEqual(self.make_twill_url("/"), "http://127.0.0.1:5000/")

########NEW FILE########
__FILENAME__ = test_utils
try:
    from urllib2 import urlopen
except ImportError:
    from urllib.request import urlopen
from unittest import TestResult
from flask_testing import TestCase, LiveServerTestCase
from flask_testing.utils import ContextVariableDoesNotExist
from .flask_app import create_app


class TestSetup(TestCase):

    def create_app(self):
        return create_app()

    def test_setup(self):

        self.assertTrue(self.app is not None)
        self.assertTrue(self.client is not None)
        self.assertTrue(self._ctx is not None)


class TestSetupFailure(TestCase):

    def _pre_setup(self):
        pass

    def test_setup_failure(self):
        '''Should not fail in _post_teardown if _pre_setup fails'''
        assert True


class TestClientUtils(TestCase):

    def create_app(self):
        return create_app()

    def test_get_json(self):
        response = self.client.get("/ajax/")
        self.assertEqual(response.json, dict(name="test"))

    def test_assert_200(self):
        self.assert200(self.client.get("/"))

    def test_assert_404(self):
        self.assert404(self.client.get("/oops/"))

    def test_assert_403(self):
        self.assert403(self.client.get("/forbidden/"))

    def test_assert_401(self):
        self.assert401(self.client.get("/unauthorized/"))

    def test_assert_405(self):
        self.assert405(self.client.post("/"))

    def test_assert_500(self):
        self.assert500(self.client.get("/internal_server_error/"))

    def test_assert_redirects(self):
        response = self.client.get("/redirect/")
        self.assertRedirects(response, "/")

    def test_assert_template_used(self):
        try:
            self.client.get("/template/")
            self.assert_template_used("index.html")
        except RuntimeError:
            pass

    def test_assert_template_not_used(self):
        self.client.get("/")
        try:
            self.assert_template_used("index.html")
            assert False
        except AssertionError:
            pass
        except RuntimeError:
            pass

    def test_get_context_variable(self):
        try:
            self.client.get("/template/")
            self.assertEqual(self.get_context_variable("name"), "test")
        except RuntimeError:
            pass

    def test_assert_context(self):
        try:
            self.client.get("/template/")
            self.assert_context("name", "test")
        except RuntimeError:
            pass

    def test_assert_bad_context(self):
        try:
            self.client.get("/template/")
            self.assertRaises(AssertionError, self.assert_context,
                              "name", "foo")
            self.assertRaises(AssertionError, self.assert_context,
                              "foo", "foo")
        except RuntimeError:
            pass

    def test_assert_get_context_variable_not_exists(self):
        try:
            self.client.get("/template/")
            self.assertRaises(ContextVariableDoesNotExist,
                              self.get_context_variable, "foo")
        except RuntimeError:
            pass


class TestLiveServer(LiveServerTestCase):

        def create_app(self):
            app = create_app()
            app.config['LIVESERVER_PORT'] = 8943
            return app

        def test_server_process_is_spawned(self):
            process = self._process

            # Check the process is spawned
            self.assertNotEqual(process, None)

            # Check the process is alive
            self.assertTrue(process.is_alive())

        def test_server_listening(self):
            response = urlopen(self.get_server_url())
            self.assertTrue(b'OK' in response.read())
            self.assertEqual(response.code, 200)


class TestNotRenderTemplates(TestCase):

    render_templates = False

    def create_app(self):
        return create_app()

    def test_assert_not_process_the_template(self):
        response = self.client.get("/template/")

        assert "" == response.data

    def test_assert_template_rendered_signal_sent(self):
        self.client.get("/template/")

        self.assert_template_used('index.html')


class TestRenderTemplates(TestCase):

    render_templates = True

    def create_app(self):
        return create_app()

    def test_assert_not_process_the_template(self):
        response = self.client.get("/template/")

        assert "" != response.data


class TestRestoreTheRealRender(TestCase):

    def create_app(self):
        return create_app()

    def test_assert_the_real_render_template_is_restored(self):
        test = TestNotRenderTemplates('test_assert_not_process_the_template')
        test_result = TestResult()
        test(test_result)

        assert test_result.wasSuccessful()

        response = self.client.get("/template/")

        assert "" != response.data

########NEW FILE########
__FILENAME__ = __main__
from run import run

if __name__ == '__main__':
    run()

########NEW FILE########
