__FILENAME__ = conf
# -*- coding: utf-8 -*-
#
# Flask-KVsession documentation build configuration file, created by
# sphinx-quickstart on Wed Jul  6 16:01:19 2011.
#
# This file is execfile()d with the current directory set to its containing
# dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out serve
# to show the default.

import sys
import os

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
sys.path.insert(0, os.path.abspath('_themes'))

# -- General configuration
# -----------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
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
project = u'Flask-KVsession'
copyright = u'2011, Marc Brinkmann'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = '0.5'
# The full version, including alpha/beta/rc tags.
release = '0.5dev'

# The language for content autogenerated by Sphinx. Refer to documentation for
# a list of supported languages.
#language = None

# There are two options for replacing |today|: either, you set today to some
# non-false value, then it is used:
#today = ''
# Else, today_fmt is used as the format for a strftime call.
#today_fmt = '%B %d, %Y'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ['_build']

# The reST default role (used for this markup: `text`) to use for all
# documents.
#default_role = None

# If true, '()' will be appended to :func: etc. cross-reference text.
#add_function_parentheses = True

# If true, the current module name will be prepended to all description unit
# titles (such as .. function::).
#add_module_names = True

# If true, sectionauthor and moduleauthor directives will be shown in the
# output. They are ignored by default.
#show_authors = False

# The name of the Pygments (syntax highlighting) style to use.
#pygments_style = 'sphinx'

# A list of ignored prefixes for module index sorting.
#modindex_common_prefix = []


# -- Options for HTML output
# ---------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for a
# list of builtin themes.
html_theme = 'flask_small'

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
html_theme_options = {'github_fork': 'mbr/flask-kvsession', 'index_logo':
'flask_kvsession.png', }

# Add any paths that contain custom themes here, relative to this directory.
html_theme_path = ['_themes']

# The name for this set of Sphinx documents.  If None, it defaults to
# "<project> v<release> documentation".
#html_title = None

# A shorter title for the navigation bar.  Default is the same as html_title.
#html_short_title = None

# The name of an image file (relative to this directory) to place at the top of
# the sidebar.
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
htmlhelp_basename = 'Flask-KVsessiondoc'


# -- Options for LaTeX output
# --------------------------------------------------

# The paper size ('letter' or 'a4').
#latex_paper_size = 'letter'

# The font size ('10pt', '11pt' or '12pt').
#latex_font_size = '10pt'

# Grouping the document tree into LaTeX files. List of tuples (source start
# file, target name, title, author, documentclass [howto/manual]).
latex_documents = [('index', 'Flask-KVsession.tex', u'Flask-KVsession'\
'Documentation', u'Marc Brinkmann', 'manual'), ]

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


# -- Options for manual page output
# --------------------------------------------

# One entry per manual page. List of tuples (source start file, name,
# description, authors, manual section).
man_pages = [('index', 'flask-kvsession', u'Flask-KVsession Documentation',
[u'Marc Brinkmann'], 1)]


# Example configuration for intersphinx: refer to the Python standard library.
intersphinx_mapping = {'http://docs.python.org/': None,
                       'http://simplekv.readthedocs.org/en/latest/': None,
                       'http://flask.pocoo.org/docs/': None}

########NEW FILE########
__FILENAME__ = flask-session-expiry-test
#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import session, Flask
import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'topsecret'
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(seconds=30)


@app.route('/')
def index():
    session['foo'] = str(datetime.datetime.now())
    return 'OK'


@app.route('/make-permanent/')
def make_permanent():
    session.permanent = True
    return 'DONE'


@app.route('/show-session/')
def show_session():
    s = 'SESSION:\n'\
        'new: %s\n'\
        'modified: %s\n'\
        'permanent: %s\n' % (session.new, session.modified, session.permanent)

    s += '\n%s' % session.items()
    return s


app.run(debug=True)

########NEW FILE########
__FILENAME__ = flask_kvsession
# -*- coding: utf-8 -*-
"""
    flaskext.kvsession
    ~~~~~~~~~~~~~~~~~~

    Drop-in replacement module for Flask sessions that uses a
    :class:`simplekv.KeyValueStore` as a
    backend for server-side sessions.
"""


import calendar
try:
    import cPickle as pickle
except ImportError:
    import pickle
from datetime import datetime
from random import SystemRandom
import re

from itsdangerous import Signer, BadSignature
from werkzeug.datastructures import CallbackDict

