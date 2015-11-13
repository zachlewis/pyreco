__FILENAME__ = fabfile
"""fabric commands for building sphinx docs

note 1): tested with Fabric 0.9.0

full command: $ fab deploy
"""
import os

from fabric.api import *

cur_dir = os.path.dirname(os.path.abspath(__file__))

def sphinxbuild():
    local('sphinx-build -b html %s %s/html' % \
        (os.path.join(cur_dir, 'source'), 
         os.path.join(cur_dir, 'build')))
        
def create_zip():
    # create zip for pypi, for example
    local('cd %s && zip -r github-cli *' % os.path.join(cur_dir, 'build/html'))

def clean():
    local('rm -rf %s' % os.path.join(cur_dir, 'build'))

def build():
    clean()
    sphinxbuild()
    create_zip()

    
    

    

########NEW FILE########
__FILENAME__ = conf
# -*- coding: utf-8 -*-
#
# github-cli documentation build configuration file, created by
# sphinx-quickstart on Tue May  5 17:40:34 2009.
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
#sys.path.append(os.path.abspath('.'))

# -- General configuration -----------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be extensions
# coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = []

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The encoding of source files.
#source_encoding = 'utf-8'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = u'github-cli'
copyright = u'2009-2012, Sander Smits'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = '1.0'
# The full version, including alpha/beta/rc tags.
release = '1.0.0'

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#language = None

# There are two options for replacing |today|: either, you set today to some
# non-false value, then it is used:
#today = ''
# Else, today_fmt is used as the format for a strftime call.
#today_fmt = '%B %d, %Y'

# List of documents that shouldn't be included in the build.
#unused_docs = []

# List of directories, relative to source directory, that shouldn't be searched
# for source files.
exclude_trees = []

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

# The theme to use for HTML and HTML Help pages.  Major themes that come with
# Sphinx are currently 'default' and 'sphinxdoc'.
html_theme = 'sphinxdoc'

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
#html_use_modindex = True

# If false, no index is generated.
#html_use_index = True

# If true, the index is split into individual pages for each letter.
#html_split_index = False

# If true, links to the reST sources are added to the pages.
#html_show_sourcelink = True

# If true, an OpenSearch description file will be output, and all pages will
# contain a <link> tag referring to it.  The value of this option must be the
# base URL from which the finished HTML is served.
#html_use_opensearch = ''

# If nonempty, this is the file name suffix for HTML files (e.g. ".xhtml").
#html_file_suffix = ''

# Output file base name for HTML help builder.
htmlhelp_basename = 'github-clidoc'


# -- Options for LaTeX output --------------------------------------------------

# The paper size ('letter' or 'a4').
#latex_paper_size = 'letter'

# The font size ('10pt', '11pt' or '12pt').
#latex_font_size = '10pt'

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass [howto/manual]).
latex_documents = [
  ('index', 'github-cli.tex', u'github-cli Documentation',
   u'Sander Smits', 'manual'),
]

# The name of an image file (relative to this directory) to place at the top of
# the title page.
#latex_logo = None

# For "manual" documents, if this is true, then toplevel headings are parts,
# not chapters.
#latex_use_parts = False

# Additional stuff for the LaTeX preamble.
#latex_preamble = ''

# Documents to append as an appendix to all manuals.
#latex_appendices = []

# If false, no module index is generated.
#latex_use_modindex = True

########NEW FILE########
__FILENAME__ = issues
import os
import sys
import urllib
import webbrowser as browser
from optparse import OptionParser

try:
    import simplejson
except ImportError:
    print "error: simplejson required"
    sys.exit(1)

from github.utils import urlopen2, get_remote_info, edit_text, \
    get_remote_info_from_option, get_prog, Pager, wrap_text, get_underline
from github.version import get_version


def smart_unicode(text):
    try:
        return str(text)
    except UnicodeEncodeError:
        return text.encode('utf-8')


