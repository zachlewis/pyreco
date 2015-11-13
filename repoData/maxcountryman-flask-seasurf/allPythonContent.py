__FILENAME__ = conf
# -*- coding: utf-8 -*-
#
# SeaSurf documentation build configuration file, created by
# sphinx-quickstart on Tue Dec  6 12:26:37 2011.
#
# This file is execfile()d with the current directory set to its containing dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out
# serve to show the default.

import sys, os
sys.path.append(os.path.abspath('_themes'))

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#sys.path.insert(0, os.path.abspath('.'))

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
project = u'SeaSurf'
copyright = u'2011, Max Countryman'

module_path = os.path.join(os.path.dirname(__file__), '..', 'flask_seasurf.py')
module_path = os.path.abspath(module_path)
version_line = filter(lambda l: l.startswith('__version_info__'),
                      open(module_path))[0]

__version__ = '.'.join(eval(version_line.split('__version_info__ = ')[-1]))

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = __version__
# The full version, including alpha/beta/rc tags.
release = __version__

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
pygments_style = 'sphinx'

# A list of ignored prefixes for module index sorting.
#modindex_common_prefix = []


# -- Options for HTML output ---------------------------------------------------
html_theme_options = {'github_fork': 'maxcountryman/flask-seasurf', 'index_logo': False}

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
html_theme = 'flask_small'

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

# This is the file name suffix for HTML files (e.g. ".xhtml").
#html_file_suffix = None

# Output file base name for HTML help builder.
htmlhelp_basename = 'SeaSurfdoc'


# -- Options for LaTeX output --------------------------------------------------

# The paper size ('letter' or 'a4').
#latex_paper_size = 'letter'

# The font size ('10pt', '11pt' or '12pt').
#latex_font_size = '10pt'

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass [howto/manual]).
latex_documents = [
  ('index', 'SeaSurf.tex', u'SeaSurf Documentation',
   u'Max Countryman', 'manual'),
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
    ('index', 'seasurf', u'SeaSurf Documentation',
     [u'Max Countryman'], 1)
]


# Example configuration for intersphinx: refer to the Python standard library.
intersphinx_mapping = {'http://docs.python.org/': None}

########NEW FILE########
__FILENAME__ = flask_seasurf
'''
    flaskext.seasurf
    ----------------

    A Flask extension providing fairly good protection against cross-site
    request forgery (CSRF), otherwise known as "sea surf".

    :copyright: (c) 2011 by Max Countryman.
    :license: BSD, see LICENSE for more details.
'''

from __future__ import absolute_import

__version_info__ = ('0', '1', '22')
__version__ = '.'.join(__version_info__)
__author__ = 'Max Countryman'
__license__ = 'BSD'
__copyright__ = '(c) 2011 by Max Countryman'
__all__ = ['SeaSurf']

import sys
import hashlib
import random

from datetime import timedelta

from flask import g, request, abort, session
from werkzeug.security import safe_str_cmp


if sys.version_info[0] < 3:
    import urlparse
    _MAX_CSRF_KEY = long(18446744073709551616)  # 2 << 63
else:
    import urllib.parse as urlparse
    _MAX_CSRF_KEY = 18446744073709551616  # 2 << 63


if hasattr(random, 'SystemRandom'):
    randrange = random.SystemRandom().randrange
else:
    randrange = random.randrange

REASON_NO_REFERER = 'Referer checking failed: no referer.'
REASON_BAD_REFERER = 'Referer checking failed: %s does not match %s.'
REASON_NO_CSRF_TOKEN = 'CSRF token not set.'
REASON_BAD_TOKEN = 'CSRF token missing or incorrect.'


def csrf(app):
    '''Helper function to wrap the SeaSurf class.'''
    SeaSurf(app)


def xsrf(app):
    '''Helper function to wrap the SeaSurf class.'''
    SeaSurf(app)


def _same_origin(url1, url2):
    '''Determine if two URLs share the same origin.'''
    p1, p2 = urlparse.urlparse(url1), urlparse.urlparse(url2)
    origin1 = p1.scheme, p1.hostname, p1.port
    origin2 = p2.scheme, p2.hostname, p2.port
    return origin1 == origin2


