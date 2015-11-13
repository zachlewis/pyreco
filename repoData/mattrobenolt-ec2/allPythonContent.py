__FILENAME__ = base
"""
ec2.base
~~~~~~~~

:copyright: (c) 2014 by Matt Robenolt.
:license: BSD, see LICENSE for more details.
"""

from ec2.helpers import make_compare


class _EC2MetaClass(type):
    "Metaclass for all EC2 filter type classes"

    def __new__(cls, name, bases, attrs):
        # Append MultipleObjectsReturned and DoesNotExist exceptions
        for contrib in ('MultipleObjectsReturned', 'DoesNotExist'):
            attrs[contrib] = type(contrib, (Exception,), {})
        return super(_EC2MetaClass, cls).__new__(cls, name, bases, attrs)


class objects_base(object):
    "Base class for all EC2 filter type classes"

    __metaclass__ = _EC2MetaClass

    @classmethod
    def all(cls):
        """
        Wrapper around _all() to cache and return all results of something

        >>> ec2.instances.all()
        [ ... ]
        """
        if not hasattr(cls, '_cache'):
            cls._cache = cls._all()
        return cls._cache

    @classmethod
    def get(cls, **kwargs):
        """
        Generic get() for one item only

        >>> ec2.instances.get(name='production-web-01')
        <Instance: ...>
        """
        things = cls.filter(**kwargs)
        if len(things) > 1:
            # Raise an exception if more than one object is matched
            raise cls.MultipleObjectsReturned
        elif len(things) == 0:
            # Rase an exception if no objects were matched
            raise cls.DoesNotExist
        return things[0]

    @classmethod
    def filter(cls, **kwargs):
        """
        The meat. Filtering using Django model style syntax.

        All kwargs are translated into attributes on the underlying objects.
        If the attribute is not found, it looks for a similar key
        in the tags.

        There are a couple comparisons to check against as well:
            exact: check strict equality
            iexact: case insensitive exact
            like: check against regular expression
            ilike: case insensitive like
            contains: check if string is found with attribute
            icontains: case insensitive contains
            startswith: check if attribute value starts with the string
            istartswith: case insensitive startswith
            endswith: check if attribute value ends with the string
            iendswith: case insensitive startswith
            isnull: check if the attribute does not exist

        >>> ec2.instances.filter(name__startswith='production')
        [ ... ]
        """
        qs = cls.all()
        for key in kwargs:
            qs = filter(lambda i: make_compare(key, kwargs[key], i), qs)
        return qs

    @classmethod
    def clear(cls):
        "Clear the cached instances"
        try:
            del cls._cache
        except AttributeError:
            pass

########NEW FILE########
__FILENAME__ = connection
"""
ec2.connection
~~~~~~~~~~~~~~

:copyright: (c) 2014 by Matt Robenolt.
:license: BSD, see LICENSE for more details.
"""

import os
import boto.ec2
import boto.vpc

_connection = None
_vpc_connection = None


def get_connection():
    "Cache a global connection object to be used by all classes"
    global _connection
    if _connection is None:
        _connection = boto.ec2.connect_to_region(**credentials())
    return _connection


def get_vpc_connection():
    global _vpc_connection
    if _vpc_connection is None:
        _vpc_connection = boto.vpc.connect_to_region(**credentials())
    return _vpc_connection


class credentials(object):
    """
    Simple credentials singleton that holds our fun AWS info
    and masquerades as a dict
    """
    ACCESS_KEY_ID = None
    SECRET_ACCESS_KEY = None
    REGION_NAME = 'us-east-1'

    def keys(self):
        return ['aws_access_key_id', 'aws_secret_access_key', 'region_name']

    def __getitem__(self, item):
        item = item.upper()
        return (
            os.environ.get(item) or
            getattr(self, item, None) or
            getattr(self, item[4:])
        )

    @classmethod
    def from_file(cls, filename):
        """
        Load ACCESS_KEY_ID and SECRET_ACCESS_KEY from csv
        generated by Amazon's IAM.

        >>> ec2.credentials.from_file('credentials.csv')
        """
        import csv
        with open(filename, 'r') as f:
            reader = csv.DictReader(f)
            row = reader.next()  # Only one row in the file
        try:
            cls.ACCESS_KEY_ID = row['Access Key Id']
            cls.SECRET_ACCESS_KEY = row['Secret Access Key']
        except KeyError:
            raise IOError('Invalid credentials format')

