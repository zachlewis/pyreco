__FILENAME__ = conf
# -*- coding: utf-8 -*-
#
# Django Ratelimit documentation build configuration file, created by
# sphinx-quickstart on Fri Jan  4 15:55:31 2013.
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

# -- General configuration -----------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be extensions
# coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
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
project = u'Django Ratelimit'
copyright = u'2013, James Socol'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = '0.3'
# The full version, including alpha/beta/rc tags.
release = '0.3.0'

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
htmlhelp_basename = 'DjangoRatelimitdoc'


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
  ('index', 'DjangoRatelimit.tex', u'Django Ratelimit Documentation',
   u'James Socol', 'manual'),
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
    ('index', 'djangoratelimit', u'Django Ratelimit Documentation',
     [u'James Socol'], 1)
]

# If true, show URL addresses after external links.
#man_show_urls = False


# -- Options for Texinfo output ------------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
  ('index', 'DjangoRatelimit', u'Django Ratelimit Documentation',
   u'James Socol', 'DjangoRatelimit', 'One line description of project.',
   'Miscellaneous'),
]

# Documents to append as an appendix to all manuals.
#texinfo_appendices = []

# If false, no module index is generated.
#texinfo_domain_indices = True

# How to display URL addresses: 'footnote', 'no', or 'inline'.
#texinfo_show_urls = 'footnote'

########NEW FILE########
__FILENAME__ = decorators
from functools import wraps

from ratelimit.exceptions import Ratelimited
from ratelimit.helpers import is_ratelimited


__all__ = ['ratelimit']


def ratelimit(ip=True, block=False, method=['POST'], field=None, rate='5/m',
              skip_if=None, keys=None):
    def decorator(fn):
        @wraps(fn)
        def _wrapped(request, *args, **kw):
            request.limited = getattr(request, 'limited', False)
            if skip_if is None or not skip_if(request):
                ratelimited = is_ratelimited(request=request, increment=True,
                                             ip=ip, method=method, field=field,
                                             rate=rate, keys=keys)
                if ratelimited and block:
                    raise Ratelimited()
            return fn(request, *args, **kw)
        return _wrapped
    return decorator

########NEW FILE########
__FILENAME__ = exceptions
from django.core.exceptions import PermissionDenied


class Ratelimited(PermissionDenied):
    pass

########NEW FILE########
__FILENAME__ = helpers
import hashlib
import re

from django.conf import settings
from django.core.cache import get_cache


__all__ = ['is_ratelimited']

_PERIODS = {
    's': 1,
    'm': 60,
    'h': 60 * 60,
    'd': 24 * 60 * 60,
}

rate_re = re.compile('([\d]+)/([\d]*)([smhd])')


def _method_match(request, method=None):
    if method is None:
        return True
    if not isinstance(method, (list, tuple)):
        method = [method]
    return request.method in [m.upper() for m in method]


def _split_rate(rate):
    count, multi, period = rate_re.match(rate).groups()
    count = int(count)
    time = _PERIODS[period.lower()]
    if multi:
        time = time * int(multi)
    return count, time


def _get_keys(request, ip=True, field=None, keyfuncs=None):
    keys = []
    if ip:
        keys.append('ip:' + request.META['REMOTE_ADDR'])
    if field is not None:
        if not isinstance(field, (list, tuple)):
            field = [field]
        for f in field:
            val = getattr(request, request.method).get(f, '').encode('utf-8')
            val = hashlib.sha1(val).hexdigest()
            keys.append(u'field:%s:%s' % (f, val))
    if keyfuncs:
        if not isinstance(keyfuncs, (list, tuple)):
            keyfuncs = [keyfuncs]
        for k in keyfuncs:
            keys.append(k(request))
    prefix = getattr(settings, 'CACHE_PREFIX', 'rl:')
    return [prefix + k for k in keys]


