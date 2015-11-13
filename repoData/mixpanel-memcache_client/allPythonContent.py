__FILENAME__ = conf
# -*- coding: utf-8 -*-
#
# memcache_client documentation build configuration file, created by
# sphinx-quickstart on Tue Jul 10 14:39:26 2012.
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
sys.path.insert(0, os.path.abspath('..'))

# -- General configuration -----------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be extensions
# coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = ['sphinx.ext.autodoc', 'sphinx.ext.viewcode']

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The encoding of source files.
#source_encoding = 'utf-8-sig'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = u'memcache_client'
copyright = u'2012, Mixpanel'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = '1.0'
# The full version, including alpha/beta/rc tags.
release = '1.0'

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
htmlhelp_basename = 'memcache_clientdoc'


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
  ('index', 'memcache_client.tex', u'memcache\\_client Documentation',
   u'Mixpanel', 'manual'),
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
    ('index', 'memcache_client', u'memcache_client Documentation',
     [u'Mixpanel'], 1)
]

# If true, show URL addresses after external links.
#man_show_urls = False


# -- Options for Texinfo output ------------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
  ('index', 'memcache_client', u'memcache_client Documentation',
   u'Mixpanel', 'memcache_client', 'One line description of project.',
   'Miscellaneous'),
]

# Documents to append as an appendix to all manuals.
#texinfo_appendices = []

# If false, no module index is generated.
#texinfo_domain_indices = True

# How to display URL addresses: 'footnote', 'no', or 'inline'.
#texinfo_show_urls = 'footnote'

autodoc_member_order = 'bysource'
autoclass_content = 'both'

########NEW FILE########
__FILENAME__ = memcache
# Copyright 2012 Mixpanel, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

'''
a minimal, pure python client for memcached, kestrel, etc.

Usage example::

    import memcache
    mc = memcache.Client("127.0.0.1", 11211, timeout=1, connect_timeout=5)
    mc.set("some_key", "Some value")
    value = mc.get("some_key")
    mc.delete("another_key")
'''

import errno
import re
import socket

class ClientException(Exception):
    '''
    Raised when the server does something we don't expect

    | This does not include `socket errors <http://docs.python.org/library/socket.html#socket.error>`_
    | Note that ``ValidationException`` subclasses this so, technically, this is raised on any error
    '''

    def __init__(self, msg, item=None):
        if item is not None:
            msg = '%s: %r' % (msg, item) # use repr() to better see special chars
        super(ClientException, self).__init__(msg)

class ValidationException(ClientException):
    '''
    Raised when an invalid parameter is passed to a ``Client`` function
    '''

    def __init__(self, msg, item):
        super(ValidationException, self).__init__(msg, item)

