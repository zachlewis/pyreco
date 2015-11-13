__FILENAME__ = app
#!/usr/bin/python
import logging
import new
import os
import pickle
import cgi
import sys
import traceback
import urlparse
import types
import wsgiref.handlers
import re
import posixpath
import urllib

from google.appengine.api import urlfetch
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template

_LOCAL_ = os.environ[ 'SERVER_SOFTWARE' ].startswith( 'Development' )
_DEBUG_ = False or _LOCAL_
_CACHE_ = False

sys.path.append( 'pyl' )

import jinja2 as jinja2_
jinja2 = jinja2_.Environment( loader=jinja2_.FileSystemLoader( 'jinja2-assets' ) )

from gist_it import appengine as gist_it_appengine
gist_it_appengine.jinja2 = jinja2

class RequestHandler( webapp.RequestHandler ):

    def url_for( self, *arguments ):
        parse = urlparse.urlparse( self.request.url )
        path = ''
        if len( arguments ):
            path = posixpath.join( *arguments )
        return str( urlparse.urlunparse( ( parse.scheme, parse.netloc, path, '', '', '' ) ) )

    def render_template( self, template_name, **arguments ):
        self.response.out.write( jinja2.get_template( template_name ).render( dispatch=self, **arguments ) )

class dispatch_index( RequestHandler ):
    def get( self ):
        self.render_template( 'index.jinja.html' )

class dispatch_test( RequestHandler ):
    def get( self ):
        return gist_it_appengine.dispatch_test( self )

class dispatch_test0( RequestHandler ):
    def get( self ):
        return gist_it_appengine.dispatch_test0( self )

class dispatch_gist_it( RequestHandler ):
    def get( self, location ):
        return gist_it_appengine.dispatch_gist_it( self, location )

wsgi_application = webapp.WSGIApplication( [
    ( r'/', dispatch_index ),
    ( r'/test', dispatch_test ),
    ( r'/test0', dispatch_test0 ),
    ( r'/xyzzy/(.*)', dispatch_gist_it ),
    ( r'(.*)', dispatch_gist_it ),
], debug=_DEBUG_ )

def main():
    run_wsgi_app( wsgi_application )

if __name__ == '__main__':
    main()

########NEW FILE########
__FILENAME__ = appengine
#!/usr/bin/python
import logging
import os
import cgi
import sys
import urllib
import simplejson

jinja2 = None

_LOCAL_ = os.environ[ 'SERVER_SOFTWARE' ].startswith( 'Development' )
_DEBUG_ = True
_CACHE_ = False

from google.appengine.api import urlfetch
from google.appengine.ext import webapp
from versioned_memcache import memcache

import gist_it
from gist_it import take_slice, cgi_escape

def render_gist_html( base, gist, document ):
    if jinja2 is None:
        return
    result = jinja2.get_template( 'gist.jinja.html' ).render( cgi_escape = cgi_escape, base = base, gist = gist, document = document )
    return result

def render_gist_js( base, gist, gist_html  ):
    if jinja2 is None:
        return
    result = jinja2.get_template( 'gist.jinja.js' ).render( base = base, gist = gist, gist_html = gist_html )
    return result

def render_gist_js_callback( callback, gist, gist_html  ):
    return "%s( '%s', '%s' );" % ( callback, gist_html.encode( 'string_escape' ), gist.raw_path )

# dispatch == RequestHandler
def dispatch_test( dispatch ):
    dispatch.render_template( 'test.jinja.html', list =
        map( lambda _: ( _, 'github/robertkrimen/gist-it-example/raw/master/test.js?' + _ ), [
        # Standard
        ''
        # Without footer
        'footer=0',
        # Footer without "brought to you by" mention
        'footer=minimal',
        # Partial file
        'slice=3:10',
        # First line of file
        'slice=0',
        # Last line of file
        'slice=-1',
        # With no style request
        'style=0',
        # Documentation
        'slice=24:100',
        'slice=0:-2',
        'slice=0',
        ] )
    )

# dispatch == RequestHandler
def dispatch_test0( dispatch ):
    dispatch.render_template( 'test.jinja.html', list = [
        ( '', 'github/whittle/node-coffee-heroku-tutorial/raw/eb587185509ec8c2e728067d49f4ac2d5a67ec09/app.js' ),
        ( '', 'github/horstjens/ThePythonGameBook/blob/master/pygame/015_more_sprites.py' ),
        ]
    )

# dispatch == RequestHandler
def dispatch_gist_it( dispatch, location ):
    location = urllib.unquote( location )
    match = gist_it.Gist.match( location )
    dispatch.response.headers['Content-Type'] = 'text/plain'; 
    if not match:
        dispatch.response.set_status( 404 )
        dispatch.response.out.write( dispatch.response.http_status_message( 404 ) )
        dispatch.response.out.write( "\n" )
        return

    else:
        slice_option = dispatch.request.get( 'slice' )
        footer_option = dispatch.request.get( 'footer' )
        style_option = dispatch.request.get( 'style' )
        highlight_option = dispatch.request.get( 'highlight' )
        test = dispatch.request.get( 'test' )

        gist = gist_it.Gist.parse( location, slice_option = slice_option, footer_option = footer_option, style_option = style_option, highlight_option = highlight_option )
        if not gist:
            dispatch.response.set_status( 500 )
            dispatch.response.out.write( "Unable to parse \"%s\": Not a valid repository path?" % ( location ) )
            dispatch.response.out.write( "\n" )
            return
            
        if _CACHE_ and dispatch.request.get( 'flush' ):
            dispatch.response.out.write( memcache.delete( memcache_key ) )
            return

        memcache_key = gist.raw_url
        data = memcache.get( memcache_key )
        if data is None or not _CACHE_:
            base = dispatch.url_for()
            # For below, see: http://stackoverflow.com/questions/2826238/does-google-appengine-cache-external-requests
            response = urlfetch.fetch( gist.raw_url, headers = { 'Cache-Control': 'max-age=300' } )
            if response.status_code != 200:
                if response.status_code == 403:
                    dispatch.response.set_status( response.status_code )
                elif response.status_code == 404:
                    dispatch.response.set_status( response.status_code )
                else:
                    dispatch.response.set_status( 500 )
                dispatch.response.out.write( "Unable to fetch \"%s\": (%i)" % ( gist.raw_url, response.status_code ) )
                return
            else:
                # I believe GitHub always returns a utf-8 encoding, so this should be safe
                response_content = response.content.decode('utf-8')

                gist_content = take_slice( response_content, gist.start_line, gist.end_line )
                gist_html = str( render_gist_html( base, gist, gist_content ) ).strip()
                callback = dispatch.request.get( 'callback' );
                if callback != '':
                    result = render_gist_js_callback( callback, gist, gist_html )
                else:
                    result = render_gist_js( base, gist, gist_html )
                result = str( result ).strip()
                data = result
                if test:
                    if test == 'json':
                        dispatch.response.headers['Content-Type'] = 'application/json';
                        dispatch.response.out.write(simplejson.dumps({
                            'gist': gist.value(),
                            'content': gist_content,
                            'html': gist_html,
                        }))
                    elif False and test == 'example':
                        pass
                    else:
                        dispatch.response.headers['Content-Type'] = 'text/plain' 
                        dispatch.response.out.write( gist_html )
                    return
                if _CACHE_:
                    memcache.add( memcache_key, data, 60 * 60 * 24 )

        dispatch.response.headers['Content-Type'] = 'text/javascript'
        dispatch.response.out.write( data )

########NEW FILE########
__FILENAME__ = bccache
# -*- coding: utf-8 -*-
"""
    jinja2.bccache
    ~~~~~~~~~~~~~~

    This module implements the bytecode cache system Jinja is optionally
    using.  This is useful if you have very complex template situations and
    the compiliation of all those templates slow down your application too
    much.

    Situations where this is useful are often forking web applications that
    are initialized on the first request.

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD.
"""
from os import path, listdir
import sys
import marshal
import tempfile
import cPickle as pickle
import fnmatch
from cStringIO import StringIO
try:
    from hashlib import sha1
except ImportError:
    from sha import new as sha1
from jinja2.utils import open_if_exists


bc_version = 2

# magic version used to only change with new jinja versions.  With 2.6
# we change this to also take Python version changes into account.  The
# reason for this is that Python tends to segfault if fed earlier bytecode
# versions because someone thought it would be a good idea to reuse opcodes
# or make Python incompatible with earlier versions.
bc_magic = 'j2'.encode('ascii') + \
    pickle.dumps(bc_version, 2) + \
    pickle.dumps((sys.version_info[0] << 24) | sys.version_info[1])


class Bucket(object):
    """Buckets are used to store the bytecode for one template.  It's created
    and initialized by the bytecode cache and passed to the loading functions.

    The buckets get an internal checksum from the cache assigned and use this
    to automatically reject outdated cache material.  Individual bytecode
    cache subclasses don't have to care about cache invalidation.
    """

    def __init__(self, environment, key, checksum):
        self.environment = environment
        self.key = key
        self.checksum = checksum
        self.reset()

    def reset(self):
        """Resets the bucket (unloads the bytecode)."""
        self.code = None

    def load_bytecode(self, f):
        """Loads bytecode from a file or file like object."""
        # make sure the magic header is correct
        magic = f.read(len(bc_magic))
        if magic != bc_magic:
            self.reset()
            return
        # the source code of the file changed, we need to reload
        checksum = pickle.load(f)
        if self.checksum != checksum:
            self.reset()
            return
        # now load the code.  Because marshal is not able to load
        # from arbitrary streams we have to work around that
        if isinstance(f, file):
            self.code = marshal.load(f)
        else:
            self.code = marshal.loads(f.read())

    def write_bytecode(self, f):
        """Dump the bytecode into the file or file like object passed."""
        if self.code is None:
            raise TypeError('can\'t write empty bucket')
        f.write(bc_magic)
        pickle.dump(self.checksum, f, 2)
        if isinstance(f, file):
            marshal.dump(self.code, f)
        else:
            f.write(marshal.dumps(self.code))

    def bytecode_from_string(self, string):
        """Load bytecode from a string."""
        self.load_bytecode(StringIO(string))

    def bytecode_to_string(self):
        """Return the bytecode as string."""
        out = StringIO()
        self.write_bytecode(out)
        return out.getvalue()


class BytecodeCache(object):
    """To implement your own bytecode cache you have to subclass this class
    and override :meth:`load_bytecode` and :meth:`dump_bytecode`.  Both of
    these methods are passed a :class:`~jinja2.bccache.Bucket`.

    A very basic bytecode cache that saves the bytecode on the file system::

        from os import path

        class MyCache(BytecodeCache):

            def __init__(self, directory):
                self.directory = directory

            def load_bytecode(self, bucket):
                filename = path.join(self.directory, bucket.key)
                if path.exists(filename):
                    with open(filename, 'rb') as f:
                        bucket.load_bytecode(f)

            def dump_bytecode(self, bucket):
                filename = path.join(self.directory, bucket.key)
                with open(filename, 'wb') as f:
                    bucket.write_bytecode(f)

    A more advanced version of a filesystem based bytecode cache is part of
    Jinja2.
    """

    def load_bytecode(self, bucket):
        """Subclasses have to override this method to load bytecode into a
        bucket.  If they are not able to find code in the cache for the
        bucket, it must not do anything.
        """
        raise NotImplementedError()

    def dump_bytecode(self, bucket):
        """Subclasses have to override this method to write the bytecode
        from a bucket back to the cache.  If it unable to do so it must not
        fail silently but raise an exception.
        """
        raise NotImplementedError()

    def clear(self):
        """Clears the cache.  This method is not used by Jinja2 but should be
        implemented to allow applications to clear the bytecode cache used
        by a particular environment.
        """

    def get_cache_key(self, name, filename=None):
        """Returns the unique hash key for this template name."""
        hash = sha1(name.encode('utf-8'))
        if filename is not None:
            if isinstance(filename, unicode):
                filename = filename.encode('utf-8')
            hash.update('|' + filename)
        return hash.hexdigest()

    def get_source_checksum(self, source):
        """Returns a checksum for the source."""
        return sha1(source.encode('utf-8')).hexdigest()

    def get_bucket(self, environment, name, filename, source):
        """Return a cache bucket for the given template.  All arguments are
        mandatory but filename may be `None`.
        """
        key = self.get_cache_key(name, filename)
        checksum = self.get_source_checksum(source)
        bucket = Bucket(environment, key, checksum)
        self.load_bytecode(bucket)
        return bucket

    def set_bucket(self, bucket):
        """Put the bucket into the cache."""
        self.dump_bytecode(bucket)


class FileSystemBytecodeCache(BytecodeCache):
    """A bytecode cache that stores bytecode on the filesystem.  It accepts
    two arguments: The directory where the cache items are stored and a
    pattern string that is used to build the filename.

    If no directory is specified the system temporary items folder is used.

    The pattern can be used to have multiple separate caches operate on the
    same directory.  The default pattern is ``'__jinja2_%s.cache'``.  ``%s``
    is replaced with the cache key.

    >>> bcc = FileSystemBytecodeCache('/tmp/jinja_cache', '%s.cache')

    This bytecode cache supports clearing of the cache using the clear method.
    """

    def __init__(self, directory=None, pattern='__jinja2_%s.cache'):
        if directory is None:
            directory = tempfile.gettempdir()
        self.directory = directory
        self.pattern = pattern

    def _get_cache_filename(self, bucket):
        return path.join(self.directory, self.pattern % bucket.key)

    def load_bytecode(self, bucket):
        f = open_if_exists(self._get_cache_filename(bucket), 'rb')
        if f is not None:
            try:
                bucket.load_bytecode(f)
            finally:
                f.close()

    def dump_bytecode(self, bucket):
        f = open(self._get_cache_filename(bucket), 'wb')
        try:
            bucket.write_bytecode(f)
        finally:
            f.close()

    def clear(self):
        # imported lazily here because google app-engine doesn't support
        # write access on the file system and the function does not exist
        # normally.
        from os import remove
        files = fnmatch.filter(listdir(self.directory), self.pattern % '*')
        for filename in files:
            try:
                remove(path.join(self.directory, filename))
            except OSError:
                pass


class MemcachedBytecodeCache(BytecodeCache):
    """This class implements a bytecode cache that uses a memcache cache for
    storing the information.  It does not enforce a specific memcache library
    (tummy's memcache or cmemcache) but will accept any class that provides
    the minimal interface required.

    Libraries compatible with this class:

    -   `werkzeug <http://werkzeug.pocoo.org/>`_.contrib.cache
    -   `python-memcached <http://www.tummy.com/Community/software/python-memcached/>`_
    -   `cmemcache <http://gijsbert.org/cmemcache/>`_

    (Unfortunately the django cache interface is not compatible because it
    does not support storing binary data, only unicode.  You can however pass
    the underlying cache client to the bytecode cache which is available
    as `django.core.cache.cache._client`.)

    The minimal interface for the client passed to the constructor is this:

    .. class:: MinimalClientInterface

        .. method:: set(key, value[, timeout])

            Stores the bytecode in the cache.  `value` is a string and
            `timeout` the timeout of the key.  If timeout is not provided
            a default timeout or no timeout should be assumed, if it's
            provided it's an integer with the number of seconds the cache
            item should exist.

        .. method:: get(key)

            Returns the value for the cache key.  If the item does not
            exist in the cache the return value must be `None`.

    The other arguments to the constructor are the prefix for all keys that
    is added before the actual cache key and the timeout for the bytecode in
    the cache system.  We recommend a high (or no) timeout.

    This bytecode cache does not support clearing of used items in the cache.
    The clear method is a no-operation function.
    """

    def __init__(self, client, prefix='jinja2/bytecode/', timeout=None):
        self.client = client
        self.prefix = prefix
        self.timeout = timeout

    def load_bytecode(self, bucket):
        code = self.client.get(self.prefix + bucket.key)
        if code is not None:
            bucket.bytecode_from_string(code)

    def dump_bytecode(self, bucket):
        args = (self.prefix + bucket.key, bucket.bytecode_to_string())
        if self.timeout is not None:
            args += (self.timeout,)
        self.client.set(*args)

########NEW FILE########
__FILENAME__ = compiler
# -*- coding: utf-8 -*-
"""
    jinja2.compiler
    ~~~~~~~~~~~~~~~

    Compiles nodes into python code.

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD, see LICENSE for more details.
"""
from cStringIO import StringIO
from itertools import chain
from copy import deepcopy
from jinja2 import nodes
from jinja2.nodes import EvalContext
from jinja2.visitor import NodeVisitor
from jinja2.exceptions import TemplateAssertionError
from jinja2.utils import Markup, concat, escape, is_python_keyword, next


operators = {
    'eq':       '==',
    'ne':       '!=',
    'gt':       '>',
    'gteq':     '>=',
    'lt':       '<',
    'lteq':     '<=',
    'in':       'in',
    'notin':    'not in'
}

try:
    exec '(0 if 0 else 0)'
except SyntaxError:
    have_condexpr = False
else:
    have_condexpr = True


# what method to iterate over items do we want to use for dict iteration
# in generated code?  on 2.x let's go with iteritems, on 3.x with items
if hasattr(dict, 'iteritems'):
    dict_item_iter = 'iteritems'
else:
    dict_item_iter = 'items'


# does if 0: dummy(x) get us x into the scope?
def unoptimize_before_dead_code():
    x = 42
    def f():
        if 0: dummy(x)
    return f
unoptimize_before_dead_code = bool(unoptimize_before_dead_code().func_closure)


def generate(node, environment, name, filename, stream=None,
             defer_init=False):
    """Generate the python source for a node tree."""
    if not isinstance(node, nodes.Template):
        raise TypeError('Can\'t compile non template nodes')
    generator = CodeGenerator(environment, name, filename, stream, defer_init)
    generator.visit(node)
    if stream is None:
        return generator.stream.getvalue()


def has_safe_repr(value):
    """Does the node have a safe representation?"""
    if value is None or value is NotImplemented or value is Ellipsis:
        return True
    if isinstance(value, (bool, int, long, float, complex, basestring,
                          xrange, Markup)):
        return True
    if isinstance(value, (tuple, list, set, frozenset)):
        for item in value:
            if not has_safe_repr(item):
                return False
        return True
    elif isinstance(value, dict):
        for key, value in value.iteritems():
            if not has_safe_repr(key):
                return False
            if not has_safe_repr(value):
                return False
        return True
    return False


def find_undeclared(nodes, names):
    """Check if the names passed are accessed undeclared.  The return value
    is a set of all the undeclared names from the sequence of names found.
    """
    visitor = UndeclaredNameVisitor(names)
    try:
        for node in nodes:
            visitor.visit(node)
    except VisitorExit:
        pass
    return visitor.undeclared


class Identifiers(object):
    """Tracks the status of identifiers in frames."""

    def __init__(self):
        # variables that are known to be declared (probably from outer
        # frames or because they are special for the frame)
        self.declared = set()

        # undeclared variables from outer scopes
        self.outer_undeclared = set()

        # names that are accessed without being explicitly declared by
        # this one or any of the outer scopes.  Names can appear both in
        # declared and undeclared.
        self.undeclared = set()

        # names that are declared locally
        self.declared_locally = set()

        # names that are declared by parameters
        self.declared_parameter = set()

    def add_special(self, name):
        """Register a special name like `loop`."""
        self.undeclared.discard(name)
        self.declared.add(name)

    def is_declared(self, name):
        """Check if a name is declared in this or an outer scope."""
        if name in self.declared_locally or name in self.declared_parameter:
            return True
        return name in self.declared

    def copy(self):
        return deepcopy(self)


class Frame(object):
    """Holds compile time information for us."""

    def __init__(self, eval_ctx, parent=None):
        self.eval_ctx = eval_ctx
        self.identifiers = Identifiers()

        # a toplevel frame is the root + soft frames such as if conditions.
        self.toplevel = False

        # the root frame is basically just the outermost frame, so no if
        # conditions.  This information is used to optimize inheritance
        # situations.
        self.rootlevel = False

        # in some dynamic inheritance situations the compiler needs to add
        # write tests around output statements.
        self.require_output_check = parent and parent.require_output_check

        # inside some tags we are using a buffer rather than yield statements.
        # this for example affects {% filter %} or {% macro %}.  If a frame
        # is buffered this variable points to the name of the list used as
        # buffer.
        self.buffer = None

        # the name of the block we're in, otherwise None.
        self.block = parent and parent.block or None

        # a set of actually assigned names
        self.assigned_names = set()

        # the parent of this frame
        self.parent = parent

        if parent is not None:
            self.identifiers.declared.update(
                parent.identifiers.declared |
                parent.identifiers.declared_parameter |
                parent.assigned_names
            )
            self.identifiers.outer_undeclared.update(
                parent.identifiers.undeclared -
                self.identifiers.declared
            )
            self.buffer = parent.buffer

    def copy(self):
        """Create a copy of the current one."""
        rv = object.__new__(self.__class__)
        rv.__dict__.update(self.__dict__)
        rv.identifiers = object.__new__(self.identifiers.__class__)
        rv.identifiers.__dict__.update(self.identifiers.__dict__)
        return rv

    def inspect(self, nodes):
        """Walk the node and check for identifiers.  If the scope is hard (eg:
        enforce on a python level) overrides from outer scopes are tracked
        differently.
        """
        visitor = FrameIdentifierVisitor(self.identifiers)
        for node in nodes:
            visitor.visit(node)

    def find_shadowed(self, extra=()):
        """Find all the shadowed names.  extra is an iterable of variables
        that may be defined with `add_special` which may occour scoped.
        """
        i = self.identifiers
        return (i.declared | i.outer_undeclared) & \
               (i.declared_locally | i.declared_parameter) | \
               set(x for x in extra if i.is_declared(x))

    def inner(self):
        """Return an inner frame."""
        return Frame(self.eval_ctx, self)

    def soft(self):
        """Return a soft frame.  A soft frame may not be modified as
        standalone thing as it shares the resources with the frame it
        was created of, but it's not a rootlevel frame any longer.
        """
        rv = self.copy()
        rv.rootlevel = False
        return rv

    __copy__ = copy


class VisitorExit(RuntimeError):
    """Exception used by the `UndeclaredNameVisitor` to signal a stop."""


class DependencyFinderVisitor(NodeVisitor):
    """A visitor that collects filter and test calls."""

    def __init__(self):
        self.filters = set()
        self.tests = set()

    def visit_Filter(self, node):
        self.generic_visit(node)
        self.filters.add(node.name)

    def visit_Test(self, node):
        self.generic_visit(node)
        self.tests.add(node.name)

    def visit_Block(self, node):
        """Stop visiting at blocks."""


class UndeclaredNameVisitor(NodeVisitor):
    """A visitor that checks if a name is accessed without being
    declared.  This is different from the frame visitor as it will
    not stop at closure frames.
    """

    def __init__(self, names):
        self.names = set(names)
        self.undeclared = set()

    def visit_Name(self, node):
        if node.ctx == 'load' and node.name in self.names:
            self.undeclared.add(node.name)
            if self.undeclared == self.names:
                raise VisitorExit()
        else:
            self.names.discard(node.name)

    def visit_Block(self, node):
        """Stop visiting a blocks."""


class FrameIdentifierVisitor(NodeVisitor):
    """A visitor for `Frame.inspect`."""

    def __init__(self, identifiers):
        self.identifiers = identifiers

    def visit_Name(self, node):
        """All assignments to names go through this function."""
        if node.ctx == 'store':
            self.identifiers.declared_locally.add(node.name)
        elif node.ctx == 'param':
            self.identifiers.declared_parameter.add(node.name)
        elif node.ctx == 'load' and not \
             self.identifiers.is_declared(node.name):
            self.identifiers.undeclared.add(node.name)

    def visit_If(self, node):
        self.visit(node.test)
        real_identifiers = self.identifiers

        old_names = real_identifiers.declared_locally | \
                    real_identifiers.declared_parameter

        def inner_visit(nodes):
            if not nodes:
                return set()
            self.identifiers = real_identifiers.copy()
            for subnode in nodes:
                self.visit(subnode)
            rv = self.identifiers.declared_locally - old_names
            # we have to remember the undeclared variables of this branch
            # because we will have to pull them.
            real_identifiers.undeclared.update(self.identifiers.undeclared)
            self.identifiers = real_identifiers
            return rv

        body = inner_visit(node.body)
        else_ = inner_visit(node.else_ or ())

        # the differences between the two branches are also pulled as
        # undeclared variables
        real_identifiers.undeclared.update(body.symmetric_difference(else_) -
                                           real_identifiers.declared)

        # remember those that are declared.
        real_identifiers.declared_locally.update(body | else_)

    def visit_Macro(self, node):
        self.identifiers.declared_locally.add(node.name)

    def visit_Import(self, node):
        self.generic_visit(node)
        self.identifiers.declared_locally.add(node.target)

    def visit_FromImport(self, node):
        self.generic_visit(node)
        for name in node.names:
            if isinstance(name, tuple):
                self.identifiers.declared_locally.add(name[1])
            else:
                self.identifiers.declared_locally.add(name)

    def visit_Assign(self, node):
        """Visit assignments in the correct order."""
        self.visit(node.node)
        self.visit(node.target)

    def visit_For(self, node):
        """Visiting stops at for blocks.  However the block sequence
        is visited as part of the outer scope.
        """
        self.visit(node.iter)

    def visit_CallBlock(self, node):
        self.visit(node.call)

    def visit_FilterBlock(self, node):
        self.visit(node.filter)

    def visit_Scope(self, node):
        """Stop visiting at scopes."""

    def visit_Block(self, node):
        """Stop visiting at blocks."""


class CompilerExit(Exception):
    """Raised if the compiler encountered a situation where it just
    doesn't make sense to further process the code.  Any block that
    raises such an exception is not further processed.
    """


class CodeGenerator(NodeVisitor):

    def __init__(self, environment, name, filename, stream=None,
                 defer_init=False):
        if stream is None:
            stream = StringIO()
        self.environment = environment
        self.name = name
        self.filename = filename
        self.stream = stream
        self.created_block_context = False
        self.defer_init = defer_init

        # aliases for imports
        self.import_aliases = {}

        # a registry for all blocks.  Because blocks are moved out
        # into the global python scope they are registered here
        self.blocks = {}

        # the number of extends statements so far
        self.extends_so_far = 0

        # some templates have a rootlevel extends.  In this case we
        # can safely assume that we're a child template and do some
        # more optimizations.
        self.has_known_extends = False

        # the current line number
        self.code_lineno = 1

        # registry of all filters and tests (global, not block local)
        self.tests = {}
        self.filters = {}

        # the debug information
        self.debug_info = []
        self._write_debug_info = None

        # the number of new lines before the next write()
        self._new_lines = 0

        # the line number of the last written statement
        self._last_line = 0

        # true if nothing was written so far.
        self._first_write = True

        # used by the `temporary_identifier` method to get new
        # unique, temporary identifier
        self._last_identifier = 0

        # the current indentation
        self._indentation = 0

    # -- Various compilation helpers

    def fail(self, msg, lineno):
        """Fail with a :exc:`TemplateAssertionError`."""
        raise TemplateAssertionError(msg, lineno, self.name, self.filename)

    def temporary_identifier(self):
        """Get a new unique identifier."""
        self._last_identifier += 1
        return 't_%d' % self._last_identifier

    def buffer(self, frame):
        """Enable buffering for the frame from that point onwards."""
        frame.buffer = self.temporary_identifier()
        self.writeline('%s = []' % frame.buffer)

    def return_buffer_contents(self, frame):
        """Return the buffer contents of the frame."""
        if frame.eval_ctx.volatile:
            self.writeline('if context.eval_ctx.autoescape:')
            self.indent()
            self.writeline('return Markup(concat(%s))' % frame.buffer)
            self.outdent()
            self.writeline('else:')
            self.indent()
            self.writeline('return concat(%s)' % frame.buffer)
            self.outdent()
        elif frame.eval_ctx.autoescape:
            self.writeline('return Markup(concat(%s))' % frame.buffer)
        else:
            self.writeline('return concat(%s)' % frame.buffer)

    def indent(self):
        """Indent by one."""
        self._indentation += 1

    def outdent(self, step=1):
        """Outdent by step."""
        self._indentation -= step

    def start_write(self, frame, node=None):
        """Yield or write into the frame buffer."""
        if frame.buffer is None:
            self.writeline('yield ', node)
        else:
            self.writeline('%s.append(' % frame.buffer, node)

    def end_write(self, frame):
        """End the writing process started by `start_write`."""
        if frame.buffer is not None:
            self.write(')')

    def simple_write(self, s, frame, node=None):
        """Simple shortcut for start_write + write + end_write."""
        self.start_write(frame, node)
        self.write(s)
        self.end_write(frame)

    def blockvisit(self, nodes, frame):
        """Visit a list of nodes as block in a frame.  If the current frame
        is no buffer a dummy ``if 0: yield None`` is written automatically
        unless the force_generator parameter is set to False.
        """
        if frame.buffer is None:
            self.writeline('if 0: yield None')
        else:
            self.writeline('pass')
        try:
            for node in nodes:
                self.visit(node, frame)
        except CompilerExit:
            pass

    def write(self, x):
        """Write a string into the output stream."""
        if self._new_lines:
            if not self._first_write:
                self.stream.write('\n' * self._new_lines)
                self.code_lineno += self._new_lines
                if self._write_debug_info is not None:
                    self.debug_info.append((self._write_debug_info,
                                            self.code_lineno))
                    self._write_debug_info = None
            self._first_write = False
            self.stream.write('    ' * self._indentation)
            self._new_lines = 0
        self.stream.write(x)

    def writeline(self, x, node=None, extra=0):
        """Combination of newline and write."""
        self.newline(node, extra)
        self.write(x)

    def newline(self, node=None, extra=0):
        """Add one or more newlines before the next write."""
        self._new_lines = max(self._new_lines, 1 + extra)
        if node is not None and node.lineno != self._last_line:
            self._write_debug_info = node.lineno
            self._last_line = node.lineno

    def signature(self, node, frame, extra_kwargs=None):
        """Writes a function call to the stream for the current node.
        A leading comma is added automatically.  The extra keyword
        arguments may not include python keywords otherwise a syntax
        error could occour.  The extra keyword arguments should be given
        as python dict.
        """
        # if any of the given keyword arguments is a python keyword
        # we have to make sure that no invalid call is created.
        kwarg_workaround = False
        for kwarg in chain((x.key for x in node.kwargs), extra_kwargs or ()):
            if is_python_keyword(kwarg):
                kwarg_workaround = True
                break

        for arg in node.args:
            self.write(', ')
            self.visit(arg, frame)

        if not kwarg_workaround:
            for kwarg in node.kwargs:
                self.write(', ')
                self.visit(kwarg, frame)
            if extra_kwargs is not None:
                for key, value in extra_kwargs.iteritems():
                    self.write(', %s=%s' % (key, value))
        if node.dyn_args:
            self.write(', *')
            self.visit(node.dyn_args, frame)

        if kwarg_workaround:
            if node.dyn_kwargs is not None:
                self.write(', **dict({')
            else:
                self.write(', **{')
            for kwarg in node.kwargs:
                self.write('%r: ' % kwarg.key)
                self.visit(kwarg.value, frame)
                self.write(', ')
            if extra_kwargs is not None:
                for key, value in extra_kwargs.iteritems():
                    self.write('%r: %s, ' % (key, value))
            if node.dyn_kwargs is not None:
                self.write('}, **')
                self.visit(node.dyn_kwargs, frame)
                self.write(')')
            else:
                self.write('}')

        elif node.dyn_kwargs is not None:
            self.write(', **')
            self.visit(node.dyn_kwargs, frame)

    def pull_locals(self, frame):
        """Pull all the references identifiers into the local scope."""
        for name in frame.identifiers.undeclared:
            self.writeline('l_%s = context.resolve(%r)' % (name, name))

    def pull_dependencies(self, nodes):
        """Pull all the dependencies."""
        visitor = DependencyFinderVisitor()
        for node in nodes:
            visitor.visit(node)
        for dependency in 'filters', 'tests':
            mapping = getattr(self, dependency)
            for name in getattr(visitor, dependency):
                if name not in mapping:
                    mapping[name] = self.temporary_identifier()
                self.writeline('%s = environment.%s[%r]' %
                               (mapping[name], dependency, name))

    def unoptimize_scope(self, frame):
        """Disable Python optimizations for the frame."""
        # XXX: this is not that nice but it has no real overhead.  It
        # mainly works because python finds the locals before dead code
        # is removed.  If that breaks we have to add a dummy function
        # that just accepts the arguments and does nothing.
        if frame.identifiers.declared:
            self.writeline('%sdummy(%s)' % (
                unoptimize_before_dead_code and 'if 0: ' or '',
                ', '.join('l_' + name for name in frame.identifiers.declared)
            ))

    def push_scope(self, frame, extra_vars=()):
        """This function returns all the shadowed variables in a dict
        in the form name: alias and will write the required assignments
        into the current scope.  No indentation takes place.

        This also predefines locally declared variables from the loop
        body because under some circumstances it may be the case that

        `extra_vars` is passed to `Frame.find_shadowed`.
        """
        aliases = {}
        for name in frame.find_shadowed(extra_vars):
            aliases[name] = ident = self.temporary_identifier()
            self.writeline('%s = l_%s' % (ident, name))
        to_declare = set()
        for name in frame.identifiers.declared_locally:
            if name not in aliases:
                to_declare.add('l_' + name)
        if to_declare:
            self.writeline(' = '.join(to_declare) + ' = missing')
        return aliases

    def pop_scope(self, aliases, frame):
        """Restore all aliases and delete unused variables."""
        for name, alias in aliases.iteritems():
            self.writeline('l_%s = %s' % (name, alias))
        to_delete = set()
        for name in frame.identifiers.declared_locally:
            if name not in aliases:
                to_delete.add('l_' + name)
        if to_delete:
            # we cannot use the del statement here because enclosed
            # scopes can trigger a SyntaxError:
            #   a = 42; b = lambda: a; del a
            self.writeline(' = '.join(to_delete) + ' = missing')

    def function_scoping(self, node, frame, children=None,
                         find_special=True):
        """In Jinja a few statements require the help of anonymous
        functions.  Those are currently macros and call blocks and in
        the future also recursive loops.  As there is currently
        technical limitation that doesn't allow reading and writing a
        variable in a scope where the initial value is coming from an
        outer scope, this function tries to fall back with a common
        error message.  Additionally the frame passed is modified so
        that the argumetns are collected and callers are looked up.

        This will return the modified frame.
        """
        # we have to iterate twice over it, make sure that works
        if children is None:
            children = node.iter_child_nodes()
        children = list(children)
        func_frame = frame.inner()
        func_frame.inspect(children)

        # variables that are undeclared (accessed before declaration) and
        # declared locally *and* part of an outside scope raise a template
        # assertion error. Reason: we can't generate reasonable code from
        # it without aliasing all the variables.
        # this could be fixed in Python 3 where we have the nonlocal
        # keyword or if we switch to bytecode generation
        overriden_closure_vars = (
            func_frame.identifiers.undeclared &
            func_frame.identifiers.declared &
            (func_frame.identifiers.declared_locally |
             func_frame.identifiers.declared_parameter)
        )
        if overriden_closure_vars:
            self.fail('It\'s not possible to set and access variables '
                      'derived from an outer scope! (affects: %s)' %
                      ', '.join(sorted(overriden_closure_vars)), node.lineno)

        # remove variables from a closure from the frame's undeclared
        # identifiers.
        func_frame.identifiers.undeclared -= (
            func_frame.identifiers.undeclared &
            func_frame.identifiers.declared
        )

        # no special variables for this scope, abort early
        if not find_special:
            return func_frame

        func_frame.accesses_kwargs = False
        func_frame.accesses_varargs = False
        func_frame.accesses_caller = False
        func_frame.arguments = args = ['l_' + x.name for x in node.args]

        undeclared = find_undeclared(children, ('caller', 'kwargs', 'varargs'))

        if 'caller' in undeclared:
            func_frame.accesses_caller = True
            func_frame.identifiers.add_special('caller')
            args.append('l_caller')
        if 'kwargs' in undeclared:
            func_frame.accesses_kwargs = True
            func_frame.identifiers.add_special('kwargs')
            args.append('l_kwargs')
        if 'varargs' in undeclared:
            func_frame.accesses_varargs = True
            func_frame.identifiers.add_special('varargs')
            args.append('l_varargs')
        return func_frame

    def macro_body(self, node, frame, children=None):
        """Dump the function def of a macro or call block."""
        frame = self.function_scoping(node, frame, children)
        # macros are delayed, they never require output checks
        frame.require_output_check = False
        args = frame.arguments
        # XXX: this is an ugly fix for the loop nesting bug
        # (tests.test_old_bugs.test_loop_call_bug).  This works around
        # a identifier nesting problem we have in general.  It's just more
        # likely to happen in loops which is why we work around it.  The
        # real solution would be "nonlocal" all the identifiers that are
        # leaking into a new python frame and might be used both unassigned
        # and assigned.
        if 'loop' in frame.identifiers.declared:
            args = args + ['l_loop=l_loop']
        self.writeline('def macro(%s):' % ', '.join(args), node)
        self.indent()
        self.buffer(frame)
        self.pull_locals(frame)
        self.blockvisit(node.body, frame)
        self.return_buffer_contents(frame)
        self.outdent()
        return frame

    def macro_def(self, node, frame):
        """Dump the macro definition for the def created by macro_body."""
        arg_tuple = ', '.join(repr(x.name) for x in node.args)
        name = getattr(node, 'name', None)
        if len(node.args) == 1:
            arg_tuple += ','
        self.write('Macro(environment, macro, %r, (%s), (' %
                   (name, arg_tuple))
        for arg in node.defaults:
            self.visit(arg, frame)
            self.write(', ')
        self.write('), %r, %r, %r)' % (
            bool(frame.accesses_kwargs),
            bool(frame.accesses_varargs),
            bool(frame.accesses_caller)
        ))

    def position(self, node):
        """Return a human readable position for the node."""
        rv = 'line %d' % node.lineno
        if self.name is not None:
            rv += ' in ' + repr(self.name)
        return rv

    # -- Statement Visitors

    def visit_Template(self, node, frame=None):
        assert frame is None, 'no root frame allowed'
        eval_ctx = EvalContext(self.environment, self.name)

        from jinja2.runtime import __all__ as exported
        self.writeline('from __future__ import division')
        self.writeline('from jinja2.runtime import ' + ', '.join(exported))
        if not unoptimize_before_dead_code:
            self.writeline('dummy = lambda *x: None')

        # if we want a deferred initialization we cannot move the
        # environment into a local name
        envenv = not self.defer_init and ', environment=environment' or ''

        # do we have an extends tag at all?  If not, we can save some
        # overhead by just not processing any inheritance code.
        have_extends = node.find(nodes.Extends) is not None

        # find all blocks
        for block in node.find_all(nodes.Block):
            if block.name in self.blocks:
                self.fail('block %r defined twice' % block.name, block.lineno)
            self.blocks[block.name] = block

        # find all imports and import them
        for import_ in node.find_all(nodes.ImportedName):
            if import_.importname not in self.import_aliases:
                imp = import_.importname
                self.import_aliases[imp] = alias = self.temporary_identifier()
                if '.' in imp:
                    module, obj = imp.rsplit('.', 1)
                    self.writeline('from %s import %s as %s' %
                                   (module, obj, alias))
                else:
                    self.writeline('import %s as %s' % (imp, alias))

        # add the load name
        self.writeline('name = %r' % self.name)

        # generate the root render function.
        self.writeline('def root(context%s):' % envenv, extra=1)

        # process the root
        frame = Frame(eval_ctx)
        frame.inspect(node.body)
        frame.toplevel = frame.rootlevel = True
        frame.require_output_check = have_extends and not self.has_known_extends
        self.indent()
        if have_extends:
            self.writeline('parent_template = None')
        if 'self' in find_undeclared(node.body, ('self',)):
            frame.identifiers.add_special('self')
            self.writeline('l_self = TemplateReference(context)')
        self.pull_locals(frame)
        self.pull_dependencies(node.body)
        self.blockvisit(node.body, frame)
        self.outdent()

        # make sure that the parent root is called.
        if have_extends:
            if not self.has_known_extends:
                self.indent()
                self.writeline('if parent_template is not None:')
            self.indent()
            self.writeline('for event in parent_template.'
                           'root_render_func(context):')
            self.indent()
            self.writeline('yield event')
            self.outdent(2 + (not self.has_known_extends))

        # at this point we now have the blocks collected and can visit them too.
        for name, block in self.blocks.iteritems():
            block_frame = Frame(eval_ctx)
            block_frame.inspect(block.body)
            block_frame.block = name
            self.writeline('def block_%s(context%s):' % (name, envenv),
                           block, 1)
            self.indent()
            undeclared = find_undeclared(block.body, ('self', 'super'))
            if 'self' in undeclared:
                block_frame.identifiers.add_special('self')
                self.writeline('l_self = TemplateReference(context)')
            if 'super' in undeclared:
                block_frame.identifiers.add_special('super')
                self.writeline('l_super = context.super(%r, '
                               'block_%s)' % (name, name))
            self.pull_locals(block_frame)
            self.pull_dependencies(block.body)
            self.blockvisit(block.body, block_frame)
            self.outdent()

        self.writeline('blocks = {%s}' % ', '.join('%r: block_%s' % (x, x)
                                                   for x in self.blocks),
                       extra=1)

        # add a function that returns the debug info
        self.writeline('debug_info = %r' % '&'.join('%s=%s' % x for x
                                                    in self.debug_info))

    def visit_Block(self, node, frame):
        """Call a block and register it for the template."""
        level = 1
        if frame.toplevel:
            # if we know that we are a child template, there is no need to
            # check if we are one
            if self.has_known_extends:
                return
            if self.extends_so_far > 0:
                self.writeline('if parent_template is None:')
                self.indent()
                level += 1
        context = node.scoped and 'context.derived(locals())' or 'context'
        self.writeline('for event in context.blocks[%r][0](%s):' % (
                       node.name, context), node)
        self.indent()
        self.simple_write('event', frame)
        self.outdent(level)

    def visit_Extends(self, node, frame):
        """Calls the extender."""
        if not frame.toplevel:
            self.fail('cannot use extend from a non top-level scope',
                      node.lineno)

        # if the number of extends statements in general is zero so
        # far, we don't have to add a check if something extended
        # the template before this one.
        if self.extends_so_far > 0:

            # if we have a known extends we just add a template runtime
            # error into the generated code.  We could catch that at compile
            # time too, but i welcome it not to confuse users by throwing the
            # same error at different times just "because we can".
            if not self.has_known_extends:
                self.writeline('if parent_template is not None:')
                self.indent()
            self.writeline('raise TemplateRuntimeError(%r)' %
                           'extended multiple times')
            self.outdent()

            # if we have a known extends already we don't need that code here
            # as we know that the template execution will end here.
            if self.has_known_extends:
                raise CompilerExit()

        self.writeline('parent_template = environment.get_template(', node)
        self.visit(node.template, frame)
        self.write(', %r)' % self.name)
        self.writeline('for name, parent_block in parent_template.'
                       'blocks.%s():' % dict_item_iter)
        self.indent()
        self.writeline('context.blocks.setdefault(name, []).'
                       'append(parent_block)')
        self.outdent()

        # if this extends statement was in the root level we can take
        # advantage of that information and simplify the generated code
        # in the top level from this point onwards
        if frame.rootlevel:
            self.has_known_extends = True

        # and now we have one more
        self.extends_so_far += 1

    def visit_Include(self, node, frame):
        """Handles includes."""
        if node.with_context:
            self.unoptimize_scope(frame)
        if node.ignore_missing:
            self.writeline('try:')
            self.indent()

        func_name = 'get_or_select_template'
        if isinstance(node.template, nodes.Const):
            if isinstance(node.template.value, basestring):
                func_name = 'get_template'
            elif isinstance(node.template.value, (tuple, list)):
                func_name = 'select_template'
        elif isinstance(node.template, (nodes.Tuple, nodes.List)):
            func_name = 'select_template'

        self.writeline('template = environment.%s(' % func_name, node)
        self.visit(node.template, frame)
        self.write(', %r)' % self.name)
        if node.ignore_missing:
            self.outdent()
            self.writeline('except TemplateNotFound:')
            self.indent()
            self.writeline('pass')
            self.outdent()
            self.writeline('else:')
            self.indent()

        if node.with_context:
            self.writeline('for event in template.root_render_func('
                           'template.new_context(context.parent, True, '
                           'locals())):')
        else:
            self.writeline('for event in template.module._body_stream:')

        self.indent()
        self.simple_write('event', frame)
        self.outdent()

        if node.ignore_missing:
            self.outdent()

    def visit_Import(self, node, frame):
        """Visit regular imports."""
        if node.with_context:
            self.unoptimize_scope(frame)
        self.writeline('l_%s = ' % node.target, node)
        if frame.toplevel:
            self.write('context.vars[%r] = ' % node.target)
        self.write('environment.get_template(')
        self.visit(node.template, frame)
        self.write(', %r).' % self.name)
        if node.with_context:
            self.write('make_module(context.parent, True, locals())')
        else:
            self.write('module')
        if frame.toplevel and not node.target.startswith('_'):
            self.writeline('context.exported_vars.discard(%r)' % node.target)
        frame.assigned_names.add(node.target)

    def visit_FromImport(self, node, frame):
        """Visit named imports."""
        self.newline(node)
        self.write('included_template = environment.get_template(')
        self.visit(node.template, frame)
        self.write(', %r).' % self.name)
        if node.with_context:
            self.write('make_module(context.parent, True)')
        else:
            self.write('module')

        var_names = []
        discarded_names = []
        for name in node.names:
            if isinstance(name, tuple):
                name, alias = name
            else:
                alias = name
            self.writeline('l_%s = getattr(included_template, '
                           '%r, missing)' % (alias, name))
            self.writeline('if l_%s is missing:' % alias)
            self.indent()
            self.writeline('l_%s = environment.undefined(%r %% '
                           'included_template.__name__, '
                           'name=%r)' %
                           (alias, 'the template %%r (imported on %s) does '
                           'not export the requested name %s' % (
                                self.position(node),
                                repr(name)
                           ), name))
            self.outdent()
            if frame.toplevel:
                var_names.append(alias)
                if not alias.startswith('_'):
                    discarded_names.append(alias)
            frame.assigned_names.add(alias)

        if var_names:
            if len(var_names) == 1:
                name = var_names[0]
                self.writeline('context.vars[%r] = l_%s' % (name, name))
            else:
                self.writeline('context.vars.update({%s})' % ', '.join(
                    '%r: l_%s' % (name, name) for name in var_names
                ))
        if discarded_names:
            if len(discarded_names) == 1:
                self.writeline('context.exported_vars.discard(%r)' %
                               discarded_names[0])
            else:
                self.writeline('context.exported_vars.difference_'
                               'update((%s))' % ', '.join(map(repr, discarded_names)))

    def visit_For(self, node, frame):
        # when calculating the nodes for the inner frame we have to exclude
        # the iterator contents from it
        children = node.iter_child_nodes(exclude=('iter',))
        if node.recursive:
            loop_frame = self.function_scoping(node, frame, children,
                                               find_special=False)
        else:
            loop_frame = frame.inner()
            loop_frame.inspect(children)

        # try to figure out if we have an extended loop.  An extended loop
        # is necessary if the loop is in recursive mode if the special loop
        # variable is accessed in the body.
        extended_loop = node.recursive or 'loop' in \
                        find_undeclared(node.iter_child_nodes(
                            only=('body',)), ('loop',))

        # if we don't have an recursive loop we have to find the shadowed
        # variables at that point.  Because loops can be nested but the loop
        # variable is a special one we have to enforce aliasing for it.
        if not node.recursive:
            aliases = self.push_scope(loop_frame, ('loop',))

        # otherwise we set up a buffer and add a function def
        else:
            self.writeline('def loop(reciter, loop_render_func):', node)
            self.indent()
            self.buffer(loop_frame)
            aliases = {}

        # make sure the loop variable is a special one and raise a template
        # assertion error if a loop tries to write to loop
        if extended_loop:
            loop_frame.identifiers.add_special('loop')
        for name in node.find_all(nodes.Name):
            if name.ctx == 'store' and name.name == 'loop':
                self.fail('Can\'t assign to special loop variable '
                          'in for-loop target', name.lineno)

        self.pull_locals(loop_frame)
        if node.else_:
            iteration_indicator = self.temporary_identifier()
            self.writeline('%s = 1' % iteration_indicator)

        # Create a fake parent loop if the else or test section of a
        # loop is accessing the special loop variable and no parent loop
        # exists.
        if 'loop' not in aliases and 'loop' in find_undeclared(
           node.iter_child_nodes(only=('else_', 'test')), ('loop',)):
            self.writeline("l_loop = environment.undefined(%r, name='loop')" %
                ("'loop' is undefined. the filter section of a loop as well "
                 "as the else block don't have access to the special 'loop'"
                 " variable of the current loop.  Because there is no parent "
                 "loop it's undefined.  Happened in loop on %s" %
                 self.position(node)))

        self.writeline('for ', node)
        self.visit(node.target, loop_frame)
        self.write(extended_loop and ', l_loop in LoopContext(' or ' in ')

        # if we have an extened loop and a node test, we filter in the
        # "outer frame".
        if extended_loop and node.test is not None:
            self.write('(')
            self.visit(node.target, loop_frame)
            self.write(' for ')
            self.visit(node.target, loop_frame)
            self.write(' in ')
            if node.recursive:
                self.write('reciter')
            else:
                self.visit(node.iter, loop_frame)
            self.write(' if (')
            test_frame = loop_frame.copy()
            self.visit(node.test, test_frame)
            self.write('))')

        elif node.recursive:
            self.write('reciter')
        else:
            self.visit(node.iter, loop_frame)

        if node.recursive:
            self.write(', recurse=loop_render_func):')
        else:
            self.write(extended_loop and '):' or ':')

        # tests in not extended loops become a continue
        if not extended_loop and node.test is not None:
            self.indent()
            self.writeline('if not ')
            self.visit(node.test, loop_frame)
            self.write(':')
            self.indent()
            self.writeline('continue')
            self.outdent(2)

        self.indent()
        self.blockvisit(node.body, loop_frame)
        if node.else_:
            self.writeline('%s = 0' % iteration_indicator)
        self.outdent()

        if node.else_:
            self.writeline('if %s:' % iteration_indicator)
            self.indent()
            self.blockvisit(node.else_, loop_frame)
            self.outdent()

        # reset the aliases if there are any.
        if not node.recursive:
            self.pop_scope(aliases, loop_frame)

        # if the node was recursive we have to return the buffer contents
        # and start the iteration code
        if node.recursive:
            self.return_buffer_contents(loop_frame)
            self.outdent()
            self.start_write(frame, node)
            self.write('loop(')
            self.visit(node.iter, frame)
            self.write(', loop)')
            self.end_write(frame)

    def visit_If(self, node, frame):
        if_frame = frame.soft()
        self.writeline('if ', node)
        self.visit(node.test, if_frame)
        self.write(':')
        self.indent()
        self.blockvisit(node.body, if_frame)
        self.outdent()
        if node.else_:
            self.writeline('else:')
            self.indent()
            self.blockvisit(node.else_, if_frame)
            self.outdent()

    def visit_Macro(self, node, frame):
        macro_frame = self.macro_body(node, frame)
        self.newline()
        if frame.toplevel:
            if not node.name.startswith('_'):
                self.write('context.exported_vars.add(%r)' % node.name)
            self.writeline('context.vars[%r] = ' % node.name)
        self.write('l_%s = ' % node.name)
        self.macro_def(node, macro_frame)
        frame.assigned_names.add(node.name)

    def visit_CallBlock(self, node, frame):
        children = node.iter_child_nodes(exclude=('call',))
        call_frame = self.macro_body(node, frame, children)
        self.writeline('caller = ')
        self.macro_def(node, call_frame)
        self.start_write(frame, node)
        self.visit_Call(node.call, call_frame, forward_caller=True)
        self.end_write(frame)

    def visit_FilterBlock(self, node, frame):
        filter_frame = frame.inner()
        filter_frame.inspect(node.iter_child_nodes())
        aliases = self.push_scope(filter_frame)
        self.pull_locals(filter_frame)
        self.buffer(filter_frame)
        self.blockvisit(node.body, filter_frame)
        self.start_write(frame, node)
        self.visit_Filter(node.filter, filter_frame)
        self.end_write(frame)
        self.pop_scope(aliases, filter_frame)

    def visit_ExprStmt(self, node, frame):
        self.newline(node)
        self.visit(node.node, frame)

    def visit_Output(self, node, frame):
        # if we have a known extends statement, we don't output anything
        # if we are in a require_output_check section
        if self.has_known_extends and frame.require_output_check:
            return

        if self.environment.finalize:
            finalize = lambda x: unicode(self.environment.finalize(x))
        else:
            finalize = unicode

        # if we are inside a frame that requires output checking, we do so
        outdent_later = False
        if frame.require_output_check:
            self.writeline('if parent_template is None:')
            self.indent()
            outdent_later = True

        # try to evaluate as many chunks as possible into a static
        # string at compile time.
        body = []
        for child in node.nodes:
            try:
                const = child.as_const(frame.eval_ctx)
            except nodes.Impossible:
                body.append(child)
                continue
            # the frame can't be volatile here, becaus otherwise the
            # as_const() function would raise an Impossible exception
            # at that point.
            try:
                if frame.eval_ctx.autoescape:
                    if hasattr(const, '__html__'):
                        const = const.__html__()
                    else:
                        const = escape(const)
                const = finalize(const)
            except Exception:
                # if something goes wrong here we evaluate the node
                # at runtime for easier debugging
                body.append(child)
                continue
            if body and isinstance(body[-1], list):
                body[-1].append(const)
            else:
                body.append([const])

        # if we have less than 3 nodes or a buffer we yield or extend/append
        if len(body) < 3 or frame.buffer is not None:
            if frame.buffer is not None:
                # for one item we append, for more we extend
                if len(body) == 1:
                    self.writeline('%s.append(' % frame.buffer)
                else:
                    self.writeline('%s.extend((' % frame.buffer)
                self.indent()
            for item in body:
                if isinstance(item, list):
                    val = repr(concat(item))
                    if frame.buffer is None:
                        self.writeline('yield ' + val)
                    else:
                        self.writeline(val + ', ')
                else:
                    if frame.buffer is None:
                        self.writeline('yield ', item)
                    else:
                        self.newline(item)
                    close = 1
                    if frame.eval_ctx.volatile:
                        self.write('(context.eval_ctx.autoescape and'
                                   ' escape or to_string)(')
                    elif frame.eval_ctx.autoescape:
                        self.write('escape(')
                    else:
                        self.write('to_string(')
                    if self.environment.finalize is not None:
                        self.write('environment.finalize(')
                        close += 1
                    self.visit(item, frame)
                    self.write(')' * close)
                    if frame.buffer is not None:
                        self.write(', ')
            if frame.buffer is not None:
                # close the open parentheses
                self.outdent()
                self.writeline(len(body) == 1 and ')' or '))')

        # otherwise we create a format string as this is faster in that case
        else:
            format = []
            arguments = []
            for item in body:
                if isinstance(item, list):
                    format.append(concat(item).replace('%', '%%'))
                else:
                    format.append('%s')
                    arguments.append(item)
            self.writeline('yield ')
            self.write(repr(concat(format)) + ' % (')
            idx = -1
            self.indent()
            for argument in arguments:
                self.newline(argument)
                close = 0
                if frame.eval_ctx.volatile:
                    self.write('(context.eval_ctx.autoescape and'
                               ' escape or to_string)(')
                    close += 1
                elif frame.eval_ctx.autoescape:
                    self.write('escape(')
                    close += 1
                if self.environment.finalize is not None:
                    self.write('environment.finalize(')
                    close += 1
                self.visit(argument, frame)
                self.write(')' * close + ', ')
            self.outdent()
            self.writeline(')')

        if outdent_later:
            self.outdent()

    def visit_Assign(self, node, frame):
        self.newline(node)
        # toplevel assignments however go into the local namespace and
        # the current template's context.  We create a copy of the frame
        # here and add a set so that the Name visitor can add the assigned
        # names here.
        if frame.toplevel:
            assignment_frame = frame.copy()
            assignment_frame.toplevel_assignments = set()
        else:
            assignment_frame = frame
        self.visit(node.target, assignment_frame)
        self.write(' = ')
        self.visit(node.node, frame)

        # make sure toplevel assignments are added to the context.
        if frame.toplevel:
            public_names = [x for x in assignment_frame.toplevel_assignments
                            if not x.startswith('_')]
            if len(assignment_frame.toplevel_assignments) == 1:
                name = next(iter(assignment_frame.toplevel_assignments))
                self.writeline('context.vars[%r] = l_%s' % (name, name))
            else:
                self.writeline('context.vars.update({')
                for idx, name in enumerate(assignment_frame.toplevel_assignments):
                    if idx:
                        self.write(', ')
                    self.write('%r: l_%s' % (name, name))
                self.write('})')
            if public_names:
                if len(public_names) == 1:
                    self.writeline('context.exported_vars.add(%r)' %
                                   public_names[0])
                else:
                    self.writeline('context.exported_vars.update((%s))' %
                                   ', '.join(map(repr, public_names)))

    # -- Expression Visitors

    def visit_Name(self, node, frame):
        if node.ctx == 'store' and frame.toplevel:
            frame.toplevel_assignments.add(node.name)
        self.write('l_' + node.name)
        frame.assigned_names.add(node.name)

    def visit_Const(self, node, frame):
        val = node.value
        if isinstance(val, float):
            self.write(str(val))
        else:
            self.write(repr(val))

    def visit_TemplateData(self, node, frame):
        try:
            self.write(repr(node.as_const(frame.eval_ctx)))
        except nodes.Impossible:
            self.write('(context.eval_ctx.autoescape and Markup or identity)(%r)'
                       % node.data)

    def visit_Tuple(self, node, frame):
        self.write('(')
        idx = -1
        for idx, item in enumerate(node.items):
            if idx:
                self.write(', ')
            self.visit(item, frame)
        self.write(idx == 0 and ',)' or ')')

    def visit_List(self, node, frame):
        self.write('[')
        for idx, item in enumerate(node.items):
            if idx:
                self.write(', ')
            self.visit(item, frame)
        self.write(']')

    def visit_Dict(self, node, frame):
        self.write('{')
        for idx, item in enumerate(node.items):
            if idx:
                self.write(', ')
            self.visit(item.key, frame)
            self.write(': ')
            self.visit(item.value, frame)
        self.write('}')

    def binop(operator, interceptable=True):
        def visitor(self, node, frame):
            if self.environment.sandboxed and \
               operator in self.environment.intercepted_binops:
                self.write('environment.call_binop(context, %r, ' % operator)
                self.visit(node.left, frame)
                self.write(', ')
                self.visit(node.right, frame)
            else:
                self.write('(')
                self.visit(node.left, frame)
                self.write(' %s ' % operator)
                self.visit(node.right, frame)
            self.write(')')
        return visitor

    def uaop(operator, interceptable=True):
        def visitor(self, node, frame):
            if self.environment.sandboxed and \
               operator in self.environment.intercepted_unops:
                self.write('environment.call_unop(context, %r, ' % operator)
                self.visit(node.node, frame)
            else:
                self.write('(' + operator)
                self.visit(node.node, frame)
            self.write(')')
        return visitor

    visit_Add = binop('+')
    visit_Sub = binop('-')
    visit_Mul = binop('*')
    visit_Div = binop('/')
    visit_FloorDiv = binop('//')
    visit_Pow = binop('**')
    visit_Mod = binop('%')
    visit_And = binop('and', interceptable=False)
    visit_Or = binop('or', interceptable=False)
    visit_Pos = uaop('+')
    visit_Neg = uaop('-')
    visit_Not = uaop('not ', interceptable=False)
    del binop, uaop

    def visit_Concat(self, node, frame):
        if frame.eval_ctx.volatile:
            func_name = '(context.eval_ctx.volatile and' \
                        ' markup_join or unicode_join)'
        elif frame.eval_ctx.autoescape:
            func_name = 'markup_join'
        else:
            func_name = 'unicode_join'
        self.write('%s((' % func_name)
        for arg in node.nodes:
            self.visit(arg, frame)
            self.write(', ')
        self.write('))')

    def visit_Compare(self, node, frame):
        self.visit(node.expr, frame)
        for op in node.ops:
            self.visit(op, frame)

    def visit_Operand(self, node, frame):
        self.write(' %s ' % operators[node.op])
        self.visit(node.expr, frame)

    def visit_Getattr(self, node, frame):
        self.write('environment.getattr(')
        self.visit(node.node, frame)
        self.write(', %r)' % node.attr)

    def visit_Getitem(self, node, frame):
        # slices bypass the environment getitem method.
        if isinstance(node.arg, nodes.Slice):
            self.visit(node.node, frame)
            self.write('[')
            self.visit(node.arg, frame)
            self.write(']')
        else:
            self.write('environment.getitem(')
            self.visit(node.node, frame)
            self.write(', ')
            self.visit(node.arg, frame)
            self.write(')')

    def visit_Slice(self, node, frame):
        if node.start is not None:
            self.visit(node.start, frame)
        self.write(':')
        if node.stop is not None:
            self.visit(node.stop, frame)
        if node.step is not None:
            self.write(':')
            self.visit(node.step, frame)

    def visit_Filter(self, node, frame):
        self.write(self.filters[node.name] + '(')
        func = self.environment.filters.get(node.name)
        if func is None:
            self.fail('no filter named %r' % node.name, node.lineno)
        if getattr(func, 'contextfilter', False):
            self.write('context, ')
        elif getattr(func, 'evalcontextfilter', False):
            self.write('context.eval_ctx, ')
        elif getattr(func, 'environmentfilter', False):
            self.write('environment, ')

        # if the filter node is None we are inside a filter block
        # and want to write to the current buffer
        if node.node is not None:
            self.visit(node.node, frame)
        elif frame.eval_ctx.volatile:
            self.write('(context.eval_ctx.autoescape and'
                       ' Markup(concat(%s)) or concat(%s))' %
                       (frame.buffer, frame.buffer))
        elif frame.eval_ctx.autoescape:
            self.write('Markup(concat(%s))' % frame.buffer)
        else:
            self.write('concat(%s)' % frame.buffer)
        self.signature(node, frame)
        self.write(')')

    def visit_Test(self, node, frame):
        self.write(self.tests[node.name] + '(')
        if node.name not in self.environment.tests:
            self.fail('no test named %r' % node.name, node.lineno)
        self.visit(node.node, frame)
        self.signature(node, frame)
        self.write(')')

    def visit_CondExpr(self, node, frame):
        def write_expr2():
            if node.expr2 is not None:
                return self.visit(node.expr2, frame)
            self.write('environment.undefined(%r)' % ('the inline if-'
                       'expression on %s evaluated to false and '
                       'no else section was defined.' % self.position(node)))

        if not have_condexpr:
            self.write('((')
            self.visit(node.test, frame)
            self.write(') and (')
            self.visit(node.expr1, frame)
            self.write(',) or (')
            write_expr2()
            self.write(',))[0]')
        else:
            self.write('(')
            self.visit(node.expr1, frame)
            self.write(' if ')
            self.visit(node.test, frame)
            self.write(' else ')
            write_expr2()
            self.write(')')

    def visit_Call(self, node, frame, forward_caller=False):
        if self.environment.sandboxed:
            self.write('environment.call(context, ')
        else:
            self.write('context.call(')
        self.visit(node.node, frame)
        extra_kwargs = forward_caller and {'caller': 'caller'} or None
        self.signature(node, frame, extra_kwargs)
        self.write(')')

    def visit_Keyword(self, node, frame):
        self.write(node.key + '=')
        self.visit(node.value, frame)

    # -- Unused nodes for extensions

    def visit_MarkSafe(self, node, frame):
        self.write('Markup(')
        self.visit(node.expr, frame)
        self.write(')')

    def visit_MarkSafeIfAutoescape(self, node, frame):
        self.write('(context.eval_ctx.autoescape and Markup or identity)(')
        self.visit(node.expr, frame)
        self.write(')')

    def visit_EnvironmentAttribute(self, node, frame):
        self.write('environment.' + node.name)

    def visit_ExtensionAttribute(self, node, frame):
        self.write('environment.extensions[%r].%s' % (node.identifier, node.name))

    def visit_ImportedName(self, node, frame):
        self.write(self.import_aliases[node.importname])

    def visit_InternalName(self, node, frame):
        self.write(node.name)

    def visit_ContextReference(self, node, frame):
        self.write('context')

    def visit_Continue(self, node, frame):
        self.writeline('continue', node)

    def visit_Break(self, node, frame):
        self.writeline('break', node)

    def visit_Scope(self, node, frame):
        scope_frame = frame.inner()
        scope_frame.inspect(node.iter_child_nodes())
        aliases = self.push_scope(scope_frame)
        self.pull_locals(scope_frame)
        self.blockvisit(node.body, scope_frame)
        self.pop_scope(aliases, scope_frame)

    def visit_EvalContextModifier(self, node, frame):
        for keyword in node.options:
            self.writeline('context.eval_ctx.%s = ' % keyword.key)
            self.visit(keyword.value, frame)
            try:
                val = keyword.value.as_const(frame.eval_ctx)
            except nodes.Impossible:
                frame.eval_ctx.volatile = True
            else:
                setattr(frame.eval_ctx, keyword.key, val)

    def visit_ScopedEvalContextModifier(self, node, frame):
        old_ctx_name = self.temporary_identifier()
        safed_ctx = frame.eval_ctx.save()
        self.writeline('%s = context.eval_ctx.save()' % old_ctx_name)
        self.visit_EvalContextModifier(node, frame)
        for child in node.body:
            self.visit(child, frame)
        frame.eval_ctx.revert(safed_ctx)
        self.writeline('context.eval_ctx.revert(%s)' % old_ctx_name)

########NEW FILE########
__FILENAME__ = constants
# -*- coding: utf-8 -*-
"""
    jinja.constants
    ~~~~~~~~~~~~~~~

    Various constants.

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD, see LICENSE for more details.
"""


#: list of lorem ipsum words used by the lipsum() helper function
LOREM_IPSUM_WORDS = u'''\
a ac accumsan ad adipiscing aenean aliquam aliquet amet ante aptent arcu at
auctor augue bibendum blandit class commodo condimentum congue consectetuer
consequat conubia convallis cras cubilia cum curabitur curae cursus dapibus
diam dictum dictumst dignissim dis dolor donec dui duis egestas eget eleifend
elementum elit enim erat eros est et etiam eu euismod facilisi facilisis fames
faucibus felis fermentum feugiat fringilla fusce gravida habitant habitasse hac
hendrerit hymenaeos iaculis id imperdiet in inceptos integer interdum ipsum
justo lacinia lacus laoreet lectus leo libero ligula litora lobortis lorem
luctus maecenas magna magnis malesuada massa mattis mauris metus mi molestie
mollis montes morbi mus nam nascetur natoque nec neque netus nibh nisi nisl non
nonummy nostra nulla nullam nunc odio orci ornare parturient pede pellentesque
penatibus per pharetra phasellus placerat platea porta porttitor posuere
potenti praesent pretium primis proin pulvinar purus quam quis quisque rhoncus
ridiculus risus rutrum sagittis sapien scelerisque sed sem semper senectus sit
sociis sociosqu sodales sollicitudin suscipit suspendisse taciti tellus tempor
tempus tincidunt torquent tortor tristique turpis ullamcorper ultrices
ultricies urna ut varius vehicula vel velit venenatis vestibulum vitae vivamus
viverra volutpat vulputate'''

########NEW FILE########
__FILENAME__ = debug
# -*- coding: utf-8 -*-
"""
    jinja2.debug
    ~~~~~~~~~~~~

    Implements the debug interface for Jinja.  This module does some pretty
    ugly stuff with the Python traceback system in order to achieve tracebacks
    with correct line numbers, locals and contents.

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD, see LICENSE for more details.
"""
import sys
import traceback
from types import TracebackType
from jinja2.utils import CodeType, missing, internal_code
from jinja2.exceptions import TemplateSyntaxError

# on pypy we can take advantage of transparent proxies
try:
    from __pypy__ import tproxy
except ImportError:
    tproxy = None


# how does the raise helper look like?
try:
    exec "raise TypeError, 'foo'"
except SyntaxError:
    raise_helper = 'raise __jinja_exception__[1]'
except TypeError:
    raise_helper = 'raise __jinja_exception__[0], __jinja_exception__[1]'


class TracebackFrameProxy(object):
    """Proxies a traceback frame."""

    def __init__(self, tb):
        self.tb = tb
        self._tb_next = None

    @property
    def tb_next(self):
        return self._tb_next

    def set_next(self, next):
        if tb_set_next is not None:
            try:
                tb_set_next(self.tb, next and next.tb or None)
            except Exception:
                # this function can fail due to all the hackery it does
                # on various python implementations.  We just catch errors
                # down and ignore them if necessary.
                pass
        self._tb_next = next

    @property
    def is_jinja_frame(self):
        return '__jinja_template__' in self.tb.tb_frame.f_globals

    def __getattr__(self, name):
        return getattr(self.tb, name)


def make_frame_proxy(frame):
    proxy = TracebackFrameProxy(frame)
    if tproxy is None:
        return proxy
    def operation_handler(operation, *args, **kwargs):
        if operation in ('__getattribute__', '__getattr__'):
            return getattr(proxy, args[0])
        elif operation == '__setattr__':
            proxy.__setattr__(*args, **kwargs)
        else:
            return getattr(proxy, operation)(*args, **kwargs)
    return tproxy(TracebackType, operation_handler)


class ProcessedTraceback(object):
    """Holds a Jinja preprocessed traceback for priting or reraising."""

    def __init__(self, exc_type, exc_value, frames):
        assert frames, 'no frames for this traceback?'
        self.exc_type = exc_type
        self.exc_value = exc_value
        self.frames = frames

        # newly concatenate the frames (which are proxies)
        prev_tb = None
        for tb in self.frames:
            if prev_tb is not None:
                prev_tb.set_next(tb)
            prev_tb = tb
        prev_tb.set_next(None)

    def render_as_text(self, limit=None):
        """Return a string with the traceback."""
        lines = traceback.format_exception(self.exc_type, self.exc_value,
                                           self.frames[0], limit=limit)
        return ''.join(lines).rstrip()

    def render_as_html(self, full=False):
        """Return a unicode string with the traceback as rendered HTML."""
        from jinja2.debugrenderer import render_traceback
        return u'%s\n\n<!--\n%s\n-->' % (
            render_traceback(self, full=full),
            self.render_as_text().decode('utf-8', 'replace')
        )

    @property
    def is_template_syntax_error(self):
        """`True` if this is a template syntax error."""
        return isinstance(self.exc_value, TemplateSyntaxError)

    @property
    def exc_info(self):
        """Exception info tuple with a proxy around the frame objects."""
        return self.exc_type, self.exc_value, self.frames[0]

    @property
    def standard_exc_info(self):
        """Standard python exc_info for re-raising"""
        tb = self.frames[0]
        # the frame will be an actual traceback (or transparent proxy) if
        # we are on pypy or a python implementation with support for tproxy
        if type(tb) is not TracebackType:
            tb = tb.tb
        return self.exc_type, self.exc_value, tb


def make_traceback(exc_info, source_hint=None):
    """Creates a processed traceback object from the exc_info."""
    exc_type, exc_value, tb = exc_info
    if isinstance(exc_value, TemplateSyntaxError):
        exc_info = translate_syntax_error(exc_value, source_hint)
        initial_skip = 0
    else:
        initial_skip = 1
    return translate_exception(exc_info, initial_skip)


def translate_syntax_error(error, source=None):
    """Rewrites a syntax error to please traceback systems."""
    error.source = source
    error.translated = True
    exc_info = (error.__class__, error, None)
    filename = error.filename
    if filename is None:
        filename = '<unknown>'
    return fake_exc_info(exc_info, filename, error.lineno)


def translate_exception(exc_info, initial_skip=0):
    """If passed an exc_info it will automatically rewrite the exceptions
    all the way down to the correct line numbers and frames.
    """
    tb = exc_info[2]
    frames = []

    # skip some internal frames if wanted
    for x in xrange(initial_skip):
        if tb is not None:
            tb = tb.tb_next
    initial_tb = tb

    while tb is not None:
        # skip frames decorated with @internalcode.  These are internal
        # calls we can't avoid and that are useless in template debugging
        # output.
        if tb.tb_frame.f_code in internal_code:
            tb = tb.tb_next
            continue

        # save a reference to the next frame if we override the current
        # one with a faked one.
        next = tb.tb_next

        # fake template exceptions
        template = tb.tb_frame.f_globals.get('__jinja_template__')
        if template is not None:
            lineno = template.get_corresponding_lineno(tb.tb_lineno)
            tb = fake_exc_info(exc_info[:2] + (tb,), template.filename,
                               lineno)[2]

        frames.append(make_frame_proxy(tb))
        tb = next

    # if we don't have any exceptions in the frames left, we have to
    # reraise it unchanged.
    # XXX: can we backup here?  when could this happen?
    if not frames:
        raise exc_info[0], exc_info[1], exc_info[2]

    return ProcessedTraceback(exc_info[0], exc_info[1], frames)


def fake_exc_info(exc_info, filename, lineno):
    """Helper for `translate_exception`."""
    exc_type, exc_value, tb = exc_info

    # figure the real context out
    if tb is not None:
        real_locals = tb.tb_frame.f_locals.copy()
        ctx = real_locals.get('context')
        if ctx:
            locals = ctx.get_all()
        else:
            locals = {}
        for name, value in real_locals.iteritems():
            if name.startswith('l_') and value is not missing:
                locals[name[2:]] = value

        # if there is a local called __jinja_exception__, we get
        # rid of it to not break the debug functionality.
        locals.pop('__jinja_exception__', None)
    else:
        locals = {}

    # assamble fake globals we need
    globals = {
        '__name__':             filename,
        '__file__':             filename,
        '__jinja_exception__':  exc_info[:2],

        # we don't want to keep the reference to the template around
        # to not cause circular dependencies, but we mark it as Jinja
        # frame for the ProcessedTraceback
        '__jinja_template__':   None
    }

    # and fake the exception
    code = compile('\n' * (lineno - 1) + raise_helper, filename, 'exec')

    # if it's possible, change the name of the code.  This won't work
    # on some python environments such as google appengine
    try:
        if tb is None:
            location = 'template'
        else:
            function = tb.tb_frame.f_code.co_name
            if function == 'root':
                location = 'top-level template code'
            elif function.startswith('block_'):
                location = 'block "%s"' % function[6:]
            else:
                location = 'template'
        code = CodeType(0, code.co_nlocals, code.co_stacksize,
                        code.co_flags, code.co_code, code.co_consts,
                        code.co_names, code.co_varnames, filename,
                        location, code.co_firstlineno,
                        code.co_lnotab, (), ())
    except:
        pass

    # execute the code and catch the new traceback
    try:
        exec code in globals, locals
    except:
        exc_info = sys.exc_info()
        new_tb = exc_info[2].tb_next

    # return without this frame
    return exc_info[:2] + (new_tb,)


def _init_ugly_crap():
    """This function implements a few ugly things so that we can patch the
    traceback objects.  The function returned allows resetting `tb_next` on
    any python traceback object.  Do not attempt to use this on non cpython
    interpreters
    """
    import ctypes
    from types import TracebackType

    # figure out side of _Py_ssize_t
    if hasattr(ctypes.pythonapi, 'Py_InitModule4_64'):
        _Py_ssize_t = ctypes.c_int64
    else:
        _Py_ssize_t = ctypes.c_int

    # regular python
    class _PyObject(ctypes.Structure):
        pass
    _PyObject._fields_ = [
        ('ob_refcnt', _Py_ssize_t),
        ('ob_type', ctypes.POINTER(_PyObject))
    ]

    # python with trace
    if hasattr(sys, 'getobjects'):
        class _PyObject(ctypes.Structure):
            pass
        _PyObject._fields_ = [
            ('_ob_next', ctypes.POINTER(_PyObject)),
            ('_ob_prev', ctypes.POINTER(_PyObject)),
            ('ob_refcnt', _Py_ssize_t),
            ('ob_type', ctypes.POINTER(_PyObject))
        ]

    class _Traceback(_PyObject):
        pass
    _Traceback._fields_ = [
        ('tb_next', ctypes.POINTER(_Traceback)),
        ('tb_frame', ctypes.POINTER(_PyObject)),
        ('tb_lasti', ctypes.c_int),
        ('tb_lineno', ctypes.c_int)
    ]

    def tb_set_next(tb, next):
        """Set the tb_next attribute of a traceback object."""
        if not (isinstance(tb, TracebackType) and
                (next is None or isinstance(next, TracebackType))):
            raise TypeError('tb_set_next arguments must be traceback objects')
        obj = _Traceback.from_address(id(tb))
        if tb.tb_next is not None:
            old = _Traceback.from_address(id(tb.tb_next))
            old.ob_refcnt -= 1
        if next is None:
            obj.tb_next = ctypes.POINTER(_Traceback)()
        else:
            next = _Traceback.from_address(id(next))
            next.ob_refcnt += 1
            obj.tb_next = ctypes.pointer(next)

    return tb_set_next


# try to get a tb_set_next implementation if we don't have transparent
# proxies.
tb_set_next = None
if tproxy is None:
    try:
        from jinja2._debugsupport import tb_set_next
    except ImportError:
        try:
            tb_set_next = _init_ugly_crap()
        except:
            pass
    del _init_ugly_crap

########NEW FILE########
__FILENAME__ = defaults
# -*- coding: utf-8 -*-
"""
    jinja2.defaults
    ~~~~~~~~~~~~~~~

    Jinja default filters and tags.

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD, see LICENSE for more details.
"""
from jinja2.utils import generate_lorem_ipsum, Cycler, Joiner


# defaults for the parser / lexer
BLOCK_START_STRING = '{%'
BLOCK_END_STRING = '%}'
VARIABLE_START_STRING = '{{'
VARIABLE_END_STRING = '}}'
COMMENT_START_STRING = '{#'
COMMENT_END_STRING = '#}'
LINE_STATEMENT_PREFIX = None
LINE_COMMENT_PREFIX = None
TRIM_BLOCKS = False
NEWLINE_SEQUENCE = '\n'


# default filters, tests and namespace
from jinja2.filters import FILTERS as DEFAULT_FILTERS
from jinja2.tests import TESTS as DEFAULT_TESTS
DEFAULT_NAMESPACE = {
    'range':        xrange,
    'dict':         lambda **kw: kw,
    'lipsum':       generate_lorem_ipsum,
    'cycler':       Cycler,
    'joiner':       Joiner
}


# export all constants
__all__ = tuple(x for x in locals().keys() if x.isupper())

########NEW FILE########
__FILENAME__ = environment
# -*- coding: utf-8 -*-
"""
    jinja2.environment
    ~~~~~~~~~~~~~~~~~~

    Provides a class that holds runtime and parsing time options.

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD, see LICENSE for more details.
"""
import os
import sys
from jinja2 import nodes
from jinja2.defaults import *
from jinja2.lexer import get_lexer, TokenStream
from jinja2.parser import Parser
from jinja2.optimizer import optimize
from jinja2.compiler import generate
from jinja2.runtime import Undefined, new_context
from jinja2.exceptions import TemplateSyntaxError, TemplateNotFound, \
     TemplatesNotFound
from jinja2.utils import import_string, LRUCache, Markup, missing, \
     concat, consume, internalcode, _encode_filename


# for direct template usage we have up to ten living environments
_spontaneous_environments = LRUCache(10)

# the function to create jinja traceback objects.  This is dynamically
# imported on the first exception in the exception handler.
_make_traceback = None


def get_spontaneous_environment(*args):
    """Return a new spontaneous environment.  A spontaneous environment is an
    unnamed and unaccessible (in theory) environment that is used for
    templates generated from a string and not from the file system.
    """
    try:
        env = _spontaneous_environments.get(args)
    except TypeError:
        return Environment(*args)
    if env is not None:
        return env
    _spontaneous_environments[args] = env = Environment(*args)
    env.shared = True
    return env


def create_cache(size):
    """Return the cache class for the given size."""
    if size == 0:
        return None
    if size < 0:
        return {}
    return LRUCache(size)


def copy_cache(cache):
    """Create an empty copy of the given cache."""
    if cache is None:
        return None
    elif type(cache) is dict:
        return {}
    return LRUCache(cache.capacity)


def load_extensions(environment, extensions):
    """Load the extensions from the list and bind it to the environment.
    Returns a dict of instanciated environments.
    """
    result = {}
    for extension in extensions:
        if isinstance(extension, basestring):
            extension = import_string(extension)
        result[extension.identifier] = extension(environment)
    return result


def _environment_sanity_check(environment):
    """Perform a sanity check on the environment."""
    assert issubclass(environment.undefined, Undefined), 'undefined must ' \
           'be a subclass of undefined because filters depend on it.'
    assert environment.block_start_string != \
           environment.variable_start_string != \
           environment.comment_start_string, 'block, variable and comment ' \
           'start strings must be different'
    assert environment.newline_sequence in ('\r', '\r\n', '\n'), \
           'newline_sequence set to unknown line ending string.'
    return environment


class Environment(object):
    r"""The core component of Jinja is the `Environment`.  It contains
    important shared variables like configuration, filters, tests,
    globals and others.  Instances of this class may be modified if
    they are not shared and if no template was loaded so far.
    Modifications on environments after the first template was loaded
    will lead to surprising effects and undefined behavior.

    Here the possible initialization parameters:

        `block_start_string`
            The string marking the begin of a block.  Defaults to ``'{%'``.

        `block_end_string`
            The string marking the end of a block.  Defaults to ``'%}'``.

        `variable_start_string`
            The string marking the begin of a print statement.
            Defaults to ``'{{'``.

        `variable_end_string`
            The string marking the end of a print statement.  Defaults to
            ``'}}'``.

        `comment_start_string`
            The string marking the begin of a comment.  Defaults to ``'{#'``.

        `comment_end_string`
            The string marking the end of a comment.  Defaults to ``'#}'``.

        `line_statement_prefix`
            If given and a string, this will be used as prefix for line based
            statements.  See also :ref:`line-statements`.

        `line_comment_prefix`
            If given and a string, this will be used as prefix for line based
            based comments.  See also :ref:`line-statements`.

            .. versionadded:: 2.2

        `trim_blocks`
            If this is set to ``True`` the first newline after a block is
            removed (block, not variable tag!).  Defaults to `False`.

        `newline_sequence`
            The sequence that starts a newline.  Must be one of ``'\r'``,
            ``'\n'`` or ``'\r\n'``.  The default is ``'\n'`` which is a
            useful default for Linux and OS X systems as well as web
            applications.

        `extensions`
            List of Jinja extensions to use.  This can either be import paths
            as strings or extension classes.  For more information have a
            look at :ref:`the extensions documentation <jinja-extensions>`.

        `optimized`
            should the optimizer be enabled?  Default is `True`.

        `undefined`
            :class:`Undefined` or a subclass of it that is used to represent
            undefined values in the template.

        `finalize`
            A callable that can be used to process the result of a variable
            expression before it is output.  For example one can convert
            `None` implicitly into an empty string here.

        `autoescape`
            If set to true the XML/HTML autoescaping feature is enabled by
            default.  For more details about auto escaping see
            :class:`~jinja2.utils.Markup`.  As of Jinja 2.4 this can also
            be a callable that is passed the template name and has to
            return `True` or `False` depending on autoescape should be
            enabled by default.

            .. versionchanged:: 2.4
               `autoescape` can now be a function

        `loader`
            The template loader for this environment.

        `cache_size`
            The size of the cache.  Per default this is ``50`` which means
            that if more than 50 templates are loaded the loader will clean
            out the least recently used template.  If the cache size is set to
            ``0`` templates are recompiled all the time, if the cache size is
            ``-1`` the cache will not be cleaned.

        `auto_reload`
            Some loaders load templates from locations where the template
            sources may change (ie: file system or database).  If
            `auto_reload` is set to `True` (default) every time a template is
            requested the loader checks if the source changed and if yes, it
            will reload the template.  For higher performance it's possible to
            disable that.

        `bytecode_cache`
            If set to a bytecode cache object, this object will provide a
            cache for the internal Jinja bytecode so that templates don't
            have to be parsed if they were not changed.

            See :ref:`bytecode-cache` for more information.
    """

    #: if this environment is sandboxed.  Modifying this variable won't make
    #: the environment sandboxed though.  For a real sandboxed environment
    #: have a look at jinja2.sandbox.  This flag alone controls the code
    #: generation by the compiler.
    sandboxed = False

    #: True if the environment is just an overlay
    overlayed = False

    #: the environment this environment is linked to if it is an overlay
    linked_to = None

    #: shared environments have this set to `True`.  A shared environment
    #: must not be modified
    shared = False

    #: these are currently EXPERIMENTAL undocumented features.
    exception_handler = None
    exception_formatter = None

    def __init__(self,
                 block_start_string=BLOCK_START_STRING,
                 block_end_string=BLOCK_END_STRING,
                 variable_start_string=VARIABLE_START_STRING,
                 variable_end_string=VARIABLE_END_STRING,
                 comment_start_string=COMMENT_START_STRING,
                 comment_end_string=COMMENT_END_STRING,
                 line_statement_prefix=LINE_STATEMENT_PREFIX,
                 line_comment_prefix=LINE_COMMENT_PREFIX,
                 trim_blocks=TRIM_BLOCKS,
                 newline_sequence=NEWLINE_SEQUENCE,
                 extensions=(),
                 optimized=True,
                 undefined=Undefined,
                 finalize=None,
                 autoescape=False,
                 loader=None,
                 cache_size=50,
                 auto_reload=True,
                 bytecode_cache=None):
        # !!Important notice!!
        #   The constructor accepts quite a few arguments that should be
        #   passed by keyword rather than position.  However it's important to
        #   not change the order of arguments because it's used at least
        #   internally in those cases:
        #       -   spontaneus environments (i18n extension and Template)
        #       -   unittests
        #   If parameter changes are required only add parameters at the end
        #   and don't change the arguments (or the defaults!) of the arguments
        #   existing already.

        # lexer / parser information
        self.block_start_string = block_start_string
        self.block_end_string = block_end_string
        self.variable_start_string = variable_start_string
        self.variable_end_string = variable_end_string
        self.comment_start_string = comment_start_string
        self.comment_end_string = comment_end_string
        self.line_statement_prefix = line_statement_prefix
        self.line_comment_prefix = line_comment_prefix
        self.trim_blocks = trim_blocks
        self.newline_sequence = newline_sequence

        # runtime information
        self.undefined = undefined
        self.optimized = optimized
        self.finalize = finalize
        self.autoescape = autoescape

        # defaults
        self.filters = DEFAULT_FILTERS.copy()
        self.tests = DEFAULT_TESTS.copy()
        self.globals = DEFAULT_NAMESPACE.copy()

        # set the loader provided
        self.loader = loader
        self.bytecode_cache = None
        self.cache = create_cache(cache_size)
        self.bytecode_cache = bytecode_cache
        self.auto_reload = auto_reload

        # load extensions
        self.extensions = load_extensions(self, extensions)

        _environment_sanity_check(self)

    def add_extension(self, extension):
        """Adds an extension after the environment was created.

        .. versionadded:: 2.5
        """
        self.extensions.update(load_extensions(self, [extension]))

    def extend(self, **attributes):
        """Add the items to the instance of the environment if they do not exist
        yet.  This is used by :ref:`extensions <writing-extensions>` to register
        callbacks and configuration values without breaking inheritance.
        """
        for key, value in attributes.iteritems():
            if not hasattr(self, key):
                setattr(self, key, value)

    def overlay(self, block_start_string=missing, block_end_string=missing,
                variable_start_string=missing, variable_end_string=missing,
                comment_start_string=missing, comment_end_string=missing,
                line_statement_prefix=missing, line_comment_prefix=missing,
                trim_blocks=missing, extensions=missing, optimized=missing,
                undefined=missing, finalize=missing, autoescape=missing,
                loader=missing, cache_size=missing, auto_reload=missing,
                bytecode_cache=missing):
        """Create a new overlay environment that shares all the data with the
        current environment except of cache and the overridden attributes.
        Extensions cannot be removed for an overlayed environment.  An overlayed
        environment automatically gets all the extensions of the environment it
        is linked to plus optional extra extensions.

        Creating overlays should happen after the initial environment was set
        up completely.  Not all attributes are truly linked, some are just
        copied over so modifications on the original environment may not shine
        through.
        """
        args = dict(locals())
        del args['self'], args['cache_size'], args['extensions']

        rv = object.__new__(self.__class__)
        rv.__dict__.update(self.__dict__)
        rv.overlayed = True
        rv.linked_to = self

        for key, value in args.iteritems():
            if value is not missing:
                setattr(rv, key, value)

        if cache_size is not missing:
            rv.cache = create_cache(cache_size)
        else:
            rv.cache = copy_cache(self.cache)

        rv.extensions = {}
        for key, value in self.extensions.iteritems():
            rv.extensions[key] = value.bind(rv)
        if extensions is not missing:
            rv.extensions.update(load_extensions(rv, extensions))

        return _environment_sanity_check(rv)

    lexer = property(get_lexer, doc="The lexer for this environment.")

    def iter_extensions(self):
        """Iterates over the extensions by priority."""
        return iter(sorted(self.extensions.values(),
                           key=lambda x: x.priority))

    def getitem(self, obj, argument):
        """Get an item or attribute of an object but prefer the item."""
        try:
            return obj[argument]
        except (TypeError, LookupError):
            if isinstance(argument, basestring):
                try:
                    attr = str(argument)
                except Exception:
                    pass
                else:
                    try:
                        return getattr(obj, attr)
                    except AttributeError:
                        pass
            return self.undefined(obj=obj, name=argument)

    def getattr(self, obj, attribute):
        """Get an item or attribute of an object but prefer the attribute.
        Unlike :meth:`getitem` the attribute *must* be a bytestring.
        """
        try:
            return getattr(obj, attribute)
        except AttributeError:
            pass
        try:
            return obj[attribute]
        except (TypeError, LookupError, AttributeError):
            return self.undefined(obj=obj, name=attribute)

    @internalcode
    def parse(self, source, name=None, filename=None):
        """Parse the sourcecode and return the abstract syntax tree.  This
        tree of nodes is used by the compiler to convert the template into
        executable source- or bytecode.  This is useful for debugging or to
        extract information from templates.

        If you are :ref:`developing Jinja2 extensions <writing-extensions>`
        this gives you a good overview of the node tree generated.
        """
        try:
            return self._parse(source, name, filename)
        except TemplateSyntaxError:
            exc_info = sys.exc_info()
        self.handle_exception(exc_info, source_hint=source)

    def _parse(self, source, name, filename):
        """Internal parsing function used by `parse` and `compile`."""
        return Parser(self, source, name, _encode_filename(filename)).parse()

    def lex(self, source, name=None, filename=None):
        """Lex the given sourcecode and return a generator that yields
        tokens as tuples in the form ``(lineno, token_type, value)``.
        This can be useful for :ref:`extension development <writing-extensions>`
        and debugging templates.

        This does not perform preprocessing.  If you want the preprocessing
        of the extensions to be applied you have to filter source through
        the :meth:`preprocess` method.
        """
        source = unicode(source)
        try:
            return self.lexer.tokeniter(source, name, filename)
        except TemplateSyntaxError:
            exc_info = sys.exc_info()
        self.handle_exception(exc_info, source_hint=source)

    def preprocess(self, source, name=None, filename=None):
        """Preprocesses the source with all extensions.  This is automatically
        called for all parsing and compiling methods but *not* for :meth:`lex`
        because there you usually only want the actual source tokenized.
        """
        return reduce(lambda s, e: e.preprocess(s, name, filename),
                      self.iter_extensions(), unicode(source))

    def _tokenize(self, source, name, filename=None, state=None):
        """Called by the parser to do the preprocessing and filtering
        for all the extensions.  Returns a :class:`~jinja2.lexer.TokenStream`.
        """
        source = self.preprocess(source, name, filename)
        stream = self.lexer.tokenize(source, name, filename, state)
        for ext in self.iter_extensions():
            stream = ext.filter_stream(stream)
            if not isinstance(stream, TokenStream):
                stream = TokenStream(stream, name, filename)
        return stream

    def _generate(self, source, name, filename, defer_init=False):
        """Internal hook that can be overriden to hook a different generate
        method in.

        .. versionadded:: 2.5
        """
        return generate(source, self, name, filename, defer_init=defer_init)

    def _compile(self, source, filename):
        """Internal hook that can be overriden to hook a different compile
        method in.

        .. versionadded:: 2.5
        """
        return compile(source, filename, 'exec')

    @internalcode
    def compile(self, source, name=None, filename=None, raw=False,
                defer_init=False):
        """Compile a node or template source code.  The `name` parameter is
        the load name of the template after it was joined using
        :meth:`join_path` if necessary, not the filename on the file system.
        the `filename` parameter is the estimated filename of the template on
        the file system.  If the template came from a database or memory this
        can be omitted.

        The return value of this method is a python code object.  If the `raw`
        parameter is `True` the return value will be a string with python
        code equivalent to the bytecode returned otherwise.  This method is
        mainly used internally.

        `defer_init` is use internally to aid the module code generator.  This
        causes the generated code to be able to import without the global
        environment variable to be set.

        .. versionadded:: 2.4
           `defer_init` parameter added.
        """
        source_hint = None
        try:
            if isinstance(source, basestring):
                source_hint = source
                source = self._parse(source, name, filename)
            if self.optimized:
                source = optimize(source, self)
            source = self._generate(source, name, filename,
                                    defer_init=defer_init)
            if raw:
                return source
            if filename is None:
                filename = '<template>'
            else:
                filename = _encode_filename(filename)
            return self._compile(source, filename)
        except TemplateSyntaxError:
            exc_info = sys.exc_info()
        self.handle_exception(exc_info, source_hint=source)

    def compile_expression(self, source, undefined_to_none=True):
        """A handy helper method that returns a callable that accepts keyword
        arguments that appear as variables in the expression.  If called it
        returns the result of the expression.

        This is useful if applications want to use the same rules as Jinja
        in template "configuration files" or similar situations.

        Example usage:

        >>> env = Environment()
        >>> expr = env.compile_expression('foo == 42')
        >>> expr(foo=23)
        False
        >>> expr(foo=42)
        True

        Per default the return value is converted to `None` if the
        expression returns an undefined value.  This can be changed
        by setting `undefined_to_none` to `False`.

        >>> env.compile_expression('var')() is None
        True
        >>> env.compile_expression('var', undefined_to_none=False)()
        Undefined

        .. versionadded:: 2.1
        """
        parser = Parser(self, source, state='variable')
        exc_info = None
        try:
            expr = parser.parse_expression()
            if not parser.stream.eos:
                raise TemplateSyntaxError('chunk after expression',
                                          parser.stream.current.lineno,
                                          None, None)
            expr.set_environment(self)
        except TemplateSyntaxError:
            exc_info = sys.exc_info()
        if exc_info is not None:
            self.handle_exception(exc_info, source_hint=source)
        body = [nodes.Assign(nodes.Name('result', 'store'), expr, lineno=1)]
        template = self.from_string(nodes.Template(body, lineno=1))
        return TemplateExpression(template, undefined_to_none)

    def compile_templates(self, target, extensions=None, filter_func=None,
                          zip='deflated', log_function=None,
                          ignore_errors=True, py_compile=False):
        """Finds all the templates the loader can find, compiles them
        and stores them in `target`.  If `zip` is `None`, instead of in a
        zipfile, the templates will be will be stored in a directory.
        By default a deflate zip algorithm is used, to switch to
        the stored algorithm, `zip` can be set to ``'stored'``.

        `extensions` and `filter_func` are passed to :meth:`list_templates`.
        Each template returned will be compiled to the target folder or
        zipfile.

        By default template compilation errors are ignored.  In case a
        log function is provided, errors are logged.  If you want template
        syntax errors to abort the compilation you can set `ignore_errors`
        to `False` and you will get an exception on syntax errors.

        If `py_compile` is set to `True` .pyc files will be written to the
        target instead of standard .py files.

        .. versionadded:: 2.4
        """
        from jinja2.loaders import ModuleLoader

        if log_function is None:
            log_function = lambda x: None

        if py_compile:
            import imp, marshal
            py_header = imp.get_magic() + \
                u'\xff\xff\xff\xff'.encode('iso-8859-15')

        def write_file(filename, data, mode):
            if zip:
                info = ZipInfo(filename)
                info.external_attr = 0755 << 16L
                zip_file.writestr(info, data)
            else:
                f = open(os.path.join(target, filename), mode)
                try:
                    f.write(data)
                finally:
                    f.close()

        if zip is not None:
            from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED, ZIP_STORED
            zip_file = ZipFile(target, 'w', dict(deflated=ZIP_DEFLATED,
                                                 stored=ZIP_STORED)[zip])
            log_function('Compiling into Zip archive "%s"' % target)
        else:
            if not os.path.isdir(target):
                os.makedirs(target)
            log_function('Compiling into folder "%s"' % target)

        try:
            for name in self.list_templates(extensions, filter_func):
                source, filename, _ = self.loader.get_source(self, name)
                try:
                    code = self.compile(source, name, filename, True, True)
                except TemplateSyntaxError, e:
                    if not ignore_errors:
                        raise
                    log_function('Could not compile "%s": %s' % (name, e))
                    continue

                filename = ModuleLoader.get_module_filename(name)

                if py_compile:
                    c = self._compile(code, _encode_filename(filename))
                    write_file(filename + 'c', py_header +
                               marshal.dumps(c), 'wb')
                    log_function('Byte-compiled "%s" as %s' %
                                 (name, filename + 'c'))
                else:
                    write_file(filename, code, 'w')
                    log_function('Compiled "%s" as %s' % (name, filename))
        finally:
            if zip:
                zip_file.close()

        log_function('Finished compiling templates')

    def list_templates(self, extensions=None, filter_func=None):
        """Returns a list of templates for this environment.  This requires
        that the loader supports the loader's
        :meth:`~BaseLoader.list_templates` method.

        If there are other files in the template folder besides the
        actual templates, the returned list can be filtered.  There are two
        ways: either `extensions` is set to a list of file extensions for
        templates, or a `filter_func` can be provided which is a callable that
        is passed a template name and should return `True` if it should end up
        in the result list.

        If the loader does not support that, a :exc:`TypeError` is raised.

        .. versionadded:: 2.4
        """
        x = self.loader.list_templates()
        if extensions is not None:
            if filter_func is not None:
                raise TypeError('either extensions or filter_func '
                                'can be passed, but not both')
            filter_func = lambda x: '.' in x and \
                                    x.rsplit('.', 1)[1] in extensions
        if filter_func is not None:
            x = filter(filter_func, x)
        return x

    def handle_exception(self, exc_info=None, rendered=False, source_hint=None):
        """Exception handling helper.  This is used internally to either raise
        rewritten exceptions or return a rendered traceback for the template.
        """
        global _make_traceback
        if exc_info is None:
            exc_info = sys.exc_info()

        # the debugging module is imported when it's used for the first time.
        # we're doing a lot of stuff there and for applications that do not
        # get any exceptions in template rendering there is no need to load
        # all of that.
        if _make_traceback is None:
            from jinja2.debug import make_traceback as _make_traceback
        traceback = _make_traceback(exc_info, source_hint)
        if rendered and self.exception_formatter is not None:
            return self.exception_formatter(traceback)
        if self.exception_handler is not None:
            self.exception_handler(traceback)
        exc_type, exc_value, tb = traceback.standard_exc_info
        raise exc_type, exc_value, tb

    def join_path(self, template, parent):
        """Join a template with the parent.  By default all the lookups are
        relative to the loader root so this method returns the `template`
        parameter unchanged, but if the paths should be relative to the
        parent template, this function can be used to calculate the real
        template name.

        Subclasses may override this method and implement template path
        joining here.
        """
        return template

    @internalcode
    def _load_template(self, name, globals):
        if self.loader is None:
            raise TypeError('no loader for this environment specified')
        if self.cache is not None:
            template = self.cache.get(name)
            if template is not None and (not self.auto_reload or \
                                         template.is_up_to_date):
                return template
        template = self.loader.load(self, name, globals)
        if self.cache is not None:
            self.cache[name] = template
        return template

    @internalcode
    def get_template(self, name, parent=None, globals=None):
        """Load a template from the loader.  If a loader is configured this
        method ask the loader for the template and returns a :class:`Template`.
        If the `parent` parameter is not `None`, :meth:`join_path` is called
        to get the real template name before loading.

        The `globals` parameter can be used to provide template wide globals.
        These variables are available in the context at render time.

        If the template does not exist a :exc:`TemplateNotFound` exception is
        raised.

        .. versionchanged:: 2.4
           If `name` is a :class:`Template` object it is returned from the
           function unchanged.
        """
        if isinstance(name, Template):
            return name
        if parent is not None:
            name = self.join_path(name, parent)
        return self._load_template(name, self.make_globals(globals))

    @internalcode
    def select_template(self, names, parent=None, globals=None):
        """Works like :meth:`get_template` but tries a number of templates
        before it fails.  If it cannot find any of the templates, it will
        raise a :exc:`TemplatesNotFound` exception.

        .. versionadded:: 2.3

        .. versionchanged:: 2.4
           If `names` contains a :class:`Template` object it is returned
           from the function unchanged.
        """
        if not names:
            raise TemplatesNotFound(message=u'Tried to select from an empty list '
                                            u'of templates.')
        globals = self.make_globals(globals)
        for name in names:
            if isinstance(name, Template):
                return name
            if parent is not None:
                name = self.join_path(name, parent)
            try:
                return self._load_template(name, globals)
            except TemplateNotFound:
                pass
        raise TemplatesNotFound(names)

    @internalcode
    def get_or_select_template(self, template_name_or_list,
                               parent=None, globals=None):
        """Does a typecheck and dispatches to :meth:`select_template`
        if an iterable of template names is given, otherwise to
        :meth:`get_template`.

        .. versionadded:: 2.3
        """
        if isinstance(template_name_or_list, basestring):
            return self.get_template(template_name_or_list, parent, globals)
        elif isinstance(template_name_or_list, Template):
            return template_name_or_list
        return self.select_template(template_name_or_list, parent, globals)

    def from_string(self, source, globals=None, template_class=None):
        """Load a template from a string.  This parses the source given and
        returns a :class:`Template` object.
        """
        globals = self.make_globals(globals)
        cls = template_class or self.template_class
        return cls.from_code(self, self.compile(source), globals, None)

    def make_globals(self, d):
        """Return a dict for the globals."""
        if not d:
            return self.globals
        return dict(self.globals, **d)


class Template(object):
    """The central template object.  This class represents a compiled template
    and is used to evaluate it.

    Normally the template object is generated from an :class:`Environment` but
    it also has a constructor that makes it possible to create a template
    instance directly using the constructor.  It takes the same arguments as
    the environment constructor but it's not possible to specify a loader.

    Every template object has a few methods and members that are guaranteed
    to exist.  However it's important that a template object should be
    considered immutable.  Modifications on the object are not supported.

    Template objects created from the constructor rather than an environment
    do have an `environment` attribute that points to a temporary environment
    that is probably shared with other templates created with the constructor
    and compatible settings.

    >>> template = Template('Hello {{ name }}!')
    >>> template.render(name='John Doe')
    u'Hello John Doe!'

    >>> stream = template.stream(name='John Doe')
    >>> stream.next()
    u'Hello John Doe!'
    >>> stream.next()
    Traceback (most recent call last):
        ...
    StopIteration
    """

    def __new__(cls, source,
                block_start_string=BLOCK_START_STRING,
                block_end_string=BLOCK_END_STRING,
                variable_start_string=VARIABLE_START_STRING,
                variable_end_string=VARIABLE_END_STRING,
                comment_start_string=COMMENT_START_STRING,
                comment_end_string=COMMENT_END_STRING,
                line_statement_prefix=LINE_STATEMENT_PREFIX,
                line_comment_prefix=LINE_COMMENT_PREFIX,
                trim_blocks=TRIM_BLOCKS,
                newline_sequence=NEWLINE_SEQUENCE,
                extensions=(),
                optimized=True,
                undefined=Undefined,
                finalize=None,
                autoescape=False):
        env = get_spontaneous_environment(
            block_start_string, block_end_string, variable_start_string,
            variable_end_string, comment_start_string, comment_end_string,
            line_statement_prefix, line_comment_prefix, trim_blocks,
            newline_sequence, frozenset(extensions), optimized, undefined,
            finalize, autoescape, None, 0, False, None)
        return env.from_string(source, template_class=cls)

    @classmethod
    def from_code(cls, environment, code, globals, uptodate=None):
        """Creates a template object from compiled code and the globals.  This
        is used by the loaders and environment to create a template object.
        """
        namespace = {
            'environment':  environment,
            '__file__':     code.co_filename
        }
        exec code in namespace
        rv = cls._from_namespace(environment, namespace, globals)
        rv._uptodate = uptodate
        return rv

    @classmethod
    def from_module_dict(cls, environment, module_dict, globals):
        """Creates a template object from a module.  This is used by the
        module loader to create a template object.

        .. versionadded:: 2.4
        """
        return cls._from_namespace(environment, module_dict, globals)

    @classmethod
    def _from_namespace(cls, environment, namespace, globals):
        t = object.__new__(cls)
        t.environment = environment
        t.globals = globals
        t.name = namespace['name']
        t.filename = namespace['__file__']
        t.blocks = namespace['blocks']

        # render function and module
        t.root_render_func = namespace['root']
        t._module = None

        # debug and loader helpers
        t._debug_info = namespace['debug_info']
        t._uptodate = None

        # store the reference
        namespace['environment'] = environment
        namespace['__jinja_template__'] = t

        return t

    def render(self, *args, **kwargs):
        """This method accepts the same arguments as the `dict` constructor:
        A dict, a dict subclass or some keyword arguments.  If no arguments
        are given the context will be empty.  These two calls do the same::

            template.render(knights='that say nih')
            template.render({'knights': 'that say nih'})

        This will return the rendered template as unicode string.
        """
        vars = dict(*args, **kwargs)
        try:
            return concat(self.root_render_func(self.new_context(vars)))
        except Exception:
            exc_info = sys.exc_info()
        return self.environment.handle_exception(exc_info, True)

    def stream(self, *args, **kwargs):
        """Works exactly like :meth:`generate` but returns a
        :class:`TemplateStream`.
        """
        return TemplateStream(self.generate(*args, **kwargs))

    def generate(self, *args, **kwargs):
        """For very large templates it can be useful to not render the whole
        template at once but evaluate each statement after another and yield
        piece for piece.  This method basically does exactly that and returns
        a generator that yields one item after another as unicode strings.

        It accepts the same arguments as :meth:`render`.
        """
        vars = dict(*args, **kwargs)
        try:
            for event in self.root_render_func(self.new_context(vars)):
                yield event
        except Exception:
            exc_info = sys.exc_info()
        else:
            return
        yield self.environment.handle_exception(exc_info, True)

    def new_context(self, vars=None, shared=False, locals=None):
        """Create a new :class:`Context` for this template.  The vars
        provided will be passed to the template.  Per default the globals
        are added to the context.  If shared is set to `True` the data
        is passed as it to the context without adding the globals.

        `locals` can be a dict of local variables for internal usage.
        """
        return new_context(self.environment, self.name, self.blocks,
                           vars, shared, self.globals, locals)

    def make_module(self, vars=None, shared=False, locals=None):
        """This method works like the :attr:`module` attribute when called
        without arguments but it will evaluate the template on every call
        rather than caching it.  It's also possible to provide
        a dict which is then used as context.  The arguments are the same
        as for the :meth:`new_context` method.
        """
        return TemplateModule(self, self.new_context(vars, shared, locals))

    @property
    def module(self):
        """The template as module.  This is used for imports in the
        template runtime but is also useful if one wants to access
        exported template variables from the Python layer:

        >>> t = Template('{% macro foo() %}42{% endmacro %}23')
        >>> unicode(t.module)
        u'23'
        >>> t.module.foo()
        u'42'
        """
        if self._module is not None:
            return self._module
        self._module = rv = self.make_module()
        return rv

    def get_corresponding_lineno(self, lineno):
        """Return the source line number of a line number in the
        generated bytecode as they are not in sync.
        """
        for template_line, code_line in reversed(self.debug_info):
            if code_line <= lineno:
                return template_line
        return 1

    @property
    def is_up_to_date(self):
        """If this variable is `False` there is a newer version available."""
        if self._uptodate is None:
            return True
        return self._uptodate()

    @property
    def debug_info(self):
        """The debug info mapping."""
        return [tuple(map(int, x.split('='))) for x in
                self._debug_info.split('&')]

    def __repr__(self):
        if self.name is None:
            name = 'memory:%x' % id(self)
        else:
            name = repr(self.name)
        return '<%s %s>' % (self.__class__.__name__, name)


class TemplateModule(object):
    """Represents an imported template.  All the exported names of the
    template are available as attributes on this object.  Additionally
    converting it into an unicode- or bytestrings renders the contents.
    """

    def __init__(self, template, context):
        self._body_stream = list(template.root_render_func(context))
        self.__dict__.update(context.get_exported())
        self.__name__ = template.name

    def __html__(self):
        return Markup(concat(self._body_stream))

    def __str__(self):
        return unicode(self).encode('utf-8')

    # unicode goes after __str__ because we configured 2to3 to rename
    # __unicode__ to __str__.  because the 2to3 tree is not designed to
    # remove nodes from it, we leave the above __str__ around and let
    # it override at runtime.
    def __unicode__(self):
        return concat(self._body_stream)

    def __repr__(self):
        if self.__name__ is None:
            name = 'memory:%x' % id(self)
        else:
            name = repr(self.__name__)
        return '<%s %s>' % (self.__class__.__name__, name)


class TemplateExpression(object):
    """The :meth:`jinja2.Environment.compile_expression` method returns an
    instance of this object.  It encapsulates the expression-like access
    to the template with an expression it wraps.
    """

    def __init__(self, template, undefined_to_none):
        self._template = template
        self._undefined_to_none = undefined_to_none

    def __call__(self, *args, **kwargs):
        context = self._template.new_context(dict(*args, **kwargs))
        consume(self._template.root_render_func(context))
        rv = context.vars['result']
        if self._undefined_to_none and isinstance(rv, Undefined):
            rv = None
        return rv


class TemplateStream(object):
    """A template stream works pretty much like an ordinary python generator
    but it can buffer multiple items to reduce the number of total iterations.
    Per default the output is unbuffered which means that for every unbuffered
    instruction in the template one unicode string is yielded.

    If buffering is enabled with a buffer size of 5, five items are combined
    into a new unicode string.  This is mainly useful if you are streaming
    big templates to a client via WSGI which flushes after each iteration.
    """

    def __init__(self, gen):
        self._gen = gen
        self.disable_buffering()

    def dump(self, fp, encoding=None, errors='strict'):
        """Dump the complete stream into a file or file-like object.
        Per default unicode strings are written, if you want to encode
        before writing specifiy an `encoding`.

        Example usage::

            Template('Hello {{ name }}!').stream(name='foo').dump('hello.html')
        """
        close = False
        if isinstance(fp, basestring):
            fp = file(fp, 'w')
            close = True
        try:
            if encoding is not None:
                iterable = (x.encode(encoding, errors) for x in self)
            else:
                iterable = self
            if hasattr(fp, 'writelines'):
                fp.writelines(iterable)
            else:
                for item in iterable:
                    fp.write(item)
        finally:
            if close:
                fp.close()

    def disable_buffering(self):
        """Disable the output buffering."""
        self._next = self._gen.next
        self.buffered = False

    def enable_buffering(self, size=5):
        """Enable buffering.  Buffer `size` items before yielding them."""
        if size <= 1:
            raise ValueError('buffer size too small')

        def generator(next):
            buf = []
            c_size = 0
            push = buf.append

            while 1:
                try:
                    while c_size < size:
                        c = next()
                        push(c)
                        if c:
                            c_size += 1
                except StopIteration:
                    if not c_size:
                        return
                yield concat(buf)
                del buf[:]
                c_size = 0

        self.buffered = True
        self._next = generator(self._gen.next).next

    def __iter__(self):
        return self

    def next(self):
        return self._next()


# hook in default template class.  if anyone reads this comment: ignore that
# it's possible to use custom templates ;-)
Environment.template_class = Template

########NEW FILE########
__FILENAME__ = exceptions
# -*- coding: utf-8 -*-
"""
    jinja2.exceptions
    ~~~~~~~~~~~~~~~~~

    Jinja exceptions.

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD, see LICENSE for more details.
"""


class TemplateError(Exception):
    """Baseclass for all template errors."""

    def __init__(self, message=None):
        if message is not None:
            message = unicode(message).encode('utf-8')
        Exception.__init__(self, message)

    @property
    def message(self):
        if self.args:
            message = self.args[0]
            if message is not None:
                return message.decode('utf-8', 'replace')


class TemplateNotFound(IOError, LookupError, TemplateError):
    """Raised if a template does not exist."""

    # looks weird, but removes the warning descriptor that just
    # bogusly warns us about message being deprecated
    message = None

    def __init__(self, name, message=None):
        IOError.__init__(self)
        if message is None:
            message = name
        self.message = message
        self.name = name
        self.templates = [name]

    def __str__(self):
        return self.message.encode('utf-8')

    # unicode goes after __str__ because we configured 2to3 to rename
    # __unicode__ to __str__.  because the 2to3 tree is not designed to
    # remove nodes from it, we leave the above __str__ around and let
    # it override at runtime.
    def __unicode__(self):
        return self.message


class TemplatesNotFound(TemplateNotFound):
    """Like :class:`TemplateNotFound` but raised if multiple templates
    are selected.  This is a subclass of :class:`TemplateNotFound`
    exception, so just catching the base exception will catch both.

    .. versionadded:: 2.2
    """

    def __init__(self, names=(), message=None):
        if message is None:
            message = u'non of the templates given were found: ' + \
                      u', '.join(map(unicode, names))
        TemplateNotFound.__init__(self, names and names[-1] or None, message)
        self.templates = list(names)


class TemplateSyntaxError(TemplateError):
    """Raised to tell the user that there is a problem with the template."""

    def __init__(self, message, lineno, name=None, filename=None):
        TemplateError.__init__(self, message)
        self.lineno = lineno
        self.name = name
        self.filename = filename
        self.source = None

        # this is set to True if the debug.translate_syntax_error
        # function translated the syntax error into a new traceback
        self.translated = False

    def __str__(self):
        return unicode(self).encode('utf-8')

    # unicode goes after __str__ because we configured 2to3 to rename
    # __unicode__ to __str__.  because the 2to3 tree is not designed to
    # remove nodes from it, we leave the above __str__ around and let
    # it override at runtime.
    def __unicode__(self):
        # for translated errors we only return the message
        if self.translated:
            return self.message

        # otherwise attach some stuff
        location = 'line %d' % self.lineno
        name = self.filename or self.name
        if name:
            location = 'File "%s", %s' % (name, location)
        lines = [self.message, '  ' + location]

        # if the source is set, add the line to the output
        if self.source is not None:
            try:
                line = self.source.splitlines()[self.lineno - 1]
            except IndexError:
                line = None
            if line:
                lines.append('    ' + line.strip())

        return u'\n'.join(lines)


class TemplateAssertionError(TemplateSyntaxError):
    """Like a template syntax error, but covers cases where something in the
    template caused an error at compile time that wasn't necessarily caused
    by a syntax error.  However it's a direct subclass of
    :exc:`TemplateSyntaxError` and has the same attributes.
    """


class TemplateRuntimeError(TemplateError):
    """A generic runtime error in the template engine.  Under some situations
    Jinja may raise this exception.
    """


class UndefinedError(TemplateRuntimeError):
    """Raised if a template tries to operate on :class:`Undefined`."""


class SecurityError(TemplateRuntimeError):
    """Raised if a template tries to do something insecure if the
    sandbox is enabled.
    """


class FilterArgumentError(TemplateRuntimeError):
    """This error is raised if a filter was called with inappropriate
    arguments
    """

########NEW FILE########
__FILENAME__ = ext
# -*- coding: utf-8 -*-
"""
    jinja2.ext
    ~~~~~~~~~~

    Jinja extensions allow to add custom tags similar to the way django custom
    tags work.  By default two example extensions exist: an i18n and a cache
    extension.

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD.
"""
from collections import deque
from jinja2 import nodes
from jinja2.defaults import *
from jinja2.environment import Environment
from jinja2.runtime import Undefined, concat
from jinja2.exceptions import TemplateAssertionError, TemplateSyntaxError
from jinja2.utils import contextfunction, import_string, Markup, next


# the only real useful gettext functions for a Jinja template.  Note
# that ugettext must be assigned to gettext as Jinja doesn't support
# non unicode strings.
GETTEXT_FUNCTIONS = ('_', 'gettext', 'ngettext')


class ExtensionRegistry(type):
    """Gives the extension an unique identifier."""

    def __new__(cls, name, bases, d):
        rv = type.__new__(cls, name, bases, d)
        rv.identifier = rv.__module__ + '.' + rv.__name__
        return rv


class Extension(object):
    """Extensions can be used to add extra functionality to the Jinja template
    system at the parser level.  Custom extensions are bound to an environment
    but may not store environment specific data on `self`.  The reason for
    this is that an extension can be bound to another environment (for
    overlays) by creating a copy and reassigning the `environment` attribute.

    As extensions are created by the environment they cannot accept any
    arguments for configuration.  One may want to work around that by using
    a factory function, but that is not possible as extensions are identified
    by their import name.  The correct way to configure the extension is
    storing the configuration values on the environment.  Because this way the
    environment ends up acting as central configuration storage the
    attributes may clash which is why extensions have to ensure that the names
    they choose for configuration are not too generic.  ``prefix`` for example
    is a terrible name, ``fragment_cache_prefix`` on the other hand is a good
    name as includes the name of the extension (fragment cache).
    """
    __metaclass__ = ExtensionRegistry

    #: if this extension parses this is the list of tags it's listening to.
    tags = set()

    #: the priority of that extension.  This is especially useful for
    #: extensions that preprocess values.  A lower value means higher
    #: priority.
    #:
    #: .. versionadded:: 2.4
    priority = 100

    def __init__(self, environment):
        self.environment = environment

    def bind(self, environment):
        """Create a copy of this extension bound to another environment."""
        rv = object.__new__(self.__class__)
        rv.__dict__.update(self.__dict__)
        rv.environment = environment
        return rv

    def preprocess(self, source, name, filename=None):
        """This method is called before the actual lexing and can be used to
        preprocess the source.  The `filename` is optional.  The return value
        must be the preprocessed source.
        """
        return source

    def filter_stream(self, stream):
        """It's passed a :class:`~jinja2.lexer.TokenStream` that can be used
        to filter tokens returned.  This method has to return an iterable of
        :class:`~jinja2.lexer.Token`\s, but it doesn't have to return a
        :class:`~jinja2.lexer.TokenStream`.

        In the `ext` folder of the Jinja2 source distribution there is a file
        called `inlinegettext.py` which implements a filter that utilizes this
        method.
        """
        return stream

    def parse(self, parser):
        """If any of the :attr:`tags` matched this method is called with the
        parser as first argument.  The token the parser stream is pointing at
        is the name token that matched.  This method has to return one or a
        list of multiple nodes.
        """
        raise NotImplementedError()

    def attr(self, name, lineno=None):
        """Return an attribute node for the current extension.  This is useful
        to pass constants on extensions to generated template code.

        ::

            self.attr('_my_attribute', lineno=lineno)
        """
        return nodes.ExtensionAttribute(self.identifier, name, lineno=lineno)

    def call_method(self, name, args=None, kwargs=None, dyn_args=None,
                    dyn_kwargs=None, lineno=None):
        """Call a method of the extension.  This is a shortcut for
        :meth:`attr` + :class:`jinja2.nodes.Call`.
        """
        if args is None:
            args = []
        if kwargs is None:
            kwargs = []
        return nodes.Call(self.attr(name, lineno=lineno), args, kwargs,
                          dyn_args, dyn_kwargs, lineno=lineno)


@contextfunction
def _gettext_alias(__context, *args, **kwargs):
    return __context.call(__context.resolve('gettext'), *args, **kwargs)


def _make_new_gettext(func):
    @contextfunction
    def gettext(__context, __string, **variables):
        rv = __context.call(func, __string)
        if __context.eval_ctx.autoescape:
            rv = Markup(rv)
        return rv % variables
    return gettext


def _make_new_ngettext(func):
    @contextfunction
    def ngettext(__context, __singular, __plural, __num, **variables):
        variables.setdefault('num', __num)
        rv = __context.call(func, __singular, __plural, __num)
        if __context.eval_ctx.autoescape:
            rv = Markup(rv)
        return rv % variables
    return ngettext


class InternationalizationExtension(Extension):
    """This extension adds gettext support to Jinja2."""
    tags = set(['trans'])

    # TODO: the i18n extension is currently reevaluating values in a few
    # situations.  Take this example:
    #   {% trans count=something() %}{{ count }} foo{% pluralize
    #     %}{{ count }} fooss{% endtrans %}
    # something is called twice here.  One time for the gettext value and
    # the other time for the n-parameter of the ngettext function.

    def __init__(self, environment):
        Extension.__init__(self, environment)
        environment.globals['_'] = _gettext_alias
        environment.extend(
            install_gettext_translations=self._install,
            install_null_translations=self._install_null,
            install_gettext_callables=self._install_callables,
            uninstall_gettext_translations=self._uninstall,
            extract_translations=self._extract,
            newstyle_gettext=False
        )

    def _install(self, translations, newstyle=None):
        gettext = getattr(translations, 'ugettext', None)
        if gettext is None:
            gettext = translations.gettext
        ngettext = getattr(translations, 'ungettext', None)
        if ngettext is None:
            ngettext = translations.ngettext
        self._install_callables(gettext, ngettext, newstyle)

    def _install_null(self, newstyle=None):
        self._install_callables(
            lambda x: x,
            lambda s, p, n: (n != 1 and (p,) or (s,))[0],
            newstyle
        )

    def _install_callables(self, gettext, ngettext, newstyle=None):
        if newstyle is not None:
            self.environment.newstyle_gettext = newstyle
        if self.environment.newstyle_gettext:
            gettext = _make_new_gettext(gettext)
            ngettext = _make_new_ngettext(ngettext)
        self.environment.globals.update(
            gettext=gettext,
            ngettext=ngettext
        )

    def _uninstall(self, translations):
        for key in 'gettext', 'ngettext':
            self.environment.globals.pop(key, None)

    def _extract(self, source, gettext_functions=GETTEXT_FUNCTIONS):
        if isinstance(source, basestring):
            source = self.environment.parse(source)
        return extract_from_ast(source, gettext_functions)

    def parse(self, parser):
        """Parse a translatable tag."""
        lineno = next(parser.stream).lineno
        num_called_num = False

        # find all the variables referenced.  Additionally a variable can be
        # defined in the body of the trans block too, but this is checked at
        # a later state.
        plural_expr = None
        variables = {}
        while parser.stream.current.type != 'block_end':
            if variables:
                parser.stream.expect('comma')

            # skip colon for python compatibility
            if parser.stream.skip_if('colon'):
                break

            name = parser.stream.expect('name')
            if name.value in variables:
                parser.fail('translatable variable %r defined twice.' %
                            name.value, name.lineno,
                            exc=TemplateAssertionError)

            # expressions
            if parser.stream.current.type == 'assign':
                next(parser.stream)
                variables[name.value] = var = parser.parse_expression()
            else:
                variables[name.value] = var = nodes.Name(name.value, 'load')

            if plural_expr is None:
                plural_expr = var
                num_called_num = name.value == 'num'

        parser.stream.expect('block_end')

        plural = plural_names = None
        have_plural = False
        referenced = set()

        # now parse until endtrans or pluralize
        singular_names, singular = self._parse_block(parser, True)
        if singular_names:
            referenced.update(singular_names)
            if plural_expr is None:
                plural_expr = nodes.Name(singular_names[0], 'load')
                num_called_num = singular_names[0] == 'num'

        # if we have a pluralize block, we parse that too
        if parser.stream.current.test('name:pluralize'):
            have_plural = True
            next(parser.stream)
            if parser.stream.current.type != 'block_end':
                name = parser.stream.expect('name')
                if name.value not in variables:
                    parser.fail('unknown variable %r for pluralization' %
                                name.value, name.lineno,
                                exc=TemplateAssertionError)
                plural_expr = variables[name.value]
                num_called_num = name.value == 'num'
            parser.stream.expect('block_end')
            plural_names, plural = self._parse_block(parser, False)
            next(parser.stream)
            referenced.update(plural_names)
        else:
            next(parser.stream)

        # register free names as simple name expressions
        for var in referenced:
            if var not in variables:
                variables[var] = nodes.Name(var, 'load')

        if not have_plural:
            plural_expr = None
        elif plural_expr is None:
            parser.fail('pluralize without variables', lineno)

        node = self._make_node(singular, plural, variables, plural_expr,
                               bool(referenced),
                               num_called_num and have_plural)
        node.set_lineno(lineno)
        return node

    def _parse_block(self, parser, allow_pluralize):
        """Parse until the next block tag with a given name."""
        referenced = []
        buf = []
        while 1:
            if parser.stream.current.type == 'data':
                buf.append(parser.stream.current.value.replace('%', '%%'))
                next(parser.stream)
            elif parser.stream.current.type == 'variable_begin':
                next(parser.stream)
                name = parser.stream.expect('name').value
                referenced.append(name)
                buf.append('%%(%s)s' % name)
                parser.stream.expect('variable_end')
            elif parser.stream.current.type == 'block_begin':
                next(parser.stream)
                if parser.stream.current.test('name:endtrans'):
                    break
                elif parser.stream.current.test('name:pluralize'):
                    if allow_pluralize:
                        break
                    parser.fail('a translatable section can have only one '
                                'pluralize section')
                parser.fail('control structures in translatable sections are '
                            'not allowed')
            elif parser.stream.eos:
                parser.fail('unclosed translation block')
            else:
                assert False, 'internal parser error'

        return referenced, concat(buf)

    def _make_node(self, singular, plural, variables, plural_expr,
                   vars_referenced, num_called_num):
        """Generates a useful node from the data provided."""
        # no variables referenced?  no need to escape for old style
        # gettext invocations only if there are vars.
        if not vars_referenced and not self.environment.newstyle_gettext:
            singular = singular.replace('%%', '%')
            if plural:
                plural = plural.replace('%%', '%')

        # singular only:
        if plural_expr is None:
            gettext = nodes.Name('gettext', 'load')
            node = nodes.Call(gettext, [nodes.Const(singular)],
                              [], None, None)

        # singular and plural
        else:
            ngettext = nodes.Name('ngettext', 'load')
            node = nodes.Call(ngettext, [
                nodes.Const(singular),
                nodes.Const(plural),
                plural_expr
            ], [], None, None)

        # in case newstyle gettext is used, the method is powerful
        # enough to handle the variable expansion and autoescape
        # handling itself
        if self.environment.newstyle_gettext:
            for key, value in variables.iteritems():
                # the function adds that later anyways in case num was
                # called num, so just skip it.
                if num_called_num and key == 'num':
                    continue
                node.kwargs.append(nodes.Keyword(key, value))

        # otherwise do that here
        else:
            # mark the return value as safe if we are in an
            # environment with autoescaping turned on
            node = nodes.MarkSafeIfAutoescape(node)
            if variables:
                node = nodes.Mod(node, nodes.Dict([
                    nodes.Pair(nodes.Const(key), value)
                    for key, value in variables.items()
                ]))
        return nodes.Output([node])


class ExprStmtExtension(Extension):
    """Adds a `do` tag to Jinja2 that works like the print statement just
    that it doesn't print the return value.
    """
    tags = set(['do'])

    def parse(self, parser):
        node = nodes.ExprStmt(lineno=next(parser.stream).lineno)
        node.node = parser.parse_tuple()
        return node


class LoopControlExtension(Extension):
    """Adds break and continue to the template engine."""
    tags = set(['break', 'continue'])

    def parse(self, parser):
        token = next(parser.stream)
        if token.value == 'break':
            return nodes.Break(lineno=token.lineno)
        return nodes.Continue(lineno=token.lineno)


class WithExtension(Extension):
    """Adds support for a django-like with block."""
    tags = set(['with'])

    def parse(self, parser):
        node = nodes.Scope(lineno=next(parser.stream).lineno)
        assignments = []
        while parser.stream.current.type != 'block_end':
            lineno = parser.stream.current.lineno
            if assignments:
                parser.stream.expect('comma')
            target = parser.parse_assign_target()
            parser.stream.expect('assign')
            expr = parser.parse_expression()
            assignments.append(nodes.Assign(target, expr, lineno=lineno))
        node.body = assignments + \
            list(parser.parse_statements(('name:endwith',),
                                         drop_needle=True))
        return node


class AutoEscapeExtension(Extension):
    """Changes auto escape rules for a scope."""
    tags = set(['autoescape'])

    def parse(self, parser):
        node = nodes.ScopedEvalContextModifier(lineno=next(parser.stream).lineno)
        node.options = [
            nodes.Keyword('autoescape', parser.parse_expression())
        ]
        node.body = parser.parse_statements(('name:endautoescape',),
                                            drop_needle=True)
        return nodes.Scope([node])


def extract_from_ast(node, gettext_functions=GETTEXT_FUNCTIONS,
                     babel_style=True):
    """Extract localizable strings from the given template node.  Per
    default this function returns matches in babel style that means non string
    parameters as well as keyword arguments are returned as `None`.  This
    allows Babel to figure out what you really meant if you are using
    gettext functions that allow keyword arguments for placeholder expansion.
    If you don't want that behavior set the `babel_style` parameter to `False`
    which causes only strings to be returned and parameters are always stored
    in tuples.  As a consequence invalid gettext calls (calls without a single
    string parameter or string parameters after non-string parameters) are
    skipped.

    This example explains the behavior:

    >>> from jinja2 import Environment
    >>> env = Environment()
    >>> node = env.parse('{{ (_("foo"), _(), ngettext("foo", "bar", 42)) }}')
    >>> list(extract_from_ast(node))
    [(1, '_', 'foo'), (1, '_', ()), (1, 'ngettext', ('foo', 'bar', None))]
    >>> list(extract_from_ast(node, babel_style=False))
    [(1, '_', ('foo',)), (1, 'ngettext', ('foo', 'bar'))]

    For every string found this function yields a ``(lineno, function,
    message)`` tuple, where:

    * ``lineno`` is the number of the line on which the string was found,
    * ``function`` is the name of the ``gettext`` function used (if the
      string was extracted from embedded Python code), and
    *  ``message`` is the string itself (a ``unicode`` object, or a tuple
       of ``unicode`` objects for functions with multiple string arguments).

    This extraction function operates on the AST and is because of that unable
    to extract any comments.  For comment support you have to use the babel
    extraction interface or extract comments yourself.
    """
    for node in node.find_all(nodes.Call):
        if not isinstance(node.node, nodes.Name) or \
           node.node.name not in gettext_functions:
            continue

        strings = []
        for arg in node.args:
            if isinstance(arg, nodes.Const) and \
               isinstance(arg.value, basestring):
                strings.append(arg.value)
            else:
                strings.append(None)

        for arg in node.kwargs:
            strings.append(None)
        if node.dyn_args is not None:
            strings.append(None)
        if node.dyn_kwargs is not None:
            strings.append(None)

        if not babel_style:
            strings = tuple(x for x in strings if x is not None)
            if not strings:
                continue
        else:
            if len(strings) == 1:
                strings = strings[0]
            else:
                strings = tuple(strings)
        yield node.lineno, node.node.name, strings


class _CommentFinder(object):
    """Helper class to find comments in a token stream.  Can only
    find comments for gettext calls forwards.  Once the comment
    from line 4 is found, a comment for line 1 will not return a
    usable value.
    """

    def __init__(self, tokens, comment_tags):
        self.tokens = tokens
        self.comment_tags = comment_tags
        self.offset = 0
        self.last_lineno = 0

    def find_backwards(self, offset):
        try:
            for _, token_type, token_value in \
                    reversed(self.tokens[self.offset:offset]):
                if token_type in ('comment', 'linecomment'):
                    try:
                        prefix, comment = token_value.split(None, 1)
                    except ValueError:
                        continue
                    if prefix in self.comment_tags:
                        return [comment.rstrip()]
            return []
        finally:
            self.offset = offset

    def find_comments(self, lineno):
        if not self.comment_tags or self.last_lineno > lineno:
            return []
        for idx, (token_lineno, _, _) in enumerate(self.tokens[self.offset:]):
            if token_lineno > lineno:
                return self.find_backwards(self.offset + idx)
        return self.find_backwards(len(self.tokens))


def babel_extract(fileobj, keywords, comment_tags, options):
    """Babel extraction method for Jinja templates.

    .. versionchanged:: 2.3
       Basic support for translation comments was added.  If `comment_tags`
       is now set to a list of keywords for extraction, the extractor will
       try to find the best preceeding comment that begins with one of the
       keywords.  For best results, make sure to not have more than one
       gettext call in one line of code and the matching comment in the
       same line or the line before.

    .. versionchanged:: 2.5.1
       The `newstyle_gettext` flag can be set to `True` to enable newstyle
       gettext calls.

    :param fileobj: the file-like object the messages should be extracted from
    :param keywords: a list of keywords (i.e. function names) that should be
                     recognized as translation functions
    :param comment_tags: a list of translator tags to search for and include
                         in the results.
    :param options: a dictionary of additional options (optional)
    :return: an iterator over ``(lineno, funcname, message, comments)`` tuples.
             (comments will be empty currently)
    """
    extensions = set()
    for extension in options.get('extensions', '').split(','):
        extension = extension.strip()
        if not extension:
            continue
        extensions.add(import_string(extension))
    if InternationalizationExtension not in extensions:
        extensions.add(InternationalizationExtension)

    def getbool(options, key, default=False):
        options.get(key, str(default)).lower() in ('1', 'on', 'yes', 'true')

    environment = Environment(
        options.get('block_start_string', BLOCK_START_STRING),
        options.get('block_end_string', BLOCK_END_STRING),
        options.get('variable_start_string', VARIABLE_START_STRING),
        options.get('variable_end_string', VARIABLE_END_STRING),
        options.get('comment_start_string', COMMENT_START_STRING),
        options.get('comment_end_string', COMMENT_END_STRING),
        options.get('line_statement_prefix') or LINE_STATEMENT_PREFIX,
        options.get('line_comment_prefix') or LINE_COMMENT_PREFIX,
        getbool(options, 'trim_blocks', TRIM_BLOCKS),
        NEWLINE_SEQUENCE, frozenset(extensions),
        cache_size=0,
        auto_reload=False
    )

    if getbool(options, 'newstyle_gettext'):
        environment.newstyle_gettext = True

    source = fileobj.read().decode(options.get('encoding', 'utf-8'))
    try:
        node = environment.parse(source)
        tokens = list(environment.lex(environment.preprocess(source)))
    except TemplateSyntaxError, e:
        # skip templates with syntax errors
        return

    finder = _CommentFinder(tokens, comment_tags)
    for lineno, func, message in extract_from_ast(node, keywords):
        yield lineno, func, message, finder.find_comments(lineno)


#: nicer import names
i18n = InternationalizationExtension
do = ExprStmtExtension
loopcontrols = LoopControlExtension
with_ = WithExtension
autoescape = AutoEscapeExtension

########NEW FILE########
__FILENAME__ = filters
# -*- coding: utf-8 -*-
"""
    jinja2.filters
    ~~~~~~~~~~~~~~

    Bundled jinja filters.

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD, see LICENSE for more details.
"""
import re
import math
from random import choice
from operator import itemgetter
from itertools import imap, groupby
from jinja2.utils import Markup, escape, pformat, urlize, soft_unicode
from jinja2.runtime import Undefined
from jinja2.exceptions import FilterArgumentError, SecurityError


_word_re = re.compile(r'\w+(?u)')


def contextfilter(f):
    """Decorator for marking context dependent filters. The current
    :class:`Context` will be passed as first argument.
    """
    f.contextfilter = True
    return f


def evalcontextfilter(f):
    """Decorator for marking eval-context dependent filters.  An eval
    context object is passed as first argument.  For more information
    about the eval context, see :ref:`eval-context`.

    .. versionadded:: 2.4
    """
    f.evalcontextfilter = True
    return f


def environmentfilter(f):
    """Decorator for marking evironment dependent filters.  The current
    :class:`Environment` is passed to the filter as first argument.
    """
    f.environmentfilter = True
    return f


def make_attrgetter(environment, attribute):
    """Returns a callable that looks up the given attribute from a
    passed object with the rules of the environment.  Dots are allowed
    to access attributes of attributes.
    """
    if '.' not in attribute:
        return lambda x: environment.getitem(x, attribute)
    attribute = attribute.split('.')
    def attrgetter(item):
        for part in attribute:
            item = environment.getitem(item, part)
        return item
    return attrgetter


def do_forceescape(value):
    """Enforce HTML escaping.  This will probably double escape variables."""
    if hasattr(value, '__html__'):
        value = value.__html__()
    return escape(unicode(value))


@evalcontextfilter
def do_replace(eval_ctx, s, old, new, count=None):
    """Return a copy of the value with all occurrences of a substring
    replaced with a new one. The first argument is the substring
    that should be replaced, the second is the replacement string.
    If the optional third argument ``count`` is given, only the first
    ``count`` occurrences are replaced:

    .. sourcecode:: jinja

        {{ "Hello World"|replace("Hello", "Goodbye") }}
            -> Goodbye World

        {{ "aaaaargh"|replace("a", "d'oh, ", 2) }}
            -> d'oh, d'oh, aaargh
    """
    if count is None:
        count = -1
    if not eval_ctx.autoescape:
        return unicode(s).replace(unicode(old), unicode(new), count)
    if hasattr(old, '__html__') or hasattr(new, '__html__') and \
       not hasattr(s, '__html__'):
        s = escape(s)
    else:
        s = soft_unicode(s)
    return s.replace(soft_unicode(old), soft_unicode(new), count)


def do_upper(s):
    """Convert a value to uppercase."""
    return soft_unicode(s).upper()


def do_lower(s):
    """Convert a value to lowercase."""
    return soft_unicode(s).lower()


@evalcontextfilter
def do_xmlattr(_eval_ctx, d, autospace=True):
    """Create an SGML/XML attribute string based on the items in a dict.
    All values that are neither `none` nor `undefined` are automatically
    escaped:

    .. sourcecode:: html+jinja

        <ul{{ {'class': 'my_list', 'missing': none,
                'id': 'list-%d'|format(variable)}|xmlattr }}>
        ...
        </ul>

    Results in something like this:

    .. sourcecode:: html

        <ul class="my_list" id="list-42">
        ...
        </ul>

    As you can see it automatically prepends a space in front of the item
    if the filter returned something unless the second parameter is false.
    """
    rv = u' '.join(
        u'%s="%s"' % (escape(key), escape(value))
        for key, value in d.iteritems()
        if value is not None and not isinstance(value, Undefined)
    )
    if autospace and rv:
        rv = u' ' + rv
    if _eval_ctx.autoescape:
        rv = Markup(rv)
    return rv


def do_capitalize(s):
    """Capitalize a value. The first character will be uppercase, all others
    lowercase.
    """
    return soft_unicode(s).capitalize()


def do_title(s):
    """Return a titlecased version of the value. I.e. words will start with
    uppercase letters, all remaining characters are lowercase.
    """
    return soft_unicode(s).title()


def do_dictsort(value, case_sensitive=False, by='key'):
    """Sort a dict and yield (key, value) pairs. Because python dicts are
    unsorted you may want to use this function to order them by either
    key or value:

    .. sourcecode:: jinja

        {% for item in mydict|dictsort %}
            sort the dict by key, case insensitive

        {% for item in mydict|dicsort(true) %}
            sort the dict by key, case sensitive

        {% for item in mydict|dictsort(false, 'value') %}
            sort the dict by key, case insensitive, sorted
            normally and ordered by value.
    """
    if by == 'key':
        pos = 0
    elif by == 'value':
        pos = 1
    else:
        raise FilterArgumentError('You can only sort by either '
                                  '"key" or "value"')
    def sort_func(item):
        value = item[pos]
        if isinstance(value, basestring) and not case_sensitive:
            value = value.lower()
        return value

    return sorted(value.items(), key=sort_func)


@environmentfilter
def do_sort(environment, value, reverse=False, case_sensitive=False,
            attribute=None):
    """Sort an iterable.  Per default it sorts ascending, if you pass it
    true as first argument it will reverse the sorting.

    If the iterable is made of strings the third parameter can be used to
    control the case sensitiveness of the comparison which is disabled by
    default.

    .. sourcecode:: jinja

        {% for item in iterable|sort %}
            ...
        {% endfor %}

    It is also possible to sort by an attribute (for example to sort
    by the date of an object) by specifying the `attribute` parameter:

    .. sourcecode:: jinja

        {% for item in iterable|sort(attribute='date') %}
            ...
        {% endfor %}

    .. versionchanged:: 2.6
       The `attribute` parameter was added.
    """
    if not case_sensitive:
        def sort_func(item):
            if isinstance(item, basestring):
                item = item.lower()
            return item
    else:
        sort_func = None
    if attribute is not None:
        getter = make_attrgetter(environment, attribute)
        def sort_func(item, processor=sort_func or (lambda x: x)):
            return processor(getter(item))
    return sorted(value, key=sort_func, reverse=reverse)


def do_default(value, default_value=u'', boolean=False):
    """If the value is undefined it will return the passed default value,
    otherwise the value of the variable:

    .. sourcecode:: jinja

        {{ my_variable|default('my_variable is not defined') }}

    This will output the value of ``my_variable`` if the variable was
    defined, otherwise ``'my_variable is not defined'``. If you want
    to use default with variables that evaluate to false you have to
    set the second parameter to `true`:

    .. sourcecode:: jinja

        {{ ''|default('the string was empty', true) }}
    """
    if (boolean and not value) or isinstance(value, Undefined):
        return default_value
    return value


@evalcontextfilter
def do_join(eval_ctx, value, d=u'', attribute=None):
    """Return a string which is the concatenation of the strings in the
    sequence. The separator between elements is an empty string per
    default, you can define it with the optional parameter:

    .. sourcecode:: jinja

        {{ [1, 2, 3]|join('|') }}
            -> 1|2|3

        {{ [1, 2, 3]|join }}
            -> 123

    It is also possible to join certain attributes of an object:

    .. sourcecode:: jinja

        {{ users|join(', ', attribute='username') }}

    .. versionadded:: 2.6
       The `attribute` parameter was added.
    """
    if attribute is not None:
        value = imap(make_attrgetter(eval_ctx.environment, attribute), value)

    # no automatic escaping?  joining is a lot eaiser then
    if not eval_ctx.autoescape:
        return unicode(d).join(imap(unicode, value))

    # if the delimiter doesn't have an html representation we check
    # if any of the items has.  If yes we do a coercion to Markup
    if not hasattr(d, '__html__'):
        value = list(value)
        do_escape = False
        for idx, item in enumerate(value):
            if hasattr(item, '__html__'):
                do_escape = True
            else:
                value[idx] = unicode(item)
        if do_escape:
            d = escape(d)
        else:
            d = unicode(d)
        return d.join(value)

    # no html involved, to normal joining
    return soft_unicode(d).join(imap(soft_unicode, value))


def do_center(value, width=80):
    """Centers the value in a field of a given width."""
    return unicode(value).center(width)


@environmentfilter
def do_first(environment, seq):
    """Return the first item of a sequence."""
    try:
        return iter(seq).next()
    except StopIteration:
        return environment.undefined('No first item, sequence was empty.')


@environmentfilter
def do_last(environment, seq):
    """Return the last item of a sequence."""
    try:
        return iter(reversed(seq)).next()
    except StopIteration:
        return environment.undefined('No last item, sequence was empty.')


@environmentfilter
def do_random(environment, seq):
    """Return a random item from the sequence."""
    try:
        return choice(seq)
    except IndexError:
        return environment.undefined('No random item, sequence was empty.')


def do_filesizeformat(value, binary=False):
    """Format the value like a 'human-readable' file size (i.e. 13 kB,
    4.1 MB, 102 Bytes, etc).  Per default decimal prefixes are used (Mega,
    Giga, etc.), if the second parameter is set to `True` the binary
    prefixes are used (Mebi, Gibi).
    """
    bytes = float(value)
    base = binary and 1024 or 1000
    prefixes = [
        (binary and "KiB" or "kB"),
        (binary and "MiB" or "MB"),
        (binary and "GiB" or "GB"),
        (binary and "TiB" or "TB"),
        (binary and "PiB" or "PB"),
        (binary and "EiB" or "EB"),
        (binary and "ZiB" or "ZB"),
        (binary and "YiB" or "YB")
    ]
    if bytes == 1:
        return "1 Byte"
    elif bytes < base:
        return "%d Bytes" % bytes
    else:
        for i, prefix in enumerate(prefixes):
            unit = base * base ** (i + 1)
            if bytes < unit:
                return "%.1f %s" % ((bytes / unit), prefix)
        return "%.1f %s" % ((bytes / unit), prefix)


def do_pprint(value, verbose=False):
    """Pretty print a variable. Useful for debugging.

    With Jinja 1.2 onwards you can pass it a parameter.  If this parameter
    is truthy the output will be more verbose (this requires `pretty`)
    """
    return pformat(value, verbose=verbose)


@evalcontextfilter
def do_urlize(eval_ctx, value, trim_url_limit=None, nofollow=False):
    """Converts URLs in plain text into clickable links.

    If you pass the filter an additional integer it will shorten the urls
    to that number. Also a third argument exists that makes the urls
    "nofollow":

    .. sourcecode:: jinja

        {{ mytext|urlize(40, true) }}
            links are shortened to 40 chars and defined with rel="nofollow"
    """
    rv = urlize(value, trim_url_limit, nofollow)
    if eval_ctx.autoescape:
        rv = Markup(rv)
    return rv


def do_indent(s, width=4, indentfirst=False):
    """Return a copy of the passed string, each line indented by
    4 spaces. The first line is not indented. If you want to
    change the number of spaces or indent the first line too
    you can pass additional parameters to the filter:

    .. sourcecode:: jinja

        {{ mytext|indent(2, true) }}
            indent by two spaces and indent the first line too.
    """
    indention = u' ' * width
    rv = (u'\n' + indention).join(s.splitlines())
    if indentfirst:
        rv = indention + rv
    return rv


def do_truncate(s, length=255, killwords=False, end='...'):
    """Return a truncated copy of the string. The length is specified
    with the first parameter which defaults to ``255``. If the second
    parameter is ``true`` the filter will cut the text at length. Otherwise
    it will try to save the last word. If the text was in fact
    truncated it will append an ellipsis sign (``"..."``). If you want a
    different ellipsis sign than ``"..."`` you can specify it using the
    third parameter.

    .. sourcecode jinja::

        {{ mytext|truncate(300, false, '&raquo;') }}
            truncate mytext to 300 chars, don't split up words, use a
            right pointing double arrow as ellipsis sign.
    """
    if len(s) <= length:
        return s
    elif killwords:
        return s[:length] + end
    words = s.split(' ')
    result = []
    m = 0
    for word in words:
        m += len(word) + 1
        if m > length:
            break
        result.append(word)
    result.append(end)
    return u' '.join(result)

@environmentfilter
def do_wordwrap(environment, s, width=79, break_long_words=True):
    """
    Return a copy of the string passed to the filter wrapped after
    ``79`` characters.  You can override this default using the first
    parameter.  If you set the second parameter to `false` Jinja will not
    split words apart if they are longer than `width`.
    """
    import textwrap
    return environment.newline_sequence.join(textwrap.wrap(s, width=width, expand_tabs=False,
                                   replace_whitespace=False,
                                   break_long_words=break_long_words))


def do_wordcount(s):
    """Count the words in that string."""
    return len(_word_re.findall(s))


def do_int(value, default=0):
    """Convert the value into an integer. If the
    conversion doesn't work it will return ``0``. You can
    override this default using the first parameter.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        # this quirk is necessary so that "42.23"|int gives 42.
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default


def do_float(value, default=0.0):
    """Convert the value into a floating point number. If the
    conversion doesn't work it will return ``0.0``. You can
    override this default using the first parameter.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def do_format(value, *args, **kwargs):
    """
    Apply python string formatting on an object:

    .. sourcecode:: jinja

        {{ "%s - %s"|format("Hello?", "Foo!") }}
            -> Hello? - Foo!
    """
    if args and kwargs:
        raise FilterArgumentError('can\'t handle positional and keyword '
                                  'arguments at the same time')
    return soft_unicode(value) % (kwargs or args)


def do_trim(value):
    """Strip leading and trailing whitespace."""
    return soft_unicode(value).strip()


def do_striptags(value):
    """Strip SGML/XML tags and replace adjacent whitespace by one space.
    """
    if hasattr(value, '__html__'):
        value = value.__html__()
    return Markup(unicode(value)).striptags()


def do_slice(value, slices, fill_with=None):
    """Slice an iterator and return a list of lists containing
    those items. Useful if you want to create a div containing
    three ul tags that represent columns:

    .. sourcecode:: html+jinja

        <div class="columwrapper">
          {%- for column in items|slice(3) %}
            <ul class="column-{{ loop.index }}">
            {%- for item in column %}
              <li>{{ item }}</li>
            {%- endfor %}
            </ul>
          {%- endfor %}
        </div>

    If you pass it a second argument it's used to fill missing
    values on the last iteration.
    """
    seq = list(value)
    length = len(seq)
    items_per_slice = length // slices
    slices_with_extra = length % slices
    offset = 0
    for slice_number in xrange(slices):
        start = offset + slice_number * items_per_slice
        if slice_number < slices_with_extra:
            offset += 1
        end = offset + (slice_number + 1) * items_per_slice
        tmp = seq[start:end]
        if fill_with is not None and slice_number >= slices_with_extra:
            tmp.append(fill_with)
        yield tmp


def do_batch(value, linecount, fill_with=None):
    """
    A filter that batches items. It works pretty much like `slice`
    just the other way round. It returns a list of lists with the
    given number of items. If you provide a second parameter this
    is used to fill missing items. See this example:

    .. sourcecode:: html+jinja

        <table>
        {%- for row in items|batch(3, '&nbsp;') %}
          <tr>
          {%- for column in row %}
            <td>{{ column }}</td>
          {%- endfor %}
          </tr>
        {%- endfor %}
        </table>
    """
    result = []
    tmp = []
    for item in value:
        if len(tmp) == linecount:
            yield tmp
            tmp = []
        tmp.append(item)
    if tmp:
        if fill_with is not None and len(tmp) < linecount:
            tmp += [fill_with] * (linecount - len(tmp))
        yield tmp


def do_round(value, precision=0, method='common'):
    """Round the number to a given precision. The first
    parameter specifies the precision (default is ``0``), the
    second the rounding method:

    - ``'common'`` rounds either up or down
    - ``'ceil'`` always rounds up
    - ``'floor'`` always rounds down

    If you don't specify a method ``'common'`` is used.

    .. sourcecode:: jinja

        {{ 42.55|round }}
            -> 43.0
        {{ 42.55|round(1, 'floor') }}
            -> 42.5

    Note that even if rounded to 0 precision, a float is returned.  If
    you need a real integer, pipe it through `int`:

    .. sourcecode:: jinja

        {{ 42.55|round|int }}
            -> 43
    """
    if not method in ('common', 'ceil', 'floor'):
        raise FilterArgumentError('method must be common, ceil or floor')
    if method == 'common':
        return round(value, precision)
    func = getattr(math, method)
    return func(value * (10 ** precision)) / (10 ** precision)


@environmentfilter
def do_groupby(environment, value, attribute):
    """Group a sequence of objects by a common attribute.

    If you for example have a list of dicts or objects that represent persons
    with `gender`, `first_name` and `last_name` attributes and you want to
    group all users by genders you can do something like the following
    snippet:

    .. sourcecode:: html+jinja

        <ul>
        {% for group in persons|groupby('gender') %}
            <li>{{ group.grouper }}<ul>
            {% for person in group.list %}
                <li>{{ person.first_name }} {{ person.last_name }}</li>
            {% endfor %}</ul></li>
        {% endfor %}
        </ul>

    Additionally it's possible to use tuple unpacking for the grouper and
    list:

    .. sourcecode:: html+jinja

        <ul>
        {% for grouper, list in persons|groupby('gender') %}
            ...
        {% endfor %}
        </ul>

    As you can see the item we're grouping by is stored in the `grouper`
    attribute and the `list` contains all the objects that have this grouper
    in common.

    .. versionchanged:: 2.6
       It's now possible to use dotted notation to group by the child
       attribute of another attribute.
    """
    expr = make_attrgetter(environment, attribute)
    return sorted(map(_GroupTuple, groupby(sorted(value, key=expr), expr)))


class _GroupTuple(tuple):
    __slots__ = ()
    grouper = property(itemgetter(0))
    list = property(itemgetter(1))

    def __new__(cls, (key, value)):
        return tuple.__new__(cls, (key, list(value)))


@environmentfilter
def do_sum(environment, iterable, attribute=None, start=0):
    """Returns the sum of a sequence of numbers plus the value of parameter
    'start' (which defaults to 0).  When the sequence is empty it returns
    start.

    It is also possible to sum up only certain attributes:

    .. sourcecode:: jinja

        Total: {{ items|sum(attribute='price') }}

    .. versionchanged:: 2.6
       The `attribute` parameter was added to allow suming up over
       attributes.  Also the `start` parameter was moved on to the right.
    """
    if attribute is not None:
        iterable = imap(make_attrgetter(environment, attribute), iterable)
    return sum(iterable, start)


def do_list(value):
    """Convert the value into a list.  If it was a string the returned list
    will be a list of characters.
    """
    return list(value)


def do_mark_safe(value):
    """Mark the value as safe which means that in an environment with automatic
    escaping enabled this variable will not be escaped.
    """
    return Markup(value)


def do_mark_unsafe(value):
    """Mark a value as unsafe.  This is the reverse operation for :func:`safe`."""
    return unicode(value)


def do_reverse(value):
    """Reverse the object or return an iterator the iterates over it the other
    way round.
    """
    if isinstance(value, basestring):
        return value[::-1]
    try:
        return reversed(value)
    except TypeError:
        try:
            rv = list(value)
            rv.reverse()
            return rv
        except TypeError:
            raise FilterArgumentError('argument must be iterable')


@environmentfilter
def do_attr(environment, obj, name):
    """Get an attribute of an object.  ``foo|attr("bar")`` works like
    ``foo["bar"]`` just that always an attribute is returned and items are not
    looked up.

    See :ref:`Notes on subscriptions <notes-on-subscriptions>` for more details.
    """
    try:
        name = str(name)
    except UnicodeError:
        pass
    else:
        try:
            value = getattr(obj, name)
        except AttributeError:
            pass
        else:
            if environment.sandboxed and not \
               environment.is_safe_attribute(obj, name, value):
                return environment.unsafe_undefined(obj, name)
            return value
    return environment.undefined(obj=obj, name=name)


FILTERS = {
    'attr':                 do_attr,
    'replace':              do_replace,
    'upper':                do_upper,
    'lower':                do_lower,
    'escape':               escape,
    'e':                    escape,
    'forceescape':          do_forceescape,
    'capitalize':           do_capitalize,
    'title':                do_title,
    'default':              do_default,
    'd':                    do_default,
    'join':                 do_join,
    'count':                len,
    'dictsort':             do_dictsort,
    'sort':                 do_sort,
    'length':               len,
    'reverse':              do_reverse,
    'center':               do_center,
    'indent':               do_indent,
    'title':                do_title,
    'capitalize':           do_capitalize,
    'first':                do_first,
    'last':                 do_last,
    'random':               do_random,
    'filesizeformat':       do_filesizeformat,
    'pprint':               do_pprint,
    'truncate':             do_truncate,
    'wordwrap':             do_wordwrap,
    'wordcount':            do_wordcount,
    'int':                  do_int,
    'float':                do_float,
    'string':               soft_unicode,
    'list':                 do_list,
    'urlize':               do_urlize,
    'format':               do_format,
    'trim':                 do_trim,
    'striptags':            do_striptags,
    'slice':                do_slice,
    'batch':                do_batch,
    'sum':                  do_sum,
    'abs':                  abs,
    'round':                do_round,
    'groupby':              do_groupby,
    'safe':                 do_mark_safe,
    'xmlattr':              do_xmlattr
}

########NEW FILE########
__FILENAME__ = lexer
# -*- coding: utf-8 -*-
"""
    jinja2.lexer
    ~~~~~~~~~~~~

    This module implements a Jinja / Python combination lexer. The
    `Lexer` class provided by this module is used to do some preprocessing
    for Jinja.

    On the one hand it filters out invalid operators like the bitshift
    operators we don't allow in templates. On the other hand it separates
    template code and python code in expressions.

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD, see LICENSE for more details.
"""
import re
from operator import itemgetter
from collections import deque
from jinja2.exceptions import TemplateSyntaxError
from jinja2.utils import LRUCache, next


# cache for the lexers. Exists in order to be able to have multiple
# environments with the same lexer
_lexer_cache = LRUCache(50)

# static regular expressions
whitespace_re = re.compile(r'\s+', re.U)
string_re = re.compile(r"('([^'\\]*(?:\\.[^'\\]*)*)'"
                       r'|"([^"\\]*(?:\\.[^"\\]*)*)")', re.S)
integer_re = re.compile(r'\d+')

# we use the unicode identifier rule if this python version is able
# to handle unicode identifiers, otherwise the standard ASCII one.
try:
    compile('föö', '<unknown>', 'eval')
except SyntaxError:
    name_re = re.compile(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b')
else:
    from jinja2 import _stringdefs
    name_re = re.compile(r'[%s][%s]*' % (_stringdefs.xid_start,
                                         _stringdefs.xid_continue))

float_re = re.compile(r'(?<!\.)\d+\.\d+')
newline_re = re.compile(r'(\r\n|\r|\n)')

# internal the tokens and keep references to them
TOKEN_ADD = intern('add')
TOKEN_ASSIGN = intern('assign')
TOKEN_COLON = intern('colon')
TOKEN_COMMA = intern('comma')
TOKEN_DIV = intern('div')
TOKEN_DOT = intern('dot')
TOKEN_EQ = intern('eq')
TOKEN_FLOORDIV = intern('floordiv')
TOKEN_GT = intern('gt')
TOKEN_GTEQ = intern('gteq')
TOKEN_LBRACE = intern('lbrace')
TOKEN_LBRACKET = intern('lbracket')
TOKEN_LPAREN = intern('lparen')
TOKEN_LT = intern('lt')
TOKEN_LTEQ = intern('lteq')
TOKEN_MOD = intern('mod')
TOKEN_MUL = intern('mul')
TOKEN_NE = intern('ne')
TOKEN_PIPE = intern('pipe')
TOKEN_POW = intern('pow')
TOKEN_RBRACE = intern('rbrace')
TOKEN_RBRACKET = intern('rbracket')
TOKEN_RPAREN = intern('rparen')
TOKEN_SEMICOLON = intern('semicolon')
TOKEN_SUB = intern('sub')
TOKEN_TILDE = intern('tilde')
TOKEN_WHITESPACE = intern('whitespace')
TOKEN_FLOAT = intern('float')
TOKEN_INTEGER = intern('integer')
TOKEN_NAME = intern('name')
TOKEN_STRING = intern('string')
TOKEN_OPERATOR = intern('operator')
TOKEN_BLOCK_BEGIN = intern('block_begin')
TOKEN_BLOCK_END = intern('block_end')
TOKEN_VARIABLE_BEGIN = intern('variable_begin')
TOKEN_VARIABLE_END = intern('variable_end')
TOKEN_RAW_BEGIN = intern('raw_begin')
TOKEN_RAW_END = intern('raw_end')
TOKEN_COMMENT_BEGIN = intern('comment_begin')
TOKEN_COMMENT_END = intern('comment_end')
TOKEN_COMMENT = intern('comment')
TOKEN_LINESTATEMENT_BEGIN = intern('linestatement_begin')
TOKEN_LINESTATEMENT_END = intern('linestatement_end')
TOKEN_LINECOMMENT_BEGIN = intern('linecomment_begin')
TOKEN_LINECOMMENT_END = intern('linecomment_end')
TOKEN_LINECOMMENT = intern('linecomment')
TOKEN_DATA = intern('data')
TOKEN_INITIAL = intern('initial')
TOKEN_EOF = intern('eof')

# bind operators to token types
operators = {
    '+':            TOKEN_ADD,
    '-':            TOKEN_SUB,
    '/':            TOKEN_DIV,
    '//':           TOKEN_FLOORDIV,
    '*':            TOKEN_MUL,
    '%':            TOKEN_MOD,
    '**':           TOKEN_POW,
    '~':            TOKEN_TILDE,
    '[':            TOKEN_LBRACKET,
    ']':            TOKEN_RBRACKET,
    '(':            TOKEN_LPAREN,
    ')':            TOKEN_RPAREN,
    '{':            TOKEN_LBRACE,
    '}':            TOKEN_RBRACE,
    '==':           TOKEN_EQ,
    '!=':           TOKEN_NE,
    '>':            TOKEN_GT,
    '>=':           TOKEN_GTEQ,
    '<':            TOKEN_LT,
    '<=':           TOKEN_LTEQ,
    '=':            TOKEN_ASSIGN,
    '.':            TOKEN_DOT,
    ':':            TOKEN_COLON,
    '|':            TOKEN_PIPE,
    ',':            TOKEN_COMMA,
    ';':            TOKEN_SEMICOLON
}

reverse_operators = dict([(v, k) for k, v in operators.iteritems()])
assert len(operators) == len(reverse_operators), 'operators dropped'
operator_re = re.compile('(%s)' % '|'.join(re.escape(x) for x in
                         sorted(operators, key=lambda x: -len(x))))

ignored_tokens = frozenset([TOKEN_COMMENT_BEGIN, TOKEN_COMMENT,
                            TOKEN_COMMENT_END, TOKEN_WHITESPACE,
                            TOKEN_WHITESPACE, TOKEN_LINECOMMENT_BEGIN,
                            TOKEN_LINECOMMENT_END, TOKEN_LINECOMMENT])
ignore_if_empty = frozenset([TOKEN_WHITESPACE, TOKEN_DATA,
                             TOKEN_COMMENT, TOKEN_LINECOMMENT])


def _describe_token_type(token_type):
    if token_type in reverse_operators:
        return reverse_operators[token_type]
    return {
        TOKEN_COMMENT_BEGIN:        'begin of comment',
        TOKEN_COMMENT_END:          'end of comment',
        TOKEN_COMMENT:              'comment',
        TOKEN_LINECOMMENT:          'comment',
        TOKEN_BLOCK_BEGIN:          'begin of statement block',
        TOKEN_BLOCK_END:            'end of statement block',
        TOKEN_VARIABLE_BEGIN:       'begin of print statement',
        TOKEN_VARIABLE_END:         'end of print statement',
        TOKEN_LINESTATEMENT_BEGIN:  'begin of line statement',
        TOKEN_LINESTATEMENT_END:    'end of line statement',
        TOKEN_DATA:                 'template data / text',
        TOKEN_EOF:                  'end of template'
    }.get(token_type, token_type)


def describe_token(token):
    """Returns a description of the token."""
    if token.type == 'name':
        return token.value
    return _describe_token_type(token.type)


def describe_token_expr(expr):
    """Like `describe_token` but for token expressions."""
    if ':' in expr:
        type, value = expr.split(':', 1)
        if type == 'name':
            return value
    else:
        type = expr
    return _describe_token_type(type)


def count_newlines(value):
    """Count the number of newline characters in the string.  This is
    useful for extensions that filter a stream.
    """
    return len(newline_re.findall(value))


def compile_rules(environment):
    """Compiles all the rules from the environment into a list of rules."""
    e = re.escape
    rules = [
        (len(environment.comment_start_string), 'comment',
         e(environment.comment_start_string)),
        (len(environment.block_start_string), 'block',
         e(environment.block_start_string)),
        (len(environment.variable_start_string), 'variable',
         e(environment.variable_start_string))
    ]

    if environment.line_statement_prefix is not None:
        rules.append((len(environment.line_statement_prefix), 'linestatement',
                      r'^\s*' + e(environment.line_statement_prefix)))
    if environment.line_comment_prefix is not None:
        rules.append((len(environment.line_comment_prefix), 'linecomment',
                      r'(?:^|(?<=\S))[^\S\r\n]*' +
                      e(environment.line_comment_prefix)))

    return [x[1:] for x in sorted(rules, reverse=True)]


class Failure(object):
    """Class that raises a `TemplateSyntaxError` if called.
    Used by the `Lexer` to specify known errors.
    """

    def __init__(self, message, cls=TemplateSyntaxError):
        self.message = message
        self.error_class = cls

    def __call__(self, lineno, filename):
        raise self.error_class(self.message, lineno, filename)


class Token(tuple):
    """Token class."""
    __slots__ = ()
    lineno, type, value = (property(itemgetter(x)) for x in range(3))

    def __new__(cls, lineno, type, value):
        return tuple.__new__(cls, (lineno, intern(str(type)), value))

    def __str__(self):
        if self.type in reverse_operators:
            return reverse_operators[self.type]
        elif self.type == 'name':
            return self.value
        return self.type

    def test(self, expr):
        """Test a token against a token expression.  This can either be a
        token type or ``'token_type:token_value'``.  This can only test
        against string values and types.
        """
        # here we do a regular string equality check as test_any is usually
        # passed an iterable of not interned strings.
        if self.type == expr:
            return True
        elif ':' in expr:
            return expr.split(':', 1) == [self.type, self.value]
        return False

    def test_any(self, *iterable):
        """Test against multiple token expressions."""
        for expr in iterable:
            if self.test(expr):
                return True
        return False

    def __repr__(self):
        return 'Token(%r, %r, %r)' % (
            self.lineno,
            self.type,
            self.value
        )


class TokenStreamIterator(object):
    """The iterator for tokenstreams.  Iterate over the stream
    until the eof token is reached.
    """

    def __init__(self, stream):
        self.stream = stream

    def __iter__(self):
        return self

    def next(self):
        token = self.stream.current
        if token.type is TOKEN_EOF:
            self.stream.close()
            raise StopIteration()
        next(self.stream)
        return token


class TokenStream(object):
    """A token stream is an iterable that yields :class:`Token`\s.  The
    parser however does not iterate over it but calls :meth:`next` to go
    one token ahead.  The current active token is stored as :attr:`current`.
    """

    def __init__(self, generator, name, filename):
        self._next = iter(generator).next
        self._pushed = deque()
        self.name = name
        self.filename = filename
        self.closed = False
        self.current = Token(1, TOKEN_INITIAL, '')
        next(self)

    def __iter__(self):
        return TokenStreamIterator(self)

    def __nonzero__(self):
        return bool(self._pushed) or self.current.type is not TOKEN_EOF

    eos = property(lambda x: not x, doc="Are we at the end of the stream?")

    def push(self, token):
        """Push a token back to the stream."""
        self._pushed.append(token)

    def look(self):
        """Look at the next token."""
        old_token = next(self)
        result = self.current
        self.push(result)
        self.current = old_token
        return result

    def skip(self, n=1):
        """Got n tokens ahead."""
        for x in xrange(n):
            next(self)

    def next_if(self, expr):
        """Perform the token test and return the token if it matched.
        Otherwise the return value is `None`.
        """
        if self.current.test(expr):
            return next(self)

    def skip_if(self, expr):
        """Like :meth:`next_if` but only returns `True` or `False`."""
        return self.next_if(expr) is not None

    def next(self):
        """Go one token ahead and return the old one"""
        rv = self.current
        if self._pushed:
            self.current = self._pushed.popleft()
        elif self.current.type is not TOKEN_EOF:
            try:
                self.current = self._next()
            except StopIteration:
                self.close()
        return rv

    def close(self):
        """Close the stream."""
        self.current = Token(self.current.lineno, TOKEN_EOF, '')
        self._next = None
        self.closed = True

    def expect(self, expr):
        """Expect a given token type and return it.  This accepts the same
        argument as :meth:`jinja2.lexer.Token.test`.
        """
        if not self.current.test(expr):
            expr = describe_token_expr(expr)
            if self.current.type is TOKEN_EOF:
                raise TemplateSyntaxError('unexpected end of template, '
                                          'expected %r.' % expr,
                                          self.current.lineno,
                                          self.name, self.filename)
            raise TemplateSyntaxError("expected token %r, got %r" %
                                      (expr, describe_token(self.current)),
                                      self.current.lineno,
                                      self.name, self.filename)
        try:
            return self.current
        finally:
            next(self)


def get_lexer(environment):
    """Return a lexer which is probably cached."""
    key = (environment.block_start_string,
           environment.block_end_string,
           environment.variable_start_string,
           environment.variable_end_string,
           environment.comment_start_string,
           environment.comment_end_string,
           environment.line_statement_prefix,
           environment.line_comment_prefix,
           environment.trim_blocks,
           environment.newline_sequence)
    lexer = _lexer_cache.get(key)
    if lexer is None:
        lexer = Lexer(environment)
        _lexer_cache[key] = lexer
    return lexer


class Lexer(object):
    """Class that implements a lexer for a given environment. Automatically
    created by the environment class, usually you don't have to do that.

    Note that the lexer is not automatically bound to an environment.
    Multiple environments can share the same lexer.
    """

    def __init__(self, environment):
        # shortcuts
        c = lambda x: re.compile(x, re.M | re.S)
        e = re.escape

        # lexing rules for tags
        tag_rules = [
            (whitespace_re, TOKEN_WHITESPACE, None),
            (float_re, TOKEN_FLOAT, None),
            (integer_re, TOKEN_INTEGER, None),
            (name_re, TOKEN_NAME, None),
            (string_re, TOKEN_STRING, None),
            (operator_re, TOKEN_OPERATOR, None)
        ]

        # assamble the root lexing rule. because "|" is ungreedy
        # we have to sort by length so that the lexer continues working
        # as expected when we have parsing rules like <% for block and
        # <%= for variables. (if someone wants asp like syntax)
        # variables are just part of the rules if variable processing
        # is required.
        root_tag_rules = compile_rules(environment)

        # block suffix if trimming is enabled
        block_suffix_re = environment.trim_blocks and '\\n?' or ''

        self.newline_sequence = environment.newline_sequence

        # global lexing rules
        self.rules = {
            'root': [
                # directives
                (c('(.*?)(?:%s)' % '|'.join(
                    [r'(?P<raw_begin>(?:\s*%s\-|%s)\s*raw\s*(?:\-%s\s*|%s))' % (
                        e(environment.block_start_string),
                        e(environment.block_start_string),
                        e(environment.block_end_string),
                        e(environment.block_end_string)
                    )] + [
                        r'(?P<%s_begin>\s*%s\-|%s)' % (n, r, r)
                        for n, r in root_tag_rules
                    ])), (TOKEN_DATA, '#bygroup'), '#bygroup'),
                # data
                (c('.+'), TOKEN_DATA, None)
            ],
            # comments
            TOKEN_COMMENT_BEGIN: [
                (c(r'(.*?)((?:\-%s\s*|%s)%s)' % (
                    e(environment.comment_end_string),
                    e(environment.comment_end_string),
                    block_suffix_re
                )), (TOKEN_COMMENT, TOKEN_COMMENT_END), '#pop'),
                (c('(.)'), (Failure('Missing end of comment tag'),), None)
            ],
            # blocks
            TOKEN_BLOCK_BEGIN: [
                (c('(?:\-%s\s*|%s)%s' % (
                    e(environment.block_end_string),
                    e(environment.block_end_string),
                    block_suffix_re
                )), TOKEN_BLOCK_END, '#pop'),
            ] + tag_rules,
            # variables
            TOKEN_VARIABLE_BEGIN: [
                (c('\-%s\s*|%s' % (
                    e(environment.variable_end_string),
                    e(environment.variable_end_string)
                )), TOKEN_VARIABLE_END, '#pop')
            ] + tag_rules,
            # raw block
            TOKEN_RAW_BEGIN: [
                (c('(.*?)((?:\s*%s\-|%s)\s*endraw\s*(?:\-%s\s*|%s%s))' % (
                    e(environment.block_start_string),
                    e(environment.block_start_string),
                    e(environment.block_end_string),
                    e(environment.block_end_string),
                    block_suffix_re
                )), (TOKEN_DATA, TOKEN_RAW_END), '#pop'),
                (c('(.)'), (Failure('Missing end of raw directive'),), None)
            ],
            # line statements
            TOKEN_LINESTATEMENT_BEGIN: [
                (c(r'\s*(\n|$)'), TOKEN_LINESTATEMENT_END, '#pop')
            ] + tag_rules,
            # line comments
            TOKEN_LINECOMMENT_BEGIN: [
                (c(r'(.*?)()(?=\n|$)'), (TOKEN_LINECOMMENT,
                 TOKEN_LINECOMMENT_END), '#pop')
            ]
        }

    def _normalize_newlines(self, value):
        """Called for strings and template data to normlize it to unicode."""
        return newline_re.sub(self.newline_sequence, value)

    def tokenize(self, source, name=None, filename=None, state=None):
        """Calls tokeniter + tokenize and wraps it in a token stream.
        """
        stream = self.tokeniter(source, name, filename, state)
        return TokenStream(self.wrap(stream, name, filename), name, filename)

    def wrap(self, stream, name=None, filename=None):
        """This is called with the stream as returned by `tokenize` and wraps
        every token in a :class:`Token` and converts the value.
        """
        for lineno, token, value in stream:
            if token in ignored_tokens:
                continue
            elif token == 'linestatement_begin':
                token = 'block_begin'
            elif token == 'linestatement_end':
                token = 'block_end'
            # we are not interested in those tokens in the parser
            elif token in ('raw_begin', 'raw_end'):
                continue
            elif token == 'data':
                value = self._normalize_newlines(value)
            elif token == 'keyword':
                token = value
            elif token == 'name':
                value = str(value)
            elif token == 'string':
                # try to unescape string
                try:
                    value = self._normalize_newlines(value[1:-1]) \
                        .encode('ascii', 'backslashreplace') \
                        .decode('unicode-escape')
                except Exception, e:
                    msg = str(e).split(':')[-1].strip()
                    raise TemplateSyntaxError(msg, lineno, name, filename)
                # if we can express it as bytestring (ascii only)
                # we do that for support of semi broken APIs
                # as datetime.datetime.strftime.  On python 3 this
                # call becomes a noop thanks to 2to3
                try:
                    value = str(value)
                except UnicodeError:
                    pass
            elif token == 'integer':
                value = int(value)
            elif token == 'float':
                value = float(value)
            elif token == 'operator':
                token = operators[value]
            yield Token(lineno, token, value)

    def tokeniter(self, source, name, filename=None, state=None):
        """This method tokenizes the text and returns the tokens in a
        generator.  Use this method if you just want to tokenize a template.
        """
        source = '\n'.join(unicode(source).splitlines())
        pos = 0
        lineno = 1
        stack = ['root']
        if state is not None and state != 'root':
            assert state in ('variable', 'block'), 'invalid state'
            stack.append(state + '_begin')
        else:
            state = 'root'
        statetokens = self.rules[stack[-1]]
        source_length = len(source)

        balancing_stack = []

        while 1:
            # tokenizer loop
            for regex, tokens, new_state in statetokens:
                m = regex.match(source, pos)
                # if no match we try again with the next rule
                if m is None:
                    continue

                # we only match blocks and variables if brances / parentheses
                # are balanced. continue parsing with the lower rule which
                # is the operator rule. do this only if the end tags look
                # like operators
                if balancing_stack and \
                   tokens in ('variable_end', 'block_end',
                              'linestatement_end'):
                    continue

                # tuples support more options
                if isinstance(tokens, tuple):
                    for idx, token in enumerate(tokens):
                        # failure group
                        if token.__class__ is Failure:
                            raise token(lineno, filename)
                        # bygroup is a bit more complex, in that case we
                        # yield for the current token the first named
                        # group that matched
                        elif token == '#bygroup':
                            for key, value in m.groupdict().iteritems():
                                if value is not None:
                                    yield lineno, key, value
                                    lineno += value.count('\n')
                                    break
                            else:
                                raise RuntimeError('%r wanted to resolve '
                                                   'the token dynamically'
                                                   ' but no group matched'
                                                   % regex)
                        # normal group
                        else:
                            data = m.group(idx + 1)
                            if data or token not in ignore_if_empty:
                                yield lineno, token, data
                            lineno += data.count('\n')

                # strings as token just are yielded as it.
                else:
                    data = m.group()
                    # update brace/parentheses balance
                    if tokens == 'operator':
                        if data == '{':
                            balancing_stack.append('}')
                        elif data == '(':
                            balancing_stack.append(')')
                        elif data == '[':
                            balancing_stack.append(']')
                        elif data in ('}', ')', ']'):
                            if not balancing_stack:
                                raise TemplateSyntaxError('unexpected \'%s\'' %
                                                          data, lineno, name,
                                                          filename)
                            expected_op = balancing_stack.pop()
                            if expected_op != data:
                                raise TemplateSyntaxError('unexpected \'%s\', '
                                                          'expected \'%s\'' %
                                                          (data, expected_op),
                                                          lineno, name,
                                                          filename)
                    # yield items
                    if data or tokens not in ignore_if_empty:
                        yield lineno, tokens, data
                    lineno += data.count('\n')

                # fetch new position into new variable so that we can check
                # if there is a internal parsing error which would result
                # in an infinite loop
                pos2 = m.end()

                # handle state changes
                if new_state is not None:
                    # remove the uppermost state
                    if new_state == '#pop':
                        stack.pop()
                    # resolve the new state by group checking
                    elif new_state == '#bygroup':
                        for key, value in m.groupdict().iteritems():
                            if value is not None:
                                stack.append(key)
                                break
                        else:
                            raise RuntimeError('%r wanted to resolve the '
                                               'new state dynamically but'
                                               ' no group matched' %
                                               regex)
                    # direct state name given
                    else:
                        stack.append(new_state)
                    statetokens = self.rules[stack[-1]]
                # we are still at the same position and no stack change.
                # this means a loop without break condition, avoid that and
                # raise error
                elif pos2 == pos:
                    raise RuntimeError('%r yielded empty string without '
                                       'stack change' % regex)
                # publish new function and start again
                pos = pos2
                break
            # if loop terminated without break we havn't found a single match
            # either we are at the end of the file or we have a problem
            else:
                # end of text
                if pos >= source_length:
                    return
                # something went wrong
                raise TemplateSyntaxError('unexpected char %r at %d' %
                                          (source[pos], pos), lineno,
                                          name, filename)

########NEW FILE########
__FILENAME__ = loaders
# -*- coding: utf-8 -*-
"""
    jinja2.loaders
    ~~~~~~~~~~~~~~

    Jinja loader classes.

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD, see LICENSE for more details.
"""
import os
import sys
import weakref
from types import ModuleType
from os import path
try:
    from hashlib import sha1
except ImportError:
    from sha import new as sha1
from jinja2.exceptions import TemplateNotFound
from jinja2.utils import LRUCache, open_if_exists, internalcode


def split_template_path(template):
    """Split a path into segments and perform a sanity check.  If it detects
    '..' in the path it will raise a `TemplateNotFound` error.
    """
    pieces = []
    for piece in template.split('/'):
        if path.sep in piece \
           or (path.altsep and path.altsep in piece) or \
           piece == path.pardir:
            raise TemplateNotFound(template)
        elif piece and piece != '.':
            pieces.append(piece)
    return pieces


class BaseLoader(object):
    """Baseclass for all loaders.  Subclass this and override `get_source` to
    implement a custom loading mechanism.  The environment provides a
    `get_template` method that calls the loader's `load` method to get the
    :class:`Template` object.

    A very basic example for a loader that looks up templates on the file
    system could look like this::

        from jinja2 import BaseLoader, TemplateNotFound
        from os.path import join, exists, getmtime

        class MyLoader(BaseLoader):

            def __init__(self, path):
                self.path = path

            def get_source(self, environment, template):
                path = join(self.path, template)
                if not exists(path):
                    raise TemplateNotFound(template)
                mtime = getmtime(path)
                with file(path) as f:
                    source = f.read().decode('utf-8')
                return source, path, lambda: mtime == getmtime(path)
    """

    #: if set to `False` it indicates that the loader cannot provide access
    #: to the source of templates.
    #:
    #: .. versionadded:: 2.4
    has_source_access = True

    def get_source(self, environment, template):
        """Get the template source, filename and reload helper for a template.
        It's passed the environment and template name and has to return a
        tuple in the form ``(source, filename, uptodate)`` or raise a
        `TemplateNotFound` error if it can't locate the template.

        The source part of the returned tuple must be the source of the
        template as unicode string or a ASCII bytestring.  The filename should
        be the name of the file on the filesystem if it was loaded from there,
        otherwise `None`.  The filename is used by python for the tracebacks
        if no loader extension is used.

        The last item in the tuple is the `uptodate` function.  If auto
        reloading is enabled it's always called to check if the template
        changed.  No arguments are passed so the function must store the
        old state somewhere (for example in a closure).  If it returns `False`
        the template will be reloaded.
        """
        if not self.has_source_access:
            raise RuntimeError('%s cannot provide access to the source' %
                               self.__class__.__name__)
        raise TemplateNotFound(template)

    def list_templates(self):
        """Iterates over all templates.  If the loader does not support that
        it should raise a :exc:`TypeError` which is the default behavior.
        """
        raise TypeError('this loader cannot iterate over all templates')

    @internalcode
    def load(self, environment, name, globals=None):
        """Loads a template.  This method looks up the template in the cache
        or loads one by calling :meth:`get_source`.  Subclasses should not
        override this method as loaders working on collections of other
        loaders (such as :class:`PrefixLoader` or :class:`ChoiceLoader`)
        will not call this method but `get_source` directly.
        """
        code = None
        if globals is None:
            globals = {}

        # first we try to get the source for this template together
        # with the filename and the uptodate function.
        source, filename, uptodate = self.get_source(environment, name)

        # try to load the code from the bytecode cache if there is a
        # bytecode cache configured.
        bcc = environment.bytecode_cache
        if bcc is not None:
            bucket = bcc.get_bucket(environment, name, filename, source)
            code = bucket.code

        # if we don't have code so far (not cached, no longer up to
        # date) etc. we compile the template
        if code is None:
            code = environment.compile(source, name, filename)

        # if the bytecode cache is available and the bucket doesn't
        # have a code so far, we give the bucket the new code and put
        # it back to the bytecode cache.
        if bcc is not None and bucket.code is None:
            bucket.code = code
            bcc.set_bucket(bucket)

        return environment.template_class.from_code(environment, code,
                                                    globals, uptodate)


class FileSystemLoader(BaseLoader):
    """Loads templates from the file system.  This loader can find templates
    in folders on the file system and is the preferred way to load them.

    The loader takes the path to the templates as string, or if multiple
    locations are wanted a list of them which is then looked up in the
    given order:

    >>> loader = FileSystemLoader('/path/to/templates')
    >>> loader = FileSystemLoader(['/path/to/templates', '/other/path'])

    Per default the template encoding is ``'utf-8'`` which can be changed
    by setting the `encoding` parameter to something else.
    """

    def __init__(self, searchpath, encoding='utf-8'):
        if isinstance(searchpath, basestring):
            searchpath = [searchpath]
        self.searchpath = list(searchpath)
        self.encoding = encoding

    def get_source(self, environment, template):
        pieces = split_template_path(template)
        for searchpath in self.searchpath:
            filename = path.join(searchpath, *pieces)
            f = open_if_exists(filename)
            if f is None:
                continue
            try:
                contents = f.read().decode(self.encoding)
            finally:
                f.close()

            mtime = path.getmtime(filename)
            def uptodate():
                try:
                    return path.getmtime(filename) == mtime
                except OSError:
                    return False
            return contents, filename, uptodate
        raise TemplateNotFound(template)

    def list_templates(self):
        found = set()
        for searchpath in self.searchpath:
            for dirpath, dirnames, filenames in os.walk(searchpath):
                for filename in filenames:
                    template = os.path.join(dirpath, filename) \
                        [len(searchpath):].strip(os.path.sep) \
                                          .replace(os.path.sep, '/')
                    if template[:2] == './':
                        template = template[2:]
                    if template not in found:
                        found.add(template)
        return sorted(found)


class PackageLoader(BaseLoader):
    """Load templates from python eggs or packages.  It is constructed with
    the name of the python package and the path to the templates in that
    package::

        loader = PackageLoader('mypackage', 'views')

    If the package path is not given, ``'templates'`` is assumed.

    Per default the template encoding is ``'utf-8'`` which can be changed
    by setting the `encoding` parameter to something else.  Due to the nature
    of eggs it's only possible to reload templates if the package was loaded
    from the file system and not a zip file.
    """

    def __init__(self, package_name, package_path='templates',
                 encoding='utf-8'):
        from pkg_resources import DefaultProvider, ResourceManager, \
                                  get_provider
        provider = get_provider(package_name)
        self.encoding = encoding
        self.manager = ResourceManager()
        self.filesystem_bound = isinstance(provider, DefaultProvider)
        self.provider = provider
        self.package_path = package_path

    def get_source(self, environment, template):
        pieces = split_template_path(template)
        p = '/'.join((self.package_path,) + tuple(pieces))
        if not self.provider.has_resource(p):
            raise TemplateNotFound(template)

        filename = uptodate = None
        if self.filesystem_bound:
            filename = self.provider.get_resource_filename(self.manager, p)
            mtime = path.getmtime(filename)
            def uptodate():
                try:
                    return path.getmtime(filename) == mtime
                except OSError:
                    return False

        source = self.provider.get_resource_string(self.manager, p)
        return source.decode(self.encoding), filename, uptodate

    def list_templates(self):
        path = self.package_path
        if path[:2] == './':
            path = path[2:]
        elif path == '.':
            path = ''
        offset = len(path)
        results = []
        def _walk(path):
            for filename in self.provider.resource_listdir(path):
                fullname = path + '/' + filename
                if self.provider.resource_isdir(fullname):
                    for item in _walk(fullname):
                        results.append(item)
                else:
                    results.append(fullname[offset:].lstrip('/'))
        _walk(path)
        results.sort()
        return results


class DictLoader(BaseLoader):
    """Loads a template from a python dict.  It's passed a dict of unicode
    strings bound to template names.  This loader is useful for unittesting:

    >>> loader = DictLoader({'index.html': 'source here'})

    Because auto reloading is rarely useful this is disabled per default.
    """

    def __init__(self, mapping):
        self.mapping = mapping

    def get_source(self, environment, template):
        if template in self.mapping:
            source = self.mapping[template]
            return source, None, lambda: source != self.mapping.get(template)
        raise TemplateNotFound(template)

    def list_templates(self):
        return sorted(self.mapping)


class FunctionLoader(BaseLoader):
    """A loader that is passed a function which does the loading.  The
    function becomes the name of the template passed and has to return either
    an unicode string with the template source, a tuple in the form ``(source,
    filename, uptodatefunc)`` or `None` if the template does not exist.

    >>> def load_template(name):
    ...     if name == 'index.html':
    ...         return '...'
    ...
    >>> loader = FunctionLoader(load_template)

    The `uptodatefunc` is a function that is called if autoreload is enabled
    and has to return `True` if the template is still up to date.  For more
    details have a look at :meth:`BaseLoader.get_source` which has the same
    return value.
    """

    def __init__(self, load_func):
        self.load_func = load_func

    def get_source(self, environment, template):
        rv = self.load_func(template)
        if rv is None:
            raise TemplateNotFound(template)
        elif isinstance(rv, basestring):
            return rv, None, None
        return rv


class PrefixLoader(BaseLoader):
    """A loader that is passed a dict of loaders where each loader is bound
    to a prefix.  The prefix is delimited from the template by a slash per
    default, which can be changed by setting the `delimiter` argument to
    something else::

        loader = PrefixLoader({
            'app1':     PackageLoader('mypackage.app1'),
            'app2':     PackageLoader('mypackage.app2')
        })

    By loading ``'app1/index.html'`` the file from the app1 package is loaded,
    by loading ``'app2/index.html'`` the file from the second.
    """

    def __init__(self, mapping, delimiter='/'):
        self.mapping = mapping
        self.delimiter = delimiter

    def get_source(self, environment, template):
        try:
            prefix, name = template.split(self.delimiter, 1)
            loader = self.mapping[prefix]
        except (ValueError, KeyError):
            raise TemplateNotFound(template)
        try:
            return loader.get_source(environment, name)
        except TemplateNotFound:
            # re-raise the exception with the correct fileame here.
            # (the one that includes the prefix)
            raise TemplateNotFound(template)

    def list_templates(self):
        result = []
        for prefix, loader in self.mapping.iteritems():
            for template in loader.list_templates():
                result.append(prefix + self.delimiter + template)
        return result


class ChoiceLoader(BaseLoader):
    """This loader works like the `PrefixLoader` just that no prefix is
    specified.  If a template could not be found by one loader the next one
    is tried.

    >>> loader = ChoiceLoader([
    ...     FileSystemLoader('/path/to/user/templates'),
    ...     FileSystemLoader('/path/to/system/templates')
    ... ])

    This is useful if you want to allow users to override builtin templates
    from a different location.
    """

    def __init__(self, loaders):
        self.loaders = loaders

    def get_source(self, environment, template):
        for loader in self.loaders:
            try:
                return loader.get_source(environment, template)
            except TemplateNotFound:
                pass
        raise TemplateNotFound(template)

    def list_templates(self):
        found = set()
        for loader in self.loaders:
            found.update(loader.list_templates())
        return sorted(found)


class _TemplateModule(ModuleType):
    """Like a normal module but with support for weak references"""


class ModuleLoader(BaseLoader):
    """This loader loads templates from precompiled templates.

    Example usage:

    >>> loader = ChoiceLoader([
    ...     ModuleLoader('/path/to/compiled/templates'),
    ...     FileSystemLoader('/path/to/templates')
    ... ])

    Templates can be precompiled with :meth:`Environment.compile_templates`.
    """

    has_source_access = False

    def __init__(self, path):
        package_name = '_jinja2_module_templates_%x' % id(self)

        # create a fake module that looks for the templates in the
        # path given.
        mod = _TemplateModule(package_name)
        if isinstance(path, basestring):
            path = [path]
        else:
            path = list(path)
        mod.__path__ = path

        sys.modules[package_name] = weakref.proxy(mod,
            lambda x: sys.modules.pop(package_name, None))

        # the only strong reference, the sys.modules entry is weak
        # so that the garbage collector can remove it once the
        # loader that created it goes out of business.
        self.module = mod
        self.package_name = package_name

    @staticmethod
    def get_template_key(name):
        return 'tmpl_' + sha1(name.encode('utf-8')).hexdigest()

    @staticmethod
    def get_module_filename(name):
        return ModuleLoader.get_template_key(name) + '.py'

    @internalcode
    def load(self, environment, name, globals=None):
        key = self.get_template_key(name)
        module = '%s.%s' % (self.package_name, key)
        mod = getattr(self.module, module, None)
        if mod is None:
            try:
                mod = __import__(module, None, None, ['root'])
            except ImportError:
                raise TemplateNotFound(name)

            # remove the entry from sys.modules, we only want the attribute
            # on the module object we have stored on the loader.
            sys.modules.pop(module, None)

        return environment.template_class.from_module_dict(
            environment, mod.__dict__, globals)

########NEW FILE########
__FILENAME__ = meta
# -*- coding: utf-8 -*-
"""
    jinja2.meta
    ~~~~~~~~~~~

    This module implements various functions that exposes information about
    templates that might be interesting for various kinds of applications.

    :copyright: (c) 2010 by the Jinja Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from jinja2 import nodes
from jinja2.compiler import CodeGenerator


class TrackingCodeGenerator(CodeGenerator):
    """We abuse the code generator for introspection."""

    def __init__(self, environment):
        CodeGenerator.__init__(self, environment, '<introspection>',
                               '<introspection>')
        self.undeclared_identifiers = set()

    def write(self, x):
        """Don't write."""

    def pull_locals(self, frame):
        """Remember all undeclared identifiers."""
        self.undeclared_identifiers.update(frame.identifiers.undeclared)


def find_undeclared_variables(ast):
    """Returns a set of all variables in the AST that will be looked up from
    the context at runtime.  Because at compile time it's not known which
    variables will be used depending on the path the execution takes at
    runtime, all variables are returned.

    >>> from jinja2 import Environment, meta
    >>> env = Environment()
    >>> ast = env.parse('{% set foo = 42 %}{{ bar + foo }}')
    >>> meta.find_undeclared_variables(ast)
    set(['bar'])

    .. admonition:: Implementation

       Internally the code generator is used for finding undeclared variables.
       This is good to know because the code generator might raise a
       :exc:`TemplateAssertionError` during compilation and as a matter of
       fact this function can currently raise that exception as well.
    """
    codegen = TrackingCodeGenerator(ast.environment)
    codegen.visit(ast)
    return codegen.undeclared_identifiers


def find_referenced_templates(ast):
    """Finds all the referenced templates from the AST.  This will return an
    iterator over all the hardcoded template extensions, inclusions and
    imports.  If dynamic inheritance or inclusion is used, `None` will be
    yielded.

    >>> from jinja2 import Environment, meta
    >>> env = Environment()
    >>> ast = env.parse('{% extends "layout.html" %}{% include helper %}')
    >>> list(meta.find_referenced_templates(ast))
    ['layout.html', None]

    This function is useful for dependency tracking.  For example if you want
    to rebuild parts of the website after a layout template has changed.
    """
    for node in ast.find_all((nodes.Extends, nodes.FromImport, nodes.Import,
                              nodes.Include)):
        if not isinstance(node.template, nodes.Const):
            # a tuple with some non consts in there
            if isinstance(node.template, (nodes.Tuple, nodes.List)):
                for template_name in node.template.items:
                    # something const, only yield the strings and ignore
                    # non-string consts that really just make no sense
                    if isinstance(template_name, nodes.Const):
                        if isinstance(template_name.value, basestring):
                            yield template_name.value
                    # something dynamic in there
                    else:
                        yield None
            # something dynamic we don't know about here
            else:
                yield None
            continue
        # constant is a basestring, direct template name
        if isinstance(node.template.value, basestring):
            yield node.template.value
        # a tuple or list (latter *should* not happen) made of consts,
        # yield the consts that are strings.  We could warn here for
        # non string values
        elif isinstance(node, nodes.Include) and \
             isinstance(node.template.value, (tuple, list)):
            for template_name in node.template.value:
                if isinstance(template_name, basestring):
                    yield template_name
        # something else we don't care about, we could warn here
        else:
            yield None

########NEW FILE########
__FILENAME__ = nodes
# -*- coding: utf-8 -*-
"""
    jinja2.nodes
    ~~~~~~~~~~~~

    This module implements additional nodes derived from the ast base node.

    It also provides some node tree helper functions like `in_lineno` and
    `get_nodes` used by the parser and translator in order to normalize
    python and jinja nodes.

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD, see LICENSE for more details.
"""
import operator
from itertools import chain, izip
from collections import deque
from jinja2.utils import Markup, MethodType, FunctionType


#: the types we support for context functions
_context_function_types = (FunctionType, MethodType)


_binop_to_func = {
    '*':        operator.mul,
    '/':        operator.truediv,
    '//':       operator.floordiv,
    '**':       operator.pow,
    '%':        operator.mod,
    '+':        operator.add,
    '-':        operator.sub
}

_uaop_to_func = {
    'not':      operator.not_,
    '+':        operator.pos,
    '-':        operator.neg
}

_cmpop_to_func = {
    'eq':       operator.eq,
    'ne':       operator.ne,
    'gt':       operator.gt,
    'gteq':     operator.ge,
    'lt':       operator.lt,
    'lteq':     operator.le,
    'in':       lambda a, b: a in b,
    'notin':    lambda a, b: a not in b
}


class Impossible(Exception):
    """Raised if the node could not perform a requested action."""


class NodeType(type):
    """A metaclass for nodes that handles the field and attribute
    inheritance.  fields and attributes from the parent class are
    automatically forwarded to the child."""

    def __new__(cls, name, bases, d):
        for attr in 'fields', 'attributes':
            storage = []
            storage.extend(getattr(bases[0], attr, ()))
            storage.extend(d.get(attr, ()))
            assert len(bases) == 1, 'multiple inheritance not allowed'
            assert len(storage) == len(set(storage)), 'layout conflict'
            d[attr] = tuple(storage)
        d.setdefault('abstract', False)
        return type.__new__(cls, name, bases, d)


class EvalContext(object):
    """Holds evaluation time information.  Custom attributes can be attached
    to it in extensions.
    """

    def __init__(self, environment, template_name=None):
        self.environment = environment
        if callable(environment.autoescape):
            self.autoescape = environment.autoescape(template_name)
        else:
            self.autoescape = environment.autoescape
        self.volatile = False

    def save(self):
        return self.__dict__.copy()

    def revert(self, old):
        self.__dict__.clear()
        self.__dict__.update(old)


def get_eval_context(node, ctx):
    if ctx is None:
        if node.environment is None:
            raise RuntimeError('if no eval context is passed, the '
                               'node must have an attached '
                               'environment.')
        return EvalContext(node.environment)
    return ctx


class Node(object):
    """Baseclass for all Jinja2 nodes.  There are a number of nodes available
    of different types.  There are three major types:

    -   :class:`Stmt`: statements
    -   :class:`Expr`: expressions
    -   :class:`Helper`: helper nodes
    -   :class:`Template`: the outermost wrapper node

    All nodes have fields and attributes.  Fields may be other nodes, lists,
    or arbitrary values.  Fields are passed to the constructor as regular
    positional arguments, attributes as keyword arguments.  Each node has
    two attributes: `lineno` (the line number of the node) and `environment`.
    The `environment` attribute is set at the end of the parsing process for
    all nodes automatically.
    """
    __metaclass__ = NodeType
    fields = ()
    attributes = ('lineno', 'environment')
    abstract = True

    def __init__(self, *fields, **attributes):
        if self.abstract:
            raise TypeError('abstract nodes are not instanciable')
        if fields:
            if len(fields) != len(self.fields):
                if not self.fields:
                    raise TypeError('%r takes 0 arguments' %
                                    self.__class__.__name__)
                raise TypeError('%r takes 0 or %d argument%s' % (
                    self.__class__.__name__,
                    len(self.fields),
                    len(self.fields) != 1 and 's' or ''
                ))
            for name, arg in izip(self.fields, fields):
                setattr(self, name, arg)
        for attr in self.attributes:
            setattr(self, attr, attributes.pop(attr, None))
        if attributes:
            raise TypeError('unknown attribute %r' %
                            iter(attributes).next())

    def iter_fields(self, exclude=None, only=None):
        """This method iterates over all fields that are defined and yields
        ``(key, value)`` tuples.  Per default all fields are returned, but
        it's possible to limit that to some fields by providing the `only`
        parameter or to exclude some using the `exclude` parameter.  Both
        should be sets or tuples of field names.
        """
        for name in self.fields:
            if (exclude is only is None) or \
               (exclude is not None and name not in exclude) or \
               (only is not None and name in only):
                try:
                    yield name, getattr(self, name)
                except AttributeError:
                    pass

    def iter_child_nodes(self, exclude=None, only=None):
        """Iterates over all direct child nodes of the node.  This iterates
        over all fields and yields the values of they are nodes.  If the value
        of a field is a list all the nodes in that list are returned.
        """
        for field, item in self.iter_fields(exclude, only):
            if isinstance(item, list):
                for n in item:
                    if isinstance(n, Node):
                        yield n
            elif isinstance(item, Node):
                yield item

    def find(self, node_type):
        """Find the first node of a given type.  If no such node exists the
        return value is `None`.
        """
        for result in self.find_all(node_type):
            return result

    def find_all(self, node_type):
        """Find all the nodes of a given type.  If the type is a tuple,
        the check is performed for any of the tuple items.
        """
        for child in self.iter_child_nodes():
            if isinstance(child, node_type):
                yield child
            for result in child.find_all(node_type):
                yield result

    def set_ctx(self, ctx):
        """Reset the context of a node and all child nodes.  Per default the
        parser will all generate nodes that have a 'load' context as it's the
        most common one.  This method is used in the parser to set assignment
        targets and other nodes to a store context.
        """
        todo = deque([self])
        while todo:
            node = todo.popleft()
            if 'ctx' in node.fields:
                node.ctx = ctx
            todo.extend(node.iter_child_nodes())
        return self

    def set_lineno(self, lineno, override=False):
        """Set the line numbers of the node and children."""
        todo = deque([self])
        while todo:
            node = todo.popleft()
            if 'lineno' in node.attributes:
                if node.lineno is None or override:
                    node.lineno = lineno
            todo.extend(node.iter_child_nodes())
        return self

    def set_environment(self, environment):
        """Set the environment for all nodes."""
        todo = deque([self])
        while todo:
            node = todo.popleft()
            node.environment = environment
            todo.extend(node.iter_child_nodes())
        return self

    def __eq__(self, other):
        return type(self) is type(other) and \
               tuple(self.iter_fields()) == tuple(other.iter_fields())

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return '%s(%s)' % (
            self.__class__.__name__,
            ', '.join('%s=%r' % (arg, getattr(self, arg, None)) for
                      arg in self.fields)
        )


class Stmt(Node):
    """Base node for all statements."""
    abstract = True


class Helper(Node):
    """Nodes that exist in a specific context only."""
    abstract = True


class Template(Node):
    """Node that represents a template.  This must be the outermost node that
    is passed to the compiler.
    """
    fields = ('body',)


class Output(Stmt):
    """A node that holds multiple expressions which are then printed out.
    This is used both for the `print` statement and the regular template data.
    """
    fields = ('nodes',)


class Extends(Stmt):
    """Represents an extends statement."""
    fields = ('template',)


class For(Stmt):
    """The for loop.  `target` is the target for the iteration (usually a
    :class:`Name` or :class:`Tuple`), `iter` the iterable.  `body` is a list
    of nodes that are used as loop-body, and `else_` a list of nodes for the
    `else` block.  If no else node exists it has to be an empty list.

    For filtered nodes an expression can be stored as `test`, otherwise `None`.
    """
    fields = ('target', 'iter', 'body', 'else_', 'test', 'recursive')


class If(Stmt):
    """If `test` is true, `body` is rendered, else `else_`."""
    fields = ('test', 'body', 'else_')


class Macro(Stmt):
    """A macro definition.  `name` is the name of the macro, `args` a list of
    arguments and `defaults` a list of defaults if there are any.  `body` is
    a list of nodes for the macro body.
    """
    fields = ('name', 'args', 'defaults', 'body')


class CallBlock(Stmt):
    """Like a macro without a name but a call instead.  `call` is called with
    the unnamed macro as `caller` argument this node holds.
    """
    fields = ('call', 'args', 'defaults', 'body')


class FilterBlock(Stmt):
    """Node for filter sections."""
    fields = ('body', 'filter')


class Block(Stmt):
    """A node that represents a block."""
    fields = ('name', 'body', 'scoped')


class Include(Stmt):
    """A node that represents the include tag."""
    fields = ('template', 'with_context', 'ignore_missing')


class Import(Stmt):
    """A node that represents the import tag."""
    fields = ('template', 'target', 'with_context')


class FromImport(Stmt):
    """A node that represents the from import tag.  It's important to not
    pass unsafe names to the name attribute.  The compiler translates the
    attribute lookups directly into getattr calls and does *not* use the
    subscript callback of the interface.  As exported variables may not
    start with double underscores (which the parser asserts) this is not a
    problem for regular Jinja code, but if this node is used in an extension
    extra care must be taken.

    The list of names may contain tuples if aliases are wanted.
    """
    fields = ('template', 'names', 'with_context')


class ExprStmt(Stmt):
    """A statement that evaluates an expression and discards the result."""
    fields = ('node',)


class Assign(Stmt):
    """Assigns an expression to a target."""
    fields = ('target', 'node')


class Expr(Node):
    """Baseclass for all expressions."""
    abstract = True

    def as_const(self, eval_ctx=None):
        """Return the value of the expression as constant or raise
        :exc:`Impossible` if this was not possible.

        An :class:`EvalContext` can be provided, if none is given
        a default context is created which requires the nodes to have
        an attached environment.

        .. versionchanged:: 2.4
           the `eval_ctx` parameter was added.
        """
        raise Impossible()

    def can_assign(self):
        """Check if it's possible to assign something to this node."""
        return False


class BinExpr(Expr):
    """Baseclass for all binary expressions."""
    fields = ('left', 'right')
    operator = None
    abstract = True

    def as_const(self, eval_ctx=None):
        eval_ctx = get_eval_context(self, eval_ctx)
        # intercepted operators cannot be folded at compile time
        if self.environment.sandboxed and \
           self.operator in self.environment.intercepted_binops:
            raise Impossible()
        f = _binop_to_func[self.operator]
        try:
            return f(self.left.as_const(eval_ctx), self.right.as_const(eval_ctx))
        except Exception:
            raise Impossible()


class UnaryExpr(Expr):
    """Baseclass for all unary expressions."""
    fields = ('node',)
    operator = None
    abstract = True

    def as_const(self, eval_ctx=None):
        eval_ctx = get_eval_context(self, eval_ctx)
        # intercepted operators cannot be folded at compile time
        if self.environment.sandboxed and \
           self.operator in self.environment.intercepted_unops:
            raise Impossible()
        f = _uaop_to_func[self.operator]
        try:
            return f(self.node.as_const(eval_ctx))
        except Exception:
            raise Impossible()


class Name(Expr):
    """Looks up a name or stores a value in a name.
    The `ctx` of the node can be one of the following values:

    -   `store`: store a value in the name
    -   `load`: load that name
    -   `param`: like `store` but if the name was defined as function parameter.
    """
    fields = ('name', 'ctx')

    def can_assign(self):
        return self.name not in ('true', 'false', 'none',
                                 'True', 'False', 'None')


class Literal(Expr):
    """Baseclass for literals."""
    abstract = True


class Const(Literal):
    """All constant values.  The parser will return this node for simple
    constants such as ``42`` or ``"foo"`` but it can be used to store more
    complex values such as lists too.  Only constants with a safe
    representation (objects where ``eval(repr(x)) == x`` is true).
    """
    fields = ('value',)

    def as_const(self, eval_ctx=None):
        return self.value

    @classmethod
    def from_untrusted(cls, value, lineno=None, environment=None):
        """Return a const object if the value is representable as
        constant value in the generated code, otherwise it will raise
        an `Impossible` exception.
        """
        from compiler import has_safe_repr
        if not has_safe_repr(value):
            raise Impossible()
        return cls(value, lineno=lineno, environment=environment)


class TemplateData(Literal):
    """A constant template string."""
    fields = ('data',)

    def as_const(self, eval_ctx=None):
        eval_ctx = get_eval_context(self, eval_ctx)
        if eval_ctx.volatile:
            raise Impossible()
        if eval_ctx.autoescape:
            return Markup(self.data)
        return self.data


class Tuple(Literal):
    """For loop unpacking and some other things like multiple arguments
    for subscripts.  Like for :class:`Name` `ctx` specifies if the tuple
    is used for loading the names or storing.
    """
    fields = ('items', 'ctx')

    def as_const(self, eval_ctx=None):
        eval_ctx = get_eval_context(self, eval_ctx)
        return tuple(x.as_const(eval_ctx) for x in self.items)

    def can_assign(self):
        for item in self.items:
            if not item.can_assign():
                return False
        return True


class List(Literal):
    """Any list literal such as ``[1, 2, 3]``"""
    fields = ('items',)

    def as_const(self, eval_ctx=None):
        eval_ctx = get_eval_context(self, eval_ctx)
        return [x.as_const(eval_ctx) for x in self.items]


class Dict(Literal):
    """Any dict literal such as ``{1: 2, 3: 4}``.  The items must be a list of
    :class:`Pair` nodes.
    """
    fields = ('items',)

    def as_const(self, eval_ctx=None):
        eval_ctx = get_eval_context(self, eval_ctx)
        return dict(x.as_const(eval_ctx) for x in self.items)


class Pair(Helper):
    """A key, value pair for dicts."""
    fields = ('key', 'value')

    def as_const(self, eval_ctx=None):
        eval_ctx = get_eval_context(self, eval_ctx)
        return self.key.as_const(eval_ctx), self.value.as_const(eval_ctx)


class Keyword(Helper):
    """A key, value pair for keyword arguments where key is a string."""
    fields = ('key', 'value')

    def as_const(self, eval_ctx=None):
        eval_ctx = get_eval_context(self, eval_ctx)
        return self.key, self.value.as_const(eval_ctx)


class CondExpr(Expr):
    """A conditional expression (inline if expression).  (``{{
    foo if bar else baz }}``)
    """
    fields = ('test', 'expr1', 'expr2')

    def as_const(self, eval_ctx=None):
        eval_ctx = get_eval_context(self, eval_ctx)
        if self.test.as_const(eval_ctx):
            return self.expr1.as_const(eval_ctx)

        # if we evaluate to an undefined object, we better do that at runtime
        if self.expr2 is None:
            raise Impossible()

        return self.expr2.as_const(eval_ctx)


class Filter(Expr):
    """This node applies a filter on an expression.  `name` is the name of
    the filter, the rest of the fields are the same as for :class:`Call`.

    If the `node` of a filter is `None` the contents of the last buffer are
    filtered.  Buffers are created by macros and filter blocks.
    """
    fields = ('node', 'name', 'args', 'kwargs', 'dyn_args', 'dyn_kwargs')

    def as_const(self, eval_ctx=None):
        eval_ctx = get_eval_context(self, eval_ctx)
        if eval_ctx.volatile or self.node is None:
            raise Impossible()
        # we have to be careful here because we call filter_ below.
        # if this variable would be called filter, 2to3 would wrap the
        # call in a list beause it is assuming we are talking about the
        # builtin filter function here which no longer returns a list in
        # python 3.  because of that, do not rename filter_ to filter!
        filter_ = self.environment.filters.get(self.name)
        if filter_ is None or getattr(filter_, 'contextfilter', False):
            raise Impossible()
        obj = self.node.as_const(eval_ctx)
        args = [x.as_const(eval_ctx) for x in self.args]
        if getattr(filter_, 'evalcontextfilter', False):
            args.insert(0, eval_ctx)
        elif getattr(filter_, 'environmentfilter', False):
            args.insert(0, self.environment)
        kwargs = dict(x.as_const(eval_ctx) for x in self.kwargs)
        if self.dyn_args is not None:
            try:
                args.extend(self.dyn_args.as_const(eval_ctx))
            except Exception:
                raise Impossible()
        if self.dyn_kwargs is not None:
            try:
                kwargs.update(self.dyn_kwargs.as_const(eval_ctx))
            except Exception:
                raise Impossible()
        try:
            return filter_(obj, *args, **kwargs)
        except Exception:
            raise Impossible()


class Test(Expr):
    """Applies a test on an expression.  `name` is the name of the test, the
    rest of the fields are the same as for :class:`Call`.
    """
    fields = ('node', 'name', 'args', 'kwargs', 'dyn_args', 'dyn_kwargs')


class Call(Expr):
    """Calls an expression.  `args` is a list of arguments, `kwargs` a list
    of keyword arguments (list of :class:`Keyword` nodes), and `dyn_args`
    and `dyn_kwargs` has to be either `None` or a node that is used as
    node for dynamic positional (``*args``) or keyword (``**kwargs``)
    arguments.
    """
    fields = ('node', 'args', 'kwargs', 'dyn_args', 'dyn_kwargs')

    def as_const(self, eval_ctx=None):
        eval_ctx = get_eval_context(self, eval_ctx)
        if eval_ctx.volatile:
            raise Impossible()
        obj = self.node.as_const(eval_ctx)

        # don't evaluate context functions
        args = [x.as_const(eval_ctx) for x in self.args]
        if isinstance(obj, _context_function_types):
            if getattr(obj, 'contextfunction', False):
                raise Impossible()
            elif getattr(obj, 'evalcontextfunction', False):
                args.insert(0, eval_ctx)
            elif getattr(obj, 'environmentfunction', False):
                args.insert(0, self.environment)

        kwargs = dict(x.as_const(eval_ctx) for x in self.kwargs)
        if self.dyn_args is not None:
            try:
                args.extend(self.dyn_args.as_const(eval_ctx))
            except Exception:
                raise Impossible()
        if self.dyn_kwargs is not None:
            try:
                kwargs.update(self.dyn_kwargs.as_const(eval_ctx))
            except Exception:
                raise Impossible()
        try:
            return obj(*args, **kwargs)
        except Exception:
            raise Impossible()


class Getitem(Expr):
    """Get an attribute or item from an expression and prefer the item."""
    fields = ('node', 'arg', 'ctx')

    def as_const(self, eval_ctx=None):
        eval_ctx = get_eval_context(self, eval_ctx)
        if self.ctx != 'load':
            raise Impossible()
        try:
            return self.environment.getitem(self.node.as_const(eval_ctx),
                                            self.arg.as_const(eval_ctx))
        except Exception:
            raise Impossible()

    def can_assign(self):
        return False


class Getattr(Expr):
    """Get an attribute or item from an expression that is a ascii-only
    bytestring and prefer the attribute.
    """
    fields = ('node', 'attr', 'ctx')

    def as_const(self, eval_ctx=None):
        if self.ctx != 'load':
            raise Impossible()
        try:
            eval_ctx = get_eval_context(self, eval_ctx)
            return self.environment.getattr(self.node.as_const(eval_ctx),
                                            self.attr)
        except Exception:
            raise Impossible()

    def can_assign(self):
        return False


class Slice(Expr):
    """Represents a slice object.  This must only be used as argument for
    :class:`Subscript`.
    """
    fields = ('start', 'stop', 'step')

    def as_const(self, eval_ctx=None):
        eval_ctx = get_eval_context(self, eval_ctx)
        def const(obj):
            if obj is None:
                return None
            return obj.as_const(eval_ctx)
        return slice(const(self.start), const(self.stop), const(self.step))


class Concat(Expr):
    """Concatenates the list of expressions provided after converting them to
    unicode.
    """
    fields = ('nodes',)

    def as_const(self, eval_ctx=None):
        eval_ctx = get_eval_context(self, eval_ctx)
        return ''.join(unicode(x.as_const(eval_ctx)) for x in self.nodes)


class Compare(Expr):
    """Compares an expression with some other expressions.  `ops` must be a
    list of :class:`Operand`\s.
    """
    fields = ('expr', 'ops')

    def as_const(self, eval_ctx=None):
        eval_ctx = get_eval_context(self, eval_ctx)
        result = value = self.expr.as_const(eval_ctx)
        try:
            for op in self.ops:
                new_value = op.expr.as_const(eval_ctx)
                result = _cmpop_to_func[op.op](value, new_value)
                value = new_value
        except Exception:
            raise Impossible()
        return result


class Operand(Helper):
    """Holds an operator and an expression."""
    fields = ('op', 'expr')

if __debug__:
    Operand.__doc__ += '\nThe following operators are available: ' + \
        ', '.join(sorted('``%s``' % x for x in set(_binop_to_func) |
                  set(_uaop_to_func) | set(_cmpop_to_func)))


class Mul(BinExpr):
    """Multiplies the left with the right node."""
    operator = '*'


class Div(BinExpr):
    """Divides the left by the right node."""
    operator = '/'


class FloorDiv(BinExpr):
    """Divides the left by the right node and truncates conver the
    result into an integer by truncating.
    """
    operator = '//'


class Add(BinExpr):
    """Add the left to the right node."""
    operator = '+'


class Sub(BinExpr):
    """Substract the right from the left node."""
    operator = '-'


class Mod(BinExpr):
    """Left modulo right."""
    operator = '%'


class Pow(BinExpr):
    """Left to the power of right."""
    operator = '**'


class And(BinExpr):
    """Short circuited AND."""
    operator = 'and'

    def as_const(self, eval_ctx=None):
        eval_ctx = get_eval_context(self, eval_ctx)
        return self.left.as_const(eval_ctx) and self.right.as_const(eval_ctx)


class Or(BinExpr):
    """Short circuited OR."""
    operator = 'or'

    def as_const(self, eval_ctx=None):
        eval_ctx = get_eval_context(self, eval_ctx)
        return self.left.as_const(eval_ctx) or self.right.as_const(eval_ctx)


class Not(UnaryExpr):
    """Negate the expression."""
    operator = 'not'


class Neg(UnaryExpr):
    """Make the expression negative."""
    operator = '-'


class Pos(UnaryExpr):
    """Make the expression positive (noop for most expressions)"""
    operator = '+'


# Helpers for extensions


class EnvironmentAttribute(Expr):
    """Loads an attribute from the environment object.  This is useful for
    extensions that want to call a callback stored on the environment.
    """
    fields = ('name',)


class ExtensionAttribute(Expr):
    """Returns the attribute of an extension bound to the environment.
    The identifier is the identifier of the :class:`Extension`.

    This node is usually constructed by calling the
    :meth:`~jinja2.ext.Extension.attr` method on an extension.
    """
    fields = ('identifier', 'name')


class ImportedName(Expr):
    """If created with an import name the import name is returned on node
    access.  For example ``ImportedName('cgi.escape')`` returns the `escape`
    function from the cgi module on evaluation.  Imports are optimized by the
    compiler so there is no need to assign them to local variables.
    """
    fields = ('importname',)


class InternalName(Expr):
    """An internal name in the compiler.  You cannot create these nodes
    yourself but the parser provides a
    :meth:`~jinja2.parser.Parser.free_identifier` method that creates
    a new identifier for you.  This identifier is not available from the
    template and is not threated specially by the compiler.
    """
    fields = ('name',)

    def __init__(self):
        raise TypeError('Can\'t create internal names.  Use the '
                        '`free_identifier` method on a parser.')


class MarkSafe(Expr):
    """Mark the wrapped expression as safe (wrap it as `Markup`)."""
    fields = ('expr',)

    def as_const(self, eval_ctx=None):
        eval_ctx = get_eval_context(self, eval_ctx)
        return Markup(self.expr.as_const(eval_ctx))


class MarkSafeIfAutoescape(Expr):
    """Mark the wrapped expression as safe (wrap it as `Markup`) but
    only if autoescaping is active.

    .. versionadded:: 2.5
    """
    fields = ('expr',)

    def as_const(self, eval_ctx=None):
        eval_ctx = get_eval_context(self, eval_ctx)
        if eval_ctx.volatile:
            raise Impossible()
        expr = self.expr.as_const(eval_ctx)
        if eval_ctx.autoescape:
            return Markup(expr)
        return expr


class ContextReference(Expr):
    """Returns the current template context.  It can be used like a
    :class:`Name` node, with a ``'load'`` ctx and will return the
    current :class:`~jinja2.runtime.Context` object.

    Here an example that assigns the current template name to a
    variable named `foo`::

        Assign(Name('foo', ctx='store'),
               Getattr(ContextReference(), 'name'))
    """


class Continue(Stmt):
    """Continue a loop."""


class Break(Stmt):
    """Break a loop."""


class Scope(Stmt):
    """An artificial scope."""
    fields = ('body',)


class EvalContextModifier(Stmt):
    """Modifies the eval context.  For each option that should be modified,
    a :class:`Keyword` has to be added to the :attr:`options` list.

    Example to change the `autoescape` setting::

        EvalContextModifier(options=[Keyword('autoescape', Const(True))])
    """
    fields = ('options',)


class ScopedEvalContextModifier(EvalContextModifier):
    """Modifies the eval context and reverts it later.  Works exactly like
    :class:`EvalContextModifier` but will only modify the
    :class:`~jinja2.nodes.EvalContext` for nodes in the :attr:`body`.
    """
    fields = ('body',)


# make sure nobody creates custom nodes
def _failing_new(*args, **kwargs):
    raise TypeError('can\'t create custom node types')
NodeType.__new__ = staticmethod(_failing_new); del _failing_new

########NEW FILE########
__FILENAME__ = optimizer
# -*- coding: utf-8 -*-
"""
    jinja2.optimizer
    ~~~~~~~~~~~~~~~~

    The jinja optimizer is currently trying to constant fold a few expressions
    and modify the AST in place so that it should be easier to evaluate it.

    Because the AST does not contain all the scoping information and the
    compiler has to find that out, we cannot do all the optimizations we
    want.  For example loop unrolling doesn't work because unrolled loops would
    have a different scoping.

    The solution would be a second syntax tree that has the scoping rules stored.

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD.
"""
from jinja2 import nodes
from jinja2.visitor import NodeTransformer


def optimize(node, environment):
    """The context hint can be used to perform an static optimization
    based on the context given."""
    optimizer = Optimizer(environment)
    return optimizer.visit(node)


class Optimizer(NodeTransformer):

    def __init__(self, environment):
        self.environment = environment

    def visit_If(self, node):
        """Eliminate dead code."""
        # do not optimize ifs that have a block inside so that it doesn't
        # break super().
        if node.find(nodes.Block) is not None:
            return self.generic_visit(node)
        try:
            val = self.visit(node.test).as_const()
        except nodes.Impossible:
            return self.generic_visit(node)
        if val:
            body = node.body
        else:
            body = node.else_
        result = []
        for node in body:
            result.extend(self.visit_list(node))
        return result

    def fold(self, node):
        """Do constant folding."""
        node = self.generic_visit(node)
        try:
            return nodes.Const.from_untrusted(node.as_const(),
                                              lineno=node.lineno,
                                              environment=self.environment)
        except nodes.Impossible:
            return node

    visit_Add = visit_Sub = visit_Mul = visit_Div = visit_FloorDiv = \
    visit_Pow = visit_Mod = visit_And = visit_Or = visit_Pos = visit_Neg = \
    visit_Not = visit_Compare = visit_Getitem = visit_Getattr = visit_Call = \
    visit_Filter = visit_Test = visit_CondExpr = fold
    del fold

########NEW FILE########
__FILENAME__ = parser
# -*- coding: utf-8 -*-
"""
    jinja2.parser
    ~~~~~~~~~~~~~

    Implements the template parser.

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD, see LICENSE for more details.
"""
from jinja2 import nodes
from jinja2.exceptions import TemplateSyntaxError, TemplateAssertionError
from jinja2.utils import next
from jinja2.lexer import describe_token, describe_token_expr


#: statements that callinto 
_statement_keywords = frozenset(['for', 'if', 'block', 'extends', 'print',
                                 'macro', 'include', 'from', 'import',
                                 'set'])
_compare_operators = frozenset(['eq', 'ne', 'lt', 'lteq', 'gt', 'gteq'])


class Parser(object):
    """This is the central parsing class Jinja2 uses.  It's passed to
    extensions and can be used to parse expressions or statements.
    """

    def __init__(self, environment, source, name=None, filename=None,
                 state=None):
        self.environment = environment
        self.stream = environment._tokenize(source, name, filename, state)
        self.name = name
        self.filename = filename
        self.closed = False
        self.extensions = {}
        for extension in environment.iter_extensions():
            for tag in extension.tags:
                self.extensions[tag] = extension.parse
        self._last_identifier = 0
        self._tag_stack = []
        self._end_token_stack = []

    def fail(self, msg, lineno=None, exc=TemplateSyntaxError):
        """Convenience method that raises `exc` with the message, passed
        line number or last line number as well as the current name and
        filename.
        """
        if lineno is None:
            lineno = self.stream.current.lineno
        raise exc(msg, lineno, self.name, self.filename)

    def _fail_ut_eof(self, name, end_token_stack, lineno):
        expected = []
        for exprs in end_token_stack:
            expected.extend(map(describe_token_expr, exprs))
        if end_token_stack:
            currently_looking = ' or '.join(
                "'%s'" % describe_token_expr(expr)
                for expr in end_token_stack[-1])
        else:
            currently_looking = None

        if name is None:
            message = ['Unexpected end of template.']
        else:
            message = ['Encountered unknown tag \'%s\'.' % name]

        if currently_looking:
            if name is not None and name in expected:
                message.append('You probably made a nesting mistake. Jinja '
                               'is expecting this tag, but currently looking '
                               'for %s.' % currently_looking)
            else:
                message.append('Jinja was looking for the following tags: '
                               '%s.' % currently_looking)

        if self._tag_stack:
            message.append('The innermost block that needs to be '
                           'closed is \'%s\'.' % self._tag_stack[-1])

        self.fail(' '.join(message), lineno)

    def fail_unknown_tag(self, name, lineno=None):
        """Called if the parser encounters an unknown tag.  Tries to fail
        with a human readable error message that could help to identify
        the problem.
        """
        return self._fail_ut_eof(name, self._end_token_stack, lineno)

    def fail_eof(self, end_tokens=None, lineno=None):
        """Like fail_unknown_tag but for end of template situations."""
        stack = list(self._end_token_stack)
        if end_tokens is not None:
            stack.append(end_tokens)
        return self._fail_ut_eof(None, stack, lineno)

    def is_tuple_end(self, extra_end_rules=None):
        """Are we at the end of a tuple?"""
        if self.stream.current.type in ('variable_end', 'block_end', 'rparen'):
            return True
        elif extra_end_rules is not None:
            return self.stream.current.test_any(extra_end_rules)
        return False

    def free_identifier(self, lineno=None):
        """Return a new free identifier as :class:`~jinja2.nodes.InternalName`."""
        self._last_identifier += 1
        rv = object.__new__(nodes.InternalName)
        nodes.Node.__init__(rv, 'fi%d' % self._last_identifier, lineno=lineno)
        return rv

    def parse_statement(self):
        """Parse a single statement."""
        token = self.stream.current
        if token.type != 'name':
            self.fail('tag name expected', token.lineno)
        self._tag_stack.append(token.value)
        pop_tag = True
        try:
            if token.value in _statement_keywords:
                return getattr(self, 'parse_' + self.stream.current.value)()
            if token.value == 'call':
                return self.parse_call_block()
            if token.value == 'filter':
                return self.parse_filter_block()
            ext = self.extensions.get(token.value)
            if ext is not None:
                return ext(self)

            # did not work out, remove the token we pushed by accident
            # from the stack so that the unknown tag fail function can
            # produce a proper error message.
            self._tag_stack.pop()
            pop_tag = False
            self.fail_unknown_tag(token.value, token.lineno)
        finally:
            if pop_tag:
                self._tag_stack.pop()

    def parse_statements(self, end_tokens, drop_needle=False):
        """Parse multiple statements into a list until one of the end tokens
        is reached.  This is used to parse the body of statements as it also
        parses template data if appropriate.  The parser checks first if the
        current token is a colon and skips it if there is one.  Then it checks
        for the block end and parses until if one of the `end_tokens` is
        reached.  Per default the active token in the stream at the end of
        the call is the matched end token.  If this is not wanted `drop_needle`
        can be set to `True` and the end token is removed.
        """
        # the first token may be a colon for python compatibility
        self.stream.skip_if('colon')

        # in the future it would be possible to add whole code sections
        # by adding some sort of end of statement token and parsing those here.
        self.stream.expect('block_end')
        result = self.subparse(end_tokens)

        # we reached the end of the template too early, the subparser
        # does not check for this, so we do that now
        if self.stream.current.type == 'eof':
            self.fail_eof(end_tokens)

        if drop_needle:
            next(self.stream)
        return result

    def parse_set(self):
        """Parse an assign statement."""
        lineno = next(self.stream).lineno
        target = self.parse_assign_target()
        self.stream.expect('assign')
        expr = self.parse_tuple()
        return nodes.Assign(target, expr, lineno=lineno)

    def parse_for(self):
        """Parse a for loop."""
        lineno = self.stream.expect('name:for').lineno
        target = self.parse_assign_target(extra_end_rules=('name:in',))
        self.stream.expect('name:in')
        iter = self.parse_tuple(with_condexpr=False,
                                extra_end_rules=('name:recursive',))
        test = None
        if self.stream.skip_if('name:if'):
            test = self.parse_expression()
        recursive = self.stream.skip_if('name:recursive')
        body = self.parse_statements(('name:endfor', 'name:else'))
        if next(self.stream).value == 'endfor':
            else_ = []
        else:
            else_ = self.parse_statements(('name:endfor',), drop_needle=True)
        return nodes.For(target, iter, body, else_, test,
                         recursive, lineno=lineno)

    def parse_if(self):
        """Parse an if construct."""
        node = result = nodes.If(lineno=self.stream.expect('name:if').lineno)
        while 1:
            node.test = self.parse_tuple(with_condexpr=False)
            node.body = self.parse_statements(('name:elif', 'name:else',
                                               'name:endif'))
            token = next(self.stream)
            if token.test('name:elif'):
                new_node = nodes.If(lineno=self.stream.current.lineno)
                node.else_ = [new_node]
                node = new_node
                continue
            elif token.test('name:else'):
                node.else_ = self.parse_statements(('name:endif',),
                                                   drop_needle=True)
            else:
                node.else_ = []
            break
        return result

    def parse_block(self):
        node = nodes.Block(lineno=next(self.stream).lineno)
        node.name = self.stream.expect('name').value
        node.scoped = self.stream.skip_if('name:scoped')

        # common problem people encounter when switching from django
        # to jinja.  we do not support hyphens in block names, so let's
        # raise a nicer error message in that case.
        if self.stream.current.type == 'sub':
            self.fail('Block names in Jinja have to be valid Python '
                      'identifiers and may not contain hypens, use an '
                      'underscore instead.')

        node.body = self.parse_statements(('name:endblock',), drop_needle=True)
        self.stream.skip_if('name:' + node.name)
        return node

    def parse_extends(self):
        node = nodes.Extends(lineno=next(self.stream).lineno)
        node.template = self.parse_expression()
        return node

    def parse_import_context(self, node, default):
        if self.stream.current.test_any('name:with', 'name:without') and \
           self.stream.look().test('name:context'):
            node.with_context = next(self.stream).value == 'with'
            self.stream.skip()
        else:
            node.with_context = default
        return node

    def parse_include(self):
        node = nodes.Include(lineno=next(self.stream).lineno)
        node.template = self.parse_expression()
        if self.stream.current.test('name:ignore') and \
           self.stream.look().test('name:missing'):
            node.ignore_missing = True
            self.stream.skip(2)
        else:
            node.ignore_missing = False
        return self.parse_import_context(node, True)

    def parse_import(self):
        node = nodes.Import(lineno=next(self.stream).lineno)
        node.template = self.parse_expression()
        self.stream.expect('name:as')
        node.target = self.parse_assign_target(name_only=True).name
        return self.parse_import_context(node, False)

    def parse_from(self):
        node = nodes.FromImport(lineno=next(self.stream).lineno)
        node.template = self.parse_expression()
        self.stream.expect('name:import')
        node.names = []

        def parse_context():
            if self.stream.current.value in ('with', 'without') and \
               self.stream.look().test('name:context'):
                node.with_context = next(self.stream).value == 'with'
                self.stream.skip()
                return True
            return False

        while 1:
            if node.names:
                self.stream.expect('comma')
            if self.stream.current.type == 'name':
                if parse_context():
                    break
                target = self.parse_assign_target(name_only=True)
                if target.name.startswith('_'):
                    self.fail('names starting with an underline can not '
                              'be imported', target.lineno,
                              exc=TemplateAssertionError)
                if self.stream.skip_if('name:as'):
                    alias = self.parse_assign_target(name_only=True)
                    node.names.append((target.name, alias.name))
                else:
                    node.names.append(target.name)
                if parse_context() or self.stream.current.type != 'comma':
                    break
            else:
                break
        if not hasattr(node, 'with_context'):
            node.with_context = False
            self.stream.skip_if('comma')
        return node

    def parse_signature(self, node):
        node.args = args = []
        node.defaults = defaults = []
        self.stream.expect('lparen')
        while self.stream.current.type != 'rparen':
            if args:
                self.stream.expect('comma')
            arg = self.parse_assign_target(name_only=True)
            arg.set_ctx('param')
            if self.stream.skip_if('assign'):
                defaults.append(self.parse_expression())
            args.append(arg)
        self.stream.expect('rparen')

    def parse_call_block(self):
        node = nodes.CallBlock(lineno=next(self.stream).lineno)
        if self.stream.current.type == 'lparen':
            self.parse_signature(node)
        else:
            node.args = []
            node.defaults = []

        node.call = self.parse_expression()
        if not isinstance(node.call, nodes.Call):
            self.fail('expected call', node.lineno)
        node.body = self.parse_statements(('name:endcall',), drop_needle=True)
        return node

    def parse_filter_block(self):
        node = nodes.FilterBlock(lineno=next(self.stream).lineno)
        node.filter = self.parse_filter(None, start_inline=True)
        node.body = self.parse_statements(('name:endfilter',),
                                          drop_needle=True)
        return node

    def parse_macro(self):
        node = nodes.Macro(lineno=next(self.stream).lineno)
        node.name = self.parse_assign_target(name_only=True).name
        self.parse_signature(node)
        node.body = self.parse_statements(('name:endmacro',),
                                          drop_needle=True)
        return node

    def parse_print(self):
        node = nodes.Output(lineno=next(self.stream).lineno)
        node.nodes = []
        while self.stream.current.type != 'block_end':
            if node.nodes:
                self.stream.expect('comma')
            node.nodes.append(self.parse_expression())
        return node

    def parse_assign_target(self, with_tuple=True, name_only=False,
                            extra_end_rules=None):
        """Parse an assignment target.  As Jinja2 allows assignments to
        tuples, this function can parse all allowed assignment targets.  Per
        default assignments to tuples are parsed, that can be disable however
        by setting `with_tuple` to `False`.  If only assignments to names are
        wanted `name_only` can be set to `True`.  The `extra_end_rules`
        parameter is forwarded to the tuple parsing function.
        """
        if name_only:
            token = self.stream.expect('name')
            target = nodes.Name(token.value, 'store', lineno=token.lineno)
        else:
            if with_tuple:
                target = self.parse_tuple(simplified=True,
                                          extra_end_rules=extra_end_rules)
            else:
                target = self.parse_primary()
            target.set_ctx('store')
        if not target.can_assign():
            self.fail('can\'t assign to %r' % target.__class__.
                      __name__.lower(), target.lineno)
        return target

    def parse_expression(self, with_condexpr=True):
        """Parse an expression.  Per default all expressions are parsed, if
        the optional `with_condexpr` parameter is set to `False` conditional
        expressions are not parsed.
        """
        if with_condexpr:
            return self.parse_condexpr()
        return self.parse_or()

    def parse_condexpr(self):
        lineno = self.stream.current.lineno
        expr1 = self.parse_or()
        while self.stream.skip_if('name:if'):
            expr2 = self.parse_or()
            if self.stream.skip_if('name:else'):
                expr3 = self.parse_condexpr()
            else:
                expr3 = None
            expr1 = nodes.CondExpr(expr2, expr1, expr3, lineno=lineno)
            lineno = self.stream.current.lineno
        return expr1

    def parse_or(self):
        lineno = self.stream.current.lineno
        left = self.parse_and()
        while self.stream.skip_if('name:or'):
            right = self.parse_and()
            left = nodes.Or(left, right, lineno=lineno)
            lineno = self.stream.current.lineno
        return left

    def parse_and(self):
        lineno = self.stream.current.lineno
        left = self.parse_not()
        while self.stream.skip_if('name:and'):
            right = self.parse_not()
            left = nodes.And(left, right, lineno=lineno)
            lineno = self.stream.current.lineno
        return left

    def parse_not(self):
        if self.stream.current.test('name:not'):
            lineno = next(self.stream).lineno
            return nodes.Not(self.parse_not(), lineno=lineno)
        return self.parse_compare()

    def parse_compare(self):
        lineno = self.stream.current.lineno
        expr = self.parse_add()
        ops = []
        while 1:
            token_type = self.stream.current.type
            if token_type in _compare_operators:
                next(self.stream)
                ops.append(nodes.Operand(token_type, self.parse_add()))
            elif self.stream.skip_if('name:in'):
                ops.append(nodes.Operand('in', self.parse_add()))
            elif self.stream.current.test('name:not') and \
                 self.stream.look().test('name:in'):
                self.stream.skip(2)
                ops.append(nodes.Operand('notin', self.parse_add()))
            else:
                break
            lineno = self.stream.current.lineno
        if not ops:
            return expr
        return nodes.Compare(expr, ops, lineno=lineno)

    def parse_add(self):
        lineno = self.stream.current.lineno
        left = self.parse_sub()
        while self.stream.current.type == 'add':
            next(self.stream)
            right = self.parse_sub()
            left = nodes.Add(left, right, lineno=lineno)
            lineno = self.stream.current.lineno
        return left

    def parse_sub(self):
        lineno = self.stream.current.lineno
        left = self.parse_concat()
        while self.stream.current.type == 'sub':
            next(self.stream)
            right = self.parse_concat()
            left = nodes.Sub(left, right, lineno=lineno)
            lineno = self.stream.current.lineno
        return left

    def parse_concat(self):
        lineno = self.stream.current.lineno
        args = [self.parse_mul()]
        while self.stream.current.type == 'tilde':
            next(self.stream)
            args.append(self.parse_mul())
        if len(args) == 1:
            return args[0]
        return nodes.Concat(args, lineno=lineno)

    def parse_mul(self):
        lineno = self.stream.current.lineno
        left = self.parse_div()
        while self.stream.current.type == 'mul':
            next(self.stream)
            right = self.parse_div()
            left = nodes.Mul(left, right, lineno=lineno)
            lineno = self.stream.current.lineno
        return left

    def parse_div(self):
        lineno = self.stream.current.lineno
        left = self.parse_floordiv()
        while self.stream.current.type == 'div':
            next(self.stream)
            right = self.parse_floordiv()
            left = nodes.Div(left, right, lineno=lineno)
            lineno = self.stream.current.lineno
        return left

    def parse_floordiv(self):
        lineno = self.stream.current.lineno
        left = self.parse_mod()
        while self.stream.current.type == 'floordiv':
            next(self.stream)
            right = self.parse_mod()
            left = nodes.FloorDiv(left, right, lineno=lineno)
            lineno = self.stream.current.lineno
        return left

    def parse_mod(self):
        lineno = self.stream.current.lineno
        left = self.parse_pow()
        while self.stream.current.type == 'mod':
            next(self.stream)
            right = self.parse_pow()
            left = nodes.Mod(left, right, lineno=lineno)
            lineno = self.stream.current.lineno
        return left

    def parse_pow(self):
        lineno = self.stream.current.lineno
        left = self.parse_unary()
        while self.stream.current.type == 'pow':
            next(self.stream)
            right = self.parse_unary()
            left = nodes.Pow(left, right, lineno=lineno)
            lineno = self.stream.current.lineno
        return left

    def parse_unary(self, with_filter=True):
        token_type = self.stream.current.type
        lineno = self.stream.current.lineno
        if token_type == 'sub':
            next(self.stream)
            node = nodes.Neg(self.parse_unary(False), lineno=lineno)
        elif token_type == 'add':
            next(self.stream)
            node = nodes.Pos(self.parse_unary(False), lineno=lineno)
        else:
            node = self.parse_primary()
        node = self.parse_postfix(node)
        if with_filter:
            node = self.parse_filter_expr(node)
        return node

    def parse_primary(self):
        token = self.stream.current
        if token.type == 'name':
            if token.value in ('true', 'false', 'True', 'False'):
                node = nodes.Const(token.value in ('true', 'True'),
                                   lineno=token.lineno)
            elif token.value in ('none', 'None'):
                node = nodes.Const(None, lineno=token.lineno)
            else:
                node = nodes.Name(token.value, 'load', lineno=token.lineno)
            next(self.stream)
        elif token.type == 'string':
            next(self.stream)
            buf = [token.value]
            lineno = token.lineno
            while self.stream.current.type == 'string':
                buf.append(self.stream.current.value)
                next(self.stream)
            node = nodes.Const(''.join(buf), lineno=lineno)
        elif token.type in ('integer', 'float'):
            next(self.stream)
            node = nodes.Const(token.value, lineno=token.lineno)
        elif token.type == 'lparen':
            next(self.stream)
            node = self.parse_tuple(explicit_parentheses=True)
            self.stream.expect('rparen')
        elif token.type == 'lbracket':
            node = self.parse_list()
        elif token.type == 'lbrace':
            node = self.parse_dict()
        else:
            self.fail("unexpected '%s'" % describe_token(token), token.lineno)
        return node

    def parse_tuple(self, simplified=False, with_condexpr=True,
                    extra_end_rules=None, explicit_parentheses=False):
        """Works like `parse_expression` but if multiple expressions are
        delimited by a comma a :class:`~jinja2.nodes.Tuple` node is created.
        This method could also return a regular expression instead of a tuple
        if no commas where found.

        The default parsing mode is a full tuple.  If `simplified` is `True`
        only names and literals are parsed.  The `no_condexpr` parameter is
        forwarded to :meth:`parse_expression`.

        Because tuples do not require delimiters and may end in a bogus comma
        an extra hint is needed that marks the end of a tuple.  For example
        for loops support tuples between `for` and `in`.  In that case the
        `extra_end_rules` is set to ``['name:in']``.

        `explicit_parentheses` is true if the parsing was triggered by an
        expression in parentheses.  This is used to figure out if an empty
        tuple is a valid expression or not.
        """
        lineno = self.stream.current.lineno
        if simplified:
            parse = self.parse_primary
        elif with_condexpr:
            parse = self.parse_expression
        else:
            parse = lambda: self.parse_expression(with_condexpr=False)
        args = []
        is_tuple = False
        while 1:
            if args:
                self.stream.expect('comma')
            if self.is_tuple_end(extra_end_rules):
                break
            args.append(parse())
            if self.stream.current.type == 'comma':
                is_tuple = True
            else:
                break
            lineno = self.stream.current.lineno

        if not is_tuple:
            if args:
                return args[0]

            # if we don't have explicit parentheses, an empty tuple is
            # not a valid expression.  This would mean nothing (literally
            # nothing) in the spot of an expression would be an empty
            # tuple.
            if not explicit_parentheses:
                self.fail('Expected an expression, got \'%s\'' %
                          describe_token(self.stream.current))

        return nodes.Tuple(args, 'load', lineno=lineno)

    def parse_list(self):
        token = self.stream.expect('lbracket')
        items = []
        while self.stream.current.type != 'rbracket':
            if items:
                self.stream.expect('comma')
            if self.stream.current.type == 'rbracket':
                break
            items.append(self.parse_expression())
        self.stream.expect('rbracket')
        return nodes.List(items, lineno=token.lineno)

    def parse_dict(self):
        token = self.stream.expect('lbrace')
        items = []
        while self.stream.current.type != 'rbrace':
            if items:
                self.stream.expect('comma')
            if self.stream.current.type == 'rbrace':
                break
            key = self.parse_expression()
            self.stream.expect('colon')
            value = self.parse_expression()
            items.append(nodes.Pair(key, value, lineno=key.lineno))
        self.stream.expect('rbrace')
        return nodes.Dict(items, lineno=token.lineno)

    def parse_postfix(self, node):
        while 1:
            token_type = self.stream.current.type
            if token_type == 'dot' or token_type == 'lbracket':
                node = self.parse_subscript(node)
            # calls are valid both after postfix expressions (getattr
            # and getitem) as well as filters and tests
            elif token_type == 'lparen':
                node = self.parse_call(node)
            else:
                break
        return node

    def parse_filter_expr(self, node):
        while 1:
            token_type = self.stream.current.type
            if token_type == 'pipe':
                node = self.parse_filter(node)
            elif token_type == 'name' and self.stream.current.value == 'is':
                node = self.parse_test(node)
            # calls are valid both after postfix expressions (getattr
            # and getitem) as well as filters and tests
            elif token_type == 'lparen':
                node = self.parse_call(node)
            else:
                break
        return node

    def parse_subscript(self, node):
        token = next(self.stream)
        if token.type == 'dot':
            attr_token = self.stream.current
            next(self.stream)
            if attr_token.type == 'name':
                return nodes.Getattr(node, attr_token.value, 'load',
                                     lineno=token.lineno)
            elif attr_token.type != 'integer':
                self.fail('expected name or number', attr_token.lineno)
            arg = nodes.Const(attr_token.value, lineno=attr_token.lineno)
            return nodes.Getitem(node, arg, 'load', lineno=token.lineno)
        if token.type == 'lbracket':
            priority_on_attribute = False
            args = []
            while self.stream.current.type != 'rbracket':
                if args:
                    self.stream.expect('comma')
                args.append(self.parse_subscribed())
            self.stream.expect('rbracket')
            if len(args) == 1:
                arg = args[0]
            else:
                arg = nodes.Tuple(args, 'load', lineno=token.lineno)
            return nodes.Getitem(node, arg, 'load', lineno=token.lineno)
        self.fail('expected subscript expression', self.lineno)

    def parse_subscribed(self):
        lineno = self.stream.current.lineno

        if self.stream.current.type == 'colon':
            next(self.stream)
            args = [None]
        else:
            node = self.parse_expression()
            if self.stream.current.type != 'colon':
                return node
            next(self.stream)
            args = [node]

        if self.stream.current.type == 'colon':
            args.append(None)
        elif self.stream.current.type not in ('rbracket', 'comma'):
            args.append(self.parse_expression())
        else:
            args.append(None)

        if self.stream.current.type == 'colon':
            next(self.stream)
            if self.stream.current.type not in ('rbracket', 'comma'):
                args.append(self.parse_expression())
            else:
                args.append(None)
        else:
            args.append(None)

        return nodes.Slice(lineno=lineno, *args)

    def parse_call(self, node):
        token = self.stream.expect('lparen')
        args = []
        kwargs = []
        dyn_args = dyn_kwargs = None
        require_comma = False

        def ensure(expr):
            if not expr:
                self.fail('invalid syntax for function call expression',
                          token.lineno)

        while self.stream.current.type != 'rparen':
            if require_comma:
                self.stream.expect('comma')
                # support for trailing comma
                if self.stream.current.type == 'rparen':
                    break
            if self.stream.current.type == 'mul':
                ensure(dyn_args is None and dyn_kwargs is None)
                next(self.stream)
                dyn_args = self.parse_expression()
            elif self.stream.current.type == 'pow':
                ensure(dyn_kwargs is None)
                next(self.stream)
                dyn_kwargs = self.parse_expression()
            else:
                ensure(dyn_args is None and dyn_kwargs is None)
                if self.stream.current.type == 'name' and \
                    self.stream.look().type == 'assign':
                    key = self.stream.current.value
                    self.stream.skip(2)
                    value = self.parse_expression()
                    kwargs.append(nodes.Keyword(key, value,
                                                lineno=value.lineno))
                else:
                    ensure(not kwargs)
                    args.append(self.parse_expression())

            require_comma = True
        self.stream.expect('rparen')

        if node is None:
            return args, kwargs, dyn_args, dyn_kwargs
        return nodes.Call(node, args, kwargs, dyn_args, dyn_kwargs,
                          lineno=token.lineno)

    def parse_filter(self, node, start_inline=False):
        while self.stream.current.type == 'pipe' or start_inline:
            if not start_inline:
                next(self.stream)
            token = self.stream.expect('name')
            name = token.value
            while self.stream.current.type == 'dot':
                next(self.stream)
                name += '.' + self.stream.expect('name').value
            if self.stream.current.type == 'lparen':
                args, kwargs, dyn_args, dyn_kwargs = self.parse_call(None)
            else:
                args = []
                kwargs = []
                dyn_args = dyn_kwargs = None
            node = nodes.Filter(node, name, args, kwargs, dyn_args,
                                dyn_kwargs, lineno=token.lineno)
            start_inline = False
        return node

    def parse_test(self, node):
        token = next(self.stream)
        if self.stream.current.test('name:not'):
            next(self.stream)
            negated = True
        else:
            negated = False
        name = self.stream.expect('name').value
        while self.stream.current.type == 'dot':
            next(self.stream)
            name += '.' + self.stream.expect('name').value
        dyn_args = dyn_kwargs = None
        kwargs = []
        if self.stream.current.type == 'lparen':
            args, kwargs, dyn_args, dyn_kwargs = self.parse_call(None)
        elif self.stream.current.type in ('name', 'string', 'integer',
                                          'float', 'lparen', 'lbracket',
                                          'lbrace') and not \
             self.stream.current.test_any('name:else', 'name:or',
                                          'name:and'):
            if self.stream.current.test('name:is'):
                self.fail('You cannot chain multiple tests with is')
            args = [self.parse_expression()]
        else:
            args = []
        node = nodes.Test(node, name, args, kwargs, dyn_args,
                          dyn_kwargs, lineno=token.lineno)
        if negated:
            node = nodes.Not(node, lineno=token.lineno)
        return node

    def subparse(self, end_tokens=None):
        body = []
        data_buffer = []
        add_data = data_buffer.append

        if end_tokens is not None:
            self._end_token_stack.append(end_tokens)

        def flush_data():
            if data_buffer:
                lineno = data_buffer[0].lineno
                body.append(nodes.Output(data_buffer[:], lineno=lineno))
                del data_buffer[:]

        try:
            while self.stream:
                token = self.stream.current
                if token.type == 'data':
                    if token.value:
                        add_data(nodes.TemplateData(token.value,
                                                    lineno=token.lineno))
                    next(self.stream)
                elif token.type == 'variable_begin':
                    next(self.stream)
                    add_data(self.parse_tuple(with_condexpr=True))
                    self.stream.expect('variable_end')
                elif token.type == 'block_begin':
                    flush_data()
                    next(self.stream)
                    if end_tokens is not None and \
                       self.stream.current.test_any(*end_tokens):
                        return body
                    rv = self.parse_statement()
                    if isinstance(rv, list):
                        body.extend(rv)
                    else:
                        body.append(rv)
                    self.stream.expect('block_end')
                else:
                    raise AssertionError('internal parsing error')

            flush_data()
        finally:
            if end_tokens is not None:
                self._end_token_stack.pop()

        return body

    def parse(self):
        """Parse the whole template into a `Template` node."""
        result = nodes.Template(self.subparse(), lineno=1)
        result.set_environment(self.environment)
        return result

########NEW FILE########
__FILENAME__ = runtime
# -*- coding: utf-8 -*-
"""
    jinja2.runtime
    ~~~~~~~~~~~~~~

    Runtime helpers.

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD.
"""
from itertools import chain, imap
from jinja2.nodes import EvalContext, _context_function_types
from jinja2.utils import Markup, partial, soft_unicode, escape, missing, \
     concat, internalcode, next, object_type_repr
from jinja2.exceptions import UndefinedError, TemplateRuntimeError, \
     TemplateNotFound


# these variables are exported to the template runtime
__all__ = ['LoopContext', 'TemplateReference', 'Macro', 'Markup',
           'TemplateRuntimeError', 'missing', 'concat', 'escape',
           'markup_join', 'unicode_join', 'to_string', 'identity',
           'TemplateNotFound']

#: the name of the function that is used to convert something into
#: a string.  2to3 will adopt that automatically and the generated
#: code can take advantage of it.
to_string = unicode

#: the identity function.  Useful for certain things in the environment
identity = lambda x: x


def markup_join(seq):
    """Concatenation that escapes if necessary and converts to unicode."""
    buf = []
    iterator = imap(soft_unicode, seq)
    for arg in iterator:
        buf.append(arg)
        if hasattr(arg, '__html__'):
            return Markup(u'').join(chain(buf, iterator))
    return concat(buf)


def unicode_join(seq):
    """Simple args to unicode conversion and concatenation."""
    return concat(imap(unicode, seq))


def new_context(environment, template_name, blocks, vars=None,
                shared=None, globals=None, locals=None):
    """Internal helper to for context creation."""
    if vars is None:
        vars = {}
    if shared:
        parent = vars
    else:
        parent = dict(globals or (), **vars)
    if locals:
        # if the parent is shared a copy should be created because
        # we don't want to modify the dict passed
        if shared:
            parent = dict(parent)
        for key, value in locals.iteritems():
            if key[:2] == 'l_' and value is not missing:
                parent[key[2:]] = value
    return Context(environment, parent, template_name, blocks)


class TemplateReference(object):
    """The `self` in templates."""

    def __init__(self, context):
        self.__context = context

    def __getitem__(self, name):
        blocks = self.__context.blocks[name]
        return BlockReference(name, self.__context, blocks, 0)

    def __repr__(self):
        return '<%s %r>' % (
            self.__class__.__name__,
            self.__context.name
        )


class Context(object):
    """The template context holds the variables of a template.  It stores the
    values passed to the template and also the names the template exports.
    Creating instances is neither supported nor useful as it's created
    automatically at various stages of the template evaluation and should not
    be created by hand.

    The context is immutable.  Modifications on :attr:`parent` **must not**
    happen and modifications on :attr:`vars` are allowed from generated
    template code only.  Template filters and global functions marked as
    :func:`contextfunction`\s get the active context passed as first argument
    and are allowed to access the context read-only.

    The template context supports read only dict operations (`get`,
    `keys`, `values`, `items`, `iterkeys`, `itervalues`, `iteritems`,
    `__getitem__`, `__contains__`).  Additionally there is a :meth:`resolve`
    method that doesn't fail with a `KeyError` but returns an
    :class:`Undefined` object for missing variables.
    """
    __slots__ = ('parent', 'vars', 'environment', 'eval_ctx', 'exported_vars',
                 'name', 'blocks', '__weakref__')

    def __init__(self, environment, parent, name, blocks):
        self.parent = parent
        self.vars = {}
        self.environment = environment
        self.eval_ctx = EvalContext(self.environment, name)
        self.exported_vars = set()
        self.name = name

        # create the initial mapping of blocks.  Whenever template inheritance
        # takes place the runtime will update this mapping with the new blocks
        # from the template.
        self.blocks = dict((k, [v]) for k, v in blocks.iteritems())

    def super(self, name, current):
        """Render a parent block."""
        try:
            blocks = self.blocks[name]
            index = blocks.index(current) + 1
            blocks[index]
        except LookupError:
            return self.environment.undefined('there is no parent block '
                                              'called %r.' % name,
                                              name='super')
        return BlockReference(name, self, blocks, index)

    def get(self, key, default=None):
        """Returns an item from the template context, if it doesn't exist
        `default` is returned.
        """
        try:
            return self[key]
        except KeyError:
            return default

    def resolve(self, key):
        """Looks up a variable like `__getitem__` or `get` but returns an
        :class:`Undefined` object with the name of the name looked up.
        """
        if key in self.vars:
            return self.vars[key]
        if key in self.parent:
            return self.parent[key]
        return self.environment.undefined(name=key)

    def get_exported(self):
        """Get a new dict with the exported variables."""
        return dict((k, self.vars[k]) for k in self.exported_vars)

    def get_all(self):
        """Return a copy of the complete context as dict including the
        exported variables.
        """
        return dict(self.parent, **self.vars)

    @internalcode
    def call(__self, __obj, *args, **kwargs):
        """Call the callable with the arguments and keyword arguments
        provided but inject the active context or environment as first
        argument if the callable is a :func:`contextfunction` or
        :func:`environmentfunction`.
        """
        if __debug__:
            __traceback_hide__ = True
        if isinstance(__obj, _context_function_types):
            if getattr(__obj, 'contextfunction', 0):
                args = (__self,) + args
            elif getattr(__obj, 'evalcontextfunction', 0):
                args = (__self.eval_ctx,) + args
            elif getattr(__obj, 'environmentfunction', 0):
                args = (__self.environment,) + args
        try:
            return __obj(*args, **kwargs)
        except StopIteration:
            return __self.environment.undefined('value was undefined because '
                                                'a callable raised a '
                                                'StopIteration exception')

    def derived(self, locals=None):
        """Internal helper function to create a derived context."""
        context = new_context(self.environment, self.name, {},
                              self.parent, True, None, locals)
        context.vars.update(self.vars)
        context.eval_ctx = self.eval_ctx
        context.blocks.update((k, list(v)) for k, v in self.blocks.iteritems())
        return context

    def _all(meth):
        proxy = lambda self: getattr(self.get_all(), meth)()
        proxy.__doc__ = getattr(dict, meth).__doc__
        proxy.__name__ = meth
        return proxy

    keys = _all('keys')
    values = _all('values')
    items = _all('items')

    # not available on python 3
    if hasattr(dict, 'iterkeys'):
        iterkeys = _all('iterkeys')
        itervalues = _all('itervalues')
        iteritems = _all('iteritems')
    del _all

    def __contains__(self, name):
        return name in self.vars or name in self.parent

    def __getitem__(self, key):
        """Lookup a variable or raise `KeyError` if the variable is
        undefined.
        """
        item = self.resolve(key)
        if isinstance(item, Undefined):
            raise KeyError(key)
        return item

    def __repr__(self):
        return '<%s %s of %r>' % (
            self.__class__.__name__,
            repr(self.get_all()),
            self.name
        )


# register the context as mapping if possible
try:
    from collections import Mapping
    Mapping.register(Context)
except ImportError:
    pass


class BlockReference(object):
    """One block on a template reference."""

    def __init__(self, name, context, stack, depth):
        self.name = name
        self._context = context
        self._stack = stack
        self._depth = depth

    @property
    def super(self):
        """Super the block."""
        if self._depth + 1 >= len(self._stack):
            return self._context.environment. \
                undefined('there is no parent block called %r.' %
                          self.name, name='super')
        return BlockReference(self.name, self._context, self._stack,
                              self._depth + 1)

    @internalcode
    def __call__(self):
        rv = concat(self._stack[self._depth](self._context))
        if self._context.eval_ctx.autoescape:
            rv = Markup(rv)
        return rv


class LoopContext(object):
    """A loop context for dynamic iteration."""

    def __init__(self, iterable, recurse=None):
        self._iterator = iter(iterable)
        self._recurse = recurse
        self.index0 = -1

        # try to get the length of the iterable early.  This must be done
        # here because there are some broken iterators around where there
        # __len__ is the number of iterations left (i'm looking at your
        # listreverseiterator!).
        try:
            self._length = len(iterable)
        except (TypeError, AttributeError):
            self._length = None

    def cycle(self, *args):
        """Cycles among the arguments with the current loop index."""
        if not args:
            raise TypeError('no items for cycling given')
        return args[self.index0 % len(args)]

    first = property(lambda x: x.index0 == 0)
    last = property(lambda x: x.index0 + 1 == x.length)
    index = property(lambda x: x.index0 + 1)
    revindex = property(lambda x: x.length - x.index0)
    revindex0 = property(lambda x: x.length - x.index)

    def __len__(self):
        return self.length

    def __iter__(self):
        return LoopContextIterator(self)

    @internalcode
    def loop(self, iterable):
        if self._recurse is None:
            raise TypeError('Tried to call non recursive loop.  Maybe you '
                            "forgot the 'recursive' modifier.")
        return self._recurse(iterable, self._recurse)

    # a nifty trick to enhance the error message if someone tried to call
    # the the loop without or with too many arguments.
    __call__ = loop
    del loop

    @property
    def length(self):
        if self._length is None:
            # if was not possible to get the length of the iterator when
            # the loop context was created (ie: iterating over a generator)
            # we have to convert the iterable into a sequence and use the
            # length of that.
            iterable = tuple(self._iterator)
            self._iterator = iter(iterable)
            self._length = len(iterable) + self.index0 + 1
        return self._length

    def __repr__(self):
        return '<%s %r/%r>' % (
            self.__class__.__name__,
            self.index,
            self.length
        )


class LoopContextIterator(object):
    """The iterator for a loop context."""
    __slots__ = ('context',)

    def __init__(self, context):
        self.context = context

    def __iter__(self):
        return self

    def next(self):
        ctx = self.context
        ctx.index0 += 1
        return next(ctx._iterator), ctx


class Macro(object):
    """Wraps a macro function."""

    def __init__(self, environment, func, name, arguments, defaults,
                 catch_kwargs, catch_varargs, caller):
        self._environment = environment
        self._func = func
        self._argument_count = len(arguments)
        self.name = name
        self.arguments = arguments
        self.defaults = defaults
        self.catch_kwargs = catch_kwargs
        self.catch_varargs = catch_varargs
        self.caller = caller

    @internalcode
    def __call__(self, *args, **kwargs):
        # try to consume the positional arguments
        arguments = list(args[:self._argument_count])
        off = len(arguments)

        # if the number of arguments consumed is not the number of
        # arguments expected we start filling in keyword arguments
        # and defaults.
        if off != self._argument_count:
            for idx, name in enumerate(self.arguments[len(arguments):]):
                try:
                    value = kwargs.pop(name)
                except KeyError:
                    try:
                        value = self.defaults[idx - self._argument_count + off]
                    except IndexError:
                        value = self._environment.undefined(
                            'parameter %r was not provided' % name, name=name)
                arguments.append(value)

        # it's important that the order of these arguments does not change
        # if not also changed in the compiler's `function_scoping` method.
        # the order is caller, keyword arguments, positional arguments!
        if self.caller:
            caller = kwargs.pop('caller', None)
            if caller is None:
                caller = self._environment.undefined('No caller defined',
                                                     name='caller')
            arguments.append(caller)
        if self.catch_kwargs:
            arguments.append(kwargs)
        elif kwargs:
            raise TypeError('macro %r takes no keyword argument %r' %
                            (self.name, next(iter(kwargs))))
        if self.catch_varargs:
            arguments.append(args[self._argument_count:])
        elif len(args) > self._argument_count:
            raise TypeError('macro %r takes not more than %d argument(s)' %
                            (self.name, len(self.arguments)))
        return self._func(*arguments)

    def __repr__(self):
        return '<%s %s>' % (
            self.__class__.__name__,
            self.name is None and 'anonymous' or repr(self.name)
        )


class Undefined(object):
    """The default undefined type.  This undefined type can be printed and
    iterated over, but every other access will raise an :exc:`UndefinedError`:

    >>> foo = Undefined(name='foo')
    >>> str(foo)
    ''
    >>> not foo
    True
    >>> foo + 42
    Traceback (most recent call last):
      ...
    UndefinedError: 'foo' is undefined
    """
    __slots__ = ('_undefined_hint', '_undefined_obj', '_undefined_name',
                 '_undefined_exception')

    def __init__(self, hint=None, obj=missing, name=None, exc=UndefinedError):
        self._undefined_hint = hint
        self._undefined_obj = obj
        self._undefined_name = name
        self._undefined_exception = exc

    @internalcode
    def _fail_with_undefined_error(self, *args, **kwargs):
        """Regular callback function for undefined objects that raises an
        `UndefinedError` on call.
        """
        if self._undefined_hint is None:
            if self._undefined_obj is missing:
                hint = '%r is undefined' % self._undefined_name
            elif not isinstance(self._undefined_name, basestring):
                hint = '%s has no element %r' % (
                    object_type_repr(self._undefined_obj),
                    self._undefined_name
                )
            else:
                hint = '%r has no attribute %r' % (
                    object_type_repr(self._undefined_obj),
                    self._undefined_name
                )
        else:
            hint = self._undefined_hint
        raise self._undefined_exception(hint)

    @internalcode
    def __getattr__(self, name):
        if name[:2] == '__':
            raise AttributeError(name)
        return self._fail_with_undefined_error()

    __add__ = __radd__ = __mul__ = __rmul__ = __div__ = __rdiv__ = \
    __truediv__ = __rtruediv__ = __floordiv__ = __rfloordiv__ = \
    __mod__ = __rmod__ = __pos__ = __neg__ = __call__ = \
    __getitem__ = __lt__ = __le__ = __gt__ = __ge__ = __int__ = \
    __float__ = __complex__ = __pow__ = __rpow__ = \
        _fail_with_undefined_error

    def __str__(self):
        return unicode(self).encode('utf-8')

    # unicode goes after __str__ because we configured 2to3 to rename
    # __unicode__ to __str__.  because the 2to3 tree is not designed to
    # remove nodes from it, we leave the above __str__ around and let
    # it override at runtime.
    def __unicode__(self):
        return u''

    def __len__(self):
        return 0

    def __iter__(self):
        if 0:
            yield None

    def __nonzero__(self):
        return False

    def __repr__(self):
        return 'Undefined'


class DebugUndefined(Undefined):
    """An undefined that returns the debug info when printed.

    >>> foo = DebugUndefined(name='foo')
    >>> str(foo)
    '{{ foo }}'
    >>> not foo
    True
    >>> foo + 42
    Traceback (most recent call last):
      ...
    UndefinedError: 'foo' is undefined
    """
    __slots__ = ()

    def __unicode__(self):
        if self._undefined_hint is None:
            if self._undefined_obj is missing:
                return u'{{ %s }}' % self._undefined_name
            return '{{ no such element: %s[%r] }}' % (
                object_type_repr(self._undefined_obj),
                self._undefined_name
            )
        return u'{{ undefined value printed: %s }}' % self._undefined_hint


class StrictUndefined(Undefined):
    """An undefined that barks on print and iteration as well as boolean
    tests and all kinds of comparisons.  In other words: you can do nothing
    with it except checking if it's defined using the `defined` test.

    >>> foo = StrictUndefined(name='foo')
    >>> str(foo)
    Traceback (most recent call last):
      ...
    UndefinedError: 'foo' is undefined
    >>> not foo
    Traceback (most recent call last):
      ...
    UndefinedError: 'foo' is undefined
    >>> foo + 42
    Traceback (most recent call last):
      ...
    UndefinedError: 'foo' is undefined
    """
    __slots__ = ()
    __iter__ = __unicode__ = __str__ = __len__ = __nonzero__ = __eq__ = \
        __ne__ = __bool__ = Undefined._fail_with_undefined_error


# remove remaining slots attributes, after the metaclass did the magic they
# are unneeded and irritating as they contain wrong data for the subclasses.
del Undefined.__slots__, DebugUndefined.__slots__, StrictUndefined.__slots__

########NEW FILE########
__FILENAME__ = sandbox
# -*- coding: utf-8 -*-
"""
    jinja2.sandbox
    ~~~~~~~~~~~~~~

    Adds a sandbox layer to Jinja as it was the default behavior in the old
    Jinja 1 releases.  This sandbox is slightly different from Jinja 1 as the
    default behavior is easier to use.

    The behavior can be changed by subclassing the environment.

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD.
"""
import operator
from jinja2.environment import Environment
from jinja2.exceptions import SecurityError
from jinja2.utils import FunctionType, MethodType, TracebackType, CodeType, \
     FrameType, GeneratorType


#: maximum number of items a range may produce
MAX_RANGE = 100000

#: attributes of function objects that are considered unsafe.
UNSAFE_FUNCTION_ATTRIBUTES = set(['func_closure', 'func_code', 'func_dict',
                                  'func_defaults', 'func_globals'])

#: unsafe method attributes.  function attributes are unsafe for methods too
UNSAFE_METHOD_ATTRIBUTES = set(['im_class', 'im_func', 'im_self'])


import warnings

# make sure we don't warn in python 2.6 about stuff we don't care about
warnings.filterwarnings('ignore', 'the sets module', DeprecationWarning,
                        module='jinja2.sandbox')

from collections import deque

_mutable_set_types = (set,)
_mutable_mapping_types = (dict,)
_mutable_sequence_types = (list,)


# on python 2.x we can register the user collection types
try:
    from UserDict import UserDict, DictMixin
    from UserList import UserList
    _mutable_mapping_types += (UserDict, DictMixin)
    _mutable_set_types += (UserList,)
except ImportError:
    pass

# if sets is still available, register the mutable set from there as well
try:
    from sets import Set
    _mutable_set_types += (Set,)
except ImportError:
    pass

#: register Python 2.6 abstract base classes
try:
    from collections import MutableSet, MutableMapping, MutableSequence
    _mutable_set_types += (MutableSet,)
    _mutable_mapping_types += (MutableMapping,)
    _mutable_sequence_types += (MutableSequence,)
except ImportError:
    pass

_mutable_spec = (
    (_mutable_set_types, frozenset([
        'add', 'clear', 'difference_update', 'discard', 'pop', 'remove',
        'symmetric_difference_update', 'update'
    ])),
    (_mutable_mapping_types, frozenset([
        'clear', 'pop', 'popitem', 'setdefault', 'update'
    ])),
    (_mutable_sequence_types, frozenset([
        'append', 'reverse', 'insert', 'sort', 'extend', 'remove'
    ])),
    (deque, frozenset([
        'append', 'appendleft', 'clear', 'extend', 'extendleft', 'pop',
        'popleft', 'remove', 'rotate'
    ]))
)


def safe_range(*args):
    """A range that can't generate ranges with a length of more than
    MAX_RANGE items.
    """
    rng = xrange(*args)
    if len(rng) > MAX_RANGE:
        raise OverflowError('range too big, maximum size for range is %d' %
                            MAX_RANGE)
    return rng


def unsafe(f):
    """Marks a function or method as unsafe.

    ::

        @unsafe
        def delete(self):
            pass
    """
    f.unsafe_callable = True
    return f


def is_internal_attribute(obj, attr):
    """Test if the attribute given is an internal python attribute.  For
    example this function returns `True` for the `func_code` attribute of
    python objects.  This is useful if the environment method
    :meth:`~SandboxedEnvironment.is_safe_attribute` is overriden.

    >>> from jinja2.sandbox import is_internal_attribute
    >>> is_internal_attribute(lambda: None, "func_code")
    True
    >>> is_internal_attribute((lambda x:x).func_code, 'co_code')
    True
    >>> is_internal_attribute(str, "upper")
    False
    """
    if isinstance(obj, FunctionType):
        if attr in UNSAFE_FUNCTION_ATTRIBUTES:
            return True
    elif isinstance(obj, MethodType):
        if attr in UNSAFE_FUNCTION_ATTRIBUTES or \
           attr in UNSAFE_METHOD_ATTRIBUTES:
            return True
    elif isinstance(obj, type):
        if attr == 'mro':
            return True
    elif isinstance(obj, (CodeType, TracebackType, FrameType)):
        return True
    elif isinstance(obj, GeneratorType):
        if attr == 'gi_frame':
            return True
    return attr.startswith('__')


def modifies_known_mutable(obj, attr):
    """This function checks if an attribute on a builtin mutable object
    (list, dict, set or deque) would modify it if called.  It also supports
    the "user"-versions of the objects (`sets.Set`, `UserDict.*` etc.) and
    with Python 2.6 onwards the abstract base classes `MutableSet`,
    `MutableMapping`, and `MutableSequence`.

    >>> modifies_known_mutable({}, "clear")
    True
    >>> modifies_known_mutable({}, "keys")
    False
    >>> modifies_known_mutable([], "append")
    True
    >>> modifies_known_mutable([], "index")
    False

    If called with an unsupported object (such as unicode) `False` is
    returned.

    >>> modifies_known_mutable("foo", "upper")
    False
    """
    for typespec, unsafe in _mutable_spec:
        if isinstance(obj, typespec):
            return attr in unsafe
    return False


class SandboxedEnvironment(Environment):
    """The sandboxed environment.  It works like the regular environment but
    tells the compiler to generate sandboxed code.  Additionally subclasses of
    this environment may override the methods that tell the runtime what
    attributes or functions are safe to access.

    If the template tries to access insecure code a :exc:`SecurityError` is
    raised.  However also other exceptions may occour during the rendering so
    the caller has to ensure that all exceptions are catched.
    """
    sandboxed = True

    #: default callback table for the binary operators.  A copy of this is
    #: available on each instance of a sandboxed environment as
    #: :attr:`binop_table`
    default_binop_table = {
        '+':        operator.add,
        '-':        operator.sub,
        '*':        operator.mul,
        '/':        operator.truediv,
        '//':       operator.floordiv,
        '**':       operator.pow,
        '%':        operator.mod
    }

    #: default callback table for the unary operators.  A copy of this is
    #: available on each instance of a sandboxed environment as
    #: :attr:`unop_table`
    default_unop_table = {
        '+':        operator.pos,
        '-':        operator.neg
    }

    #: a set of binary operators that should be intercepted.  Each operator
    #: that is added to this set (empty by default) is delegated to the
    #: :meth:`call_binop` method that will perform the operator.  The default
    #: operator callback is specified by :attr:`binop_table`.
    #:
    #: The following binary operators are interceptable:
    #: ``//``, ``%``, ``+``, ``*``, ``-``, ``/``, and ``**``
    #:
    #: The default operation form the operator table corresponds to the
    #: builtin function.  Intercepted calls are always slower than the native
    #: operator call, so make sure only to intercept the ones you are
    #: interested in.
    #:
    #: .. versionadded:: 2.6
    intercepted_binops = frozenset()

    #: a set of unary operators that should be intercepted.  Each operator
    #: that is added to this set (empty by default) is delegated to the
    #: :meth:`call_unop` method that will perform the operator.  The default
    #: operator callback is specified by :attr:`unop_table`.
    #:
    #: The following unary operators are interceptable: ``+``, ``-``
    #:
    #: The default operation form the operator table corresponds to the
    #: builtin function.  Intercepted calls are always slower than the native
    #: operator call, so make sure only to intercept the ones you are
    #: interested in.
    #:
    #: .. versionadded:: 2.6
    intercepted_unops = frozenset()

    def intercept_unop(self, operator):
        """Called during template compilation with the name of a unary
        operator to check if it should be intercepted at runtime.  If this
        method returns `True`, :meth:`call_unop` is excuted for this unary
        operator.  The default implementation of :meth:`call_unop` will use
        the :attr:`unop_table` dictionary to perform the operator with the
        same logic as the builtin one.

        The following unary operators are interceptable: ``+`` and ``-``

        Intercepted calls are always slower than the native operator call,
        so make sure only to intercept the ones you are interested in.

        .. versionadded:: 2.6
        """
        return False


    def __init__(self, *args, **kwargs):
        Environment.__init__(self, *args, **kwargs)
        self.globals['range'] = safe_range
        self.binop_table = self.default_binop_table.copy()
        self.unop_table = self.default_unop_table.copy()

    def is_safe_attribute(self, obj, attr, value):
        """The sandboxed environment will call this method to check if the
        attribute of an object is safe to access.  Per default all attributes
        starting with an underscore are considered private as well as the
        special attributes of internal python objects as returned by the
        :func:`is_internal_attribute` function.
        """
        return not (attr.startswith('_') or is_internal_attribute(obj, attr))

    def is_safe_callable(self, obj):
        """Check if an object is safely callable.  Per default a function is
        considered safe unless the `unsafe_callable` attribute exists and is
        True.  Override this method to alter the behavior, but this won't
        affect the `unsafe` decorator from this module.
        """
        return not (getattr(obj, 'unsafe_callable', False) or
                    getattr(obj, 'alters_data', False))

    def call_binop(self, context, operator, left, right):
        """For intercepted binary operator calls (:meth:`intercepted_binops`)
        this function is executed instead of the builtin operator.  This can
        be used to fine tune the behavior of certain operators.

        .. versionadded:: 2.6
        """
        return self.binop_table[operator](left, right)

    def call_unop(self, context, operator, arg):
        """For intercepted unary operator calls (:meth:`intercepted_unops`)
        this function is executed instead of the builtin operator.  This can
        be used to fine tune the behavior of certain operators.

        .. versionadded:: 2.6
        """
        return self.unop_table[operator](arg)

    def getitem(self, obj, argument):
        """Subscribe an object from sandboxed code."""
        try:
            return obj[argument]
        except (TypeError, LookupError):
            if isinstance(argument, basestring):
                try:
                    attr = str(argument)
                except Exception:
                    pass
                else:
                    try:
                        value = getattr(obj, attr)
                    except AttributeError:
                        pass
                    else:
                        if self.is_safe_attribute(obj, argument, value):
                            return value
                        return self.unsafe_undefined(obj, argument)
        return self.undefined(obj=obj, name=argument)

    def getattr(self, obj, attribute):
        """Subscribe an object from sandboxed code and prefer the
        attribute.  The attribute passed *must* be a bytestring.
        """
        try:
            value = getattr(obj, attribute)
        except AttributeError:
            try:
                return obj[attribute]
            except (TypeError, LookupError):
                pass
        else:
            if self.is_safe_attribute(obj, attribute, value):
                return value
            return self.unsafe_undefined(obj, attribute)
        return self.undefined(obj=obj, name=attribute)

    def unsafe_undefined(self, obj, attribute):
        """Return an undefined object for unsafe attributes."""
        return self.undefined('access to attribute %r of %r '
                              'object is unsafe.' % (
            attribute,
            obj.__class__.__name__
        ), name=attribute, obj=obj, exc=SecurityError)

    def call(__self, __context, __obj, *args, **kwargs):
        """Call an object from sandboxed code."""
        # the double prefixes are to avoid double keyword argument
        # errors when proxying the call.
        if not __self.is_safe_callable(__obj):
            raise SecurityError('%r is not safely callable' % (__obj,))
        return __context.call(__obj, *args, **kwargs)


class ImmutableSandboxedEnvironment(SandboxedEnvironment):
    """Works exactly like the regular `SandboxedEnvironment` but does not
    permit modifications on the builtin mutable objects `list`, `set`, and
    `dict` by using the :func:`modifies_known_mutable` function.
    """

    def is_safe_attribute(self, obj, attr, value):
        if not SandboxedEnvironment.is_safe_attribute(self, obj, attr, value):
            return False
        return not modifies_known_mutable(obj, attr)

########NEW FILE########
__FILENAME__ = tests
# -*- coding: utf-8 -*-
"""
    jinja2.tests
    ~~~~~~~~~~~~

    Jinja test functions. Used with the "is" operator.

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD, see LICENSE for more details.
"""
import re
from jinja2.runtime import Undefined

# nose, nothing here to test
__test__ = False


number_re = re.compile(r'^-?\d+(\.\d+)?$')
regex_type = type(number_re)


try:
    test_callable = callable
except NameError:
    def test_callable(x):
        return hasattr(x, '__call__')


def test_odd(value):
    """Return true if the variable is odd."""
    return value % 2 == 1


def test_even(value):
    """Return true if the variable is even."""
    return value % 2 == 0


def test_divisibleby(value, num):
    """Check if a variable is divisible by a number."""
    return value % num == 0


def test_defined(value):
    """Return true if the variable is defined:

    .. sourcecode:: jinja

        {% if variable is defined %}
            value of variable: {{ variable }}
        {% else %}
            variable is not defined
        {% endif %}

    See the :func:`default` filter for a simple way to set undefined
    variables.
    """
    return not isinstance(value, Undefined)


def test_undefined(value):
    """Like :func:`defined` but the other way round."""
    return isinstance(value, Undefined)


def test_none(value):
    """Return true if the variable is none."""
    return value is None


def test_lower(value):
    """Return true if the variable is lowercased."""
    return unicode(value).islower()


def test_upper(value):
    """Return true if the variable is uppercased."""
    return unicode(value).isupper()


def test_string(value):
    """Return true if the object is a string."""
    return isinstance(value, basestring)


def test_number(value):
    """Return true if the variable is a number."""
    return isinstance(value, (int, long, float, complex))


def test_sequence(value):
    """Return true if the variable is a sequence. Sequences are variables
    that are iterable.
    """
    try:
        len(value)
        value.__getitem__
    except:
        return False
    return True


def test_sameas(value, other):
    """Check if an object points to the same memory address than another
    object:

    .. sourcecode:: jinja

        {% if foo.attribute is sameas false %}
            the foo attribute really is the `False` singleton
        {% endif %}
    """
    return value is other


def test_iterable(value):
    """Check if it's possible to iterate over an object."""
    try:
        iter(value)
    except TypeError:
        return False
    return True


def test_escaped(value):
    """Check if the value is escaped."""
    return hasattr(value, '__html__')


TESTS = {
    'odd':              test_odd,
    'even':             test_even,
    'divisibleby':      test_divisibleby,
    'defined':          test_defined,
    'undefined':        test_undefined,
    'none':             test_none,
    'lower':            test_lower,
    'upper':            test_upper,
    'string':           test_string,
    'number':           test_number,
    'sequence':         test_sequence,
    'iterable':         test_iterable,
    'callable':         test_callable,
    'sameas':           test_sameas,
    'escaped':          test_escaped
}

########NEW FILE########
__FILENAME__ = api
# -*- coding: utf-8 -*-
"""
    jinja2.testsuite.api
    ~~~~~~~~~~~~~~~~~~~~

    Tests the public API and related stuff.

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD, see LICENSE for more details.
"""
import unittest

from jinja2.testsuite import JinjaTestCase

from jinja2 import Environment, Undefined, DebugUndefined, \
     StrictUndefined, UndefinedError, meta, \
     is_undefined, Template, DictLoader
from jinja2.utils import Cycler

env = Environment()


class ExtendedAPITestCase(JinjaTestCase):

    def test_item_and_attribute(self):
        from jinja2.sandbox import SandboxedEnvironment

        for env in Environment(), SandboxedEnvironment():
            # the |list is necessary for python3
            tmpl = env.from_string('{{ foo.items()|list }}')
            assert tmpl.render(foo={'items': 42}) == "[('items', 42)]"
            tmpl = env.from_string('{{ foo|attr("items")()|list }}')
            assert tmpl.render(foo={'items': 42}) == "[('items', 42)]"
            tmpl = env.from_string('{{ foo["items"] }}')
            assert tmpl.render(foo={'items': 42}) == '42'

    def test_finalizer(self):
        def finalize_none_empty(value):
            if value is None:
                value = u''
            return value
        env = Environment(finalize=finalize_none_empty)
        tmpl = env.from_string('{% for item in seq %}|{{ item }}{% endfor %}')
        assert tmpl.render(seq=(None, 1, "foo")) == '||1|foo'
        tmpl = env.from_string('<{{ none }}>')
        assert tmpl.render() == '<>'

    def test_cycler(self):
        items = 1, 2, 3
        c = Cycler(*items)
        for item in items + items:
            assert c.current == item
            assert c.next() == item
        c.next()
        assert c.current == 2
        c.reset()
        assert c.current == 1

    def test_expressions(self):
        expr = env.compile_expression("foo")
        assert expr() is None
        assert expr(foo=42) == 42
        expr2 = env.compile_expression("foo", undefined_to_none=False)
        assert is_undefined(expr2())

        expr = env.compile_expression("42 + foo")
        assert expr(foo=42) == 84

    def test_template_passthrough(self):
        t = Template('Content')
        assert env.get_template(t) is t
        assert env.select_template([t]) is t
        assert env.get_or_select_template([t]) is t
        assert env.get_or_select_template(t) is t

    def test_autoescape_autoselect(self):
        def select_autoescape(name):
            if name is None or '.' not in name:
                return False
            return name.endswith('.html')
        env = Environment(autoescape=select_autoescape,
                          loader=DictLoader({
            'test.txt':     '{{ foo }}',
            'test.html':    '{{ foo }}'
        }))
        t = env.get_template('test.txt')
        assert t.render(foo='<foo>') == '<foo>'
        t = env.get_template('test.html')
        assert t.render(foo='<foo>') == '&lt;foo&gt;'
        t = env.from_string('{{ foo }}')
        assert t.render(foo='<foo>') == '<foo>'


class MetaTestCase(JinjaTestCase):

    def test_find_undeclared_variables(self):
        ast = env.parse('{% set foo = 42 %}{{ bar + foo }}')
        x = meta.find_undeclared_variables(ast)
        assert x == set(['bar'])

        ast = env.parse('{% set foo = 42 %}{{ bar + foo }}'
                        '{% macro meh(x) %}{{ x }}{% endmacro %}'
                        '{% for item in seq %}{{ muh(item) + meh(seq) }}{% endfor %}')
        x = meta.find_undeclared_variables(ast)
        assert x == set(['bar', 'seq', 'muh'])

    def test_find_refererenced_templates(self):
        ast = env.parse('{% extends "layout.html" %}{% include helper %}')
        i = meta.find_referenced_templates(ast)
        assert i.next() == 'layout.html'
        assert i.next() is None
        assert list(i) == []

        ast = env.parse('{% extends "layout.html" %}'
                        '{% from "test.html" import a, b as c %}'
                        '{% import "meh.html" as meh %}'
                        '{% include "muh.html" %}')
        i = meta.find_referenced_templates(ast)
        assert list(i) == ['layout.html', 'test.html', 'meh.html', 'muh.html']

    def test_find_included_templates(self):
        ast = env.parse('{% include ["foo.html", "bar.html"] %}')
        i = meta.find_referenced_templates(ast)
        assert list(i) == ['foo.html', 'bar.html']

        ast = env.parse('{% include ("foo.html", "bar.html") %}')
        i = meta.find_referenced_templates(ast)
        assert list(i) == ['foo.html', 'bar.html']

        ast = env.parse('{% include ["foo.html", "bar.html", foo] %}')
        i = meta.find_referenced_templates(ast)
        assert list(i) == ['foo.html', 'bar.html', None]

        ast = env.parse('{% include ("foo.html", "bar.html", foo) %}')
        i = meta.find_referenced_templates(ast)
        assert list(i) == ['foo.html', 'bar.html', None]


class StreamingTestCase(JinjaTestCase):

    def test_basic_streaming(self):
        tmpl = env.from_string("<ul>{% for item in seq %}<li>{{ loop.index "
                               "}} - {{ item }}</li>{%- endfor %}</ul>")
        stream = tmpl.stream(seq=range(4))
        self.assert_equal(stream.next(), '<ul>')
        self.assert_equal(stream.next(), '<li>1 - 0</li>')
        self.assert_equal(stream.next(), '<li>2 - 1</li>')
        self.assert_equal(stream.next(), '<li>3 - 2</li>')
        self.assert_equal(stream.next(), '<li>4 - 3</li>')
        self.assert_equal(stream.next(), '</ul>')

    def test_buffered_streaming(self):
        tmpl = env.from_string("<ul>{% for item in seq %}<li>{{ loop.index "
                               "}} - {{ item }}</li>{%- endfor %}</ul>")
        stream = tmpl.stream(seq=range(4))
        stream.enable_buffering(size=3)
        self.assert_equal(stream.next(), u'<ul><li>1 - 0</li><li>2 - 1</li>')
        self.assert_equal(stream.next(), u'<li>3 - 2</li><li>4 - 3</li></ul>')

    def test_streaming_behavior(self):
        tmpl = env.from_string("")
        stream = tmpl.stream()
        assert not stream.buffered
        stream.enable_buffering(20)
        assert stream.buffered
        stream.disable_buffering()
        assert not stream.buffered


class UndefinedTestCase(JinjaTestCase):

    def test_stopiteration_is_undefined(self):
        def test():
            raise StopIteration()
        t = Template('A{{ test() }}B')
        assert t.render(test=test) == 'AB'
        t = Template('A{{ test().missingattribute }}B')
        self.assert_raises(UndefinedError, t.render, test=test)

    def test_undefined_and_special_attributes(self):
        try:
            Undefined('Foo').__dict__
        except AttributeError:
            pass
        else:
            assert False, "Expected actual attribute error"

    def test_default_undefined(self):
        env = Environment(undefined=Undefined)
        self.assert_equal(env.from_string('{{ missing }}').render(), u'')
        self.assert_raises(UndefinedError,
                           env.from_string('{{ missing.attribute }}').render)
        self.assert_equal(env.from_string('{{ missing|list }}').render(), '[]')
        self.assert_equal(env.from_string('{{ missing is not defined }}').render(), 'True')
        self.assert_equal(env.from_string('{{ foo.missing }}').render(foo=42), '')
        self.assert_equal(env.from_string('{{ not missing }}').render(), 'True')

    def test_debug_undefined(self):
        env = Environment(undefined=DebugUndefined)
        self.assert_equal(env.from_string('{{ missing }}').render(), '{{ missing }}')
        self.assert_raises(UndefinedError,
                           env.from_string('{{ missing.attribute }}').render)
        self.assert_equal(env.from_string('{{ missing|list }}').render(), '[]')
        self.assert_equal(env.from_string('{{ missing is not defined }}').render(), 'True')
        self.assert_equal(env.from_string('{{ foo.missing }}').render(foo=42),
                          u"{{ no such element: int object['missing'] }}")
        self.assert_equal(env.from_string('{{ not missing }}').render(), 'True')

    def test_strict_undefined(self):
        env = Environment(undefined=StrictUndefined)
        self.assert_raises(UndefinedError, env.from_string('{{ missing }}').render)
        self.assert_raises(UndefinedError, env.from_string('{{ missing.attribute }}').render)
        self.assert_raises(UndefinedError, env.from_string('{{ missing|list }}').render)
        self.assert_equal(env.from_string('{{ missing is not defined }}').render(), 'True')
        self.assert_raises(UndefinedError, env.from_string('{{ foo.missing }}').render, foo=42)
        self.assert_raises(UndefinedError, env.from_string('{{ not missing }}').render)

    def test_indexing_gives_undefined(self):
        t = Template("{{ var[42].foo }}")
        self.assert_raises(UndefinedError, t.render, var=0)

    def test_none_gives_proper_error(self):
        try:
            Environment().getattr(None, 'split')()
        except UndefinedError, e:
            assert e.message == "'None' has no attribute 'split'"
        else:
            assert False, 'expected exception'

    def test_object_repr(self):
        try:
            Undefined(obj=42, name='upper')()
        except UndefinedError, e:
            assert e.message == "'int object' has no attribute 'upper'"
        else:
            assert False, 'expected exception'


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(ExtendedAPITestCase))
    suite.addTest(unittest.makeSuite(MetaTestCase))
    suite.addTest(unittest.makeSuite(StreamingTestCase))
    suite.addTest(unittest.makeSuite(UndefinedTestCase))
    return suite

########NEW FILE########
__FILENAME__ = core_tags
# -*- coding: utf-8 -*-
"""
    jinja2.testsuite.core_tags
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the core tags like for and if.

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD, see LICENSE for more details.
"""
import unittest

from jinja2.testsuite import JinjaTestCase

from jinja2 import Environment, TemplateSyntaxError, UndefinedError, \
     DictLoader

env = Environment()


class ForLoopTestCase(JinjaTestCase):

    def test_simple(self):
        tmpl = env.from_string('{% for item in seq %}{{ item }}{% endfor %}')
        assert tmpl.render(seq=range(10)) == '0123456789'

    def test_else(self):
        tmpl = env.from_string('{% for item in seq %}XXX{% else %}...{% endfor %}')
        assert tmpl.render() == '...'

    def test_empty_blocks(self):
        tmpl = env.from_string('<{% for item in seq %}{% else %}{% endfor %}>')
        assert tmpl.render() == '<>'

    def test_context_vars(self):
        tmpl = env.from_string('''{% for item in seq -%}
        {{ loop.index }}|{{ loop.index0 }}|{{ loop.revindex }}|{{
            loop.revindex0 }}|{{ loop.first }}|{{ loop.last }}|{{
           loop.length }}###{% endfor %}''')
        one, two, _ = tmpl.render(seq=[0, 1]).split('###')
        (one_index, one_index0, one_revindex, one_revindex0, one_first,
         one_last, one_length) = one.split('|')
        (two_index, two_index0, two_revindex, two_revindex0, two_first,
         two_last, two_length) = two.split('|')

        assert int(one_index) == 1 and int(two_index) == 2
        assert int(one_index0) == 0 and int(two_index0) == 1
        assert int(one_revindex) == 2 and int(two_revindex) == 1
        assert int(one_revindex0) == 1 and int(two_revindex0) == 0
        assert one_first == 'True' and two_first == 'False'
        assert one_last == 'False' and two_last == 'True'
        assert one_length == two_length == '2'

    def test_cycling(self):
        tmpl = env.from_string('''{% for item in seq %}{{
            loop.cycle('<1>', '<2>') }}{% endfor %}{%
            for item in seq %}{{ loop.cycle(*through) }}{% endfor %}''')
        output = tmpl.render(seq=range(4), through=('<1>', '<2>'))
        assert output == '<1><2>' * 4

    def test_scope(self):
        tmpl = env.from_string('{% for item in seq %}{% endfor %}{{ item }}')
        output = tmpl.render(seq=range(10))
        assert not output

    def test_varlen(self):
        def inner():
            for item in range(5):
                yield item
        tmpl = env.from_string('{% for item in iter %}{{ item }}{% endfor %}')
        output = tmpl.render(iter=inner())
        assert output == '01234'

    def test_noniter(self):
        tmpl = env.from_string('{% for item in none %}...{% endfor %}')
        self.assert_raises(TypeError, tmpl.render)

    def test_recursive(self):
        tmpl = env.from_string('''{% for item in seq recursive -%}
            [{{ item.a }}{% if item.b %}<{{ loop(item.b) }}>{% endif %}]
        {%- endfor %}''')
        assert tmpl.render(seq=[
            dict(a=1, b=[dict(a=1), dict(a=2)]),
            dict(a=2, b=[dict(a=1), dict(a=2)]),
            dict(a=3, b=[dict(a='a')])
        ]) == '[1<[1][2]>][2<[1][2]>][3<[a]>]'

    def test_looploop(self):
        tmpl = env.from_string('''{% for row in table %}
            {%- set rowloop = loop -%}
            {% for cell in row -%}
                [{{ rowloop.index }}|{{ loop.index }}]
            {%- endfor %}
        {%- endfor %}''')
        assert tmpl.render(table=['ab', 'cd']) == '[1|1][1|2][2|1][2|2]'

    def test_reversed_bug(self):
        tmpl = env.from_string('{% for i in items %}{{ i }}'
                               '{% if not loop.last %}'
                               ',{% endif %}{% endfor %}')
        assert tmpl.render(items=reversed([3, 2, 1])) == '1,2,3'

    def test_loop_errors(self):
        tmpl = env.from_string('''{% for item in [1] if loop.index
                                      == 0 %}...{% endfor %}''')
        self.assert_raises(UndefinedError, tmpl.render)
        tmpl = env.from_string('''{% for item in [] %}...{% else
            %}{{ loop }}{% endfor %}''')
        assert tmpl.render() == ''

    def test_loop_filter(self):
        tmpl = env.from_string('{% for item in range(10) if item '
                               'is even %}[{{ item }}]{% endfor %}')
        assert tmpl.render() == '[0][2][4][6][8]'
        tmpl = env.from_string('''
            {%- for item in range(10) if item is even %}[{{
                loop.index }}:{{ item }}]{% endfor %}''')
        assert tmpl.render() == '[1:0][2:2][3:4][4:6][5:8]'

    def test_loop_unassignable(self):
        self.assert_raises(TemplateSyntaxError, env.from_string,
                           '{% for loop in seq %}...{% endfor %}')

    def test_scoped_special_var(self):
        t = env.from_string('{% for s in seq %}[{{ loop.first }}{% for c in s %}'
                            '|{{ loop.first }}{% endfor %}]{% endfor %}')
        assert t.render(seq=('ab', 'cd')) == '[True|True|False][False|True|False]'

    def test_scoped_loop_var(self):
        t = env.from_string('{% for x in seq %}{{ loop.first }}'
                            '{% for y in seq %}{% endfor %}{% endfor %}')
        assert t.render(seq='ab') == 'TrueFalse'
        t = env.from_string('{% for x in seq %}{% for y in seq %}'
                            '{{ loop.first }}{% endfor %}{% endfor %}')
        assert t.render(seq='ab') == 'TrueFalseTrueFalse'

    def test_recursive_empty_loop_iter(self):
        t = env.from_string('''
        {%- for item in foo recursive -%}{%- endfor -%}
        ''')
        assert t.render(dict(foo=[])) == ''

    def test_call_in_loop(self):
        t = env.from_string('''
        {%- macro do_something() -%}
            [{{ caller() }}]
        {%- endmacro %}

        {%- for i in [1, 2, 3] %}
            {%- call do_something() -%}
                {{ i }}
            {%- endcall %}
        {%- endfor -%}
        ''')
        assert t.render() == '[1][2][3]'

    def test_scoping_bug(self):
        t = env.from_string('''
        {%- for item in foo %}...{{ item }}...{% endfor %}
        {%- macro item(a) %}...{{ a }}...{% endmacro %}
        {{- item(2) -}}
        ''')
        assert t.render(foo=(1,)) == '...1......2...'

    def test_unpacking(self):
        tmpl = env.from_string('{% for a, b, c in [[1, 2, 3]] %}'
            '{{ a }}|{{ b }}|{{ c }}{% endfor %}')
        assert tmpl.render() == '1|2|3'


class IfConditionTestCase(JinjaTestCase):

    def test_simple(self):
        tmpl = env.from_string('''{% if true %}...{% endif %}''')
        assert tmpl.render() == '...'

    def test_elif(self):
        tmpl = env.from_string('''{% if false %}XXX{% elif true
            %}...{% else %}XXX{% endif %}''')
        assert tmpl.render() == '...'

    def test_else(self):
        tmpl = env.from_string('{% if false %}XXX{% else %}...{% endif %}')
        assert tmpl.render() == '...'

    def test_empty(self):
        tmpl = env.from_string('[{% if true %}{% else %}{% endif %}]')
        assert tmpl.render() == '[]'

    def test_complete(self):
        tmpl = env.from_string('{% if a %}A{% elif b %}B{% elif c == d %}'
                               'C{% else %}D{% endif %}')
        assert tmpl.render(a=0, b=False, c=42, d=42.0) == 'C'

    def test_no_scope(self):
        tmpl = env.from_string('{% if a %}{% set foo = 1 %}{% endif %}{{ foo }}')
        assert tmpl.render(a=True) == '1'
        tmpl = env.from_string('{% if true %}{% set foo = 1 %}{% endif %}{{ foo }}')
        assert tmpl.render() == '1'


class MacrosTestCase(JinjaTestCase):
    env = Environment(trim_blocks=True)

    def test_simple(self):
        tmpl = self.env.from_string('''\
{% macro say_hello(name) %}Hello {{ name }}!{% endmacro %}
{{ say_hello('Peter') }}''')
        assert tmpl.render() == 'Hello Peter!'

    def test_scoping(self):
        tmpl = self.env.from_string('''\
{% macro level1(data1) %}
{% macro level2(data2) %}{{ data1 }}|{{ data2 }}{% endmacro %}
{{ level2('bar') }}{% endmacro %}
{{ level1('foo') }}''')
        assert tmpl.render() == 'foo|bar'

    def test_arguments(self):
        tmpl = self.env.from_string('''\
{% macro m(a, b, c='c', d='d') %}{{ a }}|{{ b }}|{{ c }}|{{ d }}{% endmacro %}
{{ m() }}|{{ m('a') }}|{{ m('a', 'b') }}|{{ m(1, 2, 3) }}''')
        assert tmpl.render() == '||c|d|a||c|d|a|b|c|d|1|2|3|d'

    def test_varargs(self):
        tmpl = self.env.from_string('''\
{% macro test() %}{{ varargs|join('|') }}{% endmacro %}\
{{ test(1, 2, 3) }}''')
        assert tmpl.render() == '1|2|3'

    def test_simple_call(self):
        tmpl = self.env.from_string('''\
{% macro test() %}[[{{ caller() }}]]{% endmacro %}\
{% call test() %}data{% endcall %}''')
        assert tmpl.render() == '[[data]]'

    def test_complex_call(self):
        tmpl = self.env.from_string('''\
{% macro test() %}[[{{ caller('data') }}]]{% endmacro %}\
{% call(data) test() %}{{ data }}{% endcall %}''')
        assert tmpl.render() == '[[data]]'

    def test_caller_undefined(self):
        tmpl = self.env.from_string('''\
{% set caller = 42 %}\
{% macro test() %}{{ caller is not defined }}{% endmacro %}\
{{ test() }}''')
        assert tmpl.render() == 'True'

    def test_include(self):
        self.env = Environment(loader=DictLoader({'include':
            '{% macro test(foo) %}[{{ foo }}]{% endmacro %}'}))
        tmpl = self.env.from_string('{% from "include" import test %}{{ test("foo") }}')
        assert tmpl.render() == '[foo]'

    def test_macro_api(self):
        tmpl = self.env.from_string('{% macro foo(a, b) %}{% endmacro %}'
                               '{% macro bar() %}{{ varargs }}{{ kwargs }}{% endmacro %}'
                               '{% macro baz() %}{{ caller() }}{% endmacro %}')
        assert tmpl.module.foo.arguments == ('a', 'b')
        assert tmpl.module.foo.defaults == ()
        assert tmpl.module.foo.name == 'foo'
        assert not tmpl.module.foo.caller
        assert not tmpl.module.foo.catch_kwargs
        assert not tmpl.module.foo.catch_varargs
        assert tmpl.module.bar.arguments == ()
        assert tmpl.module.bar.defaults == ()
        assert not tmpl.module.bar.caller
        assert tmpl.module.bar.catch_kwargs
        assert tmpl.module.bar.catch_varargs
        assert tmpl.module.baz.caller

    def test_callself(self):
        tmpl = self.env.from_string('{% macro foo(x) %}{{ x }}{% if x > 1 %}|'
                                    '{{ foo(x - 1) }}{% endif %}{% endmacro %}'
                                    '{{ foo(5) }}')
        assert tmpl.render() == '5|4|3|2|1'


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(ForLoopTestCase))
    suite.addTest(unittest.makeSuite(IfConditionTestCase))
    suite.addTest(unittest.makeSuite(MacrosTestCase))
    return suite

########NEW FILE########
__FILENAME__ = debug
# -*- coding: utf-8 -*-
"""
    jinja2.testsuite.debug
    ~~~~~~~~~~~~~~~~~~~~~~

    Tests the debug system.

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD, see LICENSE for more details.
"""
import sys
import unittest

from jinja2.testsuite import JinjaTestCase, filesystem_loader

from jinja2 import Environment, TemplateSyntaxError

env = Environment(loader=filesystem_loader)


class DebugTestCase(JinjaTestCase):

    if sys.version_info[:2] != (2, 4):
        def test_runtime_error(self):
            def test():
                tmpl.render(fail=lambda: 1 / 0)
            tmpl = env.get_template('broken.html')
            self.assert_traceback_matches(test, r'''
  File ".*?broken.html", line 2, in (top-level template code|<module>)
    \{\{ fail\(\) \}\}
  File ".*?debug.pyc?", line \d+, in <lambda>
    tmpl\.render\(fail=lambda: 1 / 0\)
ZeroDivisionError: (int(eger)? )?division (or modulo )?by zero
''')

    def test_syntax_error(self):
        # XXX: the .*? is necessary for python3 which does not hide
        # some of the stack frames we don't want to show.  Not sure
        # what's up with that, but that is not that critical.  Should
        # be fixed though.
        self.assert_traceback_matches(lambda: env.get_template('syntaxerror.html'), r'''(?sm)
  File ".*?syntaxerror.html", line 4, in (template|<module>)
    \{% endif %\}.*?
(jinja2\.exceptions\.)?TemplateSyntaxError: Encountered unknown tag 'endif'. Jinja was looking for the following tags: 'endfor' or 'else'. The innermost block that needs to be closed is 'for'.
    ''')

    def test_regular_syntax_error(self):
        def test():
            raise TemplateSyntaxError('wtf', 42)
        self.assert_traceback_matches(test, r'''
  File ".*debug.pyc?", line \d+, in test
    raise TemplateSyntaxError\('wtf', 42\)
(jinja2\.exceptions\.)?TemplateSyntaxError: wtf
  line 42''')


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(DebugTestCase))
    return suite

########NEW FILE########
__FILENAME__ = doctests
# -*- coding: utf-8 -*-
"""
    jinja2.testsuite.doctests
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    The doctests.  Collects all tests we want to test from
    the Jinja modules.

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD, see LICENSE for more details.
"""
import unittest
import doctest


def suite():
    from jinja2 import utils, sandbox, runtime, meta, loaders, \
        ext, environment, bccache, nodes
    suite = unittest.TestSuite()
    suite.addTest(doctest.DocTestSuite(utils))
    suite.addTest(doctest.DocTestSuite(sandbox))
    suite.addTest(doctest.DocTestSuite(runtime))
    suite.addTest(doctest.DocTestSuite(meta))
    suite.addTest(doctest.DocTestSuite(loaders))
    suite.addTest(doctest.DocTestSuite(ext))
    suite.addTest(doctest.DocTestSuite(environment))
    suite.addTest(doctest.DocTestSuite(bccache))
    suite.addTest(doctest.DocTestSuite(nodes))
    return suite

########NEW FILE########
__FILENAME__ = ext
# -*- coding: utf-8 -*-
"""
    jinja2.testsuite.ext
    ~~~~~~~~~~~~~~~~~~~~

    Tests for the extensions.

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD, see LICENSE for more details.
"""
import re
import unittest

from jinja2.testsuite import JinjaTestCase

from jinja2 import Environment, DictLoader, contextfunction, nodes
from jinja2.exceptions import TemplateAssertionError
from jinja2.ext import Extension
from jinja2.lexer import Token, count_newlines
from jinja2.utils import next

# 2.x / 3.x
try:
    from io import BytesIO
except ImportError:
    from StringIO import StringIO as BytesIO


importable_object = 23

_gettext_re = re.compile(r'_\((.*?)\)(?s)')


i18n_templates = {
    'master.html': '<title>{{ page_title|default(_("missing")) }}</title>'
                   '{% block body %}{% endblock %}',
    'child.html': '{% extends "master.html" %}{% block body %}'
                  '{% trans %}watch out{% endtrans %}{% endblock %}',
    'plural.html': '{% trans user_count %}One user online{% pluralize %}'
                   '{{ user_count }} users online{% endtrans %}',
    'stringformat.html': '{{ _("User: %(num)s")|format(num=user_count) }}'
}

newstyle_i18n_templates = {
    'master.html': '<title>{{ page_title|default(_("missing")) }}</title>'
                   '{% block body %}{% endblock %}',
    'child.html': '{% extends "master.html" %}{% block body %}'
                  '{% trans %}watch out{% endtrans %}{% endblock %}',
    'plural.html': '{% trans user_count %}One user online{% pluralize %}'
                   '{{ user_count }} users online{% endtrans %}',
    'stringformat.html': '{{ _("User: %(num)s", num=user_count) }}',
    'ngettext.html': '{{ ngettext("%(num)s apple", "%(num)s apples", apples) }}',
    'ngettext_long.html': '{% trans num=apples %}{{ num }} apple{% pluralize %}'
                          '{{ num }} apples{% endtrans %}',
    'transvars1.html': '{% trans %}User: {{ num }}{% endtrans %}',
    'transvars2.html': '{% trans num=count %}User: {{ num }}{% endtrans %}',
    'transvars3.html': '{% trans count=num %}User: {{ count }}{% endtrans %}',
    'novars.html': '{% trans %}%(hello)s{% endtrans %}',
    'vars.html': '{% trans %}{{ foo }}%(foo)s{% endtrans %}',
    'explicitvars.html': '{% trans foo="42" %}%(foo)s{% endtrans %}'
}


languages = {
    'de': {
        'missing':                      u'fehlend',
        'watch out':                    u'pass auf',
        'One user online':              u'Ein Benutzer online',
        '%(user_count)s users online':  u'%(user_count)s Benutzer online',
        'User: %(num)s':                u'Benutzer: %(num)s',
        'User: %(count)s':              u'Benutzer: %(count)s',
        '%(num)s apple':                u'%(num)s Apfel',
        '%(num)s apples':               u'%(num)s Äpfel'
    }
}


@contextfunction
def gettext(context, string):
    language = context.get('LANGUAGE', 'en')
    return languages.get(language, {}).get(string, string)


@contextfunction
def ngettext(context, s, p, n):
    language = context.get('LANGUAGE', 'en')
    if n != 1:
        return languages.get(language, {}).get(p, p)
    return languages.get(language, {}).get(s, s)


i18n_env = Environment(
    loader=DictLoader(i18n_templates),
    extensions=['jinja2.ext.i18n']
)
i18n_env.globals.update({
    '_':            gettext,
    'gettext':      gettext,
    'ngettext':     ngettext
})

newstyle_i18n_env = Environment(
    loader=DictLoader(newstyle_i18n_templates),
    extensions=['jinja2.ext.i18n']
)
newstyle_i18n_env.install_gettext_callables(gettext, ngettext, newstyle=True)

class TestExtension(Extension):
    tags = set(['test'])
    ext_attr = 42

    def parse(self, parser):
        return nodes.Output([self.call_method('_dump', [
            nodes.EnvironmentAttribute('sandboxed'),
            self.attr('ext_attr'),
            nodes.ImportedName(__name__ + '.importable_object'),
            nodes.ContextReference()
        ])]).set_lineno(next(parser.stream).lineno)

    def _dump(self, sandboxed, ext_attr, imported_object, context):
        return '%s|%s|%s|%s' % (
            sandboxed,
            ext_attr,
            imported_object,
            context.blocks
        )


class PreprocessorExtension(Extension):

    def preprocess(self, source, name, filename=None):
        return source.replace('[[TEST]]', '({{ foo }})')


class StreamFilterExtension(Extension):

    def filter_stream(self, stream):
        for token in stream:
            if token.type == 'data':
                for t in self.interpolate(token):
                    yield t
            else:
                yield token

    def interpolate(self, token):
        pos = 0
        end = len(token.value)
        lineno = token.lineno
        while 1:
            match = _gettext_re.search(token.value, pos)
            if match is None:
                break
            value = token.value[pos:match.start()]
            if value:
                yield Token(lineno, 'data', value)
            lineno += count_newlines(token.value)
            yield Token(lineno, 'variable_begin', None)
            yield Token(lineno, 'name', 'gettext')
            yield Token(lineno, 'lparen', None)
            yield Token(lineno, 'string', match.group(1))
            yield Token(lineno, 'rparen', None)
            yield Token(lineno, 'variable_end', None)
            pos = match.end()
        if pos < end:
            yield Token(lineno, 'data', token.value[pos:])


class ExtensionsTestCase(JinjaTestCase):

    def test_extend_late(self):
        env = Environment()
        env.add_extension('jinja2.ext.autoescape')
        t = env.from_string('{% autoescape true %}{{ "<test>" }}{% endautoescape %}')
        assert t.render() == '&lt;test&gt;'

    def test_loop_controls(self):
        env = Environment(extensions=['jinja2.ext.loopcontrols'])

        tmpl = env.from_string('''
            {%- for item in [1, 2, 3, 4] %}
                {%- if item % 2 == 0 %}{% continue %}{% endif -%}
                {{ item }}
            {%- endfor %}''')
        assert tmpl.render() == '13'

        tmpl = env.from_string('''
            {%- for item in [1, 2, 3, 4] %}
                {%- if item > 2 %}{% break %}{% endif -%}
                {{ item }}
            {%- endfor %}''')
        assert tmpl.render() == '12'

    def test_do(self):
        env = Environment(extensions=['jinja2.ext.do'])
        tmpl = env.from_string('''
            {%- set items = [] %}
            {%- for char in "foo" %}
                {%- do items.append(loop.index0 ~ char) %}
            {%- endfor %}{{ items|join(', ') }}''')
        assert tmpl.render() == '0f, 1o, 2o'

    def test_with(self):
        env = Environment(extensions=['jinja2.ext.with_'])
        tmpl = env.from_string('''\
        {% with a=42, b=23 -%}
            {{ a }} = {{ b }}
        {% endwith -%}
            {{ a }} = {{ b }}\
        ''')
        assert [x.strip() for x in tmpl.render(a=1, b=2).splitlines()] \
            == ['42 = 23', '1 = 2']

    def test_extension_nodes(self):
        env = Environment(extensions=[TestExtension])
        tmpl = env.from_string('{% test %}')
        assert tmpl.render() == 'False|42|23|{}'

    def test_identifier(self):
        assert TestExtension.identifier == __name__ + '.TestExtension'

    def test_rebinding(self):
        original = Environment(extensions=[TestExtension])
        overlay = original.overlay()
        for env in original, overlay:
            for ext in env.extensions.itervalues():
                assert ext.environment is env

    def test_preprocessor_extension(self):
        env = Environment(extensions=[PreprocessorExtension])
        tmpl = env.from_string('{[[TEST]]}')
        assert tmpl.render(foo=42) == '{(42)}'

    def test_streamfilter_extension(self):
        env = Environment(extensions=[StreamFilterExtension])
        env.globals['gettext'] = lambda x: x.upper()
        tmpl = env.from_string('Foo _(bar) Baz')
        out = tmpl.render()
        assert out == 'Foo BAR Baz'

    def test_extension_ordering(self):
        class T1(Extension):
            priority = 1
        class T2(Extension):
            priority = 2
        env = Environment(extensions=[T1, T2])
        ext = list(env.iter_extensions())
        assert ext[0].__class__ is T1
        assert ext[1].__class__ is T2


class InternationalizationTestCase(JinjaTestCase):

    def test_trans(self):
        tmpl = i18n_env.get_template('child.html')
        assert tmpl.render(LANGUAGE='de') == '<title>fehlend</title>pass auf'

    def test_trans_plural(self):
        tmpl = i18n_env.get_template('plural.html')
        assert tmpl.render(LANGUAGE='de', user_count=1) == 'Ein Benutzer online'
        assert tmpl.render(LANGUAGE='de', user_count=2) == '2 Benutzer online'

    def test_complex_plural(self):
        tmpl = i18n_env.from_string('{% trans foo=42, count=2 %}{{ count }} item{% '
                                    'pluralize count %}{{ count }} items{% endtrans %}')
        assert tmpl.render() == '2 items'
        self.assert_raises(TemplateAssertionError, i18n_env.from_string,
                           '{% trans foo %}...{% pluralize bar %}...{% endtrans %}')

    def test_trans_stringformatting(self):
        tmpl = i18n_env.get_template('stringformat.html')
        assert tmpl.render(LANGUAGE='de', user_count=5) == 'Benutzer: 5'

    def test_extract(self):
        from jinja2.ext import babel_extract
        source = BytesIO('''
        {{ gettext('Hello World') }}
        {% trans %}Hello World{% endtrans %}
        {% trans %}{{ users }} user{% pluralize %}{{ users }} users{% endtrans %}
        '''.encode('ascii')) # make python 3 happy
        assert list(babel_extract(source, ('gettext', 'ngettext', '_'), [], {})) == [
            (2, 'gettext', u'Hello World', []),
            (3, 'gettext', u'Hello World', []),
            (4, 'ngettext', (u'%(users)s user', u'%(users)s users', None), [])
        ]

    def test_comment_extract(self):
        from jinja2.ext import babel_extract
        source = BytesIO('''
        {# trans first #}
        {{ gettext('Hello World') }}
        {% trans %}Hello World{% endtrans %}{# trans second #}
        {#: third #}
        {% trans %}{{ users }} user{% pluralize %}{{ users }} users{% endtrans %}
        '''.encode('utf-8')) # make python 3 happy
        assert list(babel_extract(source, ('gettext', 'ngettext', '_'), ['trans', ':'], {})) == [
            (3, 'gettext', u'Hello World', ['first']),
            (4, 'gettext', u'Hello World', ['second']),
            (6, 'ngettext', (u'%(users)s user', u'%(users)s users', None), ['third'])
        ]


class NewstyleInternationalizationTestCase(JinjaTestCase):

    def test_trans(self):
        tmpl = newstyle_i18n_env.get_template('child.html')
        assert tmpl.render(LANGUAGE='de') == '<title>fehlend</title>pass auf'

    def test_trans_plural(self):
        tmpl = newstyle_i18n_env.get_template('plural.html')
        assert tmpl.render(LANGUAGE='de', user_count=1) == 'Ein Benutzer online'
        assert tmpl.render(LANGUAGE='de', user_count=2) == '2 Benutzer online'

    def test_complex_plural(self):
        tmpl = newstyle_i18n_env.from_string('{% trans foo=42, count=2 %}{{ count }} item{% '
                                    'pluralize count %}{{ count }} items{% endtrans %}')
        assert tmpl.render() == '2 items'
        self.assert_raises(TemplateAssertionError, i18n_env.from_string,
                           '{% trans foo %}...{% pluralize bar %}...{% endtrans %}')

    def test_trans_stringformatting(self):
        tmpl = newstyle_i18n_env.get_template('stringformat.html')
        assert tmpl.render(LANGUAGE='de', user_count=5) == 'Benutzer: 5'

    def test_newstyle_plural(self):
        tmpl = newstyle_i18n_env.get_template('ngettext.html')
        assert tmpl.render(LANGUAGE='de', apples=1) == '1 Apfel'
        assert tmpl.render(LANGUAGE='de', apples=5) == u'5 Äpfel'

    def test_autoescape_support(self):
        env = Environment(extensions=['jinja2.ext.autoescape',
                                      'jinja2.ext.i18n'])
        env.install_gettext_callables(lambda x: u'<strong>Wert: %(name)s</strong>',
                                      lambda s, p, n: s, newstyle=True)
        t = env.from_string('{% autoescape ae %}{{ gettext("foo", name='
                            '"<test>") }}{% endautoescape %}')
        assert t.render(ae=True) == '<strong>Wert: &lt;test&gt;</strong>'
        assert t.render(ae=False) == '<strong>Wert: <test></strong>'

    def test_num_used_twice(self):
        tmpl = newstyle_i18n_env.get_template('ngettext_long.html')
        assert tmpl.render(apples=5, LANGUAGE='de') == u'5 Äpfel'

    def test_num_called_num(self):
        source = newstyle_i18n_env.compile('''
            {% trans num=3 %}{{ num }} apple{% pluralize
            %}{{ num }} apples{% endtrans %}
        ''', raw=True)
        # quite hacky, but the only way to properly test that.  The idea is
        # that the generated code does not pass num twice (although that
        # would work) for better performance.  This only works on the
        # newstyle gettext of course
        assert re.search(r"l_ngettext, u?'\%\(num\)s apple', u?'\%\(num\)s "
                         r"apples', 3", source) is not None

    def test_trans_vars(self):
        t1 = newstyle_i18n_env.get_template('transvars1.html')
        t2 = newstyle_i18n_env.get_template('transvars2.html')
        t3 = newstyle_i18n_env.get_template('transvars3.html')
        assert t1.render(num=1, LANGUAGE='de') == 'Benutzer: 1'
        assert t2.render(count=23, LANGUAGE='de') == 'Benutzer: 23'
        assert t3.render(num=42, LANGUAGE='de') == 'Benutzer: 42'

    def test_novars_vars_escaping(self):
        t = newstyle_i18n_env.get_template('novars.html')
        assert t.render() == '%(hello)s'
        t = newstyle_i18n_env.get_template('vars.html')
        assert t.render(foo='42') == '42%(foo)s'
        t = newstyle_i18n_env.get_template('explicitvars.html')
        assert t.render() == '%(foo)s'


class AutoEscapeTestCase(JinjaTestCase):

    def test_scoped_setting(self):
        env = Environment(extensions=['jinja2.ext.autoescape'],
                          autoescape=True)
        tmpl = env.from_string('''
            {{ "<HelloWorld>" }}
            {% autoescape false %}
                {{ "<HelloWorld>" }}
            {% endautoescape %}
            {{ "<HelloWorld>" }}
        ''')
        assert tmpl.render().split() == \
            [u'&lt;HelloWorld&gt;', u'<HelloWorld>', u'&lt;HelloWorld&gt;']

        env = Environment(extensions=['jinja2.ext.autoescape'],
                          autoescape=False)
        tmpl = env.from_string('''
            {{ "<HelloWorld>" }}
            {% autoescape true %}
                {{ "<HelloWorld>" }}
            {% endautoescape %}
            {{ "<HelloWorld>" }}
        ''')
        assert tmpl.render().split() == \
            [u'<HelloWorld>', u'&lt;HelloWorld&gt;', u'<HelloWorld>']

    def test_nonvolatile(self):
        env = Environment(extensions=['jinja2.ext.autoescape'],
                          autoescape=True)
        tmpl = env.from_string('{{ {"foo": "<test>"}|xmlattr|escape }}')
        assert tmpl.render() == ' foo="&lt;test&gt;"'
        tmpl = env.from_string('{% autoescape false %}{{ {"foo": "<test>"}'
                               '|xmlattr|escape }}{% endautoescape %}')
        assert tmpl.render() == ' foo=&#34;&amp;lt;test&amp;gt;&#34;'

    def test_volatile(self):
        env = Environment(extensions=['jinja2.ext.autoescape'],
                          autoescape=True)
        tmpl = env.from_string('{% autoescape foo %}{{ {"foo": "<test>"}'
                               '|xmlattr|escape }}{% endautoescape %}')
        assert tmpl.render(foo=False) == ' foo=&#34;&amp;lt;test&amp;gt;&#34;'
        assert tmpl.render(foo=True) == ' foo="&lt;test&gt;"'

    def test_scoping(self):
        env = Environment(extensions=['jinja2.ext.autoescape'])
        tmpl = env.from_string('{% autoescape true %}{% set x = "<x>" %}{{ x }}'
                               '{% endautoescape %}{{ x }}{{ "<y>" }}')
        assert tmpl.render(x=1) == '&lt;x&gt;1<y>'

    def test_volatile_scoping(self):
        env = Environment(extensions=['jinja2.ext.autoescape'])
        tmplsource = '''
        {% autoescape val %}
            {% macro foo(x) %}
                [{{ x }}]
            {% endmacro %}
            {{ foo().__class__.__name__ }}
        {% endautoescape %}
        {{ '<testing>' }}
        '''
        tmpl = env.from_string(tmplsource)
        assert tmpl.render(val=True).split()[0] == 'Markup'
        assert tmpl.render(val=False).split()[0] == unicode.__name__

        # looking at the source we should see <testing> there in raw
        # (and then escaped as well)
        env = Environment(extensions=['jinja2.ext.autoescape'])
        pysource = env.compile(tmplsource, raw=True)
        assert '<testing>\\n' in pysource

        env = Environment(extensions=['jinja2.ext.autoescape'],
                          autoescape=True)
        pysource = env.compile(tmplsource, raw=True)
        assert '&lt;testing&gt;\\n' in pysource


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(ExtensionsTestCase))
    suite.addTest(unittest.makeSuite(InternationalizationTestCase))
    suite.addTest(unittest.makeSuite(NewstyleInternationalizationTestCase))
    suite.addTest(unittest.makeSuite(AutoEscapeTestCase))
    return suite

########NEW FILE########
__FILENAME__ = filters
# -*- coding: utf-8 -*-
"""
    jinja2.testsuite.filters
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Tests for the jinja filters.

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD, see LICENSE for more details.
"""
import unittest
from jinja2.testsuite import JinjaTestCase

from jinja2 import Markup, Environment

env = Environment()


class FilterTestCase(JinjaTestCase):

    def test_capitalize(self):
        tmpl = env.from_string('{{ "foo bar"|capitalize }}')
        assert tmpl.render() == 'Foo bar'

    def test_center(self):
        tmpl = env.from_string('{{ "foo"|center(9) }}')
        assert tmpl.render() == '   foo   '

    def test_default(self):
        tmpl = env.from_string(
            "{{ missing|default('no') }}|{{ false|default('no') }}|"
            "{{ false|default('no', true) }}|{{ given|default('no') }}"
        )
        assert tmpl.render(given='yes') == 'no|False|no|yes'

    def test_dictsort(self):
        tmpl = env.from_string(
            '{{ foo|dictsort }}|'
            '{{ foo|dictsort(true) }}|'
            '{{ foo|dictsort(false, "value") }}'
        )
        out = tmpl.render(foo={"aa": 0, "b": 1, "c": 2, "AB": 3})
        assert out == ("[('aa', 0), ('AB', 3), ('b', 1), ('c', 2)]|"
                       "[('AB', 3), ('aa', 0), ('b', 1), ('c', 2)]|"
                       "[('aa', 0), ('b', 1), ('c', 2), ('AB', 3)]")

    def test_batch(self):
        tmpl = env.from_string("{{ foo|batch(3)|list }}|"
                               "{{ foo|batch(3, 'X')|list }}")
        out = tmpl.render(foo=range(10))
        assert out == ("[[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]|"
                       "[[0, 1, 2], [3, 4, 5], [6, 7, 8], [9, 'X', 'X']]")

    def test_slice(self):
        tmpl = env.from_string('{{ foo|slice(3)|list }}|'
                               '{{ foo|slice(3, "X")|list }}')
        out = tmpl.render(foo=range(10))
        assert out == ("[[0, 1, 2, 3], [4, 5, 6], [7, 8, 9]]|"
                       "[[0, 1, 2, 3], [4, 5, 6, 'X'], [7, 8, 9, 'X']]")

    def test_escape(self):
        tmpl = env.from_string('''{{ '<">&'|escape }}''')
        out = tmpl.render()
        assert out == '&lt;&#34;&gt;&amp;'

    def test_striptags(self):
        tmpl = env.from_string('''{{ foo|striptags }}''')
        out = tmpl.render(foo='  <p>just a small   \n <a href="#">'
                          'example</a> link</p>\n<p>to a webpage</p> '
                          '<!-- <p>and some commented stuff</p> -->')
        assert out == 'just a small example link to a webpage'

    def test_filesizeformat(self):
        tmpl = env.from_string(
            '{{ 100|filesizeformat }}|'
            '{{ 1000|filesizeformat }}|'
            '{{ 1000000|filesizeformat }}|'
            '{{ 1000000000|filesizeformat }}|'
            '{{ 1000000000000|filesizeformat }}|'
            '{{ 100|filesizeformat(true) }}|'
            '{{ 1000|filesizeformat(true) }}|'
            '{{ 1000000|filesizeformat(true) }}|'
            '{{ 1000000000|filesizeformat(true) }}|'
            '{{ 1000000000000|filesizeformat(true) }}'
        )
        out = tmpl.render()
        assert out == (
            '100 Bytes|0.0 kB|0.0 MB|0.0 GB|0.0 TB|100 Bytes|'
            '1000 Bytes|1.0 KiB|0.9 MiB|0.9 GiB'
        )

    def test_first(self):
        tmpl = env.from_string('{{ foo|first }}')
        out = tmpl.render(foo=range(10))
        assert out == '0'

    def test_float(self):
        tmpl = env.from_string('{{ "42"|float }}|'
                               '{{ "ajsghasjgd"|float }}|'
                               '{{ "32.32"|float }}')
        out = tmpl.render()
        assert out == '42.0|0.0|32.32'

    def test_format(self):
        tmpl = env.from_string('''{{ "%s|%s"|format("a", "b") }}''')
        out = tmpl.render()
        assert out == 'a|b'

    def test_indent(self):
        tmpl = env.from_string('{{ foo|indent(2) }}|{{ foo|indent(2, true) }}')
        text = '\n'.join([' '.join(['foo', 'bar'] * 2)] * 2)
        out = tmpl.render(foo=text)
        assert out == ('foo bar foo bar\n  foo bar foo bar|  '
                       'foo bar foo bar\n  foo bar foo bar')

    def test_int(self):
        tmpl = env.from_string('{{ "42"|int }}|{{ "ajsghasjgd"|int }}|'
                               '{{ "32.32"|int }}')
        out = tmpl.render()
        assert out == '42|0|32'

    def test_join(self):
        tmpl = env.from_string('{{ [1, 2, 3]|join("|") }}')
        out = tmpl.render()
        assert out == '1|2|3'

        env2 = Environment(autoescape=True)
        tmpl = env2.from_string('{{ ["<foo>", "<span>foo</span>"|safe]|join }}')
        assert tmpl.render() == '&lt;foo&gt;<span>foo</span>'

    def test_join_attribute(self):
        class User(object):
            def __init__(self, username):
                self.username = username
        tmpl = env.from_string('''{{ users|join(', ', 'username') }}''')
        assert tmpl.render(users=map(User, ['foo', 'bar'])) == 'foo, bar'

    def test_last(self):
        tmpl = env.from_string('''{{ foo|last }}''')
        out = tmpl.render(foo=range(10))
        assert out == '9'

    def test_length(self):
        tmpl = env.from_string('''{{ "hello world"|length }}''')
        out = tmpl.render()
        assert out == '11'

    def test_lower(self):
        tmpl = env.from_string('''{{ "FOO"|lower }}''')
        out = tmpl.render()
        assert out == 'foo'

    def test_pprint(self):
        from pprint import pformat
        tmpl = env.from_string('''{{ data|pprint }}''')
        data = range(1000)
        assert tmpl.render(data=data) == pformat(data)

    def test_random(self):
        tmpl = env.from_string('''{{ seq|random }}''')
        seq = range(100)
        for _ in range(10):
            assert int(tmpl.render(seq=seq)) in seq

    def test_reverse(self):
        tmpl = env.from_string('{{ "foobar"|reverse|join }}|'
                               '{{ [1, 2, 3]|reverse|list }}')
        assert tmpl.render() == 'raboof|[3, 2, 1]'

    def test_string(self):
        x = [1, 2, 3, 4, 5]
        tmpl = env.from_string('''{{ obj|string }}''')
        assert tmpl.render(obj=x) == unicode(x)

    def test_title(self):
        tmpl = env.from_string('''{{ "foo bar"|title }}''')
        assert tmpl.render() == "Foo Bar"

    def test_truncate(self):
        tmpl = env.from_string(
            '{{ data|truncate(15, true, ">>>") }}|'
            '{{ data|truncate(15, false, ">>>") }}|'
            '{{ smalldata|truncate(15) }}'
        )
        out = tmpl.render(data='foobar baz bar' * 1000,
                          smalldata='foobar baz bar')
        assert out == 'foobar baz barf>>>|foobar baz >>>|foobar baz bar'

    def test_upper(self):
        tmpl = env.from_string('{{ "foo"|upper }}')
        assert tmpl.render() == 'FOO'

    def test_urlize(self):
        tmpl = env.from_string('{{ "foo http://www.example.com/ bar"|urlize }}')
        assert tmpl.render() == 'foo <a href="http://www.example.com/">'\
                                'http://www.example.com/</a> bar'

    def test_wordcount(self):
        tmpl = env.from_string('{{ "foo bar baz"|wordcount }}')
        assert tmpl.render() == '3'

    def test_block(self):
        tmpl = env.from_string('{% filter lower|escape %}<HEHE>{% endfilter %}')
        assert tmpl.render() == '&lt;hehe&gt;'

    def test_chaining(self):
        tmpl = env.from_string('''{{ ['<foo>', '<bar>']|first|upper|escape }}''')
        assert tmpl.render() == '&lt;FOO&gt;'

    def test_sum(self):
        tmpl = env.from_string('''{{ [1, 2, 3, 4, 5, 6]|sum }}''')
        assert tmpl.render() == '21'

    def test_sum_attributes(self):
        tmpl = env.from_string('''{{ values|sum('value') }}''')
        assert tmpl.render(values=[
            {'value': 23},
            {'value': 1},
            {'value': 18},
        ]) == '42'

    def test_sum_attributes_nested(self):
        tmpl = env.from_string('''{{ values|sum('real.value') }}''')
        assert tmpl.render(values=[
            {'real': {'value': 23}},
            {'real': {'value': 1}},
            {'real': {'value': 18}},
        ]) == '42'

    def test_abs(self):
        tmpl = env.from_string('''{{ -1|abs }}|{{ 1|abs }}''')
        assert tmpl.render() == '1|1', tmpl.render()

    def test_round_positive(self):
        tmpl = env.from_string('{{ 2.7|round }}|{{ 2.1|round }}|'
                               "{{ 2.1234|round(3, 'floor') }}|"
                               "{{ 2.1|round(0, 'ceil') }}")
        assert tmpl.render() == '3.0|2.0|2.123|3.0', tmpl.render()

    def test_round_negative(self):
        tmpl = env.from_string('{{ 21.3|round(-1)}}|'
                               "{{ 21.3|round(-1, 'ceil')}}|"
                               "{{ 21.3|round(-1, 'floor')}}")
        assert tmpl.render() == '20.0|30.0|20.0',tmpl.render()

    def test_xmlattr(self):
        tmpl = env.from_string("{{ {'foo': 42, 'bar': 23, 'fish': none, "
                               "'spam': missing, 'blub:blub': '<?>'}|xmlattr }}")
        out = tmpl.render().split()
        assert len(out) == 3
        assert 'foo="42"' in out
        assert 'bar="23"' in out
        assert 'blub:blub="&lt;?&gt;"' in out

    def test_sort1(self):
        tmpl = env.from_string('{{ [2, 3, 1]|sort }}|{{ [2, 3, 1]|sort(true) }}')
        assert tmpl.render() == '[1, 2, 3]|[3, 2, 1]'

    def test_sort2(self):
        tmpl = env.from_string('{{ "".join(["c", "A", "b", "D"]|sort) }}')
        assert tmpl.render() == 'AbcD'

    def test_sort3(self):
        tmpl = env.from_string('''{{ ['foo', 'Bar', 'blah']|sort }}''')
        assert tmpl.render() == "['Bar', 'blah', 'foo']"

    def test_sort4(self):
        class Magic(object):
            def __init__(self, value):
                self.value = value
            def __unicode__(self):
                return unicode(self.value)
        tmpl = env.from_string('''{{ items|sort(attribute='value')|join }}''')
        assert tmpl.render(items=map(Magic, [3, 2, 4, 1])) == '1234'

    def test_groupby(self):
        tmpl = env.from_string('''
        {%- for grouper, list in [{'foo': 1, 'bar': 2},
                                  {'foo': 2, 'bar': 3},
                                  {'foo': 1, 'bar': 1},
                                  {'foo': 3, 'bar': 4}]|groupby('foo') -%}
            {{ grouper }}{% for x in list %}: {{ x.foo }}, {{ x.bar }}{% endfor %}|
        {%- endfor %}''')
        assert tmpl.render().split('|') == [
            "1: 1, 2: 1, 1",
            "2: 2, 3",
            "3: 3, 4",
            ""
        ]

    def test_groupby_multidot(self):
        class Date(object):
            def __init__(self, day, month, year):
                self.day = day
                self.month = month
                self.year = year
        class Article(object):
            def __init__(self, title, *date):
                self.date = Date(*date)
                self.title = title
        articles = [
            Article('aha', 1, 1, 1970),
            Article('interesting', 2, 1, 1970),
            Article('really?', 3, 1, 1970),
            Article('totally not', 1, 1, 1971)
        ]
        tmpl = env.from_string('''
        {%- for year, list in articles|groupby('date.year') -%}
            {{ year }}{% for x in list %}[{{ x.title }}]{% endfor %}|
        {%- endfor %}''')
        assert tmpl.render(articles=articles).split('|') == [
            '1970[aha][interesting][really?]',
            '1971[totally not]',
            ''
        ]

    def test_filtertag(self):
        tmpl = env.from_string("{% filter upper|replace('FOO', 'foo') %}"
                               "foobar{% endfilter %}")
        assert tmpl.render() == 'fooBAR'

    def test_replace(self):
        env = Environment()
        tmpl = env.from_string('{{ string|replace("o", 42) }}')
        assert tmpl.render(string='<foo>') == '<f4242>'
        env = Environment(autoescape=True)
        tmpl = env.from_string('{{ string|replace("o", 42) }}')
        assert tmpl.render(string='<foo>') == '&lt;f4242&gt;'
        tmpl = env.from_string('{{ string|replace("<", 42) }}')
        assert tmpl.render(string='<foo>') == '42foo&gt;'
        tmpl = env.from_string('{{ string|replace("o", ">x<") }}')
        assert tmpl.render(string=Markup('foo')) == 'f&gt;x&lt;&gt;x&lt;'

    def test_forceescape(self):
        tmpl = env.from_string('{{ x|forceescape }}')
        assert tmpl.render(x=Markup('<div />')) == u'&lt;div /&gt;'

    def test_safe(self):
        env = Environment(autoescape=True)
        tmpl = env.from_string('{{ "<div>foo</div>"|safe }}')
        assert tmpl.render() == '<div>foo</div>'
        tmpl = env.from_string('{{ "<div>foo</div>" }}')
        assert tmpl.render() == '&lt;div&gt;foo&lt;/div&gt;'


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(FilterTestCase))
    return suite

########NEW FILE########
__FILENAME__ = imports
# -*- coding: utf-8 -*-
"""
    jinja2.testsuite.imports
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Tests the import features (with includes).

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD, see LICENSE for more details.
"""
import unittest

from jinja2.testsuite import JinjaTestCase

from jinja2 import Environment, DictLoader
from jinja2.exceptions import TemplateNotFound, TemplatesNotFound


test_env = Environment(loader=DictLoader(dict(
    module='{% macro test() %}[{{ foo }}|{{ bar }}]{% endmacro %}',
    header='[{{ foo }}|{{ 23 }}]',
    o_printer='({{ o }})'
)))
test_env.globals['bar'] = 23


class ImportsTestCase(JinjaTestCase):

    def test_context_imports(self):
        t = test_env.from_string('{% import "module" as m %}{{ m.test() }}')
        assert t.render(foo=42) == '[|23]'
        t = test_env.from_string('{% import "module" as m without context %}{{ m.test() }}')
        assert t.render(foo=42) == '[|23]'
        t = test_env.from_string('{% import "module" as m with context %}{{ m.test() }}')
        assert t.render(foo=42) == '[42|23]'
        t = test_env.from_string('{% from "module" import test %}{{ test() }}')
        assert t.render(foo=42) == '[|23]'
        t = test_env.from_string('{% from "module" import test without context %}{{ test() }}')
        assert t.render(foo=42) == '[|23]'
        t = test_env.from_string('{% from "module" import test with context %}{{ test() }}')
        assert t.render(foo=42) == '[42|23]'

    def test_trailing_comma(self):
        test_env.from_string('{% from "foo" import bar, baz with context %}')
        test_env.from_string('{% from "foo" import bar, baz, with context %}')
        test_env.from_string('{% from "foo" import bar, with context %}')
        test_env.from_string('{% from "foo" import bar, with, context %}')
        test_env.from_string('{% from "foo" import bar, with with context %}')

    def test_exports(self):
        m = test_env.from_string('''
            {% macro toplevel() %}...{% endmacro %}
            {% macro __private() %}...{% endmacro %}
            {% set variable = 42 %}
            {% for item in [1] %}
                {% macro notthere() %}{% endmacro %}
            {% endfor %}
        ''').module
        assert m.toplevel() == '...'
        assert not hasattr(m, '__missing')
        assert m.variable == 42
        assert not hasattr(m, 'notthere')


class IncludesTestCase(JinjaTestCase):

    def test_context_include(self):
        t = test_env.from_string('{% include "header" %}')
        assert t.render(foo=42) == '[42|23]'
        t = test_env.from_string('{% include "header" with context %}')
        assert t.render(foo=42) == '[42|23]'
        t = test_env.from_string('{% include "header" without context %}')
        assert t.render(foo=42) == '[|23]'

    def test_choice_includes(self):
        t = test_env.from_string('{% include ["missing", "header"] %}')
        assert t.render(foo=42) == '[42|23]'

        t = test_env.from_string('{% include ["missing", "missing2"] ignore missing %}')
        assert t.render(foo=42) == ''

        t = test_env.from_string('{% include ["missing", "missing2"] %}')
        self.assert_raises(TemplateNotFound, t.render)
        try:
            t.render()
        except TemplatesNotFound, e:
            assert e.templates == ['missing', 'missing2']
            assert e.name == 'missing2'
        else:
            assert False, 'thou shalt raise'

        def test_includes(t, **ctx):
            ctx['foo'] = 42
            assert t.render(ctx) == '[42|23]'

        t = test_env.from_string('{% include ["missing", "header"] %}')
        test_includes(t)
        t = test_env.from_string('{% include x %}')
        test_includes(t, x=['missing', 'header'])
        t = test_env.from_string('{% include [x, "header"] %}')
        test_includes(t, x='missing')
        t = test_env.from_string('{% include x %}')
        test_includes(t, x='header')
        t = test_env.from_string('{% include x %}')
        test_includes(t, x='header')
        t = test_env.from_string('{% include [x] %}')
        test_includes(t, x='header')

    def test_include_ignoring_missing(self):
        t = test_env.from_string('{% include "missing" %}')
        self.assert_raises(TemplateNotFound, t.render)
        for extra in '', 'with context', 'without context':
            t = test_env.from_string('{% include "missing" ignore missing ' +
                                     extra + ' %}')
            assert t.render() == ''

    def test_context_include_with_overrides(self):
        env = Environment(loader=DictLoader(dict(
            main="{% for item in [1, 2, 3] %}{% include 'item' %}{% endfor %}",
            item="{{ item }}"
        )))
        assert env.get_template("main").render() == "123"

    def test_unoptimized_scopes(self):
        t = test_env.from_string("""
            {% macro outer(o) %}
            {% macro inner() %}
            {% include "o_printer" %}
            {% endmacro %}
            {{ inner() }}
            {% endmacro %}
            {{ outer("FOO") }}
        """)
        assert t.render().strip() == '(FOO)'


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(ImportsTestCase))
    suite.addTest(unittest.makeSuite(IncludesTestCase))
    return suite

########NEW FILE########
__FILENAME__ = inheritance
# -*- coding: utf-8 -*-
"""
    jinja2.testsuite.inheritance
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Tests the template inheritance feature.

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD, see LICENSE for more details.
"""
import unittest

from jinja2.testsuite import JinjaTestCase

from jinja2 import Environment, DictLoader


LAYOUTTEMPLATE = '''\
|{% block block1 %}block 1 from layout{% endblock %}
|{% block block2 %}block 2 from layout{% endblock %}
|{% block block3 %}
{% block block4 %}nested block 4 from layout{% endblock %}
{% endblock %}|'''

LEVEL1TEMPLATE = '''\
{% extends "layout" %}
{% block block1 %}block 1 from level1{% endblock %}'''

LEVEL2TEMPLATE = '''\
{% extends "level1" %}
{% block block2 %}{% block block5 %}nested block 5 from level2{%
endblock %}{% endblock %}'''

LEVEL3TEMPLATE = '''\
{% extends "level2" %}
{% block block5 %}block 5 from level3{% endblock %}
{% block block4 %}block 4 from level3{% endblock %}
'''

LEVEL4TEMPLATE = '''\
{% extends "level3" %}
{% block block3 %}block 3 from level4{% endblock %}
'''

WORKINGTEMPLATE = '''\
{% extends "layout" %}
{% block block1 %}
  {% if false %}
    {% block block2 %}
      this should workd
    {% endblock %}
  {% endif %}
{% endblock %}
'''

env = Environment(loader=DictLoader({
    'layout':       LAYOUTTEMPLATE,
    'level1':       LEVEL1TEMPLATE,
    'level2':       LEVEL2TEMPLATE,
    'level3':       LEVEL3TEMPLATE,
    'level4':       LEVEL4TEMPLATE,
    'working':      WORKINGTEMPLATE
}), trim_blocks=True)


class InheritanceTestCase(JinjaTestCase):

    def test_layout(self):
        tmpl = env.get_template('layout')
        assert tmpl.render() == ('|block 1 from layout|block 2 from '
                                 'layout|nested block 4 from layout|')

    def test_level1(self):
        tmpl = env.get_template('level1')
        assert tmpl.render() == ('|block 1 from level1|block 2 from '
                                 'layout|nested block 4 from layout|')

    def test_level2(self):
        tmpl = env.get_template('level2')
        assert tmpl.render() == ('|block 1 from level1|nested block 5 from '
                                 'level2|nested block 4 from layout|')

    def test_level3(self):
        tmpl = env.get_template('level3')
        assert tmpl.render() == ('|block 1 from level1|block 5 from level3|'
                                 'block 4 from level3|')

    def test_level4(sel):
        tmpl = env.get_template('level4')
        assert tmpl.render() == ('|block 1 from level1|block 5 from '
                                 'level3|block 3 from level4|')

    def test_super(self):
        env = Environment(loader=DictLoader({
            'a': '{% block intro %}INTRO{% endblock %}|'
                 'BEFORE|{% block data %}INNER{% endblock %}|AFTER',
            'b': '{% extends "a" %}{% block data %}({{ '
                 'super() }}){% endblock %}',
            'c': '{% extends "b" %}{% block intro %}--{{ '
                 'super() }}--{% endblock %}\n{% block data '
                 '%}[{{ super() }}]{% endblock %}'
        }))
        tmpl = env.get_template('c')
        assert tmpl.render() == '--INTRO--|BEFORE|[(INNER)]|AFTER'

    def test_working(self):
        tmpl = env.get_template('working')

    def test_reuse_blocks(self):
        tmpl = env.from_string('{{ self.foo() }}|{% block foo %}42'
                               '{% endblock %}|{{ self.foo() }}')
        assert tmpl.render() == '42|42|42'

    def test_preserve_blocks(self):
        env = Environment(loader=DictLoader({
            'a': '{% if false %}{% block x %}A{% endblock %}{% endif %}{{ self.x() }}',
            'b': '{% extends "a" %}{% block x %}B{{ super() }}{% endblock %}'
        }))
        tmpl = env.get_template('b')
        assert tmpl.render() == 'BA'

    def test_dynamic_inheritance(self):
        env = Environment(loader=DictLoader({
            'master1': 'MASTER1{% block x %}{% endblock %}',
            'master2': 'MASTER2{% block x %}{% endblock %}',
            'child': '{% extends master %}{% block x %}CHILD{% endblock %}'
        }))
        tmpl = env.get_template('child')
        for m in range(1, 3):
            assert tmpl.render(master='master%d' % m) == 'MASTER%dCHILD' % m

    def test_multi_inheritance(self):
        env = Environment(loader=DictLoader({
            'master1': 'MASTER1{% block x %}{% endblock %}',
            'master2': 'MASTER2{% block x %}{% endblock %}',
            'child': '''{% if master %}{% extends master %}{% else %}{% extends
                        'master1' %}{% endif %}{% block x %}CHILD{% endblock %}'''
        }))
        tmpl = env.get_template('child')
        assert tmpl.render(master='master2') == 'MASTER2CHILD'
        assert tmpl.render(master='master1') == 'MASTER1CHILD'
        assert tmpl.render() == 'MASTER1CHILD'

    def test_scoped_block(self):
        env = Environment(loader=DictLoader({
            'master.html': '{% for item in seq %}[{% block item scoped %}'
                           '{% endblock %}]{% endfor %}'
        }))
        t = env.from_string('{% extends "master.html" %}{% block item %}'
                            '{{ item }}{% endblock %}')
        assert t.render(seq=range(5)) == '[0][1][2][3][4]'

    def test_super_in_scoped_block(self):
        env = Environment(loader=DictLoader({
            'master.html': '{% for item in seq %}[{% block item scoped %}'
                           '{{ item }}{% endblock %}]{% endfor %}'
        }))
        t = env.from_string('{% extends "master.html" %}{% block item %}'
                            '{{ super() }}|{{ item * 2 }}{% endblock %}')
        assert t.render(seq=range(5)) == '[0|0][1|2][2|4][3|6][4|8]'

    def test_scoped_block_after_inheritance(self):
        env = Environment(loader=DictLoader({
            'layout.html': '''
            {% block useless %}{% endblock %}
            ''',
            'index.html': '''
            {%- extends 'layout.html' %}
            {% from 'helpers.html' import foo with context %}
            {% block useless %}
                {% for x in [1, 2, 3] %}
                    {% block testing scoped %}
                        {{ foo(x) }}
                    {% endblock %}
                {% endfor %}
            {% endblock %}
            ''',
            'helpers.html': '''
            {% macro foo(x) %}{{ the_foo + x }}{% endmacro %}
            '''
        }))
        rv = env.get_template('index.html').render(the_foo=42).split()
        assert rv == ['43', '44', '45']


class BugFixTestCase(JinjaTestCase):

    def test_fixed_macro_scoping_bug(self):
        assert Environment(loader=DictLoader({
            'test.html': '''\
        {% extends 'details.html' %}

        {% macro my_macro() %}
        my_macro
        {% endmacro %}

        {% block inner_box %}
            {{ my_macro() }}
        {% endblock %}
            ''',
            'details.html': '''\
        {% extends 'standard.html' %}

        {% macro my_macro() %}
        my_macro
        {% endmacro %}

        {% block content %}
            {% block outer_box %}
                outer_box
                {% block inner_box %}
                    inner_box
                {% endblock %}
            {% endblock %}
        {% endblock %}
        ''',
            'standard.html': '''
        {% block content %}&nbsp;{% endblock %}
        '''
        })).get_template("test.html").render().split() == [u'outer_box', u'my_macro']


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(InheritanceTestCase))
    suite.addTest(unittest.makeSuite(BugFixTestCase))
    return suite

########NEW FILE########
__FILENAME__ = lexnparse
# -*- coding: utf-8 -*-
"""
    jinja2.testsuite.lexnparse
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    All the unittests regarding lexing, parsing and syntax.

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD, see LICENSE for more details.
"""
import sys
import unittest

from jinja2.testsuite import JinjaTestCase

from jinja2 import Environment, Template, TemplateSyntaxError, \
     UndefinedError, nodes

env = Environment()


# how does a string look like in jinja syntax?
if sys.version_info < (3, 0):
    def jinja_string_repr(string):
        return repr(string)[1:]
else:
    jinja_string_repr = repr


class LexerTestCase(JinjaTestCase):

    def test_raw1(self):
        tmpl = env.from_string('{% raw %}foo{% endraw %}|'
                               '{%raw%}{{ bar }}|{% baz %}{%       endraw    %}')
        assert tmpl.render() == 'foo|{{ bar }}|{% baz %}'

    def test_raw2(self):
        tmpl = env.from_string('1  {%- raw -%}   2   {%- endraw -%}   3')
        assert tmpl.render() == '123'

    def test_balancing(self):
        env = Environment('{%', '%}', '${', '}')
        tmpl = env.from_string('''{% for item in seq
            %}${{'foo': item}|upper}{% endfor %}''')
        assert tmpl.render(seq=range(3)) == "{'FOO': 0}{'FOO': 1}{'FOO': 2}"

    def test_comments(self):
        env = Environment('<!--', '-->', '{', '}')
        tmpl = env.from_string('''\
<ul>
<!--- for item in seq -->
  <li>{item}</li>
<!--- endfor -->
</ul>''')
        assert tmpl.render(seq=range(3)) == ("<ul>\n  <li>0</li>\n  "
                                             "<li>1</li>\n  <li>2</li>\n</ul>")

    def test_string_escapes(self):
        for char in u'\0', u'\u2668', u'\xe4', u'\t', u'\r', u'\n':
            tmpl = env.from_string('{{ %s }}' % jinja_string_repr(char))
            assert tmpl.render() == char
        assert env.from_string('{{ "\N{HOT SPRINGS}" }}').render() == u'\u2668'

    def test_bytefallback(self):
        from pprint import pformat
        tmpl = env.from_string(u'''{{ 'foo'|pprint }}|{{ 'bär'|pprint }}''')
        assert tmpl.render() == pformat('foo') + '|' + pformat(u'bär')

    def test_operators(self):
        from jinja2.lexer import operators
        for test, expect in operators.iteritems():
            if test in '([{}])':
                continue
            stream = env.lexer.tokenize('{{ %s }}' % test)
            stream.next()
            assert stream.current.type == expect

    def test_normalizing(self):
        for seq in '\r', '\r\n', '\n':
            env = Environment(newline_sequence=seq)
            tmpl = env.from_string('1\n2\r\n3\n4\n')
            result = tmpl.render()
            assert result.replace(seq, 'X') == '1X2X3X4'


class ParserTestCase(JinjaTestCase):

    def test_php_syntax(self):
        env = Environment('<?', '?>', '<?=', '?>', '<!--', '-->')
        tmpl = env.from_string('''\
<!-- I'm a comment, I'm not interesting -->\
<? for item in seq -?>
    <?= item ?>
<?- endfor ?>''')
        assert tmpl.render(seq=range(5)) == '01234'

    def test_erb_syntax(self):
        env = Environment('<%', '%>', '<%=', '%>', '<%#', '%>')
        tmpl = env.from_string('''\
<%# I'm a comment, I'm not interesting %>\
<% for item in seq -%>
    <%= item %>
<%- endfor %>''')
        assert tmpl.render(seq=range(5)) == '01234'

    def test_comment_syntax(self):
        env = Environment('<!--', '-->', '${', '}', '<!--#', '-->')
        tmpl = env.from_string('''\
<!--# I'm a comment, I'm not interesting -->\
<!-- for item in seq --->
    ${item}
<!--- endfor -->''')
        assert tmpl.render(seq=range(5)) == '01234'

    def test_balancing(self):
        tmpl = env.from_string('''{{{'foo':'bar'}.foo}}''')
        assert tmpl.render() == 'bar'

    def test_start_comment(self):
        tmpl = env.from_string('''{# foo comment
and bar comment #}
{% macro blub() %}foo{% endmacro %}
{{ blub() }}''')
        assert tmpl.render().strip() == 'foo'

    def test_line_syntax(self):
        env = Environment('<%', '%>', '${', '}', '<%#', '%>', '%')
        tmpl = env.from_string('''\
<%# regular comment %>
% for item in seq:
    ${item}
% endfor''')
        assert [int(x.strip()) for x in tmpl.render(seq=range(5)).split()] == \
               range(5)

        env = Environment('<%', '%>', '${', '}', '<%#', '%>', '%', '##')
        tmpl = env.from_string('''\
<%# regular comment %>
% for item in seq:
    ${item} ## the rest of the stuff
% endfor''')
        assert [int(x.strip()) for x in tmpl.render(seq=range(5)).split()] == \
                range(5)

    def test_line_syntax_priority(self):
        # XXX: why is the whitespace there in front of the newline?
        env = Environment('{%', '%}', '${', '}', '/*', '*/', '##', '#')
        tmpl = env.from_string('''\
/* ignore me.
   I'm a multiline comment */
## for item in seq:
* ${item}          # this is just extra stuff
## endfor''')
        assert tmpl.render(seq=[1, 2]).strip() == '* 1\n* 2'
        env = Environment('{%', '%}', '${', '}', '/*', '*/', '#', '##')
        tmpl = env.from_string('''\
/* ignore me.
   I'm a multiline comment */
# for item in seq:
* ${item}          ## this is just extra stuff
    ## extra stuff i just want to ignore
# endfor''')
        assert tmpl.render(seq=[1, 2]).strip() == '* 1\n\n* 2'

    def test_error_messages(self):
        def assert_error(code, expected):
            try:
                Template(code)
            except TemplateSyntaxError, e:
                assert str(e) == expected, 'unexpected error message'
            else:
                assert False, 'that was suposed to be an error'

        assert_error('{% for item in seq %}...{% endif %}',
                     "Encountered unknown tag 'endif'. Jinja was looking "
                     "for the following tags: 'endfor' or 'else'. The "
                     "innermost block that needs to be closed is 'for'.")
        assert_error('{% if foo %}{% for item in seq %}...{% endfor %}{% endfor %}',
                     "Encountered unknown tag 'endfor'. Jinja was looking for "
                     "the following tags: 'elif' or 'else' or 'endif'. The "
                     "innermost block that needs to be closed is 'if'.")
        assert_error('{% if foo %}',
                     "Unexpected end of template. Jinja was looking for the "
                     "following tags: 'elif' or 'else' or 'endif'. The "
                     "innermost block that needs to be closed is 'if'.")
        assert_error('{% for item in seq %}',
                     "Unexpected end of template. Jinja was looking for the "
                     "following tags: 'endfor' or 'else'. The innermost block "
                     "that needs to be closed is 'for'.")
        assert_error('{% block foo-bar-baz %}',
                     "Block names in Jinja have to be valid Python identifiers "
                     "and may not contain hypens, use an underscore instead.")
        assert_error('{% unknown_tag %}',
                     "Encountered unknown tag 'unknown_tag'.")


class SyntaxTestCase(JinjaTestCase):

    def test_call(self):
        env = Environment()
        env.globals['foo'] = lambda a, b, c, e, g: a + b + c + e + g
        tmpl = env.from_string("{{ foo('a', c='d', e='f', *['b'], **{'g': 'h'}) }}")
        assert tmpl.render() == 'abdfh'

    def test_slicing(self):
        tmpl = env.from_string('{{ [1, 2, 3][:] }}|{{ [1, 2, 3][::-1] }}')
        assert tmpl.render() == '[1, 2, 3]|[3, 2, 1]'

    def test_attr(self):
        tmpl = env.from_string("{{ foo.bar }}|{{ foo['bar'] }}")
        assert tmpl.render(foo={'bar': 42}) == '42|42'

    def test_subscript(self):
        tmpl = env.from_string("{{ foo[0] }}|{{ foo[-1] }}")
        assert tmpl.render(foo=[0, 1, 2]) == '0|2'

    def test_tuple(self):
        tmpl = env.from_string('{{ () }}|{{ (1,) }}|{{ (1, 2) }}')
        assert tmpl.render() == '()|(1,)|(1, 2)'

    def test_math(self):
        tmpl = env.from_string('{{ (1 + 1 * 2) - 3 / 2 }}|{{ 2**3 }}')
        assert tmpl.render() == '1.5|8'

    def test_div(self):
        tmpl = env.from_string('{{ 3 // 2 }}|{{ 3 / 2 }}|{{ 3 % 2 }}')
        assert tmpl.render() == '1|1.5|1'

    def test_unary(self):
        tmpl = env.from_string('{{ +3 }}|{{ -3 }}')
        assert tmpl.render() == '3|-3'

    def test_concat(self):
        tmpl = env.from_string("{{ [1, 2] ~ 'foo' }}")
        assert tmpl.render() == '[1, 2]foo'

    def test_compare(self):
        tmpl = env.from_string('{{ 1 > 0 }}|{{ 1 >= 1 }}|{{ 2 < 3 }}|'
                               '{{ 2 == 2 }}|{{ 1 <= 1 }}')
        assert tmpl.render() == 'True|True|True|True|True'

    def test_inop(self):
        tmpl = env.from_string('{{ 1 in [1, 2, 3] }}|{{ 1 not in [1, 2, 3] }}')
        assert tmpl.render() == 'True|False'

    def test_literals(self):
        tmpl = env.from_string('{{ [] }}|{{ {} }}|{{ () }}')
        assert tmpl.render().lower() == '[]|{}|()'

    def test_bool(self):
        tmpl = env.from_string('{{ true and false }}|{{ false '
                               'or true }}|{{ not false }}')
        assert tmpl.render() == 'False|True|True'

    def test_grouping(self):
        tmpl = env.from_string('{{ (true and false) or (false and true) and not false }}')
        assert tmpl.render() == 'False'

    def test_django_attr(self):
        tmpl = env.from_string('{{ [1, 2, 3].0 }}|{{ [[1]].0.0 }}')
        assert tmpl.render() == '1|1'

    def test_conditional_expression(self):
        tmpl = env.from_string('''{{ 0 if true else 1 }}''')
        assert tmpl.render() == '0'

    def test_short_conditional_expression(self):
        tmpl = env.from_string('<{{ 1 if false }}>')
        assert tmpl.render() == '<>'

        tmpl = env.from_string('<{{ (1 if false).bar }}>')
        self.assert_raises(UndefinedError, tmpl.render)

    def test_filter_priority(self):
        tmpl = env.from_string('{{ "foo"|upper + "bar"|upper }}')
        assert tmpl.render() == 'FOOBAR'

    def test_function_calls(self):
        tests = [
            (True, '*foo, bar'),
            (True, '*foo, *bar'),
            (True, '*foo, bar=42'),
            (True, '**foo, *bar'),
            (True, '**foo, bar'),
            (False, 'foo, bar'),
            (False, 'foo, bar=42'),
            (False, 'foo, bar=23, *args'),
            (False, 'a, b=c, *d, **e'),
            (False, '*foo, **bar')
        ]
        for should_fail, sig in tests:
            if should_fail:
                self.assert_raises(TemplateSyntaxError,
                    env.from_string, '{{ foo(%s) }}' % sig)
            else:
                env.from_string('foo(%s)' % sig)

    def test_tuple_expr(self):
        for tmpl in [
            '{{ () }}',
            '{{ (1, 2) }}',
            '{{ (1, 2,) }}',
            '{{ 1, }}',
            '{{ 1, 2 }}',
            '{% for foo, bar in seq %}...{% endfor %}',
            '{% for x in foo, bar %}...{% endfor %}',
            '{% for x in foo, %}...{% endfor %}'
        ]:
            assert env.from_string(tmpl)

    def test_trailing_comma(self):
        tmpl = env.from_string('{{ (1, 2,) }}|{{ [1, 2,] }}|{{ {1: 2,} }}')
        assert tmpl.render().lower() == '(1, 2)|[1, 2]|{1: 2}'

    def test_block_end_name(self):
        env.from_string('{% block foo %}...{% endblock foo %}')
        self.assert_raises(TemplateSyntaxError, env.from_string,
                           '{% block x %}{% endblock y %}')

    def test_contant_casing(self):
        for const in True, False, None:
            tmpl = env.from_string('{{ %s }}|{{ %s }}|{{ %s }}' % (
                str(const), str(const).lower(), str(const).upper()
            ))
            assert tmpl.render() == '%s|%s|' % (const, const)

    def test_test_chaining(self):
        self.assert_raises(TemplateSyntaxError, env.from_string,
                           '{{ foo is string is sequence }}')
        env.from_string('{{ 42 is string or 42 is number }}'
            ).render() == 'True'

    def test_string_concatenation(self):
        tmpl = env.from_string('{{ "foo" "bar" "baz" }}')
        assert tmpl.render() == 'foobarbaz'

    def test_notin(self):
        bar = xrange(100)
        tmpl = env.from_string('''{{ not 42 in bar }}''')
        assert tmpl.render(bar=bar) == unicode(not 42 in bar)

    def test_implicit_subscribed_tuple(self):
        class Foo(object):
            def __getitem__(self, x):
                return x
        t = env.from_string('{{ foo[1, 2] }}')
        assert t.render(foo=Foo()) == u'(1, 2)'

    def test_raw2(self):
        tmpl = env.from_string('{% raw %}{{ FOO }} and {% BAR %}{% endraw %}')
        assert tmpl.render() == '{{ FOO }} and {% BAR %}'

    def test_const(self):
        tmpl = env.from_string('{{ true }}|{{ false }}|{{ none }}|'
                               '{{ none is defined }}|{{ missing is defined }}')
        assert tmpl.render() == 'True|False|None|True|False'

    def test_neg_filter_priority(self):
        node = env.parse('{{ -1|foo }}')
        assert isinstance(node.body[0].nodes[0], nodes.Filter)
        assert isinstance(node.body[0].nodes[0].node, nodes.Neg)

    def test_const_assign(self):
        constass1 = '''{% set true = 42 %}'''
        constass2 = '''{% for none in seq %}{% endfor %}'''
        for tmpl in constass1, constass2:
            self.assert_raises(TemplateSyntaxError, env.from_string, tmpl)

    def test_localset(self):
        tmpl = env.from_string('''{% set foo = 0 %}\
{% for item in [1, 2] %}{% set foo = 1 %}{% endfor %}\
{{ foo }}''')
        assert tmpl.render() == '0'

    def test_parse_unary(self):
        tmpl = env.from_string('{{ -foo["bar"] }}')
        assert tmpl.render(foo={'bar': 42}) == '-42'
        tmpl = env.from_string('{{ -foo["bar"]|abs }}')
        assert tmpl.render(foo={'bar': 42}) == '42'


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(LexerTestCase))
    suite.addTest(unittest.makeSuite(ParserTestCase))
    suite.addTest(unittest.makeSuite(SyntaxTestCase))
    return suite

########NEW FILE########
__FILENAME__ = loader
# -*- coding: utf-8 -*-
"""
    jinja2.testsuite.loader
    ~~~~~~~~~~~~~~~~~~~~~~~

    Test the loaders.

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD, see LICENSE for more details.
"""
import os
import sys
import tempfile
import shutil
import unittest

from jinja2.testsuite import JinjaTestCase, dict_loader, \
     package_loader, filesystem_loader, function_loader, \
     choice_loader, prefix_loader

from jinja2 import Environment, loaders
from jinja2.loaders import split_template_path
from jinja2.exceptions import TemplateNotFound


class LoaderTestCase(JinjaTestCase):

    def test_dict_loader(self):
        env = Environment(loader=dict_loader)
        tmpl = env.get_template('justdict.html')
        assert tmpl.render().strip() == 'FOO'
        self.assert_raises(TemplateNotFound, env.get_template, 'missing.html')

    def test_package_loader(self):
        env = Environment(loader=package_loader)
        tmpl = env.get_template('test.html')
        assert tmpl.render().strip() == 'BAR'
        self.assert_raises(TemplateNotFound, env.get_template, 'missing.html')

    def test_filesystem_loader(self):
        env = Environment(loader=filesystem_loader)
        tmpl = env.get_template('test.html')
        assert tmpl.render().strip() == 'BAR'
        tmpl = env.get_template('foo/test.html')
        assert tmpl.render().strip() == 'FOO'
        self.assert_raises(TemplateNotFound, env.get_template, 'missing.html')

    def test_choice_loader(self):
        env = Environment(loader=choice_loader)
        tmpl = env.get_template('justdict.html')
        assert tmpl.render().strip() == 'FOO'
        tmpl = env.get_template('test.html')
        assert tmpl.render().strip() == 'BAR'
        self.assert_raises(TemplateNotFound, env.get_template, 'missing.html')

    def test_function_loader(self):
        env = Environment(loader=function_loader)
        tmpl = env.get_template('justfunction.html')
        assert tmpl.render().strip() == 'FOO'
        self.assert_raises(TemplateNotFound, env.get_template, 'missing.html')

    def test_prefix_loader(self):
        env = Environment(loader=prefix_loader)
        tmpl = env.get_template('a/test.html')
        assert tmpl.render().strip() == 'BAR'
        tmpl = env.get_template('b/justdict.html')
        assert tmpl.render().strip() == 'FOO'
        self.assert_raises(TemplateNotFound, env.get_template, 'missing')

    def test_caching(self):
        changed = False
        class TestLoader(loaders.BaseLoader):
            def get_source(self, environment, template):
                return u'foo', None, lambda: not changed
        env = Environment(loader=TestLoader(), cache_size=-1)
        tmpl = env.get_template('template')
        assert tmpl is env.get_template('template')
        changed = True
        assert tmpl is not env.get_template('template')
        changed = False

        env = Environment(loader=TestLoader(), cache_size=0)
        assert env.get_template('template') \
               is not env.get_template('template')

        env = Environment(loader=TestLoader(), cache_size=2)
        t1 = env.get_template('one')
        t2 = env.get_template('two')
        assert t2 is env.get_template('two')
        assert t1 is env.get_template('one')
        t3 = env.get_template('three')
        assert 'one' in env.cache
        assert 'two' not in env.cache
        assert 'three' in env.cache

    def test_split_template_path(self):
        assert split_template_path('foo/bar') == ['foo', 'bar']
        assert split_template_path('./foo/bar') == ['foo', 'bar']
        self.assert_raises(TemplateNotFound, split_template_path, '../foo')


class ModuleLoaderTestCase(JinjaTestCase):
    archive = None

    def compile_down(self, zip='deflated', py_compile=False):
        super(ModuleLoaderTestCase, self).setup()
        log = []
        self.reg_env = Environment(loader=prefix_loader)
        if zip is not None:
            self.archive = tempfile.mkstemp(suffix='.zip')[1]
        else:
            self.archive = tempfile.mkdtemp()
        self.reg_env.compile_templates(self.archive, zip=zip,
                                       log_function=log.append,
                                       py_compile=py_compile)
        self.mod_env = Environment(loader=loaders.ModuleLoader(self.archive))
        return ''.join(log)

    def teardown(self):
        super(ModuleLoaderTestCase, self).teardown()
        if hasattr(self, 'mod_env'):
            if os.path.isfile(self.archive):
                os.remove(self.archive)
            else:
                shutil.rmtree(self.archive)
            self.archive = None

    def test_log(self):
        log = self.compile_down()
        assert 'Compiled "a/foo/test.html" as ' \
               'tmpl_a790caf9d669e39ea4d280d597ec891c4ef0404a' in log
        assert 'Finished compiling templates' in log
        assert 'Could not compile "a/syntaxerror.html": ' \
               'Encountered unknown tag \'endif\'' in log

    def _test_common(self):
        tmpl1 = self.reg_env.get_template('a/test.html')
        tmpl2 = self.mod_env.get_template('a/test.html')
        assert tmpl1.render() == tmpl2.render()

        tmpl1 = self.reg_env.get_template('b/justdict.html')
        tmpl2 = self.mod_env.get_template('b/justdict.html')
        assert tmpl1.render() == tmpl2.render()

    def test_deflated_zip_compile(self):
        self.compile_down(zip='deflated')
        self._test_common()

    def test_stored_zip_compile(self):
        self.compile_down(zip='stored')
        self._test_common()

    def test_filesystem_compile(self):
        self.compile_down(zip=None)
        self._test_common()

    def test_weak_references(self):
        self.compile_down()
        tmpl = self.mod_env.get_template('a/test.html')
        key = loaders.ModuleLoader.get_template_key('a/test.html')
        name = self.mod_env.loader.module.__name__

        assert hasattr(self.mod_env.loader.module, key)
        assert name in sys.modules

        # unset all, ensure the module is gone from sys.modules
        self.mod_env = tmpl = None

        try:
            import gc
            gc.collect()
        except:
            pass

        assert name not in sys.modules

    def test_byte_compilation(self):
        log = self.compile_down(py_compile=True)
        assert 'Byte-compiled "a/test.html"' in log
        tmpl1 = self.mod_env.get_template('a/test.html')
        mod = self.mod_env.loader.module. \
            tmpl_3c4ddf650c1a73df961a6d3d2ce2752f1b8fd490
        assert mod.__file__.endswith('.pyc')


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(LoaderTestCase))
    suite.addTest(unittest.makeSuite(ModuleLoaderTestCase))
    return suite

########NEW FILE########
__FILENAME__ = regression
# -*- coding: utf-8 -*-
"""
    jinja2.testsuite.regression
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Tests corner cases and bugs.

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD, see LICENSE for more details.
"""
import unittest

from jinja2.testsuite import JinjaTestCase

from jinja2 import Template, Environment, DictLoader, TemplateSyntaxError, \
     TemplateNotFound, PrefixLoader

env = Environment()


class CornerTestCase(JinjaTestCase):

    def test_assigned_scoping(self):
        t = env.from_string('''
        {%- for item in (1, 2, 3, 4) -%}
            [{{ item }}]
        {%- endfor %}
        {{- item -}}
        ''')
        assert t.render(item=42) == '[1][2][3][4]42'

        t = env.from_string('''
        {%- for item in (1, 2, 3, 4) -%}
            [{{ item }}]
        {%- endfor %}
        {%- set item = 42 %}
        {{- item -}}
        ''')
        assert t.render() == '[1][2][3][4]42'

        t = env.from_string('''
        {%- set item = 42 %}
        {%- for item in (1, 2, 3, 4) -%}
            [{{ item }}]
        {%- endfor %}
        {{- item -}}
        ''')
        assert t.render() == '[1][2][3][4]42'

    def test_closure_scoping(self):
        t = env.from_string('''
        {%- set wrapper = "<FOO>" %}
        {%- for item in (1, 2, 3, 4) %}
            {%- macro wrapper() %}[{{ item }}]{% endmacro %}
            {{- wrapper() }}
        {%- endfor %}
        {{- wrapper -}}
        ''')
        assert t.render() == '[1][2][3][4]<FOO>'

        t = env.from_string('''
        {%- for item in (1, 2, 3, 4) %}
            {%- macro wrapper() %}[{{ item }}]{% endmacro %}
            {{- wrapper() }}
        {%- endfor %}
        {%- set wrapper = "<FOO>" %}
        {{- wrapper -}}
        ''')
        assert t.render() == '[1][2][3][4]<FOO>'

        t = env.from_string('''
        {%- for item in (1, 2, 3, 4) %}
            {%- macro wrapper() %}[{{ item }}]{% endmacro %}
            {{- wrapper() }}
        {%- endfor %}
        {{- wrapper -}}
        ''')
        assert t.render(wrapper=23) == '[1][2][3][4]23'


class BugTestCase(JinjaTestCase):

    def test_keyword_folding(self):
        env = Environment()
        env.filters['testing'] = lambda value, some: value + some
        assert env.from_string("{{ 'test'|testing(some='stuff') }}") \
               .render() == 'teststuff'

    def test_extends_output_bugs(self):
        env = Environment(loader=DictLoader({
            'parent.html': '(({% block title %}{% endblock %}))'
        }))

        t = env.from_string('{% if expr %}{% extends "parent.html" %}{% endif %}'
                            '[[{% block title %}title{% endblock %}]]'
                            '{% for item in [1, 2, 3] %}({{ item }}){% endfor %}')
        assert t.render(expr=False) == '[[title]](1)(2)(3)'
        assert t.render(expr=True) == '((title))'

    def test_urlize_filter_escaping(self):
        tmpl = env.from_string('{{ "http://www.example.org/<foo"|urlize }}')
        assert tmpl.render() == '<a href="http://www.example.org/&lt;foo">http://www.example.org/&lt;foo</a>'

    def test_loop_call_loop(self):
        tmpl = env.from_string('''

        {% macro test() %}
            {{ caller() }}
        {% endmacro %}

        {% for num1 in range(5) %}
            {% call test() %}
                {% for num2 in range(10) %}
                    {{ loop.index }}
                {% endfor %}
            {% endcall %}
        {% endfor %}

        ''')

        assert tmpl.render().split() == map(unicode, range(1, 11)) * 5

    def test_weird_inline_comment(self):
        env = Environment(line_statement_prefix='%')
        self.assert_raises(TemplateSyntaxError, env.from_string,
                           '% for item in seq {# missing #}\n...% endfor')

    def test_old_macro_loop_scoping_bug(self):
        tmpl = env.from_string('{% for i in (1, 2) %}{{ i }}{% endfor %}'
                               '{% macro i() %}3{% endmacro %}{{ i() }}')
        assert tmpl.render() == '123'

    def test_partial_conditional_assignments(self):
        tmpl = env.from_string('{% if b %}{% set a = 42 %}{% endif %}{{ a }}')
        assert tmpl.render(a=23) == '23'
        assert tmpl.render(b=True) == '42'

    def test_stacked_locals_scoping_bug(self):
        env = Environment(line_statement_prefix='#')
        t = env.from_string('''\
# for j in [1, 2]:
#   set x = 1
#   for i in [1, 2]:
#     print x
#     if i % 2 == 0:
#       set x = x + 1
#     endif
#   endfor
# endfor
# if a
#   print 'A'
# elif b
#   print 'B'
# elif c == d
#   print 'C'
# else
#   print 'D'
# endif
    ''')
        assert t.render(a=0, b=False, c=42, d=42.0) == '1111C'

    def test_stacked_locals_scoping_bug_twoframe(self):
        t = Template('''
            {% set x = 1 %}
            {% for item in foo %}
                {% if item == 1 %}
                    {% set x = 2 %}
                {% endif %}
            {% endfor %}
            {{ x }}
        ''')
        rv = t.render(foo=[1]).strip()
        assert rv == u'1'

    def test_call_with_args(self):
        t = Template("""{% macro dump_users(users) -%}
        <ul>
          {%- for user in users -%}
            <li><p>{{ user.username|e }}</p>{{ caller(user) }}</li>
          {%- endfor -%}
          </ul>
        {%- endmacro -%}

        {% call(user) dump_users(list_of_user) -%}
          <dl>
            <dl>Realname</dl>
            <dd>{{ user.realname|e }}</dd>
            <dl>Description</dl>
            <dd>{{ user.description }}</dd>
          </dl>
        {% endcall %}""")

        assert [x.strip() for x in t.render(list_of_user=[{
            'username':'apo',
            'realname':'something else',
            'description':'test'
        }]).splitlines()] == [
            u'<ul><li><p>apo</p><dl>',
            u'<dl>Realname</dl>',
            u'<dd>something else</dd>',
            u'<dl>Description</dl>',
            u'<dd>test</dd>',
            u'</dl>',
            u'</li></ul>'
        ]

    def test_empty_if_condition_fails(self):
        self.assert_raises(TemplateSyntaxError, Template, '{% if %}....{% endif %}')
        self.assert_raises(TemplateSyntaxError, Template, '{% if foo %}...{% elif %}...{% endif %}')
        self.assert_raises(TemplateSyntaxError, Template, '{% for x in %}..{% endfor %}')

    def test_recursive_loop_bug(self):
        tpl1 = Template("""
        {% for p in foo recursive%}
            {{p.bar}}
            {% for f in p.fields recursive%}
                {{f.baz}}
                {{p.bar}}
                {% if f.rec %}
                    {{ loop(f.sub) }}
                {% endif %}
            {% endfor %}
        {% endfor %}
        """)

        tpl2 = Template("""
        {% for p in foo%}
            {{p.bar}}
            {% for f in p.fields recursive%}
                {{f.baz}}
                {{p.bar}}
                {% if f.rec %}
                    {{ loop(f.sub) }}
                {% endif %}
            {% endfor %}
        {% endfor %}
        """)

    def test_correct_prefix_loader_name(self):
        env = Environment(loader=PrefixLoader({
            'foo':  DictLoader({})
        }))
        try:
            env.get_template('foo/bar.html')
        except TemplateNotFound, e:
            assert e.name == 'foo/bar.html'
        else:
            assert False, 'expected error here'


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(CornerTestCase))
    suite.addTest(unittest.makeSuite(BugTestCase))
    return suite

########NEW FILE########
__FILENAME__ = security
# -*- coding: utf-8 -*-
"""
    jinja2.testsuite.security
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    Checks the sandbox and other security features.

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD, see LICENSE for more details.
"""
import unittest

from jinja2.testsuite import JinjaTestCase

from jinja2 import Environment
from jinja2.sandbox import SandboxedEnvironment, \
     ImmutableSandboxedEnvironment, unsafe
from jinja2 import Markup, escape
from jinja2.exceptions import SecurityError, TemplateSyntaxError, \
     TemplateRuntimeError


class PrivateStuff(object):

    def bar(self):
        return 23

    @unsafe
    def foo(self):
        return 42

    def __repr__(self):
        return 'PrivateStuff'


class PublicStuff(object):
    bar = lambda self: 23
    _foo = lambda self: 42

    def __repr__(self):
        return 'PublicStuff'


class SandboxTestCase(JinjaTestCase):

    def test_unsafe(self):
        env = SandboxedEnvironment()
        self.assert_raises(SecurityError, env.from_string("{{ foo.foo() }}").render,
                           foo=PrivateStuff())
        self.assert_equal(env.from_string("{{ foo.bar() }}").render(foo=PrivateStuff()), '23')

        self.assert_raises(SecurityError, env.from_string("{{ foo._foo() }}").render,
                           foo=PublicStuff())
        self.assert_equal(env.from_string("{{ foo.bar() }}").render(foo=PublicStuff()), '23')
        self.assert_equal(env.from_string("{{ foo.__class__ }}").render(foo=42), '')
        self.assert_equal(env.from_string("{{ foo.func_code }}").render(foo=lambda:None), '')
        # security error comes from __class__ already.
        self.assert_raises(SecurityError, env.from_string(
            "{{ foo.__class__.__subclasses__() }}").render, foo=42)

    def test_immutable_environment(self):
        env = ImmutableSandboxedEnvironment()
        self.assert_raises(SecurityError, env.from_string(
            '{{ [].append(23) }}').render)
        self.assert_raises(SecurityError, env.from_string(
            '{{ {1:2}.clear() }}').render)

    def test_restricted(self):
        env = SandboxedEnvironment()
        self.assert_raises(TemplateSyntaxError, env.from_string,
                      "{% for item.attribute in seq %}...{% endfor %}")
        self.assert_raises(TemplateSyntaxError, env.from_string,
                      "{% for foo, bar.baz in seq %}...{% endfor %}")

    def test_markup_operations(self):
        # adding two strings should escape the unsafe one
        unsafe = '<script type="application/x-some-script">alert("foo");</script>'
        safe = Markup('<em>username</em>')
        assert unsafe + safe == unicode(escape(unsafe)) + unicode(safe)

        # string interpolations are safe to use too
        assert Markup('<em>%s</em>') % '<bad user>' == \
               '<em>&lt;bad user&gt;</em>'
        assert Markup('<em>%(username)s</em>') % {
            'username': '<bad user>'
        } == '<em>&lt;bad user&gt;</em>'

        # an escaped object is markup too
        assert type(Markup('foo') + 'bar') is Markup

        # and it implements __html__ by returning itself
        x = Markup("foo")
        assert x.__html__() is x

        # it also knows how to treat __html__ objects
        class Foo(object):
            def __html__(self):
                return '<em>awesome</em>'
            def __unicode__(self):
                return 'awesome'
        assert Markup(Foo()) == '<em>awesome</em>'
        assert Markup('<strong>%s</strong>') % Foo() == \
               '<strong><em>awesome</em></strong>'

        # escaping and unescaping
        assert escape('"<>&\'') == '&#34;&lt;&gt;&amp;&#39;'
        assert Markup("<em>Foo &amp; Bar</em>").striptags() == "Foo & Bar"
        assert Markup("&lt;test&gt;").unescape() == "<test>"

    def test_template_data(self):
        env = Environment(autoescape=True)
        t = env.from_string('{% macro say_hello(name) %}'
                            '<p>Hello {{ name }}!</p>{% endmacro %}'
                            '{{ say_hello("<blink>foo</blink>") }}')
        escaped_out = '<p>Hello &lt;blink&gt;foo&lt;/blink&gt;!</p>'
        assert t.render() == escaped_out
        assert unicode(t.module) == escaped_out
        assert escape(t.module) == escaped_out
        assert t.module.say_hello('<blink>foo</blink>') == escaped_out
        assert escape(t.module.say_hello('<blink>foo</blink>')) == escaped_out

    def test_attr_filter(self):
        env = SandboxedEnvironment()
        tmpl = env.from_string('{{ cls|attr("__subclasses__")() }}')
        self.assert_raises(SecurityError, tmpl.render, cls=int)

    def test_binary_operator_intercepting(self):
        def disable_op(left, right):
            raise TemplateRuntimeError('that operator so does not work')
        for expr, ctx, rv in ('1 + 2', {}, '3'), ('a + 2', {'a': 2}, '4'):
            env = SandboxedEnvironment()
            env.binop_table['+'] = disable_op
            t = env.from_string('{{ %s }}' % expr)
            assert t.render(ctx) == rv
            env.intercepted_binops = frozenset(['+'])
            t = env.from_string('{{ %s }}' % expr)
            try:
                t.render(ctx)
            except TemplateRuntimeError, e:
                pass
            else:
                self.fail('expected runtime error')

    def test_unary_operator_intercepting(self):
        def disable_op(arg):
            raise TemplateRuntimeError('that operator so does not work')
        for expr, ctx, rv in ('-1', {}, '-1'), ('-a', {'a': 2}, '-2'):
            env = SandboxedEnvironment()
            env.unop_table['-'] = disable_op
            t = env.from_string('{{ %s }}' % expr)
            assert t.render(ctx) == rv
            env.intercepted_unops = frozenset(['-'])
            t = env.from_string('{{ %s }}' % expr)
            try:
                t.render(ctx)
            except TemplateRuntimeError, e:
                pass
            else:
                self.fail('expected runtime error')


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(SandboxTestCase))
    return suite

########NEW FILE########
__FILENAME__ = tests
# -*- coding: utf-8 -*-
"""
    jinja2.testsuite.tests
    ~~~~~~~~~~~~~~~~~~~~~~

    Who tests the tests?

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD, see LICENSE for more details.
"""
import unittest
from jinja2.testsuite import JinjaTestCase

from jinja2 import Markup, Environment

env = Environment()


class TestsTestCase(JinjaTestCase):

    def test_defined(self):
        tmpl = env.from_string('{{ missing is defined }}|{{ true is defined }}')
        assert tmpl.render() == 'False|True'

    def test_even(self):
        tmpl = env.from_string('''{{ 1 is even }}|{{ 2 is even }}''')
        assert tmpl.render() == 'False|True'

    def test_odd(self):
        tmpl = env.from_string('''{{ 1 is odd }}|{{ 2 is odd }}''')
        assert tmpl.render() == 'True|False'

    def test_lower(self):
        tmpl = env.from_string('''{{ "foo" is lower }}|{{ "FOO" is lower }}''')
        assert tmpl.render() == 'True|False'

    def test_typechecks(self):
        tmpl = env.from_string('''
            {{ 42 is undefined }}
            {{ 42 is defined }}
            {{ 42 is none }}
            {{ none is none }}
            {{ 42 is number }}
            {{ 42 is string }}
            {{ "foo" is string }}
            {{ "foo" is sequence }}
            {{ [1] is sequence }}
            {{ range is callable }}
            {{ 42 is callable }}
            {{ range(5) is iterable }}
        ''')
        assert tmpl.render().split() == [
            'False', 'True', 'False', 'True', 'True', 'False',
            'True', 'True', 'True', 'True', 'False', 'True'
        ]

    def test_sequence(self):
        tmpl = env.from_string(
            '{{ [1, 2, 3] is sequence }}|'
            '{{ "foo" is sequence }}|'
            '{{ 42 is sequence }}'
        )
        assert tmpl.render() == 'True|True|False'

    def test_upper(self):
        tmpl = env.from_string('{{ "FOO" is upper }}|{{ "foo" is upper }}')
        assert tmpl.render() == 'True|False'

    def test_sameas(self):
        tmpl = env.from_string('{{ foo is sameas false }}|'
                               '{{ 0 is sameas false }}')
        assert tmpl.render(foo=False) == 'True|False'

    def test_no_paren_for_arg1(self):
        tmpl = env.from_string('{{ foo is sameas none }}')
        assert tmpl.render(foo=None) == 'True'

    def test_escaped(self):
        env = Environment(autoescape=True)
        tmpl = env.from_string('{{ x is escaped }}|{{ y is escaped }}')
        assert tmpl.render(x='foo', y=Markup('foo')) == 'False|True'


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestsTestCase))
    return suite

########NEW FILE########
__FILENAME__ = utils
# -*- coding: utf-8 -*-
"""
    jinja2.testsuite.utils
    ~~~~~~~~~~~~~~~~~~~~~~

    Tests utilities jinja uses.

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD, see LICENSE for more details.
"""
import gc
import unittest

import pickle

from jinja2.testsuite import JinjaTestCase

from jinja2.utils import LRUCache, escape, object_type_repr


class LRUCacheTestCase(JinjaTestCase):

    def test_simple(self):
        d = LRUCache(3)
        d["a"] = 1
        d["b"] = 2
        d["c"] = 3
        d["a"]
        d["d"] = 4
        assert len(d) == 3
        assert 'a' in d and 'c' in d and 'd' in d and 'b' not in d

    def test_pickleable(self):
        cache = LRUCache(2)
        cache["foo"] = 42
        cache["bar"] = 23
        cache["foo"]

        for protocol in range(3):
            copy = pickle.loads(pickle.dumps(cache, protocol))
            assert copy.capacity == cache.capacity
            assert copy._mapping == cache._mapping
            assert copy._queue == cache._queue


class HelpersTestCase(JinjaTestCase):

    def test_object_type_repr(self):
        class X(object):
            pass
        self.assert_equal(object_type_repr(42), 'int object')
        self.assert_equal(object_type_repr([]), 'list object')
        self.assert_equal(object_type_repr(X()),
                         'jinja2.testsuite.utils.X object')
        self.assert_equal(object_type_repr(None), 'None')
        self.assert_equal(object_type_repr(Ellipsis), 'Ellipsis')


class MarkupLeakTestCase(JinjaTestCase):

    def test_markup_leaks(self):
        counts = set()
        for count in xrange(20):
            for item in xrange(1000):
                escape("foo")
                escape("<foo>")
                escape(u"foo")
                escape(u"<foo>")
            counts.add(len(gc.get_objects()))
        assert len(counts) == 1, 'ouch, c extension seems to leak objects'


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(LRUCacheTestCase))
    suite.addTest(unittest.makeSuite(HelpersTestCase))

    # this test only tests the c extension
    if not hasattr(escape, 'func_code'):
        suite.addTest(unittest.makeSuite(MarkupLeakTestCase))

    return suite

########NEW FILE########
__FILENAME__ = utils
# -*- coding: utf-8 -*-
"""
    jinja2.utils
    ~~~~~~~~~~~~

    Utility functions.

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD, see LICENSE for more details.
"""
import re
import sys
import errno
try:
    from thread import allocate_lock
except ImportError:
    from dummy_thread import allocate_lock
from collections import deque
from itertools import imap


_word_split_re = re.compile(r'(\s+)')
_punctuation_re = re.compile(
    '^(?P<lead>(?:%s)*)(?P<middle>.*?)(?P<trail>(?:%s)*)$' % (
        '|'.join(imap(re.escape, ('(', '<', '&lt;'))),
        '|'.join(imap(re.escape, ('.', ',', ')', '>', '\n', '&gt;')))
    )
)
_simple_email_re = re.compile(r'^\S+@[a-zA-Z0-9._-]+\.[a-zA-Z0-9._-]+$')
_striptags_re = re.compile(r'(<!--.*?-->|<[^>]*>)')
_entity_re = re.compile(r'&([^;]+);')
_letters = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
_digits = '0123456789'

# special singleton representing missing values for the runtime
missing = type('MissingType', (), {'__repr__': lambda x: 'missing'})()

# internal code
internal_code = set()


# concatenate a list of strings and convert them to unicode.
# unfortunately there is a bug in python 2.4 and lower that causes
# unicode.join trash the traceback.
_concat = u''.join
try:
    def _test_gen_bug():
        raise TypeError(_test_gen_bug)
        yield None
    _concat(_test_gen_bug())
except TypeError, _error:
    if not _error.args or _error.args[0] is not _test_gen_bug:
        def concat(gen):
            try:
                return _concat(list(gen))
            except Exception:
                # this hack is needed so that the current frame
                # does not show up in the traceback.
                exc_type, exc_value, tb = sys.exc_info()
                raise exc_type, exc_value, tb.tb_next
    else:
        concat = _concat
    del _test_gen_bug, _error


# for python 2.x we create outselves a next() function that does the
# basics without exception catching.
try:
    next = next
except NameError:
    def next(x):
        return x.next()


# if this python version is unable to deal with unicode filenames
# when passed to encode we let this function encode it properly.
# This is used in a couple of places.  As far as Jinja is concerned
# filenames are unicode *or* bytestrings in 2.x and unicode only in
# 3.x because compile cannot handle bytes
if sys.version_info < (3, 0):
    def _encode_filename(filename):
        if isinstance(filename, unicode):
            return filename.encode('utf-8')
        return filename
else:
    def _encode_filename(filename):
        assert filename is None or isinstance(filename, str), \
            'filenames must be strings'
        return filename

from keyword import iskeyword as is_python_keyword


# common types.  These do exist in the special types module too which however
# does not exist in IronPython out of the box.  Also that way we don't have
# to deal with implementation specific stuff here
class _C(object):
    def method(self): pass
def _func():
    yield None
FunctionType = type(_func)
GeneratorType = type(_func())
MethodType = type(_C.method)
CodeType = type(_C.method.func_code)
try:
    raise TypeError()
except TypeError:
    _tb = sys.exc_info()[2]
    TracebackType = type(_tb)
    FrameType = type(_tb.tb_frame)
del _C, _tb, _func


def contextfunction(f):
    """This decorator can be used to mark a function or method context callable.
    A context callable is passed the active :class:`Context` as first argument when
    called from the template.  This is useful if a function wants to get access
    to the context or functions provided on the context object.  For example
    a function that returns a sorted list of template variables the current
    template exports could look like this::

        @contextfunction
        def get_exported_names(context):
            return sorted(context.exported_vars)
    """
    f.contextfunction = True
    return f


def evalcontextfunction(f):
    """This decoraotr can be used to mark a function or method as an eval
    context callable.  This is similar to the :func:`contextfunction`
    but instead of passing the context, an evaluation context object is
    passed.  For more information about the eval context, see
    :ref:`eval-context`.

    .. versionadded:: 2.4
    """
    f.evalcontextfunction = True
    return f


def environmentfunction(f):
    """This decorator can be used to mark a function or method as environment
    callable.  This decorator works exactly like the :func:`contextfunction`
    decorator just that the first argument is the active :class:`Environment`
    and not context.
    """
    f.environmentfunction = True
    return f


def internalcode(f):
    """Marks the function as internally used"""
    internal_code.add(f.func_code)
    return f


def is_undefined(obj):
    """Check if the object passed is undefined.  This does nothing more than
    performing an instance check against :class:`Undefined` but looks nicer.
    This can be used for custom filters or tests that want to react to
    undefined variables.  For example a custom default filter can look like
    this::

        def default(var, default=''):
            if is_undefined(var):
                return default
            return var
    """
    from jinja2.runtime import Undefined
    return isinstance(obj, Undefined)


def consume(iterable):
    """Consumes an iterable without doing anything with it."""
    for event in iterable:
        pass


def clear_caches():
    """Jinja2 keeps internal caches for environments and lexers.  These are
    used so that Jinja2 doesn't have to recreate environments and lexers all
    the time.  Normally you don't have to care about that but if you are
    messuring memory consumption you may want to clean the caches.
    """
    from jinja2.environment import _spontaneous_environments
    from jinja2.lexer import _lexer_cache
    _spontaneous_environments.clear()
    _lexer_cache.clear()


def import_string(import_name, silent=False):
    """Imports an object based on a string.  This use useful if you want to
    use import paths as endpoints or something similar.  An import path can
    be specified either in dotted notation (``xml.sax.saxutils.escape``)
    or with a colon as object delimiter (``xml.sax.saxutils:escape``).

    If the `silent` is True the return value will be `None` if the import
    fails.

    :return: imported object
    """
    try:
        if ':' in import_name:
            module, obj = import_name.split(':', 1)
        elif '.' in import_name:
            items = import_name.split('.')
            module = '.'.join(items[:-1])
            obj = items[-1]
        else:
            return __import__(import_name)
        return getattr(__import__(module, None, None, [obj]), obj)
    except (ImportError, AttributeError):
        if not silent:
            raise


def open_if_exists(filename, mode='rb'):
    """Returns a file descriptor for the filename if that file exists,
    otherwise `None`.
    """
    try:
        return open(filename, mode)
    except IOError, e:
        if e.errno not in (errno.ENOENT, errno.EISDIR):
            raise


def object_type_repr(obj):
    """Returns the name of the object's type.  For some recognized
    singletons the name of the object is returned instead. (For
    example for `None` and `Ellipsis`).
    """
    if obj is None:
        return 'None'
    elif obj is Ellipsis:
        return 'Ellipsis'
    # __builtin__ in 2.x, builtins in 3.x
    if obj.__class__.__module__ in ('__builtin__', 'builtins'):
        name = obj.__class__.__name__
    else:
        name = obj.__class__.__module__ + '.' + obj.__class__.__name__
    return '%s object' % name


def pformat(obj, verbose=False):
    """Prettyprint an object.  Either use the `pretty` library or the
    builtin `pprint`.
    """
    try:
        from pretty import pretty
        return pretty(obj, verbose=verbose)
    except ImportError:
        from pprint import pformat
        return pformat(obj)


def urlize(text, trim_url_limit=None, nofollow=False):
    """Converts any URLs in text into clickable links. Works on http://,
    https:// and www. links. Links can have trailing punctuation (periods,
    commas, close-parens) and leading punctuation (opening parens) and
    it'll still do the right thing.

    If trim_url_limit is not None, the URLs in link text will be limited
    to trim_url_limit characters.

    If nofollow is True, the URLs in link text will get a rel="nofollow"
    attribute.
    """
    trim_url = lambda x, limit=trim_url_limit: limit is not None \
                         and (x[:limit] + (len(x) >=limit and '...'
                         or '')) or x
    words = _word_split_re.split(unicode(escape(text)))
    nofollow_attr = nofollow and ' rel="nofollow"' or ''
    for i, word in enumerate(words):
        match = _punctuation_re.match(word)
        if match:
            lead, middle, trail = match.groups()
            if middle.startswith('www.') or (
                '@' not in middle and
                not middle.startswith('http://') and
                len(middle) > 0 and
                middle[0] in _letters + _digits and (
                    middle.endswith('.org') or
                    middle.endswith('.net') or
                    middle.endswith('.com')
                )):
                middle = '<a href="http://%s"%s>%s</a>' % (middle,
                    nofollow_attr, trim_url(middle))
            if middle.startswith('http://') or \
               middle.startswith('https://'):
                middle = '<a href="%s"%s>%s</a>' % (middle,
                    nofollow_attr, trim_url(middle))
            if '@' in middle and not middle.startswith('www.') and \
               not ':' in middle and _simple_email_re.match(middle):
                middle = '<a href="mailto:%s">%s</a>' % (middle, middle)
            if lead + middle + trail != word:
                words[i] = lead + middle + trail
    return u''.join(words)


def generate_lorem_ipsum(n=5, html=True, min=20, max=100):
    """Generate some lorem impsum for the template."""
    from jinja2.constants import LOREM_IPSUM_WORDS
    from random import choice, randrange
    words = LOREM_IPSUM_WORDS.split()
    result = []

    for _ in xrange(n):
        next_capitalized = True
        last_comma = last_fullstop = 0
        word = None
        last = None
        p = []

        # each paragraph contains out of 20 to 100 words.
        for idx, _ in enumerate(xrange(randrange(min, max))):
            while True:
                word = choice(words)
                if word != last:
                    last = word
                    break
            if next_capitalized:
                word = word.capitalize()
                next_capitalized = False
            # add commas
            if idx - randrange(3, 8) > last_comma:
                last_comma = idx
                last_fullstop += 2
                word += ','
            # add end of sentences
            if idx - randrange(10, 20) > last_fullstop:
                last_comma = last_fullstop = idx
                word += '.'
                next_capitalized = True
            p.append(word)

        # ensure that the paragraph ends with a dot.
        p = u' '.join(p)
        if p.endswith(','):
            p = p[:-1] + '.'
        elif not p.endswith('.'):
            p += '.'
        result.append(p)

    if not html:
        return u'\n\n'.join(result)
    return Markup(u'\n'.join(u'<p>%s</p>' % escape(x) for x in result))


class LRUCache(object):
    """A simple LRU Cache implementation."""

    # this is fast for small capacities (something below 1000) but doesn't
    # scale.  But as long as it's only used as storage for templates this
    # won't do any harm.

    def __init__(self, capacity):
        self.capacity = capacity
        self._mapping = {}
        self._queue = deque()
        self._postinit()

    def _postinit(self):
        # alias all queue methods for faster lookup
        self._popleft = self._queue.popleft
        self._pop = self._queue.pop
        if hasattr(self._queue, 'remove'):
            self._remove = self._queue.remove
        self._wlock = allocate_lock()
        self._append = self._queue.append

    def _remove(self, obj):
        """Python 2.4 compatibility."""
        for idx, item in enumerate(self._queue):
            if item == obj:
                del self._queue[idx]
                break

    def __getstate__(self):
        return {
            'capacity':     self.capacity,
            '_mapping':     self._mapping,
            '_queue':       self._queue
        }

    def __setstate__(self, d):
        self.__dict__.update(d)
        self._postinit()

    def __getnewargs__(self):
        return (self.capacity,)

    def copy(self):
        """Return an shallow copy of the instance."""
        rv = self.__class__(self.capacity)
        rv._mapping.update(self._mapping)
        rv._queue = deque(self._queue)
        return rv

    def get(self, key, default=None):
        """Return an item from the cache dict or `default`"""
        try:
            return self[key]
        except KeyError:
            return default

    def setdefault(self, key, default=None):
        """Set `default` if the key is not in the cache otherwise
        leave unchanged. Return the value of this key.
        """
        try:
            return self[key]
        except KeyError:
            self[key] = default
            return default

    def clear(self):
        """Clear the cache."""
        self._wlock.acquire()
        try:
            self._mapping.clear()
            self._queue.clear()
        finally:
            self._wlock.release()

    def __contains__(self, key):
        """Check if a key exists in this cache."""
        return key in self._mapping

    def __len__(self):
        """Return the current size of the cache."""
        return len(self._mapping)

    def __repr__(self):
        return '<%s %r>' % (
            self.__class__.__name__,
            self._mapping
        )

    def __getitem__(self, key):
        """Get an item from the cache. Moves the item up so that it has the
        highest priority then.

        Raise an `KeyError` if it does not exist.
        """
        rv = self._mapping[key]
        if self._queue[-1] != key:
            try:
                self._remove(key)
            except ValueError:
                # if something removed the key from the container
                # when we read, ignore the ValueError that we would
                # get otherwise.
                pass
            self._append(key)
        return rv

    def __setitem__(self, key, value):
        """Sets the value for an item. Moves the item up so that it
        has the highest priority then.
        """
        self._wlock.acquire()
        try:
            if key in self._mapping:
                try:
                    self._remove(key)
                except ValueError:
                    # __getitem__ is not locked, it might happen
                    pass
            elif len(self._mapping) == self.capacity:
                del self._mapping[self._popleft()]
            self._append(key)
            self._mapping[key] = value
        finally:
            self._wlock.release()

    def __delitem__(self, key):
        """Remove an item from the cache dict.
        Raise an `KeyError` if it does not exist.
        """
        self._wlock.acquire()
        try:
            del self._mapping[key]
            try:
                self._remove(key)
            except ValueError:
                # __getitem__ is not locked, it might happen
                pass
        finally:
            self._wlock.release()

    def items(self):
        """Return a list of items."""
        result = [(key, self._mapping[key]) for key in list(self._queue)]
        result.reverse()
        return result

    def iteritems(self):
        """Iterate over all items."""
        return iter(self.items())

    def values(self):
        """Return a list of all values."""
        return [x[1] for x in self.items()]

    def itervalue(self):
        """Iterate over all values."""
        return iter(self.values())

    def keys(self):
        """Return a list of all keys ordered by most recent usage."""
        return list(self)

    def iterkeys(self):
        """Iterate over all keys in the cache dict, ordered by
        the most recent usage.
        """
        return reversed(tuple(self._queue))

    __iter__ = iterkeys

    def __reversed__(self):
        """Iterate over the values in the cache dict, oldest items
        coming first.
        """
        return iter(tuple(self._queue))

    __copy__ = copy


# register the LRU cache as mutable mapping if possible
try:
    from collections import MutableMapping
    MutableMapping.register(LRUCache)
except ImportError:
    pass


class Cycler(object):
    """A cycle helper for templates."""

    def __init__(self, *items):
        if not items:
            raise RuntimeError('at least one item has to be provided')
        self.items = items
        self.reset()

    def reset(self):
        """Resets the cycle."""
        self.pos = 0

    @property
    def current(self):
        """Returns the current item."""
        return self.items[self.pos]

    def next(self):
        """Goes one item ahead and returns it."""
        rv = self.current
        self.pos = (self.pos + 1) % len(self.items)
        return rv


class Joiner(object):
    """A joining helper for templates."""

    def __init__(self, sep=u', '):
        self.sep = sep
        self.used = False

    def __call__(self):
        if not self.used:
            self.used = True
            return u''
        return self.sep


# try markupsafe first, if that fails go with Jinja2's bundled version
# of markupsafe.  Markupsafe was previously Jinja2's implementation of
# the Markup object but was moved into a separate package in a patchleve
# release
try:
    from markupsafe import Markup, escape, soft_unicode
except ImportError:
    from jinja2._markupsafe import Markup, escape, soft_unicode


# partials
try:
    from functools import partial
except ImportError:
    class partial(object):
        def __init__(self, _func, *args, **kwargs):
            self._func = _func
            self._args = args
            self._kwargs = kwargs
        def __call__(self, *args, **kwargs):
            kwargs.update(self._kwargs)
            return self._func(*(self._args + args), **kwargs)

########NEW FILE########
__FILENAME__ = visitor
# -*- coding: utf-8 -*-
"""
    jinja2.visitor
    ~~~~~~~~~~~~~~

    This module implements a visitor for the nodes.

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD.
"""
from jinja2.nodes import Node


class NodeVisitor(object):
    """Walks the abstract syntax tree and call visitor functions for every
    node found.  The visitor functions may return values which will be
    forwarded by the `visit` method.

    Per default the visitor functions for the nodes are ``'visit_'`` +
    class name of the node.  So a `TryFinally` node visit function would
    be `visit_TryFinally`.  This behavior can be changed by overriding
    the `get_visitor` function.  If no visitor function exists for a node
    (return value `None`) the `generic_visit` visitor is used instead.
    """

    def get_visitor(self, node):
        """Return the visitor function for this node or `None` if no visitor
        exists for this node.  In that case the generic visit function is
        used instead.
        """
        method = 'visit_' + node.__class__.__name__
        return getattr(self, method, None)

    def visit(self, node, *args, **kwargs):
        """Visit a node."""
        f = self.get_visitor(node)
        if f is not None:
            return f(node, *args, **kwargs)
        return self.generic_visit(node, *args, **kwargs)

    def generic_visit(self, node, *args, **kwargs):
        """Called if no explicit visitor function exists for a node."""
        for node in node.iter_child_nodes():
            self.visit(node, *args, **kwargs)


class NodeTransformer(NodeVisitor):
    """Walks the abstract syntax tree and allows modifications of nodes.

    The `NodeTransformer` will walk the AST and use the return value of the
    visitor functions to replace or remove the old node.  If the return
    value of the visitor function is `None` the node will be removed
    from the previous location otherwise it's replaced with the return
    value.  The return value may be the original node in which case no
    replacement takes place.
    """

    def generic_visit(self, node, *args, **kwargs):
        for field, old_value in node.iter_fields():
            if isinstance(old_value, list):
                new_values = []
                for value in old_value:
                    if isinstance(value, Node):
                        value = self.visit(value, *args, **kwargs)
                        if value is None:
                            continue
                        elif not isinstance(value, Node):
                            new_values.extend(value)
                            continue
                    new_values.append(value)
                old_value[:] = new_values
            elif isinstance(old_value, Node):
                new_node = self.visit(old_value, *args, **kwargs)
                if new_node is None:
                    delattr(node, field)
                else:
                    setattr(node, field, new_node)
        return node

    def visit_list(self, node, *args, **kwargs):
        """As transformers may return lists in some places this method
        can be used to enforce a list as return value.
        """
        rv = self.visit(node, *args, **kwargs)
        if not isinstance(rv, list):
            rv = [rv]
        return rv

########NEW FILE########
__FILENAME__ = tests
import gc
import unittest
from jinja2._markupsafe import Markup, escape, escape_silent


class MarkupTestCase(unittest.TestCase):

    def test_markup_operations(self):
        # adding two strings should escape the unsafe one
        unsafe = '<script type="application/x-some-script">alert("foo");</script>'
        safe = Markup('<em>username</em>')
        assert unsafe + safe == unicode(escape(unsafe)) + unicode(safe)

        # string interpolations are safe to use too
        assert Markup('<em>%s</em>') % '<bad user>' == \
               '<em>&lt;bad user&gt;</em>'
        assert Markup('<em>%(username)s</em>') % {
            'username': '<bad user>'
        } == '<em>&lt;bad user&gt;</em>'

        # an escaped object is markup too
        assert type(Markup('foo') + 'bar') is Markup

        # and it implements __html__ by returning itself
        x = Markup("foo")
        assert x.__html__() is x

        # it also knows how to treat __html__ objects
        class Foo(object):
            def __html__(self):
                return '<em>awesome</em>'
            def __unicode__(self):
                return 'awesome'
        assert Markup(Foo()) == '<em>awesome</em>'
        assert Markup('<strong>%s</strong>') % Foo() == \
               '<strong><em>awesome</em></strong>'

        # escaping and unescaping
        assert escape('"<>&\'') == '&#34;&lt;&gt;&amp;&#39;'
        assert Markup("<em>Foo &amp; Bar</em>").striptags() == "Foo & Bar"
        assert Markup("&lt;test&gt;").unescape() == "<test>"

    def test_all_set(self):
        import jinja2._markupsafe as markup
        for item in markup.__all__:
            getattr(markup, item)

    def test_escape_silent(self):
        assert escape_silent(None) == Markup()
        assert escape(None) == Markup(None)
        assert escape_silent('<foo>') == Markup(u'&lt;foo&gt;')


class MarkupLeakTestCase(unittest.TestCase):

    def test_markup_leaks(self):
        counts = set()
        for count in xrange(20):
            for item in xrange(1000):
                escape("foo")
                escape("<foo>")
                escape(u"foo")
                escape(u"<foo>")
            counts.add(len(gc.get_objects()))
        assert len(counts) == 1, 'ouch, c extension seems to leak objects'


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(MarkupTestCase))

    # this test only tests the c extension
    if not hasattr(escape, 'func_code'):
        suite.addTest(unittest.makeSuite(MarkupLeakTestCase))

    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')

########NEW FILE########
__FILENAME__ = _bundle
# -*- coding: utf-8 -*-
"""
    jinja2._markupsafe._bundle
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    This script pulls in markupsafe from a source folder and
    bundles it with Jinja2.  It does not pull in the speedups
    module though.

    :copyright: Copyright 2010 by the Jinja team, see AUTHORS.
    :license: BSD, see LICENSE for details.
"""
import sys
import os
import re


def rewrite_imports(lines):
    for idx, line in enumerate(lines):
        new_line = re.sub(r'(import|from)\s+markupsafe\b',
                          r'\1 jinja2._markupsafe', line)
        if new_line != line:
            lines[idx] = new_line


def main():
    if len(sys.argv) != 2:
        print 'error: only argument is path to markupsafe'
        sys.exit(1)
    basedir = os.path.dirname(__file__)
    markupdir = sys.argv[1]
    for filename in os.listdir(markupdir):
        if filename.endswith('.py'):
            f = open(os.path.join(markupdir, filename))
            try:
                lines = list(f)
            finally:
                f.close()
            rewrite_imports(lines)
            f = open(os.path.join(basedir, filename), 'w')
            try:
                for line in lines:
                    f.write(line)
            finally:
                f.close()


if __name__ == '__main__':
    main()

########NEW FILE########
__FILENAME__ = _constants
# -*- coding: utf-8 -*-
"""
    markupsafe._constants
    ~~~~~~~~~~~~~~~~~~~~~

    Highlevel implementation of the Markup string.

    :copyright: (c) 2010 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""


HTML_ENTITIES = {
    'AElig': 198,
    'Aacute': 193,
    'Acirc': 194,
    'Agrave': 192,
    'Alpha': 913,
    'Aring': 197,
    'Atilde': 195,
    'Auml': 196,
    'Beta': 914,
    'Ccedil': 199,
    'Chi': 935,
    'Dagger': 8225,
    'Delta': 916,
    'ETH': 208,
    'Eacute': 201,
    'Ecirc': 202,
    'Egrave': 200,
    'Epsilon': 917,
    'Eta': 919,
    'Euml': 203,
    'Gamma': 915,
    'Iacute': 205,
    'Icirc': 206,
    'Igrave': 204,
    'Iota': 921,
    'Iuml': 207,
    'Kappa': 922,
    'Lambda': 923,
    'Mu': 924,
    'Ntilde': 209,
    'Nu': 925,
    'OElig': 338,
    'Oacute': 211,
    'Ocirc': 212,
    'Ograve': 210,
    'Omega': 937,
    'Omicron': 927,
    'Oslash': 216,
    'Otilde': 213,
    'Ouml': 214,
    'Phi': 934,
    'Pi': 928,
    'Prime': 8243,
    'Psi': 936,
    'Rho': 929,
    'Scaron': 352,
    'Sigma': 931,
    'THORN': 222,
    'Tau': 932,
    'Theta': 920,
    'Uacute': 218,
    'Ucirc': 219,
    'Ugrave': 217,
    'Upsilon': 933,
    'Uuml': 220,
    'Xi': 926,
    'Yacute': 221,
    'Yuml': 376,
    'Zeta': 918,
    'aacute': 225,
    'acirc': 226,
    'acute': 180,
    'aelig': 230,
    'agrave': 224,
    'alefsym': 8501,
    'alpha': 945,
    'amp': 38,
    'and': 8743,
    'ang': 8736,
    'apos': 39,
    'aring': 229,
    'asymp': 8776,
    'atilde': 227,
    'auml': 228,
    'bdquo': 8222,
    'beta': 946,
    'brvbar': 166,
    'bull': 8226,
    'cap': 8745,
    'ccedil': 231,
    'cedil': 184,
    'cent': 162,
    'chi': 967,
    'circ': 710,
    'clubs': 9827,
    'cong': 8773,
    'copy': 169,
    'crarr': 8629,
    'cup': 8746,
    'curren': 164,
    'dArr': 8659,
    'dagger': 8224,
    'darr': 8595,
    'deg': 176,
    'delta': 948,
    'diams': 9830,
    'divide': 247,
    'eacute': 233,
    'ecirc': 234,
    'egrave': 232,
    'empty': 8709,
    'emsp': 8195,
    'ensp': 8194,
    'epsilon': 949,
    'equiv': 8801,
    'eta': 951,
    'eth': 240,
    'euml': 235,
    'euro': 8364,
    'exist': 8707,
    'fnof': 402,
    'forall': 8704,
    'frac12': 189,
    'frac14': 188,
    'frac34': 190,
    'frasl': 8260,
    'gamma': 947,
    'ge': 8805,
    'gt': 62,
    'hArr': 8660,
    'harr': 8596,
    'hearts': 9829,
    'hellip': 8230,
    'iacute': 237,
    'icirc': 238,
    'iexcl': 161,
    'igrave': 236,
    'image': 8465,
    'infin': 8734,
    'int': 8747,
    'iota': 953,
    'iquest': 191,
    'isin': 8712,
    'iuml': 239,
    'kappa': 954,
    'lArr': 8656,
    'lambda': 955,
    'lang': 9001,
    'laquo': 171,
    'larr': 8592,
    'lceil': 8968,
    'ldquo': 8220,
    'le': 8804,
    'lfloor': 8970,
    'lowast': 8727,
    'loz': 9674,
    'lrm': 8206,
    'lsaquo': 8249,
    'lsquo': 8216,
    'lt': 60,
    'macr': 175,
    'mdash': 8212,
    'micro': 181,
    'middot': 183,
    'minus': 8722,
    'mu': 956,
    'nabla': 8711,
    'nbsp': 160,
    'ndash': 8211,
    'ne': 8800,
    'ni': 8715,
    'not': 172,
    'notin': 8713,
    'nsub': 8836,
    'ntilde': 241,
    'nu': 957,
    'oacute': 243,
    'ocirc': 244,
    'oelig': 339,
    'ograve': 242,
    'oline': 8254,
    'omega': 969,
    'omicron': 959,
    'oplus': 8853,
    'or': 8744,
    'ordf': 170,
    'ordm': 186,
    'oslash': 248,
    'otilde': 245,
    'otimes': 8855,
    'ouml': 246,
    'para': 182,
    'part': 8706,
    'permil': 8240,
    'perp': 8869,
    'phi': 966,
    'pi': 960,
    'piv': 982,
    'plusmn': 177,
    'pound': 163,
    'prime': 8242,
    'prod': 8719,
    'prop': 8733,
    'psi': 968,
    'quot': 34,
    'rArr': 8658,
    'radic': 8730,
    'rang': 9002,
    'raquo': 187,
    'rarr': 8594,
    'rceil': 8969,
    'rdquo': 8221,
    'real': 8476,
    'reg': 174,
    'rfloor': 8971,
    'rho': 961,
    'rlm': 8207,
    'rsaquo': 8250,
    'rsquo': 8217,
    'sbquo': 8218,
    'scaron': 353,
    'sdot': 8901,
    'sect': 167,
    'shy': 173,
    'sigma': 963,
    'sigmaf': 962,
    'sim': 8764,
    'spades': 9824,
    'sub': 8834,
    'sube': 8838,
    'sum': 8721,
    'sup': 8835,
    'sup1': 185,
    'sup2': 178,
    'sup3': 179,
    'supe': 8839,
    'szlig': 223,
    'tau': 964,
    'there4': 8756,
    'theta': 952,
    'thetasym': 977,
    'thinsp': 8201,
    'thorn': 254,
    'tilde': 732,
    'times': 215,
    'trade': 8482,
    'uArr': 8657,
    'uacute': 250,
    'uarr': 8593,
    'ucirc': 251,
    'ugrave': 249,
    'uml': 168,
    'upsih': 978,
    'upsilon': 965,
    'uuml': 252,
    'weierp': 8472,
    'xi': 958,
    'yacute': 253,
    'yen': 165,
    'yuml': 255,
    'zeta': 950,
    'zwj': 8205,
    'zwnj': 8204
}

########NEW FILE########
__FILENAME__ = _native
# -*- coding: utf-8 -*-
"""
    markupsafe._native
    ~~~~~~~~~~~~~~~~~~

    Native Python implementation the C module is not compiled.

    :copyright: (c) 2010 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
from jinja2._markupsafe import Markup


def escape(s):
    """Convert the characters &, <, >, ' and " in string s to HTML-safe
    sequences.  Use this if you need to display text that might contain
    such characters in HTML.  Marks return value as markup string.
    """
    if hasattr(s, '__html__'):
        return s.__html__()
    return Markup(unicode(s)
        .replace('&', '&amp;')
        .replace('>', '&gt;')
        .replace('<', '&lt;')
        .replace("'", '&#39;')
        .replace('"', '&#34;')
    )


def escape_silent(s):
    """Like :func:`escape` but converts `None` into an empty
    markup string.
    """
    if s is None:
        return Markup()
    return escape(s)


def soft_unicode(s):
    """Make a string unicode if it isn't already.  That way a markup
    string is not converted back to unicode.
    """
    if not isinstance(s, unicode):
        s = unicode(s)
    return s

########NEW FILE########
__FILENAME__ = _stringdefs
# -*- coding: utf-8 -*-
"""
    jinja2._stringdefs
    ~~~~~~~~~~~~~~~~~~

    Strings of all Unicode characters of a certain category.
    Used for matching in Unicode-aware languages. Run to regenerate.

    Inspired by chartypes_create.py from the MoinMoin project, original
    implementation from Pygments.

    :copyright: Copyright 2006-2009 by the Jinja team, see AUTHORS.
    :license: BSD, see LICENSE for details.
"""

Cc = u'\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f\x7f\x80\x81\x82\x83\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f\x90\x91\x92\x93\x94\x95\x96\x97\x98\x99\x9a\x9b\x9c\x9d\x9e\x9f'

Cf = u'\xad\u0600\u0601\u0602\u0603\u06dd\u070f\u17b4\u17b5\u200b\u200c\u200d\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2060\u2061\u2062\u2063\u206a\u206b\u206c\u206d\u206e\u206f\ufeff\ufff9\ufffa\ufffb'

Cn = u'\u0242\u0243\u0244\u0245\u0246\u0247\u0248\u0249\u024a\u024b\u024c\u024d\u024e\u024f\u0370\u0371\u0372\u0373\u0376\u0377\u0378\u0379\u037b\u037c\u037d\u037f\u0380\u0381\u0382\u0383\u038b\u038d\u03a2\u03cf\u0487\u04cf\u04fa\u04fb\u04fc\u04fd\u04fe\u04ff\u0510\u0511\u0512\u0513\u0514\u0515\u0516\u0517\u0518\u0519\u051a\u051b\u051c\u051d\u051e\u051f\u0520\u0521\u0522\u0523\u0524\u0525\u0526\u0527\u0528\u0529\u052a\u052b\u052c\u052d\u052e\u052f\u0530\u0557\u0558\u0560\u0588\u058b\u058c\u058d\u058e\u058f\u0590\u05ba\u05c8\u05c9\u05ca\u05cb\u05cc\u05cd\u05ce\u05cf\u05eb\u05ec\u05ed\u05ee\u05ef\u05f5\u05f6\u05f7\u05f8\u05f9\u05fa\u05fb\u05fc\u05fd\u05fe\u05ff\u0604\u0605\u0606\u0607\u0608\u0609\u060a\u0616\u0617\u0618\u0619\u061a\u061c\u061d\u0620\u063b\u063c\u063d\u063e\u063f\u065f\u070e\u074b\u074c\u076e\u076f\u0770\u0771\u0772\u0773\u0774\u0775\u0776\u0777\u0778\u0779\u077a\u077b\u077c\u077d\u077e\u077f\u07b2\u07b3\u07b4\u07b5\u07b6\u07b7\u07b8\u07b9\u07ba\u07bb\u07bc\u07bd\u07be\u07bf\u07c0\u07c1\u07c2\u07c3\u07c4\u07c5\u07c6\u07c7\u07c8\u07c9\u07ca\u07cb\u07cc\u07cd\u07ce\u07cf\u07d0\u07d1\u07d2\u07d3\u07d4\u07d5\u07d6\u07d7\u07d8\u07d9\u07da\u07db\u07dc\u07dd\u07de\u07df\u07e0\u07e1\u07e2\u07e3\u07e4\u07e5\u07e6\u07e7\u07e8\u07e9\u07ea\u07eb\u07ec\u07ed\u07ee\u07ef\u07f0\u07f1\u07f2\u07f3\u07f4\u07f5\u07f6\u07f7\u07f8\u07f9\u07fa\u07fb\u07fc\u07fd\u07fe\u07ff\u0800\u0801\u0802\u0803\u0804\u0805\u0806\u0807\u0808\u0809\u080a\u080b\u080c\u080d\u080e\u080f\u0810\u0811\u0812\u0813\u0814\u0815\u0816\u0817\u0818\u0819\u081a\u081b\u081c\u081d\u081e\u081f\u0820\u0821\u0822\u0823\u0824\u0825\u0826\u0827\u0828\u0829\u082a\u082b\u082c\u082d\u082e\u082f\u0830\u0831\u0832\u0833\u0834\u0835\u0836\u0837\u0838\u0839\u083a\u083b\u083c\u083d\u083e\u083f\u0840\u0841\u0842\u0843\u0844\u0845\u0846\u0847\u0848\u0849\u084a\u084b\u084c\u084d\u084e\u084f\u0850\u0851\u0852\u0853\u0854\u0855\u0856\u0857\u0858\u0859\u085a\u085b\u085c\u085d\u085e\u085f\u0860\u0861\u0862\u0863\u0864\u0865\u0866\u0867\u0868\u0869\u086a\u086b\u086c\u086d\u086e\u086f\u0870\u0871\u0872\u0873\u0874\u0875\u0876\u0877\u0878\u0879\u087a\u087b\u087c\u087d\u087e\u087f\u0880\u0881\u0882\u0883\u0884\u0885\u0886\u0887\u0888\u0889\u088a\u088b\u088c\u088d\u088e\u088f\u0890\u0891\u0892\u0893\u0894\u0895\u0896\u0897\u0898\u0899\u089a\u089b\u089c\u089d\u089e\u089f\u08a0\u08a1\u08a2\u08a3\u08a4\u08a5\u08a6\u08a7\u08a8\u08a9\u08aa\u08ab\u08ac\u08ad\u08ae\u08af\u08b0\u08b1\u08b2\u08b3\u08b4\u08b5\u08b6\u08b7\u08b8\u08b9\u08ba\u08bb\u08bc\u08bd\u08be\u08bf\u08c0\u08c1\u08c2\u08c3\u08c4\u08c5\u08c6\u08c7\u08c8\u08c9\u08ca\u08cb\u08cc\u08cd\u08ce\u08cf\u08d0\u08d1\u08d2\u08d3\u08d4\u08d5\u08d6\u08d7\u08d8\u08d9\u08da\u08db\u08dc\u08dd\u08de\u08df\u08e0\u08e1\u08e2\u08e3\u08e4\u08e5\u08e6\u08e7\u08e8\u08e9\u08ea\u08eb\u08ec\u08ed\u08ee\u08ef\u08f0\u08f1\u08f2\u08f3\u08f4\u08f5\u08f6\u08f7\u08f8\u08f9\u08fa\u08fb\u08fc\u08fd\u08fe\u08ff\u0900\u093a\u093b\u094e\u094f\u0955\u0956\u0957\u0971\u0972\u0973\u0974\u0975\u0976\u0977\u0978\u0979\u097a\u097b\u097c\u097e\u097f\u0980\u0984\u098d\u098e\u0991\u0992\u09a9\u09b1\u09b3\u09b4\u09b5\u09ba\u09bb\u09c5\u09c6\u09c9\u09ca\u09cf\u09d0\u09d1\u09d2\u09d3\u09d4\u09d5\u09d6\u09d8\u09d9\u09da\u09db\u09de\u09e4\u09e5\u09fb\u09fc\u09fd\u09fe\u09ff\u0a00\u0a04\u0a0b\u0a0c\u0a0d\u0a0e\u0a11\u0a12\u0a29\u0a31\u0a34\u0a37\u0a3a\u0a3b\u0a3d\u0a43\u0a44\u0a45\u0a46\u0a49\u0a4a\u0a4e\u0a4f\u0a50\u0a51\u0a52\u0a53\u0a54\u0a55\u0a56\u0a57\u0a58\u0a5d\u0a5f\u0a60\u0a61\u0a62\u0a63\u0a64\u0a65\u0a75\u0a76\u0a77\u0a78\u0a79\u0a7a\u0a7b\u0a7c\u0a7d\u0a7e\u0a7f\u0a80\u0a84\u0a8e\u0a92\u0aa9\u0ab1\u0ab4\u0aba\u0abb\u0ac6\u0aca\u0ace\u0acf\u0ad1\u0ad2\u0ad3\u0ad4\u0ad5\u0ad6\u0ad7\u0ad8\u0ad9\u0ada\u0adb\u0adc\u0add\u0ade\u0adf\u0ae4\u0ae5\u0af0\u0af2\u0af3\u0af4\u0af5\u0af6\u0af7\u0af8\u0af9\u0afa\u0afb\u0afc\u0afd\u0afe\u0aff\u0b00\u0b04\u0b0d\u0b0e\u0b11\u0b12\u0b29\u0b31\u0b34\u0b3a\u0b3b\u0b44\u0b45\u0b46\u0b49\u0b4a\u0b4e\u0b4f\u0b50\u0b51\u0b52\u0b53\u0b54\u0b55\u0b58\u0b59\u0b5a\u0b5b\u0b5e\u0b62\u0b63\u0b64\u0b65\u0b72\u0b73\u0b74\u0b75\u0b76\u0b77\u0b78\u0b79\u0b7a\u0b7b\u0b7c\u0b7d\u0b7e\u0b7f\u0b80\u0b81\u0b84\u0b8b\u0b8c\u0b8d\u0b91\u0b96\u0b97\u0b98\u0b9b\u0b9d\u0ba0\u0ba1\u0ba2\u0ba5\u0ba6\u0ba7\u0bab\u0bac\u0bad\u0bba\u0bbb\u0bbc\u0bbd\u0bc3\u0bc4\u0bc5\u0bc9\u0bce\u0bcf\u0bd0\u0bd1\u0bd2\u0bd3\u0bd4\u0bd5\u0bd6\u0bd8\u0bd9\u0bda\u0bdb\u0bdc\u0bdd\u0bde\u0bdf\u0be0\u0be1\u0be2\u0be3\u0be4\u0be5\u0bfb\u0bfc\u0bfd\u0bfe\u0bff\u0c00\u0c04\u0c0d\u0c11\u0c29\u0c34\u0c3a\u0c3b\u0c3c\u0c3d\u0c45\u0c49\u0c4e\u0c4f\u0c50\u0c51\u0c52\u0c53\u0c54\u0c57\u0c58\u0c59\u0c5a\u0c5b\u0c5c\u0c5d\u0c5e\u0c5f\u0c62\u0c63\u0c64\u0c65\u0c70\u0c71\u0c72\u0c73\u0c74\u0c75\u0c76\u0c77\u0c78\u0c79\u0c7a\u0c7b\u0c7c\u0c7d\u0c7e\u0c7f\u0c80\u0c81\u0c84\u0c8d\u0c91\u0ca9\u0cb4\u0cba\u0cbb\u0cc5\u0cc9\u0cce\u0ccf\u0cd0\u0cd1\u0cd2\u0cd3\u0cd4\u0cd7\u0cd8\u0cd9\u0cda\u0cdb\u0cdc\u0cdd\u0cdf\u0ce2\u0ce3\u0ce4\u0ce5\u0cf0\u0cf1\u0cf2\u0cf3\u0cf4\u0cf5\u0cf6\u0cf7\u0cf8\u0cf9\u0cfa\u0cfb\u0cfc\u0cfd\u0cfe\u0cff\u0d00\u0d01\u0d04\u0d0d\u0d11\u0d29\u0d3a\u0d3b\u0d3c\u0d3d\u0d44\u0d45\u0d49\u0d4e\u0d4f\u0d50\u0d51\u0d52\u0d53\u0d54\u0d55\u0d56\u0d58\u0d59\u0d5a\u0d5b\u0d5c\u0d5d\u0d5e\u0d5f\u0d62\u0d63\u0d64\u0d65\u0d70\u0d71\u0d72\u0d73\u0d74\u0d75\u0d76\u0d77\u0d78\u0d79\u0d7a\u0d7b\u0d7c\u0d7d\u0d7e\u0d7f\u0d80\u0d81\u0d84\u0d97\u0d98\u0d99\u0db2\u0dbc\u0dbe\u0dbf\u0dc7\u0dc8\u0dc9\u0dcb\u0dcc\u0dcd\u0dce\u0dd5\u0dd7\u0de0\u0de1\u0de2\u0de3\u0de4\u0de5\u0de6\u0de7\u0de8\u0de9\u0dea\u0deb\u0dec\u0ded\u0dee\u0def\u0df0\u0df1\u0df5\u0df6\u0df7\u0df8\u0df9\u0dfa\u0dfb\u0dfc\u0dfd\u0dfe\u0dff\u0e00\u0e3b\u0e3c\u0e3d\u0e3e\u0e5c\u0e5d\u0e5e\u0e5f\u0e60\u0e61\u0e62\u0e63\u0e64\u0e65\u0e66\u0e67\u0e68\u0e69\u0e6a\u0e6b\u0e6c\u0e6d\u0e6e\u0e6f\u0e70\u0e71\u0e72\u0e73\u0e74\u0e75\u0e76\u0e77\u0e78\u0e79\u0e7a\u0e7b\u0e7c\u0e7d\u0e7e\u0e7f\u0e80\u0e83\u0e85\u0e86\u0e89\u0e8b\u0e8c\u0e8e\u0e8f\u0e90\u0e91\u0e92\u0e93\u0e98\u0ea0\u0ea4\u0ea6\u0ea8\u0ea9\u0eac\u0eba\u0ebe\u0ebf\u0ec5\u0ec7\u0ece\u0ecf\u0eda\u0edb\u0ede\u0edf\u0ee0\u0ee1\u0ee2\u0ee3\u0ee4\u0ee5\u0ee6\u0ee7\u0ee8\u0ee9\u0eea\u0eeb\u0eec\u0eed\u0eee\u0eef\u0ef0\u0ef1\u0ef2\u0ef3\u0ef4\u0ef5\u0ef6\u0ef7\u0ef8\u0ef9\u0efa\u0efb\u0efc\u0efd\u0efe\u0eff\u0f48\u0f6b\u0f6c\u0f6d\u0f6e\u0f6f\u0f70\u0f8c\u0f8d\u0f8e\u0f8f\u0f98\u0fbd\u0fcd\u0fce\u0fd2\u0fd3\u0fd4\u0fd5\u0fd6\u0fd7\u0fd8\u0fd9\u0fda\u0fdb\u0fdc\u0fdd\u0fde\u0fdf\u0fe0\u0fe1\u0fe2\u0fe3\u0fe4\u0fe5\u0fe6\u0fe7\u0fe8\u0fe9\u0fea\u0feb\u0fec\u0fed\u0fee\u0fef\u0ff0\u0ff1\u0ff2\u0ff3\u0ff4\u0ff5\u0ff6\u0ff7\u0ff8\u0ff9\u0ffa\u0ffb\u0ffc\u0ffd\u0ffe\u0fff\u1022\u1028\u102b\u1033\u1034\u1035\u103a\u103b\u103c\u103d\u103e\u103f\u105a\u105b\u105c\u105d\u105e\u105f\u1060\u1061\u1062\u1063\u1064\u1065\u1066\u1067\u1068\u1069\u106a\u106b\u106c\u106d\u106e\u106f\u1070\u1071\u1072\u1073\u1074\u1075\u1076\u1077\u1078\u1079\u107a\u107b\u107c\u107d\u107e\u107f\u1080\u1081\u1082\u1083\u1084\u1085\u1086\u1087\u1088\u1089\u108a\u108b\u108c\u108d\u108e\u108f\u1090\u1091\u1092\u1093\u1094\u1095\u1096\u1097\u1098\u1099\u109a\u109b\u109c\u109d\u109e\u109f\u10c6\u10c7\u10c8\u10c9\u10ca\u10cb\u10cc\u10cd\u10ce\u10cf\u10fd\u10fe\u10ff\u115a\u115b\u115c\u115d\u115e\u11a3\u11a4\u11a5\u11a6\u11a7\u11fa\u11fb\u11fc\u11fd\u11fe\u11ff\u1249\u124e\u124f\u1257\u1259\u125e\u125f\u1289\u128e\u128f\u12b1\u12b6\u12b7\u12bf\u12c1\u12c6\u12c7\u12d7\u1311\u1316\u1317\u135b\u135c\u135d\u135e\u137d\u137e\u137f\u139a\u139b\u139c\u139d\u139e\u139f\u13f5\u13f6\u13f7\u13f8\u13f9\u13fa\u13fb\u13fc\u13fd\u13fe\u13ff\u1400\u1677\u1678\u1679\u167a\u167b\u167c\u167d\u167e\u167f\u169d\u169e\u169f\u16f1\u16f2\u16f3\u16f4\u16f5\u16f6\u16f7\u16f8\u16f9\u16fa\u16fb\u16fc\u16fd\u16fe\u16ff\u170d\u1715\u1716\u1717\u1718\u1719\u171a\u171b\u171c\u171d\u171e\u171f\u1737\u1738\u1739\u173a\u173b\u173c\u173d\u173e\u173f\u1754\u1755\u1756\u1757\u1758\u1759\u175a\u175b\u175c\u175d\u175e\u175f\u176d\u1771\u1774\u1775\u1776\u1777\u1778\u1779\u177a\u177b\u177c\u177d\u177e\u177f\u17de\u17df\u17ea\u17eb\u17ec\u17ed\u17ee\u17ef\u17fa\u17fb\u17fc\u17fd\u17fe\u17ff\u180f\u181a\u181b\u181c\u181d\u181e\u181f\u1878\u1879\u187a\u187b\u187c\u187d\u187e\u187f\u18aa\u18ab\u18ac\u18ad\u18ae\u18af\u18b0\u18b1\u18b2\u18b3\u18b4\u18b5\u18b6\u18b7\u18b8\u18b9\u18ba\u18bb\u18bc\u18bd\u18be\u18bf\u18c0\u18c1\u18c2\u18c3\u18c4\u18c5\u18c6\u18c7\u18c8\u18c9\u18ca\u18cb\u18cc\u18cd\u18ce\u18cf\u18d0\u18d1\u18d2\u18d3\u18d4\u18d5\u18d6\u18d7\u18d8\u18d9\u18da\u18db\u18dc\u18dd\u18de\u18df\u18e0\u18e1\u18e2\u18e3\u18e4\u18e5\u18e6\u18e7\u18e8\u18e9\u18ea\u18eb\u18ec\u18ed\u18ee\u18ef\u18f0\u18f1\u18f2\u18f3\u18f4\u18f5\u18f6\u18f7\u18f8\u18f9\u18fa\u18fb\u18fc\u18fd\u18fe\u18ff\u191d\u191e\u191f\u192c\u192d\u192e\u192f\u193c\u193d\u193e\u193f\u1941\u1942\u1943\u196e\u196f\u1975\u1976\u1977\u1978\u1979\u197a\u197b\u197c\u197d\u197e\u197f\u19aa\u19ab\u19ac\u19ad\u19ae\u19af\u19ca\u19cb\u19cc\u19cd\u19ce\u19cf\u19da\u19db\u19dc\u19dd\u1a1c\u1a1d\u1a20\u1a21\u1a22\u1a23\u1a24\u1a25\u1a26\u1a27\u1a28\u1a29\u1a2a\u1a2b\u1a2c\u1a2d\u1a2e\u1a2f\u1a30\u1a31\u1a32\u1a33\u1a34\u1a35\u1a36\u1a37\u1a38\u1a39\u1a3a\u1a3b\u1a3c\u1a3d\u1a3e\u1a3f\u1a40\u1a41\u1a42\u1a43\u1a44\u1a45\u1a46\u1a47\u1a48\u1a49\u1a4a\u1a4b\u1a4c\u1a4d\u1a4e\u1a4f\u1a50\u1a51\u1a52\u1a53\u1a54\u1a55\u1a56\u1a57\u1a58\u1a59\u1a5a\u1a5b\u1a5c\u1a5d\u1a5e\u1a5f\u1a60\u1a61\u1a62\u1a63\u1a64\u1a65\u1a66\u1a67\u1a68\u1a69\u1a6a\u1a6b\u1a6c\u1a6d\u1a6e\u1a6f\u1a70\u1a71\u1a72\u1a73\u1a74\u1a75\u1a76\u1a77\u1a78\u1a79\u1a7a\u1a7b\u1a7c\u1a7d\u1a7e\u1a7f\u1a80\u1a81\u1a82\u1a83\u1a84\u1a85\u1a86\u1a87\u1a88\u1a89\u1a8a\u1a8b\u1a8c\u1a8d\u1a8e\u1a8f\u1a90\u1a91\u1a92\u1a93\u1a94\u1a95\u1a96\u1a97\u1a98\u1a99\u1a9a\u1a9b\u1a9c\u1a9d\u1a9e\u1a9f\u1aa0\u1aa1\u1aa2\u1aa3\u1aa4\u1aa5\u1aa6\u1aa7\u1aa8\u1aa9\u1aaa\u1aab\u1aac\u1aad\u1aae\u1aaf\u1ab0\u1ab1\u1ab2\u1ab3\u1ab4\u1ab5\u1ab6\u1ab7\u1ab8\u1ab9\u1aba\u1abb\u1abc\u1abd\u1abe\u1abf\u1ac0\u1ac1\u1ac2\u1ac3\u1ac4\u1ac5\u1ac6\u1ac7\u1ac8\u1ac9\u1aca\u1acb\u1acc\u1acd\u1ace\u1acf\u1ad0\u1ad1\u1ad2\u1ad3\u1ad4\u1ad5\u1ad6\u1ad7\u1ad8\u1ad9\u1ada\u1adb\u1adc\u1add\u1ade\u1adf\u1ae0\u1ae1\u1ae2\u1ae3\u1ae4\u1ae5\u1ae6\u1ae7\u1ae8\u1ae9\u1aea\u1aeb\u1aec\u1aed\u1aee\u1aef\u1af0\u1af1\u1af2\u1af3\u1af4\u1af5\u1af6\u1af7\u1af8\u1af9\u1afa\u1afb\u1afc\u1afd\u1afe\u1aff\u1b00\u1b01\u1b02\u1b03\u1b04\u1b05\u1b06\u1b07\u1b08\u1b09\u1b0a\u1b0b\u1b0c\u1b0d\u1b0e\u1b0f\u1b10\u1b11\u1b12\u1b13\u1b14\u1b15\u1b16\u1b17\u1b18\u1b19\u1b1a\u1b1b\u1b1c\u1b1d\u1b1e\u1b1f\u1b20\u1b21\u1b22\u1b23\u1b24\u1b25\u1b26\u1b27\u1b28\u1b29\u1b2a\u1b2b\u1b2c\u1b2d\u1b2e\u1b2f\u1b30\u1b31\u1b32\u1b33\u1b34\u1b35\u1b36\u1b37\u1b38\u1b39\u1b3a\u1b3b\u1b3c\u1b3d\u1b3e\u1b3f\u1b40\u1b41\u1b42\u1b43\u1b44\u1b45\u1b46\u1b47\u1b48\u1b49\u1b4a\u1b4b\u1b4c\u1b4d\u1b4e\u1b4f\u1b50\u1b51\u1b52\u1b53\u1b54\u1b55\u1b56\u1b57\u1b58\u1b59\u1b5a\u1b5b\u1b5c\u1b5d\u1b5e\u1b5f\u1b60\u1b61\u1b62\u1b63\u1b64\u1b65\u1b66\u1b67\u1b68\u1b69\u1b6a\u1b6b\u1b6c\u1b6d\u1b6e\u1b6f\u1b70\u1b71\u1b72\u1b73\u1b74\u1b75\u1b76\u1b77\u1b78\u1b79\u1b7a\u1b7b\u1b7c\u1b7d\u1b7e\u1b7f\u1b80\u1b81\u1b82\u1b83\u1b84\u1b85\u1b86\u1b87\u1b88\u1b89\u1b8a\u1b8b\u1b8c\u1b8d\u1b8e\u1b8f\u1b90\u1b91\u1b92\u1b93\u1b94\u1b95\u1b96\u1b97\u1b98\u1b99\u1b9a\u1b9b\u1b9c\u1b9d\u1b9e\u1b9f\u1ba0\u1ba1\u1ba2\u1ba3\u1ba4\u1ba5\u1ba6\u1ba7\u1ba8\u1ba9\u1baa\u1bab\u1bac\u1bad\u1bae\u1baf\u1bb0\u1bb1\u1bb2\u1bb3\u1bb4\u1bb5\u1bb6\u1bb7\u1bb8\u1bb9\u1bba\u1bbb\u1bbc\u1bbd\u1bbe\u1bbf\u1bc0\u1bc1\u1bc2\u1bc3\u1bc4\u1bc5\u1bc6\u1bc7\u1bc8\u1bc9\u1bca\u1bcb\u1bcc\u1bcd\u1bce\u1bcf\u1bd0\u1bd1\u1bd2\u1bd3\u1bd4\u1bd5\u1bd6\u1bd7\u1bd8\u1bd9\u1bda\u1bdb\u1bdc\u1bdd\u1bde\u1bdf\u1be0\u1be1\u1be2\u1be3\u1be4\u1be5\u1be6\u1be7\u1be8\u1be9\u1bea\u1beb\u1bec\u1bed\u1bee\u1bef\u1bf0\u1bf1\u1bf2\u1bf3\u1bf4\u1bf5\u1bf6\u1bf7\u1bf8\u1bf9\u1bfa\u1bfb\u1bfc\u1bfd\u1bfe\u1bff\u1c00\u1c01\u1c02\u1c03\u1c04\u1c05\u1c06\u1c07\u1c08\u1c09\u1c0a\u1c0b\u1c0c\u1c0d\u1c0e\u1c0f\u1c10\u1c11\u1c12\u1c13\u1c14\u1c15\u1c16\u1c17\u1c18\u1c19\u1c1a\u1c1b\u1c1c\u1c1d\u1c1e\u1c1f\u1c20\u1c21\u1c22\u1c23\u1c24\u1c25\u1c26\u1c27\u1c28\u1c29\u1c2a\u1c2b\u1c2c\u1c2d\u1c2e\u1c2f\u1c30\u1c31\u1c32\u1c33\u1c34\u1c35\u1c36\u1c37\u1c38\u1c39\u1c3a\u1c3b\u1c3c\u1c3d\u1c3e\u1c3f\u1c40\u1c41\u1c42\u1c43\u1c44\u1c45\u1c46\u1c47\u1c48\u1c49\u1c4a\u1c4b\u1c4c\u1c4d\u1c4e\u1c4f\u1c50\u1c51\u1c52\u1c53\u1c54\u1c55\u1c56\u1c57\u1c58\u1c59\u1c5a\u1c5b\u1c5c\u1c5d\u1c5e\u1c5f\u1c60\u1c61\u1c62\u1c63\u1c64\u1c65\u1c66\u1c67\u1c68\u1c69\u1c6a\u1c6b\u1c6c\u1c6d\u1c6e\u1c6f\u1c70\u1c71\u1c72\u1c73\u1c74\u1c75\u1c76\u1c77\u1c78\u1c79\u1c7a\u1c7b\u1c7c\u1c7d\u1c7e\u1c7f\u1c80\u1c81\u1c82\u1c83\u1c84\u1c85\u1c86\u1c87\u1c88\u1c89\u1c8a\u1c8b\u1c8c\u1c8d\u1c8e\u1c8f\u1c90\u1c91\u1c92\u1c93\u1c94\u1c95\u1c96\u1c97\u1c98\u1c99\u1c9a\u1c9b\u1c9c\u1c9d\u1c9e\u1c9f\u1ca0\u1ca1\u1ca2\u1ca3\u1ca4\u1ca5\u1ca6\u1ca7\u1ca8\u1ca9\u1caa\u1cab\u1cac\u1cad\u1cae\u1caf\u1cb0\u1cb1\u1cb2\u1cb3\u1cb4\u1cb5\u1cb6\u1cb7\u1cb8\u1cb9\u1cba\u1cbb\u1cbc\u1cbd\u1cbe\u1cbf\u1cc0\u1cc1\u1cc2\u1cc3\u1cc4\u1cc5\u1cc6\u1cc7\u1cc8\u1cc9\u1cca\u1ccb\u1ccc\u1ccd\u1cce\u1ccf\u1cd0\u1cd1\u1cd2\u1cd3\u1cd4\u1cd5\u1cd6\u1cd7\u1cd8\u1cd9\u1cda\u1cdb\u1cdc\u1cdd\u1cde\u1cdf\u1ce0\u1ce1\u1ce2\u1ce3\u1ce4\u1ce5\u1ce6\u1ce7\u1ce8\u1ce9\u1cea\u1ceb\u1cec\u1ced\u1cee\u1cef\u1cf0\u1cf1\u1cf2\u1cf3\u1cf4\u1cf5\u1cf6\u1cf7\u1cf8\u1cf9\u1cfa\u1cfb\u1cfc\u1cfd\u1cfe\u1cff\u1dc4\u1dc5\u1dc6\u1dc7\u1dc8\u1dc9\u1dca\u1dcb\u1dcc\u1dcd\u1dce\u1dcf\u1dd0\u1dd1\u1dd2\u1dd3\u1dd4\u1dd5\u1dd6\u1dd7\u1dd8\u1dd9\u1dda\u1ddb\u1ddc\u1ddd\u1dde\u1ddf\u1de0\u1de1\u1de2\u1de3\u1de4\u1de5\u1de6\u1de7\u1de8\u1de9\u1dea\u1deb\u1dec\u1ded\u1dee\u1def\u1df0\u1df1\u1df2\u1df3\u1df4\u1df5\u1df6\u1df7\u1df8\u1df9\u1dfa\u1dfb\u1dfc\u1dfd\u1dfe\u1dff\u1e9c\u1e9d\u1e9e\u1e9f\u1efa\u1efb\u1efc\u1efd\u1efe\u1eff\u1f16\u1f17\u1f1e\u1f1f\u1f46\u1f47\u1f4e\u1f4f\u1f58\u1f5a\u1f5c\u1f5e\u1f7e\u1f7f\u1fb5\u1fc5\u1fd4\u1fd5\u1fdc\u1ff0\u1ff1\u1ff5\u1fff\u2064\u2065\u2066\u2067\u2068\u2069\u2072\u2073\u208f\u2095\u2096\u2097\u2098\u2099\u209a\u209b\u209c\u209d\u209e\u209f\u20b6\u20b7\u20b8\u20b9\u20ba\u20bb\u20bc\u20bd\u20be\u20bf\u20c0\u20c1\u20c2\u20c3\u20c4\u20c5\u20c6\u20c7\u20c8\u20c9\u20ca\u20cb\u20cc\u20cd\u20ce\u20cf\u20ec\u20ed\u20ee\u20ef\u20f0\u20f1\u20f2\u20f3\u20f4\u20f5\u20f6\u20f7\u20f8\u20f9\u20fa\u20fb\u20fc\u20fd\u20fe\u20ff\u214d\u214e\u214f\u2150\u2151\u2152\u2184\u2185\u2186\u2187\u2188\u2189\u218a\u218b\u218c\u218d\u218e\u218f\u23dc\u23dd\u23de\u23df\u23e0\u23e1\u23e2\u23e3\u23e4\u23e5\u23e6\u23e7\u23e8\u23e9\u23ea\u23eb\u23ec\u23ed\u23ee\u23ef\u23f0\u23f1\u23f2\u23f3\u23f4\u23f5\u23f6\u23f7\u23f8\u23f9\u23fa\u23fb\u23fc\u23fd\u23fe\u23ff\u2427\u2428\u2429\u242a\u242b\u242c\u242d\u242e\u242f\u2430\u2431\u2432\u2433\u2434\u2435\u2436\u2437\u2438\u2439\u243a\u243b\u243c\u243d\u243e\u243f\u244b\u244c\u244d\u244e\u244f\u2450\u2451\u2452\u2453\u2454\u2455\u2456\u2457\u2458\u2459\u245a\u245b\u245c\u245d\u245e\u245f\u269d\u269e\u269f\u26b2\u26b3\u26b4\u26b5\u26b6\u26b7\u26b8\u26b9\u26ba\u26bb\u26bc\u26bd\u26be\u26bf\u26c0\u26c1\u26c2\u26c3\u26c4\u26c5\u26c6\u26c7\u26c8\u26c9\u26ca\u26cb\u26cc\u26cd\u26ce\u26cf\u26d0\u26d1\u26d2\u26d3\u26d4\u26d5\u26d6\u26d7\u26d8\u26d9\u26da\u26db\u26dc\u26dd\u26de\u26df\u26e0\u26e1\u26e2\u26e3\u26e4\u26e5\u26e6\u26e7\u26e8\u26e9\u26ea\u26eb\u26ec\u26ed\u26ee\u26ef\u26f0\u26f1\u26f2\u26f3\u26f4\u26f5\u26f6\u26f7\u26f8\u26f9\u26fa\u26fb\u26fc\u26fd\u26fe\u26ff\u2700\u2705\u270a\u270b\u2728\u274c\u274e\u2753\u2754\u2755\u2757\u275f\u2760\u2795\u2796\u2797\u27b0\u27bf\u27c7\u27c8\u27c9\u27ca\u27cb\u27cc\u27cd\u27ce\u27cf\u27ec\u27ed\u27ee\u27ef\u2b14\u2b15\u2b16\u2b17\u2b18\u2b19\u2b1a\u2b1b\u2b1c\u2b1d\u2b1e\u2b1f\u2b20\u2b21\u2b22\u2b23\u2b24\u2b25\u2b26\u2b27\u2b28\u2b29\u2b2a\u2b2b\u2b2c\u2b2d\u2b2e\u2b2f\u2b30\u2b31\u2b32\u2b33\u2b34\u2b35\u2b36\u2b37\u2b38\u2b39\u2b3a\u2b3b\u2b3c\u2b3d\u2b3e\u2b3f\u2b40\u2b41\u2b42\u2b43\u2b44\u2b45\u2b46\u2b47\u2b48\u2b49\u2b4a\u2b4b\u2b4c\u2b4d\u2b4e\u2b4f\u2b50\u2b51\u2b52\u2b53\u2b54\u2b55\u2b56\u2b57\u2b58\u2b59\u2b5a\u2b5b\u2b5c\u2b5d\u2b5e\u2b5f\u2b60\u2b61\u2b62\u2b63\u2b64\u2b65\u2b66\u2b67\u2b68\u2b69\u2b6a\u2b6b\u2b6c\u2b6d\u2b6e\u2b6f\u2b70\u2b71\u2b72\u2b73\u2b74\u2b75\u2b76\u2b77\u2b78\u2b79\u2b7a\u2b7b\u2b7c\u2b7d\u2b7e\u2b7f\u2b80\u2b81\u2b82\u2b83\u2b84\u2b85\u2b86\u2b87\u2b88\u2b89\u2b8a\u2b8b\u2b8c\u2b8d\u2b8e\u2b8f\u2b90\u2b91\u2b92\u2b93\u2b94\u2b95\u2b96\u2b97\u2b98\u2b99\u2b9a\u2b9b\u2b9c\u2b9d\u2b9e\u2b9f\u2ba0\u2ba1\u2ba2\u2ba3\u2ba4\u2ba5\u2ba6\u2ba7\u2ba8\u2ba9\u2baa\u2bab\u2bac\u2bad\u2bae\u2baf\u2bb0\u2bb1\u2bb2\u2bb3\u2bb4\u2bb5\u2bb6\u2bb7\u2bb8\u2bb9\u2bba\u2bbb\u2bbc\u2bbd\u2bbe\u2bbf\u2bc0\u2bc1\u2bc2\u2bc3\u2bc4\u2bc5\u2bc6\u2bc7\u2bc8\u2bc9\u2bca\u2bcb\u2bcc\u2bcd\u2bce\u2bcf\u2bd0\u2bd1\u2bd2\u2bd3\u2bd4\u2bd5\u2bd6\u2bd7\u2bd8\u2bd9\u2bda\u2bdb\u2bdc\u2bdd\u2bde\u2bdf\u2be0\u2be1\u2be2\u2be3\u2be4\u2be5\u2be6\u2be7\u2be8\u2be9\u2bea\u2beb\u2bec\u2bed\u2bee\u2bef\u2bf0\u2bf1\u2bf2\u2bf3\u2bf4\u2bf5\u2bf6\u2bf7\u2bf8\u2bf9\u2bfa\u2bfb\u2bfc\u2bfd\u2bfe\u2bff\u2c2f\u2c5f\u2c60\u2c61\u2c62\u2c63\u2c64\u2c65\u2c66\u2c67\u2c68\u2c69\u2c6a\u2c6b\u2c6c\u2c6d\u2c6e\u2c6f\u2c70\u2c71\u2c72\u2c73\u2c74\u2c75\u2c76\u2c77\u2c78\u2c79\u2c7a\u2c7b\u2c7c\u2c7d\u2c7e\u2c7f\u2ceb\u2cec\u2ced\u2cee\u2cef\u2cf0\u2cf1\u2cf2\u2cf3\u2cf4\u2cf5\u2cf6\u2cf7\u2cf8\u2d26\u2d27\u2d28\u2d29\u2d2a\u2d2b\u2d2c\u2d2d\u2d2e\u2d2f\u2d66\u2d67\u2d68\u2d69\u2d6a\u2d6b\u2d6c\u2d6d\u2d6e\u2d70\u2d71\u2d72\u2d73\u2d74\u2d75\u2d76\u2d77\u2d78\u2d79\u2d7a\u2d7b\u2d7c\u2d7d\u2d7e\u2d7f\u2d97\u2d98\u2d99\u2d9a\u2d9b\u2d9c\u2d9d\u2d9e\u2d9f\u2da7\u2daf\u2db7\u2dbf\u2dc7\u2dcf\u2dd7\u2ddf\u2de0\u2de1\u2de2\u2de3\u2de4\u2de5\u2de6\u2de7\u2de8\u2de9\u2dea\u2deb\u2dec\u2ded\u2dee\u2def\u2df0\u2df1\u2df2\u2df3\u2df4\u2df5\u2df6\u2df7\u2df8\u2df9\u2dfa\u2dfb\u2dfc\u2dfd\u2dfe\u2dff\u2e18\u2e19\u2e1a\u2e1b\u2e1e\u2e1f\u2e20\u2e21\u2e22\u2e23\u2e24\u2e25\u2e26\u2e27\u2e28\u2e29\u2e2a\u2e2b\u2e2c\u2e2d\u2e2e\u2e2f\u2e30\u2e31\u2e32\u2e33\u2e34\u2e35\u2e36\u2e37\u2e38\u2e39\u2e3a\u2e3b\u2e3c\u2e3d\u2e3e\u2e3f\u2e40\u2e41\u2e42\u2e43\u2e44\u2e45\u2e46\u2e47\u2e48\u2e49\u2e4a\u2e4b\u2e4c\u2e4d\u2e4e\u2e4f\u2e50\u2e51\u2e52\u2e53\u2e54\u2e55\u2e56\u2e57\u2e58\u2e59\u2e5a\u2e5b\u2e5c\u2e5d\u2e5e\u2e5f\u2e60\u2e61\u2e62\u2e63\u2e64\u2e65\u2e66\u2e67\u2e68\u2e69\u2e6a\u2e6b\u2e6c\u2e6d\u2e6e\u2e6f\u2e70\u2e71\u2e72\u2e73\u2e74\u2e75\u2e76\u2e77\u2e78\u2e79\u2e7a\u2e7b\u2e7c\u2e7d\u2e7e\u2e7f\u2e9a\u2ef4\u2ef5\u2ef6\u2ef7\u2ef8\u2ef9\u2efa\u2efb\u2efc\u2efd\u2efe\u2eff\u2fd6\u2fd7\u2fd8\u2fd9\u2fda\u2fdb\u2fdc\u2fdd\u2fde\u2fdf\u2fe0\u2fe1\u2fe2\u2fe3\u2fe4\u2fe5\u2fe6\u2fe7\u2fe8\u2fe9\u2fea\u2feb\u2fec\u2fed\u2fee\u2fef\u2ffc\u2ffd\u2ffe\u2fff\u3040\u3097\u3098\u3100\u3101\u3102\u3103\u3104\u312d\u312e\u312f\u3130\u318f\u31b8\u31b9\u31ba\u31bb\u31bc\u31bd\u31be\u31bf\u31d0\u31d1\u31d2\u31d3\u31d4\u31d5\u31d6\u31d7\u31d8\u31d9\u31da\u31db\u31dc\u31dd\u31de\u31df\u31e0\u31e1\u31e2\u31e3\u31e4\u31e5\u31e6\u31e7\u31e8\u31e9\u31ea\u31eb\u31ec\u31ed\u31ee\u31ef\u321f\u3244\u3245\u3246\u3247\u3248\u3249\u324a\u324b\u324c\u324d\u324e\u324f\u32ff\u4db6\u4db7\u4db8\u4db9\u4dba\u4dbb\u4dbc\u4dbd\u4dbe\u4dbf\u9fbc\u9fbd\u9fbe\u9fbf\u9fc0\u9fc1\u9fc2\u9fc3\u9fc4\u9fc5\u9fc6\u9fc7\u9fc8\u9fc9\u9fca\u9fcb\u9fcc\u9fcd\u9fce\u9fcf\u9fd0\u9fd1\u9fd2\u9fd3\u9fd4\u9fd5\u9fd6\u9fd7\u9fd8\u9fd9\u9fda\u9fdb\u9fdc\u9fdd\u9fde\u9fdf\u9fe0\u9fe1\u9fe2\u9fe3\u9fe4\u9fe5\u9fe6\u9fe7\u9fe8\u9fe9\u9fea\u9feb\u9fec\u9fed\u9fee\u9fef\u9ff0\u9ff1\u9ff2\u9ff3\u9ff4\u9ff5\u9ff6\u9ff7\u9ff8\u9ff9\u9ffa\u9ffb\u9ffc\u9ffd\u9ffe\u9fff\ua48d\ua48e\ua48f\ua4c7\ua4c8\ua4c9\ua4ca\ua4cb\ua4cc\ua4cd\ua4ce\ua4cf\ua4d0\ua4d1\ua4d2\ua4d3\ua4d4\ua4d5\ua4d6\ua4d7\ua4d8\ua4d9\ua4da\ua4db\ua4dc\ua4dd\ua4de\ua4df\ua4e0\ua4e1\ua4e2\ua4e3\ua4e4\ua4e5\ua4e6\ua4e7\ua4e8\ua4e9\ua4ea\ua4eb\ua4ec\ua4ed\ua4ee\ua4ef\ua4f0\ua4f1\ua4f2\ua4f3\ua4f4\ua4f5\ua4f6\ua4f7\ua4f8\ua4f9\ua4fa\ua4fb\ua4fc\ua4fd\ua4fe\ua4ff\ua500\ua501\ua502\ua503\ua504\ua505\ua506\ua507\ua508\ua509\ua50a\ua50b\ua50c\ua50d\ua50e\ua50f\ua510\ua511\ua512\ua513\ua514\ua515\ua516\ua517\ua518\ua519\ua51a\ua51b\ua51c\ua51d\ua51e\ua51f\ua520\ua521\ua522\ua523\ua524\ua525\ua526\ua527\ua528\ua529\ua52a\ua52b\ua52c\ua52d\ua52e\ua52f\ua530\ua531\ua532\ua533\ua534\ua535\ua536\ua537\ua538\ua539\ua53a\ua53b\ua53c\ua53d\ua53e\ua53f\ua540\ua541\ua542\ua543\ua544\ua545\ua546\ua547\ua548\ua549\ua54a\ua54b\ua54c\ua54d\ua54e\ua54f\ua550\ua551\ua552\ua553\ua554\ua555\ua556\ua557\ua558\ua559\ua55a\ua55b\ua55c\ua55d\ua55e\ua55f\ua560\ua561\ua562\ua563\ua564\ua565\ua566\ua567\ua568\ua569\ua56a\ua56b\ua56c\ua56d\ua56e\ua56f\ua570\ua571\ua572\ua573\ua574\ua575\ua576\ua577\ua578\ua579\ua57a\ua57b\ua57c\ua57d\ua57e\ua57f\ua580\ua581\ua582\ua583\ua584\ua585\ua586\ua587\ua588\ua589\ua58a\ua58b\ua58c\ua58d\ua58e\ua58f\ua590\ua591\ua592\ua593\ua594\ua595\ua596\ua597\ua598\ua599\ua59a\ua59b\ua59c\ua59d\ua59e\ua59f\ua5a0\ua5a1\ua5a2\ua5a3\ua5a4\ua5a5\ua5a6\ua5a7\ua5a8\ua5a9\ua5aa\ua5ab\ua5ac\ua5ad\ua5ae\ua5af\ua5b0\ua5b1\ua5b2\ua5b3\ua5b4\ua5b5\ua5b6\ua5b7\ua5b8\ua5b9\ua5ba\ua5bb\ua5bc\ua5bd\ua5be\ua5bf\ua5c0\ua5c1\ua5c2\ua5c3\ua5c4\ua5c5\ua5c6\ua5c7\ua5c8\ua5c9\ua5ca\ua5cb\ua5cc\ua5cd\ua5ce\ua5cf\ua5d0\ua5d1\ua5d2\ua5d3\ua5d4\ua5d5\ua5d6\ua5d7\ua5d8\ua5d9\ua5da\ua5db\ua5dc\ua5dd\ua5de\ua5df\ua5e0\ua5e1\ua5e2\ua5e3\ua5e4\ua5e5\ua5e6\ua5e7\ua5e8\ua5e9\ua5ea\ua5eb\ua5ec\ua5ed\ua5ee\ua5ef\ua5f0\ua5f1\ua5f2\ua5f3\ua5f4\ua5f5\ua5f6\ua5f7\ua5f8\ua5f9\ua5fa\ua5fb\ua5fc\ua5fd\ua5fe\ua5ff\ua600\ua601\ua602\ua603\ua604\ua605\ua606\ua607\ua608\ua609\ua60a\ua60b\ua60c\ua60d\ua60e\ua60f\ua610\ua611\ua612\ua613\ua614\ua615\ua616\ua617\ua618\ua619\ua61a\ua61b\ua61c\ua61d\ua61e\ua61f\ua620\ua621\ua622\ua623\ua624\ua625\ua626\ua627\ua628\ua629\ua62a\ua62b\ua62c\ua62d\ua62e\ua62f\ua630\ua631\ua632\ua633\ua634\ua635\ua636\ua637\ua638\ua639\ua63a\ua63b\ua63c\ua63d\ua63e\ua63f\ua640\ua641\ua642\ua643\ua644\ua645\ua646\ua647\ua648\ua649\ua64a\ua64b\ua64c\ua64d\ua64e\ua64f\ua650\ua651\ua652\ua653\ua654\ua655\ua656\ua657\ua658\ua659\ua65a\ua65b\ua65c\ua65d\ua65e\ua65f\ua660\ua661\ua662\ua663\ua664\ua665\ua666\ua667\ua668\ua669\ua66a\ua66b\ua66c\ua66d\ua66e\ua66f\ua670\ua671\ua672\ua673\ua674\ua675\ua676\ua677\ua678\ua679\ua67a\ua67b\ua67c\ua67d\ua67e\ua67f\ua680\ua681\ua682\ua683\ua684\ua685\ua686\ua687\ua688\ua689\ua68a\ua68b\ua68c\ua68d\ua68e\ua68f\ua690\ua691\ua692\ua693\ua694\ua695\ua696\ua697\ua698\ua699\ua69a\ua69b\ua69c\ua69d\ua69e\ua69f\ua6a0\ua6a1\ua6a2\ua6a3\ua6a4\ua6a5\ua6a6\ua6a7\ua6a8\ua6a9\ua6aa\ua6ab\ua6ac\ua6ad\ua6ae\ua6af\ua6b0\ua6b1\ua6b2\ua6b3\ua6b4\ua6b5\ua6b6\ua6b7\ua6b8\ua6b9\ua6ba\ua6bb\ua6bc\ua6bd\ua6be\ua6bf\ua6c0\ua6c1\ua6c2\ua6c3\ua6c4\ua6c5\ua6c6\ua6c7\ua6c8\ua6c9\ua6ca\ua6cb\ua6cc\ua6cd\ua6ce\ua6cf\ua6d0\ua6d1\ua6d2\ua6d3\ua6d4\ua6d5\ua6d6\ua6d7\ua6d8\ua6d9\ua6da\ua6db\ua6dc\ua6dd\ua6de\ua6df\ua6e0\ua6e1\ua6e2\ua6e3\ua6e4\ua6e5\ua6e6\ua6e7\ua6e8\ua6e9\ua6ea\ua6eb\ua6ec\ua6ed\ua6ee\ua6ef\ua6f0\ua6f1\ua6f2\ua6f3\ua6f4\ua6f5\ua6f6\ua6f7\ua6f8\ua6f9\ua6fa\ua6fb\ua6fc\ua6fd\ua6fe\ua6ff\ua717\ua718\ua719\ua71a\ua71b\ua71c\ua71d\ua71e\ua71f\ua720\ua721\ua722\ua723\ua724\ua725\ua726\ua727\ua728\ua729\ua72a\ua72b\ua72c\ua72d\ua72e\ua72f\ua730\ua731\ua732\ua733\ua734\ua735\ua736\ua737\ua738\ua739\ua73a\ua73b\ua73c\ua73d\ua73e\ua73f\ua740\ua741\ua742\ua743\ua744\ua745\ua746\ua747\ua748\ua749\ua74a\ua74b\ua74c\ua74d\ua74e\ua74f\ua750\ua751\ua752\ua753\ua754\ua755\ua756\ua757\ua758\ua759\ua75a\ua75b\ua75c\ua75d\ua75e\ua75f\ua760\ua761\ua762\ua763\ua764\ua765\ua766\ua767\ua768\ua769\ua76a\ua76b\ua76c\ua76d\ua76e\ua76f\ua770\ua771\ua772\ua773\ua774\ua775\ua776\ua777\ua778\ua779\ua77a\ua77b\ua77c\ua77d\ua77e\ua77f\ua780\ua781\ua782\ua783\ua784\ua785\ua786\ua787\ua788\ua789\ua78a\ua78b\ua78c\ua78d\ua78e\ua78f\ua790\ua791\ua792\ua793\ua794\ua795\ua796\ua797\ua798\ua799\ua79a\ua79b\ua79c\ua79d\ua79e\ua79f\ua7a0\ua7a1\ua7a2\ua7a3\ua7a4\ua7a5\ua7a6\ua7a7\ua7a8\ua7a9\ua7aa\ua7ab\ua7ac\ua7ad\ua7ae\ua7af\ua7b0\ua7b1\ua7b2\ua7b3\ua7b4\ua7b5\ua7b6\ua7b7\ua7b8\ua7b9\ua7ba\ua7bb\ua7bc\ua7bd\ua7be\ua7bf\ua7c0\ua7c1\ua7c2\ua7c3\ua7c4\ua7c5\ua7c6\ua7c7\ua7c8\ua7c9\ua7ca\ua7cb\ua7cc\ua7cd\ua7ce\ua7cf\ua7d0\ua7d1\ua7d2\ua7d3\ua7d4\ua7d5\ua7d6\ua7d7\ua7d8\ua7d9\ua7da\ua7db\ua7dc\ua7dd\ua7de\ua7df\ua7e0\ua7e1\ua7e2\ua7e3\ua7e4\ua7e5\ua7e6\ua7e7\ua7e8\ua7e9\ua7ea\ua7eb\ua7ec\ua7ed\ua7ee\ua7ef\ua7f0\ua7f1\ua7f2\ua7f3\ua7f4\ua7f5\ua7f6\ua7f7\ua7f8\ua7f9\ua7fa\ua7fb\ua7fc\ua7fd\ua7fe\ua7ff\ua82c\ua82d\ua82e\ua82f\ua830\ua831\ua832\ua833\ua834\ua835\ua836\ua837\ua838\ua839\ua83a\ua83b\ua83c\ua83d\ua83e\ua83f\ua840\ua841\ua842\ua843\ua844\ua845\ua846\ua847\ua848\ua849\ua84a\ua84b\ua84c\ua84d\ua84e\ua84f\ua850\ua851\ua852\ua853\ua854\ua855\ua856\ua857\ua858\ua859\ua85a\ua85b\ua85c\ua85d\ua85e\ua85f\ua860\ua861\ua862\ua863\ua864\ua865\ua866\ua867\ua868\ua869\ua86a\ua86b\ua86c\ua86d\ua86e\ua86f\ua870\ua871\ua872\ua873\ua874\ua875\ua876\ua877\ua878\ua879\ua87a\ua87b\ua87c\ua87d\ua87e\ua87f\ua880\ua881\ua882\ua883\ua884\ua885\ua886\ua887\ua888\ua889\ua88a\ua88b\ua88c\ua88d\ua88e\ua88f\ua890\ua891\ua892\ua893\ua894\ua895\ua896\ua897\ua898\ua899\ua89a\ua89b\ua89c\ua89d\ua89e\ua89f\ua8a0\ua8a1\ua8a2\ua8a3\ua8a4\ua8a5\ua8a6\ua8a7\ua8a8\ua8a9\ua8aa\ua8ab\ua8ac\ua8ad\ua8ae\ua8af\ua8b0\ua8b1\ua8b2\ua8b3\ua8b4\ua8b5\ua8b6\ua8b7\ua8b8\ua8b9\ua8ba\ua8bb\ua8bc\ua8bd\ua8be\ua8bf\ua8c0\ua8c1\ua8c2\ua8c3\ua8c4\ua8c5\ua8c6\ua8c7\ua8c8\ua8c9\ua8ca\ua8cb\ua8cc\ua8cd\ua8ce\ua8cf\ua8d0\ua8d1\ua8d2\ua8d3\ua8d4\ua8d5\ua8d6\ua8d7\ua8d8\ua8d9\ua8da\ua8db\ua8dc\ua8dd\ua8de\ua8df\ua8e0\ua8e1\ua8e2\ua8e3\ua8e4\ua8e5\ua8e6\ua8e7\ua8e8\ua8e9\ua8ea\ua8eb\ua8ec\ua8ed\ua8ee\ua8ef\ua8f0\ua8f1\ua8f2\ua8f3\ua8f4\ua8f5\ua8f6\ua8f7\ua8f8\ua8f9\ua8fa\ua8fb\ua8fc\ua8fd\ua8fe\ua8ff\ua900\ua901\ua902\ua903\ua904\ua905\ua906\ua907\ua908\ua909\ua90a\ua90b\ua90c\ua90d\ua90e\ua90f\ua910\ua911\ua912\ua913\ua914\ua915\ua916\ua917\ua918\ua919\ua91a\ua91b\ua91c\ua91d\ua91e\ua91f\ua920\ua921\ua922\ua923\ua924\ua925\ua926\ua927\ua928\ua929\ua92a\ua92b\ua92c\ua92d\ua92e\ua92f\ua930\ua931\ua932\ua933\ua934\ua935\ua936\ua937\ua938\ua939\ua93a\ua93b\ua93c\ua93d\ua93e\ua93f\ua940\ua941\ua942\ua943\ua944\ua945\ua946\ua947\ua948\ua949\ua94a\ua94b\ua94c\ua94d\ua94e\ua94f\ua950\ua951\ua952\ua953\ua954\ua955\ua956\ua957\ua958\ua959\ua95a\ua95b\ua95c\ua95d\ua95e\ua95f\ua960\ua961\ua962\ua963\ua964\ua965\ua966\ua967\ua968\ua969\ua96a\ua96b\ua96c\ua96d\ua96e\ua96f\ua970\ua971\ua972\ua973\ua974\ua975\ua976\ua977\ua978\ua979\ua97a\ua97b\ua97c\ua97d\ua97e\ua97f\ua980\ua981\ua982\ua983\ua984\ua985\ua986\ua987\ua988\ua989\ua98a\ua98b\ua98c\ua98d\ua98e\ua98f\ua990\ua991\ua992\ua993\ua994\ua995\ua996\ua997\ua998\ua999\ua99a\ua99b\ua99c\ua99d\ua99e\ua99f\ua9a0\ua9a1\ua9a2\ua9a3\ua9a4\ua9a5\ua9a6\ua9a7\ua9a8\ua9a9\ua9aa\ua9ab\ua9ac\ua9ad\ua9ae\ua9af\ua9b0\ua9b1\ua9b2\ua9b3\ua9b4\ua9b5\ua9b6\ua9b7\ua9b8\ua9b9\ua9ba\ua9bb\ua9bc\ua9bd\ua9be\ua9bf\ua9c0\ua9c1\ua9c2\ua9c3\ua9c4\ua9c5\ua9c6\ua9c7\ua9c8\ua9c9\ua9ca\ua9cb\ua9cc\ua9cd\ua9ce\ua9cf\ua9d0\ua9d1\ua9d2\ua9d3\ua9d4\ua9d5\ua9d6\ua9d7\ua9d8\ua9d9\ua9da\ua9db\ua9dc\ua9dd\ua9de\ua9df\ua9e0\ua9e1\ua9e2\ua9e3\ua9e4\ua9e5\ua9e6\ua9e7\ua9e8\ua9e9\ua9ea\ua9eb\ua9ec\ua9ed\ua9ee\ua9ef\ua9f0\ua9f1\ua9f2\ua9f3\ua9f4\ua9f5\ua9f6\ua9f7\ua9f8\ua9f9\ua9fa\ua9fb\ua9fc\ua9fd\ua9fe\ua9ff\uaa00\uaa01\uaa02\uaa03\uaa04\uaa05\uaa06\uaa07\uaa08\uaa09\uaa0a\uaa0b\uaa0c\uaa0d\uaa0e\uaa0f\uaa10\uaa11\uaa12\uaa13\uaa14\uaa15\uaa16\uaa17\uaa18\uaa19\uaa1a\uaa1b\uaa1c\uaa1d\uaa1e\uaa1f\uaa20\uaa21\uaa22\uaa23\uaa24\uaa25\uaa26\uaa27\uaa28\uaa29\uaa2a\uaa2b\uaa2c\uaa2d\uaa2e\uaa2f\uaa30\uaa31\uaa32\uaa33\uaa34\uaa35\uaa36\uaa37\uaa38\uaa39\uaa3a\uaa3b\uaa3c\uaa3d\uaa3e\uaa3f\uaa40\uaa41\uaa42\uaa43\uaa44\uaa45\uaa46\uaa47\uaa48\uaa49\uaa4a\uaa4b\uaa4c\uaa4d\uaa4e\uaa4f\uaa50\uaa51\uaa52\uaa53\uaa54\uaa55\uaa56\uaa57\uaa58\uaa59\uaa5a\uaa5b\uaa5c\uaa5d\uaa5e\uaa5f\uaa60\uaa61\uaa62\uaa63\uaa64\uaa65\uaa66\uaa67\uaa68\uaa69\uaa6a\uaa6b\uaa6c\uaa6d\uaa6e\uaa6f\uaa70\uaa71\uaa72\uaa73\uaa74\uaa75\uaa76\uaa77\uaa78\uaa79\uaa7a\uaa7b\uaa7c\uaa7d\uaa7e\uaa7f\uaa80\uaa81\uaa82\uaa83\uaa84\uaa85\uaa86\uaa87\uaa88\uaa89\uaa8a\uaa8b\uaa8c\uaa8d\uaa8e\uaa8f\uaa90\uaa91\uaa92\uaa93\uaa94\uaa95\uaa96\uaa97\uaa98\uaa99\uaa9a\uaa9b\uaa9c\uaa9d\uaa9e\uaa9f\uaaa0\uaaa1\uaaa2\uaaa3\uaaa4\uaaa5\uaaa6\uaaa7\uaaa8\uaaa9\uaaaa\uaaab\uaaac\uaaad\uaaae\uaaaf\uaab0\uaab1\uaab2\uaab3\uaab4\uaab5\uaab6\uaab7\uaab8\uaab9\uaaba\uaabb\uaabc\uaabd\uaabe\uaabf\uaac0\uaac1\uaac2\uaac3\uaac4\uaac5\uaac6\uaac7\uaac8\uaac9\uaaca\uaacb\uaacc\uaacd\uaace\uaacf\uaad0\uaad1\uaad2\uaad3\uaad4\uaad5\uaad6\uaad7\uaad8\uaad9\uaada\uaadb\uaadc\uaadd\uaade\uaadf\uaae0\uaae1\uaae2\uaae3\uaae4\uaae5\uaae6\uaae7\uaae8\uaae9\uaaea\uaaeb\uaaec\uaaed\uaaee\uaaef\uaaf0\uaaf1\uaaf2\uaaf3\uaaf4\uaaf5\uaaf6\uaaf7\uaaf8\uaaf9\uaafa\uaafb\uaafc\uaafd\uaafe\uaaff\uab00\uab01\uab02\uab03\uab04\uab05\uab06\uab07\uab08\uab09\uab0a\uab0b\uab0c\uab0d\uab0e\uab0f\uab10\uab11\uab12\uab13\uab14\uab15\uab16\uab17\uab18\uab19\uab1a\uab1b\uab1c\uab1d\uab1e\uab1f\uab20\uab21\uab22\uab23\uab24\uab25\uab26\uab27\uab28\uab29\uab2a\uab2b\uab2c\uab2d\uab2e\uab2f\uab30\uab31\uab32\uab33\uab34\uab35\uab36\uab37\uab38\uab39\uab3a\uab3b\uab3c\uab3d\uab3e\uab3f\uab40\uab41\uab42\uab43\uab44\uab45\uab46\uab47\uab48\uab49\uab4a\uab4b\uab4c\uab4d\uab4e\uab4f\uab50\uab51\uab52\uab53\uab54\uab55\uab56\uab57\uab58\uab59\uab5a\uab5b\uab5c\uab5d\uab5e\uab5f\uab60\uab61\uab62\uab63\uab64\uab65\uab66\uab67\uab68\uab69\uab6a\uab6b\uab6c\uab6d\uab6e\uab6f\uab70\uab71\uab72\uab73\uab74\uab75\uab76\uab77\uab78\uab79\uab7a\uab7b\uab7c\uab7d\uab7e\uab7f\uab80\uab81\uab82\uab83\uab84\uab85\uab86\uab87\uab88\uab89\uab8a\uab8b\uab8c\uab8d\uab8e\uab8f\uab90\uab91\uab92\uab93\uab94\uab95\uab96\uab97\uab98\uab99\uab9a\uab9b\uab9c\uab9d\uab9e\uab9f\uaba0\uaba1\uaba2\uaba3\uaba4\uaba5\uaba6\uaba7\uaba8\uaba9\uabaa\uabab\uabac\uabad\uabae\uabaf\uabb0\uabb1\uabb2\uabb3\uabb4\uabb5\uabb6\uabb7\uabb8\uabb9\uabba\uabbb\uabbc\uabbd\uabbe\uabbf\uabc0\uabc1\uabc2\uabc3\uabc4\uabc5\uabc6\uabc7\uabc8\uabc9\uabca\uabcb\uabcc\uabcd\uabce\uabcf\uabd0\uabd1\uabd2\uabd3\uabd4\uabd5\uabd6\uabd7\uabd8\uabd9\uabda\uabdb\uabdc\uabdd\uabde\uabdf\uabe0\uabe1\uabe2\uabe3\uabe4\uabe5\uabe6\uabe7\uabe8\uabe9\uabea\uabeb\uabec\uabed\uabee\uabef\uabf0\uabf1\uabf2\uabf3\uabf4\uabf5\uabf6\uabf7\uabf8\uabf9\uabfa\uabfb\uabfc\uabfd\uabfe\uabff\ud7a4\ud7a5\ud7a6\ud7a7\ud7a8\ud7a9\ud7aa\ud7ab\ud7ac\ud7ad\ud7ae\ud7af\ud7b0\ud7b1\ud7b2\ud7b3\ud7b4\ud7b5\ud7b6\ud7b7\ud7b8\ud7b9\ud7ba\ud7bb\ud7bc\ud7bd\ud7be\ud7bf\ud7c0\ud7c1\ud7c2\ud7c3\ud7c4\ud7c5\ud7c6\ud7c7\ud7c8\ud7c9\ud7ca\ud7cb\ud7cc\ud7cd\ud7ce\ud7cf\ud7d0\ud7d1\ud7d2\ud7d3\ud7d4\ud7d5\ud7d6\ud7d7\ud7d8\ud7d9\ud7da\ud7db\ud7dc\ud7dd\ud7de\ud7df\ud7e0\ud7e1\ud7e2\ud7e3\ud7e4\ud7e5\ud7e6\ud7e7\ud7e8\ud7e9\ud7ea\ud7eb\ud7ec\ud7ed\ud7ee\ud7ef\ud7f0\ud7f1\ud7f2\ud7f3\ud7f4\ud7f5\ud7f6\ud7f7\ud7f8\ud7f9\ud7fa\ud7fb\ud7fc\ud7fd\ud7fe\ud7ff\ufa2e\ufa2f\ufa6b\ufa6c\ufa6d\ufa6e\ufa6f\ufada\ufadb\ufadc\ufadd\ufade\ufadf\ufae0\ufae1\ufae2\ufae3\ufae4\ufae5\ufae6\ufae7\ufae8\ufae9\ufaea\ufaeb\ufaec\ufaed\ufaee\ufaef\ufaf0\ufaf1\ufaf2\ufaf3\ufaf4\ufaf5\ufaf6\ufaf7\ufaf8\ufaf9\ufafa\ufafb\ufafc\ufafd\ufafe\ufaff\ufb07\ufb08\ufb09\ufb0a\ufb0b\ufb0c\ufb0d\ufb0e\ufb0f\ufb10\ufb11\ufb12\ufb18\ufb19\ufb1a\ufb1b\ufb1c\ufb37\ufb3d\ufb3f\ufb42\ufb45\ufbb2\ufbb3\ufbb4\ufbb5\ufbb6\ufbb7\ufbb8\ufbb9\ufbba\ufbbb\ufbbc\ufbbd\ufbbe\ufbbf\ufbc0\ufbc1\ufbc2\ufbc3\ufbc4\ufbc5\ufbc6\ufbc7\ufbc8\ufbc9\ufbca\ufbcb\ufbcc\ufbcd\ufbce\ufbcf\ufbd0\ufbd1\ufbd2\ufd40\ufd41\ufd42\ufd43\ufd44\ufd45\ufd46\ufd47\ufd48\ufd49\ufd4a\ufd4b\ufd4c\ufd4d\ufd4e\ufd4f\ufd90\ufd91\ufdc8\ufdc9\ufdca\ufdcb\ufdcc\ufdcd\ufdce\ufdcf\ufdd0\ufdd1\ufdd2\ufdd3\ufdd4\ufdd5\ufdd6\ufdd7\ufdd8\ufdd9\ufdda\ufddb\ufddc\ufddd\ufdde\ufddf\ufde0\ufde1\ufde2\ufde3\ufde4\ufde5\ufde6\ufde7\ufde8\ufde9\ufdea\ufdeb\ufdec\ufded\ufdee\ufdef\ufdfe\ufdff\ufe1a\ufe1b\ufe1c\ufe1d\ufe1e\ufe1f\ufe24\ufe25\ufe26\ufe27\ufe28\ufe29\ufe2a\ufe2b\ufe2c\ufe2d\ufe2e\ufe2f\ufe53\ufe67\ufe6c\ufe6d\ufe6e\ufe6f\ufe75\ufefd\ufefe\uff00\uffbf\uffc0\uffc1\uffc8\uffc9\uffd0\uffd1\uffd8\uffd9\uffdd\uffde\uffdf\uffe7\uffef\ufff0\ufff1\ufff2\ufff3\ufff4\ufff5\ufff6\ufff7\ufff8\ufffe'

Co = u'\ue000\ue001\ue002\ue003\ue004\ue005\ue006\ue007\ue008\ue009\ue00a\ue00b\ue00c\ue00d\ue00e\ue00f\ue010\ue011\ue012\ue013\ue014\ue015\ue016\ue017\ue018\ue019\ue01a\ue01b\ue01c\ue01d\ue01e\ue01f\ue020\ue021\ue022\ue023\ue024\ue025\ue026\ue027\ue028\ue029\ue02a\ue02b\ue02c\ue02d\ue02e\ue02f\ue030\ue031\ue032\ue033\ue034\ue035\ue036\ue037\ue038\ue039\ue03a\ue03b\ue03c\ue03d\ue03e\ue03f\ue040\ue041\ue042\ue043\ue044\ue045\ue046\ue047\ue048\ue049\ue04a\ue04b\ue04c\ue04d\ue04e\ue04f\ue050\ue051\ue052\ue053\ue054\ue055\ue056\ue057\ue058\ue059\ue05a\ue05b\ue05c\ue05d\ue05e\ue05f\ue060\ue061\ue062\ue063\ue064\ue065\ue066\ue067\ue068\ue069\ue06a\ue06b\ue06c\ue06d\ue06e\ue06f\ue070\ue071\ue072\ue073\ue074\ue075\ue076\ue077\ue078\ue079\ue07a\ue07b\ue07c\ue07d\ue07e\ue07f\ue080\ue081\ue082\ue083\ue084\ue085\ue086\ue087\ue088\ue089\ue08a\ue08b\ue08c\ue08d\ue08e\ue08f\ue090\ue091\ue092\ue093\ue094\ue095\ue096\ue097\ue098\ue099\ue09a\ue09b\ue09c\ue09d\ue09e\ue09f\ue0a0\ue0a1\ue0a2\ue0a3\ue0a4\ue0a5\ue0a6\ue0a7\ue0a8\ue0a9\ue0aa\ue0ab\ue0ac\ue0ad\ue0ae\ue0af\ue0b0\ue0b1\ue0b2\ue0b3\ue0b4\ue0b5\ue0b6\ue0b7\ue0b8\ue0b9\ue0ba\ue0bb\ue0bc\ue0bd\ue0be\ue0bf\ue0c0\ue0c1\ue0c2\ue0c3\ue0c4\ue0c5\ue0c6\ue0c7\ue0c8\ue0c9\ue0ca\ue0cb\ue0cc\ue0cd\ue0ce\ue0cf\ue0d0\ue0d1\ue0d2\ue0d3\ue0d4\ue0d5\ue0d6\ue0d7\ue0d8\ue0d9\ue0da\ue0db\ue0dc\ue0dd\ue0de\ue0df\ue0e0\ue0e1\ue0e2\ue0e3\ue0e4\ue0e5\ue0e6\ue0e7\ue0e8\ue0e9\ue0ea\ue0eb\ue0ec\ue0ed\ue0ee\ue0ef\ue0f0\ue0f1\ue0f2\ue0f3\ue0f4\ue0f5\ue0f6\ue0f7\ue0f8\ue0f9\ue0fa\ue0fb\ue0fc\ue0fd\ue0fe\ue0ff\ue100\ue101\ue102\ue103\ue104\ue105\ue106\ue107\ue108\ue109\ue10a\ue10b\ue10c\ue10d\ue10e\ue10f\ue110\ue111\ue112\ue113\ue114\ue115\ue116\ue117\ue118\ue119\ue11a\ue11b\ue11c\ue11d\ue11e\ue11f\ue120\ue121\ue122\ue123\ue124\ue125\ue126\ue127\ue128\ue129\ue12a\ue12b\ue12c\ue12d\ue12e\ue12f\ue130\ue131\ue132\ue133\ue134\ue135\ue136\ue137\ue138\ue139\ue13a\ue13b\ue13c\ue13d\ue13e\ue13f\ue140\ue141\ue142\ue143\ue144\ue145\ue146\ue147\ue148\ue149\ue14a\ue14b\ue14c\ue14d\ue14e\ue14f\ue150\ue151\ue152\ue153\ue154\ue155\ue156\ue157\ue158\ue159\ue15a\ue15b\ue15c\ue15d\ue15e\ue15f\ue160\ue161\ue162\ue163\ue164\ue165\ue166\ue167\ue168\ue169\ue16a\ue16b\ue16c\ue16d\ue16e\ue16f\ue170\ue171\ue172\ue173\ue174\ue175\ue176\ue177\ue178\ue179\ue17a\ue17b\ue17c\ue17d\ue17e\ue17f\ue180\ue181\ue182\ue183\ue184\ue185\ue186\ue187\ue188\ue189\ue18a\ue18b\ue18c\ue18d\ue18e\ue18f\ue190\ue191\ue192\ue193\ue194\ue195\ue196\ue197\ue198\ue199\ue19a\ue19b\ue19c\ue19d\ue19e\ue19f\ue1a0\ue1a1\ue1a2\ue1a3\ue1a4\ue1a5\ue1a6\ue1a7\ue1a8\ue1a9\ue1aa\ue1ab\ue1ac\ue1ad\ue1ae\ue1af\ue1b0\ue1b1\ue1b2\ue1b3\ue1b4\ue1b5\ue1b6\ue1b7\ue1b8\ue1b9\ue1ba\ue1bb\ue1bc\ue1bd\ue1be\ue1bf\ue1c0\ue1c1\ue1c2\ue1c3\ue1c4\ue1c5\ue1c6\ue1c7\ue1c8\ue1c9\ue1ca\ue1cb\ue1cc\ue1cd\ue1ce\ue1cf\ue1d0\ue1d1\ue1d2\ue1d3\ue1d4\ue1d5\ue1d6\ue1d7\ue1d8\ue1d9\ue1da\ue1db\ue1dc\ue1dd\ue1de\ue1df\ue1e0\ue1e1\ue1e2\ue1e3\ue1e4\ue1e5\ue1e6\ue1e7\ue1e8\ue1e9\ue1ea\ue1eb\ue1ec\ue1ed\ue1ee\ue1ef\ue1f0\ue1f1\ue1f2\ue1f3\ue1f4\ue1f5\ue1f6\ue1f7\ue1f8\ue1f9\ue1fa\ue1fb\ue1fc\ue1fd\ue1fe\ue1ff\ue200\ue201\ue202\ue203\ue204\ue205\ue206\ue207\ue208\ue209\ue20a\ue20b\ue20c\ue20d\ue20e\ue20f\ue210\ue211\ue212\ue213\ue214\ue215\ue216\ue217\ue218\ue219\ue21a\ue21b\ue21c\ue21d\ue21e\ue21f\ue220\ue221\ue222\ue223\ue224\ue225\ue226\ue227\ue228\ue229\ue22a\ue22b\ue22c\ue22d\ue22e\ue22f\ue230\ue231\ue232\ue233\ue234\ue235\ue236\ue237\ue238\ue239\ue23a\ue23b\ue23c\ue23d\ue23e\ue23f\ue240\ue241\ue242\ue243\ue244\ue245\ue246\ue247\ue248\ue249\ue24a\ue24b\ue24c\ue24d\ue24e\ue24f\ue250\ue251\ue252\ue253\ue254\ue255\ue256\ue257\ue258\ue259\ue25a\ue25b\ue25c\ue25d\ue25e\ue25f\ue260\ue261\ue262\ue263\ue264\ue265\ue266\ue267\ue268\ue269\ue26a\ue26b\ue26c\ue26d\ue26e\ue26f\ue270\ue271\ue272\ue273\ue274\ue275\ue276\ue277\ue278\ue279\ue27a\ue27b\ue27c\ue27d\ue27e\ue27f\ue280\ue281\ue282\ue283\ue284\ue285\ue286\ue287\ue288\ue289\ue28a\ue28b\ue28c\ue28d\ue28e\ue28f\ue290\ue291\ue292\ue293\ue294\ue295\ue296\ue297\ue298\ue299\ue29a\ue29b\ue29c\ue29d\ue29e\ue29f\ue2a0\ue2a1\ue2a2\ue2a3\ue2a4\ue2a5\ue2a6\ue2a7\ue2a8\ue2a9\ue2aa\ue2ab\ue2ac\ue2ad\ue2ae\ue2af\ue2b0\ue2b1\ue2b2\ue2b3\ue2b4\ue2b5\ue2b6\ue2b7\ue2b8\ue2b9\ue2ba\ue2bb\ue2bc\ue2bd\ue2be\ue2bf\ue2c0\ue2c1\ue2c2\ue2c3\ue2c4\ue2c5\ue2c6\ue2c7\ue2c8\ue2c9\ue2ca\ue2cb\ue2cc\ue2cd\ue2ce\ue2cf\ue2d0\ue2d1\ue2d2\ue2d3\ue2d4\ue2d5\ue2d6\ue2d7\ue2d8\ue2d9\ue2da\ue2db\ue2dc\ue2dd\ue2de\ue2df\ue2e0\ue2e1\ue2e2\ue2e3\ue2e4\ue2e5\ue2e6\ue2e7\ue2e8\ue2e9\ue2ea\ue2eb\ue2ec\ue2ed\ue2ee\ue2ef\ue2f0\ue2f1\ue2f2\ue2f3\ue2f4\ue2f5\ue2f6\ue2f7\ue2f8\ue2f9\ue2fa\ue2fb\ue2fc\ue2fd\ue2fe\ue2ff\ue300\ue301\ue302\ue303\ue304\ue305\ue306\ue307\ue308\ue309\ue30a\ue30b\ue30c\ue30d\ue30e\ue30f\ue310\ue311\ue312\ue313\ue314\ue315\ue316\ue317\ue318\ue319\ue31a\ue31b\ue31c\ue31d\ue31e\ue31f\ue320\ue321\ue322\ue323\ue324\ue325\ue326\ue327\ue328\ue329\ue32a\ue32b\ue32c\ue32d\ue32e\ue32f\ue330\ue331\ue332\ue333\ue334\ue335\ue336\ue337\ue338\ue339\ue33a\ue33b\ue33c\ue33d\ue33e\ue33f\ue340\ue341\ue342\ue343\ue344\ue345\ue346\ue347\ue348\ue349\ue34a\ue34b\ue34c\ue34d\ue34e\ue34f\ue350\ue351\ue352\ue353\ue354\ue355\ue356\ue357\ue358\ue359\ue35a\ue35b\ue35c\ue35d\ue35e\ue35f\ue360\ue361\ue362\ue363\ue364\ue365\ue366\ue367\ue368\ue369\ue36a\ue36b\ue36c\ue36d\ue36e\ue36f\ue370\ue371\ue372\ue373\ue374\ue375\ue376\ue377\ue378\ue379\ue37a\ue37b\ue37c\ue37d\ue37e\ue37f\ue380\ue381\ue382\ue383\ue384\ue385\ue386\ue387\ue388\ue389\ue38a\ue38b\ue38c\ue38d\ue38e\ue38f\ue390\ue391\ue392\ue393\ue394\ue395\ue396\ue397\ue398\ue399\ue39a\ue39b\ue39c\ue39d\ue39e\ue39f\ue3a0\ue3a1\ue3a2\ue3a3\ue3a4\ue3a5\ue3a6\ue3a7\ue3a8\ue3a9\ue3aa\ue3ab\ue3ac\ue3ad\ue3ae\ue3af\ue3b0\ue3b1\ue3b2\ue3b3\ue3b4\ue3b5\ue3b6\ue3b7\ue3b8\ue3b9\ue3ba\ue3bb\ue3bc\ue3bd\ue3be\ue3bf\ue3c0\ue3c1\ue3c2\ue3c3\ue3c4\ue3c5\ue3c6\ue3c7\ue3c8\ue3c9\ue3ca\ue3cb\ue3cc\ue3cd\ue3ce\ue3cf\ue3d0\ue3d1\ue3d2\ue3d3\ue3d4\ue3d5\ue3d6\ue3d7\ue3d8\ue3d9\ue3da\ue3db\ue3dc\ue3dd\ue3de\ue3df\ue3e0\ue3e1\ue3e2\ue3e3\ue3e4\ue3e5\ue3e6\ue3e7\ue3e8\ue3e9\ue3ea\ue3eb\ue3ec\ue3ed\ue3ee\ue3ef\ue3f0\ue3f1\ue3f2\ue3f3\ue3f4\ue3f5\ue3f6\ue3f7\ue3f8\ue3f9\ue3fa\ue3fb\ue3fc\ue3fd\ue3fe\ue3ff\ue400\ue401\ue402\ue403\ue404\ue405\ue406\ue407\ue408\ue409\ue40a\ue40b\ue40c\ue40d\ue40e\ue40f\ue410\ue411\ue412\ue413\ue414\ue415\ue416\ue417\ue418\ue419\ue41a\ue41b\ue41c\ue41d\ue41e\ue41f\ue420\ue421\ue422\ue423\ue424\ue425\ue426\ue427\ue428\ue429\ue42a\ue42b\ue42c\ue42d\ue42e\ue42f\ue430\ue431\ue432\ue433\ue434\ue435\ue436\ue437\ue438\ue439\ue43a\ue43b\ue43c\ue43d\ue43e\ue43f\ue440\ue441\ue442\ue443\ue444\ue445\ue446\ue447\ue448\ue449\ue44a\ue44b\ue44c\ue44d\ue44e\ue44f\ue450\ue451\ue452\ue453\ue454\ue455\ue456\ue457\ue458\ue459\ue45a\ue45b\ue45c\ue45d\ue45e\ue45f\ue460\ue461\ue462\ue463\ue464\ue465\ue466\ue467\ue468\ue469\ue46a\ue46b\ue46c\ue46d\ue46e\ue46f\ue470\ue471\ue472\ue473\ue474\ue475\ue476\ue477\ue478\ue479\ue47a\ue47b\ue47c\ue47d\ue47e\ue47f\ue480\ue481\ue482\ue483\ue484\ue485\ue486\ue487\ue488\ue489\ue48a\ue48b\ue48c\ue48d\ue48e\ue48f\ue490\ue491\ue492\ue493\ue494\ue495\ue496\ue497\ue498\ue499\ue49a\ue49b\ue49c\ue49d\ue49e\ue49f\ue4a0\ue4a1\ue4a2\ue4a3\ue4a4\ue4a5\ue4a6\ue4a7\ue4a8\ue4a9\ue4aa\ue4ab\ue4ac\ue4ad\ue4ae\ue4af\ue4b0\ue4b1\ue4b2\ue4b3\ue4b4\ue4b5\ue4b6\ue4b7\ue4b8\ue4b9\ue4ba\ue4bb\ue4bc\ue4bd\ue4be\ue4bf\ue4c0\ue4c1\ue4c2\ue4c3\ue4c4\ue4c5\ue4c6\ue4c7\ue4c8\ue4c9\ue4ca\ue4cb\ue4cc\ue4cd\ue4ce\ue4cf\ue4d0\ue4d1\ue4d2\ue4d3\ue4d4\ue4d5\ue4d6\ue4d7\ue4d8\ue4d9\ue4da\ue4db\ue4dc\ue4dd\ue4de\ue4df\ue4e0\ue4e1\ue4e2\ue4e3\ue4e4\ue4e5\ue4e6\ue4e7\ue4e8\ue4e9\ue4ea\ue4eb\ue4ec\ue4ed\ue4ee\ue4ef\ue4f0\ue4f1\ue4f2\ue4f3\ue4f4\ue4f5\ue4f6\ue4f7\ue4f8\ue4f9\ue4fa\ue4fb\ue4fc\ue4fd\ue4fe\ue4ff\ue500\ue501\ue502\ue503\ue504\ue505\ue506\ue507\ue508\ue509\ue50a\ue50b\ue50c\ue50d\ue50e\ue50f\ue510\ue511\ue512\ue513\ue514\ue515\ue516\ue517\ue518\ue519\ue51a\ue51b\ue51c\ue51d\ue51e\ue51f\ue520\ue521\ue522\ue523\ue524\ue525\ue526\ue527\ue528\ue529\ue52a\ue52b\ue52c\ue52d\ue52e\ue52f\ue530\ue531\ue532\ue533\ue534\ue535\ue536\ue537\ue538\ue539\ue53a\ue53b\ue53c\ue53d\ue53e\ue53f\ue540\ue541\ue542\ue543\ue544\ue545\ue546\ue547\ue548\ue549\ue54a\ue54b\ue54c\ue54d\ue54e\ue54f\ue550\ue551\ue552\ue553\ue554\ue555\ue556\ue557\ue558\ue559\ue55a\ue55b\ue55c\ue55d\ue55e\ue55f\ue560\ue561\ue562\ue563\ue564\ue565\ue566\ue567\ue568\ue569\ue56a\ue56b\ue56c\ue56d\ue56e\ue56f\ue570\ue571\ue572\ue573\ue574\ue575\ue576\ue577\ue578\ue579\ue57a\ue57b\ue57c\ue57d\ue57e\ue57f\ue580\ue581\ue582\ue583\ue584\ue585\ue586\ue587\ue588\ue589\ue58a\ue58b\ue58c\ue58d\ue58e\ue58f\ue590\ue591\ue592\ue593\ue594\ue595\ue596\ue597\ue598\ue599\ue59a\ue59b\ue59c\ue59d\ue59e\ue59f\ue5a0\ue5a1\ue5a2\ue5a3\ue5a4\ue5a5\ue5a6\ue5a7\ue5a8\ue5a9\ue5aa\ue5ab\ue5ac\ue5ad\ue5ae\ue5af\ue5b0\ue5b1\ue5b2\ue5b3\ue5b4\ue5b5\ue5b6\ue5b7\ue5b8\ue5b9\ue5ba\ue5bb\ue5bc\ue5bd\ue5be\ue5bf\ue5c0\ue5c1\ue5c2\ue5c3\ue5c4\ue5c5\ue5c6\ue5c7\ue5c8\ue5c9\ue5ca\ue5cb\ue5cc\ue5cd\ue5ce\ue5cf\ue5d0\ue5d1\ue5d2\ue5d3\ue5d4\ue5d5\ue5d6\ue5d7\ue5d8\ue5d9\ue5da\ue5db\ue5dc\ue5dd\ue5de\ue5df\ue5e0\ue5e1\ue5e2\ue5e3\ue5e4\ue5e5\ue5e6\ue5e7\ue5e8\ue5e9\ue5ea\ue5eb\ue5ec\ue5ed\ue5ee\ue5ef\ue5f0\ue5f1\ue5f2\ue5f3\ue5f4\ue5f5\ue5f6\ue5f7\ue5f8\ue5f9\ue5fa\ue5fb\ue5fc\ue5fd\ue5fe\ue5ff\ue600\ue601\ue602\ue603\ue604\ue605\ue606\ue607\ue608\ue609\ue60a\ue60b\ue60c\ue60d\ue60e\ue60f\ue610\ue611\ue612\ue613\ue614\ue615\ue616\ue617\ue618\ue619\ue61a\ue61b\ue61c\ue61d\ue61e\ue61f\ue620\ue621\ue622\ue623\ue624\ue625\ue626\ue627\ue628\ue629\ue62a\ue62b\ue62c\ue62d\ue62e\ue62f\ue630\ue631\ue632\ue633\ue634\ue635\ue636\ue637\ue638\ue639\ue63a\ue63b\ue63c\ue63d\ue63e\ue63f\ue640\ue641\ue642\ue643\ue644\ue645\ue646\ue647\ue648\ue649\ue64a\ue64b\ue64c\ue64d\ue64e\ue64f\ue650\ue651\ue652\ue653\ue654\ue655\ue656\ue657\ue658\ue659\ue65a\ue65b\ue65c\ue65d\ue65e\ue65f\ue660\ue661\ue662\ue663\ue664\ue665\ue666\ue667\ue668\ue669\ue66a\ue66b\ue66c\ue66d\ue66e\ue66f\ue670\ue671\ue672\ue673\ue674\ue675\ue676\ue677\ue678\ue679\ue67a\ue67b\ue67c\ue67d\ue67e\ue67f\ue680\ue681\ue682\ue683\ue684\ue685\ue686\ue687\ue688\ue689\ue68a\ue68b\ue68c\ue68d\ue68e\ue68f\ue690\ue691\ue692\ue693\ue694\ue695\ue696\ue697\ue698\ue699\ue69a\ue69b\ue69c\ue69d\ue69e\ue69f\ue6a0\ue6a1\ue6a2\ue6a3\ue6a4\ue6a5\ue6a6\ue6a7\ue6a8\ue6a9\ue6aa\ue6ab\ue6ac\ue6ad\ue6ae\ue6af\ue6b0\ue6b1\ue6b2\ue6b3\ue6b4\ue6b5\ue6b6\ue6b7\ue6b8\ue6b9\ue6ba\ue6bb\ue6bc\ue6bd\ue6be\ue6bf\ue6c0\ue6c1\ue6c2\ue6c3\ue6c4\ue6c5\ue6c6\ue6c7\ue6c8\ue6c9\ue6ca\ue6cb\ue6cc\ue6cd\ue6ce\ue6cf\ue6d0\ue6d1\ue6d2\ue6d3\ue6d4\ue6d5\ue6d6\ue6d7\ue6d8\ue6d9\ue6da\ue6db\ue6dc\ue6dd\ue6de\ue6df\ue6e0\ue6e1\ue6e2\ue6e3\ue6e4\ue6e5\ue6e6\ue6e7\ue6e8\ue6e9\ue6ea\ue6eb\ue6ec\ue6ed\ue6ee\ue6ef\ue6f0\ue6f1\ue6f2\ue6f3\ue6f4\ue6f5\ue6f6\ue6f7\ue6f8\ue6f9\ue6fa\ue6fb\ue6fc\ue6fd\ue6fe\ue6ff\ue700\ue701\ue702\ue703\ue704\ue705\ue706\ue707\ue708\ue709\ue70a\ue70b\ue70c\ue70d\ue70e\ue70f\ue710\ue711\ue712\ue713\ue714\ue715\ue716\ue717\ue718\ue719\ue71a\ue71b\ue71c\ue71d\ue71e\ue71f\ue720\ue721\ue722\ue723\ue724\ue725\ue726\ue727\ue728\ue729\ue72a\ue72b\ue72c\ue72d\ue72e\ue72f\ue730\ue731\ue732\ue733\ue734\ue735\ue736\ue737\ue738\ue739\ue73a\ue73b\ue73c\ue73d\ue73e\ue73f\ue740\ue741\ue742\ue743\ue744\ue745\ue746\ue747\ue748\ue749\ue74a\ue74b\ue74c\ue74d\ue74e\ue74f\ue750\ue751\ue752\ue753\ue754\ue755\ue756\ue757\ue758\ue759\ue75a\ue75b\ue75c\ue75d\ue75e\ue75f\ue760\ue761\ue762\ue763\ue764\ue765\ue766\ue767\ue768\ue769\ue76a\ue76b\ue76c\ue76d\ue76e\ue76f\ue770\ue771\ue772\ue773\ue774\ue775\ue776\ue777\ue778\ue779\ue77a\ue77b\ue77c\ue77d\ue77e\ue77f\ue780\ue781\ue782\ue783\ue784\ue785\ue786\ue787\ue788\ue789\ue78a\ue78b\ue78c\ue78d\ue78e\ue78f\ue790\ue791\ue792\ue793\ue794\ue795\ue796\ue797\ue798\ue799\ue79a\ue79b\ue79c\ue79d\ue79e\ue79f\ue7a0\ue7a1\ue7a2\ue7a3\ue7a4\ue7a5\ue7a6\ue7a7\ue7a8\ue7a9\ue7aa\ue7ab\ue7ac\ue7ad\ue7ae\ue7af\ue7b0\ue7b1\ue7b2\ue7b3\ue7b4\ue7b5\ue7b6\ue7b7\ue7b8\ue7b9\ue7ba\ue7bb\ue7bc\ue7bd\ue7be\ue7bf\ue7c0\ue7c1\ue7c2\ue7c3\ue7c4\ue7c5\ue7c6\ue7c7\ue7c8\ue7c9\ue7ca\ue7cb\ue7cc\ue7cd\ue7ce\ue7cf\ue7d0\ue7d1\ue7d2\ue7d3\ue7d4\ue7d5\ue7d6\ue7d7\ue7d8\ue7d9\ue7da\ue7db\ue7dc\ue7dd\ue7de\ue7df\ue7e0\ue7e1\ue7e2\ue7e3\ue7e4\ue7e5\ue7e6\ue7e7\ue7e8\ue7e9\ue7ea\ue7eb\ue7ec\ue7ed\ue7ee\ue7ef\ue7f0\ue7f1\ue7f2\ue7f3\ue7f4\ue7f5\ue7f6\ue7f7\ue7f8\ue7f9\ue7fa\ue7fb\ue7fc\ue7fd\ue7fe\ue7ff\ue800\ue801\ue802\ue803\ue804\ue805\ue806\ue807\ue808\ue809\ue80a\ue80b\ue80c\ue80d\ue80e\ue80f\ue810\ue811\ue812\ue813\ue814\ue815\ue816\ue817\ue818\ue819\ue81a\ue81b\ue81c\ue81d\ue81e\ue81f\ue820\ue821\ue822\ue823\ue824\ue825\ue826\ue827\ue828\ue829\ue82a\ue82b\ue82c\ue82d\ue82e\ue82f\ue830\ue831\ue832\ue833\ue834\ue835\ue836\ue837\ue838\ue839\ue83a\ue83b\ue83c\ue83d\ue83e\ue83f\ue840\ue841\ue842\ue843\ue844\ue845\ue846\ue847\ue848\ue849\ue84a\ue84b\ue84c\ue84d\ue84e\ue84f\ue850\ue851\ue852\ue853\ue854\ue855\ue856\ue857\ue858\ue859\ue85a\ue85b\ue85c\ue85d\ue85e\ue85f\ue860\ue861\ue862\ue863\ue864\ue865\ue866\ue867\ue868\ue869\ue86a\ue86b\ue86c\ue86d\ue86e\ue86f\ue870\ue871\ue872\ue873\ue874\ue875\ue876\ue877\ue878\ue879\ue87a\ue87b\ue87c\ue87d\ue87e\ue87f\ue880\ue881\ue882\ue883\ue884\ue885\ue886\ue887\ue888\ue889\ue88a\ue88b\ue88c\ue88d\ue88e\ue88f\ue890\ue891\ue892\ue893\ue894\ue895\ue896\ue897\ue898\ue899\ue89a\ue89b\ue89c\ue89d\ue89e\ue89f\ue8a0\ue8a1\ue8a2\ue8a3\ue8a4\ue8a5\ue8a6\ue8a7\ue8a8\ue8a9\ue8aa\ue8ab\ue8ac\ue8ad\ue8ae\ue8af\ue8b0\ue8b1\ue8b2\ue8b3\ue8b4\ue8b5\ue8b6\ue8b7\ue8b8\ue8b9\ue8ba\ue8bb\ue8bc\ue8bd\ue8be\ue8bf\ue8c0\ue8c1\ue8c2\ue8c3\ue8c4\ue8c5\ue8c6\ue8c7\ue8c8\ue8c9\ue8ca\ue8cb\ue8cc\ue8cd\ue8ce\ue8cf\ue8d0\ue8d1\ue8d2\ue8d3\ue8d4\ue8d5\ue8d6\ue8d7\ue8d8\ue8d9\ue8da\ue8db\ue8dc\ue8dd\ue8de\ue8df\ue8e0\ue8e1\ue8e2\ue8e3\ue8e4\ue8e5\ue8e6\ue8e7\ue8e8\ue8e9\ue8ea\ue8eb\ue8ec\ue8ed\ue8ee\ue8ef\ue8f0\ue8f1\ue8f2\ue8f3\ue8f4\ue8f5\ue8f6\ue8f7\ue8f8\ue8f9\ue8fa\ue8fb\ue8fc\ue8fd\ue8fe\ue8ff\ue900\ue901\ue902\ue903\ue904\ue905\ue906\ue907\ue908\ue909\ue90a\ue90b\ue90c\ue90d\ue90e\ue90f\ue910\ue911\ue912\ue913\ue914\ue915\ue916\ue917\ue918\ue919\ue91a\ue91b\ue91c\ue91d\ue91e\ue91f\ue920\ue921\ue922\ue923\ue924\ue925\ue926\ue927\ue928\ue929\ue92a\ue92b\ue92c\ue92d\ue92e\ue92f\ue930\ue931\ue932\ue933\ue934\ue935\ue936\ue937\ue938\ue939\ue93a\ue93b\ue93c\ue93d\ue93e\ue93f\ue940\ue941\ue942\ue943\ue944\ue945\ue946\ue947\ue948\ue949\ue94a\ue94b\ue94c\ue94d\ue94e\ue94f\ue950\ue951\ue952\ue953\ue954\ue955\ue956\ue957\ue958\ue959\ue95a\ue95b\ue95c\ue95d\ue95e\ue95f\ue960\ue961\ue962\ue963\ue964\ue965\ue966\ue967\ue968\ue969\ue96a\ue96b\ue96c\ue96d\ue96e\ue96f\ue970\ue971\ue972\ue973\ue974\ue975\ue976\ue977\ue978\ue979\ue97a\ue97b\ue97c\ue97d\ue97e\ue97f\ue980\ue981\ue982\ue983\ue984\ue985\ue986\ue987\ue988\ue989\ue98a\ue98b\ue98c\ue98d\ue98e\ue98f\ue990\ue991\ue992\ue993\ue994\ue995\ue996\ue997\ue998\ue999\ue99a\ue99b\ue99c\ue99d\ue99e\ue99f\ue9a0\ue9a1\ue9a2\ue9a3\ue9a4\ue9a5\ue9a6\ue9a7\ue9a8\ue9a9\ue9aa\ue9ab\ue9ac\ue9ad\ue9ae\ue9af\ue9b0\ue9b1\ue9b2\ue9b3\ue9b4\ue9b5\ue9b6\ue9b7\ue9b8\ue9b9\ue9ba\ue9bb\ue9bc\ue9bd\ue9be\ue9bf\ue9c0\ue9c1\ue9c2\ue9c3\ue9c4\ue9c5\ue9c6\ue9c7\ue9c8\ue9c9\ue9ca\ue9cb\ue9cc\ue9cd\ue9ce\ue9cf\ue9d0\ue9d1\ue9d2\ue9d3\ue9d4\ue9d5\ue9d6\ue9d7\ue9d8\ue9d9\ue9da\ue9db\ue9dc\ue9dd\ue9de\ue9df\ue9e0\ue9e1\ue9e2\ue9e3\ue9e4\ue9e5\ue9e6\ue9e7\ue9e8\ue9e9\ue9ea\ue9eb\ue9ec\ue9ed\ue9ee\ue9ef\ue9f0\ue9f1\ue9f2\ue9f3\ue9f4\ue9f5\ue9f6\ue9f7\ue9f8\ue9f9\ue9fa\ue9fb\ue9fc\ue9fd\ue9fe\ue9ff\uea00\uea01\uea02\uea03\uea04\uea05\uea06\uea07\uea08\uea09\uea0a\uea0b\uea0c\uea0d\uea0e\uea0f\uea10\uea11\uea12\uea13\uea14\uea15\uea16\uea17\uea18\uea19\uea1a\uea1b\uea1c\uea1d\uea1e\uea1f\uea20\uea21\uea22\uea23\uea24\uea25\uea26\uea27\uea28\uea29\uea2a\uea2b\uea2c\uea2d\uea2e\uea2f\uea30\uea31\uea32\uea33\uea34\uea35\uea36\uea37\uea38\uea39\uea3a\uea3b\uea3c\uea3d\uea3e\uea3f\uea40\uea41\uea42\uea43\uea44\uea45\uea46\uea47\uea48\uea49\uea4a\uea4b\uea4c\uea4d\uea4e\uea4f\uea50\uea51\uea52\uea53\uea54\uea55\uea56\uea57\uea58\uea59\uea5a\uea5b\uea5c\uea5d\uea5e\uea5f\uea60\uea61\uea62\uea63\uea64\uea65\uea66\uea67\uea68\uea69\uea6a\uea6b\uea6c\uea6d\uea6e\uea6f\uea70\uea71\uea72\uea73\uea74\uea75\uea76\uea77\uea78\uea79\uea7a\uea7b\uea7c\uea7d\uea7e\uea7f\uea80\uea81\uea82\uea83\uea84\uea85\uea86\uea87\uea88\uea89\uea8a\uea8b\uea8c\uea8d\uea8e\uea8f\uea90\uea91\uea92\uea93\uea94\uea95\uea96\uea97\uea98\uea99\uea9a\uea9b\uea9c\uea9d\uea9e\uea9f\ueaa0\ueaa1\ueaa2\ueaa3\ueaa4\ueaa5\ueaa6\ueaa7\ueaa8\ueaa9\ueaaa\ueaab\ueaac\ueaad\ueaae\ueaaf\ueab0\ueab1\ueab2\ueab3\ueab4\ueab5\ueab6\ueab7\ueab8\ueab9\ueaba\ueabb\ueabc\ueabd\ueabe\ueabf\ueac0\ueac1\ueac2\ueac3\ueac4\ueac5\ueac6\ueac7\ueac8\ueac9\ueaca\ueacb\ueacc\ueacd\ueace\ueacf\uead0\uead1\uead2\uead3\uead4\uead5\uead6\uead7\uead8\uead9\ueada\ueadb\ueadc\ueadd\ueade\ueadf\ueae0\ueae1\ueae2\ueae3\ueae4\ueae5\ueae6\ueae7\ueae8\ueae9\ueaea\ueaeb\ueaec\ueaed\ueaee\ueaef\ueaf0\ueaf1\ueaf2\ueaf3\ueaf4\ueaf5\ueaf6\ueaf7\ueaf8\ueaf9\ueafa\ueafb\ueafc\ueafd\ueafe\ueaff\ueb00\ueb01\ueb02\ueb03\ueb04\ueb05\ueb06\ueb07\ueb08\ueb09\ueb0a\ueb0b\ueb0c\ueb0d\ueb0e\ueb0f\ueb10\ueb11\ueb12\ueb13\ueb14\ueb15\ueb16\ueb17\ueb18\ueb19\ueb1a\ueb1b\ueb1c\ueb1d\ueb1e\ueb1f\ueb20\ueb21\ueb22\ueb23\ueb24\ueb25\ueb26\ueb27\ueb28\ueb29\ueb2a\ueb2b\ueb2c\ueb2d\ueb2e\ueb2f\ueb30\ueb31\ueb32\ueb33\ueb34\ueb35\ueb36\ueb37\ueb38\ueb39\ueb3a\ueb3b\ueb3c\ueb3d\ueb3e\ueb3f\ueb40\ueb41\ueb42\ueb43\ueb44\ueb45\ueb46\ueb47\ueb48\ueb49\ueb4a\ueb4b\ueb4c\ueb4d\ueb4e\ueb4f\ueb50\ueb51\ueb52\ueb53\ueb54\ueb55\ueb56\ueb57\ueb58\ueb59\ueb5a\ueb5b\ueb5c\ueb5d\ueb5e\ueb5f\ueb60\ueb61\ueb62\ueb63\ueb64\ueb65\ueb66\ueb67\ueb68\ueb69\ueb6a\ueb6b\ueb6c\ueb6d\ueb6e\ueb6f\ueb70\ueb71\ueb72\ueb73\ueb74\ueb75\ueb76\ueb77\ueb78\ueb79\ueb7a\ueb7b\ueb7c\ueb7d\ueb7e\ueb7f\ueb80\ueb81\ueb82\ueb83\ueb84\ueb85\ueb86\ueb87\ueb88\ueb89\ueb8a\ueb8b\ueb8c\ueb8d\ueb8e\ueb8f\ueb90\ueb91\ueb92\ueb93\ueb94\ueb95\ueb96\ueb97\ueb98\ueb99\ueb9a\ueb9b\ueb9c\ueb9d\ueb9e\ueb9f\ueba0\ueba1\ueba2\ueba3\ueba4\ueba5\ueba6\ueba7\ueba8\ueba9\uebaa\uebab\uebac\uebad\uebae\uebaf\uebb0\uebb1\uebb2\uebb3\uebb4\uebb5\uebb6\uebb7\uebb8\uebb9\uebba\uebbb\uebbc\uebbd\uebbe\uebbf\uebc0\uebc1\uebc2\uebc3\uebc4\uebc5\uebc6\uebc7\uebc8\uebc9\uebca\uebcb\uebcc\uebcd\uebce\uebcf\uebd0\uebd1\uebd2\uebd3\uebd4\uebd5\uebd6\uebd7\uebd8\uebd9\uebda\uebdb\uebdc\uebdd\uebde\uebdf\uebe0\uebe1\uebe2\uebe3\uebe4\uebe5\uebe6\uebe7\uebe8\uebe9\uebea\uebeb\uebec\uebed\uebee\uebef\uebf0\uebf1\uebf2\uebf3\uebf4\uebf5\uebf6\uebf7\uebf8\uebf9\uebfa\uebfb\uebfc\uebfd\uebfe\uebff\uec00\uec01\uec02\uec03\uec04\uec05\uec06\uec07\uec08\uec09\uec0a\uec0b\uec0c\uec0d\uec0e\uec0f\uec10\uec11\uec12\uec13\uec14\uec15\uec16\uec17\uec18\uec19\uec1a\uec1b\uec1c\uec1d\uec1e\uec1f\uec20\uec21\uec22\uec23\uec24\uec25\uec26\uec27\uec28\uec29\uec2a\uec2b\uec2c\uec2d\uec2e\uec2f\uec30\uec31\uec32\uec33\uec34\uec35\uec36\uec37\uec38\uec39\uec3a\uec3b\uec3c\uec3d\uec3e\uec3f\uec40\uec41\uec42\uec43\uec44\uec45\uec46\uec47\uec48\uec49\uec4a\uec4b\uec4c\uec4d\uec4e\uec4f\uec50\uec51\uec52\uec53\uec54\uec55\uec56\uec57\uec58\uec59\uec5a\uec5b\uec5c\uec5d\uec5e\uec5f\uec60\uec61\uec62\uec63\uec64\uec65\uec66\uec67\uec68\uec69\uec6a\uec6b\uec6c\uec6d\uec6e\uec6f\uec70\uec71\uec72\uec73\uec74\uec75\uec76\uec77\uec78\uec79\uec7a\uec7b\uec7c\uec7d\uec7e\uec7f\uec80\uec81\uec82\uec83\uec84\uec85\uec86\uec87\uec88\uec89\uec8a\uec8b\uec8c\uec8d\uec8e\uec8f\uec90\uec91\uec92\uec93\uec94\uec95\uec96\uec97\uec98\uec99\uec9a\uec9b\uec9c\uec9d\uec9e\uec9f\ueca0\ueca1\ueca2\ueca3\ueca4\ueca5\ueca6\ueca7\ueca8\ueca9\uecaa\uecab\uecac\uecad\uecae\uecaf\uecb0\uecb1\uecb2\uecb3\uecb4\uecb5\uecb6\uecb7\uecb8\uecb9\uecba\uecbb\uecbc\uecbd\uecbe\uecbf\uecc0\uecc1\uecc2\uecc3\uecc4\uecc5\uecc6\uecc7\uecc8\uecc9\uecca\ueccb\ueccc\ueccd\uecce\ueccf\uecd0\uecd1\uecd2\uecd3\uecd4\uecd5\uecd6\uecd7\uecd8\uecd9\uecda\uecdb\uecdc\uecdd\uecde\uecdf\uece0\uece1\uece2\uece3\uece4\uece5\uece6\uece7\uece8\uece9\uecea\ueceb\uecec\ueced\uecee\uecef\uecf0\uecf1\uecf2\uecf3\uecf4\uecf5\uecf6\uecf7\uecf8\uecf9\uecfa\uecfb\uecfc\uecfd\uecfe\uecff\ued00\ued01\ued02\ued03\ued04\ued05\ued06\ued07\ued08\ued09\ued0a\ued0b\ued0c\ued0d\ued0e\ued0f\ued10\ued11\ued12\ued13\ued14\ued15\ued16\ued17\ued18\ued19\ued1a\ued1b\ued1c\ued1d\ued1e\ued1f\ued20\ued21\ued22\ued23\ued24\ued25\ued26\ued27\ued28\ued29\ued2a\ued2b\ued2c\ued2d\ued2e\ued2f\ued30\ued31\ued32\ued33\ued34\ued35\ued36\ued37\ued38\ued39\ued3a\ued3b\ued3c\ued3d\ued3e\ued3f\ued40\ued41\ued42\ued43\ued44\ued45\ued46\ued47\ued48\ued49\ued4a\ued4b\ued4c\ued4d\ued4e\ued4f\ued50\ued51\ued52\ued53\ued54\ued55\ued56\ued57\ued58\ued59\ued5a\ued5b\ued5c\ued5d\ued5e\ued5f\ued60\ued61\ued62\ued63\ued64\ued65\ued66\ued67\ued68\ued69\ued6a\ued6b\ued6c\ued6d\ued6e\ued6f\ued70\ued71\ued72\ued73\ued74\ued75\ued76\ued77\ued78\ued79\ued7a\ued7b\ued7c\ued7d\ued7e\ued7f\ued80\ued81\ued82\ued83\ued84\ued85\ued86\ued87\ued88\ued89\ued8a\ued8b\ued8c\ued8d\ued8e\ued8f\ued90\ued91\ued92\ued93\ued94\ued95\ued96\ued97\ued98\ued99\ued9a\ued9b\ued9c\ued9d\ued9e\ued9f\ueda0\ueda1\ueda2\ueda3\ueda4\ueda5\ueda6\ueda7\ueda8\ueda9\uedaa\uedab\uedac\uedad\uedae\uedaf\uedb0\uedb1\uedb2\uedb3\uedb4\uedb5\uedb6\uedb7\uedb8\uedb9\uedba\uedbb\uedbc\uedbd\uedbe\uedbf\uedc0\uedc1\uedc2\uedc3\uedc4\uedc5\uedc6\uedc7\uedc8\uedc9\uedca\uedcb\uedcc\uedcd\uedce\uedcf\uedd0\uedd1\uedd2\uedd3\uedd4\uedd5\uedd6\uedd7\uedd8\uedd9\uedda\ueddb\ueddc\ueddd\uedde\ueddf\uede0\uede1\uede2\uede3\uede4\uede5\uede6\uede7\uede8\uede9\uedea\uedeb\uedec\ueded\uedee\uedef\uedf0\uedf1\uedf2\uedf3\uedf4\uedf5\uedf6\uedf7\uedf8\uedf9\uedfa\uedfb\uedfc\uedfd\uedfe\uedff\uee00\uee01\uee02\uee03\uee04\uee05\uee06\uee07\uee08\uee09\uee0a\uee0b\uee0c\uee0d\uee0e\uee0f\uee10\uee11\uee12\uee13\uee14\uee15\uee16\uee17\uee18\uee19\uee1a\uee1b\uee1c\uee1d\uee1e\uee1f\uee20\uee21\uee22\uee23\uee24\uee25\uee26\uee27\uee28\uee29\uee2a\uee2b\uee2c\uee2d\uee2e\uee2f\uee30\uee31\uee32\uee33\uee34\uee35\uee36\uee37\uee38\uee39\uee3a\uee3b\uee3c\uee3d\uee3e\uee3f\uee40\uee41\uee42\uee43\uee44\uee45\uee46\uee47\uee48\uee49\uee4a\uee4b\uee4c\uee4d\uee4e\uee4f\uee50\uee51\uee52\uee53\uee54\uee55\uee56\uee57\uee58\uee59\uee5a\uee5b\uee5c\uee5d\uee5e\uee5f\uee60\uee61\uee62\uee63\uee64\uee65\uee66\uee67\uee68\uee69\uee6a\uee6b\uee6c\uee6d\uee6e\uee6f\uee70\uee71\uee72\uee73\uee74\uee75\uee76\uee77\uee78\uee79\uee7a\uee7b\uee7c\uee7d\uee7e\uee7f\uee80\uee81\uee82\uee83\uee84\uee85\uee86\uee87\uee88\uee89\uee8a\uee8b\uee8c\uee8d\uee8e\uee8f\uee90\uee91\uee92\uee93\uee94\uee95\uee96\uee97\uee98\uee99\uee9a\uee9b\uee9c\uee9d\uee9e\uee9f\ueea0\ueea1\ueea2\ueea3\ueea4\ueea5\ueea6\ueea7\ueea8\ueea9\ueeaa\ueeab\ueeac\ueead\ueeae\ueeaf\ueeb0\ueeb1\ueeb2\ueeb3\ueeb4\ueeb5\ueeb6\ueeb7\ueeb8\ueeb9\ueeba\ueebb\ueebc\ueebd\ueebe\ueebf\ueec0\ueec1\ueec2\ueec3\ueec4\ueec5\ueec6\ueec7\ueec8\ueec9\ueeca\ueecb\ueecc\ueecd\ueece\ueecf\ueed0\ueed1\ueed2\ueed3\ueed4\ueed5\ueed6\ueed7\ueed8\ueed9\ueeda\ueedb\ueedc\ueedd\ueede\ueedf\ueee0\ueee1\ueee2\ueee3\ueee4\ueee5\ueee6\ueee7\ueee8\ueee9\ueeea\ueeeb\ueeec\ueeed\ueeee\ueeef\ueef0\ueef1\ueef2\ueef3\ueef4\ueef5\ueef6\ueef7\ueef8\ueef9\ueefa\ueefb\ueefc\ueefd\ueefe\ueeff\uef00\uef01\uef02\uef03\uef04\uef05\uef06\uef07\uef08\uef09\uef0a\uef0b\uef0c\uef0d\uef0e\uef0f\uef10\uef11\uef12\uef13\uef14\uef15\uef16\uef17\uef18\uef19\uef1a\uef1b\uef1c\uef1d\uef1e\uef1f\uef20\uef21\uef22\uef23\uef24\uef25\uef26\uef27\uef28\uef29\uef2a\uef2b\uef2c\uef2d\uef2e\uef2f\uef30\uef31\uef32\uef33\uef34\uef35\uef36\uef37\uef38\uef39\uef3a\uef3b\uef3c\uef3d\uef3e\uef3f\uef40\uef41\uef42\uef43\uef44\uef45\uef46\uef47\uef48\uef49\uef4a\uef4b\uef4c\uef4d\uef4e\uef4f\uef50\uef51\uef52\uef53\uef54\uef55\uef56\uef57\uef58\uef59\uef5a\uef5b\uef5c\uef5d\uef5e\uef5f\uef60\uef61\uef62\uef63\uef64\uef65\uef66\uef67\uef68\uef69\uef6a\uef6b\uef6c\uef6d\uef6e\uef6f\uef70\uef71\uef72\uef73\uef74\uef75\uef76\uef77\uef78\uef79\uef7a\uef7b\uef7c\uef7d\uef7e\uef7f\uef80\uef81\uef82\uef83\uef84\uef85\uef86\uef87\uef88\uef89\uef8a\uef8b\uef8c\uef8d\uef8e\uef8f\uef90\uef91\uef92\uef93\uef94\uef95\uef96\uef97\uef98\uef99\uef9a\uef9b\uef9c\uef9d\uef9e\uef9f\uefa0\uefa1\uefa2\uefa3\uefa4\uefa5\uefa6\uefa7\uefa8\uefa9\uefaa\uefab\uefac\uefad\uefae\uefaf\uefb0\uefb1\uefb2\uefb3\uefb4\uefb5\uefb6\uefb7\uefb8\uefb9\uefba\uefbb\uefbc\uefbd\uefbe\uefbf\uefc0\uefc1\uefc2\uefc3\uefc4\uefc5\uefc6\uefc7\uefc8\uefc9\uefca\uefcb\uefcc\uefcd\uefce\uefcf\uefd0\uefd1\uefd2\uefd3\uefd4\uefd5\uefd6\uefd7\uefd8\uefd9\uefda\uefdb\uefdc\uefdd\uefde\uefdf\uefe0\uefe1\uefe2\uefe3\uefe4\uefe5\uefe6\uefe7\uefe8\uefe9\uefea\uefeb\uefec\uefed\uefee\uefef\ueff0\ueff1\ueff2\ueff3\ueff4\ueff5\ueff6\ueff7\ueff8\ueff9\ueffa\ueffb\ueffc\ueffd\ueffe\uefff\uf000\uf001\uf002\uf003\uf004\uf005\uf006\uf007\uf008\uf009\uf00a\uf00b\uf00c\uf00d\uf00e\uf00f\uf010\uf011\uf012\uf013\uf014\uf015\uf016\uf017\uf018\uf019\uf01a\uf01b\uf01c\uf01d\uf01e\uf01f\uf020\uf021\uf022\uf023\uf024\uf025\uf026\uf027\uf028\uf029\uf02a\uf02b\uf02c\uf02d\uf02e\uf02f\uf030\uf031\uf032\uf033\uf034\uf035\uf036\uf037\uf038\uf039\uf03a\uf03b\uf03c\uf03d\uf03e\uf03f\uf040\uf041\uf042\uf043\uf044\uf045\uf046\uf047\uf048\uf049\uf04a\uf04b\uf04c\uf04d\uf04e\uf04f\uf050\uf051\uf052\uf053\uf054\uf055\uf056\uf057\uf058\uf059\uf05a\uf05b\uf05c\uf05d\uf05e\uf05f\uf060\uf061\uf062\uf063\uf064\uf065\uf066\uf067\uf068\uf069\uf06a\uf06b\uf06c\uf06d\uf06e\uf06f\uf070\uf071\uf072\uf073\uf074\uf075\uf076\uf077\uf078\uf079\uf07a\uf07b\uf07c\uf07d\uf07e\uf07f\uf080\uf081\uf082\uf083\uf084\uf085\uf086\uf087\uf088\uf089\uf08a\uf08b\uf08c\uf08d\uf08e\uf08f\uf090\uf091\uf092\uf093\uf094\uf095\uf096\uf097\uf098\uf099\uf09a\uf09b\uf09c\uf09d\uf09e\uf09f\uf0a0\uf0a1\uf0a2\uf0a3\uf0a4\uf0a5\uf0a6\uf0a7\uf0a8\uf0a9\uf0aa\uf0ab\uf0ac\uf0ad\uf0ae\uf0af\uf0b0\uf0b1\uf0b2\uf0b3\uf0b4\uf0b5\uf0b6\uf0b7\uf0b8\uf0b9\uf0ba\uf0bb\uf0bc\uf0bd\uf0be\uf0bf\uf0c0\uf0c1\uf0c2\uf0c3\uf0c4\uf0c5\uf0c6\uf0c7\uf0c8\uf0c9\uf0ca\uf0cb\uf0cc\uf0cd\uf0ce\uf0cf\uf0d0\uf0d1\uf0d2\uf0d3\uf0d4\uf0d5\uf0d6\uf0d7\uf0d8\uf0d9\uf0da\uf0db\uf0dc\uf0dd\uf0de\uf0df\uf0e0\uf0e1\uf0e2\uf0e3\uf0e4\uf0e5\uf0e6\uf0e7\uf0e8\uf0e9\uf0ea\uf0eb\uf0ec\uf0ed\uf0ee\uf0ef\uf0f0\uf0f1\uf0f2\uf0f3\uf0f4\uf0f5\uf0f6\uf0f7\uf0f8\uf0f9\uf0fa\uf0fb\uf0fc\uf0fd\uf0fe\uf0ff\uf100\uf101\uf102\uf103\uf104\uf105\uf106\uf107\uf108\uf109\uf10a\uf10b\uf10c\uf10d\uf10e\uf10f\uf110\uf111\uf112\uf113\uf114\uf115\uf116\uf117\uf118\uf119\uf11a\uf11b\uf11c\uf11d\uf11e\uf11f\uf120\uf121\uf122\uf123\uf124\uf125\uf126\uf127\uf128\uf129\uf12a\uf12b\uf12c\uf12d\uf12e\uf12f\uf130\uf131\uf132\uf133\uf134\uf135\uf136\uf137\uf138\uf139\uf13a\uf13b\uf13c\uf13d\uf13e\uf13f\uf140\uf141\uf142\uf143\uf144\uf145\uf146\uf147\uf148\uf149\uf14a\uf14b\uf14c\uf14d\uf14e\uf14f\uf150\uf151\uf152\uf153\uf154\uf155\uf156\uf157\uf158\uf159\uf15a\uf15b\uf15c\uf15d\uf15e\uf15f\uf160\uf161\uf162\uf163\uf164\uf165\uf166\uf167\uf168\uf169\uf16a\uf16b\uf16c\uf16d\uf16e\uf16f\uf170\uf171\uf172\uf173\uf174\uf175\uf176\uf177\uf178\uf179\uf17a\uf17b\uf17c\uf17d\uf17e\uf17f\uf180\uf181\uf182\uf183\uf184\uf185\uf186\uf187\uf188\uf189\uf18a\uf18b\uf18c\uf18d\uf18e\uf18f\uf190\uf191\uf192\uf193\uf194\uf195\uf196\uf197\uf198\uf199\uf19a\uf19b\uf19c\uf19d\uf19e\uf19f\uf1a0\uf1a1\uf1a2\uf1a3\uf1a4\uf1a5\uf1a6\uf1a7\uf1a8\uf1a9\uf1aa\uf1ab\uf1ac\uf1ad\uf1ae\uf1af\uf1b0\uf1b1\uf1b2\uf1b3\uf1b4\uf1b5\uf1b6\uf1b7\uf1b8\uf1b9\uf1ba\uf1bb\uf1bc\uf1bd\uf1be\uf1bf\uf1c0\uf1c1\uf1c2\uf1c3\uf1c4\uf1c5\uf1c6\uf1c7\uf1c8\uf1c9\uf1ca\uf1cb\uf1cc\uf1cd\uf1ce\uf1cf\uf1d0\uf1d1\uf1d2\uf1d3\uf1d4\uf1d5\uf1d6\uf1d7\uf1d8\uf1d9\uf1da\uf1db\uf1dc\uf1dd\uf1de\uf1df\uf1e0\uf1e1\uf1e2\uf1e3\uf1e4\uf1e5\uf1e6\uf1e7\uf1e8\uf1e9\uf1ea\uf1eb\uf1ec\uf1ed\uf1ee\uf1ef\uf1f0\uf1f1\uf1f2\uf1f3\uf1f4\uf1f5\uf1f6\uf1f7\uf1f8\uf1f9\uf1fa\uf1fb\uf1fc\uf1fd\uf1fe\uf1ff\uf200\uf201\uf202\uf203\uf204\uf205\uf206\uf207\uf208\uf209\uf20a\uf20b\uf20c\uf20d\uf20e\uf20f\uf210\uf211\uf212\uf213\uf214\uf215\uf216\uf217\uf218\uf219\uf21a\uf21b\uf21c\uf21d\uf21e\uf21f\uf220\uf221\uf222\uf223\uf224\uf225\uf226\uf227\uf228\uf229\uf22a\uf22b\uf22c\uf22d\uf22e\uf22f\uf230\uf231\uf232\uf233\uf234\uf235\uf236\uf237\uf238\uf239\uf23a\uf23b\uf23c\uf23d\uf23e\uf23f\uf240\uf241\uf242\uf243\uf244\uf245\uf246\uf247\uf248\uf249\uf24a\uf24b\uf24c\uf24d\uf24e\uf24f\uf250\uf251\uf252\uf253\uf254\uf255\uf256\uf257\uf258\uf259\uf25a\uf25b\uf25c\uf25d\uf25e\uf25f\uf260\uf261\uf262\uf263\uf264\uf265\uf266\uf267\uf268\uf269\uf26a\uf26b\uf26c\uf26d\uf26e\uf26f\uf270\uf271\uf272\uf273\uf274\uf275\uf276\uf277\uf278\uf279\uf27a\uf27b\uf27c\uf27d\uf27e\uf27f\uf280\uf281\uf282\uf283\uf284\uf285\uf286\uf287\uf288\uf289\uf28a\uf28b\uf28c\uf28d\uf28e\uf28f\uf290\uf291\uf292\uf293\uf294\uf295\uf296\uf297\uf298\uf299\uf29a\uf29b\uf29c\uf29d\uf29e\uf29f\uf2a0\uf2a1\uf2a2\uf2a3\uf2a4\uf2a5\uf2a6\uf2a7\uf2a8\uf2a9\uf2aa\uf2ab\uf2ac\uf2ad\uf2ae\uf2af\uf2b0\uf2b1\uf2b2\uf2b3\uf2b4\uf2b5\uf2b6\uf2b7\uf2b8\uf2b9\uf2ba\uf2bb\uf2bc\uf2bd\uf2be\uf2bf\uf2c0\uf2c1\uf2c2\uf2c3\uf2c4\uf2c5\uf2c6\uf2c7\uf2c8\uf2c9\uf2ca\uf2cb\uf2cc\uf2cd\uf2ce\uf2cf\uf2d0\uf2d1\uf2d2\uf2d3\uf2d4\uf2d5\uf2d6\uf2d7\uf2d8\uf2d9\uf2da\uf2db\uf2dc\uf2dd\uf2de\uf2df\uf2e0\uf2e1\uf2e2\uf2e3\uf2e4\uf2e5\uf2e6\uf2e7\uf2e8\uf2e9\uf2ea\uf2eb\uf2ec\uf2ed\uf2ee\uf2ef\uf2f0\uf2f1\uf2f2\uf2f3\uf2f4\uf2f5\uf2f6\uf2f7\uf2f8\uf2f9\uf2fa\uf2fb\uf2fc\uf2fd\uf2fe\uf2ff\uf300\uf301\uf302\uf303\uf304\uf305\uf306\uf307\uf308\uf309\uf30a\uf30b\uf30c\uf30d\uf30e\uf30f\uf310\uf311\uf312\uf313\uf314\uf315\uf316\uf317\uf318\uf319\uf31a\uf31b\uf31c\uf31d\uf31e\uf31f\uf320\uf321\uf322\uf323\uf324\uf325\uf326\uf327\uf328\uf329\uf32a\uf32b\uf32c\uf32d\uf32e\uf32f\uf330\uf331\uf332\uf333\uf334\uf335\uf336\uf337\uf338\uf339\uf33a\uf33b\uf33c\uf33d\uf33e\uf33f\uf340\uf341\uf342\uf343\uf344\uf345\uf346\uf347\uf348\uf349\uf34a\uf34b\uf34c\uf34d\uf34e\uf34f\uf350\uf351\uf352\uf353\uf354\uf355\uf356\uf357\uf358\uf359\uf35a\uf35b\uf35c\uf35d\uf35e\uf35f\uf360\uf361\uf362\uf363\uf364\uf365\uf366\uf367\uf368\uf369\uf36a\uf36b\uf36c\uf36d\uf36e\uf36f\uf370\uf371\uf372\uf373\uf374\uf375\uf376\uf377\uf378\uf379\uf37a\uf37b\uf37c\uf37d\uf37e\uf37f\uf380\uf381\uf382\uf383\uf384\uf385\uf386\uf387\uf388\uf389\uf38a\uf38b\uf38c\uf38d\uf38e\uf38f\uf390\uf391\uf392\uf393\uf394\uf395\uf396\uf397\uf398\uf399\uf39a\uf39b\uf39c\uf39d\uf39e\uf39f\uf3a0\uf3a1\uf3a2\uf3a3\uf3a4\uf3a5\uf3a6\uf3a7\uf3a8\uf3a9\uf3aa\uf3ab\uf3ac\uf3ad\uf3ae\uf3af\uf3b0\uf3b1\uf3b2\uf3b3\uf3b4\uf3b5\uf3b6\uf3b7\uf3b8\uf3b9\uf3ba\uf3bb\uf3bc\uf3bd\uf3be\uf3bf\uf3c0\uf3c1\uf3c2\uf3c3\uf3c4\uf3c5\uf3c6\uf3c7\uf3c8\uf3c9\uf3ca\uf3cb\uf3cc\uf3cd\uf3ce\uf3cf\uf3d0\uf3d1\uf3d2\uf3d3\uf3d4\uf3d5\uf3d6\uf3d7\uf3d8\uf3d9\uf3da\uf3db\uf3dc\uf3dd\uf3de\uf3df\uf3e0\uf3e1\uf3e2\uf3e3\uf3e4\uf3e5\uf3e6\uf3e7\uf3e8\uf3e9\uf3ea\uf3eb\uf3ec\uf3ed\uf3ee\uf3ef\uf3f0\uf3f1\uf3f2\uf3f3\uf3f4\uf3f5\uf3f6\uf3f7\uf3f8\uf3f9\uf3fa\uf3fb\uf3fc\uf3fd\uf3fe\uf3ff\uf400\uf401\uf402\uf403\uf404\uf405\uf406\uf407\uf408\uf409\uf40a\uf40b\uf40c\uf40d\uf40e\uf40f\uf410\uf411\uf412\uf413\uf414\uf415\uf416\uf417\uf418\uf419\uf41a\uf41b\uf41c\uf41d\uf41e\uf41f\uf420\uf421\uf422\uf423\uf424\uf425\uf426\uf427\uf428\uf429\uf42a\uf42b\uf42c\uf42d\uf42e\uf42f\uf430\uf431\uf432\uf433\uf434\uf435\uf436\uf437\uf438\uf439\uf43a\uf43b\uf43c\uf43d\uf43e\uf43f\uf440\uf441\uf442\uf443\uf444\uf445\uf446\uf447\uf448\uf449\uf44a\uf44b\uf44c\uf44d\uf44e\uf44f\uf450\uf451\uf452\uf453\uf454\uf455\uf456\uf457\uf458\uf459\uf45a\uf45b\uf45c\uf45d\uf45e\uf45f\uf460\uf461\uf462\uf463\uf464\uf465\uf466\uf467\uf468\uf469\uf46a\uf46b\uf46c\uf46d\uf46e\uf46f\uf470\uf471\uf472\uf473\uf474\uf475\uf476\uf477\uf478\uf479\uf47a\uf47b\uf47c\uf47d\uf47e\uf47f\uf480\uf481\uf482\uf483\uf484\uf485\uf486\uf487\uf488\uf489\uf48a\uf48b\uf48c\uf48d\uf48e\uf48f\uf490\uf491\uf492\uf493\uf494\uf495\uf496\uf497\uf498\uf499\uf49a\uf49b\uf49c\uf49d\uf49e\uf49f\uf4a0\uf4a1\uf4a2\uf4a3\uf4a4\uf4a5\uf4a6\uf4a7\uf4a8\uf4a9\uf4aa\uf4ab\uf4ac\uf4ad\uf4ae\uf4af\uf4b0\uf4b1\uf4b2\uf4b3\uf4b4\uf4b5\uf4b6\uf4b7\uf4b8\uf4b9\uf4ba\uf4bb\uf4bc\uf4bd\uf4be\uf4bf\uf4c0\uf4c1\uf4c2\uf4c3\uf4c4\uf4c5\uf4c6\uf4c7\uf4c8\uf4c9\uf4ca\uf4cb\uf4cc\uf4cd\uf4ce\uf4cf\uf4d0\uf4d1\uf4d2\uf4d3\uf4d4\uf4d5\uf4d6\uf4d7\uf4d8\uf4d9\uf4da\uf4db\uf4dc\uf4dd\uf4de\uf4df\uf4e0\uf4e1\uf4e2\uf4e3\uf4e4\uf4e5\uf4e6\uf4e7\uf4e8\uf4e9\uf4ea\uf4eb\uf4ec\uf4ed\uf4ee\uf4ef\uf4f0\uf4f1\uf4f2\uf4f3\uf4f4\uf4f5\uf4f6\uf4f7\uf4f8\uf4f9\uf4fa\uf4fb\uf4fc\uf4fd\uf4fe\uf4ff\uf500\uf501\uf502\uf503\uf504\uf505\uf506\uf507\uf508\uf509\uf50a\uf50b\uf50c\uf50d\uf50e\uf50f\uf510\uf511\uf512\uf513\uf514\uf515\uf516\uf517\uf518\uf519\uf51a\uf51b\uf51c\uf51d\uf51e\uf51f\uf520\uf521\uf522\uf523\uf524\uf525\uf526\uf527\uf528\uf529\uf52a\uf52b\uf52c\uf52d\uf52e\uf52f\uf530\uf531\uf532\uf533\uf534\uf535\uf536\uf537\uf538\uf539\uf53a\uf53b\uf53c\uf53d\uf53e\uf53f\uf540\uf541\uf542\uf543\uf544\uf545\uf546\uf547\uf548\uf549\uf54a\uf54b\uf54c\uf54d\uf54e\uf54f\uf550\uf551\uf552\uf553\uf554\uf555\uf556\uf557\uf558\uf559\uf55a\uf55b\uf55c\uf55d\uf55e\uf55f\uf560\uf561\uf562\uf563\uf564\uf565\uf566\uf567\uf568\uf569\uf56a\uf56b\uf56c\uf56d\uf56e\uf56f\uf570\uf571\uf572\uf573\uf574\uf575\uf576\uf577\uf578\uf579\uf57a\uf57b\uf57c\uf57d\uf57e\uf57f\uf580\uf581\uf582\uf583\uf584\uf585\uf586\uf587\uf588\uf589\uf58a\uf58b\uf58c\uf58d\uf58e\uf58f\uf590\uf591\uf592\uf593\uf594\uf595\uf596\uf597\uf598\uf599\uf59a\uf59b\uf59c\uf59d\uf59e\uf59f\uf5a0\uf5a1\uf5a2\uf5a3\uf5a4\uf5a5\uf5a6\uf5a7\uf5a8\uf5a9\uf5aa\uf5ab\uf5ac\uf5ad\uf5ae\uf5af\uf5b0\uf5b1\uf5b2\uf5b3\uf5b4\uf5b5\uf5b6\uf5b7\uf5b8\uf5b9\uf5ba\uf5bb\uf5bc\uf5bd\uf5be\uf5bf\uf5c0\uf5c1\uf5c2\uf5c3\uf5c4\uf5c5\uf5c6\uf5c7\uf5c8\uf5c9\uf5ca\uf5cb\uf5cc\uf5cd\uf5ce\uf5cf\uf5d0\uf5d1\uf5d2\uf5d3\uf5d4\uf5d5\uf5d6\uf5d7\uf5d8\uf5d9\uf5da\uf5db\uf5dc\uf5dd\uf5de\uf5df\uf5e0\uf5e1\uf5e2\uf5e3\uf5e4\uf5e5\uf5e6\uf5e7\uf5e8\uf5e9\uf5ea\uf5eb\uf5ec\uf5ed\uf5ee\uf5ef\uf5f0\uf5f1\uf5f2\uf5f3\uf5f4\uf5f5\uf5f6\uf5f7\uf5f8\uf5f9\uf5fa\uf5fb\uf5fc\uf5fd\uf5fe\uf5ff\uf600\uf601\uf602\uf603\uf604\uf605\uf606\uf607\uf608\uf609\uf60a\uf60b\uf60c\uf60d\uf60e\uf60f\uf610\uf611\uf612\uf613\uf614\uf615\uf616\uf617\uf618\uf619\uf61a\uf61b\uf61c\uf61d\uf61e\uf61f\uf620\uf621\uf622\uf623\uf624\uf625\uf626\uf627\uf628\uf629\uf62a\uf62b\uf62c\uf62d\uf62e\uf62f\uf630\uf631\uf632\uf633\uf634\uf635\uf636\uf637\uf638\uf639\uf63a\uf63b\uf63c\uf63d\uf63e\uf63f\uf640\uf641\uf642\uf643\uf644\uf645\uf646\uf647\uf648\uf649\uf64a\uf64b\uf64c\uf64d\uf64e\uf64f\uf650\uf651\uf652\uf653\uf654\uf655\uf656\uf657\uf658\uf659\uf65a\uf65b\uf65c\uf65d\uf65e\uf65f\uf660\uf661\uf662\uf663\uf664\uf665\uf666\uf667\uf668\uf669\uf66a\uf66b\uf66c\uf66d\uf66e\uf66f\uf670\uf671\uf672\uf673\uf674\uf675\uf676\uf677\uf678\uf679\uf67a\uf67b\uf67c\uf67d\uf67e\uf67f\uf680\uf681\uf682\uf683\uf684\uf685\uf686\uf687\uf688\uf689\uf68a\uf68b\uf68c\uf68d\uf68e\uf68f\uf690\uf691\uf692\uf693\uf694\uf695\uf696\uf697\uf698\uf699\uf69a\uf69b\uf69c\uf69d\uf69e\uf69f\uf6a0\uf6a1\uf6a2\uf6a3\uf6a4\uf6a5\uf6a6\uf6a7\uf6a8\uf6a9\uf6aa\uf6ab\uf6ac\uf6ad\uf6ae\uf6af\uf6b0\uf6b1\uf6b2\uf6b3\uf6b4\uf6b5\uf6b6\uf6b7\uf6b8\uf6b9\uf6ba\uf6bb\uf6bc\uf6bd\uf6be\uf6bf\uf6c0\uf6c1\uf6c2\uf6c3\uf6c4\uf6c5\uf6c6\uf6c7\uf6c8\uf6c9\uf6ca\uf6cb\uf6cc\uf6cd\uf6ce\uf6cf\uf6d0\uf6d1\uf6d2\uf6d3\uf6d4\uf6d5\uf6d6\uf6d7\uf6d8\uf6d9\uf6da\uf6db\uf6dc\uf6dd\uf6de\uf6df\uf6e0\uf6e1\uf6e2\uf6e3\uf6e4\uf6e5\uf6e6\uf6e7\uf6e8\uf6e9\uf6ea\uf6eb\uf6ec\uf6ed\uf6ee\uf6ef\uf6f0\uf6f1\uf6f2\uf6f3\uf6f4\uf6f5\uf6f6\uf6f7\uf6f8\uf6f9\uf6fa\uf6fb\uf6fc\uf6fd\uf6fe\uf6ff\uf700\uf701\uf702\uf703\uf704\uf705\uf706\uf707\uf708\uf709\uf70a\uf70b\uf70c\uf70d\uf70e\uf70f\uf710\uf711\uf712\uf713\uf714\uf715\uf716\uf717\uf718\uf719\uf71a\uf71b\uf71c\uf71d\uf71e\uf71f\uf720\uf721\uf722\uf723\uf724\uf725\uf726\uf727\uf728\uf729\uf72a\uf72b\uf72c\uf72d\uf72e\uf72f\uf730\uf731\uf732\uf733\uf734\uf735\uf736\uf737\uf738\uf739\uf73a\uf73b\uf73c\uf73d\uf73e\uf73f\uf740\uf741\uf742\uf743\uf744\uf745\uf746\uf747\uf748\uf749\uf74a\uf74b\uf74c\uf74d\uf74e\uf74f\uf750\uf751\uf752\uf753\uf754\uf755\uf756\uf757\uf758\uf759\uf75a\uf75b\uf75c\uf75d\uf75e\uf75f\uf760\uf761\uf762\uf763\uf764\uf765\uf766\uf767\uf768\uf769\uf76a\uf76b\uf76c\uf76d\uf76e\uf76f\uf770\uf771\uf772\uf773\uf774\uf775\uf776\uf777\uf778\uf779\uf77a\uf77b\uf77c\uf77d\uf77e\uf77f\uf780\uf781\uf782\uf783\uf784\uf785\uf786\uf787\uf788\uf789\uf78a\uf78b\uf78c\uf78d\uf78e\uf78f\uf790\uf791\uf792\uf793\uf794\uf795\uf796\uf797\uf798\uf799\uf79a\uf79b\uf79c\uf79d\uf79e\uf79f\uf7a0\uf7a1\uf7a2\uf7a3\uf7a4\uf7a5\uf7a6\uf7a7\uf7a8\uf7a9\uf7aa\uf7ab\uf7ac\uf7ad\uf7ae\uf7af\uf7b0\uf7b1\uf7b2\uf7b3\uf7b4\uf7b5\uf7b6\uf7b7\uf7b8\uf7b9\uf7ba\uf7bb\uf7bc\uf7bd\uf7be\uf7bf\uf7c0\uf7c1\uf7c2\uf7c3\uf7c4\uf7c5\uf7c6\uf7c7\uf7c8\uf7c9\uf7ca\uf7cb\uf7cc\uf7cd\uf7ce\uf7cf\uf7d0\uf7d1\uf7d2\uf7d3\uf7d4\uf7d5\uf7d6\uf7d7\uf7d8\uf7d9\uf7da\uf7db\uf7dc\uf7dd\uf7de\uf7df\uf7e0\uf7e1\uf7e2\uf7e3\uf7e4\uf7e5\uf7e6\uf7e7\uf7e8\uf7e9\uf7ea\uf7eb\uf7ec\uf7ed\uf7ee\uf7ef\uf7f0\uf7f1\uf7f2\uf7f3\uf7f4\uf7f5\uf7f6\uf7f7\uf7f8\uf7f9\uf7fa\uf7fb\uf7fc\uf7fd\uf7fe\uf7ff\uf800\uf801\uf802\uf803\uf804\uf805\uf806\uf807\uf808\uf809\uf80a\uf80b\uf80c\uf80d\uf80e\uf80f\uf810\uf811\uf812\uf813\uf814\uf815\uf816\uf817\uf818\uf819\uf81a\uf81b\uf81c\uf81d\uf81e\uf81f\uf820\uf821\uf822\uf823\uf824\uf825\uf826\uf827\uf828\uf829\uf82a\uf82b\uf82c\uf82d\uf82e\uf82f\uf830\uf831\uf832\uf833\uf834\uf835\uf836\uf837\uf838\uf839\uf83a\uf83b\uf83c\uf83d\uf83e\uf83f\uf840\uf841\uf842\uf843\uf844\uf845\uf846\uf847\uf848\uf849\uf84a\uf84b\uf84c\uf84d\uf84e\uf84f\uf850\uf851\uf852\uf853\uf854\uf855\uf856\uf857\uf858\uf859\uf85a\uf85b\uf85c\uf85d\uf85e\uf85f\uf860\uf861\uf862\uf863\uf864\uf865\uf866\uf867\uf868\uf869\uf86a\uf86b\uf86c\uf86d\uf86e\uf86f\uf870\uf871\uf872\uf873\uf874\uf875\uf876\uf877\uf878\uf879\uf87a\uf87b\uf87c\uf87d\uf87e\uf87f\uf880\uf881\uf882\uf883\uf884\uf885\uf886\uf887\uf888\uf889\uf88a\uf88b\uf88c\uf88d\uf88e\uf88f\uf890\uf891\uf892\uf893\uf894\uf895\uf896\uf897\uf898\uf899\uf89a\uf89b\uf89c\uf89d\uf89e\uf89f\uf8a0\uf8a1\uf8a2\uf8a3\uf8a4\uf8a5\uf8a6\uf8a7\uf8a8\uf8a9\uf8aa\uf8ab\uf8ac\uf8ad\uf8ae\uf8af\uf8b0\uf8b1\uf8b2\uf8b3\uf8b4\uf8b5\uf8b6\uf8b7\uf8b8\uf8b9\uf8ba\uf8bb\uf8bc\uf8bd\uf8be\uf8bf\uf8c0\uf8c1\uf8c2\uf8c3\uf8c4\uf8c5\uf8c6\uf8c7\uf8c8\uf8c9\uf8ca\uf8cb\uf8cc\uf8cd\uf8ce\uf8cf\uf8d0\uf8d1\uf8d2\uf8d3\uf8d4\uf8d5\uf8d6\uf8d7\uf8d8\uf8d9\uf8da\uf8db\uf8dc\uf8dd\uf8de\uf8df\uf8e0\uf8e1\uf8e2\uf8e3\uf8e4\uf8e5\uf8e6\uf8e7\uf8e8\uf8e9\uf8ea\uf8eb\uf8ec\uf8ed\uf8ee\uf8ef\uf8f0\uf8f1\uf8f2\uf8f3\uf8f4\uf8f5\uf8f6\uf8f7\uf8f8\uf8f9\uf8fa\uf8fb\uf8fc\uf8fd\uf8fe\uf8ff'

try:
    Cs = eval(r"'\ud800\ud801\ud802\ud803\ud804\ud805\ud806\ud807\ud808\ud809\ud80a\ud80b\ud80c\ud80d\ud80e\ud80f\ud810\ud811\ud812\ud813\ud814\ud815\ud816\ud817\ud818\ud819\ud81a\ud81b\ud81c\ud81d\ud81e\ud81f\ud820\ud821\ud822\ud823\ud824\ud825\ud826\ud827\ud828\ud829\ud82a\ud82b\ud82c\ud82d\ud82e\ud82f\ud830\ud831\ud832\ud833\ud834\ud835\ud836\ud837\ud838\ud839\ud83a\ud83b\ud83c\ud83d\ud83e\ud83f\ud840\ud841\ud842\ud843\ud844\ud845\ud846\ud847\ud848\ud849\ud84a\ud84b\ud84c\ud84d\ud84e\ud84f\ud850\ud851\ud852\ud853\ud854\ud855\ud856\ud857\ud858\ud859\ud85a\ud85b\ud85c\ud85d\ud85e\ud85f\ud860\ud861\ud862\ud863\ud864\ud865\ud866\ud867\ud868\ud869\ud86a\ud86b\ud86c\ud86d\ud86e\ud86f\ud870\ud871\ud872\ud873\ud874\ud875\ud876\ud877\ud878\ud879\ud87a\ud87b\ud87c\ud87d\ud87e\ud87f\ud880\ud881\ud882\ud883\ud884\ud885\ud886\ud887\ud888\ud889\ud88a\ud88b\ud88c\ud88d\ud88e\ud88f\ud890\ud891\ud892\ud893\ud894\ud895\ud896\ud897\ud898\ud899\ud89a\ud89b\ud89c\ud89d\ud89e\ud89f\ud8a0\ud8a1\ud8a2\ud8a3\ud8a4\ud8a5\ud8a6\ud8a7\ud8a8\ud8a9\ud8aa\ud8ab\ud8ac\ud8ad\ud8ae\ud8af\ud8b0\ud8b1\ud8b2\ud8b3\ud8b4\ud8b5\ud8b6\ud8b7\ud8b8\ud8b9\ud8ba\ud8bb\ud8bc\ud8bd\ud8be\ud8bf\ud8c0\ud8c1\ud8c2\ud8c3\ud8c4\ud8c5\ud8c6\ud8c7\ud8c8\ud8c9\ud8ca\ud8cb\ud8cc\ud8cd\ud8ce\ud8cf\ud8d0\ud8d1\ud8d2\ud8d3\ud8d4\ud8d5\ud8d6\ud8d7\ud8d8\ud8d9\ud8da\ud8db\ud8dc\ud8dd\ud8de\ud8df\ud8e0\ud8e1\ud8e2\ud8e3\ud8e4\ud8e5\ud8e6\ud8e7\ud8e8\ud8e9\ud8ea\ud8eb\ud8ec\ud8ed\ud8ee\ud8ef\ud8f0\ud8f1\ud8f2\ud8f3\ud8f4\ud8f5\ud8f6\ud8f7\ud8f8\ud8f9\ud8fa\ud8fb\ud8fc\ud8fd\ud8fe\ud8ff\ud900\ud901\ud902\ud903\ud904\ud905\ud906\ud907\ud908\ud909\ud90a\ud90b\ud90c\ud90d\ud90e\ud90f\ud910\ud911\ud912\ud913\ud914\ud915\ud916\ud917\ud918\ud919\ud91a\ud91b\ud91c\ud91d\ud91e\ud91f\ud920\ud921\ud922\ud923\ud924\ud925\ud926\ud927\ud928\ud929\ud92a\ud92b\ud92c\ud92d\ud92e\ud92f\ud930\ud931\ud932\ud933\ud934\ud935\ud936\ud937\ud938\ud939\ud93a\ud93b\ud93c\ud93d\ud93e\ud93f\ud940\ud941\ud942\ud943\ud944\ud945\ud946\ud947\ud948\ud949\ud94a\ud94b\ud94c\ud94d\ud94e\ud94f\ud950\ud951\ud952\ud953\ud954\ud955\ud956\ud957\ud958\ud959\ud95a\ud95b\ud95c\ud95d\ud95e\ud95f\ud960\ud961\ud962\ud963\ud964\ud965\ud966\ud967\ud968\ud969\ud96a\ud96b\ud96c\ud96d\ud96e\ud96f\ud970\ud971\ud972\ud973\ud974\ud975\ud976\ud977\ud978\ud979\ud97a\ud97b\ud97c\ud97d\ud97e\ud97f\ud980\ud981\ud982\ud983\ud984\ud985\ud986\ud987\ud988\ud989\ud98a\ud98b\ud98c\ud98d\ud98e\ud98f\ud990\ud991\ud992\ud993\ud994\ud995\ud996\ud997\ud998\ud999\ud99a\ud99b\ud99c\ud99d\ud99e\ud99f\ud9a0\ud9a1\ud9a2\ud9a3\ud9a4\ud9a5\ud9a6\ud9a7\ud9a8\ud9a9\ud9aa\ud9ab\ud9ac\ud9ad\ud9ae\ud9af\ud9b0\ud9b1\ud9b2\ud9b3\ud9b4\ud9b5\ud9b6\ud9b7\ud9b8\ud9b9\ud9ba\ud9bb\ud9bc\ud9bd\ud9be\ud9bf\ud9c0\ud9c1\ud9c2\ud9c3\ud9c4\ud9c5\ud9c6\ud9c7\ud9c8\ud9c9\ud9ca\ud9cb\ud9cc\ud9cd\ud9ce\ud9cf\ud9d0\ud9d1\ud9d2\ud9d3\ud9d4\ud9d5\ud9d6\ud9d7\ud9d8\ud9d9\ud9da\ud9db\ud9dc\ud9dd\ud9de\ud9df\ud9e0\ud9e1\ud9e2\ud9e3\ud9e4\ud9e5\ud9e6\ud9e7\ud9e8\ud9e9\ud9ea\ud9eb\ud9ec\ud9ed\ud9ee\ud9ef\ud9f0\ud9f1\ud9f2\ud9f3\ud9f4\ud9f5\ud9f6\ud9f7\ud9f8\ud9f9\ud9fa\ud9fb\ud9fc\ud9fd\ud9fe\ud9ff\uda00\uda01\uda02\uda03\uda04\uda05\uda06\uda07\uda08\uda09\uda0a\uda0b\uda0c\uda0d\uda0e\uda0f\uda10\uda11\uda12\uda13\uda14\uda15\uda16\uda17\uda18\uda19\uda1a\uda1b\uda1c\uda1d\uda1e\uda1f\uda20\uda21\uda22\uda23\uda24\uda25\uda26\uda27\uda28\uda29\uda2a\uda2b\uda2c\uda2d\uda2e\uda2f\uda30\uda31\uda32\uda33\uda34\uda35\uda36\uda37\uda38\uda39\uda3a\uda3b\uda3c\uda3d\uda3e\uda3f\uda40\uda41\uda42\uda43\uda44\uda45\uda46\uda47\uda48\uda49\uda4a\uda4b\uda4c\uda4d\uda4e\uda4f\uda50\uda51\uda52\uda53\uda54\uda55\uda56\uda57\uda58\uda59\uda5a\uda5b\uda5c\uda5d\uda5e\uda5f\uda60\uda61\uda62\uda63\uda64\uda65\uda66\uda67\uda68\uda69\uda6a\uda6b\uda6c\uda6d\uda6e\uda6f\uda70\uda71\uda72\uda73\uda74\uda75\uda76\uda77\uda78\uda79\uda7a\uda7b\uda7c\uda7d\uda7e\uda7f\uda80\uda81\uda82\uda83\uda84\uda85\uda86\uda87\uda88\uda89\uda8a\uda8b\uda8c\uda8d\uda8e\uda8f\uda90\uda91\uda92\uda93\uda94\uda95\uda96\uda97\uda98\uda99\uda9a\uda9b\uda9c\uda9d\uda9e\uda9f\udaa0\udaa1\udaa2\udaa3\udaa4\udaa5\udaa6\udaa7\udaa8\udaa9\udaaa\udaab\udaac\udaad\udaae\udaaf\udab0\udab1\udab2\udab3\udab4\udab5\udab6\udab7\udab8\udab9\udaba\udabb\udabc\udabd\udabe\udabf\udac0\udac1\udac2\udac3\udac4\udac5\udac6\udac7\udac8\udac9\udaca\udacb\udacc\udacd\udace\udacf\udad0\udad1\udad2\udad3\udad4\udad5\udad6\udad7\udad8\udad9\udada\udadb\udadc\udadd\udade\udadf\udae0\udae1\udae2\udae3\udae4\udae5\udae6\udae7\udae8\udae9\udaea\udaeb\udaec\udaed\udaee\udaef\udaf0\udaf1\udaf2\udaf3\udaf4\udaf5\udaf6\udaf7\udaf8\udaf9\udafa\udafb\udafc\udafd\udafe\udaff\udb00\udb01\udb02\udb03\udb04\udb05\udb06\udb07\udb08\udb09\udb0a\udb0b\udb0c\udb0d\udb0e\udb0f\udb10\udb11\udb12\udb13\udb14\udb15\udb16\udb17\udb18\udb19\udb1a\udb1b\udb1c\udb1d\udb1e\udb1f\udb20\udb21\udb22\udb23\udb24\udb25\udb26\udb27\udb28\udb29\udb2a\udb2b\udb2c\udb2d\udb2e\udb2f\udb30\udb31\udb32\udb33\udb34\udb35\udb36\udb37\udb38\udb39\udb3a\udb3b\udb3c\udb3d\udb3e\udb3f\udb40\udb41\udb42\udb43\udb44\udb45\udb46\udb47\udb48\udb49\udb4a\udb4b\udb4c\udb4d\udb4e\udb4f\udb50\udb51\udb52\udb53\udb54\udb55\udb56\udb57\udb58\udb59\udb5a\udb5b\udb5c\udb5d\udb5e\udb5f\udb60\udb61\udb62\udb63\udb64\udb65\udb66\udb67\udb68\udb69\udb6a\udb6b\udb6c\udb6d\udb6e\udb6f\udb70\udb71\udb72\udb73\udb74\udb75\udb76\udb77\udb78\udb79\udb7a\udb7b\udb7c\udb7d\udb7e\udb7f\udb80\udb81\udb82\udb83\udb84\udb85\udb86\udb87\udb88\udb89\udb8a\udb8b\udb8c\udb8d\udb8e\udb8f\udb90\udb91\udb92\udb93\udb94\udb95\udb96\udb97\udb98\udb99\udb9a\udb9b\udb9c\udb9d\udb9e\udb9f\udba0\udba1\udba2\udba3\udba4\udba5\udba6\udba7\udba8\udba9\udbaa\udbab\udbac\udbad\udbae\udbaf\udbb0\udbb1\udbb2\udbb3\udbb4\udbb5\udbb6\udbb7\udbb8\udbb9\udbba\udbbb\udbbc\udbbd\udbbe\udbbf\udbc0\udbc1\udbc2\udbc3\udbc4\udbc5\udbc6\udbc7\udbc8\udbc9\udbca\udbcb\udbcc\udbcd\udbce\udbcf\udbd0\udbd1\udbd2\udbd3\udbd4\udbd5\udbd6\udbd7\udbd8\udbd9\udbda\udbdb\udbdc\udbdd\udbde\udbdf\udbe0\udbe1\udbe2\udbe3\udbe4\udbe5\udbe6\udbe7\udbe8\udbe9\udbea\udbeb\udbec\udbed\udbee\udbef\udbf0\udbf1\udbf2\udbf3\udbf4\udbf5\udbf6\udbf7\udbf8\udbf9\udbfa\udbfb\udbfc\udbfd\udbfe\U0010fc00\udc01\udc02\udc03\udc04\udc05\udc06\udc07\udc08\udc09\udc0a\udc0b\udc0c\udc0d\udc0e\udc0f\udc10\udc11\udc12\udc13\udc14\udc15\udc16\udc17\udc18\udc19\udc1a\udc1b\udc1c\udc1d\udc1e\udc1f\udc20\udc21\udc22\udc23\udc24\udc25\udc26\udc27\udc28\udc29\udc2a\udc2b\udc2c\udc2d\udc2e\udc2f\udc30\udc31\udc32\udc33\udc34\udc35\udc36\udc37\udc38\udc39\udc3a\udc3b\udc3c\udc3d\udc3e\udc3f\udc40\udc41\udc42\udc43\udc44\udc45\udc46\udc47\udc48\udc49\udc4a\udc4b\udc4c\udc4d\udc4e\udc4f\udc50\udc51\udc52\udc53\udc54\udc55\udc56\udc57\udc58\udc59\udc5a\udc5b\udc5c\udc5d\udc5e\udc5f\udc60\udc61\udc62\udc63\udc64\udc65\udc66\udc67\udc68\udc69\udc6a\udc6b\udc6c\udc6d\udc6e\udc6f\udc70\udc71\udc72\udc73\udc74\udc75\udc76\udc77\udc78\udc79\udc7a\udc7b\udc7c\udc7d\udc7e\udc7f\udc80\udc81\udc82\udc83\udc84\udc85\udc86\udc87\udc88\udc89\udc8a\udc8b\udc8c\udc8d\udc8e\udc8f\udc90\udc91\udc92\udc93\udc94\udc95\udc96\udc97\udc98\udc99\udc9a\udc9b\udc9c\udc9d\udc9e\udc9f\udca0\udca1\udca2\udca3\udca4\udca5\udca6\udca7\udca8\udca9\udcaa\udcab\udcac\udcad\udcae\udcaf\udcb0\udcb1\udcb2\udcb3\udcb4\udcb5\udcb6\udcb7\udcb8\udcb9\udcba\udcbb\udcbc\udcbd\udcbe\udcbf\udcc0\udcc1\udcc2\udcc3\udcc4\udcc5\udcc6\udcc7\udcc8\udcc9\udcca\udccb\udccc\udccd\udcce\udccf\udcd0\udcd1\udcd2\udcd3\udcd4\udcd5\udcd6\udcd7\udcd8\udcd9\udcda\udcdb\udcdc\udcdd\udcde\udcdf\udce0\udce1\udce2\udce3\udce4\udce5\udce6\udce7\udce8\udce9\udcea\udceb\udcec\udced\udcee\udcef\udcf0\udcf1\udcf2\udcf3\udcf4\udcf5\udcf6\udcf7\udcf8\udcf9\udcfa\udcfb\udcfc\udcfd\udcfe\udcff\udd00\udd01\udd02\udd03\udd04\udd05\udd06\udd07\udd08\udd09\udd0a\udd0b\udd0c\udd0d\udd0e\udd0f\udd10\udd11\udd12\udd13\udd14\udd15\udd16\udd17\udd18\udd19\udd1a\udd1b\udd1c\udd1d\udd1e\udd1f\udd20\udd21\udd22\udd23\udd24\udd25\udd26\udd27\udd28\udd29\udd2a\udd2b\udd2c\udd2d\udd2e\udd2f\udd30\udd31\udd32\udd33\udd34\udd35\udd36\udd37\udd38\udd39\udd3a\udd3b\udd3c\udd3d\udd3e\udd3f\udd40\udd41\udd42\udd43\udd44\udd45\udd46\udd47\udd48\udd49\udd4a\udd4b\udd4c\udd4d\udd4e\udd4f\udd50\udd51\udd52\udd53\udd54\udd55\udd56\udd57\udd58\udd59\udd5a\udd5b\udd5c\udd5d\udd5e\udd5f\udd60\udd61\udd62\udd63\udd64\udd65\udd66\udd67\udd68\udd69\udd6a\udd6b\udd6c\udd6d\udd6e\udd6f\udd70\udd71\udd72\udd73\udd74\udd75\udd76\udd77\udd78\udd79\udd7a\udd7b\udd7c\udd7d\udd7e\udd7f\udd80\udd81\udd82\udd83\udd84\udd85\udd86\udd87\udd88\udd89\udd8a\udd8b\udd8c\udd8d\udd8e\udd8f\udd90\udd91\udd92\udd93\udd94\udd95\udd96\udd97\udd98\udd99\udd9a\udd9b\udd9c\udd9d\udd9e\udd9f\udda0\udda1\udda2\udda3\udda4\udda5\udda6\udda7\udda8\udda9\uddaa\uddab\uddac\uddad\uddae\uddaf\uddb0\uddb1\uddb2\uddb3\uddb4\uddb5\uddb6\uddb7\uddb8\uddb9\uddba\uddbb\uddbc\uddbd\uddbe\uddbf\uddc0\uddc1\uddc2\uddc3\uddc4\uddc5\uddc6\uddc7\uddc8\uddc9\uddca\uddcb\uddcc\uddcd\uddce\uddcf\uddd0\uddd1\uddd2\uddd3\uddd4\uddd5\uddd6\uddd7\uddd8\uddd9\uddda\udddb\udddc\udddd\uddde\udddf\udde0\udde1\udde2\udde3\udde4\udde5\udde6\udde7\udde8\udde9\uddea\uddeb\uddec\udded\uddee\uddef\uddf0\uddf1\uddf2\uddf3\uddf4\uddf5\uddf6\uddf7\uddf8\uddf9\uddfa\uddfb\uddfc\uddfd\uddfe\uddff\ude00\ude01\ude02\ude03\ude04\ude05\ude06\ude07\ude08\ude09\ude0a\ude0b\ude0c\ude0d\ude0e\ude0f\ude10\ude11\ude12\ude13\ude14\ude15\ude16\ude17\ude18\ude19\ude1a\ude1b\ude1c\ude1d\ude1e\ude1f\ude20\ude21\ude22\ude23\ude24\ude25\ude26\ude27\ude28\ude29\ude2a\ude2b\ude2c\ude2d\ude2e\ude2f\ude30\ude31\ude32\ude33\ude34\ude35\ude36\ude37\ude38\ude39\ude3a\ude3b\ude3c\ude3d\ude3e\ude3f\ude40\ude41\ude42\ude43\ude44\ude45\ude46\ude47\ude48\ude49\ude4a\ude4b\ude4c\ude4d\ude4e\ude4f\ude50\ude51\ude52\ude53\ude54\ude55\ude56\ude57\ude58\ude59\ude5a\ude5b\ude5c\ude5d\ude5e\ude5f\ude60\ude61\ude62\ude63\ude64\ude65\ude66\ude67\ude68\ude69\ude6a\ude6b\ude6c\ude6d\ude6e\ude6f\ude70\ude71\ude72\ude73\ude74\ude75\ude76\ude77\ude78\ude79\ude7a\ude7b\ude7c\ude7d\ude7e\ude7f\ude80\ude81\ude82\ude83\ude84\ude85\ude86\ude87\ude88\ude89\ude8a\ude8b\ude8c\ude8d\ude8e\ude8f\ude90\ude91\ude92\ude93\ude94\ude95\ude96\ude97\ude98\ude99\ude9a\ude9b\ude9c\ude9d\ude9e\ude9f\udea0\udea1\udea2\udea3\udea4\udea5\udea6\udea7\udea8\udea9\udeaa\udeab\udeac\udead\udeae\udeaf\udeb0\udeb1\udeb2\udeb3\udeb4\udeb5\udeb6\udeb7\udeb8\udeb9\udeba\udebb\udebc\udebd\udebe\udebf\udec0\udec1\udec2\udec3\udec4\udec5\udec6\udec7\udec8\udec9\udeca\udecb\udecc\udecd\udece\udecf\uded0\uded1\uded2\uded3\uded4\uded5\uded6\uded7\uded8\uded9\udeda\udedb\udedc\udedd\udede\udedf\udee0\udee1\udee2\udee3\udee4\udee5\udee6\udee7\udee8\udee9\udeea\udeeb\udeec\udeed\udeee\udeef\udef0\udef1\udef2\udef3\udef4\udef5\udef6\udef7\udef8\udef9\udefa\udefb\udefc\udefd\udefe\udeff\udf00\udf01\udf02\udf03\udf04\udf05\udf06\udf07\udf08\udf09\udf0a\udf0b\udf0c\udf0d\udf0e\udf0f\udf10\udf11\udf12\udf13\udf14\udf15\udf16\udf17\udf18\udf19\udf1a\udf1b\udf1c\udf1d\udf1e\udf1f\udf20\udf21\udf22\udf23\udf24\udf25\udf26\udf27\udf28\udf29\udf2a\udf2b\udf2c\udf2d\udf2e\udf2f\udf30\udf31\udf32\udf33\udf34\udf35\udf36\udf37\udf38\udf39\udf3a\udf3b\udf3c\udf3d\udf3e\udf3f\udf40\udf41\udf42\udf43\udf44\udf45\udf46\udf47\udf48\udf49\udf4a\udf4b\udf4c\udf4d\udf4e\udf4f\udf50\udf51\udf52\udf53\udf54\udf55\udf56\udf57\udf58\udf59\udf5a\udf5b\udf5c\udf5d\udf5e\udf5f\udf60\udf61\udf62\udf63\udf64\udf65\udf66\udf67\udf68\udf69\udf6a\udf6b\udf6c\udf6d\udf6e\udf6f\udf70\udf71\udf72\udf73\udf74\udf75\udf76\udf77\udf78\udf79\udf7a\udf7b\udf7c\udf7d\udf7e\udf7f\udf80\udf81\udf82\udf83\udf84\udf85\udf86\udf87\udf88\udf89\udf8a\udf8b\udf8c\udf8d\udf8e\udf8f\udf90\udf91\udf92\udf93\udf94\udf95\udf96\udf97\udf98\udf99\udf9a\udf9b\udf9c\udf9d\udf9e\udf9f\udfa0\udfa1\udfa2\udfa3\udfa4\udfa5\udfa6\udfa7\udfa8\udfa9\udfaa\udfab\udfac\udfad\udfae\udfaf\udfb0\udfb1\udfb2\udfb3\udfb4\udfb5\udfb6\udfb7\udfb8\udfb9\udfba\udfbb\udfbc\udfbd\udfbe\udfbf\udfc0\udfc1\udfc2\udfc3\udfc4\udfc5\udfc6\udfc7\udfc8\udfc9\udfca\udfcb\udfcc\udfcd\udfce\udfcf\udfd0\udfd1\udfd2\udfd3\udfd4\udfd5\udfd6\udfd7\udfd8\udfd9\udfda\udfdb\udfdc\udfdd\udfde\udfdf\udfe0\udfe1\udfe2\udfe3\udfe4\udfe5\udfe6\udfe7\udfe8\udfe9\udfea\udfeb\udfec\udfed\udfee\udfef\udff0\udff1\udff2\udff3\udff4\udff5\udff6\udff7\udff8\udff9\udffa\udffb\udffc\udffd\udffe\udfff'")
except UnicodeDecodeError:
    Cs = '' # Jython can't handle isolated surrogates

Ll = u'abcdefghijklmnopqrstuvwxyz\xaa\xb5\xba\xdf\xe0\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xeb\xec\xed\xee\xef\xf0\xf1\xf2\xf3\xf4\xf5\xf6\xf8\xf9\xfa\xfb\xfc\xfd\xfe\xff\u0101\u0103\u0105\u0107\u0109\u010b\u010d\u010f\u0111\u0113\u0115\u0117\u0119\u011b\u011d\u011f\u0121\u0123\u0125\u0127\u0129\u012b\u012d\u012f\u0131\u0133\u0135\u0137\u0138\u013a\u013c\u013e\u0140\u0142\u0144\u0146\u0148\u0149\u014b\u014d\u014f\u0151\u0153\u0155\u0157\u0159\u015b\u015d\u015f\u0161\u0163\u0165\u0167\u0169\u016b\u016d\u016f\u0171\u0173\u0175\u0177\u017a\u017c\u017e\u017f\u0180\u0183\u0185\u0188\u018c\u018d\u0192\u0195\u0199\u019a\u019b\u019e\u01a1\u01a3\u01a5\u01a8\u01aa\u01ab\u01ad\u01b0\u01b4\u01b6\u01b9\u01ba\u01bd\u01be\u01bf\u01c6\u01c9\u01cc\u01ce\u01d0\u01d2\u01d4\u01d6\u01d8\u01da\u01dc\u01dd\u01df\u01e1\u01e3\u01e5\u01e7\u01e9\u01eb\u01ed\u01ef\u01f0\u01f3\u01f5\u01f9\u01fb\u01fd\u01ff\u0201\u0203\u0205\u0207\u0209\u020b\u020d\u020f\u0211\u0213\u0215\u0217\u0219\u021b\u021d\u021f\u0221\u0223\u0225\u0227\u0229\u022b\u022d\u022f\u0231\u0233\u0234\u0235\u0236\u0237\u0238\u0239\u023c\u023f\u0240\u0250\u0251\u0252\u0253\u0254\u0255\u0256\u0257\u0258\u0259\u025a\u025b\u025c\u025d\u025e\u025f\u0260\u0261\u0262\u0263\u0264\u0265\u0266\u0267\u0268\u0269\u026a\u026b\u026c\u026d\u026e\u026f\u0270\u0271\u0272\u0273\u0274\u0275\u0276\u0277\u0278\u0279\u027a\u027b\u027c\u027d\u027e\u027f\u0280\u0281\u0282\u0283\u0284\u0285\u0286\u0287\u0288\u0289\u028a\u028b\u028c\u028d\u028e\u028f\u0290\u0291\u0292\u0293\u0294\u0295\u0296\u0297\u0298\u0299\u029a\u029b\u029c\u029d\u029e\u029f\u02a0\u02a1\u02a2\u02a3\u02a4\u02a5\u02a6\u02a7\u02a8\u02a9\u02aa\u02ab\u02ac\u02ad\u02ae\u02af\u0390\u03ac\u03ad\u03ae\u03af\u03b0\u03b1\u03b2\u03b3\u03b4\u03b5\u03b6\u03b7\u03b8\u03b9\u03ba\u03bb\u03bc\u03bd\u03be\u03bf\u03c0\u03c1\u03c2\u03c3\u03c4\u03c5\u03c6\u03c7\u03c8\u03c9\u03ca\u03cb\u03cc\u03cd\u03ce\u03d0\u03d1\u03d5\u03d6\u03d7\u03d9\u03db\u03dd\u03df\u03e1\u03e3\u03e5\u03e7\u03e9\u03eb\u03ed\u03ef\u03f0\u03f1\u03f2\u03f3\u03f5\u03f8\u03fb\u03fc\u0430\u0431\u0432\u0433\u0434\u0435\u0436\u0437\u0438\u0439\u043a\u043b\u043c\u043d\u043e\u043f\u0440\u0441\u0442\u0443\u0444\u0445\u0446\u0447\u0448\u0449\u044a\u044b\u044c\u044d\u044e\u044f\u0450\u0451\u0452\u0453\u0454\u0455\u0456\u0457\u0458\u0459\u045a\u045b\u045c\u045d\u045e\u045f\u0461\u0463\u0465\u0467\u0469\u046b\u046d\u046f\u0471\u0473\u0475\u0477\u0479\u047b\u047d\u047f\u0481\u048b\u048d\u048f\u0491\u0493\u0495\u0497\u0499\u049b\u049d\u049f\u04a1\u04a3\u04a5\u04a7\u04a9\u04ab\u04ad\u04af\u04b1\u04b3\u04b5\u04b7\u04b9\u04bb\u04bd\u04bf\u04c2\u04c4\u04c6\u04c8\u04ca\u04cc\u04ce\u04d1\u04d3\u04d5\u04d7\u04d9\u04db\u04dd\u04df\u04e1\u04e3\u04e5\u04e7\u04e9\u04eb\u04ed\u04ef\u04f1\u04f3\u04f5\u04f7\u04f9\u0501\u0503\u0505\u0507\u0509\u050b\u050d\u050f\u0561\u0562\u0563\u0564\u0565\u0566\u0567\u0568\u0569\u056a\u056b\u056c\u056d\u056e\u056f\u0570\u0571\u0572\u0573\u0574\u0575\u0576\u0577\u0578\u0579\u057a\u057b\u057c\u057d\u057e\u057f\u0580\u0581\u0582\u0583\u0584\u0585\u0586\u0587\u1d00\u1d01\u1d02\u1d03\u1d04\u1d05\u1d06\u1d07\u1d08\u1d09\u1d0a\u1d0b\u1d0c\u1d0d\u1d0e\u1d0f\u1d10\u1d11\u1d12\u1d13\u1d14\u1d15\u1d16\u1d17\u1d18\u1d19\u1d1a\u1d1b\u1d1c\u1d1d\u1d1e\u1d1f\u1d20\u1d21\u1d22\u1d23\u1d24\u1d25\u1d26\u1d27\u1d28\u1d29\u1d2a\u1d2b\u1d62\u1d63\u1d64\u1d65\u1d66\u1d67\u1d68\u1d69\u1d6a\u1d6b\u1d6c\u1d6d\u1d6e\u1d6f\u1d70\u1d71\u1d72\u1d73\u1d74\u1d75\u1d76\u1d77\u1d79\u1d7a\u1d7b\u1d7c\u1d7d\u1d7e\u1d7f\u1d80\u1d81\u1d82\u1d83\u1d84\u1d85\u1d86\u1d87\u1d88\u1d89\u1d8a\u1d8b\u1d8c\u1d8d\u1d8e\u1d8f\u1d90\u1d91\u1d92\u1d93\u1d94\u1d95\u1d96\u1d97\u1d98\u1d99\u1d9a\u1e01\u1e03\u1e05\u1e07\u1e09\u1e0b\u1e0d\u1e0f\u1e11\u1e13\u1e15\u1e17\u1e19\u1e1b\u1e1d\u1e1f\u1e21\u1e23\u1e25\u1e27\u1e29\u1e2b\u1e2d\u1e2f\u1e31\u1e33\u1e35\u1e37\u1e39\u1e3b\u1e3d\u1e3f\u1e41\u1e43\u1e45\u1e47\u1e49\u1e4b\u1e4d\u1e4f\u1e51\u1e53\u1e55\u1e57\u1e59\u1e5b\u1e5d\u1e5f\u1e61\u1e63\u1e65\u1e67\u1e69\u1e6b\u1e6d\u1e6f\u1e71\u1e73\u1e75\u1e77\u1e79\u1e7b\u1e7d\u1e7f\u1e81\u1e83\u1e85\u1e87\u1e89\u1e8b\u1e8d\u1e8f\u1e91\u1e93\u1e95\u1e96\u1e97\u1e98\u1e99\u1e9a\u1e9b\u1ea1\u1ea3\u1ea5\u1ea7\u1ea9\u1eab\u1ead\u1eaf\u1eb1\u1eb3\u1eb5\u1eb7\u1eb9\u1ebb\u1ebd\u1ebf\u1ec1\u1ec3\u1ec5\u1ec7\u1ec9\u1ecb\u1ecd\u1ecf\u1ed1\u1ed3\u1ed5\u1ed7\u1ed9\u1edb\u1edd\u1edf\u1ee1\u1ee3\u1ee5\u1ee7\u1ee9\u1eeb\u1eed\u1eef\u1ef1\u1ef3\u1ef5\u1ef7\u1ef9\u1f00\u1f01\u1f02\u1f03\u1f04\u1f05\u1f06\u1f07\u1f10\u1f11\u1f12\u1f13\u1f14\u1f15\u1f20\u1f21\u1f22\u1f23\u1f24\u1f25\u1f26\u1f27\u1f30\u1f31\u1f32\u1f33\u1f34\u1f35\u1f36\u1f37\u1f40\u1f41\u1f42\u1f43\u1f44\u1f45\u1f50\u1f51\u1f52\u1f53\u1f54\u1f55\u1f56\u1f57\u1f60\u1f61\u1f62\u1f63\u1f64\u1f65\u1f66\u1f67\u1f70\u1f71\u1f72\u1f73\u1f74\u1f75\u1f76\u1f77\u1f78\u1f79\u1f7a\u1f7b\u1f7c\u1f7d\u1f80\u1f81\u1f82\u1f83\u1f84\u1f85\u1f86\u1f87\u1f90\u1f91\u1f92\u1f93\u1f94\u1f95\u1f96\u1f97\u1fa0\u1fa1\u1fa2\u1fa3\u1fa4\u1fa5\u1fa6\u1fa7\u1fb0\u1fb1\u1fb2\u1fb3\u1fb4\u1fb6\u1fb7\u1fbe\u1fc2\u1fc3\u1fc4\u1fc6\u1fc7\u1fd0\u1fd1\u1fd2\u1fd3\u1fd6\u1fd7\u1fe0\u1fe1\u1fe2\u1fe3\u1fe4\u1fe5\u1fe6\u1fe7\u1ff2\u1ff3\u1ff4\u1ff6\u1ff7\u2071\u207f\u210a\u210e\u210f\u2113\u212f\u2134\u2139\u213c\u213d\u2146\u2147\u2148\u2149\u2c30\u2c31\u2c32\u2c33\u2c34\u2c35\u2c36\u2c37\u2c38\u2c39\u2c3a\u2c3b\u2c3c\u2c3d\u2c3e\u2c3f\u2c40\u2c41\u2c42\u2c43\u2c44\u2c45\u2c46\u2c47\u2c48\u2c49\u2c4a\u2c4b\u2c4c\u2c4d\u2c4e\u2c4f\u2c50\u2c51\u2c52\u2c53\u2c54\u2c55\u2c56\u2c57\u2c58\u2c59\u2c5a\u2c5b\u2c5c\u2c5d\u2c5e\u2c81\u2c83\u2c85\u2c87\u2c89\u2c8b\u2c8d\u2c8f\u2c91\u2c93\u2c95\u2c97\u2c99\u2c9b\u2c9d\u2c9f\u2ca1\u2ca3\u2ca5\u2ca7\u2ca9\u2cab\u2cad\u2caf\u2cb1\u2cb3\u2cb5\u2cb7\u2cb9\u2cbb\u2cbd\u2cbf\u2cc1\u2cc3\u2cc5\u2cc7\u2cc9\u2ccb\u2ccd\u2ccf\u2cd1\u2cd3\u2cd5\u2cd7\u2cd9\u2cdb\u2cdd\u2cdf\u2ce1\u2ce3\u2ce4\u2d00\u2d01\u2d02\u2d03\u2d04\u2d05\u2d06\u2d07\u2d08\u2d09\u2d0a\u2d0b\u2d0c\u2d0d\u2d0e\u2d0f\u2d10\u2d11\u2d12\u2d13\u2d14\u2d15\u2d16\u2d17\u2d18\u2d19\u2d1a\u2d1b\u2d1c\u2d1d\u2d1e\u2d1f\u2d20\u2d21\u2d22\u2d23\u2d24\u2d25\ufb00\ufb01\ufb02\ufb03\ufb04\ufb05\ufb06\ufb13\ufb14\ufb15\ufb16\ufb17\uff41\uff42\uff43\uff44\uff45\uff46\uff47\uff48\uff49\uff4a\uff4b\uff4c\uff4d\uff4e\uff4f\uff50\uff51\uff52\uff53\uff54\uff55\uff56\uff57\uff58\uff59\uff5a'

Lm = u'\u02b0\u02b1\u02b2\u02b3\u02b4\u02b5\u02b6\u02b7\u02b8\u02b9\u02ba\u02bb\u02bc\u02bd\u02be\u02bf\u02c0\u02c1\u02c6\u02c7\u02c8\u02c9\u02ca\u02cb\u02cc\u02cd\u02ce\u02cf\u02d0\u02d1\u02e0\u02e1\u02e2\u02e3\u02e4\u02ee\u037a\u0559\u0640\u06e5\u06e6\u0e46\u0ec6\u10fc\u17d7\u1843\u1d2c\u1d2d\u1d2e\u1d2f\u1d30\u1d31\u1d32\u1d33\u1d34\u1d35\u1d36\u1d37\u1d38\u1d39\u1d3a\u1d3b\u1d3c\u1d3d\u1d3e\u1d3f\u1d40\u1d41\u1d42\u1d43\u1d44\u1d45\u1d46\u1d47\u1d48\u1d49\u1d4a\u1d4b\u1d4c\u1d4d\u1d4e\u1d4f\u1d50\u1d51\u1d52\u1d53\u1d54\u1d55\u1d56\u1d57\u1d58\u1d59\u1d5a\u1d5b\u1d5c\u1d5d\u1d5e\u1d5f\u1d60\u1d61\u1d78\u1d9b\u1d9c\u1d9d\u1d9e\u1d9f\u1da0\u1da1\u1da2\u1da3\u1da4\u1da5\u1da6\u1da7\u1da8\u1da9\u1daa\u1dab\u1dac\u1dad\u1dae\u1daf\u1db0\u1db1\u1db2\u1db3\u1db4\u1db5\u1db6\u1db7\u1db8\u1db9\u1dba\u1dbb\u1dbc\u1dbd\u1dbe\u1dbf\u2090\u2091\u2092\u2093\u2094\u2d6f\u3005\u3031\u3032\u3033\u3034\u3035\u303b\u309d\u309e\u30fc\u30fd\u30fe\ua015\uff70\uff9e\uff9f'

Lo = u'\u01bb\u01c0\u01c1\u01c2\u01c3\u05d0\u05d1\u05d2\u05d3\u05d4\u05d5\u05d6\u05d7\u05d8\u05d9\u05da\u05db\u05dc\u05dd\u05de\u05df\u05e0\u05e1\u05e2\u05e3\u05e4\u05e5\u05e6\u05e7\u05e8\u05e9\u05ea\u05f0\u05f1\u05f2\u0621\u0622\u0623\u0624\u0625\u0626\u0627\u0628\u0629\u062a\u062b\u062c\u062d\u062e\u062f\u0630\u0631\u0632\u0633\u0634\u0635\u0636\u0637\u0638\u0639\u063a\u0641\u0642\u0643\u0644\u0645\u0646\u0647\u0648\u0649\u064a\u066e\u066f\u0671\u0672\u0673\u0674\u0675\u0676\u0677\u0678\u0679\u067a\u067b\u067c\u067d\u067e\u067f\u0680\u0681\u0682\u0683\u0684\u0685\u0686\u0687\u0688\u0689\u068a\u068b\u068c\u068d\u068e\u068f\u0690\u0691\u0692\u0693\u0694\u0695\u0696\u0697\u0698\u0699\u069a\u069b\u069c\u069d\u069e\u069f\u06a0\u06a1\u06a2\u06a3\u06a4\u06a5\u06a6\u06a7\u06a8\u06a9\u06aa\u06ab\u06ac\u06ad\u06ae\u06af\u06b0\u06b1\u06b2\u06b3\u06b4\u06b5\u06b6\u06b7\u06b8\u06b9\u06ba\u06bb\u06bc\u06bd\u06be\u06bf\u06c0\u06c1\u06c2\u06c3\u06c4\u06c5\u06c6\u06c7\u06c8\u06c9\u06ca\u06cb\u06cc\u06cd\u06ce\u06cf\u06d0\u06d1\u06d2\u06d3\u06d5\u06ee\u06ef\u06fa\u06fb\u06fc\u06ff\u0710\u0712\u0713\u0714\u0715\u0716\u0717\u0718\u0719\u071a\u071b\u071c\u071d\u071e\u071f\u0720\u0721\u0722\u0723\u0724\u0725\u0726\u0727\u0728\u0729\u072a\u072b\u072c\u072d\u072e\u072f\u074d\u074e\u074f\u0750\u0751\u0752\u0753\u0754\u0755\u0756\u0757\u0758\u0759\u075a\u075b\u075c\u075d\u075e\u075f\u0760\u0761\u0762\u0763\u0764\u0765\u0766\u0767\u0768\u0769\u076a\u076b\u076c\u076d\u0780\u0781\u0782\u0783\u0784\u0785\u0786\u0787\u0788\u0789\u078a\u078b\u078c\u078d\u078e\u078f\u0790\u0791\u0792\u0793\u0794\u0795\u0796\u0797\u0798\u0799\u079a\u079b\u079c\u079d\u079e\u079f\u07a0\u07a1\u07a2\u07a3\u07a4\u07a5\u07b1\u0904\u0905\u0906\u0907\u0908\u0909\u090a\u090b\u090c\u090d\u090e\u090f\u0910\u0911\u0912\u0913\u0914\u0915\u0916\u0917\u0918\u0919\u091a\u091b\u091c\u091d\u091e\u091f\u0920\u0921\u0922\u0923\u0924\u0925\u0926\u0927\u0928\u0929\u092a\u092b\u092c\u092d\u092e\u092f\u0930\u0931\u0932\u0933\u0934\u0935\u0936\u0937\u0938\u0939\u093d\u0950\u0958\u0959\u095a\u095b\u095c\u095d\u095e\u095f\u0960\u0961\u097d\u0985\u0986\u0987\u0988\u0989\u098a\u098b\u098c\u098f\u0990\u0993\u0994\u0995\u0996\u0997\u0998\u0999\u099a\u099b\u099c\u099d\u099e\u099f\u09a0\u09a1\u09a2\u09a3\u09a4\u09a5\u09a6\u09a7\u09a8\u09aa\u09ab\u09ac\u09ad\u09ae\u09af\u09b0\u09b2\u09b6\u09b7\u09b8\u09b9\u09bd\u09ce\u09dc\u09dd\u09df\u09e0\u09e1\u09f0\u09f1\u0a05\u0a06\u0a07\u0a08\u0a09\u0a0a\u0a0f\u0a10\u0a13\u0a14\u0a15\u0a16\u0a17\u0a18\u0a19\u0a1a\u0a1b\u0a1c\u0a1d\u0a1e\u0a1f\u0a20\u0a21\u0a22\u0a23\u0a24\u0a25\u0a26\u0a27\u0a28\u0a2a\u0a2b\u0a2c\u0a2d\u0a2e\u0a2f\u0a30\u0a32\u0a33\u0a35\u0a36\u0a38\u0a39\u0a59\u0a5a\u0a5b\u0a5c\u0a5e\u0a72\u0a73\u0a74\u0a85\u0a86\u0a87\u0a88\u0a89\u0a8a\u0a8b\u0a8c\u0a8d\u0a8f\u0a90\u0a91\u0a93\u0a94\u0a95\u0a96\u0a97\u0a98\u0a99\u0a9a\u0a9b\u0a9c\u0a9d\u0a9e\u0a9f\u0aa0\u0aa1\u0aa2\u0aa3\u0aa4\u0aa5\u0aa6\u0aa7\u0aa8\u0aaa\u0aab\u0aac\u0aad\u0aae\u0aaf\u0ab0\u0ab2\u0ab3\u0ab5\u0ab6\u0ab7\u0ab8\u0ab9\u0abd\u0ad0\u0ae0\u0ae1\u0b05\u0b06\u0b07\u0b08\u0b09\u0b0a\u0b0b\u0b0c\u0b0f\u0b10\u0b13\u0b14\u0b15\u0b16\u0b17\u0b18\u0b19\u0b1a\u0b1b\u0b1c\u0b1d\u0b1e\u0b1f\u0b20\u0b21\u0b22\u0b23\u0b24\u0b25\u0b26\u0b27\u0b28\u0b2a\u0b2b\u0b2c\u0b2d\u0b2e\u0b2f\u0b30\u0b32\u0b33\u0b35\u0b36\u0b37\u0b38\u0b39\u0b3d\u0b5c\u0b5d\u0b5f\u0b60\u0b61\u0b71\u0b83\u0b85\u0b86\u0b87\u0b88\u0b89\u0b8a\u0b8e\u0b8f\u0b90\u0b92\u0b93\u0b94\u0b95\u0b99\u0b9a\u0b9c\u0b9e\u0b9f\u0ba3\u0ba4\u0ba8\u0ba9\u0baa\u0bae\u0baf\u0bb0\u0bb1\u0bb2\u0bb3\u0bb4\u0bb5\u0bb6\u0bb7\u0bb8\u0bb9\u0c05\u0c06\u0c07\u0c08\u0c09\u0c0a\u0c0b\u0c0c\u0c0e\u0c0f\u0c10\u0c12\u0c13\u0c14\u0c15\u0c16\u0c17\u0c18\u0c19\u0c1a\u0c1b\u0c1c\u0c1d\u0c1e\u0c1f\u0c20\u0c21\u0c22\u0c23\u0c24\u0c25\u0c26\u0c27\u0c28\u0c2a\u0c2b\u0c2c\u0c2d\u0c2e\u0c2f\u0c30\u0c31\u0c32\u0c33\u0c35\u0c36\u0c37\u0c38\u0c39\u0c60\u0c61\u0c85\u0c86\u0c87\u0c88\u0c89\u0c8a\u0c8b\u0c8c\u0c8e\u0c8f\u0c90\u0c92\u0c93\u0c94\u0c95\u0c96\u0c97\u0c98\u0c99\u0c9a\u0c9b\u0c9c\u0c9d\u0c9e\u0c9f\u0ca0\u0ca1\u0ca2\u0ca3\u0ca4\u0ca5\u0ca6\u0ca7\u0ca8\u0caa\u0cab\u0cac\u0cad\u0cae\u0caf\u0cb0\u0cb1\u0cb2\u0cb3\u0cb5\u0cb6\u0cb7\u0cb8\u0cb9\u0cbd\u0cde\u0ce0\u0ce1\u0d05\u0d06\u0d07\u0d08\u0d09\u0d0a\u0d0b\u0d0c\u0d0e\u0d0f\u0d10\u0d12\u0d13\u0d14\u0d15\u0d16\u0d17\u0d18\u0d19\u0d1a\u0d1b\u0d1c\u0d1d\u0d1e\u0d1f\u0d20\u0d21\u0d22\u0d23\u0d24\u0d25\u0d26\u0d27\u0d28\u0d2a\u0d2b\u0d2c\u0d2d\u0d2e\u0d2f\u0d30\u0d31\u0d32\u0d33\u0d34\u0d35\u0d36\u0d37\u0d38\u0d39\u0d60\u0d61\u0d85\u0d86\u0d87\u0d88\u0d89\u0d8a\u0d8b\u0d8c\u0d8d\u0d8e\u0d8f\u0d90\u0d91\u0d92\u0d93\u0d94\u0d95\u0d96\u0d9a\u0d9b\u0d9c\u0d9d\u0d9e\u0d9f\u0da0\u0da1\u0da2\u0da3\u0da4\u0da5\u0da6\u0da7\u0da8\u0da9\u0daa\u0dab\u0dac\u0dad\u0dae\u0daf\u0db0\u0db1\u0db3\u0db4\u0db5\u0db6\u0db7\u0db8\u0db9\u0dba\u0dbb\u0dbd\u0dc0\u0dc1\u0dc2\u0dc3\u0dc4\u0dc5\u0dc6\u0e01\u0e02\u0e03\u0e04\u0e05\u0e06\u0e07\u0e08\u0e09\u0e0a\u0e0b\u0e0c\u0e0d\u0e0e\u0e0f\u0e10\u0e11\u0e12\u0e13\u0e14\u0e15\u0e16\u0e17\u0e18\u0e19\u0e1a\u0e1b\u0e1c\u0e1d\u0e1e\u0e1f\u0e20\u0e21\u0e22\u0e23\u0e24\u0e25\u0e26\u0e27\u0e28\u0e29\u0e2a\u0e2b\u0e2c\u0e2d\u0e2e\u0e2f\u0e30\u0e32\u0e33\u0e40\u0e41\u0e42\u0e43\u0e44\u0e45\u0e81\u0e82\u0e84\u0e87\u0e88\u0e8a\u0e8d\u0e94\u0e95\u0e96\u0e97\u0e99\u0e9a\u0e9b\u0e9c\u0e9d\u0e9e\u0e9f\u0ea1\u0ea2\u0ea3\u0ea5\u0ea7\u0eaa\u0eab\u0ead\u0eae\u0eaf\u0eb0\u0eb2\u0eb3\u0ebd\u0ec0\u0ec1\u0ec2\u0ec3\u0ec4\u0edc\u0edd\u0f00\u0f40\u0f41\u0f42\u0f43\u0f44\u0f45\u0f46\u0f47\u0f49\u0f4a\u0f4b\u0f4c\u0f4d\u0f4e\u0f4f\u0f50\u0f51\u0f52\u0f53\u0f54\u0f55\u0f56\u0f57\u0f58\u0f59\u0f5a\u0f5b\u0f5c\u0f5d\u0f5e\u0f5f\u0f60\u0f61\u0f62\u0f63\u0f64\u0f65\u0f66\u0f67\u0f68\u0f69\u0f6a\u0f88\u0f89\u0f8a\u0f8b\u1000\u1001\u1002\u1003\u1004\u1005\u1006\u1007\u1008\u1009\u100a\u100b\u100c\u100d\u100e\u100f\u1010\u1011\u1012\u1013\u1014\u1015\u1016\u1017\u1018\u1019\u101a\u101b\u101c\u101d\u101e\u101f\u1020\u1021\u1023\u1024\u1025\u1026\u1027\u1029\u102a\u1050\u1051\u1052\u1053\u1054\u1055\u10d0\u10d1\u10d2\u10d3\u10d4\u10d5\u10d6\u10d7\u10d8\u10d9\u10da\u10db\u10dc\u10dd\u10de\u10df\u10e0\u10e1\u10e2\u10e3\u10e4\u10e5\u10e6\u10e7\u10e8\u10e9\u10ea\u10eb\u10ec\u10ed\u10ee\u10ef\u10f0\u10f1\u10f2\u10f3\u10f4\u10f5\u10f6\u10f7\u10f8\u10f9\u10fa\u1100\u1101\u1102\u1103\u1104\u1105\u1106\u1107\u1108\u1109\u110a\u110b\u110c\u110d\u110e\u110f\u1110\u1111\u1112\u1113\u1114\u1115\u1116\u1117\u1118\u1119\u111a\u111b\u111c\u111d\u111e\u111f\u1120\u1121\u1122\u1123\u1124\u1125\u1126\u1127\u1128\u1129\u112a\u112b\u112c\u112d\u112e\u112f\u1130\u1131\u1132\u1133\u1134\u1135\u1136\u1137\u1138\u1139\u113a\u113b\u113c\u113d\u113e\u113f\u1140\u1141\u1142\u1143\u1144\u1145\u1146\u1147\u1148\u1149\u114a\u114b\u114c\u114d\u114e\u114f\u1150\u1151\u1152\u1153\u1154\u1155\u1156\u1157\u1158\u1159\u115f\u1160\u1161\u1162\u1163\u1164\u1165\u1166\u1167\u1168\u1169\u116a\u116b\u116c\u116d\u116e\u116f\u1170\u1171\u1172\u1173\u1174\u1175\u1176\u1177\u1178\u1179\u117a\u117b\u117c\u117d\u117e\u117f\u1180\u1181\u1182\u1183\u1184\u1185\u1186\u1187\u1188\u1189\u118a\u118b\u118c\u118d\u118e\u118f\u1190\u1191\u1192\u1193\u1194\u1195\u1196\u1197\u1198\u1199\u119a\u119b\u119c\u119d\u119e\u119f\u11a0\u11a1\u11a2\u11a8\u11a9\u11aa\u11ab\u11ac\u11ad\u11ae\u11af\u11b0\u11b1\u11b2\u11b3\u11b4\u11b5\u11b6\u11b7\u11b8\u11b9\u11ba\u11bb\u11bc\u11bd\u11be\u11bf\u11c0\u11c1\u11c2\u11c3\u11c4\u11c5\u11c6\u11c7\u11c8\u11c9\u11ca\u11cb\u11cc\u11cd\u11ce\u11cf\u11d0\u11d1\u11d2\u11d3\u11d4\u11d5\u11d6\u11d7\u11d8\u11d9\u11da\u11db\u11dc\u11dd\u11de\u11df\u11e0\u11e1\u11e2\u11e3\u11e4\u11e5\u11e6\u11e7\u11e8\u11e9\u11ea\u11eb\u11ec\u11ed\u11ee\u11ef\u11f0\u11f1\u11f2\u11f3\u11f4\u11f5\u11f6\u11f7\u11f8\u11f9\u1200\u1201\u1202\u1203\u1204\u1205\u1206\u1207\u1208\u1209\u120a\u120b\u120c\u120d\u120e\u120f\u1210\u1211\u1212\u1213\u1214\u1215\u1216\u1217\u1218\u1219\u121a\u121b\u121c\u121d\u121e\u121f\u1220\u1221\u1222\u1223\u1224\u1225\u1226\u1227\u1228\u1229\u122a\u122b\u122c\u122d\u122e\u122f\u1230\u1231\u1232\u1233\u1234\u1235\u1236\u1237\u1238\u1239\u123a\u123b\u123c\u123d\u123e\u123f\u1240\u1241\u1242\u1243\u1244\u1245\u1246\u1247\u1248\u124a\u124b\u124c\u124d\u1250\u1251\u1252\u1253\u1254\u1255\u1256\u1258\u125a\u125b\u125c\u125d\u1260\u1261\u1262\u1263\u1264\u1265\u1266\u1267\u1268\u1269\u126a\u126b\u126c\u126d\u126e\u126f\u1270\u1271\u1272\u1273\u1274\u1275\u1276\u1277\u1278\u1279\u127a\u127b\u127c\u127d\u127e\u127f\u1280\u1281\u1282\u1283\u1284\u1285\u1286\u1287\u1288\u128a\u128b\u128c\u128d\u1290\u1291\u1292\u1293\u1294\u1295\u1296\u1297\u1298\u1299\u129a\u129b\u129c\u129d\u129e\u129f\u12a0\u12a1\u12a2\u12a3\u12a4\u12a5\u12a6\u12a7\u12a8\u12a9\u12aa\u12ab\u12ac\u12ad\u12ae\u12af\u12b0\u12b2\u12b3\u12b4\u12b5\u12b8\u12b9\u12ba\u12bb\u12bc\u12bd\u12be\u12c0\u12c2\u12c3\u12c4\u12c5\u12c8\u12c9\u12ca\u12cb\u12cc\u12cd\u12ce\u12cf\u12d0\u12d1\u12d2\u12d3\u12d4\u12d5\u12d6\u12d8\u12d9\u12da\u12db\u12dc\u12dd\u12de\u12df\u12e0\u12e1\u12e2\u12e3\u12e4\u12e5\u12e6\u12e7\u12e8\u12e9\u12ea\u12eb\u12ec\u12ed\u12ee\u12ef\u12f0\u12f1\u12f2\u12f3\u12f4\u12f5\u12f6\u12f7\u12f8\u12f9\u12fa\u12fb\u12fc\u12fd\u12fe\u12ff\u1300\u1301\u1302\u1303\u1304\u1305\u1306\u1307\u1308\u1309\u130a\u130b\u130c\u130d\u130e\u130f\u1310\u1312\u1313\u1314\u1315\u1318\u1319\u131a\u131b\u131c\u131d\u131e\u131f\u1320\u1321\u1322\u1323\u1324\u1325\u1326\u1327\u1328\u1329\u132a\u132b\u132c\u132d\u132e\u132f\u1330\u1331\u1332\u1333\u1334\u1335\u1336\u1337\u1338\u1339\u133a\u133b\u133c\u133d\u133e\u133f\u1340\u1341\u1342\u1343\u1344\u1345\u1346\u1347\u1348\u1349\u134a\u134b\u134c\u134d\u134e\u134f\u1350\u1351\u1352\u1353\u1354\u1355\u1356\u1357\u1358\u1359\u135a\u1380\u1381\u1382\u1383\u1384\u1385\u1386\u1387\u1388\u1389\u138a\u138b\u138c\u138d\u138e\u138f\u13a0\u13a1\u13a2\u13a3\u13a4\u13a5\u13a6\u13a7\u13a8\u13a9\u13aa\u13ab\u13ac\u13ad\u13ae\u13af\u13b0\u13b1\u13b2\u13b3\u13b4\u13b5\u13b6\u13b7\u13b8\u13b9\u13ba\u13bb\u13bc\u13bd\u13be\u13bf\u13c0\u13c1\u13c2\u13c3\u13c4\u13c5\u13c6\u13c7\u13c8\u13c9\u13ca\u13cb\u13cc\u13cd\u13ce\u13cf\u13d0\u13d1\u13d2\u13d3\u13d4\u13d5\u13d6\u13d7\u13d8\u13d9\u13da\u13db\u13dc\u13dd\u13de\u13df\u13e0\u13e1\u13e2\u13e3\u13e4\u13e5\u13e6\u13e7\u13e8\u13e9\u13ea\u13eb\u13ec\u13ed\u13ee\u13ef\u13f0\u13f1\u13f2\u13f3\u13f4\u1401\u1402\u1403\u1404\u1405\u1406\u1407\u1408\u1409\u140a\u140b\u140c\u140d\u140e\u140f\u1410\u1411\u1412\u1413\u1414\u1415\u1416\u1417\u1418\u1419\u141a\u141b\u141c\u141d\u141e\u141f\u1420\u1421\u1422\u1423\u1424\u1425\u1426\u1427\u1428\u1429\u142a\u142b\u142c\u142d\u142e\u142f\u1430\u1431\u1432\u1433\u1434\u1435\u1436\u1437\u1438\u1439\u143a\u143b\u143c\u143d\u143e\u143f\u1440\u1441\u1442\u1443\u1444\u1445\u1446\u1447\u1448\u1449\u144a\u144b\u144c\u144d\u144e\u144f\u1450\u1451\u1452\u1453\u1454\u1455\u1456\u1457\u1458\u1459\u145a\u145b\u145c\u145d\u145e\u145f\u1460\u1461\u1462\u1463\u1464\u1465\u1466\u1467\u1468\u1469\u146a\u146b\u146c\u146d\u146e\u146f\u1470\u1471\u1472\u1473\u1474\u1475\u1476\u1477\u1478\u1479\u147a\u147b\u147c\u147d\u147e\u147f\u1480\u1481\u1482\u1483\u1484\u1485\u1486\u1487\u1488\u1489\u148a\u148b\u148c\u148d\u148e\u148f\u1490\u1491\u1492\u1493\u1494\u1495\u1496\u1497\u1498\u1499\u149a\u149b\u149c\u149d\u149e\u149f\u14a0\u14a1\u14a2\u14a3\u14a4\u14a5\u14a6\u14a7\u14a8\u14a9\u14aa\u14ab\u14ac\u14ad\u14ae\u14af\u14b0\u14b1\u14b2\u14b3\u14b4\u14b5\u14b6\u14b7\u14b8\u14b9\u14ba\u14bb\u14bc\u14bd\u14be\u14bf\u14c0\u14c1\u14c2\u14c3\u14c4\u14c5\u14c6\u14c7\u14c8\u14c9\u14ca\u14cb\u14cc\u14cd\u14ce\u14cf\u14d0\u14d1\u14d2\u14d3\u14d4\u14d5\u14d6\u14d7\u14d8\u14d9\u14da\u14db\u14dc\u14dd\u14de\u14df\u14e0\u14e1\u14e2\u14e3\u14e4\u14e5\u14e6\u14e7\u14e8\u14e9\u14ea\u14eb\u14ec\u14ed\u14ee\u14ef\u14f0\u14f1\u14f2\u14f3\u14f4\u14f5\u14f6\u14f7\u14f8\u14f9\u14fa\u14fb\u14fc\u14fd\u14fe\u14ff\u1500\u1501\u1502\u1503\u1504\u1505\u1506\u1507\u1508\u1509\u150a\u150b\u150c\u150d\u150e\u150f\u1510\u1511\u1512\u1513\u1514\u1515\u1516\u1517\u1518\u1519\u151a\u151b\u151c\u151d\u151e\u151f\u1520\u1521\u1522\u1523\u1524\u1525\u1526\u1527\u1528\u1529\u152a\u152b\u152c\u152d\u152e\u152f\u1530\u1531\u1532\u1533\u1534\u1535\u1536\u1537\u1538\u1539\u153a\u153b\u153c\u153d\u153e\u153f\u1540\u1541\u1542\u1543\u1544\u1545\u1546\u1547\u1548\u1549\u154a\u154b\u154c\u154d\u154e\u154f\u1550\u1551\u1552\u1553\u1554\u1555\u1556\u1557\u1558\u1559\u155a\u155b\u155c\u155d\u155e\u155f\u1560\u1561\u1562\u1563\u1564\u1565\u1566\u1567\u1568\u1569\u156a\u156b\u156c\u156d\u156e\u156f\u1570\u1571\u1572\u1573\u1574\u1575\u1576\u1577\u1578\u1579\u157a\u157b\u157c\u157d\u157e\u157f\u1580\u1581\u1582\u1583\u1584\u1585\u1586\u1587\u1588\u1589\u158a\u158b\u158c\u158d\u158e\u158f\u1590\u1591\u1592\u1593\u1594\u1595\u1596\u1597\u1598\u1599\u159a\u159b\u159c\u159d\u159e\u159f\u15a0\u15a1\u15a2\u15a3\u15a4\u15a5\u15a6\u15a7\u15a8\u15a9\u15aa\u15ab\u15ac\u15ad\u15ae\u15af\u15b0\u15b1\u15b2\u15b3\u15b4\u15b5\u15b6\u15b7\u15b8\u15b9\u15ba\u15bb\u15bc\u15bd\u15be\u15bf\u15c0\u15c1\u15c2\u15c3\u15c4\u15c5\u15c6\u15c7\u15c8\u15c9\u15ca\u15cb\u15cc\u15cd\u15ce\u15cf\u15d0\u15d1\u15d2\u15d3\u15d4\u15d5\u15d6\u15d7\u15d8\u15d9\u15da\u15db\u15dc\u15dd\u15de\u15df\u15e0\u15e1\u15e2\u15e3\u15e4\u15e5\u15e6\u15e7\u15e8\u15e9\u15ea\u15eb\u15ec\u15ed\u15ee\u15ef\u15f0\u15f1\u15f2\u15f3\u15f4\u15f5\u15f6\u15f7\u15f8\u15f9\u15fa\u15fb\u15fc\u15fd\u15fe\u15ff\u1600\u1601\u1602\u1603\u1604\u1605\u1606\u1607\u1608\u1609\u160a\u160b\u160c\u160d\u160e\u160f\u1610\u1611\u1612\u1613\u1614\u1615\u1616\u1617\u1618\u1619\u161a\u161b\u161c\u161d\u161e\u161f\u1620\u1621\u1622\u1623\u1624\u1625\u1626\u1627\u1628\u1629\u162a\u162b\u162c\u162d\u162e\u162f\u1630\u1631\u1632\u1633\u1634\u1635\u1636\u1637\u1638\u1639\u163a\u163b\u163c\u163d\u163e\u163f\u1640\u1641\u1642\u1643\u1644\u1645\u1646\u1647\u1648\u1649\u164a\u164b\u164c\u164d\u164e\u164f\u1650\u1651\u1652\u1653\u1654\u1655\u1656\u1657\u1658\u1659\u165a\u165b\u165c\u165d\u165e\u165f\u1660\u1661\u1662\u1663\u1664\u1665\u1666\u1667\u1668\u1669\u166a\u166b\u166c\u166f\u1670\u1671\u1672\u1673\u1674\u1675\u1676\u1681\u1682\u1683\u1684\u1685\u1686\u1687\u1688\u1689\u168a\u168b\u168c\u168d\u168e\u168f\u1690\u1691\u1692\u1693\u1694\u1695\u1696\u1697\u1698\u1699\u169a\u16a0\u16a1\u16a2\u16a3\u16a4\u16a5\u16a6\u16a7\u16a8\u16a9\u16aa\u16ab\u16ac\u16ad\u16ae\u16af\u16b0\u16b1\u16b2\u16b3\u16b4\u16b5\u16b6\u16b7\u16b8\u16b9\u16ba\u16bb\u16bc\u16bd\u16be\u16bf\u16c0\u16c1\u16c2\u16c3\u16c4\u16c5\u16c6\u16c7\u16c8\u16c9\u16ca\u16cb\u16cc\u16cd\u16ce\u16cf\u16d0\u16d1\u16d2\u16d3\u16d4\u16d5\u16d6\u16d7\u16d8\u16d9\u16da\u16db\u16dc\u16dd\u16de\u16df\u16e0\u16e1\u16e2\u16e3\u16e4\u16e5\u16e6\u16e7\u16e8\u16e9\u16ea\u1700\u1701\u1702\u1703\u1704\u1705\u1706\u1707\u1708\u1709\u170a\u170b\u170c\u170e\u170f\u1710\u1711\u1720\u1721\u1722\u1723\u1724\u1725\u1726\u1727\u1728\u1729\u172a\u172b\u172c\u172d\u172e\u172f\u1730\u1731\u1740\u1741\u1742\u1743\u1744\u1745\u1746\u1747\u1748\u1749\u174a\u174b\u174c\u174d\u174e\u174f\u1750\u1751\u1760\u1761\u1762\u1763\u1764\u1765\u1766\u1767\u1768\u1769\u176a\u176b\u176c\u176e\u176f\u1770\u1780\u1781\u1782\u1783\u1784\u1785\u1786\u1787\u1788\u1789\u178a\u178b\u178c\u178d\u178e\u178f\u1790\u1791\u1792\u1793\u1794\u1795\u1796\u1797\u1798\u1799\u179a\u179b\u179c\u179d\u179e\u179f\u17a0\u17a1\u17a2\u17a3\u17a4\u17a5\u17a6\u17a7\u17a8\u17a9\u17aa\u17ab\u17ac\u17ad\u17ae\u17af\u17b0\u17b1\u17b2\u17b3\u17dc\u1820\u1821\u1822\u1823\u1824\u1825\u1826\u1827\u1828\u1829\u182a\u182b\u182c\u182d\u182e\u182f\u1830\u1831\u1832\u1833\u1834\u1835\u1836\u1837\u1838\u1839\u183a\u183b\u183c\u183d\u183e\u183f\u1840\u1841\u1842\u1844\u1845\u1846\u1847\u1848\u1849\u184a\u184b\u184c\u184d\u184e\u184f\u1850\u1851\u1852\u1853\u1854\u1855\u1856\u1857\u1858\u1859\u185a\u185b\u185c\u185d\u185e\u185f\u1860\u1861\u1862\u1863\u1864\u1865\u1866\u1867\u1868\u1869\u186a\u186b\u186c\u186d\u186e\u186f\u1870\u1871\u1872\u1873\u1874\u1875\u1876\u1877\u1880\u1881\u1882\u1883\u1884\u1885\u1886\u1887\u1888\u1889\u188a\u188b\u188c\u188d\u188e\u188f\u1890\u1891\u1892\u1893\u1894\u1895\u1896\u1897\u1898\u1899\u189a\u189b\u189c\u189d\u189e\u189f\u18a0\u18a1\u18a2\u18a3\u18a4\u18a5\u18a6\u18a7\u18a8\u1900\u1901\u1902\u1903\u1904\u1905\u1906\u1907\u1908\u1909\u190a\u190b\u190c\u190d\u190e\u190f\u1910\u1911\u1912\u1913\u1914\u1915\u1916\u1917\u1918\u1919\u191a\u191b\u191c\u1950\u1951\u1952\u1953\u1954\u1955\u1956\u1957\u1958\u1959\u195a\u195b\u195c\u195d\u195e\u195f\u1960\u1961\u1962\u1963\u1964\u1965\u1966\u1967\u1968\u1969\u196a\u196b\u196c\u196d\u1970\u1971\u1972\u1973\u1974\u1980\u1981\u1982\u1983\u1984\u1985\u1986\u1987\u1988\u1989\u198a\u198b\u198c\u198d\u198e\u198f\u1990\u1991\u1992\u1993\u1994\u1995\u1996\u1997\u1998\u1999\u199a\u199b\u199c\u199d\u199e\u199f\u19a0\u19a1\u19a2\u19a3\u19a4\u19a5\u19a6\u19a7\u19a8\u19a9\u19c1\u19c2\u19c3\u19c4\u19c5\u19c6\u19c7\u1a00\u1a01\u1a02\u1a03\u1a04\u1a05\u1a06\u1a07\u1a08\u1a09\u1a0a\u1a0b\u1a0c\u1a0d\u1a0e\u1a0f\u1a10\u1a11\u1a12\u1a13\u1a14\u1a15\u1a16\u2135\u2136\u2137\u2138\u2d30\u2d31\u2d32\u2d33\u2d34\u2d35\u2d36\u2d37\u2d38\u2d39\u2d3a\u2d3b\u2d3c\u2d3d\u2d3e\u2d3f\u2d40\u2d41\u2d42\u2d43\u2d44\u2d45\u2d46\u2d47\u2d48\u2d49\u2d4a\u2d4b\u2d4c\u2d4d\u2d4e\u2d4f\u2d50\u2d51\u2d52\u2d53\u2d54\u2d55\u2d56\u2d57\u2d58\u2d59\u2d5a\u2d5b\u2d5c\u2d5d\u2d5e\u2d5f\u2d60\u2d61\u2d62\u2d63\u2d64\u2d65\u2d80\u2d81\u2d82\u2d83\u2d84\u2d85\u2d86\u2d87\u2d88\u2d89\u2d8a\u2d8b\u2d8c\u2d8d\u2d8e\u2d8f\u2d90\u2d91\u2d92\u2d93\u2d94\u2d95\u2d96\u2da0\u2da1\u2da2\u2da3\u2da4\u2da5\u2da6\u2da8\u2da9\u2daa\u2dab\u2dac\u2dad\u2dae\u2db0\u2db1\u2db2\u2db3\u2db4\u2db5\u2db6\u2db8\u2db9\u2dba\u2dbb\u2dbc\u2dbd\u2dbe\u2dc0\u2dc1\u2dc2\u2dc3\u2dc4\u2dc5\u2dc6\u2dc8\u2dc9\u2dca\u2dcb\u2dcc\u2dcd\u2dce\u2dd0\u2dd1\u2dd2\u2dd3\u2dd4\u2dd5\u2dd6\u2dd8\u2dd9\u2dda\u2ddb\u2ddc\u2ddd\u2dde\u3006\u303c\u3041\u3042\u3043\u3044\u3045\u3046\u3047\u3048\u3049\u304a\u304b\u304c\u304d\u304e\u304f\u3050\u3051\u3052\u3053\u3054\u3055\u3056\u3057\u3058\u3059\u305a\u305b\u305c\u305d\u305e\u305f\u3060\u3061\u3062\u3063\u3064\u3065\u3066\u3067\u3068\u3069\u306a\u306b\u306c\u306d\u306e\u306f\u3070\u3071\u3072\u3073\u3074\u3075\u3076\u3077\u3078\u3079\u307a\u307b\u307c\u307d\u307e\u307f\u3080\u3081\u3082\u3083\u3084\u3085\u3086\u3087\u3088\u3089\u308a\u308b\u308c\u308d\u308e\u308f\u3090\u3091\u3092\u3093\u3094\u3095\u3096\u309f\u30a1\u30a2\u30a3\u30a4\u30a5\u30a6\u30a7\u30a8\u30a9\u30aa\u30ab\u30ac\u30ad\u30ae\u30af\u30b0\u30b1\u30b2\u30b3\u30b4\u30b5\u30b6\u30b7\u30b8\u30b9\u30ba\u30bb\u30bc\u30bd\u30be\u30bf\u30c0\u30c1\u30c2\u30c3\u30c4\u30c5\u30c6\u30c7\u30c8\u30c9\u30ca\u30cb\u30cc\u30cd\u30ce\u30cf\u30d0\u30d1\u30d2\u30d3\u30d4\u30d5\u30d6\u30d7\u30d8\u30d9\u30da\u30db\u30dc\u30dd\u30de\u30df\u30e0\u30e1\u30e2\u30e3\u30e4\u30e5\u30e6\u30e7\u30e8\u30e9\u30ea\u30eb\u30ec\u30ed\u30ee\u30ef\u30f0\u30f1\u30f2\u30f3\u30f4\u30f5\u30f6\u30f7\u30f8\u30f9\u30fa\u30ff\u3105\u3106\u3107\u3108\u3109\u310a\u310b\u310c\u310d\u310e\u310f\u3110\u3111\u3112\u3113\u3114\u3115\u3116\u3117\u3118\u3119\u311a\u311b\u311c\u311d\u311e\u311f\u3120\u3121\u3122\u3123\u3124\u3125\u3126\u3127\u3128\u3129\u312a\u312b\u312c\u3131\u3132\u3133\u3134\u3135\u3136\u3137\u3138\u3139\u313a\u313b\u313c\u313d\u313e\u313f\u3140\u3141\u3142\u3143\u3144\u3145\u3146\u3147\u3148\u3149\u314a\u314b\u314c\u314d\u314e\u314f\u3150\u3151\u3152\u3153\u3154\u3155\u3156\u3157\u3158\u3159\u315a\u315b\u315c\u315d\u315e\u315f\u3160\u3161\u3162\u3163\u3164\u3165\u3166\u3167\u3168\u3169\u316a\u316b\u316c\u316d\u316e\u316f\u3170\u3171\u3172\u3173\u3174\u3175\u3176\u3177\u3178\u3179\u317a\u317b\u317c\u317d\u317e\u317f\u3180\u3181\u3182\u3183\u3184\u3185\u3186\u3187\u3188\u3189\u318a\u318b\u318c\u318d\u318e\u31a0\u31a1\u31a2\u31a3\u31a4\u31a5\u31a6\u31a7\u31a8\u31a9\u31aa\u31ab\u31ac\u31ad\u31ae\u31af\u31b0\u31b1\u31b2\u31b3\u31b4\u31b5\u31b6\u31b7\u31f0\u31f1\u31f2\u31f3\u31f4\u31f5\u31f6\u31f7\u31f8\u31f9\u31fa\u31fb\u31fc\u31fd\u31fe\u31ff\u3400\u3401\u3402\u3403\u3404\u3405\u3406\u3407\u3408\u3409\u340a\u340b\u340c\u340d\u340e\u340f\u3410\u3411\u3412\u3413\u3414\u3415\u3416\u3417\u3418\u3419\u341a\u341b\u341c\u341d\u341e\u341f\u3420\u3421\u3422\u3423\u3424\u3425\u3426\u3427\u3428\u3429\u342a\u342b\u342c\u342d\u342e\u342f\u3430\u3431\u3432\u3433\u3434\u3435\u3436\u3437\u3438\u3439\u343a\u343b\u343c\u343d\u343e\u343f\u3440\u3441\u3442\u3443\u3444\u3445\u3446\u3447\u3448\u3449\u344a\u344b\u344c\u344d\u344e\u344f\u3450\u3451\u3452\u3453\u3454\u3455\u3456\u3457\u3458\u3459\u345a\u345b\u345c\u345d\u345e\u345f\u3460\u3461\u3462\u3463\u3464\u3465\u3466\u3467\u3468\u3469\u346a\u346b\u346c\u346d\u346e\u346f\u3470\u3471\u3472\u3473\u3474\u3475\u3476\u3477\u3478\u3479\u347a\u347b\u347c\u347d\u347e\u347f\u3480\u3481\u3482\u3483\u3484\u3485\u3486\u3487\u3488\u3489\u348a\u348b\u348c\u348d\u348e\u348f\u3490\u3491\u3492\u3493\u3494\u3495\u3496\u3497\u3498\u3499\u349a\u349b\u349c\u349d\u349e\u349f\u34a0\u34a1\u34a2\u34a3\u34a4\u34a5\u34a6\u34a7\u34a8\u34a9\u34aa\u34ab\u34ac\u34ad\u34ae\u34af\u34b0\u34b1\u34b2\u34b3\u34b4\u34b5\u34b6\u34b7\u34b8\u34b9\u34ba\u34bb\u34bc\u34bd\u34be\u34bf\u34c0\u34c1\u34c2\u34c3\u34c4\u34c5\u34c6\u34c7\u34c8\u34c9\u34ca\u34cb\u34cc\u34cd\u34ce\u34cf\u34d0\u34d1\u34d2\u34d3\u34d4\u34d5\u34d6\u34d7\u34d8\u34d9\u34da\u34db\u34dc\u34dd\u34de\u34df\u34e0\u34e1\u34e2\u34e3\u34e4\u34e5\u34e6\u34e7\u34e8\u34e9\u34ea\u34eb\u34ec\u34ed\u34ee\u34ef\u34f0\u34f1\u34f2\u34f3\u34f4\u34f5\u34f6\u34f7\u34f8\u34f9\u34fa\u34fb\u34fc\u34fd\u34fe\u34ff\u3500\u3501\u3502\u3503\u3504\u3505\u3506\u3507\u3508\u3509\u350a\u350b\u350c\u350d\u350e\u350f\u3510\u3511\u3512\u3513\u3514\u3515\u3516\u3517\u3518\u3519\u351a\u351b\u351c\u351d\u351e\u351f\u3520\u3521\u3522\u3523\u3524\u3525\u3526\u3527\u3528\u3529\u352a\u352b\u352c\u352d\u352e\u352f\u3530\u3531\u3532\u3533\u3534\u3535\u3536\u3537\u3538\u3539\u353a\u353b\u353c\u353d\u353e\u353f\u3540\u3541\u3542\u3543\u3544\u3545\u3546\u3547\u3548\u3549\u354a\u354b\u354c\u354d\u354e\u354f\u3550\u3551\u3552\u3553\u3554\u3555\u3556\u3557\u3558\u3559\u355a\u355b\u355c\u355d\u355e\u355f\u3560\u3561\u3562\u3563\u3564\u3565\u3566\u3567\u3568\u3569\u356a\u356b\u356c\u356d\u356e\u356f\u3570\u3571\u3572\u3573\u3574\u3575\u3576\u3577\u3578\u3579\u357a\u357b\u357c\u357d\u357e\u357f\u3580\u3581\u3582\u3583\u3584\u3585\u3586\u3587\u3588\u3589\u358a\u358b\u358c\u358d\u358e\u358f\u3590\u3591\u3592\u3593\u3594\u3595\u3596\u3597\u3598\u3599\u359a\u359b\u359c\u359d\u359e\u359f\u35a0\u35a1\u35a2\u35a3\u35a4\u35a5\u35a6\u35a7\u35a8\u35a9\u35aa\u35ab\u35ac\u35ad\u35ae\u35af\u35b0\u35b1\u35b2\u35b3\u35b4\u35b5\u35b6\u35b7\u35b8\u35b9\u35ba\u35bb\u35bc\u35bd\u35be\u35bf\u35c0\u35c1\u35c2\u35c3\u35c4\u35c5\u35c6\u35c7\u35c8\u35c9\u35ca\u35cb\u35cc\u35cd\u35ce\u35cf\u35d0\u35d1\u35d2\u35d3\u35d4\u35d5\u35d6\u35d7\u35d8\u35d9\u35da\u35db\u35dc\u35dd\u35de\u35df\u35e0\u35e1\u35e2\u35e3\u35e4\u35e5\u35e6\u35e7\u35e8\u35e9\u35ea\u35eb\u35ec\u35ed\u35ee\u35ef\u35f0\u35f1\u35f2\u35f3\u35f4\u35f5\u35f6\u35f7\u35f8\u35f9\u35fa\u35fb\u35fc\u35fd\u35fe\u35ff\u3600\u3601\u3602\u3603\u3604\u3605\u3606\u3607\u3608\u3609\u360a\u360b\u360c\u360d\u360e\u360f\u3610\u3611\u3612\u3613\u3614\u3615\u3616\u3617\u3618\u3619\u361a\u361b\u361c\u361d\u361e\u361f\u3620\u3621\u3622\u3623\u3624\u3625\u3626\u3627\u3628\u3629\u362a\u362b\u362c\u362d\u362e\u362f\u3630\u3631\u3632\u3633\u3634\u3635\u3636\u3637\u3638\u3639\u363a\u363b\u363c\u363d\u363e\u363f\u3640\u3641\u3642\u3643\u3644\u3645\u3646\u3647\u3648\u3649\u364a\u364b\u364c\u364d\u364e\u364f\u3650\u3651\u3652\u3653\u3654\u3655\u3656\u3657\u3658\u3659\u365a\u365b\u365c\u365d\u365e\u365f\u3660\u3661\u3662\u3663\u3664\u3665\u3666\u3667\u3668\u3669\u366a\u366b\u366c\u366d\u366e\u366f\u3670\u3671\u3672\u3673\u3674\u3675\u3676\u3677\u3678\u3679\u367a\u367b\u367c\u367d\u367e\u367f\u3680\u3681\u3682\u3683\u3684\u3685\u3686\u3687\u3688\u3689\u368a\u368b\u368c\u368d\u368e\u368f\u3690\u3691\u3692\u3693\u3694\u3695\u3696\u3697\u3698\u3699\u369a\u369b\u369c\u369d\u369e\u369f\u36a0\u36a1\u36a2\u36a3\u36a4\u36a5\u36a6\u36a7\u36a8\u36a9\u36aa\u36ab\u36ac\u36ad\u36ae\u36af\u36b0\u36b1\u36b2\u36b3\u36b4\u36b5\u36b6\u36b7\u36b8\u36b9\u36ba\u36bb\u36bc\u36bd\u36be\u36bf\u36c0\u36c1\u36c2\u36c3\u36c4\u36c5\u36c6\u36c7\u36c8\u36c9\u36ca\u36cb\u36cc\u36cd\u36ce\u36cf\u36d0\u36d1\u36d2\u36d3\u36d4\u36d5\u36d6\u36d7\u36d8\u36d9\u36da\u36db\u36dc\u36dd\u36de\u36df\u36e0\u36e1\u36e2\u36e3\u36e4\u36e5\u36e6\u36e7\u36e8\u36e9\u36ea\u36eb\u36ec\u36ed\u36ee\u36ef\u36f0\u36f1\u36f2\u36f3\u36f4\u36f5\u36f6\u36f7\u36f8\u36f9\u36fa\u36fb\u36fc\u36fd\u36fe\u36ff\u3700\u3701\u3702\u3703\u3704\u3705\u3706\u3707\u3708\u3709\u370a\u370b\u370c\u370d\u370e\u370f\u3710\u3711\u3712\u3713\u3714\u3715\u3716\u3717\u3718\u3719\u371a\u371b\u371c\u371d\u371e\u371f\u3720\u3721\u3722\u3723\u3724\u3725\u3726\u3727\u3728\u3729\u372a\u372b\u372c\u372d\u372e\u372f\u3730\u3731\u3732\u3733\u3734\u3735\u3736\u3737\u3738\u3739\u373a\u373b\u373c\u373d\u373e\u373f\u3740\u3741\u3742\u3743\u3744\u3745\u3746\u3747\u3748\u3749\u374a\u374b\u374c\u374d\u374e\u374f\u3750\u3751\u3752\u3753\u3754\u3755\u3756\u3757\u3758\u3759\u375a\u375b\u375c\u375d\u375e\u375f\u3760\u3761\u3762\u3763\u3764\u3765\u3766\u3767\u3768\u3769\u376a\u376b\u376c\u376d\u376e\u376f\u3770\u3771\u3772\u3773\u3774\u3775\u3776\u3777\u3778\u3779\u377a\u377b\u377c\u377d\u377e\u377f\u3780\u3781\u3782\u3783\u3784\u3785\u3786\u3787\u3788\u3789\u378a\u378b\u378c\u378d\u378e\u378f\u3790\u3791\u3792\u3793\u3794\u3795\u3796\u3797\u3798\u3799\u379a\u379b\u379c\u379d\u379e\u379f\u37a0\u37a1\u37a2\u37a3\u37a4\u37a5\u37a6\u37a7\u37a8\u37a9\u37aa\u37ab\u37ac\u37ad\u37ae\u37af\u37b0\u37b1\u37b2\u37b3\u37b4\u37b5\u37b6\u37b7\u37b8\u37b9\u37ba\u37bb\u37bc\u37bd\u37be\u37bf\u37c0\u37c1\u37c2\u37c3\u37c4\u37c5\u37c6\u37c7\u37c8\u37c9\u37ca\u37cb\u37cc\u37cd\u37ce\u37cf\u37d0\u37d1\u37d2\u37d3\u37d4\u37d5\u37d6\u37d7\u37d8\u37d9\u37da\u37db\u37dc\u37dd\u37de\u37df\u37e0\u37e1\u37e2\u37e3\u37e4\u37e5\u37e6\u37e7\u37e8\u37e9\u37ea\u37eb\u37ec\u37ed\u37ee\u37ef\u37f0\u37f1\u37f2\u37f3\u37f4\u37f5\u37f6\u37f7\u37f8\u37f9\u37fa\u37fb\u37fc\u37fd\u37fe\u37ff\u3800\u3801\u3802\u3803\u3804\u3805\u3806\u3807\u3808\u3809\u380a\u380b\u380c\u380d\u380e\u380f\u3810\u3811\u3812\u3813\u3814\u3815\u3816\u3817\u3818\u3819\u381a\u381b\u381c\u381d\u381e\u381f\u3820\u3821\u3822\u3823\u3824\u3825\u3826\u3827\u3828\u3829\u382a\u382b\u382c\u382d\u382e\u382f\u3830\u3831\u3832\u3833\u3834\u3835\u3836\u3837\u3838\u3839\u383a\u383b\u383c\u383d\u383e\u383f\u3840\u3841\u3842\u3843\u3844\u3845\u3846\u3847\u3848\u3849\u384a\u384b\u384c\u384d\u384e\u384f\u3850\u3851\u3852\u3853\u3854\u3855\u3856\u3857\u3858\u3859\u385a\u385b\u385c\u385d\u385e\u385f\u3860\u3861\u3862\u3863\u3864\u3865\u3866\u3867\u3868\u3869\u386a\u386b\u386c\u386d\u386e\u386f\u3870\u3871\u3872\u3873\u3874\u3875\u3876\u3877\u3878\u3879\u387a\u387b\u387c\u387d\u387e\u387f\u3880\u3881\u3882\u3883\u3884\u3885\u3886\u3887\u3888\u3889\u388a\u388b\u388c\u388d\u388e\u388f\u3890\u3891\u3892\u3893\u3894\u3895\u3896\u3897\u3898\u3899\u389a\u389b\u389c\u389d\u389e\u389f\u38a0\u38a1\u38a2\u38a3\u38a4\u38a5\u38a6\u38a7\u38a8\u38a9\u38aa\u38ab\u38ac\u38ad\u38ae\u38af\u38b0\u38b1\u38b2\u38b3\u38b4\u38b5\u38b6\u38b7\u38b8\u38b9\u38ba\u38bb\u38bc\u38bd\u38be\u38bf\u38c0\u38c1\u38c2\u38c3\u38c4\u38c5\u38c6\u38c7\u38c8\u38c9\u38ca\u38cb\u38cc\u38cd\u38ce\u38cf\u38d0\u38d1\u38d2\u38d3\u38d4\u38d5\u38d6\u38d7\u38d8\u38d9\u38da\u38db\u38dc\u38dd\u38de\u38df\u38e0\u38e1\u38e2\u38e3\u38e4\u38e5\u38e6\u38e7\u38e8\u38e9\u38ea\u38eb\u38ec\u38ed\u38ee\u38ef\u38f0\u38f1\u38f2\u38f3\u38f4\u38f5\u38f6\u38f7\u38f8\u38f9\u38fa\u38fb\u38fc\u38fd\u38fe\u38ff\u3900\u3901\u3902\u3903\u3904\u3905\u3906\u3907\u3908\u3909\u390a\u390b\u390c\u390d\u390e\u390f\u3910\u3911\u3912\u3913\u3914\u3915\u3916\u3917\u3918\u3919\u391a\u391b\u391c\u391d\u391e\u391f\u3920\u3921\u3922\u3923\u3924\u3925\u3926\u3927\u3928\u3929\u392a\u392b\u392c\u392d\u392e\u392f\u3930\u3931\u3932\u3933\u3934\u3935\u3936\u3937\u3938\u3939\u393a\u393b\u393c\u393d\u393e\u393f\u3940\u3941\u3942\u3943\u3944\u3945\u3946\u3947\u3948\u3949\u394a\u394b\u394c\u394d\u394e\u394f\u3950\u3951\u3952\u3953\u3954\u3955\u3956\u3957\u3958\u3959\u395a\u395b\u395c\u395d\u395e\u395f\u3960\u3961\u3962\u3963\u3964\u3965\u3966\u3967\u3968\u3969\u396a\u396b\u396c\u396d\u396e\u396f\u3970\u3971\u3972\u3973\u3974\u3975\u3976\u3977\u3978\u3979\u397a\u397b\u397c\u397d\u397e\u397f\u3980\u3981\u3982\u3983\u3984\u3985\u3986\u3987\u3988\u3989\u398a\u398b\u398c\u398d\u398e\u398f\u3990\u3991\u3992\u3993\u3994\u3995\u3996\u3997\u3998\u3999\u399a\u399b\u399c\u399d\u399e\u399f\u39a0\u39a1\u39a2\u39a3\u39a4\u39a5\u39a6\u39a7\u39a8\u39a9\u39aa\u39ab\u39ac\u39ad\u39ae\u39af\u39b0\u39b1\u39b2\u39b3\u39b4\u39b5\u39b6\u39b7\u39b8\u39b9\u39ba\u39bb\u39bc\u39bd\u39be\u39bf\u39c0\u39c1\u39c2\u39c3\u39c4\u39c5\u39c6\u39c7\u39c8\u39c9\u39ca\u39cb\u39cc\u39cd\u39ce\u39cf\u39d0\u39d1\u39d2\u39d3\u39d4\u39d5\u39d6\u39d7\u39d8\u39d9\u39da\u39db\u39dc\u39dd\u39de\u39df\u39e0\u39e1\u39e2\u39e3\u39e4\u39e5\u39e6\u39e7\u39e8\u39e9\u39ea\u39eb\u39ec\u39ed\u39ee\u39ef\u39f0\u39f1\u39f2\u39f3\u39f4\u39f5\u39f6\u39f7\u39f8\u39f9\u39fa\u39fb\u39fc\u39fd\u39fe\u39ff\u3a00\u3a01\u3a02\u3a03\u3a04\u3a05\u3a06\u3a07\u3a08\u3a09\u3a0a\u3a0b\u3a0c\u3a0d\u3a0e\u3a0f\u3a10\u3a11\u3a12\u3a13\u3a14\u3a15\u3a16\u3a17\u3a18\u3a19\u3a1a\u3a1b\u3a1c\u3a1d\u3a1e\u3a1f\u3a20\u3a21\u3a22\u3a23\u3a24\u3a25\u3a26\u3a27\u3a28\u3a29\u3a2a\u3a2b\u3a2c\u3a2d\u3a2e\u3a2f\u3a30\u3a31\u3a32\u3a33\u3a34\u3a35\u3a36\u3a37\u3a38\u3a39\u3a3a\u3a3b\u3a3c\u3a3d\u3a3e\u3a3f\u3a40\u3a41\u3a42\u3a43\u3a44\u3a45\u3a46\u3a47\u3a48\u3a49\u3a4a\u3a4b\u3a4c\u3a4d\u3a4e\u3a4f\u3a50\u3a51\u3a52\u3a53\u3a54\u3a55\u3a56\u3a57\u3a58\u3a59\u3a5a\u3a5b\u3a5c\u3a5d\u3a5e\u3a5f\u3a60\u3a61\u3a62\u3a63\u3a64\u3a65\u3a66\u3a67\u3a68\u3a69\u3a6a\u3a6b\u3a6c\u3a6d\u3a6e\u3a6f\u3a70\u3a71\u3a72\u3a73\u3a74\u3a75\u3a76\u3a77\u3a78\u3a79\u3a7a\u3a7b\u3a7c\u3a7d\u3a7e\u3a7f\u3a80\u3a81\u3a82\u3a83\u3a84\u3a85\u3a86\u3a87\u3a88\u3a89\u3a8a\u3a8b\u3a8c\u3a8d\u3a8e\u3a8f\u3a90\u3a91\u3a92\u3a93\u3a94\u3a95\u3a96\u3a97\u3a98\u3a99\u3a9a\u3a9b\u3a9c\u3a9d\u3a9e\u3a9f\u3aa0\u3aa1\u3aa2\u3aa3\u3aa4\u3aa5\u3aa6\u3aa7\u3aa8\u3aa9\u3aaa\u3aab\u3aac\u3aad\u3aae\u3aaf\u3ab0\u3ab1\u3ab2\u3ab3\u3ab4\u3ab5\u3ab6\u3ab7\u3ab8\u3ab9\u3aba\u3abb\u3abc\u3abd\u3abe\u3abf\u3ac0\u3ac1\u3ac2\u3ac3\u3ac4\u3ac5\u3ac6\u3ac7\u3ac8\u3ac9\u3aca\u3acb\u3acc\u3acd\u3ace\u3acf\u3ad0\u3ad1\u3ad2\u3ad3\u3ad4\u3ad5\u3ad6\u3ad7\u3ad8\u3ad9\u3ada\u3adb\u3adc\u3add\u3ade\u3adf\u3ae0\u3ae1\u3ae2\u3ae3\u3ae4\u3ae5\u3ae6\u3ae7\u3ae8\u3ae9\u3aea\u3aeb\u3aec\u3aed\u3aee\u3aef\u3af0\u3af1\u3af2\u3af3\u3af4\u3af5\u3af6\u3af7\u3af8\u3af9\u3afa\u3afb\u3afc\u3afd\u3afe\u3aff\u3b00\u3b01\u3b02\u3b03\u3b04\u3b05\u3b06\u3b07\u3b08\u3b09\u3b0a\u3b0b\u3b0c\u3b0d\u3b0e\u3b0f\u3b10\u3b11\u3b12\u3b13\u3b14\u3b15\u3b16\u3b17\u3b18\u3b19\u3b1a\u3b1b\u3b1c\u3b1d\u3b1e\u3b1f\u3b20\u3b21\u3b22\u3b23\u3b24\u3b25\u3b26\u3b27\u3b28\u3b29\u3b2a\u3b2b\u3b2c\u3b2d\u3b2e\u3b2f\u3b30\u3b31\u3b32\u3b33\u3b34\u3b35\u3b36\u3b37\u3b38\u3b39\u3b3a\u3b3b\u3b3c\u3b3d\u3b3e\u3b3f\u3b40\u3b41\u3b42\u3b43\u3b44\u3b45\u3b46\u3b47\u3b48\u3b49\u3b4a\u3b4b\u3b4c\u3b4d\u3b4e\u3b4f\u3b50\u3b51\u3b52\u3b53\u3b54\u3b55\u3b56\u3b57\u3b58\u3b59\u3b5a\u3b5b\u3b5c\u3b5d\u3b5e\u3b5f\u3b60\u3b61\u3b62\u3b63\u3b64\u3b65\u3b66\u3b67\u3b68\u3b69\u3b6a\u3b6b\u3b6c\u3b6d\u3b6e\u3b6f\u3b70\u3b71\u3b72\u3b73\u3b74\u3b75\u3b76\u3b77\u3b78\u3b79\u3b7a\u3b7b\u3b7c\u3b7d\u3b7e\u3b7f\u3b80\u3b81\u3b82\u3b83\u3b84\u3b85\u3b86\u3b87\u3b88\u3b89\u3b8a\u3b8b\u3b8c\u3b8d\u3b8e\u3b8f\u3b90\u3b91\u3b92\u3b93\u3b94\u3b95\u3b96\u3b97\u3b98\u3b99\u3b9a\u3b9b\u3b9c\u3b9d\u3b9e\u3b9f\u3ba0\u3ba1\u3ba2\u3ba3\u3ba4\u3ba5\u3ba6\u3ba7\u3ba8\u3ba9\u3baa\u3bab\u3bac\u3bad\u3bae\u3baf\u3bb0\u3bb1\u3bb2\u3bb3\u3bb4\u3bb5\u3bb6\u3bb7\u3bb8\u3bb9\u3bba\u3bbb\u3bbc\u3bbd\u3bbe\u3bbf\u3bc0\u3bc1\u3bc2\u3bc3\u3bc4\u3bc5\u3bc6\u3bc7\u3bc8\u3bc9\u3bca\u3bcb\u3bcc\u3bcd\u3bce\u3bcf\u3bd0\u3bd1\u3bd2\u3bd3\u3bd4\u3bd5\u3bd6\u3bd7\u3bd8\u3bd9\u3bda\u3bdb\u3bdc\u3bdd\u3bde\u3bdf\u3be0\u3be1\u3be2\u3be3\u3be4\u3be5\u3be6\u3be7\u3be8\u3be9\u3bea\u3beb\u3bec\u3bed\u3bee\u3bef\u3bf0\u3bf1\u3bf2\u3bf3\u3bf4\u3bf5\u3bf6\u3bf7\u3bf8\u3bf9\u3bfa\u3bfb\u3bfc\u3bfd\u3bfe\u3bff\u3c00\u3c01\u3c02\u3c03\u3c04\u3c05\u3c06\u3c07\u3c08\u3c09\u3c0a\u3c0b\u3c0c\u3c0d\u3c0e\u3c0f\u3c10\u3c11\u3c12\u3c13\u3c14\u3c15\u3c16\u3c17\u3c18\u3c19\u3c1a\u3c1b\u3c1c\u3c1d\u3c1e\u3c1f\u3c20\u3c21\u3c22\u3c23\u3c24\u3c25\u3c26\u3c27\u3c28\u3c29\u3c2a\u3c2b\u3c2c\u3c2d\u3c2e\u3c2f\u3c30\u3c31\u3c32\u3c33\u3c34\u3c35\u3c36\u3c37\u3c38\u3c39\u3c3a\u3c3b\u3c3c\u3c3d\u3c3e\u3c3f\u3c40\u3c41\u3c42\u3c43\u3c44\u3c45\u3c46\u3c47\u3c48\u3c49\u3c4a\u3c4b\u3c4c\u3c4d\u3c4e\u3c4f\u3c50\u3c51\u3c52\u3c53\u3c54\u3c55\u3c56\u3c57\u3c58\u3c59\u3c5a\u3c5b\u3c5c\u3c5d\u3c5e\u3c5f\u3c60\u3c61\u3c62\u3c63\u3c64\u3c65\u3c66\u3c67\u3c68\u3c69\u3c6a\u3c6b\u3c6c\u3c6d\u3c6e\u3c6f\u3c70\u3c71\u3c72\u3c73\u3c74\u3c75\u3c76\u3c77\u3c78\u3c79\u3c7a\u3c7b\u3c7c\u3c7d\u3c7e\u3c7f\u3c80\u3c81\u3c82\u3c83\u3c84\u3c85\u3c86\u3c87\u3c88\u3c89\u3c8a\u3c8b\u3c8c\u3c8d\u3c8e\u3c8f\u3c90\u3c91\u3c92\u3c93\u3c94\u3c95\u3c96\u3c97\u3c98\u3c99\u3c9a\u3c9b\u3c9c\u3c9d\u3c9e\u3c9f\u3ca0\u3ca1\u3ca2\u3ca3\u3ca4\u3ca5\u3ca6\u3ca7\u3ca8\u3ca9\u3caa\u3cab\u3cac\u3cad\u3cae\u3caf\u3cb0\u3cb1\u3cb2\u3cb3\u3cb4\u3cb5\u3cb6\u3cb7\u3cb8\u3cb9\u3cba\u3cbb\u3cbc\u3cbd\u3cbe\u3cbf\u3cc0\u3cc1\u3cc2\u3cc3\u3cc4\u3cc5\u3cc6\u3cc7\u3cc8\u3cc9\u3cca\u3ccb\u3ccc\u3ccd\u3cce\u3ccf\u3cd0\u3cd1\u3cd2\u3cd3\u3cd4\u3cd5\u3cd6\u3cd7\u3cd8\u3cd9\u3cda\u3cdb\u3cdc\u3cdd\u3cde\u3cdf\u3ce0\u3ce1\u3ce2\u3ce3\u3ce4\u3ce5\u3ce6\u3ce7\u3ce8\u3ce9\u3cea\u3ceb\u3cec\u3ced\u3cee\u3cef\u3cf0\u3cf1\u3cf2\u3cf3\u3cf4\u3cf5\u3cf6\u3cf7\u3cf8\u3cf9\u3cfa\u3cfb\u3cfc\u3cfd\u3cfe\u3cff\u3d00\u3d01\u3d02\u3d03\u3d04\u3d05\u3d06\u3d07\u3d08\u3d09\u3d0a\u3d0b\u3d0c\u3d0d\u3d0e\u3d0f\u3d10\u3d11\u3d12\u3d13\u3d14\u3d15\u3d16\u3d17\u3d18\u3d19\u3d1a\u3d1b\u3d1c\u3d1d\u3d1e\u3d1f\u3d20\u3d21\u3d22\u3d23\u3d24\u3d25\u3d26\u3d27\u3d28\u3d29\u3d2a\u3d2b\u3d2c\u3d2d\u3d2e\u3d2f\u3d30\u3d31\u3d32\u3d33\u3d34\u3d35\u3d36\u3d37\u3d38\u3d39\u3d3a\u3d3b\u3d3c\u3d3d\u3d3e\u3d3f\u3d40\u3d41\u3d42\u3d43\u3d44\u3d45\u3d46\u3d47\u3d48\u3d49\u3d4a\u3d4b\u3d4c\u3d4d\u3d4e\u3d4f\u3d50\u3d51\u3d52\u3d53\u3d54\u3d55\u3d56\u3d57\u3d58\u3d59\u3d5a\u3d5b\u3d5c\u3d5d\u3d5e\u3d5f\u3d60\u3d61\u3d62\u3d63\u3d64\u3d65\u3d66\u3d67\u3d68\u3d69\u3d6a\u3d6b\u3d6c\u3d6d\u3d6e\u3d6f\u3d70\u3d71\u3d72\u3d73\u3d74\u3d75\u3d76\u3d77\u3d78\u3d79\u3d7a\u3d7b\u3d7c\u3d7d\u3d7e\u3d7f\u3d80\u3d81\u3d82\u3d83\u3d84\u3d85\u3d86\u3d87\u3d88\u3d89\u3d8a\u3d8b\u3d8c\u3d8d\u3d8e\u3d8f\u3d90\u3d91\u3d92\u3d93\u3d94\u3d95\u3d96\u3d97\u3d98\u3d99\u3d9a\u3d9b\u3d9c\u3d9d\u3d9e\u3d9f\u3da0\u3da1\u3da2\u3da3\u3da4\u3da5\u3da6\u3da7\u3da8\u3da9\u3daa\u3dab\u3dac\u3dad\u3dae\u3daf\u3db0\u3db1\u3db2\u3db3\u3db4\u3db5\u3db6\u3db7\u3db8\u3db9\u3dba\u3dbb\u3dbc\u3dbd\u3dbe\u3dbf\u3dc0\u3dc1\u3dc2\u3dc3\u3dc4\u3dc5\u3dc6\u3dc7\u3dc8\u3dc9\u3dca\u3dcb\u3dcc\u3dcd\u3dce\u3dcf\u3dd0\u3dd1\u3dd2\u3dd3\u3dd4\u3dd5\u3dd6\u3dd7\u3dd8\u3dd9\u3dda\u3ddb\u3ddc\u3ddd\u3dde\u3ddf\u3de0\u3de1\u3de2\u3de3\u3de4\u3de5\u3de6\u3de7\u3de8\u3de9\u3dea\u3deb\u3dec\u3ded\u3dee\u3def\u3df0\u3df1\u3df2\u3df3\u3df4\u3df5\u3df6\u3df7\u3df8\u3df9\u3dfa\u3dfb\u3dfc\u3dfd\u3dfe\u3dff\u3e00\u3e01\u3e02\u3e03\u3e04\u3e05\u3e06\u3e07\u3e08\u3e09\u3e0a\u3e0b\u3e0c\u3e0d\u3e0e\u3e0f\u3e10\u3e11\u3e12\u3e13\u3e14\u3e15\u3e16\u3e17\u3e18\u3e19\u3e1a\u3e1b\u3e1c\u3e1d\u3e1e\u3e1f\u3e20\u3e21\u3e22\u3e23\u3e24\u3e25\u3e26\u3e27\u3e28\u3e29\u3e2a\u3e2b\u3e2c\u3e2d\u3e2e\u3e2f\u3e30\u3e31\u3e32\u3e33\u3e34\u3e35\u3e36\u3e37\u3e38\u3e39\u3e3a\u3e3b\u3e3c\u3e3d\u3e3e\u3e3f\u3e40\u3e41\u3e42\u3e43\u3e44\u3e45\u3e46\u3e47\u3e48\u3e49\u3e4a\u3e4b\u3e4c\u3e4d\u3e4e\u3e4f\u3e50\u3e51\u3e52\u3e53\u3e54\u3e55\u3e56\u3e57\u3e58\u3e59\u3e5a\u3e5b\u3e5c\u3e5d\u3e5e\u3e5f\u3e60\u3e61\u3e62\u3e63\u3e64\u3e65\u3e66\u3e67\u3e68\u3e69\u3e6a\u3e6b\u3e6c\u3e6d\u3e6e\u3e6f\u3e70\u3e71\u3e72\u3e73\u3e74\u3e75\u3e76\u3e77\u3e78\u3e79\u3e7a\u3e7b\u3e7c\u3e7d\u3e7e\u3e7f\u3e80\u3e81\u3e82\u3e83\u3e84\u3e85\u3e86\u3e87\u3e88\u3e89\u3e8a\u3e8b\u3e8c\u3e8d\u3e8e\u3e8f\u3e90\u3e91\u3e92\u3e93\u3e94\u3e95\u3e96\u3e97\u3e98\u3e99\u3e9a\u3e9b\u3e9c\u3e9d\u3e9e\u3e9f\u3ea0\u3ea1\u3ea2\u3ea3\u3ea4\u3ea5\u3ea6\u3ea7\u3ea8\u3ea9\u3eaa\u3eab\u3eac\u3ead\u3eae\u3eaf\u3eb0\u3eb1\u3eb2\u3eb3\u3eb4\u3eb5\u3eb6\u3eb7\u3eb8\u3eb9\u3eba\u3ebb\u3ebc\u3ebd\u3ebe\u3ebf\u3ec0\u3ec1\u3ec2\u3ec3\u3ec4\u3ec5\u3ec6\u3ec7\u3ec8\u3ec9\u3eca\u3ecb\u3ecc\u3ecd\u3ece\u3ecf\u3ed0\u3ed1\u3ed2\u3ed3\u3ed4\u3ed5\u3ed6\u3ed7\u3ed8\u3ed9\u3eda\u3edb\u3edc\u3edd\u3ede\u3edf\u3ee0\u3ee1\u3ee2\u3ee3\u3ee4\u3ee5\u3ee6\u3ee7\u3ee8\u3ee9\u3eea\u3eeb\u3eec\u3eed\u3eee\u3eef\u3ef0\u3ef1\u3ef2\u3ef3\u3ef4\u3ef5\u3ef6\u3ef7\u3ef8\u3ef9\u3efa\u3efb\u3efc\u3efd\u3efe\u3eff\u3f00\u3f01\u3f02\u3f03\u3f04\u3f05\u3f06\u3f07\u3f08\u3f09\u3f0a\u3f0b\u3f0c\u3f0d\u3f0e\u3f0f\u3f10\u3f11\u3f12\u3f13\u3f14\u3f15\u3f16\u3f17\u3f18\u3f19\u3f1a\u3f1b\u3f1c\u3f1d\u3f1e\u3f1f\u3f20\u3f21\u3f22\u3f23\u3f24\u3f25\u3f26\u3f27\u3f28\u3f29\u3f2a\u3f2b\u3f2c\u3f2d\u3f2e\u3f2f\u3f30\u3f31\u3f32\u3f33\u3f34\u3f35\u3f36\u3f37\u3f38\u3f39\u3f3a\u3f3b\u3f3c\u3f3d\u3f3e\u3f3f\u3f40\u3f41\u3f42\u3f43\u3f44\u3f45\u3f46\u3f47\u3f48\u3f49\u3f4a\u3f4b\u3f4c\u3f4d\u3f4e\u3f4f\u3f50\u3f51\u3f52\u3f53\u3f54\u3f55\u3f56\u3f57\u3f58\u3f59\u3f5a\u3f5b\u3f5c\u3f5d\u3f5e\u3f5f\u3f60\u3f61\u3f62\u3f63\u3f64\u3f65\u3f66\u3f67\u3f68\u3f69\u3f6a\u3f6b\u3f6c\u3f6d\u3f6e\u3f6f\u3f70\u3f71\u3f72\u3f73\u3f74\u3f75\u3f76\u3f77\u3f78\u3f79\u3f7a\u3f7b\u3f7c\u3f7d\u3f7e\u3f7f\u3f80\u3f81\u3f82\u3f83\u3f84\u3f85\u3f86\u3f87\u3f88\u3f89\u3f8a\u3f8b\u3f8c\u3f8d\u3f8e\u3f8f\u3f90\u3f91\u3f92\u3f93\u3f94\u3f95\u3f96\u3f97\u3f98\u3f99\u3f9a\u3f9b\u3f9c\u3f9d\u3f9e\u3f9f\u3fa0\u3fa1\u3fa2\u3fa3\u3fa4\u3fa5\u3fa6\u3fa7\u3fa8\u3fa9\u3faa\u3fab\u3fac\u3fad\u3fae\u3faf\u3fb0\u3fb1\u3fb2\u3fb3\u3fb4\u3fb5\u3fb6\u3fb7\u3fb8\u3fb9\u3fba\u3fbb\u3fbc\u3fbd\u3fbe\u3fbf\u3fc0\u3fc1\u3fc2\u3fc3\u3fc4\u3fc5\u3fc6\u3fc7\u3fc8\u3fc9\u3fca\u3fcb\u3fcc\u3fcd\u3fce\u3fcf\u3fd0\u3fd1\u3fd2\u3fd3\u3fd4\u3fd5\u3fd6\u3fd7\u3fd8\u3fd9\u3fda\u3fdb\u3fdc\u3fdd\u3fde\u3fdf\u3fe0\u3fe1\u3fe2\u3fe3\u3fe4\u3fe5\u3fe6\u3fe7\u3fe8\u3fe9\u3fea\u3feb\u3fec\u3fed\u3fee\u3fef\u3ff0\u3ff1\u3ff2\u3ff3\u3ff4\u3ff5\u3ff6\u3ff7\u3ff8\u3ff9\u3ffa\u3ffb\u3ffc\u3ffd\u3ffe\u3fff\u4000\u4001\u4002\u4003\u4004\u4005\u4006\u4007\u4008\u4009\u400a\u400b\u400c\u400d\u400e\u400f\u4010\u4011\u4012\u4013\u4014\u4015\u4016\u4017\u4018\u4019\u401a\u401b\u401c\u401d\u401e\u401f\u4020\u4021\u4022\u4023\u4024\u4025\u4026\u4027\u4028\u4029\u402a\u402b\u402c\u402d\u402e\u402f\u4030\u4031\u4032\u4033\u4034\u4035\u4036\u4037\u4038\u4039\u403a\u403b\u403c\u403d\u403e\u403f\u4040\u4041\u4042\u4043\u4044\u4045\u4046\u4047\u4048\u4049\u404a\u404b\u404c\u404d\u404e\u404f\u4050\u4051\u4052\u4053\u4054\u4055\u4056\u4057\u4058\u4059\u405a\u405b\u405c\u405d\u405e\u405f\u4060\u4061\u4062\u4063\u4064\u4065\u4066\u4067\u4068\u4069\u406a\u406b\u406c\u406d\u406e\u406f\u4070\u4071\u4072\u4073\u4074\u4075\u4076\u4077\u4078\u4079\u407a\u407b\u407c\u407d\u407e\u407f\u4080\u4081\u4082\u4083\u4084\u4085\u4086\u4087\u4088\u4089\u408a\u408b\u408c\u408d\u408e\u408f\u4090\u4091\u4092\u4093\u4094\u4095\u4096\u4097\u4098\u4099\u409a\u409b\u409c\u409d\u409e\u409f\u40a0\u40a1\u40a2\u40a3\u40a4\u40a5\u40a6\u40a7\u40a8\u40a9\u40aa\u40ab\u40ac\u40ad\u40ae\u40af\u40b0\u40b1\u40b2\u40b3\u40b4\u40b5\u40b6\u40b7\u40b8\u40b9\u40ba\u40bb\u40bc\u40bd\u40be\u40bf\u40c0\u40c1\u40c2\u40c3\u40c4\u40c5\u40c6\u40c7\u40c8\u40c9\u40ca\u40cb\u40cc\u40cd\u40ce\u40cf\u40d0\u40d1\u40d2\u40d3\u40d4\u40d5\u40d6\u40d7\u40d8\u40d9\u40da\u40db\u40dc\u40dd\u40de\u40df\u40e0\u40e1\u40e2\u40e3\u40e4\u40e5\u40e6\u40e7\u40e8\u40e9\u40ea\u40eb\u40ec\u40ed\u40ee\u40ef\u40f0\u40f1\u40f2\u40f3\u40f4\u40f5\u40f6\u40f7\u40f8\u40f9\u40fa\u40fb\u40fc\u40fd\u40fe\u40ff\u4100\u4101\u4102\u4103\u4104\u4105\u4106\u4107\u4108\u4109\u410a\u410b\u410c\u410d\u410e\u410f\u4110\u4111\u4112\u4113\u4114\u4115\u4116\u4117\u4118\u4119\u411a\u411b\u411c\u411d\u411e\u411f\u4120\u4121\u4122\u4123\u4124\u4125\u4126\u4127\u4128\u4129\u412a\u412b\u412c\u412d\u412e\u412f\u4130\u4131\u4132\u4133\u4134\u4135\u4136\u4137\u4138\u4139\u413a\u413b\u413c\u413d\u413e\u413f\u4140\u4141\u4142\u4143\u4144\u4145\u4146\u4147\u4148\u4149\u414a\u414b\u414c\u414d\u414e\u414f\u4150\u4151\u4152\u4153\u4154\u4155\u4156\u4157\u4158\u4159\u415a\u415b\u415c\u415d\u415e\u415f\u4160\u4161\u4162\u4163\u4164\u4165\u4166\u4167\u4168\u4169\u416a\u416b\u416c\u416d\u416e\u416f\u4170\u4171\u4172\u4173\u4174\u4175\u4176\u4177\u4178\u4179\u417a\u417b\u417c\u417d\u417e\u417f\u4180\u4181\u4182\u4183\u4184\u4185\u4186\u4187\u4188\u4189\u418a\u418b\u418c\u418d\u418e\u418f\u4190\u4191\u4192\u4193\u4194\u4195\u4196\u4197\u4198\u4199\u419a\u419b\u419c\u419d\u419e\u419f\u41a0\u41a1\u41a2\u41a3\u41a4\u41a5\u41a6\u41a7\u41a8\u41a9\u41aa\u41ab\u41ac\u41ad\u41ae\u41af\u41b0\u41b1\u41b2\u41b3\u41b4\u41b5\u41b6\u41b7\u41b8\u41b9\u41ba\u41bb\u41bc\u41bd\u41be\u41bf\u41c0\u41c1\u41c2\u41c3\u41c4\u41c5\u41c6\u41c7\u41c8\u41c9\u41ca\u41cb\u41cc\u41cd\u41ce\u41cf\u41d0\u41d1\u41d2\u41d3\u41d4\u41d5\u41d6\u41d7\u41d8\u41d9\u41da\u41db\u41dc\u41dd\u41de\u41df\u41e0\u41e1\u41e2\u41e3\u41e4\u41e5\u41e6\u41e7\u41e8\u41e9\u41ea\u41eb\u41ec\u41ed\u41ee\u41ef\u41f0\u41f1\u41f2\u41f3\u41f4\u41f5\u41f6\u41f7\u41f8\u41f9\u41fa\u41fb\u41fc\u41fd\u41fe\u41ff\u4200\u4201\u4202\u4203\u4204\u4205\u4206\u4207\u4208\u4209\u420a\u420b\u420c\u420d\u420e\u420f\u4210\u4211\u4212\u4213\u4214\u4215\u4216\u4217\u4218\u4219\u421a\u421b\u421c\u421d\u421e\u421f\u4220\u4221\u4222\u4223\u4224\u4225\u4226\u4227\u4228\u4229\u422a\u422b\u422c\u422d\u422e\u422f\u4230\u4231\u4232\u4233\u4234\u4235\u4236\u4237\u4238\u4239\u423a\u423b\u423c\u423d\u423e\u423f\u4240\u4241\u4242\u4243\u4244\u4245\u4246\u4247\u4248\u4249\u424a\u424b\u424c\u424d\u424e\u424f\u4250\u4251\u4252\u4253\u4254\u4255\u4256\u4257\u4258\u4259\u425a\u425b\u425c\u425d\u425e\u425f\u4260\u4261\u4262\u4263\u4264\u4265\u4266\u4267\u4268\u4269\u426a\u426b\u426c\u426d\u426e\u426f\u4270\u4271\u4272\u4273\u4274\u4275\u4276\u4277\u4278\u4279\u427a\u427b\u427c\u427d\u427e\u427f\u4280\u4281\u4282\u4283\u4284\u4285\u4286\u4287\u4288\u4289\u428a\u428b\u428c\u428d\u428e\u428f\u4290\u4291\u4292\u4293\u4294\u4295\u4296\u4297\u4298\u4299\u429a\u429b\u429c\u429d\u429e\u429f\u42a0\u42a1\u42a2\u42a3\u42a4\u42a5\u42a6\u42a7\u42a8\u42a9\u42aa\u42ab\u42ac\u42ad\u42ae\u42af\u42b0\u42b1\u42b2\u42b3\u42b4\u42b5\u42b6\u42b7\u42b8\u42b9\u42ba\u42bb\u42bc\u42bd\u42be\u42bf\u42c0\u42c1\u42c2\u42c3\u42c4\u42c5\u42c6\u42c7\u42c8\u42c9\u42ca\u42cb\u42cc\u42cd\u42ce\u42cf\u42d0\u42d1\u42d2\u42d3\u42d4\u42d5\u42d6\u42d7\u42d8\u42d9\u42da\u42db\u42dc\u42dd\u42de\u42df\u42e0\u42e1\u42e2\u42e3\u42e4\u42e5\u42e6\u42e7\u42e8\u42e9\u42ea\u42eb\u42ec\u42ed\u42ee\u42ef\u42f0\u42f1\u42f2\u42f3\u42f4\u42f5\u42f6\u42f7\u42f8\u42f9\u42fa\u42fb\u42fc\u42fd\u42fe\u42ff\u4300\u4301\u4302\u4303\u4304\u4305\u4306\u4307\u4308\u4309\u430a\u430b\u430c\u430d\u430e\u430f\u4310\u4311\u4312\u4313\u4314\u4315\u4316\u4317\u4318\u4319\u431a\u431b\u431c\u431d\u431e\u431f\u4320\u4321\u4322\u4323\u4324\u4325\u4326\u4327\u4328\u4329\u432a\u432b\u432c\u432d\u432e\u432f\u4330\u4331\u4332\u4333\u4334\u4335\u4336\u4337\u4338\u4339\u433a\u433b\u433c\u433d\u433e\u433f\u4340\u4341\u4342\u4343\u4344\u4345\u4346\u4347\u4348\u4349\u434a\u434b\u434c\u434d\u434e\u434f\u4350\u4351\u4352\u4353\u4354\u4355\u4356\u4357\u4358\u4359\u435a\u435b\u435c\u435d\u435e\u435f\u4360\u4361\u4362\u4363\u4364\u4365\u4366\u4367\u4368\u4369\u436a\u436b\u436c\u436d\u436e\u436f\u4370\u4371\u4372\u4373\u4374\u4375\u4376\u4377\u4378\u4379\u437a\u437b\u437c\u437d\u437e\u437f\u4380\u4381\u4382\u4383\u4384\u4385\u4386\u4387\u4388\u4389\u438a\u438b\u438c\u438d\u438e\u438f\u4390\u4391\u4392\u4393\u4394\u4395\u4396\u4397\u4398\u4399\u439a\u439b\u439c\u439d\u439e\u439f\u43a0\u43a1\u43a2\u43a3\u43a4\u43a5\u43a6\u43a7\u43a8\u43a9\u43aa\u43ab\u43ac\u43ad\u43ae\u43af\u43b0\u43b1\u43b2\u43b3\u43b4\u43b5\u43b6\u43b7\u43b8\u43b9\u43ba\u43bb\u43bc\u43bd\u43be\u43bf\u43c0\u43c1\u43c2\u43c3\u43c4\u43c5\u43c6\u43c7\u43c8\u43c9\u43ca\u43cb\u43cc\u43cd\u43ce\u43cf\u43d0\u43d1\u43d2\u43d3\u43d4\u43d5\u43d6\u43d7\u43d8\u43d9\u43da\u43db\u43dc\u43dd\u43de\u43df\u43e0\u43e1\u43e2\u43e3\u43e4\u43e5\u43e6\u43e7\u43e8\u43e9\u43ea\u43eb\u43ec\u43ed\u43ee\u43ef\u43f0\u43f1\u43f2\u43f3\u43f4\u43f5\u43f6\u43f7\u43f8\u43f9\u43fa\u43fb\u43fc\u43fd\u43fe\u43ff\u4400\u4401\u4402\u4403\u4404\u4405\u4406\u4407\u4408\u4409\u440a\u440b\u440c\u440d\u440e\u440f\u4410\u4411\u4412\u4413\u4414\u4415\u4416\u4417\u4418\u4419\u441a\u441b\u441c\u441d\u441e\u441f\u4420\u4421\u4422\u4423\u4424\u4425\u4426\u4427\u4428\u4429\u442a\u442b\u442c\u442d\u442e\u442f\u4430\u4431\u4432\u4433\u4434\u4435\u4436\u4437\u4438\u4439\u443a\u443b\u443c\u443d\u443e\u443f\u4440\u4441\u4442\u4443\u4444\u4445\u4446\u4447\u4448\u4449\u444a\u444b\u444c\u444d\u444e\u444f\u4450\u4451\u4452\u4453\u4454\u4455\u4456\u4457\u4458\u4459\u445a\u445b\u445c\u445d\u445e\u445f\u4460\u4461\u4462\u4463\u4464\u4465\u4466\u4467\u4468\u4469\u446a\u446b\u446c\u446d\u446e\u446f\u4470\u4471\u4472\u4473\u4474\u4475\u4476\u4477\u4478\u4479\u447a\u447b\u447c\u447d\u447e\u447f\u4480\u4481\u4482\u4483\u4484\u4485\u4486\u4487\u4488\u4489\u448a\u448b\u448c\u448d\u448e\u448f\u4490\u4491\u4492\u4493\u4494\u4495\u4496\u4497\u4498\u4499\u449a\u449b\u449c\u449d\u449e\u449f\u44a0\u44a1\u44a2\u44a3\u44a4\u44a5\u44a6\u44a7\u44a8\u44a9\u44aa\u44ab\u44ac\u44ad\u44ae\u44af\u44b0\u44b1\u44b2\u44b3\u44b4\u44b5\u44b6\u44b7\u44b8\u44b9\u44ba\u44bb\u44bc\u44bd\u44be\u44bf\u44c0\u44c1\u44c2\u44c3\u44c4\u44c5\u44c6\u44c7\u44c8\u44c9\u44ca\u44cb\u44cc\u44cd\u44ce\u44cf\u44d0\u44d1\u44d2\u44d3\u44d4\u44d5\u44d6\u44d7\u44d8\u44d9\u44da\u44db\u44dc\u44dd\u44de\u44df\u44e0\u44e1\u44e2\u44e3\u44e4\u44e5\u44e6\u44e7\u44e8\u44e9\u44ea\u44eb\u44ec\u44ed\u44ee\u44ef\u44f0\u44f1\u44f2\u44f3\u44f4\u44f5\u44f6\u44f7\u44f8\u44f9\u44fa\u44fb\u44fc\u44fd\u44fe\u44ff\u4500\u4501\u4502\u4503\u4504\u4505\u4506\u4507\u4508\u4509\u450a\u450b\u450c\u450d\u450e\u450f\u4510\u4511\u4512\u4513\u4514\u4515\u4516\u4517\u4518\u4519\u451a\u451b\u451c\u451d\u451e\u451f\u4520\u4521\u4522\u4523\u4524\u4525\u4526\u4527\u4528\u4529\u452a\u452b\u452c\u452d\u452e\u452f\u4530\u4531\u4532\u4533\u4534\u4535\u4536\u4537\u4538\u4539\u453a\u453b\u453c\u453d\u453e\u453f\u4540\u4541\u4542\u4543\u4544\u4545\u4546\u4547\u4548\u4549\u454a\u454b\u454c\u454d\u454e\u454f\u4550\u4551\u4552\u4553\u4554\u4555\u4556\u4557\u4558\u4559\u455a\u455b\u455c\u455d\u455e\u455f\u4560\u4561\u4562\u4563\u4564\u4565\u4566\u4567\u4568\u4569\u456a\u456b\u456c\u456d\u456e\u456f\u4570\u4571\u4572\u4573\u4574\u4575\u4576\u4577\u4578\u4579\u457a\u457b\u457c\u457d\u457e\u457f\u4580\u4581\u4582\u4583\u4584\u4585\u4586\u4587\u4588\u4589\u458a\u458b\u458c\u458d\u458e\u458f\u4590\u4591\u4592\u4593\u4594\u4595\u4596\u4597\u4598\u4599\u459a\u459b\u459c\u459d\u459e\u459f\u45a0\u45a1\u45a2\u45a3\u45a4\u45a5\u45a6\u45a7\u45a8\u45a9\u45aa\u45ab\u45ac\u45ad\u45ae\u45af\u45b0\u45b1\u45b2\u45b3\u45b4\u45b5\u45b6\u45b7\u45b8\u45b9\u45ba\u45bb\u45bc\u45bd\u45be\u45bf\u45c0\u45c1\u45c2\u45c3\u45c4\u45c5\u45c6\u45c7\u45c8\u45c9\u45ca\u45cb\u45cc\u45cd\u45ce\u45cf\u45d0\u45d1\u45d2\u45d3\u45d4\u45d5\u45d6\u45d7\u45d8\u45d9\u45da\u45db\u45dc\u45dd\u45de\u45df\u45e0\u45e1\u45e2\u45e3\u45e4\u45e5\u45e6\u45e7\u45e8\u45e9\u45ea\u45eb\u45ec\u45ed\u45ee\u45ef\u45f0\u45f1\u45f2\u45f3\u45f4\u45f5\u45f6\u45f7\u45f8\u45f9\u45fa\u45fb\u45fc\u45fd\u45fe\u45ff\u4600\u4601\u4602\u4603\u4604\u4605\u4606\u4607\u4608\u4609\u460a\u460b\u460c\u460d\u460e\u460f\u4610\u4611\u4612\u4613\u4614\u4615\u4616\u4617\u4618\u4619\u461a\u461b\u461c\u461d\u461e\u461f\u4620\u4621\u4622\u4623\u4624\u4625\u4626\u4627\u4628\u4629\u462a\u462b\u462c\u462d\u462e\u462f\u4630\u4631\u4632\u4633\u4634\u4635\u4636\u4637\u4638\u4639\u463a\u463b\u463c\u463d\u463e\u463f\u4640\u4641\u4642\u4643\u4644\u4645\u4646\u4647\u4648\u4649\u464a\u464b\u464c\u464d\u464e\u464f\u4650\u4651\u4652\u4653\u4654\u4655\u4656\u4657\u4658\u4659\u465a\u465b\u465c\u465d\u465e\u465f\u4660\u4661\u4662\u4663\u4664\u4665\u4666\u4667\u4668\u4669\u466a\u466b\u466c\u466d\u466e\u466f\u4670\u4671\u4672\u4673\u4674\u4675\u4676\u4677\u4678\u4679\u467a\u467b\u467c\u467d\u467e\u467f\u4680\u4681\u4682\u4683\u4684\u4685\u4686\u4687\u4688\u4689\u468a\u468b\u468c\u468d\u468e\u468f\u4690\u4691\u4692\u4693\u4694\u4695\u4696\u4697\u4698\u4699\u469a\u469b\u469c\u469d\u469e\u469f\u46a0\u46a1\u46a2\u46a3\u46a4\u46a5\u46a6\u46a7\u46a8\u46a9\u46aa\u46ab\u46ac\u46ad\u46ae\u46af\u46b0\u46b1\u46b2\u46b3\u46b4\u46b5\u46b6\u46b7\u46b8\u46b9\u46ba\u46bb\u46bc\u46bd\u46be\u46bf\u46c0\u46c1\u46c2\u46c3\u46c4\u46c5\u46c6\u46c7\u46c8\u46c9\u46ca\u46cb\u46cc\u46cd\u46ce\u46cf\u46d0\u46d1\u46d2\u46d3\u46d4\u46d5\u46d6\u46d7\u46d8\u46d9\u46da\u46db\u46dc\u46dd\u46de\u46df\u46e0\u46e1\u46e2\u46e3\u46e4\u46e5\u46e6\u46e7\u46e8\u46e9\u46ea\u46eb\u46ec\u46ed\u46ee\u46ef\u46f0\u46f1\u46f2\u46f3\u46f4\u46f5\u46f6\u46f7\u46f8\u46f9\u46fa\u46fb\u46fc\u46fd\u46fe\u46ff\u4700\u4701\u4702\u4703\u4704\u4705\u4706\u4707\u4708\u4709\u470a\u470b\u470c\u470d\u470e\u470f\u4710\u4711\u4712\u4713\u4714\u4715\u4716\u4717\u4718\u4719\u471a\u471b\u471c\u471d\u471e\u471f\u4720\u4721\u4722\u4723\u4724\u4725\u4726\u4727\u4728\u4729\u472a\u472b\u472c\u472d\u472e\u472f\u4730\u4731\u4732\u4733\u4734\u4735\u4736\u4737\u4738\u4739\u473a\u473b\u473c\u473d\u473e\u473f\u4740\u4741\u4742\u4743\u4744\u4745\u4746\u4747\u4748\u4749\u474a\u474b\u474c\u474d\u474e\u474f\u4750\u4751\u4752\u4753\u4754\u4755\u4756\u4757\u4758\u4759\u475a\u475b\u475c\u475d\u475e\u475f\u4760\u4761\u4762\u4763\u4764\u4765\u4766\u4767\u4768\u4769\u476a\u476b\u476c\u476d\u476e\u476f\u4770\u4771\u4772\u4773\u4774\u4775\u4776\u4777\u4778\u4779\u477a\u477b\u477c\u477d\u477e\u477f\u4780\u4781\u4782\u4783\u4784\u4785\u4786\u4787\u4788\u4789\u478a\u478b\u478c\u478d\u478e\u478f\u4790\u4791\u4792\u4793\u4794\u4795\u4796\u4797\u4798\u4799\u479a\u479b\u479c\u479d\u479e\u479f\u47a0\u47a1\u47a2\u47a3\u47a4\u47a5\u47a6\u47a7\u47a8\u47a9\u47aa\u47ab\u47ac\u47ad\u47ae\u47af\u47b0\u47b1\u47b2\u47b3\u47b4\u47b5\u47b6\u47b7\u47b8\u47b9\u47ba\u47bb\u47bc\u47bd\u47be\u47bf\u47c0\u47c1\u47c2\u47c3\u47c4\u47c5\u47c6\u47c7\u47c8\u47c9\u47ca\u47cb\u47cc\u47cd\u47ce\u47cf\u47d0\u47d1\u47d2\u47d3\u47d4\u47d5\u47d6\u47d7\u47d8\u47d9\u47da\u47db\u47dc\u47dd\u47de\u47df\u47e0\u47e1\u47e2\u47e3\u47e4\u47e5\u47e6\u47e7\u47e8\u47e9\u47ea\u47eb\u47ec\u47ed\u47ee\u47ef\u47f0\u47f1\u47f2\u47f3\u47f4\u47f5\u47f6\u47f7\u47f8\u47f9\u47fa\u47fb\u47fc\u47fd\u47fe\u47ff\u4800\u4801\u4802\u4803\u4804\u4805\u4806\u4807\u4808\u4809\u480a\u480b\u480c\u480d\u480e\u480f\u4810\u4811\u4812\u4813\u4814\u4815\u4816\u4817\u4818\u4819\u481a\u481b\u481c\u481d\u481e\u481f\u4820\u4821\u4822\u4823\u4824\u4825\u4826\u4827\u4828\u4829\u482a\u482b\u482c\u482d\u482e\u482f\u4830\u4831\u4832\u4833\u4834\u4835\u4836\u4837\u4838\u4839\u483a\u483b\u483c\u483d\u483e\u483f\u4840\u4841\u4842\u4843\u4844\u4845\u4846\u4847\u4848\u4849\u484a\u484b\u484c\u484d\u484e\u484f\u4850\u4851\u4852\u4853\u4854\u4855\u4856\u4857\u4858\u4859\u485a\u485b\u485c\u485d\u485e\u485f\u4860\u4861\u4862\u4863\u4864\u4865\u4866\u4867\u4868\u4869\u486a\u486b\u486c\u486d\u486e\u486f\u4870\u4871\u4872\u4873\u4874\u4875\u4876\u4877\u4878\u4879\u487a\u487b\u487c\u487d\u487e\u487f\u4880\u4881\u4882\u4883\u4884\u4885\u4886\u4887\u4888\u4889\u488a\u488b\u488c\u488d\u488e\u488f\u4890\u4891\u4892\u4893\u4894\u4895\u4896\u4897\u4898\u4899\u489a\u489b\u489c\u489d\u489e\u489f\u48a0\u48a1\u48a2\u48a3\u48a4\u48a5\u48a6\u48a7\u48a8\u48a9\u48aa\u48ab\u48ac\u48ad\u48ae\u48af\u48b0\u48b1\u48b2\u48b3\u48b4\u48b5\u48b6\u48b7\u48b8\u48b9\u48ba\u48bb\u48bc\u48bd\u48be\u48bf\u48c0\u48c1\u48c2\u48c3\u48c4\u48c5\u48c6\u48c7\u48c8\u48c9\u48ca\u48cb\u48cc\u48cd\u48ce\u48cf\u48d0\u48d1\u48d2\u48d3\u48d4\u48d5\u48d6\u48d7\u48d8\u48d9\u48da\u48db\u48dc\u48dd\u48de\u48df\u48e0\u48e1\u48e2\u48e3\u48e4\u48e5\u48e6\u48e7\u48e8\u48e9\u48ea\u48eb\u48ec\u48ed\u48ee\u48ef\u48f0\u48f1\u48f2\u48f3\u48f4\u48f5\u48f6\u48f7\u48f8\u48f9\u48fa\u48fb\u48fc\u48fd\u48fe\u48ff\u4900\u4901\u4902\u4903\u4904\u4905\u4906\u4907\u4908\u4909\u490a\u490b\u490c\u490d\u490e\u490f\u4910\u4911\u4912\u4913\u4914\u4915\u4916\u4917\u4918\u4919\u491a\u491b\u491c\u491d\u491e\u491f\u4920\u4921\u4922\u4923\u4924\u4925\u4926\u4927\u4928\u4929\u492a\u492b\u492c\u492d\u492e\u492f\u4930\u4931\u4932\u4933\u4934\u4935\u4936\u4937\u4938\u4939\u493a\u493b\u493c\u493d\u493e\u493f\u4940\u4941\u4942\u4943\u4944\u4945\u4946\u4947\u4948\u4949\u494a\u494b\u494c\u494d\u494e\u494f\u4950\u4951\u4952\u4953\u4954\u4955\u4956\u4957\u4958\u4959\u495a\u495b\u495c\u495d\u495e\u495f\u4960\u4961\u4962\u4963\u4964\u4965\u4966\u4967\u4968\u4969\u496a\u496b\u496c\u496d\u496e\u496f\u4970\u4971\u4972\u4973\u4974\u4975\u4976\u4977\u4978\u4979\u497a\u497b\u497c\u497d\u497e\u497f\u4980\u4981\u4982\u4983\u4984\u4985\u4986\u4987\u4988\u4989\u498a\u498b\u498c\u498d\u498e\u498f\u4990\u4991\u4992\u4993\u4994\u4995\u4996\u4997\u4998\u4999\u499a\u499b\u499c\u499d\u499e\u499f\u49a0\u49a1\u49a2\u49a3\u49a4\u49a5\u49a6\u49a7\u49a8\u49a9\u49aa\u49ab\u49ac\u49ad\u49ae\u49af\u49b0\u49b1\u49b2\u49b3\u49b4\u49b5\u49b6\u49b7\u49b8\u49b9\u49ba\u49bb\u49bc\u49bd\u49be\u49bf\u49c0\u49c1\u49c2\u49c3\u49c4\u49c5\u49c6\u49c7\u49c8\u49c9\u49ca\u49cb\u49cc\u49cd\u49ce\u49cf\u49d0\u49d1\u49d2\u49d3\u49d4\u49d5\u49d6\u49d7\u49d8\u49d9\u49da\u49db\u49dc\u49dd\u49de\u49df\u49e0\u49e1\u49e2\u49e3\u49e4\u49e5\u49e6\u49e7\u49e8\u49e9\u49ea\u49eb\u49ec\u49ed\u49ee\u49ef\u49f0\u49f1\u49f2\u49f3\u49f4\u49f5\u49f6\u49f7\u49f8\u49f9\u49fa\u49fb\u49fc\u49fd\u49fe\u49ff\u4a00\u4a01\u4a02\u4a03\u4a04\u4a05\u4a06\u4a07\u4a08\u4a09\u4a0a\u4a0b\u4a0c\u4a0d\u4a0e\u4a0f\u4a10\u4a11\u4a12\u4a13\u4a14\u4a15\u4a16\u4a17\u4a18\u4a19\u4a1a\u4a1b\u4a1c\u4a1d\u4a1e\u4a1f\u4a20\u4a21\u4a22\u4a23\u4a24\u4a25\u4a26\u4a27\u4a28\u4a29\u4a2a\u4a2b\u4a2c\u4a2d\u4a2e\u4a2f\u4a30\u4a31\u4a32\u4a33\u4a34\u4a35\u4a36\u4a37\u4a38\u4a39\u4a3a\u4a3b\u4a3c\u4a3d\u4a3e\u4a3f\u4a40\u4a41\u4a42\u4a43\u4a44\u4a45\u4a46\u4a47\u4a48\u4a49\u4a4a\u4a4b\u4a4c\u4a4d\u4a4e\u4a4f\u4a50\u4a51\u4a52\u4a53\u4a54\u4a55\u4a56\u4a57\u4a58\u4a59\u4a5a\u4a5b\u4a5c\u4a5d\u4a5e\u4a5f\u4a60\u4a61\u4a62\u4a63\u4a64\u4a65\u4a66\u4a67\u4a68\u4a69\u4a6a\u4a6b\u4a6c\u4a6d\u4a6e\u4a6f\u4a70\u4a71\u4a72\u4a73\u4a74\u4a75\u4a76\u4a77\u4a78\u4a79\u4a7a\u4a7b\u4a7c\u4a7d\u4a7e\u4a7f\u4a80\u4a81\u4a82\u4a83\u4a84\u4a85\u4a86\u4a87\u4a88\u4a89\u4a8a\u4a8b\u4a8c\u4a8d\u4a8e\u4a8f\u4a90\u4a91\u4a92\u4a93\u4a94\u4a95\u4a96\u4a97\u4a98\u4a99\u4a9a\u4a9b\u4a9c\u4a9d\u4a9e\u4a9f\u4aa0\u4aa1\u4aa2\u4aa3\u4aa4\u4aa5\u4aa6\u4aa7\u4aa8\u4aa9\u4aaa\u4aab\u4aac\u4aad\u4aae\u4aaf\u4ab0\u4ab1\u4ab2\u4ab3\u4ab4\u4ab5\u4ab6\u4ab7\u4ab8\u4ab9\u4aba\u4abb\u4abc\u4abd\u4abe\u4abf\u4ac0\u4ac1\u4ac2\u4ac3\u4ac4\u4ac5\u4ac6\u4ac7\u4ac8\u4ac9\u4aca\u4acb\u4acc\u4acd\u4ace\u4acf\u4ad0\u4ad1\u4ad2\u4ad3\u4ad4\u4ad5\u4ad6\u4ad7\u4ad8\u4ad9\u4ada\u4adb\u4adc\u4add\u4ade\u4adf\u4ae0\u4ae1\u4ae2\u4ae3\u4ae4\u4ae5\u4ae6\u4ae7\u4ae8\u4ae9\u4aea\u4aeb\u4aec\u4aed\u4aee\u4aef\u4af0\u4af1\u4af2\u4af3\u4af4\u4af5\u4af6\u4af7\u4af8\u4af9\u4afa\u4afb\u4afc\u4afd\u4afe\u4aff\u4b00\u4b01\u4b02\u4b03\u4b04\u4b05\u4b06\u4b07\u4b08\u4b09\u4b0a\u4b0b\u4b0c\u4b0d\u4b0e\u4b0f\u4b10\u4b11\u4b12\u4b13\u4b14\u4b15\u4b16\u4b17\u4b18\u4b19\u4b1a\u4b1b\u4b1c\u4b1d\u4b1e\u4b1f\u4b20\u4b21\u4b22\u4b23\u4b24\u4b25\u4b26\u4b27\u4b28\u4b29\u4b2a\u4b2b\u4b2c\u4b2d\u4b2e\u4b2f\u4b30\u4b31\u4b32\u4b33\u4b34\u4b35\u4b36\u4b37\u4b38\u4b39\u4b3a\u4b3b\u4b3c\u4b3d\u4b3e\u4b3f\u4b40\u4b41\u4b42\u4b43\u4b44\u4b45\u4b46\u4b47\u4b48\u4b49\u4b4a\u4b4b\u4b4c\u4b4d\u4b4e\u4b4f\u4b50\u4b51\u4b52\u4b53\u4b54\u4b55\u4b56\u4b57\u4b58\u4b59\u4b5a\u4b5b\u4b5c\u4b5d\u4b5e\u4b5f\u4b60\u4b61\u4b62\u4b63\u4b64\u4b65\u4b66\u4b67\u4b68\u4b69\u4b6a\u4b6b\u4b6c\u4b6d\u4b6e\u4b6f\u4b70\u4b71\u4b72\u4b73\u4b74\u4b75\u4b76\u4b77\u4b78\u4b79\u4b7a\u4b7b\u4b7c\u4b7d\u4b7e\u4b7f\u4b80\u4b81\u4b82\u4b83\u4b84\u4b85\u4b86\u4b87\u4b88\u4b89\u4b8a\u4b8b\u4b8c\u4b8d\u4b8e\u4b8f\u4b90\u4b91\u4b92\u4b93\u4b94\u4b95\u4b96\u4b97\u4b98\u4b99\u4b9a\u4b9b\u4b9c\u4b9d\u4b9e\u4b9f\u4ba0\u4ba1\u4ba2\u4ba3\u4ba4\u4ba5\u4ba6\u4ba7\u4ba8\u4ba9\u4baa\u4bab\u4bac\u4bad\u4bae\u4baf\u4bb0\u4bb1\u4bb2\u4bb3\u4bb4\u4bb5\u4bb6\u4bb7\u4bb8\u4bb9\u4bba\u4bbb\u4bbc\u4bbd\u4bbe\u4bbf\u4bc0\u4bc1\u4bc2\u4bc3\u4bc4\u4bc5\u4bc6\u4bc7\u4bc8\u4bc9\u4bca\u4bcb\u4bcc\u4bcd\u4bce\u4bcf\u4bd0\u4bd1\u4bd2\u4bd3\u4bd4\u4bd5\u4bd6\u4bd7\u4bd8\u4bd9\u4bda\u4bdb\u4bdc\u4bdd\u4bde\u4bdf\u4be0\u4be1\u4be2\u4be3\u4be4\u4be5\u4be6\u4be7\u4be8\u4be9\u4bea\u4beb\u4bec\u4bed\u4bee\u4bef\u4bf0\u4bf1\u4bf2\u4bf3\u4bf4\u4bf5\u4bf6\u4bf7\u4bf8\u4bf9\u4bfa\u4bfb\u4bfc\u4bfd\u4bfe\u4bff\u4c00\u4c01\u4c02\u4c03\u4c04\u4c05\u4c06\u4c07\u4c08\u4c09\u4c0a\u4c0b\u4c0c\u4c0d\u4c0e\u4c0f\u4c10\u4c11\u4c12\u4c13\u4c14\u4c15\u4c16\u4c17\u4c18\u4c19\u4c1a\u4c1b\u4c1c\u4c1d\u4c1e\u4c1f\u4c20\u4c21\u4c22\u4c23\u4c24\u4c25\u4c26\u4c27\u4c28\u4c29\u4c2a\u4c2b\u4c2c\u4c2d\u4c2e\u4c2f\u4c30\u4c31\u4c32\u4c33\u4c34\u4c35\u4c36\u4c37\u4c38\u4c39\u4c3a\u4c3b\u4c3c\u4c3d\u4c3e\u4c3f\u4c40\u4c41\u4c42\u4c43\u4c44\u4c45\u4c46\u4c47\u4c48\u4c49\u4c4a\u4c4b\u4c4c\u4c4d\u4c4e\u4c4f\u4c50\u4c51\u4c52\u4c53\u4c54\u4c55\u4c56\u4c57\u4c58\u4c59\u4c5a\u4c5b\u4c5c\u4c5d\u4c5e\u4c5f\u4c60\u4c61\u4c62\u4c63\u4c64\u4c65\u4c66\u4c67\u4c68\u4c69\u4c6a\u4c6b\u4c6c\u4c6d\u4c6e\u4c6f\u4c70\u4c71\u4c72\u4c73\u4c74\u4c75\u4c76\u4c77\u4c78\u4c79\u4c7a\u4c7b\u4c7c\u4c7d\u4c7e\u4c7f\u4c80\u4c81\u4c82\u4c83\u4c84\u4c85\u4c86\u4c87\u4c88\u4c89\u4c8a\u4c8b\u4c8c\u4c8d\u4c8e\u4c8f\u4c90\u4c91\u4c92\u4c93\u4c94\u4c95\u4c96\u4c97\u4c98\u4c99\u4c9a\u4c9b\u4c9c\u4c9d\u4c9e\u4c9f\u4ca0\u4ca1\u4ca2\u4ca3\u4ca4\u4ca5\u4ca6\u4ca7\u4ca8\u4ca9\u4caa\u4cab\u4cac\u4cad\u4cae\u4caf\u4cb0\u4cb1\u4cb2\u4cb3\u4cb4\u4cb5\u4cb6\u4cb7\u4cb8\u4cb9\u4cba\u4cbb\u4cbc\u4cbd\u4cbe\u4cbf\u4cc0\u4cc1\u4cc2\u4cc3\u4cc4\u4cc5\u4cc6\u4cc7\u4cc8\u4cc9\u4cca\u4ccb\u4ccc\u4ccd\u4cce\u4ccf\u4cd0\u4cd1\u4cd2\u4cd3\u4cd4\u4cd5\u4cd6\u4cd7\u4cd8\u4cd9\u4cda\u4cdb\u4cdc\u4cdd\u4cde\u4cdf\u4ce0\u4ce1\u4ce2\u4ce3\u4ce4\u4ce5\u4ce6\u4ce7\u4ce8\u4ce9\u4cea\u4ceb\u4cec\u4ced\u4cee\u4cef\u4cf0\u4cf1\u4cf2\u4cf3\u4cf4\u4cf5\u4cf6\u4cf7\u4cf8\u4cf9\u4cfa\u4cfb\u4cfc\u4cfd\u4cfe\u4cff\u4d00\u4d01\u4d02\u4d03\u4d04\u4d05\u4d06\u4d07\u4d08\u4d09\u4d0a\u4d0b\u4d0c\u4d0d\u4d0e\u4d0f\u4d10\u4d11\u4d12\u4d13\u4d14\u4d15\u4d16\u4d17\u4d18\u4d19\u4d1a\u4d1b\u4d1c\u4d1d\u4d1e\u4d1f\u4d20\u4d21\u4d22\u4d23\u4d24\u4d25\u4d26\u4d27\u4d28\u4d29\u4d2a\u4d2b\u4d2c\u4d2d\u4d2e\u4d2f\u4d30\u4d31\u4d32\u4d33\u4d34\u4d35\u4d36\u4d37\u4d38\u4d39\u4d3a\u4d3b\u4d3c\u4d3d\u4d3e\u4d3f\u4d40\u4d41\u4d42\u4d43\u4d44\u4d45\u4d46\u4d47\u4d48\u4d49\u4d4a\u4d4b\u4d4c\u4d4d\u4d4e\u4d4f\u4d50\u4d51\u4d52\u4d53\u4d54\u4d55\u4d56\u4d57\u4d58\u4d59\u4d5a\u4d5b\u4d5c\u4d5d\u4d5e\u4d5f\u4d60\u4d61\u4d62\u4d63\u4d64\u4d65\u4d66\u4d67\u4d68\u4d69\u4d6a\u4d6b\u4d6c\u4d6d\u4d6e\u4d6f\u4d70\u4d71\u4d72\u4d73\u4d74\u4d75\u4d76\u4d77\u4d78\u4d79\u4d7a\u4d7b\u4d7c\u4d7d\u4d7e\u4d7f\u4d80\u4d81\u4d82\u4d83\u4d84\u4d85\u4d86\u4d87\u4d88\u4d89\u4d8a\u4d8b\u4d8c\u4d8d\u4d8e\u4d8f\u4d90\u4d91\u4d92\u4d93\u4d94\u4d95\u4d96\u4d97\u4d98\u4d99\u4d9a\u4d9b\u4d9c\u4d9d\u4d9e\u4d9f\u4da0\u4da1\u4da2\u4da3\u4da4\u4da5\u4da6\u4da7\u4da8\u4da9\u4daa\u4dab\u4dac\u4dad\u4dae\u4daf\u4db0\u4db1\u4db2\u4db3\u4db4\u4db5\u4e00\u4e01\u4e02\u4e03\u4e04\u4e05\u4e06\u4e07\u4e08\u4e09\u4e0a\u4e0b\u4e0c\u4e0d\u4e0e\u4e0f\u4e10\u4e11\u4e12\u4e13\u4e14\u4e15\u4e16\u4e17\u4e18\u4e19\u4e1a\u4e1b\u4e1c\u4e1d\u4e1e\u4e1f\u4e20\u4e21\u4e22\u4e23\u4e24\u4e25\u4e26\u4e27\u4e28\u4e29\u4e2a\u4e2b\u4e2c\u4e2d\u4e2e\u4e2f\u4e30\u4e31\u4e32\u4e33\u4e34\u4e35\u4e36\u4e37\u4e38\u4e39\u4e3a\u4e3b\u4e3c\u4e3d\u4e3e\u4e3f\u4e40\u4e41\u4e42\u4e43\u4e44\u4e45\u4e46\u4e47\u4e48\u4e49\u4e4a\u4e4b\u4e4c\u4e4d\u4e4e\u4e4f\u4e50\u4e51\u4e52\u4e53\u4e54\u4e55\u4e56\u4e57\u4e58\u4e59\u4e5a\u4e5b\u4e5c\u4e5d\u4e5e\u4e5f\u4e60\u4e61\u4e62\u4e63\u4e64\u4e65\u4e66\u4e67\u4e68\u4e69\u4e6a\u4e6b\u4e6c\u4e6d\u4e6e\u4e6f\u4e70\u4e71\u4e72\u4e73\u4e74\u4e75\u4e76\u4e77\u4e78\u4e79\u4e7a\u4e7b\u4e7c\u4e7d\u4e7e\u4e7f\u4e80\u4e81\u4e82\u4e83\u4e84\u4e85\u4e86\u4e87\u4e88\u4e89\u4e8a\u4e8b\u4e8c\u4e8d\u4e8e\u4e8f\u4e90\u4e91\u4e92\u4e93\u4e94\u4e95\u4e96\u4e97\u4e98\u4e99\u4e9a\u4e9b\u4e9c\u4e9d\u4e9e\u4e9f\u4ea0\u4ea1\u4ea2\u4ea3\u4ea4\u4ea5\u4ea6\u4ea7\u4ea8\u4ea9\u4eaa\u4eab\u4eac\u4ead\u4eae\u4eaf\u4eb0\u4eb1\u4eb2\u4eb3\u4eb4\u4eb5\u4eb6\u4eb7\u4eb8\u4eb9\u4eba\u4ebb\u4ebc\u4ebd\u4ebe\u4ebf\u4ec0\u4ec1\u4ec2\u4ec3\u4ec4\u4ec5\u4ec6\u4ec7\u4ec8\u4ec9\u4eca\u4ecb\u4ecc\u4ecd\u4ece\u4ecf\u4ed0\u4ed1\u4ed2\u4ed3\u4ed4\u4ed5\u4ed6\u4ed7\u4ed8\u4ed9\u4eda\u4edb\u4edc\u4edd\u4ede\u4edf\u4ee0\u4ee1\u4ee2\u4ee3\u4ee4\u4ee5\u4ee6\u4ee7\u4ee8\u4ee9\u4eea\u4eeb\u4eec\u4eed\u4eee\u4eef\u4ef0\u4ef1\u4ef2\u4ef3\u4ef4\u4ef5\u4ef6\u4ef7\u4ef8\u4ef9\u4efa\u4efb\u4efc\u4efd\u4efe\u4eff\u4f00\u4f01\u4f02\u4f03\u4f04\u4f05\u4f06\u4f07\u4f08\u4f09\u4f0a\u4f0b\u4f0c\u4f0d\u4f0e\u4f0f\u4f10\u4f11\u4f12\u4f13\u4f14\u4f15\u4f16\u4f17\u4f18\u4f19\u4f1a\u4f1b\u4f1c\u4f1d\u4f1e\u4f1f\u4f20\u4f21\u4f22\u4f23\u4f24\u4f25\u4f26\u4f27\u4f28\u4f29\u4f2a\u4f2b\u4f2c\u4f2d\u4f2e\u4f2f\u4f30\u4f31\u4f32\u4f33\u4f34\u4f35\u4f36\u4f37\u4f38\u4f39\u4f3a\u4f3b\u4f3c\u4f3d\u4f3e\u4f3f\u4f40\u4f41\u4f42\u4f43\u4f44\u4f45\u4f46\u4f47\u4f48\u4f49\u4f4a\u4f4b\u4f4c\u4f4d\u4f4e\u4f4f\u4f50\u4f51\u4f52\u4f53\u4f54\u4f55\u4f56\u4f57\u4f58\u4f59\u4f5a\u4f5b\u4f5c\u4f5d\u4f5e\u4f5f\u4f60\u4f61\u4f62\u4f63\u4f64\u4f65\u4f66\u4f67\u4f68\u4f69\u4f6a\u4f6b\u4f6c\u4f6d\u4f6e\u4f6f\u4f70\u4f71\u4f72\u4f73\u4f74\u4f75\u4f76\u4f77\u4f78\u4f79\u4f7a\u4f7b\u4f7c\u4f7d\u4f7e\u4f7f\u4f80\u4f81\u4f82\u4f83\u4f84\u4f85\u4f86\u4f87\u4f88\u4f89\u4f8a\u4f8b\u4f8c\u4f8d\u4f8e\u4f8f\u4f90\u4f91\u4f92\u4f93\u4f94\u4f95\u4f96\u4f97\u4f98\u4f99\u4f9a\u4f9b\u4f9c\u4f9d\u4f9e\u4f9f\u4fa0\u4fa1\u4fa2\u4fa3\u4fa4\u4fa5\u4fa6\u4fa7\u4fa8\u4fa9\u4faa\u4fab\u4fac\u4fad\u4fae\u4faf\u4fb0\u4fb1\u4fb2\u4fb3\u4fb4\u4fb5\u4fb6\u4fb7\u4fb8\u4fb9\u4fba\u4fbb\u4fbc\u4fbd\u4fbe\u4fbf\u4fc0\u4fc1\u4fc2\u4fc3\u4fc4\u4fc5\u4fc6\u4fc7\u4fc8\u4fc9\u4fca\u4fcb\u4fcc\u4fcd\u4fce\u4fcf\u4fd0\u4fd1\u4fd2\u4fd3\u4fd4\u4fd5\u4fd6\u4fd7\u4fd8\u4fd9\u4fda\u4fdb\u4fdc\u4fdd\u4fde\u4fdf\u4fe0\u4fe1\u4fe2\u4fe3\u4fe4\u4fe5\u4fe6\u4fe7\u4fe8\u4fe9\u4fea\u4feb\u4fec\u4fed\u4fee\u4fef\u4ff0\u4ff1\u4ff2\u4ff3\u4ff4\u4ff5\u4ff6\u4ff7\u4ff8\u4ff9\u4ffa\u4ffb\u4ffc\u4ffd\u4ffe\u4fff\u5000\u5001\u5002\u5003\u5004\u5005\u5006\u5007\u5008\u5009\u500a\u500b\u500c\u500d\u500e\u500f\u5010\u5011\u5012\u5013\u5014\u5015\u5016\u5017\u5018\u5019\u501a\u501b\u501c\u501d\u501e\u501f\u5020\u5021\u5022\u5023\u5024\u5025\u5026\u5027\u5028\u5029\u502a\u502b\u502c\u502d\u502e\u502f\u5030\u5031\u5032\u5033\u5034\u5035\u5036\u5037\u5038\u5039\u503a\u503b\u503c\u503d\u503e\u503f\u5040\u5041\u5042\u5043\u5044\u5045\u5046\u5047\u5048\u5049\u504a\u504b\u504c\u504d\u504e\u504f\u5050\u5051\u5052\u5053\u5054\u5055\u5056\u5057\u5058\u5059\u505a\u505b\u505c\u505d\u505e\u505f\u5060\u5061\u5062\u5063\u5064\u5065\u5066\u5067\u5068\u5069\u506a\u506b\u506c\u506d\u506e\u506f\u5070\u5071\u5072\u5073\u5074\u5075\u5076\u5077\u5078\u5079\u507a\u507b\u507c\u507d\u507e\u507f\u5080\u5081\u5082\u5083\u5084\u5085\u5086\u5087\u5088\u5089\u508a\u508b\u508c\u508d\u508e\u508f\u5090\u5091\u5092\u5093\u5094\u5095\u5096\u5097\u5098\u5099\u509a\u509b\u509c\u509d\u509e\u509f\u50a0\u50a1\u50a2\u50a3\u50a4\u50a5\u50a6\u50a7\u50a8\u50a9\u50aa\u50ab\u50ac\u50ad\u50ae\u50af\u50b0\u50b1\u50b2\u50b3\u50b4\u50b5\u50b6\u50b7\u50b8\u50b9\u50ba\u50bb\u50bc\u50bd\u50be\u50bf\u50c0\u50c1\u50c2\u50c3\u50c4\u50c5\u50c6\u50c7\u50c8\u50c9\u50ca\u50cb\u50cc\u50cd\u50ce\u50cf\u50d0\u50d1\u50d2\u50d3\u50d4\u50d5\u50d6\u50d7\u50d8\u50d9\u50da\u50db\u50dc\u50dd\u50de\u50df\u50e0\u50e1\u50e2\u50e3\u50e4\u50e5\u50e6\u50e7\u50e8\u50e9\u50ea\u50eb\u50ec\u50ed\u50ee\u50ef\u50f0\u50f1\u50f2\u50f3\u50f4\u50f5\u50f6\u50f7\u50f8\u50f9\u50fa\u50fb\u50fc\u50fd\u50fe\u50ff\u5100\u5101\u5102\u5103\u5104\u5105\u5106\u5107\u5108\u5109\u510a\u510b\u510c\u510d\u510e\u510f\u5110\u5111\u5112\u5113\u5114\u5115\u5116\u5117\u5118\u5119\u511a\u511b\u511c\u511d\u511e\u511f\u5120\u5121\u5122\u5123\u5124\u5125\u5126\u5127\u5128\u5129\u512a\u512b\u512c\u512d\u512e\u512f\u5130\u5131\u5132\u5133\u5134\u5135\u5136\u5137\u5138\u5139\u513a\u513b\u513c\u513d\u513e\u513f\u5140\u5141\u5142\u5143\u5144\u5145\u5146\u5147\u5148\u5149\u514a\u514b\u514c\u514d\u514e\u514f\u5150\u5151\u5152\u5153\u5154\u5155\u5156\u5157\u5158\u5159\u515a\u515b\u515c\u515d\u515e\u515f\u5160\u5161\u5162\u5163\u5164\u5165\u5166\u5167\u5168\u5169\u516a\u516b\u516c\u516d\u516e\u516f\u5170\u5171\u5172\u5173\u5174\u5175\u5176\u5177\u5178\u5179\u517a\u517b\u517c\u517d\u517e\u517f\u5180\u5181\u5182\u5183\u5184\u5185\u5186\u5187\u5188\u5189\u518a\u518b\u518c\u518d\u518e\u518f\u5190\u5191\u5192\u5193\u5194\u5195\u5196\u5197\u5198\u5199\u519a\u519b\u519c\u519d\u519e\u519f\u51a0\u51a1\u51a2\u51a3\u51a4\u51a5\u51a6\u51a7\u51a8\u51a9\u51aa\u51ab\u51ac\u51ad\u51ae\u51af\u51b0\u51b1\u51b2\u51b3\u51b4\u51b5\u51b6\u51b7\u51b8\u51b9\u51ba\u51bb\u51bc\u51bd\u51be\u51bf\u51c0\u51c1\u51c2\u51c3\u51c4\u51c5\u51c6\u51c7\u51c8\u51c9\u51ca\u51cb\u51cc\u51cd\u51ce\u51cf\u51d0\u51d1\u51d2\u51d3\u51d4\u51d5\u51d6\u51d7\u51d8\u51d9\u51da\u51db\u51dc\u51dd\u51de\u51df\u51e0\u51e1\u51e2\u51e3\u51e4\u51e5\u51e6\u51e7\u51e8\u51e9\u51ea\u51eb\u51ec\u51ed\u51ee\u51ef\u51f0\u51f1\u51f2\u51f3\u51f4\u51f5\u51f6\u51f7\u51f8\u51f9\u51fa\u51fb\u51fc\u51fd\u51fe\u51ff\u5200\u5201\u5202\u5203\u5204\u5205\u5206\u5207\u5208\u5209\u520a\u520b\u520c\u520d\u520e\u520f\u5210\u5211\u5212\u5213\u5214\u5215\u5216\u5217\u5218\u5219\u521a\u521b\u521c\u521d\u521e\u521f\u5220\u5221\u5222\u5223\u5224\u5225\u5226\u5227\u5228\u5229\u522a\u522b\u522c\u522d\u522e\u522f\u5230\u5231\u5232\u5233\u5234\u5235\u5236\u5237\u5238\u5239\u523a\u523b\u523c\u523d\u523e\u523f\u5240\u5241\u5242\u5243\u5244\u5245\u5246\u5247\u5248\u5249\u524a\u524b\u524c\u524d\u524e\u524f\u5250\u5251\u5252\u5253\u5254\u5255\u5256\u5257\u5258\u5259\u525a\u525b\u525c\u525d\u525e\u525f\u5260\u5261\u5262\u5263\u5264\u5265\u5266\u5267\u5268\u5269\u526a\u526b\u526c\u526d\u526e\u526f\u5270\u5271\u5272\u5273\u5274\u5275\u5276\u5277\u5278\u5279\u527a\u527b\u527c\u527d\u527e\u527f\u5280\u5281\u5282\u5283\u5284\u5285\u5286\u5287\u5288\u5289\u528a\u528b\u528c\u528d\u528e\u528f\u5290\u5291\u5292\u5293\u5294\u5295\u5296\u5297\u5298\u5299\u529a\u529b\u529c\u529d\u529e\u529f\u52a0\u52a1\u52a2\u52a3\u52a4\u52a5\u52a6\u52a7\u52a8\u52a9\u52aa\u52ab\u52ac\u52ad\u52ae\u52af\u52b0\u52b1\u52b2\u52b3\u52b4\u52b5\u52b6\u52b7\u52b8\u52b9\u52ba\u52bb\u52bc\u52bd\u52be\u52bf\u52c0\u52c1\u52c2\u52c3\u52c4\u52c5\u52c6\u52c7\u52c8\u52c9\u52ca\u52cb\u52cc\u52cd\u52ce\u52cf\u52d0\u52d1\u52d2\u52d3\u52d4\u52d5\u52d6\u52d7\u52d8\u52d9\u52da\u52db\u52dc\u52dd\u52de\u52df\u52e0\u52e1\u52e2\u52e3\u52e4\u52e5\u52e6\u52e7\u52e8\u52e9\u52ea\u52eb\u52ec\u52ed\u52ee\u52ef\u52f0\u52f1\u52f2\u52f3\u52f4\u52f5\u52f6\u52f7\u52f8\u52f9\u52fa\u52fb\u52fc\u52fd\u52fe\u52ff\u5300\u5301\u5302\u5303\u5304\u5305\u5306\u5307\u5308\u5309\u530a\u530b\u530c\u530d\u530e\u530f\u5310\u5311\u5312\u5313\u5314\u5315\u5316\u5317\u5318\u5319\u531a\u531b\u531c\u531d\u531e\u531f\u5320\u5321\u5322\u5323\u5324\u5325\u5326\u5327\u5328\u5329\u532a\u532b\u532c\u532d\u532e\u532f\u5330\u5331\u5332\u5333\u5334\u5335\u5336\u5337\u5338\u5339\u533a\u533b\u533c\u533d\u533e\u533f\u5340\u5341\u5342\u5343\u5344\u5345\u5346\u5347\u5348\u5349\u534a\u534b\u534c\u534d\u534e\u534f\u5350\u5351\u5352\u5353\u5354\u5355\u5356\u5357\u5358\u5359\u535a\u535b\u535c\u535d\u535e\u535f\u5360\u5361\u5362\u5363\u5364\u5365\u5366\u5367\u5368\u5369\u536a\u536b\u536c\u536d\u536e\u536f\u5370\u5371\u5372\u5373\u5374\u5375\u5376\u5377\u5378\u5379\u537a\u537b\u537c\u537d\u537e\u537f\u5380\u5381\u5382\u5383\u5384\u5385\u5386\u5387\u5388\u5389\u538a\u538b\u538c\u538d\u538e\u538f\u5390\u5391\u5392\u5393\u5394\u5395\u5396\u5397\u5398\u5399\u539a\u539b\u539c\u539d\u539e\u539f\u53a0\u53a1\u53a2\u53a3\u53a4\u53a5\u53a6\u53a7\u53a8\u53a9\u53aa\u53ab\u53ac\u53ad\u53ae\u53af\u53b0\u53b1\u53b2\u53b3\u53b4\u53b5\u53b6\u53b7\u53b8\u53b9\u53ba\u53bb\u53bc\u53bd\u53be\u53bf\u53c0\u53c1\u53c2\u53c3\u53c4\u53c5\u53c6\u53c7\u53c8\u53c9\u53ca\u53cb\u53cc\u53cd\u53ce\u53cf\u53d0\u53d1\u53d2\u53d3\u53d4\u53d5\u53d6\u53d7\u53d8\u53d9\u53da\u53db\u53dc\u53dd\u53de\u53df\u53e0\u53e1\u53e2\u53e3\u53e4\u53e5\u53e6\u53e7\u53e8\u53e9\u53ea\u53eb\u53ec\u53ed\u53ee\u53ef\u53f0\u53f1\u53f2\u53f3\u53f4\u53f5\u53f6\u53f7\u53f8\u53f9\u53fa\u53fb\u53fc\u53fd\u53fe\u53ff\u5400\u5401\u5402\u5403\u5404\u5405\u5406\u5407\u5408\u5409\u540a\u540b\u540c\u540d\u540e\u540f\u5410\u5411\u5412\u5413\u5414\u5415\u5416\u5417\u5418\u5419\u541a\u541b\u541c\u541d\u541e\u541f\u5420\u5421\u5422\u5423\u5424\u5425\u5426\u5427\u5428\u5429\u542a\u542b\u542c\u542d\u542e\u542f\u5430\u5431\u5432\u5433\u5434\u5435\u5436\u5437\u5438\u5439\u543a\u543b\u543c\u543d\u543e\u543f\u5440\u5441\u5442\u5443\u5444\u5445\u5446\u5447\u5448\u5449\u544a\u544b\u544c\u544d\u544e\u544f\u5450\u5451\u5452\u5453\u5454\u5455\u5456\u5457\u5458\u5459\u545a\u545b\u545c\u545d\u545e\u545f\u5460\u5461\u5462\u5463\u5464\u5465\u5466\u5467\u5468\u5469\u546a\u546b\u546c\u546d\u546e\u546f\u5470\u5471\u5472\u5473\u5474\u5475\u5476\u5477\u5478\u5479\u547a\u547b\u547c\u547d\u547e\u547f\u5480\u5481\u5482\u5483\u5484\u5485\u5486\u5487\u5488\u5489\u548a\u548b\u548c\u548d\u548e\u548f\u5490\u5491\u5492\u5493\u5494\u5495\u5496\u5497\u5498\u5499\u549a\u549b\u549c\u549d\u549e\u549f\u54a0\u54a1\u54a2\u54a3\u54a4\u54a5\u54a6\u54a7\u54a8\u54a9\u54aa\u54ab\u54ac\u54ad\u54ae\u54af\u54b0\u54b1\u54b2\u54b3\u54b4\u54b5\u54b6\u54b7\u54b8\u54b9\u54ba\u54bb\u54bc\u54bd\u54be\u54bf\u54c0\u54c1\u54c2\u54c3\u54c4\u54c5\u54c6\u54c7\u54c8\u54c9\u54ca\u54cb\u54cc\u54cd\u54ce\u54cf\u54d0\u54d1\u54d2\u54d3\u54d4\u54d5\u54d6\u54d7\u54d8\u54d9\u54da\u54db\u54dc\u54dd\u54de\u54df\u54e0\u54e1\u54e2\u54e3\u54e4\u54e5\u54e6\u54e7\u54e8\u54e9\u54ea\u54eb\u54ec\u54ed\u54ee\u54ef\u54f0\u54f1\u54f2\u54f3\u54f4\u54f5\u54f6\u54f7\u54f8\u54f9\u54fa\u54fb\u54fc\u54fd\u54fe\u54ff\u5500\u5501\u5502\u5503\u5504\u5505\u5506\u5507\u5508\u5509\u550a\u550b\u550c\u550d\u550e\u550f\u5510\u5511\u5512\u5513\u5514\u5515\u5516\u5517\u5518\u5519\u551a\u551b\u551c\u551d\u551e\u551f\u5520\u5521\u5522\u5523\u5524\u5525\u5526\u5527\u5528\u5529\u552a\u552b\u552c\u552d\u552e\u552f\u5530\u5531\u5532\u5533\u5534\u5535\u5536\u5537\u5538\u5539\u553a\u553b\u553c\u553d\u553e\u553f\u5540\u5541\u5542\u5543\u5544\u5545\u5546\u5547\u5548\u5549\u554a\u554b\u554c\u554d\u554e\u554f\u5550\u5551\u5552\u5553\u5554\u5555\u5556\u5557\u5558\u5559\u555a\u555b\u555c\u555d\u555e\u555f\u5560\u5561\u5562\u5563\u5564\u5565\u5566\u5567\u5568\u5569\u556a\u556b\u556c\u556d\u556e\u556f\u5570\u5571\u5572\u5573\u5574\u5575\u5576\u5577\u5578\u5579\u557a\u557b\u557c\u557d\u557e\u557f\u5580\u5581\u5582\u5583\u5584\u5585\u5586\u5587\u5588\u5589\u558a\u558b\u558c\u558d\u558e\u558f\u5590\u5591\u5592\u5593\u5594\u5595\u5596\u5597\u5598\u5599\u559a\u559b\u559c\u559d\u559e\u559f\u55a0\u55a1\u55a2\u55a3\u55a4\u55a5\u55a6\u55a7\u55a8\u55a9\u55aa\u55ab\u55ac\u55ad\u55ae\u55af\u55b0\u55b1\u55b2\u55b3\u55b4\u55b5\u55b6\u55b7\u55b8\u55b9\u55ba\u55bb\u55bc\u55bd\u55be\u55bf\u55c0\u55c1\u55c2\u55c3\u55c4\u55c5\u55c6\u55c7\u55c8\u55c9\u55ca\u55cb\u55cc\u55cd\u55ce\u55cf\u55d0\u55d1\u55d2\u55d3\u55d4\u55d5\u55d6\u55d7\u55d8\u55d9\u55da\u55db\u55dc\u55dd\u55de\u55df\u55e0\u55e1\u55e2\u55e3\u55e4\u55e5\u55e6\u55e7\u55e8\u55e9\u55ea\u55eb\u55ec\u55ed\u55ee\u55ef\u55f0\u55f1\u55f2\u55f3\u55f4\u55f5\u55f6\u55f7\u55f8\u55f9\u55fa\u55fb\u55fc\u55fd\u55fe\u55ff\u5600\u5601\u5602\u5603\u5604\u5605\u5606\u5607\u5608\u5609\u560a\u560b\u560c\u560d\u560e\u560f\u5610\u5611\u5612\u5613\u5614\u5615\u5616\u5617\u5618\u5619\u561a\u561b\u561c\u561d\u561e\u561f\u5620\u5621\u5622\u5623\u5624\u5625\u5626\u5627\u5628\u5629\u562a\u562b\u562c\u562d\u562e\u562f\u5630\u5631\u5632\u5633\u5634\u5635\u5636\u5637\u5638\u5639\u563a\u563b\u563c\u563d\u563e\u563f\u5640\u5641\u5642\u5643\u5644\u5645\u5646\u5647\u5648\u5649\u564a\u564b\u564c\u564d\u564e\u564f\u5650\u5651\u5652\u5653\u5654\u5655\u5656\u5657\u5658\u5659\u565a\u565b\u565c\u565d\u565e\u565f\u5660\u5661\u5662\u5663\u5664\u5665\u5666\u5667\u5668\u5669\u566a\u566b\u566c\u566d\u566e\u566f\u5670\u5671\u5672\u5673\u5674\u5675\u5676\u5677\u5678\u5679\u567a\u567b\u567c\u567d\u567e\u567f\u5680\u5681\u5682\u5683\u5684\u5685\u5686\u5687\u5688\u5689\u568a\u568b\u568c\u568d\u568e\u568f\u5690\u5691\u5692\u5693\u5694\u5695\u5696\u5697\u5698\u5699\u569a\u569b\u569c\u569d\u569e\u569f\u56a0\u56a1\u56a2\u56a3\u56a4\u56a5\u56a6\u56a7\u56a8\u56a9\u56aa\u56ab\u56ac\u56ad\u56ae\u56af\u56b0\u56b1\u56b2\u56b3\u56b4\u56b5\u56b6\u56b7\u56b8\u56b9\u56ba\u56bb\u56bc\u56bd\u56be\u56bf\u56c0\u56c1\u56c2\u56c3\u56c4\u56c5\u56c6\u56c7\u56c8\u56c9\u56ca\u56cb\u56cc\u56cd\u56ce\u56cf\u56d0\u56d1\u56d2\u56d3\u56d4\u56d5\u56d6\u56d7\u56d8\u56d9\u56da\u56db\u56dc\u56dd\u56de\u56df\u56e0\u56e1\u56e2\u56e3\u56e4\u56e5\u56e6\u56e7\u56e8\u56e9\u56ea\u56eb\u56ec\u56ed\u56ee\u56ef\u56f0\u56f1\u56f2\u56f3\u56f4\u56f5\u56f6\u56f7\u56f8\u56f9\u56fa\u56fb\u56fc\u56fd\u56fe\u56ff\u5700\u5701\u5702\u5703\u5704\u5705\u5706\u5707\u5708\u5709\u570a\u570b\u570c\u570d\u570e\u570f\u5710\u5711\u5712\u5713\u5714\u5715\u5716\u5717\u5718\u5719\u571a\u571b\u571c\u571d\u571e\u571f\u5720\u5721\u5722\u5723\u5724\u5725\u5726\u5727\u5728\u5729\u572a\u572b\u572c\u572d\u572e\u572f\u5730\u5731\u5732\u5733\u5734\u5735\u5736\u5737\u5738\u5739\u573a\u573b\u573c\u573d\u573e\u573f\u5740\u5741\u5742\u5743\u5744\u5745\u5746\u5747\u5748\u5749\u574a\u574b\u574c\u574d\u574e\u574f\u5750\u5751\u5752\u5753\u5754\u5755\u5756\u5757\u5758\u5759\u575a\u575b\u575c\u575d\u575e\u575f\u5760\u5761\u5762\u5763\u5764\u5765\u5766\u5767\u5768\u5769\u576a\u576b\u576c\u576d\u576e\u576f\u5770\u5771\u5772\u5773\u5774\u5775\u5776\u5777\u5778\u5779\u577a\u577b\u577c\u577d\u577e\u577f\u5780\u5781\u5782\u5783\u5784\u5785\u5786\u5787\u5788\u5789\u578a\u578b\u578c\u578d\u578e\u578f\u5790\u5791\u5792\u5793\u5794\u5795\u5796\u5797\u5798\u5799\u579a\u579b\u579c\u579d\u579e\u579f\u57a0\u57a1\u57a2\u57a3\u57a4\u57a5\u57a6\u57a7\u57a8\u57a9\u57aa\u57ab\u57ac\u57ad\u57ae\u57af\u57b0\u57b1\u57b2\u57b3\u57b4\u57b5\u57b6\u57b7\u57b8\u57b9\u57ba\u57bb\u57bc\u57bd\u57be\u57bf\u57c0\u57c1\u57c2\u57c3\u57c4\u57c5\u57c6\u57c7\u57c8\u57c9\u57ca\u57cb\u57cc\u57cd\u57ce\u57cf\u57d0\u57d1\u57d2\u57d3\u57d4\u57d5\u57d6\u57d7\u57d8\u57d9\u57da\u57db\u57dc\u57dd\u57de\u57df\u57e0\u57e1\u57e2\u57e3\u57e4\u57e5\u57e6\u57e7\u57e8\u57e9\u57ea\u57eb\u57ec\u57ed\u57ee\u57ef\u57f0\u57f1\u57f2\u57f3\u57f4\u57f5\u57f6\u57f7\u57f8\u57f9\u57fa\u57fb\u57fc\u57fd\u57fe\u57ff\u5800\u5801\u5802\u5803\u5804\u5805\u5806\u5807\u5808\u5809\u580a\u580b\u580c\u580d\u580e\u580f\u5810\u5811\u5812\u5813\u5814\u5815\u5816\u5817\u5818\u5819\u581a\u581b\u581c\u581d\u581e\u581f\u5820\u5821\u5822\u5823\u5824\u5825\u5826\u5827\u5828\u5829\u582a\u582b\u582c\u582d\u582e\u582f\u5830\u5831\u5832\u5833\u5834\u5835\u5836\u5837\u5838\u5839\u583a\u583b\u583c\u583d\u583e\u583f\u5840\u5841\u5842\u5843\u5844\u5845\u5846\u5847\u5848\u5849\u584a\u584b\u584c\u584d\u584e\u584f\u5850\u5851\u5852\u5853\u5854\u5855\u5856\u5857\u5858\u5859\u585a\u585b\u585c\u585d\u585e\u585f\u5860\u5861\u5862\u5863\u5864\u5865\u5866\u5867\u5868\u5869\u586a\u586b\u586c\u586d\u586e\u586f\u5870\u5871\u5872\u5873\u5874\u5875\u5876\u5877\u5878\u5879\u587a\u587b\u587c\u587d\u587e\u587f\u5880\u5881\u5882\u5883\u5884\u5885\u5886\u5887\u5888\u5889\u588a\u588b\u588c\u588d\u588e\u588f\u5890\u5891\u5892\u5893\u5894\u5895\u5896\u5897\u5898\u5899\u589a\u589b\u589c\u589d\u589e\u589f\u58a0\u58a1\u58a2\u58a3\u58a4\u58a5\u58a6\u58a7\u58a8\u58a9\u58aa\u58ab\u58ac\u58ad\u58ae\u58af\u58b0\u58b1\u58b2\u58b3\u58b4\u58b5\u58b6\u58b7\u58b8\u58b9\u58ba\u58bb\u58bc\u58bd\u58be\u58bf\u58c0\u58c1\u58c2\u58c3\u58c4\u58c5\u58c6\u58c7\u58c8\u58c9\u58ca\u58cb\u58cc\u58cd\u58ce\u58cf\u58d0\u58d1\u58d2\u58d3\u58d4\u58d5\u58d6\u58d7\u58d8\u58d9\u58da\u58db\u58dc\u58dd\u58de\u58df\u58e0\u58e1\u58e2\u58e3\u58e4\u58e5\u58e6\u58e7\u58e8\u58e9\u58ea\u58eb\u58ec\u58ed\u58ee\u58ef\u58f0\u58f1\u58f2\u58f3\u58f4\u58f5\u58f6\u58f7\u58f8\u58f9\u58fa\u58fb\u58fc\u58fd\u58fe\u58ff\u5900\u5901\u5902\u5903\u5904\u5905\u5906\u5907\u5908\u5909\u590a\u590b\u590c\u590d\u590e\u590f\u5910\u5911\u5912\u5913\u5914\u5915\u5916\u5917\u5918\u5919\u591a\u591b\u591c\u591d\u591e\u591f\u5920\u5921\u5922\u5923\u5924\u5925\u5926\u5927\u5928\u5929\u592a\u592b\u592c\u592d\u592e\u592f\u5930\u5931\u5932\u5933\u5934\u5935\u5936\u5937\u5938\u5939\u593a\u593b\u593c\u593d\u593e\u593f\u5940\u5941\u5942\u5943\u5944\u5945\u5946\u5947\u5948\u5949\u594a\u594b\u594c\u594d\u594e\u594f\u5950\u5951\u5952\u5953\u5954\u5955\u5956\u5957\u5958\u5959\u595a\u595b\u595c\u595d\u595e\u595f\u5960\u5961\u5962\u5963\u5964\u5965\u5966\u5967\u5968\u5969\u596a\u596b\u596c\u596d\u596e\u596f\u5970\u5971\u5972\u5973\u5974\u5975\u5976\u5977\u5978\u5979\u597a\u597b\u597c\u597d\u597e\u597f\u5980\u5981\u5982\u5983\u5984\u5985\u5986\u5987\u5988\u5989\u598a\u598b\u598c\u598d\u598e\u598f\u5990\u5991\u5992\u5993\u5994\u5995\u5996\u5997\u5998\u5999\u599a\u599b\u599c\u599d\u599e\u599f\u59a0\u59a1\u59a2\u59a3\u59a4\u59a5\u59a6\u59a7\u59a8\u59a9\u59aa\u59ab\u59ac\u59ad\u59ae\u59af\u59b0\u59b1\u59b2\u59b3\u59b4\u59b5\u59b6\u59b7\u59b8\u59b9\u59ba\u59bb\u59bc\u59bd\u59be\u59bf\u59c0\u59c1\u59c2\u59c3\u59c4\u59c5\u59c6\u59c7\u59c8\u59c9\u59ca\u59cb\u59cc\u59cd\u59ce\u59cf\u59d0\u59d1\u59d2\u59d3\u59d4\u59d5\u59d6\u59d7\u59d8\u59d9\u59da\u59db\u59dc\u59dd\u59de\u59df\u59e0\u59e1\u59e2\u59e3\u59e4\u59e5\u59e6\u59e7\u59e8\u59e9\u59ea\u59eb\u59ec\u59ed\u59ee\u59ef\u59f0\u59f1\u59f2\u59f3\u59f4\u59f5\u59f6\u59f7\u59f8\u59f9\u59fa\u59fb\u59fc\u59fd\u59fe\u59ff\u5a00\u5a01\u5a02\u5a03\u5a04\u5a05\u5a06\u5a07\u5a08\u5a09\u5a0a\u5a0b\u5a0c\u5a0d\u5a0e\u5a0f\u5a10\u5a11\u5a12\u5a13\u5a14\u5a15\u5a16\u5a17\u5a18\u5a19\u5a1a\u5a1b\u5a1c\u5a1d\u5a1e\u5a1f\u5a20\u5a21\u5a22\u5a23\u5a24\u5a25\u5a26\u5a27\u5a28\u5a29\u5a2a\u5a2b\u5a2c\u5a2d\u5a2e\u5a2f\u5a30\u5a31\u5a32\u5a33\u5a34\u5a35\u5a36\u5a37\u5a38\u5a39\u5a3a\u5a3b\u5a3c\u5a3d\u5a3e\u5a3f\u5a40\u5a41\u5a42\u5a43\u5a44\u5a45\u5a46\u5a47\u5a48\u5a49\u5a4a\u5a4b\u5a4c\u5a4d\u5a4e\u5a4f\u5a50\u5a51\u5a52\u5a53\u5a54\u5a55\u5a56\u5a57\u5a58\u5a59\u5a5a\u5a5b\u5a5c\u5a5d\u5a5e\u5a5f\u5a60\u5a61\u5a62\u5a63\u5a64\u5a65\u5a66\u5a67\u5a68\u5a69\u5a6a\u5a6b\u5a6c\u5a6d\u5a6e\u5a6f\u5a70\u5a71\u5a72\u5a73\u5a74\u5a75\u5a76\u5a77\u5a78\u5a79\u5a7a\u5a7b\u5a7c\u5a7d\u5a7e\u5a7f\u5a80\u5a81\u5a82\u5a83\u5a84\u5a85\u5a86\u5a87\u5a88\u5a89\u5a8a\u5a8b\u5a8c\u5a8d\u5a8e\u5a8f\u5a90\u5a91\u5a92\u5a93\u5a94\u5a95\u5a96\u5a97\u5a98\u5a99\u5a9a\u5a9b\u5a9c\u5a9d\u5a9e\u5a9f\u5aa0\u5aa1\u5aa2\u5aa3\u5aa4\u5aa5\u5aa6\u5aa7\u5aa8\u5aa9\u5aaa\u5aab\u5aac\u5aad\u5aae\u5aaf\u5ab0\u5ab1\u5ab2\u5ab3\u5ab4\u5ab5\u5ab6\u5ab7\u5ab8\u5ab9\u5aba\u5abb\u5abc\u5abd\u5abe\u5abf\u5ac0\u5ac1\u5ac2\u5ac3\u5ac4\u5ac5\u5ac6\u5ac7\u5ac8\u5ac9\u5aca\u5acb\u5acc\u5acd\u5ace\u5acf\u5ad0\u5ad1\u5ad2\u5ad3\u5ad4\u5ad5\u5ad6\u5ad7\u5ad8\u5ad9\u5ada\u5adb\u5adc\u5add\u5ade\u5adf\u5ae0\u5ae1\u5ae2\u5ae3\u5ae4\u5ae5\u5ae6\u5ae7\u5ae8\u5ae9\u5aea\u5aeb\u5aec\u5aed\u5aee\u5aef\u5af0\u5af1\u5af2\u5af3\u5af4\u5af5\u5af6\u5af7\u5af8\u5af9\u5afa\u5afb\u5afc\u5afd\u5afe\u5aff\u5b00\u5b01\u5b02\u5b03\u5b04\u5b05\u5b06\u5b07\u5b08\u5b09\u5b0a\u5b0b\u5b0c\u5b0d\u5b0e\u5b0f\u5b10\u5b11\u5b12\u5b13\u5b14\u5b15\u5b16\u5b17\u5b18\u5b19\u5b1a\u5b1b\u5b1c\u5b1d\u5b1e\u5b1f\u5b20\u5b21\u5b22\u5b23\u5b24\u5b25\u5b26\u5b27\u5b28\u5b29\u5b2a\u5b2b\u5b2c\u5b2d\u5b2e\u5b2f\u5b30\u5b31\u5b32\u5b33\u5b34\u5b35\u5b36\u5b37\u5b38\u5b39\u5b3a\u5b3b\u5b3c\u5b3d\u5b3e\u5b3f\u5b40\u5b41\u5b42\u5b43\u5b44\u5b45\u5b46\u5b47\u5b48\u5b49\u5b4a\u5b4b\u5b4c\u5b4d\u5b4e\u5b4f\u5b50\u5b51\u5b52\u5b53\u5b54\u5b55\u5b56\u5b57\u5b58\u5b59\u5b5a\u5b5b\u5b5c\u5b5d\u5b5e\u5b5f\u5b60\u5b61\u5b62\u5b63\u5b64\u5b65\u5b66\u5b67\u5b68\u5b69\u5b6a\u5b6b\u5b6c\u5b6d\u5b6e\u5b6f\u5b70\u5b71\u5b72\u5b73\u5b74\u5b75\u5b76\u5b77\u5b78\u5b79\u5b7a\u5b7b\u5b7c\u5b7d\u5b7e\u5b7f\u5b80\u5b81\u5b82\u5b83\u5b84\u5b85\u5b86\u5b87\u5b88\u5b89\u5b8a\u5b8b\u5b8c\u5b8d\u5b8e\u5b8f\u5b90\u5b91\u5b92\u5b93\u5b94\u5b95\u5b96\u5b97\u5b98\u5b99\u5b9a\u5b9b\u5b9c\u5b9d\u5b9e\u5b9f\u5ba0\u5ba1\u5ba2\u5ba3\u5ba4\u5ba5\u5ba6\u5ba7\u5ba8\u5ba9\u5baa\u5bab\u5bac\u5bad\u5bae\u5baf\u5bb0\u5bb1\u5bb2\u5bb3\u5bb4\u5bb5\u5bb6\u5bb7\u5bb8\u5bb9\u5bba\u5bbb\u5bbc\u5bbd\u5bbe\u5bbf\u5bc0\u5bc1\u5bc2\u5bc3\u5bc4\u5bc5\u5bc6\u5bc7\u5bc8\u5bc9\u5bca\u5bcb\u5bcc\u5bcd\u5bce\u5bcf\u5bd0\u5bd1\u5bd2\u5bd3\u5bd4\u5bd5\u5bd6\u5bd7\u5bd8\u5bd9\u5bda\u5bdb\u5bdc\u5bdd\u5bde\u5bdf\u5be0\u5be1\u5be2\u5be3\u5be4\u5be5\u5be6\u5be7\u5be8\u5be9\u5bea\u5beb\u5bec\u5bed\u5bee\u5bef\u5bf0\u5bf1\u5bf2\u5bf3\u5bf4\u5bf5\u5bf6\u5bf7\u5bf8\u5bf9\u5bfa\u5bfb\u5bfc\u5bfd\u5bfe\u5bff\u5c00\u5c01\u5c02\u5c03\u5c04\u5c05\u5c06\u5c07\u5c08\u5c09\u5c0a\u5c0b\u5c0c\u5c0d\u5c0e\u5c0f\u5c10\u5c11\u5c12\u5c13\u5c14\u5c15\u5c16\u5c17\u5c18\u5c19\u5c1a\u5c1b\u5c1c\u5c1d\u5c1e\u5c1f\u5c20\u5c21\u5c22\u5c23\u5c24\u5c25\u5c26\u5c27\u5c28\u5c29\u5c2a\u5c2b\u5c2c\u5c2d\u5c2e\u5c2f\u5c30\u5c31\u5c32\u5c33\u5c34\u5c35\u5c36\u5c37\u5c38\u5c39\u5c3a\u5c3b\u5c3c\u5c3d\u5c3e\u5c3f\u5c40\u5c41\u5c42\u5c43\u5c44\u5c45\u5c46\u5c47\u5c48\u5c49\u5c4a\u5c4b\u5c4c\u5c4d\u5c4e\u5c4f\u5c50\u5c51\u5c52\u5c53\u5c54\u5c55\u5c56\u5c57\u5c58\u5c59\u5c5a\u5c5b\u5c5c\u5c5d\u5c5e\u5c5f\u5c60\u5c61\u5c62\u5c63\u5c64\u5c65\u5c66\u5c67\u5c68\u5c69\u5c6a\u5c6b\u5c6c\u5c6d\u5c6e\u5c6f\u5c70\u5c71\u5c72\u5c73\u5c74\u5c75\u5c76\u5c77\u5c78\u5c79\u5c7a\u5c7b\u5c7c\u5c7d\u5c7e\u5c7f\u5c80\u5c81\u5c82\u5c83\u5c84\u5c85\u5c86\u5c87\u5c88\u5c89\u5c8a\u5c8b\u5c8c\u5c8d\u5c8e\u5c8f\u5c90\u5c91\u5c92\u5c93\u5c94\u5c95\u5c96\u5c97\u5c98\u5c99\u5c9a\u5c9b\u5c9c\u5c9d\u5c9e\u5c9f\u5ca0\u5ca1\u5ca2\u5ca3\u5ca4\u5ca5\u5ca6\u5ca7\u5ca8\u5ca9\u5caa\u5cab\u5cac\u5cad\u5cae\u5caf\u5cb0\u5cb1\u5cb2\u5cb3\u5cb4\u5cb5\u5cb6\u5cb7\u5cb8\u5cb9\u5cba\u5cbb\u5cbc\u5cbd\u5cbe\u5cbf\u5cc0\u5cc1\u5cc2\u5cc3\u5cc4\u5cc5\u5cc6\u5cc7\u5cc8\u5cc9\u5cca\u5ccb\u5ccc\u5ccd\u5cce\u5ccf\u5cd0\u5cd1\u5cd2\u5cd3\u5cd4\u5cd5\u5cd6\u5cd7\u5cd8\u5cd9\u5cda\u5cdb\u5cdc\u5cdd\u5cde\u5cdf\u5ce0\u5ce1\u5ce2\u5ce3\u5ce4\u5ce5\u5ce6\u5ce7\u5ce8\u5ce9\u5cea\u5ceb\u5cec\u5ced\u5cee\u5cef\u5cf0\u5cf1\u5cf2\u5cf3\u5cf4\u5cf5\u5cf6\u5cf7\u5cf8\u5cf9\u5cfa\u5cfb\u5cfc\u5cfd\u5cfe\u5cff\u5d00\u5d01\u5d02\u5d03\u5d04\u5d05\u5d06\u5d07\u5d08\u5d09\u5d0a\u5d0b\u5d0c\u5d0d\u5d0e\u5d0f\u5d10\u5d11\u5d12\u5d13\u5d14\u5d15\u5d16\u5d17\u5d18\u5d19\u5d1a\u5d1b\u5d1c\u5d1d\u5d1e\u5d1f\u5d20\u5d21\u5d22\u5d23\u5d24\u5d25\u5d26\u5d27\u5d28\u5d29\u5d2a\u5d2b\u5d2c\u5d2d\u5d2e\u5d2f\u5d30\u5d31\u5d32\u5d33\u5d34\u5d35\u5d36\u5d37\u5d38\u5d39\u5d3a\u5d3b\u5d3c\u5d3d\u5d3e\u5d3f\u5d40\u5d41\u5d42\u5d43\u5d44\u5d45\u5d46\u5d47\u5d48\u5d49\u5d4a\u5d4b\u5d4c\u5d4d\u5d4e\u5d4f\u5d50\u5d51\u5d52\u5d53\u5d54\u5d55\u5d56\u5d57\u5d58\u5d59\u5d5a\u5d5b\u5d5c\u5d5d\u5d5e\u5d5f\u5d60\u5d61\u5d62\u5d63\u5d64\u5d65\u5d66\u5d67\u5d68\u5d69\u5d6a\u5d6b\u5d6c\u5d6d\u5d6e\u5d6f\u5d70\u5d71\u5d72\u5d73\u5d74\u5d75\u5d76\u5d77\u5d78\u5d79\u5d7a\u5d7b\u5d7c\u5d7d\u5d7e\u5d7f\u5d80\u5d81\u5d82\u5d83\u5d84\u5d85\u5d86\u5d87\u5d88\u5d89\u5d8a\u5d8b\u5d8c\u5d8d\u5d8e\u5d8f\u5d90\u5d91\u5d92\u5d93\u5d94\u5d95\u5d96\u5d97\u5d98\u5d99\u5d9a\u5d9b\u5d9c\u5d9d\u5d9e\u5d9f\u5da0\u5da1\u5da2\u5da3\u5da4\u5da5\u5da6\u5da7\u5da8\u5da9\u5daa\u5dab\u5dac\u5dad\u5dae\u5daf\u5db0\u5db1\u5db2\u5db3\u5db4\u5db5\u5db6\u5db7\u5db8\u5db9\u5dba\u5dbb\u5dbc\u5dbd\u5dbe\u5dbf\u5dc0\u5dc1\u5dc2\u5dc3\u5dc4\u5dc5\u5dc6\u5dc7\u5dc8\u5dc9\u5dca\u5dcb\u5dcc\u5dcd\u5dce\u5dcf\u5dd0\u5dd1\u5dd2\u5dd3\u5dd4\u5dd5\u5dd6\u5dd7\u5dd8\u5dd9\u5dda\u5ddb\u5ddc\u5ddd\u5dde\u5ddf\u5de0\u5de1\u5de2\u5de3\u5de4\u5de5\u5de6\u5de7\u5de8\u5de9\u5dea\u5deb\u5dec\u5ded\u5dee\u5def\u5df0\u5df1\u5df2\u5df3\u5df4\u5df5\u5df6\u5df7\u5df8\u5df9\u5dfa\u5dfb\u5dfc\u5dfd\u5dfe\u5dff\u5e00\u5e01\u5e02\u5e03\u5e04\u5e05\u5e06\u5e07\u5e08\u5e09\u5e0a\u5e0b\u5e0c\u5e0d\u5e0e\u5e0f\u5e10\u5e11\u5e12\u5e13\u5e14\u5e15\u5e16\u5e17\u5e18\u5e19\u5e1a\u5e1b\u5e1c\u5e1d\u5e1e\u5e1f\u5e20\u5e21\u5e22\u5e23\u5e24\u5e25\u5e26\u5e27\u5e28\u5e29\u5e2a\u5e2b\u5e2c\u5e2d\u5e2e\u5e2f\u5e30\u5e31\u5e32\u5e33\u5e34\u5e35\u5e36\u5e37\u5e38\u5e39\u5e3a\u5e3b\u5e3c\u5e3d\u5e3e\u5e3f\u5e40\u5e41\u5e42\u5e43\u5e44\u5e45\u5e46\u5e47\u5e48\u5e49\u5e4a\u5e4b\u5e4c\u5e4d\u5e4e\u5e4f\u5e50\u5e51\u5e52\u5e53\u5e54\u5e55\u5e56\u5e57\u5e58\u5e59\u5e5a\u5e5b\u5e5c\u5e5d\u5e5e\u5e5f\u5e60\u5e61\u5e62\u5e63\u5e64\u5e65\u5e66\u5e67\u5e68\u5e69\u5e6a\u5e6b\u5e6c\u5e6d\u5e6e\u5e6f\u5e70\u5e71\u5e72\u5e73\u5e74\u5e75\u5e76\u5e77\u5e78\u5e79\u5e7a\u5e7b\u5e7c\u5e7d\u5e7e\u5e7f\u5e80\u5e81\u5e82\u5e83\u5e84\u5e85\u5e86\u5e87\u5e88\u5e89\u5e8a\u5e8b\u5e8c\u5e8d\u5e8e\u5e8f\u5e90\u5e91\u5e92\u5e93\u5e94\u5e95\u5e96\u5e97\u5e98\u5e99\u5e9a\u5e9b\u5e9c\u5e9d\u5e9e\u5e9f\u5ea0\u5ea1\u5ea2\u5ea3\u5ea4\u5ea5\u5ea6\u5ea7\u5ea8\u5ea9\u5eaa\u5eab\u5eac\u5ead\u5eae\u5eaf\u5eb0\u5eb1\u5eb2\u5eb3\u5eb4\u5eb5\u5eb6\u5eb7\u5eb8\u5eb9\u5eba\u5ebb\u5ebc\u5ebd\u5ebe\u5ebf\u5ec0\u5ec1\u5ec2\u5ec3\u5ec4\u5ec5\u5ec6\u5ec7\u5ec8\u5ec9\u5eca\u5ecb\u5ecc\u5ecd\u5ece\u5ecf\u5ed0\u5ed1\u5ed2\u5ed3\u5ed4\u5ed5\u5ed6\u5ed7\u5ed8\u5ed9\u5eda\u5edb\u5edc\u5edd\u5ede\u5edf\u5ee0\u5ee1\u5ee2\u5ee3\u5ee4\u5ee5\u5ee6\u5ee7\u5ee8\u5ee9\u5eea\u5eeb\u5eec\u5eed\u5eee\u5eef\u5ef0\u5ef1\u5ef2\u5ef3\u5ef4\u5ef5\u5ef6\u5ef7\u5ef8\u5ef9\u5efa\u5efb\u5efc\u5efd\u5efe\u5eff\u5f00\u5f01\u5f02\u5f03\u5f04\u5f05\u5f06\u5f07\u5f08\u5f09\u5f0a\u5f0b\u5f0c\u5f0d\u5f0e\u5f0f\u5f10\u5f11\u5f12\u5f13\u5f14\u5f15\u5f16\u5f17\u5f18\u5f19\u5f1a\u5f1b\u5f1c\u5f1d\u5f1e\u5f1f\u5f20\u5f21\u5f22\u5f23\u5f24\u5f25\u5f26\u5f27\u5f28\u5f29\u5f2a\u5f2b\u5f2c\u5f2d\u5f2e\u5f2f\u5f30\u5f31\u5f32\u5f33\u5f34\u5f35\u5f36\u5f37\u5f38\u5f39\u5f3a\u5f3b\u5f3c\u5f3d\u5f3e\u5f3f\u5f40\u5f41\u5f42\u5f43\u5f44\u5f45\u5f46\u5f47\u5f48\u5f49\u5f4a\u5f4b\u5f4c\u5f4d\u5f4e\u5f4f\u5f50\u5f51\u5f52\u5f53\u5f54\u5f55\u5f56\u5f57\u5f58\u5f59\u5f5a\u5f5b\u5f5c\u5f5d\u5f5e\u5f5f\u5f60\u5f61\u5f62\u5f63\u5f64\u5f65\u5f66\u5f67\u5f68\u5f69\u5f6a\u5f6b\u5f6c\u5f6d\u5f6e\u5f6f\u5f70\u5f71\u5f72\u5f73\u5f74\u5f75\u5f76\u5f77\u5f78\u5f79\u5f7a\u5f7b\u5f7c\u5f7d\u5f7e\u5f7f\u5f80\u5f81\u5f82\u5f83\u5f84\u5f85\u5f86\u5f87\u5f88\u5f89\u5f8a\u5f8b\u5f8c\u5f8d\u5f8e\u5f8f\u5f90\u5f91\u5f92\u5f93\u5f94\u5f95\u5f96\u5f97\u5f98\u5f99\u5f9a\u5f9b\u5f9c\u5f9d\u5f9e\u5f9f\u5fa0\u5fa1\u5fa2\u5fa3\u5fa4\u5fa5\u5fa6\u5fa7\u5fa8\u5fa9\u5faa\u5fab\u5fac\u5fad\u5fae\u5faf\u5fb0\u5fb1\u5fb2\u5fb3\u5fb4\u5fb5\u5fb6\u5fb7\u5fb8\u5fb9\u5fba\u5fbb\u5fbc\u5fbd\u5fbe\u5fbf\u5fc0\u5fc1\u5fc2\u5fc3\u5fc4\u5fc5\u5fc6\u5fc7\u5fc8\u5fc9\u5fca\u5fcb\u5fcc\u5fcd\u5fce\u5fcf\u5fd0\u5fd1\u5fd2\u5fd3\u5fd4\u5fd5\u5fd6\u5fd7\u5fd8\u5fd9\u5fda\u5fdb\u5fdc\u5fdd\u5fde\u5fdf\u5fe0\u5fe1\u5fe2\u5fe3\u5fe4\u5fe5\u5fe6\u5fe7\u5fe8\u5fe9\u5fea\u5feb\u5fec\u5fed\u5fee\u5fef\u5ff0\u5ff1\u5ff2\u5ff3\u5ff4\u5ff5\u5ff6\u5ff7\u5ff8\u5ff9\u5ffa\u5ffb\u5ffc\u5ffd\u5ffe\u5fff\u6000\u6001\u6002\u6003\u6004\u6005\u6006\u6007\u6008\u6009\u600a\u600b\u600c\u600d\u600e\u600f\u6010\u6011\u6012\u6013\u6014\u6015\u6016\u6017\u6018\u6019\u601a\u601b\u601c\u601d\u601e\u601f\u6020\u6021\u6022\u6023\u6024\u6025\u6026\u6027\u6028\u6029\u602a\u602b\u602c\u602d\u602e\u602f\u6030\u6031\u6032\u6033\u6034\u6035\u6036\u6037\u6038\u6039\u603a\u603b\u603c\u603d\u603e\u603f\u6040\u6041\u6042\u6043\u6044\u6045\u6046\u6047\u6048\u6049\u604a\u604b\u604c\u604d\u604e\u604f\u6050\u6051\u6052\u6053\u6054\u6055\u6056\u6057\u6058\u6059\u605a\u605b\u605c\u605d\u605e\u605f\u6060\u6061\u6062\u6063\u6064\u6065\u6066\u6067\u6068\u6069\u606a\u606b\u606c\u606d\u606e\u606f\u6070\u6071\u6072\u6073\u6074\u6075\u6076\u6077\u6078\u6079\u607a\u607b\u607c\u607d\u607e\u607f\u6080\u6081\u6082\u6083\u6084\u6085\u6086\u6087\u6088\u6089\u608a\u608b\u608c\u608d\u608e\u608f\u6090\u6091\u6092\u6093\u6094\u6095\u6096\u6097\u6098\u6099\u609a\u609b\u609c\u609d\u609e\u609f\u60a0\u60a1\u60a2\u60a3\u60a4\u60a5\u60a6\u60a7\u60a8\u60a9\u60aa\u60ab\u60ac\u60ad\u60ae\u60af\u60b0\u60b1\u60b2\u60b3\u60b4\u60b5\u60b6\u60b7\u60b8\u60b9\u60ba\u60bb\u60bc\u60bd\u60be\u60bf\u60c0\u60c1\u60c2\u60c3\u60c4\u60c5\u60c6\u60c7\u60c8\u60c9\u60ca\u60cb\u60cc\u60cd\u60ce\u60cf\u60d0\u60d1\u60d2\u60d3\u60d4\u60d5\u60d6\u60d7\u60d8\u60d9\u60da\u60db\u60dc\u60dd\u60de\u60df\u60e0\u60e1\u60e2\u60e3\u60e4\u60e5\u60e6\u60e7\u60e8\u60e9\u60ea\u60eb\u60ec\u60ed\u60ee\u60ef\u60f0\u60f1\u60f2\u60f3\u60f4\u60f5\u60f6\u60f7\u60f8\u60f9\u60fa\u60fb\u60fc\u60fd\u60fe\u60ff\u6100\u6101\u6102\u6103\u6104\u6105\u6106\u6107\u6108\u6109\u610a\u610b\u610c\u610d\u610e\u610f\u6110\u6111\u6112\u6113\u6114\u6115\u6116\u6117\u6118\u6119\u611a\u611b\u611c\u611d\u611e\u611f\u6120\u6121\u6122\u6123\u6124\u6125\u6126\u6127\u6128\u6129\u612a\u612b\u612c\u612d\u612e\u612f\u6130\u6131\u6132\u6133\u6134\u6135\u6136\u6137\u6138\u6139\u613a\u613b\u613c\u613d\u613e\u613f\u6140\u6141\u6142\u6143\u6144\u6145\u6146\u6147\u6148\u6149\u614a\u614b\u614c\u614d\u614e\u614f\u6150\u6151\u6152\u6153\u6154\u6155\u6156\u6157\u6158\u6159\u615a\u615b\u615c\u615d\u615e\u615f\u6160\u6161\u6162\u6163\u6164\u6165\u6166\u6167\u6168\u6169\u616a\u616b\u616c\u616d\u616e\u616f\u6170\u6171\u6172\u6173\u6174\u6175\u6176\u6177\u6178\u6179\u617a\u617b\u617c\u617d\u617e\u617f\u6180\u6181\u6182\u6183\u6184\u6185\u6186\u6187\u6188\u6189\u618a\u618b\u618c\u618d\u618e\u618f\u6190\u6191\u6192\u6193\u6194\u6195\u6196\u6197\u6198\u6199\u619a\u619b\u619c\u619d\u619e\u619f\u61a0\u61a1\u61a2\u61a3\u61a4\u61a5\u61a6\u61a7\u61a8\u61a9\u61aa\u61ab\u61ac\u61ad\u61ae\u61af\u61b0\u61b1\u61b2\u61b3\u61b4\u61b5\u61b6\u61b7\u61b8\u61b9\u61ba\u61bb\u61bc\u61bd\u61be\u61bf\u61c0\u61c1\u61c2\u61c3\u61c4\u61c5\u61c6\u61c7\u61c8\u61c9\u61ca\u61cb\u61cc\u61cd\u61ce\u61cf\u61d0\u61d1\u61d2\u61d3\u61d4\u61d5\u61d6\u61d7\u61d8\u61d9\u61da\u61db\u61dc\u61dd\u61de\u61df\u61e0\u61e1\u61e2\u61e3\u61e4\u61e5\u61e6\u61e7\u61e8\u61e9\u61ea\u61eb\u61ec\u61ed\u61ee\u61ef\u61f0\u61f1\u61f2\u61f3\u61f4\u61f5\u61f6\u61f7\u61f8\u61f9\u61fa\u61fb\u61fc\u61fd\u61fe\u61ff\u6200\u6201\u6202\u6203\u6204\u6205\u6206\u6207\u6208\u6209\u620a\u620b\u620c\u620d\u620e\u620f\u6210\u6211\u6212\u6213\u6214\u6215\u6216\u6217\u6218\u6219\u621a\u621b\u621c\u621d\u621e\u621f\u6220\u6221\u6222\u6223\u6224\u6225\u6226\u6227\u6228\u6229\u622a\u622b\u622c\u622d\u622e\u622f\u6230\u6231\u6232\u6233\u6234\u6235\u6236\u6237\u6238\u6239\u623a\u623b\u623c\u623d\u623e\u623f\u6240\u6241\u6242\u6243\u6244\u6245\u6246\u6247\u6248\u6249\u624a\u624b\u624c\u624d\u624e\u624f\u6250\u6251\u6252\u6253\u6254\u6255\u6256\u6257\u6258\u6259\u625a\u625b\u625c\u625d\u625e\u625f\u6260\u6261\u6262\u6263\u6264\u6265\u6266\u6267\u6268\u6269\u626a\u626b\u626c\u626d\u626e\u626f\u6270\u6271\u6272\u6273\u6274\u6275\u6276\u6277\u6278\u6279\u627a\u627b\u627c\u627d\u627e\u627f\u6280\u6281\u6282\u6283\u6284\u6285\u6286\u6287\u6288\u6289\u628a\u628b\u628c\u628d\u628e\u628f\u6290\u6291\u6292\u6293\u6294\u6295\u6296\u6297\u6298\u6299\u629a\u629b\u629c\u629d\u629e\u629f\u62a0\u62a1\u62a2\u62a3\u62a4\u62a5\u62a6\u62a7\u62a8\u62a9\u62aa\u62ab\u62ac\u62ad\u62ae\u62af\u62b0\u62b1\u62b2\u62b3\u62b4\u62b5\u62b6\u62b7\u62b8\u62b9\u62ba\u62bb\u62bc\u62bd\u62be\u62bf\u62c0\u62c1\u62c2\u62c3\u62c4\u62c5\u62c6\u62c7\u62c8\u62c9\u62ca\u62cb\u62cc\u62cd\u62ce\u62cf\u62d0\u62d1\u62d2\u62d3\u62d4\u62d5\u62d6\u62d7\u62d8\u62d9\u62da\u62db\u62dc\u62dd\u62de\u62df\u62e0\u62e1\u62e2\u62e3\u62e4\u62e5\u62e6\u62e7\u62e8\u62e9\u62ea\u62eb\u62ec\u62ed\u62ee\u62ef\u62f0\u62f1\u62f2\u62f3\u62f4\u62f5\u62f6\u62f7\u62f8\u62f9\u62fa\u62fb\u62fc\u62fd\u62fe\u62ff\u6300\u6301\u6302\u6303\u6304\u6305\u6306\u6307\u6308\u6309\u630a\u630b\u630c\u630d\u630e\u630f\u6310\u6311\u6312\u6313\u6314\u6315\u6316\u6317\u6318\u6319\u631a\u631b\u631c\u631d\u631e\u631f\u6320\u6321\u6322\u6323\u6324\u6325\u6326\u6327\u6328\u6329\u632a\u632b\u632c\u632d\u632e\u632f\u6330\u6331\u6332\u6333\u6334\u6335\u6336\u6337\u6338\u6339\u633a\u633b\u633c\u633d\u633e\u633f\u6340\u6341\u6342\u6343\u6344\u6345\u6346\u6347\u6348\u6349\u634a\u634b\u634c\u634d\u634e\u634f\u6350\u6351\u6352\u6353\u6354\u6355\u6356\u6357\u6358\u6359\u635a\u635b\u635c\u635d\u635e\u635f\u6360\u6361\u6362\u6363\u6364\u6365\u6366\u6367\u6368\u6369\u636a\u636b\u636c\u636d\u636e\u636f\u6370\u6371\u6372\u6373\u6374\u6375\u6376\u6377\u6378\u6379\u637a\u637b\u637c\u637d\u637e\u637f\u6380\u6381\u6382\u6383\u6384\u6385\u6386\u6387\u6388\u6389\u638a\u638b\u638c\u638d\u638e\u638f\u6390\u6391\u6392\u6393\u6394\u6395\u6396\u6397\u6398\u6399\u639a\u639b\u639c\u639d\u639e\u639f\u63a0\u63a1\u63a2\u63a3\u63a4\u63a5\u63a6\u63a7\u63a8\u63a9\u63aa\u63ab\u63ac\u63ad\u63ae\u63af\u63b0\u63b1\u63b2\u63b3\u63b4\u63b5\u63b6\u63b7\u63b8\u63b9\u63ba\u63bb\u63bc\u63bd\u63be\u63bf\u63c0\u63c1\u63c2\u63c3\u63c4\u63c5\u63c6\u63c7\u63c8\u63c9\u63ca\u63cb\u63cc\u63cd\u63ce\u63cf\u63d0\u63d1\u63d2\u63d3\u63d4\u63d5\u63d6\u63d7\u63d8\u63d9\u63da\u63db\u63dc\u63dd\u63de\u63df\u63e0\u63e1\u63e2\u63e3\u63e4\u63e5\u63e6\u63e7\u63e8\u63e9\u63ea\u63eb\u63ec\u63ed\u63ee\u63ef\u63f0\u63f1\u63f2\u63f3\u63f4\u63f5\u63f6\u63f7\u63f8\u63f9\u63fa\u63fb\u63fc\u63fd\u63fe\u63ff\u6400\u6401\u6402\u6403\u6404\u6405\u6406\u6407\u6408\u6409\u640a\u640b\u640c\u640d\u640e\u640f\u6410\u6411\u6412\u6413\u6414\u6415\u6416\u6417\u6418\u6419\u641a\u641b\u641c\u641d\u641e\u641f\u6420\u6421\u6422\u6423\u6424\u6425\u6426\u6427\u6428\u6429\u642a\u642b\u642c\u642d\u642e\u642f\u6430\u6431\u6432\u6433\u6434\u6435\u6436\u6437\u6438\u6439\u643a\u643b\u643c\u643d\u643e\u643f\u6440\u6441\u6442\u6443\u6444\u6445\u6446\u6447\u6448\u6449\u644a\u644b\u644c\u644d\u644e\u644f\u6450\u6451\u6452\u6453\u6454\u6455\u6456\u6457\u6458\u6459\u645a\u645b\u645c\u645d\u645e\u645f\u6460\u6461\u6462\u6463\u6464\u6465\u6466\u6467\u6468\u6469\u646a\u646b\u646c\u646d\u646e\u646f\u6470\u6471\u6472\u6473\u6474\u6475\u6476\u6477\u6478\u6479\u647a\u647b\u647c\u647d\u647e\u647f\u6480\u6481\u6482\u6483\u6484\u6485\u6486\u6487\u6488\u6489\u648a\u648b\u648c\u648d\u648e\u648f\u6490\u6491\u6492\u6493\u6494\u6495\u6496\u6497\u6498\u6499\u649a\u649b\u649c\u649d\u649e\u649f\u64a0\u64a1\u64a2\u64a3\u64a4\u64a5\u64a6\u64a7\u64a8\u64a9\u64aa\u64ab\u64ac\u64ad\u64ae\u64af\u64b0\u64b1\u64b2\u64b3\u64b4\u64b5\u64b6\u64b7\u64b8\u64b9\u64ba\u64bb\u64bc\u64bd\u64be\u64bf\u64c0\u64c1\u64c2\u64c3\u64c4\u64c5\u64c6\u64c7\u64c8\u64c9\u64ca\u64cb\u64cc\u64cd\u64ce\u64cf\u64d0\u64d1\u64d2\u64d3\u64d4\u64d5\u64d6\u64d7\u64d8\u64d9\u64da\u64db\u64dc\u64dd\u64de\u64df\u64e0\u64e1\u64e2\u64e3\u64e4\u64e5\u64e6\u64e7\u64e8\u64e9\u64ea\u64eb\u64ec\u64ed\u64ee\u64ef\u64f0\u64f1\u64f2\u64f3\u64f4\u64f5\u64f6\u64f7\u64f8\u64f9\u64fa\u64fb\u64fc\u64fd\u64fe\u64ff\u6500\u6501\u6502\u6503\u6504\u6505\u6506\u6507\u6508\u6509\u650a\u650b\u650c\u650d\u650e\u650f\u6510\u6511\u6512\u6513\u6514\u6515\u6516\u6517\u6518\u6519\u651a\u651b\u651c\u651d\u651e\u651f\u6520\u6521\u6522\u6523\u6524\u6525\u6526\u6527\u6528\u6529\u652a\u652b\u652c\u652d\u652e\u652f\u6530\u6531\u6532\u6533\u6534\u6535\u6536\u6537\u6538\u6539\u653a\u653b\u653c\u653d\u653e\u653f\u6540\u6541\u6542\u6543\u6544\u6545\u6546\u6547\u6548\u6549\u654a\u654b\u654c\u654d\u654e\u654f\u6550\u6551\u6552\u6553\u6554\u6555\u6556\u6557\u6558\u6559\u655a\u655b\u655c\u655d\u655e\u655f\u6560\u6561\u6562\u6563\u6564\u6565\u6566\u6567\u6568\u6569\u656a\u656b\u656c\u656d\u656e\u656f\u6570\u6571\u6572\u6573\u6574\u6575\u6576\u6577\u6578\u6579\u657a\u657b\u657c\u657d\u657e\u657f\u6580\u6581\u6582\u6583\u6584\u6585\u6586\u6587\u6588\u6589\u658a\u658b\u658c\u658d\u658e\u658f\u6590\u6591\u6592\u6593\u6594\u6595\u6596\u6597\u6598\u6599\u659a\u659b\u659c\u659d\u659e\u659f\u65a0\u65a1\u65a2\u65a3\u65a4\u65a5\u65a6\u65a7\u65a8\u65a9\u65aa\u65ab\u65ac\u65ad\u65ae\u65af\u65b0\u65b1\u65b2\u65b3\u65b4\u65b5\u65b6\u65b7\u65b8\u65b9\u65ba\u65bb\u65bc\u65bd\u65be\u65bf\u65c0\u65c1\u65c2\u65c3\u65c4\u65c5\u65c6\u65c7\u65c8\u65c9\u65ca\u65cb\u65cc\u65cd\u65ce\u65cf\u65d0\u65d1\u65d2\u65d3\u65d4\u65d5\u65d6\u65d7\u65d8\u65d9\u65da\u65db\u65dc\u65dd\u65de\u65df\u65e0\u65e1\u65e2\u65e3\u65e4\u65e5\u65e6\u65e7\u65e8\u65e9\u65ea\u65eb\u65ec\u65ed\u65ee\u65ef\u65f0\u65f1\u65f2\u65f3\u65f4\u65f5\u65f6\u65f7\u65f8\u65f9\u65fa\u65fb\u65fc\u65fd\u65fe\u65ff\u6600\u6601\u6602\u6603\u6604\u6605\u6606\u6607\u6608\u6609\u660a\u660b\u660c\u660d\u660e\u660f\u6610\u6611\u6612\u6613\u6614\u6615\u6616\u6617\u6618\u6619\u661a\u661b\u661c\u661d\u661e\u661f\u6620\u6621\u6622\u6623\u6624\u6625\u6626\u6627\u6628\u6629\u662a\u662b\u662c\u662d\u662e\u662f\u6630\u6631\u6632\u6633\u6634\u6635\u6636\u6637\u6638\u6639\u663a\u663b\u663c\u663d\u663e\u663f\u6640\u6641\u6642\u6643\u6644\u6645\u6646\u6647\u6648\u6649\u664a\u664b\u664c\u664d\u664e\u664f\u6650\u6651\u6652\u6653\u6654\u6655\u6656\u6657\u6658\u6659\u665a\u665b\u665c\u665d\u665e\u665f\u6660\u6661\u6662\u6663\u6664\u6665\u6666\u6667\u6668\u6669\u666a\u666b\u666c\u666d\u666e\u666f\u6670\u6671\u6672\u6673\u6674\u6675\u6676\u6677\u6678\u6679\u667a\u667b\u667c\u667d\u667e\u667f\u6680\u6681\u6682\u6683\u6684\u6685\u6686\u6687\u6688\u6689\u668a\u668b\u668c\u668d\u668e\u668f\u6690\u6691\u6692\u6693\u6694\u6695\u6696\u6697\u6698\u6699\u669a\u669b\u669c\u669d\u669e\u669f\u66a0\u66a1\u66a2\u66a3\u66a4\u66a5\u66a6\u66a7\u66a8\u66a9\u66aa\u66ab\u66ac\u66ad\u66ae\u66af\u66b0\u66b1\u66b2\u66b3\u66b4\u66b5\u66b6\u66b7\u66b8\u66b9\u66ba\u66bb\u66bc\u66bd\u66be\u66bf\u66c0\u66c1\u66c2\u66c3\u66c4\u66c5\u66c6\u66c7\u66c8\u66c9\u66ca\u66cb\u66cc\u66cd\u66ce\u66cf\u66d0\u66d1\u66d2\u66d3\u66d4\u66d5\u66d6\u66d7\u66d8\u66d9\u66da\u66db\u66dc\u66dd\u66de\u66df\u66e0\u66e1\u66e2\u66e3\u66e4\u66e5\u66e6\u66e7\u66e8\u66e9\u66ea\u66eb\u66ec\u66ed\u66ee\u66ef\u66f0\u66f1\u66f2\u66f3\u66f4\u66f5\u66f6\u66f7\u66f8\u66f9\u66fa\u66fb\u66fc\u66fd\u66fe\u66ff\u6700\u6701\u6702\u6703\u6704\u6705\u6706\u6707\u6708\u6709\u670a\u670b\u670c\u670d\u670e\u670f\u6710\u6711\u6712\u6713\u6714\u6715\u6716\u6717\u6718\u6719\u671a\u671b\u671c\u671d\u671e\u671f\u6720\u6721\u6722\u6723\u6724\u6725\u6726\u6727\u6728\u6729\u672a\u672b\u672c\u672d\u672e\u672f\u6730\u6731\u6732\u6733\u6734\u6735\u6736\u6737\u6738\u6739\u673a\u673b\u673c\u673d\u673e\u673f\u6740\u6741\u6742\u6743\u6744\u6745\u6746\u6747\u6748\u6749\u674a\u674b\u674c\u674d\u674e\u674f\u6750\u6751\u6752\u6753\u6754\u6755\u6756\u6757\u6758\u6759\u675a\u675b\u675c\u675d\u675e\u675f\u6760\u6761\u6762\u6763\u6764\u6765\u6766\u6767\u6768\u6769\u676a\u676b\u676c\u676d\u676e\u676f\u6770\u6771\u6772\u6773\u6774\u6775\u6776\u6777\u6778\u6779\u677a\u677b\u677c\u677d\u677e\u677f\u6780\u6781\u6782\u6783\u6784\u6785\u6786\u6787\u6788\u6789\u678a\u678b\u678c\u678d\u678e\u678f\u6790\u6791\u6792\u6793\u6794\u6795\u6796\u6797\u6798\u6799\u679a\u679b\u679c\u679d\u679e\u679f\u67a0\u67a1\u67a2\u67a3\u67a4\u67a5\u67a6\u67a7\u67a8\u67a9\u67aa\u67ab\u67ac\u67ad\u67ae\u67af\u67b0\u67b1\u67b2\u67b3\u67b4\u67b5\u67b6\u67b7\u67b8\u67b9\u67ba\u67bb\u67bc\u67bd\u67be\u67bf\u67c0\u67c1\u67c2\u67c3\u67c4\u67c5\u67c6\u67c7\u67c8\u67c9\u67ca\u67cb\u67cc\u67cd\u67ce\u67cf\u67d0\u67d1\u67d2\u67d3\u67d4\u67d5\u67d6\u67d7\u67d8\u67d9\u67da\u67db\u67dc\u67dd\u67de\u67df\u67e0\u67e1\u67e2\u67e3\u67e4\u67e5\u67e6\u67e7\u67e8\u67e9\u67ea\u67eb\u67ec\u67ed\u67ee\u67ef\u67f0\u67f1\u67f2\u67f3\u67f4\u67f5\u67f6\u67f7\u67f8\u67f9\u67fa\u67fb\u67fc\u67fd\u67fe\u67ff\u6800\u6801\u6802\u6803\u6804\u6805\u6806\u6807\u6808\u6809\u680a\u680b\u680c\u680d\u680e\u680f\u6810\u6811\u6812\u6813\u6814\u6815\u6816\u6817\u6818\u6819\u681a\u681b\u681c\u681d\u681e\u681f\u6820\u6821\u6822\u6823\u6824\u6825\u6826\u6827\u6828\u6829\u682a\u682b\u682c\u682d\u682e\u682f\u6830\u6831\u6832\u6833\u6834\u6835\u6836\u6837\u6838\u6839\u683a\u683b\u683c\u683d\u683e\u683f\u6840\u6841\u6842\u6843\u6844\u6845\u6846\u6847\u6848\u6849\u684a\u684b\u684c\u684d\u684e\u684f\u6850\u6851\u6852\u6853\u6854\u6855\u6856\u6857\u6858\u6859\u685a\u685b\u685c\u685d\u685e\u685f\u6860\u6861\u6862\u6863\u6864\u6865\u6866\u6867\u6868\u6869\u686a\u686b\u686c\u686d\u686e\u686f\u6870\u6871\u6872\u6873\u6874\u6875\u6876\u6877\u6878\u6879\u687a\u687b\u687c\u687d\u687e\u687f\u6880\u6881\u6882\u6883\u6884\u6885\u6886\u6887\u6888\u6889\u688a\u688b\u688c\u688d\u688e\u688f\u6890\u6891\u6892\u6893\u6894\u6895\u6896\u6897\u6898\u6899\u689a\u689b\u689c\u689d\u689e\u689f\u68a0\u68a1\u68a2\u68a3\u68a4\u68a5\u68a6\u68a7\u68a8\u68a9\u68aa\u68ab\u68ac\u68ad\u68ae\u68af\u68b0\u68b1\u68b2\u68b3\u68b4\u68b5\u68b6\u68b7\u68b8\u68b9\u68ba\u68bb\u68bc\u68bd\u68be\u68bf\u68c0\u68c1\u68c2\u68c3\u68c4\u68c5\u68c6\u68c7\u68c8\u68c9\u68ca\u68cb\u68cc\u68cd\u68ce\u68cf\u68d0\u68d1\u68d2\u68d3\u68d4\u68d5\u68d6\u68d7\u68d8\u68d9\u68da\u68db\u68dc\u68dd\u68de\u68df\u68e0\u68e1\u68e2\u68e3\u68e4\u68e5\u68e6\u68e7\u68e8\u68e9\u68ea\u68eb\u68ec\u68ed\u68ee\u68ef\u68f0\u68f1\u68f2\u68f3\u68f4\u68f5\u68f6\u68f7\u68f8\u68f9\u68fa\u68fb\u68fc\u68fd\u68fe\u68ff\u6900\u6901\u6902\u6903\u6904\u6905\u6906\u6907\u6908\u6909\u690a\u690b\u690c\u690d\u690e\u690f\u6910\u6911\u6912\u6913\u6914\u6915\u6916\u6917\u6918\u6919\u691a\u691b\u691c\u691d\u691e\u691f\u6920\u6921\u6922\u6923\u6924\u6925\u6926\u6927\u6928\u6929\u692a\u692b\u692c\u692d\u692e\u692f\u6930\u6931\u6932\u6933\u6934\u6935\u6936\u6937\u6938\u6939\u693a\u693b\u693c\u693d\u693e\u693f\u6940\u6941\u6942\u6943\u6944\u6945\u6946\u6947\u6948\u6949\u694a\u694b\u694c\u694d\u694e\u694f\u6950\u6951\u6952\u6953\u6954\u6955\u6956\u6957\u6958\u6959\u695a\u695b\u695c\u695d\u695e\u695f\u6960\u6961\u6962\u6963\u6964\u6965\u6966\u6967\u6968\u6969\u696a\u696b\u696c\u696d\u696e\u696f\u6970\u6971\u6972\u6973\u6974\u6975\u6976\u6977\u6978\u6979\u697a\u697b\u697c\u697d\u697e\u697f\u6980\u6981\u6982\u6983\u6984\u6985\u6986\u6987\u6988\u6989\u698a\u698b\u698c\u698d\u698e\u698f\u6990\u6991\u6992\u6993\u6994\u6995\u6996\u6997\u6998\u6999\u699a\u699b\u699c\u699d\u699e\u699f\u69a0\u69a1\u69a2\u69a3\u69a4\u69a5\u69a6\u69a7\u69a8\u69a9\u69aa\u69ab\u69ac\u69ad\u69ae\u69af\u69b0\u69b1\u69b2\u69b3\u69b4\u69b5\u69b6\u69b7\u69b8\u69b9\u69ba\u69bb\u69bc\u69bd\u69be\u69bf\u69c0\u69c1\u69c2\u69c3\u69c4\u69c5\u69c6\u69c7\u69c8\u69c9\u69ca\u69cb\u69cc\u69cd\u69ce\u69cf\u69d0\u69d1\u69d2\u69d3\u69d4\u69d5\u69d6\u69d7\u69d8\u69d9\u69da\u69db\u69dc\u69dd\u69de\u69df\u69e0\u69e1\u69e2\u69e3\u69e4\u69e5\u69e6\u69e7\u69e8\u69e9\u69ea\u69eb\u69ec\u69ed\u69ee\u69ef\u69f0\u69f1\u69f2\u69f3\u69f4\u69f5\u69f6\u69f7\u69f8\u69f9\u69fa\u69fb\u69fc\u69fd\u69fe\u69ff\u6a00\u6a01\u6a02\u6a03\u6a04\u6a05\u6a06\u6a07\u6a08\u6a09\u6a0a\u6a0b\u6a0c\u6a0d\u6a0e\u6a0f\u6a10\u6a11\u6a12\u6a13\u6a14\u6a15\u6a16\u6a17\u6a18\u6a19\u6a1a\u6a1b\u6a1c\u6a1d\u6a1e\u6a1f\u6a20\u6a21\u6a22\u6a23\u6a24\u6a25\u6a26\u6a27\u6a28\u6a29\u6a2a\u6a2b\u6a2c\u6a2d\u6a2e\u6a2f\u6a30\u6a31\u6a32\u6a33\u6a34\u6a35\u6a36\u6a37\u6a38\u6a39\u6a3a\u6a3b\u6a3c\u6a3d\u6a3e\u6a3f\u6a40\u6a41\u6a42\u6a43\u6a44\u6a45\u6a46\u6a47\u6a48\u6a49\u6a4a\u6a4b\u6a4c\u6a4d\u6a4e\u6a4f\u6a50\u6a51\u6a52\u6a53\u6a54\u6a55\u6a56\u6a57\u6a58\u6a59\u6a5a\u6a5b\u6a5c\u6a5d\u6a5e\u6a5f\u6a60\u6a61\u6a62\u6a63\u6a64\u6a65\u6a66\u6a67\u6a68\u6a69\u6a6a\u6a6b\u6a6c\u6a6d\u6a6e\u6a6f\u6a70\u6a71\u6a72\u6a73\u6a74\u6a75\u6a76\u6a77\u6a78\u6a79\u6a7a\u6a7b\u6a7c\u6a7d\u6a7e\u6a7f\u6a80\u6a81\u6a82\u6a83\u6a84\u6a85\u6a86\u6a87\u6a88\u6a89\u6a8a\u6a8b\u6a8c\u6a8d\u6a8e\u6a8f\u6a90\u6a91\u6a92\u6a93\u6a94\u6a95\u6a96\u6a97\u6a98\u6a99\u6a9a\u6a9b\u6a9c\u6a9d\u6a9e\u6a9f\u6aa0\u6aa1\u6aa2\u6aa3\u6aa4\u6aa5\u6aa6\u6aa7\u6aa8\u6aa9\u6aaa\u6aab\u6aac\u6aad\u6aae\u6aaf\u6ab0\u6ab1\u6ab2\u6ab3\u6ab4\u6ab5\u6ab6\u6ab7\u6ab8\u6ab9\u6aba\u6abb\u6abc\u6abd\u6abe\u6abf\u6ac0\u6ac1\u6ac2\u6ac3\u6ac4\u6ac5\u6ac6\u6ac7\u6ac8\u6ac9\u6aca\u6acb\u6acc\u6acd\u6ace\u6acf\u6ad0\u6ad1\u6ad2\u6ad3\u6ad4\u6ad5\u6ad6\u6ad7\u6ad8\u6ad9\u6ada\u6adb\u6adc\u6add\u6ade\u6adf\u6ae0\u6ae1\u6ae2\u6ae3\u6ae4\u6ae5\u6ae6\u6ae7\u6ae8\u6ae9\u6aea\u6aeb\u6aec\u6aed\u6aee\u6aef\u6af0\u6af1\u6af2\u6af3\u6af4\u6af5\u6af6\u6af7\u6af8\u6af9\u6afa\u6afb\u6afc\u6afd\u6afe\u6aff\u6b00\u6b01\u6b02\u6b03\u6b04\u6b05\u6b06\u6b07\u6b08\u6b09\u6b0a\u6b0b\u6b0c\u6b0d\u6b0e\u6b0f\u6b10\u6b11\u6b12\u6b13\u6b14\u6b15\u6b16\u6b17\u6b18\u6b19\u6b1a\u6b1b\u6b1c\u6b1d\u6b1e\u6b1f\u6b20\u6b21\u6b22\u6b23\u6b24\u6b25\u6b26\u6b27\u6b28\u6b29\u6b2a\u6b2b\u6b2c\u6b2d\u6b2e\u6b2f\u6b30\u6b31\u6b32\u6b33\u6b34\u6b35\u6b36\u6b37\u6b38\u6b39\u6b3a\u6b3b\u6b3c\u6b3d\u6b3e\u6b3f\u6b40\u6b41\u6b42\u6b43\u6b44\u6b45\u6b46\u6b47\u6b48\u6b49\u6b4a\u6b4b\u6b4c\u6b4d\u6b4e\u6b4f\u6b50\u6b51\u6b52\u6b53\u6b54\u6b55\u6b56\u6b57\u6b58\u6b59\u6b5a\u6b5b\u6b5c\u6b5d\u6b5e\u6b5f\u6b60\u6b61\u6b62\u6b63\u6b64\u6b65\u6b66\u6b67\u6b68\u6b69\u6b6a\u6b6b\u6b6c\u6b6d\u6b6e\u6b6f\u6b70\u6b71\u6b72\u6b73\u6b74\u6b75\u6b76\u6b77\u6b78\u6b79\u6b7a\u6b7b\u6b7c\u6b7d\u6b7e\u6b7f\u6b80\u6b81\u6b82\u6b83\u6b84\u6b85\u6b86\u6b87\u6b88\u6b89\u6b8a\u6b8b\u6b8c\u6b8d\u6b8e\u6b8f\u6b90\u6b91\u6b92\u6b93\u6b94\u6b95\u6b96\u6b97\u6b98\u6b99\u6b9a\u6b9b\u6b9c\u6b9d\u6b9e\u6b9f\u6ba0\u6ba1\u6ba2\u6ba3\u6ba4\u6ba5\u6ba6\u6ba7\u6ba8\u6ba9\u6baa\u6bab\u6bac\u6bad\u6bae\u6baf\u6bb0\u6bb1\u6bb2\u6bb3\u6bb4\u6bb5\u6bb6\u6bb7\u6bb8\u6bb9\u6bba\u6bbb\u6bbc\u6bbd\u6bbe\u6bbf\u6bc0\u6bc1\u6bc2\u6bc3\u6bc4\u6bc5\u6bc6\u6bc7\u6bc8\u6bc9\u6bca\u6bcb\u6bcc\u6bcd\u6bce\u6bcf\u6bd0\u6bd1\u6bd2\u6bd3\u6bd4\u6bd5\u6bd6\u6bd7\u6bd8\u6bd9\u6bda\u6bdb\u6bdc\u6bdd\u6bde\u6bdf\u6be0\u6be1\u6be2\u6be3\u6be4\u6be5\u6be6\u6be7\u6be8\u6be9\u6bea\u6beb\u6bec\u6bed\u6bee\u6bef\u6bf0\u6bf1\u6bf2\u6bf3\u6bf4\u6bf5\u6bf6\u6bf7\u6bf8\u6bf9\u6bfa\u6bfb\u6bfc\u6bfd\u6bfe\u6bff\u6c00\u6c01\u6c02\u6c03\u6c04\u6c05\u6c06\u6c07\u6c08\u6c09\u6c0a\u6c0b\u6c0c\u6c0d\u6c0e\u6c0f\u6c10\u6c11\u6c12\u6c13\u6c14\u6c15\u6c16\u6c17\u6c18\u6c19\u6c1a\u6c1b\u6c1c\u6c1d\u6c1e\u6c1f\u6c20\u6c21\u6c22\u6c23\u6c24\u6c25\u6c26\u6c27\u6c28\u6c29\u6c2a\u6c2b\u6c2c\u6c2d\u6c2e\u6c2f\u6c30\u6c31\u6c32\u6c33\u6c34\u6c35\u6c36\u6c37\u6c38\u6c39\u6c3a\u6c3b\u6c3c\u6c3d\u6c3e\u6c3f\u6c40\u6c41\u6c42\u6c43\u6c44\u6c45\u6c46\u6c47\u6c48\u6c49\u6c4a\u6c4b\u6c4c\u6c4d\u6c4e\u6c4f\u6c50\u6c51\u6c52\u6c53\u6c54\u6c55\u6c56\u6c57\u6c58\u6c59\u6c5a\u6c5b\u6c5c\u6c5d\u6c5e\u6c5f\u6c60\u6c61\u6c62\u6c63\u6c64\u6c65\u6c66\u6c67\u6c68\u6c69\u6c6a\u6c6b\u6c6c\u6c6d\u6c6e\u6c6f\u6c70\u6c71\u6c72\u6c73\u6c74\u6c75\u6c76\u6c77\u6c78\u6c79\u6c7a\u6c7b\u6c7c\u6c7d\u6c7e\u6c7f\u6c80\u6c81\u6c82\u6c83\u6c84\u6c85\u6c86\u6c87\u6c88\u6c89\u6c8a\u6c8b\u6c8c\u6c8d\u6c8e\u6c8f\u6c90\u6c91\u6c92\u6c93\u6c94\u6c95\u6c96\u6c97\u6c98\u6c99\u6c9a\u6c9b\u6c9c\u6c9d\u6c9e\u6c9f\u6ca0\u6ca1\u6ca2\u6ca3\u6ca4\u6ca5\u6ca6\u6ca7\u6ca8\u6ca9\u6caa\u6cab\u6cac\u6cad\u6cae\u6caf\u6cb0\u6cb1\u6cb2\u6cb3\u6cb4\u6cb5\u6cb6\u6cb7\u6cb8\u6cb9\u6cba\u6cbb\u6cbc\u6cbd\u6cbe\u6cbf\u6cc0\u6cc1\u6cc2\u6cc3\u6cc4\u6cc5\u6cc6\u6cc7\u6cc8\u6cc9\u6cca\u6ccb\u6ccc\u6ccd\u6cce\u6ccf\u6cd0\u6cd1\u6cd2\u6cd3\u6cd4\u6cd5\u6cd6\u6cd7\u6cd8\u6cd9\u6cda\u6cdb\u6cdc\u6cdd\u6cde\u6cdf\u6ce0\u6ce1\u6ce2\u6ce3\u6ce4\u6ce5\u6ce6\u6ce7\u6ce8\u6ce9\u6cea\u6ceb\u6cec\u6ced\u6cee\u6cef\u6cf0\u6cf1\u6cf2\u6cf3\u6cf4\u6cf5\u6cf6\u6cf7\u6cf8\u6cf9\u6cfa\u6cfb\u6cfc\u6cfd\u6cfe\u6cff\u6d00\u6d01\u6d02\u6d03\u6d04\u6d05\u6d06\u6d07\u6d08\u6d09\u6d0a\u6d0b\u6d0c\u6d0d\u6d0e\u6d0f\u6d10\u6d11\u6d12\u6d13\u6d14\u6d15\u6d16\u6d17\u6d18\u6d19\u6d1a\u6d1b\u6d1c\u6d1d\u6d1e\u6d1f\u6d20\u6d21\u6d22\u6d23\u6d24\u6d25\u6d26\u6d27\u6d28\u6d29\u6d2a\u6d2b\u6d2c\u6d2d\u6d2e\u6d2f\u6d30\u6d31\u6d32\u6d33\u6d34\u6d35\u6d36\u6d37\u6d38\u6d39\u6d3a\u6d3b\u6d3c\u6d3d\u6d3e\u6d3f\u6d40\u6d41\u6d42\u6d43\u6d44\u6d45\u6d46\u6d47\u6d48\u6d49\u6d4a\u6d4b\u6d4c\u6d4d\u6d4e\u6d4f\u6d50\u6d51\u6d52\u6d53\u6d54\u6d55\u6d56\u6d57\u6d58\u6d59\u6d5a\u6d5b\u6d5c\u6d5d\u6d5e\u6d5f\u6d60\u6d61\u6d62\u6d63\u6d64\u6d65\u6d66\u6d67\u6d68\u6d69\u6d6a\u6d6b\u6d6c\u6d6d\u6d6e\u6d6f\u6d70\u6d71\u6d72\u6d73\u6d74\u6d75\u6d76\u6d77\u6d78\u6d79\u6d7a\u6d7b\u6d7c\u6d7d\u6d7e\u6d7f\u6d80\u6d81\u6d82\u6d83\u6d84\u6d85\u6d86\u6d87\u6d88\u6d89\u6d8a\u6d8b\u6d8c\u6d8d\u6d8e\u6d8f\u6d90\u6d91\u6d92\u6d93\u6d94\u6d95\u6d96\u6d97\u6d98\u6d99\u6d9a\u6d9b\u6d9c\u6d9d\u6d9e\u6d9f\u6da0\u6da1\u6da2\u6da3\u6da4\u6da5\u6da6\u6da7\u6da8\u6da9\u6daa\u6dab\u6dac\u6dad\u6dae\u6daf\u6db0\u6db1\u6db2\u6db3\u6db4\u6db5\u6db6\u6db7\u6db8\u6db9\u6dba\u6dbb\u6dbc\u6dbd\u6dbe\u6dbf\u6dc0\u6dc1\u6dc2\u6dc3\u6dc4\u6dc5\u6dc6\u6dc7\u6dc8\u6dc9\u6dca\u6dcb\u6dcc\u6dcd\u6dce\u6dcf\u6dd0\u6dd1\u6dd2\u6dd3\u6dd4\u6dd5\u6dd6\u6dd7\u6dd8\u6dd9\u6dda\u6ddb\u6ddc\u6ddd\u6dde\u6ddf\u6de0\u6de1\u6de2\u6de3\u6de4\u6de5\u6de6\u6de7\u6de8\u6de9\u6dea\u6deb\u6dec\u6ded\u6dee\u6def\u6df0\u6df1\u6df2\u6df3\u6df4\u6df5\u6df6\u6df7\u6df8\u6df9\u6dfa\u6dfb\u6dfc\u6dfd\u6dfe\u6dff\u6e00\u6e01\u6e02\u6e03\u6e04\u6e05\u6e06\u6e07\u6e08\u6e09\u6e0a\u6e0b\u6e0c\u6e0d\u6e0e\u6e0f\u6e10\u6e11\u6e12\u6e13\u6e14\u6e15\u6e16\u6e17\u6e18\u6e19\u6e1a\u6e1b\u6e1c\u6e1d\u6e1e\u6e1f\u6e20\u6e21\u6e22\u6e23\u6e24\u6e25\u6e26\u6e27\u6e28\u6e29\u6e2a\u6e2b\u6e2c\u6e2d\u6e2e\u6e2f\u6e30\u6e31\u6e32\u6e33\u6e34\u6e35\u6e36\u6e37\u6e38\u6e39\u6e3a\u6e3b\u6e3c\u6e3d\u6e3e\u6e3f\u6e40\u6e41\u6e42\u6e43\u6e44\u6e45\u6e46\u6e47\u6e48\u6e49\u6e4a\u6e4b\u6e4c\u6e4d\u6e4e\u6e4f\u6e50\u6e51\u6e52\u6e53\u6e54\u6e55\u6e56\u6e57\u6e58\u6e59\u6e5a\u6e5b\u6e5c\u6e5d\u6e5e\u6e5f\u6e60\u6e61\u6e62\u6e63\u6e64\u6e65\u6e66\u6e67\u6e68\u6e69\u6e6a\u6e6b\u6e6c\u6e6d\u6e6e\u6e6f\u6e70\u6e71\u6e72\u6e73\u6e74\u6e75\u6e76\u6e77\u6e78\u6e79\u6e7a\u6e7b\u6e7c\u6e7d\u6e7e\u6e7f\u6e80\u6e81\u6e82\u6e83\u6e84\u6e85\u6e86\u6e87\u6e88\u6e89\u6e8a\u6e8b\u6e8c\u6e8d\u6e8e\u6e8f\u6e90\u6e91\u6e92\u6e93\u6e94\u6e95\u6e96\u6e97\u6e98\u6e99\u6e9a\u6e9b\u6e9c\u6e9d\u6e9e\u6e9f\u6ea0\u6ea1\u6ea2\u6ea3\u6ea4\u6ea5\u6ea6\u6ea7\u6ea8\u6ea9\u6eaa\u6eab\u6eac\u6ead\u6eae\u6eaf\u6eb0\u6eb1\u6eb2\u6eb3\u6eb4\u6eb5\u6eb6\u6eb7\u6eb8\u6eb9\u6eba\u6ebb\u6ebc\u6ebd\u6ebe\u6ebf\u6ec0\u6ec1\u6ec2\u6ec3\u6ec4\u6ec5\u6ec6\u6ec7\u6ec8\u6ec9\u6eca\u6ecb\u6ecc\u6ecd\u6ece\u6ecf\u6ed0\u6ed1\u6ed2\u6ed3\u6ed4\u6ed5\u6ed6\u6ed7\u6ed8\u6ed9\u6eda\u6edb\u6edc\u6edd\u6ede\u6edf\u6ee0\u6ee1\u6ee2\u6ee3\u6ee4\u6ee5\u6ee6\u6ee7\u6ee8\u6ee9\u6eea\u6eeb\u6eec\u6eed\u6eee\u6eef\u6ef0\u6ef1\u6ef2\u6ef3\u6ef4\u6ef5\u6ef6\u6ef7\u6ef8\u6ef9\u6efa\u6efb\u6efc\u6efd\u6efe\u6eff\u6f00\u6f01\u6f02\u6f03\u6f04\u6f05\u6f06\u6f07\u6f08\u6f09\u6f0a\u6f0b\u6f0c\u6f0d\u6f0e\u6f0f\u6f10\u6f11\u6f12\u6f13\u6f14\u6f15\u6f16\u6f17\u6f18\u6f19\u6f1a\u6f1b\u6f1c\u6f1d\u6f1e\u6f1f\u6f20\u6f21\u6f22\u6f23\u6f24\u6f25\u6f26\u6f27\u6f28\u6f29\u6f2a\u6f2b\u6f2c\u6f2d\u6f2e\u6f2f\u6f30\u6f31\u6f32\u6f33\u6f34\u6f35\u6f36\u6f37\u6f38\u6f39\u6f3a\u6f3b\u6f3c\u6f3d\u6f3e\u6f3f\u6f40\u6f41\u6f42\u6f43\u6f44\u6f45\u6f46\u6f47\u6f48\u6f49\u6f4a\u6f4b\u6f4c\u6f4d\u6f4e\u6f4f\u6f50\u6f51\u6f52\u6f53\u6f54\u6f55\u6f56\u6f57\u6f58\u6f59\u6f5a\u6f5b\u6f5c\u6f5d\u6f5e\u6f5f\u6f60\u6f61\u6f62\u6f63\u6f64\u6f65\u6f66\u6f67\u6f68\u6f69\u6f6a\u6f6b\u6f6c\u6f6d\u6f6e\u6f6f\u6f70\u6f71\u6f72\u6f73\u6f74\u6f75\u6f76\u6f77\u6f78\u6f79\u6f7a\u6f7b\u6f7c\u6f7d\u6f7e\u6f7f\u6f80\u6f81\u6f82\u6f83\u6f84\u6f85\u6f86\u6f87\u6f88\u6f89\u6f8a\u6f8b\u6f8c\u6f8d\u6f8e\u6f8f\u6f90\u6f91\u6f92\u6f93\u6f94\u6f95\u6f96\u6f97\u6f98\u6f99\u6f9a\u6f9b\u6f9c\u6f9d\u6f9e\u6f9f\u6fa0\u6fa1\u6fa2\u6fa3\u6fa4\u6fa5\u6fa6\u6fa7\u6fa8\u6fa9\u6faa\u6fab\u6fac\u6fad\u6fae\u6faf\u6fb0\u6fb1\u6fb2\u6fb3\u6fb4\u6fb5\u6fb6\u6fb7\u6fb8\u6fb9\u6fba\u6fbb\u6fbc\u6fbd\u6fbe\u6fbf\u6fc0\u6fc1\u6fc2\u6fc3\u6fc4\u6fc5\u6fc6\u6fc7\u6fc8\u6fc9\u6fca\u6fcb\u6fcc\u6fcd\u6fce\u6fcf\u6fd0\u6fd1\u6fd2\u6fd3\u6fd4\u6fd5\u6fd6\u6fd7\u6fd8\u6fd9\u6fda\u6fdb\u6fdc\u6fdd\u6fde\u6fdf\u6fe0\u6fe1\u6fe2\u6fe3\u6fe4\u6fe5\u6fe6\u6fe7\u6fe8\u6fe9\u6fea\u6feb\u6fec\u6fed\u6fee\u6fef\u6ff0\u6ff1\u6ff2\u6ff3\u6ff4\u6ff5\u6ff6\u6ff7\u6ff8\u6ff9\u6ffa\u6ffb\u6ffc\u6ffd\u6ffe\u6fff\u7000\u7001\u7002\u7003\u7004\u7005\u7006\u7007\u7008\u7009\u700a\u700b\u700c\u700d\u700e\u700f\u7010\u7011\u7012\u7013\u7014\u7015\u7016\u7017\u7018\u7019\u701a\u701b\u701c\u701d\u701e\u701f\u7020\u7021\u7022\u7023\u7024\u7025\u7026\u7027\u7028\u7029\u702a\u702b\u702c\u702d\u702e\u702f\u7030\u7031\u7032\u7033\u7034\u7035\u7036\u7037\u7038\u7039\u703a\u703b\u703c\u703d\u703e\u703f\u7040\u7041\u7042\u7043\u7044\u7045\u7046\u7047\u7048\u7049\u704a\u704b\u704c\u704d\u704e\u704f\u7050\u7051\u7052\u7053\u7054\u7055\u7056\u7057\u7058\u7059\u705a\u705b\u705c\u705d\u705e\u705f\u7060\u7061\u7062\u7063\u7064\u7065\u7066\u7067\u7068\u7069\u706a\u706b\u706c\u706d\u706e\u706f\u7070\u7071\u7072\u7073\u7074\u7075\u7076\u7077\u7078\u7079\u707a\u707b\u707c\u707d\u707e\u707f\u7080\u7081\u7082\u7083\u7084\u7085\u7086\u7087\u7088\u7089\u708a\u708b\u708c\u708d\u708e\u708f\u7090\u7091\u7092\u7093\u7094\u7095\u7096\u7097\u7098\u7099\u709a\u709b\u709c\u709d\u709e\u709f\u70a0\u70a1\u70a2\u70a3\u70a4\u70a5\u70a6\u70a7\u70a8\u70a9\u70aa\u70ab\u70ac\u70ad\u70ae\u70af\u70b0\u70b1\u70b2\u70b3\u70b4\u70b5\u70b6\u70b7\u70b8\u70b9\u70ba\u70bb\u70bc\u70bd\u70be\u70bf\u70c0\u70c1\u70c2\u70c3\u70c4\u70c5\u70c6\u70c7\u70c8\u70c9\u70ca\u70cb\u70cc\u70cd\u70ce\u70cf\u70d0\u70d1\u70d2\u70d3\u70d4\u70d5\u70d6\u70d7\u70d8\u70d9\u70da\u70db\u70dc\u70dd\u70de\u70df\u70e0\u70e1\u70e2\u70e3\u70e4\u70e5\u70e6\u70e7\u70e8\u70e9\u70ea\u70eb\u70ec\u70ed\u70ee\u70ef\u70f0\u70f1\u70f2\u70f3\u70f4\u70f5\u70f6\u70f7\u70f8\u70f9\u70fa\u70fb\u70fc\u70fd\u70fe\u70ff\u7100\u7101\u7102\u7103\u7104\u7105\u7106\u7107\u7108\u7109\u710a\u710b\u710c\u710d\u710e\u710f\u7110\u7111\u7112\u7113\u7114\u7115\u7116\u7117\u7118\u7119\u711a\u711b\u711c\u711d\u711e\u711f\u7120\u7121\u7122\u7123\u7124\u7125\u7126\u7127\u7128\u7129\u712a\u712b\u712c\u712d\u712e\u712f\u7130\u7131\u7132\u7133\u7134\u7135\u7136\u7137\u7138\u7139\u713a\u713b\u713c\u713d\u713e\u713f\u7140\u7141\u7142\u7143\u7144\u7145\u7146\u7147\u7148\u7149\u714a\u714b\u714c\u714d\u714e\u714f\u7150\u7151\u7152\u7153\u7154\u7155\u7156\u7157\u7158\u7159\u715a\u715b\u715c\u715d\u715e\u715f\u7160\u7161\u7162\u7163\u7164\u7165\u7166\u7167\u7168\u7169\u716a\u716b\u716c\u716d\u716e\u716f\u7170\u7171\u7172\u7173\u7174\u7175\u7176\u7177\u7178\u7179\u717a\u717b\u717c\u717d\u717e\u717f\u7180\u7181\u7182\u7183\u7184\u7185\u7186\u7187\u7188\u7189\u718a\u718b\u718c\u718d\u718e\u718f\u7190\u7191\u7192\u7193\u7194\u7195\u7196\u7197\u7198\u7199\u719a\u719b\u719c\u719d\u719e\u719f\u71a0\u71a1\u71a2\u71a3\u71a4\u71a5\u71a6\u71a7\u71a8\u71a9\u71aa\u71ab\u71ac\u71ad\u71ae\u71af\u71b0\u71b1\u71b2\u71b3\u71b4\u71b5\u71b6\u71b7\u71b8\u71b9\u71ba\u71bb\u71bc\u71bd\u71be\u71bf\u71c0\u71c1\u71c2\u71c3\u71c4\u71c5\u71c6\u71c7\u71c8\u71c9\u71ca\u71cb\u71cc\u71cd\u71ce\u71cf\u71d0\u71d1\u71d2\u71d3\u71d4\u71d5\u71d6\u71d7\u71d8\u71d9\u71da\u71db\u71dc\u71dd\u71de\u71df\u71e0\u71e1\u71e2\u71e3\u71e4\u71e5\u71e6\u71e7\u71e8\u71e9\u71ea\u71eb\u71ec\u71ed\u71ee\u71ef\u71f0\u71f1\u71f2\u71f3\u71f4\u71f5\u71f6\u71f7\u71f8\u71f9\u71fa\u71fb\u71fc\u71fd\u71fe\u71ff\u7200\u7201\u7202\u7203\u7204\u7205\u7206\u7207\u7208\u7209\u720a\u720b\u720c\u720d\u720e\u720f\u7210\u7211\u7212\u7213\u7214\u7215\u7216\u7217\u7218\u7219\u721a\u721b\u721c\u721d\u721e\u721f\u7220\u7221\u7222\u7223\u7224\u7225\u7226\u7227\u7228\u7229\u722a\u722b\u722c\u722d\u722e\u722f\u7230\u7231\u7232\u7233\u7234\u7235\u7236\u7237\u7238\u7239\u723a\u723b\u723c\u723d\u723e\u723f\u7240\u7241\u7242\u7243\u7244\u7245\u7246\u7247\u7248\u7249\u724a\u724b\u724c\u724d\u724e\u724f\u7250\u7251\u7252\u7253\u7254\u7255\u7256\u7257\u7258\u7259\u725a\u725b\u725c\u725d\u725e\u725f\u7260\u7261\u7262\u7263\u7264\u7265\u7266\u7267\u7268\u7269\u726a\u726b\u726c\u726d\u726e\u726f\u7270\u7271\u7272\u7273\u7274\u7275\u7276\u7277\u7278\u7279\u727a\u727b\u727c\u727d\u727e\u727f\u7280\u7281\u7282\u7283\u7284\u7285\u7286\u7287\u7288\u7289\u728a\u728b\u728c\u728d\u728e\u728f\u7290\u7291\u7292\u7293\u7294\u7295\u7296\u7297\u7298\u7299\u729a\u729b\u729c\u729d\u729e\u729f\u72a0\u72a1\u72a2\u72a3\u72a4\u72a5\u72a6\u72a7\u72a8\u72a9\u72aa\u72ab\u72ac\u72ad\u72ae\u72af\u72b0\u72b1\u72b2\u72b3\u72b4\u72b5\u72b6\u72b7\u72b8\u72b9\u72ba\u72bb\u72bc\u72bd\u72be\u72bf\u72c0\u72c1\u72c2\u72c3\u72c4\u72c5\u72c6\u72c7\u72c8\u72c9\u72ca\u72cb\u72cc\u72cd\u72ce\u72cf\u72d0\u72d1\u72d2\u72d3\u72d4\u72d5\u72d6\u72d7\u72d8\u72d9\u72da\u72db\u72dc\u72dd\u72de\u72df\u72e0\u72e1\u72e2\u72e3\u72e4\u72e5\u72e6\u72e7\u72e8\u72e9\u72ea\u72eb\u72ec\u72ed\u72ee\u72ef\u72f0\u72f1\u72f2\u72f3\u72f4\u72f5\u72f6\u72f7\u72f8\u72f9\u72fa\u72fb\u72fc\u72fd\u72fe\u72ff\u7300\u7301\u7302\u7303\u7304\u7305\u7306\u7307\u7308\u7309\u730a\u730b\u730c\u730d\u730e\u730f\u7310\u7311\u7312\u7313\u7314\u7315\u7316\u7317\u7318\u7319\u731a\u731b\u731c\u731d\u731e\u731f\u7320\u7321\u7322\u7323\u7324\u7325\u7326\u7327\u7328\u7329\u732a\u732b\u732c\u732d\u732e\u732f\u7330\u7331\u7332\u7333\u7334\u7335\u7336\u7337\u7338\u7339\u733a\u733b\u733c\u733d\u733e\u733f\u7340\u7341\u7342\u7343\u7344\u7345\u7346\u7347\u7348\u7349\u734a\u734b\u734c\u734d\u734e\u734f\u7350\u7351\u7352\u7353\u7354\u7355\u7356\u7357\u7358\u7359\u735a\u735b\u735c\u735d\u735e\u735f\u7360\u7361\u7362\u7363\u7364\u7365\u7366\u7367\u7368\u7369\u736a\u736b\u736c\u736d\u736e\u736f\u7370\u7371\u7372\u7373\u7374\u7375\u7376\u7377\u7378\u7379\u737a\u737b\u737c\u737d\u737e\u737f\u7380\u7381\u7382\u7383\u7384\u7385\u7386\u7387\u7388\u7389\u738a\u738b\u738c\u738d\u738e\u738f\u7390\u7391\u7392\u7393\u7394\u7395\u7396\u7397\u7398\u7399\u739a\u739b\u739c\u739d\u739e\u739f\u73a0\u73a1\u73a2\u73a3\u73a4\u73a5\u73a6\u73a7\u73a8\u73a9\u73aa\u73ab\u73ac\u73ad\u73ae\u73af\u73b0\u73b1\u73b2\u73b3\u73b4\u73b5\u73b6\u73b7\u73b8\u73b9\u73ba\u73bb\u73bc\u73bd\u73be\u73bf\u73c0\u73c1\u73c2\u73c3\u73c4\u73c5\u73c6\u73c7\u73c8\u73c9\u73ca\u73cb\u73cc\u73cd\u73ce\u73cf\u73d0\u73d1\u73d2\u73d3\u73d4\u73d5\u73d6\u73d7\u73d8\u73d9\u73da\u73db\u73dc\u73dd\u73de\u73df\u73e0\u73e1\u73e2\u73e3\u73e4\u73e5\u73e6\u73e7\u73e8\u73e9\u73ea\u73eb\u73ec\u73ed\u73ee\u73ef\u73f0\u73f1\u73f2\u73f3\u73f4\u73f5\u73f6\u73f7\u73f8\u73f9\u73fa\u73fb\u73fc\u73fd\u73fe\u73ff\u7400\u7401\u7402\u7403\u7404\u7405\u7406\u7407\u7408\u7409\u740a\u740b\u740c\u740d\u740e\u740f\u7410\u7411\u7412\u7413\u7414\u7415\u7416\u7417\u7418\u7419\u741a\u741b\u741c\u741d\u741e\u741f\u7420\u7421\u7422\u7423\u7424\u7425\u7426\u7427\u7428\u7429\u742a\u742b\u742c\u742d\u742e\u742f\u7430\u7431\u7432\u7433\u7434\u7435\u7436\u7437\u7438\u7439\u743a\u743b\u743c\u743d\u743e\u743f\u7440\u7441\u7442\u7443\u7444\u7445\u7446\u7447\u7448\u7449\u744a\u744b\u744c\u744d\u744e\u744f\u7450\u7451\u7452\u7453\u7454\u7455\u7456\u7457\u7458\u7459\u745a\u745b\u745c\u745d\u745e\u745f\u7460\u7461\u7462\u7463\u7464\u7465\u7466\u7467\u7468\u7469\u746a\u746b\u746c\u746d\u746e\u746f\u7470\u7471\u7472\u7473\u7474\u7475\u7476\u7477\u7478\u7479\u747a\u747b\u747c\u747d\u747e\u747f\u7480\u7481\u7482\u7483\u7484\u7485\u7486\u7487\u7488\u7489\u748a\u748b\u748c\u748d\u748e\u748f\u7490\u7491\u7492\u7493\u7494\u7495\u7496\u7497\u7498\u7499\u749a\u749b\u749c\u749d\u749e\u749f\u74a0\u74a1\u74a2\u74a3\u74a4\u74a5\u74a6\u74a7\u74a8\u74a9\u74aa\u74ab\u74ac\u74ad\u74ae\u74af\u74b0\u74b1\u74b2\u74b3\u74b4\u74b5\u74b6\u74b7\u74b8\u74b9\u74ba\u74bb\u74bc\u74bd\u74be\u74bf\u74c0\u74c1\u74c2\u74c3\u74c4\u74c5\u74c6\u74c7\u74c8\u74c9\u74ca\u74cb\u74cc\u74cd\u74ce\u74cf\u74d0\u74d1\u74d2\u74d3\u74d4\u74d5\u74d6\u74d7\u74d8\u74d9\u74da\u74db\u74dc\u74dd\u74de\u74df\u74e0\u74e1\u74e2\u74e3\u74e4\u74e5\u74e6\u74e7\u74e8\u74e9\u74ea\u74eb\u74ec\u74ed\u74ee\u74ef\u74f0\u74f1\u74f2\u74f3\u74f4\u74f5\u74f6\u74f7\u74f8\u74f9\u74fa\u74fb\u74fc\u74fd\u74fe\u74ff\u7500\u7501\u7502\u7503\u7504\u7505\u7506\u7507\u7508\u7509\u750a\u750b\u750c\u750d\u750e\u750f\u7510\u7511\u7512\u7513\u7514\u7515\u7516\u7517\u7518\u7519\u751a\u751b\u751c\u751d\u751e\u751f\u7520\u7521\u7522\u7523\u7524\u7525\u7526\u7527\u7528\u7529\u752a\u752b\u752c\u752d\u752e\u752f\u7530\u7531\u7532\u7533\u7534\u7535\u7536\u7537\u7538\u7539\u753a\u753b\u753c\u753d\u753e\u753f\u7540\u7541\u7542\u7543\u7544\u7545\u7546\u7547\u7548\u7549\u754a\u754b\u754c\u754d\u754e\u754f\u7550\u7551\u7552\u7553\u7554\u7555\u7556\u7557\u7558\u7559\u755a\u755b\u755c\u755d\u755e\u755f\u7560\u7561\u7562\u7563\u7564\u7565\u7566\u7567\u7568\u7569\u756a\u756b\u756c\u756d\u756e\u756f\u7570\u7571\u7572\u7573\u7574\u7575\u7576\u7577\u7578\u7579\u757a\u757b\u757c\u757d\u757e\u757f\u7580\u7581\u7582\u7583\u7584\u7585\u7586\u7587\u7588\u7589\u758a\u758b\u758c\u758d\u758e\u758f\u7590\u7591\u7592\u7593\u7594\u7595\u7596\u7597\u7598\u7599\u759a\u759b\u759c\u759d\u759e\u759f\u75a0\u75a1\u75a2\u75a3\u75a4\u75a5\u75a6\u75a7\u75a8\u75a9\u75aa\u75ab\u75ac\u75ad\u75ae\u75af\u75b0\u75b1\u75b2\u75b3\u75b4\u75b5\u75b6\u75b7\u75b8\u75b9\u75ba\u75bb\u75bc\u75bd\u75be\u75bf\u75c0\u75c1\u75c2\u75c3\u75c4\u75c5\u75c6\u75c7\u75c8\u75c9\u75ca\u75cb\u75cc\u75cd\u75ce\u75cf\u75d0\u75d1\u75d2\u75d3\u75d4\u75d5\u75d6\u75d7\u75d8\u75d9\u75da\u75db\u75dc\u75dd\u75de\u75df\u75e0\u75e1\u75e2\u75e3\u75e4\u75e5\u75e6\u75e7\u75e8\u75e9\u75ea\u75eb\u75ec\u75ed\u75ee\u75ef\u75f0\u75f1\u75f2\u75f3\u75f4\u75f5\u75f6\u75f7\u75f8\u75f9\u75fa\u75fb\u75fc\u75fd\u75fe\u75ff\u7600\u7601\u7602\u7603\u7604\u7605\u7606\u7607\u7608\u7609\u760a\u760b\u760c\u760d\u760e\u760f\u7610\u7611\u7612\u7613\u7614\u7615\u7616\u7617\u7618\u7619\u761a\u761b\u761c\u761d\u761e\u761f\u7620\u7621\u7622\u7623\u7624\u7625\u7626\u7627\u7628\u7629\u762a\u762b\u762c\u762d\u762e\u762f\u7630\u7631\u7632\u7633\u7634\u7635\u7636\u7637\u7638\u7639\u763a\u763b\u763c\u763d\u763e\u763f\u7640\u7641\u7642\u7643\u7644\u7645\u7646\u7647\u7648\u7649\u764a\u764b\u764c\u764d\u764e\u764f\u7650\u7651\u7652\u7653\u7654\u7655\u7656\u7657\u7658\u7659\u765a\u765b\u765c\u765d\u765e\u765f\u7660\u7661\u7662\u7663\u7664\u7665\u7666\u7667\u7668\u7669\u766a\u766b\u766c\u766d\u766e\u766f\u7670\u7671\u7672\u7673\u7674\u7675\u7676\u7677\u7678\u7679\u767a\u767b\u767c\u767d\u767e\u767f\u7680\u7681\u7682\u7683\u7684\u7685\u7686\u7687\u7688\u7689\u768a\u768b\u768c\u768d\u768e\u768f\u7690\u7691\u7692\u7693\u7694\u7695\u7696\u7697\u7698\u7699\u769a\u769b\u769c\u769d\u769e\u769f\u76a0\u76a1\u76a2\u76a3\u76a4\u76a5\u76a6\u76a7\u76a8\u76a9\u76aa\u76ab\u76ac\u76ad\u76ae\u76af\u76b0\u76b1\u76b2\u76b3\u76b4\u76b5\u76b6\u76b7\u76b8\u76b9\u76ba\u76bb\u76bc\u76bd\u76be\u76bf\u76c0\u76c1\u76c2\u76c3\u76c4\u76c5\u76c6\u76c7\u76c8\u76c9\u76ca\u76cb\u76cc\u76cd\u76ce\u76cf\u76d0\u76d1\u76d2\u76d3\u76d4\u76d5\u76d6\u76d7\u76d8\u76d9\u76da\u76db\u76dc\u76dd\u76de\u76df\u76e0\u76e1\u76e2\u76e3\u76e4\u76e5\u76e6\u76e7\u76e8\u76e9\u76ea\u76eb\u76ec\u76ed\u76ee\u76ef\u76f0\u76f1\u76f2\u76f3\u76f4\u76f5\u76f6\u76f7\u76f8\u76f9\u76fa\u76fb\u76fc\u76fd\u76fe\u76ff\u7700\u7701\u7702\u7703\u7704\u7705\u7706\u7707\u7708\u7709\u770a\u770b\u770c\u770d\u770e\u770f\u7710\u7711\u7712\u7713\u7714\u7715\u7716\u7717\u7718\u7719\u771a\u771b\u771c\u771d\u771e\u771f\u7720\u7721\u7722\u7723\u7724\u7725\u7726\u7727\u7728\u7729\u772a\u772b\u772c\u772d\u772e\u772f\u7730\u7731\u7732\u7733\u7734\u7735\u7736\u7737\u7738\u7739\u773a\u773b\u773c\u773d\u773e\u773f\u7740\u7741\u7742\u7743\u7744\u7745\u7746\u7747\u7748\u7749\u774a\u774b\u774c\u774d\u774e\u774f\u7750\u7751\u7752\u7753\u7754\u7755\u7756\u7757\u7758\u7759\u775a\u775b\u775c\u775d\u775e\u775f\u7760\u7761\u7762\u7763\u7764\u7765\u7766\u7767\u7768\u7769\u776a\u776b\u776c\u776d\u776e\u776f\u7770\u7771\u7772\u7773\u7774\u7775\u7776\u7777\u7778\u7779\u777a\u777b\u777c\u777d\u777e\u777f\u7780\u7781\u7782\u7783\u7784\u7785\u7786\u7787\u7788\u7789\u778a\u778b\u778c\u778d\u778e\u778f\u7790\u7791\u7792\u7793\u7794\u7795\u7796\u7797\u7798\u7799\u779a\u779b\u779c\u779d\u779e\u779f\u77a0\u77a1\u77a2\u77a3\u77a4\u77a5\u77a6\u77a7\u77a8\u77a9\u77aa\u77ab\u77ac\u77ad\u77ae\u77af\u77b0\u77b1\u77b2\u77b3\u77b4\u77b5\u77b6\u77b7\u77b8\u77b9\u77ba\u77bb\u77bc\u77bd\u77be\u77bf\u77c0\u77c1\u77c2\u77c3\u77c4\u77c5\u77c6\u77c7\u77c8\u77c9\u77ca\u77cb\u77cc\u77cd\u77ce\u77cf\u77d0\u77d1\u77d2\u77d3\u77d4\u77d5\u77d6\u77d7\u77d8\u77d9\u77da\u77db\u77dc\u77dd\u77de\u77df\u77e0\u77e1\u77e2\u77e3\u77e4\u77e5\u77e6\u77e7\u77e8\u77e9\u77ea\u77eb\u77ec\u77ed\u77ee\u77ef\u77f0\u77f1\u77f2\u77f3\u77f4\u77f5\u77f6\u77f7\u77f8\u77f9\u77fa\u77fb\u77fc\u77fd\u77fe\u77ff\u7800\u7801\u7802\u7803\u7804\u7805\u7806\u7807\u7808\u7809\u780a\u780b\u780c\u780d\u780e\u780f\u7810\u7811\u7812\u7813\u7814\u7815\u7816\u7817\u7818\u7819\u781a\u781b\u781c\u781d\u781e\u781f\u7820\u7821\u7822\u7823\u7824\u7825\u7826\u7827\u7828\u7829\u782a\u782b\u782c\u782d\u782e\u782f\u7830\u7831\u7832\u7833\u7834\u7835\u7836\u7837\u7838\u7839\u783a\u783b\u783c\u783d\u783e\u783f\u7840\u7841\u7842\u7843\u7844\u7845\u7846\u7847\u7848\u7849\u784a\u784b\u784c\u784d\u784e\u784f\u7850\u7851\u7852\u7853\u7854\u7855\u7856\u7857\u7858\u7859\u785a\u785b\u785c\u785d\u785e\u785f\u7860\u7861\u7862\u7863\u7864\u7865\u7866\u7867\u7868\u7869\u786a\u786b\u786c\u786d\u786e\u786f\u7870\u7871\u7872\u7873\u7874\u7875\u7876\u7877\u7878\u7879\u787a\u787b\u787c\u787d\u787e\u787f\u7880\u7881\u7882\u7883\u7884\u7885\u7886\u7887\u7888\u7889\u788a\u788b\u788c\u788d\u788e\u788f\u7890\u7891\u7892\u7893\u7894\u7895\u7896\u7897\u7898\u7899\u789a\u789b\u789c\u789d\u789e\u789f\u78a0\u78a1\u78a2\u78a3\u78a4\u78a5\u78a6\u78a7\u78a8\u78a9\u78aa\u78ab\u78ac\u78ad\u78ae\u78af\u78b0\u78b1\u78b2\u78b3\u78b4\u78b5\u78b6\u78b7\u78b8\u78b9\u78ba\u78bb\u78bc\u78bd\u78be\u78bf\u78c0\u78c1\u78c2\u78c3\u78c4\u78c5\u78c6\u78c7\u78c8\u78c9\u78ca\u78cb\u78cc\u78cd\u78ce\u78cf\u78d0\u78d1\u78d2\u78d3\u78d4\u78d5\u78d6\u78d7\u78d8\u78d9\u78da\u78db\u78dc\u78dd\u78de\u78df\u78e0\u78e1\u78e2\u78e3\u78e4\u78e5\u78e6\u78e7\u78e8\u78e9\u78ea\u78eb\u78ec\u78ed\u78ee\u78ef\u78f0\u78f1\u78f2\u78f3\u78f4\u78f5\u78f6\u78f7\u78f8\u78f9\u78fa\u78fb\u78fc\u78fd\u78fe\u78ff\u7900\u7901\u7902\u7903\u7904\u7905\u7906\u7907\u7908\u7909\u790a\u790b\u790c\u790d\u790e\u790f\u7910\u7911\u7912\u7913\u7914\u7915\u7916\u7917\u7918\u7919\u791a\u791b\u791c\u791d\u791e\u791f\u7920\u7921\u7922\u7923\u7924\u7925\u7926\u7927\u7928\u7929\u792a\u792b\u792c\u792d\u792e\u792f\u7930\u7931\u7932\u7933\u7934\u7935\u7936\u7937\u7938\u7939\u793a\u793b\u793c\u793d\u793e\u793f\u7940\u7941\u7942\u7943\u7944\u7945\u7946\u7947\u7948\u7949\u794a\u794b\u794c\u794d\u794e\u794f\u7950\u7951\u7952\u7953\u7954\u7955\u7956\u7957\u7958\u7959\u795a\u795b\u795c\u795d\u795e\u795f\u7960\u7961\u7962\u7963\u7964\u7965\u7966\u7967\u7968\u7969\u796a\u796b\u796c\u796d\u796e\u796f\u7970\u7971\u7972\u7973\u7974\u7975\u7976\u7977\u7978\u7979\u797a\u797b\u797c\u797d\u797e\u797f\u7980\u7981\u7982\u7983\u7984\u7985\u7986\u7987\u7988\u7989\u798a\u798b\u798c\u798d\u798e\u798f\u7990\u7991\u7992\u7993\u7994\u7995\u7996\u7997\u7998\u7999\u799a\u799b\u799c\u799d\u799e\u799f\u79a0\u79a1\u79a2\u79a3\u79a4\u79a5\u79a6\u79a7\u79a8\u79a9\u79aa\u79ab\u79ac\u79ad\u79ae\u79af\u79b0\u79b1\u79b2\u79b3\u79b4\u79b5\u79b6\u79b7\u79b8\u79b9\u79ba\u79bb\u79bc\u79bd\u79be\u79bf\u79c0\u79c1\u79c2\u79c3\u79c4\u79c5\u79c6\u79c7\u79c8\u79c9\u79ca\u79cb\u79cc\u79cd\u79ce\u79cf\u79d0\u79d1\u79d2\u79d3\u79d4\u79d5\u79d6\u79d7\u79d8\u79d9\u79da\u79db\u79dc\u79dd\u79de\u79df\u79e0\u79e1\u79e2\u79e3\u79e4\u79e5\u79e6\u79e7\u79e8\u79e9\u79ea\u79eb\u79ec\u79ed\u79ee\u79ef\u79f0\u79f1\u79f2\u79f3\u79f4\u79f5\u79f6\u79f7\u79f8\u79f9\u79fa\u79fb\u79fc\u79fd\u79fe\u79ff\u7a00\u7a01\u7a02\u7a03\u7a04\u7a05\u7a06\u7a07\u7a08\u7a09\u7a0a\u7a0b\u7a0c\u7a0d\u7a0e\u7a0f\u7a10\u7a11\u7a12\u7a13\u7a14\u7a15\u7a16\u7a17\u7a18\u7a19\u7a1a\u7a1b\u7a1c\u7a1d\u7a1e\u7a1f\u7a20\u7a21\u7a22\u7a23\u7a24\u7a25\u7a26\u7a27\u7a28\u7a29\u7a2a\u7a2b\u7a2c\u7a2d\u7a2e\u7a2f\u7a30\u7a31\u7a32\u7a33\u7a34\u7a35\u7a36\u7a37\u7a38\u7a39\u7a3a\u7a3b\u7a3c\u7a3d\u7a3e\u7a3f\u7a40\u7a41\u7a42\u7a43\u7a44\u7a45\u7a46\u7a47\u7a48\u7a49\u7a4a\u7a4b\u7a4c\u7a4d\u7a4e\u7a4f\u7a50\u7a51\u7a52\u7a53\u7a54\u7a55\u7a56\u7a57\u7a58\u7a59\u7a5a\u7a5b\u7a5c\u7a5d\u7a5e\u7a5f\u7a60\u7a61\u7a62\u7a63\u7a64\u7a65\u7a66\u7a67\u7a68\u7a69\u7a6a\u7a6b\u7a6c\u7a6d\u7a6e\u7a6f\u7a70\u7a71\u7a72\u7a73\u7a74\u7a75\u7a76\u7a77\u7a78\u7a79\u7a7a\u7a7b\u7a7c\u7a7d\u7a7e\u7a7f\u7a80\u7a81\u7a82\u7a83\u7a84\u7a85\u7a86\u7a87\u7a88\u7a89\u7a8a\u7a8b\u7a8c\u7a8d\u7a8e\u7a8f\u7a90\u7a91\u7a92\u7a93\u7a94\u7a95\u7a96\u7a97\u7a98\u7a99\u7a9a\u7a9b\u7a9c\u7a9d\u7a9e\u7a9f\u7aa0\u7aa1\u7aa2\u7aa3\u7aa4\u7aa5\u7aa6\u7aa7\u7aa8\u7aa9\u7aaa\u7aab\u7aac\u7aad\u7aae\u7aaf\u7ab0\u7ab1\u7ab2\u7ab3\u7ab4\u7ab5\u7ab6\u7ab7\u7ab8\u7ab9\u7aba\u7abb\u7abc\u7abd\u7abe\u7abf\u7ac0\u7ac1\u7ac2\u7ac3\u7ac4\u7ac5\u7ac6\u7ac7\u7ac8\u7ac9\u7aca\u7acb\u7acc\u7acd\u7ace\u7acf\u7ad0\u7ad1\u7ad2\u7ad3\u7ad4\u7ad5\u7ad6\u7ad7\u7ad8\u7ad9\u7ada\u7adb\u7adc\u7add\u7ade\u7adf\u7ae0\u7ae1\u7ae2\u7ae3\u7ae4\u7ae5\u7ae6\u7ae7\u7ae8\u7ae9\u7aea\u7aeb\u7aec\u7aed\u7aee\u7aef\u7af0\u7af1\u7af2\u7af3\u7af4\u7af5\u7af6\u7af7\u7af8\u7af9\u7afa\u7afb\u7afc\u7afd\u7afe\u7aff\u7b00\u7b01\u7b02\u7b03\u7b04\u7b05\u7b06\u7b07\u7b08\u7b09\u7b0a\u7b0b\u7b0c\u7b0d\u7b0e\u7b0f\u7b10\u7b11\u7b12\u7b13\u7b14\u7b15\u7b16\u7b17\u7b18\u7b19\u7b1a\u7b1b\u7b1c\u7b1d\u7b1e\u7b1f\u7b20\u7b21\u7b22\u7b23\u7b24\u7b25\u7b26\u7b27\u7b28\u7b29\u7b2a\u7b2b\u7b2c\u7b2d\u7b2e\u7b2f\u7b30\u7b31\u7b32\u7b33\u7b34\u7b35\u7b36\u7b37\u7b38\u7b39\u7b3a\u7b3b\u7b3c\u7b3d\u7b3e\u7b3f\u7b40\u7b41\u7b42\u7b43\u7b44\u7b45\u7b46\u7b47\u7b48\u7b49\u7b4a\u7b4b\u7b4c\u7b4d\u7b4e\u7b4f\u7b50\u7b51\u7b52\u7b53\u7b54\u7b55\u7b56\u7b57\u7b58\u7b59\u7b5a\u7b5b\u7b5c\u7b5d\u7b5e\u7b5f\u7b60\u7b61\u7b62\u7b63\u7b64\u7b65\u7b66\u7b67\u7b68\u7b69\u7b6a\u7b6b\u7b6c\u7b6d\u7b6e\u7b6f\u7b70\u7b71\u7b72\u7b73\u7b74\u7b75\u7b76\u7b77\u7b78\u7b79\u7b7a\u7b7b\u7b7c\u7b7d\u7b7e\u7b7f\u7b80\u7b81\u7b82\u7b83\u7b84\u7b85\u7b86\u7b87\u7b88\u7b89\u7b8a\u7b8b\u7b8c\u7b8d\u7b8e\u7b8f\u7b90\u7b91\u7b92\u7b93\u7b94\u7b95\u7b96\u7b97\u7b98\u7b99\u7b9a\u7b9b\u7b9c\u7b9d\u7b9e\u7b9f\u7ba0\u7ba1\u7ba2\u7ba3\u7ba4\u7ba5\u7ba6\u7ba7\u7ba8\u7ba9\u7baa\u7bab\u7bac\u7bad\u7bae\u7baf\u7bb0\u7bb1\u7bb2\u7bb3\u7bb4\u7bb5\u7bb6\u7bb7\u7bb8\u7bb9\u7bba\u7bbb\u7bbc\u7bbd\u7bbe\u7bbf\u7bc0\u7bc1\u7bc2\u7bc3\u7bc4\u7bc5\u7bc6\u7bc7\u7bc8\u7bc9\u7bca\u7bcb\u7bcc\u7bcd\u7bce\u7bcf\u7bd0\u7bd1\u7bd2\u7bd3\u7bd4\u7bd5\u7bd6\u7bd7\u7bd8\u7bd9\u7bda\u7bdb\u7bdc\u7bdd\u7bde\u7bdf\u7be0\u7be1\u7be2\u7be3\u7be4\u7be5\u7be6\u7be7\u7be8\u7be9\u7bea\u7beb\u7bec\u7bed\u7bee\u7bef\u7bf0\u7bf1\u7bf2\u7bf3\u7bf4\u7bf5\u7bf6\u7bf7\u7bf8\u7bf9\u7bfa\u7bfb\u7bfc\u7bfd\u7bfe\u7bff\u7c00\u7c01\u7c02\u7c03\u7c04\u7c05\u7c06\u7c07\u7c08\u7c09\u7c0a\u7c0b\u7c0c\u7c0d\u7c0e\u7c0f\u7c10\u7c11\u7c12\u7c13\u7c14\u7c15\u7c16\u7c17\u7c18\u7c19\u7c1a\u7c1b\u7c1c\u7c1d\u7c1e\u7c1f\u7c20\u7c21\u7c22\u7c23\u7c24\u7c25\u7c26\u7c27\u7c28\u7c29\u7c2a\u7c2b\u7c2c\u7c2d\u7c2e\u7c2f\u7c30\u7c31\u7c32\u7c33\u7c34\u7c35\u7c36\u7c37\u7c38\u7c39\u7c3a\u7c3b\u7c3c\u7c3d\u7c3e\u7c3f\u7c40\u7c41\u7c42\u7c43\u7c44\u7c45\u7c46\u7c47\u7c48\u7c49\u7c4a\u7c4b\u7c4c\u7c4d\u7c4e\u7c4f\u7c50\u7c51\u7c52\u7c53\u7c54\u7c55\u7c56\u7c57\u7c58\u7c59\u7c5a\u7c5b\u7c5c\u7c5d\u7c5e\u7c5f\u7c60\u7c61\u7c62\u7c63\u7c64\u7c65\u7c66\u7c67\u7c68\u7c69\u7c6a\u7c6b\u7c6c\u7c6d\u7c6e\u7c6f\u7c70\u7c71\u7c72\u7c73\u7c74\u7c75\u7c76\u7c77\u7c78\u7c79\u7c7a\u7c7b\u7c7c\u7c7d\u7c7e\u7c7f\u7c80\u7c81\u7c82\u7c83\u7c84\u7c85\u7c86\u7c87\u7c88\u7c89\u7c8a\u7c8b\u7c8c\u7c8d\u7c8e\u7c8f\u7c90\u7c91\u7c92\u7c93\u7c94\u7c95\u7c96\u7c97\u7c98\u7c99\u7c9a\u7c9b\u7c9c\u7c9d\u7c9e\u7c9f\u7ca0\u7ca1\u7ca2\u7ca3\u7ca4\u7ca5\u7ca6\u7ca7\u7ca8\u7ca9\u7caa\u7cab\u7cac\u7cad\u7cae\u7caf\u7cb0\u7cb1\u7cb2\u7cb3\u7cb4\u7cb5\u7cb6\u7cb7\u7cb8\u7cb9\u7cba\u7cbb\u7cbc\u7cbd\u7cbe\u7cbf\u7cc0\u7cc1\u7cc2\u7cc3\u7cc4\u7cc5\u7cc6\u7cc7\u7cc8\u7cc9\u7cca\u7ccb\u7ccc\u7ccd\u7cce\u7ccf\u7cd0\u7cd1\u7cd2\u7cd3\u7cd4\u7cd5\u7cd6\u7cd7\u7cd8\u7cd9\u7cda\u7cdb\u7cdc\u7cdd\u7cde\u7cdf\u7ce0\u7ce1\u7ce2\u7ce3\u7ce4\u7ce5\u7ce6\u7ce7\u7ce8\u7ce9\u7cea\u7ceb\u7cec\u7ced\u7cee\u7cef\u7cf0\u7cf1\u7cf2\u7cf3\u7cf4\u7cf5\u7cf6\u7cf7\u7cf8\u7cf9\u7cfa\u7cfb\u7cfc\u7cfd\u7cfe\u7cff\u7d00\u7d01\u7d02\u7d03\u7d04\u7d05\u7d06\u7d07\u7d08\u7d09\u7d0a\u7d0b\u7d0c\u7d0d\u7d0e\u7d0f\u7d10\u7d11\u7d12\u7d13\u7d14\u7d15\u7d16\u7d17\u7d18\u7d19\u7d1a\u7d1b\u7d1c\u7d1d\u7d1e\u7d1f\u7d20\u7d21\u7d22\u7d23\u7d24\u7d25\u7d26\u7d27\u7d28\u7d29\u7d2a\u7d2b\u7d2c\u7d2d\u7d2e\u7d2f\u7d30\u7d31\u7d32\u7d33\u7d34\u7d35\u7d36\u7d37\u7d38\u7d39\u7d3a\u7d3b\u7d3c\u7d3d\u7d3e\u7d3f\u7d40\u7d41\u7d42\u7d43\u7d44\u7d45\u7d46\u7d47\u7d48\u7d49\u7d4a\u7d4b\u7d4c\u7d4d\u7d4e\u7d4f\u7d50\u7d51\u7d52\u7d53\u7d54\u7d55\u7d56\u7d57\u7d58\u7d59\u7d5a\u7d5b\u7d5c\u7d5d\u7d5e\u7d5f\u7d60\u7d61\u7d62\u7d63\u7d64\u7d65\u7d66\u7d67\u7d68\u7d69\u7d6a\u7d6b\u7d6c\u7d6d\u7d6e\u7d6f\u7d70\u7d71\u7d72\u7d73\u7d74\u7d75\u7d76\u7d77\u7d78\u7d79\u7d7a\u7d7b\u7d7c\u7d7d\u7d7e\u7d7f\u7d80\u7d81\u7d82\u7d83\u7d84\u7d85\u7d86\u7d87\u7d88\u7d89\u7d8a\u7d8b\u7d8c\u7d8d\u7d8e\u7d8f\u7d90\u7d91\u7d92\u7d93\u7d94\u7d95\u7d96\u7d97\u7d98\u7d99\u7d9a\u7d9b\u7d9c\u7d9d\u7d9e\u7d9f\u7da0\u7da1\u7da2\u7da3\u7da4\u7da5\u7da6\u7da7\u7da8\u7da9\u7daa\u7dab\u7dac\u7dad\u7dae\u7daf\u7db0\u7db1\u7db2\u7db3\u7db4\u7db5\u7db6\u7db7\u7db8\u7db9\u7dba\u7dbb\u7dbc\u7dbd\u7dbe\u7dbf\u7dc0\u7dc1\u7dc2\u7dc3\u7dc4\u7dc5\u7dc6\u7dc7\u7dc8\u7dc9\u7dca\u7dcb\u7dcc\u7dcd\u7dce\u7dcf\u7dd0\u7dd1\u7dd2\u7dd3\u7dd4\u7dd5\u7dd6\u7dd7\u7dd8\u7dd9\u7dda\u7ddb\u7ddc\u7ddd\u7dde\u7ddf\u7de0\u7de1\u7de2\u7de3\u7de4\u7de5\u7de6\u7de7\u7de8\u7de9\u7dea\u7deb\u7dec\u7ded\u7dee\u7def\u7df0\u7df1\u7df2\u7df3\u7df4\u7df5\u7df6\u7df7\u7df8\u7df9\u7dfa\u7dfb\u7dfc\u7dfd\u7dfe\u7dff\u7e00\u7e01\u7e02\u7e03\u7e04\u7e05\u7e06\u7e07\u7e08\u7e09\u7e0a\u7e0b\u7e0c\u7e0d\u7e0e\u7e0f\u7e10\u7e11\u7e12\u7e13\u7e14\u7e15\u7e16\u7e17\u7e18\u7e19\u7e1a\u7e1b\u7e1c\u7e1d\u7e1e\u7e1f\u7e20\u7e21\u7e22\u7e23\u7e24\u7e25\u7e26\u7e27\u7e28\u7e29\u7e2a\u7e2b\u7e2c\u7e2d\u7e2e\u7e2f\u7e30\u7e31\u7e32\u7e33\u7e34\u7e35\u7e36\u7e37\u7e38\u7e39\u7e3a\u7e3b\u7e3c\u7e3d\u7e3e\u7e3f\u7e40\u7e41\u7e42\u7e43\u7e44\u7e45\u7e46\u7e47\u7e48\u7e49\u7e4a\u7e4b\u7e4c\u7e4d\u7e4e\u7e4f\u7e50\u7e51\u7e52\u7e53\u7e54\u7e55\u7e56\u7e57\u7e58\u7e59\u7e5a\u7e5b\u7e5c\u7e5d\u7e5e\u7e5f\u7e60\u7e61\u7e62\u7e63\u7e64\u7e65\u7e66\u7e67\u7e68\u7e69\u7e6a\u7e6b\u7e6c\u7e6d\u7e6e\u7e6f\u7e70\u7e71\u7e72\u7e73\u7e74\u7e75\u7e76\u7e77\u7e78\u7e79\u7e7a\u7e7b\u7e7c\u7e7d\u7e7e\u7e7f\u7e80\u7e81\u7e82\u7e83\u7e84\u7e85\u7e86\u7e87\u7e88\u7e89\u7e8a\u7e8b\u7e8c\u7e8d\u7e8e\u7e8f\u7e90\u7e91\u7e92\u7e93\u7e94\u7e95\u7e96\u7e97\u7e98\u7e99\u7e9a\u7e9b\u7e9c\u7e9d\u7e9e\u7e9f\u7ea0\u7ea1\u7ea2\u7ea3\u7ea4\u7ea5\u7ea6\u7ea7\u7ea8\u7ea9\u7eaa\u7eab\u7eac\u7ead\u7eae\u7eaf\u7eb0\u7eb1\u7eb2\u7eb3\u7eb4\u7eb5\u7eb6\u7eb7\u7eb8\u7eb9\u7eba\u7ebb\u7ebc\u7ebd\u7ebe\u7ebf\u7ec0\u7ec1\u7ec2\u7ec3\u7ec4\u7ec5\u7ec6\u7ec7\u7ec8\u7ec9\u7eca\u7ecb\u7ecc\u7ecd\u7ece\u7ecf\u7ed0\u7ed1\u7ed2\u7ed3\u7ed4\u7ed5\u7ed6\u7ed7\u7ed8\u7ed9\u7eda\u7edb\u7edc\u7edd\u7ede\u7edf\u7ee0\u7ee1\u7ee2\u7ee3\u7ee4\u7ee5\u7ee6\u7ee7\u7ee8\u7ee9\u7eea\u7eeb\u7eec\u7eed\u7eee\u7eef\u7ef0\u7ef1\u7ef2\u7ef3\u7ef4\u7ef5\u7ef6\u7ef7\u7ef8\u7ef9\u7efa\u7efb\u7efc\u7efd\u7efe\u7eff\u7f00\u7f01\u7f02\u7f03\u7f04\u7f05\u7f06\u7f07\u7f08\u7f09\u7f0a\u7f0b\u7f0c\u7f0d\u7f0e\u7f0f\u7f10\u7f11\u7f12\u7f13\u7f14\u7f15\u7f16\u7f17\u7f18\u7f19\u7f1a\u7f1b\u7f1c\u7f1d\u7f1e\u7f1f\u7f20\u7f21\u7f22\u7f23\u7f24\u7f25\u7f26\u7f27\u7f28\u7f29\u7f2a\u7f2b\u7f2c\u7f2d\u7f2e\u7f2f\u7f30\u7f31\u7f32\u7f33\u7f34\u7f35\u7f36\u7f37\u7f38\u7f39\u7f3a\u7f3b\u7f3c\u7f3d\u7f3e\u7f3f\u7f40\u7f41\u7f42\u7f43\u7f44\u7f45\u7f46\u7f47\u7f48\u7f49\u7f4a\u7f4b\u7f4c\u7f4d\u7f4e\u7f4f\u7f50\u7f51\u7f52\u7f53\u7f54\u7f55\u7f56\u7f57\u7f58\u7f59\u7f5a\u7f5b\u7f5c\u7f5d\u7f5e\u7f5f\u7f60\u7f61\u7f62\u7f63\u7f64\u7f65\u7f66\u7f67\u7f68\u7f69\u7f6a\u7f6b\u7f6c\u7f6d\u7f6e\u7f6f\u7f70\u7f71\u7f72\u7f73\u7f74\u7f75\u7f76\u7f77\u7f78\u7f79\u7f7a\u7f7b\u7f7c\u7f7d\u7f7e\u7f7f\u7f80\u7f81\u7f82\u7f83\u7f84\u7f85\u7f86\u7f87\u7f88\u7f89\u7f8a\u7f8b\u7f8c\u7f8d\u7f8e\u7f8f\u7f90\u7f91\u7f92\u7f93\u7f94\u7f95\u7f96\u7f97\u7f98\u7f99\u7f9a\u7f9b\u7f9c\u7f9d\u7f9e\u7f9f\u7fa0\u7fa1\u7fa2\u7fa3\u7fa4\u7fa5\u7fa6\u7fa7\u7fa8\u7fa9\u7faa\u7fab\u7fac\u7fad\u7fae\u7faf\u7fb0\u7fb1\u7fb2\u7fb3\u7fb4\u7fb5\u7fb6\u7fb7\u7fb8\u7fb9\u7fba\u7fbb\u7fbc\u7fbd\u7fbe\u7fbf\u7fc0\u7fc1\u7fc2\u7fc3\u7fc4\u7fc5\u7fc6\u7fc7\u7fc8\u7fc9\u7fca\u7fcb\u7fcc\u7fcd\u7fce\u7fcf\u7fd0\u7fd1\u7fd2\u7fd3\u7fd4\u7fd5\u7fd6\u7fd7\u7fd8\u7fd9\u7fda\u7fdb\u7fdc\u7fdd\u7fde\u7fdf\u7fe0\u7fe1\u7fe2\u7fe3\u7fe4\u7fe5\u7fe6\u7fe7\u7fe8\u7fe9\u7fea\u7feb\u7fec\u7fed\u7fee\u7fef\u7ff0\u7ff1\u7ff2\u7ff3\u7ff4\u7ff5\u7ff6\u7ff7\u7ff8\u7ff9\u7ffa\u7ffb\u7ffc\u7ffd\u7ffe\u7fff\u8000\u8001\u8002\u8003\u8004\u8005\u8006\u8007\u8008\u8009\u800a\u800b\u800c\u800d\u800e\u800f\u8010\u8011\u8012\u8013\u8014\u8015\u8016\u8017\u8018\u8019\u801a\u801b\u801c\u801d\u801e\u801f\u8020\u8021\u8022\u8023\u8024\u8025\u8026\u8027\u8028\u8029\u802a\u802b\u802c\u802d\u802e\u802f\u8030\u8031\u8032\u8033\u8034\u8035\u8036\u8037\u8038\u8039\u803a\u803b\u803c\u803d\u803e\u803f\u8040\u8041\u8042\u8043\u8044\u8045\u8046\u8047\u8048\u8049\u804a\u804b\u804c\u804d\u804e\u804f\u8050\u8051\u8052\u8053\u8054\u8055\u8056\u8057\u8058\u8059\u805a\u805b\u805c\u805d\u805e\u805f\u8060\u8061\u8062\u8063\u8064\u8065\u8066\u8067\u8068\u8069\u806a\u806b\u806c\u806d\u806e\u806f\u8070\u8071\u8072\u8073\u8074\u8075\u8076\u8077\u8078\u8079\u807a\u807b\u807c\u807d\u807e\u807f\u8080\u8081\u8082\u8083\u8084\u8085\u8086\u8087\u8088\u8089\u808a\u808b\u808c\u808d\u808e\u808f\u8090\u8091\u8092\u8093\u8094\u8095\u8096\u8097\u8098\u8099\u809a\u809b\u809c\u809d\u809e\u809f\u80a0\u80a1\u80a2\u80a3\u80a4\u80a5\u80a6\u80a7\u80a8\u80a9\u80aa\u80ab\u80ac\u80ad\u80ae\u80af\u80b0\u80b1\u80b2\u80b3\u80b4\u80b5\u80b6\u80b7\u80b8\u80b9\u80ba\u80bb\u80bc\u80bd\u80be\u80bf\u80c0\u80c1\u80c2\u80c3\u80c4\u80c5\u80c6\u80c7\u80c8\u80c9\u80ca\u80cb\u80cc\u80cd\u80ce\u80cf\u80d0\u80d1\u80d2\u80d3\u80d4\u80d5\u80d6\u80d7\u80d8\u80d9\u80da\u80db\u80dc\u80dd\u80de\u80df\u80e0\u80e1\u80e2\u80e3\u80e4\u80e5\u80e6\u80e7\u80e8\u80e9\u80ea\u80eb\u80ec\u80ed\u80ee\u80ef\u80f0\u80f1\u80f2\u80f3\u80f4\u80f5\u80f6\u80f7\u80f8\u80f9\u80fa\u80fb\u80fc\u80fd\u80fe\u80ff\u8100\u8101\u8102\u8103\u8104\u8105\u8106\u8107\u8108\u8109\u810a\u810b\u810c\u810d\u810e\u810f\u8110\u8111\u8112\u8113\u8114\u8115\u8116\u8117\u8118\u8119\u811a\u811b\u811c\u811d\u811e\u811f\u8120\u8121\u8122\u8123\u8124\u8125\u8126\u8127\u8128\u8129\u812a\u812b\u812c\u812d\u812e\u812f\u8130\u8131\u8132\u8133\u8134\u8135\u8136\u8137\u8138\u8139\u813a\u813b\u813c\u813d\u813e\u813f\u8140\u8141\u8142\u8143\u8144\u8145\u8146\u8147\u8148\u8149\u814a\u814b\u814c\u814d\u814e\u814f\u8150\u8151\u8152\u8153\u8154\u8155\u8156\u8157\u8158\u8159\u815a\u815b\u815c\u815d\u815e\u815f\u8160\u8161\u8162\u8163\u8164\u8165\u8166\u8167\u8168\u8169\u816a\u816b\u816c\u816d\u816e\u816f\u8170\u8171\u8172\u8173\u8174\u8175\u8176\u8177\u8178\u8179\u817a\u817b\u817c\u817d\u817e\u817f\u8180\u8181\u8182\u8183\u8184\u8185\u8186\u8187\u8188\u8189\u818a\u818b\u818c\u818d\u818e\u818f\u8190\u8191\u8192\u8193\u8194\u8195\u8196\u8197\u8198\u8199\u819a\u819b\u819c\u819d\u819e\u819f\u81a0\u81a1\u81a2\u81a3\u81a4\u81a5\u81a6\u81a7\u81a8\u81a9\u81aa\u81ab\u81ac\u81ad\u81ae\u81af\u81b0\u81b1\u81b2\u81b3\u81b4\u81b5\u81b6\u81b7\u81b8\u81b9\u81ba\u81bb\u81bc\u81bd\u81be\u81bf\u81c0\u81c1\u81c2\u81c3\u81c4\u81c5\u81c6\u81c7\u81c8\u81c9\u81ca\u81cb\u81cc\u81cd\u81ce\u81cf\u81d0\u81d1\u81d2\u81d3\u81d4\u81d5\u81d6\u81d7\u81d8\u81d9\u81da\u81db\u81dc\u81dd\u81de\u81df\u81e0\u81e1\u81e2\u81e3\u81e4\u81e5\u81e6\u81e7\u81e8\u81e9\u81ea\u81eb\u81ec\u81ed\u81ee\u81ef\u81f0\u81f1\u81f2\u81f3\u81f4\u81f5\u81f6\u81f7\u81f8\u81f9\u81fa\u81fb\u81fc\u81fd\u81fe\u81ff\u8200\u8201\u8202\u8203\u8204\u8205\u8206\u8207\u8208\u8209\u820a\u820b\u820c\u820d\u820e\u820f\u8210\u8211\u8212\u8213\u8214\u8215\u8216\u8217\u8218\u8219\u821a\u821b\u821c\u821d\u821e\u821f\u8220\u8221\u8222\u8223\u8224\u8225\u8226\u8227\u8228\u8229\u822a\u822b\u822c\u822d\u822e\u822f\u8230\u8231\u8232\u8233\u8234\u8235\u8236\u8237\u8238\u8239\u823a\u823b\u823c\u823d\u823e\u823f\u8240\u8241\u8242\u8243\u8244\u8245\u8246\u8247\u8248\u8249\u824a\u824b\u824c\u824d\u824e\u824f\u8250\u8251\u8252\u8253\u8254\u8255\u8256\u8257\u8258\u8259\u825a\u825b\u825c\u825d\u825e\u825f\u8260\u8261\u8262\u8263\u8264\u8265\u8266\u8267\u8268\u8269\u826a\u826b\u826c\u826d\u826e\u826f\u8270\u8271\u8272\u8273\u8274\u8275\u8276\u8277\u8278\u8279\u827a\u827b\u827c\u827d\u827e\u827f\u8280\u8281\u8282\u8283\u8284\u8285\u8286\u8287\u8288\u8289\u828a\u828b\u828c\u828d\u828e\u828f\u8290\u8291\u8292\u8293\u8294\u8295\u8296\u8297\u8298\u8299\u829a\u829b\u829c\u829d\u829e\u829f\u82a0\u82a1\u82a2\u82a3\u82a4\u82a5\u82a6\u82a7\u82a8\u82a9\u82aa\u82ab\u82ac\u82ad\u82ae\u82af\u82b0\u82b1\u82b2\u82b3\u82b4\u82b5\u82b6\u82b7\u82b8\u82b9\u82ba\u82bb\u82bc\u82bd\u82be\u82bf\u82c0\u82c1\u82c2\u82c3\u82c4\u82c5\u82c6\u82c7\u82c8\u82c9\u82ca\u82cb\u82cc\u82cd\u82ce\u82cf\u82d0\u82d1\u82d2\u82d3\u82d4\u82d5\u82d6\u82d7\u82d8\u82d9\u82da\u82db\u82dc\u82dd\u82de\u82df\u82e0\u82e1\u82e2\u82e3\u82e4\u82e5\u82e6\u82e7\u82e8\u82e9\u82ea\u82eb\u82ec\u82ed\u82ee\u82ef\u82f0\u82f1\u82f2\u82f3\u82f4\u82f5\u82f6\u82f7\u82f8\u82f9\u82fa\u82fb\u82fc\u82fd\u82fe\u82ff\u8300\u8301\u8302\u8303\u8304\u8305\u8306\u8307\u8308\u8309\u830a\u830b\u830c\u830d\u830e\u830f\u8310\u8311\u8312\u8313\u8314\u8315\u8316\u8317\u8318\u8319\u831a\u831b\u831c\u831d\u831e\u831f\u8320\u8321\u8322\u8323\u8324\u8325\u8326\u8327\u8328\u8329\u832a\u832b\u832c\u832d\u832e\u832f\u8330\u8331\u8332\u8333\u8334\u8335\u8336\u8337\u8338\u8339\u833a\u833b\u833c\u833d\u833e\u833f\u8340\u8341\u8342\u8343\u8344\u8345\u8346\u8347\u8348\u8349\u834a\u834b\u834c\u834d\u834e\u834f\u8350\u8351\u8352\u8353\u8354\u8355\u8356\u8357\u8358\u8359\u835a\u835b\u835c\u835d\u835e\u835f\u8360\u8361\u8362\u8363\u8364\u8365\u8366\u8367\u8368\u8369\u836a\u836b\u836c\u836d\u836e\u836f\u8370\u8371\u8372\u8373\u8374\u8375\u8376\u8377\u8378\u8379\u837a\u837b\u837c\u837d\u837e\u837f\u8380\u8381\u8382\u8383\u8384\u8385\u8386\u8387\u8388\u8389\u838a\u838b\u838c\u838d\u838e\u838f\u8390\u8391\u8392\u8393\u8394\u8395\u8396\u8397\u8398\u8399\u839a\u839b\u839c\u839d\u839e\u839f\u83a0\u83a1\u83a2\u83a3\u83a4\u83a5\u83a6\u83a7\u83a8\u83a9\u83aa\u83ab\u83ac\u83ad\u83ae\u83af\u83b0\u83b1\u83b2\u83b3\u83b4\u83b5\u83b6\u83b7\u83b8\u83b9\u83ba\u83bb\u83bc\u83bd\u83be\u83bf\u83c0\u83c1\u83c2\u83c3\u83c4\u83c5\u83c6\u83c7\u83c8\u83c9\u83ca\u83cb\u83cc\u83cd\u83ce\u83cf\u83d0\u83d1\u83d2\u83d3\u83d4\u83d5\u83d6\u83d7\u83d8\u83d9\u83da\u83db\u83dc\u83dd\u83de\u83df\u83e0\u83e1\u83e2\u83e3\u83e4\u83e5\u83e6\u83e7\u83e8\u83e9\u83ea\u83eb\u83ec\u83ed\u83ee\u83ef\u83f0\u83f1\u83f2\u83f3\u83f4\u83f5\u83f6\u83f7\u83f8\u83f9\u83fa\u83fb\u83fc\u83fd\u83fe\u83ff\u8400\u8401\u8402\u8403\u8404\u8405\u8406\u8407\u8408\u8409\u840a\u840b\u840c\u840d\u840e\u840f\u8410\u8411\u8412\u8413\u8414\u8415\u8416\u8417\u8418\u8419\u841a\u841b\u841c\u841d\u841e\u841f\u8420\u8421\u8422\u8423\u8424\u8425\u8426\u8427\u8428\u8429\u842a\u842b\u842c\u842d\u842e\u842f\u8430\u8431\u8432\u8433\u8434\u8435\u8436\u8437\u8438\u8439\u843a\u843b\u843c\u843d\u843e\u843f\u8440\u8441\u8442\u8443\u8444\u8445\u8446\u8447\u8448\u8449\u844a\u844b\u844c\u844d\u844e\u844f\u8450\u8451\u8452\u8453\u8454\u8455\u8456\u8457\u8458\u8459\u845a\u845b\u845c\u845d\u845e\u845f\u8460\u8461\u8462\u8463\u8464\u8465\u8466\u8467\u8468\u8469\u846a\u846b\u846c\u846d\u846e\u846f\u8470\u8471\u8472\u8473\u8474\u8475\u8476\u8477\u8478\u8479\u847a\u847b\u847c\u847d\u847e\u847f\u8480\u8481\u8482\u8483\u8484\u8485\u8486\u8487\u8488\u8489\u848a\u848b\u848c\u848d\u848e\u848f\u8490\u8491\u8492\u8493\u8494\u8495\u8496\u8497\u8498\u8499\u849a\u849b\u849c\u849d\u849e\u849f\u84a0\u84a1\u84a2\u84a3\u84a4\u84a5\u84a6\u84a7\u84a8\u84a9\u84aa\u84ab\u84ac\u84ad\u84ae\u84af\u84b0\u84b1\u84b2\u84b3\u84b4\u84b5\u84b6\u84b7\u84b8\u84b9\u84ba\u84bb\u84bc\u84bd\u84be\u84bf\u84c0\u84c1\u84c2\u84c3\u84c4\u84c5\u84c6\u84c7\u84c8\u84c9\u84ca\u84cb\u84cc\u84cd\u84ce\u84cf\u84d0\u84d1\u84d2\u84d3\u84d4\u84d5\u84d6\u84d7\u84d8\u84d9\u84da\u84db\u84dc\u84dd\u84de\u84df\u84e0\u84e1\u84e2\u84e3\u84e4\u84e5\u84e6\u84e7\u84e8\u84e9\u84ea\u84eb\u84ec\u84ed\u84ee\u84ef\u84f0\u84f1\u84f2\u84f3\u84f4\u84f5\u84f6\u84f7\u84f8\u84f9\u84fa\u84fb\u84fc\u84fd\u84fe\u84ff\u8500\u8501\u8502\u8503\u8504\u8505\u8506\u8507\u8508\u8509\u850a\u850b\u850c\u850d\u850e\u850f\u8510\u8511\u8512\u8513\u8514\u8515\u8516\u8517\u8518\u8519\u851a\u851b\u851c\u851d\u851e\u851f\u8520\u8521\u8522\u8523\u8524\u8525\u8526\u8527\u8528\u8529\u852a\u852b\u852c\u852d\u852e\u852f\u8530\u8531\u8532\u8533\u8534\u8535\u8536\u8537\u8538\u8539\u853a\u853b\u853c\u853d\u853e\u853f\u8540\u8541\u8542\u8543\u8544\u8545\u8546\u8547\u8548\u8549\u854a\u854b\u854c\u854d\u854e\u854f\u8550\u8551\u8552\u8553\u8554\u8555\u8556\u8557\u8558\u8559\u855a\u855b\u855c\u855d\u855e\u855f\u8560\u8561\u8562\u8563\u8564\u8565\u8566\u8567\u8568\u8569\u856a\u856b\u856c\u856d\u856e\u856f\u8570\u8571\u8572\u8573\u8574\u8575\u8576\u8577\u8578\u8579\u857a\u857b\u857c\u857d\u857e\u857f\u8580\u8581\u8582\u8583\u8584\u8585\u8586\u8587\u8588\u8589\u858a\u858b\u858c\u858d\u858e\u858f\u8590\u8591\u8592\u8593\u8594\u8595\u8596\u8597\u8598\u8599\u859a\u859b\u859c\u859d\u859e\u859f\u85a0\u85a1\u85a2\u85a3\u85a4\u85a5\u85a6\u85a7\u85a8\u85a9\u85aa\u85ab\u85ac\u85ad\u85ae\u85af\u85b0\u85b1\u85b2\u85b3\u85b4\u85b5\u85b6\u85b7\u85b8\u85b9\u85ba\u85bb\u85bc\u85bd\u85be\u85bf\u85c0\u85c1\u85c2\u85c3\u85c4\u85c5\u85c6\u85c7\u85c8\u85c9\u85ca\u85cb\u85cc\u85cd\u85ce\u85cf\u85d0\u85d1\u85d2\u85d3\u85d4\u85d5\u85d6\u85d7\u85d8\u85d9\u85da\u85db\u85dc\u85dd\u85de\u85df\u85e0\u85e1\u85e2\u85e3\u85e4\u85e5\u85e6\u85e7\u85e8\u85e9\u85ea\u85eb\u85ec\u85ed\u85ee\u85ef\u85f0\u85f1\u85f2\u85f3\u85f4\u85f5\u85f6\u85f7\u85f8\u85f9\u85fa\u85fb\u85fc\u85fd\u85fe\u85ff\u8600\u8601\u8602\u8603\u8604\u8605\u8606\u8607\u8608\u8609\u860a\u860b\u860c\u860d\u860e\u860f\u8610\u8611\u8612\u8613\u8614\u8615\u8616\u8617\u8618\u8619\u861a\u861b\u861c\u861d\u861e\u861f\u8620\u8621\u8622\u8623\u8624\u8625\u8626\u8627\u8628\u8629\u862a\u862b\u862c\u862d\u862e\u862f\u8630\u8631\u8632\u8633\u8634\u8635\u8636\u8637\u8638\u8639\u863a\u863b\u863c\u863d\u863e\u863f\u8640\u8641\u8642\u8643\u8644\u8645\u8646\u8647\u8648\u8649\u864a\u864b\u864c\u864d\u864e\u864f\u8650\u8651\u8652\u8653\u8654\u8655\u8656\u8657\u8658\u8659\u865a\u865b\u865c\u865d\u865e\u865f\u8660\u8661\u8662\u8663\u8664\u8665\u8666\u8667\u8668\u8669\u866a\u866b\u866c\u866d\u866e\u866f\u8670\u8671\u8672\u8673\u8674\u8675\u8676\u8677\u8678\u8679\u867a\u867b\u867c\u867d\u867e\u867f\u8680\u8681\u8682\u8683\u8684\u8685\u8686\u8687\u8688\u8689\u868a\u868b\u868c\u868d\u868e\u868f\u8690\u8691\u8692\u8693\u8694\u8695\u8696\u8697\u8698\u8699\u869a\u869b\u869c\u869d\u869e\u869f\u86a0\u86a1\u86a2\u86a3\u86a4\u86a5\u86a6\u86a7\u86a8\u86a9\u86aa\u86ab\u86ac\u86ad\u86ae\u86af\u86b0\u86b1\u86b2\u86b3\u86b4\u86b5\u86b6\u86b7\u86b8\u86b9\u86ba\u86bb\u86bc\u86bd\u86be\u86bf\u86c0\u86c1\u86c2\u86c3\u86c4\u86c5\u86c6\u86c7\u86c8\u86c9\u86ca\u86cb\u86cc\u86cd\u86ce\u86cf\u86d0\u86d1\u86d2\u86d3\u86d4\u86d5\u86d6\u86d7\u86d8\u86d9\u86da\u86db\u86dc\u86dd\u86de\u86df\u86e0\u86e1\u86e2\u86e3\u86e4\u86e5\u86e6\u86e7\u86e8\u86e9\u86ea\u86eb\u86ec\u86ed\u86ee\u86ef\u86f0\u86f1\u86f2\u86f3\u86f4\u86f5\u86f6\u86f7\u86f8\u86f9\u86fa\u86fb\u86fc\u86fd\u86fe\u86ff\u8700\u8701\u8702\u8703\u8704\u8705\u8706\u8707\u8708\u8709\u870a\u870b\u870c\u870d\u870e\u870f\u8710\u8711\u8712\u8713\u8714\u8715\u8716\u8717\u8718\u8719\u871a\u871b\u871c\u871d\u871e\u871f\u8720\u8721\u8722\u8723\u8724\u8725\u8726\u8727\u8728\u8729\u872a\u872b\u872c\u872d\u872e\u872f\u8730\u8731\u8732\u8733\u8734\u8735\u8736\u8737\u8738\u8739\u873a\u873b\u873c\u873d\u873e\u873f\u8740\u8741\u8742\u8743\u8744\u8745\u8746\u8747\u8748\u8749\u874a\u874b\u874c\u874d\u874e\u874f\u8750\u8751\u8752\u8753\u8754\u8755\u8756\u8757\u8758\u8759\u875a\u875b\u875c\u875d\u875e\u875f\u8760\u8761\u8762\u8763\u8764\u8765\u8766\u8767\u8768\u8769\u876a\u876b\u876c\u876d\u876e\u876f\u8770\u8771\u8772\u8773\u8774\u8775\u8776\u8777\u8778\u8779\u877a\u877b\u877c\u877d\u877e\u877f\u8780\u8781\u8782\u8783\u8784\u8785\u8786\u8787\u8788\u8789\u878a\u878b\u878c\u878d\u878e\u878f\u8790\u8791\u8792\u8793\u8794\u8795\u8796\u8797\u8798\u8799\u879a\u879b\u879c\u879d\u879e\u879f\u87a0\u87a1\u87a2\u87a3\u87a4\u87a5\u87a6\u87a7\u87a8\u87a9\u87aa\u87ab\u87ac\u87ad\u87ae\u87af\u87b0\u87b1\u87b2\u87b3\u87b4\u87b5\u87b6\u87b7\u87b8\u87b9\u87ba\u87bb\u87bc\u87bd\u87be\u87bf\u87c0\u87c1\u87c2\u87c3\u87c4\u87c5\u87c6\u87c7\u87c8\u87c9\u87ca\u87cb\u87cc\u87cd\u87ce\u87cf\u87d0\u87d1\u87d2\u87d3\u87d4\u87d5\u87d6\u87d7\u87d8\u87d9\u87da\u87db\u87dc\u87dd\u87de\u87df\u87e0\u87e1\u87e2\u87e3\u87e4\u87e5\u87e6\u87e7\u87e8\u87e9\u87ea\u87eb\u87ec\u87ed\u87ee\u87ef\u87f0\u87f1\u87f2\u87f3\u87f4\u87f5\u87f6\u87f7\u87f8\u87f9\u87fa\u87fb\u87fc\u87fd\u87fe\u87ff\u8800\u8801\u8802\u8803\u8804\u8805\u8806\u8807\u8808\u8809\u880a\u880b\u880c\u880d\u880e\u880f\u8810\u8811\u8812\u8813\u8814\u8815\u8816\u8817\u8818\u8819\u881a\u881b\u881c\u881d\u881e\u881f\u8820\u8821\u8822\u8823\u8824\u8825\u8826\u8827\u8828\u8829\u882a\u882b\u882c\u882d\u882e\u882f\u8830\u8831\u8832\u8833\u8834\u8835\u8836\u8837\u8838\u8839\u883a\u883b\u883c\u883d\u883e\u883f\u8840\u8841\u8842\u8843\u8844\u8845\u8846\u8847\u8848\u8849\u884a\u884b\u884c\u884d\u884e\u884f\u8850\u8851\u8852\u8853\u8854\u8855\u8856\u8857\u8858\u8859\u885a\u885b\u885c\u885d\u885e\u885f\u8860\u8861\u8862\u8863\u8864\u8865\u8866\u8867\u8868\u8869\u886a\u886b\u886c\u886d\u886e\u886f\u8870\u8871\u8872\u8873\u8874\u8875\u8876\u8877\u8878\u8879\u887a\u887b\u887c\u887d\u887e\u887f\u8880\u8881\u8882\u8883\u8884\u8885\u8886\u8887\u8888\u8889\u888a\u888b\u888c\u888d\u888e\u888f\u8890\u8891\u8892\u8893\u8894\u8895\u8896\u8897\u8898\u8899\u889a\u889b\u889c\u889d\u889e\u889f\u88a0\u88a1\u88a2\u88a3\u88a4\u88a5\u88a6\u88a7\u88a8\u88a9\u88aa\u88ab\u88ac\u88ad\u88ae\u88af\u88b0\u88b1\u88b2\u88b3\u88b4\u88b5\u88b6\u88b7\u88b8\u88b9\u88ba\u88bb\u88bc\u88bd\u88be\u88bf\u88c0\u88c1\u88c2\u88c3\u88c4\u88c5\u88c6\u88c7\u88c8\u88c9\u88ca\u88cb\u88cc\u88cd\u88ce\u88cf\u88d0\u88d1\u88d2\u88d3\u88d4\u88d5\u88d6\u88d7\u88d8\u88d9\u88da\u88db\u88dc\u88dd\u88de\u88df\u88e0\u88e1\u88e2\u88e3\u88e4\u88e5\u88e6\u88e7\u88e8\u88e9\u88ea\u88eb\u88ec\u88ed\u88ee\u88ef\u88f0\u88f1\u88f2\u88f3\u88f4\u88f5\u88f6\u88f7\u88f8\u88f9\u88fa\u88fb\u88fc\u88fd\u88fe\u88ff\u8900\u8901\u8902\u8903\u8904\u8905\u8906\u8907\u8908\u8909\u890a\u890b\u890c\u890d\u890e\u890f\u8910\u8911\u8912\u8913\u8914\u8915\u8916\u8917\u8918\u8919\u891a\u891b\u891c\u891d\u891e\u891f\u8920\u8921\u8922\u8923\u8924\u8925\u8926\u8927\u8928\u8929\u892a\u892b\u892c\u892d\u892e\u892f\u8930\u8931\u8932\u8933\u8934\u8935\u8936\u8937\u8938\u8939\u893a\u893b\u893c\u893d\u893e\u893f\u8940\u8941\u8942\u8943\u8944\u8945\u8946\u8947\u8948\u8949\u894a\u894b\u894c\u894d\u894e\u894f\u8950\u8951\u8952\u8953\u8954\u8955\u8956\u8957\u8958\u8959\u895a\u895b\u895c\u895d\u895e\u895f\u8960\u8961\u8962\u8963\u8964\u8965\u8966\u8967\u8968\u8969\u896a\u896b\u896c\u896d\u896e\u896f\u8970\u8971\u8972\u8973\u8974\u8975\u8976\u8977\u8978\u8979\u897a\u897b\u897c\u897d\u897e\u897f\u8980\u8981\u8982\u8983\u8984\u8985\u8986\u8987\u8988\u8989\u898a\u898b\u898c\u898d\u898e\u898f\u8990\u8991\u8992\u8993\u8994\u8995\u8996\u8997\u8998\u8999\u899a\u899b\u899c\u899d\u899e\u899f\u89a0\u89a1\u89a2\u89a3\u89a4\u89a5\u89a6\u89a7\u89a8\u89a9\u89aa\u89ab\u89ac\u89ad\u89ae\u89af\u89b0\u89b1\u89b2\u89b3\u89b4\u89b5\u89b6\u89b7\u89b8\u89b9\u89ba\u89bb\u89bc\u89bd\u89be\u89bf\u89c0\u89c1\u89c2\u89c3\u89c4\u89c5\u89c6\u89c7\u89c8\u89c9\u89ca\u89cb\u89cc\u89cd\u89ce\u89cf\u89d0\u89d1\u89d2\u89d3\u89d4\u89d5\u89d6\u89d7\u89d8\u89d9\u89da\u89db\u89dc\u89dd\u89de\u89df\u89e0\u89e1\u89e2\u89e3\u89e4\u89e5\u89e6\u89e7\u89e8\u89e9\u89ea\u89eb\u89ec\u89ed\u89ee\u89ef\u89f0\u89f1\u89f2\u89f3\u89f4\u89f5\u89f6\u89f7\u89f8\u89f9\u89fa\u89fb\u89fc\u89fd\u89fe\u89ff\u8a00\u8a01\u8a02\u8a03\u8a04\u8a05\u8a06\u8a07\u8a08\u8a09\u8a0a\u8a0b\u8a0c\u8a0d\u8a0e\u8a0f\u8a10\u8a11\u8a12\u8a13\u8a14\u8a15\u8a16\u8a17\u8a18\u8a19\u8a1a\u8a1b\u8a1c\u8a1d\u8a1e\u8a1f\u8a20\u8a21\u8a22\u8a23\u8a24\u8a25\u8a26\u8a27\u8a28\u8a29\u8a2a\u8a2b\u8a2c\u8a2d\u8a2e\u8a2f\u8a30\u8a31\u8a32\u8a33\u8a34\u8a35\u8a36\u8a37\u8a38\u8a39\u8a3a\u8a3b\u8a3c\u8a3d\u8a3e\u8a3f\u8a40\u8a41\u8a42\u8a43\u8a44\u8a45\u8a46\u8a47\u8a48\u8a49\u8a4a\u8a4b\u8a4c\u8a4d\u8a4e\u8a4f\u8a50\u8a51\u8a52\u8a53\u8a54\u8a55\u8a56\u8a57\u8a58\u8a59\u8a5a\u8a5b\u8a5c\u8a5d\u8a5e\u8a5f\u8a60\u8a61\u8a62\u8a63\u8a64\u8a65\u8a66\u8a67\u8a68\u8a69\u8a6a\u8a6b\u8a6c\u8a6d\u8a6e\u8a6f\u8a70\u8a71\u8a72\u8a73\u8a74\u8a75\u8a76\u8a77\u8a78\u8a79\u8a7a\u8a7b\u8a7c\u8a7d\u8a7e\u8a7f\u8a80\u8a81\u8a82\u8a83\u8a84\u8a85\u8a86\u8a87\u8a88\u8a89\u8a8a\u8a8b\u8a8c\u8a8d\u8a8e\u8a8f\u8a90\u8a91\u8a92\u8a93\u8a94\u8a95\u8a96\u8a97\u8a98\u8a99\u8a9a\u8a9b\u8a9c\u8a9d\u8a9e\u8a9f\u8aa0\u8aa1\u8aa2\u8aa3\u8aa4\u8aa5\u8aa6\u8aa7\u8aa8\u8aa9\u8aaa\u8aab\u8aac\u8aad\u8aae\u8aaf\u8ab0\u8ab1\u8ab2\u8ab3\u8ab4\u8ab5\u8ab6\u8ab7\u8ab8\u8ab9\u8aba\u8abb\u8abc\u8abd\u8abe\u8abf\u8ac0\u8ac1\u8ac2\u8ac3\u8ac4\u8ac5\u8ac6\u8ac7\u8ac8\u8ac9\u8aca\u8acb\u8acc\u8acd\u8ace\u8acf\u8ad0\u8ad1\u8ad2\u8ad3\u8ad4\u8ad5\u8ad6\u8ad7\u8ad8\u8ad9\u8ada\u8adb\u8adc\u8add\u8ade\u8adf\u8ae0\u8ae1\u8ae2\u8ae3\u8ae4\u8ae5\u8ae6\u8ae7\u8ae8\u8ae9\u8aea\u8aeb\u8aec\u8aed\u8aee\u8aef\u8af0\u8af1\u8af2\u8af3\u8af4\u8af5\u8af6\u8af7\u8af8\u8af9\u8afa\u8afb\u8afc\u8afd\u8afe\u8aff\u8b00\u8b01\u8b02\u8b03\u8b04\u8b05\u8b06\u8b07\u8b08\u8b09\u8b0a\u8b0b\u8b0c\u8b0d\u8b0e\u8b0f\u8b10\u8b11\u8b12\u8b13\u8b14\u8b15\u8b16\u8b17\u8b18\u8b19\u8b1a\u8b1b\u8b1c\u8b1d\u8b1e\u8b1f\u8b20\u8b21\u8b22\u8b23\u8b24\u8b25\u8b26\u8b27\u8b28\u8b29\u8b2a\u8b2b\u8b2c\u8b2d\u8b2e\u8b2f\u8b30\u8b31\u8b32\u8b33\u8b34\u8b35\u8b36\u8b37\u8b38\u8b39\u8b3a\u8b3b\u8b3c\u8b3d\u8b3e\u8b3f\u8b40\u8b41\u8b42\u8b43\u8b44\u8b45\u8b46\u8b47\u8b48\u8b49\u8b4a\u8b4b\u8b4c\u8b4d\u8b4e\u8b4f\u8b50\u8b51\u8b52\u8b53\u8b54\u8b55\u8b56\u8b57\u8b58\u8b59\u8b5a\u8b5b\u8b5c\u8b5d\u8b5e\u8b5f\u8b60\u8b61\u8b62\u8b63\u8b64\u8b65\u8b66\u8b67\u8b68\u8b69\u8b6a\u8b6b\u8b6c\u8b6d\u8b6e\u8b6f\u8b70\u8b71\u8b72\u8b73\u8b74\u8b75\u8b76\u8b77\u8b78\u8b79\u8b7a\u8b7b\u8b7c\u8b7d\u8b7e\u8b7f\u8b80\u8b81\u8b82\u8b83\u8b84\u8b85\u8b86\u8b87\u8b88\u8b89\u8b8a\u8b8b\u8b8c\u8b8d\u8b8e\u8b8f\u8b90\u8b91\u8b92\u8b93\u8b94\u8b95\u8b96\u8b97\u8b98\u8b99\u8b9a\u8b9b\u8b9c\u8b9d\u8b9e\u8b9f\u8ba0\u8ba1\u8ba2\u8ba3\u8ba4\u8ba5\u8ba6\u8ba7\u8ba8\u8ba9\u8baa\u8bab\u8bac\u8bad\u8bae\u8baf\u8bb0\u8bb1\u8bb2\u8bb3\u8bb4\u8bb5\u8bb6\u8bb7\u8bb8\u8bb9\u8bba\u8bbb\u8bbc\u8bbd\u8bbe\u8bbf\u8bc0\u8bc1\u8bc2\u8bc3\u8bc4\u8bc5\u8bc6\u8bc7\u8bc8\u8bc9\u8bca\u8bcb\u8bcc\u8bcd\u8bce\u8bcf\u8bd0\u8bd1\u8bd2\u8bd3\u8bd4\u8bd5\u8bd6\u8bd7\u8bd8\u8bd9\u8bda\u8bdb\u8bdc\u8bdd\u8bde\u8bdf\u8be0\u8be1\u8be2\u8be3\u8be4\u8be5\u8be6\u8be7\u8be8\u8be9\u8bea\u8beb\u8bec\u8bed\u8bee\u8bef\u8bf0\u8bf1\u8bf2\u8bf3\u8bf4\u8bf5\u8bf6\u8bf7\u8bf8\u8bf9\u8bfa\u8bfb\u8bfc\u8bfd\u8bfe\u8bff\u8c00\u8c01\u8c02\u8c03\u8c04\u8c05\u8c06\u8c07\u8c08\u8c09\u8c0a\u8c0b\u8c0c\u8c0d\u8c0e\u8c0f\u8c10\u8c11\u8c12\u8c13\u8c14\u8c15\u8c16\u8c17\u8c18\u8c19\u8c1a\u8c1b\u8c1c\u8c1d\u8c1e\u8c1f\u8c20\u8c21\u8c22\u8c23\u8c24\u8c25\u8c26\u8c27\u8c28\u8c29\u8c2a\u8c2b\u8c2c\u8c2d\u8c2e\u8c2f\u8c30\u8c31\u8c32\u8c33\u8c34\u8c35\u8c36\u8c37\u8c38\u8c39\u8c3a\u8c3b\u8c3c\u8c3d\u8c3e\u8c3f\u8c40\u8c41\u8c42\u8c43\u8c44\u8c45\u8c46\u8c47\u8c48\u8c49\u8c4a\u8c4b\u8c4c\u8c4d\u8c4e\u8c4f\u8c50\u8c51\u8c52\u8c53\u8c54\u8c55\u8c56\u8c57\u8c58\u8c59\u8c5a\u8c5b\u8c5c\u8c5d\u8c5e\u8c5f\u8c60\u8c61\u8c62\u8c63\u8c64\u8c65\u8c66\u8c67\u8c68\u8c69\u8c6a\u8c6b\u8c6c\u8c6d\u8c6e\u8c6f\u8c70\u8c71\u8c72\u8c73\u8c74\u8c75\u8c76\u8c77\u8c78\u8c79\u8c7a\u8c7b\u8c7c\u8c7d\u8c7e\u8c7f\u8c80\u8c81\u8c82\u8c83\u8c84\u8c85\u8c86\u8c87\u8c88\u8c89\u8c8a\u8c8b\u8c8c\u8c8d\u8c8e\u8c8f\u8c90\u8c91\u8c92\u8c93\u8c94\u8c95\u8c96\u8c97\u8c98\u8c99\u8c9a\u8c9b\u8c9c\u8c9d\u8c9e\u8c9f\u8ca0\u8ca1\u8ca2\u8ca3\u8ca4\u8ca5\u8ca6\u8ca7\u8ca8\u8ca9\u8caa\u8cab\u8cac\u8cad\u8cae\u8caf\u8cb0\u8cb1\u8cb2\u8cb3\u8cb4\u8cb5\u8cb6\u8cb7\u8cb8\u8cb9\u8cba\u8cbb\u8cbc\u8cbd\u8cbe\u8cbf\u8cc0\u8cc1\u8cc2\u8cc3\u8cc4\u8cc5\u8cc6\u8cc7\u8cc8\u8cc9\u8cca\u8ccb\u8ccc\u8ccd\u8cce\u8ccf\u8cd0\u8cd1\u8cd2\u8cd3\u8cd4\u8cd5\u8cd6\u8cd7\u8cd8\u8cd9\u8cda\u8cdb\u8cdc\u8cdd\u8cde\u8cdf\u8ce0\u8ce1\u8ce2\u8ce3\u8ce4\u8ce5\u8ce6\u8ce7\u8ce8\u8ce9\u8cea\u8ceb\u8cec\u8ced\u8cee\u8cef\u8cf0\u8cf1\u8cf2\u8cf3\u8cf4\u8cf5\u8cf6\u8cf7\u8cf8\u8cf9\u8cfa\u8cfb\u8cfc\u8cfd\u8cfe\u8cff\u8d00\u8d01\u8d02\u8d03\u8d04\u8d05\u8d06\u8d07\u8d08\u8d09\u8d0a\u8d0b\u8d0c\u8d0d\u8d0e\u8d0f\u8d10\u8d11\u8d12\u8d13\u8d14\u8d15\u8d16\u8d17\u8d18\u8d19\u8d1a\u8d1b\u8d1c\u8d1d\u8d1e\u8d1f\u8d20\u8d21\u8d22\u8d23\u8d24\u8d25\u8d26\u8d27\u8d28\u8d29\u8d2a\u8d2b\u8d2c\u8d2d\u8d2e\u8d2f\u8d30\u8d31\u8d32\u8d33\u8d34\u8d35\u8d36\u8d37\u8d38\u8d39\u8d3a\u8d3b\u8d3c\u8d3d\u8d3e\u8d3f\u8d40\u8d41\u8d42\u8d43\u8d44\u8d45\u8d46\u8d47\u8d48\u8d49\u8d4a\u8d4b\u8d4c\u8d4d\u8d4e\u8d4f\u8d50\u8d51\u8d52\u8d53\u8d54\u8d55\u8d56\u8d57\u8d58\u8d59\u8d5a\u8d5b\u8d5c\u8d5d\u8d5e\u8d5f\u8d60\u8d61\u8d62\u8d63\u8d64\u8d65\u8d66\u8d67\u8d68\u8d69\u8d6a\u8d6b\u8d6c\u8d6d\u8d6e\u8d6f\u8d70\u8d71\u8d72\u8d73\u8d74\u8d75\u8d76\u8d77\u8d78\u8d79\u8d7a\u8d7b\u8d7c\u8d7d\u8d7e\u8d7f\u8d80\u8d81\u8d82\u8d83\u8d84\u8d85\u8d86\u8d87\u8d88\u8d89\u8d8a\u8d8b\u8d8c\u8d8d\u8d8e\u8d8f\u8d90\u8d91\u8d92\u8d93\u8d94\u8d95\u8d96\u8d97\u8d98\u8d99\u8d9a\u8d9b\u8d9c\u8d9d\u8d9e\u8d9f\u8da0\u8da1\u8da2\u8da3\u8da4\u8da5\u8da6\u8da7\u8da8\u8da9\u8daa\u8dab\u8dac\u8dad\u8dae\u8daf\u8db0\u8db1\u8db2\u8db3\u8db4\u8db5\u8db6\u8db7\u8db8\u8db9\u8dba\u8dbb\u8dbc\u8dbd\u8dbe\u8dbf\u8dc0\u8dc1\u8dc2\u8dc3\u8dc4\u8dc5\u8dc6\u8dc7\u8dc8\u8dc9\u8dca\u8dcb\u8dcc\u8dcd\u8dce\u8dcf\u8dd0\u8dd1\u8dd2\u8dd3\u8dd4\u8dd5\u8dd6\u8dd7\u8dd8\u8dd9\u8dda\u8ddb\u8ddc\u8ddd\u8dde\u8ddf\u8de0\u8de1\u8de2\u8de3\u8de4\u8de5\u8de6\u8de7\u8de8\u8de9\u8dea\u8deb\u8dec\u8ded\u8dee\u8def\u8df0\u8df1\u8df2\u8df3\u8df4\u8df5\u8df6\u8df7\u8df8\u8df9\u8dfa\u8dfb\u8dfc\u8dfd\u8dfe\u8dff\u8e00\u8e01\u8e02\u8e03\u8e04\u8e05\u8e06\u8e07\u8e08\u8e09\u8e0a\u8e0b\u8e0c\u8e0d\u8e0e\u8e0f\u8e10\u8e11\u8e12\u8e13\u8e14\u8e15\u8e16\u8e17\u8e18\u8e19\u8e1a\u8e1b\u8e1c\u8e1d\u8e1e\u8e1f\u8e20\u8e21\u8e22\u8e23\u8e24\u8e25\u8e26\u8e27\u8e28\u8e29\u8e2a\u8e2b\u8e2c\u8e2d\u8e2e\u8e2f\u8e30\u8e31\u8e32\u8e33\u8e34\u8e35\u8e36\u8e37\u8e38\u8e39\u8e3a\u8e3b\u8e3c\u8e3d\u8e3e\u8e3f\u8e40\u8e41\u8e42\u8e43\u8e44\u8e45\u8e46\u8e47\u8e48\u8e49\u8e4a\u8e4b\u8e4c\u8e4d\u8e4e\u8e4f\u8e50\u8e51\u8e52\u8e53\u8e54\u8e55\u8e56\u8e57\u8e58\u8e59\u8e5a\u8e5b\u8e5c\u8e5d\u8e5e\u8e5f\u8e60\u8e61\u8e62\u8e63\u8e64\u8e65\u8e66\u8e67\u8e68\u8e69\u8e6a\u8e6b\u8e6c\u8e6d\u8e6e\u8e6f\u8e70\u8e71\u8e72\u8e73\u8e74\u8e75\u8e76\u8e77\u8e78\u8e79\u8e7a\u8e7b\u8e7c\u8e7d\u8e7e\u8e7f\u8e80\u8e81\u8e82\u8e83\u8e84\u8e85\u8e86\u8e87\u8e88\u8e89\u8e8a\u8e8b\u8e8c\u8e8d\u8e8e\u8e8f\u8e90\u8e91\u8e92\u8e93\u8e94\u8e95\u8e96\u8e97\u8e98\u8e99\u8e9a\u8e9b\u8e9c\u8e9d\u8e9e\u8e9f\u8ea0\u8ea1\u8ea2\u8ea3\u8ea4\u8ea5\u8ea6\u8ea7\u8ea8\u8ea9\u8eaa\u8eab\u8eac\u8ead\u8eae\u8eaf\u8eb0\u8eb1\u8eb2\u8eb3\u8eb4\u8eb5\u8eb6\u8eb7\u8eb8\u8eb9\u8eba\u8ebb\u8ebc\u8ebd\u8ebe\u8ebf\u8ec0\u8ec1\u8ec2\u8ec3\u8ec4\u8ec5\u8ec6\u8ec7\u8ec8\u8ec9\u8eca\u8ecb\u8ecc\u8ecd\u8ece\u8ecf\u8ed0\u8ed1\u8ed2\u8ed3\u8ed4\u8ed5\u8ed6\u8ed7\u8ed8\u8ed9\u8eda\u8edb\u8edc\u8edd\u8ede\u8edf\u8ee0\u8ee1\u8ee2\u8ee3\u8ee4\u8ee5\u8ee6\u8ee7\u8ee8\u8ee9\u8eea\u8eeb\u8eec\u8eed\u8eee\u8eef\u8ef0\u8ef1\u8ef2\u8ef3\u8ef4\u8ef5\u8ef6\u8ef7\u8ef8\u8ef9\u8efa\u8efb\u8efc\u8efd\u8efe\u8eff\u8f00\u8f01\u8f02\u8f03\u8f04\u8f05\u8f06\u8f07\u8f08\u8f09\u8f0a\u8f0b\u8f0c\u8f0d\u8f0e\u8f0f\u8f10\u8f11\u8f12\u8f13\u8f14\u8f15\u8f16\u8f17\u8f18\u8f19\u8f1a\u8f1b\u8f1c\u8f1d\u8f1e\u8f1f\u8f20\u8f21\u8f22\u8f23\u8f24\u8f25\u8f26\u8f27\u8f28\u8f29\u8f2a\u8f2b\u8f2c\u8f2d\u8f2e\u8f2f\u8f30\u8f31\u8f32\u8f33\u8f34\u8f35\u8f36\u8f37\u8f38\u8f39\u8f3a\u8f3b\u8f3c\u8f3d\u8f3e\u8f3f\u8f40\u8f41\u8f42\u8f43\u8f44\u8f45\u8f46\u8f47\u8f48\u8f49\u8f4a\u8f4b\u8f4c\u8f4d\u8f4e\u8f4f\u8f50\u8f51\u8f52\u8f53\u8f54\u8f55\u8f56\u8f57\u8f58\u8f59\u8f5a\u8f5b\u8f5c\u8f5d\u8f5e\u8f5f\u8f60\u8f61\u8f62\u8f63\u8f64\u8f65\u8f66\u8f67\u8f68\u8f69\u8f6a\u8f6b\u8f6c\u8f6d\u8f6e\u8f6f\u8f70\u8f71\u8f72\u8f73\u8f74\u8f75\u8f76\u8f77\u8f78\u8f79\u8f7a\u8f7b\u8f7c\u8f7d\u8f7e\u8f7f\u8f80\u8f81\u8f82\u8f83\u8f84\u8f85\u8f86\u8f87\u8f88\u8f89\u8f8a\u8f8b\u8f8c\u8f8d\u8f8e\u8f8f\u8f90\u8f91\u8f92\u8f93\u8f94\u8f95\u8f96\u8f97\u8f98\u8f99\u8f9a\u8f9b\u8f9c\u8f9d\u8f9e\u8f9f\u8fa0\u8fa1\u8fa2\u8fa3\u8fa4\u8fa5\u8fa6\u8fa7\u8fa8\u8fa9\u8faa\u8fab\u8fac\u8fad\u8fae\u8faf\u8fb0\u8fb1\u8fb2\u8fb3\u8fb4\u8fb5\u8fb6\u8fb7\u8fb8\u8fb9\u8fba\u8fbb\u8fbc\u8fbd\u8fbe\u8fbf\u8fc0\u8fc1\u8fc2\u8fc3\u8fc4\u8fc5\u8fc6\u8fc7\u8fc8\u8fc9\u8fca\u8fcb\u8fcc\u8fcd\u8fce\u8fcf\u8fd0\u8fd1\u8fd2\u8fd3\u8fd4\u8fd5\u8fd6\u8fd7\u8fd8\u8fd9\u8fda\u8fdb\u8fdc\u8fdd\u8fde\u8fdf\u8fe0\u8fe1\u8fe2\u8fe3\u8fe4\u8fe5\u8fe6\u8fe7\u8fe8\u8fe9\u8fea\u8feb\u8fec\u8fed\u8fee\u8fef\u8ff0\u8ff1\u8ff2\u8ff3\u8ff4\u8ff5\u8ff6\u8ff7\u8ff8\u8ff9\u8ffa\u8ffb\u8ffc\u8ffd\u8ffe\u8fff\u9000\u9001\u9002\u9003\u9004\u9005\u9006\u9007\u9008\u9009\u900a\u900b\u900c\u900d\u900e\u900f\u9010\u9011\u9012\u9013\u9014\u9015\u9016\u9017\u9018\u9019\u901a\u901b\u901c\u901d\u901e\u901f\u9020\u9021\u9022\u9023\u9024\u9025\u9026\u9027\u9028\u9029\u902a\u902b\u902c\u902d\u902e\u902f\u9030\u9031\u9032\u9033\u9034\u9035\u9036\u9037\u9038\u9039\u903a\u903b\u903c\u903d\u903e\u903f\u9040\u9041\u9042\u9043\u9044\u9045\u9046\u9047\u9048\u9049\u904a\u904b\u904c\u904d\u904e\u904f\u9050\u9051\u9052\u9053\u9054\u9055\u9056\u9057\u9058\u9059\u905a\u905b\u905c\u905d\u905e\u905f\u9060\u9061\u9062\u9063\u9064\u9065\u9066\u9067\u9068\u9069\u906a\u906b\u906c\u906d\u906e\u906f\u9070\u9071\u9072\u9073\u9074\u9075\u9076\u9077\u9078\u9079\u907a\u907b\u907c\u907d\u907e\u907f\u9080\u9081\u9082\u9083\u9084\u9085\u9086\u9087\u9088\u9089\u908a\u908b\u908c\u908d\u908e\u908f\u9090\u9091\u9092\u9093\u9094\u9095\u9096\u9097\u9098\u9099\u909a\u909b\u909c\u909d\u909e\u909f\u90a0\u90a1\u90a2\u90a3\u90a4\u90a5\u90a6\u90a7\u90a8\u90a9\u90aa\u90ab\u90ac\u90ad\u90ae\u90af\u90b0\u90b1\u90b2\u90b3\u90b4\u90b5\u90b6\u90b7\u90b8\u90b9\u90ba\u90bb\u90bc\u90bd\u90be\u90bf\u90c0\u90c1\u90c2\u90c3\u90c4\u90c5\u90c6\u90c7\u90c8\u90c9\u90ca\u90cb\u90cc\u90cd\u90ce\u90cf\u90d0\u90d1\u90d2\u90d3\u90d4\u90d5\u90d6\u90d7\u90d8\u90d9\u90da\u90db\u90dc\u90dd\u90de\u90df\u90e0\u90e1\u90e2\u90e3\u90e4\u90e5\u90e6\u90e7\u90e8\u90e9\u90ea\u90eb\u90ec\u90ed\u90ee\u90ef\u90f0\u90f1\u90f2\u90f3\u90f4\u90f5\u90f6\u90f7\u90f8\u90f9\u90fa\u90fb\u90fc\u90fd\u90fe\u90ff\u9100\u9101\u9102\u9103\u9104\u9105\u9106\u9107\u9108\u9109\u910a\u910b\u910c\u910d\u910e\u910f\u9110\u9111\u9112\u9113\u9114\u9115\u9116\u9117\u9118\u9119\u911a\u911b\u911c\u911d\u911e\u911f\u9120\u9121\u9122\u9123\u9124\u9125\u9126\u9127\u9128\u9129\u912a\u912b\u912c\u912d\u912e\u912f\u9130\u9131\u9132\u9133\u9134\u9135\u9136\u9137\u9138\u9139\u913a\u913b\u913c\u913d\u913e\u913f\u9140\u9141\u9142\u9143\u9144\u9145\u9146\u9147\u9148\u9149\u914a\u914b\u914c\u914d\u914e\u914f\u9150\u9151\u9152\u9153\u9154\u9155\u9156\u9157\u9158\u9159\u915a\u915b\u915c\u915d\u915e\u915f\u9160\u9161\u9162\u9163\u9164\u9165\u9166\u9167\u9168\u9169\u916a\u916b\u916c\u916d\u916e\u916f\u9170\u9171\u9172\u9173\u9174\u9175\u9176\u9177\u9178\u9179\u917a\u917b\u917c\u917d\u917e\u917f\u9180\u9181\u9182\u9183\u9184\u9185\u9186\u9187\u9188\u9189\u918a\u918b\u918c\u918d\u918e\u918f\u9190\u9191\u9192\u9193\u9194\u9195\u9196\u9197\u9198\u9199\u919a\u919b\u919c\u919d\u919e\u919f\u91a0\u91a1\u91a2\u91a3\u91a4\u91a5\u91a6\u91a7\u91a8\u91a9\u91aa\u91ab\u91ac\u91ad\u91ae\u91af\u91b0\u91b1\u91b2\u91b3\u91b4\u91b5\u91b6\u91b7\u91b8\u91b9\u91ba\u91bb\u91bc\u91bd\u91be\u91bf\u91c0\u91c1\u91c2\u91c3\u91c4\u91c5\u91c6\u91c7\u91c8\u91c9\u91ca\u91cb\u91cc\u91cd\u91ce\u91cf\u91d0\u91d1\u91d2\u91d3\u91d4\u91d5\u91d6\u91d7\u91d8\u91d9\u91da\u91db\u91dc\u91dd\u91de\u91df\u91e0\u91e1\u91e2\u91e3\u91e4\u91e5\u91e6\u91e7\u91e8\u91e9\u91ea\u91eb\u91ec\u91ed\u91ee\u91ef\u91f0\u91f1\u91f2\u91f3\u91f4\u91f5\u91f6\u91f7\u91f8\u91f9\u91fa\u91fb\u91fc\u91fd\u91fe\u91ff\u9200\u9201\u9202\u9203\u9204\u9205\u9206\u9207\u9208\u9209\u920a\u920b\u920c\u920d\u920e\u920f\u9210\u9211\u9212\u9213\u9214\u9215\u9216\u9217\u9218\u9219\u921a\u921b\u921c\u921d\u921e\u921f\u9220\u9221\u9222\u9223\u9224\u9225\u9226\u9227\u9228\u9229\u922a\u922b\u922c\u922d\u922e\u922f\u9230\u9231\u9232\u9233\u9234\u9235\u9236\u9237\u9238\u9239\u923a\u923b\u923c\u923d\u923e\u923f\u9240\u9241\u9242\u9243\u9244\u9245\u9246\u9247\u9248\u9249\u924a\u924b\u924c\u924d\u924e\u924f\u9250\u9251\u9252\u9253\u9254\u9255\u9256\u9257\u9258\u9259\u925a\u925b\u925c\u925d\u925e\u925f\u9260\u9261\u9262\u9263\u9264\u9265\u9266\u9267\u9268\u9269\u926a\u926b\u926c\u926d\u926e\u926f\u9270\u9271\u9272\u9273\u9274\u9275\u9276\u9277\u9278\u9279\u927a\u927b\u927c\u927d\u927e\u927f\u9280\u9281\u9282\u9283\u9284\u9285\u9286\u9287\u9288\u9289\u928a\u928b\u928c\u928d\u928e\u928f\u9290\u9291\u9292\u9293\u9294\u9295\u9296\u9297\u9298\u9299\u929a\u929b\u929c\u929d\u929e\u929f\u92a0\u92a1\u92a2\u92a3\u92a4\u92a5\u92a6\u92a7\u92a8\u92a9\u92aa\u92ab\u92ac\u92ad\u92ae\u92af\u92b0\u92b1\u92b2\u92b3\u92b4\u92b5\u92b6\u92b7\u92b8\u92b9\u92ba\u92bb\u92bc\u92bd\u92be\u92bf\u92c0\u92c1\u92c2\u92c3\u92c4\u92c5\u92c6\u92c7\u92c8\u92c9\u92ca\u92cb\u92cc\u92cd\u92ce\u92cf\u92d0\u92d1\u92d2\u92d3\u92d4\u92d5\u92d6\u92d7\u92d8\u92d9\u92da\u92db\u92dc\u92dd\u92de\u92df\u92e0\u92e1\u92e2\u92e3\u92e4\u92e5\u92e6\u92e7\u92e8\u92e9\u92ea\u92eb\u92ec\u92ed\u92ee\u92ef\u92f0\u92f1\u92f2\u92f3\u92f4\u92f5\u92f6\u92f7\u92f8\u92f9\u92fa\u92fb\u92fc\u92fd\u92fe\u92ff\u9300\u9301\u9302\u9303\u9304\u9305\u9306\u9307\u9308\u9309\u930a\u930b\u930c\u930d\u930e\u930f\u9310\u9311\u9312\u9313\u9314\u9315\u9316\u9317\u9318\u9319\u931a\u931b\u931c\u931d\u931e\u931f\u9320\u9321\u9322\u9323\u9324\u9325\u9326\u9327\u9328\u9329\u932a\u932b\u932c\u932d\u932e\u932f\u9330\u9331\u9332\u9333\u9334\u9335\u9336\u9337\u9338\u9339\u933a\u933b\u933c\u933d\u933e\u933f\u9340\u9341\u9342\u9343\u9344\u9345\u9346\u9347\u9348\u9349\u934a\u934b\u934c\u934d\u934e\u934f\u9350\u9351\u9352\u9353\u9354\u9355\u9356\u9357\u9358\u9359\u935a\u935b\u935c\u935d\u935e\u935f\u9360\u9361\u9362\u9363\u9364\u9365\u9366\u9367\u9368\u9369\u936a\u936b\u936c\u936d\u936e\u936f\u9370\u9371\u9372\u9373\u9374\u9375\u9376\u9377\u9378\u9379\u937a\u937b\u937c\u937d\u937e\u937f\u9380\u9381\u9382\u9383\u9384\u9385\u9386\u9387\u9388\u9389\u938a\u938b\u938c\u938d\u938e\u938f\u9390\u9391\u9392\u9393\u9394\u9395\u9396\u9397\u9398\u9399\u939a\u939b\u939c\u939d\u939e\u939f\u93a0\u93a1\u93a2\u93a3\u93a4\u93a5\u93a6\u93a7\u93a8\u93a9\u93aa\u93ab\u93ac\u93ad\u93ae\u93af\u93b0\u93b1\u93b2\u93b3\u93b4\u93b5\u93b6\u93b7\u93b8\u93b9\u93ba\u93bb\u93bc\u93bd\u93be\u93bf\u93c0\u93c1\u93c2\u93c3\u93c4\u93c5\u93c6\u93c7\u93c8\u93c9\u93ca\u93cb\u93cc\u93cd\u93ce\u93cf\u93d0\u93d1\u93d2\u93d3\u93d4\u93d5\u93d6\u93d7\u93d8\u93d9\u93da\u93db\u93dc\u93dd\u93de\u93df\u93e0\u93e1\u93e2\u93e3\u93e4\u93e5\u93e6\u93e7\u93e8\u93e9\u93ea\u93eb\u93ec\u93ed\u93ee\u93ef\u93f0\u93f1\u93f2\u93f3\u93f4\u93f5\u93f6\u93f7\u93f8\u93f9\u93fa\u93fb\u93fc\u93fd\u93fe\u93ff\u9400\u9401\u9402\u9403\u9404\u9405\u9406\u9407\u9408\u9409\u940a\u940b\u940c\u940d\u940e\u940f\u9410\u9411\u9412\u9413\u9414\u9415\u9416\u9417\u9418\u9419\u941a\u941b\u941c\u941d\u941e\u941f\u9420\u9421\u9422\u9423\u9424\u9425\u9426\u9427\u9428\u9429\u942a\u942b\u942c\u942d\u942e\u942f\u9430\u9431\u9432\u9433\u9434\u9435\u9436\u9437\u9438\u9439\u943a\u943b\u943c\u943d\u943e\u943f\u9440\u9441\u9442\u9443\u9444\u9445\u9446\u9447\u9448\u9449\u944a\u944b\u944c\u944d\u944e\u944f\u9450\u9451\u9452\u9453\u9454\u9455\u9456\u9457\u9458\u9459\u945a\u945b\u945c\u945d\u945e\u945f\u9460\u9461\u9462\u9463\u9464\u9465\u9466\u9467\u9468\u9469\u946a\u946b\u946c\u946d\u946e\u946f\u9470\u9471\u9472\u9473\u9474\u9475\u9476\u9477\u9478\u9479\u947a\u947b\u947c\u947d\u947e\u947f\u9480\u9481\u9482\u9483\u9484\u9485\u9486\u9487\u9488\u9489\u948a\u948b\u948c\u948d\u948e\u948f\u9490\u9491\u9492\u9493\u9494\u9495\u9496\u9497\u9498\u9499\u949a\u949b\u949c\u949d\u949e\u949f\u94a0\u94a1\u94a2\u94a3\u94a4\u94a5\u94a6\u94a7\u94a8\u94a9\u94aa\u94ab\u94ac\u94ad\u94ae\u94af\u94b0\u94b1\u94b2\u94b3\u94b4\u94b5\u94b6\u94b7\u94b8\u94b9\u94ba\u94bb\u94bc\u94bd\u94be\u94bf\u94c0\u94c1\u94c2\u94c3\u94c4\u94c5\u94c6\u94c7\u94c8\u94c9\u94ca\u94cb\u94cc\u94cd\u94ce\u94cf\u94d0\u94d1\u94d2\u94d3\u94d4\u94d5\u94d6\u94d7\u94d8\u94d9\u94da\u94db\u94dc\u94dd\u94de\u94df\u94e0\u94e1\u94e2\u94e3\u94e4\u94e5\u94e6\u94e7\u94e8\u94e9\u94ea\u94eb\u94ec\u94ed\u94ee\u94ef\u94f0\u94f1\u94f2\u94f3\u94f4\u94f5\u94f6\u94f7\u94f8\u94f9\u94fa\u94fb\u94fc\u94fd\u94fe\u94ff\u9500\u9501\u9502\u9503\u9504\u9505\u9506\u9507\u9508\u9509\u950a\u950b\u950c\u950d\u950e\u950f\u9510\u9511\u9512\u9513\u9514\u9515\u9516\u9517\u9518\u9519\u951a\u951b\u951c\u951d\u951e\u951f\u9520\u9521\u9522\u9523\u9524\u9525\u9526\u9527\u9528\u9529\u952a\u952b\u952c\u952d\u952e\u952f\u9530\u9531\u9532\u9533\u9534\u9535\u9536\u9537\u9538\u9539\u953a\u953b\u953c\u953d\u953e\u953f\u9540\u9541\u9542\u9543\u9544\u9545\u9546\u9547\u9548\u9549\u954a\u954b\u954c\u954d\u954e\u954f\u9550\u9551\u9552\u9553\u9554\u9555\u9556\u9557\u9558\u9559\u955a\u955b\u955c\u955d\u955e\u955f\u9560\u9561\u9562\u9563\u9564\u9565\u9566\u9567\u9568\u9569\u956a\u956b\u956c\u956d\u956e\u956f\u9570\u9571\u9572\u9573\u9574\u9575\u9576\u9577\u9578\u9579\u957a\u957b\u957c\u957d\u957e\u957f\u9580\u9581\u9582\u9583\u9584\u9585\u9586\u9587\u9588\u9589\u958a\u958b\u958c\u958d\u958e\u958f\u9590\u9591\u9592\u9593\u9594\u9595\u9596\u9597\u9598\u9599\u959a\u959b\u959c\u959d\u959e\u959f\u95a0\u95a1\u95a2\u95a3\u95a4\u95a5\u95a6\u95a7\u95a8\u95a9\u95aa\u95ab\u95ac\u95ad\u95ae\u95af\u95b0\u95b1\u95b2\u95b3\u95b4\u95b5\u95b6\u95b7\u95b8\u95b9\u95ba\u95bb\u95bc\u95bd\u95be\u95bf\u95c0\u95c1\u95c2\u95c3\u95c4\u95c5\u95c6\u95c7\u95c8\u95c9\u95ca\u95cb\u95cc\u95cd\u95ce\u95cf\u95d0\u95d1\u95d2\u95d3\u95d4\u95d5\u95d6\u95d7\u95d8\u95d9\u95da\u95db\u95dc\u95dd\u95de\u95df\u95e0\u95e1\u95e2\u95e3\u95e4\u95e5\u95e6\u95e7\u95e8\u95e9\u95ea\u95eb\u95ec\u95ed\u95ee\u95ef\u95f0\u95f1\u95f2\u95f3\u95f4\u95f5\u95f6\u95f7\u95f8\u95f9\u95fa\u95fb\u95fc\u95fd\u95fe\u95ff\u9600\u9601\u9602\u9603\u9604\u9605\u9606\u9607\u9608\u9609\u960a\u960b\u960c\u960d\u960e\u960f\u9610\u9611\u9612\u9613\u9614\u9615\u9616\u9617\u9618\u9619\u961a\u961b\u961c\u961d\u961e\u961f\u9620\u9621\u9622\u9623\u9624\u9625\u9626\u9627\u9628\u9629\u962a\u962b\u962c\u962d\u962e\u962f\u9630\u9631\u9632\u9633\u9634\u9635\u9636\u9637\u9638\u9639\u963a\u963b\u963c\u963d\u963e\u963f\u9640\u9641\u9642\u9643\u9644\u9645\u9646\u9647\u9648\u9649\u964a\u964b\u964c\u964d\u964e\u964f\u9650\u9651\u9652\u9653\u9654\u9655\u9656\u9657\u9658\u9659\u965a\u965b\u965c\u965d\u965e\u965f\u9660\u9661\u9662\u9663\u9664\u9665\u9666\u9667\u9668\u9669\u966a\u966b\u966c\u966d\u966e\u966f\u9670\u9671\u9672\u9673\u9674\u9675\u9676\u9677\u9678\u9679\u967a\u967b\u967c\u967d\u967e\u967f\u9680\u9681\u9682\u9683\u9684\u9685\u9686\u9687\u9688\u9689\u968a\u968b\u968c\u968d\u968e\u968f\u9690\u9691\u9692\u9693\u9694\u9695\u9696\u9697\u9698\u9699\u969a\u969b\u969c\u969d\u969e\u969f\u96a0\u96a1\u96a2\u96a3\u96a4\u96a5\u96a6\u96a7\u96a8\u96a9\u96aa\u96ab\u96ac\u96ad\u96ae\u96af\u96b0\u96b1\u96b2\u96b3\u96b4\u96b5\u96b6\u96b7\u96b8\u96b9\u96ba\u96bb\u96bc\u96bd\u96be\u96bf\u96c0\u96c1\u96c2\u96c3\u96c4\u96c5\u96c6\u96c7\u96c8\u96c9\u96ca\u96cb\u96cc\u96cd\u96ce\u96cf\u96d0\u96d1\u96d2\u96d3\u96d4\u96d5\u96d6\u96d7\u96d8\u96d9\u96da\u96db\u96dc\u96dd\u96de\u96df\u96e0\u96e1\u96e2\u96e3\u96e4\u96e5\u96e6\u96e7\u96e8\u96e9\u96ea\u96eb\u96ec\u96ed\u96ee\u96ef\u96f0\u96f1\u96f2\u96f3\u96f4\u96f5\u96f6\u96f7\u96f8\u96f9\u96fa\u96fb\u96fc\u96fd\u96fe\u96ff\u9700\u9701\u9702\u9703\u9704\u9705\u9706\u9707\u9708\u9709\u970a\u970b\u970c\u970d\u970e\u970f\u9710\u9711\u9712\u9713\u9714\u9715\u9716\u9717\u9718\u9719\u971a\u971b\u971c\u971d\u971e\u971f\u9720\u9721\u9722\u9723\u9724\u9725\u9726\u9727\u9728\u9729\u972a\u972b\u972c\u972d\u972e\u972f\u9730\u9731\u9732\u9733\u9734\u9735\u9736\u9737\u9738\u9739\u973a\u973b\u973c\u973d\u973e\u973f\u9740\u9741\u9742\u9743\u9744\u9745\u9746\u9747\u9748\u9749\u974a\u974b\u974c\u974d\u974e\u974f\u9750\u9751\u9752\u9753\u9754\u9755\u9756\u9757\u9758\u9759\u975a\u975b\u975c\u975d\u975e\u975f\u9760\u9761\u9762\u9763\u9764\u9765\u9766\u9767\u9768\u9769\u976a\u976b\u976c\u976d\u976e\u976f\u9770\u9771\u9772\u9773\u9774\u9775\u9776\u9777\u9778\u9779\u977a\u977b\u977c\u977d\u977e\u977f\u9780\u9781\u9782\u9783\u9784\u9785\u9786\u9787\u9788\u9789\u978a\u978b\u978c\u978d\u978e\u978f\u9790\u9791\u9792\u9793\u9794\u9795\u9796\u9797\u9798\u9799\u979a\u979b\u979c\u979d\u979e\u979f\u97a0\u97a1\u97a2\u97a3\u97a4\u97a5\u97a6\u97a7\u97a8\u97a9\u97aa\u97ab\u97ac\u97ad\u97ae\u97af\u97b0\u97b1\u97b2\u97b3\u97b4\u97b5\u97b6\u97b7\u97b8\u97b9\u97ba\u97bb\u97bc\u97bd\u97be\u97bf\u97c0\u97c1\u97c2\u97c3\u97c4\u97c5\u97c6\u97c7\u97c8\u97c9\u97ca\u97cb\u97cc\u97cd\u97ce\u97cf\u97d0\u97d1\u97d2\u97d3\u97d4\u97d5\u97d6\u97d7\u97d8\u97d9\u97da\u97db\u97dc\u97dd\u97de\u97df\u97e0\u97e1\u97e2\u97e3\u97e4\u97e5\u97e6\u97e7\u97e8\u97e9\u97ea\u97eb\u97ec\u97ed\u97ee\u97ef\u97f0\u97f1\u97f2\u97f3\u97f4\u97f5\u97f6\u97f7\u97f8\u97f9\u97fa\u97fb\u97fc\u97fd\u97fe\u97ff\u9800\u9801\u9802\u9803\u9804\u9805\u9806\u9807\u9808\u9809\u980a\u980b\u980c\u980d\u980e\u980f\u9810\u9811\u9812\u9813\u9814\u9815\u9816\u9817\u9818\u9819\u981a\u981b\u981c\u981d\u981e\u981f\u9820\u9821\u9822\u9823\u9824\u9825\u9826\u9827\u9828\u9829\u982a\u982b\u982c\u982d\u982e\u982f\u9830\u9831\u9832\u9833\u9834\u9835\u9836\u9837\u9838\u9839\u983a\u983b\u983c\u983d\u983e\u983f\u9840\u9841\u9842\u9843\u9844\u9845\u9846\u9847\u9848\u9849\u984a\u984b\u984c\u984d\u984e\u984f\u9850\u9851\u9852\u9853\u9854\u9855\u9856\u9857\u9858\u9859\u985a\u985b\u985c\u985d\u985e\u985f\u9860\u9861\u9862\u9863\u9864\u9865\u9866\u9867\u9868\u9869\u986a\u986b\u986c\u986d\u986e\u986f\u9870\u9871\u9872\u9873\u9874\u9875\u9876\u9877\u9878\u9879\u987a\u987b\u987c\u987d\u987e\u987f\u9880\u9881\u9882\u9883\u9884\u9885\u9886\u9887\u9888\u9889\u988a\u988b\u988c\u988d\u988e\u988f\u9890\u9891\u9892\u9893\u9894\u9895\u9896\u9897\u9898\u9899\u989a\u989b\u989c\u989d\u989e\u989f\u98a0\u98a1\u98a2\u98a3\u98a4\u98a5\u98a6\u98a7\u98a8\u98a9\u98aa\u98ab\u98ac\u98ad\u98ae\u98af\u98b0\u98b1\u98b2\u98b3\u98b4\u98b5\u98b6\u98b7\u98b8\u98b9\u98ba\u98bb\u98bc\u98bd\u98be\u98bf\u98c0\u98c1\u98c2\u98c3\u98c4\u98c5\u98c6\u98c7\u98c8\u98c9\u98ca\u98cb\u98cc\u98cd\u98ce\u98cf\u98d0\u98d1\u98d2\u98d3\u98d4\u98d5\u98d6\u98d7\u98d8\u98d9\u98da\u98db\u98dc\u98dd\u98de\u98df\u98e0\u98e1\u98e2\u98e3\u98e4\u98e5\u98e6\u98e7\u98e8\u98e9\u98ea\u98eb\u98ec\u98ed\u98ee\u98ef\u98f0\u98f1\u98f2\u98f3\u98f4\u98f5\u98f6\u98f7\u98f8\u98f9\u98fa\u98fb\u98fc\u98fd\u98fe\u98ff\u9900\u9901\u9902\u9903\u9904\u9905\u9906\u9907\u9908\u9909\u990a\u990b\u990c\u990d\u990e\u990f\u9910\u9911\u9912\u9913\u9914\u9915\u9916\u9917\u9918\u9919\u991a\u991b\u991c\u991d\u991e\u991f\u9920\u9921\u9922\u9923\u9924\u9925\u9926\u9927\u9928\u9929\u992a\u992b\u992c\u992d\u992e\u992f\u9930\u9931\u9932\u9933\u9934\u9935\u9936\u9937\u9938\u9939\u993a\u993b\u993c\u993d\u993e\u993f\u9940\u9941\u9942\u9943\u9944\u9945\u9946\u9947\u9948\u9949\u994a\u994b\u994c\u994d\u994e\u994f\u9950\u9951\u9952\u9953\u9954\u9955\u9956\u9957\u9958\u9959\u995a\u995b\u995c\u995d\u995e\u995f\u9960\u9961\u9962\u9963\u9964\u9965\u9966\u9967\u9968\u9969\u996a\u996b\u996c\u996d\u996e\u996f\u9970\u9971\u9972\u9973\u9974\u9975\u9976\u9977\u9978\u9979\u997a\u997b\u997c\u997d\u997e\u997f\u9980\u9981\u9982\u9983\u9984\u9985\u9986\u9987\u9988\u9989\u998a\u998b\u998c\u998d\u998e\u998f\u9990\u9991\u9992\u9993\u9994\u9995\u9996\u9997\u9998\u9999\u999a\u999b\u999c\u999d\u999e\u999f\u99a0\u99a1\u99a2\u99a3\u99a4\u99a5\u99a6\u99a7\u99a8\u99a9\u99aa\u99ab\u99ac\u99ad\u99ae\u99af\u99b0\u99b1\u99b2\u99b3\u99b4\u99b5\u99b6\u99b7\u99b8\u99b9\u99ba\u99bb\u99bc\u99bd\u99be\u99bf\u99c0\u99c1\u99c2\u99c3\u99c4\u99c5\u99c6\u99c7\u99c8\u99c9\u99ca\u99cb\u99cc\u99cd\u99ce\u99cf\u99d0\u99d1\u99d2\u99d3\u99d4\u99d5\u99d6\u99d7\u99d8\u99d9\u99da\u99db\u99dc\u99dd\u99de\u99df\u99e0\u99e1\u99e2\u99e3\u99e4\u99e5\u99e6\u99e7\u99e8\u99e9\u99ea\u99eb\u99ec\u99ed\u99ee\u99ef\u99f0\u99f1\u99f2\u99f3\u99f4\u99f5\u99f6\u99f7\u99f8\u99f9\u99fa\u99fb\u99fc\u99fd\u99fe\u99ff\u9a00\u9a01\u9a02\u9a03\u9a04\u9a05\u9a06\u9a07\u9a08\u9a09\u9a0a\u9a0b\u9a0c\u9a0d\u9a0e\u9a0f\u9a10\u9a11\u9a12\u9a13\u9a14\u9a15\u9a16\u9a17\u9a18\u9a19\u9a1a\u9a1b\u9a1c\u9a1d\u9a1e\u9a1f\u9a20\u9a21\u9a22\u9a23\u9a24\u9a25\u9a26\u9a27\u9a28\u9a29\u9a2a\u9a2b\u9a2c\u9a2d\u9a2e\u9a2f\u9a30\u9a31\u9a32\u9a33\u9a34\u9a35\u9a36\u9a37\u9a38\u9a39\u9a3a\u9a3b\u9a3c\u9a3d\u9a3e\u9a3f\u9a40\u9a41\u9a42\u9a43\u9a44\u9a45\u9a46\u9a47\u9a48\u9a49\u9a4a\u9a4b\u9a4c\u9a4d\u9a4e\u9a4f\u9a50\u9a51\u9a52\u9a53\u9a54\u9a55\u9a56\u9a57\u9a58\u9a59\u9a5a\u9a5b\u9a5c\u9a5d\u9a5e\u9a5f\u9a60\u9a61\u9a62\u9a63\u9a64\u9a65\u9a66\u9a67\u9a68\u9a69\u9a6a\u9a6b\u9a6c\u9a6d\u9a6e\u9a6f\u9a70\u9a71\u9a72\u9a73\u9a74\u9a75\u9a76\u9a77\u9a78\u9a79\u9a7a\u9a7b\u9a7c\u9a7d\u9a7e\u9a7f\u9a80\u9a81\u9a82\u9a83\u9a84\u9a85\u9a86\u9a87\u9a88\u9a89\u9a8a\u9a8b\u9a8c\u9a8d\u9a8e\u9a8f\u9a90\u9a91\u9a92\u9a93\u9a94\u9a95\u9a96\u9a97\u9a98\u9a99\u9a9a\u9a9b\u9a9c\u9a9d\u9a9e\u9a9f\u9aa0\u9aa1\u9aa2\u9aa3\u9aa4\u9aa5\u9aa6\u9aa7\u9aa8\u9aa9\u9aaa\u9aab\u9aac\u9aad\u9aae\u9aaf\u9ab0\u9ab1\u9ab2\u9ab3\u9ab4\u9ab5\u9ab6\u9ab7\u9ab8\u9ab9\u9aba\u9abb\u9abc\u9abd\u9abe\u9abf\u9ac0\u9ac1\u9ac2\u9ac3\u9ac4\u9ac5\u9ac6\u9ac7\u9ac8\u9ac9\u9aca\u9acb\u9acc\u9acd\u9ace\u9acf\u9ad0\u9ad1\u9ad2\u9ad3\u9ad4\u9ad5\u9ad6\u9ad7\u9ad8\u9ad9\u9ada\u9adb\u9adc\u9add\u9ade\u9adf\u9ae0\u9ae1\u9ae2\u9ae3\u9ae4\u9ae5\u9ae6\u9ae7\u9ae8\u9ae9\u9aea\u9aeb\u9aec\u9aed\u9aee\u9aef\u9af0\u9af1\u9af2\u9af3\u9af4\u9af5\u9af6\u9af7\u9af8\u9af9\u9afa\u9afb\u9afc\u9afd\u9afe\u9aff\u9b00\u9b01\u9b02\u9b03\u9b04\u9b05\u9b06\u9b07\u9b08\u9b09\u9b0a\u9b0b\u9b0c\u9b0d\u9b0e\u9b0f\u9b10\u9b11\u9b12\u9b13\u9b14\u9b15\u9b16\u9b17\u9b18\u9b19\u9b1a\u9b1b\u9b1c\u9b1d\u9b1e\u9b1f\u9b20\u9b21\u9b22\u9b23\u9b24\u9b25\u9b26\u9b27\u9b28\u9b29\u9b2a\u9b2b\u9b2c\u9b2d\u9b2e\u9b2f\u9b30\u9b31\u9b32\u9b33\u9b34\u9b35\u9b36\u9b37\u9b38\u9b39\u9b3a\u9b3b\u9b3c\u9b3d\u9b3e\u9b3f\u9b40\u9b41\u9b42\u9b43\u9b44\u9b45\u9b46\u9b47\u9b48\u9b49\u9b4a\u9b4b\u9b4c\u9b4d\u9b4e\u9b4f\u9b50\u9b51\u9b52\u9b53\u9b54\u9b55\u9b56\u9b57\u9b58\u9b59\u9b5a\u9b5b\u9b5c\u9b5d\u9b5e\u9b5f\u9b60\u9b61\u9b62\u9b63\u9b64\u9b65\u9b66\u9b67\u9b68\u9b69\u9b6a\u9b6b\u9b6c\u9b6d\u9b6e\u9b6f\u9b70\u9b71\u9b72\u9b73\u9b74\u9b75\u9b76\u9b77\u9b78\u9b79\u9b7a\u9b7b\u9b7c\u9b7d\u9b7e\u9b7f\u9b80\u9b81\u9b82\u9b83\u9b84\u9b85\u9b86\u9b87\u9b88\u9b89\u9b8a\u9b8b\u9b8c\u9b8d\u9b8e\u9b8f\u9b90\u9b91\u9b92\u9b93\u9b94\u9b95\u9b96\u9b97\u9b98\u9b99\u9b9a\u9b9b\u9b9c\u9b9d\u9b9e\u9b9f\u9ba0\u9ba1\u9ba2\u9ba3\u9ba4\u9ba5\u9ba6\u9ba7\u9ba8\u9ba9\u9baa\u9bab\u9bac\u9bad\u9bae\u9baf\u9bb0\u9bb1\u9bb2\u9bb3\u9bb4\u9bb5\u9bb6\u9bb7\u9bb8\u9bb9\u9bba\u9bbb\u9bbc\u9bbd\u9bbe\u9bbf\u9bc0\u9bc1\u9bc2\u9bc3\u9bc4\u9bc5\u9bc6\u9bc7\u9bc8\u9bc9\u9bca\u9bcb\u9bcc\u9bcd\u9bce\u9bcf\u9bd0\u9bd1\u9bd2\u9bd3\u9bd4\u9bd5\u9bd6\u9bd7\u9bd8\u9bd9\u9bda\u9bdb\u9bdc\u9bdd\u9bde\u9bdf\u9be0\u9be1\u9be2\u9be3\u9be4\u9be5\u9be6\u9be7\u9be8\u9be9\u9bea\u9beb\u9bec\u9bed\u9bee\u9bef\u9bf0\u9bf1\u9bf2\u9bf3\u9bf4\u9bf5\u9bf6\u9bf7\u9bf8\u9bf9\u9bfa\u9bfb\u9bfc\u9bfd\u9bfe\u9bff\u9c00\u9c01\u9c02\u9c03\u9c04\u9c05\u9c06\u9c07\u9c08\u9c09\u9c0a\u9c0b\u9c0c\u9c0d\u9c0e\u9c0f\u9c10\u9c11\u9c12\u9c13\u9c14\u9c15\u9c16\u9c17\u9c18\u9c19\u9c1a\u9c1b\u9c1c\u9c1d\u9c1e\u9c1f\u9c20\u9c21\u9c22\u9c23\u9c24\u9c25\u9c26\u9c27\u9c28\u9c29\u9c2a\u9c2b\u9c2c\u9c2d\u9c2e\u9c2f\u9c30\u9c31\u9c32\u9c33\u9c34\u9c35\u9c36\u9c37\u9c38\u9c39\u9c3a\u9c3b\u9c3c\u9c3d\u9c3e\u9c3f\u9c40\u9c41\u9c42\u9c43\u9c44\u9c45\u9c46\u9c47\u9c48\u9c49\u9c4a\u9c4b\u9c4c\u9c4d\u9c4e\u9c4f\u9c50\u9c51\u9c52\u9c53\u9c54\u9c55\u9c56\u9c57\u9c58\u9c59\u9c5a\u9c5b\u9c5c\u9c5d\u9c5e\u9c5f\u9c60\u9c61\u9c62\u9c63\u9c64\u9c65\u9c66\u9c67\u9c68\u9c69\u9c6a\u9c6b\u9c6c\u9c6d\u9c6e\u9c6f\u9c70\u9c71\u9c72\u9c73\u9c74\u9c75\u9c76\u9c77\u9c78\u9c79\u9c7a\u9c7b\u9c7c\u9c7d\u9c7e\u9c7f\u9c80\u9c81\u9c82\u9c83\u9c84\u9c85\u9c86\u9c87\u9c88\u9c89\u9c8a\u9c8b\u9c8c\u9c8d\u9c8e\u9c8f\u9c90\u9c91\u9c92\u9c93\u9c94\u9c95\u9c96\u9c97\u9c98\u9c99\u9c9a\u9c9b\u9c9c\u9c9d\u9c9e\u9c9f\u9ca0\u9ca1\u9ca2\u9ca3\u9ca4\u9ca5\u9ca6\u9ca7\u9ca8\u9ca9\u9caa\u9cab\u9cac\u9cad\u9cae\u9caf\u9cb0\u9cb1\u9cb2\u9cb3\u9cb4\u9cb5\u9cb6\u9cb7\u9cb8\u9cb9\u9cba\u9cbb\u9cbc\u9cbd\u9cbe\u9cbf\u9cc0\u9cc1\u9cc2\u9cc3\u9cc4\u9cc5\u9cc6\u9cc7\u9cc8\u9cc9\u9cca\u9ccb\u9ccc\u9ccd\u9cce\u9ccf\u9cd0\u9cd1\u9cd2\u9cd3\u9cd4\u9cd5\u9cd6\u9cd7\u9cd8\u9cd9\u9cda\u9cdb\u9cdc\u9cdd\u9cde\u9cdf\u9ce0\u9ce1\u9ce2\u9ce3\u9ce4\u9ce5\u9ce6\u9ce7\u9ce8\u9ce9\u9cea\u9ceb\u9cec\u9ced\u9cee\u9cef\u9cf0\u9cf1\u9cf2\u9cf3\u9cf4\u9cf5\u9cf6\u9cf7\u9cf8\u9cf9\u9cfa\u9cfb\u9cfc\u9cfd\u9cfe\u9cff\u9d00\u9d01\u9d02\u9d03\u9d04\u9d05\u9d06\u9d07\u9d08\u9d09\u9d0a\u9d0b\u9d0c\u9d0d\u9d0e\u9d0f\u9d10\u9d11\u9d12\u9d13\u9d14\u9d15\u9d16\u9d17\u9d18\u9d19\u9d1a\u9d1b\u9d1c\u9d1d\u9d1e\u9d1f\u9d20\u9d21\u9d22\u9d23\u9d24\u9d25\u9d26\u9d27\u9d28\u9d29\u9d2a\u9d2b\u9d2c\u9d2d\u9d2e\u9d2f\u9d30\u9d31\u9d32\u9d33\u9d34\u9d35\u9d36\u9d37\u9d38\u9d39\u9d3a\u9d3b\u9d3c\u9d3d\u9d3e\u9d3f\u9d40\u9d41\u9d42\u9d43\u9d44\u9d45\u9d46\u9d47\u9d48\u9d49\u9d4a\u9d4b\u9d4c\u9d4d\u9d4e\u9d4f\u9d50\u9d51\u9d52\u9d53\u9d54\u9d55\u9d56\u9d57\u9d58\u9d59\u9d5a\u9d5b\u9d5c\u9d5d\u9d5e\u9d5f\u9d60\u9d61\u9d62\u9d63\u9d64\u9d65\u9d66\u9d67\u9d68\u9d69\u9d6a\u9d6b\u9d6c\u9d6d\u9d6e\u9d6f\u9d70\u9d71\u9d72\u9d73\u9d74\u9d75\u9d76\u9d77\u9d78\u9d79\u9d7a\u9d7b\u9d7c\u9d7d\u9d7e\u9d7f\u9d80\u9d81\u9d82\u9d83\u9d84\u9d85\u9d86\u9d87\u9d88\u9d89\u9d8a\u9d8b\u9d8c\u9d8d\u9d8e\u9d8f\u9d90\u9d91\u9d92\u9d93\u9d94\u9d95\u9d96\u9d97\u9d98\u9d99\u9d9a\u9d9b\u9d9c\u9d9d\u9d9e\u9d9f\u9da0\u9da1\u9da2\u9da3\u9da4\u9da5\u9da6\u9da7\u9da8\u9da9\u9daa\u9dab\u9dac\u9dad\u9dae\u9daf\u9db0\u9db1\u9db2\u9db3\u9db4\u9db5\u9db6\u9db7\u9db8\u9db9\u9dba\u9dbb\u9dbc\u9dbd\u9dbe\u9dbf\u9dc0\u9dc1\u9dc2\u9dc3\u9dc4\u9dc5\u9dc6\u9dc7\u9dc8\u9dc9\u9dca\u9dcb\u9dcc\u9dcd\u9dce\u9dcf\u9dd0\u9dd1\u9dd2\u9dd3\u9dd4\u9dd5\u9dd6\u9dd7\u9dd8\u9dd9\u9dda\u9ddb\u9ddc\u9ddd\u9dde\u9ddf\u9de0\u9de1\u9de2\u9de3\u9de4\u9de5\u9de6\u9de7\u9de8\u9de9\u9dea\u9deb\u9dec\u9ded\u9dee\u9def\u9df0\u9df1\u9df2\u9df3\u9df4\u9df5\u9df6\u9df7\u9df8\u9df9\u9dfa\u9dfb\u9dfc\u9dfd\u9dfe\u9dff\u9e00\u9e01\u9e02\u9e03\u9e04\u9e05\u9e06\u9e07\u9e08\u9e09\u9e0a\u9e0b\u9e0c\u9e0d\u9e0e\u9e0f\u9e10\u9e11\u9e12\u9e13\u9e14\u9e15\u9e16\u9e17\u9e18\u9e19\u9e1a\u9e1b\u9e1c\u9e1d\u9e1e\u9e1f\u9e20\u9e21\u9e22\u9e23\u9e24\u9e25\u9e26\u9e27\u9e28\u9e29\u9e2a\u9e2b\u9e2c\u9e2d\u9e2e\u9e2f\u9e30\u9e31\u9e32\u9e33\u9e34\u9e35\u9e36\u9e37\u9e38\u9e39\u9e3a\u9e3b\u9e3c\u9e3d\u9e3e\u9e3f\u9e40\u9e41\u9e42\u9e43\u9e44\u9e45\u9e46\u9e47\u9e48\u9e49\u9e4a\u9e4b\u9e4c\u9e4d\u9e4e\u9e4f\u9e50\u9e51\u9e52\u9e53\u9e54\u9e55\u9e56\u9e57\u9e58\u9e59\u9e5a\u9e5b\u9e5c\u9e5d\u9e5e\u9e5f\u9e60\u9e61\u9e62\u9e63\u9e64\u9e65\u9e66\u9e67\u9e68\u9e69\u9e6a\u9e6b\u9e6c\u9e6d\u9e6e\u9e6f\u9e70\u9e71\u9e72\u9e73\u9e74\u9e75\u9e76\u9e77\u9e78\u9e79\u9e7a\u9e7b\u9e7c\u9e7d\u9e7e\u9e7f\u9e80\u9e81\u9e82\u9e83\u9e84\u9e85\u9e86\u9e87\u9e88\u9e89\u9e8a\u9e8b\u9e8c\u9e8d\u9e8e\u9e8f\u9e90\u9e91\u9e92\u9e93\u9e94\u9e95\u9e96\u9e97\u9e98\u9e99\u9e9a\u9e9b\u9e9c\u9e9d\u9e9e\u9e9f\u9ea0\u9ea1\u9ea2\u9ea3\u9ea4\u9ea5\u9ea6\u9ea7\u9ea8\u9ea9\u9eaa\u9eab\u9eac\u9ead\u9eae\u9eaf\u9eb0\u9eb1\u9eb2\u9eb3\u9eb4\u9eb5\u9eb6\u9eb7\u9eb8\u9eb9\u9eba\u9ebb\u9ebc\u9ebd\u9ebe\u9ebf\u9ec0\u9ec1\u9ec2\u9ec3\u9ec4\u9ec5\u9ec6\u9ec7\u9ec8\u9ec9\u9eca\u9ecb\u9ecc\u9ecd\u9ece\u9ecf\u9ed0\u9ed1\u9ed2\u9ed3\u9ed4\u9ed5\u9ed6\u9ed7\u9ed8\u9ed9\u9eda\u9edb\u9edc\u9edd\u9ede\u9edf\u9ee0\u9ee1\u9ee2\u9ee3\u9ee4\u9ee5\u9ee6\u9ee7\u9ee8\u9ee9\u9eea\u9eeb\u9eec\u9eed\u9eee\u9eef\u9ef0\u9ef1\u9ef2\u9ef3\u9ef4\u9ef5\u9ef6\u9ef7\u9ef8\u9ef9\u9efa\u9efb\u9efc\u9efd\u9efe\u9eff\u9f00\u9f01\u9f02\u9f03\u9f04\u9f05\u9f06\u9f07\u9f08\u9f09\u9f0a\u9f0b\u9f0c\u9f0d\u9f0e\u9f0f\u9f10\u9f11\u9f12\u9f13\u9f14\u9f15\u9f16\u9f17\u9f18\u9f19\u9f1a\u9f1b\u9f1c\u9f1d\u9f1e\u9f1f\u9f20\u9f21\u9f22\u9f23\u9f24\u9f25\u9f26\u9f27\u9f28\u9f29\u9f2a\u9f2b\u9f2c\u9f2d\u9f2e\u9f2f\u9f30\u9f31\u9f32\u9f33\u9f34\u9f35\u9f36\u9f37\u9f38\u9f39\u9f3a\u9f3b\u9f3c\u9f3d\u9f3e\u9f3f\u9f40\u9f41\u9f42\u9f43\u9f44\u9f45\u9f46\u9f47\u9f48\u9f49\u9f4a\u9f4b\u9f4c\u9f4d\u9f4e\u9f4f\u9f50\u9f51\u9f52\u9f53\u9f54\u9f55\u9f56\u9f57\u9f58\u9f59\u9f5a\u9f5b\u9f5c\u9f5d\u9f5e\u9f5f\u9f60\u9f61\u9f62\u9f63\u9f64\u9f65\u9f66\u9f67\u9f68\u9f69\u9f6a\u9f6b\u9f6c\u9f6d\u9f6e\u9f6f\u9f70\u9f71\u9f72\u9f73\u9f74\u9f75\u9f76\u9f77\u9f78\u9f79\u9f7a\u9f7b\u9f7c\u9f7d\u9f7e\u9f7f\u9f80\u9f81\u9f82\u9f83\u9f84\u9f85\u9f86\u9f87\u9f88\u9f89\u9f8a\u9f8b\u9f8c\u9f8d\u9f8e\u9f8f\u9f90\u9f91\u9f92\u9f93\u9f94\u9f95\u9f96\u9f97\u9f98\u9f99\u9f9a\u9f9b\u9f9c\u9f9d\u9f9e\u9f9f\u9fa0\u9fa1\u9fa2\u9fa3\u9fa4\u9fa5\u9fa6\u9fa7\u9fa8\u9fa9\u9faa\u9fab\u9fac\u9fad\u9fae\u9faf\u9fb0\u9fb1\u9fb2\u9fb3\u9fb4\u9fb5\u9fb6\u9fb7\u9fb8\u9fb9\u9fba\u9fbb\ua000\ua001\ua002\ua003\ua004\ua005\ua006\ua007\ua008\ua009\ua00a\ua00b\ua00c\ua00d\ua00e\ua00f\ua010\ua011\ua012\ua013\ua014\ua016\ua017\ua018\ua019\ua01a\ua01b\ua01c\ua01d\ua01e\ua01f\ua020\ua021\ua022\ua023\ua024\ua025\ua026\ua027\ua028\ua029\ua02a\ua02b\ua02c\ua02d\ua02e\ua02f\ua030\ua031\ua032\ua033\ua034\ua035\ua036\ua037\ua038\ua039\ua03a\ua03b\ua03c\ua03d\ua03e\ua03f\ua040\ua041\ua042\ua043\ua044\ua045\ua046\ua047\ua048\ua049\ua04a\ua04b\ua04c\ua04d\ua04e\ua04f\ua050\ua051\ua052\ua053\ua054\ua055\ua056\ua057\ua058\ua059\ua05a\ua05b\ua05c\ua05d\ua05e\ua05f\ua060\ua061\ua062\ua063\ua064\ua065\ua066\ua067\ua068\ua069\ua06a\ua06b\ua06c\ua06d\ua06e\ua06f\ua070\ua071\ua072\ua073\ua074\ua075\ua076\ua077\ua078\ua079\ua07a\ua07b\ua07c\ua07d\ua07e\ua07f\ua080\ua081\ua082\ua083\ua084\ua085\ua086\ua087\ua088\ua089\ua08a\ua08b\ua08c\ua08d\ua08e\ua08f\ua090\ua091\ua092\ua093\ua094\ua095\ua096\ua097\ua098\ua099\ua09a\ua09b\ua09c\ua09d\ua09e\ua09f\ua0a0\ua0a1\ua0a2\ua0a3\ua0a4\ua0a5\ua0a6\ua0a7\ua0a8\ua0a9\ua0aa\ua0ab\ua0ac\ua0ad\ua0ae\ua0af\ua0b0\ua0b1\ua0b2\ua0b3\ua0b4\ua0b5\ua0b6\ua0b7\ua0b8\ua0b9\ua0ba\ua0bb\ua0bc\ua0bd\ua0be\ua0bf\ua0c0\ua0c1\ua0c2\ua0c3\ua0c4\ua0c5\ua0c6\ua0c7\ua0c8\ua0c9\ua0ca\ua0cb\ua0cc\ua0cd\ua0ce\ua0cf\ua0d0\ua0d1\ua0d2\ua0d3\ua0d4\ua0d5\ua0d6\ua0d7\ua0d8\ua0d9\ua0da\ua0db\ua0dc\ua0dd\ua0de\ua0df\ua0e0\ua0e1\ua0e2\ua0e3\ua0e4\ua0e5\ua0e6\ua0e7\ua0e8\ua0e9\ua0ea\ua0eb\ua0ec\ua0ed\ua0ee\ua0ef\ua0f0\ua0f1\ua0f2\ua0f3\ua0f4\ua0f5\ua0f6\ua0f7\ua0f8\ua0f9\ua0fa\ua0fb\ua0fc\ua0fd\ua0fe\ua0ff\ua100\ua101\ua102\ua103\ua104\ua105\ua106\ua107\ua108\ua109\ua10a\ua10b\ua10c\ua10d\ua10e\ua10f\ua110\ua111\ua112\ua113\ua114\ua115\ua116\ua117\ua118\ua119\ua11a\ua11b\ua11c\ua11d\ua11e\ua11f\ua120\ua121\ua122\ua123\ua124\ua125\ua126\ua127\ua128\ua129\ua12a\ua12b\ua12c\ua12d\ua12e\ua12f\ua130\ua131\ua132\ua133\ua134\ua135\ua136\ua137\ua138\ua139\ua13a\ua13b\ua13c\ua13d\ua13e\ua13f\ua140\ua141\ua142\ua143\ua144\ua145\ua146\ua147\ua148\ua149\ua14a\ua14b\ua14c\ua14d\ua14e\ua14f\ua150\ua151\ua152\ua153\ua154\ua155\ua156\ua157\ua158\ua159\ua15a\ua15b\ua15c\ua15d\ua15e\ua15f\ua160\ua161\ua162\ua163\ua164\ua165\ua166\ua167\ua168\ua169\ua16a\ua16b\ua16c\ua16d\ua16e\ua16f\ua170\ua171\ua172\ua173\ua174\ua175\ua176\ua177\ua178\ua179\ua17a\ua17b\ua17c\ua17d\ua17e\ua17f\ua180\ua181\ua182\ua183\ua184\ua185\ua186\ua187\ua188\ua189\ua18a\ua18b\ua18c\ua18d\ua18e\ua18f\ua190\ua191\ua192\ua193\ua194\ua195\ua196\ua197\ua198\ua199\ua19a\ua19b\ua19c\ua19d\ua19e\ua19f\ua1a0\ua1a1\ua1a2\ua1a3\ua1a4\ua1a5\ua1a6\ua1a7\ua1a8\ua1a9\ua1aa\ua1ab\ua1ac\ua1ad\ua1ae\ua1af\ua1b0\ua1b1\ua1b2\ua1b3\ua1b4\ua1b5\ua1b6\ua1b7\ua1b8\ua1b9\ua1ba\ua1bb\ua1bc\ua1bd\ua1be\ua1bf\ua1c0\ua1c1\ua1c2\ua1c3\ua1c4\ua1c5\ua1c6\ua1c7\ua1c8\ua1c9\ua1ca\ua1cb\ua1cc\ua1cd\ua1ce\ua1cf\ua1d0\ua1d1\ua1d2\ua1d3\ua1d4\ua1d5\ua1d6\ua1d7\ua1d8\ua1d9\ua1da\ua1db\ua1dc\ua1dd\ua1de\ua1df\ua1e0\ua1e1\ua1e2\ua1e3\ua1e4\ua1e5\ua1e6\ua1e7\ua1e8\ua1e9\ua1ea\ua1eb\ua1ec\ua1ed\ua1ee\ua1ef\ua1f0\ua1f1\ua1f2\ua1f3\ua1f4\ua1f5\ua1f6\ua1f7\ua1f8\ua1f9\ua1fa\ua1fb\ua1fc\ua1fd\ua1fe\ua1ff\ua200\ua201\ua202\ua203\ua204\ua205\ua206\ua207\ua208\ua209\ua20a\ua20b\ua20c\ua20d\ua20e\ua20f\ua210\ua211\ua212\ua213\ua214\ua215\ua216\ua217\ua218\ua219\ua21a\ua21b\ua21c\ua21d\ua21e\ua21f\ua220\ua221\ua222\ua223\ua224\ua225\ua226\ua227\ua228\ua229\ua22a\ua22b\ua22c\ua22d\ua22e\ua22f\ua230\ua231\ua232\ua233\ua234\ua235\ua236\ua237\ua238\ua239\ua23a\ua23b\ua23c\ua23d\ua23e\ua23f\ua240\ua241\ua242\ua243\ua244\ua245\ua246\ua247\ua248\ua249\ua24a\ua24b\ua24c\ua24d\ua24e\ua24f\ua250\ua251\ua252\ua253\ua254\ua255\ua256\ua257\ua258\ua259\ua25a\ua25b\ua25c\ua25d\ua25e\ua25f\ua260\ua261\ua262\ua263\ua264\ua265\ua266\ua267\ua268\ua269\ua26a\ua26b\ua26c\ua26d\ua26e\ua26f\ua270\ua271\ua272\ua273\ua274\ua275\ua276\ua277\ua278\ua279\ua27a\ua27b\ua27c\ua27d\ua27e\ua27f\ua280\ua281\ua282\ua283\ua284\ua285\ua286\ua287\ua288\ua289\ua28a\ua28b\ua28c\ua28d\ua28e\ua28f\ua290\ua291\ua292\ua293\ua294\ua295\ua296\ua297\ua298\ua299\ua29a\ua29b\ua29c\ua29d\ua29e\ua29f\ua2a0\ua2a1\ua2a2\ua2a3\ua2a4\ua2a5\ua2a6\ua2a7\ua2a8\ua2a9\ua2aa\ua2ab\ua2ac\ua2ad\ua2ae\ua2af\ua2b0\ua2b1\ua2b2\ua2b3\ua2b4\ua2b5\ua2b6\ua2b7\ua2b8\ua2b9\ua2ba\ua2bb\ua2bc\ua2bd\ua2be\ua2bf\ua2c0\ua2c1\ua2c2\ua2c3\ua2c4\ua2c5\ua2c6\ua2c7\ua2c8\ua2c9\ua2ca\ua2cb\ua2cc\ua2cd\ua2ce\ua2cf\ua2d0\ua2d1\ua2d2\ua2d3\ua2d4\ua2d5\ua2d6\ua2d7\ua2d8\ua2d9\ua2da\ua2db\ua2dc\ua2dd\ua2de\ua2df\ua2e0\ua2e1\ua2e2\ua2e3\ua2e4\ua2e5\ua2e6\ua2e7\ua2e8\ua2e9\ua2ea\ua2eb\ua2ec\ua2ed\ua2ee\ua2ef\ua2f0\ua2f1\ua2f2\ua2f3\ua2f4\ua2f5\ua2f6\ua2f7\ua2f8\ua2f9\ua2fa\ua2fb\ua2fc\ua2fd\ua2fe\ua2ff\ua300\ua301\ua302\ua303\ua304\ua305\ua306\ua307\ua308\ua309\ua30a\ua30b\ua30c\ua30d\ua30e\ua30f\ua310\ua311\ua312\ua313\ua314\ua315\ua316\ua317\ua318\ua319\ua31a\ua31b\ua31c\ua31d\ua31e\ua31f\ua320\ua321\ua322\ua323\ua324\ua325\ua326\ua327\ua328\ua329\ua32a\ua32b\ua32c\ua32d\ua32e\ua32f\ua330\ua331\ua332\ua333\ua334\ua335\ua336\ua337\ua338\ua339\ua33a\ua33b\ua33c\ua33d\ua33e\ua33f\ua340\ua341\ua342\ua343\ua344\ua345\ua346\ua347\ua348\ua349\ua34a\ua34b\ua34c\ua34d\ua34e\ua34f\ua350\ua351\ua352\ua353\ua354\ua355\ua356\ua357\ua358\ua359\ua35a\ua35b\ua35c\ua35d\ua35e\ua35f\ua360\ua361\ua362\ua363\ua364\ua365\ua366\ua367\ua368\ua369\ua36a\ua36b\ua36c\ua36d\ua36e\ua36f\ua370\ua371\ua372\ua373\ua374\ua375\ua376\ua377\ua378\ua379\ua37a\ua37b\ua37c\ua37d\ua37e\ua37f\ua380\ua381\ua382\ua383\ua384\ua385\ua386\ua387\ua388\ua389\ua38a\ua38b\ua38c\ua38d\ua38e\ua38f\ua390\ua391\ua392\ua393\ua394\ua395\ua396\ua397\ua398\ua399\ua39a\ua39b\ua39c\ua39d\ua39e\ua39f\ua3a0\ua3a1\ua3a2\ua3a3\ua3a4\ua3a5\ua3a6\ua3a7\ua3a8\ua3a9\ua3aa\ua3ab\ua3ac\ua3ad\ua3ae\ua3af\ua3b0\ua3b1\ua3b2\ua3b3\ua3b4\ua3b5\ua3b6\ua3b7\ua3b8\ua3b9\ua3ba\ua3bb\ua3bc\ua3bd\ua3be\ua3bf\ua3c0\ua3c1\ua3c2\ua3c3\ua3c4\ua3c5\ua3c6\ua3c7\ua3c8\ua3c9\ua3ca\ua3cb\ua3cc\ua3cd\ua3ce\ua3cf\ua3d0\ua3d1\ua3d2\ua3d3\ua3d4\ua3d5\ua3d6\ua3d7\ua3d8\ua3d9\ua3da\ua3db\ua3dc\ua3dd\ua3de\ua3df\ua3e0\ua3e1\ua3e2\ua3e3\ua3e4\ua3e5\ua3e6\ua3e7\ua3e8\ua3e9\ua3ea\ua3eb\ua3ec\ua3ed\ua3ee\ua3ef\ua3f0\ua3f1\ua3f2\ua3f3\ua3f4\ua3f5\ua3f6\ua3f7\ua3f8\ua3f9\ua3fa\ua3fb\ua3fc\ua3fd\ua3fe\ua3ff\ua400\ua401\ua402\ua403\ua404\ua405\ua406\ua407\ua408\ua409\ua40a\ua40b\ua40c\ua40d\ua40e\ua40f\ua410\ua411\ua412\ua413\ua414\ua415\ua416\ua417\ua418\ua419\ua41a\ua41b\ua41c\ua41d\ua41e\ua41f\ua420\ua421\ua422\ua423\ua424\ua425\ua426\ua427\ua428\ua429\ua42a\ua42b\ua42c\ua42d\ua42e\ua42f\ua430\ua431\ua432\ua433\ua434\ua435\ua436\ua437\ua438\ua439\ua43a\ua43b\ua43c\ua43d\ua43e\ua43f\ua440\ua441\ua442\ua443\ua444\ua445\ua446\ua447\ua448\ua449\ua44a\ua44b\ua44c\ua44d\ua44e\ua44f\ua450\ua451\ua452\ua453\ua454\ua455\ua456\ua457\ua458\ua459\ua45a\ua45b\ua45c\ua45d\ua45e\ua45f\ua460\ua461\ua462\ua463\ua464\ua465\ua466\ua467\ua468\ua469\ua46a\ua46b\ua46c\ua46d\ua46e\ua46f\ua470\ua471\ua472\ua473\ua474\ua475\ua476\ua477\ua478\ua479\ua47a\ua47b\ua47c\ua47d\ua47e\ua47f\ua480\ua481\ua482\ua483\ua484\ua485\ua486\ua487\ua488\ua489\ua48a\ua48b\ua48c\ua800\ua801\ua803\ua804\ua805\ua807\ua808\ua809\ua80a\ua80c\ua80d\ua80e\ua80f\ua810\ua811\ua812\ua813\ua814\ua815\ua816\ua817\ua818\ua819\ua81a\ua81b\ua81c\ua81d\ua81e\ua81f\ua820\ua821\ua822\uac00\uac01\uac02\uac03\uac04\uac05\uac06\uac07\uac08\uac09\uac0a\uac0b\uac0c\uac0d\uac0e\uac0f\uac10\uac11\uac12\uac13\uac14\uac15\uac16\uac17\uac18\uac19\uac1a\uac1b\uac1c\uac1d\uac1e\uac1f\uac20\uac21\uac22\uac23\uac24\uac25\uac26\uac27\uac28\uac29\uac2a\uac2b\uac2c\uac2d\uac2e\uac2f\uac30\uac31\uac32\uac33\uac34\uac35\uac36\uac37\uac38\uac39\uac3a\uac3b\uac3c\uac3d\uac3e\uac3f\uac40\uac41\uac42\uac43\uac44\uac45\uac46\uac47\uac48\uac49\uac4a\uac4b\uac4c\uac4d\uac4e\uac4f\uac50\uac51\uac52\uac53\uac54\uac55\uac56\uac57\uac58\uac59\uac5a\uac5b\uac5c\uac5d\uac5e\uac5f\uac60\uac61\uac62\uac63\uac64\uac65\uac66\uac67\uac68\uac69\uac6a\uac6b\uac6c\uac6d\uac6e\uac6f\uac70\uac71\uac72\uac73\uac74\uac75\uac76\uac77\uac78\uac79\uac7a\uac7b\uac7c\uac7d\uac7e\uac7f\uac80\uac81\uac82\uac83\uac84\uac85\uac86\uac87\uac88\uac89\uac8a\uac8b\uac8c\uac8d\uac8e\uac8f\uac90\uac91\uac92\uac93\uac94\uac95\uac96\uac97\uac98\uac99\uac9a\uac9b\uac9c\uac9d\uac9e\uac9f\uaca0\uaca1\uaca2\uaca3\uaca4\uaca5\uaca6\uaca7\uaca8\uaca9\uacaa\uacab\uacac\uacad\uacae\uacaf\uacb0\uacb1\uacb2\uacb3\uacb4\uacb5\uacb6\uacb7\uacb8\uacb9\uacba\uacbb\uacbc\uacbd\uacbe\uacbf\uacc0\uacc1\uacc2\uacc3\uacc4\uacc5\uacc6\uacc7\uacc8\uacc9\uacca\uaccb\uaccc\uaccd\uacce\uaccf\uacd0\uacd1\uacd2\uacd3\uacd4\uacd5\uacd6\uacd7\uacd8\uacd9\uacda\uacdb\uacdc\uacdd\uacde\uacdf\uace0\uace1\uace2\uace3\uace4\uace5\uace6\uace7\uace8\uace9\uacea\uaceb\uacec\uaced\uacee\uacef\uacf0\uacf1\uacf2\uacf3\uacf4\uacf5\uacf6\uacf7\uacf8\uacf9\uacfa\uacfb\uacfc\uacfd\uacfe\uacff\uad00\uad01\uad02\uad03\uad04\uad05\uad06\uad07\uad08\uad09\uad0a\uad0b\uad0c\uad0d\uad0e\uad0f\uad10\uad11\uad12\uad13\uad14\uad15\uad16\uad17\uad18\uad19\uad1a\uad1b\uad1c\uad1d\uad1e\uad1f\uad20\uad21\uad22\uad23\uad24\uad25\uad26\uad27\uad28\uad29\uad2a\uad2b\uad2c\uad2d\uad2e\uad2f\uad30\uad31\uad32\uad33\uad34\uad35\uad36\uad37\uad38\uad39\uad3a\uad3b\uad3c\uad3d\uad3e\uad3f\uad40\uad41\uad42\uad43\uad44\uad45\uad46\uad47\uad48\uad49\uad4a\uad4b\uad4c\uad4d\uad4e\uad4f\uad50\uad51\uad52\uad53\uad54\uad55\uad56\uad57\uad58\uad59\uad5a\uad5b\uad5c\uad5d\uad5e\uad5f\uad60\uad61\uad62\uad63\uad64\uad65\uad66\uad67\uad68\uad69\uad6a\uad6b\uad6c\uad6d\uad6e\uad6f\uad70\uad71\uad72\uad73\uad74\uad75\uad76\uad77\uad78\uad79\uad7a\uad7b\uad7c\uad7d\uad7e\uad7f\uad80\uad81\uad82\uad83\uad84\uad85\uad86\uad87\uad88\uad89\uad8a\uad8b\uad8c\uad8d\uad8e\uad8f\uad90\uad91\uad92\uad93\uad94\uad95\uad96\uad97\uad98\uad99\uad9a\uad9b\uad9c\uad9d\uad9e\uad9f\uada0\uada1\uada2\uada3\uada4\uada5\uada6\uada7\uada8\uada9\uadaa\uadab\uadac\uadad\uadae\uadaf\uadb0\uadb1\uadb2\uadb3\uadb4\uadb5\uadb6\uadb7\uadb8\uadb9\uadba\uadbb\uadbc\uadbd\uadbe\uadbf\uadc0\uadc1\uadc2\uadc3\uadc4\uadc5\uadc6\uadc7\uadc8\uadc9\uadca\uadcb\uadcc\uadcd\uadce\uadcf\uadd0\uadd1\uadd2\uadd3\uadd4\uadd5\uadd6\uadd7\uadd8\uadd9\uadda\uaddb\uaddc\uaddd\uadde\uaddf\uade0\uade1\uade2\uade3\uade4\uade5\uade6\uade7\uade8\uade9\uadea\uadeb\uadec\uaded\uadee\uadef\uadf0\uadf1\uadf2\uadf3\uadf4\uadf5\uadf6\uadf7\uadf8\uadf9\uadfa\uadfb\uadfc\uadfd\uadfe\uadff\uae00\uae01\uae02\uae03\uae04\uae05\uae06\uae07\uae08\uae09\uae0a\uae0b\uae0c\uae0d\uae0e\uae0f\uae10\uae11\uae12\uae13\uae14\uae15\uae16\uae17\uae18\uae19\uae1a\uae1b\uae1c\uae1d\uae1e\uae1f\uae20\uae21\uae22\uae23\uae24\uae25\uae26\uae27\uae28\uae29\uae2a\uae2b\uae2c\uae2d\uae2e\uae2f\uae30\uae31\uae32\uae33\uae34\uae35\uae36\uae37\uae38\uae39\uae3a\uae3b\uae3c\uae3d\uae3e\uae3f\uae40\uae41\uae42\uae43\uae44\uae45\uae46\uae47\uae48\uae49\uae4a\uae4b\uae4c\uae4d\uae4e\uae4f\uae50\uae51\uae52\uae53\uae54\uae55\uae56\uae57\uae58\uae59\uae5a\uae5b\uae5c\uae5d\uae5e\uae5f\uae60\uae61\uae62\uae63\uae64\uae65\uae66\uae67\uae68\uae69\uae6a\uae6b\uae6c\uae6d\uae6e\uae6f\uae70\uae71\uae72\uae73\uae74\uae75\uae76\uae77\uae78\uae79\uae7a\uae7b\uae7c\uae7d\uae7e\uae7f\uae80\uae81\uae82\uae83\uae84\uae85\uae86\uae87\uae88\uae89\uae8a\uae8b\uae8c\uae8d\uae8e\uae8f\uae90\uae91\uae92\uae93\uae94\uae95\uae96\uae97\uae98\uae99\uae9a\uae9b\uae9c\uae9d\uae9e\uae9f\uaea0\uaea1\uaea2\uaea3\uaea4\uaea5\uaea6\uaea7\uaea8\uaea9\uaeaa\uaeab\uaeac\uaead\uaeae\uaeaf\uaeb0\uaeb1\uaeb2\uaeb3\uaeb4\uaeb5\uaeb6\uaeb7\uaeb8\uaeb9\uaeba\uaebb\uaebc\uaebd\uaebe\uaebf\uaec0\uaec1\uaec2\uaec3\uaec4\uaec5\uaec6\uaec7\uaec8\uaec9\uaeca\uaecb\uaecc\uaecd\uaece\uaecf\uaed0\uaed1\uaed2\uaed3\uaed4\uaed5\uaed6\uaed7\uaed8\uaed9\uaeda\uaedb\uaedc\uaedd\uaede\uaedf\uaee0\uaee1\uaee2\uaee3\uaee4\uaee5\uaee6\uaee7\uaee8\uaee9\uaeea\uaeeb\uaeec\uaeed\uaeee\uaeef\uaef0\uaef1\uaef2\uaef3\uaef4\uaef5\uaef6\uaef7\uaef8\uaef9\uaefa\uaefb\uaefc\uaefd\uaefe\uaeff\uaf00\uaf01\uaf02\uaf03\uaf04\uaf05\uaf06\uaf07\uaf08\uaf09\uaf0a\uaf0b\uaf0c\uaf0d\uaf0e\uaf0f\uaf10\uaf11\uaf12\uaf13\uaf14\uaf15\uaf16\uaf17\uaf18\uaf19\uaf1a\uaf1b\uaf1c\uaf1d\uaf1e\uaf1f\uaf20\uaf21\uaf22\uaf23\uaf24\uaf25\uaf26\uaf27\uaf28\uaf29\uaf2a\uaf2b\uaf2c\uaf2d\uaf2e\uaf2f\uaf30\uaf31\uaf32\uaf33\uaf34\uaf35\uaf36\uaf37\uaf38\uaf39\uaf3a\uaf3b\uaf3c\uaf3d\uaf3e\uaf3f\uaf40\uaf41\uaf42\uaf43\uaf44\uaf45\uaf46\uaf47\uaf48\uaf49\uaf4a\uaf4b\uaf4c\uaf4d\uaf4e\uaf4f\uaf50\uaf51\uaf52\uaf53\uaf54\uaf55\uaf56\uaf57\uaf58\uaf59\uaf5a\uaf5b\uaf5c\uaf5d\uaf5e\uaf5f\uaf60\uaf61\uaf62\uaf63\uaf64\uaf65\uaf66\uaf67\uaf68\uaf69\uaf6a\uaf6b\uaf6c\uaf6d\uaf6e\uaf6f\uaf70\uaf71\uaf72\uaf73\uaf74\uaf75\uaf76\uaf77\uaf78\uaf79\uaf7a\uaf7b\uaf7c\uaf7d\uaf7e\uaf7f\uaf80\uaf81\uaf82\uaf83\uaf84\uaf85\uaf86\uaf87\uaf88\uaf89\uaf8a\uaf8b\uaf8c\uaf8d\uaf8e\uaf8f\uaf90\uaf91\uaf92\uaf93\uaf94\uaf95\uaf96\uaf97\uaf98\uaf99\uaf9a\uaf9b\uaf9c\uaf9d\uaf9e\uaf9f\uafa0\uafa1\uafa2\uafa3\uafa4\uafa5\uafa6\uafa7\uafa8\uafa9\uafaa\uafab\uafac\uafad\uafae\uafaf\uafb0\uafb1\uafb2\uafb3\uafb4\uafb5\uafb6\uafb7\uafb8\uafb9\uafba\uafbb\uafbc\uafbd\uafbe\uafbf\uafc0\uafc1\uafc2\uafc3\uafc4\uafc5\uafc6\uafc7\uafc8\uafc9\uafca\uafcb\uafcc\uafcd\uafce\uafcf\uafd0\uafd1\uafd2\uafd3\uafd4\uafd5\uafd6\uafd7\uafd8\uafd9\uafda\uafdb\uafdc\uafdd\uafde\uafdf\uafe0\uafe1\uafe2\uafe3\uafe4\uafe5\uafe6\uafe7\uafe8\uafe9\uafea\uafeb\uafec\uafed\uafee\uafef\uaff0\uaff1\uaff2\uaff3\uaff4\uaff5\uaff6\uaff7\uaff8\uaff9\uaffa\uaffb\uaffc\uaffd\uaffe\uafff\ub000\ub001\ub002\ub003\ub004\ub005\ub006\ub007\ub008\ub009\ub00a\ub00b\ub00c\ub00d\ub00e\ub00f\ub010\ub011\ub012\ub013\ub014\ub015\ub016\ub017\ub018\ub019\ub01a\ub01b\ub01c\ub01d\ub01e\ub01f\ub020\ub021\ub022\ub023\ub024\ub025\ub026\ub027\ub028\ub029\ub02a\ub02b\ub02c\ub02d\ub02e\ub02f\ub030\ub031\ub032\ub033\ub034\ub035\ub036\ub037\ub038\ub039\ub03a\ub03b\ub03c\ub03d\ub03e\ub03f\ub040\ub041\ub042\ub043\ub044\ub045\ub046\ub047\ub048\ub049\ub04a\ub04b\ub04c\ub04d\ub04e\ub04f\ub050\ub051\ub052\ub053\ub054\ub055\ub056\ub057\ub058\ub059\ub05a\ub05b\ub05c\ub05d\ub05e\ub05f\ub060\ub061\ub062\ub063\ub064\ub065\ub066\ub067\ub068\ub069\ub06a\ub06b\ub06c\ub06d\ub06e\ub06f\ub070\ub071\ub072\ub073\ub074\ub075\ub076\ub077\ub078\ub079\ub07a\ub07b\ub07c\ub07d\ub07e\ub07f\ub080\ub081\ub082\ub083\ub084\ub085\ub086\ub087\ub088\ub089\ub08a\ub08b\ub08c\ub08d\ub08e\ub08f\ub090\ub091\ub092\ub093\ub094\ub095\ub096\ub097\ub098\ub099\ub09a\ub09b\ub09c\ub09d\ub09e\ub09f\ub0a0\ub0a1\ub0a2\ub0a3\ub0a4\ub0a5\ub0a6\ub0a7\ub0a8\ub0a9\ub0aa\ub0ab\ub0ac\ub0ad\ub0ae\ub0af\ub0b0\ub0b1\ub0b2\ub0b3\ub0b4\ub0b5\ub0b6\ub0b7\ub0b8\ub0b9\ub0ba\ub0bb\ub0bc\ub0bd\ub0be\ub0bf\ub0c0\ub0c1\ub0c2\ub0c3\ub0c4\ub0c5\ub0c6\ub0c7\ub0c8\ub0c9\ub0ca\ub0cb\ub0cc\ub0cd\ub0ce\ub0cf\ub0d0\ub0d1\ub0d2\ub0d3\ub0d4\ub0d5\ub0d6\ub0d7\ub0d8\ub0d9\ub0da\ub0db\ub0dc\ub0dd\ub0de\ub0df\ub0e0\ub0e1\ub0e2\ub0e3\ub0e4\ub0e5\ub0e6\ub0e7\ub0e8\ub0e9\ub0ea\ub0eb\ub0ec\ub0ed\ub0ee\ub0ef\ub0f0\ub0f1\ub0f2\ub0f3\ub0f4\ub0f5\ub0f6\ub0f7\ub0f8\ub0f9\ub0fa\ub0fb\ub0fc\ub0fd\ub0fe\ub0ff\ub100\ub101\ub102\ub103\ub104\ub105\ub106\ub107\ub108\ub109\ub10a\ub10b\ub10c\ub10d\ub10e\ub10f\ub110\ub111\ub112\ub113\ub114\ub115\ub116\ub117\ub118\ub119\ub11a\ub11b\ub11c\ub11d\ub11e\ub11f\ub120\ub121\ub122\ub123\ub124\ub125\ub126\ub127\ub128\ub129\ub12a\ub12b\ub12c\ub12d\ub12e\ub12f\ub130\ub131\ub132\ub133\ub134\ub135\ub136\ub137\ub138\ub139\ub13a\ub13b\ub13c\ub13d\ub13e\ub13f\ub140\ub141\ub142\ub143\ub144\ub145\ub146\ub147\ub148\ub149\ub14a\ub14b\ub14c\ub14d\ub14e\ub14f\ub150\ub151\ub152\ub153\ub154\ub155\ub156\ub157\ub158\ub159\ub15a\ub15b\ub15c\ub15d\ub15e\ub15f\ub160\ub161\ub162\ub163\ub164\ub165\ub166\ub167\ub168\ub169\ub16a\ub16b\ub16c\ub16d\ub16e\ub16f\ub170\ub171\ub172\ub173\ub174\ub175\ub176\ub177\ub178\ub179\ub17a\ub17b\ub17c\ub17d\ub17e\ub17f\ub180\ub181\ub182\ub183\ub184\ub185\ub186\ub187\ub188\ub189\ub18a\ub18b\ub18c\ub18d\ub18e\ub18f\ub190\ub191\ub192\ub193\ub194\ub195\ub196\ub197\ub198\ub199\ub19a\ub19b\ub19c\ub19d\ub19e\ub19f\ub1a0\ub1a1\ub1a2\ub1a3\ub1a4\ub1a5\ub1a6\ub1a7\ub1a8\ub1a9\ub1aa\ub1ab\ub1ac\ub1ad\ub1ae\ub1af\ub1b0\ub1b1\ub1b2\ub1b3\ub1b4\ub1b5\ub1b6\ub1b7\ub1b8\ub1b9\ub1ba\ub1bb\ub1bc\ub1bd\ub1be\ub1bf\ub1c0\ub1c1\ub1c2\ub1c3\ub1c4\ub1c5\ub1c6\ub1c7\ub1c8\ub1c9\ub1ca\ub1cb\ub1cc\ub1cd\ub1ce\ub1cf\ub1d0\ub1d1\ub1d2\ub1d3\ub1d4\ub1d5\ub1d6\ub1d7\ub1d8\ub1d9\ub1da\ub1db\ub1dc\ub1dd\ub1de\ub1df\ub1e0\ub1e1\ub1e2\ub1e3\ub1e4\ub1e5\ub1e6\ub1e7\ub1e8\ub1e9\ub1ea\ub1eb\ub1ec\ub1ed\ub1ee\ub1ef\ub1f0\ub1f1\ub1f2\ub1f3\ub1f4\ub1f5\ub1f6\ub1f7\ub1f8\ub1f9\ub1fa\ub1fb\ub1fc\ub1fd\ub1fe\ub1ff\ub200\ub201\ub202\ub203\ub204\ub205\ub206\ub207\ub208\ub209\ub20a\ub20b\ub20c\ub20d\ub20e\ub20f\ub210\ub211\ub212\ub213\ub214\ub215\ub216\ub217\ub218\ub219\ub21a\ub21b\ub21c\ub21d\ub21e\ub21f\ub220\ub221\ub222\ub223\ub224\ub225\ub226\ub227\ub228\ub229\ub22a\ub22b\ub22c\ub22d\ub22e\ub22f\ub230\ub231\ub232\ub233\ub234\ub235\ub236\ub237\ub238\ub239\ub23a\ub23b\ub23c\ub23d\ub23e\ub23f\ub240\ub241\ub242\ub243\ub244\ub245\ub246\ub247\ub248\ub249\ub24a\ub24b\ub24c\ub24d\ub24e\ub24f\ub250\ub251\ub252\ub253\ub254\ub255\ub256\ub257\ub258\ub259\ub25a\ub25b\ub25c\ub25d\ub25e\ub25f\ub260\ub261\ub262\ub263\ub264\ub265\ub266\ub267\ub268\ub269\ub26a\ub26b\ub26c\ub26d\ub26e\ub26f\ub270\ub271\ub272\ub273\ub274\ub275\ub276\ub277\ub278\ub279\ub27a\ub27b\ub27c\ub27d\ub27e\ub27f\ub280\ub281\ub282\ub283\ub284\ub285\ub286\ub287\ub288\ub289\ub28a\ub28b\ub28c\ub28d\ub28e\ub28f\ub290\ub291\ub292\ub293\ub294\ub295\ub296\ub297\ub298\ub299\ub29a\ub29b\ub29c\ub29d\ub29e\ub29f\ub2a0\ub2a1\ub2a2\ub2a3\ub2a4\ub2a5\ub2a6\ub2a7\ub2a8\ub2a9\ub2aa\ub2ab\ub2ac\ub2ad\ub2ae\ub2af\ub2b0\ub2b1\ub2b2\ub2b3\ub2b4\ub2b5\ub2b6\ub2b7\ub2b8\ub2b9\ub2ba\ub2bb\ub2bc\ub2bd\ub2be\ub2bf\ub2c0\ub2c1\ub2c2\ub2c3\ub2c4\ub2c5\ub2c6\ub2c7\ub2c8\ub2c9\ub2ca\ub2cb\ub2cc\ub2cd\ub2ce\ub2cf\ub2d0\ub2d1\ub2d2\ub2d3\ub2d4\ub2d5\ub2d6\ub2d7\ub2d8\ub2d9\ub2da\ub2db\ub2dc\ub2dd\ub2de\ub2df\ub2e0\ub2e1\ub2e2\ub2e3\ub2e4\ub2e5\ub2e6\ub2e7\ub2e8\ub2e9\ub2ea\ub2eb\ub2ec\ub2ed\ub2ee\ub2ef\ub2f0\ub2f1\ub2f2\ub2f3\ub2f4\ub2f5\ub2f6\ub2f7\ub2f8\ub2f9\ub2fa\ub2fb\ub2fc\ub2fd\ub2fe\ub2ff\ub300\ub301\ub302\ub303\ub304\ub305\ub306\ub307\ub308\ub309\ub30a\ub30b\ub30c\ub30d\ub30e\ub30f\ub310\ub311\ub312\ub313\ub314\ub315\ub316\ub317\ub318\ub319\ub31a\ub31b\ub31c\ub31d\ub31e\ub31f\ub320\ub321\ub322\ub323\ub324\ub325\ub326\ub327\ub328\ub329\ub32a\ub32b\ub32c\ub32d\ub32e\ub32f\ub330\ub331\ub332\ub333\ub334\ub335\ub336\ub337\ub338\ub339\ub33a\ub33b\ub33c\ub33d\ub33e\ub33f\ub340\ub341\ub342\ub343\ub344\ub345\ub346\ub347\ub348\ub349\ub34a\ub34b\ub34c\ub34d\ub34e\ub34f\ub350\ub351\ub352\ub353\ub354\ub355\ub356\ub357\ub358\ub359\ub35a\ub35b\ub35c\ub35d\ub35e\ub35f\ub360\ub361\ub362\ub363\ub364\ub365\ub366\ub367\ub368\ub369\ub36a\ub36b\ub36c\ub36d\ub36e\ub36f\ub370\ub371\ub372\ub373\ub374\ub375\ub376\ub377\ub378\ub379\ub37a\ub37b\ub37c\ub37d\ub37e\ub37f\ub380\ub381\ub382\ub383\ub384\ub385\ub386\ub387\ub388\ub389\ub38a\ub38b\ub38c\ub38d\ub38e\ub38f\ub390\ub391\ub392\ub393\ub394\ub395\ub396\ub397\ub398\ub399\ub39a\ub39b\ub39c\ub39d\ub39e\ub39f\ub3a0\ub3a1\ub3a2\ub3a3\ub3a4\ub3a5\ub3a6\ub3a7\ub3a8\ub3a9\ub3aa\ub3ab\ub3ac\ub3ad\ub3ae\ub3af\ub3b0\ub3b1\ub3b2\ub3b3\ub3b4\ub3b5\ub3b6\ub3b7\ub3b8\ub3b9\ub3ba\ub3bb\ub3bc\ub3bd\ub3be\ub3bf\ub3c0\ub3c1\ub3c2\ub3c3\ub3c4\ub3c5\ub3c6\ub3c7\ub3c8\ub3c9\ub3ca\ub3cb\ub3cc\ub3cd\ub3ce\ub3cf\ub3d0\ub3d1\ub3d2\ub3d3\ub3d4\ub3d5\ub3d6\ub3d7\ub3d8\ub3d9\ub3da\ub3db\ub3dc\ub3dd\ub3de\ub3df\ub3e0\ub3e1\ub3e2\ub3e3\ub3e4\ub3e5\ub3e6\ub3e7\ub3e8\ub3e9\ub3ea\ub3eb\ub3ec\ub3ed\ub3ee\ub3ef\ub3f0\ub3f1\ub3f2\ub3f3\ub3f4\ub3f5\ub3f6\ub3f7\ub3f8\ub3f9\ub3fa\ub3fb\ub3fc\ub3fd\ub3fe\ub3ff\ub400\ub401\ub402\ub403\ub404\ub405\ub406\ub407\ub408\ub409\ub40a\ub40b\ub40c\ub40d\ub40e\ub40f\ub410\ub411\ub412\ub413\ub414\ub415\ub416\ub417\ub418\ub419\ub41a\ub41b\ub41c\ub41d\ub41e\ub41f\ub420\ub421\ub422\ub423\ub424\ub425\ub426\ub427\ub428\ub429\ub42a\ub42b\ub42c\ub42d\ub42e\ub42f\ub430\ub431\ub432\ub433\ub434\ub435\ub436\ub437\ub438\ub439\ub43a\ub43b\ub43c\ub43d\ub43e\ub43f\ub440\ub441\ub442\ub443\ub444\ub445\ub446\ub447\ub448\ub449\ub44a\ub44b\ub44c\ub44d\ub44e\ub44f\ub450\ub451\ub452\ub453\ub454\ub455\ub456\ub457\ub458\ub459\ub45a\ub45b\ub45c\ub45d\ub45e\ub45f\ub460\ub461\ub462\ub463\ub464\ub465\ub466\ub467\ub468\ub469\ub46a\ub46b\ub46c\ub46d\ub46e\ub46f\ub470\ub471\ub472\ub473\ub474\ub475\ub476\ub477\ub478\ub479\ub47a\ub47b\ub47c\ub47d\ub47e\ub47f\ub480\ub481\ub482\ub483\ub484\ub485\ub486\ub487\ub488\ub489\ub48a\ub48b\ub48c\ub48d\ub48e\ub48f\ub490\ub491\ub492\ub493\ub494\ub495\ub496\ub497\ub498\ub499\ub49a\ub49b\ub49c\ub49d\ub49e\ub49f\ub4a0\ub4a1\ub4a2\ub4a3\ub4a4\ub4a5\ub4a6\ub4a7\ub4a8\ub4a9\ub4aa\ub4ab\ub4ac\ub4ad\ub4ae\ub4af\ub4b0\ub4b1\ub4b2\ub4b3\ub4b4\ub4b5\ub4b6\ub4b7\ub4b8\ub4b9\ub4ba\ub4bb\ub4bc\ub4bd\ub4be\ub4bf\ub4c0\ub4c1\ub4c2\ub4c3\ub4c4\ub4c5\ub4c6\ub4c7\ub4c8\ub4c9\ub4ca\ub4cb\ub4cc\ub4cd\ub4ce\ub4cf\ub4d0\ub4d1\ub4d2\ub4d3\ub4d4\ub4d5\ub4d6\ub4d7\ub4d8\ub4d9\ub4da\ub4db\ub4dc\ub4dd\ub4de\ub4df\ub4e0\ub4e1\ub4e2\ub4e3\ub4e4\ub4e5\ub4e6\ub4e7\ub4e8\ub4e9\ub4ea\ub4eb\ub4ec\ub4ed\ub4ee\ub4ef\ub4f0\ub4f1\ub4f2\ub4f3\ub4f4\ub4f5\ub4f6\ub4f7\ub4f8\ub4f9\ub4fa\ub4fb\ub4fc\ub4fd\ub4fe\ub4ff\ub500\ub501\ub502\ub503\ub504\ub505\ub506\ub507\ub508\ub509\ub50a\ub50b\ub50c\ub50d\ub50e\ub50f\ub510\ub511\ub512\ub513\ub514\ub515\ub516\ub517\ub518\ub519\ub51a\ub51b\ub51c\ub51d\ub51e\ub51f\ub520\ub521\ub522\ub523\ub524\ub525\ub526\ub527\ub528\ub529\ub52a\ub52b\ub52c\ub52d\ub52e\ub52f\ub530\ub531\ub532\ub533\ub534\ub535\ub536\ub537\ub538\ub539\ub53a\ub53b\ub53c\ub53d\ub53e\ub53f\ub540\ub541\ub542\ub543\ub544\ub545\ub546\ub547\ub548\ub549\ub54a\ub54b\ub54c\ub54d\ub54e\ub54f\ub550\ub551\ub552\ub553\ub554\ub555\ub556\ub557\ub558\ub559\ub55a\ub55b\ub55c\ub55d\ub55e\ub55f\ub560\ub561\ub562\ub563\ub564\ub565\ub566\ub567\ub568\ub569\ub56a\ub56b\ub56c\ub56d\ub56e\ub56f\ub570\ub571\ub572\ub573\ub574\ub575\ub576\ub577\ub578\ub579\ub57a\ub57b\ub57c\ub57d\ub57e\ub57f\ub580\ub581\ub582\ub583\ub584\ub585\ub586\ub587\ub588\ub589\ub58a\ub58b\ub58c\ub58d\ub58e\ub58f\ub590\ub591\ub592\ub593\ub594\ub595\ub596\ub597\ub598\ub599\ub59a\ub59b\ub59c\ub59d\ub59e\ub59f\ub5a0\ub5a1\ub5a2\ub5a3\ub5a4\ub5a5\ub5a6\ub5a7\ub5a8\ub5a9\ub5aa\ub5ab\ub5ac\ub5ad\ub5ae\ub5af\ub5b0\ub5b1\ub5b2\ub5b3\ub5b4\ub5b5\ub5b6\ub5b7\ub5b8\ub5b9\ub5ba\ub5bb\ub5bc\ub5bd\ub5be\ub5bf\ub5c0\ub5c1\ub5c2\ub5c3\ub5c4\ub5c5\ub5c6\ub5c7\ub5c8\ub5c9\ub5ca\ub5cb\ub5cc\ub5cd\ub5ce\ub5cf\ub5d0\ub5d1\ub5d2\ub5d3\ub5d4\ub5d5\ub5d6\ub5d7\ub5d8\ub5d9\ub5da\ub5db\ub5dc\ub5dd\ub5de\ub5df\ub5e0\ub5e1\ub5e2\ub5e3\ub5e4\ub5e5\ub5e6\ub5e7\ub5e8\ub5e9\ub5ea\ub5eb\ub5ec\ub5ed\ub5ee\ub5ef\ub5f0\ub5f1\ub5f2\ub5f3\ub5f4\ub5f5\ub5f6\ub5f7\ub5f8\ub5f9\ub5fa\ub5fb\ub5fc\ub5fd\ub5fe\ub5ff\ub600\ub601\ub602\ub603\ub604\ub605\ub606\ub607\ub608\ub609\ub60a\ub60b\ub60c\ub60d\ub60e\ub60f\ub610\ub611\ub612\ub613\ub614\ub615\ub616\ub617\ub618\ub619\ub61a\ub61b\ub61c\ub61d\ub61e\ub61f\ub620\ub621\ub622\ub623\ub624\ub625\ub626\ub627\ub628\ub629\ub62a\ub62b\ub62c\ub62d\ub62e\ub62f\ub630\ub631\ub632\ub633\ub634\ub635\ub636\ub637\ub638\ub639\ub63a\ub63b\ub63c\ub63d\ub63e\ub63f\ub640\ub641\ub642\ub643\ub644\ub645\ub646\ub647\ub648\ub649\ub64a\ub64b\ub64c\ub64d\ub64e\ub64f\ub650\ub651\ub652\ub653\ub654\ub655\ub656\ub657\ub658\ub659\ub65a\ub65b\ub65c\ub65d\ub65e\ub65f\ub660\ub661\ub662\ub663\ub664\ub665\ub666\ub667\ub668\ub669\ub66a\ub66b\ub66c\ub66d\ub66e\ub66f\ub670\ub671\ub672\ub673\ub674\ub675\ub676\ub677\ub678\ub679\ub67a\ub67b\ub67c\ub67d\ub67e\ub67f\ub680\ub681\ub682\ub683\ub684\ub685\ub686\ub687\ub688\ub689\ub68a\ub68b\ub68c\ub68d\ub68e\ub68f\ub690\ub691\ub692\ub693\ub694\ub695\ub696\ub697\ub698\ub699\ub69a\ub69b\ub69c\ub69d\ub69e\ub69f\ub6a0\ub6a1\ub6a2\ub6a3\ub6a4\ub6a5\ub6a6\ub6a7\ub6a8\ub6a9\ub6aa\ub6ab\ub6ac\ub6ad\ub6ae\ub6af\ub6b0\ub6b1\ub6b2\ub6b3\ub6b4\ub6b5\ub6b6\ub6b7\ub6b8\ub6b9\ub6ba\ub6bb\ub6bc\ub6bd\ub6be\ub6bf\ub6c0\ub6c1\ub6c2\ub6c3\ub6c4\ub6c5\ub6c6\ub6c7\ub6c8\ub6c9\ub6ca\ub6cb\ub6cc\ub6cd\ub6ce\ub6cf\ub6d0\ub6d1\ub6d2\ub6d3\ub6d4\ub6d5\ub6d6\ub6d7\ub6d8\ub6d9\ub6da\ub6db\ub6dc\ub6dd\ub6de\ub6df\ub6e0\ub6e1\ub6e2\ub6e3\ub6e4\ub6e5\ub6e6\ub6e7\ub6e8\ub6e9\ub6ea\ub6eb\ub6ec\ub6ed\ub6ee\ub6ef\ub6f0\ub6f1\ub6f2\ub6f3\ub6f4\ub6f5\ub6f6\ub6f7\ub6f8\ub6f9\ub6fa\ub6fb\ub6fc\ub6fd\ub6fe\ub6ff\ub700\ub701\ub702\ub703\ub704\ub705\ub706\ub707\ub708\ub709\ub70a\ub70b\ub70c\ub70d\ub70e\ub70f\ub710\ub711\ub712\ub713\ub714\ub715\ub716\ub717\ub718\ub719\ub71a\ub71b\ub71c\ub71d\ub71e\ub71f\ub720\ub721\ub722\ub723\ub724\ub725\ub726\ub727\ub728\ub729\ub72a\ub72b\ub72c\ub72d\ub72e\ub72f\ub730\ub731\ub732\ub733\ub734\ub735\ub736\ub737\ub738\ub739\ub73a\ub73b\ub73c\ub73d\ub73e\ub73f\ub740\ub741\ub742\ub743\ub744\ub745\ub746\ub747\ub748\ub749\ub74a\ub74b\ub74c\ub74d\ub74e\ub74f\ub750\ub751\ub752\ub753\ub754\ub755\ub756\ub757\ub758\ub759\ub75a\ub75b\ub75c\ub75d\ub75e\ub75f\ub760\ub761\ub762\ub763\ub764\ub765\ub766\ub767\ub768\ub769\ub76a\ub76b\ub76c\ub76d\ub76e\ub76f\ub770\ub771\ub772\ub773\ub774\ub775\ub776\ub777\ub778\ub779\ub77a\ub77b\ub77c\ub77d\ub77e\ub77f\ub780\ub781\ub782\ub783\ub784\ub785\ub786\ub787\ub788\ub789\ub78a\ub78b\ub78c\ub78d\ub78e\ub78f\ub790\ub791\ub792\ub793\ub794\ub795\ub796\ub797\ub798\ub799\ub79a\ub79b\ub79c\ub79d\ub79e\ub79f\ub7a0\ub7a1\ub7a2\ub7a3\ub7a4\ub7a5\ub7a6\ub7a7\ub7a8\ub7a9\ub7aa\ub7ab\ub7ac\ub7ad\ub7ae\ub7af\ub7b0\ub7b1\ub7b2\ub7b3\ub7b4\ub7b5\ub7b6\ub7b7\ub7b8\ub7b9\ub7ba\ub7bb\ub7bc\ub7bd\ub7be\ub7bf\ub7c0\ub7c1\ub7c2\ub7c3\ub7c4\ub7c5\ub7c6\ub7c7\ub7c8\ub7c9\ub7ca\ub7cb\ub7cc\ub7cd\ub7ce\ub7cf\ub7d0\ub7d1\ub7d2\ub7d3\ub7d4\ub7d5\ub7d6\ub7d7\ub7d8\ub7d9\ub7da\ub7db\ub7dc\ub7dd\ub7de\ub7df\ub7e0\ub7e1\ub7e2\ub7e3\ub7e4\ub7e5\ub7e6\ub7e7\ub7e8\ub7e9\ub7ea\ub7eb\ub7ec\ub7ed\ub7ee\ub7ef\ub7f0\ub7f1\ub7f2\ub7f3\ub7f4\ub7f5\ub7f6\ub7f7\ub7f8\ub7f9\ub7fa\ub7fb\ub7fc\ub7fd\ub7fe\ub7ff\ub800\ub801\ub802\ub803\ub804\ub805\ub806\ub807\ub808\ub809\ub80a\ub80b\ub80c\ub80d\ub80e\ub80f\ub810\ub811\ub812\ub813\ub814\ub815\ub816\ub817\ub818\ub819\ub81a\ub81b\ub81c\ub81d\ub81e\ub81f\ub820\ub821\ub822\ub823\ub824\ub825\ub826\ub827\ub828\ub829\ub82a\ub82b\ub82c\ub82d\ub82e\ub82f\ub830\ub831\ub832\ub833\ub834\ub835\ub836\ub837\ub838\ub839\ub83a\ub83b\ub83c\ub83d\ub83e\ub83f\ub840\ub841\ub842\ub843\ub844\ub845\ub846\ub847\ub848\ub849\ub84a\ub84b\ub84c\ub84d\ub84e\ub84f\ub850\ub851\ub852\ub853\ub854\ub855\ub856\ub857\ub858\ub859\ub85a\ub85b\ub85c\ub85d\ub85e\ub85f\ub860\ub861\ub862\ub863\ub864\ub865\ub866\ub867\ub868\ub869\ub86a\ub86b\ub86c\ub86d\ub86e\ub86f\ub870\ub871\ub872\ub873\ub874\ub875\ub876\ub877\ub878\ub879\ub87a\ub87b\ub87c\ub87d\ub87e\ub87f\ub880\ub881\ub882\ub883\ub884\ub885\ub886\ub887\ub888\ub889\ub88a\ub88b\ub88c\ub88d\ub88e\ub88f\ub890\ub891\ub892\ub893\ub894\ub895\ub896\ub897\ub898\ub899\ub89a\ub89b\ub89c\ub89d\ub89e\ub89f\ub8a0\ub8a1\ub8a2\ub8a3\ub8a4\ub8a5\ub8a6\ub8a7\ub8a8\ub8a9\ub8aa\ub8ab\ub8ac\ub8ad\ub8ae\ub8af\ub8b0\ub8b1\ub8b2\ub8b3\ub8b4\ub8b5\ub8b6\ub8b7\ub8b8\ub8b9\ub8ba\ub8bb\ub8bc\ub8bd\ub8be\ub8bf\ub8c0\ub8c1\ub8c2\ub8c3\ub8c4\ub8c5\ub8c6\ub8c7\ub8c8\ub8c9\ub8ca\ub8cb\ub8cc\ub8cd\ub8ce\ub8cf\ub8d0\ub8d1\ub8d2\ub8d3\ub8d4\ub8d5\ub8d6\ub8d7\ub8d8\ub8d9\ub8da\ub8db\ub8dc\ub8dd\ub8de\ub8df\ub8e0\ub8e1\ub8e2\ub8e3\ub8e4\ub8e5\ub8e6\ub8e7\ub8e8\ub8e9\ub8ea\ub8eb\ub8ec\ub8ed\ub8ee\ub8ef\ub8f0\ub8f1\ub8f2\ub8f3\ub8f4\ub8f5\ub8f6\ub8f7\ub8f8\ub8f9\ub8fa\ub8fb\ub8fc\ub8fd\ub8fe\ub8ff\ub900\ub901\ub902\ub903\ub904\ub905\ub906\ub907\ub908\ub909\ub90a\ub90b\ub90c\ub90d\ub90e\ub90f\ub910\ub911\ub912\ub913\ub914\ub915\ub916\ub917\ub918\ub919\ub91a\ub91b\ub91c\ub91d\ub91e\ub91f\ub920\ub921\ub922\ub923\ub924\ub925\ub926\ub927\ub928\ub929\ub92a\ub92b\ub92c\ub92d\ub92e\ub92f\ub930\ub931\ub932\ub933\ub934\ub935\ub936\ub937\ub938\ub939\ub93a\ub93b\ub93c\ub93d\ub93e\ub93f\ub940\ub941\ub942\ub943\ub944\ub945\ub946\ub947\ub948\ub949\ub94a\ub94b\ub94c\ub94d\ub94e\ub94f\ub950\ub951\ub952\ub953\ub954\ub955\ub956\ub957\ub958\ub959\ub95a\ub95b\ub95c\ub95d\ub95e\ub95f\ub960\ub961\ub962\ub963\ub964\ub965\ub966\ub967\ub968\ub969\ub96a\ub96b\ub96c\ub96d\ub96e\ub96f\ub970\ub971\ub972\ub973\ub974\ub975\ub976\ub977\ub978\ub979\ub97a\ub97b\ub97c\ub97d\ub97e\ub97f\ub980\ub981\ub982\ub983\ub984\ub985\ub986\ub987\ub988\ub989\ub98a\ub98b\ub98c\ub98d\ub98e\ub98f\ub990\ub991\ub992\ub993\ub994\ub995\ub996\ub997\ub998\ub999\ub99a\ub99b\ub99c\ub99d\ub99e\ub99f\ub9a0\ub9a1\ub9a2\ub9a3\ub9a4\ub9a5\ub9a6\ub9a7\ub9a8\ub9a9\ub9aa\ub9ab\ub9ac\ub9ad\ub9ae\ub9af\ub9b0\ub9b1\ub9b2\ub9b3\ub9b4\ub9b5\ub9b6\ub9b7\ub9b8\ub9b9\ub9ba\ub9bb\ub9bc\ub9bd\ub9be\ub9bf\ub9c0\ub9c1\ub9c2\ub9c3\ub9c4\ub9c5\ub9c6\ub9c7\ub9c8\ub9c9\ub9ca\ub9cb\ub9cc\ub9cd\ub9ce\ub9cf\ub9d0\ub9d1\ub9d2\ub9d3\ub9d4\ub9d5\ub9d6\ub9d7\ub9d8\ub9d9\ub9da\ub9db\ub9dc\ub9dd\ub9de\ub9df\ub9e0\ub9e1\ub9e2\ub9e3\ub9e4\ub9e5\ub9e6\ub9e7\ub9e8\ub9e9\ub9ea\ub9eb\ub9ec\ub9ed\ub9ee\ub9ef\ub9f0\ub9f1\ub9f2\ub9f3\ub9f4\ub9f5\ub9f6\ub9f7\ub9f8\ub9f9\ub9fa\ub9fb\ub9fc\ub9fd\ub9fe\ub9ff\uba00\uba01\uba02\uba03\uba04\uba05\uba06\uba07\uba08\uba09\uba0a\uba0b\uba0c\uba0d\uba0e\uba0f\uba10\uba11\uba12\uba13\uba14\uba15\uba16\uba17\uba18\uba19\uba1a\uba1b\uba1c\uba1d\uba1e\uba1f\uba20\uba21\uba22\uba23\uba24\uba25\uba26\uba27\uba28\uba29\uba2a\uba2b\uba2c\uba2d\uba2e\uba2f\uba30\uba31\uba32\uba33\uba34\uba35\uba36\uba37\uba38\uba39\uba3a\uba3b\uba3c\uba3d\uba3e\uba3f\uba40\uba41\uba42\uba43\uba44\uba45\uba46\uba47\uba48\uba49\uba4a\uba4b\uba4c\uba4d\uba4e\uba4f\uba50\uba51\uba52\uba53\uba54\uba55\uba56\uba57\uba58\uba59\uba5a\uba5b\uba5c\uba5d\uba5e\uba5f\uba60\uba61\uba62\uba63\uba64\uba65\uba66\uba67\uba68\uba69\uba6a\uba6b\uba6c\uba6d\uba6e\uba6f\uba70\uba71\uba72\uba73\uba74\uba75\uba76\uba77\uba78\uba79\uba7a\uba7b\uba7c\uba7d\uba7e\uba7f\uba80\uba81\uba82\uba83\uba84\uba85\uba86\uba87\uba88\uba89\uba8a\uba8b\uba8c\uba8d\uba8e\uba8f\uba90\uba91\uba92\uba93\uba94\uba95\uba96\uba97\uba98\uba99\uba9a\uba9b\uba9c\uba9d\uba9e\uba9f\ubaa0\ubaa1\ubaa2\ubaa3\ubaa4\ubaa5\ubaa6\ubaa7\ubaa8\ubaa9\ubaaa\ubaab\ubaac\ubaad\ubaae\ubaaf\ubab0\ubab1\ubab2\ubab3\ubab4\ubab5\ubab6\ubab7\ubab8\ubab9\ubaba\ubabb\ubabc\ubabd\ubabe\ubabf\ubac0\ubac1\ubac2\ubac3\ubac4\ubac5\ubac6\ubac7\ubac8\ubac9\ubaca\ubacb\ubacc\ubacd\ubace\ubacf\ubad0\ubad1\ubad2\ubad3\ubad4\ubad5\ubad6\ubad7\ubad8\ubad9\ubada\ubadb\ubadc\ubadd\ubade\ubadf\ubae0\ubae1\ubae2\ubae3\ubae4\ubae5\ubae6\ubae7\ubae8\ubae9\ubaea\ubaeb\ubaec\ubaed\ubaee\ubaef\ubaf0\ubaf1\ubaf2\ubaf3\ubaf4\ubaf5\ubaf6\ubaf7\ubaf8\ubaf9\ubafa\ubafb\ubafc\ubafd\ubafe\ubaff\ubb00\ubb01\ubb02\ubb03\ubb04\ubb05\ubb06\ubb07\ubb08\ubb09\ubb0a\ubb0b\ubb0c\ubb0d\ubb0e\ubb0f\ubb10\ubb11\ubb12\ubb13\ubb14\ubb15\ubb16\ubb17\ubb18\ubb19\ubb1a\ubb1b\ubb1c\ubb1d\ubb1e\ubb1f\ubb20\ubb21\ubb22\ubb23\ubb24\ubb25\ubb26\ubb27\ubb28\ubb29\ubb2a\ubb2b\ubb2c\ubb2d\ubb2e\ubb2f\ubb30\ubb31\ubb32\ubb33\ubb34\ubb35\ubb36\ubb37\ubb38\ubb39\ubb3a\ubb3b\ubb3c\ubb3d\ubb3e\ubb3f\ubb40\ubb41\ubb42\ubb43\ubb44\ubb45\ubb46\ubb47\ubb48\ubb49\ubb4a\ubb4b\ubb4c\ubb4d\ubb4e\ubb4f\ubb50\ubb51\ubb52\ubb53\ubb54\ubb55\ubb56\ubb57\ubb58\ubb59\ubb5a\ubb5b\ubb5c\ubb5d\ubb5e\ubb5f\ubb60\ubb61\ubb62\ubb63\ubb64\ubb65\ubb66\ubb67\ubb68\ubb69\ubb6a\ubb6b\ubb6c\ubb6d\ubb6e\ubb6f\ubb70\ubb71\ubb72\ubb73\ubb74\ubb75\ubb76\ubb77\ubb78\ubb79\ubb7a\ubb7b\ubb7c\ubb7d\ubb7e\ubb7f\ubb80\ubb81\ubb82\ubb83\ubb84\ubb85\ubb86\ubb87\ubb88\ubb89\ubb8a\ubb8b\ubb8c\ubb8d\ubb8e\ubb8f\ubb90\ubb91\ubb92\ubb93\ubb94\ubb95\ubb96\ubb97\ubb98\ubb99\ubb9a\ubb9b\ubb9c\ubb9d\ubb9e\ubb9f\ubba0\ubba1\ubba2\ubba3\ubba4\ubba5\ubba6\ubba7\ubba8\ubba9\ubbaa\ubbab\ubbac\ubbad\ubbae\ubbaf\ubbb0\ubbb1\ubbb2\ubbb3\ubbb4\ubbb5\ubbb6\ubbb7\ubbb8\ubbb9\ubbba\ubbbb\ubbbc\ubbbd\ubbbe\ubbbf\ubbc0\ubbc1\ubbc2\ubbc3\ubbc4\ubbc5\ubbc6\ubbc7\ubbc8\ubbc9\ubbca\ubbcb\ubbcc\ubbcd\ubbce\ubbcf\ubbd0\ubbd1\ubbd2\ubbd3\ubbd4\ubbd5\ubbd6\ubbd7\ubbd8\ubbd9\ubbda\ubbdb\ubbdc\ubbdd\ubbde\ubbdf\ubbe0\ubbe1\ubbe2\ubbe3\ubbe4\ubbe5\ubbe6\ubbe7\ubbe8\ubbe9\ubbea\ubbeb\ubbec\ubbed\ubbee\ubbef\ubbf0\ubbf1\ubbf2\ubbf3\ubbf4\ubbf5\ubbf6\ubbf7\ubbf8\ubbf9\ubbfa\ubbfb\ubbfc\ubbfd\ubbfe\ubbff\ubc00\ubc01\ubc02\ubc03\ubc04\ubc05\ubc06\ubc07\ubc08\ubc09\ubc0a\ubc0b\ubc0c\ubc0d\ubc0e\ubc0f\ubc10\ubc11\ubc12\ubc13\ubc14\ubc15\ubc16\ubc17\ubc18\ubc19\ubc1a\ubc1b\ubc1c\ubc1d\ubc1e\ubc1f\ubc20\ubc21\ubc22\ubc23\ubc24\ubc25\ubc26\ubc27\ubc28\ubc29\ubc2a\ubc2b\ubc2c\ubc2d\ubc2e\ubc2f\ubc30\ubc31\ubc32\ubc33\ubc34\ubc35\ubc36\ubc37\ubc38\ubc39\ubc3a\ubc3b\ubc3c\ubc3d\ubc3e\ubc3f\ubc40\ubc41\ubc42\ubc43\ubc44\ubc45\ubc46\ubc47\ubc48\ubc49\ubc4a\ubc4b\ubc4c\ubc4d\ubc4e\ubc4f\ubc50\ubc51\ubc52\ubc53\ubc54\ubc55\ubc56\ubc57\ubc58\ubc59\ubc5a\ubc5b\ubc5c\ubc5d\ubc5e\ubc5f\ubc60\ubc61\ubc62\ubc63\ubc64\ubc65\ubc66\ubc67\ubc68\ubc69\ubc6a\ubc6b\ubc6c\ubc6d\ubc6e\ubc6f\ubc70\ubc71\ubc72\ubc73\ubc74\ubc75\ubc76\ubc77\ubc78\ubc79\ubc7a\ubc7b\ubc7c\ubc7d\ubc7e\ubc7f\ubc80\ubc81\ubc82\ubc83\ubc84\ubc85\ubc86\ubc87\ubc88\ubc89\ubc8a\ubc8b\ubc8c\ubc8d\ubc8e\ubc8f\ubc90\ubc91\ubc92\ubc93\ubc94\ubc95\ubc96\ubc97\ubc98\ubc99\ubc9a\ubc9b\ubc9c\ubc9d\ubc9e\ubc9f\ubca0\ubca1\ubca2\ubca3\ubca4\ubca5\ubca6\ubca7\ubca8\ubca9\ubcaa\ubcab\ubcac\ubcad\ubcae\ubcaf\ubcb0\ubcb1\ubcb2\ubcb3\ubcb4\ubcb5\ubcb6\ubcb7\ubcb8\ubcb9\ubcba\ubcbb\ubcbc\ubcbd\ubcbe\ubcbf\ubcc0\ubcc1\ubcc2\ubcc3\ubcc4\ubcc5\ubcc6\ubcc7\ubcc8\ubcc9\ubcca\ubccb\ubccc\ubccd\ubcce\ubccf\ubcd0\ubcd1\ubcd2\ubcd3\ubcd4\ubcd5\ubcd6\ubcd7\ubcd8\ubcd9\ubcda\ubcdb\ubcdc\ubcdd\ubcde\ubcdf\ubce0\ubce1\ubce2\ubce3\ubce4\ubce5\ubce6\ubce7\ubce8\ubce9\ubcea\ubceb\ubcec\ubced\ubcee\ubcef\ubcf0\ubcf1\ubcf2\ubcf3\ubcf4\ubcf5\ubcf6\ubcf7\ubcf8\ubcf9\ubcfa\ubcfb\ubcfc\ubcfd\ubcfe\ubcff\ubd00\ubd01\ubd02\ubd03\ubd04\ubd05\ubd06\ubd07\ubd08\ubd09\ubd0a\ubd0b\ubd0c\ubd0d\ubd0e\ubd0f\ubd10\ubd11\ubd12\ubd13\ubd14\ubd15\ubd16\ubd17\ubd18\ubd19\ubd1a\ubd1b\ubd1c\ubd1d\ubd1e\ubd1f\ubd20\ubd21\ubd22\ubd23\ubd24\ubd25\ubd26\ubd27\ubd28\ubd29\ubd2a\ubd2b\ubd2c\ubd2d\ubd2e\ubd2f\ubd30\ubd31\ubd32\ubd33\ubd34\ubd35\ubd36\ubd37\ubd38\ubd39\ubd3a\ubd3b\ubd3c\ubd3d\ubd3e\ubd3f\ubd40\ubd41\ubd42\ubd43\ubd44\ubd45\ubd46\ubd47\ubd48\ubd49\ubd4a\ubd4b\ubd4c\ubd4d\ubd4e\ubd4f\ubd50\ubd51\ubd52\ubd53\ubd54\ubd55\ubd56\ubd57\ubd58\ubd59\ubd5a\ubd5b\ubd5c\ubd5d\ubd5e\ubd5f\ubd60\ubd61\ubd62\ubd63\ubd64\ubd65\ubd66\ubd67\ubd68\ubd69\ubd6a\ubd6b\ubd6c\ubd6d\ubd6e\ubd6f\ubd70\ubd71\ubd72\ubd73\ubd74\ubd75\ubd76\ubd77\ubd78\ubd79\ubd7a\ubd7b\ubd7c\ubd7d\ubd7e\ubd7f\ubd80\ubd81\ubd82\ubd83\ubd84\ubd85\ubd86\ubd87\ubd88\ubd89\ubd8a\ubd8b\ubd8c\ubd8d\ubd8e\ubd8f\ubd90\ubd91\ubd92\ubd93\ubd94\ubd95\ubd96\ubd97\ubd98\ubd99\ubd9a\ubd9b\ubd9c\ubd9d\ubd9e\ubd9f\ubda0\ubda1\ubda2\ubda3\ubda4\ubda5\ubda6\ubda7\ubda8\ubda9\ubdaa\ubdab\ubdac\ubdad\ubdae\ubdaf\ubdb0\ubdb1\ubdb2\ubdb3\ubdb4\ubdb5\ubdb6\ubdb7\ubdb8\ubdb9\ubdba\ubdbb\ubdbc\ubdbd\ubdbe\ubdbf\ubdc0\ubdc1\ubdc2\ubdc3\ubdc4\ubdc5\ubdc6\ubdc7\ubdc8\ubdc9\ubdca\ubdcb\ubdcc\ubdcd\ubdce\ubdcf\ubdd0\ubdd1\ubdd2\ubdd3\ubdd4\ubdd5\ubdd6\ubdd7\ubdd8\ubdd9\ubdda\ubddb\ubddc\ubddd\ubdde\ubddf\ubde0\ubde1\ubde2\ubde3\ubde4\ubde5\ubde6\ubde7\ubde8\ubde9\ubdea\ubdeb\ubdec\ubded\ubdee\ubdef\ubdf0\ubdf1\ubdf2\ubdf3\ubdf4\ubdf5\ubdf6\ubdf7\ubdf8\ubdf9\ubdfa\ubdfb\ubdfc\ubdfd\ubdfe\ubdff\ube00\ube01\ube02\ube03\ube04\ube05\ube06\ube07\ube08\ube09\ube0a\ube0b\ube0c\ube0d\ube0e\ube0f\ube10\ube11\ube12\ube13\ube14\ube15\ube16\ube17\ube18\ube19\ube1a\ube1b\ube1c\ube1d\ube1e\ube1f\ube20\ube21\ube22\ube23\ube24\ube25\ube26\ube27\ube28\ube29\ube2a\ube2b\ube2c\ube2d\ube2e\ube2f\ube30\ube31\ube32\ube33\ube34\ube35\ube36\ube37\ube38\ube39\ube3a\ube3b\ube3c\ube3d\ube3e\ube3f\ube40\ube41\ube42\ube43\ube44\ube45\ube46\ube47\ube48\ube49\ube4a\ube4b\ube4c\ube4d\ube4e\ube4f\ube50\ube51\ube52\ube53\ube54\ube55\ube56\ube57\ube58\ube59\ube5a\ube5b\ube5c\ube5d\ube5e\ube5f\ube60\ube61\ube62\ube63\ube64\ube65\ube66\ube67\ube68\ube69\ube6a\ube6b\ube6c\ube6d\ube6e\ube6f\ube70\ube71\ube72\ube73\ube74\ube75\ube76\ube77\ube78\ube79\ube7a\ube7b\ube7c\ube7d\ube7e\ube7f\ube80\ube81\ube82\ube83\ube84\ube85\ube86\ube87\ube88\ube89\ube8a\ube8b\ube8c\ube8d\ube8e\ube8f\ube90\ube91\ube92\ube93\ube94\ube95\ube96\ube97\ube98\ube99\ube9a\ube9b\ube9c\ube9d\ube9e\ube9f\ubea0\ubea1\ubea2\ubea3\ubea4\ubea5\ubea6\ubea7\ubea8\ubea9\ubeaa\ubeab\ubeac\ubead\ubeae\ubeaf\ubeb0\ubeb1\ubeb2\ubeb3\ubeb4\ubeb5\ubeb6\ubeb7\ubeb8\ubeb9\ubeba\ubebb\ubebc\ubebd\ubebe\ubebf\ubec0\ubec1\ubec2\ubec3\ubec4\ubec5\ubec6\ubec7\ubec8\ubec9\ubeca\ubecb\ubecc\ubecd\ubece\ubecf\ubed0\ubed1\ubed2\ubed3\ubed4\ubed5\ubed6\ubed7\ubed8\ubed9\ubeda\ubedb\ubedc\ubedd\ubede\ubedf\ubee0\ubee1\ubee2\ubee3\ubee4\ubee5\ubee6\ubee7\ubee8\ubee9\ubeea\ubeeb\ubeec\ubeed\ubeee\ubeef\ubef0\ubef1\ubef2\ubef3\ubef4\ubef5\ubef6\ubef7\ubef8\ubef9\ubefa\ubefb\ubefc\ubefd\ubefe\ubeff\ubf00\ubf01\ubf02\ubf03\ubf04\ubf05\ubf06\ubf07\ubf08\ubf09\ubf0a\ubf0b\ubf0c\ubf0d\ubf0e\ubf0f\ubf10\ubf11\ubf12\ubf13\ubf14\ubf15\ubf16\ubf17\ubf18\ubf19\ubf1a\ubf1b\ubf1c\ubf1d\ubf1e\ubf1f\ubf20\ubf21\ubf22\ubf23\ubf24\ubf25\ubf26\ubf27\ubf28\ubf29\ubf2a\ubf2b\ubf2c\ubf2d\ubf2e\ubf2f\ubf30\ubf31\ubf32\ubf33\ubf34\ubf35\ubf36\ubf37\ubf38\ubf39\ubf3a\ubf3b\ubf3c\ubf3d\ubf3e\ubf3f\ubf40\ubf41\ubf42\ubf43\ubf44\ubf45\ubf46\ubf47\ubf48\ubf49\ubf4a\ubf4b\ubf4c\ubf4d\ubf4e\ubf4f\ubf50\ubf51\ubf52\ubf53\ubf54\ubf55\ubf56\ubf57\ubf58\ubf59\ubf5a\ubf5b\ubf5c\ubf5d\ubf5e\ubf5f\ubf60\ubf61\ubf62\ubf63\ubf64\ubf65\ubf66\ubf67\ubf68\ubf69\ubf6a\ubf6b\ubf6c\ubf6d\ubf6e\ubf6f\ubf70\ubf71\ubf72\ubf73\ubf74\ubf75\ubf76\ubf77\ubf78\ubf79\ubf7a\ubf7b\ubf7c\ubf7d\ubf7e\ubf7f\ubf80\ubf81\ubf82\ubf83\ubf84\ubf85\ubf86\ubf87\ubf88\ubf89\ubf8a\ubf8b\ubf8c\ubf8d\ubf8e\ubf8f\ubf90\ubf91\ubf92\ubf93\ubf94\ubf95\ubf96\ubf97\ubf98\ubf99\ubf9a\ubf9b\ubf9c\ubf9d\ubf9e\ubf9f\ubfa0\ubfa1\ubfa2\ubfa3\ubfa4\ubfa5\ubfa6\ubfa7\ubfa8\ubfa9\ubfaa\ubfab\ubfac\ubfad\ubfae\ubfaf\ubfb0\ubfb1\ubfb2\ubfb3\ubfb4\ubfb5\ubfb6\ubfb7\ubfb8\ubfb9\ubfba\ubfbb\ubfbc\ubfbd\ubfbe\ubfbf\ubfc0\ubfc1\ubfc2\ubfc3\ubfc4\ubfc5\ubfc6\ubfc7\ubfc8\ubfc9\ubfca\ubfcb\ubfcc\ubfcd\ubfce\ubfcf\ubfd0\ubfd1\ubfd2\ubfd3\ubfd4\ubfd5\ubfd6\ubfd7\ubfd8\ubfd9\ubfda\ubfdb\ubfdc\ubfdd\ubfde\ubfdf\ubfe0\ubfe1\ubfe2\ubfe3\ubfe4\ubfe5\ubfe6\ubfe7\ubfe8\ubfe9\ubfea\ubfeb\ubfec\ubfed\ubfee\ubfef\ubff0\ubff1\ubff2\ubff3\ubff4\ubff5\ubff6\ubff7\ubff8\ubff9\ubffa\ubffb\ubffc\ubffd\ubffe\ubfff\uc000\uc001\uc002\uc003\uc004\uc005\uc006\uc007\uc008\uc009\uc00a\uc00b\uc00c\uc00d\uc00e\uc00f\uc010\uc011\uc012\uc013\uc014\uc015\uc016\uc017\uc018\uc019\uc01a\uc01b\uc01c\uc01d\uc01e\uc01f\uc020\uc021\uc022\uc023\uc024\uc025\uc026\uc027\uc028\uc029\uc02a\uc02b\uc02c\uc02d\uc02e\uc02f\uc030\uc031\uc032\uc033\uc034\uc035\uc036\uc037\uc038\uc039\uc03a\uc03b\uc03c\uc03d\uc03e\uc03f\uc040\uc041\uc042\uc043\uc044\uc045\uc046\uc047\uc048\uc049\uc04a\uc04b\uc04c\uc04d\uc04e\uc04f\uc050\uc051\uc052\uc053\uc054\uc055\uc056\uc057\uc058\uc059\uc05a\uc05b\uc05c\uc05d\uc05e\uc05f\uc060\uc061\uc062\uc063\uc064\uc065\uc066\uc067\uc068\uc069\uc06a\uc06b\uc06c\uc06d\uc06e\uc06f\uc070\uc071\uc072\uc073\uc074\uc075\uc076\uc077\uc078\uc079\uc07a\uc07b\uc07c\uc07d\uc07e\uc07f\uc080\uc081\uc082\uc083\uc084\uc085\uc086\uc087\uc088\uc089\uc08a\uc08b\uc08c\uc08d\uc08e\uc08f\uc090\uc091\uc092\uc093\uc094\uc095\uc096\uc097\uc098\uc099\uc09a\uc09b\uc09c\uc09d\uc09e\uc09f\uc0a0\uc0a1\uc0a2\uc0a3\uc0a4\uc0a5\uc0a6\uc0a7\uc0a8\uc0a9\uc0aa\uc0ab\uc0ac\uc0ad\uc0ae\uc0af\uc0b0\uc0b1\uc0b2\uc0b3\uc0b4\uc0b5\uc0b6\uc0b7\uc0b8\uc0b9\uc0ba\uc0bb\uc0bc\uc0bd\uc0be\uc0bf\uc0c0\uc0c1\uc0c2\uc0c3\uc0c4\uc0c5\uc0c6\uc0c7\uc0c8\uc0c9\uc0ca\uc0cb\uc0cc\uc0cd\uc0ce\uc0cf\uc0d0\uc0d1\uc0d2\uc0d3\uc0d4\uc0d5\uc0d6\uc0d7\uc0d8\uc0d9\uc0da\uc0db\uc0dc\uc0dd\uc0de\uc0df\uc0e0\uc0e1\uc0e2\uc0e3\uc0e4\uc0e5\uc0e6\uc0e7\uc0e8\uc0e9\uc0ea\uc0eb\uc0ec\uc0ed\uc0ee\uc0ef\uc0f0\uc0f1\uc0f2\uc0f3\uc0f4\uc0f5\uc0f6\uc0f7\uc0f8\uc0f9\uc0fa\uc0fb\uc0fc\uc0fd\uc0fe\uc0ff\uc100\uc101\uc102\uc103\uc104\uc105\uc106\uc107\uc108\uc109\uc10a\uc10b\uc10c\uc10d\uc10e\uc10f\uc110\uc111\uc112\uc113\uc114\uc115\uc116\uc117\uc118\uc119\uc11a\uc11b\uc11c\uc11d\uc11e\uc11f\uc120\uc121\uc122\uc123\uc124\uc125\uc126\uc127\uc128\uc129\uc12a\uc12b\uc12c\uc12d\uc12e\uc12f\uc130\uc131\uc132\uc133\uc134\uc135\uc136\uc137\uc138\uc139\uc13a\uc13b\uc13c\uc13d\uc13e\uc13f\uc140\uc141\uc142\uc143\uc144\uc145\uc146\uc147\uc148\uc149\uc14a\uc14b\uc14c\uc14d\uc14e\uc14f\uc150\uc151\uc152\uc153\uc154\uc155\uc156\uc157\uc158\uc159\uc15a\uc15b\uc15c\uc15d\uc15e\uc15f\uc160\uc161\uc162\uc163\uc164\uc165\uc166\uc167\uc168\uc169\uc16a\uc16b\uc16c\uc16d\uc16e\uc16f\uc170\uc171\uc172\uc173\uc174\uc175\uc176\uc177\uc178\uc179\uc17a\uc17b\uc17c\uc17d\uc17e\uc17f\uc180\uc181\uc182\uc183\uc184\uc185\uc186\uc187\uc188\uc189\uc18a\uc18b\uc18c\uc18d\uc18e\uc18f\uc190\uc191\uc192\uc193\uc194\uc195\uc196\uc197\uc198\uc199\uc19a\uc19b\uc19c\uc19d\uc19e\uc19f\uc1a0\uc1a1\uc1a2\uc1a3\uc1a4\uc1a5\uc1a6\uc1a7\uc1a8\uc1a9\uc1aa\uc1ab\uc1ac\uc1ad\uc1ae\uc1af\uc1b0\uc1b1\uc1b2\uc1b3\uc1b4\uc1b5\uc1b6\uc1b7\uc1b8\uc1b9\uc1ba\uc1bb\uc1bc\uc1bd\uc1be\uc1bf\uc1c0\uc1c1\uc1c2\uc1c3\uc1c4\uc1c5\uc1c6\uc1c7\uc1c8\uc1c9\uc1ca\uc1cb\uc1cc\uc1cd\uc1ce\uc1cf\uc1d0\uc1d1\uc1d2\uc1d3\uc1d4\uc1d5\uc1d6\uc1d7\uc1d8\uc1d9\uc1da\uc1db\uc1dc\uc1dd\uc1de\uc1df\uc1e0\uc1e1\uc1e2\uc1e3\uc1e4\uc1e5\uc1e6\uc1e7\uc1e8\uc1e9\uc1ea\uc1eb\uc1ec\uc1ed\uc1ee\uc1ef\uc1f0\uc1f1\uc1f2\uc1f3\uc1f4\uc1f5\uc1f6\uc1f7\uc1f8\uc1f9\uc1fa\uc1fb\uc1fc\uc1fd\uc1fe\uc1ff\uc200\uc201\uc202\uc203\uc204\uc205\uc206\uc207\uc208\uc209\uc20a\uc20b\uc20c\uc20d\uc20e\uc20f\uc210\uc211\uc212\uc213\uc214\uc215\uc216\uc217\uc218\uc219\uc21a\uc21b\uc21c\uc21d\uc21e\uc21f\uc220\uc221\uc222\uc223\uc224\uc225\uc226\uc227\uc228\uc229\uc22a\uc22b\uc22c\uc22d\uc22e\uc22f\uc230\uc231\uc232\uc233\uc234\uc235\uc236\uc237\uc238\uc239\uc23a\uc23b\uc23c\uc23d\uc23e\uc23f\uc240\uc241\uc242\uc243\uc244\uc245\uc246\uc247\uc248\uc249\uc24a\uc24b\uc24c\uc24d\uc24e\uc24f\uc250\uc251\uc252\uc253\uc254\uc255\uc256\uc257\uc258\uc259\uc25a\uc25b\uc25c\uc25d\uc25e\uc25f\uc260\uc261\uc262\uc263\uc264\uc265\uc266\uc267\uc268\uc269\uc26a\uc26b\uc26c\uc26d\uc26e\uc26f\uc270\uc271\uc272\uc273\uc274\uc275\uc276\uc277\uc278\uc279\uc27a\uc27b\uc27c\uc27d\uc27e\uc27f\uc280\uc281\uc282\uc283\uc284\uc285\uc286\uc287\uc288\uc289\uc28a\uc28b\uc28c\uc28d\uc28e\uc28f\uc290\uc291\uc292\uc293\uc294\uc295\uc296\uc297\uc298\uc299\uc29a\uc29b\uc29c\uc29d\uc29e\uc29f\uc2a0\uc2a1\uc2a2\uc2a3\uc2a4\uc2a5\uc2a6\uc2a7\uc2a8\uc2a9\uc2aa\uc2ab\uc2ac\uc2ad\uc2ae\uc2af\uc2b0\uc2b1\uc2b2\uc2b3\uc2b4\uc2b5\uc2b6\uc2b7\uc2b8\uc2b9\uc2ba\uc2bb\uc2bc\uc2bd\uc2be\uc2bf\uc2c0\uc2c1\uc2c2\uc2c3\uc2c4\uc2c5\uc2c6\uc2c7\uc2c8\uc2c9\uc2ca\uc2cb\uc2cc\uc2cd\uc2ce\uc2cf\uc2d0\uc2d1\uc2d2\uc2d3\uc2d4\uc2d5\uc2d6\uc2d7\uc2d8\uc2d9\uc2da\uc2db\uc2dc\uc2dd\uc2de\uc2df\uc2e0\uc2e1\uc2e2\uc2e3\uc2e4\uc2e5\uc2e6\uc2e7\uc2e8\uc2e9\uc2ea\uc2eb\uc2ec\uc2ed\uc2ee\uc2ef\uc2f0\uc2f1\uc2f2\uc2f3\uc2f4\uc2f5\uc2f6\uc2f7\uc2f8\uc2f9\uc2fa\uc2fb\uc2fc\uc2fd\uc2fe\uc2ff\uc300\uc301\uc302\uc303\uc304\uc305\uc306\uc307\uc308\uc309\uc30a\uc30b\uc30c\uc30d\uc30e\uc30f\uc310\uc311\uc312\uc313\uc314\uc315\uc316\uc317\uc318\uc319\uc31a\uc31b\uc31c\uc31d\uc31e\uc31f\uc320\uc321\uc322\uc323\uc324\uc325\uc326\uc327\uc328\uc329\uc32a\uc32b\uc32c\uc32d\uc32e\uc32f\uc330\uc331\uc332\uc333\uc334\uc335\uc336\uc337\uc338\uc339\uc33a\uc33b\uc33c\uc33d\uc33e\uc33f\uc340\uc341\uc342\uc343\uc344\uc345\uc346\uc347\uc348\uc349\uc34a\uc34b\uc34c\uc34d\uc34e\uc34f\uc350\uc351\uc352\uc353\uc354\uc355\uc356\uc357\uc358\uc359\uc35a\uc35b\uc35c\uc35d\uc35e\uc35f\uc360\uc361\uc362\uc363\uc364\uc365\uc366\uc367\uc368\uc369\uc36a\uc36b\uc36c\uc36d\uc36e\uc36f\uc370\uc371\uc372\uc373\uc374\uc375\uc376\uc377\uc378\uc379\uc37a\uc37b\uc37c\uc37d\uc37e\uc37f\uc380\uc381\uc382\uc383\uc384\uc385\uc386\uc387\uc388\uc389\uc38a\uc38b\uc38c\uc38d\uc38e\uc38f\uc390\uc391\uc392\uc393\uc394\uc395\uc396\uc397\uc398\uc399\uc39a\uc39b\uc39c\uc39d\uc39e\uc39f\uc3a0\uc3a1\uc3a2\uc3a3\uc3a4\uc3a5\uc3a6\uc3a7\uc3a8\uc3a9\uc3aa\uc3ab\uc3ac\uc3ad\uc3ae\uc3af\uc3b0\uc3b1\uc3b2\uc3b3\uc3b4\uc3b5\uc3b6\uc3b7\uc3b8\uc3b9\uc3ba\uc3bb\uc3bc\uc3bd\uc3be\uc3bf\uc3c0\uc3c1\uc3c2\uc3c3\uc3c4\uc3c5\uc3c6\uc3c7\uc3c8\uc3c9\uc3ca\uc3cb\uc3cc\uc3cd\uc3ce\uc3cf\uc3d0\uc3d1\uc3d2\uc3d3\uc3d4\uc3d5\uc3d6\uc3d7\uc3d8\uc3d9\uc3da\uc3db\uc3dc\uc3dd\uc3de\uc3df\uc3e0\uc3e1\uc3e2\uc3e3\uc3e4\uc3e5\uc3e6\uc3e7\uc3e8\uc3e9\uc3ea\uc3eb\uc3ec\uc3ed\uc3ee\uc3ef\uc3f0\uc3f1\uc3f2\uc3f3\uc3f4\uc3f5\uc3f6\uc3f7\uc3f8\uc3f9\uc3fa\uc3fb\uc3fc\uc3fd\uc3fe\uc3ff\uc400\uc401\uc402\uc403\uc404\uc405\uc406\uc407\uc408\uc409\uc40a\uc40b\uc40c\uc40d\uc40e\uc40f\uc410\uc411\uc412\uc413\uc414\uc415\uc416\uc417\uc418\uc419\uc41a\uc41b\uc41c\uc41d\uc41e\uc41f\uc420\uc421\uc422\uc423\uc424\uc425\uc426\uc427\uc428\uc429\uc42a\uc42b\uc42c\uc42d\uc42e\uc42f\uc430\uc431\uc432\uc433\uc434\uc435\uc436\uc437\uc438\uc439\uc43a\uc43b\uc43c\uc43d\uc43e\uc43f\uc440\uc441\uc442\uc443\uc444\uc445\uc446\uc447\uc448\uc449\uc44a\uc44b\uc44c\uc44d\uc44e\uc44f\uc450\uc451\uc452\uc453\uc454\uc455\uc456\uc457\uc458\uc459\uc45a\uc45b\uc45c\uc45d\uc45e\uc45f\uc460\uc461\uc462\uc463\uc464\uc465\uc466\uc467\uc468\uc469\uc46a\uc46b\uc46c\uc46d\uc46e\uc46f\uc470\uc471\uc472\uc473\uc474\uc475\uc476\uc477\uc478\uc479\uc47a\uc47b\uc47c\uc47d\uc47e\uc47f\uc480\uc481\uc482\uc483\uc484\uc485\uc486\uc487\uc488\uc489\uc48a\uc48b\uc48c\uc48d\uc48e\uc48f\uc490\uc491\uc492\uc493\uc494\uc495\uc496\uc497\uc498\uc499\uc49a\uc49b\uc49c\uc49d\uc49e\uc49f\uc4a0\uc4a1\uc4a2\uc4a3\uc4a4\uc4a5\uc4a6\uc4a7\uc4a8\uc4a9\uc4aa\uc4ab\uc4ac\uc4ad\uc4ae\uc4af\uc4b0\uc4b1\uc4b2\uc4b3\uc4b4\uc4b5\uc4b6\uc4b7\uc4b8\uc4b9\uc4ba\uc4bb\uc4bc\uc4bd\uc4be\uc4bf\uc4c0\uc4c1\uc4c2\uc4c3\uc4c4\uc4c5\uc4c6\uc4c7\uc4c8\uc4c9\uc4ca\uc4cb\uc4cc\uc4cd\uc4ce\uc4cf\uc4d0\uc4d1\uc4d2\uc4d3\uc4d4\uc4d5\uc4d6\uc4d7\uc4d8\uc4d9\uc4da\uc4db\uc4dc\uc4dd\uc4de\uc4df\uc4e0\uc4e1\uc4e2\uc4e3\uc4e4\uc4e5\uc4e6\uc4e7\uc4e8\uc4e9\uc4ea\uc4eb\uc4ec\uc4ed\uc4ee\uc4ef\uc4f0\uc4f1\uc4f2\uc4f3\uc4f4\uc4f5\uc4f6\uc4f7\uc4f8\uc4f9\uc4fa\uc4fb\uc4fc\uc4fd\uc4fe\uc4ff\uc500\uc501\uc502\uc503\uc504\uc505\uc506\uc507\uc508\uc509\uc50a\uc50b\uc50c\uc50d\uc50e\uc50f\uc510\uc511\uc512\uc513\uc514\uc515\uc516\uc517\uc518\uc519\uc51a\uc51b\uc51c\uc51d\uc51e\uc51f\uc520\uc521\uc522\uc523\uc524\uc525\uc526\uc527\uc528\uc529\uc52a\uc52b\uc52c\uc52d\uc52e\uc52f\uc530\uc531\uc532\uc533\uc534\uc535\uc536\uc537\uc538\uc539\uc53a\uc53b\uc53c\uc53d\uc53e\uc53f\uc540\uc541\uc542\uc543\uc544\uc545\uc546\uc547\uc548\uc549\uc54a\uc54b\uc54c\uc54d\uc54e\uc54f\uc550\uc551\uc552\uc553\uc554\uc555\uc556\uc557\uc558\uc559\uc55a\uc55b\uc55c\uc55d\uc55e\uc55f\uc560\uc561\uc562\uc563\uc564\uc565\uc566\uc567\uc568\uc569\uc56a\uc56b\uc56c\uc56d\uc56e\uc56f\uc570\uc571\uc572\uc573\uc574\uc575\uc576\uc577\uc578\uc579\uc57a\uc57b\uc57c\uc57d\uc57e\uc57f\uc580\uc581\uc582\uc583\uc584\uc585\uc586\uc587\uc588\uc589\uc58a\uc58b\uc58c\uc58d\uc58e\uc58f\uc590\uc591\uc592\uc593\uc594\uc595\uc596\uc597\uc598\uc599\uc59a\uc59b\uc59c\uc59d\uc59e\uc59f\uc5a0\uc5a1\uc5a2\uc5a3\uc5a4\uc5a5\uc5a6\uc5a7\uc5a8\uc5a9\uc5aa\uc5ab\uc5ac\uc5ad\uc5ae\uc5af\uc5b0\uc5b1\uc5b2\uc5b3\uc5b4\uc5b5\uc5b6\uc5b7\uc5b8\uc5b9\uc5ba\uc5bb\uc5bc\uc5bd\uc5be\uc5bf\uc5c0\uc5c1\uc5c2\uc5c3\uc5c4\uc5c5\uc5c6\uc5c7\uc5c8\uc5c9\uc5ca\uc5cb\uc5cc\uc5cd\uc5ce\uc5cf\uc5d0\uc5d1\uc5d2\uc5d3\uc5d4\uc5d5\uc5d6\uc5d7\uc5d8\uc5d9\uc5da\uc5db\uc5dc\uc5dd\uc5de\uc5df\uc5e0\uc5e1\uc5e2\uc5e3\uc5e4\uc5e5\uc5e6\uc5e7\uc5e8\uc5e9\uc5ea\uc5eb\uc5ec\uc5ed\uc5ee\uc5ef\uc5f0\uc5f1\uc5f2\uc5f3\uc5f4\uc5f5\uc5f6\uc5f7\uc5f8\uc5f9\uc5fa\uc5fb\uc5fc\uc5fd\uc5fe\uc5ff\uc600\uc601\uc602\uc603\uc604\uc605\uc606\uc607\uc608\uc609\uc60a\uc60b\uc60c\uc60d\uc60e\uc60f\uc610\uc611\uc612\uc613\uc614\uc615\uc616\uc617\uc618\uc619\uc61a\uc61b\uc61c\uc61d\uc61e\uc61f\uc620\uc621\uc622\uc623\uc624\uc625\uc626\uc627\uc628\uc629\uc62a\uc62b\uc62c\uc62d\uc62e\uc62f\uc630\uc631\uc632\uc633\uc634\uc635\uc636\uc637\uc638\uc639\uc63a\uc63b\uc63c\uc63d\uc63e\uc63f\uc640\uc641\uc642\uc643\uc644\uc645\uc646\uc647\uc648\uc649\uc64a\uc64b\uc64c\uc64d\uc64e\uc64f\uc650\uc651\uc652\uc653\uc654\uc655\uc656\uc657\uc658\uc659\uc65a\uc65b\uc65c\uc65d\uc65e\uc65f\uc660\uc661\uc662\uc663\uc664\uc665\uc666\uc667\uc668\uc669\uc66a\uc66b\uc66c\uc66d\uc66e\uc66f\uc670\uc671\uc672\uc673\uc674\uc675\uc676\uc677\uc678\uc679\uc67a\uc67b\uc67c\uc67d\uc67e\uc67f\uc680\uc681\uc682\uc683\uc684\uc685\uc686\uc687\uc688\uc689\uc68a\uc68b\uc68c\uc68d\uc68e\uc68f\uc690\uc691\uc692\uc693\uc694\uc695\uc696\uc697\uc698\uc699\uc69a\uc69b\uc69c\uc69d\uc69e\uc69f\uc6a0\uc6a1\uc6a2\uc6a3\uc6a4\uc6a5\uc6a6\uc6a7\uc6a8\uc6a9\uc6aa\uc6ab\uc6ac\uc6ad\uc6ae\uc6af\uc6b0\uc6b1\uc6b2\uc6b3\uc6b4\uc6b5\uc6b6\uc6b7\uc6b8\uc6b9\uc6ba\uc6bb\uc6bc\uc6bd\uc6be\uc6bf\uc6c0\uc6c1\uc6c2\uc6c3\uc6c4\uc6c5\uc6c6\uc6c7\uc6c8\uc6c9\uc6ca\uc6cb\uc6cc\uc6cd\uc6ce\uc6cf\uc6d0\uc6d1\uc6d2\uc6d3\uc6d4\uc6d5\uc6d6\uc6d7\uc6d8\uc6d9\uc6da\uc6db\uc6dc\uc6dd\uc6de\uc6df\uc6e0\uc6e1\uc6e2\uc6e3\uc6e4\uc6e5\uc6e6\uc6e7\uc6e8\uc6e9\uc6ea\uc6eb\uc6ec\uc6ed\uc6ee\uc6ef\uc6f0\uc6f1\uc6f2\uc6f3\uc6f4\uc6f5\uc6f6\uc6f7\uc6f8\uc6f9\uc6fa\uc6fb\uc6fc\uc6fd\uc6fe\uc6ff\uc700\uc701\uc702\uc703\uc704\uc705\uc706\uc707\uc708\uc709\uc70a\uc70b\uc70c\uc70d\uc70e\uc70f\uc710\uc711\uc712\uc713\uc714\uc715\uc716\uc717\uc718\uc719\uc71a\uc71b\uc71c\uc71d\uc71e\uc71f\uc720\uc721\uc722\uc723\uc724\uc725\uc726\uc727\uc728\uc729\uc72a\uc72b\uc72c\uc72d\uc72e\uc72f\uc730\uc731\uc732\uc733\uc734\uc735\uc736\uc737\uc738\uc739\uc73a\uc73b\uc73c\uc73d\uc73e\uc73f\uc740\uc741\uc742\uc743\uc744\uc745\uc746\uc747\uc748\uc749\uc74a\uc74b\uc74c\uc74d\uc74e\uc74f\uc750\uc751\uc752\uc753\uc754\uc755\uc756\uc757\uc758\uc759\uc75a\uc75b\uc75c\uc75d\uc75e\uc75f\uc760\uc761\uc762\uc763\uc764\uc765\uc766\uc767\uc768\uc769\uc76a\uc76b\uc76c\uc76d\uc76e\uc76f\uc770\uc771\uc772\uc773\uc774\uc775\uc776\uc777\uc778\uc779\uc77a\uc77b\uc77c\uc77d\uc77e\uc77f\uc780\uc781\uc782\uc783\uc784\uc785\uc786\uc787\uc788\uc789\uc78a\uc78b\uc78c\uc78d\uc78e\uc78f\uc790\uc791\uc792\uc793\uc794\uc795\uc796\uc797\uc798\uc799\uc79a\uc79b\uc79c\uc79d\uc79e\uc79f\uc7a0\uc7a1\uc7a2\uc7a3\uc7a4\uc7a5\uc7a6\uc7a7\uc7a8\uc7a9\uc7aa\uc7ab\uc7ac\uc7ad\uc7ae\uc7af\uc7b0\uc7b1\uc7b2\uc7b3\uc7b4\uc7b5\uc7b6\uc7b7\uc7b8\uc7b9\uc7ba\uc7bb\uc7bc\uc7bd\uc7be\uc7bf\uc7c0\uc7c1\uc7c2\uc7c3\uc7c4\uc7c5\uc7c6\uc7c7\uc7c8\uc7c9\uc7ca\uc7cb\uc7cc\uc7cd\uc7ce\uc7cf\uc7d0\uc7d1\uc7d2\uc7d3\uc7d4\uc7d5\uc7d6\uc7d7\uc7d8\uc7d9\uc7da\uc7db\uc7dc\uc7dd\uc7de\uc7df\uc7e0\uc7e1\uc7e2\uc7e3\uc7e4\uc7e5\uc7e6\uc7e7\uc7e8\uc7e9\uc7ea\uc7eb\uc7ec\uc7ed\uc7ee\uc7ef\uc7f0\uc7f1\uc7f2\uc7f3\uc7f4\uc7f5\uc7f6\uc7f7\uc7f8\uc7f9\uc7fa\uc7fb\uc7fc\uc7fd\uc7fe\uc7ff\uc800\uc801\uc802\uc803\uc804\uc805\uc806\uc807\uc808\uc809\uc80a\uc80b\uc80c\uc80d\uc80e\uc80f\uc810\uc811\uc812\uc813\uc814\uc815\uc816\uc817\uc818\uc819\uc81a\uc81b\uc81c\uc81d\uc81e\uc81f\uc820\uc821\uc822\uc823\uc824\uc825\uc826\uc827\uc828\uc829\uc82a\uc82b\uc82c\uc82d\uc82e\uc82f\uc830\uc831\uc832\uc833\uc834\uc835\uc836\uc837\uc838\uc839\uc83a\uc83b\uc83c\uc83d\uc83e\uc83f\uc840\uc841\uc842\uc843\uc844\uc845\uc846\uc847\uc848\uc849\uc84a\uc84b\uc84c\uc84d\uc84e\uc84f\uc850\uc851\uc852\uc853\uc854\uc855\uc856\uc857\uc858\uc859\uc85a\uc85b\uc85c\uc85d\uc85e\uc85f\uc860\uc861\uc862\uc863\uc864\uc865\uc866\uc867\uc868\uc869\uc86a\uc86b\uc86c\uc86d\uc86e\uc86f\uc870\uc871\uc872\uc873\uc874\uc875\uc876\uc877\uc878\uc879\uc87a\uc87b\uc87c\uc87d\uc87e\uc87f\uc880\uc881\uc882\uc883\uc884\uc885\uc886\uc887\uc888\uc889\uc88a\uc88b\uc88c\uc88d\uc88e\uc88f\uc890\uc891\uc892\uc893\uc894\uc895\uc896\uc897\uc898\uc899\uc89a\uc89b\uc89c\uc89d\uc89e\uc89f\uc8a0\uc8a1\uc8a2\uc8a3\uc8a4\uc8a5\uc8a6\uc8a7\uc8a8\uc8a9\uc8aa\uc8ab\uc8ac\uc8ad\uc8ae\uc8af\uc8b0\uc8b1\uc8b2\uc8b3\uc8b4\uc8b5\uc8b6\uc8b7\uc8b8\uc8b9\uc8ba\uc8bb\uc8bc\uc8bd\uc8be\uc8bf\uc8c0\uc8c1\uc8c2\uc8c3\uc8c4\uc8c5\uc8c6\uc8c7\uc8c8\uc8c9\uc8ca\uc8cb\uc8cc\uc8cd\uc8ce\uc8cf\uc8d0\uc8d1\uc8d2\uc8d3\uc8d4\uc8d5\uc8d6\uc8d7\uc8d8\uc8d9\uc8da\uc8db\uc8dc\uc8dd\uc8de\uc8df\uc8e0\uc8e1\uc8e2\uc8e3\uc8e4\uc8e5\uc8e6\uc8e7\uc8e8\uc8e9\uc8ea\uc8eb\uc8ec\uc8ed\uc8ee\uc8ef\uc8f0\uc8f1\uc8f2\uc8f3\uc8f4\uc8f5\uc8f6\uc8f7\uc8f8\uc8f9\uc8fa\uc8fb\uc8fc\uc8fd\uc8fe\uc8ff\uc900\uc901\uc902\uc903\uc904\uc905\uc906\uc907\uc908\uc909\uc90a\uc90b\uc90c\uc90d\uc90e\uc90f\uc910\uc911\uc912\uc913\uc914\uc915\uc916\uc917\uc918\uc919\uc91a\uc91b\uc91c\uc91d\uc91e\uc91f\uc920\uc921\uc922\uc923\uc924\uc925\uc926\uc927\uc928\uc929\uc92a\uc92b\uc92c\uc92d\uc92e\uc92f\uc930\uc931\uc932\uc933\uc934\uc935\uc936\uc937\uc938\uc939\uc93a\uc93b\uc93c\uc93d\uc93e\uc93f\uc940\uc941\uc942\uc943\uc944\uc945\uc946\uc947\uc948\uc949\uc94a\uc94b\uc94c\uc94d\uc94e\uc94f\uc950\uc951\uc952\uc953\uc954\uc955\uc956\uc957\uc958\uc959\uc95a\uc95b\uc95c\uc95d\uc95e\uc95f\uc960\uc961\uc962\uc963\uc964\uc965\uc966\uc967\uc968\uc969\uc96a\uc96b\uc96c\uc96d\uc96e\uc96f\uc970\uc971\uc972\uc973\uc974\uc975\uc976\uc977\uc978\uc979\uc97a\uc97b\uc97c\uc97d\uc97e\uc97f\uc980\uc981\uc982\uc983\uc984\uc985\uc986\uc987\uc988\uc989\uc98a\uc98b\uc98c\uc98d\uc98e\uc98f\uc990\uc991\uc992\uc993\uc994\uc995\uc996\uc997\uc998\uc999\uc99a\uc99b\uc99c\uc99d\uc99e\uc99f\uc9a0\uc9a1\uc9a2\uc9a3\uc9a4\uc9a5\uc9a6\uc9a7\uc9a8\uc9a9\uc9aa\uc9ab\uc9ac\uc9ad\uc9ae\uc9af\uc9b0\uc9b1\uc9b2\uc9b3\uc9b4\uc9b5\uc9b6\uc9b7\uc9b8\uc9b9\uc9ba\uc9bb\uc9bc\uc9bd\uc9be\uc9bf\uc9c0\uc9c1\uc9c2\uc9c3\uc9c4\uc9c5\uc9c6\uc9c7\uc9c8\uc9c9\uc9ca\uc9cb\uc9cc\uc9cd\uc9ce\uc9cf\uc9d0\uc9d1\uc9d2\uc9d3\uc9d4\uc9d5\uc9d6\uc9d7\uc9d8\uc9d9\uc9da\uc9db\uc9dc\uc9dd\uc9de\uc9df\uc9e0\uc9e1\uc9e2\uc9e3\uc9e4\uc9e5\uc9e6\uc9e7\uc9e8\uc9e9\uc9ea\uc9eb\uc9ec\uc9ed\uc9ee\uc9ef\uc9f0\uc9f1\uc9f2\uc9f3\uc9f4\uc9f5\uc9f6\uc9f7\uc9f8\uc9f9\uc9fa\uc9fb\uc9fc\uc9fd\uc9fe\uc9ff\uca00\uca01\uca02\uca03\uca04\uca05\uca06\uca07\uca08\uca09\uca0a\uca0b\uca0c\uca0d\uca0e\uca0f\uca10\uca11\uca12\uca13\uca14\uca15\uca16\uca17\uca18\uca19\uca1a\uca1b\uca1c\uca1d\uca1e\uca1f\uca20\uca21\uca22\uca23\uca24\uca25\uca26\uca27\uca28\uca29\uca2a\uca2b\uca2c\uca2d\uca2e\uca2f\uca30\uca31\uca32\uca33\uca34\uca35\uca36\uca37\uca38\uca39\uca3a\uca3b\uca3c\uca3d\uca3e\uca3f\uca40\uca41\uca42\uca43\uca44\uca45\uca46\uca47\uca48\uca49\uca4a\uca4b\uca4c\uca4d\uca4e\uca4f\uca50\uca51\uca52\uca53\uca54\uca55\uca56\uca57\uca58\uca59\uca5a\uca5b\uca5c\uca5d\uca5e\uca5f\uca60\uca61\uca62\uca63\uca64\uca65\uca66\uca67\uca68\uca69\uca6a\uca6b\uca6c\uca6d\uca6e\uca6f\uca70\uca71\uca72\uca73\uca74\uca75\uca76\uca77\uca78\uca79\uca7a\uca7b\uca7c\uca7d\uca7e\uca7f\uca80\uca81\uca82\uca83\uca84\uca85\uca86\uca87\uca88\uca89\uca8a\uca8b\uca8c\uca8d\uca8e\uca8f\uca90\uca91\uca92\uca93\uca94\uca95\uca96\uca97\uca98\uca99\uca9a\uca9b\uca9c\uca9d\uca9e\uca9f\ucaa0\ucaa1\ucaa2\ucaa3\ucaa4\ucaa5\ucaa6\ucaa7\ucaa8\ucaa9\ucaaa\ucaab\ucaac\ucaad\ucaae\ucaaf\ucab0\ucab1\ucab2\ucab3\ucab4\ucab5\ucab6\ucab7\ucab8\ucab9\ucaba\ucabb\ucabc\ucabd\ucabe\ucabf\ucac0\ucac1\ucac2\ucac3\ucac4\ucac5\ucac6\ucac7\ucac8\ucac9\ucaca\ucacb\ucacc\ucacd\ucace\ucacf\ucad0\ucad1\ucad2\ucad3\ucad4\ucad5\ucad6\ucad7\ucad8\ucad9\ucada\ucadb\ucadc\ucadd\ucade\ucadf\ucae0\ucae1\ucae2\ucae3\ucae4\ucae5\ucae6\ucae7\ucae8\ucae9\ucaea\ucaeb\ucaec\ucaed\ucaee\ucaef\ucaf0\ucaf1\ucaf2\ucaf3\ucaf4\ucaf5\ucaf6\ucaf7\ucaf8\ucaf9\ucafa\ucafb\ucafc\ucafd\ucafe\ucaff\ucb00\ucb01\ucb02\ucb03\ucb04\ucb05\ucb06\ucb07\ucb08\ucb09\ucb0a\ucb0b\ucb0c\ucb0d\ucb0e\ucb0f\ucb10\ucb11\ucb12\ucb13\ucb14\ucb15\ucb16\ucb17\ucb18\ucb19\ucb1a\ucb1b\ucb1c\ucb1d\ucb1e\ucb1f\ucb20\ucb21\ucb22\ucb23\ucb24\ucb25\ucb26\ucb27\ucb28\ucb29\ucb2a\ucb2b\ucb2c\ucb2d\ucb2e\ucb2f\ucb30\ucb31\ucb32\ucb33\ucb34\ucb35\ucb36\ucb37\ucb38\ucb39\ucb3a\ucb3b\ucb3c\ucb3d\ucb3e\ucb3f\ucb40\ucb41\ucb42\ucb43\ucb44\ucb45\ucb46\ucb47\ucb48\ucb49\ucb4a\ucb4b\ucb4c\ucb4d\ucb4e\ucb4f\ucb50\ucb51\ucb52\ucb53\ucb54\ucb55\ucb56\ucb57\ucb58\ucb59\ucb5a\ucb5b\ucb5c\ucb5d\ucb5e\ucb5f\ucb60\ucb61\ucb62\ucb63\ucb64\ucb65\ucb66\ucb67\ucb68\ucb69\ucb6a\ucb6b\ucb6c\ucb6d\ucb6e\ucb6f\ucb70\ucb71\ucb72\ucb73\ucb74\ucb75\ucb76\ucb77\ucb78\ucb79\ucb7a\ucb7b\ucb7c\ucb7d\ucb7e\ucb7f\ucb80\ucb81\ucb82\ucb83\ucb84\ucb85\ucb86\ucb87\ucb88\ucb89\ucb8a\ucb8b\ucb8c\ucb8d\ucb8e\ucb8f\ucb90\ucb91\ucb92\ucb93\ucb94\ucb95\ucb96\ucb97\ucb98\ucb99\ucb9a\ucb9b\ucb9c\ucb9d\ucb9e\ucb9f\ucba0\ucba1\ucba2\ucba3\ucba4\ucba5\ucba6\ucba7\ucba8\ucba9\ucbaa\ucbab\ucbac\ucbad\ucbae\ucbaf\ucbb0\ucbb1\ucbb2\ucbb3\ucbb4\ucbb5\ucbb6\ucbb7\ucbb8\ucbb9\ucbba\ucbbb\ucbbc\ucbbd\ucbbe\ucbbf\ucbc0\ucbc1\ucbc2\ucbc3\ucbc4\ucbc5\ucbc6\ucbc7\ucbc8\ucbc9\ucbca\ucbcb\ucbcc\ucbcd\ucbce\ucbcf\ucbd0\ucbd1\ucbd2\ucbd3\ucbd4\ucbd5\ucbd6\ucbd7\ucbd8\ucbd9\ucbda\ucbdb\ucbdc\ucbdd\ucbde\ucbdf\ucbe0\ucbe1\ucbe2\ucbe3\ucbe4\ucbe5\ucbe6\ucbe7\ucbe8\ucbe9\ucbea\ucbeb\ucbec\ucbed\ucbee\ucbef\ucbf0\ucbf1\ucbf2\ucbf3\ucbf4\ucbf5\ucbf6\ucbf7\ucbf8\ucbf9\ucbfa\ucbfb\ucbfc\ucbfd\ucbfe\ucbff\ucc00\ucc01\ucc02\ucc03\ucc04\ucc05\ucc06\ucc07\ucc08\ucc09\ucc0a\ucc0b\ucc0c\ucc0d\ucc0e\ucc0f\ucc10\ucc11\ucc12\ucc13\ucc14\ucc15\ucc16\ucc17\ucc18\ucc19\ucc1a\ucc1b\ucc1c\ucc1d\ucc1e\ucc1f\ucc20\ucc21\ucc22\ucc23\ucc24\ucc25\ucc26\ucc27\ucc28\ucc29\ucc2a\ucc2b\ucc2c\ucc2d\ucc2e\ucc2f\ucc30\ucc31\ucc32\ucc33\ucc34\ucc35\ucc36\ucc37\ucc38\ucc39\ucc3a\ucc3b\ucc3c\ucc3d\ucc3e\ucc3f\ucc40\ucc41\ucc42\ucc43\ucc44\ucc45\ucc46\ucc47\ucc48\ucc49\ucc4a\ucc4b\ucc4c\ucc4d\ucc4e\ucc4f\ucc50\ucc51\ucc52\ucc53\ucc54\ucc55\ucc56\ucc57\ucc58\ucc59\ucc5a\ucc5b\ucc5c\ucc5d\ucc5e\ucc5f\ucc60\ucc61\ucc62\ucc63\ucc64\ucc65\ucc66\ucc67\ucc68\ucc69\ucc6a\ucc6b\ucc6c\ucc6d\ucc6e\ucc6f\ucc70\ucc71\ucc72\ucc73\ucc74\ucc75\ucc76\ucc77\ucc78\ucc79\ucc7a\ucc7b\ucc7c\ucc7d\ucc7e\ucc7f\ucc80\ucc81\ucc82\ucc83\ucc84\ucc85\ucc86\ucc87\ucc88\ucc89\ucc8a\ucc8b\ucc8c\ucc8d\ucc8e\ucc8f\ucc90\ucc91\ucc92\ucc93\ucc94\ucc95\ucc96\ucc97\ucc98\ucc99\ucc9a\ucc9b\ucc9c\ucc9d\ucc9e\ucc9f\ucca0\ucca1\ucca2\ucca3\ucca4\ucca5\ucca6\ucca7\ucca8\ucca9\uccaa\uccab\uccac\uccad\uccae\uccaf\uccb0\uccb1\uccb2\uccb3\uccb4\uccb5\uccb6\uccb7\uccb8\uccb9\uccba\uccbb\uccbc\uccbd\uccbe\uccbf\uccc0\uccc1\uccc2\uccc3\uccc4\uccc5\uccc6\uccc7\uccc8\uccc9\uccca\ucccb\ucccc\ucccd\uccce\ucccf\uccd0\uccd1\uccd2\uccd3\uccd4\uccd5\uccd6\uccd7\uccd8\uccd9\uccda\uccdb\uccdc\uccdd\uccde\uccdf\ucce0\ucce1\ucce2\ucce3\ucce4\ucce5\ucce6\ucce7\ucce8\ucce9\uccea\ucceb\uccec\ucced\uccee\uccef\uccf0\uccf1\uccf2\uccf3\uccf4\uccf5\uccf6\uccf7\uccf8\uccf9\uccfa\uccfb\uccfc\uccfd\uccfe\uccff\ucd00\ucd01\ucd02\ucd03\ucd04\ucd05\ucd06\ucd07\ucd08\ucd09\ucd0a\ucd0b\ucd0c\ucd0d\ucd0e\ucd0f\ucd10\ucd11\ucd12\ucd13\ucd14\ucd15\ucd16\ucd17\ucd18\ucd19\ucd1a\ucd1b\ucd1c\ucd1d\ucd1e\ucd1f\ucd20\ucd21\ucd22\ucd23\ucd24\ucd25\ucd26\ucd27\ucd28\ucd29\ucd2a\ucd2b\ucd2c\ucd2d\ucd2e\ucd2f\ucd30\ucd31\ucd32\ucd33\ucd34\ucd35\ucd36\ucd37\ucd38\ucd39\ucd3a\ucd3b\ucd3c\ucd3d\ucd3e\ucd3f\ucd40\ucd41\ucd42\ucd43\ucd44\ucd45\ucd46\ucd47\ucd48\ucd49\ucd4a\ucd4b\ucd4c\ucd4d\ucd4e\ucd4f\ucd50\ucd51\ucd52\ucd53\ucd54\ucd55\ucd56\ucd57\ucd58\ucd59\ucd5a\ucd5b\ucd5c\ucd5d\ucd5e\ucd5f\ucd60\ucd61\ucd62\ucd63\ucd64\ucd65\ucd66\ucd67\ucd68\ucd69\ucd6a\ucd6b\ucd6c\ucd6d\ucd6e\ucd6f\ucd70\ucd71\ucd72\ucd73\ucd74\ucd75\ucd76\ucd77\ucd78\ucd79\ucd7a\ucd7b\ucd7c\ucd7d\ucd7e\ucd7f\ucd80\ucd81\ucd82\ucd83\ucd84\ucd85\ucd86\ucd87\ucd88\ucd89\ucd8a\ucd8b\ucd8c\ucd8d\ucd8e\ucd8f\ucd90\ucd91\ucd92\ucd93\ucd94\ucd95\ucd96\ucd97\ucd98\ucd99\ucd9a\ucd9b\ucd9c\ucd9d\ucd9e\ucd9f\ucda0\ucda1\ucda2\ucda3\ucda4\ucda5\ucda6\ucda7\ucda8\ucda9\ucdaa\ucdab\ucdac\ucdad\ucdae\ucdaf\ucdb0\ucdb1\ucdb2\ucdb3\ucdb4\ucdb5\ucdb6\ucdb7\ucdb8\ucdb9\ucdba\ucdbb\ucdbc\ucdbd\ucdbe\ucdbf\ucdc0\ucdc1\ucdc2\ucdc3\ucdc4\ucdc5\ucdc6\ucdc7\ucdc8\ucdc9\ucdca\ucdcb\ucdcc\ucdcd\ucdce\ucdcf\ucdd0\ucdd1\ucdd2\ucdd3\ucdd4\ucdd5\ucdd6\ucdd7\ucdd8\ucdd9\ucdda\ucddb\ucddc\ucddd\ucdde\ucddf\ucde0\ucde1\ucde2\ucde3\ucde4\ucde5\ucde6\ucde7\ucde8\ucde9\ucdea\ucdeb\ucdec\ucded\ucdee\ucdef\ucdf0\ucdf1\ucdf2\ucdf3\ucdf4\ucdf5\ucdf6\ucdf7\ucdf8\ucdf9\ucdfa\ucdfb\ucdfc\ucdfd\ucdfe\ucdff\uce00\uce01\uce02\uce03\uce04\uce05\uce06\uce07\uce08\uce09\uce0a\uce0b\uce0c\uce0d\uce0e\uce0f\uce10\uce11\uce12\uce13\uce14\uce15\uce16\uce17\uce18\uce19\uce1a\uce1b\uce1c\uce1d\uce1e\uce1f\uce20\uce21\uce22\uce23\uce24\uce25\uce26\uce27\uce28\uce29\uce2a\uce2b\uce2c\uce2d\uce2e\uce2f\uce30\uce31\uce32\uce33\uce34\uce35\uce36\uce37\uce38\uce39\uce3a\uce3b\uce3c\uce3d\uce3e\uce3f\uce40\uce41\uce42\uce43\uce44\uce45\uce46\uce47\uce48\uce49\uce4a\uce4b\uce4c\uce4d\uce4e\uce4f\uce50\uce51\uce52\uce53\uce54\uce55\uce56\uce57\uce58\uce59\uce5a\uce5b\uce5c\uce5d\uce5e\uce5f\uce60\uce61\uce62\uce63\uce64\uce65\uce66\uce67\uce68\uce69\uce6a\uce6b\uce6c\uce6d\uce6e\uce6f\uce70\uce71\uce72\uce73\uce74\uce75\uce76\uce77\uce78\uce79\uce7a\uce7b\uce7c\uce7d\uce7e\uce7f\uce80\uce81\uce82\uce83\uce84\uce85\uce86\uce87\uce88\uce89\uce8a\uce8b\uce8c\uce8d\uce8e\uce8f\uce90\uce91\uce92\uce93\uce94\uce95\uce96\uce97\uce98\uce99\uce9a\uce9b\uce9c\uce9d\uce9e\uce9f\ucea0\ucea1\ucea2\ucea3\ucea4\ucea5\ucea6\ucea7\ucea8\ucea9\uceaa\uceab\uceac\ucead\uceae\uceaf\uceb0\uceb1\uceb2\uceb3\uceb4\uceb5\uceb6\uceb7\uceb8\uceb9\uceba\ucebb\ucebc\ucebd\ucebe\ucebf\ucec0\ucec1\ucec2\ucec3\ucec4\ucec5\ucec6\ucec7\ucec8\ucec9\uceca\ucecb\ucecc\ucecd\ucece\ucecf\uced0\uced1\uced2\uced3\uced4\uced5\uced6\uced7\uced8\uced9\uceda\ucedb\ucedc\ucedd\ucede\ucedf\ucee0\ucee1\ucee2\ucee3\ucee4\ucee5\ucee6\ucee7\ucee8\ucee9\uceea\uceeb\uceec\uceed\uceee\uceef\ucef0\ucef1\ucef2\ucef3\ucef4\ucef5\ucef6\ucef7\ucef8\ucef9\ucefa\ucefb\ucefc\ucefd\ucefe\uceff\ucf00\ucf01\ucf02\ucf03\ucf04\ucf05\ucf06\ucf07\ucf08\ucf09\ucf0a\ucf0b\ucf0c\ucf0d\ucf0e\ucf0f\ucf10\ucf11\ucf12\ucf13\ucf14\ucf15\ucf16\ucf17\ucf18\ucf19\ucf1a\ucf1b\ucf1c\ucf1d\ucf1e\ucf1f\ucf20\ucf21\ucf22\ucf23\ucf24\ucf25\ucf26\ucf27\ucf28\ucf29\ucf2a\ucf2b\ucf2c\ucf2d\ucf2e\ucf2f\ucf30\ucf31\ucf32\ucf33\ucf34\ucf35\ucf36\ucf37\ucf38\ucf39\ucf3a\ucf3b\ucf3c\ucf3d\ucf3e\ucf3f\ucf40\ucf41\ucf42\ucf43\ucf44\ucf45\ucf46\ucf47\ucf48\ucf49\ucf4a\ucf4b\ucf4c\ucf4d\ucf4e\ucf4f\ucf50\ucf51\ucf52\ucf53\ucf54\ucf55\ucf56\ucf57\ucf58\ucf59\ucf5a\ucf5b\ucf5c\ucf5d\ucf5e\ucf5f\ucf60\ucf61\ucf62\ucf63\ucf64\ucf65\ucf66\ucf67\ucf68\ucf69\ucf6a\ucf6b\ucf6c\ucf6d\ucf6e\ucf6f\ucf70\ucf71\ucf72\ucf73\ucf74\ucf75\ucf76\ucf77\ucf78\ucf79\ucf7a\ucf7b\ucf7c\ucf7d\ucf7e\ucf7f\ucf80\ucf81\ucf82\ucf83\ucf84\ucf85\ucf86\ucf87\ucf88\ucf89\ucf8a\ucf8b\ucf8c\ucf8d\ucf8e\ucf8f\ucf90\ucf91\ucf92\ucf93\ucf94\ucf95\ucf96\ucf97\ucf98\ucf99\ucf9a\ucf9b\ucf9c\ucf9d\ucf9e\ucf9f\ucfa0\ucfa1\ucfa2\ucfa3\ucfa4\ucfa5\ucfa6\ucfa7\ucfa8\ucfa9\ucfaa\ucfab\ucfac\ucfad\ucfae\ucfaf\ucfb0\ucfb1\ucfb2\ucfb3\ucfb4\ucfb5\ucfb6\ucfb7\ucfb8\ucfb9\ucfba\ucfbb\ucfbc\ucfbd\ucfbe\ucfbf\ucfc0\ucfc1\ucfc2\ucfc3\ucfc4\ucfc5\ucfc6\ucfc7\ucfc8\ucfc9\ucfca\ucfcb\ucfcc\ucfcd\ucfce\ucfcf\ucfd0\ucfd1\ucfd2\ucfd3\ucfd4\ucfd5\ucfd6\ucfd7\ucfd8\ucfd9\ucfda\ucfdb\ucfdc\ucfdd\ucfde\ucfdf\ucfe0\ucfe1\ucfe2\ucfe3\ucfe4\ucfe5\ucfe6\ucfe7\ucfe8\ucfe9\ucfea\ucfeb\ucfec\ucfed\ucfee\ucfef\ucff0\ucff1\ucff2\ucff3\ucff4\ucff5\ucff6\ucff7\ucff8\ucff9\ucffa\ucffb\ucffc\ucffd\ucffe\ucfff\ud000\ud001\ud002\ud003\ud004\ud005\ud006\ud007\ud008\ud009\ud00a\ud00b\ud00c\ud00d\ud00e\ud00f\ud010\ud011\ud012\ud013\ud014\ud015\ud016\ud017\ud018\ud019\ud01a\ud01b\ud01c\ud01d\ud01e\ud01f\ud020\ud021\ud022\ud023\ud024\ud025\ud026\ud027\ud028\ud029\ud02a\ud02b\ud02c\ud02d\ud02e\ud02f\ud030\ud031\ud032\ud033\ud034\ud035\ud036\ud037\ud038\ud039\ud03a\ud03b\ud03c\ud03d\ud03e\ud03f\ud040\ud041\ud042\ud043\ud044\ud045\ud046\ud047\ud048\ud049\ud04a\ud04b\ud04c\ud04d\ud04e\ud04f\ud050\ud051\ud052\ud053\ud054\ud055\ud056\ud057\ud058\ud059\ud05a\ud05b\ud05c\ud05d\ud05e\ud05f\ud060\ud061\ud062\ud063\ud064\ud065\ud066\ud067\ud068\ud069\ud06a\ud06b\ud06c\ud06d\ud06e\ud06f\ud070\ud071\ud072\ud073\ud074\ud075\ud076\ud077\ud078\ud079\ud07a\ud07b\ud07c\ud07d\ud07e\ud07f\ud080\ud081\ud082\ud083\ud084\ud085\ud086\ud087\ud088\ud089\ud08a\ud08b\ud08c\ud08d\ud08e\ud08f\ud090\ud091\ud092\ud093\ud094\ud095\ud096\ud097\ud098\ud099\ud09a\ud09b\ud09c\ud09d\ud09e\ud09f\ud0a0\ud0a1\ud0a2\ud0a3\ud0a4\ud0a5\ud0a6\ud0a7\ud0a8\ud0a9\ud0aa\ud0ab\ud0ac\ud0ad\ud0ae\ud0af\ud0b0\ud0b1\ud0b2\ud0b3\ud0b4\ud0b5\ud0b6\ud0b7\ud0b8\ud0b9\ud0ba\ud0bb\ud0bc\ud0bd\ud0be\ud0bf\ud0c0\ud0c1\ud0c2\ud0c3\ud0c4\ud0c5\ud0c6\ud0c7\ud0c8\ud0c9\ud0ca\ud0cb\ud0cc\ud0cd\ud0ce\ud0cf\ud0d0\ud0d1\ud0d2\ud0d3\ud0d4\ud0d5\ud0d6\ud0d7\ud0d8\ud0d9\ud0da\ud0db\ud0dc\ud0dd\ud0de\ud0df\ud0e0\ud0e1\ud0e2\ud0e3\ud0e4\ud0e5\ud0e6\ud0e7\ud0e8\ud0e9\ud0ea\ud0eb\ud0ec\ud0ed\ud0ee\ud0ef\ud0f0\ud0f1\ud0f2\ud0f3\ud0f4\ud0f5\ud0f6\ud0f7\ud0f8\ud0f9\ud0fa\ud0fb\ud0fc\ud0fd\ud0fe\ud0ff\ud100\ud101\ud102\ud103\ud104\ud105\ud106\ud107\ud108\ud109\ud10a\ud10b\ud10c\ud10d\ud10e\ud10f\ud110\ud111\ud112\ud113\ud114\ud115\ud116\ud117\ud118\ud119\ud11a\ud11b\ud11c\ud11d\ud11e\ud11f\ud120\ud121\ud122\ud123\ud124\ud125\ud126\ud127\ud128\ud129\ud12a\ud12b\ud12c\ud12d\ud12e\ud12f\ud130\ud131\ud132\ud133\ud134\ud135\ud136\ud137\ud138\ud139\ud13a\ud13b\ud13c\ud13d\ud13e\ud13f\ud140\ud141\ud142\ud143\ud144\ud145\ud146\ud147\ud148\ud149\ud14a\ud14b\ud14c\ud14d\ud14e\ud14f\ud150\ud151\ud152\ud153\ud154\ud155\ud156\ud157\ud158\ud159\ud15a\ud15b\ud15c\ud15d\ud15e\ud15f\ud160\ud161\ud162\ud163\ud164\ud165\ud166\ud167\ud168\ud169\ud16a\ud16b\ud16c\ud16d\ud16e\ud16f\ud170\ud171\ud172\ud173\ud174\ud175\ud176\ud177\ud178\ud179\ud17a\ud17b\ud17c\ud17d\ud17e\ud17f\ud180\ud181\ud182\ud183\ud184\ud185\ud186\ud187\ud188\ud189\ud18a\ud18b\ud18c\ud18d\ud18e\ud18f\ud190\ud191\ud192\ud193\ud194\ud195\ud196\ud197\ud198\ud199\ud19a\ud19b\ud19c\ud19d\ud19e\ud19f\ud1a0\ud1a1\ud1a2\ud1a3\ud1a4\ud1a5\ud1a6\ud1a7\ud1a8\ud1a9\ud1aa\ud1ab\ud1ac\ud1ad\ud1ae\ud1af\ud1b0\ud1b1\ud1b2\ud1b3\ud1b4\ud1b5\ud1b6\ud1b7\ud1b8\ud1b9\ud1ba\ud1bb\ud1bc\ud1bd\ud1be\ud1bf\ud1c0\ud1c1\ud1c2\ud1c3\ud1c4\ud1c5\ud1c6\ud1c7\ud1c8\ud1c9\ud1ca\ud1cb\ud1cc\ud1cd\ud1ce\ud1cf\ud1d0\ud1d1\ud1d2\ud1d3\ud1d4\ud1d5\ud1d6\ud1d7\ud1d8\ud1d9\ud1da\ud1db\ud1dc\ud1dd\ud1de\ud1df\ud1e0\ud1e1\ud1e2\ud1e3\ud1e4\ud1e5\ud1e6\ud1e7\ud1e8\ud1e9\ud1ea\ud1eb\ud1ec\ud1ed\ud1ee\ud1ef\ud1f0\ud1f1\ud1f2\ud1f3\ud1f4\ud1f5\ud1f6\ud1f7\ud1f8\ud1f9\ud1fa\ud1fb\ud1fc\ud1fd\ud1fe\ud1ff\ud200\ud201\ud202\ud203\ud204\ud205\ud206\ud207\ud208\ud209\ud20a\ud20b\ud20c\ud20d\ud20e\ud20f\ud210\ud211\ud212\ud213\ud214\ud215\ud216\ud217\ud218\ud219\ud21a\ud21b\ud21c\ud21d\ud21e\ud21f\ud220\ud221\ud222\ud223\ud224\ud225\ud226\ud227\ud228\ud229\ud22a\ud22b\ud22c\ud22d\ud22e\ud22f\ud230\ud231\ud232\ud233\ud234\ud235\ud236\ud237\ud238\ud239\ud23a\ud23b\ud23c\ud23d\ud23e\ud23f\ud240\ud241\ud242\ud243\ud244\ud245\ud246\ud247\ud248\ud249\ud24a\ud24b\ud24c\ud24d\ud24e\ud24f\ud250\ud251\ud252\ud253\ud254\ud255\ud256\ud257\ud258\ud259\ud25a\ud25b\ud25c\ud25d\ud25e\ud25f\ud260\ud261\ud262\ud263\ud264\ud265\ud266\ud267\ud268\ud269\ud26a\ud26b\ud26c\ud26d\ud26e\ud26f\ud270\ud271\ud272\ud273\ud274\ud275\ud276\ud277\ud278\ud279\ud27a\ud27b\ud27c\ud27d\ud27e\ud27f\ud280\ud281\ud282\ud283\ud284\ud285\ud286\ud287\ud288\ud289\ud28a\ud28b\ud28c\ud28d\ud28e\ud28f\ud290\ud291\ud292\ud293\ud294\ud295\ud296\ud297\ud298\ud299\ud29a\ud29b\ud29c\ud29d\ud29e\ud29f\ud2a0\ud2a1\ud2a2\ud2a3\ud2a4\ud2a5\ud2a6\ud2a7\ud2a8\ud2a9\ud2aa\ud2ab\ud2ac\ud2ad\ud2ae\ud2af\ud2b0\ud2b1\ud2b2\ud2b3\ud2b4\ud2b5\ud2b6\ud2b7\ud2b8\ud2b9\ud2ba\ud2bb\ud2bc\ud2bd\ud2be\ud2bf\ud2c0\ud2c1\ud2c2\ud2c3\ud2c4\ud2c5\ud2c6\ud2c7\ud2c8\ud2c9\ud2ca\ud2cb\ud2cc\ud2cd\ud2ce\ud2cf\ud2d0\ud2d1\ud2d2\ud2d3\ud2d4\ud2d5\ud2d6\ud2d7\ud2d8\ud2d9\ud2da\ud2db\ud2dc\ud2dd\ud2de\ud2df\ud2e0\ud2e1\ud2e2\ud2e3\ud2e4\ud2e5\ud2e6\ud2e7\ud2e8\ud2e9\ud2ea\ud2eb\ud2ec\ud2ed\ud2ee\ud2ef\ud2f0\ud2f1\ud2f2\ud2f3\ud2f4\ud2f5\ud2f6\ud2f7\ud2f8\ud2f9\ud2fa\ud2fb\ud2fc\ud2fd\ud2fe\ud2ff\ud300\ud301\ud302\ud303\ud304\ud305\ud306\ud307\ud308\ud309\ud30a\ud30b\ud30c\ud30d\ud30e\ud30f\ud310\ud311\ud312\ud313\ud314\ud315\ud316\ud317\ud318\ud319\ud31a\ud31b\ud31c\ud31d\ud31e\ud31f\ud320\ud321\ud322\ud323\ud324\ud325\ud326\ud327\ud328\ud329\ud32a\ud32b\ud32c\ud32d\ud32e\ud32f\ud330\ud331\ud332\ud333\ud334\ud335\ud336\ud337\ud338\ud339\ud33a\ud33b\ud33c\ud33d\ud33e\ud33f\ud340\ud341\ud342\ud343\ud344\ud345\ud346\ud347\ud348\ud349\ud34a\ud34b\ud34c\ud34d\ud34e\ud34f\ud350\ud351\ud352\ud353\ud354\ud355\ud356\ud357\ud358\ud359\ud35a\ud35b\ud35c\ud35d\ud35e\ud35f\ud360\ud361\ud362\ud363\ud364\ud365\ud366\ud367\ud368\ud369\ud36a\ud36b\ud36c\ud36d\ud36e\ud36f\ud370\ud371\ud372\ud373\ud374\ud375\ud376\ud377\ud378\ud379\ud37a\ud37b\ud37c\ud37d\ud37e\ud37f\ud380\ud381\ud382\ud383\ud384\ud385\ud386\ud387\ud388\ud389\ud38a\ud38b\ud38c\ud38d\ud38e\ud38f\ud390\ud391\ud392\ud393\ud394\ud395\ud396\ud397\ud398\ud399\ud39a\ud39b\ud39c\ud39d\ud39e\ud39f\ud3a0\ud3a1\ud3a2\ud3a3\ud3a4\ud3a5\ud3a6\ud3a7\ud3a8\ud3a9\ud3aa\ud3ab\ud3ac\ud3ad\ud3ae\ud3af\ud3b0\ud3b1\ud3b2\ud3b3\ud3b4\ud3b5\ud3b6\ud3b7\ud3b8\ud3b9\ud3ba\ud3bb\ud3bc\ud3bd\ud3be\ud3bf\ud3c0\ud3c1\ud3c2\ud3c3\ud3c4\ud3c5\ud3c6\ud3c7\ud3c8\ud3c9\ud3ca\ud3cb\ud3cc\ud3cd\ud3ce\ud3cf\ud3d0\ud3d1\ud3d2\ud3d3\ud3d4\ud3d5\ud3d6\ud3d7\ud3d8\ud3d9\ud3da\ud3db\ud3dc\ud3dd\ud3de\ud3df\ud3e0\ud3e1\ud3e2\ud3e3\ud3e4\ud3e5\ud3e6\ud3e7\ud3e8\ud3e9\ud3ea\ud3eb\ud3ec\ud3ed\ud3ee\ud3ef\ud3f0\ud3f1\ud3f2\ud3f3\ud3f4\ud3f5\ud3f6\ud3f7\ud3f8\ud3f9\ud3fa\ud3fb\ud3fc\ud3fd\ud3fe\ud3ff\ud400\ud401\ud402\ud403\ud404\ud405\ud406\ud407\ud408\ud409\ud40a\ud40b\ud40c\ud40d\ud40e\ud40f\ud410\ud411\ud412\ud413\ud414\ud415\ud416\ud417\ud418\ud419\ud41a\ud41b\ud41c\ud41d\ud41e\ud41f\ud420\ud421\ud422\ud423\ud424\ud425\ud426\ud427\ud428\ud429\ud42a\ud42b\ud42c\ud42d\ud42e\ud42f\ud430\ud431\ud432\ud433\ud434\ud435\ud436\ud437\ud438\ud439\ud43a\ud43b\ud43c\ud43d\ud43e\ud43f\ud440\ud441\ud442\ud443\ud444\ud445\ud446\ud447\ud448\ud449\ud44a\ud44b\ud44c\ud44d\ud44e\ud44f\ud450\ud451\ud452\ud453\ud454\ud455\ud456\ud457\ud458\ud459\ud45a\ud45b\ud45c\ud45d\ud45e\ud45f\ud460\ud461\ud462\ud463\ud464\ud465\ud466\ud467\ud468\ud469\ud46a\ud46b\ud46c\ud46d\ud46e\ud46f\ud470\ud471\ud472\ud473\ud474\ud475\ud476\ud477\ud478\ud479\ud47a\ud47b\ud47c\ud47d\ud47e\ud47f\ud480\ud481\ud482\ud483\ud484\ud485\ud486\ud487\ud488\ud489\ud48a\ud48b\ud48c\ud48d\ud48e\ud48f\ud490\ud491\ud492\ud493\ud494\ud495\ud496\ud497\ud498\ud499\ud49a\ud49b\ud49c\ud49d\ud49e\ud49f\ud4a0\ud4a1\ud4a2\ud4a3\ud4a4\ud4a5\ud4a6\ud4a7\ud4a8\ud4a9\ud4aa\ud4ab\ud4ac\ud4ad\ud4ae\ud4af\ud4b0\ud4b1\ud4b2\ud4b3\ud4b4\ud4b5\ud4b6\ud4b7\ud4b8\ud4b9\ud4ba\ud4bb\ud4bc\ud4bd\ud4be\ud4bf\ud4c0\ud4c1\ud4c2\ud4c3\ud4c4\ud4c5\ud4c6\ud4c7\ud4c8\ud4c9\ud4ca\ud4cb\ud4cc\ud4cd\ud4ce\ud4cf\ud4d0\ud4d1\ud4d2\ud4d3\ud4d4\ud4d5\ud4d6\ud4d7\ud4d8\ud4d9\ud4da\ud4db\ud4dc\ud4dd\ud4de\ud4df\ud4e0\ud4e1\ud4e2\ud4e3\ud4e4\ud4e5\ud4e6\ud4e7\ud4e8\ud4e9\ud4ea\ud4eb\ud4ec\ud4ed\ud4ee\ud4ef\ud4f0\ud4f1\ud4f2\ud4f3\ud4f4\ud4f5\ud4f6\ud4f7\ud4f8\ud4f9\ud4fa\ud4fb\ud4fc\ud4fd\ud4fe\ud4ff\ud500\ud501\ud502\ud503\ud504\ud505\ud506\ud507\ud508\ud509\ud50a\ud50b\ud50c\ud50d\ud50e\ud50f\ud510\ud511\ud512\ud513\ud514\ud515\ud516\ud517\ud518\ud519\ud51a\ud51b\ud51c\ud51d\ud51e\ud51f\ud520\ud521\ud522\ud523\ud524\ud525\ud526\ud527\ud528\ud529\ud52a\ud52b\ud52c\ud52d\ud52e\ud52f\ud530\ud531\ud532\ud533\ud534\ud535\ud536\ud537\ud538\ud539\ud53a\ud53b\ud53c\ud53d\ud53e\ud53f\ud540\ud541\ud542\ud543\ud544\ud545\ud546\ud547\ud548\ud549\ud54a\ud54b\ud54c\ud54d\ud54e\ud54f\ud550\ud551\ud552\ud553\ud554\ud555\ud556\ud557\ud558\ud559\ud55a\ud55b\ud55c\ud55d\ud55e\ud55f\ud560\ud561\ud562\ud563\ud564\ud565\ud566\ud567\ud568\ud569\ud56a\ud56b\ud56c\ud56d\ud56e\ud56f\ud570\ud571\ud572\ud573\ud574\ud575\ud576\ud577\ud578\ud579\ud57a\ud57b\ud57c\ud57d\ud57e\ud57f\ud580\ud581\ud582\ud583\ud584\ud585\ud586\ud587\ud588\ud589\ud58a\ud58b\ud58c\ud58d\ud58e\ud58f\ud590\ud591\ud592\ud593\ud594\ud595\ud596\ud597\ud598\ud599\ud59a\ud59b\ud59c\ud59d\ud59e\ud59f\ud5a0\ud5a1\ud5a2\ud5a3\ud5a4\ud5a5\ud5a6\ud5a7\ud5a8\ud5a9\ud5aa\ud5ab\ud5ac\ud5ad\ud5ae\ud5af\ud5b0\ud5b1\ud5b2\ud5b3\ud5b4\ud5b5\ud5b6\ud5b7\ud5b8\ud5b9\ud5ba\ud5bb\ud5bc\ud5bd\ud5be\ud5bf\ud5c0\ud5c1\ud5c2\ud5c3\ud5c4\ud5c5\ud5c6\ud5c7\ud5c8\ud5c9\ud5ca\ud5cb\ud5cc\ud5cd\ud5ce\ud5cf\ud5d0\ud5d1\ud5d2\ud5d3\ud5d4\ud5d5\ud5d6\ud5d7\ud5d8\ud5d9\ud5da\ud5db\ud5dc\ud5dd\ud5de\ud5df\ud5e0\ud5e1\ud5e2\ud5e3\ud5e4\ud5e5\ud5e6\ud5e7\ud5e8\ud5e9\ud5ea\ud5eb\ud5ec\ud5ed\ud5ee\ud5ef\ud5f0\ud5f1\ud5f2\ud5f3\ud5f4\ud5f5\ud5f6\ud5f7\ud5f8\ud5f9\ud5fa\ud5fb\ud5fc\ud5fd\ud5fe\ud5ff\ud600\ud601\ud602\ud603\ud604\ud605\ud606\ud607\ud608\ud609\ud60a\ud60b\ud60c\ud60d\ud60e\ud60f\ud610\ud611\ud612\ud613\ud614\ud615\ud616\ud617\ud618\ud619\ud61a\ud61b\ud61c\ud61d\ud61e\ud61f\ud620\ud621\ud622\ud623\ud624\ud625\ud626\ud627\ud628\ud629\ud62a\ud62b\ud62c\ud62d\ud62e\ud62f\ud630\ud631\ud632\ud633\ud634\ud635\ud636\ud637\ud638\ud639\ud63a\ud63b\ud63c\ud63d\ud63e\ud63f\ud640\ud641\ud642\ud643\ud644\ud645\ud646\ud647\ud648\ud649\ud64a\ud64b\ud64c\ud64d\ud64e\ud64f\ud650\ud651\ud652\ud653\ud654\ud655\ud656\ud657\ud658\ud659\ud65a\ud65b\ud65c\ud65d\ud65e\ud65f\ud660\ud661\ud662\ud663\ud664\ud665\ud666\ud667\ud668\ud669\ud66a\ud66b\ud66c\ud66d\ud66e\ud66f\ud670\ud671\ud672\ud673\ud674\ud675\ud676\ud677\ud678\ud679\ud67a\ud67b\ud67c\ud67d\ud67e\ud67f\ud680\ud681\ud682\ud683\ud684\ud685\ud686\ud687\ud688\ud689\ud68a\ud68b\ud68c\ud68d\ud68e\ud68f\ud690\ud691\ud692\ud693\ud694\ud695\ud696\ud697\ud698\ud699\ud69a\ud69b\ud69c\ud69d\ud69e\ud69f\ud6a0\ud6a1\ud6a2\ud6a3\ud6a4\ud6a5\ud6a6\ud6a7\ud6a8\ud6a9\ud6aa\ud6ab\ud6ac\ud6ad\ud6ae\ud6af\ud6b0\ud6b1\ud6b2\ud6b3\ud6b4\ud6b5\ud6b6\ud6b7\ud6b8\ud6b9\ud6ba\ud6bb\ud6bc\ud6bd\ud6be\ud6bf\ud6c0\ud6c1\ud6c2\ud6c3\ud6c4\ud6c5\ud6c6\ud6c7\ud6c8\ud6c9\ud6ca\ud6cb\ud6cc\ud6cd\ud6ce\ud6cf\ud6d0\ud6d1\ud6d2\ud6d3\ud6d4\ud6d5\ud6d6\ud6d7\ud6d8\ud6d9\ud6da\ud6db\ud6dc\ud6dd\ud6de\ud6df\ud6e0\ud6e1\ud6e2\ud6e3\ud6e4\ud6e5\ud6e6\ud6e7\ud6e8\ud6e9\ud6ea\ud6eb\ud6ec\ud6ed\ud6ee\ud6ef\ud6f0\ud6f1\ud6f2\ud6f3\ud6f4\ud6f5\ud6f6\ud6f7\ud6f8\ud6f9\ud6fa\ud6fb\ud6fc\ud6fd\ud6fe\ud6ff\ud700\ud701\ud702\ud703\ud704\ud705\ud706\ud707\ud708\ud709\ud70a\ud70b\ud70c\ud70d\ud70e\ud70f\ud710\ud711\ud712\ud713\ud714\ud715\ud716\ud717\ud718\ud719\ud71a\ud71b\ud71c\ud71d\ud71e\ud71f\ud720\ud721\ud722\ud723\ud724\ud725\ud726\ud727\ud728\ud729\ud72a\ud72b\ud72c\ud72d\ud72e\ud72f\ud730\ud731\ud732\ud733\ud734\ud735\ud736\ud737\ud738\ud739\ud73a\ud73b\ud73c\ud73d\ud73e\ud73f\ud740\ud741\ud742\ud743\ud744\ud745\ud746\ud747\ud748\ud749\ud74a\ud74b\ud74c\ud74d\ud74e\ud74f\ud750\ud751\ud752\ud753\ud754\ud755\ud756\ud757\ud758\ud759\ud75a\ud75b\ud75c\ud75d\ud75e\ud75f\ud760\ud761\ud762\ud763\ud764\ud765\ud766\ud767\ud768\ud769\ud76a\ud76b\ud76c\ud76d\ud76e\ud76f\ud770\ud771\ud772\ud773\ud774\ud775\ud776\ud777\ud778\ud779\ud77a\ud77b\ud77c\ud77d\ud77e\ud77f\ud780\ud781\ud782\ud783\ud784\ud785\ud786\ud787\ud788\ud789\ud78a\ud78b\ud78c\ud78d\ud78e\ud78f\ud790\ud791\ud792\ud793\ud794\ud795\ud796\ud797\ud798\ud799\ud79a\ud79b\ud79c\ud79d\ud79e\ud79f\ud7a0\ud7a1\ud7a2\ud7a3\uf900\uf901\uf902\uf903\uf904\uf905\uf906\uf907\uf908\uf909\uf90a\uf90b\uf90c\uf90d\uf90e\uf90f\uf910\uf911\uf912\uf913\uf914\uf915\uf916\uf917\uf918\uf919\uf91a\uf91b\uf91c\uf91d\uf91e\uf91f\uf920\uf921\uf922\uf923\uf924\uf925\uf926\uf927\uf928\uf929\uf92a\uf92b\uf92c\uf92d\uf92e\uf92f\uf930\uf931\uf932\uf933\uf934\uf935\uf936\uf937\uf938\uf939\uf93a\uf93b\uf93c\uf93d\uf93e\uf93f\uf940\uf941\uf942\uf943\uf944\uf945\uf946\uf947\uf948\uf949\uf94a\uf94b\uf94c\uf94d\uf94e\uf94f\uf950\uf951\uf952\uf953\uf954\uf955\uf956\uf957\uf958\uf959\uf95a\uf95b\uf95c\uf95d\uf95e\uf95f\uf960\uf961\uf962\uf963\uf964\uf965\uf966\uf967\uf968\uf969\uf96a\uf96b\uf96c\uf96d\uf96e\uf96f\uf970\uf971\uf972\uf973\uf974\uf975\uf976\uf977\uf978\uf979\uf97a\uf97b\uf97c\uf97d\uf97e\uf97f\uf980\uf981\uf982\uf983\uf984\uf985\uf986\uf987\uf988\uf989\uf98a\uf98b\uf98c\uf98d\uf98e\uf98f\uf990\uf991\uf992\uf993\uf994\uf995\uf996\uf997\uf998\uf999\uf99a\uf99b\uf99c\uf99d\uf99e\uf99f\uf9a0\uf9a1\uf9a2\uf9a3\uf9a4\uf9a5\uf9a6\uf9a7\uf9a8\uf9a9\uf9aa\uf9ab\uf9ac\uf9ad\uf9ae\uf9af\uf9b0\uf9b1\uf9b2\uf9b3\uf9b4\uf9b5\uf9b6\uf9b7\uf9b8\uf9b9\uf9ba\uf9bb\uf9bc\uf9bd\uf9be\uf9bf\uf9c0\uf9c1\uf9c2\uf9c3\uf9c4\uf9c5\uf9c6\uf9c7\uf9c8\uf9c9\uf9ca\uf9cb\uf9cc\uf9cd\uf9ce\uf9cf\uf9d0\uf9d1\uf9d2\uf9d3\uf9d4\uf9d5\uf9d6\uf9d7\uf9d8\uf9d9\uf9da\uf9db\uf9dc\uf9dd\uf9de\uf9df\uf9e0\uf9e1\uf9e2\uf9e3\uf9e4\uf9e5\uf9e6\uf9e7\uf9e8\uf9e9\uf9ea\uf9eb\uf9ec\uf9ed\uf9ee\uf9ef\uf9f0\uf9f1\uf9f2\uf9f3\uf9f4\uf9f5\uf9f6\uf9f7\uf9f8\uf9f9\uf9fa\uf9fb\uf9fc\uf9fd\uf9fe\uf9ff\ufa00\ufa01\ufa02\ufa03\ufa04\ufa05\ufa06\ufa07\ufa08\ufa09\ufa0a\ufa0b\ufa0c\ufa0d\ufa0e\ufa0f\ufa10\ufa11\ufa12\ufa13\ufa14\ufa15\ufa16\ufa17\ufa18\ufa19\ufa1a\ufa1b\ufa1c\ufa1d\ufa1e\ufa1f\ufa20\ufa21\ufa22\ufa23\ufa24\ufa25\ufa26\ufa27\ufa28\ufa29\ufa2a\ufa2b\ufa2c\ufa2d\ufa30\ufa31\ufa32\ufa33\ufa34\ufa35\ufa36\ufa37\ufa38\ufa39\ufa3a\ufa3b\ufa3c\ufa3d\ufa3e\ufa3f\ufa40\ufa41\ufa42\ufa43\ufa44\ufa45\ufa46\ufa47\ufa48\ufa49\ufa4a\ufa4b\ufa4c\ufa4d\ufa4e\ufa4f\ufa50\ufa51\ufa52\ufa53\ufa54\ufa55\ufa56\ufa57\ufa58\ufa59\ufa5a\ufa5b\ufa5c\ufa5d\ufa5e\ufa5f\ufa60\ufa61\ufa62\ufa63\ufa64\ufa65\ufa66\ufa67\ufa68\ufa69\ufa6a\ufa70\ufa71\ufa72\ufa73\ufa74\ufa75\ufa76\ufa77\ufa78\ufa79\ufa7a\ufa7b\ufa7c\ufa7d\ufa7e\ufa7f\ufa80\ufa81\ufa82\ufa83\ufa84\ufa85\ufa86\ufa87\ufa88\ufa89\ufa8a\ufa8b\ufa8c\ufa8d\ufa8e\ufa8f\ufa90\ufa91\ufa92\ufa93\ufa94\ufa95\ufa96\ufa97\ufa98\ufa99\ufa9a\ufa9b\ufa9c\ufa9d\ufa9e\ufa9f\ufaa0\ufaa1\ufaa2\ufaa3\ufaa4\ufaa5\ufaa6\ufaa7\ufaa8\ufaa9\ufaaa\ufaab\ufaac\ufaad\ufaae\ufaaf\ufab0\ufab1\ufab2\ufab3\ufab4\ufab5\ufab6\ufab7\ufab8\ufab9\ufaba\ufabb\ufabc\ufabd\ufabe\ufabf\ufac0\ufac1\ufac2\ufac3\ufac4\ufac5\ufac6\ufac7\ufac8\ufac9\ufaca\ufacb\ufacc\ufacd\uface\ufacf\ufad0\ufad1\ufad2\ufad3\ufad4\ufad5\ufad6\ufad7\ufad8\ufad9\ufb1d\ufb1f\ufb20\ufb21\ufb22\ufb23\ufb24\ufb25\ufb26\ufb27\ufb28\ufb2a\ufb2b\ufb2c\ufb2d\ufb2e\ufb2f\ufb30\ufb31\ufb32\ufb33\ufb34\ufb35\ufb36\ufb38\ufb39\ufb3a\ufb3b\ufb3c\ufb3e\ufb40\ufb41\ufb43\ufb44\ufb46\ufb47\ufb48\ufb49\ufb4a\ufb4b\ufb4c\ufb4d\ufb4e\ufb4f\ufb50\ufb51\ufb52\ufb53\ufb54\ufb55\ufb56\ufb57\ufb58\ufb59\ufb5a\ufb5b\ufb5c\ufb5d\ufb5e\ufb5f\ufb60\ufb61\ufb62\ufb63\ufb64\ufb65\ufb66\ufb67\ufb68\ufb69\ufb6a\ufb6b\ufb6c\ufb6d\ufb6e\ufb6f\ufb70\ufb71\ufb72\ufb73\ufb74\ufb75\ufb76\ufb77\ufb78\ufb79\ufb7a\ufb7b\ufb7c\ufb7d\ufb7e\ufb7f\ufb80\ufb81\ufb82\ufb83\ufb84\ufb85\ufb86\ufb87\ufb88\ufb89\ufb8a\ufb8b\ufb8c\ufb8d\ufb8e\ufb8f\ufb90\ufb91\ufb92\ufb93\ufb94\ufb95\ufb96\ufb97\ufb98\ufb99\ufb9a\ufb9b\ufb9c\ufb9d\ufb9e\ufb9f\ufba0\ufba1\ufba2\ufba3\ufba4\ufba5\ufba6\ufba7\ufba8\ufba9\ufbaa\ufbab\ufbac\ufbad\ufbae\ufbaf\ufbb0\ufbb1\ufbd3\ufbd4\ufbd5\ufbd6\ufbd7\ufbd8\ufbd9\ufbda\ufbdb\ufbdc\ufbdd\ufbde\ufbdf\ufbe0\ufbe1\ufbe2\ufbe3\ufbe4\ufbe5\ufbe6\ufbe7\ufbe8\ufbe9\ufbea\ufbeb\ufbec\ufbed\ufbee\ufbef\ufbf0\ufbf1\ufbf2\ufbf3\ufbf4\ufbf5\ufbf6\ufbf7\ufbf8\ufbf9\ufbfa\ufbfb\ufbfc\ufbfd\ufbfe\ufbff\ufc00\ufc01\ufc02\ufc03\ufc04\ufc05\ufc06\ufc07\ufc08\ufc09\ufc0a\ufc0b\ufc0c\ufc0d\ufc0e\ufc0f\ufc10\ufc11\ufc12\ufc13\ufc14\ufc15\ufc16\ufc17\ufc18\ufc19\ufc1a\ufc1b\ufc1c\ufc1d\ufc1e\ufc1f\ufc20\ufc21\ufc22\ufc23\ufc24\ufc25\ufc26\ufc27\ufc28\ufc29\ufc2a\ufc2b\ufc2c\ufc2d\ufc2e\ufc2f\ufc30\ufc31\ufc32\ufc33\ufc34\ufc35\ufc36\ufc37\ufc38\ufc39\ufc3a\ufc3b\ufc3c\ufc3d\ufc3e\ufc3f\ufc40\ufc41\ufc42\ufc43\ufc44\ufc45\ufc46\ufc47\ufc48\ufc49\ufc4a\ufc4b\ufc4c\ufc4d\ufc4e\ufc4f\ufc50\ufc51\ufc52\ufc53\ufc54\ufc55\ufc56\ufc57\ufc58\ufc59\ufc5a\ufc5b\ufc5c\ufc5d\ufc5e\ufc5f\ufc60\ufc61\ufc62\ufc63\ufc64\ufc65\ufc66\ufc67\ufc68\ufc69\ufc6a\ufc6b\ufc6c\ufc6d\ufc6e\ufc6f\ufc70\ufc71\ufc72\ufc73\ufc74\ufc75\ufc76\ufc77\ufc78\ufc79\ufc7a\ufc7b\ufc7c\ufc7d\ufc7e\ufc7f\ufc80\ufc81\ufc82\ufc83\ufc84\ufc85\ufc86\ufc87\ufc88\ufc89\ufc8a\ufc8b\ufc8c\ufc8d\ufc8e\ufc8f\ufc90\ufc91\ufc92\ufc93\ufc94\ufc95\ufc96\ufc97\ufc98\ufc99\ufc9a\ufc9b\ufc9c\ufc9d\ufc9e\ufc9f\ufca0\ufca1\ufca2\ufca3\ufca4\ufca5\ufca6\ufca7\ufca8\ufca9\ufcaa\ufcab\ufcac\ufcad\ufcae\ufcaf\ufcb0\ufcb1\ufcb2\ufcb3\ufcb4\ufcb5\ufcb6\ufcb7\ufcb8\ufcb9\ufcba\ufcbb\ufcbc\ufcbd\ufcbe\ufcbf\ufcc0\ufcc1\ufcc2\ufcc3\ufcc4\ufcc5\ufcc6\ufcc7\ufcc8\ufcc9\ufcca\ufccb\ufccc\ufccd\ufcce\ufccf\ufcd0\ufcd1\ufcd2\ufcd3\ufcd4\ufcd5\ufcd6\ufcd7\ufcd8\ufcd9\ufcda\ufcdb\ufcdc\ufcdd\ufcde\ufcdf\ufce0\ufce1\ufce2\ufce3\ufce4\ufce5\ufce6\ufce7\ufce8\ufce9\ufcea\ufceb\ufcec\ufced\ufcee\ufcef\ufcf0\ufcf1\ufcf2\ufcf3\ufcf4\ufcf5\ufcf6\ufcf7\ufcf8\ufcf9\ufcfa\ufcfb\ufcfc\ufcfd\ufcfe\ufcff\ufd00\ufd01\ufd02\ufd03\ufd04\ufd05\ufd06\ufd07\ufd08\ufd09\ufd0a\ufd0b\ufd0c\ufd0d\ufd0e\ufd0f\ufd10\ufd11\ufd12\ufd13\ufd14\ufd15\ufd16\ufd17\ufd18\ufd19\ufd1a\ufd1b\ufd1c\ufd1d\ufd1e\ufd1f\ufd20\ufd21\ufd22\ufd23\ufd24\ufd25\ufd26\ufd27\ufd28\ufd29\ufd2a\ufd2b\ufd2c\ufd2d\ufd2e\ufd2f\ufd30\ufd31\ufd32\ufd33\ufd34\ufd35\ufd36\ufd37\ufd38\ufd39\ufd3a\ufd3b\ufd3c\ufd3d\ufd50\ufd51\ufd52\ufd53\ufd54\ufd55\ufd56\ufd57\ufd58\ufd59\ufd5a\ufd5b\ufd5c\ufd5d\ufd5e\ufd5f\ufd60\ufd61\ufd62\ufd63\ufd64\ufd65\ufd66\ufd67\ufd68\ufd69\ufd6a\ufd6b\ufd6c\ufd6d\ufd6e\ufd6f\ufd70\ufd71\ufd72\ufd73\ufd74\ufd75\ufd76\ufd77\ufd78\ufd79\ufd7a\ufd7b\ufd7c\ufd7d\ufd7e\ufd7f\ufd80\ufd81\ufd82\ufd83\ufd84\ufd85\ufd86\ufd87\ufd88\ufd89\ufd8a\ufd8b\ufd8c\ufd8d\ufd8e\ufd8f\ufd92\ufd93\ufd94\ufd95\ufd96\ufd97\ufd98\ufd99\ufd9a\ufd9b\ufd9c\ufd9d\ufd9e\ufd9f\ufda0\ufda1\ufda2\ufda3\ufda4\ufda5\ufda6\ufda7\ufda8\ufda9\ufdaa\ufdab\ufdac\ufdad\ufdae\ufdaf\ufdb0\ufdb1\ufdb2\ufdb3\ufdb4\ufdb5\ufdb6\ufdb7\ufdb8\ufdb9\ufdba\ufdbb\ufdbc\ufdbd\ufdbe\ufdbf\ufdc0\ufdc1\ufdc2\ufdc3\ufdc4\ufdc5\ufdc6\ufdc7\ufdf0\ufdf1\ufdf2\ufdf3\ufdf4\ufdf5\ufdf6\ufdf7\ufdf8\ufdf9\ufdfa\ufdfb\ufe70\ufe71\ufe72\ufe73\ufe74\ufe76\ufe77\ufe78\ufe79\ufe7a\ufe7b\ufe7c\ufe7d\ufe7e\ufe7f\ufe80\ufe81\ufe82\ufe83\ufe84\ufe85\ufe86\ufe87\ufe88\ufe89\ufe8a\ufe8b\ufe8c\ufe8d\ufe8e\ufe8f\ufe90\ufe91\ufe92\ufe93\ufe94\ufe95\ufe96\ufe97\ufe98\ufe99\ufe9a\ufe9b\ufe9c\ufe9d\ufe9e\ufe9f\ufea0\ufea1\ufea2\ufea3\ufea4\ufea5\ufea6\ufea7\ufea8\ufea9\ufeaa\ufeab\ufeac\ufead\ufeae\ufeaf\ufeb0\ufeb1\ufeb2\ufeb3\ufeb4\ufeb5\ufeb6\ufeb7\ufeb8\ufeb9\ufeba\ufebb\ufebc\ufebd\ufebe\ufebf\ufec0\ufec1\ufec2\ufec3\ufec4\ufec5\ufec6\ufec7\ufec8\ufec9\ufeca\ufecb\ufecc\ufecd\ufece\ufecf\ufed0\ufed1\ufed2\ufed3\ufed4\ufed5\ufed6\ufed7\ufed8\ufed9\ufeda\ufedb\ufedc\ufedd\ufede\ufedf\ufee0\ufee1\ufee2\ufee3\ufee4\ufee5\ufee6\ufee7\ufee8\ufee9\ufeea\ufeeb\ufeec\ufeed\ufeee\ufeef\ufef0\ufef1\ufef2\ufef3\ufef4\ufef5\ufef6\ufef7\ufef8\ufef9\ufefa\ufefb\ufefc\uff66\uff67\uff68\uff69\uff6a\uff6b\uff6c\uff6d\uff6e\uff6f\uff71\uff72\uff73\uff74\uff75\uff76\uff77\uff78\uff79\uff7a\uff7b\uff7c\uff7d\uff7e\uff7f\uff80\uff81\uff82\uff83\uff84\uff85\uff86\uff87\uff88\uff89\uff8a\uff8b\uff8c\uff8d\uff8e\uff8f\uff90\uff91\uff92\uff93\uff94\uff95\uff96\uff97\uff98\uff99\uff9a\uff9b\uff9c\uff9d\uffa0\uffa1\uffa2\uffa3\uffa4\uffa5\uffa6\uffa7\uffa8\uffa9\uffaa\uffab\uffac\uffad\uffae\uffaf\uffb0\uffb1\uffb2\uffb3\uffb4\uffb5\uffb6\uffb7\uffb8\uffb9\uffba\uffbb\uffbc\uffbd\uffbe\uffc2\uffc3\uffc4\uffc5\uffc6\uffc7\uffca\uffcb\uffcc\uffcd\uffce\uffcf\uffd2\uffd3\uffd4\uffd5\uffd6\uffd7\uffda\uffdb\uffdc'

Lt = u'\u01c5\u01c8\u01cb\u01f2\u1f88\u1f89\u1f8a\u1f8b\u1f8c\u1f8d\u1f8e\u1f8f\u1f98\u1f99\u1f9a\u1f9b\u1f9c\u1f9d\u1f9e\u1f9f\u1fa8\u1fa9\u1faa\u1fab\u1fac\u1fad\u1fae\u1faf\u1fbc\u1fcc\u1ffc'

Lu = u'ABCDEFGHIJKLMNOPQRSTUVWXYZ\xc0\xc1\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xcb\xcc\xcd\xce\xcf\xd0\xd1\xd2\xd3\xd4\xd5\xd6\xd8\xd9\xda\xdb\xdc\xdd\xde\u0100\u0102\u0104\u0106\u0108\u010a\u010c\u010e\u0110\u0112\u0114\u0116\u0118\u011a\u011c\u011e\u0120\u0122\u0124\u0126\u0128\u012a\u012c\u012e\u0130\u0132\u0134\u0136\u0139\u013b\u013d\u013f\u0141\u0143\u0145\u0147\u014a\u014c\u014e\u0150\u0152\u0154\u0156\u0158\u015a\u015c\u015e\u0160\u0162\u0164\u0166\u0168\u016a\u016c\u016e\u0170\u0172\u0174\u0176\u0178\u0179\u017b\u017d\u0181\u0182\u0184\u0186\u0187\u0189\u018a\u018b\u018e\u018f\u0190\u0191\u0193\u0194\u0196\u0197\u0198\u019c\u019d\u019f\u01a0\u01a2\u01a4\u01a6\u01a7\u01a9\u01ac\u01ae\u01af\u01b1\u01b2\u01b3\u01b5\u01b7\u01b8\u01bc\u01c4\u01c7\u01ca\u01cd\u01cf\u01d1\u01d3\u01d5\u01d7\u01d9\u01db\u01de\u01e0\u01e2\u01e4\u01e6\u01e8\u01ea\u01ec\u01ee\u01f1\u01f4\u01f6\u01f7\u01f8\u01fa\u01fc\u01fe\u0200\u0202\u0204\u0206\u0208\u020a\u020c\u020e\u0210\u0212\u0214\u0216\u0218\u021a\u021c\u021e\u0220\u0222\u0224\u0226\u0228\u022a\u022c\u022e\u0230\u0232\u023a\u023b\u023d\u023e\u0241\u0386\u0388\u0389\u038a\u038c\u038e\u038f\u0391\u0392\u0393\u0394\u0395\u0396\u0397\u0398\u0399\u039a\u039b\u039c\u039d\u039e\u039f\u03a0\u03a1\u03a3\u03a4\u03a5\u03a6\u03a7\u03a8\u03a9\u03aa\u03ab\u03d2\u03d3\u03d4\u03d8\u03da\u03dc\u03de\u03e0\u03e2\u03e4\u03e6\u03e8\u03ea\u03ec\u03ee\u03f4\u03f7\u03f9\u03fa\u03fd\u03fe\u03ff\u0400\u0401\u0402\u0403\u0404\u0405\u0406\u0407\u0408\u0409\u040a\u040b\u040c\u040d\u040e\u040f\u0410\u0411\u0412\u0413\u0414\u0415\u0416\u0417\u0418\u0419\u041a\u041b\u041c\u041d\u041e\u041f\u0420\u0421\u0422\u0423\u0424\u0425\u0426\u0427\u0428\u0429\u042a\u042b\u042c\u042d\u042e\u042f\u0460\u0462\u0464\u0466\u0468\u046a\u046c\u046e\u0470\u0472\u0474\u0476\u0478\u047a\u047c\u047e\u0480\u048a\u048c\u048e\u0490\u0492\u0494\u0496\u0498\u049a\u049c\u049e\u04a0\u04a2\u04a4\u04a6\u04a8\u04aa\u04ac\u04ae\u04b0\u04b2\u04b4\u04b6\u04b8\u04ba\u04bc\u04be\u04c0\u04c1\u04c3\u04c5\u04c7\u04c9\u04cb\u04cd\u04d0\u04d2\u04d4\u04d6\u04d8\u04da\u04dc\u04de\u04e0\u04e2\u04e4\u04e6\u04e8\u04ea\u04ec\u04ee\u04f0\u04f2\u04f4\u04f6\u04f8\u0500\u0502\u0504\u0506\u0508\u050a\u050c\u050e\u0531\u0532\u0533\u0534\u0535\u0536\u0537\u0538\u0539\u053a\u053b\u053c\u053d\u053e\u053f\u0540\u0541\u0542\u0543\u0544\u0545\u0546\u0547\u0548\u0549\u054a\u054b\u054c\u054d\u054e\u054f\u0550\u0551\u0552\u0553\u0554\u0555\u0556\u10a0\u10a1\u10a2\u10a3\u10a4\u10a5\u10a6\u10a7\u10a8\u10a9\u10aa\u10ab\u10ac\u10ad\u10ae\u10af\u10b0\u10b1\u10b2\u10b3\u10b4\u10b5\u10b6\u10b7\u10b8\u10b9\u10ba\u10bb\u10bc\u10bd\u10be\u10bf\u10c0\u10c1\u10c2\u10c3\u10c4\u10c5\u1e00\u1e02\u1e04\u1e06\u1e08\u1e0a\u1e0c\u1e0e\u1e10\u1e12\u1e14\u1e16\u1e18\u1e1a\u1e1c\u1e1e\u1e20\u1e22\u1e24\u1e26\u1e28\u1e2a\u1e2c\u1e2e\u1e30\u1e32\u1e34\u1e36\u1e38\u1e3a\u1e3c\u1e3e\u1e40\u1e42\u1e44\u1e46\u1e48\u1e4a\u1e4c\u1e4e\u1e50\u1e52\u1e54\u1e56\u1e58\u1e5a\u1e5c\u1e5e\u1e60\u1e62\u1e64\u1e66\u1e68\u1e6a\u1e6c\u1e6e\u1e70\u1e72\u1e74\u1e76\u1e78\u1e7a\u1e7c\u1e7e\u1e80\u1e82\u1e84\u1e86\u1e88\u1e8a\u1e8c\u1e8e\u1e90\u1e92\u1e94\u1ea0\u1ea2\u1ea4\u1ea6\u1ea8\u1eaa\u1eac\u1eae\u1eb0\u1eb2\u1eb4\u1eb6\u1eb8\u1eba\u1ebc\u1ebe\u1ec0\u1ec2\u1ec4\u1ec6\u1ec8\u1eca\u1ecc\u1ece\u1ed0\u1ed2\u1ed4\u1ed6\u1ed8\u1eda\u1edc\u1ede\u1ee0\u1ee2\u1ee4\u1ee6\u1ee8\u1eea\u1eec\u1eee\u1ef0\u1ef2\u1ef4\u1ef6\u1ef8\u1f08\u1f09\u1f0a\u1f0b\u1f0c\u1f0d\u1f0e\u1f0f\u1f18\u1f19\u1f1a\u1f1b\u1f1c\u1f1d\u1f28\u1f29\u1f2a\u1f2b\u1f2c\u1f2d\u1f2e\u1f2f\u1f38\u1f39\u1f3a\u1f3b\u1f3c\u1f3d\u1f3e\u1f3f\u1f48\u1f49\u1f4a\u1f4b\u1f4c\u1f4d\u1f59\u1f5b\u1f5d\u1f5f\u1f68\u1f69\u1f6a\u1f6b\u1f6c\u1f6d\u1f6e\u1f6f\u1fb8\u1fb9\u1fba\u1fbb\u1fc8\u1fc9\u1fca\u1fcb\u1fd8\u1fd9\u1fda\u1fdb\u1fe8\u1fe9\u1fea\u1feb\u1fec\u1ff8\u1ff9\u1ffa\u1ffb\u2102\u2107\u210b\u210c\u210d\u2110\u2111\u2112\u2115\u2119\u211a\u211b\u211c\u211d\u2124\u2126\u2128\u212a\u212b\u212c\u212d\u2130\u2131\u2133\u213e\u213f\u2145\u2c00\u2c01\u2c02\u2c03\u2c04\u2c05\u2c06\u2c07\u2c08\u2c09\u2c0a\u2c0b\u2c0c\u2c0d\u2c0e\u2c0f\u2c10\u2c11\u2c12\u2c13\u2c14\u2c15\u2c16\u2c17\u2c18\u2c19\u2c1a\u2c1b\u2c1c\u2c1d\u2c1e\u2c1f\u2c20\u2c21\u2c22\u2c23\u2c24\u2c25\u2c26\u2c27\u2c28\u2c29\u2c2a\u2c2b\u2c2c\u2c2d\u2c2e\u2c80\u2c82\u2c84\u2c86\u2c88\u2c8a\u2c8c\u2c8e\u2c90\u2c92\u2c94\u2c96\u2c98\u2c9a\u2c9c\u2c9e\u2ca0\u2ca2\u2ca4\u2ca6\u2ca8\u2caa\u2cac\u2cae\u2cb0\u2cb2\u2cb4\u2cb6\u2cb8\u2cba\u2cbc\u2cbe\u2cc0\u2cc2\u2cc4\u2cc6\u2cc8\u2cca\u2ccc\u2cce\u2cd0\u2cd2\u2cd4\u2cd6\u2cd8\u2cda\u2cdc\u2cde\u2ce0\u2ce2\uff21\uff22\uff23\uff24\uff25\uff26\uff27\uff28\uff29\uff2a\uff2b\uff2c\uff2d\uff2e\uff2f\uff30\uff31\uff32\uff33\uff34\uff35\uff36\uff37\uff38\uff39\uff3a'

Mc = u'\u0903\u093e\u093f\u0940\u0949\u094a\u094b\u094c\u0982\u0983\u09be\u09bf\u09c0\u09c7\u09c8\u09cb\u09cc\u09d7\u0a03\u0a3e\u0a3f\u0a40\u0a83\u0abe\u0abf\u0ac0\u0ac9\u0acb\u0acc\u0b02\u0b03\u0b3e\u0b40\u0b47\u0b48\u0b4b\u0b4c\u0b57\u0bbe\u0bbf\u0bc1\u0bc2\u0bc6\u0bc7\u0bc8\u0bca\u0bcb\u0bcc\u0bd7\u0c01\u0c02\u0c03\u0c41\u0c42\u0c43\u0c44\u0c82\u0c83\u0cbe\u0cc0\u0cc1\u0cc2\u0cc3\u0cc4\u0cc7\u0cc8\u0cca\u0ccb\u0cd5\u0cd6\u0d02\u0d03\u0d3e\u0d3f\u0d40\u0d46\u0d47\u0d48\u0d4a\u0d4b\u0d4c\u0d57\u0d82\u0d83\u0dcf\u0dd0\u0dd1\u0dd8\u0dd9\u0dda\u0ddb\u0ddc\u0ddd\u0dde\u0ddf\u0df2\u0df3\u0f3e\u0f3f\u0f7f\u102c\u1031\u1038\u1056\u1057\u17b6\u17be\u17bf\u17c0\u17c1\u17c2\u17c3\u17c4\u17c5\u17c7\u17c8\u1923\u1924\u1925\u1926\u1929\u192a\u192b\u1930\u1931\u1933\u1934\u1935\u1936\u1937\u1938\u19b0\u19b1\u19b2\u19b3\u19b4\u19b5\u19b6\u19b7\u19b8\u19b9\u19ba\u19bb\u19bc\u19bd\u19be\u19bf\u19c0\u19c8\u19c9\u1a19\u1a1a\u1a1b\ua802\ua823\ua824\ua827'

Me = u'\u0488\u0489\u06de\u20dd\u20de\u20df\u20e0\u20e2\u20e3\u20e4'

Mn = u'\u0300\u0301\u0302\u0303\u0304\u0305\u0306\u0307\u0308\u0309\u030a\u030b\u030c\u030d\u030e\u030f\u0310\u0311\u0312\u0313\u0314\u0315\u0316\u0317\u0318\u0319\u031a\u031b\u031c\u031d\u031e\u031f\u0320\u0321\u0322\u0323\u0324\u0325\u0326\u0327\u0328\u0329\u032a\u032b\u032c\u032d\u032e\u032f\u0330\u0331\u0332\u0333\u0334\u0335\u0336\u0337\u0338\u0339\u033a\u033b\u033c\u033d\u033e\u033f\u0340\u0341\u0342\u0343\u0344\u0345\u0346\u0347\u0348\u0349\u034a\u034b\u034c\u034d\u034e\u034f\u0350\u0351\u0352\u0353\u0354\u0355\u0356\u0357\u0358\u0359\u035a\u035b\u035c\u035d\u035e\u035f\u0360\u0361\u0362\u0363\u0364\u0365\u0366\u0367\u0368\u0369\u036a\u036b\u036c\u036d\u036e\u036f\u0483\u0484\u0485\u0486\u0591\u0592\u0593\u0594\u0595\u0596\u0597\u0598\u0599\u059a\u059b\u059c\u059d\u059e\u059f\u05a0\u05a1\u05a2\u05a3\u05a4\u05a5\u05a6\u05a7\u05a8\u05a9\u05aa\u05ab\u05ac\u05ad\u05ae\u05af\u05b0\u05b1\u05b2\u05b3\u05b4\u05b5\u05b6\u05b7\u05b8\u05b9\u05bb\u05bc\u05bd\u05bf\u05c1\u05c2\u05c4\u05c5\u05c7\u0610\u0611\u0612\u0613\u0614\u0615\u064b\u064c\u064d\u064e\u064f\u0650\u0651\u0652\u0653\u0654\u0655\u0656\u0657\u0658\u0659\u065a\u065b\u065c\u065d\u065e\u0670\u06d6\u06d7\u06d8\u06d9\u06da\u06db\u06dc\u06df\u06e0\u06e1\u06e2\u06e3\u06e4\u06e7\u06e8\u06ea\u06eb\u06ec\u06ed\u0711\u0730\u0731\u0732\u0733\u0734\u0735\u0736\u0737\u0738\u0739\u073a\u073b\u073c\u073d\u073e\u073f\u0740\u0741\u0742\u0743\u0744\u0745\u0746\u0747\u0748\u0749\u074a\u07a6\u07a7\u07a8\u07a9\u07aa\u07ab\u07ac\u07ad\u07ae\u07af\u07b0\u0901\u0902\u093c\u0941\u0942\u0943\u0944\u0945\u0946\u0947\u0948\u094d\u0951\u0952\u0953\u0954\u0962\u0963\u0981\u09bc\u09c1\u09c2\u09c3\u09c4\u09cd\u09e2\u09e3\u0a01\u0a02\u0a3c\u0a41\u0a42\u0a47\u0a48\u0a4b\u0a4c\u0a4d\u0a70\u0a71\u0a81\u0a82\u0abc\u0ac1\u0ac2\u0ac3\u0ac4\u0ac5\u0ac7\u0ac8\u0acd\u0ae2\u0ae3\u0b01\u0b3c\u0b3f\u0b41\u0b42\u0b43\u0b4d\u0b56\u0b82\u0bc0\u0bcd\u0c3e\u0c3f\u0c40\u0c46\u0c47\u0c48\u0c4a\u0c4b\u0c4c\u0c4d\u0c55\u0c56\u0cbc\u0cbf\u0cc6\u0ccc\u0ccd\u0d41\u0d42\u0d43\u0d4d\u0dca\u0dd2\u0dd3\u0dd4\u0dd6\u0e31\u0e34\u0e35\u0e36\u0e37\u0e38\u0e39\u0e3a\u0e47\u0e48\u0e49\u0e4a\u0e4b\u0e4c\u0e4d\u0e4e\u0eb1\u0eb4\u0eb5\u0eb6\u0eb7\u0eb8\u0eb9\u0ebb\u0ebc\u0ec8\u0ec9\u0eca\u0ecb\u0ecc\u0ecd\u0f18\u0f19\u0f35\u0f37\u0f39\u0f71\u0f72\u0f73\u0f74\u0f75\u0f76\u0f77\u0f78\u0f79\u0f7a\u0f7b\u0f7c\u0f7d\u0f7e\u0f80\u0f81\u0f82\u0f83\u0f84\u0f86\u0f87\u0f90\u0f91\u0f92\u0f93\u0f94\u0f95\u0f96\u0f97\u0f99\u0f9a\u0f9b\u0f9c\u0f9d\u0f9e\u0f9f\u0fa0\u0fa1\u0fa2\u0fa3\u0fa4\u0fa5\u0fa6\u0fa7\u0fa8\u0fa9\u0faa\u0fab\u0fac\u0fad\u0fae\u0faf\u0fb0\u0fb1\u0fb2\u0fb3\u0fb4\u0fb5\u0fb6\u0fb7\u0fb8\u0fb9\u0fba\u0fbb\u0fbc\u0fc6\u102d\u102e\u102f\u1030\u1032\u1036\u1037\u1039\u1058\u1059\u135f\u1712\u1713\u1714\u1732\u1733\u1734\u1752\u1753\u1772\u1773\u17b7\u17b8\u17b9\u17ba\u17bb\u17bc\u17bd\u17c6\u17c9\u17ca\u17cb\u17cc\u17cd\u17ce\u17cf\u17d0\u17d1\u17d2\u17d3\u17dd\u180b\u180c\u180d\u18a9\u1920\u1921\u1922\u1927\u1928\u1932\u1939\u193a\u193b\u1a17\u1a18\u1dc0\u1dc1\u1dc2\u1dc3\u20d0\u20d1\u20d2\u20d3\u20d4\u20d5\u20d6\u20d7\u20d8\u20d9\u20da\u20db\u20dc\u20e1\u20e5\u20e6\u20e7\u20e8\u20e9\u20ea\u20eb\u302a\u302b\u302c\u302d\u302e\u302f\u3099\u309a\ua806\ua80b\ua825\ua826\ufb1e\ufe00\ufe01\ufe02\ufe03\ufe04\ufe05\ufe06\ufe07\ufe08\ufe09\ufe0a\ufe0b\ufe0c\ufe0d\ufe0e\ufe0f\ufe20\ufe21\ufe22\ufe23'

Nd = u'0123456789\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669\u06f0\u06f1\u06f2\u06f3\u06f4\u06f5\u06f6\u06f7\u06f8\u06f9\u0966\u0967\u0968\u0969\u096a\u096b\u096c\u096d\u096e\u096f\u09e6\u09e7\u09e8\u09e9\u09ea\u09eb\u09ec\u09ed\u09ee\u09ef\u0a66\u0a67\u0a68\u0a69\u0a6a\u0a6b\u0a6c\u0a6d\u0a6e\u0a6f\u0ae6\u0ae7\u0ae8\u0ae9\u0aea\u0aeb\u0aec\u0aed\u0aee\u0aef\u0b66\u0b67\u0b68\u0b69\u0b6a\u0b6b\u0b6c\u0b6d\u0b6e\u0b6f\u0be6\u0be7\u0be8\u0be9\u0bea\u0beb\u0bec\u0bed\u0bee\u0bef\u0c66\u0c67\u0c68\u0c69\u0c6a\u0c6b\u0c6c\u0c6d\u0c6e\u0c6f\u0ce6\u0ce7\u0ce8\u0ce9\u0cea\u0ceb\u0cec\u0ced\u0cee\u0cef\u0d66\u0d67\u0d68\u0d69\u0d6a\u0d6b\u0d6c\u0d6d\u0d6e\u0d6f\u0e50\u0e51\u0e52\u0e53\u0e54\u0e55\u0e56\u0e57\u0e58\u0e59\u0ed0\u0ed1\u0ed2\u0ed3\u0ed4\u0ed5\u0ed6\u0ed7\u0ed8\u0ed9\u0f20\u0f21\u0f22\u0f23\u0f24\u0f25\u0f26\u0f27\u0f28\u0f29\u1040\u1041\u1042\u1043\u1044\u1045\u1046\u1047\u1048\u1049\u17e0\u17e1\u17e2\u17e3\u17e4\u17e5\u17e6\u17e7\u17e8\u17e9\u1810\u1811\u1812\u1813\u1814\u1815\u1816\u1817\u1818\u1819\u1946\u1947\u1948\u1949\u194a\u194b\u194c\u194d\u194e\u194f\u19d0\u19d1\u19d2\u19d3\u19d4\u19d5\u19d6\u19d7\u19d8\u19d9\uff10\uff11\uff12\uff13\uff14\uff15\uff16\uff17\uff18\uff19'

Nl = u'\u16ee\u16ef\u16f0\u2160\u2161\u2162\u2163\u2164\u2165\u2166\u2167\u2168\u2169\u216a\u216b\u216c\u216d\u216e\u216f\u2170\u2171\u2172\u2173\u2174\u2175\u2176\u2177\u2178\u2179\u217a\u217b\u217c\u217d\u217e\u217f\u2180\u2181\u2182\u2183\u3007\u3021\u3022\u3023\u3024\u3025\u3026\u3027\u3028\u3029\u3038\u3039\u303a'

No = u'\xb2\xb3\xb9\xbc\xbd\xbe\u09f4\u09f5\u09f6\u09f7\u09f8\u09f9\u0bf0\u0bf1\u0bf2\u0f2a\u0f2b\u0f2c\u0f2d\u0f2e\u0f2f\u0f30\u0f31\u0f32\u0f33\u1369\u136a\u136b\u136c\u136d\u136e\u136f\u1370\u1371\u1372\u1373\u1374\u1375\u1376\u1377\u1378\u1379\u137a\u137b\u137c\u17f0\u17f1\u17f2\u17f3\u17f4\u17f5\u17f6\u17f7\u17f8\u17f9\u2070\u2074\u2075\u2076\u2077\u2078\u2079\u2080\u2081\u2082\u2083\u2084\u2085\u2086\u2087\u2088\u2089\u2153\u2154\u2155\u2156\u2157\u2158\u2159\u215a\u215b\u215c\u215d\u215e\u215f\u2460\u2461\u2462\u2463\u2464\u2465\u2466\u2467\u2468\u2469\u246a\u246b\u246c\u246d\u246e\u246f\u2470\u2471\u2472\u2473\u2474\u2475\u2476\u2477\u2478\u2479\u247a\u247b\u247c\u247d\u247e\u247f\u2480\u2481\u2482\u2483\u2484\u2485\u2486\u2487\u2488\u2489\u248a\u248b\u248c\u248d\u248e\u248f\u2490\u2491\u2492\u2493\u2494\u2495\u2496\u2497\u2498\u2499\u249a\u249b\u24ea\u24eb\u24ec\u24ed\u24ee\u24ef\u24f0\u24f1\u24f2\u24f3\u24f4\u24f5\u24f6\u24f7\u24f8\u24f9\u24fa\u24fb\u24fc\u24fd\u24fe\u24ff\u2776\u2777\u2778\u2779\u277a\u277b\u277c\u277d\u277e\u277f\u2780\u2781\u2782\u2783\u2784\u2785\u2786\u2787\u2788\u2789\u278a\u278b\u278c\u278d\u278e\u278f\u2790\u2791\u2792\u2793\u2cfd\u3192\u3193\u3194\u3195\u3220\u3221\u3222\u3223\u3224\u3225\u3226\u3227\u3228\u3229\u3251\u3252\u3253\u3254\u3255\u3256\u3257\u3258\u3259\u325a\u325b\u325c\u325d\u325e\u325f\u3280\u3281\u3282\u3283\u3284\u3285\u3286\u3287\u3288\u3289\u32b1\u32b2\u32b3\u32b4\u32b5\u32b6\u32b7\u32b8\u32b9\u32ba\u32bb\u32bc\u32bd\u32be\u32bf'

Pc = u'_\u203f\u2040\u2054\ufe33\ufe34\ufe4d\ufe4e\ufe4f\uff3f'

Pd = u'-\u058a\u1806\u2010\u2011\u2012\u2013\u2014\u2015\u2e17\u301c\u3030\u30a0\ufe31\ufe32\ufe58\ufe63\uff0d'

Pe = u')]}\u0f3b\u0f3d\u169c\u2046\u207e\u208e\u232a\u23b5\u2769\u276b\u276d\u276f\u2771\u2773\u2775\u27c6\u27e7\u27e9\u27eb\u2984\u2986\u2988\u298a\u298c\u298e\u2990\u2992\u2994\u2996\u2998\u29d9\u29db\u29fd\u3009\u300b\u300d\u300f\u3011\u3015\u3017\u3019\u301b\u301e\u301f\ufd3f\ufe18\ufe36\ufe38\ufe3a\ufe3c\ufe3e\ufe40\ufe42\ufe44\ufe48\ufe5a\ufe5c\ufe5e\uff09\uff3d\uff5d\uff60\uff63'

Pf = u'\xbb\u2019\u201d\u203a\u2e03\u2e05\u2e0a\u2e0d\u2e1d'

Pi = u'\xab\u2018\u201b\u201c\u201f\u2039\u2e02\u2e04\u2e09\u2e0c\u2e1c'

Po = u'!"#%&\'*,./:;?@\\\xa1\xb7\xbf\u037e\u0387\u055a\u055b\u055c\u055d\u055e\u055f\u0589\u05be\u05c0\u05c3\u05c6\u05f3\u05f4\u060c\u060d\u061b\u061e\u061f\u066a\u066b\u066c\u066d\u06d4\u0700\u0701\u0702\u0703\u0704\u0705\u0706\u0707\u0708\u0709\u070a\u070b\u070c\u070d\u0964\u0965\u0970\u0df4\u0e4f\u0e5a\u0e5b\u0f04\u0f05\u0f06\u0f07\u0f08\u0f09\u0f0a\u0f0b\u0f0c\u0f0d\u0f0e\u0f0f\u0f10\u0f11\u0f12\u0f85\u0fd0\u0fd1\u104a\u104b\u104c\u104d\u104e\u104f\u10fb\u1361\u1362\u1363\u1364\u1365\u1366\u1367\u1368\u166d\u166e\u16eb\u16ec\u16ed\u1735\u1736\u17d4\u17d5\u17d6\u17d8\u17d9\u17da\u1800\u1801\u1802\u1803\u1804\u1805\u1807\u1808\u1809\u180a\u1944\u1945\u19de\u19df\u1a1e\u1a1f\u2016\u2017\u2020\u2021\u2022\u2023\u2024\u2025\u2026\u2027\u2030\u2031\u2032\u2033\u2034\u2035\u2036\u2037\u2038\u203b\u203c\u203d\u203e\u2041\u2042\u2043\u2047\u2048\u2049\u204a\u204b\u204c\u204d\u204e\u204f\u2050\u2051\u2053\u2055\u2056\u2057\u2058\u2059\u205a\u205b\u205c\u205d\u205e\u23b6\u2cf9\u2cfa\u2cfb\u2cfc\u2cfe\u2cff\u2e00\u2e01\u2e06\u2e07\u2e08\u2e0b\u2e0e\u2e0f\u2e10\u2e11\u2e12\u2e13\u2e14\u2e15\u2e16\u3001\u3002\u3003\u303d\u30fb\ufe10\ufe11\ufe12\ufe13\ufe14\ufe15\ufe16\ufe19\ufe30\ufe45\ufe46\ufe49\ufe4a\ufe4b\ufe4c\ufe50\ufe51\ufe52\ufe54\ufe55\ufe56\ufe57\ufe5f\ufe60\ufe61\ufe68\ufe6a\ufe6b\uff01\uff02\uff03\uff05\uff06\uff07\uff0a\uff0c\uff0e\uff0f\uff1a\uff1b\uff1f\uff20\uff3c\uff61\uff64\uff65'

Ps = u'([{\u0f3a\u0f3c\u169b\u201a\u201e\u2045\u207d\u208d\u2329\u23b4\u2768\u276a\u276c\u276e\u2770\u2772\u2774\u27c5\u27e6\u27e8\u27ea\u2983\u2985\u2987\u2989\u298b\u298d\u298f\u2991\u2993\u2995\u2997\u29d8\u29da\u29fc\u3008\u300a\u300c\u300e\u3010\u3014\u3016\u3018\u301a\u301d\ufd3e\ufe17\ufe35\ufe37\ufe39\ufe3b\ufe3d\ufe3f\ufe41\ufe43\ufe47\ufe59\ufe5b\ufe5d\uff08\uff3b\uff5b\uff5f\uff62'

Sc = u'$\xa2\xa3\xa4\xa5\u060b\u09f2\u09f3\u0af1\u0bf9\u0e3f\u17db\u20a0\u20a1\u20a2\u20a3\u20a4\u20a5\u20a6\u20a7\u20a8\u20a9\u20aa\u20ab\u20ac\u20ad\u20ae\u20af\u20b0\u20b1\u20b2\u20b3\u20b4\u20b5\ufdfc\ufe69\uff04\uffe0\uffe1\uffe5\uffe6'

Sk = u'^`\xa8\xaf\xb4\xb8\u02c2\u02c3\u02c4\u02c5\u02d2\u02d3\u02d4\u02d5\u02d6\u02d7\u02d8\u02d9\u02da\u02db\u02dc\u02dd\u02de\u02df\u02e5\u02e6\u02e7\u02e8\u02e9\u02ea\u02eb\u02ec\u02ed\u02ef\u02f0\u02f1\u02f2\u02f3\u02f4\u02f5\u02f6\u02f7\u02f8\u02f9\u02fa\u02fb\u02fc\u02fd\u02fe\u02ff\u0374\u0375\u0384\u0385\u1fbd\u1fbf\u1fc0\u1fc1\u1fcd\u1fce\u1fcf\u1fdd\u1fde\u1fdf\u1fed\u1fee\u1fef\u1ffd\u1ffe\u309b\u309c\ua700\ua701\ua702\ua703\ua704\ua705\ua706\ua707\ua708\ua709\ua70a\ua70b\ua70c\ua70d\ua70e\ua70f\ua710\ua711\ua712\ua713\ua714\ua715\ua716\uff3e\uff40\uffe3'

Sm = u'+<=>|~\xac\xb1\xd7\xf7\u03f6\u2044\u2052\u207a\u207b\u207c\u208a\u208b\u208c\u2140\u2141\u2142\u2143\u2144\u214b\u2190\u2191\u2192\u2193\u2194\u219a\u219b\u21a0\u21a3\u21a6\u21ae\u21ce\u21cf\u21d2\u21d4\u21f4\u21f5\u21f6\u21f7\u21f8\u21f9\u21fa\u21fb\u21fc\u21fd\u21fe\u21ff\u2200\u2201\u2202\u2203\u2204\u2205\u2206\u2207\u2208\u2209\u220a\u220b\u220c\u220d\u220e\u220f\u2210\u2211\u2212\u2213\u2214\u2215\u2216\u2217\u2218\u2219\u221a\u221b\u221c\u221d\u221e\u221f\u2220\u2221\u2222\u2223\u2224\u2225\u2226\u2227\u2228\u2229\u222a\u222b\u222c\u222d\u222e\u222f\u2230\u2231\u2232\u2233\u2234\u2235\u2236\u2237\u2238\u2239\u223a\u223b\u223c\u223d\u223e\u223f\u2240\u2241\u2242\u2243\u2244\u2245\u2246\u2247\u2248\u2249\u224a\u224b\u224c\u224d\u224e\u224f\u2250\u2251\u2252\u2253\u2254\u2255\u2256\u2257\u2258\u2259\u225a\u225b\u225c\u225d\u225e\u225f\u2260\u2261\u2262\u2263\u2264\u2265\u2266\u2267\u2268\u2269\u226a\u226b\u226c\u226d\u226e\u226f\u2270\u2271\u2272\u2273\u2274\u2275\u2276\u2277\u2278\u2279\u227a\u227b\u227c\u227d\u227e\u227f\u2280\u2281\u2282\u2283\u2284\u2285\u2286\u2287\u2288\u2289\u228a\u228b\u228c\u228d\u228e\u228f\u2290\u2291\u2292\u2293\u2294\u2295\u2296\u2297\u2298\u2299\u229a\u229b\u229c\u229d\u229e\u229f\u22a0\u22a1\u22a2\u22a3\u22a4\u22a5\u22a6\u22a7\u22a8\u22a9\u22aa\u22ab\u22ac\u22ad\u22ae\u22af\u22b0\u22b1\u22b2\u22b3\u22b4\u22b5\u22b6\u22b7\u22b8\u22b9\u22ba\u22bb\u22bc\u22bd\u22be\u22bf\u22c0\u22c1\u22c2\u22c3\u22c4\u22c5\u22c6\u22c7\u22c8\u22c9\u22ca\u22cb\u22cc\u22cd\u22ce\u22cf\u22d0\u22d1\u22d2\u22d3\u22d4\u22d5\u22d6\u22d7\u22d8\u22d9\u22da\u22db\u22dc\u22dd\u22de\u22df\u22e0\u22e1\u22e2\u22e3\u22e4\u22e5\u22e6\u22e7\u22e8\u22e9\u22ea\u22eb\u22ec\u22ed\u22ee\u22ef\u22f0\u22f1\u22f2\u22f3\u22f4\u22f5\u22f6\u22f7\u22f8\u22f9\u22fa\u22fb\u22fc\u22fd\u22fe\u22ff\u2308\u2309\u230a\u230b\u2320\u2321\u237c\u239b\u239c\u239d\u239e\u239f\u23a0\u23a1\u23a2\u23a3\u23a4\u23a5\u23a6\u23a7\u23a8\u23a9\u23aa\u23ab\u23ac\u23ad\u23ae\u23af\u23b0\u23b1\u23b2\u23b3\u25b7\u25c1\u25f8\u25f9\u25fa\u25fb\u25fc\u25fd\u25fe\u25ff\u266f\u27c0\u27c1\u27c2\u27c3\u27c4\u27d0\u27d1\u27d2\u27d3\u27d4\u27d5\u27d6\u27d7\u27d8\u27d9\u27da\u27db\u27dc\u27dd\u27de\u27df\u27e0\u27e1\u27e2\u27e3\u27e4\u27e5\u27f0\u27f1\u27f2\u27f3\u27f4\u27f5\u27f6\u27f7\u27f8\u27f9\u27fa\u27fb\u27fc\u27fd\u27fe\u27ff\u2900\u2901\u2902\u2903\u2904\u2905\u2906\u2907\u2908\u2909\u290a\u290b\u290c\u290d\u290e\u290f\u2910\u2911\u2912\u2913\u2914\u2915\u2916\u2917\u2918\u2919\u291a\u291b\u291c\u291d\u291e\u291f\u2920\u2921\u2922\u2923\u2924\u2925\u2926\u2927\u2928\u2929\u292a\u292b\u292c\u292d\u292e\u292f\u2930\u2931\u2932\u2933\u2934\u2935\u2936\u2937\u2938\u2939\u293a\u293b\u293c\u293d\u293e\u293f\u2940\u2941\u2942\u2943\u2944\u2945\u2946\u2947\u2948\u2949\u294a\u294b\u294c\u294d\u294e\u294f\u2950\u2951\u2952\u2953\u2954\u2955\u2956\u2957\u2958\u2959\u295a\u295b\u295c\u295d\u295e\u295f\u2960\u2961\u2962\u2963\u2964\u2965\u2966\u2967\u2968\u2969\u296a\u296b\u296c\u296d\u296e\u296f\u2970\u2971\u2972\u2973\u2974\u2975\u2976\u2977\u2978\u2979\u297a\u297b\u297c\u297d\u297e\u297f\u2980\u2981\u2982\u2999\u299a\u299b\u299c\u299d\u299e\u299f\u29a0\u29a1\u29a2\u29a3\u29a4\u29a5\u29a6\u29a7\u29a8\u29a9\u29aa\u29ab\u29ac\u29ad\u29ae\u29af\u29b0\u29b1\u29b2\u29b3\u29b4\u29b5\u29b6\u29b7\u29b8\u29b9\u29ba\u29bb\u29bc\u29bd\u29be\u29bf\u29c0\u29c1\u29c2\u29c3\u29c4\u29c5\u29c6\u29c7\u29c8\u29c9\u29ca\u29cb\u29cc\u29cd\u29ce\u29cf\u29d0\u29d1\u29d2\u29d3\u29d4\u29d5\u29d6\u29d7\u29dc\u29dd\u29de\u29df\u29e0\u29e1\u29e2\u29e3\u29e4\u29e5\u29e6\u29e7\u29e8\u29e9\u29ea\u29eb\u29ec\u29ed\u29ee\u29ef\u29f0\u29f1\u29f2\u29f3\u29f4\u29f5\u29f6\u29f7\u29f8\u29f9\u29fa\u29fb\u29fe\u29ff\u2a00\u2a01\u2a02\u2a03\u2a04\u2a05\u2a06\u2a07\u2a08\u2a09\u2a0a\u2a0b\u2a0c\u2a0d\u2a0e\u2a0f\u2a10\u2a11\u2a12\u2a13\u2a14\u2a15\u2a16\u2a17\u2a18\u2a19\u2a1a\u2a1b\u2a1c\u2a1d\u2a1e\u2a1f\u2a20\u2a21\u2a22\u2a23\u2a24\u2a25\u2a26\u2a27\u2a28\u2a29\u2a2a\u2a2b\u2a2c\u2a2d\u2a2e\u2a2f\u2a30\u2a31\u2a32\u2a33\u2a34\u2a35\u2a36\u2a37\u2a38\u2a39\u2a3a\u2a3b\u2a3c\u2a3d\u2a3e\u2a3f\u2a40\u2a41\u2a42\u2a43\u2a44\u2a45\u2a46\u2a47\u2a48\u2a49\u2a4a\u2a4b\u2a4c\u2a4d\u2a4e\u2a4f\u2a50\u2a51\u2a52\u2a53\u2a54\u2a55\u2a56\u2a57\u2a58\u2a59\u2a5a\u2a5b\u2a5c\u2a5d\u2a5e\u2a5f\u2a60\u2a61\u2a62\u2a63\u2a64\u2a65\u2a66\u2a67\u2a68\u2a69\u2a6a\u2a6b\u2a6c\u2a6d\u2a6e\u2a6f\u2a70\u2a71\u2a72\u2a73\u2a74\u2a75\u2a76\u2a77\u2a78\u2a79\u2a7a\u2a7b\u2a7c\u2a7d\u2a7e\u2a7f\u2a80\u2a81\u2a82\u2a83\u2a84\u2a85\u2a86\u2a87\u2a88\u2a89\u2a8a\u2a8b\u2a8c\u2a8d\u2a8e\u2a8f\u2a90\u2a91\u2a92\u2a93\u2a94\u2a95\u2a96\u2a97\u2a98\u2a99\u2a9a\u2a9b\u2a9c\u2a9d\u2a9e\u2a9f\u2aa0\u2aa1\u2aa2\u2aa3\u2aa4\u2aa5\u2aa6\u2aa7\u2aa8\u2aa9\u2aaa\u2aab\u2aac\u2aad\u2aae\u2aaf\u2ab0\u2ab1\u2ab2\u2ab3\u2ab4\u2ab5\u2ab6\u2ab7\u2ab8\u2ab9\u2aba\u2abb\u2abc\u2abd\u2abe\u2abf\u2ac0\u2ac1\u2ac2\u2ac3\u2ac4\u2ac5\u2ac6\u2ac7\u2ac8\u2ac9\u2aca\u2acb\u2acc\u2acd\u2ace\u2acf\u2ad0\u2ad1\u2ad2\u2ad3\u2ad4\u2ad5\u2ad6\u2ad7\u2ad8\u2ad9\u2ada\u2adb\u2adc\u2add\u2ade\u2adf\u2ae0\u2ae1\u2ae2\u2ae3\u2ae4\u2ae5\u2ae6\u2ae7\u2ae8\u2ae9\u2aea\u2aeb\u2aec\u2aed\u2aee\u2aef\u2af0\u2af1\u2af2\u2af3\u2af4\u2af5\u2af6\u2af7\u2af8\u2af9\u2afa\u2afb\u2afc\u2afd\u2afe\u2aff\ufb29\ufe62\ufe64\ufe65\ufe66\uff0b\uff1c\uff1d\uff1e\uff5c\uff5e\uffe2\uffe9\uffea\uffeb\uffec'

So = u'\xa6\xa7\xa9\xae\xb0\xb6\u0482\u060e\u060f\u06e9\u06fd\u06fe\u09fa\u0b70\u0bf3\u0bf4\u0bf5\u0bf6\u0bf7\u0bf8\u0bfa\u0f01\u0f02\u0f03\u0f13\u0f14\u0f15\u0f16\u0f17\u0f1a\u0f1b\u0f1c\u0f1d\u0f1e\u0f1f\u0f34\u0f36\u0f38\u0fbe\u0fbf\u0fc0\u0fc1\u0fc2\u0fc3\u0fc4\u0fc5\u0fc7\u0fc8\u0fc9\u0fca\u0fcb\u0fcc\u0fcf\u1360\u1390\u1391\u1392\u1393\u1394\u1395\u1396\u1397\u1398\u1399\u1940\u19e0\u19e1\u19e2\u19e3\u19e4\u19e5\u19e6\u19e7\u19e8\u19e9\u19ea\u19eb\u19ec\u19ed\u19ee\u19ef\u19f0\u19f1\u19f2\u19f3\u19f4\u19f5\u19f6\u19f7\u19f8\u19f9\u19fa\u19fb\u19fc\u19fd\u19fe\u19ff\u2100\u2101\u2103\u2104\u2105\u2106\u2108\u2109\u2114\u2116\u2117\u2118\u211e\u211f\u2120\u2121\u2122\u2123\u2125\u2127\u2129\u212e\u2132\u213a\u213b\u214a\u214c\u2195\u2196\u2197\u2198\u2199\u219c\u219d\u219e\u219f\u21a1\u21a2\u21a4\u21a5\u21a7\u21a8\u21a9\u21aa\u21ab\u21ac\u21ad\u21af\u21b0\u21b1\u21b2\u21b3\u21b4\u21b5\u21b6\u21b7\u21b8\u21b9\u21ba\u21bb\u21bc\u21bd\u21be\u21bf\u21c0\u21c1\u21c2\u21c3\u21c4\u21c5\u21c6\u21c7\u21c8\u21c9\u21ca\u21cb\u21cc\u21cd\u21d0\u21d1\u21d3\u21d5\u21d6\u21d7\u21d8\u21d9\u21da\u21db\u21dc\u21dd\u21de\u21df\u21e0\u21e1\u21e2\u21e3\u21e4\u21e5\u21e6\u21e7\u21e8\u21e9\u21ea\u21eb\u21ec\u21ed\u21ee\u21ef\u21f0\u21f1\u21f2\u21f3\u2300\u2301\u2302\u2303\u2304\u2305\u2306\u2307\u230c\u230d\u230e\u230f\u2310\u2311\u2312\u2313\u2314\u2315\u2316\u2317\u2318\u2319\u231a\u231b\u231c\u231d\u231e\u231f\u2322\u2323\u2324\u2325\u2326\u2327\u2328\u232b\u232c\u232d\u232e\u232f\u2330\u2331\u2332\u2333\u2334\u2335\u2336\u2337\u2338\u2339\u233a\u233b\u233c\u233d\u233e\u233f\u2340\u2341\u2342\u2343\u2344\u2345\u2346\u2347\u2348\u2349\u234a\u234b\u234c\u234d\u234e\u234f\u2350\u2351\u2352\u2353\u2354\u2355\u2356\u2357\u2358\u2359\u235a\u235b\u235c\u235d\u235e\u235f\u2360\u2361\u2362\u2363\u2364\u2365\u2366\u2367\u2368\u2369\u236a\u236b\u236c\u236d\u236e\u236f\u2370\u2371\u2372\u2373\u2374\u2375\u2376\u2377\u2378\u2379\u237a\u237b\u237d\u237e\u237f\u2380\u2381\u2382\u2383\u2384\u2385\u2386\u2387\u2388\u2389\u238a\u238b\u238c\u238d\u238e\u238f\u2390\u2391\u2392\u2393\u2394\u2395\u2396\u2397\u2398\u2399\u239a\u23b7\u23b8\u23b9\u23ba\u23bb\u23bc\u23bd\u23be\u23bf\u23c0\u23c1\u23c2\u23c3\u23c4\u23c5\u23c6\u23c7\u23c8\u23c9\u23ca\u23cb\u23cc\u23cd\u23ce\u23cf\u23d0\u23d1\u23d2\u23d3\u23d4\u23d5\u23d6\u23d7\u23d8\u23d9\u23da\u23db\u2400\u2401\u2402\u2403\u2404\u2405\u2406\u2407\u2408\u2409\u240a\u240b\u240c\u240d\u240e\u240f\u2410\u2411\u2412\u2413\u2414\u2415\u2416\u2417\u2418\u2419\u241a\u241b\u241c\u241d\u241e\u241f\u2420\u2421\u2422\u2423\u2424\u2425\u2426\u2440\u2441\u2442\u2443\u2444\u2445\u2446\u2447\u2448\u2449\u244a\u249c\u249d\u249e\u249f\u24a0\u24a1\u24a2\u24a3\u24a4\u24a5\u24a6\u24a7\u24a8\u24a9\u24aa\u24ab\u24ac\u24ad\u24ae\u24af\u24b0\u24b1\u24b2\u24b3\u24b4\u24b5\u24b6\u24b7\u24b8\u24b9\u24ba\u24bb\u24bc\u24bd\u24be\u24bf\u24c0\u24c1\u24c2\u24c3\u24c4\u24c5\u24c6\u24c7\u24c8\u24c9\u24ca\u24cb\u24cc\u24cd\u24ce\u24cf\u24d0\u24d1\u24d2\u24d3\u24d4\u24d5\u24d6\u24d7\u24d8\u24d9\u24da\u24db\u24dc\u24dd\u24de\u24df\u24e0\u24e1\u24e2\u24e3\u24e4\u24e5\u24e6\u24e7\u24e8\u24e9\u2500\u2501\u2502\u2503\u2504\u2505\u2506\u2507\u2508\u2509\u250a\u250b\u250c\u250d\u250e\u250f\u2510\u2511\u2512\u2513\u2514\u2515\u2516\u2517\u2518\u2519\u251a\u251b\u251c\u251d\u251e\u251f\u2520\u2521\u2522\u2523\u2524\u2525\u2526\u2527\u2528\u2529\u252a\u252b\u252c\u252d\u252e\u252f\u2530\u2531\u2532\u2533\u2534\u2535\u2536\u2537\u2538\u2539\u253a\u253b\u253c\u253d\u253e\u253f\u2540\u2541\u2542\u2543\u2544\u2545\u2546\u2547\u2548\u2549\u254a\u254b\u254c\u254d\u254e\u254f\u2550\u2551\u2552\u2553\u2554\u2555\u2556\u2557\u2558\u2559\u255a\u255b\u255c\u255d\u255e\u255f\u2560\u2561\u2562\u2563\u2564\u2565\u2566\u2567\u2568\u2569\u256a\u256b\u256c\u256d\u256e\u256f\u2570\u2571\u2572\u2573\u2574\u2575\u2576\u2577\u2578\u2579\u257a\u257b\u257c\u257d\u257e\u257f\u2580\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588\u2589\u258a\u258b\u258c\u258d\u258e\u258f\u2590\u2591\u2592\u2593\u2594\u2595\u2596\u2597\u2598\u2599\u259a\u259b\u259c\u259d\u259e\u259f\u25a0\u25a1\u25a2\u25a3\u25a4\u25a5\u25a6\u25a7\u25a8\u25a9\u25aa\u25ab\u25ac\u25ad\u25ae\u25af\u25b0\u25b1\u25b2\u25b3\u25b4\u25b5\u25b6\u25b8\u25b9\u25ba\u25bb\u25bc\u25bd\u25be\u25bf\u25c0\u25c2\u25c3\u25c4\u25c5\u25c6\u25c7\u25c8\u25c9\u25ca\u25cb\u25cc\u25cd\u25ce\u25cf\u25d0\u25d1\u25d2\u25d3\u25d4\u25d5\u25d6\u25d7\u25d8\u25d9\u25da\u25db\u25dc\u25dd\u25de\u25df\u25e0\u25e1\u25e2\u25e3\u25e4\u25e5\u25e6\u25e7\u25e8\u25e9\u25ea\u25eb\u25ec\u25ed\u25ee\u25ef\u25f0\u25f1\u25f2\u25f3\u25f4\u25f5\u25f6\u25f7\u2600\u2601\u2602\u2603\u2604\u2605\u2606\u2607\u2608\u2609\u260a\u260b\u260c\u260d\u260e\u260f\u2610\u2611\u2612\u2613\u2614\u2615\u2616\u2617\u2618\u2619\u261a\u261b\u261c\u261d\u261e\u261f\u2620\u2621\u2622\u2623\u2624\u2625\u2626\u2627\u2628\u2629\u262a\u262b\u262c\u262d\u262e\u262f\u2630\u2631\u2632\u2633\u2634\u2635\u2636\u2637\u2638\u2639\u263a\u263b\u263c\u263d\u263e\u263f\u2640\u2641\u2642\u2643\u2644\u2645\u2646\u2647\u2648\u2649\u264a\u264b\u264c\u264d\u264e\u264f\u2650\u2651\u2652\u2653\u2654\u2655\u2656\u2657\u2658\u2659\u265a\u265b\u265c\u265d\u265e\u265f\u2660\u2661\u2662\u2663\u2664\u2665\u2666\u2667\u2668\u2669\u266a\u266b\u266c\u266d\u266e\u2670\u2671\u2672\u2673\u2674\u2675\u2676\u2677\u2678\u2679\u267a\u267b\u267c\u267d\u267e\u267f\u2680\u2681\u2682\u2683\u2684\u2685\u2686\u2687\u2688\u2689\u268a\u268b\u268c\u268d\u268e\u268f\u2690\u2691\u2692\u2693\u2694\u2695\u2696\u2697\u2698\u2699\u269a\u269b\u269c\u26a0\u26a1\u26a2\u26a3\u26a4\u26a5\u26a6\u26a7\u26a8\u26a9\u26aa\u26ab\u26ac\u26ad\u26ae\u26af\u26b0\u26b1\u2701\u2702\u2703\u2704\u2706\u2707\u2708\u2709\u270c\u270d\u270e\u270f\u2710\u2711\u2712\u2713\u2714\u2715\u2716\u2717\u2718\u2719\u271a\u271b\u271c\u271d\u271e\u271f\u2720\u2721\u2722\u2723\u2724\u2725\u2726\u2727\u2729\u272a\u272b\u272c\u272d\u272e\u272f\u2730\u2731\u2732\u2733\u2734\u2735\u2736\u2737\u2738\u2739\u273a\u273b\u273c\u273d\u273e\u273f\u2740\u2741\u2742\u2743\u2744\u2745\u2746\u2747\u2748\u2749\u274a\u274b\u274d\u274f\u2750\u2751\u2752\u2756\u2758\u2759\u275a\u275b\u275c\u275d\u275e\u2761\u2762\u2763\u2764\u2765\u2766\u2767\u2794\u2798\u2799\u279a\u279b\u279c\u279d\u279e\u279f\u27a0\u27a1\u27a2\u27a3\u27a4\u27a5\u27a6\u27a7\u27a8\u27a9\u27aa\u27ab\u27ac\u27ad\u27ae\u27af\u27b1\u27b2\u27b3\u27b4\u27b5\u27b6\u27b7\u27b8\u27b9\u27ba\u27bb\u27bc\u27bd\u27be\u2800\u2801\u2802\u2803\u2804\u2805\u2806\u2807\u2808\u2809\u280a\u280b\u280c\u280d\u280e\u280f\u2810\u2811\u2812\u2813\u2814\u2815\u2816\u2817\u2818\u2819\u281a\u281b\u281c\u281d\u281e\u281f\u2820\u2821\u2822\u2823\u2824\u2825\u2826\u2827\u2828\u2829\u282a\u282b\u282c\u282d\u282e\u282f\u2830\u2831\u2832\u2833\u2834\u2835\u2836\u2837\u2838\u2839\u283a\u283b\u283c\u283d\u283e\u283f\u2840\u2841\u2842\u2843\u2844\u2845\u2846\u2847\u2848\u2849\u284a\u284b\u284c\u284d\u284e\u284f\u2850\u2851\u2852\u2853\u2854\u2855\u2856\u2857\u2858\u2859\u285a\u285b\u285c\u285d\u285e\u285f\u2860\u2861\u2862\u2863\u2864\u2865\u2866\u2867\u2868\u2869\u286a\u286b\u286c\u286d\u286e\u286f\u2870\u2871\u2872\u2873\u2874\u2875\u2876\u2877\u2878\u2879\u287a\u287b\u287c\u287d\u287e\u287f\u2880\u2881\u2882\u2883\u2884\u2885\u2886\u2887\u2888\u2889\u288a\u288b\u288c\u288d\u288e\u288f\u2890\u2891\u2892\u2893\u2894\u2895\u2896\u2897\u2898\u2899\u289a\u289b\u289c\u289d\u289e\u289f\u28a0\u28a1\u28a2\u28a3\u28a4\u28a5\u28a6\u28a7\u28a8\u28a9\u28aa\u28ab\u28ac\u28ad\u28ae\u28af\u28b0\u28b1\u28b2\u28b3\u28b4\u28b5\u28b6\u28b7\u28b8\u28b9\u28ba\u28bb\u28bc\u28bd\u28be\u28bf\u28c0\u28c1\u28c2\u28c3\u28c4\u28c5\u28c6\u28c7\u28c8\u28c9\u28ca\u28cb\u28cc\u28cd\u28ce\u28cf\u28d0\u28d1\u28d2\u28d3\u28d4\u28d5\u28d6\u28d7\u28d8\u28d9\u28da\u28db\u28dc\u28dd\u28de\u28df\u28e0\u28e1\u28e2\u28e3\u28e4\u28e5\u28e6\u28e7\u28e8\u28e9\u28ea\u28eb\u28ec\u28ed\u28ee\u28ef\u28f0\u28f1\u28f2\u28f3\u28f4\u28f5\u28f6\u28f7\u28f8\u28f9\u28fa\u28fb\u28fc\u28fd\u28fe\u28ff\u2b00\u2b01\u2b02\u2b03\u2b04\u2b05\u2b06\u2b07\u2b08\u2b09\u2b0a\u2b0b\u2b0c\u2b0d\u2b0e\u2b0f\u2b10\u2b11\u2b12\u2b13\u2ce5\u2ce6\u2ce7\u2ce8\u2ce9\u2cea\u2e80\u2e81\u2e82\u2e83\u2e84\u2e85\u2e86\u2e87\u2e88\u2e89\u2e8a\u2e8b\u2e8c\u2e8d\u2e8e\u2e8f\u2e90\u2e91\u2e92\u2e93\u2e94\u2e95\u2e96\u2e97\u2e98\u2e99\u2e9b\u2e9c\u2e9d\u2e9e\u2e9f\u2ea0\u2ea1\u2ea2\u2ea3\u2ea4\u2ea5\u2ea6\u2ea7\u2ea8\u2ea9\u2eaa\u2eab\u2eac\u2ead\u2eae\u2eaf\u2eb0\u2eb1\u2eb2\u2eb3\u2eb4\u2eb5\u2eb6\u2eb7\u2eb8\u2eb9\u2eba\u2ebb\u2ebc\u2ebd\u2ebe\u2ebf\u2ec0\u2ec1\u2ec2\u2ec3\u2ec4\u2ec5\u2ec6\u2ec7\u2ec8\u2ec9\u2eca\u2ecb\u2ecc\u2ecd\u2ece\u2ecf\u2ed0\u2ed1\u2ed2\u2ed3\u2ed4\u2ed5\u2ed6\u2ed7\u2ed8\u2ed9\u2eda\u2edb\u2edc\u2edd\u2ede\u2edf\u2ee0\u2ee1\u2ee2\u2ee3\u2ee4\u2ee5\u2ee6\u2ee7\u2ee8\u2ee9\u2eea\u2eeb\u2eec\u2eed\u2eee\u2eef\u2ef0\u2ef1\u2ef2\u2ef3\u2f00\u2f01\u2f02\u2f03\u2f04\u2f05\u2f06\u2f07\u2f08\u2f09\u2f0a\u2f0b\u2f0c\u2f0d\u2f0e\u2f0f\u2f10\u2f11\u2f12\u2f13\u2f14\u2f15\u2f16\u2f17\u2f18\u2f19\u2f1a\u2f1b\u2f1c\u2f1d\u2f1e\u2f1f\u2f20\u2f21\u2f22\u2f23\u2f24\u2f25\u2f26\u2f27\u2f28\u2f29\u2f2a\u2f2b\u2f2c\u2f2d\u2f2e\u2f2f\u2f30\u2f31\u2f32\u2f33\u2f34\u2f35\u2f36\u2f37\u2f38\u2f39\u2f3a\u2f3b\u2f3c\u2f3d\u2f3e\u2f3f\u2f40\u2f41\u2f42\u2f43\u2f44\u2f45\u2f46\u2f47\u2f48\u2f49\u2f4a\u2f4b\u2f4c\u2f4d\u2f4e\u2f4f\u2f50\u2f51\u2f52\u2f53\u2f54\u2f55\u2f56\u2f57\u2f58\u2f59\u2f5a\u2f5b\u2f5c\u2f5d\u2f5e\u2f5f\u2f60\u2f61\u2f62\u2f63\u2f64\u2f65\u2f66\u2f67\u2f68\u2f69\u2f6a\u2f6b\u2f6c\u2f6d\u2f6e\u2f6f\u2f70\u2f71\u2f72\u2f73\u2f74\u2f75\u2f76\u2f77\u2f78\u2f79\u2f7a\u2f7b\u2f7c\u2f7d\u2f7e\u2f7f\u2f80\u2f81\u2f82\u2f83\u2f84\u2f85\u2f86\u2f87\u2f88\u2f89\u2f8a\u2f8b\u2f8c\u2f8d\u2f8e\u2f8f\u2f90\u2f91\u2f92\u2f93\u2f94\u2f95\u2f96\u2f97\u2f98\u2f99\u2f9a\u2f9b\u2f9c\u2f9d\u2f9e\u2f9f\u2fa0\u2fa1\u2fa2\u2fa3\u2fa4\u2fa5\u2fa6\u2fa7\u2fa8\u2fa9\u2faa\u2fab\u2fac\u2fad\u2fae\u2faf\u2fb0\u2fb1\u2fb2\u2fb3\u2fb4\u2fb5\u2fb6\u2fb7\u2fb8\u2fb9\u2fba\u2fbb\u2fbc\u2fbd\u2fbe\u2fbf\u2fc0\u2fc1\u2fc2\u2fc3\u2fc4\u2fc5\u2fc6\u2fc7\u2fc8\u2fc9\u2fca\u2fcb\u2fcc\u2fcd\u2fce\u2fcf\u2fd0\u2fd1\u2fd2\u2fd3\u2fd4\u2fd5\u2ff0\u2ff1\u2ff2\u2ff3\u2ff4\u2ff5\u2ff6\u2ff7\u2ff8\u2ff9\u2ffa\u2ffb\u3004\u3012\u3013\u3020\u3036\u3037\u303e\u303f\u3190\u3191\u3196\u3197\u3198\u3199\u319a\u319b\u319c\u319d\u319e\u319f\u31c0\u31c1\u31c2\u31c3\u31c4\u31c5\u31c6\u31c7\u31c8\u31c9\u31ca\u31cb\u31cc\u31cd\u31ce\u31cf\u3200\u3201\u3202\u3203\u3204\u3205\u3206\u3207\u3208\u3209\u320a\u320b\u320c\u320d\u320e\u320f\u3210\u3211\u3212\u3213\u3214\u3215\u3216\u3217\u3218\u3219\u321a\u321b\u321c\u321d\u321e\u322a\u322b\u322c\u322d\u322e\u322f\u3230\u3231\u3232\u3233\u3234\u3235\u3236\u3237\u3238\u3239\u323a\u323b\u323c\u323d\u323e\u323f\u3240\u3241\u3242\u3243\u3250\u3260\u3261\u3262\u3263\u3264\u3265\u3266\u3267\u3268\u3269\u326a\u326b\u326c\u326d\u326e\u326f\u3270\u3271\u3272\u3273\u3274\u3275\u3276\u3277\u3278\u3279\u327a\u327b\u327c\u327d\u327e\u327f\u328a\u328b\u328c\u328d\u328e\u328f\u3290\u3291\u3292\u3293\u3294\u3295\u3296\u3297\u3298\u3299\u329a\u329b\u329c\u329d\u329e\u329f\u32a0\u32a1\u32a2\u32a3\u32a4\u32a5\u32a6\u32a7\u32a8\u32a9\u32aa\u32ab\u32ac\u32ad\u32ae\u32af\u32b0\u32c0\u32c1\u32c2\u32c3\u32c4\u32c5\u32c6\u32c7\u32c8\u32c9\u32ca\u32cb\u32cc\u32cd\u32ce\u32cf\u32d0\u32d1\u32d2\u32d3\u32d4\u32d5\u32d6\u32d7\u32d8\u32d9\u32da\u32db\u32dc\u32dd\u32de\u32df\u32e0\u32e1\u32e2\u32e3\u32e4\u32e5\u32e6\u32e7\u32e8\u32e9\u32ea\u32eb\u32ec\u32ed\u32ee\u32ef\u32f0\u32f1\u32f2\u32f3\u32f4\u32f5\u32f6\u32f7\u32f8\u32f9\u32fa\u32fb\u32fc\u32fd\u32fe\u3300\u3301\u3302\u3303\u3304\u3305\u3306\u3307\u3308\u3309\u330a\u330b\u330c\u330d\u330e\u330f\u3310\u3311\u3312\u3313\u3314\u3315\u3316\u3317\u3318\u3319\u331a\u331b\u331c\u331d\u331e\u331f\u3320\u3321\u3322\u3323\u3324\u3325\u3326\u3327\u3328\u3329\u332a\u332b\u332c\u332d\u332e\u332f\u3330\u3331\u3332\u3333\u3334\u3335\u3336\u3337\u3338\u3339\u333a\u333b\u333c\u333d\u333e\u333f\u3340\u3341\u3342\u3343\u3344\u3345\u3346\u3347\u3348\u3349\u334a\u334b\u334c\u334d\u334e\u334f\u3350\u3351\u3352\u3353\u3354\u3355\u3356\u3357\u3358\u3359\u335a\u335b\u335c\u335d\u335e\u335f\u3360\u3361\u3362\u3363\u3364\u3365\u3366\u3367\u3368\u3369\u336a\u336b\u336c\u336d\u336e\u336f\u3370\u3371\u3372\u3373\u3374\u3375\u3376\u3377\u3378\u3379\u337a\u337b\u337c\u337d\u337e\u337f\u3380\u3381\u3382\u3383\u3384\u3385\u3386\u3387\u3388\u3389\u338a\u338b\u338c\u338d\u338e\u338f\u3390\u3391\u3392\u3393\u3394\u3395\u3396\u3397\u3398\u3399\u339a\u339b\u339c\u339d\u339e\u339f\u33a0\u33a1\u33a2\u33a3\u33a4\u33a5\u33a6\u33a7\u33a8\u33a9\u33aa\u33ab\u33ac\u33ad\u33ae\u33af\u33b0\u33b1\u33b2\u33b3\u33b4\u33b5\u33b6\u33b7\u33b8\u33b9\u33ba\u33bb\u33bc\u33bd\u33be\u33bf\u33c0\u33c1\u33c2\u33c3\u33c4\u33c5\u33c6\u33c7\u33c8\u33c9\u33ca\u33cb\u33cc\u33cd\u33ce\u33cf\u33d0\u33d1\u33d2\u33d3\u33d4\u33d5\u33d6\u33d7\u33d8\u33d9\u33da\u33db\u33dc\u33dd\u33de\u33df\u33e0\u33e1\u33e2\u33e3\u33e4\u33e5\u33e6\u33e7\u33e8\u33e9\u33ea\u33eb\u33ec\u33ed\u33ee\u33ef\u33f0\u33f1\u33f2\u33f3\u33f4\u33f5\u33f6\u33f7\u33f8\u33f9\u33fa\u33fb\u33fc\u33fd\u33fe\u33ff\u4dc0\u4dc1\u4dc2\u4dc3\u4dc4\u4dc5\u4dc6\u4dc7\u4dc8\u4dc9\u4dca\u4dcb\u4dcc\u4dcd\u4dce\u4dcf\u4dd0\u4dd1\u4dd2\u4dd3\u4dd4\u4dd5\u4dd6\u4dd7\u4dd8\u4dd9\u4dda\u4ddb\u4ddc\u4ddd\u4dde\u4ddf\u4de0\u4de1\u4de2\u4de3\u4de4\u4de5\u4de6\u4de7\u4de8\u4de9\u4dea\u4deb\u4dec\u4ded\u4dee\u4def\u4df0\u4df1\u4df2\u4df3\u4df4\u4df5\u4df6\u4df7\u4df8\u4df9\u4dfa\u4dfb\u4dfc\u4dfd\u4dfe\u4dff\ua490\ua491\ua492\ua493\ua494\ua495\ua496\ua497\ua498\ua499\ua49a\ua49b\ua49c\ua49d\ua49e\ua49f\ua4a0\ua4a1\ua4a2\ua4a3\ua4a4\ua4a5\ua4a6\ua4a7\ua4a8\ua4a9\ua4aa\ua4ab\ua4ac\ua4ad\ua4ae\ua4af\ua4b0\ua4b1\ua4b2\ua4b3\ua4b4\ua4b5\ua4b6\ua4b7\ua4b8\ua4b9\ua4ba\ua4bb\ua4bc\ua4bd\ua4be\ua4bf\ua4c0\ua4c1\ua4c2\ua4c3\ua4c4\ua4c5\ua4c6\ua828\ua829\ua82a\ua82b\ufdfd\uffe4\uffe8\uffed\uffee\ufffc\ufffd'

Zl = u'\u2028'

Zp = u'\u2029'

Zs = u' \xa0\u1680\u180e\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u202f\u205f\u3000'

cats = ['Cc', 'Cf', 'Cn', 'Co', 'Cs', 'Ll', 'Lm', 'Lo', 'Lt', 'Lu', 'Mc', 'Me', 'Mn', 'Nd', 'Nl', 'No', 'Pc', 'Pd', 'Pe', 'Pf', 'Pi', 'Po', 'Ps', 'Sc', 'Sk', 'Sm', 'So', 'Zl', 'Zp', 'Zs']

def combine(*args):
    return u''.join([globals()[cat] for cat in args])

xid_start = u'\u0041-\u005A\u005F\u0061-\u007A\u00AA\u00B5\u00BA\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u01BA\u01BB\u01BC-\u01BF\u01C0-\u01C3\u01C4-\u0241\u0250-\u02AF\u02B0-\u02C1\u02C6-\u02D1\u02E0-\u02E4\u02EE\u0386\u0388-\u038A\u038C\u038E-\u03A1\u03A3-\u03CE\u03D0-\u03F5\u03F7-\u0481\u048A-\u04CE\u04D0-\u04F9\u0500-\u050F\u0531-\u0556\u0559\u0561-\u0587\u05D0-\u05EA\u05F0-\u05F2\u0621-\u063A\u0640\u0641-\u064A\u066E-\u066F\u0671-\u06D3\u06D5\u06E5-\u06E6\u06EE-\u06EF\u06FA-\u06FC\u06FF\u0710\u0712-\u072F\u074D-\u076D\u0780-\u07A5\u07B1\u0904-\u0939\u093D\u0950\u0958-\u0961\u097D\u0985-\u098C\u098F-\u0990\u0993-\u09A8\u09AA-\u09B0\u09B2\u09B6-\u09B9\u09BD\u09CE\u09DC-\u09DD\u09DF-\u09E1\u09F0-\u09F1\u0A05-\u0A0A\u0A0F-\u0A10\u0A13-\u0A28\u0A2A-\u0A30\u0A32-\u0A33\u0A35-\u0A36\u0A38-\u0A39\u0A59-\u0A5C\u0A5E\u0A72-\u0A74\u0A85-\u0A8D\u0A8F-\u0A91\u0A93-\u0AA8\u0AAA-\u0AB0\u0AB2-\u0AB3\u0AB5-\u0AB9\u0ABD\u0AD0\u0AE0-\u0AE1\u0B05-\u0B0C\u0B0F-\u0B10\u0B13-\u0B28\u0B2A-\u0B30\u0B32-\u0B33\u0B35-\u0B39\u0B3D\u0B5C-\u0B5D\u0B5F-\u0B61\u0B71\u0B83\u0B85-\u0B8A\u0B8E-\u0B90\u0B92-\u0B95\u0B99-\u0B9A\u0B9C\u0B9E-\u0B9F\u0BA3-\u0BA4\u0BA8-\u0BAA\u0BAE-\u0BB9\u0C05-\u0C0C\u0C0E-\u0C10\u0C12-\u0C28\u0C2A-\u0C33\u0C35-\u0C39\u0C60-\u0C61\u0C85-\u0C8C\u0C8E-\u0C90\u0C92-\u0CA8\u0CAA-\u0CB3\u0CB5-\u0CB9\u0CBD\u0CDE\u0CE0-\u0CE1\u0D05-\u0D0C\u0D0E-\u0D10\u0D12-\u0D28\u0D2A-\u0D39\u0D60-\u0D61\u0D85-\u0D96\u0D9A-\u0DB1\u0DB3-\u0DBB\u0DBD\u0DC0-\u0DC6\u0E01-\u0E30\u0E32\u0E40-\u0E45\u0E46\u0E81-\u0E82\u0E84\u0E87-\u0E88\u0E8A\u0E8D\u0E94-\u0E97\u0E99-\u0E9F\u0EA1-\u0EA3\u0EA5\u0EA7\u0EAA-\u0EAB\u0EAD-\u0EB0\u0EB2\u0EBD\u0EC0-\u0EC4\u0EC6\u0EDC-\u0EDD\u0F00\u0F40-\u0F47\u0F49-\u0F6A\u0F88-\u0F8B\u1000-\u1021\u1023-\u1027\u1029-\u102A\u1050-\u1055\u10A0-\u10C5\u10D0-\u10FA\u10FC\u1100-\u1159\u115F-\u11A2\u11A8-\u11F9\u1200-\u1248\u124A-\u124D\u1250-\u1256\u1258\u125A-\u125D\u1260-\u1288\u128A-\u128D\u1290-\u12B0\u12B2-\u12B5\u12B8-\u12BE\u12C0\u12C2-\u12C5\u12C8-\u12D6\u12D8-\u1310\u1312-\u1315\u1318-\u135A\u1380-\u138F\u13A0-\u13F4\u1401-\u166C\u166F-\u1676\u1681-\u169A\u16A0-\u16EA\u16EE-\u16F0\u1700-\u170C\u170E-\u1711\u1720-\u1731\u1740-\u1751\u1760-\u176C\u176E-\u1770\u1780-\u17B3\u17D7\u17DC\u1820-\u1842\u1843\u1844-\u1877\u1880-\u18A8\u1900-\u191C\u1950-\u196D\u1970-\u1974\u1980-\u19A9\u19C1-\u19C7\u1A00-\u1A16\u1D00-\u1D2B\u1D2C-\u1D61\u1D62-\u1D77\u1D78\u1D79-\u1D9A\u1D9B-\u1DBF\u1E00-\u1E9B\u1EA0-\u1EF9\u1F00-\u1F15\u1F18-\u1F1D\u1F20-\u1F45\u1F48-\u1F4D\u1F50-\u1F57\u1F59\u1F5B\u1F5D\u1F5F-\u1F7D\u1F80-\u1FB4\u1FB6-\u1FBC\u1FBE\u1FC2-\u1FC4\u1FC6-\u1FCC\u1FD0-\u1FD3\u1FD6-\u1FDB\u1FE0-\u1FEC\u1FF2-\u1FF4\u1FF6-\u1FFC\u2071\u207F\u2090-\u2094\u2102\u2107\u210A-\u2113\u2115\u2118\u2119-\u211D\u2124\u2126\u2128\u212A-\u212D\u212E\u212F-\u2131\u2133-\u2134\u2135-\u2138\u2139\u213C-\u213F\u2145-\u2149\u2160-\u2183\u2C00-\u2C2E\u2C30-\u2C5E\u2C80-\u2CE4\u2D00-\u2D25\u2D30-\u2D65\u2D6F\u2D80-\u2D96\u2DA0-\u2DA6\u2DA8-\u2DAE\u2DB0-\u2DB6\u2DB8-\u2DBE\u2DC0-\u2DC6\u2DC8-\u2DCE\u2DD0-\u2DD6\u2DD8-\u2DDE\u3005\u3006\u3007\u3021-\u3029\u3031-\u3035\u3038-\u303A\u303B\u303C\u3041-\u3096\u309D-\u309E\u309F\u30A1-\u30FA\u30FC-\u30FE\u30FF\u3105-\u312C\u3131-\u318E\u31A0-\u31B7\u31F0-\u31FF\u3400-\u4DB5\u4E00-\u9FBB\uA000-\uA014\uA015\uA016-\uA48C\uA800-\uA801\uA803-\uA805\uA807-\uA80A\uA80C-\uA822\uAC00-\uD7A3\uF900-\uFA2D\uFA30-\uFA6A\uFA70-\uFAD9\uFB00-\uFB06\uFB13-\uFB17\uFB1D\uFB1F-\uFB28\uFB2A-\uFB36\uFB38-\uFB3C\uFB3E\uFB40-\uFB41\uFB43-\uFB44\uFB46-\uFBB1\uFBD3-\uFC5D\uFC64-\uFD3D\uFD50-\uFD8F\uFD92-\uFDC7\uFDF0-\uFDF9\uFE71\uFE73\uFE77\uFE79\uFE7B\uFE7D\uFE7F-\uFEFC\uFF21-\uFF3A\uFF41-\uFF5A\uFF66-\uFF6F\uFF70\uFF71-\uFF9D\uFFA0-\uFFBE\uFFC2-\uFFC7\uFFCA-\uFFCF\uFFD2-\uFFD7\uFFDA-\uFFDC'

xid_continue = u'\u0030-\u0039\u0041-\u005A\u005F\u0061-\u007A\u00AA\u00B5\u00B7\u00BA\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u01BA\u01BB\u01BC-\u01BF\u01C0-\u01C3\u01C4-\u0241\u0250-\u02AF\u02B0-\u02C1\u02C6-\u02D1\u02E0-\u02E4\u02EE\u0300-\u036F\u0386\u0388-\u038A\u038C\u038E-\u03A1\u03A3-\u03CE\u03D0-\u03F5\u03F7-\u0481\u0483-\u0486\u048A-\u04CE\u04D0-\u04F9\u0500-\u050F\u0531-\u0556\u0559\u0561-\u0587\u0591-\u05B9\u05BB-\u05BD\u05BF\u05C1-\u05C2\u05C4-\u05C5\u05C7\u05D0-\u05EA\u05F0-\u05F2\u0610-\u0615\u0621-\u063A\u0640\u0641-\u064A\u064B-\u065E\u0660-\u0669\u066E-\u066F\u0670\u0671-\u06D3\u06D5\u06D6-\u06DC\u06DF-\u06E4\u06E5-\u06E6\u06E7-\u06E8\u06EA-\u06ED\u06EE-\u06EF\u06F0-\u06F9\u06FA-\u06FC\u06FF\u0710\u0711\u0712-\u072F\u0730-\u074A\u074D-\u076D\u0780-\u07A5\u07A6-\u07B0\u07B1\u0901-\u0902\u0903\u0904-\u0939\u093C\u093D\u093E-\u0940\u0941-\u0948\u0949-\u094C\u094D\u0950\u0951-\u0954\u0958-\u0961\u0962-\u0963\u0966-\u096F\u097D\u0981\u0982-\u0983\u0985-\u098C\u098F-\u0990\u0993-\u09A8\u09AA-\u09B0\u09B2\u09B6-\u09B9\u09BC\u09BD\u09BE-\u09C0\u09C1-\u09C4\u09C7-\u09C8\u09CB-\u09CC\u09CD\u09CE\u09D7\u09DC-\u09DD\u09DF-\u09E1\u09E2-\u09E3\u09E6-\u09EF\u09F0-\u09F1\u0A01-\u0A02\u0A03\u0A05-\u0A0A\u0A0F-\u0A10\u0A13-\u0A28\u0A2A-\u0A30\u0A32-\u0A33\u0A35-\u0A36\u0A38-\u0A39\u0A3C\u0A3E-\u0A40\u0A41-\u0A42\u0A47-\u0A48\u0A4B-\u0A4D\u0A59-\u0A5C\u0A5E\u0A66-\u0A6F\u0A70-\u0A71\u0A72-\u0A74\u0A81-\u0A82\u0A83\u0A85-\u0A8D\u0A8F-\u0A91\u0A93-\u0AA8\u0AAA-\u0AB0\u0AB2-\u0AB3\u0AB5-\u0AB9\u0ABC\u0ABD\u0ABE-\u0AC0\u0AC1-\u0AC5\u0AC7-\u0AC8\u0AC9\u0ACB-\u0ACC\u0ACD\u0AD0\u0AE0-\u0AE1\u0AE2-\u0AE3\u0AE6-\u0AEF\u0B01\u0B02-\u0B03\u0B05-\u0B0C\u0B0F-\u0B10\u0B13-\u0B28\u0B2A-\u0B30\u0B32-\u0B33\u0B35-\u0B39\u0B3C\u0B3D\u0B3E\u0B3F\u0B40\u0B41-\u0B43\u0B47-\u0B48\u0B4B-\u0B4C\u0B4D\u0B56\u0B57\u0B5C-\u0B5D\u0B5F-\u0B61\u0B66-\u0B6F\u0B71\u0B82\u0B83\u0B85-\u0B8A\u0B8E-\u0B90\u0B92-\u0B95\u0B99-\u0B9A\u0B9C\u0B9E-\u0B9F\u0BA3-\u0BA4\u0BA8-\u0BAA\u0BAE-\u0BB9\u0BBE-\u0BBF\u0BC0\u0BC1-\u0BC2\u0BC6-\u0BC8\u0BCA-\u0BCC\u0BCD\u0BD7\u0BE6-\u0BEF\u0C01-\u0C03\u0C05-\u0C0C\u0C0E-\u0C10\u0C12-\u0C28\u0C2A-\u0C33\u0C35-\u0C39\u0C3E-\u0C40\u0C41-\u0C44\u0C46-\u0C48\u0C4A-\u0C4D\u0C55-\u0C56\u0C60-\u0C61\u0C66-\u0C6F\u0C82-\u0C83\u0C85-\u0C8C\u0C8E-\u0C90\u0C92-\u0CA8\u0CAA-\u0CB3\u0CB5-\u0CB9\u0CBC\u0CBD\u0CBE\u0CBF\u0CC0-\u0CC4\u0CC6\u0CC7-\u0CC8\u0CCA-\u0CCB\u0CCC-\u0CCD\u0CD5-\u0CD6\u0CDE\u0CE0-\u0CE1\u0CE6-\u0CEF\u0D02-\u0D03\u0D05-\u0D0C\u0D0E-\u0D10\u0D12-\u0D28\u0D2A-\u0D39\u0D3E-\u0D40\u0D41-\u0D43\u0D46-\u0D48\u0D4A-\u0D4C\u0D4D\u0D57\u0D60-\u0D61\u0D66-\u0D6F\u0D82-\u0D83\u0D85-\u0D96\u0D9A-\u0DB1\u0DB3-\u0DBB\u0DBD\u0DC0-\u0DC6\u0DCA\u0DCF-\u0DD1\u0DD2-\u0DD4\u0DD6\u0DD8-\u0DDF\u0DF2-\u0DF3\u0E01-\u0E30\u0E31\u0E32-\u0E33\u0E34-\u0E3A\u0E40-\u0E45\u0E46\u0E47-\u0E4E\u0E50-\u0E59\u0E81-\u0E82\u0E84\u0E87-\u0E88\u0E8A\u0E8D\u0E94-\u0E97\u0E99-\u0E9F\u0EA1-\u0EA3\u0EA5\u0EA7\u0EAA-\u0EAB\u0EAD-\u0EB0\u0EB1\u0EB2-\u0EB3\u0EB4-\u0EB9\u0EBB-\u0EBC\u0EBD\u0EC0-\u0EC4\u0EC6\u0EC8-\u0ECD\u0ED0-\u0ED9\u0EDC-\u0EDD\u0F00\u0F18-\u0F19\u0F20-\u0F29\u0F35\u0F37\u0F39\u0F3E-\u0F3F\u0F40-\u0F47\u0F49-\u0F6A\u0F71-\u0F7E\u0F7F\u0F80-\u0F84\u0F86-\u0F87\u0F88-\u0F8B\u0F90-\u0F97\u0F99-\u0FBC\u0FC6\u1000-\u1021\u1023-\u1027\u1029-\u102A\u102C\u102D-\u1030\u1031\u1032\u1036-\u1037\u1038\u1039\u1040-\u1049\u1050-\u1055\u1056-\u1057\u1058-\u1059\u10A0-\u10C5\u10D0-\u10FA\u10FC\u1100-\u1159\u115F-\u11A2\u11A8-\u11F9\u1200-\u1248\u124A-\u124D\u1250-\u1256\u1258\u125A-\u125D\u1260-\u1288\u128A-\u128D\u1290-\u12B0\u12B2-\u12B5\u12B8-\u12BE\u12C0\u12C2-\u12C5\u12C8-\u12D6\u12D8-\u1310\u1312-\u1315\u1318-\u135A\u135F\u1369-\u1371\u1380-\u138F\u13A0-\u13F4\u1401-\u166C\u166F-\u1676\u1681-\u169A\u16A0-\u16EA\u16EE-\u16F0\u1700-\u170C\u170E-\u1711\u1712-\u1714\u1720-\u1731\u1732-\u1734\u1740-\u1751\u1752-\u1753\u1760-\u176C\u176E-\u1770\u1772-\u1773\u1780-\u17B3\u17B6\u17B7-\u17BD\u17BE-\u17C5\u17C6\u17C7-\u17C8\u17C9-\u17D3\u17D7\u17DC\u17DD\u17E0-\u17E9\u180B-\u180D\u1810-\u1819\u1820-\u1842\u1843\u1844-\u1877\u1880-\u18A8\u18A9\u1900-\u191C\u1920-\u1922\u1923-\u1926\u1927-\u1928\u1929-\u192B\u1930-\u1931\u1932\u1933-\u1938\u1939-\u193B\u1946-\u194F\u1950-\u196D\u1970-\u1974\u1980-\u19A9\u19B0-\u19C0\u19C1-\u19C7\u19C8-\u19C9\u19D0-\u19D9\u1A00-\u1A16\u1A17-\u1A18\u1A19-\u1A1B\u1D00-\u1D2B\u1D2C-\u1D61\u1D62-\u1D77\u1D78\u1D79-\u1D9A\u1D9B-\u1DBF\u1DC0-\u1DC3\u1E00-\u1E9B\u1EA0-\u1EF9\u1F00-\u1F15\u1F18-\u1F1D\u1F20-\u1F45\u1F48-\u1F4D\u1F50-\u1F57\u1F59\u1F5B\u1F5D\u1F5F-\u1F7D\u1F80-\u1FB4\u1FB6-\u1FBC\u1FBE\u1FC2-\u1FC4\u1FC6-\u1FCC\u1FD0-\u1FD3\u1FD6-\u1FDB\u1FE0-\u1FEC\u1FF2-\u1FF4\u1FF6-\u1FFC\u203F-\u2040\u2054\u2071\u207F\u2090-\u2094\u20D0-\u20DC\u20E1\u20E5-\u20EB\u2102\u2107\u210A-\u2113\u2115\u2118\u2119-\u211D\u2124\u2126\u2128\u212A-\u212D\u212E\u212F-\u2131\u2133-\u2134\u2135-\u2138\u2139\u213C-\u213F\u2145-\u2149\u2160-\u2183\u2C00-\u2C2E\u2C30-\u2C5E\u2C80-\u2CE4\u2D00-\u2D25\u2D30-\u2D65\u2D6F\u2D80-\u2D96\u2DA0-\u2DA6\u2DA8-\u2DAE\u2DB0-\u2DB6\u2DB8-\u2DBE\u2DC0-\u2DC6\u2DC8-\u2DCE\u2DD0-\u2DD6\u2DD8-\u2DDE\u3005\u3006\u3007\u3021-\u3029\u302A-\u302F\u3031-\u3035\u3038-\u303A\u303B\u303C\u3041-\u3096\u3099-\u309A\u309D-\u309E\u309F\u30A1-\u30FA\u30FC-\u30FE\u30FF\u3105-\u312C\u3131-\u318E\u31A0-\u31B7\u31F0-\u31FF\u3400-\u4DB5\u4E00-\u9FBB\uA000-\uA014\uA015\uA016-\uA48C\uA800-\uA801\uA802\uA803-\uA805\uA806\uA807-\uA80A\uA80B\uA80C-\uA822\uA823-\uA824\uA825-\uA826\uA827\uAC00-\uD7A3\uF900-\uFA2D\uFA30-\uFA6A\uFA70-\uFAD9\uFB00-\uFB06\uFB13-\uFB17\uFB1D\uFB1E\uFB1F-\uFB28\uFB2A-\uFB36\uFB38-\uFB3C\uFB3E\uFB40-\uFB41\uFB43-\uFB44\uFB46-\uFBB1\uFBD3-\uFC5D\uFC64-\uFD3D\uFD50-\uFD8F\uFD92-\uFDC7\uFDF0-\uFDF9\uFE00-\uFE0F\uFE20-\uFE23\uFE33-\uFE34\uFE4D-\uFE4F\uFE71\uFE73\uFE77\uFE79\uFE7B\uFE7D\uFE7F-\uFEFC\uFF10-\uFF19\uFF21-\uFF3A\uFF3F\uFF41-\uFF5A\uFF66-\uFF6F\uFF70\uFF71-\uFF9D\uFF9E-\uFF9F\uFFA0-\uFFBE\uFFC2-\uFFC7\uFFCA-\uFFCF\uFFD2-\uFFD7\uFFDA-\uFFDC'

def allexcept(*args):
    newcats = cats[:]
    for arg in args:
        newcats.remove(arg)
    return u''.join([globals()[cat] for cat in newcats])

if __name__ == '__main__':
    import unicodedata

    categories = {}

    f = open(__file__.rstrip('co'))
    try:
        content = f.read()
    finally:
        f.close()

    header = content[:content.find('Cc =')]
    footer = content[content.find("def combine("):]

    for code in range(65535):
        c = unichr(code)
        cat = unicodedata.category(c)
        categories.setdefault(cat, []).append(c)

    f = open(__file__, 'w')
    f.write(header)

    for cat in sorted(categories):
        val = u''.join(categories[cat])
        if cat == 'Cs':
            # Jython can't handle isolated surrogates
            f.write("""\
try:
    Cs = eval(r"%r")
except UnicodeDecodeError:
    Cs = '' # Jython can't handle isolated surrogates\n\n""" % val)
        else:
            f.write('%s = %r\n\n' % (cat, val))
    f.write('cats = %r\n\n' % sorted(categories.keys()))

    f.write(footer)
    f.close()

########NEW FILE########
__FILENAME__ = memcache
#!/usr/bin/env python
#
# Copyright 2009 Google Inc.
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
#

"""Memcache wrapper that transparently adds app version

This wraps google.appengine.api.memcache, adding a namespace
parameter to all calls that is based on the app version 
environment variable (os.environ["CURRENT_VERSION_ID"]). This
means new versions of the app will not access cached entries
from an old version, so no cache flushing is required when
changing app versions.
"""

# Pylint doesn't like the names memcache uses -- disable those warnings
# Also disabling no docstring warning
# pylint: disable-msg=C0111
# pylint: disable-msg=W0622

import os

from google.appengine.api import memcache

#
# Wrap memcache API calls with calls that set the namespace to
# the App Engine version string, obtained from the environment
# variables.
#
# These calls do not support a namespace parameter, so as not
# to confuse the user.
#
# The Client() object is not supported by this wrapper either.
#

def get(key):
  return memcache.get(key, 
    namespace=os.environ["CURRENT_VERSION_ID"])

def get_multi(keys, key_prefix=''):
  return memcache.get_multi(keys, key_prefix,
    namespace=os.environ["CURRENT_VERSION_ID"])

def delete(key, seconds=0):
  return memcache.delete(key, seconds,
    namespace=os.environ["CURRENT_VERSION_ID"])

def delete_multi(keys, seconds=0, key_prefix=''):
  return memcache.delete_multi(keys, seconds, key_prefix,
    namespace=os.environ["CURRENT_VERSION_ID"])

def set(key, value, time=0, min_compress_len=0):
  return memcache.set(key, value, time, min_compress_len,
    namespace=os.environ["CURRENT_VERSION_ID"])

def add(key, value, time=0, min_compress_len=0):
  return memcache.add(key, value, time, min_compress_len,
    namespace=os.environ["CURRENT_VERSION_ID"])

def replace(key, value, time=0, min_compress_len=0):
  return memcache.replace(key, value, time, min_compress_len,
    namespace=os.environ["CURRENT_VERSION_ID"])

def set_multi(mapping, time=0, key_prefix='', min_compress_len=0):
  return memcache.set_multi(mapping, time, key_prefix, min_compress_len,
    namespace=os.environ["CURRENT_VERSION_ID"])

def add_multi(mapping, time=0, key_prefix='', min_compress_len=0):
  return memcache.add_multi(mapping, time, key_prefix, min_compress_len,
    namespace=os.environ["CURRENT_VERSION_ID"])

def replace_multi(mapping, time=0, key_prefix='', min_compress_len=0):
  return memcache.replace_multi(mapping, time, key_prefix, min_compress_len,
    namespace=os.environ["CURRENT_VERSION_ID"])

def incr(key, delta=1, initial_value=None):
  return memcache.incr(key, delta,
    namespace=os.environ["CURRENT_VERSION_ID"],
    initial_value=initial_value)

def decr(key, delta=1, initial_value=None):
  return memcache.decr(key, delta,
    namespace=os.environ["CURRENT_VERSION_ID"],
    initial_value=initial_value)

def flush_all():
  return memcache.flush_all()

def get_stats():
  return memcache.get_stats()


########NEW FILE########
__FILENAME__ = test_cgi_escape
#!/usr/bin/env python
# vim: ft=python: set fileencoding=utf-8
import random
import unittest2
import sys;
import os;

sys.path.append( os.path.join( sys.path[0], ".." ) )
from gist_it import cgi_escape

# https://github.com/whittle/node-coffee-heroku-tutorial/blob/eb587185509ec8c2e728067d49f4ac2d5a67ec09/app.js
class t( unittest2.TestCase ):
    def runTest( self ):
        self.assertEqual( len(cgi_escape( """
(function() {
  var http = require('http');

  var say_nothing = function(request, response) {
    var message = 'مرحبا العالم';

    response.setHeader('Content-Type', 'text/plain; charset=utf-8');
    response.setHeader('X-Bad-Content-Length', message.length);
    response.setHeader('Content-Length', Buffer.byteLength(message, 'utf8'));
    response.write(message, 'utf8');
    response.end();
  };

  var app = http.createServer(say_nothing);
  app.listen(3080);
})();

""".decode('utf-8') ) ), 542 )

if __name__ == '__main__':
    unittest2.main()

########NEW FILE########
__FILENAME__ = test_footer
#!/usr/bin/env python
# vim: ft=python:
import random
import unittest2
import sys;
import os;

sys.path.append( os.path.join( sys.path[0], ".." ) )
import gist_it

class t( unittest2.TestCase ):
    def runTest( self ):
        self.assertEqual( gist_it.parse_footer( 0 ), '0' )
        self.assertEqual( gist_it.parse_footer( '0' ), '0' )
        self.assertEqual( gist_it.parse_footer( False ), '0' )
        self.assertEqual( gist_it.parse_footer( True ), '1' )
        self.assertEqual( gist_it.parse_footer( None ), '1' )
        self.assertEqual( gist_it.parse_footer( '  1' ), '1' )
        self.assertEqual( gist_it.parse_footer( 'yes  ' ), '1' )
        self.assertEqual( gist_it.parse_footer( '  no' ), '0' )
        self.assertEqual( gist_it.parse_footer( 'none ' ), '0' )
        self.assertEqual( gist_it.parse_footer( ' minimal ' ), 'minimal' )

if __name__ == '__main__':
    unittest2.main()

########NEW FILE########
__FILENAME__ = test_gist_it
#!/usr/bin/env python
# vim: ft=python:
import random
import unittest2
import sys;
import os;

sys.path.append( os.path.join( sys.path[0], ".." ) )
import gist_it

class t( unittest2.TestCase ):
    def runTest( self ):
        self.assertTrue( True, 'Xyzzy' )

        self.assertTrue( gist_it.match( 'github/robertkrimen/yzzy-projection/raw/master/src/yzzy/projection/View.as' ) )

        gist = gist_it.parse( 'github/robertkrimen/yzzy-projection/raw/master/src/yzzy/projection/View.as' )
        self.assertEqual( gist.user, 'robertkrimen' )
        self.assertEqual( gist.repository, 'yzzy-projection' )
        self.assertEqual( gist.branch, 'master' )
        self.assertEqual( gist.path, 'src/yzzy/projection/View.as' )

        self.assertEqual( gist.blob_path, 'robertkrimen/yzzy-projection/blob/master/src/yzzy/projection/View.as' )
        self.assertEqual( gist.blob_url, 'https://github.com/robertkrimen/yzzy-projection/blob/master/src/yzzy/projection/View.as' )

        self.assertEqual( gist.raw_path, 'robertkrimen/yzzy-projection/raw/master/src/yzzy/projection/View.as' )
        self.assertEqual( gist.raw_url, 'https://github.com/robertkrimen/yzzy-projection/raw/master/src/yzzy/projection/View.as' )

        self.assertEqual( gist.user_repository, 'robertkrimen/yzzy-projection' )
        self.assertEqual( gist.user_repository_branch_path, 'robertkrimen/yzzy-projection/master/src/yzzy/projection/View.as' )
        self.assertEqual( gist.user_repository_url, 'https://github.com/robertkrimen/yzzy-projection' )

        self.assertEqual( gist.start_line, 0 )
        self.assertEqual( gist.end_line, 0 )

        gist = gist_it.parse( 'github/robertkrimen/yzzy-projection/raw/master/src/yzzy/projection/View.as', slice_option = '1:' )

        self.assertEqual( gist.start_line, 1 )
        self.assertEqual( gist.end_line, 0 )

if __name__ == '__main__':
    unittest2.main()

########NEW FILE########
__FILENAME__ = test_highlight
#!/usr/bin/env python
# vim: ft=python:
import random
import unittest2
import sys;
import os;

sys.path.append( os.path.join( sys.path[0], ".." ) )
import gist_it

class t( unittest2.TestCase ):
    def runTest( self ):
        self.assertEqual( gist_it.parse_highlight( 0 ), '0' )
        self.assertEqual( gist_it.parse_highlight( '0' ), '0' )
        self.assertEqual( gist_it.parse_highlight( False ), '0' )
        self.assertEqual( gist_it.parse_highlight( True ), 'prettify' )
        self.assertEqual( gist_it.parse_highlight( None ), 'prettify' )
        self.assertEqual( gist_it.parse_highlight( '  1' ), 'prettify' )
        self.assertEqual( gist_it.parse_highlight( 'yes  ' ), 'prettify' )
        self.assertEqual( gist_it.parse_highlight( '  no' ), '0' )
        self.assertEqual( gist_it.parse_highlight( 'none ' ), '0' )
        self.assertEqual( gist_it.parse_highlight( 'deferred-prettify' ), 'deferred-prettify' )

if __name__ == '__main__':
    unittest2.main()

########NEW FILE########
__FILENAME__ = test_slice
#!/usr/bin/env python
# vim: ft=python:
import random
import unittest2
import sys;
import os;

sys.path.append( os.path.join( sys.path[0], ".." ) )
import gist_it

class t( unittest2.TestCase ):
    def runTest( self ):
        slice_ = gist_it.parse_slice( '' )
        self.assertEqual( len( slice_ ), 2 )
        self.assertEqual( slice_[0], 0 )
        self.assertEqual( slice_[1], 0 )

        slice_ = gist_it.parse_slice( '1' )
        self.assertEqual( len( slice_ ), 2 )
        self.assertEqual( slice_[0], 1 )
        self.assertEqual( slice_[1], None )

        slice_ = gist_it.parse_slice( '1:' )
        self.assertEqual( len( slice_ ), 2 )
        self.assertEqual( slice_[0], 1 )
        self.assertEqual( slice_[1], 0 )

        slice_ = gist_it.parse_slice( '1:0' )
        self.assertEqual( len( slice_ ), 2 )
        self.assertEqual( slice_[0], 1 )
        self.assertEqual( slice_[1], 0 )

        slice_ = gist_it.parse_slice( ':1' )
        self.assertEqual( len( slice_ ), 2 )
        self.assertEqual( slice_[0], 0 )
        self.assertEqual( slice_[1], 1 )

        slice_ = gist_it.parse_slice( '0:1' )
        self.assertEqual( len( slice_ ), 2 )
        self.assertEqual( slice_[0], 0 )
        self.assertEqual( slice_[1], 1 )

        slice_ = gist_it.parse_slice( '1:1' )
        self.assertEqual( len( slice_ ), 2 )
        self.assertEqual( slice_[0], 1 )
        self.assertEqual( slice_[1], 1 )

        slice_ = gist_it.parse_slice( ':' )
        self.assertEqual( len( slice_ ), 2 )
        self.assertEqual( slice_[0], 0 )
        self.assertEqual( slice_[1], 0 )

        slice_ = gist_it.parse_slice( '-0:-0' )
        self.assertEqual( len( slice_ ), 2 )
        self.assertEqual( slice_[0], 0 )
        self.assertEqual( slice_[1], 0 )

        slice_ = gist_it.parse_slice( '-1:' )
        self.assertEqual( len( slice_ ), 2 )
        self.assertEqual( slice_[0], -1 )
        self.assertEqual( slice_[1], 0 )

        content = """
Line 2
Line 3
Line 4
Line 5
Line 6

Line 8
"""
        self.assertEqual( gist_it.take_slice( content, 0, 0 ), content )
        self.assertEqual( gist_it.take_slice( content, 1, 2 ), "Line 2\nLine 3" )
        self.assertEqual( gist_it.take_slice( content, 1, None ), "Line 2" )
        self.assertEqual( gist_it.take_slice( content, 0, 2 ), "\nLine 2\nLine 3" )
        self.assertEqual( gist_it.take_slice( content, 0, -1 ), """
Line 2
Line 3
Line 4
Line 5
Line 6
""" )
        self.assertEqual( gist_it.take_slice( content, -1, 0 ), "Line 8" )

if __name__ == '__main__':
    unittest2.main()

########NEW FILE########
__FILENAME__ = test_style
#!/usr/bin/env python
# vim: ft=python:
import random
import unittest2
import sys;
import os;

sys.path.append( os.path.join( sys.path[0], ".." ) )
import gist_it

class t( unittest2.TestCase ):
    def runTest( self ):
        self.assertEqual( gist_it.parse_style( 0 ), '0' )
        self.assertEqual( gist_it.parse_style( '0' ), '0' )
        self.assertEqual( gist_it.parse_style( False ), '0' )
        self.assertEqual( gist_it.parse_style( True ), '1' )
        self.assertEqual( gist_it.parse_style( None ), '1' )
        self.assertEqual( gist_it.parse_style( '  1' ), '1' )
        self.assertEqual( gist_it.parse_style( 'yes  ' ), '1' )
        self.assertEqual( gist_it.parse_style( '  no' ), '0' )
        self.assertEqual( gist_it.parse_style( 'none ' ), '0' )

if __name__ == '__main__':
    unittest2.main()

########NEW FILE########
