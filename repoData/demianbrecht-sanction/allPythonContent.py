__FILENAME__ = conf
# -*- coding: utf-8 -*-
#
# sanction documentation build configuration file, created by
# sphinx-quickstart on Tue Aug 20 07:22:31 2013.
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
#sys.path.insert(0, os.path.abspath('.'))
sys.path.insert(0, os.path.abspath('../'))

# -- General configuration -----------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be extensions
# coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = ['sphinx.ext.autodoc']

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The encoding of source files.
#source_encoding = 'utf-8-sig'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = u'sanction'
copyright = u'2013, Demian Brecht'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = '0.4'
# The full version, including alpha/beta/rc tags.
release = '0.4'

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

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
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
htmlhelp_basename = 'sanctiondoc'


# -- Options for LaTeX output --------------------------------------------------

latex_elements = {
# The paper size ('letterpaper' or 'a4paper').
#'papersize': 'letterpaper',

# The font size ('10pt', '11pt' or '12pt').
#'pointsize': '10pt',

# Additional stuff for the LaTeX preamble.
#'preamble': '',
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass [howto/manual]).
latex_documents = [
  ('index', 'sanction.tex', u'sanction Documentation',
   u'Demian Brecht', 'manual'),
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

# Documents to append as an appendix to all manuals.
#latex_appendices = []

# If false, no module index is generated.
#latex_domain_indices = True


# -- Options for manual page output --------------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    ('index', 'sanction', u'sanction Documentation',
     [u'Demian Brecht'], 1)
]

# If true, show URL addresses after external links.
#man_show_urls = False


# -- Options for Texinfo output ------------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
  ('index', 'sanction', u'sanction Documentation',
   u'Demian Brecht', 'sanction', 'One line description of project.',
   'Miscellaneous'),
]

# Documents to append as an appendix to all manuals.
#texinfo_appendices = []

# If false, no module index is generated.
#texinfo_domain_indices = True

# How to display URL addresses: 'footnote', 'no', or 'inline'.
#texinfo_show_urls = 'footnote'

########NEW FILE########
__FILENAME__ = server
#!/usr/bin/env python
# vim: set ts=4 sw=4 et:

import logging
import sys, os

try:
    from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
    from ConfigParser import ConfigParser
    from urlparse import urlparse, urlsplit, urlunsplit, parse_qsl
    from urllib import urlencode
    from urllib2 import Request
    from io import BytesIO 
except ImportError:
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from configparser import ConfigParser
    from urllib.parse import (urlparse, parse_qsl, urlencode,
        urlunsplit, urlsplit)
    from io import BytesIO 
    from urllib.request import Request

from gzip import GzipFile
from json import loads

# so we can run without installing
sys.path.append(os.path.abspath('../'))

from sanction import Client, transport_headers

ENCODING_UTF8 = 'utf-8'

def get_config():
    config = ConfigParser({}, dict)
    config.read('example.ini') 

    c = config._sections['sanction']
    if '__name__' in c:
        del c['__name__']

    if 'http_debug' in c:
        c['http_debug'] = c['http_debug'] == 'true'

    return config._sections['sanction']


logging.basicConfig(format='%(message)s')
l = logging.getLogger(__name__)
config = get_config()


