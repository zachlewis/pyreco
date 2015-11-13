__FILENAME__ = conf
# -*- coding: utf-8 -*-
#
# Slumber documentation build configuration file, created by
# sphinx-quickstart on Sun Jul 31 17:42:40 2011.
#
# This file is execfile()d with the current directory set to its containing dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out
# serve to show the default.

import os
import sys

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#sys.path.insert(0, os.path.abspath('.'))

# -- General configuration -----------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be extensions
# coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = ['sphinx.ext.autodoc', 'sphinx.ext.doctest', 'sphinx.ext.coverage', 'sphinx.ext.viewcode']

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The encoding of source files.
#source_encoding = 'utf-8-sig'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = u'Slumber'
copyright = u'2011, Donald Stufft'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = '0.6'
# The full version, including alpha/beta/rc tags.
release = '0.6.1.dev'

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
htmlhelp_basename = 'Slumberdoc'


# -- Options for LaTeX output --------------------------------------------------

# The paper size ('letter' or 'a4').
#latex_paper_size = 'letter'

# The font size ('10pt', '11pt' or '12pt').
#latex_font_size = '10pt'

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass [howto/manual]).
latex_documents = [
  ('index', 'Slumber.tex', u'Slumber Documentation',
   u'Donald Stufft', 'manual'),
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
    ('index', 'slumber', u'Slumber Documentation',
     [u'Donald Stufft'], 1)
]

########NEW FILE########
__FILENAME__ = exceptions
class SlumberBaseException(Exception):
    """
    All Slumber exceptions inherit from this exception.
    """


class SlumberHttpBaseException(SlumberBaseException):
    """
    All Slumber HTTP Exceptions inherit from this exception.
    """

    def __init__(self, *args, **kwargs):
        for key, value in kwargs.iteritems():
            setattr(self, key, value)
        super(SlumberHttpBaseException, self).__init__(*args)


class HttpClientError(SlumberHttpBaseException):
    """
    Called when the server tells us there was a client error (4xx).
    """


class HttpServerError(SlumberHttpBaseException):
    """
    Called when the server tells us there was a server error (5xx).
    """


class SerializerNoAvailable(SlumberBaseException):
    """
    There are no available Serializers.
    """


class SerializerNotAvailable(SlumberBaseException):
    """
    The chosen Serializer is not available.
    """


class ImproperlyConfigured(SlumberBaseException):
    """
    Slumber is somehow improperly configured.
    """

########NEW FILE########
__FILENAME__ = serialize
from slumber import exceptions

_SERIALIZERS = {
    "json": True,
    "yaml": True,
}

try:
    import json
except ImportError:
    _SERIALIZERS["json"] = False

try:
    import yaml
except ImportError:
    _SERIALIZERS["yaml"] = False


class BaseSerializer(object):

    content_types = None
    key = None

    def get_content_type(self):
        if self.content_types is None:
            raise NotImplementedError()
        return self.content_types[0]

    def loads(self, data):
        raise NotImplementedError()

    def dumps(self, data):
        raise NotImplementedError()


class JsonSerializer(BaseSerializer):

    content_types = [
                        "application/json",
                        "application/x-javascript",
                        "text/javascript",
                        "text/x-javascript",
                        "text/x-json",
                    ]
    key = "json"

    def loads(self, data):
        return json.loads(data)

    def dumps(self, data):
        return json.dumps(data)


class YamlSerializer(BaseSerializer):

    content_types = ["text/yaml"]
    key = "yaml"

    def loads(self, data):
        return yaml.safe_load(data)

    def dumps(self, data):
        return yaml.dump(data)


class Serializer(object):

    def __init__(self, default=None, serializers=None):
        if default is None:
            default = "json" if _SERIALIZERS["json"] else "yaml"

        if serializers is None:
            serializers = [x() for x in [JsonSerializer, YamlSerializer] if _SERIALIZERS[x.key]]

        if not serializers:
            raise exceptions.SerializerNoAvailable("There are no Available Serializers.")

        self.serializers = {}

        for serializer in serializers:
            self.serializers[serializer.key] = serializer

        self.default = default

    def get_serializer(self, name=None, content_type=None):
        if name is None and content_type is None:
            return self.serializers[self.default]
        elif name is not None and content_type is None:
            if not name in self.serializers:
                raise exceptions.SerializerNotAvailable("%s is not an available serializer" % name)
            return self.serializers[name]
        else:
            for x in self.serializers.values():
                for ctype in x.content_types:
                    if content_type == ctype:
                        return x
            raise exceptions.SerializerNotAvailable("%s is not an available serializer" % content_type)

    def loads(self, data, format=None):
        s = self.get_serializer(format)
        return s.loads(data)

    def dumps(self, data, format=None):
        s = self.get_serializer(format)
        return s.dumps(data)

    def get_content_type(self, format=None):
        s = self.get_serializer(format)
        return s.get_content_type()

