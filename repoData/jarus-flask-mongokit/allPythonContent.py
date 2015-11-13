__FILENAME__ = conf
# -*- coding: utf-8 -*-
#
# Flask-MongoKit documentation build configuration file, created by
# sphinx-quickstart on Tue Aug 16 21:56:43 2011.
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
sys.path.append(os.path.abspath('_themes'))

# -- General configuration -----------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be extensions
# coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = ['sphinx.ext.autodoc', 'sphinx.ext.intersphinx', 'sphinx.ext.todo']

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The encoding of source files.
#source_encoding = 'utf-8-sig'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = u'Flask-MongoKit'
copyright = u'2011, Christoph Heer'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = '0.2'
# The full version, including alpha/beta/rc tags.
release = '0.2'

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

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
html_theme_options = {
    'github_fork': 'jarus/flask-mongokit',
    'index_logo': 'flask-mongokit.png'
}

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
htmlhelp_basename = 'Flask-MongoKitdoc'


# -- Options for LaTeX output --------------------------------------------------

# The paper size ('letter' or 'a4').
#latex_paper_size = 'letter'

# The font size ('10pt', '11pt' or '12pt').
#latex_font_size = '10pt'

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass [howto/manual]).
latex_documents = [
  ('index', 'Flask-MongoKit.tex', u'Flask-MongoKit Documentation',
   u'Christoph Heer', 'manual'),
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
    ('index', 'flask-mongokit', u'Flask-MongoKit Documentation',
     [u'Christoph Heer'], 1)
]

# Example configuration for intersphinx: refer to the Python standard library.
intersphinx_mapping = {
    'python': ('http://docs.python.org/', None),
    'flask': ('http://flask.pocoo.org/docs/', None),
    'mongokit': ('http://namlook.github.com/mongokit/', None),
    'pymongo': ('http://api.mongodb.org/python/current/', None),
    'bson': ('http://api.mongodb.org/python/current/', None),
}
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
__FILENAME__ = todo
from datetime import datetime

from flask import Flask, request, render_template, redirect, url_for
from flask.ext.mongokit import MongoKit, Document

app = Flask(__name__)


class Task(Document):
    __collection__ = 'tasks'
    structure = {
        'title': unicode,
        'text': unicode,
        'creation': datetime,
    }
    required_fields = ['title', 'creation']
    default_values = {'creation': datetime.utcnow()}
    use_dot_notation = True

db = MongoKit(app)
db.register([Task])


@app.route('/')
def show_all():
    tasks = db.Task.find()
    return render_template('list.html', tasks=tasks)


@app.route('/<ObjectId:task_id>')
def show_task(task_id):
    task = db.Task.get_from_id(task_id)
    return render_template('task.html', task=task)


@app.route('/new', methods=["GET", "POST"])
def new_task():
    if request.method == 'POST':
        task = db.Task()
        task.title = request.form['title']
        task.text = request.form['text']
        task.save()
        return redirect(url_for('show_all'))
    return render_template('new.html')

if __name__ == '__main__':
    app.run(debug=True)

########NEW FILE########
__FILENAME__ = flask_mongokit
# -*- coding: utf-8 -*-
"""
    flask.ext.mongokit
    ~~~~~~~~~~~~~~~~~~

    Flask-MongoKit simplifies to use MongoKit, a powerful MongoDB ORM in Flask
    applications.

    :copyright: 2011 by Christoph Heer <Christoph.Heer@googlemail.com
    :license: BSD, see LICENSE for more details.
"""

from __future__ import absolute_import

import bson
from mongokit import Connection, Database, Collection, Document
from pymongo.errors import OperationFailure

from werkzeug.routing import BaseConverter
from flask import abort, _request_ctx_stack

try: # pragma: no cover
    from flask import _app_ctx_stack
    ctx_stack = _app_ctx_stack
except ImportError: # pragma: no cover
    ctx_stack = _request_ctx_stack

class AuthenticationIncorrect(Exception):
    pass

