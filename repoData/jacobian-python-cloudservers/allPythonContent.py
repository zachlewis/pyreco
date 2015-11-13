__FILENAME__ = backup_schedules
from cloudservers import base

BACKUP_WEEKLY_DISABLED  = 'DISABLED'
BACKUP_WEEKLY_SUNDAY    = 'SUNDAY'
BACKUP_WEEKLY_MONDAY    = 'MONDAY'
BACKUP_WEEKLY_TUESDAY   = 'TUESDAY'
BACKUP_WEEKLY_WEDNESDAY = 'WEDNESDAY'
BACKUP_WEEKLY_THURSDAY  = 'THURSDAY'
BACKUP_WEEKLY_FRIDAY    = 'FRIDAY'
BACKUP_WEEKLY_SATURDAY  = 'SATURDAY'

BACKUP_DAILY_DISABLED    = 'DISABLED'
BACKUP_DAILY_H_0000_0200 = 'H_0000_0200'
BACKUP_DAILY_H_0200_0400 = 'H_0200_0400'
BACKUP_DAILY_H_0400_0600 = 'H_0400_0600'
BACKUP_DAILY_H_0600_0800 = 'H_0600_0800'
BACKUP_DAILY_H_0800_1000 = 'H_0800_1000'
BACKUP_DAILY_H_1000_1200 = 'H_1000_1200'
BACKUP_DAILY_H_1200_1400 = 'H_1200_1400'
BACKUP_DAILY_H_1400_1600 = 'H_1400_1600'
BACKUP_DAILY_H_1600_1800 = 'H_1600_1800'
BACKUP_DAILY_H_1800_2000 = 'H_1800_2000'
BACKUP_DAILY_H_2000_2200 = 'H_2000_2200'
BACKUP_DAILY_H_2200_0000 = 'H_2200_0000'

class BackupSchedule(base.Resource):
    """
    Represents the daily or weekly backup schedule for some server.
    """
    def get(self):
        """
        Get this `BackupSchedule` again from the API.
        """
        return self.manager.get(server=self.server)
    
    def delete(self):
        """
        Delete (i.e. disable and remove) this scheduled backup.
        """
        self.manager.delete(server=self.server)
    
    def update(self, enabled=True, weekly=BACKUP_WEEKLY_DISABLED, daily=BACKUP_DAILY_DISABLED):
        """
        Update this backup schedule. 
        
        See :meth:`BackupScheduleManager.create` for details.
        """
        self.manager.create(self.server, enabled, weekly, daily)
    
class BackupScheduleManager(base.Manager):
    """
    Manage server backup schedules.
    """
    resource_class = BackupSchedule
    
    def get(self, server):
        """
        Get the current backup schedule for a server.
        
        :arg server: The server (or its ID).
        :rtype: :class:`BackupSchedule`
        """
        s = base.getid(server)
        schedule = self._get('/servers/%s/backup_schedule' % s, 'backupSchedule')
        schedule.server = server
        return schedule
    
    # Backup schedules use POST for both create and update, so allow both here.
    # Unlike the rest of the API, POST here returns no body, so we can't use the
    # nice little helper methods.
    
    def create(self, server, enabled=True, weekly=BACKUP_WEEKLY_DISABLED, daily=BACKUP_DAILY_DISABLED):
        """
        Create or update the backup schedule for the given server.
        
        :arg server: The server (or its ID).
        :arg enabled: boolean; should this schedule be enabled?
        :arg weekly: Run a weekly backup on this day (one of the `BACKUP_WEEKLY_*` constants)
        :arg daily: Run a daily backup at this time (one of the `BACKUP_DAILY_*` constants)
        """
        s = base.getid(server)
        body = {'backupSchedule': {
            'enabled': enabled, 'weekly': weekly, 'daily': daily
        }}
        self.api.client.post('/servers/%s/backup_schedule' % s, body=body)
        
    update = create
    
    def delete(self, server):
        """
        Remove the scheduled backup for `server`.
        
        :arg server: The server (or its ID).
        """
        s = base.getid(server)
        self._delete('/servers/%s/backup_schedule' % s)
########NEW FILE########
__FILENAME__ = base
"""
Base utilities to build API operation managers and objects on top of.
"""

from cloudservers.exceptions import NotFound

# Python 2.4 compat
try:
    all
except NameError:
    def all(iterable):
        return True not in (not x for x in iterable)

class Manager(object):
    """
    Managers interact with a particular type of API (servers, flavors, images,
    etc.) and provide CRUD operations for them.
    """
    resource_class = None
    
    def __init__(self, api):
        self.api = api

    def _list(self, url, response_key):
        resp, body = self.api.client.get(url)
        return [self.resource_class(self, res) for res in body[response_key]]
    
    def _get(self, url, response_key):
        resp, body = self.api.client.get(url)
        return self.resource_class(self, body[response_key])
    
    def _create(self, url, body, response_key):
        resp, body = self.api.client.post(url, body=body)
        return self.resource_class(self, body[response_key])
        
    def _delete(self, url):
        resp, body = self.api.client.delete(url)
    
    def _update(self, url, body):
        resp, body = self.api.client.put(url, body=body)

class ManagerWithFind(Manager):
    """
    Like a `Manager`, but with additional `find()`/`findall()` methods.
    """
    def find(self, **kwargs):
        """
        Find a single item with attributes matching ``**kwargs``.
        
        This isn't very efficient: it loads the entire list then filters on
        the Python side.
        """
        rl = self.findall(**kwargs)
        try:
            return rl[0]
        except IndexError:
            raise NotFound(404, "No %s matching %s." % (self.resource_class.__name__, kwargs))
        
    def findall(self, **kwargs):
        """
        Find all items with attributes matching ``**kwargs``.
        
        This isn't very efficient: it loads the entire list then filters on
        the Python side.
        """
        found = []
        searches = kwargs.items()
        
        for obj in self.list():
            try:
                if all(getattr(obj, attr) == value for (attr, value) in searches):
                    found.append(obj)
            except AttributeError:
                continue
        
        return found
                    
class Resource(object):
    """
    A resource represents a particular instance of an object (server, flavor,
    etc). This is pretty much just a bag for attributes.
    """
    def __init__(self, manager, info):
        self.manager = manager
        self._info = info
        self._add_details(info)
        
    def _add_details(self, info):
        for (k, v) in info.iteritems():
            setattr(self, k, v)
            
    def __getattr__(self, k):
        self.get()
        if k not in self.__dict__:
            raise AttributeError(k)
        else:
            return self.__dict__[k]
            
    def __repr__(self):
        reprkeys = sorted(k for k in self.__dict__.keys() if k[0] != '_' and k != 'manager')
        info = ", ".join("%s=%s" % (k, getattr(self, k)) for k in reprkeys)
        return "<%s %s>" % (self.__class__.__name__, info)

    def get(self):
        new = self.manager.get(self.id)
        self._add_details(new._info)
        
    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        if hasattr(self, 'id') and hasattr(other, 'id'):
            return self.id == other.id
        return self._info == other._info

def getid(obj):
    """
    Abstracts the common pattern of allowing both an object or an object's ID
    (integer) as a parameter when dealing with relationships.
    """
    try:
        return obj.id
    except AttributeError:
        return int(obj)
########NEW FILE########
__FILENAME__ = client
import time
import urlparse
import urllib
import httplib2
try:
    import json
except ImportError:
    import simplejson as json

# Python 2.5 compat fix
if not hasattr(urlparse, 'parse_qsl'):
    import cgi
    urlparse.parse_qsl = cgi.parse_qsl

import cloudservers
from cloudservers import exceptions

class CloudServersClient(httplib2.Http):
    
    AUTH_URL = 'https://auth.api.rackspacecloud.com/v1.0'
    USER_AGENT = 'python-cloudservers/%s' % cloudservers.__version__
    
    def __init__(self, user, apikey):
        super(CloudServersClient, self).__init__()
        self.user = user
        self.apikey = apikey
        
        self.management_url = None
        self.auth_token = None
        
        # httplib2 overrides
        self.force_exception_to_status_code = True

    def request(self, *args, **kwargs):
        kwargs.setdefault('headers', {})
        kwargs['headers']['User-Agent'] = self.USER_AGENT
        if 'body' in kwargs:
            kwargs['headers']['Content-Type'] = 'application/json'
            kwargs['body'] = json.dumps(kwargs['body'])
            
        resp, body = super(CloudServersClient, self).request(*args, **kwargs)
        if body:
            body = json.loads(body)
        else:
            body = None

        if resp.status in (400, 401, 403, 404, 413, 500):
            raise exceptions.from_response(resp, body)

        return resp, body

    def _cs_request(self, url, method, **kwargs):
        if not self.management_url:
            self.authenticate()

        # Perform the request once. If we get a 401 back then it
        # might be because the auth token expired, so try to
        # re-authenticate and try again. If it still fails, bail.
        try:
            kwargs.setdefault('headers', {})['X-Auth-Token'] = self.auth_token
            resp, body = self.request(self.management_url + url, method, **kwargs)
            return resp, body
        except exceptions.Unauthorized, ex:
            try:
                self.authenticate()
                resp, body = self.request(self.management_url + url, method, **kwargs)
                return resp, body
            except exceptions.Unauthorized:
                raise ex

    def get(self, url, **kwargs):
        url = self._munge_get_url(url)
        return self._cs_request(url, 'GET', **kwargs)
    
    def post(self, url, **kwargs):
        return self._cs_request(url, 'POST', **kwargs)
    
    def put(self, url, **kwargs):
        return self._cs_request(url, 'PUT', **kwargs)
    
    def delete(self, url, **kwargs):
        return self._cs_request(url, 'DELETE', **kwargs)

    def authenticate(self):
        headers = {'X-Auth-User': self.user, 'X-Auth-Key': self.apikey}
        resp, body = self.request(self.AUTH_URL, 'GET', headers=headers)
        self.management_url = resp['x-server-management-url']
        self.auth_token = resp['x-auth-token']
        
    def _munge_get_url(self, url):
        """
        Munge GET URLs to always return uncached content.
        
        The Cloud Servers API caches data *very* agressively and doesn't respect
        cache headers. To avoid stale data, then, we append a little bit of
        nonsense onto GET parameters; this appears to force the data not to be
        cached.
        """
        scheme, netloc, path, query, frag = urlparse.urlsplit(url)
        query = urlparse.parse_qsl(query)
        query.append(('fresh', str(time.time())))
        query = urllib.urlencode(query)
        return urlparse.urlunsplit((scheme, netloc, path, query, frag))