def format_issue(issue, verbose=True):
    output = []
    if verbose:
        indent = ""
    else:
        indent = " " * (5 - len(str(issue['number'])))
    title = "%s%s. %s" % (indent, issue['number'], issue['title'])
    title = smart_unicode(title)
    if not verbose:
        output.append(title[:80])
    if verbose:
        title = wrap_text(title)
        output.append(title)
        underline = get_underline(title)
        output.append(underline)
        if issue['body']:
            body = smart_unicode(wrap_text(issue['body']))
            output.append(body)
        output.append("    state: %s" % issue['state'])
        output.append("     user: %s" % issue['user'])
        output.append("    votes: %s" % issue['votes'])
        output.append("  created: %s" % issue['created_at'])
        updated = issue.get('updated_at')
        if updated and not updated == issue['created_at']:
            output.append("  updated: %s" % updated)
        output.append(" comments: %s" % issue.get('comments', 0))
        output.append(" ")
    return output


def format_comment(comment, nr, total):
    timestamp = comment.get("updated_at", comment["created_at"])
    title = "comment %s of %s by %s (%s)" % (nr, total, comment["user"],
        timestamp)
    title = smart_unicode(title)
    output = [title]
    underline = get_underline(title)
    output.append(underline)
    body = smart_unicode(wrap_text(comment['body']))
    output.append(body)
    return output


def pprint_issue(issue, verbose=True):
    lines = format_issue(issue, verbose)
    lines.insert(0, " ") # insert empty first line
    print "\n".join(lines)


def handle_error(result):
    output = []
    for msg in result['error']:
        if msg == result['error'][0]:
            output.append(msg['error'])
        else:
            output.append("error: %s" % msg['error'])
    error_msg = "\n".join(output)
    raise Exception(error_msg)


def validate_number(number, example):
    msg = "number required\nexample: %s" % example
    if not number:
        raise Exception(msg)
    else:
        try:
            int(number)
        except:
            raise Exception(msg)


def get_key(data, key):
    try:
        return data[key]
    except KeyError:
        raise Exception("unexpected failure")


def create_edit_issue(issue=None, text=None):
    main_text = """# Please explain the issue.
# The first line will be used as the title.
# Lines starting with `#` will be ignored."""
    if issue:
        issue['main'] = main_text
        template = """%(title)s
%(body)s
%(main)s
#
#    number:  %(number)s
#      user:  %(user)s
#     votes:  %(votes)s
#     state:  %(state)s
#   created:  %(created_at)s""" % issue
    else:
        template = "\n%s" % main_text
    if text:
        # \n on the command-line becomes \\n; undoing this:
        text = text.replace("\\n", "\n")
    else:
        text = edit_text(template)
        if not text:
            raise Exception("can not submit an empty issue")
    lines = text.splitlines()
    title = lines[0]
    body = "\n".join(lines[1:]).strip()
    return {'title': title, 'body': body}


def create_comment(issue=None, text=None):
    inp = """
# Please enter a comment.
# Lines starting with `#` will be ignored.
#
#    number:  %(number)s
#      user:  %(user)s
#     votes:  %(votes)s
#     state:  %(state)s
#   created:  %(created_at)s""" % issue
    if text:
        # \n on the command-line becomes \\n; undoing this:
        out = text.replace("\\n", "\n")
    else:
        out = edit_text(inp)
    if not out:
        raise Exception("can not submit an empty comment")
    lines = out.splitlines()
    comment = "\n".join(lines).strip()
    return comment