########NEW FILE########
__FILENAME__ = helpers
"""
ec2.helpers
~~~~~~~~~~~

:copyright: (c) 2014 by Matt Robenolt.
:license: BSD, see LICENSE for more details.
"""

import re


def make_compare(key, value, obj):
    "Map a key name to a specific comparison function"
    if '__' not in key:
        # If no __ exists, default to doing an "exact" comparison
        key, comp = key, 'exact'
    else:
        key, comp = key.rsplit('__', 1)
    # Check if comp is valid
    if hasattr(Compare, comp):
        return getattr(Compare, comp)(key, value, obj)
    raise AttributeError("No comparison '%s'" % comp)


class Compare(object):
    "Private class, namespacing comparison functions."

    @staticmethod
    def exact(key, value, obj):
        try:
            return getattr(obj, key) == value
        except AttributeError:
            # Fall back to checking tags
            if hasattr(obj, 'tags'):
                for tag in obj.tags:
                    if key == tag.lower():
                        return obj.tags[tag] == value
            # There is no tag found either
            return False

    @staticmethod
    def iexact(key, value, obj):
        value = value.lower()
        try:
            return getattr(obj, key).lower() == value
        except AttributeError:
            # Fall back to checking tags
            if hasattr(obj, 'tags'):
                for tag in obj.tags:
                    if key == tag.lower():
                        return obj.tags[tag].lower() == value
            # There is no tag found either
            return False

    @staticmethod
    def like(key, value, obj):
        if isinstance(value, basestring):
            # If a string is passed in,
            # we want to convert it to a pattern object
            value = re.compile(value)
        try:
            return bool(value.match(getattr(obj, key)))
        except AttributeError:
            # Fall back to checking tags
            if hasattr(obj, 'tags'):
                for tag in obj.tags:
                    if key == tag.lower():
                        return bool(value.match(obj.tags[tag]))
            # There is no tag found either
            return False
    # Django alias
    regex = like

    @staticmethod
    def ilike(key, value, obj):
        return Compare.like(key, re.compile(value, re.I), obj)
    # Django alias
    iregex = ilike

    @staticmethod
    def contains(key, value, obj):
        try:
            return value in getattr(obj, key)
        except AttributeError:
            # Fall back to checking tags
            if hasattr(obj, 'tags'):
                for tag in obj.tags:
                    if key == tag.lower():
                        return value in obj.tags[tag]
            # There is no tag found either
            return False

    @staticmethod
    def icontains(key, value, obj):
        value = value.lower()
        try:
            return value in getattr(obj, key).lower()
        except AttributeError:
            # Fall back to checking tags
            if hasattr(obj, 'tags'):
                for tag in obj.tags:
                    if key == tag.lower():
                        return value in obj.tags[tag]
            # There is no tag found either
            return False

    @staticmethod
    def startswith(key, value, obj):
        try:
            return getattr(obj, key).startswith(value)
        except AttributeError:
            # Fall back to checking tags
            if hasattr(obj, 'tags'):
                for tag in obj.tags:
                    if key == tag.lower():
                        return obj.tags[tag].startswith(value)
            # There is no tag found either
            return False

    @staticmethod
    def istartswith(key, value, obj):
        value = value.lower()
        try:
            return getattr(obj, key).startswith(value)
        except AttributeError:
            # Fall back to checking tags
            if hasattr(obj, 'tags'):
                for tag in obj.tags:
                    if key == tag.lower():
                        return obj.tags[tag].lower().startswith(value)
            # There is no tag found either
            return False

    @staticmethod
    def endswith(key, value, obj):
        try:
            return getattr(obj, key).endswith(value)
        except AttributeError:
            # Fall back to checking tags
            if hasattr(obj, 'tags'):
                for tag in obj.tags:
                    if key == tag.lower():
                        return obj.tags[tag].endswith(value)
            # There is no tag found either
            return False

    @staticmethod
    def iendswith(key, value, obj):
        value = value.lower()
        try:
            return getattr(obj, key).endswith(value)
        except AttributeError:
            # Fall back to checking tags
            if hasattr(obj, 'tags'):
                for tag in obj.tags:
                    if key == tag.lower():
                        return obj.tags[tag].lower().endswith(value)
            # There is no tag found either
            return False

    @staticmethod
    def isnull(key, value, obj):
        try:
            return (getattr(obj, key) is None) == value
        except AttributeError:
            # Fall back to checking tags
            if hasattr(obj, 'tags'):
                for tag in obj.tags:
                    if key == tag.lower():
                        return (obj.tags[tag] is None) and value
            # There is no tag found either, so must be null
            return True and value

