__FILENAME__ = demo
from twisted.internet import reactor
from twisted.internet import protocol
from twisted.internet import defer

from txredis.client import RedisClient

# Hostname and Port number of a redis server
HOST = 'localhost'
PORT = 6379


@defer.inlineCallbacks
def main():
    clientCreator = protocol.ClientCreator(reactor, RedisClient)
    redis = yield clientCreator.connectTCP(HOST, PORT)

    res = yield redis.ping()
    print res

    info = yield redis.info()
    print info

    res = yield redis.set('test', 42)
    print res

    test = yield redis.get('test')
    print test

    reactor.stop()

if __name__ == "__main__":
    main()
    reactor.run()

########NEW FILE########
__FILENAME__ = demo_hiredis
from twisted.internet import reactor
from twisted.internet import protocol
from twisted.internet import defer

from txredis.client import HiRedisClient

# Hostname and Port number of a redis server
HOST = 'localhost'
PORT = 6379


@defer.inlineCallbacks
def main():
    clientCreator = protocol.ClientCreator(reactor, HiRedisClient)
    redis = yield clientCreator.connectTCP(HOST, PORT)

    res = yield redis.ping()
    print res

    info = yield redis.info()
    print info

    res = yield redis.set('test', 42)
    print res

    test = yield redis.get('test')
    print test

    reactor.stop()

if __name__ == "__main__":
    main()
    reactor.run()

########NEW FILE########
__FILENAME__ = pubsub
from twisted.internet import reactor, protocol, defer
from twisted.python import log

from txredis.client import RedisClient, RedisSubscriber

import sys

REDIS_HOST = 'localhost'
REDIS_PORT = 6379


def getRedisSubscriber():
    clientCreator = protocol.ClientCreator(reactor, RedisSubscriber)
    return clientCreator.connectTCP(REDIS_HOST, REDIS_PORT)


def getRedis():
    clientCreator = protocol.ClientCreator(reactor, RedisClient)
    return clientCreator.connectTCP(REDIS_HOST, REDIS_PORT)


@defer.inlineCallbacks
def runTest():
    redis1 = yield getRedisSubscriber()
    redis2 = yield getRedis()

    log.msg("redis1: SUBSCRIBE w00t")
    response = yield redis1.subscribe("w00t")
    log.msg("subscribed to w00t, response = %r" % response)

    log.msg("redis2: PUBLISH w00t 'Hello, world!'")
    response = yield redis2.publish("w00t", "Hello, world!")
    log.msg("published to w00t, response = %r" % response)

    reactor.stop()


def main():
    log.startLogging(sys.stdout)
    reactor.callLater(0, runTest)
    reactor.run()


if __name__ == "__main__":
    main()

########NEW FILE########
__FILENAME__ = client
"""
@file client.py
"""
import itertools

from twisted.internet import defer
from twisted.internet.protocol import ReconnectingClientFactory

try:
    import hiredis
except ImportError:
    pass

from txredis import exceptions
from txredis.protocol import RedisBase, HiRedisBase