class Client(object):

    def __init__(self, host, port, timeout=None, connect_timeout=None):
        '''
        If ``connect_timeout`` is None, ``timeout`` will be used instead
        (for connect and everything else)
        '''
        self._addr = (host, port)
        self._timeout = timeout
        self._connect_timeout = connect_timeout
        self._socket = None

    def __del__(self):
        self.close()

    def _get_addr(self):
        return self._addr

    address = property(_get_addr)
    ''' A read-only (str, int) tuple representing the host operations are performed on '''

    def _get_timeout(self):
        return self._timeout

    def _set_timeout(self, timeout):
        # presumably this should fail rarely
        # set locally before on socket
        # b/c if socket fails, it will probably be closed/reopened
        # and will want to use last intended value
        self._timeout = timeout
        if self._socket:
            self._socket.settimeout(timeout)

    timeout = property(_get_timeout, _set_timeout)
    '''
    A float representing the timeout in seconds for reads and sends on the underlying socket
    (``connect_timeout`` cannot be changed once init)

    Setting a timeout can raise a ``TypeError`` (non-float)  or a ``ValueError`` (negative)
    '''

    def _connect(self):
        # buffer needed since we always ask for 4096 bytes at a time
        # thus, might read more than the current expected response
        # cleared on every reconnect since old bytes are part of old session and can't be reused
        self._buffer = ''

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        connect_timeout = self._connect_timeout if self._connect_timeout is not None else self._timeout
        self._socket.settimeout(connect_timeout) # passing None means blocking
        try:
            self._socket.connect(self._addr)
            self._socket.settimeout(self._timeout)
        except (socket.error, socket.timeout):
            self._socket = None # don't want to hang on to bad socket
            raise

    def _read(self, length=None):
        '''
        Return the next length bytes from server
        Or, when length is None,
        Read a response delimited by \r\n and return it (including \r\n)
        (Use latter only when \r\n is unambiguous -- aka for control responses, not data)
        '''
        result = None
        while result is None:
            if length: # length = 0 is ambiguous, so don't use
                if len(self._buffer) >= length:
                    result = self._buffer[:length]
                    self._buffer = self._buffer[length:]
            else:
                delim_index = self._buffer.find('\r\n')
                if delim_index != -1:
                    result = self._buffer[:delim_index+2]
                    self._buffer = self._buffer[delim_index+2:]

            if result is None:
                try:
                    tmp = self._socket.recv(4096)
                except (socket.error, socket.timeout) as e:
                    self.close()
                    raise e

                if not tmp:
                    # we handle common close/retry cases in _send_command
                    # however, this can happen if server suddenly goes away
                    # (e.g. restarting memcache under sufficient load)
                    raise socket.error, 'unexpected socket close on recv'
                else:
                    self._buffer += tmp
        return result

    def _send_command(self, command):
        '''
        Send command to server and return initial response line
        Will reopen socket if it got closed (either locally or by server)
        '''
        if self._socket: # try to find out if the socket is still open
            try:
                self._socket.settimeout(0)
                self._socket.recv(0)
                # if recv didn't raise, then the socket was closed or there is junk
                # in the read buffer, either way, close
                self.close()
            except socket.error as e:
                if e.errno == errno.EAGAIN: # this is expected if the socket is still open
                    self._socket.settimeout(self._timeout)
                else:
                    self.close()

        if not self._socket:
            self._connect()

        self._socket.sendall(command)
        return self._read()

    # key supports ascii sans space and control chars
    # \x21 is !, right after space, and \x7e is -, right before DEL
    # also 1 <= len <= 250 as per the spec
    _valid_key_re = re.compile('^[\x21-\x7e]{1,250}$')

    def _validate_key(self, key):
        if not isinstance(key, str): # avoid bugs subtle and otherwise
            raise ValidationException('key must be str', key)
        m = self._valid_key_re.match(key)
        if m:
            # in python re, $ matches either end of line or right before
            # \n at end of line. We can't allow latter case, so
            # making sure length matches is simplest way to detect
            if len(m.group(0)) != len(key):
                raise ValidationException('trailing newline', key)
        else:
            raise ValidationException('invalid key', key)
        return key

    def close(self):
        '''
        Closes the socket if its open

        | Sockets are automatically closed when the ``Client`` object is garbage collected
        | Sockets are opened the first time a command is run (such as ``get`` or ``set``)
        | Raises socket errors
        '''
        if self._socket:
            self._socket.close()
            self._socket = None

    def delete(self, key):
        '''
        Deletes a key/value pair from the server

        Raises ``ClientException`` and socket errors
        '''
        # req  - delete <key> [noreply]\r\n
        # resp - DELETED\r\n
        #        or
        #        NOT_FOUND\r\n
        key = self._validate_key(key)

        command = 'delete %s\r\n' % key
        resp = self._send_command(command)
        if resp != 'DELETED\r\n' and resp != 'NOT_FOUND\r\n':
            raise ClientException('delete failed', resp)

    def get(self, key):
        '''
        Gets a single value from the server; returns None if there is no value

        Raises ``ValidationException``, ``ClientException``, and socket errors
        '''
        return self.multi_get([key])[0]

    def multi_get(self, keys):
        '''
        Takes a list of keys and returns a list of values

        Raises ``ValidationException``, ``ClientException``, and socket errors
        '''
        if len(keys) == 0:
            return []

        # req  - get <key> [<key> ...]\r\n
        # resp - VALUE <key> <flags> <bytes> [<cas unique>]\r\n
        #        <data block>\r\n (if exists)
        #        [...]
        #        END\r\n
        keys = [self._validate_key(key) for key in keys]
        if len(set(keys)) != len(keys):
            raise ClientException('duplicate keys passed to multi_get')
        command = 'get %s\r\n' % ' '.join(keys)
        received = {}
        resp = self._send_command(command)
        error = None

        while resp != 'END\r\n':
            terms = resp.split()
            if len(terms) == 4 and terms[0] == 'VALUE': # exists
                key = terms[1]
                flags = int(terms[2])
                length = int(terms[3])
                if flags != 0:
                    error = ClientException('received non zero flags')
                val = self._read(length+2)[:-2]
                if key in received:
                    error = ClientException('duplicate results from server')
                received[key] = val
            else:
                raise ClientException('get failed', resp)
            resp = self._read()

        if error is not None:
            # this can happen if a memcached instance contains items set by a previous client
            # leads to subtle bugs, so fail fast
            raise error

        if len(received) > len(keys):
            raise ClientException('received too many responses')
        # memcache client is used by other servers besides memcached.
        # In the case of kestrel, responses coming back to not necessarily
        # match the requests going out. Thus we just ignore the key name
        # if there is only one key and return what we received.
        if len(keys) == 1 and len(received) == 1:
            response = received.values()
        else:
            response = [received.get(key) for key in keys]
        return response

    def set(self, key, val, exptime=0):
        '''
        Sets a key to a value on the server with an optional exptime (0 means don't auto-expire)

        Raises ``ValidationException``, ``ClientException``, and socket errors
        '''
        # req  - set <key> <flags> <exptime> <bytes> [noreply]\r\n
        #        <data block>\r\n
        # resp - STORED\r\n (or others)
        key = self._validate_key(key)

        # the problem with supporting types is it oftens leads to uneven and confused usage
        # some code sites use the type support, others do manual casting to/from str
        # worse yet, some sites don't even know what value they are putting in and mis-cast on get
        # by uniformly requiring str, the end-use code is much more uniform and legible
        if not isinstance(val, str):
            raise ValidationException('value must be str', val)

        # typically, if val is > 1024**2 bytes server returns:
        #   SERVER_ERROR object too large for cache\r\n
        # however custom-compiled memcached can have different limit
        # so, we'll let the server decide what's too much

        if not isinstance(exptime, int):
            raise ValidationException('exptime not int', exptime)
        elif exptime < 0:
            raise ValidationException('exptime negative', exptime)

        command = 'set %s 0 %d %d\r\n%s\r\n' % (key, exptime, len(val), val)
        resp = self._send_command(command)
        if resp != 'STORED\r\n':
            raise ClientException('set failed', resp)

    def stats(self, additional_args=None):
        '''
        Runs a stats command on the server.

        ``additional_args`` are passed verbatim to the server.
        See `the memcached wiki <http://code.google.com/p/memcached/wiki/NewCommands#Statistics>`_ for details
        or `the spec <https://github.com/memcached/memcached/blob/master/doc/protocol.txt>`_ for even more details

        Raises ``ClientException`` and socket errors
        '''
        # req  - stats [additional args]\r\n
        # resp - STAT <name> <value>\r\n (one per result)
        #        END\r\n
        if additional_args is not None:
            command = 'stats %s\r\n' % additional_args
        else:
            command = 'stats\r\n'

        resp = self._send_command(command)
        result = {}
        while resp != 'END\r\n':
            terms = resp.split()
            if len(terms) == 2 and terms[0] == 'STAT':
                result[terms[1]] = None
            elif len(terms) == 3 and terms[0] == 'STAT':
                result[terms[1]] = terms[2]
            else:
                raise ClientException('stats failed', resp)
            resp = self._read()
        return result

