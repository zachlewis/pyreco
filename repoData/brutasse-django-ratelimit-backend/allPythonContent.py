__FILENAME__ = conf
# -*- coding: utf-8 -*-
#
# django-ratelimit-backend documentation build configuration file, created by
# sphinx-quickstart on Tue Oct 18 13:27:32 2011.
#
# This file is execfile()d with the current directory set to its containing dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out
# serve to show the default.

import datetime

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#sys.path.insert(0, os.path.abspath('.'))

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
project = u'django-ratelimit-backend'
copyright = u'2011-{0}, Bruno Renié'.format(datetime.datetime.today().year)

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = '0.6.1'
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
#html_static_path = ['_static']

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
htmlhelp_basename = 'django-ratelimit-backenddoc'


# -- Options for LaTeX output --------------------------------------------------

# The paper size ('letter' or 'a4').
#latex_paper_size = 'letter'

# The font size ('10pt', '11pt' or '12pt').
#latex_font_size = '10pt'

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass [howto/manual]).
latex_documents = [
  ('index', 'django-ratelimit-backend.tex', u'django-ratelimit-backend Documentation',
   u'Bruno Renié', 'manual'),
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
    ('index', 'django-ratelimit-backend', u'django-ratelimit-backend Documentation',
     [u'Bruno Renié'], 1)
]

DIRECTORIES = (
    ('', 'make html'),
)

########NEW FILE########
__FILENAME__ = admin
from django.contrib.admin import *  # noqa
from django.contrib.admin import (site as django_site,
                                  autodiscover as django_autodiscover)
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.utils.translation import ugettext as _

from .forms import AdminAuthenticationForm
from .views import login


class RateLimitAdminSite(AdminSite):
    def login(self, request, extra_context=None):
        """
        Displays the login form for the given HttpRequest.
        """
        context = {
            'title': _('Log in'),
            'app_path': request.get_full_path(),
            REDIRECT_FIELD_NAME: request.get_full_path(),
        }
        context.update(extra_context or {})
        defaults = {
            'extra_context': context,
            'current_app': self.name,
            'authentication_form': self.login_form or AdminAuthenticationForm,
            'template_name': self.login_template or 'admin/login.html',
        }
        return login(request, **defaults)
site = RateLimitAdminSite()


def autodiscover():
    django_autodiscover()
    for model, modeladmin in django_site._registry.items():
        if not model in site._registry:
            site.register(model, modeladmin.__class__)

########NEW FILE########
__FILENAME__ = backends
import logging
import warnings

from datetime import datetime, timedelta

from django.contrib.auth.backends import ModelBackend
from django.core.cache import cache

from .exceptions import RateLimitException

logger = logging.getLogger('ratelimitbackend')


class RateLimitMixin(object):
    """
    A mixin to enable rate-limiting in an existing authentication backend.
    """
    cache_prefix = 'ratelimitbackend-'
    minutes = 5
    requests = 30
    username_key = 'username'

    def authenticate(self, **kwargs):
        request = kwargs.pop('request', None)
        username = kwargs[self.username_key]
        if request is not None:
            counts = self.get_counters(request)
            if sum(counts.values()) >= self.requests:
                logger.warning(
                    u"Login rate-limit reached: username '{0}', IP {1}".format(
                        username, request.META['REMOTE_ADDR']
                    )
                )
                raise RateLimitException('Rate-limit reached', counts)
        else:
            warnings.warn(u"No request passed to the backend, unable to "
                          u"rate-limit. Username was '%s'" % username,
                          stacklevel=2)
        user = super(RateLimitMixin, self).authenticate(**kwargs)
        if user is None and request is not None:
            logger.info(
                u"Login failed: username '{0}', IP {1}".format(
                    username,
                    request.META['REMOTE_ADDR'],
                )
            )
            cache_key = self.get_cache_key(request)
            self.cache_incr(cache_key)
        return user

    def get_counters(self, request):
        return cache.get_many(self.keys_to_check(request))

    def keys_to_check(self, request):
        now = datetime.now()
        return [
            self.key(
                request,
                now - timedelta(minutes=minute),
            ) for minute in range(self.minutes + 1)
        ]

    def get_cache_key(self, request):
        return self.key(request, datetime.now())

    def key(self, request, dt):
        return '%s%s-%s' % (
            self.cache_prefix,
            request.META.get('REMOTE_ADDR', ''),
            dt.strftime('%Y%m%d%H%M'),
        )

    def cache_incr(self, key):
        """
        Non-atomic cache increment operation. Not optimal but
        consistent across different cache backends.
        """
        cache.set(key, cache.get(key, 0) + 1, self.expire_after())

    def expire_after(self):
        """Cache expiry delay"""
        return (self.minutes + 1) * 60


class RateLimitModelBackend(RateLimitMixin, ModelBackend):
    pass