########NEW FILE########
__FILENAME__ = types
"""
ec2.types
~~~~~~~~~

:copyright: (c) 2014 by Matt Robenolt.
:license: BSD, see LICENSE for more details.
"""

from ec2.connection import get_connection, get_vpc_connection
from ec2.base import objects_base


class instances(objects_base):
    "Singleton to stem off queries for instances"

    @classmethod
    def _all(cls):
        "Grab all AWS instances"
        return [
            i for r in get_connection().get_all_instances()
            for i in r.instances
        ]


class security_groups(objects_base):
    "Singleton to stem off queries for security groups"

    @classmethod
    def _all(cls):
        "Grab all AWS Security Groups"
        return get_connection().get_all_security_groups()


class vpcs(objects_base):
    "Singleton to stem off queries for virtual private clouds"

    @classmethod
    def _all(cls):
        "Grab all AWS Virtual Private Clouds"
        return get_vpc_connection().get_all_vpcs()

########NEW FILE########
__FILENAME__ = example
import ec2

ec2.credentials.ACCESS_KEY_ID = 'xxx'
ec2.credentials.SECRET_ACCESS_KEY = 'xxx'
ec2.credentials.REGION_NAME = 'us-west-2'
# ec2.credentials.from_file('credentials.csv')

print ec2.instances.all()
for i in ec2.instances.filter(state__iexact='rUnning', name__endswith='01', name__startswith='production'):
    print i.tags['Name']
print ec2.instances.filter(id__iregex=r'^I\-')

print ec2.security_groups.all()
for g in ec2.security_groups.filter(name__istartswith='production'):
    print g.description

########NEW FILE########
__FILENAME__ = base
from boto.ec2.instance import Instance, InstanceState

from boto.ec2.securitygroup import SecurityGroup
from boto.vpc.vpc import VPC
from mock import MagicMock, patch
import unittest

import ec2

RUNNING_STATE = InstanceState(16, 'running')
STOPPED_STATE = InstanceState(64, 'stopped')