class Commands(object):

    def __init__(self, user, repo):
        self.user = user
        self.repo = repo
        self.url_template = "https://github.com/api/v2/json/issues/%s/%s/%s"

    def search(self, search_term=None, state='open', verbose=False, **kwargs):
        if not search_term:
            example = "%s search experimental" % get_prog()
            msg = "error: search term required\nexample: %s" % example
            print msg
            sys.exit(1)
        search_term_quoted = urllib.quote_plus(search_term)
        search_term_quoted = search_term_quoted.replace(".", "%2E")
        result = self.__submit('search', search_term, state)
        issues = get_key(result, 'issues')
        header = "# searching for '%s' returned %s issues" % (search_term,
            len(issues))
        printer = Pager()
        printer.write(header)
        for issue in issues:
            lines = format_issue(issue, verbose)
            printer.write("\n".join(lines))
        printer.close()

    def list(self, state='open', verbose=False, webbrowser=False, 
            created_by=False, **kwargs):
        if webbrowser:
            issues_url_template = "https://github.com/%s/%s/issues/%s"
            if state == "closed":
                issues_url = issues_url_template % (self.user, self.repo,
                    state)
            else:
                issues_url = issues_url_template % (self.user, self.repo, "")
            try:
                browser.open(issues_url)
            except:
                print "error: opening page in web browser failed"
            else:
                sys.exit(0)

        if state == 'all':
            states = ['open', 'closed']
        else:
            states = [state]
        printer = Pager()
        for st in states:
            header = "# %s issues on %s/%s" % (st, self.user, self.repo)
            printer.write(header)
            result = self.__submit('list', st)
            issues = get_key(result, 'issues')
            if issues:
                for issue in issues:
                    if created_by == False or created_by == issue.get('user'):
                        lines = format_issue(issue, verbose)
                        printer.write("\n".join(lines))
            else:
                printer.write("no %s issues available" % st)
            if not st == states[-1]:
                printer.write() # new line between states
        printer.close()

    def show(self, number=None, verbose=False, webbrowser=False, **kwargs):
        validate_number(number, example="%s show 1" % get_prog())
        if webbrowser:
            issue_url_template = "https://github.com/%s/%s/issues/%s"
            issue_url = issue_url_template % (self.user, self.repo, number)
            try:
                browser.open(issue_url)
            except:
                print "error: opening page in web browser failed"
            else:
                sys.exit(0)

        issue = self.__get_issue(number)
        if not verbose:
            pprint_issue(issue)
        else:
            printer = Pager()
            lines = format_issue(issue, verbose=True)
            lines.insert(0, " ")
            printer.write("\n".join(lines))
            if issue.get("comments", 0) > 0:
                comments = self.__submit('comments', number)
                comments = get_key(comments, 'comments')
                lines = [] # reset
                total = len(comments)
                for i in range(total):
                    comment = comments[i]
                    lines.extend(format_comment(comment, i+1, total))
                    lines.append(" ")
                printer.write("\n".join(lines))
            printer.close()

    def open(self, message=None, **kwargs):
        post_data = create_edit_issue(text=message)
        result = self.__submit('open', data=post_data)
        issue = get_key(result, 'issue')
        pprint_issue(issue)

    def close(self, number=None, **kwargs):
        validate_number(number, example="%s close 1" % get_prog())
        result = self.__submit('close', number)
        issue = get_key(result, 'issue')
        pprint_issue(issue)

    def reopen(self, number=None, **kwargs):
        validate_number(number, example="%s open 1" % get_prog())
        result = self.__submit('reopen', number)
        issue = get_key(result, 'issue')
        pprint_issue(issue)

    def edit(self, number=None, **kwargs):
        validate_number(number, example="%s edit 1" % get_prog())
        gh_issue = self.__get_issue(number)
        output = {'title': gh_issue['title'], 'body': gh_issue['body']}
        post_data = create_edit_issue(gh_issue)
        if post_data['title'] == output['title'] and \
                post_data['body'].splitlines() == output['body'].splitlines():
            print "no changes found"
            sys.exit(1)
        result = self.__submit('edit', number, data=post_data)
        issue = get_key(result, 'issue')
        pprint_issue(issue)

    def label(self, command, label, number=None, **kwargs):
        validate_number(number, example="%s label %s %s 1" % (get_prog(),
            command, label))
        if command not in ['add', 'remove']:
            msg = "label command should use either 'add' or 'remove'\n"\
                "example: %s label add %s %s" % (get_prog(), label, number)
            raise Exception(msg)
        label = urllib.quote(label)
        label = label.replace(".", "%2E") # this is not done by urllib.quote
        result = self.__submit('label/%s' % command, label, number)
        labels = get_key(result, 'labels')
        if labels:
            print "labels for issue #%s:" % number
            for label in labels:
                print "- %s" % label
        else:
            print "no labels found for issue #%s" % number

    def comment(self, number=None, message=None, **kwargs):
        validate_number(number, example="%s comment 1" % get_prog())
        gh_issue = self.__get_issue(number)
        comment = create_comment(issue=gh_issue, text=message)
        post_data = {'comment': comment}
        result = self.__submit('comment', number, data=post_data)
        returned_comment = get_key(result, 'comment')
        if returned_comment:
            print "comment for issue #%s submitted successfully" % number

    def __get_issue(self, number):
        result = self.__submit('show', number)
        return get_key(result, 'issue')

    def __submit(self, action, *args, **kwargs):
        base_url = self.url_template % (action, self.user, self.repo)
        args_list = list(args)
        args_list.insert(0, base_url)
        url = "/".join(args_list)
        page = urlopen2(url, **kwargs)
        result = simplejson.load(page)
        page.close()
        if result.get('error'):
            handle_error(result)
        else:
            return result