########NEW FILE########
__FILENAME__ = exceptions
class RateLimitException(Exception):
    def __init__(self, msg, counts):
        self.counts = counts
        super(RateLimitException, self).__init__(msg)

########NEW FILE########
__FILENAME__ = forms
from django import forms
from django.contrib.admin.forms import (
    AdminAuthenticationForm as AdminAuthForm, ERROR_MESSAGE,
)
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm as AuthForm
from django.utils.translation import ugettext_lazy as _


class AuthenticationForm(AuthForm):
    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username and password:
            self.user_cache = authenticate(username=username,
                                           password=password,
                                           request=self.request)
            if self.user_cache is None:
                raise forms.ValidationError(
                    _('Please enter a correct username and password. '
                      'Note that both fields are case-sensitive.'),
                )
            elif not self.user_cache.is_active:
                raise forms.ValidationError(_('This account is inactive.'))
        return self.cleaned_data


class AdminAuthenticationForm(AdminAuthForm):
    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        message = ERROR_MESSAGE

        if username and password:
            self.user_cache = authenticate(username=username,
                                           password=password,
                                           request=self.request)
            if self.user_cache is None:
                raise forms.ValidationError(message)
            elif not self.user_cache.is_active or not self.user_cache.is_staff:
                raise forms.ValidationError(message)
        return self.cleaned_data

########NEW FILE########
__FILENAME__ = middleware
from django.http import HttpResponseForbidden

from .exceptions import RateLimitException


class RateLimitMiddleware(object):
    """
    Handles exceptions thrown by rate-limited login attepmts.
    """
    def process_exception(self, request, exception):
        if isinstance(exception, RateLimitException):
            return HttpResponseForbidden(
                'Too many failed login attempts. Try again later.',
                content_type='text/plain',
            )

########NEW FILE########
__FILENAME__ = models

########NEW FILE########
__FILENAME__ = backends
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User

from ..backends import RateLimitMixin, RateLimitModelBackend


class TestBackend(RateLimitModelBackend):
    minutes = 10
    requests = 50

    def key(self, request, dt):
        """Derives the cache key from the submitted username too."""
        return '%s%s-%s-%s' % (
            self.cache_prefix,
            request.META.get('REMOTE_ADDR', ''),
            request.POST['username'],
            dt.strftime('%Y%m%d%H%M'),
        )


class CustomBackend(ModelBackend):
    def authenticate(self, token=None, secret=None):
        try:
            user = User.objects.get(username=token)
            if user.check_password(secret):
                return user
        except User.DoesNotExist:
            return None


class TestCustomBackend(RateLimitMixin, CustomBackend):
    """Rate-limited backend with token/secret instead of username/password"""
    username_key = 'token'


class TestCustomBrokenBackend(RateLimitMixin, CustomBackend):
    """Rate-limited backend with token/secret instead of username/password"""

########NEW FILE########
__FILENAME__ = forms
from django.forms import Form, ValidationError, CharField, PasswordInput
from django.contrib.auth import authenticate


class CustomAuthForm(Form):
    token = CharField(max_length=30)
    secret = CharField(widget=PasswordInput)

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super(CustomAuthForm, self).__init__(*args, **kwargs)

    def clean(self):
        token = self.cleaned_data.get('token')
        secret = self.cleaned_data.get('secret')
        if token and secret:
            self.user_cache = authenticate(token=token,
                                           secret=secret,
                                           request=self.request)
            if self.user_cache is None:
                raise ValidationError("Invalid")
            elif not self.user_cache.is_active:
                raise ValidationError("Inactive")
        return self.cleaned_data

    def get_user(self):
        return self.user_cache

########NEW FILE########
__FILENAME__ = models
from django.db import models

try:
    from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
    from django.utils import timezone
except ImportError:
    pass
else:
    class UserManager(BaseUserManager):
        def create_user(self, email, password=None, **extra_fields):
            now = timezone.now()
            if not email:
                raise ValueError('The email must be set.')
            email = UserManager.normalize_email(email)
            user = self.model(email=email, last_login=now, date_joined=now,
                              **extra_fields)
            user.set_password(password)
            user.save(using=self._db)
            return user

        def create_superuser(self, email, password, **extra_fields):
            user = self.create_user(email, password, **extra_fields)
            user.is_staff = True
            user.is_active = True
            user.is_superuser = True
            user.save(using=self._db, update_fields=['is_staff', 'is_active',
                                                     'is_superuser'])
            return user

    class User(AbstractBaseUser):
        """A user with email as identifier"""
        USERNAME_FIELD = 'email'
        REQUIRED_FIELDS = []
        email = models.EmailField(max_length=255, unique=True, db_index=True)
        is_staff = models.BooleanField(default=False)
        is_active = models.BooleanField(default=False)
        is_superuser = models.BooleanField(default=False)
        date_joined = models.DateTimeField(default=timezone.now)

        objects = UserManager()