class BaseTestCase(unittest.TestCase):
    def setUp(self):
        ec2.credentials.ACCESS_KEY_ID = 'abc'
        ec2.credentials.SECRET_ACCESS_KEY = 'xyz'

        # Build up two reservations, with two instances each, totalling 4 instances
        # Two running, two stopped
        reservations = []
        instance_count = 0
        for i in xrange(2):
            i1 = Instance()
            i1.id = 'i-abc%d' % instance_count
            i1._state = RUNNING_STATE
            i1.tags = {'Name': 'instance-%d' % instance_count}
            instance_count += 1
            i2 = Instance()
            i2.id = 'i-abc%d' % instance_count
            i2._state = STOPPED_STATE
            i2.tags = {'Name': 'instance-%d' % instance_count}
            instance_count += 1
            reservation = MagicMock()
            reservation.instances.__iter__ = MagicMock(return_value=iter([i1, i2]))
            reservations.append(reservation)

        security_groups = []
        for i in xrange(2):
            sg = SecurityGroup()
            sg.id = 'sg-abc%d' % i
            sg.name = 'group-%d' % i
            sg.description = 'Group %d' % i
            security_groups.append(sg)

        vpcs = []
        for i in xrange(2):
            vpc = VPC()
            vpc.id = 'vpc-abc%d' % i
            if i % 2:
                vpc.state = 'pending'
                vpc.is_default = False
                vpc.instance_tenancy = 'default'
            else:
                vpc.state = 'available'
                vpc.is_default = True
                vpc.instance_tenancy = 'dedicated'
            vpc.cidr_block = '10.%d.0.0/16' % i
            vpc.dhcp_options_id = 'dopt-abc%d' % i
            vpcs.append(vpc)

        self.connection = MagicMock()
        self.connection.get_all_instances = MagicMock(return_value=reservations)
        self.connection.get_all_security_groups = MagicMock(return_value=security_groups)

        self.vpc_connection = MagicMock()
        self.vpc_connection.get_all_vpcs = MagicMock(return_value=vpcs)

    def tearDown(self):
        ec2.credentials.ACCESS_KEY_ID = None
        ec2.credentials.SECRET_ACCESS_KEY = None
        ec2.credentials.REGION_NAME = 'us-east-1'
        ec2.instances.clear()
        ec2.security_groups.clear()
        ec2.vpcs.clear()

    def _patch_connection(self):
        return patch('ec2.types.get_connection', return_value=self.connection)

    def _patch_vpc_connection(self):
        return patch('ec2.types.get_vpc_connection', return_value=self.vpc_connection)

########NEW FILE########
__FILENAME__ = test_connection
from .base import BaseTestCase
from mock import patch

import ec2


class ConnectionTestCase(BaseTestCase):
    def test_connect(self):
        with patch('boto.ec2.connect_to_region') as mock:
            ec2.connection.get_connection()
            mock.assert_called_once_with(aws_access_key_id='abc', aws_secret_access_key='xyz', region_name='us-east-1')

        with patch('boto.vpc.connect_to_region') as mock:
            ec2.connection.get_vpc_connection()
            mock.assert_called_once_with(aws_access_key_id='abc', aws_secret_access_key='xyz', region_name='us-east-1')


class CredentialsTestCase(BaseTestCase):
    def test_credentials(self):
        self.assertEquals(dict(**ec2.credentials()), {'aws_access_key_id': 'abc', 'aws_secret_access_key': 'xyz', 'region_name': 'us-east-1'})

    def test_from_bad_file(self):
        self.assertRaises(
            IOError,
            ec2.credentials.from_file,
            'tests/base.py'
        )

    def test_from_file(self):
        ec2.credentials.from_file('tests/credentials.csv')
        self.assertEquals(dict(**ec2.credentials()), {'aws_access_key_id': 'foo', 'aws_secret_access_key': 'bar', 'region_name': 'us-east-1'})

########NEW FILE########
__FILENAME__ = test_helpers
from .base import RUNNING_STATE
from boto.ec2.instance import Instance
from mock import patch
import unittest
import re