class SeaSurf(object):
    '''Primary class container for CSRF validation logic. The main function of
    this extension is to generate and validate CSRF tokens. The design and
    implementation of this extension is influenced by Django's CSRF middleware.

    Tokens are generated using a salted SHA1 hash. The salt is based off a
    a random range. The OS's SystemRandom is used if available, otherwise
    the core random.randrange is used.

    You might intialize :class:`SeaSurf` something like this::

        csrf = SeaSurf(app)

    Validation will now be active for all requests whose methods are not GET,
    HEAD, OPTIONS, or TRACE.

    When using other request methods, such as POST for instance, you will need
    to provide the CSRF token as a parameter. This can be achieved by making
    use of the Jinja global. In your template::

        <form method="POST">
        ...
        <input type="hidden" name="_csrf_token" value="{{ csrf_token() }}">
        </form>

    This will assign a token to both the session cookie and the rendered HTML
    which will then be validated on the backend. POST requests missing this
    field will fail unless the header X-CSRFToken is specified.

    .. admonition:: Excluding Views From Validation

        For views that use methods which may be validated but for which you
        wish to not run validation on you may make use of the :class:`exempt`
        decorator to indicate that they should not be checked.

    :param app: The Flask application object, defaults to None.
    '''

    def __init__(self, app=None):
        self._exempt_views = set()
        self._include_views = set()

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        '''Initializes a Flask object `app`, binds CSRF validation to
        app.before_request, and assigns `csrf_token` as a Jinja global.

        :param app: The Flask application object.
        '''

        self.app = app
        app.before_request(self._before_request)
        app.after_request(self._after_request)

        # expose the CSRF token to the template
        app.jinja_env.globals['csrf_token'] = self._get_token

        self._csrf_name = app.config.get('CSRF_COOKIE_NAME', '_csrf_token')
        self._csrf_header_name = app.config.get('CSRF_HEADER_NAME', 'X-CSRFToken')
        self._csrf_disable = app.config.get('CSRF_DISABLE',
                                            app.config.get('TESTING', False))
        self._csrf_timeout = app.config.get('CSRF_COOKIE_TIMEOUT',
                                            timedelta(days=5))
        self._csrf_secure = app.config.get('CSRF_COOKIE_SECURE', False)
        self._csrf_httponly = app.config.get('CSRF_COOKIE_HTTPONLY', False)
        self._type = app.config.get('SEASURF_INCLUDE_OR_EXEMPT_VIEWS',
                                    'exempt')

    def exempt(self, view):
        '''A decorator that can be used to exclude a view from CSRF validation.

        Example usage of :class:`exempt` might look something like this::

            csrf = SeaSurf(app)

            @csrf.exempt
            @app.route('/some_view')
            def some_view():
                """This view is exempt from CSRF validation."""
                return render_template('some_view.html')

        :param view: The view to be wrapped by the decorator.
        '''

        view_location = '%s.%s' % (view.__module__, view.__name__)
        self._exempt_views.add(view_location)
        return view

    def include(self, view):
        '''A decorator that can be used to include a view from CSRF validation.

        Example usage of :class:`include` might look something like this::

            csrf = SeaSurf(app)

            @csrf.include
            @app.route('/some_view')
            def some_view():
                """This view is include from CSRF validation."""
                return render_template('some_view.html')

        :param view: The view to be wrapped by the decorator.
        '''

        view_location = '%s.%s' % (view.__module__, view.__name__)
        self._include_views.add(view_location)
        return view

    def _should_use_token(self, view_func):
        '''Given a view function, determine whether or not we should
        deliver a CSRF token to this view through the response and
        validate CSRF tokens upon requests to this view.'''
        if view_func is None:
            return False
        view = '%s.%s' % (view_func.__module__, view_func.__name__)
        if self._type == 'exempt':
            if view in self._exempt_views:
                return False
        elif self._type == 'include':
            if view not in self._include_views:
                return False
        else:
            raise NotImplementedError
        return True

    def _before_request(self):
        '''Determine if a view is exempt from CSRF validation and if not
        then ensure the validity of the CSRF token. This method is bound to
        the Flask `before_request` decorator.

        If a request is determined to be secure, i.e. using HTTPS, then we
        use strict referer checking to prevent a man-in-the-middle attack
        from being plausible.

        Validation is suspended if `TESTING` is True in your application's
        configuration.
        '''

        if self._csrf_disable:
            return  # don't validate for testing

        csrf_token = session.get(self._csrf_name, None)
        if not csrf_token:
            setattr(g, self._csrf_name, self._generate_token())
        else:
            setattr(g, self._csrf_name, csrf_token)

        # Always set this to let the response know whether or not to set the CSRF token
        g._view_func = self.app.view_functions.get(request.endpoint)

        if request.method not in ('GET', 'HEAD', 'OPTIONS', 'TRACE'):
            # Retrieve the view function based on the request endpoint and
            # then compare it to the set of exempted views
            if not self._should_use_token(g._view_func):
                return

            if request.is_secure:
                referer = request.headers.get('Referer')
                if referer is None:
                    error = (REASON_NO_REFERER, request.path)
                    self.app.logger.warning('Forbidden (%s): %s' % error)
                    return abort(403)

                # by setting the Access-Control-Allow-Origin header, browsers will
                # let you send cross-domain ajax requests so if there is an Origin
                # header, the browser has already decided that it trusts this domain
                # otherwise it would have blocked the request before it got here.
                allowed_referer = request.headers.get('Origin') or request.url_root
                if not _same_origin(referer, allowed_referer):
                    error = REASON_BAD_REFERER % (referer, allowed_referer)
                    error = (error, request.path)
                    self.app.logger.warning('Forbidden (%s): %s' % error)
                    return abort(403)

            request_csrf_token = request.form.get(self._csrf_name, '') 
            if request_csrf_token == '':
                # Check to see if the data is being sent as JSON
                if hasattr(request, 'json') and request.json:
                    request_csrf_token = request.json.get(self._csrf_name, '')

            if request_csrf_token == '':
                # As per the Django middleware, this makes AJAX easier and
                # PUT and DELETE possible
                request_csrf_token = request.headers.get(self._csrf_header_name, '')

            some_none = None in (request_csrf_token, csrf_token)
            if some_none or not safe_str_cmp(request_csrf_token, csrf_token):
                error = (REASON_BAD_TOKEN, request.path)
                self.app.logger.warning('Forbidden (%s): %s' % error)
                return abort(403)

    def _after_request(self, response):
        '''Checks if the flask.g object contains the CSRF token, and if
        the view in question has CSRF protection enabled. If both, returns
        the response with a cookie containing the token. If not then we just
        return the response unaltered. Bound to the Flask `after_request`
        decorator.'''

        if getattr(g, self._csrf_name, None) is None:
            return response

        _view_func = getattr(g, '_view_func', False)
        if not (_view_func and self._should_use_token(_view_func)):
            return response

        session[self._csrf_name] = getattr(g, self._csrf_name)
        response.set_cookie(self._csrf_name,
                            getattr(g, self._csrf_name),
                            max_age=self._csrf_timeout,
                            secure=self._csrf_secure,
                            httponly=self._csrf_httponly
                            )
        response.vary.add('Cookie')
        return response

    def _get_token(self):
        '''Attempts to get a token from the request cookies.'''
        return getattr(g, self._csrf_name, None)

    def _generate_token(self):
        '''Generates a token with randomly salted SHA1. Returns a string.'''
        salt = str(randrange(0, _MAX_CSRF_KEY)).encode('utf-8')
        return hashlib.sha1(salt).hexdigest()