########NEW FILE########
__FILENAME__ = mock_memcached
#!/usr/bin/env python

# Copyright 2012 Mixpanel, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# this is a simple mock memcached server
# it only accepts a single cxn then closes
# the point is that we can handcraft delays
# to verify timeouts work as expected

import errno
from optparse import OptionError, OptionParser
import socket
import time

class SocketClosedException(Exception):

    def __init__(self):
        super(SocketClosedException, self).__init__('socket closed unexpectedly')

class MockMemcached(object):
    def __init__(self, host, port, accept_connections, get_delay):
        self._addr = (host, port)
        self._accept_connections = accept_connections
        self._get_delay = get_delay
        self._dict = {} # stores the key-val pairs
        self._root_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._root_socket.bind(self._addr)

        # buffer needed since we always ask for 4096 bytes at a time
        # and thus might read more than the current expected response
        self._buffer = ''
        # self._socket set after accept

    def _read(self, length=None):
        '''
        Return the next length bytes from server
        Or, when length is None,
        Read a response delimited by \r\n and return it (including \r\n)
        (Use latter only when \r\n is unambiguous -- aka for control responses, not data)
        '''
        result = None
        while result is None:
            if length: # length = 0 is ambiguous, so don't use 
                if len(self._buffer) >= length:
                    result = self._buffer[:length]
                    self._buffer = self._buffer[length:]
            else:
                delim_index = self._buffer.find('\r\n')
                if delim_index != -1:
                    result = self._buffer[:delim_index+2]
                    self._buffer = self._buffer[delim_index+2:]

            if result is None:
                tmp = self._socket.recv(4096)
                if not tmp:
                    raise SocketClosedException
                else:
                    self._buffer += tmp
        return result

    def _handle_get(self, key):
        # req  - get <key>\r\n
        # resp - VALUE <key> <flags> <bytes> [<cas unique>]\r\n
        #        <data block>\r\n (if exists)
        #        END\r\n
        if self._get_delay > 0:
            time.sleep(self._get_delay)
        if key in self._dict:
            val = self._dict[key]
            command = 'VALUE %s 0 %d\r\n%s\r\n' % (key, len(val), val)
            self._socket.sendall(command)
        self._socket.sendall('END\r\n')

    def _handle_set(self, key, length):
        # req  - set <key> <flags> <exptime> <bytes> [noreply]\r\n
        #        <data block>\r\n
        # resp - STORED\r\n (or others)
        val = self._read(length+2)[:-2] # read \r\n then chop it off
        self._dict[key] = val
        self._socket.sendall('STORED\r\n')

    def run(self):
        self._root_socket.listen(1)

        if self._accept_connections:
            self._socket, addr = self._root_socket.accept()
        else:
            while True: # spin until killed
                time.sleep(1)

        while True:
            try:
                request = self._read()
                terms = request.split()
                if len(terms) == 2 and terms[0] == 'get':
                    self._handle_get(terms[1])
                elif len(terms) == 5 and terms[0] == 'set':
                    self._handle_set(terms[1], int(terms[4]))
                else:
                    print 'unknown command', repr(request)
                    break
            except SocketClosedException:
                print 'socket closed', repr(request)
                break

        self._socket.close()
        self._root_socket.close()

        # spin until killed - this simplifies cleanup code for the unit tests
        while True:
            time.sleep(1)

