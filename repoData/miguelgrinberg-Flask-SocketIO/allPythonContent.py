__FILENAME__ = conf
# -*- coding: utf-8 -*-
#
# Flask-SocketIO documentation build configuration file, created by
# sphinx-quickstart on Sun Feb  9 12:36:23 2014.
#
# This file is execfile()d with the current directory set to its
# containing dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out
# serve to show the default.

import sys
import os

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
sys.path.insert(0, os.path.abspath('..'))
sys.path.append(os.path.abspath('_themes'))

# -- General configuration ------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = []

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The encoding of source files.
#source_encoding = 'utf-8-sig'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = u'Flask-SocketIO'
copyright = u'2014, Miguel Grinberg'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
#version = '0.1.0'
# The full version, including alpha/beta/rc tags.
#release = '0.1.0'

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

# The reST default role (used for this markup: `text`) to use for all
# documents.
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

# If true, keep warnings as "system message" paragraphs in the built documents.
#keep_warnings = False


# -- Options for HTML output ----------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
html_theme = 'flask_small'

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
html_theme_options = {
    'index_logo': 'logo.png',
    'github_fork': 'miguelgrinberg/Flask-SocketIO'
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

# Add any extra paths that contain custom files (such as robots.txt or
# .htaccess) here, relative to this directory. These files are copied
# directly to the root of the documentation.
#html_extra_path = []

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
htmlhelp_basename = 'Flask-SocketIOdoc'


# -- Options for LaTeX output ---------------------------------------------

latex_elements = {
# The paper size ('letterpaper' or 'a4paper').
#'papersize': 'letterpaper',

# The font size ('10pt', '11pt' or '12pt').
#'pointsize': '10pt',

# Additional stuff for the LaTeX preamble.
#'preamble': '',
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title,
#  author, documentclass [howto, manual, or own class]).
latex_documents = [
  ('index', 'Flask-SocketIO.tex', u'Flask-SocketIO Documentation',
   u'Miguel Grinberg', 'manual'),
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


# -- Options for manual page output ---------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    ('index', 'flask-socketio', u'Flask-SocketIO Documentation',
     [u'Miguel Grinberg'], 1)
]

# If true, show URL addresses after external links.
#man_show_urls = False


# -- Options for Texinfo output -------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
  ('index', 'Flask-SocketIO', u'Flask-SocketIO Documentation',
   u'Miguel Grinberg', 'Flask-SocketIO', 'One line description of project.',
   'Miscellaneous'),
]

# Documents to append as an appendix to all manuals.
#texinfo_appendices = []

# If false, no module index is generated.
#texinfo_domain_indices = True

# How to display URL addresses: 'footnote', 'no', or 'inline'.
#texinfo_show_urls = 'footnote'

# If true, do not generate a @detailmenu in the "Top" node's menu.
#texinfo_no_detailmenu = False

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
__FILENAME__ = app
from gevent import monkey
monkey.patch_all()

import time
from threading import Thread
from flask import Flask, render_template, session, request
from flask.ext.socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
app.debug = True
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)
thread = None


def background_thread():
    """Example of how to send server generated events to clients."""
    count = 0
    while True:
        time.sleep(10)
        count += 1
        socketio.emit('my response',
                      {'data': 'Server generated event', 'count': count},
                      namespace='/test')


@app.route('/')
def index():
    global thread
    if thread is None:
        thread = Thread(target=background_thread)
        thread.start()
    return render_template('index.html')


@socketio.on('my event', namespace='/test')
def test_message(message):
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my response',
         {'data': message['data'], 'count': session['receive_count']})


@socketio.on('my broadcast event', namespace='/test')
def test_message(message):
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my response',
         {'data': message['data'], 'count': session['receive_count']},
         broadcast=True)


@socketio.on('join', namespace='/test')
def join(message):
    join_room(message['room'])
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my response',
         {'data': 'In rooms: ' + ', '.join(request.namespace.rooms),
          'count': session['receive_count']})


@socketio.on('leave', namespace='/test')
def leave(message):
    leave_room(message['room'])
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my response',
         {'data': 'In rooms: ' + ', '.join(request.namespace.rooms),
          'count': session['receive_count']})


