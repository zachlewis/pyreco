__FILENAME__ = pkg_doc
from pythondoc import ET, parse, CompactHTML
import sys

MODULE_NAME = "xlrd"
PATH_TO_FILES = sys.argv[1]


module = ET.Element("module", name=MODULE_NAME)

parts = [
    '__init__',
    'sheet',
    'xldate',
    # 'compdoc',
    'biffh',
    'formatting',
    'formula',
    ]
flist = ["%s/%s.py" % (PATH_TO_FILES, p) for p in parts]
for fname in flist:
    print "about to parse", fname
    elem = parse(fname)
    for elem in elem:
        if module and elem.tag == "info":
            # skip all module info sections except the first
            continue
        module.append(elem)

formatter = CompactHTML()
print formatter.save(module, MODULE_NAME), "ok"


########NEW FILE########
__FILENAME__ = pythondoc
#
#!/usr/bin/env python
#
# $Id: pythondoc.py 3271 2007-09-09 09:45:14Z fredrik $
# pythondoc documentation generator
#
# history:
# 2003-10-19 fl   first preview release (2.0a1)
# 2003-10-19 fl   fix HTML in descriptor tags, 1.5.2 tweaks, etc (2.0a2)
# 2003-10-20 fl   added encoding support, default HTML generator, etc (2.0a3)
# 2003-10-21 fl   fixed some 1.5.2 issues, etc (2.0b1)
# 2003-10-22 fl   HTML tweaks, pluggable output generators, etc (2.0b2)
# 2003-10-23 fl   fixed encoding, added @author, @version, @since etc
# 2003-10-24 fl   disable XML output by default
# 2003-10-25 fl   moved info properties into an 'info' element
# 2003-10-26 fl   expand wildcards on windows (2.0b3)
# 2003-10-30 fl   added support for RISC OS
# 2003-10-31 fl   (experimental) support module-level comments
# 2003-11-01 fl   minor HTML tweaks (2.0b4)
# 2003-11-03 fl   pythondoc 2.0 final
# 2003-11-15 fl   added support for inline @link/@linkplain tags (2.1b1)
# 2003-11-20 fl   fixed class attribute parsing bug
# 2004-03-27 fl   handle multiple single-line methods
# 2004-09-01 fl   support Python 2.4 decorators (2.1b2)
# 2004-09-21 fl   fixed output filename for "pythondoc ."
# 2005-03-25 fl   added docstring extraction for classes and methods (2.1b3)
# 2005-06-18 fl   fixed correct HTML output when using ElementTree 1.3 (2.1b4)
# 2005-12-23 fl   use xml.etree where available
# 2006-04-04 fl   refactored comment parser code; added -s support (2.1b5)
# 2006-04-06 fl   handle multiple params in docstrings correctly (2.1b6)
# 2007-09-09 fl   moved HTML parser into pythondoc module itself
#
# Copyright (c) 2002-2007 by Fredrik Lundh.
#

##
# This is the PythonDoc tool.  This tool parses Python source files
# and generates API descriptions in XML and HTML.
# <p>
# For more information on the PythonDoc tool and the markup format, see
# <a href="http://effbot.org/zone/pythondoc.htm">the PythonDoc page</a>
# at <a href="http://effbot.org/">effbot.org</a>.
##

# --------------------------------------------------------------------
# Software License
# --------------------------------------------------------------------
#
# Copyright (c) 2002-2007 by Fredrik Lundh
#
# By obtaining, using, and/or copying this software and/or its
# associated documentation, you agree that you have read, understood,
# and will comply with the following terms and conditions:
#
# Permission to use, copy, modify, and distribute this software and
# its associated documentation for any purpose and without fee is
# hereby granted, provided that the above copyright notice appears in
# all copies, and that both that copyright notice and this permission
# notice appear in supporting documentation, and that the name of
# Secret Labs AB or the author not be used in advertising or publicity
# pertaining to distribution of the software without specific, written
# prior permission.
#
# SECRET LABS AB AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD
# TO THIS SOFTWARE, INCLUDING ALL IMPLIED WARRANTIES OF MERCHANT-
# ABILITY AND FITNESS.  IN NO EVENT SHALL SECRET LABS AB OR THE AUTHOR
# BE LIABLE FOR ANY SPECIAL, INDIRECT OR CONSEQUENTIAL DAMAGES OR ANY
# DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS,
# WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS
# ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE
# OF THIS SOFTWARE.
#
# --------------------------------------------------------------------

# to do in later releases:
#
# TODO: test this release under 1.5.2 !
# TODO: better rendering of constructors/package modules
# TODO: check @param names against @def/define tags
# TODO: support recursive parsing (-R)
# TODO: warn for tags that doesn't make sense for a given target type
# TODO: HTML output localization (the %s module, returns, raises, etc)
# TODO: make compactHTML generate an element tree instead of raw HTML
#
# nice to have, maybe:
#
# IDEA: support multiple output handlers (multiple -O statements);
#       make -x an alias for -Oxml
# IDEA: make pythondoc self-contained (include stub element implementation)

VERSION_DATE = "2.1b7-20070909"
VERSION = VERSION_DATE.split("-")[0]

COPYRIGHT = "(c) 2002-2007 by Fredrik Lundh"

# explicitly import site (for exemaker etc)
import site

# stuff we use in this module
import glob, os, re, string, sys, tokenize

# make sure elementtree is available
try:
    try:
        import xml.etree.ElementTree as ET
    except ImportError:
        import elementtree.ElementTree as ET
except ImportError:
    raise RuntimeError(
        "PythonDoc %s requires ElementTree 1.1 or later "
        "(available from http://effbot.org/downloads)." % VERSION
        )

# extension separator (not all systems use a period)
try:
    EXTSEP = os.extsep
except AttributeError:
    EXTSEP = "."

##
# Debug level.  The higher the value, the more junk you'll see on
# standard output.
# <p>
# You can use the <b>-V</b> option to <b>pythondoc</b> to increase
# the debug level.

DEBUG = 0

##
# Whitespace tokens.  These are ignored when the parser is scanning
# for a subject.

WHITESPACE_TOKEN = (
    tokenize.NL, tokenize.NEWLINE, tokenize.DEDENT, tokenize.INDENT
    )

##
# Default encoding.  To override this for a module, put a "coding"
# directive in your Python module (see PEP 263 for details).

ENCODING = "iso-8859-1"

##
# Known tags.  The parser generates warnings for tags that are not in
# this list, but it still copies them to the XML infoset.

TAGS = (
    "def", "defreturn",
    "param", "keyparam",
    "return",
    "throws", "exception",
    # javadoc tags not used by the standard generator
    "author", "deprecated", "see", "since", "version"
    )

##
# (Helper) Combines filename prefix with extension part.
#
# @param prefix Filename prefix.
# @param ext Extension string, including a leading period.  The
#    period is replaced with a platform-specific separator, if
#    necessary.
# @return The combined name.

def joinext(prefix, ext):
    assert ext[0] == "." # require leading separator, to match os.path.splitext
    return prefix + EXTSEP + ext[1:]

##
# (Helper) Extracts block tags from a PythonDoc comment.
#
# @param comment Comment text.
# @return A list of (lineno, tag, text) tuples, where the tag is None
#     for the initial description.
# @defreturn List of tuples.

def gettags(comment):

    tags = []

    tag = None
    tag_lineno = lineno = 0
    tag_text = []

    for line in comment:
        if line[:1] == "@":
            tags.append((tag_lineno, tag, string.join(tag_text, "\n")))
            line = string.split(line, " ", 1)
            tag = line[0][1:]
            if len(line) > 1:
                tag_text = [line[1]]
            else:
                tag_text = []
            tag_lineno = lineno
        else:
            tag_text.append(line)
        lineno = lineno + 1

    tags.append((tag_lineno, tag, string.join(tag_text, "\n")))

    return tags

##
# (Helper) Flattens an element tree, returning only the text contents.
#
# @param elem An element tree.
# @return A text string.
# @defreturn String.

def flatten(elem):
    text = elem.text or ""
    for e in elem:
        text += flatten(e)
        if e.tail:
            text += e.tail
    return text

##
# (Helper) Extracts summary from a PythonDoc comment.  This function
# gets the first complete sentence from the description string.
#
# @param description An element containing the description.
# @return A summary string.
# @defreturn String.

def getsummary(description):

    description = flatten(description)

    # extract the first sentence from the description
    m = re.search("(?s)(.+?\.)\s", description + " ")
    if m:
        return m.group(1)

    return description # sorry

##
# (Helper) Parses HTML descriptor text into an XHTML structure.
#
# @param parser Parser instance (provides a warning method).
# @param text Text fragment.
# @return An element tree containing XHTML data.
# @defreturn Element.

def parsehtml(parser, tag, text, lineno):

    # transcode
    if parser.encoding != "ascii":
        try:
            text = unicode(text, parser.encoding)
        except NameError:
            pass # 1.5.2

    # process inline links (@link, @linkplain)
    # note that links are replaced with <a href='link:...> elements;
    # the href's are resolved in a later step
    if "{" in text:
        def fixlink(m, parser=parser, lineno=lineno):
            linkdef = string.split(m.group(1), None, 2)
            if len(linkdef) == 2:
                # default text is same as last part of target name
                href = linkdef[1]
                if href[:1] == "#":
                    href = href[1:]
                linkdef.append(string.split(href, ".")[-1])
            if len(linkdef) < 3 or linkdef[0] not in ("@link", "@linkplain"):
                parser.warning(
                    (lineno, 0),
                    "malformed @link near this line",
                    )
                return m.group(0)
            type, href, text = linkdef
            href = "link:" + html_encode(href)
            if type == "@link":
                return "<a href='%s' class='link'><b>%s</b></a>" % (href, text)
            else:
                return "<a href='%s' class='linkplain'>%s</a>" % (href, text)
        text = re.sub("\{(@link[^}]+)\}", fixlink, text)

    if "<" not in text and "&" not in text:
        # plain text
        elem = ET.Element(tag)
        elem.text = string.strip(text)
        return elem

    p = HTMLTreeBuilder()
    ix = 0
    try:
        p.feed("<%s>" % tag)
        p.feed("<p>") # make sure everything's wrapped in a paragraph tag
        # feed line by line
        for line in string.split(text, "\n"):
            p.feed(line + "\n")
            ix = ix + 1
        p.feed("</%s>" % tag)
        tree = p.close()
    except:
        parser.warning(
            (lineno+ix, 0),
            "HTML parser error near this line (%s)",
            sys.exc_value
            )
        return ET.Element("p")

    return tree

# --------------------------------------------------------------------
# copied from ElementTree/HTMLTreeBuilder.py

import htmlentitydefs

AUTOCLOSE = "p", "li", "tr", "th", "td", "head", "body"
IGNOREEND = "img", "hr", "meta", "link", "br"

if sys.version[:3] == "1.5":
    is_not_ascii = re.compile(r"[\x80-\xff]").search # 1.5.2
else:
    is_not_ascii = re.compile(eval(r'u"[\u0080-\uffff]"')).search

try:
    from HTMLParser import HTMLParser
except ImportError:
    from sgmllib import SGMLParser
    # hack to use sgmllib's SGMLParser to emulate 2.2's HTMLParser
    class HTMLParser(SGMLParser):
        # the following only works as long as this class doesn't
        # provide any do, start, or end handlers
        def unknown_starttag(self, tag, attrs):
            self.handle_starttag(tag, attrs)
        def unknown_endtag(self, tag):
            self.handle_endtag(tag)

##
# ElementTree builder for HTML source code.  This builder converts an
# HTML document or fragment to an ElementTree.
# <p>
# The parser is relatively picky, and requires balanced tags for most
# elements.  However, elements belonging to the following group are
# automatically closed: P, LI, TR, TH, and TD.  In addition, the
# parser automatically inserts end tags immediately after the start
# tag, and ignores any end tags for the following group: IMG, HR,
# META, and LINK.
#
# @keyparam builder Optional builder object.  If omitted, the parser
#     uses the standard <b>elementtree</b> builder.
# @keyparam encoding Optional character encoding, if known.  If omitted,
#     the parser looks for META tags inside the document.  If no tags
#     are found, the parser defaults to ISO-8859-1.  Note that if your
#     document uses a non-ASCII compatible encoding, you must decode
#     the document before parsing.

class HTMLTreeBuilder(HTMLParser):

    def __init__(self, encoding=None):
        self.__stack = []
        self.__builder = ET.TreeBuilder()
        self.encoding = encoding or "iso-8859-1"
        HTMLParser.__init__(self)

    ##
    # Flushes parser buffers, and return the root element.
    #
    # @return An Element instance.

    def close(self):
        HTMLParser.close(self)
        return self.__builder.close()

    ##
    # (Internal) Handles start tags.

    def handle_starttag(self, tag, attrs):
        if tag == "meta":
            # look for encoding directives
            http_equiv = content = None
            for k, v in attrs:
                if k == "http-equiv":
                    http_equiv = string.lower(v)
                elif k == "content":
                    content = v
            if http_equiv == "content-type" and content:
                # use mimetools to parse the http header
                import mimetools, StringIO
                header = mimetools.Message(
                    StringIO.StringIO("%s: %s\n\n" % (http_equiv, content))
                    )
                encoding = header.getparam("charset")
                if encoding:
                    self.encoding = encoding
        if tag in AUTOCLOSE:
            if self.__stack and self.__stack[-1] == tag:
                self.handle_endtag(tag)
        self.__stack.append(tag)
        attrib = {}
        if attrs:
            for k, v in attrs:
                attrib[string.lower(k)] = v
        self.__builder.start(tag, attrib)
        if tag in IGNOREEND:
            self.__stack.pop()
            self.__builder.end(tag)

    ##
    # (Internal) Handles end tags.

    def handle_endtag(self, tag):
        if tag in IGNOREEND:
            return
        lasttag = self.__stack.pop()
        if tag != lasttag and lasttag in AUTOCLOSE:
            self.handle_endtag(lasttag)
        self.__builder.end(tag)

    ##
    # (Internal) Handles character references.

    def handle_charref(self, char):
        if char[:1] == "x":
            char = int(char[1:], 16)
        else:
            char = int(char)
        if 0 <= char < 128:
            self.__builder.data(chr(char))
        else:
            self.__builder.data(unichr(char))

    ##
    # (Internal) Handles entity references.

    def handle_entityref(self, name):
        entity = htmlentitydefs.entitydefs.get(name)
        if entity:
            if len(entity) == 1:
                entity = ord(entity)
            else:
                entity = int(entity[2:-1])
            if 0 <= entity < 128:
                self.__builder.data(chr(entity))
            else:
                self.__builder.data(unichr(entity))
        else:
            self.unknown_entityref(name)

    ##
    # (Internal) Handles character data.

    def handle_data(self, data):
        if isinstance(data, type('')) and is_not_ascii(data):
            # convert to unicode, but only if necessary
            data = unicode(data, self.encoding, "ignore")
        self.__builder.data(data)

    ##
    # (Hook) Handles unknown entity references.  The default action
    # is to ignore unknown entities.

    def unknown_entityref(self, name):
        pass # ignore by default; override if necessary

# --------------------------------------------------------------------

##
# (Helper) Parses a PythonDoc comment into an PythonDoc info structure.
#
# @param parser Parser instance (provides a warning method).
# @param lineno Line number where this comment starts.
# @param comment A list of text line making up the comment.
# @param dedent If true, strip leading whitespace from all comment
#     lines except the first one.
# @return An element tree containing XHTML data.
# @defreturn Element.

def parsecomment(parser, lineno, comment, dedent=0):

    subject_info = ET.Element("info")

    # untabify
    for ix in range(len(comment)):
        comment[ix] = string.expandtabs(comment[ix])

    if dedent:
        margin = None
        for ix in range(1, len(comment)):
            s = string.lstrip(comment[ix])
            if not s:
                continue
            m = len(comment[ix]) - len(s)
            if margin is None:
                margin = m
            else:
                margin = min(m, margin)
        if margin:
            for ix in range(1, len(comment)):
                comment[ix] = comment[ix][margin:]

    for ix, tag, text in gettags(comment):

        pos = lineno + ix + 1, 0

        # check tag name
        if tag is None:
            tag = "description"
        else:
            if tag not in TAGS:
                parser.warning(
                    pos,
                    "unknown tag in description: @%s", tag
                    )
            if tag in ("throws", "exception"):
                tag = "exception" # PythonDoc extension

        # deal with "named" tags
        if tag in ("param", "keyparam", "exception"):
            text = string.split(text, " ", 1)
            name = text[0]
            if len(text) > 1:
                text = string.lstrip(text[1])
            else:
                text = ""
        else:
            name = None

        tag_elem = parsehtml(parser, tag, text, pos[0])

        # generate summaries
        if tag == "description":
            summary = getsummary(tag_elem)
            if summary:
                elem = ET.SubElement(subject_info, "summary")
                elem.text = summary

        subject_info.append(tag_elem)

        if name:
            tag_elem.set("name", name)

    return subject_info

##
# Module parser.
# <p>
# This class implements the PythonDoc source code scanner.  It reads
# source code from a file or a file-like object, and builds an element
# tree with information about the module.
# <p>
# Note that the constructor only sets things up for parsing.  Use the
# {@link ModuleParser.parse} method to parse the file.  Or for
# convenience, use the {@link parse} function to create a parser
# object and parse a given file.
#
# @param file Name of the module source file, or a file object.  If a
#    file object is used, it must provide a <b>name</b> attribute and
#    a <b>readline</b> method.
# @param prefix Optional name prefix.  If given, this is prepended to
#    the module name.  For example, if the prefix is set to "prefix"
#    and the module filename is "name.py", the module is assumed to
#    contain the "prefix.name" namespace.

class ModuleParser:

    ##
    # Module name.

    name = None

    def __init__(self, file, prefix=None):
        if hasattr(file, "readline"):
            self.file = file
            self.filename = file.name
        else:
            self.file = None
            self.filename = file
        name = os.path.splitext(os.path.basename(self.filename))[0]
        if prefix and prefix != ".":
            name = prefix + "." + name
        self.name = name
        self.stack = [
            ET.Element(
                "module",
                name=name, filename=self.filename
                )
            ]
        self.indent = 0
        self.scope = [] # list of (indent, tag, name, ...) tuples
        self.handler = self.look_for_encoding
        self.encoding = ENCODING

    ##
    # Parses the file.
    #
    # @keyparam docstring If true, look for markup in docstrings.
    # @return An element tree containing information about the module.
    # @defreturn Element.
    # @exception IOError If the file could not be opened.

    def parse(self, docstring=0):
        if self.file is None:
            file = open(self.filename)
        else:
            file = self.file
        try:
            tokenize.tokenize(file.readline, self.handle_token)
        except tokenize.TokenError, v:
            message, lineno = v
            self.warning(lineno, "exception in tokenizer: %s", message)
        if len(self.stack) != 1:
            pass # FIXME: print warning?
        tree = self.stack[0] # may be incomplete
        # fixup internal links
        # 1) find all named elements
        elems = {}
        for elem in tree.getiterator():
            name = elem.get("name")
            if name:
                elems[name] = elem
        # 2) find all link anchors
        for elem in tree.getiterator("a"):
            href = elem.get("href")
            if href[:5] == "link:":
                # FIXME: add support for external links
                href = href[5:]
                if href[:1] == "#":
                    href = href[1:]
                target = elems.get(self.name + "." + href)
                if target:
                    href = "#" + target.get("name") + "-" + target.tag
                    elem.set("href", href)
        if docstring:
            # look for markup in docstrings
            for info in tree.getiterator("info"):
                docstring = info.findtext("docstring")
                if not docstring:
                    continue
                comment = docstring.split("\n")
                newinfo = parsecomment(self, 0, comment, dedent=1)
                for elem in info:
                    if newinfo.find(elem.tag) is None:
                        newinfo.append(elem)
                info[:] = newinfo
        return tree

    ##
    # Prints a warning message to standard output.
    #
    # @param position A (line, column) tuple.  The column can be set
    #     to None if not known (or not relevant).
    # @param format Message or format string.
    # @param *args Optional arguments.

    def warning(self, position, format, *args):
        line, column = position
        message = "%s:%d: WARNING: %s" % (self.filename, line, format % args)
        sys.stderr.write(message)
        sys.stderr.write("\n")

    ##
    # Dispatches tokens to the current handler.  Each handler should
    # return the handler to call for the next token.
    # <p>
    # This method also handles indentation and dedentation tokens,
    # and manages the scope stack.

    def handle_token(self, *args):
        # dispatch incoming tokens to the current handler
        if DEBUG > 1:
            print self.handler.im_func.func_name, self.indent,
            print tokenize.tok_name[args[0]], repr(args[1])
        if args[0] == tokenize.DEDENT:
            self.indent = self.indent - 1
            while self.scope and self.scope[-1][0] >= self.indent:
                del self.scope[-1]
                del self.stack[-1]
        self.handler = apply(self.handler, args)
        if args[0] == tokenize.INDENT:
            self.indent = self.indent + 1

    ##
    # (Token handler) Scans for encoding directive.

    def look_for_encoding(self, type, token, start, end, line):
        if type == tokenize.COMMENT:
            if string.rstrip(token) == "##":
                return self.look_for_pythondoc(type, token, start, end, line)
            m = re.search("coding[:=]\s*([-_.\w]+)", token)
            if m:
                self.encoding = m.group(1)
                return self.look_for_pythondoc
        if start[0] > 2:
            return self.look_for_pythondoc
        return self.look_for_encoding

    ##
    # (Token handler) Scans for PythonDoc comments.

    def look_for_pythondoc(self, type, token, start, end, line):
        if type == tokenize.COMMENT and string.rstrip(token) == "##":
            # found a comment: set things up for comment processing
            self.comment_start = start
            self.comment = []
            return self.process_comment_body
        else:
            # deal with "bare" subjects
            if token == "def" or token == "class":
                self.subject_indent = self.indent
                self.subject_parens = 0
                self.subject_start = self.comment_start = None
                self.subject = []
                return self.process_subject(type, token, start, end, line)
            return self.look_for_pythondoc

    ##
    # (Token handler) Processes a comment body.  This handler adds
    # comment lines to the current comment.

    def process_comment_body(self, type, token, start, end, line):
        if type == tokenize.COMMENT:
            if start[1] != self.comment_start[1]:
                self.warning(
                    start,
                    "comment line should be aligned with marker"
                    )
            line = string.rstrip(token)
            if line == "##":
                # handle module comments (experimental)
                # FIXME: add more consistency checks?
                if self.stack[0].find("info") is not None:
                    self.warning(
                        self.comment_start,
                        "multiple module comments are not allowed"
                        )
                    # FIXME: ignore additional comments?
                self.process_subject_info(None, self.stack[0])
                return self.look_for_pythondoc
            elif line[:2] == "# ":
                line = line[2:]
            elif line[:1] == "#":
                line = line[1:]
            self.comment.append(line)
        else:
            if not self.comment:
                self.warning(
                    self.comment_start,
                    "found pythondoc marker but no comment body"
                    )
                return self.look_for_pythondoc
            self.subject_start = None
            self.subject = []
            if type != tokenize.NL:
                return self.process_subject(type, token, start, end, line)
            return self.process_subject # end of comment
        return self.process_comment_body

    ##
    # (Token handler) Processes the comment subject.  The subject can
    # be either a plain variable, or a function/method or class
    # definition.
    # <p>
    # This method is also used to process "bare" subjects; that is,
    # functions, methods, and classes that don't have PythonDoc
    # markup.  In that case, the comment_start variable is set to
    # None.

    def process_subject(self, type, token, start, end, line):
        # got an item; deal with it
        if self.subject:
            # method/function/class definition
            definition = self.subject[0] in ("def", "class")
            if definition:
                if type not in WHITESPACE_TOKEN:
                    if token == "(":
                        self.subject_parens = self.subject_parens + 1
                    elif token == ")":
                        self.subject_parens = self.subject_parens - 1
                if self.subject_parens or token != ":":
                    self.subject.append(token)
                    return self.process_subject
            else:
                # simple assignment
                if token != "=":
                    self.warning(
                        self.subject_start,
                        "bad subject %s; ignoring description",
                        repr(self.subject[0])
                        )
                    # might be a pythondoc marker; pass it to the scanner
                    return self.look_for_pythondoc(
                        type, token, start, end, line
                        )
                # FIXME: keep adding stuff until end of expression
        else:
            if type in WHITESPACE_TOKEN:
                return self.process_subject
            if type == tokenize.COMMENT:
                self.warning(
                    start,
                    "comment between description and subject; " +
                    "ignoring description"
                    )
                # might be a pythondoc marker; pass it to the scanner
                return self.look_for_pythondoc(
                    type, token, start, end, line
                    )
            # FIXME: check token type!
            # the @ token type is currently tokenize.ERRORTOKEN; hopefully
            # this will change before 2.4 final
            if token == "@":
                self.decorator_parens = 0
                return self.skip_decorator
            self.subject_start = start
            self.subject.append(token)
            if token in ("def", "class"):
                # handle single-line subjects
                while self.scope and self.scope[-1][0] >= self.indent:
                    self.scope.pop()
                    self.stack.pop()
                self.subject_indent = self.indent
                self.subject_parens = 0
            return self.process_subject

        # check if this is a method or a function
        method = self.scope and self.scope[-1][1] == "class"

        # calculate fully qualified subject name
        name = [self.name]
        for s in self.scope:
            name.append(s[2])
        if definition:
            name.append(self.subject[1])
        else:
            name.append(self.subject[0])

        # calculate subject definition statement
        statement = []
        for part in self.subject:
            if part in ("class", "def"):
                continue
            statement.append(part)
            if part == ",":
                statement.append(" ")
        if self.subject[0] == "def" and method:
            # ignore the first argument for methods
            # 'name', '(', 'self', ',', ' ', ...)
            del statement[2:min(5, len(statement)-1)]
        statement = string.join(statement, "")

        # create subject element
        if self.subject[0] == "class":
            subject_elem = ET.Element("class")
        elif self.subject[0] == "def":
            if method:
                subject_elem = ET.Element("method")
            else:
                subject_elem = ET.Element("function")
        else:
            subject_elem = ET.Element("variable")

        self.stack[-1].append(subject_elem)

        # add new subject to the scope and element stacks
        if definition:
            self.scope.append((self.subject_indent,) + tuple(self.subject))
            self.stack.append(subject_elem)

        subject_info = self.process_subject_info(name, subject_elem)

        # add local name to info
        elem = ET.Element("name")
        elem.text = name[-1]

        subject_info.insert(0, elem)

        name = string.join(name, ".")

        subject_elem.set("name", name)
        subject_elem.set("lineno", str(self.subject_start[0]))

        if subject_info.find("def") is None and statement:
            # add subject definition (unless specified in comment)
            elem = ET.Element("def")
            elem.text = statement
            # add to front, to make the XML easier to read
            subject_info.insert(0, elem)

        if definition:
            return self.look_for_docstring(type, token, start, end, line)
        else:
            return self.look_for_pythondoc(type, token, start, end, line)

    ##
    # (Token handler) Skips a decorator.

    def skip_decorator(self, type, token, start, end, line):
        if token == "(":
            self.decorator_parens = self.decorator_parens + 1
        elif token == ")":
            self.decorator_parens = self.decorator_parens - 1
        if self.decorator_parens or type != tokenize.NEWLINE:
            return self.skip_decorator
        return self.process_subject

    ##
    # (Token handler helper) Processes a PythonDoc comment.  This
    # method creates an "info" element based on the current comment,
    # and attaches it to the current subject element.
    #
    # @param subject_name Subject name (or None if the name is not known).
    # @param subject_elem The current subject element.
    # @return The info element.  Note that this element has already
    #     been attached to the subject element.
    # @defreturn Element

    def process_subject_info(self, subject_name, subject_elem):

        # process pythondoc comment (if any)
        if self.comment_start:
            subject_info = parsecomment(
                self, self.comment_start[0], self.comment
                )
        else:
            subject_info = ET.Element("info")

        subject_elem.append(subject_info)

        if DEBUG:
            if subject_name:
                subject_name = string.join(subject_name, ".")
            else:
                subject_name = "<module>"
            print "---", subject_name
            prefix = "   " * len(self.scope)
            for line in self.comment:
                print prefix + line

        return subject_info

    ##
    # (Token handler) Look for docstring inside a definition.

    def look_for_docstring(self, type, token, start, end, line):
        if type in WHITESPACE_TOKEN or token == ":":
            return self.look_for_docstring
        if type == tokenize.STRING:
            subject_elem = self.stack[-1]
            subject_info = subject_elem.find("info")
            if subject_info is not None:
                elem = ET.SubElement(subject_info, "docstring")
                # FIXME: add string sanity check here, before doing eval
                elem.text = eval(token)
        return self.skip_subject_body(type, token, start, end, line)

    ##
    # (Token handler) Skips over the subject body.

    def skip_subject_body(self, type, token, start, end, line):
        # for now, just hand control back to the pythondoc scanner,
        # and let it skip over the subject body while looking for the
        # next marker.
        return self.look_for_pythondoc(type, token, start, end, line)

##
# Parses a module.
# <p>
# This function creates a {@link #ModuleParser} instance, and uses it
# to parse the given file.  For details, see {@linkplain #ModuleParser
# the <b>ModuleParser</b> documentation}.
#
# @param file Name of the module source file, or a file object.
# @param prefix Optional name prefix.
# @keyparam docstring If true, look for markup in docstrings.
# @return An element tree containing the module description.
# @defreturn Element.
# @exception IOError If the file could not be found, or could not
#    be opened for reading.

def parse(file, prefix=None, docstring=0):
    m = ModuleParser(file, prefix)
    return m.parse(docstring=docstring)

# --------------------------------------------------------------------
# default formatter

if sys.version[:3] == "1.5":
    _escape = re.compile(r"[&<>\"\x80-\xff]") # 1.5.2
else:
    _escape = re.compile(eval(r'u"[&<>\"\u0080-\uffff]"'))

_escape_map = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
}

##
# Encodes reserved HTML characters and non-ASCII characters as HTML
# character references.
#
# @def html_encode(text)
# @param text Source text.
# @return An encoded string.

def html_encode(text, pattern=_escape):
    if not text:
        return ""
    def escape_entities(m, map=_escape_map):
        char = m.group()
        text = map.get(char)
        if text is None:
            text = "&#%d;" % ord(char)
        return text
    text = pattern.sub(escape_entities, text)
    try:
        return text.encode("ascii")
    except AttributeError:
        return text # 1.5.2

##
# Compact HTML formatter.  This formatter turns a module XML
# description into a minimal HTML document.
# <p>
# This formatter supports the following options:
# </p>
# <dl>
# <dt><b>-Dstyle</b>=URL</dt>
# <dd>Stylesheet URL.  If this option is present, the formatter adds a
# stylesheet &lt;link&gt; element to the HTML output.</dd>
# <dt><b>-Dzone</b></dt>
# <dd>Generate effbot.org zone documents.</dd>
# </dl>
#
# @param options Options dictionary.

class CompactHTML:

    def __init__(self, options=None):
        self.options = options or {}

    ##
    # Writes an element containing some text (plain or formatted).
    #
    # @param elem Element.
    # @param compact If true, try to minimize the amount of vertical
    #     padding.

    def writetext(self, elem, compact=0):
        if len(elem):
            if compact and len(elem) == 1 and elem[0].tag == "p":
                elem = elem[0]
                self.file.write(html_encode(elem.text))
                for e in elem:
                    ET.ElementTree(e).write(self.file)
                self.file.write(html_encode(elem.tail))
            else:
                for e in elem:
                    ET.ElementTree(e).write(self.file)
        elif elem is not None and elem.text:
            if compact:
                self.file.write(html_encode(elem.text))
            else:
                self.file.write("<p>%s</p>\n" % html_encode(elem.text))

    ##
    # Writes an object description (the description text, parameters,
    # return values) etc.
    #
    # @param object The object element.
    # @param summary If true, use summary instead of full description.

    def writeobject(self, object, summary=0):
        name = object.get("name")
        info = object.find("info")
        localname = string.split(name, ".")[-1]
        define = info.findtext("def")
        anchor = html_encode(name + "-" + object.tag)
        if object.tag == "class":
            # look for the constructor
            for obj in object:
                if obj.get("name") == name + ".__init__":
                    inf = obj.find("info")
                    define = string.split(inf.findtext("def"), "(", 1)
                    define = localname + "(" + define[1]
                    self.file.write(
                        "<dt><b>%s</b> (class)" % html_encode(define)
                        )
                    break
            else:
                self.file.write(
                    "<dt><b>%s</b> (class) " % html_encode(localname)
                    )
        elif object.tag == "variable":
            self.file.write(
                "<dt><a id='%s' name='%s'><b>%s</b></a> (variable)" % (
                    anchor, anchor, html_encode(localname)
                    )
                )
        else:
            self.file.write(
                "<dt><a id='%s' name='%s'><b>%s</b></a>" % (
                    anchor, anchor, html_encode(define)
                    )
                )
            if object.tag == "function" or object.tag == "method":
                defreturn = info.find("defreturn")
                if defreturn is not None:
                    defreturn = flatten(defreturn)
                    self.file.write(" &rArr; %s" % html_encode(defreturn))
        self.file.write(" [<a href='#%s'>#</a>]</dt>\n" % anchor)
        self.file.write("<dd>\n")
        if summary:
            text = info.findtext("summary")
            if text:
                self.file.write("<p>%s</p>\n" % html_encode(text))
        else:
            self.writetext(info.find("description"))
        param = info.findall("param")
        keyparam = info.findall("keyparam")
        exception = info.findall("exception")
        return_elem = info.find("return")
        if param or keyparam or exception or return_elem != None:
            self.file.write("<dl>\n")
            for p in param + keyparam:
                name = p.get("name")
                if p.tag == "keyparam":
                    name = name + "="
                self.file.write("<dt><i>%s</i></dt>\n" % html_encode(name))
                self.file.write("<dd>\n")
                self.writetext(p, compact=1)
                self.file.write("</dd>\n")
            if return_elem is not None:
                self.file.write("<dt>Returns:</dt>\n")
                self.file.write("<dd>\n")
                self.writetext(return_elem, compact=1)
                self.file.write("</dd>\n")
            for e in exception:
                name = html_encode(e.get("name"))
                self.file.write("<dt>Raises <b>%s</b>:</dt>" % name)
                self.file.write("<dd>\n")
                self.writetext(e, compact=1)
                self.file.write("</dd>\n")
            self.file.write("</dl><br />\n")
        if object.tag == "class" and summary:
            self.file.write(
                "<p>For more information about this class, see "
                "<a href='#%s'><i>The %s Class</i></a>.</p>\n" % (
                    anchor, localname
                    )
                )
        self.file.write("</dd>\n")

    ##
    # Writes a module description to file.
    #
    # @param module A module element tree, as returned by {@link
    # ModuleParser.parse}.
    # @param file Output file name (minus extension).
    # @return If successful, the output filename used to store the
    #     module.
    # @defreturn String or None.

    def save(self, module, file):

        title = "The %s Module" % module.get("name")

        zone = self.options.has_key("zone")

        if zone:
            filename = joinext(file, ".txt")
        else:
            filename = joinext(file, ".html")
        self.file = open(filename, "w")

        if zone:
            # generate zone document
            self.file.write(title + "\n\n")
        else:
            self.file.write(
                "<!DOCTYPE html PUBLIC '-//W3C//DTD XHTML 1.0 Strict//EN' "
                "'http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd'>\n"
                )
            self.file.write("<html>\n<head>\n")
            self.file.write(
                "<meta http-equiv='Content-Type' "
                "content='text/html; charset=us-ascii' />\n"
                )
            self.file.write("<title>%s</title>\n" % html_encode(title))
            try:
                style = self.options["style"]
            except KeyError:
                pass
            else:
                self.file.write(
                    "<link rel='stylesheet' href='%s' type='text/css' />\n" %
                    html_encode(style)
                    )
            self.file.write("</head>\n<body>\n")
            self.file.write("<h1>%s</h1>\n" % title)

        # 0) module comments
        info = module.find("info")
        if info is not None:
            self.writetext(info.find("description"))
            self.file.write("<h2>Module Contents</h2>\n")

        # 1) toplevel subjects (including class overviews)
        objects = []
        for object in module:
            info = object.find("info")
            if info is None or info.find("description") is None:
                continue
            if object.tag in ("variable", "function", "class"):
                objects.append(object)
        objects.sort(lambda a, b: cmp(
            string.lower(string.split(a.get("name"), ".")[-1]),
            string.lower(string.split(b.get("name"), ".")[-1])
            ))
        self.file.write("<dl>\n")
        for object in objects:
            self.writeobject(object, object.tag == "class")
        self.file.write("</dl>\n")
        # 2) class descriptions
        for object in objects:
            if object.tag != "class":
                continue
            name = object.get("name")
            localname = string.split(name, ".")[-1]
            anchor = name + "-class"
            self.file.write(
                "<h2><a id='%s' name='%s'>The %s Class</a></h2>\n" % (
                    anchor, anchor, localname
                    )
                )
            self.file.write("<dl>\n")
            self.writeobject(object)
            objects = []
            for object in object:
                info = object.find("info")
                if info is None or info.find("description") is None:
                    continue
                if object.tag not in ("method", "variable"):
                    continue
                objects.append(object)
            objects.sort(lambda a, b: cmp(
            string.lower(string.split(a.get("name"), ".")[-1]),
            string.lower(string.split(b.get("name"), ".")[-1])
                ))
            for object in objects:
                if object.tag == "variable":
                    object.tag = "attribute"
                self.writeobject(object)
                if object.tag == "attribute":
                    object.tag = "variable"
            self.file.write("</dl>\n")

        if not zone:
            self.file.write("</body></html>\n")

        self.file.close()
        self.file = None

        return filename

##
# Prints a usage message and exits.

def usage():
    print "PythonDoc", VERSION, COPYRIGHT
    print
    print "Usage:"
    print
    print "  pythondoc [options] files..."
    print
    print "where the files can be either python modules or package"
    print "directories."
    print
    print "Options:"
    print
    print "  -p prefix    Prepend given prefix to symbol names."
    print "  -f           Generate output also for files without descriptions."
    print "  -x           Generate XML output (pythondoc infosets)."
    print
    print "  -s           Look for markup in docstrings (experimental)."
    print
    print "Output options:"
    print
    print "  -O format    Use given output format handler."
    print "  -D name      Define output variable."
    print "  -D name=text Set output variable to given text."
    print
    print "For more information on PythonDoc and the PythonDoc comment syntax,"
    print "see http://effbot.org/zone/pythondoc.htm"
    sys.exit(1)

if __name__ == "__main__":

    import getopt

    try:
        opts, args = getopt.getopt(sys.argv[1:], "D:fO:p:Vsx")
    except getopt.error:
        usage()

    force = 0
    prefix = None
    docstring = 0
    output_xml = 0
    output_handler = CompactHTML
    output_options = {}

    for k, v in opts:
        if k == "-f":
            force = 1
        elif k == "-p":
            prefix = v
        elif k == "-s":
            docstring = 1
        elif k == "-x":
            output_xml = 1
        elif k == "-O":
            try:
                m = __import__(v)
                for k in string.split(v, ".")[1:]:
                    m = getattr(m, k)
                output_handler = getattr(m, "PythonDocGenerator")
            except (ImportError, AttributeError):
                print "cannot find/load", repr(v), "generator"
                sys.exit(1)
        elif k == "-D":
            try:
                k, v = string.split(v, "=", 1)
            except ValueError:
                k = v; v = None
            output_options[k] = v
        elif k == "-V":
            DEBUG = DEBUG + 1

    if not args:
        usage()

    # instantiate output handler
    output_handler = output_handler(output_options)

    # check if handler supports custom tags
    try:
        TAGS = TAGS + output_handler.tags
    except AttributeError:
        pass

    import time
    t0 = time.time()

    input = output = 0

    for filename in args:

        this_prefix = prefix

        if os.path.isdir(filename):
            # FIXME: explicitly check if this is a package?
            files = glob.glob(os.path.join(filename, joinext("*", ".py")))
            if not this_prefix:
                this_prefix = os.path.basename(filename)
        else:
            if sys.platform == "win32" and glob.has_magic(filename):
                files = glob.glob(filename)
            else:
                files = [filename]

        files.sort()

        for file in files:

            try:
                module = parse(file, this_prefix, docstring=docstring)
            except IOError, v:
                sys.stderr.write("%s error: %s\n" % (file, v[1]))
                continue

            input = input + 1

            # check if any toplevel object has a description
            if not force:
                for n in module:
                    i = n.find("info")
                    if i and i.find("description") is not None:
                        break
                else:
                    continue # no documented subjects

            f = "pythondoc-" + string.replace(module.get("name"), ".", EXTSEP)

            if output_xml:
                # generate XML
                filename = joinext(f, ".xml")
                try:
                    out = open(filename, "w")
                    ET.ElementTree(module).write(out)
                    out.close()
                except IOError, v:
                    sys.stderr.write("%s error: %s\n" % (filename, v[1]))
                else:
                    sys.stderr.write("%s ok\n" % filename)

            # generate output
            try:
                out = output_handler.save(module, f)
            except IOError, v:
                sys.stderr.write("%s error: %s\n" % (file, v[1]))
            else:
                if out:
                    sys.stderr.write("%s ok\n" % out)

            output = output + 1

    # flush output handler
    try:
        done = output_handler.done
    except AttributeError:
        pass
    else:
        out = output_handler.done()
        if out:
            sys.stderr.write("%s ok\n" % out)

    if DEBUG:
        sys.stderr.write(
            "%d files parsed, %d descriptions generated, in %.2f seconds\n" % (
                input, output, time.time() - t0
                ))

########NEW FILE########
__FILENAME__ = runxlrd
#!/usr/bin/env python
# Copyright (c) 2005-2012 Stephen John Machin, Lingfo Pty Ltd
# This script is part of the xlrd package, which is released under a
# BSD-style licence.

from __future__ import print_function

cmd_doc = """
Commands:

2rows           Print the contents of first and last row in each sheet
3rows           Print the contents of first, second and last row in each sheet
bench           Same as "show", but doesn't print -- for profiling
biff_count[1]   Print a count of each type of BIFF record in the file
biff_dump[1]    Print a dump (char and hex) of the BIFF records in the file
fonts           hdr + print a dump of all font objects
hdr             Mini-overview of file (no per-sheet information)
hotshot         Do a hotshot profile run e.g. ... -f1 hotshot bench bigfile*.xls
labels          Dump of sheet.col_label_ranges and ...row... for each sheet
name_dump       Dump of each object in book.name_obj_list
names           Print brief information for each NAME record
ov              Overview of file
profile         Like "hotshot", but uses cProfile
show            Print the contents of all rows in each sheet
version[0]      Print versions of xlrd and Python and exit
xfc             Print "XF counts" and cell-type counts -- see code for details

[0] means no file arg
[1] means only one file arg i.e. no glob.glob pattern
"""

options = None
if __name__ == "__main__":

    PSYCO = 0

    import xlrd
    import sys, time, glob, traceback, gc
    
    from xlrd.timemachine import xrange, REPR
    

    class LogHandler(object):

        def __init__(self, logfileobj):
            self.logfileobj = logfileobj
            self.fileheading = None
            self.shown = 0
            
        def setfileheading(self, fileheading):
            self.fileheading = fileheading
            self.shown = 0
            
        def write(self, text):
            if self.fileheading and not self.shown:
                self.logfileobj.write(self.fileheading)
                self.shown = 1
            self.logfileobj.write(text)
        
    null_cell = xlrd.empty_cell

    def show_row(bk, sh, rowx, colrange, printit):
        if bk.ragged_rows:
            colrange = range(sh.row_len(rowx))
        if not colrange: return
        if printit: print()
        if bk.formatting_info:
            for colx, ty, val, cxfx in get_row_data(bk, sh, rowx, colrange):
                if printit:
                    print("cell %s%d: type=%d, data: %r, xfx: %s"
                        % (xlrd.colname(colx), rowx+1, ty, val, cxfx))
        else:
            for colx, ty, val, _unused in get_row_data(bk, sh, rowx, colrange):
                if printit:
                    print("cell %s%d: type=%d, data: %r" % (xlrd.colname(colx), rowx+1, ty, val))

    def get_row_data(bk, sh, rowx, colrange):
        result = []
        dmode = bk.datemode
        ctys = sh.row_types(rowx)
        cvals = sh.row_values(rowx)
        for colx in colrange:
            cty = ctys[colx]
            cval = cvals[colx]
            if bk.formatting_info:
                cxfx = str(sh.cell_xf_index(rowx, colx))
            else:
                cxfx = ''
            if cty == xlrd.XL_CELL_DATE:
                try:
                    showval = xlrd.xldate_as_tuple(cval, dmode)
                except xlrd.XLDateError as e:
                    showval = "%s:%s" % (type(e).__name__, e)
                    cty = xlrd.XL_CELL_ERROR
            elif cty == xlrd.XL_CELL_ERROR:
                showval = xlrd.error_text_from_code.get(cval, '<Unknown error code 0x%02x>' % cval)
            else:
                showval = cval
            result.append((colx, cty, showval, cxfx))
        return result

    def bk_header(bk):
        print()
        print("BIFF version: %s; datemode: %s"
            % (xlrd.biff_text_from_num[bk.biff_version], bk.datemode))
        print("codepage: %r (encoding: %s); countries: %r"
            % (bk.codepage, bk.encoding, bk.countries))
        print("Last saved by: %r" % bk.user_name)
        print("Number of data sheets: %d" % bk.nsheets)
        print("Use mmap: %d; Formatting: %d; On demand: %d"
            % (bk.use_mmap, bk.formatting_info, bk.on_demand))
        print("Ragged rows: %d" % bk.ragged_rows)
        if bk.formatting_info:
            print("FORMATs: %d, FONTs: %d, XFs: %d"
                % (len(bk.format_list), len(bk.font_list), len(bk.xf_list)))
        if not options.suppress_timing:        
            print("Load time: %.2f seconds (stage 1) %.2f seconds (stage 2)"
                % (bk.load_time_stage_1, bk.load_time_stage_2))
        print()

    def show_fonts(bk):
        print("Fonts:")
        for x in xrange(len(bk.font_list)):
            font = bk.font_list[x]
            font.dump(header='== Index %d ==' % x, indent=4)

    def show_names(bk, dump=0):
        bk_header(bk)
        if bk.biff_version < 50:
            print("Names not extracted in this BIFF version")
            return
        nlist = bk.name_obj_list
        print("Name list: %d entries" % len(nlist))
        for nobj in nlist:
            if dump:
                nobj.dump(sys.stdout,
                    header="\n=== Dump of name_obj_list[%d] ===" % nobj.name_index)
            else:
                print("[%d]\tName:%r macro:%r scope:%d\n\tresult:%r\n"
                    % (nobj.name_index, nobj.name, nobj.macro, nobj.scope, nobj.result))

    def print_labels(sh, labs, title):
        if not labs:return
        for rlo, rhi, clo, chi in labs:
            print("%s label range %s:%s contains:"
                % (title, xlrd.cellname(rlo, clo), xlrd.cellname(rhi-1, chi-1)))
            for rx in xrange(rlo, rhi):
                for cx in xrange(clo, chi):
                    print("    %s: %r" % (xlrd.cellname(rx, cx), sh.cell_value(rx, cx)))

    def show_labels(bk):
        # bk_header(bk)
        hdr = 0
        for shx in range(bk.nsheets):
            sh = bk.sheet_by_index(shx)
            clabs = sh.col_label_ranges
            rlabs = sh.row_label_ranges
            if clabs or rlabs:
                if not hdr:
                    bk_header(bk)
                    hdr = 1
                print("sheet %d: name = %r; nrows = %d; ncols = %d" %
                    (shx, sh.name, sh.nrows, sh.ncols))
                print_labels(sh, clabs, 'Col')
                print_labels(sh, rlabs, 'Row')
            if bk.on_demand: bk.unload_sheet(shx)

    def show(bk, nshow=65535, printit=1):
        bk_header(bk)
        if 0:
            rclist = xlrd.sheet.rc_stats.items()
            rclist = sorted(rclist)
            print("rc stats")
            for k, v in rclist:
                print("0x%04x %7d" % (k, v))
        if options.onesheet:
            try:
                shx = int(options.onesheet)
            except ValueError:
                shx = bk.sheet_by_name(options.onesheet).number
            shxrange = [shx]
        else:
            shxrange = range(bk.nsheets)
        # print("shxrange", list(shxrange))
        for shx in shxrange:
            sh = bk.sheet_by_index(shx)
            nrows, ncols = sh.nrows, sh.ncols
            colrange = range(ncols)
            anshow = min(nshow, nrows)
            print("sheet %d: name = %s; nrows = %d; ncols = %d" %
                (shx, REPR(sh.name), sh.nrows, sh.ncols))
            if nrows and ncols:
                # Beat the bounds
                for rowx in xrange(nrows):
                    nc = sh.row_len(rowx)
                    if nc:
                        _junk = sh.row_types(rowx)[nc-1]
                        _junk = sh.row_values(rowx)[nc-1]
                        _junk = sh.cell(rowx, nc-1)
            for rowx in xrange(anshow-1):
                if not printit and rowx % 10000 == 1 and rowx > 1:
                    print("done %d rows" % (rowx-1,))
                show_row(bk, sh, rowx, colrange, printit)
            if anshow and nrows:
                show_row(bk, sh, nrows-1, colrange, printit)
            print()
            if bk.on_demand: bk.unload_sheet(shx)

    def count_xfs(bk):
        bk_header(bk)
        for shx in range(bk.nsheets):
            sh = bk.sheet_by_index(shx)
            nrows, ncols = sh.nrows, sh.ncols
            print("sheet %d: name = %r; nrows = %d; ncols = %d" %
                (shx, sh.name, sh.nrows, sh.ncols))
            # Access all xfindexes to force gathering stats
            type_stats = [0, 0, 0, 0, 0, 0, 0]
            for rowx in xrange(nrows):
                for colx in xrange(sh.row_len(rowx)):
                    xfx = sh.cell_xf_index(rowx, colx)
                    assert xfx >= 0
                    cty = sh.cell_type(rowx, colx)
                    type_stats[cty] += 1
            print("XF stats", sh._xf_index_stats)
            print("type stats", type_stats)
            print()
            if bk.on_demand: bk.unload_sheet(shx)

    def main(cmd_args):
        import optparse
        global options, PSYCO
        usage = "\n%prog [options] command [input-file-patterns]\n" + cmd_doc
        oparser = optparse.OptionParser(usage)
        oparser.add_option(
            "-l", "--logfilename",
            default="",
            help="contains error messages")
        oparser.add_option(
            "-v", "--verbosity",
            type="int", default=0,
            help="level of information and diagnostics provided")
        oparser.add_option(
            "-m", "--mmap",
            type="int", default=-1,
            help="1: use mmap; 0: don't use mmap; -1: accept heuristic")
        oparser.add_option(
            "-e", "--encoding",
            default="",
            help="encoding override")
        oparser.add_option(
            "-f", "--formatting",
            type="int", default=0,
            help="0 (default): no fmt info\n"
                 "1: fmt info (all cells)\n"
            )
        oparser.add_option(
            "-g", "--gc",
            type="int", default=0,
            help="0: auto gc enabled; 1: auto gc disabled, manual collect after each file; 2: no gc")
        oparser.add_option(
            "-s", "--onesheet",
            default="",
            help="restrict output to this sheet (name or index)")
        oparser.add_option(
            "-u", "--unnumbered",
            action="store_true", default=0,
            help="omit line numbers or offsets in biff_dump")
        oparser.add_option(
            "-d", "--on-demand",
            action="store_true", default=0,
            help="load sheets on demand instead of all at once")
        oparser.add_option(
            "-t", "--suppress-timing",
            action="store_true", default=0,
            help="don't print timings (diffs are less messy)")
        oparser.add_option(
            "-r", "--ragged-rows",
            action="store_true", default=0,
            help="open_workbook(..., ragged_rows=True)")
        options, args = oparser.parse_args(cmd_args)
        if len(args) == 1 and args[0] in ("version", ):
            pass
        elif len(args) < 2:
            oparser.error("Expected at least 2 args, found %d" % len(args))
        cmd = args[0]
        xlrd_version = getattr(xlrd, "__VERSION__", "unknown; before 0.5")
        if cmd == 'biff_dump':
            xlrd.dump(args[1], unnumbered=options.unnumbered)
            sys.exit(0)
        if cmd == 'biff_count':
            xlrd.count_records(args[1])
            sys.exit(0)
        if cmd == 'version':
            print("xlrd: %s, from %s" % (xlrd_version, xlrd.__file__))
            print("Python:", sys.version)
            sys.exit(0)
        if options.logfilename:
            logfile = LogHandler(open(options.logfilename, 'w'))
        else:
            logfile = sys.stdout
        mmap_opt = options.mmap
        mmap_arg = xlrd.USE_MMAP
        if mmap_opt in (1, 0):
            mmap_arg = mmap_opt
        elif mmap_opt != -1:
            print('Unexpected value (%r) for mmap option -- assuming default' % mmap_opt)
        fmt_opt = options.formatting | (cmd in ('xfc', ))
        gc_mode = options.gc
        if gc_mode:
            gc.disable()
        for pattern in args[1:]:
            for fname in glob.glob(pattern):
                print("\n=== File: %s ===" % fname)
                if logfile != sys.stdout:
                    logfile.setfileheading("\n=== File: %s ===\n" % fname)
                if gc_mode == 1:
                    n_unreachable = gc.collect()
                    if n_unreachable:
                        print("GC before open:", n_unreachable, "unreachable objects")
                if PSYCO:
                    import psyco
                    psyco.full()
                    PSYCO = 0
                try:
                    t0 = time.time()
                    bk = xlrd.open_workbook(fname,
                        verbosity=options.verbosity, logfile=logfile,
                        use_mmap=mmap_arg,
                        encoding_override=options.encoding,
                        formatting_info=fmt_opt,
                        on_demand=options.on_demand,
                        ragged_rows=options.ragged_rows,
                        )
                    t1 = time.time()
                    if not options.suppress_timing:
                        print("Open took %.2f seconds" % (t1-t0,))
                except xlrd.XLRDError as e:
                    print("*** Open failed: %s: %s" % (type(e).__name__, e))
                    continue
                except KeyboardInterrupt:
                    print("*** KeyboardInterrupt ***")
                    traceback.print_exc(file=sys.stdout)
                    sys.exit(1)
                except BaseException as e:
                    print("*** Open failed: %s: %s" % (type(e).__name__, e))
                    traceback.print_exc(file=sys.stdout)
                    continue
                t0 = time.time()
                if cmd == 'hdr':
                    bk_header(bk)
                elif cmd == 'ov': # OverView
                    show(bk, 0)
                elif cmd == 'show': # all rows
                    show(bk)
                elif cmd == '2rows': # first row and last row
                    show(bk, 2)
                elif cmd == '3rows': # first row, 2nd row and last row
                    show(bk, 3)
                elif cmd == 'bench':
                    show(bk, printit=0)
                elif cmd == 'fonts':
                    bk_header(bk)
                    show_fonts(bk)
                elif cmd == 'names': # named reference list
                    show_names(bk)
                elif cmd == 'name_dump': # named reference list
                    show_names(bk, dump=1)
                elif cmd == 'labels':
                    show_labels(bk)
                elif cmd == 'xfc':
                    count_xfs(bk)
                else:
                    print("*** Unknown command <%s>" % cmd)
                    sys.exit(1)
                del bk
                if gc_mode == 1:
                    n_unreachable = gc.collect()
                    if n_unreachable:
                        print("GC post cmd:", fname, "->", n_unreachable, "unreachable objects")
                if not options.suppress_timing:
                    t1 = time.time()
                    print("\ncommand took %.2f seconds\n" % (t1-t0,))

        return None

    av = sys.argv[1:]
    if not av:
        main(av)
    firstarg = av[0].lower()
    if firstarg == "hotshot":
        import hotshot, hotshot.stats
        av = av[1:]
        prof_log_name = "XXXX.prof"
        prof = hotshot.Profile(prof_log_name)
        # benchtime, result = prof.runcall(main, *av)
        result = prof.runcall(main, *(av, ))
        print("result", repr(result))
        prof.close()
        stats = hotshot.stats.load(prof_log_name)
        stats.strip_dirs()
        stats.sort_stats('time', 'calls')
        stats.print_stats(20)
    elif firstarg == "profile":
        import cProfile
        av = av[1:]
        cProfile.run('main(av)', 'YYYY.prof')
        import pstats
        p = pstats.Stats('YYYY.prof')
        p.strip_dirs().sort_stats('cumulative').print_stats(30)
    elif firstarg == "psyco":
        PSYCO = 1
        main(av[1:])
    else:
        main(av)

########NEW FILE########
__FILENAME__ = base
import os

def from_this_dir(filename):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

########NEW FILE########
__FILENAME__ = test_biffh
import unittest
import sys

if sys.version_info[0] >= 3:
    from io import StringIO
else:
    # Python 2.6+ does have the io module, but io.StringIO is strict about
    # unicode, which won't work for our test.
    from StringIO import StringIO

from xlrd import biffh

class TestHexDump(unittest.TestCase):
    def test_hex_char_dump(self):
        sio = StringIO()
        biffh.hex_char_dump(b"abc\0e\01", 0, 6, fout=sio)
        s = sio.getvalue()
        assert "61 62 63 00 65 01" in s, s
        assert "abc~e?" in s, s

if __name__=='__main__':
    unittest.main()

########NEW FILE########
__FILENAME__ = test_cell
# Portions Copyright (C) 2010, Manfred Moitzi under a BSD licence

import sys
import os
import unittest

import xlrd

from .base import from_this_dir

class TestCell(unittest.TestCase):

    def setUp(self):
        self.book = xlrd.open_workbook(from_this_dir('profiles.xls'), formatting_info=True)
        self.sheet = self.book.sheet_by_name('PROFILEDEF')
        
    def test_string_cell(self):
        cell = self.sheet.cell(0, 0)
        self.assertEqual(cell.ctype, xlrd.book.XL_CELL_TEXT)
        self.assertEqual(cell.value, 'PROFIL')
        self.assertTrue(cell.xf_index > 0)

    def test_number_cell(self):
        cell = self.sheet.cell(1, 1)
        self.assertEqual(cell.ctype, xlrd.book.XL_CELL_NUMBER)
        self.assertEqual(cell.value, 100)
        self.assertTrue(cell.xf_index > 0)

    def test_calculated_cell(self):
        sheet2 = self.book.sheet_by_name('PROFILELEVELS')
        cell = sheet2.cell(1, 3)
        self.assertEqual(cell.ctype, xlrd.book.XL_CELL_NUMBER)
        self.assertAlmostEqual(cell.value, 265.131, places=3)
        self.assertTrue(cell.xf_index > 0)

    def test_merged_cells(self):
        book = xlrd.open_workbook(from_this_dir('xf_class.xls'), formatting_info=True)
        sheet3 = book.sheet_by_name('table2')
        row_lo, row_hi, col_lo, col_hi = sheet3.merged_cells[0]
        self.assertEqual(sheet3.cell(row_lo, col_lo).value, 'MERGED')
        self.assertEqual((row_lo, row_hi, col_lo, col_hi), (3, 7, 2, 5))

    def test_merged_cells_xlsx(self):
        book = xlrd.open_workbook(from_this_dir('merged_cells.xlsx'))

        sheet1 = book.sheet_by_name('Sheet1')
        expected = []
        got = sheet1.merged_cells
        self.assertEqual(expected, got)

        sheet2 = book.sheet_by_name('Sheet2')
        expected = [(0, 1, 0, 2)]
        got = sheet2.merged_cells
        self.assertEqual(expected, got)

        sheet3 = book.sheet_by_name('Sheet3')
        expected = [(0, 1, 0, 2), (0, 1, 2, 4), (1, 4, 0, 2), (1, 9, 2, 4)]
        got = sheet3.merged_cells
        self.assertEqual(expected, got)

        sheet4 = book.sheet_by_name('Sheet4')
        expected = [(0, 1, 0, 2), (2, 20, 0, 1), (1, 6, 2, 5)]
        got = sheet4.merged_cells
        self.assertEqual(expected, got)

########NEW FILE########
__FILENAME__ = test_formats
 # -*- coding: utf-8 -*-
 # Portions Copyright (C) 2010, Manfred Moitzi under a BSD licence

from unittest import TestCase
import sys
import os

import xlrd

if sys.version_info[0] >= 3:
    def u(s): return s
else:
    def u(s):
        return s.decode('utf-8')

from .base import from_this_dir

class TestCellContent(TestCase):

    def setUp(self):
        self.book = xlrd.open_workbook(from_this_dir('Formate.xls'), formatting_info=True)
        self.sheet = self.book.sheet_by_name(u('Blätt1'))

    def test_text_cells(self):
        for row, name in enumerate([u('Huber'), u('Äcker'), u('Öcker')]):
            cell = self.sheet.cell(row, 0)
            self.assertEqual(cell.ctype, xlrd.book.XL_CELL_TEXT)
            self.assertEqual(cell.value, name)
            self.assertTrue(cell.xf_index > 0)

    def test_date_cells(self):
        # see also 'Dates in Excel spreadsheets' in the documentation
        # convert: xldate_as_tuple(float, book.datemode) -> (year, month,
        # day, hour, minutes, seconds)
        for row, date in [(0, 2741.), (1, 38406.), (2, 32266.)]:
            cell = self.sheet.cell(row, 1)
            self.assertEqual(cell.ctype, xlrd.book.XL_CELL_DATE)
            self.assertEqual(cell.value, date)
            self.assertTrue(cell.xf_index > 0)

    def test_time_cells(self):
        # see also 'Dates in Excel spreadsheets' in the documentation
        # convert: xldate_as_tuple(float, book.datemode) -> (year, month,
        # day, hour, minutes, seconds)
        for row, time in [(3, .273611), (4, .538889), (5, .741123)]:
            cell = self.sheet.cell(row, 1)
            self.assertEqual(cell.ctype, xlrd.book.XL_CELL_DATE)
            self.assertAlmostEqual(cell.value, time, places=6)
            self.assertTrue(cell.xf_index > 0)

    def test_percent_cells(self):
        for row, time in [(6, .974), (7, .124)]:
            cell = self.sheet.cell(row, 1)
            self.assertEqual(cell.ctype, xlrd.book.XL_CELL_NUMBER)
            self.assertAlmostEqual(cell.value, time, places=3)
            self.assertTrue(cell.xf_index > 0)

    def test_currency_cells(self):
        for row, time in [(8, 1000.30), (9, 1.20)]:
            cell = self.sheet.cell(row, 1)
            self.assertEqual(cell.ctype, xlrd.book.XL_CELL_NUMBER)
            self.assertAlmostEqual(cell.value, time, places=2)
            self.assertTrue(cell.xf_index > 0)

    def test_get_from_merged_cell(self):
        sheet = self.book.sheet_by_name(u('ÖÄÜ'))
        cell = sheet.cell(2, 2)
        self.assertEqual(cell.ctype, xlrd.book.XL_CELL_TEXT)
        self.assertEqual(cell.value, 'MERGED CELLS')
        self.assertTrue(cell.xf_index > 0)

    def test_ignore_diagram(self):
        sheet = self.book.sheet_by_name(u('Blätt3'))
        cell = sheet.cell(0, 0)
        self.assertEqual(cell.ctype, xlrd.book.XL_CELL_NUMBER)
        self.assertEqual(cell.value, 100)
        self.assertTrue(cell.xf_index > 0)

########NEW FILE########
__FILENAME__ = test_formulas
 # -*- coding: utf-8 -*-
# Portions Copyright (C) 2010, Manfred Moitzi under a BSD licence

from unittest import TestCase
import os
import sys

import xlrd

from .base import from_this_dir

try:
    ascii
except NameError:
    # For Python 2
    def ascii(s):
        a = repr(s)
        if a.startswith(('u"', "u'")):
            a = a[1:]
        return a

class TestFormulas(TestCase):

    def setUp(self):
        book = xlrd.open_workbook(from_this_dir('formula_test_sjmachin.xls'))
        self.sheet = book.sheet_by_index(0)
        
    def get_value(self, col, row):
        return ascii(self.sheet.col_values(col)[row])

    def test_cell_B2(self):
        self.assertEqual(
            self.get_value(1, 1),
            r"'\u041c\u041e\u0421\u041a\u0412\u0410 \u041c\u043e\u0441\u043a\u0432\u0430'"
            )

    def test_cell_B3(self):
        self.assertEqual(self.get_value(1, 2), '0.14285714285714285')

    def test_cell_B4(self):
        self.assertEqual(self.get_value(1, 3), "'ABCDEF'")

    def test_cell_B5(self):
        self.assertEqual(self.get_value(1, 4), "''")

    def test_cell_B6(self):
        self.assertEqual(self.get_value(1, 5), '1')

    def test_cell_B7(self):
        self.assertEqual(self.get_value(1, 6), '7')

    def test_cell_B8(self):
        self.assertEqual(
            self.get_value(1, 7),
            r"'\u041c\u041e\u0421\u041a\u0412\u0410 \u041c\u043e\u0441\u043a\u0432\u0430'"
            )

class TestNameFormulas(TestCase):

    def setUp(self):
        book = xlrd.open_workbook(from_this_dir('formula_test_names.xls'))
        self.sheet = book.sheet_by_index(0)
    
    def get_value(self, col, row):
        return ascii(self.sheet.col_values(col)[row])
    
    def test_unaryop(self):
        self.assertEqual(self.get_value(1, 1), '-7.0')
    
    def test_attrsum(self):
        self.assertEqual(self.get_value(1, 2), '4.0')
    
    def test_func(self):
        self.assertEqual(self.get_value(1, 3), '6.0')
    
    def test_func_var_args(self):
        self.assertEqual(self.get_value(1, 4), '3.0')
    
    def test_if(self):
        self.assertEqual(self.get_value(1, 5), "'b'")
    
    def test_choose(self):
        self.assertEqual(self.get_value(1, 6), "'C'")

########NEW FILE########
__FILENAME__ = test_open_workbook
from unittest import TestCase

import os

from xlrd import open_workbook

from .base import from_this_dir

class TestOpen(TestCase):
    # test different uses of open_workbook

    def test_names_demo(self):
        # For now, we just check this doesn't raise an error.
        open_workbook(
            from_this_dir(os.path.join('..','xlrd','examples','namesdemo.xls'))
            )

    def test_ragged_rows_tidied_with_formatting(self):
        # For now, we just check this doesn't raise an error.
        open_workbook(from_this_dir('issue20.xls'),
                      formatting_info=True)
        
    def test_BYTES_X00(self):
        # For now, we just check this doesn't raise an error.
        open_workbook(from_this_dir('picture_in_cell.xls'),
                      formatting_info=True)
        
    def test_xlsx_simple(self):
        # For now, we just check this doesn't raise an error.
        open_workbook(from_this_dir('text_bar.xlsx'))
        # we should make assertions here that data has been
        # correctly processed.
        
    def test_xlsx(self):
        # For now, we just check this doesn't raise an error.
        open_workbook(from_this_dir('reveng1.xlsx'))
        # we should make assertions here that data has been
        # correctly processed.

########NEW FILE########
__FILENAME__ = test_sheet
# Portions Copyright (C) 2010, Manfred Moitzi under a BSD licence

from unittest import TestCase

import sys
import os
import unittest

import xlrd

from .base import from_this_dir

SHEETINDEX = 0
NROWS = 15
NCOLS = 13

ROW_ERR = NROWS + 10
COL_ERR = NCOLS + 10

class TestSheet(TestCase):

    sheetnames = ['PROFILEDEF', 'AXISDEF', 'TRAVERSALCHAINAGE',
                  'AXISDATUMLEVELS', 'PROFILELEVELS']

    def setUp(self):
        self.book = xlrd.open_workbook(from_this_dir('profiles.xls'), formatting_info=True)

    def check_sheet_function(self, function):
        self.assertTrue(function(0, 0))
        self.assertTrue(function(NROWS-1, NCOLS-1))

    def check_sheet_function_index_error(self, function):
        self.assertRaises(IndexError, function, ROW_ERR, 0)
        self.assertRaises(IndexError, function, 0, COL_ERR)

    def check_col_slice(self, col_function):
        _slice = col_function(0, 2, NROWS-2)
        self.assertEqual(len(_slice), NROWS-4)

    def check_row_slice(self, row_function):
        _slice = row_function(0, 2, NCOLS-2)
        self.assertEqual(len(_slice), NCOLS-4)

    def test_nrows(self):
        sheet = self.book.sheet_by_index(SHEETINDEX)
        self.assertEqual(sheet.nrows, NROWS)

    def test_ncols(self):
        sheet = self.book.sheet_by_index(SHEETINDEX)
        self.assertEqual(sheet.ncols, NCOLS)

    def test_cell(self):
        sheet = self.book.sheet_by_index(SHEETINDEX)
        self.assertNotEqual(xlrd.empty_cell, sheet.cell(0, 0))
        self.assertNotEqual(xlrd.empty_cell, sheet.cell(NROWS-1, NCOLS-1))

    def test_cell_error(self):
        sheet = self.book.sheet_by_index(SHEETINDEX)
        self.check_sheet_function_index_error(sheet.cell)

    def test_cell_type(self):
        sheet = self.book.sheet_by_index(SHEETINDEX)
        self.check_sheet_function(sheet.cell_type)

    def test_cell_type_error(self):
        sheet = self.book.sheet_by_index(SHEETINDEX)
        self.check_sheet_function_index_error(sheet.cell_type)

    def test_cell_value(self):
        sheet = self.book.sheet_by_index(SHEETINDEX)
        self.check_sheet_function(sheet.cell_value)

    def test_cell_value_error(self):
        sheet = self.book.sheet_by_index(SHEETINDEX)
        self.check_sheet_function_index_error(sheet.cell_value)

    def test_cell_xf_index(self):
        sheet = self.book.sheet_by_index(SHEETINDEX)
        self.check_sheet_function(sheet.cell_xf_index)

    def test_cell_xf_index_error(self):
        sheet = self.book.sheet_by_index(SHEETINDEX)
        self.check_sheet_function_index_error(sheet.cell_xf_index)

    def test_col(self):
        sheet = self.book.sheet_by_index(SHEETINDEX)
        col = sheet.col(0)
        self.assertEqual(len(col), NROWS)

    def test_row(self):
        sheet = self.book.sheet_by_index(SHEETINDEX)
        row = sheet.row(0)
        self.assertEqual(len(row), NCOLS)

    def test_col_slice(self):
        sheet = self.book.sheet_by_index(SHEETINDEX)
        self.check_col_slice(sheet.col_slice)

    def test_col_types(self):
        sheet = self.book.sheet_by_index(SHEETINDEX)
        self.check_col_slice(sheet.col_types)

    def test_col_values(self):
        sheet = self.book.sheet_by_index(SHEETINDEX)
        self.check_col_slice(sheet.col_values)

    def test_row_slice(self):
        sheet = self.book.sheet_by_index(SHEETINDEX)
        self.check_row_slice(sheet.row_slice)

    def test_row_types(self):
        sheet = self.book.sheet_by_index(SHEETINDEX)
        self.check_row_slice(sheet.col_types)

    def test_row_values(self):
        sheet = self.book.sheet_by_index(SHEETINDEX)
        self.check_col_slice(sheet.row_values)

class TestSheetRagged(TestCase):
    
    def test_read_ragged(self):
        book = xlrd.open_workbook(from_this_dir('ragged.xls'), ragged_rows=True)
        sheet = book.sheet_by_index(0)
        self.assertEqual(sheet.row_len(0), 3)
        self.assertEqual(sheet.row_len(1), 2)
        self.assertEqual(sheet.row_len(2), 1)
        self.assertEqual(sheet.row_len(3), 4)
        self.assertEqual(sheet.row_len(4), 4)

########NEW FILE########
__FILENAME__ = test_workbook
# Portions Copyright (C) 2010, Manfred Moitzi under a BSD licence

from unittest import TestCase
import os
import sys

from xlrd import open_workbook
from xlrd.book import Book
from xlrd.sheet import Sheet

from .base import from_this_dir

class TestWorkbook(TestCase):

    sheetnames = ['PROFILEDEF', 'AXISDEF', 'TRAVERSALCHAINAGE',
                  'AXISDATUMLEVELS', 'PROFILELEVELS']
    
    def setUp(self):
        self.book = open_workbook(from_this_dir('profiles.xls'))

    def test_open_workbook(self):
        self.assertTrue(isinstance(self.book, Book))

    def test_nsheets(self):
        self.assertEqual(self.book.nsheets, 5)

    def test_sheet_by_name(self):
        for name in self.sheetnames:
            sheet = self.book.sheet_by_name(name)
            self.assertTrue(isinstance(sheet, Sheet))
            self.assertEqual(name, sheet.name)

    def test_sheet_by_index(self):
        for index in range(5):
            sheet = self.book.sheet_by_index(index)
            self.assertTrue(isinstance(sheet, Sheet))
            self.assertEqual(sheet.name, self.sheetnames[index])

    def test_sheets(self):
        sheets = self.book.sheets()
        for index, sheet in enumerate(sheets):
            self.assertTrue(isinstance(sheet, Sheet))
            self.assertEqual(sheet.name, self.sheetnames[index])

    def test_sheet_names(self):
        self.assertEqual(self.sheetnames, self.book.sheet_names())


########NEW FILE########
__FILENAME__ = test_xldate
#!/usr/bin/env python
# Author:  mozman <mozman@gmx.at>
# Purpose: test xldate.py
# Created: 04.12.2010
# Copyright (C) 2010, Manfred Moitzi
# License: BSD licence

import sys
import unittest

from xlrd import xldate

DATEMODE = 0 # 1900-based

class TestXLDate(unittest.TestCase):
    def test_date_as_tuple(self):
        date = xldate.xldate_as_tuple(2741., DATEMODE)
        self.assertEqual(date, (1907, 7, 3, 0, 0, 0))
        date = xldate.xldate_as_tuple(38406., DATEMODE)
        self.assertEqual(date, (2005, 2, 23, 0, 0, 0))
        date = xldate.xldate_as_tuple(32266., DATEMODE)
        self.assertEqual(date, (1988, 5, 3, 0, 0, 0))

    def test_time_as_tuple(self):
        time = xldate.xldate_as_tuple(.273611, DATEMODE)
        self.assertEqual(time, (0, 0, 0, 6, 34, 0))
        time = xldate.xldate_as_tuple(.538889, DATEMODE)
        self.assertEqual(time, (0, 0, 0, 12, 56, 0))
        time = xldate.xldate_as_tuple(.741123, DATEMODE)
        self.assertEqual(time, (0, 0, 0, 17, 47, 13))

    def test_xldate_from_date_tuple(self):
        date = xldate.xldate_from_date_tuple( (1907, 7, 3), DATEMODE )
        self.assertAlmostEqual(date, 2741.)
        date = xldate.xldate_from_date_tuple( (2005, 2, 23), DATEMODE )
        self.assertAlmostEqual(date, 38406.)
        date = xldate.xldate_from_date_tuple( (1988, 5, 3), DATEMODE )
        self.assertAlmostEqual(date, 32266.)

    def test_xldate_from_time_tuple(self):
        time = xldate.xldate_from_time_tuple( (6, 34, 0) )
        self.assertAlmostEqual(time, .273611, places=6)
        time = xldate.xldate_from_time_tuple( (12, 56, 0) )
        self.assertAlmostEqual(time, .538889, places=6)
        time = xldate.xldate_from_time_tuple( (17, 47, 13) )
        self.assertAlmostEqual(time, .741123, places=6)

    def test_xldate_from_datetime_tuple(self):
        date = xldate.xldate_from_datetime_tuple( (1907, 7, 3, 6, 34, 0), DATEMODE)
        self.assertAlmostEqual(date, 2741.273611, places=6)
        date = xldate.xldate_from_datetime_tuple( (2005, 2, 23, 12, 56, 0), DATEMODE)
        self.assertAlmostEqual(date, 38406.538889, places=6)
        date = xldate.xldate_from_datetime_tuple( (1988, 5, 3, 17, 47, 13), DATEMODE)
        self.assertAlmostEqual(date, 32266.741123, places=6)

if __name__=='__main__':
    unittest.main()

########NEW FILE########
__FILENAME__ = test_xldate_to_datetime
###############################################################################
#
# Tests for the xlrd xldate.xldate_as_datetime() function.
#

import unittest
from datetime import datetime
from xlrd import xldate

not_1904 = False
is_1904 = True


class TestConvertToDateTime(unittest.TestCase):
    """
    Testcases to test the _xldate_to_datetime() function against dates
    extracted from Excel files, with 1900/1904 epochs.

    """

    def test_dates_and_times_1900_epoch(self):
        """
        Test the _xldate_to_datetime() function for dates and times in
        the Excel standard 1900 epoch.

        """
        # Test Excel dates strings and corresponding serial date numbers taken
        # from an Excel file.
        excel_dates = [
            # Excel's 0.0 date in the 1900 epoch is 1 day before 1900.
            ('1899-12-31T00:00:00.000', 0),

            # Date/time before the false Excel 1900 leapday.
            ('1900-02-28T02:11:11.986', 59.09111094906),

            # Date/time after the false Excel 1900 leapday.
            ('1900-03-01T05:46:44.068', 61.24078782403),

            # Random date/times in Excel's 0-9999.9999+ range.
            ('1982-08-25T00:15:20.213', 30188.010650613425),
            ('2065-04-19T00:16:48.290', 60376.011670023145),
            ('3222-06-11T03:08:08.251', 483014.13065105322),
            ('4379-08-03T06:14:48.580', 905652.26028449077),
            ('5949-12-30T12:59:54.263', 1479232.5416002662),

            # End of Excel's date range.
            ('9999-12-31T23:59:59.000', 2958465.999988426),
        ]

        # Convert the Excel date strings to datetime objects and compare
        # against the dateitme return value of xldate.xldate_as_datetime().
        for excel_date in excel_dates:
            exp = datetime.strptime(excel_date[0], "%Y-%m-%dT%H:%M:%S.%f")
            got = xldate.xldate_as_datetime(excel_date[1], not_1904)

            self.assertEqual(got, exp)

    def test_dates_only_1900_epoch(self):
        """
        Test the _xldate_to_datetime() function for dates in the Excel
        standard 1900 epoch.

        """
        # Test Excel dates strings and corresponding serial date numbers taken
        # from an Excel file.
        excel_dates = [
            # Excel's day 0 in the 1900 epoch is 1 day before 1900.
            ('1899-12-31', 0),

            # Excel's day 1 in the 1900 epoch.
            ('1900-01-01', 1),

            # Date/time before the false Excel 1900 leapday.
            ('1900-02-28', 59),

            # Date/time after the false Excel 1900 leapday.
            ('1900-03-01', 61),

            # Random date/times in Excel's 0-9999.9999+ range.
            ('1902-09-27', 1001),
            ('1999-12-31', 36525),
            ('2000-01-01', 36526),
            ('4000-12-31', 767376),
            ('4321-01-01', 884254),
            ('9999-01-01', 2958101),

            # End of Excel's date range.
            ('9999-12-31', 2958465),
        ]

        # Convert the Excel date strings to datetime objects and compare
        # against the dateitme return value of xldate.xldate_as_datetime().
        for excel_date in excel_dates:
            exp = datetime.strptime(excel_date[0], "%Y-%m-%d")
            got = xldate.xldate_as_datetime(excel_date[1], not_1904)

            self.assertEqual(got, exp)

    def test_dates_only_1904_epoch(self):
        """
        Test the _xldate_to_datetime() function for dates in the Excel
        Mac/1904 epoch.

        """
        # Test Excel dates strings and corresponding serial date numbers taken
        # from an Excel file.
        excel_dates = [
            # Excel's day 0 in the 1904 epoch.
            ('1904-01-01', 0),

            # Random date/times in Excel's 0-9999.9999+ range.
            ('1904-01-31', 30),
            ('1904-08-31', 243),
            ('1999-02-28', 34757),
            ('1999-12-31', 35063),
            ('2000-01-01', 35064),
            ('2400-12-31', 181526),
            ('4000-01-01', 765549),
            ('9999-01-01', 2956639),

            # End of Excel's date range.
            ('9999-12-31', 2957003),
        ]

        # Convert the Excel date strings to datetime objects and compare
        # against the dateitme return value of xldate.xldate_as_datetime().
        for excel_date in excel_dates:
            exp = datetime.strptime(excel_date[0], "%Y-%m-%d")
            got = xldate.xldate_as_datetime(excel_date[1], is_1904)

            self.assertEqual(got, exp)

    def test_times_only(self):
        """
        Test the _xldate_to_datetime() function for times only, i.e, the
        fractional part of the Excel date when the serial date is 0.

        """
        # Test Excel dates strings and corresponding serial date numbers taken
        # from an Excel file. The 1899-12-31 date is Excel's day 0.
        excel_dates = [
            # Random times in Excel's 0-0.9999+ range for 1 day.
            ('1899-12-31T00:00:00.000', 0),
            ('1899-12-31T00:15:20.213', 1.0650613425925924E-2),
            ('1899-12-31T02:24:37.095', 0.10042934027777778),
            ('1899-12-31T04:56:35.792', 0.2059698148148148),
            ('1899-12-31T07:31:20.407', 0.31343063657407405),
            ('1899-12-31T09:37:23.945', 0.40097158564814817),
            ('1899-12-31T12:09:48.602', 0.50681252314814818),
            ('1899-12-31T14:37:57.451', 0.60969271990740748),
            ('1899-12-31T17:04:02.415', 0.71113906250000003),
            ('1899-12-31T19:14:24.673', 0.80167445601851861),
            ('1899-12-31T21:39:05.944', 0.90215212962962965),
            ('1899-12-31T23:17:12.632', 0.97028509259259266),
            ('1899-12-31T23:59:59.999', 0.99999998842592586),
        ]

        # Convert the Excel date strings to datetime objects and compare
        # against the dateitme return value of xldate.xldate_as_datetime().
        for excel_date in excel_dates:
            exp = datetime.strptime(excel_date[0], "%Y-%m-%dT%H:%M:%S.%f")
            got = xldate.xldate_as_datetime(excel_date[1], not_1904)

            self.assertEqual(got, exp)

########NEW FILE########
__FILENAME__ = test_xlsx_comments
from unittest import TestCase

import os

from xlrd import open_workbook

from .base import from_this_dir

class TestXlsxComments(TestCase):

    def test_excel_comments(self):
        book = open_workbook(from_this_dir('test_comments_excel.xlsx'))
        sheet = book.sheet_by_index(0)

        note_map = sheet.cell_note_map
        self.assertEqual(len(note_map), 1)
        self.assertEqual(note_map[(0, 1)].text, 'hello')

    def test_excel_comments_multiline(self):
        book = open_workbook(from_this_dir('test_comments_excel.xlsx'))
        sheet = book.sheet_by_index(1)

        note_map = sheet.cell_note_map
        self.assertEqual(note_map[(1, 2)].text, '1st line\n2nd line')

    def test_excel_comments_two_t_elements(self):
        book = open_workbook(from_this_dir('test_comments_excel.xlsx'))
        sheet = book.sheet_by_index(2)

        note_map = sheet.cell_note_map
        self.assertEqual(note_map[(0, 0)].text, 'Author:\nTwo t elements')

    def test_excel_comments_no_t_elements(self):
        book = open_workbook(from_this_dir('test_comments_excel.xlsx'))
        sheet = book.sheet_by_index(3)

        note_map = sheet.cell_note_map
        self.assertEqual(note_map[(0,0)].text, '')

    def test_gdocs_comments(self):
        book = open_workbook(from_this_dir('test_comments_gdocs.xlsx'))
        sheet = book.sheet_by_index(0)

        note_map = sheet.cell_note_map
        self.assertEqual(len(note_map), 1)
        self.assertEqual(note_map[(0, 1)].text, 'Just a test')

########NEW FILE########
__FILENAME__ = biffh
# -*- coding: cp1252 -*-

##
# Support module for the xlrd package.
#
# <p>Portions copyright � 2005-2010 Stephen John Machin, Lingfo Pty Ltd</p>
# <p>This module is part of the xlrd package, which is released under a BSD-style licence.</p>
##

# 2010-03-01 SJM Reading SCL record
# 2010-03-01 SJM Added more record IDs for biff_dump & biff_count
# 2008-02-10 SJM BIFF2 BLANK record
# 2008-02-08 SJM Preparation for Excel 2.0 support
# 2008-02-02 SJM Added suffixes (_B2, _B2_ONLY, etc) on record names for biff_dump & biff_count
# 2007-12-04 SJM Added support for Excel 2.x (BIFF2) files.
# 2007-09-08 SJM Avoid crash when zero-length Unicode string missing options byte.
# 2007-04-22 SJM Remove experimental "trimming" facility.

from __future__ import print_function

DEBUG = 0

from struct import unpack
import sys
from .timemachine import *

class XLRDError(Exception):
    pass

##
# Parent of almost all other classes in the package. Defines a common "dump" method
# for debugging.

class BaseObject(object):

    _repr_these = []

    ##
    # @param f open file object, to which the dump is written
    # @param header text to write before the dump
    # @param footer text to write after the dump
    # @param indent number of leading spaces (for recursive calls)

    def dump(self, f=None, header=None, footer=None, indent=0):
        if f is None:
            f = sys.stderr
        if hasattr(self, "__slots__"):
            alist = []
            for attr in self.__slots__:
                alist.append((attr, getattr(self, attr)))
        else:
            alist = self.__dict__.items()
        alist = sorted(alist)
        pad = " " * indent
        if header is not None: print(header, file=f)
        list_type = type([])
        dict_type = type({})
        for attr, value in alist:
            if getattr(value, 'dump', None) and attr != 'book':
                value.dump(f,
                    header="%s%s (%s object):" % (pad, attr, value.__class__.__name__),
                    indent=indent+4)
            elif attr not in self._repr_these and (
                isinstance(value, list_type) or isinstance(value, dict_type)
                ):
                print("%s%s: %s, len = %d" % (pad, attr, type(value), len(value)), file=f)
            else:
                fprintf(f, "%s%s: %r\n", pad, attr, value)
        if footer is not None: print(footer, file=f)

FUN, FDT, FNU, FGE, FTX = range(5) # unknown, date, number, general, text
DATEFORMAT = FDT
NUMBERFORMAT = FNU

(
    XL_CELL_EMPTY,
    XL_CELL_TEXT,
    XL_CELL_NUMBER,
    XL_CELL_DATE,
    XL_CELL_BOOLEAN,
    XL_CELL_ERROR,
    XL_CELL_BLANK, # for use in debugging, gathering stats, etc
) = range(7)

biff_text_from_num = {
    0:  "(not BIFF)",
    20: "2.0",
    21: "2.1",
    30: "3",
    40: "4S",
    45: "4W",
    50: "5",
    70: "7",
    80: "8",
    85: "8X",
    }

##
# <p>This dictionary can be used to produce a text version of the internal codes
# that Excel uses for error cells. Here are its contents:
# <pre>
# 0x00: '#NULL!',  # Intersection of two cell ranges is empty
# 0x07: '#DIV/0!', # Division by zero
# 0x0F: '#VALUE!', # Wrong type of operand
# 0x17: '#REF!',   # Illegal or deleted cell reference
# 0x1D: '#NAME?',  # Wrong function or range name
# 0x24: '#NUM!',   # Value range overflow
# 0x2A: '#N/A',    # Argument or function not available
# </pre></p>

error_text_from_code = {
    0x00: '#NULL!',  # Intersection of two cell ranges is empty
    0x07: '#DIV/0!', # Division by zero
    0x0F: '#VALUE!', # Wrong type of operand
    0x17: '#REF!',   # Illegal or deleted cell reference
    0x1D: '#NAME?',  # Wrong function or range name
    0x24: '#NUM!',   # Value range overflow
    0x2A: '#N/A',    # Argument or function not available
}

BIFF_FIRST_UNICODE = 80

XL_WORKBOOK_GLOBALS = WBKBLOBAL = 0x5
XL_WORKBOOK_GLOBALS_4W = 0x100
XL_WORKSHEET = WRKSHEET = 0x10

XL_BOUNDSHEET_WORKSHEET = 0x00
XL_BOUNDSHEET_CHART     = 0x02
XL_BOUNDSHEET_VB_MODULE = 0x06

# XL_RK2 = 0x7e
XL_ARRAY  = 0x0221
XL_ARRAY2 = 0x0021
XL_BLANK = 0x0201
XL_BLANK_B2 = 0x01
XL_BOF = 0x809
XL_BOOLERR = 0x205
XL_BOOLERR_B2 = 0x5
XL_BOUNDSHEET = 0x85
XL_BUILTINFMTCOUNT = 0x56
XL_CF = 0x01B1
XL_CODEPAGE = 0x42
XL_COLINFO = 0x7D
XL_COLUMNDEFAULT = 0x20 # BIFF2 only
XL_COLWIDTH = 0x24 # BIFF2 only
XL_CONDFMT = 0x01B0
XL_CONTINUE = 0x3c
XL_COUNTRY = 0x8C
XL_DATEMODE = 0x22
XL_DEFAULTROWHEIGHT = 0x0225
XL_DEFCOLWIDTH = 0x55
XL_DIMENSION = 0x200
XL_DIMENSION2 = 0x0
XL_EFONT = 0x45
XL_EOF = 0x0a
XL_EXTERNNAME = 0x23
XL_EXTERNSHEET = 0x17
XL_EXTSST = 0xff
XL_FEAT11 = 0x872
XL_FILEPASS = 0x2f
XL_FONT = 0x31
XL_FONT_B3B4 = 0x231
XL_FORMAT = 0x41e
XL_FORMAT2 = 0x1E # BIFF2, BIFF3
XL_FORMULA = 0x6
XL_FORMULA3 = 0x206
XL_FORMULA4 = 0x406
XL_GCW = 0xab
XL_HLINK = 0x01B8
XL_QUICKTIP = 0x0800
XL_HORIZONTALPAGEBREAKS = 0x1b
XL_INDEX = 0x20b
XL_INTEGER = 0x2 # BIFF2 only
XL_IXFE = 0x44 # BIFF2 only
XL_LABEL = 0x204
XL_LABEL_B2 = 0x04
XL_LABELRANGES = 0x15f
XL_LABELSST = 0xfd
XL_LEFTMARGIN = 0x26
XL_TOPMARGIN = 0x28
XL_RIGHTMARGIN = 0x27
XL_BOTTOMMARGIN = 0x29
XL_HEADER = 0x14
XL_FOOTER = 0x15
XL_HCENTER = 0x83
XL_VCENTER = 0x84
XL_MERGEDCELLS = 0xE5
XL_MSO_DRAWING = 0x00EC
XL_MSO_DRAWING_GROUP = 0x00EB
XL_MSO_DRAWING_SELECTION = 0x00ED
XL_MULRK = 0xbd
XL_MULBLANK = 0xbe
XL_NAME = 0x18
XL_NOTE = 0x1c
XL_NUMBER = 0x203
XL_NUMBER_B2 = 0x3
XL_OBJ = 0x5D
XL_PAGESETUP = 0xA1
XL_PALETTE = 0x92
XL_PANE = 0x41
XL_PRINTGRIDLINES = 0x2B
XL_PRINTHEADERS = 0x2A
XL_RK = 0x27e
XL_ROW = 0x208
XL_ROW_B2 = 0x08
XL_RSTRING = 0xd6
XL_SCL = 0x00A0
XL_SHEETHDR = 0x8F # BIFF4W only
XL_SHEETPR = 0x81
XL_SHEETSOFFSET = 0x8E # BIFF4W only
XL_SHRFMLA = 0x04bc
XL_SST = 0xfc
XL_STANDARDWIDTH = 0x99
XL_STRING = 0x207
XL_STRING_B2 = 0x7
XL_STYLE = 0x293
XL_SUPBOOK = 0x1AE # aka EXTERNALBOOK in OOo docs
XL_TABLEOP = 0x236
XL_TABLEOP2 = 0x37
XL_TABLEOP_B2 = 0x36
XL_TXO = 0x1b6
XL_UNCALCED = 0x5e
XL_UNKNOWN = 0xffff
XL_VERTICALPAGEBREAKS = 0x1a
XL_WINDOW2    = 0x023E
XL_WINDOW2_B2 = 0x003E
XL_WRITEACCESS = 0x5C
XL_WSBOOL = XL_SHEETPR
XL_XF = 0xe0
XL_XF2 = 0x0043 # BIFF2 version of XF record
XL_XF3 = 0x0243 # BIFF3 version of XF record
XL_XF4 = 0x0443 # BIFF4 version of XF record

boflen = {0x0809: 8, 0x0409: 6, 0x0209: 6, 0x0009: 4}
bofcodes = (0x0809, 0x0409, 0x0209, 0x0009)

XL_FORMULA_OPCODES = (0x0006, 0x0406, 0x0206)

_cell_opcode_list = [
    XL_BOOLERR,
    XL_FORMULA,
    XL_FORMULA3,
    XL_FORMULA4,
    XL_LABEL,
    XL_LABELSST,
    XL_MULRK,
    XL_NUMBER,
    XL_RK,
    XL_RSTRING,
    ]
_cell_opcode_dict = {}
for _cell_opcode in _cell_opcode_list:
    _cell_opcode_dict[_cell_opcode] = 1

def is_cell_opcode(c):
    return c in  _cell_opcode_dict

def upkbits(tgt_obj, src, manifest, local_setattr=setattr):
    for n, mask, attr in manifest:
        local_setattr(tgt_obj, attr, (src & mask) >> n)

def upkbitsL(tgt_obj, src, manifest, local_setattr=setattr, local_int=int):
    for n, mask, attr in manifest:
        local_setattr(tgt_obj, attr, local_int((src & mask) >> n))

def unpack_string(data, pos, encoding, lenlen=1):
    nchars = unpack('<' + 'BH'[lenlen-1], data[pos:pos+lenlen])[0]
    pos += lenlen
    return unicode(data[pos:pos+nchars], encoding)

def unpack_string_update_pos(data, pos, encoding, lenlen=1, known_len=None):
    if known_len is not None:
        # On a NAME record, the length byte is detached from the front of the string.
        nchars = known_len
    else:
        nchars = unpack('<' + 'BH'[lenlen-1], data[pos:pos+lenlen])[0]
        pos += lenlen
    newpos = pos + nchars
    return (unicode(data[pos:newpos], encoding), newpos)

def unpack_unicode(data, pos, lenlen=2):
    "Return unicode_strg"
    nchars = unpack('<' + 'BH'[lenlen-1], data[pos:pos+lenlen])[0]
    if not nchars:
        # Ambiguous whether 0-length string should have an "options" byte.
        # Avoid crash if missing.
        return UNICODE_LITERAL("")
    pos += lenlen
    options = BYTES_ORD(data[pos])
    pos += 1
    # phonetic = options & 0x04
    # richtext = options & 0x08
    if options & 0x08:
        # rt = unpack('<H', data[pos:pos+2])[0] # unused
        pos += 2
    if options & 0x04:
        # sz = unpack('<i', data[pos:pos+4])[0] # unused
        pos += 4
    if options & 0x01:
        # Uncompressed UTF-16-LE
        rawstrg = data[pos:pos+2*nchars]
        # if DEBUG: print "nchars=%d pos=%d rawstrg=%r" % (nchars, pos, rawstrg)
        strg = unicode(rawstrg, 'utf_16_le')
        # pos += 2*nchars
    else:
        # Note: this is COMPRESSED (not ASCII!) encoding!!!
        # Merely returning the raw bytes would work OK 99.99% of the time
        # if the local codepage was cp1252 -- however this would rapidly go pear-shaped
        # for other codepages so we grit our Anglocentric teeth and return Unicode :-)

        strg = unicode(data[pos:pos+nchars], "latin_1")
        # pos += nchars
    # if richtext:
    #     pos += 4 * rt
    # if phonetic:
    #     pos += sz
    # return (strg, pos)
    return strg

def unpack_unicode_update_pos(data, pos, lenlen=2, known_len=None):
    "Return (unicode_strg, updated value of pos)"
    if known_len is not None:
        # On a NAME record, the length byte is detached from the front of the string.
        nchars = known_len
    else:
        nchars = unpack('<' + 'BH'[lenlen-1], data[pos:pos+lenlen])[0]
        pos += lenlen
    if not nchars and not data[pos:]:
        # Zero-length string with no options byte
        return (UNICODE_LITERAL(""), pos)
    options = BYTES_ORD(data[pos])
    pos += 1
    phonetic = options & 0x04
    richtext = options & 0x08
    if richtext:
        rt = unpack('<H', data[pos:pos+2])[0]
        pos += 2
    if phonetic:
        sz = unpack('<i', data[pos:pos+4])[0]
        pos += 4
    if options & 0x01:
        # Uncompressed UTF-16-LE
        strg = unicode(data[pos:pos+2*nchars], 'utf_16_le')
        pos += 2*nchars
    else:
        # Note: this is COMPRESSED (not ASCII!) encoding!!!
        strg = unicode(data[pos:pos+nchars], "latin_1")
        pos += nchars
    if richtext:
        pos += 4 * rt
    if phonetic:
        pos += sz
    return (strg, pos)

def unpack_cell_range_address_list_update_pos(
    output_list, data, pos, biff_version, addr_size=6):
    # output_list is updated in situ
    assert addr_size in (6, 8)
    # Used to assert size == 6 if not BIFF8, but pyWLWriter writes
    # BIFF8-only MERGEDCELLS records in a BIFF5 file!
    n, = unpack("<H", data[pos:pos+2])
    pos += 2
    if n:
        if addr_size == 6:
            fmt = "<HHBB"
        else:
            fmt = "<HHHH"
        for _unused in xrange(n):
            ra, rb, ca, cb = unpack(fmt, data[pos:pos+addr_size])
            output_list.append((ra, rb+1, ca, cb+1))
            pos += addr_size
    return pos

_brecstrg = """\
0000 DIMENSIONS_B2
0001 BLANK_B2
0002 INTEGER_B2_ONLY
0003 NUMBER_B2
0004 LABEL_B2
0005 BOOLERR_B2
0006 FORMULA
0007 STRING_B2
0008 ROW_B2
0009 BOF_B2
000A EOF
000B INDEX_B2_ONLY
000C CALCCOUNT
000D CALCMODE
000E PRECISION
000F REFMODE
0010 DELTA
0011 ITERATION
0012 PROTECT
0013 PASSWORD
0014 HEADER
0015 FOOTER
0016 EXTERNCOUNT
0017 EXTERNSHEET
0018 NAME_B2,5+
0019 WINDOWPROTECT
001A VERTICALPAGEBREAKS
001B HORIZONTALPAGEBREAKS
001C NOTE
001D SELECTION
001E FORMAT_B2-3
001F BUILTINFMTCOUNT_B2
0020 COLUMNDEFAULT_B2_ONLY
0021 ARRAY_B2_ONLY
0022 DATEMODE
0023 EXTERNNAME
0024 COLWIDTH_B2_ONLY
0025 DEFAULTROWHEIGHT_B2_ONLY
0026 LEFTMARGIN
0027 RIGHTMARGIN
0028 TOPMARGIN
0029 BOTTOMMARGIN
002A PRINTHEADERS
002B PRINTGRIDLINES
002F FILEPASS
0031 FONT
0032 FONT2_B2_ONLY
0036 TABLEOP_B2
0037 TABLEOP2_B2
003C CONTINUE
003D WINDOW1
003E WINDOW2_B2
0040 BACKUP
0041 PANE
0042 CODEPAGE
0043 XF_B2
0044 IXFE_B2_ONLY
0045 EFONT_B2_ONLY
004D PLS
0051 DCONREF
0055 DEFCOLWIDTH
0056 BUILTINFMTCOUNT_B3-4
0059 XCT
005A CRN
005B FILESHARING
005C WRITEACCESS
005D OBJECT
005E UNCALCED
005F SAVERECALC
0063 OBJECTPROTECT
007D COLINFO
007E RK2_mythical_?
0080 GUTS
0081 WSBOOL
0082 GRIDSET
0083 HCENTER
0084 VCENTER
0085 BOUNDSHEET
0086 WRITEPROT
008C COUNTRY
008D HIDEOBJ
008E SHEETSOFFSET
008F SHEETHDR
0090 SORT
0092 PALETTE
0099 STANDARDWIDTH
009B FILTERMODE
009C FNGROUPCOUNT
009D AUTOFILTERINFO
009E AUTOFILTER
00A0 SCL
00A1 SETUP
00AB GCW
00BD MULRK
00BE MULBLANK
00C1 MMS
00D6 RSTRING
00D7 DBCELL
00DA BOOKBOOL
00DD SCENPROTECT
00E0 XF
00E1 INTERFACEHDR
00E2 INTERFACEEND
00E5 MERGEDCELLS
00E9 BITMAP
00EB MSO_DRAWING_GROUP
00EC MSO_DRAWING
00ED MSO_DRAWING_SELECTION
00EF PHONETIC
00FC SST
00FD LABELSST
00FF EXTSST
013D TABID
015F LABELRANGES
0160 USESELFS
0161 DSF
01AE SUPBOOK
01AF PROTECTIONREV4
01B0 CONDFMT
01B1 CF
01B2 DVAL
01B6 TXO
01B7 REFRESHALL
01B8 HLINK
01BC PASSWORDREV4
01BE DV
01C0 XL9FILE
01C1 RECALCID
0200 DIMENSIONS
0201 BLANK
0203 NUMBER
0204 LABEL
0205 BOOLERR
0206 FORMULA_B3
0207 STRING
0208 ROW
0209 BOF
020B INDEX_B3+
0218 NAME
0221 ARRAY
0223 EXTERNNAME_B3-4
0225 DEFAULTROWHEIGHT
0231 FONT_B3B4
0236 TABLEOP
023E WINDOW2
0243 XF_B3
027E RK
0293 STYLE
0406 FORMULA_B4
0409 BOF
041E FORMAT
0443 XF_B4
04BC SHRFMLA
0800 QUICKTIP
0809 BOF
0862 SHEETLAYOUT
0867 SHEETPROTECTION
0868 RANGEPROTECTION
"""

biff_rec_name_dict = {}
for _buff in _brecstrg.splitlines():
    _numh, _name = _buff.split()
    biff_rec_name_dict[int(_numh, 16)] = _name
del _buff, _name, _brecstrg

def hex_char_dump(strg, ofs, dlen, base=0, fout=sys.stdout, unnumbered=False):
    endpos = min(ofs + dlen, len(strg))
    pos = ofs
    numbered = not unnumbered
    num_prefix = ''
    while pos < endpos:
        endsub = min(pos + 16, endpos)
        substrg = strg[pos:endsub]
        lensub = endsub - pos
        if lensub <= 0 or lensub != len(substrg):
            fprintf(
                sys.stdout,
                '??? hex_char_dump: ofs=%d dlen=%d base=%d -> endpos=%d pos=%d endsub=%d substrg=%r\n',
                ofs, dlen, base, endpos, pos, endsub, substrg)
            break
        hexd = ''.join(["%02x " % BYTES_ORD(c) for c in substrg])
        
        chard = ''
        for c in substrg:
            c = chr(BYTES_ORD(c))
            if c == '\0':
                c = '~'
            elif not (' ' <= c <= '~'):
                c = '?'
            chard += c
        if numbered:
            num_prefix = "%5d: " %  (base+pos-ofs)
        
        fprintf(fout, "%s     %-48s %s\n", num_prefix, hexd, chard)
        pos = endsub

def biff_dump(mem, stream_offset, stream_len, base=0, fout=sys.stdout, unnumbered=False):
    pos = stream_offset
    stream_end = stream_offset + stream_len
    adj = base - stream_offset
    dummies = 0
    numbered = not unnumbered
    num_prefix = ''
    while stream_end - pos >= 4:
        rc, length = unpack('<HH', mem[pos:pos+4])
        if rc == 0 and length == 0:
            if mem[pos:] == b'\0' * (stream_end - pos):
                dummies = stream_end - pos
                savpos = pos
                pos = stream_end
                break
            if dummies:
                dummies += 4
            else:
                savpos = pos
                dummies = 4
            pos += 4
        else:
            if dummies:
                if numbered:
                    num_prefix =  "%5d: " % (adj + savpos)
                fprintf(fout, "%s---- %d zero bytes skipped ----\n", num_prefix, dummies)
                dummies = 0
            recname = biff_rec_name_dict.get(rc, '<UNKNOWN>')
            if numbered:
                num_prefix = "%5d: " % (adj + pos)
            fprintf(fout, "%s%04x %s len = %04x (%d)\n", num_prefix, rc, recname, length, length)
            pos += 4
            hex_char_dump(mem, pos, length, adj+pos, fout, unnumbered)
            pos += length
    if dummies:
        if numbered:
            num_prefix =  "%5d: " % (adj + savpos)
        fprintf(fout, "%s---- %d zero bytes skipped ----\n", num_prefix, dummies)
    if pos < stream_end:
        if numbered:
            num_prefix = "%5d: " % (adj + pos)
        fprintf(fout, "%s---- Misc bytes at end ----\n", num_prefix)
        hex_char_dump(mem, pos, stream_end-pos, adj + pos, fout, unnumbered)
    elif pos > stream_end:
        fprintf(fout, "Last dumped record has length (%d) that is too large\n", length)

def biff_count_records(mem, stream_offset, stream_len, fout=sys.stdout):
    pos = stream_offset
    stream_end = stream_offset + stream_len
    tally = {}
    while stream_end - pos >= 4:
        rc, length = unpack('<HH', mem[pos:pos+4])
        if rc == 0 and length == 0:
            if mem[pos:] == b'\0' * (stream_end - pos):
                break
            recname = "<Dummy (zero)>"
        else:
            recname = biff_rec_name_dict.get(rc, None)
            if recname is None:
                recname = "Unknown_0x%04X" % rc
        if recname in tally:
            tally[recname] += 1
        else:
            tally[recname] = 1
        pos += length + 4
    slist = sorted(tally.items())
    for recname, count in slist:
        print("%8d %s" % (count, recname), file=fout)

encoding_from_codepage = {
    1200 : 'utf_16_le',
    10000: 'mac_roman',
    10006: 'mac_greek', # guess
    10007: 'mac_cyrillic', # guess
    10029: 'mac_latin2', # guess
    10079: 'mac_iceland', # guess
    10081: 'mac_turkish', # guess
    32768: 'mac_roman',
    32769: 'cp1252',
    }
# some more guessing, for Indic scripts
# codepage 57000 range:
# 2 Devanagari [0]
# 3 Bengali [1]
# 4 Tamil [5]
# 5 Telegu [6]
# 6 Assamese [1] c.f. Bengali
# 7 Oriya [4]
# 8 Kannada [7]
# 9 Malayalam [8]
# 10 Gujarati [3]
# 11 Gurmukhi [2]

########NEW FILE########
__FILENAME__ = book
# Copyright (c) 2005-2012 Stephen John Machin, Lingfo Pty Ltd
# This module is part of the xlrd package, which is released under a
# BSD-style licence.

from __future__ import print_function

from .timemachine import *
from .biffh import *
import struct; unpack = struct.unpack
import sys
import time
from . import sheet
from . import compdoc
from .formula import *
from . import formatting
if sys.version.startswith("IronPython"):
    # print >> sys.stderr, "...importing encodings"
    import encodings

empty_cell = sheet.empty_cell # for exposure to the world ...

DEBUG = 0

USE_FANCY_CD = 1

TOGGLE_GC = 0
import gc
# gc.set_debug(gc.DEBUG_STATS)

try:
    import mmap
    MMAP_AVAILABLE = 1
except ImportError:
    MMAP_AVAILABLE = 0
USE_MMAP = MMAP_AVAILABLE

MY_EOF = 0xF00BAAA # not a 16-bit number

SUPBOOK_UNK, SUPBOOK_INTERNAL, SUPBOOK_EXTERNAL, SUPBOOK_ADDIN, SUPBOOK_DDEOLE = range(5)

SUPPORTED_VERSIONS = (80, 70, 50, 45, 40, 30, 21, 20)

_code_from_builtin_name = {
    "Consolidate_Area": "\x00",
    "Auto_Open":        "\x01",
    "Auto_Close":       "\x02",
    "Extract":          "\x03",
    "Database":         "\x04",
    "Criteria":         "\x05",
    "Print_Area":       "\x06",
    "Print_Titles":     "\x07",
    "Recorder":         "\x08",
    "Data_Form":        "\x09",
    "Auto_Activate":    "\x0A",
    "Auto_Deactivate":  "\x0B",
    "Sheet_Title":      "\x0C",
    "_FilterDatabase":  "\x0D",
    }
builtin_name_from_code = {}
code_from_builtin_name = {}
for _bin, _bic in _code_from_builtin_name.items():
    _bin = UNICODE_LITERAL(_bin)
    _bic = UNICODE_LITERAL(_bic)
    code_from_builtin_name[_bin] = _bic
    builtin_name_from_code[_bic] = _bin
del _bin, _bic, _code_from_builtin_name

def open_workbook_xls(filename=None,
    logfile=sys.stdout, verbosity=0, use_mmap=USE_MMAP,
    file_contents=None,
    encoding_override=None,
    formatting_info=False, on_demand=False, ragged_rows=False,
    ):
    t0 = time.clock()
    if TOGGLE_GC:
        orig_gc_enabled = gc.isenabled()
        if orig_gc_enabled:
            gc.disable()
    bk = Book()
    try:
        bk.biff2_8_load(
            filename=filename, file_contents=file_contents,
            logfile=logfile, verbosity=verbosity, use_mmap=use_mmap,
            encoding_override=encoding_override,
            formatting_info=formatting_info,
            on_demand=on_demand,
            ragged_rows=ragged_rows,
            )
        t1 = time.clock()
        bk.load_time_stage_1 = t1 - t0
        biff_version = bk.getbof(XL_WORKBOOK_GLOBALS)
        if not biff_version:
            raise XLRDError("Can't determine file's BIFF version")
        if biff_version not in SUPPORTED_VERSIONS:
            raise XLRDError(
                "BIFF version %s is not supported"
                % biff_text_from_num[biff_version]
                )
        bk.biff_version = biff_version
        if biff_version <= 40:
            # no workbook globals, only 1 worksheet
            if on_demand:
                fprintf(bk.logfile,
                    "*** WARNING: on_demand is not supported for this Excel version.\n"
                    "*** Setting on_demand to False.\n")
                bk.on_demand = on_demand = False
            bk.fake_globals_get_sheet()
        elif biff_version == 45:
            # worksheet(s) embedded in global stream
            bk.parse_globals()
            if on_demand:
                fprintf(bk.logfile, "*** WARNING: on_demand is not supported for this Excel version.\n"
                                    "*** Setting on_demand to False.\n")
                bk.on_demand = on_demand = False
        else:
            bk.parse_globals()
            bk._sheet_list = [None for sh in bk._sheet_names]
            if not on_demand:
                bk.get_sheets()
        bk.nsheets = len(bk._sheet_list)
        if biff_version == 45 and bk.nsheets > 1:
            fprintf(bk.logfile,
                "*** WARNING: Excel 4.0 workbook (.XLW) file contains %d worksheets.\n"
                "*** Book-level data will be that of the last worksheet.\n",
                bk.nsheets
                )
        if TOGGLE_GC:
            if orig_gc_enabled:
                gc.enable()
        t2 = time.clock()
        bk.load_time_stage_2 = t2 - t1
    except:
        bk.release_resources()
        raise
    # normal exit
    if not on_demand:
        bk.release_resources()
    return bk

##
# For debugging: dump the file's BIFF records in char & hex.
# @param filename The path to the file to be dumped.
# @param outfile An open file, to which the dump is written.
# @param unnumbered If true, omit offsets (for meaningful diffs).

def dump(filename, outfile=sys.stdout, unnumbered=False):
    bk = Book()
    bk.biff2_8_load(filename=filename, logfile=outfile, )
    biff_dump(bk.mem, bk.base, bk.stream_len, 0, outfile, unnumbered)

##
# For debugging and analysis: summarise the file's BIFF records.
# I.e. produce a sorted file of (record_name, count).
# @param filename The path to the file to be summarised.
# @param outfile An open file, to which the summary is written.

def count_records(filename, outfile=sys.stdout):
    bk = Book()
    bk.biff2_8_load(filename=filename, logfile=outfile, )
    biff_count_records(bk.mem, bk.base, bk.stream_len, outfile)

##
# Information relating to a named reference, formula, macro, etc.
# <br />  -- New in version 0.6.0
# <br />  -- <i>Name information is <b>not</b> extracted from files older than
# Excel 5.0 (Book.biff_version < 50)</i>

class Name(BaseObject):

    _repr_these = ['stack']
    book = None # parent

    ##
    # 0 = Visible; 1 = Hidden
    hidden = 0

    ##
    # 0 = Command macro; 1 = Function macro. Relevant only if macro == 1
    func = 0

    ##
    # 0 = Sheet macro; 1 = VisualBasic macro. Relevant only if macro == 1
    vbasic = 0

    ##
    # 0 = Standard name; 1 = Macro name
    macro = 0

    ##
    # 0 = Simple formula; 1 = Complex formula (array formula or user defined)<br />
    # <i>No examples have been sighted.</i>
    complex = 0

    ##
    # 0 = User-defined name; 1 = Built-in name
    # (common examples: Print_Area, Print_Titles; see OOo docs for full list)
    builtin = 0

    ##
    # Function group. Relevant only if macro == 1; see OOo docs for values.
    funcgroup = 0

    ##
    # 0 = Formula definition; 1 = Binary data<br />  <i>No examples have been sighted.</i>
    binary = 0

    ##
    # The index of this object in book.name_obj_list
    name_index = 0

    ##
    # A Unicode string. If builtin, decoded as per OOo docs.
    name = UNICODE_LITERAL("")

    ##
    # An 8-bit string.
    raw_formula = b''

    ##
    # -1: The name is global (visible in all calculation sheets).<br />
    # -2: The name belongs to a macro sheet or VBA sheet.<br />
    # -3: The name is invalid.<br />
    # 0 <= scope < book.nsheets: The name is local to the sheet whose index is scope.
    scope = -1

    ##
    # The result of evaluating the formula, if any.
    # If no formula, or evaluation of the formula encountered problems,
    # the result is None. Otherwise the result is a single instance of the
    # Operand class.
    #
    result = None

    ##
    # This is a convenience method for the frequent use case where the name
    # refers to a single cell.
    # @return An instance of the Cell class.
    # @throws XLRDError The name is not a constant absolute reference
    # to a single cell.
    def cell(self):
        res = self.result
        if res:
            # result should be an instance of the Operand class
            kind = res.kind
            value = res.value
            if kind == oREF and len(value) == 1:
                ref3d = value[0]
                if (0 <= ref3d.shtxlo == ref3d.shtxhi - 1
                and      ref3d.rowxlo == ref3d.rowxhi - 1
                and      ref3d.colxlo == ref3d.colxhi - 1):
                    sh = self.book.sheet_by_index(ref3d.shtxlo)
                    return sh.cell(ref3d.rowxlo, ref3d.colxlo)
        self.dump(self.book.logfile,
            header="=== Dump of Name object ===",
            footer="======= End of dump =======",
            )
        raise XLRDError("Not a constant absolute reference to a single cell")

    ##
    # This is a convenience method for the use case where the name
    # refers to one rectangular area in one worksheet.
    # @param clipped If true (the default), the returned rectangle is clipped
    # to fit in (0, sheet.nrows, 0, sheet.ncols) -- it is guaranteed that
    # 0 <= rowxlo <= rowxhi <= sheet.nrows and that the number of usable rows
    # in the area (which may be zero) is rowxhi - rowxlo; likewise for columns.
    # @return a tuple (sheet_object, rowxlo, rowxhi, colxlo, colxhi).
    # @throws XLRDError The name is not a constant absolute reference
    # to a single area in a single sheet.
    def area2d(self, clipped=True):
        res = self.result
        if res:
            # result should be an instance of the Operand class
            kind = res.kind
            value = res.value
            if kind == oREF and len(value) == 1: # only 1 reference
                ref3d = value[0]
                if 0 <= ref3d.shtxlo == ref3d.shtxhi - 1: # only 1 usable sheet
                    sh = self.book.sheet_by_index(ref3d.shtxlo)
                    if not clipped:
                        return sh, ref3d.rowxlo, ref3d.rowxhi, ref3d.colxlo, ref3d.colxhi
                    rowxlo = min(ref3d.rowxlo, sh.nrows)
                    rowxhi = max(rowxlo, min(ref3d.rowxhi, sh.nrows))
                    colxlo = min(ref3d.colxlo, sh.ncols)
                    colxhi = max(colxlo, min(ref3d.colxhi, sh.ncols))
                    assert 0 <= rowxlo <= rowxhi <= sh.nrows
                    assert 0 <= colxlo <= colxhi <= sh.ncols
                    return sh, rowxlo, rowxhi, colxlo, colxhi
        self.dump(self.book.logfile,
            header="=== Dump of Name object ===",
            footer="======= End of dump =======",
            )
        raise XLRDError("Not a constant absolute reference to a single area in a single sheet")

##
# Contents of a "workbook".
# <p>WARNING: You don't call this class yourself. You use the Book object that
# was returned when you called xlrd.open_workbook("myfile.xls").</p>

class Book(BaseObject):

    ##
    # The number of worksheets present in the workbook file.
    # This information is available even when no sheets have yet been loaded.
    nsheets = 0

    ##
    # Which date system was in force when this file was last saved.<br />
    #    0 => 1900 system (the Excel for Windows default).<br />
    #    1 => 1904 system (the Excel for Macintosh default).<br />
    datemode = 0 # In case it's not specified in the file.

    ##
    # Version of BIFF (Binary Interchange File Format) used to create the file.
    # Latest is 8.0 (represented here as 80), introduced with Excel 97.
    # Earliest supported by this module: 2.0 (represented as 20).
    biff_version = 0

    ##
    # List containing a Name object for each NAME record in the workbook.
    # <br />  -- New in version 0.6.0
    name_obj_list = []

    ##
    # An integer denoting the character set used for strings in this file.
    # For BIFF 8 and later, this will be 1200, meaning Unicode; more precisely, UTF_16_LE.
    # For earlier versions, this is used to derive the appropriate Python encoding
    # to be used to convert to Unicode.
    # Examples: 1252 -> 'cp1252', 10000 -> 'mac_roman'
    codepage = None

    ##
    # The encoding that was derived from the codepage.
    encoding = None

    ##
    # A tuple containing the (telephone system) country code for:<br />
    #    [0]: the user-interface setting when the file was created.<br />
    #    [1]: the regional settings.<br />
    # Example: (1, 61) meaning (USA, Australia).
    # This information may give a clue to the correct encoding for an unknown codepage.
    # For a long list of observed values, refer to the OpenOffice.org documentation for
    # the COUNTRY record.
    countries = (0, 0)

    ##
    # What (if anything) is recorded as the name of the last user to save the file.
    user_name = UNICODE_LITERAL('')

    ##
    # A list of Font class instances, each corresponding to a FONT record.
    # <br /> -- New in version 0.6.1
    font_list = []

    ##
    # A list of XF class instances, each corresponding to an XF record.
    # <br /> -- New in version 0.6.1
    xf_list = []

    ##
    # A list of Format objects, each corresponding to a FORMAT record, in
    # the order that they appear in the input file.
    # It does <i>not</i> contain builtin formats.
    # If you are creating an output file using (for example) pyExcelerator,
    # use this list.
    # The collection to be used for all visual rendering purposes is format_map.
    # <br /> -- New in version 0.6.1
    format_list = []

    ##
    # The mapping from XF.format_key to Format object.
    # <br /> -- New in version 0.6.1
    format_map = {}

    ##
    # This provides access via name to the extended format information for
    # both built-in styles and user-defined styles.<br />
    # It maps <i>name</i> to (<i>built_in</i>, <i>xf_index</i>), where:<br />
    # <i>name</i> is either the name of a user-defined style,
    # or the name of one of the built-in styles. Known built-in names are
    # Normal, RowLevel_1 to RowLevel_7,
    # ColLevel_1 to ColLevel_7, Comma, Currency, Percent, "Comma [0]",
    # "Currency [0]", Hyperlink, and "Followed Hyperlink".<br />
    # <i>built_in</i> 1 = built-in style, 0 = user-defined<br />
    # <i>xf_index</i> is an index into Book.xf_list.<br />
    # References: OOo docs s6.99 (STYLE record); Excel UI Format/Style
    # <br /> -- New in version 0.6.1; since 0.7.4, extracted only if
    # open_workbook(..., formatting_info=True)
    style_name_map = {}

    ##
    # This provides definitions for colour indexes. Please refer to the
    # above section "The Palette; Colour Indexes" for an explanation
    # of how colours are represented in Excel.<br />
    # Colour indexes into the palette map into (red, green, blue) tuples.
    # "Magic" indexes e.g. 0x7FFF map to None.
    # <i>colour_map</i> is what you need if you want to render cells on screen or in a PDF
    # file. If you are writing an output XLS file, use <i>palette_record</i>.
    # <br /> -- New in version 0.6.1. Extracted only if open_workbook(..., formatting_info=True)
    colour_map = {}

    ##
    # If the user has changed any of the colours in the standard palette, the XLS
    # file will contain a PALETTE record with 56 (16 for Excel 4.0 and earlier)
    # RGB values in it, and this list will be e.g. [(r0, b0, g0), ..., (r55, b55, g55)].
    # Otherwise this list will be empty. This is what you need if you are
    # writing an output XLS file. If you want to render cells on screen or in a PDF
    # file, use colour_map.
    # <br /> -- New in version 0.6.1. Extracted only if open_workbook(..., formatting_info=True)
    palette_record = []

    ##
    # Time in seconds to extract the XLS image as a contiguous string (or mmap equivalent).
    load_time_stage_1 = -1.0

    ##
    # Time in seconds to parse the data from the contiguous string (or mmap equivalent).
    load_time_stage_2 = -1.0

    ##
    # @return A list of all sheets in the book.
    # All sheets not already loaded will be loaded.
    def sheets(self):
        for sheetx in xrange(self.nsheets):
            if not self._sheet_list[sheetx]:
                self.get_sheet(sheetx)
        return self._sheet_list[:]

    ##
    # @param sheetx Sheet index in range(nsheets)
    # @return An object of the Sheet class
    def sheet_by_index(self, sheetx):
        return self._sheet_list[sheetx] or self.get_sheet(sheetx)

    ##
    # @param sheet_name Name of sheet required
    # @return An object of the Sheet class
    def sheet_by_name(self, sheet_name):
        try:
            sheetx = self._sheet_names.index(sheet_name)
        except ValueError:
            raise XLRDError('No sheet named <%r>' % sheet_name)
        return self.sheet_by_index(sheetx)

    ##
    # @return A list of the names of all the worksheets in the workbook file.
    # This information is available even when no sheets have yet been loaded.
    def sheet_names(self):
        return self._sheet_names[:]

    ##
    # @param sheet_name_or_index Name or index of sheet enquired upon
    # @return true if sheet is loaded, false otherwise
    # <br />  -- New in version 0.7.1
    def sheet_loaded(self, sheet_name_or_index):
        if isinstance(sheet_name_or_index, int):
            sheetx = sheet_name_or_index
        else:
            try:
                sheetx = self._sheet_names.index(sheet_name_or_index)
            except ValueError:
                raise XLRDError('No sheet named <%r>' % sheet_name_or_index)
        return bool(self._sheet_list[sheetx])

    ##
    # @param sheet_name_or_index Name or index of sheet to be unloaded.
    # <br />  -- New in version 0.7.1
    def unload_sheet(self, sheet_name_or_index):
        if isinstance(sheet_name_or_index, int):
            sheetx = sheet_name_or_index
        else:
            try:
                sheetx = self._sheet_names.index(sheet_name_or_index)
            except ValueError:
                raise XLRDError('No sheet named <%r>' % sheet_name_or_index)
        self._sheet_list[sheetx] = None
        
    ##
    # This method has a dual purpose. You can call it to release
    # memory-consuming objects and (possibly) a memory-mapped file
    # (mmap.mmap object) when you have finished loading sheets in
    # on_demand mode, but still require the Book object to examine the
    # loaded sheets. It is also called automatically (a) when open_workbook
    # raises an exception and (b) if you are using a "with" statement, when 
    # the "with" block is exited. Calling this method multiple times on the 
    # same object has no ill effect.
    def release_resources(self):
        self._resources_released = 1
        if hasattr(self.mem, "close"):
            # must be a mmap.mmap object
            self.mem.close()
        self.mem = None
        if hasattr(self.filestr, "close"):
            self.filestr.close()
        self.filestr = None
        self._sharedstrings = None
        self._rich_text_runlist_map = None
    
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_value, exc_tb):
        self.release_resources()
        # return false        

    ##
    # A mapping from (lower_case_name, scope) to a single Name object.
    # <br />  -- New in version 0.6.0
    name_and_scope_map = {}

    ##
    # A mapping from lower_case_name to a list of Name objects. The list is
    # sorted in scope order. Typically there will be one item (of global scope)
    # in the list.
    # <br />  -- New in version 0.6.0
    name_map = {}

    def __init__(self):
        self._sheet_list = []
        self._sheet_names = []
        self._sheet_visibility = [] # from BOUNDSHEET record
        self.nsheets = 0
        self._sh_abs_posn = [] # sheet's absolute position in the stream
        self._sharedstrings = []
        self._rich_text_runlist_map = {}
        self.raw_user_name = False
        self._sheethdr_count = 0 # BIFF 4W only
        self.builtinfmtcount = -1 # unknown as yet. BIFF 3, 4S, 4W
        self.initialise_format_info()
        self._all_sheets_count = 0 # includes macro & VBA sheets
        self._supbook_count = 0
        self._supbook_locals_inx = None
        self._supbook_addins_inx = None
        self._all_sheets_map = [] # maps an all_sheets index to a calc-sheets index (or -1)
        self._externsheet_info = []
        self._externsheet_type_b57 = []
        self._extnsht_name_from_num = {}
        self._sheet_num_from_name = {}
        self._extnsht_count = 0
        self._supbook_types = []
        self._resources_released = 0
        self.addin_func_names = []
        self.name_obj_list = []
        self.colour_map = {}
        self.palette_record = []
        self.xf_list = []
        self.style_name_map = {}
        self.mem = b''
        self.filestr = b''

    def biff2_8_load(self, filename=None, file_contents=None,
        logfile=sys.stdout, verbosity=0, use_mmap=USE_MMAP,
        encoding_override=None,
        formatting_info=False,
        on_demand=False,
        ragged_rows=False,
        ):
        # DEBUG = 0
        self.logfile = logfile
        self.verbosity = verbosity
        self.use_mmap = use_mmap and MMAP_AVAILABLE
        self.encoding_override = encoding_override
        self.formatting_info = formatting_info
        self.on_demand = on_demand
        self.ragged_rows = ragged_rows

        if not file_contents:
            with open(filename, "rb") as f:
                f.seek(0, 2) # EOF
                size = f.tell()
                f.seek(0, 0) # BOF
                if size == 0:
                    raise XLRDError("File size is 0 bytes")
                if self.use_mmap:
                    self.filestr = mmap.mmap(f.fileno(), size, access=mmap.ACCESS_READ)
                    self.stream_len = size
                else:
                    self.filestr = f.read()
                    self.stream_len = len(self.filestr)
        else:
            self.filestr = file_contents
            self.stream_len = len(file_contents)

        self.base = 0
        if self.filestr[:8] != compdoc.SIGNATURE:
            # got this one at the antique store
            self.mem = self.filestr
        else:
            cd = compdoc.CompDoc(self.filestr, logfile=self.logfile)
            if USE_FANCY_CD:
                for qname in ['Workbook', 'Book']:
                    self.mem, self.base, self.stream_len = \
                                cd.locate_named_stream(UNICODE_LITERAL(qname))
                    if self.mem: break
                else:
                    raise XLRDError("Can't find workbook in OLE2 compound document")
            else:
                for qname in ['Workbook', 'Book']:
                    self.mem = cd.get_named_stream(UNICODE_LITERAL(qname))
                    if self.mem: break
                else:
                    raise XLRDError("Can't find workbook in OLE2 compound document")
                self.stream_len = len(self.mem)
            del cd
            if self.mem is not self.filestr:
                if hasattr(self.filestr, "close"):
                    self.filestr.close()
                self.filestr = b''
        self._position = self.base
        if DEBUG:
            print("mem: %s, base: %d, len: %d" % (type(self.mem), self.base, self.stream_len), file=self.logfile)

    def initialise_format_info(self):
        # needs to be done once per sheet for BIFF 4W :-(
        self.format_map = {}
        self.format_list = []
        self.xfcount = 0
        self.actualfmtcount = 0 # number of FORMAT records seen so far
        self._xf_index_to_xl_type_map = {0: XL_CELL_NUMBER}
        self._xf_epilogue_done = 0
        self.xf_list = []
        self.font_list = []

    def get2bytes(self):
        pos = self._position
        buff_two = self.mem[pos:pos+2]
        lenbuff = len(buff_two)
        self._position += lenbuff
        if lenbuff < 2:
            return MY_EOF
        lo, hi = buff_two
        return (BYTES_ORD(hi) << 8) | BYTES_ORD(lo)

    def get_record_parts(self):
        pos = self._position
        mem = self.mem
        code, length = unpack('<HH', mem[pos:pos+4])
        pos += 4
        data = mem[pos:pos+length]
        self._position = pos + length
        return (code, length, data)

    def get_record_parts_conditional(self, reqd_record):
        pos = self._position
        mem = self.mem
        code, length = unpack('<HH', mem[pos:pos+4])
        if code != reqd_record:
            return (None, 0, b'')
        pos += 4
        data = mem[pos:pos+length]
        self._position = pos + length
        return (code, length, data)

    def get_sheet(self, sh_number, update_pos=True):
        if self._resources_released:
            raise XLRDError("Can't load sheets after releasing resources.")
        if update_pos:
            self._position = self._sh_abs_posn[sh_number]
        _unused_biff_version = self.getbof(XL_WORKSHEET)
        # assert biff_version == self.biff_version ### FAILS
        # Have an example where book is v7 but sheet reports v8!!!
        # It appears to work OK if the sheet version is ignored.
        # Confirmed by Daniel Rentz: happens when Excel does "save as"
        # creating an old version file; ignore version details on sheet BOF.
        sh = sheet.Sheet(self,
                self._position,
                self._sheet_names[sh_number],
                sh_number,
                )
        sh.read(self)
        self._sheet_list[sh_number] = sh
        return sh

    def get_sheets(self):
        # DEBUG = 0
        if DEBUG: print("GET_SHEETS:", self._sheet_names, self._sh_abs_posn, file=self.logfile)
        for sheetno in xrange(len(self._sheet_names)):
            if DEBUG: print("GET_SHEETS: sheetno =", sheetno, self._sheet_names, self._sh_abs_posn, file=self.logfile)
            self.get_sheet(sheetno)

    def fake_globals_get_sheet(self): # for BIFF 4.0 and earlier
        formatting.initialise_book(self)
        fake_sheet_name = UNICODE_LITERAL('Sheet 1')
        self._sheet_names = [fake_sheet_name]
        self._sh_abs_posn = [0]
        self._sheet_visibility = [0] # one sheet, visible
        self._sheet_list.append(None) # get_sheet updates _sheet_list but needs a None beforehand
        self.get_sheets()

    def handle_boundsheet(self, data):
        # DEBUG = 1
        bv = self.biff_version
        self.derive_encoding()
        if DEBUG:
            fprintf(self.logfile, "BOUNDSHEET: bv=%d data %r\n", bv, data);
        if bv == 45: # BIFF4W
            #### Not documented in OOo docs ...
            # In fact, the *only* data is the name of the sheet.
            sheet_name = unpack_string(data, 0, self.encoding, lenlen=1)
            visibility = 0
            sheet_type = XL_BOUNDSHEET_WORKSHEET # guess, patch later
            if len(self._sh_abs_posn) == 0:
                abs_posn = self._sheetsoffset + self.base
                # Note (a) this won't be used
                # (b) it's the position of the SHEETHDR record
                # (c) add 11 to get to the worksheet BOF record
            else:
                abs_posn = -1 # unknown
        else:
            offset, visibility, sheet_type = unpack('<iBB', data[0:6])
            abs_posn = offset + self.base # because global BOF is always at posn 0 in the stream
            if bv < BIFF_FIRST_UNICODE:
                sheet_name = unpack_string(data, 6, self.encoding, lenlen=1)
            else:
                sheet_name = unpack_unicode(data, 6, lenlen=1)

        if DEBUG or self.verbosity >= 2:
            fprintf(self.logfile,
                "BOUNDSHEET: inx=%d vis=%r sheet_name=%r abs_posn=%d sheet_type=0x%02x\n",
                self._all_sheets_count, visibility, sheet_name, abs_posn, sheet_type)
        self._all_sheets_count += 1
        if sheet_type != XL_BOUNDSHEET_WORKSHEET:
            self._all_sheets_map.append(-1)
            descr = {
                1: 'Macro sheet',
                2: 'Chart',
                6: 'Visual Basic module',
                }.get(sheet_type, 'UNKNOWN')

            if DEBUG or self.verbosity >= 1:
                fprintf(self.logfile,
                    "NOTE *** Ignoring non-worksheet data named %r (type 0x%02x = %s)\n",
                    sheet_name, sheet_type, descr)
        else:
            snum = len(self._sheet_names)
            self._all_sheets_map.append(snum)
            self._sheet_names.append(sheet_name)
            self._sh_abs_posn.append(abs_posn)
            self._sheet_visibility.append(visibility)
            self._sheet_num_from_name[sheet_name] = snum

    def handle_builtinfmtcount(self, data):
        ### N.B. This count appears to be utterly useless.
        # DEBUG = 1
        builtinfmtcount = unpack('<H', data[0:2])[0]
        if DEBUG: fprintf(self.logfile, "BUILTINFMTCOUNT: %r\n", builtinfmtcount)
        self.builtinfmtcount = builtinfmtcount

    def derive_encoding(self):
        if self.encoding_override:
            self.encoding = self.encoding_override
        elif self.codepage is None:
            if self.biff_version < 80:
                fprintf(self.logfile,
                    "*** No CODEPAGE record, no encoding_override: will use 'ascii'\n")
                self.encoding = 'ascii'
            else:
                self.codepage = 1200 # utf16le
                if self.verbosity >= 2:
                    fprintf(self.logfile, "*** No CODEPAGE record; assuming 1200 (utf_16_le)\n")
        else:
            codepage = self.codepage
            if codepage in encoding_from_codepage:
                encoding = encoding_from_codepage[codepage]
            elif 300 <= codepage <= 1999:
                encoding = 'cp' + str(codepage)
            else:
                encoding = 'unknown_codepage_' + str(codepage)
            if DEBUG or (self.verbosity and encoding != self.encoding) :
                fprintf(self.logfile, "CODEPAGE: codepage %r -> encoding %r\n", codepage, encoding)
            self.encoding = encoding
        if self.codepage != 1200: # utf_16_le
            # If we don't have a codec that can decode ASCII into Unicode,
            # we're well & truly stuffed -- let the punter know ASAP.
            try:
                _unused = unicode(b'trial', self.encoding)
            except BaseException as e:
                fprintf(self.logfile,
                    "ERROR *** codepage %r -> encoding %r -> %s: %s\n",
                    self.codepage, self.encoding, type(e).__name__.split(".")[-1], e)
                raise
        if self.raw_user_name:
            strg = unpack_string(self.user_name, 0, self.encoding, lenlen=1)
            strg = strg.rstrip()
            # if DEBUG:
            #     print "CODEPAGE: user name decoded from %r to %r" % (self.user_name, strg)
            self.user_name = strg
            self.raw_user_name = False
        return self.encoding

    def handle_codepage(self, data):
        # DEBUG = 0
        codepage = unpack('<H', data[0:2])[0]
        self.codepage = codepage
        self.derive_encoding()

    def handle_country(self, data):
        countries = unpack('<HH', data[0:4])
        if self.verbosity: print("Countries:", countries, file=self.logfile)
        # Note: in BIFF7 and earlier, country record was put (redundantly?) in each worksheet.
        assert self.countries == (0, 0) or self.countries == countries
        self.countries = countries

    def handle_datemode(self, data):
        datemode = unpack('<H', data[0:2])[0]
        if DEBUG or self.verbosity:
            fprintf(self.logfile, "DATEMODE: datemode %r\n", datemode)
        assert datemode in (0, 1)
        self.datemode = datemode

    def handle_externname(self, data):
        blah = DEBUG or self.verbosity >= 2
        if self.biff_version >= 80:
            option_flags, other_info =unpack("<HI", data[:6])
            pos = 6
            name, pos = unpack_unicode_update_pos(data, pos, lenlen=1)
            extra = data[pos:]
            if self._supbook_types[-1] == SUPBOOK_ADDIN:
                self.addin_func_names.append(name)
            if blah:
                fprintf(self.logfile,
                    "EXTERNNAME: sbktype=%d oflags=0x%04x oinfo=0x%08x name=%r extra=%r\n",
                    self._supbook_types[-1], option_flags, other_info, name, extra)

    def handle_externsheet(self, data):
        self.derive_encoding() # in case CODEPAGE record missing/out of order/wrong
        self._extnsht_count += 1 # for use as a 1-based index
        blah1 = DEBUG or self.verbosity >= 1
        blah2 = DEBUG or self.verbosity >= 2
        if self.biff_version >= 80:
            num_refs = unpack("<H", data[0:2])[0]
            bytes_reqd = num_refs * 6 + 2
            while len(data) < bytes_reqd:
                if blah1:
                    fprintf(
                        self.logfile,
                        "INFO: EXTERNSHEET needs %d bytes, have %d\n",
                        bytes_reqd, len(data),
                        )
                code2, length2, data2 = self.get_record_parts()
                if code2 != XL_CONTINUE:
                    raise XLRDError("Missing CONTINUE after EXTERNSHEET record")
                data += data2
            pos = 2
            for k in xrange(num_refs):
                info = unpack("<HHH", data[pos:pos+6])
                ref_recordx, ref_first_sheetx, ref_last_sheetx = info
                self._externsheet_info.append(info)
                pos += 6
                if blah2:
                    fprintf(
                        self.logfile,
                        "EXTERNSHEET(b8): k = %2d, record = %2d, first_sheet = %5d, last sheet = %5d\n",
                        k, ref_recordx, ref_first_sheetx, ref_last_sheetx,
                        )
        else:
            nc, ty = unpack("<BB", data[:2])
            if blah2:
                print("EXTERNSHEET(b7-):", file=self.logfile)
                hex_char_dump(data, 0, len(data), fout=self.logfile)
                msg = {
                    1: "Encoded URL",
                    2: "Current sheet!!",
                    3: "Specific sheet in own doc't",
                    4: "Nonspecific sheet in own doc't!!",
                    }.get(ty, "Not encoded")
                print("   %3d chars, type is %d (%s)" % (nc, ty, msg), file=self.logfile)
            if ty == 3:
                sheet_name = unicode(data[2:nc+2], self.encoding)
                self._extnsht_name_from_num[self._extnsht_count] = sheet_name
                if blah2: print(self._extnsht_name_from_num, file=self.logfile)
            if not (1 <= ty <= 4):
                ty = 0
            self._externsheet_type_b57.append(ty)

    def handle_filepass(self, data):
        if self.verbosity >= 2:
            logf = self.logfile
            fprintf(logf, "FILEPASS:\n")
            hex_char_dump(data, 0, len(data), base=0, fout=logf)
            if self.biff_version >= 80:
                kind1, = unpack('<H', data[:2])
                if kind1 == 0: # weak XOR encryption
                    key, hash_value = unpack('<HH', data[2:])
                    fprintf(logf,
                        'weak XOR: key=0x%04x hash=0x%04x\n',
                        key, hash_value)
                elif kind1 == 1:
                    kind2, = unpack('<H', data[4:6])
                    if kind2 == 1: # BIFF8 standard encryption
                        caption = "BIFF8 std"
                    elif kind2 == 2:
                        caption = "BIFF8 strong"
                    else:
                        caption = "** UNKNOWN ENCRYPTION METHOD **"
                    fprintf(logf, "%s\n", caption)
        raise XLRDError("Workbook is encrypted")

    def handle_name(self, data):
        blah = DEBUG or self.verbosity >= 2
        bv = self.biff_version
        if bv < 50:
            return
        self.derive_encoding()
        # print
        # hex_char_dump(data, 0, len(data), fout=self.logfile)
        (
        option_flags, kb_shortcut, name_len, fmla_len, extsht_index, sheet_index,
        menu_text_len, description_text_len, help_topic_text_len, status_bar_text_len,
        ) = unpack("<HBBHHH4B", data[0:14])
        nobj = Name()
        nobj.book = self ### CIRCULAR ###
        name_index = len(self.name_obj_list)
        nobj.name_index = name_index
        self.name_obj_list.append(nobj)
        nobj.option_flags = option_flags
        for attr, mask, nshift in (
            ('hidden', 1, 0),
            ('func', 2, 1),
            ('vbasic', 4, 2),
            ('macro', 8, 3),
            ('complex', 0x10, 4),
            ('builtin', 0x20, 5),
            ('funcgroup', 0xFC0, 6),
            ('binary', 0x1000, 12),
            ):
            setattr(nobj, attr, (option_flags & mask) >> nshift)

        macro_flag = " M"[nobj.macro]
        if bv < 80:
            internal_name, pos = unpack_string_update_pos(data, 14, self.encoding, known_len=name_len)
        else:
            internal_name, pos = unpack_unicode_update_pos(data, 14, known_len=name_len)
        nobj.extn_sheet_num = extsht_index
        nobj.excel_sheet_index = sheet_index
        nobj.scope = None # patched up in the names_epilogue() method
        if blah:
            fprintf(
                self.logfile,
                "NAME[%d]:%s oflags=%d, name_len=%d, fmla_len=%d, extsht_index=%d, sheet_index=%d, name=%r\n",
                name_index, macro_flag, option_flags, name_len,
                fmla_len, extsht_index, sheet_index, internal_name)
        name = internal_name
        if nobj.builtin:
            name = builtin_name_from_code.get(name, "??Unknown??")
            if blah: print("    builtin: %s" % name, file=self.logfile)
        nobj.name = name
        nobj.raw_formula = data[pos:]
        nobj.basic_formula_len = fmla_len
        nobj.evaluated = 0
        if blah:
            nobj.dump(
                self.logfile,
                header="--- handle_name: name[%d] ---" % name_index,
                footer="-------------------",
                )

    def names_epilogue(self):
        blah = self.verbosity >= 2
        f = self.logfile
        if blah:
            print("+++++ names_epilogue +++++", file=f)
            print("_all_sheets_map", REPR(self._all_sheets_map), file=f)
            print("_extnsht_name_from_num", REPR(self._extnsht_name_from_num), file=f)
            print("_sheet_num_from_name", REPR(self._sheet_num_from_name), file=f)
        num_names = len(self.name_obj_list)
        for namex in range(num_names):
            nobj = self.name_obj_list[namex]
            # Convert from excel_sheet_index to scope.
            # This is done here because in BIFF7 and earlier, the
            # BOUNDSHEET records (from which _all_sheets_map is derived)
            # come after the NAME records.
            if self.biff_version >= 80:
                sheet_index = nobj.excel_sheet_index
                if sheet_index == 0:
                    intl_sheet_index = -1 # global
                elif 1 <= sheet_index <= len(self._all_sheets_map):
                    intl_sheet_index = self._all_sheets_map[sheet_index-1]
                    if intl_sheet_index == -1: # maps to a macro or VBA sheet
                        intl_sheet_index = -2 # valid sheet reference but not useful
                else:
                    # huh?
                    intl_sheet_index = -3 # invalid
            elif 50 <= self.biff_version <= 70:
                sheet_index = nobj.extn_sheet_num
                if sheet_index == 0:
                    intl_sheet_index = -1 # global
                else:
                    sheet_name = self._extnsht_name_from_num[sheet_index]
                    intl_sheet_index = self._sheet_num_from_name.get(sheet_name, -2)
            nobj.scope = intl_sheet_index

        for namex in range(num_names):
            nobj = self.name_obj_list[namex]
            # Parse the formula ...
            if nobj.macro or nobj.binary: continue
            if nobj.evaluated: continue
            evaluate_name_formula(self, nobj, namex, blah=blah)

        if self.verbosity >= 2:
            print("---------- name object dump ----------", file=f)
            for namex in range(num_names):
                nobj = self.name_obj_list[namex]
                nobj.dump(f, header="--- name[%d] ---" % namex)
            print("--------------------------------------", file=f)
        #
        # Build some dicts for access to the name objects
        #
        name_and_scope_map = {} # (name.lower(), scope): Name_object
        name_map = {}           # name.lower() : list of Name_objects (sorted in scope order)
        for namex in range(num_names):
            nobj = self.name_obj_list[namex]
            name_lcase = nobj.name.lower()
            key = (name_lcase, nobj.scope)
            if key in name_and_scope_map and self.verbosity:
                fprintf(f, 'Duplicate entry %r in name_and_scope_map\n', key)
            name_and_scope_map[key] = nobj
            sort_data = (nobj.scope, namex, nobj)
            # namex (a temp unique ID) ensures the Name objects will not
            # be compared (fatal in py3)
            if name_lcase in name_map:
                name_map[name_lcase].append(sort_data)
            else:
                name_map[name_lcase] = [sort_data]
        for key in name_map.keys():
            alist = name_map[key]
            alist.sort()
            name_map[key] = [x[2] for x in alist]
        self.name_and_scope_map = name_and_scope_map
        self.name_map = name_map

    def handle_obj(self, data):
        # Not doing much handling at all.
        # Worrying about embedded (BOF ... EOF) substreams is done elsewhere.
        # DEBUG = 1
        obj_type, obj_id = unpack('<HI', data[4:10])
        # if DEBUG: print "---> handle_obj type=%d id=0x%08x" % (obj_type, obj_id)

    def handle_supbook(self, data):
        # aka EXTERNALBOOK in OOo docs
        self._supbook_types.append(None)
        blah = DEBUG or self.verbosity >= 2
        if blah:
            print("SUPBOOK:", file=self.logfile)
            hex_char_dump(data, 0, len(data), fout=self.logfile)
        num_sheets = unpack("<H", data[0:2])[0]
        if blah: print("num_sheets = %d" % num_sheets, file=self.logfile)
        sbn = self._supbook_count
        self._supbook_count += 1
        if data[2:4] == b"\x01\x04":
            self._supbook_types[-1] = SUPBOOK_INTERNAL
            self._supbook_locals_inx = self._supbook_count - 1
            if blah:
                print("SUPBOOK[%d]: internal 3D refs; %d sheets" % (sbn, num_sheets), file=self.logfile)
                print("    _all_sheets_map", self._all_sheets_map, file=self.logfile)
            return
        if data[0:4] == b"\x01\x00\x01\x3A":
            self._supbook_types[-1] = SUPBOOK_ADDIN
            self._supbook_addins_inx = self._supbook_count - 1
            if blah: print("SUPBOOK[%d]: add-in functions" % sbn, file=self.logfile)
            return
        url, pos = unpack_unicode_update_pos(data, 2, lenlen=2)
        if num_sheets == 0:
            self._supbook_types[-1] = SUPBOOK_DDEOLE
            if blah: fprintf(self.logfile, "SUPBOOK[%d]: DDE/OLE document = %r\n", sbn, url)
            return
        self._supbook_types[-1] = SUPBOOK_EXTERNAL
        if blah: fprintf(self.logfile, "SUPBOOK[%d]: url = %r\n", sbn, url)
        sheet_names = []
        for x in range(num_sheets):
            try:
                shname, pos = unpack_unicode_update_pos(data, pos, lenlen=2)
            except struct.error:
                # #### FIX ME ####
                # Should implement handling of CONTINUE record(s) ...
                if self.verbosity:
                    print((
                        "*** WARNING: unpack failure in sheet %d of %d in SUPBOOK record for file %r" 
                        % (x, num_sheets, url)
                        ), file=self.logfile)
                break
            sheet_names.append(shname)
            if blah: fprintf(self.logfile, "  sheetx=%d namelen=%d name=%r (next pos=%d)\n", x, len(shname), shname, pos)

    def handle_sheethdr(self, data):
        # This a BIFF 4W special.
        # The SHEETHDR record is followed by a (BOF ... EOF) substream containing
        # a worksheet.
        # DEBUG = 1
        self.derive_encoding()
        sheet_len = unpack('<i', data[:4])[0]
        sheet_name = unpack_string(data, 4, self.encoding, lenlen=1)
        sheetno = self._sheethdr_count
        assert sheet_name == self._sheet_names[sheetno]
        self._sheethdr_count += 1
        BOF_posn = self._position
        posn = BOF_posn - 4 - len(data)
        if DEBUG: fprintf(self.logfile, 'SHEETHDR %d at posn %d: len=%d name=%r\n', sheetno, posn, sheet_len, sheet_name)
        self.initialise_format_info()
        if DEBUG: print('SHEETHDR: xf epilogue flag is %d' % self._xf_epilogue_done, file=self.logfile)
        self._sheet_list.append(None) # get_sheet updates _sheet_list but needs a None beforehand
        self.get_sheet(sheetno, update_pos=False)
        if DEBUG: print('SHEETHDR: posn after get_sheet() =', self._position, file=self.logfile)
        self._position = BOF_posn + sheet_len

    def handle_sheetsoffset(self, data):
        # DEBUG = 0
        posn = unpack('<i', data)[0]
        if DEBUG: print('SHEETSOFFSET:', posn, file=self.logfile)
        self._sheetsoffset = posn

    def handle_sst(self, data):
        # DEBUG = 1
        if DEBUG:
            print("SST Processing", file=self.logfile)
            t0 = time.time()
        nbt = len(data)
        strlist = [data]
        uniquestrings = unpack('<i', data[4:8])[0]
        if DEBUG  or self.verbosity >= 2:
            fprintf(self.logfile, "SST: unique strings: %d\n", uniquestrings)
        while 1:
            code, nb, data = self.get_record_parts_conditional(XL_CONTINUE)
            if code is None:
                break
            nbt += nb
            if DEBUG >= 2:
                fprintf(self.logfile, "CONTINUE: adding %d bytes to SST -> %d\n", nb, nbt)
            strlist.append(data)
        self._sharedstrings, rt_runlist = unpack_SST_table(strlist, uniquestrings)
        if self.formatting_info:
            self._rich_text_runlist_map = rt_runlist        
        if DEBUG:
            t1 = time.time()
            print("SST processing took %.2f seconds" % (t1 - t0, ), file=self.logfile)

    def handle_writeaccess(self, data):
        DEBUG = 0
        if self.biff_version < 80:
            if not self.encoding:
                self.raw_user_name = True
                self.user_name = data
                return
            strg = unpack_string(data, 0, self.encoding, lenlen=1)
        else:
            strg = unpack_unicode(data, 0, lenlen=2)
        if DEBUG: fprintf(self.logfile, "WRITEACCESS: %d bytes; raw=%s %r\n", len(data), self.raw_user_name, strg)
        strg = strg.rstrip()
        self.user_name = strg

    def parse_globals(self):
        # DEBUG = 0
        # no need to position, just start reading (after the BOF)
        formatting.initialise_book(self)
        while 1:
            rc, length, data = self.get_record_parts()
            if DEBUG: print("parse_globals: record code is 0x%04x" % rc, file=self.logfile)
            if rc == XL_SST:
                self.handle_sst(data)
            elif rc == XL_FONT or rc == XL_FONT_B3B4:
                self.handle_font(data)
            elif rc == XL_FORMAT: # XL_FORMAT2 is BIFF <= 3.0, can't appear in globals
                self.handle_format(data)
            elif rc == XL_XF:
                self.handle_xf(data)
            elif rc ==  XL_BOUNDSHEET:
                self.handle_boundsheet(data)
            elif rc == XL_DATEMODE:
                self.handle_datemode(data)
            elif rc == XL_CODEPAGE:
                self.handle_codepage(data)
            elif rc == XL_COUNTRY:
                self.handle_country(data)
            elif rc == XL_EXTERNNAME:
                self.handle_externname(data)
            elif rc == XL_EXTERNSHEET:
                self.handle_externsheet(data)
            elif rc == XL_FILEPASS:
                self.handle_filepass(data)
            elif rc == XL_WRITEACCESS:
                self.handle_writeaccess(data)
            elif rc == XL_SHEETSOFFSET:
                self.handle_sheetsoffset(data)
            elif rc == XL_SHEETHDR:
                self.handle_sheethdr(data)
            elif rc == XL_SUPBOOK:
                self.handle_supbook(data)
            elif rc == XL_NAME:
                self.handle_name(data)
            elif rc == XL_PALETTE:
                self.handle_palette(data)
            elif rc == XL_STYLE:
                self.handle_style(data)
            elif rc & 0xff == 9 and self.verbosity:
                fprintf(self.logfile, "*** Unexpected BOF at posn %d: 0x%04x len=%d data=%r\n",
                    self._position - length - 4, rc, length, data)
            elif rc ==  XL_EOF:
                self.xf_epilogue()
                self.names_epilogue()
                self.palette_epilogue()
                if not self.encoding:
                    self.derive_encoding()
                if self.biff_version == 45:
                    # DEBUG = 0
                    if DEBUG: print("global EOF: position", self._position, file=self.logfile)
                    # if DEBUG:
                    #     pos = self._position - 4
                    #     print repr(self.mem[pos:pos+40])
                return
            else:
                # if DEBUG:
                #     print >> self.logfile, "parse_globals: ignoring record code 0x%04x" % rc
                pass

    def read(self, pos, length):
        data = self.mem[pos:pos+length]
        self._position = pos + len(data)
        return data

    def getbof(self, rqd_stream):
        # DEBUG = 1
        # if DEBUG: print >> self.logfile, "getbof(): position", self._position
        if DEBUG: print("reqd: 0x%04x" % rqd_stream, file=self.logfile)
        def bof_error(msg):
            raise XLRDError('Unsupported format, or corrupt file: ' + msg)
        savpos = self._position
        opcode = self.get2bytes()
        if opcode == MY_EOF:
            bof_error('Expected BOF record; met end of file')
        if opcode not in bofcodes:
            bof_error('Expected BOF record; found %r' % self.mem[savpos:savpos+8])
        length = self.get2bytes()
        if length == MY_EOF:
            bof_error('Incomplete BOF record[1]; met end of file')
        if not (4 <= length <= 20):
            bof_error(
                'Invalid length (%d) for BOF record type 0x%04x'
                % (length, opcode))
        padding = b'\0' * max(0, boflen[opcode] - length)
        data = self.read(self._position, length);
        if DEBUG: fprintf(self.logfile, "\ngetbof(): data=%r\n", data)
        if len(data) < length:
            bof_error('Incomplete BOF record[2]; met end of file')
        data += padding
        version1 = opcode >> 8
        version2, streamtype = unpack('<HH', data[0:4])
        if DEBUG:
            print("getbof(): op=0x%04x version2=0x%04x streamtype=0x%04x" \
                % (opcode, version2, streamtype), file=self.logfile)
        bof_offset = self._position - 4 - length
        if DEBUG:
            print("getbof(): BOF found at offset %d; savpos=%d" \
                % (bof_offset, savpos), file=self.logfile)
        version = build = year = 0
        if version1 == 0x08:
            build, year = unpack('<HH', data[4:8])
            if version2 == 0x0600:
                version = 80
            elif version2 == 0x0500:
                if year < 1994 or build in (2412, 3218, 3321):
                    version = 50
                else:
                    version = 70
            else:
                # dodgy one, created by a 3rd-party tool
                version = {
                    0x0000: 21,
                    0x0007: 21,
                    0x0200: 21,
                    0x0300: 30,
                    0x0400: 40,
                    }.get(version2, 0)
        elif version1 in (0x04, 0x02, 0x00):
            version = {0x04: 40, 0x02: 30, 0x00: 21}[version1]

        if version == 40 and streamtype == XL_WORKBOOK_GLOBALS_4W:
            version = 45 # i.e. 4W

        if DEBUG or self.verbosity >= 2:
            print("BOF: op=0x%04x vers=0x%04x stream=0x%04x buildid=%d buildyr=%d -> BIFF%d" \
                % (opcode, version2, streamtype, build, year, version), file=self.logfile)
        got_globals = streamtype == XL_WORKBOOK_GLOBALS or (
            version == 45 and streamtype == XL_WORKBOOK_GLOBALS_4W)
        if (rqd_stream == XL_WORKBOOK_GLOBALS and got_globals) or streamtype == rqd_stream:
            return version
        if version < 50 and streamtype == XL_WORKSHEET:
            return version
        if version >= 50 and streamtype == 0x0100:
            bof_error("Workspace file -- no spreadsheet data")
        bof_error(
            'BOF not workbook/worksheet: op=0x%04x vers=0x%04x strm=0x%04x build=%d year=%d -> BIFF%d' \
            % (opcode, version2, streamtype, build, year, version)
            )

# === helper functions

def expand_cell_address(inrow, incol):
    # Ref : OOo docs, "4.3.4 Cell Addresses in BIFF8"
    outrow = inrow
    if incol & 0x8000:
        if outrow >= 32768:
            outrow -= 65536
        relrow = 1
    else:
        relrow = 0
    outcol = incol & 0xFF
    if incol & 0x4000:
        if outcol >= 128:
            outcol -= 256
        relcol = 1
    else:
        relcol = 0
    return outrow, outcol, relrow, relcol

def colname(colx, _A2Z="ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
    assert colx >= 0
    name = UNICODE_LITERAL('')
    while 1:
        quot, rem = divmod(colx, 26)
        name = _A2Z[rem] + name
        if not quot:
            return name
        colx = quot - 1

def display_cell_address(rowx, colx, relrow, relcol):
    if relrow:
        rowpart = "(*%s%d)" % ("+-"[rowx < 0], abs(rowx))
    else:
        rowpart = "$%d" % (rowx+1,)
    if relcol:
        colpart = "(*%s%d)" % ("+-"[colx < 0], abs(colx))
    else:
        colpart = "$" + colname(colx)
    return colpart + rowpart

def unpack_SST_table(datatab, nstrings):
    "Return list of strings"
    datainx = 0
    ndatas = len(datatab)
    data = datatab[0]
    datalen = len(data)
    pos = 8
    strings = []
    strappend = strings.append
    richtext_runs = {}
    local_unpack = unpack
    local_min = min
    local_BYTES_ORD = BYTES_ORD
    latin_1 = "latin_1"
    for _unused_i in xrange(nstrings):
        nchars = local_unpack('<H', data[pos:pos+2])[0]
        pos += 2
        options = local_BYTES_ORD(data[pos])
        pos += 1
        rtcount = 0
        phosz = 0
        if options & 0x08: # richtext
            rtcount = local_unpack('<H', data[pos:pos+2])[0]
            pos += 2
        if options & 0x04: # phonetic
            phosz = local_unpack('<i', data[pos:pos+4])[0]
            pos += 4
        accstrg = UNICODE_LITERAL('')
        charsgot = 0
        while 1:
            charsneed = nchars - charsgot
            if options & 0x01:
                # Uncompressed UTF-16
                charsavail = local_min((datalen - pos) >> 1, charsneed)
                rawstrg = data[pos:pos+2*charsavail]
                # if DEBUG: print "SST U16: nchars=%d pos=%d rawstrg=%r" % (nchars, pos, rawstrg)
                try:
                    accstrg += unicode(rawstrg, "utf_16_le")
                except:
                    # print "SST U16: nchars=%d pos=%d rawstrg=%r" % (nchars, pos, rawstrg)
                    # Probable cause: dodgy data e.g. unfinished surrogate pair.
                    # E.g. file unicode2.xls in pyExcelerator's examples has cells containing
                    # unichr(i) for i in range(0x100000)
                    # so this will include 0xD800 etc
                    raise
                pos += 2*charsavail
            else:
                # Note: this is COMPRESSED (not ASCII!) encoding!!!
                charsavail = local_min(datalen - pos, charsneed)
                rawstrg = data[pos:pos+charsavail]
                # if DEBUG: print "SST CMPRSD: nchars=%d pos=%d rawstrg=%r" % (nchars, pos, rawstrg)
                accstrg += unicode(rawstrg, latin_1)
                pos += charsavail
            charsgot += charsavail
            if charsgot == nchars:
                break
            datainx += 1
            data = datatab[datainx]
            datalen = len(data)
            options = local_BYTES_ORD(data[0])
            pos = 1
        
        if rtcount:
            runs = []
            for runindex in xrange(rtcount):
                if pos == datalen:
                    pos = 0
                    datainx += 1
                    data = datatab[datainx]
                    datalen = len(data)
                runs.append(local_unpack("<HH", data[pos:pos+4]))
                pos += 4
            richtext_runs[len(strings)] = runs
                
        pos += phosz # size of the phonetic stuff to skip
        if pos >= datalen:
            # adjust to correct position in next record
            pos = pos - datalen
            datainx += 1
            if datainx < ndatas:
                data = datatab[datainx]
                datalen = len(data)
            else:
                assert _unused_i == nstrings - 1
        strappend(accstrg)
    return strings, richtext_runs

########NEW FILE########
__FILENAME__ = compdoc
# -*- coding: cp1252 -*-

##
# Implements the minimal functionality required
# to extract a "Workbook" or "Book" stream (as one big string)
# from an OLE2 Compound Document file.
# <p>Copyright � 2005-2012 Stephen John Machin, Lingfo Pty Ltd</p>
# <p>This module is part of the xlrd package, which is released under a BSD-style licence.</p>
##

# No part of the content of this file was derived from the works of David Giffin.

# 2008-11-04 SJM Avoid assertion error when -1 used instead of -2 for first_SID of empty SCSS [Frank Hoffsuemmer]
# 2007-09-08 SJM Warning message if sector sizes are extremely large.
# 2007-05-07 SJM Meaningful exception instead of IndexError if a SAT (sector allocation table) is corrupted.
# 2007-04-22 SJM Missing "<" in a struct.unpack call => can't open files on bigendian platforms.

from __future__ import print_function
import sys
from struct import unpack
from .timemachine import *
import array

##
# Magic cookie that should appear in the first 8 bytes of the file.
SIGNATURE = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"

EOCSID = -2
FREESID = -1
SATSID = -3
MSATSID = -4
EVILSID = -5

class CompDocError(Exception):
    pass

class DirNode(object):

    def __init__(self, DID, dent, DEBUG=0, logfile=sys.stdout):
        # dent is the 128-byte directory entry
        self.DID = DID
        self.logfile = logfile
        (cbufsize, self.etype, self.colour, self.left_DID, self.right_DID,
        self.root_DID) = \
            unpack('<HBBiii', dent[64:80])
        (self.first_SID, self.tot_size) = \
            unpack('<ii', dent[116:124])
        if cbufsize == 0:
            self.name = UNICODE_LITERAL('')
        else:
            self.name = unicode(dent[0:cbufsize-2], 'utf_16_le') # omit the trailing U+0000
        self.children = [] # filled in later
        self.parent = -1 # indicates orphan; fixed up later
        self.tsinfo = unpack('<IIII', dent[100:116])
        if DEBUG:
            self.dump(DEBUG)

    def dump(self, DEBUG=1):
        fprintf(
            self.logfile,
            "DID=%d name=%r etype=%d DIDs(left=%d right=%d root=%d parent=%d kids=%r) first_SID=%d tot_size=%d\n",
            self.DID, self.name, self.etype, self.left_DID,
            self.right_DID, self.root_DID, self.parent, self.children, self.first_SID, self.tot_size
            )
        if DEBUG == 2:
            # cre_lo, cre_hi, mod_lo, mod_hi = tsinfo
            print("timestamp info", self.tsinfo, file=self.logfile)

def _build_family_tree(dirlist, parent_DID, child_DID):
    if child_DID < 0: return
    _build_family_tree(dirlist, parent_DID, dirlist[child_DID].left_DID)
    dirlist[parent_DID].children.append(child_DID)
    dirlist[child_DID].parent = parent_DID
    _build_family_tree(dirlist, parent_DID, dirlist[child_DID].right_DID)
    if dirlist[child_DID].etype == 1: # storage
        _build_family_tree(dirlist, child_DID, dirlist[child_DID].root_DID)

##
# Compound document handler.
# @param mem The raw contents of the file, as a string, or as an mmap.mmap() object. The
# only operation it needs to support is slicing.

class CompDoc(object):

    def __init__(self, mem, logfile=sys.stdout, DEBUG=0):
        self.logfile = logfile
        self.DEBUG = DEBUG
        if mem[0:8] != SIGNATURE:
            raise CompDocError('Not an OLE2 compound document')
        if mem[28:30] != b'\xFE\xFF':
            raise CompDocError('Expected "little-endian" marker, found %r' % mem[28:30])
        revision, version = unpack('<HH', mem[24:28])
        if DEBUG:
            print("\nCompDoc format: version=0x%04x revision=0x%04x" % (version, revision), file=logfile)
        self.mem = mem
        ssz, sssz = unpack('<HH', mem[30:34])
        if ssz > 20: # allows for 2**20 bytes i.e. 1MB
            print("WARNING: sector size (2**%d) is preposterous; assuming 512 and continuing ..." \
                % ssz, file=logfile)
            ssz = 9
        if sssz > ssz:
            print("WARNING: short stream sector size (2**%d) is preposterous; assuming 64 and continuing ..." \
                % sssz, file=logfile)
            sssz = 6
        self.sec_size = sec_size = 1 << ssz
        self.short_sec_size = 1 << sssz
        if self.sec_size != 512 or self.short_sec_size != 64:
            print("@@@@ sec_size=%d short_sec_size=%d" % (self.sec_size, self.short_sec_size), file=logfile)
        (
            SAT_tot_secs, self.dir_first_sec_sid, _unused, self.min_size_std_stream,
            SSAT_first_sec_sid, SSAT_tot_secs,
            MSATX_first_sec_sid, MSATX_tot_secs,
        # ) = unpack('<ii4xiiiii', mem[44:76])
        ) = unpack('<iiiiiiii', mem[44:76])
        mem_data_len = len(mem) - 512
        mem_data_secs, left_over = divmod(mem_data_len, sec_size)
        if left_over:
            #### raise CompDocError("Not a whole number of sectors")
            mem_data_secs += 1
            print("WARNING *** file size (%d) not 512 + multiple of sector size (%d)" \
                % (len(mem), sec_size), file=logfile)
        self.mem_data_secs = mem_data_secs # use for checking later
        self.mem_data_len = mem_data_len
        seen = self.seen = array.array('B', [0]) * mem_data_secs

        if DEBUG:
            print('sec sizes', ssz, sssz, sec_size, self.short_sec_size, file=logfile)
            print("mem data: %d bytes == %d sectors" % (mem_data_len, mem_data_secs), file=logfile)
            print("SAT_tot_secs=%d, dir_first_sec_sid=%d, min_size_std_stream=%d" \
                % (SAT_tot_secs, self.dir_first_sec_sid, self.min_size_std_stream,), file=logfile)
            print("SSAT_first_sec_sid=%d, SSAT_tot_secs=%d" % (SSAT_first_sec_sid, SSAT_tot_secs,), file=logfile)
            print("MSATX_first_sec_sid=%d, MSATX_tot_secs=%d" % (MSATX_first_sec_sid, MSATX_tot_secs,), file=logfile)
        nent = sec_size // 4 # number of SID entries in a sector
        fmt = "<%di" % nent
        trunc_warned = 0
        #
        # === build the MSAT ===
        #
        MSAT = list(unpack('<109i', mem[76:512]))
        SAT_sectors_reqd = (mem_data_secs + nent - 1) // nent
        expected_MSATX_sectors = max(0, (SAT_sectors_reqd - 109 + nent - 2) // (nent - 1))
        actual_MSATX_sectors = 0
        if MSATX_tot_secs == 0 and MSATX_first_sec_sid in (EOCSID, FREESID, 0):
            # Strictly, if there is no MSAT extension, then MSATX_first_sec_sid
            # should be set to EOCSID ... FREESID and 0 have been met in the wild.
            pass # Presuming no extension
        else:
            sid = MSATX_first_sec_sid
            while sid not in (EOCSID, FREESID):
                # Above should be only EOCSID according to MS & OOo docs
                # but Excel doesn't complain about FREESID. Zero is a valid
                # sector number, not a sentinel.
                if DEBUG > 1:
                    print('MSATX: sid=%d (0x%08X)' % (sid, sid), file=logfile)
                if sid >= mem_data_secs:
                    msg = "MSAT extension: accessing sector %d but only %d in file" % (sid, mem_data_secs)
                    if DEBUG > 1:
                        print(msg, file=logfile)
                        break
                    raise CompDocError(msg)
                elif sid < 0:
                    raise CompDocError("MSAT extension: invalid sector id: %d" % sid)
                if seen[sid]:
                    raise CompDocError("MSAT corruption: seen[%d] == %d" % (sid, seen[sid]))
                seen[sid] = 1
                actual_MSATX_sectors += 1
                if DEBUG and actual_MSATX_sectors > expected_MSATX_sectors:
                    print("[1]===>>>", mem_data_secs, nent, SAT_sectors_reqd, expected_MSATX_sectors, actual_MSATX_sectors, file=logfile)
                offset = 512 + sec_size * sid
                MSAT.extend(unpack(fmt, mem[offset:offset+sec_size]))
                sid = MSAT.pop() # last sector id is sid of next sector in the chain
                
        if DEBUG and actual_MSATX_sectors != expected_MSATX_sectors:
            print("[2]===>>>", mem_data_secs, nent, SAT_sectors_reqd, expected_MSATX_sectors, actual_MSATX_sectors, file=logfile)
        if DEBUG:
            print("MSAT: len =", len(MSAT), file=logfile)
            dump_list(MSAT, 10, logfile)
        #
        # === build the SAT ===
        #
        self.SAT = []
        actual_SAT_sectors = 0
        dump_again = 0
        for msidx in xrange(len(MSAT)):
            msid = MSAT[msidx]
            if msid in (FREESID, EOCSID):
                # Specification: the MSAT array may be padded with trailing FREESID entries.
                # Toleration: a FREESID or EOCSID entry anywhere in the MSAT array will be ignored.
                continue
            if msid >= mem_data_secs:
                if not trunc_warned:
                    print("WARNING *** File is truncated, or OLE2 MSAT is corrupt!!", file=logfile)
                    print("INFO: Trying to access sector %d but only %d available" \
                        % (msid, mem_data_secs), file=logfile)
                    trunc_warned = 1
                MSAT[msidx] = EVILSID
                dump_again = 1
                continue
            elif msid < -2:
                raise CompDocError("MSAT: invalid sector id: %d" % msid)
            if seen[msid]:
                raise CompDocError("MSAT extension corruption: seen[%d] == %d" % (msid, seen[msid]))
            seen[msid] = 2
            actual_SAT_sectors += 1
            if DEBUG and actual_SAT_sectors > SAT_sectors_reqd:
                print("[3]===>>>", mem_data_secs, nent, SAT_sectors_reqd, expected_MSATX_sectors, actual_MSATX_sectors, actual_SAT_sectors, msid, file=logfile)
            offset = 512 + sec_size * msid
            self.SAT.extend(unpack(fmt, mem[offset:offset+sec_size]))

        if DEBUG:
            print("SAT: len =", len(self.SAT), file=logfile)
            dump_list(self.SAT, 10, logfile)
            # print >> logfile, "SAT ",
            # for i, s in enumerate(self.SAT):
                # print >> logfile, "entry: %4d offset: %6d, next entry: %4d" % (i, 512 + sec_size * i, s)
                # print >> logfile, "%d:%d " % (i, s),
            print(file=logfile)
        if DEBUG and dump_again:
            print("MSAT: len =", len(MSAT), file=logfile)
            dump_list(MSAT, 10, logfile)
            for satx in xrange(mem_data_secs, len(self.SAT)):
                self.SAT[satx] = EVILSID
            print("SAT: len =", len(self.SAT), file=logfile)
            dump_list(self.SAT, 10, logfile)
        #
        # === build the directory ===
        #
        dbytes = self._get_stream(
            self.mem, 512, self.SAT, self.sec_size, self.dir_first_sec_sid,
            name="directory", seen_id=3)
        dirlist = []
        did = -1
        for pos in xrange(0, len(dbytes), 128):
            did += 1
            dirlist.append(DirNode(did, dbytes[pos:pos+128], 0, logfile))
        self.dirlist = dirlist
        _build_family_tree(dirlist, 0, dirlist[0].root_DID) # and stand well back ...
        if DEBUG:
            for d in dirlist:
                d.dump(DEBUG)
        #
        # === get the SSCS ===
        #
        sscs_dir = self.dirlist[0]
        assert sscs_dir.etype == 5 # root entry
        if sscs_dir.first_SID < 0 or sscs_dir.tot_size == 0:
            # Problem reported by Frank Hoffsuemmer: some software was
            # writing -1 instead of -2 (EOCSID) for the first_SID
            # when the SCCS was empty. Not having EOCSID caused assertion
            # failure in _get_stream.
            # Solution: avoid calling _get_stream in any case when the
            # SCSS appears to be empty.
            self.SSCS = ""
        else:
            self.SSCS = self._get_stream(
                self.mem, 512, self.SAT, sec_size, sscs_dir.first_SID,
                sscs_dir.tot_size, name="SSCS", seen_id=4)
        # if DEBUG: print >> logfile, "SSCS", repr(self.SSCS)
        #
        # === build the SSAT ===
        #
        self.SSAT = []
        if SSAT_tot_secs > 0 and sscs_dir.tot_size == 0:
            print("WARNING *** OLE2 inconsistency: SSCS size is 0 but SSAT size is non-zero", file=logfile)
        if sscs_dir.tot_size > 0:
            sid = SSAT_first_sec_sid
            nsecs = SSAT_tot_secs
            while sid >= 0 and nsecs > 0:
                if seen[sid]:
                    raise CompDocError("SSAT corruption: seen[%d] == %d" % (sid, seen[sid]))
                seen[sid] = 5
                nsecs -= 1
                start_pos = 512 + sid * sec_size
                news = list(unpack(fmt, mem[start_pos:start_pos+sec_size]))
                self.SSAT.extend(news)
                sid = self.SAT[sid]
            if DEBUG: print("SSAT last sid %d; remaining sectors %d" % (sid, nsecs), file=logfile)
            assert nsecs == 0 and sid == EOCSID
        if DEBUG:
            print("SSAT", file=logfile)
            dump_list(self.SSAT, 10, logfile)
        if DEBUG:
            print("seen", file=logfile)
            dump_list(seen, 20, logfile)

    def _get_stream(self, mem, base, sat, sec_size, start_sid, size=None, name='', seen_id=None):
        # print >> self.logfile, "_get_stream", base, sec_size, start_sid, size
        sectors = []
        s = start_sid
        if size is None:
            # nothing to check against
            while s >= 0:
                if seen_id is not None:
                    if self.seen[s]:
                        raise CompDocError("%s corruption: seen[%d] == %d" % (name, s, self.seen[s]))
                    self.seen[s] = seen_id
                start_pos = base + s * sec_size
                sectors.append(mem[start_pos:start_pos+sec_size])
                try:
                    s = sat[s]
                except IndexError:
                    raise CompDocError(
                        "OLE2 stream %r: sector allocation table invalid entry (%d)" %
                        (name, s)
                        )
            assert s == EOCSID
        else:
            todo = size
            while s >= 0:
                if seen_id is not None:
                    if self.seen[s]:
                        raise CompDocError("%s corruption: seen[%d] == %d" % (name, s, self.seen[s]))
                    self.seen[s] = seen_id
                start_pos = base + s * sec_size
                grab = sec_size
                if grab > todo:
                    grab = todo
                todo -= grab
                sectors.append(mem[start_pos:start_pos+grab])
                try:
                    s = sat[s]
                except IndexError:
                    raise CompDocError(
                        "OLE2 stream %r: sector allocation table invalid entry (%d)" %
                        (name, s)
                        )
            assert s == EOCSID
            if todo != 0:
                fprintf(self.logfile, 
                    "WARNING *** OLE2 stream %r: expected size %d, actual size %d\n",
                    name, size, size - todo)

        return b''.join(sectors)

    def _dir_search(self, path, storage_DID=0):
        # Return matching DirNode instance, or None
        head = path[0]
        tail = path[1:]
        dl = self.dirlist
        for child in dl[storage_DID].children:
            if dl[child].name.lower() == head.lower():
                et = dl[child].etype
                if et == 2:
                    return dl[child]
                if et == 1:
                    if not tail:
                        raise CompDocError("Requested component is a 'storage'")
                    return self._dir_search(tail, child)
                dl[child].dump(1)
                raise CompDocError("Requested stream is not a 'user stream'")
        return None

    ##
    # Interrogate the compound document's directory; return the stream as a string if found, otherwise
    # return None.
    # @param qname Name of the desired stream e.g. u'Workbook'. Should be in Unicode or convertible thereto.

    def get_named_stream(self, qname):
        d = self._dir_search(qname.split("/"))
        if d is None:
            return None
        if d.tot_size >= self.min_size_std_stream:
            return self._get_stream(
                self.mem, 512, self.SAT, self.sec_size, d.first_SID,
                d.tot_size, name=qname, seen_id=d.DID+6)
        else:
            return self._get_stream(
                self.SSCS, 0, self.SSAT, self.short_sec_size, d.first_SID,
                d.tot_size, name=qname + " (from SSCS)", seen_id=None)

    ##
    # Interrogate the compound document's directory.
    # If the named stream is not found, (None, 0, 0) will be returned.
    # If the named stream is found and is contiguous within the original byte sequence ("mem")
    # used when the document was opened,
    # then (mem, offset_to_start_of_stream, length_of_stream) is returned.
    # Otherwise a new string is built from the fragments and (new_string, 0, length_of_stream) is returned.
    # @param qname Name of the desired stream e.g. u'Workbook'. Should be in Unicode or convertible thereto.

    def locate_named_stream(self, qname):
        d = self._dir_search(qname.split("/"))
        if d is None:
            return (None, 0, 0)
        if d.tot_size > self.mem_data_len:
            raise CompDocError("%r stream length (%d bytes) > file data size (%d bytes)"
                % (qname, d.tot_size, self.mem_data_len))
        if d.tot_size >= self.min_size_std_stream:
            result = self._locate_stream(
                self.mem, 512, self.SAT, self.sec_size, d.first_SID, 
                d.tot_size, qname, d.DID+6)
            if self.DEBUG:
                print("\nseen", file=self.logfile)
                dump_list(self.seen, 20, self.logfile)
            return result
        else:
            return (
                self._get_stream(
                    self.SSCS, 0, self.SSAT, self.short_sec_size, d.first_SID,
                    d.tot_size, qname + " (from SSCS)", None),
                0,
                d.tot_size
                )

    def _locate_stream(self, mem, base, sat, sec_size, start_sid, expected_stream_size, qname, seen_id):
        # print >> self.logfile, "_locate_stream", base, sec_size, start_sid, expected_stream_size
        s = start_sid
        if s < 0:
            raise CompDocError("_locate_stream: start_sid (%d) is -ve" % start_sid)
        p = -99 # dummy previous SID
        start_pos = -9999
        end_pos = -8888
        slices = []
        tot_found = 0
        found_limit = (expected_stream_size + sec_size - 1) // sec_size
        while s >= 0:
            if self.seen[s]:
                print("_locate_stream(%s): seen" % qname, file=self.logfile); dump_list(self.seen, 20, self.logfile)
                raise CompDocError("%s corruption: seen[%d] == %d" % (qname, s, self.seen[s]))
            self.seen[s] = seen_id
            tot_found += 1
            if tot_found > found_limit:
                raise CompDocError(
                    "%s: size exceeds expected %d bytes; corrupt?"
                    % (qname, found_limit * sec_size)
                    ) # Note: expected size rounded up to higher sector
            if s == p+1:
                # contiguous sectors
                end_pos += sec_size
            else:
                # start new slice
                if p >= 0:
                    # not first time
                    slices.append((start_pos, end_pos))
                start_pos = base + s * sec_size
                end_pos = start_pos + sec_size
            p = s
            s = sat[s]
        assert s == EOCSID
        assert tot_found == found_limit
        # print >> self.logfile, "_locate_stream(%s): seen" % qname; dump_list(self.seen, 20, self.logfile)
        if not slices:
            # The stream is contiguous ... just what we like!
            return (mem, start_pos, expected_stream_size)
        slices.append((start_pos, end_pos))
        # print >> self.logfile, "+++>>> %d fragments" % len(slices)
        return (b''.join([mem[start_pos:end_pos] for start_pos, end_pos in slices]), 0, expected_stream_size)

# ==========================================================================================
def x_dump_line(alist, stride, f, dpos, equal=0):
    print("%5d%s" % (dpos, " ="[equal]), end=' ', file=f)
    for value in alist[dpos:dpos + stride]:
        print(str(value), end=' ', file=f)
    print(file=f)

def dump_list(alist, stride, f=sys.stdout):
    def _dump_line(dpos, equal=0):
        print("%5d%s" % (dpos, " ="[equal]), end=' ', file=f)
        for value in alist[dpos:dpos + stride]:
            print(str(value), end=' ', file=f)
        print(file=f)
    pos = None
    oldpos = None
    for pos in xrange(0, len(alist), stride):
        if oldpos is None:
            _dump_line(pos)
            oldpos = pos
        elif alist[pos:pos+stride] != alist[oldpos:oldpos+stride]:
            if pos - oldpos > stride:
                _dump_line(pos - stride, equal=1)
            _dump_line(pos)
            oldpos = pos
    if oldpos is not None and pos is not None and pos != oldpos:
        _dump_line(pos, equal=1)

########NEW FILE########
__FILENAME__ = xlrdnameAPIdemo
# -*- coding: cp1252 -*-

##
# Module/script example of the xlrd API for extracting information
# about named references, named constants, etc.
#
# <p>Copyright � 2006 Stephen John Machin, Lingfo Pty Ltd</p>
# <p>This module is part of the xlrd package, which is released under a BSD-style licence.</p>
##
from __future__ import print_function

import xlrd
from xlrd.timemachine import REPR
import sys
import glob

def scope_as_string(book, scope):
    if 0 <= scope < book.nsheets:
        return "sheet #%d (%r)" % (scope, REPR(book.sheet_names()[scope]))
    if scope == -1:
        return "Global"
    if scope == -2:
        return "Macro/VBA"
    return "Unknown scope value (%r)" % REPR(scope)

def do_scope_query(book, scope_strg, show_contents=0, f=sys.stdout):
    try:
        qscope = int(scope_strg)
    except ValueError:
        if scope_strg == "*":
            qscope = None # means "all'
        else:
            # so assume it's a sheet name ...
            qscope = book.sheet_names().index(scope_strg)
            print("%r => %d" % (scope_strg, qscope), file=f)
    for nobj in book.name_obj_list:
        if qscope is None or nobj.scope == qscope:
            show_name_object(book, nobj, show_contents, f)

def show_name_details(book, name, show_contents=0, f=sys.stdout):
    """
    book -- Book object obtained from xlrd.open_workbook().
    name -- The name that's being investigated.
    show_contents -- 0: Don't; 1: Non-empty cells only; 2: All cells
    f -- Open output file handle.
    """
    name_lcase = name.lower() # Excel names are case-insensitive.
    nobj_list = book.name_map.get(name_lcase)
    if not nobj_list:
        print("%r: unknown name" % name, file=f)
        return
    for nobj in nobj_list:
        show_name_object(book, nobj, show_contents, f)

def show_name_details_in_scope(
    book, name, scope_strg, show_contents=0, f=sys.stdout,
    ):
    try:
        scope = int(scope_strg)
    except ValueError:
        # so assume it's a sheet name ...
        scope = book.sheet_names().index(scope_strg)
        print("%r => %d" % (scope_strg, scope), file=f)
    name_lcase = name.lower() # Excel names are case-insensitive.
    while 1:
        nobj = book.name_and_scope_map.get((name_lcase, scope))
        if nobj:
            break
        print("Name %s not found in scope %d" % (REPR(name), scope), file=f)
        if scope == -1:
            return
        scope = -1 # Try again with global scope
    print("Name %s found in scope %d" % (REPR(name), scope), file=f)
    show_name_object(book, nobj, show_contents, f)

def showable_cell_value(celltype, cellvalue, datemode):
    if celltype == xlrd.XL_CELL_DATE:
        try:
            showval = xlrd.xldate_as_tuple(cellvalue, datemode)
        except xlrd.XLDateError as e:
            showval = "%s:%s" % (type(e).__name__, e)
    elif celltype == xlrd.XL_CELL_ERROR:
        showval = xlrd.error_text_from_code.get(
            cellvalue, '<Unknown error code 0x%02x>' % cellvalue)
    else:
        showval = cellvalue
    return showval

def show_name_object(book, nobj, show_contents=0, f=sys.stdout):
    print("\nName: %s, scope: %s (%s)" \
        % (REPR(nobj.name), REPR(nobj.scope), scope_as_string(book, nobj.scope)), file=f)
    res = nobj.result
    print("Formula eval result: %s" % REPR(res), file=f)
    if res is None:
        return
    # result should be an instance of the Operand class
    kind = res.kind
    value = res.value
    if kind >= 0:
        # A scalar, or unknown ... you've seen all there is to see.
        pass
    elif kind == xlrd.oREL:
        # A list of Ref3D objects representing *relative* ranges
        for i in range(len(value)):
            ref3d = value[i]
            print("Range %d: %s ==> %s"% (i, REPR(ref3d.coords), REPR(xlrd.rangename3drel(book, ref3d))), file=f)
    elif kind == xlrd.oREF:
        # A list of Ref3D objects
        for i in range(len(value)):
            ref3d = value[i]
            print("Range %d: %s ==> %s"% (i, REPR(ref3d.coords), REPR(xlrd.rangename3d(book, ref3d))), file=f)
            if not show_contents:
                continue
            datemode = book.datemode
            for shx in range(ref3d.shtxlo, ref3d.shtxhi):
                sh = book.sheet_by_index(shx)
                print("   Sheet #%d (%s)" % (shx, sh.name), file=f)
                rowlim = min(ref3d.rowxhi, sh.nrows)
                collim = min(ref3d.colxhi, sh.ncols)
                for rowx in range(ref3d.rowxlo, rowlim):
                    for colx in range(ref3d.colxlo, collim):
                        cty = sh.cell_type(rowx, colx)
                        if cty == xlrd.XL_CELL_EMPTY and show_contents == 1:
                            continue
                        cval = sh.cell_value(rowx, colx)
                        sval = showable_cell_value(cty, cval, datemode)
                        print("      (%3d,%3d) %-5s: %s"
                            % (rowx, colx, xlrd.cellname(rowx, colx), REPR(sval)), file=f)

if __name__ == "__main__":
    def usage():
        text = """
usage: xlrdnameAIPdemo.py glob_pattern name scope show_contents

where:
    "glob_pattern" designates a set of files
    "name" is a name or '*' (all names)
    "scope" is -1 (global) or a sheet number
        or a sheet name or * (all scopes)
    "show_contents" is one of 0 (no show),
       1 (only non-empty cells), or 2 (all cells)

Examples (script name and glob_pattern arg omitted for brevity)
    [Searching through book.name_obj_list]
    * * 0 lists all names
    * * 1 lists all names, showing referenced non-empty cells
    * 1 0 lists all names local to the 2nd sheet
    * Northern 0 lists all names local to the 'Northern' sheet
    * -1 0 lists all names with global scope
    [Initial direct access through book.name_map]
    Sales * 0 lists all occurrences of "Sales" in any scope
    [Direct access through book.name_and_scope_map]
    Revenue -1 0 checks if "Revenue" exists in global scope

"""
        sys.stdout.write(text)
    
    if len(sys.argv) != 5:
        usage()
        sys.exit(0)
    arg_pattern = sys.argv[1] # glob pattern e.g. "foo*.xls"
    arg_name = sys.argv[2]    # see below
    arg_scope = sys.argv[3]   # see below
    arg_show_contents = int(sys.argv[4]) # 0: no show, 1: only non-empty cells,
                                         # 2: all cells
    for fname in glob.glob(arg_pattern):
        book = xlrd.open_workbook(fname)
        if arg_name == "*":
            # Examine book.name_obj_list to find all names
            # in a given scope ("*" => all scopes)
            do_scope_query(book, arg_scope, arg_show_contents)
        elif arg_scope == "*":
            # Using book.name_map to find all usage of a name.
            show_name_details(book, arg_name, arg_show_contents)
        else:
            # Using book.name_and_scope_map to find which if any instances
            # of a name are visible in the given scope, which can be supplied
            # as -1 (global) or a sheet number or a sheet name.
            show_name_details_in_scope(book, arg_name, arg_scope, arg_show_contents)

########NEW FILE########
__FILENAME__ = formatting
# -*- coding: cp1252 -*-

##
# Module for formatting information.
#
# <p>Copyright � 2005-2012 Stephen John Machin, Lingfo Pty Ltd</p>
# <p>This module is part of the xlrd package, which is released under
# a BSD-style licence.</p>
##

# No part of the content of this file was derived from the works of David Giffin.

from __future__ import print_function

DEBUG = 0
import re
from struct import unpack
from .timemachine import *
from .biffh import BaseObject, unpack_unicode, unpack_string, \
    upkbits, upkbitsL, fprintf, \
    FUN, FDT, FNU, FGE, FTX, XL_CELL_NUMBER, XL_CELL_DATE, \
    XL_FORMAT, XL_FORMAT2, \
    XLRDError

_cellty_from_fmtty = {
    FNU: XL_CELL_NUMBER,
    FUN: XL_CELL_NUMBER,
    FGE: XL_CELL_NUMBER,
    FDT: XL_CELL_DATE,
    FTX: XL_CELL_NUMBER, # Yes, a number can be formatted as text.
    }    
    
excel_default_palette_b5 = (
    (  0,   0,   0), (255, 255, 255), (255,   0,   0), (  0, 255,   0),
    (  0,   0, 255), (255, 255,   0), (255,   0, 255), (  0, 255, 255),
    (128,   0,   0), (  0, 128,   0), (  0,   0, 128), (128, 128,   0),
    (128,   0, 128), (  0, 128, 128), (192, 192, 192), (128, 128, 128),
    (153, 153, 255), (153,  51, 102), (255, 255, 204), (204, 255, 255),
    (102,   0, 102), (255, 128, 128), (  0, 102, 204), (204, 204, 255),
    (  0,   0, 128), (255,   0, 255), (255, 255,   0), (  0, 255, 255),
    (128,   0, 128), (128,   0,   0), (  0, 128, 128), (  0,   0, 255),
    (  0, 204, 255), (204, 255, 255), (204, 255, 204), (255, 255, 153),
    (153, 204, 255), (255, 153, 204), (204, 153, 255), (227, 227, 227),
    ( 51, 102, 255), ( 51, 204, 204), (153, 204,   0), (255, 204,   0),
    (255, 153,   0), (255, 102,   0), (102, 102, 153), (150, 150, 150),
    (  0,  51, 102), ( 51, 153, 102), (  0,  51,   0), ( 51,  51,   0),
    (153,  51,   0), (153,  51, 102), ( 51,  51, 153), ( 51,  51,  51),
    )

excel_default_palette_b2 = excel_default_palette_b5[:16]

# Following table borrowed from Gnumeric 1.4 source.
# Checked against OOo docs and MS docs.
excel_default_palette_b8 = ( # (red, green, blue)
    (  0,  0,  0), (255,255,255), (255,  0,  0), (  0,255,  0), # 0
    (  0,  0,255), (255,255,  0), (255,  0,255), (  0,255,255), # 4
    (128,  0,  0), (  0,128,  0), (  0,  0,128), (128,128,  0), # 8
    (128,  0,128), (  0,128,128), (192,192,192), (128,128,128), # 12
    (153,153,255), (153, 51,102), (255,255,204), (204,255,255), # 16
    (102,  0,102), (255,128,128), (  0,102,204), (204,204,255), # 20
    (  0,  0,128), (255,  0,255), (255,255,  0), (  0,255,255), # 24
    (128,  0,128), (128,  0,  0), (  0,128,128), (  0,  0,255), # 28
    (  0,204,255), (204,255,255), (204,255,204), (255,255,153), # 32
    (153,204,255), (255,153,204), (204,153,255), (255,204,153), # 36
    ( 51,102,255), ( 51,204,204), (153,204,  0), (255,204,  0), # 40
    (255,153,  0), (255,102,  0), (102,102,153), (150,150,150), # 44
    (  0, 51,102), ( 51,153,102), (  0, 51,  0), ( 51, 51,  0), # 48
    (153, 51,  0), (153, 51,102), ( 51, 51,153), ( 51, 51, 51), # 52
    )

default_palette = {
    80: excel_default_palette_b8,
    70: excel_default_palette_b5,
    50: excel_default_palette_b5,
    45: excel_default_palette_b2,
    40: excel_default_palette_b2,
    30: excel_default_palette_b2,
    21: excel_default_palette_b2,
    20: excel_default_palette_b2,
    }

"""
00H = Normal
01H = RowLevel_lv (see next field)
02H = ColLevel_lv (see next field)
03H = Comma
04H = Currency
05H = Percent
06H = Comma [0] (BIFF4-BIFF8)
07H = Currency [0] (BIFF4-BIFF8)
08H = Hyperlink (BIFF8)
09H = Followed Hyperlink (BIFF8)
"""
built_in_style_names = [
    "Normal",
    "RowLevel_",
    "ColLevel_",
    "Comma",
    "Currency",
    "Percent",
    "Comma [0]",
    "Currency [0]",
    "Hyperlink",
    "Followed Hyperlink",
    ]

def initialise_colour_map(book):
    book.colour_map = {}
    book.colour_indexes_used = {}
    if not book.formatting_info:
        return
    # Add the 8 invariant colours
    for i in xrange(8):
        book.colour_map[i] = excel_default_palette_b8[i]
    # Add the default palette depending on the version
    dpal = default_palette[book.biff_version]
    ndpal = len(dpal)
    for i in xrange(ndpal):
        book.colour_map[i+8] = dpal[i]
    # Add the specials -- None means the RGB value is not known
    # System window text colour for border lines
    book.colour_map[ndpal+8] = None
    # System window background colour for pattern background
    book.colour_map[ndpal+8+1] = None #
    for ci in (
        0x51, # System ToolTip text colour (used in note objects)
        0x7FFF, # 32767, system window text colour for fonts
        ):
        book.colour_map[ci] = None

def nearest_colour_index(colour_map, rgb, debug=0):
    # General purpose function. Uses Euclidean distance.
    # So far used only for pre-BIFF8 WINDOW2 record.
    # Doesn't have to be fast.
    # Doesn't have to be fancy.
    best_metric = 3 * 256 * 256
    best_colourx = 0
    for colourx, cand_rgb in colour_map.items():
        if cand_rgb is None:
            continue
        metric = 0
        for v1, v2 in zip(rgb, cand_rgb):
            metric += (v1 - v2) * (v1 - v2)
        if metric < best_metric:
            best_metric = metric
            best_colourx = colourx
            if metric == 0:
                break
    if 0 and debug:
        print("nearest_colour_index for %r is %r -> %r; best_metric is %d" \
            % (rgb, best_colourx, colour_map[best_colourx], best_metric))
    return best_colourx

##
# This mixin class exists solely so that Format, Font, and XF.... objects
# can be compared by value of their attributes.
class EqNeAttrs(object):

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return self.__dict__ != other.__dict__

##
# An Excel "font" contains the details of not only what is normally
# considered a font, but also several other display attributes.
# Items correspond to those in the Excel UI's Format/Cells/Font tab.
# <br /> -- New in version 0.6.1
class Font(BaseObject, EqNeAttrs):
    ##
    # 1 = Characters are bold. Redundant; see "weight" attribute.
    bold = 0
    ##
    # Values: 0 = ANSI Latin, 1 = System default, 2 = Symbol,
    # 77 = Apple Roman,
    # 128 = ANSI Japanese Shift-JIS,
    # 129 = ANSI Korean (Hangul),
    # 130 = ANSI Korean (Johab),
    # 134 = ANSI Chinese Simplified GBK,
    # 136 = ANSI Chinese Traditional BIG5,
    # 161 = ANSI Greek,
    # 162 = ANSI Turkish,
    # 163 = ANSI Vietnamese,
    # 177 = ANSI Hebrew,
    # 178 = ANSI Arabic,
    # 186 = ANSI Baltic,
    # 204 = ANSI Cyrillic,
    # 222 = ANSI Thai,
    # 238 = ANSI Latin II (Central European),
    # 255 = OEM Latin I
    character_set = 0
    ##
    # An explanation of "colour index" is given in the Formatting
    # section at the start of this document.
    colour_index = 0
    ##
    # 1 = Superscript, 2 = Subscript.
    escapement = 0
    ##
    # 0 = None (unknown or don't care)<br />
    # 1 = Roman (variable width, serifed)<br />
    # 2 = Swiss (variable width, sans-serifed)<br />
    # 3 = Modern (fixed width, serifed or sans-serifed)<br />
    # 4 = Script (cursive)<br />
    # 5 = Decorative (specialised, for example Old English, Fraktur)
    family = 0
    ##
    # The 0-based index used to refer to this Font() instance.
    # Note that index 4 is never used; xlrd supplies a dummy place-holder.
    font_index = 0
    ##
    # Height of the font (in twips). A twip = 1/20 of a point.
    height = 0
    ##
    # 1 = Characters are italic.
    italic = 0
    ##
    # The name of the font. Example: u"Arial"
    name = UNICODE_LITERAL("")
    ##
    # 1 = Characters are struck out.
    struck_out = 0
    ##
    # 0 = None<br />
    # 1 = Single;  0x21 (33) = Single accounting<br />
    # 2 = Double;  0x22 (34) = Double accounting
    underline_type = 0
    ##
    # 1 = Characters are underlined. Redundant; see "underline_type" attribute.
    underlined = 0
    ##
    # Font weight (100-1000). Standard values are 400 for normal text
    # and 700 for bold text.
    weight = 400
    ##
    # 1 = Font is outline style (Macintosh only)
    outline = 0
    ##
    # 1 = Font is shadow style (Macintosh only)
    shadow = 0

    # No methods ...

def handle_efont(book, data): # BIFF2 only
    if not book.formatting_info:
        return
    book.font_list[-1].colour_index = unpack('<H', data)[0]

def handle_font(book, data):
    if not book.formatting_info:
        return
    if not book.encoding:
        book.derive_encoding()
    blah = DEBUG or book.verbosity >= 2
    bv = book.biff_version
    k = len(book.font_list)
    if k == 4:
        f = Font()
        f.name = UNICODE_LITERAL('Dummy Font')
        f.font_index = k
        book.font_list.append(f)
        k += 1
    f = Font()
    f.font_index = k
    book.font_list.append(f)
    if bv >= 50:
        (
            f.height, option_flags, f.colour_index, f.weight,
            f.escapement, f.underline_type, f.family,
            f.character_set,
        ) = unpack('<HHHHHBBB', data[0:13])
        f.bold = option_flags & 1
        f.italic = (option_flags & 2) >> 1
        f.underlined = (option_flags & 4) >> 2
        f.struck_out = (option_flags & 8) >> 3
        f.outline = (option_flags & 16) >> 4
        f.shadow = (option_flags & 32) >> 5
        if bv >= 80:
            f.name = unpack_unicode(data, 14, lenlen=1)
        else:
            f.name = unpack_string(data, 14, book.encoding, lenlen=1)
    elif bv >= 30:
        f.height, option_flags, f.colour_index = unpack('<HHH', data[0:6])
        f.bold = option_flags & 1
        f.italic = (option_flags & 2) >> 1
        f.underlined = (option_flags & 4) >> 2
        f.struck_out = (option_flags & 8) >> 3
        f.outline = (option_flags & 16) >> 4
        f.shadow = (option_flags & 32) >> 5
        f.name = unpack_string(data, 6, book.encoding, lenlen=1)
        # Now cook up the remaining attributes ...
        f.weight = [400, 700][f.bold]
        f.escapement = 0 # None
        f.underline_type = f.underlined # None or Single
        f.family = 0 # Unknown / don't care
        f.character_set = 1 # System default (0 means "ANSI Latin")
    else: # BIFF2
        f.height, option_flags = unpack('<HH', data[0:4])
        f.colour_index = 0x7FFF # "system window text colour"
        f.bold = option_flags & 1
        f.italic = (option_flags & 2) >> 1
        f.underlined = (option_flags & 4) >> 2
        f.struck_out = (option_flags & 8) >> 3
        f.outline = 0
        f.shadow = 0
        f.name = unpack_string(data, 4, book.encoding, lenlen=1)
        # Now cook up the remaining attributes ...
        f.weight = [400, 700][f.bold]
        f.escapement = 0 # None
        f.underline_type = f.underlined # None or Single
        f.family = 0 # Unknown / don't care
        f.character_set = 1 # System default (0 means "ANSI Latin")
    if blah:
        f.dump(
            book.logfile,
            header="--- handle_font: font[%d] ---" % f.font_index,
            footer="-------------------",
            )

# === "Number formats" ===

##
# "Number format" information from a FORMAT record.
# <br /> -- New in version 0.6.1
class Format(BaseObject, EqNeAttrs):
    ##
    # The key into Book.format_map
    format_key = 0
    ##
    # A classification that has been inferred from the format string.
    # Currently, this is used only to distinguish between numbers and dates.
    # <br />Values:
    # <br />FUN = 0 # unknown
    # <br />FDT = 1 # date
    # <br />FNU = 2 # number
    # <br />FGE = 3 # general
    # <br />FTX = 4 # text
    type = FUN
    ##
    # The format string
    format_str = UNICODE_LITERAL('')

    def __init__(self, format_key, ty, format_str):
        self.format_key = format_key
        self.type = ty
        self.format_str = format_str

std_format_strings = {
    # "std" == "standard for US English locale"
    # #### TODO ... a lot of work to tailor these to the user's locale.
    # See e.g. gnumeric-1.x.y/src/formats.c
    0x00: "General",
    0x01: "0",
    0x02: "0.00",
    0x03: "#,##0",
    0x04: "#,##0.00",
    0x05: "$#,##0_);($#,##0)",
    0x06: "$#,##0_);[Red]($#,##0)",
    0x07: "$#,##0.00_);($#,##0.00)",
    0x08: "$#,##0.00_);[Red]($#,##0.00)",
    0x09: "0%",
    0x0a: "0.00%",
    0x0b: "0.00E+00",
    0x0c: "# ?/?",
    0x0d: "# ??/??",
    0x0e: "m/d/yy",
    0x0f: "d-mmm-yy",
    0x10: "d-mmm",
    0x11: "mmm-yy",
    0x12: "h:mm AM/PM",
    0x13: "h:mm:ss AM/PM",
    0x14: "h:mm",
    0x15: "h:mm:ss",
    0x16: "m/d/yy h:mm",
    0x25: "#,##0_);(#,##0)",
    0x26: "#,##0_);[Red](#,##0)",
    0x27: "#,##0.00_);(#,##0.00)",
    0x28: "#,##0.00_);[Red](#,##0.00)",
    0x29: "_(* #,##0_);_(* (#,##0);_(* \"-\"_);_(@_)",
    0x2a: "_($* #,##0_);_($* (#,##0);_($* \"-\"_);_(@_)",
    0x2b: "_(* #,##0.00_);_(* (#,##0.00);_(* \"-\"??_);_(@_)",
    0x2c: "_($* #,##0.00_);_($* (#,##0.00);_($* \"-\"??_);_(@_)",
    0x2d: "mm:ss",
    0x2e: "[h]:mm:ss",
    0x2f: "mm:ss.0",
    0x30: "##0.0E+0",
    0x31: "@",
    }

fmt_code_ranges = [ # both-inclusive ranges of "standard" format codes
    # Source: the openoffice.org doc't
    # and the OOXML spec Part 4, section 3.8.30
    ( 0,  0, FGE),
    ( 1, 13, FNU),
    (14, 22, FDT),
    (27, 36, FDT), # CJK date formats
    (37, 44, FNU),
    (45, 47, FDT),
    (48, 48, FNU),
    (49, 49, FTX),
    # Gnumeric assumes (or assumed) that built-in formats finish at 49, not at 163
    (50, 58, FDT), # CJK date formats
    (59, 62, FNU), # Thai number (currency?) formats
    (67, 70, FNU), # Thai number (currency?) formats
    (71, 81, FDT), # Thai date formats
    ]

std_format_code_types = {}
for lo, hi, ty in fmt_code_ranges:
    for x in xrange(lo, hi+1):
        std_format_code_types[x] = ty
del lo, hi, ty, x

date_chars = UNICODE_LITERAL('ymdhs') # year, month/minute, day, hour, second
date_char_dict = {}
for _c in date_chars + date_chars.upper():
    date_char_dict[_c] = 5
del _c, date_chars

skip_char_dict = {}
for _c in UNICODE_LITERAL('$-+/(): '):
    skip_char_dict[_c] = 1

num_char_dict = {
    UNICODE_LITERAL('0'): 5,
    UNICODE_LITERAL('#'): 5,
    UNICODE_LITERAL('?'): 5,
    }

non_date_formats = {
    UNICODE_LITERAL('0.00E+00'):1,
    UNICODE_LITERAL('##0.0E+0'):1,
    UNICODE_LITERAL('General') :1,
    UNICODE_LITERAL('GENERAL') :1, # OOo Calc 1.1.4 does this.
    UNICODE_LITERAL('general') :1,  # pyExcelerator 0.6.3 does this.
    UNICODE_LITERAL('@')       :1,
    }

fmt_bracketed_sub = re.compile(r'\[[^]]*\]').sub

# Boolean format strings (actual cases)
# u'"Yes";"Yes";"No"'
# u'"True";"True";"False"'
# u'"On";"On";"Off"'

def is_date_format_string(book, fmt):
    # Heuristics:
    # Ignore "text" and [stuff in square brackets (aarrgghh -- see below)].
    # Handle backslashed-escaped chars properly.
    # E.g. hh\hmm\mss\s should produce a display like 23h59m59s
    # Date formats have one or more of ymdhs (caseless) in them.
    # Numeric formats have # and 0.
    # N.B. u'General"."' hence get rid of "text" first.
    # TODO: Find where formats are interpreted in Gnumeric
    # TODO: u'[h]\\ \\h\\o\\u\\r\\s' ([h] means don't care about hours > 23)
    state = 0
    s = ''
    
    for c in fmt:
        if state == 0:
            if c == UNICODE_LITERAL('"'):
                state = 1
            elif c in UNICODE_LITERAL(r"\_*"):
                state = 2
            elif c in skip_char_dict:
                pass
            else:
                s += c
        elif state == 1:
            if c == UNICODE_LITERAL('"'):
                state = 0
        elif state == 2:
            # Ignore char after backslash, underscore or asterisk
            state = 0
        assert 0 <= state <= 2
    if book.verbosity >= 4:
        print("is_date_format_string: reduced format is %s" % REPR(s), file=book.logfile)
    s = fmt_bracketed_sub('', s)
    if s in non_date_formats:
        return False
    state = 0
    separator = ";"
    got_sep = 0
    date_count = num_count = 0
    for c in s:
        if c in date_char_dict:
            date_count += date_char_dict[c]
        elif c in num_char_dict:
            num_count += num_char_dict[c]
        elif c == separator:
            got_sep = 1
    # print num_count, date_count, repr(fmt)
    if date_count and not num_count:
        return True
    if num_count and not date_count:
        return False
    if date_count:
        if book.verbosity:
            fprintf(book.logfile,
                'WARNING *** is_date_format: ambiguous d=%d n=%d fmt=%r\n',
                date_count, num_count, fmt)
    elif not got_sep:
        if book.verbosity:
            fprintf(book.logfile,
                "WARNING *** format %r produces constant result\n",
                fmt)
    return date_count > num_count

def handle_format(self, data, rectype=XL_FORMAT):
    DEBUG = 0
    bv = self.biff_version
    if rectype == XL_FORMAT2:
        bv = min(bv, 30)
    if not self.encoding:
        self.derive_encoding()
    strpos = 2
    if bv >= 50:
        fmtkey = unpack('<H', data[0:2])[0]
    else:
        fmtkey = self.actualfmtcount
        if bv <= 30:
            strpos = 0
    self.actualfmtcount += 1
    if bv >= 80:
        unistrg = unpack_unicode(data, 2)
    else:
        unistrg = unpack_string(data, strpos, self.encoding, lenlen=1)
    blah = DEBUG or self.verbosity >= 3
    if blah:
        fprintf(self.logfile,
            "FORMAT: count=%d fmtkey=0x%04x (%d) s=%r\n",
            self.actualfmtcount, fmtkey, fmtkey, unistrg)
    is_date_s = self.is_date_format_string(unistrg)
    ty = [FGE, FDT][is_date_s]
    if not(fmtkey > 163 or bv < 50):
        # user_defined if fmtkey > 163
        # N.B. Gnumeric incorrectly starts these at 50 instead of 164 :-(
        # if earlier than BIFF 5, standard info is useless
        std_ty = std_format_code_types.get(fmtkey, FUN)
        # print "std ty", std_ty
        is_date_c = std_ty == FDT
        if self.verbosity and 0 < fmtkey < 50 and (is_date_c ^ is_date_s):
            DEBUG = 2
            fprintf(self.logfile,
                "WARNING *** Conflict between "
                "std format key %d and its format string %r\n",
                fmtkey, unistrg)
    if DEBUG == 2:
        fprintf(self.logfile,
            "ty: %d; is_date_c: %r; is_date_s: %r; fmt_strg: %r",
            ty, is_date_c, is_date_s, unistrg)
    fmtobj = Format(fmtkey, ty, unistrg)
    if blah:
        fmtobj.dump(self.logfile,
            header="--- handle_format [%d] ---" % (self.actualfmtcount-1, ))
    self.format_map[fmtkey] = fmtobj
    self.format_list.append(fmtobj)

# =============================================================================

def handle_palette(book, data):
    if not book.formatting_info:
        return
    blah = DEBUG or book.verbosity >= 2
    n_colours, = unpack('<H', data[:2])
    expected_n_colours = (16, 56)[book.biff_version >= 50]
    if ((DEBUG or book.verbosity >= 1)
    and n_colours != expected_n_colours):
        fprintf(book.logfile,
            "NOTE *** Expected %d colours in PALETTE record, found %d\n",
            expected_n_colours, n_colours)
    elif blah:
        fprintf(book.logfile,
            "PALETTE record with %d colours\n", n_colours)
    fmt = '<xx%di' % n_colours # use i to avoid long integers
    expected_size = 4 * n_colours + 2
    actual_size = len(data)
    tolerance = 4
    if not expected_size <= actual_size <= expected_size + tolerance:
        raise XLRDError('PALETTE record: expected size %d, actual size %d' % (expected_size, actual_size))
    colours = unpack(fmt, data[:expected_size])
    assert book.palette_record == [] # There should be only 1 PALETTE record
    # a colour will be 0xbbggrr
    # IOW, red is at the little end
    for i in xrange(n_colours):
        c = colours[i]
        red   =  c        & 0xff
        green = (c >>  8) & 0xff
        blue  = (c >> 16) & 0xff
        old_rgb = book.colour_map[8+i]
        new_rgb = (red, green, blue)
        book.palette_record.append(new_rgb)
        book.colour_map[8+i] = new_rgb
        if blah:
            if new_rgb != old_rgb:
                print("%2d: %r -> %r" % (i, old_rgb, new_rgb), file=book.logfile)

def palette_epilogue(book):
    # Check colour indexes in fonts etc.
    # This must be done here as FONT records
    # come *before* the PALETTE record :-(
    for font in book.font_list:
        if font.font_index == 4: # the missing font record
            continue
        cx = font.colour_index
        if cx == 0x7fff: # system window text colour
            continue
        if cx in book.colour_map:
            book.colour_indexes_used[cx] = 1
        elif book.verbosity:
            print("Size of colour table:", len(book.colour_map), file=book.logfile)
            fprintf(book.logfile, "*** Font #%d (%r): colour index 0x%04x is unknown\n",
                font.font_index, font.name, cx)
    if book.verbosity >= 1:
        used = sorted(book.colour_indexes_used.keys())
        print("\nColour indexes used:\n%r\n" % used, file=book.logfile)

def handle_style(book, data):
    if not book.formatting_info:
        return
    blah = DEBUG or book.verbosity >= 2
    bv = book.biff_version
    flag_and_xfx, built_in_id, level = unpack('<HBB', data[:4])
    xf_index = flag_and_xfx & 0x0fff
    if (data == b"\0\0\0\0"
    and "Normal" not in book.style_name_map):
        # Erroneous record (doesn't have built-in bit set).
        # Example file supplied by Jeff Bell.
        built_in = 1
        built_in_id = 0
        xf_index = 0
        name = "Normal"
        level = 255
    elif flag_and_xfx & 0x8000:
        # built-in style
        built_in = 1
        name = built_in_style_names[built_in_id]
        if 1 <= built_in_id <= 2:
            name += str(level + 1)
    else:
        # user-defined style
        built_in = 0
        built_in_id = 0
        level = 0
        if bv >= 80:
            try:
                name = unpack_unicode(data, 2, lenlen=2)
            except UnicodeDecodeError:
                print("STYLE: built_in=%d xf_index=%d built_in_id=%d level=%d" \
                    % (built_in, xf_index, built_in_id, level), file=book.logfile)
                print("raw bytes:", repr(data[2:]), file=book.logfile)
                raise
        else:
            name = unpack_string(data, 2, book.encoding, lenlen=1)
        if blah and not name:
            print("WARNING *** A user-defined style has a zero-length name", file=book.logfile)
    book.style_name_map[name] = (built_in, xf_index)
    if blah:
        fprintf(book.logfile, "STYLE: built_in=%d xf_index=%d built_in_id=%d level=%d name=%r\n",
            built_in, xf_index, built_in_id, level, name)

def check_colour_indexes_in_obj(book, obj, orig_index):
    alist = sorted(obj.__dict__.items())
    for attr, nobj in alist:
        if hasattr(nobj, 'dump'):
            check_colour_indexes_in_obj(book, nobj, orig_index)
        elif attr.find('colour_index') >= 0:
            if nobj in book.colour_map:
                book.colour_indexes_used[nobj] = 1
                continue
            oname = obj.__class__.__name__
            print("*** xf #%d : %s.%s =  0x%04x (unknown)" \
                % (orig_index, oname, attr, nobj), file=book.logfile)

def fill_in_standard_formats(book):
    for x in std_format_code_types.keys():
        if x not in book.format_map:
            ty = std_format_code_types[x]
            # Note: many standard format codes (mostly CJK date formats) have
            # format strings that vary by locale; xlrd does not (yet)
            # handle those; the type (date or numeric) is recorded but the fmt_str will be None.
            fmt_str = std_format_strings.get(x)
            fmtobj = Format(x, ty, fmt_str)
            book.format_map[x] = fmtobj

def handle_xf(self, data):
    ### self is a Book instance
    # DEBUG = 0
    blah = DEBUG or self.verbosity >= 3
    bv = self.biff_version
    xf = XF()
    xf.alignment = XFAlignment()
    xf.alignment.indent_level = 0
    xf.alignment.shrink_to_fit = 0
    xf.alignment.text_direction = 0
    xf.border = XFBorder()
    xf.border.diag_up = 0
    xf.border.diag_down = 0
    xf.border.diag_colour_index = 0
    xf.border.diag_line_style = 0 # no line
    xf.background = XFBackground()
    xf.protection = XFProtection()
    # fill in the known standard formats
    if bv >= 50 and not self.xfcount:
        # i.e. do this once before we process the first XF record
        fill_in_standard_formats(self)
    if bv >= 80:
        unpack_fmt = '<HHHBBBBIiH'
        (xf.font_index, xf.format_key, pkd_type_par,
        pkd_align1, xf.alignment.rotation, pkd_align2,
        pkd_used, pkd_brdbkg1, pkd_brdbkg2, pkd_brdbkg3,
        ) = unpack(unpack_fmt, data[0:20])
        upkbits(xf.protection, pkd_type_par, (
            (0, 0x01, 'cell_locked'),
            (1, 0x02, 'formula_hidden'),
            ))
        upkbits(xf, pkd_type_par, (
            (2, 0x0004, 'is_style'),
            # Following is not in OOo docs, but is mentioned
            # in Gnumeric source and also in (deep breath)
            # org.apache.poi.hssf.record.ExtendedFormatRecord.java
            (3, 0x0008, 'lotus_123_prefix'), # Meaning is not known.
            (4, 0xFFF0, 'parent_style_index'),
            ))
        upkbits(xf.alignment, pkd_align1, (
            (0, 0x07, 'hor_align'),
            (3, 0x08, 'text_wrapped'),
            (4, 0x70, 'vert_align'),
            ))
        upkbits(xf.alignment, pkd_align2, (
            (0, 0x0f, 'indent_level'),
            (4, 0x10, 'shrink_to_fit'),
            (6, 0xC0, 'text_direction'),
            ))
        reg = pkd_used >> 2
        for attr_stem in \
            "format font alignment border background protection".split():
            attr = "_" + attr_stem + "_flag"
            setattr(xf, attr, reg & 1)
            reg >>= 1
        upkbitsL(xf.border, pkd_brdbkg1, (
            (0,  0x0000000f,  'left_line_style'),
            (4,  0x000000f0,  'right_line_style'),
            (8,  0x00000f00,  'top_line_style'),
            (12, 0x0000f000,  'bottom_line_style'),
            (16, 0x007f0000,  'left_colour_index'),
            (23, 0x3f800000,  'right_colour_index'),
            (30, 0x40000000,  'diag_down'),
            (31, 0x80000000, 'diag_up'),
            ))
        upkbits(xf.border, pkd_brdbkg2, (
            (0,  0x0000007F, 'top_colour_index'),
            (7,  0x00003F80, 'bottom_colour_index'),
            (14, 0x001FC000, 'diag_colour_index'),
            (21, 0x01E00000, 'diag_line_style'),
            ))
        upkbitsL(xf.background, pkd_brdbkg2, (
            (26, 0xFC000000, 'fill_pattern'),
            ))
        upkbits(xf.background, pkd_brdbkg3, (
            (0, 0x007F, 'pattern_colour_index'),
            (7, 0x3F80, 'background_colour_index'),
            ))
    elif bv >= 50:
        unpack_fmt = '<HHHBBIi'
        (xf.font_index, xf.format_key, pkd_type_par,
        pkd_align1, pkd_orient_used,
        pkd_brdbkg1, pkd_brdbkg2,
        ) = unpack(unpack_fmt, data[0:16])
        upkbits(xf.protection, pkd_type_par, (
            (0, 0x01, 'cell_locked'),
            (1, 0x02, 'formula_hidden'),
            ))
        upkbits(xf, pkd_type_par, (
            (2, 0x0004, 'is_style'),
            (3, 0x0008, 'lotus_123_prefix'), # Meaning is not known.
            (4, 0xFFF0, 'parent_style_index'),
            ))
        upkbits(xf.alignment, pkd_align1, (
            (0, 0x07, 'hor_align'),
            (3, 0x08, 'text_wrapped'),
            (4, 0x70, 'vert_align'),
            ))
        orientation = pkd_orient_used & 0x03
        xf.alignment.rotation = [0, 255, 90, 180][orientation]
        reg = pkd_orient_used >> 2
        for attr_stem in \
            "format font alignment border background protection".split():
            attr = "_" + attr_stem + "_flag"
            setattr(xf, attr, reg & 1)
            reg >>= 1
        upkbitsL(xf.background, pkd_brdbkg1, (
            ( 0, 0x0000007F, 'pattern_colour_index'),
            ( 7, 0x00003F80, 'background_colour_index'),
            (16, 0x003F0000, 'fill_pattern'),
            ))
        upkbitsL(xf.border, pkd_brdbkg1, (
            (22, 0x01C00000,  'bottom_line_style'),
            (25, 0xFE000000, 'bottom_colour_index'),
            ))
        upkbits(xf.border, pkd_brdbkg2, (
            ( 0, 0x00000007, 'top_line_style'),
            ( 3, 0x00000038, 'left_line_style'),
            ( 6, 0x000001C0, 'right_line_style'),
            ( 9, 0x0000FE00, 'top_colour_index'),
            (16, 0x007F0000, 'left_colour_index'),
            (23, 0x3F800000, 'right_colour_index'),
            ))
    elif bv >= 40:
        unpack_fmt = '<BBHBBHI'
        (xf.font_index, xf.format_key, pkd_type_par,
        pkd_align_orient, pkd_used,
        pkd_bkg_34, pkd_brd_34,
        ) = unpack(unpack_fmt, data[0:12])
        upkbits(xf.protection, pkd_type_par, (
            (0, 0x01, 'cell_locked'),
            (1, 0x02, 'formula_hidden'),
            ))
        upkbits(xf, pkd_type_par, (
            (2, 0x0004, 'is_style'),
            (3, 0x0008, 'lotus_123_prefix'), # Meaning is not known.
            (4, 0xFFF0, 'parent_style_index'),
            ))
        upkbits(xf.alignment, pkd_align_orient, (
            (0, 0x07, 'hor_align'),
            (3, 0x08, 'text_wrapped'),
            (4, 0x30, 'vert_align'),
            ))
        orientation = (pkd_align_orient & 0xC0) >> 6
        xf.alignment.rotation = [0, 255, 90, 180][orientation]
        reg = pkd_used >> 2
        for attr_stem in \
            "format font alignment border background protection".split():
            attr = "_" + attr_stem + "_flag"
            setattr(xf, attr, reg & 1)
            reg >>= 1
        upkbits(xf.background, pkd_bkg_34, (
            ( 0, 0x003F, 'fill_pattern'),
            ( 6, 0x07C0, 'pattern_colour_index'),
            (11, 0xF800, 'background_colour_index'),
            ))
        upkbitsL(xf.border, pkd_brd_34, (
            ( 0, 0x00000007,  'top_line_style'),
            ( 3, 0x000000F8,  'top_colour_index'),
            ( 8, 0x00000700,  'left_line_style'),
            (11, 0x0000F800,  'left_colour_index'),
            (16, 0x00070000,  'bottom_line_style'),
            (19, 0x00F80000,  'bottom_colour_index'),
            (24, 0x07000000,  'right_line_style'),
            (27, 0xF8000000, 'right_colour_index'),
            ))
    elif bv == 30:
        unpack_fmt = '<BBBBHHI'
        (xf.font_index, xf.format_key, pkd_type_prot,
        pkd_used, pkd_align_par,
        pkd_bkg_34, pkd_brd_34,
        ) = unpack(unpack_fmt, data[0:12])
        upkbits(xf.protection, pkd_type_prot, (
            (0, 0x01, 'cell_locked'),
            (1, 0x02, 'formula_hidden'),
            ))
        upkbits(xf, pkd_type_prot, (
            (2, 0x0004, 'is_style'),
            (3, 0x0008, 'lotus_123_prefix'), # Meaning is not known.
            ))
        upkbits(xf.alignment, pkd_align_par, (
            (0, 0x07, 'hor_align'),
            (3, 0x08, 'text_wrapped'),
            ))
        upkbits(xf, pkd_align_par, (
            (4, 0xFFF0, 'parent_style_index'),
            ))
        reg = pkd_used >> 2
        for attr_stem in \
            "format font alignment border background protection".split():
            attr = "_" + attr_stem + "_flag"
            setattr(xf, attr, reg & 1)
            reg >>= 1
        upkbits(xf.background, pkd_bkg_34, (
            ( 0, 0x003F, 'fill_pattern'),
            ( 6, 0x07C0, 'pattern_colour_index'),
            (11, 0xF800, 'background_colour_index'),
            ))
        upkbitsL(xf.border, pkd_brd_34, (
            ( 0, 0x00000007,  'top_line_style'),
            ( 3, 0x000000F8,  'top_colour_index'),
            ( 8, 0x00000700,  'left_line_style'),
            (11, 0x0000F800,  'left_colour_index'),
            (16, 0x00070000,  'bottom_line_style'),
            (19, 0x00F80000,  'bottom_colour_index'),
            (24, 0x07000000,  'right_line_style'),
            (27, 0xF8000000, 'right_colour_index'),
            ))
        xf.alignment.vert_align = 2 # bottom
        xf.alignment.rotation = 0
    elif bv == 21:
        #### Warning: incomplete treatment; formatting_info not fully supported.
        #### Probably need to offset incoming BIFF2 XF[n] to BIFF8-like XF[n+16],
        #### and create XF[0:16] like the standard ones in BIFF8
        #### *AND* add 16 to all XF references in cell records :-(
        (xf.font_index, format_etc, halign_etc) = unpack('<BxBB', data)
        xf.format_key = format_etc & 0x3F
        upkbits(xf.protection, format_etc, (
            (6, 0x40, 'cell_locked'),
            (7, 0x80, 'formula_hidden'),
            ))
        upkbits(xf.alignment, halign_etc, (
            (0, 0x07, 'hor_align'),
            ))
        for mask, side in ((0x08, 'left'), (0x10, 'right'), (0x20, 'top'), (0x40, 'bottom')):
            if halign_etc & mask:
                colour_index, line_style = 8, 1 # black, thin
            else:
                colour_index, line_style = 0, 0 # none, none
            setattr(xf.border, side + '_colour_index', colour_index)
            setattr(xf.border, side + '_line_style', line_style)
        bg = xf.background
        if halign_etc & 0x80:
            bg.fill_pattern = 17
        else:
            bg.fill_pattern = 0
        bg.background_colour_index = 9 # white
        bg.pattern_colour_index = 8 # black
        xf.parent_style_index = 0 # ???????????
        xf.alignment.vert_align = 2 # bottom
        xf.alignment.rotation = 0
        for attr_stem in \
            "format font alignment border background protection".split():
            attr = "_" + attr_stem + "_flag"
            setattr(xf, attr, 1)
    else:
        raise XLRDError('programmer stuff-up: bv=%d' % bv)

    xf.xf_index = len(self.xf_list)
    self.xf_list.append(xf)
    self.xfcount += 1
    if blah:
        xf.dump(
            self.logfile,
            header="--- handle_xf: xf[%d] ---" % xf.xf_index,
            footer=" ",
        )
    try:
        fmt = self.format_map[xf.format_key]
        cellty = _cellty_from_fmtty[fmt.type]
    except KeyError:
        cellty = XL_CELL_NUMBER
    self._xf_index_to_xl_type_map[xf.xf_index] = cellty

    # Now for some assertions ...
    if self.formatting_info:
        if self.verbosity and xf.is_style and xf.parent_style_index != 0x0FFF:
            msg = "WARNING *** XF[%d] is a style XF but parent_style_index is 0x%04x, not 0x0fff\n"
            fprintf(self.logfile, msg, xf.xf_index, xf.parent_style_index)
        check_colour_indexes_in_obj(self, xf, xf.xf_index)
    if xf.format_key not in self.format_map:
        msg = "WARNING *** XF[%d] unknown (raw) format key (%d, 0x%04x)\n"
        if self.verbosity:
            fprintf(self.logfile, msg,
                xf.xf_index, xf.format_key, xf.format_key)
        xf.format_key = 0

def xf_epilogue(self):
    # self is a Book instance.
    self._xf_epilogue_done = 1
    num_xfs = len(self.xf_list)
    blah = DEBUG or self.verbosity >= 3
    blah1 = DEBUG or self.verbosity >= 1
    if blah:
        fprintf(self.logfile, "xf_epilogue called ...\n")

    def check_same(book_arg, xf_arg, parent_arg, attr):
        # the _arg caper is to avoid a Warning msg from Python 2.1 :-(
        if getattr(xf_arg, attr) != getattr(parent_arg, attr):
            fprintf(book_arg.logfile,
                "NOTE !!! XF[%d] parent[%d] %s different\n",
                xf_arg.xf_index, parent_arg.xf_index, attr)

    for xfx in xrange(num_xfs):
        xf = self.xf_list[xfx]
        if xf.format_key not in self.format_map:
            msg = "ERROR *** XF[%d] unknown format key (%d, 0x%04x)\n"
            fprintf(self.logfile, msg,
                    xf.xf_index, xf.format_key, xf.format_key)
            xf.format_key = 0

        fmt = self.format_map[xf.format_key]
        cellty = _cellty_from_fmtty[fmt.type]
        self._xf_index_to_xl_type_map[xf.xf_index] = cellty
        # Now for some assertions etc
        if not self.formatting_info:
            continue
        if xf.is_style:
            continue
        if not(0 <= xf.parent_style_index < num_xfs):
            if blah1:
                fprintf(self.logfile,
                    "WARNING *** XF[%d]: is_style=%d but parent_style_index=%d\n",
                    xf.xf_index, xf.is_style, xf.parent_style_index)
            # make it conform
            xf.parent_style_index = 0
        if self.biff_version >= 30:
            if blah1:
                if xf.parent_style_index == xf.xf_index:
                    fprintf(self.logfile,
                        "NOTE !!! XF[%d]: parent_style_index is also %d\n",
                        xf.xf_index, xf.parent_style_index)
                elif not self.xf_list[xf.parent_style_index].is_style:
                    fprintf(self.logfile,
                        "NOTE !!! XF[%d]: parent_style_index is %d; style flag not set\n",
                        xf.xf_index, xf.parent_style_index)                
            if blah1 and xf.parent_style_index > xf.xf_index:
                fprintf(self.logfile,
                    "NOTE !!! XF[%d]: parent_style_index is %d; out of order?\n",
                    xf.xf_index, xf.parent_style_index)
            parent = self.xf_list[xf.parent_style_index]
            if not xf._alignment_flag and not parent._alignment_flag:
                if blah1: check_same(self, xf, parent, 'alignment')
            if not xf._background_flag and not parent._background_flag:
                if blah1: check_same(self, xf, parent, 'background')
            if not xf._border_flag and not parent._border_flag:
                if blah1: check_same(self, xf, parent, 'border')
            if not xf._protection_flag and not parent._protection_flag:
                if blah1: check_same(self, xf, parent, 'protection')
            if not xf._format_flag and not parent._format_flag:
                if blah1 and xf.format_key != parent.format_key:
                    fprintf(self.logfile,
                        "NOTE !!! XF[%d] fmtk=%d, parent[%d] fmtk=%r\n%r / %r\n",
                        xf.xf_index, xf.format_key, parent.xf_index, parent.format_key,
                        self.format_map[xf.format_key].format_str,
                        self.format_map[parent.format_key].format_str)
            if not xf._font_flag and not parent._font_flag:
                if blah1 and xf.font_index != parent.font_index:
                    fprintf(self.logfile,
                        "NOTE !!! XF[%d] fontx=%d, parent[%d] fontx=%r\n",
                        xf.xf_index, xf.font_index, parent.xf_index, parent.font_index)

def initialise_book(book):
    initialise_colour_map(book)
    book._xf_epilogue_done = 0
    methods = (
        handle_font,
        handle_efont,
        handle_format,
        is_date_format_string,
        handle_palette,
        palette_epilogue,
        handle_style,
        handle_xf,
        xf_epilogue,
        )
    for method in methods:
        setattr(book.__class__, method.__name__, method)

##
# <p>A collection of the border-related attributes of an XF record.
# Items correspond to those in the Excel UI's Format/Cells/Border tab.</p>
# <p> An explanations of "colour index" is given in the Formatting
# section at the start of this document.
# There are five line style attributes; possible values and the
# associated meanings are:
# 0&nbsp;=&nbsp;No line,
# 1&nbsp;=&nbsp;Thin,
# 2&nbsp;=&nbsp;Medium,
# 3&nbsp;=&nbsp;Dashed,
# 4&nbsp;=&nbsp;Dotted,
# 5&nbsp;=&nbsp;Thick,
# 6&nbsp;=&nbsp;Double,
# 7&nbsp;=&nbsp;Hair,
# 8&nbsp;=&nbsp;Medium dashed,
# 9&nbsp;=&nbsp;Thin dash-dotted,
# 10&nbsp;=&nbsp;Medium dash-dotted,
# 11&nbsp;=&nbsp;Thin dash-dot-dotted,
# 12&nbsp;=&nbsp;Medium dash-dot-dotted,
# 13&nbsp;=&nbsp;Slanted medium dash-dotted.
# The line styles 8 to 13 appear in BIFF8 files (Excel 97 and later) only.
# For pictures of the line styles, refer to OOo docs s3.10 (p22)
# "Line Styles for Cell Borders (BIFF3-BIFF8)".</p>
# <br /> -- New in version 0.6.1
class XFBorder(BaseObject, EqNeAttrs):

    ##
    # The colour index for the cell's top line
    top_colour_index = 0
    ##
    # The colour index for the cell's bottom line
    bottom_colour_index = 0
    ##
    # The colour index for the cell's left line
    left_colour_index = 0
    ##
    # The colour index for the cell's right line
    right_colour_index = 0
    ##
    # The colour index for the cell's diagonal lines, if any
    diag_colour_index = 0
    ##
    # The line style for the cell's top line
    top_line_style = 0
    ##
    # The line style for the cell's bottom line
    bottom_line_style = 0
    ##
    # The line style for the cell's left line
    left_line_style = 0
    ##
    # The line style for the cell's right line
    right_line_style = 0
    ##
    # The line style for the cell's diagonal lines, if any
    diag_line_style = 0
    ##
    # 1 = draw a diagonal from top left to bottom right
    diag_down = 0
    ##
    # 1 = draw a diagonal from bottom left to top right
    diag_up = 0

##
# A collection of the background-related attributes of an XF record.
# Items correspond to those in the Excel UI's Format/Cells/Patterns tab.
# An explanation of "colour index" is given in the Formatting
# section at the start of this document.
# <br /> -- New in version 0.6.1
class XFBackground(BaseObject, EqNeAttrs):

    ##
    # See section 3.11 of the OOo docs.
    fill_pattern = 0
    ##
    # See section 3.11 of the OOo docs.
    background_colour_index = 0
    ##
    # See section 3.11 of the OOo docs.
    pattern_colour_index = 0

##
# A collection of the alignment and similar attributes of an XF record.
# Items correspond to those in the Excel UI's Format/Cells/Alignment tab.
# <br /> -- New in version 0.6.1

class XFAlignment(BaseObject, EqNeAttrs):

    ##
    # Values: section 6.115 (p 214) of OOo docs
    hor_align = 0
    ##
    # Values: section 6.115 (p 215) of OOo docs
    vert_align = 0
    ##
    # Values: section 6.115 (p 215) of OOo docs.<br />
    # Note: file versions BIFF7 and earlier use the documented
    # "orientation" attribute; this will be mapped (without loss)
    # into "rotation".
    rotation = 0
    ##
    # 1 = text is wrapped at right margin
    text_wrapped = 0
    ##
    # A number in range(15).
    indent_level = 0
    ##
    # 1 = shrink font size to fit text into cell.
    shrink_to_fit = 0
    ##
    # 0 = according to context; 1 = left-to-right; 2 = right-to-left
    text_direction = 0

##
# A collection of the protection-related attributes of an XF record.
# Items correspond to those in the Excel UI's Format/Cells/Protection tab.
# Note the OOo docs include the "cell or style" bit
# in this bundle of attributes.
# This is incorrect; the bit is used in determining which bundles to use.
# <br /> -- New in version 0.6.1

class XFProtection(BaseObject, EqNeAttrs):

    ##
    # 1 = Cell is prevented from being changed, moved, resized, or deleted
    # (only if the sheet is protected).
    cell_locked = 0
    ##
    # 1 = Hide formula so that it doesn't appear in the formula bar when
    # the cell is selected (only if the sheet is protected).
    formula_hidden = 0

##
# eXtended Formatting information for cells, rows, columns and styles.
# <br /> -- New in version 0.6.1
#
# <p>Each of the 6 flags below describes the validity of
# a specific group of attributes.
# <br />
# In cell XFs, flag==0 means the attributes of the parent style XF are used,
# (but only if the attributes are valid there); flag==1 means the attributes
# of this XF are used.<br />
# In style XFs, flag==0 means the attribute setting is valid; flag==1 means
# the attribute should be ignored.<br />
# Note that the API
# provides both "raw" XFs and "computed" XFs -- in the latter case, cell XFs
# have had the above inheritance mechanism applied.
# </p>

class XF(BaseObject):

    ##
    # 0 = cell XF, 1 = style XF
    is_style = 0
    ##
    # cell XF: Index into Book.xf_list
    # of this XF's style XF<br />
    # style XF: 0xFFF
    parent_style_index = 0
    ##
    #
    _format_flag = 0
    ##
    #
    _font_flag = 0
    ##
    #
    _alignment_flag = 0
    ##
    #
    _border_flag = 0
    ##
    #
    _background_flag = 0
    ##
    # &nbsp;
    _protection_flag = 0
    ##
    # Index into Book.xf_list
    xf_index = 0
    ##
    # Index into Book.font_list
    font_index = 0
    ##
    # Key into Book.format_map
    # <p>
    # Warning: OOo docs on the XF record call this "Index to FORMAT record".
    # It is not an index in the Python sense. It is a key to a map.
    # It is true <i>only</i> for Excel 4.0 and earlier files
    # that the key into format_map from an XF instance
    # is the same as the index into format_list, and <i>only</i>
    # if the index is less than 164.
    # </p>
    format_key = 0
    ##
    # An instance of an XFProtection object.
    protection = None
    ##
    # An instance of an XFBackground object.
    background = None
    ##
    # An instance of an XFAlignment object.
    alignment = None
    ##
    # An instance of an XFBorder object.
    border = None

########NEW FILE########
__FILENAME__ = formula
# -*- coding: cp1252 -*-

##
# Module for parsing/evaluating Microsoft Excel formulas.
#
# <p>Copyright � 2005-2012 Stephen John Machin, Lingfo Pty Ltd</p>
# <p>This module is part of the xlrd package, which is released under
# a BSD-style licence.</p>
##

# No part of the content of this file was derived from the works of David Giffin.

from __future__ import print_function 
import copy
from struct import unpack
from .timemachine import *
from .biffh import unpack_unicode_update_pos, unpack_string_update_pos, \
    XLRDError, hex_char_dump, error_text_from_code, BaseObject

__all__ = [
    'oBOOL', 'oERR', 'oNUM', 'oREF', 'oREL', 'oSTRG', 'oUNK',
    'decompile_formula',
    'dump_formula',
    'evaluate_name_formula',
    'okind_dict',
    'rangename3d', 'rangename3drel', 'cellname', 'cellnameabs', 'colname',
    'FMLA_TYPE_CELL',
    'FMLA_TYPE_SHARED',
    'FMLA_TYPE_ARRAY',
    'FMLA_TYPE_COND_FMT',
    'FMLA_TYPE_DATA_VAL',
    'FMLA_TYPE_NAME',
    ]

FMLA_TYPE_CELL = 1
FMLA_TYPE_SHARED = 2
FMLA_TYPE_ARRAY = 4
FMLA_TYPE_COND_FMT = 8
FMLA_TYPE_DATA_VAL = 16
FMLA_TYPE_NAME = 32
ALL_FMLA_TYPES = 63


FMLA_TYPEDESCR_MAP = {
    1 : 'CELL',
    2 : 'SHARED',
    4 : 'ARRAY',
    8 : 'COND-FMT',
    16: 'DATA-VAL',
    32: 'NAME',
    }

_TOKEN_NOT_ALLOWED = {
    0x01:   ALL_FMLA_TYPES - FMLA_TYPE_CELL, # tExp
    0x02:   ALL_FMLA_TYPES - FMLA_TYPE_CELL, # tTbl
    0x0F:   FMLA_TYPE_SHARED + FMLA_TYPE_COND_FMT + FMLA_TYPE_DATA_VAL, # tIsect
    0x10:   FMLA_TYPE_SHARED + FMLA_TYPE_COND_FMT + FMLA_TYPE_DATA_VAL, # tUnion/List
    0x11:   FMLA_TYPE_SHARED + FMLA_TYPE_COND_FMT + FMLA_TYPE_DATA_VAL, # tRange
    0x20:   FMLA_TYPE_SHARED + FMLA_TYPE_COND_FMT + FMLA_TYPE_DATA_VAL, # tArray
    0x23:   FMLA_TYPE_SHARED, # tName
    0x39:   FMLA_TYPE_SHARED + FMLA_TYPE_COND_FMT + FMLA_TYPE_DATA_VAL, # tNameX
    0x3A:   FMLA_TYPE_SHARED + FMLA_TYPE_COND_FMT + FMLA_TYPE_DATA_VAL, # tRef3d
    0x3B:   FMLA_TYPE_SHARED + FMLA_TYPE_COND_FMT + FMLA_TYPE_DATA_VAL, # tArea3d
    0x2C:   FMLA_TYPE_CELL + FMLA_TYPE_ARRAY, # tRefN
    0x2D:   FMLA_TYPE_CELL + FMLA_TYPE_ARRAY, # tAreaN
    # plus weird stuff like tMem*
    }.get

oBOOL = 3
oERR =  4
oMSNG = 5 # tMissArg
oNUM =  2
oREF = -1
oREL = -2
oSTRG = 1
oUNK =  0

okind_dict = {
    -2: "oREL",
    -1: "oREF",
    0 : "oUNK",
    1 : "oSTRG",
    2 : "oNUM",
    3 : "oBOOL",
    4 : "oERR",
    5 : "oMSNG",
    }

listsep = ',' #### probably should depend on locale


# sztabN[opcode] -> the number of bytes to consume.
# -1 means variable
# -2 means this opcode not implemented in this version.
# Which N to use? Depends on biff_version; see szdict.
sztab0 = [-2, 4, 4, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, -1, -2, -1, 8, 4, 2, 2, 3, 9, 8, 2, 3, 8, 4, 7, 5, 5, 5, 2, 4, 7, 4, 7, 2, 2, -2, -2, -2, -2, -2, -2, -2, -2, 3, -2, -2, -2, -2, -2, -2, -2]
sztab1 = [-2, 5, 5, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, -1, -2, -1, 11, 5, 2, 2, 3, 9, 9, 2, 3, 11, 4, 7, 7, 7, 7, 3, 4, 7, 4, 7, 3, 3, -2, -2, -2, -2, -2, -2, -2, -2, 3, -2, -2, -2, -2, -2, -2, -2]
sztab2 = [-2, 5, 5, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, -1, -2, -1, 11, 5, 2, 2, 3, 9, 9, 3, 4, 11, 4, 7, 7, 7, 7, 3, 4, 7, 4, 7, 3, 3, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2]
sztab3 = [-2, 5, 5, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, -1, -2, -1, -2, -2, 2, 2, 3, 9, 9, 3, 4, 15, 4, 7, 7, 7, 7, 3, 4, 7, 4, 7, 3, 3, -2, -2, -2, -2, -2, -2, -2, -2, -2, 25, 18, 21, 18, 21, -2, -2]
sztab4 = [-2, 5, 5, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, -1, -1, -1, -2, -2, 2, 2, 3, 9, 9, 3, 4, 5, 5, 9, 7, 7, 7, 3, 5, 9, 5, 9, 3, 3, -2, -2, -2, -2, -2, -2, -2, -2, -2, 7, 7, 11, 7, 11, -2, -2]

szdict = {
    20 : sztab0,
    21 : sztab0,
    30 : sztab1,
    40 : sztab2,
    45 : sztab2,
    50 : sztab3,
    70 : sztab3,
    80 : sztab4,
    }

# For debugging purposes ... the name for each opcode
# (without the prefix "t" used on OOo docs)
onames = ['Unk00', 'Exp', 'Tbl', 'Add', 'Sub', 'Mul', 'Div', 'Power', 'Concat', 'LT', 'LE', 'EQ', 'GE', 'GT', 'NE', 'Isect', 'List', 'Range', 'Uplus', 'Uminus', 'Percent', 'Paren', 'MissArg', 'Str', 'Extended', 'Attr', 'Sheet', 'EndSheet', 'Err', 'Bool', 'Int', 'Num', 'Array', 'Func', 'FuncVar', 'Name', 'Ref', 'Area', 'MemArea', 'MemErr', 'MemNoMem', 'MemFunc', 'RefErr', 'AreaErr', 'RefN', 'AreaN', 'MemAreaN', 'MemNoMemN', '', '', '', '', '', '', '', '', 'FuncCE', 'NameX', 'Ref3d', 'Area3d', 'RefErr3d', 'AreaErr3d', '', '']

func_defs = {
    # index: (name, min#args, max#args, flags, #known_args, return_type, kargs)
    0  : ('COUNT',            0, 30, 0x04,  1, 'V', 'R'),
    1  : ('IF',               2,  3, 0x04,  3, 'V', 'VRR'),
    2  : ('ISNA',             1,  1, 0x02,  1, 'V', 'V'),
    3  : ('ISERROR',          1,  1, 0x02,  1, 'V', 'V'),
    4  : ('SUM',              0, 30, 0x04,  1, 'V', 'R'),
    5  : ('AVERAGE',          1, 30, 0x04,  1, 'V', 'R'),
    6  : ('MIN',              1, 30, 0x04,  1, 'V', 'R'),
    7  : ('MAX',              1, 30, 0x04,  1, 'V', 'R'),
    8  : ('ROW',              0,  1, 0x04,  1, 'V', 'R'),
    9  : ('COLUMN',           0,  1, 0x04,  1, 'V', 'R'),
    10 : ('NA',               0,  0, 0x02,  0, 'V', ''),
    11 : ('NPV',              2, 30, 0x04,  2, 'V', 'VR'),
    12 : ('STDEV',            1, 30, 0x04,  1, 'V', 'R'),
    13 : ('DOLLAR',           1,  2, 0x04,  1, 'V', 'V'),
    14 : ('FIXED',            2,  3, 0x04,  3, 'V', 'VVV'),
    15 : ('SIN',              1,  1, 0x02,  1, 'V', 'V'),
    16 : ('COS',              1,  1, 0x02,  1, 'V', 'V'),
    17 : ('TAN',              1,  1, 0x02,  1, 'V', 'V'),
    18 : ('ATAN',             1,  1, 0x02,  1, 'V', 'V'),
    19 : ('PI',               0,  0, 0x02,  0, 'V', ''),
    20 : ('SQRT',             1,  1, 0x02,  1, 'V', 'V'),
    21 : ('EXP',              1,  1, 0x02,  1, 'V', 'V'),
    22 : ('LN',               1,  1, 0x02,  1, 'V', 'V'),
    23 : ('LOG10',            1,  1, 0x02,  1, 'V', 'V'),
    24 : ('ABS',              1,  1, 0x02,  1, 'V', 'V'),
    25 : ('INT',              1,  1, 0x02,  1, 'V', 'V'),
    26 : ('SIGN',             1,  1, 0x02,  1, 'V', 'V'),
    27 : ('ROUND',            2,  2, 0x02,  2, 'V', 'VV'),
    28 : ('LOOKUP',           2,  3, 0x04,  2, 'V', 'VR'),
    29 : ('INDEX',            2,  4, 0x0c,  4, 'R', 'RVVV'),
    30 : ('REPT',             2,  2, 0x02,  2, 'V', 'VV'),
    31 : ('MID',              3,  3, 0x02,  3, 'V', 'VVV'),
    32 : ('LEN',              1,  1, 0x02,  1, 'V', 'V'),
    33 : ('VALUE',            1,  1, 0x02,  1, 'V', 'V'),
    34 : ('TRUE',             0,  0, 0x02,  0, 'V', ''),
    35 : ('FALSE',            0,  0, 0x02,  0, 'V', ''),
    36 : ('AND',              1, 30, 0x04,  1, 'V', 'R'),
    37 : ('OR',               1, 30, 0x04,  1, 'V', 'R'),
    38 : ('NOT',              1,  1, 0x02,  1, 'V', 'V'),
    39 : ('MOD',              2,  2, 0x02,  2, 'V', 'VV'),
    40 : ('DCOUNT',           3,  3, 0x02,  3, 'V', 'RRR'),
    41 : ('DSUM',             3,  3, 0x02,  3, 'V', 'RRR'),
    42 : ('DAVERAGE',         3,  3, 0x02,  3, 'V', 'RRR'),
    43 : ('DMIN',             3,  3, 0x02,  3, 'V', 'RRR'),
    44 : ('DMAX',             3,  3, 0x02,  3, 'V', 'RRR'),
    45 : ('DSTDEV',           3,  3, 0x02,  3, 'V', 'RRR'),
    46 : ('VAR',              1, 30, 0x04,  1, 'V', 'R'),
    47 : ('DVAR',             3,  3, 0x02,  3, 'V', 'RRR'),
    48 : ('TEXT',             2,  2, 0x02,  2, 'V', 'VV'),
    49 : ('LINEST',           1,  4, 0x04,  4, 'A', 'RRVV'),
    50 : ('TREND',            1,  4, 0x04,  4, 'A', 'RRRV'),
    51 : ('LOGEST',           1,  4, 0x04,  4, 'A', 'RRVV'),
    52 : ('GROWTH',           1,  4, 0x04,  4, 'A', 'RRRV'),
    56 : ('PV',               3,  5, 0x04,  5, 'V', 'VVVVV'),
    57 : ('FV',               3,  5, 0x04,  5, 'V', 'VVVVV'),
    58 : ('NPER',             3,  5, 0x04,  5, 'V', 'VVVVV'),
    59 : ('PMT',              3,  5, 0x04,  5, 'V', 'VVVVV'),
    60 : ('RATE',             3,  6, 0x04,  6, 'V', 'VVVVVV'),
    61 : ('MIRR',             3,  3, 0x02,  3, 'V', 'RVV'),
    62 : ('IRR',              1,  2, 0x04,  2, 'V', 'RV'),
    63 : ('RAND',             0,  0, 0x0a,  0, 'V', ''),
    64 : ('MATCH',            2,  3, 0x04,  3, 'V', 'VRR'),
    65 : ('DATE',             3,  3, 0x02,  3, 'V', 'VVV'),
    66 : ('TIME',             3,  3, 0x02,  3, 'V', 'VVV'),
    67 : ('DAY',              1,  1, 0x02,  1, 'V', 'V'),
    68 : ('MONTH',            1,  1, 0x02,  1, 'V', 'V'),
    69 : ('YEAR',             1,  1, 0x02,  1, 'V', 'V'),
    70 : ('WEEKDAY',          1,  2, 0x04,  2, 'V', 'VV'),
    71 : ('HOUR',             1,  1, 0x02,  1, 'V', 'V'),
    72 : ('MINUTE',           1,  1, 0x02,  1, 'V', 'V'),
    73 : ('SECOND',           1,  1, 0x02,  1, 'V', 'V'),
    74 : ('NOW',              0,  0, 0x0a,  0, 'V', ''),
    75 : ('AREAS',            1,  1, 0x02,  1, 'V', 'R'),
    76 : ('ROWS',             1,  1, 0x02,  1, 'V', 'R'),
    77 : ('COLUMNS',          1,  1, 0x02,  1, 'V', 'R'),
    78 : ('OFFSET',           3,  5, 0x04,  5, 'R', 'RVVVV'),
    82 : ('SEARCH',           2,  3, 0x04,  3, 'V', 'VVV'),
    83 : ('TRANSPOSE',        1,  1, 0x02,  1, 'A', 'A'),
    86 : ('TYPE',             1,  1, 0x02,  1, 'V', 'V'),
    92 : ('SERIESSUM',        4,  4, 0x02,  4, 'V', 'VVVA'),
    97 : ('ATAN2',            2,  2, 0x02,  2, 'V', 'VV'),
    98 : ('ASIN',             1,  1, 0x02,  1, 'V', 'V'),
    99 : ('ACOS',             1,  1, 0x02,  1, 'V', 'V'),
    100: ('CHOOSE',           2, 30, 0x04,  2, 'V', 'VR'),
    101: ('HLOOKUP',          3,  4, 0x04,  4, 'V', 'VRRV'),
    102: ('VLOOKUP',          3,  4, 0x04,  4, 'V', 'VRRV'),
    105: ('ISREF',            1,  1, 0x02,  1, 'V', 'R'),
    109: ('LOG',              1,  2, 0x04,  2, 'V', 'VV'),
    111: ('CHAR',             1,  1, 0x02,  1, 'V', 'V'),
    112: ('LOWER',            1,  1, 0x02,  1, 'V', 'V'),
    113: ('UPPER',            1,  1, 0x02,  1, 'V', 'V'),
    114: ('PROPER',           1,  1, 0x02,  1, 'V', 'V'),
    115: ('LEFT',             1,  2, 0x04,  2, 'V', 'VV'),
    116: ('RIGHT',            1,  2, 0x04,  2, 'V', 'VV'),
    117: ('EXACT',            2,  2, 0x02,  2, 'V', 'VV'),
    118: ('TRIM',             1,  1, 0x02,  1, 'V', 'V'),
    119: ('REPLACE',          4,  4, 0x02,  4, 'V', 'VVVV'),
    120: ('SUBSTITUTE',       3,  4, 0x04,  4, 'V', 'VVVV'),
    121: ('CODE',             1,  1, 0x02,  1, 'V', 'V'),
    124: ('FIND',             2,  3, 0x04,  3, 'V', 'VVV'),
    125: ('CELL',             1,  2, 0x0c,  2, 'V', 'VR'),
    126: ('ISERR',            1,  1, 0x02,  1, 'V', 'V'),
    127: ('ISTEXT',           1,  1, 0x02,  1, 'V', 'V'),
    128: ('ISNUMBER',         1,  1, 0x02,  1, 'V', 'V'),
    129: ('ISBLANK',          1,  1, 0x02,  1, 'V', 'V'),
    130: ('T',                1,  1, 0x02,  1, 'V', 'R'),
    131: ('N',                1,  1, 0x02,  1, 'V', 'R'),
    140: ('DATEVALUE',        1,  1, 0x02,  1, 'V', 'V'),
    141: ('TIMEVALUE',        1,  1, 0x02,  1, 'V', 'V'),
    142: ('SLN',              3,  3, 0x02,  3, 'V', 'VVV'),
    143: ('SYD',              4,  4, 0x02,  4, 'V', 'VVVV'),
    144: ('DDB',              4,  5, 0x04,  5, 'V', 'VVVVV'),
    148: ('INDIRECT',         1,  2, 0x0c,  2, 'R', 'VV'),
    162: ('CLEAN',            1,  1, 0x02,  1, 'V', 'V'),
    163: ('MDETERM',          1,  1, 0x02,  1, 'V', 'A'),
    164: ('MINVERSE',         1,  1, 0x02,  1, 'A', 'A'),
    165: ('MMULT',            2,  2, 0x02,  2, 'A', 'AA'),
    167: ('IPMT',             4,  6, 0x04,  6, 'V', 'VVVVVV'),
    168: ('PPMT',             4,  6, 0x04,  6, 'V', 'VVVVVV'),
    169: ('COUNTA',           0, 30, 0x04,  1, 'V', 'R'),
    183: ('PRODUCT',          0, 30, 0x04,  1, 'V', 'R'),
    184: ('FACT',             1,  1, 0x02,  1, 'V', 'V'),
    189: ('DPRODUCT',         3,  3, 0x02,  3, 'V', 'RRR'),
    190: ('ISNONTEXT',        1,  1, 0x02,  1, 'V', 'V'),
    193: ('STDEVP',           1, 30, 0x04,  1, 'V', 'R'),
    194: ('VARP',             1, 30, 0x04,  1, 'V', 'R'),
    195: ('DSTDEVP',          3,  3, 0x02,  3, 'V', 'RRR'),
    196: ('DVARP',            3,  3, 0x02,  3, 'V', 'RRR'),
    197: ('TRUNC',            1,  2, 0x04,  2, 'V', 'VV'),
    198: ('ISLOGICAL',        1,  1, 0x02,  1, 'V', 'V'),
    199: ('DCOUNTA',          3,  3, 0x02,  3, 'V', 'RRR'),
    204: ('USDOLLAR',         1,  2, 0x04,  2, 'V', 'VV'),
    205: ('FINDB',            2,  3, 0x04,  3, 'V', 'VVV'),
    206: ('SEARCHB',          2,  3, 0x04,  3, 'V', 'VVV'),
    207: ('REPLACEB',         4,  4, 0x02,  4, 'V', 'VVVV'),
    208: ('LEFTB',            1,  2, 0x04,  2, 'V', 'VV'),
    209: ('RIGHTB',           1,  2, 0x04,  2, 'V', 'VV'),
    210: ('MIDB',             3,  3, 0x02,  3, 'V', 'VVV'),
    211: ('LENB',             1,  1, 0x02,  1, 'V', 'V'),
    212: ('ROUNDUP',          2,  2, 0x02,  2, 'V', 'VV'),
    213: ('ROUNDDOWN',        2,  2, 0x02,  2, 'V', 'VV'),
    214: ('ASC',              1,  1, 0x02,  1, 'V', 'V'),
    215: ('DBCS',             1,  1, 0x02,  1, 'V', 'V'),
    216: ('RANK',             2,  3, 0x04,  3, 'V', 'VRV'),
    219: ('ADDRESS',          2,  5, 0x04,  5, 'V', 'VVVVV'),
    220: ('DAYS360',          2,  3, 0x04,  3, 'V', 'VVV'),
    221: ('TODAY',            0,  0, 0x0a,  0, 'V', ''),
    222: ('VDB',              5,  7, 0x04,  7, 'V', 'VVVVVVV'),
    227: ('MEDIAN',           1, 30, 0x04,  1, 'V', 'R'),
    228: ('SUMPRODUCT',       1, 30, 0x04,  1, 'V', 'A'),
    229: ('SINH',             1,  1, 0x02,  1, 'V', 'V'),
    230: ('COSH',             1,  1, 0x02,  1, 'V', 'V'),
    231: ('TANH',             1,  1, 0x02,  1, 'V', 'V'),
    232: ('ASINH',            1,  1, 0x02,  1, 'V', 'V'),
    233: ('ACOSH',            1,  1, 0x02,  1, 'V', 'V'),
    234: ('ATANH',            1,  1, 0x02,  1, 'V', 'V'),
    235: ('DGET',             3,  3, 0x02,  3, 'V', 'RRR'),
    244: ('INFO',             1,  1, 0x02,  1, 'V', 'V'),
    247: ('DB',               4,  5, 0x04,  5, 'V', 'VVVVV'),
    252: ('FREQUENCY',        2,  2, 0x02,  2, 'A', 'RR'),
    261: ('ERROR.TYPE',       1,  1, 0x02,  1, 'V', 'V'),
    269: ('AVEDEV',           1, 30, 0x04,  1, 'V', 'R'),
    270: ('BETADIST',         3,  5, 0x04,  1, 'V', 'V'),
    271: ('GAMMALN',          1,  1, 0x02,  1, 'V', 'V'),
    272: ('BETAINV',          3,  5, 0x04,  1, 'V', 'V'),
    273: ('BINOMDIST',        4,  4, 0x02,  4, 'V', 'VVVV'),
    274: ('CHIDIST',          2,  2, 0x02,  2, 'V', 'VV'),
    275: ('CHIINV',           2,  2, 0x02,  2, 'V', 'VV'),
    276: ('COMBIN',           2,  2, 0x02,  2, 'V', 'VV'),
    277: ('CONFIDENCE',       3,  3, 0x02,  3, 'V', 'VVV'),
    278: ('CRITBINOM',        3,  3, 0x02,  3, 'V', 'VVV'),
    279: ('EVEN',             1,  1, 0x02,  1, 'V', 'V'),
    280: ('EXPONDIST',        3,  3, 0x02,  3, 'V', 'VVV'),
    281: ('FDIST',            3,  3, 0x02,  3, 'V', 'VVV'),
    282: ('FINV',             3,  3, 0x02,  3, 'V', 'VVV'),
    283: ('FISHER',           1,  1, 0x02,  1, 'V', 'V'),
    284: ('FISHERINV',        1,  1, 0x02,  1, 'V', 'V'),
    285: ('FLOOR',            2,  2, 0x02,  2, 'V', 'VV'),
    286: ('GAMMADIST',        4,  4, 0x02,  4, 'V', 'VVVV'),
    287: ('GAMMAINV',         3,  3, 0x02,  3, 'V', 'VVV'),
    288: ('CEILING',          2,  2, 0x02,  2, 'V', 'VV'),
    289: ('HYPGEOMDIST',      4,  4, 0x02,  4, 'V', 'VVVV'),
    290: ('LOGNORMDIST',      3,  3, 0x02,  3, 'V', 'VVV'),
    291: ('LOGINV',           3,  3, 0x02,  3, 'V', 'VVV'),
    292: ('NEGBINOMDIST',     3,  3, 0x02,  3, 'V', 'VVV'),
    293: ('NORMDIST',         4,  4, 0x02,  4, 'V', 'VVVV'),
    294: ('NORMSDIST',        1,  1, 0x02,  1, 'V', 'V'),
    295: ('NORMINV',          3,  3, 0x02,  3, 'V', 'VVV'),
    296: ('NORMSINV',         1,  1, 0x02,  1, 'V', 'V'),
    297: ('STANDARDIZE',      3,  3, 0x02,  3, 'V', 'VVV'),
    298: ('ODD',              1,  1, 0x02,  1, 'V', 'V'),
    299: ('PERMUT',           2,  2, 0x02,  2, 'V', 'VV'),
    300: ('POISSON',          3,  3, 0x02,  3, 'V', 'VVV'),
    301: ('TDIST',            3,  3, 0x02,  3, 'V', 'VVV'),
    302: ('WEIBULL',          4,  4, 0x02,  4, 'V', 'VVVV'),
    303: ('SUMXMY2',          2,  2, 0x02,  2, 'V', 'AA'),
    304: ('SUMX2MY2',         2,  2, 0x02,  2, 'V', 'AA'),
    305: ('SUMX2PY2',         2,  2, 0x02,  2, 'V', 'AA'),
    306: ('CHITEST',          2,  2, 0x02,  2, 'V', 'AA'),
    307: ('CORREL',           2,  2, 0x02,  2, 'V', 'AA'),
    308: ('COVAR',            2,  2, 0x02,  2, 'V', 'AA'),
    309: ('FORECAST',         3,  3, 0x02,  3, 'V', 'VAA'),
    310: ('FTEST',            2,  2, 0x02,  2, 'V', 'AA'),
    311: ('INTERCEPT',        2,  2, 0x02,  2, 'V', 'AA'),
    312: ('PEARSON',          2,  2, 0x02,  2, 'V', 'AA'),
    313: ('RSQ',              2,  2, 0x02,  2, 'V', 'AA'),
    314: ('STEYX',            2,  2, 0x02,  2, 'V', 'AA'),
    315: ('SLOPE',            2,  2, 0x02,  2, 'V', 'AA'),
    316: ('TTEST',            4,  4, 0x02,  4, 'V', 'AAVV'),
    317: ('PROB',             3,  4, 0x04,  3, 'V', 'AAV'),
    318: ('DEVSQ',            1, 30, 0x04,  1, 'V', 'R'),
    319: ('GEOMEAN',          1, 30, 0x04,  1, 'V', 'R'),
    320: ('HARMEAN',          1, 30, 0x04,  1, 'V', 'R'),
    321: ('SUMSQ',            0, 30, 0x04,  1, 'V', 'R'),
    322: ('KURT',             1, 30, 0x04,  1, 'V', 'R'),
    323: ('SKEW',             1, 30, 0x04,  1, 'V', 'R'),
    324: ('ZTEST',            2,  3, 0x04,  2, 'V', 'RV'),
    325: ('LARGE',            2,  2, 0x02,  2, 'V', 'RV'),
    326: ('SMALL',            2,  2, 0x02,  2, 'V', 'RV'),
    327: ('QUARTILE',         2,  2, 0x02,  2, 'V', 'RV'),
    328: ('PERCENTILE',       2,  2, 0x02,  2, 'V', 'RV'),
    329: ('PERCENTRANK',      2,  3, 0x04,  2, 'V', 'RV'),
    330: ('MODE',             1, 30, 0x04,  1, 'V', 'A'),
    331: ('TRIMMEAN',         2,  2, 0x02,  2, 'V', 'RV'),
    332: ('TINV',             2,  2, 0x02,  2, 'V', 'VV'),
    336: ('CONCATENATE',      0, 30, 0x04,  1, 'V', 'V'),
    337: ('POWER',            2,  2, 0x02,  2, 'V', 'VV'),
    342: ('RADIANS',          1,  1, 0x02,  1, 'V', 'V'),
    343: ('DEGREES',          1,  1, 0x02,  1, 'V', 'V'),
    344: ('SUBTOTAL',         2, 30, 0x04,  2, 'V', 'VR'),
    345: ('SUMIF',            2,  3, 0x04,  3, 'V', 'RVR'),
    346: ('COUNTIF',          2,  2, 0x02,  2, 'V', 'RV'),
    347: ('COUNTBLANK',       1,  1, 0x02,  1, 'V', 'R'),
    350: ('ISPMT',            4,  4, 0x02,  4, 'V', 'VVVV'),
    351: ('DATEDIF',          3,  3, 0x02,  3, 'V', 'VVV'),
    352: ('DATESTRING',       1,  1, 0x02,  1, 'V', 'V'),
    353: ('NUMBERSTRING',     2,  2, 0x02,  2, 'V', 'VV'),
    354: ('ROMAN',            1,  2, 0x04,  2, 'V', 'VV'),
    358: ('GETPIVOTDATA',     2,  2, 0x02,  2, 'V', 'RV'),
    359: ('HYPERLINK',        1,  2, 0x04,  2, 'V', 'VV'),
    360: ('PHONETIC',         1,  1, 0x02,  1, 'V', 'V'),
    361: ('AVERAGEA',         1, 30, 0x04,  1, 'V', 'R'),
    362: ('MAXA',             1, 30, 0x04,  1, 'V', 'R'),
    363: ('MINA',             1, 30, 0x04,  1, 'V', 'R'),
    364: ('STDEVPA',          1, 30, 0x04,  1, 'V', 'R'),
    365: ('VARPA',            1, 30, 0x04,  1, 'V', 'R'),
    366: ('STDEVA',           1, 30, 0x04,  1, 'V', 'R'),
    367: ('VARA',             1, 30, 0x04,  1, 'V', 'R'),
    368: ('BAHTTEXT',         1,  1, 0x02,  1, 'V', 'V'),
    369: ('THAIDAYOFWEEK',    1,  1, 0x02,  1, 'V', 'V'),
    370: ('THAIDIGIT',        1,  1, 0x02,  1, 'V', 'V'),
    371: ('THAIMONTHOFYEAR',  1,  1, 0x02,  1, 'V', 'V'),
    372: ('THAINUMSOUND',     1,  1, 0x02,  1, 'V', 'V'),
    373: ('THAINUMSTRING',    1,  1, 0x02,  1, 'V', 'V'),
    374: ('THAISTRINGLENGTH', 1,  1, 0x02,  1, 'V', 'V'),
    375: ('ISTHAIDIGIT',      1,  1, 0x02,  1, 'V', 'V'),
    376: ('ROUNDBAHTDOWN',    1,  1, 0x02,  1, 'V', 'V'),
    377: ('ROUNDBAHTUP',      1,  1, 0x02,  1, 'V', 'V'),
    378: ('THAIYEAR',         1,  1, 0x02,  1, 'V', 'V'),
    379: ('RTD',              2,  5, 0x04,  1, 'V', 'V'),
    }

tAttrNames = {
    0x00: "Skip??", # seen in SAMPLES.XLS which shipped with Excel 5.0
    0x01: "Volatile",
    0x02: "If",
    0x04: "Choose",
    0x08: "Skip",
    0x10: "Sum",
    0x20: "Assign",
    0x40: "Space",
    0x41: "SpaceVolatile",
    }

error_opcodes = set([0x07, 0x08, 0x0A, 0x0B, 0x1C, 0x1D, 0x2F])

tRangeFuncs = (min, max, min, max, min, max)
tIsectFuncs = (max, min, max, min, max, min)

def do_box_funcs(box_funcs, boxa, boxb):
    return tuple([
        func(numa, numb)
        for func, numa, numb in zip(box_funcs, boxa.coords, boxb.coords)
        ])

def adjust_cell_addr_biff8(rowval, colval, reldelta, browx=None, bcolx=None):
    row_rel = (colval >> 15) & 1
    col_rel = (colval >> 14) & 1
    rowx = rowval
    colx = colval & 0xff
    if reldelta:
        if row_rel and rowx >= 32768:
            rowx -= 65536
        if col_rel and colx >= 128:
            colx -= 256
    else:
        if row_rel:
            rowx -= browx
        if col_rel:
            colx -= bcolx
    return rowx, colx, row_rel, col_rel

def adjust_cell_addr_biff_le7(
        rowval, colval, reldelta, browx=None, bcolx=None):
    row_rel = (rowval >> 15) & 1
    col_rel = (rowval >> 14) & 1
    rowx = rowval & 0x3fff
    colx = colval
    if reldelta:
        if row_rel and rowx >= 8192:
            rowx -= 16384
        if col_rel and colx >= 128:
            colx -= 256
    else:
        if row_rel:
            rowx -= browx
        if col_rel:
            colx -= bcolx
    return rowx, colx, row_rel, col_rel

def get_cell_addr(data, pos, bv, reldelta, browx=None, bcolx=None):
    if bv >= 80:
        rowval, colval = unpack("<HH", data[pos:pos+4])
        # print "    rv=%04xh cv=%04xh" % (rowval, colval)
        return adjust_cell_addr_biff8(rowval, colval, reldelta, browx, bcolx)
    else:
        rowval, colval = unpack("<HB", data[pos:pos+3])
        # print "    rv=%04xh cv=%04xh" % (rowval, colval)
        return adjust_cell_addr_biff_le7(
                    rowval, colval, reldelta, browx, bcolx)

def get_cell_range_addr(data, pos, bv, reldelta, browx=None, bcolx=None):
    if bv >= 80:
        row1val, row2val, col1val, col2val = unpack("<HHHH", data[pos:pos+8])
        # print "    rv=%04xh cv=%04xh" % (row1val, col1val)
        # print "    rv=%04xh cv=%04xh" % (row2val, col2val)
        res1 = adjust_cell_addr_biff8(row1val, col1val, reldelta, browx, bcolx)
        res2 = adjust_cell_addr_biff8(row2val, col2val, reldelta, browx, bcolx)
        return res1, res2
    else:
        row1val, row2val, col1val, col2val = unpack("<HHBB", data[pos:pos+6])
        # print "    rv=%04xh cv=%04xh" % (row1val, col1val)
        # print "    rv=%04xh cv=%04xh" % (row2val, col2val)
        res1 = adjust_cell_addr_biff_le7(
                    row1val, col1val, reldelta, browx, bcolx)
        res2 = adjust_cell_addr_biff_le7(
                    row2val, col2val, reldelta, browx, bcolx)
        return res1, res2

def get_externsheet_local_range(bk, refx, blah=0):
    try:
        info = bk._externsheet_info[refx]
    except IndexError:
        print("!!! get_externsheet_local_range: refx=%d, not in range(%d)" \
            % (refx, len(bk._externsheet_info)), file=bk.logfile)
        return (-101, -101)
    ref_recordx, ref_first_sheetx, ref_last_sheetx = info
    if ref_recordx == bk._supbook_addins_inx:
        if blah:
            print("/// get_externsheet_local_range(refx=%d) -> addins %r" % (refx, info), file=bk.logfile)
        assert ref_first_sheetx == 0xFFFE == ref_last_sheetx
        return (-5, -5)
    if ref_recordx != bk._supbook_locals_inx:
        if blah:
            print("/// get_externsheet_local_range(refx=%d) -> external %r" % (refx, info), file=bk.logfile)
        return (-4, -4) # external reference
    if ref_first_sheetx == 0xFFFE == ref_last_sheetx:
        if blah:
            print("/// get_externsheet_local_range(refx=%d) -> unspecified sheet %r" % (refx, info), file=bk.logfile)
        return (-1, -1) # internal reference, any sheet
    if ref_first_sheetx == 0xFFFF == ref_last_sheetx:
        if blah:
            print("/// get_externsheet_local_range(refx=%d) -> deleted sheet(s)" % (refx, ), file=bk.logfile)
        return (-2, -2) # internal reference, deleted sheet(s)
    nsheets = len(bk._all_sheets_map)
    if not(0 <= ref_first_sheetx <= ref_last_sheetx < nsheets):
        if blah:
            print("/// get_externsheet_local_range(refx=%d) -> %r" % (refx, info), file=bk.logfile)
            print("--- first/last sheet not in range(%d)" % nsheets, file=bk.logfile)
        return (-102, -102) # stuffed up somewhere :-(
    xlrd_sheetx1 = bk._all_sheets_map[ref_first_sheetx]
    xlrd_sheetx2 = bk._all_sheets_map[ref_last_sheetx]
    if not(0 <= xlrd_sheetx1 <= xlrd_sheetx2):
        return (-3, -3) # internal reference, but to a macro sheet
    return xlrd_sheetx1, xlrd_sheetx2

def get_externsheet_local_range_b57(
        bk, raw_extshtx, ref_first_sheetx, ref_last_sheetx, blah=0):
    if raw_extshtx > 0:
        if blah:
            print("/// get_externsheet_local_range_b57(raw_extshtx=%d) -> external" % raw_extshtx, file=bk.logfile)
        return (-4, -4) # external reference
    if ref_first_sheetx == -1 and ref_last_sheetx == -1:
        return (-2, -2) # internal reference, deleted sheet(s)
    nsheets = len(bk._all_sheets_map)
    if not(0 <= ref_first_sheetx <= ref_last_sheetx < nsheets):
        if blah:
            print("/// get_externsheet_local_range_b57(%d, %d, %d) -> ???" \
                % (raw_extshtx, ref_first_sheetx, ref_last_sheetx), file=bk.logfile)
            print("--- first/last sheet not in range(%d)" % nsheets, file=bk.logfile)
        return (-103, -103) # stuffed up somewhere :-(
    xlrd_sheetx1 = bk._all_sheets_map[ref_first_sheetx]
    xlrd_sheetx2 = bk._all_sheets_map[ref_last_sheetx]
    if not(0 <= xlrd_sheetx1 <= xlrd_sheetx2):
        return (-3, -3) # internal reference, but to a macro sheet
    return xlrd_sheetx1, xlrd_sheetx2

class FormulaError(Exception):
    pass


##
# Used in evaluating formulas.
# The following table describes the kinds and how their values
# are represented.</p>
#
# <table border="1" cellpadding="7">
# <tr>
# <th>Kind symbol</th>
# <th>Kind number</th>
# <th>Value representation</th>
# </tr>
# <tr>
# <td>oBOOL</td>
# <td align="center">3</td>
# <td>integer: 0 => False; 1 => True</td>
# </tr>
# <tr>
# <td>oERR</td>
# <td align="center">4</td>
# <td>None, or an int error code (same as XL_CELL_ERROR in the Cell class).
# </td>
# </tr>
# <tr>
# <td>oMSNG</td>
# <td align="center">5</td>
# <td>Used by Excel as a placeholder for a missing (not supplied) function
# argument. Should *not* appear as a final formula result. Value is None.</td>
# </tr>
# <tr>
# <td>oNUM</td>
# <td align="center">2</td>
# <td>A float. Note that there is no way of distinguishing dates.</td>
# </tr>
# <tr>
# <td>oREF</td>
# <td align="center">-1</td>
# <td>The value is either None or a non-empty list of
# absolute Ref3D instances.<br>
# </td>
# </tr>
# <tr>
# <td>oREL</td>
# <td align="center">-2</td>
# <td>The value is None or a non-empty list of
# fully or partially relative Ref3D instances.
# </td>
# </tr>
# <tr>
# <td>oSTRG</td>
# <td align="center">1</td>
# <td>A Unicode string.</td>
# </tr>
# <tr>
# <td>oUNK</td>
# <td align="center">0</td>
# <td>The kind is unknown or ambiguous. The value is None</td>
# </tr>
# </table>
#<p></p>

class Operand(object):

    ##
    # None means that the actual value of the operand is a variable
    # (depends on cell data), not a constant.
    value = None
    ##
    # oUNK means that the kind of operand is not known unambiguously.
    kind = oUNK
    ##
    # The reconstituted text of the original formula. Function names will be
    # in English irrespective of the original language, which doesn't seem
    # to be recorded anywhere. The separator is ",", not ";" or whatever else
    # might be more appropriate for the end-user's locale; patches welcome.
    text = '?'

    def __init__(self, akind=None, avalue=None, arank=0, atext='?'):
        if akind is not None:
            self.kind = akind
        if avalue is not None:
            self.value = avalue
        self.rank = arank
        # rank is an internal gizmo (operator precedence);
        # it's used in reconstructing formula text.
        self.text = atext

    def __repr__(self):
        kind_text = okind_dict.get(self.kind, "?Unknown kind?")
        return "Operand(kind=%s, value=%r, text=%r)" \
            % (kind_text, self.value, self.text)

##
# <p>Represents an absolute or relative 3-dimensional reference to a box
# of one or more cells.<br />
# -- New in version 0.6.0
# </p>
#
# <p>The <i>coords</i> attribute is a tuple of the form:<br />
# (shtxlo, shtxhi, rowxlo, rowxhi, colxlo, colxhi)<br />
# where 0 <= thingxlo <= thingx < thingxhi.<br />
# Note that it is quite possible to have thingx > nthings; for example
# Print_Titles could have colxhi == 256 and/or rowxhi == 65536
# irrespective of how many columns/rows are actually used in the worksheet.
# The caller will need to decide how to handle this situation.
# Keyword: IndexError :-)
# </p>
#
# <p>The components of the coords attribute are also available as individual
# attributes: shtxlo, shtxhi, rowxlo, rowxhi, colxlo, and colxhi.</p>
#
# <p>The <i>relflags</i> attribute is a 6-tuple of flags which indicate whether
# the corresponding (sheet|row|col)(lo|hi) is relative (1) or absolute (0).<br>
# Note that there is necessarily no information available as to what cell(s)
# the reference could possibly be relative to. The caller must decide what if
# any use to make of oREL operands. Note also that a partially relative
# reference may well be a typo.
# For example, define name A1Z10 as $a$1:$z10 (missing $ after z)
# while the cursor is on cell Sheet3!A27.<br>
# The resulting Ref3D instance will have coords = (2, 3, 0, -16, 0, 26)
# and relflags = (0, 0, 0, 1, 0, 0).<br>
# So far, only one possibility of a sheet-relative component in
# a reference has been noticed: a 2D reference located in the "current sheet".
# <br /> This will appear as coords = (0, 1, ...) and relflags = (1, 1, ...).

class Ref3D(tuple):

    def __init__(self, atuple):
        self.coords = atuple[0:6]
        self.relflags = atuple[6:12]
        if not self.relflags:
            self.relflags = (0, 0, 0, 0, 0, 0)
        (self.shtxlo, self.shtxhi,
        self.rowxlo, self.rowxhi,
        self.colxlo, self.colxhi) = self.coords

    def __repr__(self):
        if not self.relflags or self.relflags == (0, 0, 0, 0, 0, 0):
            return "Ref3D(coords=%r)" % (self.coords, )
        else:
            return "Ref3D(coords=%r, relflags=%r)" \
                % (self.coords, self.relflags)

tAdd = 0x03
tSub = 0x04
tMul = 0x05
tDiv = 0x06
tPower = 0x07
tConcat = 0x08
tLT, tLE, tEQ, tGE, tGT, tNE = range(0x09, 0x0F)

import operator as opr

def nop(x):
    return x

def _opr_pow(x, y): return x ** y

def _opr_lt(x, y): return x <  y
def _opr_le(x, y): return x <= y
def _opr_eq(x, y): return x == y
def _opr_ge(x, y): return x >= y
def _opr_gt(x, y): return x >  y
def _opr_ne(x, y): return x != y

def num2strg(num):
    """Attempt to emulate Excel's default conversion
       from number to string.
    """
    s = str(num)
    if s.endswith(".0"):
        s = s[:-2]
    return s

_arith_argdict = {oNUM: nop,     oSTRG: float}
_cmp_argdict =   {oNUM: nop,     oSTRG: nop}
# Seems no conversions done on relops; in Excel, "1" > 9 produces TRUE.
_strg_argdict =  {oNUM:num2strg, oSTRG:nop}
binop_rules = {
    tAdd:   (_arith_argdict, oNUM, opr.add,  30, '+'),
    tSub:   (_arith_argdict, oNUM, opr.sub,  30, '-'),
    tMul:   (_arith_argdict, oNUM, opr.mul,  40, '*'),
    tDiv:   (_arith_argdict, oNUM, opr.truediv,  40, '/'),
    tPower: (_arith_argdict, oNUM, _opr_pow, 50, '^',),
    tConcat:(_strg_argdict, oSTRG, opr.add,  20, '&'),
    tLT:    (_cmp_argdict, oBOOL, _opr_lt,   10, '<'),
    tLE:    (_cmp_argdict, oBOOL, _opr_le,   10, '<='),
    tEQ:    (_cmp_argdict, oBOOL, _opr_eq,   10, '='),
    tGE:    (_cmp_argdict, oBOOL, _opr_ge,   10, '>='),
    tGT:    (_cmp_argdict, oBOOL, _opr_gt,   10, '>'),
    tNE:    (_cmp_argdict, oBOOL, _opr_ne,   10, '<>'),
    }

unop_rules = {
    0x13: (lambda x: -x,        70, '-', ''), # unary minus
    0x12: (lambda x: x,         70, '+', ''), # unary plus
    0x14: (lambda x: x / 100.0, 60, '',  '%'),# percent
    }

LEAF_RANK = 90
FUNC_RANK = 90

STACK_ALARM_LEVEL = 5
STACK_PANIC_LEVEL = 10

def evaluate_name_formula(bk, nobj, namex, blah=0, level=0):
    if level > STACK_ALARM_LEVEL:
        blah = 1
    data = nobj.raw_formula
    fmlalen = nobj.basic_formula_len
    bv = bk.biff_version
    reldelta = 1 # All defined name formulas use "Method B" [OOo docs]
    if blah:
        print("::: evaluate_name_formula %r %r %d %d %r level=%d" \
            % (namex, nobj.name, fmlalen, bv, data, level), file=bk.logfile)
        hex_char_dump(data, 0, fmlalen, fout=bk.logfile)
    if level > STACK_PANIC_LEVEL:
        raise XLRDError("Excessive indirect references in NAME formula")
    sztab = szdict[bv]
    pos = 0
    stack = []
    any_rel = 0
    any_err = 0
    any_external = 0
    unk_opnd = Operand(oUNK, None)
    error_opnd = Operand(oERR, None)
    spush = stack.append

    def do_binop(opcd, stk):
        assert len(stk) >= 2
        bop = stk.pop()
        aop = stk.pop()
        argdict, result_kind, func, rank, sym = binop_rules[opcd]
        otext = ''.join([
            '('[:aop.rank < rank],
            aop.text,
            ')'[:aop.rank < rank],
            sym,
            '('[:bop.rank < rank],
            bop.text,
            ')'[:bop.rank < rank],
            ])
        resop = Operand(result_kind, None, rank, otext)
        try:
            bconv = argdict[bop.kind]
            aconv = argdict[aop.kind]
        except KeyError:
            stk.append(resop)
            return
        if bop.value is None or aop.value is None:
            stk.append(resop)
            return
        bval = bconv(bop.value)
        aval = aconv(aop.value)
        result = func(aval, bval)
        if result_kind == oBOOL:
            result = 1 if result else 0
        resop.value = result
        stk.append(resop)

    def do_unaryop(opcode, result_kind, stk):
        assert len(stk) >= 1
        aop = stk.pop()
        val = aop.value
        func, rank, sym1, sym2 = unop_rules[opcode]
        otext = ''.join([
            sym1,
            '('[:aop.rank < rank],
            aop.text,
            ')'[:aop.rank < rank],
            sym2,
            ])
        if val is not None:
            val = func(val)
        stk.append(Operand(result_kind, val, rank, otext))

    def not_in_name_formula(op_arg, oname_arg):
        msg = "ERROR *** Token 0x%02x (%s) found in NAME formula" \
              % (op_arg, oname_arg)
        raise FormulaError(msg)

    if fmlalen == 0:
        stack = [unk_opnd]

    while 0 <= pos < fmlalen:
        op = BYTES_ORD(data[pos])
        opcode = op & 0x1f
        optype = (op & 0x60) >> 5
        if optype:
            opx = opcode + 32
        else:
            opx = opcode
        oname = onames[opx] # + [" RVA"][optype]
        sz = sztab[opx]
        if blah:
            print("Pos:%d Op:0x%02x Name:t%s Sz:%d opcode:%02xh optype:%02xh" \
                % (pos, op, oname, sz, opcode, optype), file=bk.logfile)
            print("Stack =", stack, file=bk.logfile)
        if sz == -2:
            msg = 'ERROR *** Unexpected token 0x%02x ("%s"); biff_version=%d' \
                % (op, oname, bv)
            raise FormulaError(msg)
        if not optype:
            if 0x00 <= opcode <= 0x02: # unk_opnd, tExp, tTbl
                not_in_name_formula(op, oname)
            elif 0x03 <= opcode <= 0x0E:
                # Add, Sub, Mul, Div, Power
                # tConcat
                # tLT, ..., tNE
                do_binop(opcode, stack)
            elif opcode == 0x0F: # tIsect
                if blah: print("tIsect pre", stack, file=bk.logfile)
                assert len(stack) >= 2
                bop = stack.pop()
                aop = stack.pop()
                sym = ' '
                rank = 80 ########## check #######
                otext = ''.join([
                    '('[:aop.rank < rank],
                    aop.text,
                    ')'[:aop.rank < rank],
                    sym,
                    '('[:bop.rank < rank],
                    bop.text,
                    ')'[:bop.rank < rank],
                    ])
                res = Operand(oREF)
                res.text = otext
                if bop.kind == oERR or aop.kind == oERR:
                    res.kind = oERR
                elif bop.kind == oUNK or aop.kind == oUNK:
                    # This can happen with undefined
                    # (go search in the current sheet) labels.
                    # For example =Bob Sales
                    # Each label gets a NAME record with an empty formula (!)
                    # Evaluation of the tName token classifies it as oUNK
                    # res.kind = oREF
                    pass
                elif bop.kind == oREF == aop.kind:
                    if aop.value is not None and bop.value is not None:
                        assert len(aop.value) == 1
                        assert len(bop.value) == 1
                        coords = do_box_funcs(
                            tIsectFuncs, aop.value[0], bop.value[0])
                        res.value = [Ref3D(coords)]
                elif bop.kind == oREL == aop.kind:
                    res.kind = oREL
                    if aop.value is not None and bop.value is not None:
                        assert len(aop.value) == 1
                        assert len(bop.value) == 1
                        coords = do_box_funcs(
                            tIsectFuncs, aop.value[0], bop.value[0])
                        relfa = aop.value[0].relflags
                        relfb = bop.value[0].relflags
                        if relfa == relfb:
                            res.value = [Ref3D(coords + relfa)]
                else:
                    pass
                spush(res)
                if blah: print("tIsect post", stack, file=bk.logfile)
            elif opcode == 0x10: # tList
                if blah: print("tList pre", stack, file=bk.logfile)
                assert len(stack) >= 2
                bop = stack.pop()
                aop = stack.pop()
                sym = ','
                rank = 80 ########## check #######
                otext = ''.join([
                    '('[:aop.rank < rank],
                    aop.text,
                    ')'[:aop.rank < rank],
                    sym,
                    '('[:bop.rank < rank],
                    bop.text,
                    ')'[:bop.rank < rank],
                    ])
                res = Operand(oREF, None, rank, otext)
                if bop.kind == oERR or aop.kind == oERR:
                    res.kind = oERR
                elif bop.kind in (oREF, oREL) and aop.kind in (oREF, oREL):
                    res.kind = oREF
                    if aop.kind == oREL or bop.kind == oREL:
                        res.kind = oREL
                    if aop.value is not None and bop.value is not None:
                        assert len(aop.value) >= 1
                        assert len(bop.value) == 1
                        res.value = aop.value + bop.value
                else:
                    pass
                spush(res)
                if blah: print("tList post", stack, file=bk.logfile)
            elif opcode == 0x11: # tRange
                if blah: print("tRange pre", stack, file=bk.logfile)
                assert len(stack) >= 2
                bop = stack.pop()
                aop = stack.pop()
                sym = ':'
                rank = 80 ########## check #######
                otext = ''.join([
                    '('[:aop.rank < rank],
                    aop.text,
                    ')'[:aop.rank < rank],
                    sym,
                    '('[:bop.rank < rank],
                    bop.text,
                    ')'[:bop.rank < rank],
                    ])
                res = Operand(oREF, None, rank, otext)
                if bop.kind == oERR or aop.kind == oERR:
                    res = oERR
                elif bop.kind == oREF == aop.kind:
                    if aop.value is not None and bop.value is not None:
                        assert len(aop.value) == 1
                        assert len(bop.value) == 1
                        coords = do_box_funcs(
                            tRangeFuncs, aop.value[0], bop.value[0])
                        res.value = [Ref3D(coords)]
                elif bop.kind == oREL == aop.kind:
                    res.kind = oREL
                    if aop.value is not None and bop.value is not None:
                        assert len(aop.value) == 1
                        assert len(bop.value) == 1
                        coords = do_box_funcs(
                            tRangeFuncs, aop.value[0], bop.value[0])
                        relfa = aop.value[0].relflags
                        relfb = bop.value[0].relflags
                        if relfa == relfb:
                            res.value = [Ref3D(coords + relfa)]
                else:
                    pass
                spush(res)
                if blah: print("tRange post", stack, file=bk.logfile)
            elif 0x12 <= opcode <= 0x14: # tUplus, tUminus, tPercent
                do_unaryop(opcode, oNUM, stack)
            elif opcode == 0x15: # tParen
                # source cosmetics
                pass
            elif opcode == 0x16: # tMissArg
                spush(Operand(oMSNG, None, LEAF_RANK, ''))
            elif opcode == 0x17: # tStr
                if bv <= 70:
                    strg, newpos = unpack_string_update_pos(
                                        data, pos+1, bk.encoding, lenlen=1)
                else:
                    strg, newpos = unpack_unicode_update_pos(
                                        data, pos+1, lenlen=1)
                sz = newpos - pos
                if blah: print("   sz=%d strg=%r" % (sz, strg), file=bk.logfile)
                text = '"' + strg.replace('"', '""') + '"'
                spush(Operand(oSTRG, strg, LEAF_RANK, text))
            elif opcode == 0x18: # tExtended
                # new with BIFF 8
                assert bv >= 80
                # not in OOo docs
                raise FormulaError("tExtended token not implemented")
            elif opcode == 0x19: # tAttr
                subop, nc = unpack("<BH", data[pos+1:pos+4])
                subname = tAttrNames.get(subop, "??Unknown??")
                if subop == 0x04: # Choose
                    sz = nc * 2 + 6
                elif subop == 0x10: # Sum (single arg)
                    sz = 4
                    if blah: print("tAttrSum", stack, file=bk.logfile)
                    assert len(stack) >= 1
                    aop = stack[-1]
                    otext = 'SUM(%s)' % aop.text
                    stack[-1] = Operand(oNUM, None, FUNC_RANK, otext)
                else:
                    sz = 4
                if blah:
                    print("   subop=%02xh subname=t%s sz=%d nc=%02xh" \
                        % (subop, subname, sz, nc), file=bk.logfile)
            elif 0x1A <= opcode <= 0x1B: # tSheet, tEndSheet
                assert bv < 50
                raise FormulaError("tSheet & tEndsheet tokens not implemented")
            elif 0x1C <= opcode <= 0x1F: # tErr, tBool, tInt, tNum
                inx = opcode - 0x1C
                nb = [1, 1, 2, 8][inx]
                kind = [oERR, oBOOL, oNUM, oNUM][inx]
                value, = unpack("<" + "BBHd"[inx], data[pos+1:pos+1+nb])
                if inx == 2: # tInt
                    value = float(value)
                    text = str(value)
                elif inx == 3: # tNum
                    text = str(value)
                elif inx == 1: # tBool
                    text = ('FALSE', 'TRUE')[value]
                else:
                    text = '"' +error_text_from_code[value] + '"'
                spush(Operand(kind, value, LEAF_RANK, text))
            else:
                raise FormulaError("Unhandled opcode: 0x%02x" % opcode)
            if sz <= 0:
                raise FormulaError("Size not set for opcode 0x%02x" % opcode)
            pos += sz
            continue
        if opcode == 0x00: # tArray
            spush(unk_opnd)
        elif opcode == 0x01: # tFunc
            nb = 1 + int(bv >= 40)
            funcx = unpack("<" + " BH"[nb], data[pos+1:pos+1+nb])[0]
            func_attrs = func_defs.get(funcx, None)
            if not func_attrs:
                print("*** formula/tFunc unknown FuncID:%d" \
                      % funcx, file=bk.logfile)
                spush(unk_opnd)
            else:
                func_name, nargs = func_attrs[:2]
                if blah:
                    print("    FuncID=%d name=%s nargs=%d" \
                          % (funcx, func_name, nargs), file=bk.logfile)
                assert len(stack) >= nargs
                if nargs:
                    argtext = listsep.join([arg.text for arg in stack[-nargs:]])
                    otext = "%s(%s)" % (func_name, argtext)
                    del stack[-nargs:]
                else:
                    otext = func_name + "()"
                res = Operand(oUNK, None, FUNC_RANK, otext)
                spush(res)
        elif opcode == 0x02: #tFuncVar
            nb = 1 + int(bv >= 40)
            nargs, funcx = unpack("<B" + " BH"[nb], data[pos+1:pos+2+nb])
            prompt, nargs = divmod(nargs, 128)
            macro, funcx = divmod(funcx, 32768)
            if blah:
                print("   FuncID=%d nargs=%d macro=%d prompt=%d" \
                      % (funcx, nargs, macro, prompt), file=bk.logfile)
            func_attrs = func_defs.get(funcx, None)
            if not func_attrs:
                print("*** formula/tFuncVar unknown FuncID:%d" \
                      % funcx, file=bk.logfile)
                spush(unk_opnd)
            else:
                func_name, minargs, maxargs = func_attrs[:3]
                if blah:
                    print("    name: %r, min~max args: %d~%d" \
                        % (func_name, minargs, maxargs), file=bk.logfile)
                assert minargs <= nargs <= maxargs
                assert len(stack) >= nargs
                assert len(stack) >= nargs
                argtext = listsep.join([arg.text for arg in stack[-nargs:]])
                otext = "%s(%s)" % (func_name, argtext)
                res = Operand(oUNK, None, FUNC_RANK, otext)
                if funcx == 1: # IF
                    testarg = stack[-nargs]
                    if testarg.kind not in (oNUM, oBOOL):
                        if blah and testarg.kind != oUNK:
                            print("IF testarg kind?", file=bk.logfile)
                    elif testarg.value not in (0, 1):
                        if blah and testarg.value is not None:
                            print("IF testarg value?", file=bk.logfile)
                    else:
                        if nargs == 2 and not testarg.value:
                            # IF(FALSE, tv) => FALSE
                            res.kind, res.value = oBOOL, 0
                        else:
                            respos = -nargs + 2 - int(testarg.value)
                            chosen = stack[respos]
                            if chosen.kind == oMSNG:
                                res.kind, res.value = oNUM, 0
                            else:
                                res.kind, res.value = chosen.kind, chosen.value
                        if blah:
                            print("$$$$$$ IF => constant", file=bk.logfile)
                elif funcx == 100: # CHOOSE
                    testarg = stack[-nargs]
                    if testarg.kind == oNUM:
                        if 1 <= testarg.value < nargs:
                            chosen = stack[-nargs + int(testarg.value)]
                            if chosen.kind == oMSNG:
                                res.kind, res.value = oNUM, 0
                            else:
                                res.kind, res.value = chosen.kind, chosen.value
                del stack[-nargs:]
                spush(res)
        elif opcode == 0x03: #tName
            tgtnamex = unpack("<H", data[pos+1:pos+3])[0] - 1
            # Only change with BIFF version is number of trailing UNUSED bytes!
            if blah: print("   tgtnamex=%d" % tgtnamex, file=bk.logfile)
            tgtobj = bk.name_obj_list[tgtnamex]
            if not tgtobj.evaluated:
                ### recursive ###
                evaluate_name_formula(bk, tgtobj, tgtnamex, blah, level+1)
            if tgtobj.macro or tgtobj.binary \
            or tgtobj.any_err:
                if blah:
                    tgtobj.dump(
                        bk.logfile,
                        header="!!! tgtobj has problems!!!",
                        footer="-----------       --------",
                        )
                res = Operand(oUNK, None)
                any_err = any_err or tgtobj.macro or tgtobj.binary or tgtobj.any_err
                any_rel = any_rel or tgtobj.any_rel
            else:
                assert len(tgtobj.stack) == 1
                res = copy.deepcopy(tgtobj.stack[0])
            res.rank = LEAF_RANK
            if tgtobj.scope == -1:
                res.text = tgtobj.name
            else:
                res.text = "%s!%s" \
                           % (bk._sheet_names[tgtobj.scope], tgtobj.name)
            if blah:
                print("    tName: setting text to", repr(res.text), file=bk.logfile)
            spush(res)
        elif opcode == 0x04: # tRef
            # not_in_name_formula(op, oname)
            res = get_cell_addr(data, pos+1, bv, reldelta)
            if blah: print("  ", res, file=bk.logfile)
            rowx, colx, row_rel, col_rel = res
            shx1 = shx2 = 0 ####### N.B. relative to the CURRENT SHEET
            any_rel = 1
            coords = (shx1, shx2+1, rowx, rowx+1, colx, colx+1)
            if blah: print("   ", coords, file=bk.logfile)
            res = Operand(oUNK, None)
            if optype == 1:
                relflags = (1, 1, row_rel, row_rel, col_rel, col_rel)
                res = Operand(oREL, [Ref3D(coords + relflags)])
            spush(res)
        elif opcode == 0x05: # tArea
            # not_in_name_formula(op, oname)
            res1, res2 = get_cell_range_addr(data, pos+1, bv, reldelta)
            if blah: print("  ", res1, res2, file=bk.logfile)
            rowx1, colx1, row_rel1, col_rel1 = res1
            rowx2, colx2, row_rel2, col_rel2 = res2
            shx1 = shx2 = 0 ####### N.B. relative to the CURRENT SHEET
            any_rel = 1
            coords = (shx1, shx2+1, rowx1, rowx2+1, colx1, colx2+1)
            if blah: print("   ", coords, file=bk.logfile)
            res = Operand(oUNK, None)
            if optype == 1:
                relflags = (1, 1, row_rel1, row_rel2, col_rel1, col_rel2)
                res = Operand(oREL, [Ref3D(coords + relflags)])
            spush(res)
        elif opcode == 0x06: # tMemArea
            not_in_name_formula(op, oname)
        elif opcode == 0x09: # tMemFunc
            nb = unpack("<H", data[pos+1:pos+3])[0]
            if blah: print("  %d bytes of cell ref formula" % nb, file=bk.logfile)
            # no effect on stack
        elif opcode == 0x0C: #tRefN
            not_in_name_formula(op, oname)
            # res = get_cell_addr(data, pos+1, bv, reldelta=1)
            # # note *ALL* tRefN usage has signed offset for relative addresses
            # any_rel = 1
            # if blah: print >> bk.logfile, "   ", res
            # spush(res)
        elif opcode == 0x0D: #tAreaN
            not_in_name_formula(op, oname)
            # res = get_cell_range_addr(data, pos+1, bv, reldelta=1)
            # # note *ALL* tAreaN usage has signed offset for relative addresses
            # any_rel = 1
            # if blah: print >> bk.logfile, "   ", res
        elif opcode == 0x1A: # tRef3d
            if bv >= 80:
                res = get_cell_addr(data, pos+3, bv, reldelta)
                refx = unpack("<H", data[pos+1:pos+3])[0]
                shx1, shx2 = get_externsheet_local_range(bk, refx, blah)
            else:
                res = get_cell_addr(data, pos+15, bv, reldelta)
                raw_extshtx, raw_shx1, raw_shx2 = \
                             unpack("<hxxxxxxxxhh", data[pos+1:pos+15])
                if blah:
                    print("tRef3d", raw_extshtx, raw_shx1, raw_shx2, file=bk.logfile)
                shx1, shx2 = get_externsheet_local_range_b57(
                                bk, raw_extshtx, raw_shx1, raw_shx2, blah)
            rowx, colx, row_rel, col_rel = res
            is_rel = row_rel or col_rel
            any_rel = any_rel or is_rel
            coords = (shx1, shx2+1, rowx, rowx+1, colx, colx+1)
            any_err |= shx1 < -1
            if blah: print("   ", coords, file=bk.logfile)
            res = Operand(oUNK, None)
            if is_rel:
                relflags = (0, 0, row_rel, row_rel, col_rel, col_rel)
                ref3d = Ref3D(coords + relflags)
                res.kind = oREL
                res.text = rangename3drel(bk, ref3d, r1c1=1)
            else:
                ref3d = Ref3D(coords)
                res.kind = oREF
                res.text = rangename3d(bk, ref3d)
            res.rank = LEAF_RANK
            if optype == 1:
                res.value = [ref3d]
            spush(res)
        elif opcode == 0x1B: # tArea3d
            if bv >= 80:
                res1, res2 = get_cell_range_addr(data, pos+3, bv, reldelta)
                refx = unpack("<H", data[pos+1:pos+3])[0]
                shx1, shx2 = get_externsheet_local_range(bk, refx, blah)
            else:
                res1, res2 = get_cell_range_addr(data, pos+15, bv, reldelta)
                raw_extshtx, raw_shx1, raw_shx2 = \
                             unpack("<hxxxxxxxxhh", data[pos+1:pos+15])
                if blah:
                    print("tArea3d", raw_extshtx, raw_shx1, raw_shx2, file=bk.logfile)
                shx1, shx2 = get_externsheet_local_range_b57(
                                bk, raw_extshtx, raw_shx1, raw_shx2, blah)
            any_err |= shx1 < -1
            rowx1, colx1, row_rel1, col_rel1 = res1
            rowx2, colx2, row_rel2, col_rel2 = res2
            is_rel = row_rel1 or col_rel1 or row_rel2 or col_rel2
            any_rel = any_rel or is_rel
            coords = (shx1, shx2+1, rowx1, rowx2+1, colx1, colx2+1)
            if blah: print("   ", coords, file=bk.logfile)
            res = Operand(oUNK, None)
            if is_rel:
                relflags = (0, 0, row_rel1, row_rel2, col_rel1, col_rel2)
                ref3d = Ref3D(coords + relflags)
                res.kind = oREL
                res.text = rangename3drel(bk, ref3d, r1c1=1)
            else:
                ref3d = Ref3D(coords)
                res.kind = oREF
                res.text = rangename3d(bk, ref3d)
            res.rank = LEAF_RANK
            if optype == 1:
                res.value = [ref3d]

            spush(res)
        elif opcode == 0x19: # tNameX
            dodgy = 0
            res = Operand(oUNK, None)
            if bv >= 80:
                refx, tgtnamex = unpack("<HH", data[pos+1:pos+5])
                tgtnamex -= 1
                origrefx = refx
            else:
                refx, tgtnamex = unpack("<hxxxxxxxxH", data[pos+1:pos+13])
                tgtnamex -= 1
                origrefx = refx
                if refx > 0:
                    refx -= 1
                elif refx < 0:
                    refx = -refx - 1
                else:
                    dodgy = 1
            if blah:
                print("   origrefx=%d refx=%d tgtnamex=%d dodgy=%d" \
                    % (origrefx, refx, tgtnamex, dodgy), file=bk.logfile)
            if tgtnamex == namex:
                if blah: print("!!!! Self-referential !!!!", file=bk.logfile)
                dodgy = any_err = 1
            if not dodgy:
                if bv >= 80:
                    shx1, shx2 = get_externsheet_local_range(bk, refx, blah)
                elif origrefx > 0:
                    shx1, shx2 = (-4, -4) # external ref
                else:
                    exty = bk._externsheet_type_b57[refx]
                    if exty == 4: # non-specific sheet in own doc't
                        shx1, shx2 = (-1, -1) # internal, any sheet
                    else:
                        shx1, shx2 = (-666, -666)
            if dodgy or shx1 < -1:
                otext = "<<Name #%d in external(?) file #%d>>" \
                        % (tgtnamex, origrefx)
                res = Operand(oUNK, None, LEAF_RANK, otext)
            else:
                tgtobj = bk.name_obj_list[tgtnamex]
                if not tgtobj.evaluated:
                    ### recursive ###
                    evaluate_name_formula(bk, tgtobj, tgtnamex, blah, level+1)
                if tgtobj.macro or tgtobj.binary \
                or tgtobj.any_err:
                    if blah:
                        tgtobj.dump(
                            bk.logfile,
                            header="!!! bad tgtobj !!!",
                            footer="------------------",
                            )
                    res = Operand(oUNK, None)
                    any_err = any_err or tgtobj.macro or tgtobj.binary or tgtobj.any_err
                    any_rel = any_rel or tgtobj.any_rel
                else:
                    assert len(tgtobj.stack) == 1
                    res = copy.deepcopy(tgtobj.stack[0])
                res.rank = LEAF_RANK
                if tgtobj.scope == -1:
                    res.text = tgtobj.name
                else:
                    res.text = "%s!%s" \
                               % (bk._sheet_names[tgtobj.scope], tgtobj.name)
                if blah:
                    print("    tNameX: setting text to", repr(res.text), file=bk.logfile)
            spush(res)
        elif opcode in error_opcodes:
            any_err = 1
            spush(error_opnd)
        else:
            if blah:
                print("FORMULA: /// Not handled yet: t" + oname, file=bk.logfile)
            any_err = 1
        if sz <= 0:
            raise FormulaError("Fatal: token size is not positive")
        pos += sz
    any_rel = not not any_rel
    if blah:
        fprintf(bk.logfile, "End of formula. level=%d any_rel=%d any_err=%d stack=%r\n",
            level, not not any_rel, any_err, stack)
        if len(stack) >= 2:
            print("*** Stack has unprocessed args", file=bk.logfile)
        print(file=bk.logfile)
    nobj.stack = stack
    if len(stack) != 1:
        nobj.result = None
    else:
        nobj.result = stack[0]
    nobj.any_rel = any_rel
    nobj.any_err = any_err
    nobj.any_external = any_external
    nobj.evaluated = 1

#### under construction #############################################################################
def decompile_formula(bk, fmla, fmlalen,
    fmlatype=None, browx=None, bcolx=None,
    blah=0, level=0, r1c1=0):
    if level > STACK_ALARM_LEVEL:
        blah = 1
    reldelta = fmlatype in (FMLA_TYPE_SHARED, FMLA_TYPE_NAME, FMLA_TYPE_COND_FMT, FMLA_TYPE_DATA_VAL)
    data = fmla
    bv = bk.biff_version
    if blah:
        print("::: decompile_formula len=%d fmlatype=%r browx=%r bcolx=%r reldelta=%d %r level=%d" \
            % (fmlalen, fmlatype, browx, bcolx, reldelta, data, level), file=bk.logfile)
        hex_char_dump(data, 0, fmlalen, fout=bk.logfile)
    if level > STACK_PANIC_LEVEL:
        raise XLRDError("Excessive indirect references in formula")
    sztab = szdict[bv]
    pos = 0
    stack = []
    any_rel = 0
    any_err = 0
    any_external = 0
    unk_opnd = Operand(oUNK, None)
    error_opnd = Operand(oERR, None)
    spush = stack.append

    def do_binop(opcd, stk):
        assert len(stk) >= 2
        bop = stk.pop()
        aop = stk.pop()
        argdict, result_kind, func, rank, sym = binop_rules[opcd]
        otext = ''.join([
            '('[:aop.rank < rank],
            aop.text,
            ')'[:aop.rank < rank],
            sym,
            '('[:bop.rank < rank],
            bop.text,
            ')'[:bop.rank < rank],
            ])
        resop = Operand(result_kind, None, rank, otext)
        stk.append(resop)

    def do_unaryop(opcode, result_kind, stk):
        assert len(stk) >= 1
        aop = stk.pop()
        func, rank, sym1, sym2 = unop_rules[opcode]
        otext = ''.join([
            sym1,
            '('[:aop.rank < rank],
            aop.text,
            ')'[:aop.rank < rank],
            sym2,
            ])
        stk.append(Operand(result_kind, None, rank, otext))

    def unexpected_opcode(op_arg, oname_arg):
        msg = "ERROR *** Unexpected token 0x%02x (%s) found in formula type %s" \
              % (op_arg, oname_arg, FMLA_TYPEDESCR_MAP[fmlatype])
        print(msg, file=bk.logfile)
        # raise FormulaError(msg)

    if fmlalen == 0:
        stack = [unk_opnd]

    while 0 <= pos < fmlalen:
        op = BYTES_ORD(data[pos])
        opcode = op & 0x1f
        optype = (op & 0x60) >> 5
        if optype:
            opx = opcode + 32
        else:
            opx = opcode
        oname = onames[opx] # + [" RVA"][optype]
        sz = sztab[opx]
        if blah:
            print("Pos:%d Op:0x%02x opname:t%s Sz:%d opcode:%02xh optype:%02xh" \
                % (pos, op, oname, sz, opcode, optype), file=bk.logfile)
            print("Stack =", stack, file=bk.logfile)
        if sz == -2:
            msg = 'ERROR *** Unexpected token 0x%02x ("%s"); biff_version=%d' \
                % (op, oname, bv)
            raise FormulaError(msg)
        if _TOKEN_NOT_ALLOWED(opx, 0) & fmlatype:
            unexpected_opcode(op, oname)
        if not optype:
            if opcode <= 0x01: # tExp
                if bv >= 30:
                    fmt = '<x2H'
                else:
                    fmt = '<xHB'
                assert pos == 0 and fmlalen == sz and not stack
                rowx, colx = unpack(fmt, data)
                text = "SHARED FMLA at rowx=%d colx=%d" % (rowx, colx)
                spush(Operand(oUNK, None, LEAF_RANK, text))
                if not fmlatype & (FMLA_TYPE_CELL | FMLA_TYPE_ARRAY):
                    unexpected_opcode(op, oname)
            elif 0x03 <= opcode <= 0x0E:
                # Add, Sub, Mul, Div, Power
                # tConcat
                # tLT, ..., tNE
                do_binop(opcode, stack)
            elif opcode == 0x0F: # tIsect
                if blah: print("tIsect pre", stack, file=bk.logfile)
                assert len(stack) >= 2
                bop = stack.pop()
                aop = stack.pop()
                sym = ' '
                rank = 80 ########## check #######
                otext = ''.join([
                    '('[:aop.rank < rank],
                    aop.text,
                    ')'[:aop.rank < rank],
                    sym,
                    '('[:bop.rank < rank],
                    bop.text,
                    ')'[:bop.rank < rank],
                    ])
                res = Operand(oREF)
                res.text = otext
                if bop.kind == oERR or aop.kind == oERR:
                    res.kind = oERR
                elif bop.kind == oUNK or aop.kind == oUNK:
                    # This can happen with undefined
                    # (go search in the current sheet) labels.
                    # For example =Bob Sales
                    # Each label gets a NAME record with an empty formula (!)
                    # Evaluation of the tName token classifies it as oUNK
                    # res.kind = oREF
                    pass
                elif bop.kind == oREF == aop.kind:
                    pass
                elif bop.kind == oREL == aop.kind:
                    res.kind = oREL
                else:
                    pass
                spush(res)
                if blah: print("tIsect post", stack, file=bk.logfile)
            elif opcode == 0x10: # tList
                if blah: print("tList pre", stack, file=bk.logfile)
                assert len(stack) >= 2
                bop = stack.pop()
                aop = stack.pop()
                sym = ','
                rank = 80 ########## check #######
                otext = ''.join([
                    '('[:aop.rank < rank],
                    aop.text,
                    ')'[:aop.rank < rank],
                    sym,
                    '('[:bop.rank < rank],
                    bop.text,
                    ')'[:bop.rank < rank],
                    ])
                res = Operand(oREF, None, rank, otext)
                if bop.kind == oERR or aop.kind == oERR:
                    res.kind = oERR
                elif bop.kind in (oREF, oREL) and aop.kind in (oREF, oREL):
                    res.kind = oREF
                    if aop.kind == oREL or bop.kind == oREL:
                        res.kind = oREL
                else:
                    pass
                spush(res)
                if blah: print("tList post", stack, file=bk.logfile)
            elif opcode == 0x11: # tRange
                if blah: print("tRange pre", stack, file=bk.logfile)
                assert len(stack) >= 2
                bop = stack.pop()
                aop = stack.pop()
                sym = ':'
                rank = 80 ########## check #######
                otext = ''.join([
                    '('[:aop.rank < rank],
                    aop.text,
                    ')'[:aop.rank < rank],
                    sym,
                    '('[:bop.rank < rank],
                    bop.text,
                    ')'[:bop.rank < rank],
                    ])
                res = Operand(oREF, None, rank, otext)
                if bop.kind == oERR or aop.kind == oERR:
                    res = oERR
                elif bop.kind == oREF == aop.kind:
                    pass
                else:
                    pass
                spush(res)
                if blah: print("tRange post", stack, file=bk.logfile)
            elif 0x12 <= opcode <= 0x14: # tUplus, tUminus, tPercent
                do_unaryop(opcode, oNUM, stack)
            elif opcode == 0x15: # tParen
                # source cosmetics
                pass
            elif opcode == 0x16: # tMissArg
                spush(Operand(oMSNG, None, LEAF_RANK, ''))
            elif opcode == 0x17: # tStr
                if bv <= 70:
                    strg, newpos = unpack_string_update_pos(
                                        data, pos+1, bk.encoding, lenlen=1)
                else:
                    strg, newpos = unpack_unicode_update_pos(
                                        data, pos+1, lenlen=1)
                sz = newpos - pos
                if blah: print("   sz=%d strg=%r" % (sz, strg), file=bk.logfile)
                text = '"' + strg.replace('"', '""') + '"'
                spush(Operand(oSTRG, None, LEAF_RANK, text))
            elif opcode == 0x18: # tExtended
                # new with BIFF 8
                assert bv >= 80
                # not in OOo docs, don't even know how to determine its length
                raise FormulaError("tExtended token not implemented")
            elif opcode == 0x19: # tAttr
                subop, nc = unpack("<BH", data[pos+1:pos+4])
                subname = tAttrNames.get(subop, "??Unknown??")
                if subop == 0x04: # Choose
                    sz = nc * 2 + 6
                elif subop == 0x10: # Sum (single arg)
                    sz = 4
                    if blah: print("tAttrSum", stack, file=bk.logfile)
                    assert len(stack) >= 1
                    aop = stack[-1]
                    otext = 'SUM(%s)' % aop.text
                    stack[-1] = Operand(oNUM, None, FUNC_RANK, otext)
                else:
                    sz = 4
                if blah:
                    print("   subop=%02xh subname=t%s sz=%d nc=%02xh" \
                        % (subop, subname, sz, nc), file=bk.logfile)
            elif 0x1A <= opcode <= 0x1B: # tSheet, tEndSheet
                assert bv < 50
                raise FormulaError("tSheet & tEndsheet tokens not implemented")
            elif 0x1C <= opcode <= 0x1F: # tErr, tBool, tInt, tNum
                inx = opcode - 0x1C
                nb = [1, 1, 2, 8][inx]
                kind = [oERR, oBOOL, oNUM, oNUM][inx]
                value, = unpack("<" + "BBHd"[inx], data[pos+1:pos+1+nb])
                if inx == 2: # tInt
                    value = float(value)
                    text = str(value)
                elif inx == 3: # tNum
                    text = str(value)
                elif inx == 1: # tBool
                    text = ('FALSE', 'TRUE')[value]
                else:
                    text = '"' +error_text_from_code[value] + '"'
                spush(Operand(kind, None, LEAF_RANK, text))
            else:
                raise FormulaError("Unhandled opcode: 0x%02x" % opcode)
            if sz <= 0:
                raise FormulaError("Size not set for opcode 0x%02x" % opcode)
            pos += sz
            continue
        if opcode == 0x00: # tArray
            spush(unk_opnd)
        elif opcode == 0x01: # tFunc
            nb = 1 + int(bv >= 40)
            funcx = unpack("<" + " BH"[nb], data[pos+1:pos+1+nb])[0]
            func_attrs = func_defs.get(funcx, None)
            if not func_attrs:
                print("*** formula/tFunc unknown FuncID:%d" % funcx, file=bk.logfile)
                spush(unk_opnd)
            else:
                func_name, nargs = func_attrs[:2]
                if blah:
                    print("    FuncID=%d name=%s nargs=%d" \
                          % (funcx, func_name, nargs), file=bk.logfile)
                assert len(stack) >= nargs
                if nargs:
                    argtext = listsep.join([arg.text for arg in stack[-nargs:]])
                    otext = "%s(%s)" % (func_name, argtext)
                    del stack[-nargs:]
                else:
                    otext = func_name + "()"
                res = Operand(oUNK, None, FUNC_RANK, otext)
                spush(res)
        elif opcode == 0x02: #tFuncVar
            nb = 1 + int(bv >= 40)
            nargs, funcx = unpack("<B" + " BH"[nb], data[pos+1:pos+2+nb])
            prompt, nargs = divmod(nargs, 128)
            macro, funcx = divmod(funcx, 32768)
            if blah:
                print("   FuncID=%d nargs=%d macro=%d prompt=%d" \
                      % (funcx, nargs, macro, prompt), file=bk.logfile)
            #### TODO #### if funcx == 255: # call add-in function
            if funcx == 255:
                func_attrs = ("CALL_ADDIN", 1, 30)
            else:
                func_attrs = func_defs.get(funcx, None)
            if not func_attrs:
                print("*** formula/tFuncVar unknown FuncID:%d" \
                      % funcx, file=bk.logfile)
                spush(unk_opnd)
            else:
                func_name, minargs, maxargs = func_attrs[:3]
                if blah:
                    print("    name: %r, min~max args: %d~%d" \
                        % (func_name, minargs, maxargs), file=bk.logfile)
                assert minargs <= nargs <= maxargs
                assert len(stack) >= nargs
                assert len(stack) >= nargs
                argtext = listsep.join([arg.text for arg in stack[-nargs:]])
                otext = "%s(%s)" % (func_name, argtext)
                res = Operand(oUNK, None, FUNC_RANK, otext)
                del stack[-nargs:]
                spush(res)
        elif opcode == 0x03: #tName
            tgtnamex = unpack("<H", data[pos+1:pos+3])[0] - 1
            # Only change with BIFF version is number of trailing UNUSED bytes!
            if blah: print("   tgtnamex=%d" % tgtnamex, file=bk.logfile)
            tgtobj = bk.name_obj_list[tgtnamex]
            if tgtobj.scope == -1:
                otext = tgtobj.name
            else:
                otext = "%s!%s" % (bk._sheet_names[tgtobj.scope], tgtobj.name)
            if blah:
                print("    tName: setting text to", repr(otext), file=bk.logfile)
            res = Operand(oUNK, None, LEAF_RANK, otext)
            spush(res)
        elif opcode == 0x04: # tRef
            res = get_cell_addr(data, pos+1, bv, reldelta, browx, bcolx)
            if blah: print("  ", res, file=bk.logfile)
            rowx, colx, row_rel, col_rel = res
            is_rel = row_rel or col_rel
            if is_rel:
                okind = oREL
            else:
                okind = oREF
            otext = cellnamerel(rowx, colx, row_rel, col_rel, browx, bcolx, r1c1)
            res = Operand(okind, None, LEAF_RANK, otext)
            spush(res)
        elif opcode == 0x05: # tArea
            res1, res2 = get_cell_range_addr(
                            data, pos+1, bv, reldelta, browx, bcolx)
            if blah: print("  ", res1, res2, file=bk.logfile)
            rowx1, colx1, row_rel1, col_rel1 = res1
            rowx2, colx2, row_rel2, col_rel2 = res2
            coords = (rowx1, rowx2+1, colx1, colx2+1)
            relflags = (row_rel1, row_rel2, col_rel1, col_rel2)
            if sum(relflags):  # relative
                okind = oREL
            else:
                okind = oREF
            if blah: print("   ", coords, relflags, file=bk.logfile)
            otext = rangename2drel(coords, relflags, browx, bcolx, r1c1)
            res = Operand(okind, None, LEAF_RANK, otext)
            spush(res)
        elif opcode == 0x06: # tMemArea
            not_in_name_formula(op, oname)
        elif opcode == 0x09: # tMemFunc
            nb = unpack("<H", data[pos+1:pos+3])[0]
            if blah: print("  %d bytes of cell ref formula" % nb, file=bk.logfile)
            # no effect on stack
        elif opcode == 0x0C: #tRefN
            res = get_cell_addr(data, pos+1, bv, reldelta, browx, bcolx)
            # note *ALL* tRefN usage has signed offset for relative addresses
            any_rel = 1
            if blah: print("   ", res, file=bk.logfile)
            rowx, colx, row_rel, col_rel = res
            is_rel = row_rel or col_rel
            if is_rel:
                okind = oREL
            else:
                okind = oREF
            otext = cellnamerel(rowx, colx, row_rel, col_rel, browx, bcolx, r1c1)
            res = Operand(okind, None, LEAF_RANK, otext)
            spush(res)
        elif opcode == 0x0D: #tAreaN
            # res = get_cell_range_addr(data, pos+1, bv, reldelta, browx, bcolx)
            # # note *ALL* tAreaN usage has signed offset for relative addresses
            # any_rel = 1
            # if blah: print >> bk.logfile, "   ", res
            res1, res2 = get_cell_range_addr(
                            data, pos+1, bv, reldelta, browx, bcolx)
            if blah: print("  ", res1, res2, file=bk.logfile)
            rowx1, colx1, row_rel1, col_rel1 = res1
            rowx2, colx2, row_rel2, col_rel2 = res2
            coords = (rowx1, rowx2+1, colx1, colx2+1)
            relflags = (row_rel1, row_rel2, col_rel1, col_rel2)
            if sum(relflags):  # relative
                okind = oREL
            else:
                okind = oREF
            if blah: print("   ", coords, relflags, file=bk.logfile)
            otext = rangename2drel(coords, relflags, browx, bcolx, r1c1)
            res = Operand(okind, None, LEAF_RANK, otext)
            spush(res)
        elif opcode == 0x1A: # tRef3d
            if bv >= 80:
                res = get_cell_addr(data, pos+3, bv, reldelta, browx, bcolx)
                refx = unpack("<H", data[pos+1:pos+3])[0]
                shx1, shx2 = get_externsheet_local_range(bk, refx, blah)
            else:
                res = get_cell_addr(data, pos+15, bv, reldelta, browx, bcolx)
                raw_extshtx, raw_shx1, raw_shx2 = \
                             unpack("<hxxxxxxxxhh", data[pos+1:pos+15])
                if blah:
                    print("tRef3d", raw_extshtx, raw_shx1, raw_shx2, file=bk.logfile)
                shx1, shx2 = get_externsheet_local_range_b57(
                                bk, raw_extshtx, raw_shx1, raw_shx2, blah)
            rowx, colx, row_rel, col_rel = res
            is_rel = row_rel or col_rel
            any_rel = any_rel or is_rel
            coords = (shx1, shx2+1, rowx, rowx+1, colx, colx+1)
            any_err |= shx1 < -1
            if blah: print("   ", coords, file=bk.logfile)
            res = Operand(oUNK, None)
            if is_rel:
                relflags = (0, 0, row_rel, row_rel, col_rel, col_rel)
                ref3d = Ref3D(coords + relflags)
                res.kind = oREL
                res.text = rangename3drel(bk, ref3d, browx, bcolx, r1c1)
            else:
                ref3d = Ref3D(coords)
                res.kind = oREF
                res.text = rangename3d(bk, ref3d)
            res.rank = LEAF_RANK
            res.value = None
            spush(res)
        elif opcode == 0x1B: # tArea3d
            if bv >= 80:
                res1, res2 = get_cell_range_addr(data, pos+3, bv, reldelta)
                refx = unpack("<H", data[pos+1:pos+3])[0]
                shx1, shx2 = get_externsheet_local_range(bk, refx, blah)
            else:
                res1, res2 = get_cell_range_addr(data, pos+15, bv, reldelta)
                raw_extshtx, raw_shx1, raw_shx2 = \
                             unpack("<hxxxxxxxxhh", data[pos+1:pos+15])
                if blah:
                    print("tArea3d", raw_extshtx, raw_shx1, raw_shx2, file=bk.logfile)
                shx1, shx2 = get_externsheet_local_range_b57(
                                bk, raw_extshtx, raw_shx1, raw_shx2, blah)
            any_err |= shx1 < -1
            rowx1, colx1, row_rel1, col_rel1 = res1
            rowx2, colx2, row_rel2, col_rel2 = res2
            is_rel = row_rel1 or col_rel1 or row_rel2 or col_rel2
            any_rel = any_rel or is_rel
            coords = (shx1, shx2+1, rowx1, rowx2+1, colx1, colx2+1)
            if blah: print("   ", coords, file=bk.logfile)
            res = Operand(oUNK, None)
            if is_rel:
                relflags = (0, 0, row_rel1, row_rel2, col_rel1, col_rel2)
                ref3d = Ref3D(coords + relflags)
                res.kind = oREL
                res.text = rangename3drel(bk, ref3d, browx, bcolx, r1c1)
            else:
                ref3d = Ref3D(coords)
                res.kind = oREF
                res.text = rangename3d(bk, ref3d)
            res.rank = LEAF_RANK
            spush(res)
        elif opcode == 0x19: # tNameX
            dodgy = 0
            res = Operand(oUNK, None)
            if bv >= 80:
                refx, tgtnamex = unpack("<HH", data[pos+1:pos+5])
                tgtnamex -= 1
                origrefx = refx
            else:
                refx, tgtnamex = unpack("<hxxxxxxxxH", data[pos+1:pos+13])
                tgtnamex -= 1
                origrefx = refx
                if refx > 0:
                    refx -= 1
                elif refx < 0:
                    refx = -refx - 1
                else:
                    dodgy = 1
            if blah:
                print("   origrefx=%d refx=%d tgtnamex=%d dodgy=%d" \
                    % (origrefx, refx, tgtnamex, dodgy), file=bk.logfile)
            # if tgtnamex == namex:
            #     if blah: print >> bk.logfile, "!!!! Self-referential !!!!"
            #     dodgy = any_err = 1
            if not dodgy:
                if bv >= 80:
                    shx1, shx2 = get_externsheet_local_range(bk, refx, blah)
                elif origrefx > 0:
                    shx1, shx2 = (-4, -4) # external ref
                else:
                    exty = bk._externsheet_type_b57[refx]
                    if exty == 4: # non-specific sheet in own doc't
                        shx1, shx2 = (-1, -1) # internal, any sheet
                    else:
                        shx1, shx2 = (-666, -666)
            okind = oUNK
            ovalue = None
            if shx1 == -5: # addin func name
                okind = oSTRG
                ovalue = bk.addin_func_names[tgtnamex]
                otext = '"' + ovalue.replace('"', '""') + '"'
            elif dodgy or shx1 < -1:
                otext = "<<Name #%d in external(?) file #%d>>" \
                        % (tgtnamex, origrefx)
            else:
                tgtobj = bk.name_obj_list[tgtnamex]
                if tgtobj.scope == -1:
                    otext = tgtobj.name
                else:
                    otext = "%s!%s" \
                            % (bk._sheet_names[tgtobj.scope], tgtobj.name)
                if blah:
                    print("    tNameX: setting text to", repr(res.text), file=bk.logfile)
            res = Operand(okind, ovalue, LEAF_RANK, otext)
            spush(res)
        elif opcode in error_opcodes:
            any_err = 1
            spush(error_opnd)
        else:
            if blah:
                print("FORMULA: /// Not handled yet: t" + oname, file=bk.logfile)
            any_err = 1
        if sz <= 0:
            raise FormulaError("Fatal: token size is not positive")
        pos += sz
    any_rel = not not any_rel
    if blah:
        print("End of formula. level=%d any_rel=%d any_err=%d stack=%r" % \
            (level, not not any_rel, any_err, stack), file=bk.logfile)
        if len(stack) >= 2:
            print("*** Stack has unprocessed args", file=bk.logfile)
        print(file=bk.logfile)

    if len(stack) != 1:
        result = None
    else:
        result = stack[0].text
    return result

#### under deconstruction ###
def dump_formula(bk, data, fmlalen, bv, reldelta, blah=0, isname=0):
    if blah:
        print("dump_formula", fmlalen, bv, len(data), file=bk.logfile)
        hex_char_dump(data, 0, fmlalen, fout=bk.logfile)
    assert bv >= 80 #### this function needs updating ####
    sztab = szdict[bv]
    pos = 0
    stack = []
    any_rel = 0
    any_err = 0
    spush = stack.append
    while 0 <= pos < fmlalen:
        op = BYTES_ORD(data[pos])
        opcode = op & 0x1f
        optype = (op & 0x60) >> 5
        if optype:
            opx = opcode + 32
        else:
            opx = opcode
        oname = onames[opx] # + [" RVA"][optype]

        sz = sztab[opx]
        if blah:
            print("Pos:%d Op:0x%02x Name:t%s Sz:%d opcode:%02xh optype:%02xh" \
                % (pos, op, oname, sz, opcode, optype), file=bk.logfile)
        if not optype:
            if 0x01 <= opcode <= 0x02: # tExp, tTbl
                # reference to a shared formula or table record
                rowx, colx = unpack("<HH", data[pos+1:pos+5])
                if blah: print("  ", (rowx, colx), file=bk.logfile)
            elif opcode == 0x10: # tList
                if blah: print("tList pre", stack, file=bk.logfile)
                assert len(stack) >= 2
                bop = stack.pop()
                aop = stack.pop()
                spush(aop + bop)
                if blah: print("tlist post", stack, file=bk.logfile)
            elif opcode == 0x11: # tRange
                if blah: print("tRange pre", stack, file=bk.logfile)
                assert len(stack) >= 2
                bop = stack.pop()
                aop = stack.pop()
                assert len(aop) == 1
                assert len(bop) == 1
                result = do_box_funcs(tRangeFuncs, aop[0], bop[0])
                spush(result)
                if blah: print("tRange post", stack, file=bk.logfile)
            elif opcode == 0x0F: # tIsect
                if blah: print("tIsect pre", stack, file=bk.logfile)
                assert len(stack) >= 2
                bop = stack.pop()
                aop = stack.pop()
                assert len(aop) == 1
                assert len(bop) == 1
                result = do_box_funcs(tIsectFuncs, aop[0], bop[0])
                spush(result)
                if blah: print("tIsect post", stack, file=bk.logfile)
            elif opcode == 0x19: # tAttr
                subop, nc = unpack("<BH", data[pos+1:pos+4])
                subname = tAttrNames.get(subop, "??Unknown??")
                if subop == 0x04: # Choose
                    sz = nc * 2 + 6
                else:
                    sz = 4
                if blah: print("   subop=%02xh subname=t%s sz=%d nc=%02xh" % (subop, subname, sz, nc), file=bk.logfile)
            elif opcode == 0x17: # tStr
                if bv <= 70:
                    nc = BYTES_ORD(data[pos+1])
                    strg = data[pos+2:pos+2+nc] # left in 8-bit encoding
                    sz = nc + 2
                else:
                    strg, newpos = unpack_unicode_update_pos(data, pos+1, lenlen=1)
                    sz = newpos - pos
                if blah: print("   sz=%d strg=%r" % (sz, strg), file=bk.logfile)
            else:
                if sz <= 0:
                    print("**** Dud size; exiting ****", file=bk.logfile)
                    return
            pos += sz
            continue
        if opcode == 0x00: # tArray
            pass
        elif opcode == 0x01: # tFunc
            nb = 1 + int(bv >= 40)
            funcx = unpack("<" + " BH"[nb], data[pos+1:pos+1+nb])
            if blah: print("   FuncID=%d" % funcx, file=bk.logfile)
        elif opcode == 0x02: #tFuncVar
            nb = 1 + int(bv >= 40)
            nargs, funcx = unpack("<B" + " BH"[nb], data[pos+1:pos+2+nb])
            prompt, nargs = divmod(nargs, 128)
            macro, funcx = divmod(funcx, 32768)
            if blah: print("   FuncID=%d nargs=%d macro=%d prompt=%d" % (funcx, nargs, macro, prompt), file=bk.logfile)
        elif opcode == 0x03: #tName
            namex = unpack("<H", data[pos+1:pos+3])
            # Only change with BIFF version is the number of trailing UNUSED bytes!!!
            if blah: print("   namex=%d" % namex, file=bk.logfile)
        elif opcode == 0x04: # tRef
            res = get_cell_addr(data, pos+1, bv, reldelta)
            if blah: print("  ", res, file=bk.logfile)
        elif opcode == 0x05: # tArea
            res = get_cell_range_addr(data, pos+1, bv, reldelta)
            if blah: print("  ", res, file=bk.logfile)
        elif opcode == 0x09: # tMemFunc
            nb = unpack("<H", data[pos+1:pos+3])[0]
            if blah: print("  %d bytes of cell ref formula" % nb, file=bk.logfile)
        elif opcode == 0x0C: #tRefN
            res = get_cell_addr(data, pos+1, bv, reldelta=1)
            # note *ALL* tRefN usage has signed offset for relative addresses
            any_rel = 1
            if blah: print("   ", res, file=bk.logfile)
        elif opcode == 0x0D: #tAreaN
            res = get_cell_range_addr(data, pos+1, bv, reldelta=1)
            # note *ALL* tAreaN usage has signed offset for relative addresses
            any_rel = 1
            if blah: print("   ", res, file=bk.logfile)
        elif opcode == 0x1A: # tRef3d
            refx = unpack("<H", data[pos+1:pos+3])[0]
            res = get_cell_addr(data, pos+3, bv, reldelta)
            if blah: print("  ", refx, res, file=bk.logfile)
            rowx, colx, row_rel, col_rel = res
            any_rel = any_rel or row_rel or col_rel
            shx1, shx2 = get_externsheet_local_range(bk, refx, blah)
            any_err |= shx1 < -1
            coords = (shx1, shx2+1, rowx, rowx+1, colx, colx+1)
            if blah: print("   ", coords, file=bk.logfile)
            if optype == 1: spush([coords])
        elif opcode == 0x1B: # tArea3d
            refx = unpack("<H", data[pos+1:pos+3])[0]
            res1, res2 = get_cell_range_addr(data, pos+3, bv, reldelta)
            if blah: print("  ", refx, res1, res2, file=bk.logfile)
            rowx1, colx1, row_rel1, col_rel1 = res1
            rowx2, colx2, row_rel2, col_rel2 = res2
            any_rel = any_rel or row_rel1 or col_rel1 or row_rel2 or col_rel2
            shx1, shx2 = get_externsheet_local_range(bk, refx, blah)
            any_err |= shx1 < -1
            coords = (shx1, shx2+1, rowx1, rowx2+1, colx1, colx2+1)
            if blah: print("   ", coords, file=bk.logfile)
            if optype == 1: spush([coords])
        elif opcode == 0x19: # tNameX
            refx, namex = unpack("<HH", data[pos+1:pos+5])
            if blah: print("   refx=%d namex=%d" % (refx, namex), file=bk.logfile)
        elif opcode in error_opcodes:
            any_err = 1
        else:
            if blah: print("FORMULA: /// Not handled yet: t" + oname, file=bk.logfile)
            any_err = 1
        if sz <= 0:
            print("**** Dud size; exiting ****", file=bk.logfile)
            return
        pos += sz
    if blah:
        print("End of formula. any_rel=%d any_err=%d stack=%r" % \
            (not not any_rel, any_err, stack), file=bk.logfile)
        if len(stack) >= 2:
            print("*** Stack has unprocessed args", file=bk.logfile)

# === Some helper functions for displaying cell references ===

# I'm aware of only one possibility of a sheet-relative component in
# a reference: a 2D reference located in the "current sheet".
# xlrd stores this internally with bounds of (0, 1, ...) and
# relative flags of (1, 1, ...). These functions display the
# sheet component as empty, just like Excel etc.

def rownamerel(rowx, rowxrel, browx=None, r1c1=0):
    # if no base rowx is provided, we have to return r1c1
    if browx is None:
        r1c1 = True
    if not rowxrel:
        if r1c1:
            return "R%d" % (rowx+1)
        return "$%d" % (rowx+1)
    if r1c1:
        if rowx:
            return "R[%d]" % rowx
        return "R"
    return "%d" % ((browx + rowx) % 65536 + 1)

def colnamerel(colx, colxrel, bcolx=None, r1c1=0):
    # if no base colx is provided, we have to return r1c1
    if bcolx is None:
        r1c1 = True
    if not colxrel:
        if r1c1:
            return "C%d" % (colx + 1)
        return "$" + colname(colx)
    if r1c1:
        if colx:
            return "C[%d]" % colx
        return "C"
    return colname((bcolx + colx) % 256)

##
# Utility function: (5, 7) => 'H6'
def cellname(rowx, colx):
    """ (5, 7) => 'H6' """
    return "%s%d" % (colname(colx), rowx+1)

##
# Utility function: (5, 7) => '$H$6'
def cellnameabs(rowx, colx, r1c1=0):
    """ (5, 7) => '$H$6' or 'R8C6'"""
    if r1c1:
        return "R%dC%d" % (rowx+1, colx+1)
    return "$%s$%d" % (colname(colx), rowx+1)

def cellnamerel(rowx, colx, rowxrel, colxrel, browx=None, bcolx=None, r1c1=0):
    if not rowxrel and not colxrel:
        return cellnameabs(rowx, colx, r1c1)
    if (rowxrel and browx is None) or (colxrel and bcolx is None):
        # must flip the whole cell into R1C1 mode
        r1c1 = True
    c = colnamerel(colx, colxrel, bcolx, r1c1)
    r = rownamerel(rowx, rowxrel, browx, r1c1)
    if r1c1:
        return r + c
    return c + r

##
# Utility function: 7 => 'H', 27 => 'AB'
def colname(colx):
    """ 7 => 'H', 27 => 'AB' """
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if colx <= 25:
        return alphabet[colx]
    else:
        xdiv26, xmod26 = divmod(colx, 26)
        return alphabet[xdiv26 - 1] + alphabet[xmod26]

def rangename2d(rlo, rhi, clo, chi, r1c1=0):
    """ (5, 20, 7, 10) => '$H$6:$J$20' """
    if r1c1:
        return
    if rhi == rlo+1 and chi == clo+1:
        return cellnameabs(rlo, clo, r1c1)
    return "%s:%s" % (cellnameabs(rlo, clo, r1c1), cellnameabs(rhi-1, chi-1, r1c1))

def rangename2drel(rlo_rhi_clo_chi, rlorel_rhirel_clorel_chirel, browx=None, bcolx=None, r1c1=0):
    rlo, rhi, clo, chi = rlo_rhi_clo_chi
    rlorel, rhirel, clorel, chirel = rlorel_rhirel_clorel_chirel
    if (rlorel or rhirel) and browx is None:
        r1c1 = True
    if (clorel or chirel) and bcolx is None:
        r1c1 = True
    return "%s:%s" % (
        cellnamerel(rlo,   clo,   rlorel, clorel, browx, bcolx, r1c1),
        cellnamerel(rhi-1, chi-1, rhirel, chirel, browx, bcolx, r1c1)
        )
##
# Utility function:
# <br /> Ref3D((1, 4, 5, 20, 7, 10)) => 'Sheet2:Sheet3!$H$6:$J$20'
def rangename3d(book, ref3d):
    """ Ref3D(1, 4, 5, 20, 7, 10) => 'Sheet2:Sheet3!$H$6:$J$20'
        (assuming Excel's default sheetnames) """
    coords = ref3d.coords
    return "%s!%s" % (
        sheetrange(book, *coords[:2]),
        rangename2d(*coords[2:6]))

##
# Utility function:
# <br /> Ref3D(coords=(0, 1, -32, -22, -13, 13), relflags=(0, 0, 1, 1, 1, 1))
# R1C1 mode => 'Sheet1!R[-32]C[-13]:R[-23]C[12]'
# A1 mode => depends on base cell (browx, bcolx)
def rangename3drel(book, ref3d, browx=None, bcolx=None, r1c1=0):
    coords = ref3d.coords
    relflags = ref3d.relflags
    shdesc = sheetrangerel(book, coords[:2], relflags[:2])
    rngdesc = rangename2drel(coords[2:6], relflags[2:6], browx, bcolx, r1c1)
    if not shdesc:
        return rngdesc
    return "%s!%s" % (shdesc, rngdesc)

def quotedsheetname(shnames, shx):
    if shx >= 0:
        shname = shnames[shx]
    else:
        shname = {
            -1: "?internal; any sheet?",
            -2: "internal; deleted sheet",
            -3: "internal; macro sheet",
            -4: "<<external>>",
            }.get(shx, "?error %d?" % shx)
    if "'" in shname:
        return "'" + shname.replace("'", "''") + "'"
    if " " in shname:
        return "'" + shname + "'"
    return shname

def sheetrange(book, slo, shi):
    shnames = book.sheet_names()
    shdesc = quotedsheetname(shnames, slo)
    if slo != shi-1:
        shdesc += ":" + quotedsheetname(shnames, shi-1)
    return shdesc

def sheetrangerel(book, srange, srangerel):
    slo, shi = srange
    slorel, shirel = srangerel
    if not slorel and not shirel:
        return sheetrange(book, slo, shi)
    assert (slo == 0 == shi-1) and slorel and shirel
    return ""

# ==============================================================

########NEW FILE########
__FILENAME__ = info
__VERSION__ = "0.9.3dev"

########NEW FILE########
__FILENAME__ = licences
# -*- coding: cp1252 -*-

"""
Portions copyright � 2005-2009, Stephen John Machin, Lingfo Pty Ltd
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice,
this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
this list of conditions and the following disclaimer in the documentation
and/or other materials provided with the distribution.

3. None of the names of Stephen John Machin, Lingfo Pty Ltd and any
contributors may be used to endorse or promote products derived from this
software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS
BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF
THE POSSIBILITY OF SUCH DAMAGE.
"""

"""
/*-
 * Copyright (c) 2001 David Giffin.
 * All rights reserved.
 *
 * Based on the the Java version: Andrew Khan Copyright (c) 2000.
 *
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 *
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 *
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in
 *    the documentation and/or other materials provided with the
 *    distribution.
 *
 * 3. All advertising materials mentioning features or use of this
 *    software must display the following acknowledgment:
 *    "This product includes software developed by
 *     David Giffin <david@giffin.org>."
 *
 * 4. Redistributions of any form whatsoever must retain the following
 *    acknowledgment:
 *    "This product includes software developed by
 *     David Giffin <david@giffin.org>."
 *
 * THIS SOFTWARE IS PROVIDED BY DAVID GIFFIN ``AS IS'' AND ANY
 * EXPRESSED OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
 * PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL DAVID GIFFIN OR
 * ITS CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
 * SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
 * NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
 * LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
 * HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
 * STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED
 * OF THE POSSIBILITY OF SUCH DAMAGE.
 */
"""

########NEW FILE########
__FILENAME__ = sheet
# -*- coding: cp1252 -*-

##
# <p> Portions copyright � 2005-2013 Stephen John Machin, Lingfo Pty Ltd</p>
# <p>This module is part of the xlrd package, which is released under a BSD-style licence.</p>
##

# 2010-04-25 SJM fix zoom factors cooking logic
# 2010-04-15 CW  r4253 fix zoom factors cooking logic
# 2010-04-09 CW  r4248 add a flag so xlutils knows whether or not to write a PANE record
# 2010-03-29 SJM Fixed bug in adding new empty rows in put_cell_ragged
# 2010-03-28 SJM Tailored put_cell method for each of ragged_rows=False (fixed speed regression) and =True (faster)
# 2010-03-25 CW  r4236 Slight refactoring to remove method calls
# 2010-03-25 CW  r4235 Collapse expand_cells into put_cell and enhance the raggedness. This should save even more memory!
# 2010-03-25 CW  r4234 remove duplicate chunks for extend_cells; refactor to remove put_number_cell and put_blank_cell which essentially duplicated the code of put_cell
# 2010-03-10 SJM r4222 Added reading of the PANE record.
# 2010-03-10 SJM r4221 Preliminary work on "cooked" mag factors; use at own peril
# 2010-03-01 SJM Reading SCL record
# 2010-03-01 SJM Added ragged_rows functionality
# 2009-08-23 SJM Reduced CPU time taken by parsing MULBLANK records.
# 2009-08-18 SJM Used __slots__ and sharing to reduce memory consumed by Rowinfo instances
# 2009-05-31 SJM Fixed problem with no CODEPAGE record on extremely minimal BIFF2.x 3rd-party file
# 2009-04-27 SJM Integrated on_demand patch by Armando Serrano Lombillo
# 2008-02-09 SJM Excel 2.0: build XFs on the fly from cell attributes
# 2007-12-04 SJM Added support for Excel 2.x (BIFF2) files.
# 2007-10-11 SJM Added missing entry for blank cell type to ctype_text
# 2007-07-11 SJM Allow for BIFF2/3-style FORMAT record in BIFF4/8 file
# 2007-04-22 SJM Remove experimental "trimming" facility.

from __future__ import print_function

from array import array
from struct import unpack, calcsize
from .biffh import *
from .timemachine import *
from .formula import dump_formula, decompile_formula, rangename2d, FMLA_TYPE_CELL, FMLA_TYPE_SHARED
from .formatting import nearest_colour_index, Format

DEBUG = 0
OBJ_MSO_DEBUG = 0

_WINDOW2_options = (
    # Attribute names and initial values to use in case
    # a WINDOW2 record is not written.
    ("show_formulas", 0),
    ("show_grid_lines", 1),
    ("show_sheet_headers", 1),
    ("panes_are_frozen", 0),
    ("show_zero_values", 1),
    ("automatic_grid_line_colour", 1),
    ("columns_from_right_to_left", 0),
    ("show_outline_symbols", 1),
    ("remove_splits_if_pane_freeze_is_removed", 0),
    # Multiple sheets can be selected, but only one can be active
    # (hold down Ctrl and click multiple tabs in the file in OOo)
    ("sheet_selected", 0),
    # "sheet_visible" should really be called "sheet_active"
    # and is 1 when this sheet is the sheet displayed when the file
    # is open. More than likely only one sheet should ever be set as
    # visible.
    # This would correspond to the Book's sheet_active attribute, but
    # that doesn't exist as WINDOW1 records aren't currently processed.
    # The real thing is the visibility attribute from the BOUNDSHEET record.
    ("sheet_visible", 0),
    ("show_in_page_break_preview", 0),
    )

##
# <p>Contains the data for one worksheet.</p>
#
# <p>In the cell access functions, "rowx" is a row index, counting from zero, and "colx" is a
# column index, counting from zero.
# Negative values for row/column indexes and slice positions are supported in the expected fashion.</p>
#
# <p>For information about cell types and cell values, refer to the documentation of the {@link #Cell} class.</p>
#
# <p>WARNING: You don't call this class yourself. You access Sheet objects via the Book object that
# was returned when you called xlrd.open_workbook("myfile.xls").</p>


class Sheet(BaseObject):
    ##
    # Name of sheet.
    name = ''

    ##
    # A reference to the Book object to which this sheet belongs.
    # Example usage: some_sheet.book.datemode
    book = None
    
    ##
    # Number of rows in sheet. A row index is in range(thesheet.nrows).
    nrows = 0

    ##
    # Nominal number of columns in sheet. It is 1 + the maximum column index
    # found, ignoring trailing empty cells. See also open_workbook(ragged_rows=?)
    # and Sheet.{@link #Sheet.row_len}(row_index).
    ncols = 0

    ##
    # The map from a column index to a {@link #Colinfo} object. Often there is an entry
    # in COLINFO records for all column indexes in range(257).
    # Note that xlrd ignores the entry for the non-existent
    # 257th column. On the other hand, there may be no entry for unused columns.
    # <br /> -- New in version 0.6.1. Populated only if open_workbook(formatting_info=True).
    colinfo_map = {}

    ##
    # The map from a row index to a {@link #Rowinfo} object. Note that it is possible
    # to have missing entries -- at least one source of XLS files doesn't
    # bother writing ROW records.
    # <br /> -- New in version 0.6.1. Populated only if open_workbook(formatting_info=True).
    rowinfo_map = {}

    ##
    # List of address ranges of cells containing column labels.
    # These are set up in Excel by Insert > Name > Labels > Columns.
    # <br> -- New in version 0.6.0
    # <br>How to deconstruct the list:
    # <pre>
    # for crange in thesheet.col_label_ranges:
    #     rlo, rhi, clo, chi = crange
    #     for rx in xrange(rlo, rhi):
    #         for cx in xrange(clo, chi):
    #             print "Column label at (rowx=%d, colx=%d) is %r" \
    #                 (rx, cx, thesheet.cell_value(rx, cx))
    # </pre>
    col_label_ranges = []

    ##
    # List of address ranges of cells containing row labels.
    # For more details, see <i>col_label_ranges</i> above.
    # <br> -- New in version 0.6.0
    row_label_ranges = []

    ##
    # List of address ranges of cells which have been merged.
    # These are set up in Excel by Format > Cells > Alignment, then ticking
    # the "Merge cells" box.
    # <br> -- New in version 0.6.1. Extracted only if open_workbook(formatting_info=True).
    # <br>How to deconstruct the list:
    # <pre>
    # for crange in thesheet.merged_cells:
    #     rlo, rhi, clo, chi = crange
    #     for rowx in xrange(rlo, rhi):
    #         for colx in xrange(clo, chi):
    #             # cell (rlo, clo) (the top left one) will carry the data
    #             # and formatting info; the remainder will be recorded as
    #             # blank cells, but a renderer will apply the formatting info
    #             # for the top left cell (e.g. border, pattern) to all cells in
    #             # the range.
    # </pre>
    merged_cells = []
    
    ##
    # Mapping of (rowx, colx) to list of (offset, font_index) tuples. The offset
    # defines where in the string the font begins to be used.
    # Offsets are expected to be in ascending order.
    # If the first offset is not zero, the meaning is that the cell's XF's font should
    # be used from offset 0.
    # <br /> This is a sparse mapping. There is no entry for cells that are not formatted with  
    # rich text.
    # <br>How to use:
    # <pre>
    # runlist = thesheet.rich_text_runlist_map.get((rowx, colx))
    # if runlist:
    #     for offset, font_index in runlist:
    #         # do work here.
    #         pass
    # </pre>
    # Populated only if open_workbook(formatting_info=True).
    # <br /> -- New in version 0.7.2.
    # <br /> &nbsp;
    rich_text_runlist_map = {}    

    ##
    # Default column width from DEFCOLWIDTH record, else None.
    # From the OOo docs:<br />
    # """Column width in characters, using the width of the zero character
    # from default font (first FONT record in the file). Excel adds some
    # extra space to the default width, depending on the default font and
    # default font size. The algorithm how to exactly calculate the resulting
    # column width is not known.<br />
    # Example: The default width of 8 set in this record results in a column
    # width of 8.43 using Arial font with a size of 10 points."""<br />
    # For the default hierarchy, refer to the {@link #Colinfo} class.
    # <br /> -- New in version 0.6.1
    defcolwidth = None

    ##
    # Default column width from STANDARDWIDTH record, else None.
    # From the OOo docs:<br />
    # """Default width of the columns in 1/256 of the width of the zero
    # character, using default font (first FONT record in the file)."""<br />
    # For the default hierarchy, refer to the {@link #Colinfo} class.
    # <br /> -- New in version 0.6.1
    standardwidth = None

    ##
    # Default value to be used for a row if there is
    # no ROW record for that row.
    # From the <i>optional</i> DEFAULTROWHEIGHT record.
    default_row_height = None

    ##
    # Default value to be used for a row if there is
    # no ROW record for that row.
    # From the <i>optional</i> DEFAULTROWHEIGHT record.
    default_row_height_mismatch = None

    ##
    # Default value to be used for a row if there is
    # no ROW record for that row.
    # From the <i>optional</i> DEFAULTROWHEIGHT record.
    default_row_hidden = None

    ##
    # Default value to be used for a row if there is
    # no ROW record for that row.
    # From the <i>optional</i> DEFAULTROWHEIGHT record.
    default_additional_space_above = None

    ##
    # Default value to be used for a row if there is
    # no ROW record for that row.
    # From the <i>optional</i> DEFAULTROWHEIGHT record.
    default_additional_space_below = None

    ##
    # Visibility of the sheet. 0 = visible, 1 = hidden (can be unhidden
    # by user -- Format/Sheet/Unhide), 2 = "very hidden" (can be unhidden
    # only by VBA macro).
    visibility = 0

    ##
    # A 256-element tuple corresponding to the contents of the GCW record for this sheet.
    # If no such record, treat as all bits zero.
    # Applies to BIFF4-7 only. See docs of the {@link #Colinfo} class for discussion.
    gcw = (0, ) * 256

    ##
    # <p>A list of {@link #Hyperlink} objects corresponding to HLINK records found
    # in the worksheet.<br />-- New in version 0.7.2 </p>
    hyperlink_list = []

    ##
    # <p>A sparse mapping from (rowx, colx) to an item in {@link #Sheet.hyperlink_list}.
    # Cells not covered by a hyperlink are not mapped.
    # It is possible using the Excel UI to set up a hyperlink that 
    # covers a larger-than-1x1 rectangle of cells.
    # Hyperlink rectangles may overlap (Excel doesn't check).
    # When a multiply-covered cell is clicked on, the hyperlink that is activated
    # (and the one that is mapped here) is the last in hyperlink_list.
    # <br />-- New in version 0.7.2 </p>
    hyperlink_map = {}

    ##
    # <p>A sparse mapping from (rowx, colx) to a {@link #Note} object.
    # Cells not containing a note ("comment") are not mapped.
    # <br />-- New in version 0.7.2 </p>
    cell_note_map = {}    
    
    ##
    # Number of columns in left pane (frozen panes; for split panes, see comments below in code)
    vert_split_pos = 0

    ##
    # Number of rows in top pane (frozen panes; for split panes, see comments below in code)
    horz_split_pos = 0

    ##
    # Index of first visible row in bottom frozen/split pane
    horz_split_first_visible = 0

    ##
    # Index of first visible column in right frozen/split pane
    vert_split_first_visible = 0

    ##
    # Frozen panes: ignore it. Split panes: explanation and diagrams in OOo docs.
    split_active_pane = 0

    ##
    # Boolean specifying if a PANE record was present, ignore unless you're xlutils.copy
    has_pane_record = 0

    ##
    # A list of the horizontal page breaks in this sheet.
    # Breaks are tuples in the form (index of row after break, start col index, end col index).
    # Populated only if open_workbook(formatting_info=True).
    # <br /> -- New in version 0.7.2
    horizontal_page_breaks = []

    ##
    # A list of the vertical page breaks in this sheet.
    # Breaks are tuples in the form (index of col after break, start row index, end row index).
    # Populated only if open_workbook(formatting_info=True).
    # <br /> -- New in version 0.7.2
    vertical_page_breaks = []


    def __init__(self, book, position, name, number):
        self.book = book
        self.biff_version = book.biff_version
        self._position = position
        self.logfile = book.logfile
        self.bt = array('B', [XL_CELL_EMPTY])
        self.bf = array('h', [-1])
        self.name = name
        self.number = number
        self.verbosity = book.verbosity
        self.formatting_info = book.formatting_info
        self.ragged_rows = book.ragged_rows
        if self.ragged_rows:
            self.put_cell = self.put_cell_ragged
        else:
            self.put_cell = self.put_cell_unragged
        self._xf_index_to_xl_type_map = book._xf_index_to_xl_type_map
        self.nrows = 0 # actual, including possibly empty cells
        self.ncols = 0
        self._maxdatarowx = -1 # highest rowx containing a non-empty cell
        self._maxdatacolx = -1 # highest colx containing a non-empty cell
        self._dimnrows = 0 # as per DIMENSIONS record
        self._dimncols = 0
        self._cell_values = []
        self._cell_types = []
        self._cell_xf_indexes = []
        self.defcolwidth = None
        self.standardwidth = None
        self.default_row_height = None
        self.default_row_height_mismatch = 0
        self.default_row_hidden = 0
        self.default_additional_space_above = 0
        self.default_additional_space_below = 0
        self.colinfo_map = {}
        self.rowinfo_map = {}
        self.col_label_ranges = []
        self.row_label_ranges = []
        self.merged_cells = []
        self.rich_text_runlist_map = {}
        self.horizontal_page_breaks = []
        self.vertical_page_breaks = []
        self._xf_index_stats = [0, 0, 0, 0]
        self.visibility = book._sheet_visibility[number] # from BOUNDSHEET record
        for attr, defval in _WINDOW2_options:
            setattr(self, attr, defval)
        self.first_visible_rowx = 0
        self.first_visible_colx = 0
        self.gridline_colour_index = 0x40
        self.gridline_colour_rgb = None # pre-BIFF8
        self.hyperlink_list = []
        self.hyperlink_map = {}
        self.cell_note_map = {}

        # Values calculated by xlrd to predict the mag factors that
        # will actually be used by Excel to display your worksheet.
        # Pass these values to xlwt when writing XLS files.
        # Warning 1: Behaviour of OOo Calc and Gnumeric has been observed to differ from Excel's.
        # Warning 2: A value of zero means almost exactly what it says. Your sheet will be
        # displayed as a very tiny speck on the screen. xlwt will reject attempts to set
        # a mag_factor that is not (10 <= mag_factor <= 400).
        self.cooked_page_break_preview_mag_factor = 60
        self.cooked_normal_view_mag_factor = 100

        # Values (if any) actually stored on the XLS file
        self.cached_page_break_preview_mag_factor = None # from WINDOW2 record
        self.cached_normal_view_mag_factor = None # from WINDOW2 record
        self.scl_mag_factor = None # from SCL record

        self._ixfe = None # BIFF2 only
        self._cell_attr_to_xfx = {} # BIFF2.0 only

        #### Don't initialise this here, use class attribute initialisation.
        #### self.gcw = (0, ) * 256 ####

        if self.biff_version >= 80:
            self.utter_max_rows = 65536
        else:
            self.utter_max_rows = 16384
        self.utter_max_cols = 256

        self._first_full_rowx = -1

        # self._put_cell_exceptions = 0
        # self._put_cell_row_widenings = 0
        # self._put_cell_rows_appended = 0
        # self._put_cell_cells_appended = 0


    ##
    # {@link #Cell} object in the given row and column.
    def cell(self, rowx, colx):
        if self.formatting_info:
            xfx = self.cell_xf_index(rowx, colx)
        else:
            xfx = None
        return Cell(
            self._cell_types[rowx][colx],
            self._cell_values[rowx][colx],
            xfx,
            )

    ##
    # Value of the cell in the given row and column.
    def cell_value(self, rowx, colx):
        return self._cell_values[rowx][colx]

    ##
    # Type of the cell in the given row and column.
    # Refer to the documentation of the {@link #Cell} class.
    def cell_type(self, rowx, colx):
        return self._cell_types[rowx][colx]

    ##
    # XF index of the cell in the given row and column.
    # This is an index into Book.{@link #Book.xf_list}.
    # <br /> -- New in version 0.6.1
    def cell_xf_index(self, rowx, colx):
        self.req_fmt_info()
        xfx = self._cell_xf_indexes[rowx][colx]
        if xfx > -1:
            self._xf_index_stats[0] += 1
            return xfx
        # Check for a row xf_index
        try:
            xfx = self.rowinfo_map[rowx].xf_index
            if xfx > -1:
                self._xf_index_stats[1] += 1
                return xfx
        except KeyError:
            pass
        # Check for a column xf_index
        try:
            xfx = self.colinfo_map[colx].xf_index
            if xfx == -1: xfx = 15
            self._xf_index_stats[2] += 1
            return xfx
        except KeyError:
            # If all else fails, 15 is used as hardwired global default xf_index.
            self._xf_index_stats[3] += 1
            return 15

    ##
    # Returns the effective number of cells in the given row. For use with
    # open_workbook(ragged_rows=True) which is likely to produce rows
    # with fewer than {@link #Sheet.ncols} cells.
    # <br /> -- New in version 0.7.2
    def row_len(self, rowx):
        return len(self._cell_values[rowx])

    ##
    # Returns a sequence of the {@link #Cell} objects in the given row.
    def row(self, rowx):
        return [
            self.cell(rowx, colx)
            for colx in xrange(len(self._cell_values[rowx]))
            ]

    ##
    # Returns a slice of the types
    # of the cells in the given row.
    def row_types(self, rowx, start_colx=0, end_colx=None):
        if end_colx is None:
            return self._cell_types[rowx][start_colx:]
        return self._cell_types[rowx][start_colx:end_colx]

    ##
    # Returns a slice of the values
    # of the cells in the given row.
    def row_values(self, rowx, start_colx=0, end_colx=None):
        if end_colx is None:
            return self._cell_values[rowx][start_colx:]
        return self._cell_values[rowx][start_colx:end_colx]

    ##
    # Returns a slice of the {@link #Cell} objects in the given row.
    def row_slice(self, rowx, start_colx=0, end_colx=None):
        nc = len(self._cell_values[rowx])
        if start_colx < 0:
            start_colx += nc
            if start_colx < 0:
                start_colx = 0
        if end_colx is None or end_colx > nc:
            end_colx = nc
        elif end_colx < 0:
            end_colx += nc
        return [
            self.cell(rowx, colx)
            for colx in xrange(start_colx, end_colx)
            ]

    ##
    # Returns a slice of the {@link #Cell} objects in the given column.
    def col_slice(self, colx, start_rowx=0, end_rowx=None):
        nr = self.nrows
        if start_rowx < 0:
            start_rowx += nr
            if start_rowx < 0:
                start_rowx = 0
        if end_rowx is None or end_rowx > nr:
            end_rowx = nr
        elif end_rowx < 0:
            end_rowx += nr
        return [
            self.cell(rowx, colx)
            for rowx in xrange(start_rowx, end_rowx)
            ]

    ##
    # Returns a slice of the values of the cells in the given column.
    def col_values(self, colx, start_rowx=0, end_rowx=None):
        nr = self.nrows
        if start_rowx < 0:
            start_rowx += nr
            if start_rowx < 0:
                start_rowx = 0
        if end_rowx is None or end_rowx > nr:
            end_rowx = nr
        elif end_rowx < 0:
            end_rowx += nr
        return [
            self._cell_values[rowx][colx]
            for rowx in xrange(start_rowx, end_rowx)
            ]

    ##
    # Returns a slice of the types of the cells in the given column.
    def col_types(self, colx, start_rowx=0, end_rowx=None):
        nr = self.nrows
        if start_rowx < 0:
            start_rowx += nr
            if start_rowx < 0:
                start_rowx = 0
        if end_rowx is None or end_rowx > nr:
            end_rowx = nr
        elif end_rowx < 0:
            end_rowx += nr
        return [
            self._cell_types[rowx][colx]
            for rowx in xrange(start_rowx, end_rowx)
            ]

    ##
    # Returns a sequence of the {@link #Cell} objects in the given column.
    def col(self, colx):
        return self.col_slice(colx)
    # Above two lines just for the docs. Here's the real McCoy:
    col = col_slice

    # === Following methods are used in building the worksheet.
    # === They are not part of the API.

    def tidy_dimensions(self):
        if self.verbosity >= 3:
            fprintf(self.logfile,
                "tidy_dimensions: nrows=%d ncols=%d \n",
                self.nrows, self.ncols,
                )
        if 1 and self.merged_cells:
            nr = nc = 0
            umaxrows = self.utter_max_rows
            umaxcols = self.utter_max_cols
            for crange in self.merged_cells:
                rlo, rhi, clo, chi = crange
                if not (0 <= rlo < rhi <= umaxrows) \
                or not (0 <= clo < chi <= umaxcols):
                    fprintf(self.logfile,
                        "*** WARNING: sheet #%d (%r), MERGEDCELLS bad range %r\n",
                        self.number, self.name, crange)
                if rhi > nr: nr = rhi
                if chi > nc: nc = chi
            if nc > self.ncols:
                self.ncols = nc
            if nr > self.nrows:
                # we put one empty cell at (nr-1,0) to make sure
                # we have the right number of rows. The ragged rows
                # will sort out the rest if needed.
                self.put_cell(nr-1, 0, XL_CELL_EMPTY, '', -1)
        if self.verbosity >= 1 \
        and (self.nrows != self._dimnrows or self.ncols != self._dimncols):
            fprintf(self.logfile,
                "NOTE *** sheet %d (%r): DIMENSIONS R,C = %d,%d should be %d,%d\n",
                self.number,
                self.name,
                self._dimnrows,
                self._dimncols,
                self.nrows,
                self.ncols,
                )
        if not self.ragged_rows:
            # fix ragged rows
            ncols = self.ncols
            s_cell_types = self._cell_types
            s_cell_values = self._cell_values
            s_cell_xf_indexes = self._cell_xf_indexes
            s_fmt_info = self.formatting_info
            # for rowx in xrange(self.nrows):
            if self._first_full_rowx == -2:
                ubound = self.nrows
            else:
                ubound = self._first_full_rowx
            for rowx in xrange(ubound):
                trow = s_cell_types[rowx]
                rlen = len(trow)
                nextra = ncols - rlen
                if nextra > 0:
                    s_cell_values[rowx][rlen:] = [''] * nextra
                    trow[rlen:] = self.bt * nextra
                    if s_fmt_info:
                        s_cell_xf_indexes[rowx][rlen:] = self.bf * nextra

    def put_cell_ragged(self, rowx, colx, ctype, value, xf_index):
        if ctype is None:
            # we have a number, so look up the cell type
            ctype = self._xf_index_to_xl_type_map[xf_index]
        assert 0 <= colx < self.utter_max_cols
        assert 0 <= rowx < self.utter_max_rows
        fmt_info = self.formatting_info

        try:
            nr = rowx + 1
            if self.nrows < nr:

                scta = self._cell_types.append
                scva = self._cell_values.append
                scxa = self._cell_xf_indexes.append
                bt = self.bt
                bf = self.bf
                for _unused in xrange(self.nrows, nr):
                    scta(bt * 0)
                    scva([])
                    if fmt_info:
                        scxa(bf * 0)
                self.nrows = nr

            types_row = self._cell_types[rowx]
            values_row = self._cell_values[rowx]
            if fmt_info:
                fmt_row = self._cell_xf_indexes[rowx]
            ltr = len(types_row)
            if colx >= self.ncols:
                self.ncols = colx + 1
            num_empty = colx - ltr
            if not num_empty:
                # most common case: colx == previous colx + 1
                # self._put_cell_cells_appended += 1
                types_row.append(ctype)
                values_row.append(value)
                if fmt_info:
                    fmt_row.append(xf_index)
                return
            if num_empty > 0:
                num_empty += 1
                # self._put_cell_row_widenings += 1
                # types_row.extend(self.bt * num_empty)
                # values_row.extend([''] * num_empty)
                # if fmt_info:
                #     fmt_row.extend(self.bf * num_empty)
                types_row[ltr:] = self.bt * num_empty
                values_row[ltr:] = [''] * num_empty
                if fmt_info:
                    fmt_row[ltr:] = self.bf * num_empty
            types_row[colx] = ctype
            values_row[colx] = value
            if fmt_info:
                fmt_row[colx] = xf_index
        except:
            print("put_cell", rowx, colx, file=self.logfile)
            raise

    def put_cell_unragged(self, rowx, colx, ctype, value, xf_index):
        if ctype is None:
            # we have a number, so look up the cell type
            ctype = self._xf_index_to_xl_type_map[xf_index]
        # assert 0 <= colx < self.utter_max_cols
        # assert 0 <= rowx < self.utter_max_rows
        try:
            self._cell_types[rowx][colx] = ctype
            self._cell_values[rowx][colx] = value
            if self.formatting_info:
                self._cell_xf_indexes[rowx][colx] = xf_index
        except IndexError:
            # print >> self.logfile, "put_cell extending", rowx, colx
            # self.extend_cells(rowx+1, colx+1)
            # self._put_cell_exceptions += 1
            nr = rowx + 1
            nc = colx + 1
            assert 1 <= nc <= self.utter_max_cols
            assert 1 <= nr <= self.utter_max_rows
            if nc > self.ncols:
                self.ncols = nc
                # The row self._first_full_rowx and all subsequent rows
                # are guaranteed to have length == self.ncols. Thus the
                # "fix ragged rows" section of the tidy_dimensions method
                # doesn't need to examine them.
                if nr < self.nrows:
                    # cell data is not in non-descending row order *AND*
                    # self.ncols has been bumped up.
                    # This very rare case ruins this optmisation.
                    self._first_full_rowx = -2
                elif rowx > self._first_full_rowx > -2:
                    self._first_full_rowx = rowx
            if nr <= self.nrows:
                # New cell is in an existing row, so extend that row (if necessary).
                # Note that nr < self.nrows means that the cell data
                # is not in ascending row order!!
                trow = self._cell_types[rowx]
                nextra = self.ncols - len(trow)
                if nextra > 0:
                    # self._put_cell_row_widenings += 1
                    trow.extend(self.bt * nextra)
                    if self.formatting_info:
                        self._cell_xf_indexes[rowx].extend(self.bf * nextra)
                    self._cell_values[rowx].extend([''] * nextra)
            else:
                scta = self._cell_types.append
                scva = self._cell_values.append
                scxa = self._cell_xf_indexes.append
                fmt_info = self.formatting_info
                nc = self.ncols
                bt = self.bt
                bf = self.bf
                for _unused in xrange(self.nrows, nr):
                    # self._put_cell_rows_appended += 1
                    scta(bt * nc)
                    scva([''] * nc)
                    if fmt_info:
                        scxa(bf * nc)
                self.nrows = nr
            # === end of code from extend_cells()
            try:
                self._cell_types[rowx][colx] = ctype
                self._cell_values[rowx][colx] = value
                if self.formatting_info:
                    self._cell_xf_indexes[rowx][colx] = xf_index
            except:
                print("put_cell", rowx, colx, file=self.logfile)
                raise
        except:
           print("put_cell", rowx, colx, file=self.logfile)
           raise


    # === Methods after this line neither know nor care about how cells are stored.

    def read(self, bk):
        global rc_stats
        DEBUG = 0
        blah = DEBUG or self.verbosity >= 2
        blah_rows = DEBUG or self.verbosity >= 4
        blah_formulas = 0 and blah
        r1c1 = 0
        oldpos = bk._position
        bk._position = self._position
        XL_SHRFMLA_ETC_ETC = (
            XL_SHRFMLA, XL_ARRAY, XL_TABLEOP, XL_TABLEOP2,
            XL_ARRAY2, XL_TABLEOP_B2,
            )
        self_put_cell = self.put_cell
        local_unpack = unpack
        bk_get_record_parts = bk.get_record_parts
        bv = self.biff_version
        fmt_info = self.formatting_info
        do_sst_rich_text = fmt_info and bk._rich_text_runlist_map
        rowinfo_sharing_dict = {}
        txos = {}
        eof_found = 0
        while 1:
            # if DEBUG: print "SHEET.READ: about to read from position %d" % bk._position
            rc, data_len, data = bk_get_record_parts()
            # if rc in rc_stats:
            #     rc_stats[rc] += 1
            # else:
            #     rc_stats[rc] = 1
            # if DEBUG: print "SHEET.READ: op 0x%04x, %d bytes %r" % (rc, data_len, data)
            if rc == XL_NUMBER:
                # [:14] in following stmt ignores extraneous rubbish at end of record.
                # Sample file testEON-8.xls supplied by Jan Kraus.
                rowx, colx, xf_index, d = local_unpack('<HHHd', data[:14])
                # if xf_index == 0:
                #     fprintf(self.logfile,
                #         "NUMBER: r=%d c=%d xfx=%d %f\n", rowx, colx, xf_index, d)
                self_put_cell(rowx, colx, None, d, xf_index)
            elif rc == XL_LABELSST:
                rowx, colx, xf_index, sstindex = local_unpack('<HHHi', data)
                # print "LABELSST", rowx, colx, sstindex, bk._sharedstrings[sstindex]
                self_put_cell(rowx, colx, XL_CELL_TEXT, bk._sharedstrings[sstindex], xf_index)
                if do_sst_rich_text:
                    runlist = bk._rich_text_runlist_map.get(sstindex)
                    if runlist:
                        self.rich_text_runlist_map[(rowx, colx)] = runlist
            elif rc == XL_LABEL:
                rowx, colx, xf_index = local_unpack('<HHH', data[0:6])
                if bv < BIFF_FIRST_UNICODE:
                    strg = unpack_string(data, 6, bk.encoding or bk.derive_encoding(), lenlen=2)
                else:
                    strg = unpack_unicode(data, 6, lenlen=2)
                self_put_cell(rowx, colx, XL_CELL_TEXT, strg, xf_index)
            elif rc == XL_RSTRING:
                rowx, colx, xf_index = local_unpack('<HHH', data[0:6])
                if bv < BIFF_FIRST_UNICODE:
                    strg, pos = unpack_string_update_pos(data, 6, bk.encoding or bk.derive_encoding(), lenlen=2)
                    nrt = BYTES_ORD(data[pos])
                    pos += 1
                    runlist = []
                    for _unused in xrange(nrt):
                        runlist.append(unpack('<BB', data[pos:pos+2]))
                        pos += 2
                    assert pos == len(data)
                else:
                    strg, pos = unpack_unicode_update_pos(data, 6, lenlen=2)
                    nrt = unpack('<H', data[pos:pos+2])[0]
                    pos += 2
                    runlist = []
                    for _unused in xrange(nrt):
                        runlist.append(unpack('<HH', data[pos:pos+4]))
                        pos += 4
                    assert pos == len(data)
                self_put_cell(rowx, colx, XL_CELL_TEXT, strg, xf_index)
                self.rich_text_runlist_map[(rowx, colx)] = runlist
            elif rc == XL_RK:
                rowx, colx, xf_index = local_unpack('<HHH', data[:6])
                d = unpack_RK(data[6:10])
                self_put_cell(rowx, colx, None, d, xf_index)
            elif rc == XL_MULRK:
                mulrk_row, mulrk_first = local_unpack('<HH', data[0:4])
                mulrk_last, = local_unpack('<H', data[-2:])
                pos = 4
                for colx in xrange(mulrk_first, mulrk_last+1):
                    xf_index, = local_unpack('<H', data[pos:pos+2])
                    d = unpack_RK(data[pos+2:pos+6])
                    pos += 6
                    self_put_cell(mulrk_row, colx, None, d, xf_index)
            elif rc == XL_ROW:
                # Version 0.6.0a3: ROW records are just not worth using (for memory allocation).
                # Version 0.6.1: now used for formatting info.
                if not fmt_info: continue
                rowx, bits1, bits2 = local_unpack('<H4xH4xi', data[0:16])
                if not(0 <= rowx < self.utter_max_rows):
                    print("*** NOTE: ROW record has row index %d; " \
                        "should have 0 <= rowx < %d -- record ignored!" \
                        % (rowx, self.utter_max_rows), file=self.logfile)
                    continue
                key = (bits1, bits2)
                r = rowinfo_sharing_dict.get(key)
                if r is None:
                    rowinfo_sharing_dict[key] = r = Rowinfo()
                    # Using upkbits() is far too slow on a file
                    # with 30 sheets each with 10K rows :-(
                    #    upkbits(r, bits1, (
                    #        ( 0, 0x7FFF, 'height'),
                    #        (15, 0x8000, 'has_default_height'),
                    #        ))
                    #    upkbits(r, bits2, (
                    #        ( 0, 0x00000007, 'outline_level'),
                    #        ( 4, 0x00000010, 'outline_group_starts_ends'),
                    #        ( 5, 0x00000020, 'hidden'),
                    #        ( 6, 0x00000040, 'height_mismatch'),
                    #        ( 7, 0x00000080, 'has_default_xf_index'),
                    #        (16, 0x0FFF0000, 'xf_index'),
                    #        (28, 0x10000000, 'additional_space_above'),
                    #        (29, 0x20000000, 'additional_space_below'),
                    #        ))
                    # So:
                    r.height = bits1 & 0x7fff
                    r.has_default_height = (bits1 >> 15) & 1
                    r.outline_level = bits2 & 7
                    r.outline_group_starts_ends = (bits2 >> 4) & 1
                    r.hidden = (bits2 >> 5) & 1
                    r.height_mismatch = (bits2 >> 6) & 1
                    r.has_default_xf_index = (bits2 >> 7) & 1
                    r.xf_index = (bits2 >> 16) & 0xfff
                    r.additional_space_above = (bits2 >> 28) & 1
                    r.additional_space_below = (bits2 >> 29) & 1
                    if not r.has_default_xf_index:
                        r.xf_index = -1
                self.rowinfo_map[rowx] = r
                if 0 and r.xf_index > -1:
                    fprintf(self.logfile,
                        "**ROW %d %d %d\n",
                        self.number, rowx, r.xf_index)
                if blah_rows:
                    print('ROW', rowx, bits1, bits2, file=self.logfile)
                    r.dump(self.logfile,
                        header="--- sh #%d, rowx=%d ---" % (self.number, rowx))
            elif rc in XL_FORMULA_OPCODES: # 06, 0206, 0406
                # DEBUG = 1
                # if DEBUG: print "FORMULA: rc: 0x%04x data: %r" % (rc, data)
                if bv >= 50:
                    rowx, colx, xf_index, result_str, flags = local_unpack('<HHH8sH', data[0:16])
                    lenlen = 2
                    tkarr_offset = 20
                elif bv >= 30:
                    rowx, colx, xf_index, result_str, flags = local_unpack('<HHH8sH', data[0:16])
                    lenlen = 2
                    tkarr_offset = 16
                else: # BIFF2
                    rowx, colx, cell_attr,  result_str, flags = local_unpack('<HH3s8sB', data[0:16])
                    xf_index =  self.fixed_BIFF2_xfindex(cell_attr, rowx, colx)
                    lenlen = 1
                    tkarr_offset = 16
                if blah_formulas: # testing formula dumper
                    #### XXXX FIXME
                    fprintf(self.logfile, "FORMULA: rowx=%d colx=%d\n", rowx, colx)
                    fmlalen = local_unpack("<H", data[20:22])[0]
                    decompile_formula(bk, data[22:], fmlalen, FMLA_TYPE_CELL,
                        browx=rowx, bcolx=colx, blah=1, r1c1=r1c1)
                if result_str[6:8] == b"\xFF\xFF":
                    first_byte = BYTES_ORD(result_str[0])
                    if first_byte == 0:
                        # need to read next record (STRING)
                        gotstring = 0
                        # if flags & 8:
                        if 1: # "flags & 8" applies only to SHRFMLA
                            # actually there's an optional SHRFMLA or ARRAY etc record to skip over
                            rc2, data2_len, data2 = bk.get_record_parts()
                            if rc2 == XL_STRING or rc2 == XL_STRING_B2:
                                gotstring = 1
                            elif rc2 == XL_ARRAY:
                                row1x, rownx, col1x, colnx, array_flags, tokslen = \
                                    local_unpack("<HHBBBxxxxxH", data2[:14])
                                if blah_formulas:
                                    fprintf(self.logfile, "ARRAY: %d %d %d %d %d\n",
                                        row1x, rownx, col1x, colnx, array_flags)
                                    # dump_formula(bk, data2[14:], tokslen, bv, reldelta=0, blah=1)
                            elif rc2 == XL_SHRFMLA:
                                row1x, rownx, col1x, colnx, nfmlas, tokslen = \
                                    local_unpack("<HHBBxBH", data2[:10])
                                if blah_formulas:
                                    fprintf(self.logfile, "SHRFMLA (sub): %d %d %d %d %d\n",
                                        row1x, rownx, col1x, colnx, nfmlas)
                                    decompile_formula(bk, data2[10:], tokslen, FMLA_TYPE_SHARED,
                                        blah=1, browx=rowx, bcolx=colx, r1c1=r1c1)
                            elif rc2 not in XL_SHRFMLA_ETC_ETC:
                                raise XLRDError(
                                    "Expected SHRFMLA, ARRAY, TABLEOP* or STRING record; found 0x%04x" % rc2)
                            # if DEBUG: print "gotstring:", gotstring
                        # now for the STRING record
                        if not gotstring:
                            rc2, _unused_len, data2 = bk.get_record_parts()
                            if rc2 not in (XL_STRING, XL_STRING_B2):
                                raise XLRDError("Expected STRING record; found 0x%04x" % rc2)
                        # if DEBUG: print "STRING: data=%r BIFF=%d cp=%d" % (data2, self.biff_version, bk.encoding)
                        strg = self.string_record_contents(data2)
                        self.put_cell(rowx, colx, XL_CELL_TEXT, strg, xf_index)
                        # if DEBUG: print "FORMULA strg %r" % strg
                    elif first_byte == 1:
                        # boolean formula result
                        value = BYTES_ORD(result_str[2])
                        self_put_cell(rowx, colx, XL_CELL_BOOLEAN, value, xf_index)
                    elif first_byte == 2:
                        # Error in cell
                        value = BYTES_ORD(result_str[2])
                        self_put_cell(rowx, colx, XL_CELL_ERROR, value, xf_index)
                    elif first_byte == 3:
                        # empty ... i.e. empty (zero-length) string, NOT an empty cell.
                        self_put_cell(rowx, colx, XL_CELL_TEXT, "", xf_index)
                    else:
                        raise XLRDError("unexpected special case (0x%02x) in FORMULA" % first_byte)
                else:
                    # it is a number
                    d = local_unpack('<d', result_str)[0]
                    self_put_cell(rowx, colx, None, d, xf_index)
            elif rc == XL_BOOLERR:
                rowx, colx, xf_index, value, is_err = local_unpack('<HHHBB', data[:8])
                # Note OOo Calc 2.0 writes 9-byte BOOLERR records.
                # OOo docs say 8. Excel writes 8.
                cellty = (XL_CELL_BOOLEAN, XL_CELL_ERROR)[is_err]
                # if DEBUG: print "XL_BOOLERR", rowx, colx, xf_index, value, is_err
                self_put_cell(rowx, colx, cellty, value, xf_index)
            elif rc == XL_COLINFO:
                if not fmt_info: continue
                c = Colinfo()
                first_colx, last_colx, c.width, c.xf_index, flags \
                    = local_unpack("<HHHHH", data[:10])
                #### Colinfo.width is denominated in 256ths of a character,
                #### *not* in characters.
                if not(0 <= first_colx <= last_colx <= 256):
                    # Note: 256 instead of 255 is a common mistake.
                    # We silently ignore the non-existing 257th column in that case.
                    print("*** NOTE: COLINFO record has first col index %d, last %d; " \
                        "should have 0 <= first <= last <= 255 -- record ignored!" \
                        % (first_colx, last_colx), file=self.logfile)
                    del c
                    continue
                upkbits(c, flags, (
                    ( 0, 0x0001, 'hidden'),
                    ( 1, 0x0002, 'bit1_flag'),
                    # *ALL* colinfos created by Excel in "default" cases are 0x0002!!
                    # Maybe it's "locked" by analogy with XFProtection data.
                    ( 8, 0x0700, 'outline_level'),
                    (12, 0x1000, 'collapsed'),
                    ))
                for colx in xrange(first_colx, last_colx+1):
                    if colx > 255: break # Excel does 0 to 256 inclusive
                    self.colinfo_map[colx] = c
                    if 0:
                        fprintf(self.logfile,
                            "**COL %d %d %d\n",
                            self.number, colx, c.xf_index)
                if blah:
                    fprintf(
                        self.logfile,
                        "COLINFO sheet #%d cols %d-%d: wid=%d xf_index=%d flags=0x%04x\n",
                        self.number, first_colx, last_colx, c.width, c.xf_index, flags,
                        )
                    c.dump(self.logfile, header='===')
            elif rc == XL_DEFCOLWIDTH:
                self.defcolwidth, = local_unpack("<H", data[:2])
                if 0: print('DEFCOLWIDTH', self.defcolwidth, file=self.logfile)
            elif rc == XL_STANDARDWIDTH:
                if data_len != 2:
                    print('*** ERROR *** STANDARDWIDTH', data_len, repr(data), file=self.logfile)
                self.standardwidth, = local_unpack("<H", data[:2])
                if 0: print('STANDARDWIDTH', self.standardwidth, file=self.logfile)
            elif rc == XL_GCW:
                if not fmt_info: continue # useless w/o COLINFO
                assert data_len == 34
                assert data[0:2] == b"\x20\x00"
                iguff = unpack("<8i", data[2:34])
                gcw = []
                for bits in iguff:
                    for j in xrange(32):
                        gcw.append(bits & 1)
                        bits >>= 1
                self.gcw = tuple(gcw)
                if 0:
                    showgcw = "".join(map(lambda x: "F "[x], gcw)).rstrip().replace(' ', '.')
                    print("GCW:", showgcw, file=self.logfile)
            elif rc == XL_BLANK:
                if not fmt_info: continue
                rowx, colx, xf_index = local_unpack('<HHH', data[:6])
                # if 0: print >> self.logfile, "BLANK", rowx, colx, xf_index
                self_put_cell(rowx, colx, XL_CELL_BLANK, '', xf_index)
            elif rc == XL_MULBLANK: # 00BE
                if not fmt_info: continue
                nitems = data_len >> 1
                result = local_unpack("<%dH" % nitems, data)
                rowx, mul_first = result[:2]
                mul_last = result[-1]
                # print >> self.logfile, "MULBLANK", rowx, mul_first, mul_last, data_len, nitems, mul_last + 4 - mul_first
                assert nitems == mul_last + 4 - mul_first
                pos = 2
                for colx in xrange(mul_first, mul_last + 1):
                    self_put_cell(rowx, colx, XL_CELL_BLANK, '', result[pos])
                    pos += 1
            elif rc == XL_DIMENSION or rc == XL_DIMENSION2:
                if data_len == 0:
                    # Four zero bytes after some other record. See github issue 64.
                    continue
                # if data_len == 10:
                # Was crashing on BIFF 4.0 file w/o the two trailing unused bytes.
                # Reported by Ralph Heimburger.
                if bv < 80:
                    dim_tuple = local_unpack('<HxxH', data[2:8])
                else:
                    dim_tuple = local_unpack('<ixxH', data[4:12])
                self.nrows, self.ncols = 0, 0
                self._dimnrows, self._dimncols = dim_tuple
                if bv in (21, 30, 40) and self.book.xf_list and not self.book._xf_epilogue_done:
                    self.book.xf_epilogue()
                if blah:
                    fprintf(self.logfile,
                        "sheet %d(%r) DIMENSIONS: ncols=%d nrows=%d\n",
                        self.number, self.name, self._dimncols, self._dimnrows
                        )
            elif rc == XL_HLINK:
                self.handle_hlink(data)
            elif rc == XL_QUICKTIP:
                self.handle_quicktip(data)
            elif rc == XL_EOF:
                DEBUG = 0
                if DEBUG: print("SHEET.READ: EOF", file=self.logfile)
                eof_found = 1
                break
            elif rc == XL_OBJ:
                # handle SHEET-level objects; note there's a separate Book.handle_obj
                saved_obj = self.handle_obj(data)
                if saved_obj: saved_obj_id = saved_obj.id
                else: saved_obj_id = None
            elif rc == XL_MSO_DRAWING:
                self.handle_msodrawingetc(rc, data_len, data)
            elif rc == XL_TXO:
                txo = self.handle_txo(data)
                if txo and saved_obj_id:
                    txos[saved_obj_id] = txo
                    saved_obj_id = None
            elif rc == XL_NOTE:
                self.handle_note(data, txos)
            elif rc == XL_FEAT11:
                self.handle_feat11(data)
            elif rc in bofcodes: ##### EMBEDDED BOF #####
                version, boftype = local_unpack('<HH', data[0:4])
                if boftype != 0x20: # embedded chart
                    print("*** Unexpected embedded BOF (0x%04x) at offset %d: version=0x%04x type=0x%04x" \
                        % (rc, bk._position - data_len - 4, version, boftype), file=self.logfile)
                while 1:
                    code, data_len, data = bk.get_record_parts()
                    if code == XL_EOF:
                        break
                if DEBUG: print("---> found EOF", file=self.logfile)
            elif rc == XL_COUNTRY:
                bk.handle_country(data)
            elif rc == XL_LABELRANGES:
                pos = 0
                pos = unpack_cell_range_address_list_update_pos(
                        self.row_label_ranges, data, pos, bv, addr_size=8,
                        )
                pos = unpack_cell_range_address_list_update_pos(
                        self.col_label_ranges, data, pos, bv, addr_size=8,
                        )
                assert pos == data_len
            elif rc == XL_ARRAY:
                row1x, rownx, col1x, colnx, array_flags, tokslen = \
                    local_unpack("<HHBBBxxxxxH", data[:14])
                if blah_formulas:
                    print("ARRAY:", row1x, rownx, col1x, colnx, array_flags, file=self.logfile)
                    # dump_formula(bk, data[14:], tokslen, bv, reldelta=0, blah=1)
            elif rc == XL_SHRFMLA:
                row1x, rownx, col1x, colnx, nfmlas, tokslen = \
                    local_unpack("<HHBBxBH", data[:10])
                if blah_formulas:
                    print("SHRFMLA (main):", row1x, rownx, col1x, colnx, nfmlas, file=self.logfile)
                    decompile_formula(bk, data[10:], tokslen, FMLA_TYPE_SHARED,
                        blah=1, browx=rowx, bcolx=colx, r1c1=r1c1)
            elif rc == XL_CONDFMT:
                if not fmt_info: continue
                assert bv >= 80
                num_CFs, needs_recalc, browx1, browx2, bcolx1, bcolx2 = \
                    unpack("<6H", data[0:12])
                if self.verbosity >= 1:
                    fprintf(self.logfile,
                        "\n*** WARNING: Ignoring CONDFMT (conditional formatting) record\n" \
                        "*** in Sheet %d (%r).\n" \
                        "*** %d CF record(s); needs_recalc_or_redraw = %d\n" \
                        "*** Bounding box is %s\n",
                        self.number, self.name, num_CFs, needs_recalc,
                        rangename2d(browx1, browx2+1, bcolx1, bcolx2+1),
                        )
                olist = [] # updated by the function
                pos = unpack_cell_range_address_list_update_pos(
                    olist, data, 12, bv, addr_size=8)
                # print >> self.logfile, repr(result), len(result)
                if self.verbosity >= 1:
                    fprintf(self.logfile,
                        "*** %d individual range(s):\n" \
                        "*** %s\n",
                        len(olist),
                        ", ".join([rangename2d(*coords) for coords in olist]),
                        )
            elif rc == XL_CF:
                if not fmt_info: continue
                cf_type, cmp_op, sz1, sz2, flags = unpack("<BBHHi", data[0:10])
                font_block = (flags >> 26) & 1
                bord_block = (flags >> 28) & 1
                patt_block = (flags >> 29) & 1
                if self.verbosity >= 1:
                    fprintf(self.logfile,
                        "\n*** WARNING: Ignoring CF (conditional formatting) sub-record.\n" \
                        "*** cf_type=%d, cmp_op=%d, sz1=%d, sz2=%d, flags=0x%08x\n" \
                        "*** optional data blocks: font=%d, border=%d, pattern=%d\n",
                        cf_type, cmp_op, sz1, sz2, flags,
                        font_block, bord_block, patt_block,
                        )
                # hex_char_dump(data, 0, data_len, fout=self.logfile)
                pos = 12
                if font_block:
                    (font_height, font_options, weight, escapement, underline,
                    font_colour_index, two_bits, font_esc, font_underl) = \
                    unpack("<64x i i H H B 3x i 4x i i i 18x", data[pos:pos+118])
                    font_style = (two_bits > 1) & 1
                    posture = (font_options > 1) & 1
                    font_canc = (two_bits > 7) & 1
                    cancellation = (font_options > 7) & 1
                    if self.verbosity >= 1:
                        fprintf(self.logfile,
                            "*** Font info: height=%d, weight=%d, escapement=%d,\n" \
                            "*** underline=%d, colour_index=%d, esc=%d, underl=%d,\n" \
                            "*** style=%d, posture=%d, canc=%d, cancellation=%d\n",
                            font_height, weight, escapement, underline,
                            font_colour_index, font_esc, font_underl,
                            font_style, posture, font_canc, cancellation,
                            )
                    pos += 118
                if bord_block:
                    pos += 8
                if patt_block:
                    pos += 4
                fmla1 = data[pos:pos+sz1]
                pos += sz1
                if blah and sz1:
                    fprintf(self.logfile,
                        "*** formula 1:\n",
                        )
                    dump_formula(bk, fmla1, sz1, bv, reldelta=0, blah=1)
                fmla2 = data[pos:pos+sz2]
                pos += sz2
                assert pos == data_len
                if blah and sz2:
                    fprintf(self.logfile,
                        "*** formula 2:\n",
                        )
                    dump_formula(bk, fmla2, sz2, bv, reldelta=0, blah=1)
            elif rc == XL_DEFAULTROWHEIGHT:
                if data_len == 4:
                    bits, self.default_row_height = unpack("<HH", data[:4])
                elif data_len == 2:
                    self.default_row_height, = unpack("<H", data)
                    bits = 0
                    fprintf(self.logfile,
                        "*** WARNING: DEFAULTROWHEIGHT record len is 2, " \
                        "should be 4; assuming BIFF2 format\n")
                else:
                    bits = 0
                    fprintf(self.logfile,
                        "*** WARNING: DEFAULTROWHEIGHT record len is %d, " \
                        "should be 4; ignoring this record\n",
                        data_len)
                self.default_row_height_mismatch = bits & 1
                self.default_row_hidden = (bits >> 1) & 1
                self.default_additional_space_above = (bits >> 2) & 1
                self.default_additional_space_below = (bits >> 3) & 1
            elif rc == XL_MERGEDCELLS:
                if not fmt_info: continue
                pos = unpack_cell_range_address_list_update_pos(
                    self.merged_cells, data, 0, bv, addr_size=8)
                if blah:
                    fprintf(self.logfile,
                        "MERGEDCELLS: %d ranges\n", (pos - 2) // 8)
                assert pos == data_len, \
                    "MERGEDCELLS: pos=%d data_len=%d" % (pos, data_len)
            elif rc == XL_WINDOW2:
                if bv >= 80 and data_len >= 14:
                    (options,
                    self.first_visible_rowx, self.first_visible_colx,
                    self.gridline_colour_index,
                    self.cached_page_break_preview_mag_factor,
                    self.cached_normal_view_mag_factor
                    ) = unpack("<HHHHxxHH", data[:14])
                else:
                    assert bv >= 30 # BIFF3-7
                    (options,
                    self.first_visible_rowx, self.first_visible_colx,
                    ) = unpack("<HHH", data[:6])
                    self.gridline_colour_rgb = unpack("<BBB", data[6:9])
                    self.gridline_colour_index = nearest_colour_index(
                        self.book.colour_map, self.gridline_colour_rgb, debug=0)
                    self.cached_page_break_preview_mag_factor = 0 # default (60%)
                    self.cached_normal_view_mag_factor = 0 # default (100%)
                # options -- Bit, Mask, Contents:
                # 0 0001H 0 = Show formula results 1 = Show formulas
                # 1 0002H 0 = Do not show grid lines 1 = Show grid lines
                # 2 0004H 0 = Do not show sheet headers 1 = Show sheet headers
                # 3 0008H 0 = Panes are not frozen 1 = Panes are frozen (freeze)
                # 4 0010H 0 = Show zero values as empty cells 1 = Show zero values
                # 5 0020H 0 = Manual grid line colour 1 = Automatic grid line colour
                # 6 0040H 0 = Columns from left to right 1 = Columns from right to left
                # 7 0080H 0 = Do not show outline symbols 1 = Show outline symbols
                # 8 0100H 0 = Keep splits if pane freeze is removed 1 = Remove splits if pane freeze is removed
                # 9 0200H 0 = Sheet not selected 1 = Sheet selected (BIFF5-BIFF8)
                # 10 0400H 0 = Sheet not visible 1 = Sheet visible (BIFF5-BIFF8)
                # 11 0800H 0 = Show in normal view 1 = Show in page break preview (BIFF8)
                # The freeze flag specifies, if a following PANE record (6.71) describes unfrozen or frozen panes.
                for attr, _unused_defval in _WINDOW2_options:
                    setattr(self, attr, options & 1)
                    options >>= 1
            elif rc == XL_SCL:
                num, den = unpack("<HH", data)
                result = 0
                if den:
                    result = (num * 100) // den
                if not(10 <= result <= 400):
                    if DEBUG or self.verbosity >= 0:
                        print((
                            "WARNING *** SCL rcd sheet %d: should have 0.1 <= num/den <= 4; got %d/%d"
                            % (self.number, num, den)
                            ), file=self.logfile)
                    result = 100
                self.scl_mag_factor = result
            elif rc == XL_PANE:
                (
                self.vert_split_pos,
                self.horz_split_pos,
                self.horz_split_first_visible,
                self.vert_split_first_visible,
                self.split_active_pane,
                ) = unpack("<HHHHB", data[:9])
                self.has_pane_record = 1
            elif rc == XL_HORIZONTALPAGEBREAKS:
                if not fmt_info: continue
                num_breaks, = local_unpack("<H", data[:2])
                assert num_breaks * (2 + 4 * (bv >= 80)) + 2 == data_len
                pos = 2
                if bv < 80:
                    while pos < data_len:
                        self.horizontal_page_breaks.append((local_unpack("<H", data[pos:pos+2])[0], 0, 255))
                        pos += 2
                else:
                    while pos < data_len:
                        self.horizontal_page_breaks.append(local_unpack("<HHH", data[pos:pos+6]))
                        pos += 6
            elif rc == XL_VERTICALPAGEBREAKS:
                if not fmt_info: continue
                num_breaks, = local_unpack("<H", data[:2])
                assert num_breaks * (2 + 4 * (bv >= 80)) + 2 == data_len
                pos = 2
                if bv < 80:
                    while pos < data_len:
                        self.vertical_page_breaks.append((local_unpack("<H", data[pos:pos+2])[0], 0, 65535))
                        pos += 2
                else:
                    while pos < data_len:
                        self.vertical_page_breaks.append(local_unpack("<HHH", data[pos:pos+6]))
                        pos += 6
            #### all of the following are for BIFF <= 4W
            elif bv <= 45:
                if rc == XL_FORMAT or rc == XL_FORMAT2:
                    bk.handle_format(data, rc)
                elif rc == XL_FONT or rc == XL_FONT_B3B4:
                    bk.handle_font(data)
                elif rc == XL_STYLE:
                    if not self.book._xf_epilogue_done:
                        self.book.xf_epilogue()
                    bk.handle_style(data)
                elif rc == XL_PALETTE:
                    bk.handle_palette(data)
                elif rc == XL_BUILTINFMTCOUNT:
                    bk.handle_builtinfmtcount(data)
                elif rc == XL_XF4 or rc == XL_XF3 or rc == XL_XF2: #### N.B. not XL_XF
                    bk.handle_xf(data)
                elif rc == XL_DATEMODE:
                    bk.handle_datemode(data)
                elif rc == XL_CODEPAGE:
                    bk.handle_codepage(data)
                elif rc == XL_FILEPASS:
                    bk.handle_filepass(data)
                elif rc == XL_WRITEACCESS:
                    bk.handle_writeaccess(data)
                elif rc == XL_IXFE:
                    self._ixfe = local_unpack('<H', data)[0]
                elif rc == XL_NUMBER_B2:
                    rowx, colx, cell_attr, d = local_unpack('<HH3sd', data)
                    self_put_cell(rowx, colx, None, d, self.fixed_BIFF2_xfindex(cell_attr, rowx, colx))
                elif rc == XL_INTEGER:
                    rowx, colx, cell_attr, d = local_unpack('<HH3sH', data)
                    self_put_cell(rowx, colx, None, float(d), self.fixed_BIFF2_xfindex(cell_attr, rowx, colx))
                elif rc == XL_LABEL_B2:
                    rowx, colx, cell_attr = local_unpack('<HH3s', data[0:7])
                    strg = unpack_string(data, 7, bk.encoding or bk.derive_encoding(), lenlen=1)
                    self_put_cell(rowx, colx, XL_CELL_TEXT, strg, self.fixed_BIFF2_xfindex(cell_attr, rowx, colx))
                elif rc == XL_BOOLERR_B2:
                    rowx, colx, cell_attr, value, is_err = local_unpack('<HH3sBB', data)
                    cellty = (XL_CELL_BOOLEAN, XL_CELL_ERROR)[is_err]
                    # if DEBUG: print "XL_BOOLERR_B2", rowx, colx, cell_attr, value, is_err
                    self_put_cell(rowx, colx, cellty, value, self.fixed_BIFF2_xfindex(cell_attr, rowx, colx))
                elif rc == XL_BLANK_B2:
                    if not fmt_info: continue
                    rowx, colx, cell_attr = local_unpack('<HH3s', data[:7])
                    self_put_cell(rowx, colx, XL_CELL_BLANK, '', self.fixed_BIFF2_xfindex(cell_attr, rowx, colx))
                elif rc == XL_EFONT:
                    bk.handle_efont(data)
                elif rc == XL_ROW_B2:
                    if not fmt_info: continue
                    rowx, bits1, bits2 = local_unpack('<H4xH2xB', data[0:11])
                    if not(0 <= rowx < self.utter_max_rows):
                        print("*** NOTE: ROW_B2 record has row index %d; " \
                            "should have 0 <= rowx < %d -- record ignored!" \
                            % (rowx, self.utter_max_rows), file=self.logfile)
                        continue
                    if not (bits2 & 1):  # has_default_xf_index is false
                        xf_index = -1
                    elif data_len == 18:
                        # Seems the XF index in the cell_attr is dodgy
                         xfx = local_unpack('<H', data[16:18])[0]
                         xf_index = self.fixed_BIFF2_xfindex(cell_attr=None, rowx=rowx, colx=-1, true_xfx=xfx)
                    else:
                        cell_attr = data[13:16]
                        xf_index = self.fixed_BIFF2_xfindex(cell_attr, rowx, colx=-1)
                    key = (bits1, bits2, xf_index)
                    r = rowinfo_sharing_dict.get(key)
                    if r is None:
                        rowinfo_sharing_dict[key] = r = Rowinfo()
                        r.height = bits1 & 0x7fff
                        r.has_default_height = (bits1 >> 15) & 1
                        r.has_default_xf_index = bits2 & 1
                        r.xf_index = xf_index
                        # r.outline_level = 0             # set in __init__
                        # r.outline_group_starts_ends = 0 # set in __init__
                        # r.hidden = 0                    # set in __init__
                        # r.height_mismatch = 0           # set in __init__
                        # r.additional_space_above = 0    # set in __init__
                        # r.additional_space_below = 0    # set in __init__
                    self.rowinfo_map[rowx] = r
                    if 0 and r.xf_index > -1:
                        fprintf(self.logfile,
                            "**ROW %d %d %d\n",
                            self.number, rowx, r.xf_index)
                    if blah_rows:
                        print('ROW_B2', rowx, bits1, has_defaults, file=self.logfile)
                        r.dump(self.logfile,
                            header="--- sh #%d, rowx=%d ---" % (self.number, rowx))
                elif rc == XL_COLWIDTH: # BIFF2 only
                    if not fmt_info: continue
                    first_colx, last_colx, width\
                        = local_unpack("<BBH", data[:4])
                    if not(first_colx <= last_colx):
                        print("*** NOTE: COLWIDTH record has first col index %d, last %d; " \
                            "should have first <= last -- record ignored!" \
                            % (first_colx, last_colx), file=self.logfile)
                        continue
                    for colx in xrange(first_colx, last_colx+1):
                        if colx in self.colinfo_map:
                            c = self.colinfo_map[colx]
                        else:
                            c = Colinfo()
                            self.colinfo_map[colx] = c
                        c.width = width
                    if blah:
                        fprintf(
                            self.logfile,
                            "COLWIDTH sheet #%d cols %d-%d: wid=%d\n",
                            self.number, first_colx, last_colx, width
                            )
                elif rc == XL_COLUMNDEFAULT: # BIFF2 only
                    if not fmt_info: continue
                    first_colx, last_colx = local_unpack("<HH", data[:4])
                    #### Warning OOo docs wrong; first_colx <= colx < last_colx
                    if blah:
                        fprintf(
                            self.logfile,
                            "COLUMNDEFAULT sheet #%d cols in range(%d, %d)\n",
                            self.number, first_colx, last_colx
                            )
                    if not(0 <= first_colx < last_colx <= 256):
                        print("*** NOTE: COLUMNDEFAULT record has first col index %d, last %d; " \
                            "should have 0 <= first < last <= 256" \
                            % (first_colx, last_colx), file=self.logfile)
                        last_colx = min(last_colx, 256)
                    for colx in xrange(first_colx, last_colx):
                        offset = 4 + 3 * (colx - first_colx)
                        cell_attr = data[offset:offset+3]
                        xf_index = self.fixed_BIFF2_xfindex(cell_attr, rowx=-1, colx=colx)
                        if colx in self.colinfo_map:
                            c = self.colinfo_map[colx]
                        else:
                            c = Colinfo()
                            self.colinfo_map[colx] = c
                        c.xf_index = xf_index
                elif rc == XL_WINDOW2_B2: # BIFF 2 only
                    attr_names = ("show_formulas", "show_grid_lines", "show_sheet_headers",
                        "panes_are_frozen", "show_zero_values")
                    for attr, char in zip(attr_names, data[0:5]):
                        setattr(self, attr, int(char != b'\0'))
                    (self.first_visible_rowx, self.first_visible_colx,
                    self.automatic_grid_line_colour,
                    ) = unpack("<HHB", data[5:10])
                    self.gridline_colour_rgb = unpack("<BBB", data[10:13])
                    self.gridline_colour_index = nearest_colour_index(
                        self.book.colour_map, self.gridline_colour_rgb, debug=0)
                    self.cached_page_break_preview_mag_factor = 0 # default (60%)
                    self.cached_normal_view_mag_factor = 0 # default (100%)
            else:
                # if DEBUG: print "SHEET.READ: Unhandled record type %02x %d bytes %r" % (rc, data_len, data)
                pass
        if not eof_found:
            raise XLRDError("Sheet %d (%r) missing EOF record" \
                % (self.number, self.name))
        self.tidy_dimensions()
        self.update_cooked_mag_factors()
        bk._position = oldpos
        return 1
    
    def string_record_contents(self, data):
        bv = self.biff_version
        bk = self.book
        lenlen = (bv >= 30) + 1
        nchars_expected = unpack("<" + "BH"[lenlen - 1], data[:lenlen])[0]
        offset = lenlen
        if bv < 80:
            enc = bk.encoding or bk.derive_encoding()
        nchars_found = 0
        result = UNICODE_LITERAL("")
        while 1:
            if bv >= 80:
                flag = BYTES_ORD(data[offset]) & 1
                enc = ("latin_1", "utf_16_le")[flag]
                offset += 1
            chunk = unicode(data[offset:], enc)
            result += chunk
            nchars_found += len(chunk)
            if nchars_found == nchars_expected:
                return result
            if nchars_found > nchars_expected:
                msg = ("STRING/CONTINUE: expected %d chars, found %d" 
                    % (nchars_expected, nchars_found))
                raise XLRDError(msg)
            rc, _unused_len, data = bk.get_record_parts()
            if rc != XL_CONTINUE:
                raise XLRDError(
                    "Expected CONTINUE record; found record-type 0x%04X" % rc)
            offset = 0

    def update_cooked_mag_factors(self):
        # Cached values are used ONLY for the non-active view mode.
        # When the user switches to the non-active view mode,
        # if the cached value for that mode is not valid,
        # Excel pops up a window which says:
        # "The number must be between 10 and 400. Try again by entering a number in this range."
        # When the user hits OK, it drops into the non-active view mode
        # but uses the magn from the active mode.
        # NOTE: definition of "valid" depends on mode ... see below
        blah = DEBUG or self.verbosity > 0
        if self.show_in_page_break_preview:
            if self.scl_mag_factor is None: # no SCL record
                self.cooked_page_break_preview_mag_factor = 100 # Yes, 100, not 60, NOT a typo
            else:
                self.cooked_page_break_preview_mag_factor = self.scl_mag_factor
            zoom = self.cached_normal_view_mag_factor
            if not (10 <= zoom <=400):
                if blah:
                    print((
                        "WARNING *** WINDOW2 rcd sheet %d: Bad cached_normal_view_mag_factor: %d"
                        % (self.number, self.cached_normal_view_mag_factor)
                        ), file=self.logfile)
                zoom = self.cooked_page_break_preview_mag_factor
            self.cooked_normal_view_mag_factor = zoom
        else:
            # normal view mode
            if self.scl_mag_factor is None: # no SCL record
                self.cooked_normal_view_mag_factor = 100
            else:
                self.cooked_normal_view_mag_factor = self.scl_mag_factor
            zoom = self.cached_page_break_preview_mag_factor
            if zoom == 0:
                # VALID, defaults to 60
                zoom = 60
            elif not (10 <= zoom <= 400):
                if blah:
                    print((
                        "WARNING *** WINDOW2 rcd sheet %r: Bad cached_page_break_preview_mag_factor: %r"
                        % (self.number, self.cached_page_break_preview_mag_factor)
                        ), file=self.logfile)
                zoom = self.cooked_normal_view_mag_factor
            self.cooked_page_break_preview_mag_factor = zoom

    def fixed_BIFF2_xfindex(self, cell_attr, rowx, colx, true_xfx=None):
        DEBUG = 0
        blah = DEBUG or self.verbosity >= 2
        if self.biff_version == 21:
            if self.book.xf_list:
                if true_xfx is not None:
                    xfx = true_xfx
                else:
                    xfx = BYTES_ORD(cell_attr[0]) & 0x3F
                if xfx == 0x3F:
                    if self._ixfe is None:
                        raise XLRDError("BIFF2 cell record has XF index 63 but no preceding IXFE record.")
                    xfx = self._ixfe
                    # OOo docs are capable of interpretation that each
                    # cell record is preceded immediately by its own IXFE record.
                    # Empirical evidence is that (sensibly) an IXFE record applies to all
                    # following cell records until another IXFE comes along.
                return xfx
            # Have either Excel 2.0, or broken 2.1 w/o XF records -- same effect.
            self.biff_version = self.book.biff_version = 20
        #### check that XF slot in cell_attr is zero
        xfx_slot = BYTES_ORD(cell_attr[0]) & 0x3F
        assert xfx_slot == 0
        xfx = self._cell_attr_to_xfx.get(cell_attr)
        if xfx is not None:
            return xfx
        if blah:
            fprintf(self.logfile, "New cell_attr %r at (%r, %r)\n", cell_attr, rowx, colx)
        if not self.book.xf_list:
            for xfx in xrange(16):
                self.insert_new_BIFF20_xf(cell_attr=b"\x40\x00\x00", style=xfx < 15)
        xfx = self.insert_new_BIFF20_xf(cell_attr=cell_attr)
        return xfx

    def insert_new_BIFF20_xf(self, cell_attr, style=0):
        DEBUG = 0
        blah = DEBUG or self.verbosity >= 2
        book = self.book
        xfx = len(book.xf_list)
        xf = self.fake_XF_from_BIFF20_cell_attr(cell_attr, style)
        xf.xf_index = xfx
        book.xf_list.append(xf)
        if blah:
            xf.dump(self.logfile, header="=== Faked XF %d ===" % xfx, footer="======")
        if xf.format_key not in book.format_map:
            if xf.format_key:
                msg = "ERROR *** XF[%d] unknown format key (%d, 0x%04x)\n"
                fprintf(self.logfile, msg,
                        xf.xf_index, xf.format_key, xf.format_key)
            fmt = Format(xf.format_key, FUN, UNICODE_LITERAL("General"))
            book.format_map[xf.format_key] = fmt
            book.format_list.append(fmt)
        cellty_from_fmtty = {
            FNU: XL_CELL_NUMBER,
            FUN: XL_CELL_NUMBER,
            FGE: XL_CELL_NUMBER,
            FDT: XL_CELL_DATE,
            FTX: XL_CELL_NUMBER, # Yes, a number can be formatted as text.
            }
        fmt = book.format_map[xf.format_key]
        cellty = cellty_from_fmtty[fmt.type]
        self._xf_index_to_xl_type_map[xf.xf_index] = cellty
        self._cell_attr_to_xfx[cell_attr] = xfx
        return xfx

    def fake_XF_from_BIFF20_cell_attr(self, cell_attr, style=0):
        from .formatting import XF, XFAlignment, XFBorder, XFBackground, XFProtection
        xf = XF()
        xf.alignment = XFAlignment()
        xf.alignment.indent_level = 0
        xf.alignment.shrink_to_fit = 0
        xf.alignment.text_direction = 0
        xf.border = XFBorder()
        xf.border.diag_up = 0
        xf.border.diag_down = 0
        xf.border.diag_colour_index = 0
        xf.border.diag_line_style = 0 # no line
        xf.background = XFBackground()
        xf.protection = XFProtection()
        (prot_bits, font_and_format, halign_etc) = unpack('<BBB', cell_attr)
        xf.format_key = font_and_format & 0x3F
        xf.font_index = (font_and_format & 0xC0) >> 6
        upkbits(xf.protection, prot_bits, (
            (6, 0x40, 'cell_locked'),
            (7, 0x80, 'formula_hidden'),
            ))
        xf.alignment.hor_align = halign_etc & 0x07
        for mask, side in ((0x08, 'left'), (0x10, 'right'), (0x20, 'top'), (0x40, 'bottom')):
            if halign_etc & mask:
                colour_index, line_style = 8, 1 # black, thin
            else:
                colour_index, line_style = 0, 0 # none, none
            setattr(xf.border, side + '_colour_index', colour_index)
            setattr(xf.border, side + '_line_style', line_style)
        bg = xf.background
        if halign_etc & 0x80:
            bg.fill_pattern = 17
        else:
            bg.fill_pattern = 0
        bg.background_colour_index = 9 # white
        bg.pattern_colour_index = 8 # black
        xf.parent_style_index = (0x0FFF, 0)[style]
        xf.alignment.vert_align = 2 # bottom
        xf.alignment.rotation = 0
        for attr_stem in \
            "format font alignment border background protection".split():
            attr = "_" + attr_stem + "_flag"
            setattr(xf, attr, 1)
        return xf

    def req_fmt_info(self):
        if not self.formatting_info:
            raise XLRDError("Feature requires open_workbook(..., formatting_info=True)")

    ##
    # Determine column display width.
    # <br /> -- New in version 0.6.1
    # <br />
    # @param colx Index of the queried column, range 0 to 255.
    # Note that it is possible to find out the width that will be used to display
    # columns with no cell information e.g. column IV (colx=255).
    # @return The column width that will be used for displaying
    # the given column by Excel, in units of 1/256th of the width of a
    # standard character (the digit zero in the first font).

    def computed_column_width(self, colx):
        self.req_fmt_info()
        if self.biff_version >= 80:
            colinfo = self.colinfo_map.get(colx, None)
            if colinfo is not None:
                return colinfo.width
            if self.standardwidth is not None:
                return self.standardwidth
        elif self.biff_version >= 40:
            if self.gcw[colx]:
                if self.standardwidth is not None:
                    return self.standardwidth
            else:
                colinfo = self.colinfo_map.get(colx, None)
                if colinfo is not None:
                    return colinfo.width
        elif self.biff_version == 30:
            colinfo = self.colinfo_map.get(colx, None)
            if colinfo is not None:
                return colinfo.width
        # All roads lead to Rome and the DEFCOLWIDTH ...
        if self.defcolwidth is not None:
            return self.defcolwidth * 256
        return 8 * 256 # 8 is what Excel puts in a DEFCOLWIDTH record

    def handle_hlink(self, data):
        # DEBUG = 1
        if DEBUG: print("\n=== hyperlink ===", file=self.logfile)
        record_size = len(data)
        h = Hyperlink()
        h.frowx, h.lrowx, h.fcolx, h.lcolx, guid0, dummy, options = unpack('<HHHH16s4si', data[:32])
        assert guid0 == b"\xD0\xC9\xEA\x79\xF9\xBA\xCE\x11\x8C\x82\x00\xAA\x00\x4B\xA9\x0B"
        assert dummy == b"\x02\x00\x00\x00"
        if DEBUG: print("options: %08X" % options, file=self.logfile)
        offset = 32

        def get_nul_terminated_unicode(buf, ofs):
            nb = unpack('<L', buf[ofs:ofs+4])[0] * 2
            ofs += 4
            uc = unicode(buf[ofs:ofs+nb], 'UTF-16le')[:-1]
            ofs += nb
            return uc, ofs

        if options & 0x14: # has a description
            h.desc, offset = get_nul_terminated_unicode(data, offset)
            
        if options & 0x80: # has a target
            h.target, offset = get_nul_terminated_unicode(data, offset)
            
        if (options & 1) and not (options & 0x100): # HasMoniker and not MonikerSavedAsString
            # an OLEMoniker structure
            clsid, = unpack('<16s', data[offset:offset + 16])
            if DEBUG: fprintf(self.logfile, "clsid=%r\n",  clsid)
            offset += 16
            if clsid == b"\xE0\xC9\xEA\x79\xF9\xBA\xCE\x11\x8C\x82\x00\xAA\x00\x4B\xA9\x0B":
                #          E0H C9H EAH 79H F9H BAH CEH 11H 8CH 82H 00H AAH 00H 4BH A9H 0BH
                # URL Moniker
                h.type = UNICODE_LITERAL('url')
                nbytes = unpack('<L', data[offset:offset + 4])[0]
                offset += 4
                h.url_or_path = unicode(data[offset:offset + nbytes], 'UTF-16le')
                if DEBUG: fprintf(self.logfile, "initial url=%r len=%d\n", h.url_or_path, len(h.url_or_path))
                endpos = h.url_or_path.find('\x00')
                if DEBUG: print("endpos=%d" % endpos, file=self.logfile)
                h.url_or_path = h.url_or_path[:endpos]
                true_nbytes = 2 * (endpos + 1)
                offset += true_nbytes
                extra_nbytes = nbytes - true_nbytes
                extra_data = data[offset:offset + extra_nbytes]
                offset += extra_nbytes
                if DEBUG: 
                    fprintf(
                        self.logfile,
                        "url=%r\nextra=%r\nnbytes=%d true_nbytes=%d extra_nbytes=%d\n",
                        h.url_or_path, extra_data, nbytes, true_nbytes, extra_nbytes,
                        )
                assert extra_nbytes in (24, 0)
            elif clsid == b"\x03\x03\x00\x00\x00\x00\x00\x00\xC0\x00\x00\x00\x00\x00\x00\x46":
                # file moniker
                h.type = UNICODE_LITERAL('local file')
                uplevels, nbytes = unpack("<Hi", data[offset:offset + 6])
                offset += 6
                shortpath = b"..\\" * uplevels + data[offset:offset + nbytes - 1] #### BYTES, not unicode
                if DEBUG: fprintf(self.logfile, "uplevels=%d shortpath=%r\n", uplevels, shortpath)
                offset += nbytes
                offset += 24 # OOo: "unknown byte sequence"
                # above is version 0xDEAD + 20 reserved zero bytes
                sz = unpack('<i', data[offset:offset + 4])[0]
                if DEBUG: print("sz=%d" % sz, file=self.logfile)
                offset += 4
                if sz:
                    xl = unpack('<i', data[offset:offset + 4])[0]
                    offset += 4
                    offset += 2 # "unknown byte sequence" MS: 0x0003
                    extended_path = unicode(data[offset:offset + xl], 'UTF-16le') # not zero-terminated
                    offset += xl
                    h.url_or_path = extended_path
                else:
                    h.url_or_path = shortpath
                    #### MS KLUDGE WARNING ####
                    # The "shortpath" is bytes encoded in the **UNKNOWN** creator's "ANSI" encoding.
            else:
                fprintf(self.logfile, "*** unknown clsid %r\n", clsid)
        elif options & 0x163 == 0x103: # UNC
            h.type = UNICODE_LITERAL('unc')
            h.url_or_path, offset = get_nul_terminated_unicode(data, offset)
        elif options & 0x16B == 8:
            h.type = UNICODE_LITERAL('workbook')
        else:
            h.type = UNICODE_LITERAL('unknown')
            
        if options & 0x8: # has textmark
            h.textmark, offset = get_nul_terminated_unicode(data, offset)

        if DEBUG:
            h.dump(header="... object dump ...") 
            print("offset=%d record_size=%d" % (offset, record_size))
            
        extra_nbytes = record_size - offset
        if extra_nbytes > 0:
            fprintf(
                self.logfile,
                "*** WARNING: hyperlink at r=%d c=%d has %d extra data bytes: %s\n",
                h.frowx,
                h.fcolx,
                extra_nbytes,
                REPR(data[-extra_nbytes:])
                )
            # Seen: b"\x00\x00" also b"A\x00", b"V\x00"
        elif extra_nbytes < 0:        
            raise XLRDError("Bug or corrupt file, send copy of input file for debugging")

        self.hyperlink_list.append(h)
        for rowx in xrange(h.frowx, h.lrowx+1):
            for colx in xrange(h.fcolx, h.lcolx+1):
                self.hyperlink_map[rowx, colx] = h
                
    def handle_quicktip(self, data):
        rcx, frowx, lrowx, fcolx, lcolx = unpack('<5H', data[:10])
        assert rcx == XL_QUICKTIP
        assert self.hyperlink_list
        h = self.hyperlink_list[-1]
        assert (frowx, lrowx, fcolx, lcolx) == (h.frowx, h.lrowx, h.fcolx, h.lcolx)
        assert data[-2:] == b'\x00\x00'
        h.quicktip = unicode(data[10:-2], 'utf_16_le')

    def handle_msodrawingetc(self, recid, data_len, data):
        if not OBJ_MSO_DEBUG:
            return
        DEBUG = 1
        if self.biff_version < 80:
            return
        o = MSODrawing()
        pos = 0
        while pos < data_len:
            tmp, fbt, cb = unpack('<HHI', data[pos:pos+8])
            ver = tmp & 0xF
            inst = (tmp >> 4) & 0xFFF
            if ver == 0xF:
                ndb = 0 # container
            else:
                ndb = cb
            if DEBUG:
                hex_char_dump(data, pos, ndb + 8, base=0, fout=self.logfile)
                fprintf(self.logfile,
                    "fbt:0x%04X  inst:%d  ver:0x%X  cb:%d (0x%04X)\n",
                    fbt, inst, ver, cb, cb)
            if fbt == 0xF010: # Client Anchor
                assert ndb == 18
                (o.anchor_unk,
                o.anchor_colx_lo, o.anchor_rowx_lo,
                o.anchor_colx_hi, o.anchor_rowx_hi) = unpack('<Hiiii', data[pos+8:pos+8+ndb])
            elif fbt == 0xF011: # Client Data
                # must be followed by an OBJ record
                assert cb == 0
                assert pos + 8 == data_len
            else:
                pass
            pos += ndb + 8
        else:
            # didn't break out of while loop
            assert pos == data_len
        if DEBUG:
            o.dump(self.logfile, header="=== MSODrawing ===", footer= " ")


    def handle_obj(self, data):
        if self.biff_version < 80:
            return None
        o = MSObj()
        data_len = len(data)
        pos = 0
        if OBJ_MSO_DEBUG:
            fprintf(self.logfile, "... OBJ record len=%d...\n", data_len)
        while pos < data_len:
            ft, cb = unpack('<HH', data[pos:pos+4])
            if OBJ_MSO_DEBUG:
                fprintf(self.logfile, "pos=%d ft=0x%04X cb=%d\n", pos, ft, cb)
                hex_char_dump(data, pos, cb + 4, base=0, fout=self.logfile)
            if pos == 0 and not (ft == 0x15 and cb == 18):
                if self.verbosity:
                    fprintf(self.logfile, "*** WARNING Ignoring antique or corrupt OBJECT record\n")
                return None
            if ft == 0x15: # ftCmo ... s/b first
                assert pos == 0
                o.type, o.id, option_flags = unpack('<HHH', data[pos+4:pos+10])
                upkbits(o, option_flags, (
                    ( 0, 0x0001, 'locked'),
                    ( 4, 0x0010, 'printable'),
                    ( 8, 0x0100, 'autofilter'), # not documented in Excel 97 dev kit
                    ( 9, 0x0200, 'scrollbar_flag'), # not documented in Excel 97 dev kit
                    (13, 0x2000, 'autofill'),
                    (14, 0x4000, 'autoline'),
                    ))
            elif ft == 0x00:
                if data[pos:data_len] == b'\0' * (data_len - pos):
                    # ignore "optional reserved" data at end of record
                    break
                msg = "Unexpected data at end of OBJECT record"
                fprintf(self.logfile, "*** ERROR %s\n" % msg)
                hex_char_dump(data, pos, data_len - pos, base=0, fout=self.logfile)
                raise XLRDError(msg)
            elif ft == 0x0C: # Scrollbar
                values = unpack('<5H', data[pos+8:pos+18])
                for value, tag in zip(values, ('value', 'min', 'max', 'inc', 'page')):
                    setattr(o, 'scrollbar_' + tag, value)
            elif ft == 0x0D: # "Notes structure" [used for cell comments]
                # not documented in Excel 97 dev kit
                if OBJ_MSO_DEBUG: fprintf(self.logfile, "*** OBJ record has ft==0x0D 'notes' structure\n")
            elif ft == 0x13: # list box data
                if o.autofilter: # non standard exit. NOT documented
                    break
            else:
                pass
            pos += cb + 4
        else:
            # didn't break out of while loop
            pass
        if OBJ_MSO_DEBUG:
            o.dump(self.logfile, header="=== MSOBj ===", footer= " ")
        return o

    def handle_note(self, data, txos):
        if OBJ_MSO_DEBUG:
            fprintf(self.logfile, '... NOTE record ...\n')
            hex_char_dump(data, 0, len(data), base=0, fout=self.logfile)
        o = Note()
        data_len = len(data)
        if self.biff_version < 80:
            o.rowx, o.colx, expected_bytes = unpack('<HHH', data[:6])
            nb = len(data) - 6
            assert nb <= expected_bytes
            pieces = [data[6:]]
            expected_bytes -= nb
            while expected_bytes > 0:
                rc2, data2_len, data2 = self.book.get_record_parts()
                assert rc2 == XL_NOTE
                dummy_rowx, nb = unpack('<H2xH', data2[:6])
                assert dummy_rowx == 0xFFFF
                assert nb == data2_len - 6
                pieces.append(data2[6:])
                expected_bytes -= nb
            assert expected_bytes == 0
            enc = self.book.encoding or self.book.derive_encoding()
            o.text = unicode(b''.join(pieces), enc)
            o.rich_text_runlist = [(0, 0)]
            o.show = 0
            o.row_hidden = 0
            o.col_hidden = 0
            o.author = UNICODE_LITERAL('')
            o._object_id = None
            self.cell_note_map[o.rowx, o.colx] = o        
            return
        # Excel 8.0+
        o.rowx, o.colx, option_flags, o._object_id = unpack('<4H', data[:8])
        o.show = (option_flags >> 1) & 1
        o.row_hidden = (option_flags >> 7) & 1
        o.col_hidden = (option_flags >> 8) & 1
        # XL97 dev kit book says NULL [sic] bytes padding between string count and string data
        # to ensure that string is word-aligned. Appears to be nonsense.
        o.author, endpos = unpack_unicode_update_pos(data, 8, lenlen=2)
        # There is a random/undefined byte after the author string (not counted in the
        # string length).
        # Issue 4 on github: Google Spreadsheet doesn't write the undefined byte.
        assert (data_len - endpos) in (0, 1)
        if OBJ_MSO_DEBUG:
            o.dump(self.logfile, header="=== Note ===", footer= " ")
        txo = txos.get(o._object_id)
        if txo:
            o.text = txo.text
            o.rich_text_runlist = txo.rich_text_runlist
            self.cell_note_map[o.rowx, o.colx] = o        

    def handle_txo(self, data):
        if self.biff_version < 80:
            return
        o = MSTxo()
        data_len = len(data)
        fmt = '<HH6sHHH'
        fmtsize = calcsize(fmt)
        option_flags, o.rot, controlInfo, cchText, cbRuns, o.ifntEmpty = unpack(fmt, data[:fmtsize])
        o.fmla = data[fmtsize:]
        upkbits(o, option_flags, (
            ( 3, 0x000E, 'horz_align'),
            ( 6, 0x0070, 'vert_align'),
            ( 9, 0x0200, 'lock_text'),
            (14, 0x4000, 'just_last'),
            (15, 0x8000, 'secret_edit'),
            ))
        totchars = 0
        o.text = UNICODE_LITERAL('')
        while totchars < cchText:
            rc2, data2_len, data2 = self.book.get_record_parts()
            assert rc2 == XL_CONTINUE
            if OBJ_MSO_DEBUG:
                hex_char_dump(data2, 0, data2_len, base=0, fout=self.logfile)
            nb = BYTES_ORD(data2[0]) # 0 means latin1, 1 means utf_16_le
            nchars = data2_len - 1
            if nb:
                assert nchars % 2 == 0
                nchars //= 2
            utext, endpos = unpack_unicode_update_pos(data2, 0, known_len=nchars)
            assert endpos == data2_len
            o.text += utext
            totchars += nchars
        o.rich_text_runlist = []
        totruns = 0
        while totruns < cbRuns: # counts of BYTES, not runs
            rc3, data3_len, data3 = self.book.get_record_parts()
            # print totruns, cbRuns, rc3, data3_len, repr(data3)
            assert rc3 == XL_CONTINUE
            assert data3_len % 8 == 0
            for pos in xrange(0, data3_len, 8):
                run = unpack('<HH4x', data3[pos:pos+8])
                o.rich_text_runlist.append(run)
                totruns += 8
        # remove trailing entries that point to the end of the string
        while o.rich_text_runlist and o.rich_text_runlist[-1][0] == cchText:
            del o.rich_text_runlist[-1]
        if OBJ_MSO_DEBUG:
            o.dump(self.logfile, header="=== MSTxo ===", footer= " ")
            print(o.rich_text_runlist, file=self.logfile)
        return o

    def handle_feat11(self, data):
        if not OBJ_MSO_DEBUG:
            return
        # rt: Record type; this matches the BIFF rt in the first two bytes of the record; =0872h
        # grbitFrt: FRT cell reference flag (see table below for details)
        # Ref0: Range reference to a worksheet cell region if grbitFrt=1 (bitFrtRef). Otherwise blank.
        # isf: Shared feature type index =5 for Table
        # fHdr: =0 since this is for feat not feat header
        # reserved0: Reserved for future use =0 for Table
        # cref: Count of ref ranges this feature is on
        # cbFeatData: Count of byte for the current feature data.
        # reserved1: =0 currently not used
        # Ref1: Repeat of Ref0. UNDOCUMENTED
        rt, grbitFrt, Ref0, isf, fHdr, reserved0, cref, cbFeatData, reserved1, Ref1 = unpack('<HH8sHBiHiH8s', data[0:35])
        assert reserved0 == 0
        assert reserved1 == 0
        assert isf == 5
        assert rt == 0x872
        assert fHdr == 0
        assert Ref1 == Ref0
        print(self.logfile, "FEAT11: grbitFrt=%d  Ref0=%r cref=%d cbFeatData=%d\n", grbitFrt, Ref0, cref, cbFeatData)
        # lt: Table data source type:
        #   =0 for Excel Worksheet Table =1 for read-write SharePoint linked List
        #   =2 for XML mapper Table =3 for Query Table
        # idList: The ID of the Table (unique per worksheet)
        # crwHeader: How many header/title rows the Table has at the top
        # crwTotals: How many total rows the Table has at the bottom
        # idFieldNext: Next id to try when assigning a unique id to a new field
        # cbFSData: The size of the Fixed Data portion of the Table data structure.
        # rupBuild: the rupBuild that generated the record
        # unusedShort: UNUSED short that can be used later. The value is reserved during round-tripping.
        # listFlags: Collection of bit flags: (see listFlags' bit setting table below for detail.)
        # lPosStmCache: Table data stream position of cached data
        # cbStmCache: Count of bytes of cached data
        # cchStmCache: Count of characters of uncompressed cached data in the stream
        # lem: Table edit mode (see List (Table) Editing Mode (lem) setting table below for details.)
        # rgbHashParam: Hash value for SharePoint Table
        # cchName: Count of characters in the Table name string rgbName
        (lt, idList, crwHeader, crwTotals, idFieldNext, cbFSData,
        rupBuild, unusedShort, listFlags, lPosStmCache, cbStmCache,
        cchStmCache, lem, rgbHashParam, cchName) = unpack('<iiiiiiHHiiiii16sH', data[35:35+66])
        print("lt=%d  idList=%d crwHeader=%d  crwTotals=%d  idFieldNext=%d cbFSData=%d\n"\
            "rupBuild=%d  unusedShort=%d listFlags=%04X  lPosStmCache=%d  cbStmCache=%d\n"\
            "cchStmCache=%d  lem=%d  rgbHashParam=%r  cchName=%d" % (
            lt, idList, crwHeader, crwTotals, idFieldNext, cbFSData,
            rupBuild, unusedShort,listFlags, lPosStmCache, cbStmCache,
            cchStmCache, lem, rgbHashParam, cchName), file=self.logfile)

class MSODrawing(BaseObject):
    pass

class MSObj(BaseObject):
    pass

class MSTxo(BaseObject):
    pass

##    
# <p> Represents a user "comment" or "note".
# Note objects are accessible through Sheet.{@link #Sheet.cell_note_map}.
# <br />-- New in version 0.7.2  
# </p>
class Note(BaseObject):
    ##
    # Author of note
    author = UNICODE_LITERAL('')
    ##
    # True if the containing column is hidden
    col_hidden = 0 
    ##
    # Column index
    colx = 0
    ##
    # List of (offset_in_string, font_index) tuples.
    # Unlike Sheet.{@link #Sheet.rich_text_runlist_map}, the first offset should always be 0.
    rich_text_runlist = None
    ##
    # True if the containing row is hidden
    row_hidden = 0
    ##
    # Row index
    rowx = 0
    ##
    # True if note is always shown
    show = 0
    ##
    # Text of the note
    text = UNICODE_LITERAL('')

##
# <p>Contains the attributes of a hyperlink.
# Hyperlink objects are accessible through Sheet.{@link #Sheet.hyperlink_list}
# and Sheet.{@link #Sheet.hyperlink_map}.
# <br />-- New in version 0.7.2
# </p>   
class Hyperlink(BaseObject):
    ##
    # Index of first row
    frowx = None
    ##
    # Index of last row
    lrowx = None
    ##
    # Index of first column
    fcolx = None
    ##
    # Index of last column
    lcolx = None
    ##
    # Type of hyperlink. Unicode string, one of 'url', 'unc',
    # 'local file', 'workbook', 'unknown'
    type = None
    ##
    # The URL or file-path, depending in the type. Unicode string, except 
    # in the rare case of a local but non-existent file with non-ASCII
    # characters in the name, in which case only the "8.3" filename is available,
    # as a bytes (3.x) or str (2.x) string, <i>with unknown encoding.</i>
    url_or_path = None
    ##
    # Description ... this is displayed in the cell,
    # and should be identical to the cell value. Unicode string, or None. It seems
    # impossible NOT to have a description created by the Excel UI.
    desc = None
    ##
    # Target frame. Unicode string. Note: I have not seen a case of this.
    # It seems impossible to create one in the Excel UI.
    target = None
    ##
    # "Textmark": the piece after the "#" in 
    # "http://docs.python.org/library#struct_module", or the Sheet1!A1:Z99
    # part when type is "workbook".
    textmark = None
    ##
    # The text of the "quick tip" displayed when the cursor
    # hovers over the hyperlink.
    quicktip = None

# === helpers ===

def unpack_RK(rk_str):
    flags = BYTES_ORD(rk_str[0])
    if flags & 2:
        # There's a SIGNED 30-bit integer in there!
        i,  = unpack('<i', rk_str)
        i >>= 2 # div by 4 to drop the 2 flag bits
        if flags & 1:
            return i / 100.0
        return float(i)
    else:
        # It's the most significant 30 bits of an IEEE 754 64-bit FP number
        d, = unpack('<d', b'\0\0\0\0' + BYTES_LITERAL(chr(flags & 252)) + rk_str[1:4])
        if flags & 1:
            return d / 100.0
        return d

##### =============== Cell ======================================== #####

cellty_from_fmtty = {
    FNU: XL_CELL_NUMBER,
    FUN: XL_CELL_NUMBER,
    FGE: XL_CELL_NUMBER,
    FDT: XL_CELL_DATE,
    FTX: XL_CELL_NUMBER, # Yes, a number can be formatted as text.
    }

ctype_text = {
    XL_CELL_EMPTY: 'empty',
    XL_CELL_TEXT: 'text',
    XL_CELL_NUMBER: 'number',
    XL_CELL_DATE: 'xldate',
    XL_CELL_BOOLEAN: 'bool',
    XL_CELL_ERROR: 'error',
    XL_CELL_BLANK: 'blank',
    }

##
# <p>Contains the data for one cell.</p>
#
# <p>WARNING: You don't call this class yourself. You access Cell objects
# via methods of the {@link #Sheet} object(s) that you found in the {@link #Book} object that
# was returned when you called xlrd.open_workbook("myfile.xls").</p>
# <p> Cell objects have three attributes: <i>ctype</i> is an int, <i>value</i>
# (which depends on <i>ctype</i>) and <i>xf_index</i>.
# If "formatting_info" is not enabled when the workbook is opened, xf_index will be None.
# The following table describes the types of cells and how their values
# are represented in Python.</p>
#
# <table border="1" cellpadding="7">
# <tr>
# <th>Type symbol</th>
# <th>Type number</th>
# <th>Python value</th>
# </tr>
# <tr>
# <td>XL_CELL_EMPTY</td>
# <td align="center">0</td>
# <td>empty string u''</td>
# </tr>
# <tr>
# <td>XL_CELL_TEXT</td>
# <td align="center">1</td>
# <td>a Unicode string</td>
# </tr>
# <tr>
# <td>XL_CELL_NUMBER</td>
# <td align="center">2</td>
# <td>float</td>
# </tr>
# <tr>
# <td>XL_CELL_DATE</td>
# <td align="center">3</td>
# <td>float</td>
# </tr>
# <tr>
# <td>XL_CELL_BOOLEAN</td>
# <td align="center">4</td>
# <td>int; 1 means TRUE, 0 means FALSE</td>
# </tr>
# <tr>
# <td>XL_CELL_ERROR</td>
# <td align="center">5</td>
# <td>int representing internal Excel codes; for a text representation,
# refer to the supplied dictionary error_text_from_code</td>
# </tr>
# <tr>
# <td>XL_CELL_BLANK</td>
# <td align="center">6</td>
# <td>empty string u''. Note: this type will appear only when
# open_workbook(..., formatting_info=True) is used.</td>
# </tr>
# </table>
#<p></p>

class Cell(BaseObject):

    __slots__ = ['ctype', 'value', 'xf_index']

    def __init__(self, ctype, value, xf_index=None):
        self.ctype = ctype
        self.value = value
        self.xf_index = xf_index

    def __repr__(self):
        if self.xf_index is None:
            return "%s:%r" % (ctype_text[self.ctype], self.value)
        else:
            return "%s:%r (XF:%r)" % (ctype_text[self.ctype], self.value, self.xf_index)

##
# There is one and only one instance of an empty cell -- it's a singleton. This is it.
# You may use a test like "acell is empty_cell".
empty_cell = Cell(XL_CELL_EMPTY, '')

##### =============== Colinfo and Rowinfo ============================== #####

##
# Width and default formatting information that applies to one or
# more columns in a sheet. Derived from COLINFO records.
#
# <p> Here is the default hierarchy for width, according to the OOo docs:
#
# <br />"""In BIFF3, if a COLINFO record is missing for a column,
# the width specified in the record DEFCOLWIDTH is used instead.
#
# <br />In BIFF4-BIFF7, the width set in this [COLINFO] record is only used,
# if the corresponding bit for this column is cleared in the GCW
# record, otherwise the column width set in the DEFCOLWIDTH record
# is used (the STANDARDWIDTH record is always ignored in this case [see footnote!]).
#
# <br />In BIFF8, if a COLINFO record is missing for a column,
# the width specified in the record STANDARDWIDTH is used.
# If this [STANDARDWIDTH] record is also missing,
# the column width of the record DEFCOLWIDTH is used instead."""
# <br />
#
# Footnote:  The docs on the GCW record say this:
# """<br />
# If a bit is set, the corresponding column uses the width set in the STANDARDWIDTH
# record. If a bit is cleared, the corresponding column uses the width set in the
# COLINFO record for this column.
# <br />If a bit is set, and the worksheet does not contain the STANDARDWIDTH record, or if
# the bit is cleared, and the worksheet does not contain the COLINFO record, the DEFCOLWIDTH
# record of the worksheet will be used instead.
# <br />"""<br />
# At the moment (2007-01-17) xlrd is going with the GCW version of the story.
# Reference to the source may be useful: see the computed_column_width(colx) method
# of the Sheet class.
# <br />-- New in version 0.6.1
# </p>

class Colinfo(BaseObject):
    ##
    # Width of the column in 1/256 of the width of the zero character,
    # using default font (first FONT record in the file).
    width = 0
    ##
    # XF index to be used for formatting empty cells.
    xf_index = -1
    ##
    # 1 = column is hidden
    hidden = 0
    ##
    # Value of a 1-bit flag whose purpose is unknown
    # but is often seen set to 1
    bit1_flag = 0
    ##
    # Outline level of the column, in range(7).
    # (0 = no outline)
    outline_level = 0
    ##
    # 1 = column is collapsed
    collapsed = 0

_USE_SLOTS = 1

##
# <p>Height and default formatting information that applies to a row in a sheet.
# Derived from ROW records.
# <br /> -- New in version 0.6.1</p>
#
# <p><b>height</b>: Height of the row, in twips. One twip == 1/20 of a point.</p>
#
# <p><b>has_default_height</b>: 0 = Row has custom height; 1 = Row has default height.</p>
#
# <p><b>outline_level</b>: Outline level of the row (0 to 7) </p>
#
# <p><b>outline_group_starts_ends</b>: 1 = Outline group starts or ends here (depending on where the
# outline buttons are located, see WSBOOL record [TODO ??]),
# <i>and</i> is collapsed </p>
#
# <p><b>hidden</b>: 1 = Row is hidden (manually, or by a filter or outline group) </p>
#
# <p><b>height_mismatch</b>: 1 = Row height and default font height do not match </p>
#
# <p><b>has_default_xf_index</b>: 1 = the xf_index attribute is usable; 0 = ignore it </p>
#
# <p><b>xf_index</b>: Index to default XF record for empty cells in this row.
# Don't use this if has_default_xf_index == 0. </p>
#
# <p><b>additional_space_above</b>: This flag is set, if the upper border of at least one cell in this row
# or if the lower border of at least one cell in the row above is
# formatted with a thick line style. Thin and medium line styles are not
# taken into account. </p>
#
# <p><b>additional_space_below</b>: This flag is set, if the lower border of at least one cell in this row
# or if the upper border of at least one cell in the row below is
# formatted with a medium or thick line style. Thin line styles are not
# taken into account. </p>

class Rowinfo(BaseObject):

    if _USE_SLOTS:
        __slots__ = (
            "height",
            "has_default_height",
            "outline_level",
            "outline_group_starts_ends",
            "hidden",
            "height_mismatch",
            "has_default_xf_index",
            "xf_index",
            "additional_space_above",
            "additional_space_below",
            )

    def __init__(self):
        self.height = None
        self.has_default_height = None
        self.outline_level = None
        self.outline_group_starts_ends = None
        self.hidden = None
        self.height_mismatch = None
        self.has_default_xf_index = None
        self.xf_index = None
        self.additional_space_above = None
        self.additional_space_below = None

    def __getstate__(self):
        return (
            self.height,
            self.has_default_height,
            self.outline_level,
            self.outline_group_starts_ends,
            self.hidden,
            self.height_mismatch,
            self.has_default_xf_index,
            self.xf_index,
            self.additional_space_above,
            self.additional_space_below,
            )

    def __setstate__(self, state):
        (
            self.height,
            self.has_default_height,
            self.outline_level,
            self.outline_group_starts_ends,
            self.hidden,
            self.height_mismatch,
            self.has_default_xf_index,
            self.xf_index,
            self.additional_space_above,
            self.additional_space_below,
            ) = state

########NEW FILE########
__FILENAME__ = timemachine
##
# <p>Copyright (c) 2006-2012 Stephen John Machin, Lingfo Pty Ltd</p>
# <p>This module is part of the xlrd package, which is released under a BSD-style licence.</p>
##

# timemachine.py -- adaptation for single codebase.
# Currently supported: 2.6 to 2.7, 3.2+
# usage: from timemachine import *

from __future__ import print_function
import sys

python_version = sys.version_info[:2] # e.g. version 2.6 -> (2, 6)

if python_version >= (3, 0):
    # Python 3
    BYTES_LITERAL = lambda x: x.encode('latin1')
    UNICODE_LITERAL = lambda x: x
    BYTES_ORD = lambda byte: byte
    from io import BytesIO as BYTES_IO
    def fprintf(f, fmt, *vargs):
        fmt = fmt.replace("%r", "%a")
        if fmt.endswith('\n'):
            print(fmt[:-1] % vargs, file=f)
        else:
            print(fmt % vargs, end=' ', file=f)        
    EXCEL_TEXT_TYPES = (str, bytes, bytearray) # xlwt: isinstance(obj, EXCEL_TEXT_TYPES)
    REPR = ascii
    xrange = range
    unicode = lambda b, enc: b.decode(enc)
    ensure_unicode = lambda s: s
    unichr = chr
else:
    # Python 2
    BYTES_LITERAL = lambda x: x
    UNICODE_LITERAL = lambda x: x.decode('latin1')
    BYTES_ORD = ord
    from cStringIO import StringIO as BYTES_IO
    def fprintf(f, fmt, *vargs):
        if fmt.endswith('\n'):
            print(fmt[:-1] % vargs, file=f)
        else:
            print(fmt % vargs, end=' ', file=f)        
    try:
        EXCEL_TEXT_TYPES = basestring # xlwt: isinstance(obj, EXCEL_TEXT_TYPES)
    except NameError:
        EXCEL_TEXT_TYPES = (str, unicode)
    REPR = repr
    xrange = xrange
    # following used only to overcome 2.x ElementTree gimmick which
    # returns text as `str` if it's ascii, otherwise `unicode`
    ensure_unicode = unicode # used only in xlsx.py 

########NEW FILE########
__FILENAME__ = xldate
# -*- coding: cp1252 -*-

# No part of the content of this file was derived from the works of David Giffin.

##
# <p>Copyright � 2005-2008 Stephen John Machin, Lingfo Pty Ltd</p>
# <p>This module is part of the xlrd package, which is released under a BSD-style licence.</p>
#
# <p>Provides function(s) for dealing with Microsoft Excel � dates.</p>
##

# 2008-10-18 SJM Fix bug in xldate_from_date_tuple (affected some years after 2099)

# The conversion from days to (year, month, day) starts with
# an integral "julian day number" aka JDN.
# FWIW, JDN 0 corresponds to noon on Monday November 24 in Gregorian year -4713.
# More importantly:
#    Noon on Gregorian 1900-03-01 (day 61 in the 1900-based system) is JDN 2415080.0
#    Noon on Gregorian 1904-01-02 (day  1 in the 1904-based system) is JDN 2416482.0
import datetime

_JDN_delta = (2415080 - 61, 2416482 - 1)
assert _JDN_delta[1] - _JDN_delta[0] == 1462

# Pre-calculate the datetime epochs for efficiency.
epoch_1904 = datetime.datetime(1904, 1, 1)
epoch_1900 = datetime.datetime(1899, 12, 31)
epoch_1900_minus_1 = datetime.datetime(1899, 12, 30)

class XLDateError(ValueError): pass

class XLDateNegative(XLDateError): pass
class XLDateAmbiguous(XLDateError): pass
class XLDateTooLarge(XLDateError): pass
class XLDateBadDatemode(XLDateError): pass
class XLDateBadTuple(XLDateError): pass

_XLDAYS_TOO_LARGE = (2958466, 2958466 - 1462) # This is equivalent to 10000-01-01

##
# Convert an Excel number (presumed to represent a date, a datetime or a time) into
# a tuple suitable for feeding to datetime or mx.DateTime constructors.
# @param xldate The Excel number
# @param datemode 0: 1900-based, 1: 1904-based.
# <br>WARNING: when using this function to
# interpret the contents of a workbook, you should pass in the Book.datemode
# attribute of that workbook. Whether
# the workbook has ever been anywhere near a Macintosh is irrelevant.
# @return Gregorian (year, month, day, hour, minute, nearest_second).
# <br>Special case: if 0.0 <= xldate < 1.0, it is assumed to represent a time;
# (0, 0, 0, hour, minute, second) will be returned.
# <br>Note: 1904-01-01 is not regarded as a valid date in the datemode 1 system; its "serial number"
# is zero.
# @throws XLDateNegative xldate < 0.00
# @throws XLDateAmbiguous The 1900 leap-year problem (datemode == 0 and 1.0 <= xldate < 61.0)
# @throws XLDateTooLarge Gregorian year 10000 or later
# @throws XLDateBadDatemode datemode arg is neither 0 nor 1
# @throws XLDateError Covers the 4 specific errors

def xldate_as_tuple(xldate, datemode):
    if datemode not in (0, 1):
        raise XLDateBadDatemode(datemode)
    if xldate == 0.00:
        return (0, 0, 0, 0, 0, 0)
    if xldate < 0.00:
        raise XLDateNegative(xldate)
    xldays = int(xldate)
    frac = xldate - xldays
    seconds = int(round(frac * 86400.0))
    assert 0 <= seconds <= 86400
    if seconds == 86400:
        hour = minute = second = 0
        xldays += 1
    else:
        # second = seconds % 60; minutes = seconds // 60
        minutes, second = divmod(seconds, 60)
        # minute = minutes % 60; hour    = minutes // 60
        hour, minute = divmod(minutes, 60)
    if xldays >= _XLDAYS_TOO_LARGE[datemode]:
        raise XLDateTooLarge(xldate)

    if xldays == 0:
        return (0, 0, 0, hour, minute, second)

    if xldays < 61 and datemode == 0:
        raise XLDateAmbiguous(xldate)

    jdn = xldays + _JDN_delta[datemode]
    yreg = ((((jdn * 4 + 274277) // 146097) * 3 // 4) + jdn + 1363) * 4 + 3
    mp = ((yreg % 1461) // 4) * 535 + 333
    d = ((mp % 16384) // 535) + 1
    # mp /= 16384
    mp >>= 14
    if mp >= 10:
        return ((yreg // 1461) - 4715, mp - 9, d, hour, minute, second)
    else:
        return ((yreg // 1461) - 4716, mp + 3, d, hour, minute, second)


##
# Convert an Excel date/time number into a datetime.datetime object.
#
# @param xldate The Excel number
# @param datemode 0: 1900-based, 1: 1904-based.
#
# @return a datetime.datetime() object.
#
def xldate_as_datetime(xldate, datemode):
    """Convert an Excel date/time number into a datetime.datetime object."""

    # Set the epoch based on the 1900/1904 datemode.
    if datemode:
        epoch = epoch_1904
    else:
        if xldate < 60:
            epoch = epoch_1900
        else:
            # Workaround Excel 1900 leap year bug by adjusting the epoch.
            epoch = epoch_1900_minus_1

    # The integer part of the Excel date stores the number of days since
    # the epoch and the fractional part stores the percentage of the day.
    days = int(xldate)
    fraction = xldate - days

    # Get the the integer and decimal seconds in Excel's millisecond resolution.
    seconds = int(round(fraction * 86400000.0))
    seconds, milliseconds = divmod(seconds, 1000)

    return epoch + datetime.timedelta(days, seconds, 0, milliseconds)


# === conversions from date/time to xl numbers

def _leap(y):
    if y % 4: return 0
    if y % 100: return 1
    if y % 400: return 0
    return 1

_days_in_month = (None, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)

##
# Convert a date tuple (year, month, day) to an Excel date.
# @param year Gregorian year.
# @param month 1 <= month <= 12
# @param day 1 <= day <= last day of that (year, month)
# @param datemode 0: 1900-based, 1: 1904-based.
# @throws XLDateAmbiguous The 1900 leap-year problem (datemode == 0 and 1.0 <= xldate < 61.0)
# @throws XLDateBadDatemode datemode arg is neither 0 nor 1
# @throws XLDateBadTuple (year, month, day) is too early/late or has invalid component(s)
# @throws XLDateError Covers the specific errors

def xldate_from_date_tuple(date_tuple, datemode):
    """Create an excel date from a tuple of (year, month, day)"""
    year, month, day = date_tuple

    if datemode not in (0, 1):
        raise XLDateBadDatemode(datemode)

    if year == 0 and month == 0 and day == 0:
        return 0.00

    if not (1900 <= year <= 9999):
        raise XLDateBadTuple("Invalid year: %r" % ((year, month, day),))
    if not (1 <= month <= 12):
        raise XLDateBadTuple("Invalid month: %r" % ((year, month, day),))
    if  day < 1 \
    or (day > _days_in_month[month] and not(day == 29 and month == 2 and _leap(year))):
        raise XLDateBadTuple("Invalid day: %r" % ((year, month, day),))

    Yp = year + 4716
    M = month
    if M <= 2:
        Yp = Yp - 1
        Mp = M + 9
    else:
        Mp = M - 3
    jdn = (1461 * Yp // 4) + ((979 * Mp + 16) // 32) + \
        day - 1364 - (((Yp + 184) // 100) * 3 // 4)
    xldays = jdn - _JDN_delta[datemode]
    if xldays <= 0:
        raise XLDateBadTuple("Invalid (year, month, day): %r" % ((year, month, day),))
    if xldays < 61 and datemode == 0:
        raise XLDateAmbiguous("Before 1900-03-01: %r" % ((year, month, day),))
    return float(xldays)

##
# Convert a time tuple (hour, minute, second) to an Excel "date" value (fraction of a day).
# @param hour 0 <= hour < 24
# @param minute 0 <= minute < 60
# @param second 0 <= second < 60
# @throws XLDateBadTuple Out-of-range hour, minute, or second

def xldate_from_time_tuple(time_tuple):
    """Create an excel date from a tuple of (hour, minute, second)"""
    hour, minute, second = time_tuple
    if 0 <= hour < 24 and 0 <= minute < 60 and 0 <= second < 60:
        return ((second / 60.0 + minute) / 60.0 + hour) / 24.0
    raise XLDateBadTuple("Invalid (hour, minute, second): %r" % ((hour, minute, second),))

##
# Convert a datetime tuple (year, month, day, hour, minute, second) to an Excel date value.
# For more details, refer to other xldate_from_*_tuple functions.
# @param datetime_tuple (year, month, day, hour, minute, second)
# @param datemode 0: 1900-based, 1: 1904-based.

def xldate_from_datetime_tuple(datetime_tuple, datemode):
    return (
        xldate_from_date_tuple(datetime_tuple[:3], datemode)
        +
        xldate_from_time_tuple(datetime_tuple[3:])
        )

########NEW FILE########
__FILENAME__ = xlsx
##
# Portions copyright (c) 2008-2012 Stephen John Machin, Lingfo Pty Ltd
# This module is part of the xlrd package, which is released under a BSD-style licence.
##

from __future__ import print_function, unicode_literals

DEBUG = 0

import sys
import re
from .timemachine import *
from .book import Book, Name
from .biffh import error_text_from_code, XLRDError, XL_CELL_BLANK, XL_CELL_TEXT, XL_CELL_BOOLEAN, XL_CELL_ERROR
from .formatting import is_date_format_string, Format, XF
from .sheet import Sheet

DLF = sys.stdout # Default Log File

ET = None
ET_has_iterparse = False

def ensure_elementtree_imported(verbosity, logfile):
    global ET, ET_has_iterparse
    if ET is not None:
        return
    if "IronPython" in sys.version:
        import xml.etree.ElementTree as ET
        #### 2.7.2.1: fails later with 
        #### NotImplementedError: iterparse is not supported on IronPython. (CP #31923)
    else:
        try: import xml.etree.cElementTree as ET
        except ImportError:
            try: import cElementTree as ET
            except ImportError:
                try: import lxml.etree as ET
                except ImportError:
                    try: import xml.etree.ElementTree as ET
                    except ImportError:
                        try: import elementtree.ElementTree as ET
                        except ImportError:
                            raise Exception("Failed to import an ElementTree implementation")
    if hasattr(ET, 'iterparse'):
        _dummy_stream = BYTES_IO(b'')
        try:
            ET.iterparse(_dummy_stream)
            ET_has_iterparse = True
        except NotImplementedError:
            pass
    if verbosity:
        etree_version = repr([
            (item, getattr(ET, item))
            for item in ET.__dict__.keys()
            if item.lower().replace('_', '') == 'version'
            ])
        print(ET.__file__, ET.__name__, etree_version, ET_has_iterparse, file=logfile)
        
def split_tag(tag):
    pos = tag.rfind('}') + 1
    if pos >= 2:
        return tag[:pos], tag[pos:]
    return '', tag

def augment_keys(adict, uri):
    # uri must already be enclosed in {}
    for x in list(adict.keys()):
        adict[uri + x] = adict[x]

_UPPERCASE_1_REL_INDEX = {} # Used in fast conversion of column names (e.g. "XFD") to indices (16383)
for _x in xrange(26):
    _UPPERCASE_1_REL_INDEX["ABCDEFGHIJKLMNOPQRSTUVWXYZ"[_x]] = _x + 1
for _x in "123456789":
    _UPPERCASE_1_REL_INDEX[_x] = 0
del _x

def cell_name_to_rowx_colx(cell_name, letter_value=_UPPERCASE_1_REL_INDEX):
    # Extract column index from cell name
    # A<row number> => 0, Z =>25, AA => 26, XFD => 16383
    colx = 0
    charx = -1
    try:
        for c in cell_name:
            charx += 1
            lv = letter_value[c]
            if lv:
                colx = colx * 26 + lv
            else: # start of row number; can't be '0'
                colx = colx - 1
                assert 0 <= colx < X12_MAX_COLS
                break
    except KeyError:
        raise Exception('Unexpected character %r in cell name %r' % (c, cell_name))
    rowx = int(cell_name[charx:]) - 1
    return rowx, colx

error_code_from_text = {}
for _code, _text in error_text_from_code.items():
    error_code_from_text[_text] = _code

# === X12 === Excel 2007 .xlsx ===============================================

U_SSML12 = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
U_ODREL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
U_PKGREL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
U_CP = "{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}"
U_DC = "{http://purl.org/dc/elements/1.1/}"
U_DCTERMS = "{http://purl.org/dc/terms/}"
XML_SPACE_ATTR = "{http://www.w3.org/XML/1998/namespace}space"
XML_WHITESPACE = "\t\n \r"
X12_MAX_ROWS = 2 ** 20
X12_MAX_COLS = 2 ** 14
V_TAG = U_SSML12 + 'v' # cell child: value
F_TAG = U_SSML12 + 'f' # cell child: formula
IS_TAG = U_SSML12 + 'is' # cell child: inline string

def unescape(s,
    subber=re.compile(r'_x[0-9A-Fa-f]{4,4}_', re.UNICODE).sub,
    repl=lambda mobj: unichr(int(mobj.group(0)[2:6], 16)),
    ):
    if "_" in s:
        return subber(repl, s)
    return s

def cooked_text(self, elem):
    t = elem.text
    if t is None:
        return ''
    if elem.get(XML_SPACE_ATTR) != 'preserve':
        t = t.strip(XML_WHITESPACE)
    return ensure_unicode(unescape(t))

def get_text_from_si_or_is(self, elem, r_tag=U_SSML12+'r', t_tag=U_SSML12 +'t'):
    "Returns unescaped unicode"
    accum = []
    for child in elem:
        # self.dump_elem(child)
        tag = child.tag
        if tag == t_tag:
            t = cooked_text(self, child)
            if t: # note: .text attribute can be None
                accum.append(t)
        elif tag == r_tag:
            for tnode in child:
                if tnode.tag == t_tag:
                    t = cooked_text(self, tnode)
                    if t:
                        accum.append(t)
    return ''.join(accum)

def map_attributes(amap, elem, obj):
    for xml_attr, obj_attr, cnv_func_or_const in amap:
        if not xml_attr:
            setattr(obj, obj_attr, cnv_func_or_const)
            continue
        if not obj_attr: continue #### FIX ME ####
        raw_value = elem.get(xml_attr)
        cooked_value = cnv_func_or_const(raw_value)
        setattr(obj, obj_attr, cooked_value)

def cnv_ST_Xstring(s):
    if s is None: return ""
    return ensure_unicode(s)

def cnv_xsd_unsignedInt(s):
    if not s:
        return None
    value = int(s)
    assert value >= 0
    return value

def cnv_xsd_boolean(s):
    if not s:
        return 0
    if s in ("1", "true", "on"):
        return 1
    if s in ("0", "false", "off"):
        return 0
    raise ValueError("unexpected xsd:boolean value: %r" % s)


_defined_name_attribute_map = (
    ("name",                "name",         cnv_ST_Xstring, ),
    ("comment",             "",             cnv_ST_Xstring, ),
    ("customMenu",          "",             cnv_ST_Xstring, ),
    ("description",         "",             cnv_ST_Xstring, ),
    ("help",                "",             cnv_ST_Xstring, ),
    ("statusBar",           "",             cnv_ST_Xstring, ),
    ("localSheetId",        "scope",        cnv_xsd_unsignedInt, ),
    ("hidden",              "hidden",       cnv_xsd_boolean, ),
    ("function",            "func",         cnv_xsd_boolean, ),
    ("vbProcedure",         "vbasic",       cnv_xsd_boolean, ),
    ("xlm",                 "macro",        cnv_xsd_boolean, ),
    ("functionGroupId",     "funcgroup",    cnv_xsd_unsignedInt, ),
    ("shortcutKey",         "",             cnv_ST_Xstring,  ),
    ("publishToServer",     "",             cnv_xsd_boolean, ),
    ("workbookParameter",   "",             cnv_xsd_boolean, ),
    ("",                    "any_err",      0,               ),
    ("",                    "any_external", 0,               ),
    ("",                    "any_rel",      0,               ),
    ("",                    "basic_formula_len", 0,          ),
    ("",                    "binary",       0,               ),
    ("",                    "builtin",      0,               ),
    ("",                    "complex",      0,               ),
    ("",                    "evaluated",    0,               ),
    ("",                    "excel_sheet_index", 0,          ),
    ("",                    "excel_sheet_num", 0,            ),
    ("",                    "option_flags", 0,               ),
    ("",                    "result",       None,            ),
    ("",                    "stack",        None,            ),
    )

def make_name_access_maps(bk):
    name_and_scope_map = {} # (name.lower(), scope): Name_object
    name_map = {}           # name.lower() : list of Name_objects (sorted in scope order)
    num_names = len(bk.name_obj_list)
    for namex in xrange(num_names):
        nobj = bk.name_obj_list[namex]
        name_lcase = nobj.name.lower()
        key = (name_lcase, nobj.scope)
        if key in name_and_scope_map:
            msg = 'Duplicate entry %r in name_and_scope_map' % (key, )
            if 0:
                raise XLRDError(msg)
            else:
                if bk.verbosity:
                    print(msg, file=bk.logfile)
        name_and_scope_map[key] = nobj
        if name_lcase in name_map:
            name_map[name_lcase].append((nobj.scope, nobj))
        else:
            name_map[name_lcase] = [(nobj.scope, nobj)]
    for key in name_map.keys():
        alist = name_map[key]
        alist.sort()
        name_map[key] = [x[1] for x in alist]
    bk.name_and_scope_map = name_and_scope_map
    bk.name_map = name_map

class X12General(object):

    def process_stream(self, stream, heading=None):
        if self.verbosity >= 2 and heading is not None:
            fprintf(self.logfile, "\n=== %s ===\n", heading)
        self.tree = ET.parse(stream)
        getmethod = self.tag2meth.get
        for elem in self.tree.getiterator():
            if self.verbosity >= 3:
                self.dump_elem(elem)
            meth = getmethod(elem.tag)
            if meth:
                meth(self, elem)
        self.finish_off()

    def finish_off(self):
        pass

    def dump_elem(self, elem):
        fprintf(self.logfile,
            "===\ntag=%r len=%d attrib=%r text=%r tail=%r\n",
            split_tag(elem.tag)[1], len(elem), elem.attrib, elem.text, elem.tail)

    def dumpout(self, fmt, *vargs):
        text = (12 * ' ' + fmt + '\n') % vargs
        self.logfile.write(text)

class X12Book(X12General):

    def __init__(self, bk, logfile=DLF, verbosity=False):
        self.bk = bk
        self.logfile = logfile
        self.verbosity = verbosity
        self.bk.nsheets = 0
        self.bk.props = {}
        self.relid2path = {}
        self.relid2reltype = {}
        self.sheet_targets = [] # indexed by sheetx
        self.sheetIds = [] # indexed by sheetx

    core_props_menu = {
        U_CP+"lastModifiedBy": ("last_modified_by", cnv_ST_Xstring),
        U_DC+"creator": ("creator", cnv_ST_Xstring),
        U_DCTERMS+"modified": ("modified", cnv_ST_Xstring),
        U_DCTERMS+"created": ("created", cnv_ST_Xstring),
        }

    def process_coreprops(self, stream):
        if self.verbosity >= 2:
            fprintf(self.logfile, "\n=== coreProps ===\n")
        self.tree = ET.parse(stream)
        getmenu = self.core_props_menu.get
        props = {}
        for elem in self.tree.getiterator():
            if self.verbosity >= 3:
                self.dump_elem(elem)
            menu = getmenu(elem.tag)
            if menu:
                attr, func = menu
                value = func(elem.text)
                props[attr] = value
        self.bk.user_name = props.get('last_modified_by') or props.get('creator')
        self.bk.props = props
        if self.verbosity >= 2:
            fprintf(self.logfile, "props: %r\n", props)
        self.finish_off()

    def process_rels(self, stream):
        if self.verbosity >= 2:
            fprintf(self.logfile, "\n=== Relationships ===\n")
        tree = ET.parse(stream)
        r_tag = U_PKGREL + 'Relationship'
        for elem in tree.findall(r_tag):
            rid = elem.get('Id')
            target = elem.get('Target')
            reltype = elem.get('Type').split('/')[-1]
            if self.verbosity >= 2:
                self.dumpout('Id=%r Type=%r Target=%r', rid, reltype, target)
            self.relid2reltype[rid] = reltype
            # self.relid2path[rid] = 'xl/' + target
            if target.startswith('/'):
                self.relid2path[rid]  = target[1:] # drop the /
            else:
                self.relid2path[rid] = 'xl/' + target

    def do_defined_name(self, elem):
        #### UNDER CONSTRUCTION ####
        if 0 and self.verbosity >= 3:
            self.dump_elem(elem)
        nobj = Name()
        bk = self.bk
        nobj.bk = bk
        nobj.name_index = len(bk.name_obj_list)
        bk.name_obj_list.append(nobj)
        nobj.name = elem.get('name')
        nobj.raw_formula = None # compiled bytecode formula -- not in XLSX
        nobj.formula_text = cooked_text(self, elem)
        map_attributes(_defined_name_attribute_map, elem, nobj)
        if nobj.scope is None:
            nobj.scope = -1 # global
        if nobj.name.startswith("_xlnm."):
            nobj.builtin = 1
        if self.verbosity >= 2:
            nobj.dump(header='=== Name object ===')

    def do_defined_names(self, elem):
        for child in elem:
            self.do_defined_name(child)
        make_name_access_maps(self.bk)

    def do_sheet(self, elem):
        bk = self.bk
        sheetx = bk.nsheets
        # print elem.attrib
        rid = elem.get(U_ODREL + 'id')
        sheetId = int(elem.get('sheetId'))
        name = unescape(ensure_unicode(elem.get('name')))
        reltype = self.relid2reltype[rid]
        target = self.relid2path[rid]
        if self.verbosity >= 2:
            self.dumpout(
                'sheetx=%d sheetId=%r rid=%r type=%r name=%r',
                sheetx, sheetId, rid, reltype, name)
        if reltype != 'worksheet':
            if self.verbosity >= 2:
                self.dumpout('Ignoring sheet of type %r (name=%r)', reltype, name)
            return
        state = elem.get('state')
        visibility_map = {
            None: 0,
            'visible': 0,
            'hidden': 1,
            'veryHidden': 2
            }
        bk._sheet_visibility.append(visibility_map[state])
        sheet = Sheet(bk, position=None, name=name, number=sheetx)
        sheet.utter_max_rows = X12_MAX_ROWS
        sheet.utter_max_cols = X12_MAX_COLS
        bk._sheet_list.append(sheet)
        bk._sheet_names.append(name)
        bk.nsheets += 1
        self.sheet_targets.append(target)
        self.sheetIds.append(sheetId)


    def do_workbookpr(self, elem):
        datemode = cnv_xsd_boolean(elem.get('date1904'))
        if self.verbosity >= 2:
            self.dumpout('datemode=%r', datemode)
        self.bk.datemode = datemode

    tag2meth = {
        'definedNames':  do_defined_names,
        'workbookPr':   do_workbookpr,
        'sheet':        do_sheet,
        }
    augment_keys(tag2meth, U_SSML12)

class X12SST(X12General):

    def __init__(self, bk, logfile=DLF, verbosity=0):
        self.bk = bk
        self.logfile = logfile
        self.verbosity = verbosity
        if ET_has_iterparse:
            self.process_stream = self.process_stream_iterparse
        else:
            self.process_stream = self.process_stream_findall
            
    def process_stream_iterparse(self, stream, heading=None):
        if self.verbosity >= 2 and heading is not None:
            fprintf(self.logfile, "\n=== %s ===\n", heading)
        si_tag = U_SSML12 + 'si'
        elemno = -1
        sst = self.bk._sharedstrings
        for event, elem in ET.iterparse(stream):
            if elem.tag != si_tag: continue
            elemno = elemno + 1
            if self.verbosity >= 3:
                fprintf(self.logfile, "element #%d\n", elemno)
                self.dump_elem(elem)
            result = get_text_from_si_or_is(self, elem)
            sst.append(result)                
            elem.clear() # destroy all child elements
        if self.verbosity >= 2:
            self.dumpout('Entries in SST: %d', len(sst))
        if self.verbosity >= 3:
            for x, s in enumerate(sst):
                fprintf(self.logfile, "SST x=%d s=%r\n", x, s)

    def process_stream_findall(self, stream, heading=None):
        if self.verbosity >= 2 and heading is not None:
            fprintf(self.logfile, "\n=== %s ===\n", heading)
        self.tree = ET.parse(stream)
        si_tag = U_SSML12 + 'si'
        elemno = -1
        sst = self.bk._sharedstrings
        for elem in self.tree.findall(si_tag):
            elemno = elemno + 1
            if self.verbosity >= 3:
                fprintf(self.logfile, "element #%d\n", elemno)
                self.dump_elem(elem)
            result = get_text_from_si_or_is(self, elem)
            sst.append(result)
        if self.verbosity >= 2:
            self.dumpout('Entries in SST: %d', len(sst))

class X12Styles(X12General):

    def __init__(self, bk, logfile=DLF, verbosity=0):
        self.bk = bk
        self.logfile = logfile
        self.verbosity = verbosity
        self.xf_counts = [0, 0]
        self.xf_type = None
        self.fmt_is_date = {}
        for x in list(range(14, 23)) + list(range(45, 48)): #### hard-coding FIX ME ####
            self.fmt_is_date[x] = 1
        # dummy entry for XF 0 in case no Styles section
        self.bk._xf_index_to_xl_type_map[0] = 2
        # fill_in_standard_formats(bk) #### pre-integration kludge

    def do_cellstylexfs(self, elem):
        self.xf_type = 0

    def do_cellxfs(self, elem):
        self.xf_type = 1

    def do_numfmt(self, elem):
        formatCode = ensure_unicode(elem.get('formatCode'))
        numFmtId = int(elem.get('numFmtId'))
        is_date = is_date_format_string(self.bk, formatCode)
        self.fmt_is_date[numFmtId] = is_date
        fmt_obj = Format(numFmtId, is_date + 2, formatCode)
        self.bk.format_map[numFmtId] = fmt_obj
        if self.verbosity >= 3:
            self.dumpout('numFmtId=%d formatCode=%r is_date=%d', numFmtId, formatCode, is_date)

    def do_xf(self, elem):
        if self.xf_type != 1:
            #### ignoring style XFs for the moment
            return
        xfx = self.xf_counts[self.xf_type]
        self.xf_counts[self.xf_type] = xfx + 1
        xf = XF()
        self.bk.xf_list.append(xf)
        self.bk.xfcount += 1
        numFmtId = int(elem.get('numFmtId', '0'))
        xf.format_key = numFmtId
        is_date = self.fmt_is_date.get(numFmtId, 0)
        self.bk._xf_index_to_xl_type_map[xfx] = is_date + 2
        if self.verbosity >= 3:
            self.dumpout(
                'xfx=%d numFmtId=%d',
                xfx, numFmtId,
                )
            self.dumpout(repr(self.bk._xf_index_to_xl_type_map))

    tag2meth = {
        'cellStyleXfs': do_cellstylexfs,
        'cellXfs':      do_cellxfs,
        'numFmt':       do_numfmt,
        'xf':           do_xf,
        }
    augment_keys(tag2meth, U_SSML12)

class X12Sheet(X12General):

    def __init__(self, sheet, logfile=DLF, verbosity=0):
        self.sheet = sheet
        self.logfile = logfile
        self.verbosity = verbosity
        self.rowx = -1 # We may need to count them.
        self.bk = sheet.book
        self.sst = self.bk._sharedstrings
        self.merged_cells = sheet.merged_cells
        self.warned_no_cell_name = 0
        self.warned_no_row_num = 0
        if ET_has_iterparse:
            self.process_stream = self.own_process_stream

    def own_process_stream(self, stream, heading=None):
        if self.verbosity >= 2 and heading is not None:
            fprintf(self.logfile, "\n=== %s ===\n", heading)
        getmethod = self.tag2meth.get
        row_tag = U_SSML12 + "row"
        self_do_row = self.do_row
        for event, elem in ET.iterparse(stream):
            if elem.tag == row_tag:
                self_do_row(elem)
                elem.clear() # destroy all child elements (cells)
            elif elem.tag == U_SSML12 + "dimension":
                self.do_dimension(elem)
            elif elem.tag == U_SSML12 + "mergeCell":
                self.do_merge_cell(elem)
        self.finish_off()

    def process_comments_stream(self, stream):
        root = ET.parse(stream).getroot()
        author_list = root[0]
        assert author_list.tag == U_SSML12 + 'authors'
        authors = [elem.text for elem in author_list]
        comment_list = root[1]
        assert comment_list.tag == U_SSML12 + 'commentList'
        cell_note_map = self.sheet.cell_note_map
        from .sheet import Note
        text_tag = U_SSML12 + 'text'
        r_tag = U_SSML12 + 'r'
        t_tag = U_SSML12 + 't'
        for elem in comment_list.findall(U_SSML12 + 'comment'):
            ts = elem.findall('./' + text_tag + '/' + t_tag)
            ts += elem.findall('./' + text_tag + '/' + r_tag + '/' + t_tag)
            ref = elem.get('ref')
            note = Note()
            note.author = authors[int(elem.get('authorId'))]
            note.rowx, note.colx = coords = cell_name_to_rowx_colx(ref)
            note.text = ''
            for t in ts:
                note.text += cooked_text(self, t)
            cell_note_map[coords] = note

    def do_dimension(self, elem):
        ref = elem.get('ref') # example: "A1:Z99" or just "A1"
        if ref:
            # print >> self.logfile, "dimension: ref=%r" % ref
            last_cell_ref = ref.split(':')[-1] # example: "Z99"
            rowx, colx = cell_name_to_rowx_colx(last_cell_ref)
            self.sheet._dimnrows = rowx + 1
            self.sheet._dimncols = colx + 1

    def do_merge_cell(self, elem):
        # The ref attribute should be a cell range like "B1:D5".
        ref = elem.get('ref')
        if ref:
            first_cell_ref, last_cell_ref = ref.split(':')
            first_rowx, first_colx = cell_name_to_rowx_colx(first_cell_ref)
            last_rowx, last_colx = cell_name_to_rowx_colx(last_cell_ref)
            self.merged_cells.append((first_rowx, last_rowx + 1,
                                      first_colx, last_colx + 1))

    def do_row(self, row_elem):
    
        def bad_child_tag(child_tag):
             raise Exception('cell type %s has unexpected child <%s> at rowx=%r colx=%r' % (cell_type, child_tag, rowx, colx))
 
        row_number = row_elem.get('r')
        if row_number is None: # Yes, it's optional.
            self.rowx += 1
            explicit_row_number = 0
            if self.verbosity and not self.warned_no_row_num:
                self.dumpout("no row number; assuming rowx=%d", self.rowx)
                self.warned_no_row_num = 1
        else:
            self.rowx = int(row_number) - 1
            explicit_row_number = 1
        assert 0 <= self.rowx < X12_MAX_ROWS
        rowx = self.rowx
        colx = -1
        if self.verbosity >= 3:
            self.dumpout("<row> row_number=%r rowx=%d explicit=%d",
                row_number, self.rowx, explicit_row_number)
        letter_value = _UPPERCASE_1_REL_INDEX
        for cell_elem in row_elem:
            cell_name = cell_elem.get('r')
            if cell_name is None: # Yes, it's optional.
                colx += 1
                if self.verbosity and not self.warned_no_cell_name:
                    self.dumpout("no cellname; assuming rowx=%d colx=%d", rowx, colx)
                    self.warned_no_cell_name = 1
            else:
                # Extract column index from cell name
                # A<row number> => 0, Z =>25, AA => 26, XFD => 16383
                colx = 0
                charx = -1
                try:
                    for c in cell_name:
                        charx += 1
                        if c == '$':
                            continue
                        lv = letter_value[c]
                        if lv:
                            colx = colx * 26 + lv
                        else: # start of row number; can't be '0'
                            colx = colx - 1
                            assert 0 <= colx < X12_MAX_COLS
                            break
                except KeyError:
                    raise Exception('Unexpected character %r in cell name %r' % (c, cell_name))
                if explicit_row_number and cell_name[charx:] != row_number:
                    raise Exception('cell name %r but row number is %r' % (cell_name, row_number))
            xf_index = int(cell_elem.get('s', '0'))
            cell_type = cell_elem.get('t', 'n')
            tvalue = None
            formula = None
            if cell_type == 'n':
                # n = number. Most frequent type.
                # <v> child contains plain text which can go straight into float()
                # OR there's no text in which case it's a BLANK cell
                for child in cell_elem:
                    child_tag = child.tag
                    if child_tag == V_TAG:
                        tvalue = child.text
                    elif child_tag == F_TAG:
                        formula = cooked_text(self, child)
                    else:
                        raise Exception('unexpected tag %r' % child_tag)
                if not tvalue:
                    if self.bk.formatting_info:
                        self.sheet.put_cell(rowx, colx, XL_CELL_BLANK, '', xf_index)
                else:
                    self.sheet.put_cell(rowx, colx, None, float(tvalue), xf_index)
            elif cell_type == "s":
                # s = index into shared string table. 2nd most frequent type
                # <v> child contains plain text which can go straight into int()
                for child in cell_elem:
                    child_tag = child.tag
                    if child_tag == V_TAG:
                        tvalue = child.text
                    elif child_tag == F_TAG:
                        # formula not expected here, but gnumeric does it.
                        formula = child.text
                    else:
                        bad_child_tag(child_tag)
                if not tvalue:
                    # <c r="A1" t="s"/>
                    if self.bk.formatting_info:
                        self.sheet.put_cell(rowx, colx, XL_CELL_BLANK, '', xf_index)
                else:
                    value = self.sst[int(tvalue)]
                    self.sheet.put_cell(rowx, colx, XL_CELL_TEXT, value, xf_index)
            elif cell_type == "str":
                # str = string result from formula.
                # Should have <f> (formula) child; however in one file, all text cells are str with no formula.
                # <v> child can contain escapes
                for child in cell_elem:
                    child_tag = child.tag
                    if child_tag == V_TAG:
                        tvalue = cooked_text(self, child)
                    elif child_tag == F_TAG:
                        formula = cooked_text(self, child)
                    else:
                        bad_child_tag(child_tag)
                # assert tvalue is not None and formula is not None
                # Yuk. Fails with file created by gnumeric -- no tvalue!
                self.sheet.put_cell(rowx, colx, XL_CELL_TEXT, tvalue, xf_index)
            elif cell_type == "b":
                # b = boolean
                # <v> child contains "0" or "1"
                # Maybe the data should be converted with cnv_xsd_boolean;
                # ECMA standard is silent; Excel 2007 writes 0 or 1
                for child in cell_elem:
                    child_tag = child.tag
                    if child_tag == V_TAG:
                        tvalue = child.text
                    elif child_tag == F_TAG:
                        formula = cooked_text(self, child)
                    else:
                        bad_child_tag(child_tag)
                self.sheet.put_cell(rowx, colx, XL_CELL_BOOLEAN, int(tvalue), xf_index)
            elif cell_type == "e":
                # e = error
                # <v> child contains e.g. "#REF!"
                for child in cell_elem:
                    child_tag = child.tag
                    if child_tag == V_TAG:
                        tvalue = child.text
                    elif child_tag == F_TAG:
                        formula = cooked_text(self, child)
                    else:
                        bad_child_tag(child_tag)
                value = error_code_from_text[tvalue]
                self.sheet.put_cell(rowx, colx, XL_CELL_ERROR, value, xf_index)
            elif cell_type == "inlineStr":
                # Not expected in files produced by Excel.
                # Only possible child is <is>.
                # It's a way of allowing 3rd party s/w to write text (including rich text) cells
                # without having to build a shared string table
                for child in cell_elem:
                    child_tag = child.tag
                    if child_tag == IS_TAG:
                        tvalue = get_text_from_si_or_is(self, child)
                    else:
                        bad_child_tag(child_tag)
                assert tvalue is not None
                self.sheet.put_cell(rowx, colx, XL_CELL_TEXT, tvalue, xf_index)
            else:
                raise Exception("Unknown cell type %r in rowx=%d colx=%d" % (cell_type, rowx, colx))

    tag2meth = {
        'row':          do_row,
        }
    augment_keys(tag2meth, U_SSML12)

def open_workbook_2007_xml(
    zf,
    component_names,
    logfile=sys.stdout,
    verbosity=0,
    use_mmap=0,
    formatting_info=0,
    on_demand=0,
    ragged_rows=0,
    ):
    ensure_elementtree_imported(verbosity, logfile)
    bk = Book()
    bk.logfile = logfile
    bk.verbosity = verbosity
    bk.formatting_info = formatting_info
    if formatting_info:
        raise NotImplementedError("formatting_info=True not yet implemented")
    bk.use_mmap = False #### Not supported initially
    bk.on_demand = on_demand
    if on_demand:
        if verbosity:
            print("WARNING *** on_demand=True not yet implemented; falling back to False", file=bk.logfile)
        bk.on_demand = False
    bk.ragged_rows = ragged_rows

    x12book = X12Book(bk, logfile, verbosity)
    zflo = zf.open('xl/_rels/workbook.xml.rels')
    x12book.process_rels(zflo)
    del zflo
    zflo = zf.open('xl/workbook.xml')
    x12book.process_stream(zflo, 'Workbook')
    del zflo
    props_name = 'docProps/core.xml'
    if props_name in component_names:
        zflo = zf.open(props_name)
        x12book.process_coreprops(zflo)

    x12sty = X12Styles(bk, logfile, verbosity)
    if 'xl/styles.xml' in component_names:
        zflo = zf.open('xl/styles.xml')
        x12sty.process_stream(zflo, 'styles')
        del zflo
    else:
        # seen in MS sample file MergedCells.xlsx
        pass

    sst_fname = 'xl/sharedStrings.xml'
    x12sst = X12SST(bk, logfile, verbosity)
    if sst_fname in component_names:
        zflo = zf.open(sst_fname)
        x12sst.process_stream(zflo, 'SST')
        del zflo

    for sheetx in range(bk.nsheets):
        fname = x12book.sheet_targets[sheetx]
        zflo = zf.open(fname)
        sheet = bk._sheet_list[sheetx]
        x12sheet = X12Sheet(sheet, logfile, verbosity)
        heading = "Sheet %r (sheetx=%d) from %r" % (sheet.name, sheetx, fname)
        x12sheet.process_stream(zflo, heading)
        del zflo
        comments_fname = 'xl/comments%d.xml' % (sheetx + 1)
        if comments_fname in component_names:
            comments_stream = zf.open(comments_fname)
            x12sheet.process_comments_stream(comments_stream)
            del comments_stream

        sheet.tidy_dimensions()

    return bk

########NEW FILE########