if __name__ == '__main__':
    usage = 'usage: %prog [options]'
    parser = OptionParser(usage=usage)
    # note - this option cannot be used to test connect timeout
    # accept receives already-connected cxns that are ready to go
    parser.add_option(
        '--dont-accept',
        default=True,
        dest='accept_connections',
        action='store_false',
        help="don't accept any incoming connection requests",
    )
    parser.add_option(
        '--get-delay',
        default=0,
        dest='get_delay',
        metavar='GET_DELAY',
        type='int',
        help='delay get command by GET_DELAY seconds',
    )
    parser.add_option(
        '-p', '--port',
        default=11212,
        dest='port',
        metavar='PORT',
        type='int',
        help='listen on PORT',
    )
    (options, args) = parser.parse_args()
    if len(args) > 0:
        raise OptionError('unrecognized arguments: %s' % ' '.join(args))

    server = MockMemcached('127.0.0.1',
                           options.port,
                           options.accept_connections,
                           options.get_delay)
    server.run()

########NEW FILE########
__FILENAME__ = test
#!/usr/bin/env python

# Copyright 2012 Mixpanel, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

try:
    from . import memcache
except ValueError:
    import memcache

# subprocess is not monkey-patched, hence the special import
import sys
if 'eventlet' in sys.modules:
    from eventlet.green import subprocess