class RedisClient(RedisBase):
    """The main Redis client."""

    def __init__(self, *args, **kwargs):
        RedisBase.__init__(self, *args, **kwargs)

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # REDIS COMMANDS
    #
    def ping(self):
        """
        Test command. Expect PONG as a reply.
        """
        self._send('PING')
        return self.getResponse()

    def shutdown(self):
        """
        Synchronously save the dataset to disk and then shut down the server
        """
        self._send('SHUTDOWN')
        return self.getResponse()

    def slaveof(self, host, port):
        """
        Make the server a slave of another instance, or promote it as master

        The SLAVEOF command can change the replication settings of a slave on
        the fly. If a Redis server is arleady acting as slave, the command
        SLAVEOF NO ONE will turn off the replicaiton turning the Redis server
        into a MASTER. In the proper form SLAVEOF hostname port will make the
        server a slave of the specific server listening at the specified
        hostname and port.

        If a server is already a slave of some master, SLAVEOF hostname port
        will stop the replication against the old server and start the
        synchrnonization against the new one discarding the old dataset.

        The form SLAVEOF no one will stop replication turning the server into a
        MASTER but will not discard the replication. So if the old master stop
        working it is possible to turn the slave into a master and set the
        application to use the new master in read/write. Later when the other
        Redis server will be fixed it can be configured in order to work as
        slave.
        """
        self._send('SLAVEOF', host, port)
        return self.getResponse()

    def get_config(self, pattern):
        """
        Get configuration for Redis at runtime.
        """
        self._send('CONFIG', 'GET', pattern)

        def post_process(values):
            # transform into dict
            res = {}
            if not values:
                return res
            for i in xrange(0, len(values) - 1, 2):
                res[values[i]] = values[i + 1]
            return res
        return self.getResponse().addCallback(post_process)

    def set_config(self, parameter, value):
        """
        Set configuration at runtime.
        """
        self._send('CONFIG', 'SET', parameter, value)
        return self.getResponse()

    # Commands operating on string values
    def set(self, key, value, preserve=False, getset=False, expire=None):
        """
        Set the string value of a key
        """
        # The following will raise an error for unicode values that can't be
        # encoded to ascii. We could probably add an 'encoding' arg to init,
        # but then what do we do with get()? Convert back to unicode? And what
        # about ints, or pickled values?
        if getset:
            command = 'GETSET'
        elif preserve:
            return self.setnx(key, value)
        else:
            command = 'SET'

        if expire:
            self._send('SETEX', key, expire, value)
        else:
            self._send(command, key, value)
        return self.getResponse()

    def setnx(self, key, value):
        """
        Set key to hold string value if key does not exist. In that case, it is
        equal to SET. When key already holds a value, no operation is
        performed. SETNX is short for "SET if Not eXists".
        """
        self._send('SETNX', key, value)
        return self.getResponse()

    def msetnx(self, mapping):
        """
        Sets the given keys to their respective values. MSETNX will not perform
        any operation at all even if just a single key already exists.

        Because of this semantic MSETNX can be used in order to set different
        keys representing different fields of an unique logic object in a way
        that ensures that either all the fields or none at all are set.

        MSETNX is atomic, so all given keys are set at once. It is not possible
        for clients to see that some of the keys were updated while others are
        unchanged.
        """

        self._send('msetnx', *list(itertools.chain(*mapping.iteritems())))
        return self.getResponse()

    def mset(self, mapping, preserve=False):
        """
        Set multiple keys to multiple values
        """
        if preserve:
            command = 'MSETNX'
        else:
            command = 'MSET'
        self._send(command, *list(itertools.chain(*mapping.iteritems())))
        return self.getResponse()

    def append(self, key, value):
        """
        Append a value to a key
        """
        self._send('APPEND', key, value)
        return self.getResponse()

    def getrange(self, key, start, end):
        """
        Get a substring of the string stored at a key
        """
        self._send('GETRANGE', key, start, end)
        return self.getResponse()
    substr = getrange

    def get(self, key):
        """
        Get the value of a key
        """
        self._send('GET', key)
        return self.getResponse()

    def getset(self, key, value):
        """
        Set the string value of a key and return its old value
        """
        return self.set(key, value, getset=True)

    def mget(self, *args):
        """
        Get the values of all the given keys
        """
        self._send('MGET', *args)
        return self.getResponse()

    def incr(self, key, amount=1):
        """
        Increment the integer value of a key by the given amount (default 1)
        """
        if amount == 1:
            self._send('INCR', key)
        else:
            self._send('INCRBY', key, amount)
        return self.getResponse()

    def decr(self, key, amount=1):
        """
        Decrement the integer value of a key by the given amount (default 1)
        """
        if amount == 1:
            self._send('DECR', key)
        else:
            self._send('DECRBY', key, amount)
        return self.getResponse()

    def exists(self, key):
        """
        Determine if a key exists
        """
        self._send('EXISTS', key)
        return self.getResponse()

    def delete(self, key, *keys):
        """
        Delete one or more keys
        """
        self._send('DEL', key, *keys)
        return self.getResponse()

    def get_type(self, key):
        """
        Determine the type stored at key
        """
        self._send('TYPE', key)
        return self.getResponse()

    def get_object(self, key, refcount=False, encoding=False, idletime=False):
        """
        Inspect the internals of Redis objects.
        @param key : The Redis key you want to inspect
        @param refcount: Returns the number of refereces of the value
                         associated with the specified key.
        @param encoding: Returns the kind of internal representation for
                         value.
        @param idletime: Returns the number of seconds since the object stored
                         at the specified key is idle. (Currently the actual
                         resolution is 10 seconds.)
        """
        subcommand = ''
        if idletime:
            subcommand = 'IDLETIME'
        elif encoding:
            subcommand = 'ENCODING'
        elif refcount:
            subcommand = 'REFCOUNT'
        if not subcommand:
            raise exceptions.InvalidCommand('Need a subcommand')
        self._send('OBJECT', subcommand, key)
        return self.getResponse()

    # Bit operations
    def getbit(self, key, offset):
        """
        Returns the bit value at offset in the string value stored at key.

        @param key: The Redis key to get bit from.
        @param offset: The offset to get bit from.
        """
        self._send('GETBIT', key, offset)
        return self.getResponse()

    def setbit(self, key, offset, value):
        """
        Sets the bit value at offset in the string value stored at key.

        @param key: The Redis key to set bit on.
        @param offset: The offset for the bit to set.
        @param value: The bit value (0 or 1)
        """
        self._send('SETBIT', key, offset, value)
        return self.getResponse()

    def bitcount(self, key, start=None, end=None):
        """
        Count the number of set bits (population counting) in a string.

        @param key: The Redis key to get bit count from.
        @param start: Optional starting index for bytes to scan (inclusive)
        @param end: Optional ending index for bytes to scan (inclusive).
                    End index is required when start is given.
        """
        start_end = []
        if start is not None:
            start_end.append(start)
            start_end.append(end)
        self._send('BITCOUNT', key, *start_end)
        return self.getResponse()

    # Commands operating on the key space
    def keys(self, pattern):
        """
        Find all keys matching the given pattern
        """
        self._send('KEYS', pattern)

        def post_process(res):
            if res is not None:
                # XXX is sort ok?
                res.sort()
            else:
                res = []
            return res

        return self.getResponse().addCallback(post_process)

    def randomkey(self):
        """
        Return a random key from the keyspace
        """
        #raise NotImplementedError("Implemented but buggy, do not use.")
        self._send('RANDOMKEY')
        return self.getResponse()

    def rename(self, src, dst, preserve=False):
        """
        Rename a key
        """
        self._send('RENAMENX' if preserve else 'RENAME', src, dst)
        return self.getResponse()

    def dbsize(self):
        """
        Return the number of keys in the selected database
        """
        self._send('DBSIZE')
        return self.getResponse()

    def expire(self, key, time):
        """
        Set a key's time to live in seconds
        """
        self._send('EXPIRE', key, time)
        return self.getResponse()

    def expireat(self, key, time):
        """
        Set the expiration for a key as a UNIX timestamp
        """
        self._send('EXPIREAT', key, time)
        return self.getResponse()

    def ttl(self, key):
        """
        Get the time to live for a key
        """
        self._send('TTL', key)
        return self.getResponse()

    # transaction commands:
    def multi(self):
        """
        Mark the start of a transaction block
        """
        self._send('MULTI')
        return self.getResponse()

    def execute(self):
        """
        Sends the EXEC command

        Called execute because exec is a reserved word in Python.
        """
        self._send('EXEC')
        return self.getResponse()

    def discard(self):
        """
        Discard all commands issued after MULTI
        """
        self._send('DISCARD')
        return self.getResponse()

    def watch(self, *keys):
        """
        Watch the given keys to determine execution of the MULTI/EXEC block
        """
        self._send('WATCH', *keys)
        return self.getResponse()

    def unwatch(self):
        """
        Forget about all watched keys
        """
        self._send('UNWATCH')
        return self.getResponse()

    # # # # # # # # #
    # List Commands:
    # RPUSH
    # LPUSH
    # RPUSHX
    # LPUSHX
    # LLEN
    # LRANGE
    # LTRIM
    # LINDEX
    # LSET
    # LREM
    # LPOP
    # RPOP
    # BLPOP
    # BRPOP
    # RPOPLPUSH
    # SORT
    def push(self, key, value, tail=False, no_create=False):
        """
        @param key Redis key
        @param value String element of list

        Add the string value to the head (LPUSH/LPUSHX) or tail
        (RPUSH/RPUSHX) of the list stored at key key. If the key does
        not exist and no_create is False (the default) an empty list
        is created just before the append operation. If the key exists
        but is not a List an error is returned.

        @note Time complexity: O(1)
        """
        if tail:
            if no_create:
                return self.rpushx(key, value)
            else:
                return self.rpush(key, value)
        else:
            if no_create:
                return self.lpushx(key, value)
            else:
                return self.lpush(key, value)

    def lpush(self, key, *values, **kwargs):
        """
        Add string to head of list.
        @param key : List key
        @param values : Sequence of values to push
        @param value : For backwards compatibility, a single value.
        """
        if not kwargs:
            self._send('LPUSH', key, *values)
        elif 'value' in kwargs:
            self._send('LPUSH', key, kwargs['value'])
        else:
            raise exceptions.InvalidCommand('Need arguments for LPUSH')
        return self.getResponse()

    def rpush(self, key, *values, **kwargs):
        """
        Add string to end of list.
        @param key : List key
        @param values : Sequence of values to push
        @param value : For backwards compatibility, a single value.
        """
        if not kwargs:
            self._send('RPUSH', key, *values)
        elif 'value' in kwargs:
            self._send('RPUSH', key, kwargs['value'])
        else:
            raise exceptions.InvalidCommand('Need arguments for RPUSH')
        return self.getResponse()

    def lpushx(self, key, value):
        self._send('LPUSHX', key, value)
        return self.getResponse()

    def rpushx(self, key, value):
        self._send('RPUSHX', key, value)
        return self.getResponse()

    def llen(self, key):
        """
        @param key Redis key

        Return the length of the list stored at the key key. If the
        key does not exist zero is returned (the same behavior as for
        empty lists). If the value stored at key is not a list an error is
        returned.

        @note Time complexity: O(1)
        """
        self._send('LLEN', key)
        return self.getResponse()

    def lrange(self, key, start, end):
        """
        @param key Redis key
        @param start first element
        @param end last element

        Return the specified elements of the list stored at the key key.
        Start and end are zero-based indexes. 0 is the first element
        of the list (the list head), 1 the next element and so on.
        For example LRANGE foobar 0 2 will return the first three elements
        of the list.
        start and end can also be negative numbers indicating offsets from
        the end of the list. For example -1 is the last element of the
        list, -2 the penultimate element and so on.
        Indexes out of range will not produce an error: if start is over
        the end of the list, or start > end, an empty list is returned. If
        end is over the end of the list Redis will threat it just like the
        last element of the list.

        @note Time complexity: O(n) (with n being the length of the range)
        """
        self._send('LRANGE', key, start, end)
        return self.getResponse()

    def ltrim(self, key, start, end):
        """
        @param key Redis key
        @param start first element
        @param end last element

        Trim an existing list so that it will contain only the specified
        range of elements specified. Start and end are zero-based indexes.
        0 is the first element of the list (the list head), 1 the next
        element and so on.
        For example LTRIM foobar 0 2 will modify the list stored at foobar
        key so that only the first three elements of the list will remain.
        start and end can also be negative numbers indicating offsets from
        the end of the list. For example -1 is the last element of the
        list, -2 the penultimate element and so on.
        Indexes out of range will not produce an error: if start is over
        the end of the list, or start > end, an empty list is left as
        value. If end over the end of the list Redis will threat it just
        like the last element of the list.

        @note Time complexity: O(n) (with n being len of list - len of range)
        """
        self._send('LTRIM', key, start, end)
        return self.getResponse()

    def lindex(self, key, index):
        """
        @param key Redis key
        @param index index of element

        Return the specified element of the list stored at the specified
        key. 0 is the first element, 1 the second and so on. Negative
        indexes are supported, for example -1 is the last element, -2 the
        penultimate and so on.
        If the value stored at key is not of list type an error is
        returned. If the index is out of range an empty string is returned.

        @note Time complexity: O(n) (with n being the length of the list)
        Note that even if the average time complexity is O(n) asking for
        the first or the last element of the list is O(1).
        """
        self._send('LINDEX', key, index)
        return self.getResponse()

    def rpop(self, key):
        self._send('RPOP', key)
        return self.getResponse()

    def lpop(self, key):
        self._send('LPOP', key)
        return self.getResponse()

    def pop(self, key, tail=False):
        """
        @param key Redis key
        @param tail pop element from tail instead of head

        Atomically return and remove the first (LPOP) or last (RPOP)
        element of the list. For example if the list contains the elements
        "a","b","c" LPOP will return "a" and the list will become "b","c".
        If the key does not exist or the list is already empty the special
        value 'nil' is returned.
        """
        return self.rpop(key) if tail else self.lpop(key)

    def brpop(self, keys, timeout=30):
        """
        Issue a BRPOP - blockling list pop from the right.
        @param keys is a list of one or more Redis keys
        @param timeout max number of seconds to block for
        """
        self._send('BRPOP', *(list(keys) + [str(timeout)]))
        return self.getResponse()

    def brpoplpush(self, source, destination, timeout=30):
        """
        Blocking variant of RPOPLPUSH.
        @param source - Source list.
        @param destination - Destination list
        @param timeout - max number of seconds to block for (a
                        timeout of 0 will block indefinitely)
        """
        self._send('BRPOPLPUSH', source, destination, str(timeout))
        return self.getResponse()

    def bpop(self, keys, tail=False, timeout=30):
        """
        @param keys a list of one or more Redis keys of non-empty list(s)
        @param tail pop element from tail instead of head
        @param timeout max number of seconds block for (0 is forever)

        BLPOP (and BRPOP) is a blocking list pop primitive. You can see
        this commands as blocking versions of LPOP and RPOP able to block
        if the specified keys don't exist or contain empty lists.
        The following is a description of the exact semantic. We
        describe BLPOP but the two commands are identical, the only
        difference is that BLPOP pops the element from the left (head)
        of the list, and BRPOP pops from the right (tail).

        Non blocking behavior
        When BLPOP is called, if at least one of the specified keys
        contain a non empty list, an element is popped from the head of
        the list and returned to the caller together with the name of
        the key (BLPOP returns a two elements array, the first element
        is the key, the second the popped value).
        Keys are scanned from left to right, so for instance if you
        issue BLPOP list1 list2 list3 0 against a dataset where list1
        does not exist but list2 and list3 contain non empty lists,
        BLPOP guarantees to return an element from the list stored at
        list2 (since it is the first non empty list starting from the
        left).

        Blocking behavior
        If none of the specified keys exist or contain non empty lists,
        BLPOP blocks until some other client performs a LPUSH or an
        RPUSH operation against one of the lists.
        Once new data is present on one of the lists, the client
        finally returns with the name of the key unblocking it and the
        popped value.
        When blocking, if a non-zero timeout is specified, the client
        will unblock returning a nil special value if the specified
        amount of seconds passed without a push operation against at
        least one of the specified keys.
        A timeout of zero means instead to block forever.

        Multiple clients blocking for the same keys
        Multiple clients can block for the same key. They are put into
        a queue, so the first to be served will be the one that started
        to wait earlier, in a first-blpopping first-served fashion.

        Return value
        BLPOP returns a two-elements array via a multi bulk reply in
        order to return both the unblocking key and the popped value.
        When a non-zero timeout is specified, and the BLPOP operation
        timed out, the return value is a nil multi bulk reply. Most
        client values will return false or nil accordingly to the
        programming language used.
        """
        cmd = 'BRPOP' if tail else 'BLPOP'
        self._send(cmd, *(list(keys) + [str(timeout)]))
        return self.getResponse()

    def rpoplpush(self, srckey, dstkey):
        """
        @param srckey key of list to pop tail element of
        @param dstkey key of list to push to

        Atomically return and remove the last (tail) element of the srckey
        list, and push the element as the first (head) element of the
        dstkey list. For example if the source list contains the elements
        "a","b","c" and the destination list contains the elements
        "foo","bar" after an RPOPLPUSH command the content of the two lists
        will be "a","b" and "c","foo","bar".
        If the key does not exist or the list is already empty the special
        value 'nil' is returned. If the srckey and dstkey are the same the
        operation is equivalent to removing the last element from the list
        and pusing it as first element of the list, so it's a "list
        rotation" command.

        Programming patterns: safe queues
        Redis lists are often used as queues in order to exchange messages
        between different programs. A program can add a message performing
        an LPUSH operation against a Redis list (we call this program a
        Producer), while another program (that we call Consumer)
        can process the messages performing an RPOP command in
        order to start reading the messages from the oldest.
        Unfortunately if a Consumer crashes just after an RPOP
        operation the message gets lost. RPOPLPUSH solves this
        problem since the returned message is added to another
        "backup" list. The Consumer can later remove the message
        from the backup list using the LREM command when the
        message was correctly processed.
        Another process, called Helper, can monitor the "backup"
        list to check for timed out entries to repush against the
        main queue.

        Programming patterns: server-side O(N) list traversal
        Using RPOPPUSH with the same source and destination key a
        process can visit all the elements of an N-elements List in
        O(N) without to transfer the full list from the server to
        the client in a single LRANGE operation. Note that a
        process can traverse the list even while other processes
        are actively RPUSHing against the list, and still no
        element will be skipped.
        Return value

        Bulk reply
        """
        self._send('RPOPLPUSH', srckey, dstkey)
        return self.getResponse()

    def lset(self, key, index, value):
        """
        @param key Redis key
        @param index index of element
        @param value new value of element at index

        Set the list element at index (see LINDEX for information about the
        index argument) with the new value. Out of range indexes will
        generate an error. Note that setting the first or last elements of
        the list is O(1).
        Similarly to other list commands accepting indexes, the index can
        be negative to access elements starting from the end of the list.
        So -1 is the last element, -2 is the penultimate, and so forth.

        @note Time complexity: O(N) (with N being the length of the list)
        """
        self._send('LSET', key, index, value)
        return self.getResponse()

    def lrem(self, key, value, count=0):
        """
        @param key Redis key
        @param value value to match
        @param count number of occurrences of value
        Remove the first count occurrences of the value element from the
        list. If count is zero all the elements are removed. If count is
        negative elements are removed from tail to head, instead to go from
        head to tail that is the normal behavior. So for example LREM with
        count -2 and hello as value to remove against the list
        (a,b,c,hello,x,hello,hello) will lave the list (a,b,c,hello,x). The
        number of removed elements is returned as an integer, see below for
        more information about the returned value. Note that non existing
        keys are considered like empty lists by LREM, so LREM against non
        existing keys will always return 0.

        @retval deferred that returns the number of removed elements
        (int) if the operation succeeded

        @note Time complexity: O(N) (with N being the length of the list)
        """
        self._send('LREM', key, count, value)
        return self.getResponse()

    # Commands operating on sets
    def _list_to_set(self, res):
        if type(res) is list:
            return set(res)
        return res

    def sadd(self, key, *values, **kwargs):
        """
        Add a member to a set
        @param key : SET key to add values to.
        @param values : sequence of values to add to set
        @param value : For backwards compatibility, add one value.
        """
        if not kwargs:
            self._send('SADD', key, *values)
        elif 'value' in kwargs:
            self._send('SADD', key, kwargs['value'])
        else:
            raise exceptions.InvalidCommand('Need arguments for SADD')
        return self.getResponse()

    def srem(self, key, *values, **kwargs):
        """
        Remove a member from a set
        @param key : Set key
        @param values : Sequence of values to remove
        @param value : For backwards compatibility, single value to remove.
        """
        if not kwargs:
            self._send('SREM', key, *values)
        elif 'value' in kwargs:
            self._send('SREM', key, kwargs['value'])
        else:
            raise exceptions.InvalidCommand('Need arguments for SREM')
        return self.getResponse()

    def spop(self, key):
        """
        Remove and return a random member from a set
        """
        self._send('SPOP', key)
        return self.getResponse()

    def scard(self, key):
        """
        Get the number of members in a set
        """
        self._send('SCARD', key)
        return self.getResponse()

    def sismember(self, key, value):
        """
        Determine if a given value is a member of a set
        """
        self._send('SISMEMBER', key, value)
        return self.getResponse()

    def sdiff(self, *args):
        """
        Subtract multiple sets
        """
        self._send('SDIFF', *args)
        return self.getResponse()

    def sdiffstore(self, dstkey, *args):
        """
        Subtract multiple sets and store the resulting set in dstkey
        """
        self._send('SDIFFSTORE', dstkey, *args)
        return self.getResponse()

    def srandmember(self, key):
        """
        Get a random member from a set
        """
        self._send('SRANDMEMBER', key)
        return self.getResponse()

    def sinter(self, *args):
        """
        Intersect multiple sets
        """
        self._send('SINTER', *args)
        return self.getResponse().addCallback(self._list_to_set)

    def sinterstore(self, dest, *args):
        """
        Intersect multiple sets and store the resulting set in dest
        """
        self._send('SINTERSTORE', dest, *args)
        return self.getResponse()

    def smembers(self, key):
        """
        Get all the members in a set
        """
        self._send('SMEMBERS', key)
        return self.getResponse().addCallback(self._list_to_set)

    def smove(self, srckey, dstkey, member):
        """Move member from the set at srckey to the set at dstkey."""
        self._send('SMOVE', srckey, dstkey, member)
        return self.getResponse()

    def sunion(self, *args):
        """
        Add multiple sets
        """
        self._send('SUNION', *args)
        return self.getResponse().addCallback(self._list_to_set)

    def sunionstore(self, dest, *args):
        """
        Add multiple sets and store the resulting set in dest
        """
        self._send('SUNIONSTORE', dest, *args)
        return self.getResponse()

    # Multiple databases handling commands
    def select(self, db):
        """
        Select the DB with having the specified zero-based numeric index. New
        connections always use DB 0.
        """
        self._send('SELECT', db)
        return self.getResponse()

    def move(self, key, db):
        """
        Move a key to another database
        """
        self._send('MOVE', key, db)
        return self.getResponse()

    def flush(self, all_dbs=False):
        """
        Remove all keys from the current database or, if all_dbs is True,
        all databases.
        """
        if all_dbs:
            return self.flushall()
        else:
            return self.flushdb()

    def flushall(self):
        """
        Remove all keys from all databases
        """
        self._send('FLUSHALL')
        return self.getResponse()

    def flushdb(self):
        """
        Remove all keys from the current database
        """
        self._send('FLUSHDB')
        return self.getResponse()

    # Persistence control commands
    def bgrewriteaof(self):
        """
        Rewrites the append-only file to reflect the current dataset in memory.
        If BGREWRITEAOF fails, no data gets lost as the old AOF will be
        untouched.
        """
        self._send('BGREWRITEAOF')
        return self.getResponse()

    def bgsave(self):
        """
        Save the DB in background. The OK code is immediately returned. Redis
        forks, the parent continues to server the clients, the child saves the
        DB on disk then exit. A client my be able to check if the operation
        succeeded using the LASTSAVE command.
        """
        self._send('BGSAVE')
        return self.getResponse()

    def save(self, background=False):
        """
        Synchronously save the dataset to disk.
        """
        if background:
            return self.bgsave()
        else:
            self._send('SAVE')
        return self.getResponse()

    def lastsave(self):
        """
        Return the UNIX TIME of the last DB save executed with success. A
        client may check if a BGSAVE command succeeded reading the LASTSAVE
        value, then issuing a BGSAVE command and checking at regular intervals
        every N seconds if LASTSAVE changed.
        """
        self._send('LASTSAVE')
        return self.getResponse()

    def info(self):
        """
        The info command returns different information and statistics about the
        server in an format that's simple to parse by computers and easy to red
        by huamns.
        """
        self._send('INFO')

        def post_process(res):
            info = dict()
            res = res.split('\r\n')
            for l in res:
                if not l or l[0] == '#':
                    continue
                k, v = l.split(':')
                info[k] = int(v) if v.isdigit() else v
            return info

        return self.getResponse().addCallback(post_process)

    def sort(self, key, by=None, get=None, start=None, num=None, desc=False,
             alpha=False):
        """
        Sort the elements in a list, set or sorted set
        """
        stmt = ['SORT', key]
        if by:
            stmt.extend(['BY', by])
        if start and num:
            stmt.extend(['LIMIT', start, num])
        if get is None:
            pass
        elif isinstance(get, basestring):
            stmt.extend(['GET', get])
        elif isinstance(get, list) or isinstance(get, tuple):
            for g in get:
                stmt.extend(['GET', g])
        else:
            raise exceptions.RedisError(
                "Invalid parameter 'get' for Redis sort")
        if desc:
            stmt.append("DESC")
        if alpha:
            stmt.append("ALPHA")
        self._send(*stmt)
        return self.getResponse()

    def auth(self, passwd):
        """
        Request for authentication in a password protected Redis server. Redis
        can be instructed to require a password before allowing clients to
        execute commands. This is done using the requirepass directive in the
        configuration file.  If password matches the password in the
        configuration file, the server replies with the OK status code and
        starts accepting commands. Otherwise, an error is returned and the
        clients needs to try a new password.

        Note: because of the high performance nature of Redis, it is possible
        to try a lot of passwords in parallel in very short time, so make sure
        to generate a strong and very long password so that this attack is
        infeasible.
        """
        self._send('AUTH', passwd)
        return self.getResponse()

    def quit(self):
        """
        Ask the server to close the connection. The connection is closed as
        soon as all pending replies have been written to the client.
        """
        self._send('QUIT')
        return self.getResponse()

    def echo(self, msg):
        """
        Returns message.
        """
        self._send('ECHO', msg)
        return self.getResponse()

    # # # # # # # # #
    # Hash Commands:
    # HSET
    # HGET
    # HMSET
    # HINCRBY
    # HEXISTS
    # HDEL
    # HLEN
    # HKEYS
    # HVALS
    # HGETALL
    def hmset(self, key, in_dict):
        """
        Sets the specified fields to their respective values in the hash stored
        at key. This command overwrites any existing fields in the hash. If key
        does not exist, a new key holding a hash is created.
        """
        fields = list(itertools.chain(*in_dict.iteritems()))
        self._send('HMSET', key, *fields)
        return self.getResponse()

    def hset(self, key, field, value, preserve=False):
        """
        Sets field in the hash stored at key to value. If key does not exist, a
        new key holding a hash is created. If field already exists in the hash,
        it is overwritten.
        """
        if preserve:
            return self.hsetnx(key, field, value)
        else:
            self._send('HSET', key, field, value)
            return self.getResponse()

    def hsetnx(self, key, field, value):
        """
        Sets field in the hash stored at key to value, only if field does not
        yet exist. If key does not exist, a new key holding a hash is created.
        If field already exists, this operation has no effect.
        """
        self._send('HSETNX', key, field, value)
        return self.getResponse()

    def hget(self, key, field):
        """
        Returns the value associated with field in the hash stored at key.
        """
        if isinstance(field, basestring):
            self._send('HGET', key, field)
        else:
            self._send('HMGET', *([key] + field))

        def post_process(values):
            if not values:
                return values
            if isinstance(field, basestring):
                return {field: values}
            return dict(itertools.izip(field, values))

        return self.getResponse().addCallback(post_process)
    hmget = hget

    def hget_value(self, key, field):
        """
        Get the value of a hash field
        """
        assert isinstance(field, basestring)
        self._send('HGET', key, field)
        return self.getResponse()

    def hkeys(self, key):
        """
        Get all the fields in a hash
        """
        self._send('HKEYS', key)
        return self.getResponse()

    def hvals(self, key):
        """
        Get all the values in a hash
        """
        self._send('HVALS', key)
        return self.getResponse()

    def hincr(self, key, field, amount=1):
        """
        Increments the number stored at field in the hash stored at key by
        increment. If key does not exist, a new key holding a hash is created.
        If field does not exist or holds a string that cannot be interpreted as
        integer, the value is set to 0 before the operation is performed.  The
        range of values supported by HINCRBY is limited to 64 bit signed
        integers.
        """
        self._send('HINCRBY', key, field, amount)
        return self.getResponse()
    hincrby = hincr

    def hexists(self, key, field):
        """
        Returns if field is an existing field in the hash stored at key.
        """
        self._send('HEXISTS', key, field)
        return self.getResponse()

    def hdel(self, key, *fields):
        """
        Removes field from the hash stored at key.
        @param key : Hash key
        @param fields : Sequence of fields to remvoe
        """
        if fields:
            self._send('HDEL', key, *fields)
        else:
            raise exceptions.InvalidCommand('Need arguments for HDEL')
        return self.getResponse()
    hdelete = hdel  # backwards compat for older txredis

    def hlen(self, key):
        """
        Returns the number of fields contained in the hash stored at key.
        """
        self._send('HLEN', key)
        return self.getResponse()

    def hgetall(self, key):
        """
        Returns all fields and values of the hash stored at key. In the
        returned value, every field name is followed by its value, so the
        length of the reply is twice the size of the hash.
        """
        self._send('HGETALL', key)

        def post_process(key_vals):
            res = {}
            i = 0
            while i < len(key_vals) - 1:
                res[key_vals[i]] = key_vals[i + 1]
                i += 2
            return res

        return self.getResponse().addCallback(post_process)

    def publish(self, channel, message):
        """
        Publishes a message to all subscribers of a specified channel.
        """
        self._send('PUBLISH', channel, message)
        return self.getResponse()

    # # # # # # # # #
    # Sorted Set Commands:
    # ZADD
    # ZREM
    # ZINCRBY
    # ZRANK
    # ZREVRANK
    # ZRANGE
    # ZREVRANGE
    # ZRANGEBYSCORE
    # ZREVRANGEBYSCORE
    # ZCARD
    # ZSCORE
    # ZREMRANGEBYRANK
    # ZREMRANGEBYSCORE
    # ZUNIONSTORE / ZINTERSTORE
    def zadd(self, key, *item_tuples, **kwargs):
        """
        Add members to a sorted set, or update its score if it already exists
        @param key : Sorted set key
        @param item_tuples : Sequence of score, value pairs.
                            e.g. zadd(key, score1, value1, score2, value2)
        @param member : For backwards compatibility, member name.
        @param score : For backwards compatibility, score.

        NOTE: If there are only two arguments, the order is interpreted
              as (value, score) for backwards compatibility reasons.
        """
        if not kwargs and len(item_tuples) == 2 and \
           isinstance(item_tuples[0], basestring):
            self._send('ZADD', key, item_tuples[1], item_tuples[0])
        elif not kwargs:
            self._send('ZADD', key, *item_tuples)
        elif 'member' in kwargs and 'score' in kwargs:
            score, member = item_tuples
            self._send('ZADD', key, kwargs['score'], kwargs['member'])
        else:
            raise exceptions.InvalidCommand('Need arguments for ZADD')
        return self.getResponse()

    def zrem(self, key, *members, **kwargs):
        """
        Remove members from a sorted set
        @param key : Sorted set key
        @param members : Sequeunce of members to remove
        @param member : For backwards compatibility - if specified remove
                        one member.
        """
        if not kwargs:
            self._send('ZREM', key, *members)
        elif 'member' in kwargs:
            self._send('ZREM', key, kwargs['member'])
        else:
            raise exceptions.InvalidCommand('Need arguments for ZREM')
        return self.getResponse()

    def zremrangebyrank(self, key, start, end):
        """
        Remove all members in a sorted set within the given indexes
        """
        self._send('ZREMRANGEBYRANK', key, start, end)
        return self.getResponse()

    def zremrangebyscore(self, key, min, max):
        """
        Remove all members in a sorted set within the given scores
        """
        self._send('ZREMRANGEBYSCORE', key, min, max)
        return self.getResponse()

    def _zopstore(self, op, dstkey, keys, aggregate=None):
        """ Creates a union or intersection of N sorted sets given by keys k1
        through kN, and stores it at dstkey. It is mandatory to provide the
        number of input keys N, before passing the input keys and the other
        (optional) arguments.
        """
        # basic arguments
        args = [op, dstkey, len(keys)]
        # add in key names, and optionally weights
        if isinstance(keys, dict):
            args.extend(list(keys.iterkeys()))
            args.append('WEIGHTS')
            args.extend(list(keys.itervalues()))
        else:
            args.extend(keys)
        if aggregate:
            args.append('AGGREGATE')
            args.append(aggregate)
        self._send(*args)
        return self.getResponse()

    def zunionstore(self, dstkey, keys, aggregate=None):
        """ Creates a union of N sorted sets at dstkey. keys can be a list
        of keys or dict of keys mapping to weights. aggregate can be
        one of SUM, MIN or MAX.
        """
        return self._zopstore('ZUNIONSTORE', dstkey, keys, aggregate)

    def zinterstore(self, dstkey, keys, aggregate=None):
        """Creates an intersection of N sorted sets at dstkey.

        Keys can be a list of keys or dict of keys mapping to weights.
        Aggregate can be one of SUM, MIN or MAX.

        """
        return self._zopstore('ZINTERSTORE', dstkey, keys, aggregate)

    def zincr(self, key, member, incr=1):
        """
        Increment the score of a member in a sorted set by the given amount
        (default 1)
        """
        self._send('ZINCRBY', key, incr, member)
        return self.getResponse()

    def zrank(self, key, member, reverse=False):
        """
        Determine the index of a member in a sorted set. If reverse
        is True, the scores are orderd from high to low.
        """
        cmd = 'ZREVRANK' if reverse else 'ZRANK'
        self._send(cmd, key, member)
        return self.getResponse()

    def zcount(self, key, min, max):
        """
        Count the members in a sorted set with scores within the given values
        """
        self._send('ZCOUNT', key, min, max)
        return self.getResponse()

    def zrange(self, key, start, end, withscores=False, reverse=False):
        """
        Return a range of members in a sorted set, by index.
        If withscores is True, the score is returned as well.
        If reverse is True, the elements are considered to be
        sorted from high to low.
        """
        cmd = 'ZREVRANGE' if reverse else 'ZRANGE'
        args = [cmd, key, start, end]
        if withscores:
            args.append('WITHSCORES')
        self._send(*args)
        dfr = self.getResponse()

        def post_process(vals_and_scores):
            # return list of (val, score) tuples
            res = []
            bins = len(vals_and_scores) - 1
            i = 0
            while i < bins:
                res.append((vals_and_scores[i], float(vals_and_scores[i + 1])))
                i += 2
            return res

        if withscores:
            dfr.addCallback(post_process)
        return dfr

    def zrevrange(self, key, start, end, withscores=False):
        """
        Return a range of members in a sorted set, by index, with scores
        ordered from high to low
        """
        return self.zrange(key, start, end, withscores, reverse=True)

    def zrevrank(self, key, member):
        """
        Determine the index of a member in a sorted set, with scores ordered
        from high to low
        """
        self._send('ZREVRANK', key, member)
        return self.getResponse()

    def zcard(self, key):
        """
        Get the number of members in a sorted set
        """
        self._send('ZCARD', key)
        return self.getResponse()

    def zscore(self, key, element):
        """
        Get the score associated with the given member in a sorted set
        """
        self._send('ZSCORE', key, element)

        def post_process(res):
            if res is not None:
                return float(res)
            else:
                return res
        return self.getResponse().addCallback(post_process)

    def zrangebyscore(self, key, min='-inf', max='+inf', offset=0,
                      count=None, withscores=False, reverse=False):
        """
        Return a range of members in a sorted set, by score.
        """
        if reverse:
            args = ['ZREVRANGEBYSCORE', key, max, min]
        else:
            args = ['ZRANGEBYSCORE', key, min, max]
        if count is not None:
            args.extend(['LIMIT', offset, count])
        elif offset:
            raise ValueError("Can't have offset without count")
        if withscores:
            args.append('WITHSCORES')
        self._send(*args)
        dfr = self.getResponse()

        def post_process(vals_and_scores):
            # return list of (val, score) tuples
            res = []
            bins = len(vals_and_scores) - 1
            i = 0
            while i < bins:
                res.append((vals_and_scores[i], float(vals_and_scores[i + 1])))
                i += 2
            return res

        if withscores:
            dfr.addCallback(post_process)
        return dfr

    def zrevrangebyscore(self, key, min='-inf', max='+inf', offset=0,
            count=None, withscores=False):
        return self.zrangebyscore(key, min, max, offset, count, withscores,
                reverse=True)

    # # # # # # # # #
    # Scripting Commands:
    # EVAL
    # EVALSHA
    # SCRIPT LOAD
    # SCRIPT EXISTS
    # SCRIPT FLUSH
    # SCRIPT KILL

    def eval(self, source, keys=(), args=()):
        """
        Evaluate Lua script source with keys and arguments.
        """
        keycount = len(keys)
        args = ['EVAL', source, keycount] + list(keys) + list(args)
        self._send(*args)
        return self.getResponse()

    def evalsha(self, sha1, keys=(), args=()):
        """
        Evaluate Lua script loaded in script cache under given sha1 with keys
        and arguments.
        """
        keycount = len(keys)
        args = ['EVALSHA', sha1, keycount] + list(keys) + list(args)
        self._send(*args)
        return self.getResponse()

    def script_load(self, source):
        """
        Load Lua script source into cache. This returns the SHA1 of the loaded
        script on success.
        """
        args = ['SCRIPT', 'LOAD', source]
        self._send(*args)
        return self.getResponse()

    def script_exists(self, *sha1s):
        """
        Check whether of no scripts for given sha1 exists in cache. Returns
        list of booleans.
        """
        args = ['SCRIPT', 'EXISTS'] + list(sha1s)
        self._send(*args)
        return self.getResponse()

    def script_flush(self):
        """
        Flush the script cache.
        """
        args = ['SCRIPT', 'FLUSH']
        self._send(*args)
        return self.getResponse()

    def script_kill(self):
        """
        Kill the currently executing script.
        """
        args = ['SCRIPT', 'KILL']
        self._send(*args)
        return self.getResponse()