@socketio.on('my room event', namespace='/test')
def send_room_message(message):
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my response',
         {'data': message['data'], 'count': session['receive_count']},
         room=message['room'])


@socketio.on('connect', namespace='/test')
def test_connect():
    emit('my response', {'data': 'Connected', 'count': 0})


@socketio.on('disconnect', namespace='/test')
def test_disconnect():
    print('Client disconnected')


if __name__ == '__main__':
    socketio.run(app)

########NEW FILE########
__FILENAME__ = test_client
"""
This module contains a collection of auxiliary mock objects used by
unit tests.
"""


class TestServer(object):
    counter = 0

    def __init__(self):
        self.sockets = {}

    def new_socket(self):
        socket = TestSocket(self, self.counter)
        self.sockets[self.counter] = socket
        self.counter += 1
        return socket

    def remove_socket(self, socket):
        for id, s in self.sockets.items():
            if s == socket:
                del self.sockets[id]
                return


class TestSocket(object):
    def __init__(self, server, sessid):
        self.server = server
        self.sessid = sessid
        self.active_ns = {}

    def __getitem__(self, ns_name):
        return self.active_ns[ns_name]


class TestBaseNamespace(object):
    def __init__(self, ns_name, socket, request=None):
        from werkzeug.test import EnvironBuilder
        self.environ = EnvironBuilder().get_environ()
        self.ns_name = ns_name
        self.socket = socket
        self.request = request
        self.session = {}
        self.received = []
        self.initialize()

    def initialize(self):
        pass

    def recv_connect(self):
        pass

    def recv_disconnect(self):
        pass

    def emit(self, event, *args, **kwargs):
        self.received.append({'name': event, 'args': args})
        callback = kwargs.pop('callback', None)
        if callback:
            callback()

    def send(self, message, json=False, callback=None):
        if not json:
            self.received.append({'name': 'message', 'args': message})
        else:
            self.received.append({'name': 'json', 'args': message})
        if callback:
            callback()


class SocketIOTestClient(object):
    server = TestServer()

    def __init__(self, app, socketio, namespace=''):
        self.socketio = socketio
        self.socketio.server = self.server
        self.socket = self.server.new_socket()
        self.connect(app, namespace)

    def __del__(self):
        self.server.remove_socket(self.socket)

    def connect(self, app, namespace=None):
        if self.socket.active_ns.get(namespace):
            self.disconnect(namespace)
        if namespace is None or namespace == '/':
            namespace = ''
        self.socket.active_ns[namespace] = \
            self.socketio.get_namespaces(
                TestBaseNamespace)[namespace](namespace, self.socket, app)
        self.socket[namespace].recv_connect()

    def disconnect(self, namespace=None):
        if namespace is None or namespace == '/':
            namespace = ''
        if self.socket[namespace]:
            self.socket[namespace].recv_disconnect()
            del self.socket.active_ns[namespace]

    def emit(self, event, *args, **kwargs):
        namespace = kwargs.pop('namespace', None)
        if namespace is None or namespace == '/':
            namespace = ''
        return self.socket[namespace].process_event({'name': event, 'args': args})

    def send(self, message, json=False, namespace=None):
        if namespace is None or namespace == '/':
            namespace = ''
        if not json:
            return self.socket[namespace].recv_message(message)
        else:
            return self.socket[namespace].recv_json(message)

    def get_received(self, namespace=None):
        if namespace is None or namespace == '/':
            namespace = ''
        received = self.socket[namespace].received
        self.socket[namespace].received = []
        return received

########NEW FILE########
__FILENAME__ = test_socketio
from gevent import monkey
monkey.patch_all()

import unittest
import coverage

cov = coverage.coverage()
cov.start()

from flask import Flask, session
from flask.ext.socketio import SocketIO, send, emit, join_room, leave_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'
socketio = SocketIO(app)
disconnected = None

@socketio.on('connect')
def on_connect():
    send('connected')
    session['a'] = 'b'

@socketio.on('disconnect')
def on_connect():
    global disconnected
    disconnected = '/'

@socketio.on('connect', namespace='/test')
def on_connect_test():
    send('connected-test')

@socketio.on('disconnect', namespace='/test')
def on_disconnect_test():
    global disconnected
    disconnected = '/test'

@socketio.on('message')
def on_message(message):
    send(message)

