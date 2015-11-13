__FILENAME__ = conf
# -*- coding: utf-8 -*-
#
# Flask-WhooshAlchemy documentation build configuration file, created by
# sphinx-quickstart on Fri May 18 11:36:44 2012.
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
sys.path.insert(0, os.path.abspath('..'))

# -- General configuration -----------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#needs_sphinx = '1.0'


# Add any Sphinx extension module names here, as strings. They can be extensions
# coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = ['sphinx.ext.autodoc', 'sphinx.ext.doctest', 'sphinx.ext.intersphinx', 'sphinx.ext.todo', 'sphinx.ext.coverage']

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The encoding of source files.
#source_encoding = 'utf-8-sig'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = u'Flask-WhooshAlchemy'
copyright = u'2012, Karl Gyllstrom'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = '0.4a'
# The full version, including alpha/beta/rc tags.
release = '0.4a'

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
#

sys.path.append(os.path.abspath('_themes'))
html_theme_path = ['_themes']
html_theme = 'flask_small'

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
html_show_copyright = True

# If true, an OpenSearch description file will be output, and all pages will
# contain a <link> tag referring to it.  The value of this option must be the
# base URL from which the finished HTML is served.
#html_use_opensearch = ''

# This is the file name suffix for HTML files (e.g. ".xhtml").
#html_file_suffix = None

# Output file base name for HTML help builder.
htmlhelp_basename = 'Flask-WhooshAlchemydoc'


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
  ('index', 'Flask-WhooshAlchemy.tex', u'Flask-WhooshAlchemy Documentation',
   u'Karl Gyllstrom', 'manual'),
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
    ('index', 'flask-whooshalchemy', u'Flask-WhooshAlchemy Documentation',
     [u'Karl Gyllstrom'], 1)
]

# If true, show URL addresses after external links.
#man_show_urls = False


# -- Options for Texinfo output ------------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
  ('index', 'Flask-WhooshAlchemy', u'Flask-WhooshAlchemy Documentation',
   u'Karl Gyllstrom', 'Flask-WhooshAlchemy', 'One line description of project.',
   'Miscellaneous'),
]

# Documents to append as an appendix to all manuals.
#texinfo_appendices = []

# If false, no module index is generated.
#texinfo_domain_indices = True

# How to display URL addresses: 'footnote', 'no', or 'inline'.
#texinfo_show_urls = 'footnote'


# Example configuration for intersphinx: refer to the Python standard library.
intersphinx_mapping = {'http://docs.python.org/': None,
                       'http://flask.pocoo.org/docs/': None,
                       'http://www.sqlalchemy.org/docs/': None}

########NEW FILE########
__FILENAME__ = flask_whooshalchemy
'''

    whooshalchemy flask extension
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Adds whoosh indexing capabilities to SQLAlchemy models for Flask
    applications.

    :copyright: (c) 2012 by Karl Gyllstrom
    :license: BSD (see LICENSE.txt)

'''

from __future__ import with_statement
from __future__ import absolute_import


import flask.ext.sqlalchemy as flask_sqlalchemy

import sqlalchemy

from whoosh.qparser import OrGroup
from whoosh.qparser import AndGroup
from whoosh.qparser import MultifieldParser
from whoosh.analysis import StemmingAnalyzer
import whoosh.index
from whoosh.fields import Schema
#from whoosh.fields import ID, TEXT, KEYWORD, STORED

import heapq
import os


__searchable__ = '__searchable__'


DEFAULT_WHOOSH_INDEX_NAME = 'whoosh_index'