########NEW FILE########
__FILENAME__ = resource
import mock
import unittest
import requests
import slumber
import slumber.serialize


class ResourceTestCase(unittest.TestCase):

    def setUp(self):
        self.base_resource = slumber.Resource(base_url="http://example/api/v1/test", format="json", append_slash=False)

    def test_get_200_json(self):
        r = mock.Mock(spec=requests.Response)
        r.status_code = 200
        r.headers = {"content-type": "application/json"}
        r.content = '{"result": ["a", "b", "c"]}'

        self.base_resource._store.update({
            "session": mock.Mock(spec=requests.Session),
            "serializer": slumber.serialize.Serializer(),
        })
        self.base_resource._store["session"].request.return_value = r

        resp = self.base_resource._request("GET")

        self.assertTrue(resp is r)
        self.assertEqual(resp.content, r.content)

        self.base_resource._store["session"].request.assert_called_once_with(
            "GET",
            "http://example/api/v1/test",
            data=None,
            files=None,
            params=None,
            headers={"content-type": self.base_resource._store["serializer"].get_content_type(), "accept": self.base_resource._store["serializer"].get_content_type()}
        )

        resp = self.base_resource.get()
        self.assertEqual(resp['result'], ['a', 'b', 'c'])

    def test_get_200_text(self):
        r = mock.Mock(spec=requests.Response)
        r.status_code = 200
        r.headers = {"content-type": "text/plain"}
        r.content = "Mocked Content"

        self.base_resource._store.update({
            "session": mock.Mock(spec=requests.Session),
            "serializer": slumber.serialize.Serializer(),
        })
        self.base_resource._store["session"].request.return_value = r

        resp = self.base_resource._request("GET")

        self.assertTrue(resp is r)
        self.assertEqual(resp.content, "Mocked Content")

        self.base_resource._store["session"].request.assert_called_once_with(
            "GET",
            "http://example/api/v1/test",
            data=None,
            files=None,
            params=None,
            headers={"content-type": self.base_resource._store["serializer"].get_content_type(), "accept": self.base_resource._store["serializer"].get_content_type()}
        )

        resp = self.base_resource.get()
        self.assertEqual(resp, r.content)

    def test_post_201_redirect(self):
        r1 = mock.Mock(spec=requests.Response)
        r1.status_code = 201
        r1.headers = {"location": "http://example/api/v1/test/1"}
        r1.content = ''

        r2 = mock.Mock(spec=requests.Response)
        r2.status_code = 200
        r2.headers = {"content-type": "application/json"}
        r2.content = '{"result": ["a", "b", "c"]}'

        self.base_resource._store.update({
            "session": mock.Mock(spec=requests.Session),
            "serializer": slumber.serialize.Serializer(),
        })
        self.base_resource._store["session"].request.side_effect = (r1, r2)

        resp = self.base_resource._request("POST")

        self.assertTrue(resp is r1)
        self.assertEqual(resp.content, r1.content)

        self.base_resource._store["session"].request.assert_called_once_with(
            "POST",
            "http://example/api/v1/test",
            data=None,
            files=None,
            params=None,
            headers={"content-type": self.base_resource._store["serializer"].get_content_type(), "accept": self.base_resource._store["serializer"].get_content_type()}
        )

        resp = self.base_resource.post(data={'foo': 'bar'})
        self.assertEqual(resp['result'], ['a', 'b', 'c'])

    def test_post_decodable_response(self):
        r = mock.Mock(spec=requests.Response)
        r.status_code = 200
        r.content = '{"result": ["a", "b", "c"]}'
        r.headers = {"content-type": "application/json"}

        self.base_resource._store.update({
            "session": mock.Mock(spec=requests.Session),
            "serializer": slumber.serialize.Serializer(),
        })
        self.base_resource._store["session"].request.return_value = r

        resp = self.base_resource._request("POST")

        self.assertTrue(resp is r)
        self.assertEqual(resp.content, r.content)

        self.base_resource._store["session"].request.assert_called_once_with(
            "POST",
            "http://example/api/v1/test",
            data=None,
            files=None,
            params=None,
            headers={"content-type": self.base_resource._store["serializer"].get_content_type(), "accept": self.base_resource._store["serializer"].get_content_type()}
        )

        resp = self.base_resource.post(data={'foo': 'bar'})
        self.assertEqual(resp['result'], ['a', 'b', 'c'])

    def test_patch_201_redirect(self):
        r1 = mock.Mock(spec=requests.Response)
        r1.status_code = 201
        r1.headers = {"location": "http://example/api/v1/test/1"}
        r1.content = ''

        r2 = mock.Mock(spec=requests.Response)
        r2.status_code = 200
        r2.headers = {"content-type": "application/json"}
        r2.content = '{"result": ["a", "b", "c"]}'

        self.base_resource._store.update({
            "session": mock.Mock(spec=requests.Session),
            "serializer": slumber.serialize.Serializer(),
        })
        self.base_resource._store["session"].request.side_effect = (r1, r2)

        resp = self.base_resource._request("PATCH")

        self.assertTrue(resp is r1)
        self.assertEqual(resp.content, r1.content)

        self.base_resource._store["session"].request.assert_called_once_with(
            "PATCH",
            "http://example/api/v1/test",
            data=None,
            files=None,
            params=None,
            headers={"content-type": self.base_resource._store["serializer"].get_content_type(), "accept": self.base_resource._store["serializer"].get_content_type()}
        )

        resp = self.base_resource.patch(data={'foo': 'bar'})
        self.assertEqual(resp['result'], ['a', 'b', 'c'])

    def test_patch_decodable_response(self):
        r = mock.Mock(spec=requests.Response)
        r.status_code = 200
        r.content = '{"result": ["a", "b", "c"]}'
        r.headers = {"content-type": "application/json"}

        self.base_resource._store.update({
            "session": mock.Mock(spec=requests.Session),
            "serializer": slumber.serialize.Serializer(),
        })
        self.base_resource._store["session"].request.return_value = r

        resp = self.base_resource._request("PATCH")

        self.assertTrue(resp is r)
        self.assertEqual(resp.content, r.content)

        self.base_resource._store["session"].request.assert_called_once_with(
            "PATCH",
            "http://example/api/v1/test",
            data=None,
            files=None,
            params=None,
            headers={"content-type": self.base_resource._store["serializer"].get_content_type(), "accept": self.base_resource._store["serializer"].get_content_type()}
        )

        resp = self.base_resource.patch(data={'foo': 'bar'})
        self.assertEqual(resp['result'], ['a', 'b', 'c'])

    def test_put_201_redirect(self):
        r1 = mock.Mock(spec=requests.Response)
        r1.status_code = 201
        r1.headers = {"location": "http://example/api/v1/test/1"}
        r1.content = ''

        r2 = mock.Mock(spec=requests.Response)
        r2.status_code = 200
        r2.headers = {"content-type": "application/json"}
        r2.content = '{"result": ["a", "b", "c"]}'

        self.base_resource._store.update({
            "session": mock.Mock(spec=requests.Session),
            "serializer": slumber.serialize.Serializer(),
        })
        self.base_resource._store["session"].request.side_effect = (r1, r2)

        resp = self.base_resource._request("PUT")

        self.assertTrue(resp is r1)
        self.assertEqual(resp.content, r1.content)

        self.base_resource._store["session"].request.assert_called_once_with(
            "PUT",
            "http://example/api/v1/test",
            data=None,
            files=None,
            params=None,
            headers={"content-type": self.base_resource._store["serializer"].get_content_type(), "accept": self.base_resource._store["serializer"].get_content_type()}
        )

        resp = self.base_resource.put(data={'foo': 'bar'})
        self.assertEqual(resp['result'], ['a', 'b', 'c'])

    def test_put_decodable_response(self):
        r = mock.Mock(spec=requests.Response)
        r.status_code = 200
        r.content = '{"result": ["a", "b", "c"]}'
        r.headers = {"content-type": "application/json"}

        self.base_resource._store.update({
            "session": mock.Mock(spec=requests.Session),
            "serializer": slumber.serialize.Serializer(),
        })
        self.base_resource._store["session"].request.return_value = r

        resp = self.base_resource._request("PUT")

        self.assertTrue(resp is r)
        self.assertEqual(resp.content, r.content)

        self.base_resource._store["session"].request.assert_called_once_with(
            "PUT",
            "http://example/api/v1/test",
            data=None,
            files=None,
            params=None,
            headers={"content-type": self.base_resource._store["serializer"].get_content_type(), "accept": self.base_resource._store["serializer"].get_content_type()}
        )

        resp = self.base_resource.put(data={'foo': 'bar'})
        self.assertEqual(resp['result'], ['a', 'b', 'c'])

    def test_handle_serialization(self):
        self.base_resource._store.update({
            "serializer": slumber.serialize.Serializer(),
        })

        resp = mock.Mock(spec=requests.Response)
        resp.headers = {"content-type": "application/json; charset=utf-8"}
        resp.content = '{"foo": "bar"}'

        r = self.base_resource._try_to_serialize_response(resp)

        if not isinstance(r, dict):
            self.fail("Serialization did not take place")