import ec2


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.instance = Instance()
        self.instance._state = RUNNING_STATE
        self.instance.id = 'i-abc'
        self.instance.tags = {'Name': 'awesome'}

    def test_comp(self):
        i = self.instance

        self.assertRaises(AttributeError, ec2.helpers.make_compare, 'state__nope', 'running', i)

        with patch('ec2.helpers.Compare.exact') as mock:
            ec2.helpers.make_compare('state', 'running', i)
            mock.assert_called_once_with('state', 'running', i)

        with patch('ec2.helpers.Compare.exact') as mock:
            ec2.helpers.make_compare('state__exact', 'running', i)
            mock.assert_called_once_with('state', 'running', i)

        with patch('ec2.helpers.Compare.iexact') as mock:
            ec2.helpers.make_compare('state__iexact', 'running', i)
            mock.assert_called_once_with('state', 'running', i)

        with patch('ec2.helpers.Compare.like') as mock:
            ec2.helpers.make_compare('state__like', 'running', i)
            mock.assert_called_once_with('state', 'running', i)

        with patch('ec2.helpers.Compare.regex') as mock:
            ec2.helpers.make_compare('state__regex', 'running', i)
            mock.assert_called_once_with('state', 'running', i)

        with patch('ec2.helpers.Compare.ilike') as mock:
            ec2.helpers.make_compare('state__ilike', 'running', i)
            mock.assert_called_once_with('state', 'running', i)

        with patch('ec2.helpers.Compare.iregex') as mock:
            ec2.helpers.make_compare('state__iregex', 'running', i)
            mock.assert_called_once_with('state', 'running', i)

        with patch('ec2.helpers.Compare.contains') as mock:
            ec2.helpers.make_compare('state__contains', 'running', i)
            mock.assert_called_once_with('state', 'running', i)

        with patch('ec2.helpers.Compare.icontains') as mock:
            ec2.helpers.make_compare('state__icontains', 'running', i)
            mock.assert_called_once_with('state', 'running', i)

        with patch('ec2.helpers.Compare.startswith') as mock:
            ec2.helpers.make_compare('state__startswith', 'running', i)
            mock.assert_called_once_with('state', 'running', i)

        with patch('ec2.helpers.Compare.istartswith') as mock:
            ec2.helpers.make_compare('state__istartswith', 'running', i)
            mock.assert_called_once_with('state', 'running', i)

        with patch('ec2.helpers.Compare.endswith') as mock:
            ec2.helpers.make_compare('state__endswith', 'running', i)
            mock.assert_called_once_with('state', 'running', i)

        with patch('ec2.helpers.Compare.iendswith') as mock:
            ec2.helpers.make_compare('state__iendswith', 'running', i)
            mock.assert_called_once_with('state', 'running', i)

        with patch('ec2.helpers.Compare.isnull') as mock:
            ec2.helpers.make_compare('state__isnull', True, i)
            mock.assert_called_once_with('state', True, i)

    def test_exact(self):
        i = self.instance
        self.assertTrue(ec2.helpers.Compare.exact('state', 'running', i))
        self.assertFalse(ec2.helpers.Compare.exact('state', 'notrunning', i))
        self.assertTrue(ec2.helpers.Compare.exact('name', 'awesome', i))
        self.assertFalse(ec2.helpers.Compare.exact('name', 'notawesome', i))

    def test_iexact(self):
        i = self.instance
        self.assertTrue(ec2.helpers.Compare.iexact('state', 'RUNNING', i))
        self.assertFalse(ec2.helpers.Compare.iexact('state', 'NOTRUNNING', i))
        self.assertTrue(ec2.helpers.Compare.iexact('name', 'AWESOME', i))
        self.assertFalse(ec2.helpers.Compare.iexact('name', 'NOTAWESOME', i))

    def test_like(self):
        i = self.instance
        self.assertTrue(ec2.helpers.Compare.like('state', r'^r.+g$', i))
        self.assertTrue(ec2.helpers.Compare.like('state', re.compile(r'^r.+g$'), i))
        self.assertFalse(ec2.helpers.Compare.like('state', r'^n.+g$', i))
        self.assertFalse(ec2.helpers.Compare.like('state', re.compile(r'^n.+g$'), i))
        self.assertTrue(ec2.helpers.Compare.like('name', r'^a.+e$', i))
        self.assertTrue(ec2.helpers.Compare.like('name', re.compile(r'^a.+e$'), i))
        self.assertFalse(ec2.helpers.Compare.like('name', r'^n.+e$', i))
        self.assertFalse(ec2.helpers.Compare.like('name', re.compile(r'^n.+e$'), i))

    def test_regex(self):
        i = self.instance
        self.assertTrue(ec2.helpers.Compare.regex('state', r'^r.+g$', i))
        self.assertTrue(ec2.helpers.Compare.regex('state', re.compile(r'^r.+g$'), i))
        self.assertFalse(ec2.helpers.Compare.regex('state', r'^n.+g$', i))
        self.assertFalse(ec2.helpers.Compare.regex('state', re.compile(r'^n.+g$'), i))
        self.assertTrue(ec2.helpers.Compare.regex('name', r'^a.+e$', i))
        self.assertTrue(ec2.helpers.Compare.regex('name', re.compile(r'^a.+e$'), i))
        self.assertFalse(ec2.helpers.Compare.regex('name', r'^n.+e$', i))
        self.assertFalse(ec2.helpers.Compare.regex('name', re.compile(r'^n.+e$'), i))

    def test_ilike(self):
        i = self.instance
        self.assertTrue(ec2.helpers.Compare.ilike('state', r'^R.+G$', i))
        self.assertFalse(ec2.helpers.Compare.ilike('state', r'^N.+G$', i))
        self.assertTrue(ec2.helpers.Compare.ilike('name', r'^A.+E$', i))
        self.assertFalse(ec2.helpers.Compare.ilike('name', r'^N.+E$', i))

    def test_iregex(self):
        i = self.instance
        self.assertTrue(ec2.helpers.Compare.iregex('state', r'^R.+G$', i))
        self.assertFalse(ec2.helpers.Compare.iregex('state', r'^N.+G$', i))
        self.assertTrue(ec2.helpers.Compare.iregex('name', r'^A.+E$', i))
        self.assertFalse(ec2.helpers.Compare.iregex('name', r'^N.+E$', i))

    def test_contains(self):
        i = self.instance
        self.assertTrue(ec2.helpers.Compare.contains('state', 'unn', i))
        self.assertFalse(ec2.helpers.Compare.contains('state', 'notunn', i))
        self.assertTrue(ec2.helpers.Compare.contains('name', 'wes', i))
        self.assertFalse(ec2.helpers.Compare.contains('name', 'notwes', i))

    def test_icontains(self):
        i = self.instance
        self.assertTrue(ec2.helpers.Compare.icontains('state', 'UNN', i))
        self.assertFalse(ec2.helpers.Compare.icontains('state', 'NOTUNN', i))
        self.assertTrue(ec2.helpers.Compare.icontains('name', 'WES', i))
        self.assertFalse(ec2.helpers.Compare.icontains('name', 'NOTWES', i))

    def test_startswith(self):
        i = self.instance
        self.assertTrue(ec2.helpers.Compare.startswith('state', 'run', i))
        self.assertFalse(ec2.helpers.Compare.startswith('state', 'notrun', i))
        self.assertTrue(ec2.helpers.Compare.startswith('name', 'awe', i))
        self.assertFalse(ec2.helpers.Compare.startswith('name', 'notawe', i))

    def test_istartswith(self):
        i = self.instance
        self.assertTrue(ec2.helpers.Compare.istartswith('state', 'RUN', i))
        self.assertFalse(ec2.helpers.Compare.istartswith('state', 'NOTRUN', i))
        self.assertTrue(ec2.helpers.Compare.istartswith('name', 'AWE', i))
        self.assertFalse(ec2.helpers.Compare.istartswith('name', 'NOTAWE', i))

    def test_endswith(self):
        i = self.instance
        self.assertTrue(ec2.helpers.Compare.endswith('state', 'ing', i))
        self.assertFalse(ec2.helpers.Compare.endswith('state', 'noting', i))
        self.assertTrue(ec2.helpers.Compare.endswith('name', 'some', i))
        self.assertFalse(ec2.helpers.Compare.endswith('name', 'notsome', i))

    def test_iendswith(self):
        i = self.instance
        self.assertTrue(ec2.helpers.Compare.iendswith('state', 'ING', i))
        self.assertFalse(ec2.helpers.Compare.iendswith('state', 'NOTING', i))
        self.assertTrue(ec2.helpers.Compare.iendswith('name', 'SOME', i))
        self.assertFalse(ec2.helpers.Compare.iendswith('name', 'NOTSOME', i))

    def test_isnull(self):
        i = self.instance
        self.assertTrue(ec2.helpers.Compare.isnull('foo', True, i))
        self.assertFalse(ec2.helpers.Compare.isnull('foo', False, i))
        self.assertFalse(ec2.helpers.Compare.isnull('name', True, i))
        self.assertFalse(ec2.helpers.Compare.isnull('name', False, i))

    def test_unknown_key(self):
        i = self.instance
        for attr in ('exact', 'iexact', 'like', 'ilike', 'contains', 'icontains', 'startswith', 'istartswith', 'endswith', 'iendswith'):
            self.assertFalse(getattr(ec2.helpers.Compare, attr)('lol', 'foo', i))