class BSONObjectIdConverter(BaseConverter):
    """A simple converter for the RESTfull URL routing system of Flask.

    .. code-block:: python

        @app.route('/<ObjectId:task_id>')
        def show_task(task_id):
            task = db.Task.get_from_id(task_id)
            return render_template('task.html', task=task)

    It checks the validate of the id and converts it into a
    :class:`bson.objectid.ObjectId` object. The converter will be
    automatically registered by the initialization of
    :class:`~flask.ext.mongokit.MongoKit` with keyword :attr:`ObjectId`.
    """

    def to_python(self, value):
        try:
            return bson.ObjectId(value)
        except bson.errors.InvalidId:
            raise abort(400)

    def to_url(self, value):
        return str(value)


class Document(Document):
    def get_or_404(self, id):
        """This method get one document over the _id field. If there no
        document with this id then it will raised a 404 error.

        :param id: The id from the document. The most time there will be
                   an :class:`bson.objectid.ObjectId`.
        """
        doc = self.get_from_id(id)
        if doc is None:
            abort(404)
        else:
            return doc

    def find_one_or_404(self, *args, **kwargs):
        """This method get one document over normal query parameter like
        :meth:`~flask.ext.mongokit.Document.find_one` but if there no document
        then it will raise a 404 error.
        """

        doc = self.find_one(*args, **kwargs)
        if doc is None:
            abort(404)
        else:
            return doc


class MongoKit(object):
    """This class is used to integrate `MongoKit`_ into a Flask application.

    :param app: The Flask application will be bound to this MongoKit instance.
                If an app is not provided at initialization time than it
                must be provided later by calling :meth:`init_app` manually.

    .. _MongoKit: http://namlook.github.com/mongokit/
    """

    def __init__(self, app=None):
        #: :class:`list` of :class:`mongokit.Document`
        #: which will be automated registed at connection
        self.registered_documents = []

        if app is not None:
            self.app = app
            self.init_app(self.app)
        else:
            self.app = None

    def init_app(self, app):
        """This method connect your ``app`` with this extension. Flask-
        MongoKit will now take care about to open and close the connection to
        your MongoDB.

        Also it registers the
        :class:`flask.ext.mongokit.BSONObjectIdConverter`
        as a converter with the key word **ObjectId**.

        :param app: The Flask application will be bound to this MongoKit
                    instance.
        """
        app.config.setdefault('MONGODB_HOST', '127.0.0.1')
        app.config.setdefault('MONGODB_PORT', 27017)
        app.config.setdefault('MONGODB_DATABASE', 'flask')
        app.config.setdefault('MONGODB_SLAVE_OKAY', False)
        app.config.setdefault('MONGODB_USERNAME', None)
        app.config.setdefault('MONGODB_PASSWORD', None)

        # 0.9 and later
        # no coverage check because there is everytime only one
        if hasattr(app, 'teardown_appcontext'): # pragma: no cover
            app.teardown_appcontext(self._teardown_request)
        # 0.7 to 0.8
        elif hasattr(app, 'teardown_request'): # pragma: no cover
            app.teardown_request(self._teardown_request)
        # Older Flask versions
        else: # pragma: no cover
            app.after_request(self._teardown_request)

        # register extension with app only to say "I'm here"
        app.extensions = getattr(app, 'extensions', {})
        app.extensions['mongokit'] = self

        app.url_map.converters['ObjectId'] = BSONObjectIdConverter

        self.app = app

    def register(self, documents):
        """Register one or more :class:`mongokit.Document` instances to the
        connection.

        Can be also used as a decorator on documents:

        .. code-block:: python

            db = MongoKit(app)

            @db.register
            class Task(Document):
                structure = {
                   'title': unicode,
                   'text': unicode,
                   'creation': datetime,
                }

        :param documents: A :class:`list` of :class:`mongokit.Document`.
        """

        #enable decorator usage as in mongokit.Connection
        decorator = None
        if not isinstance(documents, (list, tuple, set, frozenset)):
            # we assume that the user used this as a decorator
            # using @register syntax or using db.register(SomeDoc)
            # we stock the class object in order to return it later
            decorator = documents
            documents = [documents]

        for document in documents:
            if document not in self.registered_documents:
                self.registered_documents.append(document)

        if decorator is None:
            return self.registered_documents
        else:
            return decorator

    def connect(self):
        """Connect to the MongoDB server and register the documents from
        :attr:`registered_documents`. If you set ``MONGODB_USERNAME`` and
        ``MONGODB_PASSWORD`` then you will be authenticated at the
        ``MONGODB_DATABASE``. You can also enable timezone awareness if
        you set to True ``MONGODB_TZ_AWARE`.
        """
        if self.app is None:
            raise RuntimeError('The flask-mongokit extension was not init to '
                               'the current application.  Please make sure '
                               'to call init_app() first.')

        ctx = ctx_stack.top
        mongokit_connection = getattr(ctx, 'mongokit_connection', None)
        if mongokit_connection is None:
            ctx.mongokit_connection = Connection(
                host=ctx.app.config.get('MONGODB_HOST'),
                port=ctx.app.config.get('MONGODB_PORT'),
                slave_okay=ctx.app.config.get('MONGODB_SLAVE_OKAY'),
                tz_aware=ctx.app.config.get('MONGODB_TZ_AWARE', False)
            )

            ctx.mongokit_connection.register(self.registered_documents)

        mongokit_database = getattr(ctx, 'mongokit_database', None)
        if mongokit_database is None:
            ctx.mongokit_database = Database(
                ctx.mongokit_connection,
                ctx.app.config.get('MONGODB_DATABASE')
            )

        if ctx.app.config.get('MONGODB_USERNAME') is not None:
            try:
                auth_success = ctx.mongokit_database.authenticate(
                    ctx.app.config.get('MONGODB_USERNAME'),
                    ctx.app.config.get('MONGODB_PASSWORD')
                )
            except OperationFailure:
                auth_success = False

            if not auth_success:
                raise AuthenticationIncorrect('Server authentication failed')

    @property
    def connected(self):
        """Connection status to your MongoDB."""
        ctx = ctx_stack.top
        return getattr(ctx, 'mongokit_connection', None) is not None

    def disconnect(self):
        """Close the connection to your MongoDB."""
        if self.connected:
            ctx = ctx_stack.top
            ctx.mongokit_connection.disconnect()
            del ctx.mongokit_connection
            del ctx.mongokit_database

    def _teardown_request(self, response):
        self.disconnect()
        return response

    def __getattr__(self, name, **kwargs):
        if not self.connected:
            self.connect()

        mongokit_database = getattr(ctx_stack.top, "mongokit_database")
        return getattr(mongokit_database, name)

    def __getitem__(self, name):
        if not self.connected:
            self.connect()

        mongokit_database = getattr(ctx_stack.top, "mongokit_database")
        return mongokit_database[name]

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
        cov = coverage(source=['flask_mongokit'])
        cov.start()

    from tests import suite
    result = unittest.TextTestRunner(verbosity=2).run(suite())
    if not result.wasSuccessful():
        sys.exit(1)

    if coverage_available:
        cov.stop()

        print "\nCode Coverage"
        cov.report()
        cov.html_report(directory='cover')
    else:
        print("\nTipp:\n\tUse 'pip install coverage' to get great code "
              "coverage stats")