########NEW FILE########
__FILENAME__ = urls
from django.conf.urls import include, patterns, url

from .. import admin
from ..views import login
from .forms import CustomAuthForm

admin.autodiscover()


urlpatterns = patterns(
    '',
    url(r'^login/$', login,
        {'template_name': 'admin/login.html'}, name='login'),
    url(r'^custom_login/$', login,
        {'template_name': 'custom_login.html',
         'authentication_form': CustomAuthForm},
        name='custom_login'),
    url(r'^admin/', include(admin.site.urls)),
)

########NEW FILE########
__FILENAME__ = views
try:
    from urllib.parse import urlparse
except ImportError:  # Python2
    from urlparse import urlparse  # noqa

from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME, login as auth_login
from django.contrib.sites.models import get_current_site
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect

from .forms import AuthenticationForm


@csrf_protect
@never_cache
def login(request, template_name='registration/login.html',
          redirect_field_name=REDIRECT_FIELD_NAME,
          authentication_form=AuthenticationForm,
          current_app=None, extra_context=None):
    """
    Displays the login form and handles the login action.
    """
    redirect_to = request.REQUEST.get(redirect_field_name, '')

    if request.method == "POST":
        form = authentication_form(data=request.POST, request=request)
        if form.is_valid():
            netloc = urlparse(redirect_to)[1]

            # Use default setting if redirect_to is empty
            if not redirect_to:
                redirect_to = settings.LOGIN_REDIRECT_URL

            # Heavier security check -- don't allow redirection to a different
            # host.
            elif netloc and netloc != request.get_host():
                redirect_to = settings.LOGIN_REDIRECT_URL

            # Okay, security checks complete. Log the user in.
            auth_login(request, form.get_user())

            return redirect(redirect_to)
    else:
        form = authentication_form(request)

    current_site = get_current_site(request)

    context = {
        'form': form,
        redirect_field_name: redirect_to,
        'site': current_site,
        'site_name': current_site.name,
    }
    if extra_context is not None:
        context.update(extra_context)
    return TemplateResponse(request, template_name, context,
                            current_app=current_app)

########NEW FILE########
__FILENAME__ = runtests
#!/usr/bin/env python
import logging
import os
import sys

from django.conf import settings
try:
    from django.utils.functional import empty
except ImportError:
    empty = None


class NullHandler(logging.Handler):  # NullHandler isn't in Python 2.6
    def emit(self, record):
        pass


def setup_test_environment():
    # reset settings
    settings._wrapped = empty

    apps = [
        'django.contrib.sessions',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sites',
        'django.contrib.admin',
        'django.contrib.messages',
        'ratelimitbackend',
        'ratelimitbackend.tests',
    ]

    middleware_classes = [
        'django.middleware.common.CommonMiddleware',
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.contrib.messages.middleware.MessageMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'django.middleware.csrf.CsrfViewMiddleware',
        'ratelimitbackend.middleware.RateLimitMiddleware',
    ]

    settings_dict = {
        "DATABASES": {
            'default': {
                'ENGINE': "django.db.backends.sqlite3",
                'NAME': 'ratelimitbackend.sqlite',
            },
        },
        "CACHES": {
            'default': {
                'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            },
        },
        "ROOT_URLCONF": "ratelimitbackend.tests.urls",
        "MIDDLEWARE_CLASSES": middleware_classes,
        "INSTALLED_APPS": apps,
        "SITE_ID": 1,
        "AUTHENTICATION_BACKENDS": (
            'ratelimitbackend.backends.RateLimitModelBackend',
        ),
        "LOGGING": {
            'version': 1,
            'handlers': {
                'null': {
                    'class': 'runtests.NullHandler',
                }
            },
            'loggers': {
                'ratelimitbackend': {
                    'handlers': ['null'],
                },
            },
        },
    }

    # set up settings for running tests for all apps
    settings.configure(**settings_dict)


def runtests(*test_args):
    if not test_args:
        test_args = ('ratelimitbackend',)
    setup_test_environment()

    parent = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, parent)
    try:
        from django.test.simple import DjangoTestSuiteRunner

        def run_tests(test_args, verbosity, interactive):
            runner = DjangoTestSuiteRunner(
                verbosity=verbosity, interactive=interactive, failfast=False)
            return runner.run_tests(test_args)
    except ImportError:
        # for Django versions that don't have DjangoTestSuiteRunner
        from django.test.simple import run_tests
    failures = run_tests(test_args, verbosity=1, interactive=True)
    sys.exit(failures)


if __name__ == '__main__':
    runtests('ratelimitbackend')

DIRECTORIES = (
    ('ratelimitbackend', 'python runtests.py'),
    ('docs', 'cd docs && make html'),
)

########NEW FILE########