class HiRedisClient(HiRedisBase, RedisClient):
    """A subclass of the Redis protocol that uses the hiredis library for
    parsing.
    """
    def __init__(self, db=None, password=None, charset='utf8',
                 errors='strict'):
        super(HiRedisClient, self).__init__(db, password, charset, errors)
        self._reader = hiredis.Reader(protocolError=exceptions.InvalidData,
                                      replyError=exceptions.ResponseError)


class RedisSubscriber(RedisBase):
    """
    Redis client for subscribing & listening for published events.  Redis
    connections listening to events are expected to not issue commands other
    than subscribe & unsubscribe, and therefore no other commands are available
    on a RedisSubscriber instance.
    """

    def __init__(self, *args, **kwargs):
        RedisBase.__init__(self, *args, **kwargs)
        self.setTimeout(None)

    def handleCompleteMultiBulkData(self, reply):
        """
        Overrides RedisBase.handleCompleteMultiBulkData to intercept published
        message events.
        """
        if reply[0] == u"message":
            channel, message = reply[1:]
            self.messageReceived(channel, message)
        elif reply[0] == u"pmessage":
            pattern, channel, message = reply[1:]
            self.messageReceived(channel, message)
        elif reply[0] == u"subscribe":
            channel, numSubscribed = reply[1:]
            self.channelSubscribed(channel, numSubscribed)
        elif reply[0] == u"unsubscribe":
            channel, numSubscribed = reply[1:]
            self.channelUnsubscribed(channel, numSubscribed)
        elif reply[0] == u"psubscribe":
            channelPattern, numSubscribed = reply[1:]
            self.channelPatternSubscribed(channelPattern, numSubscribed)
        elif reply[0] == u"punsubscribe":
            channelPattern, numSubscribed = reply[1:]
            self.channelPatternUnsubscribed(channelPattern, numSubscribed)
        else:
            RedisBase.handleCompleteMultiBulkData(self, reply)

    def messageReceived(self, channel, message):
        """
        Called when this connection is subscribed to a channel that
        has received a message published on it.
        """
        pass

    def channelSubscribed(self, channel, numSubscriptions):
        """
        Called when a channel is subscribed to.
        """
        pass

    def channelUnsubscribed(self, channel, numSubscriptions):
        """
        Called when a channel is unsubscribed from.
        """
        pass

    def channelPatternSubscribed(self, channel, numSubscriptions):
        """
        Called when a channel patern is subscribed to.
        """
        pass

    def channelPatternUnsubscribed(self, channel, numSubscriptions):
        """
        Called when a channel pattern is unsubscribed from.
        """
        pass

    def subscribe(self, *channels):
        """
        Begin listening for PUBLISH messages on one or more channels.  When a
        message is published on one, the messageReceived method will be
        invoked.  Does not return any value, although the method
        channelSubscribed will be invoked on confirmation from the server of
        every subscribed channel.  If a channel is already subscribed to by
        this connection, then channelSubscribed will not be invoked but the
        channel will continue to be subscribed to.
        """
        self._send('SUBSCRIBE', *channels)

    def unsubscribe(self, *channels):
        """
        Terminate listening for PUBLISH messages on one or more channels.  If
        no channels are passed in, all channels are unsubscribed from.i Does
        not return any value, but the method channelUnsubscribed will be
        invokved for each channel that is unsubscribed from.  If a channel is
        provided that is not subscribed to by this connection, then
        channelUnsubscribed will not be invoked.
        """
        self._send('UNSUBSCRIBE', *channels)

    def psubscribe(self, *patterns):
        """
        Begin listening for PUBLISH messages on one or more channel patterns.
        When a message is published on a matching channel, the messageReceived
        method will be invoked.  Does not return any value, but the method
        channelPatternSubscribed will be invoked for each channel pattern that
        is subscribed to.
        """
        self._send('PSUBSCRIBE', *patterns)

    def punsubscribe(self, *patterns):
        """
        Terminate listening for PUBLISH messages on one or more channel
        patterns.  If no channel patterns are passed in, all channel patterns
        are unsubscribed from.  Does not return any value, but the method
        channelPatternUnsubscribed will be invoked for eeach channel pattern
        that is unsubscribed from.
        """
        self._send('PUNSUBSCRIBE', *patterns)