def _incr(cache, keys, timeout=60):
    # Yes, this is a race condition, but memcached.incr doesn't reset the
    # timeout.
    counts = cache.get_many(keys)
    for key in keys:
        if key in counts:
            counts[key] += 1
        else:
            counts[key] = 1
    cache.set_many(counts, timeout=timeout)
    return counts


def _get(cache, keys):
    counts = cache.get_many(keys)
    for key in keys:
        if key in counts:
            counts[key] += 1
        else:
            counts[key] = 1
    return counts


def is_ratelimited(request, increment=False, ip=True, method=['POST'],
                   field=None, rate='5/m', keys=None):
    count, period = _split_rate(rate)
    cache = getattr(settings, 'RATELIMIT_USE_CACHE', 'default')
    cache = get_cache(cache)

    request.limited = getattr(request, 'limited', False)
    if (not request.limited
            and getattr(settings, 'RATELIMIT_ENABLE', True)
            and _method_match(request, method)):
        _keys = _get_keys(request, ip, field, keys)
        if increment:
            counts = _incr(cache, _keys, period)
        else:
            counts = _get(cache, _keys)
        if any([c > count for c in counts.values()]):
            request.limited = True

    return request.limited

########NEW FILE########
__FILENAME__ = middleware
from django.conf import settings
from django.utils.importlib import import_module

from ratelimit.exceptions import Ratelimited


class RatelimitMiddleware(object):
    def process_exception(self, request, exception):
        if not isinstance(exception, Ratelimited):
            return
        module_name, _, view_name = settings.RATELIMIT_VIEW.rpartition('.')
        module = import_module(module_name)
        view = getattr(module, view_name)
        return view(request, exception)

########NEW FILE########
__FILENAME__ = mixins
# -*- coding: utf-8 -*-

from .decorators import ratelimit


class RateLimitMixin(object):
    """
    Mixin for usage in Class Based Views
    configured with the decorator ``ratelimit`` defaults.

    Configure the class-attributes prefixed with ``ratelimit_``
    for customization of the ratelimit process.

    Example::

        class ContactView(RateLimitMixin, FormView):
            form_class = ContactForm
            template_name = "contact.html"

            ratelimit_block = True

            def form_valid(self, form):
                # do sth. here
                return super(ContactView, self).form_valid(form)

    """
    ratelimit_ip = True
    ratelimit_block = False
    ratelimit_method = ['POST']
    ratelimit_field = None
    ratelimit_rate = '5/m'
    ratelimit_skip_if = None
    ratelimit_keys = None

    def get_ratelimit_config(self):
        return dict(
            (k[len("ratelimit_"):], v)
            for k, v in vars(self.__class__).items()
            if k.startswith("ratelimit")
        )

    def dispatch(self, *args, **kwargs):
        return ratelimit(
            **self.get_ratelimit_config()
        )(super(RateLimitMixin, self).dispatch)(*args, **kwargs)

########NEW FILE########
__FILENAME__ = models
# This module intentionally left blank.

########NEW FILE########
__FILENAME__ = tests
import django
from django.core.cache import cache, InvalidCacheBackendError
from django.test import RequestFactory, TestCase
from django.test.utils import override_settings
from django.views.generic import View

from ratelimit.decorators import ratelimit
from ratelimit.exceptions import Ratelimited
from ratelimit.mixins import RateLimitMixin
from ratelimit.helpers import is_ratelimited


class RatelimitTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_limit_ip(self):
        @ratelimit(ip=True, method=None, rate='1/m', block=True)
        def view(request):
            return True

        req = RequestFactory().get('/')
        assert view(req), 'First request works.'
        with self.assertRaises(Ratelimited):
            view(req)

    def test_block(self):
        @ratelimit(ip=True, method=None, rate='1/m', block=True)
        def blocked(request):
            return request.limited

        @ratelimit(ip=True, method=None, rate='1/m', block=False)
        def unblocked(request):
            return request.limited

        req = RequestFactory().get('/')

        assert not blocked(req), 'First request works.'
        with self.assertRaises(Ratelimited):
            blocked(req)

        assert unblocked(req), 'Request is limited but not blocked.'

    def test_method(self):
        rf = RequestFactory()
        post = rf.post('/')
        get = rf.get('/')

        @ratelimit(ip=True, method=['POST'], rate='1/m')
        def limit_post(request):
            return request.limited

        @ratelimit(ip=True, method=['POST', 'GET'], rate='1/m')
        def limit_get(request):
            return request.limited

        assert not limit_post(post), 'Do not limit first POST.'
        assert limit_post(post), 'Limit second POST.'
        assert not limit_post(get), 'Do not limit GET.'

        assert limit_get(post), 'Limit first POST.'
        assert limit_get(get), 'Limit first GET.'

    def test_field(self):
        james = RequestFactory().post('/', {'username': 'james'})
        john = RequestFactory().post('/', {'username': 'john'})

        @ratelimit(ip=False, field='username', rate='1/m')
        def username(request):
            return request.limited

        assert not username(james), "james' first request is fine."
        assert username(james), "james' second request is limited."
        assert not username(john), "john's first request is fine."

    def test_field_unicode(self):
        post = RequestFactory().post('/', {'username': u'fran\xe7ois'})

        @ratelimit(ip=False, field='username', rate='1/m')
        def view(request):
            return request.limited

        assert not view(post), 'First request is not limited.'
        assert view(post), 'Second request is limited.'

    def test_field_empty(self):
        post = RequestFactory().post('/', {})

        @ratelimit(ip=False, field='username', rate='1/m')
        def view(request):
            return request.limited

        assert not view(post), 'First request is not limited.'
        assert view(post), 'Second request is limited.'

    def test_rate(self):
        req = RequestFactory().post('/')

        @ratelimit(ip=True, rate='2/m')
        def twice(request):
            return request.limited

        assert not twice(req), 'First request is not limited.'
        assert not twice(req), 'Second request is not limited.'
        assert twice(req), 'Third request is limited.'

    def test_skip_if(self):
        req = RequestFactory().post('/')

        @ratelimit(rate='1/m', skip_if=lambda r: getattr(r, 'skip', False))
        def view(request):
            return request.limited

        assert not view(req), 'First request is not limited.'
        assert view(req), 'Second request is limited.'
        del req.limited
        req.skip = True
        assert not view(req), 'Skipped request is not limited.'

    @override_settings(RATELIMIT_USE_CACHE='fake.cache')
    def test_bad_cache(self):
        """The RATELIMIT_USE_CACHE setting works if the cache exists."""

        @ratelimit()
        def view(request):
            return request

        req = RequestFactory().post('/')

        with self.assertRaises(InvalidCacheBackendError):
            view(req)

    def test_keys(self):
        """Allow custom functions to set cache keys."""
        class User(object):
            def __init__(self, authenticated=False):
                self.pk = 1
                self.authenticated = authenticated

            def is_authenticated(self):
                return self.authenticated

        def user_or_ip(req):
            if req.user.is_authenticated():
                return 'uip:%d' % req.user.pk
            return 'uip:%s' % req.META['REMOTE_ADDR']

        @ratelimit(ip=False, rate='1/m', block=False, keys=user_or_ip)
        def view(request):
            return request.limited

        req = RequestFactory().post('/')
        req.user = User(authenticated=False)

        assert not view(req), 'First unauthenticated request is allowed.'
        assert view(req), 'Second unauthenticated request is limited.'

        del req.limited
        req.user = User(authenticated=True)

        assert not view(req), 'First authenticated request is allowed.'
        assert view(req), 'Second authenticated is limited.'

    def test_stacked_decorator(self):
        """Allow @ratelimit to be stacked."""
        # Put the shorter one first and make sure the second one doesn't
        # reset request.limited back to False.
        @ratelimit(ip=False, rate='1/m', block=False, keys=lambda x: 'min')
        @ratelimit(ip=False, rate='10/d', block=False, keys=lambda x: 'day')
        def view(request):
            return request.limited

        req = RequestFactory().post('/')
        assert not view(req), 'First unauthenticated request is allowed.'
        assert view(req), 'Second unauthenticated request is limited.'

    def test_is_ratelimited(self):
        def get_keys(request):
            return 'test_is_ratelimited_key'

        def not_increment(request):
            return is_ratelimited(request, increment=False, ip=False,
                                  method=None, keys=[get_keys], rate='1/m')

        def do_increment(request):
            return is_ratelimited(request, increment=True, ip=False,
                                  method=None, keys=[get_keys], rate='1/m')

        req = RequestFactory().get('/')
        # Does not increment. Count still 0. Does not rate limit
        # because 0 < 1.
        assert not not_increment(req), 'Request should not be rate limited.'

        # Increments. Does not rate limit because 0 < 1. Count now 1.
        assert not do_increment(req), 'Request should not be rate limited.'

        # Does not increment. Count still 1. Rate limits because 1 < 1
        # is false.
        assert not_increment(req), 'Request should be rate limited.'