@socketio.on('json')
def on_json(data):
    send(data, json=True, broadcast=True)

@socketio.on('message', namespace='/test')
def on_message_test(message):
    send(message)

@socketio.on('json', namespace='/test')
def on_json_test(data):
    send(data, json=True, namespace='/test')

@socketio.on('my custom event')
def on_custom_event(data):
    emit('my custom response', data)

@socketio.on('my custom namespace event', namespace='/test')
def on_custom_event_test(data):
    emit('my custom namespace response', data, namespace='/test')

@socketio.on('my custom broadcast event')
def on_custom_event_broadcast(data):
    emit('my custom response', data, broadcast=True)

@socketio.on('my custom broadcast namespace event', namespace='/test')
def on_custom_event_broadcast_test(data):
    emit('my custom namespace response', data, namespace='/test',
         broadcast=True)

@socketio.on('join room')
def on_join_room(data):
    join_room(data['room'])

@socketio.on('leave room')
def on_leave_room(data):
    leave_room(data['room'])

@socketio.on('join room', namespace='/test')
def on_join_room(data):
    join_room(data['room'])

@socketio.on('leave room', namespace='/test')
def on_leave_room(data):
    leave_room(data['room'])

@socketio.on('my room event')
def on_room_event(data):
    room = data.pop('room')
    emit('my room response', data, room=room)

@socketio.on('my room namespace event', namespace='/test')
def on_room_namespace_event(data):
    room = data.pop('room')
    send('room message', room=room)