class _QueryProxy(flask_sqlalchemy.BaseQuery):
    # We're replacing the model's ``query`` field with this proxy. The main
    # thing this proxy does is override the __iter__ method so that results are
    # returned in the order of the whoosh score to reflect text-based ranking.

    def __init__(self, entities, session=None):
        super(_QueryProxy, self).__init__(entities, session)

        self._modelclass = self._mapper_zero().class_
        self._primary_key_name = self._modelclass.whoosh_primary_key
        self._whoosh_searcher = self._modelclass.pure_whoosh

        # Stores whoosh results from query. If ``None``, indicates that no
        # whoosh query was performed.
        self._whoosh_rank = None

    def __iter__(self):
        ''' Reorder ORM-db results according to Whoosh relevance score. '''

        super_iter = super(_QueryProxy, self).__iter__()

        if self._whoosh_rank is None:
            # Whoosh search hasn't been run so behave as normal.

            return super_iter

        # Iterate through the values and re-order by whoosh relevance.
        ordered_by_whoosh_rank = []

        for row in super_iter:
            # Push items onto heap, where sort value is the rank provided by
            # Whoosh

            heapq.heappush(ordered_by_whoosh_rank,
                (self._whoosh_rank[unicode(getattr(row,
                    self._primary_key_name))], row))

        def _inner():
            while ordered_by_whoosh_rank:
                yield heapq.heappop(ordered_by_whoosh_rank)[1]

        return _inner()

    def whoosh_search(self, query, limit=None, fields=None, or_=False):
        '''

        Execute text query on database. Results have a text-based
        match to the query, ranked by the scores from the underlying Whoosh
        index.

        By default, the search is executed on all of the indexed fields as an
        OR conjunction. For example, if a model has 'title' and 'content'
        indicated as ``__searchable__``, a query will be checked against both
        fields, returning any instance whose title or content are a content
        match for the query. To specify particular fields to be checked,
        populate the ``fields`` parameter with the desired fields.

        By default, results will only be returned if they contain all of the
        query terms (AND). To switch to an OR grouping, set the ``or_``
        parameter to ``True``.

        '''
            
        if not isinstance(query, unicode):
            query = unicode(query)

        results = self._whoosh_searcher(query, limit, fields, or_)

        if not results:
            # We don't want to proceed with empty results because we get a
            # stderr warning from sqlalchemy when executing 'in_' on empty set.
            # However we cannot just return an empty list because it will not
            # be a query.

            # XXX is this efficient?
            return self.filter('null')

        result_set = set()
        result_ranks = {}

        for rank, result in enumerate(results):
            pk = result[self._primary_key_name]
            result_set.add(pk)
            result_ranks[pk] = rank

        f = self.filter(getattr(self._modelclass,
            self._primary_key_name).in_(result_set))

        f._whoosh_rank = result_ranks

        return f


class _Searcher(object):
    ''' Assigned to a Model class as ``pure_search``, which enables
    text-querying to whoosh hit list. Also used by ``query.whoosh_search``'''

    def __init__(self, primary, indx):
        self.primary_key_name = primary
        self._index = indx
        self.searcher = indx.searcher()
        self._all_fields = list(set(indx.schema._fields.keys()) -
                set([self.primary_key_name]))

    def __call__(self, query, limit=None, fields=None, or_=False):
        if fields is None:
            fields = self._all_fields

        group = OrGroup if or_ else AndGroup
        parser = MultifieldParser(fields, self._index.schema, group=group)
        return self._index.searcher().search(parser.parse(query),
                limit=limit)


def whoosh_index(app, model):
    ''' Create whoosh index for ``model``, if one does not exist. If 
    the index exists it is opened and cached. '''

    # gets the whoosh index for this model, creating one if it does not exist.
    # A dict of model -> whoosh index is added to the ``app`` variable.

    if not hasattr(app, 'whoosh_indexes'):
        app.whoosh_indexes = {}

    return app.whoosh_indexes.get(model.__name__,
                _create_index(app, model))


def _create_index(app, model):
    # a schema is created based on the fields of the model. Currently we only
    # support primary key -> whoosh.ID, and sqlalchemy.(String, Unicode, Text)
    # -> whoosh.TEXT.

    if not app.config.get('WHOOSH_BASE'):
        # XXX todo: is there a better approach to handle the absenSe of a
        # config value for whoosh base? Should we throw an exception? If
        # so, this exception will be thrown in the after_commit function,
        # which is probably not ideal.

        app.config['WHOOSH_BASE'] = DEFAULT_WHOOSH_INDEX_NAME

    # we index per model.
    wi = os.path.join(app.config.get('WHOOSH_BASE'),
            model.__name__)

    schema, primary_key = _get_whoosh_schema_and_primary_key(model)

    if whoosh.index.exists_in(wi):
        indx = whoosh.index.open_dir(wi)
    else:
        if not os.path.exists(wi):
            os.makedirs(wi)
        indx = whoosh.index.create_in(wi, schema)

    app.whoosh_indexes[model.__name__] = indx

    model.pure_whoosh = _Searcher(primary_key, indx)
    model.whoosh_primary_key = primary_key

    # change the query class of this model to our own
    model.query_class = _QueryProxy
    
    return indx