from flask import current_app
from flask.sessions import SessionMixin, SessionInterface


class SessionID(object):
    """Helper class for parsing session ids.

    Internally, Flask-KVSession stores session ids that are serialized as
    ``KEY_CREATED``, where ``KEY`` is a random number (the sessions "true" id)
    and ``CREATED`` a UNIX-timestamp of when the session was created.

    :param id: An integer to be used as the session key.
    :param created: A :class:`~datetime.datetime` instance or None. A value of
                    None will result in :meth:`~datetime.datetime.utcnow()` to
                    be used.
    """
    def __init__(self, id, created=None):
        if None == created:
            created = datetime.utcnow()

        self.id = id
        self.created = created

    def has_expired(self, lifetime, now=None):
        """Report if the session key has expired.

        :param lifetime: A :class:`datetime.timedelta` that specifies the
                         maximum age this :class:`SessionID` should be checked
                         against.
        :param now: If specified, use this :class:`~datetime.datetime` instance
                         instead of :meth:`~datetime.datetime.utcnow()` as the
                         current time.
        """
        now = now or datetime.utcnow()
        return now > self.created + lifetime

    def serialize(self):
        """Serializes to the standard form of ``KEY_CREATED``"""
        return '%x_%x' % (self.id,
                          calendar.timegm(self.created.utctimetuple()))

    @classmethod
    def unserialize(cls, string):
        """Unserializes from a string.

        :param string: A string created by :meth:`serialize`.
        """
        id_s, created_s = string.split('_')
        return cls(int(id_s, 16),
                   datetime.utcfromtimestamp(int(created_s, 16)))


class KVSession(CallbackDict, SessionMixin):
    """Replacement session class.

    Instances of this class will replace the session (and thus be available
    through things like :attr:`flask.session`.

    The session class will save data to the store only when necessary, empty
    sessions will not be stored at all."""
    def __init__(self, initial=None):
        def _on_update(d):
            d.modified = True

        CallbackDict.__init__(self, initial, _on_update)

        if not initial:
            self.modified = False

    def destroy(self):
        """Destroys a session completely, by deleting all keys and removing it
        from the internal store immediately.

        This allows removing a session for security reasons, e.g. a login
        stored in a session will cease to exist if the session is destroyed.
        """
        for k in self.keys():
            del self[k]

        if self.sid_s:
            current_app.kvsession_store.delete(self.sid_s)

        self.modified = False
        self.new = False

    def regenerate(self):
        """Generate a new session id for this session.

        To avoid vulnerabilities through `session fixation attacks
        <http://en.wikipedia.org/wiki/Session_fixation>`_, this function can be
        called after an action like a login has taken place. The session will
        be copied over to a new session id and the old one removed.
        """
        self.modified = True

        if getattr(self, 'sid_s', None):
            # delete old session
            current_app.kvsession_store.delete(self.sid_s)

            # remove sid_s, set modified
            self.sid_s = None
            self.modified = True

            # save_session() will take care of saving the session now


class KVSessionInterface(SessionInterface):
    serialization_method = pickle
    session_class = KVSession

    def open_session(self, app, request):
        key = app.secret_key

        if key is not None:
            session_cookie = request.cookies.get(
                app.config['SESSION_COOKIE_NAME'],
                None
            )

            if session_cookie:
                try:
                    # restore the cookie, if it has been manipulated,
                    # we will find out here
                    sid_s = Signer(app.secret_key).unsign(session_cookie)
                    sid = SessionID.unserialize(sid_s)

                    if sid.has_expired(
                        app.config['PERMANENT_SESSION_LIFETIME']):
                        #return None  # the session has expired, no need to
                                      # check if it exists
                        # we reach this point if a "non-permanent" session has
                        # expired, but is made permanent. silently ignore the
                        # error with a new session
                        raise KeyError

                    # retrieve from store
                    s = self.session_class(self.serialization_method.loads(
                        current_app.kvsession_store.get(sid_s))
                    )
                    s.sid_s = sid_s
                except (BadSignature, KeyError):
                    # either the cookie was manipulated or we did not find the
                    # session in the backend.

                    # silently swallow errors, instead of of returning a
                    # NullSession
                    s = self.session_class()
                    s.new = True
            else:
                s = self.session_class()  # create an empty session
                s.new = True

            return s

    def save_session(self, app, session, response):
        if session.modified:
            # create a new session id only if requested
            # this makes it possible to avoid session fixation, but prevents
            # full cookie-highjacking if used carefully
            if not getattr(session, 'sid_s', None):
                session.sid_s = SessionID(
                    current_app.config['SESSION_RANDOM_SOURCE'].getrandbits(
                        app.config['SESSION_KEY_BITS']
                    )
                ).serialize()

            current_app.kvsession_store.put(session.sid_s,
                           self.serialization_method.dumps(dict(session)))
            session.new = False

            # save sid_s in session cookie
            cookie_data = Signer(app.secret_key).sign(session.sid_s)

            response.set_cookie(key=app.config['SESSION_COOKIE_NAME'],
                                value=cookie_data,
                                expires=self.get_expiration_time(app, session),
                                domain=self.get_cookie_domain(app),
                                secure=app.config['SESSION_COOKIE_SECURE'],
                                httponly=app.config['SESSION_COOKIE_HTTPONLY'])


