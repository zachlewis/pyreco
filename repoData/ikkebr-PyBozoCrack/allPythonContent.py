__FILENAME__ = conf
#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# complexity documentation build configuration file, created by
# sphinx-quickstart on Tue Jul  9 22:26:36 2013.
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

# If extensions (or modules to document with autodoc) are in another
# directory, add these directories to sys.path here. If the directory is
# relative to the documentation root, use os.path.abspath to make it
# absolute, like shown here.
#sys.path.insert(0, os.path.abspath('.'))

# Get the project root dir, which is the parent dir of this
cwd = os.getcwd()
project_root = os.path.dirname(cwd)

# Insert the project root dir as the first element in the PYTHONPATH.
# This lets us ensure that the source package is imported, and that its
# version is used.
sys.path.insert(0, project_root)

import pybozocrack

# -- General configuration ---------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
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
project = u'PyBozoCrack'
copyright = u'2014, Henrique Pereira'

# The version info for the project you're documenting, acts as replacement
# for |version| and |release|, also used in various other places throughout
# the built documents.
#
# The short X.Y version.
version = pybozocrack.__version__
# The full version, including alpha/beta/rc tags.
release = pybozocrack.__version__

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#language = None

# There are two options for replacing |today|: either, you set today to
# some non-false value, then it is used:
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

# If true, keep warnings as "system message" paragraphs in the built
# documents.
#keep_warnings = False


# -- Options for HTML output -------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
html_theme = 'default'

# Theme options are theme-specific and customize the look and feel of a
# theme further.  For a list of options available for each theme, see the
# documentation.
#html_theme_options = {}

# Add any paths that contain custom themes here, relative to this directory.
#html_theme_path = []

# The name for this set of Sphinx documents.  If None, it defaults to
# "<project> v<release> documentation".
#html_title = None

# A shorter title for the navigation bar.  Default is the same as
# html_title.
#html_short_title = None

# The name of an image file (relative to this directory) to place at the
# top of the sidebar.
#html_logo = None

# The name of an image file (within the static path) to use as favicon
# of the docs.  This file should be a Windows icon file (.ico) being
# 16x16 or 32x32 pixels large.
#html_favicon = None

# Add any paths that contain custom static files (such as style sheets)
# here, relative to this directory. They are copied after the builtin
# static files, so a file named "default.css" will overwrite the builtin
# "default.css".
html_static_path = ['_static']

# If not '', a 'Last updated on:' timestamp is inserted at every page
# bottom, using the given strftime format.
#html_last_updated_fmt = '%b %d, %Y'

# If true, SmartyPants will be used to convert quotes and dashes to
# typographically correct entities.
#html_use_smartypants = True

# Custom sidebar templates, maps document names to template names.
#html_sidebars = {}

# Additional templates that should be rendered to pages, maps page names
# to template names.
#html_additional_pages = {}

# If false, no module index is generated.
#html_domain_indices = True

# If false, no index is generated.
#html_use_index = True

# If true, the index is split into individual pages for each letter.
#html_split_index = False

# If true, links to the reST sources are added to the pages.
#html_show_sourcelink = True

# If true, "Created using Sphinx" is shown in the HTML footer.
# Default is True.
#html_show_sphinx = True

# If true, "(C) Copyright ..." is shown in the HTML footer.
# Default is True.
#html_show_copyright = True

# If true, an OpenSearch description file will be output, and all pages
# will contain a <link> tag referring to it.  The value of this option
# must be the base URL from which the finished HTML is served.
#html_use_opensearch = ''

# This is the file name suffix for HTML files (e.g. ".xhtml").
#html_file_suffix = None

# Output file base name for HTML help builder.
htmlhelp_basename = 'pybozocrackdoc'


# -- Options for LaTeX output ------------------------------------------

latex_elements = {
    # The paper size ('letterpaper' or 'a4paper').
    #'papersize': 'letterpaper',

    # The font size ('10pt', '11pt' or '12pt').
    #'pointsize': '10pt',

    # Additional stuff for the LaTeX preamble.
    #'preamble': '',
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass
# [howto/manual]).
latex_documents = [
    ('index', 'pybozocrack.tex',
     u'PyBozoCrack Documentation',
     u'Henrique Pereira', 'manual'),
]

# The name of an image file (relative to this directory) to place at
# the top of the title page.
#latex_logo = None

# For "manual" documents, if this is true, then toplevel headings
# are parts, not chapters.
#latex_use_parts = False

# If true, show page references after internal links.
#latex_show_pagerefs = False

# If true, show URL addresses after external links.
#latex_show_urls = False

# Documents to append as an appendix to all manuals.
#latex_appendices = []

# If false, no module index is generated.
#latex_domain_indices = True


# -- Options for manual page output ------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    ('index', 'pybozocrack',
     u'PyBozoCrack Documentation',
     [u'Henrique Pereira'], 1)
]

# If true, show URL addresses after external links.
#man_show_urls = False


# -- Options for Texinfo output ----------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    ('index', 'pybozocrack',
     u'PyBozoCrack Documentation',
     u'Henrique Pereira',
     'pybozocrack',
     'One line description of project.',
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
__FILENAME__ = pybozocrack
#!/usr/bin/env python
import hashlib
import re
from urllib import FancyURLopener
import sys
from optparse import OptionParser

