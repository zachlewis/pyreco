__FILENAME__ = builddiscover
#!/usr/bin/env python
import os.path
import urlparse

from openid.test import discoverdata

manifest_header = """\
# This file contains test cases for doing YADIS identity URL and
# service discovery. For each case, there are three URLs. The first
# URL is the user input. The second is the identity URL and the third
# is the URL from which the XRDS document should be read.
#
# The file format is as follows:
# User URL <tab> Identity URL <tab> XRDS URL <newline>
#
# blank lines and lines starting with # should be ignored.
#
# To use this test:
#
# 1. Run your discovery routine on the User URL.
#
# 2. Compare the identity URL returned by the discovery routine to the
#    identity URL on that line of the file. It must be an EXACT match.
#
# 3. Do a regular HTTP GET on the XRDS URL. Compare the content that
#    was returned by your discovery routine with the content returned
#    from that URL. It should also be an exact match.

"""

def buildDiscover(base_url, out_dir):
    """Convert all files in a directory to apache mod_asis files in
    another directory."""
    test_data = discoverdata.readTests(discoverdata.default_test_file)

    def writeTestFile(test_name):
        template = test_data[test_name]

        data = discoverdata.fillTemplate(
            test_name, template, base_url, discoverdata.example_xrds)

        out_file_name = os.path.join(out_dir, test_name)
        out_file = file(out_file_name, 'w')
        out_file.write(data)

    manifest = [manifest_header]
    for success, input_name, id_name, result_name in discoverdata.testlist:
        if not success:
            continue
        writeTestFile(input_name)

        input_url = urlparse.urljoin(base_url, input_name)
        id_url = urlparse.urljoin(base_url, id_name)
        result_url = urlparse.urljoin(base_url, result_name)

        manifest.append('\t'.join((input_url, id_url, result_url)))
        manifest.append('\n')

    manifest_file_name = os.path.join(out_dir, 'manifest.txt')
    manifest_file = file(manifest_file_name, 'w')
    for chunk in manifest:
        manifest_file.write(chunk)
    manifest_file.close()

if __name__ == '__main__':
    import sys
    buildDiscover(*sys.argv[1:])

########NEW FILE########
__FILENAME__ = gettlds
"""
Fetch the current TLD list from the IANA Web site, parse it, and print
an expression suitable for direct insertion into each library's trust
root validation module

Usage:
  python gettlds.py (php|python|ruby)

Then cut-n-paste.
"""

import urllib2

import sys

langs = {
    'php': (r"'/\.(",
            "'", "|", "|' .",
            r")\.?$/'"),
    'python': ("['",
               "'", "', '", "',",
               "']"),
    'ruby': ("%w'",
             "", " ", "",
             "'"),
    }

lang = sys.argv[1]
prefix, line_prefix, separator, line_suffix, suffix = langs[lang]

f = urllib2.urlopen('http://data.iana.org/TLD/tlds-alpha-by-domain.txt')
tlds = []
output_line = ""
for input_line in f:
    if input_line.startswith('#'):
        continue

    tld = input_line.strip().lower()
    new_output_line = output_line + prefix + tld
    if len(new_output_line) > 60:
        print output_line + line_suffix
        output_line = line_prefix + tld
    else:
        output_line = new_output_line
    prefix = separator

print output_line + suffix

########NEW FILE########
__FILENAME__ = consumer
#!/usr/bin/env python
"""
Simple example for an OpenID consumer.

Once you understand this example you'll know the basics of OpenID
and using the Python OpenID library. You can then move on to more
robust examples, and integrating OpenID into your application.
"""
__copyright__ = 'Copyright 2005-2008, Janrain, Inc.'

from Cookie import SimpleCookie
import cgi
import urlparse
import cgitb
import sys

def quoteattr(s):
    qs = cgi.escape(s, 1)
    return '"%s"' % (qs,)

from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler

try:
    import openid
except ImportError:
    sys.stderr.write("""
Failed to import the OpenID library. In order to use this example, you
must either install the library (see INSTALL in the root of the
distribution) or else add the library to python's import path (the
PYTHONPATH environment variable).

For more information, see the README in the root of the library
distribution.""")
    sys.exit(1)

from openid.store import memstore
from openid.store import filestore
from openid.consumer import consumer
from openid.oidutil import appendArgs
from openid.cryptutil import randomString
from openid.fetchers import setDefaultFetcher, Urllib2Fetcher
from openid.extensions import pape, sreg

# Used with an OpenID provider affiliate program.
OPENID_PROVIDER_NAME = 'MyOpenID'
OPENID_PROVIDER_URL ='https://www.myopenid.com/affiliate_signup?affiliate_id=39'


class OpenIDHTTPServer(HTTPServer):
    """http server that contains a reference to an OpenID consumer and
    knows its base URL.
    """
    def __init__(self, store, *args, **kwargs):
        HTTPServer.__init__(self, *args, **kwargs)
        self.sessions = {}
        self.store = store

        if self.server_port != 80:
            self.base_url = ('http://%s:%s/' %
                             (self.server_name, self.server_port))
        else:
            self.base_url = 'http://%s/' % (self.server_name,)

class OpenIDRequestHandler(BaseHTTPRequestHandler):
    """Request handler that knows how to verify an OpenID identity."""
    SESSION_COOKIE_NAME = 'pyoidconsexsid'

    session = None

    def getConsumer(self, stateless=False):
        if stateless:
            store = None
        else:
            store = self.server.store
        return consumer.Consumer(self.getSession(), store)

    def getSession(self):
        """Return the existing session or a new session"""
        if self.session is not None:
            return self.session

        # Get value of cookie header that was sent
        cookie_str = self.headers.get('Cookie')
        if cookie_str:
            cookie_obj = SimpleCookie(cookie_str)
            sid_morsel = cookie_obj.get(self.SESSION_COOKIE_NAME, None)
            if sid_morsel is not None:
                sid = sid_morsel.value
            else:
                sid = None
        else:
            sid = None

        # If a session id was not set, create a new one
        if sid is None:
            sid = randomString(16, '0123456789abcdef')
            session = None
        else:
            session = self.server.sessions.get(sid)

        # If no session exists for this session ID, create one
        if session is None:
            session = self.server.sessions[sid] = {}

        session['id'] = sid
        self.session = session
        return session

    def setSessionCookie(self):
        sid = self.getSession()['id']
        session_cookie = '%s=%s;' % (self.SESSION_COOKIE_NAME, sid)
        self.send_header('Set-Cookie', session_cookie)

    def do_GET(self):
        """Dispatching logic. There are three paths defined:

          / - Display an empty form asking for an identity URL to
              verify
          /verify - Handle form submission, initiating OpenID verification
          /process - Handle a redirect from an OpenID server

        Any other path gets a 404 response. This function also parses
        the query parameters.

        If an exception occurs in this function, a traceback is
        written to the requesting browser.
        """
        try:
            self.parsed_uri = urlparse.urlparse(self.path)
            self.query = {}
            for k, v in cgi.parse_qsl(self.parsed_uri[4]):
                self.query[k] = v.decode('utf-8')

            path = self.parsed_uri[2]
            if path == '/':
                self.render()
            elif path == '/verify':
                self.doVerify()
            elif path == '/process':
                self.doProcess()
            elif path == '/affiliate':
                self.doAffiliate()
            else:
                self.notFound()

        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.send_response(500)
            self.send_header('Content-type', 'text/html')
            self.setSessionCookie()
            self.end_headers()
            self.wfile.write(cgitb.html(sys.exc_info(), context=10))

    def doVerify(self):
        """Process the form submission, initating OpenID verification.
        """

        # First, make sure that the user entered something
        openid_url = self.query.get('openid_identifier')
        if not openid_url:
            self.render('Enter an OpenID Identifier to verify.',
                        css_class='error', form_contents=openid_url)
            return

        immediate = 'immediate' in self.query
        use_sreg = 'use_sreg' in self.query
        use_pape = 'use_pape' in self.query
        use_stateless = 'use_stateless' in self.query

        oidconsumer = self.getConsumer(stateless = use_stateless)
        try:
            request = oidconsumer.begin(openid_url)
        except consumer.DiscoveryFailure, exc:
            fetch_error_string = 'Error in discovery: %s' % (
                cgi.escape(str(exc[0])))
            self.render(fetch_error_string,
                        css_class='error',
                        form_contents=openid_url)
        else:
            if request is None:
                msg = 'No OpenID services found for <code>%s</code>' % (
                    cgi.escape(openid_url),)
                self.render(msg, css_class='error', form_contents=openid_url)
            else:
                # Then, ask the library to begin the authorization.
                # Here we find out the identity server that will verify the
                # user's identity, and get a token that allows us to
                # communicate securely with the identity server.
                if use_sreg:
                    self.requestRegistrationData(request)

                if use_pape:
                    self.requestPAPEDetails(request)

                trust_root = self.server.base_url
                return_to = self.buildURL('process')
                if request.shouldSendRedirect():
                    redirect_url = request.redirectURL(
                        trust_root, return_to, immediate=immediate)
                    self.send_response(302)
                    self.send_header('Location', redirect_url)
                    self.writeUserHeader()
                    self.end_headers()
                else:
                    form_html = request.htmlMarkup(
                        trust_root, return_to,
                        form_tag_attrs={'id':'openid_message'},
                        immediate=immediate)

                    self.wfile.write(form_html)

    def requestRegistrationData(self, request):
        sreg_request = sreg.SRegRequest(
            required=['nickname'], optional=['fullname', 'email'])
        request.addExtension(sreg_request)

    def requestPAPEDetails(self, request):
        pape_request = pape.Request([pape.AUTH_PHISHING_RESISTANT])
        request.addExtension(pape_request)

    def doProcess(self):
        """Handle the redirect from the OpenID server.
        """
        oidconsumer = self.getConsumer()

        # Ask the library to check the response that the server sent
        # us.  Status is a code indicating the response type. info is
        # either None or a string containing more information about
        # the return type.
        url = 'http://'+self.headers.get('Host')+self.path
        info = oidconsumer.complete(self.query, url)

        sreg_resp = None
        pape_resp = None
        css_class = 'error'
        display_identifier = info.getDisplayIdentifier()

        if info.status == consumer.FAILURE and display_identifier:
            # In the case of failure, if info is non-None, it is the
            # URL that we were verifying. We include it in the error
            # message to help the user figure out what happened.
            fmt = "Verification of %s failed: %s"
            message = fmt % (cgi.escape(display_identifier),
                             info.message)
        elif info.status == consumer.SUCCESS:
            # Success means that the transaction completed without
            # error. If info is None, it means that the user cancelled
            # the verification.
            css_class = 'alert'

            # This is a successful verification attempt. If this
            # was a real application, we would do our login,
            # comment posting, etc. here.
            fmt = "You have successfully verified %s as your identity."
            message = fmt % (cgi.escape(display_identifier),)
            sreg_resp = sreg.SRegResponse.fromSuccessResponse(info)
            pape_resp = pape.Response.fromSuccessResponse(info)
            if info.endpoint.canonicalID:
                # You should authorize i-name users by their canonicalID,
                # rather than their more human-friendly identifiers.  That
                # way their account with you is not compromised if their
                # i-name registration expires and is bought by someone else.
                message += ("  This is an i-name, and its persistent ID is %s"
                            % (cgi.escape(info.endpoint.canonicalID),))
        elif info.status == consumer.CANCEL:
            # cancelled
            message = 'Verification cancelled'
        elif info.status == consumer.SETUP_NEEDED:
            if info.setup_url:
                message = '<a href=%s>Setup needed</a>' % (
                    quoteattr(info.setup_url),)
            else:
                # This means auth didn't succeed, but you're welcome to try
                # non-immediate mode.
                message = 'Setup needed'
        else:
            # Either we don't understand the code or there is no
            # openid_url included with the error. Give a generic
            # failure message. The library should supply debug
            # information in a log.
            message = 'Verification failed.'

        self.render(message, css_class, display_identifier,
                    sreg_data=sreg_resp, pape_data=pape_resp)

    def doAffiliate(self):
        """Direct the user sign up with an affiliate OpenID provider."""
        sreg_req = sreg.SRegRequest(['nickname'], ['fullname', 'email'])
        href = sreg_req.toMessage().toURL(OPENID_PROVIDER_URL)

        message = """Get an OpenID at <a href=%s>%s</a>""" % (
            quoteattr(href), OPENID_PROVIDER_NAME)
        self.render(message)

    def renderSREG(self, sreg_data):
        if not sreg_data:
            self.wfile.write(
                '<div class="alert">No registration data was returned</div>')
        else:
            sreg_list = sreg_data.items()
            sreg_list.sort()
            self.wfile.write(
                '<h2>Registration Data</h2>'
                '<table class="sreg">'
                '<thead><tr><th>Field</th><th>Value</th></tr></thead>'
                '<tbody>')

            odd = ' class="odd"'
            for k, v in sreg_list:
                field_name = sreg.data_fields.get(k, k)
                value = cgi.escape(v.encode('UTF-8'))
                self.wfile.write(
                    '<tr%s><td>%s</td><td>%s</td></tr>' % (odd, field_name, value))
                if odd:
                    odd = ''
                else:
                    odd = ' class="odd"'

            self.wfile.write('</tbody></table>')

    def renderPAPE(self, pape_data):
        if not pape_data:
            self.wfile.write(
                '<div class="alert">No PAPE data was returned</div>')
        else:
            self.wfile.write('<div class="alert">Effective Auth Policies<ul>')

            for policy_uri in pape_data.auth_policies:
                self.wfile.write('<li><tt>%s</tt></li>' % (cgi.escape(policy_uri),))

            if not pape_data.auth_policies:
                self.wfile.write('<li>No policies were applied.</li>')

            self.wfile.write('</ul></div>')

    def buildURL(self, action, **query):
        """Build a URL relative to the server base_url, with the given
        query parameters added."""
        base = urlparse.urljoin(self.server.base_url, action)
        return appendArgs(base, query)

    def notFound(self):
        """Render a page with a 404 return code and a message."""
        fmt = 'The path <q>%s</q> was not understood by this server.'
        msg = fmt % (self.path,)
        openid_url = self.query.get('openid_identifier')
        self.render(msg, 'error', openid_url, status=404)

    def render(self, message=None, css_class='alert', form_contents=None,
               status=200, title="Python OpenID Consumer Example",
               sreg_data=None, pape_data=None):
        """Render a page."""
        self.send_response(status)
        self.pageHeader(title)
        if message:
            self.wfile.write("<div class='%s'>" % (css_class,))
            self.wfile.write(message)
            self.wfile.write("</div>")

        if sreg_data is not None:
            self.renderSREG(sreg_data)

        if pape_data is not None:
            self.renderPAPE(pape_data)

        self.pageFooter(form_contents)

    def pageHeader(self, title):
        """Render the page header"""
        self.setSessionCookie()
        self.wfile.write('''\
Content-type: text/html; charset=UTF-8

<html>
  <head><title>%s</title></head>
  <style type="text/css">
      * {
        font-family: verdana,sans-serif;
      }
      body {
        width: 50em;
        margin: 1em;
      }
      div {
        padding: .5em;
      }
      tr.odd td {
        background-color: #dddddd;
      }
      table.sreg {
        border: 1px solid black;
        border-collapse: collapse;
      }
      table.sreg th {
        border-bottom: 1px solid black;
      }
      table.sreg td, table.sreg th {
        padding: 0.5em;
        text-align: left;
      }
      table {
        margin: 0;
        padding: 0;
      }
      .alert {
        border: 1px solid #e7dc2b;
        background: #fff888;
      }
      .error {
        border: 1px solid #ff0000;
        background: #ffaaaa;
      }
      #verify-form {
        border: 1px solid #777777;
        background: #dddddd;
        margin-top: 1em;
        padding-bottom: 0em;
      }
  </style>
  <body>
    <h1>%s</h1>
    <p>
      This example consumer uses the <a href=
      "http://github.com/openid/python-openid" >Python
      OpenID</a> library. It just verifies that the identifier that you enter
      is your identifier.
    </p>
''' % (title, title))

    def pageFooter(self, form_contents):
        """Render the page footer"""
        if not form_contents:
            form_contents = ''

        self.wfile.write('''\
    <div id="verify-form">
      <form method="get" accept-charset="UTF-8" action=%s>
        Identifier:
        <input type="text" name="openid_identifier" value=%s />
        <input type="submit" value="Verify" /><br />
        <input type="checkbox" name="immediate" id="immediate" /><label for="immediate">Use immediate mode</label>
        <input type="checkbox" name="use_sreg" id="use_sreg" /><label for="use_sreg">Request registration data</label>
        <input type="checkbox" name="use_pape" id="use_pape" /><label for="use_pape">Request phishing-resistent auth policy (PAPE)</label>
        <input type="checkbox" name="use_stateless" id="use_stateless" /><label for="use_stateless">Use stateless mode</label>
      </form>
    </div>
  </body>
</html>
''' % (quoteattr(self.buildURL('verify')), quoteattr(form_contents)))

def main(host, port, data_path, weak_ssl=False):
    # Instantiate OpenID consumer store and OpenID consumer.  If you
    # were connecting to a database, you would create the database
    # connection and instantiate an appropriate store here.
    if data_path:
        store = filestore.FileOpenIDStore(data_path)
    else:
        store = memstore.MemoryStore()

    if weak_ssl:
        setDefaultFetcher(Urllib2Fetcher())

    addr = (host, port)
    server = OpenIDHTTPServer(store, addr, OpenIDRequestHandler)

    print 'Server running at:'
    print server.base_url
    server.serve_forever()

if __name__ == '__main__':
    host = 'localhost'
    port = 8001
    weak_ssl = False

    try:
        import optparse
    except ImportError:
        pass # Use defaults (for Python 2.2)
    else:
        parser = optparse.OptionParser('Usage:\n %prog [options]')
        parser.add_option(
            '-d', '--data-path', dest='data_path',
            help='Data directory for storing OpenID consumer state. '
            'Setting this option implies using a "FileStore."')
        parser.add_option(
            '-p', '--port', dest='port', type='int', default=port,
            help='Port on which to listen for HTTP requests. '
            'Defaults to port %default.')
        parser.add_option(
            '-s', '--host', dest='host', default=host,
            help='Host on which to listen for HTTP requests. '
            'Also used for generating URLs. Defaults to %default.')
        parser.add_option(
            '-w', '--weakssl', dest='weakssl', default=False,
            action='store_true', help='Skip ssl cert verification')

        options, args = parser.parse_args()
        if args:
            parser.error('Expected no arguments. Got %r' % args)

        host = options.host
        port = options.port
        data_path = options.data_path
        weak_ssl = options.weakssl

    main(host, port, data_path, weak_ssl)

########NEW FILE########
__FILENAME__ = models
from django.db import models

# Create your models here.

########NEW FILE########
__FILENAME__ = urls

from django.conf.urls.defaults import *

urlpatterns = patterns(
    'djopenid.consumer.views',
    (r'^$', 'startOpenID'),
    (r'^finish/$', 'finishOpenID'),
    (r'^xrds/$', 'rpXRDS'),
)

########NEW FILE########
__FILENAME__ = views

from django import http
from django.http import HttpResponseRedirect
from django.views.generic.simple import direct_to_template

from openid.consumer import consumer
from openid.consumer.discover import DiscoveryFailure
from openid.extensions import ax, pape, sreg
from openid.yadis.constants import YADIS_HEADER_NAME, YADIS_CONTENT_TYPE
from openid.server.trustroot import RP_RETURN_TO_URL_TYPE

from djopenid import util

PAPE_POLICIES = [
    'AUTH_PHISHING_RESISTANT',
    'AUTH_MULTI_FACTOR',
    'AUTH_MULTI_FACTOR_PHYSICAL',
    ]

# List of (name, uri) for use in generating the request form.
POLICY_PAIRS = [(p, getattr(pape, p))
                for p in PAPE_POLICIES]

def getOpenIDStore():
    """
    Return an OpenID store object fit for the currently-chosen
    database backend, if any.
    """
    return util.getOpenIDStore('/tmp/djopenid_c_store', 'c_')

def getConsumer(request):
    """
    Get a Consumer object to perform OpenID authentication.
    """
    return consumer.Consumer(request.session, getOpenIDStore())

def renderIndexPage(request, **template_args):
    template_args['consumer_url'] = util.getViewURL(request, startOpenID)
    template_args['pape_policies'] = POLICY_PAIRS

    response =  direct_to_template(
        request, 'consumer/index.html', template_args)
    response[YADIS_HEADER_NAME] = util.getViewURL(request, rpXRDS)
    return response

def startOpenID(request):
    """
    Start the OpenID authentication process.  Renders an
    authentication form and accepts its POST.

    * Renders an error message if OpenID cannot be initiated

    * Requests some Simple Registration data using the OpenID
      library's Simple Registration machinery

    * Generates the appropriate trust root and return URL values for
      this application (tweak where appropriate)

    * Generates the appropriate redirect based on the OpenID protocol
      version.
    """
    if request.POST:
        # Start OpenID authentication.
        openid_url = request.POST['openid_identifier']
        c = getConsumer(request)
        error = None

        try:
            auth_request = c.begin(openid_url)
        except DiscoveryFailure, e:
            # Some other protocol-level failure occurred.
            error = "OpenID discovery error: %s" % (str(e),)

        if error:
            # Render the page with an error.
            return renderIndexPage(request, error=error)

        # Add Simple Registration request information.  Some fields
        # are optional, some are required.  It's possible that the
        # server doesn't support sreg or won't return any of the
        # fields.
        sreg_request = sreg.SRegRequest(optional=['email', 'nickname'],
                                        required=['dob'])
        auth_request.addExtension(sreg_request)

        # Add Attribute Exchange request information.
        ax_request = ax.FetchRequest()
        # XXX - uses myOpenID-compatible schema values, which are
        # not those listed at axschema.org.
        ax_request.add(
            ax.AttrInfo('http://schema.openid.net/namePerson',
                        required=True))
        ax_request.add(
            ax.AttrInfo('http://schema.openid.net/contact/web/default',
                        required=False, count=ax.UNLIMITED_VALUES))
        auth_request.addExtension(ax_request)

        # Add PAPE request information.  We'll ask for
        # phishing-resistant auth and display any policies we get in
        # the response.
        requested_policies = []
        policy_prefix = 'policy_'
        for k, v in request.POST.iteritems():
            if k.startswith(policy_prefix):
                policy_attr = k[len(policy_prefix):]
                if policy_attr in PAPE_POLICIES:
                    requested_policies.append(getattr(pape, policy_attr))

        if requested_policies:
            pape_request = pape.Request(requested_policies)
            auth_request.addExtension(pape_request)

        # Compute the trust root and return URL values to build the
        # redirect information.
        trust_root = util.getViewURL(request, startOpenID)
        return_to = util.getViewURL(request, finishOpenID)

        # Send the browser to the server either by sending a redirect
        # URL or by generating a POST form.
        if auth_request.shouldSendRedirect():
            url = auth_request.redirectURL(trust_root, return_to)
            return HttpResponseRedirect(url)
        else:
            # Beware: this renders a template whose content is a form
            # and some javascript to submit it upon page load.  Non-JS
            # users will have to click the form submit button to
            # initiate OpenID authentication.
            form_id = 'openid_message'
            form_html = auth_request.formMarkup(trust_root, return_to,
                                                False, {'id': form_id})
            return direct_to_template(
                request, 'consumer/request_form.html', {'html': form_html})

    return renderIndexPage(request)

def finishOpenID(request):
    """
    Finish the OpenID authentication process.  Invoke the OpenID
    library with the response from the OpenID server and render a page
    detailing the result.
    """
    result = {}

    # Because the object containing the query parameters is a
    # MultiValueDict and the OpenID library doesn't allow that, we'll
    # convert it to a normal dict.

    # OpenID 2 can send arguments as either POST body or GET query
    # parameters.
    request_args = util.normalDict(request.GET)
    if request.method == 'POST':
        request_args.update(util.normalDict(request.POST))

    if request_args:
        c = getConsumer(request)

        # Get a response object indicating the result of the OpenID
        # protocol.
        return_to = util.getViewURL(request, finishOpenID)
        response = c.complete(request_args, return_to)

        # Get a Simple Registration response object if response
        # information was included in the OpenID response.
        sreg_response = {}
        ax_items = {}
        if response.status == consumer.SUCCESS:
            sreg_response = sreg.SRegResponse.fromSuccessResponse(response)

            ax_response = ax.FetchResponse.fromSuccessResponse(response)
            if ax_response:
                ax_items = {
                    'fullname': ax_response.get(
                        'http://schema.openid.net/namePerson'),
                    'web': ax_response.get(
                        'http://schema.openid.net/contact/web/default'),
                    }

        # Get a PAPE response object if response information was
        # included in the OpenID response.
        pape_response = None
        if response.status == consumer.SUCCESS:
            pape_response = pape.Response.fromSuccessResponse(response)

            if not pape_response.auth_policies:
                pape_response = None

        # Map different consumer status codes to template contexts.
        results = {
            consumer.CANCEL:
            {'message': 'OpenID authentication cancelled.'},

            consumer.FAILURE:
            {'error': 'OpenID authentication failed.'},

            consumer.SUCCESS:
            {'url': response.getDisplayIdentifier(),
             'sreg': sreg_response and sreg_response.items(),
             'ax': ax_items.items(),
             'pape': pape_response}
            }

        result = results[response.status]

        if isinstance(response, consumer.FailureResponse):
            # In a real application, this information should be
            # written to a log for debugging/tracking OpenID
            # authentication failures. In general, the messages are
            # not user-friendly, but intended for developers.
            result['failure_reason'] = response.message

    return renderIndexPage(request, **result)

def rpXRDS(request):
    """
    Return a relying party verification XRDS document
    """
    return util.renderXRDS(
        request,
        [RP_RETURN_TO_URL_TYPE],
        [util.getViewURL(request, finishOpenID)])

########NEW FILE########
__FILENAME__ = manage
#!/usr/bin/env python
from django.core.management import execute_manager
try:
    import settings # Assumed to be in the same directory.
except ImportError:
    import sys
    sys.stderr.write("Error: Can't find the file 'settings.py' in the directory containing %r. It appears you've customized things.\nYou'll have to run django-admin.py, passing it your settings module.\n(If the file settings.py does indeed exist, it's causing an ImportError somehow.)\n" % __file__)
    sys.exit(1)

if __name__ == "__main__":
    execute_manager(settings)

########NEW FILE########
__FILENAME__ = models
from django.db import models

# Create your models here.

########NEW FILE########
__FILENAME__ = tests

from django.test.testcases import TestCase
from djopenid.server import views
from djopenid import util

from django.http import HttpRequest
from django.contrib.sessions.middleware import SessionWrapper

from openid.server.server import CheckIDRequest
from openid.message import Message
from openid.yadis.constants import YADIS_CONTENT_TYPE
from openid.yadis.services import applyFilter

def dummyRequest():
    request = HttpRequest()
    request.session = SessionWrapper("test")
    request.META['HTTP_HOST'] = 'example.invalid'
    request.META['SERVER_PROTOCOL'] = 'HTTP'
    return request

class TestProcessTrustResult(TestCase):
    def setUp(self):
        self.request = dummyRequest()

        id_url = util.getViewURL(self.request, views.idPage)

        # Set up the OpenID request we're responding to.
        op_endpoint = 'http://127.0.0.1:8080/endpoint'
        message = Message.fromPostArgs({
            'openid.mode': 'checkid_setup',
            'openid.identity': id_url,
            'openid.return_to': 'http://127.0.0.1/%s' % (self.id(),),
            'openid.sreg.required': 'postcode',
            })
        self.openid_request = CheckIDRequest.fromMessage(message, op_endpoint)

        views.setRequest(self.request, self.openid_request)


    def test_allow(self):
        self.request.POST['allow'] = 'Yes'

        response = views.processTrustResult(self.request)

        self.failUnlessEqual(response.status_code, 302)
        finalURL = response['location']
        self.failUnless('openid.mode=id_res' in finalURL, finalURL)
        self.failUnless('openid.identity=' in finalURL, finalURL)
        self.failUnless('openid.sreg.postcode=12345' in finalURL, finalURL)

    def test_cancel(self):
        self.request.POST['cancel'] = 'Yes'

        response = views.processTrustResult(self.request)

        self.failUnlessEqual(response.status_code, 302)
        finalURL = response['location']
        self.failUnless('openid.mode=cancel' in finalURL, finalURL)
        self.failIf('openid.identity=' in finalURL, finalURL)
        self.failIf('openid.sreg.postcode=12345' in finalURL, finalURL)



class TestShowDecidePage(TestCase):
    def test_unreachableRealm(self):
        self.request = dummyRequest()

        id_url = util.getViewURL(self.request, views.idPage)

        # Set up the OpenID request we're responding to.
        op_endpoint = 'http://127.0.0.1:8080/endpoint'
        message = Message.fromPostArgs({
            'openid.mode': 'checkid_setup',
            'openid.identity': id_url,
            'openid.return_to': 'http://unreachable.invalid/%s' % (self.id(),),
            'openid.sreg.required': 'postcode',
            })
        self.openid_request = CheckIDRequest.fromMessage(message, op_endpoint)

        views.setRequest(self.request, self.openid_request)

        response = views.showDecidePage(self.request, self.openid_request)
        self.failUnless('trust_root_valid is Unreachable' in response.content,
                        response)



class TestGenericXRDS(TestCase):
    def test_genericRender(self):
        """Render an XRDS document with a single type URI and a single endpoint URL
        Parse it to see that it matches."""
        request = dummyRequest()

        type_uris = ['A_TYPE']
        endpoint_url = 'A_URL'
        response = util.renderXRDS(request, type_uris, [endpoint_url])

        requested_url = 'http://requested.invalid/'
        (endpoint,) = applyFilter(requested_url, response.content)

        self.failUnlessEqual(YADIS_CONTENT_TYPE, response['Content-Type'])
        self.failUnlessEqual(type_uris, endpoint.type_uris)
        self.failUnlessEqual(endpoint_url, endpoint.uri)

########NEW FILE########
__FILENAME__ = urls

from django.conf.urls.defaults import *

urlpatterns = patterns(
    'djopenid.server.views',
    (r'^$', 'server'),
    (r'^xrds/$', 'idpXrds'),
    (r'^processTrustResult/$', 'processTrustResult'),
    (r'^user/$', 'idPage'),
    (r'^endpoint/$', 'endpoint'),
    (r'^trust/$', 'trustPage'),
)

########NEW FILE########
__FILENAME__ = views

"""
This module implements an example server for the OpenID library.  Some
functionality has been omitted intentionally; this code is intended to
be instructive on the use of this library.  This server does not
perform actual user authentication and serves up only one OpenID URL,
with the exception of IDP-generated identifiers.

Some code conventions used here:

* 'request' is a Django request object.

* 'openid_request' is an OpenID library request object.

* 'openid_response' is an OpenID library response
"""

import cgi

from djopenid import util
from djopenid.util import getViewURL

from django import http
from django.views.generic.simple import direct_to_template

from openid.server.server import Server, ProtocolError, CheckIDRequest, \
     EncodingError
from openid.server.trustroot import verifyReturnTo
from openid.yadis.discover import DiscoveryFailure
from openid.consumer.discover import OPENID_IDP_2_0_TYPE
from openid.extensions import sreg
from openid.extensions import pape
from openid.fetchers import HTTPFetchingError

def getOpenIDStore():
    """
    Return an OpenID store object fit for the currently-chosen
    database backend, if any.
    """
    return util.getOpenIDStore('/tmp/djopenid_s_store', 's_')

def getServer(request):
    """
    Get a Server object to perform OpenID authentication.
    """
    return Server(getOpenIDStore(), getViewURL(request, endpoint))

def setRequest(request, openid_request):
    """
    Store the openid request information in the session.
    """
    if openid_request:
        request.session['openid_request'] = openid_request
    else:
        request.session['openid_request'] = None

def getRequest(request):
    """
    Get an openid request from the session, if any.
    """
    return request.session.get('openid_request')

def server(request):
    """
    Respond to requests for the server's primary web page.
    """
    return direct_to_template(
        request,
        'server/index.html',
        {'user_url': getViewURL(request, idPage),
         'server_xrds_url': getViewURL(request, idpXrds),
         })

def idpXrds(request):
    """
    Respond to requests for the IDP's XRDS document, which is used in
    IDP-driven identifier selection.
    """
    return util.renderXRDS(
        request, [OPENID_IDP_2_0_TYPE], [getViewURL(request, endpoint)])

def idPage(request):
    """
    Serve the identity page for OpenID URLs.
    """
    return direct_to_template(
        request,
        'server/idPage.html',
        {'server_url': getViewURL(request, endpoint)})

def trustPage(request):
    """
    Display the trust page template, which allows the user to decide
    whether to approve the OpenID verification.
    """
    return direct_to_template(
        request,
        'server/trust.html',
        {'trust_handler_url':getViewURL(request, processTrustResult)})

def endpoint(request):
    """
    Respond to low-level OpenID protocol messages.
    """
    s = getServer(request)

    query = util.normalDict(request.GET or request.POST)

    # First, decode the incoming request into something the OpenID
    # library can use.
    try:
        openid_request = s.decodeRequest(query)
    except ProtocolError, why:
        # This means the incoming request was invalid.
        return direct_to_template(
            request,
            'server/endpoint.html',
            {'error': str(why)})

    # If we did not get a request, display text indicating that this
    # is an endpoint.
    if openid_request is None:
        return direct_to_template(
            request,
            'server/endpoint.html',
            {})

    # We got a request; if the mode is checkid_*, we will handle it by
    # getting feedback from the user or by checking the session.
    if openid_request.mode in ["checkid_immediate", "checkid_setup"]:
        return handleCheckIDRequest(request, openid_request)
    else:
        # We got some other kind of OpenID request, so we let the
        # server handle this.
        openid_response = s.handleRequest(openid_request)
        return displayResponse(request, openid_response)

def handleCheckIDRequest(request, openid_request):
    """
    Handle checkid_* requests.  Get input from the user to find out
    whether she trusts the RP involved.  Possibly, get intput about
    what Simple Registration information, if any, to send in the
    response.
    """
    # If the request was an IDP-driven identifier selection request
    # (i.e., the IDP URL was entered at the RP), then return the
    # default identity URL for this server. In a full-featured
    # provider, there could be interaction with the user to determine
    # what URL should be sent.
    if not openid_request.idSelect():

        id_url = getViewURL(request, idPage)

        # Confirm that this server can actually vouch for that
        # identifier
        if id_url != openid_request.identity:
            # Return an error response
            error_response = ProtocolError(
                openid_request.message,
                "This server cannot verify the URL %r" %
                (openid_request.identity,))

            return displayResponse(request, error_response)

    if openid_request.immediate:
        # Always respond with 'cancel' to immediate mode requests
        # because we don't track information about a logged-in user.
        # If we did, then the answer would depend on whether that user
        # had trusted the request's trust root and whether the user is
        # even logged in.
        openid_response = openid_request.answer(False)
        return displayResponse(request, openid_response)
    else:
        # Store the incoming request object in the session so we can
        # get to it later.
        setRequest(request, openid_request)
        return showDecidePage(request, openid_request)

def showDecidePage(request, openid_request):
    """
    Render a page to the user so a trust decision can be made.

    @type openid_request: openid.server.server.CheckIDRequest
    """
    trust_root = openid_request.trust_root
    return_to = openid_request.return_to

    try:
        # Stringify because template's ifequal can only compare to strings.
        trust_root_valid = verifyReturnTo(trust_root, return_to) \
                           and "Valid" or "Invalid"
    except DiscoveryFailure, err:
        trust_root_valid = "DISCOVERY_FAILED"
    except HTTPFetchingError, err:
        trust_root_valid = "Unreachable"

    pape_request = pape.Request.fromOpenIDRequest(openid_request)

    return direct_to_template(
        request,
        'server/trust.html',
        {'trust_root': trust_root,
         'trust_handler_url':getViewURL(request, processTrustResult),
         'trust_root_valid': trust_root_valid,
         'pape_request': pape_request,
         })

def processTrustResult(request):
    """
    Handle the result of a trust decision and respond to the RP
    accordingly.
    """
    # Get the request from the session so we can construct the
    # appropriate response.
    openid_request = getRequest(request)

    # The identifier that this server can vouch for
    response_identity = getViewURL(request, idPage)

    # If the decision was to allow the verification, respond
    # accordingly.
    allowed = 'allow' in request.POST

    # Generate a response with the appropriate answer.
    openid_response = openid_request.answer(allowed,
                                            identity=response_identity)

    # Send Simple Registration data in the response, if appropriate.
    if allowed:
        sreg_data = {
            'fullname': 'Example User',
            'nickname': 'example',
            'dob': '1970-01-01',
            'email': 'invalid@example.com',
            'gender': 'F',
            'postcode': '12345',
            'country': 'ES',
            'language': 'eu',
            'timezone': 'America/New_York',
            }

        sreg_req = sreg.SRegRequest.fromOpenIDRequest(openid_request)
        sreg_resp = sreg.SRegResponse.extractResponse(sreg_req, sreg_data)
        openid_response.addExtension(sreg_resp)

        pape_response = pape.Response()
        pape_response.setAuthLevel(pape.LEVELS_NIST, 0)
        openid_response.addExtension(pape_response)

    return displayResponse(request, openid_response)

def displayResponse(request, openid_response):
    """
    Display an OpenID response.  Errors will be displayed directly to
    the user; successful responses and other protocol-level messages
    will be sent using the proper mechanism (i.e., direct response,
    redirection, etc.).
    """
    s = getServer(request)

    # Encode the response into something that is renderable.
    try:
        webresponse = s.encodeResponse(openid_response)
    except EncodingError, why:
        # If it couldn't be encoded, display an error.
        text = why.response.encodeToKVForm()
        return direct_to_template(
            request,
            'server/endpoint.html',
            {'error': cgi.escape(text)})

    # Construct the appropriate django framework response.
    r = http.HttpResponse(webresponse.body)
    r.status_code = webresponse.code

    for header, value in webresponse.headers.iteritems():
        r[header] = value

    return r

########NEW FILE########
__FILENAME__ = settings
# Django settings for djopenid project.

import os
import sys
import warnings

try:
    import openid
except ImportError, e:
    warnings.warn("Could not import OpenID library.  Please consult the djopenid README.")
    sys.exit(1)

DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    # ('Your Name', 'your_email@domain.com'),
)

MANAGERS = ADMINS

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3', # Add 'postgresql_psycopg2', 'mysql', 'sqlite3' or 'oracle'.
        'NAME': '/tmp/test.db',          # Or path to database file if using sqlite3.
        'USER': '',                      # Not used with sqlite3.
        'PASSWORD': '',                  # Not used with sqlite3.
        'HOST': '',                      # Set to empty string for localhost. Not used with sqlite3.
        'PORT': '',                      # Set to empty string for default. Not used with sqlite3.
    }
}

# Local time zone for this installation. All choices can be found here:
# http://www.postgresql.org/docs/current/static/datetime-keywords.html#DATETIME-TIMEZONE-SET-TABLE
TIME_ZONE = 'America/Chicago'

# Language code for this installation. All choices can be found here:
# http://www.w3.org/TR/REC-html40/struct/dirlang.html#langcodes
# http://blogs.law.harvard.edu/tech/stories/storyReader$15
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT.
# Example: "http://media.lawrence.com"
MEDIA_URL = ''

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/media/'

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'u^bw6lmsa6fah0$^lz-ct$)y7x7#ag92-z+y45-8!(jk0lkavy'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
#     'django.template.loaders.eggs.load_template_source',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.doc.XViewMiddleware',
)

ROOT_URLCONF = 'djopenid.urls'

TEMPLATE_CONTEXT_PROCESSORS = ()

TEMPLATE_DIRS = (
    os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates')),
)

INSTALLED_APPS = (
    'django.contrib.contenttypes',
    'django.contrib.sessions',

    'djopenid.consumer',
    'djopenid.server',
)

########NEW FILE########
__FILENAME__ = urls
from django.conf.urls.defaults import *

urlpatterns = patterns(
    '',
    ('^$', 'djopenid.views.index'),
    ('^consumer/', include('djopenid.consumer.urls')),
    ('^server/', include('djopenid.server.urls')),
)

########NEW FILE########
__FILENAME__ = util

"""
Utility code for the Django example consumer and server.
"""

from urlparse import urljoin

from django.db import connection
from django.template.context import RequestContext
from django.template import loader
from django import http
from django.core.exceptions import ImproperlyConfigured
from django.core.urlresolvers import reverse as reverseURL
from django.views.generic.simple import direct_to_template

from django.conf import settings

from openid.store.filestore import FileOpenIDStore
from openid.store import sqlstore
from openid.yadis.constants import YADIS_CONTENT_TYPE

def getOpenIDStore(filestore_path, table_prefix):
    """
    Returns an OpenID association store object based on the database
    engine chosen for this Django application.

    * If no database engine is chosen, a filesystem-based store will
      be used whose path is filestore_path.

    * If a database engine is chosen, a store object for that database
      type will be returned.

    * If the chosen engine is not supported by the OpenID library,
      raise ImproperlyConfigured.

    * If a database store is used, this will create the tables
      necessary to use it.  The table names will be prefixed with
      table_prefix.  DO NOT use the same table prefix for both an
      OpenID consumer and an OpenID server in the same database.

    The result of this function should be passed to the Consumer
    constructor as the store parameter.
    """
    if not settings.DATABASES.get('default', {'ENGINE':None}).get('ENGINE'):
        return FileOpenIDStore(filestore_path)

    # Possible side-effect: create a database connection if one isn't
    # already open.
    connection.cursor()

    # Create table names to specify for SQL-backed stores.
    tablenames = {
        'associations_table': table_prefix + 'openid_associations',
        'nonces_table': table_prefix + 'openid_nonces',
        }

    types = {
        'django.db.backends.postgresql': sqlstore.PostgreSQLStore,
        'django.db.backends.mysql': sqlstore.MySQLStore,
        'django.db.backends.sqlite3': sqlstore.SQLiteStore,
        }

    try:
        s = types[settings.DATABASES.get('default', {'ENGINE':None}).get('ENGINE')](connection.connection,
                                            **tablenames)
    except KeyError:
        raise ImproperlyConfigured, \
              "Database engine %s not supported by OpenID library" % \
              (settings.DATABASES.get('default', {'ENGINE':None}).get('ENGINE'),)

    try:
        s.createTables()
    except (SystemExit, KeyboardInterrupt, MemoryError), e:
        raise
    except:
        # XXX This is not the Right Way to do this, but because the
        # underlying database implementation might differ in behavior
        # at this point, we can't reliably catch the right
        # exception(s) here.  Ideally, the SQL store in the OpenID
        # library would catch exceptions that it expects and fail
        # silently, but that could be bad, too.  More ideally, the SQL
        # store would not attempt to create tables it knows already
        # exists.
        pass

    return s

def getViewURL(req, view_name_or_obj, args=None, kwargs=None):
    relative_url = reverseURL(view_name_or_obj, args=args, kwargs=kwargs)
    full_path = req.META.get('SCRIPT_NAME', '') + relative_url
    return urljoin(getBaseURL(req), full_path)

def getBaseURL(req):
    """
    Given a Django web request object, returns the OpenID 'trust root'
    for that request; namely, the absolute URL to the site root which
    is serving the Django request.  The trust root will include the
    proper scheme and authority.  It will lack a port if the port is
    standard (80, 443).
    """
    name = req.META['HTTP_HOST']
    try:
        name = name[:name.index(':')]
    except:
        pass

    try:
        port = int(req.META['SERVER_PORT'])
    except:
        port = 80

    proto = req.META['SERVER_PROTOCOL']

    if 'HTTPS' in proto:
        proto = 'https'
    else:
        proto = 'http'

    if port in [80, 443] or not port:
        port = ''
    else:
        port = ':%s' % (port,)

    url = "%s://%s%s/" % (proto, name, port)
    return url

def normalDict(request_data):
    """
    Converts a django request MutliValueDict (e.g., request.GET,
    request.POST) into a standard python dict whose values are the
    first value from each of the MultiValueDict's value lists.  This
    avoids the OpenID library's refusal to deal with dicts whose
    values are lists, because in OpenID, each key in the query arg set
    can have at most one value.
    """
    return dict((k, v) for k, v in request_data.iteritems())

def renderXRDS(request, type_uris, endpoint_urls):
    """Render an XRDS page with the specified type URIs and endpoint
    URLs in one service block, and return a response with the
    appropriate content-type.
    """
    response = direct_to_template(
        request, 'xrds.xml',
        {'type_uris':type_uris, 'endpoint_urls':endpoint_urls,})
    response['Content-Type'] = YADIS_CONTENT_TYPE
    return response

########NEW FILE########
__FILENAME__ = views

from djopenid import util
from django.views.generic.simple import direct_to_template

def index(request):
    consumer_url = util.getViewURL(
        request, 'djopenid.consumer.views.startOpenID')
    server_url = util.getViewURL(request, 'djopenid.server.views.server')

    return direct_to_template(
        request,
        'index.html',
        {'consumer_url':consumer_url, 'server_url':server_url})


########NEW FILE########
__FILENAME__ = server
#!/usr/bin/env python

__copyright__ = 'Copyright 2005-2008, Janrain, Inc.'

from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from urlparse import urlparse

import time
import Cookie
import cgi
import cgitb
import sys

def quoteattr(s):
    qs = cgi.escape(s, 1)
    return '"%s"' % (qs,)

try:
    import openid
except ImportError:
    sys.stderr.write("""
Failed to import the OpenID library. In order to use this example, you
must either install the library (see INSTALL in the root of the
distribution) or else add the library to python's import path (the
PYTHONPATH environment variable).

For more information, see the README in the root of the library
distribution.""")
    sys.exit(1)

from openid.extensions import sreg
from openid.server import server
from openid.store.filestore import FileOpenIDStore
from openid.consumer import discover

class OpenIDHTTPServer(HTTPServer):
    """
    http server that contains a reference to an OpenID Server and
    knows its base URL.
    """
    def __init__(self, *args, **kwargs):
        HTTPServer.__init__(self, *args, **kwargs)

        if self.server_port != 80:
            self.base_url = ('http://%s:%s/' %
                             (self.server_name, self.server_port))
        else:
            self.base_url = 'http://%s/' % (self.server_name,)

        self.openid = None
        self.approved = {}
        self.lastCheckIDRequest = {}

    def setOpenIDServer(self, oidserver):
        self.openid = oidserver


class ServerHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.user = None
        BaseHTTPRequestHandler.__init__(self, *args, **kwargs)


    def do_GET(self):
        try:
            self.parsed_uri = urlparse(self.path)
            self.query = {}
            for k, v in cgi.parse_qsl(self.parsed_uri[4]):
                self.query[k] = v

            self.setUser()

            path = self.parsed_uri[2].lower()

            if path == '/':
                self.showMainPage()
            elif path == '/openidserver':
                self.serverEndPoint(self.query)

            elif path == '/login':
                self.showLoginPage('/', '/')
            elif path == '/loginsubmit':
                self.doLogin()
            elif path.startswith('/id/'):
                self.showIdPage(path)
            elif path.startswith('/yadis/'):
                self.showYadis(path[7:])
            elif path == '/serveryadis':
                self.showServerYadis()
            else:
                self.send_response(404)
                self.end_headers()

        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.send_response(500)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(cgitb.html(sys.exc_info(), context=10))

    def do_POST(self):
        try:
            self.parsed_uri = urlparse(self.path)

            self.setUser()
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)

            self.query = {}
            for k, v in cgi.parse_qsl(post_data):
                self.query[k] = v

            path = self.parsed_uri[2]
            if path == '/openidserver':
                self.serverEndPoint(self.query)

            elif path == '/allow':
                self.handleAllow(self.query)
            else:
                self.send_response(404)
                self.end_headers()

        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.send_response(500)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(cgitb.html(sys.exc_info(), context=10))

    def handleAllow(self, query):
        # pretend this next bit is keying off the user's session or something,
        # right?
        request = self.server.lastCheckIDRequest.get(self.user)

        if 'yes' in query:
            if 'login_as' in query:
                self.user = self.query['login_as']

            if request.idSelect():
                identity = self.server.base_url + 'id/' + query['identifier']
            else:
                identity = request.identity

            trust_root = request.trust_root
            if self.query.get('remember', 'no') == 'yes':
                self.server.approved[(identity, trust_root)] = 'always'

            response = self.approved(request, identity)

        elif 'no' in query:
            response = request.answer(False)

        else:
            assert False, 'strange allow post.  %r' % (query,)

        self.displayResponse(response)


    def setUser(self):
        cookies = self.headers.get('Cookie')
        if cookies:
            morsel = Cookie.BaseCookie(cookies).get('user')
            if morsel:
                self.user = morsel.value

    def isAuthorized(self, identity_url, trust_root):
        if self.user is None:
            return False

        if identity_url != self.server.base_url + 'id/' + self.user:
            return False

        key = (identity_url, trust_root)
        return self.server.approved.get(key) is not None

    def serverEndPoint(self, query):
        try:
            request = self.server.openid.decodeRequest(query)
        except server.ProtocolError, why:
            self.displayResponse(why)
            return

        if request is None:
            # Display text indicating that this is an endpoint.
            self.showAboutPage()
            return

        if request.mode in ["checkid_immediate", "checkid_setup"]:
            self.handleCheckIDRequest(request)
        else:
            response = self.server.openid.handleRequest(request)
            self.displayResponse(response)

    def addSRegResponse(self, request, response):
        sreg_req = sreg.SRegRequest.fromOpenIDRequest(request)

        # In a real application, this data would be user-specific,
        # and the user should be asked for permission to release
        # it.
        sreg_data = {
            'nickname':self.user
            }

        sreg_resp = sreg.SRegResponse.extractResponse(sreg_req, sreg_data)
        response.addExtension(sreg_resp)

    def approved(self, request, identifier=None):
        response = request.answer(True, identity=identifier)
        self.addSRegResponse(request, response)
        return response

    def handleCheckIDRequest(self, request):
        is_authorized = self.isAuthorized(request.identity, request.trust_root)
        if is_authorized:
            response = self.approved(request)
            self.displayResponse(response)
        elif request.immediate:
            response = request.answer(False)
            self.displayResponse(response)
        else:
            self.server.lastCheckIDRequest[self.user] = request
            self.showDecidePage(request)

    def displayResponse(self, response):
        try:
            webresponse = self.server.openid.encodeResponse(response)
        except server.EncodingError, why:
            text = why.response.encodeToKVForm()
            self.showErrorPage('<pre>%s</pre>' % cgi.escape(text))
            return

        self.send_response(webresponse.code)
        for header, value in webresponse.headers.iteritems():
            self.send_header(header, value)
        self.writeUserHeader()
        self.end_headers()

        if webresponse.body:
            self.wfile.write(webresponse.body)

    def doLogin(self):
        if 'submit' in self.query:
            if 'user' in self.query:
                self.user = self.query['user']
            else:
                self.user = None
            self.redirect(self.query['success_to'])
        elif 'cancel' in self.query:
            self.redirect(self.query['fail_to'])
        else:
            assert 0, 'strange login %r' % (self.query,)

    def redirect(self, url):
        self.send_response(302)
        self.send_header('Location', url)
        self.writeUserHeader()

        self.end_headers()

    def writeUserHeader(self):
        if self.user is None:
            t1970 = time.gmtime(0)
            expires = time.strftime(
                'Expires=%a, %d-%b-%y %H:%M:%S GMT', t1970)
            self.send_header('Set-Cookie', 'user=;%s' % expires)
        else:
            self.send_header('Set-Cookie', 'user=%s' % self.user)

    def showAboutPage(self):
        endpoint_url = self.server.base_url + 'openidserver'

        def link(url):
            url_attr = quoteattr(url)
            url_text = cgi.escape(url)
            return '<a href=%s><code>%s</code></a>' % (url_attr, url_text)

        def term(url, text):
            return '<dt>%s</dt><dd>%s</dd>' % (link(url), text)

        resources = [
            (self.server.base_url, "This example server's home page"),
            ('http://www.openidenabled.com/',
             'An OpenID community Web site, home of this library'),
            ('http://www.openid.net/', 'the official OpenID Web site'),
            ]

        resource_markup = ''.join([term(url, text) for url, text in resources])

        self.showPage(200, 'This is an OpenID server', msg="""\
        <p>%s is an OpenID server endpoint.<p>
        <p>For more information about OpenID, see:</p>
        <dl>
        %s
        </dl>
        """ % (link(endpoint_url), resource_markup,))

    def showErrorPage(self, error_message):
        self.showPage(400, 'Error Processing Request', err='''\
        <p>%s</p>
        <!--

        This is a large comment.  It exists to make this page larger.
        That is unfortunately necessary because of the "smart"
        handling of pages returned with an error code in IE.

        *************************************************************
        *************************************************************
        *************************************************************
        *************************************************************
        *************************************************************
        *************************************************************
        *************************************************************
        *************************************************************
        *************************************************************
        *************************************************************
        *************************************************************
        *************************************************************
        *************************************************************
        *************************************************************
        *************************************************************
        *************************************************************
        *************************************************************
        *************************************************************
        *************************************************************
        *************************************************************
        *************************************************************
        *************************************************************
        *************************************************************

        -->
        ''' % error_message)

    def showDecidePage(self, request):
        id_url_base = self.server.base_url+'id/'
        # XXX: This may break if there are any synonyms for id_url_base,
        # such as referring to it by IP address or a CNAME.
        assert (request.identity.startswith(id_url_base) or 
                request.idSelect()), repr((request.identity, id_url_base))
        expected_user = request.identity[len(id_url_base):]

        if request.idSelect(): # We are being asked to select an ID
            msg = '''\
            <p>A site has asked for your identity.  You may select an
            identifier by which you would like this site to know you.
            On a production site this would likely be a drop down list
            of pre-created accounts or have the facility to generate
            a random anonymous identifier.
            </p>
            '''
            fdata = {
                'id_url_base': id_url_base,
                'trust_root': request.trust_root,
                }
            form = '''\
            <form method="POST" action="/allow">
            <table>
              <tr><td>Identity:</td>
                 <td>%(id_url_base)s<input type='text' name='identifier'></td></tr>
              <tr><td>Trust Root:</td><td>%(trust_root)s</td></tr>
            </table>
            <p>Allow this authentication to proceed?</p>
            <input type="checkbox" id="remember" name="remember" value="yes"
                /><label for="remember">Remember this
                decision</label><br />
            <input type="submit" name="yes" value="yes" />
            <input type="submit" name="no" value="no" />
            </form>
            '''%fdata
        elif expected_user == self.user:
            msg = '''\
            <p>A new site has asked to confirm your identity.  If you
            approve, the site represented by the trust root below will
            be told that you control identity URL listed below. (If
            you are using a delegated identity, the site will take
            care of reversing the delegation on its own.)</p>'''

            fdata = {
                'identity': request.identity,
                'trust_root': request.trust_root,
                }
            form = '''\
            <table>
              <tr><td>Identity:</td><td>%(identity)s</td></tr>
              <tr><td>Trust Root:</td><td>%(trust_root)s</td></tr>
            </table>
            <p>Allow this authentication to proceed?</p>
            <form method="POST" action="/allow">
              <input type="checkbox" id="remember" name="remember" value="yes"
                  /><label for="remember">Remember this
                  decision</label><br />
              <input type="submit" name="yes" value="yes" />
              <input type="submit" name="no" value="no" />
            </form>''' % fdata
        else:
            mdata = {
                'expected_user': expected_user,
                'user': self.user,
                }
            msg = '''\
            <p>A site has asked for an identity belonging to
            %(expected_user)s, but you are logged in as %(user)s.  To
            log in as %(expected_user)s and approve the login request,
            hit OK below.  The "Remember this decision" checkbox
            applies only to the trust root decision.</p>''' % mdata

            fdata = {
                'identity': request.identity,
                'trust_root': request.trust_root,
                'expected_user': expected_user,
                }
            form = '''\
            <table>
              <tr><td>Identity:</td><td>%(identity)s</td></tr>
              <tr><td>Trust Root:</td><td>%(trust_root)s</td></tr>
            </table>
            <p>Allow this authentication to proceed?</p>
            <form method="POST" action="/allow">
              <input type="checkbox" id="remember" name="remember" value="yes"
                  /><label for="remember">Remember this
                  decision</label><br />
              <input type="hidden" name="login_as" value="%(expected_user)s"/>
              <input type="submit" name="yes" value="yes" />
              <input type="submit" name="no" value="no" />
            </form>''' % fdata

        self.showPage(200, 'Approve OpenID request?', msg=msg, form=form)

    def showIdPage(self, path):
        link_tag = '<link rel="openid.server" href="%sopenidserver">' %\
              self.server.base_url
        yadis_loc_tag = '<meta http-equiv="x-xrds-location" content="%s">'%\
            (self.server.base_url+'yadis/'+path[4:])
        disco_tags = link_tag + yadis_loc_tag
        ident = self.server.base_url + path[1:]

        approved_trust_roots = []
        for (aident, trust_root) in self.server.approved.keys():
            if aident == ident:
                trs = '<li><tt>%s</tt></li>\n' % cgi.escape(trust_root)
                approved_trust_roots.append(trs)

        if approved_trust_roots:
            prepend = '<p>Approved trust roots:</p>\n<ul>\n'
            approved_trust_roots.insert(0, prepend)
            approved_trust_roots.append('</ul>\n')
            msg = ''.join(approved_trust_roots)
        else:
            msg = ''

        self.showPage(200, 'An Identity Page', head_extras=disco_tags, msg='''\
        <p>This is an identity page for %s.</p>
        %s
        ''' % (ident, msg))

    def showYadis(self, user):
        self.send_response(200)
        self.send_header('Content-type', 'application/xrds+xml')
        self.end_headers()

        endpoint_url = self.server.base_url + 'openidserver'
        user_url = self.server.base_url + 'id/' + user
        self.wfile.write("""\
<?xml version="1.0" encoding="UTF-8"?>
<xrds:XRDS
    xmlns:xrds="xri://$xrds"
    xmlns="xri://$xrd*($v*2.0)">
  <XRD>

    <Service priority="0">
      <Type>%s</Type>
      <Type>%s</Type>
      <URI>%s</URI>
      <LocalID>%s</LocalID>
    </Service>

  </XRD>
</xrds:XRDS>
"""%(discover.OPENID_2_0_TYPE, discover.OPENID_1_0_TYPE,
     endpoint_url, user_url))

    def showServerYadis(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/xrds+xml')
        self.end_headers()

        endpoint_url = self.server.base_url + 'openidserver'
        self.wfile.write("""\
<?xml version="1.0" encoding="UTF-8"?>
<xrds:XRDS
    xmlns:xrds="xri://$xrds"
    xmlns="xri://$xrd*($v*2.0)">
  <XRD>

    <Service priority="0">
      <Type>%s</Type>
      <URI>%s</URI>
    </Service>

  </XRD>
</xrds:XRDS>
"""%(discover.OPENID_IDP_2_0_TYPE, endpoint_url,))

    def showMainPage(self):
        yadis_tag = '<meta http-equiv="x-xrds-location" content="%s">'%\
            (self.server.base_url + 'serveryadis')
        if self.user:
            openid_url = self.server.base_url + 'id/' + self.user
            user_message = """\
            <p>You are logged in as %s. Your OpenID identity URL is
            <tt><a href=%s>%s</a></tt>. Enter that URL at an OpenID
            consumer to test this server.</p>
            """ % (self.user, quoteattr(openid_url), openid_url)
        else:
            user_message = """\
            <p>This server uses a cookie to remember who you are in
            order to simulate a standard Web user experience. You are
            not <a href='/login'>logged in</a>.</p>"""

        self.showPage(200, 'Main Page', head_extras = yadis_tag, msg='''\
        <p>This is a simple OpenID server implemented using the <a
        href="http://openid.schtuff.com/">Python OpenID
        library</a>.</p>

        %s

        <p>To use this server with a consumer, the consumer must be
        able to fetch HTTP pages from this web server. If this
        computer is behind a firewall, you will not be able to use
        OpenID consumers outside of the firewall with it.</p>

        <p>The URL for this server is <a href=%s><tt>%s</tt></a>.</p>
        ''' % (user_message, quoteattr(self.server.base_url), self.server.base_url))

    def showLoginPage(self, success_to, fail_to):
        self.showPage(200, 'Login Page', form='''\
        <h2>Login</h2>
        <p>You may log in with any name. This server does not use
        passwords because it is just a sample of how to use the OpenID
        library.</p>
        <form method="GET" action="/loginsubmit">
          <input type="hidden" name="success_to" value="%s" />
          <input type="hidden" name="fail_to" value="%s" />
          <input type="text" name="user" value="" />
          <input type="submit" name="submit" value="Log In" />
          <input type="submit" name="cancel" value="Cancel" />
        </form>
        ''' % (success_to, fail_to))

    def showPage(self, response_code, title,
                 head_extras='', msg=None, err=None, form=None):

        if self.user is None:
            user_link = '<a href="/login">not logged in</a>.'
        else:
            user_link = 'logged in as <a href="/id/%s">%s</a>.<br /><a href="/loginsubmit?submit=true&success_to=/login">Log out</a>' % \
                        (self.user, self.user)

        body = ''

        if err is not None:
            body +=  '''\
            <div class="error">
              %s
            </div>
            ''' % err

        if msg is not None:
            body += '''\
            <div class="message">
              %s
            </div>
            ''' % msg

        if form is not None:
            body += '''\
            <div class="form">
              %s
            </div>
            ''' % form

        contents = {
            'title': 'Python OpenID Server Example - ' + title,
            'head_extras': head_extras,
            'body': body,
            'user_link': user_link,
            }

        self.send_response(response_code)
        self.writeUserHeader()
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        self.wfile.write('''<html>
  <head>
    <title>%(title)s</title>
    %(head_extras)s
  </head>
  <style type="text/css">
      h1 a:link {
          color: black;
          text-decoration: none;
      }
      h1 a:visited {
          color: black;
          text-decoration: none;
      }
      h1 a:hover {
          text-decoration: underline;
      }
      body {
        font-family: verdana,sans-serif;
        width: 50em;
        margin: 1em;
      }
      div {
        padding: .5em;
      }
      table {
        margin: none;
        padding: none;
      }
      .banner {
        padding: none 1em 1em 1em;
        width: 100%%;
      }
      .leftbanner {
        text-align: left;
      }
      .rightbanner {
        text-align: right;
        font-size: smaller;
      }
      .error {
        border: 1px solid #ff0000;
        background: #ffaaaa;
        margin: .5em;
      }
      .message {
        border: 1px solid #2233ff;
        background: #eeeeff;
        margin: .5em;
      }
      .form {
        border: 1px solid #777777;
        background: #ddddcc;
        margin: .5em;
        margin-top: 1em;
        padding-bottom: 0em;
      }
      dd {
        margin-bottom: 0.5em;
      }
  </style>
  <body>
    <table class="banner">
      <tr>
        <td class="leftbanner">
          <h1><a href="/">Python OpenID Server Example</a></h1>
        </td>
        <td class="rightbanner">
          You are %(user_link)s
        </td>
      </tr>
    </table>
%(body)s
  </body>
</html>
''' % contents)


def main(host, port, data_path):
    addr = (host, port)
    httpserver = OpenIDHTTPServer(addr, ServerHandler)

    # Instantiate OpenID consumer store and OpenID consumer.  If you
    # were connecting to a database, you would create the database
    # connection and instantiate an appropriate store here.
    store = FileOpenIDStore(data_path)
    oidserver = server.Server(store, httpserver.base_url + 'openidserver')

    httpserver.setOpenIDServer(oidserver)

    print 'Server running at:'
    print httpserver.base_url
    httpserver.serve_forever()

if __name__ == '__main__':
    host = 'localhost'
    data_path = 'sstore'
    port = 8000

    try:
        import optparse
    except ImportError:
        pass # Use defaults (for Python 2.2)
    else:
        parser = optparse.OptionParser('Usage:\n %prog [options]')
        parser.add_option(
            '-d', '--data-path', dest='data_path', default=data_path,
            help='Data directory for storing OpenID consumer state. '
            'Defaults to "%default" in the current directory.')
        parser.add_option(
            '-p', '--port', dest='port', type='int', default=port,
            help='Port on which to listen for HTTP requests. '
            'Defaults to port %default.')
        parser.add_option(
            '-s', '--host', dest='host', default=host,
            help='Host on which to listen for HTTP requests. '
            'Also used for generating URLs. Defaults to %default.')

        options, args = parser.parse_args()
        if args:
            parser.error('Expected no arguments. Got %r' % args)

        host = options.host
        port = options.port
        data_path = options.data_path

    main(host, port, data_path)

########NEW FILE########
__FILENAME__ = association
# -*- test-case-name: openid.test.test_association -*-
"""
This module contains code for dealing with associations between
consumers and servers. Associations contain a shared secret that is
used to sign C{openid.mode=id_res} messages.

Users of the library should not usually need to interact directly with
associations. The L{store<openid.store>},
L{server<openid.server.server>} and
L{consumer<openid.consumer.consumer>} objects will create and manage
the associations. The consumer and server code will make use of a
C{L{SessionNegotiator}} when managing associations, which enables
users to express a preference for what kind of associations should be
allowed, and what kind of exchange should be done to establish the
association.

@var default_negotiator: A C{L{SessionNegotiator}} that allows all
    association types that are specified by the OpenID
    specification. It prefers to use HMAC-SHA1/DH-SHA1, if it's
    available. If HMAC-SHA256 is not supported by your Python runtime,
    HMAC-SHA256 and DH-SHA256 will not be available.

@var encrypted_negotiator: A C{L{SessionNegotiator}} that
    does not support C{'no-encryption'} associations. It prefers
    HMAC-SHA1/DH-SHA1 association types if available.
"""

__all__ = [
    'default_negotiator',
    'encrypted_negotiator',
    'SessionNegotiator',
    'Association',
    ]

import time

from openid import cryptutil
from openid import kvform
from openid import oidutil
from openid.message import OPENID_NS

all_association_types = [
    'HMAC-SHA1',
    'HMAC-SHA256',
    ]

if hasattr(cryptutil, 'hmacSha256'):
    supported_association_types = list(all_association_types)

    default_association_order = [
        ('HMAC-SHA1', 'DH-SHA1'),
        ('HMAC-SHA1', 'no-encryption'),
        ('HMAC-SHA256', 'DH-SHA256'),
        ('HMAC-SHA256', 'no-encryption'),
        ]

    only_encrypted_association_order = [
        ('HMAC-SHA1', 'DH-SHA1'),
        ('HMAC-SHA256', 'DH-SHA256'),
        ]
else:
    supported_association_types = ['HMAC-SHA1']

    default_association_order = [
        ('HMAC-SHA1', 'DH-SHA1'),
        ('HMAC-SHA1', 'no-encryption'),
        ]

    only_encrypted_association_order = [
        ('HMAC-SHA1', 'DH-SHA1'),
        ]

def getSessionTypes(assoc_type):
    """Return the allowed session types for a given association type"""
    assoc_to_session = {
        'HMAC-SHA1': ['DH-SHA1', 'no-encryption'],
        'HMAC-SHA256': ['DH-SHA256', 'no-encryption'],
        }
    return assoc_to_session.get(assoc_type, [])

def checkSessionType(assoc_type, session_type):
    """Check to make sure that this pair of assoc type and session
    type are allowed"""
    if session_type not in getSessionTypes(assoc_type):
        raise ValueError(
            'Session type %r not valid for assocation type %r'
            % (session_type, assoc_type))

class SessionNegotiator(object):
    """A session negotiator controls the allowed and preferred
    association types and association session types. Both the
    C{L{Consumer<openid.consumer.consumer.Consumer>}} and
    C{L{Server<openid.server.server.Server>}} use negotiators when
    creating associations.

    You can create and use negotiators if you:

     - Do not want to do Diffie-Hellman key exchange because you use
       transport-layer encryption (e.g. SSL)

     - Want to use only SHA-256 associations

     - Do not want to support plain-text associations over a non-secure
       channel

    It is up to you to set a policy for what kinds of associations to
    accept. By default, the library will make any kind of association
    that is allowed in the OpenID 2.0 specification.

    Use of negotiators in the library
    =================================

    When a consumer makes an association request, it calls
    C{L{getAllowedType}} to get the preferred association type and
    association session type.

    The server gets a request for a particular association/session
    type and calls C{L{isAllowed}} to determine if it should
    create an association. If it is supported, negotiation is
    complete. If it is not, the server calls C{L{getAllowedType}} to
    get an allowed association type to return to the consumer.

    If the consumer gets an error response indicating that the
    requested association/session type is not supported by the server
    that contains an assocation/session type to try, it calls
    C{L{isAllowed}} to determine if it should try again with the
    given combination of association/session type.

    @ivar allowed_types: A list of association/session types that are
        allowed by the server. The order of the pairs in this list
        determines preference. If an association/session type comes
        earlier in the list, the library is more likely to use that
        type.
    @type allowed_types: [(str, str)]
    """

    def __init__(self, allowed_types):
        self.setAllowedTypes(allowed_types)

    def copy(self):
        return self.__class__(list(self.allowed_types))

    def setAllowedTypes(self, allowed_types):
        """Set the allowed association types, checking to make sure
        each combination is valid."""
        for (assoc_type, session_type) in allowed_types:
            checkSessionType(assoc_type, session_type)

        self.allowed_types = allowed_types

    def addAllowedType(self, assoc_type, session_type=None):
        """Add an association type and session type to the allowed
        types list. The assocation/session pairs are tried in the
        order that they are added."""
        if self.allowed_types is None:
            self.allowed_types = []

        if session_type is None:
            available = getSessionTypes(assoc_type)

            if not available:
                raise ValueError('No session available for association type %r'
                                 % (assoc_type,))

            for session_type in getSessionTypes(assoc_type):
                self.addAllowedType(assoc_type, session_type)
        else:
            checkSessionType(assoc_type, session_type)
            self.allowed_types.append((assoc_type, session_type))


    def isAllowed(self, assoc_type, session_type):
        """Is this combination of association type and session type allowed?"""
        assoc_good = (assoc_type, session_type) in self.allowed_types
        matches = session_type in getSessionTypes(assoc_type)
        return assoc_good and matches

    def getAllowedType(self):
        """Get a pair of assocation type and session type that are
        supported"""
        try:
            return self.allowed_types[0]
        except IndexError:
            return (None, None)

default_negotiator = SessionNegotiator(default_association_order)
encrypted_negotiator = SessionNegotiator(only_encrypted_association_order)

def getSecretSize(assoc_type):
    if assoc_type == 'HMAC-SHA1':
        return 20
    elif assoc_type == 'HMAC-SHA256':
        return 32
    else:
        raise ValueError('Unsupported association type: %r' % (assoc_type,))

class Association(object):
    """
    This class represents an association between a server and a
    consumer.  In general, users of this library will never see
    instances of this object.  The only exception is if you implement
    a custom C{L{OpenIDStore<openid.store.interface.OpenIDStore>}}.

    If you do implement such a store, it will need to store the values
    of the C{L{handle}}, C{L{secret}}, C{L{issued}}, C{L{lifetime}}, and
    C{L{assoc_type}} instance variables.

    @ivar handle: This is the handle the server gave this association.

    @type handle: C{str}


    @ivar secret: This is the shared secret the server generated for
        this association.

    @type secret: C{str}


    @ivar issued: This is the time this association was issued, in
        seconds since 00:00 GMT, January 1, 1970.  (ie, a unix
        timestamp)

    @type issued: C{int}


    @ivar lifetime: This is the amount of time this association is
        good for, measured in seconds since the association was
        issued.

    @type lifetime: C{int}


    @ivar assoc_type: This is the type of association this instance
        represents.  The only valid value of this field at this time
        is C{'HMAC-SHA1'}, but new types may be defined in the future.

    @type assoc_type: C{str}


    @sort: __init__, fromExpiresIn, getExpiresIn, __eq__, __ne__,
        handle, secret, issued, lifetime, assoc_type
    """

    # The ordering and name of keys as stored by serialize
    assoc_keys = [
        'version',
        'handle',
        'secret',
        'issued',
        'lifetime',
        'assoc_type',
        ]


    _macs = {
        'HMAC-SHA1': cryptutil.hmacSha1,
        'HMAC-SHA256': cryptutil.hmacSha256,
        }


    def fromExpiresIn(cls, expires_in, handle, secret, assoc_type):
        """
        This is an alternate constructor used by the OpenID consumer
        library to create associations.  C{L{OpenIDStore
        <openid.store.interface.OpenIDStore>}} implementations
        shouldn't use this constructor.


        @param expires_in: This is the amount of time this association
            is good for, measured in seconds since the association was
            issued.

        @type expires_in: C{int}


        @param handle: This is the handle the server gave this
            association.

        @type handle: C{str}


        @param secret: This is the shared secret the server generated
            for this association.

        @type secret: C{str}


        @param assoc_type: This is the type of association this
            instance represents.  The only valid value of this field
            at this time is C{'HMAC-SHA1'}, but new types may be
            defined in the future.

        @type assoc_type: C{str}
        """
        issued = int(time.time())
        lifetime = expires_in
        return cls(handle, secret, issued, lifetime, assoc_type)

    fromExpiresIn = classmethod(fromExpiresIn)

    def __init__(self, handle, secret, issued, lifetime, assoc_type):
        """
        This is the standard constructor for creating an association.


        @param handle: This is the handle the server gave this
            association.

        @type handle: C{str}


        @param secret: This is the shared secret the server generated
            for this association.

        @type secret: C{str}


        @param issued: This is the time this association was issued,
            in seconds since 00:00 GMT, January 1, 1970.  (ie, a unix
            timestamp)

        @type issued: C{int}


        @param lifetime: This is the amount of time this association
            is good for, measured in seconds since the association was
            issued.

        @type lifetime: C{int}


        @param assoc_type: This is the type of association this
            instance represents.  The only valid value of this field
            at this time is C{'HMAC-SHA1'}, but new types may be
            defined in the future.

        @type assoc_type: C{str}
        """
        if assoc_type not in all_association_types:
            fmt = '%r is not a supported association type'
            raise ValueError(fmt % (assoc_type,))

#         secret_size = getSecretSize(assoc_type)
#         if len(secret) != secret_size:
#             fmt = 'Wrong size secret (%s bytes) for association type %s'
#             raise ValueError(fmt % (len(secret), assoc_type))

        self.handle = handle
        self.secret = secret
        self.issued = issued
        self.lifetime = lifetime
        self.assoc_type = assoc_type

    def getExpiresIn(self, now=None):
        """
        This returns the number of seconds this association is still
        valid for, or C{0} if the association is no longer valid.


        @return: The number of seconds this association is still valid
            for, or C{0} if the association is no longer valid.

        @rtype: C{int}
        """
        if now is None:
            now = int(time.time())

        return max(0, self.issued + self.lifetime - now)

    expiresIn = property(getExpiresIn)

    def __eq__(self, other):
        """
        This checks to see if two C{L{Association}} instances
        represent the same association.


        @return: C{True} if the two instances represent the same
            association, C{False} otherwise.

        @rtype: C{bool}
        """
        return type(self) is type(other) and self.__dict__ == other.__dict__

    def __ne__(self, other):
        """
        This checks to see if two C{L{Association}} instances
        represent different associations.


        @return: C{True} if the two instances represent different
            associations, C{False} otherwise.

        @rtype: C{bool}
        """
        return not (self == other)

    def serialize(self):
        """
        Convert an association to KV form.

        @return: String in KV form suitable for deserialization by
            deserialize.

        @rtype: str
        """
        data = {
            'version':'2',
            'handle':self.handle,
            'secret':oidutil.toBase64(self.secret),
            'issued':str(int(self.issued)),
            'lifetime':str(int(self.lifetime)),
            'assoc_type':self.assoc_type
            }

        assert len(data) == len(self.assoc_keys)
        pairs = []
        for field_name in self.assoc_keys:
            pairs.append((field_name, data[field_name]))

        return kvform.seqToKV(pairs, strict=True)

    def deserialize(cls, assoc_s):
        """
        Parse an association as stored by serialize().

        inverse of serialize


        @param assoc_s: Association as serialized by serialize()

        @type assoc_s: str


        @return: instance of this class
        """
        pairs = kvform.kvToSeq(assoc_s, strict=True)
        keys = []
        values = []
        for k, v in pairs:
            keys.append(k)
            values.append(v)

        if keys != cls.assoc_keys:
            raise ValueError('Unexpected key values: %r', keys)

        version, handle, secret, issued, lifetime, assoc_type = values
        if version != '2':
            raise ValueError('Unknown version: %r' % version)
        issued = int(issued)
        lifetime = int(lifetime)
        secret = oidutil.fromBase64(secret)
        return cls(handle, secret, issued, lifetime, assoc_type)

    deserialize = classmethod(deserialize)

    def sign(self, pairs):
        """
        Generate a signature for a sequence of (key, value) pairs


        @param pairs: The pairs to sign, in order

        @type pairs: sequence of (str, str)


        @return: The binary signature of this sequence of pairs

        @rtype: str
        """
        kv = kvform.seqToKV(pairs)

        try:
            mac = self._macs[self.assoc_type]
        except KeyError:
            raise ValueError(
                'Unknown association type: %r' % (self.assoc_type,))

        return mac(self.secret, kv)


    def getMessageSignature(self, message):
        """Return the signature of a message.

        If I am not a sign-all association, the message must have a
        signed list.

        @return: the signature, base64 encoded

        @rtype: str

        @raises ValueError: If there is no signed list and I am not a sign-all
            type of association.
        """
        pairs = self._makePairs(message)
        return oidutil.toBase64(self.sign(pairs))

    def signMessage(self, message):
        """Add a signature (and a signed list) to a message.

        @return: a new Message object with a signature
        @rtype: L{openid.message.Message}
        """
        if (message.hasKey(OPENID_NS, 'sig') or
            message.hasKey(OPENID_NS, 'signed')):
            raise ValueError('Message already has signed list or signature')

        extant_handle = message.getArg(OPENID_NS, 'assoc_handle')
        if extant_handle and extant_handle != self.handle:
            raise ValueError("Message has a different association handle")

        signed_message = message.copy()
        signed_message.setArg(OPENID_NS, 'assoc_handle', self.handle)
        message_keys = signed_message.toPostArgs().keys()
        signed_list = [k[7:] for k in message_keys
                       if k.startswith('openid.')]
        signed_list.append('signed')
        signed_list.sort()
        signed_message.setArg(OPENID_NS, 'signed', ','.join(signed_list))
        sig = self.getMessageSignature(signed_message)
        signed_message.setArg(OPENID_NS, 'sig', sig)
        return signed_message

    def checkMessageSignature(self, message):
        """Given a message with a signature, calculate a new signature
        and return whether it matches the signature in the message.

        @raises ValueError: if the message has no signature or no signature
            can be calculated for it.
        """
        message_sig = message.getArg(OPENID_NS, 'sig')
        if not message_sig:
            raise ValueError("%s has no sig." % (message,))
        calculated_sig = self.getMessageSignature(message)
        return cryptutil.const_eq(calculated_sig, message_sig)


    def _makePairs(self, message):
        signed = message.getArg(OPENID_NS, 'signed')
        if not signed:
            raise ValueError('Message has no signed list: %s' % (message,))

        signed_list = signed.split(',')
        pairs = []
        data = message.toPostArgs()
        for field in signed_list:
            pairs.append((field, data.get('openid.' + field, '')))
        return pairs

    def __repr__(self):
        return "<%s.%s %s %s>" % (
            self.__class__.__module__,
            self.__class__.__name__,
            self.assoc_type,
            self.handle)

########NEW FILE########
__FILENAME__ = consumer
# -*- test-case-name: openid.test.test_consumer -*-
"""OpenID support for Relying Parties (aka Consumers).

This module documents the main interface with the OpenID consumer
library.  The only part of the library which has to be used and isn't
documented in full here is the store required to create an
C{L{Consumer}} instance.  More on the abstract store type and
concrete implementations of it that are provided in the documentation
for the C{L{__init__<Consumer.__init__>}} method of the
C{L{Consumer}} class.


OVERVIEW
========

    The OpenID identity verification process most commonly uses the
    following steps, as visible to the user of this library:

        1. The user enters their OpenID into a field on the consumer's
           site, and hits a login button.

        2. The consumer site discovers the user's OpenID provider using
           the Yadis protocol.

        3. The consumer site sends the browser a redirect to the
           OpenID provider.  This is the authentication request as
           described in the OpenID specification.

        4. The OpenID provider's site sends the browser a redirect
           back to the consumer site.  This redirect contains the
           provider's response to the authentication request.

    The most important part of the flow to note is the consumer's site
    must handle two separate HTTP requests in order to perform the
    full identity check.


LIBRARY DESIGN
==============

    This consumer library is designed with that flow in mind.  The
    goal is to make it as easy as possible to perform the above steps
    securely.

    At a high level, there are two important parts in the consumer
    library.  The first important part is this module, which contains
    the interface to actually use this library.  The second is the
    C{L{openid.store.interface}} module, which describes the
    interface to use if you need to create a custom method for storing
    the state this library needs to maintain between requests.

    In general, the second part is less important for users of the
    library to know about, as several implementations are provided
    which cover a wide variety of situations in which consumers may
    use the library.

    This module contains a class, C{L{Consumer}}, with methods
    corresponding to the actions necessary in each of steps 2, 3, and
    4 described in the overview.  Use of this library should be as easy
    as creating an C{L{Consumer}} instance and calling the methods
    appropriate for the action the site wants to take.


SESSIONS, STORES, AND STATELESS MODE
====================================

    The C{L{Consumer}} object keeps track of two types of state:

        1. State of the user's current authentication attempt.  Things like
           the identity URL, the list of endpoints discovered for that
           URL, and in case where some endpoints are unreachable, the list
           of endpoints already tried.  This state needs to be held from
           Consumer.begin() to Consumer.complete(), but it is only applicable
           to a single session with a single user agent, and at the end of
           the authentication process (i.e. when an OP replies with either
           C{id_res} or C{cancel}) it may be discarded.

        2. State of relationships with servers, i.e. shared secrets
           (associations) with servers and nonces seen on signed messages.
           This information should persist from one session to the next and
           should not be bound to a particular user-agent.


    These two types of storage are reflected in the first two arguments of
    Consumer's constructor, C{session} and C{store}.  C{session} is a
    dict-like object and we hope your web framework provides you with one
    of these bound to the user agent.  C{store} is an instance of
    L{openid.store.interface.OpenIDStore}.

    Since the store does hold secrets shared between your application and the
    OpenID provider, you should be careful about how you use it in a shared
    hosting environment.  If the filesystem or database permissions of your
    web host allow strangers to read from them, do not store your data there!
    If you have no safe place to store your data, construct your consumer
    with C{None} for the store, and it will operate only in stateless mode.
    Stateless mode may be slower, put more load on the OpenID provider, and
    trusts the provider to keep you safe from replay attacks.


    Several store implementation are provided, and the interface is
    fully documented so that custom stores can be used as well.  See
    the documentation for the C{L{Consumer}} class for more
    information on the interface for stores.  The implementations that
    are provided allow the consumer site to store the necessary data
    in several different ways, including several SQL databases and
    normal files on disk.


IMMEDIATE MODE
==============

    In the flow described above, the user may need to confirm to the
    OpenID provider that it's ok to disclose his or her identity.
    The provider may draw pages asking for information from the user
    before it redirects the browser back to the consumer's site.  This
    is generally transparent to the consumer site, so it is typically
    ignored as an implementation detail.

    There can be times, however, where the consumer site wants to get
    a response immediately.  When this is the case, the consumer can
    put the library in immediate mode.  In immediate mode, there is an
    extra response possible from the server, which is essentially the
    server reporting that it doesn't have enough information to answer
    the question yet.


USING THIS LIBRARY
==================

    Integrating this library into an application is usually a
    relatively straightforward process.  The process should basically
    follow this plan:

    Add an OpenID login field somewhere on your site.  When an OpenID
    is entered in that field and the form is submitted, it should make
    a request to your site which includes that OpenID URL.

    First, the application should L{instantiate a Consumer<Consumer.__init__>}
    with a session for per-user state and store for shared state.
    using the store of choice.

    Next, the application should call the 'C{L{begin<Consumer.begin>}}' method on the
    C{L{Consumer}} instance.  This method takes the OpenID URL.  The
    C{L{begin<Consumer.begin>}} method returns an C{L{AuthRequest}}
    object.

    Next, the application should call the
    C{L{redirectURL<AuthRequest.redirectURL>}} method on the
    C{L{AuthRequest}} object.  The parameter C{return_to} is the URL
    that the OpenID server will send the user back to after attempting
    to verify his or her identity.  The C{realm} parameter is the
    URL (or URL pattern) that identifies your web site to the user
    when he or she is authorizing it.  Send a redirect to the
    resulting URL to the user's browser.

    That's the first half of the authentication process.  The second
    half of the process is done after the user's OpenID Provider sends the
    user's browser a redirect back to your site to complete their
    login.

    When that happens, the user will contact your site at the URL
    given as the C{return_to} URL to the
    C{L{redirectURL<AuthRequest.redirectURL>}} call made
    above.  The request will have several query parameters added to
    the URL by the OpenID provider as the information necessary to
    finish the request.

    Get a C{L{Consumer}} instance with the same session and store as
    before and call its C{L{complete<Consumer.complete>}} method,
    passing in all the received query arguments.

    There are multiple possible return types possible from that
    method. These indicate whether or not the login was successful,
    and include any additional information appropriate for their type.

@var SUCCESS: constant used as the status for
    L{SuccessResponse<openid.consumer.consumer.SuccessResponse>} objects.

@var FAILURE: constant used as the status for
    L{FailureResponse<openid.consumer.consumer.FailureResponse>} objects.

@var CANCEL: constant used as the status for
    L{CancelResponse<openid.consumer.consumer.CancelResponse>} objects.

@var SETUP_NEEDED: constant used as the status for
    L{SetupNeededResponse<openid.consumer.consumer.SetupNeededResponse>}
    objects.
"""

import cgi
import copy
import logging
from urlparse import urlparse, urldefrag

from openid import fetchers

from openid.consumer.discover import discover, OpenIDServiceEndpoint, \
     DiscoveryFailure, OPENID_1_0_TYPE, OPENID_1_1_TYPE, OPENID_2_0_TYPE
from openid.message import Message, OPENID_NS, OPENID2_NS, OPENID1_NS, \
     IDENTIFIER_SELECT, no_default, BARE_NS
from openid import cryptutil
from openid import oidutil
from openid.association import Association, default_negotiator, \
     SessionNegotiator
from openid.dh import DiffieHellman
from openid.store.nonce import mkNonce, split as splitNonce
from openid.yadis.manager import Discovery
from openid import urinorm


__all__ = ['AuthRequest', 'Consumer', 'SuccessResponse',
           'SetupNeededResponse', 'CancelResponse', 'FailureResponse',
           'SUCCESS', 'FAILURE', 'CANCEL', 'SETUP_NEEDED',
           ]


def makeKVPost(request_message, server_url):
    """Make a Direct Request to an OpenID Provider and return the
    result as a Message object.

    @raises openid.fetchers.HTTPFetchingError: if an error is
        encountered in making the HTTP post.

    @rtype: L{openid.message.Message}
    """
    # XXX: TESTME
    resp = fetchers.fetch(server_url, body=request_message.toURLEncoded())

    # Process response in separate function that can be shared by async code.
    return _httpResponseToMessage(resp, server_url)


def _httpResponseToMessage(response, server_url):
    """Adapt a POST response to a Message.

    @type response: L{openid.fetchers.HTTPResponse}
    @param response: Result of a POST to an OpenID endpoint.

    @rtype: L{openid.message.Message}

    @raises openid.fetchers.HTTPFetchingError: if the server returned a
        status of other than 200 or 400.

    @raises ServerError: if the server returned an OpenID error.
    """
    # Should this function be named Message.fromHTTPResponse instead?
    response_message = Message.fromKVForm(response.body)
    if response.status == 400:
        raise ServerError.fromMessage(response_message)

    elif response.status not in (200, 206):
        fmt = 'bad status code from server %s: %s'
        error_message = fmt % (server_url, response.status)
        raise fetchers.HTTPFetchingError(error_message)

    return response_message



class Consumer(object):
    """An OpenID consumer implementation that performs discovery and
    does session management.

    @ivar consumer: an instance of an object implementing the OpenID
        protocol, but doing no discovery or session management.

    @type consumer: GenericConsumer

    @ivar session: A dictionary-like object representing the user's
        session data.  This is used for keeping state of the OpenID
        transaction when the user is redirected to the server.

    @cvar session_key_prefix: A string that is prepended to session
        keys to ensure that they are unique. This variable may be
        changed to suit your application.
    """
    session_key_prefix = "_openid_consumer_"

    _token = 'last_token'

    _discover = staticmethod(discover)

    def __init__(self, session, store, consumer_class=None):
        """Initialize a Consumer instance.

        You should create a new instance of the Consumer object with
        every HTTP request that handles OpenID transactions.

        @param session: See L{the session instance variable<openid.consumer.consumer.Consumer.session>}

        @param store: an object that implements the interface in
            C{L{openid.store.interface.OpenIDStore}}.  Several
            implementations are provided, to cover common database
            environments.

        @type store: C{L{openid.store.interface.OpenIDStore}}

        @see: L{openid.store.interface}
        @see: L{openid.store}
        """
        self.session = session
        if consumer_class is None:
            consumer_class = GenericConsumer
        self.consumer = consumer_class(store)
        self._token_key = self.session_key_prefix + self._token

    def begin(self, user_url, anonymous=False):
        """Start the OpenID authentication process. See steps 1-2 in
        the overview at the top of this file.

        @param user_url: Identity URL given by the user. This method
            performs a textual transformation of the URL to try and
            make sure it is normalized. For example, a user_url of
            example.com will be normalized to http://example.com/
            normalizing and resolving any redirects the server might
            issue.

        @type user_url: unicode

        @param anonymous: Whether to make an anonymous request of the OpenID
            provider.  Such a request does not ask for an authorization
            assertion for an OpenID identifier, but may be used with
            extensions to pass other data.  e.g. "I don't care who you are,
            but I'd like to know your time zone."

        @type anonymous: bool

        @returns: An object containing the discovered information will
            be returned, with a method for building a redirect URL to
            the server, as described in step 3 of the overview. This
            object may also be used to add extension arguments to the
            request, using its
            L{addExtensionArg<openid.consumer.consumer.AuthRequest.addExtensionArg>}
            method.

        @returntype: L{AuthRequest<openid.consumer.consumer.AuthRequest>}

        @raises openid.consumer.discover.DiscoveryFailure: when I fail to
            find an OpenID server for this URL.  If the C{yadis} package
            is available, L{openid.consumer.discover.DiscoveryFailure} is
            an alias for C{yadis.discover.DiscoveryFailure}.
        """
        disco = Discovery(self.session, user_url, self.session_key_prefix)
        try:
            service = disco.getNextService(self._discover)
        except fetchers.HTTPFetchingError, why:
            raise DiscoveryFailure(
                'Error fetching XRDS document: %s' % (why[0],), None)

        if service is None:
            raise DiscoveryFailure(
                'No usable OpenID services found for %s' % (user_url,), None)
        else:
            return self.beginWithoutDiscovery(service, anonymous)

    def beginWithoutDiscovery(self, service, anonymous=False):
        """Start OpenID verification without doing OpenID server
        discovery. This method is used internally by Consumer.begin
        after discovery is performed, and exists to provide an
        interface for library users needing to perform their own
        discovery.

        @param service: an OpenID service endpoint descriptor.  This
            object and factories for it are found in the
            L{openid.consumer.discover} module.

        @type service:
            L{OpenIDServiceEndpoint<openid.consumer.discover.OpenIDServiceEndpoint>}

        @returns: an OpenID authentication request object.

        @rtype: L{AuthRequest<openid.consumer.consumer.AuthRequest>}

        @See: Openid.consumer.consumer.Consumer.begin
        @see: openid.consumer.discover
        """
        auth_req = self.consumer.begin(service)
        self.session[self._token_key] = auth_req.endpoint

        try:
            auth_req.setAnonymous(anonymous)
        except ValueError, why:
            raise ProtocolError(str(why))

        return auth_req

    def complete(self, query, current_url):
        """Called to interpret the server's response to an OpenID
        request. It is called in step 4 of the flow described in the
        consumer overview.

        @param query: A dictionary of the query parameters for this
            HTTP request.

        @param current_url: The URL used to invoke the application.
            Extract the URL from your application's web
            request framework and specify it here to have it checked
            against the openid.return_to value in the response.  If
            the return_to URL check fails, the status of the
            completion will be FAILURE.

        @returns: a subclass of Response. The type of response is
            indicated by the status attribute, which will be one of
            SUCCESS, CANCEL, FAILURE, or SETUP_NEEDED.

        @see: L{SuccessResponse<openid.consumer.consumer.SuccessResponse>}
        @see: L{CancelResponse<openid.consumer.consumer.CancelResponse>}
        @see: L{SetupNeededResponse<openid.consumer.consumer.SetupNeededResponse>}
        @see: L{FailureResponse<openid.consumer.consumer.FailureResponse>}
        """

        endpoint = self.session.get(self._token_key)

        message = Message.fromPostArgs(query)
        response = self.consumer.complete(message, endpoint, current_url)

        try:
            del self.session[self._token_key]
        except KeyError:
            pass

        if (response.status in ['success', 'cancel'] and
            response.identity_url is not None):

            disco = Discovery(self.session,
                              response.identity_url,
                              self.session_key_prefix)
            # This is OK to do even if we did not do discovery in
            # the first place.
            disco.cleanup(force=True)

        return response

    def setAssociationPreference(self, association_preferences):
        """Set the order in which association types/sessions should be
        attempted. For instance, to only allow HMAC-SHA256
        associations created with a DH-SHA256 association session:

        >>> consumer.setAssociationPreference([('HMAC-SHA256', 'DH-SHA256')])

        Any association type/association type pair that is not in this
        list will not be attempted at all.

        @param association_preferences: The list of allowed
            (association type, association session type) pairs that
            should be allowed for this consumer to use, in order from
            most preferred to least preferred.
        @type association_preferences: [(str, str)]

        @returns: None

        @see: C{L{openid.association.SessionNegotiator}}
        """
        self.consumer.negotiator = SessionNegotiator(association_preferences)

class DiffieHellmanSHA1ConsumerSession(object):
    session_type = 'DH-SHA1'
    hash_func = staticmethod(cryptutil.sha1)
    secret_size = 20
    allowed_assoc_types = ['HMAC-SHA1']

    def __init__(self, dh=None):
        if dh is None:
            dh = DiffieHellman.fromDefaults()

        self.dh = dh

    def getRequest(self):
        cpub = cryptutil.longToBase64(self.dh.public)

        args = {'dh_consumer_public': cpub}

        if not self.dh.usingDefaultValues():
            args.update({
                'dh_modulus': cryptutil.longToBase64(self.dh.modulus),
                'dh_gen': cryptutil.longToBase64(self.dh.generator),
                })

        return args

    def extractSecret(self, response):
        dh_server_public64 = response.getArg(
            OPENID_NS, 'dh_server_public', no_default)
        enc_mac_key64 = response.getArg(OPENID_NS, 'enc_mac_key', no_default)
        dh_server_public = cryptutil.base64ToLong(dh_server_public64)
        enc_mac_key = oidutil.fromBase64(enc_mac_key64)
        return self.dh.xorSecret(dh_server_public, enc_mac_key, self.hash_func)

class DiffieHellmanSHA256ConsumerSession(DiffieHellmanSHA1ConsumerSession):
    session_type = 'DH-SHA256'
    hash_func = staticmethod(cryptutil.sha256)
    secret_size = 32
    allowed_assoc_types = ['HMAC-SHA256']

class PlainTextConsumerSession(object):
    session_type = 'no-encryption'
    allowed_assoc_types = ['HMAC-SHA1', 'HMAC-SHA256']

    def getRequest(self):
        return {}

    def extractSecret(self, response):
        mac_key64 = response.getArg(OPENID_NS, 'mac_key', no_default)
        return oidutil.fromBase64(mac_key64)

class SetupNeededError(Exception):
    """Internally-used exception that indicates that an immediate-mode
    request cancelled."""
    def __init__(self, user_setup_url=None):
        Exception.__init__(self, user_setup_url)
        self.user_setup_url = user_setup_url

class ProtocolError(ValueError):
    """Exception that indicates that a message violated the
    protocol. It is raised and caught internally to this file."""

class TypeURIMismatch(ProtocolError):
    """A protocol error arising from type URIs mismatching
    """

    def __init__(self, expected, endpoint):
        ProtocolError.__init__(self, expected, endpoint)
        self.expected = expected
        self.endpoint = endpoint

    def __str__(self):
        s = '<%s.%s: Required type %s not found in %s for endpoint %s>' % (
            self.__class__.__module__, self.__class__.__name__,
            self.expected, self.endpoint.type_uris, self.endpoint)
        return s



class ServerError(Exception):
    """Exception that is raised when the server returns a 400 response
    code to a direct request."""

    def __init__(self, error_text, error_code, message):
        Exception.__init__(self, error_text)
        self.error_text = error_text
        self.error_code = error_code
        self.message = message

    def fromMessage(cls, message):
        """Generate a ServerError instance, extracting the error text
        and the error code from the message."""
        error_text = message.getArg(
            OPENID_NS, 'error', '<no error message supplied>')
        error_code = message.getArg(OPENID_NS, 'error_code')
        return cls(error_text, error_code, message)

    fromMessage = classmethod(fromMessage)

class GenericConsumer(object):
    """This is the implementation of the common logic for OpenID
    consumers. It is unaware of the application in which it is
    running.

    @ivar negotiator: An object that controls the kind of associations
        that the consumer makes. It defaults to
        C{L{openid.association.default_negotiator}}. Assign a
        different negotiator to it if you have specific requirements
        for how associations are made.
    @type negotiator: C{L{openid.association.SessionNegotiator}}
    """

    # The name of the query parameter that gets added to the return_to
    # URL when using OpenID1. You can change this value if you want or
    # need a different name, but don't make it start with openid,
    # because it's not a standard protocol thing for OpenID1. For
    # OpenID2, the library will take care of the nonce using standard
    # OpenID query parameter names.
    openid1_nonce_query_arg_name = 'janrain_nonce'

    # Another query parameter that gets added to the return_to for
    # OpenID 1; if the user's session state is lost, use this claimed
    # identifier to do discovery when verifying the response.
    openid1_return_to_identifier_name = 'openid1_claimed_id'

    session_types = {
        'DH-SHA1':DiffieHellmanSHA1ConsumerSession,
        'DH-SHA256':DiffieHellmanSHA256ConsumerSession,
        'no-encryption':PlainTextConsumerSession,
        }

    _discover = staticmethod(discover)

    def __init__(self, store):
        self.store = store
        self.negotiator = default_negotiator.copy()

    def begin(self, service_endpoint):
        """Create an AuthRequest object for the specified
        service_endpoint. This method will create an association if
        necessary."""
        if self.store is None:
            assoc = None
        else:
            assoc = self._getAssociation(service_endpoint)

        request = AuthRequest(service_endpoint, assoc)
        request.return_to_args[self.openid1_nonce_query_arg_name] = mkNonce()

        if request.message.isOpenID1():
            request.return_to_args[self.openid1_return_to_identifier_name] = \
                request.endpoint.claimed_id

        return request

    def complete(self, message, endpoint, return_to):
        """Process the OpenID message, using the specified endpoint
        and return_to URL as context. This method will handle any
        OpenID message that is sent to the return_to URL.
        """
        mode = message.getArg(OPENID_NS, 'mode', '<No mode set>')

        modeMethod = getattr(self, '_complete_' + mode,
                             self._completeInvalid)

        return modeMethod(message, endpoint, return_to)

    def _complete_cancel(self, message, endpoint, _):
        return CancelResponse(endpoint)

    def _complete_error(self, message, endpoint, _):
        error = message.getArg(OPENID_NS, 'error')
        contact = message.getArg(OPENID_NS, 'contact')
        reference = message.getArg(OPENID_NS, 'reference')

        return FailureResponse(endpoint, error, contact=contact,
                               reference=reference)

    def _complete_setup_needed(self, message, endpoint, _):
        if not message.isOpenID2():
            return self._completeInvalid(message, endpoint, _)

        user_setup_url = message.getArg(OPENID2_NS, 'user_setup_url')
        return SetupNeededResponse(endpoint, user_setup_url)

    def _complete_id_res(self, message, endpoint, return_to):
        try:
            self._checkSetupNeeded(message)
        except SetupNeededError, why:
            return SetupNeededResponse(endpoint, why.user_setup_url)
        else:
            try:
                return self._doIdRes(message, endpoint, return_to)
            except (ProtocolError, DiscoveryFailure), why:
                return FailureResponse(endpoint, why[0])

    def _completeInvalid(self, message, endpoint, _):
        mode = message.getArg(OPENID_NS, 'mode', '<No mode set>')
        return FailureResponse(endpoint,
                               'Invalid openid.mode: %r' % (mode,))

    def _checkReturnTo(self, message, return_to):
        """Check an OpenID message and its openid.return_to value
        against a return_to URL from an application.  Return True on
        success, False on failure.
        """
        # Check the openid.return_to args against args in the original
        # message.
        try:
            self._verifyReturnToArgs(message.toPostArgs())
        except ProtocolError, why:
            logging.exception("Verifying return_to arguments: %s" % (why[0],))
            return False

        # Check the return_to base URL against the one in the message.
        msg_return_to = message.getArg(OPENID_NS, 'return_to')

        # The URL scheme, authority, and path MUST be the same between
        # the two URLs.
        app_parts = urlparse(urinorm.urinorm(return_to))
        msg_parts = urlparse(urinorm.urinorm(msg_return_to))

        # (addressing scheme, network location, path) must be equal in
        # both URLs.
        for part in range(0, 3):
            if app_parts[part] != msg_parts[part]:
                return False

        return True

    _makeKVPost = staticmethod(makeKVPost)

    def _checkSetupNeeded(self, message):
        """Check an id_res message to see if it is a
        checkid_immediate cancel response.

        @raises SetupNeededError: if it is a checkid_immediate cancellation
        """
        # In OpenID 1, we check to see if this is a cancel from
        # immediate mode by the presence of the user_setup_url
        # parameter.
        if message.isOpenID1():
            user_setup_url = message.getArg(OPENID1_NS, 'user_setup_url')
            if user_setup_url is not None:
                raise SetupNeededError(user_setup_url)

    def _doIdRes(self, message, endpoint, return_to):
        """Handle id_res responses that are not cancellations of
        immediate mode requests.

        @param message: the response paramaters.
        @param endpoint: the discovered endpoint object. May be None.

        @raises ProtocolError: If the message contents are not
            well-formed according to the OpenID specification. This
            includes missing fields or not signing fields that should
            be signed.

        @raises DiscoveryFailure: If the subject of the id_res message
            does not match the supplied endpoint, and discovery on the
            identifier in the message fails (this should only happen
            when using OpenID 2)

        @returntype: L{Response}
        """
        # Checks for presence of appropriate fields (and checks
        # signed list fields)
        self._idResCheckForFields(message)

        if not self._checkReturnTo(message, return_to):
            raise ProtocolError(
                "return_to does not match return URL. Expected %r, got %r"
                % (return_to, message.getArg(OPENID_NS, 'return_to')))


        # Verify discovery information:
        endpoint = self._verifyDiscoveryResults(message, endpoint)
        logging.info("Received id_res response from %s using association %s" %
                    (endpoint.server_url,
                     message.getArg(OPENID_NS, 'assoc_handle')))

        self._idResCheckSignature(message, endpoint.server_url)

        # Will raise a ProtocolError if the nonce is bad
        self._idResCheckNonce(message, endpoint)

        signed_list_str = message.getArg(OPENID_NS, 'signed', no_default)
        signed_list = signed_list_str.split(',')
        signed_fields = ["openid." + s for s in signed_list]
        return SuccessResponse(endpoint, message, signed_fields)

    def _idResGetNonceOpenID1(self, message, endpoint):
        """Extract the nonce from an OpenID 1 response.  Return the
        nonce from the BARE_NS since we independently check the
        return_to arguments are the same as those in the response
        message.

        See the openid1_nonce_query_arg_name class variable

        @returns: The nonce as a string or None
        """
        return message.getArg(BARE_NS, self.openid1_nonce_query_arg_name)

    def _idResCheckNonce(self, message, endpoint):
        if message.isOpenID1():
            # This indicates that the nonce was generated by the consumer
            nonce = self._idResGetNonceOpenID1(message, endpoint)
            server_url = ''
        else:
            nonce = message.getArg(OPENID2_NS, 'response_nonce')
            server_url = endpoint.server_url

        if nonce is None:
            raise ProtocolError('Nonce missing from response')

        try:
            timestamp, salt = splitNonce(nonce)
        except ValueError, why:
            raise ProtocolError('Malformed nonce: %s' % (why[0],))

        if (self.store is not None and
            not self.store.useNonce(server_url, timestamp, salt)):
            raise ProtocolError('Nonce already used or out of range')

    def _idResCheckSignature(self, message, server_url):
        assoc_handle = message.getArg(OPENID_NS, 'assoc_handle')
        if self.store is None:
            assoc = None
        else:
            assoc = self.store.getAssociation(server_url, assoc_handle)

        if assoc:
            if assoc.getExpiresIn() <= 0:
                # XXX: It might be a good idea sometimes to re-start the
                # authentication with a new association. Doing it
                # automatically opens the possibility for
                # denial-of-service by a server that just returns expired
                # associations (or really short-lived associations)
                raise ProtocolError(
                    'Association with %s expired' % (server_url,))

            if not assoc.checkMessageSignature(message):
                raise ProtocolError('Bad signature')

        else:
            # It's not an association we know about.  Stateless mode is our
            # only possible path for recovery.
            # XXX - async framework will not want to block on this call to
            # _checkAuth.
            if not self._checkAuth(message, server_url):
                raise ProtocolError('Server denied check_authentication')

    def _idResCheckForFields(self, message):
        # XXX: this should be handled by the code that processes the
        # response (that is, if a field is missing, we should not have
        # to explicitly check that it's present, just make sure that
        # the fields are actually being used by the rest of the code
        # in tests). Although, which fields are signed does need to be
        # checked somewhere.
        basic_fields = ['return_to', 'assoc_handle', 'sig', 'signed']
        basic_sig_fields = ['return_to', 'identity']

        require_fields = {
            OPENID2_NS: basic_fields + ['op_endpoint'],
            OPENID1_NS: basic_fields + ['identity'],
            }

        require_sigs = {
            OPENID2_NS: basic_sig_fields + ['response_nonce',
                                            'claimed_id',
                                            'assoc_handle',
                                            'op_endpoint',],
            OPENID1_NS: basic_sig_fields,
            }

        for field in require_fields[message.getOpenIDNamespace()]:
            if not message.hasKey(OPENID_NS, field):
                raise ProtocolError('Missing required field %r' % (field,))

        signed_list_str = message.getArg(OPENID_NS, 'signed', no_default)
        signed_list = signed_list_str.split(',')

        for field in require_sigs[message.getOpenIDNamespace()]:
            # Field is present and not in signed list
            if message.hasKey(OPENID_NS, field) and field not in signed_list:
                raise ProtocolError('"%s" not signed' % (field,))


    def _verifyReturnToArgs(query):
        """Verify that the arguments in the return_to URL are present in this
        response.
        """
        message = Message.fromPostArgs(query)
        return_to = message.getArg(OPENID_NS, 'return_to')

        if return_to is None:
            raise ProtocolError('Response has no return_to')

        parsed_url = urlparse(return_to)
        rt_query = parsed_url[4]
        parsed_args = cgi.parse_qsl(rt_query)

        for rt_key, rt_value in parsed_args:
            try:
                value = query[rt_key]
                if rt_value != value:
                    format = ("parameter %s value %r does not match "
                              "return_to's value %r")
                    raise ProtocolError(format % (rt_key, value, rt_value))
            except KeyError:
                format = "return_to parameter %s absent from query %r"
                raise ProtocolError(format % (rt_key, query))

        # Make sure all non-OpenID arguments in the response are also
        # in the signed return_to.
        bare_args = message.getArgs(BARE_NS)
        for pair in bare_args.iteritems():
            if pair not in parsed_args:
                raise ProtocolError("Parameter %s not in return_to URL" % (pair[0],))

    _verifyReturnToArgs = staticmethod(_verifyReturnToArgs)

    def _verifyDiscoveryResults(self, resp_msg, endpoint=None):
        """
        Extract the information from an OpenID assertion message and
        verify it against the original

        @param endpoint: The endpoint that resulted from doing discovery
        @param resp_msg: The id_res message object

        @returns: the verified endpoint
        """
        if resp_msg.getOpenIDNamespace() == OPENID2_NS:
            return self._verifyDiscoveryResultsOpenID2(resp_msg, endpoint)
        else:
            return self._verifyDiscoveryResultsOpenID1(resp_msg, endpoint)


    def _verifyDiscoveryResultsOpenID2(self, resp_msg, endpoint):
        to_match = OpenIDServiceEndpoint()
        to_match.type_uris = [OPENID_2_0_TYPE]
        to_match.claimed_id = resp_msg.getArg(OPENID2_NS, 'claimed_id')
        to_match.local_id = resp_msg.getArg(OPENID2_NS, 'identity')

        # Raises a KeyError when the op_endpoint is not present
        to_match.server_url = resp_msg.getArg(
            OPENID2_NS, 'op_endpoint', no_default)

        # claimed_id and identifier must both be present or both
        # be absent
        if (to_match.claimed_id is None and
            to_match.local_id is not None):
            raise ProtocolError(
                'openid.identity is present without openid.claimed_id')

        elif (to_match.claimed_id is not None and
              to_match.local_id is None):
            raise ProtocolError(
                'openid.claimed_id is present without openid.identity')

        # This is a response without identifiers, so there's really no
        # checking that we can do, so return an endpoint that's for
        # the specified `openid.op_endpoint'
        elif to_match.claimed_id is None:
            return OpenIDServiceEndpoint.fromOPEndpointURL(to_match.server_url)

        # The claimed ID doesn't match, so we have to do discovery
        # again. This covers not using sessions, OP identifier
        # endpoints and responses that didn't match the original
        # request.
        if not endpoint:
            logging.info('No pre-discovered information supplied.')
            endpoint = self._discoverAndVerify(to_match.claimed_id, [to_match])
        else:
            # The claimed ID matches, so we use the endpoint that we
            # discovered in initiation. This should be the most common
            # case.
            try:
                self._verifyDiscoverySingle(endpoint, to_match)
            except ProtocolError, e:
                logging.exception(
                    "Error attempting to use stored discovery information: " +
                    str(e))
                logging.info("Attempting discovery to verify endpoint")
                endpoint = self._discoverAndVerify(
                    to_match.claimed_id, [to_match])

        # The endpoint we return should have the claimed ID from the
        # message we just verified, fragment and all.
        if endpoint.claimed_id != to_match.claimed_id:
            endpoint = copy.copy(endpoint)
            endpoint.claimed_id = to_match.claimed_id
        return endpoint

    def _verifyDiscoveryResultsOpenID1(self, resp_msg, endpoint):
        claimed_id = resp_msg.getArg(BARE_NS, self.openid1_return_to_identifier_name)

        if endpoint is None and claimed_id is None:
            raise RuntimeError(
                'When using OpenID 1, the claimed ID must be supplied, '
                'either by passing it through as a return_to parameter '
                'or by using a session, and supplied to the GenericConsumer '
                'as the argument to complete()')
        elif endpoint is not None and claimed_id is None:
            claimed_id = endpoint.claimed_id

        to_match = OpenIDServiceEndpoint()
        to_match.type_uris = [OPENID_1_1_TYPE]
        to_match.local_id = resp_msg.getArg(OPENID1_NS, 'identity')
        # Restore delegate information from the initiation phase
        to_match.claimed_id = claimed_id

        if to_match.local_id is None:
            raise ProtocolError('Missing required field openid.identity')

        to_match_1_0 = copy.copy(to_match)
        to_match_1_0.type_uris = [OPENID_1_0_TYPE]

        if endpoint is not None:
            try:
                try:
                    self._verifyDiscoverySingle(endpoint, to_match)
                except TypeURIMismatch:
                    self._verifyDiscoverySingle(endpoint, to_match_1_0)
            except ProtocolError, e:
                logging.exception("Error attempting to use stored discovery information: " +
                            str(e))
                logging.info("Attempting discovery to verify endpoint")
            else:
                return endpoint

        # Endpoint is either bad (failed verification) or None
        return self._discoverAndVerify(claimed_id, [to_match, to_match_1_0])

    def _verifyDiscoverySingle(self, endpoint, to_match):
        """Verify that the given endpoint matches the information
        extracted from the OpenID assertion, and raise an exception if
        there is a mismatch.

        @type endpoint: openid.consumer.discover.OpenIDServiceEndpoint
        @type to_match: openid.consumer.discover.OpenIDServiceEndpoint

        @rtype: NoneType

        @raises ProtocolError: when the endpoint does not match the
            discovered information.
        """
        # Every type URI that's in the to_match endpoint has to be
        # present in the discovered endpoint.
        for type_uri in to_match.type_uris:
            if not endpoint.usesExtension(type_uri):
                raise TypeURIMismatch(type_uri, endpoint)

        # Fragments do not influence discovery, so we can't compare a
        # claimed identifier with a fragment to discovered information.
        defragged_claimed_id, _ = urldefrag(to_match.claimed_id)
        if defragged_claimed_id != endpoint.claimed_id:
            raise ProtocolError(
                'Claimed ID does not match (different subjects!), '
                'Expected %s, got %s' %
                (defragged_claimed_id, endpoint.claimed_id))

        if to_match.getLocalID() != endpoint.getLocalID():
            raise ProtocolError('local_id mismatch. Expected %s, got %s' %
                                (to_match.getLocalID(), endpoint.getLocalID()))

        # If the server URL is None, this must be an OpenID 1
        # response, because op_endpoint is a required parameter in
        # OpenID 2. In that case, we don't actually care what the
        # discovered server_url is, because signature checking or
        # check_auth should take care of that check for us.
        if to_match.server_url is None:
            assert to_match.preferredNamespace() == OPENID1_NS, (
                """The code calling this must ensure that OpenID 2
                responses have a non-none `openid.op_endpoint' and
                that it is set as the `server_url' attribute of the
                `to_match' endpoint.""")

        elif to_match.server_url != endpoint.server_url:
            raise ProtocolError('OP Endpoint mismatch. Expected %s, got %s' %
                                (to_match.server_url, endpoint.server_url))

    def _discoverAndVerify(self, claimed_id, to_match_endpoints):
        """Given an endpoint object created from the information in an
        OpenID response, perform discovery and verify the discovery
        results, returning the matching endpoint that is the result of
        doing that discovery.

        @type to_match: openid.consumer.discover.OpenIDServiceEndpoint
        @param to_match: The endpoint whose information we're confirming

        @rtype: openid.consumer.discover.OpenIDServiceEndpoint
        @returns: The result of performing discovery on the claimed
            identifier in `to_match'

        @raises DiscoveryFailure: when discovery fails.
        """
        logging.info('Performing discovery on %s' % (claimed_id,))
        _, services = self._discover(claimed_id)
        if not services:
            raise DiscoveryFailure('No OpenID information found at %s' %
                                   (claimed_id,), None)
        return self._verifyDiscoveredServices(claimed_id, services,
                                              to_match_endpoints)


    def _verifyDiscoveredServices(self, claimed_id, services, to_match_endpoints):
        """See @L{_discoverAndVerify}"""

        # Search the services resulting from discovery to find one
        # that matches the information from the assertion
        failure_messages = []
        for endpoint in services:
            for to_match_endpoint in to_match_endpoints:
                try:
                    self._verifyDiscoverySingle(
                        endpoint, to_match_endpoint)
                except ProtocolError, why:
                    failure_messages.append(str(why))
                else:
                    # It matches, so discover verification has
                    # succeeded. Return this endpoint.
                    return endpoint
        else:
            logging.error('Discovery verification failure for %s' %
                        (claimed_id,))
            for failure_message in failure_messages:
                logging.error(' * Endpoint mismatch: ' + failure_message)

            raise DiscoveryFailure(
                'No matching endpoint found after discovering %s'
                % (claimed_id,), None)

    def _checkAuth(self, message, server_url):
        """Make a check_authentication request to verify this message.

        @returns: True if the request is valid.
        @rtype: bool
        """
        logging.info('Using OpenID check_authentication')
        request = self._createCheckAuthRequest(message)
        if request is None:
            return False
        try:
            response = self._makeKVPost(request, server_url)
        except (fetchers.HTTPFetchingError, ServerError), e:
            logging.exception('check_authentication failed: %s' % (e[0],))
            return False
        else:
            return self._processCheckAuthResponse(response, server_url)

    def _createCheckAuthRequest(self, message):
        """Generate a check_authentication request message given an
        id_res message.
        """
        signed = message.getArg(OPENID_NS, 'signed')
        if signed:
            for k in signed.split(','):
                logging.info(k)
                val = message.getAliasedArg(k)

                # Signed value is missing
                if val is None:
                    logging.info('Missing signed field %r' % (k,))
                    return None

        check_auth_message = message.copy()
        check_auth_message.setArg(OPENID_NS, 'mode', 'check_authentication')
        return check_auth_message

    def _processCheckAuthResponse(self, response, server_url):
        """Process the response message from a check_authentication
        request, invalidating associations if requested.
        """
        is_valid = response.getArg(OPENID_NS, 'is_valid', 'false')

        invalidate_handle = response.getArg(OPENID_NS, 'invalidate_handle')
        if invalidate_handle is not None:
            logging.info(
                'Received "invalidate_handle" from server %s' % (server_url,))
            if self.store is None:
                logging.error('Unexpectedly got invalidate_handle without '
                            'a store!')
            else:
                self.store.removeAssociation(server_url, invalidate_handle)

        if is_valid == 'true':
            return True
        else:
            logging.error('Server responds that checkAuth call is not valid')
            return False

    def _getAssociation(self, endpoint):
        """Get an association for the endpoint's server_url.

        First try seeing if we have a good association in the
        store. If we do not, then attempt to negotiate an association
        with the server.

        If we negotiate a good association, it will get stored.

        @returns: A valid association for the endpoint's server_url or None
        @rtype: openid.association.Association or NoneType
        """
        assoc = self.store.getAssociation(endpoint.server_url)

        if assoc is None or assoc.expiresIn <= 0:
            assoc = self._negotiateAssociation(endpoint)
            if assoc is not None:
                self.store.storeAssociation(endpoint.server_url, assoc)

        return assoc

    def _negotiateAssociation(self, endpoint):
        """Make association requests to the server, attempting to
        create a new association.

        @returns: a new association object

        @rtype: L{openid.association.Association}
        """
        # Get our preferred session/association type from the negotiatior.
        assoc_type, session_type = self.negotiator.getAllowedType()

        try:
            assoc = self._requestAssociation(
                endpoint, assoc_type, session_type)
        except ServerError, why:
            supportedTypes = self._extractSupportedAssociationType(why,
                                                                   endpoint,
                                                                   assoc_type)
            if supportedTypes is not None:
                assoc_type, session_type = supportedTypes
                # Attempt to create an association from the assoc_type
                # and session_type that the server told us it
                # supported.
                try:
                    assoc = self._requestAssociation(
                        endpoint, assoc_type, session_type)
                except ServerError, why:
                    # Do not keep trying, since it rejected the
                    # association type that it told us to use.
                    logging.error('Server %s refused its suggested association '
                                'type: session_type=%s, assoc_type=%s'
                                % (endpoint.server_url, session_type,
                                   assoc_type))
                    return None
                else:
                    return assoc
        else:
            return assoc

    def _extractSupportedAssociationType(self, server_error, endpoint,
                                         assoc_type):
        """Handle ServerErrors resulting from association requests.

        @returns: If server replied with an C{unsupported-type} error,
            return a tuple of supported C{association_type}, C{session_type}.
            Otherwise logs the error and returns None.
        @rtype: tuple or None
        """
        # Any error message whose code is not 'unsupported-type'
        # should be considered a total failure.
        if server_error.error_code != 'unsupported-type' or \
               server_error.message.isOpenID1():
            logging.error(
                'Server error when requesting an association from %r: %s'
                % (endpoint.server_url, server_error.error_text))
            return None

        # The server didn't like the association/session type
        # that we sent, and it sent us back a message that
        # might tell us how to handle it.
        logging.error(
            'Unsupported association type %s: %s' % (assoc_type,
                                                     server_error.error_text,))

        # Extract the session_type and assoc_type from the
        # error message
        assoc_type = server_error.message.getArg(OPENID_NS, 'assoc_type')
        session_type = server_error.message.getArg(OPENID_NS, 'session_type')

        if assoc_type is None or session_type is None:
            logging.error('Server responded with unsupported association '
                        'session but did not supply a fallback.')
            return None
        elif not self.negotiator.isAllowed(assoc_type, session_type):
            fmt = ('Server sent unsupported session/association type: '
                   'session_type=%s, assoc_type=%s')
            logging.error(fmt % (session_type, assoc_type))
            return None
        else:
            return assoc_type, session_type


    def _requestAssociation(self, endpoint, assoc_type, session_type):
        """Make and process one association request to this endpoint's
        OP endpoint URL.

        @returns: An association object or None if the association
            processing failed.

        @raises ServerError: when the remote OpenID server returns an error.
        """
        assoc_session, args = self._createAssociateRequest(
            endpoint, assoc_type, session_type)

        try:
            response = self._makeKVPost(args, endpoint.server_url)
        except fetchers.HTTPFetchingError, why:
            logging.exception('openid.associate request failed: %s' % (why[0],))
            return None

        try:
            assoc = self._extractAssociation(response, assoc_session)
        except KeyError, why:
            logging.exception('Missing required parameter in response from %s: %s'
                        % (endpoint.server_url, why[0]))
            return None
        except ProtocolError, why:
            logging.exception('Protocol error parsing response from %s: %s' % (
                endpoint.server_url, why[0]))
            return None
        else:
            return assoc

    def _createAssociateRequest(self, endpoint, assoc_type, session_type):
        """Create an association request for the given assoc_type and
        session_type.

        @param endpoint: The endpoint whose server_url will be
            queried. The important bit about the endpoint is whether
            it's in compatiblity mode (OpenID 1.1)

        @param assoc_type: The association type that the request
            should ask for.
        @type assoc_type: str

        @param session_type: The session type that should be used in
            the association request. The session_type is used to
            create an association session object, and that session
            object is asked for any additional fields that it needs to
            add to the request.
        @type session_type: str

        @returns: a pair of the association session object and the
            request message that will be sent to the server.
        @rtype: (association session type (depends on session_type),
                 openid.message.Message)
        """
        session_type_class = self.session_types[session_type]
        assoc_session = session_type_class()

        args = {
            'mode': 'associate',
            'assoc_type': assoc_type,
            }

        if not endpoint.compatibilityMode():
            args['ns'] = OPENID2_NS

        # Leave out the session type if we're in compatibility mode
        # *and* it's no-encryption.
        if (not endpoint.compatibilityMode() or
            assoc_session.session_type != 'no-encryption'):
            args['session_type'] = assoc_session.session_type

        args.update(assoc_session.getRequest())
        message = Message.fromOpenIDArgs(args)
        return assoc_session, message

    def _getOpenID1SessionType(self, assoc_response):
        """Given an association response message, extract the OpenID
        1.X session type.

        This function mostly takes care of the 'no-encryption' default
        behavior in OpenID 1.

        If the association type is plain-text, this function will
        return 'no-encryption'

        @returns: The association type for this message
        @rtype: str

        @raises KeyError: when the session_type field is absent.
        """
        # If it's an OpenID 1 message, allow session_type to default
        # to None (which signifies "no-encryption")
        session_type = assoc_response.getArg(OPENID1_NS, 'session_type')

        # Handle the differences between no-encryption association
        # respones in OpenID 1 and 2:

        # no-encryption is not really a valid session type for
        # OpenID 1, but we'll accept it anyway, while issuing a
        # warning.
        if session_type == 'no-encryption':
            logging.warn('OpenID server sent "no-encryption"'
                        'for OpenID 1.X')

        # Missing or empty session type is the way to flag a
        # 'no-encryption' response. Change the session type to
        # 'no-encryption' so that it can be handled in the same
        # way as OpenID 2 'no-encryption' respones.
        elif session_type == '' or session_type is None:
            session_type = 'no-encryption'

        return session_type

    def _extractAssociation(self, assoc_response, assoc_session):
        """Attempt to extract an association from the response, given
        the association response message and the established
        association session.

        @param assoc_response: The association response message from
            the server
        @type assoc_response: openid.message.Message

        @param assoc_session: The association session object that was
            used when making the request
        @type assoc_session: depends on the session type of the request

        @raises ProtocolError: when data is malformed
        @raises KeyError: when a field is missing

        @rtype: openid.association.Association
        """
        # Extract the common fields from the response, raising an
        # exception if they are not found
        assoc_type = assoc_response.getArg(
            OPENID_NS, 'assoc_type', no_default)
        assoc_handle = assoc_response.getArg(
            OPENID_NS, 'assoc_handle', no_default)

        # expires_in is a base-10 string. The Python parsing will
        # accept literals that have whitespace around them and will
        # accept negative values. Neither of these are really in-spec,
        # but we think it's OK to accept them.
        expires_in_str = assoc_response.getArg(
            OPENID_NS, 'expires_in', no_default)
        try:
            expires_in = int(expires_in_str)
        except ValueError, why:
            raise ProtocolError('Invalid expires_in field: %s' % (why[0],))

        # OpenID 1 has funny association session behaviour.
        if assoc_response.isOpenID1():
            session_type = self._getOpenID1SessionType(assoc_response)
        else:
            session_type = assoc_response.getArg(
                OPENID2_NS, 'session_type', no_default)

        # Session type mismatch
        if assoc_session.session_type != session_type:
            if (assoc_response.isOpenID1() and
                session_type == 'no-encryption'):
                # In OpenID 1, any association request can result in a
                # 'no-encryption' association response. Setting
                # assoc_session to a new no-encryption session should
                # make the rest of this function work properly for
                # that case.
                assoc_session = PlainTextConsumerSession()
            else:
                # Any other mismatch, regardless of protocol version
                # results in the failure of the association session
                # altogether.
                fmt = 'Session type mismatch. Expected %r, got %r'
                message = fmt % (assoc_session.session_type, session_type)
                raise ProtocolError(message)

        # Make sure assoc_type is valid for session_type
        if assoc_type not in assoc_session.allowed_assoc_types:
            fmt = 'Unsupported assoc_type for session %s returned: %s'
            raise ProtocolError(fmt % (assoc_session.session_type, assoc_type))

        # Delegate to the association session to extract the secret
        # from the response, however is appropriate for that session
        # type.
        try:
            secret = assoc_session.extractSecret(assoc_response)
        except ValueError, why:
            fmt = 'Malformed response for %s session: %s'
            raise ProtocolError(fmt % (assoc_session.session_type, why[0]))

        return Association.fromExpiresIn(
            expires_in, assoc_handle, secret, assoc_type)

class AuthRequest(object):
    """An object that holds the state necessary for generating an
    OpenID authentication request. This object holds the association
    with the server and the discovered information with which the
    request will be made.

    It is separate from the consumer because you may wish to add
    things to the request before sending it on its way to the
    server. It also has serialization options that let you encode the
    authentication request as a URL or as a form POST.
    """

    def __init__(self, endpoint, assoc):
        """
        Creates a new AuthRequest object.  This just stores each
        argument in an appropriately named field.

        Users of this library should not create instances of this
        class.  Instances of this class are created by the library
        when needed.
        """
        self.assoc = assoc
        self.endpoint = endpoint
        self.return_to_args = {}
        self.message = Message(endpoint.preferredNamespace())
        self._anonymous = False

    def setAnonymous(self, is_anonymous):
        """Set whether this request should be made anonymously. If a
        request is anonymous, the identifier will not be sent in the
        request. This is only useful if you are making another kind of
        request with an extension in this request.

        Anonymous requests are not allowed when the request is made
        with OpenID 1.

        @raises ValueError: when attempting to set an OpenID1 request
            as anonymous
        """
        if is_anonymous and self.message.isOpenID1():
            raise ValueError('OpenID 1 requests MUST include the '
                             'identifier in the request')
        else:
            self._anonymous = is_anonymous

    def addExtension(self, extension_request):
        """Add an extension to this checkid request.

        @param extension_request: An object that implements the
            extension interface for adding arguments to an OpenID
            message.
        """
        extension_request.toMessage(self.message)

    def addExtensionArg(self, namespace, key, value):
        """Add an extension argument to this OpenID authentication
        request.

        Use caution when adding arguments, because they will be
        URL-escaped and appended to the redirect URL, which can easily
        get quite long.

        @param namespace: The namespace for the extension. For
            example, the simple registration extension uses the
            namespace C{sreg}.

        @type namespace: str

        @param key: The key within the extension namespace. For
            example, the nickname field in the simple registration
            extension's key is C{nickname}.

        @type key: str

        @param value: The value to provide to the server for this
            argument.

        @type value: str
        """
        self.message.setArg(namespace, key, value)

    def getMessage(self, realm, return_to=None, immediate=False):
        """Produce a L{openid.message.Message} representing this request.

        @param realm: The URL (or URL pattern) that identifies your
            web site to the user when she is authorizing it.

        @type realm: str

        @param return_to: The URL that the OpenID provider will send the
            user back to after attempting to verify her identity.

            Not specifying a return_to URL means that the user will not
            be returned to the site issuing the request upon its
            completion.

        @type return_to: str

        @param immediate: If True, the OpenID provider is to send back
            a response immediately, useful for behind-the-scenes
            authentication attempts.  Otherwise the OpenID provider
            may engage the user before providing a response.  This is
            the default case, as the user may need to provide
            credentials or approve the request before a positive
            response can be sent.

        @type immediate: bool

        @returntype: L{openid.message.Message}
        """
        if return_to:
            return_to = oidutil.appendArgs(return_to, self.return_to_args)
        elif immediate:
            raise ValueError(
                '"return_to" is mandatory when using "checkid_immediate"')
        elif self.message.isOpenID1():
            raise ValueError('"return_to" is mandatory for OpenID 1 requests')
        elif self.return_to_args:
            raise ValueError('extra "return_to" arguments were specified, '
                             'but no return_to was specified')

        if immediate:
            mode = 'checkid_immediate'
        else:
            mode = 'checkid_setup'

        message = self.message.copy()
        if message.isOpenID1():
            realm_key = 'trust_root'
        else:
            realm_key = 'realm'

        message.updateArgs(OPENID_NS,
            {
            realm_key:realm,
            'mode':mode,
            'return_to':return_to,
            })

        if not self._anonymous:
            if self.endpoint.isOPIdentifier():
                # This will never happen when we're in compatibility
                # mode, as long as isOPIdentifier() returns False
                # whenever preferredNamespace() returns OPENID1_NS.
                claimed_id = request_identity = IDENTIFIER_SELECT
            else:
                request_identity = self.endpoint.getLocalID()
                claimed_id = self.endpoint.claimed_id

            # This is true for both OpenID 1 and 2
            message.setArg(OPENID_NS, 'identity', request_identity)

            if message.isOpenID2():
                message.setArg(OPENID2_NS, 'claimed_id', claimed_id)

        if self.assoc:
            message.setArg(OPENID_NS, 'assoc_handle', self.assoc.handle)
            assoc_log_msg = 'with association %s' % (self.assoc.handle,)
        else:
            assoc_log_msg = 'using stateless mode.'

        logging.info("Generated %s request to %s %s" %
                    (mode, self.endpoint.server_url, assoc_log_msg))

        return message

    def redirectURL(self, realm, return_to=None, immediate=False):
        """Returns a URL with an encoded OpenID request.

        The resulting URL is the OpenID provider's endpoint URL with
        parameters appended as query arguments.  You should redirect
        the user agent to this URL.

        OpenID 2.0 endpoints also accept POST requests, see
        C{L{shouldSendRedirect}} and C{L{formMarkup}}.

        @param realm: The URL (or URL pattern) that identifies your
            web site to the user when she is authorizing it.

        @type realm: str

        @param return_to: The URL that the OpenID provider will send the
            user back to after attempting to verify her identity.

            Not specifying a return_to URL means that the user will not
            be returned to the site issuing the request upon its
            completion.

        @type return_to: str

        @param immediate: If True, the OpenID provider is to send back
            a response immediately, useful for behind-the-scenes
            authentication attempts.  Otherwise the OpenID provider
            may engage the user before providing a response.  This is
            the default case, as the user may need to provide
            credentials or approve the request before a positive
            response can be sent.

        @type immediate: bool

        @returns: The URL to redirect the user agent to.

        @returntype: str
        """
        message = self.getMessage(realm, return_to, immediate)
        return message.toURL(self.endpoint.server_url)

    def formMarkup(self, realm, return_to=None, immediate=False,
            form_tag_attrs=None):
        """Get html for a form to submit this request to the IDP.

        @param form_tag_attrs: Dictionary of attributes to be added to
            the form tag. 'accept-charset' and 'enctype' have defaults
            that can be overridden. If a value is supplied for
            'action' or 'method', it will be replaced.
        @type form_tag_attrs: {unicode: unicode}
        """
        message = self.getMessage(realm, return_to, immediate)
        return message.toFormMarkup(self.endpoint.server_url,
                    form_tag_attrs)

    def htmlMarkup(self, realm, return_to=None, immediate=False,
            form_tag_attrs=None):
        """Get an autosubmitting HTML page that submits this request to the
        IDP.  This is just a wrapper for formMarkup.

        @see: formMarkup

        @returns: str
        """
        return oidutil.autoSubmitHTML(self.formMarkup(realm, 
                                                      return_to,
                                                      immediate, 
                                                      form_tag_attrs))

    def shouldSendRedirect(self):
        """Should this OpenID authentication request be sent as a HTTP
        redirect or as a POST (form submission)?

        @rtype: bool
        """
        return self.endpoint.compatibilityMode()

FAILURE = 'failure'
SUCCESS = 'success'
CANCEL = 'cancel'
SETUP_NEEDED = 'setup_needed'

class Response(object):
    status = None

    def setEndpoint(self, endpoint):
        self.endpoint = endpoint
        if endpoint is None:
            self.identity_url = None
        else:
            self.identity_url = endpoint.claimed_id

    def getDisplayIdentifier(self):
        """Return the display identifier for this response.

        The display identifier is related to the Claimed Identifier, but the
        two are not always identical.  The display identifier is something the
        user should recognize as what they entered, whereas the response's
        claimed identifier (in the L{identity_url} attribute) may have extra
        information for better persistence.

        URLs will be stripped of their fragments for display.  XRIs will
        display the human-readable identifier (i-name) instead of the
        persistent identifier (i-number).

        Use the display identifier in your user interface.  Use
        L{identity_url} for querying your database or authorization server.
        """
        if self.endpoint is not None:
            return self.endpoint.getDisplayIdentifier()
        return None

class SuccessResponse(Response):
    """A response with a status of SUCCESS. Indicates that this request is a
    successful acknowledgement from the OpenID server that the
    supplied URL is, indeed controlled by the requesting agent.

    @ivar identity_url: The identity URL that has been authenticated; the Claimed Identifier.
        See also L{getDisplayIdentifier}.

    @ivar endpoint: The endpoint that authenticated the identifier.  You
        may access other discovered information related to this endpoint,
        such as the CanonicalID of an XRI, through this object.
    @type endpoint: L{OpenIDServiceEndpoint<openid.consumer.discover.OpenIDServiceEndpoint>}

    @ivar signed_fields: The arguments in the server's response that
        were signed and verified.

    @cvar status: SUCCESS
    """

    status = SUCCESS

    def __init__(self, endpoint, message, signed_fields=None):
        # Don't use setEndpoint, because endpoint should never be None
        # for a successfull transaction.
        self.endpoint = endpoint
        self.identity_url = endpoint.claimed_id

        self.message = message

        if signed_fields is None:
            signed_fields = []
        self.signed_fields = signed_fields

    def isOpenID1(self):
        """Was this authentication response an OpenID 1 authentication
        response?
        """
        return self.message.isOpenID1()

    def isSigned(self, ns_uri, ns_key):
        """Return whether a particular key is signed, regardless of
        its namespace alias
        """
        return self.message.getKey(ns_uri, ns_key) in self.signed_fields

    def getSigned(self, ns_uri, ns_key, default=None):
        """Return the specified signed field if available,
        otherwise return default
        """
        if self.isSigned(ns_uri, ns_key):
            return self.message.getArg(ns_uri, ns_key, default)
        else:
            return default

    def getSignedNS(self, ns_uri):
        """Get signed arguments from the response message.  Return a
        dict of all arguments in the specified namespace.  If any of
        the arguments are not signed, return None.
        """
        msg_args = self.message.getArgs(ns_uri)

        for key in msg_args.iterkeys():
            if not self.isSigned(ns_uri, key):
                logging.info("SuccessResponse.getSignedNS: (%s, %s) not signed."
                            % (ns_uri, key))
                return None

        return msg_args

    def extensionResponse(self, namespace_uri, require_signed):
        """Return response arguments in the specified namespace.

        @param namespace_uri: The namespace URI of the arguments to be
        returned.

        @param require_signed: True if the arguments should be among
        those signed in the response, False if you don't care.

        If require_signed is True and the arguments are not signed,
        return None.
        """
        if require_signed:
            return self.getSignedNS(namespace_uri)
        else:
            return self.message.getArgs(namespace_uri)

    def getReturnTo(self):
        """Get the openid.return_to argument from this response.

        This is useful for verifying that this request was initiated
        by this consumer.

        @returns: The return_to URL supplied to the server on the
            initial request, or C{None} if the response did not contain
            an C{openid.return_to} argument.

        @returntype: str
        """
        return self.getSigned(OPENID_NS, 'return_to')

    def __eq__(self, other):
        return (
            (self.endpoint == other.endpoint) and
            (self.identity_url == other.identity_url) and
            (self.message == other.message) and
            (self.signed_fields == other.signed_fields) and
            (self.status == other.status))

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return '<%s.%s id=%r signed=%r>' % (
            self.__class__.__module__,
            self.__class__.__name__,
            self.identity_url, self.signed_fields)


class FailureResponse(Response):
    """A response with a status of FAILURE. Indicates that the OpenID
    protocol has failed. This could be locally or remotely triggered.

    @ivar identity_url:  The identity URL for which authenitcation was
        attempted, if it can be determined. Otherwise, None.

    @ivar message: A message indicating why the request failed, if one
        is supplied. otherwise, None.

    @cvar status: FAILURE
    """

    status = FAILURE

    def __init__(self, endpoint, message=None, contact=None,
                 reference=None):
        self.setEndpoint(endpoint)
        self.message = message
        self.contact = contact
        self.reference = reference

    def __repr__(self):
        return "<%s.%s id=%r message=%r>" % (
            self.__class__.__module__, self.__class__.__name__,
            self.identity_url, self.message)


class CancelResponse(Response):
    """A response with a status of CANCEL. Indicates that the user
    cancelled the OpenID authentication request.

    @ivar identity_url: The identity URL for which authenitcation was
        attempted, if it can be determined. Otherwise, None.

    @cvar status: CANCEL
    """

    status = CANCEL

    def __init__(self, endpoint):
        self.setEndpoint(endpoint)

class SetupNeededResponse(Response):
    """A response with a status of SETUP_NEEDED. Indicates that the
    request was in immediate mode, and the server is unable to
    authenticate the user without further interaction.

    @ivar identity_url:  The identity URL for which authenitcation was
        attempted.

    @ivar setup_url: A URL that can be used to send the user to the
        server to set up for authentication. The user should be
        redirected in to the setup_url, either in the current window
        or in a new browser window.  C{None} in OpenID 2.0.

    @cvar status: SETUP_NEEDED
    """

    status = SETUP_NEEDED

    def __init__(self, endpoint, setup_url=None):
        self.setEndpoint(endpoint)
        self.setup_url = setup_url

########NEW FILE########
__FILENAME__ = discover
# -*- test-case-name: openid.test.test_discover -*-
"""Functions to discover OpenID endpoints from identifiers.
"""

__all__ = [
    'DiscoveryFailure',
    'OPENID_1_0_NS',
    'OPENID_1_0_TYPE',
    'OPENID_1_1_TYPE',
    'OPENID_2_0_TYPE',
    'OPENID_IDP_2_0_TYPE',
    'OpenIDServiceEndpoint',
    'discover',
    ]

import urlparse
import logging

from openid import fetchers, urinorm

from openid import yadis
from openid.yadis.etxrd import nsTag, XRDSError, XRD_NS_2_0
from openid.yadis.services import applyFilter as extractServices
from openid.yadis.discover import discover as yadisDiscover
from openid.yadis.discover import DiscoveryFailure
from openid.yadis import xrires, filters
from openid.yadis import xri

from openid.consumer import html_parse

OPENID_1_0_NS = 'http://openid.net/xmlns/1.0'
OPENID_IDP_2_0_TYPE = 'http://specs.openid.net/auth/2.0/server'
OPENID_2_0_TYPE = 'http://specs.openid.net/auth/2.0/signon'
OPENID_1_1_TYPE = 'http://openid.net/signon/1.1'
OPENID_1_0_TYPE = 'http://openid.net/signon/1.0'

from openid.message import OPENID1_NS as OPENID_1_0_MESSAGE_NS
from openid.message import OPENID2_NS as OPENID_2_0_MESSAGE_NS

class OpenIDServiceEndpoint(object):
    """Object representing an OpenID service endpoint.

    @ivar identity_url: the verified identifier.
    @ivar canonicalID: For XRI, the persistent identifier.
    """

    # OpenID service type URIs, listed in order of preference.  The
    # ordering of this list affects yadis and XRI service discovery.
    openid_type_uris = [
        OPENID_IDP_2_0_TYPE,

        OPENID_2_0_TYPE,
        OPENID_1_1_TYPE,
        OPENID_1_0_TYPE,
        ]

    def __init__(self):
        self.claimed_id = None
        self.server_url = None
        self.type_uris = []
        self.local_id = None
        self.canonicalID = None
        self.used_yadis = False # whether this came from an XRDS
        self.display_identifier = None

    def usesExtension(self, extension_uri):
        return extension_uri in self.type_uris

    def preferredNamespace(self):
        if (OPENID_IDP_2_0_TYPE in self.type_uris or
            OPENID_2_0_TYPE in self.type_uris):
            return OPENID_2_0_MESSAGE_NS
        else:
            return OPENID_1_0_MESSAGE_NS

    def supportsType(self, type_uri):
        """Does this endpoint support this type?

        I consider C{/server} endpoints to implicitly support C{/signon}.
        """
        return (
            (type_uri in self.type_uris) or 
            (type_uri == OPENID_2_0_TYPE and self.isOPIdentifier())
            )

    def getDisplayIdentifier(self):
        """Return the display_identifier if set, else return the claimed_id.
        """
        if self.display_identifier is not None:
            return self.display_identifier
        if self.claimed_id is None:
            return None
        else:
            return urlparse.urldefrag(self.claimed_id)[0]

    def compatibilityMode(self):
        return self.preferredNamespace() != OPENID_2_0_MESSAGE_NS

    def isOPIdentifier(self):
        return OPENID_IDP_2_0_TYPE in self.type_uris

    def parseService(self, yadis_url, uri, type_uris, service_element):
        """Set the state of this object based on the contents of the
        service element."""
        self.type_uris = type_uris
        self.server_url = uri
        self.used_yadis = True

        if not self.isOPIdentifier():
            # XXX: This has crappy implications for Service elements
            # that contain both 'server' and 'signon' Types.  But
            # that's a pathological configuration anyway, so I don't
            # think I care.
            self.local_id = findOPLocalIdentifier(service_element,
                                                  self.type_uris)
            self.claimed_id = yadis_url

    def getLocalID(self):
        """Return the identifier that should be sent as the
        openid.identity parameter to the server."""
        # I looked at this conditional and thought "ah-hah! there's the bug!"
        # but Python actually makes that one big expression somehow, i.e.
        # "x is x is x" is not the same thing as "(x is x) is x".
        # That's pretty weird, dude.  -- kmt, 1/07
        if (self.local_id is self.canonicalID is None):
            return self.claimed_id
        else:
            return self.local_id or self.canonicalID

    def fromBasicServiceEndpoint(cls, endpoint):
        """Create a new instance of this class from the endpoint
        object passed in.

        @return: None or OpenIDServiceEndpoint for this endpoint object"""
        type_uris = endpoint.matchTypes(cls.openid_type_uris)

        # If any Type URIs match and there is an endpoint URI
        # specified, then this is an OpenID endpoint
        if type_uris and endpoint.uri is not None:
            openid_endpoint = cls()
            openid_endpoint.parseService(
                endpoint.yadis_url,
                endpoint.uri,
                endpoint.type_uris,
                endpoint.service_element)
        else:
            openid_endpoint = None

        return openid_endpoint

    fromBasicServiceEndpoint = classmethod(fromBasicServiceEndpoint)

    def fromHTML(cls, uri, html):
        """Parse the given document as HTML looking for an OpenID <link
        rel=...>

        @rtype: [OpenIDServiceEndpoint]
        """
        discovery_types = [
            (OPENID_2_0_TYPE, 'openid2.provider', 'openid2.local_id'),
            (OPENID_1_1_TYPE, 'openid.server', 'openid.delegate'),
            ]

        link_attrs = html_parse.parseLinkAttrs(html)
        services = []
        for type_uri, op_endpoint_rel, local_id_rel in discovery_types:
            op_endpoint_url = html_parse.findFirstHref(
                link_attrs, op_endpoint_rel)
            if op_endpoint_url is None:
                continue

            service = cls()
            service.claimed_id = uri
            service.local_id = html_parse.findFirstHref(
                link_attrs, local_id_rel)
            service.server_url = op_endpoint_url
            service.type_uris = [type_uri]

            services.append(service)

        return services

    fromHTML = classmethod(fromHTML)


    def fromXRDS(cls, uri, xrds):
        """Parse the given document as XRDS looking for OpenID services.

        @rtype: [OpenIDServiceEndpoint]

        @raises XRDSError: When the XRDS does not parse.

        @since: 2.1.0
        """
        return extractServices(uri, xrds, cls)

    fromXRDS = classmethod(fromXRDS)


    def fromDiscoveryResult(cls, discoveryResult):
        """Create endpoints from a DiscoveryResult.

        @type discoveryResult: L{DiscoveryResult}

        @rtype: list of L{OpenIDServiceEndpoint}

        @raises XRDSError: When the XRDS does not parse.

        @since: 2.1.0
        """
        if discoveryResult.isXRDS():
            method = cls.fromXRDS
        else:
            method = cls.fromHTML
        return method(discoveryResult.normalized_uri,
                      discoveryResult.response_text)

    fromDiscoveryResult = classmethod(fromDiscoveryResult)


    def fromOPEndpointURL(cls, op_endpoint_url):
        """Construct an OP-Identifier OpenIDServiceEndpoint object for
        a given OP Endpoint URL

        @param op_endpoint_url: The URL of the endpoint
        @rtype: OpenIDServiceEndpoint
        """
        service = cls()
        service.server_url = op_endpoint_url
        service.type_uris = [OPENID_IDP_2_0_TYPE]
        return service

    fromOPEndpointURL = classmethod(fromOPEndpointURL)


    def __str__(self):
        return ("<%s.%s "
                "server_url=%r "
                "claimed_id=%r "
                "local_id=%r "
                "canonicalID=%r "
                "used_yadis=%s "
                ">"
                 % (self.__class__.__module__, self.__class__.__name__,
                    self.server_url,
                    self.claimed_id,
                    self.local_id,
                    self.canonicalID,
                    self.used_yadis))



def findOPLocalIdentifier(service_element, type_uris):
    """Find the OP-Local Identifier for this xrd:Service element.

    This considers openid:Delegate to be a synonym for xrd:LocalID if
    both OpenID 1.X and OpenID 2.0 types are present. If only OpenID
    1.X is present, it returns the value of openid:Delegate. If only
    OpenID 2.0 is present, it returns the value of xrd:LocalID. If
    there is more than one LocalID tag and the values are different,
    it raises a DiscoveryFailure. This is also triggered when the
    xrd:LocalID and openid:Delegate tags are different.

    @param service_element: The xrd:Service element
    @type service_element: ElementTree.Node

    @param type_uris: The xrd:Type values present in this service
        element. This function could extract them, but higher level
        code needs to do that anyway.
    @type type_uris: [str]

    @raises DiscoveryFailure: when discovery fails.

    @returns: The OP-Local Identifier for this service element, if one
        is present, or None otherwise.
    @rtype: str or unicode or NoneType
    """
    # XXX: Test this function on its own!

    # Build the list of tags that could contain the OP-Local Identifier
    local_id_tags = []
    if (OPENID_1_1_TYPE in type_uris or
        OPENID_1_0_TYPE in type_uris):
        local_id_tags.append(nsTag(OPENID_1_0_NS, 'Delegate'))

    if OPENID_2_0_TYPE in type_uris:
        local_id_tags.append(nsTag(XRD_NS_2_0, 'LocalID'))

    # Walk through all the matching tags and make sure that they all
    # have the same value
    local_id = None
    for local_id_tag in local_id_tags:
        for local_id_element in service_element.findall(local_id_tag):
            if local_id is None:
                local_id = local_id_element.text
            elif local_id != local_id_element.text:
                format = 'More than one %r tag found in one service element'
                message = format % (local_id_tag,)
                raise DiscoveryFailure(message, None)

    return local_id

def normalizeURL(url):
    """Normalize a URL, converting normalization failures to
    DiscoveryFailure"""
    try:
        normalized = urinorm.urinorm(url)
    except ValueError, why:
        raise DiscoveryFailure('Normalizing identifier: %s' % (why[0],), None)
    else:
        return urlparse.urldefrag(normalized)[0]

def normalizeXRI(xri):
    """Normalize an XRI, stripping its scheme if present"""
    if xri.startswith("xri://"):
        xri = xri[6:]
    return xri

def arrangeByType(service_list, preferred_types):
    """Rearrange service_list in a new list so services are ordered by
    types listed in preferred_types.  Return the new list."""

    def enumerate(elts):
        """Return an iterable that pairs the index of an element with
        that element.

        For Python 2.2 compatibility"""
        return zip(range(len(elts)), elts)

    def bestMatchingService(service):
        """Return the index of the first matching type, or something
        higher if no type matches.

        This provides an ordering in which service elements that
        contain a type that comes earlier in the preferred types list
        come before service elements that come later. If a service
        element has more than one type, the most preferred one wins.
        """
        for i, t in enumerate(preferred_types):
            if preferred_types[i] in service.type_uris:
                return i

        return len(preferred_types)

    # Build a list with the service elements in tuples whose
    # comparison will prefer the one with the best matching service
    prio_services = [(bestMatchingService(s), orig_index, s)
                     for (orig_index, s) in enumerate(service_list)]
    prio_services.sort()

    # Now that the services are sorted by priority, remove the sort
    # keys from the list.
    for i in range(len(prio_services)):
        prio_services[i] = prio_services[i][2]

    return prio_services

def getOPOrUserServices(openid_services):
    """Extract OP Identifier services.  If none found, return the
    rest, sorted with most preferred first according to
    OpenIDServiceEndpoint.openid_type_uris.

    openid_services is a list of OpenIDServiceEndpoint objects.

    Returns a list of OpenIDServiceEndpoint objects."""

    op_services = arrangeByType(openid_services, [OPENID_IDP_2_0_TYPE])

    openid_services = arrangeByType(openid_services,
                                    OpenIDServiceEndpoint.openid_type_uris)

    return op_services or openid_services

def discoverYadis(uri):
    """Discover OpenID services for a URI. Tries Yadis and falls back
    on old-style <link rel='...'> discovery if Yadis fails.

    @param uri: normalized identity URL
    @type uri: str

    @return: (claimed_id, services)
    @rtype: (str, list(OpenIDServiceEndpoint))

    @raises DiscoveryFailure: when discovery fails.
    """
    # Might raise a yadis.discover.DiscoveryFailure if no document
    # came back for that URI at all.  I don't think falling back
    # to OpenID 1.0 discovery on the same URL will help, so don't
    # bother to catch it.
    response = yadisDiscover(uri)

    yadis_url = response.normalized_uri
    body = response.response_text
    try:
        openid_services = OpenIDServiceEndpoint.fromXRDS(yadis_url, body)
    except XRDSError:
        # Does not parse as a Yadis XRDS file
        openid_services = []

    if not openid_services:
        # Either not an XRDS or there are no OpenID services.

        if response.isXRDS():
            # if we got the Yadis content-type or followed the Yadis
            # header, re-fetch the document without following the Yadis
            # header, with no Accept header.
            return discoverNoYadis(uri)

        # Try to parse the response as HTML.
        # <link rel="...">
        openid_services = OpenIDServiceEndpoint.fromHTML(yadis_url, body)

    return (yadis_url, getOPOrUserServices(openid_services))

def discoverXRI(iname):
    endpoints = []
    iname = normalizeXRI(iname)
    try:
        canonicalID, services = xrires.ProxyResolver().query(
            iname, OpenIDServiceEndpoint.openid_type_uris)

        if canonicalID is None:
            raise XRDSError('No CanonicalID found for XRI %r' % (iname,))

        flt = filters.mkFilter(OpenIDServiceEndpoint)
        for service_element in services:
            endpoints.extend(flt.getServiceEndpoints(iname, service_element))
    except XRDSError:
        logging.exception('xrds error on ' + iname)

    for endpoint in endpoints:
        # Is there a way to pass this through the filter to the endpoint
        # constructor instead of tacking it on after?
        endpoint.canonicalID = canonicalID
        endpoint.claimed_id = canonicalID
        endpoint.display_identifier = iname

    # FIXME: returned xri should probably be in some normal form
    return iname, getOPOrUserServices(endpoints)


def discoverNoYadis(uri):
    http_resp = fetchers.fetch(uri)
    if http_resp.status not in (200, 206):
        raise DiscoveryFailure(
            'HTTP Response status from identity URL host is not 200. '
            'Got status %r' % (http_resp.status,), http_resp)

    claimed_id = http_resp.final_url
    openid_services = OpenIDServiceEndpoint.fromHTML(
        claimed_id, http_resp.body)
    return claimed_id, openid_services

def discoverURI(uri):
    parsed = urlparse.urlparse(uri)
    if parsed[0] and parsed[1]:
        if parsed[0] not in ['http', 'https']:
            raise DiscoveryFailure('URI scheme is not HTTP or HTTPS', None)
    else:
        uri = 'http://' + uri

    uri = normalizeURL(uri)
    claimed_id, openid_services = discoverYadis(uri)
    claimed_id = normalizeURL(claimed_id)
    return claimed_id, openid_services

def discover(identifier):
    if xri.identifierScheme(identifier) == "XRI":
        return discoverXRI(identifier)
    else:
        return discoverURI(identifier)

########NEW FILE########
__FILENAME__ = html_parse
"""
This module implements a VERY limited parser that finds <link> tags in
the head of HTML or XHTML documents and parses out their attributes
according to the OpenID spec. It is a liberal parser, but it requires
these things from the data in order to work:

 - There must be an open <html> tag

 - There must be an open <head> tag inside of the <html> tag

 - Only <link>s that are found inside of the <head> tag are parsed
   (this is by design)

 - The parser follows the OpenID specification in resolving the
   attributes of the link tags. This means that the attributes DO NOT
   get resolved as they would by an XML or HTML parser. In particular,
   only certain entities get replaced, and href attributes do not get
   resolved relative to a base URL.

From http://openid.net/specs.bml#linkrel:

 - The openid.server URL MUST be an absolute URL. OpenID consumers
   MUST NOT attempt to resolve relative URLs.

 - The openid.server URL MUST NOT include entities other than &amp;,
   &lt;, &gt;, and &quot;.

The parser ignores SGML comments and <![CDATA[blocks]]>. Both kinds of
quoting are allowed for attributes.

The parser deals with invalid markup in these ways:

 - Tag names are not case-sensitive

 - The <html> tag is accepted even when it is not at the top level

 - The <head> tag is accepted even when it is not a direct child of
   the <html> tag, but a <html> tag must be an ancestor of the <head>
   tag

 - <link> tags are accepted even when they are not direct children of
   the <head> tag, but a <head> tag must be an ancestor of the <link>
   tag

 - If there is no closing tag for an open <html> or <head> tag, the
   remainder of the document is viewed as being inside of the tag. If
   there is no closing tag for a <link> tag, the link tag is treated
   as a short tag. Exceptions to this rule are that <html> closes
   <html> and <body> or <head> closes <head>

 - Attributes of the <link> tag are not required to be quoted.

 - In the case of duplicated attribute names, the attribute coming
   last in the tag will be the value returned.

 - Any text that does not parse as an attribute within a link tag will
   be ignored. (e.g. <link pumpkin rel='openid.server' /> will ignore
   pumpkin)

 - If there are more than one <html> or <head> tag, the parser only
   looks inside of the first one.

 - The contents of <script> tags are ignored entirely, except unclosed
   <script> tags. Unclosed <script> tags are ignored.

 - Any other invalid markup is ignored, including unclosed SGML
   comments and unclosed <![CDATA[blocks.
"""

__all__ = ['parseLinkAttrs']

import re

flags = ( re.DOTALL # Match newlines with '.'
        | re.IGNORECASE
        | re.VERBOSE # Allow comments and whitespace in patterns
        | re.UNICODE # Make \b respect Unicode word boundaries
        )

# Stuff to remove before we start looking for tags
removed_re = re.compile(r'''
  # Comments
  <!--.*?-->

  # CDATA blocks
| <!\[CDATA\[.*?\]\]>

  # script blocks
| <script\b

  # make sure script is not an XML namespace
  (?!:)

  [^>]*>.*?</script>

''', flags)

tag_expr = r'''
# Starts with the tag name at a word boundary, where the tag name is
# not a namespace
<%(tag_name)s\b(?!:)

# All of the stuff up to a ">", hopefully attributes.
(?P<attrs>[^>]*?)

(?: # Match a short tag
    />

|   # Match a full tag
    >

    (?P<contents>.*?)

    # Closed by
    (?: # One of the specified close tags
        </?%(closers)s\s*>

        # End of the string
    |   \Z

    )

)
'''

def tagMatcher(tag_name, *close_tags):
    if close_tags:
        options = '|'.join((tag_name,) + close_tags)
        closers = '(?:%s)' % (options,)
    else:
        closers = tag_name

    expr = tag_expr % locals()
    return re.compile(expr, flags)

# Must contain at least an open html and an open head tag
html_find = tagMatcher('html')
head_find = tagMatcher('head', 'body')
link_find = re.compile(r'<link\b(?!:)', flags)

attr_find = re.compile(r'''
# Must start with a sequence of word-characters, followed by an equals sign
(?P<attr_name>\w+)=

# Then either a quoted or unquoted attribute
(?:

 # Match everything that\'s between matching quote marks
 (?P<qopen>["\'])(?P<q_val>.*?)(?P=qopen)
|

 # If the value is not quoted, match up to whitespace
 (?P<unq_val>(?:[^\s<>/]|/(?!>))+)
)

|

(?P<end_link>[<>])
''', flags)

# Entity replacement:
replacements = {
    'amp':'&',
    'lt':'<',
    'gt':'>',
    'quot':'"',
    }

ent_replace = re.compile(r'&(%s);' % '|'.join(replacements.keys()))
def replaceEnt(mo):
    "Replace the entities that are specified by OpenID"
    return replacements.get(mo.group(1), mo.group())

def parseLinkAttrs(html):
    """Find all link tags in a string representing a HTML document and
    return a list of their attributes.

    @param html: the text to parse
    @type html: str or unicode

    @return: A list of dictionaries of attributes, one for each link tag
    @rtype: [[(type(html), type(html))]]
    """
    stripped = removed_re.sub('', html)
    html_mo = html_find.search(stripped)
    if html_mo is None or html_mo.start('contents') == -1:
        return []

    start, end = html_mo.span('contents')
    head_mo = head_find.search(stripped, start, end)
    if head_mo is None or head_mo.start('contents') == -1:
        return []

    start, end = head_mo.span('contents')
    link_mos = link_find.finditer(stripped, head_mo.start(), head_mo.end())

    matches = []
    for link_mo in link_mos:
        start = link_mo.start() + 5
        link_attrs = {}
        for attr_mo in attr_find.finditer(stripped, start):
            if attr_mo.lastgroup == 'end_link':
                break

            # Either q_val or unq_val must be present, but not both
            # unq_val is a True (non-empty) value if it is present
            attr_name, q_val, unq_val = attr_mo.group(
                'attr_name', 'q_val', 'unq_val')
            attr_val = ent_replace.sub(replaceEnt, unq_val or q_val)

            link_attrs[attr_name] = attr_val

        matches.append(link_attrs)

    return matches

def relMatches(rel_attr, target_rel):
    """Does this target_rel appear in the rel_str?"""
    # XXX: TESTME
    rels = rel_attr.strip().split()
    for rel in rels:
        rel = rel.lower()
        if rel == target_rel:
            return 1

    return 0

def linkHasRel(link_attrs, target_rel):
    """Does this link have target_rel as a relationship?"""
    # XXX: TESTME
    rel_attr = link_attrs.get('rel')
    return rel_attr and relMatches(rel_attr, target_rel)

def findLinksRel(link_attrs_list, target_rel):
    """Filter the list of link attributes on whether it has target_rel
    as a relationship."""
    # XXX: TESTME
    matchesTarget = lambda attrs: linkHasRel(attrs, target_rel)
    return filter(matchesTarget, link_attrs_list)

def findFirstHref(link_attrs_list, target_rel):
    """Return the value of the href attribute for the first link tag
    in the list that has target_rel as a relationship."""
    # XXX: TESTME
    matches = findLinksRel(link_attrs_list, target_rel)
    if not matches:
        return None
    first = matches[0]
    return first.get('href')

########NEW FILE########
__FILENAME__ = cryptutil
"""Module containing a cryptographic-quality source of randomness and
other cryptographically useful functionality

Python 2.4 needs no external support for this module, nor does Python
2.3 on a system with /dev/urandom.

Other configurations will need a quality source of random bytes and
access to a function that will convert binary strings to long
integers. This module will work with the Python Cryptography Toolkit
(pycrypto) if it is present. pycrypto can be found with a search
engine, but is currently found at:

http://www.amk.ca/python/code/crypto
"""

__all__ = [
    'base64ToLong',
    'binaryToLong',
    'hmacSha1',
    'hmacSha256',
    'longToBase64',
    'longToBinary',
    'randomString',
    'randrange',
    'sha1',
    'sha256',
    ]

import hmac
import os
import random

from openid.oidutil import toBase64, fromBase64

try:
    import hashlib
except ImportError:
    import sha as sha1_module

    try:
        from Crypto.Hash import SHA256 as sha256_module
    except ImportError:
        sha256_module = None

else:
    class HashContainer(object):
        def __init__(self, hash_constructor):
            self.new = hash_constructor
            self.digest_size = hash_constructor().digest_size

    sha1_module = HashContainer(hashlib.sha1)
    sha256_module = HashContainer(hashlib.sha256)

def hmacSha1(key, text):
    return hmac.new(key, text, sha1_module).digest()

def sha1(s):
    return sha1_module.new(s).digest()

if sha256_module is not None:
    def hmacSha256(key, text):
        return hmac.new(key, text, sha256_module).digest()

    def sha256(s):
        return sha256_module.new(s).digest()

    SHA256_AVAILABLE = True

else:
    _no_sha256 = NotImplementedError(
        'Use Python 2.5, install pycrypto or install hashlib to use SHA256')

    def hmacSha256(unused_key, unused_text):
        raise _no_sha256

    def sha256(s):
        raise _no_sha256

    SHA256_AVAILABLE = False

try:
    from Crypto.Util.number import long_to_bytes, bytes_to_long
except ImportError:
    import pickle
    try:
        # Check Python compatiblity by raising an exception on import
        # if the needed functionality is not present. Present in
        # Python >= 2.3
        pickle.encode_long
        pickle.decode_long
    except AttributeError:
        raise ImportError(
            'No functionality for serializing long integers found')

    # Present in Python >= 2.4
    try:
        reversed
    except NameError:
        def reversed(seq):
            return map(seq.__getitem__, xrange(len(seq) - 1, -1, -1))

    def longToBinary(l):
        if l == 0:
            return '\x00'

        return ''.join(reversed(pickle.encode_long(l)))

    def binaryToLong(s):
        return pickle.decode_long(''.join(reversed(s)))
else:
    # We have pycrypto

    def longToBinary(l):
        if l < 0:
            raise ValueError('This function only supports positive integers')

        bytes = long_to_bytes(l)
        if ord(bytes[0]) > 127:
            return '\x00' + bytes
        else:
            return bytes

    def binaryToLong(bytes):
        if not bytes:
            raise ValueError('Empty string passed to strToLong')

        if ord(bytes[0]) > 127:
            raise ValueError('This function only supports positive integers')

        return bytes_to_long(bytes)

# A cryptographically safe source of random bytes
try:
    getBytes = os.urandom
except AttributeError:
    try:
        from Crypto.Util.randpool import RandomPool
    except ImportError:
        # Fall back on /dev/urandom, if present. It would be nice to
        # have Windows equivalent here, but for now, require pycrypto
        # on Windows.
        try:
            _urandom = file('/dev/urandom', 'rb')
        except IOError:
            raise ImportError('No adequate source of randomness found!')
        else:
            def getBytes(n):
                bytes = []
                while n:
                    chunk = _urandom.read(n)
                    n -= len(chunk)
                    bytes.append(chunk)
                    assert n >= 0
                return ''.join(bytes)
    else:
        _pool = RandomPool()
        def getBytes(n, pool=_pool):
            if pool.entropy < n:
                pool.randomize()
            return pool.get_bytes(n)

# A randrange function that works for longs
try:
    randrange = random.SystemRandom().randrange
except AttributeError:
    # In Python 2.2's random.Random, randrange does not support
    # numbers larger than sys.maxint for randrange. For simplicity,
    # use this implementation for any Python that does not have
    # random.SystemRandom
    from math import log, ceil

    _duplicate_cache = {}
    def randrange(start, stop=None, step=1):
        if stop is None:
            stop = start
            start = 0

        r = (stop - start) // step
        try:
            (duplicate, nbytes) = _duplicate_cache[r]
        except KeyError:
            rbytes = longToBinary(r)
            if rbytes[0] == '\x00':
                nbytes = len(rbytes) - 1
            else:
                nbytes = len(rbytes)

            mxrand = (256 ** nbytes)

            # If we get a number less than this, then it is in the
            # duplicated range.
            duplicate = mxrand % r

            if len(_duplicate_cache) > 10:
                _duplicate_cache.clear()

            _duplicate_cache[r] = (duplicate, nbytes)

        while 1:
            bytes = '\x00' + getBytes(nbytes)
            n = binaryToLong(bytes)
            # Keep looping if this value is in the low duplicated range
            if n >= duplicate:
                break

        return start + (n % r) * step

def longToBase64(l):
    return toBase64(longToBinary(l))

def base64ToLong(s):
    return binaryToLong(fromBase64(s))

def randomString(length, chrs=None):
    """Produce a string of length random bytes, chosen from chrs."""
    if chrs is None:
        return getBytes(length)
    else:
        n = len(chrs)
        return ''.join([chrs[randrange(n)] for _ in xrange(length)])

def const_eq(s1, s2):
    if len(s1) != len(s2):
        return False

    result = True
    for i in range(len(s1)):
        result = result and (s1[i] == s2[i])

    return result

########NEW FILE########
__FILENAME__ = dh
from openid import cryptutil
from openid import oidutil

def strxor(x, y):
    if len(x) != len(y):
        raise ValueError('Inputs to strxor must have the same length')

    xor = lambda (a, b): chr(ord(a) ^ ord(b))
    return "".join(map(xor, zip(x, y)))

class DiffieHellman(object):
    DEFAULT_MOD = 155172898181473697471232257763715539915724801966915404479707795314057629378541917580651227423698188993727816152646631438561595825688188889951272158842675419950341258706556549803580104870537681476726513255747040765857479291291572334510643245094715007229621094194349783925984760375594985848253359305585439638443L

    DEFAULT_GEN = 2

    def fromDefaults(cls):
        return cls(cls.DEFAULT_MOD, cls.DEFAULT_GEN)

    fromDefaults = classmethod(fromDefaults)

    def __init__(self, modulus, generator):
        self.modulus = long(modulus)
        self.generator = long(generator)

        self._setPrivate(cryptutil.randrange(1, modulus - 1))

    def _setPrivate(self, private):
        """This is here to make testing easier"""
        self.private = private
        self.public = pow(self.generator, self.private, self.modulus)

    def usingDefaultValues(self):
        return (self.modulus == self.DEFAULT_MOD and
                self.generator == self.DEFAULT_GEN)

    def getSharedSecret(self, composite):
        return pow(composite, self.private, self.modulus)

    def xorSecret(self, composite, secret, hash_func):
        dh_shared = self.getSharedSecret(composite)
        hashed_dh_shared = hash_func(cryptutil.longToBinary(dh_shared))
        return strxor(secret, hashed_dh_shared)

########NEW FILE########
__FILENAME__ = extension
from openid import message as message_module

class Extension(object):
    """An interface for OpenID extensions.

    @ivar ns_uri: The namespace to which to add the arguments for this
        extension
    """
    ns_uri = None
    ns_alias = None

    def getExtensionArgs(self):
        """Get the string arguments that should be added to an OpenID
        message for this extension.

        @returns: A dictionary of completely non-namespaced arguments
            to be added. For example, if the extension's alias is
            'uncle', and this method returns {'meat':'Hot Rats'}, the
            final message will contain {'openid.uncle.meat':'Hot Rats'}
        """
        raise NotImplementedError

    def toMessage(self, message=None):
        """Add the arguments from this extension to the provided
        message, or create a new message containing only those
        arguments.

        @returns: The message with the extension arguments added
        """
        if message is None:
            warnings.warn('Passing None to Extension.toMessage is deprecated. '
                          'Creating a message assuming you want OpenID 2.',
                          DeprecationWarning, stacklevel=2)
            message = message_module.Message(message_module.OPENID2_NS)

        implicit = message.isOpenID1()

        try:
            message.namespaces.addAlias(self.ns_uri, self.ns_alias,
                                        implicit=implicit)
        except KeyError:
            if message.namespaces.getAlias(self.ns_uri) != self.ns_alias:
                raise

        message.updateArgs(self.ns_uri, self.getExtensionArgs())
        return message

########NEW FILE########
__FILENAME__ = ax
# -*- test-case-name: openid.test.test_ax -*-
"""Implements the OpenID Attribute Exchange specification, version 1.0.

@since: 2.1.0
"""

__all__ = [
    'AttributeRequest',
    'FetchRequest',
    'FetchResponse',
    'StoreRequest',
    'StoreResponse',
    ]

from openid import extension
from openid.server.trustroot import TrustRoot
from openid.message import NamespaceMap, OPENID_NS

# Use this as the 'count' value for an attribute in a FetchRequest to
# ask for as many values as the OP can provide.
UNLIMITED_VALUES = "unlimited"

# Minimum supported alias length in characters.  Here for
# completeness.
MINIMUM_SUPPORTED_ALIAS_LENGTH = 32

def checkAlias(alias):
    """
    Check an alias for invalid characters; raise AXError if any are
    found.  Return None if the alias is valid.
    """
    if ',' in alias:
        raise AXError("Alias %r must not contain comma" % (alias,))
    if '.' in alias:
        raise AXError("Alias %r must not contain period" % (alias,))


class AXError(ValueError):
    """Results from data that does not meet the attribute exchange 1.0
    specification"""


class NotAXMessage(AXError):
    """Raised when there is no Attribute Exchange mode in the message."""

    def __repr__(self):
        return self.__class__.__name__

    def __str__(self):
        return self.__class__.__name__


class AXMessage(extension.Extension):
    """Abstract class containing common code for attribute exchange messages

    @cvar ns_alias: The preferred namespace alias for attribute
        exchange messages

    @cvar mode: The type of this attribute exchange message. This must
        be overridden in subclasses.
    """

    # This class is abstract, so it's OK that it doesn't override the
    # abstract method in Extension:
    #
    #pylint:disable-msg=W0223

    ns_alias = 'ax'
    mode = None
    ns_uri = 'http://openid.net/srv/ax/1.0'

    def _checkMode(self, ax_args):
        """Raise an exception if the mode in the attribute exchange
        arguments does not match what is expected for this class.

        @raises NotAXMessage: When there is no mode value in ax_args at all.

        @raises AXError: When mode does not match.
        """
        mode = ax_args.get('mode')
        if mode != self.mode:
            if not mode:
                raise NotAXMessage()
            else:
                raise AXError(
                    'Expected mode %r; got %r' % (self.mode, mode))

    def _newArgs(self):
        """Return a set of attribute exchange arguments containing the
        basic information that must be in every attribute exchange
        message.
        """
        return {'mode':self.mode}


class AttrInfo(object):
    """Represents a single attribute in an attribute exchange
    request. This should be added to an AXRequest object in order to
    request the attribute.

    @ivar required: Whether the attribute will be marked as required
        when presented to the subject of the attribute exchange
        request.
    @type required: bool

    @ivar count: How many values of this type to request from the
        subject. Defaults to one.
    @type count: int

    @ivar type_uri: The identifier that determines what the attribute
        represents and how it is serialized. For example, one type URI
        representing dates could represent a Unix timestamp in base 10
        and another could represent a human-readable string.
    @type type_uri: str

    @ivar alias: The name that should be given to this alias in the
        request. If it is not supplied, a generic name will be
        assigned. For example, if you want to call a Unix timestamp
        value 'tstamp', set its alias to that value. If two attributes
        in the same message request to use the same alias, the request
        will fail to be generated.
    @type alias: str or NoneType
    """

    # It's OK that this class doesn't have public methods (it's just a
    # holder for a bunch of attributes):
    #
    #pylint:disable-msg=R0903

    def __init__(self, type_uri, count=1, required=False, alias=None):
        self.required = required
        self.count = count
        self.type_uri = type_uri
        self.alias = alias

        if self.alias is not None:
            checkAlias(self.alias)

    def wantsUnlimitedValues(self):
        """
        When processing a request for this attribute, the OP should
        call this method to determine whether all available attribute
        values were requested.  If self.count == UNLIMITED_VALUES,
        this returns True.  Otherwise this returns False, in which
        case self.count is an integer.
        """
        return self.count == UNLIMITED_VALUES

def toTypeURIs(namespace_map, alias_list_s):
    """Given a namespace mapping and a string containing a
    comma-separated list of namespace aliases, return a list of type
    URIs that correspond to those aliases.

    @param namespace_map: The mapping from namespace URI to alias
    @type namespace_map: openid.message.NamespaceMap

    @param alias_list_s: The string containing the comma-separated
        list of aliases. May also be None for convenience.
    @type alias_list_s: str or NoneType

    @returns: The list of namespace URIs that corresponds to the
        supplied list of aliases. If the string was zero-length or
        None, an empty list will be returned.

    @raise KeyError: If an alias is present in the list of aliases but
        is not present in the namespace map.
    """
    uris = []

    if alias_list_s:
        for alias in alias_list_s.split(','):
            type_uri = namespace_map.getNamespaceURI(alias)
            if type_uri is None:
                raise KeyError(
                    'No type is defined for attribute name %r' % (alias,))
            else:
                uris.append(type_uri)

    return uris


class FetchRequest(AXMessage):
    """An attribute exchange 'fetch_request' message. This message is
    sent by a relying party when it wishes to obtain attributes about
    the subject of an OpenID authentication request.

    @ivar requested_attributes: The attributes that have been
        requested thus far, indexed by the type URI.
    @type requested_attributes: {str:AttrInfo}

    @ivar update_url: A URL that will accept responses for this
        attribute exchange request, even in the absence of the user
        who made this request.
    """
    mode = 'fetch_request'

    def __init__(self, update_url=None):
        AXMessage.__init__(self)
        self.requested_attributes = {}
        self.update_url = update_url

    def add(self, attribute):
        """Add an attribute to this attribute exchange request.

        @param attribute: The attribute that is being requested
        @type attribute: C{L{AttrInfo}}

        @returns: None

        @raise KeyError: when the requested attribute is already
            present in this fetch request.
        """
        if attribute.type_uri in self.requested_attributes:
            raise KeyError('The attribute %r has already been requested'
                           % (attribute.type_uri,))

        self.requested_attributes[attribute.type_uri] = attribute

    def getExtensionArgs(self):
        """Get the serialized form of this attribute fetch request.

        @returns: The fetch request message parameters
        @rtype: {unicode:unicode}
        """
        aliases = NamespaceMap()

        required = []
        if_available = []

        ax_args = self._newArgs()

        for type_uri, attribute in self.requested_attributes.iteritems():
            if attribute.alias is None:
                alias = aliases.add(type_uri)
            else:
                # This will raise an exception when the second
                # attribute with the same alias is added. I think it
                # would be better to complain at the time that the
                # attribute is added to this object so that the code
                # that is adding it is identified in the stack trace,
                # but it's more work to do so, and it won't be 100%
                # accurate anyway, since the attributes are
                # mutable. So for now, just live with the fact that
                # we'll learn about the error later.
                #
                # The other possible approach is to hide the error and
                # generate a new alias on the fly. I think that would
                # probably be bad.
                alias = aliases.addAlias(type_uri, attribute.alias)

            if attribute.required:
                required.append(alias)
            else:
                if_available.append(alias)

            if attribute.count != 1:
                ax_args['count.' + alias] = str(attribute.count)

            ax_args['type.' + alias] = type_uri

        if required:
            ax_args['required'] = ','.join(required)

        if if_available:
            ax_args['if_available'] = ','.join(if_available)

        return ax_args

    def getRequiredAttrs(self):
        """Get the type URIs for all attributes that have been marked
        as required.

        @returns: A list of the type URIs for attributes that have
            been marked as required.
        @rtype: [str]
        """
        required = []
        for type_uri, attribute in self.requested_attributes.iteritems():
            if attribute.required:
                required.append(type_uri)

        return required

    def fromOpenIDRequest(cls, openid_request):
        """Extract a FetchRequest from an OpenID message

        @param openid_request: The OpenID authentication request
            containing the attribute fetch request
        @type openid_request: C{L{openid.server.server.CheckIDRequest}}

        @rtype: C{L{FetchRequest}} or C{None}
        @returns: The FetchRequest extracted from the message or None, if
            the message contained no AX extension.

        @raises KeyError: if the AuthRequest is not consistent in its use
            of namespace aliases.

        @raises AXError: When parseExtensionArgs would raise same.

        @see: L{parseExtensionArgs}
        """
        message = openid_request.message
        ax_args = message.getArgs(cls.ns_uri)
        self = cls()
        try:
            self.parseExtensionArgs(ax_args)
        except NotAXMessage, err:
            return None

        if self.update_url:
            # Update URL must match the openid.realm of the underlying
            # OpenID 2 message.
            realm = message.getArg(OPENID_NS, 'realm',
                                   message.getArg(OPENID_NS, 'return_to'))

            if not realm:
                raise AXError(("Cannot validate update_url %r " +
                               "against absent realm") % (self.update_url,))

            tr = TrustRoot.parse(realm)
            if not tr.validateURL(self.update_url):
                raise AXError("Update URL %r failed validation against realm %r" %
                              (self.update_url, realm,))

        return self

    fromOpenIDRequest = classmethod(fromOpenIDRequest)

    def parseExtensionArgs(self, ax_args):
        """Given attribute exchange arguments, populate this FetchRequest.

        @param ax_args: Attribute Exchange arguments from the request.
            As returned from L{Message.getArgs<openid.message.Message.getArgs>}.
        @type ax_args: dict

        @raises KeyError: if the message is not consistent in its use
            of namespace aliases.

        @raises NotAXMessage: If ax_args does not include an Attribute Exchange
            mode.

        @raises AXError: If the data to be parsed does not follow the
            attribute exchange specification. At least when
            'if_available' or 'required' is not specified for a
            particular attribute type.
        """
        # Raises an exception if the mode is not the expected value
        self._checkMode(ax_args)

        aliases = NamespaceMap()

        for key, value in ax_args.iteritems():
            if key.startswith('type.'):
                alias = key[5:]
                type_uri = value
                aliases.addAlias(type_uri, alias)

                count_key = 'count.' + alias
                count_s = ax_args.get(count_key)
                if count_s:
                    try:
                        count = int(count_s)
                        if count <= 0:
                            raise AXError("Count %r must be greater than zero, got %r" % (count_key, count_s,))
                    except ValueError:
                        if count_s != UNLIMITED_VALUES:
                            raise AXError("Invalid count value for %r: %r" % (count_key, count_s,))
                        count = count_s
                else:
                    count = 1

                self.add(AttrInfo(type_uri, alias=alias, count=count))

        required = toTypeURIs(aliases, ax_args.get('required'))

        for type_uri in required:
            self.requested_attributes[type_uri].required = True

        if_available = toTypeURIs(aliases, ax_args.get('if_available'))

        all_type_uris = required + if_available

        for type_uri in aliases.iterNamespaceURIs():
            if type_uri not in all_type_uris:
                raise AXError(
                    'Type URI %r was in the request but not '
                    'present in "required" or "if_available"' % (type_uri,))

        self.update_url = ax_args.get('update_url')

    def iterAttrs(self):
        """Iterate over the AttrInfo objects that are
        contained in this fetch_request.
        """
        return self.requested_attributes.itervalues()

    def __iter__(self):
        """Iterate over the attribute type URIs in this fetch_request
        """
        return iter(self.requested_attributes)

    def has_key(self, type_uri):
        """Is the given type URI present in this fetch_request?
        """
        return type_uri in self.requested_attributes

    __contains__ = has_key


class AXKeyValueMessage(AXMessage):
    """An abstract class that implements a message that has attribute
    keys and values. It contains the common code between
    fetch_response and store_request.
    """

    # This class is abstract, so it's OK that it doesn't override the
    # abstract method in Extension:
    #
    #pylint:disable-msg=W0223

    def __init__(self):
        AXMessage.__init__(self)
        self.data = {}

    def addValue(self, type_uri, value):
        """Add a single value for the given attribute type to the
        message. If there are already values specified for this type,
        this value will be sent in addition to the values already
        specified.

        @param type_uri: The URI for the attribute

        @param value: The value to add to the response to the relying
            party for this attribute
        @type value: unicode

        @returns: None
        """
        try:
            values = self.data[type_uri]
        except KeyError:
            values = self.data[type_uri] = []

        values.append(value)

    def setValues(self, type_uri, values):
        """Set the values for the given attribute type. This replaces
        any values that have already been set for this attribute.

        @param type_uri: The URI for the attribute

        @param values: A list of values to send for this attribute.
        @type values: [unicode]
        """

        self.data[type_uri] = values

    def _getExtensionKVArgs(self, aliases=None):
        """Get the extension arguments for the key/value pairs
        contained in this message.

        @param aliases: An alias mapping. Set to None if you don't
            care about the aliases for this request.
        """
        if aliases is None:
            aliases = NamespaceMap()

        ax_args = {}

        for type_uri, values in self.data.iteritems():
            alias = aliases.add(type_uri)

            ax_args['type.' + alias] = type_uri
            ax_args['count.' + alias] = str(len(values))

            for i, value in enumerate(values):
                key = 'value.%s.%d' % (alias, i + 1)
                ax_args[key] = value

        return ax_args

    def parseExtensionArgs(self, ax_args):
        """Parse attribute exchange key/value arguments into this
        object.

        @param ax_args: The attribute exchange fetch_response
            arguments, with namespacing removed.
        @type ax_args: {unicode:unicode}

        @returns: None

        @raises ValueError: If the message has bad values for
            particular fields

        @raises KeyError: If the namespace mapping is bad or required
            arguments are missing
        """
        self._checkMode(ax_args)

        aliases = NamespaceMap()

        for key, value in ax_args.iteritems():
            if key.startswith('type.'):
                type_uri = value
                alias = key[5:]
                checkAlias(alias)
                aliases.addAlias(type_uri, alias)

        for type_uri, alias in aliases.iteritems():
            try:
                count_s = ax_args['count.' + alias]
            except KeyError:
                value = ax_args['value.' + alias]

                if value == u'':
                    values = []
                else:
                    values = [value]
            else:
                count = int(count_s)
                values = []
                for i in range(1, count + 1):
                    value_key = 'value.%s.%d' % (alias, i)
                    value = ax_args[value_key]
                    values.append(value)

            self.data[type_uri] = values

    def getSingle(self, type_uri, default=None):
        """Get a single value for an attribute. If no value was sent
        for this attribute, use the supplied default. If there is more
        than one value for this attribute, this method will fail.

        @type type_uri: str
        @param type_uri: The URI for the attribute

        @param default: The value to return if the attribute was not
            sent in the fetch_response.

        @returns: The value of the attribute in the fetch_response
            message, or the default supplied
        @rtype: unicode or NoneType

        @raises ValueError: If there is more than one value for this
            parameter in the fetch_response message.
        @raises KeyError: If the attribute was not sent in this response
        """
        values = self.data.get(type_uri)
        if not values:
            return default
        elif len(values) == 1:
            return values[0]
        else:
            raise AXError(
                'More than one value present for %r' % (type_uri,))

    def get(self, type_uri):
        """Get the list of values for this attribute in the
        fetch_response.

        XXX: what to do if the values are not present? default
        parameter? this is funny because it's always supposed to
        return a list, so the default may break that, though it's
        provided by the user's code, so it might be okay. If no
        default is supplied, should the return be None or []?

        @param type_uri: The URI of the attribute

        @returns: The list of values for this attribute in the
            response. May be an empty list.
        @rtype: [unicode]

        @raises KeyError: If the attribute was not sent in the response
        """
        return self.data[type_uri]

    def count(self, type_uri):
        """Get the number of responses for a particular attribute in
        this fetch_response message.

        @param type_uri: The URI of the attribute

        @returns: The number of values sent for this attribute

        @raises KeyError: If the attribute was not sent in the
            response. KeyError will not be raised if the number of
            values was zero.
        """
        return len(self.get(type_uri))


class FetchResponse(AXKeyValueMessage):
    """A fetch_response attribute exchange message
    """
    mode = 'fetch_response'

    def __init__(self, request=None, update_url=None):
        """
        @param request: When supplied, I will use namespace aliases
            that match those in this request.  I will also check to
            make sure I do not respond with attributes that were not
            requested.

        @type request: L{FetchRequest}

        @param update_url: By default, C{update_url} is taken from the
            request.  But if you do not supply the request, you may set
            the C{update_url} here.

        @type update_url: str
        """
        AXKeyValueMessage.__init__(self)
        self.update_url = update_url
        self.request = request

    def getExtensionArgs(self):
        """Serialize this object into arguments in the attribute
        exchange namespace

        @returns: The dictionary of unqualified attribute exchange
            arguments that represent this fetch_response.
        @rtype: {unicode;unicode}
        """

        aliases = NamespaceMap()

        zero_value_types = []

        if self.request is not None:
            # Validate the data in the context of the request (the
            # same attributes should be present in each, and the
            # counts in the response must be no more than the counts
            # in the request)

            for type_uri in self.data:
                if type_uri not in self.request:
                    raise KeyError(
                        'Response attribute not present in request: %r'
                        % (type_uri,))

            for attr_info in self.request.iterAttrs():
                # Copy the aliases from the request so that reading
                # the response in light of the request is easier
                if attr_info.alias is None:
                    aliases.add(attr_info.type_uri)
                else:
                    aliases.addAlias(attr_info.type_uri, attr_info.alias)

                try:
                    values = self.data[attr_info.type_uri]
                except KeyError:
                    values = []
                    zero_value_types.append(attr_info)

                if (attr_info.count != UNLIMITED_VALUES) and \
                       (attr_info.count < len(values)):
                    raise AXError(
                        'More than the number of requested values were '
                        'specified for %r' % (attr_info.type_uri,))

        kv_args = self._getExtensionKVArgs(aliases)

        # Add the KV args into the response with the args that are
        # unique to the fetch_response
        ax_args = self._newArgs()

        # For each requested attribute, put its type/alias and count
        # into the response even if no data were returned.
        for attr_info in zero_value_types:
            alias = aliases.getAlias(attr_info.type_uri)
            kv_args['type.' + alias] = attr_info.type_uri
            kv_args['count.' + alias] = '0'

        update_url = ((self.request and self.request.update_url)
                      or self.update_url)

        if update_url:
            ax_args['update_url'] = update_url

        ax_args.update(kv_args)

        return ax_args

    def parseExtensionArgs(self, ax_args):
        """@see: {Extension.parseExtensionArgs<openid.extension.Extension.parseExtensionArgs>}"""
        super(FetchResponse, self).parseExtensionArgs(ax_args)
        self.update_url = ax_args.get('update_url')

    def fromSuccessResponse(cls, success_response, signed=True):
        """Construct a FetchResponse object from an OpenID library
        SuccessResponse object.

        @param success_response: A successful id_res response object
        @type success_response: openid.consumer.consumer.SuccessResponse

        @param signed: Whether non-signed args should be
            processsed. If True (the default), only signed arguments
            will be processsed.
        @type signed: bool

        @returns: A FetchResponse containing the data from the OpenID
            message, or None if the SuccessResponse did not contain AX
            extension data.

        @raises AXError: when the AX data cannot be parsed.
        """
        self = cls()
        ax_args = success_response.extensionResponse(self.ns_uri, signed)

        try:
            self.parseExtensionArgs(ax_args)
        except NotAXMessage, err:
            return None
        else:
            return self

    fromSuccessResponse = classmethod(fromSuccessResponse)


class StoreRequest(AXKeyValueMessage):
    """A store request attribute exchange message representation
    """
    mode = 'store_request'

    def __init__(self, aliases=None):
        """
        @param aliases: The namespace aliases to use when making this
            store request.  Leave as None to use defaults.
        """
        super(StoreRequest, self).__init__()
        self.aliases = aliases

    def getExtensionArgs(self):
        """
        @see: L{Extension.getExtensionArgs<openid.extension.Extension.getExtensionArgs>}
        """
        ax_args = self._newArgs()
        kv_args = self._getExtensionKVArgs(self.aliases)
        ax_args.update(kv_args)
        return ax_args


class StoreResponse(AXMessage):
    """An indication that the store request was processed along with
    this OpenID transaction.
    """

    SUCCESS_MODE = 'store_response_success'
    FAILURE_MODE = 'store_response_failure'

    def __init__(self, succeeded=True, error_message=None):
        AXMessage.__init__(self)

        if succeeded and error_message is not None:
            raise AXError('An error message may only be included in a '
                             'failing fetch response')
        if succeeded:
            self.mode = self.SUCCESS_MODE
        else:
            self.mode = self.FAILURE_MODE

        self.error_message = error_message

    def succeeded(self):
        """Was this response a success response?"""
        return self.mode == self.SUCCESS_MODE

    def getExtensionArgs(self):
        """@see: {Extension.getExtensionArgs<openid.extension.Extension.getExtensionArgs>}"""
        ax_args = self._newArgs()
        if not self.succeeded() and self.error_message:
            ax_args['error'] = self.error_message

        return ax_args

########NEW FILE########
__FILENAME__ = pape2
"""An implementation of the OpenID Provider Authentication Policy
Extension 1.0

@see: http://openid.net/developers/specs/

@since: 2.1.0
"""

__all__ = [
    'Request',
    'Response',
    'ns_uri',
    'AUTH_PHISHING_RESISTANT',
    'AUTH_MULTI_FACTOR',
    'AUTH_MULTI_FACTOR_PHYSICAL',
    ]

from openid.extension import Extension
import re

ns_uri = "http://specs.openid.net/extensions/pape/1.0"

AUTH_MULTI_FACTOR_PHYSICAL = \
    'http://schemas.openid.net/pape/policies/2007/06/multi-factor-physical'
AUTH_MULTI_FACTOR = \
    'http://schemas.openid.net/pape/policies/2007/06/multi-factor'
AUTH_PHISHING_RESISTANT = \
    'http://schemas.openid.net/pape/policies/2007/06/phishing-resistant'

TIME_VALIDATOR = re.compile('^\d\d\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ$')

class Request(Extension):
    """A Provider Authentication Policy request, sent from a relying
    party to a provider

    @ivar preferred_auth_policies: The authentication policies that
        the relying party prefers
    @type preferred_auth_policies: [str]

    @ivar max_auth_age: The maximum time, in seconds, that the relying
        party wants to allow to have elapsed before the user must
        re-authenticate
    @type max_auth_age: int or NoneType
    """

    ns_alias = 'pape'

    def __init__(self, preferred_auth_policies=None, max_auth_age=None):
        super(Request, self).__init__()
        if not preferred_auth_policies:
            preferred_auth_policies = []

        self.preferred_auth_policies = preferred_auth_policies
        self.max_auth_age = max_auth_age

    def __nonzero__(self):
        return bool(self.preferred_auth_policies or
                    self.max_auth_age is not None)

    def addPolicyURI(self, policy_uri):
        """Add an acceptable authentication policy URI to this request

        This method is intended to be used by the relying party to add
        acceptable authentication types to the request.

        @param policy_uri: The identifier for the preferred type of
            authentication.
        @see: http://openid.net/specs/openid-provider-authentication-policy-extension-1_0-01.html#auth_policies
        """
        if policy_uri not in self.preferred_auth_policies:
            self.preferred_auth_policies.append(policy_uri)

    def getExtensionArgs(self):
        """@see: C{L{Extension.getExtensionArgs}}
        """
        ns_args = {
            'preferred_auth_policies':' '.join(self.preferred_auth_policies)
            }

        if self.max_auth_age is not None:
            ns_args['max_auth_age'] = str(self.max_auth_age)

        return ns_args

    def fromOpenIDRequest(cls, request):
        """Instantiate a Request object from the arguments in a
        C{checkid_*} OpenID message
        """
        self = cls()
        args = request.message.getArgs(self.ns_uri)

        if args == {}:
            return None

        self.parseExtensionArgs(args)
        return self

    fromOpenIDRequest = classmethod(fromOpenIDRequest)

    def parseExtensionArgs(self, args):
        """Set the state of this request to be that expressed in these
        PAPE arguments

        @param args: The PAPE arguments without a namespace

        @rtype: None

        @raises ValueError: When the max_auth_age is not parseable as
            an integer
        """

        # preferred_auth_policies is a space-separated list of policy URIs
        self.preferred_auth_policies = []

        policies_str = args.get('preferred_auth_policies')
        if policies_str:
            for uri in policies_str.split(' '):
                if uri not in self.preferred_auth_policies:
                    self.preferred_auth_policies.append(uri)

        # max_auth_age is base-10 integer number of seconds
        max_auth_age_str = args.get('max_auth_age')
        self.max_auth_age = None

        if max_auth_age_str:
            try:
                self.max_auth_age = int(max_auth_age_str)
            except ValueError:
                pass

    def preferredTypes(self, supported_types):
        """Given a list of authentication policy URIs that a provider
        supports, this method returns the subsequence of those types
        that are preferred by the relying party.

        @param supported_types: A sequence of authentication policy
            type URIs that are supported by a provider

        @returns: The sub-sequence of the supported types that are
            preferred by the relying party. This list will be ordered
            in the order that the types appear in the supported_types
            sequence, and may be empty if the provider does not prefer
            any of the supported authentication types.

        @returntype: [str]
        """
        return filter(self.preferred_auth_policies.__contains__,
                      supported_types)

Request.ns_uri = ns_uri


class Response(Extension):
    """A Provider Authentication Policy response, sent from a provider
    to a relying party
    """

    ns_alias = 'pape'

    def __init__(self, auth_policies=None, auth_time=None,
                 nist_auth_level=None):
        super(Response, self).__init__()
        if auth_policies:
            self.auth_policies = auth_policies
        else:
            self.auth_policies = []

        self.auth_time = auth_time
        self.nist_auth_level = nist_auth_level

    def addPolicyURI(self, policy_uri):
        """Add a authentication policy to this response

        This method is intended to be used by the provider to add a
        policy that the provider conformed to when authenticating the user.

        @param policy_uri: The identifier for the preferred type of
            authentication.
        @see: http://openid.net/specs/openid-provider-authentication-policy-extension-1_0-01.html#auth_policies
        """
        if policy_uri not in self.auth_policies:
            self.auth_policies.append(policy_uri)

    def fromSuccessResponse(cls, success_response):
        """Create a C{L{Response}} object from a successful OpenID
        library response
        (C{L{openid.consumer.consumer.SuccessResponse}}) response
        message

        @param success_response: A SuccessResponse from consumer.complete()
        @type success_response: C{L{openid.consumer.consumer.SuccessResponse}}

        @rtype: Response or None
        @returns: A provider authentication policy response from the
            data that was supplied with the C{id_res} response or None
            if the provider sent no signed PAPE response arguments.
        """
        self = cls()

        # PAPE requires that the args be signed.
        args = success_response.getSignedNS(self.ns_uri)

        # Only try to construct a PAPE response if the arguments were
        # signed in the OpenID response.  If not, return None.
        if args is not None:
            self.parseExtensionArgs(args)
            return self
        else:
            return None

    def parseExtensionArgs(self, args, strict=False):
        """Parse the provider authentication policy arguments into the
        internal state of this object

        @param args: unqualified provider authentication policy
            arguments

        @param strict: Whether to raise an exception when bad data is
            encountered

        @returns: None. The data is parsed into the internal fields of
            this object.
        """
        policies_str = args.get('auth_policies')
        if policies_str and policies_str != 'none':
            self.auth_policies = policies_str.split(' ')

        nist_level_str = args.get('nist_auth_level')
        if nist_level_str:
            try:
                nist_level = int(nist_level_str)
            except ValueError:
                if strict:
                    raise ValueError('nist_auth_level must be an integer between '
                                     'zero and four, inclusive')
                else:
                    self.nist_auth_level = None
            else:
                if 0 <= nist_level < 5:
                    self.nist_auth_level = nist_level

        auth_time = args.get('auth_time')
        if auth_time:
            if TIME_VALIDATOR.match(auth_time):
                self.auth_time = auth_time
            elif strict:
                raise ValueError("auth_time must be in RFC3339 format")

    fromSuccessResponse = classmethod(fromSuccessResponse)

    def getExtensionArgs(self):
        """@see: C{L{Extension.getExtensionArgs}}
        """
        if len(self.auth_policies) == 0:
            ns_args = {
                'auth_policies':'none',
            }
        else:
            ns_args = {
                'auth_policies':' '.join(self.auth_policies),
                }

        if self.nist_auth_level is not None:
            if self.nist_auth_level not in range(0, 5):
                raise ValueError('nist_auth_level must be an integer between '
                                 'zero and four, inclusive')
            ns_args['nist_auth_level'] = str(self.nist_auth_level)

        if self.auth_time is not None:
            if not TIME_VALIDATOR.match(self.auth_time):
                raise ValueError('auth_time must be in RFC3339 format')

            ns_args['auth_time'] = self.auth_time

        return ns_args

Response.ns_uri = ns_uri

########NEW FILE########
__FILENAME__ = pape5
"""An implementation of the OpenID Provider Authentication Policy
Extension 1.0, Draft 5

@see: http://openid.net/developers/specs/

@since: 2.1.0
"""

__all__ = [
    'Request',
    'Response',
    'ns_uri',
    'AUTH_PHISHING_RESISTANT',
    'AUTH_MULTI_FACTOR',
    'AUTH_MULTI_FACTOR_PHYSICAL',
    'LEVELS_NIST',
    'LEVELS_JISA',
    ]

from openid.extension import Extension
import warnings
import re

ns_uri = "http://specs.openid.net/extensions/pape/1.0"

AUTH_MULTI_FACTOR_PHYSICAL = \
    'http://schemas.openid.net/pape/policies/2007/06/multi-factor-physical'
AUTH_MULTI_FACTOR = \
    'http://schemas.openid.net/pape/policies/2007/06/multi-factor'
AUTH_PHISHING_RESISTANT = \
    'http://schemas.openid.net/pape/policies/2007/06/phishing-resistant'
AUTH_NONE = \
    'http://schemas.openid.net/pape/policies/2007/06/none'

TIME_VALIDATOR = re.compile('^\d\d\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ$')

LEVELS_NIST = 'http://csrc.nist.gov/publications/nistpubs/800-63/SP800-63V1_0_2.pdf'
LEVELS_JISA = 'http://www.jisa.or.jp/spec/auth_level.html'

class PAPEExtension(Extension):
    _default_auth_level_aliases = {
        'nist': LEVELS_NIST,
        'jisa': LEVELS_JISA,
        }

    def __init__(self):
        self.auth_level_aliases = self._default_auth_level_aliases.copy()

    def _addAuthLevelAlias(self, auth_level_uri, alias=None):
        """Add an auth level URI alias to this request.

        @param auth_level_uri: The auth level URI to send in the
            request.

        @param alias: The namespace alias to use for this auth level
            in this message. May be None if the alias is not
            important.
        """
        if alias is None:
            try:
                alias = self._getAlias(auth_level_uri)
            except KeyError:
                alias = self._generateAlias()
        else:
            existing_uri = self.auth_level_aliases.get(alias)
            if existing_uri is not None and existing_uri != auth_level_uri:
                raise KeyError('Attempting to redefine alias %r from %r to %r',
                               alias, existing_uri, auth_level_uri)

        self.auth_level_aliases[alias] = auth_level_uri

    def _generateAlias(self):
        """Return an unused auth level alias"""
        for i in xrange(1000):
            alias = 'cust%d' % (i,)
            if alias not in self.auth_level_aliases:
                return alias

        raise RuntimeError('Could not find an unused alias (tried 1000!)')

    def _getAlias(self, auth_level_uri):
        """Return the alias for the specified auth level URI.

        @raises KeyError: if no alias is defined
        """
        for (alias, existing_uri) in self.auth_level_aliases.iteritems():
            if auth_level_uri == existing_uri:
                return alias

        raise KeyError(auth_level_uri)

class Request(PAPEExtension):
    """A Provider Authentication Policy request, sent from a relying
    party to a provider

    @ivar preferred_auth_policies: The authentication policies that
        the relying party prefers
    @type preferred_auth_policies: [str]

    @ivar max_auth_age: The maximum time, in seconds, that the relying
        party wants to allow to have elapsed before the user must
        re-authenticate
    @type max_auth_age: int or NoneType

    @ivar preferred_auth_level_types: Ordered list of authentication
        level namespace URIs

    @type preferred_auth_level_types: [str]
    """

    ns_alias = 'pape'

    def __init__(self, preferred_auth_policies=None, max_auth_age=None,
                 preferred_auth_level_types=None):
        super(Request, self).__init__()
        if preferred_auth_policies is None:
            preferred_auth_policies = []

        self.preferred_auth_policies = preferred_auth_policies
        self.max_auth_age = max_auth_age
        self.preferred_auth_level_types = []

        if preferred_auth_level_types is not None:
            for auth_level in preferred_auth_level_types:
                self.addAuthLevel(auth_level)

    def __nonzero__(self):
        return bool(self.preferred_auth_policies or
                    self.max_auth_age is not None or
                    self.preferred_auth_level_types)

    def addPolicyURI(self, policy_uri):
        """Add an acceptable authentication policy URI to this request

        This method is intended to be used by the relying party to add
        acceptable authentication types to the request.

        @param policy_uri: The identifier for the preferred type of
            authentication.
        @see: http://openid.net/specs/openid-provider-authentication-policy-extension-1_0-05.html#auth_policies
        """
        if policy_uri not in self.preferred_auth_policies:
            self.preferred_auth_policies.append(policy_uri)

    def addAuthLevel(self, auth_level_uri, alias=None):
        self._addAuthLevelAlias(auth_level_uri, alias)
        if auth_level_uri not in self.preferred_auth_level_types:
            self.preferred_auth_level_types.append(auth_level_uri)

    def getExtensionArgs(self):
        """@see: C{L{Extension.getExtensionArgs}}
        """
        ns_args = {
            'preferred_auth_policies':' '.join(self.preferred_auth_policies),
            }

        if self.max_auth_age is not None:
            ns_args['max_auth_age'] = str(self.max_auth_age)

        if self.preferred_auth_level_types:
            preferred_types = []

            for auth_level_uri in self.preferred_auth_level_types:
                alias = self._getAlias(auth_level_uri)
                ns_args['auth_level.ns.%s' % (alias,)] = auth_level_uri
                preferred_types.append(alias)

            ns_args['preferred_auth_level_types'] = ' '.join(preferred_types)

        return ns_args

    def fromOpenIDRequest(cls, request):
        """Instantiate a Request object from the arguments in a
        C{checkid_*} OpenID message
        """
        self = cls()
        args = request.message.getArgs(self.ns_uri)
        is_openid1 = request.message.isOpenID1()

        if args == {}:
            return None

        self.parseExtensionArgs(args, is_openid1)
        return self

    fromOpenIDRequest = classmethod(fromOpenIDRequest)

    def parseExtensionArgs(self, args, is_openid1, strict=False):
        """Set the state of this request to be that expressed in these
        PAPE arguments

        @param args: The PAPE arguments without a namespace

        @param strict: Whether to raise an exception if the input is
            out of spec or otherwise malformed. If strict is false,
            malformed input will be ignored.

        @param is_openid1: Whether the input should be treated as part
            of an OpenID1 request

        @rtype: None

        @raises ValueError: When the max_auth_age is not parseable as
            an integer
        """

        # preferred_auth_policies is a space-separated list of policy URIs
        self.preferred_auth_policies = []

        policies_str = args.get('preferred_auth_policies')
        if policies_str:
            for uri in policies_str.split(' '):
                if uri not in self.preferred_auth_policies:
                    self.preferred_auth_policies.append(uri)

        # max_auth_age is base-10 integer number of seconds
        max_auth_age_str = args.get('max_auth_age')
        self.max_auth_age = None

        if max_auth_age_str:
            try:
                self.max_auth_age = int(max_auth_age_str)
            except ValueError:
                if strict:
                    raise

        # Parse auth level information
        preferred_auth_level_types = args.get('preferred_auth_level_types')
        if preferred_auth_level_types:
            aliases = preferred_auth_level_types.strip().split()

            for alias in aliases:
                key = 'auth_level.ns.%s' % (alias,)
                try:
                    uri = args[key]
                except KeyError:
                    if is_openid1:
                        uri = self._default_auth_level_aliases.get(alias)
                    else:
                        uri = None

                if uri is None:
                    if strict:
                        raise ValueError('preferred auth level %r is not '
                                         'defined in this message' % (alias,))
                else:
                    self.addAuthLevel(uri, alias)

    def preferredTypes(self, supported_types):
        """Given a list of authentication policy URIs that a provider
        supports, this method returns the subsequence of those types
        that are preferred by the relying party.

        @param supported_types: A sequence of authentication policy
            type URIs that are supported by a provider

        @returns: The sub-sequence of the supported types that are
            preferred by the relying party. This list will be ordered
            in the order that the types appear in the supported_types
            sequence, and may be empty if the provider does not prefer
            any of the supported authentication types.

        @returntype: [str]
        """
        return filter(self.preferred_auth_policies.__contains__,
                      supported_types)

Request.ns_uri = ns_uri


class Response(PAPEExtension):
    """A Provider Authentication Policy response, sent from a provider
    to a relying party

    @ivar auth_policies: List of authentication policies conformed to
        by this OpenID assertion, represented as policy URIs
    """

    ns_alias = 'pape'

    def __init__(self, auth_policies=None, auth_time=None,
                 auth_levels=None):
        super(Response, self).__init__()
        if auth_policies:
            self.auth_policies = auth_policies
        else:
            self.auth_policies = []

        self.auth_time = auth_time
        self.auth_levels = {}

        if auth_levels is None:
            auth_levels = {}

        for uri, level in auth_levels.iteritems():
            self.setAuthLevel(uri, level)

    def setAuthLevel(self, level_uri, level, alias=None):
        """Set the value for the given auth level type.

        @param level: string representation of an authentication level
            valid for level_uri

        @param alias: An optional namespace alias for the given auth
            level URI. May be omitted if the alias is not
            significant. The library will use a reasonable default for
            widely-used auth level types.
        """
        self._addAuthLevelAlias(level_uri, alias)
        self.auth_levels[level_uri] = level

    def getAuthLevel(self, level_uri):
        """Return the auth level for the specified auth level
        identifier

        @returns: A string that should map to the auth levels defined
            for the auth level type

        @raises KeyError: If the auth level type is not present in
            this message
        """
        return self.auth_levels[level_uri]

    def _getNISTAuthLevel(self):
        try:
            return int(self.getAuthLevel(LEVELS_NIST))
        except KeyError:
            return None

    nist_auth_level = property(
        _getNISTAuthLevel,
        doc="Backward-compatibility accessor for the NIST auth level")

    def addPolicyURI(self, policy_uri):
        """Add a authentication policy to this response

        This method is intended to be used by the provider to add a
        policy that the provider conformed to when authenticating the user.

        @param policy_uri: The identifier for the preferred type of
            authentication.
        @see: http://openid.net/specs/openid-provider-authentication-policy-extension-1_0-01.html#auth_policies
        """
        if policy_uri == AUTH_NONE:
            raise RuntimeError(
                'To send no policies, do not set any on the response.')

        if policy_uri not in self.auth_policies:
            self.auth_policies.append(policy_uri)

    def fromSuccessResponse(cls, success_response):
        """Create a C{L{Response}} object from a successful OpenID
        library response
        (C{L{openid.consumer.consumer.SuccessResponse}}) response
        message

        @param success_response: A SuccessResponse from consumer.complete()
        @type success_response: C{L{openid.consumer.consumer.SuccessResponse}}

        @rtype: Response or None
        @returns: A provider authentication policy response from the
            data that was supplied with the C{id_res} response or None
            if the provider sent no signed PAPE response arguments.
        """
        self = cls()

        # PAPE requires that the args be signed.
        args = success_response.getSignedNS(self.ns_uri)
        is_openid1 = success_response.isOpenID1()

        # Only try to construct a PAPE response if the arguments were
        # signed in the OpenID response.  If not, return None.
        if args is not None:
            self.parseExtensionArgs(args, is_openid1)
            return self
        else:
            return None

    def parseExtensionArgs(self, args, is_openid1, strict=False):
        """Parse the provider authentication policy arguments into the
        internal state of this object

        @param args: unqualified provider authentication policy
            arguments

        @param strict: Whether to raise an exception when bad data is
            encountered

        @returns: None. The data is parsed into the internal fields of
            this object.
        """
        policies_str = args.get('auth_policies')
        if policies_str:
            auth_policies = policies_str.split(' ')
        elif strict:
            raise ValueError('Missing auth_policies')
        else:
            auth_policies = []

        if (len(auth_policies) > 1 and strict and AUTH_NONE in auth_policies):
            raise ValueError('Got some auth policies, as well as the special '
                             '"none" URI: %r' % (auth_policies,))

        if 'none' in auth_policies:
            msg = '"none" used as a policy URI (see PAPE draft < 5)'
            if strict:
                raise ValueError(msg)
            else:
                warnings.warn(msg, stacklevel=2)

        auth_policies = [u for u in auth_policies
                         if u not in ['none', AUTH_NONE]]

        self.auth_policies = auth_policies

        for (key, val) in args.iteritems():
            if key.startswith('auth_level.'):
                alias = key[11:]

                # skip the already-processed namespace declarations
                if alias.startswith('ns.'):
                    continue

                try:
                    uri = args['auth_level.ns.%s' % (alias,)]
                except KeyError:
                    if is_openid1:
                        uri = self._default_auth_level_aliases.get(alias)
                    else:
                        uri = None

                if uri is None:
                    if strict:
                        raise ValueError(
                            'Undefined auth level alias: %r' % (alias,))
                else:
                    self.setAuthLevel(uri, val, alias)

        auth_time = args.get('auth_time')
        if auth_time:
            if TIME_VALIDATOR.match(auth_time):
                self.auth_time = auth_time
            elif strict:
                raise ValueError("auth_time must be in RFC3339 format")

    fromSuccessResponse = classmethod(fromSuccessResponse)

    def getExtensionArgs(self):
        """@see: C{L{Extension.getExtensionArgs}}
        """
        if len(self.auth_policies) == 0:
            ns_args = {
                'auth_policies': AUTH_NONE,
            }
        else:
            ns_args = {
                'auth_policies':' '.join(self.auth_policies),
                }

        for level_type, level in self.auth_levels.iteritems():
            alias = self._getAlias(level_type)
            ns_args['auth_level.ns.%s' % (alias,)] = level_type
            ns_args['auth_level.%s' % (alias,)] = str(level)

        if self.auth_time is not None:
            if not TIME_VALIDATOR.match(self.auth_time):
                raise ValueError('auth_time must be in RFC3339 format')

            ns_args['auth_time'] = self.auth_time

        return ns_args

Response.ns_uri = ns_uri

########NEW FILE########
__FILENAME__ = sreg
"""Simple registration request and response parsing and object representation

This module contains objects representing simple registration requests
and responses that can be used with both OpenID relying parties and
OpenID providers.

  1. The relying party creates a request object and adds it to the
     C{L{AuthRequest<openid.consumer.consumer.AuthRequest>}} object
     before making the C{checkid_} request to the OpenID provider::

      auth_request.addExtension(SRegRequest(required=['email']))

  2. The OpenID provider extracts the simple registration request from
     the OpenID request using C{L{SRegRequest.fromOpenIDRequest}},
     gets the user's approval and data, creates a C{L{SRegResponse}}
     object and adds it to the C{id_res} response::

      sreg_req = SRegRequest.fromOpenIDRequest(checkid_request)
      # [ get the user's approval and data, informing the user that
      #   the fields in sreg_response were requested ]
      sreg_resp = SRegResponse.extractResponse(sreg_req, user_data)
      sreg_resp.toMessage(openid_response.fields)

  3. The relying party uses C{L{SRegResponse.fromSuccessResponse}} to
     extract the data from the OpenID response::

      sreg_resp = SRegResponse.fromSuccessResponse(success_response)

@since: 2.0

@var sreg_data_fields: The names of the data fields that are listed in
    the sreg spec, and a description of them in English

@var sreg_uri: The preferred URI to use for the simple registration
    namespace and XRD Type value
"""

from openid.message import registerNamespaceAlias, \
     NamespaceAliasRegistrationError
from openid.extension import Extension
import logging

try:
    basestring #pylint:disable-msg=W0104
except NameError:
    # For Python 2.2
    basestring = (str, unicode) #pylint:disable-msg=W0622

__all__ = [
    'SRegRequest',
    'SRegResponse',
    'data_fields',
    'ns_uri',
    'ns_uri_1_0',
    'ns_uri_1_1',
    'supportsSReg',
    ]

# The data fields that are listed in the sreg spec
data_fields = {
    'fullname':'Full Name',
    'nickname':'Nickname',
    'dob':'Date of Birth',
    'email':'E-mail Address',
    'gender':'Gender',
    'postcode':'Postal Code',
    'country':'Country',
    'language':'Language',
    'timezone':'Time Zone',
    }

def checkFieldName(field_name):
    """Check to see that the given value is a valid simple
    registration data field name.

    @raise ValueError: if the field name is not a valid simple
        registration data field name
    """
    if field_name not in data_fields:
        raise ValueError('%r is not a defined simple registration field' %
                         (field_name,))

# URI used in the wild for Yadis documents advertising simple
# registration support
ns_uri_1_0 = 'http://openid.net/sreg/1.0'

# URI in the draft specification for simple registration 1.1
# <http://openid.net/specs/openid-simple-registration-extension-1_1-01.html>
ns_uri_1_1 = 'http://openid.net/extensions/sreg/1.1'

# This attribute will always hold the preferred URI to use when adding
# sreg support to an XRDS file or in an OpenID namespace declaration.
ns_uri = ns_uri_1_1

try:
    registerNamespaceAlias(ns_uri_1_1, 'sreg')
except NamespaceAliasRegistrationError, e:
    logging.exception('registerNamespaceAlias(%r, %r) failed: %s' % (ns_uri_1_1,
                                                               'sreg', str(e),))

def supportsSReg(endpoint):
    """Does the given endpoint advertise support for simple
    registration?

    @param endpoint: The endpoint object as returned by OpenID discovery
    @type endpoint: openid.consumer.discover.OpenIDEndpoint

    @returns: Whether an sreg type was advertised by the endpoint
    @rtype: bool
    """
    return (endpoint.usesExtension(ns_uri_1_1) or
            endpoint.usesExtension(ns_uri_1_0))

class SRegNamespaceError(ValueError):
    """The simple registration namespace was not found and could not
    be created using the expected name (there's another extension
    using the name 'sreg')

    This is not I{illegal}, for OpenID 2, although it probably
    indicates a problem, since it's not expected that other extensions
    will re-use the alias that is in use for OpenID 1.

    If this is an OpenID 1 request, then there is no recourse. This
    should not happen unless some code has modified the namespaces for
    the message that is being processed.
    """

def getSRegNS(message):
    """Extract the simple registration namespace URI from the given
    OpenID message. Handles OpenID 1 and 2, as well as both sreg
    namespace URIs found in the wild, as well as missing namespace
    definitions (for OpenID 1)

    @param message: The OpenID message from which to parse simple
        registration fields. This may be a request or response message.
    @type message: C{L{openid.message.Message}}

    @returns: the sreg namespace URI for the supplied message. The
        message may be modified to define a simple registration
        namespace.
    @rtype: C{str}

    @raise ValueError: when using OpenID 1 if the message defines
        the 'sreg' alias to be something other than a simple
        registration type.
    """
    # See if there exists an alias for one of the two defined simple
    # registration types.
    for sreg_ns_uri in [ns_uri_1_1, ns_uri_1_0]:
        alias = message.namespaces.getAlias(sreg_ns_uri)
        if alias is not None:
            break
    else:
        # There is no alias for either of the types, so try to add
        # one. We default to using the modern value (1.1)
        sreg_ns_uri = ns_uri_1_1
        try:
            message.namespaces.addAlias(ns_uri_1_1, 'sreg')
        except KeyError, why:
            # An alias for the string 'sreg' already exists, but it's
            # defined for something other than simple registration
            raise SRegNamespaceError(why[0])

    # we know that sreg_ns_uri defined, because it's defined in the
    # else clause of the loop as well, so disable the warning
    return sreg_ns_uri #pylint:disable-msg=W0631

class SRegRequest(Extension):
    """An object to hold the state of a simple registration request.

    @ivar required: A list of the required fields in this simple
        registration request
    @type required: [str]

    @ivar optional: A list of the optional fields in this simple
        registration request
    @type optional: [str]

    @ivar policy_url: The policy URL that was provided with the request
    @type policy_url: str or NoneType

    @group Consumer: requestField, requestFields, getExtensionArgs, addToOpenIDRequest
    @group Server: fromOpenIDRequest, parseExtensionArgs
    """

    ns_alias = 'sreg'

    def __init__(self, required=None, optional=None, policy_url=None,
                 sreg_ns_uri=ns_uri):
        """Initialize an empty simple registration request"""
        Extension.__init__(self)
        self.required = []
        self.optional = []
        self.policy_url = policy_url
        self.ns_uri = sreg_ns_uri

        if required:
            self.requestFields(required, required=True, strict=True)

        if optional:
            self.requestFields(optional, required=False, strict=True)

    # Assign getSRegNS to a static method so that it can be
    # overridden for testing.
    _getSRegNS = staticmethod(getSRegNS)

    def fromOpenIDRequest(cls, request):
        """Create a simple registration request that contains the
        fields that were requested in the OpenID request with the
        given arguments

        @param request: The OpenID request
        @type request: openid.server.CheckIDRequest

        @returns: The newly created simple registration request
        @rtype: C{L{SRegRequest}}
        """
        self = cls()

        # Since we're going to mess with namespace URI mapping, don't
        # mutate the object that was passed in.
        message = request.message.copy()

        self.ns_uri = self._getSRegNS(message)
        args = message.getArgs(self.ns_uri)
        self.parseExtensionArgs(args)

        return self

    fromOpenIDRequest = classmethod(fromOpenIDRequest)

    def parseExtensionArgs(self, args, strict=False):
        """Parse the unqualified simple registration request
        parameters and add them to this object.

        This method is essentially the inverse of
        C{L{getExtensionArgs}}. This method restores the serialized simple
        registration request fields.

        If you are extracting arguments from a standard OpenID
        checkid_* request, you probably want to use C{L{fromOpenIDRequest}},
        which will extract the sreg namespace and arguments from the
        OpenID request. This method is intended for cases where the
        OpenID server needs more control over how the arguments are
        parsed than that method provides.

        >>> args = message.getArgs(ns_uri)
        >>> request.parseExtensionArgs(args)

        @param args: The unqualified simple registration arguments
        @type args: {str:str}

        @param strict: Whether requests with fields that are not
            defined in the simple registration specification should be
            tolerated (and ignored)
        @type strict: bool

        @returns: None; updates this object
        """
        for list_name in ['required', 'optional']:
            required = (list_name == 'required')
            items = args.get(list_name)
            if items:
                for field_name in items.split(','):
                    try:
                        self.requestField(field_name, required, strict)
                    except ValueError:
                        if strict:
                            raise

        self.policy_url = args.get('policy_url')

    def allRequestedFields(self):
        """A list of all of the simple registration fields that were
        requested, whether they were required or optional.

        @rtype: [str]
        """
        return self.required + self.optional

    def wereFieldsRequested(self):
        """Have any simple registration fields been requested?

        @rtype: bool
        """
        return bool(self.allRequestedFields())

    def __contains__(self, field_name):
        """Was this field in the request?"""
        return (field_name in self.required or
                field_name in self.optional)

    def requestField(self, field_name, required=False, strict=False):
        """Request the specified field from the OpenID user

        @param field_name: the unqualified simple registration field name
        @type field_name: str

        @param required: whether the given field should be presented
            to the user as being a required to successfully complete
            the request

        @param strict: whether to raise an exception when a field is
            added to a request more than once

        @raise ValueError: when the field requested is not a simple
            registration field or strict is set and the field was
            requested more than once
        """
        checkFieldName(field_name)

        if strict:
            if field_name in self.required or field_name in self.optional:
                raise ValueError('That field has already been requested')
        else:
            if field_name in self.required:
                return

            if field_name in self.optional:
                if required:
                    self.optional.remove(field_name)
                else:
                    return

        if required:
            self.required.append(field_name)
        else:
            self.optional.append(field_name)

    def requestFields(self, field_names, required=False, strict=False):
        """Add the given list of fields to the request

        @param field_names: The simple registration data fields to request
        @type field_names: [str]

        @param required: Whether these values should be presented to
            the user as required

        @param strict: whether to raise an exception when a field is
            added to a request more than once

        @raise ValueError: when a field requested is not a simple
            registration field or strict is set and a field was
            requested more than once
        """
        if isinstance(field_names, basestring):
            raise TypeError('Fields should be passed as a list of '
                            'strings (not %r)' % (type(field_names),))

        for field_name in field_names:
            self.requestField(field_name, required, strict=strict)

    def getExtensionArgs(self):
        """Get a dictionary of unqualified simple registration
        arguments representing this request.

        This method is essentially the inverse of
        C{L{parseExtensionArgs}}. This method serializes the simple
        registration request fields.

        @rtype: {str:str}
        """
        args = {}

        if self.required:
            args['required'] = ','.join(self.required)

        if self.optional:
            args['optional'] = ','.join(self.optional)

        if self.policy_url:
            args['policy_url'] = self.policy_url

        return args

class SRegResponse(Extension):
    """Represents the data returned in a simple registration response
    inside of an OpenID C{id_res} response. This object will be
    created by the OpenID server, added to the C{id_res} response
    object, and then extracted from the C{id_res} message by the
    Consumer.

    @ivar data: The simple registration data, keyed by the unqualified
        simple registration name of the field (i.e. nickname is keyed
        by C{'nickname'})

    @ivar ns_uri: The URI under which the simple registration data was
        stored in the response message.

    @group Server: extractResponse
    @group Consumer: fromSuccessResponse
    @group Read-only dictionary interface: keys, iterkeys, items, iteritems,
        __iter__, get, __getitem__, keys, has_key
    """

    ns_alias = 'sreg'

    def __init__(self, data=None, sreg_ns_uri=ns_uri):
        Extension.__init__(self)
        if data is None:
            self.data = {}
        else:
            self.data = data

        self.ns_uri = sreg_ns_uri

    def extractResponse(cls, request, data):
        """Take a C{L{SRegRequest}} and a dictionary of simple
        registration values and create a C{L{SRegResponse}}
        object containing that data.

        @param request: The simple registration request object
        @type request: SRegRequest

        @param data: The simple registration data for this
            response, as a dictionary from unqualified simple
            registration field name to string (unicode) value. For
            instance, the nickname should be stored under the key
            'nickname'.
        @type data: {str:str}

        @returns: a simple registration response object
        @rtype: SRegResponse
        """
        self = cls()
        self.ns_uri = request.ns_uri
        for field in request.allRequestedFields():
            value = data.get(field)
            if value is not None:
                self.data[field] = value
        return self

    extractResponse = classmethod(extractResponse)

    # Assign getSRegArgs to a static method so that it can be
    # overridden for testing
    _getSRegNS = staticmethod(getSRegNS)

    def fromSuccessResponse(cls, success_response, signed_only=True):
        """Create a C{L{SRegResponse}} object from a successful OpenID
        library response
        (C{L{openid.consumer.consumer.SuccessResponse}}) response
        message

        @param success_response: A SuccessResponse from consumer.complete()
        @type success_response: C{L{openid.consumer.consumer.SuccessResponse}}

        @param signed_only: Whether to process only data that was
            signed in the id_res message from the server.
        @type signed_only: bool

        @rtype: SRegResponse
        @returns: A simple registration response containing the data
            that was supplied with the C{id_res} response.
        """
        self = cls()
        self.ns_uri = self._getSRegNS(success_response.message)
        if signed_only:
            args = success_response.getSignedNS(self.ns_uri)
        else:
            args = success_response.message.getArgs(self.ns_uri)

        if not args:
            return None

        for field_name in data_fields:
            if field_name in args:
                self.data[field_name] = args[field_name]

        return self

    fromSuccessResponse = classmethod(fromSuccessResponse)

    def getExtensionArgs(self):
        """Get the fields to put in the simple registration namespace
        when adding them to an id_res message.

        @see: openid.extension
        """
        return self.data

    # Read-only dictionary interface
    def get(self, field_name, default=None):
        """Like dict.get, except that it checks that the field name is
        defined by the simple registration specification"""
        checkFieldName(field_name)
        return self.data.get(field_name, default)

    def items(self):
        """All of the data values in this simple registration response
        """
        return self.data.items()

    def iteritems(self):
        return self.data.iteritems()

    def keys(self):
        return self.data.keys()

    def iterkeys(self):
        return self.data.iterkeys()

    def has_key(self, key):
        return key in self

    def __contains__(self, field_name):
        checkFieldName(field_name)
        return field_name in self.data

    def __iter__(self):
        return iter(self.data)

    def __getitem__(self, field_name):
        checkFieldName(field_name)
        return self.data[field_name]

    def __nonzero__(self):
        return bool(self.data)

########NEW FILE########
__FILENAME__ = fetchers
# -*- test-case-name: openid.test.test_fetchers -*-
"""
This module contains the HTTP fetcher interface and several implementations.
"""

__all__ = ['fetch', 'getDefaultFetcher', 'setDefaultFetcher', 'HTTPResponse',
           'HTTPFetcher', 'createHTTPFetcher', 'HTTPFetchingError',
           'HTTPError']

import urllib2
import time
import cStringIO
import sys

import openid
import openid.urinorm

# Try to import httplib2 for caching support
# http://bitworking.org/projects/httplib2/
try:
    import httplib2
except ImportError:
    # httplib2 not available
    httplib2 = None

# try to import pycurl, which will let us use CurlHTTPFetcher
try:
    import pycurl
except ImportError:
    pycurl = None

USER_AGENT = "python-openid/%s (%s)" % (openid.__version__, sys.platform)
MAX_RESPONSE_KB = 1024

def fetch(url, body=None, headers=None):
    """Invoke the fetch method on the default fetcher. Most users
    should need only this method.

    @raises Exception: any exceptions that may be raised by the default fetcher
    """
    fetcher = getDefaultFetcher()
    return fetcher.fetch(url, body, headers)

def createHTTPFetcher():
    """Create a default HTTP fetcher instance

    prefers Curl to urllib2."""
    if pycurl is None:
        fetcher = Urllib2Fetcher()
    else:
        fetcher = CurlHTTPFetcher()

    return fetcher

# Contains the currently set HTTP fetcher. If it is set to None, the
# library will call createHTTPFetcher() to set it. Do not access this
# variable outside of this module.
_default_fetcher = None

def getDefaultFetcher():
    """Return the default fetcher instance
    if no fetcher has been set, it will create a default fetcher.

    @return: the default fetcher
    @rtype: HTTPFetcher
    """
    global _default_fetcher

    if _default_fetcher is None:
        setDefaultFetcher(createHTTPFetcher())

    return _default_fetcher

def setDefaultFetcher(fetcher, wrap_exceptions=True):
    """Set the default fetcher

    @param fetcher: The fetcher to use as the default HTTP fetcher
    @type fetcher: HTTPFetcher

    @param wrap_exceptions: Whether to wrap exceptions thrown by the
        fetcher wil HTTPFetchingError so that they may be caught
        easier. By default, exceptions will be wrapped. In general,
        unwrapped fetchers are useful for debugging of fetching errors
        or if your fetcher raises well-known exceptions that you would
        like to catch.
    @type wrap_exceptions: bool
    """
    global _default_fetcher
    if fetcher is None or not wrap_exceptions:
        _default_fetcher = fetcher
    else:
        _default_fetcher = ExceptionWrappingFetcher(fetcher)

def usingCurl():
    """Whether the currently set HTTP fetcher is a Curl HTTP fetcher."""
    fetcher = getDefaultFetcher()
    if isinstance(fetcher, ExceptionWrappingFetcher):
        fetcher = fetcher.fetcher
    return isinstance(fetcher, CurlHTTPFetcher)

class HTTPResponse(object):
    """XXX document attributes"""
    headers = None
    status = None
    body = None
    final_url = None

    def __init__(self, final_url=None, status=None, headers=None, body=None):
        self.final_url = final_url
        self.status = status
        self.headers = headers
        self.body = body

    def __repr__(self):
        return "<%s status %s for %s>" % (self.__class__.__name__,
                                          self.status,
                                          self.final_url)

class HTTPFetcher(object):
    """
    This class is the interface for openid HTTP fetchers.  This
    interface is only important if you need to write a new fetcher for
    some reason.
    """

    def fetch(self, url, body=None, headers=None):
        """
        This performs an HTTP POST or GET, following redirects along
        the way. If a body is specified, then the request will be a
        POST. Otherwise, it will be a GET.


        @param headers: HTTP headers to include with the request
        @type headers: {str:str}

        @return: An object representing the server's HTTP response. If
            there are network or protocol errors, an exception will be
            raised. HTTP error responses, like 404 or 500, do not
            cause exceptions.

        @rtype: L{HTTPResponse}

        @raise Exception: Different implementations will raise
            different errors based on the underlying HTTP library.
        """
        raise NotImplementedError

def _allowedURL(url):
    return url.startswith('http://') or url.startswith('https://')

class HTTPFetchingError(Exception):
    """Exception that is wrapped around all exceptions that are raised
    by the underlying fetcher when using the ExceptionWrappingFetcher

    @ivar why: The exception that caused this exception
    """
    def __init__(self, why=None):
        Exception.__init__(self, why)
        self.why = why

class ExceptionWrappingFetcher(HTTPFetcher):
    """Fetcher that wraps another fetcher, causing all exceptions

    @cvar uncaught_exceptions: Exceptions that should be exposed to the
        user if they are raised by the fetch call
    """

    uncaught_exceptions = (SystemExit, KeyboardInterrupt, MemoryError)

    def __init__(self, fetcher):
        self.fetcher = fetcher

    def fetch(self, *args, **kwargs):
        try:
            return self.fetcher.fetch(*args, **kwargs)
        except self.uncaught_exceptions:
            raise
        except:
            exc_cls, exc_inst = sys.exc_info()[:2]
            if exc_inst is None:
                # string exceptions
                exc_inst = exc_cls

            raise HTTPFetchingError(why=exc_inst)

class Urllib2Fetcher(HTTPFetcher):
    """An C{L{HTTPFetcher}} that uses urllib2.
    """

    # Parameterized for the benefit of testing frameworks, see
    # http://trac.openidenabled.com/trac/ticket/85
    urlopen = staticmethod(urllib2.urlopen)

    def fetch(self, url, body=None, headers=None):
        if not _allowedURL(url):
            raise ValueError('Bad URL scheme: %r' % (url,))

        if headers is None:
            headers = {}

        headers.setdefault(
            'User-Agent',
            "%s Python-urllib/%s" % (USER_AGENT, urllib2.__version__,))

        req = urllib2.Request(url, data=body, headers=headers)
        try:
            f = self.urlopen(req)
            try:
                return self._makeResponse(f)
            finally:
                f.close()
        except urllib2.HTTPError, why:
            try:
                return self._makeResponse(why)
            finally:
                why.close()

    def _makeResponse(self, urllib2_response):
        resp = HTTPResponse()
        resp.body = urllib2_response.read(MAX_RESPONSE_KB * 1024)
        resp.final_url = urllib2_response.geturl()
        resp.headers = dict(urllib2_response.info().items())

        if hasattr(urllib2_response, 'code'):
            resp.status = urllib2_response.code
        else:
            resp.status = 200

        return resp

class HTTPError(HTTPFetchingError):
    """
    This exception is raised by the C{L{CurlHTTPFetcher}} when it
    encounters an exceptional situation fetching a URL.
    """
    pass

# XXX: define what we mean by paranoid, and make sure it is.
class CurlHTTPFetcher(HTTPFetcher):
    """
    An C{L{HTTPFetcher}} that uses pycurl for fetching.
    See U{http://pycurl.sourceforge.net/}.
    """
    ALLOWED_TIME = 20 # seconds

    def __init__(self):
        HTTPFetcher.__init__(self)
        if pycurl is None:
            raise RuntimeError('Cannot find pycurl library')

    def _parseHeaders(self, header_file):
        header_file.seek(0)

        # Remove the status line from the beginning of the input
        unused_http_status_line = header_file.readline().lower ()
        if unused_http_status_line.startswith('http/1.1 100 '):
            unused_http_status_line = header_file.readline()
            unused_http_status_line = header_file.readline()

        lines = [line.strip() for line in header_file]

        # and the blank line from the end
        empty_line = lines.pop()
        if empty_line:
            raise HTTPError("No blank line at end of headers: %r" % (line,))

        headers = {}
        for line in lines:
            try:
                name, value = line.split(':', 1)
            except ValueError:
                raise HTTPError(
                    "Malformed HTTP header line in response: %r" % (line,))

            value = value.strip()

            # HTTP headers are case-insensitive
            name = name.lower()
            headers[name] = value

        return headers

    def _checkURL(self, url):
        # XXX: document that this can be overridden to match desired policy
        # XXX: make sure url is well-formed and routeable
        return _allowedURL(url)

    def fetch(self, url, body=None, headers=None):
        stop = int(time.time()) + self.ALLOWED_TIME
        off = self.ALLOWED_TIME

        if headers is None:
            headers = {}

        headers.setdefault('User-Agent',
                           "%s %s" % (USER_AGENT, pycurl.version,))

        header_list = []
        if headers is not None:
            for header_name, header_value in headers.iteritems():
                header_list.append('%s: %s' % (header_name, header_value))

        c = pycurl.Curl()
        try:
            c.setopt(pycurl.NOSIGNAL, 1)

            if header_list:
                c.setopt(pycurl.HTTPHEADER, header_list)

            # Presence of a body indicates that we should do a POST
            if body is not None:
                c.setopt(pycurl.POST, 1)
                c.setopt(pycurl.POSTFIELDS, body)

            while off > 0:
                if not self._checkURL(url):
                    raise HTTPError("Fetching URL not allowed: %r" % (url,))

                data = cStringIO.StringIO()
                def write_data(chunk):
                    if data.tell() > 1024*MAX_RESPONSE_KB:
                        return 0
                    else:
                        return data.write(chunk)

                response_header_data = cStringIO.StringIO()
                c.setopt(pycurl.WRITEFUNCTION, write_data)
                c.setopt(pycurl.HEADERFUNCTION, response_header_data.write)
                c.setopt(pycurl.TIMEOUT, off)
                c.setopt(pycurl.URL, openid.urinorm.urinorm(url))

                c.perform()

                response_headers = self._parseHeaders(response_header_data)
                code = c.getinfo(pycurl.RESPONSE_CODE)
                if code in [301, 302, 303, 307]:
                    url = response_headers.get('location')
                    if url is None:
                        raise HTTPError(
                            'Redirect (%s) returned without a location' % code)

                    # Redirects are always GETs
                    c.setopt(pycurl.POST, 0)

                    # There is no way to reset POSTFIELDS to empty and
                    # reuse the connection, but we only use it once.
                else:
                    resp = HTTPResponse()
                    resp.headers = response_headers
                    resp.status = code
                    resp.final_url = url
                    resp.body = data.getvalue()
                    return resp

                off = stop - int(time.time())

            raise HTTPError("Timed out fetching: %r" % (url,))
        finally:
            c.close()

class HTTPLib2Fetcher(HTTPFetcher):
    """A fetcher that uses C{httplib2} for performing HTTP
    requests. This implementation supports HTTP caching.

    @see: http://bitworking.org/projects/httplib2/
    """

    def __init__(self, cache=None):
        """@param cache: An object suitable for use as an C{httplib2}
            cache. If a string is passed, it is assumed to be a
            directory name.
        """
        if httplib2 is None:
            raise RuntimeError('Cannot find httplib2 library. '
                               'See http://bitworking.org/projects/httplib2/')

        super(HTTPLib2Fetcher, self).__init__()

        # An instance of the httplib2 object that performs HTTP requests
        self.httplib2 = httplib2.Http(cache)

        # We want httplib2 to raise exceptions for errors, just like
        # the other fetchers.
        self.httplib2.force_exception_to_status_code = False

    def fetch(self, url, body=None, headers=None):
        """Perform an HTTP request

        @raises Exception: Any exception that can be raised by httplib2

        @see: C{L{HTTPFetcher.fetch}}
        """
        if body:
            method = 'POST'
        else:
            method = 'GET'

        if headers is None:
            headers = {}

        # httplib2 doesn't check to make sure that the URL's scheme is
        # 'http' so we do it here.
        if not (url.startswith('http://') or url.startswith('https://')):
            raise ValueError('URL is not a HTTP URL: %r' % (url,))

        httplib2_response, content = self.httplib2.request(
            url, method, body=body, headers=headers)

        # Translate the httplib2 response to our HTTP response abstraction

        # When a 400 is returned, there is no "content-location"
        # header set. This seems like a bug to me. I can't think of a
        # case where we really care about the final URL when it is an
        # error response, but being careful about it can't hurt.
        try:
            final_url = httplib2_response['content-location']
        except KeyError:
            # We're assuming that no redirects occurred
            assert not httplib2_response.previous

            # And this should never happen for a successful response
            assert httplib2_response.status != 200
            final_url = url

        return HTTPResponse(
            body=content,
            final_url=final_url,
            headers=dict(httplib2_response.items()),
            status=httplib2_response.status,
            )

########NEW FILE########
__FILENAME__ = kvform
__all__ = ['seqToKV', 'kvToSeq', 'dictToKV', 'kvToDict']

import types
import logging

class KVFormError(ValueError):
    pass

def seqToKV(seq, strict=False):
    """Represent a sequence of pairs of strings as newline-terminated
    key:value pairs. The pairs are generated in the order given.

    @param seq: The pairs
    @type seq: [(str, (unicode|str))]

    @return: A string representation of the sequence
    @rtype: str
    """
    def err(msg):
        formatted = 'seqToKV warning: %s: %r' % (msg, seq)
        if strict:
            raise KVFormError(formatted)
        else:
            logging.warn(formatted)

    lines = []
    for k, v in seq:
        if isinstance(k, types.StringType):
            k = k.decode('UTF8')
        elif not isinstance(k, types.UnicodeType):
            err('Converting key to string: %r' % k)
            k = str(k)

        if '\n' in k:
            raise KVFormError(
                'Invalid input for seqToKV: key contains newline: %r' % (k,))

        if ':' in k:
            raise KVFormError(
                'Invalid input for seqToKV: key contains colon: %r' % (k,))

        if k.strip() != k:
            err('Key has whitespace at beginning or end: %r' % (k,))

        if isinstance(v, types.StringType):
            v = v.decode('UTF8')
        elif not isinstance(v, types.UnicodeType):
            err('Converting value to string: %r' % (v,))
            v = str(v)

        if '\n' in v:
            raise KVFormError(
                'Invalid input for seqToKV: value contains newline: %r' % (v,))

        if v.strip() != v:
            err('Value has whitespace at beginning or end: %r' % (v,))

        lines.append(k + ':' + v + '\n')

    return ''.join(lines).encode('UTF8')

def kvToSeq(data, strict=False):
    """

    After one parse, seqToKV and kvToSeq are inverses, with no warnings::

        seq = kvToSeq(s)
        seqToKV(kvToSeq(seq)) == seq
    """
    def err(msg):
        formatted = 'kvToSeq warning: %s: %r' % (msg, data)
        if strict:
            raise KVFormError(formatted)
        else:
            logging.warn(formatted)

    lines = data.split('\n')
    if lines[-1]:
        err('Does not end in a newline')
    else:
        del lines[-1]

    pairs = []
    line_num = 0
    for line in lines:
        line_num += 1

        # Ignore blank lines
        if not line.strip():
            continue

        pair = line.split(':', 1)
        if len(pair) == 2:
            k, v = pair
            k_s = k.strip()
            if k_s != k:
                fmt = ('In line %d, ignoring leading or trailing '
                       'whitespace in key %r')
                err(fmt % (line_num, k))

            if not k_s:
                err('In line %d, got empty key' % (line_num,))

            v_s = v.strip()
            if v_s != v:
                fmt = ('In line %d, ignoring leading or trailing '
                       'whitespace in value %r')
                err(fmt % (line_num, v))

            pairs.append((k_s.decode('UTF8'), v_s.decode('UTF8')))
        else:
            err('Line %d does not contain a colon' % line_num)

    return pairs

def dictToKV(d):
    seq = d.items()
    seq.sort()
    return seqToKV(seq)

def kvToDict(s):
    return dict(kvToSeq(s))

########NEW FILE########
__FILENAME__ = message
"""Extension argument processing code
"""
__all__ = ['Message', 'NamespaceMap', 'no_default', 'registerNamespaceAlias',
           'OPENID_NS', 'BARE_NS', 'OPENID1_NS', 'OPENID2_NS', 'SREG_URI',
           'IDENTIFIER_SELECT']

import copy
import warnings
import urllib

from openid import oidutil
from openid import kvform
try:
    ElementTree = oidutil.importElementTree()
except ImportError:
    # No elementtree found, so give up, but don't fail to import,
    # since we have fallbacks.
    ElementTree = None

# This doesn't REALLY belong here, but where is better?
IDENTIFIER_SELECT = 'http://specs.openid.net/auth/2.0/identifier_select'

# URI for Simple Registration extension, the only commonly deployed
# OpenID 1.x extension, and so a special case
SREG_URI = 'http://openid.net/sreg/1.0'

# The OpenID 1.X namespace URI
OPENID1_NS = 'http://openid.net/signon/1.0'
THE_OTHER_OPENID1_NS = 'http://openid.net/signon/1.1'

OPENID1_NAMESPACES = OPENID1_NS, THE_OTHER_OPENID1_NS

# The OpenID 2.0 namespace URI
OPENID2_NS = 'http://specs.openid.net/auth/2.0'

# The namespace consisting of pairs with keys that are prefixed with
# "openid."  but not in another namespace.
NULL_NAMESPACE = oidutil.Symbol('Null namespace')

# The null namespace, when it is an allowed OpenID namespace
OPENID_NS = oidutil.Symbol('OpenID namespace')

# The top-level namespace, excluding all pairs with keys that start
# with "openid."
BARE_NS = oidutil.Symbol('Bare namespace')

# Limit, in bytes, of identity provider and return_to URLs, including
# response payload.  See OpenID 1.1 specification, Appendix D.
OPENID1_URL_LIMIT = 2047

# All OpenID protocol fields.  Used to check namespace aliases.
OPENID_PROTOCOL_FIELDS = [
    'ns', 'mode', 'error', 'return_to', 'contact', 'reference',
    'signed', 'assoc_type', 'session_type', 'dh_modulus', 'dh_gen',
    'dh_consumer_public', 'claimed_id', 'identity', 'realm',
    'invalidate_handle', 'op_endpoint', 'response_nonce', 'sig',
    'assoc_handle', 'trust_root', 'openid',
    ]

class UndefinedOpenIDNamespace(ValueError):
    """Raised if the generic OpenID namespace is accessed when there
    is no OpenID namespace set for this message."""

class InvalidOpenIDNamespace(ValueError):
    """Raised if openid.ns is not a recognized value.

    For recognized values, see L{Message.allowed_openid_namespaces}
    """
    def __str__(self):
        s = "Invalid OpenID Namespace"
        if self.args:
            s += " %r" % (self.args[0],)
        return s


# Sentinel used for Message implementation to indicate that getArg
# should raise an exception instead of returning a default.
no_default = object()

# Global namespace / alias registration map.  See
# registerNamespaceAlias.
registered_aliases = {}

class NamespaceAliasRegistrationError(Exception):
    """
    Raised when an alias or namespace URI has already been registered.
    """
    pass

def registerNamespaceAlias(namespace_uri, alias):
    """
    Registers a (namespace URI, alias) mapping in a global namespace
    alias map.  Raises NamespaceAliasRegistrationError if either the
    namespace URI or alias has already been registered with a
    different value.  This function is required if you want to use a
    namespace with an OpenID 1 message.
    """
    global registered_aliases

    if registered_aliases.get(alias) == namespace_uri:
        return

    if namespace_uri in registered_aliases.values():
        raise NamespaceAliasRegistrationError, \
              'Namespace uri %r already registered' % (namespace_uri,)

    if alias in registered_aliases:
        raise NamespaceAliasRegistrationError, \
              'Alias %r already registered' % (alias,)

    registered_aliases[alias] = namespace_uri

class Message(object):
    """
    In the implementation of this object, None represents the global
    namespace as well as a namespace with no key.

    @cvar namespaces: A dictionary specifying specific
        namespace-URI to alias mappings that should be used when
        generating namespace aliases.

    @ivar ns_args: two-level dictionary of the values in this message,
        grouped by namespace URI. The first level is the namespace
        URI.
    """

    allowed_openid_namespaces = [OPENID1_NS, THE_OTHER_OPENID1_NS, OPENID2_NS]

    def __init__(self, openid_namespace=None):
        """Create an empty Message.

        @raises InvalidOpenIDNamespace: if openid_namespace is not in
            L{Message.allowed_openid_namespaces}
        """
        self.args = {}
        self.namespaces = NamespaceMap()
        if openid_namespace is None:
            self._openid_ns_uri = None
        else:
            implicit = openid_namespace in OPENID1_NAMESPACES
            self.setOpenIDNamespace(openid_namespace, implicit)

    def fromPostArgs(cls, args):
        """Construct a Message containing a set of POST arguments.

        """
        self = cls()

        # Partition into "openid." args and bare args
        openid_args = {}
        for key, value in args.items():
            if isinstance(value, list):
                raise TypeError("query dict must have one value for each key, "
                                "not lists of values.  Query is %r" % (args,))


            try:
                prefix, rest = key.split('.', 1)
            except ValueError:
                prefix = None

            if prefix != 'openid':
                self.args[(BARE_NS, key)] = value
            else:
                openid_args[rest] = value

        self._fromOpenIDArgs(openid_args)

        return self

    fromPostArgs = classmethod(fromPostArgs)

    def fromOpenIDArgs(cls, openid_args):
        """Construct a Message from a parsed KVForm message.

        @raises InvalidOpenIDNamespace: if openid.ns is not in
            L{Message.allowed_openid_namespaces}
        """
        self = cls()
        self._fromOpenIDArgs(openid_args)
        return self

    fromOpenIDArgs = classmethod(fromOpenIDArgs)

    def _fromOpenIDArgs(self, openid_args):
        ns_args = []

        # Resolve namespaces
        for rest, value in openid_args.iteritems():
            try:
                ns_alias, ns_key = rest.split('.', 1)
            except ValueError:
                ns_alias = NULL_NAMESPACE
                ns_key = rest

            if ns_alias == 'ns':
                self.namespaces.addAlias(value, ns_key)
            elif ns_alias == NULL_NAMESPACE and ns_key == 'ns':
                # null namespace
                self.setOpenIDNamespace(value, False)
            else:
                ns_args.append((ns_alias, ns_key, value))

        # Implicitly set an OpenID namespace definition (OpenID 1)
        if not self.getOpenIDNamespace():
            self.setOpenIDNamespace(OPENID1_NS, True)

        # Actually put the pairs into the appropriate namespaces
        for (ns_alias, ns_key, value) in ns_args:
            ns_uri = self.namespaces.getNamespaceURI(ns_alias)
            if ns_uri is None:
                # we found a namespaced arg without a namespace URI defined
                ns_uri = self._getDefaultNamespace(ns_alias)
                if ns_uri is None:
                    ns_uri = self.getOpenIDNamespace()
                    ns_key = '%s.%s' % (ns_alias, ns_key)
                else:
                    self.namespaces.addAlias(ns_uri, ns_alias, implicit=True)

            self.setArg(ns_uri, ns_key, value)

    def _getDefaultNamespace(self, mystery_alias):
        """OpenID 1 compatibility: look for a default namespace URI to
        use for this alias."""
        global registered_aliases
        # Only try to map an alias to a default if it's an
        # OpenID 1.x message.
        if self.isOpenID1():
            return registered_aliases.get(mystery_alias)
        else:
            return None

    def setOpenIDNamespace(self, openid_ns_uri, implicit):
        """Set the OpenID namespace URI used in this message.

        @raises InvalidOpenIDNamespace: if the namespace is not in
            L{Message.allowed_openid_namespaces}
        """
        if openid_ns_uri not in self.allowed_openid_namespaces:
            raise InvalidOpenIDNamespace(openid_ns_uri)

        self.namespaces.addAlias(openid_ns_uri, NULL_NAMESPACE, implicit)
        self._openid_ns_uri = openid_ns_uri

    def getOpenIDNamespace(self):
        return self._openid_ns_uri

    def isOpenID1(self):
        return self.getOpenIDNamespace() in OPENID1_NAMESPACES

    def isOpenID2(self):
        return self.getOpenIDNamespace() == OPENID2_NS

    def fromKVForm(cls, kvform_string):
        """Create a Message from a KVForm string"""
        return cls.fromOpenIDArgs(kvform.kvToDict(kvform_string))

    fromKVForm = classmethod(fromKVForm)

    def copy(self):
        return copy.deepcopy(self)

    def toPostArgs(self):
        """Return all arguments with openid. in front of namespaced arguments.
        """
        args = {}

        # Add namespace definitions to the output
        for ns_uri, alias in self.namespaces.iteritems():
            if self.namespaces.isImplicit(ns_uri):
                continue
            if alias == NULL_NAMESPACE:
                ns_key = 'openid.ns'
            else:
                ns_key = 'openid.ns.' + alias
            args[ns_key] = oidutil.toUnicode(ns_uri).encode('UTF-8')

        for (ns_uri, ns_key), value in self.args.iteritems():
            key = self.getKey(ns_uri, ns_key)
            # Ensure the resulting value is an UTF-8 encoded bytestring.
            args[key] = oidutil.toUnicode(value).encode('UTF-8')

        return args

    def toArgs(self):
        """Return all namespaced arguments, failing if any
        non-namespaced arguments exist."""
        # FIXME - undocumented exception
        post_args = self.toPostArgs()
        kvargs = {}
        for k, v in post_args.iteritems():
            if not k.startswith('openid.'):
                raise ValueError(
                    'This message can only be encoded as a POST, because it '
                    'contains arguments that are not prefixed with "openid."')
            else:
                kvargs[k[7:]] = v

        return kvargs

    def toFormMarkup(self, action_url, form_tag_attrs=None,
                     submit_text=u"Continue"):
        """Generate HTML form markup that contains the values in this
        message, to be HTTP POSTed as x-www-form-urlencoded UTF-8.

        @param action_url: The URL to which the form will be POSTed
        @type action_url: str

        @param form_tag_attrs: Dictionary of attributes to be added to
            the form tag. 'accept-charset' and 'enctype' have defaults
            that can be overridden. If a value is supplied for
            'action' or 'method', it will be replaced.
        @type form_tag_attrs: {unicode: unicode}

        @param submit_text: The text that will appear on the submit
            button for this form.
        @type submit_text: unicode

        @returns: A string containing (X)HTML markup for a form that
            encodes the values in this Message object.
        @rtype: str or unicode
        """
        if ElementTree is None:
            raise RuntimeError('This function requires ElementTree.')

        assert action_url is not None

        form = ElementTree.Element(u'form')

        if form_tag_attrs:
            for name, attr in form_tag_attrs.iteritems():
                form.attrib[name] = attr

        form.attrib[u'action'] = oidutil.toUnicode(action_url)
        form.attrib[u'method'] = u'post'
        form.attrib[u'accept-charset'] = u'UTF-8'
        form.attrib[u'enctype'] = u'application/x-www-form-urlencoded'

        for name, value in self.toPostArgs().iteritems():
            attrs = {u'type': u'hidden',
                     u'name': oidutil.toUnicode(name),
                     u'value': oidutil.toUnicode(value)}
            form.append(ElementTree.Element(u'input', attrs))

        submit = ElementTree.Element(u'input',
            {u'type':'submit', u'value':oidutil.toUnicode(submit_text)})
        form.append(submit)

        return ElementTree.tostring(form, encoding='utf-8')

    def toURL(self, base_url):
        """Generate a GET URL with the parameters in this message
        attached as query parameters."""
        return oidutil.appendArgs(base_url, self.toPostArgs())

    def toKVForm(self):
        """Generate a KVForm string that contains the parameters in
        this message. This will fail if the message contains arguments
        outside of the 'openid.' prefix.
        """
        return kvform.dictToKV(self.toArgs())

    def toURLEncoded(self):
        """Generate an x-www-urlencoded string"""
        args = self.toPostArgs().items()
        args.sort()
        return urllib.urlencode(args)

    def _fixNS(self, namespace):
        """Convert an input value into the internally used values of
        this object

        @param namespace: The string or constant to convert
        @type namespace: str or unicode or BARE_NS or OPENID_NS
        """
        if namespace == OPENID_NS:
            if self._openid_ns_uri is None:
                raise UndefinedOpenIDNamespace('OpenID namespace not set')
            else:
                namespace = self._openid_ns_uri

        if namespace != BARE_NS and type(namespace) not in [str, unicode]:
            raise TypeError(
                "Namespace must be BARE_NS, OPENID_NS or a string. got %r"
                % (namespace,))

        if namespace != BARE_NS and ':' not in namespace:
            fmt = 'OpenID 2.0 namespace identifiers SHOULD be URIs. Got %r'
            warnings.warn(fmt % (namespace,), DeprecationWarning)

            if namespace == 'sreg':
                fmt = 'Using %r instead of "sreg" as namespace'
                warnings.warn(fmt % (SREG_URI,), DeprecationWarning,)
                return SREG_URI

        return namespace

    def hasKey(self, namespace, ns_key):
        namespace = self._fixNS(namespace)
        return (namespace, ns_key) in self.args

    def getKey(self, namespace, ns_key):
        """Get the key for a particular namespaced argument"""
        namespace = self._fixNS(namespace)
        if namespace == BARE_NS:
            return ns_key

        ns_alias = self.namespaces.getAlias(namespace)

        # No alias is defined, so no key can exist
        if ns_alias is None:
            return None

        if ns_alias == NULL_NAMESPACE:
            tail = ns_key
        else:
            tail = '%s.%s' % (ns_alias, ns_key)

        return 'openid.' + tail

    def getArg(self, namespace, key, default=None):
        """Get a value for a namespaced key.

        @param namespace: The namespace in the message for this key
        @type namespace: str

        @param key: The key to get within this namespace
        @type key: str

        @param default: The value to use if this key is absent from
            this message. Using the special value
            openid.message.no_default will result in this method
            raising a KeyError instead of returning the default.

        @rtype: str or the type of default
        @raises KeyError: if default is no_default
        @raises UndefinedOpenIDNamespace: if the message has not yet
            had an OpenID namespace set
        """
        namespace = self._fixNS(namespace)
        args_key = (namespace, key)
        try:
            return self.args[args_key]
        except KeyError:
            if default is no_default:
                raise KeyError((namespace, key))
            else:
                return default

    def getArgs(self, namespace):
        """Get the arguments that are defined for this namespace URI

        @returns: mapping from namespaced keys to values
        @returntype: dict
        """
        namespace = self._fixNS(namespace)
        return dict([
            (ns_key, value)
            for ((pair_ns, ns_key), value)
            in self.args.iteritems()
            if pair_ns == namespace
            ])

    def updateArgs(self, namespace, updates):
        """Set multiple key/value pairs in one call

        @param updates: The values to set
        @type updates: {unicode:unicode}
        """
        namespace = self._fixNS(namespace)
        for k, v in updates.iteritems():
            self.setArg(namespace, k, v)

    def setArg(self, namespace, key, value):
        """Set a single argument in this namespace"""
        assert key is not None
        assert value is not None
        namespace = self._fixNS(namespace)
        self.args[(namespace, key)] = value
        if not (namespace is BARE_NS):
            self.namespaces.add(namespace)

    def delArg(self, namespace, key):
        namespace = self._fixNS(namespace)
        del self.args[(namespace, key)]

    def __repr__(self):
        return "<%s.%s %r>" % (self.__class__.__module__,
                               self.__class__.__name__,
                               self.args)

    def __eq__(self, other):
        return self.args == other.args


    def __ne__(self, other):
        return not (self == other)


    def getAliasedArg(self, aliased_key, default=None):
        if aliased_key == 'ns':
            return self.getOpenIDNamespace()

        if aliased_key.startswith('ns.'):
            uri = self.namespaces.getNamespaceURI(aliased_key[3:])
            if uri is None:
                if default == no_default:
                    raise KeyError
                else:
                    return default
            else:
                return uri

        try:
            alias, key = aliased_key.split('.', 1)
        except ValueError:
            # need more than x values to unpack
            ns = None
        else:
            ns = self.namespaces.getNamespaceURI(alias)

        if ns is None:
            key = aliased_key
            ns = self.getOpenIDNamespace()

        return self.getArg(ns, key, default)

class NamespaceMap(object):
    """Maintains a bijective map between namespace uris and aliases.
    """
    def __init__(self):
        self.alias_to_namespace = {}
        self.namespace_to_alias = {}
        self.implicit_namespaces = []

    def getAlias(self, namespace_uri):
        return self.namespace_to_alias.get(namespace_uri)

    def getNamespaceURI(self, alias):
        return self.alias_to_namespace.get(alias)

    def iterNamespaceURIs(self):
        """Return an iterator over the namespace URIs"""
        return iter(self.namespace_to_alias)

    def iterAliases(self):
        """Return an iterator over the aliases"""
        return iter(self.alias_to_namespace)

    def iteritems(self):
        """Iterate over the mapping

        @returns: iterator of (namespace_uri, alias)
        """
        return self.namespace_to_alias.iteritems()

    def addAlias(self, namespace_uri, desired_alias, implicit=False):
        """Add an alias from this namespace URI to the desired alias
        """
        # Check that desired_alias is not an openid protocol field as
        # per the spec.
        assert desired_alias not in OPENID_PROTOCOL_FIELDS, \
               "%r is not an allowed namespace alias" % (desired_alias,)

        # Check that desired_alias does not contain a period as per
        # the spec.
        if type(desired_alias) in [str, unicode]:
            assert '.' not in desired_alias, \
                   "%r must not contain a dot" % (desired_alias,)

        # Check that there is not a namespace already defined for
        # the desired alias
        current_namespace_uri = self.alias_to_namespace.get(desired_alias)
        if (current_namespace_uri is not None
            and current_namespace_uri != namespace_uri):

            fmt = ('Cannot map %r to alias %r. '
                   '%r is already mapped to alias %r')

            msg = fmt % (
                namespace_uri,
                desired_alias,
                current_namespace_uri,
                desired_alias)
            raise KeyError(msg)

        # Check that there is not already a (different) alias for
        # this namespace URI
        alias = self.namespace_to_alias.get(namespace_uri)
        if alias is not None and alias != desired_alias:
            fmt = ('Cannot map %r to alias %r. '
                   'It is already mapped to alias %r')
            raise KeyError(fmt % (namespace_uri, desired_alias, alias))

        assert (desired_alias == NULL_NAMESPACE or
                type(desired_alias) in [str, unicode]), repr(desired_alias)
        assert namespace_uri not in self.implicit_namespaces
        self.alias_to_namespace[desired_alias] = namespace_uri
        self.namespace_to_alias[namespace_uri] = desired_alias
        if implicit:
            self.implicit_namespaces.append(namespace_uri)
        return desired_alias

    def add(self, namespace_uri):
        """Add this namespace URI to the mapping, without caring what
        alias it ends up with"""
        # See if this namespace is already mapped to an alias
        alias = self.namespace_to_alias.get(namespace_uri)
        if alias is not None:
            return alias

        # Fall back to generating a numerical alias
        i = 0
        while True:
            alias = 'ext' + str(i)
            try:
                self.addAlias(namespace_uri, alias)
            except KeyError:
                i += 1
            else:
                return alias

        assert False, "Not reached"

    def isDefined(self, namespace_uri):
        return namespace_uri in self.namespace_to_alias

    def __contains__(self, namespace_uri):
        return self.isDefined(namespace_uri)

    def isImplicit(self, namespace_uri):
        return namespace_uri in self.implicit_namespaces

########NEW FILE########
__FILENAME__ = oidutil
"""This module contains general utility code that is used throughout
the library.

For users of this library, the C{L{log}} function is probably the most
interesting.
"""

__all__ = ['log', 'appendArgs', 'toBase64', 'fromBase64', 'autoSubmitHTML', 'toUnicode']

import binascii
import sys
import urlparse
import logging

from urllib import urlencode

elementtree_modules = [
    'lxml.etree',
    'xml.etree.cElementTree',
    'xml.etree.ElementTree',
    'cElementTree',
    'elementtree.ElementTree',
    ]

def toUnicode(value):
    """Returns the given argument as a unicode object.

    @param value: A UTF-8 encoded string or a unicode (coercable) object
    @type message: str or unicode

    @returns: Unicode object representing the input value.
    """
    if isinstance(value, str):
        return value.decode('utf-8')
    return unicode(value)

def autoSubmitHTML(form, title='OpenID transaction in progress'):
    return """
<html>
<head>
  <title>%s</title>
</head>
<body onload="document.forms[0].submit();">
%s
<script>
var elements = document.forms[0].elements;
for (var i = 0; i < elements.length; i++) {
  elements[i].style.display = "none";
}
</script>
</body>
</html>
""" % (title, form)

def importElementTree(module_names=None):
    """Find a working ElementTree implementation, trying the standard
    places that such a thing might show up.

    >>> ElementTree = importElementTree()

    @param module_names: The names of modules to try to use as
        ElementTree. Defaults to C{L{elementtree_modules}}

    @returns: An ElementTree module
    """
    if module_names is None:
        module_names = elementtree_modules

    for mod_name in module_names:
        try:
            ElementTree = __import__(mod_name, None, None, ['unused'])
        except ImportError:
            pass
        else:
            # Make sure it can actually parse XML
            try:
                ElementTree.XML('<unused/>')
            except (SystemExit, MemoryError, AssertionError):
                raise
            except:
                logging.exception('Not using ElementTree library %r because it failed to '
                    'parse a trivial document: %s' % mod_name)
            else:
                return ElementTree
    else:
        raise ImportError('No ElementTree library found. '
                          'You may need to install one. '
                          'Tried importing %r' % (module_names,)
                          )

def log(message, level=0):
    """Handle a log message from the OpenID library.

    This is a legacy function which redirects to logging.error.
    The logging module should be used instead of this

    @param message: A string containing a debugging message from the
        OpenID library
    @type message: str

    @param level: The severity of the log message. This parameter is
        currently unused, but in the future, the library may indicate
        more important information with a higher level value.
    @type level: int or None

    @returns: Nothing.
    """

    logging.error("This is a legacy log message, please use the "
      "logging module. Message: %s", message)

def appendArgs(url, args):
    """Append query arguments to a HTTP(s) URL. If the URL already has
    query arguemtns, these arguments will be added, and the existing
    arguments will be preserved. Duplicate arguments will not be
    detected or collapsed (both will appear in the output).

    @param url: The url to which the arguments will be appended
    @type url: str

    @param args: The query arguments to add to the URL. If a
        dictionary is passed, the items will be sorted before
        appending them to the URL. If a sequence of pairs is passed,
        the order of the sequence will be preserved.
    @type args: A dictionary from string to string, or a sequence of
        pairs of strings.

    @returns: The URL with the parameters added
    @rtype: str
    """
    if hasattr(args, 'items'):
        args = args.items()
        args.sort()
    else:
        args = list(args)

    if len(args) == 0:
        return url

    if '?' in url:
        sep = '&'
    else:
        sep = '?'

    # Map unicode to UTF-8 if present. Do not make any assumptions
    # about the encodings of plain bytes (str).
    i = 0
    for k, v in args:
        if type(k) is not str:
            k = k.encode('UTF-8')

        if type(v) is not str:
            v = v.encode('UTF-8')

        args[i] = (k, v)
        i += 1

    return '%s%s%s' % (url, sep, urlencode(args))

def toBase64(s):
    """Represent string s as base64, omitting newlines"""
    return binascii.b2a_base64(s)[:-1]

def fromBase64(s):
    try:
        return binascii.a2b_base64(s)
    except binascii.Error, why:
        # Convert to a common exception type
        raise ValueError(why[0])

class Symbol(object):
    """This class implements an object that compares equal to others
    of the same type that have the same name. These are distict from
    str or unicode objects.
    """

    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return type(self) is type(other) and self.name == other.name

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash((self.__class__, self.name))
   
    def __repr__(self):
        return '<Symbol %s>' % (self.name,)

########NEW FILE########
__FILENAME__ = server
# -*- test-case-name: openid.test.test_server -*-
"""OpenID server protocol and logic.

Overview
========

    An OpenID server must perform three tasks:

        1. Examine the incoming request to determine its nature and validity.

        2. Make a decision about how to respond to this request.

        3. Format the response according to the protocol.

    The first and last of these tasks may performed by
    the L{decodeRequest<Server.decodeRequest>} and
    L{encodeResponse<Server.encodeResponse>} methods of the
    L{Server} object.  Who gets to do the intermediate task -- deciding
    how to respond to the request -- will depend on what type of request it
    is.

    If it's a request to authenticate a user (a X{C{checkid_setup}} or
    X{C{checkid_immediate}} request), you need to decide if you will assert
    that this user may claim the identity in question.  Exactly how you do
    that is a matter of application policy, but it generally involves making
    sure the user has an account with your system and is logged in, checking
    to see if that identity is hers to claim, and verifying with the user that
    she does consent to releasing that information to the party making the
    request.

    Examine the properties of the L{CheckIDRequest} object, optionally
    check L{CheckIDRequest.returnToVerified}, and and when you've come
    to a decision, form a response by calling L{CheckIDRequest.answer}.

    Other types of requests relate to establishing associations between client
    and server and verifying the authenticity of previous communications.
    L{Server} contains all the logic and data necessary to respond to
    such requests; just pass the request to L{Server.handleRequest}.


OpenID Extensions
=================

    Do you want to provide other information for your users
    in addition to authentication?  Version 2.0 of the OpenID
    protocol allows consumers to add extensions to their requests.
    For example, with sites using the U{Simple Registration
    Extension<http://openid.net/specs/openid-simple-registration-extension-1_0.html>},
    a user can agree to have their nickname and e-mail address sent to a
    site when they sign up.

    Since extensions do not change the way OpenID authentication works,
    code to handle extension requests may be completely separate from the
    L{OpenIDRequest} class here.  But you'll likely want data sent back by
    your extension to be signed.  L{OpenIDResponse} provides methods with
    which you can add data to it which can be signed with the other data in
    the OpenID signature.

    For example::

        # when request is a checkid_* request
        response = request.answer(True)
        # this will a signed 'openid.sreg.timezone' parameter to the response
        # as well as a namespace declaration for the openid.sreg namespace
        response.fields.setArg('http://openid.net/sreg/1.0', 'timezone', 'America/Los_Angeles')

    There are helper modules for a number of extensions, including
    L{Attribute Exchange<openid.extensions.ax>},
    L{PAPE<openid.extensions.pape>}, and
    L{Simple Registration<openid.extensions.sreg>} in the L{openid.extensions}
    package.

Stores
======

    The OpenID server needs to maintain state between requests in order
    to function.  Its mechanism for doing this is called a store.  The
    store interface is defined in C{L{openid.store.interface.OpenIDStore}}.
    Additionally, several concrete store implementations are provided, so that
    most sites won't need to implement a custom store.  For a store backed
    by flat files on disk, see C{L{openid.store.filestore.FileOpenIDStore}}.
    For stores based on MySQL or SQLite, see the C{L{openid.store.sqlstore}}
    module.


Upgrading
=========

From 1.0 to 1.1
---------------

    The keys by which a server looks up associations in its store have changed
    in version 1.2 of this library.  If your store has entries created from
    version 1.0 code, you should empty it.

From 1.1 to 2.0
---------------

    One of the additions to the OpenID protocol was a specified nonce
    format for one-way nonces.  As a result, the nonce table in the store
    has changed.  You'll need to run contrib/upgrade-store-1.1-to-2.0 to
    upgrade your store, or you'll encounter errors about the wrong number
    of columns in the oid_nonces table.

    If you've written your own custom store or code that interacts
    directly with it, you'll need to review the change notes in
    L{openid.store.interface}.

@group Requests: OpenIDRequest, AssociateRequest, CheckIDRequest,
    CheckAuthRequest

@group Responses: OpenIDResponse

@group HTTP Codes: HTTP_OK, HTTP_REDIRECT, HTTP_ERROR

@group Response Encodings: ENCODE_KVFORM, ENCODE_HTML_FORM, ENCODE_URL
"""

import time, warnings
import logging
from copy import deepcopy

from openid import cryptutil
from openid import oidutil
from openid import kvform
from openid.dh import DiffieHellman
from openid.store.nonce import mkNonce
from openid.server.trustroot import TrustRoot, verifyReturnTo
from openid.association import Association, default_negotiator, getSecretSize
from openid.message import Message, InvalidOpenIDNamespace, \
     OPENID_NS, OPENID2_NS, IDENTIFIER_SELECT, OPENID1_URL_LIMIT
from openid.urinorm import urinorm

HTTP_OK = 200
HTTP_REDIRECT = 302
HTTP_ERROR = 400

BROWSER_REQUEST_MODES = ['checkid_setup', 'checkid_immediate']

ENCODE_KVFORM = ('kvform',)
ENCODE_URL = ('URL/redirect',)
ENCODE_HTML_FORM = ('HTML form',)

UNUSED = None

class OpenIDRequest(object):
    """I represent an incoming OpenID request.

    @cvar mode: the C{X{openid.mode}} of this request.
    @type mode: str
    """
    mode = None


class CheckAuthRequest(OpenIDRequest):
    """A request to verify the validity of a previous response.

    @cvar mode: "X{C{check_authentication}}"
    @type mode: str

    @ivar assoc_handle: The X{association handle} the response was signed with.
    @type assoc_handle: str
    @ivar signed: The message with the signature which wants checking.
    @type signed: L{Message}

    @ivar invalidate_handle: An X{association handle} the client is asking
        about the validity of.  Optional, may be C{None}.
    @type invalidate_handle: str

    @see: U{OpenID Specs, Mode: check_authentication
        <http://openid.net/specs.bml#mode-check_authentication>}
    """
    mode = "check_authentication"

    required_fields = ["identity", "return_to", "response_nonce"]

    def __init__(self, assoc_handle, signed, invalidate_handle=None):
        """Construct me.

        These parameters are assigned directly as class attributes, see
        my L{class documentation<CheckAuthRequest>} for their descriptions.

        @type assoc_handle: str
        @type signed: L{Message}
        @type invalidate_handle: str
        """
        self.assoc_handle = assoc_handle
        self.signed = signed
        self.invalidate_handle = invalidate_handle
        self.namespace = OPENID2_NS


    def fromMessage(klass, message, op_endpoint=UNUSED):
        """Construct me from an OpenID Message.

        @param message: An OpenID check_authentication Message
        @type message: L{openid.message.Message}

        @returntype: L{CheckAuthRequest}
        """
        self = klass.__new__(klass)
        self.message = message
        self.namespace = message.getOpenIDNamespace()
        self.assoc_handle = message.getArg(OPENID_NS, 'assoc_handle')
        self.sig = message.getArg(OPENID_NS, 'sig')

        if (self.assoc_handle is None or
            self.sig is None):
            fmt = "%s request missing required parameter from message %s"
            raise ProtocolError(
                message, text=fmt % (self.mode, message))

        self.invalidate_handle = message.getArg(OPENID_NS, 'invalidate_handle')

        self.signed = message.copy()
        # openid.mode is currently check_authentication because
        # that's the mode of this request.  But the signature
        # was made on something with a different openid.mode.
        # http://article.gmane.org/gmane.comp.web.openid.general/537
        if self.signed.hasKey(OPENID_NS, "mode"):
            self.signed.setArg(OPENID_NS, "mode", "id_res")

        return self

    fromMessage = classmethod(fromMessage)

    def answer(self, signatory):
        """Respond to this request.

        Given a L{Signatory}, I can check the validity of the signature and
        the X{C{invalidate_handle}}.

        @param signatory: The L{Signatory} to use to check the signature.
        @type signatory: L{Signatory}

        @returns: A response with an X{C{is_valid}} (and, if
           appropriate X{C{invalidate_handle}}) field.
        @returntype: L{OpenIDResponse}
        """
        is_valid = signatory.verify(self.assoc_handle, self.signed)
        # Now invalidate that assoc_handle so it this checkAuth message cannot
        # be replayed.
        signatory.invalidate(self.assoc_handle, dumb=True)
        response = OpenIDResponse(self)
        valid_str = (is_valid and "true") or "false"
        response.fields.setArg(OPENID_NS, 'is_valid', valid_str)

        if self.invalidate_handle:
            assoc = signatory.getAssociation(self.invalidate_handle, dumb=False)
            if not assoc:
                response.fields.setArg(
                    OPENID_NS, 'invalidate_handle', self.invalidate_handle)
        return response


    def __str__(self):
        if self.invalidate_handle:
            ih = " invalidate? %r" % (self.invalidate_handle,)
        else:
            ih = ""
        s = "<%s handle: %r sig: %r: signed: %r%s>" % (
            self.__class__.__name__, self.assoc_handle,
            self.sig, self.signed, ih)
        return s


class PlainTextServerSession(object):
    """An object that knows how to handle association requests with no
    session type.

    @cvar session_type: The session_type for this association
        session. There is no type defined for plain-text in the OpenID
        specification, so we use 'no-encryption'.
    @type session_type: str

    @see: U{OpenID Specs, Mode: associate
        <http://openid.net/specs.bml#mode-associate>}
    @see: AssociateRequest
    """
    session_type = 'no-encryption'
    allowed_assoc_types = ['HMAC-SHA1', 'HMAC-SHA256']

    def fromMessage(cls, unused_request):
        return cls()

    fromMessage = classmethod(fromMessage)

    def answer(self, secret):
        return {'mac_key': oidutil.toBase64(secret)}


class DiffieHellmanSHA1ServerSession(object):
    """An object that knows how to handle association requests with the
    Diffie-Hellman session type.

    @cvar session_type: The session_type for this association
        session.
    @type session_type: str

    @ivar dh: The Diffie-Hellman algorithm values for this request
    @type dh: DiffieHellman

    @ivar consumer_pubkey: The public key sent by the consumer in the
        associate request
    @type consumer_pubkey: long

    @see: U{OpenID Specs, Mode: associate
        <http://openid.net/specs.bml#mode-associate>}
    @see: AssociateRequest
    """
    session_type = 'DH-SHA1'
    hash_func = staticmethod(cryptutil.sha1)
    allowed_assoc_types = ['HMAC-SHA1']

    def __init__(self, dh, consumer_pubkey):
        self.dh = dh
        self.consumer_pubkey = consumer_pubkey

    def fromMessage(cls, message):
        """
        @param message: The associate request message
        @type message: openid.message.Message

        @returntype: L{DiffieHellmanSHA1ServerSession}

        @raises ProtocolError: When parameters required to establish the
            session are missing.
        """
        dh_modulus = message.getArg(OPENID_NS, 'dh_modulus')
        dh_gen = message.getArg(OPENID_NS, 'dh_gen')
        if (dh_modulus is None and dh_gen is not None or
            dh_gen is None and dh_modulus is not None):

            if dh_modulus is None:
                missing = 'modulus'
            else:
                missing = 'generator'

            raise ProtocolError(message,
                                'If non-default modulus or generator is '
                                'supplied, both must be supplied. Missing %s'
                                % (missing,))

        if dh_modulus or dh_gen:
            dh_modulus = cryptutil.base64ToLong(dh_modulus)
            dh_gen = cryptutil.base64ToLong(dh_gen)
            dh = DiffieHellman(dh_modulus, dh_gen)
        else:
            dh = DiffieHellman.fromDefaults()

        consumer_pubkey = message.getArg(OPENID_NS, 'dh_consumer_public')
        if consumer_pubkey is None:
            raise ProtocolError(message, "Public key for DH-SHA1 session "
                                "not found in message %s" % (message,))

        consumer_pubkey = cryptutil.base64ToLong(consumer_pubkey)

        return cls(dh, consumer_pubkey)

    fromMessage = classmethod(fromMessage)

    def answer(self, secret):
        mac_key = self.dh.xorSecret(self.consumer_pubkey,
                                    secret,
                                    self.hash_func)
        return {
            'dh_server_public': cryptutil.longToBase64(self.dh.public),
            'enc_mac_key': oidutil.toBase64(mac_key),
            }

class DiffieHellmanSHA256ServerSession(DiffieHellmanSHA1ServerSession):
    session_type = 'DH-SHA256'
    hash_func = staticmethod(cryptutil.sha256)
    allowed_assoc_types = ['HMAC-SHA256']

class AssociateRequest(OpenIDRequest):
    """A request to establish an X{association}.

    @cvar mode: "X{C{check_authentication}}"
    @type mode: str

    @ivar assoc_type: The type of association.  The protocol currently only
        defines one value for this, "X{C{HMAC-SHA1}}".
    @type assoc_type: str

    @ivar session: An object that knows how to handle association
        requests of a certain type.

    @see: U{OpenID Specs, Mode: associate
        <http://openid.net/specs.bml#mode-associate>}
    """

    mode = "associate"

    session_classes = {
        'no-encryption': PlainTextServerSession,
        'DH-SHA1': DiffieHellmanSHA1ServerSession,
        'DH-SHA256': DiffieHellmanSHA256ServerSession,
        }

    def __init__(self, session, assoc_type):
        """Construct me.

        The session is assigned directly as a class attribute. See my
        L{class documentation<AssociateRequest>} for its description.
        """
        super(AssociateRequest, self).__init__()
        self.session = session
        self.assoc_type = assoc_type
        self.namespace = OPENID2_NS


    def fromMessage(klass, message, op_endpoint=UNUSED):
        """Construct me from an OpenID Message.

        @param message: The OpenID associate request
        @type message: openid.message.Message

        @returntype: L{AssociateRequest}
        """
        if message.isOpenID1():
            session_type = message.getArg(OPENID_NS, 'session_type')
            if session_type == 'no-encryption':
                logging.warn('Received OpenID 1 request with a no-encryption '
                            'assocaition session type. Continuing anyway.')
            elif not session_type:
                session_type = 'no-encryption'
        else:
            session_type = message.getArg(OPENID2_NS, 'session_type')
            if session_type is None:
                raise ProtocolError(message,
                                    text="session_type missing from request")

        try:
            session_class = klass.session_classes[session_type]
        except KeyError:
            raise ProtocolError(message,
                                "Unknown session type %r" % (session_type,))

        try:
            session = session_class.fromMessage(message)
        except ValueError, why:
            raise ProtocolError(message, 'Error parsing %s session: %s' %
                                (session_class.session_type, why[0]))

        assoc_type = message.getArg(OPENID_NS, 'assoc_type', 'HMAC-SHA1')
        if assoc_type not in session.allowed_assoc_types:
            fmt = 'Session type %s does not support association type %s'
            raise ProtocolError(message, fmt % (session_type, assoc_type))

        self = klass(session, assoc_type)
        self.message = message
        self.namespace = message.getOpenIDNamespace()
        return self

    fromMessage = classmethod(fromMessage)

    def answer(self, assoc):
        """Respond to this request with an X{association}.

        @param assoc: The association to send back.
        @type assoc: L{openid.association.Association}

        @returns: A response with the association information, encrypted
            to the consumer's X{public key} if appropriate.
        @returntype: L{OpenIDResponse}
        """
        response = OpenIDResponse(self)
        response.fields.updateArgs(OPENID_NS, {
            'expires_in': '%d' % (assoc.getExpiresIn(),),
            'assoc_type': self.assoc_type,
            'assoc_handle': assoc.handle,
            })
        response.fields.updateArgs(OPENID_NS,
                                   self.session.answer(assoc.secret))

        if not (self.session.session_type == 'no-encryption' and
                self.message.isOpenID1()):
            # The session type "no-encryption" did not have a name
            # in OpenID v1, it was just omitted.
            response.fields.setArg(
                OPENID_NS, 'session_type', self.session.session_type)

        return response

    def answerUnsupported(self, message, preferred_association_type=None,
                          preferred_session_type=None):
        """Respond to this request indicating that the association
        type or association session type is not supported."""
        if self.message.isOpenID1():
            raise ProtocolError(self.message)

        response = OpenIDResponse(self)
        response.fields.setArg(OPENID_NS, 'error_code', 'unsupported-type')
        response.fields.setArg(OPENID_NS, 'error', message)

        if preferred_association_type:
            response.fields.setArg(
                OPENID_NS, 'assoc_type', preferred_association_type)

        if preferred_session_type:
            response.fields.setArg(
                OPENID_NS, 'session_type', preferred_session_type)

        return response

class CheckIDRequest(OpenIDRequest):
    """A request to confirm the identity of a user.

    This class handles requests for openid modes X{C{checkid_immediate}}
    and X{C{checkid_setup}}.

    @cvar mode: "X{C{checkid_immediate}}" or "X{C{checkid_setup}}"
    @type mode: str

    @ivar immediate: Is this an immediate-mode request?
    @type immediate: bool

    @ivar identity: The OP-local identifier being checked.
    @type identity: str

    @ivar claimed_id: The claimed identifier.  Not present in OpenID 1.x
        messages.
    @type claimed_id: str

    @ivar trust_root: "Are you Frank?" asks the checkid request.  "Who wants
        to know?"  C{trust_root}, that's who.  This URL identifies the party
        making the request, and the user will use that to make her decision
        about what answer she trusts them to have.  Referred to as "realm" in
        OpenID 2.0.
    @type trust_root: str

    @ivar return_to: The URL to send the user agent back to to reply to this
        request.
    @type return_to: str

    @ivar assoc_handle: Provided in smart mode requests, a handle for a
        previously established association.  C{None} for dumb mode requests.
    @type assoc_handle: str
    """

    def __init__(self, identity, return_to, trust_root=None, immediate=False,
                 assoc_handle=None, op_endpoint=None, claimed_id=None):
        """Construct me.

        These parameters are assigned directly as class attributes, see
        my L{class documentation<CheckIDRequest>} for their descriptions.

        @raises MalformedReturnURL: When the C{return_to} URL is not a URL.
        """
        self.assoc_handle = assoc_handle
        self.identity = identity
        self.claimed_id = claimed_id or identity
        self.return_to = return_to
        self.trust_root = trust_root or return_to
        self.op_endpoint = op_endpoint
        assert self.op_endpoint is not None
        if immediate:
            self.immediate = True
            self.mode = "checkid_immediate"
        else:
            self.immediate = False
            self.mode = "checkid_setup"

        if self.return_to is not None and \
               not TrustRoot.parse(self.return_to):
            raise MalformedReturnURL(None, self.return_to)
        if not self.trustRootValid():
            raise UntrustedReturnURL(None, self.return_to, self.trust_root)
        self.message = None

    def _getNamespace(self):
        warnings.warn('The "namespace" attribute of CheckIDRequest objects '
                      'is deprecated. Use "message.getOpenIDNamespace()" '
                      'instead', DeprecationWarning, stacklevel=2)
        return self.message.getOpenIDNamespace()

    namespace = property(_getNamespace)

    def fromMessage(klass, message, op_endpoint):
        """Construct me from an OpenID message.

        @raises ProtocolError: When not all required parameters are present
            in the message.

        @raises MalformedReturnURL: When the C{return_to} URL is not a URL.

        @raises UntrustedReturnURL: When the C{return_to} URL is outside
            the C{trust_root}.

        @param message: An OpenID checkid_* request Message
        @type message: openid.message.Message

        @param op_endpoint: The endpoint URL of the server that this
            message was sent to.
        @type op_endpoint: str

        @returntype: L{CheckIDRequest}
        """
        self = klass.__new__(klass)
        self.message = message
        self.op_endpoint = op_endpoint
        mode = message.getArg(OPENID_NS, 'mode')
        if mode == "checkid_immediate":
            self.immediate = True
            self.mode = "checkid_immediate"
        else:
            self.immediate = False
            self.mode = "checkid_setup"

        self.return_to = message.getArg(OPENID_NS, 'return_to')
        if message.isOpenID1() and not self.return_to:
            fmt = "Missing required field 'return_to' from %r"
            raise ProtocolError(message, text=fmt % (message,))

        self.identity = message.getArg(OPENID_NS, 'identity')
        self.claimed_id = message.getArg(OPENID_NS, 'claimed_id')
        if message.isOpenID1():
            if self.identity is None:
                s = "OpenID 1 message did not contain openid.identity"
                raise ProtocolError(message, text=s)
        else:
            if self.identity and not self.claimed_id:
                s = ("OpenID 2.0 message contained openid.identity but not "
                     "claimed_id")
                raise ProtocolError(message, text=s)
            elif self.claimed_id and not self.identity:
                s = ("OpenID 2.0 message contained openid.claimed_id but not "
                     "identity")
                raise ProtocolError(message, text=s)

        # There's a case for making self.trust_root be a TrustRoot
        # here.  But if TrustRoot isn't currently part of the "public" API,
        # I'm not sure it's worth doing.

        if message.isOpenID1():
            trust_root_param = 'trust_root'
        else:
            trust_root_param = 'realm'

        # Using 'or' here is slightly different than sending a default
        # argument to getArg, as it will treat no value and an empty
        # string as equivalent.
        self.trust_root = (message.getArg(OPENID_NS, trust_root_param)
                           or self.return_to)

        if not message.isOpenID1():
            if self.return_to is self.trust_root is None:
                raise ProtocolError(message, "openid.realm required when " +
                                    "openid.return_to absent")

        self.assoc_handle = message.getArg(OPENID_NS, 'assoc_handle')

        # Using TrustRoot.parse here is a bit misleading, as we're not
        # parsing return_to as a trust root at all.  However, valid URLs
        # are valid trust roots, so we can use this to get an idea if it
        # is a valid URL.  Not all trust roots are valid return_to URLs,
        # however (particularly ones with wildcards), so this is still a
        # little sketchy.
        if self.return_to is not None and \
               not TrustRoot.parse(self.return_to):
            raise MalformedReturnURL(message, self.return_to)

        # I first thought that checking to see if the return_to is within
        # the trust_root is premature here, a logic-not-decoding thing.  But
        # it was argued that this is really part of data validation.  A
        # request with an invalid trust_root/return_to is broken regardless of
        # application, right?
        if not self.trustRootValid():
            raise UntrustedReturnURL(message, self.return_to, self.trust_root)

        return self

    fromMessage = classmethod(fromMessage)

    def idSelect(self):
        """Is the identifier to be selected by the IDP?

        @returntype: bool
        """
        # So IDPs don't have to import the constant
        return self.identity == IDENTIFIER_SELECT

    def trustRootValid(self):
        """Is my return_to under my trust_root?

        @returntype: bool
        """
        if not self.trust_root:
            return True
        tr = TrustRoot.parse(self.trust_root)
        if tr is None:
            raise MalformedTrustRoot(self.message, self.trust_root)

        if self.return_to is not None:
            return tr.validateURL(self.return_to)
        else:
            return True

    def returnToVerified(self):
        """Does the relying party publish the return_to URL for this
        response under the realm? It is up to the provider to set a
        policy for what kinds of realms should be allowed. This
        return_to URL verification reduces vulnerability to data-theft
        attacks based on open proxies, cross-site-scripting, or open
        redirectors.

        This check should only be performed after making sure that the
        return_to URL matches the realm.

        @see: L{trustRootValid}

        @raises openid.yadis.discover.DiscoveryFailure: if the realm
            URL does not support Yadis discovery (and so does not
            support the verification process).

        @raises openid.fetchers.HTTPFetchingError: if the realm URL
            is not reachable.  When this is the case, the RP may be hosted
            on the user's intranet.

        @returntype: bool

        @returns: True if the realm publishes a document with the
            return_to URL listed

        @since: 2.1.0
        """
        return verifyReturnTo(self.trust_root, self.return_to)

    def answer(self, allow, server_url=None, identity=None, claimed_id=None):
        """Respond to this request.

        @param allow: Allow this user to claim this identity, and allow the
            consumer to have this information?
        @type allow: bool

        @param server_url: DEPRECATED.  Passing C{op_endpoint} to the
            L{Server} constructor makes this optional.

            When an OpenID 1.x immediate mode request does not succeed,
            it gets back a URL where the request may be carried out
            in a not-so-immediate fashion.  Pass my URL in here (the
            fully qualified address of this server's endpoint, i.e.
            C{http://example.com/server}), and I will use it as a base for the
            URL for a new request.

            Optional for requests where C{CheckIDRequest.immediate} is C{False}
            or C{allow} is C{True}.

        @type server_url: str

        @param identity: The OP-local identifier to answer with.  Only for use
            when the relying party requested identifier selection.
        @type identity: str or None

        @param claimed_id: The claimed identifier to answer with, for use
            with identifier selection in the case where the claimed identifier
            and the OP-local identifier differ, i.e. when the claimed_id uses
            delegation.

            If C{identity} is provided but this is not, C{claimed_id} will
            default to the value of C{identity}.  When answering requests
            that did not ask for identifier selection, the response
            C{claimed_id} will default to that of the request.

            This parameter is new in OpenID 2.0.
        @type claimed_id: str or None

        @returntype: L{OpenIDResponse}

        @change: Version 2.0 deprecates C{server_url} and adds C{claimed_id}.

        @raises NoReturnError: when I do not have a return_to.
        """
        assert self.message is not None

        if not self.return_to:
            raise NoReturnToError

        if not server_url:
            if not self.message.isOpenID1() and not self.op_endpoint:
                # In other words, that warning I raised in Server.__init__?
                # You should pay attention to it now.
                raise RuntimeError("%s should be constructed with op_endpoint "
                                   "to respond to OpenID 2.0 messages." %
                                   (self,))
            server_url = self.op_endpoint

        if allow:
            mode = 'id_res'
        elif self.message.isOpenID1():
             if self.immediate:
                 mode = 'id_res'
             else:
                 mode = 'cancel'
        else:
            if self.immediate:
                mode = 'setup_needed'
            else:
                mode = 'cancel'

        response = OpenIDResponse(self)

        if claimed_id and self.message.isOpenID1():
            namespace = self.message.getOpenIDNamespace()
            raise VersionError("claimed_id is new in OpenID 2.0 and not "
                               "available for %s" % (namespace,))

        if allow:
            if self.identity == IDENTIFIER_SELECT:
                if not identity:
                    raise ValueError(
                        "This request uses IdP-driven identifier selection."
                        "You must supply an identifier in the response.")
                response_identity = identity
                response_claimed_id = claimed_id or identity

            elif self.identity:
                if identity and (self.identity != identity):
                    normalized_request_identity = urinorm(self.identity)
                    normalized_answer_identity = urinorm(identity)

                    if (normalized_request_identity !=
                        normalized_answer_identity):
                        raise ValueError(
                            "Request was for identity %r, cannot reply "
                            "with identity %r" % (self.identity, identity))

                # The "identity" value in the response shall always be
                # the same as that in the request, otherwise the RP is
                # likely to not validate the response.
                response_identity = self.identity
                response_claimed_id = self.claimed_id
            else:
                if identity:
                    raise ValueError(
                        "This request specified no identity and you "
                        "supplied %r" % (identity,))
                response_identity = None

            if self.message.isOpenID1() and response_identity is None:
                raise ValueError(
                    "Request was an OpenID 1 request, so response must "
                    "include an identifier."
                    )

            response.fields.updateArgs(OPENID_NS, {
                'mode': mode,
                'return_to': self.return_to,
                'response_nonce': mkNonce(),
                })

            if server_url:
                response.fields.setArg(OPENID_NS, 'op_endpoint', server_url)

            if response_identity is not None:
                response.fields.setArg(
                    OPENID_NS, 'identity', response_identity)
                if self.message.isOpenID2():
                    response.fields.setArg(
                        OPENID_NS, 'claimed_id', response_claimed_id)
        else:
            response.fields.setArg(OPENID_NS, 'mode', mode)
            if self.immediate:
                if self.message.isOpenID1() and not server_url:
                    raise ValueError("setup_url is required for allow=False "
                                     "in OpenID 1.x immediate mode.")
                # Make a new request just like me, but with immediate=False.
                setup_request = self.__class__(
                    self.identity, self.return_to, self.trust_root,
                    immediate=False, assoc_handle=self.assoc_handle,
                    op_endpoint=self.op_endpoint, claimed_id=self.claimed_id)

                # XXX: This API is weird.
                setup_request.message = self.message

                setup_url = setup_request.encodeToURL(server_url)
                response.fields.setArg(OPENID_NS, 'user_setup_url', setup_url)

        return response


    def encodeToURL(self, server_url):
        """Encode this request as a URL to GET.

        @param server_url: The URL of the OpenID server to make this request of.
        @type server_url: str

        @returntype: str

        @raises NoReturnError: when I do not have a return_to.
        """
        if not self.return_to:
            raise NoReturnToError

        # Imported from the alternate reality where these classes are used
        # in both the client and server code, so Requests are Encodable too.
        # That's right, code imported from alternate realities all for the
        # love of you, id_res/user_setup_url.
        q = {'mode': self.mode,
             'identity': self.identity,
             'claimed_id': self.claimed_id,
             'return_to': self.return_to}
        if self.trust_root:
            if self.message.isOpenID1():
                q['trust_root'] = self.trust_root
            else:
                q['realm'] = self.trust_root
        if self.assoc_handle:
            q['assoc_handle'] = self.assoc_handle

        response = Message(self.message.getOpenIDNamespace())
        response.updateArgs(OPENID_NS, q)
        return response.toURL(server_url)


    def getCancelURL(self):
        """Get the URL to cancel this request.

        Useful for creating a "Cancel" button on a web form so that operation
        can be carried out directly without another trip through the server.

        (Except you probably want to make another trip through the server so
        that it knows that the user did make a decision.  Or you could simulate
        this method by doing C{.answer(False).encodeToURL()})

        @returntype: str
        @returns: The return_to URL with openid.mode = cancel.

        @raises NoReturnError: when I do not have a return_to.
        """
        if not self.return_to:
            raise NoReturnToError

        if self.immediate:
            raise ValueError("Cancel is not an appropriate response to "
                             "immediate mode requests.")

        response = Message(self.message.getOpenIDNamespace())
        response.setArg(OPENID_NS, 'mode', 'cancel')
        return response.toURL(self.return_to)


    def __repr__(self):
        return '<%s id:%r im:%s tr:%r ah:%r>' % (self.__class__.__name__,
                                                 self.identity,
                                                 self.immediate,
                                                 self.trust_root,
                                                 self.assoc_handle)



class OpenIDResponse(object):
    """I am a response to an OpenID request.

    @ivar request: The request I respond to.
    @type request: L{OpenIDRequest}

    @ivar fields: My parameters as a dictionary with each key mapping to
        one value.  Keys are parameter names with no leading "C{openid.}".
        e.g.  "C{identity}" and "C{mac_key}", never "C{openid.identity}".
    @type fields: L{openid.message.Message}

    @ivar signed: The names of the fields which should be signed.
    @type signed: list of str
    """

    # Implementer's note: In a more symmetric client/server
    # implementation, there would be more types of OpenIDResponse
    # object and they would have validated attributes according to the
    # type of response.  But as it is, Response objects in a server are
    # basically write-only, their only job is to go out over the wire,
    # so this is just a loose wrapper around OpenIDResponse.fields.

    def __init__(self, request):
        """Make a response to an L{OpenIDRequest}.

        @type request: L{OpenIDRequest}
        """
        self.request = request
        self.fields = Message(request.namespace)

    def __str__(self):
        return "%s for %s: %s" % (
            self.__class__.__name__,
            self.request.__class__.__name__,
            self.fields)


    def toFormMarkup(self, form_tag_attrs=None):
        """Returns the form markup for this response.

        @param form_tag_attrs: Dictionary of attributes to be added to
            the form tag. 'accept-charset' and 'enctype' have defaults
            that can be overridden. If a value is supplied for
            'action' or 'method', it will be replaced.

        @returntype: str

        @since: 2.1.0
        """
        return self.fields.toFormMarkup(self.request.return_to,
                                        form_tag_attrs=form_tag_attrs)

    def toHTML(self, form_tag_attrs=None):
        """Returns an HTML document that auto-submits the form markup
        for this response.

        @returntype: str

        @see: toFormMarkup

        @since: 2.1.?
        """
        return oidutil.autoSubmitHTML(self.toFormMarkup(form_tag_attrs))

    def renderAsForm(self):
        """Returns True if this response's encoding is
        ENCODE_HTML_FORM.  Convenience method for server authors.

        @returntype: bool

        @since: 2.1.0
        """
        return self.whichEncoding() == ENCODE_HTML_FORM


    def needsSigning(self):
        """Does this response require signing?

        @returntype: bool
        """
        return self.fields.getArg(OPENID_NS, 'mode') == 'id_res'


    # implements IEncodable

    def whichEncoding(self):
        """How should I be encoded?

        @returns: one of ENCODE_URL, ENCODE_HTML_FORM, or ENCODE_KVFORM.

        @change: 2.1.0 added the ENCODE_HTML_FORM response.
        """
        if self.request.mode in BROWSER_REQUEST_MODES:
            if self.fields.isOpenID1() and \
               len(self.encodeToURL()) > OPENID1_URL_LIMIT:
                return ENCODE_HTML_FORM
            else:
                return ENCODE_URL
        else:
            return ENCODE_KVFORM


    def encodeToURL(self):
        """Encode a response as a URL for the user agent to GET.

        You will generally use this URL with a HTTP redirect.

        @returns: A URL to direct the user agent back to.
        @returntype: str
        """
        return self.fields.toURL(self.request.return_to)


    def addExtension(self, extension_response):
        """
        Add an extension response to this response message.

        @param extension_response: An object that implements the
            extension interface for adding arguments to an OpenID
            message.
        @type extension_response: L{openid.extension}

        @returntype: None
        """
        extension_response.toMessage(self.fields)


    def encodeToKVForm(self):
        """Encode a response in key-value colon/newline format.

        This is a machine-readable format used to respond to messages which
        came directly from the consumer and not through the user agent.

        @see: OpenID Specs,
           U{Key-Value Colon/Newline format<http://openid.net/specs.bml#keyvalue>}

        @returntype: str
        """
        return self.fields.toKVForm()



class WebResponse(object):
    """I am a response to an OpenID request in terms a web server understands.

    I generally come from an L{Encoder}, either directly or from
    L{Server.encodeResponse}.

    @ivar code: The HTTP code of this response.
    @type code: int

    @ivar headers: Headers to include in this response.
    @type headers: dict

    @ivar body: The body of this response.
    @type body: str
    """

    def __init__(self, code=HTTP_OK, headers=None, body=""):
        """Construct me.

        These parameters are assigned directly as class attributes, see
        my L{class documentation<WebResponse>} for their descriptions.
        """
        self.code = code
        if headers is not None:
            self.headers = headers
        else:
            self.headers = {}
        self.body = body



class Signatory(object):
    """I sign things.

    I also check signatures.

    All my state is encapsulated in an
    L{OpenIDStore<openid.store.interface.OpenIDStore>}, which means
    I'm not generally pickleable but I am easy to reconstruct.

    @cvar SECRET_LIFETIME: The number of seconds a secret remains valid.
    @type SECRET_LIFETIME: int
    """

    SECRET_LIFETIME = 14 * 24 * 60 * 60 # 14 days, in seconds

    # keys have a bogus server URL in them because the filestore
    # really does expect that key to be a URL.  This seems a little
    # silly for the server store, since I expect there to be only one
    # server URL.
    _normal_key = 'http://localhost/|normal'
    _dumb_key = 'http://localhost/|dumb'


    def __init__(self, store):
        """Create a new Signatory.

        @param store: The back-end where my associations are stored.
        @type store: L{openid.store.interface.OpenIDStore}
        """
        assert store is not None
        self.store = store


    def verify(self, assoc_handle, message):
        """Verify that the signature for some data is valid.

        @param assoc_handle: The handle of the association used to sign the
            data.
        @type assoc_handle: str

        @param message: The signed message to verify
        @type message: openid.message.Message

        @returns: C{True} if the signature is valid, C{False} if not.
        @returntype: bool
        """
        assoc = self.getAssociation(assoc_handle, dumb=True)
        if not assoc:
            logging.error("failed to get assoc with handle %r to verify "
                        "message %r"
                        % (assoc_handle, message))
            return False

        try:
            valid = assoc.checkMessageSignature(message)
        except ValueError, ex:
            logging.exception("Error in verifying %s with %s: %s" % (message,
                                                               assoc,
                                                               ex))
            return False
        return valid


    def sign(self, response):
        """Sign a response.

        I take a L{OpenIDResponse}, create a signature for everything
        in its L{signed<OpenIDResponse.signed>} list, and return a new
        copy of the response object with that signature included.

        @param response: A response to sign.
        @type response: L{OpenIDResponse}

        @returns: A signed copy of the response.
        @returntype: L{OpenIDResponse}
        """
        signed_response = deepcopy(response)
        assoc_handle = response.request.assoc_handle
        if assoc_handle:
            # normal mode
            # disabling expiration check because even if the association
            # is expired, we still need to know some properties of the
            # association so that we may preserve those properties when
            # creating the fallback association.
            assoc = self.getAssociation(assoc_handle, dumb=False,
                                        checkExpiration=False)

            if not assoc or assoc.expiresIn <= 0:
                # fall back to dumb mode
                signed_response.fields.setArg(
                    OPENID_NS, 'invalidate_handle', assoc_handle)
                assoc_type = assoc and assoc.assoc_type or 'HMAC-SHA1'
                if assoc and assoc.expiresIn <= 0:
                    # now do the clean-up that the disabled checkExpiration
                    # code didn't get to do.
                    self.invalidate(assoc_handle, dumb=False)
                assoc = self.createAssociation(dumb=True, assoc_type=assoc_type)
        else:
            # dumb mode.
            assoc = self.createAssociation(dumb=True)

        try:
            signed_response.fields = assoc.signMessage(signed_response.fields)
        except kvform.KVFormError, err:
            raise EncodingError(response, explanation=str(err))
        return signed_response


    def createAssociation(self, dumb=True, assoc_type='HMAC-SHA1'):
        """Make a new association.

        @param dumb: Is this association for a dumb-mode transaction?
        @type dumb: bool

        @param assoc_type: The type of association to create.  Currently
            there is only one type defined, C{HMAC-SHA1}.
        @type assoc_type: str

        @returns: the new association.
        @returntype: L{openid.association.Association}
        """
        secret = cryptutil.getBytes(getSecretSize(assoc_type))
        uniq = oidutil.toBase64(cryptutil.getBytes(4))
        handle = '{%s}{%x}{%s}' % (assoc_type, int(time.time()), uniq)

        assoc = Association.fromExpiresIn(
            self.SECRET_LIFETIME, handle, secret, assoc_type)

        if dumb:
            key = self._dumb_key
        else:
            key = self._normal_key
        self.store.storeAssociation(key, assoc)
        return assoc


    def getAssociation(self, assoc_handle, dumb, checkExpiration=True):
        """Get the association with the specified handle.

        @type assoc_handle: str

        @param dumb: Is this association used with dumb mode?
        @type dumb: bool

        @returns: the association, or None if no valid association with that
            handle was found.
        @returntype: L{openid.association.Association}
        """
        # Hmm.  We've created an interface that deals almost entirely with
        # assoc_handles.  The only place outside the Signatory that uses this
        # (and thus the only place that ever sees Association objects) is
        # when creating a response to an association request, as it must have
        # the association's secret.

        if assoc_handle is None:
            raise ValueError("assoc_handle must not be None")

        if dumb:
            key = self._dumb_key
        else:
            key = self._normal_key
        assoc = self.store.getAssociation(key, assoc_handle)
        if assoc is not None and assoc.expiresIn <= 0:
            logging.info("requested %sdumb key %r is expired (by %s seconds)" %
                        ((not dumb) and 'not-' or '',
                         assoc_handle, assoc.expiresIn))
            if checkExpiration:
                self.store.removeAssociation(key, assoc_handle)
                assoc = None
        return assoc


    def invalidate(self, assoc_handle, dumb):
        """Invalidates the association with the given handle.

        @type assoc_handle: str

        @param dumb: Is this association used with dumb mode?
        @type dumb: bool
        """
        if dumb:
            key = self._dumb_key
        else:
            key = self._normal_key
        self.store.removeAssociation(key, assoc_handle)



class Encoder(object):
    """I encode responses in to L{WebResponses<WebResponse>}.

    If you don't like L{WebResponses<WebResponse>}, you can do
    your own handling of L{OpenIDResponses<OpenIDResponse>} with
    L{OpenIDResponse.whichEncoding}, L{OpenIDResponse.encodeToURL}, and
    L{OpenIDResponse.encodeToKVForm}.
    """

    responseFactory = WebResponse


    def encode(self, response):
        """Encode a response to a L{WebResponse}.

        @raises EncodingError: When I can't figure out how to encode this
            message.
        """
        encode_as = response.whichEncoding()
        if encode_as == ENCODE_KVFORM:
            wr = self.responseFactory(body=response.encodeToKVForm())
            if isinstance(response, Exception):
                wr.code = HTTP_ERROR
        elif encode_as == ENCODE_URL:
            location = response.encodeToURL()
            wr = self.responseFactory(code=HTTP_REDIRECT,
                                      headers={'location': location})
        elif encode_as == ENCODE_HTML_FORM:
            wr = self.responseFactory(code=HTTP_OK,
                                      body=response.toHTML())
        else:
            # Can't encode this to a protocol message.  You should probably
            # render it to HTML and show it to the user.
            raise EncodingError(response)
        return wr



class SigningEncoder(Encoder):
    """I encode responses in to L{WebResponses<WebResponse>}, signing them when required.
    """

    def __init__(self, signatory):
        """Create a L{SigningEncoder}.

        @param signatory: The L{Signatory} I will make signatures with.
        @type signatory: L{Signatory}
        """
        self.signatory = signatory


    def encode(self, response):
        """Encode a response to a L{WebResponse}, signing it first if appropriate.

        @raises EncodingError: When I can't figure out how to encode this
            message.

        @raises AlreadySigned: When this response is already signed.

        @returntype: L{WebResponse}
        """
        # the isinstance is a bit of a kludge... it means there isn't really
        # an adapter to make the interfaces quite match.
        if (not isinstance(response, Exception)) and response.needsSigning():
            if not self.signatory:
                raise ValueError(
                    "Must have a store to sign this request: %s" %
                    (response,), response)
            if response.fields.hasKey(OPENID_NS, 'sig'):
                raise AlreadySigned(response)
            response = self.signatory.sign(response)
        return super(SigningEncoder, self).encode(response)



class Decoder(object):
    """I decode an incoming web request in to a L{OpenIDRequest}.
    """

    _handlers = {
        'checkid_setup': CheckIDRequest.fromMessage,
        'checkid_immediate': CheckIDRequest.fromMessage,
        'check_authentication': CheckAuthRequest.fromMessage,
        'associate': AssociateRequest.fromMessage,
        }

    def __init__(self, server):
        """Construct a Decoder.

        @param server: The server which I am decoding requests for.
            (Necessary because some replies reference their server.)
        @type server: L{Server}
        """
        self.server = server

    def decode(self, query):
        """I transform query parameters into an L{OpenIDRequest}.

        If the query does not seem to be an OpenID request at all, I return
        C{None}.

        @param query: The query parameters as a dictionary with each
            key mapping to one value.
        @type query: dict

        @raises ProtocolError: When the query does not seem to be a valid
            OpenID request.

        @returntype: L{OpenIDRequest}
        """
        if not query:
            return None

        try:
            message = Message.fromPostArgs(query)
        except InvalidOpenIDNamespace, err:
            # It's useful to have a Message attached to a ProtocolError, so we
            # override the bad ns value to build a Message out of it.  Kinda
            # kludgy, since it's made of lies, but the parts that aren't lies
            # are more useful than a 'None'.
            query = query.copy()
            query['openid.ns'] = OPENID2_NS
            message = Message.fromPostArgs(query)
            raise ProtocolError(message, str(err))

        mode = message.getArg(OPENID_NS, 'mode')
        if not mode:
            fmt = "No mode value in message %s"
            raise ProtocolError(message, text=fmt % (message,))

        handler = self._handlers.get(mode, self.defaultDecoder)
        return handler(message, self.server.op_endpoint)


    def defaultDecoder(self, message, server):
        """Called to decode queries when no handler for that mode is found.

        @raises ProtocolError: This implementation always raises
            L{ProtocolError}.
        """
        mode = message.getArg(OPENID_NS, 'mode')
        fmt = "Unrecognized OpenID mode %r"
        raise ProtocolError(message, text=fmt % (mode,))



class Server(object):
    """I handle requests for an OpenID server.

    Some types of requests (those which are not C{checkid} requests) may be
    handed to my L{handleRequest} method, and I will take care of it and
    return a response.

    For your convenience, I also provide an interface to L{Decoder.decode}
    and L{SigningEncoder.encode} through my methods L{decodeRequest} and
    L{encodeResponse}.

    All my state is encapsulated in an
    L{OpenIDStore<openid.store.interface.OpenIDStore>}, which means
    I'm not generally pickleable but I am easy to reconstruct.

    Example::

        oserver = Server(FileOpenIDStore(data_path), "http://example.com/op")
        request = oserver.decodeRequest(query)
        if request.mode in ['checkid_immediate', 'checkid_setup']:
            if self.isAuthorized(request.identity, request.trust_root):
                response = request.answer(True)
            elif request.immediate:
                response = request.answer(False)
            else:
                self.showDecidePage(request)
                return
        else:
            response = oserver.handleRequest(request)

        webresponse = oserver.encode(response)

    @ivar signatory: I'm using this for associate requests and to sign things.
    @type signatory: L{Signatory}

    @ivar decoder: I'm using this to decode things.
    @type decoder: L{Decoder}

    @ivar encoder: I'm using this to encode things.
    @type encoder: L{Encoder}

    @ivar op_endpoint: My URL.
    @type op_endpoint: str

    @ivar negotiator: I use this to determine which kinds of
        associations I can make and how.
    @type negotiator: L{openid.association.SessionNegotiator}
    """
    
    def __init__(
        self,
        store,
        op_endpoint=None,
        signatoryClass=Signatory, 
        encoderClass=SigningEncoder, 
        decoderClass=Decoder):
        """A new L{Server}.

        @param store: The back-end where my associations are stored.
        @type store: L{openid.store.interface.OpenIDStore}

        @param op_endpoint: My URL, the fully qualified address of this
            server's endpoint, i.e. C{http://example.com/server}
        @type op_endpoint: str

        @change: C{op_endpoint} is new in library version 2.0.  It
            currently defaults to C{None} for compatibility with
            earlier versions of the library, but you must provide it
            if you want to respond to any version 2 OpenID requests.
        """
        self.store = store
        self.signatory = signatoryClass(self.store)
        self.encoder = encoderClass(self.signatory)
        self.decoder = decoderClass(self)
        self.negotiator = default_negotiator.copy()

        if not op_endpoint:
            warnings.warn("%s.%s constructor requires op_endpoint parameter "
                          "for OpenID 2.0 servers" %
                          (self.__class__.__module__, self.__class__.__name__),
                          stacklevel=2)
        self.op_endpoint = op_endpoint


    def handleRequest(self, request):
        """Handle a request.

        Give me a request, I will give you a response.  Unless it's a type
        of request I cannot handle myself, in which case I will raise
        C{NotImplementedError}.  In that case, you can handle it yourself,
        or add a method to me for handling that request type.

        @raises NotImplementedError: When I do not have a handler defined
            for that type of request.

        @returntype: L{OpenIDResponse}
        """
        handler = getattr(self, 'openid_' + request.mode, None)
        if handler is not None:
            return handler(request)
        else:
            raise NotImplementedError(
                "%s has no handler for a request of mode %r." %
                (self, request.mode))


    def openid_check_authentication(self, request):
        """Handle and respond to C{check_authentication} requests.

        @returntype: L{OpenIDResponse}
        """
        return request.answer(self.signatory)


    def openid_associate(self, request):
        """Handle and respond to C{associate} requests.

        @returntype: L{OpenIDResponse}
        """
        # XXX: TESTME
        assoc_type = request.assoc_type
        session_type = request.session.session_type
        if self.negotiator.isAllowed(assoc_type, session_type):
            assoc = self.signatory.createAssociation(dumb=False,
                                                     assoc_type=assoc_type)
            return request.answer(assoc)
        else:
            message = ('Association type %r is not supported with '
                       'session type %r' % (assoc_type, session_type))
            (preferred_assoc_type, preferred_session_type) = \
                                   self.negotiator.getAllowedType()
            return request.answerUnsupported(
                message,
                preferred_assoc_type,
                preferred_session_type)


    def decodeRequest(self, query):
        """Transform query parameters into an L{OpenIDRequest}.

        If the query does not seem to be an OpenID request at all, I return
        C{None}.

        @param query: The query parameters as a dictionary with each
            key mapping to one value.
        @type query: dict

        @raises ProtocolError: When the query does not seem to be a valid
            OpenID request.

        @returntype: L{OpenIDRequest}

        @see: L{Decoder.decode}
        """
        return self.decoder.decode(query)


    def encodeResponse(self, response):
        """Encode a response to a L{WebResponse}, signing it first if appropriate.

        @raises EncodingError: When I can't figure out how to encode this
            message.

        @raises AlreadySigned: When this response is already signed.

        @returntype: L{WebResponse}

        @see: L{SigningEncoder.encode}
        """
        return self.encoder.encode(response)



class ProtocolError(Exception):
    """A message did not conform to the OpenID protocol.

    @ivar message: The query that is failing to be a valid OpenID request.
    @type message: openid.message.Message
    """

    def __init__(self, message, text=None, reference=None, contact=None):
        """When an error occurs.

        @param message: The message that is failing to be a valid
            OpenID request.
        @type message: openid.message.Message

        @param text: A message about the encountered error.  Set as C{args[0]}.
        @type text: str
        """
        self.openid_message = message
        self.reference = reference
        self.contact = contact
        assert type(message) not in [str, unicode]
        Exception.__init__(self, text)


    def getReturnTo(self):
        """Get the return_to argument from the request, if any.

        @returntype: str
        """
        if self.openid_message is None:
            return None
        else:
            return self.openid_message.getArg(OPENID_NS, 'return_to')

    def hasReturnTo(self):
        """Did this request have a return_to parameter?

        @returntype: bool
        """
        return self.getReturnTo() is not None

    def toMessage(self):
        """Generate a Message object for sending to the relying party,
        after encoding.
        """
        namespace = self.openid_message.getOpenIDNamespace()
        reply = Message(namespace)
        reply.setArg(OPENID_NS, 'mode', 'error')
        reply.setArg(OPENID_NS, 'error', str(self))

        if self.contact is not None:
            reply.setArg(OPENID_NS, 'contact', str(self.contact))

        if self.reference is not None:
            reply.setArg(OPENID_NS, 'reference', str(self.reference))

        return reply

    # implements IEncodable

    def encodeToURL(self):
        return self.toMessage().toURL(self.getReturnTo())

    def encodeToKVForm(self):
        return self.toMessage().toKVForm()

    def toFormMarkup(self):
        """Encode to HTML form markup for POST.

        @since: 2.1.0
        """
        return self.toMessage().toFormMarkup(self.getReturnTo())

    def toHTML(self):
        """Encode to a full HTML page, wrapping the form markup in a page
        that will autosubmit the form.

        @since: 2.1.?
        """
        return oidutil.autoSubmitHTML(self.toFormMarkup())

    def whichEncoding(self):
        """How should I be encoded?

        @returns: one of ENCODE_URL, ENCODE_KVFORM, or None.  If None,
            I cannot be encoded as a protocol message and should be
            displayed to the user.
        """
        if self.hasReturnTo():
            if self.openid_message.isOpenID1() and \
               len(self.encodeToURL()) > OPENID1_URL_LIMIT:
                return ENCODE_HTML_FORM
            else:
                return ENCODE_URL

        if self.openid_message is None:
            return None

        mode = self.openid_message.getArg(OPENID_NS, 'mode')
        if mode:
            if mode not in BROWSER_REQUEST_MODES:
                return ENCODE_KVFORM

        # According to the OpenID spec as of this writing, we are probably
        # supposed to switch on request type here (GET versus POST) to figure
        # out if we're supposed to print machine-readable or human-readable
        # content at this point.  GET/POST seems like a pretty lousy way of
        # making the distinction though, as it's just as possible that the
        # user agent could have mistakenly been directed to post to the
        # server URL.

        # Basically, if your request was so broken that you didn't manage to
        # include an openid.mode, I'm not going to worry too much about
        # returning you something you can't parse.
        return None



class VersionError(Exception):
    """Raised when an operation was attempted that is not compatible with
    the protocol version being used."""



class NoReturnToError(Exception):
    """Raised when a response to a request cannot be generated because
    the request contains no return_to URL.
    """
    pass



class EncodingError(Exception):
    """Could not encode this as a protocol message.

    You should probably render it and show it to the user.

    @ivar response: The response that failed to encode.
    @type response: L{OpenIDResponse}
    """

    def __init__(self, response, explanation=None):
        Exception.__init__(self, response)
        self.response = response
        self.explanation = explanation

    def __str__(self):
        if self.explanation:
            s = '%s: %s' % (self.__class__.__name__,
                            self.explanation)
        else:
            s = '%s for Response %s' % (
                self.__class__.__name__, self.response)
        return s


class AlreadySigned(EncodingError):
    """This response is already signed."""



class UntrustedReturnURL(ProtocolError):
    """A return_to is outside the trust_root."""

    def __init__(self, message, return_to, trust_root):
        ProtocolError.__init__(self, message)
        self.return_to = return_to
        self.trust_root = trust_root

    def __str__(self):
        return "return_to %r not under trust_root %r" % (self.return_to,
                                                         self.trust_root)


class MalformedReturnURL(ProtocolError):
    """The return_to URL doesn't look like a valid URL."""
    def __init__(self, openid_message, return_to):
        self.return_to = return_to
        ProtocolError.__init__(self, openid_message)



class MalformedTrustRoot(ProtocolError):
    """The trust root is not well-formed.

    @see: OpenID Specs, U{openid.trust_root<http://openid.net/specs.bml#mode-checkid_immediate>}
    """
    pass


#class IEncodable: # Interface
#     def encodeToURL(return_to):
#         """Encode a response as a URL for redirection.
#
#         @returns: A URL to direct the user agent back to.
#         @returntype: str
#         """
#         pass
#
#     def encodeToKvform():
#         """Encode a response in key-value colon/newline format.
#
#         This is a machine-readable format used to respond to messages which
#         came directly from the consumer and not through the user agent.
#
#         @see: OpenID Specs,
#            U{Key-Value Colon/Newline format<http://openid.net/specs.bml#keyvalue>}
#
#         @returntype: str
#         """
#         pass
#
#     def whichEncoding():
#         """How should I be encoded?
#
#         @returns: one of ENCODE_URL, ENCODE_KVFORM, or None.  If None,
#             I cannot be encoded as a protocol message and should be
#             displayed to the user.
#         """
#         pass

########NEW FILE########
__FILENAME__ = trustroot
# -*- test-case-name: openid.test.test_rpverify -*-
"""
This module contains the C{L{TrustRoot}} class, which helps handle
trust root checking.  This module is used by the
C{L{openid.server.server}} module, but it is also available to server
implementers who wish to use it for additional trust root checking.

It also implements relying party return_to URL verification, based on
the realm.
"""

__all__ = [
    'TrustRoot',
    'RP_RETURN_TO_URL_TYPE',
    'extractReturnToURLs',
    'returnToMatches',
    'verifyReturnTo',
    ]

from openid import urinorm
from openid.yadis import services

from urlparse import urlparse, urlunparse
import re
import logging

############################################
_protocols = ['http', 'https']
_top_level_domains = [
    'ac', 'ad', 'ae', 'aero', 'af', 'ag', 'ai', 'al', 'am', 'an',
    'ao', 'aq', 'ar', 'arpa', 'as', 'asia', 'at', 'au', 'aw',
    'ax', 'az', 'ba', 'bb', 'bd', 'be', 'bf', 'bg', 'bh', 'bi',
    'biz', 'bj', 'bm', 'bn', 'bo', 'br', 'bs', 'bt', 'bv', 'bw',
    'by', 'bz', 'ca', 'cat', 'cc', 'cd', 'cf', 'cg', 'ch', 'ci',
    'ck', 'cl', 'cm', 'cn', 'co', 'com', 'coop', 'cr', 'cu', 'cv',
    'cx', 'cy', 'cz', 'de', 'dj', 'dk', 'dm', 'do', 'dz', 'ec',
    'edu', 'ee', 'eg', 'er', 'es', 'et', 'eu', 'fi', 'fj', 'fk',
    'fm', 'fo', 'fr', 'ga', 'gb', 'gd', 'ge', 'gf', 'gg', 'gh',
    'gi', 'gl', 'gm', 'gn', 'gov', 'gp', 'gq', 'gr', 'gs', 'gt',
    'gu', 'gw', 'gy', 'hk', 'hm', 'hn', 'hr', 'ht', 'hu', 'id',
    'ie', 'il', 'im', 'in', 'info', 'int', 'io', 'iq', 'ir', 'is',
    'it', 'je', 'jm', 'jo', 'jobs', 'jp', 'ke', 'kg', 'kh', 'ki',
    'km', 'kn', 'kp', 'kr', 'kw', 'ky', 'kz', 'la', 'lb', 'lc',
    'li', 'lk', 'lr', 'ls', 'lt', 'lu', 'lv', 'ly', 'ma', 'mc',
    'md', 'me', 'mg', 'mh', 'mil', 'mk', 'ml', 'mm', 'mn', 'mo',
    'mobi', 'mp', 'mq', 'mr', 'ms', 'mt', 'mu', 'museum', 'mv',
    'mw', 'mx', 'my', 'mz', 'na', 'name', 'nc', 'ne', 'net', 'nf',
    'ng', 'ni', 'nl', 'no', 'np', 'nr', 'nu', 'nz', 'om', 'org',
    'pa', 'pe', 'pf', 'pg', 'ph', 'pk', 'pl', 'pm', 'pn', 'pr',
    'pro', 'ps', 'pt', 'pw', 'py', 'qa', 're', 'ro', 'rs', 'ru',
    'rw', 'sa', 'sb', 'sc', 'sd', 'se', 'sg', 'sh', 'si', 'sj',
    'sk', 'sl', 'sm', 'sn', 'so', 'sr', 'st', 'su', 'sv', 'sy',
    'sz', 'tc', 'td', 'tel', 'tf', 'tg', 'th', 'tj', 'tk', 'tl',
    'tm', 'tn', 'to', 'tp', 'tr', 'travel', 'tt', 'tv', 'tw',
    'tz', 'ua', 'ug', 'uk', 'us', 'uy', 'uz', 'va', 'vc', 've',
    'vg', 'vi', 'vn', 'vu', 'wf', 'ws', 'xn--0zwm56d',
    'xn--11b5bs3a9aj6g', 'xn--80akhbyknj4f', 'xn--9t4b11yi5a',
    'xn--deba0ad', 'xn--g6w251d', 'xn--hgbk6aj7f53bba',
    'xn--hlcj6aya9esc7a', 'xn--jxalpdlp', 'xn--kgbechtv',
    'xn--zckzah', 'ye', 'yt', 'yu', 'za', 'zm', 'zw']

# Build from RFC3986, section 3.2.2. Used to reject hosts with invalid
# characters.
host_segment_re = re.compile(
    r"(?:[-a-zA-Z0-9!$&'\(\)\*+,;=._~]|%[a-zA-Z0-9]{2})+$")

class RealmVerificationRedirected(Exception):
    """Attempting to verify this realm resulted in a redirect.

    @since: 2.1.0
    """
    def __init__(self, relying_party_url, rp_url_after_redirects):
        self.relying_party_url = relying_party_url
        self.rp_url_after_redirects = rp_url_after_redirects

    def __str__(self):
        return ("Attempting to verify %r resulted in "
                "redirect to %r" %
                (self.relying_party_url,
                 self.rp_url_after_redirects))


def _parseURL(url):
    try:
        url = urinorm.urinorm(url)
    except ValueError:
        return None
    proto, netloc, path, params, query, frag = urlparse(url)
    if not path:
        # Python <2.4 does not parse URLs with no path properly
        if not query and '?' in netloc:
            netloc, query = netloc.split('?', 1)

        path = '/'

    path = urlunparse(('', '', path, params, query, frag))

    if ':' in netloc:
        try:
            host, port = netloc.split(':')
        except ValueError:
            return None

        if not re.match(r'\d+$', port):
            return None
    else:
        host = netloc
        port = ''

    host = host.lower()
    if not host_segment_re.match(host):
        return None

    return proto, host, port, path

class TrustRoot(object):
    """
    This class represents an OpenID trust root.  The C{L{parse}}
    classmethod accepts a trust root string, producing a
    C{L{TrustRoot}} object.  The method OpenID server implementers
    would be most likely to use is the C{L{isSane}} method, which
    checks the trust root for given patterns that indicate that the
    trust root is too broad or points to a local network resource.

    @sort: parse, isSane
    """

    def __init__(self, unparsed, proto, wildcard, host, port, path):
        self.unparsed = unparsed
        self.proto = proto
        self.wildcard = wildcard
        self.host = host
        self.port = port
        self.path = path

    def isSane(self):
        """
        This method checks the to see if a trust root represents a
        reasonable (sane) set of URLs.  'http://*.com/', for example
        is not a reasonable pattern, as it cannot meaningfully specify
        the site claiming it.  This function attempts to find many
        related examples, but it can only work via heuristics.
        Negative responses from this method should be treated as
        advisory, used only to alert the user to examine the trust
        root carefully.


        @return: Whether the trust root is sane

        @rtype: C{bool}
        """

        if self.host == 'localhost':
            return True

        host_parts = self.host.split('.')
        if self.wildcard:
            assert host_parts[0] == '', host_parts
            del host_parts[0]

        # If it's an absolute domain name, remove the empty string
        # from the end.
        if host_parts and not host_parts[-1]:
            del host_parts[-1]

        if not host_parts:
            return False

        # Do not allow adjacent dots
        if '' in host_parts:
            return False

        tld = host_parts[-1]
        if tld not in _top_level_domains:
            return False

        if len(host_parts) == 1:
            return False

        if self.wildcard:
            if len(tld) == 2 and len(host_parts[-2]) <= 3:
                # It's a 2-letter tld with a short second to last segment
                # so there needs to be more than two segments specified 
                # (e.g. *.co.uk is insane)
                return len(host_parts) > 2

        # Passed all tests for insanity.
        return True

    def validateURL(self, url):
        """
        Validates a URL against this trust root.


        @param url: The URL to check

        @type url: C{str}


        @return: Whether the given URL is within this trust root.

        @rtype: C{bool}
        """

        url_parts = _parseURL(url)
        if url_parts is None:
            return False

        proto, host, port, path = url_parts

        if proto != self.proto:
            return False

        if port != self.port:
            return False

        if '*' in host:
            return False

        if not self.wildcard:
            if host != self.host:
                return False
        elif ((not host.endswith(self.host)) and
              ('.' + host) != self.host):
            return False

        if path != self.path:
            path_len = len(self.path)
            trust_prefix = self.path[:path_len]
            url_prefix = path[:path_len]

            # must be equal up to the length of the path, at least
            if trust_prefix != url_prefix:
                return False

            # These characters must be on the boundary between the end
            # of the trust root's path and the start of the URL's
            # path.
            if '?' in self.path:
                allowed = '&'
            else:
                allowed = '?/'

            return (self.path[-1] in allowed or
                path[path_len] in allowed)

        return True

    def parse(cls, trust_root):
        """
        This method creates a C{L{TrustRoot}} instance from the given
        input, if possible.


        @param trust_root: This is the trust root to parse into a
        C{L{TrustRoot}} object.

        @type trust_root: C{str}


        @return: A C{L{TrustRoot}} instance if trust_root parses as a
        trust root, C{None} otherwise.

        @rtype: C{NoneType} or C{L{TrustRoot}}
        """
        url_parts = _parseURL(trust_root)
        if url_parts is None:
            return None

        proto, host, port, path = url_parts

        # check for valid prototype
        if proto not in _protocols:
            return None

        # check for URI fragment
        if path.find('#') != -1:
            return None

        # extract wildcard if it is there
        if host.find('*', 1) != -1:
            # wildcard must be at start of domain:  *.foo.com, not foo.*.com
            return None

        if host.startswith('*'):
            # Starts with star, so must have a dot after it (if a
            # domain is specified)
            if len(host) > 1 and host[1] != '.':
                return None

            host = host[1:]
            wilcard = True
        else:
            wilcard = False

        # we have a valid trust root
        tr = cls(trust_root, proto, wilcard, host, port, path)

        return tr

    parse = classmethod(parse)

    def checkSanity(cls, trust_root_string):
        """str -> bool

        is this a sane trust root?
        """
        trust_root = cls.parse(trust_root_string)
        if trust_root is None:
            return False
        else:
            return trust_root.isSane()

    checkSanity = classmethod(checkSanity)

    def checkURL(cls, trust_root, url):
        """quick func for validating a url against a trust root.  See the
        TrustRoot class if you need more control."""
        tr = cls.parse(trust_root)
        return tr is not None and tr.validateURL(url)

    checkURL = classmethod(checkURL)

    def buildDiscoveryURL(self):
        """Return a discovery URL for this realm.

        This function does not check to make sure that the realm is
        valid. Its behaviour on invalid inputs is undefined.

        @rtype: str

        @returns: The URL upon which relying party discovery should be run
            in order to verify the return_to URL

        @since: 2.1.0
        """
        if self.wildcard:
            # Use "www." in place of the star
            assert self.host.startswith('.'), self.host
            www_domain = 'www' + self.host
            return '%s://%s%s' % (self.proto, www_domain, self.path)
        else:
            return self.unparsed

    def __repr__(self):
        return "TrustRoot(%r, %r, %r, %r, %r, %r)" % (
            self.unparsed, self.proto, self.wildcard, self.host, self.port,
            self.path)

    def __str__(self):
        return repr(self)

# The URI for relying party discovery, used in realm verification.
#
# XXX: This should probably live somewhere else (like in
# openid.consumer or openid.yadis somewhere)
RP_RETURN_TO_URL_TYPE = 'http://specs.openid.net/auth/2.0/return_to'

def _extractReturnURL(endpoint):
    """If the endpoint is a relying party OpenID return_to endpoint,
    return the endpoint URL. Otherwise, return None.

    This function is intended to be used as a filter for the Yadis
    filtering interface.

    @see: C{L{openid.yadis.services}}
    @see: C{L{openid.yadis.filters}}

    @param endpoint: An XRDS BasicServiceEndpoint, as returned by
        performing Yadis dicovery.

    @returns: The endpoint URL or None if the endpoint is not a
        relying party endpoint.
    @rtype: str or NoneType
    """
    if endpoint.matchTypes([RP_RETURN_TO_URL_TYPE]):
        return endpoint.uri
    else:
        return None

def returnToMatches(allowed_return_to_urls, return_to):
    """Is the return_to URL under one of the supplied allowed
    return_to URLs?

    @since: 2.1.0
    """

    for allowed_return_to in allowed_return_to_urls:
        # A return_to pattern works the same as a realm, except that
        # it's not allowed to use a wildcard. We'll model this by
        # parsing it as a realm, and not trying to match it if it has
        # a wildcard.

        return_realm = TrustRoot.parse(allowed_return_to)
        if (# Parses as a trust root
            return_realm is not None and

            # Does not have a wildcard
            not return_realm.wildcard and

            # Matches the return_to that we passed in with it
            return_realm.validateURL(return_to)
            ):
            return True

    # No URL in the list matched
    return False

def getAllowedReturnURLs(relying_party_url):
    """Given a relying party discovery URL return a list of return_to URLs.

    @since: 2.1.0
    """
    (rp_url_after_redirects, return_to_urls) = services.getServiceEndpoints(
        relying_party_url, _extractReturnURL)

    if rp_url_after_redirects != relying_party_url:
        # Verification caused a redirect
        raise RealmVerificationRedirected(
            relying_party_url, rp_url_after_redirects)

    return return_to_urls

# _vrfy parameter is there to make testing easier
def verifyReturnTo(realm_str, return_to, _vrfy=getAllowedReturnURLs):
    """Verify that a return_to URL is valid for the given realm.

    This function builds a discovery URL, performs Yadis discovery on
    it, makes sure that the URL does not redirect, parses out the
    return_to URLs, and finally checks to see if the current return_to
    URL matches the return_to.

    @raises DiscoveryFailure: When Yadis discovery fails
    @returns: True if the return_to URL is valid for the realm

    @since: 2.1.0
    """
    realm = TrustRoot.parse(realm_str)
    if realm is None:
        # The realm does not parse as a URL pattern
        return False

    try:
        allowable_urls = _vrfy(realm.buildDiscoveryURL())
    except RealmVerificationRedirected, err:
        logging.exception(str(err))
        return False

    if returnToMatches(allowable_urls, return_to):
        return True
    else:
        logging.error("Failed to validate return_to %r for realm %r, was not "
                    "in %s" % (return_to, realm_str, allowable_urls))
        return False

########NEW FILE########
__FILENAME__ = sreg
"""moved to L{openid.extensions.sreg}"""

import warnings
warnings.warn("openid.sreg has moved to openid.extensions.sreg",
              DeprecationWarning)

from openid.extensions.sreg import *

########NEW FILE########
__FILENAME__ = filestore
"""
This module contains an C{L{OpenIDStore}} implementation backed by
flat files.
"""

import string
import os
import os.path
import time
import logging

from errno import EEXIST, ENOENT

try:
    from tempfile import mkstemp
except ImportError:
    # Python < 2.3
    import warnings
    warnings.filterwarnings("ignore",
                            "tempnam is a potential security risk",
                            RuntimeWarning,
                            "openid.store.filestore")

    def mkstemp(dir):
        for _ in range(5):
            name = os.tempnam(dir)
            try:
                fd = os.open(name, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0600)
            except OSError, why:
                if why.errno != EEXIST:
                    raise
            else:
                return fd, name

        raise RuntimeError('Failed to get temp file after 5 attempts')

from openid.association import Association
from openid.store.interface import OpenIDStore
from openid.store import nonce
from openid import cryptutil, oidutil

_filename_allowed = string.ascii_letters + string.digits + '.'
try:
    # 2.4
    set
except NameError:
    try:
        # 2.3
        import sets
    except ImportError:
        # Python < 2.2
        d = {}
        for c in _filename_allowed:
            d[c] = None
        _isFilenameSafe = d.has_key
        del d
    else:
        _isFilenameSafe = sets.Set(_filename_allowed).__contains__
else:
    _isFilenameSafe = set(_filename_allowed).__contains__

def _safe64(s):
    h64 = oidutil.toBase64(cryptutil.sha1(s))
    h64 = h64.replace('+', '_')
    h64 = h64.replace('/', '.')
    h64 = h64.replace('=', '')
    return h64

def _filenameEscape(s):
    filename_chunks = []
    for c in s:
        if _isFilenameSafe(c):
            filename_chunks.append(c)
        else:
            filename_chunks.append('_%02X' % ord(c))
    return ''.join(filename_chunks)

def _removeIfPresent(filename):
    """Attempt to remove a file, returning whether the file existed at
    the time of the call.

    str -> bool
    """
    try:
        os.unlink(filename)
    except OSError, why:
        if why.errno == ENOENT:
            # Someone beat us to it, but it's gone, so that's OK
            return 0
        else:
            raise
    else:
        # File was present
        return 1

def _ensureDir(dir_name):
    """Create dir_name as a directory if it does not exist. If it
    exists, make sure that it is, in fact, a directory.

    Can raise OSError

    str -> NoneType
    """
    try:
        os.makedirs(dir_name)
    except OSError, why:
        if why.errno != EEXIST or not os.path.isdir(dir_name):
            raise

class FileOpenIDStore(OpenIDStore):
    """
    This is a filesystem-based store for OpenID associations and
    nonces.  This store should be safe for use in concurrent systems
    on both windows and unix (excluding NFS filesystems).  There are a
    couple race conditions in the system, but those failure cases have
    been set up in such a way that the worst-case behavior is someone
    having to try to log in a second time.

    Most of the methods of this class are implementation details.
    People wishing to just use this store need only pay attention to
    the C{L{__init__}} method.

    Methods of this object can raise OSError if unexpected filesystem
    conditions, such as bad permissions or missing directories, occur.
    """

    def __init__(self, directory):
        """
        Initializes a new FileOpenIDStore.  This initializes the
        nonce and association directories, which are subdirectories of
        the directory passed in.

        @param directory: This is the directory to put the store
            directories in.

        @type directory: C{str}
        """
        # Make absolute
        directory = os.path.normpath(os.path.abspath(directory))

        self.nonce_dir = os.path.join(directory, 'nonces')

        self.association_dir = os.path.join(directory, 'associations')

        # Temp dir must be on the same filesystem as the assciations
        # directory
        self.temp_dir = os.path.join(directory, 'temp')

        self.max_nonce_age = 6 * 60 * 60 # Six hours, in seconds

        self._setup()

    def _setup(self):
        """Make sure that the directories in which we store our data
        exist.

        () -> NoneType
        """
        _ensureDir(self.nonce_dir)
        _ensureDir(self.association_dir)
        _ensureDir(self.temp_dir)

    def _mktemp(self):
        """Create a temporary file on the same filesystem as
        self.association_dir.

        The temporary directory should not be cleaned if there are any
        processes using the store. If there is no active process using
        the store, it is safe to remove all of the files in the
        temporary directory.

        () -> (file, str)
        """
        fd, name = mkstemp(dir=self.temp_dir)
        try:
            file_obj = os.fdopen(fd, 'wb')
            return file_obj, name
        except:
            _removeIfPresent(name)
            raise

    def getAssociationFilename(self, server_url, handle):
        """Create a unique filename for a given server url and
        handle. This implementation does not assume anything about the
        format of the handle. The filename that is returned will
        contain the domain name from the server URL for ease of human
        inspection of the data directory.

        (str, str) -> str
        """
        if server_url.find('://') == -1:
            raise ValueError('Bad server URL: %r' % server_url)

        proto, rest = server_url.split('://', 1)
        domain = _filenameEscape(rest.split('/', 1)[0])
        url_hash = _safe64(server_url)
        if handle:
            handle_hash = _safe64(handle)
        else:
            handle_hash = ''

        filename = '%s-%s-%s-%s' % (proto, domain, url_hash, handle_hash)

        return os.path.join(self.association_dir, filename)

    def storeAssociation(self, server_url, association):
        """Store an association in the association directory.

        (str, Association) -> NoneType
        """
        association_s = association.serialize()
        filename = self.getAssociationFilename(server_url, association.handle)
        tmp_file, tmp = self._mktemp()

        try:
            try:
                tmp_file.write(association_s)
                os.fsync(tmp_file.fileno())
            finally:
                tmp_file.close()

            try:
                os.rename(tmp, filename)
            except OSError, why:
                if why.errno != EEXIST:
                    raise

                # We only expect EEXIST to happen only on Windows. It's
                # possible that we will succeed in unlinking the existing
                # file, but not in putting the temporary file in place.
                try:
                    os.unlink(filename)
                except OSError, why:
                    if why.errno == ENOENT:
                        pass
                    else:
                        raise

                # Now the target should not exist. Try renaming again,
                # giving up if it fails.
                os.rename(tmp, filename)
        except:
            # If there was an error, don't leave the temporary file
            # around.
            _removeIfPresent(tmp)
            raise

    def getAssociation(self, server_url, handle=None):
        """Retrieve an association. If no handle is specified, return
        the association with the latest expiration.

        (str, str or NoneType) -> Association or NoneType
        """
        if handle is None:
            handle = ''

        # The filename with the empty handle is a prefix of all other
        # associations for the given server URL.
        filename = self.getAssociationFilename(server_url, handle)

        if handle:
            return self._getAssociation(filename)
        else:
            association_files = os.listdir(self.association_dir)
            matching_files = []
            # strip off the path to do the comparison
            name = os.path.basename(filename)
            for association_file in association_files:
                if association_file.startswith(name):
                    matching_files.append(association_file)

            matching_associations = []
            # read the matching files and sort by time issued
            for name in matching_files:
                full_name = os.path.join(self.association_dir, name)
                association = self._getAssociation(full_name)
                if association is not None:
                    matching_associations.append(
                        (association.issued, association))

            matching_associations.sort()

            # return the most recently issued one.
            if matching_associations:
                (_, assoc) = matching_associations[-1]
                return assoc
            else:
                return None

    def _getAssociation(self, filename):
        try:
            assoc_file = file(filename, 'rb')
        except IOError, why:
            if why.errno == ENOENT:
                # No association exists for that URL and handle
                return None
            else:
                raise
        else:
            try:
                assoc_s = assoc_file.read()
            finally:
                assoc_file.close()

            try:
                association = Association.deserialize(assoc_s)
            except ValueError:
                _removeIfPresent(filename)
                return None

        # Clean up expired associations
        if association.getExpiresIn() == 0:
            _removeIfPresent(filename)
            return None
        else:
            return association

    def removeAssociation(self, server_url, handle):
        """Remove an association if it exists. Do nothing if it does not.

        (str, str) -> bool
        """
        assoc = self.getAssociation(server_url, handle)
        if assoc is None:
            return 0
        else:
            filename = self.getAssociationFilename(server_url, handle)
            return _removeIfPresent(filename)

    def useNonce(self, server_url, timestamp, salt):
        """Return whether this nonce is valid.

        str -> bool
        """
        if abs(timestamp - time.time()) > nonce.SKEW:
            return False

        if server_url:
            proto, rest = server_url.split('://', 1)
        else:
            # Create empty proto / rest values for empty server_url,
            # which is part of a consumer-generated nonce.
            proto, rest = '', ''

        domain = _filenameEscape(rest.split('/', 1)[0])
        url_hash = _safe64(server_url)
        salt_hash = _safe64(salt)

        filename = '%08x-%s-%s-%s-%s' % (timestamp, proto, domain,
                                         url_hash, salt_hash)

        filename = os.path.join(self.nonce_dir, filename)
        try:
            fd = os.open(filename, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0200)
        except OSError, why:
            if why.errno == EEXIST:
                return False
            else:
                raise
        else:
            os.close(fd)
            return True

    def _allAssocs(self):
        all_associations = []

        association_filenames = map(
            lambda filename: os.path.join(self.association_dir, filename),
            os.listdir(self.association_dir))
        for association_filename in association_filenames:
            try:
                association_file = file(association_filename, 'rb')
            except IOError, why:
                if why.errno == ENOENT:
                    logging.exception("%s disappeared during %s._allAssocs" % (
                        association_filename, self.__class__.__name__))
                else:
                    raise
            else:
                try:
                    assoc_s = association_file.read()
                finally:
                    association_file.close()

                # Remove expired or corrupted associations
                try:
                    association = Association.deserialize(assoc_s)
                except ValueError:
                    _removeIfPresent(association_filename)
                else:
                    all_associations.append(
                        (association_filename, association))

        return all_associations

    def cleanup(self):
        """Remove expired entries from the database. This is
        potentially expensive, so only run when it is acceptable to
        take time.

        () -> NoneType
        """
        self.cleanupAssociations()
        self.cleanupNonces()

    def cleanupAssociations(self):
        removed = 0
        for assoc_filename, assoc in self._allAssocs():
            if assoc.getExpiresIn() == 0:
                _removeIfPresent(assoc_filename)
                removed += 1
        return removed

    def cleanupNonces(self):
        nonces = os.listdir(self.nonce_dir)
        now = time.time()

        removed = 0
        # Check all nonces for expiry
        for nonce_fname in nonces:
            timestamp = nonce_fname.split('-', 1)[0]
            timestamp = int(timestamp, 16)
            if abs(timestamp - now) > nonce.SKEW:
                filename = os.path.join(self.nonce_dir, nonce_fname)
                _removeIfPresent(filename)
                removed += 1
        return removed

########NEW FILE########
__FILENAME__ = interface
"""
This module contains the definition of the C{L{OpenIDStore}}
interface.
"""

class OpenIDStore(object):
    """
    This is the interface for the store objects the OpenID library
    uses.  It is a single class that provides all of the persistence
    mechanisms that the OpenID library needs, for both servers and
    consumers.

    @change: Version 2.0 removed the C{storeNonce}, C{getAuthKey}, and C{isDumb}
        methods, and changed the behavior of the C{L{useNonce}} method
        to support one-way nonces.  It added C{L{cleanupNonces}},
        C{L{cleanupAssociations}}, and C{L{cleanup}}.

    @sort: storeAssociation, getAssociation, removeAssociation,
        useNonce
    """

    def storeAssociation(self, server_url, association):
        """
        This method puts a C{L{Association
        <openid.association.Association>}} object into storage,
        retrievable by server URL and handle.


        @param server_url: The URL of the identity server that this
            association is with.  Because of the way the server
            portion of the library uses this interface, don't assume
            there are any limitations on the character set of the
            input string.  In particular, expect to see unescaped
            non-url-safe characters in the server_url field.

        @type server_url: C{str}


        @param association: The C{L{Association
            <openid.association.Association>}} to store.

        @type association: C{L{Association
            <openid.association.Association>}}


        @return: C{None}

        @rtype: C{NoneType}
        """
        raise NotImplementedError

    def getAssociation(self, server_url, handle=None):
        """
        This method returns an C{L{Association
        <openid.association.Association>}} object from storage that
        matches the server URL and, if specified, handle. It returns
        C{None} if no such association is found or if the matching
        association is expired.

        If no handle is specified, the store may return any
        association which matches the server URL.  If multiple
        associations are valid, the recommended return value for this
        method is the one most recently issued.

        This method is allowed (and encouraged) to garbage collect
        expired associations when found. This method must not return
        expired associations.


        @param server_url: The URL of the identity server to get the
            association for.  Because of the way the server portion of
            the library uses this interface, don't assume there are
            any limitations on the character set of the input string.
            In particular, expect to see unescaped non-url-safe
            characters in the server_url field.

        @type server_url: C{str}


        @param handle: This optional parameter is the handle of the
            specific association to get.  If no specific handle is
            provided, any valid association matching the server URL is
            returned.

        @type handle: C{str} or C{NoneType}


        @return: The C{L{Association
            <openid.association.Association>}} for the given identity
            server.

        @rtype: C{L{Association <openid.association.Association>}} or
            C{NoneType}
        """
        raise NotImplementedError

    def removeAssociation(self, server_url, handle):
        """
        This method removes the matching association if it's found,
        and returns whether the association was removed or not.


        @param server_url: The URL of the identity server the
            association to remove belongs to.  Because of the way the
            server portion of the library uses this interface, don't
            assume there are any limitations on the character set of
            the input string.  In particular, expect to see unescaped
            non-url-safe characters in the server_url field.

        @type server_url: C{str}


        @param handle: This is the handle of the association to
            remove.  If there isn't an association found that matches
            both the given URL and handle, then there was no matching
            handle found.

        @type handle: C{str}


        @return: Returns whether or not the given association existed.

        @rtype: C{bool} or C{int}
        """
        raise NotImplementedError

    def useNonce(self, server_url, timestamp, salt):
        """Called when using a nonce.

        This method should return C{True} if the nonce has not been
        used before, and store it for a while to make sure nobody
        tries to use the same value again.  If the nonce has already
        been used or the timestamp is not current, return C{False}.

        You may use L{openid.store.nonce.SKEW} for your timestamp window.

        @change: In earlier versions, round-trip nonces were used and
           a nonce was only valid if it had been previously stored
           with C{storeNonce}.  Version 2.0 uses one-way nonces,
           requiring a different implementation here that does not
           depend on a C{storeNonce} call.  (C{storeNonce} is no
           longer part of the interface.)

        @param server_url: The URL of the server from which the nonce
            originated.

        @type server_url: C{str}

        @param timestamp: The time that the nonce was created (to the
            nearest second), in seconds since January 1 1970 UTC.
        @type timestamp: C{int}

        @param salt: A random string that makes two nonces from the
            same server issued during the same second unique.
        @type salt: str

        @return: Whether or not the nonce was valid.

        @rtype: C{bool}
        """
        raise NotImplementedError

    def cleanupNonces(self):
        """Remove expired nonces from the store.

        Discards any nonce from storage that is old enough that its
        timestamp would not pass L{useNonce}.

        This method is not called in the normal operation of the
        library.  It provides a way for store admins to keep
        their storage from filling up with expired data.

        @return: the number of nonces expired.
        @returntype: int
        """
        raise NotImplementedError

    def cleanupAssociations(self):
        """Remove expired associations from the store.

        This method is not called in the normal operation of the
        library.  It provides a way for store admins to keep
        their storage from filling up with expired data.

        @return: the number of associations expired.
        @returntype: int
        """
        raise NotImplementedError

    def cleanup(self):
        """Shortcut for C{L{cleanupNonces}()}, C{L{cleanupAssociations}()}.

        This method is not called in the normal operation of the
        library.  It provides a way for store admins to keep
        their storage from filling up with expired data.
        """
        return self.cleanupNonces(), self.cleanupAssociations()

########NEW FILE########
__FILENAME__ = memstore
"""A simple store using only in-process memory."""

from openid.store import nonce

import copy
import time

class ServerAssocs(object):
    def __init__(self):
        self.assocs = {}

    def set(self, assoc):
        self.assocs[assoc.handle] = assoc

    def get(self, handle):
        return self.assocs.get(handle)

    def remove(self, handle):
        try:
            del self.assocs[handle]
        except KeyError:
            return False
        else:
            return True

    def best(self):
        """Returns association with the oldest issued date.

        or None if there are no associations.
        """
        best = None
        for assoc in self.assocs.values():
            if best is None or best.issued < assoc.issued:
                best = assoc
        return best

    def cleanup(self):
        """Remove expired associations.

        @return: tuple of (removed associations, remaining associations)
        """
        remove = []
        for handle, assoc in self.assocs.iteritems():
            if assoc.getExpiresIn() == 0:
                remove.append(handle)
        for handle in remove:
            del self.assocs[handle]
        return len(remove), len(self.assocs)



class MemoryStore(object):
    """In-process memory store.

    Use for single long-running processes.  No persistence supplied.
    """
    def __init__(self):
        self.server_assocs = {}
        self.nonces = {}

    def _getServerAssocs(self, server_url):
        try:
            return self.server_assocs[server_url]
        except KeyError:
            assocs = self.server_assocs[server_url] = ServerAssocs()
            return assocs

    def storeAssociation(self, server_url, assoc):
        assocs = self._getServerAssocs(server_url)
        assocs.set(copy.deepcopy(assoc))

    def getAssociation(self, server_url, handle=None):
        assocs = self._getServerAssocs(server_url)
        if handle is None:
            return assocs.best()
        else:
            return assocs.get(handle)

    def removeAssociation(self, server_url, handle):
        assocs = self._getServerAssocs(server_url)
        return assocs.remove(handle)

    def useNonce(self, server_url, timestamp, salt):
        if abs(timestamp - time.time()) > nonce.SKEW:
            return False

        anonce = (str(server_url), int(timestamp), str(salt))
        if anonce in self.nonces:
            return False
        else:
            self.nonces[anonce] = None
            return True

    def cleanupNonces(self):
        now = time.time()
        expired = []
        for anonce in self.nonces.iterkeys():
            if abs(anonce[1] - now) > nonce.SKEW:
                # removing items while iterating over the set could be bad.
                expired.append(anonce)

        for anonce in expired:
            del self.nonces[anonce]
        return len(expired)

    def cleanupAssociations(self):
        remove_urls = []
        removed_assocs = 0
        for server_url, assocs in self.server_assocs.iteritems():
            removed, remaining = assocs.cleanup()
            removed_assocs += removed
            if not remaining:
                remove_urls.append(server_url)

        # Remove entries from server_assocs that had none remaining.
        for server_url in remove_urls:
            del self.server_assocs[server_url]
        return removed_assocs

    def __eq__(self, other):
        return ((self.server_assocs == other.server_assocs) and
                (self.nonces == other.nonces))

    def __ne__(self, other):
        return not (self == other)

########NEW FILE########
__FILENAME__ = nonce
__all__ = [
    'split',
    'mkNonce',
    'checkTimestamp',
    ]

from openid import cryptutil
from time import strptime, strftime, gmtime, time
from calendar import timegm
import string

NONCE_CHARS = string.ascii_letters + string.digits

# Keep nonces for five hours (allow five hours for the combination of
# request time and clock skew). This is probably way more than is
# necessary, but there is not much overhead in storing nonces.
SKEW = 60 * 60 * 5

time_fmt = '%Y-%m-%dT%H:%M:%SZ'
time_str_len = len('0000-00-00T00:00:00Z')

def split(nonce_string):
    """Extract a timestamp from the given nonce string

    @param nonce_string: the nonce from which to extract the timestamp
    @type nonce_string: str

    @returns: A pair of a Unix timestamp and the salt characters
    @returntype: (int, str)

    @raises ValueError: if the nonce does not start with a correctly
        formatted time string
    """
    timestamp_str = nonce_string[:time_str_len]
    try:
        timestamp = timegm(strptime(timestamp_str, time_fmt))
    except AssertionError: # Python 2.2
        timestamp = -1
    if timestamp < 0:
        raise ValueError('time out of range')
    return timestamp, nonce_string[time_str_len:]

def checkTimestamp(nonce_string, allowed_skew=SKEW, now=None):
    """Is the timestamp that is part of the specified nonce string
    within the allowed clock-skew of the current time?

    @param nonce_string: The nonce that is being checked
    @type nonce_string: str

    @param allowed_skew: How many seconds should be allowed for
        completing the request, allowing for clock skew.
    @type allowed_skew: int

    @param now: The current time, as a Unix timestamp
    @type now: int

    @returntype: bool
    @returns: Whether the timestamp is correctly formatted and within
        the allowed skew of the current time.
    """
    try:
        stamp, _ = split(nonce_string)
    except ValueError:
        return False
    else:
        if now is None:
            now = time()

        # Time after which we should not use the nonce
        past = now - allowed_skew

        # Time that is too far in the future for us to allow
        future = now + allowed_skew

        # the stamp is not too far in the future and is not too far in
        # the past
        return past <= stamp <= future

def mkNonce(when=None):
    """Generate a nonce with the current timestamp

    @param when: Unix timestamp representing the issue time of the
        nonce. Defaults to the current time.
    @type when: int

    @returntype: str
    @returns: A string that should be usable as a one-way nonce

    @see: time
    """
    salt = cryptutil.randomString(6, NONCE_CHARS)
    if when is None:
        t = gmtime()
    else:
        t = gmtime(when)

    time_str = strftime(time_fmt, t)
    return time_str + salt

########NEW FILE########
__FILENAME__ = sqlstore
"""
This module contains C{L{OpenIDStore}} implementations that use
various SQL databases to back them.

Example of how to initialize a store database::

    python -c 'from openid.store import sqlstore; import pysqlite2.dbapi2; sqlstore.SQLiteStore(pysqlite2.dbapi2.connect("cstore.db")).createTables()'
"""
import re
import time

from openid.association import Association
from openid.store.interface import OpenIDStore
from openid.store import nonce

def _inTxn(func):
    def wrapped(self, *args, **kwargs):
        return self._callInTransaction(func, self, *args, **kwargs)

    if hasattr(func, '__name__'):
        try:
            wrapped.__name__ = func.__name__[4:]
        except TypeError:
            pass

    if hasattr(func, '__doc__'):
        wrapped.__doc__ = func.__doc__

    return wrapped

class SQLStore(OpenIDStore):
    """
    This is the parent class for the SQL stores, which contains the
    logic common to all of the SQL stores.

    The table names used are determined by the class variables
    C{L{associations_table}} and
    C{L{nonces_table}}.  To change the name of the tables used, pass
    new table names into the constructor.

    To create the tables with the proper schema, see the
    C{L{createTables}} method.

    This class shouldn't be used directly.  Use one of its subclasses
    instead, as those contain the code necessary to use a specific
    database.

    All methods other than C{L{__init__}} and C{L{createTables}}
    should be considered implementation details.


    @cvar associations_table: This is the default name of the table to
        keep associations in

    @cvar nonces_table: This is the default name of the table to keep
        nonces in.


    @sort: __init__, createTables
    """

    associations_table = 'oid_associations'
    nonces_table = 'oid_nonces'

    def __init__(self, conn, associations_table=None, nonces_table=None):
        """
        This creates a new SQLStore instance.  It requires an
        established database connection be given to it, and it allows
        overriding the default table names.


        @param conn: This must be an established connection to a
            database of the correct type for the SQLStore subclass
            you're using.

        @type conn: A python database API compatible connection
            object.


        @param associations_table: This is an optional parameter to
            specify the name of the table used for storing
            associations.  The default value is specified in
            C{L{SQLStore.associations_table}}.

        @type associations_table: C{str}


        @param nonces_table: This is an optional parameter to specify
            the name of the table used for storing nonces.  The
            default value is specified in C{L{SQLStore.nonces_table}}.

        @type nonces_table: C{str}
        """
        self.conn = conn
        self.cur = None
        self._statement_cache = {}
        self._table_names = {
            'associations': associations_table or self.associations_table,
            'nonces': nonces_table or self.nonces_table,
            }
        self.max_nonce_age = 6 * 60 * 60 # Six hours, in seconds

        # DB API extension: search for "Connection Attributes .Error,
        # .ProgrammingError, etc." in
        # http://www.python.org/dev/peps/pep-0249/
        if (hasattr(self.conn, 'IntegrityError') and
            hasattr(self.conn, 'OperationalError')):
            self.exceptions = self.conn

        if not (hasattr(self.exceptions, 'IntegrityError') and
                hasattr(self.exceptions, 'OperationalError')):
            raise RuntimeError("Error using database connection module "
                               "(Maybe it can't be imported?)")

    def blobDecode(self, blob):
        """Convert a blob as returned by the SQL engine into a str object.

        str -> str"""
        return blob

    def blobEncode(self, s):
        """Convert a str object into the necessary object for storing
        in the database as a blob."""
        return s

    def _getSQL(self, sql_name):
        try:
            return self._statement_cache[sql_name]
        except KeyError:
            sql = getattr(self, sql_name)
            sql %= self._table_names
            self._statement_cache[sql_name] = sql
            return sql

    def _execSQL(self, sql_name, *args):
        sql = self._getSQL(sql_name)
        # Kludge because we have reports of postgresql not quoting
        # arguments if they are passed in as unicode instead of str.
        # Currently the strings in our tables just have ascii in them,
        # so this ought to be safe.
        def unicode_to_str(arg):
            if isinstance(arg, unicode):
                return str(arg)
            else:
                return arg
        str_args = map(unicode_to_str, args)
        self.cur.execute(sql, str_args)

    def __getattr__(self, attr):
        # if the attribute starts with db_, use a default
        # implementation that looks up the appropriate SQL statement
        # as an attribute of this object and executes it.
        if attr[:3] == 'db_':
            sql_name = attr[3:] + '_sql'
            def func(*args):
                return self._execSQL(sql_name, *args)
            setattr(self, attr, func)
            return func
        else:
            raise AttributeError('Attribute %r not found' % (attr,))

    def _callInTransaction(self, func, *args, **kwargs):
        """Execute the given function inside of a transaction, with an
        open cursor. If no exception is raised, the transaction is
        comitted, otherwise it is rolled back."""
        # No nesting of transactions
        self.conn.rollback()

        try:
            self.cur = self.conn.cursor()
            try:
                ret = func(*args, **kwargs)
            finally:
                self.cur.close()
                self.cur = None
        except:
            self.conn.rollback()
            raise
        else:
            self.conn.commit()

        return ret

    def txn_createTables(self):
        """
        This method creates the database tables necessary for this
        store to work.  It should not be called if the tables already
        exist.
        """
        self.db_create_nonce()
        self.db_create_assoc()

    createTables = _inTxn(txn_createTables)

    def txn_storeAssociation(self, server_url, association):
        """Set the association for the server URL.

        Association -> NoneType
        """
        a = association
        self.db_set_assoc(
            server_url,
            a.handle,
            self.blobEncode(a.secret),
            a.issued,
            a.lifetime,
            a.assoc_type)

    storeAssociation = _inTxn(txn_storeAssociation)

    def txn_getAssociation(self, server_url, handle=None):
        """Get the most recent association that has been set for this
        server URL and handle.

        str -> NoneType or Association
        """
        if handle is not None:
            self.db_get_assoc(server_url, handle)
        else:
            self.db_get_assocs(server_url)

        rows = self.cur.fetchall()
        if len(rows) == 0:
            return None
        else:
            associations = []
            for values in rows:
                assoc = Association(*values)
                assoc.secret = self.blobDecode(assoc.secret)
                if assoc.getExpiresIn() == 0:
                    self.txn_removeAssociation(server_url, assoc.handle)
                else:
                    associations.append((assoc.issued, assoc))

            if associations:
                associations.sort()
                return associations[-1][1]
            else:
                return None

    getAssociation = _inTxn(txn_getAssociation)

    def txn_removeAssociation(self, server_url, handle):
        """Remove the association for the given server URL and handle,
        returning whether the association existed at all.

        (str, str) -> bool
        """
        self.db_remove_assoc(server_url, handle)
        return self.cur.rowcount > 0 # -1 is undefined

    removeAssociation = _inTxn(txn_removeAssociation)

    def txn_useNonce(self, server_url, timestamp, salt):
        """Return whether this nonce is present, and if it is, then
        remove it from the set.

        str -> bool"""
        if abs(timestamp - time.time()) > nonce.SKEW:
            return False

        try:
            self.db_add_nonce(server_url, timestamp, salt)
        except self.exceptions.IntegrityError:
            # The key uniqueness check failed
            return False
        else:
            # The nonce was successfully added
            return True

    useNonce = _inTxn(txn_useNonce)

    def txn_cleanupNonces(self):
        self.db_clean_nonce(int(time.time()) - nonce.SKEW)
        return self.cur.rowcount

    cleanupNonces = _inTxn(txn_cleanupNonces)

    def txn_cleanupAssociations(self):
        self.db_clean_assoc(int(time.time()))
        return self.cur.rowcount

    cleanupAssociations = _inTxn(txn_cleanupAssociations)


class SQLiteStore(SQLStore):
    """
    This is an SQLite-based specialization of C{L{SQLStore}}.

    To create an instance, see C{L{SQLStore.__init__}}.  To create the
    tables it will use, see C{L{SQLStore.createTables}}.

    All other methods are implementation details.
    """

    create_nonce_sql = """
    CREATE TABLE %(nonces)s (
        server_url VARCHAR,
        timestamp INTEGER,
        salt CHAR(40),
        UNIQUE(server_url, timestamp, salt)
    );
    """

    create_assoc_sql = """
    CREATE TABLE %(associations)s
    (
        server_url VARCHAR(2047),
        handle VARCHAR(255),
        secret BLOB(128),
        issued INTEGER,
        lifetime INTEGER,
        assoc_type VARCHAR(64),
        PRIMARY KEY (server_url, handle)
    );
    """

    set_assoc_sql = ('INSERT OR REPLACE INTO %(associations)s '
                     '(server_url, handle, secret, issued, '
                     'lifetime, assoc_type) '
                     'VALUES (?, ?, ?, ?, ?, ?);')
    get_assocs_sql = ('SELECT handle, secret, issued, lifetime, assoc_type '
                      'FROM %(associations)s WHERE server_url = ?;')
    get_assoc_sql = (
        'SELECT handle, secret, issued, lifetime, assoc_type '
        'FROM %(associations)s WHERE server_url = ? AND handle = ?;')

    get_expired_sql = ('SELECT server_url '
                       'FROM %(associations)s WHERE issued + lifetime < ?;')

    remove_assoc_sql = ('DELETE FROM %(associations)s '
                        'WHERE server_url = ? AND handle = ?;')

    clean_assoc_sql = 'DELETE FROM %(associations)s WHERE issued + lifetime < ?;'

    add_nonce_sql = 'INSERT INTO %(nonces)s VALUES (?, ?, ?);'

    clean_nonce_sql = 'DELETE FROM %(nonces)s WHERE timestamp < ?;'

    def blobDecode(self, buf):
        return str(buf)

    def blobEncode(self, s):
        return buffer(s)

    def useNonce(self, *args, **kwargs):
        # Older versions of the sqlite wrapper do not raise
        # IntegrityError as they should, so we have to detect the
        # message from the OperationalError.
        try:
            return super(SQLiteStore, self).useNonce(*args, **kwargs)
        except self.exceptions.OperationalError, why:
            if re.match('^columns .* are not unique$', why[0]):
                return False
            else:
                raise

class MySQLStore(SQLStore):
    """
    This is a MySQL-based specialization of C{L{SQLStore}}.

    Uses InnoDB tables for transaction support.

    To create an instance, see C{L{SQLStore.__init__}}.  To create the
    tables it will use, see C{L{SQLStore.createTables}}.

    All other methods are implementation details.
    """

    try:
        import MySQLdb as exceptions
    except ImportError:
        exceptions = None

    create_nonce_sql = """
    CREATE TABLE %(nonces)s (
        server_url BLOB NOT NULL,
        timestamp INTEGER NOT NULL,
        salt CHAR(40) NOT NULL,
        PRIMARY KEY (server_url(255), timestamp, salt)
    )
    ENGINE=InnoDB;
    """

    create_assoc_sql = """
    CREATE TABLE %(associations)s
    (
        server_url BLOB NOT NULL,
        handle VARCHAR(255) NOT NULL,
        secret BLOB NOT NULL,
        issued INTEGER NOT NULL,
        lifetime INTEGER NOT NULL,
        assoc_type VARCHAR(64) NOT NULL,
        PRIMARY KEY (server_url(255), handle)
    )
    ENGINE=InnoDB;
    """

    set_assoc_sql = ('REPLACE INTO %(associations)s '
                     'VALUES (%%s, %%s, %%s, %%s, %%s, %%s);')
    get_assocs_sql = ('SELECT handle, secret, issued, lifetime, assoc_type'
                      ' FROM %(associations)s WHERE server_url = %%s;')
    get_expired_sql = ('SELECT server_url '
                       'FROM %(associations)s WHERE issued + lifetime < %%s;')

    get_assoc_sql = (
        'SELECT handle, secret, issued, lifetime, assoc_type'
        ' FROM %(associations)s WHERE server_url = %%s AND handle = %%s;')
    remove_assoc_sql = ('DELETE FROM %(associations)s '
                        'WHERE server_url = %%s AND handle = %%s;')

    clean_assoc_sql = 'DELETE FROM %(associations)s WHERE issued + lifetime < %%s;'

    add_nonce_sql = 'INSERT INTO %(nonces)s VALUES (%%s, %%s, %%s);'

    clean_nonce_sql = 'DELETE FROM %(nonces)s WHERE timestamp < %%s;'

    def blobDecode(self, blob):
        if type(blob) is str:
            # Versions of MySQLdb >= 1.2.2
            return blob
        else:
            # Versions of MySQLdb prior to 1.2.2 (as far as we can tell)
            return blob.tostring()

class PostgreSQLStore(SQLStore):
    """
    This is a PostgreSQL-based specialization of C{L{SQLStore}}.

    To create an instance, see C{L{SQLStore.__init__}}.  To create the
    tables it will use, see C{L{SQLStore.createTables}}.

    All other methods are implementation details.
    """

    try:
        import psycopg as exceptions
    except ImportError:
        # psycopg2 has the dbapi extension where the exception classes
        # are available on the connection object. A psycopg2
        # connection will use the correct exception classes because of
        # this, and a psycopg connection will fall through to use the
        # psycopg imported above.
        exceptions = None

    create_nonce_sql = """
    CREATE TABLE %(nonces)s (
        server_url VARCHAR(2047) NOT NULL,
        timestamp INTEGER NOT NULL,
        salt CHAR(40) NOT NULL,
        PRIMARY KEY (server_url, timestamp, salt)
    );
    """

    create_assoc_sql = """
    CREATE TABLE %(associations)s
    (
        server_url VARCHAR(2047) NOT NULL,
        handle VARCHAR(255) NOT NULL,
        secret BYTEA NOT NULL,
        issued INTEGER NOT NULL,
        lifetime INTEGER NOT NULL,
        assoc_type VARCHAR(64) NOT NULL,
        PRIMARY KEY (server_url, handle),
        CONSTRAINT secret_length_constraint CHECK (LENGTH(secret) <= 128)
    );
    """

    def db_set_assoc(self, server_url, handle, secret, issued, lifetime, assoc_type):
        """
        Set an association.  This is implemented as a method because
        REPLACE INTO is not supported by PostgreSQL (and is not
        standard SQL).
        """
        result = self.db_get_assoc(server_url, handle)
        rows = self.cur.fetchall()
        if len(rows):
            # Update the table since this associations already exists.
            return self.db_update_assoc(secret, issued, lifetime, assoc_type,
                                        server_url, handle)
        else:
            # Insert a new record because this association wasn't
            # found.
            return self.db_new_assoc(server_url, handle, secret, issued,
                                     lifetime, assoc_type)

    new_assoc_sql = ('INSERT INTO %(associations)s '
                     'VALUES (%%s, %%s, %%s, %%s, %%s, %%s);')
    update_assoc_sql = ('UPDATE %(associations)s SET '
                        'secret = %%s, issued = %%s, '
                        'lifetime = %%s, assoc_type = %%s '
                        'WHERE server_url = %%s AND handle = %%s;')
    get_assocs_sql = ('SELECT handle, secret, issued, lifetime, assoc_type'
                      ' FROM %(associations)s WHERE server_url = %%s;')
    get_expired_sql = ('SELECT server_url '
                       'FROM %(associations)s WHERE issued + lifetime < %%s;')

    get_assoc_sql = (
        'SELECT handle, secret, issued, lifetime, assoc_type'
        ' FROM %(associations)s WHERE server_url = %%s AND handle = %%s;')
    remove_assoc_sql = ('DELETE FROM %(associations)s '
                        'WHERE server_url = %%s AND handle = %%s;')

    clean_assoc_sql = 'DELETE FROM %(associations)s WHERE issued + lifetime < %%s;'

    add_nonce_sql = 'INSERT INTO %(nonces)s VALUES (%%s, %%s, %%s);'

    clean_nonce_sql = 'DELETE FROM %(nonces)s WHERE timestamp < %%s;'

    def blobEncode(self, blob):
        try:
            from psycopg2 import Binary
        except ImportError:
            from psycopg import Binary

        return Binary(blob)

########NEW FILE########
__FILENAME__ = cryptutil
import sys
import random
import os.path

from openid import cryptutil

# Most of the purpose of this test is to make sure that cryptutil can
# find a good source of randomness on this machine.

def test_cryptrand():
    # It's possible, but HIGHLY unlikely that a correct implementation
    # will fail by returning the same number twice

    s = cryptutil.getBytes(32)
    t = cryptutil.getBytes(32)
    assert len(s) == 32
    assert len(t) == 32
    assert s != t

    a = cryptutil.randrange(2L ** 128)
    b = cryptutil.randrange(2L ** 128)
    assert type(a) is long
    assert type(b) is long
    assert b != a

    # Make sure that we can generate random numbers that are larger
    # than platform int size
    cryptutil.randrange(long(sys.maxint) + 1L)

def test_reversed():
    if hasattr(cryptutil, 'reversed'):
        cases = [
            ('', ''),
            ('a', 'a'),
            ('ab', 'ba'),
            ('abc', 'cba'),
            ('abcdefg', 'gfedcba'),
            ([], []),
            ([1], [1]),
            ([1,2], [2,1]),
            ([1,2,3], [3,2,1]),
            (range(1000), range(999, -1, -1)),
            ]

        for case, expected in cases:
            expected = list(expected)
            actual = list(cryptutil.reversed(case))
            assert actual == expected, (case, expected, actual)
            twice = list(cryptutil.reversed(actual))
            assert twice == list(case), (actual, case, twice)

def test_binaryLongConvert():
    MAX = sys.maxint
    for iteration in xrange(500):
        n = 0L
        for i in range(10):
            n += long(random.randrange(MAX))

        s = cryptutil.longToBinary(n)
        assert type(s) is str
        n_prime = cryptutil.binaryToLong(s)
        assert n == n_prime, (n, n_prime)

    cases = [
        ('\x00', 0L),
        ('\x01', 1L),
        ('\x7F', 127L),
        ('\x00\xFF', 255L),
        ('\x00\x80', 128L),
        ('\x00\x81', 129L),
        ('\x00\x80\x00', 32768L),
        ('OpenID is cool', 1611215304203901150134421257416556L)
        ]

    for s, n in cases:
        n_prime = cryptutil.binaryToLong(s)
        s_prime = cryptutil.longToBinary(n)
        assert n == n_prime, (s, n, n_prime)
        assert s == s_prime, (n, s, s_prime)

def test_longToBase64():
    f = file(os.path.join(os.path.dirname(__file__), 'n2b64'))
    try:
        for line in f:
            parts = line.strip().split(' ')
            assert parts[0] == cryptutil.longToBase64(long(parts[1]))
    finally:
        f.close()

def test_base64ToLong():
    f = file(os.path.join(os.path.dirname(__file__), 'n2b64'))
    try:
        for line in f:
            parts = line.strip().split(' ')
            assert long(parts[1]) == cryptutil.base64ToLong(parts[0])
    finally:
        f.close()


def test():
    test_reversed()
    test_binaryLongConvert()
    test_cryptrand()
    test_longToBase64()
    test_base64ToLong()

if __name__ == '__main__':
    test()

########NEW FILE########
__FILENAME__ = datadriven
import unittest
import types

class DataDrivenTestCase(unittest.TestCase):
    cases = []

    def generateCases(cls):
        return cls.cases

    generateCases = classmethod(generateCases)

    def loadTests(cls):
        tests = []
        for case in cls.generateCases():
            if isinstance(case, tuple):
                test = cls(*case)
            elif isinstance(case, dict):
                test = cls(**case)
            else:
                test = cls(case)
            tests.append(test)
        return tests

    loadTests = classmethod(loadTests)

    def __init__(self, description):
        unittest.TestCase.__init__(self, 'runOneTest')
        self.description = description

    def shortDescription(self):
        return '%s for %s' % (self.__class__.__name__, self.description)

def loadTests(module_name):
    loader = unittest.defaultTestLoader
    this_module = __import__(module_name, {}, {}, [None])

    tests = []
    for name in dir(this_module):
        obj = getattr(this_module, name)
        if (isinstance(obj, (type, types.ClassType)) and
            issubclass(obj, unittest.TestCase)):
            if hasattr(obj, 'loadTests'):
                tests.extend(obj.loadTests())
            else:
                tests.append(loader.loadTestsFromTestCase(obj))

    return unittest.TestSuite(tests)

########NEW FILE########
__FILENAME__ = dh
import os.path
from openid.dh import DiffieHellman, strxor

def test_strxor():
    NUL = '\x00'

    cases = [
        (NUL, NUL, NUL),
        ('\x01', NUL, '\x01'),
        ('a', 'a', NUL),
        ('a', NUL, 'a'),
        ('abc', NUL * 3, 'abc'),
        ('x' * 10, NUL * 10, 'x' * 10),
        ('\x01', '\x02', '\x03'),
        ('\xf0', '\x0f', '\xff'),
        ('\xff', '\x0f', '\xf0'),
        ]

    for aa, bb, expected in cases:
        actual = strxor(aa, bb)
        assert actual == expected, (aa, bb, expected, actual)

    exc_cases = [
        ('', 'a'),
        ('foo', 'ba'),
        (NUL * 3, NUL * 4),
        (''.join(map(chr, xrange(256))),
         ''.join(map(chr, xrange(128)))),
        ]

    for aa, bb in exc_cases:
        try:
            unexpected = strxor(aa, bb)
        except ValueError:
            pass
        else:
            assert False, 'Expected ValueError, got %r' % (unexpected,)

def test1():
    dh1 = DiffieHellman.fromDefaults()
    dh2 = DiffieHellman.fromDefaults()
    secret1 = dh1.getSharedSecret(dh2.public)
    secret2 = dh2.getSharedSecret(dh1.public)
    assert secret1 == secret2
    return secret1

def test_exchange():
    s1 = test1()
    s2 = test1()
    assert s1 != s2

def test_public():
    f = file(os.path.join(os.path.dirname(__file__), 'dhpriv'))
    dh = DiffieHellman.fromDefaults()
    try:
        for line in f:
            parts = line.strip().split(' ')
            dh._setPrivate(long(parts[0]))

            assert dh.public == long(parts[1])
    finally:
        f.close()

def test():
    test_exchange()
    test_public()
    test_strxor()

if __name__ == '__main__':
    test()

########NEW FILE########
__FILENAME__ = discoverdata
"""Module to make discovery data test cases available"""
import urlparse
import os.path

from openid.yadis.discover import DiscoveryResult, DiscoveryFailure
from openid.yadis.constants import YADIS_HEADER_NAME

tests_dir = os.path.dirname(__file__)
data_path = os.path.join(tests_dir, 'data')

testlist = [
# success,  input_name,          id_name,            result_name
    (True,  "equiv",             "equiv",            "xrds"),
    (True,  "header",            "header",           "xrds"),
    (True,  "lowercase_header",  "lowercase_header", "xrds"),
    (True,  "xrds",              "xrds",             "xrds"),
    (True,  "xrds_ctparam",      "xrds_ctparam",     "xrds_ctparam"),
    (True,  "xrds_ctcase",       "xrds_ctcase",      "xrds_ctcase"),
    (False, "xrds_html",         "xrds_html",        "xrds_html"),
    (True,  "redir_equiv",       "equiv",            "xrds"),
    (True,  "redir_header",      "header",           "xrds"),
    (True,  "redir_xrds",        "xrds",             "xrds"),
    (False, "redir_xrds_html",   "xrds_html",        "xrds_html"),
    (True,  "redir_redir_equiv", "equiv",            "xrds"),
    (False, "404_server_response", None,             None),
    (False, "404_with_header",     None,             None),
    (False, "404_with_meta",       None,             None),
    (False, "201_server_response", None,             None),
    (False, "500_server_response", None,             None),
    ]

def getDataName(*components):
    sanitized = []
    for part in components:
        if part in ['.', '..']:
            raise ValueError
        elif part:
            sanitized.append(part)

    if not sanitized:
        raise ValueError

    return os.path.join(data_path, *sanitized)

def getExampleXRDS():
    filename = getDataName('example-xrds.xml')
    return file(filename).read()

example_xrds = getExampleXRDS()
default_test_file = getDataName('test1-discover.txt')

discover_tests = {}

def readTests(filename):
    data = file(filename).read()
    tests = {}
    for case in data.split('\f\n'):
        (name, content) = case.split('\n', 1)
        tests[name] = content
    return tests

def getData(filename, name):
    global discover_tests
    try:
        file_tests = discover_tests[filename]
    except KeyError:
        file_tests = discover_tests[filename] = readTests(filename)
    return file_tests[name]

def fillTemplate(test_name, template, base_url, example_xrds):
    mapping = [
        ('URL_BASE/', base_url),
        ('<XRDS Content>', example_xrds),
        ('YADIS_HEADER', YADIS_HEADER_NAME),
        ('NAME', test_name),
        ]

    for k, v in mapping:
        template = template.replace(k, v)

    return template

def generateSample(test_name, base_url,
                   example_xrds=example_xrds,
                   filename=default_test_file):
    try:
        template = getData(filename, test_name)
    except IOError, why:
        import errno
        if why[0] == errno.ENOENT:
            raise KeyError(filename)
        else:
            raise

    return fillTemplate(test_name, template, base_url, example_xrds)

def generateResult(base_url, input_name, id_name, result_name, success):
    input_url = urlparse.urljoin(base_url, input_name)

    # If the name is None then we expect the protocol to fail, which
    # we represent by None
    if id_name is None:
        assert result_name is None
        return input_url, DiscoveryFailure

    result = generateSample(result_name, base_url)
    headers, content = result.split('\n\n', 1)
    header_lines = headers.split('\n')
    for header_line in header_lines:
        if header_line.startswith('Content-Type:'):
            _, ctype = header_line.split(':', 1)
            ctype = ctype.strip()
            break
    else:
        ctype = None

    id_url = urlparse.urljoin(base_url, id_name)

    result = DiscoveryResult(input_url)
    result.normalized_uri = id_url
    if success:
        result.xrds_uri = urlparse.urljoin(base_url, result_name)
    result.content_type = ctype
    result.response_text = content
    return input_url, result

########NEW FILE########
__FILENAME__ = kvform
from openid import kvform
from openid.test.support import CatchLogs
import unittest

class KVBaseTest(unittest.TestCase, CatchLogs):
    def shortDescription(self):
        return '%s test for %r' % (self.__class__.__name__, self.kvform)

    def checkWarnings(self, num_warnings):
        self.failUnlessEqual(num_warnings, len(self.messages), repr(self.messages))

    def setUp(self):
        CatchLogs.setUp(self)

    def tearDown(self):
        CatchLogs.tearDown(self)

class KVDictTest(KVBaseTest):
    def __init__(self, kv, dct, warnings):
        unittest.TestCase.__init__(self)
        self.kvform = kv
        self.dict = dct
        self.expected_warnings = warnings

    def runTest(self):
        # Convert KVForm to dict
        d = kvform.kvToDict(self.kvform)

        # make sure it parses to expected dict
        self.failUnlessEqual(self.dict, d)

        # Check to make sure we got the expected number of warnings
        self.checkWarnings(self.expected_warnings)

        # Convert back to KVForm and round-trip back to dict to make
        # sure that *** dict -> kv -> dict is identity. ***
        kv = kvform.dictToKV(d)
        d2 = kvform.kvToDict(kv)
        self.failUnlessEqual(d, d2)

class KVSeqTest(KVBaseTest):
    def __init__(self, seq, kv, expected_warnings):
        unittest.TestCase.__init__(self)
        self.kvform = kv
        self.seq = seq
        self.expected_warnings = expected_warnings

    def cleanSeq(self, seq):
        """Create a new sequence by stripping whitespace from start
        and end of each value of each pair"""
        clean = []
        for k, v in self.seq:
            if type(k) is str:
                k = k.decode('utf8')
            if type(v) is str:
                v = v.decode('utf8')
            clean.append((k.strip(), v.strip()))
        return clean

    def runTest(self):
        # seq serializes to expected kvform
        actual = kvform.seqToKV(self.seq)
        self.failUnlessEqual(self.kvform, actual)
        self.failUnless(type(actual) is str)

        # Parse back to sequence. Expected to be unchanged, except
        # stripping whitespace from start and end of values
        # (i. e. ordering, case, and internal whitespace is preserved)
        seq = kvform.kvToSeq(actual)
        clean_seq = self.cleanSeq(seq)

        self.failUnlessEqual(seq, clean_seq)
        self.checkWarnings(self.expected_warnings)

kvdict_cases = [
    # (kvform, parsed dictionary, expected warnings)
    ('', {}, 0),
    ('college:harvey mudd\n', {'college':'harvey mudd'}, 0),
    ('city:claremont\nstate:CA\n',
     {'city':'claremont', 'state':'CA'}, 0),
    ('is_valid:true\ninvalidate_handle:{HMAC-SHA1:2398410938412093}\n',
     {'is_valid':'true',
      'invalidate_handle':'{HMAC-SHA1:2398410938412093}'}, 0),

    # Warnings from lines with no colon:
    ('x\n', {}, 1),
    ('x\nx\n', {}, 2),
    ('East is least\n', {}, 1),

    # But not from blank lines (because LJ generates them)
    ('x\n\n', {}, 1),

    # Warning from empty key
    (':\n', {'':''}, 1),
    (':missing key\n', {'':'missing key'}, 1),

    # Warnings from leading or trailing whitespace in key or value
    (' street:foothill blvd\n', {'street':'foothill blvd'}, 1),
    ('major: computer science\n', {'major':'computer science'}, 1),
    (' dorm : east \n', {'dorm':'east'}, 2),

    # Warnings from missing trailing newline
    ('e^(i*pi)+1:0', {'e^(i*pi)+1':'0'}, 1),
    ('east:west\nnorth:south', {'east':'west', 'north':'south'}, 1),
    ]

kvseq_cases = [
    ([], '', 0),

    # Make sure that we handle non-ascii characters (also wider than 8 bits)
    ([(u'\u03bbx', u'x')], '\xce\xbbx:x\n', 0),

    # If it's a UTF-8 str, make sure that it's equivalent to the same
    # string, decoded.
    ([('\xce\xbbx', 'x')], '\xce\xbbx:x\n', 0),

    ([('openid', 'useful'), ('a', 'b')], 'openid:useful\na:b\n', 0),

    # Warnings about leading whitespace
    ([(' openid', 'useful'), ('a', 'b')], ' openid:useful\na:b\n', 2),

    # Warnings about leading and trailing whitespace
    ([(' openid ', ' useful '),
      (' a ', ' b ')], ' openid : useful \n a : b \n', 8),

    # warnings about leading and trailing whitespace, but not about
    # internal whitespace.
    ([(' open id ', ' use ful '),
      (' a ', ' b ')], ' open id : use ful \n a : b \n', 8),

    ([(u'foo', 'bar')], 'foo:bar\n', 0),
    ]

kvexc_cases = [
    [('openid', 'use\nful')],
    [('open\nid', 'useful')],
    [('open\nid', 'use\nful')],
    [('open:id', 'useful')],
    [('foo', 'bar'), ('ba\n d', 'seed')],
    [('foo', 'bar'), ('bad:', 'seed')],
    ]

class KVExcTest(unittest.TestCase):
    def __init__(self, seq):
        unittest.TestCase.__init__(self)
        self.seq = seq

    def shortDescription(self):
        return 'KVExcTest for %r' % (self.seq,)

    def runTest(self):
        self.failUnlessRaises(ValueError, kvform.seqToKV, self.seq)

class GeneralTest(KVBaseTest):
    kvform = '<None>'

    def test_convert(self):
        result = kvform.seqToKV([(1,1)])
        self.failUnlessEqual(result, '1:1\n')
        self.checkWarnings(2)

def pyUnitTests():
    tests = [KVDictTest(*case) for case in kvdict_cases]
    tests.extend([KVSeqTest(*case) for case in kvseq_cases])
    tests.extend([KVExcTest(case) for case in kvexc_cases])
    tests.append(unittest.defaultTestLoader.loadTestsFromTestCase(GeneralTest))
    return unittest.TestSuite(tests)

if __name__ == '__main__':
    suite = pyUnitTests()
    runner = unittest.TextTestRunner()
    runner.run(suite)

########NEW FILE########
__FILENAME__ = linkparse
from openid.consumer.html_parse import parseLinkAttrs
import os.path
import codecs
import unittest

def parseLink(line):
    parts = line.split()
    optional = parts[0] == 'Link*:'
    assert optional or parts[0] == 'Link:'

    attrs = {}
    for attr in parts[1:]:
        k, v = attr.split('=', 1)
        if k[-1] == '*':
            attr_optional = 1
            k = k[:-1]
        else:
            attr_optional = 0

        attrs[k] = (attr_optional, v)

    return (optional, attrs)

def parseCase(s):
    header, markup = s.split('\n\n', 1)
    lines = header.split('\n')
    name = lines.pop(0)
    assert name.startswith('Name: ')
    desc = name[6:]
    return desc, markup, map(parseLink, lines)

def parseTests(s):
    tests = []

    cases = s.split('\n\n\n')
    header = cases.pop(0)
    tests_line, _ = header.split('\n', 1)
    k, v = tests_line.split(': ')
    assert k == 'Num Tests'
    num_tests = int(v)

    for case in cases[:-1]:
        desc, markup, links = parseCase(case)
        tests.append((desc, markup, links, case))

    return num_tests, tests

class _LinkTest(unittest.TestCase):
    def __init__(self, desc, case, expected, raw):
        unittest.TestCase.__init__(self)
        self.desc = desc
        self.case = case
        self.expected = expected
        self.raw = raw

    def shortDescription(self):
        return self.desc

    def runTest(self):
        actual = parseLinkAttrs(self.case)
        i = 0
        for optional, exp_link in self.expected:
            if optional:
                if i >= len(actual):
                    continue

            act_link = actual[i]
            for k, (o, v) in exp_link.items():
                if o:
                    act_v = act_link.get(k)
                    if act_v is None:
                        continue
                else:
                    act_v = act_link[k]

                if optional and v != act_v:
                    break

                self.assertEqual(v, act_v)
            else:
                i += 1

        assert i == len(actual)

def pyUnitTests():
    here = os.path.dirname(os.path.abspath(__file__))
    test_data_file_name = os.path.join(here, 'linkparse.txt')
    test_data_file = codecs.open(test_data_file_name, 'r', 'utf-8')
    test_data = test_data_file.read()
    test_data_file.close()

    num_tests, test_cases = parseTests(test_data)

    tests = [_LinkTest(*case) for case in test_cases]

    def test_parseSucceeded():
        assert len(test_cases) == num_tests, (len(test_cases), num_tests)

    check_desc = 'Check that we parsed the correct number of test cases'
    check = unittest.FunctionTestCase(
        test_parseSucceeded, description=check_desc)
    tests.insert(0, check)

    return unittest.TestSuite(tests)

if __name__ == '__main__':
    suite = pyUnitTests()
    runner = unittest.TextTestRunner()
    runner.run(suite)

########NEW FILE########
__FILENAME__ = oidutil
# -*- coding: utf-8 -*-
import unittest
import codecs
import string
import random
from openid import oidutil

def test_base64():
    allowed_s = string.ascii_letters + string.digits + '+/='
    allowed_d = {}
    for c in allowed_s:
        allowed_d[c] = None
    isAllowed = allowed_d.has_key

    def checkEncoded(s):
        for c in s:
            assert isAllowed(c), s

    cases = [
        '',
        'x',
        '\x00',
        '\x01',
        '\x00' * 100,
        ''.join(map(chr, range(256))),
        ]

    for s in cases:
        b64 = oidutil.toBase64(s)
        checkEncoded(b64)
        s_prime = oidutil.fromBase64(b64)
        assert s_prime == s, (s, b64, s_prime)

    # Randomized test
    for _ in xrange(50):
        n = random.randrange(2048)
        s = ''.join(map(chr, map(lambda _: random.randrange(256), range(n))))
        b64 = oidutil.toBase64(s)
        checkEncoded(b64)
        s_prime = oidutil.fromBase64(b64)
        assert s_prime == s, (s, b64, s_prime)

class AppendArgsTest(unittest.TestCase):
    def __init__(self, desc, args, expected):
        unittest.TestCase.__init__(self)
        self.desc = desc
        self.args = args
        self.expected = expected

    def runTest(self):
        result = oidutil.appendArgs(*self.args)
        self.assertEqual(self.expected, result, self.args)

    def shortDescription(self):
        return self.desc

class TestUnicodeConversion(unittest.TestCase):

    def test_toUnicode(self):
        # Unicode objects pass through
        self.failUnless(isinstance(oidutil.toUnicode(u'fööbär'), unicode))
        self.assertEquals(oidutil.toUnicode(u'fööbär'), u'fööbär')
        # UTF-8 encoded string are decoded
        self.failUnless(isinstance(oidutil.toUnicode('fööbär'), unicode))
        self.assertEquals(oidutil.toUnicode('fööbär'), u'fööbär')
        # Other encodings raise exceptions
        self.assertRaises(UnicodeDecodeError, lambda: oidutil.toUnicode(u'fööbär'.encode('latin-1')))

class TestSymbol(unittest.TestCase):
    def testCopyHash(self):
        import copy
        s = oidutil.Symbol("Foo")
        d = {s: 1}
        d_prime = copy.deepcopy(d)
        self.failUnless(s in d_prime, "%r isn't in %r" % (s, d_prime))

        t = oidutil.Symbol("Bar")
        self.failIfEqual(hash(s), hash(t))


def buildAppendTests():
    simple = 'http://www.example.com/'
    cases = [
        ('empty list',
         (simple, []),
         simple),

        ('empty dict',
         (simple, {}),
         simple),

        ('one list',
         (simple, [('a', 'b')]),
         simple + '?a=b'),

        ('one dict',
         (simple, {'a':'b'}),
         simple + '?a=b'),

        ('two list (same)',
         (simple, [('a', 'b'), ('a', 'c')]),
         simple + '?a=b&a=c'),

        ('two list',
         (simple, [('a', 'b'), ('b', 'c')]),
         simple + '?a=b&b=c'),

        ('two list (order)',
         (simple, [('b', 'c'), ('a', 'b')]),
         simple + '?b=c&a=b'),

        ('two dict (order)',
         (simple, {'b':'c', 'a':'b'}),
         simple + '?a=b&b=c'),

        ('escape',
         (simple, [('=', '=')]),
         simple + '?%3D=%3D'),

        ('escape (URL)',
         (simple, [('this_url', simple)]),
         simple + '?this_url=http%3A%2F%2Fwww.example.com%2F'),

        ('use dots',
         (simple, [('openid.stuff', 'bother')]),
         simple + '?openid.stuff=bother'),

        ('args exist (empty)',
         (simple + '?stuff=bother', []),
         simple + '?stuff=bother'),

        ('args exist',
         (simple + '?stuff=bother', [('ack', 'ack')]),
         simple + '?stuff=bother&ack=ack'),

        ('args exist',
         (simple + '?stuff=bother', [('ack', 'ack')]),
         simple + '?stuff=bother&ack=ack'),

        ('args exist (dict)',
         (simple + '?stuff=bother', {'ack': 'ack'}),
         simple + '?stuff=bother&ack=ack'),

        ('args exist (dict 2)',
         (simple + '?stuff=bother', {'ack': 'ack', 'zebra':'lion'}),
         simple + '?stuff=bother&ack=ack&zebra=lion'),

        ('three args (dict)',
         (simple, {'stuff': 'bother', 'ack': 'ack', 'zebra':'lion'}),
         simple + '?ack=ack&stuff=bother&zebra=lion'),

        ('three args (list)',
         (simple, [('stuff', 'bother'), ('ack', 'ack'), ('zebra', 'lion')]),
         simple + '?stuff=bother&ack=ack&zebra=lion'),
        ]

    tests = []

    for name, args, expected in cases:
        test = AppendArgsTest(name, args, expected)
        tests.append(test)

    return unittest.TestSuite(tests)

def pyUnitTests():
    some = buildAppendTests()
    some.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(TestSymbol))
    some.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(TestUnicodeConversion))
    return some

def test_appendArgs():
    suite = buildAppendTests()
    suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(TestSymbol))
    runner = unittest.TextTestRunner()
    result = runner.run(suite)
    assert result.wasSuccessful()

# XXX: there are more functions that could benefit from being better
# specified and tested in oidutil.py These include, but are not
# limited to appendArgs

def test(skipPyUnit=True):
    test_base64()
    if not skipPyUnit:
        test_appendArgs()

if __name__ == '__main__':
    test(skipPyUnit=False)

########NEW FILE########
__FILENAME__ = storetest
from openid.association import Association
from openid.cryptutil import randomString
from openid.store.nonce import mkNonce, split

import unittest
import string
import time
import socket
import random
import os

db_host = 'dbtest'

allowed_handle = []
for c in string.printable:
    if c not in string.whitespace:
        allowed_handle.append(c)
allowed_handle = ''.join(allowed_handle)

def generateHandle(n):
    return randomString(n, allowed_handle)

generateSecret = randomString

def getTmpDbName():
    hostname = socket.gethostname()
    hostname = hostname.replace('.', '_')
    hostname = hostname.replace('-', '_')
    return "%s_%d_%s_openid_test" % \
           (hostname, os.getpid(), \
            random.randrange(1, int(time.time())))

def testStore(store):
    """Make sure a given store has a minimum of API compliance. Call
    this function with an empty store.

    Raises AssertionError if the store does not work as expected.

    OpenIDStore -> NoneType
    """
    ### Association functions
    now = int(time.time())

    server_url = 'http://www.myopenid.com/openid'
    def genAssoc(issued, lifetime=600):
        sec = generateSecret(20)
        hdl = generateHandle(128)
        return Association(hdl, sec, now + issued, lifetime, 'HMAC-SHA1')

    def checkRetrieve(url, handle=None, expected=None):
        retrieved_assoc = store.getAssociation(url, handle)
        assert retrieved_assoc == expected, (retrieved_assoc, expected)
        if expected is not None:
            if retrieved_assoc is expected:
                print ('Unexpected: retrieved a reference to the expected '
                       'value instead of a new object')
            assert retrieved_assoc.handle == expected.handle
            assert retrieved_assoc.secret == expected.secret

    def checkRemove(url, handle, expected):
        present = store.removeAssociation(url, handle)
        assert bool(expected) == bool(present)

    assoc = genAssoc(issued=0)

    # Make sure that a missing association returns no result
    checkRetrieve(server_url)

    # Check that after storage, getting returns the same result
    store.storeAssociation(server_url, assoc)
    checkRetrieve(server_url, None, assoc)

    # more than once
    checkRetrieve(server_url, None, assoc)

    # Storing more than once has no ill effect
    store.storeAssociation(server_url, assoc)
    checkRetrieve(server_url, None, assoc)

    # Removing an association that does not exist returns not present
    checkRemove(server_url, assoc.handle + 'x', False)

    # Removing an association that does not exist returns not present
    checkRemove(server_url + 'x', assoc.handle, False)

    # Removing an association that is present returns present
    checkRemove(server_url, assoc.handle, True)

    # but not present on subsequent calls
    checkRemove(server_url, assoc.handle, False)

    # Put assoc back in the store
    store.storeAssociation(server_url, assoc)

    # More recent and expires after assoc
    assoc2 = genAssoc(issued=1)
    store.storeAssociation(server_url, assoc2)

    # After storing an association with a different handle, but the
    # same server_url, the handle with the later issue date is returned.
    checkRetrieve(server_url, None, assoc2)

    # We can still retrieve the older association
    checkRetrieve(server_url, assoc.handle, assoc)

    # Plus we can retrieve the association with the later issue date
    # explicitly
    checkRetrieve(server_url, assoc2.handle, assoc2)

    # More recent, and expires earlier than assoc2 or assoc. Make sure
    # that we're picking the one with the latest issued date and not
    # taking into account the expiration.
    assoc3 = genAssoc(issued=2, lifetime=100)
    store.storeAssociation(server_url, assoc3)

    checkRetrieve(server_url, None, assoc3)
    checkRetrieve(server_url, assoc.handle, assoc)
    checkRetrieve(server_url, assoc2.handle, assoc2)
    checkRetrieve(server_url, assoc3.handle, assoc3)

    checkRemove(server_url, assoc2.handle, True)

    checkRetrieve(server_url, None, assoc3)
    checkRetrieve(server_url, assoc.handle, assoc)
    checkRetrieve(server_url, assoc2.handle, None)
    checkRetrieve(server_url, assoc3.handle, assoc3)

    checkRemove(server_url, assoc2.handle, False)
    checkRemove(server_url, assoc3.handle, True)

    checkRetrieve(server_url, None, assoc)
    checkRetrieve(server_url, assoc.handle, assoc)
    checkRetrieve(server_url, assoc2.handle, None)
    checkRetrieve(server_url, assoc3.handle, None)

    checkRemove(server_url, assoc2.handle, False)
    checkRemove(server_url, assoc.handle, True)
    checkRemove(server_url, assoc3.handle, False)

    checkRetrieve(server_url, None, None)
    checkRetrieve(server_url, assoc.handle, None)
    checkRetrieve(server_url, assoc2.handle, None)
    checkRetrieve(server_url, assoc3.handle, None)

    checkRemove(server_url, assoc2.handle, False)
    checkRemove(server_url, assoc.handle, False)
    checkRemove(server_url, assoc3.handle, False)

    ### test expired associations
    # assoc 1: server 1, valid
    # assoc 2: server 1, expired
    # assoc 3: server 2, expired
    # assoc 4: server 3, valid
    assocValid1 = genAssoc(issued=-3600,lifetime=7200)
    assocValid2 = genAssoc(issued=-5)
    assocExpired1 = genAssoc(issued=-7200,lifetime=3600)
    assocExpired2 = genAssoc(issued=-7200,lifetime=3600)

    store.cleanupAssociations()
    store.storeAssociation(server_url + '1', assocValid1)
    store.storeAssociation(server_url + '1', assocExpired1)
    store.storeAssociation(server_url + '2', assocExpired2)
    store.storeAssociation(server_url + '3', assocValid2)

    cleaned = store.cleanupAssociations()
    assert cleaned == 2, cleaned

    ### Nonce functions

    def checkUseNonce(nonce, expected, server_url, msg=''):
        stamp, salt = split(nonce)
        actual = store.useNonce(server_url, stamp, salt)
        assert bool(actual) == bool(expected), "%r != %r: %s" % (actual, expected,
                                                                 msg)

    for url in [server_url, '']:
        # Random nonce (not in store)
        nonce1 = mkNonce()

        # A nonce is allowed by default
        checkUseNonce(nonce1, True, url)

        # Storing once causes useNonce to return True the first, and only
        # the first, time it is called after the store.
        checkUseNonce(nonce1, False, url)
        checkUseNonce(nonce1, False, url)

        # Nonces from when the universe was an hour old should not pass these days.
        old_nonce = mkNonce(3600)
        checkUseNonce(old_nonce, False, url, "Old nonce (%r) passed." % (old_nonce,))


    old_nonce1 = mkNonce(now - 20000)
    old_nonce2 = mkNonce(now - 10000)
    recent_nonce = mkNonce(now - 600)

    from openid.store import nonce as nonceModule
    orig_skew = nonceModule.SKEW
    try:
        nonceModule.SKEW = 0
        store.cleanupNonces()
        # Set SKEW high so stores will keep our nonces.
        nonceModule.SKEW = 100000
        assert store.useNonce(server_url, *split(old_nonce1))
        assert store.useNonce(server_url, *split(old_nonce2))
        assert store.useNonce(server_url, *split(recent_nonce))

        nonceModule.SKEW = 3600
        cleaned = store.cleanupNonces()
        assert cleaned == 2, "Cleaned %r nonces." % (cleaned,)

        nonceModule.SKEW = 100000
        # A roundabout method of checking that the old nonces were cleaned is
        # to see if we're allowed to add them again.
        assert store.useNonce(server_url, *split(old_nonce1))
        assert store.useNonce(server_url, *split(old_nonce2))
        # The recent nonce wasn't cleaned, so it should still fail.
        assert not store.useNonce(server_url, *split(recent_nonce))
    finally:
        nonceModule.SKEW = orig_skew


def test_filestore():
    from openid.store import filestore
    import tempfile
    import shutil
    try:
        temp_dir = tempfile.mkdtemp()
    except AttributeError:
        import os
        temp_dir = os.tmpnam()
        os.mkdir(temp_dir)

    store = filestore.FileOpenIDStore(temp_dir)
    try:
        testStore(store)
        store.cleanup()
    except:
        raise
    else:
        shutil.rmtree(temp_dir)

def test_sqlite():
    from openid.store import sqlstore
    try:
        from pysqlite2 import dbapi2 as sqlite
    except ImportError:
        pass
    else:
        conn = sqlite.connect(':memory:')
        store = sqlstore.SQLiteStore(conn)
        store.createTables()
        testStore(store)

def test_mysql():
    from openid.store import sqlstore
    try:
        import MySQLdb
    except ImportError:
        pass
    else:
        db_user = 'openid_test'
        db_passwd = ''
        db_name = getTmpDbName()

        from MySQLdb.constants import ER

        # Change this connect line to use the right user and password
        try:
            conn = MySQLdb.connect(user=db_user, passwd=db_passwd, host = db_host)
        except MySQLdb.OperationalError, why:
            if why[0] == 2005:
                print ('Skipping MySQL store test (cannot connect '
                       'to test server on host %r)' % (db_host,))
                return
            else:
                raise

        conn.query('CREATE DATABASE %s;' % db_name)
        try:
            conn.query('USE %s;' % db_name)

            # OK, we're in the right environment. Create store and
            # create the tables.
            store = sqlstore.MySQLStore(conn)
            store.createTables()

            # At last, we get to run the test.
            testStore(store)
        finally:
            # Remove the database. If you want to do post-mortem on a
            # failing test, comment out this line.
            conn.query('DROP DATABASE %s;' % db_name)

def test_postgresql():
    """
    Tests the PostgreSQLStore on a locally-hosted PostgreSQL database
    cluster, version 7.4 or later.  To run this test, you must have:

    - The 'psycopg' python module (version 1.1) installed

    - PostgreSQL running locally

    - An 'openid_test' user account in your database cluster, which
      you can create by running 'createuser -Ad openid_test' as the
      'postgres' user

    - Trust auth for the 'openid_test' account, which you can activate
      by adding the following line to your pg_hba.conf file:

      local all openid_test trust

    This test connects to the database cluster three times:

    - To the 'template1' database, to create the test database

    - To the test database, to run the store tests

    - To the 'template1' database once more, to drop the test database
    """
    from openid.store import sqlstore
    try:
        import psycopg
    except ImportError:
        pass
    else:
        db_name = getTmpDbName()
        db_user = 'openid_test'

        # Connect once to create the database; reconnect to access the
        # new database.
        conn_create = psycopg.connect(database = 'template1', user = db_user,
                                      host = db_host)
        conn_create.autocommit()

        # Create the test database.
        cursor = conn_create.cursor()
        cursor.execute('CREATE DATABASE %s;' % (db_name,))
        conn_create.close()

        # Connect to the test database.
        conn_test = psycopg.connect(database = db_name, user = db_user,
                                    host = db_host)

        # OK, we're in the right environment. Create the store
        # instance and create the tables.
        store = sqlstore.PostgreSQLStore(conn_test)
        store.createTables()

        # At last, we get to run the test.
        testStore(store)

        # Disconnect.
        conn_test.close()

        # It takes a little time for the close() call above to take
        # effect, so we'll wait for a second before trying to remove
        # the database.  (Maybe this is because we're using a UNIX
        # socket to connect to postgres rather than TCP?)
        import time
        time.sleep(1)

        # Remove the database now that the test is over.
        conn_remove = psycopg.connect(database = 'template1', user = db_user,
                                      host = db_host)
        conn_remove.autocommit()

        cursor = conn_remove.cursor()
        cursor.execute('DROP DATABASE %s;' % (db_name,))
        conn_remove.close()

def test_memstore():
    from openid.store import memstore
    testStore(memstore.MemoryStore())

test_functions = [
    test_filestore,
    test_sqlite,
    test_mysql,
    test_postgresql,
    test_memstore,
    ]

def pyUnitTests():
    tests = map(unittest.FunctionTestCase, test_functions)
    load = unittest.defaultTestLoader.loadTestsFromTestCase
    return unittest.TestSuite(tests)

if __name__ == '__main__':
    import sys
    suite = pyUnitTests()
    runner = unittest.TextTestRunner()
    result = runner.run(suite)
    if result.wasSuccessful():
        sys.exit(0)
    else:
        sys.exit(1)

########NEW FILE########
__FILENAME__ = support
from openid import message
from logging.handlers import BufferingHandler
import logging

class TestHandler(BufferingHandler):
    def __init__(self, messages):
        BufferingHandler.__init__(self, 0)
	self.messages = messages

    def shouldFlush(self):
        return False

    def emit(self, record):
        self.messages.append(record.__dict__)

class OpenIDTestMixin(object):
    def failUnlessOpenIDValueEquals(self, msg, key, expected, ns=None):
        if ns is None:
            ns = message.OPENID_NS

        actual = msg.getArg(ns, key)
        error_format = 'Wrong value for openid.%s: expected=%s, actual=%s'
        error_message = error_format % (key, expected, actual)
        self.failUnlessEqual(expected, actual, error_message)

    def failIfOpenIDKeyExists(self, msg, key, ns=None):
        if ns is None:
            ns = message.OPENID_NS

        actual = msg.getArg(ns, key)
        error_message = 'openid.%s unexpectedly present: %s' % (key, actual)
        self.failIf(actual is not None, error_message)

class CatchLogs(object):
    def setUp(self):
	self.messages = []
	root_logger = logging.getLogger()
	self.old_log_level = root_logger.getEffectiveLevel()
	root_logger.setLevel(logging.DEBUG)

	self.handler = TestHandler(self.messages)
	formatter = logging.Formatter("%(message)s [%(asctime)s - %(name)s - %(levelname)s]")
	self.handler.setFormatter(formatter)
	root_logger.addHandler(self.handler)

    def tearDown(self):
        root_logger = logging.getLogger()
	root_logger.removeHandler(self.handler)
	root_logger.setLevel(self.old_log_level)

    def failUnlessLogMatches(self, *prefixes):
        """
        Check that the log messages contained in self.messages have
        prefixes in *prefixes.  Raise AssertionError if not, or if the
        number of prefixes is different than the number of log
        messages.
        """
	messages = [r['msg'] for r in self.messages]
	assert len(prefixes) == len(messages), \
               "Expected log prefixes %r, got %r" % (prefixes,
                                                     messages)

        for prefix, message in zip(prefixes, messages):
            assert message.startswith(prefix), \
                   "Expected log prefixes %r, got %r" % (prefixes,
                                                         messages)

    def failUnlessLogEmpty(self):
        self.failUnlessLogMatches()

########NEW FILE########
__FILENAME__ = test_accept
import unittest
import os.path
from openid.yadis import accept

def getTestData():
    """Read the test data off of disk

    () -> [(int, str)]
    """
    filename = os.path.join(os.path.dirname(__file__), 'data', 'accept.txt')
    i = 1
    lines = []
    for line in file(filename):
        lines.append((i, line))
        i += 1
    return lines

def chunk(lines):
    """Return groups of lines separated by whitespace or comments

    [(int, str)] -> [[(int, str)]]
    """
    chunks = []
    chunk = []
    for lineno, line in lines:
        stripped = line.strip()
        if not stripped or stripped[0] == '#':
            if chunk:
                chunks.append(chunk)
                chunk = []
        else:
            chunk.append((lineno, stripped))

    if chunk:
        chunks.append(chunk)

    return chunks

def parseLines(chunk):
    """Take the given chunk of lines and turn it into a test data dictionary

    [(int, str)] -> {str:(int, str)}
    """
    items = {}
    for (lineno, line) in chunk:
        header, data = line.split(':', 1)
        header = header.lower()
        items[header] = (lineno, data.strip())

    return items

def parseAvailable(available_text):
    """Parse an Available: line's data

    str -> [str]
    """
    return [s.strip() for s in available_text.split(',')]

def parseExpected(expected_text):
    """Parse an Expected: line's data

    str -> [(str, float)]
    """
    expected = []
    if expected_text:
        for chunk in expected_text.split(','):
            chunk = chunk.strip()
            mtype, qstuff = chunk.split(';')
            mtype = mtype.strip()
            assert '/' in mtype
            qstuff = qstuff.strip()
            q, qstr = qstuff.split('=')
            assert q == 'q'
            qval = float(qstr)
            expected.append((mtype, qval))

    return expected

class MatchAcceptTest(unittest.TestCase):
    def __init__(self, descr, accept_header, available, expected):
        unittest.TestCase.__init__(self)
        self.accept_header = accept_header
        self.available = available
        self.expected = expected
        self.descr = descr

    def shortDescription(self):
        return self.descr

    def runTest(self):
        accepted = accept.parseAcceptHeader(self.accept_header)
        actual = accept.matchTypes(accepted, self.available)
        self.failUnlessEqual(self.expected, actual)

def pyUnitTests():
    lines = getTestData()
    chunks = chunk(lines)
    data_sets = map(parseLines, chunks)
    cases = []
    for data in data_sets:
        lnos = []
        lno, header = data['accept']
        lnos.append(lno)
        lno, avail_data = data['available']
        lnos.append(lno)
        try:
            available = parseAvailable(avail_data)
        except:
            print 'On line', lno
            raise

        lno, exp_data = data['expected']
        lnos.append(lno)
        try:
            expected = parseExpected(exp_data)
        except:
            print 'On line', lno
            raise

        descr = 'MatchAcceptTest for lines %r' % (lnos,)
        case = MatchAcceptTest(descr, header, available, expected)
        cases.append(case)
    return unittest.TestSuite(cases)

if __name__ == '__main__':
    runner = unittest.TextTestRunner()
    runner.run(pyUnitTests())

########NEW FILE########
__FILENAME__ = test_association
from openid.test import datadriven

import unittest

from openid.message import Message, BARE_NS, OPENID_NS, OPENID2_NS
from openid import association
import time
from openid import cryptutil
import warnings

class AssociationSerializationTest(unittest.TestCase):
    def test_roundTrip(self):
        issued = int(time.time())
        lifetime = 600
        assoc = association.Association(
            'handle', 'secret', issued, lifetime, 'HMAC-SHA1')
        s = assoc.serialize()
        assoc2 = association.Association.deserialize(s)
        self.failUnlessEqual(assoc.handle, assoc2.handle)
        self.failUnlessEqual(assoc.issued, assoc2.issued)
        self.failUnlessEqual(assoc.secret, assoc2.secret)
        self.failUnlessEqual(assoc.lifetime, assoc2.lifetime)
        self.failUnlessEqual(assoc.assoc_type, assoc2.assoc_type)

from openid.server.server import \
     DiffieHellmanSHA1ServerSession, \
     DiffieHellmanSHA256ServerSession, \
     PlainTextServerSession

from openid.consumer.consumer import \
     DiffieHellmanSHA1ConsumerSession, \
     DiffieHellmanSHA256ConsumerSession, \
     PlainTextConsumerSession

from openid.dh import DiffieHellman

def createNonstandardConsumerDH():
    nonstandard_dh = DiffieHellman(1315291, 2)
    return DiffieHellmanSHA1ConsumerSession(nonstandard_dh)

class DiffieHellmanSessionTest(datadriven.DataDrivenTestCase):
    secrets = [
        '\x00' * 20,
        '\xff' * 20,
        ' ' * 20,
        'This is a secret....',
        ]

    session_factories = [
        (DiffieHellmanSHA1ConsumerSession, DiffieHellmanSHA1ServerSession),
        (createNonstandardConsumerDH, DiffieHellmanSHA1ServerSession),
        (PlainTextConsumerSession, PlainTextServerSession),
        ]

    def generateCases(cls):
        return [(c, s, sec)
                for c, s in cls.session_factories
                for sec in cls.secrets]

    generateCases = classmethod(generateCases)

    def __init__(self, csess_fact, ssess_fact, secret):
        datadriven.DataDrivenTestCase.__init__(self, csess_fact.__name__)
        self.secret = secret
        self.csess_fact = csess_fact
        self.ssess_fact = ssess_fact

    def runOneTest(self):
        csess = self.csess_fact()
        msg = Message.fromOpenIDArgs(csess.getRequest())
        ssess = self.ssess_fact.fromMessage(msg)
        check_secret = csess.extractSecret(
            Message.fromOpenIDArgs(ssess.answer(self.secret)))
        self.failUnlessEqual(self.secret, check_secret)



class TestMakePairs(unittest.TestCase):
    """Check the key-value formatting methods of associations.
    """

    def setUp(self):
        self.message = m = Message(OPENID2_NS)
        m.updateArgs(OPENID2_NS, {
            'mode': 'id_res',
            'identifier': '=example',
            'signed': 'identifier,mode',
            'sig': 'cephalopod',
            })
        m.updateArgs(BARE_NS, {'xey': 'value'})
        self.assoc = association.Association.fromExpiresIn(
            3600, '{sha1}', 'very_secret', "HMAC-SHA1")


    def testMakePairs(self):
        """Make pairs using the OpenID 1.x type signed list."""
        pairs = self.assoc._makePairs(self.message)
        expected = [
            ('identifier', '=example'),
            ('mode', 'id_res'),
            ]
        self.failUnlessEqual(pairs, expected)



class TestMac(unittest.TestCase):
    def setUp(self):
        self.pairs = [('key1', 'value1'),
                      ('key2', 'value2')]


    def test_sha1(self):
        assoc = association.Association.fromExpiresIn(
            3600, '{sha1}', 'very_secret', "HMAC-SHA1")
        expected = ('\xe0\x1bv\x04\xf1G\xc0\xbb\x7f\x9a\x8b'
                    '\xe9\xbc\xee}\\\xe5\xbb7*')
        sig = assoc.sign(self.pairs)
        self.failUnlessEqual(sig, expected)

    if cryptutil.SHA256_AVAILABLE:
        def test_sha256(self):
            assoc = association.Association.fromExpiresIn(
                3600, '{sha256SA}', 'very_secret', "HMAC-SHA256")
            expected = ('\xfd\xaa\xfe;\xac\xfc*\x988\xad\x05d6-\xeaVy'
                        '\xd5\xa5Z.<\xa9\xed\x18\x82\\$\x95x\x1c&')
            sig = assoc.sign(self.pairs)
            self.failUnlessEqual(sig, expected)



class TestMessageSigning(unittest.TestCase):
    def setUp(self):
        self.message = m = Message(OPENID2_NS)
        m.updateArgs(OPENID2_NS, {'mode': 'id_res',
                                  'identifier': '=example'})
        m.updateArgs(BARE_NS, {'xey': 'value'})
        self.args = {'openid.mode': 'id_res',
                     'openid.identifier': '=example',
                     'xey': 'value'}


    def test_signSHA1(self):
        assoc = association.Association.fromExpiresIn(
            3600, '{sha1}', 'very_secret', "HMAC-SHA1")
        signed = assoc.signMessage(self.message)
        self.failUnless(signed.getArg(OPENID_NS, "sig"))
        self.failUnlessEqual(signed.getArg(OPENID_NS, "signed"),
                             "assoc_handle,identifier,mode,ns,signed")
        self.failUnlessEqual(signed.getArg(BARE_NS, "xey"), "value",
                             signed)

    if cryptutil.SHA256_AVAILABLE:
        def test_signSHA256(self):
            assoc = association.Association.fromExpiresIn(
                3600, '{sha1}', 'very_secret', "HMAC-SHA256")
            signed = assoc.signMessage(self.message)
            self.failUnless(signed.getArg(OPENID_NS, "sig"))
            self.failUnlessEqual(signed.getArg(OPENID_NS, "signed"),
                                 "assoc_handle,identifier,mode,ns,signed")
            self.failUnlessEqual(signed.getArg(BARE_NS, "xey"), "value",
                                 signed)


class TestCheckMessageSignature(unittest.TestCase):
    def test_aintGotSignedList(self):
        m = Message(OPENID2_NS)
        m.updateArgs(OPENID2_NS, {'mode': 'id_res',
                                  'identifier': '=example',
                                  'sig': 'coyote',
                                  })
        m.updateArgs(BARE_NS, {'xey': 'value'})
        assoc = association.Association.fromExpiresIn(
            3600, '{sha1}', 'very_secret', "HMAC-SHA1")
        self.failUnlessRaises(ValueError, assoc.checkMessageSignature, m)


def pyUnitTests():
    return datadriven.loadTests(__name__)

if __name__ == '__main__':
    suite = pyUnitTests()
    runner = unittest.TextTestRunner()
    runner.run(suite)

########NEW FILE########
__FILENAME__ = test_association_response
"""Tests for consumer handling of association responses

This duplicates some things that are covered by test_consumer, but
this works for now.
"""
from openid import oidutil
from openid.test.test_consumer import CatchLogs
from openid.message import Message, OPENID2_NS, OPENID_NS, no_default
from openid.server.server import DiffieHellmanSHA1ServerSession
from openid.consumer.consumer import GenericConsumer, \
     DiffieHellmanSHA1ConsumerSession, ProtocolError
from openid.consumer.discover import OpenIDServiceEndpoint, OPENID_1_1_TYPE, OPENID_2_0_TYPE
from openid.store import memstore
import unittest

# Some values we can use for convenience (see mkAssocResponse)
association_response_values = {
    'expires_in': '1000',
    'assoc_handle':'a handle',
    'assoc_type':'a type',
    'session_type':'a session type',
    'ns':OPENID2_NS,
    }

def mkAssocResponse(*keys):
    """Build an association response message that contains the
    specified subset of keys. The values come from
    `association_response_values`.

    This is useful for testing for missing keys and other times that
    we don't care what the values are."""
    args = dict([(key, association_response_values[key]) for key in keys])
    return Message.fromOpenIDArgs(args)

class BaseAssocTest(CatchLogs, unittest.TestCase):
    def setUp(self):
        CatchLogs.setUp(self)
        self.store = memstore.MemoryStore()
        self.consumer = GenericConsumer(self.store)
        self.endpoint = OpenIDServiceEndpoint()

    def failUnlessProtocolError(self, str_prefix, func, *args, **kwargs):
        try:
            result = func(*args, **kwargs)
        except ProtocolError, e:
            message = 'Expected prefix %r, got %r' % (str_prefix, e[0])
            self.failUnless(e[0].startswith(str_prefix), message)
        else:
            self.fail('Expected ProtocolError, got %r' % (result,))

def mkExtractAssocMissingTest(keys):
    """Factory function for creating test methods for generating
    missing field tests.

    Make a test that ensures that an association response that
    is missing required fields will short-circuit return None.

    According to 'Association Session Response' subsection 'Common
    Response Parameters', the following fields are required for OpenID
    2.0:

     * ns
     * session_type
     * assoc_handle
     * assoc_type
     * expires_in

    If 'ns' is missing, it will fall back to OpenID 1 checking. In
    OpenID 1, everything except 'session_type' and 'ns' are required.
    """

    def test(self):
        msg = mkAssocResponse(*keys)

        self.failUnlessRaises(KeyError,
                              self.consumer._extractAssociation, msg, None)

    return test

class TestExtractAssociationMissingFieldsOpenID2(BaseAssocTest):
    """Test for returning an error upon missing fields in association
    responses for OpenID 2"""

    test_noFields_openid2 = mkExtractAssocMissingTest(['ns'])

    test_missingExpires_openid2 = mkExtractAssocMissingTest(
        ['assoc_handle', 'assoc_type', 'session_type', 'ns'])

    test_missingHandle_openid2 = mkExtractAssocMissingTest(
        ['expires_in', 'assoc_type', 'session_type', 'ns'])

    test_missingAssocType_openid2 = mkExtractAssocMissingTest(
        ['expires_in', 'assoc_handle', 'session_type', 'ns'])

    test_missingSessionType_openid2 = mkExtractAssocMissingTest(
        ['expires_in', 'assoc_handle', 'assoc_type', 'ns'])

class TestExtractAssociationMissingFieldsOpenID1(BaseAssocTest):
    """Test for returning an error upon missing fields in association
    responses for OpenID 2"""

    test_noFields_openid1 = mkExtractAssocMissingTest([])

    test_missingExpires_openid1 = mkExtractAssocMissingTest(
        ['assoc_handle', 'assoc_type'])

    test_missingHandle_openid1 = mkExtractAssocMissingTest(
        ['expires_in', 'assoc_type'])

    test_missingAssocType_openid1 = mkExtractAssocMissingTest(
        ['expires_in', 'assoc_handle'])

class DummyAssocationSession(object):
    def __init__(self, session_type, allowed_assoc_types=()):
        self.session_type = session_type
        self.allowed_assoc_types = allowed_assoc_types

class ExtractAssociationSessionTypeMismatch(BaseAssocTest):
    def mkTest(requested_session_type, response_session_type, openid1=False):
        def test(self):
            assoc_session = DummyAssocationSession(requested_session_type)
            keys = association_response_values.keys()
            if openid1:
                keys.remove('ns')
            msg = mkAssocResponse(*keys)
            msg.setArg(OPENID_NS, 'session_type', response_session_type)
            self.failUnlessProtocolError('Session type mismatch',
                self.consumer._extractAssociation, msg, assoc_session)

        return test

    test_typeMismatchNoEncBlank_openid2 = mkTest(
        requested_session_type='no-encryption',
        response_session_type='',
        )

    test_typeMismatchDHSHA1NoEnc_openid2 = mkTest(
        requested_session_type='DH-SHA1',
        response_session_type='no-encryption',
        )

    test_typeMismatchDHSHA256NoEnc_openid2 = mkTest(
        requested_session_type='DH-SHA256',
        response_session_type='no-encryption',
        )

    test_typeMismatchNoEncDHSHA1_openid2 = mkTest(
        requested_session_type='no-encryption',
        response_session_type='DH-SHA1',
        )

    test_typeMismatchDHSHA1NoEnc_openid1 = mkTest(
        requested_session_type='DH-SHA1',
        response_session_type='DH-SHA256',
        openid1=True,
        )

    test_typeMismatchDHSHA256NoEnc_openid1 = mkTest(
        requested_session_type='DH-SHA256',
        response_session_type='DH-SHA1',
        openid1=True,
        )

    test_typeMismatchNoEncDHSHA1_openid1 = mkTest(
        requested_session_type='no-encryption',
        response_session_type='DH-SHA1',
        openid1=True,
        )


class TestOpenID1AssociationResponseSessionType(BaseAssocTest):
    def mkTest(expected_session_type, session_type_value):
        """Return a test method that will check what session type will
        be used if the OpenID 1 response to an associate call sets the
        'session_type' field to `session_type_value`
        """
        def test(self):
            self._doTest(expected_session_type, session_type_value)
            self.failUnlessLogEmpty()

        return test

    def _doTest(self, expected_session_type, session_type_value):
        # Create a Message with just 'session_type' in it, since
        # that's all this function will use. 'session_type' may be
        # absent if it's set to None.
        args = {}
        if session_type_value is not None:
            args['session_type'] = session_type_value
        message = Message.fromOpenIDArgs(args)
        self.failUnless(message.isOpenID1())

        actual_session_type = self.consumer._getOpenID1SessionType(message)
        error_message = ('Returned sesion type parameter %r was expected '
                         'to yield session type %r, but yielded %r' %
                         (session_type_value, expected_session_type,
                          actual_session_type))
        self.failUnlessEqual(
            expected_session_type, actual_session_type, error_message)

    test_none = mkTest(
        session_type_value=None,
        expected_session_type='no-encryption',
        )

    test_empty = mkTest(
        session_type_value='',
        expected_session_type='no-encryption',
        )

    # This one's different because it expects log messages
    def test_explicitNoEncryption(self):
        self._doTest(
            session_type_value='no-encryption',
            expected_session_type='no-encryption',
            )
        self.failUnlessLogMatches('OpenID server sent "no-encryption"')

    test_dhSHA1 = mkTest(
        session_type_value='DH-SHA1',
        expected_session_type='DH-SHA1',
        )

    # DH-SHA256 is not a valid session type for OpenID1, but this
    # function does not test that. This is mostly just to make sure
    # that it will pass-through stuff that is not explicitly handled,
    # so it will get handled the same way as it is handled for OpenID
    # 2
    test_dhSHA256 = mkTest(
        session_type_value='DH-SHA256',
        expected_session_type='DH-SHA256',
        )

class DummyAssociationSession(object):
    secret = "shh! don't tell!"
    extract_secret_called = False

    session_type = None

    allowed_assoc_types = None

    def extractSecret(self, message):
        self.extract_secret_called = True
        return self.secret

class TestInvalidFields(BaseAssocTest):
    def setUp(self):
        BaseAssocTest.setUp(self)
        self.session_type = 'testing-session'

        # This must something that works for Association.fromExpiresIn
        self.assoc_type = 'HMAC-SHA1'

        self.assoc_handle = 'testing-assoc-handle'

        # These arguments should all be valid
        self.assoc_response = Message.fromOpenIDArgs({
            'expires_in': '1000',
            'assoc_handle':self.assoc_handle,
            'assoc_type':self.assoc_type,
            'session_type':self.session_type,
            'ns':OPENID2_NS,
            })

        self.assoc_session = DummyAssociationSession()

        # Make the session for the response's session type
        self.assoc_session.session_type = self.session_type
        self.assoc_session.allowed_assoc_types = [self.assoc_type]

    def test_worksWithGoodFields(self):
        """Handle a full successful association response"""
        assoc = self.consumer._extractAssociation(
            self.assoc_response, self.assoc_session)
        self.failUnless(self.assoc_session.extract_secret_called)
        self.failUnlessEqual(self.assoc_session.secret, assoc.secret)
        self.failUnlessEqual(1000, assoc.lifetime)
        self.failUnlessEqual(self.assoc_handle, assoc.handle)
        self.failUnlessEqual(self.assoc_type, assoc.assoc_type)

    def test_badAssocType(self):
        # Make sure that the assoc type in the response is not valid
        # for the given session.
        self.assoc_session.allowed_assoc_types = []
        self.failUnlessProtocolError('Unsupported assoc_type for session',
            self.consumer._extractAssociation,
            self.assoc_response, self.assoc_session)

    def test_badExpiresIn(self):
        # Invalid value for expires_in should cause failure
        self.assoc_response.setArg(OPENID_NS, 'expires_in', 'forever')
        self.failUnlessProtocolError('Invalid expires_in',
            self.consumer._extractAssociation,
            self.assoc_response, self.assoc_session)


# XXX: This is what causes most of the imports in this file. It is
# sort of a unit test and sort of a functional test. I'm not terribly
# fond of it.
class TestExtractAssociationDiffieHellman(BaseAssocTest):
    secret = 'x' * 20

    def _setUpDH(self):
        sess, message = self.consumer._createAssociateRequest(
            self.endpoint, 'HMAC-SHA1', 'DH-SHA1')

        # XXX: this is testing _createAssociateRequest
        self.failUnlessEqual(self.endpoint.compatibilityMode(),
                             message.isOpenID1())

        server_sess = DiffieHellmanSHA1ServerSession.fromMessage(message)
        server_resp = server_sess.answer(self.secret)
        server_resp['assoc_type'] = 'HMAC-SHA1'
        server_resp['assoc_handle'] = 'handle'
        server_resp['expires_in'] = '1000'
        server_resp['session_type'] = 'DH-SHA1'
        return sess, Message.fromOpenIDArgs(server_resp)

    def test_success(self):
        sess, server_resp = self._setUpDH()
        ret = self.consumer._extractAssociation(server_resp, sess)
        self.failIf(ret is None)
        self.failUnlessEqual(ret.assoc_type, 'HMAC-SHA1')
        self.failUnlessEqual(ret.secret, self.secret)
        self.failUnlessEqual(ret.handle, 'handle')
        self.failUnlessEqual(ret.lifetime, 1000)

    def test_openid2success(self):
        # Use openid 2 type in endpoint so _setUpDH checks
        # compatibility mode state properly
        self.endpoint.type_uris = [OPENID_2_0_TYPE, OPENID_1_1_TYPE]
        self.test_success()

    def test_badDHValues(self):
        sess, server_resp = self._setUpDH()
        server_resp.setArg(OPENID_NS, 'enc_mac_key', '\x00\x00\x00')
        self.failUnlessProtocolError('Malformed response for',
            self.consumer._extractAssociation, server_resp, sess)

########NEW FILE########
__FILENAME__ = test_auth_request
import cgi
import unittest

from openid.consumer import consumer
from openid import message
from openid.test import support

class DummyEndpoint(object):
    preferred_namespace = None
    local_id = None
    server_url = None
    is_op_identifier = False

    def preferredNamespace(self):
        return self.preferred_namespace

    def getLocalID(self):
        return self.local_id

    def isOPIdentifier(self):
        return self.is_op_identifier

class DummyAssoc(object):
    handle = "assoc-handle"

class AuthRequestTestMixin(support.OpenIDTestMixin):
    """Mixin for AuthRequest tests for OpenID 1 and 2; DON'T add
    unittest.TestCase as a base class here."""

    preferred_namespace = None
    immediate = False
    expected_mode = 'checkid_setup'

    def setUp(self):
        self.endpoint = DummyEndpoint()
        self.endpoint.local_id = 'http://server.unittest/joe'
        self.endpoint.claimed_id = 'http://joe.vanity.example/'
        self.endpoint.server_url = 'http://server.unittest/'
        self.endpoint.preferred_namespace = self.preferred_namespace
        self.realm = 'http://example/'
        self.return_to = 'http://example/return/'
        self.assoc = DummyAssoc()
        self.authreq = consumer.AuthRequest(self.endpoint, self.assoc)

    def failUnlessAnonymous(self, msg):
        for key in ['claimed_id', 'identity']:
            self.failIfOpenIDKeyExists(msg, key)

    def failUnlessHasRequiredFields(self, msg):
        self.failUnlessEqual(self.preferred_namespace,
                             self.authreq.message.getOpenIDNamespace())

        self.failUnlessEqual(self.preferred_namespace,
                             msg.getOpenIDNamespace())

        self.failUnlessOpenIDValueEquals(msg, 'mode',
                                         self.expected_mode)

        # Implement these in subclasses because they depend on
        # protocol differences!
        self.failUnlessHasRealm(msg)
        self.failUnlessIdentifiersPresent(msg)

    # TESTS

    def test_checkNoAssocHandle(self):
        self.authreq.assoc = None
        msg = self.authreq.getMessage(self.realm, self.return_to,
                                      self.immediate)

        self.failIfOpenIDKeyExists(msg, 'assoc_handle')

    def test_checkWithAssocHandle(self):
        msg = self.authreq.getMessage(self.realm, self.return_to,
                                      self.immediate)

        self.failUnlessOpenIDValueEquals(msg, 'assoc_handle',
                                         self.assoc.handle)

    def test_addExtensionArg(self):
        self.authreq.addExtensionArg('bag:', 'color', 'brown')
        self.authreq.addExtensionArg('bag:', 'material', 'paper')
        self.failUnless('bag:' in self.authreq.message.namespaces)
        self.failUnlessEqual(self.authreq.message.getArgs('bag:'),
                             {'color': 'brown',
                              'material': 'paper'})
        msg = self.authreq.getMessage(self.realm, self.return_to,
                                      self.immediate)

        # XXX: this depends on the way that Message assigns
        # namespaces. Really it doesn't care that it has alias "0",
        # but that is tested anyway
        post_args = msg.toPostArgs()
        self.failUnlessEqual('brown', post_args['openid.ext0.color'])
        self.failUnlessEqual('paper', post_args['openid.ext0.material'])

    def test_standard(self):
        msg = self.authreq.getMessage(self.realm, self.return_to,
                                      self.immediate)

        self.failUnlessHasIdentifiers(
            msg, self.endpoint.local_id, self.endpoint.claimed_id)

class TestAuthRequestOpenID2(AuthRequestTestMixin, unittest.TestCase):
    preferred_namespace = message.OPENID2_NS

    def failUnlessHasRealm(self, msg):
        # check presence of proper realm key and absence of the wrong
        # one.
        self.failUnlessOpenIDValueEquals(msg, 'realm', self.realm)
        self.failIfOpenIDKeyExists(msg, 'trust_root')

    def failUnlessIdentifiersPresent(self, msg):
        identity_present = msg.hasKey(message.OPENID_NS, 'identity')
        claimed_present = msg.hasKey(message.OPENID_NS, 'claimed_id')

        self.failUnlessEqual(claimed_present, identity_present)

    def failUnlessHasIdentifiers(self, msg, op_specific_id, claimed_id):
        self.failUnlessOpenIDValueEquals(msg, 'identity', op_specific_id)
        self.failUnlessOpenIDValueEquals(msg, 'claimed_id', claimed_id)

    # TESTS

    def test_setAnonymousWorksForOpenID2(self):
        """OpenID AuthRequests should be able to set 'anonymous' to true."""
        self.failUnless(self.authreq.message.isOpenID2())
        self.authreq.setAnonymous(True)
        self.authreq.setAnonymous(False)

    def test_userAnonymousIgnoresIdentfier(self):
        self.authreq.setAnonymous(True)
        msg = self.authreq.getMessage(self.realm, self.return_to,
                                      self.immediate)
        self.failUnlessHasRequiredFields(msg)
        self.failUnlessAnonymous(msg)

    def test_opAnonymousIgnoresIdentifier(self):
        self.endpoint.is_op_identifier = True
        self.authreq.setAnonymous(True)
        msg = self.authreq.getMessage(self.realm, self.return_to,
                                      self.immediate)
        self.failUnlessHasRequiredFields(msg)
        self.failUnlessAnonymous(msg)

    def test_opIdentifierSendsIdentifierSelect(self):
        self.endpoint.is_op_identifier = True
        msg = self.authreq.getMessage(self.realm, self.return_to,
                                      self.immediate)
        self.failUnlessHasRequiredFields(msg)
        self.failUnlessHasIdentifiers(
            msg, message.IDENTIFIER_SELECT, message.IDENTIFIER_SELECT)

class TestAuthRequestOpenID1(AuthRequestTestMixin, unittest.TestCase):
    preferred_namespace = message.OPENID1_NS

    def setUpEndpoint(self):
        TestAuthRequestBase.setUpEndpoint(self)
        self.endpoint.preferred_namespace = message.OPENID1_NS

    def failUnlessHasIdentifiers(self, msg, op_specific_id, claimed_id):
        """Make sure claimed_is is *absent* in request."""
        self.failUnlessOpenIDValueEquals(msg, 'identity', op_specific_id)
        self.failIfOpenIDKeyExists(msg, 'claimed_id')

    def failUnlessIdentifiersPresent(self, msg):
        self.failIfOpenIDKeyExists(msg, 'claimed_id')
        self.failUnless(msg.hasKey(message.OPENID_NS, 'identity'))

    def failUnlessHasRealm(self, msg):
        # check presence of proper realm key and absence of the wrong
        # one.
        self.failUnlessOpenIDValueEquals(msg, 'trust_root', self.realm)
        self.failIfOpenIDKeyExists(msg, 'realm')

    # TESTS

    def test_setAnonymousFailsForOpenID1(self):
        """OpenID 1 requests MUST NOT be able to set anonymous to True"""
        self.failUnless(self.authreq.message.isOpenID1())
        self.failUnlessRaises(ValueError, self.authreq.setAnonymous, True)
        self.authreq.setAnonymous(False)

    def test_identifierSelect(self):
        """Identfier select SHOULD NOT be sent, but this pathway is in
        here in case some special discovery stuff is done to trigger
        it with OpenID 1. If it is triggered, it will send
        identifier_select just like OpenID 2.
        """
        self.endpoint.is_op_identifier = True
        msg = self.authreq.getMessage(self.realm, self.return_to,
                                      self.immediate)
        self.failUnlessHasRequiredFields(msg)
        self.failUnlessEqual(message.IDENTIFIER_SELECT,
                             msg.getArg(message.OPENID1_NS, 'identity'))

class TestAuthRequestOpenID1Immediate(TestAuthRequestOpenID1):
    immediate = True
    expected_mode = 'checkid_immediate'

class TestAuthRequestOpenID2Immediate(TestAuthRequestOpenID2):
    immediate = True
    expected_mode = 'checkid_immediate'

if __name__ == '__main__':
    unittest.main()

########NEW FILE########
__FILENAME__ = test_ax
"""Tests for the attribute exchange extension module
"""

import unittest
from openid.extensions import ax
from openid.message import NamespaceMap, Message, OPENID2_NS
from openid.consumer.consumer import SuccessResponse

class BogusAXMessage(ax.AXMessage):
    mode = 'bogus'

    getExtensionArgs = ax.AXMessage._newArgs

class DummyRequest(object):
    def __init__(self, message):
        self.message = message

class AXMessageTest(unittest.TestCase):
    def setUp(self):
        self.bax = BogusAXMessage()

    def test_checkMode(self):
        check = self.bax._checkMode
        self.failUnlessRaises(ax.NotAXMessage, check, {})
        self.failUnlessRaises(ax.AXError, check, {'mode':'fetch_request'})

        # does not raise an exception when the mode is right
        check({'mode':self.bax.mode})

    def test_checkMode_newArgs(self):
        """_newArgs generates something that has the correct mode"""
        # This would raise AXError if it didn't like the mode newArgs made.
        self.bax._checkMode(self.bax._newArgs())


class AttrInfoTest(unittest.TestCase):
    def test_construct(self):
        self.failUnlessRaises(TypeError, ax.AttrInfo)
        type_uri = 'a uri'
        ainfo = ax.AttrInfo(type_uri)

        self.failUnlessEqual(type_uri, ainfo.type_uri)
        self.failUnlessEqual(1, ainfo.count)
        self.failIf(ainfo.required)
        self.failUnless(ainfo.alias is None)


class ToTypeURIsTest(unittest.TestCase):
    def setUp(self):
        self.aliases = NamespaceMap()

    def test_empty(self):
        for empty in [None, '']:
            uris = ax.toTypeURIs(self.aliases, empty)
            self.failUnlessEqual([], uris)

    def test_undefined(self):
        self.failUnlessRaises(
            KeyError,
            ax.toTypeURIs, self.aliases, 'http://janrain.com/')

    def test_one(self):
        uri = 'http://janrain.com/'
        alias = 'openid_hackers'
        self.aliases.addAlias(uri, alias)
        uris = ax.toTypeURIs(self.aliases, alias)
        self.failUnlessEqual([uri], uris)

    def test_two(self):
        uri1 = 'http://janrain.com/'
        alias1 = 'openid_hackers'
        self.aliases.addAlias(uri1, alias1)

        uri2 = 'http://jyte.com/'
        alias2 = 'openid_hack'
        self.aliases.addAlias(uri2, alias2)

        uris = ax.toTypeURIs(self.aliases, ','.join([alias1, alias2]))
        self.failUnlessEqual([uri1, uri2], uris)

class ParseAXValuesTest(unittest.TestCase):
    """Testing AXKeyValueMessage.parseExtensionArgs."""

    def failUnlessAXKeyError(self, ax_args):
        msg = ax.AXKeyValueMessage()
        self.failUnlessRaises(KeyError, msg.parseExtensionArgs, ax_args)

    def failUnlessAXValues(self, ax_args, expected_args):
        """Fail unless parseExtensionArgs(ax_args) == expected_args."""
        msg = ax.AXKeyValueMessage()
        msg.parseExtensionArgs(ax_args)
        self.failUnlessEqual(expected_args, msg.data)

    def test_emptyIsValid(self):
        self.failUnlessAXValues({}, {})

    def test_missingValueForAliasExplodes(self):
        self.failUnlessAXKeyError({'type.foo':'urn:foo'})

    def test_countPresentButNotValue(self):
        self.failUnlessAXKeyError({'type.foo':'urn:foo',
                                   'count.foo':'1'})

    def test_invalidCountValue(self):
        msg = ax.FetchRequest()
        self.failUnlessRaises(ax.AXError,
                              msg.parseExtensionArgs,
                              {'type.foo':'urn:foo',
                               'count.foo':'bogus'})

    def test_requestUnlimitedValues(self):
        msg = ax.FetchRequest()

        msg.parseExtensionArgs(
            {'mode':'fetch_request',
             'required':'foo',
             'type.foo':'urn:foo',
             'count.foo':ax.UNLIMITED_VALUES})

        attrs = list(msg.iterAttrs())
        foo = attrs[0]

        self.failUnless(foo.count == ax.UNLIMITED_VALUES)
        self.failUnless(foo.wantsUnlimitedValues())

    def test_longAlias(self):
        # Spec minimum length is 32 characters.  This is a silly test
        # for this library, but it's here for completeness.
        alias = 'x' * ax.MINIMUM_SUPPORTED_ALIAS_LENGTH

        msg = ax.AXKeyValueMessage()
        msg.parseExtensionArgs(
            {'type.%s' % (alias,): 'urn:foo',
             'count.%s' % (alias,): '1',
             'value.%s.1' % (alias,): 'first'}
            )

    def test_invalidAlias(self):
        types = [
            ax.AXKeyValueMessage,
            ax.FetchRequest
            ]

        inputs = [
            {'type.a.b':'urn:foo',
             'count.a.b':'1'},
            {'type.a,b':'urn:foo',
             'count.a,b':'1'},
            ]

        for typ in types:
            for input in inputs:
                msg = typ()
                self.failUnlessRaises(ax.AXError, msg.parseExtensionArgs,
                                      input)

    def test_countPresentAndIsZero(self):
        self.failUnlessAXValues(
            {'type.foo':'urn:foo',
             'count.foo':'0',
             }, {'urn:foo':[]})

    def test_singletonEmpty(self):
        self.failUnlessAXValues(
            {'type.foo':'urn:foo',
             'value.foo':'',
             }, {'urn:foo':[]})

    def test_doubleAlias(self):
        self.failUnlessAXKeyError(
            {'type.foo':'urn:foo',
             'value.foo':'',
             'type.bar':'urn:foo',
             'value.bar':'',
             })

    def test_doubleSingleton(self):
        self.failUnlessAXValues(
            {'type.foo':'urn:foo',
             'value.foo':'',
             'type.bar':'urn:bar',
             'value.bar':'',
             }, {'urn:foo':[], 'urn:bar':[]})

    def test_singletonValue(self):
        self.failUnlessAXValues(
            {'type.foo':'urn:foo',
             'value.foo':'Westfall',
             }, {'urn:foo':['Westfall']})


class FetchRequestTest(unittest.TestCase):
    def setUp(self):
        self.msg = ax.FetchRequest()
        self.type_a = 'http://janrain.example.com/a'
        self.alias_a = 'a'


    def test_mode(self):
        self.failUnlessEqual(self.msg.mode, 'fetch_request')

    def test_construct(self):
        self.failUnlessEqual({}, self.msg.requested_attributes)
        self.failUnlessEqual(None, self.msg.update_url)

        msg = ax.FetchRequest('hailstorm')
        self.failUnlessEqual({}, msg.requested_attributes)
        self.failUnlessEqual('hailstorm', msg.update_url)

    def test_add(self):
        uri = 'mud://puddle'

        # Not yet added:
        self.failIf(uri in self.msg)

        attr = ax.AttrInfo(uri)
        self.msg.add(attr)

        # Present after adding
        self.failUnless(uri in self.msg)

    def test_addTwice(self):
        uri = 'lightning://storm'

        attr = ax.AttrInfo(uri)
        self.msg.add(attr)
        self.failUnlessRaises(KeyError, self.msg.add, attr)

    def test_getExtensionArgs_empty(self):
        expected_args = {
            'mode':'fetch_request',
            }
        self.failUnlessEqual(expected_args, self.msg.getExtensionArgs())

    def test_getExtensionArgs_noAlias(self):
        attr = ax.AttrInfo(
            type_uri = 'type://of.transportation',
            )
        self.msg.add(attr)
        ax_args = self.msg.getExtensionArgs()
        for k, v in ax_args.iteritems():
            if v == attr.type_uri and k.startswith('type.'):
                alias = k[5:]
                break
        else:
            self.fail("Didn't find the type definition")

        self.failUnlessExtensionArgs({
            'type.' + alias:attr.type_uri,
            'if_available':alias,
            })

    def test_getExtensionArgs_alias_if_available(self):
        attr = ax.AttrInfo(
            type_uri = 'type://of.transportation',
            alias = 'transport',
            )
        self.msg.add(attr)
        self.failUnlessExtensionArgs({
            'type.' + attr.alias:attr.type_uri,
            'if_available':attr.alias,
            })

    def test_getExtensionArgs_alias_req(self):
        attr = ax.AttrInfo(
            type_uri = 'type://of.transportation',
            alias = 'transport',
            required = True,
            )
        self.msg.add(attr)
        self.failUnlessExtensionArgs({
            'type.' + attr.alias:attr.type_uri,
            'required':attr.alias,
            })

    def failUnlessExtensionArgs(self, expected_args):
        """Make sure that getExtensionArgs has the expected result

        This method will fill in the mode.
        """
        expected_args = dict(expected_args)
        expected_args['mode'] = self.msg.mode
        self.failUnlessEqual(expected_args, self.msg.getExtensionArgs())

    def test_isIterable(self):
        self.failUnlessEqual([], list(self.msg))
        self.failUnlessEqual([], list(self.msg.iterAttrs()))

    def test_getRequiredAttrs_empty(self):
        self.failUnlessEqual([], self.msg.getRequiredAttrs())

    def test_parseExtensionArgs_extraType(self):
        extension_args = {
            'mode':'fetch_request',
            'type.' + self.alias_a:self.type_a,
            }
        self.failUnlessRaises(ValueError,
                              self.msg.parseExtensionArgs, extension_args)

    def test_parseExtensionArgs(self):
        extension_args = {
            'mode':'fetch_request',
            'type.' + self.alias_a:self.type_a,
            'if_available':self.alias_a
            }
        self.msg.parseExtensionArgs(extension_args)
        self.failUnless(self.type_a in self.msg)
        self.failUnlessEqual([self.type_a], list(self.msg))
        attr_info = self.msg.requested_attributes.get(self.type_a)
        self.failUnless(attr_info)
        self.failIf(attr_info.required)
        self.failUnlessEqual(self.type_a, attr_info.type_uri)
        self.failUnlessEqual(self.alias_a, attr_info.alias)
        self.failUnlessEqual([attr_info], list(self.msg.iterAttrs()))

    def test_extensionArgs_idempotent(self):
        extension_args = {
            'mode':'fetch_request',
            'type.' + self.alias_a:self.type_a,
            'if_available':self.alias_a
            }
        self.msg.parseExtensionArgs(extension_args)
        self.failUnlessEqual(extension_args, self.msg.getExtensionArgs())
        self.failIf(self.msg.requested_attributes[self.type_a].required)

    def test_extensionArgs_idempotent_count_required(self):
        extension_args = {
            'mode':'fetch_request',
            'type.' + self.alias_a:self.type_a,
            'count.' + self.alias_a:'2',
            'required':self.alias_a
            }
        self.msg.parseExtensionArgs(extension_args)
        self.failUnlessEqual(extension_args, self.msg.getExtensionArgs())
        self.failUnless(self.msg.requested_attributes[self.type_a].required)

    def test_extensionArgs_count1(self):
        extension_args = {
            'mode':'fetch_request',
            'type.' + self.alias_a:self.type_a,
            'count.' + self.alias_a:'1',
            'if_available':self.alias_a,
            }
        extension_args_norm = {
            'mode':'fetch_request',
            'type.' + self.alias_a:self.type_a,
            'if_available':self.alias_a,
            }
        self.msg.parseExtensionArgs(extension_args)
        self.failUnlessEqual(extension_args_norm, self.msg.getExtensionArgs())

    def test_openidNoRealm(self):
        openid_req_msg = Message.fromOpenIDArgs({
            'mode': 'checkid_setup',
            'ns': OPENID2_NS,
            'ns.ax': ax.AXMessage.ns_uri,
            'ax.update_url': 'http://different.site/path',
            'ax.mode': 'fetch_request',
            })
        self.failUnlessRaises(ax.AXError,
                              ax.FetchRequest.fromOpenIDRequest,
                              DummyRequest(openid_req_msg))

    def test_openidUpdateURLVerificationError(self):
        openid_req_msg = Message.fromOpenIDArgs({
            'mode': 'checkid_setup',
            'ns': OPENID2_NS,
            'realm': 'http://example.com/realm',
            'ns.ax': ax.AXMessage.ns_uri,
            'ax.update_url': 'http://different.site/path',
            'ax.mode': 'fetch_request',
            })

        self.failUnlessRaises(ax.AXError,
                              ax.FetchRequest.fromOpenIDRequest,
                              DummyRequest(openid_req_msg))

    def test_openidUpdateURLVerificationSuccess(self):
        openid_req_msg = Message.fromOpenIDArgs({
            'mode': 'checkid_setup',
            'ns': OPENID2_NS,
            'realm': 'http://example.com/realm',
            'ns.ax': ax.AXMessage.ns_uri,
            'ax.update_url': 'http://example.com/realm/update_path',
            'ax.mode': 'fetch_request',
            })

        fr = ax.FetchRequest.fromOpenIDRequest(DummyRequest(openid_req_msg))

    def test_openidUpdateURLVerificationSuccessReturnTo(self):
        openid_req_msg = Message.fromOpenIDArgs({
            'mode': 'checkid_setup',
            'ns': OPENID2_NS,
            'return_to': 'http://example.com/realm',
            'ns.ax': ax.AXMessage.ns_uri,
            'ax.update_url': 'http://example.com/realm/update_path',
            'ax.mode': 'fetch_request',
            })

        fr = ax.FetchRequest.fromOpenIDRequest(DummyRequest(openid_req_msg))

    def test_fromOpenIDRequestWithoutExtension(self):
        """return None for an OpenIDRequest without AX paramaters."""
        openid_req_msg = Message.fromOpenIDArgs({
            'mode': 'checkid_setup',
            'ns': OPENID2_NS,
            })
        oreq = DummyRequest(openid_req_msg)
        r = ax.FetchRequest.fromOpenIDRequest(oreq)
        self.failUnless(r is None, "%s is not None" % (r,))

    def test_fromOpenIDRequestWithoutData(self):
        """return something for SuccessResponse with AX paramaters,
        even if it is the empty set."""
        openid_req_msg = Message.fromOpenIDArgs({
            'mode': 'checkid_setup',
            'realm': 'http://example.com/realm',
            'ns': OPENID2_NS,
            'ns.ax': ax.AXMessage.ns_uri,
            'ax.mode': 'fetch_request',
            })
        oreq = DummyRequest(openid_req_msg)
        r = ax.FetchRequest.fromOpenIDRequest(oreq)
        self.failUnless(r is not None)


class FetchResponseTest(unittest.TestCase):
    def setUp(self):
        self.msg = ax.FetchResponse()
        self.value_a = 'monkeys'
        self.type_a = 'http://phone.home/'
        self.alias_a = 'robocop'
        self.request_update_url = 'http://update.bogus/'

    def test_construct(self):
        self.failUnless(self.msg.update_url is None)
        self.failUnlessEqual({}, self.msg.data)

    def test_getExtensionArgs_empty(self):
        expected_args = {
            'mode':'fetch_response',
            }
        self.failUnlessEqual(expected_args, self.msg.getExtensionArgs())

    def test_getExtensionArgs_empty_request(self):
        expected_args = {
            'mode':'fetch_response',
            }
        req = ax.FetchRequest()
        msg = ax.FetchResponse(request=req)
        self.failUnlessEqual(expected_args, msg.getExtensionArgs())

    def test_getExtensionArgs_empty_request_some(self):
        uri = 'http://not.found/'
        alias = 'ext0'

        expected_args = {
            'mode':'fetch_response',
            'type.%s' % (alias,): uri,
            'count.%s' % (alias,): '0'
            }
        req = ax.FetchRequest()
        req.add(ax.AttrInfo(uri))
        msg = ax.FetchResponse(request=req)
        self.failUnlessEqual(expected_args, msg.getExtensionArgs())

    def test_updateUrlInResponse(self):
        uri = 'http://not.found/'
        alias = 'ext0'

        expected_args = {
            'mode':'fetch_response',
            'update_url': self.request_update_url,
            'type.%s' % (alias,): uri,
            'count.%s' % (alias,): '0'
            }
        req = ax.FetchRequest(update_url=self.request_update_url)
        req.add(ax.AttrInfo(uri))
        msg = ax.FetchResponse(request=req)
        self.failUnlessEqual(expected_args, msg.getExtensionArgs())

    def test_getExtensionArgs_some_request(self):
        expected_args = {
            'mode':'fetch_response',
            'type.' + self.alias_a:self.type_a,
            'value.' + self.alias_a + '.1':self.value_a,
            'count.' + self.alias_a: '1'
            }
        req = ax.FetchRequest()
        req.add(ax.AttrInfo(self.type_a, alias=self.alias_a))
        msg = ax.FetchResponse(request=req)
        msg.addValue(self.type_a, self.value_a)
        self.failUnlessEqual(expected_args, msg.getExtensionArgs())

    def test_getExtensionArgs_some_not_request(self):
        req = ax.FetchRequest()
        msg = ax.FetchResponse(request=req)
        msg.addValue(self.type_a, self.value_a)
        self.failUnlessRaises(KeyError, msg.getExtensionArgs)

    def test_getSingle_success(self):
        req = ax.FetchRequest()
        self.msg.addValue(self.type_a, self.value_a)
        self.failUnlessEqual(self.value_a, self.msg.getSingle(self.type_a))

    def test_getSingle_none(self):
        self.failUnlessEqual(None, self.msg.getSingle(self.type_a))

    def test_getSingle_extra(self):
        self.msg.setValues(self.type_a, ['x', 'y'])
        self.failUnlessRaises(ax.AXError, self.msg.getSingle, self.type_a)

    def test_get(self):
        self.failUnlessRaises(KeyError, self.msg.get, self.type_a)

    def test_fromSuccessResponseWithoutExtension(self):
        """return None for SuccessResponse with no AX paramaters."""
        args = {
            'mode': 'id_res',
            'ns': OPENID2_NS,
            }
        sf = ['openid.' + i for i in args.keys()]
        msg = Message.fromOpenIDArgs(args)
        class Endpoint:
            claimed_id = 'http://invalid.'

        oreq = SuccessResponse(Endpoint(), msg, signed_fields=sf)
        r = ax.FetchResponse.fromSuccessResponse(oreq)
        self.failUnless(r is None, "%s is not None" % (r,))

    def test_fromSuccessResponseWithoutData(self):
        """return something for SuccessResponse with AX paramaters,
        even if it is the empty set."""
        args = {
            'mode': 'id_res',
            'ns': OPENID2_NS,
            'ns.ax': ax.AXMessage.ns_uri,
            'ax.mode': 'fetch_response',
            }
        sf = ['openid.' + i for i in args.keys()]
        msg = Message.fromOpenIDArgs(args)
        class Endpoint:
            claimed_id = 'http://invalid.'

        oreq = SuccessResponse(Endpoint(), msg, signed_fields=sf)
        r = ax.FetchResponse.fromSuccessResponse(oreq)
        self.failUnless(r is not None)

    def test_fromSuccessResponseWithData(self):
        name = 'ext0'
        value = 'snozzberry'
        uri = "http://willy.wonka.name/"
        args = {
            'mode': 'id_res',
            'ns': OPENID2_NS,
            'ns.ax': ax.AXMessage.ns_uri,
            'ax.update_url': 'http://example.com/realm/update_path',
            'ax.mode': 'fetch_response',
            'ax.type.'+name: uri,
            'ax.count.'+name: '1',
            'ax.value.%s.1'%name: value,
            }
        sf = ['openid.' + i for i in args.keys()]
        msg = Message.fromOpenIDArgs(args)
        class Endpoint:
            claimed_id = 'http://invalid.'

        resp = SuccessResponse(Endpoint(), msg, signed_fields=sf)
        ax_resp = ax.FetchResponse.fromSuccessResponse(resp)
        values = ax_resp.get(uri)
        self.failUnlessEqual([value], values)


class StoreRequestTest(unittest.TestCase):
    def setUp(self):
        self.msg = ax.StoreRequest()
        self.type_a = 'http://three.count/'
        self.alias_a = 'juggling'

    def test_construct(self):
        self.failUnlessEqual({}, self.msg.data)

    def test_getExtensionArgs_empty(self):
        args = self.msg.getExtensionArgs()
        expected_args = {
            'mode':'store_request',
            }
        self.failUnlessEqual(expected_args, args)

    def test_getExtensionArgs_nonempty(self):
        aliases = NamespaceMap()
        aliases.addAlias(self.type_a, self.alias_a)
        msg = ax.StoreRequest(aliases=aliases)
        msg.setValues(self.type_a, ['foo', 'bar'])
        args = msg.getExtensionArgs()
        expected_args = {
            'mode':'store_request',
            'type.' + self.alias_a: self.type_a,
            'count.' + self.alias_a: '2',
            'value.%s.1' % (self.alias_a,):'foo',
            'value.%s.2' % (self.alias_a,):'bar',
            }
        self.failUnlessEqual(expected_args, args)

class StoreResponseTest(unittest.TestCase):
    def test_success(self):
        msg = ax.StoreResponse()
        self.failUnless(msg.succeeded())
        self.failIf(msg.error_message)
        self.failUnlessEqual({'mode':'store_response_success'},
                             msg.getExtensionArgs())

    def test_fail_nomsg(self):
        msg = ax.StoreResponse(False)
        self.failIf(msg.succeeded())
        self.failIf(msg.error_message)
        self.failUnlessEqual({'mode':'store_response_failure'},
                             msg.getExtensionArgs())

    def test_fail_msg(self):
        reason = 'no reason, really'
        msg = ax.StoreResponse(False, reason)
        self.failIf(msg.succeeded())
        self.failUnlessEqual(reason, msg.error_message)
        self.failUnlessEqual({'mode':'store_response_failure',
                              'error':reason}, msg.getExtensionArgs())

########NEW FILE########
__FILENAME__ = test_consumer
import urlparse
import cgi
import time
import warnings

from openid.message import Message, OPENID_NS, OPENID2_NS, IDENTIFIER_SELECT, \
     OPENID1_NS, BARE_NS
from openid import cryptutil, dh, oidutil, kvform
from openid.store.nonce import mkNonce, split as splitNonce
from openid.consumer.discover import OpenIDServiceEndpoint, OPENID_2_0_TYPE, \
     OPENID_1_1_TYPE
from openid.consumer.consumer import \
     AuthRequest, GenericConsumer, SUCCESS, FAILURE, CANCEL, SETUP_NEEDED, \
     SuccessResponse, FailureResponse, SetupNeededResponse, CancelResponse, \
     DiffieHellmanSHA1ConsumerSession, Consumer, PlainTextConsumerSession, \
     SetupNeededError, DiffieHellmanSHA256ConsumerSession, ServerError, \
     ProtocolError, _httpResponseToMessage
from openid import association
from openid.server.server import \
     PlainTextServerSession, DiffieHellmanSHA1ServerSession
from openid.yadis.manager import Discovery
from openid.yadis.discover import DiscoveryFailure
from openid.dh import DiffieHellman

from openid.fetchers import HTTPResponse, HTTPFetchingError
from openid import fetchers
from openid.store import memstore

from support import CatchLogs

assocs = [
    ('another 20-byte key.', 'Snarky'),
    ('\x00' * 20, 'Zeros'),
    ]

def mkSuccess(endpoint, q):
    """Convenience function to create a SuccessResponse with the given
    arguments, all signed."""
    signed_list = ['openid.' + k for k in q.keys()]
    return SuccessResponse(endpoint, Message.fromOpenIDArgs(q), signed_list)

def parseQuery(qs):
    q = {}
    for (k, v) in cgi.parse_qsl(qs):
        assert not q.has_key(k)
        q[k] = v
    return q

def associate(qs, assoc_secret, assoc_handle):
    """Do the server's half of the associate call, using the given
    secret and handle."""
    q = parseQuery(qs)
    assert q['openid.mode'] == 'associate'
    assert q['openid.assoc_type'] == 'HMAC-SHA1'
    reply_dict = {
        'assoc_type':'HMAC-SHA1',
        'assoc_handle':assoc_handle,
        'expires_in':'600',
        }

    if q.get('openid.session_type') == 'DH-SHA1':
        assert len(q) == 6 or len(q) == 4
        message = Message.fromPostArgs(q)
        session = DiffieHellmanSHA1ServerSession.fromMessage(message)
        reply_dict['session_type'] = 'DH-SHA1'
    else:
        assert len(q) == 2
        session = PlainTextServerSession.fromQuery(q)

    reply_dict.update(session.answer(assoc_secret))
    return kvform.dictToKV(reply_dict)


GOODSIG = "[A Good Signature]"


class GoodAssociation:
    expiresIn = 3600
    handle = "-blah-"

    def getExpiresIn(self):
        return self.expiresIn

    def checkMessageSignature(self, message):
        return message.getArg(OPENID_NS, 'sig') == GOODSIG


class GoodAssocStore(memstore.MemoryStore):
    def getAssociation(self, server_url, handle=None):
        return GoodAssociation()


class TestFetcher(object):
    def __init__(self, user_url, user_page, (assoc_secret, assoc_handle)):
        self.get_responses = {user_url:self.response(user_url, 200, user_page)}
        self.assoc_secret = assoc_secret
        self.assoc_handle = assoc_handle
        self.num_assocs = 0

    def response(self, url, status, body):
        return HTTPResponse(
            final_url=url, status=status, headers={}, body=body)

    def fetch(self, url, body=None, headers=None):
        if body is None:
            if url in self.get_responses:
                return self.get_responses[url]
        else:
            try:
                body.index('openid.mode=associate')
            except ValueError:
                pass # fall through
            else:
                assert body.find('DH-SHA1') != -1
                response = associate(
                    body, self.assoc_secret, self.assoc_handle)
                self.num_assocs += 1
                return self.response(url, 200, response)

        return self.response(url, 404, 'Not found')

def makeFastConsumerSession():
    """
    Create custom DH object so tests run quickly.
    """
    dh = DiffieHellman(100389557, 2)
    return DiffieHellmanSHA1ConsumerSession(dh)

def setConsumerSession(con):
    con.session_types = {'DH-SHA1': makeFastConsumerSession}

def _test_success(server_url, user_url, delegate_url, links, immediate=False):
    store = memstore.MemoryStore()
    if immediate:
        mode = 'checkid_immediate'
    else:
        mode = 'checkid_setup'

    endpoint = OpenIDServiceEndpoint()
    endpoint.claimed_id = user_url
    endpoint.server_url = server_url
    endpoint.local_id = delegate_url
    endpoint.type_uris = [OPENID_1_1_TYPE]

    fetcher = TestFetcher(None, None, assocs[0])
    fetchers.setDefaultFetcher(fetcher, wrap_exceptions=False)

    def run():
        trust_root = consumer_url

        consumer = GenericConsumer(store)
        setConsumerSession(consumer)

        request = consumer.begin(endpoint)
        return_to = consumer_url

        m = request.getMessage(trust_root, return_to, immediate)

        redirect_url = request.redirectURL(trust_root, return_to, immediate)

        parsed = urlparse.urlparse(redirect_url)
        qs = parsed[4]
        q = parseQuery(qs)
        new_return_to = q['openid.return_to']
        del q['openid.return_to']
        assert q == {
            'openid.mode':mode,
            'openid.identity':delegate_url,
            'openid.trust_root':trust_root,
            'openid.assoc_handle':fetcher.assoc_handle,
            }, (q, user_url, delegate_url, mode)

        assert new_return_to.startswith(return_to)
        assert redirect_url.startswith(server_url)

        parsed = urlparse.urlparse(new_return_to)
        query = parseQuery(parsed[4])
        query.update({
            'openid.mode':'id_res',
            'openid.return_to':new_return_to,
            'openid.identity':delegate_url,
            'openid.assoc_handle':fetcher.assoc_handle,
            })

        assoc = store.getAssociation(server_url, fetcher.assoc_handle)

        message = Message.fromPostArgs(query)
        message = assoc.signMessage(message)
        info = consumer.complete(message, request.endpoint, new_return_to)
        assert info.status == SUCCESS, info.message
        assert info.identity_url == user_url

    assert fetcher.num_assocs == 0
    run()
    assert fetcher.num_assocs == 1

    # Test that doing it again uses the existing association
    run()
    assert fetcher.num_assocs == 1

    # Another association is created if we remove the existing one
    store.removeAssociation(server_url, fetcher.assoc_handle)
    run()
    assert fetcher.num_assocs == 2

    # Test that doing it again uses the existing association
    run()
    assert fetcher.num_assocs == 2

import unittest

http_server_url = 'http://server.example.com/'
consumer_url = 'http://consumer.example.com/'
https_server_url = 'https://server.example.com/'

class TestSuccess(unittest.TestCase, CatchLogs):
    server_url = http_server_url
    user_url = 'http://www.example.com/user.html'
    delegate_url = 'http://consumer.example.com/user'

    def setUp(self):
        CatchLogs.setUp(self)
        self.links = '<link rel="openid.server" href="%s" />' % (
            self.server_url,)

        self.delegate_links = ('<link rel="openid.server" href="%s" />'
                               '<link rel="openid.delegate" href="%s" />') % (
            self.server_url, self.delegate_url)

    def tearDown(self):
        CatchLogs.tearDown(self)

    def test_nodelegate(self):
        _test_success(self.server_url, self.user_url,
                      self.user_url, self.links)

    def test_nodelegateImmediate(self):
        _test_success(self.server_url, self.user_url,
                      self.user_url, self.links, True)

    def test_delegate(self):
        _test_success(self.server_url, self.user_url,
                      self.delegate_url, self.delegate_links)

    def test_delegateImmediate(self):
        _test_success(self.server_url, self.user_url,
                      self.delegate_url, self.delegate_links, True)


class TestSuccessHTTPS(TestSuccess):
    server_url = https_server_url


class TestConstruct(unittest.TestCase):
    def setUp(self):
        self.store_sentinel = object()

    def test_construct(self):
        oidc = GenericConsumer(self.store_sentinel)
        self.failUnless(oidc.store is self.store_sentinel)

    def test_nostore(self):
        self.failUnlessRaises(TypeError, GenericConsumer)


class TestIdRes(unittest.TestCase, CatchLogs):
    consumer_class = GenericConsumer

    def setUp(self):
        CatchLogs.setUp(self)

        self.store = memstore.MemoryStore()
        self.consumer = self.consumer_class(self.store)
        self.return_to = "nonny"
        self.endpoint = OpenIDServiceEndpoint()
        self.endpoint.claimed_id = self.consumer_id = "consu"
        self.endpoint.server_url = self.server_url = "serlie"
        self.endpoint.local_id = self.server_id = "sirod"
        self.endpoint.type_uris = [OPENID_1_1_TYPE]

    def disableDiscoveryVerification(self):
        """Set the discovery verification to a no-op for test cases in
        which we don't care."""
        def dummyVerifyDiscover(_, endpoint):
            return endpoint
        self.consumer._verifyDiscoveryResults = dummyVerifyDiscover

    def disableReturnToChecking(self):
        def checkReturnTo(unused1, unused2):
            return True
        self.consumer._checkReturnTo = checkReturnTo
        complete = self.consumer.complete
        def callCompleteWithoutReturnTo(message, endpoint):
            return complete(message, endpoint, None)
        self.consumer.complete = callCompleteWithoutReturnTo

class TestIdResCheckSignature(TestIdRes):
    def setUp(self):
        TestIdRes.setUp(self)
        self.assoc = GoodAssociation()
        self.assoc.handle = "{not_dumb}"
        self.store.storeAssociation(self.endpoint.server_url, self.assoc)

        self.message = Message.fromPostArgs({
            'openid.mode': 'id_res',
            'openid.identity': '=example',
            'openid.sig': GOODSIG,
            'openid.assoc_handle': self.assoc.handle,
            'openid.signed': 'mode,identity,assoc_handle,signed',
            'frobboz': 'banzit',
            })


    def test_sign(self):
        # assoc_handle to assoc with good sig
        self.consumer._idResCheckSignature(self.message,
                                           self.endpoint.server_url)


    def test_signFailsWithBadSig(self):
        self.message.setArg(OPENID_NS, 'sig', 'BAD SIGNATURE')
        self.failUnlessRaises(
            ProtocolError, self.consumer._idResCheckSignature,
            self.message, self.endpoint.server_url)


    def test_stateless(self):
        # assoc_handle missing assoc, consumer._checkAuth returns goodthings
        self.message.setArg(OPENID_NS, "assoc_handle", "dumbHandle")
        self.consumer._processCheckAuthResponse = (
            lambda response, server_url: True)
        self.consumer._makeKVPost = lambda args, server_url: {}
        self.consumer._idResCheckSignature(self.message,
                                           self.endpoint.server_url)

    def test_statelessRaisesError(self):
        # assoc_handle missing assoc, consumer._checkAuth returns goodthings
        self.message.setArg(OPENID_NS, "assoc_handle", "dumbHandle")
        self.consumer._checkAuth = lambda unused1, unused2: False
        self.failUnlessRaises(
            ProtocolError, self.consumer._idResCheckSignature,
            self.message, self.endpoint.server_url)

    def test_stateless_noStore(self):
        # assoc_handle missing assoc, consumer._checkAuth returns goodthings
        self.message.setArg(OPENID_NS, "assoc_handle", "dumbHandle")
        self.consumer.store = None
        self.consumer._processCheckAuthResponse = (
            lambda response, server_url: True)
        self.consumer._makeKVPost = lambda args, server_url: {}
        self.consumer._idResCheckSignature(self.message,
                                           self.endpoint.server_url)

    def test_statelessRaisesError_noStore(self):
        # assoc_handle missing assoc, consumer._checkAuth returns goodthings
        self.message.setArg(OPENID_NS, "assoc_handle", "dumbHandle")
        self.consumer._checkAuth = lambda unused1, unused2: False
        self.consumer.store = None
        self.failUnlessRaises(
            ProtocolError, self.consumer._idResCheckSignature,
            self.message, self.endpoint.server_url)


class TestQueryFormat(TestIdRes):
    def test_notAList(self):
        # XXX: should be a Message object test, not a consumer test

        # Value should be a single string.  If it's a list, it should generate
        # an exception.
        query = {'openid.mode': ['cancel']}
        try:
            r = Message.fromPostArgs(query)
        except TypeError, err:
            self.failUnless(str(err).find('values') != -1, err)
        else:
            self.fail("expected TypeError, got this instead: %s" % (r,))

class TestComplete(TestIdRes):
    """Testing GenericConsumer.complete.

    Other TestIdRes subclasses test more specific aspects.
    """

    def test_setupNeededIdRes(self):
        message = Message.fromOpenIDArgs({'mode': 'id_res'})
        setup_url_sentinel = object()

        def raiseSetupNeeded(msg):
            self.failUnless(msg is message)
            raise SetupNeededError(setup_url_sentinel)

        self.consumer._checkSetupNeeded = raiseSetupNeeded

        response = self.consumer.complete(message, None, None)
        self.failUnlessEqual(SETUP_NEEDED, response.status)
        self.failUnless(setup_url_sentinel is response.setup_url)

    def test_cancel(self):
        message = Message.fromPostArgs({'openid.mode': 'cancel'})
        self.disableReturnToChecking()
        r = self.consumer.complete(message, self.endpoint)
        self.failUnlessEqual(r.status, CANCEL)
        self.failUnless(r.identity_url == self.endpoint.claimed_id)

    def test_cancel_with_return_to(self):
        message = Message.fromPostArgs({'openid.mode': 'cancel'})
        r = self.consumer.complete(message, self.endpoint, self.return_to)
        self.failUnlessEqual(r.status, CANCEL)
        self.failUnless(r.identity_url == self.endpoint.claimed_id)

    def test_error(self):
        msg = 'an error message'
        message = Message.fromPostArgs({'openid.mode': 'error',
                 'openid.error': msg,
                 })
        self.disableReturnToChecking()
        r = self.consumer.complete(message, self.endpoint)
        self.failUnlessEqual(r.status, FAILURE)
        self.failUnless(r.identity_url == self.endpoint.claimed_id)
        self.failUnlessEqual(r.message, msg)

    def test_errorWithNoOptionalKeys(self):
        msg = 'an error message'
        contact = 'some contact info here'
        message = Message.fromPostArgs({'openid.mode': 'error',
                 'openid.error': msg,
                 'openid.contact': contact,
                 })
        self.disableReturnToChecking()
        r = self.consumer.complete(message, self.endpoint)
        self.failUnlessEqual(r.status, FAILURE)
        self.failUnless(r.identity_url == self.endpoint.claimed_id)
        self.failUnless(r.contact == contact)
        self.failUnless(r.reference is None)
        self.failUnlessEqual(r.message, msg)

    def test_errorWithOptionalKeys(self):
        msg = 'an error message'
        contact = 'me'
        reference = 'support ticket'
        message = Message.fromPostArgs({'openid.mode': 'error',
                 'openid.error': msg, 'openid.reference': reference,
                 'openid.contact': contact, 'openid.ns': OPENID2_NS,
                 })
        r = self.consumer.complete(message, self.endpoint, None)
        self.failUnlessEqual(r.status, FAILURE)
        self.failUnless(r.identity_url == self.endpoint.claimed_id)
        self.failUnless(r.contact == contact)
        self.failUnless(r.reference == reference)
        self.failUnlessEqual(r.message, msg)

    def test_noMode(self):
        message = Message.fromPostArgs({})
        r = self.consumer.complete(message, self.endpoint, None)
        self.failUnlessEqual(r.status, FAILURE)
        self.failUnless(r.identity_url == self.endpoint.claimed_id)

    def test_idResMissingField(self):
        # XXX - this test is passing, but not necessarily by what it
        # is supposed to test for.  status in FAILURE, but it's because
        # *check_auth* failed, not because it's missing an arg, exactly.
        message = Message.fromPostArgs({'openid.mode': 'id_res'})
        self.failUnlessRaises(ProtocolError, self.consumer._doIdRes,
                              message, self.endpoint, None)

    def test_idResURLMismatch(self):
        class VerifiedError(Exception): pass

        def discoverAndVerify(claimed_id, _to_match_endpoints):
            raise VerifiedError

        self.consumer._discoverAndVerify = discoverAndVerify
        self.disableReturnToChecking()

        message = Message.fromPostArgs(
            {'openid.mode': 'id_res',
             'openid.return_to': 'return_to (just anything)',
             'openid.identity': 'something wrong (not self.consumer_id)',
             'openid.assoc_handle': 'does not matter',
             'openid.sig': GOODSIG,
             'openid.signed': 'identity,return_to',
             })
        self.consumer.store = GoodAssocStore()

        self.failUnlessRaises(VerifiedError,
                              self.consumer.complete,
                              message, self.endpoint)

        self.failUnlessLogMatches('Error attempting to use stored',
                                  'Attempting discovery')

class TestCompleteMissingSig(unittest.TestCase, CatchLogs):

    def setUp(self):
        self.store = GoodAssocStore()
        self.consumer = GenericConsumer(self.store)
        self.server_url = "http://idp.unittest/"
        CatchLogs.setUp(self)

        claimed_id = 'bogus.claimed'

        self.message = Message.fromOpenIDArgs(
            {'mode': 'id_res',
             'return_to': 'return_to (just anything)',
             'identity': claimed_id,
             'assoc_handle': 'does not matter',
             'sig': GOODSIG,
             'response_nonce': mkNonce(),
             'signed': 'identity,return_to,response_nonce,assoc_handle,claimed_id,op_endpoint',
             'claimed_id': claimed_id,
             'op_endpoint': self.server_url,
             'ns':OPENID2_NS,
             })

        self.endpoint = OpenIDServiceEndpoint()
        self.endpoint.server_url = self.server_url
        self.endpoint.claimed_id = claimed_id
        self.consumer._checkReturnTo = lambda unused1, unused2 : True

    def tearDown(self):
        CatchLogs.tearDown(self)


    def test_idResMissingNoSigs(self):
        def _vrfy(resp_msg, endpoint=None):
            return endpoint

        self.consumer._verifyDiscoveryResults = _vrfy
        r = self.consumer.complete(self.message, self.endpoint, None)
        self.failUnlessSuccess(r)


    def test_idResNoIdentity(self):
        self.message.delArg(OPENID_NS, 'identity')
        self.message.delArg(OPENID_NS, 'claimed_id')
        self.endpoint.claimed_id = None
        self.message.setArg(OPENID_NS, 'signed', 'return_to,response_nonce,assoc_handle,op_endpoint')
        r = self.consumer.complete(self.message, self.endpoint, None)
        self.failUnlessSuccess(r)


    def test_idResMissingIdentitySig(self):
        self.message.setArg(OPENID_NS, 'signed', 'return_to,response_nonce,assoc_handle,claimed_id')
        r = self.consumer.complete(self.message, self.endpoint, None)
        self.failUnlessEqual(r.status, FAILURE)


    def test_idResMissingReturnToSig(self):
        self.message.setArg(OPENID_NS, 'signed', 'identity,response_nonce,assoc_handle,claimed_id')
        r = self.consumer.complete(self.message, self.endpoint, None)
        self.failUnlessEqual(r.status, FAILURE)


    def test_idResMissingAssocHandleSig(self):
        self.message.setArg(OPENID_NS, 'signed', 'identity,response_nonce,return_to,claimed_id')
        r = self.consumer.complete(self.message, self.endpoint, None)
        self.failUnlessEqual(r.status, FAILURE)


    def test_idResMissingClaimedIDSig(self):
        self.message.setArg(OPENID_NS, 'signed', 'identity,response_nonce,return_to,assoc_handle')
        r = self.consumer.complete(self.message, self.endpoint, None)
        self.failUnlessEqual(r.status, FAILURE)


    def failUnlessSuccess(self, response):
        if response.status != SUCCESS:
            self.fail("Non-successful response: %s" % (response,))



class TestCheckAuthResponse(TestIdRes, CatchLogs):
    def setUp(self):
        CatchLogs.setUp(self)
        TestIdRes.setUp(self)

    def tearDown(self):
        CatchLogs.tearDown(self)

    def _createAssoc(self):
        issued = time.time()
        lifetime = 1000
        assoc = association.Association(
            'handle', 'secret', issued, lifetime, 'HMAC-SHA1')
        store = self.consumer.store
        store.storeAssociation(self.server_url, assoc)
        assoc2 = store.getAssociation(self.server_url)
        self.failUnlessEqual(assoc, assoc2)

    def test_goodResponse(self):
        """successful response to check_authentication"""
        response = Message.fromOpenIDArgs({'is_valid':'true',})
        r = self.consumer._processCheckAuthResponse(response, self.server_url)
        self.failUnless(r)

    def test_missingAnswer(self):
        """check_authentication returns false when the server sends no answer"""
        response = Message.fromOpenIDArgs({})
        r = self.consumer._processCheckAuthResponse(response, self.server_url)
        self.failIf(r)

    def test_badResponse(self):
        """check_authentication returns false when is_valid is false"""
        response = Message.fromOpenIDArgs({'is_valid':'false',})
        r = self.consumer._processCheckAuthResponse(response, self.server_url)
        self.failIf(r)

    def test_badResponseInvalidate(self):
        """Make sure that the handle is invalidated when is_valid is false

        From "Verifying directly with the OpenID Provider"::

            If the OP responds with "is_valid" set to "true", and
            "invalidate_handle" is present, the Relying Party SHOULD
            NOT send further authentication requests with that handle.
        """
        self._createAssoc()
        response = Message.fromOpenIDArgs({
            'is_valid':'false',
            'invalidate_handle':'handle',
            })
        r = self.consumer._processCheckAuthResponse(response, self.server_url)
        self.failIf(r)
        self.failUnless(
            self.consumer.store.getAssociation(self.server_url) is None)

    def test_invalidateMissing(self):
        """invalidate_handle with a handle that is not present"""
        response = Message.fromOpenIDArgs({
            'is_valid':'true',
            'invalidate_handle':'missing',
            })
        r = self.consumer._processCheckAuthResponse(response, self.server_url)
        self.failUnless(r)
        self.failUnlessLogMatches(
            'Received "invalidate_handle"'
            )

    def test_invalidateMissing_noStore(self):
        """invalidate_handle with a handle that is not present"""
        response = Message.fromOpenIDArgs({
            'is_valid':'true',
            'invalidate_handle':'missing',
            })
        self.consumer.store = None
        r = self.consumer._processCheckAuthResponse(response, self.server_url)
        self.failUnless(r)
        self.failUnlessLogMatches(
            'Received "invalidate_handle"',
            'Unexpectedly got invalidate_handle without a store')

    def test_invalidatePresent(self):
        """invalidate_handle with a handle that exists

        From "Verifying directly with the OpenID Provider"::

            If the OP responds with "is_valid" set to "true", and
            "invalidate_handle" is present, the Relying Party SHOULD
            NOT send further authentication requests with that handle.
        """
        self._createAssoc()
        response = Message.fromOpenIDArgs({
            'is_valid':'true',
            'invalidate_handle':'handle',
            })
        r = self.consumer._processCheckAuthResponse(response, self.server_url)
        self.failUnless(r)
        self.failUnless(
            self.consumer.store.getAssociation(self.server_url) is None)

class TestSetupNeeded(TestIdRes):
    def failUnlessSetupNeeded(self, expected_setup_url, message):
        try:
            self.consumer._checkSetupNeeded(message)
        except SetupNeededError, why:
            self.failUnlessEqual(expected_setup_url, why.user_setup_url)
        else:
            self.fail("Expected to find an immediate-mode response")

    def test_setupNeededOpenID1(self):
        """The minimum conditions necessary to trigger Setup Needed"""
        setup_url = 'http://unittest/setup-here'
        message = Message.fromPostArgs({
            'openid.mode': 'id_res',
            'openid.user_setup_url': setup_url,
            })
        self.failUnless(message.isOpenID1())
        self.failUnlessSetupNeeded(setup_url, message)

    def test_setupNeededOpenID1_extra(self):
        """Extra stuff along with setup_url still trigger Setup Needed"""
        setup_url = 'http://unittest/setup-here'
        message = Message.fromPostArgs({
            'openid.mode': 'id_res',
            'openid.user_setup_url': setup_url,
            'openid.identity': 'bogus',
            })
        self.failUnless(message.isOpenID1())
        self.failUnlessSetupNeeded(setup_url, message)

    def test_noSetupNeededOpenID1(self):
        """When the user_setup_url is missing on an OpenID 1 message,
        we assume that it's not a cancel response to checkid_immediate"""
        message = Message.fromOpenIDArgs({'mode': 'id_res'})
        self.failUnless(message.isOpenID1())

        # No SetupNeededError raised
        self.consumer._checkSetupNeeded(message)

    def test_setupNeededOpenID2(self):
        message = Message.fromOpenIDArgs({
            'mode':'setup_needed',
            'ns':OPENID2_NS,
            })
        self.failUnless(message.isOpenID2())
        response = self.consumer.complete(message, None, None)
        self.failUnlessEqual('setup_needed', response.status)
        self.failUnlessEqual(None, response.setup_url)

    def test_setupNeededDoesntWorkForOpenID1(self):
        message = Message.fromOpenIDArgs({
            'mode':'setup_needed',
            })

        # No SetupNeededError raised
        self.consumer._checkSetupNeeded(message)

        response = self.consumer.complete(message, None, None)
        self.failUnlessEqual('failure', response.status)
        self.failUnless(response.message.startswith('Invalid openid.mode'))

    def test_noSetupNeededOpenID2(self):
        message = Message.fromOpenIDArgs({
            'mode':'id_res',
            'game':'puerto_rico',
            'ns':OPENID2_NS,
            })
        self.failUnless(message.isOpenID2())

        # No SetupNeededError raised
        self.consumer._checkSetupNeeded(message)

class IdResCheckForFieldsTest(TestIdRes):
    def setUp(self):
        self.consumer = GenericConsumer(None)

    def mkSuccessTest(openid_args, signed_list):
        def test(self):
            message = Message.fromOpenIDArgs(openid_args)
            message.setArg(OPENID_NS, 'signed', ','.join(signed_list))
            self.consumer._idResCheckForFields(message)
        return test

    test_openid1Success = mkSuccessTest(
        {'return_to':'return',
         'assoc_handle':'assoc handle',
         'sig':'a signature',
         'identity':'someone',
         },
        ['return_to', 'identity'])

    test_openid2Success = mkSuccessTest(
        {'ns':OPENID2_NS,
         'return_to':'return',
         'assoc_handle':'assoc handle',
         'sig':'a signature',
         'op_endpoint':'my favourite server',
         'response_nonce':'use only once',
         },
        ['return_to', 'response_nonce', 'assoc_handle', 'op_endpoint'])

    test_openid2Success_identifiers = mkSuccessTest(
        {'ns':OPENID2_NS,
         'return_to':'return',
         'assoc_handle':'assoc handle',
         'sig':'a signature',
         'claimed_id':'i claim to be me',
         'identity':'my server knows me as me',
         'op_endpoint':'my favourite server',
         'response_nonce':'use only once',
         },
        ['return_to', 'response_nonce', 'identity',
         'claimed_id', 'assoc_handle', 'op_endpoint'])

    def mkMissingFieldTest(openid_args):
        def test(self):
            message = Message.fromOpenIDArgs(openid_args)
            try:
                self.consumer._idResCheckForFields(message)
            except ProtocolError, why:
                self.failUnless(why[0].startswith('Missing required'))
            else:
                self.fail('Expected an error, but none occurred')
        return test

    def mkMissingSignedTest(openid_args):
        def test(self):
            message = Message.fromOpenIDArgs(openid_args)
            try:
                self.consumer._idResCheckForFields(message)
            except ProtocolError, why:
                self.failUnless(why[0].endswith('not signed'))
            else:
                self.fail('Expected an error, but none occurred')
        return test

    test_openid1Missing_returnToSig = mkMissingSignedTest(
        {'return_to':'return',
         'assoc_handle':'assoc handle',
         'sig':'a signature',
         'identity':'someone',
         'signed':'identity',
         })

    test_openid1Missing_identitySig = mkMissingSignedTest(
        {'return_to':'return',
         'assoc_handle':'assoc handle',
         'sig':'a signature',
         'identity':'someone',
         'signed':'return_to'
         })

    test_openid2Missing_opEndpointSig = mkMissingSignedTest(
        {'ns':OPENID2_NS,
         'return_to':'return',
         'assoc_handle':'assoc handle',
         'sig':'a signature',
         'identity':'someone',
         'op_endpoint':'the endpoint',
         'signed':'return_to,identity,assoc_handle'
         })

    test_openid1MissingReturnTo = mkMissingFieldTest(
        {'assoc_handle':'assoc handle',
         'sig':'a signature',
         'identity':'someone',
         })

    test_openid1MissingAssocHandle = mkMissingFieldTest(
        {'return_to':'return',
         'sig':'a signature',
         'identity':'someone',
         })

    # XXX: I could go on...

class CheckAuthHappened(Exception): pass

class CheckNonceVerifyTest(TestIdRes, CatchLogs):
    def setUp(self):
        CatchLogs.setUp(self)
        TestIdRes.setUp(self)
        self.consumer.openid1_nonce_query_arg_name = 'nonce'

    def tearDown(self):
        CatchLogs.tearDown(self)

    def test_openid1Success(self):
        """use consumer-generated nonce"""
        nonce_value = mkNonce()
        self.return_to = 'http://rt.unittest/?nonce=%s' % (nonce_value,)
        self.response = Message.fromOpenIDArgs({'return_to': self.return_to})
        self.response.setArg(BARE_NS, 'nonce', nonce_value)
        self.consumer._idResCheckNonce(self.response, self.endpoint)
        self.failUnlessLogEmpty()

    def test_openid1Missing(self):
        """use consumer-generated nonce"""
        self.response = Message.fromOpenIDArgs({})
        n = self.consumer._idResGetNonceOpenID1(self.response, self.endpoint)
        self.failUnless(n is None, n)
        self.failUnlessLogEmpty()

    def test_consumerNonceOpenID2(self):
        """OpenID 2 does not use consumer-generated nonce"""
        self.return_to = 'http://rt.unittest/?nonce=%s' % (mkNonce(),)
        self.response = Message.fromOpenIDArgs(
            {'return_to': self.return_to, 'ns':OPENID2_NS})
        self.failUnlessRaises(ProtocolError, self.consumer._idResCheckNonce,
                              self.response, self.endpoint)
        self.failUnlessLogEmpty()

    def test_serverNonce(self):
        """use server-generated nonce"""
        self.response = Message.fromOpenIDArgs(
            {'ns':OPENID2_NS, 'response_nonce': mkNonce(),})
        self.consumer._idResCheckNonce(self.response, self.endpoint)
        self.failUnlessLogEmpty()

    def test_serverNonceOpenID1(self):
        """OpenID 1 does not use server-generated nonce"""
        self.response = Message.fromOpenIDArgs(
            {'ns':OPENID1_NS,
             'return_to': 'http://return.to/',
             'response_nonce': mkNonce(),})
        self.failUnlessRaises(ProtocolError, self.consumer._idResCheckNonce,
                              self.response, self.endpoint)
        self.failUnlessLogEmpty()

    def test_badNonce(self):
        """remove the nonce from the store

        From "Checking the Nonce"::

            When the Relying Party checks the signature on an assertion, the

            Relying Party SHOULD ensure that an assertion has not yet
            been accepted with the same value for "openid.response_nonce"
            from the same OP Endpoint URL.
        """
        nonce = mkNonce()
        stamp, salt = splitNonce(nonce)
        self.store.useNonce(self.server_url, stamp, salt)
        self.response = Message.fromOpenIDArgs(
                                  {'response_nonce': nonce,
                                   'ns':OPENID2_NS,
                                   })
        self.failUnlessRaises(ProtocolError, self.consumer._idResCheckNonce,
                              self.response, self.endpoint)

    def test_successWithNoStore(self):
        """When there is no store, checking the nonce succeeds"""
        self.consumer.store = None
        self.response = Message.fromOpenIDArgs(
                                  {'response_nonce': mkNonce(),
                                   'ns':OPENID2_NS,
                                   })
        self.consumer._idResCheckNonce(self.response, self.endpoint)
        self.failUnlessLogEmpty()

    def test_tamperedNonce(self):
        """Malformed nonce"""
        self.response = Message.fromOpenIDArgs(
                                  {'ns':OPENID2_NS,
                                   'response_nonce':'malformed'})
        self.failUnlessRaises(ProtocolError, self.consumer._idResCheckNonce,
                              self.response, self.endpoint)

    def test_missingNonce(self):
        """no nonce parameter on the return_to"""
        self.response = Message.fromOpenIDArgs(
                                  {'return_to': self.return_to})
        self.failUnlessRaises(ProtocolError, self.consumer._idResCheckNonce,
                              self.response, self.endpoint)

class CheckAuthDetectingConsumer(GenericConsumer):
    def _checkAuth(self, *args):
        raise CheckAuthHappened(args)

    def _idResCheckNonce(self, *args):
        """We're not testing nonce-checking, so just return success
        when it asks."""
        return True

class TestCheckAuthTriggered(TestIdRes, CatchLogs):
    consumer_class = CheckAuthDetectingConsumer

    def setUp(self):
        TestIdRes.setUp(self)
        CatchLogs.setUp(self)
        self.disableDiscoveryVerification()

    def test_checkAuthTriggered(self):
        message = Message.fromPostArgs({
            'openid.return_to':self.return_to,
            'openid.identity':self.server_id,
            'openid.assoc_handle':'not_found',
            'openid.sig': GOODSIG,
            'openid.signed': 'identity,return_to',
            })
        self.disableReturnToChecking()
        try:
            result = self.consumer._doIdRes(message, self.endpoint, None)
        except CheckAuthHappened:
            pass
        else:
            self.fail('_checkAuth did not happen. Result was: %r %s' %
                      (result, self.messages))

    def test_checkAuthTriggeredWithAssoc(self):
        # Store an association for this server that does not match the
        # handle that is in the message
        issued = time.time()
        lifetime = 1000
        assoc = association.Association(
            'handle', 'secret', issued, lifetime, 'HMAC-SHA1')
        self.store.storeAssociation(self.server_url, assoc)
        self.disableReturnToChecking()
        message = Message.fromPostArgs({
            'openid.return_to':self.return_to,
            'openid.identity':self.server_id,
            'openid.assoc_handle':'not_found',
            'openid.sig': GOODSIG,
            'openid.signed': 'identity,return_to',
            })
        try:
            result = self.consumer._doIdRes(message, self.endpoint, None)
        except CheckAuthHappened:
            pass
        else:
            self.fail('_checkAuth did not happen. Result was: %r' % (result,))

    def test_expiredAssoc(self):
        # Store an expired association for the server with the handle
        # that is in the message
        issued = time.time() - 10
        lifetime = 0
        handle = 'handle'
        assoc = association.Association(
            handle, 'secret', issued, lifetime, 'HMAC-SHA1')
        self.failUnless(assoc.expiresIn <= 0)
        self.store.storeAssociation(self.server_url, assoc)

        message = Message.fromPostArgs({
            'openid.return_to':self.return_to,
            'openid.identity':self.server_id,
            'openid.assoc_handle':handle,
            'openid.sig': GOODSIG,
            'openid.signed': 'identity,return_to',
            })
        self.disableReturnToChecking()
        self.failUnlessRaises(ProtocolError, self.consumer._doIdRes,
                              message, self.endpoint, None)

    def test_newerAssoc(self):
        lifetime = 1000

        good_issued = time.time() - 10
        good_handle = 'handle'
        good_assoc = association.Association(
            good_handle, 'secret', good_issued, lifetime, 'HMAC-SHA1')
        self.store.storeAssociation(self.server_url, good_assoc)

        bad_issued = time.time() - 5
        bad_handle = 'handle2'
        bad_assoc = association.Association(
            bad_handle, 'secret', bad_issued, lifetime, 'HMAC-SHA1')
        self.store.storeAssociation(self.server_url, bad_assoc)

        query = {
            'return_to':self.return_to,
            'identity':self.server_id,
            'assoc_handle':good_handle,
            }

        message = Message.fromOpenIDArgs(query)
        message = good_assoc.signMessage(message)
        self.disableReturnToChecking()
        info = self.consumer._doIdRes(message, self.endpoint, None)
        self.failUnlessEqual(info.status, SUCCESS, info.message)
        self.failUnlessEqual(self.consumer_id, info.identity_url)



class TestReturnToArgs(unittest.TestCase):
    """Verifying the Return URL paramaters.
    From the specification "Verifying the Return URL"::

        To verify that the "openid.return_to" URL matches the URL that is
        processing this assertion:

         - The URL scheme, authority, and path MUST be the same between the
           two URLs.

         - Any query parameters that are present in the "openid.return_to"
           URL MUST also be present with the same values in the
           accepting URL.

    XXX: So far we have only tested the second item on the list above.
    XXX: _verifyReturnToArgs is not invoked anywhere.
    """

    def setUp(self):
        store = object()
        self.consumer = GenericConsumer(store)

    def test_returnToArgsOkay(self):
        query = {
            'openid.mode': 'id_res',
            'openid.return_to': 'http://example.com/?foo=bar',
            'foo': 'bar',
            }
        # no return value, success is assumed if there are no exceptions.
        self.consumer._verifyReturnToArgs(query)

    def test_returnToArgsUnexpectedArg(self):
        query = {
            'openid.mode': 'id_res',
            'openid.return_to': 'http://example.com/',
            'foo': 'bar',
            }
        # no return value, success is assumed if there are no exceptions.
        self.failUnlessRaises(ProtocolError,
                              self.consumer._verifyReturnToArgs, query)

    def test_returnToMismatch(self):
        query = {
            'openid.mode': 'id_res',
            'openid.return_to': 'http://example.com/?foo=bar',
            }
        # fail, query has no key 'foo'.
        self.failUnlessRaises(ValueError,
                              self.consumer._verifyReturnToArgs, query)

        query['foo'] = 'baz'
        # fail, values for 'foo' do not match.
        self.failUnlessRaises(ValueError,
                              self.consumer._verifyReturnToArgs, query)


    def test_noReturnTo(self):
        query = {'openid.mode': 'id_res'}
        self.failUnlessRaises(ValueError,
                              self.consumer._verifyReturnToArgs, query)

    def test_completeBadReturnTo(self):
        """Test GenericConsumer.complete()'s handling of bad return_to
        values.
        """
        return_to = "http://some.url/path?foo=bar"

        # Scheme, authority, and path differences are checked by
        # GenericConsumer._checkReturnTo.  Query args checked by
        # GenericConsumer._verifyReturnToArgs.
        bad_return_tos = [
            # Scheme only
            "https://some.url/path?foo=bar",
            # Authority only
            "http://some.url.invalid/path?foo=bar",
            # Path only
            "http://some.url/path_extra?foo=bar",
            # Query args differ
            "http://some.url/path?foo=bar2",
            "http://some.url/path?foo2=bar",
            ]

        m = Message(OPENID1_NS)
        m.setArg(OPENID_NS, 'mode', 'cancel')
        m.setArg(BARE_NS, 'foo', 'bar')
        endpoint = None

        for bad in bad_return_tos:
            m.setArg(OPENID_NS, 'return_to', bad)
            self.failIf(self.consumer._checkReturnTo(m, return_to))

    def test_completeGoodReturnTo(self):
        """Test GenericConsumer.complete()'s handling of good
        return_to values.
        """
        return_to = "http://some.url/path"

        good_return_tos = [
            (return_to, {}),
            (return_to + "?another=arg", {(BARE_NS, 'another'): 'arg'}),
            (return_to + "?another=arg#fragment", {(BARE_NS, 'another'): 'arg'}),
            ("HTTP"+return_to[4:], {}),
            (return_to.replace('url','URL'), {}),
            ("http://some.url:80/path", {}),
            ("http://some.url/p%61th", {}),
            ("http://some.url/./path", {}),
            ]

        endpoint = None

        for good, extra in good_return_tos:
            m = Message(OPENID1_NS)
            m.setArg(OPENID_NS, 'mode', 'cancel')

            for ns, key in extra:
                m.setArg(ns, key, extra[(ns, key)])

            m.setArg(OPENID_NS, 'return_to', good)
            result = self.consumer.complete(m, endpoint, return_to)
            self.failUnless(isinstance(result, CancelResponse), \
                            "Expected CancelResponse, got %r for %s" % (result, good,))

class MockFetcher(object):
    def __init__(self, response=None):
        self.response = response or HTTPResponse()
        self.fetches = []

    def fetch(self, url, body=None, headers=None):
        self.fetches.append((url, body, headers))
        return self.response

class ExceptionRaisingMockFetcher(object):
    class MyException(Exception):
        pass

    def fetch(self, url, body=None, headers=None):
        raise self.MyException('mock fetcher exception')

class BadArgCheckingConsumer(GenericConsumer):
    def _makeKVPost(self, args, _):
        assert args == {
            'openid.mode':'check_authentication',
            'openid.signed':'foo',
            'openid.ns':OPENID1_NS
            }, args
        return None

class TestCheckAuth(unittest.TestCase, CatchLogs):
    consumer_class = GenericConsumer

    def setUp(self):
        CatchLogs.setUp(self)
        self.store = memstore.MemoryStore()

        self.consumer = self.consumer_class(self.store)

        self._orig_fetcher = fetchers.getDefaultFetcher()
        self.fetcher = MockFetcher()
        fetchers.setDefaultFetcher(self.fetcher)

    def tearDown(self):
        CatchLogs.tearDown(self)
        fetchers.setDefaultFetcher(self._orig_fetcher, wrap_exceptions=False)

    def test_error(self):
        self.fetcher.response = HTTPResponse(
            "http://some_url", 404, {'Hea': 'der'}, 'blah:blah\n')
        query = {'openid.signed': 'stuff',
                 'openid.stuff':'a value'}
        r = self.consumer._checkAuth(Message.fromPostArgs(query),
                                     http_server_url)
        self.failIf(r)
        self.failUnless(self.messages)

    def test_bad_args(self):
        query = {
            'openid.signed':'foo',
            'closid.foo':'something',
            }
        consumer = BadArgCheckingConsumer(self.store)
        consumer._checkAuth(Message.fromPostArgs(query), 'does://not.matter')


    def test_signedList(self):
        query = Message.fromOpenIDArgs({
            'mode': 'id_res',
            'sig': 'rabbits',
            'identity': '=example',
            'assoc_handle': 'munchkins',
            'ns.sreg': 'urn:sreg',
            'sreg.email': 'bogus@example.com',
            'signed': 'identity,mode,ns.sreg,sreg.email',
            'foo': 'bar',
            })
        args = self.consumer._createCheckAuthRequest(query)
        self.failUnless(args.isOpenID1())
        for signed_arg in query.getArg(OPENID_NS, 'signed').split(','):
           self.failUnless(args.getAliasedArg(signed_arg), signed_arg)

    def test_112(self):
        args = {'openid.assoc_handle': 'fa1f5ff0-cde4-11dc-a183-3714bfd55ca8',
                'openid.claimed_id': 'http://binkley.lan/user/test01',
                'openid.identity': 'http://test01.binkley.lan/',
                'openid.mode': 'id_res',
                'openid.ns': 'http://specs.openid.net/auth/2.0',
                'openid.ns.pape': 'http://specs.openid.net/extensions/pape/1.0',
                'openid.op_endpoint': 'http://binkley.lan/server',
                'openid.pape.auth_policies': 'none',
                'openid.pape.auth_time': '2008-01-28T20:42:36Z',
                'openid.pape.nist_auth_level': '0',
                'openid.response_nonce': '2008-01-28T21:07:04Z99Q=',
                'openid.return_to': 'http://binkley.lan:8001/process?janrain_nonce=2008-01-28T21%3A07%3A02Z0tMIKx',
                'openid.sig': 'YJlWH4U6SroB1HoPkmEKx9AyGGg=',
                'openid.signed': 'assoc_handle,identity,response_nonce,return_to,claimed_id,op_endpoint,pape.auth_time,ns.pape,pape.nist_auth_level,pape.auth_policies'
                }
        self.failUnlessEqual(OPENID2_NS, args['openid.ns'])
        incoming = Message.fromPostArgs(args)
        self.failUnless(incoming.isOpenID2())
        car = self.consumer._createCheckAuthRequest(incoming)
        expected_args = args.copy()
        expected_args['openid.mode'] = 'check_authentication'
        expected =Message.fromPostArgs(expected_args)
        self.failUnless(expected.isOpenID2())
        self.failUnlessEqual(expected, car)
        self.failUnlessEqual(expected_args, car.toPostArgs())



class TestFetchAssoc(unittest.TestCase, CatchLogs):
    consumer_class = GenericConsumer

    def setUp(self):
        CatchLogs.setUp(self)
        self.store = memstore.MemoryStore()
        self.fetcher = MockFetcher()
        fetchers.setDefaultFetcher(self.fetcher)
        self.consumer = self.consumer_class(self.store)

    def test_error_404(self):
        """404 from a kv post raises HTTPFetchingError"""
        self.fetcher.response = HTTPResponse(
            "http://some_url", 404, {'Hea': 'der'}, 'blah:blah\n')
        self.failUnlessRaises(
            fetchers.HTTPFetchingError,
            self.consumer._makeKVPost,
            Message.fromPostArgs({'mode':'associate'}),
            "http://server_url")

    def test_error_exception_unwrapped(self):
        """Ensure that exceptions are bubbled through from fetchers
        when making associations
        """
        self.fetcher = ExceptionRaisingMockFetcher()
        fetchers.setDefaultFetcher(self.fetcher, wrap_exceptions=False)
        self.failUnlessRaises(self.fetcher.MyException,
                              self.consumer._makeKVPost,
                              Message.fromPostArgs({'mode':'associate'}),
                              "http://server_url")

        # exception fetching returns no association
        e = OpenIDServiceEndpoint()
        e.server_url = 'some://url'
        self.failUnlessRaises(self.fetcher.MyException,
                              self.consumer._getAssociation, e)

        self.failUnlessRaises(self.fetcher.MyException,
                              self.consumer._checkAuth,
                              Message.fromPostArgs({'openid.signed':''}),
                              'some://url')

    def test_error_exception_wrapped(self):
        """Ensure that openid.fetchers.HTTPFetchingError is caught by
        the association creation stuff.
        """
        self.fetcher = ExceptionRaisingMockFetcher()
        # This will wrap exceptions!
        fetchers.setDefaultFetcher(self.fetcher)
        self.failUnlessRaises(fetchers.HTTPFetchingError,
                              self.consumer._makeKVPost,
                              Message.fromOpenIDArgs({'mode':'associate'}),
                              "http://server_url")

        # exception fetching returns no association
        e = OpenIDServiceEndpoint()
        e.server_url = 'some://url'
        self.failUnless(self.consumer._getAssociation(e) is None)

        msg = Message.fromPostArgs({'openid.signed':''})
        self.failIf(self.consumer._checkAuth(msg, 'some://url'))


class TestSuccessResponse(unittest.TestCase):
    def setUp(self):
        self.endpoint = OpenIDServiceEndpoint()
        self.endpoint.claimed_id = 'identity_url'

    def test_extensionResponse(self):
        resp = mkSuccess(self.endpoint, {
            'ns.sreg':'urn:sreg',
            'ns.unittest':'urn:unittest',
            'unittest.one':'1',
            'unittest.two':'2',
            'sreg.nickname':'j3h',
            'return_to':'return_to',
            })
        utargs = resp.extensionResponse('urn:unittest', False)
        self.failUnlessEqual(utargs, {'one':'1', 'two':'2'})
        sregargs = resp.extensionResponse('urn:sreg', False)
        self.failUnlessEqual(sregargs, {'nickname':'j3h'})

    def test_extensionResponseSigned(self):
        args = {
            'ns.sreg':'urn:sreg',
            'ns.unittest':'urn:unittest',
            'unittest.one':'1',
            'unittest.two':'2',
            'sreg.nickname':'j3h',
            'sreg.dob':'yesterday',
            'return_to':'return_to',
            'signed': 'sreg.nickname,unittest.one,sreg.dob',
            }

        signed_list = ['openid.sreg.nickname',
                       'openid.unittest.one',
                       'openid.sreg.dob',]

        # Don't use mkSuccess because it creates an all-inclusive
        # signed list.
        msg = Message.fromOpenIDArgs(args)
        resp = SuccessResponse(self.endpoint, msg, signed_list)

        # All args in this NS are signed, so expect all.
        sregargs = resp.extensionResponse('urn:sreg', True)
        self.failUnlessEqual(sregargs, {'nickname':'j3h', 'dob': 'yesterday'})

        # Not all args in this NS are signed, so expect None when
        # asking for them.
        utargs = resp.extensionResponse('urn:unittest', True)
        self.failUnlessEqual(utargs, None)

    def test_noReturnTo(self):
        resp = mkSuccess(self.endpoint, {})
        self.failUnless(resp.getReturnTo() is None)

    def test_returnTo(self):
        resp = mkSuccess(self.endpoint, {'return_to':'return_to'})
        self.failUnlessEqual(resp.getReturnTo(), 'return_to')

    def test_displayIdentifierClaimedId(self):
        resp = mkSuccess(self.endpoint, {})
        self.failUnlessEqual(resp.getDisplayIdentifier(),
                             resp.endpoint.claimed_id)

    def test_displayIdentifierOverride(self):
        self.endpoint.display_identifier = "http://input.url/"
        resp = mkSuccess(self.endpoint, {})
        self.failUnlessEqual(resp.getDisplayIdentifier(),
                             "http://input.url/")

class StubConsumer(object):
    def __init__(self):
        self.assoc = object()
        self.response = None
        self.endpoint = None

    def begin(self, service):
        auth_req = AuthRequest(service, self.assoc)
        self.endpoint = service
        return auth_req

    def complete(self, message, endpoint, return_to):
        assert endpoint is self.endpoint
        return self.response

class ConsumerTest(unittest.TestCase):
    """Tests for high-level consumer.Consumer functions.

    Its GenericConsumer component is stubbed out with StubConsumer.
    """
    def setUp(self):
        self.endpoint = OpenIDServiceEndpoint()
        self.endpoint.claimed_id = self.identity_url = 'http://identity.url/'
        self.store = None
        self.session = {}
        self.consumer = Consumer(self.session, self.store)
        self.consumer.consumer = StubConsumer()
        self.discovery = Discovery(self.session,
                                   self.identity_url,
                                   self.consumer.session_key_prefix)

    def test_setAssociationPreference(self):
        self.consumer.setAssociationPreference([])
        self.failUnless(isinstance(self.consumer.consumer.negotiator,
                                   association.SessionNegotiator))
        self.failUnlessEqual([],
                             self.consumer.consumer.negotiator.allowed_types)
        self.consumer.setAssociationPreference([('HMAC-SHA1', 'DH-SHA1')])
        self.failUnlessEqual([('HMAC-SHA1', 'DH-SHA1')],
                             self.consumer.consumer.negotiator.allowed_types)

    def withDummyDiscovery(self, callable, dummy_getNextService):
        class DummyDisco(object):
            def __init__(self, *ignored):
                pass

            getNextService = dummy_getNextService

        import openid.consumer.consumer
        old_discovery = openid.consumer.consumer.Discovery
        try:
            openid.consumer.consumer.Discovery = DummyDisco
            callable()
        finally:
            openid.consumer.consumer.Discovery = old_discovery

    def test_beginHTTPError(self):
        """Make sure that the discovery HTTP failure case behaves properly
        """
        def getNextService(self, ignored):
            raise HTTPFetchingError("Unit test")

        def test():
            try:
                self.consumer.begin('unused in this test')
            except DiscoveryFailure, why:
                self.failUnless(why[0].startswith('Error fetching'))
                self.failIf(why[0].find('Unit test') == -1)
            else:
                self.fail('Expected DiscoveryFailure')

        self.withDummyDiscovery(test, getNextService)

    def test_beginNoServices(self):
        def getNextService(self, ignored):
            return None

        url = 'http://a.user.url/'
        def test():
            try:
                self.consumer.begin(url)
            except DiscoveryFailure, why:
                self.failUnless(why[0].startswith('No usable OpenID'))
                self.failIf(why[0].find(url) == -1)
            else:
                self.fail('Expected DiscoveryFailure')

        self.withDummyDiscovery(test, getNextService)


    def test_beginWithoutDiscovery(self):
        # Does this really test anything non-trivial?
        result = self.consumer.beginWithoutDiscovery(self.endpoint)

        # The result is an auth request
        self.failUnless(isinstance(result, AuthRequest))

        # Side-effect of calling beginWithoutDiscovery is setting the
        # session value to the endpoint attribute of the result
        self.failUnless(self.session[self.consumer._token_key] is result.endpoint)

        # The endpoint that we passed in is the endpoint on the auth_request
        self.failUnless(result.endpoint is self.endpoint)

    def test_completeEmptySession(self):
        text = "failed complete"

        def checkEndpoint(message, endpoint, return_to):
            self.failUnless(endpoint is None)
            return FailureResponse(endpoint, text)

        self.consumer.consumer.complete = checkEndpoint

        response = self.consumer.complete({}, None)
        self.failUnlessEqual(response.status, FAILURE)
        self.failUnlessEqual(response.message, text)
        self.failUnless(response.identity_url is None)

    def _doResp(self, auth_req, exp_resp):
        """complete a transaction, using the expected response from
        the generic consumer."""
        # response is an attribute of StubConsumer, returned by
        # StubConsumer.complete.
        self.consumer.consumer.response = exp_resp

        # endpoint is stored in the session
        self.failUnless(self.session)
        resp = self.consumer.complete({}, None)

        # All responses should have the same identity URL, and the
        # session should be cleaned out
        if self.endpoint.claimed_id != IDENTIFIER_SELECT:
            self.failUnless(resp.identity_url is self.identity_url)

        self.failIf(self.consumer._token_key in self.session)

        # Expected status response
        self.failUnlessEqual(resp.status, exp_resp.status)

        return resp

    def _doRespNoDisco(self, exp_resp):
        """Set up a transaction without discovery"""
        auth_req = self.consumer.beginWithoutDiscovery(self.endpoint)
        resp = self._doResp(auth_req, exp_resp)
        # There should be nothing left in the session once we have completed.
        self.failIf(self.session)
        return resp

    def test_noDiscoCompleteSuccessWithToken(self):
        self._doRespNoDisco(mkSuccess(self.endpoint, {}))

    def test_noDiscoCompleteCancelWithToken(self):
        self._doRespNoDisco(CancelResponse(self.endpoint))

    def test_noDiscoCompleteFailure(self):
        msg = 'failed!'
        resp = self._doRespNoDisco(FailureResponse(self.endpoint, msg))
        self.failUnless(resp.message is msg)

    def test_noDiscoCompleteSetupNeeded(self):
        setup_url = 'http://setup.url/'
        resp = self._doRespNoDisco(
            SetupNeededResponse(self.endpoint, setup_url))
        self.failUnless(resp.setup_url is setup_url)

    # To test that discovery is cleaned up, we need to initialize a
    # Yadis manager, and have it put its values in the session.
    def _doRespDisco(self, is_clean, exp_resp):
        """Set up and execute a transaction, with discovery"""
        self.discovery.createManager([self.endpoint], self.identity_url)
        auth_req = self.consumer.begin(self.identity_url)
        resp = self._doResp(auth_req, exp_resp)

        manager = self.discovery.getManager()
        if is_clean:
            self.failUnless(self.discovery.getManager() is None, manager)
        else:
            self.failIf(self.discovery.getManager() is None, manager)

        return resp

    # Cancel and success DO clean up the discovery process
    def test_completeSuccess(self):
        self._doRespDisco(True, mkSuccess(self.endpoint, {}))

    def test_completeCancel(self):
        self._doRespDisco(True, CancelResponse(self.endpoint))

    # Failure and setup_needed don't clean up the discovery process
    def test_completeFailure(self):
        msg = 'failed!'
        resp = self._doRespDisco(False, FailureResponse(self.endpoint, msg))
        self.failUnless(resp.message is msg)

    def test_completeSetupNeeded(self):
        setup_url = 'http://setup.url/'
        resp = self._doRespDisco(
            False,
            SetupNeededResponse(self.endpoint, setup_url))
        self.failUnless(resp.setup_url is setup_url)

    def test_successDifferentURL(self):
        """
        Be sure that the session gets cleaned up when the response is
        successful and has a different URL than the one in the
        request.
        """
        # Set up a request endpoint describing an IDP URL
        self.identity_url = 'http://idp.url/'
        self.endpoint.claimed_id = self.endpoint.local_id = IDENTIFIER_SELECT

        # Use a response endpoint with a different URL (asserted by
        # the IDP)
        resp_endpoint = OpenIDServiceEndpoint()
        resp_endpoint.claimed_id = "http://user.url/"

        resp = self._doRespDisco(
            True,
            mkSuccess(resp_endpoint, {}))
        self.failUnless(self.discovery.getManager(force=True) is None)

    def test_begin(self):
        self.discovery.createManager([self.endpoint], self.identity_url)
        # Should not raise an exception
        auth_req = self.consumer.begin(self.identity_url)
        self.failUnless(isinstance(auth_req, AuthRequest))
        self.failUnless(auth_req.endpoint is self.endpoint)
        self.failUnless(auth_req.endpoint is self.consumer.consumer.endpoint)
        self.failUnless(auth_req.assoc is self.consumer.consumer.assoc)



class IDPDrivenTest(unittest.TestCase):

    def setUp(self):
        self.store = GoodAssocStore()
        self.consumer = GenericConsumer(self.store)
        self.endpoint = OpenIDServiceEndpoint()
        self.endpoint.server_url = "http://idp.unittest/"


    def test_idpDrivenBegin(self):
        # Testing here that the token-handling doesn't explode...
        self.consumer.begin(self.endpoint)


    def test_idpDrivenComplete(self):
        identifier = '=directed_identifier'
        message = Message.fromPostArgs({
            'openid.identity': '=directed_identifier',
            'openid.return_to': 'x',
            'openid.assoc_handle': 'z',
            'openid.signed': 'identity,return_to',
            'openid.sig': GOODSIG,
            })

        discovered_endpoint = OpenIDServiceEndpoint()
        discovered_endpoint.claimed_id = identifier
        discovered_endpoint.server_url = self.endpoint.server_url
        discovered_endpoint.local_id = identifier
        iverified = []
        def verifyDiscoveryResults(identifier, endpoint):
            self.failUnless(endpoint is self.endpoint)
            iverified.append(discovered_endpoint)
            return discovered_endpoint
        self.consumer._verifyDiscoveryResults = verifyDiscoveryResults
        self.consumer._idResCheckNonce = lambda *args: True
        self.consumer._checkReturnTo = lambda unused1, unused2 : True
        response = self.consumer._doIdRes(message, self.endpoint, None)

        self.failUnlessSuccess(response)
        self.failUnlessEqual(response.identity_url, "=directed_identifier")

        # assert that discovery attempt happens and returns good
        self.failUnlessEqual(iverified, [discovered_endpoint])


    def test_idpDrivenCompleteFraud(self):
        # crap with an identifier that doesn't match discovery info
        message = Message.fromPostArgs({
            'openid.identity': '=directed_identifier',
            'openid.return_to': 'x',
            'openid.assoc_handle': 'z',
            'openid.signed': 'identity,return_to',
            'openid.sig': GOODSIG,
            })
        def verifyDiscoveryResults(identifier, endpoint):
            raise DiscoveryFailure("PHREAK!", None)
        self.consumer._verifyDiscoveryResults = verifyDiscoveryResults
        self.consumer._checkReturnTo = lambda unused1, unused2 : True
        self.failUnlessRaises(DiscoveryFailure, self.consumer._doIdRes,
                              message, self.endpoint, None)


    def failUnlessSuccess(self, response):
        if response.status != SUCCESS:
            self.fail("Non-successful response: %s" % (response,))



class TestDiscoveryVerification(unittest.TestCase):
    services = []

    def setUp(self):
        self.store = GoodAssocStore()
        self.consumer = GenericConsumer(self.store)

        self.consumer._discover = self.discoveryFunc

        self.identifier = "http://idp.unittest/1337"
        self.server_url = "http://endpoint.unittest/"

        self.message = Message.fromPostArgs({
            'openid.ns': OPENID2_NS,
            'openid.identity': self.identifier,
            'openid.claimed_id': self.identifier,
            'openid.op_endpoint': self.server_url,
            })

        self.endpoint = OpenIDServiceEndpoint()
        self.endpoint.server_url = self.server_url

    def test_theGoodStuff(self):
        endpoint = OpenIDServiceEndpoint()
        endpoint.type_uris = [OPENID_2_0_TYPE]
        endpoint.claimed_id = self.identifier
        endpoint.server_url = self.server_url
        endpoint.local_id = self.identifier
        self.services = [endpoint]
        r = self.consumer._verifyDiscoveryResults(self.message, endpoint)

        self.failUnlessEqual(r, endpoint)


    def test_otherServer(self):
        text = "verify failed"

        def discoverAndVerify(claimed_id, to_match_endpoints):
            self.failUnlessEqual(claimed_id, self.identifier)
            for to_match in to_match_endpoints:
                self.failUnlessEqual(claimed_id, to_match.claimed_id)
            raise ProtocolError(text)

        self.consumer._discoverAndVerify = discoverAndVerify

        # a set of things without the stuff
        endpoint = OpenIDServiceEndpoint()
        endpoint.type_uris = [OPENID_2_0_TYPE]
        endpoint.claimed_id = self.identifier
        endpoint.server_url = "http://the-MOON.unittest/"
        endpoint.local_id = self.identifier
        self.services = [endpoint]
        try:
            r = self.consumer._verifyDiscoveryResults(self.message, endpoint)
        except ProtocolError, e:
            # Should we make more ProtocolError subclasses?
            self.failUnless(str(e), text)
        else:
            self.fail("expected ProtocolError, %r returned." % (r,))
            

    def test_foreignDelegate(self):
        text = "verify failed"

        def discoverAndVerify(claimed_id, to_match_endpoints):
            self.failUnlessEqual(claimed_id, self.identifier)
            for to_match in to_match_endpoints:
                self.failUnlessEqual(claimed_id, to_match.claimed_id)
            raise ProtocolError(text)

        self.consumer._discoverAndVerify = discoverAndVerify

        # a set of things with the server stuff but other delegate
        endpoint = OpenIDServiceEndpoint()
        endpoint.type_uris = [OPENID_2_0_TYPE]
        endpoint.claimed_id = self.identifier
        endpoint.server_url = self.server_url
        endpoint.local_id = "http://unittest/juan-carlos"

        try:
            r = self.consumer._verifyDiscoveryResults(self.message, endpoint)
        except ProtocolError, e:
            self.failUnlessEqual(str(e), text)
        else:
            self.fail("Exepected ProtocolError, %r returned" % (r,))

    def test_nothingDiscovered(self):
        # a set of no things.
        self.services = []
        self.failUnlessRaises(DiscoveryFailure,
                              self.consumer._verifyDiscoveryResults,
                              self.message, self.endpoint)


    def discoveryFunc(self, identifier):
        return identifier, self.services


class TestCreateAssociationRequest(unittest.TestCase):
    def setUp(self):
        class DummyEndpoint(object):
            use_compatibility = False

            def compatibilityMode(self):
                return self.use_compatibility

        self.endpoint = DummyEndpoint()
        self.consumer = GenericConsumer(store=None)
        self.assoc_type = 'HMAC-SHA1'

    def test_noEncryptionSendsType(self):
        session_type = 'no-encryption'
        session, args = self.consumer._createAssociateRequest(
            self.endpoint, self.assoc_type, session_type)

        self.failUnless(isinstance(session, PlainTextConsumerSession))
        expected = Message.fromOpenIDArgs(
            {'ns':OPENID2_NS,
             'session_type':session_type,
             'mode':'associate',
             'assoc_type':self.assoc_type,
             })

        self.failUnlessEqual(expected, args)

    def test_noEncryptionCompatibility(self):
        self.endpoint.use_compatibility = True
        session_type = 'no-encryption'
        session, args = self.consumer._createAssociateRequest(
            self.endpoint, self.assoc_type, session_type)

        self.failUnless(isinstance(session, PlainTextConsumerSession))
        self.failUnlessEqual(Message.fromOpenIDArgs({'mode':'associate',
                              'assoc_type':self.assoc_type,
                              }), args)

    def test_dhSHA1Compatibility(self):
        # Set the consumer's session type to a fast session since we
        # need it here.
        setConsumerSession(self.consumer)

        self.endpoint.use_compatibility = True
        session_type = 'DH-SHA1'
        session, args = self.consumer._createAssociateRequest(
            self.endpoint, self.assoc_type, session_type)

        self.failUnless(isinstance(session, DiffieHellmanSHA1ConsumerSession))

        # This is a random base-64 value, so just check that it's
        # present.
        self.failUnless(args.getArg(OPENID1_NS, 'dh_consumer_public'))
        args.delArg(OPENID1_NS, 'dh_consumer_public')

        # OK, session_type is set here and not for no-encryption
        # compatibility
        expected = Message.fromOpenIDArgs({'mode':'associate',
                                           'session_type':'DH-SHA1',
                                           'assoc_type':self.assoc_type,
                                           'dh_modulus': 'BfvStQ==',
                                           'dh_gen': 'Ag==',
                                           })

        self.failUnlessEqual(expected, args)

    # XXX: test the other types

class TestDiffieHellmanResponseParameters(object):
    session_cls = None
    message_namespace = None

    def setUp(self):
        # Pre-compute DH with small prime so tests run quickly.
        self.server_dh = DiffieHellman(100389557, 2)
        self.consumer_dh = DiffieHellman(100389557, 2)

        # base64(btwoc(g ^ xb mod p))
        self.dh_server_public = cryptutil.longToBase64(self.server_dh.public)

        self.secret = cryptutil.randomString(self.session_cls.secret_size)

        self.enc_mac_key = oidutil.toBase64(
            self.server_dh.xorSecret(self.consumer_dh.public,
                                     self.secret,
                                     self.session_cls.hash_func))

        self.consumer_session = self.session_cls(self.consumer_dh)

        self.msg = Message(self.message_namespace)

    def testExtractSecret(self):
        self.msg.setArg(OPENID_NS, 'dh_server_public', self.dh_server_public)
        self.msg.setArg(OPENID_NS, 'enc_mac_key', self.enc_mac_key)

        extracted = self.consumer_session.extractSecret(self.msg)
        self.failUnlessEqual(extracted, self.secret)

    def testAbsentServerPublic(self):
        self.msg.setArg(OPENID_NS, 'enc_mac_key', self.enc_mac_key)

        self.failUnlessRaises(KeyError, self.consumer_session.extractSecret, self.msg)

    def testAbsentMacKey(self):
        self.msg.setArg(OPENID_NS, 'dh_server_public', self.dh_server_public)

        self.failUnlessRaises(KeyError, self.consumer_session.extractSecret, self.msg)

    def testInvalidBase64Public(self):
        self.msg.setArg(OPENID_NS, 'dh_server_public', 'n o t b a s e 6 4.')
        self.msg.setArg(OPENID_NS, 'enc_mac_key', self.enc_mac_key)

        self.failUnlessRaises(ValueError, self.consumer_session.extractSecret, self.msg)

    def testInvalidBase64MacKey(self):
        self.msg.setArg(OPENID_NS, 'dh_server_public', self.dh_server_public)
        self.msg.setArg(OPENID_NS, 'enc_mac_key', 'n o t base 64')

        self.failUnlessRaises(ValueError, self.consumer_session.extractSecret, self.msg)

class TestOpenID1SHA1(TestDiffieHellmanResponseParameters, unittest.TestCase):
    session_cls = DiffieHellmanSHA1ConsumerSession
    message_namespace = OPENID1_NS

class TestOpenID2SHA1(TestDiffieHellmanResponseParameters, unittest.TestCase):
    session_cls = DiffieHellmanSHA1ConsumerSession
    message_namespace = OPENID2_NS

if cryptutil.SHA256_AVAILABLE:
    class TestOpenID2SHA256(TestDiffieHellmanResponseParameters, unittest.TestCase):
        session_cls = DiffieHellmanSHA256ConsumerSession
        message_namespace = OPENID2_NS
else:
    warnings.warn("Not running SHA256 association session tests.")

class TestNoStore(unittest.TestCase):
    def setUp(self):
        self.consumer = GenericConsumer(None)

    def test_completeNoGetAssoc(self):
        """_getAssociation is never called when the store is None"""
        def notCalled(unused):
            self.fail('This method was unexpectedly called')

        endpoint = OpenIDServiceEndpoint()
        endpoint.claimed_id = 'identity_url'

        self.consumer._getAssociation = notCalled
        auth_request = self.consumer.begin(endpoint)
        # _getAssociation was not called




class NonAnonymousAuthRequest(object):
    endpoint = 'unused'

    def setAnonymous(self, unused):
        raise ValueError('Should trigger ProtocolError')

class TestConsumerAnonymous(unittest.TestCase):
    def test_beginWithoutDiscoveryAnonymousFail(self):
        """Make sure that ValueError for setting an auth request
        anonymous gets converted to a ProtocolError
        """
        sess = {}
        consumer = Consumer(sess, None)
        def bogusBegin(unused):
            return NonAnonymousAuthRequest()
        consumer.consumer.begin = bogusBegin
        self.failUnlessRaises(
            ProtocolError,
            consumer.beginWithoutDiscovery, None)


class TestDiscoverAndVerify(unittest.TestCase):
    def setUp(self):
        self.consumer = GenericConsumer(None)
        self.discovery_result = None
        def dummyDiscover(unused_identifier):
            return self.discovery_result
        self.consumer._discover = dummyDiscover
        self.to_match = OpenIDServiceEndpoint()

    def failUnlessDiscoveryFailure(self):
        self.failUnlessRaises(
            DiscoveryFailure,
            self.consumer._discoverAndVerify,
            'http://claimed-id.com/',
            [self.to_match])

    def test_noServices(self):
        """Discovery returning no results results in a
        DiscoveryFailure exception"""
        self.discovery_result = (None, [])
        self.failUnlessDiscoveryFailure()

    def test_noMatches(self):
        """If no discovered endpoint matches the values from the
        assertion, then we end up raising a ProtocolError
        """
        self.discovery_result = (None, ['unused'])
        def raiseProtocolError(unused1, unused2):
            raise ProtocolError('unit test')
        self.consumer._verifyDiscoverySingle = raiseProtocolError
        self.failUnlessDiscoveryFailure()

    def test_matches(self):
        """If an endpoint matches, we return it
        """
        # Discovery returns a single "endpoint" object
        matching_endpoint = 'matching endpoint'
        self.discovery_result = (None, [matching_endpoint])

        # Make verifying discovery return True for this endpoint
        def returnTrue(unused1, unused2):
            return True
        self.consumer._verifyDiscoverySingle = returnTrue

        # Since _verifyDiscoverySingle returns True, we should get the
        # first endpoint that we passed in as a result.
        result = self.consumer._discoverAndVerify(
            'http://claimed.id/', [self.to_match])
        self.failUnlessEqual(matching_endpoint, result)

from openid.extension import Extension
class SillyExtension(Extension):
    ns_uri = 'http://silly.example.com/'
    ns_alias = 'silly'

    def getExtensionArgs(self):
        return {'i_am':'silly'}

class TestAddExtension(unittest.TestCase):

    def test_SillyExtension(self):
        ext = SillyExtension()
        ar = AuthRequest(OpenIDServiceEndpoint(), None)
        ar.addExtension(ext)
        ext_args = ar.message.getArgs(ext.ns_uri)
        self.failUnlessEqual(ext.getExtensionArgs(), ext_args)



class TestKVPost(unittest.TestCase):
    def setUp(self):
        self.server_url = 'http://unittest/%s' % (self.id(),)

    def test_200(self):
        from openid.fetchers import HTTPResponse
        response = HTTPResponse()
        response.status = 200
        response.body = "foo:bar\nbaz:quux\n"
        r = _httpResponseToMessage(response, self.server_url)
        expected_msg = Message.fromOpenIDArgs({'foo':'bar','baz':'quux'})
        self.failUnlessEqual(expected_msg, r)


    def test_400(self):
        response = HTTPResponse()
        response.status = 400
        response.body = "error:bonk\nerror_code:7\n"
        try:
            r = _httpResponseToMessage(response, self.server_url)
        except ServerError, e:
            self.failUnlessEqual(e.error_text, 'bonk')
            self.failUnlessEqual(e.error_code, '7')
        else:
            self.fail("Expected ServerError, got return %r" % (r,))


    def test_500(self):
        # 500 as an example of any non-200, non-400 code.
        response = HTTPResponse()
        response.status = 500
        response.body = "foo:bar\nbaz:quux\n"
        self.failUnlessRaises(fetchers.HTTPFetchingError,
                              _httpResponseToMessage, response,
                              self.server_url)




if __name__ == '__main__':
    unittest.main()

########NEW FILE########
__FILENAME__ = test_discover
# -*- coding: utf-8 -*-
import sys
import unittest
import datadriven
import os.path
from openid import fetchers
from openid.fetchers import HTTPResponse
from openid.yadis.discover import DiscoveryFailure
from openid.consumer import discover
from openid.yadis import xrires
from openid.yadis.xri import XRI
from urlparse import urlsplit
from openid import message

### Tests for conditions that trigger DiscoveryFailure

class SimpleMockFetcher(object):
    def __init__(self, responses):
        self.responses = list(responses)

    def fetch(self, url, body=None, headers=None):
        response = self.responses.pop(0)
        assert body is None
        assert response.final_url == url
        return response

class TestDiscoveryFailure(datadriven.DataDrivenTestCase):
    cases = [
        [HTTPResponse('http://network.error/', None)],
        [HTTPResponse('http://not.found/', 404)],
        [HTTPResponse('http://bad.request/', 400)],
        [HTTPResponse('http://server.error/', 500)],
        [HTTPResponse('http://header.found/', 200,
                      headers={'x-xrds-location':'http://xrds.missing/'}),
         HTTPResponse('http://xrds.missing/', 404)],
        ]

    def __init__(self, responses):
        self.url = responses[0].final_url
        datadriven.DataDrivenTestCase.__init__(self, self.url)
        self.responses = responses

    def setUp(self):
        fetcher = SimpleMockFetcher(self.responses)
        fetchers.setDefaultFetcher(fetcher)

    def tearDown(self):
        fetchers.setDefaultFetcher(None)

    def runOneTest(self):
        expected_status = self.responses[-1].status
        try:
            discover.discover(self.url)
        except DiscoveryFailure, why:
            self.failUnlessEqual(why.http_response.status, expected_status)
        else:
            self.fail('Did not raise DiscoveryFailure')


### Tests for raising/catching exceptions from the fetcher through the
### discover function

# Python 2.5 displays a message when running this test, which is
# testing the behaviour in the presence of string exceptions,
# deprecated or not, so tell it no to complain when this particular
# string exception is raised.
import warnings
warnings.filterwarnings('ignore', 'raising a string.*', DeprecationWarning,
                        r'^openid\.test\.test_discover$', 77)

class ErrorRaisingFetcher(object):
    """Just raise an exception when fetch is called"""

    def __init__(self, thing_to_raise):
        self.thing_to_raise = thing_to_raise

    def fetch(self, url, body=None, headers=None):
        raise self.thing_to_raise

class DidFetch(Exception):
    """Custom exception just to make sure it's not handled differently"""

class TestFetchException(datadriven.DataDrivenTestCase):
    """Make sure exceptions get passed through discover function from
    fetcher."""

    cases = [
        Exception(),
        DidFetch(),
        ValueError(),
        RuntimeError(),
        ]

    # String exceptions are finally gone from Python 2.6.
    if sys.version_info[:2] < (2, 6):
        cases.append('oi!')

    def __init__(self, exc):
        datadriven.DataDrivenTestCase.__init__(self, repr(exc))
        self.exc = exc

    def setUp(self):
        fetcher = ErrorRaisingFetcher(self.exc)
        fetchers.setDefaultFetcher(fetcher, wrap_exceptions=False)

    def tearDown(self):
        fetchers.setDefaultFetcher(None)

    def runOneTest(self):
        try:
            discover.discover('http://doesnt.matter/')
        except:
            exc = sys.exc_info()[1]
            if exc is None:
                # str exception
                self.failUnless(self.exc is sys.exc_info()[0])
            else:
                self.failUnless(self.exc is exc, exc)
        else:
            self.fail('Expected %r', self.exc)


### Tests for openid.consumer.discover.discover

class TestNormalization(unittest.TestCase):
    def testAddingProtocol(self):
        f = ErrorRaisingFetcher(RuntimeError())
        fetchers.setDefaultFetcher(f, wrap_exceptions=False)

        try:
            discover.discover('users.stompy.janrain.com:8000/x')
        except DiscoveryFailure, why:
            self.fail('failed to parse url with port correctly')
        except RuntimeError:
            pass #expected

        fetchers.setDefaultFetcher(None)


class DiscoveryMockFetcher(object):
    redirect = None

    def __init__(self, documents):
        self.documents = documents
        self.fetchlog = []

    def fetch(self, url, body=None, headers=None):
        self.fetchlog.append((url, body, headers))
        if self.redirect:
            final_url = self.redirect
        else:
            final_url = url

        try:
            ctype, body = self.documents[url]
        except KeyError:
            status = 404
            ctype = 'text/plain'
            body = ''
        else:
            status = 200

        return HTTPResponse(final_url, status, {'content-type': ctype}, body)

# from twisted.trial import unittest as trialtest

class BaseTestDiscovery(unittest.TestCase):
    id_url = "http://someuser.unittest/"

    documents = {}
    fetcherClass = DiscoveryMockFetcher

    def _checkService(self, s,
                      server_url,
                      claimed_id=None,
                      local_id=None,
                      canonical_id=None,
                      types=None,
                      used_yadis=False,
                      display_identifier=None
                      ):
        self.failUnlessEqual(server_url, s.server_url)
        if types == ['2.0 OP']:
            self.failIf(claimed_id)
            self.failIf(local_id)
            self.failIf(s.claimed_id)
            self.failIf(s.local_id)
            self.failIf(s.getLocalID())
            self.failIf(s.compatibilityMode())
            self.failUnless(s.isOPIdentifier())
            self.failUnlessEqual(s.preferredNamespace(),
                                 discover.OPENID_2_0_MESSAGE_NS)
        else:
            self.failUnlessEqual(claimed_id, s.claimed_id)
            self.failUnlessEqual(local_id, s.getLocalID())

        if used_yadis:
            self.failUnless(s.used_yadis, "Expected to use Yadis")
        else:
            self.failIf(s.used_yadis,
                        "Expected to use old-style discovery")

        openid_types = {
            '1.1': discover.OPENID_1_1_TYPE,
            '1.0': discover.OPENID_1_0_TYPE,
            '2.0': discover.OPENID_2_0_TYPE,
            '2.0 OP': discover.OPENID_IDP_2_0_TYPE,
            }

        type_uris = [openid_types[t] for t in types]
        self.failUnlessEqual(type_uris, s.type_uris)
        self.failUnlessEqual(canonical_id, s.canonicalID)

        if s.canonicalID:
            self.failUnless(s.getDisplayIdentifier() != claimed_id)
            self.failUnless(s.getDisplayIdentifier() is not None)
            self.failUnlessEqual(display_identifier, s.getDisplayIdentifier())
            self.failUnlessEqual(s.claimed_id, s.canonicalID)

        self.failUnlessEqual(s.display_identifier or s.claimed_id, s.getDisplayIdentifier())

    def setUp(self):
        self.documents = self.documents.copy()
        self.fetcher = self.fetcherClass(self.documents)
        fetchers.setDefaultFetcher(self.fetcher)

    def tearDown(self):
        fetchers.setDefaultFetcher(None)

def readDataFile(filename):
    module_directory = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(
        module_directory, 'data', 'test_discover', filename)
    return file(filename).read()

class TestDiscovery(BaseTestDiscovery):
    def _discover(self, content_type, data,
                  expected_services, expected_id=None):
        if expected_id is None:
            expected_id = self.id_url

        self.documents[self.id_url] = (content_type, data)
        id_url, services = discover.discover(self.id_url)
        self.failUnlessEqual(expected_services, len(services))
        self.failUnlessEqual(expected_id, id_url)
        return services

    def test_404(self):
        self.failUnlessRaises(DiscoveryFailure,
                              discover.discover, self.id_url + '/404')

    def test_unicode(self):
        """
        Check page with unicode and HTML entities
        """
        self._discover(
            content_type='text/html;charset=utf-8',
            data=readDataFile('unicode.html'),
            expected_services=0)

    def test_unicode_undecodable_html(self):
        """
        Check page with unicode and HTML entities that can not be decoded
        """
        data = readDataFile('unicode2.html')
        self.failUnlessRaises(UnicodeDecodeError, data.decode, 'utf-8')
        self._discover(content_type='text/html;charset=utf-8',
            data=data, expected_services=0)

    def test_unicode_undecodable_html2(self):
        """
        Check page with unicode and HTML entities that can not be decoded
        but xrds document is found before it matters
        """
        self.documents[self.id_url + 'xrds'] = (
            'application/xrds+xml', readDataFile('yadis_idp.xml'))

        data = readDataFile('unicode3.html')
        self.failUnlessRaises(UnicodeDecodeError, data.decode, 'utf-8')
        self._discover(content_type='text/html;charset=utf-8',
            data=data, expected_services=1)

    def test_noOpenID(self):
        services = self._discover(content_type='text/plain',
                                  data="junk",
                                  expected_services=0)

        services = self._discover(
            content_type='text/html',
            data=readDataFile('openid_no_delegate.html'),
            expected_services=1,
            )

        self._checkService(
            services[0],
            used_yadis=False,
            types=['1.1'],
            server_url="http://www.myopenid.com/server",
            claimed_id=self.id_url,
            local_id=self.id_url,
            )

    def test_html1(self):
        services = self._discover(
            content_type='text/html',
            data=readDataFile('openid.html'),
            expected_services=1)


        self._checkService(
            services[0],
            used_yadis=False,
            types=['1.1'],
            server_url="http://www.myopenid.com/server",
            claimed_id=self.id_url,
            local_id='http://smoker.myopenid.com/',
            display_identifier=self.id_url,
            )

    def test_html1Fragment(self):
        """Ensure that the Claimed Identifier does not have a fragment
        if one is supplied in the User Input."""
        content_type = 'text/html'
        data = readDataFile('openid.html')
        expected_services = 1

        self.documents[self.id_url] = (content_type, data)
        expected_id = self.id_url
        self.id_url = self.id_url + '#fragment'
        id_url, services = discover.discover(self.id_url)
        self.failUnlessEqual(expected_services, len(services))
        self.failUnlessEqual(expected_id, id_url)

        self._checkService(
            services[0],
            used_yadis=False,
            types=['1.1'],
            server_url="http://www.myopenid.com/server",
            claimed_id=expected_id,
            local_id='http://smoker.myopenid.com/',
            display_identifier=expected_id,
            )

    def test_html2(self):
        services = self._discover(
            content_type='text/html',
            data=readDataFile('openid2.html'),
            expected_services=1,
            )

        self._checkService(
            services[0],
            used_yadis=False,
            types=['2.0'],
            server_url="http://www.myopenid.com/server",
            claimed_id=self.id_url,
            local_id='http://smoker.myopenid.com/',
            display_identifier=self.id_url,
            )

    def test_html1And2(self):
        services = self._discover(
            content_type='text/html',
            data=readDataFile('openid_1_and_2.html'),
            expected_services=2,
            )

        for t, s in zip(['2.0', '1.1'], services):
            self._checkService(
                s,
                used_yadis=False,
                types=[t],
                server_url="http://www.myopenid.com/server",
                claimed_id=self.id_url,
                local_id='http://smoker.myopenid.com/',
                display_identifier=self.id_url,
                )

    def test_yadisEmpty(self):
        services = self._discover(content_type='application/xrds+xml',
                                  data=readDataFile('yadis_0entries.xml'),
                                  expected_services=0)

    def test_htmlEmptyYadis(self):
        """HTML document has discovery information, but points to an
        empty Yadis document."""
        # The XRDS document pointed to by "openid_and_yadis.html"
        self.documents[self.id_url + 'xrds'] = (
            'application/xrds+xml', readDataFile('yadis_0entries.xml'))

        services = self._discover(content_type='text/html',
                                  data=readDataFile('openid_and_yadis.html'),
                                  expected_services=1)

        self._checkService(
            services[0],
            used_yadis=False,
            types=['1.1'],
            server_url="http://www.myopenid.com/server",
            claimed_id=self.id_url,
            local_id='http://smoker.myopenid.com/',
            display_identifier=self.id_url,
            )

    def test_yadis1NoDelegate(self):
        services = self._discover(content_type='application/xrds+xml',
                                  data=readDataFile('yadis_no_delegate.xml'),
                                  expected_services=1)

        self._checkService(
            services[0],
            used_yadis=True,
            types=['1.0'],
            server_url="http://www.myopenid.com/server",
            claimed_id=self.id_url,
            local_id=self.id_url,
            display_identifier=self.id_url,
            )

    def test_yadis2NoLocalID(self):
        services = self._discover(
            content_type='application/xrds+xml',
            data=readDataFile('openid2_xrds_no_local_id.xml'),
            expected_services=1,
            )

        self._checkService(
            services[0],
            used_yadis=True,
            types=['2.0'],
            server_url="http://www.myopenid.com/server",
            claimed_id=self.id_url,
            local_id=self.id_url,
            display_identifier=self.id_url,
            )

    def test_yadis2(self):
        services = self._discover(
            content_type='application/xrds+xml',
            data=readDataFile('openid2_xrds.xml'),
            expected_services=1,
            )

        self._checkService(
            services[0],
            used_yadis=True,
            types=['2.0'],
            server_url="http://www.myopenid.com/server",
            claimed_id=self.id_url,
            local_id='http://smoker.myopenid.com/',
            display_identifier=self.id_url,
            )

    def test_yadis2OP(self):
        services = self._discover(
            content_type='application/xrds+xml',
            data=readDataFile('yadis_idp.xml'),
            expected_services=1,
            )

        self._checkService(
            services[0],
            used_yadis=True,
            types=['2.0 OP'],
            server_url="http://www.myopenid.com/server",
            display_identifier=self.id_url,
            )

    def test_yadis2OPDelegate(self):
        """The delegate tag isn't meaningful for OP entries."""
        services = self._discover(
            content_type='application/xrds+xml',
            data=readDataFile('yadis_idp_delegate.xml'),
            expected_services=1,
            )

        self._checkService(
            services[0],
            used_yadis=True,
            types=['2.0 OP'],
            server_url="http://www.myopenid.com/server",
            display_identifier=self.id_url,
            )

    def test_yadis2BadLocalID(self):
        self.failUnlessRaises(DiscoveryFailure, self._discover,
            content_type='application/xrds+xml',
            data=readDataFile('yadis_2_bad_local_id.xml'),
            expected_services=1,
            )

    def test_yadis1And2(self):
        services = self._discover(
            content_type='application/xrds+xml',
            data=readDataFile('openid_1_and_2_xrds.xml'),
            expected_services=1,
            )

        self._checkService(
            services[0],
            used_yadis=True,
            types=['2.0', '1.1'],
            server_url="http://www.myopenid.com/server",
            claimed_id=self.id_url,
            local_id='http://smoker.myopenid.com/',
            display_identifier=self.id_url,
            )

    def test_yadis1And2BadLocalID(self):
        self.failUnlessRaises(DiscoveryFailure, self._discover,
            content_type='application/xrds+xml',
            data=readDataFile('openid_1_and_2_xrds_bad_delegate.xml'),
            expected_services=1,
            )

class MockFetcherForXRIProxy(object):

    def __init__(self, documents, proxy_url=xrires.DEFAULT_PROXY):
        self.documents = documents
        self.fetchlog = []
        self.proxy_url = None


    def fetch(self, url, body=None, headers=None):
        self.fetchlog.append((url, body, headers))

        u = urlsplit(url)
        proxy_host = u[1]
        xri = u[2]
        query = u[3]

        if not headers and not query:
            raise ValueError("No headers or query; you probably didn't "
                             "mean to do that.")

        if xri.startswith('/'):
            xri = xri[1:]

        try:
            ctype, body = self.documents[xri]
        except KeyError:
            status = 404
            ctype = 'text/plain'
            body = ''
        else:
            status = 200

        return HTTPResponse(url, status, {'content-type': ctype}, body)


class TestXRIDiscovery(BaseTestDiscovery):
    fetcherClass = MockFetcherForXRIProxy

    documents = {'=smoker': ('application/xrds+xml',
                             readDataFile('yadis_2entries_delegate.xml')),
                 '=smoker*bad': ('application/xrds+xml',
                                 readDataFile('yadis_another_delegate.xml')) }

    def test_xri(self):
        user_xri, services = discover.discoverXRI('=smoker')

        self._checkService(
            services[0],
            used_yadis=True,
            types=['1.0'],
            server_url="http://www.myopenid.com/server",
            claimed_id=XRI("=!1000"),
            canonical_id=XRI("=!1000"),
            local_id='http://smoker.myopenid.com/',
            display_identifier='=smoker'
            )

        self._checkService(
            services[1],
            used_yadis=True,
            types=['1.0'],
            server_url="http://www.livejournal.com/openid/server.bml",
            claimed_id=XRI("=!1000"),
            canonical_id=XRI("=!1000"),
            local_id='http://frank.livejournal.com/',
            display_identifier='=smoker'
            )

    def test_xri_normalize(self):
        user_xri, services = discover.discoverXRI('xri://=smoker')

        self._checkService(
            services[0],
            used_yadis=True,
            types=['1.0'],
            server_url="http://www.myopenid.com/server",
            claimed_id=XRI("=!1000"),
            canonical_id=XRI("=!1000"),
            local_id='http://smoker.myopenid.com/',
            display_identifier='=smoker'
            )

        self._checkService(
            services[1],
            used_yadis=True,
            types=['1.0'],
            server_url="http://www.livejournal.com/openid/server.bml",
            claimed_id=XRI("=!1000"),
            canonical_id=XRI("=!1000"),
            local_id='http://frank.livejournal.com/',
            display_identifier='=smoker'
            )

    def test_xriNoCanonicalID(self):
        user_xri, services = discover.discoverXRI('=smoker*bad')
        self.failIf(services)

    def test_useCanonicalID(self):
        """When there is no delegate, the CanonicalID should be used with XRI.
        """
        endpoint = discover.OpenIDServiceEndpoint()
        endpoint.claimed_id = XRI("=!1000")
        endpoint.canonicalID = XRI("=!1000")
        self.failUnlessEqual(endpoint.getLocalID(), XRI("=!1000"))


class TestXRIDiscoveryIDP(BaseTestDiscovery):
    fetcherClass = MockFetcherForXRIProxy

    documents = {'=smoker': ('application/xrds+xml',
                             readDataFile('yadis_2entries_idp.xml')) }

    def test_xri(self):
        user_xri, services = discover.discoverXRI('=smoker')
        self.failUnless(services, "Expected services, got zero")
        self.failUnlessEqual(services[0].server_url,
                             "http://www.livejournal.com/openid/server.bml")


class TestPreferredNamespace(datadriven.DataDrivenTestCase):
    def __init__(self, expected_ns, type_uris):
        datadriven.DataDrivenTestCase.__init__(
            self, 'Expecting %s from %s' % (expected_ns, type_uris))
        self.expected_ns = expected_ns
        self.type_uris = type_uris

    def runOneTest(self):
        endpoint = discover.OpenIDServiceEndpoint()
        endpoint.type_uris = self.type_uris
        actual_ns = endpoint.preferredNamespace()
        self.failUnlessEqual(actual_ns, self.expected_ns)

    cases = [
        (message.OPENID1_NS, []),
        (message.OPENID1_NS, ['http://jyte.com/']),
        (message.OPENID1_NS, [discover.OPENID_1_0_TYPE]),
        (message.OPENID1_NS, [discover.OPENID_1_1_TYPE]),
        (message.OPENID2_NS, [discover.OPENID_2_0_TYPE]),
        (message.OPENID2_NS, [discover.OPENID_IDP_2_0_TYPE]),
        (message.OPENID2_NS, [discover.OPENID_2_0_TYPE,
                              discover.OPENID_1_0_TYPE]),
        (message.OPENID2_NS, [discover.OPENID_1_0_TYPE,
                              discover.OPENID_2_0_TYPE]),
        ]

class TestIsOPIdentifier(unittest.TestCase):
    def setUp(self):
        self.endpoint = discover.OpenIDServiceEndpoint()

    def test_none(self):
        self.failIf(self.endpoint.isOPIdentifier())

    def test_openid1_0(self):
        self.endpoint.type_uris = [discover.OPENID_1_0_TYPE]
        self.failIf(self.endpoint.isOPIdentifier())

    def test_openid1_1(self):
        self.endpoint.type_uris = [discover.OPENID_1_1_TYPE]
        self.failIf(self.endpoint.isOPIdentifier())

    def test_openid2(self):
        self.endpoint.type_uris = [discover.OPENID_2_0_TYPE]
        self.failIf(self.endpoint.isOPIdentifier())

    def test_openid2OP(self):
        self.endpoint.type_uris = [discover.OPENID_IDP_2_0_TYPE]
        self.failUnless(self.endpoint.isOPIdentifier())

    def test_multipleMissing(self):
        self.endpoint.type_uris = [discover.OPENID_2_0_TYPE,
                                   discover.OPENID_1_0_TYPE]
        self.failIf(self.endpoint.isOPIdentifier())

    def test_multiplePresent(self):
        self.endpoint.type_uris = [discover.OPENID_2_0_TYPE,
                                   discover.OPENID_1_0_TYPE,
                                   discover.OPENID_IDP_2_0_TYPE]
        self.failUnless(self.endpoint.isOPIdentifier())

class TestFromOPEndpointURL(unittest.TestCase):
    def setUp(self):
        self.op_endpoint_url = 'http://example.com/op/endpoint'
        self.endpoint = discover.OpenIDServiceEndpoint.fromOPEndpointURL(
            self.op_endpoint_url)

    def test_isOPEndpoint(self):
        self.failUnless(self.endpoint.isOPIdentifier())

    def test_noIdentifiers(self):
        self.failUnlessEqual(self.endpoint.getLocalID(), None)
        self.failUnlessEqual(self.endpoint.claimed_id, None)

    def test_compatibility(self):
        self.failIf(self.endpoint.compatibilityMode())

    def test_canonicalID(self):
        self.failUnlessEqual(self.endpoint.canonicalID, None)

    def test_serverURL(self):
        self.failUnlessEqual(self.endpoint.server_url, self.op_endpoint_url)

class TestDiscoverFunction(unittest.TestCase):
    def setUp(self):
        self._old_discoverURI = discover.discoverURI
        self._old_discoverXRI = discover.discoverXRI

        discover.discoverXRI = self.discoverXRI
        discover.discoverURI = self.discoverURI

    def tearDown(self):
        discover.discoverURI = self._old_discoverURI
        discover.discoverXRI = self._old_discoverXRI

    def discoverXRI(self, identifier):
        return 'XRI'

    def discoverURI(self, identifier):
        return 'URI'

    def test_uri(self):
        self.failUnlessEqual('URI', discover.discover('http://woo!'))

    def test_uriForBogus(self):
        self.failUnlessEqual('URI', discover.discover('not a URL or XRI'))

    def test_xri(self):
        self.failUnlessEqual('XRI', discover.discover('xri://=something'))

    def test_xriChar(self):
        self.failUnlessEqual('XRI', discover.discover('=something'))

class TestEndpointSupportsType(unittest.TestCase):
    def setUp(self):
        self.endpoint = discover.OpenIDServiceEndpoint()

    def failUnlessSupportsOnly(self, *types):
        for t in [
            'foo',
            discover.OPENID_1_1_TYPE,
            discover.OPENID_1_0_TYPE,
            discover.OPENID_2_0_TYPE,
            discover.OPENID_IDP_2_0_TYPE,
            ]:
            if t in types:
                self.failUnless(self.endpoint.supportsType(t),
                                "Must support %r" % (t,))
            else:
                self.failIf(self.endpoint.supportsType(t),
                            "Shouldn't support %r" % (t,))

    def test_supportsNothing(self):
        self.failUnlessSupportsOnly()

    def test_openid2(self):
        self.endpoint.type_uris = [discover.OPENID_2_0_TYPE]
        self.failUnlessSupportsOnly(discover.OPENID_2_0_TYPE)

    def test_openid2provider(self):
        self.endpoint.type_uris = [discover.OPENID_IDP_2_0_TYPE]
        self.failUnlessSupportsOnly(discover.OPENID_IDP_2_0_TYPE,
                                    discover.OPENID_2_0_TYPE)

    def test_openid1_0(self):
        self.endpoint.type_uris = [discover.OPENID_1_0_TYPE]
        self.failUnlessSupportsOnly(discover.OPENID_1_0_TYPE)

    def test_openid1_1(self):
        self.endpoint.type_uris = [discover.OPENID_1_1_TYPE]
        self.failUnlessSupportsOnly(discover.OPENID_1_1_TYPE)

    def test_multiple(self):
        self.endpoint.type_uris = [discover.OPENID_1_1_TYPE,
                                   discover.OPENID_2_0_TYPE]
        self.failUnlessSupportsOnly(discover.OPENID_1_1_TYPE,
                                    discover.OPENID_2_0_TYPE)

    def test_multipleWithProvider(self):
        self.endpoint.type_uris = [discover.OPENID_1_1_TYPE,
                                   discover.OPENID_2_0_TYPE,
                                   discover.OPENID_IDP_2_0_TYPE]
        self.failUnlessSupportsOnly(discover.OPENID_1_1_TYPE,
                                    discover.OPENID_2_0_TYPE,
                                    discover.OPENID_IDP_2_0_TYPE,
                                    )


class TestEndpointDisplayIdentifier(unittest.TestCase):
    def test_strip_fragment(self):
        endpoint = discover.OpenIDServiceEndpoint()
        endpoint.claimed_id = 'http://recycled.invalid/#123'
        self.failUnlessEqual('http://recycled.invalid/', endpoint.getDisplayIdentifier())


def pyUnitTests():
    return datadriven.loadTests(__name__)

if __name__ == '__main__':
    suite = pyUnitTests()
    runner = unittest.TextTestRunner()
    runner.run(suite)

########NEW FILE########
__FILENAME__ = test_etxrd
import unittest
from openid.yadis import services, etxrd, xri
import os.path

def datapath(filename):
    module_directory = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(module_directory, 'data', 'test_etxrd', filename)

XRD_FILE =  datapath('valid-populated-xrds.xml')
NOXRDS_FILE = datapath('not-xrds.xml')
NOXRD_FILE = datapath('no-xrd.xml')

# None of the namespaces or service URIs below are official (or even
# sanctioned by the owners of that piece of URL-space)

LID_2_0 = "http://lid.netmesh.org/sso/2.0b5"
TYPEKEY_1_0 = "http://typekey.com/services/1.0"

def simpleOpenIDTransformer(endpoint):
    """Function to extract information from an OpenID service element"""
    if 'http://openid.net/signon/1.0' not in endpoint.type_uris:
        return None

    delegates = list(endpoint.service_element.findall(
        '{http://openid.net/xmlns/1.0}Delegate'))
    assert len(delegates) == 1
    delegate = delegates[0].text
    return (endpoint.uri, delegate)

class TestServiceParser(unittest.TestCase):
    def setUp(self):
        self.xmldoc = file(XRD_FILE).read()
        self.yadis_url = 'http://unittest.url/'

    def _getServices(self, flt=None):
        return list(services.applyFilter(self.yadis_url, self.xmldoc, flt))

    def testParse(self):
        """Make sure that parsing succeeds at all"""
        services = self._getServices()

    def testParseOpenID(self):
        """Parse for OpenID services with a transformer function"""
        services = self._getServices(simpleOpenIDTransformer)

        expectedServices = [
            ("http://www.myopenid.com/server", "http://josh.myopenid.com/"),
            ("http://www.schtuff.com/openid", "http://users.schtuff.com/josh"),
            ("http://www.livejournal.com/openid/server.bml",
             "http://www.livejournal.com/users/nedthealpaca/"),
            ]

        it = iter(services)
        for (server_url, delegate) in expectedServices:
            for (actual_url, actual_delegate) in it:
                self.failUnlessEqual(server_url, actual_url)
                self.failUnlessEqual(delegate, actual_delegate)
                break
            else:
                self.fail('Not enough services found')

    def _checkServices(self, expectedServices):
        """Check to make sure that the expected services are found in
        that order in the parsed document."""
        it = iter(self._getServices())
        for (type_uri, uri) in expectedServices:
            for service in it:
                if type_uri in service.type_uris:
                    self.failUnlessEqual(service.uri, uri)
                    break
            else:
                self.fail('Did not find %r service' % (type_uri,))

    def testGetSeveral(self):
        """Get some services in order"""
        expectedServices = [
            # type, URL
            (TYPEKEY_1_0, None),
            (LID_2_0, "http://mylid.net/josh"),
            ]

        self._checkServices(expectedServices)

    def testGetSeveralForOne(self):
        """Getting services for one Service with several Type elements."""
        types = [ 'http://lid.netmesh.org/sso/2.0b5'
                , 'http://lid.netmesh.org/2.0b5'
                ]

        uri = "http://mylid.net/josh"

        for service in self._getServices():
            if service.uri == uri:
                found_types = service.matchTypes(types)
                if found_types == types:
                    break
        else:
            self.fail('Did not find service with expected types and uris')

    def testNoXRDS(self):
        """Make sure that we get an exception when an XRDS element is
        not present"""
        self.xmldoc = file(NOXRDS_FILE).read()
        self.failUnlessRaises(
            etxrd.XRDSError,
            services.applyFilter, self.yadis_url, self.xmldoc, None)

    def testEmpty(self):
        """Make sure that we get an exception when an XRDS element is
        not present"""
        self.xmldoc = ''
        self.failUnlessRaises(
            etxrd.XRDSError,
            services.applyFilter, self.yadis_url, self.xmldoc, None)

    def testNoXRD(self):
        """Make sure that we get an exception when there is no XRD
        element present."""
        self.xmldoc = file(NOXRD_FILE).read()
        self.failUnlessRaises(
            etxrd.XRDSError,
            services.applyFilter, self.yadis_url, self.xmldoc, None)


class TestCanonicalID(unittest.TestCase):

    def mkTest(iname, filename, expectedID):
        """This function builds a method that runs the CanonicalID
        test for the given set of inputs"""

        filename = datapath(filename)
        def test(self):
            xrds = etxrd.parseXRDS(file(filename).read())
            self._getCanonicalID(iname, xrds, expectedID)
        return test

    test_delegated = mkTest(
        "@ootao*test1", "delegated-20060809.xrds",
        "@!5BAD.2AA.3C72.AF46!0000.0000.3B9A.CA01")

    test_delegated_r1 = mkTest(
        "@ootao*test1", "delegated-20060809-r1.xrds",
        "@!5BAD.2AA.3C72.AF46!0000.0000.3B9A.CA01")

    test_delegated_r2 = mkTest(
        "@ootao*test1", "delegated-20060809-r2.xrds",
        "@!5BAD.2AA.3C72.AF46!0000.0000.3B9A.CA01")

    test_sometimesprefix = mkTest(
        "@ootao*test1", "sometimesprefix.xrds",
        "@!5BAD.2AA.3C72.AF46!0000.0000.3B9A.CA01")

    test_prefixsometimes = mkTest(
        "@ootao*test1", "prefixsometimes.xrds",
        "@!5BAD.2AA.3C72.AF46!0000.0000.3B9A.CA01")

    test_spoof1 = mkTest("=keturn*isDrummond", "spoof1.xrds", etxrd.XRDSFraud)

    test_spoof2 = mkTest("=keturn*isDrummond", "spoof2.xrds", etxrd.XRDSFraud)

    test_spoof3 = mkTest("@keturn*is*drummond", "spoof3.xrds", etxrd.XRDSFraud)

    test_status222 = mkTest("=x", "status222.xrds", None)

    test_multisegment_xri = mkTest('xri://=nishitani*masaki',
                                   'subsegments.xrds',
                                   '=!E117.EF2F.454B.C707!0000.0000.3B9A.CA01')

    test_iri_auth_not_allowed = mkTest(
        "phreak.example.com", "delegated-20060809-r2.xrds", etxrd.XRDSFraud)
    test_iri_auth_not_allowed.__doc__ = \
        "Don't let IRI authorities be canonical for the GCS."

    # TODO: Refs
    # test_ref = mkTest("@ootao*test.ref", "ref.xrds", "@!BAE.A650.823B.2475")

    # TODO: Add a IRI authority with an IRI canonicalID.
    # TODO: Add test cases with real examples of multiple CanonicalIDs
    #   somewhere in the resolution chain.

    def _getCanonicalID(self, iname, xrds, expectedID):
        if isinstance(expectedID, (str, unicode, type(None))):
            cid = etxrd.getCanonicalID(iname, xrds)
            self.failUnlessEqual(cid, expectedID and xri.XRI(expectedID))
        elif issubclass(expectedID, etxrd.XRDSError):
            self.failUnlessRaises(expectedID, etxrd.getCanonicalID,
                                  iname, xrds)
        else:
            self.fail("Don't know how to test for expected value %r"
                      % (expectedID,))


if __name__ == '__main__':
    unittest.main()

########NEW FILE########
__FILENAME__ = test_examples
"Test some examples."

import socket
import os.path, unittest, sys, time
from cStringIO import StringIO

import twill.commands, twill.parse, twill.unit

from openid.consumer.discover import \
     OpenIDServiceEndpoint, OPENID_1_1_TYPE
from openid.consumer.consumer import AuthRequest

class TwillTest(twill.unit.TestInfo):
    """Variant of twill.unit.TestInfo that runs a function as a test script,
    not twill script from a file.
    """

    # twill.unit is pretty small to start with, we're overriding
    # run_script and bypassing twill.parse, so it may make sense to
    # rewrite twill.unit altogether.

    # Desirable features:
    #  * better unittest.TestCase integration.
    #     - handle logs on setup and teardown.
    #     - treat TwillAssertionError as failed test assertion, make twill
    #       assertions more consistant with TestCase.failUnless idioms.
    #     - better error reporting on failed assertions.
    #     - The amount of functions passed back and forth between TestInfo
    #       and TestCase is currently pretty silly.
    #  * access to child process's logs.
    #       TestInfo.start_server redirects stdout/stderr to StringIO
    #       objects which are, afaict, inaccessible to the caller of
    #       test.unit.run_child_process.
    #  * notice when the child process dies, i.e. if you muck up and
    #       your runExampleServer function throws an exception.

    def run_script(self):
        time.sleep(self.sleep)
        # twill.commands.go(self.get_url())
        self.script(self)


def splitDir(d, count):
    # in python2.4 and above, it's easier to spell this as
    # d.rsplit(os.sep, count)
    for i in xrange(count):
        d = os.path.dirname(d)
    return d

def runExampleServer(host, port, data_path):
    thisfile = os.path.abspath(sys.modules[__name__].__file__)
    topDir = splitDir(thisfile, 3)
    exampleDir = os.path.join(topDir, 'examples')
    serverExample = os.path.join(exampleDir, 'server.py')
    serverModule = {}
    execfile(serverExample, serverModule)
    serverMain = serverModule['main']

    serverMain(host, port, data_path)



class TestServer(unittest.TestCase):
    """Acceptance tests for examples/server.py.

    These are more acceptance tests than unit tests as they actually
    start the whole server running and test it on its external HTTP
    interface.
    """

    def setUp(self):
        self.twillOutput = StringIO()
        self.twillErr = StringIO()
        twill.set_output(self.twillOutput)
        twill.set_errout(self.twillErr)
        # FIXME: make sure we pick an available port.
        self.server_port = 8080

        # We need something to feed the server as a realm, but it needn't
        # be reachable.  (Until we test realm verification.)
        self.realm = 'http://127.0.0.1/%s' % (self.id(),)
        self.return_to = self.realm + '/return_to'

        twill.commands.reset_browser()


    def runExampleServer(self):
        """Zero-arg run-the-server function to be passed to TestInfo."""
        # FIXME - make sure sstore starts clean.
        runExampleServer('127.0.0.1', self.server_port, 'sstore')


    def v1endpoint(self, port):
        """Return an OpenID 1.1 OpenIDServiceEndpoint for the server."""
        base = "http://%s:%s" % (socket.getfqdn('127.0.0.1'), port)
        ep = OpenIDServiceEndpoint()
        ep.claimed_id = base + "/id/bob"
        ep.server_url = base + "/openidserver"
        ep.type_uris = [OPENID_1_1_TYPE]
        return ep


    # TODO: test discovery

    def test_checkidv1(self):
        """OpenID 1.1 checkid_setup request."""
        ti = TwillTest(self.twill_checkidv1, self.runExampleServer,
                       self.server_port, sleep=0.2)
        twill.unit.run_test(ti)

        if self.twillErr.getvalue():
            self.fail(self.twillErr.getvalue())


    def test_allowed(self):
        """OpenID 1.1 checkid_setup request."""
        ti = TwillTest(self.twill_allowed, self.runExampleServer,
                       self.server_port, sleep=0.2)
        twill.unit.run_test(ti)

        if self.twillErr.getvalue():
            self.fail(self.twillErr.getvalue())


    def twill_checkidv1(self, twillInfo):
        endpoint = self.v1endpoint(self.server_port)
        authreq = AuthRequest(endpoint, assoc=None)
        url = authreq.redirectURL(self.realm, self.return_to)

        c = twill.commands

        try:
            c.go(url)
            c.get_browser()._browser.set_handle_redirect(False)
            c.submit("yes")
            c.code(302)
            headers = c.get_browser()._browser.response().info()
            finalURL = headers['Location']
            self.failUnless('openid.mode=id_res' in finalURL, finalURL)
            self.failUnless('openid.identity=' in finalURL, finalURL)
        except twill.commands.TwillAssertionError, e:
            msg = '%s\nFinal page:\n%s' % (
                str(e), c.get_browser().get_html())
            self.fail(msg)


    def twill_allowed(self, twillInfo):
        endpoint = self.v1endpoint(self.server_port)
        authreq = AuthRequest(endpoint, assoc=None)
        url = authreq.redirectURL(self.realm, self.return_to)

        c = twill.commands

        try:
            c.go(url)
            c.code(200)
            c.get_browser()._browser.set_handle_redirect(False)
            c.formvalue(1, 'remember', 'true')
            c.find('name="login_as" value="bob"')
            c.submit("yes")
            c.code(302)
            # Since we set remember=yes, the second time we shouldn't
            # see that page.
            c.go(url)
            c.code(302)
            headers = c.get_browser()._browser.response().info()
            finalURL = headers['Location']
            self.failUnless(finalURL.startswith(self.return_to))
        except twill.commands.TwillAssertionError, e:
            from traceback import format_exc
            msg = '%s\nTwill output:%s\nTwill errors:%s\nFinal page:\n%s' % (
                format_exc(),
                self.twillOutput.getvalue(),
                self.twillErr.getvalue(),
                c.get_browser().get_html())
            self.fail(msg)


    def tearDown(self):
        twill.set_output(None)
        twill.set_errout(None)


if __name__ == '__main__':
    unittest.main()

########NEW FILE########
__FILENAME__ = test_extension
from openid import extension
from openid import message

import unittest

class DummyExtension(extension.Extension):
    ns_uri = 'http://an.extension/'
    ns_alias = 'dummy'

    def getExtensionArgs(self):
        return {}

class ToMessageTest(unittest.TestCase):
    def test_OpenID1(self):
        oid1_msg = message.Message(message.OPENID1_NS)
        ext = DummyExtension()
        ext.toMessage(oid1_msg)
        namespaces = oid1_msg.namespaces
        self.failUnless(namespaces.isImplicit(DummyExtension.ns_uri))
        self.failUnlessEqual(
            DummyExtension.ns_uri,
            namespaces.getNamespaceURI(DummyExtension.ns_alias))
        self.failUnlessEqual(DummyExtension.ns_alias,
                             namespaces.getAlias(DummyExtension.ns_uri))

    def test_OpenID2(self):
        oid2_msg = message.Message(message.OPENID2_NS)
        ext = DummyExtension()
        ext.toMessage(oid2_msg)
        namespaces = oid2_msg.namespaces
        self.failIf(namespaces.isImplicit(DummyExtension.ns_uri))
        self.failUnlessEqual(
            DummyExtension.ns_uri,
            namespaces.getNamespaceURI(DummyExtension.ns_alias))
        self.failUnlessEqual(DummyExtension.ns_alias,
                             namespaces.getAlias(DummyExtension.ns_uri))

########NEW FILE########
__FILENAME__ = test_fetchers
import warnings
import unittest
import sys
import urllib2
import socket

from openid import fetchers

# XXX: make these separate test cases

def failUnlessResponseExpected(expected, actual):
    assert expected.final_url == actual.final_url, (
        "%r != %r" % (expected.final_url, actual.final_url))
    assert expected.status == actual.status
    assert expected.body == actual.body
    got_headers = dict(actual.headers)
    del got_headers['date']
    del got_headers['server']
    for k, v in expected.headers.iteritems():
        assert got_headers[k] == v, (k, v, got_headers[k])

def test_fetcher(fetcher, exc, server):
    def geturl(path):
        return 'http://%s:%s%s' % (socket.getfqdn(server.server_name),
                                   server.socket.getsockname()[1],
                                   path)

    expected_headers = {'content-type':'text/plain'}

    def plain(path, code):
        path = '/' + path
        expected = fetchers.HTTPResponse(
            geturl(path), code, expected_headers, path)
        return (path, expected)

    expect_success = fetchers.HTTPResponse(
        geturl('/success'), 200, expected_headers, '/success')
    cases = [
        ('/success', expect_success),
        ('/301redirect', expect_success),
        ('/302redirect', expect_success),
        ('/303redirect', expect_success),
        ('/307redirect', expect_success),
        plain('notfound', 404),
        plain('badreq', 400),
        plain('forbidden', 403),
        plain('error', 500),
        plain('server_error', 503),
        ]

    for path, expected in cases:
        fetch_url = geturl(path)
        try:
            actual = fetcher.fetch(fetch_url)
        except (SystemExit, KeyboardInterrupt):
            pass
        except:
            print fetcher, fetch_url
            raise
        else:
            failUnlessResponseExpected(expected, actual)

    for err_url in [geturl('/closed'),
                    'http://invalid.janrain.com/',
                    'not:a/url',
                    'ftp://janrain.com/pub/']:
        try:
            result = fetcher.fetch(err_url)
        except (KeyboardInterrupt, SystemExit):
            raise
        except fetchers.HTTPError, why:
            # This is raised by the Curl fetcher for bad cases
            # detected by the fetchers module, but it's a subclass of
            # HTTPFetchingError, so we have to catch it explicitly.
            assert exc
        except fetchers.HTTPFetchingError, why:
            assert not exc, (fetcher, exc, server)
        except:
            assert exc
        else:
            assert False, 'An exception was expected for %r (%r)' % (fetcher, result)

def run_fetcher_tests(server):
    exc_fetchers = []
    for klass, library_name in [
        (fetchers.Urllib2Fetcher, 'urllib2'),
        (fetchers.CurlHTTPFetcher, 'pycurl'),
        (fetchers.HTTPLib2Fetcher, 'httplib2'),
        ]:
        try:
            exc_fetchers.append(klass())
        except RuntimeError, why:
            if why[0].startswith('Cannot find %s library' % (library_name,)):
                try:
                    __import__(library_name)
                except ImportError:
                    warnings.warn(
                        'Skipping tests for %r fetcher because '
                        'the library did not import.' % (library_name,))
                    pass
                else:
                    assert False, ('%s present but not detected' % (library_name,))
            else:
                raise

    non_exc_fetchers = []
    for f in exc_fetchers:
        non_exc_fetchers.append(fetchers.ExceptionWrappingFetcher(f))

    for f in exc_fetchers:
        test_fetcher(f, True, server)

    for f in non_exc_fetchers:
        test_fetcher(f, False, server)

from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

class FetcherTestHandler(BaseHTTPRequestHandler):
    cases = {
        '/success':(200, None),
        '/301redirect':(301, '/success'),
        '/302redirect':(302, '/success'),
        '/303redirect':(303, '/success'),
        '/307redirect':(307, '/success'),
        '/notfound':(404, None),
        '/badreq':(400, None),
        '/forbidden':(403, None),
        '/error':(500, None),
        '/server_error':(503, None),
        }

    def log_request(self, *args):
        pass

    def do_GET(self):
        if self.path == '/closed':
            self.wfile.close()
        else:
            try:
                http_code, location = self.cases[self.path]
            except KeyError:
                self.errorResponse('Bad path')
            else:
                extra_headers = [('Content-type', 'text/plain')]
                if location is not None:
                    host, port = self.server.server_address
                    base = ('http://%s:%s' % (socket.getfqdn(host), port,))
                    location = base + location
                    extra_headers.append(('Location', location))
                self._respond(http_code, extra_headers, self.path)

    def do_POST(self):
        try:
            http_code, extra_headers = self.cases[self.path]
        except KeyError:
            self.errorResponse('Bad path')
        else:
            if http_code in [301, 302, 303, 307]:
                self.errorResponse()
            else:
                content_type = self.headers.get('content-type', 'text/plain')
                extra_headers.append(('Content-type', content_type))
                content_length = int(self.headers.get('Content-length', '-1'))
                body = self.rfile.read(content_length)
                self._respond(http_code, extra_headers, body)

    def errorResponse(self, message=None):
        req = [
            ('HTTP method', self.command),
            ('path', self.path),
            ]
        if message:
            req.append(('message', message))

        body_parts = ['Bad request:\r\n']
        for k, v in req:
            body_parts.append(' %s: %s\r\n' % (k, v))
        body = ''.join(body_parts)
        self._respond(400, [('Content-type', 'text/plain')], body)

    def _respond(self, http_code, extra_headers, body):
        self.send_response(http_code)
        for k, v in extra_headers:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)
        self.wfile.close()

    def finish(self):
        if not self.wfile.closed:
            self.wfile.flush()
        self.wfile.close()
        self.rfile.close()

def test():
    import socket
    host = socket.getfqdn('127.0.0.1')
    # When I use port 0 here, it works for the first fetch and the
    # next one gets connection refused.  Bummer.  So instead, pick a
    # port that's *probably* not in use.
    import os
    port = (os.getpid() % 31000) + 1024

    server = HTTPServer((host, port), FetcherTestHandler)

    import threading
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.setDaemon(True)
    server_thread.start()

    run_fetcher_tests(server)

class FakeFetcher(object):
    sentinel = object()

    def fetch(self, *args, **kwargs):
        return self.sentinel

class DefaultFetcherTest(unittest.TestCase):
    def setUp(self):
        """reset the default fetcher to None"""
        fetchers.setDefaultFetcher(None)

    def tearDown(self):
        """reset the default fetcher to None"""
        fetchers.setDefaultFetcher(None)

    def test_getDefaultNotNone(self):
        """Make sure that None is never returned as a default fetcher"""
        self.failUnless(fetchers.getDefaultFetcher() is not None)
        fetchers.setDefaultFetcher(None)
        self.failUnless(fetchers.getDefaultFetcher() is not None)

    def test_setDefault(self):
        """Make sure the getDefaultFetcher returns the object set for
        setDefaultFetcher"""
        sentinel = object()
        fetchers.setDefaultFetcher(sentinel, wrap_exceptions=False)
        self.failUnless(fetchers.getDefaultFetcher() is sentinel)

    def test_callFetch(self):
        """Make sure that fetchers.fetch() uses the default fetcher
        instance that was set."""
        fetchers.setDefaultFetcher(FakeFetcher())
        actual = fetchers.fetch('bad://url')
        self.failUnless(actual is FakeFetcher.sentinel)

    def test_wrappedByDefault(self):
        """Make sure that the default fetcher instance wraps
        exceptions by default"""
        default_fetcher = fetchers.getDefaultFetcher()
        self.failUnless(isinstance(default_fetcher,
                                   fetchers.ExceptionWrappingFetcher),
                        default_fetcher)

        self.failUnlessRaises(fetchers.HTTPFetchingError,
                              fetchers.fetch, 'http://invalid.janrain.com/')

    def test_notWrapped(self):
        """Make sure that if we set a non-wrapped fetcher as default,
        it will not wrap exceptions."""
        # A fetcher that will raise an exception when it encounters a
        # host that will not resolve
        fetcher = fetchers.Urllib2Fetcher()
        fetchers.setDefaultFetcher(fetcher, wrap_exceptions=False)

        self.failIf(isinstance(fetchers.getDefaultFetcher(),
                               fetchers.ExceptionWrappingFetcher))

        try:
            fetchers.fetch('http://invalid.janrain.com/')
        except fetchers.HTTPFetchingError:
            self.fail('Should not be wrapping exception')
        except:
            exc = sys.exc_info()[1]
            self.failUnless(isinstance(exc, urllib2.URLError), exc)
            pass
        else:
            self.fail('Should have raised an exception')

def pyUnitTests():
    case1 = unittest.FunctionTestCase(test)
    loadTests = unittest.defaultTestLoader.loadTestsFromTestCase
    case2 = loadTests(DefaultFetcherTest)
    return unittest.TestSuite([case1, case2])

########NEW FILE########
__FILENAME__ = test_htmldiscover
from openid.consumer.discover import OpenIDServiceEndpoint
import datadriven

class BadLinksTestCase(datadriven.DataDrivenTestCase):
    cases = [
        '',
        "http://not.in.a.link.tag/",
        '<link rel="openid.server" href="not.in.html.or.head" />',
        ]

    def __init__(self, data):
        datadriven.DataDrivenTestCase.__init__(self, data)
        self.data = data

    def runOneTest(self):
        actual = OpenIDServiceEndpoint.fromHTML('http://unused.url/', self.data)
        expected = []
        self.failUnlessEqual(expected, actual)

def pyUnitTests():
    return datadriven.loadTests(__name__)

########NEW FILE########
__FILENAME__ = test_message
# -*- coding: utf-8 -*-
from openid import message
from openid import oidutil
from openid.extensions import sreg

import urllib
import cgi
import unittest

def mkGetArgTest(ns, key, expected=None):
    def test(self):
        a_default = object()
        self.failUnlessEqual(self.msg.getArg(ns, key), expected)
        if expected is None:
            self.failUnlessEqual(
                self.msg.getArg(ns, key, a_default), a_default)
            self.failUnlessRaises(
                KeyError, self.msg.getArg, ns, key, message.no_default)
        else:
            self.failUnlessEqual(
                self.msg.getArg(ns, key, a_default), expected)
            self.failUnlessEqual(
                self.msg.getArg(ns, key, message.no_default), expected)

    return test

class EmptyMessageTest(unittest.TestCase):
    def setUp(self):
        self.msg = message.Message()

    def test_toPostArgs(self):
        self.failUnlessEqual(self.msg.toPostArgs(), {})

    def test_toArgs(self):
        self.failUnlessEqual(self.msg.toArgs(), {})

    def test_toKVForm(self):
        self.failUnlessEqual(self.msg.toKVForm(), '')

    def test_toURLEncoded(self):
        self.failUnlessEqual(self.msg.toURLEncoded(), '')

    def test_toURL(self):
        base_url = 'http://base.url/'
        self.failUnlessEqual(self.msg.toURL(base_url), base_url)

    def test_getOpenID(self):
        self.failUnlessEqual(self.msg.getOpenIDNamespace(), None)

    def test_getKeyOpenID(self):
        # Could reasonably return None instead of raising an
        # exception. I'm not sure which one is more right, since this
        # case should only happen when you're building a message from
        # scratch and so have no default namespace.
        self.failUnlessRaises(message.UndefinedOpenIDNamespace,
                              self.msg.getKey, message.OPENID_NS, 'foo')

    def test_getKeyBARE(self):
        self.failUnlessEqual(self.msg.getKey(message.BARE_NS, 'foo'), 'foo')

    def test_getKeyNS1(self):
        self.failUnlessEqual(self.msg.getKey(message.OPENID1_NS, 'foo'), None)

    def test_getKeyNS2(self):
        self.failUnlessEqual(self.msg.getKey(message.OPENID2_NS, 'foo'), None)

    def test_getKeyNS3(self):
        self.failUnlessEqual(self.msg.getKey('urn:nothing-significant', 'foo'),
                             None)

    def test_hasKey(self):
        # Could reasonably return False instead of raising an
        # exception. I'm not sure which one is more right, since this
        # case should only happen when you're building a message from
        # scratch and so have no default namespace.
        self.failUnlessRaises(message.UndefinedOpenIDNamespace,
                              self.msg.hasKey, message.OPENID_NS, 'foo')

    def test_hasKeyBARE(self):
        self.failUnlessEqual(self.msg.hasKey(message.BARE_NS, 'foo'), False)

    def test_hasKeyNS1(self):
        self.failUnlessEqual(self.msg.hasKey(message.OPENID1_NS, 'foo'), False)

    def test_hasKeyNS2(self):
        self.failUnlessEqual(self.msg.hasKey(message.OPENID2_NS, 'foo'), False)

    def test_hasKeyNS3(self):
        self.failUnlessEqual(self.msg.hasKey('urn:nothing-significant', 'foo'),
                             False)

    def test_getAliasedArgSuccess(self):
        msg = message.Message.fromPostArgs({'openid.ns.test': 'urn://foo',
                                            'openid.test.flub': 'bogus'})
        actual_uri = msg.getAliasedArg('ns.test', message.no_default)
        self.assertEquals("urn://foo", actual_uri)
    
    def test_getAliasedArgFailure(self):
        msg = message.Message.fromPostArgs({'openid.test.flub': 'bogus'})
        self.assertRaises(KeyError,
                          msg.getAliasedArg, 'ns.test', message.no_default)

    def test_getArg(self):
        # Could reasonably return None instead of raising an
        # exception. I'm not sure which one is more right, since this
        # case should only happen when you're building a message from
        # scratch and so have no default namespace.
        self.failUnlessRaises(message.UndefinedOpenIDNamespace,
                              self.msg.getArg, message.OPENID_NS, 'foo')

    test_getArgBARE = mkGetArgTest(message.BARE_NS, 'foo')
    test_getArgNS1 = mkGetArgTest(message.OPENID1_NS, 'foo')
    test_getArgNS2 = mkGetArgTest(message.OPENID2_NS, 'foo')
    test_getArgNS3 = mkGetArgTest('urn:nothing-significant', 'foo')

    def test_getArgs(self):
        # Could reasonably return {} instead of raising an
        # exception. I'm not sure which one is more right, since this
        # case should only happen when you're building a message from
        # scratch and so have no default namespace.
        self.failUnlessRaises(message.UndefinedOpenIDNamespace,
                              self.msg.getArgs, message.OPENID_NS)

    def test_getArgsBARE(self):
        self.failUnlessEqual(self.msg.getArgs(message.BARE_NS), {})

    def test_getArgsNS1(self):
        self.failUnlessEqual(self.msg.getArgs(message.OPENID1_NS), {})

    def test_getArgsNS2(self):
        self.failUnlessEqual(self.msg.getArgs(message.OPENID2_NS), {})

    def test_getArgsNS3(self):
        self.failUnlessEqual(self.msg.getArgs('urn:nothing-significant'), {})

    def test_updateArgs(self):
        self.failUnlessRaises(message.UndefinedOpenIDNamespace,
                              self.msg.updateArgs, message.OPENID_NS,
                              {'does not':'matter'})

    def _test_updateArgsNS(self, ns):
        update_args = {
            'Camper van Beethoven':'David Lowery',
            'Magnolia Electric Co.':'Jason Molina',
            }

        self.failUnlessEqual(self.msg.getArgs(ns), {})
        self.msg.updateArgs(ns, update_args)
        self.failUnlessEqual(self.msg.getArgs(ns), update_args)

    def test_updateArgsBARE(self):
        self._test_updateArgsNS(message.BARE_NS)

    def test_updateArgsNS1(self):
        self._test_updateArgsNS(message.OPENID1_NS)

    def test_updateArgsNS2(self):
        self._test_updateArgsNS(message.OPENID2_NS)

    def test_updateArgsNS3(self):
        self._test_updateArgsNS('urn:nothing-significant')

    def test_setArg(self):
        self.failUnlessRaises(message.UndefinedOpenIDNamespace,
                              self.msg.setArg, message.OPENID_NS,
                              'does not', 'matter')

    def _test_setArgNS(self, ns):
        key = 'Camper van Beethoven'
        value = 'David Lowery'
        self.failUnlessEqual(self.msg.getArg(ns, key), None)
        self.msg.setArg(ns, key, value)
        self.failUnlessEqual(self.msg.getArg(ns, key), value)

    def test_setArgBARE(self):
        self._test_setArgNS(message.BARE_NS)

    def test_setArgNS1(self):
        self._test_setArgNS(message.OPENID1_NS)

    def test_setArgNS2(self):
        self._test_setArgNS(message.OPENID2_NS)

    def test_setArgNS3(self):
        self._test_setArgNS('urn:nothing-significant')

    def test_setArgToNone(self):
        self.failUnlessRaises(AssertionError, self.msg.setArg,
                              message.OPENID1_NS, 'op_endpoint', None)

    def test_delArg(self):
        # Could reasonably raise KeyError instead of raising
        # UndefinedOpenIDNamespace. I'm not sure which one is more
        # right, since this case should only happen when you're
        # building a message from scratch and so have no default
        # namespace.
        self.failUnlessRaises(message.UndefinedOpenIDNamespace,
                              self.msg.delArg, message.OPENID_NS, 'key')

    def _test_delArgNS(self, ns):
        key = 'Camper van Beethoven'
        self.failUnlessRaises(KeyError, self.msg.delArg, ns, key)

    def test_delArgBARE(self):
        self._test_delArgNS(message.BARE_NS)

    def test_delArgNS1(self):
        self._test_delArgNS(message.OPENID1_NS)

    def test_delArgNS2(self):
        self._test_delArgNS(message.OPENID2_NS)

    def test_delArgNS3(self):
        self._test_delArgNS('urn:nothing-significant')

    def test_isOpenID1(self):
        self.failIf(self.msg.isOpenID1())

    def test_isOpenID2(self):
        self.failIf(self.msg.isOpenID2())

class OpenID1MessageTest(unittest.TestCase):
    def setUp(self):
        self.msg = message.Message.fromPostArgs({'openid.mode':'error',
                                                 'openid.error':'unit test'})

    def test_toPostArgs(self):
        self.failUnlessEqual(self.msg.toPostArgs(),
                             {'openid.mode':'error',
                              'openid.error':'unit test'})

    def test_toArgs(self):
        self.failUnlessEqual(self.msg.toArgs(), {'mode':'error',
                                                 'error':'unit test'})

    def test_toKVForm(self):
        self.failUnlessEqual(self.msg.toKVForm(),
                             'error:unit test\nmode:error\n')

    def test_toURLEncoded(self):
        self.failUnlessEqual(self.msg.toURLEncoded(),
                             'openid.error=unit+test&openid.mode=error')

    def test_toURL(self):
        base_url = 'http://base.url/'
        actual = self.msg.toURL(base_url)
        actual_base = actual[:len(base_url)]
        self.failUnlessEqual(actual_base, base_url)
        self.failUnlessEqual(actual[len(base_url)], '?')
        query = actual[len(base_url) + 1:]
        parsed = cgi.parse_qs(query)
        self.failUnlessEqual(parsed, {'openid.mode':['error'],
                                      'openid.error':['unit test']})

    def test_getOpenID(self):
        self.failUnlessEqual(self.msg.getOpenIDNamespace(), message.OPENID1_NS)

    def test_getKeyOpenID(self):
        self.failUnlessEqual(self.msg.getKey(message.OPENID_NS, 'mode'),
                             'openid.mode')

    def test_getKeyBARE(self):
        self.failUnlessEqual(self.msg.getKey(message.BARE_NS, 'mode'), 'mode')

    def test_getKeyNS1(self):
        self.failUnlessEqual(
            self.msg.getKey(message.OPENID1_NS, 'mode'), 'openid.mode')

    def test_getKeyNS2(self):
        self.failUnlessEqual(self.msg.getKey(message.OPENID2_NS, 'mode'), None)

    def test_getKeyNS3(self):
        self.failUnlessEqual(
            self.msg.getKey('urn:nothing-significant', 'mode'), None)

    def test_hasKey(self):
        self.failUnlessEqual(self.msg.hasKey(message.OPENID_NS, 'mode'), True)

    def test_hasKeyBARE(self):
        self.failUnlessEqual(self.msg.hasKey(message.BARE_NS, 'mode'), False)

    def test_hasKeyNS1(self):
        self.failUnlessEqual(self.msg.hasKey(message.OPENID1_NS, 'mode'), True)

    def test_hasKeyNS2(self):
        self.failUnlessEqual(
            self.msg.hasKey(message.OPENID2_NS, 'mode'), False)

    def test_hasKeyNS3(self):
        self.failUnlessEqual(
            self.msg.hasKey('urn:nothing-significant', 'mode'), False)

    test_getArgBARE = mkGetArgTest(message.BARE_NS, 'mode')
    test_getArgNS = mkGetArgTest(message.OPENID_NS, 'mode', 'error')
    test_getArgNS1 = mkGetArgTest(message.OPENID1_NS, 'mode', 'error')
    test_getArgNS2 = mkGetArgTest(message.OPENID2_NS, 'mode')
    test_getArgNS3 = mkGetArgTest('urn:nothing-significant', 'mode')

    def test_getArgs(self):
        self.failUnlessEqual(self.msg.getArgs(message.OPENID_NS),
                             {'mode':'error',
                              'error':'unit test',
                              })

    def test_getArgsBARE(self):
        self.failUnlessEqual(self.msg.getArgs(message.BARE_NS), {})

    def test_getArgsNS1(self):
        self.failUnlessEqual(self.msg.getArgs(message.OPENID1_NS),
                             {'mode':'error',
                              'error':'unit test',
                              })

    def test_getArgsNS2(self):
        self.failUnlessEqual(self.msg.getArgs(message.OPENID2_NS), {})

    def test_getArgsNS3(self):
        self.failUnlessEqual(self.msg.getArgs('urn:nothing-significant'), {})

    def _test_updateArgsNS(self, ns, before=None):
        if before is None:
            before = {}
        update_args = {
            'Camper van Beethoven':'David Lowery',
            'Magnolia Electric Co.':'Jason Molina',
            }

        self.failUnlessEqual(self.msg.getArgs(ns), before)
        self.msg.updateArgs(ns, update_args)
        after = dict(before)
        after.update(update_args)
        self.failUnlessEqual(self.msg.getArgs(ns), after)

    def test_updateArgs(self):
        self._test_updateArgsNS(message.OPENID_NS,
                                before={'mode':'error', 'error':'unit test'})

    def test_updateArgsBARE(self):
        self._test_updateArgsNS(message.BARE_NS)

    def test_updateArgsNS1(self):
        self._test_updateArgsNS(message.OPENID1_NS,
                                before={'mode':'error', 'error':'unit test'})

    def test_updateArgsNS2(self):
        self._test_updateArgsNS(message.OPENID2_NS)

    def test_updateArgsNS3(self):
        self._test_updateArgsNS('urn:nothing-significant')

    def _test_setArgNS(self, ns):
        key = 'Camper van Beethoven'
        value = 'David Lowery'
        self.failUnlessEqual(self.msg.getArg(ns, key), None)
        self.msg.setArg(ns, key, value)
        self.failUnlessEqual(self.msg.getArg(ns, key), value)

    def test_setArg(self):
        self._test_setArgNS(message.OPENID_NS)

    def test_setArgBARE(self):
        self._test_setArgNS(message.BARE_NS)

    def test_setArgNS1(self):
        self._test_setArgNS(message.OPENID1_NS)

    def test_setArgNS2(self):
        self._test_setArgNS(message.OPENID2_NS)

    def test_setArgNS3(self):
        self._test_setArgNS('urn:nothing-significant')

    def _test_delArgNS(self, ns):
        key = 'Camper van Beethoven'
        value = 'David Lowery'

        self.failUnlessRaises(KeyError, self.msg.delArg, ns, key)
        self.msg.setArg(ns, key, value)
        self.failUnlessEqual(self.msg.getArg(ns, key), value)
        self.msg.delArg(ns, key)
        self.failUnlessEqual(self.msg.getArg(ns, key), None)

    def test_delArg(self):
        self._test_delArgNS(message.OPENID_NS)

    def test_delArgBARE(self):
        self._test_delArgNS(message.BARE_NS)

    def test_delArgNS1(self):
        self._test_delArgNS(message.OPENID1_NS)

    def test_delArgNS2(self):
        self._test_delArgNS(message.OPENID2_NS)

    def test_delArgNS3(self):
        self._test_delArgNS('urn:nothing-significant')


    def test_isOpenID1(self):
        self.failUnless(self.msg.isOpenID1())

    def test_isOpenID2(self):
        self.failIf(self.msg.isOpenID2())

class OpenID1ExplicitMessageTest(unittest.TestCase):
    def setUp(self):
        self.msg = message.Message.fromPostArgs({'openid.mode':'error',
                                                 'openid.error':'unit test',
                                                 'openid.ns':message.OPENID1_NS
                                                 })

    def test_toPostArgs(self):
        self.failUnlessEqual(self.msg.toPostArgs(),
                             {'openid.mode':'error',
                              'openid.error':'unit test',
                              'openid.ns':message.OPENID1_NS
                              })

    def test_toArgs(self):
        self.failUnlessEqual(self.msg.toArgs(), {'mode':'error',
                                                 'error':'unit test',
                                                 'ns':message.OPENID1_NS})

    def test_toKVForm(self):
        self.failUnlessEqual(self.msg.toKVForm(),
                             'error:unit test\nmode:error\nns:%s\n'
                              %message.OPENID1_NS)

    def test_toURLEncoded(self):
        self.failUnlessEqual(self.msg.toURLEncoded(),
                             'openid.error=unit+test&openid.mode=error&openid.ns=http%3A%2F%2Fopenid.net%2Fsignon%2F1.0')

    def test_toURL(self):
        base_url = 'http://base.url/'
        actual = self.msg.toURL(base_url)
        actual_base = actual[:len(base_url)]
        self.failUnlessEqual(actual_base, base_url)
        self.failUnlessEqual(actual[len(base_url)], '?')
        query = actual[len(base_url) + 1:]
        parsed = cgi.parse_qs(query)
        self.failUnlessEqual(parsed, {'openid.mode':['error'],
                                      'openid.error':['unit test'],
                                      'openid.ns':[message.OPENID1_NS]
                                      })

    def test_isOpenID1(self):
        self.failUnless(self.msg.isOpenID1())

class OpenID2MessageTest(unittest.TestCase):
    def setUp(self):
        self.msg = message.Message.fromPostArgs({'openid.mode':'error',
                                                 'openid.error':'unit test',
                                                 'openid.ns':message.OPENID2_NS
                                                 })
        self.msg.setArg(message.BARE_NS, "xey", "value")

    def test_toPostArgs(self):
        self.failUnlessEqual(self.msg.toPostArgs(),
                             {'openid.mode':'error',
                              'openid.error':'unit test',
                              'openid.ns':message.OPENID2_NS,
                              'xey': 'value',
                              })

    def test_toPostArgs_bug_with_utf8_encoded_values(self):
        msg = message.Message.fromPostArgs({'openid.mode':'error',
                                            'openid.error':'unit test',
                                            'openid.ns':message.OPENID2_NS
                                             })
        msg.setArg(message.BARE_NS, 'ünicöde_key', 'ünicöde_välüe')
        self.failUnlessEqual(msg.toPostArgs(),
                             {'openid.mode':'error',
                              'openid.error':'unit test',
                              'openid.ns':message.OPENID2_NS,
                              'ünicöde_key': 'ünicöde_välüe',
                              })


    def test_toArgs(self):
        # This method can't tolerate BARE_NS.
        self.msg.delArg(message.BARE_NS, "xey")
        self.failUnlessEqual(self.msg.toArgs(), {'mode':'error',
                                                 'error':'unit test',
                                                 'ns':message.OPENID2_NS,
                                                 })

    def test_toKVForm(self):
        # Can't tolerate BARE_NS in kvform
        self.msg.delArg(message.BARE_NS, "xey")
        self.failUnlessEqual(self.msg.toKVForm(),
                             'error:unit test\nmode:error\nns:%s\n' %
                             (message.OPENID2_NS,))

    def _test_urlencoded(self, s):
        expected = ('openid.error=unit+test&openid.mode=error&'
                    'openid.ns=%s&xey=value' % (
            urllib.quote(message.OPENID2_NS, ''),))
        self.failUnlessEqual(s, expected)


    def test_toURLEncoded(self):
        self._test_urlencoded(self.msg.toURLEncoded())

    def test_toURL(self):
        base_url = 'http://base.url/'
        actual = self.msg.toURL(base_url)
        actual_base = actual[:len(base_url)]
        self.failUnlessEqual(actual_base, base_url)
        self.failUnlessEqual(actual[len(base_url)], '?')
        query = actual[len(base_url) + 1:]
        self._test_urlencoded(query)

    def test_getOpenID(self):
        self.failUnlessEqual(self.msg.getOpenIDNamespace(), message.OPENID2_NS)

    def test_getKeyOpenID(self):
        self.failUnlessEqual(self.msg.getKey(message.OPENID_NS, 'mode'),
                             'openid.mode')

    def test_getKeyBARE(self):
        self.failUnlessEqual(self.msg.getKey(message.BARE_NS, 'mode'), 'mode')

    def test_getKeyNS1(self):
        self.failUnlessEqual(
            self.msg.getKey(message.OPENID1_NS, 'mode'), None)

    def test_getKeyNS2(self):
        self.failUnlessEqual(
            self.msg.getKey(message.OPENID2_NS, 'mode'), 'openid.mode')

    def test_getKeyNS3(self):
        self.failUnlessEqual(
            self.msg.getKey('urn:nothing-significant', 'mode'), None)

    def test_hasKeyOpenID(self):
        self.failUnlessEqual(self.msg.hasKey(message.OPENID_NS, 'mode'), True)

    def test_hasKeyBARE(self):
        self.failUnlessEqual(self.msg.hasKey(message.BARE_NS, 'mode'), False)

    def test_hasKeyNS1(self):
        self.failUnlessEqual(
            self.msg.hasKey(message.OPENID1_NS, 'mode'), False)

    def test_hasKeyNS2(self):
        self.failUnlessEqual(
            self.msg.hasKey(message.OPENID2_NS, 'mode'), True)

    def test_hasKeyNS3(self):
        self.failUnlessEqual(
            self.msg.hasKey('urn:nothing-significant', 'mode'), False)

    test_getArgBARE = mkGetArgTest(message.BARE_NS, 'mode')
    test_getArgNS = mkGetArgTest(message.OPENID_NS, 'mode', 'error')
    test_getArgNS1 = mkGetArgTest(message.OPENID1_NS, 'mode')
    test_getArgNS2 = mkGetArgTest(message.OPENID2_NS, 'mode', 'error')
    test_getArgNS3 = mkGetArgTest('urn:nothing-significant', 'mode')

    def test_getArgsOpenID(self):
        self.failUnlessEqual(self.msg.getArgs(message.OPENID_NS),
                             {'mode':'error',
                              'error':'unit test',
                              })

    def test_getArgsBARE(self):
        self.failUnlessEqual(self.msg.getArgs(message.BARE_NS),
                             {'xey': 'value'})

    def test_getArgsNS1(self):
        self.failUnlessEqual(self.msg.getArgs(message.OPENID1_NS), {})

    def test_getArgsNS2(self):
        self.failUnlessEqual(self.msg.getArgs(message.OPENID2_NS),
                             {'mode':'error',
                              'error':'unit test',
                              })

    def test_getArgsNS3(self):
        self.failUnlessEqual(self.msg.getArgs('urn:nothing-significant'), {})

    def _test_updateArgsNS(self, ns, before=None):
        if before is None:
            before = {}
        update_args = {
            'Camper van Beethoven':'David Lowery',
            'Magnolia Electric Co.':'Jason Molina',
            }

        self.failUnlessEqual(self.msg.getArgs(ns), before)
        self.msg.updateArgs(ns, update_args)
        after = dict(before)
        after.update(update_args)
        self.failUnlessEqual(self.msg.getArgs(ns), after)

    def test_updateArgsOpenID(self):
        self._test_updateArgsNS(message.OPENID_NS,
                                before={'mode':'error', 'error':'unit test'})

    def test_updateArgsBARE(self):
        self._test_updateArgsNS(message.BARE_NS,
                                before={'xey':'value'})

    def test_updateArgsNS1(self):
        self._test_updateArgsNS(message.OPENID1_NS)

    def test_updateArgsNS2(self):
        self._test_updateArgsNS(message.OPENID2_NS,
                                before={'mode':'error', 'error':'unit test'})

    def test_updateArgsNS3(self):
        self._test_updateArgsNS('urn:nothing-significant')

    def _test_setArgNS(self, ns):
        key = 'Camper van Beethoven'
        value = 'David Lowery'
        self.failUnlessEqual(self.msg.getArg(ns, key), None)
        self.msg.setArg(ns, key, value)
        self.failUnlessEqual(self.msg.getArg(ns, key), value)

    def test_setArgOpenID(self):
        self._test_setArgNS(message.OPENID_NS)

    def test_setArgBARE(self):
        self._test_setArgNS(message.BARE_NS)

    def test_setArgNS1(self):
        self._test_setArgNS(message.OPENID1_NS)

    def test_setArgNS2(self):
        self._test_setArgNS(message.OPENID2_NS)

    def test_setArgNS3(self):
        self._test_setArgNS('urn:nothing-significant')

    def test_badAlias(self):
        """Make sure dotted aliases and OpenID protocol fields are not
        allowed as namespace aliases."""

        for f in message.OPENID_PROTOCOL_FIELDS + ['dotted.alias']:
            args = {'openid.ns.%s' % f: 'blah',
                    'openid.%s.foo' % f: 'test'}

            # .fromPostArgs covers .fromPostArgs, .fromOpenIDArgs,
            # ._fromOpenIDArgs, and .fromOpenIDArgs (since it calls
            # .fromPostArgs).
            self.failUnlessRaises(AssertionError, self.msg.fromPostArgs,
                                  args)

    def test_mysterious_missing_namespace_bug(self):
        """A failing test for bug #112"""
        openid_args = {
          'assoc_handle': '{{HMAC-SHA256}{1211477242.29743}{v5cadg==}',
          'claimed_id': 'http://nerdbank.org/OPAffirmative/AffirmativeIdentityWithSregNoAssoc.aspx', 
          'ns.sreg': 'http://openid.net/extensions/sreg/1.1', 
          'response_nonce': '2008-05-22T17:27:22ZUoW5.\\NV', 
          'signed': 'return_to,identity,claimed_id,op_endpoint,response_nonce,ns.sreg,sreg.email,sreg.nickname,assoc_handle',
          'sig': 'e3eGZ10+TNRZitgq5kQlk5KmTKzFaCRI8OrRoXyoFa4=', 
          'mode': 'check_authentication', 
          'op_endpoint': 'http://nerdbank.org/OPAffirmative/ProviderNoAssoc.aspx',
          'sreg.nickname': 'Andy',
          'return_to': 'http://localhost.localdomain:8001/process?janrain_nonce=2008-05-22T17%3A27%3A21ZnxHULd', 
          'invalidate_handle': '{{HMAC-SHA1}{1211477241.92242}{H0akXw==}', 
          'identity': 'http://nerdbank.org/OPAffirmative/AffirmativeIdentityWithSregNoAssoc.aspx', 
          'sreg.email': 'a@b.com'
          }
        m = message.Message.fromOpenIDArgs(openid_args)

        self.failUnless(('http://openid.net/extensions/sreg/1.1', 'sreg') in
                        list(m.namespaces.iteritems()))
        missing = []
        for k in openid_args['signed'].split(','):
            if not ("openid."+k) in m.toPostArgs().keys():
                missing.append(k)
        self.assertEqual([], missing, missing)
        self.assertEqual(openid_args, m.toArgs())
        self.failUnless(m.isOpenID1())

    def test_112B(self):
        args = {'openid.assoc_handle': 'fa1f5ff0-cde4-11dc-a183-3714bfd55ca8',
                'openid.claimed_id': 'http://binkley.lan/user/test01',
                'openid.identity': 'http://test01.binkley.lan/',
                'openid.mode': 'id_res',
                'openid.ns': 'http://specs.openid.net/auth/2.0',
                'openid.ns.pape': 'http://specs.openid.net/extensions/pape/1.0',
                'openid.op_endpoint': 'http://binkley.lan/server',
                'openid.pape.auth_policies': 'none',
                'openid.pape.auth_time': '2008-01-28T20:42:36Z',
                'openid.pape.nist_auth_level': '0',
                'openid.response_nonce': '2008-01-28T21:07:04Z99Q=',
                'openid.return_to': 'http://binkley.lan:8001/process?janrain_nonce=2008-01-28T21%3A07%3A02Z0tMIKx',
                'openid.sig': 'YJlWH4U6SroB1HoPkmEKx9AyGGg=',
                'openid.signed': 'assoc_handle,identity,response_nonce,return_to,claimed_id,op_endpoint,pape.auth_time,ns.pape,pape.nist_auth_level,pape.auth_policies'
                }
        m = message.Message.fromPostArgs(args)
        missing = []
        for k in args['openid.signed'].split(','):
            if not ("openid."+k) in m.toPostArgs().keys():
                missing.append(k)
        self.assertEqual([], missing, missing)
        self.assertEqual(args, m.toPostArgs())
        self.failUnless(m.isOpenID2())

    def test_implicit_sreg_ns(self):
        openid_args = {
          'sreg.email': 'a@b.com'
          }
        m = message.Message.fromOpenIDArgs(openid_args)
        self.failUnless((sreg.ns_uri, 'sreg') in
                        list(m.namespaces.iteritems()))
        self.assertEqual('a@b.com', m.getArg(sreg.ns_uri, 'email'))
        self.assertEqual(openid_args, m.toArgs())
        self.failUnless(m.isOpenID1())

    def _test_delArgNS(self, ns):
        key = 'Camper van Beethoven'
        value = 'David Lowery'

        self.failUnlessRaises(KeyError, self.msg.delArg, ns, key)
        self.msg.setArg(ns, key, value)
        self.failUnlessEqual(self.msg.getArg(ns, key), value)
        self.msg.delArg(ns, key)
        self.failUnlessEqual(self.msg.getArg(ns, key), None)

    def test_delArgOpenID(self):
        self._test_delArgNS(message.OPENID_NS)

    def test_delArgBARE(self):
        self._test_delArgNS(message.BARE_NS)

    def test_delArgNS1(self):
        self._test_delArgNS(message.OPENID1_NS)

    def test_delArgNS2(self):
        self._test_delArgNS(message.OPENID2_NS)

    def test_delArgNS3(self):
        self._test_delArgNS('urn:nothing-significant')

    def test_overwriteExtensionArg(self):
        ns = 'urn:unittest_extension'
        key = 'mykey'
        value_1 = 'value_1'
        value_2 = 'value_2'

        self.msg.setArg(ns, key, value_1)
        self.failUnless(self.msg.getArg(ns, key) == value_1)
        self.msg.setArg(ns, key, value_2)
        self.failUnless(self.msg.getArg(ns, key) == value_2)

    def test_argList(self):
        self.failUnlessRaises(TypeError, self.msg.fromPostArgs,
                              {'arg': [1, 2, 3]})

    def test_isOpenID1(self):
        self.failIf(self.msg.isOpenID1())

    def test_isOpenID2(self):
        self.failUnless(self.msg.isOpenID2())

class MessageTest(unittest.TestCase):
    def setUp(self):
        self.postargs = {
            'openid.ns': message.OPENID2_NS,
            'openid.mode': 'checkid_setup',
            'openid.identity': 'http://bogus.example.invalid:port/',
            'openid.assoc_handle': 'FLUB',
            'openid.return_to': 'Neverland',
            }

        self.action_url = 'scheme://host:port/path?query'

        self.form_tag_attrs = {
            'company': 'janrain',
            'class': 'fancyCSS',
            }

        self.submit_text = 'GO!'

        ### Expected data regardless of input

        self.required_form_attrs = {
            'accept-charset':'UTF-8',
            'enctype':'application/x-www-form-urlencoded',
            'method': 'post',
            }

    def _checkForm(self, html, message_, action_url,
                   form_tag_attrs, submit_text):
        E = oidutil.importElementTree()

        # Build element tree from HTML source
        input_tree = E.ElementTree(E.fromstring(html))

        # Get root element
        form = input_tree.getroot()

        # Check required form attributes
        for k, v in self.required_form_attrs.iteritems():
            assert form.attrib[k] == v, \
                   "Expected '%s' for required form attribute '%s', got '%s'" % \
                   (v, k, form.attrib[k])

        # Check extra form attributes
        for k, v in form_tag_attrs.iteritems():

            # Skip attributes that already passed the required
            # attribute check, since they should be ignored by the
            # form generation code.
            if k in self.required_form_attrs:
                continue

            assert form.attrib[k] == v, \
                   "Form attribute '%s' should be '%s', found '%s'" % \
                   (k, v, form.attrib[k])

        # Check hidden fields against post args
        hiddens = [e for e in form \
                   if e.tag.upper() == 'INPUT' and \
                   e.attrib['type'].upper() == 'HIDDEN']

        # For each post arg, make sure there is a hidden with that
        # value.  Make sure there are no other hiddens.
        for name, value in message_.toPostArgs().iteritems():
            for e in hiddens:
                if e.attrib['name'] == name:
                    assert e.attrib['value'] == value, \
                           "Expected value of hidden input '%s' to be '%s', got '%s'" % \
                           (e.attrib['name'], value, e.attrib['value'])
                    break
            else:
                self.fail("Post arg '%s' not found in form" % (name,))

        for e in hiddens:
            assert e.attrib['name'] in message_.toPostArgs().keys(), \
                   "Form element for '%s' not in " + \
                   "original message" % (e.attrib['name'])

        # Check action URL
        assert form.attrib['action'] == action_url, \
               "Expected form 'action' to be '%s', got '%s'" % \
               (action_url, form.attrib['action'])

        # Check submit text
        submits = [e for e in form \
                   if e.tag.upper() == 'INPUT' and \
                   e.attrib['type'].upper() == 'SUBMIT']

        assert len(submits) == 1, \
               "Expected only one 'input' with type = 'submit', got %d" % \
               (len(submits),)

        assert submits[0].attrib['value'] == submit_text, \
               "Expected submit value to be '%s', got '%s'" % \
               (submit_text, submits[0].attrib['value'])

    def test_toFormMarkup(self):
        m = message.Message.fromPostArgs(self.postargs)
        html = m.toFormMarkup(self.action_url, self.form_tag_attrs,
                              self.submit_text)
        self._checkForm(html, m, self.action_url,
                        self.form_tag_attrs, self.submit_text)

    def test_toFormMarkup_bug_with_utf8_values(self):
        postargs = {
            'openid.ns': message.OPENID2_NS,
            'openid.mode': 'checkid_setup',
            'openid.identity': 'http://bogus.example.invalid:port/',
            'openid.assoc_handle': 'FLUB',
            'openid.return_to': 'Neverland',
            'ünicöde_key' : 'ünicöde_välüe',
            }
        m = message.Message.fromPostArgs(postargs)
        # Calling m.toFormMarkup with lxml used for ElementTree will throw
        # a ValueError.
        html = m.toFormMarkup(self.action_url, self.form_tag_attrs,
                              self.submit_text)
        # Using the (c)ElementTree from stdlib will result in the UTF-8
        # encoded strings to be converted to XML character references,
        # "ünicöde_key" becomes "&#195;&#188;nic&#195;&#182;de_key" and
        # "ünicöde_välüe" becomes "&#195;&#188;nic&#195;&#182;de_v&#195;&#164;l&#195;&#188;e"
        self.failIf('&#195;&#188;nic&#195;&#182;de_key' in html,
                    'UTF-8 bytes should not convert to XML character references')
        self.failIf('&#195;&#188;nic&#195;&#182;de_v&#195;&#164;l&#195;&#188;e' in html,
                    'UTF-8 bytes should not convert to XML character references')

    def test_overrideMethod(self):
        """Be sure that caller cannot change form method to GET."""
        m = message.Message.fromPostArgs(self.postargs)

        tag_attrs = dict(self.form_tag_attrs)
        tag_attrs['method'] = 'GET'

        html = m.toFormMarkup(self.action_url, self.form_tag_attrs,
                              self.submit_text)
        self._checkForm(html, m, self.action_url,
                        self.form_tag_attrs, self.submit_text)

    def test_overrideRequired(self):
        """Be sure that caller CANNOT change the form charset for
        encoding type."""
        m = message.Message.fromPostArgs(self.postargs)

        tag_attrs = dict(self.form_tag_attrs)
        tag_attrs['accept-charset'] = 'UCS4'
        tag_attrs['enctype'] = 'invalid/x-broken'

        html = m.toFormMarkup(self.action_url, tag_attrs,
                              self.submit_text)
        self._checkForm(html, m, self.action_url,
                        tag_attrs, self.submit_text)


    def test_setOpenIDNamespace_invalid(self):
        m = message.Message()
        invalid_things = [
            # Empty string is not okay here.
            '',
            # Good guess!  But wrong.
            'http://openid.net/signon/2.0',
            # What?
            u'http://specs%\\\r2Eopenid.net/auth/2.0',
            # Too much escapings!
            'http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0',
            # This is a Type URI, not a openid.ns value.
            'http://specs.openid.net/auth/2.0/signon',
            ]

        for x in invalid_things:
            self.failUnlessRaises(message.InvalidOpenIDNamespace,
                                  m.setOpenIDNamespace, x, False)


    def test_isOpenID1(self):
        v1_namespaces = [
            # Yes, there are two of them.
            'http://openid.net/signon/1.1',
            'http://openid.net/signon/1.0',
            ]

        for ns in v1_namespaces:
            m = message.Message(ns)
            self.failUnless(m.isOpenID1(), "%r not recognized as OpenID 1" %
                            (ns,))
            self.failUnlessEqual(ns, m.getOpenIDNamespace())
            self.failUnless(m.namespaces.isImplicit(ns),
                            m.namespaces.getNamespaceURI(message.NULL_NAMESPACE))

    def test_isOpenID2(self):
        ns = 'http://specs.openid.net/auth/2.0'
        m = message.Message(ns)
        self.failUnless(m.isOpenID2())
        self.failIf(m.namespaces.isImplicit(message.NULL_NAMESPACE))
        self.failUnlessEqual(ns, m.getOpenIDNamespace())

    def test_setOpenIDNamespace_explicit(self):
        m = message.Message()
        m.setOpenIDNamespace(message.THE_OTHER_OPENID1_NS, False)
        self.failIf(m.namespaces.isImplicit(message.THE_OTHER_OPENID1_NS))

    def test_setOpenIDNamespace_implicit(self):
        m = message.Message()
        m.setOpenIDNamespace(message.THE_OTHER_OPENID1_NS, True)
        self.failUnless(m.namespaces.isImplicit(message.THE_OTHER_OPENID1_NS))


    def test_explicitOpenID11NSSerialzation(self):
        m = message.Message()
        m.setOpenIDNamespace(message.THE_OTHER_OPENID1_NS, implicit=False)

        post_args = m.toPostArgs()
        self.failUnlessEqual(post_args,
                             {'openid.ns':message.THE_OTHER_OPENID1_NS})

    def test_fromPostArgs_ns11(self):
        # An example of the stuff that some Drupal installations send us,
        # which includes openid.ns but is 1.1.
        query = {
            u'openid.assoc_handle': u'',
            u'openid.claimed_id': u'http://foobar.invalid/',
            u'openid.identity': u'http://foobar.myopenid.com',
            u'openid.mode': u'checkid_setup',
            u'openid.ns': u'http://openid.net/signon/1.1',
            u'openid.ns.sreg': u'http://openid.net/extensions/sreg/1.1',
            u'openid.return_to': u'http://drupal.invalid/return_to',
            u'openid.sreg.required': u'nickname,email',
            u'openid.trust_root': u'http://drupal.invalid',
            }
        m = message.Message.fromPostArgs(query)
        self.failUnless(m.isOpenID1())



class NamespaceMapTest(unittest.TestCase):
    def test_onealias(self):
        nsm = message.NamespaceMap()
        uri = 'http://example.com/foo'
        alias = "foo"
        nsm.addAlias(uri, alias)
        self.failUnless(nsm.getNamespaceURI(alias) == uri)
        self.failUnless(nsm.getAlias(uri) == alias)

    def test_iteration(self):
        nsm = message.NamespaceMap()
        uripat = 'http://example.com/foo%r'

        nsm.add(uripat%0)
        for n in range(1,23):
            self.failUnless(uripat%(n-1) in nsm)
            self.failUnless(nsm.isDefined(uripat%(n-1)))
            nsm.add(uripat%n)

        for (uri, alias) in nsm.iteritems():
            self.failUnless(uri[22:]==alias[3:])

        i=0
        it = nsm.iterAliases()
        try:
            while True:
                it.next()
                i += 1
        except StopIteration:
            self.failUnless(i == 23)

        i=0
        it = nsm.iterNamespaceURIs()
        try:
            while True:
                it.next()
                i += 1
        except StopIteration:
            self.failUnless(i == 23)


if __name__ == '__main__':
    unittest.main()

########NEW FILE########
__FILENAME__ = test_negotiation

import unittest
from support import CatchLogs

from openid.message import Message, OPENID2_NS, OPENID1_NS, OPENID_NS
from openid import association
from openid.consumer.consumer import GenericConsumer, ServerError
from openid.consumer.discover import OpenIDServiceEndpoint, OPENID_2_0_TYPE

class ErrorRaisingConsumer(GenericConsumer):
    """
    A consumer whose _requestAssocation will return predefined results
    instead of trying to actually perform association requests.
    """

    # The list of objects to be returned by successive calls to
    # _requestAssocation.  Each call will pop the first element from
    # this list and return it to _negotiateAssociation.  If the
    # element is a Message object, it will be wrapped in a ServerError
    # exception.  Otherwise it will be returned as-is.
    return_messages = []

    def _requestAssociation(self, endpoint, assoc_type, session_type):
        m = self.return_messages.pop(0)
        if isinstance(m, Message):
            raise ServerError.fromMessage(m)
        else:
            return m

class TestOpenID2SessionNegotiation(unittest.TestCase, CatchLogs):
    """
    Test the session type negotiation behavior of an OpenID 2
    consumer.
    """
    def setUp(self):
        CatchLogs.setUp(self)
        self.consumer = ErrorRaisingConsumer(store=None)

        self.endpoint = OpenIDServiceEndpoint()
        self.endpoint.type_uris = [OPENID_2_0_TYPE]
        self.endpoint.server_url = 'bogus'

    def testBadResponse(self):
        """
        Test the case where the response to an associate request is a
        server error or is otherwise undecipherable.
        """
        self.consumer.return_messages = [Message(self.endpoint.preferredNamespace())]
        self.assertEqual(self.consumer._negotiateAssociation(self.endpoint), None)
        self.failUnlessLogMatches('Server error when requesting an association')

    def testEmptyAssocType(self):
        """
        Test the case where the association type (assoc_type) returned
        in an unsupported-type response is absent.
        """
        msg = Message(self.endpoint.preferredNamespace())
        msg.setArg(OPENID_NS, 'error', 'Unsupported type')
        msg.setArg(OPENID_NS, 'error_code', 'unsupported-type')
        # not set: msg.delArg(OPENID_NS, 'assoc_type')
        msg.setArg(OPENID_NS, 'session_type', 'new-session-type')

        self.consumer.return_messages = [msg]
        self.assertEqual(self.consumer._negotiateAssociation(self.endpoint), None)

        self.failUnlessLogMatches('Unsupported association type',
                                  'Server responded with unsupported association ' +
                                  'session but did not supply a fallback.')

    def testEmptySessionType(self):
        """
        Test the case where the session type (session_type) returned
        in an unsupported-type response is absent.
        """
        msg = Message(self.endpoint.preferredNamespace())
        msg.setArg(OPENID_NS, 'error', 'Unsupported type')
        msg.setArg(OPENID_NS, 'error_code', 'unsupported-type')
        msg.setArg(OPENID_NS, 'assoc_type', 'new-assoc-type')
        # not set: msg.setArg(OPENID_NS, 'session_type', None)

        self.consumer.return_messages = [msg]
        self.assertEqual(self.consumer._negotiateAssociation(self.endpoint), None)

        self.failUnlessLogMatches('Unsupported association type',
                                  'Server responded with unsupported association ' +
                                  'session but did not supply a fallback.')

    def testNotAllowed(self):
        """
        Test the case where an unsupported-type response specifies a
        preferred (assoc_type, session_type) combination that is not
        allowed by the consumer's SessionNegotiator.
        """
        allowed_types = []

        negotiator = association.SessionNegotiator(allowed_types)
        self.consumer.negotiator = negotiator

        msg = Message(self.endpoint.preferredNamespace())
        msg.setArg(OPENID_NS, 'error', 'Unsupported type')
        msg.setArg(OPENID_NS, 'error_code', 'unsupported-type')
        msg.setArg(OPENID_NS, 'assoc_type', 'not-allowed')
        msg.setArg(OPENID_NS, 'session_type', 'not-allowed')

        self.consumer.return_messages = [msg]
        self.assertEqual(self.consumer._negotiateAssociation(self.endpoint), None)

        self.failUnlessLogMatches('Unsupported association type',
                                  'Server sent unsupported session/association type:')

    def testUnsupportedWithRetry(self):
        """
        Test the case where an unsupported-type response triggers a
        retry to get an association with the new preferred type.
        """
        msg = Message(self.endpoint.preferredNamespace())
        msg.setArg(OPENID_NS, 'error', 'Unsupported type')
        msg.setArg(OPENID_NS, 'error_code', 'unsupported-type')
        msg.setArg(OPENID_NS, 'assoc_type', 'HMAC-SHA1')
        msg.setArg(OPENID_NS, 'session_type', 'DH-SHA1')

        assoc = association.Association(
            'handle', 'secret', 'issued', 10000, 'HMAC-SHA1')

        self.consumer.return_messages = [msg, assoc]
        self.failUnless(self.consumer._negotiateAssociation(self.endpoint) is assoc)

        self.failUnlessLogMatches('Unsupported association type')

    def testUnsupportedWithRetryAndFail(self):
        """
        Test the case where an unsupported-typ response triggers a
        retry, but the retry fails and None is returned instead.
        """
        msg = Message(self.endpoint.preferredNamespace())
        msg.setArg(OPENID_NS, 'error', 'Unsupported type')
        msg.setArg(OPENID_NS, 'error_code', 'unsupported-type')
        msg.setArg(OPENID_NS, 'assoc_type', 'HMAC-SHA1')
        msg.setArg(OPENID_NS, 'session_type', 'DH-SHA1')

        self.consumer.return_messages = [msg,
             Message(self.endpoint.preferredNamespace())]

        self.failUnlessEqual(self.consumer._negotiateAssociation(self.endpoint), None)

        self.failUnlessLogMatches('Unsupported association type',
                                  'Server %s refused' % (self.endpoint.server_url))

    def testValid(self):
        """
        Test the valid case, wherein an association is returned on the
        first attempt to get one.
        """
        assoc = association.Association(
            'handle', 'secret', 'issued', 10000, 'HMAC-SHA1')

        self.consumer.return_messages = [assoc]
        self.failUnless(self.consumer._negotiateAssociation(self.endpoint) is assoc)
        self.failUnlessLogEmpty()

class TestOpenID1SessionNegotiation(unittest.TestCase, CatchLogs):
    """
    Tests for the OpenID 1 consumer association session behavior.  See
    the docs for TestOpenID2SessionNegotiation.  Notice that this
    class is not a subclass of the OpenID 2 tests.  Instead, it uses
    many of the same inputs but inspects the log messages.
    See the calls to self.failUnlessLogMatches.  Some of
    these tests pass openid2-style messages to the openid 1
    association processing logic to be sure it ignores the extra data.
    """
    def setUp(self):
        CatchLogs.setUp(self)
        self.consumer = ErrorRaisingConsumer(store=None)

        self.endpoint = OpenIDServiceEndpoint()
        self.endpoint.type_uris = [OPENID1_NS]
        self.endpoint.server_url = 'bogus'

    def testBadResponse(self):
        self.consumer.return_messages = [Message(self.endpoint.preferredNamespace())]
        self.assertEqual(self.consumer._negotiateAssociation(self.endpoint), None)
        self.failUnlessLogMatches('Server error when requesting an association')

    def testEmptyAssocType(self):
        msg = Message(self.endpoint.preferredNamespace())
        msg.setArg(OPENID_NS, 'error', 'Unsupported type')
        msg.setArg(OPENID_NS, 'error_code', 'unsupported-type')
        # not set: msg.setArg(OPENID_NS, 'assoc_type', None)
        msg.setArg(OPENID_NS, 'session_type', 'new-session-type')

        self.consumer.return_messages = [msg]
        self.assertEqual(self.consumer._negotiateAssociation(self.endpoint), None)

        self.failUnlessLogMatches('Server error when requesting an association')

    def testEmptySessionType(self):
        msg = Message(self.endpoint.preferredNamespace())
        msg.setArg(OPENID_NS, 'error', 'Unsupported type')
        msg.setArg(OPENID_NS, 'error_code', 'unsupported-type')
        msg.setArg(OPENID_NS, 'assoc_type', 'new-assoc-type')
        # not set: msg.setArg(OPENID_NS, 'session_type', None)

        self.consumer.return_messages = [msg]
        self.assertEqual(self.consumer._negotiateAssociation(self.endpoint), None)

        self.failUnlessLogMatches('Server error when requesting an association')

    def testNotAllowed(self):
        allowed_types = []

        negotiator = association.SessionNegotiator(allowed_types)
        self.consumer.negotiator = negotiator

        msg = Message(self.endpoint.preferredNamespace())
        msg.setArg(OPENID_NS, 'error', 'Unsupported type')
        msg.setArg(OPENID_NS, 'error_code', 'unsupported-type')
        msg.setArg(OPENID_NS, 'assoc_type', 'not-allowed')
        msg.setArg(OPENID_NS, 'session_type', 'not-allowed')

        self.consumer.return_messages = [msg]
        self.assertEqual(self.consumer._negotiateAssociation(self.endpoint), None)

        self.failUnlessLogMatches('Server error when requesting an association')

    def testUnsupportedWithRetry(self):
        msg = Message(self.endpoint.preferredNamespace())
        msg.setArg(OPENID_NS, 'error', 'Unsupported type')
        msg.setArg(OPENID_NS, 'error_code', 'unsupported-type')
        msg.setArg(OPENID_NS, 'assoc_type', 'HMAC-SHA1')
        msg.setArg(OPENID_NS, 'session_type', 'DH-SHA1')

        assoc = association.Association(
            'handle', 'secret', 'issued', 10000, 'HMAC-SHA1')

        self.consumer.return_messages = [msg, assoc]
        self.failUnless(self.consumer._negotiateAssociation(self.endpoint) is None)

        self.failUnlessLogMatches('Server error when requesting an association')

    def testValid(self):
        assoc = association.Association(
            'handle', 'secret', 'issued', 10000, 'HMAC-SHA1')

        self.consumer.return_messages = [assoc]
        self.failUnless(self.consumer._negotiateAssociation(self.endpoint) is assoc)
        self.failUnlessLogEmpty()

class TestNegotiatorBehaviors(unittest.TestCase, CatchLogs):
    def setUp(self):
        self.allowed_types = [
            ('HMAC-SHA1', 'no-encryption'),
            ('HMAC-SHA256', 'no-encryption'),
            ]

        self.n = association.SessionNegotiator(self.allowed_types)

    def testAddAllowedTypeNoSessionTypes(self):
        self.assertRaises(ValueError, self.n.addAllowedType, 'invalid')

    def testAddAllowedTypeBadSessionType(self):
        self.assertRaises(ValueError, self.n.addAllowedType, 'assoc1', 'invalid')

    def testAddAllowedTypeContents(self):
        assoc_type = 'HMAC-SHA1'
        self.failUnless(self.n.addAllowedType(assoc_type) is None)

        for typ in association.getSessionTypes(assoc_type):
            self.failUnless((assoc_type, typ) in self.n.allowed_types)

if __name__ == '__main__':
    unittest.main()

########NEW FILE########
__FILENAME__ = test_nonce
from openid.test import datadriven
import time
import unittest
import re

from openid.store.nonce import \
     mkNonce, \
     split as splitNonce, \
     checkTimestamp

nonce_re = re.compile(r'\A\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ')

class NonceTest(unittest.TestCase):
    def test_mkNonce(self):
        nonce = mkNonce()
        self.failUnless(nonce_re.match(nonce))
        self.failUnless(len(nonce) == 26)

    def test_mkNonce_when(self):
        nonce = mkNonce(0)
        self.failUnless(nonce_re.match(nonce))
        self.failUnless(nonce.startswith('1970-01-01T00:00:00Z'))
        self.failUnless(len(nonce) == 26)

    def test_splitNonce(self):
        s = '1970-01-01T00:00:00Z'
        expected_t = 0
        expected_salt = ''
        actual_t, actual_salt = splitNonce(s)
        self.failUnlessEqual(expected_t, actual_t)
        self.failUnlessEqual(expected_salt, actual_salt)

    def test_mkSplit(self):
        t = 42
        nonce_str = mkNonce(t)
        self.failUnless(nonce_re.match(nonce_str))
        et, salt = splitNonce(nonce_str)
        self.failUnlessEqual(len(salt), 6)
        self.failUnlessEqual(et, t)

class BadSplitTest(datadriven.DataDrivenTestCase):
    cases = [
        '',
        '1970-01-01T00:00:00+1:00',
        '1969-01-01T00:00:00Z',
        '1970-00-01T00:00:00Z',
        '1970.01-01T00:00:00Z',
        'Thu Sep  7 13:29:31 PDT 2006',
        'monkeys',
        ]

    def __init__(self, nonce_str):
        datadriven.DataDrivenTestCase.__init__(self, nonce_str)
        self.nonce_str = nonce_str

    def runOneTest(self):
        self.failUnlessRaises(ValueError, splitNonce, self.nonce_str)

class CheckTimestampTest(datadriven.DataDrivenTestCase):
    cases = [
        # exact, no allowed skew
        ('1970-01-01T00:00:00Z', 0, 0, True),

        # exact, large skew
        ('1970-01-01T00:00:00Z', 1000, 0, True),

        # no allowed skew, one second old
        ('1970-01-01T00:00:00Z', 0, 1, False),

        # many seconds old, outside of skew
        ('1970-01-01T00:00:00Z', 10, 50, False),

        # one second old, one second skew allowed
        ('1970-01-01T00:00:00Z', 1, 1, True),

        # One second in the future, one second skew allowed
        ('1970-01-01T00:00:02Z', 1, 1, True),

        # two seconds in the future, one second skew allowed
        ('1970-01-01T00:00:02Z', 1, 0, False),

        # malformed nonce string
        ('monkeys', 0, 0, False),
        ]

    def __init__(self, nonce_string, allowed_skew, now, expected):
        datadriven.DataDrivenTestCase.__init__(
            self, repr((nonce_string, allowed_skew, now)))
        self.nonce_string = nonce_string
        self.allowed_skew = allowed_skew
        self.now = now
        self.expected = expected

    def runOneTest(self):
        actual = checkTimestamp(self.nonce_string, self.allowed_skew, self.now)
        self.failUnlessEqual(bool(self.expected), bool(actual))

def pyUnitTests():
    return datadriven.loadTests(__name__)

if __name__ == '__main__':
    suite = pyUnitTests()
    runner = unittest.TextTestRunner()
    runner.run(suite)

########NEW FILE########
__FILENAME__ = test_openidyadis
import unittest
from openid.consumer.discover import \
     OpenIDServiceEndpoint, OPENID_1_1_TYPE, OPENID_1_0_TYPE

from openid.yadis.services import applyFilter


XRDS_BOILERPLATE = '''\
<?xml version="1.0" encoding="UTF-8"?>
<xrds:XRDS xmlns:xrds="xri://$xrds"
           xmlns="xri://$xrd*($v*2.0)"
           xmlns:openid="http://openid.net/xmlns/1.0">
    <XRD>
%s\
    </XRD>
</xrds:XRDS>
'''

def mkXRDS(services):
    return XRDS_BOILERPLATE % (services,)

def mkService(uris=None, type_uris=None, local_id=None, dent='        '):
    chunks = [dent, '<Service>\n']
    dent2 = dent + '    '
    if type_uris:
        for type_uri in type_uris:
            chunks.extend([dent2 + '<Type>', type_uri, '</Type>\n'])

    if uris:
        for uri in uris:
            if type(uri) is tuple:
                uri, prio = uri
            else:
                prio = None

            chunks.extend([dent2, '<URI'])
            if prio is not None:
                chunks.extend([' priority="', str(prio), '"'])
            chunks.extend(['>', uri, '</URI>\n'])

    if local_id:
        chunks.extend(
            [dent2, '<openid:Delegate>', local_id, '</openid:Delegate>\n'])

    chunks.extend([dent, '</Service>\n'])

    return ''.join(chunks)

# Different sets of server URLs for use in the URI tag
server_url_options = [
    [], # This case should not generate an endpoint object
    ['http://server.url/'],
    ['https://server.url/'],
    ['https://server.url/', 'http://server.url/'],
    ['https://server.url/',
     'http://server.url/',
     'http://example.server.url/'],
    ]

# Used for generating test data
def subsets(l):
    """Generate all non-empty sublists of a list"""
    subsets_list = [[]]
    for x in l:
        subsets_list += [[x] + t for t in subsets_list]
    return subsets_list

# A couple of example extension type URIs. These are not at all
# official, but are just here for testing.
ext_types = [
    'http://janrain.com/extension/blah',
    'http://openid.net/sreg/1.0',
    ]

# All valid combinations of Type tags that should produce an OpenID endpoint
type_uri_options = [
    exts + ts

    # All non-empty sublists of the valid OpenID type URIs
    for ts in subsets([OPENID_1_0_TYPE, OPENID_1_1_TYPE])
    if ts

    # All combinations of extension types (including empty extenstion list)
    for exts in subsets(ext_types)
    ]

# Range of valid Delegate tag values for generating test data
local_id_options = [
    None,
    'http://vanity.domain/',
    'https://somewhere/yadis/',
    ]

# All combinations of valid URIs, Type URIs and Delegate tags
data = [
    (uris, type_uris, local_id)
    for uris in server_url_options
    for type_uris in type_uri_options
    for local_id in local_id_options
    ]

class OpenIDYadisTest(unittest.TestCase):
    def __init__(self, uris, type_uris, local_id):
        unittest.TestCase.__init__(self)
        self.uris = uris
        self.type_uris = type_uris
        self.local_id = local_id

    def shortDescription(self):
        # XXX:
        return 'Successful OpenID Yadis parsing case'

    def setUp(self):
        self.yadis_url = 'http://unit.test/'

        # Create an XRDS document to parse
        services = mkService(uris=self.uris,
                             type_uris=self.type_uris,
                             local_id=self.local_id)
        self.xrds = mkXRDS(services)

    def runTest(self):
        # Parse into endpoint objects that we will check
        endpoints = applyFilter(
            self.yadis_url, self.xrds, OpenIDServiceEndpoint)

        # make sure there are the same number of endpoints as
        # URIs. This assumes that the type_uris contains at least one
        # OpenID type.
        self.failUnlessEqual(len(self.uris), len(endpoints))

        # So that we can check equality on the endpoint types
        type_uris = list(self.type_uris)
        type_uris.sort()

        seen_uris = []
        for endpoint in endpoints:
            seen_uris.append(endpoint.server_url)

            # All endpoints will have same yadis_url
            self.failUnlessEqual(self.yadis_url, endpoint.claimed_id)

            # and local_id
            self.failUnlessEqual(self.local_id, endpoint.local_id)

            # and types
            actual_types = list(endpoint.type_uris)
            actual_types.sort()
            self.failUnlessEqual(actual_types, type_uris)

        # So that they will compare equal, because we don't care what
        # order they are in
        seen_uris.sort()
        uris = list(self.uris)
        uris.sort()

        # Make sure we saw all URIs, and saw each one once
        self.failUnlessEqual(uris, seen_uris)

def pyUnitTests():
    cases = []
    for args in data:
        cases.append(OpenIDYadisTest(*args))
    return unittest.TestSuite(cases)

########NEW FILE########
__FILENAME__ = test_pape

from openid.extensions import pape

import unittest

class PapeImportTestCase(unittest.TestCase):
    def test_version(self):
        from openid.extensions.draft import pape5
        self.assert_(pape is pape5)

########NEW FILE########
__FILENAME__ = test_pape_draft2

from openid.extensions.draft import pape2 as pape
from openid.message import *
from openid.server import server

import unittest

class PapeRequestTestCase(unittest.TestCase):
    def setUp(self):
        self.req = pape.Request()

    def test_construct(self):
        self.failUnlessEqual([], self.req.preferred_auth_policies)
        self.failUnlessEqual(None, self.req.max_auth_age)
        self.failUnlessEqual('pape', self.req.ns_alias)

        req2 = pape.Request([pape.AUTH_MULTI_FACTOR], 1000)
        self.failUnlessEqual([pape.AUTH_MULTI_FACTOR], req2.preferred_auth_policies)
        self.failUnlessEqual(1000, req2.max_auth_age)

    def test_add_policy_uri(self):
        self.failUnlessEqual([], self.req.preferred_auth_policies)
        self.req.addPolicyURI(pape.AUTH_MULTI_FACTOR)
        self.failUnlessEqual([pape.AUTH_MULTI_FACTOR], self.req.preferred_auth_policies)
        self.req.addPolicyURI(pape.AUTH_MULTI_FACTOR)
        self.failUnlessEqual([pape.AUTH_MULTI_FACTOR], self.req.preferred_auth_policies)
        self.req.addPolicyURI(pape.AUTH_PHISHING_RESISTANT)
        self.failUnlessEqual([pape.AUTH_MULTI_FACTOR, pape.AUTH_PHISHING_RESISTANT],
                             self.req.preferred_auth_policies)
        self.req.addPolicyURI(pape.AUTH_MULTI_FACTOR)
        self.failUnlessEqual([pape.AUTH_MULTI_FACTOR, pape.AUTH_PHISHING_RESISTANT],
                             self.req.preferred_auth_policies)

    def test_getExtensionArgs(self):
        self.failUnlessEqual({'preferred_auth_policies': ''}, self.req.getExtensionArgs())
        self.req.addPolicyURI('http://uri')
        self.failUnlessEqual({'preferred_auth_policies': 'http://uri'}, self.req.getExtensionArgs())
        self.req.addPolicyURI('http://zig')
        self.failUnlessEqual({'preferred_auth_policies': 'http://uri http://zig'}, self.req.getExtensionArgs())
        self.req.max_auth_age = 789
        self.failUnlessEqual({'preferred_auth_policies': 'http://uri http://zig', 'max_auth_age': '789'}, self.req.getExtensionArgs())

    def test_parseExtensionArgs(self):
        args = {'preferred_auth_policies': 'http://foo http://bar',
                'max_auth_age': '9'}
        self.req.parseExtensionArgs(args)
        self.failUnlessEqual(9, self.req.max_auth_age)
        self.failUnlessEqual(['http://foo','http://bar'], self.req.preferred_auth_policies)

    def test_parseExtensionArgs_empty(self):
        self.req.parseExtensionArgs({})
        self.failUnlessEqual(None, self.req.max_auth_age)
        self.failUnlessEqual([], self.req.preferred_auth_policies)

    def test_fromOpenIDRequest(self):
        openid_req_msg = Message.fromOpenIDArgs({
          'mode': 'checkid_setup',
          'ns': OPENID2_NS,
          'ns.pape': pape.ns_uri,
          'pape.preferred_auth_policies': ' '.join([pape.AUTH_MULTI_FACTOR, pape.AUTH_PHISHING_RESISTANT]),
          'pape.max_auth_age': '5476'
          })
        oid_req = server.OpenIDRequest()
        oid_req.message = openid_req_msg
        req = pape.Request.fromOpenIDRequest(oid_req)
        self.failUnlessEqual([pape.AUTH_MULTI_FACTOR, pape.AUTH_PHISHING_RESISTANT], req.preferred_auth_policies)
        self.failUnlessEqual(5476, req.max_auth_age)

    def test_fromOpenIDRequest_no_pape(self):
        message = Message()
        openid_req = server.OpenIDRequest()
        openid_req.message = message
        pape_req = pape.Request.fromOpenIDRequest(openid_req)
        assert(pape_req is None)

    def test_preferred_types(self):
        self.req.addPolicyURI(pape.AUTH_PHISHING_RESISTANT)
        self.req.addPolicyURI(pape.AUTH_MULTI_FACTOR)
        pt = self.req.preferredTypes([pape.AUTH_MULTI_FACTOR,
                                      pape.AUTH_MULTI_FACTOR_PHYSICAL])
        self.failUnlessEqual([pape.AUTH_MULTI_FACTOR], pt)

class DummySuccessResponse:
    def __init__(self, message, signed_stuff):
        self.message = message
        self.signed_stuff = signed_stuff

    def getSignedNS(self, ns_uri):
        return self.signed_stuff

class PapeResponseTestCase(unittest.TestCase):
    def setUp(self):
        self.req = pape.Response()

    def test_construct(self):
        self.failUnlessEqual([], self.req.auth_policies)
        self.failUnlessEqual(None, self.req.auth_time)
        self.failUnlessEqual('pape', self.req.ns_alias)
        self.failUnlessEqual(None, self.req.nist_auth_level)

        req2 = pape.Response([pape.AUTH_MULTI_FACTOR], "2004-12-11T10:30:44Z", 3)
        self.failUnlessEqual([pape.AUTH_MULTI_FACTOR], req2.auth_policies)
        self.failUnlessEqual("2004-12-11T10:30:44Z", req2.auth_time)
        self.failUnlessEqual(3, req2.nist_auth_level)

    def test_add_policy_uri(self):
        self.failUnlessEqual([], self.req.auth_policies)
        self.req.addPolicyURI(pape.AUTH_MULTI_FACTOR)
        self.failUnlessEqual([pape.AUTH_MULTI_FACTOR], self.req.auth_policies)
        self.req.addPolicyURI(pape.AUTH_MULTI_FACTOR)
        self.failUnlessEqual([pape.AUTH_MULTI_FACTOR], self.req.auth_policies)
        self.req.addPolicyURI(pape.AUTH_PHISHING_RESISTANT)
        self.failUnlessEqual([pape.AUTH_MULTI_FACTOR, pape.AUTH_PHISHING_RESISTANT], self.req.auth_policies)
        self.req.addPolicyURI(pape.AUTH_MULTI_FACTOR)
        self.failUnlessEqual([pape.AUTH_MULTI_FACTOR, pape.AUTH_PHISHING_RESISTANT], self.req.auth_policies)

    def test_getExtensionArgs(self):
        self.failUnlessEqual({'auth_policies': 'none'}, self.req.getExtensionArgs())
        self.req.addPolicyURI('http://uri')
        self.failUnlessEqual({'auth_policies': 'http://uri'}, self.req.getExtensionArgs())
        self.req.addPolicyURI('http://zig')
        self.failUnlessEqual({'auth_policies': 'http://uri http://zig'}, self.req.getExtensionArgs())
        self.req.auth_time = "1776-07-04T14:43:12Z"
        self.failUnlessEqual({'auth_policies': 'http://uri http://zig', 'auth_time': "1776-07-04T14:43:12Z"}, self.req.getExtensionArgs())
        self.req.nist_auth_level = 3
        self.failUnlessEqual({'auth_policies': 'http://uri http://zig', 'auth_time': "1776-07-04T14:43:12Z", 'nist_auth_level': '3'}, self.req.getExtensionArgs())

    def test_getExtensionArgs_error_auth_age(self):
        self.req.auth_time = "long ago"
        self.failUnlessRaises(ValueError, self.req.getExtensionArgs)

    def test_getExtensionArgs_error_nist_auth_level(self):
        self.req.nist_auth_level = "high as a kite"
        self.failUnlessRaises(ValueError, self.req.getExtensionArgs)
        self.req.nist_auth_level = 5
        self.failUnlessRaises(ValueError, self.req.getExtensionArgs)
        self.req.nist_auth_level = -1
        self.failUnlessRaises(ValueError, self.req.getExtensionArgs)

    def test_parseExtensionArgs(self):
        args = {'auth_policies': 'http://foo http://bar',
                'auth_time': '1970-01-01T00:00:00Z'}
        self.req.parseExtensionArgs(args)
        self.failUnlessEqual('1970-01-01T00:00:00Z', self.req.auth_time)
        self.failUnlessEqual(['http://foo','http://bar'], self.req.auth_policies)

    def test_parseExtensionArgs_empty(self):
        self.req.parseExtensionArgs({})
        self.failUnlessEqual(None, self.req.auth_time)
        self.failUnlessEqual([], self.req.auth_policies)
      
    def test_parseExtensionArgs_strict_bogus1(self):
        args = {'auth_policies': 'http://foo http://bar',
                'auth_time': 'yesterday'}
        self.failUnlessRaises(ValueError, self.req.parseExtensionArgs,
                              args, True)

    def test_parseExtensionArgs_strict_bogus2(self):
        args = {'auth_policies': 'http://foo http://bar',
                'auth_time': '1970-01-01T00:00:00Z',
                'nist_auth_level': 'some'}
        self.failUnlessRaises(ValueError, self.req.parseExtensionArgs,
                              args, True)
      
    def test_parseExtensionArgs_strict_good(self):
        args = {'auth_policies': 'http://foo http://bar',
                'auth_time': '1970-01-01T00:00:00Z',
                'nist_auth_level': '0'}
        self.req.parseExtensionArgs(args, True)
        self.failUnlessEqual(['http://foo','http://bar'], self.req.auth_policies)
        self.failUnlessEqual('1970-01-01T00:00:00Z', self.req.auth_time)
        self.failUnlessEqual(0, self.req.nist_auth_level)

    def test_parseExtensionArgs_nostrict_bogus(self):
        args = {'auth_policies': 'http://foo http://bar',
                'auth_time': 'when the cows come home',
                'nist_auth_level': 'some'}
        self.req.parseExtensionArgs(args)
        self.failUnlessEqual(['http://foo','http://bar'], self.req.auth_policies)
        self.failUnlessEqual(None, self.req.auth_time)
        self.failUnlessEqual(None, self.req.nist_auth_level)

    def test_fromSuccessResponse(self):
        openid_req_msg = Message.fromOpenIDArgs({
          'mode': 'id_res',
          'ns': OPENID2_NS,
          'ns.pape': pape.ns_uri,
          'pape.auth_policies': ' '.join([pape.AUTH_MULTI_FACTOR, pape.AUTH_PHISHING_RESISTANT]),
          'pape.auth_time': '1970-01-01T00:00:00Z'
          })
        signed_stuff = {
          'auth_policies': ' '.join([pape.AUTH_MULTI_FACTOR, pape.AUTH_PHISHING_RESISTANT]),
          'auth_time': '1970-01-01T00:00:00Z'
        }
        oid_req = DummySuccessResponse(openid_req_msg, signed_stuff)
        req = pape.Response.fromSuccessResponse(oid_req)
        self.failUnlessEqual([pape.AUTH_MULTI_FACTOR, pape.AUTH_PHISHING_RESISTANT], req.auth_policies)
        self.failUnlessEqual('1970-01-01T00:00:00Z', req.auth_time)

    def test_fromSuccessResponseNoSignedArgs(self):
        openid_req_msg = Message.fromOpenIDArgs({
          'mode': 'id_res',
          'ns': OPENID2_NS,
          'ns.pape': pape.ns_uri,
          'pape.auth_policies': ' '.join([pape.AUTH_MULTI_FACTOR, pape.AUTH_PHISHING_RESISTANT]),
          'pape.auth_time': '1970-01-01T00:00:00Z'
          })

        signed_stuff = {}

        class NoSigningDummyResponse(DummySuccessResponse):
            def getSignedNS(self, ns_uri):
                return None

        oid_req = NoSigningDummyResponse(openid_req_msg, signed_stuff)
        resp = pape.Response.fromSuccessResponse(oid_req)
        self.failUnless(resp is None)

########NEW FILE########
__FILENAME__ = test_pape_draft5

from openid.extensions.draft import pape5 as pape
from openid.message import *
from openid.server import server

import warnings
warnings.filterwarnings('ignore', module=__name__,
                        message='"none" used as a policy URI')

import unittest

class PapeRequestTestCase(unittest.TestCase):
    def setUp(self):
        self.req = pape.Request()

    def test_construct(self):
        self.failUnlessEqual([], self.req.preferred_auth_policies)
        self.failUnlessEqual(None, self.req.max_auth_age)
        self.failUnlessEqual('pape', self.req.ns_alias)
        self.failIf(self.req.preferred_auth_level_types)

        bogus_levels = ['http://janrain.com/our_levels']
        req2 = pape.Request(
            [pape.AUTH_MULTI_FACTOR], 1000, bogus_levels)
        self.failUnlessEqual([pape.AUTH_MULTI_FACTOR],
                             req2.preferred_auth_policies)
        self.failUnlessEqual(1000, req2.max_auth_age)
        self.failUnlessEqual(bogus_levels, req2.preferred_auth_level_types)

    def test_addAuthLevel(self):
        self.req.addAuthLevel('http://example.com/', 'example')
        self.failUnlessEqual(['http://example.com/'],
                             self.req.preferred_auth_level_types)
        self.failUnlessEqual('http://example.com/',
                             self.req.auth_level_aliases['example'])

        self.req.addAuthLevel('http://example.com/1', 'example1')
        self.failUnlessEqual(['http://example.com/', 'http://example.com/1'],
                             self.req.preferred_auth_level_types)

        self.req.addAuthLevel('http://example.com/', 'exmpl')
        self.failUnlessEqual(['http://example.com/', 'http://example.com/1'],
                             self.req.preferred_auth_level_types)

        self.req.addAuthLevel('http://example.com/', 'example')
        self.failUnlessEqual(['http://example.com/', 'http://example.com/1'],
                             self.req.preferred_auth_level_types)

        self.failUnlessRaises(KeyError,
                              self.req.addAuthLevel,
                              'http://example.com/2', 'example')

        # alias is None; we expect a new one to be generated.
        uri = 'http://another.example.com/'
        self.req.addAuthLevel(uri)
        self.assert_(uri in self.req.auth_level_aliases.values())

        # We don't expect a new alias to be generated if one already
        # exists.
        before_aliases = self.req.auth_level_aliases.keys()
        self.req.addAuthLevel(uri)
        after_aliases = self.req.auth_level_aliases.keys()
        self.assertEqual(before_aliases, after_aliases)

    def test_add_policy_uri(self):
        self.failUnlessEqual([], self.req.preferred_auth_policies)
        self.req.addPolicyURI(pape.AUTH_MULTI_FACTOR)
        self.failUnlessEqual([pape.AUTH_MULTI_FACTOR],
                             self.req.preferred_auth_policies)
        self.req.addPolicyURI(pape.AUTH_MULTI_FACTOR)
        self.failUnlessEqual([pape.AUTH_MULTI_FACTOR],
                             self.req.preferred_auth_policies)
        self.req.addPolicyURI(pape.AUTH_PHISHING_RESISTANT)
        self.failUnlessEqual([pape.AUTH_MULTI_FACTOR,
                              pape.AUTH_PHISHING_RESISTANT],
                             self.req.preferred_auth_policies)
        self.req.addPolicyURI(pape.AUTH_MULTI_FACTOR)
        self.failUnlessEqual([pape.AUTH_MULTI_FACTOR,
                              pape.AUTH_PHISHING_RESISTANT],
                             self.req.preferred_auth_policies)

    def test_getExtensionArgs(self):
        self.failUnlessEqual({'preferred_auth_policies': ''},
                             self.req.getExtensionArgs())
        self.req.addPolicyURI('http://uri')
        self.failUnlessEqual(
            {'preferred_auth_policies': 'http://uri'},
            self.req.getExtensionArgs())
        self.req.addPolicyURI('http://zig')
        self.failUnlessEqual(
            {'preferred_auth_policies': 'http://uri http://zig'},
            self.req.getExtensionArgs())
        self.req.max_auth_age = 789
        self.failUnlessEqual(
            {'preferred_auth_policies': 'http://uri http://zig',
             'max_auth_age': '789'},
            self.req.getExtensionArgs())

    def test_getExtensionArgsWithAuthLevels(self):
        uri = 'http://example.com/auth_level'
        alias = 'my_level'
        self.req.addAuthLevel(uri, alias)

        uri2 = 'http://example.com/auth_level_2'
        alias2 = 'my_level_2'
        self.req.addAuthLevel(uri2, alias2)

        expected_args = {
            ('auth_level.ns.%s' % alias): uri,
            ('auth_level.ns.%s' % alias2): uri2,
            'preferred_auth_level_types': ' '.join([alias, alias2]),
            'preferred_auth_policies': '',
            }

        self.failUnlessEqual(expected_args, self.req.getExtensionArgs())

    def test_parseExtensionArgsWithAuthLevels(self):
        uri = 'http://example.com/auth_level'
        alias = 'my_level'

        uri2 = 'http://example.com/auth_level_2'
        alias2 = 'my_level_2'

        request_args = {
            ('auth_level.ns.%s' % alias): uri,
            ('auth_level.ns.%s' % alias2): uri2,
            'preferred_auth_level_types': ' '.join([alias, alias2]),
            'preferred_auth_policies': '',
            }

        # Check request object state
        self.req.parseExtensionArgs(request_args, is_openid1=False, strict=False)

        expected_auth_levels = [uri, uri2]

        self.assertEqual(expected_auth_levels,
                         self.req.preferred_auth_level_types)
        self.assertEqual(uri, self.req.auth_level_aliases[alias])
        self.assertEqual(uri2, self.req.auth_level_aliases[alias2])

    def test_parseExtensionArgsWithAuthLevels_openID1(self):
        request_args = {
            'preferred_auth_level_types':'nist jisa',
            }
        expected_auth_levels = [pape.LEVELS_NIST, pape.LEVELS_JISA]
        self.req.parseExtensionArgs(request_args, is_openid1=True)
        self.assertEqual(expected_auth_levels,
                         self.req.preferred_auth_level_types)

        self.req = pape.Request()
        self.req.parseExtensionArgs(request_args, is_openid1=False)
        self.assertEqual([],
                         self.req.preferred_auth_level_types)

        self.req = pape.Request()
        self.failUnlessRaises(ValueError,
                              self.req.parseExtensionArgs,
                              request_args, is_openid1=False, strict=True)

    def test_parseExtensionArgs_ignoreBadAuthLevels(self):
        request_args = {'preferred_auth_level_types':'monkeys'}
        self.req.parseExtensionArgs(request_args, False)
        self.assertEqual([], self.req.preferred_auth_level_types)

    def test_parseExtensionArgs_strictBadAuthLevels(self):
        request_args = {'preferred_auth_level_types':'monkeys'}
        self.failUnlessRaises(ValueError, self.req.parseExtensionArgs,
                              request_args, is_openid1=False, strict=True)

    def test_parseExtensionArgs(self):
        args = {'preferred_auth_policies': 'http://foo http://bar',
                'max_auth_age': '9'}
        self.req.parseExtensionArgs(args, False)
        self.failUnlessEqual(9, self.req.max_auth_age)
        self.failUnlessEqual(['http://foo','http://bar'],
                             self.req.preferred_auth_policies)
        self.failUnlessEqual([], self.req.preferred_auth_level_types)

    def test_parseExtensionArgs_strict_bad_auth_age(self):
        args = {'max_auth_age': 'not an int'}
        self.assertRaises(ValueError, self.req.parseExtensionArgs, args,
                          is_openid1=False, strict=True)

    def test_parseExtensionArgs_empty(self):
        self.req.parseExtensionArgs({}, False)
        self.failUnlessEqual(None, self.req.max_auth_age)
        self.failUnlessEqual([], self.req.preferred_auth_policies)
        self.failUnlessEqual([], self.req.preferred_auth_level_types)

    def test_fromOpenIDRequest(self):
        policy_uris = [pape.AUTH_MULTI_FACTOR, pape.AUTH_PHISHING_RESISTANT]
        openid_req_msg = Message.fromOpenIDArgs({
          'mode': 'checkid_setup',
          'ns': OPENID2_NS,
          'ns.pape': pape.ns_uri,
          'pape.preferred_auth_policies': ' '.join(policy_uris),
          'pape.max_auth_age': '5476'
          })
        oid_req = server.OpenIDRequest()
        oid_req.message = openid_req_msg
        req = pape.Request.fromOpenIDRequest(oid_req)
        self.failUnlessEqual(policy_uris, req.preferred_auth_policies)
        self.failUnlessEqual(5476, req.max_auth_age)

    def test_fromOpenIDRequest_no_pape(self):
        message = Message()
        openid_req = server.OpenIDRequest()
        openid_req.message = message
        pape_req = pape.Request.fromOpenIDRequest(openid_req)
        assert(pape_req is None)

    def test_preferred_types(self):
        self.req.addPolicyURI(pape.AUTH_PHISHING_RESISTANT)
        self.req.addPolicyURI(pape.AUTH_MULTI_FACTOR)
        pt = self.req.preferredTypes([pape.AUTH_MULTI_FACTOR,
                                      pape.AUTH_MULTI_FACTOR_PHYSICAL])
        self.failUnlessEqual([pape.AUTH_MULTI_FACTOR], pt)

class DummySuccessResponse:
    def __init__(self, message, signed_stuff):
        self.message = message
        self.signed_stuff = signed_stuff

    def isOpenID1(self):
        return False

    def getSignedNS(self, ns_uri):
        return self.signed_stuff

class PapeResponseTestCase(unittest.TestCase):
    def setUp(self):
        self.resp = pape.Response()

    def test_construct(self):
        self.failUnlessEqual([], self.resp.auth_policies)
        self.failUnlessEqual(None, self.resp.auth_time)
        self.failUnlessEqual('pape', self.resp.ns_alias)
        self.failUnlessEqual(None, self.resp.nist_auth_level)

        req2 = pape.Response([pape.AUTH_MULTI_FACTOR],
                             "2004-12-11T10:30:44Z", {pape.LEVELS_NIST: 3})
        self.failUnlessEqual([pape.AUTH_MULTI_FACTOR], req2.auth_policies)
        self.failUnlessEqual("2004-12-11T10:30:44Z", req2.auth_time)
        self.failUnlessEqual(3, req2.nist_auth_level)

    def test_add_policy_uri(self):
        self.failUnlessEqual([], self.resp.auth_policies)
        self.resp.addPolicyURI(pape.AUTH_MULTI_FACTOR)
        self.failUnlessEqual([pape.AUTH_MULTI_FACTOR], self.resp.auth_policies)
        self.resp.addPolicyURI(pape.AUTH_MULTI_FACTOR)
        self.failUnlessEqual([pape.AUTH_MULTI_FACTOR], self.resp.auth_policies)
        self.resp.addPolicyURI(pape.AUTH_PHISHING_RESISTANT)
        self.failUnlessEqual([pape.AUTH_MULTI_FACTOR,
                              pape.AUTH_PHISHING_RESISTANT],
                             self.resp.auth_policies)
        self.resp.addPolicyURI(pape.AUTH_MULTI_FACTOR)
        self.failUnlessEqual([pape.AUTH_MULTI_FACTOR,
                              pape.AUTH_PHISHING_RESISTANT],
                             self.resp.auth_policies)

        self.failUnlessRaises(RuntimeError, self.resp.addPolicyURI,
                              pape.AUTH_NONE)

    def test_getExtensionArgs(self):
        self.failUnlessEqual({'auth_policies': pape.AUTH_NONE},
                             self.resp.getExtensionArgs())
        self.resp.addPolicyURI('http://uri')
        self.failUnlessEqual({'auth_policies': 'http://uri'},
                             self.resp.getExtensionArgs())
        self.resp.addPolicyURI('http://zig')
        self.failUnlessEqual({'auth_policies': 'http://uri http://zig'},
                             self.resp.getExtensionArgs())
        self.resp.auth_time = "1776-07-04T14:43:12Z"
        self.failUnlessEqual(
            {'auth_policies': 'http://uri http://zig',
             'auth_time': "1776-07-04T14:43:12Z"},
            self.resp.getExtensionArgs())
        self.resp.setAuthLevel(pape.LEVELS_NIST, '3')
        self.failUnlessEqual(
            {'auth_policies': 'http://uri http://zig',
             'auth_time': "1776-07-04T14:43:12Z",
             'auth_level.nist': '3',
             'auth_level.ns.nist': pape.LEVELS_NIST},
            self.resp.getExtensionArgs())

    def test_getExtensionArgs_error_auth_age(self):
        self.resp.auth_time = "long ago"
        self.failUnlessRaises(ValueError, self.resp.getExtensionArgs)

    def test_parseExtensionArgs(self):
        args = {'auth_policies': 'http://foo http://bar',
                'auth_time': '1970-01-01T00:00:00Z'}
        self.resp.parseExtensionArgs(args, is_openid1=False)
        self.failUnlessEqual('1970-01-01T00:00:00Z', self.resp.auth_time)
        self.failUnlessEqual(['http://foo','http://bar'],
                             self.resp.auth_policies)

    def test_parseExtensionArgs_valid_none(self):
        args = {'auth_policies': pape.AUTH_NONE}
        self.resp.parseExtensionArgs(args, is_openid1=False)
        self.failUnlessEqual([], self.resp.auth_policies)

    def test_parseExtensionArgs_old_none(self):
        args = {'auth_policies': 'none'}
        self.resp.parseExtensionArgs(args, is_openid1=False)
        self.failUnlessEqual([], self.resp.auth_policies)

    def test_parseExtensionArgs_old_none_strict(self):
        args = {'auth_policies': 'none'}
        self.failUnlessRaises(
            ValueError,
            self.resp.parseExtensionArgs, args, is_openid1=False, strict=True)

    def test_parseExtensionArgs_empty(self):
        self.resp.parseExtensionArgs({}, is_openid1=False)
        self.failUnlessEqual(None, self.resp.auth_time)
        self.failUnlessEqual([], self.resp.auth_policies)

    def test_parseExtensionArgs_empty_strict(self):
        self.failUnlessRaises(
            ValueError,
            self.resp.parseExtensionArgs, {}, is_openid1=False, strict=True)

    def test_parseExtensionArgs_ignore_superfluous_none(self):
        policies = [pape.AUTH_NONE, pape.AUTH_MULTI_FACTOR_PHYSICAL]

        args = {
            'auth_policies': ' '.join(policies),
            }

        self.resp.parseExtensionArgs(args, is_openid1=False, strict=False)

        self.assertEqual([pape.AUTH_MULTI_FACTOR_PHYSICAL],
                         self.resp.auth_policies)

    def test_parseExtensionArgs_none_strict(self):
        policies = [pape.AUTH_NONE, pape.AUTH_MULTI_FACTOR_PHYSICAL]

        args = {
            'auth_policies': ' '.join(policies),
            }

        self.failUnlessRaises(ValueError, self.resp.parseExtensionArgs,
                              args, is_openid1=False, strict=True)

    def test_parseExtensionArgs_strict_bogus1(self):
        args = {'auth_policies': 'http://foo http://bar',
                'auth_time': 'yesterday'}
        self.failUnlessRaises(ValueError, self.resp.parseExtensionArgs,
                              args, is_openid1=False, strict=True)

    def test_parseExtensionArgs_openid1_strict(self):
        args = {'auth_level.nist': '0',
                'auth_policies': pape.AUTH_NONE,
                }
        self.resp.parseExtensionArgs(args, strict=True, is_openid1=True)
        self.failUnlessEqual('0', self.resp.getAuthLevel(pape.LEVELS_NIST))
        self.failUnlessEqual([], self.resp.auth_policies)

    def test_parseExtensionArgs_strict_no_namespace_decl_openid2(self):
        # Test the case where the namespace is not declared for an
        # auth level.
        args = {'auth_policies': pape.AUTH_NONE,
                'auth_level.nist': '0',
                }
        self.failUnlessRaises(ValueError, self.resp.parseExtensionArgs,
                              args, is_openid1=False, strict=True)

    def test_parseExtensionArgs_nostrict_no_namespace_decl_openid2(self):
        # Test the case where the namespace is not declared for an
        # auth level.
        args = {'auth_policies': pape.AUTH_NONE,
                'auth_level.nist': '0',
                }
        self.resp.parseExtensionArgs(args, is_openid1=False, strict=False)

        # There is no namespace declaration for this auth level.
        self.failUnlessRaises(KeyError, self.resp.getAuthLevel,
                              pape.LEVELS_NIST)

    def test_parseExtensionArgs_strict_good(self):
        args = {'auth_policies': 'http://foo http://bar',
                'auth_time': '1970-01-01T00:00:00Z',
                'auth_level.nist': '0',
                'auth_level.ns.nist': pape.LEVELS_NIST}
        self.resp.parseExtensionArgs(args, is_openid1=False, strict=True)
        self.failUnlessEqual(['http://foo','http://bar'],
                             self.resp.auth_policies)
        self.failUnlessEqual('1970-01-01T00:00:00Z', self.resp.auth_time)
        self.failUnlessEqual(0, self.resp.nist_auth_level)

    def test_parseExtensionArgs_nostrict_bogus(self):
        args = {'auth_policies': 'http://foo http://bar',
                'auth_time': 'when the cows come home',
                'nist_auth_level': 'some'}
        self.resp.parseExtensionArgs(args, is_openid1=False)
        self.failUnlessEqual(['http://foo','http://bar'],
                             self.resp.auth_policies)
        self.failUnlessEqual(None, self.resp.auth_time)
        self.failUnlessEqual(None, self.resp.nist_auth_level)

    def test_fromSuccessResponse(self):
        policy_uris = [pape.AUTH_MULTI_FACTOR, pape.AUTH_PHISHING_RESISTANT]
        openid_req_msg = Message.fromOpenIDArgs({
          'mode': 'id_res',
          'ns': OPENID2_NS,
          'ns.pape': pape.ns_uri,
          'pape.auth_policies': ' '.join(policy_uris),
          'pape.auth_time': '1970-01-01T00:00:00Z'
          })
        signed_stuff = {
          'auth_policies': ' '.join(policy_uris),
          'auth_time': '1970-01-01T00:00:00Z'
        }
        oid_req = DummySuccessResponse(openid_req_msg, signed_stuff)
        req = pape.Response.fromSuccessResponse(oid_req)
        self.failUnlessEqual(policy_uris, req.auth_policies)
        self.failUnlessEqual('1970-01-01T00:00:00Z', req.auth_time)

    def test_fromSuccessResponseNoSignedArgs(self):
        policy_uris = [pape.AUTH_MULTI_FACTOR, pape.AUTH_PHISHING_RESISTANT]
        openid_req_msg = Message.fromOpenIDArgs({
          'mode': 'id_res',
          'ns': OPENID2_NS,
          'ns.pape': pape.ns_uri,
          'pape.auth_policies': ' '.join(policy_uris),
          'pape.auth_time': '1970-01-01T00:00:00Z'
          })

        signed_stuff = {}

        class NoSigningDummyResponse(DummySuccessResponse):
            def getSignedNS(self, ns_uri):
                return None

        oid_req = NoSigningDummyResponse(openid_req_msg, signed_stuff)
        resp = pape.Response.fromSuccessResponse(oid_req)
        self.failUnless(resp is None)

if __name__ == '__main__':
    unittest.main()

########NEW FILE########
__FILENAME__ = test_parsehtml
from openid.yadis.parsehtml import YadisHTMLParser, ParseDone
from HTMLParser import HTMLParseError

import os.path, unittest, sys

class _TestCase(unittest.TestCase):
    reserved_values = ['None', 'EOF']

    def __init__(self, filename, testname, expected, case):
        self.filename = filename
        self.testname = testname
        self.expected = expected
        self.case = case
        unittest.TestCase.__init__(self)

    def runTest(self):
        p = YadisHTMLParser()
	try:
            p.feed(self.case)
        except ParseDone, why:
            found = why[0]

            # make sure we protect outselves against accidental bogus
            # test cases
            assert found not in self.reserved_values

            # convert to a string
            if found is None:
                found = 'None'

            msg = "%r != %r for case %s" % (found, self.expected, self.case)
            self.failUnlessEqual(found, self.expected, msg)
        except HTMLParseError:
            self.failUnless(self.expected == 'None', (self.case, self.expected))
        else:
            self.failUnless(self.expected == 'EOF', (self.case, self.expected))

    def shortDescription(self):
        return "%s (%s<%s>)" % (
            self.testname,
            self.__class__.__module__,
            os.path.basename(self.filename))

def parseCases(data):
    cases = []
    for chunk in data.split('\f\n'):
        expected, case = chunk.split('\n', 1)
        cases.append((expected, case))
    return cases

def pyUnitTests():
    """Make a pyunit TestSuite from a file defining test cases."""
    s = unittest.TestSuite()
    for (filename, test_num, expected, case) in getCases():
        s.addTest(_TestCase(filename, str(test_num), expected, case))
    return s

def test():
    runner = unittest.TextTestRunner()
    return runner.run(pyUnitTests())

filenames = ['data/test1-parsehtml.txt']

default_test_files = []
base = os.path.dirname(__file__)
for filename in filenames:
    full_name = os.path.join(base, filename)
    default_test_files.append(full_name)

def getCases(test_files=default_test_files):
    cases = []
    for filename in test_files:
        test_num = 0
        data = file(filename).read()
        for expected, case in parseCases(data):
            test_num += 1
            cases.append((filename, test_num, expected, case))
    return cases


if __name__ == '__main__':
    sys.exit(not test().wasSuccessful())

########NEW FILE########
__FILENAME__ = test_rpverify
"""Unit tests for verification of return_to URLs for a realm
"""

__all__ = ['TestBuildDiscoveryURL']

from openid.yadis.discover import DiscoveryResult, DiscoveryFailure
from openid.yadis import services
from openid.server import trustroot
from openid.test.support import CatchLogs
import unittest

# Too many methods does not apply to unit test objects
#pylint:disable-msg=R0904
class TestBuildDiscoveryURL(unittest.TestCase):
    """Tests for building the discovery URL from a realm and a
    return_to URL
    """

    def failUnlessDiscoURL(self, realm, expected_discovery_url):
        """Build a discovery URL out of the realm and a return_to and
        make sure that it matches the expected discovery URL
        """
        realm_obj = trustroot.TrustRoot.parse(realm)
        actual_discovery_url = realm_obj.buildDiscoveryURL()
        self.failUnlessEqual(expected_discovery_url, actual_discovery_url)

    def test_trivial(self):
        """There is no wildcard and the realm is the same as the return_to URL
        """
        self.failUnlessDiscoURL('http://example.com/foo',
                                'http://example.com/foo')

    def test_wildcard(self):
        """There is a wildcard
        """
        self.failUnlessDiscoURL('http://*.example.com/foo',
                                'http://www.example.com/foo')

class TestExtractReturnToURLs(unittest.TestCase):
    disco_url = 'http://example.com/'

    def setUp(self):
        self.original_discover = services.discover
        services.discover = self.mockDiscover
        self.data = None

    def tearDown(self):
        services.discover = self.original_discover

    def mockDiscover(self, uri):
        result = DiscoveryResult(uri)
        result.response_text = self.data
        result.normalized_uri = uri
        return result

    def failUnlessFileHasReturnURLs(self, filename, expected_return_urls):
        self.failUnlessXRDSHasReturnURLs(file(filename).read(),
                                         expected_return_urls)

    def failUnlessXRDSHasReturnURLs(self, data, expected_return_urls):
        self.data = data
        actual_return_urls = list(trustroot.getAllowedReturnURLs(
            self.disco_url))

        self.failUnlessEqual(expected_return_urls, actual_return_urls)

    def failUnlessDiscoveryFailure(self, text):
        self.data = text
        self.failUnlessRaises(
            DiscoveryFailure, trustroot.getAllowedReturnURLs, self.disco_url)

    def test_empty(self):
        self.failUnlessDiscoveryFailure('')

    def test_badXML(self):
        self.failUnlessDiscoveryFailure('>')

    def test_noEntries(self):
        self.failUnlessXRDSHasReturnURLs('''\
<?xml version="1.0" encoding="UTF-8"?>
<xrds:XRDS xmlns:xrds="xri://$xrds"
           xmlns="xri://$xrd*($v*2.0)"
           >
  <XRD>
  </XRD>
</xrds:XRDS>
''', [])

    def test_noReturnToEntries(self):
        self.failUnlessXRDSHasReturnURLs('''\
<?xml version="1.0" encoding="UTF-8"?>
<xrds:XRDS xmlns:xrds="xri://$xrds"
           xmlns="xri://$xrd*($v*2.0)"
           >
  <XRD>
    <Service priority="10">
      <Type>http://specs.openid.net/auth/2.0/server</Type>
      <URI>http://www.myopenid.com/server</URI>
    </Service>
  </XRD>
</xrds:XRDS>
''', [])

    def test_oneEntry(self):
        self.failUnlessXRDSHasReturnURLs('''\
<?xml version="1.0" encoding="UTF-8"?>
<xrds:XRDS xmlns:xrds="xri://$xrds"
           xmlns="xri://$xrd*($v*2.0)"
           >
  <XRD>
    <Service>
      <Type>http://specs.openid.net/auth/2.0/return_to</Type>
      <URI>http://rp.example.com/return</URI>
    </Service>
  </XRD>
</xrds:XRDS>
''', ['http://rp.example.com/return'])

    def test_twoEntries(self):
        self.failUnlessXRDSHasReturnURLs('''\
<?xml version="1.0" encoding="UTF-8"?>
<xrds:XRDS xmlns:xrds="xri://$xrds"
           xmlns="xri://$xrd*($v*2.0)"
           >
  <XRD>
    <Service priority="0">
      <Type>http://specs.openid.net/auth/2.0/return_to</Type>
      <URI>http://rp.example.com/return</URI>
    </Service>
    <Service priority="1">
      <Type>http://specs.openid.net/auth/2.0/return_to</Type>
      <URI>http://other.rp.example.com/return</URI>
    </Service>
  </XRD>
</xrds:XRDS>
''', ['http://rp.example.com/return',
      'http://other.rp.example.com/return'])

    def test_twoEntries_withOther(self):
        self.failUnlessXRDSHasReturnURLs('''\
<?xml version="1.0" encoding="UTF-8"?>
<xrds:XRDS xmlns:xrds="xri://$xrds"
           xmlns="xri://$xrd*($v*2.0)"
           >
  <XRD>
    <Service priority="0">
      <Type>http://specs.openid.net/auth/2.0/return_to</Type>
      <URI>http://rp.example.com/return</URI>
    </Service>
    <Service priority="1">
      <Type>http://specs.openid.net/auth/2.0/return_to</Type>
      <URI>http://other.rp.example.com/return</URI>
    </Service>
    <Service priority="0">
      <Type>http://example.com/LOLCATS</Type>
      <URI>http://example.com/invisible+uri</URI>
    </Service>
  </XRD>
</xrds:XRDS>
''', ['http://rp.example.com/return',
      'http://other.rp.example.com/return'])



class TestReturnToMatches(unittest.TestCase):
    def test_noEntries(self):
        self.failIf(trustroot.returnToMatches([], 'anything'))

    def test_exactMatch(self):
        r = 'http://example.com/return.to'
        self.failUnless(trustroot.returnToMatches([r], r))

    def test_garbageMatch(self):
        r = 'http://example.com/return.to'
        self.failUnless(trustroot.returnToMatches(
            ['This is not a URL at all. In fact, it has characters, '
             'like "<" that are not allowed in URLs',
             r],
            r))

    def test_descendant(self):
        r = 'http://example.com/return.to'
        self.failUnless(trustroot.returnToMatches(
            [r],
            'http://example.com/return.to/user:joe'))

    def test_wildcard(self):
        self.failIf(trustroot.returnToMatches(
            ['http://*.example.com/return.to'],
            'http://example.com/return.to'))

    def test_noMatch(self):
        r = 'http://example.com/return.to'
        self.failIf(trustroot.returnToMatches(
            [r],
            'http://example.com/xss_exploit'))

class TestVerifyReturnTo(unittest.TestCase, CatchLogs):

    def setUp(self):
        CatchLogs.setUp(self)

    def tearDown(self):
        CatchLogs.tearDown(self)
    
    def test_bogusRealm(self):
        self.failIf(trustroot.verifyReturnTo('', 'http://example.com/'))

    def test_verifyWithDiscoveryCalled(self):
        realm = 'http://*.example.com/'
        return_to = 'http://www.example.com/foo'

        def vrfy(disco_url):
            self.failUnlessEqual('http://www.example.com/', disco_url)
            return [return_to]

        self.failUnless(
            trustroot.verifyReturnTo(realm, return_to, _vrfy=vrfy))
        self.failUnlessLogEmpty()

    def test_verifyFailWithDiscoveryCalled(self):
        realm = 'http://*.example.com/'
        return_to = 'http://www.example.com/foo'

        def vrfy(disco_url):
            self.failUnlessEqual('http://www.example.com/', disco_url)
            return ['http://something-else.invalid/']

        self.failIf(
            trustroot.verifyReturnTo(realm, return_to, _vrfy=vrfy))
        self.failUnlessLogMatches("Failed to validate return_to")

    def test_verifyFailIfDiscoveryRedirects(self):
        realm = 'http://*.example.com/'
        return_to = 'http://www.example.com/foo'

        def vrfy(disco_url):
            raise trustroot.RealmVerificationRedirected(
                disco_url, "http://redirected.invalid")

        self.failIf(
            trustroot.verifyReturnTo(realm, return_to, _vrfy=vrfy))
        self.failUnlessLogMatches("Attempting to verify")

if __name__ == '__main__':
    unittest.main()

########NEW FILE########
__FILENAME__ = test_server
"""Tests for openid.server.
"""
from openid.server import server
from openid import association, cryptutil, oidutil
from openid.message import Message, OPENID_NS, OPENID2_NS, OPENID1_NS, \
     IDENTIFIER_SELECT, no_default, OPENID1_URL_LIMIT
from openid.store import memstore
from openid.test.support import CatchLogs
import cgi

import unittest
import warnings

from urlparse import urlparse

# In general, if you edit or add tests here, try to move in the direction
# of testing smaller units.  For testing the external interfaces, we'll be
# developing an implementation-agnostic testing suite.

# for more, see /etc/ssh/moduli

ALT_MODULUS = 0xCAADDDEC1667FC68B5FA15D53C4E1532DD24561A1A2D47A12C01ABEA1E00731F6921AAC40742311FDF9E634BB7131BEE1AF240261554389A910425E044E88C8359B010F5AD2B80E29CB1A5B027B19D9E01A6F63A6F45E5D7ED2FF6A2A0085050A7D0CF307C3DB51D2490355907B4427C23A98DF1EB8ABEF2BA209BB7AFFE86A7
ALT_GEN = 5

class TestProtocolError(unittest.TestCase):
    def test_browserWithReturnTo(self):
        return_to = "http://rp.unittest/consumer"
        # will be a ProtocolError raised by Decode or CheckIDRequest.answer
        args = Message.fromPostArgs({
            'openid.mode': 'monkeydance',
            'openid.identity': 'http://wagu.unittest/',
            'openid.return_to': return_to,
            })
        e = server.ProtocolError(args, "plucky")
        self.failUnless(e.hasReturnTo())
        expected_args = {
            'openid.mode': ['error'],
            'openid.error': ['plucky'],
            }

        rt_base, result_args = e.encodeToURL().split('?', 1)
        result_args = cgi.parse_qs(result_args)
        self.failUnlessEqual(result_args, expected_args)

    def test_browserWithReturnTo_OpenID2_GET(self):
        return_to = "http://rp.unittest/consumer"
        # will be a ProtocolError raised by Decode or CheckIDRequest.answer
        args = Message.fromPostArgs({
            'openid.ns': OPENID2_NS,
            'openid.mode': 'monkeydance',
            'openid.identity': 'http://wagu.unittest/',
            'openid.claimed_id': 'http://wagu.unittest/',
            'openid.return_to': return_to,
            })
        e = server.ProtocolError(args, "plucky")
        self.failUnless(e.hasReturnTo())
        expected_args = {
            'openid.ns': [OPENID2_NS],
            'openid.mode': ['error'],
            'openid.error': ['plucky'],
            }

        rt_base, result_args = e.encodeToURL().split('?', 1)
        result_args = cgi.parse_qs(result_args)
        self.failUnlessEqual(result_args, expected_args)

    def test_browserWithReturnTo_OpenID2_POST(self):
        return_to = "http://rp.unittest/consumer" + ('x' * OPENID1_URL_LIMIT)
        # will be a ProtocolError raised by Decode or CheckIDRequest.answer
        args = Message.fromPostArgs({
            'openid.ns': OPENID2_NS,
            'openid.mode': 'monkeydance',
            'openid.identity': 'http://wagu.unittest/',
            'openid.claimed_id': 'http://wagu.unittest/',
            'openid.return_to': return_to,
            })
        e = server.ProtocolError(args, "plucky")
        self.failUnless(e.hasReturnTo())
        expected_args = {
            'openid.ns': [OPENID2_NS],
            'openid.mode': ['error'],
            'openid.error': ['plucky'],
            }

        self.failUnless(e.whichEncoding() == server.ENCODE_HTML_FORM)
        self.failUnless(e.toFormMarkup() == e.toMessage().toFormMarkup(
            args.getArg(OPENID_NS, 'return_to')))

    def test_browserWithReturnTo_OpenID1_exceeds_limit(self):
        return_to = "http://rp.unittest/consumer" + ('x' * OPENID1_URL_LIMIT)
        # will be a ProtocolError raised by Decode or CheckIDRequest.answer
        args = Message.fromPostArgs({
            'openid.mode': 'monkeydance',
            'openid.identity': 'http://wagu.unittest/',
            'openid.return_to': return_to,
            })
        e = server.ProtocolError(args, "plucky")
        self.failUnless(e.hasReturnTo())
        expected_args = {
            'openid.mode': ['error'],
            'openid.error': ['plucky'],
            }

        self.failUnless(e.whichEncoding() == server.ENCODE_URL)

        rt_base, result_args = e.encodeToURL().split('?', 1)
        result_args = cgi.parse_qs(result_args)
        self.failUnlessEqual(result_args, expected_args)

    def test_noReturnTo(self):
        # will be a ProtocolError raised by Decode or CheckIDRequest.answer
        args = Message.fromPostArgs({
            'openid.mode': 'zebradance',
            'openid.identity': 'http://wagu.unittest/',
            })
        e = server.ProtocolError(args, "waffles")
        self.failIf(e.hasReturnTo())
        expected = """error:waffles
mode:error
"""
        self.failUnlessEqual(e.encodeToKVForm(), expected)


    def test_noMessage(self):
        e = server.ProtocolError(None, "no moar pancakes")
        self.failIf(e.hasReturnTo())
        self.failUnlessEqual(e.whichEncoding(), None)


class TestDecode(unittest.TestCase):
    def setUp(self):
        self.claimed_id = 'http://de.legating.de.coder.unittest/'
        self.id_url = "http://decoder.am.unittest/"
        self.rt_url = "http://rp.unittest/foobot/?qux=zam"
        self.tr_url = "http://rp.unittest/"
        self.assoc_handle = "{assoc}{handle}"
        self.op_endpoint = 'http://endpoint.unittest/encode'
        self.store = memstore.MemoryStore()
        self.server = server.Server(self.store, self.op_endpoint)
        self.decode = self.server.decoder.decode
        self.decode = server.Decoder(self.server).decode

    def test_none(self):
        args = {}
        r = self.decode(args)
        self.failUnlessEqual(r, None)

    def test_irrelevant(self):
        args = {
            'pony': 'spotted',
            'sreg.mutant_power': 'decaffinator',
            }
        self.failUnlessRaises(server.ProtocolError, self.decode, args)

    def test_bad(self):
        args = {
            'openid.mode': 'twos-compliment',
            'openid.pants': 'zippered',
            }
        self.failUnlessRaises(server.ProtocolError, self.decode, args)

    def test_dictOfLists(self):
        args = {
            'openid.mode': ['checkid_setup'],
            'openid.identity': self.id_url,
            'openid.assoc_handle': self.assoc_handle,
            'openid.return_to': self.rt_url,
            'openid.trust_root': self.tr_url,
            }
        try:
            result = self.decode(args)
        except TypeError, err:
            self.failUnless(str(err).find('values') != -1, err)
        else:
            self.fail("Expected TypeError, but got result %s" % (result,))

    def test_checkidImmediate(self):
        args = {
            'openid.mode': 'checkid_immediate',
            'openid.identity': self.id_url,
            'openid.assoc_handle': self.assoc_handle,
            'openid.return_to': self.rt_url,
            'openid.trust_root': self.tr_url,
            # should be ignored
            'openid.some.extension': 'junk',
            }
        r = self.decode(args)
        self.failUnless(isinstance(r, server.CheckIDRequest))
        self.failUnlessEqual(r.mode, "checkid_immediate")
        self.failUnlessEqual(r.immediate, True)
        self.failUnlessEqual(r.identity, self.id_url)
        self.failUnlessEqual(r.trust_root, self.tr_url)
        self.failUnlessEqual(r.return_to, self.rt_url)
        self.failUnlessEqual(r.assoc_handle, self.assoc_handle)

    def test_checkidSetup(self):
        args = {
            'openid.mode': 'checkid_setup',
            'openid.identity': self.id_url,
            'openid.assoc_handle': self.assoc_handle,
            'openid.return_to': self.rt_url,
            'openid.trust_root': self.tr_url,
            }
        r = self.decode(args)
        self.failUnless(isinstance(r, server.CheckIDRequest))
        self.failUnlessEqual(r.mode, "checkid_setup")
        self.failUnlessEqual(r.immediate, False)
        self.failUnlessEqual(r.identity, self.id_url)
        self.failUnlessEqual(r.trust_root, self.tr_url)
        self.failUnlessEqual(r.return_to, self.rt_url)

    def test_checkidSetupOpenID2(self):
        args = {
            'openid.ns': OPENID2_NS,
            'openid.mode': 'checkid_setup',
            'openid.identity': self.id_url,
            'openid.claimed_id': self.claimed_id,
            'openid.assoc_handle': self.assoc_handle,
            'openid.return_to': self.rt_url,
            'openid.realm': self.tr_url,
            }
        r = self.decode(args)
        self.failUnless(isinstance(r, server.CheckIDRequest))
        self.failUnlessEqual(r.mode, "checkid_setup")
        self.failUnlessEqual(r.immediate, False)
        self.failUnlessEqual(r.identity, self.id_url)
        self.failUnlessEqual(r.claimed_id, self.claimed_id)
        self.failUnlessEqual(r.trust_root, self.tr_url)
        self.failUnlessEqual(r.return_to, self.rt_url)

    def test_checkidSetupNoClaimedIDOpenID2(self):
        args = {
            'openid.ns': OPENID2_NS,
            'openid.mode': 'checkid_setup',
            'openid.identity': self.id_url,
            'openid.assoc_handle': self.assoc_handle,
            'openid.return_to': self.rt_url,
            'openid.realm': self.tr_url,
            }
        self.failUnlessRaises(server.ProtocolError, self.decode, args)

    def test_checkidSetupNoIdentityOpenID2(self):
        args = {
            'openid.ns': OPENID2_NS,
            'openid.mode': 'checkid_setup',
            'openid.assoc_handle': self.assoc_handle,
            'openid.return_to': self.rt_url,
            'openid.realm': self.tr_url,
            }
        r = self.decode(args)
        self.failUnless(isinstance(r, server.CheckIDRequest))
        self.failUnlessEqual(r.mode, "checkid_setup")
        self.failUnlessEqual(r.immediate, False)
        self.failUnlessEqual(r.identity, None)
        self.failUnlessEqual(r.trust_root, self.tr_url)
        self.failUnlessEqual(r.return_to, self.rt_url)

    def test_checkidSetupNoReturnOpenID1(self):
        """Make sure an OpenID 1 request cannot be decoded if it lacks
        a return_to.
        """
        args = {
            'openid.mode': 'checkid_setup',
            'openid.identity': self.id_url,
            'openid.assoc_handle': self.assoc_handle,
            'openid.trust_root': self.tr_url,
            }
        self.failUnlessRaises(server.ProtocolError, self.decode, args)

    def test_checkidSetupNoReturnOpenID2(self):
        """Make sure an OpenID 2 request with no return_to can be
        decoded, and make sure a response to such a request raises
        NoReturnToError.
        """
        args = {
            'openid.ns': OPENID2_NS,
            'openid.mode': 'checkid_setup',
            'openid.identity': self.id_url,
            'openid.claimed_id': self.id_url,
            'openid.assoc_handle': self.assoc_handle,
            'openid.realm': self.tr_url,
            }
        self.failUnless(isinstance(self.decode(args), server.CheckIDRequest))

        req = self.decode(args)
        self.assertRaises(server.NoReturnToError, req.answer, False)
        self.assertRaises(server.NoReturnToError, req.encodeToURL, 'bogus')
        self.assertRaises(server.NoReturnToError, req.getCancelURL)

    def test_checkidSetupRealmRequiredOpenID2(self):
        """Make sure that an OpenID 2 request which lacks return_to
        cannot be decoded if it lacks a realm.  Spec: This value
        (openid.realm) MUST be sent if openid.return_to is omitted.
        """
        args = {
            'openid.ns': OPENID2_NS,
            'openid.mode': 'checkid_setup',
            'openid.identity': self.id_url,
            'openid.assoc_handle': self.assoc_handle,
            }
        self.failUnlessRaises(server.ProtocolError, self.decode, args)

    def test_checkidSetupBadReturn(self):
        args = {
            'openid.mode': 'checkid_setup',
            'openid.identity': self.id_url,
            'openid.assoc_handle': self.assoc_handle,
            'openid.return_to': 'not a url',
            }
        try:
            result = self.decode(args)
        except server.ProtocolError, err:
            self.failUnless(err.openid_message)
        else:
            self.fail("Expected ProtocolError, instead returned with %s" %
                      (result,))

    def test_checkidSetupUntrustedReturn(self):
        args = {
            'openid.mode': 'checkid_setup',
            'openid.identity': self.id_url,
            'openid.assoc_handle': self.assoc_handle,
            'openid.return_to': self.rt_url,
            'openid.trust_root': 'http://not-the-return-place.unittest/',
            }
        try:
            result = self.decode(args)
        except server.UntrustedReturnURL, err:
            self.failUnless(err.openid_message)
        else:
            self.fail("Expected UntrustedReturnURL, instead returned with %s" %
                      (result,))

    def test_checkAuth(self):
        args = {
            'openid.mode': 'check_authentication',
            'openid.assoc_handle': '{dumb}{handle}',
            'openid.sig': 'sigblob',
            'openid.signed': 'identity,return_to,response_nonce,mode',
            'openid.identity': 'signedval1',
            'openid.return_to': 'signedval2',
            'openid.response_nonce': 'signedval3',
            'openid.baz': 'unsigned',
            }
        r = self.decode(args)
        self.failUnless(isinstance(r, server.CheckAuthRequest))
        self.failUnlessEqual(r.mode, 'check_authentication')
        self.failUnlessEqual(r.sig, 'sigblob')


    def test_checkAuthMissingSignature(self):
        args = {
            'openid.mode': 'check_authentication',
            'openid.assoc_handle': '{dumb}{handle}',
            'openid.signed': 'foo,bar,mode',
            'openid.foo': 'signedval1',
            'openid.bar': 'signedval2',
            'openid.baz': 'unsigned',
            }
        self.failUnlessRaises(server.ProtocolError, self.decode, args)


    def test_checkAuthAndInvalidate(self):
        args = {
            'openid.mode': 'check_authentication',
            'openid.assoc_handle': '{dumb}{handle}',
            'openid.invalidate_handle': '[[SMART_handle]]',
            'openid.sig': 'sigblob',
            'openid.signed': 'identity,return_to,response_nonce,mode',
            'openid.identity': 'signedval1',
            'openid.return_to': 'signedval2',
            'openid.response_nonce': 'signedval3',
            'openid.baz': 'unsigned',
            }
        r = self.decode(args)
        self.failUnless(isinstance(r, server.CheckAuthRequest))
        self.failUnlessEqual(r.invalidate_handle, '[[SMART_handle]]')


    def test_associateDH(self):
        args = {
            'openid.mode': 'associate',
            'openid.session_type': 'DH-SHA1',
            'openid.dh_consumer_public': "Rzup9265tw==",
            }
        r = self.decode(args)
        self.failUnless(isinstance(r, server.AssociateRequest))
        self.failUnlessEqual(r.mode, "associate")
        self.failUnlessEqual(r.session.session_type, "DH-SHA1")
        self.failUnlessEqual(r.assoc_type, "HMAC-SHA1")
        self.failUnless(r.session.consumer_pubkey)

    def test_associateDHMissingKey(self):
        """Trying DH assoc w/o public key"""
        args = {
            'openid.mode': 'associate',
            'openid.session_type': 'DH-SHA1',
            }
        # Using DH-SHA1 without supplying dh_consumer_public is an error.
        self.failUnlessRaises(server.ProtocolError, self.decode, args)


    def test_associateDHpubKeyNotB64(self):
        args = {
            'openid.mode': 'associate',
            'openid.session_type': 'DH-SHA1',
            'openid.dh_consumer_public': "donkeydonkeydonkey",
            }
        self.failUnlessRaises(server.ProtocolError, self.decode, args)


    def test_associateDHModGen(self):
        # test dh with non-default but valid values for dh_modulus and dh_gen
        args = {
            'openid.mode': 'associate',
            'openid.session_type': 'DH-SHA1',
            'openid.dh_consumer_public': "Rzup9265tw==",
            'openid.dh_modulus': cryptutil.longToBase64(ALT_MODULUS),
            'openid.dh_gen': cryptutil.longToBase64(ALT_GEN) ,
            }
        r = self.decode(args)
        self.failUnless(isinstance(r, server.AssociateRequest))
        self.failUnlessEqual(r.mode, "associate")
        self.failUnlessEqual(r.session.session_type, "DH-SHA1")
        self.failUnlessEqual(r.assoc_type, "HMAC-SHA1")
        self.failUnlessEqual(r.session.dh.modulus, ALT_MODULUS)
        self.failUnlessEqual(r.session.dh.generator, ALT_GEN)
        self.failUnless(r.session.consumer_pubkey)


    def test_associateDHCorruptModGen(self):
        # test dh with non-default but valid values for dh_modulus and dh_gen
        args = {
            'openid.mode': 'associate',
            'openid.session_type': 'DH-SHA1',
            'openid.dh_consumer_public': "Rzup9265tw==",
            'openid.dh_modulus': 'pizza',
            'openid.dh_gen': 'gnocchi',
            }
        self.failUnlessRaises(server.ProtocolError, self.decode, args)


    def test_associateDHMissingModGen(self):
        # test dh with non-default but valid values for dh_modulus and dh_gen
        args = {
            'openid.mode': 'associate',
            'openid.session_type': 'DH-SHA1',
            'openid.dh_consumer_public': "Rzup9265tw==",
            'openid.dh_modulus': 'pizza',
            }
        self.failUnlessRaises(server.ProtocolError, self.decode, args)


#     def test_associateDHInvalidModGen(self):
#         # test dh with properly encoded values that are not a valid
#         #   modulus/generator combination.
#         args = {
#             'openid.mode': 'associate',
#             'openid.session_type': 'DH-SHA1',
#             'openid.dh_consumer_public': "Rzup9265tw==",
#             'openid.dh_modulus': cryptutil.longToBase64(9),
#             'openid.dh_gen': cryptutil.longToBase64(27) ,
#             }
#         self.failUnlessRaises(server.ProtocolError, self.decode, args)
#     test_associateDHInvalidModGen.todo = "low-priority feature"


    def test_associateWeirdSession(self):
        args = {
            'openid.mode': 'associate',
            'openid.session_type': 'FLCL6',
            'openid.dh_consumer_public': "YQ==\n",
            }
        self.failUnlessRaises(server.ProtocolError, self.decode, args)


    def test_associatePlain(self):
        args = {
            'openid.mode': 'associate',
            }
        r = self.decode(args)
        self.failUnless(isinstance(r, server.AssociateRequest))
        self.failUnlessEqual(r.mode, "associate")
        self.failUnlessEqual(r.session.session_type, "no-encryption")
        self.failUnlessEqual(r.assoc_type, "HMAC-SHA1")

    def test_nomode(self):
        args = {
            'openid.session_type': 'DH-SHA1',
            'openid.dh_consumer_public': "my public keeey",
            }
        self.failUnlessRaises(server.ProtocolError, self.decode, args)

    def test_invalidns(self):
	args = {'openid.ns': 'Tuesday',
		'openid.mode': 'associate'}

        try:
            r = self.decode(args)
        except server.ProtocolError, err:
            # Assert that the ProtocolError does have a Message attached
            # to it, even though the request wasn't a well-formed Message.
            self.failUnless(err.openid_message)
            # The error message contains the bad openid.ns.
            self.failUnless('Tuesday' in str(err), str(err))
        else:
            self.fail("Expected ProtocolError but returned with %r" % (r,))


class TestEncode(unittest.TestCase):
    def setUp(self):
        self.encoder = server.Encoder()
        self.encode = self.encoder.encode
        self.op_endpoint = 'http://endpoint.unittest/encode'
        self.store = memstore.MemoryStore()
        self.server = server.Server(self.store, self.op_endpoint)

    def test_id_res_OpenID2_GET(self):
        """
        Check that when an OpenID 2 response does not exceed the
        OpenID 1 message size, a GET response (i.e., redirect) is
        issued.
        """
        request = server.CheckIDRequest(
            identity = 'http://bombom.unittest/',
            trust_root = 'http://burr.unittest/',
            return_to = 'http://burr.unittest/999',
            immediate = False,
            op_endpoint = self.server.op_endpoint,
            )
        request.message = Message(OPENID2_NS)
        response = server.OpenIDResponse(request)
        response.fields = Message.fromOpenIDArgs({
            'ns': OPENID2_NS,
            'mode': 'id_res',
            'identity': request.identity,
            'claimed_id': request.identity,
            'return_to': request.return_to,
            })

        self.failIf(response.renderAsForm())
        self.failUnless(response.whichEncoding() == server.ENCODE_URL)
        webresponse = self.encode(response)
        self.failUnless(webresponse.headers.has_key('location'))

    def test_id_res_OpenID2_POST(self):
        """
        Check that when an OpenID 2 response exceeds the OpenID 1
        message size, a POST response (i.e., an HTML form) is
        returned.
        """
        request = server.CheckIDRequest(
            identity = 'http://bombom.unittest/',
            trust_root = 'http://burr.unittest/',
            return_to = 'http://burr.unittest/999',
            immediate = False,
            op_endpoint = self.server.op_endpoint,
            )
        request.message = Message(OPENID2_NS)
        response = server.OpenIDResponse(request)
        response.fields = Message.fromOpenIDArgs({
            'ns': OPENID2_NS,
            'mode': 'id_res',
            'identity': request.identity,
            'claimed_id': request.identity,
            'return_to': 'x' * OPENID1_URL_LIMIT,
            })

        self.failUnless(response.renderAsForm())
        self.failUnless(len(response.encodeToURL()) > OPENID1_URL_LIMIT)
        self.failUnless(response.whichEncoding() == server.ENCODE_HTML_FORM)
        webresponse = self.encode(response)
        self.failUnlessEqual(webresponse.body, response.toFormMarkup())

    def test_toFormMarkup(self):
        request = server.CheckIDRequest(
            identity = 'http://bombom.unittest/',
            trust_root = 'http://burr.unittest/',
            return_to = 'http://burr.unittest/999',
            immediate = False,
            op_endpoint = self.server.op_endpoint,
            )
        request.message = Message(OPENID2_NS)
        response = server.OpenIDResponse(request)
        response.fields = Message.fromOpenIDArgs({
            'ns': OPENID2_NS,
            'mode': 'id_res',
            'identity': request.identity,
            'claimed_id': request.identity,
            'return_to': 'x' * OPENID1_URL_LIMIT,
            })

        form_markup = response.toFormMarkup({'foo':'bar'})
        self.failUnless(' foo="bar"' in form_markup)

    def test_toHTML(self):
        request = server.CheckIDRequest(
            identity = 'http://bombom.unittest/',
            trust_root = 'http://burr.unittest/',
            return_to = 'http://burr.unittest/999',
            immediate = False,
            op_endpoint = self.server.op_endpoint,
            )
        request.message = Message(OPENID2_NS)
        response = server.OpenIDResponse(request)
        response.fields = Message.fromOpenIDArgs({
            'ns': OPENID2_NS,
            'mode': 'id_res',
            'identity': request.identity,
            'claimed_id': request.identity,
            'return_to': 'x' * OPENID1_URL_LIMIT,
            })
        html = response.toHTML()
        self.failUnless('<html>' in html)
        self.failUnless('</html>' in html)
        self.failUnless('<body onload=' in html)
        self.failUnless('<form' in html)
        self.failUnless('http://bombom.unittest/' in html)

    def test_id_res_OpenID1_exceeds_limit(self):
        """
        Check that when an OpenID 1 response exceeds the OpenID 1
        message size, a GET response is issued.  Technically, this
        shouldn't be permitted by the library, but this test is in
        place to preserve the status quo for OpenID 1.
        """
        request = server.CheckIDRequest(
            identity = 'http://bombom.unittest/',
            trust_root = 'http://burr.unittest/',
            return_to = 'http://burr.unittest/999',
            immediate = False,
            op_endpoint = self.server.op_endpoint,
            )
        request.message = Message(OPENID2_NS)
        response = server.OpenIDResponse(request)
        response.fields = Message.fromOpenIDArgs({
            'mode': 'id_res',
            'identity': request.identity,
            'return_to': 'x' * OPENID1_URL_LIMIT,
            })

        self.failIf(response.renderAsForm())
        self.failUnless(len(response.encodeToURL()) > OPENID1_URL_LIMIT)
        self.failUnless(response.whichEncoding() == server.ENCODE_URL)
        webresponse = self.encode(response)
        self.failUnlessEqual(webresponse.headers['location'], response.encodeToURL())

    def test_id_res(self):
        request = server.CheckIDRequest(
            identity = 'http://bombom.unittest/',
            trust_root = 'http://burr.unittest/',
            return_to = 'http://burr.unittest/999',
            immediate = False,
            op_endpoint = self.server.op_endpoint,
            )
        request.message = Message(OPENID2_NS)
        response = server.OpenIDResponse(request)
        response.fields = Message.fromOpenIDArgs({
            'mode': 'id_res',
            'identity': request.identity,
            'return_to': request.return_to,
            })
        webresponse = self.encode(response)
        self.failUnlessEqual(webresponse.code, server.HTTP_REDIRECT)
        self.failUnless(webresponse.headers.has_key('location'))

        location = webresponse.headers['location']
        self.failUnless(location.startswith(request.return_to),
                        "%s does not start with %s" % (location,
                                                       request.return_to))
        # argh.
        q2 = dict(cgi.parse_qsl(urlparse(location)[4]))
        expected = response.fields.toPostArgs()
        self.failUnlessEqual(q2, expected)

    def test_cancel(self):
        request = server.CheckIDRequest(
            identity = 'http://bombom.unittest/',
            trust_root = 'http://burr.unittest/',
            return_to = 'http://burr.unittest/999',
            immediate = False,
            op_endpoint = self.server.op_endpoint,
            )
        request.message = Message(OPENID2_NS)
        response = server.OpenIDResponse(request)
        response.fields = Message.fromOpenIDArgs({
            'mode': 'cancel',
            })
        webresponse = self.encode(response)
        self.failUnlessEqual(webresponse.code, server.HTTP_REDIRECT)
        self.failUnless(webresponse.headers.has_key('location'))

    def test_cancelToForm(self):
        request = server.CheckIDRequest(
            identity = 'http://bombom.unittest/',
            trust_root = 'http://burr.unittest/',
            return_to = 'http://burr.unittest/999',
            immediate = False,
            op_endpoint = self.server.op_endpoint,
            )
        request.message = Message(OPENID2_NS)
        response = server.OpenIDResponse(request)
        response.fields = Message.fromOpenIDArgs({
            'mode': 'cancel',
            })
        form = response.toFormMarkup()
        self.failUnless(form)

    def test_assocReply(self):
        msg = Message(OPENID2_NS)
        msg.setArg(OPENID2_NS, 'session_type', 'no-encryption')
        request = server.AssociateRequest.fromMessage(msg)
        response = server.OpenIDResponse(request)
        response.fields = Message.fromPostArgs(
            {'openid.assoc_handle': "every-zig"})
        webresponse = self.encode(response)
        body = """assoc_handle:every-zig
"""
        self.failUnlessEqual(webresponse.code, server.HTTP_OK)
        self.failUnlessEqual(webresponse.headers, {})
        self.failUnlessEqual(webresponse.body, body)

    def test_checkauthReply(self):
        request = server.CheckAuthRequest('a_sock_monkey',
                                          'siggggg',
                                          [])
        response = server.OpenIDResponse(request)
        response.fields = Message.fromOpenIDArgs({
            'is_valid': 'true',
            'invalidate_handle': 'xXxX:xXXx'
            })
        body = """invalidate_handle:xXxX:xXXx
is_valid:true
"""
        webresponse = self.encode(response)
        self.failUnlessEqual(webresponse.code, server.HTTP_OK)
        self.failUnlessEqual(webresponse.headers, {})
        self.failUnlessEqual(webresponse.body, body)

    def test_unencodableError(self):
        args = Message.fromPostArgs({
            'openid.identity': 'http://limu.unittest/',
            })
        e = server.ProtocolError(args, "wet paint")
        self.failUnlessRaises(server.EncodingError, self.encode, e)

    def test_encodableError(self):
        args = Message.fromPostArgs({
            'openid.mode': 'associate',
            'openid.identity': 'http://limu.unittest/',
            })
        body="error:snoot\nmode:error\n"
        webresponse = self.encode(server.ProtocolError(args, "snoot"))
        self.failUnlessEqual(webresponse.code, server.HTTP_ERROR)
        self.failUnlessEqual(webresponse.headers, {})
        self.failUnlessEqual(webresponse.body, body)



class TestSigningEncode(unittest.TestCase):
    def setUp(self):
        self._dumb_key = server.Signatory._dumb_key
        self._normal_key = server.Signatory._normal_key
        self.store = memstore.MemoryStore()
        self.server = server.Server(self.store, "http://signing.unittest/enc")
        self.request = server.CheckIDRequest(
            identity = 'http://bombom.unittest/',
            trust_root = 'http://burr.unittest/',
            return_to = 'http://burr.unittest/999',
            immediate = False,
            op_endpoint = self.server.op_endpoint,
            )
        self.request.message = Message(OPENID2_NS)
        self.response = server.OpenIDResponse(self.request)
        self.response.fields = Message.fromOpenIDArgs({
            'mode': 'id_res',
            'identity': self.request.identity,
            'return_to': self.request.return_to,
            })
        self.signatory = server.Signatory(self.store)
        self.encoder = server.SigningEncoder(self.signatory)
        self.encode = self.encoder.encode

    def test_idres(self):
        assoc_handle = '{bicycle}{shed}'
        self.store.storeAssociation(
            self._normal_key,
            association.Association.fromExpiresIn(60, assoc_handle,
                                                  'sekrit', 'HMAC-SHA1'))
        self.request.assoc_handle = assoc_handle
        webresponse = self.encode(self.response)
        self.failUnlessEqual(webresponse.code, server.HTTP_REDIRECT)
        self.failUnless(webresponse.headers.has_key('location'))

        location = webresponse.headers['location']
        query = cgi.parse_qs(urlparse(location)[4])
        self.failUnless('openid.sig' in query)
        self.failUnless('openid.assoc_handle' in query)
        self.failUnless('openid.signed' in query)

    def test_idresDumb(self):
        webresponse = self.encode(self.response)
        self.failUnlessEqual(webresponse.code, server.HTTP_REDIRECT)
        self.failUnless(webresponse.headers.has_key('location'))

        location = webresponse.headers['location']
        query = cgi.parse_qs(urlparse(location)[4])
        self.failUnless('openid.sig' in query)
        self.failUnless('openid.assoc_handle' in query)
        self.failUnless('openid.signed' in query)

    def test_forgotStore(self):
        self.encoder.signatory = None
        self.failUnlessRaises(ValueError, self.encode, self.response)

    def test_cancel(self):
        request = server.CheckIDRequest(
            identity = 'http://bombom.unittest/',
            trust_root = 'http://burr.unittest/',
            return_to = 'http://burr.unittest/999',
            immediate = False,
            op_endpoint = self.server.op_endpoint,
            )
        request.message = Message(OPENID2_NS)
        response = server.OpenIDResponse(request)
        response.fields.setArg(OPENID_NS, 'mode', 'cancel')
        webresponse = self.encode(response)
        self.failUnlessEqual(webresponse.code, server.HTTP_REDIRECT)
        self.failUnless(webresponse.headers.has_key('location'))
        location = webresponse.headers['location']
        query = cgi.parse_qs(urlparse(location)[4])
        self.failIf('openid.sig' in query, response.fields.toPostArgs())

    def test_assocReply(self):
        msg = Message(OPENID2_NS)
        msg.setArg(OPENID2_NS, 'session_type', 'no-encryption')
        request = server.AssociateRequest.fromMessage(msg)
        response = server.OpenIDResponse(request)
        response.fields = Message.fromOpenIDArgs({'assoc_handle': "every-zig"})
        webresponse = self.encode(response)
        body = """assoc_handle:every-zig
"""
        self.failUnlessEqual(webresponse.code, server.HTTP_OK)
        self.failUnlessEqual(webresponse.headers, {})
        self.failUnlessEqual(webresponse.body, body)

    def test_alreadySigned(self):
        self.response.fields.setArg(OPENID_NS, 'sig', 'priorSig==')
        self.failUnlessRaises(server.AlreadySigned, self.encode, self.response)

class TestCheckID(unittest.TestCase):
    def setUp(self):
        self.op_endpoint = 'http://endpoint.unittest/'
        self.store = memstore.MemoryStore()
        self.server = server.Server(self.store, self.op_endpoint)
        self.request = server.CheckIDRequest(
            identity = 'http://bambam.unittest/',
            trust_root = 'http://bar.unittest/',
            return_to = 'http://bar.unittest/999',
            immediate = False,
            op_endpoint = self.server.op_endpoint,
            )
        self.request.message = Message(OPENID2_NS)

    def test_trustRootInvalid(self):
        self.request.trust_root = "http://foo.unittest/17"
        self.request.return_to = "http://foo.unittest/39"
        self.failIf(self.request.trustRootValid())

    def test_trustRootValid(self):
        self.request.trust_root = "http://foo.unittest/"
        self.request.return_to = "http://foo.unittest/39"
        self.failUnless(self.request.trustRootValid())

    def test_malformedTrustRoot(self):
        self.request.trust_root = "invalid://trust*root/"
        self.request.return_to = "http://foo.unittest/39"
        sentinel = object()
        self.request.message = sentinel
        try:
            result = self.request.trustRootValid()
        except server.MalformedTrustRoot, why:
            self.failUnless(sentinel is why.openid_message)
        else:
            self.fail('Expected MalformedTrustRoot exception. Got %r'
                      % (result,))

    def test_trustRootValidNoReturnTo(self):
        request = server.CheckIDRequest(
            identity = 'http://bambam.unittest/',
            trust_root = 'http://bar.unittest/',
            return_to = None,
            immediate = False,
            op_endpoint = self.server.op_endpoint,
            )

        self.failUnless(request.trustRootValid())

    def test_returnToVerified_callsVerify(self):
        """Make sure that verifyReturnTo is calling the trustroot
        function verifyReturnTo
        """
        def withVerifyReturnTo(new_verify, callable):
            old_verify = server.verifyReturnTo
            try:
                server.verifyReturnTo = new_verify
                return callable()
            finally:
                server.verifyReturnTo = old_verify

        # Ensure that exceptions are passed through
        sentinel = Exception()
        def vrfyExc(trust_root, return_to):
            self.failUnlessEqual(self.request.trust_root, trust_root)
            self.failUnlessEqual(self.request.return_to, return_to)
            raise sentinel

        try:
            withVerifyReturnTo(vrfyExc, self.request.returnToVerified)
        except Exception, e:
            self.failUnless(e is sentinel, e)

        # Ensure that True and False are passed through unchanged
        def constVerify(val):
            def verify(trust_root, return_to):
                self.failUnlessEqual(self.request.trust_root, trust_root)
                self.failUnlessEqual(self.request.return_to, return_to)
                return val
            return verify

        for val in [True, False]:
            self.failUnlessEqual(
                val,
                withVerifyReturnTo(constVerify(val),
                                   self.request.returnToVerified))

    def _expectAnswer(self, answer, identity=None, claimed_id=None):
        expected_list = [
            ('mode', 'id_res'),
            ('return_to', self.request.return_to),
            ('op_endpoint', self.op_endpoint),
            ]
        if identity:
            expected_list.append(('identity', identity))
            if claimed_id:
                expected_list.append(('claimed_id', claimed_id))
            else:
                expected_list.append(('claimed_id', identity))

        for k, expected in expected_list:
            actual = answer.fields.getArg(OPENID_NS, k)
            self.failUnlessEqual(actual, expected, "%s: expected %s, got %s" % (k, expected, actual))

        self.failUnless(answer.fields.hasKey(OPENID_NS, 'response_nonce'))
        self.failUnless(answer.fields.getOpenIDNamespace() == OPENID2_NS)

        # One for nonce, one for ns
        self.failUnlessEqual(len(answer.fields.toPostArgs()),
                             len(expected_list) + 2,
                             answer.fields.toPostArgs())

    def test_answerAllow(self):
        """Check the fields specified by "Positive Assertions"

        including mode=id_res, identity, claimed_id, op_endpoint, return_to
        """
        answer = self.request.answer(True)
        self.failUnlessEqual(answer.request, self.request)
        self._expectAnswer(answer, self.request.identity)

    def test_answerAllowDelegatedIdentity(self):
        self.request.claimed_id = 'http://delegating.unittest/'
        answer = self.request.answer(True)
        self._expectAnswer(answer, self.request.identity,
                           self.request.claimed_id)

    def test_answerAllowDelegatedIdentity2(self):
        # This time with the identity argument explicitly passed in to
        # answer()
        self.request.claimed_id = 'http://delegating.unittest/'
        answer = self.request.answer(True, identity='http://bambam.unittest/')
        self._expectAnswer(answer, self.request.identity,
                           self.request.claimed_id)

    def test_answerAllowWithoutIdentityReally(self):
        self.request.identity = None
        answer = self.request.answer(True)
        self.failUnlessEqual(answer.request, self.request)
        self._expectAnswer(answer)

    def test_answerAllowAnonymousFail(self):
        self.request.identity = None
        # XXX - Check on this, I think this behavior is legal in OpenID 2.0?
        self.failUnlessRaises(
            ValueError, self.request.answer, True, identity="=V")

    def test_answerAllowWithIdentity(self):
        self.request.identity = IDENTIFIER_SELECT
        selected_id = 'http://anon.unittest/9861'
        answer = self.request.answer(True, identity=selected_id)
        self._expectAnswer(answer, selected_id)

    def test_answerAllowWithDelegatedIdentityOpenID2(self):
        """Answer an IDENTIFIER_SELECT case with a delegated identifier.
        """
        # claimed_id delegates to selected_id here.
        self.request.identity = IDENTIFIER_SELECT
        selected_id = 'http://anon.unittest/9861'
        claimed_id = 'http://monkeyhat.unittest/'
        answer = self.request.answer(True, identity=selected_id,
                                     claimed_id=claimed_id)
        self._expectAnswer(answer, selected_id, claimed_id)

    def test_answerAllowWithDelegatedIdentityOpenID1(self):
        """claimed_id parameter doesn't exist in OpenID 1.
        """
        self.request.message = Message(OPENID1_NS)
        # claimed_id delegates to selected_id here.
        self.request.identity = IDENTIFIER_SELECT
        selected_id = 'http://anon.unittest/9861'
        claimed_id = 'http://monkeyhat.unittest/'
        self.failUnlessRaises(server.VersionError,
                              self.request.answer, True,
                              identity=selected_id,
                              claimed_id=claimed_id)

    def test_answerAllowWithAnotherIdentity(self):
        # XXX - Check on this, I think this behavior is legal in OpenID 2.0?
        self.failUnlessRaises(ValueError, self.request.answer, True,
                              identity="http://pebbles.unittest/")

    def test_answerAllowWithIdentityNormalization(self):
        # The RP has sent us a non-normalized value for openid.identity,
        # and the library user is passing an explicit value for identity
        # to CheckIDRequest.answer.
        non_normalized = 'http://bambam.unittest'
        normalized = non_normalized + '/'

        self.request.identity = non_normalized
        self.request.claimed_id = non_normalized

        answer = self.request.answer(True, identity=normalized)

        # Expect the values that were sent in the request, even though
        # they're not normalized.
        self._expectAnswer(answer, identity=non_normalized,
                           claimed_id=non_normalized)

    def test_answerAllowNoIdentityOpenID1(self):
        self.request.message = Message(OPENID1_NS)
        self.request.identity = None
        self.failUnlessRaises(ValueError, self.request.answer, True,
                              identity=None)

    def test_answerAllowForgotEndpoint(self):
        self.request.op_endpoint = None
        self.failUnlessRaises(RuntimeError, self.request.answer, True)

    def test_checkIDWithNoIdentityOpenID1(self):
        msg = Message(OPENID1_NS)
        msg.setArg(OPENID_NS, 'return_to', 'bogus')
        msg.setArg(OPENID_NS, 'trust_root', 'bogus')
        msg.setArg(OPENID_NS, 'mode', 'checkid_setup')
        msg.setArg(OPENID_NS, 'assoc_handle', 'bogus')

        self.failUnlessRaises(server.ProtocolError,
                              server.CheckIDRequest.fromMessage,
                              msg, self.server)

    def test_fromMessageClaimedIDWithoutIdentityOpenID2(self):
        name = 'https://example.myopenid.com'

        msg = Message(OPENID2_NS)
        msg.setArg(OPENID_NS, 'mode', 'checkid_setup')
        msg.setArg(OPENID_NS, 'return_to', 'http://invalid:8000/rt')
        msg.setArg(OPENID_NS, 'claimed_id', name)

        self.failUnlessRaises(server.ProtocolError,
                              server.CheckIDRequest.fromMessage,
                              msg, self.server)

    def test_fromMessageIdentityWithoutClaimedIDOpenID2(self):
        name = 'https://example.myopenid.com'

        msg = Message(OPENID2_NS)
        msg.setArg(OPENID_NS, 'mode', 'checkid_setup')
        msg.setArg(OPENID_NS, 'return_to', 'http://invalid:8000/rt')
        msg.setArg(OPENID_NS, 'identity', name)

        self.failUnlessRaises(server.ProtocolError,
                              server.CheckIDRequest.fromMessage,
                              msg, self.server)

    def test_trustRootOpenID1(self):
        """Ignore openid.realm in OpenID 1"""
        msg = Message(OPENID1_NS)
        msg.setArg(OPENID_NS, 'mode', 'checkid_setup')
        msg.setArg(OPENID_NS, 'trust_root', 'http://real_trust_root/')
        msg.setArg(OPENID_NS, 'realm', 'http://fake_trust_root/')
        msg.setArg(OPENID_NS, 'return_to', 'http://real_trust_root/foo')
        msg.setArg(OPENID_NS, 'assoc_handle', 'bogus')
        msg.setArg(OPENID_NS, 'identity', 'george')

        result = server.CheckIDRequest.fromMessage(msg, self.server.op_endpoint)

        self.failUnless(result.trust_root == 'http://real_trust_root/')

    def test_trustRootOpenID2(self):
        """Ignore openid.trust_root in OpenID 2"""
        msg = Message(OPENID2_NS)
        msg.setArg(OPENID_NS, 'mode', 'checkid_setup')
        msg.setArg(OPENID_NS, 'realm', 'http://real_trust_root/')
        msg.setArg(OPENID_NS, 'trust_root', 'http://fake_trust_root/')
        msg.setArg(OPENID_NS, 'return_to', 'http://real_trust_root/foo')
        msg.setArg(OPENID_NS, 'assoc_handle', 'bogus')
        msg.setArg(OPENID_NS, 'identity', 'george')
        msg.setArg(OPENID_NS, 'claimed_id', 'george')

        result = server.CheckIDRequest.fromMessage(msg, self.server.op_endpoint)

        self.failUnless(result.trust_root == 'http://real_trust_root/')

    def test_answerAllowNoTrustRoot(self):
        self.request.trust_root = None
        answer = self.request.answer(True)
        self.failUnlessEqual(answer.request, self.request)
        self._expectAnswer(answer, self.request.identity)

    def test_fromMessageWithoutTrustRoot(self):
        msg = Message(OPENID2_NS)
        msg.setArg(OPENID_NS, 'mode', 'checkid_setup')
        msg.setArg(OPENID_NS, 'return_to', 'http://real_trust_root/foo')
        msg.setArg(OPENID_NS, 'assoc_handle', 'bogus')
        msg.setArg(OPENID_NS, 'identity', 'george')
        msg.setArg(OPENID_NS, 'claimed_id', 'george')

        result = server.CheckIDRequest.fromMessage(msg, self.server.op_endpoint)

        self.failUnlessEqual(result.trust_root, 'http://real_trust_root/foo')

    def test_fromMessageWithEmptyTrustRoot(self):
        return_to = u'http://someplace.invalid/?go=thing'
        msg = Message.fromPostArgs({
                u'openid.assoc_handle': u'{blah}{blah}{OZivdQ==}',
                u'openid.claimed_id': u'http://delegated.invalid/',
                u'openid.identity': u'http://op-local.example.com/',
                u'openid.mode': u'checkid_setup',
                u'openid.ns': u'http://openid.net/signon/1.0',
                u'openid.return_to': return_to,
                u'openid.trust_root': u''})

        result = server.CheckIDRequest.fromMessage(msg, self.server.op_endpoint)

        self.failUnlessEqual(result.trust_root, return_to)

    def test_fromMessageWithoutTrustRootOrReturnTo(self):
        msg = Message(OPENID2_NS)
        msg.setArg(OPENID_NS, 'mode', 'checkid_setup')
        msg.setArg(OPENID_NS, 'assoc_handle', 'bogus')
        msg.setArg(OPENID_NS, 'identity', 'george')
        msg.setArg(OPENID_NS, 'claimed_id', 'george')

        self.failUnlessRaises(server.ProtocolError,
                              server.CheckIDRequest.fromMessage,
                              msg, self.server.op_endpoint)

    def test_answerAllowNoEndpointOpenID1(self):
        """Test .allow() with an OpenID 1.x Message on a CheckIDRequest
        built without an op_endpoint parameter.
        """
        identity = 'http://bambam.unittest/'
        reqmessage = Message.fromOpenIDArgs({
            'identity': identity,
            'trust_root': 'http://bar.unittest/',
            'return_to': 'http://bar.unittest/999',
            })
        self.request = server.CheckIDRequest.fromMessage(reqmessage, None)
        answer = self.request.answer(True)

        expected_list = [
            ('mode', 'id_res'),
            ('return_to', self.request.return_to),
            ('identity', identity),
            ]

        for k, expected in expected_list:
            actual = answer.fields.getArg(OPENID_NS, k)
            self.failUnlessEqual(
                expected, actual,
                "%s: expected %s, got %s" % (k, expected, actual))

        self.failUnless(answer.fields.hasKey(OPENID_NS, 'response_nonce'))
        self.failUnlessEqual(answer.fields.getOpenIDNamespace(), OPENID1_NS)
        self.failUnless(answer.fields.namespaces.isImplicit(OPENID1_NS))

        # One for nonce (OpenID v1 namespace is implicit)
        self.failUnlessEqual(len(answer.fields.toPostArgs()),
                             len(expected_list) + 1,
                             answer.fields.toPostArgs())

    def test_answerImmediateDenyOpenID2(self):
        """Look for mode=setup_needed in checkid_immediate negative
        response in OpenID 2 case.

        See specification Responding to Authentication Requests /
        Negative Assertions / In Response to Immediate Requests.
        """
        self.request.mode = 'checkid_immediate'
        self.request.immediate = True
        self.request.claimed_id = 'http://claimed-id.test/'
        server_url = "http://setup-url.unittest/"
        # crappiting setup_url, you dirty my interface with your presence!
        answer = self.request.answer(False, server_url=server_url)
        self.failUnlessEqual(answer.request, self.request)
        self.failUnlessEqual(len(answer.fields.toPostArgs()), 3, answer.fields)
        self.failUnlessEqual(answer.fields.getOpenIDNamespace(), OPENID2_NS)
        self.failUnlessEqual(answer.fields.getArg(OPENID_NS, 'mode'),
                             'setup_needed')

        usu = answer.fields.getArg(OPENID_NS, 'user_setup_url')
        expected_substr = 'openid.claimed_id=http%3A%2F%2Fclaimed-id.test%2F'
        self.failUnless(expected_substr in usu, usu)

    def test_answerImmediateDenyOpenID1(self):
        """Look for user_setup_url in checkid_immediate negative
        response in OpenID 1 case."""
        self.request.message = Message(OPENID1_NS)
        self.request.mode = 'checkid_immediate'
        self.request.immediate = True
        server_url = "http://setup-url.unittest/"
        # crappiting setup_url, you dirty my interface with your presence!
        answer = self.request.answer(False, server_url=server_url)
        self.failUnlessEqual(answer.request, self.request)
        self.failUnlessEqual(len(answer.fields.toPostArgs()), 2, answer.fields)
        self.failUnlessEqual(answer.fields.getOpenIDNamespace(), OPENID1_NS)
        self.failUnless(answer.fields.namespaces.isImplicit(OPENID1_NS))
        self.failUnlessEqual(answer.fields.getArg(OPENID_NS, 'mode'), 'id_res')
        self.failUnless(answer.fields.getArg(
            OPENID_NS, 'user_setup_url', '').startswith(server_url))

    def test_answerSetupDeny(self):
        answer = self.request.answer(False)
        self.failUnlessEqual(answer.fields.getArgs(OPENID_NS), {
            'mode': 'cancel',
            })

    def test_encodeToURL(self):
        server_url = 'http://openid-server.unittest/'
        result = self.request.encodeToURL(server_url)

        # How to check?  How about a round-trip test.
        base, result_args = result.split('?', 1)
        result_args = dict(cgi.parse_qsl(result_args))
        message = Message.fromPostArgs(result_args)
        rebuilt_request = server.CheckIDRequest.fromMessage(message,
                                                            self.server.op_endpoint)
        # argh, lousy hack
        self.request.message = message
        self.failUnlessEqual(rebuilt_request.__dict__, self.request.__dict__)

    def test_getCancelURL(self):
        url = self.request.getCancelURL()
        rt, query_string = url.split('?')
        self.failUnlessEqual(self.request.return_to, rt)
        query = dict(cgi.parse_qsl(query_string))
        self.failUnlessEqual(query, {'openid.mode':'cancel',
                                     'openid.ns':OPENID2_NS})

    def test_getCancelURLimmed(self):
        self.request.mode = 'checkid_immediate'
        self.request.immediate = True
        self.failUnlessRaises(ValueError, self.request.getCancelURL)



class TestCheckIDExtension(unittest.TestCase):

    def setUp(self):
        self.op_endpoint = 'http://endpoint.unittest/ext'
        self.store = memstore.MemoryStore()
        self.server = server.Server(self.store, self.op_endpoint)
        self.request = server.CheckIDRequest(
            identity = 'http://bambam.unittest/',
            trust_root = 'http://bar.unittest/',
            return_to = 'http://bar.unittest/999',
            immediate = False,
            op_endpoint = self.server.op_endpoint,
            )
        self.request.message = Message(OPENID2_NS)
        self.response = server.OpenIDResponse(self.request)
        self.response.fields.setArg(OPENID_NS, 'mode', 'id_res')
        self.response.fields.setArg(OPENID_NS, 'blue', 'star')


    def test_addField(self):
        namespace = 'something:'
        self.response.fields.setArg(namespace, 'bright', 'potato')
        self.failUnlessEqual(self.response.fields.getArgs(OPENID_NS),
                             {'blue': 'star',
                              'mode': 'id_res',
                              })

        self.failUnlessEqual(self.response.fields.getArgs(namespace),
                             {'bright':'potato'})


    def test_addFields(self):
        namespace = 'mi5:'
        args =  {'tangy': 'suspenders',
                 'bravo': 'inclusion'}
        self.response.fields.updateArgs(namespace, args)
        self.failUnlessEqual(self.response.fields.getArgs(OPENID_NS),
                             {'blue': 'star',
                              'mode': 'id_res',
                              })
        self.failUnlessEqual(self.response.fields.getArgs(namespace), args)



class MockSignatory(object):
    isValid = True

    def __init__(self, assoc):
        self.assocs = [assoc]

    def verify(self, assoc_handle, message):
        assert message.hasKey(OPENID_NS, "sig")
        if (True, assoc_handle) in self.assocs:
            return self.isValid
        else:
            return False

    def getAssociation(self, assoc_handle, dumb):
        if (dumb, assoc_handle) in self.assocs:
            # This isn't a valid implementation for many uses of this
            # function, mind you.
            return True
        else:
            return None

    def invalidate(self, assoc_handle, dumb):
        if (dumb, assoc_handle) in self.assocs:
            self.assocs.remove((dumb, assoc_handle))


class TestCheckAuth(unittest.TestCase):
    def setUp(self):
        self.assoc_handle = 'mooooooooo'
        self.message = Message.fromPostArgs({
            'openid.sig': 'signarture',
            'one': 'alpha',
            'two': 'beta',
            })
        self.request = server.CheckAuthRequest(
            self.assoc_handle, self.message)

        self.signatory = MockSignatory((True, self.assoc_handle))

    def test_valid(self):
        r = self.request.answer(self.signatory)
        self.failUnlessEqual(r.fields.getArgs(OPENID_NS), {'is_valid': 'true'})
        self.failUnlessEqual(r.request, self.request)

    def test_invalid(self):
        self.signatory.isValid = False
        r = self.request.answer(self.signatory)
        self.failUnlessEqual(r.fields.getArgs(OPENID_NS),
                             {'is_valid': 'false'})

    def test_replay(self):
        """Don't validate the same response twice.

        From "Checking the Nonce"::

            When using "check_authentication", the OP MUST ensure that an
            assertion has not yet been accepted with the same value for
            "openid.response_nonce".

        In this implementation, the assoc_handle is only valid once.  And
        nonces are a signed component of the message, so they can't be used
        with another handle without breaking the sig.
        """
        r = self.request.answer(self.signatory)
        r = self.request.answer(self.signatory)
        self.failUnlessEqual(r.fields.getArgs(OPENID_NS),
                             {'is_valid': 'false'})

    def test_invalidatehandle(self):
        self.request.invalidate_handle = "bogusHandle"
        r = self.request.answer(self.signatory)
        self.failUnlessEqual(r.fields.getArgs(OPENID_NS),
                             {'is_valid': 'true',
                              'invalidate_handle': "bogusHandle"})
        self.failUnlessEqual(r.request, self.request)

    def test_invalidatehandleNo(self):
        assoc_handle = 'goodhandle'
        self.signatory.assocs.append((False, 'goodhandle'))
        self.request.invalidate_handle = assoc_handle
        r = self.request.answer(self.signatory)
        self.failUnlessEqual(r.fields.getArgs(OPENID_NS), {'is_valid': 'true'})


class TestAssociate(unittest.TestCase):
    # TODO: test DH with non-default values for modulus and gen.
    # (important to do because we actually had it broken for a while.)

    def setUp(self):
        self.request = server.AssociateRequest.fromMessage(
            Message.fromPostArgs({}))
        self.store = memstore.MemoryStore()
        self.signatory = server.Signatory(self.store)

    def test_dhSHA1(self):
        self.assoc = self.signatory.createAssociation(dumb=False, assoc_type='HMAC-SHA1')
        from openid.dh import DiffieHellman
        from openid.server.server import DiffieHellmanSHA1ServerSession
        consumer_dh = DiffieHellman.fromDefaults()
        cpub = consumer_dh.public
        server_dh = DiffieHellman.fromDefaults()
        session = DiffieHellmanSHA1ServerSession(server_dh, cpub)
        self.request = server.AssociateRequest(session, 'HMAC-SHA1')
        response = self.request.answer(self.assoc)
        rfg = lambda f: response.fields.getArg(OPENID_NS, f)
        self.failUnlessEqual(rfg("assoc_type"), "HMAC-SHA1")
        self.failUnlessEqual(rfg("assoc_handle"), self.assoc.handle)
        self.failIf(rfg("mac_key"))
        self.failUnlessEqual(rfg("session_type"), "DH-SHA1")
        self.failUnless(rfg("enc_mac_key"))
        self.failUnless(rfg("dh_server_public"))

        enc_key = rfg("enc_mac_key").decode('base64')
        spub = cryptutil.base64ToLong(rfg("dh_server_public"))
        secret = consumer_dh.xorSecret(spub, enc_key, cryptutil.sha1)
        self.failUnlessEqual(secret, self.assoc.secret)


    if not cryptutil.SHA256_AVAILABLE:
        warnings.warn("Not running SHA256 tests.")
    else:
        def test_dhSHA256(self):
            self.assoc = self.signatory.createAssociation(
                dumb=False, assoc_type='HMAC-SHA256')
            from openid.dh import DiffieHellman
            from openid.server.server import DiffieHellmanSHA256ServerSession
            consumer_dh = DiffieHellman.fromDefaults()
            cpub = consumer_dh.public
            server_dh = DiffieHellman.fromDefaults()
            session = DiffieHellmanSHA256ServerSession(server_dh, cpub)
            self.request = server.AssociateRequest(session, 'HMAC-SHA256')
            response = self.request.answer(self.assoc)
            rfg = lambda f: response.fields.getArg(OPENID_NS, f)
            self.failUnlessEqual(rfg("assoc_type"), "HMAC-SHA256")
            self.failUnlessEqual(rfg("assoc_handle"), self.assoc.handle)
            self.failIf(rfg("mac_key"))
            self.failUnlessEqual(rfg("session_type"), "DH-SHA256")
            self.failUnless(rfg("enc_mac_key"))
            self.failUnless(rfg("dh_server_public"))

            enc_key = rfg("enc_mac_key").decode('base64')
            spub = cryptutil.base64ToLong(rfg("dh_server_public"))
            secret = consumer_dh.xorSecret(spub, enc_key, cryptutil.sha256)
            self.failUnlessEqual(secret, self.assoc.secret)

        def test_protoError256(self):
            from openid.consumer.consumer import \
                 DiffieHellmanSHA256ConsumerSession

            s256_session = DiffieHellmanSHA256ConsumerSession()

            invalid_s256 = {'openid.assoc_type':'HMAC-SHA1',
                            'openid.session_type':'DH-SHA256',}
            invalid_s256.update(s256_session.getRequest())

            invalid_s256_2 = {'openid.assoc_type':'MONKEY-PIRATE',
                              'openid.session_type':'DH-SHA256',}
            invalid_s256_2.update(s256_session.getRequest())

            bad_request_argss = [
                invalid_s256,
                invalid_s256_2,
                ]

            for request_args in bad_request_argss:
                message = Message.fromPostArgs(request_args)
                self.failUnlessRaises(server.ProtocolError,
                                      server.AssociateRequest.fromMessage,
                                      message)

    def test_protoError(self):
        from openid.consumer.consumer import DiffieHellmanSHA1ConsumerSession

        s1_session = DiffieHellmanSHA1ConsumerSession()

        invalid_s1 = {'openid.assoc_type':'HMAC-SHA256',
                      'openid.session_type':'DH-SHA1',}
        invalid_s1.update(s1_session.getRequest())

        invalid_s1_2 = {'openid.assoc_type':'ROBOT-NINJA',
                      'openid.session_type':'DH-SHA1',}
        invalid_s1_2.update(s1_session.getRequest())

        bad_request_argss = [
            {'openid.assoc_type':'Wha?'},
            invalid_s1,
            invalid_s1_2,
            ]

        for request_args in bad_request_argss:
            message = Message.fromPostArgs(request_args)
            self.failUnlessRaises(server.ProtocolError,
                                  server.AssociateRequest.fromMessage,
                                  message)

    def test_protoErrorFields(self):

        contact = 'user@example.invalid'
        reference = 'Trac ticket number MAX_INT'
        error = 'poltergeist'

        openid1_args = {
            'openid.identitiy': 'invalid',
            'openid.mode': 'checkid_setup',
            }

        openid2_args = dict(openid1_args)
        openid2_args.update({'openid.ns': OPENID2_NS})

        # Check presence of optional fields in both protocol versions

        openid1_msg = Message.fromPostArgs(openid1_args)
        p = server.ProtocolError(openid1_msg, error,
                                 contact=contact, reference=reference)
        reply = p.toMessage()

        self.failUnlessEqual(reply.getArg(OPENID_NS, 'reference'), reference)
        self.failUnlessEqual(reply.getArg(OPENID_NS, 'contact'), contact)

        openid2_msg = Message.fromPostArgs(openid2_args)
        p = server.ProtocolError(openid2_msg, error,
                                 contact=contact, reference=reference)
        reply = p.toMessage()

        self.failUnlessEqual(reply.getArg(OPENID_NS, 'reference'), reference)
        self.failUnlessEqual(reply.getArg(OPENID_NS, 'contact'), contact)

    def failUnlessExpiresInMatches(self, msg, expected_expires_in):
        expires_in_str = msg.getArg(OPENID_NS, 'expires_in', no_default)
        expires_in = int(expires_in_str)

        # Slop is necessary because the tests can sometimes get run
        # right on a second boundary
        slop = 1 # second
        difference = expected_expires_in - expires_in

        error_message = ('"expires_in" value not within %s of expected: '
                         'expected=%s, actual=%s' %
                         (slop, expected_expires_in, expires_in))
        self.failUnless(0 <= difference <= slop, error_message)

    def test_plaintext(self):
        self.assoc = self.signatory.createAssociation(dumb=False, assoc_type='HMAC-SHA1')
        response = self.request.answer(self.assoc)
        rfg = lambda f: response.fields.getArg(OPENID_NS, f)

        self.failUnlessEqual(rfg("assoc_type"), "HMAC-SHA1")
        self.failUnlessEqual(rfg("assoc_handle"), self.assoc.handle)

        self.failUnlessExpiresInMatches(
            response.fields, self.signatory.SECRET_LIFETIME)

        self.failUnlessEqual(
            rfg("mac_key"), oidutil.toBase64(self.assoc.secret))
        self.failIf(rfg("session_type"))
        self.failIf(rfg("enc_mac_key"))
        self.failIf(rfg("dh_server_public"))

    def test_plaintext_v2(self):
        # The main difference between this and the v1 test is that
        # session_type is always returned in v2.
        args = {
            'openid.ns': OPENID2_NS,
            'openid.mode': 'associate',
            'openid.assoc_type': 'HMAC-SHA1',
            'openid.session_type': 'no-encryption',
            }
        self.request = server.AssociateRequest.fromMessage(
            Message.fromPostArgs(args))

        self.failIf(self.request.message.isOpenID1())

        self.assoc = self.signatory.createAssociation(
            dumb=False, assoc_type='HMAC-SHA1')
        response = self.request.answer(self.assoc)
        rfg = lambda f: response.fields.getArg(OPENID_NS, f)

        self.failUnlessEqual(rfg("assoc_type"), "HMAC-SHA1")
        self.failUnlessEqual(rfg("assoc_handle"), self.assoc.handle)

        self.failUnlessExpiresInMatches(
            response.fields, self.signatory.SECRET_LIFETIME)

        self.failUnlessEqual(
            rfg("mac_key"), oidutil.toBase64(self.assoc.secret))

        self.failUnlessEqual(rfg("session_type"), "no-encryption")
        self.failIf(rfg("enc_mac_key"))
        self.failIf(rfg("dh_server_public"))

    def test_plaintext256(self):
        self.assoc = self.signatory.createAssociation(dumb=False, assoc_type='HMAC-SHA256')
        response = self.request.answer(self.assoc)
        rfg = lambda f: response.fields.getArg(OPENID_NS, f)

        self.failUnlessEqual(rfg("assoc_type"), "HMAC-SHA1")
        self.failUnlessEqual(rfg("assoc_handle"), self.assoc.handle)

        self.failUnlessExpiresInMatches(
            response.fields, self.signatory.SECRET_LIFETIME)

        self.failUnlessEqual(
            rfg("mac_key"), oidutil.toBase64(self.assoc.secret))
        self.failIf(rfg("session_type"))
        self.failIf(rfg("enc_mac_key"))
        self.failIf(rfg("dh_server_public"))

    def test_unsupportedPrefer(self):
        allowed_assoc = 'COLD-PET-RAT'
        allowed_sess = 'FROG-BONES'
        message = 'This is a unit test'

        # Set an OpenID 2 message so answerUnsupported doesn't raise
        # ProtocolError.
        self.request.message = Message(OPENID2_NS)

        response = self.request.answerUnsupported(
            message=message,
            preferred_session_type=allowed_sess,
            preferred_association_type=allowed_assoc,
            )
        rfg = lambda f: response.fields.getArg(OPENID_NS, f)
        self.failUnlessEqual(rfg('error_code'), 'unsupported-type')
        self.failUnlessEqual(rfg('assoc_type'), allowed_assoc)
        self.failUnlessEqual(rfg('error'), message)
        self.failUnlessEqual(rfg('session_type'), allowed_sess)

    def test_unsupported(self):
        message = 'This is a unit test'

        # Set an OpenID 2 message so answerUnsupported doesn't raise
        # ProtocolError.
        self.request.message = Message(OPENID2_NS)

        response = self.request.answerUnsupported(message)
        rfg = lambda f: response.fields.getArg(OPENID_NS, f)
        self.failUnlessEqual(rfg('error_code'), 'unsupported-type')
        self.failUnlessEqual(rfg('assoc_type'), None)
        self.failUnlessEqual(rfg('error'), message)
        self.failUnlessEqual(rfg('session_type'), None)

class Counter(object):
    def __init__(self):
        self.count = 0

    def inc(self):
        self.count += 1

class TestServer(unittest.TestCase, CatchLogs):
    def setUp(self):
        self.store = memstore.MemoryStore()
        self.server = server.Server(self.store, "http://server.unittest/endpt")
        CatchLogs.setUp(self)

    def test_dispatch(self):
        monkeycalled = Counter()
        def monkeyDo(request):
            monkeycalled.inc()
            r = server.OpenIDResponse(request)
            return r
        self.server.openid_monkeymode = monkeyDo
        request = server.OpenIDRequest()
        request.mode = "monkeymode"
        request.namespace = OPENID1_NS
        webresult = self.server.handleRequest(request)
        self.failUnlessEqual(monkeycalled.count, 1)

    def test_associate(self):
        request = server.AssociateRequest.fromMessage(Message.fromPostArgs({}))
        response = self.server.openid_associate(request)
        self.failUnless(response.fields.hasKey(OPENID_NS, "assoc_handle"),
                        "No assoc_handle here: %s" % (response.fields,))

    def test_associate2(self):
        """Associate when the server has no allowed association types

        Gives back an error with error_code and no fallback session or
        assoc types."""
        self.server.negotiator.setAllowedTypes([])

        # Set an OpenID 2 message so answerUnsupported doesn't raise
        # ProtocolError.
        msg = Message.fromPostArgs({
            'openid.ns': OPENID2_NS,
            'openid.session_type': 'no-encryption',
            })

        request = server.AssociateRequest.fromMessage(msg)

        response = self.server.openid_associate(request)
        self.failUnless(response.fields.hasKey(OPENID_NS, "error"))
        self.failUnless(response.fields.hasKey(OPENID_NS, "error_code"))
        self.failIf(response.fields.hasKey(OPENID_NS, "assoc_handle"))
        self.failIf(response.fields.hasKey(OPENID_NS, "assoc_type"))
        self.failIf(response.fields.hasKey(OPENID_NS, "session_type"))

    def test_associate3(self):
        """Request an assoc type that is not supported when there are
        supported types.

        Should give back an error message with a fallback type.
        """
        self.server.negotiator.setAllowedTypes([('HMAC-SHA256', 'DH-SHA256')])

        msg = Message.fromPostArgs({
            'openid.ns': OPENID2_NS,
            'openid.session_type': 'no-encryption',
            })

        request = server.AssociateRequest.fromMessage(msg)
        response = self.server.openid_associate(request)

        self.failUnless(response.fields.hasKey(OPENID_NS, "error"))
        self.failUnless(response.fields.hasKey(OPENID_NS, "error_code"))
        self.failIf(response.fields.hasKey(OPENID_NS, "assoc_handle"))
        self.failUnlessEqual(response.fields.getArg(OPENID_NS, "assoc_type"),
                             'HMAC-SHA256')
        self.failUnlessEqual(response.fields.getArg(OPENID_NS, "session_type"),
                             'DH-SHA256')

    if not cryptutil.SHA256_AVAILABLE:
        warnings.warn("Not running SHA256 tests.")
    else:
        def test_associate4(self):
            """DH-SHA256 association session"""
            self.server.negotiator.setAllowedTypes(
                [('HMAC-SHA256', 'DH-SHA256')])
            query = {
                'openid.dh_consumer_public':
                'ALZgnx8N5Lgd7pCj8K86T/DDMFjJXSss1SKoLmxE72kJTzOtG6I2PaYrHX'
                'xku4jMQWSsGfLJxwCZ6280uYjUST/9NWmuAfcrBfmDHIBc3H8xh6RBnlXJ'
                '1WxJY3jHd5k1/ZReyRZOxZTKdF/dnIqwF8ZXUwI6peV0TyS/K1fOfF/s',
                'openid.assoc_type': 'HMAC-SHA256',
                'openid.session_type': 'DH-SHA256',
                }
            message = Message.fromPostArgs(query)
            request = server.AssociateRequest.fromMessage(message)
            response = self.server.openid_associate(request)
            self.failUnless(response.fields.hasKey(OPENID_NS, "assoc_handle"))

    def test_missingSessionTypeOpenID2(self):
        """Make sure session_type is required in OpenID 2"""
        msg = Message.fromPostArgs({
            'openid.ns': OPENID2_NS,
            })

        self.assertRaises(server.ProtocolError,
                          server.AssociateRequest.fromMessage, msg)

    def test_checkAuth(self):
        request = server.CheckAuthRequest('arrrrrf', '0x3999', [])
        response = self.server.openid_check_authentication(request)
        self.failUnless(response.fields.hasKey(OPENID_NS, "is_valid"))

class TestSignatory(unittest.TestCase, CatchLogs):
    def setUp(self):
        self.store = memstore.MemoryStore()
        self.signatory = server.Signatory(self.store)
        self._dumb_key = self.signatory._dumb_key
        self._normal_key = self.signatory._normal_key
        CatchLogs.setUp(self)

    def test_sign(self):
        request = server.OpenIDRequest()
        assoc_handle = '{assoc}{lookatme}'
        self.store.storeAssociation(
            self._normal_key,
            association.Association.fromExpiresIn(60, assoc_handle,
                                                  'sekrit', 'HMAC-SHA1'))
        request.assoc_handle = assoc_handle
        request.namespace = OPENID1_NS
        response = server.OpenIDResponse(request)
        response.fields = Message.fromOpenIDArgs({
            'foo': 'amsigned',
            'bar': 'notsigned',
            'azu': 'alsosigned',
            })
        sresponse = self.signatory.sign(response)
        self.failUnlessEqual(
            sresponse.fields.getArg(OPENID_NS, 'assoc_handle'),
            assoc_handle)
        self.failUnlessEqual(sresponse.fields.getArg(OPENID_NS, 'signed'),
                             'assoc_handle,azu,bar,foo,signed')
        self.failUnless(sresponse.fields.getArg(OPENID_NS, 'sig'))
        self.failIf(self.messages, self.messages)

    def test_signDumb(self):
        request = server.OpenIDRequest()
        request.assoc_handle = None
        request.namespace = OPENID2_NS
        response = server.OpenIDResponse(request)
        response.fields = Message.fromOpenIDArgs({
            'foo': 'amsigned',
            'bar': 'notsigned',
            'azu': 'alsosigned',
            'ns':OPENID2_NS,
            })
        sresponse = self.signatory.sign(response)
        assoc_handle = sresponse.fields.getArg(OPENID_NS, 'assoc_handle')
        self.failUnless(assoc_handle)
        assoc = self.signatory.getAssociation(assoc_handle, dumb=True)
        self.failUnless(assoc)
        self.failUnlessEqual(sresponse.fields.getArg(OPENID_NS, 'signed'),
                             'assoc_handle,azu,bar,foo,ns,signed')
        self.failUnless(sresponse.fields.getArg(OPENID_NS, 'sig'))
        self.failIf(self.messages, self.messages)

    def test_signExpired(self):
        """Sign a response to a message with an expired handle (using invalidate_handle).

        From "Verifying with an Association"::

            If an authentication request included an association handle for an
            association between the OP and the Relying party, and the OP no
            longer wishes to use that handle (because it has expired or the
            secret has been compromised, for instance), the OP will send a
            response that must be verified directly with the OP, as specified
            in Section 11.3.2. In that instance, the OP will include the field
            "openid.invalidate_handle" set to the association handle that the
            Relying Party included with the original request.
        """
        request = server.OpenIDRequest()
        request.namespace = OPENID2_NS
        assoc_handle = '{assoc}{lookatme}'
        self.store.storeAssociation(
            self._normal_key,
            association.Association.fromExpiresIn(-10, assoc_handle,
                                                  'sekrit', 'HMAC-SHA1'))
        self.failUnless(self.store.getAssociation(self._normal_key, assoc_handle))

        request.assoc_handle = assoc_handle
        response = server.OpenIDResponse(request)
        response.fields = Message.fromOpenIDArgs({
            'foo': 'amsigned',
            'bar': 'notsigned',
            'azu': 'alsosigned',
            })
        sresponse = self.signatory.sign(response)

        new_assoc_handle = sresponse.fields.getArg(OPENID_NS, 'assoc_handle')
        self.failUnless(new_assoc_handle)
        self.failIfEqual(new_assoc_handle, assoc_handle)

        self.failUnlessEqual(
            sresponse.fields.getArg(OPENID_NS, 'invalidate_handle'),
            assoc_handle)

        self.failUnlessEqual(sresponse.fields.getArg(OPENID_NS, 'signed'),
                             'assoc_handle,azu,bar,foo,invalidate_handle,signed')
        self.failUnless(sresponse.fields.getArg(OPENID_NS, 'sig'))

        # make sure the expired association is gone
        self.failIf(self.store.getAssociation(self._normal_key, assoc_handle),
                    "expired association is still retrievable.")

        # make sure the new key is a dumb mode association
        self.failUnless(self.store.getAssociation(self._dumb_key, new_assoc_handle))
        self.failIf(self.store.getAssociation(self._normal_key, new_assoc_handle))
        self.failUnless(self.messages)


    def test_signInvalidHandle(self):
        request = server.OpenIDRequest()
        request.namespace = OPENID2_NS
        assoc_handle = '{bogus-assoc}{notvalid}'

        request.assoc_handle = assoc_handle
        response = server.OpenIDResponse(request)
        response.fields = Message.fromOpenIDArgs({
            'foo': 'amsigned',
            'bar': 'notsigned',
            'azu': 'alsosigned',
            })
        sresponse = self.signatory.sign(response)

        new_assoc_handle = sresponse.fields.getArg(OPENID_NS, 'assoc_handle')
        self.failUnless(new_assoc_handle)
        self.failIfEqual(new_assoc_handle, assoc_handle)

        self.failUnlessEqual(
            sresponse.fields.getArg(OPENID_NS, 'invalidate_handle'),
            assoc_handle)

        self.failUnlessEqual(
            sresponse.fields.getArg(OPENID_NS, 'signed'), 'assoc_handle,azu,bar,foo,invalidate_handle,signed')
        self.failUnless(sresponse.fields.getArg(OPENID_NS, 'sig'))

        # make sure the new key is a dumb mode association
        self.failUnless(self.store.getAssociation(self._dumb_key, new_assoc_handle))
        self.failIf(self.store.getAssociation(self._normal_key, new_assoc_handle))
        self.failIf(self.messages, self.messages)


    def test_verify(self):
        assoc_handle = '{vroom}{zoom}'
        assoc = association.Association.fromExpiresIn(
            60, assoc_handle, 'sekrit', 'HMAC-SHA1')

        self.store.storeAssociation(self._dumb_key, assoc)

        signed = Message.fromPostArgs({
            'openid.foo': 'bar',
            'openid.apple': 'orange',
            'openid.assoc_handle': assoc_handle,
            'openid.signed': 'apple,assoc_handle,foo,signed',
            'openid.sig': 'uXoT1qm62/BB09Xbj98TQ8mlBco=',
            })

        verified = self.signatory.verify(assoc_handle, signed)
        self.failIf(self.messages, self.messages)
        self.failUnless(verified)


    def test_verifyBadSig(self):
        assoc_handle = '{vroom}{zoom}'
        assoc = association.Association.fromExpiresIn(
            60, assoc_handle, 'sekrit', 'HMAC-SHA1')

        self.store.storeAssociation(self._dumb_key, assoc)

        signed = Message.fromPostArgs({
            'openid.foo': 'bar',
            'openid.apple': 'orange',
            'openid.assoc_handle': assoc_handle,
            'openid.signed': 'apple,assoc_handle,foo,signed',
            'openid.sig': 'uXoT1qm62/BB09Xbj98TQ8mlBco='.encode('rot13'),
            })

        verified = self.signatory.verify(assoc_handle, signed)
        self.failIf(self.messages, self.messages)
        self.failIf(verified)

    def test_verifyBadHandle(self):
        assoc_handle = '{vroom}{zoom}'
        signed = Message.fromPostArgs({
            'foo': 'bar',
            'apple': 'orange',
            'openid.sig': "Ylu0KcIR7PvNegB/K41KpnRgJl0=",
            })

        verified = self.signatory.verify(assoc_handle, signed)
        self.failIf(verified)
        self.failUnless(self.messages)


    def test_verifyAssocMismatch(self):
        """Attempt to validate sign-all message with a signed-list assoc."""
        assoc_handle = '{vroom}{zoom}'
        assoc = association.Association.fromExpiresIn(
            60, assoc_handle, 'sekrit', 'HMAC-SHA1')

        self.store.storeAssociation(self._dumb_key, assoc)

        signed = Message.fromPostArgs({
            'foo': 'bar',
            'apple': 'orange',
            'openid.sig': "d71xlHtqnq98DonoSgoK/nD+QRM=",
            })

        verified = self.signatory.verify(assoc_handle, signed)
        self.failIf(verified)
        self.failUnless(self.messages)

    def test_getAssoc(self):
        assoc_handle = self.makeAssoc(dumb=True)
        assoc = self.signatory.getAssociation(assoc_handle, True)
        self.failUnless(assoc)
        self.failUnlessEqual(assoc.handle, assoc_handle)
        self.failIf(self.messages, self.messages)

    def test_getAssocExpired(self):
	assoc_handle = self.makeAssoc(dumb=True, lifetime=-10)
        assoc = self.signatory.getAssociation(assoc_handle, True)
        self.failIf(assoc, assoc)
	self.failUnless(self.messages)

    def test_getAssocInvalid(self):
        ah = 'no-such-handle'
        self.failUnlessEqual(
            self.signatory.getAssociation(ah, dumb=False), None)
        self.failIf(self.messages, self.messages)

    def test_getAssocDumbVsNormal(self):
        """getAssociation(dumb=False) cannot get a dumb assoc"""
        assoc_handle = self.makeAssoc(dumb=True)
        self.failUnlessEqual(
            self.signatory.getAssociation(assoc_handle, dumb=False), None)
        self.failIf(self.messages, self.messages)

    def test_getAssocNormalVsDumb(self):
        """getAssociation(dumb=True) cannot get a shared assoc

        From "Verifying Directly with the OpenID Provider"::

            An OP MUST NOT verify signatures for associations that have shared
            MAC keys.
        """
        assoc_handle = self.makeAssoc(dumb=False)
        self.failUnlessEqual(
            self.signatory.getAssociation(assoc_handle, dumb=True), None)
        self.failIf(self.messages, self.messages)

    def test_createAssociation(self):
        assoc = self.signatory.createAssociation(dumb=False)
        self.failUnless(self.signatory.getAssociation(assoc.handle, dumb=False))
        self.failIf(self.messages, self.messages)

    def makeAssoc(self, dumb, lifetime=60):
        assoc_handle = '{bling}'
        assoc = association.Association.fromExpiresIn(lifetime, assoc_handle,
                                                      'sekrit', 'HMAC-SHA1')

        self.store.storeAssociation((dumb and self._dumb_key) or self._normal_key, assoc)
        return assoc_handle

    def test_invalidate(self):
        assoc_handle = '-squash-'
        assoc = association.Association.fromExpiresIn(60, assoc_handle,
                                                      'sekrit', 'HMAC-SHA1')

        self.store.storeAssociation(self._dumb_key, assoc)
        assoc = self.signatory.getAssociation(assoc_handle, dumb=True)
        self.failUnless(assoc)
        assoc = self.signatory.getAssociation(assoc_handle, dumb=True)
        self.failUnless(assoc)
        self.signatory.invalidate(assoc_handle, dumb=True)
        assoc = self.signatory.getAssociation(assoc_handle, dumb=True)
        self.failIf(assoc)
        self.failIf(self.messages, self.messages)



if __name__ == '__main__':
    unittest.main()

########NEW FILE########
__FILENAME__ = test_services
import unittest

from openid.yadis import services
from openid.yadis.discover import DiscoveryFailure, DiscoveryResult


class TestGetServiceEndpoints(unittest.TestCase):
    def setUp(self):
        self.orig_discover = services.discover
        services.discover = self.discover

    def tearDown(self):
        services.discover = self.orig_discover

    def discover(self, input_url):
        result = DiscoveryResult(input_url)
        result.response_text = "This is not XRDS text."
        return result

    def test_catchXRDSError(self):
        self.failUnlessRaises(DiscoveryFailure,
                              services.getServiceEndpoints,
                              "http://example.invalid/sometest")

########NEW FILE########
__FILENAME__ = test_sreg
from openid.extensions import sreg
from openid.message import NamespaceMap, Message, registerNamespaceAlias
from openid.server.server import OpenIDRequest, OpenIDResponse

import unittest

class SRegURITest(unittest.TestCase):
    def test_is11(self):
        self.failUnlessEqual(sreg.ns_uri_1_1, sreg.ns_uri)

class CheckFieldNameTest(unittest.TestCase):
    def test_goodNamePasses(self):
        for field_name in sreg.data_fields:
            sreg.checkFieldName(field_name)

    def test_badNameFails(self):
        self.failUnlessRaises(ValueError, sreg.checkFieldName, 'INVALID')

    def test_badTypeFails(self):
        self.failUnlessRaises(ValueError, sreg.checkFieldName, None)

# For supportsSReg test
class FakeEndpoint(object):
    def __init__(self, supported):
        self.supported = supported
        self.checked_uris = []

    def usesExtension(self, namespace_uri):
        self.checked_uris.append(namespace_uri)
        return namespace_uri in self.supported

class SupportsSRegTest(unittest.TestCase):
    def test_unsupported(self):
        endpoint = FakeEndpoint([])
        self.failIf(sreg.supportsSReg(endpoint))
        self.failUnlessEqual([sreg.ns_uri_1_1, sreg.ns_uri_1_0],
                             endpoint.checked_uris)

    def test_supported_1_1(self):
        endpoint = FakeEndpoint([sreg.ns_uri_1_1])
        self.failUnless(sreg.supportsSReg(endpoint))
        self.failUnlessEqual([sreg.ns_uri_1_1], endpoint.checked_uris)

    def test_supported_1_0(self):
        endpoint = FakeEndpoint([sreg.ns_uri_1_0])
        self.failUnless(sreg.supportsSReg(endpoint))
        self.failUnlessEqual([sreg.ns_uri_1_1, sreg.ns_uri_1_0],
                             endpoint.checked_uris)

class FakeMessage(object):
    def __init__(self):
        self.openid1 = False
        self.namespaces = NamespaceMap()

    def isOpenID1(self):
        return self.openid1

class GetNSTest(unittest.TestCase):
    def setUp(self):
        self.msg = FakeMessage()

    def test_openID2Empty(self):
        ns_uri = sreg.getSRegNS(self.msg)
        self.failUnlessEqual(self.msg.namespaces.getAlias(ns_uri), 'sreg')
        self.failUnlessEqual(sreg.ns_uri, ns_uri)

    def test_openID1Empty(self):
        self.msg.openid1 = True
        ns_uri = sreg.getSRegNS(self.msg)
        self.failUnlessEqual(self.msg.namespaces.getAlias(ns_uri), 'sreg')
        self.failUnlessEqual(sreg.ns_uri, ns_uri)

    def test_openID1Defined_1_0(self):
        self.msg.openid1 = True
        self.msg.namespaces.add(sreg.ns_uri_1_0)
        ns_uri = sreg.getSRegNS(self.msg)
        self.failUnlessEqual(sreg.ns_uri_1_0, ns_uri)

    def test_openID1Defined_1_0_overrideAlias(self):
        for openid_version in [True, False]:
            for sreg_version in [sreg.ns_uri_1_0, sreg.ns_uri_1_1]:
                for alias in ['sreg', 'bogus']:
                    self.setUp()

                    self.msg.openid1 = openid_version
                    self.msg.namespaces.addAlias(sreg_version, alias)
                    ns_uri = sreg.getSRegNS(self.msg)
                    self.failUnlessEqual(self.msg.namespaces.getAlias(ns_uri), alias)
                    self.failUnlessEqual(sreg_version, ns_uri)

    def test_openID1DefinedBadly(self):
        self.msg.openid1 = True
        self.msg.namespaces.addAlias('http://invalid/', 'sreg')
        self.failUnlessRaises(sreg.SRegNamespaceError,
                              sreg.getSRegNS, self.msg)

    def test_openID2DefinedBadly(self):
        self.msg.openid1 = False
        self.msg.namespaces.addAlias('http://invalid/', 'sreg')
        self.failUnlessRaises(sreg.SRegNamespaceError,
                              sreg.getSRegNS, self.msg)

    def test_openID2Defined_1_0(self):
        self.msg.namespaces.add(sreg.ns_uri_1_0)
        ns_uri = sreg.getSRegNS(self.msg)
        self.failUnlessEqual(sreg.ns_uri_1_0, ns_uri)

    def test_openID1_sregNSfromArgs(self):
        args = {
            'sreg.optional': 'nickname',
            'sreg.required': 'dob',
            }

        m = Message.fromOpenIDArgs(args)

        self.failUnless(m.getArg(sreg.ns_uri_1_1, 'optional') == 'nickname')
        self.failUnless(m.getArg(sreg.ns_uri_1_1, 'required') == 'dob')

class SRegRequestTest(unittest.TestCase):
    def test_constructEmpty(self):
        req = sreg.SRegRequest()
        self.failUnlessEqual([], req.optional)
        self.failUnlessEqual([], req.required)
        self.failUnlessEqual(None, req.policy_url)
        self.failUnlessEqual(sreg.ns_uri, req.ns_uri)

    def test_constructFields(self):
        req = sreg.SRegRequest(
            ['nickname'],
            ['gender'],
            'http://policy',
            'http://sreg.ns_uri')
        self.failUnlessEqual(['gender'], req.optional)
        self.failUnlessEqual(['nickname'], req.required)
        self.failUnlessEqual('http://policy', req.policy_url)
        self.failUnlessEqual('http://sreg.ns_uri', req.ns_uri)

    def test_constructBadFields(self):
        self.failUnlessRaises(
            ValueError,
            sreg.SRegRequest, ['elvis'])

    def test_fromOpenIDRequest(self):
        args = {}
        ns_sentinel = object()
        args_sentinel = object()

        class FakeMessage(object):
            copied = False

            def __init__(self):
                self.message = Message()

            def getArgs(msg_self, ns_uri):
                self.failUnlessEqual(ns_sentinel, ns_uri)
                return args_sentinel

            def copy(msg_self):
                msg_self.copied = True
                return msg_self

        class TestingReq(sreg.SRegRequest):
            def _getSRegNS(req_self, unused):
                return ns_sentinel

            def parseExtensionArgs(req_self, args):
                self.failUnlessEqual(args_sentinel, args)

        openid_req = OpenIDRequest()

        msg = FakeMessage()
        openid_req.message = msg

        req = TestingReq.fromOpenIDRequest(openid_req)
        self.failUnless(type(req) is TestingReq)
        self.failUnless(msg.copied)

    def test_parseExtensionArgs_empty(self):
        req = sreg.SRegRequest()
        results = req.parseExtensionArgs({})
        self.failUnlessEqual(None, results)

    def test_parseExtensionArgs_extraIgnored(self):
        req = sreg.SRegRequest()
        req.parseExtensionArgs({'janrain':'inc'})

    def test_parseExtensionArgs_nonStrict(self):
        req = sreg.SRegRequest()
        req.parseExtensionArgs({'required':'beans'})
        self.failUnlessEqual([], req.required)

    def test_parseExtensionArgs_strict(self):
        req = sreg.SRegRequest()
        self.failUnlessRaises(
            ValueError,
            req.parseExtensionArgs, {'required':'beans'}, strict=True)

    def test_parseExtensionArgs_policy(self):
        req = sreg.SRegRequest()
        req.parseExtensionArgs({'policy_url':'http://policy'}, strict=True)
        self.failUnlessEqual('http://policy', req.policy_url)

    def test_parseExtensionArgs_requiredEmpty(self):
        req = sreg.SRegRequest()
        req.parseExtensionArgs({'required':''}, strict=True)
        self.failUnlessEqual([], req.required)

    def test_parseExtensionArgs_optionalEmpty(self):
        req = sreg.SRegRequest()
        req.parseExtensionArgs({'optional':''}, strict=True)
        self.failUnlessEqual([], req.optional)

    def test_parseExtensionArgs_optionalSingle(self):
        req = sreg.SRegRequest()
        req.parseExtensionArgs({'optional':'nickname'}, strict=True)
        self.failUnlessEqual(['nickname'], req.optional)

    def test_parseExtensionArgs_optionalList(self):
        req = sreg.SRegRequest()
        req.parseExtensionArgs({'optional':'nickname,email'}, strict=True)
        self.failUnlessEqual(['nickname','email'], req.optional)

    def test_parseExtensionArgs_optionalListBadNonStrict(self):
        req = sreg.SRegRequest()
        req.parseExtensionArgs({'optional':'nickname,email,beer'})
        self.failUnlessEqual(['nickname','email'], req.optional)

    def test_parseExtensionArgs_optionalListBadStrict(self):
        req = sreg.SRegRequest()
        self.failUnlessRaises(
            ValueError,
            req.parseExtensionArgs, {'optional':'nickname,email,beer'},
            strict=True)

    def test_parseExtensionArgs_bothNonStrict(self):
        req = sreg.SRegRequest()
        req.parseExtensionArgs({'optional':'nickname',
                                'required':'nickname'})
        self.failUnlessEqual([], req.optional)
        self.failUnlessEqual(['nickname'], req.required)

    def test_parseExtensionArgs_bothStrict(self):
        req = sreg.SRegRequest()
        self.failUnlessRaises(
            ValueError,
            req.parseExtensionArgs,
            {'optional':'nickname',
             'required':'nickname'},
            strict=True)

    def test_parseExtensionArgs_bothList(self):
        req = sreg.SRegRequest()
        req.parseExtensionArgs({'optional':'nickname,email',
                                'required':'country,postcode'}, strict=True)
        self.failUnlessEqual(['nickname','email'], req.optional)
        self.failUnlessEqual(['country','postcode'], req.required)

    def test_allRequestedFields(self):
        req = sreg.SRegRequest()
        self.failUnlessEqual([], req.allRequestedFields())
        req.requestField('nickname')
        self.failUnlessEqual(['nickname'], req.allRequestedFields())
        req.requestField('gender', required=True)
        requested = req.allRequestedFields()
        requested.sort()
        self.failUnlessEqual(['gender', 'nickname'], requested)

    def test_wereFieldsRequested(self):
        req = sreg.SRegRequest()
        self.failIf(req.wereFieldsRequested())
        req.requestField('gender')
        self.failUnless(req.wereFieldsRequested())

    def test_contains(self):
        req = sreg.SRegRequest()
        for field_name in sreg.data_fields:
            self.failIf(field_name in req)

        self.failIf('something else' in req)

        req.requestField('nickname')
        for field_name in sreg.data_fields:
            if field_name == 'nickname':
                self.failUnless(field_name in req)
            else:
                self.failIf(field_name in req)

    def test_requestField_bogus(self):
        req = sreg.SRegRequest()
        self.failUnlessRaises(
            ValueError,
            req.requestField, 'something else')

        self.failUnlessRaises(
            ValueError,
            req.requestField, 'something else', strict=True)

    def test_requestField(self):
        # Add all of the fields, one at a time
        req = sreg.SRegRequest()
        fields = list(sreg.data_fields)
        for field_name in fields:
            req.requestField(field_name)

        self.failUnlessEqual(fields, req.optional)
        self.failUnlessEqual([], req.required)

        # By default, adding the same fields over again has no effect
        for field_name in fields:
            req.requestField(field_name)

        self.failUnlessEqual(fields, req.optional)
        self.failUnlessEqual([], req.required)

        # Requesting a field as required overrides requesting it as optional
        expected = list(fields)
        overridden = expected.pop(0)
        req.requestField(overridden, required=True)
        self.failUnlessEqual(expected, req.optional)
        self.failUnlessEqual([overridden], req.required)

        # Requesting a field as required overrides requesting it as optional
        for field_name in fields:
            req.requestField(field_name, required=True)

        self.failUnlessEqual([], req.optional)
        self.failUnlessEqual(fields, req.required)

        # Requesting it as optional does not downgrade it to optional
        for field_name in fields:
            req.requestField(field_name)

        self.failUnlessEqual([], req.optional)
        self.failUnlessEqual(fields, req.required)

    def test_requestFields_type(self):
        req = sreg.SRegRequest()
        self.failUnlessRaises(TypeError, req.requestFields, 'nickname')

    def test_requestFields(self):
        # Add all of the fields
        req = sreg.SRegRequest()

        fields = list(sreg.data_fields)
        req.requestFields(fields)

        self.failUnlessEqual(fields, req.optional)
        self.failUnlessEqual([], req.required)

        # By default, adding the same fields over again has no effect
        req.requestFields(fields)

        self.failUnlessEqual(fields, req.optional)
        self.failUnlessEqual([], req.required)

        # Requesting a field as required overrides requesting it as optional
        expected = list(fields)
        overridden = expected.pop(0)
        req.requestFields([overridden], required=True)
        self.failUnlessEqual(expected, req.optional)
        self.failUnlessEqual([overridden], req.required)

        # Requesting a field as required overrides requesting it as optional
        req.requestFields(fields, required=True)

        self.failUnlessEqual([], req.optional)
        self.failUnlessEqual(fields, req.required)

        # Requesting it as optional does not downgrade it to optional
        req.requestFields(fields)

        self.failUnlessEqual([], req.optional)
        self.failUnlessEqual(fields, req.required)

    def test_getExtensionArgs(self):
        req = sreg.SRegRequest()
        self.failUnlessEqual({}, req.getExtensionArgs())

        req.requestField('nickname')
        self.failUnlessEqual({'optional':'nickname'}, req.getExtensionArgs())

        req.requestField('email')
        self.failUnlessEqual({'optional':'nickname,email'},
                             req.getExtensionArgs())

        req.requestField('gender', required=True)
        self.failUnlessEqual({'optional':'nickname,email',
                              'required':'gender'},
                             req.getExtensionArgs())

        req.requestField('postcode', required=True)
        self.failUnlessEqual({'optional':'nickname,email',
                              'required':'gender,postcode'},
                             req.getExtensionArgs())

        req.policy_url = 'http://policy.invalid/'
        self.failUnlessEqual({'optional':'nickname,email',
                              'required':'gender,postcode',
                              'policy_url':'http://policy.invalid/'},
                             req.getExtensionArgs())

data = {
    'nickname':'linusaur',
    'postcode':'12345',
    'country':'US',
    'gender':'M',
    'fullname':'Leonhard Euler',
    'email':'president@whitehouse.gov',
    'dob':'0000-00-00',
    'language':'en-us',
    }

class DummySuccessResponse(object):
    def __init__(self, message, signed_stuff):
        self.message = message
        self.signed_stuff = signed_stuff

    def getSignedNS(self, ns_uri):
        return self.signed_stuff

class SRegResponseTest(unittest.TestCase):
    def test_construct(self):
        resp = sreg.SRegResponse(data)

        self.failUnless(resp)

        empty_resp = sreg.SRegResponse({})
        self.failIf(empty_resp)

        # XXX: finish this test

    def test_fromSuccessResponse_signed(self):
        message = Message.fromOpenIDArgs({
            'sreg.nickname':'The Mad Stork',
            })
        success_resp = DummySuccessResponse(message, {})
        sreg_resp = sreg.SRegResponse.fromSuccessResponse(success_resp)
        self.failIf(sreg_resp)

    def test_fromSuccessResponse_unsigned(self):
        message = Message.fromOpenIDArgs({
            'sreg.nickname':'The Mad Stork',
            })
        success_resp = DummySuccessResponse(message, {})
        sreg_resp = sreg.SRegResponse.fromSuccessResponse(success_resp,
                                                          signed_only=False)
        self.failUnlessEqual([('nickname', 'The Mad Stork')],
                             sreg_resp.items())

class SendFieldsTest(unittest.TestCase):
    def test(self):
        # Create a request message with simple registration fields
        sreg_req = sreg.SRegRequest(required=['nickname', 'email'],
                                    optional=['fullname'])
        req_msg = Message()
        req_msg.updateArgs(sreg.ns_uri, sreg_req.getExtensionArgs())

        req = OpenIDRequest()
        req.message = req_msg
        req.namespace = req_msg.getOpenIDNamespace()

        # -> send checkid_* request

        # Create an empty response message
        resp_msg = Message()
        resp = OpenIDResponse(req)
        resp.fields = resp_msg

        # Put the requested data fields in the response message
        sreg_resp = sreg.SRegResponse.extractResponse(sreg_req, data)
        resp.addExtension(sreg_resp)

        # <- send id_res response

        # Extract the fields that were sent
        sreg_data_resp = resp_msg.getArgs(sreg.ns_uri)
        self.failUnlessEqual(
            {'nickname':'linusaur',
             'email':'president@whitehouse.gov',
             'fullname':'Leonhard Euler',
             }, sreg_data_resp)

if __name__ == '__main__':
    unittest.main()

########NEW FILE########
__FILENAME__ = test_symbol
import unittest

from openid import oidutil

class SymbolTest(unittest.TestCase):
    def test_selfEquality(self):
        s = oidutil.Symbol('xxx')
        self.failUnlessEqual(s, s)

    def test_otherEquality(self):
        x = oidutil.Symbol('xxx')
        y = oidutil.Symbol('xxx')
        self.failUnlessEqual(x, y)

    def test_inequality(self):
        x = oidutil.Symbol('xxx')
        y = oidutil.Symbol('yyy')
        self.failIfEqual(x, y)

    def test_selfInequality(self):
        x = oidutil.Symbol('xxx')
        self.failIf(x != x)

    def test_otherInequality(self):
        x = oidutil.Symbol('xxx')
        y = oidutil.Symbol('xxx')
        self.failIf(x != y)

    def test_ne_inequality(self):
        x = oidutil.Symbol('xxx')
        y = oidutil.Symbol('yyy')
        self.failUnless(x != y)

if __name__ == '__main__':
    unittest.main()

########NEW FILE########
__FILENAME__ = test_urinorm
import os
import unittest
import openid.urinorm

class UrinormTest(unittest.TestCase):
    def __init__(self, desc, case, expected):
        unittest.TestCase.__init__(self)
        self.desc = desc
        self.case = case
        self.expected = expected

    def shortDescription(self):
        return self.desc

    def runTest(self):
        try:
            actual = openid.urinorm.urinorm(self.case)
        except ValueError, why:
            self.assertEqual(self.expected, 'fail', why)
        else:
            self.assertEqual(actual, self.expected)

    def parse(cls, full_case):
        desc, case, expected = full_case.split('\n')
        case = unicode(case, 'utf-8')

        return cls(desc, case, expected)

    parse = classmethod(parse)


def parseTests(test_data):
    result = []

    cases = test_data.split('\n\n')
    for case in cases:
        case = case.strip()

        if case:
            result.append(UrinormTest.parse(case))

    return result

def pyUnitTests():
    here = os.path.dirname(os.path.abspath(__file__))
    test_data_file_name = os.path.join(here, 'urinorm.txt')
    test_data_file = file(test_data_file_name)
    test_data = test_data_file.read()
    test_data_file.close()

    tests = parseTests(test_data)
    return unittest.TestSuite(tests)

########NEW FILE########
__FILENAME__ = test_verifydisco
import unittest
from openid import message
from openid.test.support import OpenIDTestMixin
from openid.consumer import consumer
from openid.test.test_consumer import TestIdRes
from openid.consumer import discover

def const(result):
    """Return a function that ignores any arguments and just returns
    the specified result"""
    def constResult(*args, **kwargs):
        return result

    return constResult

class DiscoveryVerificationTest(OpenIDTestMixin, TestIdRes):
    def failUnlessProtocolError(self, prefix, callable, *args, **kwargs):
        try:
            result = callable(*args, **kwargs)
        except consumer.ProtocolError, e:
            self.failUnless(
                e[0].startswith(prefix),
                'Expected message prefix %r, got message %r' % (prefix, e[0]))
        else:
            self.fail('Expected ProtocolError with prefix %r, '
                      'got successful return %r' % (prefix, result))

    def test_openID1NoLocalID(self):
        endpoint = discover.OpenIDServiceEndpoint()
        endpoint.claimed_id = 'bogus'

        msg = message.Message.fromOpenIDArgs({})
        self.failUnlessProtocolError(
            'Missing required field openid.identity',
            self.consumer._verifyDiscoveryResults, msg, endpoint)
        self.failUnlessLogEmpty()

    def test_openID1NoEndpoint(self):
        msg = message.Message.fromOpenIDArgs({'identity':'snakes on a plane'})
        self.failUnlessRaises(RuntimeError,
                              self.consumer._verifyDiscoveryResults, msg)
        self.failUnlessLogEmpty()

    def test_openID2NoOPEndpointArg(self):
        msg = message.Message.fromOpenIDArgs({'ns':message.OPENID2_NS})
        self.failUnlessRaises(KeyError,
                              self.consumer._verifyDiscoveryResults, msg)
        self.failUnlessLogEmpty()

    def test_openID2LocalIDNoClaimed(self):
        msg = message.Message.fromOpenIDArgs({'ns':message.OPENID2_NS,
                                              'op_endpoint':'Phone Home',
                                              'identity':'Jose Lius Borges'})
        self.failUnlessProtocolError(
            'openid.identity is present without',
            self.consumer._verifyDiscoveryResults, msg)
        self.failUnlessLogEmpty()

    def test_openID2NoLocalIDClaimed(self):
        msg = message.Message.fromOpenIDArgs({'ns':message.OPENID2_NS,
                                              'op_endpoint':'Phone Home',
                                              'claimed_id':'Manuel Noriega'})
        self.failUnlessProtocolError(
            'openid.claimed_id is present without',
            self.consumer._verifyDiscoveryResults, msg)
        self.failUnlessLogEmpty()

    def test_openID2NoIdentifiers(self):
        op_endpoint = 'Phone Home'
        msg = message.Message.fromOpenIDArgs({'ns':message.OPENID2_NS,
                                              'op_endpoint':op_endpoint})
        result_endpoint = self.consumer._verifyDiscoveryResults(msg)
        self.failUnless(result_endpoint.isOPIdentifier())
        self.failUnlessEqual(op_endpoint, result_endpoint.server_url)
        self.failUnlessEqual(None, result_endpoint.claimed_id)
        self.failUnlessLogEmpty()

    def test_openID2NoEndpointDoesDisco(self):
        op_endpoint = 'Phone Home'
        sentinel = discover.OpenIDServiceEndpoint()
        sentinel.claimed_id = 'monkeysoft'
        self.consumer._discoverAndVerify = const(sentinel)
        msg = message.Message.fromOpenIDArgs(
            {'ns':message.OPENID2_NS,
             'identity':'sour grapes',
             'claimed_id':'monkeysoft',
             'op_endpoint':op_endpoint})
        result = self.consumer._verifyDiscoveryResults(msg)
        self.failUnlessEqual(sentinel, result)
        self.failUnlessLogMatches('No pre-discovered')

    def test_openID2MismatchedDoesDisco(self):
        mismatched = discover.OpenIDServiceEndpoint()
        mismatched.identity = 'nothing special, but different'
        mismatched.local_id = 'green cheese'

        op_endpoint = 'Phone Home'
        sentinel = discover.OpenIDServiceEndpoint()
        sentinel.claimed_id = 'monkeysoft'
        self.consumer._discoverAndVerify = const(sentinel)
        msg = message.Message.fromOpenIDArgs(
            {'ns':message.OPENID2_NS,
             'identity':'sour grapes',
             'claimed_id':'monkeysoft',
             'op_endpoint':op_endpoint})
        result = self.consumer._verifyDiscoveryResults(msg, mismatched)
        self.failUnlessEqual(sentinel, result)
        self.failUnlessLogMatches('Error attempting to use stored',
                                  'Attempting discovery')

    def test_openid2UsePreDiscovered(self):
        endpoint = discover.OpenIDServiceEndpoint()
        endpoint.local_id = 'my identity'
        endpoint.claimed_id = 'i am sam'
        endpoint.server_url = 'Phone Home'
        endpoint.type_uris = [discover.OPENID_2_0_TYPE]

        msg = message.Message.fromOpenIDArgs(
            {'ns':message.OPENID2_NS,
             'identity':endpoint.local_id,
             'claimed_id':endpoint.claimed_id,
             'op_endpoint':endpoint.server_url})
        result = self.consumer._verifyDiscoveryResults(msg, endpoint)
        self.failUnless(result is endpoint)
        self.failUnlessLogEmpty()

    def test_openid2UsePreDiscoveredWrongType(self):
        text = "verify failed"

        endpoint = discover.OpenIDServiceEndpoint()
        endpoint.local_id = 'my identity'
        endpoint.claimed_id = 'i am sam'
        endpoint.server_url = 'Phone Home'
        endpoint.type_uris = [discover.OPENID_1_1_TYPE]

        def discoverAndVerify(claimed_id, to_match_endpoints):
            self.failUnlessEqual(claimed_id, endpoint.claimed_id)
            for to_match in to_match_endpoints:
                self.failUnlessEqual(claimed_id, to_match.claimed_id)
            raise consumer.ProtocolError(text)

        self.consumer._discoverAndVerify = discoverAndVerify

        msg = message.Message.fromOpenIDArgs(
            {'ns':message.OPENID2_NS,
             'identity':endpoint.local_id,
             'claimed_id':endpoint.claimed_id,
             'op_endpoint':endpoint.server_url})

        try:
            r = self.consumer._verifyDiscoveryResults(msg, endpoint)
        except consumer.ProtocolError, e:
            # Should we make more ProtocolError subclasses?
            self.failUnless(str(e), text)
        else:
            self.fail("expected ProtocolError, %r returned." % (r,))

        self.failUnlessLogMatches('Error attempting to use stored',
                                  'Attempting discovery')

    def test_openid1UsePreDiscovered(self):
        endpoint = discover.OpenIDServiceEndpoint()
        endpoint.local_id = 'my identity'
        endpoint.claimed_id = 'i am sam'
        endpoint.server_url = 'Phone Home'
        endpoint.type_uris = [discover.OPENID_1_1_TYPE]

        msg = message.Message.fromOpenIDArgs(
            {'ns':message.OPENID1_NS,
             'identity':endpoint.local_id})
        result = self.consumer._verifyDiscoveryResults(msg, endpoint)
        self.failUnless(result is endpoint)
        self.failUnlessLogEmpty()

    def test_openid1UsePreDiscoveredWrongType(self):
        class VerifiedError(Exception): pass

        def discoverAndVerify(claimed_id, _to_match):
            raise VerifiedError

        self.consumer._discoverAndVerify = discoverAndVerify

        endpoint = discover.OpenIDServiceEndpoint()
        endpoint.local_id = 'my identity'
        endpoint.claimed_id = 'i am sam'
        endpoint.server_url = 'Phone Home'
        endpoint.type_uris = [discover.OPENID_2_0_TYPE]

        msg = message.Message.fromOpenIDArgs(
            {'ns':message.OPENID1_NS,
             'identity':endpoint.local_id})

        self.failUnlessRaises(
            VerifiedError,
            self.consumer._verifyDiscoveryResults, msg, endpoint)

        self.failUnlessLogMatches('Error attempting to use stored',
                                  'Attempting discovery')

    def test_openid2Fragment(self):
        claimed_id = "http://unittest.invalid/"
        claimed_id_frag = claimed_id + "#fragment"
        endpoint = discover.OpenIDServiceEndpoint()
        endpoint.local_id = 'my identity'
        endpoint.claimed_id = claimed_id
        endpoint.server_url = 'Phone Home'
        endpoint.type_uris = [discover.OPENID_2_0_TYPE]

        msg = message.Message.fromOpenIDArgs(
            {'ns':message.OPENID2_NS,
             'identity':endpoint.local_id,
             'claimed_id': claimed_id_frag,
             'op_endpoint': endpoint.server_url})
        result = self.consumer._verifyDiscoveryResults(msg, endpoint)
        
        self.failUnlessEqual(result.local_id, endpoint.local_id)
        self.failUnlessEqual(result.server_url, endpoint.server_url)
        self.failUnlessEqual(result.type_uris, endpoint.type_uris)

        self.failUnlessEqual(result.claimed_id, claimed_id_frag)
        
        self.failUnlessLogEmpty()

    def test_openid1Fallback1_0(self):
        claimed_id = 'http://claimed.id/'
        endpoint = None
        resp_mesg = message.Message.fromOpenIDArgs({
            'ns': message.OPENID1_NS,
            'identity': claimed_id})
        # Pass the OpenID 1 claimed_id this way since we're passing
        # None for the endpoint.
        resp_mesg.setArg(message.BARE_NS, 'openid1_claimed_id', claimed_id)

        # We expect the OpenID 1 discovery verification to try
        # matching the discovered endpoint against the 1.1 type and
        # fall back to 1.0.
        expected_endpoint = discover.OpenIDServiceEndpoint()
        expected_endpoint.type_uris = [discover.OPENID_1_0_TYPE]
        expected_endpoint.local_id = None
        expected_endpoint.claimed_id = claimed_id

        discovered_services = [expected_endpoint]
        self.consumer._discover = lambda *args: ('unused', discovered_services)

        actual_endpoint = self.consumer._verifyDiscoveryResults(
            resp_mesg, endpoint)
        self.failUnless(actual_endpoint is expected_endpoint)

# XXX: test the implementation of _discoverAndVerify


class TestVerifyDiscoverySingle(TestIdRes):
    # XXX: more test the implementation of _verifyDiscoverySingle
    def test_endpointWithoutLocalID(self):
        # An endpoint like this with no local_id is generated as a result of
        # e.g. Yadis discovery with no LocalID tag.
        endpoint = discover.OpenIDServiceEndpoint()
        endpoint.server_url = "http://localhost:8000/openidserver"
        endpoint.claimed_id = "http://localhost:8000/id/id-jo"
        to_match = discover.OpenIDServiceEndpoint()
        to_match.server_url = "http://localhost:8000/openidserver"
        to_match.claimed_id = "http://localhost:8000/id/id-jo"
        to_match.local_id = "http://localhost:8000/id/id-jo"
        result = self.consumer._verifyDiscoverySingle(endpoint, to_match)
        # result should always be None, raises exception on failure.
        self.failUnlessEqual(result, None)
        self.failUnlessLogEmpty()

if __name__ == '__main__':
    unittest.main()

########NEW FILE########
__FILENAME__ = test_xri
from unittest import TestCase
from openid.yadis import xri

class XriDiscoveryTestCase(TestCase):
    def test_isXRI(self):
        i = xri.identifierScheme
        self.failUnlessEqual(i('=john.smith'), 'XRI')
        self.failUnlessEqual(i('@smiths/john'), 'XRI')
        self.failUnlessEqual(i('smoker.myopenid.com'), 'URI')
        self.failUnlessEqual(i('xri://=john'), 'XRI')
        self.failUnlessEqual(i(''), 'URI')


class XriEscapingTestCase(TestCase):
    def test_escaping_percents(self):
        self.failUnlessEqual(xri.escapeForIRI('@example/abc%2Fd/ef'),
                             '@example/abc%252Fd/ef')


    def test_escaping_xref(self):
        # no escapes
        esc = xri.escapeForIRI
        self.failUnlessEqual('@example/foo/(@bar)', esc('@example/foo/(@bar)'))
        # escape slashes
        self.failUnlessEqual('@example/foo/(@bar%2Fbaz)',
                             esc('@example/foo/(@bar/baz)'))
        self.failUnlessEqual('@example/foo/(@bar%2Fbaz)/(+a%2Fb)',
                             esc('@example/foo/(@bar/baz)/(+a/b)'))
        # escape query ? and fragment #
        self.failUnlessEqual('@example/foo/(@baz%3Fp=q%23r)?i=j#k',
                             esc('@example/foo/(@baz?p=q#r)?i=j#k'))



class XriTransformationTestCase(TestCase):
    def test_to_iri_normal(self):
        self.failUnlessEqual(xri.toIRINormal('@example'), 'xri://@example')

    try:
        unichr(0x10000)
    except ValueError:
        # bleh narrow python build
        def test_iri_to_url(self):
            s = u'l\xa1m'
            expected = 'l%C2%A1m'
            self.failUnlessEqual(xri.iriToURI(s), expected)
    else:
        def test_iri_to_url(self):
            s = u'l\xa1m\U00101010n'
            expected = 'l%C2%A1m%F4%81%80%90n'
            self.failUnlessEqual(xri.iriToURI(s), expected)



class CanonicalIDTest(TestCase):
    def mkTest(providerID, canonicalID, isAuthoritative):
        def test(self):
            result = xri.providerIsAuthoritative(providerID, canonicalID)
            format = "%s providing %s, expected %s"
            message = format % (providerID, canonicalID, isAuthoritative)
            self.failUnlessEqual(isAuthoritative, result, message)

        return test

    test_equals = mkTest('=', '=!698.74D1.A1F2.86C7', True)
    test_atOne = mkTest('@!1234', '@!1234!ABCD', True)
    test_atTwo = mkTest('@!1234!5678', '@!1234!5678!ABCD', True)

    test_atEqualsFails = mkTest('@!1234', '=!1234!ABCD', False)
    test_tooDeepFails = mkTest('@!1234', '@!1234!ABCD!9765', False)
    test_atEqualsAndTooDeepFails = mkTest('@!1234!ABCD', '=!1234', False)
    test_differentBeginningFails = mkTest('=!BABE', '=!D00D', False)

class TestGetRootAuthority(TestCase):
    def mkTest(the_xri, expected_root):
        def test(self):
            actual_root = xri.rootAuthority(the_xri)
            self.failUnlessEqual(actual_root, xri.XRI(expected_root))
        return test

    test_at = mkTest("@foo", "@")
    test_atStar = mkTest("@foo*bar", "@")
    test_atStarStar = mkTest("@*foo*bar", "@")
    test_atWithPath = mkTest("@foo/bar", "@")
    test_bangBang = mkTest("!!990!991", "!")
    test_bang = mkTest("!1001!02", "!")
    test_equalsStar = mkTest("=foo*bar", "=")
    test_xrefPath = mkTest("(example.com)/foo", "(example.com)")
    test_xrefStar = mkTest("(example.com)*bar/foo", "(example.com)")
    test_uriAuth = mkTest("baz.example.com/foo", "baz.example.com")
    test_uriAuthPort = mkTest("baz.example.com:8080/foo",
                              "baz.example.com:8080")

    # Looking at the ABNF in XRI Syntax 2.0, I don't think you can
    # have example.com*bar.  You can do (example.com)*bar, but that
    # would mean something else.
    ##("example.com*bar/(=baz)", "example.com*bar"),
    ##("baz.example.com!01/foo", "baz.example.com!01"),

if __name__ == '__main__':
    import unittest
    unittest.main()

########NEW FILE########
__FILENAME__ = test_xrires

from unittest import TestCase
from openid.yadis import xrires

class ProxyQueryTestCase(TestCase):
    def setUp(self):
        self.proxy_url = 'http://xri.example.com/'
        self.proxy = xrires.ProxyResolver(self.proxy_url)
        self.servicetype = 'xri://+i-service*(+forwarding)*($v*1.0)'
        self.servicetype_enc = 'xri%3A%2F%2F%2Bi-service%2A%28%2Bforwarding%29%2A%28%24v%2A1.0%29'


    def test_proxy_url(self):
        st = self.servicetype
        ste = self.servicetype_enc
        args_esc = "_xrd_r=application%2Fxrds%2Bxml&_xrd_t=" + ste
        pqu = self.proxy.queryURL
        h = self.proxy_url
        self.failUnlessEqual(h + '=foo?' + args_esc, pqu('=foo', st))
        self.failUnlessEqual(h + '=foo/bar?baz&' + args_esc,
                             pqu('=foo/bar?baz', st))
        self.failUnlessEqual(h + '=foo/bar?baz=quux&' + args_esc,
                             pqu('=foo/bar?baz=quux', st))
        self.failUnlessEqual(h + '=foo/bar?mi=fa&so=la&' + args_esc,
                             pqu('=foo/bar?mi=fa&so=la', st))

        # With no service endpoint selection.
        args_esc = "_xrd_r=application%2Fxrds%2Bxml%3Bsep%3Dfalse"
        self.failUnlessEqual(h + '=foo?' + args_esc, pqu('=foo', None))


    def test_proxy_url_qmarks(self):
        st = self.servicetype
        ste = self.servicetype_enc
        args_esc = "_xrd_r=application%2Fxrds%2Bxml&_xrd_t=" + ste
        pqu = self.proxy.queryURL
        h = self.proxy_url
        self.failUnlessEqual(h + '=foo/bar??' + args_esc, pqu('=foo/bar?', st))
        self.failUnlessEqual(h + '=foo/bar????' + args_esc,
                             pqu('=foo/bar???', st))

########NEW FILE########
__FILENAME__ = test_yadis_discover
#!/usr/bin/env python

"""Tests for yadis.discover.

@todo: Now that yadis.discover uses urljr.fetchers, we should be able to do
   tests with a mock fetcher instead of spawning threads with BaseHTTPServer.
"""

import unittest
import urlparse
import re
import types

from openid.yadis.discover import discover, DiscoveryFailure

from openid import fetchers

import discoverdata

status_header_re = re.compile(r'Status: (\d+) .*?$', re.MULTILINE)

four04_pat = """\
Content-Type: text/plain

No such file %s
"""

class QuitServer(Exception): pass

def mkResponse(data):
    status_mo = status_header_re.match(data)
    headers_str, body = data.split('\n\n', 1)
    headers = {}
    for line in headers_str.split('\n'):
        k, v = line.split(':', 1)
        k = k.strip().lower()
        v = v.strip()
        headers[k] = v
    status = int(status_mo.group(1))
    return fetchers.HTTPResponse(status=status,
                                 headers=headers,
                                 body=body)

class TestFetcher(object):
    def __init__(self, base_url):
        self.base_url = base_url

    def fetch(self, url, headers, body):
        current_url = url
        while True:
            parsed = urlparse.urlparse(current_url)
            path = parsed[2][1:]
            try:
                data = discoverdata.generateSample(path, self.base_url)
            except KeyError:
                return fetchers.HTTPResponse(status=404,
                                             final_url=current_url,
                                             headers={},
                                             body='')

            response = mkResponse(data)
            if response.status in [301, 302, 303, 307]:
                current_url = response.headers['location']
            else:
                response.final_url = current_url
                return response

class TestSecondGet(unittest.TestCase):
    class MockFetcher(object):
        def __init__(self):
            self.count = 0
        def fetch(self, uri, headers=None, body=None):
            self.count += 1
            if self.count == 1:
                headers = {
                    'X-XRDS-Location'.lower(): 'http://unittest/404',
                    }
                return fetchers.HTTPResponse(uri, 200, headers, '')
            else:
                return fetchers.HTTPResponse(uri, 404)

    def setUp(self):
        self.oldfetcher = fetchers.getDefaultFetcher()
        fetchers.setDefaultFetcher(self.MockFetcher())

    def tearDown(self):
        fetchers.setDefaultFetcher(self.oldfetcher)

    def test_404(self):
        uri = "http://something.unittest/"
        self.failUnlessRaises(DiscoveryFailure, discover, uri)


class _TestCase(unittest.TestCase):
    base_url = 'http://invalid.unittest/'

    def __init__(self, input_name, id_name, result_name, success):
        self.input_name = input_name
        self.id_name = id_name
        self.result_name = result_name
        self.success = success
        # Still not quite sure how to best construct these custom tests.
        # Between python2.3 and python2.4, a patch attached to pyunit.sf.net
        # bug #469444 got applied which breaks loadTestsFromModule on this
        # class if it has test_ or runTest methods.  So, kludge to change
        # the method name.
        unittest.TestCase.__init__(self, methodName='runCustomTest')

    def setUp(self):
        fetchers.setDefaultFetcher(TestFetcher(self.base_url),
                                   wrap_exceptions=False)

        self.input_url, self.expected = discoverdata.generateResult(
            self.base_url,
            self.input_name,
            self.id_name,
            self.result_name,
            self.success)

    def tearDown(self):
        fetchers.setDefaultFetcher(None)

    def runCustomTest(self):
        if self.expected is DiscoveryFailure:
            self.failUnlessRaises(DiscoveryFailure,
                                  discover, self.input_url)
        else:
            result = discover(self.input_url)
            self.failUnlessEqual(self.input_url, result.request_uri)

            msg = 'Identity URL mismatch: actual = %r, expected = %r' % (
                result.normalized_uri, self.expected.normalized_uri)
            self.failUnlessEqual(
                self.expected.normalized_uri, result.normalized_uri, msg)

            msg = 'Content mismatch: actual = %r, expected = %r' % (
                result.response_text, self.expected.response_text)
            self.failUnlessEqual(
                self.expected.response_text, result.response_text, msg)

            expected_keys = dir(self.expected)
            expected_keys.sort()
            actual_keys = dir(result)
            actual_keys.sort()
            self.failUnlessEqual(actual_keys, expected_keys)

            for k in dir(self.expected):
                if k.startswith('__') and k.endswith('__'):
                    continue
                exp_v = getattr(self.expected, k)
                if isinstance(exp_v, types.MethodType):
                    continue
                act_v = getattr(result, k)
                assert act_v == exp_v, (k, exp_v, act_v)

    def shortDescription(self):
        try:
            n = self.input_url
        except AttributeError:
            # run before setUp, or if setUp did not complete successfully.
            n = self.input_name
        return "%s (%s)" % (
            n,
            self.__class__.__module__)

def pyUnitTests():
    s = unittest.TestSuite()
    for success, input_name, id_name, result_name in discoverdata.testlist:
        test = _TestCase(input_name, id_name, result_name, success)
        s.addTest(test)

    return s

def test():
    runner = unittest.TextTestRunner()
    return runner.run(pyUnitTests())

if __name__ == '__main__':
    test()

########NEW FILE########
__FILENAME__ = trustroot
import os
import unittest
from openid.server.trustroot import TrustRoot

class _ParseTest(unittest.TestCase):
    def __init__(self, sanity, desc, case):
        unittest.TestCase.__init__(self)
        self.desc = desc + ': ' + repr(case)
        self.case = case
        self.sanity = sanity

    def shortDescription(self):
        return self.desc

    def runTest(self):
        tr = TrustRoot.parse(self.case)
        if self.sanity == 'sane':
            assert tr.isSane(), self.case
        elif self.sanity == 'insane':
            assert not tr.isSane(), self.case
        else:
            assert tr is None, tr

class _MatchTest(unittest.TestCase):
    def __init__(self, match, desc, line):
        unittest.TestCase.__init__(self)
        tr, rt = line.split()
        self.desc = desc + ': ' + repr(tr) + ' ' + repr(rt)
        self.tr = tr
        self.rt = rt
        self.match = match

    def shortDescription(self):
        return self.desc

    def runTest(self):
        tr = TrustRoot.parse(self.tr)
        self.failIf(tr is None, self.tr)

        match = tr.validateURL(self.rt)
        if self.match:
            assert match
        else:
            assert not match

def getTests(t, grps, head, dat):
    tests = []
    top = head.strip()
    gdat = map(str.strip, dat.split('-' * 40 + '\n'))
    assert not gdat[0]
    assert len(gdat) == (len(grps) * 2 + 1), (gdat, grps)
    i = 1
    for x in grps:
        n, desc = gdat[i].split(': ')
        cases = gdat[i + 1].split('\n')
        assert len(cases) == int(n)
        for case in cases:
            tests.append(t(x, top + ' - ' + desc, case))
        i += 2
    return tests

def parseTests(data):
    parts = map(str.strip, data.split('=' * 40 + '\n'))
    assert not parts[0]
    _, ph, pdat, mh, mdat = parts

    tests = []
    tests.extend(getTests(_ParseTest, ['bad', 'insane', 'sane'], ph, pdat))
    tests.extend(getTests(_MatchTest, [1, 0], mh, mdat))
    return tests

def pyUnitTests():
    here = os.path.dirname(os.path.abspath(__file__))
    test_data_file_name = os.path.join(here, 'data', 'trustroot.txt')
    test_data_file = file(test_data_file_name)
    test_data = test_data_file.read()
    test_data_file.close()

    tests = parseTests(test_data)
    return unittest.TestSuite(tests)

if __name__ == '__main__':
    suite = pyUnitTests()
    runner = unittest.TextTestRunner()
    runner.run(suite)

########NEW FILE########
__FILENAME__ = urinorm
import re

# from appendix B of rfc 3986 (http://www.ietf.org/rfc/rfc3986.txt)
uri_pattern = r'^(([^:/?#]+):)?(//([^/?#]*))?([^?#]*)(\?([^#]*))?(#(.*))?'
uri_re = re.compile(uri_pattern)

# gen-delims  = ":" / "/" / "?" / "#" / "[" / "]" / "@"
#
# sub-delims  = "!" / "$" / "&" / "'" / "(" / ")"
#                  / "*" / "+" / "," / ";" / "="
#
# unreserved  = ALPHA / DIGIT / "-" / "." / "_" / "~"

uri_illegal_char_re = re.compile(
    "[^-A-Za-z0-9:/?#[\]@!$&'()*+,;=._~%]", re.UNICODE)

authority_pattern = r'^([^@]*@)?([^:]*)(:.*)?'
authority_re = re.compile(authority_pattern)


pct_encoded_pattern = r'%([0-9A-Fa-f]{2})'
pct_encoded_re = re.compile(pct_encoded_pattern)

try:
    unichr(0x10000)
except ValueError:
    # narrow python build
    UCSCHAR = [
        (0xA0, 0xD7FF),
        (0xF900, 0xFDCF),
        (0xFDF0, 0xFFEF),
        ]

    IPRIVATE = [
        (0xE000, 0xF8FF),
        ]
else:
    UCSCHAR = [
        (0xA0, 0xD7FF),
        (0xF900, 0xFDCF),
        (0xFDF0, 0xFFEF),
        (0x10000, 0x1FFFD),
        (0x20000, 0x2FFFD),
        (0x30000, 0x3FFFD),
        (0x40000, 0x4FFFD),
        (0x50000, 0x5FFFD),
        (0x60000, 0x6FFFD),
        (0x70000, 0x7FFFD),
        (0x80000, 0x8FFFD),
        (0x90000, 0x9FFFD),
        (0xA0000, 0xAFFFD),
        (0xB0000, 0xBFFFD),
        (0xC0000, 0xCFFFD),
        (0xD0000, 0xDFFFD),
        (0xE1000, 0xEFFFD),
        ]

    IPRIVATE = [
        (0xE000, 0xF8FF),
        (0xF0000, 0xFFFFD),
        (0x100000, 0x10FFFD),
        ]


_unreserved = [False] * 256
for _ in range(ord('A'), ord('Z') + 1): _unreserved[_] = True
for _ in range(ord('0'), ord('9') + 1): _unreserved[_] = True
for _ in range(ord('a'), ord('z') + 1): _unreserved[_] = True
_unreserved[ord('-')] = True
_unreserved[ord('.')] = True
_unreserved[ord('_')] = True
_unreserved[ord('~')] = True


_escapeme_re = re.compile('[%s]' % (''.join(
    map(lambda (m, n): u'%s-%s' % (unichr(m), unichr(n)),
        UCSCHAR + IPRIVATE)),))


def _pct_escape_unicode(char_match):
    c = char_match.group()
    return ''.join(['%%%X' % (ord(octet),) for octet in c.encode('utf-8')])


def _pct_encoded_replace_unreserved(mo):
    try:
        i = int(mo.group(1), 16)
        if _unreserved[i]:
            return chr(i)
        else:
            return mo.group().upper()

    except ValueError:
        return mo.group()


def _pct_encoded_replace(mo):
    try:
        return chr(int(mo.group(1), 16))
    except ValueError:
        return mo.group()


def remove_dot_segments(path):
    result_segments = []

    while path:
        if path.startswith('../'):
            path = path[3:]
        elif path.startswith('./'):
            path = path[2:]
        elif path.startswith('/./'):
            path = path[2:]
        elif path == '/.':
            path = '/'
        elif path.startswith('/../'):
            path = path[3:]
            if result_segments:
                result_segments.pop()
        elif path == '/..':
            path = '/'
            if result_segments:
                result_segments.pop()
        elif path == '..' or path == '.':
            path = ''
        else:
            i = 0
            if path[0] == '/':
                i = 1
            i = path.find('/', i)
            if i == -1:
                i = len(path)
            result_segments.append(path[:i])
            path = path[i:]

    return ''.join(result_segments)


def urinorm(uri):
    if isinstance(uri, unicode):
        uri = _escapeme_re.sub(_pct_escape_unicode, uri).encode('ascii')

    illegal_mo = uri_illegal_char_re.search(uri)
    if illegal_mo:
        raise ValueError('Illegal characters in URI: %r at position %s' %
                         (illegal_mo.group(), illegal_mo.start()))

    uri_mo = uri_re.match(uri)

    scheme = uri_mo.group(2)
    if scheme is None:
        raise ValueError('No scheme specified')

    scheme = scheme.lower()
    if scheme not in ('http', 'https'):
        raise ValueError('Not an absolute HTTP or HTTPS URI: %r' % (uri,))

    authority = uri_mo.group(4)
    if authority is None:
        raise ValueError('Not an absolute URI: %r' % (uri,))

    authority_mo = authority_re.match(authority)
    if authority_mo is None:
        raise ValueError('URI does not have a valid authority: %r' % (uri,))

    userinfo, host, port = authority_mo.groups()

    if userinfo is None:
        userinfo = ''

    if '%' in host:
        host = host.lower()
        host = pct_encoded_re.sub(_pct_encoded_replace, host)
        host = unicode(host, 'utf-8').encode('idna')
    else:
        host = host.lower()

    if port:
        if (port == ':' or
            (scheme == 'http' and port == ':80') or
            (scheme == 'https' and port == ':443')):
            port = ''
    else:
        port = ''

    authority = userinfo + host + port

    path = uri_mo.group(5)
    path = pct_encoded_re.sub(_pct_encoded_replace_unreserved, path)
    path = remove_dot_segments(path)
    if not path:
        path = '/'

    query = uri_mo.group(6)
    if query is None:
        query = ''

    fragment = uri_mo.group(8)
    if fragment is None:
        fragment = ''

    return scheme + '://' + authority + path + query + fragment

########NEW FILE########
__FILENAME__ = accept
"""Functions for generating and parsing HTTP Accept: headers for
supporting server-directed content negotiation.
"""

def generateAcceptHeader(*elements):
    """Generate an accept header value

    [str or (str, float)] -> str
    """
    parts = []
    for element in elements:
        if type(element) is str:
            qs = "1.0"
            mtype = element
        else:
            mtype, q = element
            q = float(q)
            if q > 1 or q <= 0:
                raise ValueError('Invalid preference factor: %r' % q)

            qs = '%0.1f' % (q,)

        parts.append((qs, mtype))

    parts.sort()
    chunks = []
    for q, mtype in parts:
        if q == '1.0':
            chunks.append(mtype)
        else:
            chunks.append('%s; q=%s' % (mtype, q))

    return ', '.join(chunks)

def parseAcceptHeader(value):
    """Parse an accept header, ignoring any accept-extensions

    returns a list of tuples containing main MIME type, MIME subtype,
    and quality markdown.

    str -> [(str, str, float)]
    """
    chunks = [chunk.strip() for chunk in value.split(',')]
    accept = []
    for chunk in chunks:
        parts = [s.strip() for s in chunk.split(';')]

        mtype = parts.pop(0)
        if '/' not in mtype:
            # This is not a MIME type, so ignore the bad data
            continue

        main, sub = mtype.split('/', 1)

        for ext in parts:
            if '=' in ext:
                k, v = ext.split('=', 1)
                if k == 'q':
                    try:
                        q = float(v)
                        break
                    except ValueError:
                        # Ignore poorly formed q-values
                        pass
        else:
            q = 1.0

        accept.append((q, main, sub))

    accept.sort()
    accept.reverse()
    return [(main, sub, q) for (q, main, sub) in accept]

def matchTypes(accept_types, have_types):
    """Given the result of parsing an Accept: header, and the
    available MIME types, return the acceptable types with their
    quality markdowns.

    For example:

    >>> acceptable = parseAcceptHeader('text/html, text/plain; q=0.5')
    >>> matchTypes(acceptable, ['text/plain', 'text/html', 'image/jpeg'])
    [('text/html', 1.0), ('text/plain', 0.5)]


    Type signature: ([(str, str, float)], [str]) -> [(str, float)]
    """
    if not accept_types:
        # Accept all of them
        default = 1
    else:
        default = 0

    match_main = {}
    match_sub = {}
    for (main, sub, q) in accept_types:
        if main == '*':
            default = max(default, q)
            continue
        elif sub == '*':
            match_main[main] = max(match_main.get(main, 0), q)
        else:
            match_sub[(main, sub)] = max(match_sub.get((main, sub), 0), q)

    accepted_list = []
    order_maintainer = 0
    for mtype in have_types:
        main, sub = mtype.split('/')
        if (main, sub) in match_sub:
            q = match_sub[(main, sub)]
        else:
            q = match_main.get(main, default)

        if q:
            accepted_list.append((1 - q, order_maintainer, q, mtype))
            order_maintainer += 1

    accepted_list.sort()
    return [(mtype, q) for (_, _, q, mtype) in accepted_list]

def getAcceptable(accept_header, have_types):
    """Parse the accept header and return a list of available types in
    preferred order. If a type is unacceptable, it will not be in the
    resulting list.

    This is a convenience wrapper around matchTypes and
    parseAcceptHeader.

    (str, [str]) -> [str]
    """
    accepted = parseAcceptHeader(accept_header)
    preferred = matchTypes(accepted, have_types)
    return [mtype for (mtype, _) in preferred]

########NEW FILE########
__FILENAME__ = constants
__all__ = ['YADIS_HEADER_NAME', 'YADIS_CONTENT_TYPE', 'YADIS_ACCEPT_HEADER']
from openid.yadis.accept import generateAcceptHeader

YADIS_HEADER_NAME = 'X-XRDS-Location'
YADIS_CONTENT_TYPE = 'application/xrds+xml'

# A value suitable for using as an accept header when performing YADIS
# discovery, unless the application has special requirements
YADIS_ACCEPT_HEADER = generateAcceptHeader(
    ('text/html', 0.3),
    ('application/xhtml+xml', 0.5),
    (YADIS_CONTENT_TYPE, 1.0),
    )

########NEW FILE########
__FILENAME__ = discover
# -*- test-case-name: openid.test.test_yadis_discover -*-
__all__ = ['discover', 'DiscoveryResult', 'DiscoveryFailure']

from StringIO import StringIO

from openid import fetchers

from openid.yadis.constants import \
     YADIS_HEADER_NAME, YADIS_CONTENT_TYPE, YADIS_ACCEPT_HEADER
from openid.yadis.parsehtml import MetaNotFound, findHTMLMeta

class DiscoveryFailure(Exception):
    """Raised when a YADIS protocol error occurs in the discovery process"""
    identity_url = None

    def __init__(self, message, http_response):
        Exception.__init__(self, message)
        self.http_response = http_response

class DiscoveryResult(object):
    """Contains the result of performing Yadis discovery on a URI"""

    # The URI that was passed to the fetcher
    request_uri = None

    # The result of following redirects from the request_uri
    normalized_uri = None

    # The URI from which the response text was returned (set to
    # None if there was no XRDS document found)
    xrds_uri = None

    # The content-type returned with the response_text
    content_type = None

    # The document returned from the xrds_uri
    response_text = None

    def __init__(self, request_uri):
        """Initialize the state of the object

        sets all attributes to None except the request_uri
        """
        self.request_uri = request_uri

    def usedYadisLocation(self):
        """Was the Yadis protocol's indirection used?"""
        if self.xrds_uri is None:
            return False
        return self.normalized_uri != self.xrds_uri

    def isXRDS(self):
        """Is the response text supposed to be an XRDS document?"""
        return (self.usedYadisLocation() or
                self.content_type == YADIS_CONTENT_TYPE)

def discover(uri):
    """Discover services for a given URI.

    @param uri: The identity URI as a well-formed http or https
        URI. The well-formedness and the protocol are not checked, but
        the results of this function are undefined if those properties
        do not hold.

    @return: DiscoveryResult object

    @raises Exception: Any exception that can be raised by fetching a URL with
        the given fetcher.
    @raises DiscoveryFailure: When the HTTP response does not have a 200 code.
    """
    result = DiscoveryResult(uri)
    resp = fetchers.fetch(uri, headers={'Accept': YADIS_ACCEPT_HEADER})
    if resp.status not in (200, 206):
        raise DiscoveryFailure(
            'HTTP Response status from identity URL host is not 200. '
            'Got status %r' % (resp.status,), resp)

    # Note the URL after following redirects
    result.normalized_uri = resp.final_url

    # Attempt to find out where to go to discover the document
    # or if we already have it
    result.content_type = resp.headers.get('content-type')

    result.xrds_uri = whereIsYadis(resp)

    if result.xrds_uri and result.usedYadisLocation():
        resp = fetchers.fetch(result.xrds_uri)
        if resp.status not in (200, 206):
            exc = DiscoveryFailure(
                'HTTP Response status from Yadis host is not 200. '
                'Got status %r' % (resp.status,), resp)
            exc.identity_url = result.normalized_uri
            raise exc
        result.content_type = resp.headers.get('content-type')

    result.response_text = resp.body
    return result



def whereIsYadis(resp):
    """Given a HTTPResponse, return the location of the Yadis document.

    May be the URL just retrieved, another URL, or None, if I can't
    find any.

    [non-blocking]

    @returns: str or None
    """
    # Attempt to find out where to go to discover the document
    # or if we already have it
    content_type = resp.headers.get('content-type')

    # According to the spec, the content-type header must be an exact
    # match, or else we have to look for an indirection.
    if (content_type and
        content_type.split(';', 1)[0].lower() == YADIS_CONTENT_TYPE):
        return resp.final_url
    else:
        # Try the header
        yadis_loc = resp.headers.get(YADIS_HEADER_NAME.lower())

        if not yadis_loc:
            # Parse as HTML if the header is missing.
            #
            # XXX: do we want to do something with content-type, like
            # have a whitelist or a blacklist (for detecting that it's
            # HTML)?

            # Decode body by encoding of file
            content_type = content_type or ''
            encoding = content_type.rsplit(';', 1)
            if len(encoding) == 2 and encoding[1].strip().startswith('charset='):
                encoding = encoding[1].split('=', 1)[1].strip()
            else:
                encoding = 'UTF-8'

            try:
                content = resp.body.decode(encoding)
            except UnicodeError:
                # Keep encoded version in case yadis location can be found before encoding shut this up.
                # Possible errors will be caught lower.
                content = resp.body

            try:
                yadis_loc = findHTMLMeta(StringIO(content))
            except (MetaNotFound, UnicodeError):
                # UnicodeError: Response body could not be encoded and xrds location
                # could not be found before troubles occurs.
                pass

        return yadis_loc


########NEW FILE########
__FILENAME__ = etxrd
# -*- test-case-name: yadis.test.test_etxrd -*-
"""
ElementTree interface to an XRD document.
"""

__all__ = [
    'nsTag',
    'mkXRDTag',
    'isXRDS',
    'parseXRDS',
    'getCanonicalID',
    'getYadisXRD',
    'getPriorityStrict',
    'getPriority',
    'prioSort',
    'iterServices',
    'expandService',
    'expandServices',
    ]

import sys
import random

from datetime import datetime
from time import strptime

from openid.oidutil import importElementTree
ElementTree = importElementTree()

# the different elementtree modules don't have a common exception
# model. We just want to be able to catch the exceptions that signify
# malformed XML data and wrap them, so that the other library code
# doesn't have to know which XML library we're using.
try:
    # Make the parser raise an exception so we can sniff out the type
    # of exceptions
    ElementTree.XML('> purposely malformed XML <')
except (SystemExit, MemoryError, AssertionError, ImportError):
    raise
except:
    XMLError = sys.exc_info()[0]

from openid.yadis import xri

class XRDSError(Exception):
    """An error with the XRDS document."""

    # The exception that triggered this exception
    reason = None



class XRDSFraud(XRDSError):
    """Raised when there's an assertion in the XRDS that it does not have
    the authority to make.
    """



def parseXRDS(text):
    """Parse the given text as an XRDS document.

    @return: ElementTree containing an XRDS document

    @raises XRDSError: When there is a parse error or the document does
        not contain an XRDS.
    """
    try:
        element = ElementTree.XML(text)
    except XMLError, why:
        exc = XRDSError('Error parsing document as XML')
        exc.reason = why
        raise exc
    else:
        tree = ElementTree.ElementTree(element)
        if not isXRDS(tree):
            raise XRDSError('Not an XRDS document')

        return tree

XRD_NS_2_0 = 'xri://$xrd*($v*2.0)'
XRDS_NS = 'xri://$xrds'

def nsTag(ns, t):
    return '{%s}%s' % (ns, t)

def mkXRDTag(t):
    """basestring -> basestring

    Create a tag name in the XRD 2.0 XML namespace suitable for using
    with ElementTree
    """
    return nsTag(XRD_NS_2_0, t)

def mkXRDSTag(t):
    """basestring -> basestring

    Create a tag name in the XRDS XML namespace suitable for using
    with ElementTree
    """
    return nsTag(XRDS_NS, t)

# Tags that are used in Yadis documents
root_tag = mkXRDSTag('XRDS')
service_tag = mkXRDTag('Service')
xrd_tag = mkXRDTag('XRD')
type_tag = mkXRDTag('Type')
uri_tag = mkXRDTag('URI')
expires_tag = mkXRDTag('Expires')

# Other XRD tags
canonicalID_tag = mkXRDTag('CanonicalID')

def isXRDS(xrd_tree):
    """Is this document an XRDS document?"""
    root = xrd_tree.getroot()
    return root.tag == root_tag

def getYadisXRD(xrd_tree):
    """Return the XRD element that should contain the Yadis services"""
    xrd = None

    # for the side-effect of assigning the last one in the list to the
    # xrd variable
    for xrd in xrd_tree.findall(xrd_tag):
        pass

    # There were no elements found, or else xrd would be set to the
    # last one
    if xrd is None:
        raise XRDSError('No XRD present in tree')

    return xrd

def getXRDExpiration(xrd_element, default=None):
    """Return the expiration date of this XRD element, or None if no
    expiration was specified.

    @type xrd_element: ElementTree node

    @param default: The value to use as the expiration if no
        expiration was specified in the XRD.

    @rtype: datetime.datetime

    @raises ValueError: If the xrd:Expires element is present, but its
        contents are not formatted according to the specification.
    """
    expires_element = xrd_element.find(expires_tag)
    if expires_element is None:
        return default
    else:
        expires_string = expires_element.text

        # Will raise ValueError if the string is not the expected format
        expires_time = strptime(expires_string, "%Y-%m-%dT%H:%M:%SZ")
        return datetime(*expires_time[0:6])

def getCanonicalID(iname, xrd_tree):
    """Return the CanonicalID from this XRDS document.

    @param iname: the XRI being resolved.
    @type iname: unicode

    @param xrd_tree: The XRDS output from the resolver.
    @type xrd_tree: ElementTree

    @returns: The XRI CanonicalID or None.
    @returntype: unicode or None
    """
    xrd_list = xrd_tree.findall(xrd_tag)
    xrd_list.reverse()

    try:
        canonicalID = xri.XRI(xrd_list[0].findall(canonicalID_tag)[0].text)
    except IndexError:
        return None

    childID = canonicalID.lower()

    for xrd in xrd_list[1:]:
        # XXX: can't use rsplit until we require python >= 2.4.
        parent_sought = childID[:childID.rindex('!')]
        parent = xri.XRI(xrd.findtext(canonicalID_tag))
        if parent_sought != parent.lower():
            raise XRDSFraud("%r can not come from %s" % (childID, parent))

        childID = parent_sought

    root = xri.rootAuthority(iname)
    if not xri.providerIsAuthoritative(root, childID):
        raise XRDSFraud("%r can not come from root %r" % (childID, root))

    return canonicalID



class _Max(object):
    """Value that compares greater than any other value.

    Should only be used as a singleton. Implemented for use as a
    priority value for when a priority is not specified."""
    def __cmp__(self, other):
        if other is self:
            return 0

        return 1

Max = _Max()

def getPriorityStrict(element):
    """Get the priority of this element.

    Raises ValueError if the value of the priority is invalid. If no
    priority is specified, it returns a value that compares greater
    than any other value.
    """
    prio_str = element.get('priority')
    if prio_str is not None:
        prio_val = int(prio_str)
        if prio_val >= 0:
            return prio_val
        else:
            raise ValueError('Priority values must be non-negative integers')

    # Any errors in parsing the priority fall through to here
    return Max

def getPriority(element):
    """Get the priority of this element

    Returns Max if no priority is specified or the priority value is invalid.
    """
    try:
        return getPriorityStrict(element)
    except ValueError:
        return Max

def prioSort(elements):
    """Sort a list of elements that have priority attributes"""
    # Randomize the services before sorting so that equal priority
    # elements are load-balanced.
    random.shuffle(elements)

    prio_elems = [(getPriority(e), e) for e in elements]
    prio_elems.sort()
    sorted_elems = [s for (_, s) in prio_elems]
    return sorted_elems

def iterServices(xrd_tree):
    """Return an iterable over the Service elements in the Yadis XRD

    sorted by priority"""
    xrd = getYadisXRD(xrd_tree)
    return prioSort(xrd.findall(service_tag))

def sortedURIs(service_element):
    """Given a Service element, return a list of the contents of all
    URI tags in priority order."""
    return [uri_element.text for uri_element
            in prioSort(service_element.findall(uri_tag))]

def getTypeURIs(service_element):
    """Given a Service element, return a list of the contents of all
    Type tags"""
    return [type_element.text for type_element
            in service_element.findall(type_tag)]

def expandService(service_element):
    """Take a service element and expand it into an iterator of:
    ([type_uri], uri, service_element)
    """
    uris = sortedURIs(service_element)
    if not uris:
        uris = [None]

    expanded = []
    for uri in uris:
        type_uris = getTypeURIs(service_element)
        expanded.append((type_uris, uri, service_element))

    return expanded

def expandServices(service_elements):
    """Take a sorted iterator of service elements and expand it into a
    sorted iterator of:
    ([type_uri], uri, service_element)

    There may be more than one item in the resulting list for each
    service element if there is more than one URI or type for a
    service, but each triple will be unique.

    If there is no URI or Type for a Service element, it will not
    appear in the result.
    """
    expanded = []
    for service_element in service_elements:
        expanded.extend(expandService(service_element))

    return expanded

########NEW FILE########
__FILENAME__ = filters
"""This module contains functions and classes used for extracting
endpoint information out of a Yadis XRD file using the ElementTree XML
parser.
"""

__all__ = [
    'BasicServiceEndpoint',
    'mkFilter',
    'IFilter',
    'TransformFilterMaker',
    'CompoundFilter',
    ]

from openid.yadis.etxrd import expandService

class BasicServiceEndpoint(object):
    """Generic endpoint object that contains parsed service
    information, as well as a reference to the service element from
    which it was generated. If there is more than one xrd:Type or
    xrd:URI in the xrd:Service, this object represents just one of
    those pairs.

    This object can be used as a filter, because it implements
    fromBasicServiceEndpoint.

    The simplest kind of filter you can write implements
    fromBasicServiceEndpoint, which takes one of these objects.
    """
    def __init__(self, yadis_url, type_uris, uri, service_element):
        self.type_uris = type_uris
        self.yadis_url = yadis_url
        self.uri = uri
        self.service_element = service_element

    def matchTypes(self, type_uris):
        """Query this endpoint to see if it has any of the given type
        URIs. This is useful for implementing other endpoint classes
        that e.g. need to check for the presence of multiple versions
        of a single protocol.

        @param type_uris: The URIs that you wish to check
        @type type_uris: iterable of str

        @return: all types that are in both in type_uris and
            self.type_uris
        """
        return [uri for uri in type_uris if uri in self.type_uris]

    def fromBasicServiceEndpoint(endpoint):
        """Trivial transform from a basic endpoint to itself. This
        method exists to allow BasicServiceEndpoint to be used as a
        filter.

        If you are subclassing this object, re-implement this function.

        @param endpoint: An instance of BasicServiceEndpoint
        @return: The object that was passed in, with no processing.
        """
        return endpoint

    fromBasicServiceEndpoint = staticmethod(fromBasicServiceEndpoint)

class IFilter(object):
    """Interface for Yadis filter objects. Other filter-like things
    are convertable to this class."""

    def getServiceEndpoints(self, yadis_url, service_element):
        """Returns an iterator of endpoint objects"""
        raise NotImplementedError

class TransformFilterMaker(object):
    """Take a list of basic filters and makes a filter that transforms
    the basic filter into a top-level filter. This is mostly useful
    for the implementation of mkFilter, which should only be needed
    for special cases or internal use by this library.

    This object is useful for creating simple filters for services
    that use one URI and are specified by one Type (we expect most
    Types will fit this paradigm).

    Creates a BasicServiceEndpoint object and apply the filter
    functions to it until one of them returns a value.
    """

    def __init__(self, filter_functions):
        """Initialize the filter maker's state

        @param filter_functions: The endpoint transformer functions to
            apply to the basic endpoint. These are called in turn
            until one of them does not return None, and the result of
            that transformer is returned.
        """
        self.filter_functions = filter_functions

    def getServiceEndpoints(self, yadis_url, service_element):
        """Returns an iterator of endpoint objects produced by the
        filter functions."""
        endpoints = []

        # Do an expansion of the service element by xrd:Type and xrd:URI
        for type_uris, uri, _ in expandService(service_element):

            # Create a basic endpoint object to represent this
            # yadis_url, Service, Type, URI combination
            endpoint = BasicServiceEndpoint(
                yadis_url, type_uris, uri, service_element)

            e = self.applyFilters(endpoint)
            if e is not None:
                endpoints.append(e)

        return endpoints

    def applyFilters(self, endpoint):
        """Apply filter functions to an endpoint until one of them
        returns non-None."""
        for filter_function in self.filter_functions:
            e = filter_function(endpoint)
            if e is not None:
                # Once one of the filters has returned an
                # endpoint, do not apply any more.
                return e

        return None

class CompoundFilter(object):
    """Create a new filter that applies a set of filters to an endpoint
    and collects their results.
    """
    def __init__(self, subfilters):
        self.subfilters = subfilters

    def getServiceEndpoints(self, yadis_url, service_element):
        """Generate all endpoint objects for all of the subfilters of
        this filter and return their concatenation."""
        endpoints = []
        for subfilter in self.subfilters:
            endpoints.extend(
                subfilter.getServiceEndpoints(yadis_url, service_element))
        return endpoints

# Exception raised when something is not able to be turned into a filter
filter_type_error = TypeError(
    'Expected a filter, an endpoint, a callable or a list of any of these.')

def mkFilter(parts):
    """Convert a filter-convertable thing into a filter

    @param parts: a filter, an endpoint, a callable, or a list of any of these.
    """
    # Convert the parts into a list, and pass to mkCompoundFilter
    if parts is None:
        parts = [BasicServiceEndpoint]

    try:
        parts = list(parts)
    except TypeError:
        return mkCompoundFilter([parts])
    else:
        return mkCompoundFilter(parts)

def mkCompoundFilter(parts):
    """Create a filter out of a list of filter-like things

    Used by mkFilter

    @param parts: list of filter, endpoint, callable or list of any of these
    """
    # Separate into a list of callables and a list of filter objects
    transformers = []
    filters = []
    for subfilter in parts:
        try:
            subfilter = list(subfilter)
        except TypeError:
            # If it's not an iterable
            if hasattr(subfilter, 'getServiceEndpoints'):
                # It's a full filter
                filters.append(subfilter)
            elif hasattr(subfilter, 'fromBasicServiceEndpoint'):
                # It's an endpoint object, so put its endpoint
                # conversion attribute into the list of endpoint
                # transformers
                transformers.append(subfilter.fromBasicServiceEndpoint)
            elif callable(subfilter):
                # It's a simple callable, so add it to the list of
                # endpoint transformers
                transformers.append(subfilter)
            else:
                raise filter_type_error
        else:
            filters.append(mkCompoundFilter(subfilter))

    if transformers:
        filters.append(TransformFilterMaker(transformers))

    if len(filters) == 1:
        return filters[0]
    else:
        return CompoundFilter(filters)

########NEW FILE########
__FILENAME__ = manager
class YadisServiceManager(object):
    """Holds the state of a list of selected Yadis services, managing
    storing it in a session and iterating over the services in order."""

    def __init__(self, starting_url, yadis_url, services, session_key):
        # The URL that was used to initiate the Yadis protocol
        self.starting_url = starting_url

        # The URL after following redirects (the identifier)
        self.yadis_url = yadis_url

        # List of service elements
        self.services = list(services)

        self.session_key = session_key

        # Reference to the current service object
        self._current = None

    def __len__(self):
        """How many untried services remain?"""
        return len(self.services)

    def __iter__(self):
        return self

    def next(self):
        """Return the next service

        self.current() will continue to return that service until the
        next call to this method."""
        try:
            self._current = self.services.pop(0)
        except IndexError:
            raise StopIteration
        else:
            return self._current

    def current(self):
        """Return the current service.

        Returns None if there are no services left.
        """
        return self._current

    def forURL(self, url):
        return url in [self.starting_url, self.yadis_url]

    def started(self):
        """Has the first service been returned?"""
        return self._current is not None

    def store(self, session):
        """Store this object in the session, by its session key."""
        session[self.session_key] = self

class Discovery(object):
    """State management for discovery.

    High-level usage pattern is to call .getNextService(discover) in
    order to find the next available service for this user for this
    session. Once a request completes, call .finish() to clean up the
    session state.

    @ivar session: a dict-like object that stores state unique to the
        requesting user-agent. This object must be able to store
        serializable objects.

    @ivar url: the URL that is used to make the discovery request

    @ivar session_key_suffix: The suffix that will be used to identify
        this object in the session object.
    """

    DEFAULT_SUFFIX = 'auth'
    PREFIX = '_yadis_services_'

    def __init__(self, session, url, session_key_suffix=None):
        """Initialize a discovery object"""
        self.session = session
        self.url = url
        if session_key_suffix is None:
            session_key_suffix = self.DEFAULT_SUFFIX

        self.session_key_suffix = session_key_suffix

    def getNextService(self, discover):
        """Return the next authentication service for the pair of
        user_input and session.  This function handles fallback.


        @param discover: a callable that takes a URL and returns a
            list of services

        @type discover: str -> [service]


        @return: the next available service
        """
        manager = self.getManager()
        if manager is not None and not manager:
            self.destroyManager()

        if not manager:
            yadis_url, services = discover(self.url)
            manager = self.createManager(services, yadis_url)

        if manager:
            service = manager.next()
            manager.store(self.session)
        else:
            service = None

        return service

    def cleanup(self, force=False):
        """Clean up Yadis-related services in the session and return
        the most-recently-attempted service from the manager, if one
        exists.

        @param force: True if the manager should be deleted regardless
        of whether it's a manager for self.url.

        @return: current service endpoint object or None if there is
            no current service
        """
        manager = self.getManager(force=force)
        if manager is not None:
            service = manager.current()
            self.destroyManager(force=force)
        else:
            service = None

        return service

    ### Lower-level methods

    def getSessionKey(self):
        """Get the session key for this starting URL and suffix

        @return: The session key
        @rtype: str
        """
        return self.PREFIX + self.session_key_suffix

    def getManager(self, force=False):
        """Extract the YadisServiceManager for this object's URL and
        suffix from the session.

        @param force: True if the manager should be returned
        regardless of whether it's a manager for self.url.

        @return: The current YadisServiceManager, if it's for this
            URL, or else None
        """
        manager = self.session.get(self.getSessionKey())
        if (manager is not None and (manager.forURL(self.url) or force)):
            return manager
        else:
            return None

    def createManager(self, services, yadis_url=None):
        """Create a new YadisService Manager for this starting URL and
        suffix, and store it in the session.

        @raises KeyError: When I already have a manager.

        @return: A new YadisServiceManager or None
        """
        key = self.getSessionKey()
        if self.getManager():
            raise KeyError('There is already a %r manager for %r' %
                           (key, self.url))

        if not services:
            return None

        manager = YadisServiceManager(self.url, yadis_url, services, key)
        manager.store(self.session)
        return manager

    def destroyManager(self, force=False):
        """Delete any YadisServiceManager with this starting URL and
        suffix from the session.

        If there is no service manager or the service manager is for a
        different URL, it silently does nothing.

        @param force: True if the manager should be deleted regardless
        of whether it's a manager for self.url.
        """
        if self.getManager(force=force) is not None:
            key = self.getSessionKey()
            del self.session[key]

########NEW FILE########
__FILENAME__ = parsehtml
__all__ = ['findHTMLMeta', 'MetaNotFound']

from HTMLParser import HTMLParser, HTMLParseError
import htmlentitydefs
import re

from openid.yadis.constants import YADIS_HEADER_NAME

# Size of the chunks to search at a time (also the amount that gets
# read at a time)
CHUNK_SIZE = 1024 * 16 # 16 KB

class ParseDone(Exception):
    """Exception to hold the URI that was located when the parse is
    finished. If the parse finishes without finding the URI, set it to
    None."""

class MetaNotFound(Exception):
    """Exception to hold the content of the page if we did not find
    the appropriate <meta> tag"""

re_flags = re.IGNORECASE | re.UNICODE | re.VERBOSE
ent_pat = r'''
&

(?: \#x (?P<hex> [a-f0-9]+ )
|   \# (?P<dec> \d+ )
|   (?P<word> \w+ )
)

;'''

ent_re = re.compile(ent_pat, re_flags)

def substituteMO(mo):
    if mo.lastgroup == 'hex':
        codepoint = int(mo.group('hex'), 16)
    elif mo.lastgroup == 'dec':
        codepoint = int(mo.group('dec'))
    else:
        assert mo.lastgroup == 'word'
        codepoint = htmlentitydefs.name2codepoint.get(mo.group('word'))

    if codepoint is None:
        return mo.group()
    else:
        return unichr(codepoint)

def substituteEntities(s):
    return ent_re.sub(substituteMO, s)

class YadisHTMLParser(HTMLParser):
    """Parser that finds a meta http-equiv tag in the head of a html
    document.

    When feeding in data, if the tag is matched or it will never be
    found, the parser will raise ParseDone with the uri as the first
    attribute.

    Parsing state diagram
    =====================

    Any unlisted input does not affect the state::

                1, 2, 5                       8
               +--------------------------+  +-+
               |                          |  | |
            4  |    3       1, 2, 5, 7    v  | v
        TOP -> HTML -> HEAD ----------> TERMINATED
        | |            ^  |               ^  ^
        | | 3          |  |               |  |
        | +------------+  +-> FOUND ------+  |
        |                  6         8       |
        | 1, 2                               |
        +------------------------------------+

      1. any of </body>, </html>, </head> -> TERMINATE
      2. <body> -> TERMINATE
      3. <head> -> HEAD
      4. <html> -> HTML
      5. <html> -> TERMINATE
      6. <meta http-equiv='X-XRDS-Location'> -> FOUND
      7. <head> -> TERMINATE
      8. Any input -> TERMINATE
    """
    TOP = 0
    HTML = 1
    HEAD = 2
    FOUND = 3
    TERMINATED = 4

    def __init__(self):
        HTMLParser.__init__(self)
        self.phase = self.TOP

    def _terminate(self):
        self.phase = self.TERMINATED
        raise ParseDone(None)

    def handle_endtag(self, tag):
        # If we ever see an end of head, body, or html, bail out right away.
        # [1]
        if tag in ['head', 'body', 'html']:
            self._terminate()

    def handle_starttag(self, tag, attrs):
        # if we ever see a start body tag, bail out right away, since
        # we want to prevent the meta tag from appearing in the body
        # [2]
        if tag=='body':
            self._terminate()

        if self.phase == self.TOP:
            # At the top level, allow a html tag or a head tag to move
            # to the head or html phase
            if tag == 'head':
                # [3]
                self.phase = self.HEAD
            elif tag == 'html':
                # [4]
                self.phase = self.HTML

        elif self.phase == self.HTML:
            # if we are in the html tag, allow a head tag to move to
            # the HEAD phase. If we get another html tag, then bail
            # out
            if tag == 'head':
                # [3]
                self.phase = self.HEAD
            elif tag == 'html':
                # [5]
                self._terminate()

        elif self.phase == self.HEAD:
            # If we are in the head phase, look for the appropriate
            # meta tag. If we get a head or body tag, bail out.
            if tag == 'meta':
                attrs_d = dict(attrs)
                http_equiv = attrs_d.get('http-equiv', '').lower()
                if http_equiv == YADIS_HEADER_NAME.lower():
                    raw_attr = attrs_d.get('content')
                    yadis_loc = substituteEntities(raw_attr)
                    # [6]
                    self.phase = self.FOUND
                    raise ParseDone(yadis_loc)

            elif tag in ['head', 'html']:
                # [5], [7]
                self._terminate()

    def feed(self, chars):
        # [8]
        if self.phase in [self.TERMINATED, self.FOUND]:
            self._terminate()

        return HTMLParser.feed(self, chars)

def findHTMLMeta(stream):
    """Look for a meta http-equiv tag with the YADIS header name.

    @param stream: Source of the html text
    @type stream: Object that implements a read() method that works
        like file.read

    @return: The URI from which to fetch the XRDS document
    @rtype: str

    @raises MetaNotFound: raised with the content that was
        searched as the first parameter.
    """
    parser = YadisHTMLParser()
    chunks = []

    while 1:
        chunk = stream.read(CHUNK_SIZE)
        if not chunk:
            # End of file
            break

        chunks.append(chunk)
        try:
            parser.feed(chunk)
        except HTMLParseError, why:
            # HTML parse error, so bail
            chunks.append(stream.read())
            break
        except ParseDone, why:
            uri = why[0]
            if uri is None:
                # Parse finished, but we may need the rest of the file
                chunks.append(stream.read())
                break
            else:
                return uri

    content = ''.join(chunks)
    raise MetaNotFound(content)

########NEW FILE########
__FILENAME__ = services
# -*- test-case-name: openid.test.test_services -*-

from openid.yadis.filters import mkFilter
from openid.yadis.discover import discover, DiscoveryFailure
from openid.yadis.etxrd import parseXRDS, iterServices, XRDSError

def getServiceEndpoints(input_url, flt=None):
    """Perform the Yadis protocol on the input URL and return an
    iterable of resulting endpoint objects.

    @param flt: A filter object or something that is convertable to
        a filter object (using mkFilter) that will be used to generate
        endpoint objects. This defaults to generating BasicEndpoint
        objects.

    @param input_url: The URL on which to perform the Yadis protocol

    @return: The normalized identity URL and an iterable of endpoint
        objects generated by the filter function.

    @rtype: (str, [endpoint])

    @raises DiscoveryFailure: when Yadis fails to obtain an XRDS document.
    """
    result = discover(input_url)
    try:
        endpoints = applyFilter(result.normalized_uri,
                                result.response_text, flt)
    except XRDSError, err:
        raise DiscoveryFailure(str(err), None)
    return (result.normalized_uri, endpoints)

def applyFilter(normalized_uri, xrd_data, flt=None):
    """Generate an iterable of endpoint objects given this input data,
    presumably from the result of performing the Yadis protocol.

    @param normalized_uri: The input URL, after following redirects,
        as in the Yadis protocol.


    @param xrd_data: The XML text the XRDS file fetched from the
        normalized URI.
    @type xrd_data: str

    """
    flt = mkFilter(flt)
    et = parseXRDS(xrd_data)

    endpoints = []
    for service_element in iterServices(et):
        endpoints.extend(
            flt.getServiceEndpoints(normalized_uri, service_element))

    return endpoints

########NEW FILE########
__FILENAME__ = xri
# -*- test-case-name: openid.test.test_xri -*-
"""Utility functions for handling XRIs.

@see: XRI Syntax v2.0 at the U{OASIS XRI Technical Committee<http://www.oasis-open.org/committees/tc_home.php?wg_abbrev=xri>}
"""

import re

XRI_AUTHORITIES = ['!', '=', '@', '+', '$', '(']

try:
    unichr(0x10000)
except ValueError:
    # narrow python build
    UCSCHAR = [
        (0xA0, 0xD7FF),
        (0xF900, 0xFDCF),
        (0xFDF0, 0xFFEF),
        ]

    IPRIVATE = [
        (0xE000, 0xF8FF),
        ]
else:
    UCSCHAR = [
        (0xA0, 0xD7FF),
        (0xF900, 0xFDCF),
        (0xFDF0, 0xFFEF),
        (0x10000, 0x1FFFD),
        (0x20000, 0x2FFFD),
        (0x30000, 0x3FFFD),
        (0x40000, 0x4FFFD),
        (0x50000, 0x5FFFD),
        (0x60000, 0x6FFFD),
        (0x70000, 0x7FFFD),
        (0x80000, 0x8FFFD),
        (0x90000, 0x9FFFD),
        (0xA0000, 0xAFFFD),
        (0xB0000, 0xBFFFD),
        (0xC0000, 0xCFFFD),
        (0xD0000, 0xDFFFD),
        (0xE1000, 0xEFFFD),
        ]

    IPRIVATE = [
        (0xE000, 0xF8FF),
        (0xF0000, 0xFFFFD),
        (0x100000, 0x10FFFD),
        ]


_escapeme_re = re.compile('[%s]' % (''.join(
    map(lambda (m, n): u'%s-%s' % (unichr(m), unichr(n)),
        UCSCHAR + IPRIVATE)),))


def identifierScheme(identifier):
    """Determine if this identifier is an XRI or URI.

    @returns: C{"XRI"} or C{"URI"}
    """
    if identifier.startswith('xri://') or (
        identifier and identifier[0] in XRI_AUTHORITIES):
        return "XRI"
    else:
        return "URI"


def toIRINormal(xri):
    """Transform an XRI to IRI-normal form."""
    if not xri.startswith('xri://'):
        xri = 'xri://' + xri
    return escapeForIRI(xri)


_xref_re = re.compile('\((.*?)\)')


def _escape_xref(xref_match):
    """Escape things that need to be escaped if they're in a cross-reference.
    """
    xref = xref_match.group()
    xref = xref.replace('/', '%2F')
    xref = xref.replace('?', '%3F')
    xref = xref.replace('#', '%23')
    return xref


def escapeForIRI(xri):
    """Escape things that need to be escaped when transforming to an IRI."""
    xri = xri.replace('%', '%25')
    xri = _xref_re.sub(_escape_xref, xri)
    return xri


def toURINormal(xri):
    """Transform an XRI to URI normal form."""
    return iriToURI(toIRINormal(xri))


def _percentEscapeUnicode(char_match):
    c = char_match.group()
    return ''.join(['%%%X' % (ord(octet),) for octet in c.encode('utf-8')])


def iriToURI(iri):
    """Transform an IRI to a URI by escaping unicode."""
    # According to RFC 3987, section 3.1, "Mapping of IRIs to URIs"
    return _escapeme_re.sub(_percentEscapeUnicode, iri)


def providerIsAuthoritative(providerID, canonicalID):
    """Is this provider ID authoritative for this XRI?

    @returntype: bool
    """
    # XXX: can't use rsplit until we require python >= 2.4.
    lastbang = canonicalID.rindex('!')
    parent = canonicalID[:lastbang]
    return parent == providerID


def rootAuthority(xri):
    """Return the root authority for an XRI.

    Example::

        rootAuthority("xri://@example") == "xri://@"

    @type xri: unicode
    @returntype: unicode
    """
    if xri.startswith('xri://'):
        xri = xri[6:]
    authority = xri.split('/', 1)[0]
    if authority[0] == '(':
        # Cross-reference.
        # XXX: This is incorrect if someone nests cross-references so there
        #   is another close-paren in there.  Hopefully nobody does that
        #   before we have a real xriparse function.  Hopefully nobody does
        #   that *ever*.
        root = authority[:authority.index(')') + 1]
    elif authority[0] in XRI_AUTHORITIES:
        # Other XRI reference.
        root = authority[0]
    else:
        # IRI reference.  XXX: Can IRI authorities have segments?
        segments = authority.split('!')
        segments = reduce(list.__add__,
            map(lambda s: s.split('*'), segments))
        root = segments[0]

    return XRI(root)


def XRI(xri):
    """An XRI object allowing comparison of XRI.

    Ideally, this would do full normalization and provide comparsion
    operators as per XRI Syntax.  Right now, it just does a bit of
    canonicalization by ensuring the xri scheme is present.

    @param xri: an xri string
    @type xri: unicode
    """
    if not xri.startswith('xri://'):
        xri = 'xri://' + xri
    return xri

########NEW FILE########
__FILENAME__ = xrires
# -*- test-case-name: openid.test.test_xrires -*-
"""XRI resolution.
"""

from urllib import urlencode
from openid import fetchers
from openid.yadis import etxrd
from openid.yadis.xri import toURINormal
from openid.yadis.services import iterServices

DEFAULT_PROXY = 'http://proxy.xri.net/'

class ProxyResolver(object):
    """Python interface to a remote XRI proxy resolver.
    """
    def __init__(self, proxy_url=DEFAULT_PROXY):
        self.proxy_url = proxy_url


    def queryURL(self, xri, service_type=None):
        """Build a URL to query the proxy resolver.

        @param xri: An XRI to resolve.
        @type xri: unicode

        @param service_type: The service type to resolve, if you desire
            service endpoint selection.  A service type is a URI.
        @type service_type: str

        @returns: a URL
        @returntype: str
        """
        # Trim off the xri:// prefix.  The proxy resolver didn't accept it
        # when this code was written, but that may (or may not) change for
        # XRI Resolution 2.0 Working Draft 11.
        qxri = toURINormal(xri)[6:]
        hxri = self.proxy_url + qxri
        args = {
            # XXX: If the proxy resolver will ensure that it doesn't return
            # bogus CanonicalIDs (as per Steve's message of 15 Aug 2006
            # 11:13:42), then we could ask for application/xrd+xml instead,
            # which would give us a bit less to process.
            '_xrd_r': 'application/xrds+xml',
            }
        if service_type:
            args['_xrd_t'] = service_type
        else:
            # Don't perform service endpoint selection.
            args['_xrd_r'] += ';sep=false'
        query = _appendArgs(hxri, args)
        return query


    def query(self, xri, service_types):
        """Resolve some services for an XRI.

        Note: I don't implement any service endpoint selection beyond what
        the resolver I'm querying does, so the Services I return may well
        include Services that were not of the types you asked for.

        May raise fetchers.HTTPFetchingError or L{etxrd.XRDSError} if
        the fetching or parsing don't go so well.

        @param xri: An XRI to resolve.
        @type xri: unicode

        @param service_types: A list of services types to query for.  Service
            types are URIs.
        @type service_types: list of str

        @returns: tuple of (CanonicalID, Service elements)
        @returntype: (unicode, list of C{ElementTree.Element}s)
        """
        # FIXME: No test coverage!
        services = []
        # Make a seperate request to the proxy resolver for each service
        # type, as, if it is following Refs, it could return a different
        # XRDS for each.

        canonicalID = None

        for service_type in service_types:
            url = self.queryURL(xri, service_type)
            response = fetchers.fetch(url)
            if response.status not in (200, 206):
                # XXX: sucks to fail silently.
                # print "response not OK:", response
                continue
            et = etxrd.parseXRDS(response.body)
            canonicalID = etxrd.getCanonicalID(xri, et)
            some_services = list(iterServices(et))
            services.extend(some_services)
        # TODO:
        #  * If we do get hits for multiple service_types, we're almost
        #    certainly going to have duplicated service entries and
        #    broken priority ordering.
        return canonicalID, services


def _appendArgs(url, args):
    """Append some arguments to an HTTP query.
    """
    # to be merged with oidutil.appendArgs when we combine the projects.
    if hasattr(args, 'items'):
        args = args.items()
        args.sort()

    if len(args) == 0:
        return url

    # According to XRI Resolution section "QXRI query parameters":
    #
    # """If the original QXRI had a null query component (only a leading
    #    question mark), or a query component consisting of only question
    #    marks, one additional leading question mark MUST be added when
    #    adding any XRI resolution parameters."""

    if '?' in url.rstrip('?'):
        sep = '&'
    else:
        sep = '?'

    return '%s%s%s' % (url, sep, urlencode(args))

########NEW FILE########