def main():
    usage = """usage: %prog command [args] [options]

Examples:
%prog list [-s open|closed|all]       show open, closed or all issues
                                    (default: open)
%prog [-s o|c|a] -v                   same as above, but with issue details
%prog                                 same as: %prog list
%prog -v                              same as: %prog list -v
%prog [-s o|c] -w                     show issues' GitHub page in web browser
                                    (default: open)
%prog list -u <github_user>           show issues created by specified user

%prog show <nr>                       show issue <nr>
%prog show <nr> -v                    same as above, but with comments
%prog <nr>                            same as: %prog show <nr>
%prog <nr> -w                         show issue <nr>'s GitHub page in web
                                    browser
%prog open (o)                        create a new issue (with $EDITOR)
%prog open (o) -m <msg>               create a new issue with <msg> content 
                                    (optionally, use \\n for new lines; first 
                                    line will be the issue title)
%prog close (c) <nr>                  close issue <nr>
%prog open (o) <nr>                   reopen issue <nr>
%prog edit (e) <nr>                   edit issue <nr> (with $EDITOR)
%prog label add (al) <label> <nr>     add <label> to issue <nr>
%prog label remove (rl) <label> <nr>  remove <label> from issue <nr>
%prog search (s) <term>               search for <term> (default: open)
%prog s <term> [-s o|c] -v            same as above, but with details
%prog s <term> -s closed              only search in closed issues
%prog comment (m) <nr>                create a comment for issue <nr>
                                    (with $EDITOR)
%prog comment (m) <nr> -m <msg>       create a comment for issue <nr>
                                    with <msg> content. (optionally use \\n
                                    for new lines)
%prog -r <user>/<repo>                specify a repository (can be used for
                                    all commands)
%prog -r <repo>                       specify a repository (gets user from
                                    global git config)"""

    description = """Description:
command-line interface to GitHub's Issues API (v2)"""

    parser = OptionParser(usage=usage, description=description)
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose",
      default=False, help="show issue details (only for show, list and "\
        "search commands) [default: False]")
    parser.add_option("-s", "--state", action="store", dest="state",
        type='choice', choices=['o', 'open', 'c', 'closed', 'a', 'all'],
        default='open', help="specify state (only for list and search "\
        "(except `all`) commands) choices are: open (o), closed (c), all "\
        "(a) [default: open]")
    parser.add_option("-u", "--user", action="store", dest="created_by", default=False,\
        help="issues created by <github_username> [default: all]")
    parser.add_option("-m", "--message", action="store", dest="message",
      default=None, help="message content for opening or commenting on an "\
        "issue without using the editor")
    parser.add_option("-r", "--repo", "--repository", action="store",
        dest="repo", help="specify a repository (format: "\
            "`user/repo` or just `repo` (latter will get the user from the "\
            "global git config))")
    parser.add_option("-w", "--web", "--webbrowser", action="store_true",
        dest="webbrowser", default=False, help="show issue(s) GitHub page "\
        "in web browser (only for list and show commands) [default: False]")
    parser.add_option("-V", "--version", action="store_true",
        dest="show_version", default=False,
        help="show program's version number and exit")

    class CustomValues:
        pass
    (options, args) = parser.parse_args(values=CustomValues)

    kwargs = dict([(k, v) for k, v in options.__dict__.items() \
        if not k.startswith("__")])
    if kwargs.get('show_version'):
        print("ghi %s" % get_version('short'))
        sys.exit(0)

    if kwargs.get('state'):
        kwargs['state'] = {'o': 'open', 'c': 'closed', 'a': 'all'}.get(
            kwargs['state'], kwargs['state'])

    if args:
        cmd = args[0]
        try:
            nr = str(int(cmd))
            if cmd == nr:
                cmd = 'show'
                args = (cmd, nr)
        except:
            pass
    else:
        cmd = 'list' # default command

    if cmd == 'search':
        search_term = " ".join(args[1:])
        args = (args[0], search_term)

    # handle command aliases
    cmd = {'o': 'open', 'c': 'close', 'e': 'edit', 'm': 'comment',
        's': 'search'}.get(cmd, cmd)
    if cmd == 'open' and len(args) > 1:
        cmd = 'reopen'
    if cmd == 'al' or cmd == 'rl':
        alias = cmd
        cmd = 'label'
        args_list = [cmd, {'a': 'add', 'r': 'remove'}[alias[0]]]
        args_list.extend(args[1:])
        args = tuple(args_list)

    try:
        repository = kwargs.get('repo')
        if repository:
            user, repo = get_remote_info_from_option(repository)
        else:
            user, repo = get_remote_info()
        commands = Commands(user, repo)
        getattr(commands, cmd)(*args[1:], **kwargs)
    except AttributeError:
        return "error: command '%s' not implemented" % cmd
    except Exception, info:
        return "error: %s" % info