########NEW FILE########
__FILENAME__ = test_types
from .base import BaseTestCase

import ec2


class InstancesTestCase(BaseTestCase):
    def test_all(self):
        "instances.all() should iterate over all reservations and collect all instances, then cache the results"
        with self._patch_connection() as mock:
            instances = ec2.instances.all()
            self.assertEquals(4, len(instances))
            # all() should cache the connection and list of instances
            # so when calling a second time, _connect() shouldn't
            # be called
            ec2.instances.all()
            mock.assert_called_once()  # Should only be called once from the initial _connect

    def test_filters_integration(self):
        with self._patch_connection():
            instances = ec2.instances.filter(state='crap')
            self.assertEquals(0, len(instances))

            instances = ec2.instances.filter(state='running')
            self.assertEquals(2, len(instances))
            self.assertEquals('running', instances[0].state)
            self.assertEquals('running', instances[1].state)

            instances = ec2.instances.filter(state='stopped')
            self.assertEquals(2, len(instances))
            self.assertEquals('stopped', instances[0].state)
            self.assertEquals('stopped', instances[1].state)

            instances = ec2.instances.filter(id__exact='i-abc0')
            self.assertEquals(1, len(instances))

            instances = ec2.instances.filter(id__iexact='I-ABC0')
            self.assertEquals(1, len(instances))

            instances = ec2.instances.filter(id__like=r'^i\-abc\d$')
            self.assertEquals(4, len(instances))

            instances = ec2.instances.filter(id__ilike=r'^I\-ABC\d$')
            self.assertEquals(4, len(instances))

            instances = ec2.instances.filter(id__contains='1')
            self.assertEquals(1, len(instances))

            instances = ec2.instances.filter(id__icontains='ABC')
            self.assertEquals(4, len(instances))

            instances = ec2.instances.filter(id__startswith='i-')
            self.assertEquals(4, len(instances))

            instances = ec2.instances.filter(id__istartswith='I-')
            self.assertEquals(4, len(instances))

            instances = ec2.instances.filter(id__endswith='c0')
            self.assertEquals(1, len(instances))

            instances = ec2.instances.filter(id__iendswith='C0')
            self.assertEquals(1, len(instances))

            instances = ec2.instances.filter(id__startswith='i-', name__endswith='-0')
            self.assertEquals(1, len(instances))

            instances = ec2.instances.filter(id__isnull=False)
            self.assertEquals(4, len(instances))

            instances = ec2.instances.filter(id__isnull=True)
            self.assertEquals(0, len(instances))

    def test_get_raises(self):
        with self._patch_connection():
            self.assertRaises(
                ec2.instances.MultipleObjectsReturned,
                ec2.instances.get,
                id__startswith='i'
            )

            self.assertRaises(
                ec2.instances.DoesNotExist,
                ec2.instances.get,
                name='crap'
            )

    def test_get(self):
        with self._patch_connection():
            self.assertEquals(ec2.instances.get(id='i-abc0').id, 'i-abc0')