else:
    import subprocess

import os
import os.path
import socket
import time
try:
    import unittest2 as unittest
except ImportError:
    import unittest

low_port = 11000
high_port = 11210
# spin up new memcached instance to test against
def _start_new_memcached_server(port=None, mock=False, additional_args=[]):
    if not port:
        global low_port
        ports = range(low_port, high_port + 1)
        low_port += 1
    else:
        ports = [port]

    # try multiple ports so that can cleanly run tests 
    # w/o having to wait for a particular port to free up
    for attempted_port in ports:
        try:
            if mock:
                command = [
                    'python',
                    os.path.join(os.path.dirname(__file__), 'mock_memcached.py'),
                    '-p',
                    str(attempted_port),
                ]
            else:
                command = [
                    '/usr/bin/memcached',
                    '-p',
                    str(attempted_port),
                    '-m',
                    '1', # 1MB
                    '-l',
                    '127.0.0.1',
                ]
            command.extend(additional_args)
            p = subprocess.Popen(command)
            time.sleep(2) # needed otherwise unittest races against startup
            return p, attempted_port
        except:
            pass # try again
    else:
        raise Exception('could not start memcached -- no available ports')

# test memcache client for basic functionality
class TestClient(unittest.TestCase):

    @classmethod
    def setUpClass(c):
        c.memcached, c.port = _start_new_memcached_server()

    @classmethod
    def tearDownClass(c):
        try:
            c.memcached.terminate()
        except:
            print 'for some reason memcached not running'
        c.memcached.wait()

    def setUp(self):
        self.client = memcache.Client('127.0.0.1', self.port)

    def tearDown(self):
        self.client.close()

    def test_delete(self):
        key = 'delete'
        val = 'YBgGHw'
        self.client.set(key, val)
        mcval = self.client.get(key)
        self.assertEqual(mcval, val)
        self.client.delete(key)
        mcval = self.client.get(key)
        self.assertEqual(mcval, None)

    def test_multi_get(self):
        items = {'blob':'steam', 'help':'tres', 'HEHE':'Pans'}
        for k, v in items.items():
            self.client.set(k, v)
        resp = self.client.multi_get(items.keys())
        for v, r in zip(items.values(), resp):
            self.assertTrue(v == r)

    def test_expire(self):
        key = 'expire'
        val = "uiuokJ"
        self.client.set(key, val, exptime=1)
        time.sleep(2)
        mcval = self.client.get(key)
        self.assertEqual(mcval, None)

    def test_get_bad(self):
        self.assertRaises(Exception, self.client.get, 'get_bad\x84')
        mcval = self.client.get('!' * 250)
        self.assertEqual(mcval, None)
        self.assertRaises(Exception, self.client.get, '!' * 251)
        self.assertRaises(Exception, self.client.get, '')

        # this tests regex edge case specific to the impl
        self.assertRaises(Exception, self.client.get, 'get_bad_trailing_newline\n')

    def test_get_unknown(self):
        mcval = self.client.get('get_unknown')
        self.assertEqual(mcval, None)

    def test_set_bad(self):
        key = 'set_bad'
        self.assertRaises(Exception, self.client.set, key, '!' * 1024**2)
        self.client.set(key, '!' * (1024**2 - 100)) # not sure why 1024**2 - 1 rejected
        self.assertRaises(Exception, self.client.set, '', 'empty key')

    def test_set_get(self):
        key = 'set_get'
        val = "eJsiIU"
        self.client.set(key, val)
        mcval = self.client.get(key)
        self.assertEqual(mcval, val)

    def test_stats(self):
        stats = self.client.stats()
        self.assertTrue('total_items' in stats)

    def test_bad_flags(self):
        self.client._connect()
        key = 'badflags'
        val = 'xcHJFd'
        command = 'set %s 1 0 %d\r\n%s\r\n' % (key, len(val), val)
        self.client._socket.sendall(command)
        rc = self.client._read()
        self.assertEqual(rc, 'STORED\r\n')
        self.assertRaises(Exception, self.client.get, key)

    def test_str_only(self):
        self.assertRaises(Exception, self.client.set, u'unicode_key', 'sfdhjk')
        self.assertRaises(Exception, self.client.set, 'str_key', u'DFHKfl')