if __name__ == '__main__':
    main()

########NEW FILE########
__FILENAME__ = utils
import os
import sys
import re
import urllib2
import tempfile
import subprocess
import textwrap
from urllib2 import build_opener, HTTPCookieProcessor, Request
from urllib import urlencode
from subprocess import Popen, PIPE, STDOUT

opener = build_opener(HTTPCookieProcessor)


def urlopen2(url, data=None, auth=True, user_agent='github-cli'):
    if auth:
        config = get_config()
        auth_dict = {'login': config['user'], 'token': config['token']}
        if data:
            data.update(auth_dict)
        else:
            data = auth_dict
    if hasattr(data, "__iter__"):
        data = urlencode(data)
    headers = {'User-Agent': user_agent}
    try:
        return opener.open(Request(url, data, headers))
    except urllib2.HTTPError, info:
        raise Exception("server problem (%s)" % info)
    except urllib2.URLError:
        raise Exception("connection problem")


def get_remote_info():
    commands = (
        "git config --get remote.origin.url",
        "git config --get remote.github.url",
        "hg paths default",
        "hg paths github")
    aliases = get_aliases()
    for command in commands:
        stdout, stderr = Popen(command, shell=True, stdin=PIPE, stdout=PIPE,
            stderr=PIPE).communicate()
        if stdout:
            line = stdout.strip()
            if not "github.com" in line:
                # check if it's using an alias
                for alias in aliases:
                    if line.startswith(alias):
                        line = line.replace(alias, aliases[alias])
                        break
                else:
                    continue
            pattern = re.compile(r'([^:/]+)/([^/]+).git$')
            result = pattern.search(line)
            if result:
                return result.groups()
            else:
                # Whilst repos are usually configured with a postfix of ".git"
                # this is by convention only. Github happily handles requests
                # without the postfix.
                pattern = re.compile(r'([^:/]+)/([^/]+)')
                result = pattern.search(line)
                if result:
                    return result.groups()
                raise Exception("invalid user and repo name")
        elif stderr:
            for line in stderr.splitlines():
                line = line.lower()
                # a bit hackish: hg paths <path> returns 'not found!' when
                # <path> is not in .hg/hgrc; this is to avoid showing it
                if not 'not found' in line:
                    print line
    raise Exception("not a valid repository or not hosted on github.com")


def get_aliases():
    """
    Return a dict of global git aliases regarding github, or None:
        {
         "alias": "http://...",
         "alias2": "git://...it",
        }
    """
    cmd = "git config --global --get-regexp url\..*github.com.*"
    stdout, stderr = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE,
        stderr=PIPE).communicate()
    if stdout:
        d = {}
        for alias in stdout.strip().split('\n'):
            url, alias = alias.split()
            d[alias] = url.split('.', 1)[1].rsplit('.', 1)[0]
        return d
    return []


def get_remote_info_from_option(repository):
    if "/" in repository:
        user, repo = repository.split("/")
        return user, repo
    else:
        config = get_config()
        return config['user'], repository


