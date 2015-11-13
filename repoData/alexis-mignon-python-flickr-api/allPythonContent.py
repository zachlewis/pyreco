__FILENAME__ = api
"""
    module: api
    
    This module provide an interface to the REST API through a
    syntax mimicking the method names described on Flickr site.

    The hierarchy of methods is built once when the module is loaded.

    Author : Alexis Mignon (c)
    email  : alexis.mignon_at_gmail.com
    Date   : 08/08/2011

"""

from .method_call import call_api
from . import auth
from . import reflection

__methods__ = reflection.__methods__.keys()
__methods__.sort()

__proxys__ = {}


def _get_proxy(name):
    """
        return the FlickrMethodProxy object with called 'name' from 
        the __proxys__ global dictionnary. Creates the objects if needed.
    """
    if name in __proxys__ :
        return __proxys__[name]
    else :
        p = FlickrMethodProxy(name)
        __proxys__[name] = p
        return p

def _get_children_methods(name):
    """
        Get the list of method names having 'name' for prefix
    """
    return [ m for m in __methods__ if m.startswith(name + ".") ]

class FlickrMethodProxy(object):
    """
        Proxy object to perform seamless direct calls to Flickr
        API.
    """
    def __init__(self, name):
        self.name = name
        children = _get_children_methods(name)
        for child in children :
            child_node = child[(len(self.name) + 1):].split(".")[0]
            child_prefix = "%s.%s" % (self.name, child_node)
            self.__dict__[child_node] = _get_proxy(child_prefix)
        if self.name in __methods__ :
            self.__doc__ = reflection.make_docstring(self.name)

    def __call__(self, **kwargs):
        return call_api(auth_handler=auth.AUTH_HANDLER, raw=True,
                        method=self.name, **kwargs)
    
    def __repr__(self):
        return self.name

    def __str__(self):
        return repr(self)
    
    @staticmethod
    def set_auth_handler(token):
        auth.set_auth_handler(token)
        
if __methods__ :
    flickr = _get_proxy("flickr")


########NEW FILE########
__FILENAME__ = auth
"""
    Authentication capabilities for the Flickr API.

    It implements the new authentication specifications of Flickr
    based on OAuth.

    The authentication process is in 3 steps.

    - Authorisation request:
    >>> a = AuthHandler(call_back_url)
    >>> a.get_authorization_url('write')
    print  ('http://www.flickr.com/services/oauth/'
            'authorize?oauth_token=xxxx&perms=write')

    - The user gives his authorization at the url given by
    'get_authorization_url' and is redirected to the 'call_back_url' with
    the `oauth_verifier` encoded in the url. This value can then be given to
    the `AuthHandler`:

    >>> a.set_verifier("66455xxxxx")

    - The authorization handler can then be set for the python session
      and will be automatically used when needed.

    >>> flickr_api.set_auth_handler(a)

    The authorization handler can also be saved and loaded:
    >>> a.write(filename)
    >>> a = AuthHandler.load(filename)

    Date: 06/08/2011
    Author: Alexis Mignon <alexis.mignon@gmail.com>
    Author: Christoffer Viken <christoffer@viken.me>

"""

try:  # fixes a reported bug. Seems that oauth can be packed in different ways.
    from oauth import oauth
except ImportError:
    import oauth

import time
import urlparse
import urllib2
from . import keys

TOKEN_REQUEST_URL = "https://www.flickr.com/services/oauth/request_token"
AUTHORIZE_URL = "https://www.flickr.com/services/oauth/authorize"
ACCESS_TOKEN_URL = "https://www.flickr.com/services/oauth/access_token"

AUTH_HANDLER = None


class AuthHandlerError(Exception):
    pass


class AuthHandler(object):
    def __init__(self, key=None, secret=None, callback=None,
                 access_token_key=None, access_token_secret=None,
                 request_token_key=None, request_token_secret=None):

        self.key = key or keys.API_KEY
        self.secret = secret or keys.API_SECRET

        if self.key is None or self.secret is None:
            raise ValueError("API keys have not been set.")

        if callback is None:
            callback = ("https://api.flickr.com/services/rest/"
                        "?method=flickr.test.echo&api_key=%s" % self.key)

        params = {
            'oauth_timestamp': str(int(time.time())),
            'oauth_signature_method': "HMAC-SHA1",
            'oauth_version': "1.0",
            'oauth_callback': callback,
            'oauth_nonce': oauth.generate_nonce(),
            'oauth_consumer_key': self.key
        }

        self.consumer = oauth.OAuthConsumer(key=self.key, secret=self.secret)
        if (access_token_key is None) and (request_token_key is None):
            req = oauth.OAuthRequest(http_method="GET",
                                     http_url=TOKEN_REQUEST_URL,
                                     parameters=params)
            req.sign_request(oauth.OAuthSignatureMethod_HMAC_SHA1(),
                             self.consumer, None)
            resp = urllib2.urlopen(req.to_url())
            request_token = dict(urlparse.parse_qsl(resp.read()))
            self.request_token = oauth.OAuthToken(
                request_token['oauth_token'],
                request_token['oauth_token_secret']
            )
            self.access_token = None
        elif request_token_key is not None:
            self.access_token = None
            self.request_token = oauth.OAuthToken(
                request_token_key,
                request_token_secret
            )
        else:
            self.request_token = None
            self.access_token = oauth.OAuthToken(
                access_token_key,
                access_token_secret
            )

    def get_authorization_url(self, perms='read'):
        if self.request_token is None:
            raise AuthHandlerError(
                ("Request token is not defined. This ususally means that the"
                 " access token has been loaded from a file.")
            )
        return "%s?oauth_token=%s&perms=%s" % (
            AUTHORIZE_URL, self.request_token.key, perms
        )

    def set_verifier(self, oauth_verifier):
        if self.request_token is None:
            raise AuthHandlerError(
                ("Request token is not defined. "
                 "This ususally means that the access token has been loaded "
                 "from a file.")
            )
        self.request_token.set_verifier(oauth_verifier)

        access_token_parms = {
            'oauth_consumer_key': self.key,
            'oauth_nonce': oauth.generate_nonce(),
            'oauth_signature_method': "HMAC-SHA1",
            'oauth_timestamp': str(int(time.time())),
            'oauth_token': self.request_token.key,
            'oauth_verifier': self.request_token.verifier
        }

        req = oauth.OAuthRequest(http_method="GET", http_url=ACCESS_TOKEN_URL,
                                 parameters=access_token_parms)
        req.sign_request(oauth.OAuthSignatureMethod_HMAC_SHA1(),
                         self.consumer, self.request_token)
        resp = urllib2.urlopen(req.to_url())
        access_token_resp = dict(urlparse.parse_qsl(resp.read()))
        self.access_token = oauth.OAuthToken(
            access_token_resp["oauth_token"],
            access_token_resp["oauth_token_secret"]
        )

    def complete_parameters(self, url, params={}, exclude_signature=[]):

        defaults = {
            'oauth_timestamp': str(int(time.time())),
            'oauth_nonce': oauth.generate_nonce(),
            'signature_method': "HMAC-SHA1",
            'oauth_token': self.access_token.key,
            'oauth_consumer_key': self.consumer.key,
        }

        excluded = {}
        for e in exclude_signature:
            excluded[e] = params.pop(e)

        defaults.update(params)
        req = oauth.OAuthRequest(http_method="POST", http_url=url,
                                 parameters=defaults)
        req.sign_request(oauth.OAuthSignatureMethod_HMAC_SHA1(), self.consumer,
                         self.access_token)
        req.parameters.update(excluded)

        return req

    def tofile(self, filename, include_api_keys=False):
        """ saves authentication information to a file.

    Parameters:
    ----------
    filename: str
        The name of the file to which we save the information.

    include_api_keys: bool, optional (default False)
        Should we include the api keys in the file ? For security issues, it
        is recommanded not to save the API keys information in several places
        and the default behaviour is thus not to save the API keys.
"""
        if self.access_token is None:
            raise AuthHandlerError("Access token not set yet.")
        with open(filename, "w") as f:
            if include_api_keys:
                f.write("\n".join([self.key, self.secret,
                        self.access_token.key, self.access_token.secret]))
            else:
                f.write("\n".join([self.access_token.key,
                                   self.access_token.secret]))

    def save(self, filename, include_api_keys=False):
        self.tofile(filename, include_api_keys)

    def write(self, filename, include_api_keys=False):
        self.tofile(filename, include_api_keys)

    def todict(self, include_api_keys=False):
        """
        Dumps the auth object to a dict,
        Optional inclusion of API-keys, in case you are using multiple.
        - include_api_keys: Whether API-keys should be included, False if you
        have control of them.
        """
        if self.access_token is not None:
            dump = {'access_token_key': self.access_token.key,
                    'access_token_secret': self.access_token.secret}
        else:
            dump = {'request_token_key': self.request_token.key,
                    'request_token_secret': self.request_token.secret}
        if include_api_keys:
            dump['api_key'] = self.key
            dump['api_secret'] = self.secret
        return dump

    @staticmethod
    def load(filename, set_api_keys=False):
        """ Load authentication information from a file.

    Parameters
    ----------
    filename: str
        The file in which authentication information is stored.

    set_api_keys: bool, optional (default False)
        If API keys are found in the file, should we use them to set the
        API keys globally.
        Default is False. The API keys should be stored separately from
        authentication information. The recommanded way is to use a
        `flickr_keys.py` file. Setting `set_api_keys=True` should be considered
        as a conveniency only for single user settings.
"""
        return AuthHandler.fromfile(filename, set_api_keys)

    @staticmethod
    def fromfile(filename, set_api_keys=False):
        """ Load authentication information from a file.

    Parameters
    ----------
    filename: str
        The file in which authentication information is stored.

    set_api_keys: bool, optional (default False)
        If API keys are found in the file, should we use them to set the
        API keys globally.
        Default is False. The API keys should be stored separately from
        authentication information. The recommanded way is to use a
        `flickr_keys.py` file. Setting `set_api_keys=True` should be considered
        as a conveniency only for single user settings.
"""
        with open(filename, "r") as f:
            keys_info = f.read().split("\n")
            try:
                key, secret, access_key, access_secret = keys_info
                if set_api_keys:
                    keys.set_keys(api_key=key, api_secret=secret)
            except ValueError:
                access_key, access_secret = keys_info
                key = keys.API_KEY
                secret = keys.API_SECRET
        return AuthHandler(key, secret, access_token_key=access_key,
                           access_token_secret=access_secret)

    @staticmethod
    def fromdict(input_dict):
        """
        Loads an auth object from a dict.
        Structure identical to dict returned by todict
        - input_dict: Dictionary to build from
        """
        access_key, access_secret = None, None
        request_token_key, request_token_secret = None, None
        try:
            if 'api_key' in input_dict:
                key = input_dict['api_key']
                secret = input_dict['api_secret']
            else:
                key = keys.API_KEY
                secret = keys.API_SECRET
            if 'access_token_key' in input_dict:
                access_key = input_dict['access_token_key']
                access_secret = input_dict['access_token_secret']
            elif 'request_token_key' in input_dict:
                request_token_key = input_dict['request_token_key']
                request_token_secret = input_dict['request_token_secret']
        except Exception:
            raise AuthHandlerError("Error occurred while processing data")

        return AuthHandler(key, secret, access_token_key=access_key,
                           access_token_secret=access_secret,
                           request_token_key=request_token_key,
                           request_token_secret=request_token_secret)

    @staticmethod
    def create(access_key, access_secret):
        return AuthHandler(access_token_key=access_key,
                           access_token_secret=access_secret)


def token_factory(filename=None, token_key=None, token_secret=None):
    if filename is None:
        if (token_key is None) or (token_secret is None):
            raise ValueError("token_secret and token_key cannot be None")
        return AuthHandler.create(token_key, token_secret)
    else:
        return AuthHandler.load(filename)


def set_auth_handler(auth_handler, set_api_keys=False):
    """ Set the authentication handler globally.

    Parameters
    ----------
    auth_handler: AuthHandler object or str
        If a string is given, it corresponds to the file in which
        authentication information is stored.

    set_api_keys: bool, optional (default False)
        If API keys are found in the file, should we use them to set the
        API keys globally.
        Default is False. The API keys should be stored separately from
        authentication information. The recommanded way is to use a
        `flickr_keys.py` file. Setting `set_api_keys=True` should be considered
        as a conveniency only for single user settings.
    """
    global AUTH_HANDLER
    if isinstance(auth_handler, basestring):
        ah = AuthHandler.load(auth_handler, set_api_keys)
        set_auth_handler(ah)
    else:
        AUTH_HANDLER = auth_handler

########NEW FILE########
__FILENAME__ = cache
# -*- encoding: utf-8 -*-
# This code comes form the Stuvel's "flickrapi" project.

#Copyright (c) 2007 by the respective coders, see
#http://www.stuvel.eu/projects/flickrapi

#This code is subject to the Python licence, as can be read on
#http://www.python.org/download/releases/2.5.2/license/

#For those without an internet connection, here is a summary. When this
#summary clashes with the Python licence, the latter will be applied.

#Permission is hereby granted, free of charge, to any person obtaining
#a copy of this software and associated documentation files (the
#"Software"), to deal in the Software without restriction, including
#without limitation the rights to use, copy, modify, merge, publish,
#distribute, sublicense, and/or sell copies of the Software, and to
#permit persons to whom the Software is furnished to do so, subject to
#the following conditions:

#The above copyright notice and this permission notice shall be
#included in all copies or substantial portions of the Software.

#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
#EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
#MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
#CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
#TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
#SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
''' Call result cache.

Designed to have the same interface as the `Django low-level cache API`_.
Heavily inspired (read: mostly copied-and-pasted) from the Django framework -
thanks to those guys for designing a simple and effective cache!

.. _`Django low-level cache API`:
    http://www.djangoproject.com/documentation/cache/#the-low-level-cache-api
'''

import threading
import time


class SimpleCache(object):
    '''Simple response cache for FlickrAPI calls.

    This stores max 50 entries, timing them out after 120 seconds:
    >>> cache = SimpleCache(timeout=120, max_entries=50)
    '''

    def __init__(self, timeout=300, max_entries=200):
        self.storage = {}
        self.expire_info = {}
        self.lock = threading.RLock()
        self.default_timeout = timeout
        self.max_entries = max_entries
        self.cull_frequency = 3

    def locking(method):
        '''Method decorator, ensures the method call is locked'''

        def locked(self, *args, **kwargs):
            self.lock.acquire()
            try:
                return method(self, *args, **kwargs)
            finally:
                self.lock.release()

        return locked

    @locking
    def get(self, key, default=None):
        '''Fetch a given key from the cache. If the key does not exist, return
        default, which itself defaults to None.
        '''

        now = time.time()
        exp = self.expire_info.get(key)
        if exp is None:
            return default
        elif exp < now:
            self.delete(key)
            return default

        return self.storage[key]

    @locking
    def set(self, key, value, timeout=None):
        '''Set a value in the cache. If timeout is given, that timeout will be
        used for the key; otherwise the default cache timeout will be used.
        '''

        if len(self.storage) >= self.max_entries:
            self.cull()
        if timeout is None:
            timeout = self.default_timeout
        self.storage[key] = value
        self.expire_info[key] = time.time() + timeout

    @locking
    def delete(self, key):
        '''Deletes a key from the cache, failing silently if it doesn't exist.
        '''

        if key in self.storage:
            del self.storage[key]
        if key in self.expire_info:
            del self.expire_info[key]

    @locking
    def has_key(self, key):
        '''Returns True if the key is in the cache and has not expired.'''
        return self.get(key) is not None

    @locking
    def __contains__(self, key):
        '''Returns True if the key is in the cache and has not expired.'''
        return key in self

    @locking
    def cull(self):
        '''Reduces the number of cached items'''

        doomed = [k for (i, k) in enumerate(self.storage)
                if i % self.cull_frequency == 0]
        for k in doomed:
            self.delete(k)

    @locking
    def __len__(self):
        '''Returns the number of cached items -- they might be expired
        though.
        '''

        return len(self.storage)

########NEW FILE########
__FILENAME__ = flickrerrors
""" Base Exception classes

"""


class FlickrError(Exception):
    """Base Exception class
    """
    pass


class FlickrAPIError(FlickrError):
    """ Exception for Flickr API Errors

    Parameters:
    -----------
    code: int
        Error code
    message: str
        Error message
    """
    def __init__(self, code, message):
        """Constructor

    Parameters:
    -----------
    code: int
        Error code
    message: str
        Error message
    """
        FlickrError.__init__(self, "%i : %s" % (code, message))
        self.code = code
        self.message = message

########NEW FILE########
__FILENAME__ = keys
API_KEY = None
API_SECRET = None

try:
    import flickr_keys
    API_KEY = flickr_keys.API_KEY
    API_SECRET = flickr_keys.API_SECRET
except ImportError:
    pass


def set_keys(api_key, api_secret):
    global API_KEY, API_SECRET
    API_KEY = api_key
    API_SECRET = api_secret

########NEW FILE########
__FILENAME__ = methods
__methods__ = {
u'flickr.photos.notes.delete': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The note id passed was not a valid note id', u'message': u'Note not found', u'code': u'1'
            }
            , {
        'text': u'The calling user does not have permission to delete the specified note', u'message': u'User cannot delete note', u'code': u'2'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the note to delete', u'optional': u'0', u'name': u'note_id'
            }
            ], u'description': u'Delete a note from a photo.', 'needslogin': True, u'name': u'flickr.photos.notes.delete'
        }
        , u'flickr.photos.comments.addComment': {
    u'errors': [{
        'text': u'The photo id passed was not a valid photo id', u'message': u'Photo not found.', u'code': u'1'
            }
            , {
        'text': u'Comment text can not be blank', u'message': u'Blank comment.', u'code': u'8'
            }
            , {
        'text': u'The user has reached the limit for number of comments posted during a specific time period.  Wait a bit and try again.', u'message': u'User is posting comments too fast.', u'code': u'9'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Add comment to a photo as the currently authenticated user.', 'needssigning': True, u'requiredperms': 'write', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photo to add a comment to.', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u'Text of the comment', u'optional': u'0', u'name': u'comment_text'
            }
            ], 'needslogin': True, u'response': u'<comment id="97777-72057594037941949-72057594037942602" />', u'name': u'flickr.photos.comments.addComment'
        }
        , u'flickr.activity.userPhotos': {
    u'errors': [{
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Returns a list of recent activity on photos belonging to the calling user. <b>Do not poll this method more than once an hour</b>.', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u"The timeframe in which to return updates for. This can be specified in days (<code>'2d'</code>) or hours (<code>'4h'</code>). The default behavoir is to return changes since the beginning of the previous user session.", u'optional': u'1', u'name': u'timeframe'
            }
            , {
        'text': u'Number of items to return per page. If this argument is omitted, it defaults to 10. The maximum allowed value is 50.', u'optional': u'1', u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': u'1', u'name': u'page'
            }
            ], 'needslogin': True, u'response': u'<items>\r\n\t<item type="photoset" id="395" owner="12037949754@N01" \r\n\t\tprimary="6521" secret="5a3cc65d72" server="2" \r\n\t\tcommentsold="1" commentsnew="1"\r\n\t\tviews="33" photos="7" more="0">\r\n\t\t<title>A set of photos</title>\r\n\t\t<activity>\r\n\t\t\t<event type="comment"\r\n\t\t\tuser="12037949754@N01" username="Bees"\r\n\t\t\tdateadded="1144086424">yay</event>\r\n\t\t</activity>\r\n\t</item>\r\n\r\n\t<item type="photo" id="10289" owner="12037949754@N01"\r\n\t\tsecret="34da0d3891" server="2"\r\n\t\tcommentsold="1" commentsnew="1"\r\n\t\tnotesold="0" notesnew="1"\r\n\t\tviews="47" faves="0" more="0">\r\n\t\t<title>A photo</title>\r\n\t\t<activity>\r\n\t\t\t<event type="comment"\r\n\t\t\tuser="12037949754@N01" username="Bees"\r\n\t\t\tdateadded="1133806604">test</event>\r\n\t\t\t<event type="note"\r\n\t\t\tuser="12037949754@N01" username="Bees"\r\n\t\t\tdateadded="1118785229">nice</event>\r\n\t\t</activity>\r\n\t</item>\r\n</items>', u'name': u'flickr.activity.userPhotos'
        }
        , u'flickr.groups.pools.getContext': {
    u'errors': [{
        'text': u'The photo id passed was not a valid photo id, or was the id of a photo that the calling user does not have permission to view.', u'message': u'Photo not found', u'code': u'1'
            }
            , {
        'text': u"The specified photo is not in the specified group's pool.", u'message': u'Photo not in pool', u'code': u'2'
            }
            , {
        'text': u"The specified group nsid was not a valid group or the caller does not have permission to view the group's pool.", u'message': u'Group not found', u'code': u'3'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.groups.pools.getContext', u'explanation': u'<p>See <a href="/services/api/flickr.photos.getContext.html">flickr.photos.getContext</a></p>', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photo to fetch the context for.', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u"The nsid of the group who's pool to fetch the photo's context for.", u'optional': u'0', u'name': u'group_id'
            }
            , {
        'text': u'', u'optional': u'1', u'name': u'num_prev'
            }
            , {
        'text': u'', u'optional': u'1', u'name': u'num_next'
            }
            , {
        'text': u'A comma-delimited list of extra information to fetch for each returned record. Currently supported fields are: description, license, date_upload, date_taken, owner_name, icon_server, original_format, last_update, geo, tags, machine_tags, o_dims, views, media, path_alias, url_sq, url_t, url_s, url_m, url_z, url_l, url_o', u'optional': u'1', u'name': u'extras'
            }
            ], 'needslogin': False, u'response': u'<prevphoto id="2980" secret="973da1e709"\r\n\ttitle="boo!" url="/photos/bees/2980/" /> \r\n<nextphoto id="2985" secret="059b664012"\r\n\ttitle="Amsterdam Amstel" url="/photos/bees/2985/" /> ', u'description': u'Returns next and previous photos for a photo in a group pool.'
        }
        , u'flickr.photosets.getContext': {
    u'errors': [{
        'text': u'The photo id passed was not a valid photo id, or was the id of a photo that the calling user does not have permission to view.', u'message': u'Photo not found', u'code': u'1'
            }
            , {
        'text': u'The specified photo is not in the specified set.', u'message': u'Photo not in set', u'code': u'2'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.photosets.getContext', u'explanation': u'<p>See <a href="/services/api/flickr.photos.getContext.html">flickr.photos.getContext</a></p>', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photo to fetch the context for.', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u"The id of the photoset for which to fetch the photo's context.", u'optional': u'0', u'name': u'photoset_id'
            }
            , {
        'text': u'', u'optional': u'1', u'name': u'num_prev'
            }
            , {
        'text': u'', u'optional': u'1', u'name': u'num_next'
            }
            , {
        'text': u'A comma-delimited list of extra information to fetch for each returned record. Currently supported fields are: description, license, date_upload, date_taken, owner_name, icon_server, original_format, last_update, geo, tags, machine_tags, o_dims, views, media, path_alias, url_sq, url_t, url_s, url_m, url_z, url_l, url_o', u'optional': u'1', u'name': u'extras'
            }
            ], 'needslogin': False, u'response': u'<prevphoto id="2980" secret="973da1e709"\r\n\ttitle="boo!" url="/photos/bees/2980/" /> \r\n<nextphoto id="2985" secret="059b664012"\r\n\ttitle="Amsterdam Amstel" url="/photos/bees/2985/" /> ', u'description': u'Returns next and previous photos for a photo in a set.'
        }
        , u'flickr.people.getPublicGroups': {
    u'errors': [{
        'text': u'The user id passed did not match a Flickr user.', u'message': u'User not found', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.people.getPublicGroups', u'explanation': u'<p>The <code>admin</code> attribute indicates whether the user is an administrator of the group. The <code>eighteenplus</code> attribute indicates if the group is visible to members over 18 only. The <code>invite_only</code> attribute indicates whether a user can join the group without administrator approval.</p>', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The NSID of the user to fetch groups for.', u'optional': u'0', u'name': u'user_id'
            }
            , {
        'text': u'Include public groups that require <a href="http://www.flickr.com/help/groups/#10">an invitation</a> or administrator approval to join.', u'optional': u'1', u'name': u'invitation_only'
            }
            ], 'needslogin': False, u'response': u'<groups>\r\n\t<group nsid="34427469792@N01" name="FlickrCentral"\r\n\t\tadmin="0" eighteenplus="0" invitation_only="0" /> \r\n\t<group nsid="37114057624@N01" name="Cal\'s Test Group"\r\n\t\tadmin="1" eighteenplus="0" invitation_only="1" /> \r\n\t<group nsid="34955637532@N01" name="18+ Group"\r\n\t\tadmin="1" eighteenplus="1" invitation_only="0" /> \r\n</groups>', u'description': u'Returns the list of public groups a user is a member of.'
        }
        , u'flickr.tags.getClusters': {
    u'errors': [{
        'text': u'The tag was invalid or no cluster exists for that tag.', u'message': u'Tag cluster not found', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Gives you a list of tag clusters for the given tag.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The tag to fetch clusters for.', u'optional': u'0', u'name': u'tag'
            }
            ], 'needslogin': False, u'response': u'<clusters source="cows" total="2">\r\n\t<cluster total="3">\r\n\t\t<tag>farm</tag>\r\n\t\t<tag>animals</tag>\r\n\t\t<tag>cattle</tag>\r\n\t</cluster>\r\n\t<cluster total="3">\r\n\t\t<tag>green</tag>\r\n\t\t<tag>landscape</tag>\r\n\t\t<tag>countryside</tag>\r\n\t</cluster>\r\n</clusters>', u'name': u'flickr.tags.getClusters'
        }
        , u'flickr.photos.geo.photosForLocation': {
    'needssigning': True, u'requiredperms': 'read', u'errors': [{
        'text': u'One or more required arguments was missing from the method call.', u'message': u'Required arguments missing', u'code': u'1'
            }
            , {
        'text': u'The latitude argument failed validation.', u'message': u'Not a valid latitude', u'code': u'2'
            }
            , {
        'text': u'The longitude argument failed validation.', u'message': u'Not a valid longitude', u'code': u'3'
            }
            , {
        'text': u'The accuracy argument failed validation.', u'message': u'Not a valid accuracy', u'code': u'4'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The latitude whose valid range is -90 to 90. Anything more than 6 decimal places will be truncated.', u'optional': u'0', u'name': u'lat'
            }
            , {
        'text': u'The longitude whose valid range is -180 to 180. Anything more than 6 decimal places will be truncated.', u'optional': u'0', u'name': u'lon'
            }
            , {
        'text': u'Recorded accuracy level of the location information. World level is 1, Country is ~3, Region ~6, City ~11, Street ~16. Current range is 1-16. Defaults to 16 if not specified.', u'optional': u'1', u'name': u'accuracy'
            }
            , {
        'text': u'A comma-delimited list of extra information to fetch for each returned record. Currently supported fields are: <code>description</code>, <code>license</code>, <code>date_upload</code>, <code>date_taken</code>, <code>owner_name</code>, <code>icon_server</code>, <code>original_format</code>, <code>last_update</code>, <code>geo</code>, <code>tags</code>, <code>machine_tags</code>, <code>o_dims</code>, <code>views</code>, <code>media</code>, <code>path_alias</code>, <code>url_sq</code>, <code>url_t</code>, <code>url_s</code>, <code>url_q</code>, <code>url_m</code>, <code>url_n</code>, <code>url_z</code>, <code>url_c</code>, <code>url_l</code>, <code>url_o</code>', u'optional': 1, u'name': u'extras'
            }
            , {
        'text': u'Number of photos to return per page. If this argument is omitted, it defaults to 100. The maximum allowed value is 500.', u'optional': 1, u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': 1, u'name': u'page'
            }
            ], u'description': u'Return a list of photos for the calling user at a specific latitude, longitude and accuracy', 'needslogin': True, u'name': u'flickr.photos.geo.photosForLocation'
        }
        , u'flickr.places.placesForUser': {
    u'errors': [{
        'text': u'Places for user have been disabled or are otherwise not available.', u'message': u'Places for user are not available at this time', u'code': u'1'
            }
            , {
        'text': u'One or more of the required parameters was not included with your request.', u'message': u'Required parameter missing', u'code': u'2'
            }
            , {
        'text': u'An invalid place type was included with your request.', u'message': u'Not a valid place type', u'code': u'3'
            }
            , {
        'text': u'An invalid Places (or WOE) identifier was included with your request.', u'message': u'Not a valid Place ID', u'code': u'4'
            }
            , {
        'text': u'The threshold passed was invalid. ', u'message': u'Not a valid threshold', u'code': u'5'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Return a list of the top 100 unique places clustered by a given placetype for a user. ', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The numeric ID for a specific place type to cluster photos by. <br /><br />\r\n\r\nValid place type IDs are :\r\n\r\n<ul>\r\n<li><strong>22</strong>: neighbourhood</li>\r\n<li><strong>7</strong>: locality</li>\r\n<li><strong>8</strong>: region</li>\r\n<li><strong>12</strong>: country</li>\r\n<li><strong>29</strong>: continent</li>\r\n</ul>\r\n<br />\r\n<span style="font-style:italic;">The "place_type" argument has been deprecated in favor of the "place_type_id" argument. It won\'t go away but it will not be added to new methods. A complete list of place type IDs is available using the <a href="http://www.flickr.com/services/api/flickr.places.getPlaceTypes.html">flickr.places.getPlaceTypes</a> method. (While optional, you must pass either a valid place type or place type ID.)</span>', u'optional': u'1', u'name': u'place_type_id'
            }
            , {
        'text': u'A specific place type to cluster photos by. <br /><br />\r\n\r\nValid place types are :\r\n\r\n<ul>\r\n<li><strong>neighbourhood</strong> (and neighborhood)</li>\r\n<li><strong>locality</strong></li>\r\n<li><strong>region</strong></li>\r\n<li><strong>country</strong></li>\r\n<li><strong>continent</strong></li>\r\n</ul>\r\n<br /><span style="font-style:italic;">(While optional, you must pass either a valid place type or place type ID.)</span>', u'optional': u'1', u'name': u'place_type'
            }
            , {
        'text': u'A Where on Earth identifier to use to filter photo clusters. For example all the photos clustered by <strong>locality</strong> in the United States (WOE ID <strong>23424977</strong>).<br /><br />\r\n<span style="font-style:italic;">(While optional, you must pass either a valid Places ID or a WOE ID.)</span>', u'optional': u'1', u'name': u'woe_id'
            }
            , {
        'text': u'A Flickr Places identifier to use to filter photo clusters. For example all the photos clustered by <strong>locality</strong> in the United States (Place ID <strong>4KO02SibApitvSBieQ</strong>).<br /><br />\r\n<span style="font-style:italic;">(While optional, you must pass either a valid Places ID or a WOE ID.)</span>', u'optional': u'1', u'name': u'place_id'
            }
            , {
        'text': u'The minimum number of photos that a place type must have to be included. If the number of photos is lowered then the parent place type for that place will be used.<br /><br />\r\n\r\nFor example if you only have <strong>3</strong> photos taken in the locality of Montreal</strong> (WOE ID 3534) but your threshold is set to <strong>5</strong> then those photos will be "rolled up" and included instead with a place record for the region of Quebec (WOE ID 2344924).', u'optional': u'1', u'name': u'threshold'
            }
            , {
        'text': u'Minimum upload date. Photos with an upload date greater than or equal to this value will be returned. The date should be in the form of a unix timestamp.', u'optional': u'1', u'name': u'min_upload_date'
            }
            , {
        'text': u'Maximum upload date. Photos with an upload date less than or equal to this value will be returned. The date should be in the form of a unix timestamp.', u'optional': u'1', u'name': u'max_upload_date'
            }
            , {
        'text': u'Minimum taken date. Photos with an taken date greater than or equal to this value will be returned. The date should be in the form of a mysql datetime.', u'optional': u'1', u'name': u'min_taken_date'
            }
            , {
        'text': u'Maximum taken date. Photos with an taken date less than or equal to this value will be returned. The date should be in the form of a mysql datetime.', u'optional': u'1', u'name': u'max_taken_date'
            }
            ], 'needslogin': True, u'response': u'<places total="1">\r\n   <place place_id="kH8dLOubBZRvX_YZ" woeid="2487956"\r\n               latitude="37.779" longitude="-122.420"\r\n               place_url="/United+States/California/San+Francisco"\r\n               place_type="locality"\r\n               photo_count="156">San Francisco, California</place>\r\n</places>', u'name': u'flickr.places.placesForUser'
        }
        , u'flickr.photos.getAllContexts': {
    u'errors': [{
        'text': u'The photo id passed was not the id of a valid photo.', u'message': u'Photo not found', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Returns all visible sets and pools the photo belongs to.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The photo to return information for.', u'optional': u'0', u'name': u'photo_id'
            }
            ], 'needslogin': False, u'response': u'<set id="392" title="\u8bb0\u5fc6\u7fa4\u7ec4" />\r\n<pool id="34427465471@N01" title="FlickrDiscuss" />', u'name': u'flickr.photos.getAllContexts'
        }
        , u'flickr.urls.getUserProfile': {
    u'errors': [{
        'text': u'The NSID specified was not a valid user.', u'message': u'User not found', u'code': u'1'
            }
            , {
        'text': u'No user_id was passed and the calling user was not logged in.', u'message': u'No user specified', u'code': u'2'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u"Returns the url to a user's profile.", 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The NSID of the user to fetch the url for. If omitted, the calling user is assumed.', u'optional': u'1', u'name': u'user_id'
            }
            ], 'needslogin': False, u'response': u'<user nsid="12037949754@N01" url="http://www.flickr.com/people/bees/" />', u'name': u'flickr.urls.getUserProfile'
        }
        , u'flickr.photos.getPerms': {
    u'errors': [{
        'text': u'The photo id passed was not a valid photo id of a photo belonging to the calling user.', u'message': u'Photo not found', u'code': u'1'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Get permissions for a photo.', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photo to get permissions for.', u'optional': u'0', u'name': u'photo_id'
            }
            ], 'needslogin': True, u'response': u'<perms id="2733" ispublic="1" isfriend="1" isfamily="0" permcomment="0" permaddmeta="1" /> ', u'name': u'flickr.photos.getPerms'
        }
        , u'flickr.tags.getListUserPopular': {
    u'errors': [{
        'text': u'The user NSID passed was not a valid user NSID and the calling user was not logged in.\r\n', u'message': u'User not found', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Get the popular tags for a given user (or the currently logged in user).', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The NSID of the user to fetch the tag list for. If this argument is not specified, the currently logged in user (if any) is assumed.', u'optional': u'1', u'name': u'user_id'
            }
            , {
        'text': u'Number of popular tags to return. defaults to 10 when this argument is not present.', u'optional': u'1', u'name': u'count'
            }
            ], 'needslogin': False, u'response': u'<who id="12037949754@N01">\r\n\t<tags>\r\n\t\t<tag count="10">bar</tag> \r\n\t\t<tag count="11">foo</tag> \r\n\t\t<tag count="147">gull</tag> \r\n\t\t<tag count="3">tags</tag> \r\n\t\t<tag count="3">test</tag> \r\n\t</tags>\r\n</who>', u'name': u'flickr.tags.getListUserPopular'
        }
        , u'flickr.photos.geo.correctLocation': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'Before users may assign location data to a photo they must define who, by default, may view that information. Users can edit this preference at <a href="http://www.flickr.com/account/geo/privacy/">http://www.flickr.com/account/geo/privacy/</a>', u'message': u'User has not configured default viewing settings for location data.', u'code': u'1'
            }
            , {
        'text': u'No place ID was passed to the method', u'message': u'Missing place ID', u'code': u'2'
            }
            , {
        'text': u'The place ID passed to the method could not be identified', u'message': u'Not a valid place ID', u'code': u'3'
            }
            , {
        'text': u'There was an error trying to correct the location.', u'message': u'Server error correcting location.', u'code': u'4'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The ID of the photo whose WOE location is being corrected.', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u'A Flickr Places ID. (While optional, you must pass either a valid Places ID or a WOE ID.)', u'optional': u'1', u'name': u'place_id'
            }
            , {
        'text': u'A Where On Earth (WOE) ID. (While optional, you must pass either a valid Places ID or a WOE ID.)', u'optional': u'1', u'name': u'woe_id'
            }
            , {
        'text': u'The venue ID for a Foursquare location. (If not passed in with correction, any existing foursquare venue will be removed).', u'optional': u'0', u'name': u'foursquare_id'
            }
            ], u'description': u'', 'needslogin': True, u'name': u'flickr.photos.geo.correctLocation'
        }
        , u'flickr.photosets.getInfo': {
    u'errors': [{
        'text': u'The photoset id was not valid.', u'message': u'Photoset not found', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Gets information about a photoset.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The ID of the photoset to fetch information for.', u'optional': u'0', u'name': u'photoset_id'
            }
            ], 'needslogin': False, u'response': u'<photoset id="72157624618609504" owner="34427469121@N01" primary="4847770787" secret="6abd09a292" server="4153" farm="5" photos="55" count_views="523" count_comments="1" count_photos="43" count_videos="12" can_comment="1" date_create="1280530593" date_update="1308091378">\r\n    <title>Mah Kittehs</title>\r\n    <description>Sixty and Niner. Born on the 3rd of May, 2010, or thereabouts. Came to my place on Thursday, July 29, 2010.</description>\r\n</photoset>', u'name': u'flickr.photosets.getInfo'
        }
        , u'flickr.places.getInfoByUrl': {
    u'errors': [{
        'text': u'The flickr.com/places URL was not passed with the API method.', u'message': u'Place URL required.', u'code': u'2'
            }
            , {
        'text': u'Unable to find a valid place for the places URL.', u'message': u'Place not found.', u'code': u'3'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Lookup information about a place, by its flickr.com/places URL.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'A flickr.com/places URL in the form of /country/region/city. For example: /Canada/Quebec/Montreal', u'optional': u'0', u'name': u'url'
            }
            ], 'needslogin': False, u'response': u'<place place_id="4hLQygSaBJ92" woeid="3534"\r\n   latitude="45.512" longitude="-73.554"\r\n   place_url="/Canada/Quebec/Montreal" place_type="locality"\r\n   has_shapedata="1">\r\n   <locality place_id="4hLQygSaBJ92" woeid="3534"\r\n      latitude="45.512" longitude="-73.554"\r\n      place_url="/Canada/Quebec/Montreal">Montreal</locality>\r\n   <county place_id="cFBi9x6bCJ8D5rba1g" woeid="29375198"\r\n      latitude="45.551" longitude="-73.600" \r\n      place_url="/cFBi9x6bCJ8D5rba1g">Montr\xe9al</county>\r\n   <region place_id="CrZUvXebApjI0.72" woeid="2344924" \r\n      latitude="53.890" longitude="-68.429"\r\n      place_url="/Canada/Quebec">Quebec</region>\r\n   <country place_id="EESRy8qbApgaeIkbsA" woeid="23424775"\r\n      latitude="62.358" longitude="-96.582" \r\n      place_url="/Canada">Canada</country>\r\n   <shapedata created="1223513357" alpha="0.012359619140625"\r\n      count_points="34778" count_edges="52">\r\n      <polylines>\r\n         <polyline>\r\n            45.427627563477,-73.589645385742 45.428966522217,-73.587898254395, etc...\r\n         </polyline>\r\n      </polylines>\r\n   </shapedata>\r\n</place>', u'name': u'flickr.places.getInfoByUrl'
        }
        , u'flickr.places.getChildrenWithPhotosPublic': {
    u'errors': [{
        'text': u'One or more required parameter is missing from the API call.', u'message': u'Required parameter missing', u'code': u'1'
            }
            , {
        'text': u'An invalid Places (or WOE) ID was passed with the API call.', u'message': u'Not a valid Places ID', u'code': u'2'
            }
            , {
        'text': u'No place could be found for the Places (or WOE) ID passed to the API call.', u'message': u'Place not found', u'code': u'3'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Return a list of locations with public photos that are parented by a Where on Earth (WOE) or Places ID.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'A Flickr Places ID. (While optional, you must pass either a valid Places ID or a WOE ID.)', u'optional': u'1', u'name': u'place_id'
            }
            , {
        'text': u'A Where On Earth (WOE) ID. (While optional, you must pass either a valid Places ID or a WOE ID.)', u'optional': u'1', u'name': u'woe_id'
            }
            ], 'needslogin': False, u'response': u'<places total="79">\r\n   <place place_id="HznQfdKbB58biy8sdA" woeid="26332794"\r\n      latitude="45.498" longitude="-73.575"\r\n      place_url="/Canada/Quebec/Montreal  /Montreal+Golden+Square+Mile"\r\n      place_type="neighbourhood" photo_count="2717">\r\n      Montreal Golden Square Mile, Montreal, QC, CA, Canada\r\n   </place>\r\n   <place place_id="K1rYWmGbB59rwn7lOA" woeid="26332799"\r\n      latitude="45.502" longitude="-73.578"\r\n      place_url="/Canada/Quebec/Montreal/Downtown+Montr%C3%A9al"\r\n      place_type="neighbourhood" photo_count="2317">\r\n      Downtown Montr\xe9al, Montreal, QC, CA, Canada\r\n  </place>\r\n\r\n   <!-- and so on... -->\r\n\r\n</places>', u'name': u'flickr.places.getChildrenWithPhotosPublic'
        }
        , u'flickr.photos.geo.removeLocation': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The photo id was either invalid or was for a photo not viewable by the calling user.', u'message': u'Photo not found', u'code': u'1'
            }
            , {
        'text': u'The specified photo has not been geotagged - there is nothing to remove.', u'message': u'Photo has no location information', u'code': u'2'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photo you want to remove location data from.', u'optional': u'0', u'name': u'photo_id'
            }
            ], u'description': u'Removes the geo data associated with a photo.', 'needslogin': True, u'name': u'flickr.photos.geo.removeLocation'
        }
        , u'flickr.contacts.getListRecentlyUploaded': {
    'needssigning': True, u'requiredperms': 'read', u'errors': [{
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'Limits the resultset to contacts that have uploaded photos since this date. The date should be in the form of a Unix timestamp.\r\n\r\nThe default offset is (1) hour and the maximum (24) hours. ', u'optional': u'1', u'name': u'date_lastupload'
            }
            , {
        'text': u'Limit the result set to all contacts or only those who are friends or family. Valid options are:\r\n\r\n<ul>\r\n<li><strong>ff</strong> friends and family</li>\r\n<li><strong>all</strong> all your contacts</li>\r\n</ul>\r\nDefault value is "all".', u'optional': u'1', u'name': u'filter'
            }
            ], u'description': u"Return a list of contacts for a user who have recently uploaded photos along with the total count of photos uploaded.<br /><br />\r\n\r\nThis method is still considered experimental. We don't plan for it to change or to go away but so long as this notice is present you should write your code accordingly.", 'needslogin': True, u'name': u'flickr.contacts.getListRecentlyUploaded'
        }
        , u'flickr.groups.members.getList': {
    u'errors': [{
        'text': u'', u'message': u'Group not found', u'code': u'1'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u"Get a list of the members of a group.  The call must be signed on behalf of a Flickr member, and the ability to see the group membership will be determined by the Flickr member's group privileges.", 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'Return a list of members for this group.  The group must be viewable by the Flickr member on whose behalf the API call is made.', u'optional': u'0', u'name': u'group_id'
            }
            , {
        'text': u'Comma separated list of member types\r\n<ul>\r\n<li>2: member</li>\r\n<li>3: moderator</li>\r\n<li>4: admin</li>\r\n</ul>\r\nBy default returns all types.  (Returning super rare member type "1: narwhal" isn\'t supported by this API method)', u'optional': u'1', u'name': u'membertypes'
            }
            , {
        'text': u'Number of members to return per page. If this argument is omitted, it defaults to 100. The maximum allowed value is 500.', u'optional': u'1', u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': u'1', u'name': u'page'
            }
            ], 'needslogin': True, u'response': u'<members page="1" pages="1" perpage="100" total="33">\r\n<member nsid="123456@N01" username="foo" iconserver="1" iconfarm="1" membertype="2"/>\r\n<member nsid="118210@N07" username="kewlchops666" iconserver="0" iconfarm="0" membertype="4"/>\r\n<member nsid="119377@N07" username="Alpha Shanan" iconserver="0" iconfarm="0" membertype="2"/>\r\n<member nsid="67783977@N00" username="fakedunstanp1" iconserver="1003" iconfarm="2" membertype="3"/>\r\n...\r\n</members>', u'name': u'flickr.groups.members.getList'
        }
        , u'flickr.stats.getPhotoReferrers': {
    u'errors': [{
        'text': u'The user you have requested stats has not enabled stats on their account.', u'message': u'User does not have stats', u'code': u'1'
            }
            , {
        'text': u'No stats are available for the date requested. Flickr only keeps stats data for the last 28 days.', u'message': u'No stats for that date', u'code': u'2'
            }
            , {
        'text': u'The date provided could not be parsed', u'message': u'Invalid date', u'code': u'3'
            }
            , {
        'text': u'The photo id was either invalid or was for a photo not owned by the calling user.', u'message': u'Photo not found', u'code': u'4'
            }
            , {
        'text': u'The domain provided is not in the expected format.', u'message': u'Invalid domain', u'code': u'5'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.stats.getPhotoReferrers', u'explanation': u'<p>There is one <code>&lt;referrer&gt;</code> element for each referring page, with attributes for the url and the number of views.</p>\r\n\r\n<p>Where the referring page is a search engine and we have identified the search term it will be given in the searchterm attribute.</p>', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'Stats will be returned for this date. This should be in either be in YYYY-MM-DD or unix timestamp format.\r\n\r\nA day according to Flickr Stats starts at midnight GMT for all users, and timestamps will automatically be rounded down to the start of the day.', u'optional': u'0', u'name': u'date'
            }
            , {
        'text': u'The domain to return referrers for. This should be a hostname (eg: "flickr.com") with no protocol or pathname.', u'optional': u'0', u'name': u'domain'
            }
            , {
        'text': u'The id of the photo to get stats for. If not provided, stats for all photos will be returned.', u'optional': u'1', u'name': u'photo_id'
            }
            , {
        'text': u'Number of referrers to return per page. If this argument is omitted, it defaults to 25. The maximum allowed value is 100.', u'optional': u'1', u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': u'1', u'name': u'page'
            }
            ], 'needslogin': True, u'response': u'<domain page="1" perpage="25" pages="1" total="3" name="flickr.com">\r\n\t<referrer url="http://flickr.com/" views="11"/>\r\n\t<referrer url="http://flickr.com/photos/friends/" views="8"/>\r\n\t<referrer url="http://flickr.com/search/?q=stats+api" views="2" searchterm="stats api"/>\r\n</domain>', u'description': u'Get a list of referrers from a given domain to a photo'
        }
        , u'flickr.contacts.getList': {
    u'errors': [{
        'text': u'The possible values are: name and time.', u'message': u'Invalid sort parameter.', u'code': u'1'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Get a list of contacts for the calling user.', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'An optional filter of the results. The following values are valid:<br />\r\n&nbsp;\r\n<dl>\r\n\t<dt><b><code>friends</code></b></dt>\r\n\t<dl>Only contacts who are friends (and not family)</dl>\r\n\r\n\t<dt><b><code>family</code></b></dt>\r\n\t<dl>Only contacts who are family (and not friends)</dl>\r\n\r\n\t<dt><b><code>both</code></b></dt>\r\n\t<dl>Only contacts who are both friends and family</dl>\r\n\r\n\t<dt><b><code>neither</code></b></dt>\r\n\t<dl>Only contacts who are neither friends nor family</dl>\r\n</dl>', u'optional': u'1', u'name': u'filter'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': u'1', u'name': u'page'
            }
            , {
        'text': u'Number of photos to return per page. If this argument is omitted, it defaults to 1000. The maximum allowed value is 1000.', u'optional': u'1', u'name': u'per_page'
            }
            , {
        'text': u'The order in which to sort the returned contacts. Defaults to name. The possible values are: name and time.', u'optional': u'1', u'name': u'sort'
            }
            ], 'needslogin': True, u'response': u'<contacts page="1" pages="1" perpage="1000" total="3">\r\n\t<contact nsid="12037949629@N01" username="Eric" iconserver="1"\r\n\t\trealname="Eric Costello"\r\n\t\tfriend="1" family="0" ignored="1" /> \r\n\t<contact nsid="12037949631@N01" username="neb" iconserver="1"\r\n\t\trealname="Ben Cerveny"\r\n\t\tfriend="0" family="0" ignored="0" /> \r\n\t<contact nsid="41578656547@N01" username="cal_abc" iconserver="1"\r\n\t\trealname="Cal Henderson"\r\n\t\tfriend="1" family="1" ignored="0" />\r\n</contacts>', u'name': u'flickr.contacts.getList'
        }
        , u'flickr.stats.getPhotosetStats': {
    u'errors': [{
        'text': u'The user you have requested stats has not enabled stats on their account.', u'message': u'User does not have stats', u'code': u'1'
            }
            , {
        'text': u'No stats are available for the date requested. Flickr only keeps stats data for the last 28 days.', u'message': u'No stats for that date', u'code': u'2'
            }
            , {
        'text': u'The date provided could not be parsed', u'message': u'Invalid date', u'code': u'3'
            }
            , {
        'text': u'The photoset id was either invalid or was for a set not owned by the calling user.', u'message': u'Photoset not found', u'code': u'4'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Get the number of views on a photoset for a given date.', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'Stats will be returned for this date. This should be in either be in YYYY-MM-DD or unix timestamp format.\r\n\r\nA day according to Flickr Stats starts at midnight GMT for all users, and timestamps will automatically be rounded down to the start of the day.', u'optional': u'0', u'name': u'date'
            }
            , {
        'text': u'The id of the photoset to get stats for.', u'optional': u'0', u'name': u'photoset_id'
            }
            ], 'needslogin': True, u'response': u'<stats views="24" comments="1" />', u'name': u'flickr.stats.getPhotosetStats'
        }
        , u'flickr.places.placesForTags': {
    u'errors': [{
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Return a list of the top 100 unique places clustered by a given placetype for set of tags or machine tags. ', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The numeric ID for a specific place type to cluster photos by. <br /><br />\r\n\r\nValid place type IDs are :\r\n\r\n<ul>\r\n<li><strong>22</strong>: neighbourhood</li>\r\n<li><strong>7</strong>: locality</li>\r\n<li><strong>8</strong>: region</li>\r\n<li><strong>12</strong>: country</li>\r\n<li><strong>29</strong>: continent</li>\r\n</ul>', u'optional': u'0', u'name': u'place_type_id'
            }
            , {
        'text': u'A Where on Earth identifier to use to filter photo clusters. For example all the photos clustered by <strong>locality</strong> in the United States (WOE ID <strong>23424977</strong>).\r\n<br /><br />\r\n<span style="font-style:italic;">(While optional, you must pass either a valid Places ID or a WOE ID.)</span>', u'optional': u'1', u'name': u'woe_id'
            }
            , {
        'text': u'A Flickr Places identifier to use to filter photo clusters. For example all the photos clustered by <strong>locality</strong> in the United States (Place ID <strong>4KO02SibApitvSBieQ</strong>).\r\n<br /><br />\r\n<span style="font-style:italic;">(While optional, you must pass either a valid Places ID or a WOE ID.)</span>', u'optional': u'1', u'name': u'place_id'
            }
            , {
        'text': u'The minimum number of photos that a place type must have to be included. If the number of photos is lowered then the parent place type for that place will be used.<br /><br />\r\n\r\nFor example if you only have <strong>3</strong> photos taken in the locality of Montreal</strong> (WOE ID 3534) but your threshold is set to <strong>5</strong> then those photos will be "rolled up" and included instead with a place record for the region of Quebec (WOE ID 2344924).', u'optional': u'1', u'name': u'threshold'
            }
            , {
        'text': u'A comma-delimited list of tags. Photos with one or more of the tags listed will be returned.', u'optional': u'1', u'name': u'tags'
            }
            , {
        'text': u"Either 'any' for an OR combination of tags, or 'all' for an AND combination. Defaults to 'any' if not specified.", u'optional': u'1', u'name': u'tag_mode'
            }
            , {
        'text': u'Aside from passing in a fully formed machine tag, there is a special syntax for searching on specific properties :\r\n\r\n<ul>\r\n  <li>Find photos using the \'dc\' namespace :    <code>"machine_tags" => "dc:"</code></li>\r\n\r\n  <li> Find photos with a title in the \'dc\' namespace : <code>"machine_tags" => "dc:title="</code></li>\r\n\r\n  <li>Find photos titled "mr. camera" in the \'dc\' namespace : <code>"machine_tags" => "dc:title=\\"mr. camera\\"</code></li>\r\n\r\n  <li>Find photos whose value is "mr. camera" : <code>"machine_tags" => "*:*=\\"mr. camera\\""</code></li>\r\n\r\n  <li>Find photos that have a title, in any namespace : <code>"machine_tags" => "*:title="</code></li>\r\n\r\n  <li>Find photos that have a title, in any namespace, whose value is "mr. camera" : <code>"machine_tags" => "*:title=\\"mr. camera\\""</code></li>\r\n\r\n  <li>Find photos, in the \'dc\' namespace whose value is "mr. camera" : <code>"machine_tags" => "dc:*=\\"mr. camera\\""</code></li>\r\n\r\n </ul>\r\n\r\nMultiple machine tags may be queried by passing a comma-separated list. The number of machine tags you can pass in a single query depends on the tag mode (AND or OR) that you are querying with. "AND" queries are limited to (16) machine tags. "OR" queries are limited\r\nto (8).', u'optional': u'1', u'name': u'machine_tags'
            }
            , {
        'text': u"Either 'any' for an OR combination of tags, or 'all' for an AND combination. Defaults to 'any' if not specified.", u'optional': u'1', u'name': u'machine_tag_mode'
            }
            , {
        'text': u'Minimum upload date. Photos with an upload date greater than or equal to this value will be returned. The date should be in the form of a unix timestamp.', u'optional': u'1', u'name': u'min_upload_date'
            }
            , {
        'text': u'Maximum upload date. Photos with an upload date less than or equal to this value will be returned. The date should be in the form of a unix timestamp.', u'optional': u'1', u'name': u'max_upload_date'
            }
            , {
        'text': u'Minimum taken date. Photos with an taken date greater than or equal to this value will be returned. The date should be in the form of a mysql datetime.', u'optional': u'1', u'name': u'min_taken_date'
            }
            , {
        'text': u'Maximum taken date. Photos with an taken date less than or equal to this value will be returned. The date should be in the form of a mysql datetime.', u'optional': u'1', u'name': u'max_taken_date'
            }
            ], 'needslogin': False, u'response': u'<places total="1">\r\n   <place place_id="kH8dLOubBZRvX_YZ" woeid="2487956"\r\n               latitude="37.779" longitude="-122.420"\r\n               place_url="/United+States/California/San+Francisco"\r\n               place_type="locality"\r\n               photo_count="156">San Francisco, California</place>\r\n</places>', u'name': u'flickr.places.placesForTags'
        }
        , u'flickr.photosets.addPhoto': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The photoset id passed was not the id of avalid photoset owned by the calling user.', u'message': u'Photoset not found', u'code': u'1'
            }
            , {
        'text': u'The photo id passed was not the id of a valid photo owned by the calling user.', u'message': u'Photo not found', u'code': u'2'
            }
            , {
        'text': u'The photo is already a member of the photoset.', u'message': u'Photo already in set', u'code': u'3'
            }
            , {
        'text': u'A set has reached the upper limit for the number of photos allowed.', u'message': u'Maximum number of photos in set', u'code': u'10'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photoset to add a photo to.', u'optional': u'0', u'name': u'photoset_id'
            }
            , {
        'text': u'The id of the photo to add to the set.', u'optional': u'0', u'name': u'photo_id'
            }
            ], u'description': u'Add a photo to the end of an existing photoset.', 'needslogin': True, u'name': u'flickr.photosets.addPhoto'
        }
        , u'flickr.photos.geo.setPerms': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The photo id was either invalid or was for a photo not viewable by the calling user.', u'message': u'Photo not found', u'code': u'1'
            }
            , {
        'text': u'The photo requested has no location data or is not viewable by the calling user.', u'message': u'Photo has no location information', u'code': u'2'
            }
            , {
        'text': u'Some or all of the required arguments were not supplied.', u'message': u'Required arguments missing.', u'code': u'3'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u"1 to set viewing permissions for the photo's location data to public, 0 to set it to private.", u'optional': u'0', u'name': u'is_public'
            }
            , {
        'text': u"1 to set viewing permissions for the photo's location data to contacts, 0 to set it to private.", u'optional': u'0', u'name': u'is_contact'
            }
            , {
        'text': u"1 to set viewing permissions for the photo's location data to friends, 0 to set it to private.", u'optional': u'0', u'name': u'is_friend'
            }
            , {
        'text': u"1 to set viewing permissions for the photo's location data to family, 0 to set it to private.", u'optional': u'0', u'name': u'is_family'
            }
            , {
        'text': u'The id of the photo to get permissions for.', u'optional': u'0', u'name': u'photo_id'
            }
            ], u'description': u'Set the permission for who may view the geo data associated with a photo.', 'needslogin': True, u'name': u'flickr.photos.geo.setPerms'
        }
        , u'flickr.favorites.remove': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u"The photo id passed was not in the user's favorites.", u'message': u'Photo not in favorites', u'code': u'1'
            }
            , {
        'text': u'user_id was passed as an argument, but photo_id is not owned by the authenticated user.', u'message': u"Cannot remove photo from that user's favorites", u'code': u'2'
            }
            , {
        'text': u'Invalid user_id argument.', u'message': u'User not found', u'code': u'3'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u"The id of the photo to remove from the user's favorites.", u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u'NSID of the user whose favorites the photo should be removed from. This only works if the calling user owns the photo.', u'optional': u'1', u'name': u'user_id'
            }
            ], u'description': u"Removes a photo from a user's favorites list.", 'needslogin': True, u'name': u'flickr.favorites.remove'
        }
        , u'flickr.groups.pools.remove': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The group_id passed did not refer to a valid group.', u'message': u'Group not found', u'code': u'1'
            }
            , {
        'text': u'The photo_id passed was not a valid id of a photo in the group pool.', u'message': u'Photo not in pool', u'code': u'2'
            }
            , {
        'text': u"The calling user doesn't own the photo and is not an administrator of the group, so may not remove the photo from the pool.", u'message': u'Insufficient permission to remove photo', u'code': u'3'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photo to remove from the group pool. The photo must either be owned by the calling user of the calling user must be an administrator of the group.', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u"The NSID of the group who's pool the photo is to removed from.", u'optional': u'0', u'name': u'group_id'
            }
            ], u'description': u'Remove a photo from a group pool.', 'needslogin': True, u'name': u'flickr.groups.pools.remove'
        }
        , u'flickr.photos.notes.edit': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The note id passed was not a valid note id', u'message': u'Note not found', u'code': u'1'
            }
            , {
        'text': u'The calling user does not have permission to edit the specified note', u'message': u'User cannot edit note', u'code': u'2'
            }
            , {
        'text': u'One or more of the required arguments were not supplied.', u'message': u'Missing required arguments', u'code': u'3'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the note to edit', u'optional': u'0', u'name': u'note_id'
            }
            , {
        'text': u'The left coordinate of the note', u'optional': u'0', u'name': u'note_x'
            }
            , {
        'text': u'The top coordinate of the note', u'optional': u'0', u'name': u'note_y'
            }
            , {
        'text': u'The width of the note', u'optional': u'0', u'name': u'note_w'
            }
            , {
        'text': u'The height of the note', u'optional': u'0', u'name': u'note_h'
            }
            , {
        'text': u'The description of the note', u'optional': u'0', u'name': u'note_text'
            }
            ], u'description': u'Edit a note on a photo. Coordinates and sizes are in pixels, based on the 500px image size shown on individual photo pages.\r\n', 'needslogin': True, u'name': u'flickr.photos.notes.edit'
        }
        , u'flickr.groups.pools.getGroups': {
    u'errors': [{
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.groups.pools.getGroups', u'explanation': u'<p>The <code>privacy</code> attribute is 1 for private groups, 2 for invite-only public groups and 3 for open public groups.</p>', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': u'1', u'name': u'page'
            }
            , {
        'text': u'Number of groups to return per page. If this argument is omitted, it defaults to 400. The maximum allowed value is 400.', u'optional': u'1', u'name': u'per_page'
            }
            ], 'needslogin': True, u'response': u'<groups page="1" pages="1" per_page="400" total="3">\r\n\t<group nsid="33853651696@N01" name="Art and Literature Hoedown"\r\n\t\tadmin="0" privacy="3" photos="2" iconserver="1" /> \r\n\t<group nsid="34427465446@N01" name="FlickrIdeas"\r\n\t\tadmin="1" privacy="3" photos="20" iconserver="1" /> \r\n\t<group nsid="34427465497@N01" name="GNEverybody"\r\n\t\tadmin="0" privacy="3" photos="4" iconserver="1" /> \r\n</groups>', u'description': u'Returns a list of groups to which you can add photos.'
        }
        , u'flickr.photos.people.getList': {
    u'errors': [{
        'text': u'The photo id passed was not a valid photo id.', u'message': u'Photo not found', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.photos.people.getList', u'explanation': u'x, y, w and h correspond to the coordinates of the "bounding box" around a person in a photo. Since these co-ordinates are optional, these elements may not be present for every person.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photo to get a list of people for.', u'optional': u'0', u'name': u'photo_id'
            }
            ], 'needslogin': False, u'response': u'<people total="1">\r\n  <person nsid="87944415@N00" username="hitherto" iconserver="1" iconfarm="1"\r\n          realname="Simon Batistoni" added_by="12037949754@N01" x="50" y="50"\r\n          w="100" h="100"/>\r\n</people>', u'description': u'Get a list of people in a given photo.'
        }
        , u'flickr.people.findByUsername': {
    u'errors': [{
        'text': u'No user with the supplied username was found.', u'message': u'User not found', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u"Return a user's NSID, given their username.", 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The username of the user to lookup.', u'optional': u'0', u'name': u'username'
            }
            ], 'needslogin': False, u'response': u'<user nsid="12037949632@N01">\r\n\t<username>Stewart</username> \r\n</user>', u'name': u'flickr.people.findByUsername'
        }
        , u'flickr.people.getInfo': {
    u'errors': [{
        'text': u'The user id passed did not match a Flickr user.', u'message': u'User not found', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.people.getInfo', u'explanation': u'<p>The <code>firstdate</code> element contains the unix timestamp of the first photo uploaded by the user. The <code>firstdatetaken</code> element contains the mysql datetime of the first photo taken by the user.</p>\r\n<p>The <code>iconserver</code> element is used to build the url to the users\' buddyicon - for more information please read the <a href="/services/api/misc.buddyicons.html">buddyicon guide</a>.</p>\r\n<p>\r\nIf the API call is authenticated contact information will also be returned as attributes on the person element.  <code>contact</code>, <code>friend</code>, and <code>family</code> are boolean flags describing the relationship between the <a href="/services/api/auth.spec.html">authenticated</a> user, and the person currently being inspected.   <code>revcontact</code>, <code>revfriend</code>, and <code>revfamily</code> is the reciprocal relationship.\r\n</p>', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The NSID of the user to fetch information about.', u'optional': u'0', u'name': u'user_id'
            }
            , {
        'text': u'As an alternative to user_id, load a member based on URL, either photos or people URL.', u'optional': u'0', u'name': u'url'
            }
            , {
        'text': u'If set to 1, it checks if the user is connected to Facebook and returns that information back.', u'optional': u'1', u'name': u'fb_connected'
            }
            , {
        'text': u'If set to 1, it returns the storage information about the user, like the storage used and storage available.', u'optional': u'1', u'name': u'storage'
            }
            ], 'needslogin': False, u'response': u'<person nsid="12037949754@N01" ispro="0" iconserver="122" iconfarm="1">\r\n\t<username>bees</username>\r\n\t<realname>Cal Henderson</realname>\r\n        <mbox_sha1sum>eea6cd28e3d0003ab51b0058a684d94980b727ac</mbox_sha1sum>\r\n\t<location>Vancouver, Canada</location>\r\n\t<photosurl>http://www.flickr.com/photos/bees/</photosurl> \r\n\t<profileurl>http://www.flickr.com/people/bees/</profileurl> \r\n\t<photos>\r\n\t\t<firstdate>1071510391</firstdate>\r\n\t\t<firstdatetaken>1900-09-02 09:11:24</firstdatetaken>\r\n\t\t<count>449</count>\r\n\t</photos>\r\n</person>', u'description': u'Get information about a user.'
        }
        , u'flickr.photos.geo.batchCorrectLocation': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'Some or all of the required arguments were not supplied.', u'message': u'Required arguments missing', u'code': u'1'
            }
            , {
        'text': u'The latitude argument failed validation.', u'message': u'Not a valid latitude', u'code': u'2'
            }
            , {
        'text': u'The longitude argument failed validation.', u'message': u'Not a valid longitude', u'code': u'3'
            }
            , {
        'text': u'The accuracy argument failed validation.', u'message': u'Not a valid accuracy', u'code': u'4'
            }
            , {
        'text': u'An invalid Places (or WOE) ID was passed with the API call.', u'message': u'Not a valid Places ID', u'code': u'5'
            }
            , {
        'text': u'There were no geotagged photos found for the authed user at the supplied latitude, longitude and accuracy.', u'message': u'No photos geotagged at that location', u'code': u'6'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The latitude of the photos to be update whose valid range is -90 to 90. Anything more than 6 decimal places will be truncated.', u'optional': u'0', u'name': u'lat'
            }
            , {
        'text': u'The longitude of the photos to be updated whose valid range is -180 to 180. Anything more than 6 decimal places will be truncated.', u'optional': u'0', u'name': u'lon'
            }
            , {
        'text': u'Recorded accuracy level of the photos to be updated. World level is 1, Country is ~3, Region ~6, City ~11, Street ~16. Current range is 1-16. Defaults to 16 if not specified.', u'optional': u'0', u'name': u'accuracy'
            }
            , {
        'text': u'A Flickr Places ID. (While optional, you must pass either a valid Places ID or a WOE ID.)', u'optional': u'1', u'name': u'place_id'
            }
            , {
        'text': u'A Where On Earth (WOE) ID. (While optional, you must pass either a valid Places ID or a WOE ID.)', u'optional': u'1', u'name': u'woe_id'
            }
            ], u'description': u"Correct the places hierarchy for all the photos for a user at a given latitude, longitude and accuracy.<br /><br />\r\n\r\nBatch corrections are processed in a delayed queue so it may take a few minutes before the changes are reflected in a user's photos.", 'needslogin': True, u'name': u'flickr.photos.geo.batchCorrectLocation'
        }
        , u'flickr.collections.getTree': {
    u'errors': [{
        'text': u'The specified user could not be found.', u'message': u'User not found', u'code': u'1'
            }
            , {
        'text': u'The specified collection does not exist.', u'message': u'Collection not found', u'code': u'2'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.collections.getTree', u'explanation': u'A nested tree of collections, and the collections and sets they contain.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The ID of the collection to fetch a tree for, or zero to fetch the root collection. Defaults to zero.', u'optional': u'1', u'name': u'collection_id'
            }
            , {
        'text': u'The ID of the account to fetch the collection tree for. Deafults to the calling user.', u'optional': u'1', u'name': u'user_id'
            }
            ], 'needslogin': False, u'response': u'<collections>\r\n<collection id="12-72157594586579649" title="All My Photos" description="a collection" iconlarge="http://farm1.static.flickr.com/187/cols/37_43fac2cf79_l.jpg" \r\niconsmall="http://farm1.static.flickr.com/187/cols/56_43fac2cf79_s.jpg">\r\n<set id="92157594171298291" title="kitesurfing" description="a set"/>\r\n<set id="72157594247596158" title="faves" description="some favorites."/>\r\n</collection>\r\n</collections>', u'description': u'Returns a tree (or sub tree) of collections belonging to a given user.'
        }
        , u'flickr.stats.getCollectionDomains': {
    u'errors': [{
        'text': u'The user you have requested stats has not enabled stats on their account.', u'message': u'User does not have stats', u'code': u'1'
            }
            , {
        'text': u'No stats are available for the date requested. Flickr only keeps stats data for the last 28 days.', u'message': u'No stats for that date', u'code': u'2'
            }
            , {
        'text': u'The date provided could not be parsed', u'message': u'Invalid date', u'code': u'3'
            }
            , {
        'text': u'The collection id was either invalid or was for a collection not owned by the calling user.', u'message': u'Collection not found', u'code': u'4'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.stats.getCollectionDomains', u'explanation': u'<p>There is one <code>&lt;domain&gt;</code> element for each referring domain, with attributes for the domain name and the number of views.</p>\r\n\r\n<p>For details on the referrers coming from each domain listed you can call <a href="/services/api/flickr.stats.getCollectionReferrers.html">flickr.stats.getCollectionReferrers</a></p>', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'Stats will be returned for this date. This should be in either be in YYYY-MM-DD or unix timestamp format.\r\n\r\nA day according to Flickr Stats starts at midnight GMT for all users, and timestamps will automatically be rounded down to the start of the day.', u'optional': u'0', u'name': u'date'
            }
            , {
        'text': u'The id of the collection to get stats for. If not provided, stats for all collections will be returned.', u'optional': u'1', u'name': u'collection_id'
            }
            , {
        'text': u'Number of domains to return per page. If this argument is omitted, it defaults to 25. The maximum allowed value is 100.', u'optional': u'1', u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': u'1', u'name': u'page'
            }
            ], 'needslogin': True, u'response': u'<domains page="1" perpage="25" pages="1" total="3">\r\n\t<domain name="images.search.yahoo.com" views="127" />\r\n\t<domain name="flickr.com" views="122" />\r\n\t<domain name="images.google.com" views="70" />\r\n</domains>\r\n', u'description': u'Get a list of referring domains for a collection'
        }
        , u'flickr.photos.comments.deleteComment': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The requested comment is against a photo which no longer exists.', u'message': u'Photo not found.', u'code': u'1'
            }
            , {
        'text': u'The comment id passed was not a valid comment id', u'message': u'Comment not found.', u'code': u'2'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the comment to edit.', u'optional': u'0', u'name': u'comment_id'
            }
            ], u'description': u'Delete a comment as the currently authenticated user.', 'needslogin': True, u'name': u'flickr.photos.comments.deleteComment'
        }
        , u'flickr.blogs.getList': {
    u'errors': [{
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.blogs.getList', u'explanation': u'<p>The <code>needspassword</code> attribute indicates whether a call to <code>flickr.blogs.postPhoto</code> for this blog will require a password to be sent. When flickr has a password already stored, <code>needspassword</code> is 0</p>', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'Optionally only return blogs for a given service id.  You can get a list of from <a href="/services/api/flickr.blogs.getServices.html">flickr.blogs.getServices()</a>.', u'optional': u'1', u'name': u'service'
            }
            ], 'needslogin': True, u'response': u'<blogs>\r\n\t<blog id="73" name="Bloxus test" needspassword="0"\r\n\t\turl="http://remote.bloxus.com/" /> \r\n\t<blog id="74" name="Manila Test" needspassword="1"\r\n\t\turl="http://flickrtest1.userland.com/" /> \r\n</blogs>', u'description': u'Get a list of configured blogs for the calling user.'
        }
        , u'flickr.panda.getPhotos': {
    u'errors': [{
        'text': u'One or more required parameters was not included with your request.', u'message': u'Required parameter missing.', u'code': u'1'
            }
            , {
        'text': u"You requested a panda we haven't met yet.", u'message': u'Unknown panda', u'code': u'2'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.panda.getPhotos', u'explanation': u'When calling this API method please ensure that your code uses the <strong>lastupdate</strong> and <strong>interval</strong> attributes to determine when to request new photos. <em>lastupdate</em> is a Unix timestamp indicating when the list of photos was generated and <em>interval</em> is the number of seconds to wait before polling the Flickr API again.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The name of the panda to ask for photos from. There are currently three pandas named:<br /><br />\r\n\r\n<ul>\r\n<li><strong><a href="http://flickr.com/photos/ucumari/126073203/">ling ling</a></strong></li>\r\n<li><strong><a href="http://flickr.com/photos/lynnehicks/136407353">hsing hsing</a></strong></li>\r\n<li><strong><a href="http://flickr.com/photos/perfectpandas/1597067182/">wang wang</a></strong></li>\r\n</ul>\r\n\r\n<br />You can fetch a list of all the current pandas using the <a href="/services/api/flickr.panda.getList.html">flickr.panda.getList</a> API method.', u'optional': u'0', u'name': u'panda_name'
            }
            , {
        'text': u'A comma-delimited list of extra information to fetch for each returned record. Currently supported fields are: <code>description</code>, <code>license</code>, <code>date_upload</code>, <code>date_taken</code>, <code>owner_name</code>, <code>icon_server</code>, <code>original_format</code>, <code>last_update</code>, <code>geo</code>, <code>tags</code>, <code>machine_tags</code>, <code>o_dims</code>, <code>views</code>, <code>media</code>, <code>path_alias</code>, <code>url_sq</code>, <code>url_t</code>, <code>url_s</code>, <code>url_q</code>, <code>url_m</code>, <code>url_n</code>, <code>url_z</code>, <code>url_c</code>, <code>url_l</code>, <code>url_o</code>', u'optional': 1, u'name': u'extras'
            }
            , {
        'text': u'Number of photos to return per page. If this argument is omitted, it defaults to 100. The maximum allowed value is 500.', u'optional': 1, u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': 1, u'name': u'page'
            }
            ], 'needslogin': False, u'response': u'<photos interval="60000" lastupdate="1235765058272" total="120" panda="ling ling">\r\n    <photo title="Shorebirds at Pillar Point" id="3313428913" secret="2cd3cb44cb"\r\n        server="3609" farm="4" owner="72442527@N00" ownername="Pat Ulrich"/>\r\n    <photo title="Battle of the sky" id="3313713993" secret="3f7f51500f"\r\n        server="3382" farm="4" owner="10459691@N05" ownername="Sven Ericsson"/>\r\n    <!-- and so on -->\r\n</photos>', u'description': u'Ask the <a href="http://www.flickr.com/explore/panda">Flickr Pandas</a> for a list of recent public (and "safe") photos.\r\n<br/><br/>\r\nMore information about the pandas can be found on the <a href="http://code.flickr.com/blog/2009/03/03/panda-tuesday-the-history-of-the-panda-new-apis-explore-and-you/">dev blog</a>.'
        }
        , u'flickr.machinetags.getNamespaces': {
    u'errors': [{
        'text': u'Missing or invalid predicate argument.', u'message': u'Not a valid predicate.', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.machinetags.getNamespaces', u'explanation': u'"Usage" gives you roughly how popular a machine tags, while "predicates" is the count of distinct predicates a namespace has.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'Limit the list of namespaces returned to those that have the following predicate.', u'optional': u'1', u'name': u'predicate'
            }
            , {
        'text': u'Number of photos to return per page. If this argument is omitted, it defaults to 100. The maximum allowed value is 500.', u'optional': u'1', u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': u'1', u'name': u'page'
            }
            ], 'needslogin': False, u'response': u'<namespaces page="1" total="5" perpage="500" pages="1">\r\n  <namespace usage="6538" predicates="13">aero</namespace>\r\n  <namespace usage="9072" predicates="24">flickr</namespace>\r\n  <namespace usage="670270" predicates="35">geo</namespace>\r\n  <namespace usage="23903" predicates="36">taxonomy</namespace>\r\n  <namespace usage="50449" predicates="4">upcoming</namespace>\r\n</namespaces>\r\n', u'description': u'Return a list of unique namespaces, optionally limited by a given predicate, in alphabetical order.'
        }
        , u'flickr.groups.pools.getPhotos': {
    u'errors': [{
        'text': u'The group id passed was not a valid group id.', u'message': u'Group not found', u'code': u'1'
            }
            , {
        'text': u'The logged in user (if any) does not have permission to view the pool for this group.', u'message': u"You don't have permission to view this pool", u'code': u'2'
            }
            , {
        'text': u'The user specified by user_id does not exist.', u'message': u'Unknown user', u'code': u'3'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Returns a list of pool photos for a given group, based on the permissions of the group and the user logged in (if any).', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u"The id of the group who's pool you which to get the photo list for.", u'optional': u'0', u'name': u'group_id'
            }
            , {
        'text': u'A tag to filter the pool with. At the moment only one tag at a time is supported.', u'optional': u'1', u'name': u'tags'
            }
            , {
        'text': u'The nsid of a user. Specifiying this parameter will retrieve for you only those photos that the user has contributed to the group pool.', u'optional': u'1', u'name': u'user_id'
            }
            , {
        'text': u'', u'optional': u'1', u'name': u'jump_to'
            }
            , {
        'text': u'A comma-delimited list of extra information to fetch for each returned record. Currently supported fields are: <code>description</code>, <code>license</code>, <code>date_upload</code>, <code>date_taken</code>, <code>owner_name</code>, <code>icon_server</code>, <code>original_format</code>, <code>last_update</code>, <code>geo</code>, <code>tags</code>, <code>machine_tags</code>, <code>o_dims</code>, <code>views</code>, <code>media</code>, <code>path_alias</code>, <code>url_sq</code>, <code>url_t</code>, <code>url_s</code>, <code>url_q</code>, <code>url_m</code>, <code>url_n</code>, <code>url_z</code>, <code>url_c</code>, <code>url_l</code>, <code>url_o</code>', u'optional': 1, u'name': u'extras'
            }
            , {
        'text': u'Number of photos to return per page. If this argument is omitted, it defaults to 100. The maximum allowed value is 500.', u'optional': 1, u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': 1, u'name': u'page'
            }
            ], 'needslogin': False, u'response': u'<photos page="1" pages="1" perpage="1" total="1">\r\n\t<photo id="2645" owner="12037949754@N01" title="36679_o"\r\n\tsecret="a9f4a06091" server="2"\r\n\tispublic="1" isfriend="0" isfamily="0"\r\n\townername="Bees / ?" dateadded="1089918707" /> \r\n</photos>', u'name': u'flickr.groups.pools.getPhotos'
        }
        , u'flickr.stats.getPhotostreamReferrers': {
    u'errors': [{
        'text': u'The user you have requested stats has not enabled stats on their account.', u'message': u'User does not have stats', u'code': u'1'
            }
            , {
        'text': u'No stats are available for the date requested. Flickr only keeps stats data for the last 28 days.', u'message': u'No stats for that date', u'code': u'2'
            }
            , {
        'text': u'The date provided could not be parsed', u'message': u'Invalid date', u'code': u'3'
            }
            , {
        'text': u'The domain provided is not in the expected format.', u'message': u'Invalid domain', u'code': u'5'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.stats.getPhotostreamReferrers', u'explanation': u'<p>There is one <code>&lt;referrer&gt;</code> element for each referring page, with attributes for the url and the number of views.</p>\r\n\r\n<p>Where the referring page is a search engine and we have identified the search term it will be given in the searchterm attribute.</p>', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'Stats will be returned for this date. This should be in either be in YYYY-MM-DD or unix timestamp format. \r\n\r\nA day according to Flickr Stats starts at midnight GMT for all users, and timestamps will automatically be rounded down to the start of the day.', u'optional': u'0', u'name': u'date'
            }
            , {
        'text': u'The domain to return referrers for. This should be a hostname (eg: "flickr.com") with no protocol or pathname.', u'optional': u'0', u'name': u'domain'
            }
            , {
        'text': u'Number of referrers to return per page. If this argument is omitted, it defaults to 25. The maximum allowed value is 100.', u'optional': u'1', u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': u'1', u'name': u'page'
            }
            ], 'needslogin': True, u'response': u'<domain page="1" perpage="25" pages="1" total="3" name="flickr.com">\r\n\t<referrer url="http://flickr.com/" views="11"/>\r\n\t<referrer url="http://flickr.com/photos/friends/" views="8"/>\r\n\t<referrer url="http://flickr.com/search/?q=stats+api" views="2" searchterm="stats api"/>\r\n</domain>', u'description': u"Get a list of referrers from a given domain to a user's photostream"
        }
        , u'flickr.photos.getUntagged': {
    'needssigning': True, u'requiredperms': 'read', u'errors': [{
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'Minimum upload date. Photos with an upload date greater than or equal to this value will be returned. The date can be in the form of a unix timestamp or mysql datetime.', u'optional': u'1', u'name': u'min_upload_date'
            }
            , {
        'text': u'Maximum upload date. Photos with an upload date less than or equal to this value will be returned. The date can be in the form of a unix timestamp or mysql datetime.', u'optional': u'1', u'name': u'max_upload_date'
            }
            , {
        'text': u'Minimum taken date. Photos with an taken date greater than or equal to this value will be returned. The date should be in the form of a mysql datetime or unix timestamp.', u'optional': u'1', u'name': u'min_taken_date'
            }
            , {
        'text': u'Maximum taken date. Photos with an taken date less than or equal to this value will be returned. The date can be in the form of a mysql datetime or unix timestamp.', u'optional': u'1', u'name': u'max_taken_date'
            }
            , {
        'text': u'Return photos only matching a certain privacy level. Valid values are:\r\n<ul>\r\n<li>1 public photos</li>\r\n<li>2 private photos visible to friends</li>\r\n<li>3 private photos visible to family</li>\r\n<li>4 private photos visible to friends &amp; family</li>\r\n<li>5 completely private photos</li>\r\n</ul>\r\n', u'optional': u'1', u'name': u'privacy_filter'
            }
            , {
        'text': u'Filter results by media type. Possible values are <code>all</code> (default), <code>photos</code> or <code>videos</code>', u'optional': u'1', u'name': u'media'
            }
            , {
        'text': u'A comma-delimited list of extra information to fetch for each returned record. Currently supported fields are: <code>description</code>, <code>license</code>, <code>date_upload</code>, <code>date_taken</code>, <code>owner_name</code>, <code>icon_server</code>, <code>original_format</code>, <code>last_update</code>, <code>geo</code>, <code>tags</code>, <code>machine_tags</code>, <code>o_dims</code>, <code>views</code>, <code>media</code>, <code>path_alias</code>, <code>url_sq</code>, <code>url_t</code>, <code>url_s</code>, <code>url_q</code>, <code>url_m</code>, <code>url_n</code>, <code>url_z</code>, <code>url_c</code>, <code>url_l</code>, <code>url_o</code>', u'optional': 1, u'name': u'extras'
            }
            , {
        'text': u'Number of photos to return per page. If this argument is omitted, it defaults to 100. The maximum allowed value is 500.', u'optional': 1, u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': 1, u'name': u'page'
            }
            ], u'description': u'Returns a list of your photos with no tags.', 'needslogin': True, u'name': u'flickr.photos.getUntagged'
        }
        , u'flickr.groups.search': {
    u'errors': [{
        'text': u'The required text argument was ommited.', u'message': u'No text passed', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Search for groups. 18+ groups will only be returned for authenticated calls where the authenticated user is over 18.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The text to search for.', u'optional': u'0', u'name': u'text'
            }
            , {
        'text': u'Number of groups to return per page. If this argument is ommited, it defaults to 100. The maximum allowed value is 500.', u'optional': u'1', u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is ommited, it defaults to 1. ', u'optional': u'1', u'name': u'page'
            }
            ], 'needslogin': False, u'response': u'<groups page="1" pages="14" perpage="5" total="67">\r\n\t<group nsid="3000@N02"\r\n\t\tname="Frito\'s Test Group" eighteenplus="0" /> \r\n\t<group nsid="32825757@N00"\r\n\t\tname="Free for All" eighteenplus="0" /> \r\n\t<group nsid="33335981560@N01"\r\n\t\tname="joly\'s mothers" eighteenplus="0" /> \r\n\t<group nsid="33853651681@N01"\r\n\t\tname="Wintermute tower" eighteenplus="0" /> \r\n\t<group nsid="33853651696@N01"\r\n\t\tname="Art and Literature Hoedown" eighteenplus="0" /> \r\n</groups>', u'name': u'flickr.groups.search'
        }
        , u'flickr.push.subscribe': {
    'needssigning': True, u'requiredperms': 'read', u'errors': [{
        'text': u'One of the required arguments for the method was not provided.', u'message': u'Required parameter missing', u'code': u'1'
            }
            , {
        'text': u'One of the arguments was specified with an illegal value.', u'message': u'Invalid parameter value', u'code': u'2'
            }
            , {
        'text': u'A different subscription already exists that uses the same callback URL.', u'message': u'Callback URL already in use for a different subscription', u'code': u'3'
            }
            , {
        'text': u'The verification callback failed, or failed to return the expected response to confirm the subscription.', u'message': u'Callback failed or invalid response', u'code': u'4'
            }
            , {
        'text': u'PuSH subscriptions are currently restricted to Pro account holders.', u'message': u'Service currently available only to pro accounts', u'code': u'5'
            }
            , {
        'text': u'A subscription with those details exists already, but it is in a pending (non-verified) state. Please wait a bit for the verification callback to complete before attempting to update the subscription.', u'message': u'Subscription awaiting verification callback response - try again later', u'code': u'6'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The type of subscription. See <a href="http://www.flickr.com/services/api/flickr.push.getTopics.htm">flickr.push.getTopics</a>.', u'optional': u'0', u'name': u'topic'
            }
            , {
        'text': u'The url for the subscription endpoint. Limited to 255 bytes, and must be unique for this user, i.e. no two subscriptions for a given user may use the same callback url.', u'optional': u'0', u'name': u'callback'
            }
            , {
        'text': u'The verification mode, either <code>sync</code> or <code>async</code>. See the <a href="http://pubsubhubbub.googlecode.com/svn/trunk/pubsubhubbub-core-0.3.html#subscribingl">Google PubSubHubbub spec</a> for details.', u'optional': u'0', u'name': u'verify'
            }
            , {
        'text': u'The verification token to be echoed back to the subscriber during the verification callback, as per the <a href="http://pubsubhubbub.googlecode.com/svn/trunk/pubsubhubbub-core-0.3.html#subscribing">Google PubSubHubbub spec</a>. Limited to 200 bytes.', u'optional': u'1', u'name': u'verify_token'
            }
            , {
        'text': u'Number of seconds for which the subscription will be valid. Legal values are 60 to 86400 (1 minute to 1 day). If not present, the subscription will be auto-renewing.', u'optional': u'1', u'name': u'lease_seconds'
            }
            , {
        'text': u'A 32-bit integer for a <a href="http://developer.yahoo.com/geo/geoplanet/">Where on Earth ID</a>. Only valid if <code>topic</code> is <code>geo</code>.\r\n<br/><br/>\r\nThe order of precedence for geo subscriptions is : woe ids, place ids, radial i.e. the <code>lat, lon</code> parameters will be ignored if <code>place_ids</code> is present, which will be ignored if <code>woe_ids</code> is present.', u'optional': u'1', u'name': u'woe_ids'
            }
            , {
        'text': u'A comma-separated list of Flickr place IDs. Only valid if <code>topic</code> is <code>geo</code>.\r\n<br/><br/>\r\nThe order of precedence for geo subscriptions is : woe ids, place ids, radial i.e. the <code>lat, lon</code> parameters will be ignored if <code>place_ids</code> is present, which will be ignored if <code>woe_ids</code> is present.', u'optional': u'1', u'name': u'place_ids'
            }
            , {
        'text': u'A latitude value, in decimal format. Only valid if <code>topic</code> is <code>geo</code>. Defines the latitude for a radial query centered around (lat, lon).\r\n<br/><br/>\r\nThe order of precedence for geo subscriptions is : woe ids, place ids, radial i.e. the <code>lat, lon</code> parameters will be ignored if <code>place_ids</code> is present, which will be ignored if <code>woe_ids</code> is present.', u'optional': u'1', u'name': u'lat'
            }
            , {
        'text': u'A longitude value, in decimal format. Only valid if <code>topic</code> is <code>geo</code>. Defines the longitude for a radial query centered around (lat, lon).\r\n<br/><br/>\r\nThe order of precedence for geo subscriptions is : woe ids, place ids, radial i.e. the <code>lat, lon</code> parameters will be ignored if <code>place_ids</code> is present, which will be ignored if <code>woe_ids</code> is present.', u'optional': u'1', u'name': u'lon'
            }
            , {
        'text': u'A radius value, in the units defined by radius_units. Only valid if <code>topic</code> is <code>geo</code>. Defines the radius of a circle for a radial query centered around (lat, lon). Default is 5 km.\r\n<br/><br/>\r\nThe order of precedence for geo subscriptions is : woe ids, place ids, radial i.e. the <code>lat, lon</code> parameters will be ignored if <code>place_ids</code> is present, which will be ignored if <code>woe_ids</code> is present.', u'optional': u'1', u'name': u'radius'
            }
            , {
        'text': u'Defines the units for the radius parameter. Only valid if <code>topic</code> is <code>geo</code>. Options are <code>mi</code> and <code>km</code>. Default is <code>km</code>.\r\n<br/><br/>\r\nThe order of precedence for geo subscriptions is : woe ids, place ids, radial i.e. the <code>lat, lon</code> parameters will be ignored if <code>place_ids</code> is present, which will be ignored if <code>woe_ids</code> is present.', u'optional': u'1', u'name': u'radius_units'
            }
            , {
        'text': u'Defines the minimum accuracy required for photos to be included in a subscription. Only valid if <code>topic</code> is <code>geo</code> Legal values are 1-16, default is 1 (i.e. any accuracy level).\r\n<ul>\r\n<li>World level is 1</li>\r\n<li>Country is ~3</li>\r\n<li>Region is ~6</li>\r\n<li>City is ~11</li>\r\n<li>Street is ~16</li>\r\n</ul>', u'optional': u'1', u'name': u'accuracy'
            }
            , {
        'text': u'A comma-separated list of nsids representing Flickr Commons institutions (see <a href="http://www.flickr.com/services/api/flickr.commons.getInstitutions.html">flickr.commons.getInstitutions</a>). Only valid if <code>topic</code> is <code>commons</code>. If not present this argument defaults to all Flickr Commons institutions.', u'optional': u'1', u'name': u'nsids'
            }
            , {
        'text': u'A comma-separated list of strings to be used for tag subscriptions. Photos with one or more of the tags listed will be included in the subscription. Only valid if the <code>topic</code> is <code>tags</code>.', u'optional': u'1', u'name': u'tags'
            }
            , {
        'text': u'A comma-separated list of strings to be used for machine tag subscriptions. Photos with one or more of the machine tags listed will be included in the subscription. Currently the format must be <code>namespace:tag_name=value</code> Only valid if the <code>topic</code> is <code>tags</code>.', u'optional': u'1', u'name': u'machine_tags'
            }
            , {
        'text': u'', u'optional': u'1', u'name': u'update_type'
            }
            , {
        'text': u'', u'optional': u'1', u'name': u'output_format'
            }
            , {
        'text': u'', u'optional': u'1', u'name': u'mailto'
            }
            ], u'description': u'In ur pandas, tickling ur unicorn\r\n<br><br>\r\n<i>(this method is experimental and may change)</i>', 'needslogin': True, u'name': u'flickr.push.subscribe'
        }
        , u'flickr.photos.suggestions.suggestLocation': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The photo whose location you are suggesting.', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u'The latitude whose valid range is -90 to 90. Anything more than 6 decimal places will be truncated.', u'optional': u'0', u'name': u'lat'
            }
            , {
        'text': u'The longitude whose valid range is -180 to 180. Anything more than 6 decimal places will be truncated.', u'optional': u'0', u'name': u'lon'
            }
            , {
        'text': u'Recorded accuracy level of the location information. World level is 1, Country is ~3, Region ~6, City ~11, Street ~16. Current range is 1-16. Defaults to 16 if not specified.', u'optional': u'1', u'name': u'accuracy'
            }
            , {
        'text': u'The WOE ID of the location used to build the location hierarchy for the photo.', u'optional': u'1', u'name': u'woe_id'
            }
            , {
        'text': u'The Flickr Places ID of the location used to build the location hierarchy for the photo.', u'optional': u'1', u'name': u'place_id'
            }
            , {
        'text': u'A short note or history to include with the suggestion.', u'optional': u'1', u'name': u'note'
            }
            ], u'description': u'Suggest a geotagged location for a photo.', 'needslogin': True, u'name': u'flickr.photos.suggestions.suggestLocation'
        }
        , u'flickr.people.getGroups': {
    u'errors': [{
        'text': u'The user id passed did not match a Flickr user.', u'message': u'User not found', u'code': u'1'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.people.getGroups', u'explanation': u'The admin attribute indicates whether the user is an administrator of the group. The eighteenplus attribute indicates if the group is visible to members over 18 only. The invite_only attribute indicates whether a user can join the group without administrator approval.', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The NSID of the user to fetch groups for.', u'optional': u'0', u'name': u'user_id'
            }
            , {
        'text': u'A comma-delimited list of extra information to fetch for each returned record. Currently supported fields are: <code>privacy</code>, <code>throttle</code>, <code>restrictions</code>', u'optional': u'1', u'name': u'extras'
            }
            ], 'needslogin': True, u'response': u'<groups>\r\n  <group nsid="17274427@N00" name="Cream of the Crop - Please read the rules" iconfarm="1" iconserver="1" admin="0" eighteenplus="0" invitation_only="0" members="11935" pool_count="12522" />\r\n  <group nsid="20083316@N00" name="Apple" iconfarm="1" iconserver="1" admin="0" eighteenplus="0" invitation_only="0" members="11776" pool_count="62438" />\r\n  <group nsid="34427469792@N01" name="FlickrCentral" iconfarm="1" iconserver="1" admin="0" eighteenplus="0" invitation_only="0" members="168055" pool_count="5280930" />\r\n  <group nsid="37718678610@N01" name="Typography and Lettering" iconfarm="1" iconserver="1" admin="0" eighteenplus="0" invitation_only="0" members="17318" pool_count="130169" />\r\n</groups>', u'description': u'Returns the list of groups a user is a member of.'
        }
        , u'flickr.places.getTopPlacesList': {
    u'errors': [{
        'text': u'One or more required parameters with missing from your request.', u'message': u'Required parameter missing', u'code': u'1'
            }
            , {
        'text': u'An unknown or unsupported place type ID was passed with your request.', u'message': u'Not a valid place type.', u'code': u'2'
            }
            , {
        'text': u'The date argument passed with your request is invalid.', u'message': u'Not a valid date.', u'code': u'3'
            }
            , {
        'text': u'An invalid Places (or WOE) identifier was included with your request.', u'message': u'Not a valid Place ID', u'code': u'4'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Return the top 100 most geotagged places for a day.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The numeric ID for a specific place type to cluster photos by. <br /><br />\r\n\r\nValid place type IDs are :\r\n\r\n<ul>\r\n<li><strong>22</strong>: neighbourhood</li>\r\n<li><strong>7</strong>: locality</li>\r\n<li><strong>8</strong>: region</li>\r\n<li><strong>12</strong>: country</li>\r\n<li><strong>29</strong>: continent</li>\r\n</ul>', u'optional': u'0', u'name': u'place_type_id'
            }
            , {
        'text': u'A valid date in YYYY-MM-DD format. The default is yesterday.', u'optional': u'1', u'name': u'date'
            }
            , {
        'text': u'Limit your query to only those top places belonging to a specific Where on Earth (WOE) identifier.', u'optional': u'1', u'name': u'woe_id'
            }
            , {
        'text': u'Limit your query to only those top places belonging to a specific Flickr Places identifier.', u'optional': u'1', u'name': u'place_id'
            }
            ], 'needslogin': False, u'response': u'<places total="100" date_start="1246320000" date_stop="1246406399">\r\n   <place place_id="4KO02SibApitvSBieQ" woeid="23424977"\r\n       latitude="48.890" longitude="-116.982" \r\n       place_url="/United+States" place_type="country" \r\n       place_type_id="12" photo_count="23371">United States</place>\r\n   <!-- and so on... -->\r\n</places>', u'name': u'flickr.places.getTopPlacesList'
        }
        , u'flickr.photos.getInfo': {
    u'errors': [{
        'text': u'The photo id was either invalid or was for a photo not viewable by the calling user.', u'message': u'Photo not found.', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.photos.getInfo', u'explanation': u"<p>The <code>&lt;permissions&gt;</code> element is only returned for photos owned by the calling user. The <code>isfavorite</code> attribute only makes sense for logged in users who don't own the photo. The <code>rotation</code> attribute is the current clockwise rotation, in degrees, by which the smaller image sizes differ from the original image.</p>\r\n\r\n<p>The <code>&lt;date&gt;</code> element's <code>lastupdate</code> attribute is a Unix timestamp indicating the last time the photo, or any of its metadata (tags, comments, etc.) was modified.</p>", 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photo to get information for.', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u"The secret for the photo. If the correct secret is passed then permissions checking is skipped. This enables the 'sharing' of individual photos by passing around the id and secret.", u'optional': u'1', u'name': u'secret'
            }
            , {
        'text': u'', u'optional': u'1', u'name': u'humandates'
            }
            , {
        'text': u'', u'optional': u'1', u'name': u'privacy_filter'
            }
            , {
        'text': u'', u'optional': u'1', u'name': u'get_contexts'
            }
            , {
        'text': u"Return geofence information in the photo's location property", u'optional': u'1', u'name': u'get_geofences'
            }
            , {
        'text': u'', u'optional': u'1', u'name': u'extras'
            }
            ], 'needslogin': False, u'response': u'<photo id="2733" secret="123456" server="12"\r\n\tisfavorite="0" license="3" rotation="90" \r\n\toriginalsecret="1bc09ce34a" originalformat="png">\r\n\t<owner nsid="12037949754@N01" username="Bees"\r\n\t\trealname="Cal Henderson" location="Bedford, UK" />\r\n\t<title>orford_castle_taster</title>\r\n\t<description>hello!</description>\r\n\t<visibility ispublic="1" isfriend="0" isfamily="0" />\r\n\t<dates posted="1100897479" taken="2004-11-19 12:51:19"\r\n\t\ttakengranularity="0" lastupdate="1093022469" />\r\n\t<permissions permcomment="3" permaddmeta="2" />\r\n\t<editability cancomment="1" canaddmeta="1" />\r\n\t<comments>1</comments>\r\n\t<notes>\r\n\t\t<note id="313" author="12037949754@N01"\r\n\t\t\tauthorname="Bees" x="10" y="10"\r\n\t\t\tw="50" h="50">foo</note>\r\n\t</notes>\r\n\t<tags>\r\n\t\t<tag id="1234" author="12037949754@N01" raw="woo yay">wooyay</tag>\r\n\t\t<tag id="1235" author="12037949754@N01" raw="hoopla">hoopla</tag>\r\n\t</tags>\r\n\t<urls>\r\n\t\t<url type="photopage">http://www.flickr.com/photos/bees/2733/</url> \r\n\t</urls>\r\n</photo>', u'description': u'Get information about a photo. The calling user must have permission to view the photo.'
        }
        , u'flickr.photos.getSizes': {
    u'errors': [{
        'text': u'The photo id passed was not a valid photo id.', u'message': u'Photo not found', u'code': u'1'
            }
            , {
        'text': u'The calling user does not have permission to view the photo.', u'message': u'Permission denied', u'code': u'2'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Returns the available sizes for a photo.  The calling user must have permission to view the photo.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photo to fetch size information for.', u'optional': u'0', u'name': u'photo_id'
            }
            ], 'needslogin': False, u'response': u'<sizes canblog="1" canprint="1" candownload="1">\r\n    <size label="Square" width="75" height="75" source="http://farm2.staticflickr.com/1103/567229075_2cf8456f01_s.jpg" url="http://www.flickr.com/photos/stewart/567229075/sizes/sq/" media="photo" />\r\n    <size label="Large Square" width="150" height="150" source="http://farm2.staticflickr.com/1103/567229075_2cf8456f01_q.jpg" url="http://www.flickr.com/photos/stewart/567229075/sizes/q/" media="photo" />\r\n    <size label="Thumbnail" width="100" height="75" source="http://farm2.staticflickr.com/1103/567229075_2cf8456f01_t.jpg" url="http://www.flickr.com/photos/stewart/567229075/sizes/t/" media="photo" />\r\n    <size label="Small" width="240" height="180" source="http://farm2.staticflickr.com/1103/567229075_2cf8456f01_m.jpg" url="http://www.flickr.com/photos/stewart/567229075/sizes/s/" media="photo" />\r\n    <size label="Small 320" width="320" height="240" source="http://farm2.staticflickr.com/1103/567229075_2cf8456f01_n.jpg" url="http://www.flickr.com/photos/stewart/567229075/sizes/n/" media="photo" />\r\n    <size label="Medium" width="500" height="375" source="http://farm2.staticflickr.com/1103/567229075_2cf8456f01.jpg" url="http://www.flickr.com/photos/stewart/567229075/sizes/m/" media="photo" />\r\n    <size label="Medium 640" width="640" height="480" source="http://farm2.staticflickr.com/1103/567229075_2cf8456f01_z.jpg?zz=1" url="http://www.flickr.com/photos/stewart/567229075/sizes/z/" media="photo" />\r\n    <size label="Medium 800" width="800" height="600" source="http://farm2.staticflickr.com/1103/567229075_2cf8456f01_c.jpg" url="http://www.flickr.com/photos/stewart/567229075/sizes/c/" media="photo" />\r\n    <size label="Large" width="1024" height="768" source="http://farm2.staticflickr.com/1103/567229075_2cf8456f01_b.jpg" url="http://www.flickr.com/photos/stewart/567229075/sizes/l/" media="photo" />\r\n    <size label="Original" width="2400" height="1800" source="http://farm2.staticflickr.com/1103/567229075_6dc09dc6da_o.jpg" url="http://www.flickr.com/photos/stewart/567229075/sizes/o/" media="photo" />\r\n</sizes>\r\n', u'name': u'flickr.photos.getSizes'
        }
        , u'flickr.prefs.getSafetyLevel': {
    u'errors': [{
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Returns the default safety level preference for the user.', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            ], 'needslogin': True, u'response': u'<rsp stat="ok">\r\n<person nsid="12037949754@N01" safety_level="1" />\r\n</rsp>', u'name': u'flickr.prefs.getSafetyLevel'
        }
        , u'flickr.galleries.create': {
    u'errors': [{
        'text': u'One or more of the required parameters was missing from your API call.', u'message': u'Required parameter missing', u'code': u'1'
            }
            , {
        'text': u'The title or the description could not be validated.', u'message': u'Invalid title or description', u'code': u'2'
            }
            , {
        'text': u'There was a problem creating the gallery.', u'message': u'Failed to add gallery', u'code': u'3'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.galleries.create', u'explanation': u'The ID of the newly created gallery, and its URL.', 'needssigning': True, u'requiredperms': 'write', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The name of the gallery', u'optional': u'0', u'name': u'title'
            }
            , {
        'text': u'A short description for the gallery', u'optional': u'0', u'name': u'description'
            }
            , {
        'text': u'The first photo to add to your gallery', u'optional': u'1', u'name': u'primary_photo_id'
            }
            ], 'needslogin': True, u'response': u'  <gallery id="50736-72157623680420409" url="http://www.flickr.com/photos/kellan/galleries/72157623680420409" /> \r\n', u'description': u'Create a new gallery for the calling user.'
        }
        , u'flickr.cameras.getBrandModels': {
    u'errors': [{
        'text': u'Unable to find the given brand ID.', u'message': u'Brand not found', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Retrieve all the models for a given camera brand.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The ID of the requested brand (as returned from flickr.cameras.getBrands).', u'optional': u'0', u'name': u'brand'
            }
            ], 'needslogin': False, u'response': u'<rsp stat="ok">\r\n  <cameras brand="apple">\r\n    <camera id="iphone_9000">\r\n      <name>iPhone 9000</name>\r\n      <details>\r\n        <megapixels>22.0</megapixels>\r\n        <zoom>3.0</zoom>\r\n        <lcd_size>40.5</lcd_size>\r\n        <storage_type>Flash</storage_type>\r\n      </details>\r\n      <images>\r\n        <small>http://farm3.staticflickr.com/1234/cameras/123456_model_small_123456.jpg</small>\r\n        <large>http://farm3.staticflickr.com/1234/cameras/123456_model_large_123456.jpg</large>\r\n      </images>\r\n    </camera>\r\n  </cameras>\r\n</rsp>', u'name': u'flickr.cameras.getBrandModels'
        }
        , u'flickr.groups.discuss.topics.getList': {
    u'errors': [{
        'text': u'The group_id is invalid', u'message': u'Group not found', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Get a list of discussion topics in a group.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The NSID of the group to fetch information for.', u'optional': u'0', u'name': u'group_id'
            }
            , {
        'text': u'Number of photos to return per page. If this argument is omitted, it defaults to 100. The maximum allowed value is 500.', u'optional': u'1', u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': u'1', u'name': u'page'
            }
            ], 'needslogin': False, u'response': u'<rsp stat="ok">\r\n  <topics group_id="46744914@N00" iconserver="1" iconfarm="1" name="Tell a story in 5 frames (Visual story telling)" members="12428" privacy="3" lang="en-us" ispoolmoderated="1" total="4621" page="1" per_page="2" pages="2310">\r\n    <topic id="72157625038324579" subject="A long time ago in a galaxy far, far away..." author="53930889@N04" authorname="Smallportfolio_jm08" role="member" iconserver="5169" iconfarm="6" count_replies="8" can_edit="0" can_delete="0" can_reply="0" is_sticky="0" is_locked="" datecreate="1287070965" datelastpost="1336905518">\r\n      <message>&lt;div&gt;&lt;span class=&quot;photo_container pc_m bbml_img&quot;&gt;&lt;a href=&quot;/photos/53930889@N04/5080874079/&quot; title=&quot;Star Wars 1 by Smallportfolio_jm08&quot;&gt;&lt;img class=&quot;notsowide&quot; src=&quot;http://farm5.staticflickr.com/4035/5080874079_684cf874e0_m.jpg&quot; width=&quot;240&quot; height=&quot;180&quot; alt=&quot;Star Wars 1 by Smallportfolio_jm08&quot;  class=&quot;pc_img&quot; border=&quot;0&quot; /&gt;&lt;/a&gt;&lt;/span&gt;&lt;/div&gt;\r\n\r\n&lt;div&gt;&lt;span class=&quot;photo_container pc_m bbml_img&quot;&gt;&lt;a href=&quot;/photos/53930889@N04/5081467846/&quot; title=&quot;Star Wars 2 by Smallportfolio_jm08&quot;&gt;&lt;img class=&quot;notsowide&quot; src=&quot;http://farm5.staticflickr.com/4071/5081467846_2eec86176d_m.jpg&quot; width=&quot;240&quot; height=&quot;180&quot; alt=&quot;Star Wars 2 by Smallportfolio_jm08&quot;  class=&quot;pc_img&quot; border=&quot;0&quot; /&gt;&lt;/a&gt;&lt;/span&gt;&lt;/div&gt;\r\n\r\n&lt;div&gt;&lt;span class=&quot;photo_container pc_m bbml_img&quot;&gt;&lt;a href=&quot;/photos/53930889@N04/5081467886/&quot; title=&quot;Star Wars 3 by Smallportfolio_jm08&quot;&gt;&lt;img class=&quot;notsowide&quot; src=&quot;http://farm5.staticflickr.com/4021/5081467886_d8cca6c8e8_m.jpg&quot; width=&quot;240&quot; height=&quot;180&quot; alt=&quot;Star Wars 3 by Smallportfolio_jm08&quot;  class=&quot;pc_img&quot; border=&quot;0&quot; /&gt;&lt;/a&gt;&lt;/span&gt;&lt;/div&gt;\r\n\r\n&lt;div&gt;&lt;span class=&quot;photo_container pc_m bbml_img&quot;&gt;&lt;a href=&quot;/photos/53930889@N04/5081467910/&quot; title=&quot;Star Wars 4 by Smallportfolio_jm08&quot;&gt;&lt;img class=&quot;notsowide&quot; src=&quot;http://farm5.staticflickr.com/4084/5081467910_274bb11fdc_m.jpg&quot; width=&quot;240&quot; height=&quot;180&quot; alt=&quot;Star Wars 4 by Smallportfolio_jm08&quot;  class=&quot;pc_img&quot; border=&quot;0&quot; /&gt;&lt;/a&gt;&lt;/span&gt;&lt;/div&gt;\r\n\r\n&lt;div&gt;&lt;span class=&quot;photo_container pc_m bbml_img&quot;&gt;&lt;a href=&quot;/photos/53930889@N04/5081467948/&quot; title=&quot;Star Wars 5 by Smallportfolio_jm08&quot;&gt;&lt;img class=&quot;notsowide&quot; src=&quot;http://farm5.staticflickr.com/4154/5081467948_1a5f200bc0_m.jpg&quot; width=&quot;240&quot; height=&quot;180&quot; alt=&quot;Star Wars 5 by Smallportfolio_jm08&quot;  class=&quot;pc_img&quot; border=&quot;0&quot; /&gt;&lt;/a&gt;&lt;/span&gt;&lt;/div&gt;</message>\r\n    </topic>\r\n    <topic id="72157629635119774" subject="Where The Fish Are" author="75240402@N04" authorname="Nokinrocks" role="member" iconserver="7027" iconfarm="8" count_replies="0" can_edit="0" can_delete="0" can_reply="0" is_sticky="0" is_locked="" datecreate="1336485653" datelastpost="1336485653">\r\n      <message>&lt;a href=&quot;http://www.flickr.com/photos/nokinrocks/7120495637/&quot;&gt;&lt;img class=&quot;notsowide&quot; src=&quot;http://farm9.staticflickr.com/8005/7120495637_fec0382b4b_n.jpg&quot; width=&quot;320&quot; height=&quot;256&quot; alt=&quot;Step It Up&quot; /&gt;&lt;/a&gt;\r\n\r\n&lt;a href=&quot;http://www.flickr.com/photos/nokinrocks/7122908705/&quot;&gt;&lt;img class=&quot;notsowide&quot; src=&quot;http://farm8.staticflickr.com/7259/7122908705_3bef338378_n.jpg&quot; width=&quot;240&quot; height=&quot;320&quot; alt=&quot;P1050351&quot; /&gt;&lt;/a&gt;\r\n\r\n&lt;a href=&quot;http://www.flickr.com/photos/nokinrocks/7122922123/&quot;&gt;&lt;img class=&quot;notsowide&quot; src=&quot;http://farm8.staticflickr.com/7052/7122922123_2bfcb6707c_n.jpg&quot; width=&quot;214&quot; height=&quot;320&quot; alt=&quot;Frog On A Log&quot; /&gt;&lt;/a&gt;\r\n\r\n&lt;a href=&quot;http://www.flickr.com/photos/nokinrocks/7122929521/&quot;&gt;&lt;img class=&quot;notsowide&quot; src=&quot;http://farm8.staticflickr.com/7047/7122929521_8ffebdd424_n.jpg&quot; width=&quot;320&quot; height=&quot;200&quot; alt=&quot;P1050397&quot; /&gt;&lt;/a&gt;\r\n\r\n&lt;a href=&quot;http://www.flickr.com/photos/nokinrocks/7122916999/&quot;&gt;&lt;img class=&quot;notsowide&quot; src=&quot;http://farm8.staticflickr.com/7200/7122916999_a7328f9dcc_n.jpg&quot; width=&quot;320&quot; height=&quot;261&quot; alt=&quot;P1050361&quot; /&gt;&lt;/a&gt;</message>\r\n    </topic>\r\n  </topics>\r\n</rsp>', u'name': u'flickr.groups.discuss.topics.getList'
        }
        , u'flickr.stats.getPopularPhotos': {
    u'errors': [{
        'text': u'The user you have requested stats has not enabled stats on their account.', u'message': u'User does not have stats', u'code': u'1'
            }
            , {
        'text': u'No stats are available for the date requested. Flickr only keeps stats data for the last 28 days.', u'message': u'No stats for that date', u'code': u'2'
            }
            , {
        'text': u'The date provided could not be parsed', u'message': u'Invalid date', u'code': u'3'
            }
            , {
        'text': u'The sort provided is not valid', u'message': u'Invalid sort', u'code': u'5'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.stats.getPopularPhotos', u'explanation': u'<p>This method returns the standard photo list xml.</p>\r\n\r\n<p>In addition each photo element contains a <code>&lt;stats&gt;</code> element. This has attributes for the view, comment and favorite counts for the requested day.</p>\r\n\r\n<p>To map <code>&lt;photo&gt;</code> elements to urls, please read the <a href="misc.urls.html">url documentation</a>.</p>\r\n', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'Stats will be returned for this date. This should be in either be in YYYY-MM-DD or unix timestamp format. \r\n\r\nA day according to Flickr Stats starts at midnight GMT for all users, and timestamps will automatically be rounded down to the start of the day.\r\n\r\nIf no date is provided, all time view counts will be returned.', u'optional': u'1', u'name': u'date'
            }
            , {
        'text': u'The order in which to sort returned photos. Defaults to views. The possible values are views, comments and favorites. \r\n\r\nOther sort options are available through <a href="/services/api/flickr.photos.search.html">flickr.photos.search</a>.', u'optional': u'1', u'name': u'sort'
            }
            , {
        'text': u'Number of referrers to return per page. If this argument is omitted, it defaults to 25. The maximum allowed value is 100.', u'optional': u'1', u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': u'1', u'name': u'page'
            }
            ], 'needslogin': True, u'response': u'<photos page="2" pages="89" perpage="10" total="881">\r\n\t<photo id="2636" owner="47058503995@N01" \r\n\t\tsecret="a123456" server="2" title="test_04"\r\n\t\tispublic="1" isfriend="0" isfamily="0">\r\n\t\t<stats views="941" comments="18" favorites="2"/>\r\n\t</photo>\r\n\t<photo id="2635" owner="47058503995@N01"\r\n\t\tsecret="b123456" server="2" title="test_03"\r\n\t\tispublic="0" isfriend="1" isfamily="1">\r\n\t\t<stats views="141" comments="1" favorites="2"/>\r\n\t</photo>\r\n</photos>', u'description': u'List the photos with the most views, comments or favorites'
        }
        , u'flickr.photos.people.delete': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The NSID passed was not a valid user id.', u'message': u'Person not found', u'code': u'1'
            }
            , {
        'text': u'The photo id passed was not a valid photo id.', u'message': u'Photo not found', u'code': u'2'
            }
            , {
        'text': u'The calling user did not have permission to remove this person from this photo.', u'message': u'User cannot remove that person', u'code': u'3'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photo to remove a person from.', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u'The NSID of the person to remove from the photo.', u'optional': u'0', u'name': u'user_id'
            }
            , {
        'text': u'An email address for an invited user.', u'optional': u'1', u'name': u'email'
            }
            ], u'description': u'Remove a person from a photo.', 'needslogin': True, u'name': u'flickr.photos.people.delete'
        }
        , u'flickr.commons.getInstitutions': {
    u'errors': [{
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Retrieves a list of the current Commons institutions.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            ], 'needslogin': False, u'response': u'<rsp stat="ok">\r\n <institutions>\r\n  <institution nsid="123456@N01" date_launch="1232000000">\r\n   <name>Institution</name>\r\n    <urls>\r\n     <url type="site">http://example.com/</url>\r\n     <url type="license">http://example.com/commons/license</url>\r\n     <url type="flickr">http://flickr.com/photos/institution</url>\r\n    </urls>\r\n   </institution>\r\n  </institutions>\r\n</rsp>', u'name': u'flickr.commons.getInstitutions'
        }
        , u'flickr.photosets.create': {
    u'errors': [{
        'text': u'No title parameter was passed in the request.', u'message': u'No title specified', u'code': u'1'
            }
            , {
        'text': u'The primary photo id passed was not a valid photo id or does not belong to the calling user.', u'message': u'Photo not found', u'code': u'2'
            }
            , {
        'text': u'The user has reached their maximum number of photosets limit.', u'message': u"Can't create any more sets", u'code': u'3'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.photosets.create', u'explanation': u'<p>New photosets are automatically put first in the photoset ordering for the user. Use <a href="/services/api/flickr.photosets.orderSets.html">flickr.photosets.orderSets</a> if you don\'t want the new set to appear first on the user\'s photoset list.</p>', 'needssigning': True, u'requiredperms': 'write', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'A title for the photoset.', u'optional': u'0', u'name': u'title'
            }
            , {
        'text': u'A description of the photoset. May contain limited html.', u'optional': u'1', u'name': u'description'
            }
            , {
        'text': u'The id of the photo to represent this set. The photo must belong to the calling user.', u'optional': u'0', u'name': u'primary_photo_id'
            }
            ], 'needslogin': True, u'response': u'<photoset id="1234" url="http://www.flickr.com/photos/bees/sets/1234/" />', u'description': u'Create a new photoset for the calling user.'
        }
        , u'flickr.people.getLimits': {
    u'errors': [{
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.people.getLimits', u'explanation': u'<ul>\r\n<li>photos/@maxdisplaypx: maximum size in pixels for photos displayed on the site (0 means that no limit is in place). No limit is placed on the dimension of photos uploaded.</li>\r\n<li>photos/@maxupload: maximum file size in bytes for photo uploads.</li>\r\n<li>videos/@maxduration: maximum duration in seconds of a video.</li>\r\n<li>videos/@maxupload: maximum file size in bytes for video uploads.</li>\r\n</ul>\r\n\r\n<p>For more details, see the documentation about <a href="http://www.flickr.com/help/limits/">limits</a>.</p>', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            ], 'needslogin': True, u'response': u'<person nsid="30135021@N05">\r\n\t<photos maxdisplaypx="1024" maxupload="15728640" />\r\n\t<videos maxduration="90" maxupload="157286400" />\r\n</person>', u'description': u'Returns the photo and video limits that apply to the calling user account.'
        }
        , u'flickr.collections.getInfo': {
    u'errors': [{
        'text': u'The requested collection could not be found or is not visible to the calling user.', u'message': u'Collection not found', u'code': u'1'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Returns information for a single collection.  Currently can only be called by the collection owner, this may change.', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The ID of the collection to fetch information for.', u'optional': u'0', u'name': u'collection_id'
            }
            ], 'needslogin': True, u'response': u'<collection id="12-72157594586579649" child_count="6" datecreate="1173812218" iconlarge="http://farm1.static.flickr.com/187/cols/73743fac2cf79_l.jpg" iconsmall="http://farm1.static.flickr.com/187/cols/72157594586579649_43fac2cf79_s.jpg" server="187" secret="36">\r\n<title>All My Photos</title>\r\n<description>Photos!</description>\r\n<iconphotos>\r\n<photo id="14" owner="12@N01" secret="b57ba5c" server="51" farm="1" title="in full cap and gown" ispublic="1" isfriend="0" isfamily="0"/>\r\n<photo id="15" owner="12@N01" secret="ba1c2a8" server="58" farm="1" title="Just beyond the door" ispublic="0" isfriend="1" isfamily="0"/>\r\n<photo id="17" owner="12@N01" secret="0001969" server="73" farm="1" title="IMG_3787.JPG" ispublic="1" isfriend="0" isfamily="0"/>\r\n....\r\n</iconphotos>\r\n</collection>', u'name': u'flickr.collections.getInfo'
        }
        , u'flickr.stats.getCSVFiles': {
    u'errors': [{
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Returns a list of URLs for text files containing <i>all</i> your stats data (from November 26th 2007 onwards) for the currently auth\'d user.\r\n\r\n<b>Please note, these files will only be available until June 1, 2010 Noon PDT.</b> \r\nFor more information <a href="/help/stats/#1369409">please check out this FAQ</a>, or just <a href="/photos/me/stats/downloads/">go download your files</a>.', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            ], 'needslogin': True, u'response': u'<stats> \r\n   <csvfiles> \r\n      <csv href="http://farm4.static.flickr.com/3496/stats/72157623902771865_faaa.csv" type="daily" date="2010-04-01" /> \r\n      <csv href="http://farm4.static.flickr.com/3376/stats/72157624027152370_fbbb.csv" type="monthly" date="2010-04-01" /> \r\n      <csv href="http://farm5.static.flickr.com/4006/stats/72157623627769689_fccc.csv" type="daily" date="2010-03-01" /> \r\n      ....\r\n    </csvfiles> \r\n</stats>', u'name': u'flickr.stats.getCSVFiles'
        }
        , u'flickr.urls.lookupUser': {
    u'errors': [{
        'text': u'The passed URL was not a valid user profile or photos url.', u'message': u'User not found', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u"Returns a user NSID, given the url to a user's photos or profile.", 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u"The url to the user's profile or photos page.", u'optional': u'0', u'name': u'url'
            }
            ], 'needslogin': False, u'response': u'<user id="12037949632@N01">\r\n\t<username>Stewart</username> \r\n</user>', u'name': u'flickr.urls.lookupUser'
        }
        , u'flickr.urls.getUserPhotos': {
    u'errors': [{
        'text': u'The NSID specified was not a valid user.', u'message': u'User not found', u'code': u'1'
            }
            , {
        'text': u'No user_id was passed and the calling user was not logged in.', u'message': u'No user specified', u'code': u'2'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u"Returns the url to a user's photos.", 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The NSID of the user to fetch the url for. If omitted, the calling user is assumed.', u'optional': u'1', u'name': u'user_id'
            }
            ], 'needslogin': False, u'response': u'<user nsid="12037949754@N01" url="http://www.flickr.com/photos/bees/" />', u'name': u'flickr.urls.getUserPhotos'
        }
        , u'flickr.photos.getContactsPhotos': {
    u'errors': [{
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u"Fetch a list of recent photos from the calling users' contacts.", 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'Number of photos to return. Defaults to 10, maximum 50. This is only used if <code>single_photo</code> is not passed.', u'optional': u'1', u'name': u'count'
            }
            , {
        'text': u'set as 1 to only show photos from friends and family (excluding regular contacts).', u'optional': u'1', u'name': u'just_friends'
            }
            , {
        'text': u'Only fetch one photo (the latest) per contact, instead of all photos in chronological order.', u'optional': u'1', u'name': u'single_photo'
            }
            , {
        'text': u'Set to 1 to include photos from the calling user.', u'optional': u'1', u'name': u'include_self'
            }
            , {
        'text': u'A comma-delimited list of extra information to fetch for each returned record. Currently supported fields include: license, date_upload, date_taken, owner_name, icon_server, original_format, last_update. For more information see extras under <a href="/services/api/flickr.photos.search.html">flickr.photos.search</a>.', u'optional': u'1', u'name': u'extras'
            }
            ], 'needslogin': True, u'response': u'<photos>\r\n\t<photo id="2801" owner="12037949629@N01"\r\n\t\tsecret="123456" server="1"\r\n\t\tusername="Eric is the best" title="grease" /> \r\n\t<photo id="2499" owner="33853651809@N01"\r\n\t\tsecret="123456" server="1"\r\n\t\tusername="cal18" title="36679_o" /> \r\n\t<photo id="2437" owner="12037951898@N01"\r\n\t\tsecret="123456" server="1"\r\n\t\tusername="georgie parker" title="phoenix9_stewart" /> \r\n</photos>', u'name': u'flickr.photos.getContactsPhotos'
        }
        , u'flickr.groups.discuss.replies.edit': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The topic_id is invalid', u'message': u'Topic not found', u'code': u'1'
            }
            , {
        'text': u'The reply_id is invalid.', u'message': u'Reply not found', u'code': u'2'
            }
            , {
        'text': u'The topic_id and reply_id are required.', u'message': u'Missing required arguments', u'code': u'3'
            }
            , {
        'text': u'Replies can only be edited by their owner.', u'message': u'Cannot edit reply', u'code': u'4'
            }
            , {
        'text': u'Either this account is not a member of the group, or discussion in this group is disabled.', u'message': u'Cannot post to group', u'code': u'5'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The ID of the topic the post is in.', u'optional': u'0', u'name': u'topic_id'
            }
            , {
        'text': u'The ID of the reply post to edit.', u'optional': u'0', u'name': u'reply_id'
            }
            , {
        'text': u'The message to edit the post with.', u'optional': u'0', u'name': u'message'
            }
            ], u'description': u'Edit a topic reply.', 'needslogin': True, u'name': u'flickr.groups.discuss.replies.edit'
        }
        , u'flickr.tags.getListUser': {
    u'errors': [{
        'text': u'The user NSID passed was not a valid user NSID and the calling user was not logged in.\r\n', u'message': u'User not found', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Get the tag list for a given user (or the currently logged in user).', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The NSID of the user to fetch the tag list for. If this argument is not specified, the currently logged in user (if any) is assumed.', u'optional': u'1', u'name': u'user_id'
            }
            ], 'needslogin': False, u'response': u'<who id="12037949754@N01">\r\n\t<tags>\r\n\t\t<tag>gull</tag> \r\n\t\t<tag>tag1</tag> \r\n\t\t<tag>tag2</tag> \r\n\t\t<tag>tags</tag> \r\n\t\t<tag>test</tag> \r\n\t</tags>\r\n</who>', u'name': u'flickr.tags.getListUser'
        }
        , u'flickr.photos.upload.checkTickets': {
    u'errors': [{
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.photos.upload.checkTickets', u'explanation': u'<p>There is one <code>&lt;ticket&gt;</code> element for each ticket id supplied. The <code>id</code> attribute contains the corresponding ticket id. If the ticket wasn\'t found, the <code>invalid</code> attribute is set. The status of the ticket is passed in the <code>status</code> attribute; 0 means not completed, 1 means completed and 2 means the ticket failed (indicating there was a problem converting the file). When the status is 1, the photo id is passed in the <code>photoid</code> attribute. The photo id can then be used as with the <a href="/services/api/upload.api.html">synchronous upload API</a>.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'A comma-delimited list of ticket ids', u'optional': u'0', u'name': u'tickets'
            }
            , {
        'text': u'', u'optional': u'1', u'name': u'batch_id'
            }
            ], 'needslogin': False, u'response': u'<uploader>\r\n\t<ticket id="128" complete="1" photoid="2995" />\r\n\t<ticket id="129" complete="0" />\r\n\t<ticket id="130" complete="2" />\r\n\t<ticket id="131" invalid="1" />\r\n</uploader>\r\n', u'description': u'Checks the status of one or more asynchronous photo upload tickets.'
        }
        , u'flickr.photosets.comments.getList': {
    u'errors': [{
        'text': u'The photoset id was invalid.', u'message': u'Photoset not found.', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Returns the comments for a photoset.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photoset to fetch comments for.', u'optional': u'0', u'name': u'photoset_id'
            }
            ], 'needslogin': False, u'response': u'<comments photoset_id="109722179">\r\n    <comment id="6065-109722179-72057594077818641"\r\n         author="35468159852@N01" authorname="Rev Dan Catt" date_create="1141841470"\r\n         permalink="http://www.flickr.com/photos/straup/109722179/#comment72057594077818641"\r\n         >Umm, I\'m not sure, can I get back to you on that one?</comment>\r\n</comments>', u'name': u'flickr.photosets.comments.getList'
        }
        , u'flickr.places.getInfo': {
    u'errors': [{
        'text': u'One or more required parameter is missing from the API call.', u'message': u'Required parameter missing', u'code': u'1'
            }
            , {
        'text': u'An invalid Places (or WOE) ID was passed with the API call.', u'message': u'Not a valid Places ID', u'code': u'2'
            }
            , {
        'text': u'No place could be found for the Places (or WOE) ID passed to the API call.', u'message': u'Place not found', u'code': u'3'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.places.getInfo', u'explanation': u'  ', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'A Flickr Places ID. <span style="font-style:italic;">(While optional, you must pass either a valid Places ID or a WOE ID.)</span>', u'optional': u'1', u'name': u'place_id'
            }
            , {
        'text': u'A Where On Earth (WOE) ID. <span style="font-style:italic;">(While optional, you must pass either a valid Places ID or a WOE ID.)</span>', u'optional': u'1', u'name': u'woe_id'
            }
            ], 'needslogin': False, u'response': u'<place place_id="4hLQygSaBJ92" woeid="3534"\r\n   latitude="45.512" longitude="-73.554"\r\n   place_url="/Canada/Quebec/Montreal" place_type="locality"\r\n   has_shapedata="1" timezone="America/Toronto">\r\n   <locality place_id="4hLQygSaBJ92" woeid="3534"\r\n      latitude="45.512" longitude="-73.554"\r\n      place_url="/Canada/Quebec/Montreal">Montreal</locality>\r\n   <county place_id="cFBi9x6bCJ8D5rba1g" woeid="29375198"\r\n      latitude="45.551" longitude="-73.600" \r\n      place_url="/cFBi9x6bCJ8D5rba1g">Montr\xe9al</county>\r\n   <region place_id="CrZUvXebApjI0.72" woeid="2344924" \r\n      latitude="53.890" longitude="-68.429"\r\n      place_url="/Canada/Quebec">Quebec</region>\r\n   <country place_id="EESRy8qbApgaeIkbsA" woeid="23424775"\r\n      latitude="62.358" longitude="-96.582" \r\n      place_url="/Canada">Canada</country>\r\n   <shapedata created="1223513357" alpha="0.012359619140625"\r\n      count_points="34778" count_edges="52"\r\n      has_donuthole="1" is_donuthole="1">\r\n      <polylines>\r\n         <polyline>\r\n            45.427627563477,-73.589645385742 45.428966522217,-73.587898254395, etc...\r\n         </polyline>\r\n      </polylines>\r\n      <urls>\r\n         <shapefile>\r\n         http://farm4.static.flickr.com/3228/shapefiles/3534_20081111_0a8afe03c5.tar.gz\r\n         </shapefile>\r\n      </urls>\r\n   </shapedata>\r\n</place>', u'description': u'Get informations about a place.'
        }
        , u'flickr.photos.people.deleteCoords': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The NSID passed was not a valid user id.', u'message': u'Person not found', u'code': u'1'
            }
            , {
        'text': u'The photo id passed was not a valid photo id.', u'message': u'Photo not found', u'code': u'2'
            }
            , {
        'text': u'The calling user is neither the person depicted in the photo nor the person who added the bounding box.', u'message': u'User cannot edit that person in that photo', u'code': u'3'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photo to edit a person in.', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u'The NSID of the person whose bounding box you want to remove.', u'optional': u'0', u'name': u'user_id'
            }
            ], u'description': u'Remove the bounding box from a person in a photo', 'needslogin': True, u'name': u'flickr.photos.people.deleteCoords'
        }
        , u'flickr.photos.geo.setLocation': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The photo id was either invalid or was for a photo not viewable by the calling user.', u'message': u'Photo not found', u'code': u'1'
            }
            , {
        'text': u'Some or all of the required arguments were not supplied.', u'message': u'Required arguments missing.', u'code': u'2'
            }
            , {
        'text': u'The latitude argument failed validation.', u'message': u'Not a valid latitude.', u'code': u'3'
            }
            , {
        'text': u'The longitude argument failed validation.', u'message': u'Not a valid longitude.', u'code': u'4'
            }
            , {
        'text': u'The accuracy argument failed validation.', u'message': u'Not a valid accuracy.', u'code': u'5'
            }
            , {
        'text': u'There was an unexpected problem setting location information to the photo.', u'message': u'Server error.', u'code': u'6'
            }
            , {
        'text': u'Before users may assign location data to a photo they must define who, by default, may view that information. Users can edit this preference at <a href="http://www.flickr.com/account/geo/privacy/">http://www.flickr.com/account/geo/privacy/</a>', u'message': u'User has not configured default viewing settings for location data.', u'code': u'7'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photo to set location data for.', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u'The latitude whose valid range is -90 to 90. Anything more than 6 decimal places will be truncated.', u'optional': u'0', u'name': u'lat'
            }
            , {
        'text': u'The longitude whose valid range is -180 to 180. Anything more than 6 decimal places will be truncated.', u'optional': u'0', u'name': u'lon'
            }
            , {
        'text': u'Recorded accuracy level of the location information. World level is 1, Country is ~3, Region ~6, City ~11, Street ~16. Current range is 1-16. Defaults to 16 if not specified.', u'optional': u'1', u'name': u'accuracy'
            }
            , {
        'text': u'Context is a numeric value representing the photo\'s geotagginess beyond latitude and longitude. For example, you may wish to indicate that a photo was taken "indoors" or "outdoors". <br /><br />\r\nThe current list of context IDs is :<br /><br/>\r\n<ul>\r\n<li><strong>0</strong>, not defined.</li>\r\n<li><strong>1</strong>, indoors.</li>\r\n<li><strong>2</strong>, outdoors.</li>\r\n</ul><br />\r\nThe default context for geotagged photos is 0, or "not defined"\r\n', u'optional': u'1', u'name': u'context'
            }
            , {
        'text': u'Associate a geo bookmark with this photo.', u'optional': u'1', u'name': u'bookmark_id'
            }
            , {
        'text': u'', u'optional': u'1', u'name': u'is_public'
            }
            , {
        'text': u'', u'optional': u'1', u'name': u'is_contact'
            }
            , {
        'text': u'', u'optional': u'1', u'name': u'is_friend'
            }
            , {
        'text': u'', u'optional': u'1', u'name': u'is_family'
            }
            , {
        'text': u'The venue ID for a Foursquare location.', u'optional': u'1', u'name': u'foursquare_id'
            }
            , {
        'text': u'A Where On Earth (WOE) ID. (If passed in, will override the default venue based on the lat/lon.)', u'optional': u'1', u'name': u'woeid'
            }
            ], u'description': u'Sets the geo data (latitude and longitude and, optionally, the accuracy level) for a photo.\r\n\r\nBefore users may assign location data to a photo they must define who, by default, may view that information. Users can edit this preference at <a href="http://www.flickr.com/account/geo/privacy/">http://www.flickr.com/account/geo/privacy/</a>. If a user has not set this preference, the API method will return an error.', 'needslogin': True, u'name': u'flickr.photos.geo.setLocation'
        }
        , u'flickr.push.getTopics': {
    u'errors': [{
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'All the different flavours of anteater.\r\n<br><br>\r\n<i>(this method is experimental and may change)</i>', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            ], 'needslogin': False, u'response': u'<rsp stat="ok">\r\n  <topics>\r\n    <topic name="contacts_photos" />\r\n    <topic name="contacts_faves" />\r\n  </topics>\r\n</rsp>', u'name': u'flickr.push.getTopics'
        }
        , u'flickr.tags.getRelated': {
    u'errors': [{
        'text': u'The tag argument was missing.', u'message': u'Tag not found', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u"Returns a list of tags 'related' to the given tag, based on clustered usage analysis.", 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The tag to fetch related tags for.', u'optional': u'0', u'name': u'tag'
            }
            ], 'needslogin': False, u'response': u'<tags source="london">\r\n\t<tag>england</tag>\r\n\t<tag>thames</tag>\r\n\t<tag>tube</tag>\r\n\t<tag>bigben</tag>\r\n\t<tag>uk</tag>\r\n</tags>\r\n', u'name': u'flickr.tags.getRelated'
        }
        , u'flickr.favorites.getContext': {
    u'errors': [{
        'text': u'The photo id passed was not a valid photo id, or was the id of a photo that the calling user does not have permission to view.', u'message': u'Photo not found', u'code': u'1'
            }
            , {
        'text': u'The specified user was not found.', u'message': u'User not found', u'code': u'2'
            }
            , {
        'text': u'The specified photo is not a favorite of the specified user.', u'message': u'Photo not a favorite', u'code': u'3'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.favorites.getContext', u'explanation': u'<p>See <a href="/services/api/flickr.photos.getContext.html">flickr.photos.getContext</a></p>', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photo to fetch the context for.', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u'The user who counts the photo as a favorite.', u'optional': u'0', u'name': u'user_id'
            }
            , {
        'text': u'', u'optional': u'1', u'name': u'num_prev'
            }
            , {
        'text': u'', u'optional': u'1', u'name': u'num_next'
            }
            , {
        'text': u'A comma-delimited list of extra information to fetch for each returned record. Currently supported fields are: description, license, date_upload, date_taken, owner_name, icon_server, original_format, last_update, geo, tags, machine_tags, o_dims, views, media, path_alias, url_sq, url_t, url_s, url_m, url_z, url_l, url_o', u'optional': u'1', u'name': u'extras'
            }
            ], 'needslogin': False, u'response': u'<rsp stat=\'ok\'>\r\n<count>3</count>\r\n<prevphoto id="2980" secret="973da1e709"\r\n\ttitle="boo!" url="/photos/bees/2980/" /> \r\n<nextphoto id="2985" secret="059b664012"\r\n\ttitle="Amsterdam Amstel" url="/photos/bees/2985/" />\r\n</rsp>', u'description': u"Returns next and previous favorites for a photo in a user's favorites."
        }
        , u'flickr.photosets.comments.deleteComment': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The comment id passed was not a valid comment id', u'message': u'Comment not found.', u'code': u'2'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the comment to delete from a photoset.', u'optional': u'0', u'name': u'comment_id'
            }
            ], u'description': u'Delete a photoset comment as the currently authenticated user.', 'needslogin': True, u'name': u'flickr.photosets.comments.deleteComment'
        }
        , u'flickr.prefs.getPrivacy': {
    u'errors': [{
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Returns the default privacy level preference for the user.\r\n\r\nPossible values are:\r\n<ul>\r\n<li>1 : Public</li>\r\n<li>2 : Friends only</li>\r\n<li>3 : Family only</li>\r\n<li>4 : Friends and Family</li>\r\n<li>5 : Private</li>\r\n</ul>', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            ], 'needslogin': True, u'response': u'<rsp stat="ok">\r\n<person nsid="12037949754@N01" privacy="1" />\r\n</rsp>', u'name': u'flickr.prefs.getPrivacy'
        }
        , u'flickr.push.getSubscriptions': {
    u'errors': [{
        'text': u'PuSH subscriptions are currently restricted to Pro account holders.', u'message': u'Service currently available only to pro accounts', u'code': u'5'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Returns a list of the subscriptions for the logged-in user.\r\n<br><br>\r\n<i>(this method is experimental and may change)</i>', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            ], 'needslogin': True, u'response': u'<rsp stat="ok">\r\n  <subscriptions>\r\n    <subscription topic="contacts_photos" callback="http://example.com/contacts_photos_endpoint?user=12345" pending="0" date_create="1309293755" lease_seconds="0" expiry="1309380155" verify_attempts="0" />\r\n    <subscription topic="contacts_faves" callback="http://example.com/contacts_faves_endpoint?user=12345" pending="0" date_create="1309293785" lease_seconds="0" expiry="1309380185" verify_attempts="0" />\r\n  </subscriptions>\r\n</rsp>', u'name': u'flickr.push.getSubscriptions'
        }
        , u'flickr.photos.suggestions.rejectSuggestion': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The unique ID of the suggestion to reject.', u'optional': u'0', u'name': u'suggestion_id'
            }
            ], u'description': u'Reject a suggestion for a photo.', 'needslogin': True, u'name': u'flickr.photos.suggestions.rejectSuggestion'
        }
        , u'flickr.tags.getHotList': {
    u'errors': [{
        'text': u'The specified period was not understood.', u'message': u'Invalid period', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Returns a list of hot tags for the given period.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The period for which to fetch hot tags. Valid values are <code>day</code> and <code>week</code> (defaults to <code>day</code>).', u'optional': u'1', u'name': u'period'
            }
            , {
        'text': u'The number of tags to return. Defaults to 20. Maximum allowed value is 200.', u'optional': u'1', u'name': u'count'
            }
            ], 'needslogin': False, u'response': u'<hottags period="day" count="6">\r\n\t<tag score="20">northerncalifornia</tag>\r\n\t<tag score="18">top20</tag>\r\n\t<tag score="15">keychain</tag>\r\n\t<tag score="10">zb</tag>\r\n\t<tag score="9">selfportraittuesday</tag>\r\n\t<tag score="4">jan06</tag>\r\n</hottags>', u'name': u'flickr.tags.getHotList'
        }
        , u'flickr.galleries.editPhoto': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'That gallery could not be found.', u'message': u'Invalid gallery ID', u'code': u'1'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The ID of the gallery to add a photo to. Note: this is the compound ID returned in methods like flickr.galleries.getList, and flickr.galleries.getListForPhoto.', u'optional': u'0', u'name': u'gallery_id'
            }
            , {
        'text': u'The photo ID to add to the gallery.', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u'The updated comment the photo.', u'optional': u'0', u'name': u'comment'
            }
            ], u'description': u'Edit the comment for a gallery photo.', 'needslogin': True, u'name': u'flickr.galleries.editPhoto'
        }
        , u'flickr.galleries.getList': {
    u'errors': [{
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Return the list of galleries created by a user.  Sorted from newest to oldest.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The NSID of the user to get a galleries list for. If none is specified, the calling user is assumed.', u'optional': u'0', u'name': u'user_id'
            }
            , {
        'text': u'Number of galleries to return per page. If this argument is omitted, it defaults to 100. The maximum allowed value is 500.', u'optional': u'1', u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': u'1', u'name': u'page'
            }
            ], 'needslogin': False, u'response': u'<galleries total="9" page="1" pages="1" per_page="100" user_id="34427469121@N01">\r\n   <gallery id="5704-72157622637971865" \r\n             url="http://www.flickr.com/photos/george/galleries/72157622637971865" \r\n             owner="34427469121@N01" date_create="1257711422" date_update="1260360756"\r\n             primary_photo_id="107391222"  primary_photo_server="39" \r\n             primary_photo_farm="1" primary_photo_secret="ffa"\r\n             count_photos="16" count_videos="2" >\r\n       <title>I like me some black &amp; white</title>\r\n       <description>black and whites</description>\r\n   </gallery>\r\n   <gallery id="5704-72157622566655097" \r\n            url="http://www.flickr.com/photos/george/galleries/72157622566655097" \r\n            owner="34427469121@N01" date_create="1256852229" date_update="1260462343" \r\n            primary_photo_id="497374910" primary_photo_server="231" \r\n            primary_photo_farm="1" primary_photo_secret="9ae0f"\r\n            count_photos="18" count_videos="0" >\r\n       <title>People Sleeping in Libraries</title>\r\n       <description />\r\n   </gallery>\r\n</galleries>', u'name': u'flickr.galleries.getList'
        }
        , u'flickr.groups.discuss.replies.add': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The topic_id is invalid.', u'message': u'Topic not found', u'code': u'1'
            }
            , {
        'text': u'Either this account is not a member of the group, or discussion in this group is disabled.\r\n', u'message': u'Cannot post to group', u'code': u'2'
            }
            , {
        'text': u'The topic_id and message are required.', u'message': u'Missing required arguments', u'code': u'3'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The ID of the topic to post a comment to.', u'optional': u'0', u'name': u'topic_id'
            }
            , {
        'text': u'The message to post to the topic.', u'optional': u'0', u'name': u'message'
            }
            ], u'description': u'Post a new reply to a group discussion topic.', 'needslogin': True, u'name': u'flickr.groups.discuss.replies.add'
        }
        , u'flickr.favorites.getList': {
    'needssigning': True, u'requiredperms': 'read', u'errors': [{
        'text': u'The specified user NSID was not a valid flickr user.', u'message': u'User not found', u'code': u'1'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The NSID of the user to fetch the favorites list for. If this argument is omitted, the favorites list for the calling user is returned.', u'optional': u'1', u'name': u'user_id'
            }
            , {
        'text': u'', u'optional': u'1', u'name': u'jump_to'
            }
            , {
        'text': u'Minimum date that a photo was favorited on. The date should be in the form of a unix timestamp.', u'optional': u'1', u'name': u'min_fave_date'
            }
            , {
        'text': u'Maximum date that a photo was favorited on. The date should be in the form of a unix timestamp.', u'optional': u'1', u'name': u'max_fave_date'
            }
            , {
        'text': u'A comma-delimited list of extra information to fetch for each returned record. Currently supported fields are: <code>description</code>, <code>license</code>, <code>date_upload</code>, <code>date_taken</code>, <code>owner_name</code>, <code>icon_server</code>, <code>original_format</code>, <code>last_update</code>, <code>geo</code>, <code>tags</code>, <code>machine_tags</code>, <code>o_dims</code>, <code>views</code>, <code>media</code>, <code>path_alias</code>, <code>url_sq</code>, <code>url_t</code>, <code>url_s</code>, <code>url_q</code>, <code>url_m</code>, <code>url_n</code>, <code>url_z</code>, <code>url_c</code>, <code>url_l</code>, <code>url_o</code>', u'optional': 1, u'name': u'extras'
            }
            , {
        'text': u'Number of photos to return per page. If this argument is omitted, it defaults to 100. The maximum allowed value is 500.', u'optional': 1, u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': 1, u'name': u'page'
            }
            ], u'description': u"Returns a list of the user's favorite photos. Only photos which the calling user has permission to see are returned.", 'needslogin': True, u'name': u'flickr.favorites.getList'
        }
        , u'flickr.favorites.add': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The photo id passed was not a valid photo id.', u'message': u'Photo not found', u'code': u'1'
            }
            , {
        'text': u'The photo belongs to the user and so cannot be added to their favorites.', u'message': u'Photo is owned by you', u'code': u'2'
            }
            , {
        'text': u"The photo is already in the user's list of favorites.", u'message': u'Photo is already in favorites', u'code': u'3'
            }
            , {
        'text': u'The user does not have permission to add the photo to their favorites.', u'message': u'User cannot see photo', u'code': u'4'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u"The id of the photo to add to the user's favorites.", u'optional': u'0', u'name': u'photo_id'
            }
            ], u'description': u"Adds a photo to a user's favorites list.", 'needslogin': True, u'name': u'flickr.favorites.add'
        }
        , u'flickr.galleries.editPhotos': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the gallery to modify. The gallery must belong to the calling user.', u'optional': u'0', u'name': u'gallery_id'
            }
            , {
        'text': u"The id of the photo to use as the 'primary' photo for the gallery. This id must also be passed along in photo_ids list argument.", u'optional': u'0', u'name': u'primary_photo_id'
            }
            , {
        'text': u'A comma-delimited list of photo ids to include in the gallery. They will appear in the set in the order sent. This list must contain the primary photo id. This list of photos replaces the existing list.', u'optional': u'0', u'name': u'photo_ids'
            }
            ], u'description': u'Modify the photos in a gallery. Use this method to add, remove and re-order photos.', 'needslogin': True, u'name': u'flickr.galleries.editPhotos'
        }
        , u'flickr.urls.lookupGroup': {
    u'errors': [{
        'text': u'The passed URL was not a valid group page or photo pool url.', u'message': u'Group not found', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u"Returns a group NSID, given the url to a group's page or photo pool.", 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u"The url to the group's page or photo pool.", u'optional': u'0', u'name': u'url'
            }
            ], 'needslogin': False, u'response': u'<group id="34427469792@N01">\r\n\t<groupname>FlickrCentral</groupname> \r\n</group>', u'name': u'flickr.urls.lookupGroup'
        }
        , u'flickr.favorites.getPublicList': {
    'needssigning': False, u'requiredperms': 'none', u'errors': [{
        'text': u'The specified user NSID was not a valid flickr user.', u'message': u'User not found', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The user to fetch the favorites list for.', u'optional': u'0', u'name': u'user_id'
            }
            , {
        'text': u'', u'optional': u'1', u'name': u'jump_to'
            }
            , {
        'text': u'Minimum date that a photo was favorited on. The date should be in the form of a unix timestamp.', u'optional': u'1', u'name': u'min_fave_date'
            }
            , {
        'text': u'Maximum date that a photo was favorited on. The date should be in the form of a unix timestamp.', u'optional': u'1', u'name': u'max_fave_date'
            }
            , {
        'text': u'A comma-delimited list of extra information to fetch for each returned record. Currently supported fields are: <code>description</code>, <code>license</code>, <code>date_upload</code>, <code>date_taken</code>, <code>owner_name</code>, <code>icon_server</code>, <code>original_format</code>, <code>last_update</code>, <code>geo</code>, <code>tags</code>, <code>machine_tags</code>, <code>o_dims</code>, <code>views</code>, <code>media</code>, <code>path_alias</code>, <code>url_sq</code>, <code>url_t</code>, <code>url_s</code>, <code>url_q</code>, <code>url_m</code>, <code>url_n</code>, <code>url_z</code>, <code>url_c</code>, <code>url_l</code>, <code>url_o</code>', u'optional': 1, u'name': u'extras'
            }
            , {
        'text': u'Number of photos to return per page. If this argument is omitted, it defaults to 100. The maximum allowed value is 500.', u'optional': 1, u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': 1, u'name': u'page'
            }
            ], u'description': u'Returns a list of favorite public photos for the given user.', 'needslogin': False, u'name': u'flickr.favorites.getPublicList'
        }
        , u'flickr.people.getPhotosOf': {
    u'errors': [{
        'text': u'A user_id was passed which did not match a valid flickr user.', u'message': u'User not found.', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.people.getPhotosOf', u'explanation': u'<p>This method returns a variant of the standard photo list xml.</p>\r\n\r\n<p>For queries about a member other than the currently authenticated one, pagination data ("total" and "pages" attributes) will not be available.</p>\r\n\r\n<p>Instead, the <photos> element will contain a boolean value \'has_next_page\' which will tell you whether or not there are more photos to fetch.</p>', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The NSID of the user you want to find photos of. A value of "me" will search against photos of the calling user, for authenticated calls.', u'optional': u'0', u'name': u'user_id'
            }
            , {
        'text': u'An NSID of a Flickr member. This will restrict the list of photos to those taken by that member.', u'optional': u'1', u'name': u'owner_id'
            }
            , {
        'text': u'A comma-delimited list of extra information to fetch for each returned record. Currently supported fields are: <code>description</code>, <code>license</code>, <code>date_upload</code>, <code>date_taken</code>, <code>date_person_added</code>, <code>owner_name</code>, <code>icon_server</code>, <code>original_format</code>, <code>last_update</code>, <code>geo</code>, <code>tags</code>, <code>machine_tags</code>, <code>o_dims</code>, <code>views</code>, <code>media</code>, <code>path_alias</code>, <code>url_sq</code>, <code>url_t</code>, <code>url_s</code>, <code>url_q</code>, <code>url_m</code>, <code>url_n</code>, <code>url_z</code>, <code>url_c</code>, <code>url_l</code>, <code>url_o</code>', u'optional': 1, u'name': u'extras'
            }
            , {
        'text': u'Number of photos to return per page. If this argument is omitted, it defaults to 100. The maximum allowed value is 500.', u'optional': 1, u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': 1, u'name': u'page'
            }
            ], 'needslogin': False, u'response': u'<photos page="2" has_next_page="1" perpage="10">\r\n\t<photo id="2636" owner="47058503995@N01" \r\n\t\tsecret="a123456" server="2" title="test_04"\r\n\t\tispublic="1" isfriend="0" isfamily="0" />\r\n\t<photo id="2635" owner="47058503995@N01"\r\n\t\tsecret="b123456" server="2" title="test_03"\r\n\t\tispublic="0" isfriend="1" isfamily="1" />\r\n\t<photo id="2633" owner="47058503995@N01"\r\n\t\tsecret="c123456" server="2" title="test_01"\r\n\t\tispublic="1" isfriend="0" isfamily="0" />\r\n\t<photo id="2610" owner="12037949754@N01"\r\n\t\tsecret="d123456" server="2" title="00_tall"\r\n\t\tispublic="1" isfriend="0" isfamily="0" />\r\n</photos>', u'description': u'Returns a list of photos containing a particular Flickr member.'
        }
        , u'flickr.reflection.getMethodInfo': {
    u'errors': [{
        'text': u'The requested method was not found.', u'message': u'Method not found', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Returns information for a given flickr API method.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The name of the method to fetch information for.', u'optional': u'0', u'name': u'method_name'
            }
            ], 'needslogin': False, u'response': u'<method name="flickr.fakeMethod" needslogin="1">\r\n\t<description>A fake method</description> \r\n\t<response>xml-response-example</response> \r\n\t<explanation>explanation of example response</explanation> \r\n\t<arguments>\r\n\t\t<argument name="api_key" optional="0">\r\n\t\t\tYou API application key.</argument> \r\n\t\t<argument name="color" optional="1">\r\n\t\t\tYour favorite color.</argument> \r\n\t</arguments>\r\n\t<errors>\r\n\t\t<error code="1" message="Photo not found">\r\n\t\t\tFull explanation...</error> \r\n\t\t<error code="100" message="Invalid API Key">\r\n\t\t\tFull explanation...</error> \r\n\t</errors>\r\n</method>\r\n', u'name': u'flickr.reflection.getMethodInfo'
        }
        , u'flickr.places.tagsForPlace': {
    u'errors': [{
        'text': u'One or more parameters was not included with the API request', u'message': u'Required parameter missing', u'code': u'1'
            }
            , {
        'text': u'An invalid Places (or WOE) identifier was included with your request.', u'message': u'Not a valid Places ID', u'code': u'2'
            }
            , {
        'text': u'An invalid Places (or WOE) identifier was included with your request.', u'message': u'Place not found', u'code': u'3'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Return a list of the top 100 unique tags for a Flickr Places or Where on Earth (WOE) ID', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'A Where on Earth identifier to use to filter photo clusters.<br /><br />\r\n<span style="font-style:italic;">(While optional, you must pass either a valid Places ID or a WOE ID.)</span>', u'optional': u'1', u'name': u'woe_id'
            }
            , {
        'text': u'A Flickr Places identifier to use to filter photo clusters.<br /><br />\r\n<span style="font-style:italic;">(While optional, you must pass either a valid Places ID or a WOE ID.)</span>', u'optional': u'1', u'name': u'place_id'
            }
            , {
        'text': u'Minimum upload date. Photos with an upload date greater than or equal to this value will be returned. The date should be in the form of a unix timestamp.', u'optional': u'1', u'name': u'min_upload_date'
            }
            , {
        'text': u'Maximum upload date. Photos with an upload date less than or equal to this value will be returned. The date should be in the form of a unix timestamp.', u'optional': u'1', u'name': u'max_upload_date'
            }
            , {
        'text': u'Minimum taken date. Photos with an taken date greater than or equal to this value will be returned. The date should be in the form of a mysql datetime.', u'optional': u'1', u'name': u'min_taken_date'
            }
            , {
        'text': u'Maximum taken date. Photos with an taken date less than or equal to this value will be returned. The date should be in the form of a mysql datetime.', u'optional': u'1', u'name': u'max_taken_date'
            }
            ], 'needslogin': False, u'response': u'<tags total="100">\r\n   <tag count="31775">montreal</tag>\r\n   <tag count="20585">canada</tag>\r\n   <tag count="12319">montr\xe9al</tag>\r\n   <tag count="12154">quebec</tag>\r\n   <tag count="6471">qu\xe9bec</tag>\r\n   <tag count="2173">sylvainmichaud</tag>\r\n   <tag count="2091">nikon</tag>\r\n   <tag count="1541">lucbus</tag>\r\n   <tag count="1539">music</tag>\r\n   <tag count="1479">urban</tag>\r\n   <tag count="1425">lucbussieres</tag>\r\n   <tag count="1419">festival</tag>\r\n   <!-- and so on -->\r\n</tags>', u'name': u'flickr.places.tagsForPlace'
        }
        , u'flickr.groups.joinRequest': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The group_id or message argument are missing.', u'message': u'Required arguments missing', u'code': u'1'
            }
            , {
        'text': u'The Group does not exist', u'message': u'Group does not exist', u'code': u'2'
            }
            , {
        'text': u'The authed account does not have permission to view/join the group.', u'message': u'Group not available to the account', u'code': u'3'
            }
            , {
        'text': u'The authed account has previously joined this group', u'message': u'Account is already in that group', u'code': u'4'
            }
            , {
        'text': u'The group does not require an invitation to join, please use flickr.groups.join.', u'message': u'Group is public and open', u'code': u'5'
            }
            , {
        'text': u'The user must read and accept the rules before joining. Please see the accept_rules argument for this method.', u'message': u'User must accept the group rules before joining', u'code': u'6'
            }
            , {
        'text': u'A request has already been sent and is pending approval.', u'message': u'User has already requested to join that group', u'code': u'7'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The NSID of the group to request joining.', u'optional': u'0', u'name': u'group_id'
            }
            , {
        'text': u'Message to the administrators.', u'optional': u'0', u'name': u'message'
            }
            , {
        'text': u'If the group has rules, they must be displayed to the user prior to joining. Passing a true value for this argument specifies that the application has displayed the group rules to the user, and that the user has agreed to them. (See flickr.groups.getInfo).', u'optional': u'0', u'name': u'accept_rules'
            }
            ], u'description': u'Request to join a group that is invitation-only.', 'needslogin': True, u'name': u'flickr.groups.joinRequest'
        }
        , u'flickr.photos.setSafetyLevel': {
    u'errors': [{
        'text': u'The photo id passed was not a valid photo id of a photo belonging to the calling user.', u'message': u'Photo not found', u'code': u'1'
            }
            , {
        'text': u'Neither a valid safety level nor a hidden value were passed.', u'message': u'Invalid or missing arguments', u'code': u'2'
            }
            , {
        'text': u'Changing the safety level of this photo is not allowed.', u'message': u'Change not allowed', u'code': u'3'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Set the safety level of a photo.', 'needssigning': True, u'requiredperms': 'write', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photo to set the adultness of.', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u'The safety level of the photo.  Must be one of:\r\n\r\n1 for Safe, 2 for Moderate, and 3 for Restricted.', u'optional': u'1', u'name': u'safety_level'
            }
            , {
        'text': u'Whether or not to additionally hide the photo from public searches.  Must be either 1 for Yes or 0 for No.', u'optional': u'1', u'name': u'hidden'
            }
            ], 'needslogin': True, u'response': u'<rsp stat="ok">\r\n<photo id="14814" safety_level="2" hidden="0"/>\r\n</rsp>', u'name': u'flickr.photos.setSafetyLevel'
        }
        , u'flickr.places.resolvePlaceURL': {
    u'errors': [{
        'text': u'', u'message': u'Place URL required.', u'code': u'2'
            }
            , {
        'text': u'', u'message': u'Place not found.', u'code': u'3'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Find Flickr Places information by Place URL.<br /><br />\r\nThis method has been deprecated. It won\'t be removed but you should use <a href="/services/api/flickr.places.getInfoByUrl.html">flickr.places.getInfoByUrl</a> instead.\r\n', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'A Flickr Places URL.  \r\n<br /><br />\r\nFlickr Place URLs are of the form /country/region/city', u'optional': u'0', u'name': u'url'
            }
            ], 'needslogin': False, u'response': u'<location place_id="kH8dLOubBZRvX_YZ" woeid="2487956" \r\n                latitude="37.779" longitude="-122.420"\r\n                place_url="/United+States/California/San+Francisco"\r\n                place_type="locality">\r\n   <locality place_id="kH8dLOubBZRvX_YZ" woeid="2487956"\r\n                 latitude="37.779" longitude="-122.420" \r\n                 place_url="/United+States/California/San+Francisco">San Francisco</locality>\r\n   <county place_id="hCca8XSYA5nn0X1Sfw" woeid="12587707"\r\n                 latitude="37.759" longitude="-122.435" \r\n                 place_url="/hCca8XSYA5nn0X1Sfw">San Francisco</county>\r\n   <region place_id="SVrAMtCbAphCLAtP" woeid="2347563" \r\n                latitude="37.271" longitude="-119.270" \r\n                place_url="/United+States/California">California</region>\r\n   <country place_id="4KO02SibApitvSBieQ" woeid="23424977"\r\n                  latitude="48.890" longitude="-116.982" \r\n                  place_url="/United+States">United States</country>\r\n</location>', u'name': u'flickr.places.resolvePlaceURL'
        }
        , u'flickr.contacts.getTaggingSuggestions': {
    u'errors': [{
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u"Get suggestions for tagging people in photos based on the calling user's contacts.", 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'Return calling user in the list of suggestions. Default: true.', u'optional': u'1', u'name': u'include_self'
            }
            , {
        'text': u"Include suggestions from the user's address book. Default: false", u'optional': u'1', u'name': u'include_address_book'
            }
            , {
        'text': u'Number of contacts to return per page. If this argument is omitted, all contacts will be returned.', u'optional': u'1', u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': u'1', u'name': u'page'
            }
            ], 'needslogin': True, u'response': u'<rsp stat="ok">\r\n<contacts page="1" pages="1" perpage="1000" total="1">\r\n\t<contact nsid="30135021@N05" username="Hugo Haas" iconserver="1" iconfarm="1" realname="" friend="0" family="0" path_alias="" />\r\n</contacts>\r\n</rsp>', u'name': u'flickr.contacts.getTaggingSuggestions'
        }
        , u'flickr.tags.getListPhoto': {
    u'errors': [{
        'text': u'The photo id passed was not a valid photo id.', u'message': u'Photo not found', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.tags.getListPhoto', u'explanation': u'<p>For an explanation of the <code>tag</code> element, please read the <a href="/services/api/misc.tags.html">tags documentation</a>.</p>', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photo to return tags for.', u'optional': u'0', u'name': u'photo_id'
            }
            ], 'needslogin': False, u'response': u'<photo id="2619">\r\n\t<tags>\r\n\t\t<tag id="156" author="12037949754@N01"\r\n\t\t\tauthorname="Bees" raw="tag 1">tag1</tag> \r\n\t\t<tag id="157" author="12037949754@N01"\r\n\t\t\tauthorname="Bees" raw="tag 2">tag2</tag> \r\n\t</tags>\r\n</photo>', u'description': u'Get the tag list for a given photo.'
        }
        , u'flickr.auth.oauth.checkToken': {
    u'errors': [{
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Returns the credentials attached to an OAuth authentication token.', 'needssigning': True, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The OAuth authentication token to check.', u'optional': u'0', u'name': u'oauth_token'
            }
            ], 'needslogin': False, u'response': u'<oauth>\r\n    <token>72157627611980735-09e87c3024f733da</token>\r\n    <perms>write</perms>\r\n    <user nsid="1121451801@N07" username="jamalf" fullname="Jamal F"/>\r\n</oauth>', u'name': u'flickr.auth.oauth.checkToken'
        }
        , u'flickr.auth.oauth.getAccessToken': {
    u'errors': [{
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Exchange an auth token from the old Authentication API, to an OAuth access token. Calling this method will delete the auth token used to make the request.', 'needssigning': True, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            ], 'needslogin': False, u'response': u'<auth> \r\n\t<access_token oauth_token="72157607082540144-8d5d7ea7696629bf" oauth_token_secret="f38bf58b2d95bc8b" /> \r\n</auth> ', u'name': u'flickr.auth.oauth.getAccessToken'
        }
        , u'flickr.groups.join': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u"The group_id doesn't exist", u'message': u'Required arguments missing', u'code': u'1'
            }
            , {
        'text': u'The Group does not exist', u'message': u'Group does not exist', u'code': u'2'
            }
            , {
        'text': u'The authed account does not have permission to view/join the group.', u'message': u'Group not availabie to the account', u'code': u'3'
            }
            , {
        'text': u'The authed account has previously joined this group', u'message': u'Account is already in that group', u'code': u'4'
            }
            , {
        'text': u'Use flickr.groups.joinRequest to contact the administrations for an invitation.', u'message': u'Membership in group is by invitation only.', u'code': u'5'
            }
            , {
        'text': u'The user must read and accept the rules before joining. Please see the accept_rules argument for this method.', u'message': u'User must accept the group rules before joining', u'code': u'6'
            }
            , {
        'text': u'The account is a member of the maximum number of groups.', u'message': u'Account in maximum number of groups', u'code': u'10'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The NSID of the Group in question', u'optional': u'0', u'name': u'group_id'
            }
            , {
        'text': u'If the group has rules, they must be displayed to the user prior to joining. Passing a true value for this argument specifies that the application has displayed the group rules to the user, and that the user has agreed to them. (See flickr.groups.getInfo).', u'optional': u'1', u'name': u'accept_rules'
            }
            ], u'description': u'Join a public group as a member.', 'needslogin': True, u'name': u'flickr.groups.join'
        }
        , u'flickr.photosets.setPrimaryPhoto': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The photoset id passed was not the id of avalid photoset owned by the calling user.', u'message': u'Photoset not found', u'code': u'1'
            }
            , {
        'text': u'The photo id passed was not the id of a valid photo owned by the calling user.', u'message': u'Photo not found', u'code': u'2'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photoset to set primary photo to.', u'optional': u'0', u'name': u'photoset_id'
            }
            , {
        'text': u'The id of the photo to set as primary.', u'optional': u'0', u'name': u'photo_id'
            }
            ], u'description': u'Set photoset primary photo', 'needslogin': True, u'name': u'flickr.photosets.setPrimaryPhoto'
        }
        , u'flickr.people.findByEmail': {
    u'errors': [{
        'text': u'No user with the supplied email address was found.', u'message': u'User not found', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u"Return a user's NSID, given their email address", 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The email address of the user to find  (may be primary or secondary).', u'optional': u'0', u'name': u'find_email'
            }
            ], 'needslogin': False, u'response': u'<user nsid="12037949632@N01">\r\n\t<username>Stewart</username> \r\n</user>', u'name': u'flickr.people.findByEmail'
        }
        , u'flickr.auth.checkToken': {
    u'errors': [{
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.auth.checkToken', u'explanation': u'<p><code>perms</code> can have values of <code>none</code>, <code>read</code>, <code>write</code> or <code>delete</code>. For more information, see the <a href="/services/api/auth.spec.html">Auth API spec</a>.</p>', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The authentication token to check.', u'optional': u'0', u'name': u'auth_token'
            }
            ], 'needslogin': False, u'response': u'<auth>\r\n\t<token>976598454353455</token>\r\n\t<perms>read</perms>\r\n\t<user nsid="12037949754@N01" username="Bees" fullname="Cal H" />\r\n</auth>', u'description': u'Returns the credentials attached to an authentication token. This call <b>must</b> be signed, and is <b><a href="/services/api/auth.oauth.html">deprecated in favour of OAuth</a></b>.'
        }
        , u'flickr.stats.getPhotosetDomains': {
    u'errors': [{
        'text': u'The user you have requested stats has not enabled stats on their account.', u'message': u'User does not have stats', u'code': u'1'
            }
            , {
        'text': u'No stats are available for the date requested. Flickr only keeps stats data for the last 28 days.', u'message': u'No stats for that date', u'code': u'2'
            }
            , {
        'text': u'The date provided could not be parsed', u'message': u'Invalid date', u'code': u'3'
            }
            , {
        'text': u'The photoset id was either invalid or was for a set not owned by the calling user.', u'message': u'Photoset not found', u'code': u'4'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.stats.getPhotosetDomains', u'explanation': u'<p>There is one <code>&lt;domain&gt;</code> element for each referring domain, with attributes for the domain name and the number of views.</p>\r\n\r\n<p>For details on the referrers coming from each domain listed you can call <a href="/services/api/flickr.stats.getPhotosetReferrers.html">flickr.stats.getPhotosetReferrers</a></p>', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'Stats will be returned for this date. This should be in either be in YYYY-MM-DD or unix timestamp format.\r\n\r\nA day according to Flickr Stats starts at midnight GMT for all users, and timestamps will automatically be rounded down to the start of the day.', u'optional': u'0', u'name': u'date'
            }
            , {
        'text': u'The id of the photoset to get stats for. If not provided, stats for all sets will be returned.', u'optional': u'1', u'name': u'photoset_id'
            }
            , {
        'text': u'Number of domains to return per page. If this argument is omitted, it defaults to 25. The maximum allowed value is 100.', u'optional': u'1', u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': u'1', u'name': u'page'
            }
            ], 'needslogin': True, u'response': u'<domains page="1" perpage="25" pages="1" total="3">\r\n\t<domain name="images.search.yahoo.com" views="127" />\r\n\t<domain name="flickr.com" views="122" />\r\n\t<domain name="images.google.com" views="70" />\r\n</domains>\r\n', u'description': u'Get a list of referring domains for a photoset'
        }
        , u'flickr.photos.suggestions.getList': {
    'needssigning': True, u'requiredperms': 'read', u'errors': [{
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'Only show suggestions for a single photo.', u'optional': u'1', u'name': u'photo_id'
            }
            , {
        'text': u'Only show suggestions with a given status.\r\n\r\n<ul>\r\n<li><strong>0</strong>, pending</li>\r\n<li><strong>1</strong>, approved</li>\r\n<li><strong>2</strong>, rejected</li>\r\n</ul>\r\n\r\nThe default is pending (or "0").', u'optional': u'1', u'name': u'status_id'
            }
            ], u'description': u'Return a list of suggestions for a user that are pending approval.', 'needslogin': True, u'name': u'flickr.photos.suggestions.getList'
        }
        , u'flickr.photos.comments.getList': {
    u'errors': [{
        'text': u'The photo id was either invalid or was for a photo not viewable by the calling user.', u'message': u'Photo not found', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Returns the comments for a photo', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photo to fetch comments for.', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u'Minimum date that a a comment was added. The date should be in the form of a unix timestamp.', u'optional': u'1', u'name': u'min_comment_date'
            }
            , {
        'text': u'Maximum date that a comment was added. The date should be in the form of a unix timestamp.', u'optional': u'1', u'name': u'max_comment_date'
            }
            , {
        'text': u'', u'optional': u'1', u'name': u'page'
            }
            , {
        'text': u'', u'optional': u'1', u'name': u'per_page'
            }
            , {
        'text': u'', u'optional': u'1', u'name': u'include_faves'
            }
            ], 'needslogin': False, u'response': u'<comments photo_id="109722179">\r\n        <comment id="6065-109722179-72057594077818641"\r\n         author="35468159852@N01" authorname="Rev Dan Catt" datecreate="1141841470"\r\n         permalink="http://www.flickr.com/photos/straup/109722179/#comment72057594077818641"\r\n         >Umm, I\'m not sure, can I get back to you on that one?</comment>\r\n</comments>', u'name': u'flickr.photos.comments.getList'
        }
        , u'flickr.photosets.orderSets': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'One of the photoset ids passed was not the id of a valid photoset belonging to the calling user.', u'message': u'Set not found', u'code': u'1'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'A comma delimited list of photoset IDs, ordered with the set to show first, first in the list. Any set IDs not given in the list will be set to appear at the end of the list, ordered by their IDs.', u'optional': u'0', u'name': u'photoset_ids'
            }
            ], u'description': u'Set the order of photosets for the calling user.', 'needslogin': True, u'name': u'flickr.photosets.orderSets'
        }
        , u'flickr.photos.search': {
    u'errors': [{
        'text': u"When performing an 'all tags' search, you may not specify more than 20 tags to join together.", u'message': u'Too many tags in ALL query', u'code': u'1'
            }
            , {
        'text': u'A user_id was passed which did not match a valid flickr user.', u'message': u'Unknown user', u'code': u'2'
            }
            , {
        'text': u'To perform a search with no parameters (to get the latest public photos, please use flickr.photos.getRecent instead).', u'message': u'Parameterless searches have been disabled', u'code': u'3'
            }
            , {
        'text': u'The logged in user (if any) does not have permission to view the pool for this group.', u'message': u"You don't have permission to view this pool", u'code': u'4'
            }
            , {
        'text': u'The Flickr API search databases are temporarily unavailable.', u'message': u'Sorry, the Flickr search API is not currently available.', u'code': u'10'
            }
            , {
        'text': u'The query styntax for the machine_tags argument did not validate.', u'message': u'No valid machine tags', u'code': u'11'
            }
            , {
        'text': u'The maximum number of machine tags in a single query was exceeded.', u'message': u'Exceeded maximum allowable machine tags', u'code': u'12'
            }
            , {
        'text': u'jump_to only supported for some query types.', u'message': u'jump_to not avaiable for this query', u'code': u'13'
            }
            , {
        'text': u'jump_to must be valid photo ID.', u'message': u'Bad value for jump_to', u'code': u'14'
            }
            , {
        'text': u'', u'message': u'Photo not found', u'code': u'15'
            }
            , {
        'text': u'', u'message': u'You can only search within your own favorites', u'code': u'16'
            }
            , {
        'text': u'The call tried to use the contacts parameter with no user ID or a user ID other than that of the authenticated user.', u'message': u'You can only search within your own contacts', u'code': u'17'
            }
            , {
        'text': u'The request contained contradictory arguments.', u'message': u'Illogical arguments', u'code': u'18'
            }
            , {
        'text': u'The search requested photos beyond an allowable offset. Reduce the page number or number of results per page for this search.', u'message': u'Excessive photo offset in search', u'code': u'20'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.photos.search', u'explanation': u'Please note that Flickr will return at most the first 4,000 results for any given search query.  If this is an issue, we recommend trying a more specific query.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The NSID of the user who\'s photo to search. If this parameter isn\'t passed then everybody\'s public photos will be searched. A value of "me" will search against the calling user\'s photos for authenticated calls.', u'optional': u'1', u'name': u'user_id'
            }
            , {
        'text': u'A comma-delimited list of tags. Photos with one or more of the tags listed will be returned. You can exclude results that match a term by prepending it with a - character.', u'optional': u'1', u'name': u'tags'
            }
            , {
        'text': u"Either 'any' for an OR combination of tags, or 'all' for an AND combination. Defaults to 'any' if not specified.", u'optional': u'1', u'name': u'tag_mode'
            }
            , {
        'text': u"A free text search. Photos who's title, description or tags contain the text will be returned. You can exclude results that match a term by prepending it with a - character.", u'optional': u'1', u'name': u'text'
            }
            , {
        'text': u'Minimum upload date. Photos with an upload date greater than or equal to this value will be returned. The date can be in the form of a unix timestamp or mysql datetime.', u'optional': u'1', u'name': u'min_upload_date'
            }
            , {
        'text': u'Maximum upload date. Photos with an upload date less than or equal to this value will be returned. The date can be in the form of a unix timestamp or mysql datetime.', u'optional': u'1', u'name': u'max_upload_date'
            }
            , {
        'text': u'Minimum taken date. Photos with an taken date greater than or equal to this value will be returned. The date can be in the form of a mysql datetime or unix timestamp.', u'optional': u'1', u'name': u'min_taken_date'
            }
            , {
        'text': u'Maximum taken date. Photos with an taken date less than or equal to this value will be returned. The date can be in the form of a mysql datetime or unix timestamp.', u'optional': u'1', u'name': u'max_taken_date'
            }
            , {
        'text': u'The license id for photos (for possible values see the flickr.photos.licenses.getInfo method). Multiple licenses may be comma-separated.', u'optional': u'1', u'name': u'license'
            }
            , {
        'text': u'The order in which to sort returned photos. Deafults to date-posted-desc (unless you are doing a radial geo query, in which case the default sorting is by ascending distance from the point specified). The possible values are: date-posted-asc, date-posted-desc, date-taken-asc, date-taken-desc, interestingness-desc, interestingness-asc, and relevance.', u'optional': u'1', u'name': u'sort'
            }
            , {
        'text': u'Return photos only matching a certain privacy level. This only applies when making an authenticated call to view photos you own. Valid values are:\r\n<ul>\r\n<li>1 public photos</li>\r\n<li>2 private photos visible to friends</li>\r\n<li>3 private photos visible to family</li>\r\n<li>4 private photos visible to friends & family</li>\r\n<li>5 completely private photos</li>\r\n</ul>\r\n', u'optional': u'1', u'name': u'privacy_filter'
            }
            , {
        'text': u'A comma-delimited list of 4 values defining the Bounding Box of the area that will be searched.\r\n<br /><br />\r\nThe 4 values represent the bottom-left corner of the box and the top-right corner, minimum_longitude, minimum_latitude, maximum_longitude, maximum_latitude.\r\n<br /><br />\r\nLongitude has a range of -180 to 180 , latitude of -90 to 90. Defaults to -180, -90, 180, 90 if not specified.\r\n<br /><br />\r\nUnlike standard photo queries, geo (or bounding box) queries will only return 250 results per page.\r\n<br /><br />\r\nGeo queries require some sort of limiting agent in order to prevent the database from crying. This is basically like the check against "parameterless searches" for queries without a geo component.\r\n<br /><br />\r\nA tag, for instance, is considered a limiting agent as are user defined min_date_taken and min_date_upload parameters &#8212; If no limiting factor is passed we return only photos added in the last 12 hours (though we may extend the limit in the future).', u'optional': u'1', u'name': u'bbox'
            }
            , {
        'text': u'Recorded accuracy level of the location information.  Current range is 1-16 : \r\n\r\n<ul>\r\n<li>World level is 1</li>\r\n<li>Country is ~3</li>\r\n<li>Region is ~6</li>\r\n<li>City is ~11</li>\r\n<li>Street is ~16</li>\r\n</ul>\r\n\r\nDefaults to maximum value if not specified.', u'optional': u'1', u'name': u'accuracy'
            }
            , {
        'text': u'Safe search setting:\r\n\r\n<ul>\r\n<li>1 for safe.</li>\r\n<li>2 for moderate.</li>\r\n<li>3 for restricted.</li>\r\n</ul>\r\n\r\n(Please note: Un-authed calls can only see Safe content.)', u'optional': u'1', u'name': u'safe_search'
            }
            , {
        'text': u"Content Type setting:\r\n<ul>\r\n<li>1 for photos only.</li>\r\n<li>2 for screenshots only.</li>\r\n<li>3 for 'other' only.</li>\r\n<li>4 for photos and screenshots.</li>\r\n<li>5 for screenshots and 'other'.</li>\r\n<li>6 for photos and 'other'.</li>\r\n<li>7 for photos, screenshots, and 'other' (all).</li>\r\n</ul>", u'optional': u'1', u'name': u'content_type'
            }
            , {
        'text': u'Aside from passing in a fully formed machine tag, there is a special syntax for searching on specific properties :\r\n\r\n<ul>\r\n  <li>Find photos using the \'dc\' namespace :    <code>"machine_tags" => "dc:"</code></li>\r\n\r\n  <li> Find photos with a title in the \'dc\' namespace : <code>"machine_tags" => "dc:title="</code></li>\r\n\r\n  <li>Find photos titled "mr. camera" in the \'dc\' namespace : <code>"machine_tags" => "dc:title=\\"mr. camera\\"</code></li>\r\n\r\n  <li>Find photos whose value is "mr. camera" : <code>"machine_tags" => "*:*=\\"mr. camera\\""</code></li>\r\n\r\n  <li>Find photos that have a title, in any namespace : <code>"machine_tags" => "*:title="</code></li>\r\n\r\n  <li>Find photos that have a title, in any namespace, whose value is "mr. camera" : <code>"machine_tags" => "*:title=\\"mr. camera\\""</code></li>\r\n\r\n  <li>Find photos, in the \'dc\' namespace whose value is "mr. camera" : <code>"machine_tags" => "dc:*=\\"mr. camera\\""</code></li>\r\n\r\n </ul>\r\n\r\nMultiple machine tags may be queried by passing a comma-separated list. The number of machine tags you can pass in a single query depends on the tag mode (AND or OR) that you are querying with. "AND" queries are limited to (16) machine tags. "OR" queries are limited\r\nto (8).', u'optional': u'1', u'name': u'machine_tags'
            }
            , {
        'text': u"Either 'any' for an OR combination of tags, or 'all' for an AND combination. Defaults to 'any' if not specified.", u'optional': u'1', u'name': u'machine_tag_mode'
            }
            , {
        'text': u"The id of a group who's pool to search.  If specified, only matching photos posted to the group's pool will be returned.", u'optional': u'1', u'name': u'group_id'
            }
            , {
        'text': u'boolean. Pass faves=1 along with your user_id to search within your favorites', u'optional': u'1', u'name': u'faves'
            }
            , {
        'text': u'Limit results by camera.  Camera names must be in the <a href="http://www.flickr.com/cameras">Camera Finder</a> normalized form.  <a href="http://flickr.com/services/api/flickr.cameras.getList">flickr.cameras.getList()</a> returns a list of searchable cameras.', u'optional': u'1', u'name': u'camera'
            }
            , {
        'text': u'Jump, jump!', u'optional': u'1', u'name': u'jump_to'
            }
            , {
        'text': u"Search your contacts. Either 'all' or 'ff' for just friends and family. (Experimental)", u'optional': u'1', u'name': u'contacts'
            }
            , {
        'text': u'A 32-bit identifier that uniquely represents spatial entities. (not used if bbox argument is present). \r\n<br /><br />\r\nGeo queries require some sort of limiting agent in order to prevent the database from crying. This is basically like the check against "parameterless searches" for queries without a geo component.\r\n<br /><br />\r\nA tag, for instance, is considered a limiting agent as are user defined min_date_taken and min_date_upload parameters &mdash; If no limiting factor is passed we return only photos added in the last 12 hours (though we may extend the limit in the future).', u'optional': u'1', u'name': u'woe_id'
            }
            , {
        'text': u'A Flickr place id.  (not used if bbox argument is present).\r\n<br /><br />\r\nGeo queries require some sort of limiting agent in order to prevent the database from crying. This is basically like the check against "parameterless searches" for queries without a geo component.\r\n<br /><br />\r\nA tag, for instance, is considered a limiting agent as are user defined min_date_taken and min_date_upload parameters &mdash; If no limiting factor is passed we return only photos added in the last 12 hours (though we may extend the limit in the future).', u'optional': u'1', u'name': u'place_id'
            }
            , {
        'text': u'Filter results by media type. Possible values are <code>all</code> (default), <code>photos</code> or <code>videos</code>', u'optional': u'1', u'name': u'media'
            }
            , {
        'text': u'Any photo that has been geotagged, or if the value is "0" any photo that has <i>not</i> been geotagged.\r\n<br /><br />\r\nGeo queries require some sort of limiting agent in order to prevent the database from crying. This is basically like the check against "parameterless searches" for queries without a geo component.\r\n<br /><br />\r\nA tag, for instance, is considered a limiting agent as are user defined min_date_taken and min_date_upload parameters &mdash; If no limiting factor is passed we return only photos added in the last 12 hours (though we may extend the limit in the future).', u'optional': u'1', u'name': u'has_geo'
            }
            , {
        'text': u'Geo context is a numeric value representing the photo\'s geotagginess beyond latitude and longitude. For example, you may wish to search for photos that were taken "indoors" or "outdoors". <br /><br />\r\nThe current list of context IDs is :<br /><br/>\r\n<ul>\r\n<li><strong>0</strong>, not defined.</li>\r\n<li><strong>1</strong>, indoors.</li>\r\n<li><strong>2</strong>, outdoors.</li>\r\n</ul>\r\n<br /><br />\r\nGeo queries require some sort of limiting agent in order to prevent the database from crying. This is basically like the check against "parameterless searches" for queries without a geo component.\r\n<br /><br />\r\nA tag, for instance, is considered a limiting agent as are user defined min_date_taken and min_date_upload parameters &mdash; If no limiting factor is passed we return only photos added in the last 12 hours (though we may extend the limit in the future).', u'optional': u'1', u'name': u'geo_context'
            }
            , {
        'text': u'A valid latitude, in decimal format, for doing radial geo queries.\r\n<br /><br />\r\nGeo queries require some sort of limiting agent in order to prevent the database from crying. This is basically like the check against "parameterless searches" for queries without a geo component.\r\n<br /><br />\r\nA tag, for instance, is considered a limiting agent as are user defined min_date_taken and min_date_upload parameters &mdash; If no limiting factor is passed we return only photos added in the last 12 hours (though we may extend the limit in the future).', u'optional': u'1', u'name': u'lat'
            }
            , {
        'text': u'A valid longitude, in decimal format, for doing radial geo queries.\r\n<br /><br />\r\nGeo queries require some sort of limiting agent in order to prevent the database from crying. This is basically like the check against "parameterless searches" for queries without a geo component.\r\n<br /><br />\r\nA tag, for instance, is considered a limiting agent as are user defined min_date_taken and min_date_upload parameters &mdash; If no limiting factor is passed we return only photos added in the last 12 hours (though we may extend the limit in the future).', u'optional': u'1', u'name': u'lon'
            }
            , {
        'text': u'A valid radius used for geo queries, greater than zero and less than 20 miles (or 32 kilometers), for use with point-based geo queries. The default value is 5 (km).', u'optional': u'1', u'name': u'radius'
            }
            , {
        'text': u'The unit of measure when doing radial geo queries. Valid options are "mi" (miles) and "km" (kilometers). The default is "km".', u'optional': u'1', u'name': u'radius_units'
            }
            , {
        'text': u'Limit the scope of the search to only photos that are part of the <a href="http://flickr.com/commons">Flickr Commons project</a>. Default is false.', u'optional': u'1', u'name': u'is_commons'
            }
            , {
        'text': u'Limit the scope of the search to only photos that are in a <a href="http://www.flickr.com/help/galleries/">gallery</a>?  Default is false, search all photos.', u'optional': u'1', u'name': u'in_gallery'
            }
            , {
        'text': u'The id of a user.  Will return photos where the user has been people tagged.  A call signed as the person_id in question will return *all* photos the user in, otherwise returns public photos.', u'optional': u'1', u'name': u'person_id'
            }
            , {
        'text': u'Limit the scope of the search to only photos that are for sale on Getty. Default is false.', u'optional': u'1', u'name': u'is_getty'
            }
            , {
        'text': u'A comma-delimited list of extra information to fetch for each returned record. Currently supported fields are: <code>description</code>, <code>license</code>, <code>date_upload</code>, <code>date_taken</code>, <code>owner_name</code>, <code>icon_server</code>, <code>original_format</code>, <code>last_update</code>, <code>geo</code>, <code>tags</code>, <code>machine_tags</code>, <code>o_dims</code>, <code>views</code>, <code>media</code>, <code>path_alias</code>, <code>url_sq</code>, <code>url_t</code>, <code>url_s</code>, <code>url_q</code>, <code>url_m</code>, <code>url_n</code>, <code>url_z</code>, <code>url_c</code>, <code>url_l</code>, <code>url_o</code>', u'optional': 1, u'name': u'extras'
            }
            , {
        'text': u'Number of photos to return per page. If this argument is omitted, it defaults to 100. The maximum allowed value is 500.', u'optional': 1, u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': 1, u'name': u'page'
            }
            ], 'needslogin': False, u'description': u"Return a list of photos matching some criteria. Only photos visible to the calling user will be returned. To return private or semi-private photos, the caller must be authenticated with 'read' permissions, and have permission to view the photos. Unauthenticated calls will only return public photos."
        }
        , u'flickr.stats.getCollectionReferrers': {
    u'errors': [{
        'text': u'The user you have requested stats has not enabled stats on their account.', u'message': u'User does not have stats', u'code': u'1'
            }
            , {
        'text': u'No stats are available for the date requested. Flickr only keeps stats data for the last 28 days.', u'message': u'No stats for that date', u'code': u'2'
            }
            , {
        'text': u'The date provided could not be parsed', u'message': u'Invalid date', u'code': u'3'
            }
            , {
        'text': u'The collection id was either invalid or was for a collection not owned by the calling user.', u'message': u'Collection not found', u'code': u'4'
            }
            , {
        'text': u'The domain provided is not in the expected format.', u'message': u'Invalid domain', u'code': u'5'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.stats.getCollectionReferrers', u'explanation': u'<p>There is one <code>&lt;referrer&gt;</code> element for each referring page, with attributes for the url and the number of views.</p>\r\n\r\n<p>Where the referring page is a search engine and we have identified the search term it will be given in the searchterm attribute.</p>', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'Stats will be returned for this date. This should be in either be in YYYY-MM-DD or unix timestamp format. \r\n\r\nA day according to Flickr Stats starts at midnight GMT for all users, and timestamps will automatically be rounded down to the start of the day.', u'optional': u'0', u'name': u'date'
            }
            , {
        'text': u'The domain to return referrers for. This should be a hostname (eg: "flickr.com") with no protocol or pathname.', u'optional': u'0', u'name': u'domain'
            }
            , {
        'text': u'The id of the collection to get stats for. If not provided, stats for all collections will be returned.', u'optional': u'1', u'name': u'collection_id'
            }
            , {
        'text': u'Number of referrers to return per page. If this argument is omitted, it defaults to 25. The maximum allowed value is 100.', u'optional': u'1', u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': u'1', u'name': u'page'
            }
            ], 'needslogin': True, u'response': u'<domain page="1" perpage="25" pages="1" total="3" name="flickr.com">\r\n\t<referrer url="http://flickr.com/" views="11"/>\r\n\t<referrer url="http://flickr.com/photos/friends/" views="8"/>\r\n\t<referrer url="http://flickr.com/search/?q=stats+api" views="2" searchterm="stats api"/>\r\n</domain>\r\n', u'description': u'Get a list of referrers from a given domain to a collection'
        }
        , u'flickr.groups.getInfo': {
    u'errors': [{
        'text': u"The group NSID passed did not refer to a group that the calling user can see - either an invalid group is or a group that can't be seen by the calling user.", u'message': u'Group not found', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Get information about a group.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The NSID of the group to fetch information for.', u'optional': u'0', u'name': u'group_id'
            }
            , {
        'text': u'The language of the group name and description to fetch.  If the language is not found, the primary language of the group will be returned.\r\n\r\nValid values are the same as <a href="/services/feeds/">in feeds</a>.', u'optional': u'1', u'name': u'lang'
            }
            ], 'needslogin': False, u'response': u'<group id="34427465497@N01" iconserver="1" iconfarm="1" lang="en-us" ispoolmoderated="0">\r\n\t<name>GNEverybody</name>\r\n\t<description>The group for GNE players</description>\r\n\t<members>69</members>\r\n\t<privacy>3</privacy>\r\n\t<throttle count="10" mode="month" remaining="3"/>\r\n        <restrictions photos_ok="1" videos_ok="1" images_ok="1" screens_ok="1" art_ok="1" safe_ok="1" moderate_ok="0" restricted_ok="0" has_geo="0" />\r\n</group>', u'name': u'flickr.groups.getInfo'
        }
        , u'flickr.machinetags.getPredicates': {
    u'errors': [{
        'text': u'Missing or invalid namespace argument.', u'message': u'Not a valid namespace', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Return a list of unique predicates, optionally limited by a given namespace.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'Limit the list of predicates returned to those that have the following namespace.', u'optional': u'1', u'name': u'namespace'
            }
            , {
        'text': u'Number of photos to return per page. If this argument is omitted, it defaults to 100. The maximum allowed value is 500.', u'optional': u'1', u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': u'1', u'name': u'page'
            }
            ], 'needslogin': False, u'response': u'<predicates page="1" pages="1" total="3" perpage="500">\r\n    <predicate usage="20" namespaces="1">elbow</predicate>\r\n    <predicate usage="52" namespaces="2">face</predicate>\r\n    <predicate usage="10" namespaces="1">hand</predicate>\r\n</predicates>\r\n', u'name': u'flickr.machinetags.getPredicates'
        }
        , u'flickr.photos.getCounts': {
    u'errors': [{
        'text': u'Neither dates nor taken_dates were specified.', u'message': u'No dates specified', u'code': u'1'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Gets a list of photo counts for the given date ranges for the calling user.', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'A comma delimited list of unix timestamps, denoting the periods to return counts for. They should be specified <b>smallest first</b>.', u'optional': u'1', u'name': u'dates'
            }
            , {
        'text': u'A comma delimited list of mysql datetimes, denoting the periods to return counts for. They should be specified <b>smallest first</b>.', u'optional': u'1', u'name': u'taken_dates'
            }
            ], 'needslogin': True, u'response': u'<photocounts>\r\n\t<photocount count="4" fromdate="1093566950" todate="1093653350" /> \r\n\t<photocount count="0" fromdate="1093653350" todate="1093739750" /> \r\n\t<photocount count="0" fromdate="1093739750" todate="1093826150" /> \r\n\t<photocount count="2" fromdate="1093826150" todate="1093912550" /> \r\n\t<photocount count="0" fromdate="1093912550" todate="1093998950" /> \r\n\t<photocount count="0" fromdate="1093998950" todate="1094085350" /> \r\n\t<photocount count="0" fromdate="1094085350" todate="1094171750" /> \r\n</photocounts>\r\n', u'name': u'flickr.photos.getCounts'
        }
        , u'flickr.photos.transform.rotate': {
    u'errors': [{
        'text': u'The photo id was invalid or did not belong to the calling user.', u'message': u'Photo not found', u'code': u'1'
            }
            , {
        'text': u'The rotation degrees were an invalid value.', u'message': u'Invalid rotation', u'code': u'2'
            }
            , {
        'text': u'There was a problem either rotating the image or storing the rotated versions.', u'message': u'Temporary failure', u'code': u'3'
            }
            , {
        'text': u'The rotation service is currently disabled.', u'message': u'Rotation disabled', u'code': u'4'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Rotate a photo.', 'needssigning': True, u'requiredperms': 'write', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photo to rotate.', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u"The amount of degrees by which to rotate the photo (clockwise) from it's current orientation. Valid values are 90, 180 and 270.", u'optional': u'0', u'name': u'degrees'
            }
            ], 'needslogin': True, u'response': u'<photoid secret="abcdef" originalsecret="abcdef">1234</photoid>', u'name': u'flickr.photos.transform.rotate'
        }
        , u'flickr.photos.delete': {
    'needssigning': True, u'requiredperms': 'delete', u'errors': [{
        'text': u'The photo id was not the id of a photo belonging to the calling user.', u'message': u'Photo not found', u'code': u'1'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photo to delete.', u'optional': u'0', u'name': u'photo_id'
            }
            ], u'description': u'Delete a photo from flickr.', 'needslogin': True, u'name': u'flickr.photos.delete'
        }
        , u'flickr.photos.setTags': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The photo id passed was not the id of a photo belonging to the calling user. It might be an invalid id, or the photo might be owned by another user. ', u'message': u'Photo not found', u'code': u'1'
            }
            , {
        'text': u'The number of tags specified exceeds the limit for the photo. No tags were modified.', u'message': u'Maximum number of tags reached', u'code': u'2'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photo to set tags for.\r\n', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u'All tags for the photo (as a single space-delimited string).', u'optional': u'0', u'name': u'tags'
            }
            ], u'description': u'Set the tags for a photo.', 'needslogin': True, u'name': u'flickr.photos.setTags'
        }
        , u'flickr.photos.addTags': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The photo id passed was not the id of a photo that the calling user can add tags to. It could be an invalid id, or the user may not have permission to add tags to it.', u'message': u'Photo not found', u'code': u'1'
            }
            , {
        'text': u'The maximum number of tags for the photo has been reached - no more tags can be added. If the current count is less than the maximum, but adding all of the tags for this request would go over the limit, the whole request is ignored. I.E. when you get this message, none of the requested tags have been added.', u'message': u'Maximum number of tags reached', u'code': u'2'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photo to add tags to.', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u'The tags to add to the photo.', u'optional': u'0', u'name': u'tags'
            }
            ], u'description': u'Add tags to a photo.', 'needslogin': True, u'name': u'flickr.photos.addTags'
        }
        , u'flickr.stats.getPhotosetReferrers': {
    u'errors': [{
        'text': u'The user you have requested stats has not enabled stats on their account.', u'message': u'User does not have stats', u'code': u'1'
            }
            , {
        'text': u'No stats are available for the date requested. Flickr only keeps stats data for the last 28 days.', u'message': u'No stats for that date', u'code': u'2'
            }
            , {
        'text': u'The date provided could not be parsed', u'message': u'Invalid date', u'code': u'3'
            }
            , {
        'text': u'The photoset id was either invalid or was for a set not owned by the calling user.', u'message': u'Photoset not found', u'code': u'4'
            }
            , {
        'text': u'The domain provided is not in the expected format.', u'message': u'Invalid domain', u'code': u'5'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.stats.getPhotosetReferrers', u'explanation': u'<p>There is one <code>&lt;referrer&gt;</code> element for each referring page, with attributes for the url and the number of views.</p>\r\n\r\n<p>Where the referring page is a search engine and we have identified the search term it will be given in the searchterm attribute.</p>', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'Stats will be returned for this date. This should be in either be in YYYY-MM-DD or unix timestamp format. \r\n\r\nA day according to Flickr Stats starts at midnight GMT for all users, and timestamps will automatically be rounded down to the start of the day.', u'optional': u'0', u'name': u'date'
            }
            , {
        'text': u'The domain to return referrers for. This should be a hostname (eg: "flickr.com") with no protocol or pathname.', u'optional': u'0', u'name': u'domain'
            }
            , {
        'text': u'The id of the photoset to get stats for. If not provided, stats for all sets will be returned.', u'optional': u'1', u'name': u'photoset_id'
            }
            , {
        'text': u'Number of referrers to return per page. If this argument is omitted, it defaults to 25. The maximum allowed value is 100.', u'optional': u'1', u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': u'1', u'name': u'page'
            }
            ], 'needslogin': True, u'response': u'<domain page="1" perpage="25" pages="1" total="3" name="flickr.com">\r\n\t<referrer url="http://flickr.com/" views="11"/>\r\n\t<referrer url="http://flickr.com/photos/friends/" views="8"/>\r\n\t<referrer url="http://flickr.com/search/?q=stats+api" views="2" searchterm="stats api"/>\r\n</domain>', u'description': u'Get a list of referrers from a given domain to a photoset'
        }
        , u'flickr.places.getShapeHistory': {
    u'errors': [{
        'text': u'One or more required parameter is missing from the API call.', u'message': u'Required parameter missing', u'code': u'1'
            }
            , {
        'text': u'An invalid Places (or WOE) ID was passed with the API call.', u'message': u'Not a valid Places ID', u'code': u'2'
            }
            , {
        'text': u'No place could be found for the Places (or WOE) ID passed to the API call.', u'message': u'Place not found', u'code': u'3'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Return an historical list of all the shape data generated for a Places or Where on Earth (WOE) ID.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'A Flickr Places ID. <span style="font-style:italic;">(While optional, you must pass either a valid Places ID or a WOE ID.)</span>', u'optional': u'1', u'name': u'place_id'
            }
            , {
        'text': u'A Where On Earth (WOE) ID. <span style="font-style:italic;">(While optional, you must pass either a valid Places ID or a WOE ID.)</span>', u'optional': u'1', u'name': u'woe_id'
            }
            ], 'needslogin': False, u'response': u'<shapes total="2" woe_id="3534" place_id="4hLQygSaBJ92" place_type="locality" place_type_id="7">\r\n   <shapedata created="1223513357" alpha="0.012359619140625"\r\n      count_points="34778" count_edges="52" is_donuthole="0">\r\n      <polylines>\r\n         <polyline>\r\n            45.427627563477,-73.589645385742 45.428966522217,-73.587898254395, etc...\r\n         </polyline>\r\n      </polylines>\r\n      <urls>\r\n         <shapefile>\r\n         http://farm4.static.flickr.com/3228/shapefiles/3534_20081111_0a8afe03c5.tar.gz\r\n         </shapefile>\r\n      </urls>\r\n   </shapedata>\r\n   <!-- and so on... -->\r\n</shapes>', u'name': u'flickr.places.getShapeHistory'
        }
        , u'flickr.places.placesForContacts': {
    u'errors': [{
        'text': u'Places for contacts have been disabled or are otherwise not available.', u'message': u'Places for contacts are not available at this time', u'code': u'1'
            }
            , {
        'text': u'One or more of the required parameters was not included with your request.', u'message': u'Required parameter missing', u'code': u'2'
            }
            , {
        'text': u'An invalid place type was included with your request.', u'message': u'Not a valid place type.', u'code': u'3'
            }
            , {
        'text': u'An invalid Places (or WOE) identifier was included with your request.', u'message': u'Not a valid Place ID', u'code': u'4'
            }
            , {
        'text': u'The threshold passed was invalid. ', u'message': u'Not a valid threshold', u'code': u'5'
            }
            , {
        'text': u'Contacts must be either "all" or "ff" (friends and family).', u'message': u'Not a valid contacts type', u'code': u'6'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u"Return a list of the top 100 unique places clustered by a given placetype for a user's contacts. ", 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'A specific place type to cluster photos by. <br /><br />\r\n\r\nValid place types are :\r\n\r\n<ul>\r\n<li><strong>neighbourhood</strong> (and neighborhood)</li>\r\n<li><strong>locality</strong></li>\r\n<li><strong>region</strong></li>\r\n<li><strong>country</strong></li>\r\n<li><strong>continent</strong></li>\r\n</ul>\r\n<br />\r\n<span style="font-style:italic;">The "place_type" argument has been deprecated in favor of the "place_type_id" argument. It won\'t go away but it will not be added to new methods. A complete list of place type IDs is available using the <a href="http://www.flickr.com/services/api/flickr.places.getPlaceTypes.html">flickr.places.getPlaceTypes</a> method. (While optional, you must pass either a valid place type or place type ID.)</span>', u'optional': u'1', u'name': u'place_type'
            }
            , {
        'text': u'The numeric ID for a specific place type to cluster photos by. <br /><br />\r\n\r\nValid place type IDs are :\r\n\r\n<ul>\r\n<li><strong>22</strong>: neighbourhood</li>\r\n<li><strong>7</strong>: locality</li>\r\n<li><strong>8</strong>: region</li>\r\n<li><strong>12</strong>: country</li>\r\n<li><strong>29</strong>: continent</li>\r\n</ul>\r\n<br /><span style="font-style:italic;">(While optional, you must pass either a valid place type or place type ID.)</span>', u'optional': u'1', u'name': u'place_type_id'
            }
            , {
        'text': u'A Where on Earth identifier to use to filter photo clusters. For example all the photos clustered by <strong>locality</strong> in the United States (WOE ID <strong>23424977</strong>).<br /><br />\r\n<span style="font-style:italic;">(While optional, you must pass either a valid Places ID or a WOE ID.)</span>', u'optional': u'1', u'name': u'woe_id'
            }
            , {
        'text': u'A Flickr Places identifier to use to filter photo clusters. For example all the photos clustered by <strong>locality</strong> in the United States (Place ID <strong>4KO02SibApitvSBieQ</strong>).\r\n<br /><br />\r\n<span style="font-style:italic;">(While optional, you must pass either a valid Places ID or a WOE ID.)</span>', u'optional': u'1', u'name': u'place_id'
            }
            , {
        'text': u'The minimum number of photos that a place type must have to be included. If the number of photos is lowered then the parent place type for that place will be used.<br /><br />\r\n\r\nFor example if your contacts only have <strong>3</strong> photos taken in the locality of Montreal</strong> (WOE ID 3534) but your threshold is set to <strong>5</strong> then those photos will be "rolled up" and included instead with a place record for the region of Quebec (WOE ID 2344924).', u'optional': u'1', u'name': u'threshold'
            }
            , {
        'text': u"Search your contacts. Either 'all' or 'ff' for just friends and family. (Default is all)", u'optional': u'1', u'name': u'contacts'
            }
            , {
        'text': u'Minimum upload date. Photos with an upload date greater than or equal to this value will be returned. The date should be in the form of a unix timestamp.', u'optional': u'1', u'name': u'min_upload_date'
            }
            , {
        'text': u'Maximum upload date. Photos with an upload date less than or equal to this value will be returned. The date should be in the form of a unix timestamp.', u'optional': u'1', u'name': u'max_upload_date'
            }
            , {
        'text': u'Minimum taken date. Photos with an taken date greater than or equal to this value will be returned. The date should be in the form of a mysql datetime.', u'optional': u'1', u'name': u'min_taken_date'
            }
            , {
        'text': u'Maximum taken date. Photos with an taken date less than or equal to this value will be returned. The date should be in the form of a mysql datetime.', u'optional': u'1', u'name': u'max_taken_date'
            }
            ], 'needslogin': True, u'response': u'<places total="1">\r\n   <place place_id="kH8dLOubBZRvX_YZ" woeid="2487956"\r\n               latitude="37.779" longitude="-122.420"\r\n               place_url="/United+States/California/San+Francisco"\r\n               place_type="locality"\r\n               photo_count="156">San Francisco, California</place>\r\n</places>', u'name': u'flickr.places.placesForContacts'
        }
        , u'flickr.photos.licenses.setLicense': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The specified id was not the id of a valif photo owner by the calling user.', u'message': u'Photo not found', u'code': u'1'
            }
            , {
        'text': u'The license id was not valid.', u'message': u'License not found', u'code': u'2'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The photo to update the license for.', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u'The license to apply, or 0 (zero) to remove the current license. Note : as of this writing the "no known copyright restrictions" license (7) is not a valid argument.', u'optional': u'0', u'name': u'license_id'
            }
            ], u'description': u'Sets the license for a photo.', 'needslogin': True, u'name': u'flickr.photos.licenses.setLicense'
        }
        , u'flickr.groups.discuss.topics.getInfo': {
    u'errors': [{
        'text': u'The topic_id is invalid', u'message': u'Topic not found', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Get information about a group discussion topic.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The ID for the topic to edit.', u'optional': u'0', u'name': u'topic_id'
            }
            ], 'needslogin': False, u'response': u'<?xml version="1.0" encoding="utf-8" ?>\r\n<rsp stat="ok">\r\n  <topic id="72157607082559966" subject="Who\'s still around?" author="30134652@N05" authorname="JAMAL\'S ACCOUNT" is_pro="0" role="admin" iconserver="0" iconfarm="0" count_replies="1" can_edit="1" can_delete="0" can_reply="0" is_sticky="0" is_locked="0" datecreate="1337975869" datelastpost="1337975921" last_reply="72157607082559968">\r\n    <message>Is anyone still around in this group?</message>\r\n  </topic>\r\n</rsp>', u'name': u'flickr.groups.discuss.topics.getInfo'
        }
        , u'flickr.photosets.editPhotos': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The photoset id passed was not a valid photoset id or did not belong to the calling user.', u'message': u'Photoset not found', u'code': u'1'
            }
            , {
        'text': u'One or more of the photo ids passed was not a valid photo id or does not belong to the calling user.', u'message': u'Photo not found', u'code': u'2'
            }
            , {
        'text': u'The primary photo id passed was not a valid photo id or does not belong to the calling user.', u'message': u'Primary photo not found', u'code': u'3'
            }
            , {
        'text': u'The primary photo id passed did not appear in the photo id list.', u'message': u'Primary photo not in list', u'code': u'4'
            }
            , {
        'text': u'No photo ids were passed.', u'message': u'Empty photos list', u'code': u'5'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photoset to modify. The photoset must belong to the calling user.', u'optional': u'0', u'name': u'photoset_id'
            }
            , {
        'text': u"The id of the photo to use as the 'primary' photo for the set. This id must also be passed along in photo_ids list argument.", u'optional': u'0', u'name': u'primary_photo_id'
            }
            , {
        'text': u'A comma-delimited list of photo ids to include in the set. They will appear in the set in the order sent. This list <b>must</b> contain the primary photo id. All photos must belong to the owner of the set. This list of photos replaces the existing list. Call flickr.photosets.addPhoto to append a photo to a set.', u'optional': u'0', u'name': u'photo_ids'
            }
            ], u'description': u'Modify the photos in a photoset. Use this method to add, remove and re-order photos.', 'needslogin': True, u'name': u'flickr.photosets.editPhotos'
        }
        , u'flickr.photos.geo.setContext': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The photo id was either invalid or was for a photo not viewable by the calling user.', u'message': u'Photo not found', u'code': u'1'
            }
            , {
        'text': u'The context ID passed to the method is invalid.', u'message': u'Not a valid context', u'code': u'2'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photo to set context data for.', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u'Context is a numeric value representing the photo\'s geotagginess beyond latitude and longitude. For example, you may wish to indicate that a photo was taken "indoors" or "outdoors". <br /><br />\r\nThe current list of context IDs is :<br /><br/>\r\n<ul>\r\n<li><strong>0</strong>, not defined.</li>\r\n<li><strong>1</strong>, indoors.</li>\r\n<li><strong>2</strong>, outdoors.</li>\r\n</ul>', u'optional': u'0', u'name': u'context'
            }
            ], u'description': u"Indicate the state of a photo's geotagginess beyond latitude and longitude.<br /><br />\r\nNote : photos passed to this method must already be geotagged (using the <q>flickr.photos.geo.setLocation</q> method).", 'needslogin': True, u'name': u'flickr.photos.geo.setContext'
        }
        , u'flickr.places.findByLatLon': {
    u'errors': [{
        'text': u'One or more required parameters was not included with the API request.', u'message': u'Required arguments missing', u'code': u'1'
            }
            , {
        'text': u'The latitude argument failed validation.', u'message': u'Not a valid latitude', u'code': u'2'
            }
            , {
        'text': u'The longitude argument failed validation.', u'message': u'Not a valid longitude', u'code': u'3'
            }
            , {
        'text': u'The accuracy argument failed validation.', u'message': u'Not a valid accuracy', u'code': u'4'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Return a place ID for a latitude, longitude and accuracy triple.<br /><br />\r\nThe flickr.places.findByLatLon method is not meant to be a (reverse) geocoder in the traditional sense. It is designed to allow users to find photos for "places" and will round up to the nearest place type to which corresponding place IDs apply.<br /><br />\r\nFor example, if you pass it a street level coordinate it will return the city that contains the point rather than the street, or building, itself.<br /><br />\r\nIt will also truncate latitudes and longitudes to three decimal points.\r\n\r\n', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The latitude whose valid range is -90 to 90. Anything more than 4 decimal places will be truncated.', u'optional': u'0', u'name': u'lat'
            }
            , {
        'text': u'The longitude whose valid range is -180 to 180. Anything more than 4 decimal places will be truncated.', u'optional': u'0', u'name': u'lon'
            }
            , {
        'text': u'Recorded accuracy level of the location information. World level is 1, Country is ~3, Region ~6, City ~11, Street ~16. Current range is 1-16. The default is 16.', u'optional': u'1', u'name': u'accuracy'
            }
            ], 'needslogin': False, u'response': u'<places latitude="37.76513627957266" longitude="-122.42020770907402" accuracy="16" total="1">\r\n   <place place_id="Y12JWsKbApmnSQpbQg" woeid="23512048"\r\n      latitude="37.765" longitude="-122.424" \r\n      place_url="/United+States/California/San+Francisco/Mission+Dolores"\r\n      place_type="neighbourhood" place_type_id="22" \r\n      timezone="America/Los_Angeles"\r\n      name="Mission Dolores, San Francisco, CA, US, United States"/>\r\n</places>', u'name': u'flickr.places.findByLatLon'
        }
        , u'flickr.photosets.removePhoto': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The photoset id passed was not the id of avalid photoset owned by the calling user.', u'message': u'Photoset not found', u'code': u'1'
            }
            , {
        'text': u'The photo id passed was not the id of a valid photo belonging to the calling user.', u'message': u'Photo not found', u'code': u'2'
            }
            , {
        'text': u'The photo is not a member of the photoset.', u'message': u'Photo not in set', u'code': u'3'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photoset to remove a photo from.', u'optional': u'0', u'name': u'photoset_id'
            }
            , {
        'text': u'The id of the photo to remove from the set.', u'optional': u'0', u'name': u'photo_id'
            }
            ], u'description': u'Remove a photo from a photoset.', 'needslogin': True, u'name': u'flickr.photosets.removePhoto'
        }
        , u'flickr.cameras.getBrands': {
    u'errors': [{
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Returns all the brands of cameras that Flickr knows about.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            ], 'needslogin': False, u'response': u'<rsp stat="ok">\r\n<brands>\r\n\t<brand id="canon">Canon</brand>\r\n\t<brand id="nikon">Nikon</brand>\r\n        <brand id="apple">Apple</brand>\r\n</brands>\r\n</rsp>', u'name': u'flickr.cameras.getBrands'
        }
        , u'flickr.photos.getWithoutGeoData': {
    'needssigning': True, u'requiredperms': 'read', u'errors': [{
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'Maximum upload date. Photos with an upload date less than or equal to this value will be returned. The date should be in the form of a unix timestamp.', u'optional': u'1', u'name': u'max_upload_date'
            }
            , {
        'text': u'Minimum taken date. Photos with an taken date greater than or equal to this value will be returned. The date can be in the form of a mysql datetime or unix timestamp.', u'optional': u'1', u'name': u'min_taken_date'
            }
            , {
        'text': u'Maximum taken date. Photos with an taken date less than or equal to this value will be returned. The date can be in the form of a mysql datetime or unix timestamp.', u'optional': u'1', u'name': u'max_taken_date'
            }
            , {
        'text': u'Return photos only matching a certain privacy level. Valid values are:\r\n<ul>\r\n<li>1 public photos</li>\r\n<li>2 private photos visible to friends</li>\r\n<li>3 private photos visible to family</li>\r\n<li>4 private photos visible to friends &amp; family</li>\r\n<li>5 completely private photos</li>\r\n</ul>\r\n', u'optional': u'1', u'name': u'privacy_filter'
            }
            , {
        'text': u'The order in which to sort returned photos. Deafults to date-posted-desc. The possible values are: date-posted-asc, date-posted-desc, date-taken-asc, date-taken-desc, interestingness-desc, and interestingness-asc.', u'optional': u'1', u'name': u'sort'
            }
            , {
        'text': u'Filter results by media type. Possible values are <code>all</code> (default), <code>photos</code> or <code>videos</code>', u'optional': u'1', u'name': u'media'
            }
            , {
        'text': u'Minimum upload date. Photos with an upload date greater than or equal to this value will be returned. The date can be in the form of a unix timestamp or mysql datetime.', u'optional': u'1', u'name': u'min_upload_date'
            }
            , {
        'text': u'A comma-delimited list of extra information to fetch for each returned record. Currently supported fields are: <code>description</code>, <code>license</code>, <code>date_upload</code>, <code>date_taken</code>, <code>owner_name</code>, <code>icon_server</code>, <code>original_format</code>, <code>last_update</code>, <code>geo</code>, <code>tags</code>, <code>machine_tags</code>, <code>o_dims</code>, <code>views</code>, <code>media</code>, <code>path_alias</code>, <code>url_sq</code>, <code>url_t</code>, <code>url_s</code>, <code>url_q</code>, <code>url_m</code>, <code>url_n</code>, <code>url_z</code>, <code>url_c</code>, <code>url_l</code>, <code>url_o</code>', u'optional': 1, u'name': u'extras'
            }
            , {
        'text': u'Number of photos to return per page. If this argument is omitted, it defaults to 100. The maximum allowed value is 500.', u'optional': 1, u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': 1, u'name': u'page'
            }
            ], u'description': u"Returns a list of your photos which haven't been geo-tagged.", 'needslogin': True, u'name': u'flickr.photos.getWithoutGeoData'
        }
        , u'flickr.stats.getTotalViews': {
    u'errors': [{
        'text': u'The user you have requested stats has not enabled stats on their account.', u'message': u'User does not have stats', u'code': u'1'
            }
            , {
        'text': u'No stats are available for the date requested. Flickr only keeps stats data for the last 28 days.', u'message': u'No stats for that date', u'code': u'2'
            }
            , {
        'text': u'The date provided could not be parsed', u'message': u'Invalid date', u'code': u'3'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Get the overall view counts for an account', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'Stats will be returned for this date. This should be in either be in YYYY-MM-DD or unix timestamp format.\r\n\r\nA day according to Flickr Stats starts at midnight GMT for all users, and timestamps will automatically be rounded down to the start of the day.\r\n\r\nIf no date is provided, all time view counts will be returned.', u'optional': u'1', u'name': u'date'
            }
            ], 'needslogin': True, u'response': u'<stats>\r\n\t<total views="469" />\r\n\t<photos views="386" />\r\n\t<photostream views="72" />\r\n\t<sets views="11" />\r\n\t<collections views="0" />\r\n</stats>', u'name': u'flickr.stats.getTotalViews'
        }
        , u'flickr.photos.getNotInSet': {
    'needssigning': True, u'requiredperms': 'read', u'errors': [{
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'Maximum upload date. Photos with an upload date less than or equal to this value will be returned. The date can be in the form of a unix timestamp or mysql datetime.', u'optional': u'1', u'name': u'max_upload_date'
            }
            , {
        'text': u'Minimum taken date. Photos with an taken date greater than or equal to this value will be returned. The date can be in the form of a mysql datetime or unix timestamp.', u'optional': u'1', u'name': u'min_taken_date'
            }
            , {
        'text': u'Maximum taken date. Photos with an taken date less than or equal to this value will be returned. The date can be in the form of a mysql datetime or unix timestamp.', u'optional': u'1', u'name': u'max_taken_date'
            }
            , {
        'text': u'Return photos only matching a certain privacy level. Valid values are:\r\n<ul>\r\n<li>1 public photos</li>\r\n<li>2 private photos visible to friends</li>\r\n<li>3 private photos visible to family</li>\r\n<li>4 private photos visible to friends &amp; family</li>\r\n<li>5 completely private photos</li>\r\n</ul>\r\n', u'optional': u'1', u'name': u'privacy_filter'
            }
            , {
        'text': u'Filter results by media type. Possible values are <code>all</code> (default), <code>photos</code> or <code>videos</code>', u'optional': u'1', u'name': u'media'
            }
            , {
        'text': u'Minimum upload date. Photos with an upload date greater than or equal to this value will be returned. The date can be in the form of a unix timestamp or mysql datetime.', u'optional': u'1', u'name': u'min_upload_date'
            }
            , {
        'text': u'A comma-delimited list of extra information to fetch for each returned record. Currently supported fields are: <code>description</code>, <code>license</code>, <code>date_upload</code>, <code>date_taken</code>, <code>owner_name</code>, <code>icon_server</code>, <code>original_format</code>, <code>last_update</code>, <code>geo</code>, <code>tags</code>, <code>machine_tags</code>, <code>o_dims</code>, <code>views</code>, <code>media</code>, <code>path_alias</code>, <code>url_sq</code>, <code>url_t</code>, <code>url_s</code>, <code>url_q</code>, <code>url_m</code>, <code>url_n</code>, <code>url_z</code>, <code>url_c</code>, <code>url_l</code>, <code>url_o</code>', u'optional': 1, u'name': u'extras'
            }
            , {
        'text': u'Number of photos to return per page. If this argument is omitted, it defaults to 100. The maximum allowed value is 500.', u'optional': 1, u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': 1, u'name': u'page'
            }
            ], u'description': u'Returns a list of your photos that are not part of any sets.', 'needslogin': True, u'name': u'flickr.photos.getNotInSet'
        }
        , u'flickr.groups.discuss.replies.getList': {
    u'errors': [{
        'text': u'The topic_id is invalid.', u'message': u'Topic not found', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Get a list of replies from a group discussion topic.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The ID of the topic to fetch replies for.', u'optional': u'0', u'name': u'topic_id'
            }
            , {
        'text': u'Number of photos to return per page. If this argument is omitted, it defaults to 100. The maximum allowed value is 500.', u'optional': u'0', u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': u'1', u'name': u'page'
            }
            ], 'needslogin': False, u'response': u'<rsp stat="ok">\r\n  <replies>\r\n    <topic topic_id="72157625038324579" subject="A long time ago in a galaxy far, far away..." group_id="46744914@N00" iconserver="1" iconfarm="1" name="Tell a story in 5 frames (Visual story telling)" author="53930889@N04" authorname="Smallportfolio_jm08" role="member" author_iconserver="5169" author_iconfarm="6" can_edit="0" can_delete="0" can_reply="0" is_sticky="0" is_locked="" datecreate="1287070965" datelastpost="1336905518" total="8" page="1" per_page="3" pages="2">\r\n      <message>&lt;div&gt;&lt;span class=&quot;photo_container pc_m bbml_img&quot;&gt;&lt;a href=&quot;/photos/53930889@N04/5080874079/&quot; title=&quot;Star Wars 1 by Smallportfolio_jm08&quot;&gt;&lt;img class=&quot;notsowide&quot; src=&quot;http://farm5.staticflickr.com/4035/5080874079_684cf874e0_m.jpg&quot; width=&quot;240&quot; height=&quot;180&quot; alt=&quot;Star Wars 1 by Smallportfolio_jm08&quot;  class=&quot;pc_img&quot; border=&quot;0&quot; /&gt;&lt;/a&gt;&lt;/span&gt;&lt;/div&gt;\r\n\r\n&lt;div&gt;&lt;span class=&quot;photo_container pc_m bbml_img&quot;&gt;&lt;a href=&quot;/photos/53930889@N04/5081467846/&quot; title=&quot;Star Wars 2 by Smallportfolio_jm08&quot;&gt;&lt;img class=&quot;notsowide&quot; src=&quot;http://farm5.staticflickr.com/4071/5081467846_2eec86176d_m.jpg&quot; width=&quot;240&quot; height=&quot;180&quot; alt=&quot;Star Wars 2 by Smallportfolio_jm08&quot;  class=&quot;pc_img&quot; border=&quot;0&quot; /&gt;&lt;/a&gt;&lt;/span&gt;&lt;/div&gt;\r\n\r\n&lt;div&gt;&lt;span class=&quot;photo_container pc_m bbml_img&quot;&gt;&lt;a href=&quot;/photos/53930889@N04/5081467886/&quot; title=&quot;Star Wars 3 by Smallportfolio_jm08&quot;&gt;&lt;img class=&quot;notsowide&quot; src=&quot;http://farm5.staticflickr.com/4021/5081467886_d8cca6c8e8_m.jpg&quot; width=&quot;240&quot; height=&quot;180&quot; alt=&quot;Star Wars 3 by Smallportfolio_jm08&quot;  class=&quot;pc_img&quot; border=&quot;0&quot; /&gt;&lt;/a&gt;&lt;/span&gt;&lt;/div&gt;\r\n\r\n&lt;div&gt;&lt;span class=&quot;photo_container pc_m bbml_img&quot;&gt;&lt;a href=&quot;/photos/53930889@N04/5081467910/&quot; title=&quot;Star Wars 4 by Smallportfolio_jm08&quot;&gt;&lt;img class=&quot;notsowide&quot; src=&quot;http://farm5.staticflickr.com/4084/5081467910_274bb11fdc_m.jpg&quot; width=&quot;240&quot; height=&quot;180&quot; alt=&quot;Star Wars 4 by Smallportfolio_jm08&quot;  class=&quot;pc_img&quot; border=&quot;0&quot; /&gt;&lt;/a&gt;&lt;/span&gt;&lt;/div&gt;\r\n\r\n&lt;div&gt;&lt;span class=&quot;photo_container pc_m bbml_img&quot;&gt;&lt;a href=&quot;/photos/53930889@N04/5081467948/&quot; title=&quot;Star Wars 5 by Smallportfolio_jm08&quot;&gt;&lt;img class=&quot;notsowide&quot; src=&quot;http://farm5.staticflickr.com/4154/5081467948_1a5f200bc0_m.jpg&quot; width=&quot;240&quot; height=&quot;180&quot; alt=&quot;Star Wars 5 by Smallportfolio_jm08&quot;  class=&quot;pc_img&quot; border=&quot;0&quot; /&gt;&lt;/a&gt;&lt;/span&gt;&lt;/div&gt;</message>\r\n    </topic>\r\n    <reply id="72157625163054214" author="41380738@N05" authorname="BlueRidgeKitties" role="member" iconserver="2459" iconfarm="3" can_edit="0" can_delete="0" datecreate="1287071539" lastedit="0">\r\n      <message>*LOL* The universe is full of &lt;a href=&quot;http://www.flickr.com/groups/visualstory/discuss/72157622533160886/&quot;&gt;giant furry space monsters&lt;/a&gt; it seems! Love it.</message>\r\n    </reply>\r\n    <reply id="72157625163539300" author="52101018@N00" authorname="pterandon" role="admin" iconserver="1" iconfarm="1" can_edit="0" can_delete="0" datecreate="1287076748" lastedit="0">\r\n      <message>Great work. Good focus on different aspects of scene in each frame.  Funny ending-- even better that I didn\'t notice the cat right away!  Being a hopeless Trekkie, I was wondering why Han was doing the Vulcan death grip on one of his allies....</message>\r\n    </reply>\r\n    <reply id="72157625040116805" author="54830408@N02" authorname="tay.grisham" role="member" iconserver="0" iconfarm="0" can_edit="0" can_delete="0" datecreate="1287089858" lastedit="0">\r\n      <message>On a scale of 1 to 10 of awesome. This is a 15</message>\r\n    </reply>\r\n  </replies>\r\n</rsp>', u'name': u'flickr.groups.discuss.replies.getList'
        }
        , u'flickr.photos.getFavorites': {
    u'errors': [{
        'text': u'The specified photo does not exist, or the calling user does not have permission to view it.', u'message': u'Photo not found', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Returns the list of people who have favorited a given photo.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The ID of the photo to fetch the favoriters list for.', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': u'1', u'name': u'page'
            }
            , {
        'text': u'Number of usres to return per page. If this argument is omitted, it defaults to 10. The maximum allowed value is 50.', u'optional': u'1', u'name': u'per_page'
            }
            ], 'needslogin': False, u'response': u'<photo id="1253576" secret="81b96be690" server="1" farm="1"\r\n\tpage="1" pages="3" perpage="10" total="27">\r\n\t<person nsid="33939862@N00" username="Dementation" favedate="1166689690"/>\r\n\t<person nsid="49485425@N00" username="indigenous_prodigy" favedate="1166573724"/>\r\n\t<person nsid="46834205@N00" username="smaaz" favedate="1161874052"/>\r\n\t<person nsid="95626108@N00" username="chrome Foxpuppy" favedate="1160528154"/>\r\n\t<person nsid="44991966@N00" username="getnoid" favedate="1159828789"/>\r\n\t<person nsid="92544710@N00" username="miss_rogue" favedate="1158034266"/>\r\n\t<person nsid="50944224@N00" username="Infollatus" favedate="1155317436"/>\r\n\t<person nsid="80544408@N00" username="DafyddLlyr" favedate="1148511763"/>\r\n\t<person nsid="31154299@N00" username="c r i s" favedate="1143085224"/>\r\n\t<person nsid="54309070@N00" username="Shinayaker" favedate="1142584219"/>\r\n</photo>', u'name': u'flickr.photos.getFavorites'
        }
        , u'flickr.machinetags.getPairs': {
    u'errors': [{
        'text': u'Missing or invalid namespace argument.', u'message': u'Not a valid namespace', u'code': u'1'
            }
            , {
        'text': u'Missing or invalid predicate argument.', u'message': u'Not a valid predicate', u'code': u'2'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Return a list of unique namespace and predicate pairs, optionally limited by predicate or namespace, in alphabetical order.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'Limit the list of pairs returned to those that have the following namespace.', u'optional': u'1', u'name': u'namespace'
            }
            , {
        'text': u'Limit the list of pairs returned to those that have the following predicate.', u'optional': u'1', u'name': u'predicate'
            }
            , {
        'text': u'Number of photos to return per page. If this argument is omitted, it defaults to 100. The maximum allowed value is 500.', u'optional': u'1', u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': u'1', u'name': u'page'
            }
            ], 'needslogin': False, u'response': u'<pairs page="1" total="1228" perpage="500" pages="3">\r\n   <pair namespace="aero" predicate="airline" usage="1093">aero:airline</pair>\r\n   <pair namespace="aero" predicate="icao" usage="4">aero:icao</pair>\r\n   <pair namespace="aero" predicate="model" usage="1026">aero:model</pair>\r\n   <pair namespace="aero" predicate="tail" usage="1048">aero:tail</pair>\r\n</pairs>', u'name': u'flickr.machinetags.getPairs'
        }
        , u'flickr.urls.lookupGallery': {
    u'errors': [{
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.urls.lookupGallery', u'explanation': u'This is the same format returned by <a href="http://www.flickr.com/services/api/flickr.galleries.getInfo.html">flickr.galleries.getInfo</a>.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u"The gallery's URL.", u'optional': u'0', u'name': u'url'
            }
            ], 'needslogin': False, u'response': u'<gallery id="6065-72157617483228192" url="/photos/straup/galleries/72157617483228192" owner="35034348999@N01" \r\nprimary_photo_id="292882708" \r\ndate_create="1241028772" date_update="1270111667" \r\ncount_photos="17" count_videos="0" server="112" farm="1" secret="7f29861bc4">\r\n\t<title>Cat Pictures I\'ve Sent To Kevin Collins</title>\r\n\t<description />\r\n</gallery>', u'description': u'Returns gallery info, by url.'
        }
        , u'flickr.test.echo': {
    u'errors': [{
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u"A testing method which echo's all parameters back in the response.", 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            ], 'needslogin': False, u'response': u'<method>echo</method>\r\n<foo>bar</foo>', u'name': u'flickr.test.echo'
        }
        , u'flickr.photosets.editMeta': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The photoset id passed was not a valid photoset id or did not belong to the calling user.', u'message': u'Photoset not found', u'code': u'1'
            }
            , {
        'text': u'No title parameter was passed in the request. ', u'message': u'No title specified', u'code': u'2'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photoset to modify.', u'optional': u'0', u'name': u'photoset_id'
            }
            , {
        'text': u'The new title for the photoset.', u'optional': u'0', u'name': u'title'
            }
            , {
        'text': u'A description of the photoset. May contain limited html.', u'optional': u'1', u'name': u'description'
            }
            ], u'description': u'Modify the meta-data for a photoset.', 'needslogin': True, u'name': u'flickr.photosets.editMeta'
        }
        , u'flickr.photosets.removePhotos': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The photoset id passed was not the id of available photosets owned by the calling user.', u'message': u'Photoset not found', u'code': u'1'
            }
            , {
        'text': u'The photo id passed was not the id of a valid photo belonging to the calling user.', u'message': u'Photo not found', u'code': u'2'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photoset to remove photos from.', u'optional': u'0', u'name': u'photoset_id'
            }
            , {
        'text': u'Comma-delimited list of photo ids to remove from the photoset.', u'optional': u'0', u'name': u'photo_ids'
            }
            ], u'description': u'Remove multiple photos from a photoset.', 'needslogin': True, u'name': u'flickr.photosets.removePhotos'
        }
        , u'flickr.tags.getMostFrequentlyUsed': {
    u'errors': [{
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Returns a list of most frequently used tags for a user.', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            ], 'needslogin': True, u'response': u'<rsp stat="ok">\r\n<who id="30135021@N05">\r\n\t<tags>\r\n\t\t<tag count="1">blah</tag>\r\n\t\t<tag count="5">publicdomain</tag>\r\n\t</tags>\r\n</who>\r\n</rsp>', u'name': u'flickr.tags.getMostFrequentlyUsed'
        }
        , u'flickr.prefs.getContentType': {
    u'errors': [{
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Returns the default content type preference for the user.', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            ], 'needslogin': True, u'response': u'<rsp stat="ok">\r\n<person nsid="12037949754@N01" content_type="1" />\r\n</rsp>', u'name': u'flickr.prefs.getContentType'
        }
        , u'flickr.people.getPublicPhotos': {
    'needssigning': False, u'requiredperms': 'none', u'errors': [{
        'text': u'The user NSID passed was not a valid user NSID.', u'message': u'User not found', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u"The NSID of the user who's photos to return.", u'optional': u'0', u'name': u'user_id'
            }
            , {
        'text': u'Safe search setting:\r\n\r\n<ul>\r\n<li>1 for safe.</li>\r\n<li>2 for moderate.</li>\r\n<li>3 for restricted.</li>\r\n</ul>\r\n\r\n(Please note: Un-authed calls can only see Safe content.)', u'optional': u'1', u'name': u'safe_search'
            }
            , {
        'text': u'A comma-delimited list of extra information to fetch for each returned record. Currently supported fields are: <code>description</code>, <code>license</code>, <code>date_upload</code>, <code>date_taken</code>, <code>owner_name</code>, <code>icon_server</code>, <code>original_format</code>, <code>last_update</code>, <code>geo</code>, <code>tags</code>, <code>machine_tags</code>, <code>o_dims</code>, <code>views</code>, <code>media</code>, <code>path_alias</code>, <code>url_sq</code>, <code>url_t</code>, <code>url_s</code>, <code>url_q</code>, <code>url_m</code>, <code>url_n</code>, <code>url_z</code>, <code>url_c</code>, <code>url_l</code>, <code>url_o</code>', u'optional': 1, u'name': u'extras'
            }
            , {
        'text': u'Number of photos to return per page. If this argument is omitted, it defaults to 100. The maximum allowed value is 500.', u'optional': 1, u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': 1, u'name': u'page'
            }
            ], u'description': u'Get a list of public photos for the given user.', 'needslogin': False, u'name': u'flickr.people.getPublicPhotos'
        }
        , u'flickr.groups.discuss.replies.delete': {
    'needssigning': True, u'requiredperms': 'delete', u'errors': [{
        'text': u'The topic_id is invalid.', u'message': u'Topic not found', u'code': u'1'
            }
            , {
        'text': u'The reply_id is invalid.', u'message': u'Reply not found', u'code': u'2'
            }
            , {
        'text': u'Replies can only be edited by their owner.', u'message': u'Cannot delete reply', u'code': u'3'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The ID of the topic the post is in.', u'optional': u'0', u'name': u'topic_id'
            }
            , {
        'text': u'The ID of the reply to delete.', u'optional': u'0', u'name': u'reply_id'
            }
            ], u'description': u'Delete a reply from a group topic.', 'needslogin': True, u'name': u'flickr.groups.discuss.replies.delete'
        }
        , u'flickr.groups.browse': {
    u'errors': [{
        'text': u'The value passed for cat_id was not a valid category id.', u'message': u'Category not found', u'code': u'1'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.groups.browse', u'explanation': u"<p>The <code>count</code> attribute of the <code>subcat</code> element gives the number of groups inside the subcat.</p>\r\n\r\n<p>The <code>members</code> attribute of the <code>group</code> element gives the total number of members in the group. The <code>online</code> attribute gives a count of the members who are currently online. The <code>inchat</code> attribute gives a count of the number of people in the group's chat, regardless of whether they are members of the group.</p>", 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The category id to fetch a list of groups and sub-categories for. If not specified, it defaults to zero, the root of the category tree.', u'optional': u'1', u'name': u'cat_id'
            }
            ], 'needslogin': True, u'response': u'<category name="Alt" path="/Alt" pathids="/63">\r\n\t<subcat id="80" name="18+" count="0" /> \r\n\t<subcat id="82" name="Absurd" count="4" /> \r\n\t<group nsid="34955637532@N01" name="Cal\'s Public Test Group"\r\n\t\tmembers="13" online="1" chatnsid="34955637533@N01" inchat="0" /> \r\n\t<group nsid="34158032587@N01" name="Eric\'s Alt Group Test"\r\n\t\tmembers="3" online="0" chatnsid="34158032588@N01" inchat="0" /> \r\n</category>\r\n', u'description': u'Browse the group category tree, finding groups and sub-categories.'
        }
        , u'flickr.stats.getPhotostreamDomains': {
    u'errors': [{
        'text': u'The user you have requested stats has not enabled stats on their account.', u'message': u'User does not have stats', u'code': u'1'
            }
            , {
        'text': u'No stats are available for the date requested. Flickr only keeps stats data for the last 28 days.', u'message': u'No stats for that date', u'code': u'2'
            }
            , {
        'text': u'The date provided could not be parsed', u'message': u'Invalid date', u'code': u'3'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.stats.getPhotostreamDomains', u'explanation': u'<p>There is one <code>&lt;domain&gt;</code> element for each referring domain, with attributes for the domain name and the number of views.</p>\r\n\r\n<p>For details on the referrers coming from each domain listed you can call <a href="/services/api/flickr.stats.getPhotostreamReferrers.html">flickr.stats.getPhotostreamReferrers</a></p>', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'Stats will be returned for this date. This should be in either be in YYYY-MM-DD or unix timestamp format.\r\n\r\nA day according to Flickr Stats starts at midnight GMT for all users, and timestamps will automatically be rounded down to the start of the day.', u'optional': u'0', u'name': u'date'
            }
            , {
        'text': u'Number of domains to return per page. If this argument is omitted, it defaults to 25. The maximum allowed value is 100', u'optional': u'1', u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': u'1', u'name': u'page'
            }
            ], 'needslogin': True, u'response': u'<domains page="1" perpage="25" pages="1" total="3">\r\n\t<domain name="images.search.yahoo.com" views="127" />\r\n\t<domain name="flickr.com" views="122" />\r\n\t<domain name="images.google.com" views="70" />\r\n</domains>\r\n', u'description': u'Get a list of referring domains for a photostream'
        }
        , u'flickr.people.getUploadStatus': {
    u'errors': [{
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.people.getUploadStatus', u'explanation': u'<p>Bandwidth and filesize numbers are provided in bytes and kilobytes. If you\'re using 32bit numbers, stick to using the kilobyte values - they shouldn\'t ever exceed 2/4 billion, while the byte values will.</p>\r\n\r\n<p>Bandwidth is specified in bytes/kb per month.</p>\r\n\r\n\r\n<p>All accounts display "lots" for the number of remaining sets, but remains in the response for backwards compatibility.</p>\r\n\r\n<p>Pro accounts display "lots" for the number of remaining videos, while free users will display 0, 1, or 2.</p>\r\n', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            ], 'needslogin': True, u'response': u'<user id="12037949754@N01" ispro="1">\r\n\t<username>Bees</username> \r\n\t<bandwidth\r\n\t\tmaxbytes="2147483648" maxkb="2097152"\r\n\t\tusedbytes="383724" usedkb="374"\r\n\t\tremainingbytes="2147099924" remainingkb="2096777"\r\n\t /> \r\n\t<filesize\r\n\t\tmaxbytes="10485760" maxkb="10240"\r\n\t/> \r\n\t<sets\r\n\t\tcreated="27"\r\n\t\tremaining="lots"\r\n\t/>\r\n\t<videos\r\n\t\tuploaded="5"\r\n\t\tremaining="lots"\r\n\t/>\r\n</user>', u'description': u'Returns information for the calling user related to photo uploads.'
        }
        , u'flickr.places.resolvePlaceId': {
    u'errors': [{
        'text': u'', u'message': u'Place ID required.', u'code': u'2'
            }
            , {
        'text': u'', u'message': u'Place not found.', u'code': u'3'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Find Flickr Places information by Place ID.<br /><br />\r\nThis method has been deprecated. It won\'t be removed but you should use <a href="/services/api/flickr.places.getInfo.html">flickr.places.getInfo</a> instead.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'A Flickr Places ID', u'optional': u'0', u'name': u'place_id'
            }
            ], 'needslogin': False, u'response': u'<location place_id="kH8dLOubBZRvX_YZ" woeid="2487956" \r\n                latitude="37.779" longitude="-122.420"\r\n                place_url="/United+States/California/San+Francisco"\r\n                place_type="locality">\r\n   <locality place_id="kH8dLOubBZRvX_YZ" woeid="2487956"\r\n                 latitude="37.779" longitude="-122.420" \r\n                 place_url="/United+States/California/San+Francisco">San Francisco</locality>\r\n   <county place_id="hCca8XSYA5nn0X1Sfw" woeid="12587707"\r\n                 latitude="37.759" longitude="-122.435" \r\n                 place_url="/hCca8XSYA5nn0X1Sfw">San Francisco</county>\r\n   <region place_id="SVrAMtCbAphCLAtP" woeid="2347563" \r\n                latitude="37.271" longitude="-119.270" \r\n                place_url="/United+States/California">California</region>\r\n   <country place_id="4KO02SibApitvSBieQ" woeid="23424977"\r\n                  latitude="48.890" longitude="-116.982" \r\n                  place_url="/United+States">United States</country>\r\n</location>', u'name': u'flickr.places.resolvePlaceId'
        }
        , u'flickr.machinetags.getRecentValues': {
    u'errors': [{
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Fetch recently used (or created) machine tags values.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'A namespace that all values should be restricted to.', u'optional': u'1', u'name': u'namespace'
            }
            , {
        'text': u'A predicate that all values should be restricted to.', u'optional': u'1', u'name': u'predicate'
            }
            , {
        'text': u'Only return machine tags values that have been added since this timestamp, in epoch seconds.  ', u'optional': u'1', u'name': u'added_since'
            }
            ], 'needslogin': False, u'response': u'<values namespace="taxonomy" predicate="common" page="1" total="500" perpage="500" pages="1">\r\n    <value usage="4" namespace="taxonomy" predicate="common"\r\n           first_added="1244232796" last_added="1244232796">maui chaff flower</value>\r\n\r\n    <!-- and so on... -->\r\n</values>', u'name': u'flickr.machinetags.getRecentValues'
        }
        , u'flickr.panda.getList': {
    u'errors': [{
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Return a list of <a href="http://www.flickr.com/explore/panda">Flickr pandas</a>, from whom you can request photos using the <a href="/services/api/flickr.panda.getPhotos.htm">flickr.panda.getPhotos</a> API method.\r\n<br/><br/>\r\nMore information about the pandas can be found on the <a href="http://code.flickr.com/blog/2009/03/03/panda-tuesday-the-history-of-the-panda-new-apis-explore-and-you/">dev blog</a>.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            ], 'needslogin': False, u'response': u'<pandas>\r\n   <panda>ling ling</panda>\r\n   <panda>hsing hsing</panda>\r\n   <panda>wang wang</panda>\r\n</pandas>', u'name': u'flickr.panda.getList'
        }
        , u'flickr.photos.setContentType': {
    u'errors': [{
        'text': u'The photo id passed was not a valid photo id of a photo belonging to the calling user.', u'message': u'Photo not found', u'code': u'1'
            }
            , {
        'text': u'Some or all of the required arguments were not supplied.', u'message': u'Required arguments missing', u'code': u'2'
            }
            , {
        'text': u'Changing the content type of this photo is not allowed.', u'message': u'Change not allowed', u'code': u'3'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Set the content type of a photo.', 'needssigning': True, u'requiredperms': 'write', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photo to set the adultness of.', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u'The content type of the photo. Must be one of: 1 for Photo, 2 for Screenshot, and 3 for Other.', u'optional': u'0', u'name': u'content_type'
            }
            ], 'needslogin': True, u'response': u'<rsp stat="ok">\r\n<photo id="14814" content_type="3"/>\r\n</rsp>', u'name': u'flickr.photos.setContentType'
        }
        , u'flickr.photos.setDates': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The photo id was not the id of a valid photo belonging to the calling user.', u'message': u'Photo not found', u'code': u'1'
            }
            , {
        'text': u'No dates were specified to be changed.', u'message': u'Not enough arguments', u'code': u'2'
            }
            , {
        'text': u"The value passed for 'granularity' was not a valid flickr date granularity.", u'message': u'Invalid granularity', u'code': u'3'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photo to edit dates for.', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u'The date the photo was uploaded to flickr (see the <a href="/services/api/misc.dates.html">dates documentation</a>)', u'optional': u'1', u'name': u'date_posted'
            }
            , {
        'text': u'The date the photo was taken (see the <a href="/services/api/misc.dates.html">dates documentation</a>)', u'optional': u'1', u'name': u'date_taken'
            }
            , {
        'text': u'The granularity of the date the photo was taken (see the <a href="/services/api/misc.dates.html">dates documentation</a>)', u'optional': u'1', u'name': u'date_taken_granularity'
            }
            ], u'description': u'Set one or both of the dates for a photo.', 'needslogin': True, u'name': u'flickr.photos.setDates'
        }
        , u'flickr.photos.geo.getPerms': {
    u'errors': [{
        'text': u'The photo id was either invalid or was for a photo not viewable by the calling user.', u'message': u'Photo not found', u'code': u'1'
            }
            , {
        'text': u'The photo requested has no location data or is not viewable by the calling user.', u'message': u'Photo has no location information', u'code': u'2'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Get permissions for who may view geo data for a photo.', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photo to get permissions for.', u'optional': u'0', u'name': u'photo_id'
            }
            ], 'needslogin': True, u'response': u'<perms id="10592" ispublic="0" iscontact="0" isfriend="0" isfamily="1" />', u'name': u'flickr.photos.geo.getPerms'
        }
        , u'flickr.test.null': {
    'needssigning': True, u'requiredperms': 'read', u'errors': [{
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            ], u'description': u'Null test', 'needslogin': True, u'name': u'flickr.test.null'
        }
        , u'flickr.galleries.addPhoto': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'One or more required parameters was not included with your API call.', u'message': u'Required parameter missing', u'code': u'1'
            }
            , {
        'text': u'That gallery could not be found.', u'message': u'Invalid gallery ID', u'code': u'2'
            }
            , {
        'text': u'The requested photo could not be found.', u'message': u'Invalid photo ID', u'code': u'3'
            }
            , {
        'text': u'The comment body could not be validated.', u'message': u'Invalid comment', u'code': u'4'
            }
            , {
        'text': u'Unable to add the photo to the gallery.', u'message': u'Failed to add photo', u'code': u'5'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The ID of the gallery to add a photo to.  Note: this is the compound ID returned in methods like <a href="/services/api/flickr.galleries.getList.html">flickr.galleries.getList</a>, and <a href="/services/api/flickr.galleries.getListForPhoto.html">flickr.galleries.getListForPhoto</a>.', u'optional': u'0', u'name': u'gallery_id'
            }
            , {
        'text': u'The photo ID to add to the gallery', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u'A short comment or story to accompany the photo.', u'optional': u'1', u'name': u'comment'
            }
            ], u'description': u'Add a photo to a gallery.', 'needslogin': True, u'name': u'flickr.galleries.addPhoto'
        }
        , u'flickr.interestingness.getList': {
    'needssigning': False, u'requiredperms': 'none', u'errors': [{
        'text': u'The date string passed did not validate. All dates must be formatted : YYYY-MM-DD', u'message': u'Not a valid date string.', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'A specific date, formatted as YYYY-MM-DD, to return interesting photos for.', u'optional': u'1', u'name': u'date'
            }
            , {
        'text': u'Always ask the pandas for interesting photos. This is a temporary argument to allow developers to update their code.', u'optional': u'1', u'name': u'use_panda'
            }
            , {
        'text': u'A comma-delimited list of extra information to fetch for each returned record. Currently supported fields are: <code>description</code>, <code>license</code>, <code>date_upload</code>, <code>date_taken</code>, <code>owner_name</code>, <code>icon_server</code>, <code>original_format</code>, <code>last_update</code>, <code>geo</code>, <code>tags</code>, <code>machine_tags</code>, <code>o_dims</code>, <code>views</code>, <code>media</code>, <code>path_alias</code>, <code>url_sq</code>, <code>url_t</code>, <code>url_s</code>, <code>url_q</code>, <code>url_m</code>, <code>url_n</code>, <code>url_z</code>, <code>url_c</code>, <code>url_l</code>, <code>url_o</code>', u'optional': 1, u'name': u'extras'
            }
            , {
        'text': u'Number of photos to return per page. If this argument is omitted, it defaults to 100. The maximum allowed value is 500.', u'optional': 1, u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': 1, u'name': u'page'
            }
            ], u'description': u'Returns the list of interesting photos for the most recent day or a user-specified date.', 'needslogin': False, u'name': u'flickr.interestingness.getList'
        }
        , u'flickr.photosets.comments.addComment': {
    u'errors': [{
        'text': u'', u'message': u'Photoset not found', u'code': u'1'
            }
            , {
        'text': u'', u'message': u'Blank comment', u'code': u'8'
            }
            , {
        'text': u'The user has reached the limit for number of comments posted during a specific time period. Wait a bit and try again.', u'message': u'User is posting comments too fast.', u'code': u'9'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Add a comment to a photoset.', 'needssigning': True, u'requiredperms': 'write', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photoset to add a comment to.', u'optional': u'0', u'name': u'photoset_id'
            }
            , {
        'text': u'Text of the comment', u'optional': u'0', u'name': u'comment_text'
            }
            ], 'needslogin': True, u'response': u'<comment id="97777-12492-72057594037942601" />', u'name': u'flickr.photosets.comments.addComment'
        }
        , u'flickr.photos.getContext': {
    u'errors': [{
        'text': u'The photo id passed was not a valid photo id, or was the id of a photo that the calling user does not have permission to view.', u'message': u'Photo not found', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.photos.getContext', u'explanation': u'<p>When either the previous of next photo is unavailable, the element is still returned, but contains <code>id="0"</code></p>', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photo to fetch the context for.', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u'', u'optional': u'1', u'name': u'num_prev'
            }
            , {
        'text': u'', u'optional': u'1', u'name': u'num_next'
            }
            , {
        'text': u'A comma-delimited list of extra information to fetch for each returned record. Currently supported fields are: <code>description, license, date_upload, date_taken, owner_name, icon_server, original_format, last_update, geo, tags, machine_tags, o_dims, views, media, path_alias, url_sq, url_t, url_s, url_m, url_z, url_l, url_o</code>', u'optional': u'1', u'name': u'extras'
            }
            , {
        'text': u'Accepts <code>datetaken</code> or <code>dateposted</code> and returns results in the proper order.', u'optional': u'1', u'name': u'order_by'
            }
            ], 'needslogin': False, u'response': u'<prevphoto id="2980" secret="973da1e709"\r\n\ttitle="boo!" url="/photos/bees/2980/" /> \r\n<nextphoto id="2985" secret="059b664012"\r\n\ttitle="Amsterdam Amstel" url="/photos/bees/2985/" /> ', u'description': u'Returns next and previous photos for a photo in a photostream.'
        }
        , u'flickr.photos.recentlyUpdated': {
    u'errors': [{
        'text': u'Some or all of the required arguments were not supplied.', u'message': u'Required argument missing.', u'code': u'1'
            }
            , {
        'text': u'The date argument did not pass validation.', u'message': u'Not a valid date', u'code': u'2'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.photos.recentlyUpdated', u'explanation': u'<p>Photos are sorted by their date updated timestamp, in descending order.</p>', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'A Unix timestamp or any English textual datetime description indicating the date from which modifications should be compared.', u'optional': u'0', u'name': u'min_date'
            }
            , {
        'text': u'A comma-delimited list of extra information to fetch for each returned record. Currently supported fields are: <code>description</code>, <code>license</code>, <code>date_upload</code>, <code>date_taken</code>, <code>owner_name</code>, <code>icon_server</code>, <code>original_format</code>, <code>last_update</code>, <code>geo</code>, <code>tags</code>, <code>machine_tags</code>, <code>o_dims</code>, <code>views</code>, <code>media</code>, <code>path_alias</code>, <code>url_sq</code>, <code>url_t</code>, <code>url_s</code>, <code>url_q</code>, <code>url_m</code>, <code>url_n</code>, <code>url_z</code>, <code>url_c</code>, <code>url_l</code>, <code>url_o</code>', u'optional': 1, u'name': u'extras'
            }
            , {
        'text': u'Number of photos to return per page. If this argument is omitted, it defaults to 100. The maximum allowed value is 500.', u'optional': 1, u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': 1, u'name': u'page'
            }
            ], 'needslogin': True, u'response': u'<photos page="1" pages="1" perpage="100" total="2">\r\n        <photo id="169885459" owner="35034348999@N01" \r\n               secret="c85114c195" server="46" title="Doubting Michael"\r\n               ispublic="1" isfriend="0" isfamily="0" lastupdate="1150755888" />\r\n        <photo id="85022332" owner="35034348999@N01"\r\n               secret="23de6de0c0" server="41"\r\n               title="&quot;Do you think we\'re allowed to tape stuff to the walls?&quot;"\r\n               ispublic="1" isfriend="0" isfamily="0" lastupdate="1150564974" />\r\n</photos>', u'description': u"<p>Return a list of your photos that have been recently created or which have been recently modified.</p>\r\n\r\n<p>Recently modified may mean that the photo's metadata (title, description, tags) may have been changed or a comment has been added (or just modified somehow :-)</p>"
        }
        , u'flickr.photos.getWithGeoData': {
    'needssigning': True, u'requiredperms': 'read', u'errors': [{
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'Minimum upload date. Photos with an upload date greater than or equal to this value will be returned. The date should be in the form of a unix timestamp.', u'optional': u'1', u'name': u'min_upload_date'
            }
            , {
        'text': u'Maximum upload date. Photos with an upload date less than or equal to this value will be returned. The date should be in the form of a unix timestamp.', u'optional': u'1', u'name': u'max_upload_date'
            }
            , {
        'text': u'Minimum taken date. Photos with an taken date greater than or equal to this value will be returned. The date should be in the form of a mysql datetime.', u'optional': u'1', u'name': u'min_taken_date'
            }
            , {
        'text': u'Maximum taken date. Photos with an taken date less than or equal to this value will be returned. The date should be in the form of a mysql datetime.', u'optional': u'1', u'name': u'max_taken_date'
            }
            , {
        'text': u'Return photos only matching a certain privacy level. Valid values are:\r\n<ul>\r\n<li>1 public photos</li>\r\n<li>2 private photos visible to friends</li>\r\n<li>3 private photos visible to family</li>\r\n<li>4 private photos visible to friends & family</li>\r\n<li>5 completely private photos</li>\r\n</ul>\r\n', u'optional': u'1', u'name': u'privacy_filter'
            }
            , {
        'text': u'The order in which to sort returned photos. Deafults to date-posted-desc. The possible values are: date-posted-asc, date-posted-desc, date-taken-asc, date-taken-desc, interestingness-desc, and interestingness-asc.', u'optional': u'1', u'name': u'sort'
            }
            , {
        'text': u'Filter results by media type. Possible values are <code>all</code> (default), <code>photos</code> or <code>videos</code>', u'optional': u'1', u'name': u'media'
            }
            , {
        'text': u'A comma-delimited list of extra information to fetch for each returned record. Currently supported fields are: <code>description</code>, <code>license</code>, <code>date_upload</code>, <code>date_taken</code>, <code>owner_name</code>, <code>icon_server</code>, <code>original_format</code>, <code>last_update</code>, <code>geo</code>, <code>tags</code>, <code>machine_tags</code>, <code>o_dims</code>, <code>views</code>, <code>media</code>, <code>path_alias</code>, <code>url_sq</code>, <code>url_t</code>, <code>url_s</code>, <code>url_q</code>, <code>url_m</code>, <code>url_n</code>, <code>url_z</code>, <code>url_c</code>, <code>url_l</code>, <code>url_o</code>', u'optional': 1, u'name': u'extras'
            }
            , {
        'text': u'Number of photos to return per page. If this argument is omitted, it defaults to 100. The maximum allowed value is 500.', u'optional': 1, u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': 1, u'name': u'page'
            }
            ], u'description': u'Returns a list of your geo-tagged photos.', 'needslogin': True, u'name': u'flickr.photos.getWithGeoData'
        }
        , u'flickr.auth.getToken': {
    u'errors': [{
        'text': u'The specified frob does not exist or has already been used.', u'message': u'Invalid frob', u'code': u'108'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.auth.getToken', u'explanation': u'<p><code>perms</code> can have values of <code>none</code>, <code>read</code>, <code>write</code> or <code>delete</code>. For more information, see the <a href="/services/api/auth.spec.html">Auth API spec</a>.</p>', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The frob to check.', u'optional': u'0', u'name': u'frob'
            }
            ], 'needslogin': False, u'response': u'<auth>\r\n\t<token>976598454353455</token>\r\n\t<perms>write</perms>\r\n\t<user nsid="12037949754@N01" username="Bees" fullname="Cal H" />\r\n</auth>', u'description': u'Returns the auth token for the given frob, if one has been attached. <b>This method call must be signed</b>, and is <b><a href="/services/api/auth.oauth.html">deprecated in favour of OAuth</a></b>.'
        }
        , u'flickr.photos.setMeta': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The photo id passed was not the id of a photo belonging to the calling user. It might be an invalid id, or the photo might be owned by another user. ', u'message': u'Photo not found', u'code': u'1'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photo to set information for.', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u'The title for the photo.', u'optional': u'0', u'name': u'title'
            }
            , {
        'text': u'The description for the photo.', u'optional': u'0', u'name': u'description'
            }
            ], u'description': u'Set the meta information for a photo.', 'needslogin': True, u'name': u'flickr.photos.setMeta'
        }
        , u'flickr.stats.getPhotoDomains': {
    u'errors': [{
        'text': u'The user you have requested stats has not enabled stats on their account.', u'message': u'User does not have stats', u'code': u'1'
            }
            , {
        'text': u'No stats are available for the date requested. Flickr only keeps stats data for the last 28 days.', u'message': u'No stats for that date', u'code': u'2'
            }
            , {
        'text': u'The date provided could not be parsed', u'message': u'Invalid date', u'code': u'3'
            }
            , {
        'text': u'The photo id was either invalid or was for a photo not owned by the calling user.', u'message': u'Photo not found', u'code': u'4'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.stats.getPhotoDomains', u'explanation': u'<p>There is one <code>&lt;domain&gt;</code> element for each referring domain, with attributes for the domain name and the number of views.</p>\r\n\r\n<p>For details on the referrers coming from each domain listed you can call <a href="/services/api/flickr.stats.getPhotoReferrers.html">flickr.stats.getPhotoReferrers</a></p>', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'Stats will be returned for this date. This should be in either be in YYYY-MM-DD or unix timestamp format.\r\n\r\nA day according to Flickr Stats starts at midnight GMT for all users, and timestamps will automatically be rounded down to the start of the day.', u'optional': u'0', u'name': u'date'
            }
            , {
        'text': u'The id of the photo to get stats for. If not provided, stats for all photos will be returned.', u'optional': u'1', u'name': u'photo_id'
            }
            , {
        'text': u'Number of domains to return per page. If this argument is omitted, it defaults to 25. The maximum allowed value is 100.', u'optional': u'1', u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': u'1', u'name': u'page'
            }
            ], 'needslogin': True, u'response': u'<domains page="1" perpage="25" pages="1" total="3">\r\n\t<domain name="images.search.yahoo.com" views="127" />\r\n\t<domain name="flickr.com" views="122" />\r\n\t<domain name="images.google.com" views="70" />\r\n</domains>\r\n', u'description': u'Get a list of referring domains for a photo'
        }
        , u'flickr.groups.discuss.topics.add': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The group by that ID does not exist\r\n', u'message': u'Group not found', u'code': u'1'
            }
            , {
        'text': u'Either this account is not a member of the group, or discussion in this group is disabled.', u'message': u'Cannot post to group', u'code': u'2'
            }
            , {
        'text': u'The post message is too long.', u'message': u'Message is too long', u'code': u'3'
            }
            , {
        'text': u'Subject and message are required.', u'message': u'Missing required arguments', u'code': u'4'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The NSID of the group to add a topic to.\r\n', u'optional': u'0', u'name': u'group_id'
            }
            , {
        'text': u'The topic subject.', u'optional': u'0', u'name': u'subject'
            }
            , {
        'text': u'The topic message.', u'optional': u'0', u'name': u'message'
            }
            ], u'description': u'Post a new discussion topic to a group.', 'needslogin': True, u'name': u'flickr.groups.discuss.topics.add'
        }
        , u'flickr.galleries.editMeta': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'One or more required parameters was missing from your request.', u'message': u'Required parameter missing', u'code': u'1'
            }
            , {
        'text': u'The title or description arguments could not be validated.', u'message': u'Invalid title or description', u'code': u'2'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The gallery ID to update.', u'optional': u'0', u'name': u'gallery_id'
            }
            , {
        'text': u'The new title for the gallery.', u'optional': u'0', u'name': u'title'
            }
            , {
        'text': u'The new description for the gallery.', u'optional': u'1', u'name': u'description'
            }
            ], u'description': u'Modify the meta-data for a gallery.', 'needslogin': True, u'name': u'flickr.galleries.editMeta'
        }
        , u'flickr.galleries.getListForPhoto': {
    u'errors': [{
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Return the list of galleries to which a photo has been added.  Galleries are returned sorted by date which the photo was added to the gallery.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The ID of the photo to fetch a list of galleries for.', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u'Number of galleries to return per page. If this argument is omitted, it defaults to 100. The maximum allowed value is 500.', u'optional': u'1', u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': u'1', u'name': u'page'
            }
            ], 'needslogin': False, u'response': u'<galleries total="7" page="1" pages="1" per_page="100">\r\n    <gallery id="9634-72157621980433950" \r\n             url="http://www.flickr.com/photos/revdancatt/galleries/72157621980433950" \r\n             owner="35468159852@N01" date_create="1249748647" date_update="1260486168" \r\n\t     primary_photo_id="2080242123" primary_photo_server="2209" \r\n\t     primary_photo_farm="3" primary_photo_secret="55c9"\r\n             count_photos="18" count_videos="0">\r\n        <title>Vivitar Ultra Wide &amp; Slim Selection</title>\r\n        <description>The cheap and cheerful camera that isn\'t quite as cheap as it used to be.</description>\r\n    </gallery>\r\n   <gallery id="22342631-72157622254010831" \r\n             url="http://www.flickr.com/photos/22365685@N03/galleries/72157622254010831" \r\n             owner="22365685@N03" date_create="1253035020" date_update="1260431618" \r\n             primary_photo_id="3182914049" primary_photo_server="3319" \r\n             primary_photo_farm="4" primary_photo_secret="b94fb"\r\n             count_photos="13" count_videos="0">\r\n        <title>Awesome Pics</title>\r\n        <description />\r\n    </gallery>\r\n</galleries>', u'name': u'flickr.galleries.getListForPhoto'
        }
        , u'flickr.tags.getClusterPhotos': {
    'needssigning': False, u'requiredperms': 'none', u'errors': [{
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The tag that this cluster belongs to.', u'optional': u'0', u'name': u'tag'
            }
            , {
        'text': u'The top three tags for the cluster, separated by dashes (just like the url).', u'optional': u'0', u'name': u'cluster_id'
            }
            ], u'description': u'Returns the first 24 photos for a given tag cluster', 'needslogin': False, u'name': u'flickr.tags.getClusterPhotos'
        }
        , u'flickr.prefs.getGeoPerms': {
    u'errors': [{
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Returns the default privacy level for geographic information attached to the user\'s photos and whether or not the user has chosen to use geo-related EXIF information to automatically geotag their photos.\r\n\r\nPossible values, for viewing geotagged photos, are:\r\n\r\n<ul>\r\n<li>0 : <i>No default set</i></li>\r\n<li>1 : Public</li>\r\n<li>2 : Contacts only</li>\r\n<li>3 : Friends and Family only</li>\r\n<li>4 : Friends only</li>\r\n<li>5 : Family only</li>\r\n<li>6 : Private</li>\r\n</ul>\r\n\r\nUsers can edit this preference at <a href="http://www.flickr.com/account/geo/privacy/">http://www.flickr.com/account/geo/privacy/</a>.\r\n<br /><br />\r\nPossible values for whether or not geo-related EXIF information will be used to geotag a photo are:\r\n\r\n<ul>\r\n<li>0: Geo-related EXIF information will be ignored</li>\r\n<li>1: Geo-related EXIF information will be used to try and geotag photos on upload</li>\r\n</ul>\r\n\r\nUsers can edit this preference at <a href="http://www.flickr.com/account/geo/exif/?from=privacy">http://www.flickr.com/account/geo/exif/?from=privacy</a>', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            ], 'needslogin': True, u'response': u'<rsp stat="ok">\r\n<person nsid="12037949754@N01" geoperms="1" importgeoexif="0" />\r\n</rsp>', u'name': u'flickr.prefs.getGeoPerms'
        }
        , u'flickr.contacts.getPublicList': {
    u'errors': [{
        'text': u'The specified user NSID was not a valid user.', u'message': u'User not found', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.contacts.getPublicList', u'explanation': u'<p>See <a href="/services/api/flickr.contacts.getList.html">flickr.contacts.getList</a> for an explanation of the response.</p>', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The NSID of the user to fetch the contact list for.', u'optional': u'0', u'name': u'user_id'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': u'1', u'name': u'page'
            }
            , {
        'text': u'Number of photos to return per page. If this argument is omitted, it defaults to 1000. The maximum allowed value is 1000.', u'optional': u'1', u'name': u'per_page'
            }
            , {
        'text': u'Include additional information for each contact, such as realname, is_friend, is_family, path_alias and location.', u'optional': u'1', u'name': u'show_more'
            }
            ], 'needslogin': False, u'response': u'<contacts page="1" pages="1" perpage="1000" total="3">\r\n\t<contact nsid="12037949629@N01" username="Eric" iconserver="1" ignored="1" /> \r\n\t<contact nsid="12037949631@N01" username="neb" iconserver="1" ignored="0" /> \r\n\t<contact nsid="41578656547@N01" username="cal_abc" iconserver="1" ignored="0" />\r\n</contacts>', u'description': u'Get the contact list for a user.'
        }
        , u'flickr.tags.getListUserRaw': {
    u'errors': [{
        'text': u'The calling user was not logged in.', u'message': u'User not found', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Get the raw versions of a given tag (or all tags) for the currently logged-in user.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The tag you want to retrieve all raw versions for.', u'optional': u'1', u'name': u'tag'
            }
            ], 'needslogin': False, u'response': u'<who id="12037949754@N01">\r\n    <tags>\r\n        <tag clean="foo">\r\n            <raw>foo</raw>\r\n            <raw>Foo</raw>\r\n            <raw>f:oo</raw>\r\n        </tag>\r\n    </tags>\r\n</who>', u'name': u'flickr.tags.getListUserRaw'
        }
        , u'flickr.photos.getContactsPublicPhotos': {
    u'errors': [{
        'text': u'The user NSID passed was not a valid user NSID.', u'message': u'User not found', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u"Fetch a list of recent public photos from a users' contacts.", 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The NSID of the user to fetch photos for.', u'optional': u'0', u'name': u'user_id'
            }
            , {
        'text': u'Number of photos to return. Defaults to 10, maximum 50. This is only used if <code>single_photo</code> is not passed.', u'optional': u'1', u'name': u'count'
            }
            , {
        'text': u'set as 1 to only show photos from friends and family (excluding regular contacts).', u'optional': u'1', u'name': u'just_friends'
            }
            , {
        'text': u'Only fetch one photo (the latest) per contact, instead of all photos in chronological order.', u'optional': u'1', u'name': u'single_photo'
            }
            , {
        'text': u'Set to 1 to include photos from the user specified by user_id.', u'optional': u'1', u'name': u'include_self'
            }
            , {
        'text': u'A comma-delimited list of extra information to fetch for each returned record. Currently supported fields are: license, date_upload, date_taken, owner_name, icon_server, original_format, last_update.', u'optional': u'1', u'name': u'extras'
            }
            ], 'needslogin': False, u'response': u'<photos>\r\n\t<photo id="2801" owner="12037949629@N01"\r\n\t\tsecret="123456" server="1"\r\n\t\tusername="Eric is the best" title="grease" /> \r\n\t<photo id="2499" owner="33853651809@N01"\r\n\t\tsecret="123456" server="1"\r\n\t\tusername="cal18" title="36679_o" /> \r\n\t<photo id="2437" owner="12037951898@N01"\r\n\t\tsecret="123456" server="1"\r\n\t\tusername="georgie parker" title="phoenix9_stewart" /> \r\n</photos>', u'name': u'flickr.photos.getContactsPublicPhotos'
        }
        , u'flickr.photosets.getList': {
    u'errors': [{
        'text': u'The user NSID passed was not a valid user NSID and the calling user was not logged in.\r\n', u'message': u'User not found', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.photosets.getList', u'explanation': u"<p>Photosets are returned in the user's specified order, which may not mean the newest set is first. Applications displaying photosets should respect the user's ordering.</p>", 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The NSID of the user to get a photoset list for. If none is specified, the calling user is assumed.', u'optional': u'1', u'name': u'user_id'
            }
            , {
        'text': u'The page of results to get. Currently, if this is not provided, all sets are returned, but this behaviour may change in future.', u'optional': u'1', u'name': u'page'
            }
            , {
        'text': u'The number of sets to get per page. If paging is enabled, the maximum number of sets per page is 500.', u'optional': u'1', u'name': u'per_page'
            }
            ], 'needslogin': False, u'response': u'<photosets page="1" pages="1" perpage="30" total="2" cancreate="1">\r\n    <photoset id="72157626216528324" primary="5504567858" secret="017804c585" server="5174" farm="6" photos="22" videos="0" count_views="137" count_comments="0" can_comment="1" date_create="1299514498" date_update="1300335009">\r\n      <title>Avis Blanche</title>\r\n      <description>My Grandma\'s Recipe File.</description>\r\n    </photoset>\r\n    <photoset id="72157624618609504" primary="4847770787" secret="6abd09a292" server="4153" farm="5" photos="43" videos="12" count_views="523" count_comments="1" can_comment="1" date_create="1280530593" date_update="1308091378">\r\n      <title>Mah Kittehs</title>\r\n      <description>Sixty and Niner. Born on the 3rd of May, 2010, or thereabouts. Came to my place on Thursday, July 29, 2010.</description>\r\n    </photoset>\r\n</photosets>', u'description': u'Returns the photosets belonging to the specified user.'
        }
        , u'flickr.auth.getFullToken': {
    u'errors': [{
        'text': u'The passed mini-token was not valid.', u'message': u'Mini-token not found', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.auth.getFullToken', u'explanation': u'<p><code>perms</code> can have values of <code>none</code>, <code>read</code>, <code>write</code> or <code>delete</code>. For more information, see the <a href="/services/api/auth.spec.html">Auth API spec</a>.</p>', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The mini-token typed in by a user. It should be 9 digits long. It may optionally contain dashes.', u'optional': u'0', u'name': u'mini_token'
            }
            ], 'needslogin': False, u'response': u'<auth>\r\n\t<token>976598454353455</token>\r\n\t<perms>write</perms>\r\n\t<user nsid="12037949754@N01" username="Bees" fullname="Cal H" />\r\n</auth>', u'description': u'Get the full authentication token for a mini-token. <b>This method call must be signed</b>, and is <b><a href="/services/api/auth.oauth.html">deprecated in favour of OAuth</a></b>.'
        }
        , u'flickr.galleries.getPhotos': {
    u'errors': [{
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.galleries.getPhotos', u'explanation': u'Returns a <a href="http://code.flickr.com/blog/2008/08/19/standard-photos-response-apis-for-civilized-age/">standard photo response</a>.  Additionally if the gallery creator has included a comment with the photo this will be then the photo element will have the attribute has_comment="1" and the child element "comment" will be present.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The ID of the gallery of photos to return', u'optional': u'0', u'name': u'gallery_id'
            }
            , {
        'text': u'A comma-delimited list of extra information to fetch for each returned record. Currently supported fields are: <code>description</code>, <code>license</code>, <code>date_upload</code>, <code>date_taken</code>, <code>owner_name</code>, <code>icon_server</code>, <code>original_format</code>, <code>last_update</code>, <code>geo</code>, <code>tags</code>, <code>machine_tags</code>, <code>o_dims</code>, <code>views</code>, <code>media</code>, <code>path_alias</code>, <code>url_sq</code>, <code>url_t</code>, <code>url_s</code>, <code>url_q</code>, <code>url_m</code>, <code>url_n</code>, <code>url_z</code>, <code>url_c</code>, <code>url_l</code>, <code>url_o</code>', u'optional': 1, u'name': u'extras'
            }
            , {
        'text': u'Number of photos to return per page. If this argument is omitted, it defaults to 100. The maximum allowed value is 500.', u'optional': 1, u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': 1, u'name': u'page'
            }
            ], 'needslogin': False, u'response': u'<photos page="1" pages="1" perpage="500" total="2">\r\n\t<photo id="2822546461" owner="78398753@N00" secret="2dbcdb589f" server="1" farm="1" title="FOO" \r\n     ispublic="1" isfriend="0" isfamily="0" is_primary="1" has_comment="1">\r\n\t\t<comment>best cat picture ever!</comment>\r\n\t</photo>\r\n\t<photo id="2822544806" owner="78398753@N00" secret="bd93cbe917" server="1" farm="1" title="OOK" \r\n     ispublic="1" isfriend="0" isfamily="0" is_primary="0" has_comment="0" />\r\n</photos>', u'description': u'Return the list of photos for a gallery'
        }
        , u'flickr.groups.discuss.replies.getInfo': {
    u'errors': [{
        'text': u'The topic_id is invalid', u'message': u'Topic not found', u'code': u'1'
            }
            , {
        'text': u'The reply_id is invalid', u'message': u'Reply not found', u'code': u'2'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Get information on a group topic reply.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The ID of the topic the post is in.', u'optional': u'0', u'name': u'topic_id'
            }
            , {
        'text': u'The ID of the reply to fetch.', u'optional': u'0', u'name': u'reply_id'
            }
            ], 'needslogin': False, u'response': u'<?xml version="1.0" encoding="utf-8" ?>\r\n<rsp stat="ok">\r\n  <reply id="72157607082559968" author="30134652@N05" authorname="JAMAL\'S ACCOUNT" is_pro="0" role="admin" iconserver="0" iconfarm="0" can_edit="1" can_delete="1" datecreate="1337975921" lastedit="0">\r\n    <message>...well, too bad.</message>\r\n  </reply>\r\n</rsp>', u'name': u'flickr.groups.discuss.replies.getInfo'
        }
        , u'flickr.photos.geo.getLocation': {
    u'errors': [{
        'text': u'The photo id was either invalid or was for a photo not viewable by the calling user.', u'message': u'Photo not found.', u'code': u'1'
            }
            , {
        'text': u'The photo requested has no location data or is not viewable by the calling user.', u'message': u'Photo has no location information.', u'code': u'2'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Get the geo data (latitude and longitude and the accuracy level) for a photo.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photo you want to retrieve location data for.', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u'Extra flags.', u'optional': u'1', u'name': u'extras'
            }
            ], 'needslogin': False, u'response': u'<photo id="123">\r\n        <location latitude="-17.685895" longitude="-63.36914" accuracy="6" />\r\n</photo>', u'name': u'flickr.photos.geo.getLocation'
        }
        , u'flickr.places.find': {
    u'errors': [{
        'text': u'One or more required parameters was not included with the API call.', u'message': u'Required parameter missing', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.places.find', u'explanation': u'Each place returned will contain its place ID, corresponding URL (underneath www.flickr.com/places) and place type for disambiguating different locations with the same name.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The query string to use for place ID lookups', u'optional': u'0', u'name': u'query'
            }
            , {
        'text': u'A bounding box for limiting the area to query.', u'optional': u'1', u'name': u'bbox'
            }
            , {
        'text': u'Secret sauce.', u'optional': u'1', u'name': u'extras'
            }
            , {
        'text': u'Do we want sexy time words in our venue results?', u'optional': u'1', u'name': u'safe'
            }
            ], 'needslogin': False, u'response': u'<places query="Alabama" total="3">\r\n   <place place_id="VrrjuESbApjeFS4." woeid="2347559"\r\n               latitude="32.614" longitude="-86.680"\r\n               place_url="/United+States/Alabama"\r\n               place_type="region">Alabama, Alabama, United States</place>\r\n   <place place_id="cGHuc0mbApmzEHoP" woeid="2352520"\r\n               latitude="43.096" longitude="-78.389"\r\n               place_url="/United+States/New+York/Alabama"\r\n               place_type="locality">Alabama, New York, United States</place>\r\n   <place place_id="o4yVPEqYBJvFMP8Q" woeid="1579389"\r\n               latitude="-26.866" longitude="26.583"\r\n               place_url="/South+Africa/North+West/Alabama"\r\n               place_type="locality">Alabama, North West, South Africa</place>\r\n</places>', u'description': u'Return a list of place IDs for a query string.<br /><br />\r\nThe flickr.places.find method is <b>not</b> a geocoder. It will round <q>up</q> to the nearest place type to which place IDs apply. For example, if you pass it a street level address it will return the city that contains the address rather than the street, or building, itself.'
        }
        , u'flickr.photosets.comments.editComment': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The comment id passed was not a valid comment id.', u'message': u'Comment not found.', u'code': u'2'
            }
            , {
        'text': u"Comment text can't be blank.", u'message': u'Blank comment.', u'code': u'8'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the comment to edit.', u'optional': u'0', u'name': u'comment_id'
            }
            , {
        'text': u'Update the comment to this text.', u'optional': u'0', u'name': u'comment_text'
            }
            ], u'description': u'Edit the text of a comment as the currently authenticated user.', 'needslogin': True, u'name': u'flickr.photosets.comments.editComment'
        }
        , u'flickr.auth.getFrob': {
    u'errors': [{
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Returns a frob to be used during authentication. <b>This method call must be signed</b>, and is <b><a href="/services/api/auth.oauth.html">deprecated in favour of OAuth</a></b>.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            ], 'needslogin': False, u'response': u'<frob>746563215463214621</frob>', u'name': u'flickr.auth.getFrob'
        }
        , u'flickr.photos.comments.getRecentForContacts': {
    'needssigning': True, u'requiredperms': 'read', u'errors': [{
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'Limits the resultset to photos that have been commented on since this date. The date should be in the form of a Unix timestamp.<br /><br />\r\nThe default, and maximum, offset is (1) hour.\r\n\r\n\r\n', u'optional': u'1', u'name': u'date_lastcomment'
            }
            , {
        'text': u'A comma-separated list of contact NSIDs to limit the scope of the query to.', u'optional': u'1', u'name': u'contacts_filter'
            }
            , {
        'text': u'A comma-delimited list of extra information to fetch for each returned record. Currently supported fields are: <code>description</code>, <code>license</code>, <code>date_upload</code>, <code>date_taken</code>, <code>owner_name</code>, <code>icon_server</code>, <code>original_format</code>, <code>last_update</code>, <code>geo</code>, <code>tags</code>, <code>machine_tags</code>, <code>o_dims</code>, <code>views</code>, <code>media</code>, <code>path_alias</code>, <code>url_sq</code>, <code>url_t</code>, <code>url_s</code>, <code>url_q</code>, <code>url_m</code>, <code>url_n</code>, <code>url_z</code>, <code>url_c</code>, <code>url_l</code>, <code>url_o</code>', u'optional': 1, u'name': u'extras'
            }
            , {
        'text': u'Number of photos to return per page. If this argument is omitted, it defaults to 100. The maximum allowed value is 500.', u'optional': 1, u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': 1, u'name': u'page'
            }
            ], u'description': u'Return the list of photos belonging to your contacts that have been commented on recently.', 'needslogin': True, u'name': u'flickr.photos.comments.getRecentForContacts'
        }
        , u'flickr.photos.notes.add': {
    u'errors': [{
        'text': u'The photo id passed was not a valid photo id', u'message': u'Photo not found', u'code': u'1'
            }
            , {
        'text': u'The calling user does not have permission to add a note to this photo', u'message': u'User cannot add notes', u'code': u'2'
            }
            , {
        'text': u'One or more of the required arguments were not supplied.', u'message': u'Missing required arguments', u'code': u'3'
            }
            , {
        'text': u'The maximum number of notes for the photo has been reached.', u'message': u'Maximum number of notes reached', u'code': u'4'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Add a note to a photo. Coordinates and sizes are in pixels, based on the 500px image size shown on individual photo pages.', 'needssigning': True, u'requiredperms': 'write', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photo to add a note to', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u'The left coordinate of the note', u'optional': u'0', u'name': u'note_x'
            }
            , {
        'text': u'The top coordinate of the note', u'optional': u'0', u'name': u'note_y'
            }
            , {
        'text': u'The width of the note', u'optional': u'0', u'name': u'note_w'
            }
            , {
        'text': u'The height of the note', u'optional': u'0', u'name': u'note_h'
            }
            , {
        'text': u'The description of the note', u'optional': u'0', u'name': u'note_text'
            }
            ], 'needslogin': True, u'response': u'<note id="1234" />', u'name': u'flickr.photos.notes.add'
        }
        , u'flickr.photos.suggestions.removeSuggestion': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The unique ID for the location suggestion to approve.', u'optional': u'0', u'name': u'suggestion_id'
            }
            ], u'description': u'Remove a suggestion, made by the calling user, from a photo.', 'needslogin': True, u'name': u'flickr.photos.suggestions.removeSuggestion'
        }
        , u'flickr.photos.setPerms': {
    u'errors': [{
        'text': u'The photo id passed was not a valid photo id of a photo belonging to the calling user.', u'message': u'Photo not found', u'code': u'1'
            }
            , {
        'text': u'Some or all of the required arguments were not supplied.', u'message': u'Required arguments missing', u'code': u'2'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Set permissions for a photo.', 'needssigning': True, u'requiredperms': 'write', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photo to set permissions for.', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u'1 to set the photo to public, 0 to set it to private.', u'optional': u'0', u'name': u'is_public'
            }
            , {
        'text': u'1 to make the photo visible to friends when private, 0 to not.', u'optional': u'0', u'name': u'is_friend'
            }
            , {
        'text': u'1 to make the photo visible to family when private, 0 to not.', u'optional': u'0', u'name': u'is_family'
            }
            , {
        'text': u"who can add comments to the photo and it's notes. one of:<br />\r\n<code>0</code>: nobody<br />\r\n<code>1</code>: friends &amp; family<br />\r\n<code>2</code>: contacts<br />\r\n<code>3</code>: everybody", u'optional': u'0', u'name': u'perm_comment'
            }
            , {
        'text': u'who can add notes and tags to the photo. one of:<br />\r\n<code>0</code>: nobody / just the owner<br />\r\n<code>1</code>: friends &amp; family<br />\r\n<code>2</code>: contacts<br />\r\n<code>3</code>: everybody\r\n', u'optional': u'0', u'name': u'perm_addmeta'
            }
            ], 'needslogin': True, u'response': u'<photoid secret="abcdef" originalsecret="abcdef">1234</photoid>', u'name': u'flickr.photos.setPerms'
        }
        , u'flickr.photos.people.add': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The NSID passed was not a valid user id.', u'message': u'Person not found', u'code': u'1'
            }
            , {
        'text': u'The photo id passed was not a valid photo id.', u'message': u'Photo not found', u'code': u'2'
            }
            , {
        'text': u'The person being added to the photo does not allow the calling user to add them.', u'message': u'User cannot add this person to photos', u'code': u'3'
            }
            , {
        'text': u"The owner of the photo doesn't allow the calling user to add people to their photos.", u'message': u'User cannot add people to that photo', u'code': u'4'
            }
            , {
        'text': u'The person being added to the photo does not want to be identified in this photo.', u'message': u"Person can't be tagged in that photo", u'code': u'5'
            }
            , {
        'text': u'Not all of the co-ordinate parameters (person_x, person_y, person_w, person_h) were passed with valid values.', u'message': u'Some co-ordinate paramters were blank', u'code': u'6'
            }
            , {
        'text': u"You can only add yourself to another member's non-public photos.", u'message': u"Can't add that person to a non-public photo", u'code': u'7'
            }
            , {
        'text': u'The maximum number of people has already been added to the photo.', u'message': u'Too many people in that photo', u'code': u'8'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photo to add a person to.', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u'The NSID of the user to add to the photo.', u'optional': u'0', u'name': u'user_id'
            }
            , {
        'text': u'The left-most pixel co-ordinate of the box around the person.', u'optional': u'1', u'name': u'person_x'
            }
            , {
        'text': u'The top-most pixel co-ordinate of the box around the person.', u'optional': u'1', u'name': u'person_y'
            }
            , {
        'text': u'The width (in pixels) of the box around the person.', u'optional': u'1', u'name': u'person_w'
            }
            , {
        'text': u'The height (in pixels) of the box around the person.', u'optional': u'1', u'name': u'person_h'
            }
            ], u'description': u'Add a person to a photo. Coordinates and sizes of boxes are optional; they are measured in pixels, based on the 500px image size shown on individual photo pages.', 'needslogin': True, u'name': u'flickr.photos.people.add'
        }
        , u'flickr.photos.getExif': {
    u'errors': [{
        'text': u'The photo id was either invalid or was for a photo not viewable by the calling user.', u'message': u'Photo not found', u'code': u'1'
            }
            , {
        'text': u'The owner of the photo does not want to share EXIF data.', u'message': u'Permission denied', u'code': u'2'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'name': u'flickr.photos.getExif', u'explanation': u'<p>The <code>&lt;clean&gt;</code> element contains a pretty-formatted version of the tag where availabale.</p>', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photo to fetch information for.', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u"The secret for the photo. If the correct secret is passed then permissions checking is skipped. This enables the 'sharing' of individual photos by passing around the id and secret.", u'optional': u'1', u'name': u'secret'
            }
            ], 'needslogin': False, u'response': u'<photo id="4424" secret="06b8e43bc7" server="2">\r\n\t<exif tagspace="TIFF" tagspaceid="1" tag="271" label="Manufacturer">\r\n\t\t<raw>Canon</raw>\r\n\t</exif>\r\n\t<exif tagspace="EXIF" tagspaceid="0" tag="33437" label="Aperture">\r\n\t\t<raw>90/10</raw>\r\n\t\t<clean>f/9</clean>\r\n\t</exif>\r\n\t<exif tagspace="GPS" tagspaceid="3" tag="4" label="Longitude">\r\n\t\t<raw>64/1, 42/1, 4414/100</raw>\r\n\t\t<clean>64\xb0 42\' 44.14"</clean>\r\n\t</exif>\r\n</photo>\r\n', u'description': u'Retrieves a list of EXIF/TIFF/GPS tags for a given photo. The calling user must have permission to view the photo.'
        }
        , u'flickr.photos.licenses.getInfo': {
    u'errors': [{
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Fetches a list of available photo licenses for Flickr.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            ], 'needslogin': False, u'response': u'<licenses>\r\n        <license id="0" name="All Rights Reserved" url="" />\r\n\t<license id="1" name="Attribution-NonCommercial-ShareAlike License"\r\n\t\turl="http://creativecommons.org/licenses/by-nc-sa/2.0/" /> \r\n\t<license id="2" name="Attribution-NonCommercial License"\r\n\t\turl="http://creativecommons.org/licenses/by-nc/2.0/" /> \r\n\t<license id="3" name="Attribution-NonCommercial-NoDerivs License"\r\n\t\turl="http://creativecommons.org/licenses/by-nc-nd/2.0/" /> \r\n\t<license id="4" name="Attribution License"\r\n\t\turl="http://creativecommons.org/licenses/by/2.0/" /> \r\n\t<license id="5" name="Attribution-ShareAlike License"\r\n\t\turl="http://creativecommons.org/licenses/by-sa/2.0/" /> \r\n\t<license id="6" name="Attribution-NoDerivs License"\r\n\t\turl="http://creativecommons.org/licenses/by-nd/2.0/" /> \r\n\t<license id="7" name="No known copyright restrictions"\r\n\t\turl="http://flickr.com/commons/usage/" />\r\n        <license id="8" name="United States Government Work"\r\n                url="http://www.usa.gov/copyright.shtml" />\r\n</licenses>', u'name': u'flickr.photos.licenses.getInfo'
        }
        , u'flickr.groups.pools.add': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The photo id passed was not the id of a photo owned by the caling user.', u'message': u'Photo not found', u'code': u'1'
            }
            , {
        'text': u'The group id passed was not a valid id for a group the user is a member of.', u'message': u'Group not found', u'code': u'2'
            }
            , {
        'text': u'The specified photo is already in the pool for the specified group.', u'message': u'Photo already in pool', u'code': u'3'
            }
            , {
        'text': u'The photo has already been added to the maximum allowed number of pools.', u'message': u'Photo in maximum number of pools', u'code': u'4'
            }
            , {
        'text': u'The user has already added the maximum amount of allowed photos to the pool.', u'message': u'Photo limit reached', u'code': u'5'
            }
            , {
        'text': u'The pool is moderated, and the photo has been added to the Pending Queue. If it is approved by a group administrator, it will be added to the pool.', u'message': u'Your Photo has been added to the Pending Queue for this Pool', u'code': u'6'
            }
            , {
        'text': u'The pool is moderated, and the photo has already been added to the Pending Queue.', u'message': u'Your Photo has already been added to the Pending Queue for this Pool', u'code': u'7'
            }
            , {
        'text': u'The content has been disallowed from the pool by the group admin(s).', u'message': u'Content not allowed', u'code': u'8'
            }
            , {
        'text': u'A group pool has reached the upper limit for the number of photos allowed.', u'message': u'Maximum number of photos in Group Pool', u'code': u'10'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photo to add to the group pool. The photo must belong to the calling user.', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u"The NSID of the group who's pool the photo is to be added to.", u'optional': u'0', u'name': u'group_id'
            }
            ], u'description': u"Add a photo to a group's pool.", 'needslogin': True, u'name': u'flickr.groups.pools.add'
        }
        , u'flickr.machinetags.getValues': {
    u'errors': [{
        'text': u'Missing or invalid namespace argument.', u'message': u'Not a valid namespace', u'code': u'1'
            }
            , {
        'text': u'Missing or invalid predicate argument.', u'message': u'Not a valid predicate', u'code': u'2'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Return a list of unique values for a namespace and predicate.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The namespace that all values should be restricted to.', u'optional': u'0', u'name': u'namespace'
            }
            , {
        'text': u'The predicate that all values should be restricted to.', u'optional': u'0', u'name': u'predicate'
            }
            , {
        'text': u'Number of photos to return per page. If this argument is omitted, it defaults to 100. The maximum allowed value is 500.', u'optional': u'1', u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': u'1', u'name': u'page'
            }
            , {
        'text': u'Minimum usage count.', u'optional': u'1', u'name': u'usage'
            }
            ], 'needslogin': False, u'response': u'<values namespace="upcoming" predicate="event" page="1" pages="1" total="3" perpage="500">\r\n    <value usage="3">123</value>\r\n    <value usage="1">456</value>\r\n    <value usage="147">789</value>\r\n</values>', u'name': u'flickr.machinetags.getValues'
        }
        , u'flickr.photosets.delete': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The photoset id passed was not a valid photoset id or did not belong to the calling user.', u'message': u'Photoset not found', u'code': u'1'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photoset to delete. It must be owned by the calling user.', u'optional': u'0', u'name': u'photoset_id'
            }
            ], u'description': u'Delete a photoset.', 'needslogin': True, u'name': u'flickr.photosets.delete'
        }
        , u'flickr.push.unsubscribe': {
    'needssigning': True, u'requiredperms': 'read', u'errors': [{
        'text': u'One of the required arguments for the method was not provided.', u'message': u'Required parameter missing', u'code': u'1'
            }
            , {
        'text': u'One of the arguments was specified with an illegal value.', u'message': u'Invalid parameter value', u'code': u'2'
            }
            , {
        'text': u'The verification callback failed, or failed to return the expected response to confirm the un-subscription.', u'message': u'Callback failed or invalid response', u'code': u'4'
            }
            , {
        'text': u'A subscription with those details exists already, but it is in a pending (non-verified) state. Please wait a bit for the verification callback to complete before attempting to update the subscription.', u'message': u'Subscription awaiting verification callback response - try again later', u'code': u'6'
            }
            , {
        'text': u'No subscription matching the provided details for this user could be found.', u'message': u'Subscription not found', u'code': u'7'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The type of subscription. See <a href="http://www.flickr.com/services/api/flickr.push.getTopics.htm">flickr.push.getTopics</a>.', u'optional': u'0', u'name': u'topic'
            }
            , {
        'text': u'The url for the subscription endpoint (must be the same url as was used when creating the subscription).', u'optional': u'0', u'name': u'callback'
            }
            , {
        'text': u'The verification mode, either \'sync\' or \'async\'. See the <a href="http://pubsubhubbub.googlecode.com/svn/trunk/pubsubhubbub-core-0.3.html#subscribingl">Google PubSubHubbub spec</a> for details.', u'optional': u'0', u'name': u'verify'
            }
            , {
        'text': u'The verification token to be echoed back to the subscriber during the verification callback, as per the <a href="http://pubsubhubbub.googlecode.com/svn/trunk/pubsubhubbub-core-0.3.html#subscribing">Google PubSubHubbub spec</a>. Limited to 200 bytes.', u'optional': u'1', u'name': u'verify_token'
            }
            ], u'description': u'Why would you want to do this?\r\n<br><br>\r\n<i>(this method is experimental and may change)</i>', 'needslogin': True, u'name': u'flickr.push.unsubscribe'
        }
        , u'flickr.stats.getCollectionStats': {
    u'errors': [{
        'text': u'The user you have requested stats has not enabled stats on their account.', u'message': u'User does not have stats', u'code': u'1'
            }
            , {
        'text': u'No stats are available for the date requested. Flickr only keeps stats data for the last 28 days.', u'message': u'No stats for that date', u'code': u'2'
            }
            , {
        'text': u'The date provided could not be parsed', u'message': u'Invalid date', u'code': u'3'
            }
            , {
        'text': u'The collection id was either invalid or was for a collection not owned by the calling user.', u'message': u'Collection not found', u'code': u'4'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Get the number of views on a collection for a given date.', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'Stats will be returned for this date. This should be in either be in YYYY-MM-DD or unix timestamp format.\r\n\r\nA day according to Flickr Stats starts at midnight GMT for all users, and timestamps will automatically be rounded down to the start of the day.', u'optional': u'0', u'name': u'date'
            }
            , {
        'text': u'The id of the collection to get stats for.', u'optional': u'0', u'name': u'collection_id'
            }
            ], 'needslogin': True, u'response': u'<stats views="24" />', u'name': u'flickr.stats.getCollectionStats'
        }
        , u'flickr.photos.suggestions.approveSuggestion': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The unique ID for the location suggestion to approve.', u'optional': u'0', u'name': u'suggestion_id'
            }
            ], u'description': u'Approve a suggestion for a photo.', 'needslogin': True, u'name': u'flickr.photos.suggestions.approveSuggestion'
        }
        , u'flickr.places.getPlaceTypes': {
    u'errors': [{
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Fetches a list of available place types for Flickr.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            ], 'needslogin': False, u'response': u'<place_types>\r\n   <place_type place_type_id="22">neighbourhood</place_type>\r\n   <place_type place_type_id="7">locality</place_type>\r\n   <place_type place_type_id="9">county</place_type>\r\n   <place_type place_type_id="8">region</place_type>\r\n   <place_type place_type_id="12">country</place_type>\r\n   <place_type place_type_id="29">continent</place_type>\r\n</place_types>', u'name': u'flickr.places.getPlaceTypes'
        }
        , u'flickr.photos.removeTag': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u"The calling user doesn't have permission to delete the specified tag. This could mean it belongs to someone else, or doesn't exist.", u'message': u'Tag not found', u'code': u'1'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The tag to remove from the photo. This parameter should contain a tag id, as returned by <a href="/services/api/flickr.photos.getInfo.html">flickr.photos.getInfo</a>.', u'optional': u'0', u'name': u'tag_id'
            }
            ], u'description': u'Remove a tag from a photo.', 'needslogin': True, u'name': u'flickr.photos.removeTag'
        }
        , u'flickr.photos.getRecent': {
    'needssigning': False, u'requiredperms': 'none', u'errors': [{
        'text': u'', u'message': u'bad value for jump_to, must be valid photo id.', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'', u'optional': u'1', u'name': u'jump_to'
            }
            , {
        'text': u'A comma-delimited list of extra information to fetch for each returned record. Currently supported fields are: <code>description</code>, <code>license</code>, <code>date_upload</code>, <code>date_taken</code>, <code>owner_name</code>, <code>icon_server</code>, <code>original_format</code>, <code>last_update</code>, <code>geo</code>, <code>tags</code>, <code>machine_tags</code>, <code>o_dims</code>, <code>views</code>, <code>media</code>, <code>path_alias</code>, <code>url_sq</code>, <code>url_t</code>, <code>url_s</code>, <code>url_q</code>, <code>url_m</code>, <code>url_n</code>, <code>url_z</code>, <code>url_c</code>, <code>url_l</code>, <code>url_o</code>', u'optional': 1, u'name': u'extras'
            }
            , {
        'text': u'Number of photos to return per page. If this argument is omitted, it defaults to 100. The maximum allowed value is 500.', u'optional': 1, u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': 1, u'name': u'page'
            }
            ], u'description': u'Returns a list of the latest public photos uploaded to flickr.', 'needslogin': False, u'name': u'flickr.photos.getRecent'
        }
        , u'flickr.photosets.getPhotos': {
    u'errors': [{
        'text': u'The photoset id passed was not a valid photoset id.', u'message': u'Photoset not found', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Get the list of photos in a set.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photoset to return the photos for.', u'optional': u'0', u'name': u'photoset_id'
            }
            , {
        'text': u'A comma-delimited list of extra information to fetch for each returned record. Currently supported fields are: license, date_upload, date_taken, owner_name, icon_server, original_format, last_update, geo, tags, machine_tags, o_dims, views, media, path_alias, url_sq, url_t, url_s, url_m, url_o', u'optional': u'1', u'name': u'extras'
            }
            , {
        'text': u'Return photos only matching a certain privacy level. This only applies when making an authenticated call to view a photoset you own. Valid values are:\r\n<ul>\r\n<li>1 public photos</li>\r\n<li>2 private photos visible to friends</li>\r\n<li>3 private photos visible to family</li>\r\n<li>4 private photos visible to friends &amp; family</li>\r\n<li>5 completely private photos</li>\r\n</ul>\r\n', u'optional': u'1', u'name': u'privacy_filter'
            }
            , {
        'text': u'Number of photos to return per page. If this argument is omitted, it defaults to 500. The maximum allowed value is 500.', u'optional': u'1', u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': u'1', u'name': u'page'
            }
            , {
        'text': u'Filter results by media type. Possible values are <code>all</code> (default), <code>photos</code> or <code>videos</code>', u'optional': u'1', u'name': u'media'
            }
            ], 'needslogin': False, u'response': u'<photoset id="4" primary="2483" page="1" perpage="500" pages="1" total="2">\r\n\t<photo id="2484" secret="123456" server="1"\r\n\t\ttitle="my photo" isprimary="0" /> \r\n\t<photo id="2483" secret="123456" server="1"\r\n\t\ttitle="flickr rocks" isprimary="1" /> \r\n</photoset>', u'name': u'flickr.photosets.getPhotos'
        }
        , u'flickr.people.getPhotos': {
    'needssigning': True, u'requiredperms': 'read', u'errors': [{
        'text': u'', u'message': u'Required arguments missing', u'code': u'1'
            }
            , {
        'text': u'A user_id was passed which did not match a valid flickr user.', u'message': u'Unknown user', u'code': u'2'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The NSID of the user who\'s photos to return. A value of "me" will return the calling user\'s photos.', u'optional': u'0', u'name': u'user_id'
            }
            , {
        'text': u'Safe search setting:\r\n\r\n<ul>\r\n<li>1 for safe.</li>\r\n<li>2 for moderate.</li>\r\n<li>3 for restricted.</li>\r\n</ul>\r\n\r\n(Please note: Un-authed calls can only see Safe content.)', u'optional': u'1', u'name': u'safe_search'
            }
            , {
        'text': u'Minimum upload date. Photos with an upload date greater than or equal to this value will be returned. The date should be in the form of a unix timestamp.', u'optional': u'1', u'name': u'min_upload_date'
            }
            , {
        'text': u'Maximum upload date. Photos with an upload date less than or equal to this value will be returned. The date should be in the form of a unix timestamp.', u'optional': u'1', u'name': u'max_upload_date'
            }
            , {
        'text': u'Minimum taken date. Photos with an taken date greater than or equal to this value will be returned. The date should be in the form of a mysql datetime.', u'optional': u'1', u'name': u'min_taken_date'
            }
            , {
        'text': u'Maximum taken date. Photos with an taken date less than or equal to this value will be returned. The date should be in the form of a mysql datetime.', u'optional': u'1', u'name': u'max_taken_date'
            }
            , {
        'text': u"Content Type setting:\r\n<ul>\r\n<li>1 for photos only.</li>\r\n<li>2 for screenshots only.</li>\r\n<li>3 for 'other' only.</li>\r\n<li>4 for photos and screenshots.</li>\r\n<li>5 for screenshots and 'other'.</li>\r\n<li>6 for photos and 'other'.</li>\r\n<li>7 for photos, screenshots, and 'other' (all).</li>\r\n</ul>", u'optional': u'1', u'name': u'content_type'
            }
            , {
        'text': u'Return photos only matching a certain privacy level. This only applies when making an authenticated call to view photos you own. Valid values are:\r\n<ul>\r\n<li>1 public photos</li>\r\n<li>2 private photos visible to friends</li>\r\n<li>3 private photos visible to family</li>\r\n<li>4 private photos visible to friends & family</li>\r\n<li>5 completely private photos</li>\r\n</ul>', u'optional': u'1', u'name': u'privacy_filter'
            }
            , {
        'text': u'A comma-delimited list of extra information to fetch for each returned record. Currently supported fields are: <code>description</code>, <code>license</code>, <code>date_upload</code>, <code>date_taken</code>, <code>owner_name</code>, <code>icon_server</code>, <code>original_format</code>, <code>last_update</code>, <code>geo</code>, <code>tags</code>, <code>machine_tags</code>, <code>o_dims</code>, <code>views</code>, <code>media</code>, <code>path_alias</code>, <code>url_sq</code>, <code>url_t</code>, <code>url_s</code>, <code>url_q</code>, <code>url_m</code>, <code>url_n</code>, <code>url_z</code>, <code>url_c</code>, <code>url_l</code>, <code>url_o</code>', u'optional': 1, u'name': u'extras'
            }
            , {
        'text': u'Number of photos to return per page. If this argument is omitted, it defaults to 100. The maximum allowed value is 500.', u'optional': 1, u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': 1, u'name': u'page'
            }
            ], u'description': u'Return photos from the given user\'s photostream. Only photos visible to the calling user will be returned. This method must be authenticated; to return public photos for a user, use <a href="/services/api/flickr.people.getPublicPhotos.html">flickr.people.getPublicPhotos</a>.', 'needslogin': True, u'name': u'flickr.people.getPhotos'
        }
        , u'flickr.reflection.getMethods': {
    u'errors': [{
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Returns a list of available flickr API methods.', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            ], 'needslogin': False, u'response': u'<methods>\r\n\t<method>flickr.blogs.getList</method>\r\n\t<method>flickr.blogs.postPhoto</method>\r\n\t<method>flickr.contacts.getList</method>\r\n\t<method>flickr.contacts.getPublicList</method>\r\n</methods>', u'name': u'flickr.reflection.getMethods'
        }
        , u'flickr.blogs.getServices': {
    u'errors': [{
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Return a list of Flickr supported blogging services', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            ], 'needslogin': False, u'response': u'<services>\r\n<service id="beta.blogger.com">Blogger</service>\r\n<service id="Typepad">Typepad</service>\r\n<service id="MovableType">Movable Type</service>\r\n<service id="LiveJournal">LiveJournal</service>\r\n<service id="MetaWeblogAPI">Wordpress</service>\r\n<service id="MetaWeblogAPI">MetaWeblogAPI</service>\r\n<service id="Manila">Manila</service>\r\n<service id="AtomAPI">AtomAPI</service>\r\n<service id="BloggerAPI">BloggerAPI</service>\r\n<service id="Vox">Vox</service>\r\n<service id="Twitter">Twitter</service>\r\n</services>', u'name': u'flickr.blogs.getServices'
        }
        , u'flickr.test.login': {
    u'errors': [{
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'A testing method which checks if the caller is logged in then returns their username.', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            ], 'needslogin': True, u'response': u'<user id="12037949754@N01">\r\n\t<username>Bees</username> \r\n</user>\r\n', u'name': u'flickr.test.login'
        }
        , u'flickr.places.placesForBoundingBox': {
    u'errors': [{
        'text': u'One or more required parameter is missing from the API call.', u'message': u'Required parameters missing', u'code': u'1'
            }
            , {
        'text': u'The bbox argument was incomplete or incorrectly formatted', u'message': u'Not a valid bbox', u'code': u'2'
            }
            , {
        'text': u'An invalid place type was included with your request.', u'message': u'Not a valid place type', u'code': u'3'
            }
            , {
        'text': u'The bounding box passed along with your request was too large for the request place type.', u'message': u'Bounding box exceeds maximum allowable size for place type', u'code': u'4'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Return all the locations of a matching place type for a bounding box.<br /><br />\r\n\r\nThe maximum allowable size of a bounding box (the distance between the SW and NE corners) is governed by the place type you are requesting. Allowable sizes are as follows:\r\n\r\n<ul>\r\n<li><strong>neighbourhood</strong>: 3km (1.8mi)</li>\r\n<li><strong>locality</strong>: 7km (4.3mi)</li>\r\n<li><strong>county</strong>: 50km (31mi)</li>\r\n<li><strong>region</strong>: 200km (124mi)</li>\r\n<li><strong>country</strong>: 500km (310mi)</li>\r\n<li><strong>continent</strong>: 1500km (932mi)</li>\r\n</ul>', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'A comma-delimited list of 4 values defining the Bounding Box of the area that will be searched. The 4 values represent the bottom-left corner of the box and the top-right corner, minimum_longitude, minimum_latitude, maximum_longitude, maximum_latitude.', u'optional': u'0', u'name': u'bbox'
            }
            , {
        'text': u'The name of place type to using as the starting point to search for places in a bounding box. Valid placetypes are:\r\n\r\n<ul>\r\n<li>neighbourhood</li>\r\n<li>locality</li>\r\n<li>county</li>\r\n<li>region</li>\r\n<li>country</li>\r\n<li>continent</li>\r\n</ul>\r\n<br />\r\n<span style="font-style:italic;">The "place_type" argument has been deprecated in favor of the "place_type_id" argument. It won\'t go away but it will not be added to new methods. A complete list of place type IDs is available using the <a href="http://www.flickr.com/services/api/flickr.places.getPlaceTypes.html">flickr.places.getPlaceTypes</a> method. (While optional, you must pass either a valid place type or place type ID.)</span>', u'optional': u'1', u'name': u'place_type'
            }
            , {
        'text': u'The numeric ID for a specific place type to cluster photos by. <br /><br />\r\n\r\nValid place type IDs are :\r\n\r\n<ul>\r\n<li><strong>22</strong>: neighbourhood</li>\r\n<li><strong>7</strong>: locality</li>\r\n<li><strong>8</strong>: region</li>\r\n<li><strong>12</strong>: country</li>\r\n<li><strong>29</strong>: continent</li>\r\n</ul>\r\n<br /><span style="font-style:italic;">(While optional, you must pass either a valid place type or place type ID.)</span>\r\n', u'optional': u'1', u'name': u'place_type_id'
            }
            , {
        'text': u'Perform a recursive place type search. For example, if you search for neighbourhoods in a given bounding box but there are no results the method will also query for localities and so on until one or more valid places are found.<br /<br /> \r\nRecursive searches do not change the bounding box size restrictions for the initial place type passed to the method.', u'optional': u'1', u'name': u'recursive'
            }
            ], 'needslogin': False, u'response': u'<places place_type="neighbourhood" total="21"\r\n   pages="1" page="1" \r\n   bbox="-122.42307100000001,37.773779,-122.381071,37.815779">\r\n   <place place_id=".aaSwYSbApnq6seyGw" woeid="23512025"\r\n      latitude="37.788" longitude="-122.412" \r\n      place_url="/United+States/California/San+Francisco/Downtown"\r\n      place_type="neighbourhood">\r\n      Downtown, San Francisco, CA, US, United States\r\n   </place>\r\n   <place place_id="3KymK1GbCZ41eBVBxg" woeid="28288707"\r\n      latitude="37.776" longitude="-122.417" \r\n      place_url="/United+States/California/San+Francisco/Civic+Center"\r\n      place_type="neighbourhood">\r\n      Civic Center, San Francisco, CA, US, United States\r\n   </place>\r\n   <place place_id="9xdhxY.bAptvBjHo" woeid="2379855"   \r\n      latitude="37.796" longitude="-122.407" \r\n      place_url="/United+States/California/San+Francisco/Chinatown"\r\n      place_type="neighbourhood">\r\n      Chinatown, San Francisco, CA, US, United States\r\n   </place>\r\n   <!-- and so on -->\r\n</places>', u'name': u'flickr.places.placesForBoundingBox'
        }
        , u'flickr.groups.leave': {
    'needssigning': True, u'requiredperms': 'delete', u'errors': [{
        'text': u"The group_id doesn't exist", u'message': u'Required arguments missing', u'code': u'1'
            }
            , {
        'text': u'The group by that ID does not exist', u'message': u'Group does not exist', u'code': u'2'
            }
            , {
        'text': u'The user is not a member of the group that was specified', u'message': u'Account is not in that group', u'code': u'3'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The NSID of the Group to leave', u'optional': u'0', u'name': u'group_id'
            }
            , {
        'text': u'Delete all photos by this user from the group', u'optional': u'1', u'name': u'delete_photos'
            }
            ], u'description': u'Leave a group.\r\n\r\n<br /><br />If the user is the only administrator left, and there are other members, the oldest member will be promoted to administrator.\r\n\r\n<br /><br />If the user is the last person in the group, the group will be deleted.', 'needslogin': True, u'name': u'flickr.groups.leave'
        }
        , u'flickr.galleries.getInfo': {
    u'errors': [{
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'', 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The gallery ID you are requesting information for.', u'optional': u'0', u'name': u'gallery_id'
            }
            ], 'needslogin': False, u'response': u'<gallery id="6065-72157617483228192" url="http://www.flickr.com/photos/straup/galleries/72157617483228192" \r\nowner="35034348999@N01" \r\n         primary_photo_id="292882708" date_create="1241028772" date_update="1270111667" count_photos="17"\r\n count_videos="0" primary_photo_server="112" primary_photo_farm="1" primary_photo_secret="7f29861bc4">\r\n\t<title>Cat Pictures I\'ve Sent To Kevin Collins</title>\r\n\t<description />\r\n</gallery>', u'name': u'flickr.galleries.getInfo'
        }
        , u'flickr.photosets.reorderPhotos': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The photoset id passed was not a valid photoset id or did not belong to the calling user.', u'message': u'Photoset not found', u'code': u'1'
            }
            , {
        'text': u'One or more of the photo ids passed was not a valid photo id or does not belong to the calling user.', u'message': u'Photo not found', u'code': u'2'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photoset to reorder. The photoset must belong to the calling user.', u'optional': u'0', u'name': u'photoset_id'
            }
            , {
        'text': u'Ordered, comma-delimited list of photo ids. Photos that are not in the list will keep their original order', u'optional': u'0', u'name': u'photo_ids'
            }
            ], u'description': u'', 'needslogin': True, u'name': u'flickr.photosets.reorderPhotos'
        }
        , u'flickr.stats.getPhotoStats': {
    u'errors': [{
        'text': u'The user you have requested stats has not enabled stats on their account.', u'message': u'User does not have stats', u'code': u'1'
            }
            , {
        'text': u'No stats are available for the date requested. Flickr only keeps stats data for the last 28 days.', u'message': u'No stats for that date', u'code': u'2'
            }
            , {
        'text': u'The date provided could not be parsed', u'message': u'Invalid date', u'code': u'3'
            }
            , {
        'text': u'The photo id was either invalid or was for a photo not owned by the calling user.', u'message': u'Photo not found', u'code': u'4'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Get the number of views, comments and favorites on a photo for a given date.', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'Stats will be returned for this date. This should be in either be in YYYY-MM-DD or unix timestamp format.\r\n\r\nA day according to Flickr Stats starts at midnight GMT for all users, and timestamps will automatically be rounded down to the start of the day.', u'optional': u'0', u'name': u'date'
            }
            , {
        'text': u'The id of the photo to get stats for.', u'optional': u'0', u'name': u'photo_id'
            }
            ], 'needslogin': True, u'response': u'<stats views="24" comments="4" favorites="1"/>', u'name': u'flickr.stats.getPhotoStats'
        }
        , u'flickr.prefs.getHidden': {
    u'errors': [{
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Returns the default hidden preference for the user.', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            ], 'needslogin': True, u'response': u'<rsp stat="ok">\r\n<person nsid="12037949754@N01" hidden="1" />\r\n</rsp>', u'name': u'flickr.prefs.getHidden'
        }
        , u'flickr.activity.userComments': {
    u'errors': [{
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u'Returns a list of recent activity on photos commented on by the calling user. <b>Do not poll this method more than once an hour</b>.', 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'Number of items to return per page. If this argument is omitted, it defaults to 10. The maximum allowed value is 50.', u'optional': u'1', u'name': u'per_page'
            }
            , {
        'text': u'The page of results to return. If this argument is omitted, it defaults to 1.', u'optional': u'1', u'name': u'page'
            }
            ], 'needslogin': True, u'response': u'<items>\r\n\t<item type="photoset" id="395" owner="12037949754@N01" \r\n\t\tprimary="6521" secret="5a3cc65d72" server="2" \r\n\t\tcomments="1" views="33" photos="7" more="0">\r\n\t\t<title>A set of photos</title>\r\n\t\t<activity>\r\n\t\t\t<event type="comment"\r\n\t\t\tuser="12037949754@N01" username="Bees"\r\n\t\t\tdateadded="1144086424">yay</event>\r\n\t\t</activity>\r\n\t</item>\r\n\r\n\t<item type="photo" id="10289" owner="12037949754@N01"\r\n\t\tsecret="34da0d3891" server="2" comments="1"\r\n\t\tnotes="0" views="47" faves="0" more="0">\r\n\t\t<title>A photo</title>\r\n\t\t<activity>\r\n\t\t\t<event type="comment"\r\n\t\t\tuser="12037949754@N01" username="Bees"\r\n\t\t\tdateadded="1133806604">test</event>\r\n\t\t\t<event type="note"\r\n\t\t\tuser="12037949754@N01" username="Bees"\r\n\t\t\tdateadded="1118785229">nice</event>\r\n\t\t</activity>\r\n\t</item>\r\n</items>', u'name': u'flickr.activity.userComments'
        }
        , u'flickr.photos.people.editCoords': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The NSID passed was not a valid user id.', u'message': u'Person not found', u'code': u'1'
            }
            , {
        'text': u'The photo id passed was not a valid photo id.', u'message': u'Photo not found', u'code': u'2'
            }
            , {
        'text': u'The calling user did not originally add this person to the photo, and is not the person in question.', u'message': u'User cannot edit that person in that photo', u'code': u'3'
            }
            , {
        'text': u'Not all of the co-ordinate parameters (person_x, person_y, person_w, person_h) were passed with valid values.', u'message': u'Some co-ordinate paramters were blank', u'code': u'4'
            }
            , {
        'text': u'None of the co-ordinate parameters were valid.', u'message': u'No co-ordinates given', u'code': u'5'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the photo to edit a person in.', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u'The NSID of the person to edit in a photo.', u'optional': u'0', u'name': u'user_id'
            }
            , {
        'text': u'The left-most pixel co-ordinate of the box around the person.', u'optional': u'0', u'name': u'person_x'
            }
            , {
        'text': u'The top-most pixel co-ordinate of the box around the person.', u'optional': u'0', u'name': u'person_y'
            }
            , {
        'text': u'The width (in pixels) of the box around the person.', u'optional': u'0', u'name': u'person_w'
            }
            , {
        'text': u'The height (in pixels) of the box around the person.', u'optional': u'0', u'name': u'person_h'
            }
            , {
        'text': u"An email address for an 'invited' person in a photo", u'optional': u'1', u'name': u'email'
            }
            ], u'description': u'Edit the bounding box of an existing person on a photo.', 'needslogin': True, u'name': u'flickr.photos.people.editCoords'
        }
        , u'flickr.photos.comments.editComment': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The requested comment is against a photo which no longer exists.', u'message': u'Photo not found.', u'code': u'1'
            }
            , {
        'text': u'The comment id passed was not a valid comment id', u'message': u'Comment not found.', u'code': u'2'
            }
            , {
        'text': u'Comment text can not be blank', u'message': u'Blank comment.', u'code': u'8'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the comment to edit.', u'optional': u'0', u'name': u'comment_id'
            }
            , {
        'text': u'Update the comment to this text.', u'optional': u'0', u'name': u'comment_text'
            }
            ], u'description': u'Edit the text of a comment as the currently authenticated user.', 'needslogin': True, u'name': u'flickr.photos.comments.editComment'
        }
        , u'flickr.urls.getGroup': {
    u'errors': [{
        'text': u'The NSID specified was not a valid group.', u'message': u'Group not found', u'code': u'1'
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u"Returns the url to a group's page.", 'needssigning': False, u'requiredperms': 'none', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The NSID of the group to fetch the url for.', u'optional': u'0', u'name': u'group_id'
            }
            ], 'needslogin': False, u'response': u'<group nsid="48508120860@N01" url="http://www.flickr.com/groups/test1/" /> ', u'name': u'flickr.urls.getGroup'
        }
        , u'flickr.stats.getPhotostreamStats': {
    u'errors': [{
        'text': u'The user you have requested stats has not enabled stats on their account.', u'message': u'User does not have stats', u'code': u'1'
            }
            , {
        'text': u'No stats are available for the date requested. Flickr only keeps stats data for the last 28 days.', u'message': u'No stats for that date', u'code': u'2'
            }
            , {
        'text': u'The date provided could not be parsed', u'message': u'Invalid date', u'code': u'3'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'description': u"Get the number of views on a user's photostream for a given date.", 'needssigning': True, u'requiredperms': 'read', u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'Stats will be returned for this date. This should be in either be in YYYY-MM-DD or unix timestamp format.\r\n\r\nA day according to Flickr Stats starts at midnight GMT for all users, and timestamps will automatically be rounded down to the start of the day.', u'optional': u'0', u'name': u'date'
            }
            ], 'needslogin': True, u'response': u'<stats views="24" />', u'name': u'flickr.stats.getPhotostreamStats'
        }
        , u'flickr.blogs.postPhoto': {
    'needssigning': True, u'requiredperms': 'write', u'errors': [{
        'text': u'The blog id was not the id of a blog belonging to the calling user', u'message': u'Blog not found', u'code': u'1'
            }
            , {
        'text': u'The photo id was not the id of a public photo', u'message': u'Photo not found', u'code': u'2'
            }
            , {
        'text': u'A password is not stored for the blog and one was not passed with the request', u'message': u'Password needed', u'code': u'3'
            }
            , {
        'text': u'The blog posting failed (a blogging API failure of some sort)', u'message': u'Blog post failed', u'code': u'4'
            }
            , {
        'text': u'The passed signature was invalid.', u'message': u'Invalid signature', u'code': 96
            }
            , {
        'text': u'The call required signing but no signature was sent.', u'message': u'Missing signature', u'code': 97
            }
            , {
        'text': u'The login details or auth token passed were invalid.', u'message': u'Login failed / Invalid auth token', u'code': 98
            }
            , {
        'text': u'The method requires user authentication but the user was not logged in, or the authenticated method call did not have the required permissions.', u'message': u'User not logged in / Insufficient permissions', u'code': 99
            }
            , {
        'text': u'The API key passed was not valid or has expired.', u'message': u'Invalid API Key', u'code': 100
            }
            , {
        'text': u'The requested service is temporarily unavailable.', u'message': u'Service currently unavailable', u'code': 105
            }
            , {
        'text': u'The requested response format was not found.', u'message': u'Format "xxx" not found', u'code': 111
            }
            , {
        'text': u'The requested method was not found.', u'message': u'Method "xxx" not found', u'code': 112
            }
            , {
        'text': u'The SOAP envelope send in the request could not be parsed.', u'message': u'Invalid SOAP envelope', u'code': 114
            }
            , {
        'text': u'The XML-RPC request document could not be parsed.', u'message': u'Invalid XML-RPC Method Call', u'code': 115
            }
            , {
        'text': u'One or more arguments contained a URL that has been used for abuse on Flickr.', u'message': u'Bad URL found', u'code': 116
            }
            ], u'arguments': [{
        'text': u'Your API application key. <a href="/services/api/misc.api_keys.html">See here</a> for more details.', u'optional': 0, u'name': u'api_key'
            }
            , {
        'text': u'The id of the blog to post to.', u'optional': u'1', u'name': u'blog_id'
            }
            , {
        'text': u'The id of the photo to blog', u'optional': u'0', u'name': u'photo_id'
            }
            , {
        'text': u'The blog post title', u'optional': u'0', u'name': u'title'
            }
            , {
        'text': u'The blog post body', u'optional': u'0', u'name': u'description'
            }
            , {
        'text': u'The password for the blog (used when the blog does not have a stored password).', u'optional': u'1', u'name': u'blog_password'
            }
            , {
        'text': u"A Flickr supported blogging service.  Instead of passing a blog id you can pass a service id and we'll post to the first blog of that service we find.", u'optional': u'1', u'name': u'service'
            }
            ], u'description': u'', 'needslogin': True, u'name': u'flickr.blogs.postPhoto'
        }
        
    }
    

########NEW FILE########
__FILENAME__ = method_call
"""
    method_call module.

    This module is used to perform the calls to the REST interface.

    Author: Alexis Mignon (c)
    e-mail: alexis.mignon@gmail.com
    Date: 06/08/2011

"""
import urllib2
import urllib
import hashlib
import json

from . import keys
from .flickrerrors import FlickrError, FlickrAPIError
from .cache import SimpleCache

REST_URL = "https://api.flickr.com/services/rest/"

CACHE = None


def enable_cache(cache_object=None):
    """ enable caching
    Parameters:
    -----------
    cache_object: object, optional
        A Django compliant cache object. If None (default), a SimpleCache
        object is used.
    """
    global CACHE
    CACHE = cache_object or SimpleCache()


def disable_cache():
    """Disable cachine capabilities
    """
    global CACHE
    CACHE = None


def send_request(url, data):
    """send a http request.
    """
    req = urllib2.Request(url, data)
    try:
        return urllib2.urlopen(req).read()
    except urllib2.HTTPError, e:
        raise FlickrError(e.read().split('&')[0])


def call_api(api_key=None, api_secret=None, auth_handler=None,
             needssigning=False, request_url=REST_URL, raw=False, **args):
    """
        Performs the calls to the Flickr REST interface.

    Parameters:
        api_key:
            The API_KEY to use. If none is given and a auth_handler is used
            the key stored in the auth_handler is used, otherwise, the values
            stored in the `flickr_keys` module are used.
        api_secret:
            The API_SECRET to use. If none is given and a auth_handler is used
            the key stored in the auth_handler is used, otherwise, the values
            stored in the `flickr_keys` module are used.
        auth_handler:
            The authentication handler object to use to perform authentication.
        request_url:
            The url to the rest interface to use by default the url in REST_URL
            is used.
        raw:
            if True the default xml response from the server is returned. If
            False (default) a dictionnary built from the JSON answer is
            returned.
        args:
            the arguments to pass to the method.
    """

    if not api_key:
        if auth_handler is not None:
            api_key = auth_handler.key
        else:
            api_key = keys.API_KEY
    if not api_secret:
        if auth_handler is not None:
            api_secret = auth_handler.secret
        else:
            api_secret = keys.API_SECRET

    if not api_key or not api_secret:
        raise FlickrError("The Flickr API keys have not been set")

    clean_args(args)
    args["api_key"] = api_key
    if not raw:
        args["format"] = 'json'
        args["nojsoncallback"] = 1

    if auth_handler is None:
        if needssigning:
            query_elements = args.items()
            query_elements.sort()
            sig = keys.API_SECRET + \
                  ["".join(["".join(e) for e in query_elements])]
            m = hashlib.md5()
            m.update(sig)
            api_sig = m.digest()
            args["api_sig"] = api_sig
        data = urllib.urlencode(args)
    else:
        data = auth_handler.complete_parameters(
             url=request_url, params=args
        ).to_postdata()

    if CACHE is None:
        resp = send_request(request_url, data)
    else:
        resp = CACHE.get(data) or send_request(request_url, data)
        if data not in CACHE:
            CACHE.set(data, resp)

    if raw:
        return resp

    try:
        resp = json.loads(resp)
    except ValueError, e:
        print resp
        raise e

    if resp["stat"] != "ok":
        raise FlickrAPIError(resp["code"], resp["message"])

    resp = clean_content(resp)

    return resp


def clean_content(d):
    """
    Cleans out recursively the keys comming from the JSON
    dictionnary.

    Namely: "_content" keys are replaces with their associated
        values if they are the only key of the dictionnary. Other
        wise they are replaces by a "text" key with the same value.
    """
    if isinstance(d, dict):
        d_clean = {}
        if len(d) == 1 and "_content" in d:
            return clean_content(d["_content"])
        for k, v in d.iteritems():
            if k == "_content":
                k = "text"
            d_clean[k] = clean_content(v)
        return d_clean
    elif isinstance(d, list):
        return [clean_content(i) for i in d]
    else:
        return d


def clean_args(args):
    """
        Reformat the arguments.
    """
    for k, v in args.items():
        if isinstance(v, bool):
            args[k] = int(v)

########NEW FILE########
__FILENAME__ = multipart
"""
    Deals with multipart POST requests.

    The code is adapted from the recipe found at :
    http://code.activestate.com/recipes/146306/
    No author name was given.

    Author : Alexis Mignon (c)
    email  : alexis.mignon@gmail.Com
    Date   : 06/08/2011

"""

import httplib
import mimetypes
import urlparse


def posturl(url, fields, files):
    urlparts = urlparse.urlsplit(url)
    return post_multipart(urlparts[1], urlparts[2], fields, files)


def post_multipart(host, selector, fields, files):
    """
    Post fields and files to an http host as multipart/form-data.
    fields is a sequence of (name, value) elements for regular form fields.
    files is a sequence of (name, filename, value) elements for data to be
    uploaded as files.

    Return the server's response page.
    """
    content_type, body = encode_multipart_formdata(fields, files)
    h = httplib.HTTPSConnection(host)
    headers = {"Content-Type": content_type, 'content-length': str(len(body))}
    h.request("POST", selector, headers=headers)
    h.send(body)
    r = h.getresponse()
    data = r.read()
    h.close()
    return r, data


def encode_multipart_formdata(fields, files):
    """
    fields is a sequence of (name, value) elements for regular form fields.
    files is a sequence of (name, filename, value) elements for data to be
    uploaded as files.

    Return (content_type, body) ready for httplib.HTTP instance
    """
    BOUNDARY = '----------ThIs_Is_tHe_bouNdaRY_$'
    CRLF = '\r\n'
    L = []
    for (key, value) in fields:
        L.append('--' + BOUNDARY)
        L.append('Content-Disposition: form-data; name="%s"' % key)
        L.append('')
        L.append(value)
    for (key, filename, value) in files:
        filename = filename.encode("utf8")
        L.append('--' + BOUNDARY)
        L.append(
            'Content-Disposition: form-data; name="%s"; filename="%s"' % (
                key, filename
            )
        )
        L.append('Content-Type: %s' % get_content_type(filename))
        L.append('')
        L.append(value)
    L.append('--' + BOUNDARY + '--')
    L.append('')
    body = CRLF.join(L)
    content_type = 'multipart/form-data; boundary=%s' % BOUNDARY
    return content_type, body


def get_content_type(filename):
    return mimetypes.guess_type(filename)[0] or 'application/octet-stream'

########NEW FILE########
__FILENAME__ = objects
# -*- encoding: utf8 -*-
"""
    Object Oriented implementation of Flickr API.

    Important notes:
    - For consistency, the naming of methods might differ from the name
      in the official API. Please check the method "docstring" to know
      what is the implemented method.

    - For methods which expect an object "id", either the 'id' string
      or the object itself can be used as argument. Similar consideration
      holds for lists of id's.

      For instance if "photo_id" is expected you can give call the function
      with named argument "photo=PhotoObject" or with the id string
      "photo_id=id_string".

    Author: Alexis Mignon (c)
    email: alexis.mignon_at_gmail.com
    Date: 05/08/2011
"""
import method_call
from  flickrerrors import FlickrError
from reflection import caller, static_caller, FlickrAutoDoc
import urllib2
from UserList import UserList
import auth

try:
    import Image
    import cStringIO
except ImportError:
    pass


def dict_converter(keys, func):
    def convert(dict_):
        for k in keys:
            try:
                dict_[k] = func(dict_[k])
            except KeyError:
                pass
    return convert


class FlickrObject(object):
    """
        Base Object for Flickr API Objects.
        Flickr Objects are dynamically created from the
        named arguments given to the constructor.
    """

    __converters__ = []  # some functions used to convert some result field
    __display__ = []  # The attribute to display when the object is converted
                      # to a string
    __metaclass__ = FlickrAutoDoc

    def __init__(self, **params):
        params["loaded"] = False
        self._set_properties(**params)

    def _set_properties(self, **params):
        for c in self.__class__.__converters__:
            c(params)
        self.__dict__.update(params)

    def setToken(self, filename=None, token=None, token_key=None,
                 token_secret=None):
        """
            Set the authentication token to use with the object.
        """
        if token is None:
            token = auth.token_factory(filename=filename, token_key=token_key,
                                       token_secret=token_secret)
        self.__dict__["token"] = token

    def getToken(self):
        """
            Get the authentication token is any.
        """
        return self.__dict__.get("token", None)

    def __getattr__(self, name):
        if name == 'id' and name not in self.__dict__:
            raise AttributeError(
              "'%s' object has no attribute '%s'" % (
                    self.__class__.__name__, name)
              )
        if name not in self.__dict__:
            if not self.loaded:
                self.load()
        try:
            return self.__dict__[name]
        except KeyError:
            raise AttributeError(
                "'%s' object has no attribute '%s'" % (
                     self.__class__.__name__, name
                    )
                )

    def __setattr__(self, name, values):
        raise FlickrError("Readonly attribute")

    def get(self, key, *args, **kwargs):
        return self.__dict__.get(key, *args, **kwargs)

    def __getitem__(self, key):
        return self.__dict__[key]

    def __setitem__(self, key, value):
        raise FlickrError("Read-only attribute")

    def __str__(self):
        vals = []
        for k in self.__class__.__display__:
            val_found = False
            try:
                value = self.__dict__[k]
                val_found = True
            except KeyError:
                self.load()
                try:
                    value = self.__dict__[k]
                    val_found = True
                except KeyError:
                    pass
            if not val_found:
                continue
            if isinstance(value, unicode):
                value = value.encode("utf8")
            if isinstance(value, str):
                value = "'%s'" % value
            else:
                value = str(value)
            if len(value) > 20:
                value = value[:20] + "..."
            vals.append("%s=%s" % (k, value))
        return "%s(%s)" % (self.__class__.__name__, ", ".join(vals))

    def __repr__(self):
        return str(self)

    def getInfo(self):
        """
            Returns object information as a dictionnary.
            Should be overriden.
        """
        return {}

    def load(self):
        props = self.getInfo()
        self.__dict__["loaded"] = True
        self._set_properties(**props)


class FlickrList(UserList):
    def __init__(self, data=[], info=None):
        UserList.__init__(self, data)
        self.info = info

    def __str__(self):
        return '%s;%s' % (str(self.data), str(self.info))

    def __repr__(self):
        return '%s;%s' % (repr(self.data), repr(self.info))


class Activity(FlickrObject):
    @static_caller("flickr.activity.userPhotos")
    def userPhotos(**args):
        return args, _extract_activity_list

    @static_caller("flickr.activity.userComments")
    def userComments(**args):
        return args, _extract_activity_list


class Blog(FlickrObject):
    __display__ = ["id", "name"]
    __converters__ = [
        dict_converter(["needspassword"], bool),
    ]
    __self_name__ = "blog_id"

    @caller("flickr.blogs.postPhoto")
    def postPhoto(self, **args):
        return _format_id("photo", args), lambda r: None


class BlogService(FlickrObject):
    __display__ = ["id", "text"]
    __self_name__ = "service"

    @caller("flickr.blogs.getList")
    def getList(self, **args):
        try:
            args["service"] = args["service"].id
        except (KeyError, AttributeError):
            pass

        def format_result(r, token=None):
            return [Blog(token=token, **b)
                       for b in _check_list(r["blogs"]["blog"])]

        return args, format_result

    @caller("flickr.blogs.postPhoto")
    def postPhoto(self, **args):
        return _format_id(args), _none

    @static_caller("flickr.blogs.getServices")
    def getServices():
        return ({},
                lambda r: [BlogService(**s)
                          for s in _check_list(r["services"]["service"])]
               )


class Camera(FlickrObject):
    __display__ = ["name"]
    __self_name__ = "camera"

    class Brand(FlickrObject):
        __display__ = ["name"]
        __self_name__ = "brand"

        @static_caller("flickr.cameras.getBrands")
        def getList():
            return ({},
                    lambda r: [Camera.Brand(**b) for b in r["brands"]["brand"]]
            )

        @caller("flickr.cameras.getBrandModels")
        def getModels(self):
            return ({},
                   lambda r: [Camera(**m) for m in r["cameras"]["camera"]]
            )


class Collection(FlickrObject):
    __display__ = ["id", "title"]
    __self_name__ = "collection_id"

    @caller("flickr.collections.getInfo")
    def getInfo(self, **args):
        def format_result(r):
            collection = r["collection"]
            icon_photos = _check_list(collection["iconphotos"]["photo"])
            photos = []
            for p in photos:
                p["owner"] = Person(p["owner"])
                photos.append(Photo(**p))
            collection["iconphotos"] = photos
            return collection
        return args, format_result

    @caller("flickr.stats.getCollectionStats")
    def getStats(self, date, **args):
        args["date"] = date
        return args, lambda r: int(r["stats"]["views"])

    @caller("flickr.collections.getTree")
    def getTree(**args):
        def format_result(r, token=None):
            collections = _check_list(r["collections"])
            collections_ = []
            for c in collections:
                sets = _check_list(c.pop("set"))
                sets_ = [Photoset(token=token, **s) for s in sets]
                collections_.append(Collection(token=token, sets=sets_, **c))
            return collections_
        return _format_id("user", args), format_result


class CommonInstitution(FlickrObject):
    __display__ = ["id", "name"]

    @static_caller("flickr.commons.getInstitutions")
    def getInstitutions():
        def format_result(r):
            institutions = _check_list(r["institutions"]["institution"])
            institutions_ = []
            for i in institutions:
                urls = _check_list(i['urls']['url'])
                urls_ = []
                for u in urls:
                    u["url"] = u.pop("text")
                    urls_.append(CommonInstitutionUrl(**u))
                i["urls"] = urls_
                institutions_.append(CommonInstitution(id=i["nsid"], **i))
            return institutions_
        return {}, format_result


class CommonInstitutionUrl(FlickrObject):
    pass


class Contact(FlickrObject):
    @static_caller("flickr.contacts.getList")
    def getList(self, **args):
        def format_result(r):
            info = r["contacts"]
            contacts = [Person(id=c["nsid"], **c)
                         for c in _check_list(info["contact"])]
            return FlickrList(contacts, Info(**info))
        return args, format_result

    @static_caller("flickr.contacts.getListRecentlyUploaded")
    def getListRecentlyUploaded(self, **args):
        def format_result(r):
            info = r["contacts"]
            contacts = [Person(id=c["nsid"], **c)
                         for c in _check_list(info["contact"])]
            return FlickrList(contacts, Info(**info))
        return args, format_result

    @static_caller("flickr.contacts.getTaggingSuggestions")
    def getTaggingSuggestions(self, **args):
        def format_result(r):
            info = r["contacts"]
            contacts = [Person(id=c["nsid"], **c)
                         for c in _check_list(info["contact"])]
            return FlickrList(contacts, Info(**info))
        return args, format_result


class Gallery(FlickrObject):
    __display__ = ["id", "title"]
    __converters__ = [
        dict_converter(["date_create", "date_update", "count_photos",
                        "count_videos"], int),
    ]
    __self_name__ = "gallery_id"

    @caller("flickr.galleries.addPhoto")
    def addPhoto(self, **args):
        return _format_id("photo", args), _none

    @static_caller("flickr.galleries.create")
    def create(**args):
        return _format_id("primary_photo"), lambda r: Gallery(**r["gallery"])

    @caller("flickr.galleries.editMeta")
    def editMedia(self, **args):
        return args, _none

    @caller("flickr.galleries.editPhoto")
    def editPhoto(self, **args):
        return _format_id("photo", args), _none

    @caller("flickr.galleries.editPhotos")
    def editPhotos(self, **args):
        if "photos" in args:
            args["photo_ids"] = [p.id for p in args.pop("photos")]
        photo_ids = args["photo_ids"]
        if isinstance(photo_ids, list):
            args["photo_ids"] = ", ".join(photo_ids)
        return _format_id("primary_photo", args), _none

    @static_caller("flickr.urls.lookupGallery")
    def getByUrl(url):
        def format_result(r):
            gallery = r["gallery"]
            gallery["owner"] = Person(id=gallery["owner"])
            return Gallery(**gallery)
        return {'url': url}, format_result

    @caller("flickr.galleries.getInfo")
    def getInfo(self):
        def format_result(r, token=None):
            gallery = r["gallery"]
            gallery["owner"] = Person(gallery["owner"])
            pp_id = gallery.pop("primary_photo_id")
            pp_secret = gallery.pop("primary_photo_secret")
            pp_farm = gallery.pop("primary_photo_farm")
            pp_server = gallery.pop("primary_photo_server")
            gallery["primary_photo"] = Photo(id=pp_id, secret=pp_secret,
                                             server=pp_server, farm=pp_farm,
                                             token=token)
            return gallery
        return {}, format_result

    @caller("flickr.galleries.getPhotos")
    def getPhotos(self, **args):
        return _format_extras(args), _extract_photo_list


class Category(FlickrObject):
    __display__ = ["id", "name"]


class Info(FlickrObject):
    __converters__ = [
        dict_converter(["page", "perpage", "pages", "total", "count"], int)

    ]
    __display__ = ["page", "perpage", "pages", "total", "count"]
    pass


class Group(FlickrObject):
    __converters__ = [
        dict_converter(["members", "privacy"], int),
        dict_converter(["admin", "eighteenplus", "invistation_only"], bool)
    ]
    __display__ = ["id", "name"]
    __self_name__ = "group_id"

    class Topic(FlickrObject):
        __display__ = ["id", "subject"]
        __self_name__ = "topic_id"

        class Reply(FlickrObject):
            __display__ = ["id"]
            __self_name__ = "reply_id"

            def getToken(self):
                return self.topic.getToken()

            @staticmethod
            def _format_reply(reply):
                author = {
                    'id': reply.pop("author"),
                    'role': reply.pop("role"),
                    'is_pro': bool(reply.pop("is_pro")),
                }
                reply["author"] = Person(**author)
                return reply

            @caller("flickr.groups.discuss.replies.getInfo")
            def getInfo(self, **args):
                return args, lambda r: self._format_reply(r["reply"])

            @caller("flickr.groups.discuss.replies.delete")
            def delete(self, **args):
                args["topic_id"] = self.topic.id

        def getToken(self):
            return self.group.getToken()

        @caller("flickr.groups.discuss.replies.add")
        def addReply(self, **args):
            return args, _none

        @staticmethod
        def _format_topic(topic):
            """ reformat a topic dict
            """

            author = {
                'id': topic.pop("author"),
                'is_pro': bool(topic.pop('is_pro')),
                'role': topic.pop("role"),
            }
            topic["author"] = Person(**author)
            return topic

        @caller("flickr.groups.discuss.topics.getInfo")
        def getInfo(self, **args):
            def format_result(r):
                return self._format_topic(r["topic"])
            return args, format_result

        @caller("flickr.groups.discuss.replies.getList")
        def getReplies(self, **args):
            def format_result(r):
                info = r["replies"]
                return FlickrList(
                    [Group.Topic.Reply(topic=self,
                                       **Group.Topic.Reply._format_reply(rep))
                            for rep in info.pop("reply", [])],
                     Info(**info)
                )
            return args, format_result

        @caller("flickr.groups.discuss.replies.delete")
        def delete(self, **args):
            args["topic_id"] = self.topic.id
            return args, _none

        @caller("flickr.groups.discuss.replies.edit")
        def edit(self, **args):
            args["topic_id"] = self.topic.id
            return args, _none

    @caller("flickr.groups.discuss.topics.add")
    def addDiscussTopic(**args):
        return args, _none

    @static_caller("flickr.groups.browse")
    def browse(**args):
        def format_result(r, token):
            cat = r["category"]
            subcats = [Category(**c) for c in _check_list(cat.pop("subcats"))]
            groups = [Group(id=g["nsid"], **g)
                       for g in _check_list(cat.pop("group"))]
            return Category(id=args["cat_id"], subcats=subcats, groups=groups,
                            **cat)
        return _format_id("cat", args), format_result

    @caller("flickr.groups.getInfo")
    def getInfo(self, **args):
        return args, lambda r: r["group"]

    @caller("flickr.urls.getGroup")
    def getUrl(self, **args):
        return args, lambda r: r["group"]["url"]

    @static_caller("flickr.urls.lookupGroup")
    def getByUrl(url, **args):
        args["url"] = url

        def format_result(r):
            group = r["group"]
            group["name"] = group.pop("groupname")
            return Group(**group)
        return args, format_result

    @static_caller("flickr.groups.search")
    def search(**args):
        def format_result(r, token):
            info = r["groups"]
            groups = [Group(id=g["nsid"], **g) for g in info.pop("group")]
            return FlickrList(groups, Info(**info))
        return args, format_result

    @caller("flickr.groups.members.getList")
    def getMembers(self, **args):
        try:
            membertypes = args["membertypes"]
            if isinstance(membertypes, list):
                args["membertypes"] = ", ".join([str(i) for i in membertypes])
        except KeyError:
            pass

        def format_result(r):
            info = r["members"]
            return FlickrList(
                [Person(**p) for p in _check_list(info.pop("member"))],
                 Info(**info)
            )
        return args, format_result

    @caller("flickr.groups.pools.add")
    def addPhoto(self, **args):
        return _format_id("photo", args), _none

    @caller("flickr.groups.pools.getContext")
    def getPoolContext(self, **args):
        return (_format_id("photo", args),
                lambda r: (Photo(**r["prevphoto"]), Photo(r["nextphoto"]))
        )

    @caller("flickr.groups.discuss.topics.getList")
    def getDiscussTopics(self, **args):
        def format_result(r):
            info = r["topics"]
            return FlickrList(
                [Group.Topic(group=self, **Group.Topic._format_topic(t))
                    for t in info.pop("topic", [])],
                Info(**info)
            )
        return args, format_result

    @static_caller("flickr.groups.pools.getGroups")
    def getGroups(**args):
        def format_result(r, token):
            info = r["groups"]
            return FlickrList(
                [Group(token=token, **g) for g in info.pop("group", [])],
                 Info(**info)
            )
        return args, format_result

    @static_caller("flickr.people.getGroups")
    def getMemberGroups(**args):
        def format_result(r, token):
            info = r["groups"]
            return FlickrList(
                [Group(token=token, **g) for g in info.pop("group", [])],
                 Info(**info)
            )
        return args, format_result

    @caller("flickr.groups.pools.getPhotos")
    def getPhotos(self, **args):
        return _format_extras(args), _extract_photo_list

    @caller("flickr.groups.pools.remove")
    def removePhoto(self, **args):
        return _format_id("photo", args), _none

    @caller("flickr.groups.join")
    def join(self, **args):
        return args, _none

    @caller("flickr.groups.joinRequest")
    def joinRequest(self, **args):
        return args, _none

    @caller("flickr.groups.leave")
    def leave(self, **args):
        return args, _none


class License(FlickrObject):
    __display__ = ["id", "name"]
    __self_name__ = "license_id"

    @static_caller("flickr.photos.licenses.getInfo")
    def getList():
        def format_result(r):
            licenses = r["licenses"]["license"]
            if not isinstance(licenses, list):
                licenses = [licenses]
            return [License(**l) for l in licenses]
        return {}, format_result


class Location(FlickrObject):
    __display__ = ["latitude", "longitude", "accuracy"]
    __converters__ = [
        dict_converter(["latitude", "longitude"], float),
        dict_converter(["accuracy"], int),
    ]


class MachineTag(FlickrObject):

    class Namespace(FlickrObject):
        __display__ = ["text", "usage", "predicate"]

    class Pair(FlickrObject):
        __display__ = ["namespace", "text", "usage", "predicate"]

    class Predicate(FlickrObject):
        __display__ = ["usage", "text", "namespaces"]

    class Value(FlickrObject):
        __display__ = ["usage", "namespace", "predicate", "text"]

    @static_caller("flickr.machinetags.getNamespaces")
    def getNamespaces(**args):
        def format_result(r):
            info = r["namespaces"]
            return FlickrList(
                [MachineTag.Namespace(**ns)
                    for ns in _check_list(info.pop("namespace"))],
                Info(info)
            )
        return args, format_result

    @static_caller("flickr.machinetags.getPairs")
    def getPairs(**args):
        def format_result(r):
            info = r["pairs"]
            return FlickrList(
                [MachineTag.Pair(**p) for p in _check_list(info.pop("pair"))],
                 Info(info)
            )
        return args, format_result

    @static_caller("flickr.machinetags.getPredicates")
    def getPredicates(**args):
        def format_result(r):
            info = r["predicates"]
            return FlickrList(
                [MachineTag.Predicate(**p)
                    for p in _check_list(info.pop("predicate"))],
                Info(info)
            )
        return args, format_result

    @static_caller("flickr.machinetags.getRecentValues")
    def getRecentValues(**args):
        def format_result(r):
            info = r["values"]
            return FlickrList(
                [MachineTag.Value(**v)
                    for v in _check_list(info.pop("value"))],
                Info(info)
            )
        return args, format_result

    @static_caller("flickr.machinetags.getValues")
    def getValues(**args):
        def format_result(r):
            info = r["values"]
            return FlickrList(
                [MachineTag.Value(**v)
                    for v in _check_list(info.pop("value"))],
                Info(info)
            )
        return args, format_result


class Panda(FlickrObject):
    __display__ = ["name"]
    __self_name__ = 'panda_name'

    @static_caller("flickr.panda.getList")
    def getList():
        return (
            {},
            lambda r: [Panda(name=p, id=p) for p in r["pandas"]["panda"]]
        )

    @caller("flickr.panda.getPhotos")
    def getPhotos(self, **args):
        return _format_extras(args), _extract_photo_list


class Person(FlickrObject):
    __converters__ = [
        dict_converter(["ispro"], bool),
    ]
    __display__ = ["id", "username"]
    __self_name__ = "user_id"

    def __init__(self, **params):
        if not "id" in params:
            if "nsid" in params:
                params["id"] = params["nsid"]
            else:
                raise ValueError("The 'id' or 'nsid' parameter is required")
        FlickrObject.__init__(self, **params)

    @caller("flickr.photos.geo.batchCorrectLocation")
    def batchCorrectLocation(self, **args):
        return _format_id("place", args), _none

    @staticmethod
    def getFromToken(token=None, filename=None, token_key=None,
                     token_secret=None):
        """
            Retrieve the person corresponding to the authentication token.
        """
        if token is None:
            token = auth.token_factory(filename=filename, token_key=token_key,
                                       token_secret=token_secret)
        return test.login(token=token)

    @static_caller("flickr.people.findByEmail")
    def findByEmail(find_email):
        return {'find_email': find_email}, lambda r: Person(**r["user"])

    @static_caller("flickr.people.findByUsername")
    def findByUserName(username):
        return {'username': username}, lambda r: Person(**r["user"])

    @static_caller("flickr.urls.lookupUser")
    def findByUrl(url):
        return {'url': url}, lambda r: Person(**r["user"])

    @caller("flickr.favorites.getContext")
    def getFavoriteContext(self, **args):
        def format_result(r, token=None):
            return (Photo(token=token, **r["prevphoto"]),
                    Photo(token=token, **r["nextphoto"]))
        return _format_id("photo", args), format_result

    @caller("flickr.favorites.getList")
    def getFavorites(self, **args):
        return _format_extras(args), _extract_photo_list

    @caller("flickr.photosets.getList")
    def getPhotosets(self, **args):
        def format_result(r, token=None):
            info = r["photosets"]
            photosets = info.pop("photoset")
            if not isinstance(photosets, list):
                phototsets = [photosets]
            return FlickrList(
                [Photoset(token=token, **ps) for ps in photosets],
                 Info(**info)
            )
        return args, format_result

    @caller("flickr.favorites.getPublicList")
    def getPublicFavorites(self, **args):
        return _format_extras(args), _extract_photo_list

    @caller("flickr.people.getInfo")
    def getInfo(self, **args):
        def format_result(r):
            user = r["person"]
            user["photos_info"] = user.pop("photos")
            return user
        return args, format_result

    @caller("flickr.galleries.getList")
    def getGalleries(self, **args):
        def format_result(r, token=True):
            info = r["galleries"]
            galleries = _check_list(info.pop("gallery"))
            galleries_ = []

            for g in galleries_:
                g["owner"] = Person(g["owner"])
                pp_id = g.pop("primary_photo_id")
                pp_secret = g.pop("primary_photo_secret")
                pp_farm = g.pop("primary_photo_farm")
                pp_server = g.pop("primary_photo_server")
                g["primary_photo"] = Gallery(id=pp_id, secret=pp_secret,
                                            server=pp_server,
                                            farm=pp_farm, token=token)
                galleries_.append(g)
            return FlickrList(galleries_, Info(**info))
        return args, format_result

    @caller("flickr.people.getLimits")
    def getLimits(self):
        return {}, lambda r: r

    @caller("flickr.photos.getCounts")
    def getPhotoCounts(self, **args):
        return args, lambda r: r["photocounts"]["photocount"]

    @caller("flickr.people.getPhotos")
    def getPhotos(self, **args):
        return args, _extract_photo_list

    @caller("flickr.urls.getUserPhotos")
    def getPhotosUrl(self):
        return {}, lambda r: r["user"]["url"]

    @caller("flickr.urls.getUserProfile")
    def getProfileUrl(self):
        return {}, lambda r: r["user"]["url"]

    @caller("flickr.people.getPublicPhotos")
    def getPublicPhotos(self, **args):
        return args, _extract_photo_list

    @caller("flickr.people.getPhotosOf")
    def getPhotosOf(self, **args):
        return (_format_id("owner", _format_extras(args)),
               lambda r: _extract_photo_list(r, token=self.Token()))

    @caller("flickr.contacts.getPublicList")
    def getPublicContacts(self, **args):
        def format_result(r, token=None):
            info = r["contacts"]
            contacts = [Person(id=c["nsid"], token=token, **c)
                                for c in _check_list(info["contact"])]
            return FlickrList(contacts, Info(**info))
        return args, format_result

    @caller("flickr.people.getPublicGroups")
    def getPublicGroups(self, **args):
        def format_result(r, token=None):
            groups = r["groups"]["group"]
            groups_ = []
            for gr in groups:
                gr["id"] = gr["nsid"]
                groups_.append(Group(token=token, **gr))
            return groups_
        return args, format_result

    @static_caller("flickr.people.getUploadStatus")
    def getUploadStatus(**args):
        return args, lambda r: r["user"]

    @caller("flickr.collections.getTree")
    def getCollectionTree(**args):
        def format_result(r, token=None):
            collections = _check_list(r["collections"])
            collections_ = []
            for c in collections:
                sets = _check_list(c.pop("set"))
                sets_ = [Photoset(token=token, **s) for s in sets]
                collections_.append(Collection(token=token, sets=sets_, **c))
            return collections_
        return _format_id("collection", args), format_result

    @caller("flickr.photos.getContactsPublicPhotos")
    def getContactsPublicPhotos(self, **args):
        return (_format_extras(args),
                lambda r: _extract_photo_list(r, token=self.getToken())
                )

    @caller("flickr.tags.getListUser")
    def getTags(self):
        return {}, lambda r: [Tag(**t) for t in r["who"]["tags"]["tag"]]

    @caller("flickr.tags.getListUserPopular")
    def getPopularTags(**args):
        return args, lambda r: [Tag(**t) for t in r["who"]["tags"]["tag"]]

    @caller("flickr.favorites.remove")
    def removeFromFavorites(self, **args):
        return _format_id("photo", args), _none

    @static_caller("flickr.photos.getNotInSet")
    def getNotInSetPhotos(**args):
        return _format_extras(args), _extract_photo_list


class Photo(FlickrObject):
    __converters__ = [
        dict_converter(["isfamily", "ispublic", "isfriend", "cancomment",
                        "canaddmeta", "permcomment", "permmeta", "isfavorite"],
                        bool),
        dict_converter(["posted", "lastupdate"], int),
        dict_converter(["views", "comments"], int),
    ]
    __display__ = ["id", "title"]
    __self_name__ = "photo_id"

    class Comment(FlickrObject):
        __display__ = ["id", "author"]
        __self_name__ = "comment_id"

        @caller("flickr.photos.comments.deleteComment")
        def delete(self, **args):
            return args, _none

        @caller("flickr.photos.comments.editComment")
        def edit(self, **args):
            return args, _none

        @static_caller("flickr.photos.comments.getRecentForContacts")
        def getRecentForContacts(**args):
            return _format_extras(args), _extract_photo_list

    class Exif(FlickrObject):
        __display__ = ["tag", "raw"]

    class Note(FlickrObject):
        __display__ = ["id", "text"]
        __self_name__ = "note_id"

        @caller("flickr.photos.notes.edit")
        def edit(self, **args):
            return args, _none

        @caller("flickr.photos.notes.delete")
        def delete(self, **args):
            return args, _none

    class Suggestion(FlickrObject):
        __display__ = ["id"]
        __self_name__ = "suggestion_id"

        @caller("flickr.photos.suggestions.approveSuggestion")
        def approve(self):
            return {}, _none

        @caller("flickr.photos.suggestions.rejectSuggestion")
        def reject(self):
            return {}, _none

        @caller("flickr.photos.suggestions.removeSuggestion")
        def remove(self):
            return {}, _none

    @caller("flickr.photos.people.delete")
    def deletePerson(self, **args):
        return _format_id("user", args), _none

    @caller("flickr.photos.people.deleteCoords")
    def deletePersonCoords(self, **args):
        return _format_id("user", args), _none

    @caller("flickr.photos.people.editCoords")
    def editPersonCoords(self, **args):
        return _format_id("user", args), _none

    @caller("flickr.photos.comments.addComment")
    def addComment(self, **args):
        def format_result(r, token=None):
            args["id"] = r["comment"]["id"]
            args["photo"] = self
            return Photo.Comment(**args)
        return args, format_result

    @caller("flickr.photos.notes.add")
    def addNote(self, **args):
        def format_result(r, token=None):
            args["id"] = r["note"]["id"]
            args["photo"] = self
            return Photo.Note(**args)
        return args, format_result

    @caller("flickr.photos.people.add")
    def addPerson(self, **args):
        return _format_id("user", args), _none

    @caller("flickr.photos.addTags")
    def addTags(self, tags, **args):
        if isinstance(tags, list):
            tags = ", ".join(tags)
        args["tags"] = tags
        return args, _none

    @caller("flickr.favorites.add")
    def addToFavorites(self):
        return {}, _none

    @caller("flickr.photos.geo.correctLocation")
    def correctLocation(self, **args):
        return _format_id("place", args), _none

    @static_caller("flickr.photos.upload.checkTickets")
    def checkUploadTickets(tickets, **args):
        def format_result(r, token=None):
            tickets = r["uploader"]["ticket"]
            if not isinstance(tickets, list):
                tickets = [tickets]
            return [UploadTicket(**t) for t in tickets]
        return args, format_result

    @caller("flickr.photos.delete")
    def delete(self, **args):
        return args, _none

    @caller("flickr.photos.getAllContexts")
    def getAllContexts(self, **args):
        def format_result(r, token=None):
            photosets = []
            if "set" in r:
                for s in r["set"]:
                    photosets.append(Photoset(token=token, **s))
            pools = []
            if "pool" in r:
                for p in r["pool"]:
                    pools.append(Group(token=token, **p))
            return photosets, pools
        return args, format_result

    @caller("flickr.photos.comments.getList")
    def getComments(self, **args):
        def format_result(r, token=None):
            try:
                comments = r["comments"]["comment"]
            except KeyError:
                comments = []

            comments_ = []
            if not isinstance(comments, list):
                comments = [comments]
            for c in comments:
                author = c["author"]
                authorname = c.pop("authorname")
                c["author"] = Person(id=author, username=authorname,
                                        token=token)
                comments_.append(Photo.Comment(token=token, photo=self, **c))
            return comments_
        return args, format_result

    @caller("flickr.photos.getInfo")
    def getInfo(self, **args):
        def format_result(r, token=None):
            photo = r["photo"]

            owner = photo["owner"]
            owner["id"] = owner["nsid"]
            photo["owner"] = Person(token=token, **owner)

            photo.update(photo.pop("usage"))
            photo.update(photo.pop("visibility"))
            photo.update(photo.pop("publiceditability"))
            photo.update(photo.pop("dates"))

            tags = []
            for t in _check_list(photo["tags"]["tag"]):
                t["author"] = Person(token=token, id=t.pop("author"))
                tags.append(Tag(token=token, **t))
            photo["tags"] = tags
            photo["notes"] = [
                Photo.Note(token=token, **n)
                    for n in _check_list(photo["notes"]["note"])
            ]

            sizes = photo.pop("sizes", None)
            if sizes:
                photo["sizes"] = dict([(s['label'], s) for s in sizes["size"]])

            return photo
        return args, format_result

    @caller("flickr.photos.getContactsPhotos")
    def getContactsPhotos(self, **args):
        def format_result(r, token=None):
            photos = r["photos"]["photo"]
            photos_ = []
            for p in photos:
                photos_.append(Photo(token=token, **p))
            return photos_
        return args, format_result

    @caller("flickr.photos.getContext")
    def getContext(self, **args):
        def format_result(r, token):
            return (Photo(token=token, **r["prevphoto"]),
                    Photo(token=token, **r["nextphoto"]))
        return args, format_result

    @caller("flickr.photos.getExif")
    def getExif(self, **args):
        if hasattr(self, "secret"):
            args["secret"] = self.secret

        def format_result(r):
            try:
                return [Photo.Exif(**e) for e in r["photo"]["exif"]]
            except KeyError:
                return []
        return args, format_result

    @caller("flickr.favorites.getContext")
    def getFavoriteContext(self, **args):
        def format_result(r, token):
            return (Photo(token=token, **r["prevphoto"]),
                    Photo(token=token, **r["nextphoto"]))
        return _format_id("user", args), format_result

    @caller("flickr.photos.getFavorites")
    def getFavorites(self, **args):
        def format_result(r, token):
            photo = r["photo"]
            persons = photo.pop("person")
            persons_ = []
            if not isinstance(persons, list):
                persons = [persons]

            for p in persons:
                p["id"] = p["nsid"]
                persons_.append(Person(token=token, **p))
            infos = Info(**photo)
            return FlickrList(persons_, infos)
        return args, format_result

    @caller("flickr.galleries.getListForPhoto")
    def getGalleries(self, **args):
        def format_result(r):
            info = r["galleries"]
            galleries = _check_list(info.pop("gallery"))
            galleries_ = []

            for g in galleries_:
                g["owner"] = Person(g["owner"])
                pp_id = g.pop("primary_photo_id")
                pp_secret = g.pop("primary_photo_secret")
                pp_farm = g.pop("primary_photo_farm")
                pp_server = g.pop("primary_photo_server")

                g["primary_photo"] = Gallery(
                    id=pp_id, secret=pp_secret,
                    server=pp_server, farm=pp_farm
                )

                galleries_.append(g)

            return FlickrList(galleries_, Info(**info))
        return args, format_result

    @caller("flickr.photos.geo.getPerms")
    def getGeoPerms(self, **args):
        return args, lambda r, token: PhotoGeoPerms(token=token, **r["perms"])

    @caller("flickr.photos.geo.getLocation")
    def getLocation(self, **args):
        def format_result(r, token):
            loc = r["photo"]["location"]
            return Location(token=token, photo=self, **loc)
        return args, format_result

    def getNotes(self):
        """
            Returns the list of notes for a photograph
        """
        return self.notes

    @static_caller("flickr.interestingness.getList")
    def getInteresting(**args):
        return _format_extras(args), _extract_photo_list

    @static_caller("flickr.photos.getRecent")
    def getRecent(**args):
        return _format_extras(args), _extract_photo_list

    @caller("flickr.photos.suggestions.getList")
    def getSuggestions(self, **args):
        def format_result(r):
            info = r["suggestions"]
            suggestions_ = _check_list(info.pop("suggestion"))
            suggestions = []
            for s in suggestions_:
                if "photo_id" in s:
                    s["photo"] = s.pop(Photo(id=s.pop("photo_id")))
                if "suggested_by" in s:
                    s["suggested_by"] = Person(id=s["suggested_by"])
                suggestions.append(Photo.Suggestion(**s))
            return FlickrList(suggestions, info=Info(**info))
        return args, format_result

    @caller("flickr.photos.getSizes")
    def _getSizes(self, **args):
        def format_result(r):
            return dict([(s["label"], s) for s in r["sizes"]["size"]])
        return args, format_result

    def getSizes(self, **args):
        if "sizes" not in self.__dict__:
            self.__dict__["sizes"] = self._getSizes(**args)
        return self.sizes

    @caller("flickr.stats.getPhotoStats")
    def getStats(self, date, **args):
        args["date"] = date
        return (
            args,
            lambda r: dict([(k, int(v)) for k, v in r["stats"].iteritems()])
        )

    @caller("flickr.tags.getListPhoto")
    def getTags(self, **args):
        return args, lambda r: [Tag(**t) for t in r["photo"]["tags"]["tag"]]

    def getPageUrl(self):
        """
            returns the URL to the photo's page.
        """
        return "http://www.flickr.com/photos/%s/%s" % (self.owner.id, self.id)

    @caller("flickr.photos.getPerms")
    def getPerms(self):
        return {}, lambda r: r

    def _getLargestSizeLabel(self):
        """
            returns the largest size for the current photo.
        """
        sizes = self.getSizes()
        max_size = None
        max_area = None
        for sl, s in sizes.iteritems():
            area = int(s["height"]) * int(s["width"])
            if max_area is None or area > max_area:
                max_size = sl
                max_area = area
        return max_size

    def getPhotoUrl(self, size_label=None):
        """
            returns the URL to the photo page corresponding to the
            given size.

        Arguments:
            size_label: The label corresponding to the photo size

                'Square': 75x75
                'Thumbnail': 100 on longest side
                'Small': 240 on  longest side
                'Medium': 500 on longest side
                'Medium 640': 640 on longest side
                'Large': 1024 on longest side
                'Original': original photo (not always available)
        """
        if size_label is None:
            size_label = self._getLargestSizeLabel()
        try:
            return self.getSizes()[size_label]["url"]
        except KeyError:
            raise FlickrError("The requested size is not available")

    def getPhotoFile(self, size_label=None):
        """
            returns the URL to the photo file corresponding to the
            given size.

        Arguments:
            size_label: The label corresponding to the photo size

                'Square': 75x75
                'Thumbnail': 100 on longest side
                'Small': 240 on  longest side
                'Medium': 500 on longest side
                'Medium 640': 640 on longest side
                'Large': 1024 on longest side
                'Original': original photo (not always available)
        """
        if size_label is None:
            size_label = self._getLargestSizeLabel()
        try:
            return self.getSizes()[size_label]["source"]
        except KeyError:
            raise FlickrError("The requested size is not available")

    def save(self, filename, size_label=None):
        """
            saves the photo corresponding to the
            given size.

        Arguments:
            filename: target file name

            size_label: The label corresponding to the photo size

                'Square': 75x75
                'Thumbnail': 100 on longest side
                'Small': 240 on  longest side
                'Medium': 500 on longest side
                'Medium 640': 640 on longest side
                'Large': 1024 on longest side
                'Original': original photo (not always available)
        """
        if size_label is None:
            size_label = self._getLargestSizeLabel()
        r = urllib2.urlopen(self.getPhotoFile(size_label))
        with open(filename, 'wb') as f:
            f.write(r.read())
            f.close()

    def show(self, size_label=None):
        """
            Shows the photo corresponding to the
            given size.

        Note: This methods uses PIL

        Arguments:
            filename: target file name

            size_label: The label corresponding to the photo size

                'Square': 75x75
                'Thumbnail': 100 on longest side
                'Small': 240 on  longest side
                'Medium': 500 on longest side
                'Medium 640': 640 on longest side
                'Large': 1024 on longest side
                'Original': original photo (not always available)
        """
        if size_label is None:
            size_label = self._getLargestSizeLabel()
        r = urllib2.urlopen(self.getPhotoFile(size_label))
        b = cStringIO.StringIO(r.read())
        Image.open(b).show()

    @static_caller("flickr.photos.getUntagged")
    def getUntagged(**args):
        return _format_extras(args), _extract_photo_list

    @static_caller("flickr.photos.getWithGeoData")
    def getWithGeoData(**args):
        return _format_extras(args), _extract_photo_list

    @static_caller("flickr.photos.getWithoutGeoData")
    def getWithoutGeoData(**args):
        return _format_extras(args), _extract_photo_list

    @caller("flickr.photos.people.getList")
    def getPeople(self, **args):
        def format_result(r, token):
            info = r["people"]
            people = info.pop("person")
            people_ = []
            if isinstance(people, Person):
                people = [people]
            for p in people:
                p["id"] = p["nsid"]
                p["photo"] = self
                people_.append(Person(**p))
            return people_
        return args, format_result

    @static_caller("flickr.photos.geo.photosForLocation")
    def photosForLocation(**args):
        return args, _extract_photo_list

    @static_caller("flickr.photos.recentlyUpdated")
    def recentlyUpdated(**args):
        return _format_extras(args), _extract_photo_list

    @caller("flickr.favorites.remove")
    def removeFromFavorites(self, **args):
        return args, _none

    @caller("flickr.photos.geo.removeLocation")
    def removeLocation(self, **args):
        return args, _none

    @caller("flickr.photos.transform.rotate")
    def rotate(self, degrees, **args):
        args["degrees"] = degrees

        def format_result(r, token):
            photo_id = r["photo_id"]["_content"]
            photo_secret = r["photo_id"]["secret"]
            return Photo(token=token, id=photo_id, secret=photo_secret)
        return args, format_result

    @static_caller("flickr.photos.search")
    def search(**args):
        args = _format_id("user", args)
        args = _format_extras(args)
        return args, _extract_photo_list

    @caller("flickr.photos.geo.setContext")
    def setContext(self, context, **args):
        args["context"] = context
        return args, _none

    @caller("flickr.photos.setContentType")
    def setContentType(self, **args):
        return args, _none

    @caller("flickr.photos.setDates")
    def setDates(self, **args):
        return args, _none

    @caller("flickr.photos.geo.setPerms")
    def setGeoPerms(self, **args):
        return args, _none

    @caller("flickr.photos.licenses.setLicense")
    def setLicence(self, license, **args):
        return _format_id("licence", args), _none

    @caller("flickr.photos.geo.setLocation")
    def setLocation(self, **args):
        return args, _none

    @caller("flickr.photos.setMeta")
    def setMeta(self, **args):
        return args, _none

    @caller("flickr.photos.setPerms")
    def setPerms(self, **args):
        return args, _none

    @caller("flickr.photos.setSafetyLevel")
    def setSafetyLevel(self, **args):
        return args, _none

    @caller("flickr.photos.setTags")
    def setTags(self, tags, **args):
        args["tags"] = tags
        return args, _none

    @caller("flickr.photos.suggestions.suggestLocation")
    def suggestLocation(self, **args):
        _format_id("place", args)

        def format_result(r):
            info = r["suggestions"]
            suggestions_ = _check_list(info.pop("suggestion"))
            suggestions = []
            for s in suggestions_:
                if "photo_id" in s:
                    s["photo"] = Photo(id=s.pop("photo_id"))
                if "suggested_by" in s:
                    s["suggested_by"] = Person(id=s["suggested_by"])
                suggestions.append(Photo.Suggestion(**s))
            return FlickrList(suggestions, info=Info(**info))
        return args, format_result


class PhotoGeoPerms(FlickrObject):
    __converters__ = [
        dict_converter(["ispublic", "iscontact", "isfamily", "isfriend"], bool)
    ]
    __display__ = ["id", "ispublic", "iscontact", "isfamily", "isfriend"]


class Photoset(FlickrObject):
    __converters__ = [
        dict_converter(["photos"], int),
    ]
    __display__ = ["id", "title"]
    __self_name__ = "photoset_id"

    class Comment(FlickrObject):
        __display__ = ["id"]
        __self_name__ = "comment_id"

        @caller("flickr.photosets.comments.deleteComment")
        def delete(self, **args):
            return args, _none

        @caller("flickr.photosets.comments.editComment")
        def edit(self, **args):
            self._set_properties(**args)
            return args, _none

    @caller("flickr.photosets.addPhoto")
    def addPhoto(self, **args):
        return _format_id("photo", args), _none

    @caller("flickr.photosets.comments.addComment")
    def addComment(self, **args):
        return (
            args,
            lambda r, token: Photoset.Comment(token=token, photoset=self, **r)
        )

    @static_caller("flickr.photosets.create")
    def create(**args):
        try:
            pphoto = args.pop("primary_photo")
            pphoto_id = pphoto.id
        except KeyError:
            pphoto_id = args.pop("primary_photo_id")
            pphoto = Photo(id=pphoto_id)
        args["primary_photo_id"] = pphoto_id

        def format_result(r, token):
            photoset = r["photoset"]
            photoset["primary"] = pphoto
            return Photoset(token=token, **photoset)
        return args, format_result

    @caller("flickr.photosets.delete")
    def delete(self, **args):
        return args, _none

    @caller("flickr.photosets.editMeta")
    def editMeta(self, **args):
        return args, _none

    @caller("flickr.photosets.editPhotos")
    def editPhotos(self, **args):
        try:
            args["primary_photo_id"] = args.pop("primary_photo").id
        except KeyError:
            pass
        try:
            args["photo_ids"] = [p.id for p in args["photos"]]
        except KeyError:
            pass

        photo_ids = args["photo_ids"]
        if isinstance(photo_ids, list):
            args["photo_ids"] = ", ".join(photo_ids)
        return args, _none

    @caller("flickr.photosets.comments.getList")
    def getComments(self, **args):
        def format_result(r, token):
            comments = r["comments"]["comment"]
            comments_ = []
            if not isinstance(comments, list):
                comments = [comments]
            for c in comments:
                author = c["author"]
                authorname = c.pop("authorname")
                c["author"] = Person(id=author, username=authorname)
                comments_.append(
                    Photoset.Comment(token=token, photo=self, **c)
                )
            return comments_
        return args, format_result

    @caller("flickr.photosets.getContext")
    def getContext(self, **args):
        def format_result(r, token):
            return (Photo(token=token, **r["prevphoto"]),
                    Photo(token=token, **r["nextphoto"]))
        return _format_id("photo", args), format_result

    @caller("flickr.photosets.getInfo")
    def getInfo(self, **args):
        def format_result(r, token):
            photoset = r["photoset"]
            photoset["owner"] = Person(token=token, id=photoset["owner"])
            return photoset
        return args, format_result

    @caller("flickr.photosets.getPhotos")
    def getPhotos(self, **args):
        def format_result(r):
            ps = r["photoset"]
            return FlickrList([Photo(**p) for p in ps["photo"]],
                               Info(pages=ps["pages"],
                                    page=ps["page"],
                                    perpage=ps["perpage"],
                                    total=ps["total"]))
        return _format_extras(args), format_result

    @caller("flickr.stats.getPhotosetStats")
    def getStats(self, date, **args):
        args["date"] = date
        return (
            args,
            lambda r: dict([(k, int(v)) for k, v in r["stats"].iteritems()])
        )

    @static_caller("flickr.photosets.orderSets")
    def orderSets(**args):
        try:
            photosets = args.pop("photosets")
            args["photoset_ids"] = [ps.id for ps in photosets]
        except KeyError:
            pass

        photoset_ids = args["photoset_ids"]
        if isinstance(photoset_ids, list):
            args["photoset_ids"] = ", ".join(photoset_ids)

        return args, _none

    @caller("flickr.photosets.removePhoto")
    def removePhoto(self, **args):
        return _format_id("photo", args), _none

    @caller("flickr.photosets.removePhotos")
    def removePhotos(self, **args):
        try:
            args["photo_ids"] = [p.id for p in args.pop("photos")]
        except KeyError:
            pass

        photo_ids = args["photo_ids"]
        if isinstance(photo_ids, list):
            args["photo_ids"] = u", ".join(photo_ids)

        return args, _none

    @caller("flickr.photosets.reorderPhotos")
    def reorderPhotos(self, **args):
        try:
            args["photo_ids"] = [p.id for p in args.pop("photos")]
        except KeyError:
            pass

        photo_ids = args["photo_ids"]
        if isinstance(photo_ids, list):
            args["photo_ids"] = u", ".join(photo_ids)

        return args, _none

    @caller("flickr.photosets.setPrimaryPhoto")
    def setPrimaryPhoto(self, **args):
        return _format_id("photo", args), _none


class Place(FlickrObject):
    __display__ = ["id", "name", "woeid", "latitude", "longitude"]
    __converters__ = [
        dict_converter(["latitude", "longitude"], float),
    ]
    __self_name__ = 'place_id'

    class ShapeData(FlickrObject):
        class Polyline(FlickrObject):
            pass

    class Type(FlickrObject):
        __display__ = ["id", "text"]

    class Tag(FlickrObject):
        __display__ = ["text", "count"]
        __converters__ = [
            dict_converter(["count"], int),
        ]

    @static_caller("flickr.places.find")
    def find(**args):
        return args, _extract_place_list

    @static_caller("flickr.places.findByLatLon")
    def findByLatLon(**args):
        return args, _extract_place_list

    @caller("flickr.places.getChildrenWithPhotosPublic")
    def getChildrenWithPhotoPublic(self, **args):
        return args, _extract_place_list

    @caller("flickr.places.getInfo")
    def getInfo(self, **args):
        def format_result(r):
            return Place.parse_place(r["place"])
        return args, format_result

    @staticmethod
    def parse_shapedata(shape_data_dict):
        shapedata = shape_data_dict.copy()
        shapedata["polylines"] = [
            Place.ShapeData.Polyline(coords=p.split(" "))
                for p in shapedata["polylines"]["polyline"]
        ]
        if "url" in shapedata:
            shapedata["shapefile"] = shapedata.pop("urls")["shapefile"].text
        return shapedata

    @staticmethod
    def parse_place(place_dict):
        place = place_dict.copy()
        if "locality" in place:
            place["locality"] = Place(**Place.parse_place(place["locality"]))

        if "county" in place:
            place["county"] = Place(**Place.parse_place(place["county"]))

        if "region" in place:
            place["region"] = Place(**Place.parse_place(place["region"]))

        if "country" in place:
            place["country"] = Place(**Place.parse_place(place["country"]))

        if "shapedata" in place:
            shapedata = Place.parse_shapedata(place["shapedata"])
            place["shapedata"] = Place.ShapeData(**shapedata)

        if "text" in place:
            place["name"] = place.pop("text")

        place["id"] = place.pop("place_id")
        return place

    @static_caller("flickr.places.getInfoByUrl")
    def getByUrl(url):
        return {'url': url}, lambda r: Place(**Place.parse_place(r["place"]))

    @static_caller("flickr.places.getPlaceTypes")
    def getPlaceTypes(**args):
        def format_result(r):
            places_types = r["place_types"]["place_type"]
            return [Place.Type(id=pt.pop("place_type_id"), **pt)
                     for pt in places_types]
        return args, format_result

    @static_caller("flickr.places.getShapeHistory")
    def getShapeHistory(**args):
        def format_result(r):
            info = r["shapes"]
            return [Place.ShapeData(**Place.parse_shapedata(sd))
                    for sd in _check_list(info.pop("shapedata"))]
        return args, format_result

    @caller("flickr.places.getTopPlacesList")
    def getTopPlaces(self, **args):
        return args, _extract_place_list

    @static_caller("flickr.places.placesForBoundingBox")
    def placesForBoundingBox(**args):
        def format_result(r):
            info = r["places"]
            return [
                Place(Place.parse_place(place))
                    for place in info.pop("place")]
        return args, format_result

    @static_caller("flickr.places.placesForContacts")
    def placesForContacts(**args):
        def format_result(r):
            info = r["places"]
            return [
                Place(Place.parse_place(place))
                    for place in info.pop("place")]
        return args, format_result

    @static_caller("flickr.places.placesForTags")
    def placesForTags(**args):
        return args, _extract_place_list

    @static_caller("flickr.places.placesForUser")
    def placesForUser(**args):
        return args, _extract_place_list

    @static_caller("flickr.places.tagsForPlace")
    def tagsForPlace(**args):
        args = _format_id("place", args)
        args = _format_id("woe", args)
        return args, lambda r: [Place.Tag(**t) for t in r["tags"]["tag"]]

    @caller("flickr.places.tagsForPlace")
    def getTags(self, **args):
        return args, lambda r: [Place.Tag(**t) for t in r["tags"]["tag"]]


class prefs(FlickrObject):
    @static_caller("flickr.prefs.getContentType")
    def getContentType(**args):
        return args, lambda r: r["person"]["content_type"]

    @static_caller("flickr.prefs.getGeoPerms")
    def getGeoPerms(**args):
        return args, lambda r: r["person"]

    @static_caller("flickr.prefs.getHidden")
    def getHidden(**args):
        return args, lambda r: bool(r["person"]["hidden"])

    @static_caller("flickr.prefs.getPrivacy")
    def getPrivacy(**args):
        return args, lambda r: r["person"]["privacy"]

    @static_caller("flickr.prefs.getSafetyLevel")
    def getSafetyLevel(**args):
        return args, lambda r: r["person"]["safety_level"]


class Reflection(FlickrObject):
    @static_caller("flickr.reflection.getMethodInfo")
    def getMethodInfo(method_name):
        return {"method_name": method_name}, lambda r: r["method"]

    @static_caller("flickr.reflection.getMethods")
    def getMethods():
        return {}, lambda r: r["methods"]["method"]


class stats(FlickrObject):
    class Domain(FlickrObject):
        __display__ = ["name"]

    class Referrer(FlickrObject):
        __display__ = ["url", "views"]
        __converters__ = [
            dict_converter(["views"], int),
        ]

    @static_caller("flickr.stats.getCollectionDomains")
    def getCollectionDomains(**args):
        def format_result(r):
            info = r["domains"]
            domains = [stats.Domain(**d) for d in info.pop("domain")]
            return FlickrList(domains, Info(**info))
        return _format_id("collection", args), format_result

    @static_caller("flickr.stats.getCollectionReferrers")
    def getCollectionReferrers(**args):
        def format_result(r):
            info = r["domain"]
            referrers = [stats.Referrer(**r) for r in info.pop("referrer")]
            return FlickrList(referrers, Info(**info))
        return _format_id("collection", args), format_result

    @static_caller("flickr.stats.getCSVFiles")
    def getCSVFiles():
        return {}, lambda r: r["stats"]["csvfiles"]["csv"]

    @static_caller("flickr.stats.getPhotoDomains")
    def getPhotoDomains(**args):
        def format_result(r):
            info = r["domains"]
            domains = [stats.Domain(**d) for d in info.pop("domain")]
            return FlickrList(domains, Info(**info))
        return _format_id("photo", args), format_result

    @static_caller("flickr.stats.getPhotoReferrers")
    def getPhotoReferrers(**args):
        def format_result(r):
            info = r["domain"]
            referrers = [stats.Referrer(**r) for r in info.pop("referrer")]
            return FlickrList(referrers, Info(**info))
        return _format_id("photo", args), format_result

    @static_caller("flickr.stats.getPhotosetDomains")
    def getPhotosetDomains(**args):
        def format_result(r):
            info = r["domains"]
            domains = [stats.Domain(**d) for d in info.pop("domain")]
            return FlickrList(domains, Info(**info))
        return _format_id("photoset", args), format_result

    @static_caller("flickr.stats.getPhotosetReferrers")
    def getPhotosetReferrers(**args):
        def format_result(r):
            info = r["domain"]
            referrers = [stats.Referrer(**r) for r in info.pop("referrer")]
            return FlickrList(referrers, Info(**info))
        return _format_id("photoset", args), format_result

    @static_caller("flickr.stats.getPhotostreamDomains")
    def getPhotostreamDomains(**args):
        def format_result(r):
            info = r["domains"]
            domains = [stats.Domain(**d) for d in info.pop("domain")]
            return FlickrList(domains, Info(**info))
        return args, format_result

    @static_caller("flickr.stats.getPhotostreamReferrers")
    def getPhotostreamReferrers(**args):
        def format_result(r):
            info = r["domain"]
            referrers = [stats.Referrer(**r) for r in info.pop("referrer")]
            return FlickrList(referrers, Info(**info))
        return args, format_result

    @static_caller("flickr.stats.getPhotostreamStats")
    def getPhotostreamStats(date, **args):
        args["date"] = date
        return args, lambda r: int(r["stats"]["views"])

    @static_caller("flickr.stats.getPopularPhotos")
    def getPopularPhotos():
        def format_result(r):
            info = r["photos"]
            photos = []
            for p in info.pop("photo"):
                pstat = p.pop("stats")
                photos.append((Photo(**p), pstat))
            return FlickrList(photos, Info(**info))
        return {}, format_result

    @static_caller("flickr.stats.getTotalViews")
    def getTotalViews(**args):
        return args, lambda r: r["stats"]


class Tag(FlickrObject):
    __display__ = ["id", "text"]
    __self_name__ = "tag_id"

    class Cluster(FlickrObject):
        __display__ = ["total"]
        __self_name__ = "cluster_id"

        @caller("flickr.tags.getClusterPhotos")
        def getPhotos(self, **args):
            return args, _extract_photo_list

    @caller("flickr.photos.removeTag")
    def remove(self, **args):
        return args, _none

    @static_caller("flickr.tags.getClusters")
    def getClusters(**args):
        def format_result(r):
            clusters = r["clusters"]["cluster"]
            return [
                Tag.Cluster(tag=args["tag"],
                            tags=[Tag(text=t) for t in c["tag"]],
                            total=c["total"]
                ) for c in clusters
            ]
        return args, format_result

    @static_caller("flickr.tags.getHotList")
    def getHotList(**args):
        return args, lambda r: [Tag(**t) for t in r["hottags"]["tag"]]

    @static_caller("flickr.tags.getListUser")
    def getListUser(**args):
        return (
            _format_id("user", args),
            lambda r: [Tag(**t) for t in r["who"]["tags"]["tag"]]
        )

    @static_caller("flickr.tags.getListUserPopular")
    def getListUserPopular(**args):
        return (_format_id("user", args),
                lambda r: [Tag(**t) for t in r["who"]["tags"]["tag"]])

    @static_caller("flickr.tags.getListUserRaw")
    def getListUserRaw(**args):
        def format_result(r):
            tags = r["who"]["tags"]["tag"]
            return [{'clean': t["clean"], "raws": t["raw"]} for t in tags]
        return args, format_result

    @static_caller("flickr.tags.getRelated")
    def getRelated(tag, **args):
        args["tag"] = tag
        return args, lambda r: r["tags"]["tag"]


class test(FlickrObject):
    @static_caller("flickr.test.echo")
    def echo(**args):
        return args, lambda r: r

    @static_caller("flickr.test.login")
    def login(token=None, **args):
        return args, lambda r: Person(token=token, **r["user"])

    @static_caller("flickr.test.null")
    def null():
        return {}, _none


class UploadTicket(FlickrObject):
    pass


def _extract_activity_list(r):
    items = _check_list(r["items"]["item"])
    activities = []
    for item in items:
        activity = item.pop("activity")
        item_type = item.pop(["type"])
        if item_type == "photo":
            item = Photo(**item)
        elif item_type == "photoset":
            item = Photoset(**item)
        events_ = []
        events = _check_list(activity["event"])
        for e in events:
            user = e["user"]
            username = e.pop("username")
            e["user"] = Person(id=user, username=username)
            e_type = e.pop("type")
            if e_type == "comment":
                if item_type == "photo":
                    events_.append(Photo.Comment(photo=item, **e))
                elif item_type == "photoset":
                    events_.append(Photoset.Comment(photoset=item, **e))
            elif e_type == 'note':
                events_.append(Photo.Note(photo=item, **e))
        activities.append(Activity(item=item, events=events))
    return activities


def _format_id(name, args):
    try:
        args[name + "_id"] = args.pop(name).id
    except KeyError:
        pass
    return args


def _format_extras(args):
    try:
        extras = args["extras"]
        if isinstance(extras, list):
            args["extras"] = ", ".join(extras)
    except KeyError:
        pass
    return args


def _new(cls):
    def _newobject(**args):
        return cls(**args)
    return _newobject


def _none(r):
    return None


def _extract_place_list(r):
    info = r["places"]
    return FlickrList(
        [Place(id=place.pop("place_id"), **place)
            for place in info.pop("place")],
        Info(**info)
    )


def _extract_photo_list(r, token=None):
    photos = []
    infos = r["photos"]
    pp = infos.pop("photo")
    if not isinstance(pp, list):
        pp = [pp]
    for p in pp:
        owner = Person(id=p["owner"], token=token)
        p["owner"] = owner
        p["token"] = token
        photos.append(Photo(**p))
    return FlickrList(photos, Info(**infos))


def _check_list(obj):
    if isinstance(obj, list):
        return obj
    else:
        return [obj]


class Walker(object):
    """
        Object to walk along paginated results. This allows
        to loop on all the results corresponding to a query
        regardless pagination.

        w = Walker(method,*args, **kwargs)

        arguments:
        - method: a method returning a FlickrList object.
        - *args: positional arguments to call 'method' with
        - **kwargs: named arguments to call 'method' with

        ex:
        >>> w = Walker(Photo.search, tags="animals")
        >>> for photo in w:
        >>>     print photo.title

        You can also use slices:
        ex:
        >>> w = Walker(Photo.search, tags="animals")
        >>> for photo in w[:20]:
        >>>     print photo.title

        but be aware that if a starting index is given all the items
        till the wanted one will be iterated, so using a large
        starting value might be slow.
    """
    def __init__(self, method, *args, **kwargs):
        """
            Constructor

        arguments:
        - method: a method returning a FlickrList object.
        - *args: positional arguments to call 'method' with
        - **kwargs: named arguments to call 'method' with

        """
        self.method = method
        self.args = args
        self.kwargs = kwargs

        self._curr_list = self.method(*self.args, **self.kwargs)
        self._info = self._curr_list.info
        self._curr_index = 0
        self._page = 1
        self.stop = None

    def __len__(self):
        return self._info.total

    def __iter__(self):
        return self

    def __getitem__(self, slice_):
        if isinstance(slice_, slice):
            return SlicedWalker(self,
                slice_.start,
                slice_.stop,
                slice_.step)
        else:
            raise ValueError("Only slices can be used as subscript")

    def next(self):
        if self._curr_index == len(self._curr_list):
            if self._page < self._info.pages:
                self._page += 1
                self.kwargs["page"] = self._page

                self._curr_list = self.method(*self.args, **self.kwargs)
                self._info = self._curr_list.info
                self._curr_index = 0

            else:
                raise StopIteration()

        curr = self._curr_list[self._curr_index]
        self._curr_index += 1
        return curr


class SlicedWalker(object):
    """ Used to apply slices on objects.
        Starting at a large index might be slow since all items till
        the start one will be iterated.
    """
    def __init__(self, walker, start, stop, step):
        self.walker = walker
        self.start = start or 0
        self.stop = stop or len(walker)
        self.step = step or 1

        self._begin = True
        self._total = 0

    def __len__(self):
        return (self.stop - self.start) // self.step

    def __iter__(self):
        return self

    def next(self):
        if self._begin:
            for i in range(self.start):
                self.walker.next()
                self._total += 1
            self._begin = False
        else:
            for i in range(self.step - 1):
                self._total += 1
                self.walker.next()

        if self._total < self.stop:
            self._total += 1
            return self.walker.next()
        else:
            raise StopIteration()

########NEW FILE########
__FILENAME__ = reflection
"""
    Reflection module.

    This modules implements the bases of the reflection mechanisms of
    'flikr_api'.

    author: Alexis Mignon (c) 2012
    e-mail: alexis.mignon@gmail.com
    date: 21/03/2012
"""

import re
from functools import wraps
from . import method_call
from . import auth
from .flickrerrors import FlickrError

try:
    from methods import __methods__

    def make_docstring(method, ignore_arguments=[], show_errors=True):
        info = __methods__[method]
        context = {'method': method}

        doc = """
    flickr method: %(method)s

    Description:
%(description)s

    Authentication:
            %(authentication)s

    Arguments:
%(arguments)s
    """
        context["description"] = format_block(info["description"], 80, " " * 8)
        needs_login = info["needslogin"]
        required = info["requiredperms"]
        if needs_login:
            if required == 'none':
                authentication = "This method requires authentication"
            elif required == 'read':
                authentication = ("This method requires authentication with "
                                  "'read' permission")
            elif required == 'write':
                authentication = ("This method requires authentication with "
                                  "'write' permission")
            elif required == 'delete':
                authentication = ("This method requires authentication with "
                                  "'delete' permission")
            else:
                raise ValueError("Unexpected permision value: %s" % required)
        else:
            authentication = "This method does not require authentication"
        context["authentication"] = authentication
        arguments = []
        argument = """        %(argument_name)s (%(argument_required)s):
%(argument_descr)s"""
        for a in info["arguments"]:
            aname = a["name"]
            if aname in ignore_arguments:
                continue
            argument_context = {
                'argument_name': aname,
                'argument_required': 'optional' if a["optional"] \
                                                else 'required',
                'argument_descr': format_block(a["text"], 80, " " * 12)
            }
            arguments.append(argument % argument_context)
        context["arguments"] = "\n".join(arguments)

        if show_errors:
            doc += """
        Errors:
    %(errors)s
    """
            errors = []
            error = """        code %(code)s:
    %(message)s"""
            for e in info["errors"]:
                error_context = {
                    'code': e["code"],
                    'message': format_block(e["message"], 80, " " * 12)
                }
                errors.append(error % error_context)
            context["errors"] = "\n".join(errors)
        return doc % context

except ImportError:
    __methods__ = {}

    def make_docstring(method, ignore_arguments=[], show_errors=True):
        return None

LIST_REG = re.compile(r'<ul>(.*?)</ul>', re.DOTALL | re.UNICODE | re.MULTILINE)
LIST_ITEM_REG = re.compile(r'<li>(.*?)</li>', re.DOTALL | re.UNICODE)

__bindings__ = {}


def bindings_to(flickr_method):
    """
        Returns the list of bindings to the given Flickr API method
        in the object API.

        ex:
        >>> bindings_to("flickr.people.getPhotos")
        ['Person.getPhotos']
        this tells that the method from Flickr API 'flickr.people.getPhotos'
        is bound to the 'Person.getPhotos' method of the object API.
    """
    try:
        return __bindings__[flickr_method]
    except KeyError:
        if flickr_method in __methods__:
            return []
        else:
            raise FlickrError("Unknown Flickr API method: %s" % flickr_method)


class FlickrAutoDoc(type):
    """
        Meta class that adds documentation to methods that bind
        to a flickr method, which are called 'caller methods'.

        It basically adds two attributes to each caller methods:
        * __doc__: the docstring is set from the documentation
            returned by flickr.reflection.getMethodInfo. If the method
            is not static, the entry related to the object itself is
            removed from the docstring, using the __self_name__ class
            attribute.
            For instance, Person.__self_name__ = "user_id". This means
            the for a bound (not static) method, the entry corresponding
            to "user_id" in the docstring is removed.
        * __self_name__: for non static method, a '__self_name__' attribute
            is added to the method. This is used by the 'caller'
            decorator to know how to refer to the calling object.

    """
    def __new__(meta, classname, bases, classDict):
        self_name = classDict.get("__self_name__", None)
        for k, v in classDict.iteritems():
            ignore_arguments = ["api_key"]
            if hasattr(v, 'flickr_method'):
                if v.isstatic:
                    v.inner_func.__doc__ = make_docstring(v.flickr_method,
                                                          ignore_arguments,
                                                          show_errors=False)
                else:
                    ignore_arguments.append(self_name)
                    v.__self_name__ = self_name  # this is used by the
                    # decorator caller to know the arument name to use to refer
                    # to the current object.
                    v.__doc__ = make_docstring(v.flickr_method,
                                               ignore_arguments,
                                               show_errors=False)
                try:
                    __bindings__[v.flickr_method].append(classname + "." + k)
                except KeyError:
                    __bindings__[v.flickr_method] = [classname + "." + k]
        return type.__new__(meta, classname, bases, classDict)


def format_block(text, width, prefix=""):
    text = text.replace(r"<br />", r"<br/>")
    text = text.replace(r"<br/><br/>", r" <br/> ")
    text = text.replace('<strong>', "").replace("</strong>", "")
    text = text.replace("<code>", "'").replace("</code>", "'")
    text.replace("&mdash;", "--")
    text = text.split()
    lines = []
    line = prefix
    start = True

    for word in text:
        if word == "<br/>":
            lines.append(line)
            line = prefix
            start = True
            continue

        line_length = len(line) + len(word)
        if start:
            line_length += 1
        if line_length > width:
            if start:  # if the word is too big we still concatenate it.
                line += word
                start = False
            else:
                lines.append(line)
                line = prefix + word
                start = False
        else:
            if not start:
                line += ' '
            line += word
            start = False
    if not start:
        lines.append(line)
    res = "\n".join(lines) + "\n"

    list_blocks = LIST_REG.findall(res)
    for block in list_blocks:
        block.replace("\n", " ")
        items = "\n" + "".join(
            [format_block("* %s" % i.strip(), width, prefix)
                for i in LIST_ITEM_REG.findall(block)]
        ) + prefix
        res = LIST_REG.sub(items, res)
    return res


def _get_token(self, **kwargs):
    token = token = kwargs.pop("token", None)
    not_signed = kwargs.pop("not_signed", False)
    if not_signed:
        token = None
    else:
        if token is None and self is not None:
            try:
                token = self.getToken()
            except AttributeError:
                pass
    if not token:
        token = auth.AUTH_HANDLER
    return token, kwargs


def caller(flickr_method, static=False):
    """
        This decorator binds a method to the flickr method given
        by 'flickr_method'.
        The wrapped method should return the argument dictionnary
        and a function that format the result of method_call.call_api.

        Some method can propagate authentication tokens. For instance a
        Person object can propagate its token to photos retrieved from
        it. In this case, it should return its token also and the
        result formating function should take an additional argument
        token.
    """
    def decorator(method):
        @wraps(method)
        def call(self, *args, **kwargs):
            token, kwargs = _get_token(self, **kwargs)
            method_args, format_result = method(self, *args, **kwargs)
            method_args[call.__self_name__] = self.id
            if token:
                method_args["auth_handler"] = token
            r = method_call.call_api(method=flickr_method, **method_args)
            try:
                return format_result(r, token)
            except TypeError:
                return format_result(r)
        call.flickr_method = flickr_method
        call.isstatic = False
        return call
    return decorator


class StaticCaller(staticmethod):
    def __init__(self, func):
        staticmethod.__init__(self, func)
        self.__dict__ = func.__dict__
        self.inner_func = func


def static_caller(flickr_method, static=False):
    """
        This decorator binds a static method to the flickr method given
        by 'flickr_method'.
        The wrapped method should return the argument dictionnary
        and a function that format the result of method_call.call_api.

        Some method can propagate authentication tokens. For instance a
        Person object can propagate its token to photos retrieved from
        it. In this case, it should return its token also and the
        result formating function should take an additional argument
        token.
    """
    def decorator(method):
        @wraps(method)
        def static_call(*args, **kwargs):
            token, kwargs = _get_token(None, **kwargs)
            method_args, format_result = method(*args, **kwargs)
            method_args["auth_handler"] = token
            r = method_call.call_api(method=flickr_method, **method_args)
            try:
                return format_result(r, token)
            except TypeError:
                return format_result(r)
        static_call.flickr_method = flickr_method
        static_call.isstatic = True
        return StaticCaller(static_call)
    return decorator

########NEW FILE########
__FILENAME__ = tools
from method_call import call_api
import sys
import os


def load_methods():
    """
        Loads the list of all methods
    """
    r = call_api(method="flickr.reflection.getMethods")
    return r["methods"]["method"]

__perms__ = {0: 'none', '1': 'read', '2': 'write', '3': 'delete'}


def methods_info():
    methods = {}
    for m in load_methods():
        info = call_api(method="flickr.reflection.getMethodInfo",
                        method_name=m)
        info.pop("stat")
        method = info.pop("method")
        method["requiredperms"] = __perms__[method["requiredperms"]]
        method["needslogin"] = bool(method.pop("needslogin"))
        method["needssigning"] = bool(method.pop("needssigning"))
        info.update(method)
        info["arguments"] = info["arguments"]["argument"]
        info["errors"] = info["errors"]["error"]
        methods[m] = info
    return methods


def write_reflection(path, template, methods=None):
    if methods is None:
        methods = methods_info()
    with open(template, "r") as t:
        templ = t.read()

    prefix = ""
    new_templ = ""
    tab = "    "
    templ = templ % str(methods)
    for c in templ:
        if c == '{':
            new_templ += '{\n' + prefix
            prefix += tab
        elif c == '}':
            new_templ += '\n' + prefix + '}\n' + prefix
            prefix = prefix[:-len(tab)]
        else:
            new_templ += c

    with open(path, "w") as f:
        f.write(new_templ)


def write_doc(output_path, exclude=["flickr_keys", "methods"]):
    import flickr_api
    exclude.append("__init__")
    modules = ['flickr_api']
    dir = os.path.dirname(flickr_api.__file__)
    modules += [
        "flickr_api." + f[:-3]
            for f in os.listdir(dir)
            if f.endswith(".py") and f[:-3] not in exclude]
    sys.path.insert(0, dir + "../")
    if not os.path.exists(output_path):
        os.makedirs(output_path)
    os.chdir(output_path)
    for m in modules:
        os.system("pydoc -w " + m)

########NEW FILE########
__FILENAME__ = upload
"""
    Upload API for Flickr.
    It is separated since it requires different treatments than
    the usual API.

    Two functions are provided:

    - upload
    - replace (presently not working)

    Author: Alexis Mignon (c)
    email: alexis.mignon@gmail.com
    Date:  06/08/2011

"""


from .flickrerrors import FlickrError, FlickrAPIError
from .objects import Photo, UploadTicket
from . import auth
from . import multipart
import os
from xml.etree import ElementTree as ET

UPLOAD_URL = "https://api.flickr.com/services/upload/"
REPLACE_URL = "https://api.flickr.com/services/replace/"


def format_dict(d):
    d_ = {}
    for k, v in d.iteritems():
        if isinstance(v, bool):
            v = int(v)
        elif isinstance(v, unicode):
            v = v.encode("utf8")
        if isinstance(k, unicode):
            k = k.encode("utf8")
        v = str(v)
        d_[k] = v
    return d_


def post(url, auth_handler, args, photo_file):
    args = format_dict(args)
    args["api_key"] = auth_handler.key

    params = auth_handler.complete_parameters(url, args).parameters

    fields = params.items()

    files = [("photo", os.path.basename(photo_file), open(photo_file).read())]

    r, data = multipart.posturl(url, fields, files)
    if r.status != 200:
        raise FlickrError("HTTP Error %i: %s" % (r.status, data))
    
    r = ET.fromstring(data)
    if r.get("stat") != 'ok':
        err = r[0]
        raise FlickrAPIError(int(err.get("code")), err.get("msg"))
    return r


def upload(**args):
    """
    Authentication:

        This method requires authentication with 'write' permission.

    Arguments:
        photo_file
            The file to upload.
        title (optional)
            The title of the photo.
        description (optional)
            A description of the photo. May contain some limited HTML.
        tags (optional)
            A space-seperated list of tags to apply to the photo.
        is_public, is_friend, is_family (optional)
            Set to 0 for no, 1 for yes. Specifies who can view the photo.
        safety_level (optional)
            Set to 1 for Safe, 2 for Moderate, or 3 for Restricted.
        content_type (optional)
            Set to 1 for Photo, 2 for Screenshot, or 3 for Other.
        hidden (optional)
            Set to 1 to keep the photo in global search results, 2 to hide
            from public searches.
        async
            set to 1 for async mode, 0 for sync mode

    """
    if "async" not in args:
        args["async"] = False

    photo_file = args.pop("photo_file")
    r = post(UPLOAD_URL, auth.AUTH_HANDLER, args, photo_file)

    t = r[0]
    if t.tag == 'photoid':
        return Photo(
            id=t.text,
            editurl='https://www.flickr.com/photos/upload/edit/?ids=' + t.text
        )
    elif t.tag == 'ticketid':
        return UploadTicket(id=t.text)
    else:
        raise FlickrError("Unexpected tag: %s" % t.tag)


def replace(**args):
    """
     Authentication:

        This method requires authentication with 'write' permission.

        For details of how to obtain authentication tokens and how to sign
        calls, see the authentication api spec. Note that the 'photo' parameter
        should not be included in the signature. All other POST parameters
        should be included when generating the signature.

    Arguments:

        photo_file
            The file to upload.
        photo_id
            The ID of the photo to replace.
        async (optional)
            Photos may be replaced in async mode, for applications that
            don't want to wait around for an upload to complete, leaving
            a socket connection open the whole time. Processing photos
            asynchronously is recommended. Please consult the documentation
            for details.

    """
    if "async" not in args:
        args["async"] = True
    if "photo" in args:
        args["photo_id"] = args.pop("photo").id

    photo_file = args.pop("photo_file")

    r = post(REPLACE_URL, auth.AUTH_HANDLER, args, photo_file)

    t = r[0]
    if t.tag == 'photoid':
        return Photo(id=t.text)
    elif t.tag == 'ticketid':
        return UploadTicket(id=t.text, secret=t.secret)
    else:
        raise FlickrError("Unexpected tag: %s" % t.tag)

########NEW FILE########
__FILENAME__ = _version
""" Version module.

    Allows to define the version number uniquely.
"""

__version__ = "0.5"

########NEW FILE########
__FILENAME__ = download_album
import flickr_api as f
import sys
import os

try :
    username = sys.argv[1]
    photoset_idx = int(sys.argv[2])
    try :
        access_token = sys.argv[3]
        f.set_auth_handler(access_token)
    except IndexError : pass
    u = f.Person.findByUserName(username)
    ps = u.getPhotosets()[photoset_idx]

    if not os.path.exists(ps.title) : os.mkdir(ps.title)
    os.chdir(ps.title)

    for p in ps.getPhotos() :
        p.save(p.title+".jpg")
except IndexError :
    print "usage: python download_album.py username album_idx [access_token_file]"
    print "Downloads the content of a user's album."
    print "'album_idx' stands of the album index as given by the 'show_albums.py'"
    print "script. A new directory with the album title will be created and the"
    print "album content will be downloaded in this directory."





########NEW FILE########
__FILENAME__ = show_albums
import flickr_api as f
import sys

try :
    username = sys.argv[1]
    try :
        access_token = sys.argv[2]
        f.set_auth_handler(access_token)
    except IndexError : pass
    
    u = f.Person.findByUserName(username)
    ps = u.getPhotosets()
    
    for i,p in enumerate(ps) :
        print i,p.title
except IndexError :
    print "usage: python show_albums.py username [access_token_file]"
    print "Displays the list of photosets belonging to a user"

########NEW FILE########