########NEW FILE########
__FILENAME__ = exceptions
class CloudServersException(Exception):
    """
    The base exception class for all exceptions this library raises.
    """
    def __init__(self, code, message=None, details=None):
        self.code = code
        self.message = message or self.__class__.message
        self.details = details
        
    def __str__(self):
        return "%s (HTTP %s)" % (self.message, self.code)

class BadRequest(CloudServersException):
    """
    HTTP 400 - Bad request: you sent some malformed data.
    """
    http_status = 400
    message = "Bad request"

class Unauthorized(CloudServersException):
    """
    HTTP 401 - Unauthorized: bad credentials.
    """
    http_status = 401
    message = "Unauthorized"

class Forbidden(CloudServersException):
    """
    HTTP 403 - Forbidden: your credentials don't give you access to this resource.
    """
    http_status = 403
    message = "Forbidden"
    
class NotFound(CloudServersException):
    """
    HTTP 404 - Not found
    """
    http_status = 404
    message = "Not found"

class OverLimit(CloudServersException):
    """
    HTTP 413 - Over limit: you're over the API limits for this time period.
    """
    http_status = 413
    message = "Over limit"

# In Python 2.4 Exception is old-style and thus doesn't have a __subclasses__()
# so we can do this:
#     _code_map = dict((c.http_status, c) for c in CloudServersException.__subclasses__())
#
# Instead, we have to hardcode it:
_code_map = dict((c.http_status, c) for c in [BadRequest, Unauthorized, Forbidden, NotFound, OverLimit])

def from_response(response, body):
    """
    Return an instance of a CloudServersException or subclass
    based on an httplib2 response. 
    
    Usage::
    
        resp, body = http.request(...)
        if resp.status != 200:
            raise exception_from_response(resp, body)
    """
    cls = _code_map.get(response.status, CloudServersException)
    if body:
        error = body[body.keys()[0]]
        return cls(code=response.status, 
                   message=error.get('message', None),
                   details=error.get('details', None))
    else:
        return cls(code=response.status)
########NEW FILE########
__FILENAME__ = flavors
from cloudservers import base

class Flavor(base.Resource):
    """
    A flavor is an available hardware configuration for a server.
    """
    def __repr__(self):
        return "<Flavor: %s>" % self.name

class FlavorManager(base.ManagerWithFind):
    """
    Manage :class:`Flavor` resources.
    """
    resource_class = Flavor
    
    def list(self):
        """
        Get a list of all flavors.
        
        :rtype: list of :class:`Flavor`.
        """
        return self._list("/flavors/detail", "flavors")
        
    def get(self, flavor):
        """
        Get a specific flavor.
        
        :param flavor: The ID of the :class:`Flavor` to get.
        :rtype: :class:`Flavor`
        """
        return self._get("/flavors/%s" % base.getid(flavor), "flavor")
########NEW FILE########
__FILENAME__ = images
from cloudservers import base

class Image(base.Resource):
    """
    An image is a collection of files used to create or rebuild a server.
    """
    def __repr__(self):
        return "<Image: %s>" % self.name

    def delete(self):
        """
        Delete this image.
        """
        return self.manager.delete(self)

class ImageManager(base.ManagerWithFind):
    """
    Manage :class:`Image` resources.
    """
    resource_class = Image
    
    def get(self, image):
        """
        Get an image.
        
        :param image: The ID of the image to get.
        :rtype: :class:`Image`
        """
        return self._get("/images/%s" % base.getid(image), "image")
    
    def list(self):
        """
        Get a list of all images.
        
        :rtype: list of :class:`Image`
        """
        return self._list("/images/detail", "images")
    
    def create(self, name, server):
        """
        Create a new image by snapshotting a running :class:`Server`
        
        :param name: An (arbitrary) name for the new image.
        :param server: The :class:`Server` (or its ID) to make a snapshot of.
        :rtype: :class:`Image`
        """
        data = {"image": {"serverId": base.getid(server), "name": name}}
        return self._create("/images", data, "image")
        
    def delete(self, image):
        """
        Delete an image.
        
        It should go without saying that you can't delete an image 
        that you didn't create.
        
        :param image: The :class:`Image` (or its ID) to delete.
        """
        self._delete("/images/%s" % base.getid(image))
########NEW FILE########
__FILENAME__ = ipgroups
from cloudservers import base

class IPGroup(base.Resource):
    def __repr__(self):
        return "<IP Group: %s>" % self.name

    def delete(self):
        """
        Delete this group.
        """
        self.manager.delete(self)

class IPGroupManager(base.ManagerWithFind):
    resource_class = IPGroup
    
    def list(self):
        """
        Get a list of all groups.
        
        :rtype: list of :class:`IPGroup`
        """
        return self._list("/shared_ip_groups/detail", "sharedIpGroups")
        
    def get(self, group):
        """
        Get an IP group.
        
        :param group: ID of the image to get.
        :rtype: :class:`IPGroup`
        """
        return self._get("/shared_ip_groups/%s" % base.getid(group), "sharedIpGroup")
    
    def create(self, name, server=None):
        """
        Create a new :class:`IPGroup`
        
        :param name: An (arbitrary) name for the new image.
        :param server: A :class:`Server` (or its ID) to make a member of this group.
        :rtype: :class:`IPGroup`
        """
        data = {"sharedIpGroup": {"name": name}}
        if server:
            data['sharedIpGroup']['server'] = base.getid(server)
        return self._create('/shared_ip_groups', data, "sharedIpGroup")
    
    def delete(self, group):
        """
        Delete a group.
                
        :param group: The :class:`IPGroup` (or its ID) to delete.
        """
        self._delete("/shared_ip_groups/%s" % base.getid(group))

########NEW FILE########
__FILENAME__ = servers
from cloudservers import base

REBOOT_SOFT, REBOOT_HARD = 'SOFT', 'HARD'

class Server(base.Resource):
    def __repr__(self):
        return "<Server: %s>" % self.name
        
    def delete(self):
        """
        Delete (i.e. shut down and delete the image) this server.
        """
        self.manager.delete(self)
        
    def update(self, name=None, password=None):
        """
        Update the name or the password for this server.
        
        :param name: Update the server's name.
        :param password: Update the root password.
        """
        self.manager.update(self, name, password)
    
    def share_ip(self, ipgroup, address, configure=True):
        """
        Share an IP address from the given IP group onto this server.
        
        :param ipgroup: The :class:`IPGroup` that the given address belongs to.
        :param address: The IP address to share.
        :param configure: If ``True``, the server will be automatically
                         configured to use this IP. I don't know why you'd
                         want this to be ``False``.
        """
        self.manager.share_ip(self, ipgroup, address, configure)
    
    def unshare_ip(self, address):
        """
        Stop sharing the given address.
        
        :param address: The IP address to stop sharing.
        """
        self.manager.unshare_ip(self, address)
    
    def reboot(self, type=REBOOT_SOFT):
        """
        Reboot the server.
        
        :param type: either :data:`REBOOT_SOFT` for a software-level reboot,
                     or `REBOOT_HARD` for a virtual power cycle hard reboot.
        """
        self.manager.reboot(self, type)
        
    def rebuild(self, image):
        """
        Rebuild -- shut down and then re-image -- this server.
        
        :param image: the :class:`Image` (or its ID) to re-image with.
        """
        self.manager.rebuild(self, image)
        
    def resize(self, flavor):
        """
        Resize the server's resources.

        :param flavor: the :class:`Flavor` (or its ID) to resize to.
        
        Until a resize event is confirmed with :meth:`confirm_resize`, the old
        server will be kept around and you'll be able to roll back to the old
        flavor quickly with :meth:`revert_resize`. All resizes are
        automatically confirmed after 24 hours.
        """
        self.manager.resize(self, flavor)
        
    def confirm_resize(self):
        """
        Confirm that the resize worked, thus removing the original server.
        """
        self.manager.confirm_resize(self)
        
    def revert_resize(self):
        """
        Revert a previous resize, switching back to the old server.
        """
        self.manager.revert_resize(self)
    
    @property
    def backup_schedule(self):
        """
        This server's :class:`BackupSchedule`.
        """
        return self.manager.api.backup_schedules.get(self)
    
    @property
    def public_ip(self):
        """
        Shortcut to get this server's primary public IP address.
        """
        return self.addresses['public'][0]
    
    @property
    def private_ip(self):
        """
        Shortcut to get this server's primary private IP address.
        """
        return self.addresses['private'][0]
    