class KVSessionExtension(object):
    """Activates Flask-KVSession for an application.

    :param session_kvstore: An object supporting the
                            `simplekv.KeyValueStore` interface that session
                            data will be store in.
    :param app: The app to activate. If not `None`, this is essentially the
                same as calling :meth:`init_app` later."""
    key_regex = re.compile('^[0-9a-f]+_[0-9a-f]+$')

    def __init__(self, session_kvstore=None, app=None):
        self.default_kvstore = session_kvstore

        if app and session_kvstore:
            self.init_app(app)

    def cleanup_sessions(self, app=None):
        """Removes all expired session from the store.

        Periodically, this function should be called to remove sessions from
        the backend store that have expired, as they are not removed
        automatically.

        This function retrieves all session keys, checks they are older than
        ``PERMANENT_SESSION_LIFETIME`` and if so, removes them.

        Note that no distinction is made between non-permanent and permanent
        sessions.

        :param app: The app whose sessions should be cleaned up. If ``None``,
                    uses :py:attr:`flask.current_app`."""

        if not app:
            app = current_app
        for key in app.kvsession_store.keys():
            m = self.key_regex.match(key)
            now = datetime.utcnow()
            if m:
                # read id
                sid = SessionID.unserialize(key)

                # remove if expired
                if sid.has_expired(
                    app.config['PERMANENT_SESSION_LIFETIME'],
                    now
                ):
                    app.kvsession_store.delete(key)

    def init_app(self, app, session_kvstore=None):
        """Initialize application and KVSession.

        This will replace the session management of the application with
        Flask-KVSession's.

        :param app: The :class:`~flask.Flask` app to be initialized."""
        app.config.setdefault('SESSION_KEY_BITS', 64)
        app.config.setdefault('SESSION_RANDOM_SOURCE', SystemRandom())

        if not session_kvstore and not self.default_kvstore:
            raise ValueError('Must supply session_kvstore either on '
                             'construction or init_app().')

        # set store on app, either use default
        # or supplied argument
        app.kvsession_store = session_kvstore or self.default_kvstore

        app.session_interface = KVSessionInterface()

########NEW FILE########
__FILENAME__ = regenerate_on_first_request
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import flask
from simplekv.memory import DictStore
from flaskext.kvsession import KVSessionExtension

store = DictStore()

app = flask.Flask(__name__)
app.config['SECRET_KEY'] = 'topsecret'

KVSessionExtension(store, app)


@app.route('/')
def index():
    flask.session.regenerate()
    return 'OK'


app.run(debug=True)

########NEW FILE########
__FILENAME__ = test_flask_kvsession
#!/usr/bin/env python
# coding=utf8

from datetime import timedelta, datetime
import json
import sys

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

import time

from flask import Flask, session
from flask.ext.kvsession import SessionID, KVSessionExtension, KVSession
from itsdangerous import Signer

from simplekv.memory import DictStore


class TestSessionID(unittest.TestCase):
    def test_serialize(self):
        t = int(time.time())
        dt = datetime.utcfromtimestamp(t)
        sid = SessionID(1234, dt)

        self.assertEqual('%x_%x' % (1234, t), sid.serialize())

    def test_automatic_created_date(self):
        start = datetime.utcnow()
        sid = SessionID(0)
        end = datetime.utcnow()

        self.assertTrue(start <= sid.created <= end)

    def test_serialize_unserialize(self):
        dt = datetime(2011, 7, 9, 13, 14, 15)
        id = 59034

        sid = SessionID(id, dt)
        data = sid.serialize()

        SessionID(123)

        restored_sid = sid.unserialize(data)

        self.assertEqual(sid.id, restored_sid.id)
        self.assertEqual(sid.created, restored_sid.created)