def get_config():
    required_keys = {
        'user': 'GITHUB_USER',
        'token': 'GITHUB_TOKEN'
    }
    config = {}
    for key, env_key in required_keys.items():
        value = os.environ.get(env_key)
        if not value:
            command = "git config --global github.%s" % key
            stdout, stderr = Popen(command, shell=True, stdin=PIPE, stdout=PIPE,
                stderr=PIPE).communicate()
            if stderr:
                for line in stderr.splitlines():
                    print line
                sys.exit(1)
            value = stdout.strip()
        if value:
            config[key] = value
        else:
            alt_help_names = {'user': 'username'}
            help_name = alt_help_names.get(key, key)
            print "error: required GitHub entry '%s' not found in global "\
                "git config" % key
            print "please add it to the global git config by doing this:"
            print
            print "    git config --global github.%s <your GitHub %s>" % (key,
                help_name)
            print
            print "or by specifying environment variables GITHUB_USER and "\
				"GITHUB_TOKEN"
            sys.exit(1)
    return config


def edit_text(text):
    editor = os.getenv('EDITOR', 'vi')

    f = tempfile.NamedTemporaryFile()
    f.write(text)
    f.flush()

    command = "%s %s" % (editor, f.name)
    ret = subprocess.call(command, shell=True)
    if ret != 0:
        print "error: editor command failed"
        sys.exit(1)

    changed_text = open(f.name).read()
    f.close()
    stripcomment_re = re.compile(r'^#.*$', re.MULTILINE)
    return stripcomment_re.sub('', changed_text).strip()


def get_prog():
    if sys.argv and sys.argv[0]:
        return os.path.split(sys.argv[0])[1]
    else:
        return '<prog>'


class Pager(object):
    """enable paging for multiple writes

    see http://svn.python.org/view/python/branches/release25-maint/Lib/\
    pydoc.py?view=markup
    (getpager()) for handling different circumstances or platforms
    """

    def __init__(self):
        self.proc = None
        self.file = sys.stdout # ultimate fallback
        self.cmd = ''

        if hasattr(sys.stdout, 'isatty') and sys.stdout.isatty():
            pager_commands = ['more -EMR', 'more', 'less -MR', 'less']
            for cmd in pager_commands:
                if hasattr(os, 'system') and \
                              os.system('(%s) 2>/dev/null' % cmd) == 0:
                    self.proc = subprocess.Popen([cmd], shell=True,
                        stdin=subprocess.PIPE, stderr=subprocess.PIPE)
                    self.file = self.proc.stdin
                    self.cmd = cmd
                    break

    def write(self, text=""):
        try:
            self.file.write("%s\n" % text)
        except:
            # in case the pager cmd fails unexpectedly
            self.file = sys.stdout
            self.file.write("%s\n" % text)

    def close(self):
        if 'less' in self.cmd:
            self.write("press q to quit")
        if self.proc:
            self.file.close()
            try:
                self.proc.wait()
            except KeyboardInterrupt:
                sys.proc.kill()
                sys.exit(1)



def wrap_text(text, width=79):
    if text:
        output = []
        for part in text.splitlines():
            output.append(textwrap.fill(part, width))
        return "\n".join(output)
    return text


def get_underline(text, max_width=79):
    if len(text) > max_width:
        return "-" * max_width
    else:
        return "-" * len(text)

########NEW FILE########
__FILENAME__ = version
"""
Current version constant plus version pretty-print method.

This functionality is contained in its own module to prevent circular import
problems with ``__init__.py`` (which is loaded by setup.py during installation,
which in turn needs access to this version information.)

Borrowed from `fabric`.
"""

VERSION = (1, 0, 0, 'final', 0)


def get_version(form='short'):
    """
    Return a version string for this package, based on `VERSION`.

    Takes a single argument, ``form``, which should be one of the following
    strings:

    * ``branch``: just the major + minor, e.g. "0.2", "1.0".
    * ``short`` (default): compact, e.g. "0.2rc1", "0.2.0". For package
      filenames or SCM tag identifiers.
    * ``normal``: human readable, e.g. "0.2", "0.2.7", "0.2 beta 1". For e.g.
      documentation site headers.
    * ``verbose``: like ``normal`` but fully explicit, e.g. "0.2 final". For
      tag commit messages, or anywhere that it's important to remove ambiguity
      between a branch and the first final release within that branch.
    """
    # Setup
    versions = {}
    branch = "%s.%s" % (VERSION[0], VERSION[1])
    tertiary = VERSION[2]
    type_ = VERSION[3]
    final = (type_ == "final")
    type_num = VERSION[4]
    firsts = "".join([x[0] for x in type_.split()])

    # Branch
    versions['branch'] = branch

    # Short
    v = branch
    if (tertiary or final):
        v += "." + str(tertiary)
    if not final:
        v += firsts
        if type_num:
            v += str(type_num)
    versions['short'] = v

    # Normal
    v = branch
    if tertiary:
        v += "." + str(tertiary)
    if not final:
        if type_num:
            v += " " + type_ + " " + str(type_num)
        else:
            v += " pre-" + type_
    versions['normal'] = v

    # Verbose
    v = branch
    if tertiary:
        v += "." + str(tertiary)
    if not final:
        if type_num:
            v += " " + type_ + " " + str(type_num)
        else:
            v += " pre-" + type_
    else:
        v += " final"
    versions['verbose'] = v

    try:
        return versions[form]
    except KeyError:
        raise TypeError('"%s" is not a valid form specifier.' % form)