class ServerManager(base.ManagerWithFind):
    resource_class = Server
    
    def get(self, server):
        """
        Get a server.
        
        :param server: ID of the :class:`Server` to get.
        :rtype: :class:`Server`
        """
        return self._get("/servers/%s" % base.getid(server), "server")
        
    def list(self):
        """
        Get a list of servers.
        :rtype: list of :class:`Server`
        """
        return self._list("/servers/detail", "servers")
        
    def create(self, name, image, flavor, ipgroup=None, meta=None, files=None):
        """
        Create (boot) a new server.
        
        :param name: Something to name the server.
        :param image: The :class:`Image` to boot with.
        :param flavor: The :class:`Flavor` to boot onto.
        :param ipgroup: An initial :class:`IPGroup` for this server.
        :param meta: A dict of arbitrary key/value metadata to store for this
                     server. A maximum of five entries is allowed, and both
                     keys and values must be 255 characters or less.
        :param files: A dict of files to overrwrite on the server upon boot.
                      Keys are file names (i.e. ``/etc/passwd``) and values
                      are the file contents (either as a string or as a
                      file-like object). A maximum of five entries is allowed,
                      and each file must be 10k or less.
        
        There's a bunch more info about how a server boots in Rackspace's
        official API docs, page 23.
        """
        body = {"server": {
            "name": name,
            "imageId": base.getid(image),
            "flavorId": base.getid(flavor),
        }}
        if ipgroup:
            body["server"]["sharedIpGroupId"] = base.getid(ipgroup)
        if meta:
            body["server"]["metadata"] = meta
        
        # Files are a slight bit tricky. They're passed in a "personality"
        # list to the POST. Each item is a dict giving a file name and the
        # base64-encoded contents of the file. We want to allow passing
        # either an open file *or* some contents as files here.
        if files:
            personality = body['server']['personality'] = []
            for filepath, file_or_string in files.items():
                if hasattr(file_or_string, 'read'):
                    data = file_or_string.read()
                else:
                    data = file_or_string
                personality.append({
                    'path': filepath,
                    'contents': data.encode('base64'),
                })
            
        return self._create("/servers", body, "server")
        
    def update(self, server, name=None, password=None):
        """
        Update the name or the password for a server.
        
        :param server: The :class:`Server` (or its ID) to update.
        :param name: Update the server's name.
        :param password: Update the root password.
        """
        
        if name is None and password is None:
            return
        body = {"server": {}}
        if name:
            body["server"]["name"] = name
        if password:
            body["server"]["adminPass"] = password
        self._update("/servers/%s" % base.getid(server), body)
        
    def delete(self, server):
        """
        Delete (i.e. shut down and delete the image) this server.
        """
        self._delete("/servers/%s" % base.getid(server))

    def share_ip(self, server, ipgroup, address, configure=True):
        """
        Share an IP address from the given IP group onto a server.
        
        :param server: The :class:`Server` (or its ID) to share onto.
        :param ipgroup: The :class:`IPGroup` that the given address belongs to.
        :param address: The IP address to share.
        :param configure: If ``True``, the server will be automatically
                         configured to use this IP. I don't know why you'd
                         want this to be ``False``.
        """
        server = base.getid(server)
        ipgroup = base.getid(ipgroup)
        body = {'shareIp': {'sharedIpGroupId': ipgroup, 'configureServer': configure}}
        self._update("/servers/%s/ips/public/%s" % (server, address), body)
        
    def unshare_ip(self, server, address):
        """
        Stop sharing the given address.

        :param server: The :class:`Server` (or its ID) to share onto.
        :param address: The IP address to stop sharing.
        """
        server = base.getid(server)
        self._delete("/servers/%s/ips/public/%s" % (server, address))

    def reboot(self, server, type=REBOOT_SOFT):
        """
        Reboot a server.
        
        :param server: The :class:`Server` (or its ID) to share onto.
        :param type: either :data:`REBOOT_SOFT` for a software-level reboot,
                     or `REBOOT_HARD` for a virtual power cycle hard reboot.
        """
        self._action('reboot', server, {'type':type})
        
    def rebuild(self, server, image):
        """
        Rebuild -- shut down and then re-image -- a server.
        
        :param server: The :class:`Server` (or its ID) to share onto.
        :param image: the :class:`Image` (or its ID) to re-image with.
        """
        self._action('rebuild', server, {'imageId': base.getid(image)})

    def resize(self, server, flavor):
        """
        Resize a server's resources.

        :param server: The :class:`Server` (or its ID) to share onto.
        :param flavor: the :class:`Flavor` (or its ID) to resize to.
        
        Until a resize event is confirmed with :meth:`confirm_resize`, the old
        server will be kept around and you'll be able to roll back to the old
        flavor quickly with :meth:`revert_resize`. All resizes are
        automatically confirmed after 24 hours.
        """
        self._action('resize', server, {'flavorId': base.getid(flavor)})
        
    def confirm_resize(self, server):
        """
        Confirm that the resize worked, thus removing the original server.
        
        :param server: The :class:`Server` (or its ID) to share onto.
        """
        self._action('confirmResize', server)
        
    def revert_resize(self, server):
        """
        Revert a previous resize, switching back to the old server.
        
        :param server: The :class:`Server` (or its ID) to share onto.
        """
        self._action('revertResize', server)        
        
    def _action(self, action, server, info=None):
        """
        Perform a server "action" -- reboot/rebuild/resize/etc.
        """
        self.api.client.post('/servers/%s/action' % base.getid(server), body={action: info})    
########NEW FILE########
__FILENAME__ = shell
"""
Command-line interface to the Cloud Servers API.
"""

import argparse
import cloudservers
import getpass
import httplib2
import os
import prettytable
import sys
import textwrap

# Choices for flags.
DAY_CHOICES = [getattr(cloudservers, i).lower() 
               for i in dir(cloudservers)
               if i.startswith('BACKUP_WEEKLY_')]
HOUR_CHOICES = [getattr(cloudservers, i).lower()
                for i in dir(cloudservers)
                if i.startswith('BACKUP_DAILY_')]

def pretty_choice_list(l): return ', '.join("'%s'" % i for i in l)

# Sentinal for boot --key
AUTO_KEY = object()

# Decorator for args
def arg(*args, **kwargs):
    def _decorator(func):
        # Because of the sematics of decorator composition if we just append
        # to the options list positional options will appear to be backwards.
        func.__dict__.setdefault('arguments', []).insert(0, (args, kwargs))
        return func
    return _decorator

class CommandError(Exception):
    pass

def env(e):
    return os.environ.get(e, '')