class SecurityGroupsTestCase(BaseTestCase):
    def test_all(self):
        with self._patch_connection() as mock:
            groups = ec2.security_groups.all()
            self.assertEquals(2, len(groups))
            # all() should cache the connection and list of instances
            # so when calling a second time, _connect() shouldn't
            # be called
            ec2.security_groups.all()
            mock.assert_called_once()

    def test_filters_integration(self):
        with self._patch_connection():
            groups = ec2.security_groups.filter(name='crap')
            self.assertEquals(0, len(groups))

            groups = ec2.security_groups.filter(id__exact='sg-abc0')
            self.assertEquals(1, len(groups))

            groups = ec2.security_groups.filter(id__iexact='SG-ABC0')
            self.assertEquals(1, len(groups))

            groups = ec2.security_groups.filter(id__like=r'^sg\-abc\d$')
            self.assertEquals(2, len(groups))

            groups = ec2.security_groups.filter(id__ilike=r'^SG\-ABC\d$')
            self.assertEquals(2, len(groups))

            groups = ec2.security_groups.filter(id__contains='1')
            self.assertEquals(1, len(groups))

            groups = ec2.security_groups.filter(id__icontains='ABC')
            self.assertEquals(2, len(groups))

            groups = ec2.security_groups.filter(id__startswith='sg-')
            self.assertEquals(2, len(groups))

            groups = ec2.security_groups.filter(id__istartswith='SG-')
            self.assertEquals(2, len(groups))

            groups = ec2.security_groups.filter(id__endswith='c0')
            self.assertEquals(1, len(groups))

            groups = ec2.security_groups.filter(id__iendswith='C0')
            self.assertEquals(1, len(groups))

            groups = ec2.security_groups.filter(id__startswith='sg-', name__endswith='-0')
            self.assertEquals(1, len(groups))

            groups = ec2.security_groups.filter(id__isnull=False)
            self.assertEquals(2, len(groups))

            groups = ec2.security_groups.filter(id__isnull=True)
            self.assertEquals(0, len(groups))

    def test_get_raises(self):
        with self._patch_connection():
            self.assertRaises(
                ec2.security_groups.MultipleObjectsReturned,
                ec2.security_groups.get,
                id__startswith='sg'
            )

            self.assertRaises(
                ec2.security_groups.DoesNotExist,
                ec2.security_groups.get,
                name='crap'
            )

    def test_get(self):
        with self._patch_connection():
            self.assertEquals(ec2.security_groups.get(id='sg-abc0').id, 'sg-abc0')


