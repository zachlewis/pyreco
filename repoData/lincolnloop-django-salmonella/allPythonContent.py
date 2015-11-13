__FILENAME__ = conf
# -*- coding: utf-8 -*-
#
# django-salmonella documentation build configuration file, created by
# sphinx-quickstart on Sun Sep 11 07:58:02 2011.
#
# This file is execfile()d with the current directory set to its containing dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out
# serve to show the default.

import sys, os

DOCS_BASE = os.path.dirname(__file__)
sys.path.insert(0, os.path.abspath(os.path.join(DOCS_BASE, '..')))

import salmonella

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
project = u'django-salmonella'
copyright = u'2011, Lincoln Loop'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = salmonella.get_version(short=True)
# The full version, including alpha/beta/rc tags.
release = salmonella.__version__

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
htmlhelp_basename = 'django-salmonelladoc'


# -- Options for LaTeX output --------------------------------------------------

# The paper size ('letter' or 'a4').
#latex_paper_size = 'letter'

# The font size ('10pt', '11pt' or '12pt').
#latex_font_size = '10pt'

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass [howto/manual]).
latex_documents = [
  ('index', 'django-salmonella.tex', u'django-salmonella Documentation',
   u'Lincoln Loop', 'manual'),
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
    ('index', 'django-salmonella', u'django-salmonella Documentation',
     [u'Lincoln Loop'], 1)
]

########NEW FILE########
__FILENAME__ = manage
#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE",
        "project_example.conf.local")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)

########NEW FILE########
__FILENAME__ = admin
from django.contrib import admin

from salmonella.admin import SalmonellaMixin

from .models import SalmonellaTest, DirectPrimaryKeyModel, CharPrimaryKeyModel


class SalmonellaTestAdmin(SalmonellaMixin, admin.ModelAdmin):
    raw_id_fields = ('rawid_fk', 'rawid_fk_limited', 'rawid_many')
    salmonella_fields = ('salmonella_fk', 'salmonella_fk_limited', 'salmonella_many', 'salmonella_fk_direct_pk', 'salmonella_fk_char_pk')

admin.site.register(DirectPrimaryKeyModel)
admin.site.register(CharPrimaryKeyModel)
admin.site.register(SalmonellaTest, SalmonellaTestAdmin)

########NEW FILE########
__FILENAME__ = models
from django.db import models

class DirectPrimaryKeyModel(models.Model):
    num = models.IntegerField("Number", primary_key=True)

class CharPrimaryKeyModel(models.Model):
    chr = models.CharField(max_length=20, primary_key=True)


class SalmonellaTest(models.Model):
    rawid_fk = models.ForeignKey('auth.User',
        related_name='rawid_fk', blank=True, null=True)

    rawid_fk_limited = models.ForeignKey('auth.User',
        related_name='rawid_fk_limited',
        limit_choices_to={'is_staff': True},
        blank=True, null=True)

    rawid_many = models.ManyToManyField('auth.User',
        related_name='rawid_many', blank=True, null=True)

    rawid_fk_direct_pk = models.ForeignKey(DirectPrimaryKeyModel,
        related_name='rawid_fk_direct_pk', blank=True, null=True)

    salmonella_fk = models.ForeignKey('auth.User',
        related_name='salmonella_fk', blank=True, null=True)

    salmonella_fk_limited = models.ForeignKey('auth.User',
        related_name='salmonella_fk_limited',
        limit_choices_to={'is_staff': True},
        blank=True, null=True)

    salmonella_many = models.ManyToManyField('auth.User',
        related_name='salmonella_many', blank=True, null=True)

    salmonella_fk_direct_pk = models.ForeignKey(DirectPrimaryKeyModel,
        related_name='salmonella_fk_direct_pk', blank=True, null=True)

    salmonella_fk_char_pk = models.ForeignKey(CharPrimaryKeyModel,
            related_name='salmonella_fk_char_pk', blank=True, null=True)