class CloudserversShell(object):
    
    # Hook for the test suite to inject a fake server.
    _api_class = cloudservers.CloudServers
    
    def __init__(self):
        self.parser = argparse.ArgumentParser(
            prog = 'cloudservers',
            description = __doc__.strip(),
            epilog = 'See "cloudservers help COMMAND" for help on a specific command.',
            add_help = False,
            formatter_class = CloudserversHelpFormatter,
        )
        
        # Global arguments        
        self.parser.add_argument('-h', '--help',
            action = 'help',
            help = argparse.SUPPRESS,
        )
        
        self.parser.add_argument('--debug', 
            default = False, 
            action = 'store_true',
            help = argparse.SUPPRESS)
            
        self.parser.add_argument('--username',
            default = env('CLOUD_SERVERS_USERNAME'),
            help = 'Defaults to env[CLOUD_SERVERS_USERNAME].')
            
        self.parser.add_argument('--apikey',
            default = env('CLOUD_SERVERS_API_KEY'),
            help='Defaults to env[CLOUD_SERVERS_API_KEY].')
        
        # Subcommands
        subparsers = self.parser.add_subparsers(metavar='<subcommand>')
        self.subcommands = {}
        
        # Everything that's do_* is a subcommand.
        for attr in (a for a in dir(self) if a.startswith('do_')):
            # I prefer to be hypen-separated instead of underscores.
            command = attr[3:].replace('_', '-')
            callback = getattr(self, attr)
            desc = callback.__doc__ or ''
            help = desc.strip().split('\n')[0]
            arguments = getattr(callback, 'arguments', [])
            
            subparser = subparsers.add_parser(command, 
                help = help,
                description = desc,
                add_help=False,
                formatter_class = CloudserversHelpFormatter
            )
            subparser.add_argument('-h', '--help',
                action = 'help',
                help = argparse.SUPPRESS,
            )
            self.subcommands[command] = subparser
            for (args, kwargs) in arguments:
                subparser.add_argument(*args, **kwargs)
            subparser.set_defaults(func=callback)
    
    def main(self, argv):                
        # Parse args and call whatever callback was selected
        args = self.parser.parse_args(argv)
        
        # Short-circuit and deal with help right away.
        if args.func == self.do_help:
            self.do_help(args)
            return 0
                
        # Deal with global arguments
        if args.debug:
            httplib2.debuglevel = 1
           
        user, apikey = args.username, args.apikey
        if not user:
            raise CommandError("You must provide a username, either via "
                               "--username or via env[CLOUD_SERVERS_USERNAME]")
        if not apikey:
            raise CommandError("You must provide an API key, either via "
                               "--apikey or via env[CLOUD_SERVERS_API_KEY]")

        self.cs = self._api_class(user, apikey)
        try:
            self.cs.authenticate()
        except cloudservers.Unauthorized:
            raise CommandError("Invalid Cloud Servers credentials.")
        
        args.func(args)
        
    @arg('command', metavar='<subcommand>', nargs='?', help='Display help for <subcommand>')
    def do_help(self, args):
        """
        Display help about this program or one of its subcommands.
        """
        if args.command:
            if args.command in self.subcommands:
                self.subcommands[args.command].print_help()
            else:
                raise CommandError("'%s' is not a valid subcommand." % args.command)
        else:
            self.parser.print_help()
    
    @arg('server', metavar='<server>', help='Name or ID of server.')
    @arg('--enable', dest='enabled', default=None, action='store_true', help='Enable backups.')
    @arg('--disable', dest='enabled', action='store_false', help='Disable backups.')
    @arg('--weekly', metavar='<day>', choices=DAY_CHOICES,
         help='Schedule a weekly backup for <day> (one of: %s).' % pretty_choice_list(DAY_CHOICES))
    @arg('--daily', metavar='<time-window>', choices=HOUR_CHOICES,
         help='Schedule a daily backup during <time-window> (one of: %s).' % pretty_choice_list(HOUR_CHOICES))
    def do_backup_schedule(self, args):
        """
        Show or edit the backup schedule for a server.
        
        With no flags, the backup schedule will be shown. If flags are given,
        the backup schedule will be modified accordingly.
        """
        server = self._find_server(args.server)
        
        # If we have some flags, update the backup
        backup = {}
        if args.daily:
            backup['daily'] = getattr(cloudservers, 'BACKUP_DAILY_%s' % args.daily.upper())
        if args.weekly:
            backup['weekly'] = getattr(cloudservers, 'BACKUP_WEEKLY_%s' % args.weekly.upper())
        if args.enabled is not None:
            backup['enabled'] = args.enabled
        if backup:
            server.backup_schedule.update(**backup)
        else:
            print_dict(server.backup_schedule._info)
        
    @arg('server', metavar='<server>', help='Name or ID of server.')
    def do_backup_schedule_delete(self, args):
        """
        Delete the backup schedule for a server.
        """
        server = self._find_server(args.server)
        server.backup_schedule.delete()
    
    @arg('--flavor',
         default = None, 
         metavar = '<flavor>',
         help = "Flavor ID (see 'cloudservers flavors'). Defaults to 256MB RAM instance.")
    @arg('--image', 
         default = None,
         metavar = '<image>',
         help = "Image ID (see 'cloudservers images'). Defaults to Ubuntu 10.04 LTS.")
    @arg('--ipgroup',
         default = None, 
         metavar = '<group>',
         help = "IP group name or ID (see 'cloudservers ipgroup-list').")
    @arg('--meta', 
         metavar = "<key=value>", 
         action = 'append',
         default = [],
         help = "Record arbitrary key/value metadata. May be give multiple times.")
    @arg('--file',
         metavar = "<dst-path=src-path>",
         action = 'append',
         dest = 'files',
         default = [],
         help = "Store arbitrary files from <src-path> locally to <dst-path> "\
                "on the new server. You may store up to 5 files.")
    @arg('--key',
         metavar = '<path>',
         nargs = '?',
         const = AUTO_KEY,
         help = "Key the server with an SSH keypair. Looks in ~/.ssh for a key, "\
                "or takes an explicit <path> to one.")
    @arg('name', metavar='<name>', help='Name for the new server')
    def do_boot(self, args):
        """Boot a new server."""
        flavor = args.flavor or self.cs.flavors.find(ram=256)
        image = args.image or self.cs.images.find(name="Ubuntu 10.04 LTS (lucid)")
        
        # Map --ipgroup <name> to an ID.
        # XXX do this for flavor/image?
        if args.ipgroup:
            ipgroup = self._find_ipgroup(args.ipgroup)
        else:
            ipgroup = None
        
        metadata = dict(v.split('=') for v in args.meta)
            
        files = {}
        for f in args.files:
            dst, src = f.split('=', 1)
            try:
                files[dst] = open(src)
            except IOError, e:
                raise CommandError("Can't open '%s': %s" % (src, e))
        
        if args.key is AUTO_KEY:
            possible_keys = [os.path.join(os.path.expanduser('~'), '.ssh', k)
                             for k in ('id_dsa.pub', 'id_rsa.pub')]
            for k in possible_keys:
                if os.path.exists(k):
                    keyfile = k
                    break
            else:
                raise CommandError("Couldn't find a key file: tried ~/.ssh/id_dsa.pub or ~/.ssh/id_rsa.pub")
        elif args.key:
            keyfile = args.key
        else:
            keyfile = None
            
        if keyfile:
            try:
                files['/root/.ssh/authorized_keys2'] = open(keyfile)
            except IOError, e:
                raise CommandError("Can't open '%s': %s" % (keyfile, e))
        
        server = self.cs.servers.create(args.name, image, flavor, ipgroup, metadata, files)
        print_dict(server._info)
    
    def do_flavor_list(self, args):
        """Print a list of available 'flavors' (sizes of servers)."""
        print_list(self.cs.flavors.list(), ['ID', 'Name', 'RAM', 'Disk'])
    
    def do_image_list(self, args):
        """Print a list of available images to boot from."""
        print_list(self.cs.images.list(), ['ID', 'Name', 'Status'])

    @arg('server', metavar='<server>', help='Name or ID of server.')
    @arg('name', metavar='<name>', help='Name for the new image.')
    def do_image_create(self, args):
        """Create a new image by taking a snapshot of a running server."""
        server = self._find_server(args.server)
        image = self.cs.images.create(args.name, server)
        print_dict(image._info)
    
    @arg('image', metavar='<image>', help='Name or ID of image.')    
    def do_image_delete(self, args):
        """
        Delete an image.
        
        It should go without saying, but you cn only delete images you
        created.
        """
        image = self._find_image(args.image)
        image.delete()

    @arg('server', metavar='<server>', help='Name or ID of server.')
    @arg('group', metavar='<group>', help='Name or ID of group.')
    @arg('address', metavar='<address>', help='IP address to share.')
    def do_ip_share(self, args):
        """Share an IP address from the given IP group onto a server."""
        server = self._find_server(args.server)
        group = self._find_ipgroup(args.group)
        server.share_ip(group, args.address)
    
    @arg('server', metavar='<server>', help='Name or ID of server.')
    @arg('address', metavar='<address>', help='Shared IP address to remove from the server.')
    def do_ip_unshare(self, args):
        """Stop sharing an given address with a server."""
        server = self._find_server(args.server)
        server.unshare_ip(args.address)

    def do_ipgroup_list(self, args):
        """Show IP groups."""
        def pretty_server_list(ipgroup):
            return ", ".join(self.cs.servers.get(id).name for id in ipgroup.servers)
            
        print_list(self.cs.ipgroups.list(), 
                   fields = ['ID', 'Name', 'Server List'], 
                   formatters = {'Server List': pretty_server_list})
        
    @arg('group', metavar='<group>', help='Name or ID of group.')
    def do_ipgroup_show(self, args):
        """Show details about a particular IP group."""
        group = self._find_ipgroup(args.group)
        print_dict(group._info)
    
    @arg('name', metavar='<name>', help='What to name this new group.')
    @arg('server', metavar='<server>', nargs='?',
         help='Server (name or ID) to make a member of this new group.')
    def do_ipgroup_create(self, args):
        """Create a new IP group."""
        if args.server:
            server = self._find_server(args.server)
        else:
            server = None
        group = self.cs.ipgroups.create(args.name, server)
        print_dict(group._info)
        
    @arg('group', metavar='<group>', help='Name or ID of group.')
    def do_ipgroup_delete(self, args):
        """Delete an IP group."""
        self._find_ipgroup(args.group).delete()
    
    def do_list(self, args):
        """List active servers."""
        print_list(self.cs.servers.list(), ['ID', 'Name', 'Status', 'Public IP', 'Private IP'])
    
    @arg('--hard',
        dest = 'reboot_type',
        action = 'store_const',
        const = cloudservers.REBOOT_HARD,
        default = cloudservers.REBOOT_SOFT,
        help = 'Perform a hard reboot (instead of a soft one).')
    @arg('server', metavar='<server>', help='Name or ID of server.')
    def do_reboot(self, args):
        """Reboot a server."""
        self._find_server(args.server).reboot(args.reboot_type)
    
    @arg('server', metavar='<server>', help='Name or ID of server.')
    @arg('image', metavar='<image>', help="Name or ID of new image.")
    def do_rebuild(self, args):
        """Shutdown, re-image, and re-boot a server."""
        server = self._find_server(args.server)
        image = self._find_image(args.image)
        server.rebuild(image)
        
    @arg('server', metavar='<server>', help='Name (old name) or ID of server.')
    @arg('name', metavar='<name>', help='New name for the server.')
    def do_rename(self, args):
        """Rename a server."""
        self._find_server(args.server).update(name=args.name)
    
    @arg('server', metavar='<server>', help='Name or ID of server.')
    @arg('flavor', metavar='<flavor>', help = "Name or ID of new flavor.")
    def do_resize(self, args):
        """Resize a server."""
        server = self._find_server(args.server)
        flavor = self._find_flavor(args.flavor)
        server.resize(flavor)
    
    @arg('server', metavar='<server>', help='Name or ID of server.')
    def do_resize_confirm(self, args):
        """Confirm a previous resize."""
        self._find_server(args.server).confirm_resize()
    
    @arg('server', metavar='<server>', help='Name or ID of server.')
    def do_resize_revert(self, args):
        """Revert a previous resize (and return to the previous VM)."""
        self._find_server(args.server).revert_resize()
    
    @arg('server', metavar='<server>', help='Name or ID of server.')
    def do_root_password(self, args):
        """
        Change the root password for a server.
        """
        server = self._find_server(args.server)
        p1 = getpass.getpass('New password: ')
        p2 = getpass.getpass('Again: ')
        if p1 != p2:
            raise CommandError("Passwords do not match.")
        server.update(password=p1)
    
    @arg('server', metavar='<server>', help='Name or ID of server.')
    def do_show(self, args):
        """Show details about the given server."""
        s = self.cs.servers.get(self._find_server(args.server))
        
        info = s._info.copy()
        addresses = info.pop('addresses')
        for addrtype in addresses:
            info['%s ip' % addrtype] = ', '.join(addresses[addrtype])
        
        info['flavor'] = self._find_flavor(info.pop('flavorId')).name
        info['image'] = self._find_image(info.pop('imageId')).name
        
        print_dict(info)
    
    @arg('server', metavar='<server>', help='Name or ID of server.')
    def do_delete(self, args):
        """Immediately shut down and delete a server."""
        self._find_server(args.server).delete()
        
    def _find_server(self, server):
        """Get a server by name or ID."""
        return self._find_resource(self.cs.servers, server)
    
    def _find_ipgroup(self, group):
        """Get an IP group by name or ID."""
        return self._find_resource(self.cs.ipgroups, group)
    
    def _find_image(self, image):
        """Get an image by name or ID."""
        return self._find_resource(self.cs.images, image)
    
    def _find_flavor(self, flavor):
        """Get a flavor by name, ID, or RAM size."""
        try:
            return self._find_resource(self.cs.flavors, flavor)
        except cloudservers.NotFound:
            return self.cs.flavors.find(ram=flavor)
    
    def _find_resource(self, manager, name_or_id):
        """Helper for the _find_* methods."""
        try:
            if isinstance(name_or_id, int) or name_or_id.isdigit():
                return manager.get(int(name_or_id))
            else:
                return manager.find(name=name_or_id)
        except cloudservers.NotFound:
            raise CommandError("No %s with a name or ID of '%s' exists."
                               % (manager.resource_class.__name__.lower(), name_or_id))