class TestSocketIO(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        cov.stop()
        cov.report(include='flask_socketio/__init__.py')

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_connect(self):
        client = socketio.test_client(app)
        received = client.get_received()
        self.assertTrue(len(received) == 1)
        self.assertTrue(received[0]['args'] == 'connected')
        client.disconnect()

    def test_connect_namespace(self):
        client = socketio.test_client(app, namespace='/test')
        received = client.get_received('/test')
        self.assertTrue(len(received) == 1)
        self.assertTrue(received[0]['args'] == 'connected-test')
        client.disconnect(namespace='/test')

    def test_disconnect(self):
        global disconnected
        disconnected = None
        client = socketio.test_client(app)
        client.disconnect()
        self.assertTrue(disconnected == '/')

    def test_disconnect_namespace(self):
        global disconnected
        disconnected = None
        client = socketio.test_client(app, namespace='/test')
        client.disconnect('/test')
        self.assertTrue(disconnected == '/test')

    def test_send(self):
        client = socketio.test_client(app)
        client.get_received()  # clean received
        client.send('echo this message back')
        received = client.get_received()
        self.assertTrue(len(received) == 1)
        self.assertTrue(received[0]['args'] == 'echo this message back')

    def test_send_json(self):
        client1 = socketio.test_client(app)
        client2 = socketio.test_client(app)
        client1.get_received()  # clean received
        client2.get_received()  # clean received
        client1.send({'a': 'b'}, json=True)
        received = client1.get_received()
        self.assertTrue(len(received) == 1)
        self.assertTrue(received[0]['args']['a'] == 'b')
        received = client2.get_received()
        self.assertTrue(len(received) == 1)
        self.assertTrue(received[0]['args']['a'] == 'b')

    def test_send_namespace(self):
        client = socketio.test_client(app, namespace='/test')
        client.get_received('/test')  # clean received
        client.send('echo this message back', namespace='/test')
        received = client.get_received('/test')
        self.assertTrue(len(received) == 1)
        self.assertTrue(received[0]['args'] == 'echo this message back')

    def test_send_json_namespace(self):
        client = socketio.test_client(app, namespace='/test')
        client.get_received('/test')  # clean received
        client.send({'a': 'b'}, json=True, namespace='/test')
        received = client.get_received('/test')
        self.assertTrue(len(received) == 1)
        self.assertTrue(received[0]['args']['a'] == 'b')

    def test_emit(self):
        client = socketio.test_client(app)
        client.get_received()  # clean received
        client.emit('my custom event', {'a': 'b'})
        received = client.get_received()
        self.assertTrue(len(received) == 1)
        self.assertTrue(len(received[0]['args']) == 1)
        self.assertTrue(received[0]['name'] == 'my custom response')
        self.assertTrue(received[0]['args'][0]['a'] == 'b')

    def test_emit_namespace(self):
        client = socketio.test_client(app, namespace='/test')
        client.get_received('/test')  # clean received
        client.emit('my custom namespace event', {'a': 'b'}, namespace='/test')
        received = client.get_received('/test')
        self.assertTrue(len(received) == 1)
        self.assertTrue(len(received[0]['args']) == 1)
        self.assertTrue(received[0]['name'] == 'my custom namespace response')
        self.assertTrue(received[0]['args'][0]['a'] == 'b')

    def test_broadcast(self):
        client1 = socketio.test_client(app)
        client2 = socketio.test_client(app)
        client3 = socketio.test_client(app, namespace='/test')
        client2.get_received()  # clean
        client3.get_received('/test')  # clean
        client1.emit('my custom broadcast event', {'a': 'b'}, broadcast=True)
        received = client2.get_received()
        self.assertTrue(len(received) == 1)
        self.assertTrue(len(received[0]['args']) == 1)
        self.assertTrue(received[0]['name'] == 'my custom response')
        self.assertTrue(received[0]['args'][0]['a'] == 'b')
        self.assertTrue(len(client3.get_received('/test')) == 0)

    def test_broadcast_namespace(self):
        client1 = socketio.test_client(app, namespace='/test')
        client2 = socketio.test_client(app, namespace='/test')
        client3 = socketio.test_client(app)
        client2.get_received('/test')  # clean
        client3.get_received()  # clean
        client1.emit('my custom broadcast namespace event', {'a': 'b'},
                     namespace='/test')
        received = client2.get_received('/test')
        self.assertTrue(len(received) == 1)
        self.assertTrue(len(received[0]['args']) == 1)
        self.assertTrue(received[0]['name'] == 'my custom namespace response')
        self.assertTrue(received[0]['args'][0]['a'] == 'b')
        self.assertTrue(len(client3.get_received()) == 0)

    def test_session(self):
        client = socketio.test_client(app)
        client.get_received()  # clean received
        client.send('echo this message back')
        self.assertTrue(client.socket[''].session['a'] == 'b')

    def test_room(self):
        client1 = socketio.test_client(app)
        client2 = socketio.test_client(app)
        client3 = socketio.test_client(app, namespace='/test')
        client1.get_received()  # clean
        client2.get_received()  # clean
        client3.get_received('/test')  # clean
        client1.emit('join room', {'room': 'one'})
        client2.emit('join room', {'room': 'one'})
        client3.emit('join room', {'room': 'one'}, namespace='/test')
        client1.emit('my room event', {'a': 'b', 'room': 'one'})
        received = client1.get_received()
        self.assertTrue(len(received) == 1)
        self.assertTrue(len(received[0]['args']) == 1)
        self.assertTrue(received[0]['name'] == 'my room response')
        self.assertTrue(received[0]['args'][0]['a'] == 'b')
        self.assertTrue(received == client2.get_received())
        received = client3.get_received('/test')
        self.assertTrue(len(received) == 0)
        client1.emit('leave room', {'room': 'one'})
        client1.emit('my room event', {'a': 'b', 'room': 'one'})
        received = client1.get_received()
        self.assertTrue(len(received) == 0)
        received = client2.get_received()
        self.assertTrue(len(received) == 1)
        self.assertTrue(len(received[0]['args']) == 1)
        self.assertTrue(received[0]['name'] == 'my room response')
        self.assertTrue(received[0]['args'][0]['a'] == 'b')
        client2.disconnect()
        socketio.emit('my room event', {'a': 'b'}, room='one')
        received = client1.get_received()
        self.assertTrue(len(received) == 0)
        received = client3.get_received('/test')
        self.assertTrue(len(received) == 0)
        client3.emit('my room namespace event', {'room': 'one'}, namespace='/test')
        received = client3.get_received('/test')
        self.assertTrue(len(received) == 1)
        self.assertTrue(received[0]['name'] == 'message')
        self.assertTrue(received[0]['args'] == 'room message')
        self.assertTrue(len(socketio.rooms) == 1)
        client3.disconnect('/test')
        self.assertTrue(len(socketio.rooms) == 0)


if __name__ == '__main__':
    unittest.main()

########NEW FILE########
