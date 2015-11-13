__FILENAME__ = conf
# -*- coding: utf-8 -*-
#
# dryscrape documentation build configuration file, created by
# sphinx-quickstart on Thu Jan 12 15:55:25 2012.
#
# This file is execfile()d with the current directory set to its containing dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out
# serve to show the default.

import sys, os

class Mock(object):
    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        return Mock()

    @classmethod
    def __getattr__(self, name):
        if name in ('__file__', '__path__'):
            return '/dev/null'
        elif name[0].upper() == name[0]:
            return type(name, (), {})
        else:
            return Mock()

# mock some modules...
MOCK_MODULES = []
for mod_name in MOCK_MODULES:
    sys.modules[mod_name] = Mock()

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
sys.path.insert(0, os.path.abspath('..'))

# -- General configuration -----------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be extensions
# coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = ['sphinx.ext.autodoc',
              'sphinx.ext.viewcode',
              'sphinx.ext.graphviz',
              'sphinx.ext.inheritance_diagram']

# autodoc config
autodoc_default_flags = ['show-inheritance']

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The encoding of source files.
#source_encoding = 'utf-8-sig'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = u'dryscrape'
copyright = u'2012, Niklas Baumstark'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = '0.8'
# The full version, including alpha/beta/rc tags.
release = '0.8'

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
htmlhelp_basename = 'dryscrapedoc'


# -- Options for LaTeX output --------------------------------------------------

# The paper size ('letter' or 'a4').
#latex_paper_size = 'letter'

# The font size ('10pt', '11pt' or '12pt').
#latex_font_size = '10pt'

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass [howto/manual]).
latex_documents = [
  ('index', 'dryscrape.tex', u'dryscrape Documentation',
   u'Niklas Baumstark', 'manual'),
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
    ('index', 'dryscrape', u'dryscrape Documentation',
     [u'Niklas Baumstark'], 1)
]

########NEW FILE########
__FILENAME__ = webkit
"""
Headless Webkit driver for dryscrape. Wraps the ``webkit_server`` module.
"""

import dryscrape.mixins
import webkit_server

class Node(webkit_server.Node,
           dryscrape.mixins.SelectionMixin,
           dryscrape.mixins.AttributeMixin):
  """ Node implementation wrapping a ``webkit_server`` node. """


class NodeFactory(webkit_server.NodeFactory):
  """ overrides the NodeFactory provided by ``webkit_server``. """
  def create(self, node_id):
    return Node(self.client, node_id)


class Driver(webkit_server.Client,
             dryscrape.mixins.WaitMixin,
             dryscrape.mixins.HtmlParsingMixin):
  """ Driver implementation wrapping a ``webkit_server`` driver.

  Keyword arguments are passed through to the underlying ``webkit_server.Client``
  constructor. By default, `node_factory_class` is set to use the dryscrape
  node implementation. """
  def __init__(self, **kw):
    kw.setdefault('node_factory_class', NodeFactory)
    super(Driver, self).__init__(**kw)

########NEW FILE########
__FILENAME__ = mixins
"""
Mixins for use in dryscrape drivers.
"""

import time
import lxml.html

class SelectionMixin(object):
  """ Mixin that adds different methods of node selection to an object that
  provides an ``xpath`` method returning a collection of matches. """

  def css(self, css):
    """ Returns all nodes matching the given CSSv3 expression. """
    return self.css(css)

  def at_css(self, css):
    """ Returns the first node matching the given CSSv3
    expression or ``None``. """
    return self._first_or_none(self.css(css))

  def at_xpath(self, xpath):
    """ Returns the first node matching the given XPath 2.0 expression or ``None``.
    """
    return self._first_or_none(self.xpath(xpath))

  def parent(self):
    """ Returns the parent node. """
    return self.at_xpath('..')

  def children(self):
    """ Returns the child nodes. """
    return self.xpath('*')

  def form(self):
    """ Returns the form wherein this node is contained or ``None``. """
    return self.at_xpath("ancestor::form")

  def _first_or_none(self, list):
    return list[0] if list else None


class AttributeMixin(object):
  """ Mixin that adds ``[]`` access syntax sugar to an object that supports a
  ``set_attr`` and ``get_attr`` method. """

  def __getitem__(self, attr):
    """ Syntax sugar for accessing this node's attributes """
    return self.get_attr(attr)

  def __setitem__(self, attr, value):
    """ Syntax sugar for setting this node's attributes """
    self.set_attr(attr, value)


class HtmlParsingMixin(object):
  """ Mixin that adds a ``document`` method to an object that supports a ``body``
  method returning valid HTML. """

  def document(self):
    """ Parses the HTML returned by ``body`` and returns it as an lxml.html
    document. If the driver supports live DOM manipulation (like webkit_server
    does), changes performed on the returned document will not take effect. """
    return lxml.html.document_fromstring(self.body())


# default timeout values
DEFAULT_WAIT_INTERVAL = 0.5
DEFAULT_WAIT_TIMEOUT = 10
DEFAULT_AT_TIMEOUT = 1

class WaitTimeoutError(Exception):
  """ Raised when a wait times out """