HASH_REGEX = re.compile("([a-fA-F0-9]{32})")


class MyOpener(FancyURLopener):
    version = 'Mozilla/5.0 (Windows; U; Windows NT 5.1; it; rv:1.8.1.11) Gecko/20071127 Firefox/2.0.0.11'


def dictionary_attack(h, wordlist):
    for word in wordlist:
        if hashlib.md5(word).hexdigest() == h:
            return word

    return None


def format_it(hash, plaintext):
    return "{hash}:{plaintext}".format(hash=hash, plaintext=plaintext)


def crack_single_hash(h):
    myopener = MyOpener()
    response = myopener.open(
        "http://www.google.com/search?q={hash}".format(hash=h))

    wordlist = response.read().replace('.', ' ').replace(
        ':', ' ').replace('?', '').replace("('", ' ').replace("'", ' ').split(' ')
    plaintext = dictionary_attack(h, set(wordlist))

    return plaintext


class BozoCrack(object):

    def __init__(self, filename, *args, **kwargs):
        self.hashes = []

        with open(filename, 'r') as f:
            hashes = [h.lower() for line in f if HASH_REGEX.match(line)
                      for h in HASH_REGEX.findall(line.replace('\n', ''))]

        self.hashes = sorted(set(hashes))

        print "Loaded {count} unique hashes".format(count=len(self.hashes))

        self.cache = self.load_cache()

    def crack(self):
        cracked_hashes = []
        for h in self.hashes:
            if h in self.cache:
                print format_it(h, self.cache[h])
                cracked_hashes.append( (h, self.cache[h]) )
                continue

            plaintext = crack_single_hash(h)

            if plaintext:
                print format_it(h, plaintext)
                self.cache[h] = plaintext
                self.append_to_cache(h, plaintext)
                cracked_hashes.append( (h, plaintext) )

        return cracked_hashes

    def load_cache(self, filename='cache'):
        cache = {}
        with open(filename, 'a+') as c:
            for line in c:
                hash, plaintext = line.replace('\n', '').split(':', 1)
                cache[hash] = plaintext
        return cache

    def append_to_cache(self, h, plaintext, filename='cache'):
        with open(filename, 'a+') as c:
            c.write(format_it(hash=h, plaintext=plaintext)+"\n")


def main(): # pragma: no cover
    parser = OptionParser()
    parser.add_option('-s', '--single', metavar='MD5HASH',
                      help='cracks a single hash', dest='single', default=False)
    parser.add_option('-f', '--file', metavar='HASHFILE',
                      help='cracks multiple hashes on a file', dest='target',)

    options, args = parser.parse_args()

    if not options.single and not options.target:
        parser.error("please select -s or -f")
    elif options.single:
        plaintext = crack_single_hash(options.single)

        if plaintext:
            print format_it(hash=options.single, plaintext=plaintext)
    else:
        cracked = BozoCrack(options.target).crack()
        if not cracked:
            print "No hashes were cracked."

if __name__ == '__main__': # pragma: no cover
    main()

########NEW FILE########
__FILENAME__ = test_pybozocrack
#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_pybozocrack
----------------------------------

Tests for `pybozocrack` module.
"""

import unittest
import sys
import pybozocrack


class TestPybozocrack(unittest.TestCase):
	
    def setUp(self):
        self.hash = "d0763edaa9d9bd2a9516280e9044d885"
        self.plaintext = "monkey"

        file = open('test', 'w')
        file.write('fcf1eed8596699624167416a1e7e122e\nbed128365216c019988915ed3add75fb')
        file.close()
		
        file = open('cache', 'w')
        file.write('1:2\n')
        file.close()

        self.cracker = pybozocrack.BozoCrack('test')


    def test_loaded_hashes(self):
        self.assertEqual(len(self.cracker.hashes), 2)

    def test_load_empty_cache(self):
        self.assertEqual(self.cracker.load_cache('empty'), {})

    @unittest.skipIf('PyPy' in sys.version, "Test is broken on PyPy")
    def test_append_to_cache(self):
        self.cracker.append_to_cache('1', '2', 'cache')
        self.assertEqual(self.cracker.load_cache('cache'), {'1': '2'})
		
    def test_crack(self):
        self.cracker.hashes = [self.hash,]
        result = self.cracker.crack()
        self.assertEqual( self.cracker.cache[self.cracker.hashes[0]], self.plaintext )
        # cache test
        self.cracker.hashes = [self.hash,]
        result = self.cracker.crack()
        self.assertEqual( len(result), 1)

        
    def test_dictionary_attack_known_hash(self):
        self.assertEqual(pybozocrack.dictionary_attack(self.hash, ['zebra', '123', self.plaintext]), self.plaintext)
		
    def test_dictionary_attack_invalid_hash(self):
        self.assertIsNone(pybozocrack.dictionary_attack(self.hash, ['zebra', '123']))
		
    def test_format_it(self):
        self.assertEqual(pybozocrack.format_it(self.hash, self.plaintext), "{}:{}".format(self.hash, self.plaintext))

    def test_crack_single_hash(self):
        self.assertEqual(pybozocrack.crack_single_hash(self.hash), self.plaintext)

    def tearDown(self):
        pass

if __name__ == '__main__':
    unittest.main()

########NEW FILE########