# I'm picky about my shell help.
class CloudserversHelpFormatter(argparse.HelpFormatter):
    def start_section(self, heading):
        # Title-case the headings
        heading = '%s%s' % (heading[0].upper(), heading[1:])
        super(CloudserversHelpFormatter, self).start_section(heading)

# Helpers
def print_list(objs, fields, formatters={}):
    pt = prettytable.PrettyTable([f for f in fields], caching=False)
    pt.aligns = ['l' for f in fields]
    
    for o in objs:
        row = []
        for field in fields:
            if field in formatters:
                row.append(formatters[field](o))
            else:
                row.append(getattr(o, field.lower().replace(' ', '_'), ''))
        pt.add_row(row)
    
    pt.printt(sortby=fields[0])
    
def print_dict(d):
    pt = prettytable.PrettyTable(['Property', 'Value'], caching=False)
    pt.aligns = ['l', 'l']
    [pt.add_row(list(r)) for r in d.iteritems()]
    pt.printt(sortby='Property')

def main():
    try:
        CloudserversShell().main(sys.argv[1:])
    except CommandError, e:
        print >> sys.stderr, e
        sys.exit(1)
########NEW FILE########
__FILENAME__ = conf
# -*- coding: utf-8 -*-
#
# python-cloudservers documentation build configuration file, created by
# sphinx-quickstart on Sun Dec  6 14:19:25 2009.
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
extensions = ['sphinx.ext.autodoc', 'sphinx.ext.intersphinx']

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The encoding of source files.
#source_encoding = 'utf-8'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = u'python-cloudservers'
copyright = u'Jacob Kaplan-Moss'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = '1.2'
# The full version, including alpha/beta/rc tags.
release = '1.2'

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
exclude_trees = ['_build']

# The reST default role (used for this markup: `text`) to use for all documents.
#default_role = None

# If true, '()' will be appended to :func: etc. cross-reference text.
add_function_parentheses = True

# If true, the current module name will be prepended to all description
# unit titles (such as .. function::).
add_module_names = True

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
html_theme = 'nature'

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
htmlhelp_basename = 'python-cloudserversdoc'


# -- Options for LaTeX output --------------------------------------------------

# The paper size ('letter' or 'a4').
#latex_paper_size = 'letter'