if __name__ == '__main__':
    run()

########NEW FILE########
__FILENAME__ = test_base
# -*- coding: utf-8 -*-

import unittest
import os

from datetime import datetime

from flask import Flask
from flask_mongokit import MongoKit, BSONObjectIdConverter, \
                           Document, Collection, AuthenticationIncorrect
from werkzeug.exceptions import BadRequest, NotFound
from bson import ObjectId
from pymongo import Connection
from pymongo.collection import Collection

class BlogPost(Document):
    __collection__ = "posts"
    structure = {
        'title': unicode,
        'body': unicode,
        'author': unicode,
        'date_creation': datetime,
        'rank': int,
        'tags': [unicode],
    }
    required_fields = ['title', 'author', 'date_creation']
    default_values = {'rank': 0, 'date_creation': datetime.utcnow}
    use_dot_notation = True

def create_app():
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['MONGODB_DATABASE'] = 'flask_testing'
    
    maybe_conf_file = os.path.join(os.getcwd(), "config_test.cfg")
    if os.path.exists(maybe_conf_file):
        app.config.from_pyfile(maybe_conf_file)
    
    return app

class TestCaseContextIndependent(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.db = MongoKit(self.app)

    def tearDown(self):
        pass
    
    def test_register_document(self):
        self.db.register([BlogPost])
        
        assert len(self.db.registered_documents) > 0
        assert self.db.registered_documents[0] == BlogPost
    
    def test_bson_object_id_converter(self):
        converter = BSONObjectIdConverter("/")
    
        self.assertRaises(BadRequest, converter.to_python, ("132"))
        assert converter.to_python("4e4ac5cfffc84958fa1f45fb") == \
               ObjectId("4e4ac5cfffc84958fa1f45fb")
        assert converter.to_url(ObjectId("4e4ac5cfffc84958fa1f45fb")) == \
               "4e4ac5cfffc84958fa1f45fb"

    def test_is_extension_registerd(self):
        assert hasattr(self.app, 'extensions')
        assert 'mongokit' in self.app.extensions
        assert self.app.extensions['mongokit'] == self.db

class BaseTestCaseInitAppWithContext():
    def setUp(self):
        self.app = create_app()

    def test_init_later(self):
        self.db = MongoKit()
        self.assertRaises(RuntimeError, self.db.connect)

        self.db.init_app(self.app)
        self.db.connect()
        assert self.db.connected

    def test_init_immediately(self):
        self.db = MongoKit(self.app)
        self.db.connect()
        assert self.db.connected

class BaseTestCaseWithContext():

    def test_initialization(self):
        assert isinstance(self.db, MongoKit)
        assert self.db.name == self.app.config['MONGODB_DATABASE']
        assert isinstance(self.db.test, Collection)

    def test_property_connected(self):
        assert not self.db.connected

        self.db.connect()
        assert self.db.connected

        self.db.disconnect()
        assert not self.db.connected
        
        self.db.collection_names()
        assert self.db.connected
    
    def test_subscriptable(self):
        assert isinstance(self.db['test'], Collection)
        assert self.db['test'] == self.db.test

    def test_save_and_find_document(self):
        self.db.register([BlogPost])

        assert len(self.db.registered_documents) > 0
        assert self.db.registered_documents[0] == BlogPost

        post = self.db.BlogPost()
        post.title = u"Flask-MongoKit"
        post.body = u"Flask-MongoKit is a layer between Flask and MongoKit"
        post.author = u"Christoph Heer"
        post.save()

        assert self.db.BlogPost.find().count() > 0
        rec_post = self.db.BlogPost.find_one({'title': u"Flask-MongoKit"})
        assert rec_post.title == post.title
        assert rec_post.body == rec_post.body
        assert rec_post.author == rec_post.author

    def test_get_or_404(self):
        self.db.register([BlogPost])

        assert len(self.db.registered_documents) > 0
        assert self.db.registered_documents[0] == BlogPost

        post = self.db.BlogPost()
        post.title = u"Flask-MongoKit"
        post.body = u"Flask-MongoKit is a layer between Flask and MongoKit"
        post.author = u"Christoph Heer"
        post.save()

        assert self.db.BlogPost.find().count() > 0
        assert "get_or_404" in dir(self.db.BlogPost)
        try:
            self.db.BlogPost.get_or_404(post['_id'])
        except NotFound:
            self.fail("There should be a document with this id")
        self.assertRaises(NotFound, self.db.BlogPost.get_or_404, ObjectId())

    def test_find_one_or_404(self):
        self.db.register([BlogPost])

        assert len(self.db.registered_documents) > 0
        assert self.db.registered_documents[0] == BlogPost

        post = self.db.BlogPost()
        post.title = u"Flask-MongoKit"
        post.body = u"Flask-MongoKit is a layer between Flask and MongoKit"
        post.author = u"Christoph Heer"
        post.save()

        assert self.db.BlogPost.find().count() > 0
        assert "find_one_or_404" in dir(self.db.BlogPost)
        try:
            self.db.BlogPost.find_one_or_404({'title': u'Flask-MongoKit'})
        except NotFound:
            self.fail("There should be a document with this title")
        self.assertRaises(NotFound, self.db.BlogPost.find_one_or_404,
                          {'title': u'Flask is great'})

class BaseTestCaseWithAuth():
    def setUp(self):
        db = 'flask_testing_auth'
        conn = Connection()
        conn[db].add_user('test', 'test')
        
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['MONGODB_DATABASE'] = db
        
        self.db = MongoKit(self.app)

    def test_correct_login(self):
        self.app.config['MONGODB_USERNAME'] = 'test'
        self.app.config['MONGODB_PASSWORD'] = 'test'
        
        self.db.connect()
    
    def test_incorrect_login(self):
        self.app.config['MONGODB_USERNAME'] = 'fuu'
        self.app.config['MONGODB_PASSWORD'] = 'baa'
        
        self.assertRaises(AuthenticationIncorrect, self.db.connect)

class BaseTestCaseMultipleApps():

    def setUp(self):
        self.app_1 = create_app()
        self.app_1.config['MONGODB_DATABASE'] = 'app_1'
        
        self.app_2 = create_app()
        self.app_2.config['MONGODB_DATABASE'] = 'app_2'
        
        assert self.app_1 != self.app_2
        
        self.db = MongoKit()
        self.db.init_app(self.app_1)
        self.db.init_app(self.app_2)

    def tearDown(self):
        self.pop_ctx()

    def push_ctx(self):
        raise NotImplementedError
    
    def pop_ctx(self):
        raise NotImplementedError

    def test_app_1(self):
        self.push_ctx(self.app_1)
        
        self.db.connect()
        assert self.db.connected
        assert self.db.name == 'app_1'
        assert self.db.name != 'app_2'
        
    def test_app_2(self):
        self.push_ctx(self.app_2)
        
        self.db.connect()
        assert self.db.connected
        assert self.db.name != 'app_1'
        assert self.db.name == 'app_2'

class TestCaseInitAppWithRequestContext(BaseTestCaseInitAppWithContext, unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        
        self.ctx = self.app.test_request_context('/')
        self.ctx.push()
        
    def tearDown(self):
        self.ctx.pop()

class TestCaseWithRequestContext(BaseTestCaseWithContext, unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.db = MongoKit(self.app)
    
        self.ctx = self.app.test_request_context('/')
        self.ctx.push()
    
    def tearDown(self):
        self.ctx.pop()

class TestCaseWithRequestContextAuth(BaseTestCaseWithAuth, unittest.TestCase):
    def setUp(self):
        super(TestCaseWithRequestContextAuth, self).setUp()
        
        self.ctx = self.app.test_request_context('/')
        self.ctx.push()
    
    def tearDown(self):
        self.ctx.pop()

class TestCaseMultipleAppsWithRequestContext(BaseTestCaseMultipleApps, unittest.TestCase):
    def push_ctx(self, app):
        self.ctx = app.test_request_context('/')
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

# Only testing is the flask version support app context (since flask v0.9)
if hasattr(Flask, "app_context"):
    class TestCaseInitAppWithAppContext(BaseTestCaseInitAppWithContext, unittest.TestCase):
        def setUp(self):
            self.app = create_app()
    
            self.ctx = self.app.app_context()
            self.ctx.push()
    
        def tearDown(self):
            self.ctx.pop()
    
    class TestCaseWithAppContext(BaseTestCaseWithContext, unittest.TestCase):
        def setUp(self):
            self.app = create_app()
            self.db = MongoKit(self.app)
            
            self.ctx = self.app.app_context()
            self.ctx.push()
        
        def tearDown(self):
            self.ctx.pop()
    
    class TestCaseWithAppContextAuth(BaseTestCaseWithAuth, unittest.TestCase):
        def setUp(self):
            super(TestCaseWithAppContextAuth, self).setUp()
    
            self.ctx = self.app.app_context()
            self.ctx.push()
    
        def tearDown(self):
            self.ctx.pop()
    
    class TestCaseMultipleAppsWithAppContext(BaseTestCaseMultipleApps, unittest.TestCase):
        def push_ctx(self, app):
            self.ctx = app.app_context()
            self.ctx.push()
         
        def tearDown(self):
            self.ctx.pop()

if __name__ == '__main__':
    unittest.main()

########NEW FILE########
__FILENAME__ = test_decorator_registration
from flask_mongokit import Document

def decorator_registration(self):

    @self.db.register
    class DecoratorRegistered(Document):
        pass

    assert len(self.db.registered_documents) > 0
    assert self.db.registered_documents[0] == DecoratorRegistered
########NEW FILE########
__FILENAME__ = __main__
from run import run

if __name__ == '__main__':
    run()
########NEW FILE########