class VPCTestCase(BaseTestCase):
    def test_all(self):
        with self._patch_vpc_connection() as mock:
            vpcs = ec2.vpcs.all()
            self.assertEquals(2, len(vpcs))
            ec2.vpcs.all()
            mock.assert_called_once()

    def test_filters_integration(self):
        with self._patch_vpc_connection():
            groups = ec2.vpcs.filter(id__exact='vpc-abc0')
            self.assertEquals(1, len(groups))

            groups = ec2.vpcs.filter(id__iexact='VPC-ABC0')
            self.assertEquals(1, len(groups))

            groups = ec2.vpcs.filter(id__like=r'^vpc\-abc\d$')
            self.assertEquals(2, len(groups))

            groups = ec2.vpcs.filter(id__ilike=r'^VPC\-ABC\d$')
            self.assertEquals(2, len(groups))

            groups = ec2.vpcs.filter(id__contains='1')
            self.assertEquals(1, len(groups))

            groups = ec2.vpcs.filter(id__icontains='ABC')
            self.assertEquals(2, len(groups))

            groups = ec2.vpcs.filter(id__startswith='vpc-')
            self.assertEquals(2, len(groups))

            groups = ec2.vpcs.filter(id__istartswith='vpc-')
            self.assertEquals(2, len(groups))

            groups = ec2.vpcs.filter(id__endswith='c0')
            self.assertEquals(1, len(groups))

            groups = ec2.vpcs.filter(id__iendswith='C0')
            self.assertEquals(1, len(groups))

            groups = ec2.vpcs.filter(id__startswith='vpc-', dhcp_options_id__endswith='abc0')
            self.assertEquals(1, len(groups))

            groups = ec2.vpcs.filter(id__isnull=False)
            self.assertEquals(2, len(groups))

            groups = ec2.vpcs.filter(id__isnull=True)
            self.assertEquals(0, len(groups))

    def test_get_raises(self):
        with self._patch_vpc_connection():
            self.assertRaises(
                ec2.vpcs.MultipleObjectsReturned,
                ec2.vpcs.get,
                id__startswith='vpc'
            )

            self.assertRaises(
                ec2.vpcs.DoesNotExist,
                ec2.vpcs.get,
                name='crap'
            )

    def test_get(self):
        with self._patch_vpc_connection():
            self.assertEquals(ec2.vpcs.get(id='vpc-abc0').id, 'vpc-abc0')

########NEW FILE########