__version__ = get_version('short')

########NEW FILE########
__FILENAME__ = test_issues_cli
import os
import sys
from nose.tools import assert_raises

from github.issues import main

repo = 'jsmits/github-cli-public-test'
prog = 'ghi'

def test_commands():
    for cmd, exp in test_input:
        def check_command(cmd, exp):
            base = [prog, '-r', repo]
            args = cmd.split(' ')
            if not args == ['']: # need this for 'just `ghi`' command test
                base.extend(args)
            sys.argv = base
            if type(exp) == type(Exception):
                assert_raises(exp, main)
            else:
                output = main()
                assert output == exp
        check_command.description = "command: %s %s" % (prog, cmd)
        yield check_command, cmd, exp

test_input = (
    # list commands
    ('list', None), ('list -v', None), ('', None), ('-v', None),
    ('lis', "error: command 'lis' not implemented"),
    ('l', "error: command 'l' not implemented"),
    ('list -s open', None), ('list -s o', None), ('list -s closed', None),
    ('list -s c', None), ('list -s all', None), ('list -s a', None),
    ('-s a', None), ('-s a -v', None), ('list -s close', SystemExit),
    ('list -u bobdole', None),

    # show commands
    ('show 1', None), ('1', None), ('17288182', "error: server problem (HTTP"\
        " Error 404: Not Found)"), ('5', None), ('5 -v', None),

    # state modification commands
    ('close 1', None), ('open 1', None), ('c 1', None), ('close 1', None),
    ('o 1', None), ('open 1', None),

    # label commands
    ('label add testing 1', None), ('label remove testing 1', None),
    ('al testing 1', None), ('rl testing 1', None),
    ('label add testing', "error: number required\nexample: ghi label add "\
        "testing 1"),

    # help commands
    ('--help', SystemExit), ('-h', SystemExit),

    # browser commands
    ('-w', SystemExit), ('1 -w', SystemExit),

    # search commands
    ('search test', None), ('s test', None), ('search test -s open', None),
    ('search test -s o', None), ('search test -s closed', None),
    ('search test -s c', None), ('s test -s c', None), ('search', SystemExit),
    
)

########NEW FILE########
__FILENAME__ = test_version
"""
Tests covering version number pretty-print functionality.

Borrowed from `fabric`.
"""

from nose.tools import eq_

import github.version


def test_get_version():
    get_version = github.version.get_version
    for tup, short, normal, verbose in [
        ((0, 2, 0, 'final', 0), '0.2.0', '0.2', '0.2 final'),
        ((0, 2, 7, 'final', 0), '0.2.7', '0.2.7', '0.2.7 final'),
        ((0, 2, 0, 'alpha', 1), '0.2a1', '0.2 alpha 1', '0.2 alpha 1'),
        ((0, 2, 7, 'beta', 1), '0.2.7b1', '0.2.7 beta 1', '0.2.7 beta 1'),
        ((0, 2, 0, 'release candidate', 1),
            '0.2rc1', '0.2 release candidate 1', '0.2 release candidate 1'),
        ((1, 0, 0, 'alpha', 0), '1.0a', '1.0 pre-alpha', '1.0 pre-alpha'),
    ]:
        github.version.VERSION = tup
        yield eq_, get_version('short'), short
        yield eq_, get_version('normal'), normal
        yield eq_, get_version('verbose'), verbose

########NEW FILE########