def create_app(store):
    app = Flask(__name__)

    app.kvsession = KVSessionExtension(store, app)

    @app.route('/')
    def index():
        return 'nothing to see here, move along'

    @app.route('/store-in-session/<key>/<value>/')
    def store(key, value):
        session[key] = value
        return 'stored %r at %r' % (value, key)

    @app.route('/store-datetime/')
    def store_datetime():
        t = datetime(2011, 8, 10, 15, 46, 00)
        session['datetime_key'] = t
        return 'ok'

    @app.route('/delete-from-session/<key>/')
    def delete(key):
        del session[key]
        return 'deleted %r' % key

    @app.route('/destroy-session/')
    def destroy():
        session.destroy()
        return 'session destroyed'

    @app.route('/make-session-permanent/')
    def make_permanent():
        session.permanent = True
        return 'made session permanent'

    @app.route('/dump-session/')
    def dump():
        return json.dumps(dict(session))

    @app.route('/dump-datetime/')
    def dump_datetime():
        return str(session['datetime_key'])

    @app.route('/regenerate-session/')
    def regenerate():
        session.regenerate()
        return 'session regenerated'

    @app.route('/is-kvsession/')
    def is_kvsession():
        return str(isinstance(session._get_current_object(), KVSession))

    @app.route('/is-new-session/')
    def is_new_session():
        return str(session.new)

    return app