class WaitMixin(SelectionMixin):
  """ Mixin that allows waiting for conditions or elements. """

  def wait_for(self,
               condition,
               interval = DEFAULT_WAIT_INTERVAL,
               timeout  = DEFAULT_WAIT_TIMEOUT):
    """ Wait until a condition holds by checking it in regular intervals.
    Raises ``WaitTimeoutError`` on timeout. """

    start = time.time()

    # at least execute the check once!
    while True:
      res = condition()
      if res:
        return res

      # timeout?
      if time.time() - start > timeout:
        break

      # wait a bit
      time.sleep(interval)

    # timeout occured!
    raise WaitTimeoutError, "wait_for timed out"

  def wait_for_safe(self, *args, **kw):
    """ Wait until a condition holds and return
    ``None`` on timeout. """
    try:
      return self.wait_for(*args, **kw)
    except WaitTimeoutError:
      return None

  def wait_while(self, condition, *args, **kw):
    """ Wait while a condition holds. """
    return self.wait_for(lambda: not condition(), *args, **kw)

  def at_css(self, css, timeout = DEFAULT_AT_TIMEOUT, **kw):
    """ Returns the first node matching the given CSSv3 expression or ``None``
    if a timeout occurs. """
    return self.wait_for_safe(lambda: super(WaitMixin, self).at_css(css),
                              timeout = timeout,
                              **kw)

  def at_xpath(self, xpath, timeout = DEFAULT_AT_TIMEOUT, **kw):
    """ Returns the first node matching the given XPath 2.0 expression or ``None``
    if a timeout occurs. """
    return self.wait_for_safe(lambda: super(WaitMixin, self).at_xpath(xpath),
                              timeout = timeout,
                              **kw)

########NEW FILE########
__FILENAME__ = session
import urlparse
from dryscrape.driver.webkit import Driver as DefaultDriver

class Session(object):
  """ A web scraping session based on a driver instance. Implements the proxy
  pattern to pass unresolved method calls to the underlying driver.

  If no `driver` is specified, the instance will create an instance of
  ``dryscrape.session.DefaultDriver`` to get a driver instance (defaults to
  ``dryscrape.driver.webkit.Driver``).

  If `base_url` is present, relative URLs are completed with this URL base.
  If not, the `get_base_url` method is called on itself to get the base URL. """

  def __init__(self,
               driver = None,
               base_url = None):
    self.driver = driver or DefaultDriver()
    self.base_url = base_url

  # implement proxy pattern
  def __getattr__(self, attr):
    """ Pass unresolved method calls to underlying driver. """
    return getattr(self.driver, attr)

  def visit(self, url):
    """ Passes through the URL to the driver after completing it using the
    instance's URL base. """
    return self.driver.visit(self.complete_url(url))

  def complete_url(self, url):
    """ Completes a given URL with this instance's URL base. """
    if self.base_url:
      return urlparse.urljoin(self.base_url, url)
    else:
      return url

  def interact(self, **local):
    """ Drops the user into an interactive Python session with the ``sess`` variable
    set to the current session instance. If keyword arguments are supplied, these
    names will also be available within the session. """
    import code
    code.interact(local=dict(sess=self, **local))

########NEW FILE########
__FILENAME__ = gmail
import time
import dryscrape

#==========================================
# Setup
#==========================================

email    = 'YOUR_EMAIL_HERE'
password = 'YOUR_PASSWORD_HERE'

# set up a web scraping session
sess = dryscrape.Session(base_url = 'https://mail.google.com/')

# we don't need images
sess.set_attribute('auto_load_images', False)

# if we wanted, we could also configure a proxy server to use,
# so we can for example use Fiddler to monitor the requests
# performed by this script
#sess.set_proxy('localhost', 8888)

#==========================================
# GMail send a mail to self
#==========================================

# visit homepage and log in
print "Logging in..."
sess.visit('/')

email_field    = sess.at_css('#Email')
password_field = sess.at_css('#Passwd')
email_field.set(email)
password_field.set(password)

email_field.form().submit()

# find the COMPOSE button and click it
print "Sending a mail..."
compose = sess.at_xpath('//*[contains(text(), "COMPOSE")]')
compose.click()

# compose the mail
to      = sess.at_xpath('//*[@name="to"]', timeout=10)
subject = sess.at_xpath('//*[@name="subject"]')
body    = sess.at_xpath('//*[@name="body"]')

to.set(email)
subject.set("Note to self")
body.set("Remember to try dryscrape!")

# send the mail

# seems like we need to wait a bit before clicking...
# Blame Google for this ;)
time.sleep(3)
send = sess.at_xpath('//*[normalize-space(text()) = "Send"]')
send.click()

# open the mail
print "Reading the mail..."
mail = sess.at_xpath('//*[normalize-space(text()) = "Note to self"]',
                     timeout=10)
mail.click()

# sleep a bit to leave the mail a chance to open.
# This is ugly, it would be better to find something
# on the resulting page that we can wait for
time.sleep(3)

# save a screenshot of the web page
print "Writing screenshot to 'gmail.png'"
sess.render('gmail.png')

########NEW FILE########
__FILENAME__ = google
import dryscrape

search_term = 'dryscrape'

# set up a web scraping session
sess = dryscrape.Session(base_url = 'http://google.com')

# we don't need images
sess.set_attribute('auto_load_images', False)

# visit homepage and search for a term
sess.visit('/')
q = sess.at_xpath('//*[@name="q"]')
q.set(search_term)
q.form().submit()

# extract all links
for link in sess.xpath('//a[@href]'):
  print link['href']

# save a screenshot of the web page
sess.render('google.png')
print "Screenshot written to 'google.png'"

########NEW FILE########