class Handler(BaseHTTPRequestHandler):
    route_handlers = {
        '/': 'handle_root',
        '/login/google': 'handle_google_login',
        '/oauth2/google': 'handle_google',
        '/login/facebook': 'handle_facebook_login',
        '/oauth2/facebook': 'handle_facebook',
        '/login/foursquare': 'handle_foursquare_login',
        '/oauth2/foursquare': 'handle_foursquare',
        '/login/github': 'handle_github_login',
        '/oauth2/github': 'handle_github',
        '/login/instagram': 'handle_instagram_login',
        '/oauth2/instagram': 'handle_instagram',
        '/login/stackexchange': 'handle_stackexchange_login',
        '/oauth2/stackexchange': 'handle_stackexchange',
        '/login/deviantart': 'handle_deviantart_login',
        '/oauth2/deviantart': 'handle_deviantart',
    }

    def do_GET(self):
        url = urlparse(self.path)
        if url.path in self.route_handlers:
            getattr(self, self.route_handlers[url.path])(
            dict(parse_qsl(url.query)))
        else:
            self.send_response(404)

    def success(func):
        def wrapper(self, *args, **kwargs):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.log_message(self.path)
            self.end_headers()
            return func(self, *args, **kwargs)
        return wrapper

    @success
    def handle_root(self, data):
        self.wfile.write('''
            login with: <a href='/oauth2/google'>Google</a>,
            <a href='/oauth2/facebook'>Facebook</a>,
            <a href='/oauth2/github'>GitHub</a>,
            <a href='/oauth2/stackexchange'>Stack Exchange</a>,
            <a href='/oauth2/instagram'>Instagram</a>,
            <a href='/oauth2/foursquare'>Foursquare</a>,
            <a href='/oauth2/deviantart'>Deviant Art</a>,
        '''.encode(ENCODING_UTF8))

    def handle_stackexchange(self, data):
        self.send_response(302)
        c = Client(auth_endpoint='https://stackexchange.com/oauth',
            client_id=config['stackexchange.client_id'])
        self.send_header('Location', c.auth_uri(
            redirect_uri='http://localhost/login/stackexchange'))
        self.end_headers()

    def _gunzip(self, data):
        s = BytesIO(data)
        gz = GzipFile(fileobj=s, mode='rb')
        return gz.read()

    @success
    def handle_stackexchange_login(self, data):
        c = Client(token_endpoint='https://stackexchange.com/oauth/access_token',
            resource_endpoint='https://api.stackexchange.com/2.0',
            client_id=config['stackexchange.client_id'],
            client_secret=config['stackexchange.client_secret'])

        c.request_token(code=data['code'],
            parser = lambda data: dict(parse_qsl(data)),
            redirect_uri='http://localhost/login/stackexchange')

        self.dump_client(c)
        data = c.request('/me?{}'.format(urlencode({
            'site': 'stackoverflow.com',
            'key': config['stackexchange.key']
            })), parser=lambda c: loads(self._gunzip(c).decode(
                'utf-8')))['items'][0]

        self.dump_response(data)

    def dump_response(self, data):
        for k in data:
            self.wfile.write('{0}: {1}<br>'.format(k,
                data[k]).encode(ENCODING_UTF8))

    def dump_client(self, c):
        for k in c.__dict__:
            self.wfile.write('{0}: {1}<br>'.format(k,
                c.__dict__[k]).encode(ENCODING_UTF8))
        self.wfile.write('<hr/>'.encode(ENCODING_UTF8))

    def handle_google(self, data):
        self.send_response(302)
        c = Client(auth_endpoint='https://accounts.google.com/o/oauth2/auth',
            client_id=config['google.client_id'])
        self.send_header('Location', c.auth_uri(
            scope=config['google.scope'], access_type='offline',
            redirect_uri='http://localhost/login/google'))
        self.end_headers()

    @success
    def handle_google_login(self, data):
        c = Client(token_endpoint='https://accounts.google.com/o/oauth2/token',
            resource_endpoint='https://www.googleapis.com/oauth2/v1',
            client_id=config['google.client_id'],
            client_secret=config['google.client_secret'],
            token_transport=transport_headers)
        c.request_token(code=data['code'],
            redirect_uri='http://localhost/login/google')

        self.dump_client(c)
        data = c.request('/userinfo')
        self.dump_response(data)

        if hasattr(c, 'refresh_token'):
            rc = Client(token_endpoint=c.token_endpoint,
                client_id=c.client_id,
                client_secret=c.client_secret,
                resource_endpoint=c.resource_endpoint,
                token_transport='headers')

            rc.request_token(grant_type='refresh_token', 
                refresh_token=c.refresh_token)
            self.wfile.write('<p>post refresh token:</p>'.encode(ENCODING_UTF8))
            self.dump_client(rc)
        
    def handle_facebook(self, data):
        self.send_response(302)
        c = Client(auth_endpoint='https://www.facebook.com/dialog/oauth',
                client_id=config['facebook.client_id'])
        self.send_header('Location', c.auth_uri(
            scope=config['facebook.scope'],
            redirect_uri='http://localhost/login/facebook'))
            
        self.end_headers()

    @success
    def handle_facebook_login(self, data):
        c = Client(
            token_endpoint='https://graph.facebook.com/oauth/access_token',
            resource_endpoint='https://graph.facebook.com',
            client_id=config['facebook.client_id'],
            client_secret=config['facebook.client_secret'])

        c.request_token(code=data['code'],
            redirect_uri='http://localhost/login/facebook')

        self.dump_client(c)
        d = c.request('/me')
        self.dump_response(d)

        try:
            d = c.request('/me/feed', data=bytes(urlencode({
                'message': 'test post from py-sanction'
            }), 'ascii'))
            self.wfile.write(
                'I posted a message to your wall (in sandbox mode, nobody '
                'else will see it)'.encode(ENCODING_UTF8))
        except:
            self.wfile.write(
                b'Unable to post to your wall')

    def handle_foursquare(self, data):
        self.send_response(302)
        c = Client(auth_endpoint='https://foursquare.com/oauth2/authenticate',
                client_id=config['foursquare.client_id'])
        self.send_header('Location', c.auth_uri(
            redirect_uri='http://localhost/login/foursquare'))
        self.end_headers()

    @success
    def handle_foursquare_login(self, data):
        def token_transport(url, access_token, data=None, method=None):
            parts = urlsplit(url)
            query = dict(parse_qsl(parts.query))
            query.update({
                'oauth_token': access_token
            })
            url = urlunsplit((parts.scheme, parts.netloc, parts.path,
                urlencode(query), parts.fragment))
            try:
                req = Request(url, data=data, method=method)
            except TypeError:
                req = Request(url, data=data)
                req.get_method = lambda: method
            return req

        c = Client(
            token_endpoint='https://foursquare.com/oauth2/access_token',
            resource_endpoint='https://api.foursquare.com/v2',
            client_id=config['foursquare.client_id'],
            client_secret=config['foursquare.client_secret'],
            token_transport=token_transport
            )
        c.request_token(code=data['code'],
            redirect_uri='http://localhost/login/foursquare')

        self.dump_client(c)
        d = c.request('/users/24700343')
        self.dump_response(d)


    def handle_github(self, data):
        self.send_response(302)
        c = Client(auth_endpoint='https://github.com/login/oauth/authorize',
                client_id=config['github.client_id'])
        self.send_header('Location', c.auth_uri(
            redirect_uri='http://localhost/login/github'))
        self.end_headers()


    @success
    def handle_github_login(self, data):
        c = Client(token_endpoint='https://github.com/login/oauth/access_token',
            resource_endpoint='https://api.github.com',
            client_id=config['github.client_id'],
            client_secret=config['github.client_secret'])
        c.request_token(code=data['code'],
            redirect_uri='http://localhost/login/github')

        self.dump_client(c)
        data = c.request('/user')
        self.dump_response(data)


    def handle_instagram(self, data):
        self.send_response(302)
        c = Client(auth_endpoint='https://api.instagram.com/oauth/authorize/',
                client_id=config['instagram.client_id'])
        self.send_header('Location', c.auth_uri(
            redirect_uri='http://localhost/login/instagram'))
        self.end_headers()


    @success
    def handle_instagram_login(self, data):
        c = Client(token_endpoint='https://api.instagram.com/oauth/access_token',
            resource_endpoint='https://api.instagram.com/v1',
            client_id=config['instagram.client_id'],
            client_secret=config['instagram.client_secret'])
        c.request_token(code=data['code'],
            redirect_uri='http://localhost/login/instagram')

        self.dump_client(c)
        data = c.request('/users/self')['data']
        self.dump_response(data)


    def handle_deviantart(self, data):
        self.send_response(302)
        c = Client(
            auth_endpoint='https://www.deviantart.com/oauth2/draft15/authorize',
            client_id=config['deviantart.client_id'])
        self.send_header('Location', c.auth_uri(
            redirect_uri=config['deviantart.redirect_uri']))
        self.end_headers()


    @success
    def handle_deviantart_login(self, data):
        c = Client(
            token_endpoint='https://www.deviantart.com/oauth2/draft15/token',
            resource_endpoint='https://www.deviantart.com/api/draft15',
            client_id=config['deviantart.client_id'],
            client_secret=config['deviantart.client_secret'])
        c.request_token(code=data['code'],
            redirect_uri=config['deviantart.redirect_uri'])

        self.dump_client(c)
        data = c.request('/user/whoami')
        self.dump_response(data)