# The font size ('10pt', '11pt' or '12pt').
#latex_font_size = '10pt'

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass [howto/manual]).
latex_documents = [
  ('index', 'python-cloudservers.tex', u'python-cloudservers Documentation',
   u'Jacob Kaplan-Moss', 'manual'),
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


# Example configuration for intersphinx: refer to the Python standard library.
intersphinx_mapping = {'http://docs.python.org/': None}

########NEW FILE########
__FILENAME__ = fakeserver
"""
A fake server that "responds" to API methods with pre-canned responses.

All of these responses come from the spec, so if for some reason the spec's
wrong the tests might fail. I've indicated in comments the places where actual
behavior differs from the spec.
"""

import httplib2
import urlparse
import urllib
from nose.tools import assert_equal
from cloudservers import CloudServers
from cloudservers.client import CloudServersClient
from utils import fail, assert_in, assert_not_in, assert_has_keys

class FakeServer(CloudServers):
    def __init__(self, username=None, password=None):
        super(FakeServer, self).__init__('username', 'apikey')
        self.client = FakeClient()

    def assert_called(self, method, url, body=None):
        """
        Assert than an API method was just called.
        """
        expected = (method, url)
        called = self.client.callstack[-1][0:2]

        assert self.client.callstack, "Expected %s %s but no calls were made." % expected
        
        assert expected == called, 'Expected %s %s; got %s %s' % (expected + called)
        
        if body is not None:
            assert_equal(self.client.callstack[-1][2], body)
        
        self.client.callstack = []
        
    def authenticate(self):
        pass

class FakeClient(CloudServersClient):
    def __init__(self):
        self.username = 'username'
        self.apikey = 'apikey'
        self.callstack = []
    
    def _cs_request(self, url, method, **kwargs):
        # Check that certain things are called correctly
        if method in ['GET', 'DELETE']:
            assert_not_in('body', kwargs)
        elif method in ['PUT', 'POST']:
            assert_in('body', kwargs)

        # Call the method
        munged_url = url.strip('/').replace('/', '_').replace('.', '_')
        callback = "%s_%s" % (method.lower(), munged_url)
        if not hasattr(self, callback):
            fail('Called unknown API method: %s %s' % (method, url))
        
        # Note the call
        self.callstack.append((method, url, kwargs.get('body', None)))
        
        status, body = getattr(self, callback)(**kwargs)        
        return httplib2.Response({"status": status}), body

    def _munge_get_url(self, url):
        return url

    #
    # Limits
    # 

    def get_limits(self, **kw):
        return (200, {"limits" : { 
            "rate" : [
                {
                    "verb" : "POST",
                    "URI" : "*",
                    "regex" : ".*",
                    "value" : 10,
                    "remaining" : 2,
                    "unit" : "MINUTE",
                    "resetTime" : 1244425439
                }, 
                {
                    "verb" : "POST",
                    "URI" : "*/servers",
                    "regex" : "^/servers",
                    "value" : 50,
                    "remaining" : 49,
                    "unit" : "DAY", "resetTime" : 1244511839
                },
                {
                    "verb" : "PUT",
                    "URI" : "*",
                    "regex" : ".*",
                    "value" : 10,
                    "remaining" : 2,
                    "unit" : "MINUTE",
                    "resetTime" : 1244425439
                },
                {
                    "verb" : "GET",
                    "URI" : "*changes-since*",
                    "regex" : "changes-since",
                    "value" : 3,
                    "remaining" : 3,
                    "unit" : "MINUTE",
                    "resetTime" : 1244425439
                },
                {
                    "verb" : "DELETE",
                    "URI" : "*",
                    "regex" : ".*",
                    "value" : 100,
                    "remaining" : 100,
                    "unit" : "MINUTE",
                    "resetTime" : 1244425439
                }
            ], 
            "absolute" : {
                "maxTotalRAMSize" : 51200,
                "maxIPGroups" : 50,
                "maxIPGroupMembers" : 25
            }
        }})
        
    #
    # Servers
    #
        
    def get_servers(self, **kw):
        return (200, {"servers": [
            {'id': 1234, 'name': 'sample-server'},
            {'id': 5678, 'name': 'sample-server2'}
        ]})
        
    def get_servers_detail(self, **kw):
        return (200, {"servers" : [
            {
                "id" : 1234,
                "name" : "sample-server",
                "imageId" : 2,
                "flavorId" : 1,
                "hostId" : "e4d909c290d0fb1ca068ffaddf22cbd0",
                "status" : "BUILD",
                "progress" : 60,
                "addresses" : {
                    "public" : ["1.2.3.4", "5.6.7.8"],
                    "private" : ["10.11.12.13"]
                },
                "metadata" : {
                    "Server Label" : "Web Head 1",
                    "Image Version" : "2.1"
                }
            },
            {
                "id" : 5678,
                "name" : "sample-server2",
                "imageId" : 2,
                "flavorId" : 1,
                "hostId" : "9e107d9d372bb6826bd81d3542a419d6",
                "status" : "ACTIVE",
                "addresses" : {
                    "public" : ["9.10.11.12"],
                    "private" : ["10.11.12.14"]
                },
                "metadata" : {
                    "Server Label" : "DB 1"
                }
            }
        ]})
        
    def post_servers(self, body, **kw):
        assert_equal(body.keys(), ['server'])
        assert_has_keys(body['server'], 
                        required = ['name', 'imageId', 'flavorId'],
                        optional = ['sharedIpGroupId', 'metadata', 'personality'])
        if 'personality' in body['server']:
            for pfile in body['server']['personality']:
                assert_has_keys(pfile, required=['path', 'contents'])
        return (202, self.get_servers_1234()[1])
        
    def get_servers_1234(self, **kw):
        r = {'server': self.get_servers_detail()[1]['servers'][0]}
        return (200, r)

    def get_servers_5678(self, **kw):
        r = {'server': self.get_servers_detail()[1]['servers'][1]}
        return (200, r)

    def put_servers_1234(self, body, **kw):
        assert_equal(body.keys(), ['server'])
        assert_has_keys(body['server'], optional=['name', 'adminPass'])
        return (204, None)
            
    def delete_servers_1234(self, **kw):
        return (202, None)
    
    #
    # Server Addresses
    #
    
    def get_servers_1234_ips(self, **kw):
        return (200, {'addresses': self.get_servers_1234()[1]['server']['addresses']})
            
    def get_servers_1234_ips_public(self, **kw):
        return (200, {'public': self.get_servers_1234_ips()[1]['addresses']['public']})
        
    def get_servers_1234_ips_private(self, **kw):
        return (200, {'private': self.get_servers_1234_ips()[1]['addresses']['private']})
    
    def put_servers_1234_ips_public_1_2_3_4(self, body, **kw):
        assert_equal(body.keys(), ['shareIp'])
        assert_has_keys(body['shareIp'], required=['sharedIpGroupId', 'configureServer'])
        return (202, None)
    
    def delete_servers_1234_ips_public_1_2_3_4(self, **kw):
        return (202, None)
        
    #
    # Server actions
    #
    
    def post_servers_1234_action(self, body, **kw):
        assert_equal(len(body.keys()), 1)
        action = body.keys()[0]
        if action == 'reboot':
            assert_equal(body[action].keys(), ['type'])
            assert_in(body[action]['type'], ['HARD', 'SOFT'])
        elif action == 'rebuild':
            assert_equal(body[action].keys(), ['imageId'])
        elif action == 'resize':
            assert_equal(body[action].keys(), ['flavorId'])
        elif action == 'confirmResize':
            assert_equal(body[action], None)
            # This one method returns a different response code
            return (204, None)
        elif action == 'revertResize':
            assert_equal(body[action], None)
        else:
            fail("Unexpected server action: %s" % action)
        return (202, None)
        
    #
    # Flavors
    #
    
    def get_flavors(self, **kw):
        return (200, {'flavors': [
            {'id': 1, 'name': '256 MB Server'},
            {'id': 2, 'name': '512 MB Server'}
        ]})
        
    def get_flavors_detail(self, **kw):
        return (200, {'flavors': [
            {'id': 1, 'name': '256 MB Server', 'ram': 256, 'disk': 10},
            {'id': 2, 'name': '512 MB Server', 'ram': 512, 'disk': 20}
        ]})
        
    def get_flavors_1(self, **kw):
        return (200, {'flavor': self.get_flavors_detail()[1]['flavors'][0]})
    
    def get_flavors_2(self, **kw):
        return (200, {'flavor': self.get_flavors_detail()[1]['flavors'][1]})
    
    #
    # Images
    #
    def get_images(self, **kw):
        return (200, {'images': [
            {'id': 1, 'name': 'CentOS 5.2'},
            {'id': 2, 'name': 'My Server Backup'}
        ]})
        
    def get_images_detail(self, **kw):
        return (200, {'images': [
            {
                'id': 1, 
                'name': 'CentOS 5.2',
                "updated" : "2010-10-10T12:00:00Z",
                "created" : "2010-08-10T12:00:00Z",
                "status" : "ACTIVE"
            },
            {
                "id" : 743,
                "name" : "My Server Backup",
                "serverId" : 12,
                "updated" : "2010-10-10T12:00:00Z",
                "created" : "2010-08-10T12:00:00Z",
                "status" : "SAVING",
                "progress" : 80
            }
        ]})
        
    def get_images_1(self, **kw):
        return (200, {'image': self.get_images_detail()[1]['images'][0]})

    def get_images_2(self, **kw):
        return (200, {'image': self.get_images_detail()[1]['images'][1]})
        
    def post_images(self, body, **kw):
        assert_equal(body.keys(), ['image'])
        assert_has_keys(body['image'], required=['serverId', 'name'])
        return (202, self.get_images_1()[1])
        
    def delete_images_1(self, **kw):
        return (204, None)
    
    #
    # Backup schedules
    #
    def get_servers_1234_backup_schedule(self, **kw):
        return (200, {"backupSchedule" : {
            "enabled" : True,
            "weekly" : "THURSDAY",
            "daily" : "H_0400_0600"
        }})
        
    def post_servers_1234_backup_schedule(self, body, **kw):
        assert_equal(body.keys(), ['backupSchedule'])
        assert_has_keys(body['backupSchedule'], required=['enabled'], optional=['weekly', 'daily'])
        return (204, None)
        
    def delete_servers_1234_backup_schedule(self, **kw):
        return (204, None)
        
    #
    # Shared IP groups
    #
    def get_shared_ip_groups(self, **kw):
        return (200, {'sharedIpGroups': [
            {'id': 1, 'name': 'group1'},
            {'id': 2, 'name': 'group2'},
        ]})
        
    def get_shared_ip_groups_detail(self, **kw):
        return (200, {'sharedIpGroups': [
            {'id': 1, 'name': 'group1', 'servers': [1234]},
            {'id': 2, 'name': 'group2', 'servers': [5678]},
        ]})
        
    def get_shared_ip_groups_1(self, **kw):
        return (200, {'sharedIpGroup': self.get_shared_ip_groups_detail()[1]['sharedIpGroups'][0]})

    def post_shared_ip_groups(self, body, **kw):
        assert_equal(body.keys(), ['sharedIpGroup'])
        assert_has_keys(body['sharedIpGroup'], required=['name'], optional=['server'])
        return (201, {'sharedIpGroup': {
            'id': 10101,
            'name': body['sharedIpGroup']['name'],
            'servers': 'server' in body['sharedIpGroup'] and [body['sharedIpGroup']['server']] or None
        }})
        
    def delete_shared_ip_groups_1(self, **kw):
        return (204, None)
########NEW FILE########
__FILENAME__ = test_auth
import mock
import cloudservers
import httplib2
from nose.tools import assert_raises, assert_equal

def test_authenticate_success():
    cs = cloudservers.CloudServers("username", "apikey")
    auth_response = httplib2.Response({
        'status': 204,
        'x-server-management-url': 'https://servers.api.rackspacecloud.com/v1.0/443470',
        'x-auth-token': '1b751d74-de0c-46ae-84f0-915744b582d1',
    })
    mock_request = mock.Mock(return_value=(auth_response, None))
    
    @mock.patch.object(httplib2.Http, "request", mock_request)
    def test_auth_call():
        cs.client.authenticate()
        mock_request.assert_called_with(cs.client.AUTH_URL, 'GET', 
            headers = {
                'X-Auth-User': 'username',
                'X-Auth-Key': 'apikey',
                'User-Agent': cs.client.USER_AGENT
            })
        assert_equal(cs.client.management_url, auth_response['x-server-management-url'])
        assert_equal(cs.client.auth_token, auth_response['x-auth-token'])

    test_auth_call()

def test_authenticate_failure():
    cs = cloudservers.CloudServers("username", "apikey")
    auth_response = httplib2.Response({'status': 401})
    mock_request = mock.Mock(return_value=(auth_response, None))
    
    @mock.patch.object(httplib2.Http, "request", mock_request)
    def test_auth_call():
        assert_raises(cloudservers.Unauthorized, cs.client.authenticate)
        
    test_auth_call()
        
def test_auth_automatic():
    client = cloudservers.CloudServers("username", "apikey").client
    client.management_url = ''
    mock_request = mock.Mock(return_value=(None, None))
    
    @mock.patch.object(client, 'request', mock_request)
    @mock.patch.object(client, 'authenticate')
    def test_auth_call(m):
        client.get('/')
        m.assert_called()
        mock_request.assert_called()
    
    test_auth_call()
    
def test_auth_manual():
    cs = cloudservers.CloudServers("username", "password")
    
    @mock.patch.object(cs.client, 'authenticate')
    def test_auth_call(m):
        cs.authenticate()
        m.assert_called()

    test_auth_call()
########NEW FILE########
__FILENAME__ = test_backup_schedules

from cloudservers.backup_schedules import *
from fakeserver import FakeServer
from utils import assert_isinstance

cs = FakeServer()

def test_get_backup_schedule():
    s = cs.servers.get(1234)
    
    # access via manager
    b = cs.backup_schedules.get(server=s)
    assert_isinstance(b, BackupSchedule)
    cs.assert_called('GET', '/servers/1234/backup_schedule')
    
    b = cs.backup_schedules.get(server=1234)
    assert_isinstance(b, BackupSchedule)
    cs.assert_called('GET', '/servers/1234/backup_schedule')
    
    # access via instance
    assert_isinstance(s.backup_schedule, BackupSchedule)
    cs.assert_called('GET', '/servers/1234/backup_schedule')
    
    # Just for coverage's sake
    b = s.backup_schedule.get()
    cs.assert_called('GET', '/servers/1234/backup_schedule')
    
def test_create_update_backup_schedule():
    s = cs.servers.get(1234)
    
    # create/update via manager
    cs.backup_schedules.update(
        server = s,
        enabled = True,
        weekly = BACKUP_WEEKLY_THURSDAY,
        daily = BACKUP_DAILY_H_1000_1200
    )
    cs.assert_called('POST', '/servers/1234/backup_schedule')
    
    # and via instance
    s.backup_schedule.update(enabled=False)
    cs.assert_called('POST', '/servers/1234/backup_schedule')
    
def test_delete_backup_schedule():
    s = cs.servers.get(1234)
    
    # delete via manager
    cs.backup_schedules.delete(s)
    cs.assert_called('DELETE', '/servers/1234/backup_schedule')
    cs.backup_schedules.delete(1234)
    cs.assert_called('DELETE', '/servers/1234/backup_schedule')
    
    # and via instance
    s.backup_schedule.delete()
    cs.assert_called('DELETE', '/servers/1234/backup_schedule')

########NEW FILE########
__FILENAME__ = test_base

import mock
import cloudservers.base
from cloudservers import Flavor
from cloudservers.exceptions import NotFound
from cloudservers.base import Resource
from nose.tools import assert_equal, assert_not_equal, assert_raises
from fakeserver import FakeServer

cs = FakeServer()

def test_resource_repr():
    r = Resource(None, dict(foo="bar", baz="spam"))
    assert_equal(repr(r), "<Resource baz=spam, foo=bar>")
    
def test_getid():
    assert_equal(cloudservers.base.getid(4), 4)
    class O(object):
        id = 4
    assert_equal(cloudservers.base.getid(O), 4)
    
def test_resource_lazy_getattr():
    f = Flavor(cs.flavors, {'id': 1})
    assert_equal(f.name, '256 MB Server')
    cs.assert_called('GET', '/flavors/1')
    
    # Missing stuff still fails after a second get
    assert_raises(AttributeError, getattr, f, 'blahblah')
    cs.assert_called('GET', '/flavors/1')

def test_eq():
    # Two resources of the same type with the same id: equal
    r1 = Resource(None, {'id':1, 'name':'hi'})
    r2 = Resource(None, {'id':1, 'name':'hello'})
    assert_equal(r1, r2)

    # Two resoruces of different types: never equal
    r1 = Resource(None, {'id': 1})
    r2 = Flavor(None, {'id': 1})
    assert_not_equal(r1, r2)

    # Two resources with no ID: equal if their info is equal
    r1 = Resource(None, {'name': 'joe', 'age': 12})
    r2 = Resource(None, {'name': 'joe', 'age': 12})
    assert_equal(r1, r2)
    
def test_findall_invalid_attribute():
    # Make sure findall with an invalid attribute doesn't cause errors.
    # The following should not raise an exception.
    cs.flavors.findall(vegetable='carrot')
    
    # However, find() should raise an error
    assert_raises(NotFound, cs.flavors.find, vegetable='carrot')
########NEW FILE########
__FILENAME__ = test_client
import mock
import httplib2
from cloudservers.client import CloudServersClient
from nose.tools import assert_equal

fake_response = httplib2.Response({"status": 200})
fake_body = '{"hi": "there"}'
mock_request = mock.Mock(return_value=(fake_response, fake_body))

def client():
    cl = CloudServersClient("username", "apikey")
    cl.management_url = "http://example.com"
    cl.auth_token = "token"
    return cl

def test_get():
    cl = client()
    
    @mock.patch.object(httplib2.Http, "request", mock_request)
    @mock.patch('time.time', mock.Mock(return_value=1234))
    def test_get_call():
        resp, body = cl.get("/hi")
        mock_request.assert_called_with("http://example.com/hi?fresh=1234", "GET", 
            headers={"X-Auth-Token": "token", "User-Agent": cl.USER_AGENT})
        # Automatic JSON parsing
        assert_equal(body, {"hi":"there"})

    test_get_call()

def test_post():
    cl = client()
    
    @mock.patch.object(httplib2.Http, "request", mock_request)
    def test_post_call():
        cl.post("/hi", body=[1, 2, 3])
        mock_request.assert_called_with("http://example.com/hi", "POST", 
            headers = {
                "X-Auth-Token": "token",
                "Content-Type": "application/json",
                "User-Agent": cl.USER_AGENT},
            body = '[1, 2, 3]'
        )
    
    test_post_call()
########NEW FILE########
__FILENAME__ = test_flavors
from cloudservers import Flavor, NotFound
from fakeserver import FakeServer
from utils import assert_isinstance
from nose.tools import assert_raises, assert_equal

cs = FakeServer()

def test_list_flavors():
    fl = cs.flavors.list()
    cs.assert_called('GET', '/flavors/detail')
    [assert_isinstance(f, Flavor) for f in fl]
    
def test_get_flavor_details():
    f = cs.flavors.get(1)
    cs.assert_called('GET', '/flavors/1')
    assert_isinstance(f, Flavor)
    assert_equal(f.ram, 256)
    assert_equal(f.disk, 10)
    
def test_find():
    f = cs.flavors.find(ram=256)
    cs.assert_called('GET', '/flavors/detail')
    assert_equal(f.name, '256 MB Server')
    
    f = cs.flavors.find(disk=20)
    assert_equal(f.name, '512 MB Server')
    
    assert_raises(NotFound, cs.flavors.find, disk=12345)
########NEW FILE########
__FILENAME__ = test_images
from cloudservers import Image
from fakeserver import FakeServer
from utils import assert_isinstance
from nose.tools import assert_equal

cs = FakeServer()

def test_list_images():
    il = cs.images.list()
    cs.assert_called('GET', '/images/detail')
    [assert_isinstance(i, Image) for i in il]
    
def test_get_image_details():
    i = cs.images.get(1)
    cs.assert_called('GET', '/images/1')
    assert_isinstance(i, Image)
    assert_equal(i.id, 1)
    assert_equal(i.name, 'CentOS 5.2')
    
def test_create_image():
    i = cs.images.create(server=1234, name="Just in case")
    cs.assert_called('POST', '/images')
    assert_isinstance(i, Image)
    
def test_delete_image():
    cs.images.delete(1)
    cs.assert_called('DELETE', '/images/1')
    
def test_find():
    i = cs.images.find(name="CentOS 5.2")
    assert_equal(i.id, 1)
    cs.assert_called('GET', '/images/detail')
    
    iml = cs.images.findall(status='SAVING')
    assert_equal(len(iml), 1)
    assert_equal(iml[0].name, 'My Server Backup')
########NEW FILE########
__FILENAME__ = test_ipgroups
from cloudservers import IPGroup
from fakeserver import FakeServer
from utils import assert_isinstance
from nose.tools import assert_equal

cs = FakeServer()

def test_list_ipgroups():
    ipl = cs.ipgroups.list()
    cs.assert_called('GET', '/shared_ip_groups/detail')
    [assert_isinstance(ipg, IPGroup) for ipg in ipl]
    
def test_get_ipgroup():
    ipg = cs.ipgroups.get(1)
    cs.assert_called('GET', '/shared_ip_groups/1')
    assert_isinstance(ipg, IPGroup)

def test_create_ipgroup():
    ipg = cs.ipgroups.create("My group", 1234)
    cs.assert_called('POST', '/shared_ip_groups')
    assert_isinstance(ipg, IPGroup)

def test_delete_ipgroup():
    ipg = cs.ipgroups.get(1)
    ipg.delete()
    cs.assert_called('DELETE', '/shared_ip_groups/1')
    cs.ipgroups.delete(ipg)
    cs.assert_called('DELETE', '/shared_ip_groups/1')
    cs.ipgroups.delete(1)
    cs.assert_called('DELETE', '/shared_ip_groups/1')
    
def test_find():
    ipg = cs.ipgroups.find(name='group1')
    cs.assert_called('GET', '/shared_ip_groups/detail')
    assert_equal(ipg.name, 'group1')
    ipgl = cs.ipgroups.findall(id=1)
    assert_equal(ipgl, [IPGroup(None, {'id': 1})])
########NEW FILE########
__FILENAME__ = test_servers
import StringIO
from nose.tools import assert_equal
from fakeserver import FakeServer
from utils import assert_isinstance
from cloudservers import Server

cs = FakeServer()

def test_list_servers():
    sl = cs.servers.list()
    cs.assert_called('GET', '/servers/detail')
    [assert_isinstance(s, Server) for s in sl]
    
def test_get_server_details():
    s = cs.servers.get(1234)
    cs.assert_called('GET', '/servers/1234')
    assert_isinstance(s, Server)
    assert_equal(s.id, 1234)
    assert_equal(s.status, 'BUILD')
    
def test_create_server():
    s = cs.servers.create(
        name = "My server",
        image = 1,
        flavor = 1,
        meta = {'foo': 'bar'},
        ipgroup = 1,
        files = {
            '/etc/passwd': 'some data',                 # a file
            '/tmp/foo.txt': StringIO.StringIO('data')   # a stream
        }
    )
    cs.assert_called('POST', '/servers')
    assert_isinstance(s, Server)

def test_update_server():
    s = cs.servers.get(1234)
    
    # Update via instance
    s.update(name='hi')
    cs.assert_called('PUT', '/servers/1234')
    s.update(name='hi', password='there')
    cs.assert_called('PUT', '/servers/1234')
    
    # Silly, but not an error
    s.update()
    
    # Update via manager
    cs.servers.update(s, name='hi')
    cs.assert_called('PUT', '/servers/1234')
    cs.servers.update(1234, password='there')
    cs.assert_called('PUT', '/servers/1234')
    cs.servers.update(s, name='hi', password='there')
    cs.assert_called('PUT', '/servers/1234')
    
def test_delete_server():
    s = cs.servers.get(1234)
    s.delete()
    cs.assert_called('DELETE', '/servers/1234')
    cs.servers.delete(1234)
    cs.assert_called('DELETE', '/servers/1234')
    cs.servers.delete(s)
    cs.assert_called('DELETE', '/servers/1234')
    
def test_find():
    s = cs.servers.find(name='sample-server')
    cs.assert_called('GET', '/servers/detail')
    assert_equal(s.name, 'sample-server')
    
    # Find with multiple results arbitraility returns the first item
    s = cs.servers.find(flavorId=1)
    sl = cs.servers.findall(flavorId=1)
    assert_equal(sl[0], s)
    assert_equal([s.id for s in sl], [1234, 5678])
    
def test_share_ip():
    s = cs.servers.get(1234)
    
    # Share via instance
    s.share_ip(ipgroup=1, address='1.2.3.4')
    cs.assert_called('PUT', '/servers/1234/ips/public/1.2.3.4')
    
    # Share via manager
    cs.servers.share_ip(s, ipgroup=1, address='1.2.3.4', configure=False)
    cs.assert_called('PUT', '/servers/1234/ips/public/1.2.3.4')
    
def test_unshare_ip():
    s = cs.servers.get(1234)
    
    # Unshare via instance
    s.unshare_ip('1.2.3.4')
    cs.assert_called('DELETE', '/servers/1234/ips/public/1.2.3.4')
    
    # Unshare via manager
    cs.servers.unshare_ip(s, '1.2.3.4')
    cs.assert_called('DELETE', '/servers/1234/ips/public/1.2.3.4')

def test_reboot_server():
    s = cs.servers.get(1234)
    s.reboot()
    cs.assert_called('POST', '/servers/1234/action')
    cs.servers.reboot(s, type='HARD')
    cs.assert_called('POST', '/servers/1234/action')
    
def test_rebuild_server():
    s = cs.servers.get(1234)
    s.rebuild(image=1)
    cs.assert_called('POST', '/servers/1234/action')
    cs.servers.rebuild(s, image=1)
    cs.assert_called('POST', '/servers/1234/action')
    
def test_resize_server():
    s = cs.servers.get(1234)
    s.resize(flavor=1)
    cs.assert_called('POST', '/servers/1234/action')
    cs.servers.resize(s, flavor=1)
    cs.assert_called('POST', '/servers/1234/action')
    
def test_confirm_resized_server():
    s = cs.servers.get(1234)
    s.confirm_resize()
    cs.assert_called('POST', '/servers/1234/action')
    cs.servers.confirm_resize(s)
    cs.assert_called('POST', '/servers/1234/action')
    
def test_revert_resized_server():
    s = cs.servers.get(1234)
    s.revert_resize()
    cs.assert_called('POST', '/servers/1234/action')
    cs.servers.revert_resize(s)
    cs.assert_called('POST', '/servers/1234/action')
########NEW FILE########
__FILENAME__ = test_shell
import os
import mock
import httplib2
from nose.tools import assert_raises, assert_equal
from cloudservers.shell import CloudserversShell, CommandError
from fakeserver import FakeServer
from utils import assert_in

# Patch os.environ to avoid required auth info.
def setup():
    global _old_env
    fake_env = {
        'CLOUD_SERVERS_USERNAME': 'username',
        'CLOUD_SERVERS_API_KEY': 'password'
    }
    _old_env, os.environ = os.environ, fake_env.copy()

    # Make a fake shell object, a helping wrapper to call it, and a quick way
    # of asserting that certain API calls were made.
    global shell, _shell, assert_called
    _shell = CloudserversShell()
    _shell._api_class = FakeServer
    assert_called = lambda m, u, b=None: _shell.cs.assert_called(m, u, b)
    shell = lambda cmd: _shell.main(cmd.split())

def teardown():
    global _old_env
    os.environ = _old_env

def test_backup_schedule():
    shell('backup-schedule 1234')
    assert_called('GET', '/servers/1234/backup_schedule')  
      
    shell('backup-schedule sample-server --weekly monday')
    assert_called(
        'POST', '/servers/1234/backup_schedule',
        {'backupSchedule': {'enabled': True, 'daily': 'DISABLED', 
                            'weekly': 'MONDAY'}}
    )
    
    shell('backup-schedule sample-server --weekly disabled --daily h_0000_0200')
    assert_called(
        'POST', '/servers/1234/backup_schedule',
        {'backupSchedule': {'enabled': True, 'daily': 'H_0000_0200', 
                            'weekly': 'DISABLED'}}
    )
    
    shell('backup-schedule sample-server --disable')
    assert_called(
        'POST', '/servers/1234/backup_schedule',
        {'backupSchedule': {'enabled': False, 'daily': 'DISABLED', 
                            'weekly': 'DISABLED'}}
    )

def test_backup_schedule_delete():
    shell('backup-schedule-delete 1234')
    assert_called('DELETE', '/servers/1234/backup_schedule')

def test_boot():
    shell('boot --image 1 some-server')
    assert_called(
        'POST', '/servers',
        {'server': {'flavorId': 1, 'name': 'some-server', 'imageId': 1}}
    )

    shell('boot --image 1 --meta foo=bar --meta spam=eggs some-server ')
    assert_called(
        'POST', '/servers',
        {'server': {'flavorId': 1, 'name': 'some-server', 'imageId': 1, 
                   'metadata': {'foo': 'bar', 'spam': 'eggs'}}}
    )

def test_boot_files():
    testfile = os.path.join(os.path.dirname(__file__), 'testfile.txt')
    expected_file_data = open(testfile).read().encode('base64')
    
    shell('boot some-server --image 1 --file /tmp/foo=%s --file /tmp/bar=%s' % (testfile, testfile))
    
    assert_called(
        'POST', '/servers',
        {'server': {'flavorId': 1, 'name': 'some-server', 'imageId': 1,
                    'personality': [
                        {'path': '/tmp/bar', 'contents': expected_file_data},
                        {'path': '/tmp/foo', 'contents': expected_file_data}
                    ]}
        }
    )
    
def test_boot_invalid_file():
    invalid_file = os.path.join(os.path.dirname(__file__), 'asdfasdfasdfasdf')
    assert_raises(CommandError, shell, 'boot some-server --image 1 --file /foo=%s' % invalid_file)

def test_boot_key_auto():
    mock_exists = mock.Mock(return_value=True)
    mock_open = mock.Mock()
    mock_open.return_value = mock.Mock()
    mock_open.return_value.read = mock.Mock(return_value='SSHKEY')
    
    @mock.patch('os.path.exists', mock_exists)
    @mock.patch('__builtin__.open', mock_open)
    def test_shell_call():
        shell('boot some-server --image 1 --key')
        assert_called(
            'POST', '/servers',
            {'server': {'flavorId': 1, 'name': 'some-server', 'imageId': 1,
                        'personality': [{
                            'path': '/root/.ssh/authorized_keys2', 
                            'contents': ('SSHKEY').encode('base64')},
                        ]}
            }
        )
        
    test_shell_call()

def test_boot_key_auto_no_keys():
    mock_exists = mock.Mock(return_value=False)
    
    @mock.patch('os.path.exists', mock_exists)
    def test_shell_call():
        assert_raises(CommandError, shell, 'boot some-server --image 1 --key')
    
    test_shell_call()

def test_boot_key_file():
    testfile = os.path.join(os.path.dirname(__file__), 'testfile.txt')
    expected_file_data = open(testfile).read().encode('base64')
    shell('boot some-server --image 1 --key %s' % testfile)
    assert_called(
        'POST', '/servers',
        {'server': {'flavorId': 1, 'name': 'some-server', 'imageId': 1,
                    'personality': [
                        {'path': '/root/.ssh/authorized_keys2', 'contents': expected_file_data},
                    ]}
        }
    )

def test_boot_invalid_keyfile():
    invalid_file = os.path.join(os.path.dirname(__file__), 'asdfasdfasdfasdf')
    assert_raises(CommandError, shell, 'boot some-server --image 1 --key %s' % invalid_file)

def test_boot_ipgroup():
    shell('boot --image 1 --ipgroup 1 some-server')
    assert_called(
        'POST', '/servers',
        {'server': {'flavorId': 1, 'name': 'some-server', 'imageId': 1, 'sharedIpGroupId': 1}}
    )

def test_boot_ipgroup_name():
    shell('boot --image 1 --ipgroup group1 some-server')
    assert_called(
        'POST', '/servers',
        {'server': {'flavorId': 1, 'name': 'some-server', 'imageId': 1, 'sharedIpGroupId': 1}}
    )

def test_flavor_list():
    shell('flavor-list')
    assert_called('GET', '/flavors/detail')
    
def test_image_list():
    shell('image-list')
    assert_called('GET', '/images/detail')

def test_image_create():
    shell('image-create sample-server new-image')
    assert_called(
        'POST', '/images',
        {'image': {'name': 'new-image', 'serverId': 1234}}
    )
    
def test_image_delete():
    shell('image-delete 1')
    assert_called('DELETE', '/images/1')

def test_ip_share():
    shell('ip-share sample-server 1 1.2.3.4')
    assert_called(
        'PUT', '/servers/1234/ips/public/1.2.3.4',
        {'shareIp': {'sharedIpGroupId': 1, 'configureServer': True}}
    )
    
def test_ip_unshare():
    shell('ip-unshare sample-server 1.2.3.4')
    assert_called('DELETE', '/servers/1234/ips/public/1.2.3.4')
    
def test_ipgroup_list():
    shell('ipgroup-list')
    assert_in(('GET', '/shared_ip_groups/detail', None), _shell.cs.client.callstack)
    assert_called('GET', '/servers/5678')
    
def test_ipgroup_show():
    shell('ipgroup-show 1')
    assert_called('GET', '/shared_ip_groups/1')
    shell('ipgroup-show group2')
    # does a search, not a direct GET
    assert_called('GET', '/shared_ip_groups/detail')
    
def test_ipgroup_create():
    shell('ipgroup-create a-group')
    assert_called(
        'POST', '/shared_ip_groups',
        {'sharedIpGroup': {'name': 'a-group'}}
    )
    shell('ipgroup-create a-group sample-server')
    assert_called(
        'POST', '/shared_ip_groups',
        {'sharedIpGroup': {'name': 'a-group', 'server': 1234}}
    )
    
def test_ipgroup_delete():
    shell('ipgroup-delete group1')
    assert_called('DELETE', '/shared_ip_groups/1')
    
def test_list():
    shell('list')
    assert_called('GET', '/servers/detail')

def test_reboot():
    shell('reboot sample-server')
    assert_called('POST', '/servers/1234/action', {'reboot': {'type': 'SOFT'}})
    shell('reboot sample-server --hard')
    assert_called('POST', '/servers/1234/action', {'reboot': {'type': 'HARD'}})
    
def test_rebuild():
    shell('rebuild sample-server 1')
    assert_called('POST', '/servers/1234/action', {'rebuild': {'imageId': 1}})

def test_rename():
    shell('rename sample-server newname')
    assert_called('PUT', '/servers/1234', {'server': {'name':'newname'}})

def test_resize():
    shell('resize sample-server 1')
    assert_called('POST', '/servers/1234/action', {'resize': {'flavorId': 1}})

def test_resize_confirm():
    shell('resize-confirm sample-server')
    assert_called('POST', '/servers/1234/action', {'confirmResize': None})
    
def test_resize_revert():
    shell('resize-revert sample-server')
    assert_called('POST', '/servers/1234/action', {'revertResize': None})

@mock.patch('getpass.getpass', mock.Mock(return_value='p'))
def test_root_password():
    shell('root-password sample-server')
    assert_called('PUT', '/servers/1234', {'server': {'adminPass':'p'}})
    
def test_show():
    shell('show 1234')
    # XXX need a way to test multiple calls
    # assert_called('GET', '/servers/1234')
    assert_called('GET', '/images/2')
    
def test_delete():
    shell('delete 1234')
    assert_called('DELETE', '/servers/1234')
    shell('delete sample-server')
    assert_called('DELETE', '/servers/1234')
    
def test_help():
    @mock.patch.object(_shell.parser, 'print_help')
    def test_help(m):
        shell('help')
        m.assert_called()
        
    @mock.patch.object(_shell.subcommands['delete'], 'print_help')
    def test_help_delete(m):
        shell('help delete')
        m.assert_called()
        
    test_help()
    test_help_delete()
        
    assert_raises(CommandError, shell, 'help foofoo')

def test_debug():
    httplib2.debuglevel = 0
    shell('--debug list')
    assert httplib2.debuglevel == 1

########NEW FILE########
__FILENAME__ = utils
from nose.tools import ok_

def fail(msg):
    raise AssertionError(msg)

def assert_in(thing, seq, msg=None):
    msg = msg or "'%s' not found in %s" % (thing, seq)
    ok_(thing in seq, msg)
    
def assert_not_in(thing, seq, msg=None):
    msg = msg or "unexpected '%s' found in %s" % (thing, seq)
    ok_(thing not in seq, msg)
    
def assert_has_keys(dict, required=[], optional=[]):
    keys = dict.keys()
    for k in required:
        assert_in(k, keys, "required key %s missing from %s" % (k, dict))
    allowed_keys = set(required) | set(optional)
    extra_keys = set(keys).difference(set(required + optional))
    if extra_keys:
        fail("found unexpected keys: %s" % list(extra_keys))
    
def assert_isinstance(thing, kls):
    ok_(isinstance(thing, kls), "%s is not an instance of %s" % (thing, kls))
########NEW FILE########