########NEW FILE########
__FILENAME__ = test_seasurf
from __future__ import with_statement

import sys
import unittest

from flask import Flask
from flask_seasurf import SeaSurf


if sys.version_info[0] < 3:
    b = lambda s: s
else:
    b = lambda s: s.encode('utf-8')


class SeaSurfTestCase(unittest.TestCase):

    def setUp(self):
        app = Flask(__name__)
        app.debug = True
        app.secret_key = '1234'
        self.app = app

        csrf = SeaSurf(app)
        csrf._csrf_disable = False
        self.csrf = csrf

        @csrf.exempt
        @app.route('/foo', methods=['POST'])
        def foo():
            return 'bar'

        @app.route('/bar', methods=['POST'])
        def bar():
            return 'foo'

    def test_generate_token(self):
        self.assertIsNotNone(self.csrf._generate_token())

    def test_unique_generation(self):
        token_a = self.csrf._generate_token()
        token_b = self.csrf._generate_token()
        self.assertNotEqual(token_a, token_b)

    def test_token_is_string(self):
        token = self.csrf._generate_token()
        self.assertEqual(type(token), str)

    def test_exempt_view(self):
        rv = self.app.test_client().post('/foo')
        self.assertIn(b('bar'), rv.data)

    def test_token_validation(self):
        # should produce a logger warning
        rv = self.app.test_client().post('/bar')
        self.assertIn(b('403 Forbidden'), rv.data)

    def test_json_token_validation_bad(self):
        """Should fail with 403 JSON _csrf_token differers from session token"""
        tokenA = self.csrf._generate_token()
        tokenB = self.csrf._generate_token()
        data = {'_csrf_token': tokenB }
        headers = {'Content-Type': 'application/json'}
        with self.app.test_client() as client:
            with client.session_transaction() as sess:
                sess[self.csrf._csrf_name] = tokenA
                client.set_cookie('www.example.com', self.csrf._csrf_name, tokenB)

            rv = client.post('/bar', data=data)
            self.assertEqual(rv.status_code, 403, rv)

    def test_json_token_validation_good(self):
        """Should succeed error if JSON has _csrf_token set"""
        token = self.csrf._generate_token()
        data = {'_csrf_token': token }
        headers = {'Content-Type': 'application/json'}
        with self.app.test_client() as client:
            with client.session_transaction() as sess:
                client.set_cookie('www.example.com', self.csrf._csrf_name, token)
                sess[self.csrf._csrf_name] = token

            rv = client.post('/bar', data=data)
            self.assertEqual(rv.status_code, 200, rv)

    def test_https_bad_referer(self):
        with self.app.test_client() as client:
            with client.session_transaction() as sess:
                token = self.csrf._generate_token()

                client.set_cookie('www.example.com', self.csrf._csrf_name, token)
                sess[self.csrf._csrf_name] = token

            # once this is reached the session was stored
            rv = client.post('/bar',
                data={self.csrf._csrf_name: token},
                base_url='https://www.example.com',
                headers={'Referer': 'https://www.evil.com/foobar'}
            )

            self.assertEqual(403, rv.status_code)

    def test_https_good_referer(self):
        with self.app.test_client() as client:
            with client.session_transaction() as sess:
                token = self.csrf._generate_token()

                client.set_cookie('www.example.com', self.csrf._csrf_name, token)
                sess[self.csrf._csrf_name] = token

            # once this is reached the session was stored
            rv = client.post('/bar',
                data={self.csrf._csrf_name: token},
                base_url='https://www.example.com',
                headers={'Referer': 'https://www.example.com/foobar'}
            )

            self.assertEqual(rv.status_code, 200)

    # Methods for backwards compatibility with python 2.5 & 2.6
    def assertIn(self, value, container):
        self.assertTrue(value in container)

    def assertIsNotNone(self, value):
        self.assertNotEqual(value, None)