########NEW FILE########
__FILENAME__ = tests
"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""

from django.test import TestCase


class SimpleTest(TestCase):
    def test_basic_addition(self):
        """
        Tests that 1 + 1 always equals 2.
        """
        self.assertEqual(1 + 1, 2)

########NEW FILE########
__FILENAME__ = views
# Create your views here.

########NEW FILE########
__FILENAME__ = urls
from django.conf.urls import patterns, include
from django.conf.urls.static import static
from django.conf import settings


urlpatterns = patterns('',
    (r'', include('project_example.urls')),
)

if settings.MEDIA_ROOT:
    urlpatterns += static(settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT)

########NEW FILE########
__FILENAME__ = urls
from django.conf.urls import patterns, include
from django.contrib import admin

admin.autodiscover()

urlpatterns = patterns('',
    (r'', include('project_example.urls')),
    (r'^admin/', include(admin.site.urls)),
)

########NEW FILE########
__FILENAME__ = settings
# Import global settings to make it easier to extend settings.
from django.conf.global_settings import *   # pylint: disable=W0614,W0401

#==============================================================================
# Generic Django project settings
#==============================================================================

DEBUG = True
TEMPLATE_DEBUG = DEBUG

SITE_ID = 1
# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
TIME_ZONE = 'UTC'
USE_TZ = True
USE_I18N = True
USE_L10N = True
LANGUAGE_CODE = 'en'
LANGUAGES = (
    ('en', 'English'),
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'baa5(pf=j&amp;zb0a6=(as673air8u(ino%ss@+v@k9expf3gn84g'

INSTALLED_APPS = (
    'project_example.apps.test_salmonella',
    'salmonella',

    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admin',
    'django.contrib.admindocs',

)

#==============================================================================
# Calculation of directories relative to the project module location
#==============================================================================

import os
import sys
import project_example as project_module

PROJECT_DIR = os.path.dirname(os.path.realpath(project_module.__file__))

PYTHON_BIN = os.path.dirname(sys.executable)
ve_path = os.path.dirname(os.path.dirname(os.path.dirname(PROJECT_DIR)))
# Assume that the presence of 'activate_this.py' in the python bin/
# directory means that we're running in a virtual environment.
if os.path.exists(os.path.join(PYTHON_BIN, 'activate_this.py')):
    # We're running with a virtualenv python executable.
    VAR_ROOT = os.path.join(os.path.dirname(PYTHON_BIN), 'var')
elif ve_path and os.path.exists(os.path.join(ve_path, 'bin',
        'activate_this.py')):
    # We're running in [virtualenv_root]/src/[project_name].
    VAR_ROOT = os.path.join(ve_path, 'var')
else:
    # Set the variable root to the local configuration location (which is
    # ignored by the repository).
    VAR_ROOT = os.path.join(PROJECT_DIR, 'conf', 'local')

if not os.path.exists(VAR_ROOT):
    os.mkdir(VAR_ROOT)

#==============================================================================
# Project URLS and media settings
#==============================================================================

ROOT_URLCONF = 'project_example.urls'

LOGIN_URL = '/login/'
LOGOUT_URL = '/logout/'
LOGIN_REDIRECT_URL = '/'

STATIC_URL = '/static/'
MEDIA_URL = '/uploads/'

STATIC_ROOT = os.path.join(VAR_ROOT, 'static')
MEDIA_ROOT = os.path.join(VAR_ROOT, 'uploads')

STATICFILES_DIRS = (
    os.path.join(PROJECT_DIR, 'static'),
)

#==============================================================================
# Templates
#==============================================================================

TEMPLATE_DIRS = (
    os.path.join(PROJECT_DIR, 'templates'),
)

TEMPLATE_CONTEXT_PROCESSORS += (
)

#==============================================================================
# Middleware
#==============================================================================

MIDDLEWARE_CLASSES += (
)

#==============================================================================
# Auth / security
#==============================================================================

AUTHENTICATION_BACKENDS += (
)

#==============================================================================
# Miscellaneous project settings
#==============================================================================

#==============================================================================
# Third party app settings
#==============================================================================

########NEW FILE########
__FILENAME__ = urls
from django.conf.urls import patterns, url, include
from django.contrib import admin

admin.autodiscover()

urlpatterns = patterns('',
    #url('', include('project_example.apps.'))
    (r'^admin/doc/', include('django.contrib.admindocs.urls')),
    (r'^admin/', include(admin.site.urls)),


    url(r'^admin/salmonella/', include('salmonella.urls')),
)

########NEW FILE########
__FILENAME__ = admin
from salmonella.widgets import SalmonellaIdWidget, SalmonellaMultiIdWidget


class SalmonellaMixin(object):
    salmonella_fields = ()

    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        if db_field.name in self.salmonella_fields:
            try:
                kwargs['widget'] = SalmonellaIdWidget(db_field.rel)
            except TypeError:  # django 1.4+
                kwargs['widget'] = SalmonellaIdWidget(db_field.rel, self.admin_site)
            return db_field.formfield(**kwargs)
        return super(SalmonellaMixin, self).formfield_for_foreignkey(db_field,
                                                                     request,
                                                                     **kwargs)

    def formfield_for_manytomany(self, db_field, request=None, **kwargs):
        if db_field.name in self.salmonella_fields:
            try:
                kwargs['widget'] = SalmonellaMultiIdWidget(db_field.rel)
            except TypeError:  # django 1.4+
                kwargs['widget'] = SalmonellaMultiIdWidget(db_field.rel, self.admin_site)
            kwargs['help_text'] = ''
            return db_field.formfield(**kwargs)
        return super(SalmonellaMixin, self).formfield_for_manytomany(db_field,
                                                                     request,
                                                                     **kwargs)

########NEW FILE########
__FILENAME__ = models

########NEW FILE########
__FILENAME__ = tests

########NEW FILE########
__FILENAME__ = urls
from django.conf.urls import *

urlpatterns = patterns('',
    url(r'^(?P<app_name>[\w-]+)/(?P<model_name>[\w-]+)/multiple/$',
        'salmonella.views.label_view',
        {
            'multi': True,
            'template_object_name': 'objects',
            'template_name': 'salmonella/multi_label.html'
        },
        name="salmonella_multi_label"),
    url(r'^(?P<app_name>[\w-]+)/(?P<model_name>[\w-]+)/$',
        'salmonella.views.label_view',
        {
            'template_name': 'salmonella/label.html'
        },
        name="salmonella_label"),
)

########NEW FILE########
__FILENAME__ = views
from django.core.urlresolvers import reverse
from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import render_to_response
from django.db.models import get_model


@user_passes_test(lambda u: u.is_staff)
def label_view(request, app_name, model_name, template_name="", multi=False,
               template_object_name="object"):

    # The list of to obtained objects is in GET.id. No need to resume if we
    # didnt get it.
    if not request.GET.get('id'):
        msg = 'No list of objects given'
        return HttpResponseBadRequest(settings.DEBUG and msg or '')

    # Given objects are either an integer or a comma-separted list of
    # integers. Validate them and ignore invalid values. Also strip them
    # in case the user entered values by hand, such as '1, 2,3'.
    object_list = []
    for pk in request.GET['id'].split(","):
        object_list.append(pk.strip())

    # Check if at least one value survived this cleanup.
    if len(object_list) == 0:
        msg = 'No list or only invalid ids of objects given'
        return HttpResponseBadRequest(settings.DEBUG and msg or '')

    # Make sure this model exists and the user has 'change' permission for it.
    # If he doesnt have this permission, Django would not display the
    # change_list in the popup and the user were never able to select objects.
    model = get_model(app_name, model_name)
    if not model:
        msg = 'Model %s.%s does not exist.' % (app_name, model_name)
        return HttpResponseBadRequest(settings.DEBUG and msg or '')

    if not request.user.has_perm('%s.change_%s' % (app_name, model_name)):
        return HttpResponseForbidden()

    try:
        if multi:
            model_template = "salmonella/%s/multi_%s.html" % (app_name, model_name)
            objs = model.objects.filter(pk__in=object_list)
            objects = []
            for obj in objs:
                change_url = reverse("admin:%s_%s_change" % (app_name, model_name),
                                     args=[obj.pk])
                obj = (obj, change_url)
                objects.append(obj)
            extra_context = {
                template_object_name: objects,
            }
        else:
            model_template = "salmonella/%s/%s.html" % (app_name, model_name)
            obj = model.objects.get(pk=object_list[0])
            change_url = reverse("admin:%s_%s_change" % (app_name, model_name),
                                 args=[obj.pk])
            extra_context = {
                template_object_name: (obj, change_url),
            }
    # most likely the pk wasn't convertable
    except ValueError:
        msg = 'ValueError during lookup'
        return HttpResponseBadRequest(settings.DEBUG and msg or '')
    except model.DoesNotExist:
        msg = 'Model instance does not exist'
        return HttpResponseBadRequest(settings.DEBUG and msg or '')

    return render_to_response((model_template, template_name), extra_context)

########NEW FILE########
__FILENAME__ = widgets
from django.conf import settings
from django.contrib.admin import widgets
from django.core.urlresolvers import reverse, NoReverseMatch
from django.core.exceptions import ImproperlyConfigured
from django.template.loader import render_to_string
from django.utils.encoding import force_unicode


class SalmonellaImproperlyConfigured(ImproperlyConfigured):
    pass


class SalmonellaIdWidget(widgets.ForeignKeyRawIdWidget):
    def render(self, name, value, attrs=None, multi=False):
        if attrs is None:
            attrs = {}

        try:
            related_url = reverse('admin:%s_%s_changelist' % (
                self.rel.to._meta.app_label,
                self.rel.to._meta.object_name.lower()))
        except NoReverseMatch:
            raise SalmonellaImproperlyConfigured('The model %s.%s is not '
                'registered in the admin.' % (self.rel.to._meta.app_label,
                                              self.rel.to._meta.object_name))

        params = self.url_parameters()
        if params:
            url = u'?' + u'&'.join([u'%s=%s' % (k, v) for k, v in params.items()])
        else:
            url = u''
        if "class" not in attrs:
            attrs['class'] = 'vForeignKeyRawIdAdminField'  # The JavaScript looks for this hook.
        app_name = self.rel.to._meta.app_label.strip()
        model_name = self.rel.to._meta.object_name.lower().strip()
        hidden_input = super(widgets.ForeignKeyRawIdWidget, self).render(name, value, attrs)

        extra_context = {
            'hidden_input': hidden_input,
            'name': name,
            'app_name': app_name,
            'model_name': model_name,
            'related_url': related_url,
            'url': url,
            'SALMONELLA_STATIC': settings.STATIC_URL + 'salmonella/'
        }
        return render_to_string('salmonella/admin/widgets/salmonella_field.html',
                                extra_context)

    class Media:
        js = (settings.STATIC_URL + "salmonella/js/salmonella.js",)


class SalmonellaMultiIdWidget(SalmonellaIdWidget):
    def value_from_datadict(self, data, files, name):
        value = data.get(name)
        if value:
            return value.split(',')

    def render(self, name, value, attrs=None):
        if attrs is None:
            attrs = {}
        attrs['class'] = 'vManyToManyRawIdAdminField'
        if value:
            value = ','.join([force_unicode(v) for v in value])
        else:
            value = ''
        return super(SalmonellaMultiIdWidget, self).render(name, value,
                                                           attrs, multi=True)

########NEW FILE########