class TestSampleApp(unittest.TestCase):
    def setUp(self):
        self.store = DictStore()
        self.app = create_app(self.store)
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'devkey'

        self.client = self.app.test_client()

    def split_cookie(self, rv):
        signer = Signer(self.app.secret_key)
        cookie_data = rv.headers['Set-Cookie'].split(';', 1)[0]

        for cookie in cookie_data.split('&'):
            name, value = cookie_data.split('=')

            if name == self.app.session_cookie_name:
                unsigned_value = signer.unsign(value)
                return unsigned_value.split('_')

    def get_session_cookie(self):
        return self.client.cookie_jar.\
                 _cookies['localhost.local']['/']['session']

    def test_app_setup(self):
        pass

    def test_app_request_no_extras(self):
        rv = self.client.get('/')

        self.assertIn('move along', rv.data)

    def test_no_session_usage_uses_no_storage(self):
        self.client.get('/')
        self.client.get('/')

        self.assertEqual({}, self.store.d)

    def test_session_usage(self):
        self.client.get('/store-in-session/foo/bar/')

        self.assertNotEqual({}, self.store.d)

    def test_proper_cookie_received(self):
        rv = self.client.get('/store-in-session/bar/baz/')

        sid, created = self.split_cookie(rv)

        self.assertNotEqual(int(created, 16), 0)

        # check sid in store
        key = '%s_%s' % (sid, created)

        self.assertIn(key, self.store)

    def test_session_restores_properly(self):
        rv = self.client.get('/store-in-session/k1/value1/')

        rv = self.client.get('/store-in-session/k2/value2/')

        rv = self.client.get('/dump-session/')
        s = json.loads(rv.data)

        self.assertEqual(s['k1'], 'value1')
        self.assertEqual(s['k2'], 'value2')

    def test_manipulation_caught(self):
        rv = self.client.get('/store-in-session/k1/value1/')

        rv = self.client.get('/dump-session/')
        s = json.loads(rv.data)

        self.assertEqual(s['k1'], 'value1')

        # now manipulate cookie
        cookie = self.get_session_cookie()
        v_orig = cookie.value

        for i in xrange(len(v_orig)):
            broken_value = v_orig[:i] +\
                           ('a' if v_orig[i] != 'a' else 'b') +\
                           v_orig[i + 1:]
            cookie.value = broken_value

            rv = self.client.get('/dump-session/')
            s = json.loads(rv.data)

            self.assertEqual(s, {})

    def test_can_change_values(self):
        rv = self.client.get('/store-in-session/k1/value1/')

        rv = self.client.get('/dump-session/')
        s = json.loads(rv.data)

        self.assertEqual(s['k1'], 'value1')

        rv = self.client.get('/store-in-session/k1/value2/')

        rv = self.client.get('/dump-session/')
        s = json.loads(rv.data)

        self.assertEqual(s['k1'], 'value2')

    def test_can_delete_values(self):
        rv = self.client.get('/store-in-session/k1/value1/')
        rv = self.client.get('/store-in-session/k2/value2/')

        rv = self.client.get('/dump-session/')
        s = json.loads(rv.data)

        self.assertEqual(s['k1'], 'value1')
        self.assertEqual(s['k2'], 'value2')

        rv = self.client.get('/delete-from-session/k1/')

        rv = self.client.get('/dump-session/')
        s = json.loads(rv.data)

        self.assertNotIn('k1', s)
        self.assertEqual(s['k2'], 'value2')

    def test_can_destroy_sessions(self):
        rv = self.client.get('/store-in-session/k1/value1/')
        rv = self.client.get('/store-in-session/k2/value2/')

        rv = self.client.get('/dump-session/')
        s = json.loads(rv.data)

        self.assertEqual(s['k1'], 'value1')
        self.assertEqual(s['k2'], 'value2')

        # destroy session
        rv = self.client.get('/destroy-session/')
        self.assertIn('session destroyed', rv.data)

        rv = self.client.get('/dump-session/')
        s = json.loads(rv.data)

        self.assertEqual(s, {})

    def test_session_expires(self):
        # set expiration to 1 second
        self.app.permanent_session_lifetime = timedelta(seconds=1)

        rv = self.client.get('/store-in-session/k1/value1/')

        rv = self.client.get('/dump-session/')
        s = json.loads(rv.data)
        self.assertEqual(s['k1'], 'value1')

        rv = self.client.get('/make-session-permanent/')

        # assert that the session has a non-zero timestamp
        sid, created = self.split_cookie(rv)

        self.assertNotEqual(0, int(created, 16))

        rv = self.client.get('/dump-session/')
        s = json.loads(rv.data)
        self.assertEqual(s['k1'], 'value1')

        # sleep two seconds
        time.sleep(2)

        rv = self.client.get('/dump-session/')
        s = json.loads(rv.data)
        self.assertEqual(s, {})

    def test_session_cleanup_works(self):
        # set expiration to 1 second
        self.app.permanent_session_lifetime = timedelta(seconds=1)

        self.client.get('/store-in-session/k1/value1/')
        self.client.get('/make-session-permanent/')

        # assume there is a valid session, even after cleanup
        self.assertNotEqual({}, self.store.d)
        self.app.kvsession.cleanup_sessions(self.app)
        self.assertNotEqual({}, self.store.d)

        time.sleep(2)

        self.app.kvsession.cleanup_sessions(self.app)
        self.assertEqual({}, self.store.d)

    def test_can_regenerate_session(self):
        self.client.get('/store-in-session/k1/value1/')

        self.assertEqual(1, len(self.store.d))
        key = self.store.d.keys()[0]

        # now regenerate
        self.client.get('/regenerate-session/')

        self.assertEqual(1, len(self.store.d))
        new_key = self.store.d.keys()[0]

        self.assertNotEqual(new_key, key)

        rv = self.client.get('/dump-session/')
        s = json.loads(rv.data)
        self.assertEqual(s['k1'], 'value1')

    def test_works_without_secret_key_if_session_not_used(self):
        self.app = create_app(self.store)
        self.app.config['TESTING'] = True

        self.client = self.app.test_client()
        self.client.get('/')

    def test_correct_error_reporting_with_no_secret_key(self):
        self.app = create_app(self.store)
        self.app.config['TESTING'] = True

        self.client = self.app.test_client()
        with self.assertRaises(RuntimeError):
            self.client.get('/store-in-session/k1/value1/')

    def test_can_store_datetime(self):
        rv = self.client.get('/store-datetime/')
        rv = self.client.get('/dump-datetime/')
        self.assertEqual(rv.data, '2011-08-10 15:46:00')

    def test_missing_session_causes_new_empty_session(self):
        rv = self.client.get('/store-in-session/k1/value1/')
        rv = self.client.get('/dump-session/')
        s = json.loads(rv.data)
        self.assertEqual(s['k1'], 'value1')
        self.store.d.clear()
        rv = self.client.get('/dump-session/')

        self.assertEqual(rv.data, '{}')

        rv = self.client.get('/is-kvsession/')
        self.assertEqual('True', rv.data)

    def test_manipulated_session_causes_new_empty_session(self):
        rv = self.client.get('/store-in-session/k1/value1/')
        rv = self.client.get('/dump-session/')
        s = json.loads(rv.data)
        self.assertEqual(s['k1'], 'value1')

        cookie = self.get_session_cookie()
        cookie.value += 'x'

        rv = self.client.get('/dump-session/')

        self.assertEqual(rv.data, '{}')

        rv = self.client.get('/is-kvsession/')
        self.assertEqual('True', rv.data)

    def test_expired_session_causes_new_empty_session(self):
        self.app.permanent_session_lifetime = timedelta(seconds=1)

        rv = self.client.get('/store-in-session/k1/value1/')
        rv = self.client.get('/make-session-permanent/')

        # assert that the session has a non-zero timestamp
        sid, created = self.split_cookie(rv)

        self.assertNotEqual(0, int(created, 16))

        rv = self.client.get('/dump-session/')
        s = json.loads(rv.data)
        self.assertEqual(s['k1'], 'value1')

        # sleep two seconds
        time.sleep(2)

        # we should have a new session now
        rv = self.client.get('/is-new-session/')
        self.assertEqual(str(True), rv.data)

        rv = self.client.get('/dump-session/')
        s = json.loads(rv.data)
        self.assertEqual(s, {})

    def test_expired_made_permanent_causes_no_exception(self):
        self.app.permanent_session_lifetime = timedelta(seconds=1)

        rv = self.client.get('/store-in-session/k1/value1/')

        # sleep two seconds
        time.sleep(2)
        rv = self.client.get('/make-session-permanent/')

    def test_permanent_session_cookies_are_permanent(self):
        rv = self.client.get('/store-in-session/k1/value1/')

        sid, created = self.split_cookie(rv)

        # session cookie
        self.assertIsNone(self.get_session_cookie().expires)

        rv = self.client.get('/make-session-permanent/')

        # now it needs to be permanent
        self.assertIsNotNone(self.get_session_cookie().expires)

    def test_new_delayed_construction(self):
        app = Flask(__name__)

        ext = KVSessionExtension()

        with self.assertRaises(ValueError):
            ext.init_app(app)

        ext.init_app(app, self.store)

        self.assertIs(self.store, app.kvsession_store)

    def test_new_delayed_construction_with_default(self):
        app = Flask(__name__)

        ext = KVSessionExtension(self.store)
        ext.init_app(app)

        self.assertIs(self.store, app.kvsession_store)