def _get_whoosh_schema_and_primary_key(model):
    schema = {}
    primary = None
    searchable = set(model.__searchable__)
    for field in model.__table__.columns:
        if field.primary_key:
            schema[field.name] = whoosh.fields.ID(stored=True, unique=True)
            primary = field.name

        if field.name in searchable and isinstance(field.type,
                (sqlalchemy.types.Text, sqlalchemy.types.String,
                    sqlalchemy.types.Unicode)):

            schema[field.name] = whoosh.fields.TEXT(
                    analyzer=StemmingAnalyzer())

    return Schema(**schema), primary


def _after_flush(app, changes):
    # Any db updates go through here. We check if any of these models have
    # ``__searchable__`` fields, indicating they need to be indexed. With these
    # we update the whoosh index for the model. If no index exists, it will be
    # created here; this could impose a penalty on the initial commit of a
    # model.

    bytype = {}  # sort changes by type so we can use per-model writer
    for change in changes:
        update = change[1] in ('update', 'insert')

        if hasattr(change[0].__class__, __searchable__):
            bytype.setdefault(change[0].__class__.__name__, []).append((update,
                change[0]))

    for model, values in bytype.iteritems():
        index = whoosh_index(app, values[0][1].__class__)
        with index.writer() as writer:
            primary_field = values[0][1].pure_whoosh.primary_key_name
            searchable = values[0][1].__searchable__

            for update, v in values:
                if update:
                    attrs = {}
                    for key in searchable:
                        try:
                            attrs[key] = unicode(getattr(v, key))
                        except AttributeError:
                            raise AttributeError('{0} does not have {1} field {2}'
                                    .format(model, __searchable__, key))

                    attrs[primary_field] = unicode(getattr(v, primary_field))
                    writer.update_document(**attrs)
                else:
                    writer.delete_by_term(primary_field, unicode(getattr(v,
                        primary_field)))


flask_sqlalchemy.models_committed.connect(_after_flush)


# def init_app(db):
#     app = db.get_app()
# #    for table in db.get_tables_for_bind():
#     for item in globals():
# 
#        #_create_index(app, table)

########NEW FILE########
__FILENAME__ = test_all
'''

    whooshalchemy flask extension
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Adds whoosh indexing capabilities to SQLAlchemy models for Flask
    applications.

    :copyright: (c) 2012 by Karl Gyllstrom
    :license: BSD (see LICENSE.txt)

'''

from __future__ import absolute_import

from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.testing import TestCase
import flask.ext.whooshalchemy as wa

import datetime
import os
import tempfile
import shutil


db = SQLAlchemy()


class BlogishBlob(object):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.Text)
    content = db.Column(db.String)
    blurb = db.Column(db.Unicode)
    ignored = db.Column(db.Unicode)
    created = db.Column(db.DateTime(), default=datetime.datetime.utcnow())

    def __repr__(self):
        return '{0}(title={1})'.format(self.__class__.__name__, self.title)


def _after_flush(app, changes):
    from sqlalchemy.orm import EXT_CONTINUE
    return EXT_CONTINUE


class ObjectA(db.Model, BlogishBlob):
    __tablename__ = 'objectA'
    __searchable__ = ['title', 'content', 'blurb']


class ObjectB(db.Model, BlogishBlob):
    __tablename__ = 'objectB'
    __searchable__ = ['title', 'content', 'content']  # dup intentional


class ObjectC(db.Model, BlogishBlob):
    __tablename__ = 'objectC'
    __searchable__ = ['title', 'field_that_doesnt_exist']