#do it here, since python < 2.7 does not have unittest.skipIf
if django.VERSION >= (1, 4):
    class RateLimitCBVTests(TestCase):

        SKIP_REASON = u'Class Based View supported by Django >=1.4'

        def setUp(self):
            cache.clear()

        def test_limit_ip(self):

            class RLView(RateLimitMixin, View):
                ratelimit_ip = True
                ratelimit_method = None
                ratelimit_rate = '1/m'
                ratelimit_block = True

            rlview = RLView.as_view()

            req = RequestFactory().get('/')
            assert rlview(req), 'First request works.'
            with self.assertRaises(Ratelimited):
                rlview(req)

        def test_block(self):

            class BlockedView(RateLimitMixin, View):
                ratelimit_ip = True
                ratelimit_method = None
                ratelimit_rate = '1/m'
                ratelimit_block = True

                def get(self, request, *args, **kwargs):
                    return request.limited

            class UnBlockedView(RateLimitMixin, View):
                ratelimit_ip = True
                ratelimit_method = None
                ratelimit_rate = '1/m'
                ratelimit_block = False

                def get(self, request, *args, **kwargs):
                    return request.limited

            blocked = BlockedView.as_view()
            unblocked = UnBlockedView.as_view()

            req = RequestFactory().get('/')

            assert not blocked(req), 'First request works.'
            with self.assertRaises(Ratelimited):
                blocked(req)

            assert unblocked(req), 'Request is limited but not blocked.'

        def test_method(self):
            rf = RequestFactory()
            post = rf.post('/')
            get = rf.get('/')

            class LimitPostView(RateLimitMixin, View):
                ratelimit_ip = True
                ratelimit_method = ['POST']
                ratelimit_rate = '1/m'

                def post(self, request, *args, **kwargs):
                    return request.limited
                get = post

            class LimitGetView(RateLimitMixin, View):
                ratelimit_ip = True
                ratelimit_method = ['POST', 'GET']
                ratelimit_rate = '1/m'

                def post(self, request, *args, **kwargs):
                    return request.limited
                get = post

            limit_post = LimitPostView.as_view()
            limit_get = LimitGetView.as_view()

            assert not limit_post(post), 'Do not limit first POST.'
            assert limit_post(post), 'Limit second POST.'
            assert not limit_post(get), 'Do not limit GET.'

            assert limit_get(post), 'Limit first POST.'
            assert limit_get(get), 'Limit first GET.'

        def test_field(self):
            james = RequestFactory().post('/', {'username': 'james'})
            john = RequestFactory().post('/', {'username': 'john'})

            class UsernameView(RateLimitMixin, View):
                ratelimit_ip = False
                ratelimit_field = 'username'
                ratelimit_rate = '1/m'

                def post(self, request, *args, **kwargs):
                    return request.limited
                get = post

            username = UsernameView.as_view()
            assert not username(james), "james' first request is fine."
            assert username(james), "james' second request is limited."
            assert not username(john), "john's first request is fine."

        def test_field_unicode(self):
            post = RequestFactory().post('/', {'username': u'fran\xe7ois'})

            class UsernameView(RateLimitMixin, View):
                ratelimit_ip = False
                ratelimit_field = 'username'
                ratelimit_rate = '1/m'

                def post(self, request, *args, **kwargs):
                    return request.limited
                get = post

            view = UsernameView.as_view()

            assert not view(post), 'First request is not limited.'
            assert view(post), 'Second request is limited.'

        def test_field_empty(self):
            post = RequestFactory().post('/', {})

            class EmptyFieldView(RateLimitMixin, View):
                ratelimit_ip = False
                ratelimit_field = 'username'
                ratelimit_rate = '1/m'

                def post(self, request, *args, **kwargs):
                    return request.limited
                get = post

            view = EmptyFieldView.as_view()

            assert not view(post), 'First request is not limited.'
            assert view(post), 'Second request is limited.'

        def test_rate(self):
            req = RequestFactory().post('/')

            class TwiceView(RateLimitMixin, View):
                ratelimit_ip = True
                ratelimit_rate = '2/m'

                def post(self, request, *args, **kwargs):
                    return request.limited
                get = post

            twice = TwiceView.as_view()

            assert not twice(req), 'First request is not limited.'
            assert not twice(req), 'Second request is not limited.'
            assert twice(req), 'Third request is limited.'

        def test_skip_if(self):
            req = RequestFactory().post('/')

            class SkipIfView(RateLimitMixin, View):
                ratelimit_rate = '1/m'
                ratelimit_skip_if = lambda r: getattr(r, 'skip', False)

                def post(self, request, *args, **kwargs):
                    return request.limited
                get = post
            view = SkipIfView.as_view()

            assert not view(req), 'First request is not limited.'
            assert view(req), 'Second request is limited.'
            del req.limited
            req.skip = True
            assert not view(req), 'Skipped request is not limited.'

        @override_settings(RATELIMIT_USE_CACHE='fake-cache')
        def test_bad_cache(self):
            """The RATELIMIT_USE_CACHE setting works if the cache exists."""

            class BadCacheView(RateLimitMixin, View):

                def post(self, request, *args, **kwargs):
                    return request
                get = post
            view = BadCacheView.as_view()

            req = RequestFactory().post('/')

            with self.assertRaises(InvalidCacheBackendError):
                view(req)

        def test_keys(self):
            """Allow custom functions to set cache keys."""
            class User(object):
                def __init__(self, authenticated=False):
                    self.pk = 1
                    self.authenticated = authenticated

                def is_authenticated(self):
                    return self.authenticated

            def user_or_ip(req):
                if req.user.is_authenticated():
                    return 'uip:%d' % req.user.pk
                return 'uip:%s' % req.META['REMOTE_ADDR']

            class KeysView(RateLimitMixin, View):
                ratelimit_ip = False
                ratelimit_block = False
                ratelimit_rate = '1/m'
                ratelimit_keys = user_or_ip

                def post(self, request, *args, **kwargs):
                    return request.limited
                get = post
            view = KeysView.as_view()

            req = RequestFactory().post('/')
            req.user = User(authenticated=False)

            assert not view(req), 'First unauthenticated request is allowed.'
            assert view(req), 'Second unauthenticated request is limited.'

            del req.limited
            req.user = User(authenticated=True)

            assert not view(req), 'First authenticated request is allowed.'
            assert view(req), 'Second authenticated is limited.'

########NEW FILE########
__FILENAME__ = test_settings
SECRET_KEY = 'ratelimit'

INSTALLED_APPS = (
    'ratelimit',
)

RATELIMIT_USE_CACHE = 'default'

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'ratelimit-tests',
    },
}

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'test.db',
    },
}

########NEW FILE########