# make sure timeout works by using mock server
# test memcached failing in a variety of ways, coming back vs. not, etc
class TestFailures(unittest.TestCase):

    def test_gone(self):
        mock_memcached, port = _start_new_memcached_server()
        try:
            client = memcache.Client('127.0.0.1', port)
            key = 'gone'
            val = 'QWMcxh'
            client.set(key, val)

            mock_memcached.terminate()
            mock_memcached.wait()
            mock_memcached = None

            self.assertRaises(Exception, client.get, key)
            client.close()
        finally:
            if mock_memcached:
                mock_memcached.terminate()
                mock_memcached.wait()

    def test_hardfail(self):
        mock_memcached, port = _start_new_memcached_server()
        try:
            client = memcache.Client('127.0.0.1', port)
            key = 'hardfail'
            val = 'FuOIdn'
            client.set(key, val)

            mock_memcached.kill() # sends SIGKILL
            mock_memcached.wait()
            mock_memcached, port = _start_new_memcached_server(port=port)

            mcval = client.get(key)
            self.assertEqual(mcval, None) # val lost when restarted
            client.close()
        finally:
            mock_memcached.terminate()
            mock_memcached.wait()

class TestTimeout(unittest.TestCase):

    # make sure mock server works
    def test_set_get(self):
        mock_memcached, port = _start_new_memcached_server(mock=True)
        try:
            client = memcache.Client('127.0.0.1', port)
            key = 'set_get'
            val = 'DhuWmC'
            client.set(key, val)
            mcval = client.get(key)
            self.assertEqual(val, mcval)
            client.close()
        finally:
            mock_memcached.terminate()
            mock_memcached.wait()

    def test_get_timeout(self):
        mock_memcached, port = _start_new_memcached_server(mock=True, additional_args=['--get-delay', '2'])
        try:
            client = memcache.Client('127.0.0.1', port, timeout=1)
            key = 'get_timeout'
            val = 'cMuBde'
            client.set(key, val)
            # when running unpatched eventlet,
            # the following will fail w/ socket.error, EAGAIN
            self.assertRaises(socket.timeout, client.get, key)
            client.close()
        finally:
            mock_memcached.terminate()
            mock_memcached.wait()

class TestConnectTimeout(unittest.TestCase):

    # to run these tests, you need specify an ip that will not allow tcp from your machine to 11211
    # this is easiest way to test connect timeout, since has to happen at kernel level (iptables etc)
    unavailable_ip = '173.193.164.107' # appstage01 (external ip is firewalled, internal is not)

    def test_connect_timeout(self):
        # using normal timeout

        # client usually does lazy connect, but we don't want to confuse connect and non-connect timeout
        # so connect manually
        client = memcache.Client(self.unavailable_ip, 11211, timeout=1)
        self.assertRaises(socket.timeout, client._connect)
        client.close()

    def test_connect_timeout2(self):
        # using connect timeout
        client = memcache.Client(self.unavailable_ip, 11211, connect_timeout=1)
        self.assertRaises(socket.timeout, client._connect)
        client.close()

if __name__ == '__main__':
    # uncomment to only run specific tests
    #
    # sadly, the particular map below is a bit cryptic
    # basically, constructing the test case class with a string containing a method name
    # creates an instance of the class that will only run that test
    # a list of these can be passed to the test suite constructor to make the suite
    # suite = unittest.TestSuite(map(TestConnectTimeout, ['test_connect_timeout', 'test_connect_timeout2']))

    suite = unittest.TestSuite([
        unittest.TestLoader().loadTestsFromTestCase(TestClient),
        unittest.TestLoader().loadTestsFromTestCase(TestFailures),
        unittest.TestLoader().loadTestsFromTestCase(TestTimeout),
        # TestConnectTimeout not part of normal suite -- requires special config
    ])

    unittest.TextTestRunner(verbosity=2).run(suite)

########NEW FILE########