class Tests(TestCase):
    DATABASE_URL = 'sqlite://'
    TESTING = True

    def create_app(self):
        tmp_dir = tempfile.mkdtemp()

        app = Flask(__name__)

        app.config['WHOOSH_BASE'] = os.path.join(tmp_dir, 'whoosh')

        return app

    def setUp(self):
        db.init_app(self.app)
        db.create_all()

    def tearDown(self):
        try:
            shutil.rmtree(self.app.config['WHOOSH_BASE'])
        except OSError, e:
            if e.errno != 2:  # code 2 - no such file or directory
                raise

        db.drop_all()

    def test_flask_fail(self):
        # XXX This fails due to a bug in Flask-SQLAlchemy that affects
        # Flask-WhooshAlchemy. I submitted a pull request with a fix that is
        # pending.

        from flask.ext.sqlalchemy import before_models_committed, models_committed
        
        before_models_committed.connect(_after_flush)
        models_committed.connect(_after_flush)
        db.session.add(ObjectB(title=u'my title', content=u'hello world'))
        db.session.add(ObjectA(title=u'a title', content=u'hello world'))
        db.session.flush()
        db.session.commit()

    def test_all(self):
        title1 = u'a slightly long title'
        title2 = u'another title'
        title3 = u'wow another title'

        obj = ObjectA(title=u'title', blurb='this is a blurb')
        db.session.add(obj)
        db.session.commit()

        self.assertEqual(len(list(ObjectA.query.whoosh_search('blurb'))), 1)
        db.session.delete(obj)
        db.session.commit()

        db.session.add(ObjectA(title=title1, content=u'hello world', ignored=u'no match'))
        db.session.commit()

        self.assertEqual(len(list(ObjectA.query.whoosh_search('what'))), 0)
        self.assertEqual(len(list(ObjectA.query.whoosh_search(u'no match'))), 0)
        self.assertEqual(len(list(ObjectA.query.whoosh_search(u'title'))), 1)
        self.assertEqual(len(list(ObjectA.query.whoosh_search(u'hello'))), 1)

        db.session.add(ObjectB(title=u'my title', content=u'hello world'))
        db.session.commit()

        db.session.add(ObjectC(title=u'my title', content=u'hello world'))
        self.assertRaises(AttributeError, db.session.commit)
        db.session.rollback()


        # make sure does not interfere with ObjectA's results
        self.assertEqual(len(list(ObjectA.query.whoosh_search(u'what'))), 0)
        self.assertEqual(len(list(ObjectA.query.whoosh_search(u'title'))), 1)
        self.assertEqual(len(list(ObjectA.query.whoosh_search(u'hello'))), 1)

        self.assertEqual(len(list(ObjectB.query.whoosh_search(u'what'))), 0)
        self.assertEqual(len(list(ObjectB.query.whoosh_search(u'title'))), 1)
        self.assertEqual(len(list(ObjectB.query.whoosh_search(u'hello'))), 1)

        obj2 = ObjectA(title=title2, content=u'a different message')
        db.session.add(obj2)
        db.session.commit()

        self.assertEqual(len(list(ObjectA.query.whoosh_search(u'what'))), 0)
        l = list(ObjectA.query.whoosh_search(u'title'))
        self.assertEqual(len(l), 2)

        # ranking should always be as follows, since title2 should have a higher relevance score

        self.assertEqual(l[0].title, title2)
        self.assertEqual(l[1].title, title1)

        self.assertEqual(len(list(ObjectA.query.whoosh_search(u'hello'))), 1)
        self.assertEqual(len(list(ObjectA.query.whoosh_search(u'message'))), 1)

        self.assertEqual(len(list(ObjectB.query.whoosh_search(u'what'))), 0)
        self.assertEqual(len(list(ObjectB.query.whoosh_search(u'title'))), 1)
        self.assertEqual(len(list(ObjectB.query.whoosh_search(u'hello'))), 1)
        self.assertEqual(len(list(ObjectB.query.whoosh_search(u'message'))), 0)

        db.session.add(ObjectA(title=title3, content=u'a different message'))
        db.session.commit()

        l = list(ObjectA.query.whoosh_search(u'title'))
        self.assertEqual(len(l), 3)
        self.assertEqual(l[0].title, title2)
        self.assertEqual(l[1].title, title3)
        self.assertEqual(l[2].title, title1)

        db.session.delete(obj2)
        db.session.commit()

        l = list(ObjectA.query.whoosh_search(u'title'))
        self.assertEqual(len(l), 2)
        self.assertEqual(l[0].title, title3)
        self.assertEqual(l[1].title, title1)

        two_days_ago = datetime.date.today() - datetime.timedelta(2)

        title4 = u'a title that is significantly longer than the others'

        db.session.add(ObjectA(title=title4, created=two_days_ago))
        db.session.commit()

        one_day_ago = datetime.date.today() - datetime.timedelta(1)

        recent = list(ObjectA.query.whoosh_search(u'title')
                .filter(ObjectA.created >= one_day_ago))

        self.assertEqual(len(recent), 2)
        self.assertEqual(l[0].title, title3)
        self.assertEqual(l[1].title, title1)

        three_days_ago = datetime.date.today() - datetime.timedelta(3)

        l = list(ObjectA.query.whoosh_search(u'title')
                .filter(ObjectA.created >= three_days_ago))

        self.assertEqual(len(l), 3)
        self.assertEqual(l[0].title, title3)
        self.assertEqual(l[1].title, title1)
        self.assertEqual(l[2].title, title4)

        title5 = u'title with title as frequent title word'

        db.session.add(ObjectA(title=title5))
        db.session.commit()

        l = list(ObjectA.query.whoosh_search(u'title'))
        self.assertEqual(len(l), 4)
        self.assertEqual(l[0].title, title5)
        self.assertEqual(l[1].title, title3)
        self.assertEqual(l[2].title, title1)
        self.assertEqual(l[3].title, title4)

        # test limit
        l = list(ObjectA.query.whoosh_search(u'title', limit=2))
        self.assertEqual(len(l), 2)
        self.assertEqual(l[0].title, title5)
        self.assertEqual(l[1].title, title3)

        # XXX should replace this with a new function, but I can't figure out
        # how to do this cleanly with flask sqlalchemy and testing

        db.drop_all()
        db.create_all()

        title1 = u'my title'
        db.session.add(ObjectA(title=title1, content=u'hello world'))
        db.session.commit()

        l = list(ObjectA.query.whoosh_search(u'title'))
        self.assertEqual(len(l), 1)

        l = list(ObjectA.query.whoosh_search(u'hello'))
        self.assertEqual(len(l), 1)

        l = list(ObjectA.query.whoosh_search(u'title', fields=('title',)))
        self.assertEqual(len(l), 1)
        l = list(ObjectA.query.whoosh_search(u'hello', fields=('title',)))
        self.assertEqual(len(l), 0)

        l = list(ObjectA.query.whoosh_search(u'title', fields=('content',)))
        self.assertEqual(len(l), 0)
        l = list(ObjectA.query.whoosh_search(u'hello', fields=('content',)))
        self.assertEqual(len(l), 1)

        l = list(ObjectA.query.whoosh_search(u'hello dude', fields=('content',), or_=True))
        self.assertEqual(len(l), 1)

        l = list(ObjectA.query.whoosh_search(u'hello dude', fields=('content',), or_=False))
        self.assertEqual(len(l), 0)

        # new function: test chaining
        db.drop_all()
        db.create_all()

        db.session.add(ObjectA(title=u'title one', content=u'a poem'))
        db.session.add(ObjectA(title=u'title two', content=u'about testing'))
        db.session.add(ObjectA(title=u'title three', content=u'is delightfully tested'))
        db.session.add(ObjectA(title=u'four', content=u'tests'))
        db.session.commit()

        self.assertEqual(len(list(ObjectA.query.whoosh_search(u'title'))), 3)
        self.assertEqual(len(list(ObjectA.query.whoosh_search(u'test'))), 3)

        # chained query, operates as AND
        self.assertEqual(len(list(ObjectA.query.whoosh_search(u'title').whoosh_search(u'test'))),
                2)


#         self.assertEqual(len(recent), 1)
#         self.assertEqual(recent[0].title, b.title)
#         old = list(ObjectA.search_query(u'good').filter(ObjectA.created <= datetime.date.today() - datetime.timedelta(1)))
#         self.assertEqual(len(old), 1)
#         self.assertEqual(old[0].title, a.title)


if __name__ == '__main__':
    import unittest
    unittest.main()

########NEW FILE########