########NEW FILE########
__FILENAME__ = serializer
import unittest
import slumber
import slumber.serialize


class ResourceTestCase(unittest.TestCase):

    def test_json_get_serializer(self):
        s = slumber.serialize.Serializer()

        for content_type in [
                                "application/json",
                                "application/x-javascript",
                                "text/javascript",
                                "text/x-javascript",
                                "text/x-json",
                            ]:
            s.get_serializer(content_type=content_type)

########NEW FILE########
__FILENAME__ = utils
# -*- coding: utf-8 -*-

import unittest
import slumber


class UtilsTestCase(unittest.TestCase):

    def test_url_join_http(self):
        self.assertEqual(slumber.url_join("http://example.com/"), "http://example.com/")
        self.assertEqual(slumber.url_join("http://example.com/", "test"), "http://example.com/test")
        self.assertEqual(slumber.url_join("http://example.com/", "test", "example"), "http://example.com/test/example")

        self.assertEqual(slumber.url_join("http://example.com"), "http://example.com/")
        self.assertEqual(slumber.url_join("http://example.com", "test"), "http://example.com/test")
        self.assertEqual(slumber.url_join("http://example.com", "test", "example"), "http://example.com/test/example")

    def test_url_join_https(self):
        self.assertEqual(slumber.url_join("https://example.com/"), "https://example.com/")
        self.assertEqual(slumber.url_join("https://example.com/", "test"), "https://example.com/test")
        self.assertEqual(slumber.url_join("https://example.com/", "test", "example"), "https://example.com/test/example")

        self.assertEqual(slumber.url_join("https://example.com"), "https://example.com/")
        self.assertEqual(slumber.url_join("https://example.com", "test"), "https://example.com/test")
        self.assertEqual(slumber.url_join("https://example.com", "test", "example"), "https://example.com/test/example")

    def test_url_join_http_port(self):
        self.assertEqual(slumber.url_join("http://example.com:80/"), "http://example.com:80/")
        self.assertEqual(slumber.url_join("http://example.com:80/", "test"), "http://example.com:80/test")
        self.assertEqual(slumber.url_join("http://example.com:80/", "test", "example"), "http://example.com:80/test/example")

    def test_url_join_https_port(self):
        self.assertEqual(slumber.url_join("https://example.com:443/"), "https://example.com:443/")
        self.assertEqual(slumber.url_join("https://example.com:443/", "test"), "https://example.com:443/test")
        self.assertEqual(slumber.url_join("https://example.com:443/", "test", "example"), "https://example.com:443/test/example")

    def test_url_join_path(self):
        self.assertEqual(slumber.url_join("/"), "/")
        self.assertEqual(slumber.url_join("/", "test"), "/test")
        self.assertEqual(slumber.url_join("/", "test", "example"), "/test/example")

        self.assertEqual(slumber.url_join("/path/"), "/path/")
        self.assertEqual(slumber.url_join("/path/", "test"), "/path/test")
        self.assertEqual(slumber.url_join("/path/", "test", "example"), "/path/test/example")

    def test_url_join_trailing_slash(self):
        self.assertEqual(slumber.url_join("http://example.com/", "test/"), "http://example.com/test/")
        self.assertEqual(slumber.url_join("http://example.com/", "test/", "example/"), "http://example.com/test/example/")

    def test_url_join_encoded_unicode(self):
        expected = "http://example.com/tǝst/"

        url = slumber.url_join("http://example.com/", "tǝst/")
        self.assertEqual(url, expected)

        url = slumber.url_join("http://example.com/", "tǝst/".decode('utf8').encode('utf8'))
        self.assertEqual(url, expected)

    def test_url_join_decoded_unicode(self):
        url = slumber.url_join("http://example.com/", "tǝst/".decode('utf8'))
        expected = "http://example.com/tǝst/".decode('utf8')
        self.assertEqual(url, expected)

########NEW FILE########