if __name__ == '__main__':
    l.setLevel(1)
    server_address = ('', 80)
    server = HTTPServer(server_address, Handler)
    l.info('Starting server on %sport %s \nPress <ctrl>+c to exit' % server_address)
    server.serve_forever()


########NEW FILE########
__FILENAME__ = client
from warnings import warn
warn('sanction.client.Client is deprecated, please use sanction.Client')
from sanction import Client

########NEW FILE########
__FILENAME__ = test
# vim: set ts=4 sw=4 et:
from io import BytesIO 
from functools import wraps
try:
    from urllib2 import addinfourl
    from httplib import HTTPMessage
except ImportError:
    from urllib.response import addinfourl
    from http.client import HTTPMessage
    basestring = str

from mock import patch


def with_patched_client(data, code=200, headers=None):
    def wrapper(fn):
        @wraps(fn)
        def inner(*args, **kwargs):
            with patch('sanction.urlopen') as mock_urlopen:
                bdata = type(data) is basestring and data.encode() or data
                sheaders = ''
                if headers is not None:
                    sheaders = '\r\n'.join(['{}: {}'.format(k, v) for k, v in
                        headers.items()])
                bheaders = (sheaders or '').encode()

                mock_urlopen.return_value = addinfourl(BytesIO(bdata), 
                    HTTPMessage(BytesIO(bheaders)), '', code=code)
                fn(*args, **kwargs)
        return inner
    return wrapper