class RedisClientFactory(ReconnectingClientFactory):

    protocol = RedisClient

    def __init__(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs
        self.client = None
        self.deferred = defer.Deferred()

    def buildProtocol(self, addr):
        from twisted.internet import reactor

        def fire(res):
            self.deferred.callback(self.client)
            self.deferred = defer.Deferred()
        self.client = self.protocol(*self._args, **self._kwargs)
        self.client.factory = self
        reactor.callLater(0, fire, self.client)
        self.resetDelay()
        return self.client


class RedisSubscriberFactory(RedisClientFactory):
    protocol = RedisSubscriber


# backwards compatibility
Redis = RedisClient
HiRedisProtocol = HiRedisClient

########NEW FILE########
__FILENAME__ = exceptions
"""
@file exceptions.py
"""

class RedisError(Exception):
    pass


class ConnectionError(RedisError):
    pass


class ResponseError(RedisError):
    pass


class NoScript(RedisError):
    pass


class NotBusy(RedisError):
    pass


class InvalidResponse(RedisError):
    pass


class InvalidData(RedisError):
    pass


class InvalidCommand(RedisError):
    pass

########NEW FILE########
__FILENAME__ = protocol
"""
@file protocol.py

@mainpage

txRedis is an asynchronous, Twisted, version of redis.py (included in the
redis server source).

The official Redis Command Reference:
http://code.google.com/p/redis/wiki/CommandReference

@section An example demonstrating how to use the client in your code:
@code
from twisted.internet import reactor
from twisted.internet import protocol
from twisted.internet import defer

from txredis.protocol import Redis

@defer.inlineCallbacks
def main():
    clientCreator = protocol.ClientCreator(reactor, Redis)
    redis = yield clientCreator.connectTCP(HOST, PORT)

    res = yield redis.ping()
    print res

    res = yield redis.set('test', 42)
    print res

    test = yield redis.get('test')
    print res

@endcode

Redis google code project: http://code.google.com/p/redis/
Command doc strings taken from the CommandReference wiki page.

"""
from collections import deque

from twisted.internet import defer, protocol
from twisted.protocols import policies

from txredis import exceptions


class RedisBase(protocol.Protocol, policies.TimeoutMixin, object):
    """The main Redis client."""

    ERROR = "-"
    SINGLE_LINE = "+"
    INTEGER = ":"
    BULK = "$"
    MULTI_BULK = "*"

    def __init__(self, db=None, password=None, charset='utf8',
                 errors='strict'):
        self.charset = charset
        self.db = db if db is not None else 0
        self.password = password
        self.errors = errors
        self._buffer = ''
        self._bulk_length = None
        self._disconnected = False
        # Format of _multi_bulk_stack elements is:
        # [[length-remaining, [replies] | None]]
        self._multi_bulk_stack = deque()
        self._request_queue = deque()

    def dataReceived(self, data):
        """Receive data.

        Spec: http://redis.io/topics/protocol
        """
        self.resetTimeout()
        self._buffer = self._buffer + data

        while self._buffer:

            # if we're expecting bulk data, read that many bytes
            if self._bulk_length is not None:
                # wait until there's enough data in the buffer
                # we add 2 to _bulk_length to account for \r\n
                if len(self._buffer) < self._bulk_length + 2:
                    return
                data = self._buffer[:self._bulk_length]
                self._buffer = self._buffer[self._bulk_length + 2:]
                self.bulkDataReceived(data)
                continue

            # wait until we have a line
            if '\r\n' not in self._buffer:
                return

            # grab a line
            line, self._buffer = self._buffer.split('\r\n', 1)
            if len(line) == 0:
                continue

            # first byte indicates reply type
            reply_type = line[0]
            reply_data = line[1:]

            # Error message (-)
            if reply_type == self.ERROR:
                self.errorReceived(reply_data)
            # Integer number (:)
            elif reply_type == self.INTEGER:
                self.integerReceived(reply_data)
            # Single line (+)
            elif reply_type == self.SINGLE_LINE:
                self.singleLineReceived(reply_data)
            # Bulk data (&)
            elif reply_type == self.BULK:
                try:
                    self._bulk_length = int(reply_data)
                except ValueError:
                    r = exceptions.InvalidResponse(
                        "Cannot convert data '%s' to integer" % reply_data)
                    self.responseReceived(r)
                    return
                # requested value may not exist
                if self._bulk_length == -1:
                    self.bulkDataReceived(None)
            # Multi-bulk data (*)
            elif reply_type == self.MULTI_BULK:
                # reply_data will contain the # of bulks we're about to get
                try:
                    multi_bulk_length = int(reply_data)
                except ValueError:
                    r = exceptions.InvalidResponse(
                        "Cannot convert data '%s' to integer" % reply_data)
                    self.responseReceived(r)
                    return
                if multi_bulk_length == -1:
                    self._multi_bulk_stack.append([-1, None])
                    self.multiBulkDataReceived()
                    return
                else:
                    self._multi_bulk_stack.append([multi_bulk_length, []])
                    if multi_bulk_length == 0:
                        self.multiBulkDataReceived()

    def failRequests(self, reason):
        while self._request_queue:
            d = self._request_queue.popleft()
            d.errback(reason)

    def connectionMade(self):
        """ Called when incoming connections is made to the server. """
        d = defer.succeed(True)

        # if we have a password set, make sure we auth
        if self.password:
            d.addCallback(lambda _res: self.auth(self.password))

        # select the db passsed in
        if self.db:
            d.addCallback(lambda _res: self.select(self.db))

        def done_connecting(_res):
            # set our state as soon as we're properly connected
            self._disconnected = False
        d.addCallback(done_connecting)

        return d

    def connectionLost(self, reason):
        """Called when the connection is lost.

        Will fail all pending requests.

        """
        self._disconnected = True
        self.failRequests(reason)

    def timeoutConnection(self):
        """Called when the connection times out.

        Will fail all pending requests with a TimeoutError.

        """
        self.failRequests(defer.TimeoutError("Connection timeout"))
        self.transport.loseConnection()

    def errorReceived(self, data):
        """Error response received."""
        if data[:4] == 'ERR ':
            reply = exceptions.ResponseError(data[4:])
        elif data[:9] == 'NOSCRIPT ':
            reply = exceptions.NoScript(data[9:])
        elif data[:8] == 'NOTBUSY ':
            reply = exceptions.NotBusy(data[8:])
        else:
            reply = exceptions.ResponseError(data)

        if self._request_queue:
            # properly errback this reply
            self._request_queue.popleft().errback(reply)
        else:
            # we should have a request queue. if not, just raise this exception
            raise reply

    def singleLineReceived(self, data):
        """Single line response received."""
        if data == 'none':
            # should this happen here in the client?
            reply = None
        else:
            reply = data

        self.responseReceived(reply)

    def handleMultiBulkElement(self, element):
        top = self._multi_bulk_stack[-1]
        top[1].append(element)
        top[0] -= 1
        if top[0] == 0:
            self.multiBulkDataReceived()

    def integerReceived(self, data):
        """Integer response received."""
        try:
            reply = int(data)
        except ValueError:
            reply = exceptions.InvalidResponse(
                "Cannot convert data '%s' to integer" % data)
        if self._multi_bulk_stack:
            self.handleMultiBulkElement(reply)
            return

        self.responseReceived(reply)

    def bulkDataReceived(self, data):
        """Bulk data response received."""
        self._bulk_length = None
        self.responseReceived(data)

    def multiBulkDataReceived(self):
        """Multi bulk response received.

        The bulks making up this response have been collected in
        the last entry in self._multi_bulk_stack.

        """
        reply = self._multi_bulk_stack.pop()[1]
        if self._multi_bulk_stack:
            self.handleMultiBulkElement(reply)
        else:
            self.handleCompleteMultiBulkData(reply)

    def handleCompleteMultiBulkData(self, reply):
        self.responseReceived(reply)

    def responseReceived(self, reply):
        """Handle a server response.

        If we're waiting for multibulk elements, store this reply. Otherwise
        provide the reply to the waiting request.

        """
        if self._multi_bulk_stack:
            self.handleMultiBulkElement(reply)
        elif self._request_queue:
            self._request_queue.popleft().callback(reply)

    def getResponse(self):
        """
        @retval a deferred which will fire with response from server.
        """
        if self._disconnected:
            return defer.fail(RuntimeError("Not connected"))

        d = defer.Deferred()
        self._request_queue.append(d)
        return d

    def _encode(self, s):
        """Encode a value for sending to the server."""
        if isinstance(s, str):
            return s
        if isinstance(s, unicode):
            try:
                return s.encode(self.charset, self.errors)
            except UnicodeEncodeError, e:
                raise exceptions.InvalidData(
                    "Error encoding unicode value '%s': %s" % (
                        s.encode(self.charset, 'replace'), e))
        return str(s)

    def _send(self, *args):
        """Encode and send a request

        Uses the 'unified request protocol' (aka multi-bulk)

        """
        cmds = []
        for i in args:
            v = self._encode(i)
            cmds.append('$%s\r\n%s\r\n' % (len(v), v))
        cmd = '*%s\r\n' % len(args) + ''.join(cmds)
        self.transport.write(cmd)

    def send(self, command, *args):
        self._send(command, *args)
        return self.getResponse()


class HiRedisBase(RedisBase):
    """A subclass of the RedisBase protocol that uses the hiredis library for
    parsing.
    """

    def dataReceived(self, data):
        """Receive data.
        """
        self.resetTimeout()
        if data:
            self._reader.feed(data)
        res = self._reader.gets()
        while res is not False:
            if isinstance(res, exceptions.ResponseError):
                self._request_queue.popleft().errback(res)
            else:
                if isinstance(res, basestring) and res == 'none':
                    res = None
                self._request_queue.popleft().callback(res)
            res = self._reader.gets()

########NEW FILE########
__FILENAME__ = testing
"""
@file testing.py

This module provides the basic needs to run txRedis unit tests.
"""
from twisted.internet import protocol
from twisted.internet import reactor
from twisted.trial import unittest

from txredis.client import Redis


REDIS_HOST = 'localhost'
REDIS_PORT = 6381


class CommandsBaseTestCase(unittest.TestCase):

    protocol = Redis

    def setUp(self):

        def got_conn(redis):
            self.redis = redis

        def cannot_conn(res):
            msg = '\n' * 3 + '*' * 80 + '\n' * 2
            msg += ("NOTE: Redis server not running on port %s. Please start "
                    "a local instance of Redis on this port to run unit tests "
                    "against.\n\n") % REDIS_PORT
            msg += '*' * 80 + '\n' * 4
            raise unittest.SkipTest(msg)

        clientCreator = protocol.ClientCreator(reactor, self.protocol)
        d = clientCreator.connectTCP(REDIS_HOST, REDIS_PORT)
        d.addCallback(got_conn)
        d.addErrback(cannot_conn)
        return d

    def tearDown(self):
        self.redis.transport.loseConnection()

########NEW FILE########
__FILENAME__ = test_client
import time
import hashlib

from twisted.internet import error
from twisted.internet import protocol
from twisted.internet import reactor
from twisted.internet import defer
from twisted.internet.task import Clock
from twisted.test.proto_helpers import StringTransportWithDisconnection
from twisted.trial import unittest
from twisted.trial.unittest import SkipTest

from txredis.client import Redis, RedisSubscriber, RedisClientFactory
from txredis.exceptions import InvalidCommand, ResponseError, NoScript, NotBusy
from txredis.testing import CommandsBaseTestCase, REDIS_HOST, REDIS_PORT


class GeneralCommandTestCase(CommandsBaseTestCase):
    """Test commands that operate on any type of redis value.
    """
    @defer.inlineCallbacks
    def test_ping(self):
        a = yield self.redis.ping()
        self.assertEqual(a, 'PONG')

    @defer.inlineCallbacks
    def test_config(self):
        t = self.assertEqual
        a = yield self.redis.get_config('*')
        self.assertTrue(isinstance(a, dict))
        self.assertTrue('dbfilename' in a)

        a = yield self.redis.set_config('dbfilename', 'dump.rdb.tmp')
        ex = 'OK'
        t(a, ex)

        a = yield self.redis.get_config('dbfilename')
        self.assertTrue(isinstance(a, dict))
        t(a['dbfilename'], 'dump.rdb.tmp')

    """
    @defer.inlineCallbacks
    def test_auth(self):
        r = self.redis
        t = self.assertEqual

        # set a password
        password = 'foobar'
        a = yield self.redis.set_config('requirepass', password)
        ex = 'OK'
        t(a, ex)

        # auth with it
        a = yield self.redis.auth(password)
        ex = 'OK'
        t(a, ex)

        # turn password off
        a = yield self.redis.set_config('requirepass', '')
        ex = 'OK'
        t(a, ex)
    """

    @defer.inlineCallbacks
    def test_exists(self):
        r = self.redis
        t = self.assertEqual

        a = yield r.exists('dsjhfksjdhfkdsjfh')
        ex = 0
        t(a, ex)
        a = yield r.set('a', 'a')
        ex = 'OK'
        t(a, ex)
        a = yield r.exists('a')
        ex = 1
        t(a, ex)

    @defer.inlineCallbacks
    def test_delete(self):
        r = self.redis
        t = self.assertEqual

        a = yield r.delete('dsjhfksjdhfkdsjfh')
        ex = 0
        t(a, ex)
        a = yield r.set('a', 'a')
        ex = 'OK'
        t(a, ex)
        a = yield r.delete('a')
        ex = 1
        t(a, ex)
        a = yield r.exists('a')
        ex = 0
        t(a, ex)
        a = yield r.delete('a')
        ex = 0
        t(a, ex)
        a = yield r.set('a', 'a')
        ex = 'OK'
        t(a, ex)
        a = yield r.set('b', 'b')
        ex = 'OK'
        t(a, ex)
        a = yield r.delete('a', 'b')
        ex = 2
        t(a, ex)

    @defer.inlineCallbacks
    def test_get_object(self):
        r = self.redis
        t = self.assertEqual
        a = yield r.set('obj', 1)
        ex = 'OK'
        t(a, ex)

        a = yield r.get_object('obj', idletime=True)
        self.assertEqual(type(a), int)

        a = yield r.get_object('obj', encoding=True)
        ex = 'int'
        t(a, ex)

    @defer.inlineCallbacks
    def test_get_type(self):
        r = self.redis
        t = self.assertEqual

        a = yield r.set('a', 3)
        ex = 'OK'
        t(a, ex)
        a = yield r.get_type('a')
        ex = 'string'
        t(a, ex)
        a = yield r.get_type('zzz')
        ex = None
        t(a, ex)
        self.assertTrue(a is None or a == 'none')

    @defer.inlineCallbacks
    def test_keys(self):
        r = self.redis
        t = self.assertEqual

        a = yield r.flush()
        ex = 'OK'
        t(a, ex)
        a = yield r.set('a', 'a')
        ex = 'OK'
        t(a, ex)
        a = yield r.keys('a*')
        ex = [u'a']
        t(a, ex)
        a = yield r.set('a2', 'a')
        ex = 'OK'
        t(a, ex)
        a = yield r.keys('a*')
        ex = [u'a', u'a2']
        t(a, ex)
        a = yield r.delete('a2')
        ex = 1
        t(a, ex)
        a = yield r.keys('sjdfhskjh*')
        ex = []
        t(a, ex)

    @defer.inlineCallbacks
    def test_randomkey(self):
        r = self.redis
        t = self.assertEqual

        a = yield r.set('a', 'a')
        ex = 'OK'
        t(a, ex)
        a = yield isinstance((yield r.randomkey()), str)
        ex = True
        t(a, ex)

    def test_rename_same_src_dest(self):
        r = self.redis
        t = self.assertEqual
        d = r.rename('a', 'a')
        self.failUnlessFailure(d, ResponseError)

        def test_err(a):
            ex = ResponseError('source and destination objects are the same')
            t(str(a), str(ex))

        d.addCallback(test_err)
        return d

    @defer.inlineCallbacks
    def test_rename(self):
        r = self.redis
        t = self.assertEqual

        a = yield r.rename('a', 'b')
        ex = 'OK'
        t(a, ex)
        a = yield r.get('a')
        t(a, None)
        a = yield r.set('a', 1)
        ex = 'OK'
        t(a, ex)
        a = yield r.rename('b', 'a', preserve=True)
        ex = 0
        t(a, ex)

    @defer.inlineCallbacks
    def test_dbsize(self):
        r = self.redis
        t = self.assertTrue
        a = yield r.dbsize()
        t(isinstance(a, int) or isinstance(a, long))

    @defer.inlineCallbacks
    def test_expire(self):
        r = self.redis
        t = self.assertEqual

        a = yield r.set('a', 1)
        ex = 'OK'
        t(a, ex)
        a = yield r.expire('a', 1)
        ex = 1
        t(a, ex)
        a = yield r.expire('zzzzz', 1)
        ex = 0
        t(a, ex)

    @defer.inlineCallbacks
    def test_expireat(self):
        r = self.redis
        t = self.assertEqual

        a = yield r.set('a', 1)
        ex = 'OK'
        t(a, ex)
        a = yield r.expireat('a', int(time.time() + 10))
        ex = 1
        t(a, ex)
        a = yield r.expireat('zzzzz', int(time.time() + 10))
        ex = 0
        t(a, ex)

    @defer.inlineCallbacks
    def test_setex(self):
        r = self.redis
        t = self.assertEqual

        a = yield r.set('q', 1, expire=10)
        ex = 'OK'
        t(a, ex)
        # the following checks the expected response of an EXPIRE on a key with
        # an existing TTL. unfortunately the behaviour of redis changed in
        # v2.1.3 so we have to determine which behaviour to expect...
        info = yield r.info()
        redis_vern = tuple(map(int, info['redis_version'].split('.')))
        if redis_vern < (2, 1, 3):
            ex = 0
        else:
            ex = 1
        a = yield r.expire('q', 1)
        t(a, ex)

    @defer.inlineCallbacks
    def test_mset(self):
        r = self.redis
        t = self.assertEqual

        a = yield r.mset({'ma': 1, 'mb': 2})
        ex = 'OK'
        t(a, ex)

        a = yield r.mset({'ma': 1, 'mb': 2}, preserve=True)
        ex = 0

        a = yield r.msetnx({'ma': 1, 'mb': 2})
        ex = 0
        t(a, ex)

    @defer.inlineCallbacks
    def test_substr(self):
        r = self.redis
        t = self.assertEqual

        string = 'This is a string'
        r.set('s', string)
        a = yield r.substr('s', 0, 3)  # old name
        ex = 'This'
        t(a, ex)
        a = yield r.getrange('s', 0, 3)  # new name
        ex = 'This'
        t(a, ex)

    @defer.inlineCallbacks
    def test_append(self):
        r = self.redis
        t = self.assertEqual

        string = 'some_string'
        a = yield r.set('q', string)
        ex = 'OK'
        t(a, ex)

        addition = 'foo'
        a = yield r.append('q', addition)
        ex = len(string + addition)
        t(a, ex)

    @defer.inlineCallbacks
    def test_ttl(self):
        r = self.redis
        t = self.assertEqual

        a = yield r.ttl('a')
        ex = -1
        t(a, ex)
        a = yield r.expire('a', 10)
        ex = 1
        t(a, ex)
        a = yield r.ttl('a')
        ex = 10
        t(a, ex)
        a = yield r.expire('a', 0)
        ex = 1
        t(a, ex)

    @defer.inlineCallbacks
    def test_select(self):
        r = self.redis
        t = self.assertEqual

        yield r.select(9)
        yield r.delete('a')
        a = yield r.select(10)
        ex = 'OK'
        t(a, ex)
        a = yield r.set('a', 1)
        ex = 'OK'
        t(a, ex)
        a = yield r.select(9)
        ex = 'OK'
        t(a, ex)
        a = yield r.get('a')
        ex = None
        t(a, ex)

    @defer.inlineCallbacks
    def test_move(self):
        r = self.redis
        t = self.assertEqual

        yield r.select(9)
        a = yield r.set('a', 'a')
        ex = 'OK'
        t(a, ex)
        a = yield r.select(10)
        ex = 'OK'
        t(a, ex)
        if (yield r.get('a')):
            yield r.delete('a')
        a = yield r.select(9)
        ex = 'OK'
        t(a, ex)
        a = yield r.move('a', 10)
        ex = 1
        t(a, ex)
        yield r.get('a')
        a = yield r.select(10)
        ex = 'OK'
        t(a, ex)
        a = yield r.get('a')
        ex = u'a'
        t(a, ex)
        a = yield r.select(9)
        ex = 'OK'
        t(a, ex)

    @defer.inlineCallbacks
    def test_flush(self):
        r = self.redis
        t = self.assertEqual

        a = yield r.flush()
        ex = 'OK'
        t(a, ex)

    def test_lastsave(self):
        r = self.redis
        t = self.assertEqual

        tme = int(time.time())
        d = r.save()

        def done_save(a):
            ex = 'OK'
            t(a, ex)
            d = r.lastsave()

            def got_lastsave(a):
                a = a >= tme
                ex = True
                t(a, ex)
            d.addCallback(got_lastsave)
            return d

        def save_err(res):
            if 'Background save already in progress' in str(res):
                return True
            else:
                raise res
        d.addCallbacks(done_save, save_err)
        return d

    @defer.inlineCallbacks
    def test_info(self):
        r = self.redis
        t = self.assertEqual

        info = yield r.info()
        a = info and isinstance(info, dict)
        ex = True
        t(a, ex)
        a = isinstance((yield info.get('connected_clients')), int)
        ex = True
        t(a, ex)

    @defer.inlineCallbacks
    def test_multi(self):
        r = yield self.redis.multi()
        self.assertEqual(r, 'OK')

    @defer.inlineCallbacks
    def test_execute(self):
        # multi with two sets
        yield self.redis.multi()
        r = yield self.redis.set('foo', 'bar')
        self.assertEqual(r, 'QUEUED')
        r = yield self.redis.set('foo', 'barbar')
        self.assertEqual(r, 'QUEUED')
        r = yield self.redis.execute()
        self.assertEqual(r, ['OK', 'OK'])
        r = yield self.redis.get('foo')
        self.assertEqual(r, 'barbar')

    def test_discard(self):
        d = self.redis.execute()
        # discard without multi will return ResponseError
        d = self.failUnlessFailure(d, ResponseError)

        # multi with two sets
        def step1(_res):
            d = self.redis.set('foo', 'bar1')

            def step2(_res):
                d = self.redis.multi()

                def in_multi(_res):
                    d = self.redis.set('foo', 'bar2')

                    def step3(_res):
                        d = self.redis.discard()

                        def step4(r):
                            self.assertEqual(r, 'OK')
                            d = self.redis.get('foo')

                            def got_it(res):
                                self.assertEqual(res, 'bar1')
                            d.addCallback(got_it)
                            return d
                        d.addCallback(step4)
                        return d
                    d.addCallback(step3)
                    return d
                d.addCallback(in_multi)
                return d
            d.addCallback(step2)
            return d

        d.addCallback(step1)
        return d

    @defer.inlineCallbacks
    def test_watch(self):
        r = yield self.redis.watch('foo')
        self.assertEqual(r, 'OK')

    @defer.inlineCallbacks
    def test_unwatch(self):
        yield self.redis.watch('foo')
        r = yield self.redis.unwatch()
        self.assertEqual(r, 'OK')


class StringsCommandTestCase(CommandsBaseTestCase):
    """Test commands that operate on string values.
    """

    @defer.inlineCallbacks
    def test_blank(self):
        yield self.redis.set('a', "")

        r = yield self.redis.get('a')
        self.assertEquals("", r)

    @defer.inlineCallbacks
    def test_set(self):
        a = yield self.redis.set('a', 'pippo')
        self.assertEqual(a, 'OK')

        unicode_str = u'pippo \u3235'
        a = yield self.redis.set('a', unicode_str)
        self.assertEqual(a, 'OK')

        a = yield self.redis.get('a')
        self.assertEqual(a, unicode_str.encode('utf8'))

        a = yield self.redis.set('b', 105.2)
        self.assertEqual(a, 'OK')

        a = yield self.redis.set('b', 'xxx', preserve=True)
        self.assertEqual(a, 0)

        a = yield self.redis.setnx('b', 'xxx')
        self.assertEqual(a, 0)

        a = yield self.redis.get('b')
        self.assertEqual(a, '105.2')

    @defer.inlineCallbacks
    def test_get(self):
        r = self.redis
        t = self.assertEqual

        a = yield r.set('a', 'pippo')
        t(a, 'OK')
        a = yield r.set('b', 15)
        t(a, 'OK')
        a = yield r.set('c', ' \\r\\naaa\\nbbb\\r\\ncccc\\nddd\\r\\n ')
        t(a, 'OK')
        a = yield r.set('d', '\\r\\n')
        t(a, 'OK')

        a = yield r.get('a')
        t(a, u'pippo')

        a = yield r.get('b')
        ex = '15'
        t(a, ex)

        a = yield r.get('d')
        ex = u'\\r\\n'
        t(a, ex)

        a = yield r.get('b')
        ex = '15'
        t(a, ex)

        a = yield r.get('c')
        ex = u' \\r\\naaa\\nbbb\\r\\ncccc\\nddd\\r\\n '
        t(a, ex)

        a = yield r.get('ajhsd')
        ex = None
        t(a, ex)

    @defer.inlineCallbacks
    def test_getset(self):
        r = self.redis
        t = self.assertEqual

        a = yield r.set('a', 'pippo')
        ex = 'OK'
        t(a, ex)

        a = yield r.getset('a', 2)
        ex = u'pippo'
        t(a, ex)

    @defer.inlineCallbacks
    def test_mget(self):
        r = self.redis
        t = self.assertEqual

        a = yield r.set('a', 'pippo')
        ex = 'OK'
        t(a, ex)
        a = yield r.set('b', 15)
        ex = 'OK'
        t(a, ex)
        a = yield r.set('c', '\\r\\naaa\\nbbb\\r\\ncccc\\nddd\\r\\n')
        ex = 'OK'
        t(a, ex)
        a = yield r.set('d', '\\r\\n')
        ex = 'OK'
        t(a, ex)
        a = yield r.mget('a', 'b', 'c', 'd')
        ex = [u'pippo', '15',
              u'\\r\\naaa\\nbbb\\r\\ncccc\\nddd\\r\\n', u'\\r\\n']
        t(a, ex)

    @defer.inlineCallbacks
    def test_incr(self):
        r = self.redis
        t = self.assertEqual

        a = yield r.delete('a')
        ex = 1
        t(a, ex)
        a = yield r.incr('a')
        ex = 1
        t(a, ex)
        a = yield r.incr('a')
        ex = 2
        t(a, ex)
        a = yield r.incr('a', 2)
        ex = 4
        t(a, ex)

    @defer.inlineCallbacks
    def test_decr(self):
        r = self.redis
        t = self.assertEqual

        a = yield r.get('a')
        if a:
            yield r.delete('a')

        a = yield r.decr('a')
        ex = -1
        t(a, ex)
        a = yield r.decr('a')
        ex = -2
        t(a, ex)
        a = yield r.decr('a', 5)
        ex = -7
        t(a, ex)

    @defer.inlineCallbacks
    def test_setbit(self):
        r = self.redis
        yield r.delete('bittest')

        # original value is 0 when value is empty
        orig = yield r.setbit('bittest', 0, 1)
        self.assertEqual(orig, 0)

        # original value is 1 from above
        orig = yield r.setbit('bittest', 0, 0)
        self.assertEqual(orig, 1)

    @defer.inlineCallbacks
    def test_getbit(self):
        r = self.redis
        yield r.delete('bittest')

        yield r.setbit('bittest', 10, 1)
        a = yield r.getbit('bittest', 10)
        self.assertEqual(a, 1)

    @defer.inlineCallbacks
    def test_bitcount(self):
        r = self.redis
        # TODO tearDown or setUp should flushdb?
        yield r.delete('bittest')

        yield r.setbit('bittest', 10, 1)
        yield r.setbit('bittest', 25, 1)
        yield r.setbit('bittest', 3, 1)
        ct = yield r.bitcount('bittest')
        self.assertEqual(ct, 3)

    @defer.inlineCallbacks
    def test_bitcount_with_start_and_end(self):
        r = self.redis
        yield r.delete('bittest')

        yield r.setbit('bittest', 10, 1)
        yield r.setbit('bittest', 25, 1)
        yield r.setbit('bittest', 3, 1)
        ct = yield r.bitcount('bittest', 1, 2)
        self.assertEqual(ct, 1)


class ListsCommandsTestCase(CommandsBaseTestCase):
    """Test commands that operate on lists.
    """

    @defer.inlineCallbacks
    def test_blank_item(self):
        key = 'test:list'
        yield self.redis.delete(key)

        chars = ["a", "", "c"]
        for char in chars:
            yield self.redis.push(key, char)

        r = yield self.redis.lrange(key, 0, len(chars))
        self.assertEquals(["c", "", "a"], r)

    @defer.inlineCallbacks
    def test_concurrent(self):
        """Test ability to handle many large responses at the same time"""
        num_lists = 100
        items_per_list = 50

        # 1. Generate and fill lists
        lists = []
        for l in range(0, num_lists):
            key = 'list-%d' % l
            yield self.redis.delete(key)
            for i in range(0, items_per_list):
                yield self.redis.push(key, 'item-%d' % i)
            lists.append(key)

        # 2. Make requests to get all lists
        ds = []
        for key in lists:
            d = self.redis.lrange(key, 0, items_per_list)
            ds.append(d)

        # 3. Wait on all responses and make sure we got them all
        r = yield defer.DeferredList(ds)
        self.assertEquals(len(r), num_lists)

    @defer.inlineCallbacks
    def test_push(self):
        r = self.redis
        t = self.assertEqual

        a = yield r.delete('l')
        a = yield r.push('l', 'a')
        ex = 1
        t(a, ex)
        a = yield r.set('a', 'a')
        ex = 'OK'
        t(a, ex)

        yield r.delete('l')
        a = yield r.push('l', 'a', no_create=True)
        ex = 0
        t(a, ex)

        a = yield r.push('l', 'a', tail=True, no_create=True)
        ex = 0
        t(a, ex)

    @defer.inlineCallbacks
    def test_push_variable(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('l')
        yield r.lpush('l', 'a', 'b', 'c', 'd')
        a = yield r.llen('l')
        ex = 4
        t(a, ex)

        yield r.rpush('l', 't', 'u', 'v', 'w')
        a = yield r.llen('l')
        ex = 8
        t(a, ex)

    @defer.inlineCallbacks
    def test_llen(self):
        r = self.redis
        t = self.assertEqual

        a = yield r.delete('l')
        a = yield r.push('l', 'a')
        ex = 1
        t(a, ex)
        a = yield r.llen('l')
        ex = 1
        t(a, ex)
        a = yield r.push('l', 'a')
        ex = 2
        t(a, ex)
        a = yield r.llen('l')
        ex = 2
        t(a, ex)

    @defer.inlineCallbacks
    def test_lrange(self):
        r = self.redis
        t = self.assertEqual

        a = yield r.delete('l')
        a = yield r.lrange('l', 0, 1)
        ex = []
        t(a, ex)
        a = yield r.push('l', 'aaa')
        ex = 1
        t(a, ex)
        a = yield r.lrange('l', 0, 1)
        ex = [u'aaa']
        t(a, ex)
        a = yield r.push('l', 'bbb')
        ex = 2
        t(a, ex)
        a = yield r.lrange('l', 0, 0)
        ex = [u'bbb']
        t(a, ex)
        a = yield r.lrange('l', 0, 1)
        ex = [u'bbb', u'aaa']
        t(a, ex)
        a = yield r.lrange('l', -1, 0)
        ex = []
        t(a, ex)
        a = yield r.lrange('l', -1, -1)
        ex = [u'aaa']
        t(a, ex)

    @defer.inlineCallbacks
    def test_ltrim(self):
        r = self.redis
        t = self.assertEqual

        a = yield r.delete('l')
        a = yield r.ltrim('l', 0, 1)
        ex = ResponseError('OK')
        t(str(a), str(ex))
        a = yield r.push('l', 'aaa')
        ex = 1
        t(a, ex)
        a = yield r.push('l', 'bbb')
        ex = 2
        t(a, ex)
        a = yield r.push('l', 'ccc')
        ex = 3
        t(a, ex)
        a = yield r.ltrim('l', 0, 1)
        ex = 'OK'
        t(a, ex)
        a = yield r.llen('l')
        ex = 2
        t(a, ex)
        a = yield r.ltrim('l', 99, 95)
        ex = 'OK'
        t(a, ex)
        a = yield r.llen('l')
        ex = 0
        t(a, ex)

    @defer.inlineCallbacks
    def test_lindex(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('l')
        yield r.lindex('l', 0)
        a = yield r.push('l', 'aaa')
        ex = 1
        t(a, ex)
        a = yield r.lindex('l', 0)
        ex = u'aaa'
        t(a, ex)
        yield r.lindex('l', 2)
        a = yield r.push('l', 'ccc')
        ex = 2
        t(a, ex)
        a = yield r.lindex('l', 1)
        ex = u'aaa'
        t(a, ex)
        a = yield r.lindex('l', -1)
        ex = u'aaa'
        t(a, ex)

    @defer.inlineCallbacks
    def test_pop(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('l')
        yield r.pop('l')
        a = yield r.push('l', 'aaa')
        ex = 1
        t(a, ex)
        a = yield r.push('l', 'bbb')
        ex = 2
        t(a, ex)
        a = yield r.pop('l')
        ex = u'bbb'
        t(a, ex)
        a = yield r.pop('l')
        ex = u'aaa'
        t(a, ex)
        yield r.pop('l')
        a = yield r.push('l', 'aaa')
        ex = 1
        t(a, ex)
        a = yield r.push('l', 'bbb')
        ex = 2
        t(a, ex)
        a = yield r.pop('l', tail=True)
        ex = u'aaa'
        t(a, ex)
        a = yield r.pop('l')
        ex = u'bbb'
        t(a, ex)
        a = yield r.pop('l')
        ex = None
        t(a, ex)

    def test_lset_on_nonexistant_key(self):
        r = self.redis
        t = self.assertEqual

        d = r.delete('l')

        def bad_lset(_res):
            d = r.lset('l', 0, 'a')
            self.failUnlessFailure(d, ResponseError)

            def match_err(a):
                ex = ResponseError('no such key')
                t(str(a), str(ex))
            d.addCallback(match_err)
            return d
        d.addCallback(bad_lset)
        return d

    def test_lset_bad_range(self):
        r = self.redis
        t = self.assertEqual

        d = r.delete('l')

        def proceed(_res):
            d = r.push('l', 'aaa')

            def done_push(a):
                ex = 1
                t(a, ex)
                d = r.lset('l', 1, 'a')
                self.failUnlessFailure(d, ResponseError)

                def check(a):
                    ex = ResponseError('index out of range')
                    t(str(a), str(ex))
                d.addCallback(check)
                return d
            d.addCallback(done_push)
            return d
        d.addCallback(proceed)
        return d

    @defer.inlineCallbacks
    def test_lset(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('l')
        a = yield r.push('l', 'aaa')
        ex = 1
        t(a, ex)
        a = yield r.lset('l', 0, 'bbb')
        ex = 'OK'
        t(a, ex)
        a = yield r.lrange('l', 0, 1)
        ex = [u'bbb']
        t(a, ex)

    @defer.inlineCallbacks
    def test_lrem(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('l')
        a = yield r.push('l', 'aaa')
        ex = 1
        t(a, ex)
        a = yield r.push('l', 'bbb')
        ex = 2
        t(a, ex)
        a = yield r.push('l', 'aaa')
        ex = 3
        t(a, ex)
        a = yield r.lrem('l', 'aaa')
        ex = 2
        t(a, ex)
        a = yield r.lrange('l', 0, 10)
        ex = [u'bbb']
        t(a, ex)
        a = yield r.push('l', 'aaa')
        ex = 2
        t(a, ex)
        a = yield r.push('l', 'aaa')
        ex = 3
        t(a, ex)
        a = yield r.lrem('l', 'aaa', 1)
        ex = 1
        t(a, ex)
        a = yield r.lrem('l', 'aaa', 1)
        ex = 1
        t(a, ex)
        a = yield r.lrem('l', 'aaa', 1)
        ex = 0
        t(a, ex)


class SetsCommandsTestCase(CommandsBaseTestCase):
    """Test commands that operate on sets.
    """

    @defer.inlineCallbacks
    def test_blank(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('s')
        a = yield r.sadd('s', "")
        ex = 1
        t(a, ex)
        a = yield r.smembers('s')
        ex = set([""])
        t(a, ex)

    @defer.inlineCallbacks
    def test_sadd(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('s')
        a = yield r.sadd('s', 'a')
        ex = 1
        t(a, ex)
        a = yield r.sadd('s', 'b')
        ex = 1
        t(a, ex)

    @defer.inlineCallbacks
    def test_sadd_variable(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('s')
        a = yield r.sadd('s', 'a', 'b', 'c', 'd')
        ex = 4
        a = yield r.scard('s')
        ex = 4
        t(a, ex)

    @defer.inlineCallbacks
    def test_sdiff(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('s')
        yield r.delete('t')
        yield r.sadd('s', 'a')
        yield r.sadd('s', 'b')
        yield r.sadd('t', 'a')
        a = yield r.sdiff('s', 't')
        ex = ['b']
        t(a, ex)

        a = yield r.sdiffstore('c', 's', 't')
        ex = 1
        t(a, ex)

        a = yield r.scard('c')
        ex = 1
        t(a, ex)

    @defer.inlineCallbacks
    def test_srandmember(self):
        r = self.redis

        yield r.delete('s')
        yield r.sadd('s', 'a')
        yield r.sadd('s', 'b')
        yield r.sadd('s', 'c')
        a = yield r.srandmember('s')
        self.assertTrue(a in set(['a', 'b', 'c']))

    @defer.inlineCallbacks
    def test_smove(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('s')
        yield r.delete('t')
        yield r.sadd('s', 'a')
        yield r.sadd('t', 'b')
        a = yield r.smove('s', 't', 'a')
        ex = 1
        t(a, ex)
        a = yield r.scard('s')
        ex = 0
        t(a, ex)

    @defer.inlineCallbacks
    def test_srem(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('s')
        a = yield r.srem('s', 'aaa')
        ex = 0
        t(a, ex)
        a = yield r.sadd('s', 'b')
        ex = 1
        t(a, ex)
        a = yield r.srem('s', 'b')
        ex = 1
        t(a, ex)
        a = yield r.sismember('s', 'b')
        ex = 0
        t(a, ex)

    @defer.inlineCallbacks
    def test_srem_variable(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('s')
        a = yield r.sadd('s', 'a', 'b', 'c', 'd')
        ex = 4
        t(a, ex)
        a = yield r.srem('s', 'a', 'b')
        ex = 2
        t(a, ex)
        a = yield r.scard('s')
        ex = 2
        t(a, ex)

    @defer.inlineCallbacks
    def test_spop(self):
        r = self.redis
        t = self.assertEqual

        a = yield r.delete('s')

        a = yield r.sadd('s', 'a')
        ex = 1
        t(a, ex)

        a = yield r.spop('s')
        ex = u'a'
        t(a, ex)

    @defer.inlineCallbacks
    def test_scard(self):
        r = self.redis
        t = self.assertEqual

        a = yield r.delete('s')

        a = yield r.sadd('s', 'a')
        ex = 1
        t(a, ex)

        a = yield r.scard('s')
        ex = 1
        t(a, ex)

    @defer.inlineCallbacks
    def test_sismember(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('s')
        a = yield r.sismember('s', 'b')
        ex = 0
        t(a, ex)
        a = yield r.sadd('s', 'a')
        ex = 1
        t(a, ex)
        a = yield r.sismember('s', 'b')
        ex = 0
        t(a, ex)
        a = yield r.sismember('s', 'a')
        ex = 1
        t(a, ex)

    @defer.inlineCallbacks
    def test_sinter(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('s1')
        yield r.delete('s2')
        yield r.delete('s3')
        a = yield r.sadd('s1', 'a')
        ex = 1
        t(a, ex)
        a = yield r.sadd('s2', 'a')
        ex = 1
        t(a, ex)
        a = yield r.sadd('s3', 'b')
        ex = 1
        t(a, ex)
        a = yield r.sinter('s1', 's2', 's3')
        ex = set([])
        t(a, ex)
        a = yield r.sinter('s1', 's2')
        ex = set([u'a'])
        t(a, ex)

    @defer.inlineCallbacks
    def test_sinterstore(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('s1')
        yield r.delete('s2')
        yield r.delete('s3')
        a = yield r.sadd('s1', 'a')
        ex = 1
        t(a, ex)
        a = yield r.sadd('s2', 'a')
        ex = 1
        t(a, ex)
        a = yield r.sadd('s3', 'b')
        ex = 1
        t(a, ex)
        a = yield r.sinterstore('s_s', 's1', 's2', 's3')
        ex = 0
        t(a, ex)
        a = yield r.sinterstore('s_s', 's1', 's2')
        ex = 1
        t(a, ex)
        a = yield r.smembers('s_s')
        ex = set([u'a'])
        t(a, ex)

    @defer.inlineCallbacks
    def test_smembers(self):
        r = self.redis
        t = self.assertEqual

        a = yield r.delete('s')
        ex = 1
        t(a, ex)
        a = yield r.sadd('s', 'a')
        ex = 1
        t(a, ex)
        a = yield r.sadd('s', 'b')
        ex = 1
        t(a, ex)
        a = yield r.smembers('s')
        ex = set([u'a', u'b'])
        t(a, ex)

    @defer.inlineCallbacks
    def test_sunion(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('s1')
        yield r.delete('s2')
        yield r.delete('s3')
        a = yield r.sadd('s1', 'a')
        ex = 1
        t(a, ex)
        a = yield r.sadd('s2', 'a')
        ex = 1
        t(a, ex)
        a = yield r.sadd('s3', 'b')
        ex = 1
        t(a, ex)
        a = yield r.sunion('s1', 's2', 's3')
        ex = set([u'a', u'b'])
        t(a, ex)
        a = yield r.sadd('s2', 'c')
        ex = 1
        t(a, ex)
        a = yield r.sunion('s1', 's2', 's3')
        ex = set([u'a', u'c', u'b'])
        t(a, ex)

    @defer.inlineCallbacks
    def test_sunionstore(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('s1')
        yield r.delete('s2')
        yield r.delete('s3')
        a = yield r.sadd('s1', 'a')
        ex = 1
        t(a, ex)
        a = yield r.sadd('s2', 'a')
        ex = 1
        t(a, ex)
        a = yield r.sadd('s3', 'b')
        ex = 1
        t(a, ex)
        a = yield r.sunionstore('s4', 's1', 's2', 's3')
        ex = 2
        t(a, ex)
        a = yield r.smembers('s4')
        ex = set([u'a', u'b'])
        t(a, ex)

    @defer.inlineCallbacks
    def test_sort_style(self):
        # considering, given that redis only stores strings, whether the
        # sort it provides is a numeric or a lexicographical sort; turns out
        # that it's numeric; i.e. redis is doing implicit type coercion for
        # the sort of numeric values. This test serves to document that, and
        # to a lesser extent check for regression in the implicit str()
        # marshalling of txredis
        r = self.redis
        t = self.assertEqual
        yield r.delete('l')
        items = [007, 10, -5, 0.1, 100, -3, 20, 0.02, -3.141]
        for i in items:
            yield r.push('l', i, tail=True)
        a = yield r.sort('l')
        ex = map(str, sorted(items))
        t(a, ex)

    @defer.inlineCallbacks
    def test_sort(self):
        r = self.redis
        t = self.assertEqual
        s = lambda l: map(str, l)

        yield r.delete('l')
        a = yield r.push('l', 'ccc')
        ex = 1
        t(a, ex)
        a = yield r.push('l', 'aaa')
        ex = 2
        t(a, ex)
        a = yield r.push('l', 'ddd')
        ex = 3
        t(a, ex)
        a = yield r.push('l', 'bbb')
        ex = 4
        t(a, ex)
        a = yield r.sort('l', alpha=True)
        ex = [u'aaa', u'bbb', u'ccc', u'ddd']
        t(a, ex)
        a = yield r.delete('l')
        ex = 1
        t(a, ex)
        for i in range(1, 5):
            yield r.push('l', 1.0 / i, tail=True)
        a = yield r.sort('l')
        ex = s([0.25, 0.333333333333, 0.5, 1.0])
        t(a, ex)
        a = yield r.sort('l', desc=True)
        ex = s([1.0, 0.5, 0.333333333333, 0.25])
        t(a, ex)
        a = yield r.sort('l', desc=True, start=2, num=1)
        ex = s([0.333333333333])
        t(a, ex)
        a = yield r.set('weight_0.5', 10)
        ex = 'OK'
        t(a, ex)
        a = yield r.sort('l', desc=True, by='weight_*')
        ex = s([0.5, 1.0, 0.333333333333, 0.25])
        t(a, ex)
        for i in (yield r.sort('l', desc=True)):
            yield r.set('test_%s' % i, 100 - float(i))
            yield r.set('second_test_%s' % i, 200 - float(i))
        a = yield r.sort('l', desc=True, get='test_*')
        ex = s([99.0, 99.5, 99.6666666667, 99.75])
        t(a, ex)
        a = yield r.sort('l', desc=True, by='weight_*', get='test_*')
        ex = s([99.5, 99.0, 99.6666666667, 99.75])
        t(a, ex)
        a = yield r.sort('l', desc=True, by='weight_*', get=['test_*', 'second_test_*'])
        ex = s([99.5, 199.5, 99.0, 199.0, 99.6666666667, 199.6666666667, 99.75, 199.75])
        t(a, ex)
        a = yield r.sort('l', desc=True, by='weight_*', get='missing_*')
        ex = [None, None, None, None]
        t(a, ex)

    @defer.inlineCallbacks
    def test_large_values(self):
        import uuid
        import random
        r = self.redis
        t = self.assertEqual

        for i in range(5):
            key = str(uuid.uuid4())
            value = random.randrange(10 ** 40000, 11 ** 40000)
            a = yield r.set(key, value)
            t('OK', a)
            rval = yield r.get(key)
            t(rval, str(value))


class HashCommandsTestCase(CommandsBaseTestCase):
    """Test commands that operate on hashes.
    """

    @defer.inlineCallbacks
    def test_blank(self):
        yield self.redis.delete('h')
        yield self.redis.hset('h', 'blank', "")
        a = yield self.redis.hget('h', 'blank')
        self.assertEquals(a, '')
        a = yield self.redis.hgetall('h')
        self.assertEquals(a, {'blank': ''})

    @defer.inlineCallbacks
    def test_cas(self):
        r = self.redis
        t = self.assertEqual

        a = yield r.delete('h')
        ex = 1
        t(a, ex)

        a = yield r.hsetnx('h', 'f', 'v')
        ex = 1
        t(a, ex)

        a = yield r.hsetnx('h', 'f', 'v')
        ex = 0
        t(a, ex)

    @defer.inlineCallbacks
    def test_basic(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('d')

        a = yield r.hexists('d', 'k')
        ex = 0
        t(a, ex)

        yield r.hset('d', 'k', 'v')

        a = yield r.hexists('d', 'k')
        ex = 1
        t(a, ex)

        a = yield r.hget('d', 'k')
        ex = {'k': 'v'}
        t(a, ex)
        a = yield r.hset('d', 'new', 'b', preserve=True)
        ex = 1
        t(a, ex)
        a = yield r.hset('d', 'new', 'b', preserve=True)
        ex = 0
        t(a, ex)
        yield r.hdelete('d', 'new')

        yield r.hset('d', 'f', 's')
        a = yield r.hgetall('d')
        ex = dict(k='v', f='s')
        t(a, ex)

        a = yield r.hgetall('foo')
        ex = {}
        t(a, ex)

        a = yield r.hget('d', 'notexist')
        ex = None
        t(a, ex)

        a = yield r.hlen('d')
        ex = 2
        t(a, ex)

    @defer.inlineCallbacks
    def test_hdel(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('d')
        yield r.hset('d', 'a', 'vala')
        yield r.hmset('d', {'a': 'vala', 'b': 'valb', 'c': 'valc'})
        a = yield r.hdel('d', 'a', 'b', 'c')
        ex = 3
        t(a, ex)
        a = yield r.hgetall('d')
        ex = {}
        t(a, ex)

    def test_hdel_failure(self):
        self.assertRaises(InvalidCommand, self.redis.hdel, 'key')

    @defer.inlineCallbacks
    def test_hincr(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('d')
        yield r.hset('d', 'k', 0)
        a = yield r.hincr('d', 'k')
        ex = 1
        t(a, ex)

        a = yield r.hincr('d', 'k')
        ex = 2
        t(a, ex)

    @defer.inlineCallbacks
    def test_hget(self):
        r = self.redis
        t = self.assertEqual

        yield r.hdelete('key', 'field')
        yield r.hset('key', 'field', 'value1')
        a = yield r.hget('key', 'field')
        ex = {'field': 'value1'}
        t(a, ex)

    @defer.inlineCallbacks
    def test_hmget(self):
        r = self.redis
        t = self.assertEqual

        yield r.hdelete('d', 'k')
        yield r.hdelete('d', 'j')
        yield r.hset('d', 'k', 'v')
        yield r.hset('d', 'j', 'p')
        a = yield r.hget('d', ['k', 'j'])
        ex = {'k': 'v', 'j': 'p'}
        t(a, ex)

    @defer.inlineCallbacks
    def test_hmset(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('d')
        in_dict = dict(k='v', j='p')
        a = yield r.hmset('d', in_dict)
        ex = 'OK'
        t(a, ex)

        a = yield r.hgetall('d')
        ex = in_dict
        t(a, ex)

    @defer.inlineCallbacks
    def test_hkeys(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('d')
        in_dict = dict(k='v', j='p')
        yield r.hmset('d', in_dict)

        a = yield r.hkeys('d')
        ex = ['k', 'j']
        t(a, ex)

    @defer.inlineCallbacks
    def test_hvals(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('d')
        in_dict = dict(k='v', j='p')
        yield r.hmset('d', in_dict)

        a = yield r.hvals('d')
        ex = ['v', 'p']
        t(a, ex)


class LargeMultiBulkTestCase(CommandsBaseTestCase):
    @defer.inlineCallbacks
    def test_large_multibulk(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('s')
        data = set(xrange(1, 100000))
        for i in data:
            r.sadd('s', i)
        res = yield r.smembers('s')
        t(res, set(map(str, data)))


class MultiBulkTestCase(CommandsBaseTestCase):
    @defer.inlineCallbacks
    def test_nested_multibulk(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('str1', 'str2', 'list1', 'list2')
        yield r.set('str1', 'str1')
        yield r.set('str2', 'str2')
        yield r.lpush('list1', 'b1')
        yield r.lpush('list1', 'a1')
        yield r.lpush('list2', 'b2')
        yield r.lpush('list2', 'a2')

        r.multi()
        r.get('str1')
        r.lrange('list1', 0, -1)
        r.get('str2')
        r.lrange('list2', 0, -1)
        r.get('notthere')

        a = yield r.execute()
        ex = ['str1', ['a1', 'b1'], 'str2', ['a2', 'b2'], None]
        t(a, ex)

        a = yield r.get('str2')
        ex = 'str2'
        t(a, ex)

    @defer.inlineCallbacks
    def test_empty_multibulk(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('list1')
        a = yield r.lrange('list1', 0, -1)
        ex = []
        t(a, ex)

    @defer.inlineCallbacks
    def test_null_multibulk(self):
        r = self.redis
        t = self.assertEqual

        clientCreator = protocol.ClientCreator(reactor, self.protocol)
        r2 = yield clientCreator.connectTCP(REDIS_HOST, REDIS_PORT)

        yield r.delete('a')

        r.watch('a')
        r.multi()
        yield r.set('a', 'a')
        yield r2.set('a', 'b')

        r2.transport.loseConnection()

        a = yield r.execute()
        ex = None
        t(a, ex)


class SortedSetCommandsTestCase(CommandsBaseTestCase):
    """Test commands that operate on sorted sets.
    """
    @defer.inlineCallbacks
    def test_basic(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('z')
        a = yield r.zadd('z', 'a', 1)
        ex = 1
        t(a, ex)
        yield r.zadd('z', 'b', 2.142)

        a = yield r.zrank('z', 'a')
        ex = 0
        t(a, ex)

        a = yield r.zrank('z', 'a', reverse=True)
        ex = 1
        t(a, ex)

        a = yield r.zcard('z')
        ex = 2
        t(a, ex)

        a = yield r.zscore('z', 'b')
        ex = 2.142
        t(a, ex)

        a = yield r.zrange('z', 0, -1, withscores=True)
        ex = [('a', 1), ('b', 2.142)]
        t(a, ex)

        a = yield r.zrem('z', 'a')
        ex = 1
        t(a, ex)

    @defer.inlineCallbacks
    def test_zcount(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('z')
        yield r.zadd('z', 'a', 1)
        yield r.zadd('z', 'b', 2)
        yield r.zadd('z', 'c', 3)
        yield r.zadd('z', 'd', 4)
        a = yield r.zcount('z', 1, 3)
        ex = 3
        t(a, ex)

    @defer.inlineCallbacks
    def test_zremrange(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('z')
        yield r.zadd('z', 'a', 1.0)
        yield r.zadd('z', 'b', 2.0)
        yield r.zadd('z', 'c', 3.0)
        yield r.zadd('z', 'd', 4.0)

        a = yield r.zremrangebyscore('z', 1.0, 3.0)
        ex = 3
        t(a, ex)

        yield r.zadd('z', 'a', 1.0)
        yield r.zadd('z', 'b', 2.0)
        yield r.zadd('z', 'c', 3.0)
        a = yield r.zremrangebyrank('z', 0, 2)
        ex = 3
        t(a, ex)

    @defer.inlineCallbacks
    def test_add_variable(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('z')
        yield r.zadd('z', 'a', 1.0)
        a = yield r.zcard('z')
        ex = 1
        t(a, ex)

        # NB. note how for multiple argument it's score then val
        yield r.zadd('z', 2.0, 'b', 3.0, 'c')
        a = yield r.zcard('z')
        ex = 3

    @defer.inlineCallbacks
    def test_zrem_variable(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('z')
        yield r.zadd('z', 'a', 1.0)
        a = yield r.zcard('z')
        ex = 1
        t(a, ex)

        # NB. note how for multiple argument it's score then val
        yield r.zadd('z', 2.0, 'b', 3.0, 'c')
        a = yield r.zcard('z')
        ex = 3
        t(a, ex)

        yield r.zrem('z', 'a', 'b', 'c')
        a = yield r.zcard('z')
        ex = 0
        t(a, ex)

    @defer.inlineCallbacks
    def test_zrangebyscore(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('z')
        a = yield r.zrangebyscore('z', -1, -1, withscores=True)
        ex = []
        t(a, ex)

        yield r.zadd('z', 'a', 1.014)
        yield r.zadd('z', 'b', 4.252)
        yield r.zadd('z', 'c', 0.232)
        yield r.zadd('z', 'd', 10.425)
        a = yield r.zrangebyscore('z')
        ex = ['c', 'a', 'b', 'd']
        t(a, ex)

        a = yield r.zrangebyscore('z', count=2)
        ex = ['c', 'a']
        t(a, ex)

        a = yield r.zrangebyscore('z', offset=1, count=2)
        ex = ['a', 'b']
        t(a, ex)

        a = yield r.zrangebyscore('z', offset=1, count=2, withscores=True)
        ex = [('a', 1.014), ('b', 4.252)]
        t(a, ex)

        a = yield r.zrangebyscore('z', min=1, offset=1, count=2,
                                  withscores=True)
        ex = [('b', 4.252), ('d', 10.425)]

    @defer.inlineCallbacks
    def test_zrevrangebyscore(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('z')
        a = yield r.zrevrangebyscore('z', -1, -1, withscores=True)
        ex = []
        t(a, ex)

        yield r.zadd('z', 'a', 1.014)
        yield r.zadd('z', 'b', 4.252)
        yield r.zadd('z', 'c', 0.232)
        yield r.zadd('z', 'd', 10.425)
        a = yield r.zrevrangebyscore('z')
        ex = 'd b a c'.split()
        t(a, ex)

        a = yield r.zrevrangebyscore('z', count=2)
        ex = 'd b'.split()
        t(a, ex)

        a = yield r.zrevrangebyscore('z', offset=1, count=2)
        ex = 'b a'.split()
        t(a, ex)

        a = yield r.zrevrangebyscore('z', offset=1, count=2, withscores=True)
        ex = [('b', 4.252), ('a', 1.014)]
        t(a, ex)

        a = yield r.zrevrangebyscore('z', max=10, offset=1, count=2,
                                     withscores=True)
        ex = [('a', 1.014), ('c', 0.232)]

    @defer.inlineCallbacks
    def test_zscore_and_zrange_nonexistant(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('a')
        a = yield r.zscore('a', 'somekey')
        t(a, None)

        yield r.delete('a')
        a = yield r.zrange('a', 0, -1, withscores=True)
        t(a, [])

    @defer.inlineCallbacks
    def test_zaggregatestore(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('a')
        yield r.delete('b')
        yield r.delete('t')

        yield r.zadd('a', 'a', 1.0)
        yield r.zadd('a', 'b', 2.0)
        yield r.zadd('a', 'c', 3.0)
        yield r.zadd('b', 'a', 1.0)
        yield r.zadd('b', 'b', 2.0)
        yield r.zadd('b', 'c', 3.0)

        a = yield r.zunionstore('t', ['a', 'b'])
        ex = 3
        t(a, ex)

        a = yield r.zscore('t', 'a')
        ex = 2
        t(a, ex)

        yield r.delete('t')
        a = yield r.zunionstore('t', {'a': 2.0, 'b': 2.0})
        ex = 3
        t(a, ex)

        a = yield r.zscore('t', 'a')
        ex = 4
        t(a, ex)

        yield r.delete('t')
        a = yield r.zunionstore('t', {'a': 2.0, 'b': 2.0}, aggregate='MAX')
        ex = 3
        t(a, ex)

        a = yield r.zscore('t', 'a')
        ex = 2
        t(a, ex)

        yield r.delete('t')
        a = yield r.zinterstore('t', {'a': 2.0, 'b': 2.0}, aggregate='MAX')
        ex = 3
        t(a, ex)


class ScriptingCommandsTestCase(CommandsBaseTestCase):
    """
    Test for Lua scripting commands.
    """

    _skipped = False

    @defer.inlineCallbacks
    def setUp(self):
        yield CommandsBaseTestCase.setUp(self)
        if ScriptingCommandsTestCase._skipped:
            self.redis.transport.loseConnection()
            raise SkipTest(ScriptingCommandsTestCase._skipped)
        info = yield self.redis.info()
        if 'used_memory_lua' not in info:
            ScriptingCommandsTestCase._skipped = (
                    'Scripting commands not available in Redis version %s' %
                    info['redis_version'])
            self.redis.transport.loseConnection()
            raise SkipTest(ScriptingCommandsTestCase._skipped)

    @defer.inlineCallbacks
    def test_eval(self):
        r = self.redis
        t = self.assertEqual

        source = 'return "ok"'
        a = yield r.eval(source)
        ex = 'ok'
        t(a, ex)

        source = ('redis.call("SET", KEYS[1], ARGV[1]) '
                  'return redis.call("GET", KEYS[1])')
        a = yield r.eval(source, ('test_eval',), ('x',))
        ex = 'x'
        t(a, ex)

        source = 'return {ARGV[1], ARGV[2]}'
        a = yield r.eval(source, args=('a', 'b'))
        ex = ['a', 'b']
        t(a, ex)

    @defer.inlineCallbacks
    def test_evalsha(self):
        r = self.redis
        t = self.assertEqual

        source = 'return "ok"'
        yield r.eval(source)
        sha1 = hashlib.sha1(source).hexdigest()
        a = yield r.evalsha(sha1)
        ex = 'ok'
        t(a, ex)

        source = ('redis.call("SET", KEYS[1], ARGV[1]) '
                  'return redis.call("GET", KEYS[1])')
        yield r.eval(source, ('test_eval2',), ('x',))
        sha1 = hashlib.sha1(source).hexdigest()
        a = yield r.evalsha(sha1, ('test_eval3',), ('y',))
        ex = 'y'
        t(a, ex)

        source = 'return {ARGV[1], ARGV[2]}'
        yield r.eval(source, args=('a', 'b'))
        sha1 = hashlib.sha1(source).hexdigest()
        a = yield r.evalsha(sha1, args=('c', 'd'))
        ex = ['c', 'd']
        t(a, ex)

    def test_no_script(self):
        r = self.redis
        sha1 = hashlib.sha1('banana').hexdigest()
        d = r.evalsha(sha1)
        self.assertFailure(d, NoScript)
        return d

    @defer.inlineCallbacks
    def test_script_load(self):
        r = self.redis
        t = self.assertEqual

        source = ('redis.call("SET", KEYS[1], ARGV[1]) '
                  'return redis.call("GET", KEYS[1])')
        a = yield r.script_load(source)
        ex = hashlib.sha1(source).hexdigest()
        t(a, ex)

    @defer.inlineCallbacks
    def test_script_exists(self):
        r = self.redis
        t = self.assertEqual

        source = ('redis.call("SET", KEYS[1], ARGV[1]) '
                  'return redis.call("GET", KEYS[1])')
        yield r.script_load(source)
        script1 = hashlib.sha1(source).hexdigest()
        script2 = hashlib.sha1('banana').hexdigest()

        a = yield r.script_exists(script1, script2)
        ex = [True, False]
        t(a, ex)

    @defer.inlineCallbacks
    def test_script_flush(self):
        r = self.redis
        t = self.assertEqual

        source = ('redis.call("SET", KEYS[1], ARGV[1]) '
                  'return redis.call("GET", KEYS[1])')
        yield r.script_load(source)
        script1 = hashlib.sha1(source).hexdigest()
        source = 'return "ok"'
        yield r.script_load(source)
        script2 = hashlib.sha1(source).hexdigest()

        yield r.script_flush()
        a = yield r.script_exists(script1, script2)
        ex = [False, False]
        t(a, ex)

    def test_script_kill(self):
        r = self.redis
        t = self.assertEqual

        def eb(why):
            t(str(why.value), 'No scripts in execution right now.')
            return why

        d = r.script_kill()
        d.addErrback(eb)
        self.assertFailure(d, NotBusy)

        return d


class BlockingListOperartionsTestCase(CommandsBaseTestCase):
    """@todo test timeout
    @todo robustly test async/blocking redis commands
    """

    @defer.inlineCallbacks
    def test_bpop_noblock(self):
        r = self.redis
        t = self.assertEqual

        yield r.delete('test.list.a')
        yield r.delete('test.list.b')
        yield r.push('test.list.a', 'stuff')
        yield r.push('test.list.a', 'things')
        yield r.push('test.list.b', 'spam')
        yield r.push('test.list.b', 'bee')
        yield r.push('test.list.b', 'honey')

        a = yield r.bpop(['test.list.a', 'test.list.b'])
        ex = ['test.list.a', 'things']
        t(a, ex)
        a = yield r.bpop(['test.list.b', 'test.list.a'])
        ex = ['test.list.b', 'honey']
        t(a, ex)
        a = yield r.bpop(['test.list.a', 'test.list.b'])
        ex = ['test.list.a', 'stuff']
        t(a, ex)
        a = yield r.bpop(['test.list.b', 'test.list.a'])
        ex = ['test.list.b', 'bee']
        t(a, ex)
        a = yield r.bpop(['test.list.a', 'test.list.b'])
        ex = ['test.list.b', 'spam']
        t(a, ex)

    @defer.inlineCallbacks
    def test_bpop_block(self):
        r = self.redis
        t = self.assertEqual

        clientCreator = protocol.ClientCreator(reactor, Redis)
        r2 = yield clientCreator.connectTCP(REDIS_HOST, REDIS_PORT)

        def _cb(reply, ex):
            t(reply, ex)

        yield r.delete('test.list.a')
        yield r.delete('test.list.b')

        d = r.bpop(['test.list.a', 'test.list.b'])
        ex = ['test.list.a', 'stuff']
        d.addCallback(_cb, ex)

        yield r2.push('test.list.a', 'stuff')

        yield d
        r2.transport.loseConnection()


class NetworkTestCase(unittest.TestCase):

    def setUp(self):
        self.proto = Redis()
        self.clock = Clock()
        self.proto.callLater = self.clock.callLater
        self.transport = StringTransportWithDisconnection()
        self.transport.protocol = self.proto
        self.proto.makeConnection(self.transport)

    def test_request_while_disconnected(self):
        # fake disconnect
        self.proto._disconnected = True

        d = self.proto.get('foo')
        self.assertFailure(d, RuntimeError)

        def checkMessage(error):
            self.assertEquals(str(error), 'Not connected')

        return d.addCallback(checkMessage)

    def test_disconnect_during_request(self):
        d1 = self.proto.get("foo")
        d2 = self.proto.get("bar")
        self.assertEquals(len(self.proto._request_queue), 2)

        self.transport.loseConnection()
        done = defer.DeferredList([d1, d2], consumeErrors=True)

        def checkFailures(results):
            self.assertEquals(len(self.proto._request_queue), 0)
            for success, result in results:
                self.assertFalse(success)
                result.trap(error.ConnectionDone)

        return done.addCallback(checkFailures)


class ProtocolTestCase(unittest.TestCase):

    def setUp(self):
        self.proto = Redis()
        self.transport = StringTransportWithDisconnection()
        self.transport.protocol = self.proto
        self.proto.makeConnection(self.transport)

    def sendResponse(self, data):
        self.proto.dataReceived(data)

    def test_error_response(self):
        # pretending 'foo' is a set, so get is incorrect
        d = self.proto.get("foo")
        self.assertEquals(self.transport.value(),
                          '*2\r\n$3\r\nGET\r\n$3\r\nfoo\r\n')
        msg = "Operation against a key holding the wrong kind of value"
        self.sendResponse("-%s\r\n" % msg)
        self.failUnlessFailure(d, ResponseError)

        def check_err(r):
            self.assertEquals(str(r), msg)
        return d

    @defer.inlineCallbacks
    def test_singleline_response(self):
        d = self.proto.ping()
        self.assertEquals(self.transport.value(), '*1\r\n$4\r\nPING\r\n')
        self.sendResponse("+PONG\r\n")
        r = yield d
        self.assertEquals(r, 'PONG')

    @defer.inlineCallbacks
    def test_bulk_response(self):
        d = self.proto.get("foo")
        self.assertEquals(self.transport.value(),
                          '*2\r\n$3\r\nGET\r\n$3\r\nfoo\r\n')
        self.sendResponse("$3\r\nbar\r\n")
        r = yield d
        self.assertEquals(r, 'bar')

    @defer.inlineCallbacks
    def test_multibulk_response(self):
        d = self.proto.lrange("foo", 0, 1)
        expected = '*4\r\n$6\r\nLRANGE\r\n$3\r\nfoo\r\n$1\r\n0\r\n$1\r\n1\r\n'
        self.assertEquals(self.transport.value(), expected)
        self.sendResponse("*2\r\n$3\r\nbar\r\n$6\r\nlolwut\r\n")
        r = yield d
        self.assertEquals(r, ['bar', 'lolwut'])

    @defer.inlineCallbacks
    def test_integer_response(self):
        d = self.proto.dbsize()
        self.assertEquals(self.transport.value(), '*1\r\n$6\r\nDBSIZE\r\n')
        self.sendResponse(":1234\r\n")
        r = yield d
        self.assertEquals(r, 1234)


class TestFactory(CommandsBaseTestCase):

    def setUp(self):
        d = CommandsBaseTestCase.setUp(self)

        def do_setup(_res):
            self.factory = RedisClientFactory()
            reactor.connectTCP(REDIS_HOST, REDIS_PORT, self.factory)
            d = self.factory.deferred

            def cannot_connect(_res):
                raise unittest.SkipTest('Cannot connect to Redis.')

            d.addErrback(cannot_connect)
            return d

        d.addCallback(do_setup)
        return d

    def tearDown(self):
        CommandsBaseTestCase.tearDown(self)
        self.factory.continueTrying = 0
        self.factory.stopTrying()
        if self.factory.client:
            self.factory.client.setTimeout(None)
            self.factory.client.transport.loseConnection()

    @defer.inlineCallbacks
    def test_reconnect(self):
        a = yield self.factory.client.info()
        self.assertTrue('uptime_in_days' in a)

        # teardown the connection
        self.factory.client.transport.loseConnection()

        # wait until reconnected
        a = yield self.factory.deferred

        a = yield self.factory.client.info()
        self.assertTrue('uptime_in_days' in a)
    timeout = 4


class ProtocolBufferingTestCase(ProtocolTestCase):

    def sendResponse(self, data):
        """Send a response one character at a time to test buffering"""
        for char in data:
            self.proto.dataReceived(char)


class PubSubCommandsTestCase(CommandsBaseTestCase):

    @defer.inlineCallbacks
    def setUp(self):
        yield CommandsBaseTestCase.setUp(self)

        class TestSubscriber(RedisSubscriber):

            def __init__(self, *args, **kwargs):
                RedisSubscriber.__init__(self, *args, **kwargs)
                self.msg_channel = None
                self.msg_message = None
                self.msg_received = defer.Deferred()
                self.channel_subscribed = defer.Deferred()

            def messageReceived(self, channel, message):
                self.msg_channel = channel
                self.msg_message = message
                self.msg_received.callback(None)
                self.msg_received = defer.Deferred()

            def channelSubscribed(self, channel, numSubscriptions):
                self.channel_subscribed.callback(None)
                self.channel_subscribed = defer.Deferred()
            channelUnsubscribed = channelSubscribed
            channelPatternSubscribed = channelSubscribed
            channelPatternUnsubscribed = channelSubscribed

        clientCreator = protocol.ClientCreator(reactor, TestSubscriber)
        self.subscriber = yield clientCreator.connectTCP(REDIS_HOST,
                                                         REDIS_PORT)

    def tearDown(self):
        CommandsBaseTestCase.tearDown(self)
        self.subscriber.transport.loseConnection()

    @defer.inlineCallbacks
    def test_subscribe(self):
        s = self.subscriber
        t = self.assertEqual

        cb = s.channel_subscribed
        yield s.subscribe("channelA")
        yield cb

        cb = s.msg_received
        a = yield self.redis.publish("channelA", "dataB")
        ex = 1
        t(a, ex)
        yield cb
        a = s.msg_channel
        ex = "channelA"
        t(a, ex)
        a = s.msg_message
        ex = "dataB"
        t(a, ex)

    @defer.inlineCallbacks
    def test_unsubscribe(self):
        s = self.subscriber

        cb = s.channel_subscribed
        yield s.subscribe("channelA", "channelB", "channelC")
        yield cb

        cb = s.channel_subscribed
        yield s.unsubscribe("channelA", "channelC")
        yield cb

        yield s.unsubscribe()

    @defer.inlineCallbacks
    def test_psubscribe(self):
        s = self.subscriber
        t = self.assertEqual

        cb = s.channel_subscribed
        yield s.psubscribe("channel*", "magic*")
        yield cb

        cb = s.msg_received
        a = yield self.redis.publish("channelX", "dataC")
        ex = 1
        t(a, ex)
        yield cb
        a = s.msg_channel
        ex = "channelX"
        t(a, ex)
        a = s.msg_message
        ex = "dataC"
        t(a, ex)

    @defer.inlineCallbacks
    def test_punsubscribe(self):
        s = self.subscriber

        cb = s.channel_subscribed
        yield s.psubscribe("channel*", "magic*", "woot*")
        yield cb

        cb = s.channel_subscribed
        yield s.punsubscribe("channel*", "woot*")
        yield cb
        yield s.punsubscribe()

########NEW FILE########
__FILENAME__ = test_hiredis
# if hiredis and its python wrappers are installed, test them too
try:
    import hiredis
    isHiRedis = True

except ImportError:
    isHiRedis = False

from txredis.client import HiRedisClient
from txredis.tests import test_client


if isHiRedis:

    class HiRedisGeneral(test_client.GeneralCommandTestCase):
        protcol = HiRedisClient

    class HiRedisStrings(test_client.StringsCommandTestCase):
        protocol = HiRedisClient

    class HiRedisLists(test_client.ListsCommandsTestCase):
        protocol = HiRedisClient

    class HiRedisHash(test_client.HashCommandsTestCase):
        protocol = HiRedisClient

    class HiRedisSortedSet(test_client.SortedSetCommandsTestCase):
        protocol = HiRedisClient

    class HiRedisSets(test_client.SetsCommandsTestCase):
        protocol = HiRedisClient

    _hush_pyflakes = hiredis
    del _hush_pyflakes

########NEW FILE########