class SeaSurfTestCaseExemptViews(unittest.TestCase):

    def setUp(self):
        app = Flask(__name__)
        app.debug = True
        app.secret_key = '1234'
        app.config['SEASURF_INCLUDE_OR_EXEMPT_VIEWS'] = 'exempt'

        self.app = app

        csrf = SeaSurf(app)
        csrf._csrf_disable = False
        self.csrf = csrf

        @csrf.exempt
        @app.route('/foo', methods=['POST'])
        def foo():
            return 'bar'

        @app.route('/bar', methods=['POST'])
        def bar():
            return 'foo'

    def test_exempt_view(self):
        rv = self.app.test_client().post('/foo')
        self.assertIn(b('bar'), rv.data)

    def test_token_validation(self):
        # should produce a logger warning
        rv = self.app.test_client().post('/bar')
        self.assertIn(b('403 Forbidden'), rv.data)

    def assertIn(self, value, container):
        self.assertTrue(value in container)


class SeaSurfTestCaseIncludeViews(unittest.TestCase):

    def setUp(self):
        app = Flask(__name__)
        app.debug = True
        app.secret_key = '1234'
        app.config['SEASURF_INCLUDE_OR_EXEMPT_VIEWS'] = 'include'

        self.app = app

        csrf = SeaSurf(app)
        csrf._csrf_disable = False
        self.csrf = csrf

        @csrf.include
        @app.route('/foo', methods=['POST'])
        def foo():
            return 'bar'

        @app.route('/bar', methods=['POST'])
        def bar():
            return 'foo'

    def test_include_view(self):
        rv = self.app.test_client().post('/foo')
        self.assertIn(b('403 Forbidden'), rv.data)

    def test_token_validation(self):
        # should produce a logger warning
        rv = self.app.test_client().post('/bar')
        self.assertIn(b('foo'), rv.data)

    def assertIn(self, value, container):
        self.assertTrue(value in container)


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(SeaSurfTestCase))
    suite.addTest(unittest.makeSuite(SeaSurfTestCaseExemptViews))
    suite.addTest(unittest.makeSuite(SeaSurfTestCaseIncludeViews))
    return suite

if __name__ == '__main__':

    unittest.main(defaultTest='suite')

########NEW FILE########