########NEW FILE########
__FILENAME__ = tests
# vim: set ts=4 sw=4 et:
import json
import zlib

from functools import wraps
from unittest import TestCase
from uuid import uuid4
try:
    from urlparse import parse_qsl, urlparse
except ImportError:
    from urllib.parse import parse_qsl, urlparse

from mock import patch

from sanction import Client, transport_headers
from sanction.test import with_patched_client

AUTH_ENDPOINT = "http://example.com"
TOKEN_ENDPOINT = "http://example.com/token"
RESOURCE_ENDPOINT = "http://example.com/resource"
CLIENT_ID = "client_id"
CLIENT_SECRET = "client_secret"
REDIRECT_URI = "redirect_uri"
SCOPE = 'foo,bar'
STATE = str(uuid4())
ACCESS_TOKEN = 'access_token'



class TestClient(TestCase):
    def setUp(self):
        self.client = Client(auth_endpoint=AUTH_ENDPOINT,
            token_endpoint=TOKEN_ENDPOINT,
            resource_endpoint=RESOURCE_ENDPOINT,
            client_id=CLIENT_ID)

    def test_init(self):
        map(lambda c: self.assertEqual(*c),
            ((self.client.auth_endpoint, AUTH_ENDPOINT),
            (self.client.token_endpoint, TOKEN_ENDPOINT),
            (self.client.resource_endpoint, RESOURCE_ENDPOINT),
            (self.client.client_id, CLIENT_ID),))

    def test_auth_uri(self):
        parsed = urlparse(self.client.auth_uri(redirect_uri=REDIRECT_URI))
        qs = dict(parse_qsl(parsed.query))

        map(lambda c: self.assertEqual(*c),
            ((qs['redirect_uri'], REDIRECT_URI),
            (qs['response_type'], 'code'),
            (qs['client_id'], CLIENT_ID)))

        parsed = urlparse(self.client.auth_uri(scope=SCOPE))
        qs = dict(parse_qsl(parsed.query))

        self.assertEqual(qs['scope'], SCOPE)

        parsed = urlparse(self.client.auth_uri(state=STATE))
        qs = dict(parse_qsl(parsed.query))

        self.assertEqual(qs['state'], STATE)

    @with_patched_client(json.dumps({
        'access_token':'test_token',
        'expires_in': 300,
    }))
    def test_request_token_json(self):
        self.client.request_token()
        self.assertEqual(self.client.access_token, 'test_token')

        self.client.request_token(redirect_uri=REDIRECT_URI)
        self.assertEqual(self.client.access_token, 'test_token')

    @with_patched_client('access_token=test_token')
    def test_request_token_url(self):
        self.client.request_token()
        self.assertEqual(self.client.access_token, 'test_token')

    @with_patched_client(json.dumps({
        'access_token': 'refreshed_token',
    }))
    def test_refresh_token(self):
        self.client.refresh_token = 'refresh_token'
        self.client.refresh()
        self.assertEqual(self.client.access_token, 'refreshed_token')

    @with_patched_client(json.dumps({
        'userid': 1234
    }))
    def test_request(self):
        self.client.access_token = 'foo'
        data = self.client.request('/foo')
        self.assertEqual(data['userid'], 1234)

    @with_patched_client(zlib.compress(json.dumps({
        'userid': 1234
    }).encode('utf8')))
    def test_request_custom_parser(self):
        def _decompress(buf):
            return json.loads(zlib.decompress(buf).decode())

        self.client.access_token = 'foo'
        data = self.client.request('/foo', parser=_decompress)
        self.assertEqual(data['userid'], 1234)

    @with_patched_client(json.dumps({
        'userid': 1234
    }))
    def test_request_transport_headers(self):
        self.client.token_transport = transport_headers 
        self.client.access_token = 'foo'
        data = self.client.request('/foo')
        self.assertEqual(data['userid'], 1234)

    @with_patched_client(json.dumps({
        'userid': 1234
    }), headers={
        'Content-Type': 'text/html; charset=utf-8',
    })
    def test_request_with_charset(self):
        self.client.access_token = 'foo'
        data = self.client.request('/foo')
        self.assertEqual(data['userid'], 1234)

    @with_patched_client(json.dumps({
        'userid': 1234
    }))
    def test_custom_transport(self):
        def _transport(url, access_token, data=None, method=None,
            headers=None):

            self.assertEqual(url, 'http://example.com/resource/foo')
            self.assertEqual(access_token, 'foo')

        self.client.access_token = 'foo'
        self.client.token_transport = _transport
        data = self.client.request('/foo', headers={
            'Content-Type': 'application/json'})

        self.assertEqual(data['userid'], 1234)

    @with_patched_client(json.dumps({
        'userid': 1234
    }))
    def test_query_transport_with_headers(self):
        self.client.access_token = 'foo'
        data = self.client.request('/foo', headers={'Content-Type':
            'application/json'})

        self.assertEqual(data['userid'], 1234)

    @with_patched_client(json.dumps({
        'userid': 1234
    }))
    def test_header_transport_with_headers(self):
        self.client.access_token = 'foo'
        self.client.token_transport = transport_headers 
        data = self.client.request('/foo', headers={'Content-Type':
            'application/json'})

        self.assertEqual(data['userid'], 1234)

########NEW FILE########