class TestCookieFlags(unittest.TestCase):
    def setUp(self):
        self.store = DictStore()
        self.app = create_app(self.store)
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'devkey'

    def get_session_cookie(self, client):
        return client.cookie_jar._cookies['localhost.local']['/']['session']

    def test_secure_false(self):
        self.app.config['SESSION_COOKIE_SECURE'] = False
        client = self.app.test_client()

        client.get('/store-in-session/k1/value1/')
        cookie = self.get_session_cookie(client)
        self.assertEqual(cookie.secure, False)

    def test_secure_true(self):
        self.app.config['SESSION_COOKIE_SECURE'] = True
        client = self.app.test_client()

        client.get('/store-in-session/k1/value1/')
        cookie = self.get_session_cookie(client)
        self.assertEqual(cookie.secure, True)

    def test_httponly_false(self):
        self.app.config['SESSION_COOKIE_HTTPONLY'] = False
        client = self.app.test_client()

        client.get('/store-in-session/k1/value1/')
        cookie = self.get_session_cookie(client)
        self.assertEqual(cookie.has_nonstandard_attr('HttpOnly'), False)

    def test_httponly_true(self):
        self.app.config['SESSION_COOKIE_HTTPONLY'] = True
        client = self.app.test_client()

        client.get('/store-in-session/k1/value1/')
        cookie = self.get_session_cookie(client)
        self.assertEqual(cookie.has_nonstandard_attr('HttpOnly'), True)



# the code below should, in theory, trigger the problem of regenerating a
# session before it has been created, however, it doesn't
class TestFirstRequestRegenerate(unittest.TestCase):
    def test_first_request(self):
        store = DictStore()

        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'topsecret'

        KVSessionExtension(store, app)

        @app.route('/')
        def index():
            session.regenerate()
            return 'OK'

        client = app.test_client()
        client.get('/')

########NEW FILE########
