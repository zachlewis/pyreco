__FILENAME__ = conf
# -*- coding: utf-8 -*-
#
# baidupan documentation build configuration file, created by
# sphinx-quickstart on Sun Sep  1 08:35:14 2013.
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
extensions = ['sphinx.ext.viewcode']

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The encoding of source files.
#source_encoding = 'utf-8-sig'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = u'baidupan'
copyright = u'2013, solos'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = '0.0.1'
# The full version, including alpha/beta/rc tags.
release = '0.0.1'

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
exclude_patterns = []

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

# If true, keep warnings as "system message" paragraphs in the built documents.
#keep_warnings = False


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
htmlhelp_basename = 'baidupandoc'


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
  ('index', 'baidupan.tex', u'baidupan Documentation',
   u'solos', 'manual'),
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
    ('index', 'baidupan', u'baidupan Documentation',
     [u'solos'], 1)
]

# If true, show URL addresses after external links.
#man_show_urls = False


# -- Options for Texinfo output ------------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
  ('index', 'baidupan', u'baidupan Documentation',
   u'solos', 'baidupan', 'One line description of project.',
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
__FILENAME__ = example
#!/usr/bin/env python
#coding=utf-8

import json
from baidupan.baidupan import BaiduPan

if __name__ == '__main__':
    access_token = ''
    disk = BaiduPan(access_token)
    #quota
    print disk.quota()
    #upload
    print disk.upload('hello', path='/apps/appname/hello.txt')
    #merge
    '''
    def merge(self, path, param, **kw):
        self.urlpath = 'file'
        self.method = 'createsuperfile'
        self._method = 'POST'
        return self._request(path=path, param=param, **kw)
    '''
    param = ''
    print disk.merge('/apps/appname/hello.txt', param=param)
    #download
    print disk.download(path='/apps/appname/hello.txt')
    print disk.download(path='/apps/appname/hello.txt',
                        headers={"Range": "Range: bytes:1-100"})
    #mkdir
    print disk.mkdir('/apps/appname/dirname')
    #meta
    print disk.meta('/apps/appname/filename')
    #mmeta
    print disk.mmeta(json.dumps({"list": [{"path": "/apps/appname/"}]}))
    #ls
    print disk.ls("/apps/appname/")
    #mv
    print disk.mv("/apps/appname/hello.txt", "/apps/appname/hello.txt.bak")
    #mmv
    par = {"list": [{"from": "/apps/appname/hello.txt.bak",
                     "to": "/apps/appname/hello.txt.bak.bak"},
                    {"from": "/apps/appname/dirs",
                     "to": "/apps/appname/dirsbak"}]}
    print disk.mmv(json.dumps(par))
    #cp
    print disk.cp("/apps/appname/hello.txt.bak", "/apps/appname/hello.txt")
    #mcp
    par = {"list": [{"path": "/apps/appname/hello.txt1"},
                    {"path": "/apps/appname/dirs"}]}
    print disk.mcp(json.dumps(par))
    #rm
    print disk.rm('/apps/appname/hello.txt.bak')
    #mrm
    par = {"list": [{"path": "/apps/appname/hello.txt1"},
                    {"path": "/apps/appname/dirs"}]}
    print disk.mrm(json.dumps(par))
    #search
    print disk.grep('hello', '/apps/appname/')
    print disk.search('hello', '/apps/appname/')
    #thumb
    print disk.thumb('/apps/appname/1.png', 100, 100)
    #diff
    print disk.diff()
    #streaming
    print disk.streaming('/apps/appname/1.mkv')
    #stream
    print disk.stream(type='doc')
    #downstream
    print disk.downstream('/apps/appname/1.png')
    #rapidsend
    #print disk.rapidsend('/home/solos/1.png', content_length,
    #                     content_md5, slice_md5, content_crc32)
    #add_task
    print disk.add_task('http://www.baidu.com', '/apps/appname/1.html')
    #query_task
    print disk.query_task('3665778', 1)
    #list_task
    print disk.list_task()
    #cancel_task
    print disk.cancel_task('3665778')
    #listrecycle
    print disk.listrecycle()
    #restore
    print disk.restore('4045501009')
    #mrestore
    par = {"list": [{"fs_id": 2263172857}, {"fs_id": 4045501009}]}
    print disk.mrestore(json.dumps(par))
    #emptyrecycle
    print disk.emptyrecycle()

########NEW FILE########
__FILENAME__ = baidupan
#!/usr/bin/env python
#coding=utf-8

import requests


class BaiduPan(object):
    base_url = 'https://pcs.baidu.com/rest/2.0/pcs/'
    method = ''
    params = {}
    payload = {}
    headers = {}
    files = None

    def __init__(self, access_token=''):
        self.access_token = access_token

    def _request(self, **kw):
        if 'file' in kw:
            self.files = {'files': (kw['filename'], kw['file'])}
            del kw['file']
        if 'headers' in kw:
            self.headers = kw['headers']
            del kw['headers']
        if 'from_path' in kw:
            kw['from'] = kw['from_path']
            del kw['from_path']
        for keyword in ['content_length',
                        'content_md5',
                        'slice_md5',
                        'content_crc32']:
            try:
                kw[keyword.replace('_', '-')] = kw[keyword]
                del kw[keyword]
            except KeyError:
                continue

        self.params.update(method=self.method)
        self.params.update(access_token=self.access_token)
        self.params.update(kw)
        self.url = ''.join([self.base_url, self.urlpath])
        if self._method == 'GET':
            try:
                r = requests.get(self.url, params=self.params,
                                 headers=self.headers)
                return r.content
            except Exception, e:
                print e
                return None
        elif self._method == 'POST':
            if self.files:
                try:
                    r = requests.post(self.url,
                                      files=self.files,
                                      params=self.params,
                                      headers=self.headers)
                    return r.content
                except Exception, e:
                    print e
                    return None
            else:
                if self.payload:
                    try:
                        r = requests.post(self.url,
                                          data=self.payload,
                                          params=self.params,
                                          headers=self.headers)
                        return r.content
                    except Exception, e:
                        print e
                        return None
                else:
                    try:
                        r = requests.post(self.url, params=self.params,
                                          headers=self.headers)
                        return r.content
                    except Exception, e:
                        print e
                        return None
        else:
            raise Exception("Method Not Allowed: %s" % self._method)

    def quota(self, **kw):
        self.urlpath = 'quota'
        self.method = 'info'
        self._method = 'GET'
        return self._request(**kw)

    def upload(self, filename, **kw):
        self.urlpath = 'file'
        self.method = 'upload'
        self._method = 'POST'
        try:
            f = open(filename, 'rb').read()
        except Exception, e:
            print e
            raise
        return self._request(filename=filename, file=f, **kw)

    def merge(self, path, param, **kw):
        self.urlpath = 'file'
        self.method = 'createsuperfile'
        self._method = 'POST'
        return self._request(path=path, param=param, **kw)

    def download(self, path, **kw):
        self.urlpath = 'file'
        self.method = 'download'
        self._method = 'GET'
        return self._request(path=path, **kw)

    def mkdir(self, path, **kw):
        self.urlpath = 'file'
        self.method = 'mkdir'
        self._method = 'POST'
        return self._request(path=path, **kw)

    def meta(self, path, **kw):
        self.urlpath = 'file'
        self.method = 'meta'
        self._method = 'POST'
        return self._request(path=path, **kw)

    def mmeta(self, param, **kw):
        self.urlpath = 'file'
        self.method = 'meta'
        self._method = 'POST'
        return self._request(param=param, **kw)

    def ls(self, path, **kw):
        self.urlpath = 'file'
        self.method = 'list'
        self._method = 'POST'
        return self._request(path=path, **kw)

    def mv(self, from_path, to_path, **kw):
        self.urlpath = 'file'
        self.method = 'move'
        self._method = 'POST'
        return self._request(from_path=from_path, to=to_path, **kw)

    def mmv(self, param, **kw):
        self.urlpath = 'file'
        self.method = 'move'
        self._method = 'POST'
        return self._request(param=param, **kw)

    def cp(self, from_path, to_path, **kw):
        self.urlpath = 'file'
        self.method = 'copy'
        self._method = 'POST'
        return self._request(from_path=from_path, to=to_path, **kw)

    def mcp(self, param, **kw):
        self.urlpath = 'file'
        self.method = 'copy'
        self._method = 'POST'
        return self._request(param=param, **kw)

    def rm(self, path, **kw):
        self.urlpath = 'file'
        self.method = 'delete'
        self._method = 'POST'
        return self._request(path=path, **kw)

    def mrm(self, path, **kw):
        self.urlpath = 'file'
        self.method = 'delete'
        self._method = 'POST'
        return self._request(path=path, **kw)

    def grep(self, word, path, **kw):
        self.urlpath = 'file'
        self.method = 'search'
        self._method = 'POST'
        return self._request(wd=word, path=path, **kw)

    def search(self, word, path, **kw):
        self.urlpath = 'file'
        self.method = 'search'
        self._method = 'POST'
        return self._request(wd=word, path=path, **kw)

    def thumb(self, path, height, width, **kw):
        self.urlpath = 'thumbnail'
        self.method = 'generate'
        self._method = 'GET'
        return self._request(path=path, height=height, width=width, **kw)

    def diff(self, cursor='null', **kw):
        self.urlpath = 'file'
        self.method = 'diff'
        self._method = 'GET'
        return self._request(cursor=cursor, **kw)

    def streaming(self, path, type='M3U8_480_360', **kw):
        self.urlpath = 'file'
        self.method = 'streaming'
        self._method = 'GET'
        return self._request(path=path, type=type, **kw)

    def stream(self, type, **kw):
        self.urlpath = 'stream'
        self.method = 'list'
        self._method = 'GET'
        return self._request(type=type, **kw)

    def downstream(self, path, **kw):
        self.urlpath = 'file'
        self.method = 'download'
        self._method = 'GET'
        return self._request(path=path, **kw)

    def rapidsend(self, path, content_length,
                  content_md5, slice_md5, content_crc32, **kw):
        self.urlpath = 'file'
        self.method = 'rapidupload'
        self._method = 'POST'
        return self._request(path=path, content_length=content_length,
                             content_md5=content_md5, slice_md5=slice_md5,
                             content_crc32=content_crc32, **kw)

    def add_task(self, url, path, **kw):
        self.urlpath = 'services/cloud_dl'
        self.method = 'add_task'
        self._method = 'POST'
        return self._request(source_url=url, save_path=path, **kw)

    def query_task(self, task_ids, op_type, **kw):
        self.urlpath = 'services/cloud_dl'
        self.method = 'query_task'
        self._method = 'POST'
        return self._request(task_ids=task_ids, op_type=op_type, **kw)

    def list_task(self, **kw):
        self.urlpath = 'services/cloud_dl'
        self.method = 'list_task'
        self._method = 'POST'
        return self._request(**kw)

    def cancel_task(self, task_id, **kw):
        self.urlpath = 'services/cloud_dl'
        self.method = 'cancel_task'
        self._method = 'POST'
        return self._request(task_id=task_id, **kw)

    def listrecycle(self, **kw):
        self.urlpath = 'file'
        self.method = 'listrecycle'
        self._method = 'GET'
        return self._request(**kw)

    def restore(self, fs_id, **kw):
        self.urlpath = 'file'
        self.method = 'restore'
        self._method = 'POST'
        return self._request(fs_id=fs_id, **kw)

    def mrestore(self, param, **kw):
        self.urlpath = 'file'
        self.method = 'restore'
        self._method = 'POST'
        return self._request(param=param, **kw)

    def emptyrecycle(self, **kw):
        self.urlpath = 'file'
        self.method = 'delete'
        self._method = 'POST'
        return self._request(type='recycle', **kw)

########NEW FILE########
__FILENAME__ = test_baidupan

# -*- coding:utf-8 -*-

import sys
sys.path.append('../src/')

import baidupan
import unittest


class DefaultTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_version(self):
        self.assertIsNotNone(baidupan.__version__, '0.0.1')


def suite():
    suite = unittest.TestSuite()
    suite.addTest(DefaultTestCase('test_version'))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite', verbosity=2)

########NEW FILE########
