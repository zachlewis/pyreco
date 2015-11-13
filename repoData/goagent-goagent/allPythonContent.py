__FILENAME__ = addto-startup
#!/usr/bin/env python
# coding:utf-8

from __future__ import with_statement

__version__ = '1.0'

import sys
import os
import re
import time
import ctypes
import platform

python2 = os.popen('python2 -V 2>&1').read().startswith('Python 2.') and 'python2' or 'python'

def addto_startup_linux():
    filename = os.path.abspath(__file__)
    dirname = os.path.dirname(filename)
    #you can change it to 'proxy.py' if you like :)
    scriptname = 'goagent-gtk.py'
    DESKTOP_FILE = '''\
[Desktop Entry]
Type=Application
Categories=Network;Proxy;
Exec=/usr/bin/env %s "%s/%s"
Icon=%s/goagent-logo.png
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Name=GoAgent GTK
Comment=GoAgent GTK Launcher
''' % (python2, dirname , scriptname , dirname)
    #sometimes maybe  /etc/xdg/autostart , ~/.kde/Autostart/ , ~/.config/openbox/autostart
    for dirname in map(os.path.expanduser, ['~/.config/autostart']):
        if os.path.isdir(dirname):
            filename = os.path.join(dirname, 'goagent-gtk.desktop')
            with open(filename, 'w') as fp:
                fp.write(DESKTOP_FILE)
           # os.chmod(filename, 0755)


def addto_startup_osx():
    if os.getuid() != 0:
        print 'please use sudo run this script'
        sys.exit()
    import plistlib
    plist = dict(
            GroupName = 'wheel',
            Label = 'org.goagent.macos',
            ProgramArguments = list([
                '/usr/bin/%s' % python2,
                os.path.join(os.path.abspath(os.path.dirname(__file__)), 'proxy.py')
                ]),
            RunAtLoad = True,
            UserName = 'root',
            WorkingDirectory = os.path.dirname(__file__),
            StandardOutPath = '/var/log/goagent.log',
            StandardErrorPath = '/var/log/goagent.log',
            KeepAlive = dict(
                SuccessfulExit = False,
                )
            )
    filename = '/Library/LaunchDaemons/org.goagent.macos.plist'
    print 'write plist to %s' % filename
    plistlib.writePlist(plist, filename)
    print 'write plist to %s done' % filename
    print 'Adding CA.crt to system keychain, You may need to input your password...'
    cmd = 'sudo security add-trusted-cert -d -r trustRoot -k "/Library/Keychains/System.keychain" "%s/CA.crt"' % os.path.abspath(os.path.dirname(__file__))
    if os.system(cmd) != 0:
        print 'Adding CA.crt to system keychain Failed!'
        sys.exit(0)
    print 'Adding CA.crt to system keychain Done'
    print 'To start goagent right now, try this command: sudo launchctl load /Library/LaunchDaemons/org.goagent.macos.plist'
    print 'To checkout log file: using Console.app to locate /var/log/goagent.log'

    install_sharp_osx()


def install_sharp_osx():
    # extracted from SwitchySharp.crx
    extension_id = 'dpplabbmogkhghncfbfdeeokoefdjegm'
    extension_version = '1.10.2'
    extension_path = '%s/SwitchySharp.crx' % os.path.abspath(os.path.dirname(__file__))

    dest_path = '/Library/Application Support/Google/Chrome/External Extensions'
    dest_file = '%s/%s.json' % (dest_path, extension_id)
    print 'Installing SwitchySharp for Chrome...'
    cmd = 'mkdir -p "%s"' % dest_path
    if os.system(cmd) != 0:
        print 'Create Chrome External Extensions folder Failed!'
        sys.exit(0)

    json_dict = {'external_crx': extension_path,
                 'external_version': extension_version}
    with open(dest_file, 'w') as fp:
        import json
        json.dump(json_dict, fp)
        print 'Installing SwitchySharp done.'


def addto_startup_windows():
    if 1 == ctypes.windll.user32.MessageBoxW(None, u'是否将goagent.exe加入到启动项？', u'GoAgent 对话框', 1):
        if 1 == ctypes.windll.user32.MessageBoxW(None, u'是否显示托盘区图标？', u'GoAgent 对话框', 1):
            pass


def addto_startup_unknown():
    print '*** error: Unknown system'


def main():
    addto_startup_funcs = {
            'Darwin'    : addto_startup_osx,
            'Windows'   : addto_startup_windows,
            'Linux'     : addto_startup_linux,
            }
    addto_startup_funcs.get(platform.system(), addto_startup_unknown)()


if __name__ == '__main__':
   try:
       main()
   except KeyboardInterrupt:
       pass

########NEW FILE########
__FILENAME__ = dnsproxy
#!/usr/bin/env python
# coding:utf-8

__version__ = '1.0'

import sys
import os
import glob

sys.path += glob.glob('*.egg')

import gevent
import gevent.server
import gevent.timeout
import gevent.monkey
gevent.monkey.patch_all(subprocess=True)

import re
import time
import logging
import heapq
import socket
import select
import struct
import errno
import thread
import dnslib
import Queue
try:
    import pygeoip
except ImportError:
    pygeoip = None


is_local_addr = re.compile(r'(?i)(?:[0-9a-f:]+0:5efe:)?(?:127(?:\.\d+){3}|10(?:\.\d+){3}|192\.168(?:\.\d+){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d+){2})').match


def get_dnsserver_list():
    if os.name == 'nt':
        import ctypes, ctypes.wintypes, struct, socket
        DNS_CONFIG_DNS_SERVER_LIST = 6
        buf = ctypes.create_string_buffer(2048)
        ctypes.windll.dnsapi.DnsQueryConfig(DNS_CONFIG_DNS_SERVER_LIST, 0, None, None, ctypes.byref(buf), ctypes.byref(ctypes.wintypes.DWORD(len(buf))))
        ipcount = struct.unpack('I', buf[0:4])[0]
        iplist = [socket.inet_ntoa(buf[i:i+4]) for i in xrange(4, ipcount*4+4, 4)]
        return iplist
    elif os.path.isfile('/etc/resolv.conf'):
        with open('/etc/resolv.conf', 'rb') as fp:
            return re.findall(r'(?m)^nameserver\s+(\S+)', fp.read())
    else:
        logging.warning("get_dnsserver_list failed: unsupport platform '%s-%s'", sys.platform, os.name)
        return []


def parse_hostport(host, default_port=80):
    m = re.match(r'(.+)[#](\d+)$', host)
    if m:
        return m.group(1).strip('[]'), int(m.group(2))
    else:
        return host.strip('[]'), default_port


class ExpireCache(object):
    """ A dictionary-like object, supporting expire semantics."""
    def __init__(self, max_size=1024):
        self.__maxsize = max_size
        self.__values = {}
        self.__expire_times = {}
        self.__expire_heap = []

    def size(self):
        return len(self.__values)

    def clear(self):
        self.__values.clear()
        self.__expire_times.clear()
        del self.__expire_heap[:]

    def exists(self, key):
        return key in self.__values

    def set(self, key, value, expire):
        try:
            et = self.__expire_times[key]
            pos = self.__expire_heap.index((et, key))
            del self.__expire_heap[pos]
            if pos < len(self.__expire_heap):
                heapq._siftup(self.__expire_heap, pos)
        except KeyError:
            pass
        et = int(time.time() + expire)
        self.__expire_times[key] = et
        heapq.heappush(self.__expire_heap, (et, key))
        self.__values[key] = value
        self.cleanup()

    def get(self, key):
        et = self.__expire_times[key]
        if et < time.time():
            self.cleanup()
            raise KeyError(key)
        return self.__values[key]

    def delete(self, key):
        et = self.__expire_times.pop(key)
        pos = self.__expire_heap.index((et, key))
        del self.__expire_heap[pos]
        if pos < len(self.__expire_heap):
            heapq._siftup(self.__expire_heap, pos)
        del self.__values[key]

    def cleanup(self):
        t = int(time.time())
        eh = self.__expire_heap
        ets = self.__expire_times
        v = self.__values
        size = self.__maxsize
        heappop = heapq.heappop
        #Delete expired, ticky
        while eh and eh[0][0] <= t or len(v) > size:
            _, key = heappop(eh)
            del v[key], ets[key]


def dnslib_resolve_over_udp(query, dnsservers, timeout, **kwargs):
    """
    http://gfwrev.blogspot.com/2009/11/gfwdns.html
    http://zh.wikipedia.org/wiki/%E5%9F%9F%E5%90%8D%E6%9C%8D%E5%8A%A1%E5%99%A8%E7%BC%93%E5%AD%98%E6%B1%A1%E6%9F%93
    http://support.microsoft.com/kb/241352
    """
    if not isinstance(query, (basestring, dnslib.DNSRecord)):
        raise TypeError('query argument requires string/DNSRecord')
    if isinstance(query, basestring):
        query = dnslib.DNSRecord(q=dnslib.DNSQuestion(query))
    blacklist = kwargs.get('blacklist', ())
    turstservers = kwargs.get('turstservers', ())
    query_data = query.pack()
    dns_v4_servers = [x for x in dnsservers if ':' not in x]
    dns_v6_servers = [x for x in dnsservers if ':' in x]
    sock_v4 = sock_v6 = None
    socks = []
    if dns_v4_servers:
        sock_v4 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        socks.append(sock_v4)
    if dns_v6_servers:
        sock_v6 = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        socks.append(sock_v6)
    timeout_at = time.time() + timeout
    try:
        for _ in xrange(4):
            try:
                for dnsserver in dns_v4_servers:
                    sock_v4.sendto(query_data, parse_hostport(dnsserver, 53))
                for dnsserver in dns_v6_servers:
                    sock_v6.sendto(query_data, parse_hostport(dnsserver, 53))
                while time.time() < timeout_at:
                    ins, _, _ = select.select(socks, [], [], 0.1)
                    for sock in ins:
                        reply_data, (reply_server, _) = sock.recvfrom(512)
                        record = dnslib.DNSRecord.parse(reply_data)
                        iplist = [str(x.rdata) for x in record.rr if x.rtype in (1, 28, 255)]
                        if any(x in blacklist for x in iplist):
                            logging.warning('query=%r dnsservers=%r record bad iplist=%r', query, dnsservers, iplist)
                        elif record.header.rcode and not iplist and reply_server in turstservers:
                            logging.info('query=%r trust reply_server=%r record rcode=%s', query, reply_server, record.header.rcode)
                            return record
                        elif iplist:
                            logging.debug('query=%r reply_server=%r record iplist=%s', query, reply_server, iplist)
                            return record
                        else:
                            logging.debug('query=%r reply_server=%r record null iplist=%s', query, reply_server, iplist)
                            continue
            except socket.error as e:
                logging.warning('handle dns query=%s socket: %r', query, e)
        raise socket.gaierror(11004, 'getaddrinfo %r from %r failed' % (query, dnsservers))
    finally:
        for sock in socks:
            sock.close()


def dnslib_resolve_over_tcp(query, dnsservers, timeout, **kwargs):
    """dns query over tcp"""
    if not isinstance(query, (basestring, dnslib.DNSRecord)):
        raise TypeError('query argument requires string/DNSRecord')
    if isinstance(query, basestring):
        query = dnslib.DNSRecord(q=dnslib.DNSQuestion(query))
    blacklist = kwargs.get('blacklist', ())
    def do_resolve(query, dnsserver, timeout, queobj):
        query_data = query.pack()
        sock_family = socket.AF_INET6 if ':' in dnsserver else socket.AF_INET
        sock = socket.socket(sock_family)
        rfile = None
        try:
            sock.settimeout(timeout or None)
            sock.connect(parse_hostport(dnsserver, 53))
            sock.send(struct.pack('>h', len(query_data)) + query_data)
            rfile = sock.makefile('r', 1024)
            reply_data_length = rfile.read(2)
            if len(reply_data_length) < 2:
                raise socket.gaierror(11004, 'getaddrinfo %r from %r failed' % (query, dnsserver))
            reply_data = rfile.read(struct.unpack('>h', reply_data_length)[0])
            record = dnslib.DNSRecord.parse(reply_data)
            iplist = [str(x.rdata) for x in record.rr if x.rtype in (1, 28, 255)]
            if any(x in blacklist for x in iplist):
                logging.debug('query=%r dnsserver=%r record bad iplist=%r', query, dnsserver, iplist)
                raise socket.gaierror(11004, 'getaddrinfo %r from %r failed' % (query, dnsserver))
            else:
                logging.debug('query=%r dnsserver=%r record iplist=%s', query, dnsserver, iplist)
                queobj.put(record)
        except socket.error as e:
            logging.debug('query=%r dnsserver=%r failed %r', query, dnsserver, e)
            queobj.put(e)
        finally:
            if rfile:
                rfile.close()
            sock.close()
    queobj = Queue.Queue()
    for dnsserver in dnsservers:
        thread.start_new_thread(do_resolve, (query, dnsserver, timeout, queobj))
    for i in range(len(dnsservers)):
        try:
            result = queobj.get(timeout)
        except Queue.Empty:
            raise socket.gaierror(11004, 'getaddrinfo %r from %r failed' % (query, dnsservers))
        if result and not isinstance(result, Exception):
            return result
        elif i == len(dnsservers) - 1:
            logging.warning('dnslib_resolve_over_tcp %r with %s return %r', query, dnsservers, result)
    raise socket.gaierror(11004, 'getaddrinfo %r from %r failed' % (query, dnsservers))


class DNSServer(gevent.server.DatagramServer):
    """DNS Proxy based on gevent/dnslib"""

    def __init__(self, *args, **kwargs):
        dns_blacklist = kwargs.pop('dns_blacklist')
        dns_servers = kwargs.pop('dns_servers')
        dns_tcpover = kwargs.pop('dns_tcpover', [])
        dns_timeout = kwargs.pop('dns_timeout', 2)
        super(self.__class__, self).__init__(*args, **kwargs)
        self.dns_servers = list(dns_servers)
        self.dns_tcpover = tuple(dns_tcpover)
        self.dns_intranet_servers = [x for x in self.dns_servers if is_local_addr(x)]
        self.dns_blacklist = set(dns_blacklist)
        self.dns_timeout = int(dns_timeout)
        self.dns_cache = ExpireCache(max_size=65536)
        self.dns_trust_servers = set(['8.8.8.8', '8.8.4.4', '2001:4860:4860::8888', '2001:4860:4860::8844'])
        if pygeoip:
            for dirname in ('.', '/usr/share/GeoIP/', '/usr/local/share/GeoIP/'):
                filename = os.path.join(dirname, 'GeoIP.dat')
                if os.path.isfile(filename):
                    geoip = pygeoip.GeoIP(filename)
                    for dnsserver in self.dns_servers:
                        if ':' not in dnsserver and geoip.country_name_by_addr(parse_hostport(dnsserver, 53)[0]) not in ('China',):
                            self.dns_trust_servers.add(dnsserver)
                    break

    def do_read(self):
        try:
            return gevent.server.DatagramServer.do_read(self)
        except socket.error as e:
            if e[0] not in (errno.ECONNABORTED, errno.ECONNRESET, errno.EPIPE):
                raise

    def get_reply_record(self, data):
        request = dnslib.DNSRecord.parse(data)
        qname = str(request.q.qname).lower()
        qtype = request.q.qtype
        dnsservers = self.dns_servers
        if qname.endswith('.in-addr.arpa'):
            ipaddr = '.'.join(reversed(qname[:-13].split('.')))
            record = dnslib.DNSRecord(header=dnslib.DNSHeader(id=request.header.id, qr=1,aa=1,ra=1), a=dnslib.RR(qname, rdata=dnslib.A(ipaddr)))
            return record
        if 'USERDNSDOMAIN' in os.environ:
            user_dnsdomain = '.' + os.environ['USERDNSDOMAIN'].lower()
            if qname.endswith(user_dnsdomain):
                qname = qname[:-len(user_dnsdomain)]
                if '.' not in qname:
                    if not self.dns_intranet_servers:
                        logging.warning('qname=%r is a plain hostname, need intranet dns server!!!', qname)
                        return dnslib.DNSRecord(header=dnslib.DNSHeader(id=request.header.id, rcode=3))
                    qname += user_dnsdomain
                    dnsservers = self.dns_intranet_servers
        try:
            return self.dns_cache.get((qname, qtype))
        except KeyError:
            pass
        try:
            dns_resolve = dnslib_resolve_over_tcp if qname.endswith(self.dns_tcpover) else dnslib_resolve_over_udp
            kwargs = {'blacklist': self.dns_blacklist, 'turstservers': self.dns_trust_servers}
            record = dns_resolve(request, dnsservers, self.dns_timeout, **kwargs)
            ttl = max(x.ttl for x in record.rr) if record.rr else 600
            self.dns_cache.set((qname, qtype), record, ttl * 2)
            return record
        except socket.gaierror as e:
            logging.warning('resolve %r failed: %r', qname, e)
            return dnslib.DNSRecord(header=dnslib.DNSHeader(id=request.header.id, rcode=3))

    def handle(self, data, address):
        logging.debug('receive from %r data=%r', address, data)
        record = self.get_reply_record(data)
        return self.sendto(data[:2] + record.pack()[2:], address)


def test():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(asctime)s %(message)s', datefmt='[%b %d %H:%M:%S]')
    dns_servers = ['114.114.114.114', '114.114.115.115', '8.8.8.8', '8.8.4.4']
    dns_blacklist = '1.1.1.1|255.255.255.255|74.125.127.102|74.125.155.102|74.125.39.102|74.125.39.113|209.85.229.138|4.36.66.178|8.7.198.45|37.61.54.158|46.82.174.68|59.24.3.173|64.33.88.161|64.33.99.47|64.66.163.251|65.104.202.252|65.160.219.113|66.45.252.237|72.14.205.104|72.14.205.99|78.16.49.15|93.46.8.89|128.121.126.139|159.106.121.75|169.132.13.103|192.67.198.6|202.106.1.2|202.181.7.85|203.161.230.171|203.98.7.65|207.12.88.98|208.56.31.43|209.145.54.50|209.220.30.174|209.36.73.33|209.85.229.138|211.94.66.147|213.169.251.35|216.221.188.182|216.234.179.13|243.185.187.3|243.185.187.39'.split('|')
    dns_tcpover = ['.youtube.com', '.googlevideo.com']
    logging.info('serving at port 53...')
    DNSServer(('', 53), dns_servers=dns_servers, dns_blacklist=dns_blacklist, dns_tcpover=dns_tcpover).serve_forever()


if __name__ == '__main__':
    test()

########NEW FILE########
__FILENAME__ = goagent-gtk
#!/usr/bin/env python2
# coding:utf-8
# Contributor:
#      Phus Lu        <phus.lu@gmail.com>

__version__ = '1.6'

GOAGENT_LOGO_DATA = """\
iVBORw0KGgoAAAANSUhEUgAAADcAAAA3CAYAAACo29JGAAAABHNCSVQICAgIfAhkiAAADVdJREFU
aIHtmnuMXPV1xz/ndx8z4/UT8bKTEscOBa1FAt2kSYvAECxegTZRu6uGJDQJld0ofShNpJZSOlnU
KFWhSUorWlMpoaIq6q4gECANwcQ4SkkpXqVJ8DQpsBGPUgUoxsa787j39/v2j3tndmcfthmbVK1y
tL+9sztz7/19f9/zO+d7zh34qf3fNHtdrlqvu5H/2hA19687zPX3AVBbt0FT65/3jI+H12Uux8Xq
dTc8OpGCBluwrfV4ZPvO5HhO6fgwNzoRMTnmASS4+PqJNzfb+WmJ403tzK+vpNFJyvMhb7hYlmM6
1OrkL9TS6PlOlj1z8prq03eNf/A5ALbWY/aM58djWscOrl53jI+HS+p3bJxp2TVZnm9DbDbnTsLF
5Q1UDKk4R8VrKYDPEOGlyKJHh5Jw84M3XvN1qDs4djc9RnCjEUz6i/5o8oqZjC8KTjIXQQj41qEM
4TEcBBXgoHecAxphxC5KMEQcsj//1l/u+NTxYDAa/NS6g1u0rT5x2qFWeDB4naA885Hy78SEx4O0
0SJXQYoMi/sH84cDBbzPgnzHKkPnb3zHpTwz8andbN0a8/TTAzPoBj1xeHRLDKjV0XuxeLWZQpK4
L178ng3v+taNV10yVIkvM3hVZl4oFHQFei6KetcycBgpUMlbM+2O17WXX3vrz7JnT069PvAcBz6x
sW2/igvY6RbFWNDsyWvX3DT+6Yd5y2///erdf3rVNyLHw3FSjSSyYgccZhdIMnAEmYsr6cFmuAJg
uEE86BwHPnF41zprAFnQSiwYjrjTbK5jz3j+5B5eBTBsrUKQ2VHsbWHlj8yMyKI3AjSmN+hIpy5n
A4MrczAKISGGEKzycqvz+W3XT+xYtXrtj//7pZd+s5WF84JvB4elXTeUNC+CzsNswgyTEIaBHMDw
pl3WmPoJg2vUCrc0cy3MdcA3FdwvHDzUeeTVmRcOAafifbsgLVgRHi0ys1hBMqyfTRlYCVgQyvcb
0+sGZm7gPTcyMgJA8GG1JdUUF6+RS7C4spKkeqpwWFKpuKRSsbiSWlKt4FwsFQz1UkHXrPtLhoHr
vT0y6BSPjrmR7TuT5vp11nh4X2APARo29ewjDuoujuwxF9prIXQkpUYIeCQLkXkvmYQUAZ0QwhlE
8Wb53JtZfxrqkiYTAjkTwK9f8Uh02+/Tnw62DEe8cFKwC/ccNg8efqMXsqobvxnYP+rAOGz95O1/
mEWVz/jmwVlgRVep9NSLgaR2nNYqKe2b93xhx++WWnUpmtEEkY3hl7vt8syVelH1uruAs3856/jL
zw1sMlMKQAgGJhEihEFAyAjdyRbLIUl2EGefUMfn+ZuV5whVrbdcmj9fJJMZ5LnzqkP7isvvqyTN
lXgLIIfksfN+hEtvt3MeeljCmbFkol8GXN0xOeYvuf4rW8719tc+6DyLUmQeCOUqdxdzQVJ285jo
slHeW8qQzzHMocBcTNH84CkzkKnMo9m7qYYqHSDq6dML8a2P6tHz62bfvGE5BheDKxm7rP7V4Vfy
/KFgdkrIOy1om0nWN/EuoKVe9z4ztwCSIjOL5qLlYua6sMzMOAjIXmE2nIA3D6Hcp6XiWcm4pi76
oY089I/aTWwX0rcHF0fLyX2qT+xLX243bwu4U0JntmlQNagA6bEMg4hutLTFMqzAWLilJLEaMNJi
qFJINKUYVQIxWcjJm5/Rdz80xAWLmesDVxSL42HP49Pvs6T2Dt9ptc2imiQtnMRrtu6u6LqideXY
gnRXFrvmHAVz5T6QhZ40DQgjphVEVZtpP3eJGdLekb5itw/c1A+fF0A7hDGZC+ZccVkLdszgFsbl
+QFlzqPVPYY8tEkwUEwww8J8EVeIAiMQI9S5rADQL2X63XLPeL59594VwYdzlLWdoagAdgTRO4j1
knZ5EKUGlRniQLP6Hc57wynO5auRPPMVTamNkEV0ZODfKcmxY7k9NzoRAUw/98Jmw70xBB8kou6d
X/vMj3a44mhmoEwWW+RbBxrfvvSf2LD5ymhV5JBlyFzf5QU4HFkQ0ia+v21jsVXnMPVejKzb5ACy
OLyFJE0Msjk1vwRrc4GwF+5Kt+pIaklql8cjD0I7iFYus0olSWuV8Al9+uSZTMnv0c6EWYQt0GuF
Axsio+KG6OSbAZga6SmfXiqYWn+vAWQ+bMTSIoLIycwvjczKbW49VG1hqUVpGseukPdlBaBe/6Ss
COani3n9lSg0D9XczCcfuPG3bsv2XnJLsqJzJjPKMBLCgjU2KLNJIJU4pE0ATE/1PtUDN9zYQgNI
zE7tFHnUiv22lFmhPAwTCsIUJ7WKCzOdxFpT7Q5PO2e5ASZJ1lUuoaxkukm9F0qanVCd2vvAjjt0
qr2aTV36V0m18zGaIcNZXNxiUViFUPp2MMO0AYDREcFUPziGi0NklnZLr+X2W5cxGQFFmAtWi9p/
sfuxsz/LN8768dILsti6okQAX2KIj9z2npyLr02q2dnM+gxICCoZ0hLMUbiFAZasAqCxBHO1DUV9
lkmzxRnLF9BFUWleOGLHzMqaXbXrhvffr32/tC3nV24OXmeC7/p+Wd4ECMJCWbBZIBPWISgjqqGw
IVlBGmc5zPgMLIEAZuqWQUuuDlixSqFI4s0lmJvaVbS+Ffx/ylKZOSlIZv0d5G5JAgqRi9zKtP2R
B2/4wP2HvveBLzGUfTi2AJkvllVl1u1TYfNUSZcVn0PHixnaiAhnSemJYrkOtoAIERBOQr7wmJG5
XNcDN7Juv6aA2OKncnmTgnOGLXRNM5lQ2+JqpWqHJnf9yQfvmv3uVV9YeXL+YV7uzAIRBFeU0/0V
Qr8mVX/BauaASvfzy4dp5t4JMpDhzVA8XbA0Qpe5XiqYWr+9aIebf0p5e9awRFjoW/mSOQkXW86L
rdNu0r+c/6ZqNfs4B7IWUMWoIEuQJYVrLTvi3hAxMtfX/TuSCTALGAlNmqTucQCmp3rlz1xiHLcA
8PEt7R8B0xYnVigDp7nyBooepCWRsgONz583xdqTftUNRQ4vw8yhhf2D12hHI4YEhSviSZ1DNHjb
riclbH7p0y+/tu9MxsbGfBzZYxalASNQMt9dTmcIF0nSfjCPxacLc8W2lgh2pKkduxXSzTB5Uieo
fNXMApMsL5y7VknSSQuZQzJM1rcLZJjJQpcg7531enVH1aE8RutGJQlImFWbNLkDgNHD1XO37sig
7h7648sesDx7xCXVVCE0zbne/lav+91XuzAn7ZeYC8wVrq9Fdi45jKKxYC1WRBGK77Wf2/Xv2k28
sN2wmLnRLWZmYc2q6sdQeMWSSq3Qf9aW1IZSNxrtfgQlyIXMdfWWGaAM1KK8zuLB3JDaSw5oE9Sk
Qo2WDhBXr5MwXlwchha3GSbHPKOj0deuu+x751/75cvzKN7pk8pZVpTPKPgKUYK1OyfOITMWS4jy
LZXAFaAaJySWFKd0UwP9KaJ3DIu0Zy+9hAAZz5JFH7W3P/jE0fdQACYnPaMT0Tc/+75vb6/f+64f
+OzSLPNvrSTRCqEgn8VDVTsAFB46n7mFtBXM5aQupmNfo+32QkjBchSsJ4b6lHGgG7rm/Lr0uBBy
yJ/g4Kr77ML7Xiq7X0u295Zv7U2OeUYnolvHr5wF7ipHz7q6EOaDW+gZZZQVOZUoxrt7bPjLfyPt
TMy2Z8vdug42Pj//LGOaIFoOWPfuR7SR7XuT5vrpvs/+weZ/Ta6++qYZNUb/ljXRb3CwXSTxsIQr
FbnPEDPgWkVpICEVzJkyghwuJAS1qLqVtJJbSKev5wVSTqazaFLDjczs8On+qNrpU7e+fdEqf2gv
4Woo3RKWZq77t1nZ6xyCfKjQARR7xwE1B50AWS7EEGmU0CK1LY2OdhNsCwM9Ph74QQi10YXnat7v
0rpkd6tWBYRHBAI5ZhDcLDN6gI7tI4kMrEMgYIViYtXIwJlzcHDD03M9q+KwdCoo/lk6kDkgwgwi
HJF7GVv5bjv765fiTnknefQPRAzhceAKr5pu/i+Aa2wqwcQ51n2cVtbWS+0E6zt2qMWO3O62t935
qPaOrOGttzex2ucI1sEpoNACYEtj4CkODq5ZMmf2b3gVgtmKxsNhw1S3wAyCyNYAMDJ1qFAX+VoM
yORQKJ7dNkcGFuIDU65uV+PZa9Yx88oUqW2k6ZuYaotqt8X1nDAFHB6lv8MMd1O1DYTm51jNBRz0
T2A/8/Oc83cHykkOBPCYZG5XGejJX/tFyO8h4URmshzhsRARFBWyZhG4OZCRGbmeIfgTOSFewcH8
Raz6Xjvr/keO9PztdQVHMT1nRtD3338mlezPCP7KIrR7aOcCsrK3t6ASD0ZQSmywKoL9GUTubnzt
Ojvnnsbhnrv9xMAVAEcjs8mikv/B2Ln4fAz8RYjTWWFpsbMXgMsDNH0T8STO7SIkd9rZX/ln4IhP
TI/Wjlv1JdUdNKwHcvfumFNuPQPLziD3m3DRGyBPkWsS2s/h4qcI+g/uPOcJK79rWbTv0bEy9rqZ
tDXWvuH0qD8PponhVLu3Dv6dmGXsda2bpdGIxr6lvzy3D2CLt7HJY3a/n9r/N/sfrBt2air9qXQA
AAAASUVORK5CYII="""

import sys
import os
import re
import thread
import base64
import platform

try:
    import pygtk
    pygtk.require('2.0')
    import gtk
    gtk.gdk.threads_init()
except Exception:
    sys.exit(os.system(u'gdialog --title "GoAgent GTK" --msgbox "\u8bf7\u5b89\u88c5 python-gtk2" 15 60'.encode(sys.getfilesystemencoding() or sys.getdefaultencoding(), 'replace')))
try:
    import pynotify
    pynotify.init('GoAgent Notify')
except ImportError:
    pynotify = None
try:
    import appindicator
except ImportError:
    appindicator = None
try:
    import vte
except ImportError:
    sys.exit(gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR, gtk.BUTTONS_OK, u'请安装 python-vte').run())


def spawn_later(seconds, target, *args, **kwargs):
    def wrap(*args, **kwargs):
        import time
        time.sleep(seconds)
        return target(*args, **kwargs)
    return thread.start_new_thread(wrap, args, kwargs)


def drop_desktop():
    filename = os.path.abspath(__file__)
    dirname = os.path.dirname(filename)
    DESKTOP_FILE = '''\
#!/usr/bin/env xdg-open
[Desktop Entry]
Type=Application
Name=GoAgent GTK
Comment=GoAgent GTK Launcher
Categories=Network;Proxy;
Exec=/usr/bin/env python "%s"
Icon=%s/goagent-logo.png
Terminal=false
StartupNotify=true
''' % (filename, dirname)
    for dirname in map(os.path.expanduser, ['~/Desktop', u'~/桌面']):
        if os.path.isdir(dirname):
            filename = os.path.join(dirname, 'goagent-gtk.desktop')
            with open(filename, 'w') as fp:
                fp.write(DESKTOP_FILE)
            os.chmod(filename, 0755)


def should_visible():
    import ConfigParser
    ConfigParser.RawConfigParser.OPTCRE = re.compile(r'(?P<option>[^=\s][^=]*)\s*(?P<vi>[=])\s*(?P<value>.*)$')
    config = ConfigParser.ConfigParser()
    config.read(['proxy.ini', 'proxy.user.ini'])
    visible = config.has_option('listen', 'visible') and config.getint('listen', 'visible')
    return visible

#gtk.main_quit = lambda: None
#appindicator = None


class GoAgentGTK:

    command = ['/usr/bin/env', 'python', 'proxy.py']
    message = u'GoAgent已经启动，单击托盘图标可以最小化'
    fail_message = u'GoAgent启动失败，请查看控制台窗口的错误信息。'

    def __init__(self, window, terminal):
        self.window = window
        self.window.set_size_request(652, 447)
        self.window.set_position(gtk.WIN_POS_CENTER)
        self.window.connect('delete-event',self.delete_event)
        self.terminal = terminal

        for cmd in ('python2.7', 'python27', 'python2'):
            if os.system('which %s' % cmd) == 0:
                self.command[1] = cmd
                break

        self.window.add(terminal)
        self.childpid = self.terminal.fork_command(self.command[0], self.command, os.getcwd())
        if self.childpid > 0:
            self.childexited = self.terminal.connect('child-exited', self.on_child_exited)
            self.window.connect('delete-event', lambda w, e: gtk.main_quit())
        else:
            self.childexited = None

        spawn_later(0.5, self.show_startup_notify)

        if should_visible():
            self.window.show_all()

        logo_filename = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'goagent-logo.png')
        if not os.path.isfile(logo_filename):
            with open(logo_filename, 'wb') as fp:
                fp.write(base64.b64decode(GOAGENT_LOGO_DATA))
        self.window.set_icon_from_file(logo_filename)

        if appindicator:
            self.trayicon = appindicator.Indicator('GoAgent', 'indicator-messages', appindicator.CATEGORY_APPLICATION_STATUS)
            self.trayicon.set_status(appindicator.STATUS_ACTIVE)
            self.trayicon.set_attention_icon('indicator-messages-new')
            self.trayicon.set_icon(logo_filename)
            self.trayicon.set_menu(self.make_menu())
        else:
            self.trayicon = gtk.StatusIcon()
            self.trayicon.set_from_file(logo_filename)
            self.trayicon.connect('popup-menu', lambda i, b, t: self.make_menu().popup(None, None, gtk.status_icon_position_menu, b, t, self.trayicon))
            self.trayicon.connect('activate', self.show_hide_toggle)
            self.trayicon.set_tooltip('GoAgent')
            self.trayicon.set_visible(True)

    def make_menu(self):
        menu = gtk.Menu()
        itemlist = [(u'\u663e\u793a', self.on_show),
                    (u'\u9690\u85cf', self.on_hide),
                    (u'\u505c\u6b62', self.on_stop),
                    (u'\u91cd\u65b0\u8f7d\u5165', self.on_reload),
                    (u'\u9000\u51fa', self.on_quit)]
        for text, callback in itemlist:
            item = gtk.MenuItem(text)
            item.connect('activate', callback)
            item.show()
            menu.append(item)
        menu.show()
        return menu

    def show_notify(self, message=None, timeout=None):
        if pynotify and message:
            notification = pynotify.Notification('GoAgent Notify', message)
            notification.set_hint('x', 200)
            notification.set_hint('y', 400)
            if timeout:
                notification.set_timeout(timeout)
            notification.show()

    def show_startup_notify(self):
        if self.check_child_exists():
            self.show_notify(self.message, timeout=3)

    def check_child_exists(self):
        if self.childpid <= 0:
            return False
        cmd = 'ps -p %s' % self.childpid
        lines = os.popen(cmd).read().strip().splitlines()
        if len(lines) < 2:
            return False
        return True

    def on_child_exited(self, term):
        if self.terminal.get_child_exit_status() == 0:
            gtk.main_quit()
        else:
            self.show_notify(self.fail_message)

    def on_show(self, widget, data=None):
        self.window.show_all()
        self.window.present()
        self.terminal.feed('\r')

    def on_hide(self, widget, data=None):
        self.window.hide_all()

    def on_stop(self, widget, data=None):
        if self.childexited:
            self.terminal.disconnect(self.childexited)
        os.system('kill -9 %s' % self.childpid)

    def on_reload(self, widget, data=None):
        if self.childexited:
            self.terminal.disconnect(self.childexited)
        os.system('kill -9 %s' % self.childpid)
        self.on_show(widget, data)
        self.childpid = self.terminal.fork_command(self.command[0], self.command, os.getcwd())
        self.childexited = self.terminal.connect('child-exited', lambda term: gtk.main_quit())

    def show_hide_toggle(self, widget, data= None):
        if self.window.get_property('visible'):
            self.on_hide(widget, data)
        else:
            self.on_show(widget, data)

    def delete_event(self, widget, data=None):
        self.on_hide(widget, data)
        # 默认最小化至托盘
        return True

    def on_quit(self, widget, data=None):
        gtk.main_quit()


def main():
    global __file__
    __file__ = os.path.abspath(__file__)
    if os.path.islink(__file__):
        __file__ = getattr(os, 'readlink', lambda x: x)(__file__)
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    if not os.path.exists('goagent-logo.png'):
        # first run and drop shortcut to desktop
        drop_desktop()

    window = gtk.Window()
    terminal = vte.Terminal()
    GoAgentGTK(window, terminal)
    gtk.main()

if __name__ == '__main__':
    main()

########NEW FILE########
__FILENAME__ = proxy
#!/usr/bin/env python
# coding:utf-8
# Based on GAppProxy 2.0.0 by Du XiaoGang <dugang.2008@gmail.com>
# Based on WallProxy 0.4.0 by Hust Moon <www.ehust@gmail.com>
# Contributor:
#      Phus Lu           <phus.lu@gmail.com>
#      Hewig Xu          <hewigovens@gmail.com>
#      Ayanamist Yang    <ayanamist@gmail.com>
#      V.E.O             <V.E.O@tom.com>
#      Max Lv            <max.c.lv@gmail.com>
#      AlsoTang          <alsotang@gmail.com>
#      Christopher Meng  <i@cicku.me>
#      Yonsm Guo         <YonsmGuo@gmail.com>
#      Parkman           <cseparkman@gmail.com>
#      Ming Bai          <mbbill@gmail.com>
#      Bin Yu            <yubinlove1991@gmail.com>
#      lileixuan         <lileixuan@gmail.com>
#      Cong Ding         <cong@cding.org>
#      Zhang Youfu       <zhangyoufu@gmail.com>
#      Lu Wei            <luwei@barfoo>
#      Harmony Meow      <harmony.meow@gmail.com>
#      logostream        <logostream@gmail.com>
#      Rui Wang          <isnowfy@gmail.com>
#      Wang Wei Qiang    <wwqgtxx@gmail.com>
#      Felix Yan         <felixonmars@gmail.com>
#      Sui Feng          <suifeng.me@qq.com>
#      QXO               <qxodream@gmail.com>
#      Geek An           <geekan@foxmail.com>
#      Poly Rabbit       <mcx_221@foxmail.com>
#      oxnz              <yunxinyi@gmail.com>
#      Shusen Liu        <liushusen.smart@gmail.com>
#      Yad Smood         <y.s.inside@gmail.com>
#      Chen Shuang       <cs0x7f@gmail.com>
#      cnfuyu            <cnfuyu@gmail.com>
#      cuixin            <steven.cuixin@gmail.com>
#      s2marine0         <s2marine0@gmail.com>
#      Toshio Xiang      <snachx@gmail.com>
#      Bo Tian           <dxmtb@163.com>
#      Virgil            <variousvirgil@gmail.com>
#      hub01             <miaojiabumiao@yeah.net>
#      v3aqb             <sgzz.cj@gmail.com>
#      Oling Cat         <olingcat@gmail.com>

__version__ = '3.1.13'

import sys
import os
import glob

reload(sys).setdefaultencoding('UTF-8')
sys.dont_write_bytecode = True
sys.path += glob.glob('%s/*.egg' % os.path.dirname(os.path.abspath(__file__)))

try:
    import gevent
    import gevent.socket
    import gevent.server
    import gevent.queue
    import gevent.monkey
    gevent.monkey.patch_all(subprocess=True)
except ImportError:
    gevent = None
except TypeError:
    gevent.monkey.patch_all()
    sys.stderr.write('\033[31m  Warning: Please update gevent to the latest 1.0 version!\033[0m\n')

import errno
import time
import struct
import collections
import binascii
import zlib
import itertools
import re
import io
import fnmatch
import traceback
import random
import base64
import string
import hashlib
import threading
import thread
import socket
import ssl
import select
import Queue
import SocketServer
import ConfigParser
import BaseHTTPServer
import httplib
import urllib
import urllib2
import urlparse
try:
    import dnslib
except ImportError:
    dnslib = None
try:
    import OpenSSL
except ImportError:
    OpenSSL = None
try:
    import pygeoip
except ImportError:
    pygeoip = None


HAS_PYPY = hasattr(sys, 'pypy_version_info')
NetWorkIOError = (socket.error, ssl.SSLError, OSError) if not OpenSSL else (socket.error, ssl.SSLError, OpenSSL.SSL.Error, OSError)


class Logging(type(sys)):
    CRITICAL = 50
    FATAL = CRITICAL
    ERROR = 40
    WARNING = 30
    WARN = WARNING
    INFO = 20
    DEBUG = 10
    NOTSET = 0

    def __init__(self, *args, **kwargs):
        self.level = self.__class__.INFO
        self.__set_error_color = lambda: None
        self.__set_warning_color = lambda: None
        self.__set_debug_color = lambda: None
        self.__reset_color = lambda: None
        if hasattr(sys.stderr, 'isatty') and sys.stderr.isatty():
            if os.name == 'nt':
                import ctypes
                SetConsoleTextAttribute = ctypes.windll.kernel32.SetConsoleTextAttribute
                GetStdHandle = ctypes.windll.kernel32.GetStdHandle
                self.__set_error_color = lambda: SetConsoleTextAttribute(GetStdHandle(-11), 0x04)
                self.__set_warning_color = lambda: SetConsoleTextAttribute(GetStdHandle(-11), 0x06)
                self.__set_debug_color = lambda: SetConsoleTextAttribute(GetStdHandle(-11), 0x002)
                self.__reset_color = lambda: SetConsoleTextAttribute(GetStdHandle(-11), 0x07)
            elif os.name == 'posix':
                self.__set_error_color = lambda: sys.stderr.write('\033[31m')
                self.__set_warning_color = lambda: sys.stderr.write('\033[33m')
                self.__set_debug_color = lambda: sys.stderr.write('\033[32m')
                self.__reset_color = lambda: sys.stderr.write('\033[0m')

    @classmethod
    def getLogger(cls, *args, **kwargs):
        return cls(*args, **kwargs)

    def basicConfig(self, *args, **kwargs):
        self.level = int(kwargs.get('level', self.__class__.INFO))
        if self.level > self.__class__.DEBUG:
            self.debug = self.dummy

    def log(self, level, fmt, *args, **kwargs):
        sys.stderr.write('%s - [%s] %s\n' % (level, time.ctime()[4:-5], fmt % args))

    def dummy(self, *args, **kwargs):
        pass

    def debug(self, fmt, *args, **kwargs):
        self.__set_debug_color()
        self.log('DEBUG', fmt, *args, **kwargs)
        self.__reset_color()

    def info(self, fmt, *args, **kwargs):
        self.log('INFO', fmt, *args)

    def warning(self, fmt, *args, **kwargs):
        self.__set_warning_color()
        self.log('WARNING', fmt, *args, **kwargs)
        self.__reset_color()

    def warn(self, fmt, *args, **kwargs):
        self.warning(fmt, *args, **kwargs)

    def error(self, fmt, *args, **kwargs):
        self.__set_error_color()
        self.log('ERROR', fmt, *args, **kwargs)
        self.__reset_color()

    def exception(self, fmt, *args, **kwargs):
        self.error(fmt, *args, **kwargs)
        sys.stderr.write(traceback.format_exc() + '\n')

    def critical(self, fmt, *args, **kwargs):
        self.__set_error_color()
        self.log('CRITICAL', fmt, *args, **kwargs)
        self.__reset_color()
logging = sys.modules['logging'] = Logging('logging')


class LRUCache(object):
    """http://pypi.python.org/pypi/lru/"""

    def __init__(self, max_items=100):
        self.cache = {}
        self.key_order = []
        self.max_items = max_items

    def __setitem__(self, key, value):
        self.cache[key] = value
        self._mark(key)

    def __getitem__(self, key):
        value = self.cache[key]
        self._mark(key)
        return value

    def __contains__(self, key):
        return key in self.cache

    def _mark(self, key):
        if key in self.key_order:
            self.key_order.remove(key)
        self.key_order.insert(0, key)
        if len(self.key_order) > self.max_items:
            index = self.max_items // 2
            delitem = self.cache.__delitem__
            key_order = self.key_order
            any(delitem(key_order[x]) for x in xrange(index, len(key_order)))
            self.key_order = self.key_order[:index]

    def clear(self):
        self.cache = {}
        self.key_order = []


class CertUtil(object):
    """CertUtil module, based on mitmproxy"""

    ca_vendor = 'GoAgent'
    ca_keyfile = 'CA.crt'
    ca_certdir = 'certs'
    ca_lock = threading.Lock()

    @staticmethod
    def create_ca():
        key = OpenSSL.crypto.PKey()
        key.generate_key(OpenSSL.crypto.TYPE_RSA, 2048)
        ca = OpenSSL.crypto.X509()
        ca.set_serial_number(0)
        ca.set_version(2)
        subj = ca.get_subject()
        subj.countryName = 'CN'
        subj.stateOrProvinceName = 'Internet'
        subj.localityName = 'Cernet'
        subj.organizationName = CertUtil.ca_vendor
        subj.organizationalUnitName = '%s Root' % CertUtil.ca_vendor
        subj.commonName = '%s CA' % CertUtil.ca_vendor
        ca.gmtime_adj_notBefore(0)
        ca.gmtime_adj_notAfter(24 * 60 * 60 * 3652)
        ca.set_issuer(ca.get_subject())
        ca.set_pubkey(key)
        ca.add_extensions([
            OpenSSL.crypto.X509Extension(b'basicConstraints', True, b'CA:TRUE'),
            OpenSSL.crypto.X509Extension(b'nsCertType', True, b'sslCA'),
            OpenSSL.crypto.X509Extension(b'extendedKeyUsage', True, b'serverAuth,clientAuth,emailProtection,timeStamping,msCodeInd,msCodeCom,msCTLSign,msSGC,msEFS,nsSGC'),
            OpenSSL.crypto.X509Extension(b'keyUsage', False, b'keyCertSign, cRLSign'),
            OpenSSL.crypto.X509Extension(b'subjectKeyIdentifier', False, b'hash', subject=ca), ])
        ca.sign(key, 'sha1')
        return key, ca

    @staticmethod
    def dump_ca():
        key, ca = CertUtil.create_ca()
        with open(CertUtil.ca_keyfile, 'wb') as fp:
            fp.write(OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_PEM, ca))
            fp.write(OpenSSL.crypto.dump_privatekey(OpenSSL.crypto.FILETYPE_PEM, key))

    @staticmethod
    def _get_cert(commonname, sans=()):
        with open(CertUtil.ca_keyfile, 'rb') as fp:
            content = fp.read()
            key = OpenSSL.crypto.load_privatekey(OpenSSL.crypto.FILETYPE_PEM, content)
            ca = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, content)

        pkey = OpenSSL.crypto.PKey()
        pkey.generate_key(OpenSSL.crypto.TYPE_RSA, 2048)

        req = OpenSSL.crypto.X509Req()
        subj = req.get_subject()
        subj.countryName = 'CN'
        subj.stateOrProvinceName = 'Internet'
        subj.localityName = 'Cernet'
        subj.organizationalUnitName = '%s Branch' % CertUtil.ca_vendor
        if commonname[0] == '.':
            subj.commonName = '*' + commonname
            subj.organizationName = '*' + commonname
            sans = ['*'+commonname] + [x for x in sans if x != '*'+commonname]
        else:
            subj.commonName = commonname
            subj.organizationName = commonname
            sans = [commonname] + [x for x in sans if x != commonname]
        #req.add_extensions([OpenSSL.crypto.X509Extension(b'subjectAltName', True, ', '.join('DNS: %s' % x for x in sans)).encode()])
        req.set_pubkey(pkey)
        req.sign(pkey, 'sha1')

        cert = OpenSSL.crypto.X509()
        cert.set_version(2)
        try:
            cert.set_serial_number(int(hashlib.md5(commonname.encode('utf-8')).hexdigest(), 16))
        except OpenSSL.SSL.Error:
            cert.set_serial_number(int(time.time()*1000))
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(60 * 60 * 24 * 3652)
        cert.set_issuer(ca.get_subject())
        cert.set_subject(req.get_subject())
        cert.set_pubkey(req.get_pubkey())
        if commonname[0] == '.':
            sans = ['*'+commonname] + [s for s in sans if s != '*'+commonname]
        else:
            sans = [commonname] + [s for s in sans if s != commonname]
        #cert.add_extensions([OpenSSL.crypto.X509Extension(b'subjectAltName', True, ', '.join('DNS: %s' % x for x in sans))])
        cert.sign(key, 'sha1')

        certfile = os.path.join(CertUtil.ca_certdir, commonname + '.crt')
        with open(certfile, 'wb') as fp:
            fp.write(OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_PEM, cert))
            fp.write(OpenSSL.crypto.dump_privatekey(OpenSSL.crypto.FILETYPE_PEM, pkey))
        return certfile

    @staticmethod
    def get_cert(commonname, sans=()):
        if commonname.count('.') >= 2 and [len(x) for x in reversed(commonname.split('.'))] > [2, 4]:
            commonname = '.'+commonname.partition('.')[-1]
        certfile = os.path.join(CertUtil.ca_certdir, commonname + '.crt')
        if os.path.exists(certfile):
            return certfile
        elif OpenSSL is None:
            return CertUtil.ca_keyfile
        else:
            with CertUtil.ca_lock:
                if os.path.exists(certfile):
                    return certfile
                return CertUtil._get_cert(commonname, sans)

    @staticmethod
    def import_ca(certfile):
        commonname = os.path.splitext(os.path.basename(certfile))[0]
        sha1digest = 'AB:70:2C:DF:18:EB:E8:B4:38:C5:28:69:CD:4A:5D:EF:48:B4:0E:33'
        if OpenSSL:
            try:
                with open(certfile, 'rb') as fp:
                    x509 = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, fp.read())
                    commonname = next(v.decode() for k, v in x509.get_subject().get_components() if k == b'O')
                    sha1digest = x509.digest('sha1')
            except StandardError as e:
                logging.error('load_certificate(certfile=%r) failed:%s', certfile, e)
        if sys.platform.startswith('win'):
            import ctypes
            with open(certfile, 'rb') as fp:
                certdata = fp.read()
                if certdata.startswith(b'-----'):
                    begin = b'-----BEGIN CERTIFICATE-----'
                    end = b'-----END CERTIFICATE-----'
                    certdata = base64.b64decode(b''.join(certdata[certdata.find(begin)+len(begin):certdata.find(end)].strip().splitlines()))
                crypt32 = ctypes.WinDLL(b'crypt32.dll'.decode())
                store_handle = crypt32.CertOpenStore(10, 0, 0, 0x4000 | 0x20000, b'ROOT'.decode())
                if not store_handle:
                    return -1
                X509_ASN_ENCODING = 0x00000001
                CERT_FIND_HASH = 0x10000
                class CRYPT_HASH_BLOB(ctypes.Structure):
                    _fields_ = [('cbData', ctypes.c_ulong), ('pbData', ctypes.c_char_p)]
                crypt_hash = CRYPT_HASH_BLOB(20, binascii.a2b_hex(sha1digest.replace(':', '')))
                crypt_handle = crypt32.CertFindCertificateInStore(store_handle, X509_ASN_ENCODING, 0, CERT_FIND_HASH, ctypes.byref(crypt_hash), None)
                if crypt_handle:
                    crypt32.CertFreeCertificateContext(crypt_handle)
                    return 0
                ret = crypt32.CertAddEncodedCertificateToStore(store_handle, 0x1, certdata, len(certdata), 4, None)
                crypt32.CertCloseStore(store_handle, 0)
                del crypt32
                return 0 if ret else -1
        elif sys.platform == 'darwin':
            return os.system(('security find-certificate -a -c "%s" | grep "%s" >/dev/null || security add-trusted-cert -d -r trustRoot -k "/Library/Keychains/System.keychain" "%s"' % (commonname, commonname, certfile.decode('utf-8'))).encode('utf-8'))
        elif sys.platform.startswith('linux'):
            import platform
            platform_distname = platform.dist()[0]
            if platform_distname == 'Ubuntu':
                pemfile = "/etc/ssl/certs/%s.pem" % commonname
                new_certfile = "/usr/local/share/ca-certificates/%s.crt" % commonname
                if not os.path.exists(pemfile):
                    return os.system('cp "%s" "%s" && update-ca-certificates' % (certfile, new_certfile))
            elif any(os.path.isfile('%s/certutil' % x) for x in os.environ['PATH'].split(os.pathsep)):
                return os.system('certutil -L -d sql:$HOME/.pki/nssdb | grep "%s" || certutil -d sql:$HOME/.pki/nssdb -A -t "C,," -n "%s" -i "%s"' % (commonname, commonname, certfile))
            else:
                logging.warning('please install *libnss3-tools* package to import GoAgent root ca')
        return 0

    @staticmethod
    def check_ca():
        #Check CA exists
        capath = os.path.join(os.path.dirname(os.path.abspath(__file__)), CertUtil.ca_keyfile)
        certdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), CertUtil.ca_certdir)
        if not os.path.exists(capath):
            if not OpenSSL:
                logging.critical('CA.key is not exist and OpenSSL is disabled, ABORT!')
                sys.exit(-1)
            if os.path.exists(certdir):
                if os.path.isdir(certdir):
                    any(os.remove(x) for x in glob.glob(certdir+'/*.crt')+glob.glob(certdir+'/.*.crt'))
                else:
                    os.remove(certdir)
                    os.mkdir(certdir)
            CertUtil.dump_ca()
        if glob.glob('%s/*.key' % CertUtil.ca_certdir):
            for filename in glob.glob('%s/*.key' % CertUtil.ca_certdir):
                try:
                    os.remove(filename)
                    os.remove(os.path.splitext(filename)[0]+'.crt')
                except EnvironmentError:
                    pass
        #Check CA imported
        if CertUtil.import_ca(capath) != 0:
            logging.warning('install root certificate failed, Please run as administrator/root/sudo')
        #Check Certs Dir
        if not os.path.exists(certdir):
            os.makedirs(certdir)


class DetectMobileBrowser:
    """detect mobile function from http://detectmobilebrowsers.com"""
    regex_match_a  = re.compile(r"(android|bb\\d+|meego).+mobile|avantgo|bada\\/|blackberry|blazer|compal|elaine|fennec|hiptop|iemobile|ip(hone|od)|iris|kindle|lge |maemo|midp|mmp|mobile.+firefox|netfront|opera m(ob|in)i|palm( os)?|phone|p(ixi|re)\\/|plucker|pocket|psp|series(4|6)0|symbian|treo|up\\.(browser|link)|vodafone|wap|windows (ce|phone)|xda|xiino", re.I|re.M).search
    regex_match_b = re.compile(r"1207|6310|6590|3gso|4thp|50[1-6]i|770s|802s|a wa|abac|ac(er|oo|s\\-)|ai(ko|rn)|al(av|ca|co)|amoi|an(ex|ny|yw)|aptu|ar(ch|go)|as(te|us)|attw|au(di|\\-m|r |s )|avan|be(ck|ll|nq)|bi(lb|rd)|bl(ac|az)|br(e|v)w|bumb|bw\\-(n|u)|c55\\/|capi|ccwa|cdm\\-|cell|chtm|cldc|cmd\\-|co(mp|nd)|craw|da(it|ll|ng)|dbte|dc\\-s|devi|dica|dmob|do(c|p)o|ds(12|\\-d)|el(49|ai)|em(l2|ul)|er(ic|k0)|esl8|ez([4-7]0|os|wa|ze)|fetc|fly(\\-|_)|g1 u|g560|gene|gf\\-5|g\\-mo|go(\\.w|od)|gr(ad|un)|haie|hcit|hd\\-(m|p|t)|hei\\-|hi(pt|ta)|hp( i|ip)|hs\\-c|ht(c(\\-| |_|a|g|p|s|t)|tp)|hu(aw|tc)|i\\-(20|go|ma)|i230|iac( |\\-|\\/)|ibro|idea|ig01|ikom|im1k|inno|ipaq|iris|ja(t|v)a|jbro|jemu|jigs|kddi|keji|kgt( |\\/)|klon|kpt |kwc\\-|kyo(c|k)|le(no|xi)|lg( g|\\/(k|l|u)|50|54|\\-[a-w])|libw|lynx|m1\\-w|m3ga|m50\\/|ma(te|ui|xo)|mc(01|21|ca)|m\\-cr|me(rc|ri)|mi(o8|oa|ts)|mmef|mo(01|02|bi|de|do|t(\\-| |o|v)|zz)|mt(50|p1|v )|mwbp|mywa|n10[0-2]|n20[2-3]|n30(0|2)|n50(0|2|5)|n7(0(0|1)|10)|ne((c|m)\\-|on|tf|wf|wg|wt)|nok(6|i)|nzph|o2im|op(ti|wv)|oran|owg1|p800|pan(a|d|t)|pdxg|pg(13|\\-([1-8]|c))|phil|pire|pl(ay|uc)|pn\\-2|po(ck|rt|se)|prox|psio|pt\\-g|qa\\-a|qc(07|12|21|32|60|\\-[2-7]|i\\-)|qtek|r380|r600|raks|rim9|ro(ve|zo)|s55\\/|sa(ge|ma|mm|ms|ny|va)|sc(01|h\\-|oo|p\\-)|sdk\\/|se(c(\\-|0|1)|47|mc|nd|ri)|sgh\\-|shar|sie(\\-|m)|sk\\-0|sl(45|id)|sm(al|ar|b3|it|t5)|so(ft|ny)|sp(01|h\\-|v\\-|v )|sy(01|mb)|t2(18|50)|t6(00|10|18)|ta(gt|lk)|tcl\\-|tdg\\-|tel(i|m)|tim\\-|t\\-mo|to(pl|sh)|ts(70|m\\-|m3|m5)|tx\\-9|up(\\.b|g1|si)|utst|v400|v750|veri|vi(rg|te)|vk(40|5[0-3]|\\-v)|vm40|voda|vulc|vx(52|53|60|61|70|80|81|83|85|98)|w3c(\\-| )|webc|whit|wi(g |nc|nw)|wmlb|wonu|x700|yas\\-|your|zeto|zte\\-", re.I|re.M).search
    
    @staticmethod
    def detect(user_agent):
        return DetectMobileBrowser.regex_match_a(user_agent) or DetectMobileBrowser.regex_match_b(user_agent)


class SSLConnection(object):

    has_gevent = socket.socket is getattr(sys.modules.get('gevent.socket'), 'socket', None)

    def __init__(self, context, sock):
        self._context = context
        self._sock = sock
        self._connection = OpenSSL.SSL.Connection(context, sock)
        self._makefile_refs = 0
        if self.has_gevent:
            self._wait_read = gevent.socket.wait_read
            self._wait_write = gevent.socket.wait_write
            self._wait_readwrite = gevent.socket.wait_readwrite
        else:
            self._wait_read = lambda fd,t: select.select([fd], [], [fd], t)
            self._wait_write = lambda fd,t: select.select([], [fd], [fd], t)
            self._wait_readwrite = lambda fd,t: select.select([fd], [fd], [fd], t)

    def __getattr__(self, attr):
        if attr not in ('_context', '_sock', '_connection', '_makefile_refs'):
            return getattr(self._connection, attr)

    def accept(self):
        sock, addr = self._sock.accept()
        client = OpenSSL.SSL.Connection(sock._context, sock)
        return client, addr

    def do_handshake(self):
        timeout = self._sock.gettimeout()
        while True:
            try:
                self._connection.do_handshake()
                break
            except (OpenSSL.SSL.WantReadError, OpenSSL.SSL.WantX509LookupError, OpenSSL.SSL.WantWriteError):
                sys.exc_clear()
                self._wait_readwrite(self._sock.fileno(), timeout)

    def connect(self, *args, **kwargs):
        timeout = self._sock.gettimeout()
        while True:
            try:
                self._connection.connect(*args, **kwargs)
                break
            except (OpenSSL.SSL.WantReadError, OpenSSL.SSL.WantX509LookupError):
                sys.exc_clear()
                self._wait_read(self._sock.fileno(), timeout)
            except OpenSSL.SSL.WantWriteError:
                sys.exc_clear()
                self._wait_write(self._sock.fileno(), timeout)

    def send(self, data, flags=0):
        timeout = self._sock.gettimeout()
        while True:
            try:
                self._connection.send(data, flags)
                break
            except (OpenSSL.SSL.WantReadError, OpenSSL.SSL.WantX509LookupError):
                sys.exc_clear()
                self._wait_read(self._sock.fileno(), timeout)
            except OpenSSL.SSL.WantWriteError:
                sys.exc_clear()
                self._wait_write(self._sock.fileno(), timeout)
            except OpenSSL.SSL.SysCallError as e:
                if e[0] == -1 and not data:
                    # errors when writing empty strings are expected and can be ignored
                    return 0
                raise

    def recv(self, bufsiz, flags=0):
        timeout = self._sock.gettimeout()
        pending = self._connection.pending()
        if pending:
            return self._connection.recv(min(pending, bufsiz))
        while True:
            try:
                return self._connection.recv(bufsiz, flags)
            except (OpenSSL.SSL.WantReadError, OpenSSL.SSL.WantX509LookupError):
                sys.exc_clear()
                self._wait_read(self._sock.fileno(), timeout)
            except OpenSSL.SSL.WantWriteError:
                sys.exc_clear()
                self._wait_write(self._sock.fileno(), timeout)
            except OpenSSL.SSL.ZeroReturnError:
                return ''

    def read(self, bufsiz, flags=0):
        return self.recv(bufsiz, flags)

    def write(self, buf, flags=0):
        return self.sendall(buf, flags)

    def close(self):
        if self._makefile_refs < 1:
            self._connection = None
            if self._sock:
                socket.socket.close(self._sock)
        else:
            self._makefile_refs -= 1

    def makefile(self, mode='r', bufsize=-1):
        self._makefile_refs += 1
        return socket._fileobject(self, mode, bufsize, close=True)



class ProxyUtil(object):
    """ProxyUtil module, based on urllib2"""

    @staticmethod
    def parse_proxy(proxy):
        return urllib2._parse_proxy(proxy)

    @staticmethod
    def get_system_proxy():
        proxies = urllib2.getproxies()
        return proxies.get('https') or proxies.get('http') or {}

    @staticmethod
    def get_listen_ip():
        listen_ip = '127.0.0.1'
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(('8.8.8.8', 53))
            listen_ip = sock.getsockname()[0]
        except socket.error:
            pass
        finally:
            if sock:
                sock.close()
        return listen_ip


def parse_hostport(host, default_port=80):
    m = re.match(r'(.+)[#](\d+)$', host)
    if m:
        return m.group(1).strip('[]'), int(m.group(2))
    else:
        return host.strip('[]'), default_port


def dnslib_resolve_over_udp(query, dnsservers, timeout, **kwargs):
    """
    http://gfwrev.blogspot.com/2009/11/gfwdns.html
    http://zh.wikipedia.org/wiki/%E5%9F%9F%E5%90%8D%E6%9C%8D%E5%8A%A1%E5%99%A8%E7%BC%93%E5%AD%98%E6%B1%A1%E6%9F%93
    http://support.microsoft.com/kb/241352
    """
    if not isinstance(query, (basestring, dnslib.DNSRecord)):
        raise TypeError('query argument requires string/DNSRecord')
    if isinstance(query, basestring):
        query = dnslib.DNSRecord(q=dnslib.DNSQuestion(query))
    blacklist = kwargs.get('blacklist', ())
    turstservers = kwargs.get('turstservers', ())
    query_data = query.pack()
    dns_v4_servers = [x for x in dnsservers if ':' not in x]
    dns_v6_servers = [x for x in dnsservers if ':' in x]
    sock_v4 = sock_v6 = None
    socks = []
    if dns_v4_servers:
        sock_v4 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        socks.append(sock_v4)
    if dns_v6_servers:
        sock_v6 = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        socks.append(sock_v6)
    timeout_at = time.time() + timeout
    try:
        for _ in xrange(4):
            try:
                for dnsserver in dns_v4_servers:
                    sock_v4.sendto(query_data, parse_hostport(dnsserver, 53))
                for dnsserver in dns_v6_servers:
                    sock_v6.sendto(query_data, parse_hostport(dnsserver, 53))
                while time.time() < timeout_at:
                    ins, _, _ = select.select(socks, [], [], 0.1)
                    for sock in ins:
                        reply_data, (reply_server, _) = sock.recvfrom(512)
                        record = dnslib.DNSRecord.parse(reply_data)
                        iplist = [str(x.rdata) for x in record.rr if x.rtype in (1, 28, 255)]
                        if any(x in blacklist for x in iplist):
                            logging.warning('query=%r dnsservers=%r record bad iplist=%r', query, dnsservers, iplist)
                        elif record.header.rcode and not iplist and reply_server in turstservers:
                            logging.info('query=%r trust reply_server=%r record rcode=%s', query, reply_server, record.header.rcode)
                            return record
                        elif iplist:
                            logging.debug('query=%r reply_server=%r record iplist=%s', query, reply_server, iplist)
                            return record
                        else:
                            logging.debug('query=%r reply_server=%r record null iplist=%s', query, reply_server, iplist)
                            continue
            except socket.error as e:
                logging.warning('handle dns query=%s socket: %r', query, e)
        raise socket.gaierror(11004, 'getaddrinfo %r from %r failed' % (query, dnsservers))
    finally:
        for sock in socks:
            sock.close()


def dnslib_resolve_over_tcp(query, dnsservers, timeout, **kwargs):
    """dns query over tcp"""
    if not isinstance(query, (basestring, dnslib.DNSRecord)):
        raise TypeError('query argument requires string/DNSRecord')
    if isinstance(query, basestring):
        query = dnslib.DNSRecord(q=dnslib.DNSQuestion(query))
    blacklist = kwargs.get('blacklist', ())
    def do_resolve(query, dnsserver, timeout, queobj):
        query_data = query.pack()
        sock_family = socket.AF_INET6 if ':' in dnsserver else socket.AF_INET
        sock = socket.socket(sock_family)
        rfile = None
        try:
            sock.settimeout(timeout or None)
            sock.connect(parse_hostport(dnsserver, 53))
            sock.send(struct.pack('>h', len(query_data)) + query_data)
            rfile = sock.makefile('r', 1024)
            reply_data_length = rfile.read(2)
            if len(reply_data_length) < 2:
                raise socket.gaierror(11004, 'getaddrinfo %r from %r failed' % (query, dnsserver))
            reply_data = rfile.read(struct.unpack('>h', reply_data_length)[0])
            record = dnslib.DNSRecord.parse(reply_data)
            iplist = [str(x.rdata) for x in record.rr if x.rtype in (1, 28, 255)]
            if any(x in blacklist for x in iplist):
                logging.debug('query=%r dnsserver=%r record bad iplist=%r', query, dnsserver, iplist)
                raise socket.gaierror(11004, 'getaddrinfo %r from %r failed' % (query, dnsserver))
            else:
                logging.debug('query=%r dnsserver=%r record iplist=%s', query, dnsserver, iplist)
                queobj.put(record)
        except socket.error as e:
            logging.debug('query=%r dnsserver=%r failed %r', query, dnsserver, e)
            queobj.put(e)
        finally:
            if rfile:
                rfile.close()
            sock.close()
    queobj = Queue.Queue()
    for dnsserver in dnsservers:
        thread.start_new_thread(do_resolve, (query, dnsserver, timeout, queobj))
    for i in range(len(dnsservers)):
        try:
            result = queobj.get(timeout)
        except Queue.Empty:
            raise socket.gaierror(11004, 'getaddrinfo %r from %r failed' % (query, dnsservers))
        if result and not isinstance(result, Exception):
            return result
        elif i == len(dnsservers) - 1:
            logging.warning('dnslib_resolve_over_tcp %r with %s return %r', query, dnsservers, result)
    raise socket.gaierror(11004, 'getaddrinfo %r from %r failed' % (query, dnsservers))


def dnslib_record2iplist(record):
    """convert dnslib.DNSRecord to iplist"""
    assert isinstance(record, dnslib.DNSRecord)
    iplist = [x for x in (str(r.rdata) for r in record.rr) if re.match(r'^\d+\.\d+\.\d+\.\d+$', x) or ':' in x]
    return iplist


def get_dnsserver_list():
    if os.name == 'nt':
        import ctypes, ctypes.wintypes, struct, socket
        DNS_CONFIG_DNS_SERVER_LIST = 6
        buf = ctypes.create_string_buffer(2048)
        ctypes.windll.dnsapi.DnsQueryConfig(DNS_CONFIG_DNS_SERVER_LIST, 0, None, None, ctypes.byref(buf), ctypes.byref(ctypes.wintypes.DWORD(len(buf))))
        ipcount = struct.unpack('I', buf[0:4])[0]
        iplist = [socket.inet_ntoa(buf[i:i+4]) for i in xrange(4, ipcount*4+4, 4)]
        return iplist
    elif os.path.isfile('/etc/resolv.conf'):
        with open('/etc/resolv.conf', 'rb') as fp:
            return re.findall(r'(?m)^nameserver\s+(\S+)', fp.read())
    else:
        logging.warning("get_dnsserver_list failed: unsupport platform '%s-%s'", sys.platform, os.name)
        return []


def spawn_later(seconds, target, *args, **kwargs):
    def wrap(*args, **kwargs):
        __import__('time').sleep(seconds)
        return target(*args, **kwargs)
    return __import__('thread').start_new_thread(wrap, args, kwargs)


def is_clienthello(data):
    if len(data) < 20:
        return False
    if data.startswith('\x16\x03'):
        # TLSv12/TLSv11/TLSv1/SSLv3
        length, = struct.unpack('>h', data[3:5])
        return len(data) == 5 + length
    elif data[0] == '\x80' and data[2:4] == '\x01\x03':
        # SSLv23
        return len(data) == 2 + ord(data[1])
    else:
        return False


def extract_sni_name(packet):
    if packet.startswith('\x16\x03'):
        stream = io.BytesIO(packet)
        stream.read(0x2b)
        session_id_length = ord(stream.read(1))
        stream.read(session_id_length)
        cipher_suites_length, = struct.unpack('>h', stream.read(2))
        stream.read(cipher_suites_length+2)
        extensions_length, = struct.unpack('>h', stream.read(2))
        extensions = {}
        while True:
            data = stream.read(2)
            if not data:
                break
            etype, = struct.unpack('>h', data)
            elen, = struct.unpack('>h', stream.read(2))
            edata = stream.read(elen)
            if etype == 0:
                server_name = edata[5:]
                return server_name


class URLFetch(object):
    """URLFetch for gae/php fetchservers"""
    skip_headers = frozenset(['Vary', 'Via', 'X-Forwarded-For', 'Proxy-Authorization', 'Proxy-Connection', 'Upgrade', 'X-Chrome-Variations', 'Connection', 'Cache-Control'])

    def __init__(self, fetchserver, create_http_request):
        assert isinstance(fetchserver, basestring) and callable(create_http_request)
        self.fetchserver = fetchserver
        self.create_http_request = create_http_request

    def fetch(self, method, url, headers, body, timeout, **kwargs):
        if '.appspot.com/' in self.fetchserver:
            response = self.__gae_fetch(method, url, headers, body, timeout, **kwargs)
            response.app_header_parsed = True
        else:
            response = self.__php_fetch(method, url, headers, body, timeout, **kwargs)
            response.app_header_parsed = False
        return response

    def __gae_fetch(self, method, url, headers, body, timeout, **kwargs):
        # deflate = lambda x:zlib.compress(x)[2:-4]
        rc4crypt = lambda s, k: RC4Cipher(k).encrypt(s) if k else s
        if body:
            if len(body) < 10 * 1024 * 1024 and 'Content-Encoding' not in headers:
                zbody = zlib.compress(body)[2:-4]
                if len(zbody) < len(body):
                    body = zbody
                    headers['Content-Encoding'] = 'deflate'
            headers['Content-Length'] = str(len(body))
        # GAE donot allow set `Host` header
        if 'Host' in headers:
            del headers['Host']
        metadata = 'G-Method:%s\nG-Url:%s\n%s' % (method, url, ''.join('G-%s:%s\n' % (k, v) for k, v in kwargs.items() if v))
        skip_headers = self.skip_headers
        metadata += ''.join('%s:%s\n' % (k.title(), v) for k, v in headers.items() if k not in skip_headers)
        # prepare GAE request
        request_method = 'POST'
        request_headers = {}
        if common.GAE_OBFUSCATE:
            if 'rc4' in common.GAE_OPTIONS:
                request_headers['X-GOA-Options'] = 'rc4'
                cookie = base64.b64encode(rc4crypt(zlib.compress(metadata)[2:-4], kwargs.get('password'))).strip()
                body = rc4crypt(body, kwargs.get('password'))
            else:
                cookie = base64.b64encode(zlib.compress(metadata)[2:-4]).strip()
            request_headers['Cookie'] = cookie
            if body:
                request_headers['Content-Length'] = str(len(body))
            else:
                request_method = 'GET'
        else:
            metadata = zlib.compress(metadata)[2:-4]
            body = '%s%s%s' % (struct.pack('!h', len(metadata)), metadata, body)
            if 'rc4' in common.GAE_OPTIONS:
                request_headers['X-GOA-Options'] = 'rc4'
                body = rc4crypt(body, kwargs.get('password'))
            request_headers['Content-Length'] = str(len(body))
        # post data
        need_crlf = 0 if common.GAE_MODE == 'https' else 1
        need_validate = common.GAE_VALIDATE
        cache_key = '%s:%d' % (common.HOST_POSTFIX_MAP['.appspot.com'], 443 if common.GAE_MODE == 'https' else 80)
        response = self.create_http_request(request_method, self.fetchserver, request_headers, body, timeout, crlf=need_crlf, validate=need_validate, cache_key=cache_key)
        response.app_status = response.status
        response.app_options = response.getheader('X-GOA-Options', '')
        if response.status != 200:
            return response
        data = response.read(4)
        if len(data) < 4:
            response.status = 502
            response.fp = io.BytesIO(b'connection aborted. too short leadbyte data=' + data)
            response.read = response.fp.read
            return response
        response.status, headers_length = struct.unpack('!hh', data)
        data = response.read(headers_length)
        if len(data) < headers_length:
            response.status = 502
            response.fp = io.BytesIO(b'connection aborted. too short headers data=' + data)
            response.read = response.fp.read
            return response
        if 'rc4' not in response.app_options:
            response.msg = httplib.HTTPMessage(io.BytesIO(zlib.decompress(data, -zlib.MAX_WBITS)))
        else:
            response.msg = httplib.HTTPMessage(io.BytesIO(zlib.decompress(rc4crypt(data, kwargs.get('password')), -zlib.MAX_WBITS)))
            if kwargs.get('password') and response.fp:
                response.fp = CipherFileObject(response.fp, RC4Cipher(kwargs['password']))
        return response

    def __php_fetch(self, method, url, headers, body, timeout, **kwargs):
        if body:
            if len(body) < 10 * 1024 * 1024 and 'Content-Encoding' not in headers:
                zbody = zlib.compress(body)[2:-4]
                if len(zbody) < len(body):
                    body = zbody
                    headers['Content-Encoding'] = 'deflate'
            headers['Content-Length'] = str(len(body))
        skip_headers = self.skip_headers
        metadata = 'G-Method:%s\nG-Url:%s\n%s%s' % (method, url, ''.join('G-%s:%s\n' % (k, v) for k, v in kwargs.items() if v), ''.join('%s:%s\n' % (k, v) for k, v in headers.items() if k not in skip_headers))
        metadata = zlib.compress(metadata)[2:-4]
        app_body = b''.join((struct.pack('!h', len(metadata)), metadata, body))
        app_headers = {'Content-Length': len(app_body), 'Content-Type': 'application/octet-stream'}
        fetchserver = '%s?%s' % (self.fetchserver, random.random())
        crlf = 0
        cache_key = '%s//:%s' % urlparse.urlsplit(fetchserver)[:2]
        response = self.create_http_request('POST', fetchserver, app_headers, app_body, timeout, crlf=crlf, cache_key=cache_key)
        if not response:
            raise socket.error(errno.ECONNRESET, 'urlfetch %r return None' % url)
        if response.status >= 400:
            return response
        response.app_status = response.status
        need_decrypt = kwargs.get('password') and response.app_status == 200 and response.getheader('Content-Type', '') == 'image/gif' and response.fp
        if need_decrypt:
            response.fp = CipherFileObject(response.fp, XORCipher(kwargs['password'][0]))
        return response


class BaseProxyHandlerFilter(object):
    """base proxy handler filter"""
    def filter(self, handler):
        raise NotImplementedError


class SimpleProxyHandlerFilter(BaseProxyHandlerFilter):
    """simple proxy handler filter"""
    def filter(self, handler):
        if handler.command == 'CONNECT':
            return [handler.FORWARD, handler.host, handler.port, handler.connect_timeout]
        else:
            return [handler.DIRECT, {}]


class AuthFilter(BaseProxyHandlerFilter):
    """authorization filter"""
    auth_info = "Proxy authentication required"""
    white_list = set(['127.0.0.1'])

    def __init__(self, username, password):
        self.username = username
        self.password = password

    def check_auth_header(self, auth_header):
        method, _, auth_data = auth_header.partition(' ')
        if method == 'Basic':
            username, _, password = base64.b64decode(auth_data).partition(':')
            if username == self.username and password == self.password:
                return True
        return False

    def filter(self, handler):
        if self.white_list and handler.client_address[0] in self.white_list:
            return None
        auth_header = handler.headers.get('Proxy-Authorization') or getattr(handler, 'auth_header', None)
        if auth_header and self.check_auth_header(auth_header):
            handler.auth_header = auth_header
        else:
            headers = {'Access-Control-Allow-Origin': '*',
                       'Proxy-Authenticate': 'Basic realm="%s"' % self.auth_info,
                       'Content-Length': '0',
                       'Connection': 'keep-alive'}
            return [handler.MOCK, 407, headers, '']


class SimpleProxyHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    """SimpleProxyHandler for GoAgent 3.x"""

    protocol_version = 'HTTP/1.1'
    ssl_version = ssl.PROTOCOL_SSLv23
    disable_transport_ssl = True
    scheme = 'http'
    skip_headers = frozenset(['Vary', 'Via', 'X-Forwarded-For', 'Proxy-Authorization', 'Proxy-Connection', 'Upgrade', 'X-Chrome-Variations', 'Connection', 'Cache-Control'])
    bufsize = 256 * 1024
    max_timeout = 16
    connect_timeout = 4
    first_run_lock = threading.Lock()
    handler_filters = [SimpleProxyHandlerFilter()]
    sticky_filter = None

    def finish(self):
        """make python2 BaseHTTPRequestHandler happy"""
        try:
            BaseHTTPServer.BaseHTTPRequestHandler.finish(self)
        except NetWorkIOError as e:
            if e[0] not in (errno.ECONNABORTED, errno.ECONNRESET, errno.EPIPE):
                raise

    def address_string(self):
        return '%s:%s' % self.client_address[:2]

    def send_response(self, code, message=None):
        if message is None:
            if code in self.responses:
                message = self.responses[code][0]
            else:
                message = ''
        if self.request_version != 'HTTP/0.9':
            self.wfile.write('%s %d %s\r\n' % (self.protocol_version, code, message))

    def send_header(self, keyword, value):
        """Send a MIME header."""
        base_send_header = BaseHTTPServer.BaseHTTPRequestHandler.send_header
        keyword = keyword.title()
        if keyword == 'Set-Cookie':
            for cookie in re.split(r', (?=[^ =]+(?:=|$))', value):
                base_send_header(self, keyword, cookie)
        elif keyword == 'Content-Disposition' and '"' not in value:
            value = re.sub(r'filename=([^"\']+)', 'filename="\\1"', value)
            base_send_header(self, keyword, value)
        else:
            base_send_header(self, keyword, value)

    def setup(self):
        if isinstance(self.__class__.first_run, collections.Callable):
            try:
                with self.__class__.first_run_lock:
                    if isinstance(self.__class__.first_run, collections.Callable):
                        self.first_run()
                        self.__class__.first_run = None
            except StandardError as e:
                logging.exception('%s.first_run() return %r', self.__class__, e)
        self.__class__.setup = BaseHTTPServer.BaseHTTPRequestHandler.setup
        self.__class__.do_CONNECT = self.__class__.do_METHOD
        self.__class__.do_GET = self.__class__.do_METHOD
        self.__class__.do_PUT = self.__class__.do_METHOD
        self.__class__.do_POST = self.__class__.do_METHOD
        self.__class__.do_HEAD = self.__class__.do_METHOD
        self.__class__.do_DELETE = self.__class__.do_METHOD
        self.__class__.do_OPTIONS = self.__class__.do_METHOD
        self.setup()

    def handle_one_request(self):
        if not self.disable_transport_ssl and self.scheme == 'http':
            leadbyte = self.connection.recv(1, socket.MSG_PEEK)
            if leadbyte in ('\x80', '\x16'):
                server_name = ''
                if leadbyte == '\x16':
                    for _ in xrange(2):
                        leaddata = self.connection.recv(1024, socket.MSG_PEEK)
                        if is_clienthello(leaddata):
                            try:
                                server_name = extract_sni_name(leaddata)
                            finally:
                                break
                try:
                    certfile = CertUtil.get_cert(server_name or 'www.google.com')
                    ssl_sock = ssl.wrap_socket(self.connection, ssl_version=self.ssl_version, keyfile=certfile, certfile=certfile, server_side=True)
                except StandardError as e:
                    if e.args[0] not in (errno.ECONNABORTED, errno.ECONNRESET):
                        logging.exception('ssl.wrap_socket(self.connection=%r) failed: %s', self.connection, e)
                    return
                self.connection = ssl_sock
                self.rfile = self.connection.makefile('rb', self.bufsize)
                self.wfile = self.connection.makefile('wb', 0)
                self.scheme = 'https'
        return BaseHTTPServer.BaseHTTPRequestHandler.handle_one_request(self)

    def first_run(self):
        pass

    def gethostbyname2(self, hostname):
        return socket.gethostbyname_ex(hostname)[-1]

    def create_tcp_connection(self, hostname, port, timeout, **kwargs):
        return socket.create_connection((hostname, port), timeout)

    def create_ssl_connection(self, hostname, port, timeout, **kwargs):
        sock = self.create_tcp_connection(hostname, port, timeout, **kwargs)
        ssl_sock = ssl.wrap_socket(sock, ssl_version=self.ssl_version)
        return ssl_sock

    def create_http_request(self, method, url, headers, body, timeout, **kwargs):
        scheme, netloc, path, query, _ = urlparse.urlsplit(url)
        if netloc.rfind(':') <= netloc.rfind(']'):
            # no port number
            host = netloc
            port = 443 if scheme == 'https' else 80
        else:
            host, _, port = netloc.rpartition(':')
            port = int(port)
        if query:
            path += '?' + query
        if 'Host' not in headers:
            headers['Host'] = host
        if body and 'Content-Length' not in headers:
            headers['Content-Length'] = str(len(body))
        ConnectionType = httplib.HTTPSConnection if scheme == 'https' else httplib.HTTPConnection
        connection = ConnectionType(netloc, timeout=timeout)
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        return response

    def create_http_request_withserver(self, fetchserver, method, url, headers, body, timeout, **kwargs):
        return URLFetch(fetchserver, self.create_http_request).fetch(method, url, headers, body, timeout, **kwargs)

    def handle_urlfetch_error(self, fetchserver, response):
        pass

    def handle_urlfetch_response_close(self, fetchserver, response):
        pass

    def parse_header(self):
        if self.command == 'CONNECT':
            netloc = self.path
        elif self.path[0] == '/':
            netloc = self.headers.get('Host', 'localhost')
            self.path = '%s://%s%s' % (self.scheme, netloc, self.path)
        else:
            netloc = urlparse.urlsplit(self.path).netloc
        m = re.match(r'^(.+):(\d+)$', netloc)
        if m:
            self.host = m.group(1).strip('[]')
            self.port = int(m.group(2))
        else:
            self.host = netloc
            self.port = 443 if self.scheme == 'https' else 80

    def forward_socket(self, local, remote, timeout):
        try:
            tick = 1
            bufsize = self.bufsize
            timecount = timeout
            while 1:
                timecount -= tick
                if timecount <= 0:
                    break
                (ins, _, errors) = select.select([local, remote], [], [local, remote], tick)
                if errors:
                    break
                for sock in ins:
                    data = sock.recv(bufsize)
                    if not data:
                        break
                    if sock is remote:
                        local.sendall(data)
                        timecount = timeout
                    else:
                        remote.sendall(data)
                        timecount = timeout
        except socket.timeout:
            pass
        except NetWorkIOError as e:
            if e.args[0] not in (errno.ECONNABORTED, errno.ECONNRESET, errno.ENOTCONN, errno.EPIPE):
                raise
            if e.args[0] in (errno.EBADF,):
                return
        finally:
            for sock in (remote, local):
                try:
                    sock.close()
                except StandardError:
                    pass

    def MOCK(self, status, headers, content):
        """mock response"""
        logging.info('%s "MOCK %s %s %s" %d %d', self.address_string(), self.command, self.path, self.protocol_version, status, len(content))
        headers = dict((k.title(), v) for k, v in headers.items())
        if 'Transfer-Encoding' in headers:
            del headers['Transfer-Encoding']
        if 'Content-Length' not in headers:
            headers['Content-Length'] = len(content)
        if 'Connection' not in headers:
            headers['Connection'] = 'close'
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(content)

    def STRIP(self, do_ssl_handshake=True, sticky_filter=None):
        """strip connect"""
        certfile = CertUtil.get_cert(self.host)
        logging.info('%s "STRIP %s %s:%d %s" - -', self.address_string(), self.command, self.host, self.port, self.protocol_version)
        self.send_response(200)
        self.end_headers()
        if do_ssl_handshake:
            try:
                ssl_sock = ssl.wrap_socket(self.connection, ssl_version=self.ssl_version, keyfile=certfile, certfile=certfile, server_side=True)
            except StandardError as e:
                if e.args[0] not in (errno.ECONNABORTED, errno.ECONNRESET):
                    logging.exception('ssl.wrap_socket(self.connection=%r) failed: %s', self.connection, e)
                return
            self.connection = ssl_sock
            self.rfile = self.connection.makefile('rb', self.bufsize)
            self.wfile = self.connection.makefile('wb', 0)
            self.scheme = 'https'
        try:
            self.raw_requestline = self.rfile.readline(65537)
            if len(self.raw_requestline) > 65536:
                self.requestline = ''
                self.request_version = ''
                self.command = ''
                self.send_error(414)
                return
            if not self.raw_requestline:
                self.close_connection = 1
                return
            if not self.parse_request():
                return
        except NetWorkIOError as e:
            if e.args[0] not in (errno.ECONNABORTED, errno.ECONNRESET, errno.EPIPE):
                raise
        self.sticky_filter = sticky_filter
        try:
            self.do_METHOD()
        except NetWorkIOError as e:
            if e.args[0] not in (errno.ECONNABORTED, errno.ETIMEDOUT, errno.EPIPE):
                raise

    def FORWARD(self, hostname, port, timeout, kwargs={}):
        """forward socket"""
        do_ssl_handshake = kwargs.pop('do_ssl_handshake', False)
        local = self.connection
        remote = None
        self.send_response(200)
        self.end_headers()
        self.close_connection = 1
        data = local.recv(1024)
        if not data:
            local.close()
            return
        data_is_clienthello = is_clienthello(data)
        if data_is_clienthello:
            kwargs['client_hello'] = data
        max_retry = kwargs.get('max_retry', 3)
        for i in xrange(max_retry):
            try:
                if do_ssl_handshake:
                    remote = self.create_ssl_connection(hostname, port, timeout, **kwargs)
                else:
                    remote = self.create_tcp_connection(hostname, port, timeout, **kwargs)
                if not data_is_clienthello and remote and not isinstance(remote, Exception):
                    remote.sendall(data)
                break
            except StandardError as e:
                logging.exception('%s "FWD %s %s:%d %s" %r', self.address_string(), self.command, hostname, port, self.protocol_version, e)
                if hasattr(remote, 'close'):
                    remote.close()
                if i == max_retry - 1:
                    raise
        logging.info('%s "FWD %s %s:%d %s" - -', self.address_string(), self.command, hostname, port, self.protocol_version)
        if hasattr(remote, 'fileno'):
            # reset timeout default to avoid long http upload failure, but it will delay timeout retry :(
            remote.settimeout(None)
        del kwargs
        data = data_is_clienthello and getattr(remote, 'data', None)
        if data:
            del remote.data
            local.sendall(data)
        self.forward_socket(local, remote, self.max_timeout)

    def DIRECT(self, kwargs):
        method = self.command
        if 'url' in kwargs:
            url = kwargs.pop('url')
        elif self.path.lower().startswith(('http://', 'https://', 'ftp://')):
            url = self.path
        else:
            url = 'http://%s%s' % (self.headers['Host'], self.path)
        headers = dict((k.title(), v) for k, v in self.headers.items())
        body = self.body
        response = None
        try:
            response = self.create_http_request(method, url, headers, body, timeout=self.connect_timeout, **kwargs)
            logging.info('%s "DIRECT %s %s %s" %s %s', self.address_string(), self.command, url, self.protocol_version, response.status, response.getheader('Content-Length', '-'))
            response_headers = dict((k.title(), v) for k, v in response.getheaders())
            self.send_response(response.status)
            for key, value in response.getheaders():
                self.send_header(key, value)
            self.end_headers()
            if self.command == 'HEAD' or response.status in (204, 304):
                response.close()
                return
            need_chunked = 'Transfer-Encoding' in response_headers
            while True:
                data = response.read(8192)
                if not data:
                    if need_chunked:
                        self.wfile.write('0\r\n\r\n')
                    break
                if need_chunked:
                    self.wfile.write('%x\r\n' % len(data))
                self.wfile.write(data)
                if need_chunked:
                    self.wfile.write('\r\n')
                del data
        except (ssl.SSLError, socket.timeout, socket.error):
            if response:
                if response.fp and response.fp._sock:
                    response.fp._sock.close()
                response.close()
        finally:
            if response:
                response.close()

    def URLFETCH(self, fetchservers, max_retry=2, kwargs={}):
        """urlfetch from fetchserver"""
        method = self.command
        if self.path[0] == '/':
            url = '%s://%s%s' % (self.scheme, self.headers['Host'], self.path)
        elif self.path.lower().startswith(('http://', 'https://', 'ftp://')):
            url = self.path
        else:
            raise ValueError('URLFETCH %r is not a valid url' % self.path)
        headers = dict((k.title(), v) for k, v in self.headers.items())
        body = self.body
        response = None
        errors = []
        fetchserver = fetchservers[0]
        for i in xrange(max_retry):
            try:
                response = self.create_http_request_withserver(fetchserver, method, url, headers, body, timeout=60, **kwargs)
                if response.app_status < 400:
                    break
                else:
                    self.handle_urlfetch_error(fetchserver, response)
                if i < max_retry - 1:
                    if len(fetchservers) > 1:
                        fetchserver = random.choice(fetchservers[1:])
                    logging.info('URLFETCH return %d, trying fetchserver=%r', response.app_status, fetchserver)
                    response.close()
            except StandardError as e:
                errors.append(e)
                logging.info('URLFETCH "%s %s" fetchserver=%r %r, retry...', method, url, fetchserver, e)
        if len(errors) == max_retry:
            if response and response.app_status >= 500:
                status = response.app_status
                headers = dict(response.getheaders())
                content = response.read()
                response.close()
            else:
                status = 502
                headers = {'Content-Type': 'text/html'}
                content = message_html('502 URLFetch failed', 'Local URLFetch %r failed' % url, '<br>'.join(repr(x) for x in errors))
            return self.MOCK(status, headers, content)
        logging.info('%s "URL %s %s %s" %s %s', self.address_string(), method, url, self.protocol_version, response.status, response.getheader('Content-Length', '-'))
        try:
            if response.status == 206:
                return RangeFetch(self, response, fetchservers, **kwargs).fetch()
            if response.app_header_parsed:
                self.close_connection = not response.getheader('Content-Length')
                self.send_response(response.status)
                for key, value in response.getheaders():
                    if key.title() == 'Transfer-Encoding':
                        continue
                    self.send_header(key, value)
                self.end_headers()
            bufsize = 8192
            while True:
                data = response.read(bufsize)
                if data:
                    self.wfile.write(data)
                if not data:
                    self.handle_urlfetch_response_close(fetchserver, response)
                    response.close()
                    break
                del data
        except NetWorkIOError as e:
            if e[0] in (errno.ECONNABORTED, errno.EPIPE) or 'bad write retry' in repr(e):
                return

    def do_METHOD(self):
        self.parse_header()
        self.body = self.rfile.read(int(self.headers['Content-Length'])) if 'Content-Length' in self.headers else ''
        if self.sticky_filter:
            action = self.sticky_filter.filter(self)
            if action:
                return action.pop(0)(*action)
        for handler_filter in self.handler_filters:
            action = handler_filter.filter(self)
            if action:
                return action.pop(0)(*action)


class RangeFetch(object):
    """Range Fetch Class"""

    threads = 2
    maxsize = 1024*1024*4
    bufsize = 8192
    waitsize = 1024*512

    def __init__(self, handler, response, fetchservers, **kwargs):
        self.handler = handler
        self.url = handler.path
        self.response = response
        self.fetchservers = fetchservers
        self.kwargs = kwargs
        self._stopped = None
        self._last_app_status = {}
        self.expect_begin = 0

    def fetch(self):
        response_status = self.response.status
        response_headers = dict((k.title(), v) for k, v in self.response.getheaders())
        content_range = response_headers['Content-Range']
        #content_length = response_headers['Content-Length']
        start, end, length = tuple(int(x) for x in re.search(r'bytes (\d+)-(\d+)/(\d+)', content_range).group(1, 2, 3))
        if start == 0:
            response_status = 200
            response_headers['Content-Length'] = str(length)
            del response_headers['Content-Range']
        else:
            response_headers['Content-Range'] = 'bytes %s-%s/%s' % (start, end, length)
            response_headers['Content-Length'] = str(length-start)

        logging.info('>>>>>>>>>>>>>>> RangeFetch started(%r) %d-%d', self.url, start, end)
        self.handler.send_response(response_status)
        for key, value in response_headers.items():
            self.handler.send_header(key, value)
        self.handler.end_headers()

        data_queue = Queue.PriorityQueue()
        range_queue = Queue.PriorityQueue()
        range_queue.put((start, end, self.response))
        self.expect_begin = start
        for begin in range(end+1, length, self.maxsize):
            range_queue.put((begin, min(begin+self.maxsize-1, length-1), None))
        for i in xrange(0, self.threads):
            range_delay_size = i * self.maxsize
            spawn_later(float(range_delay_size)/self.waitsize, self.__fetchlet, range_queue, data_queue, range_delay_size)
        has_peek = hasattr(data_queue, 'peek')
        peek_timeout = 120
        while self.expect_begin < length - 1:
            try:
                if has_peek:
                    begin, data = data_queue.peek(timeout=peek_timeout)
                    if self.expect_begin == begin:
                        data_queue.get()
                    elif self.expect_begin < begin:
                        time.sleep(0.1)
                        continue
                    else:
                        logging.error('RangeFetch Error: begin(%r) < expect_begin(%r), quit.', begin, self.expect_begin)
                        break
                else:
                    begin, data = data_queue.get(timeout=peek_timeout)
                    if self.expect_begin == begin:
                        pass
                    elif self.expect_begin < begin:
                        data_queue.put((begin, data))
                        time.sleep(0.1)
                        continue
                    else:
                        logging.error('RangeFetch Error: begin(%r) < expect_begin(%r), quit.', begin, self.expect_begin)
                        break
            except Queue.Empty:
                logging.error('data_queue peek timeout, break')
                break
            try:
                self.handler.wfile.write(data)
                self.expect_begin += len(data)
                del data
            except StandardError as e:
                logging.info('RangeFetch client connection aborted(%s).', e)
                break
        self._stopped = True

    def __fetchlet(self, range_queue, data_queue, range_delay_size):
        headers = dict((k.title(), v) for k, v in self.handler.headers.items())
        headers['Connection'] = 'close'
        while 1:
            try:
                if self._stopped:
                    return
                try:
                    start, end, response = range_queue.get(timeout=1)
                    if self.expect_begin < start and data_queue.qsize() * self.bufsize + range_delay_size > 30*1024*1024:
                        range_queue.put((start, end, response))
                        time.sleep(10)
                        continue
                    headers['Range'] = 'bytes=%d-%d' % (start, end)
                    fetchserver = ''
                    if not response:
                        fetchserver = random.choice(self.fetchservers)
                        if self._last_app_status.get(fetchserver, 200) >= 500:
                            time.sleep(5)
                        response = self.handler.create_http_request_withserver(fetchserver, self.handler.command, self.url, headers, self.handler.body, timeout=self.handler.connect_timeout, **self.kwargs)
                except Queue.Empty:
                    continue
                except StandardError as e:
                    logging.warning("Response %r in __fetchlet", e)
                    range_queue.put((start, end, None))
                    continue
                if not response:
                    logging.warning('RangeFetch %s return %r', headers['Range'], response)
                    range_queue.put((start, end, None))
                    continue
                if fetchserver:
                    self._last_app_status[fetchserver] = response.app_status
                if response.app_status != 200:
                    logging.warning('Range Fetch "%s %s" %s return %s', self.handler.command, self.url, headers['Range'], response.app_status)
                    response.close()
                    range_queue.put((start, end, None))
                    continue
                if response.getheader('Location'):
                    self.url = urlparse.urljoin(self.url, response.getheader('Location'))
                    logging.info('RangeFetch Redirect(%r)', self.url)
                    response.close()
                    range_queue.put((start, end, None))
                    continue
                if 200 <= response.status < 300:
                    content_range = response.getheader('Content-Range')
                    if not content_range:
                        logging.warning('RangeFetch "%s %s" return Content-Range=%r: response headers=%r', self.handler.command, self.url, content_range, response.getheaders())
                        response.close()
                        range_queue.put((start, end, None))
                        continue
                    content_length = int(response.getheader('Content-Length', 0))
                    logging.info('>>>>>>>>>>>>>>> [thread %s] %s %s', threading.currentThread().ident, content_length, content_range)
                    while 1:
                        try:
                            if self._stopped:
                                response.close()
                                return
                            data = response.read(self.bufsize)
                            if not data:
                                break
                            data_queue.put((start, data))
                            start += len(data)
                        except StandardError as e:
                            logging.warning('RangeFetch "%s %s" %s failed: %s', self.handler.command, self.url, headers['Range'], e)
                            break
                    if start < end + 1:
                        logging.warning('RangeFetch "%s %s" retry %s-%s', self.handler.command, self.url, start, end)
                        response.close()
                        range_queue.put((start, end, None))
                        continue
                    logging.info('>>>>>>>>>>>>>>> Successfully reached %d bytes.', start - 1)
                else:
                    logging.error('RangeFetch %r return %s', self.url, response.status)
                    response.close()
                    range_queue.put((start, end, None))
                    continue
            except StandardError as e:
                logging.exception('RangeFetch._fetchlet error:%s', e)
                raise


class AdvancedProxyHandler(SimpleProxyHandler):
    """Advanced Proxy Handler"""
    dns_cache = LRUCache(64*1024)
    dns_servers = []
    dns_blacklist = []
    tcp_connection_time = collections.defaultdict(float)
    tcp_connection_time_with_clienthello = collections.defaultdict(float)
    tcp_connection_cache = collections.defaultdict(Queue.PriorityQueue)
    ssl_connection_time = collections.defaultdict(float)
    ssl_connection_cache = collections.defaultdict(Queue.PriorityQueue)
    ssl_connection_keepalive = False
    max_window = 4

    def gethostbyname2(self, hostname):
        try:
            iplist = self.dns_cache[hostname]
        except KeyError:
            if re.match(r'^\d+\.\d+\.\d+\.\d+$', hostname) or ':' in hostname:
                iplist = [hostname]
            elif self.dns_servers:
                try:
                    record = dnslib_resolve_over_udp(hostname, self.dns_servers, timeout=2, blacklist=self.dns_blacklist)
                except socket.gaierror:
                    record = dnslib_resolve_over_tcp(hostname, self.dns_servers, timeout=2, blacklist=self.dns_blacklist)
                iplist = dnslib_record2iplist(record)
            else:
                iplist = socket.gethostbyname_ex(hostname)[-1]
            self.dns_cache[hostname] = iplist
        return iplist

    def create_tcp_connection(self, hostname, port, timeout, **kwargs):
        client_hello = kwargs.get('client_hello', None)
        cache_key = kwargs.get('cache_key') if not client_hello else None
        def create_connection(ipaddr, timeout, queobj):
            sock = None
            try:
                # create a ipv4/ipv6 socket object
                sock = socket.socket(socket.AF_INET if ':' not in ipaddr[0] else socket.AF_INET6)
                # set reuseaddr option to avoid 10048 socket error
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                # resize socket recv buffer 8K->32K to improve browser releated application performance
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 32*1024)
                # disable nagle algorithm to send http request quickly.
                sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, True)
                # set a short timeout to trigger timeout retry more quickly.
                sock.settimeout(min(self.connect_timeout, timeout))
                # start connection time record
                start_time = time.time()
                # TCP connect
                sock.connect(ipaddr)
                # record TCP connection time
                self.tcp_connection_time[ipaddr] = time.time() - start_time
                # send client hello and peek server hello
                if client_hello:
                    sock.sendall(client_hello)
                    if gevent and isinstance(sock, gevent.socket.socket):
                        sock.data = data = sock.recv(4096)
                    else:
                        data = sock.recv(4096, socket.MSG_PEEK)
                    if not data:
                        logging.debug('create_tcp_connection %r with client_hello return NULL byte, continue %r', ipaddr, time.time()-start_time)
                        raise socket.timeout('timed out')
                    # record TCP connection time with client hello
                    self.tcp_connection_time_with_clienthello[ipaddr] = time.time() - start_time
                # set timeout
                sock.settimeout(timeout)
                # put tcp socket object to output queobj
                queobj.put(sock)
            except (socket.error, OSError) as e:
                # any socket.error, put Excpetions to output queobj.
                queobj.put(e)
                # reset a large and random timeout to the ipaddr
                self.tcp_connection_time[ipaddr] = self.connect_timeout+random.random()
                # close tcp socket
                if sock:
                    sock.close()
        def close_connection(count, queobj, first_tcp_time):
            for _ in range(count):
                sock = queobj.get()
                tcp_time_threshold = min(1, 1.3 * first_tcp_time)
                if sock and not isinstance(sock, Exception):
                    ipaddr = sock.getpeername()
                    if cache_key and self.tcp_connection_time[ipaddr] < tcp_time_threshold:
                        cache_queue = self.tcp_connection_cache[cache_key]
                        if cache_queue.qsize() < 8:
                            try:
                                _, old_sock = cache_queue.get_nowait()
                                old_sock.close()
                            except Queue.Empty:
                                pass
                        cache_queue.put((time.time(), sock))
                    else:
                        sock.close()
        try:
            while cache_key:
                ctime, sock = self.tcp_connection_cache[cache_key].get_nowait()
                if time.time() - ctime < 30:
                    return sock
                else:
                    sock.close()
        except Queue.Empty:
            pass
        addresses = [(x, port) for x in self.gethostbyname2(hostname)]
        sock = None
        for _ in range(kwargs.get('max_retry', 3)):
            window = min((self.max_window+1)//2, len(addresses))
            if client_hello:
                addresses.sort(key=self.tcp_connection_time_with_clienthello.__getitem__)
            else:
                addresses.sort(key=self.tcp_connection_time.__getitem__)
            addrs = addresses[:window] + random.sample(addresses, window)
            queobj = gevent.queue.Queue() if gevent else Queue.Queue()
            for addr in addrs:
                thread.start_new_thread(create_connection, (addr, timeout, queobj))
            for i in range(len(addrs)):
                sock = queobj.get()
                if not isinstance(sock, Exception):
                    first_tcp_time = self.tcp_connection_time[sock.getpeername()] if not cache_key else 0
                    thread.start_new_thread(close_connection, (len(addrs)-i-1, queobj, first_tcp_time))
                    return sock
                elif i == 0:
                    # only output first error
                    logging.warning('create_tcp_connection to %r with %s return %r, try again.', hostname, addrs, sock)
        if isinstance(sock, Exception):
            raise sock

    def create_ssl_connection(self, hostname, port, timeout, **kwargs):
        cache_key = kwargs.get('cache_key')
        validate = kwargs.get('validate')
        def create_connection(ipaddr, timeout, queobj):
            sock = None
            ssl_sock = None
            try:
                # create a ipv4/ipv6 socket object
                sock = socket.socket(socket.AF_INET if ':' not in ipaddr[0] else socket.AF_INET6)
                # set reuseaddr option to avoid 10048 socket error
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                # resize socket recv buffer 8K->32K to improve browser releated application performance
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 32*1024)
                # disable negal algorithm to send http request quickly.
                sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, True)
                # set a short timeout to trigger timeout retry more quickly.
                sock.settimeout(min(self.connect_timeout, timeout))
                # pick up the certificate
                if not validate:
                    ssl_sock = ssl.wrap_socket(sock, ssl_version=self.ssl_version, do_handshake_on_connect=False)
                else:
                    ssl_sock = ssl.wrap_socket(sock, ssl_version=self.ssl_version, cert_reqs=ssl.CERT_REQUIRED, ca_certs=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cacert.pem'), do_handshake_on_connect=False)
                ssl_sock.settimeout(min(self.connect_timeout, timeout))
                # start connection time record
                start_time = time.time()
                # TCP connect
                ssl_sock.connect(ipaddr)
                connected_time = time.time()
                # SSL handshake
                ssl_sock.do_handshake()
                handshaked_time = time.time()
                # record TCP connection time
                self.tcp_connection_time[ipaddr] = ssl_sock.tcp_time = connected_time - start_time
                # record SSL connection time
                self.ssl_connection_time[ipaddr] = ssl_sock.ssl_time = handshaked_time - start_time
                ssl_sock.ssl_time = connected_time - start_time
                # sometimes, we want to use raw tcp socket directly(select/epoll), so setattr it to ssl socket.
                ssl_sock.sock = sock
                # verify SSL certificate.
                if validate and hostname.endswith('.appspot.com'):
                    cert = ssl_sock.getpeercert()
                    orgname = next((v for ((k, v),) in cert['subject'] if k == 'organizationName'))
                    if not orgname.lower().startswith('google '):
                        raise ssl.SSLError("%r certificate organizationName(%r) not startswith 'Google'" % (hostname, orgname))
                # set timeout
                ssl_sock.settimeout(timeout)
                # put ssl socket object to output queobj
                queobj.put(ssl_sock)
            except (socket.error, ssl.SSLError, OSError) as e:
                # any socket.error, put Excpetions to output queobj.
                queobj.put(e)
                # reset a large and random timeout to the ipaddr
                self.ssl_connection_time[ipaddr] = self.connect_timeout + random.random()
                # close ssl socket
                if ssl_sock:
                    ssl_sock.close()
                # close tcp socket
                if sock:
                    sock.close()
        def create_connection_withopenssl(ipaddr, timeout, queobj):
            sock = None
            ssl_sock = None
            try:
                # create a ipv4/ipv6 socket object
                sock = socket.socket(socket.AF_INET if ':' not in ipaddr[0] else socket.AF_INET6)
                # set reuseaddr option to avoid 10048 socket error
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                # resize socket recv buffer 8K->32K to improve browser releated application performance
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 32*1024)
                # disable negal algorithm to send http request quickly.
                sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, True)
                # set a short timeout to trigger timeout retry more quickly.
                sock.settimeout(timeout or self.connect_timeout)
                # pick up the certificate
                server_hostname = b'www.google.com' if hostname.endswith('.appspot.com') else None
                ssl_sock = SSLConnection(self.openssl_context, sock)
                ssl_sock.set_connect_state()
                if server_hostname:
                    ssl_sock.set_tlsext_host_name(server_hostname)
                # start connection time record
                start_time = time.time()
                # TCP connect
                ssl_sock.connect(ipaddr)
                connected_time = time.time()
                # SSL handshake
                ssl_sock.do_handshake()
                handshaked_time = time.time()
                # record TCP connection time
                self.tcp_connection_time[ipaddr] = ssl_sock.tcp_time = connected_time - start_time
                # record SSL connection time
                self.ssl_connection_time[ipaddr] = ssl_sock.ssl_time = handshaked_time - start_time
                # sometimes, we want to use raw tcp socket directly(select/epoll), so setattr it to ssl socket.
                ssl_sock.sock = sock
                # verify SSL certificate.
                if validate and hostname.endswith('.appspot.com'):
                    cert = ssl_sock.get_peer_certificate()
                    commonname = next((v for k, v in cert.get_subject().get_components() if k == 'CN'))
                    if '.google' not in commonname and not commonname.endswith('.appspot.com'):
                        raise socket.error("Host name '%s' doesn't match certificate host '%s'" % (hostname, commonname))
                # put ssl socket object to output queobj
                queobj.put(ssl_sock)
            except (socket.error, OpenSSL.SSL.Error, OSError) as e:
                # any socket.error, put Excpetions to output queobj.
                queobj.put(e)
                # reset a large and random timeout to the ipaddr
                self.ssl_connection_time[ipaddr] = self.connect_timeout + random.random()
                # close ssl socket
                if ssl_sock:
                    ssl_sock.close()
                # close tcp socket
                if sock:
                    sock.close()
        def close_connection(count, queobj, first_tcp_time, first_ssl_time):
            for _ in range(count):
                sock = queobj.get()
                ssl_time_threshold = min(1, 1.3 * first_ssl_time)
                if sock and not isinstance(sock, Exception):
                    if cache_key and sock.ssl_time < ssl_time_threshold:
                        cache_queue = self.ssl_connection_cache[cache_key]
                        if cache_queue.qsize() < 8:
                            try:
                                _, old_sock = cache_queue.get_nowait()
                                old_sock.close()
                            except Queue.Empty:
                                pass
                        cache_queue.put((time.time(), sock))
                    else:
                        sock.close()
        try:
            while cache_key:
                ctime, sock = self.ssl_connection_cache[cache_key].get_nowait()
                if time.time() - ctime < 30:
                    return sock
                else:
                    sock.close()
        except Queue.Empty:
            pass
        addresses = [(x, port) for x in self.gethostbyname2(hostname)]
        sock = None
        for _ in range(kwargs.get('max_retry', 3)):
            window = min((self.max_window+1)//2, len(addresses))
            addresses.sort(key=self.ssl_connection_time.__getitem__)
            addrs = addresses[:window] + random.sample(addresses, window)
            queobj = gevent.queue.Queue() if gevent else Queue.Queue()
            for addr in addrs:
                thread.start_new_thread(create_connection, (addr, timeout, queobj))
            for i in range(len(addrs)):
                sock = queobj.get()
                if not isinstance(sock, Exception):
                    thread.start_new_thread(close_connection, (len(addrs)-i-1, queobj, sock.tcp_time, sock.ssl_time))
                    return sock
                elif i == 0:
                    # only output first error
                    logging.warning('create_ssl_connection to %r with %s return %r, try again.', hostname, addrs, sock)
        if isinstance(sock, Exception):
            raise sock

    def create_http_request(self, method, url, headers, body, timeout, max_retry=2, bufsize=8192, crlf=None, validate=None, cache_key=None):
        scheme, netloc, path, query, _ = urlparse.urlsplit(url)
        if netloc.rfind(':') <= netloc.rfind(']'):
            # no port number
            host = netloc
            port = 443 if scheme == 'https' else 80
        else:
            host, _, port = netloc.rpartition(':')
            port = int(port)
        if query:
            path += '?' + query
        if 'Host' not in headers:
            headers['Host'] = host
        if body and 'Content-Length' not in headers:
            headers['Content-Length'] = str(len(body))
        sock = None
        for i in range(max_retry):
            try:
                create_connection = self.create_ssl_connection if scheme == 'https' else self.create_tcp_connection
                sock = create_connection(host, port, timeout, validate=validate, cache_key=cache_key)
                break
            except StandardError as e:
                logging.exception('create_http_request "%s %s" failed:%s', method, url, e)
                if sock:
                    sock.close()
                if i == max_retry - 1:
                    raise
        request_data = ''
        crlf_counter = 0
        if scheme != 'https' and crlf:
            fakeheaders = dict((k.title(), v) for k, v in headers.items())
            fakeheaders.pop('Content-Length', None)
            fakeheaders.pop('Cookie', None)
            fakeheaders.pop('Host', None)
            if 'User-Agent' not in fakeheaders:
                fakeheaders['User-Agent'] = 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1878.0 Safari/537.36'
            if 'Accept-Language' not in fakeheaders:
                fakeheaders['Accept-Language'] = 'zh-CN,zh;q=0.8,en-US;q=0.6,en;q=0.4'
            if 'Accept' not in fakeheaders:
                fakeheaders['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
            fakeheaders_data = ''.join('%s: %s\r\n' % (k, v) for k, v in fakeheaders.items() if k not in self.skip_headers)
            while crlf_counter < 5 or len(request_data) < 1500 * 2:
                request_data += 'GET / HTTP/1.1\r\n%s\r\n' % fakeheaders_data
                crlf_counter += 1
            request_data += '\r\n\r\n\r\n'
        request_data += '%s %s %s\r\n' % (method, path, self.protocol_version)
        request_data += ''.join('%s: %s\r\n' % (k.title(), v) for k, v in headers.items() if k.title() not in self.skip_headers)
        request_data += '\r\n'
        if isinstance(body, bytes):
            sock.sendall(request_data.encode() + body)
        elif hasattr(body, 'read'):
            sock.sendall(request_data)
            while 1:
                data = body.read(bufsize)
                if not data:
                    break
                sock.sendall(data)
        else:
            raise TypeError('create_http_request(body) must be a string or buffer, not %r' % type(body))
        response = None
        try:
            while crlf_counter:
                if sys.version[:3] == '2.7':
                    response = httplib.HTTPResponse(sock, buffering=False)
                else:
                    response = httplib.HTTPResponse(sock)
                    response.fp.close()
                    response.fp = sock.makefile('rb', 0)
                response.begin()
                response.read()
                response.close()
                crlf_counter -= 1
        except StandardError as e:
            logging.exception('crlf skip read host=%r path=%r error: %r', headers.get('Host'), path, e)
            if response:
                if response.fp and response.fp._sock:
                    response.fp._sock.close()
                response.close()
            if sock:
                sock.close()
            return None
        if sys.version[:3] == '2.7':
            response = httplib.HTTPResponse(sock, buffering=True)
        else:
            response = httplib.HTTPResponse(sock)
            response.fp.close()
            response.fp = sock.makefile('rb')
        response.begin()
        if self.ssl_connection_keepalive and scheme == 'https' and cache_key:
            response.cache_key = cache_key
            response.cache_sock = response.fp._sock
        return response

    def handle_urlfetch_response_close(self, fetchserver, response):
        cache_sock = getattr(response, 'cache_sock', None)
        if cache_sock:
            if self.scheme == 'https':
                self.ssl_connection_cache[response.cache_key].put((time.time(), cache_sock))
            else:
                cache_sock.close()
            del response.cache_sock

    def handle_urlfetch_error(self, fetchserver, response):
        pass


class Common(object):
    """Global Config Object"""

    ENV_CONFIG_PREFIX = 'GOAGENT_'

    def __init__(self):
        """load config from proxy.ini"""
        ConfigParser.RawConfigParser.OPTCRE = re.compile(r'(?P<option>[^=\s][^=]*)\s*(?P<vi>[=])\s*(?P<value>.*)$')
        self.CONFIG = ConfigParser.ConfigParser()
        self.CONFIG_FILENAME = os.path.splitext(os.path.abspath(__file__))[0]+'.ini'
        self.CONFIG_USER_FILENAME = re.sub(r'\.ini$', '.user.ini', self.CONFIG_FILENAME)
        self.CONFIG.read([self.CONFIG_FILENAME, self.CONFIG_USER_FILENAME])

        for key, value in os.environ.items():
            m = re.match(r'^%s([A-Z]+)_([A-Z\_\-]+)$' % self.ENV_CONFIG_PREFIX, key)
            if m:
                self.CONFIG.set(m.group(1).lower(), m.group(2).lower(), value)

        self.LISTEN_IP = self.CONFIG.get('listen', 'ip')
        self.LISTEN_PORT = self.CONFIG.getint('listen', 'port')
        self.LISTEN_USERNAME = self.CONFIG.get('listen', 'username') if self.CONFIG.has_option('listen', 'username') else ''
        self.LISTEN_PASSWORD = self.CONFIG.get('listen', 'password') if self.CONFIG.has_option('listen', 'password') else ''
        self.LISTEN_VISIBLE = self.CONFIG.getint('listen', 'visible')
        self.LISTEN_DEBUGINFO = self.CONFIG.getint('listen', 'debuginfo')

        self.GAE_APPIDS = re.findall(r'[\w\-\.]+', self.CONFIG.get('gae', 'appid').replace('.appspot.com', ''))
        self.GAE_PASSWORD = self.CONFIG.get('gae', 'password').strip()
        self.GAE_PATH = self.CONFIG.get('gae', 'path')
        self.GAE_MODE = self.CONFIG.get('gae', 'mode')
        self.GAE_PROFILE = self.CONFIG.get('gae', 'profile').strip()
        self.GAE_WINDOW = self.CONFIG.getint('gae', 'window')
        self.GAE_KEEPALIVE = self.CONFIG.getint('gae', 'keepalive') if self.CONFIG.has_option('gae', 'keepalive') else 0
        self.GAE_OBFUSCATE = self.CONFIG.getint('gae', 'obfuscate')
        self.GAE_VALIDATE = self.CONFIG.getint('gae', 'validate')
        self.GAE_TRANSPORT = self.CONFIG.getint('gae', 'transport') if self.CONFIG.has_option('gae', 'transport') else 0
        self.GAE_OPTIONS = self.CONFIG.get('gae', 'options')
        self.GAE_REGIONS = set(x.upper() for x in self.CONFIG.get('gae', 'regions').split('|') if x.strip())
        self.GAE_SSLVERSION = self.CONFIG.get('gae', 'sslversion')

        if self.GAE_PROFILE == 'auto':
            try:
                socket.create_connection(('2001:4860:4860::8888', 53), timeout=1).close()
                logging.info('Use profile ipv6')
                self.GAE_PROFILE = 'ipv6'
            except socket.error as e:
                logging.info('Fail try profile ipv6 %r, fallback ipv4', e)
                self.GAE_PROFILE = 'ipv4'
        hosts_section, http_section = '%s/hosts' % self.GAE_PROFILE, '%s/http' % self.GAE_PROFILE

        if 'USERDNSDOMAIN' in os.environ and re.match(r'^\w+\.\w+$', os.environ['USERDNSDOMAIN']):
            self.CONFIG.set(hosts_section, '.' + os.environ['USERDNSDOMAIN'], '')

        self.HOST_MAP = collections.OrderedDict((k, v or k) for k, v in self.CONFIG.items(hosts_section) if '\\' not in k and ':' not in k and not k.startswith('.'))
        self.HOST_POSTFIX_MAP = collections.OrderedDict((k, v) for k, v in self.CONFIG.items(hosts_section) if '\\' not in k and ':' not in k and k.startswith('.'))
        self.HOST_POSTFIX_ENDSWITH = tuple(self.HOST_POSTFIX_MAP)

        self.HOSTPORT_MAP = collections.OrderedDict((k, v) for k, v in self.CONFIG.items(hosts_section) if ':' in k and not k.startswith('.'))
        self.HOSTPORT_POSTFIX_MAP = collections.OrderedDict((k, v) for k, v in self.CONFIG.items(hosts_section) if ':' in k and k.startswith('.'))
        self.HOSTPORT_POSTFIX_ENDSWITH = tuple(self.HOSTPORT_POSTFIX_MAP)

        self.URLRE_MAP = collections.OrderedDict((re.compile(k).match, v) for k, v in self.CONFIG.items(hosts_section) if '\\' in k)

        self.HTTP_WITHGAE = set(self.CONFIG.get(http_section, 'withgae').split('|'))
        self.HTTP_CRLFSITES = tuple(self.CONFIG.get(http_section, 'crlfsites').split('|'))
        self.HTTP_FORCEHTTPS = set(self.CONFIG.get(http_section, 'forcehttps').split('|'))
        self.HTTP_FAKEHTTPS = set(self.CONFIG.get(http_section, 'fakehttps').split('|'))
        self.HTTP_DNS = self.CONFIG.get(http_section, 'dns').split('|') if self.CONFIG.has_option(http_section, 'dns') else []

        self.IPLIST_MAP = collections.OrderedDict((k, v.split('|')) for k, v in self.CONFIG.items('iplist'))
        self.IPLIST_MAP.update((k, [k]) for k, v in self.HOST_MAP.items() if k == v)

        self.PAC_ENABLE = self.CONFIG.getint('pac', 'enable')
        self.PAC_IP = self.CONFIG.get('pac', 'ip')
        self.PAC_PORT = self.CONFIG.getint('pac', 'port')
        self.PAC_FILE = self.CONFIG.get('pac', 'file').lstrip('/')
        self.PAC_GFWLIST = self.CONFIG.get('pac', 'gfwlist')
        self.PAC_ADBLOCK = self.CONFIG.get('pac', 'adblock')
        self.PAC_ADMODE = self.CONFIG.getint('pac', 'admode')
        self.PAC_EXPIRED = self.CONFIG.getint('pac', 'expired')

        self.PHP_ENABLE = self.CONFIG.getint('php', 'enable')
        self.PHP_LISTEN = self.CONFIG.get('php', 'listen')
        self.PHP_PASSWORD = self.CONFIG.get('php', 'password') if self.CONFIG.has_option('php', 'password') else ''
        self.PHP_CRLF = self.CONFIG.getint('php', 'crlf') if self.CONFIG.has_option('php', 'crlf') else 1
        self.PHP_VALIDATE = self.CONFIG.getint('php', 'validate') if self.CONFIG.has_option('php', 'validate') else 0
        self.PHP_FETCHSERVER = self.CONFIG.get('php', 'fetchserver')
        self.PHP_USEHOSTS = self.CONFIG.getint('php', 'usehosts')

        self.PROXY_ENABLE = self.CONFIG.getint('proxy', 'enable')
        self.PROXY_AUTODETECT = self.CONFIG.getint('proxy', 'autodetect') if self.CONFIG.has_option('proxy', 'autodetect') else 0
        self.PROXY_HOST = self.CONFIG.get('proxy', 'host')
        self.PROXY_PORT = self.CONFIG.getint('proxy', 'port')
        self.PROXY_USERNAME = self.CONFIG.get('proxy', 'username')
        self.PROXY_PASSWROD = self.CONFIG.get('proxy', 'password')

        if not self.PROXY_ENABLE and self.PROXY_AUTODETECT:
            system_proxy = ProxyUtil.get_system_proxy()
            if system_proxy and self.LISTEN_IP not in system_proxy:
                _, username, password, address = ProxyUtil.parse_proxy(system_proxy)
                proxyhost, _, proxyport = address.rpartition(':')
                self.PROXY_ENABLE = 1
                self.PROXY_USERNAME = username
                self.PROXY_PASSWROD = password
                self.PROXY_HOST = proxyhost
                self.PROXY_PORT = int(proxyport)
        if self.PROXY_ENABLE:
            self.GAE_MODE = 'https'

        self.AUTORANGE_HOSTS = self.CONFIG.get('autorange', 'hosts').split('|')
        self.AUTORANGE_HOSTS_MATCH = [re.compile(fnmatch.translate(h)).match for h in self.AUTORANGE_HOSTS]
        self.AUTORANGE_ENDSWITH = tuple(self.CONFIG.get('autorange', 'endswith').split('|'))
        self.AUTORANGE_NOENDSWITH = tuple(self.CONFIG.get('autorange', 'noendswith').split('|'))
        self.AUTORANGE_MAXSIZE = self.CONFIG.getint('autorange', 'maxsize')
        self.AUTORANGE_WAITSIZE = self.CONFIG.getint('autorange', 'waitsize')
        self.AUTORANGE_BUFSIZE = self.CONFIG.getint('autorange', 'bufsize')
        self.AUTORANGE_THREADS = self.CONFIG.getint('autorange', 'threads')

        self.FETCHMAX_LOCAL = self.CONFIG.getint('fetchmax', 'local') if self.CONFIG.get('fetchmax', 'local') else 3
        self.FETCHMAX_SERVER = self.CONFIG.get('fetchmax', 'server')

        self.DNS_ENABLE = self.CONFIG.getint('dns', 'enable')
        self.DNS_LISTEN = self.CONFIG.get('dns', 'listen')
        self.DNS_SERVERS = self.HTTP_DNS or self.CONFIG.get('dns', 'servers').split('|')
        self.DNS_BLACKLIST = set(self.CONFIG.get('dns', 'blacklist').split('|'))
        self.DNS_TCPOVER = tuple(self.CONFIG.get('dns', 'tcpover').split('|'))

        self.USERAGENT_ENABLE = self.CONFIG.getint('useragent', 'enable')
        self.USERAGENT_STRING = self.CONFIG.get('useragent', 'string')

        self.LOVE_ENABLE = self.CONFIG.getint('love', 'enable')
        self.LOVE_TIP = self.CONFIG.get('love', 'tip').encode('utf8').decode('unicode-escape').split('|')

    def resolve_iplist(self):
        def do_resolve(host, dnsservers, queue):
            iplist = []
            for dnslib_resolve in (dnslib_resolve_over_udp, dnslib_resolve_over_tcp):
                try:
                    iplist += dnslib_record2iplist(dnslib_resolve_over_udp(host, dnsservers, timeout=2, blacklist=self.DNS_BLACKLIST))
                except (socket.error, OSError) as e:
                    logging.warning('%r remote host=%r failed: %s', dnslib_resolve, host, e)
            queue.put((host, dnsservers, iplist))
        # https://support.google.com/websearch/answer/186669?hl=zh-Hans
        google_blacklist = ['216.239.32.20'] + list(self.DNS_BLACKLIST)
        for name, need_resolve_hosts in list(self.IPLIST_MAP.items()):
            if all(re.match(r'\d+\.\d+\.\d+\.\d+', x) or ':' in x for x in need_resolve_hosts):
                continue
            need_resolve_remote = [x for x in need_resolve_hosts if ':' not in x and not re.match(r'\d+\.\d+\.\d+\.\d+', x)]
            resolved_iplist = [x for x in need_resolve_hosts if x not in need_resolve_remote]
            result_queue = Queue.Queue()
            for host in need_resolve_remote:
                for dnsserver in self.DNS_SERVERS:
                    logging.debug('resolve remote host=%r from dnsserver=%r', host, dnsserver)
                    thread.start_new_thread(do_resolve, (host, [dnsserver], result_queue))
            for _ in xrange(len(self.DNS_SERVERS) * len(need_resolve_remote)):
                try:
                    host, dnsservers, iplist = result_queue.get(timeout=5)
                    resolved_iplist += iplist or []
                    logging.debug('resolve remote host=%r from dnsservers=%s return iplist=%s', host, dnsservers, iplist)
                except Queue.Empty:
                    logging.warn('resolve remote timeout, try resolve local')
                    resolved_iplist += sum([socket.gethostbyname_ex(x)[-1] for x in need_resolve_remote], [])
                    break
            if name.startswith('google_') and name not in ('google_cn', 'google_hk'):
                iplist_prefix = re.split(r'[\.:]', resolved_iplist[0])[0]
                resolved_iplist = list(set(x for x in resolved_iplist if x.startswith(iplist_prefix)))
            else:
                resolved_iplist = list(set(resolved_iplist))
            if name.startswith('google_'):
                resolved_iplist = list(set(resolved_iplist) - set(google_blacklist))
            if len(resolved_iplist) == 0:
                logging.error('resolve %s host return empty! please retry!', name)
                sys.exit(-1)
            logging.info('resolve name=%s host to iplist=%r', name, resolved_iplist)
            common.IPLIST_MAP[name] = resolved_iplist

    def info(self):
        info = ''
        info += '------------------------------------------------------\n'
        info += 'GoAgent Version    : %s (python/%s %spyopenssl/%s)\n' % (__version__, sys.version[:5], gevent and 'gevent/%s ' % gevent.__version__ or '', getattr(OpenSSL, '__version__', 'Disabled'))
        info += 'Uvent Version      : %s (pyuv/%s libuv/%s)\n' % (__import__('uvent').__version__, __import__('pyuv').__version__, __import__('pyuv').LIBUV_VERSION) if all(x in sys.modules for x in ('pyuv', 'uvent')) else ''
        info += 'Listen Address     : %s:%d\n' % (self.LISTEN_IP, self.LISTEN_PORT)
        info += 'Local Proxy        : %s:%s\n' % (self.PROXY_HOST, self.PROXY_PORT) if self.PROXY_ENABLE else ''
        info += 'Debug INFO         : %s\n' % self.LISTEN_DEBUGINFO if self.LISTEN_DEBUGINFO else ''
        info += 'GAE Mode           : %s\n' % self.GAE_MODE
        info += 'GAE Profile        : %s\n' % self.GAE_PROFILE if self.GAE_PROFILE else ''
        info += 'GAE APPID          : %s\n' % '|'.join(self.GAE_APPIDS)
        info += 'GAE Validate       : %s\n' % self.GAE_VALIDATE if self.GAE_VALIDATE else ''
        info += 'GAE Obfuscate      : %s\n' % self.GAE_OBFUSCATE if self.GAE_OBFUSCATE else ''
        if common.PAC_ENABLE:
            info += 'Pac Server         : http://%s:%d/%s\n' % (self.PAC_IP if self.PAC_IP and self.PAC_IP != '0.0.0.0' else ProxyUtil.get_listen_ip(), self.PAC_PORT, self.PAC_FILE)
            info += 'Pac File           : file://%s\n' % os.path.abspath(self.PAC_FILE)
        if common.PHP_ENABLE:
            info += 'PHP Listen         : %s\n' % common.PHP_LISTEN
            info += 'PHP FetchServer    : %s\n' % common.PHP_FETCHSERVER
        if common.DNS_ENABLE:
            info += 'DNS Listen         : %s\n' % common.DNS_LISTEN
            info += 'DNS Servers        : %s\n' % '|'.join(common.DNS_SERVERS)
        info += '------------------------------------------------------\n'
        return info

common = Common()


def message_html(title, banner, detail=''):
    MESSAGE_TEMPLATE = '''
    <html><head>
    <meta http-equiv="content-type" content="text/html;charset=utf-8">
    <title>$title</title>
    <style><!--
    body {font-family: arial,sans-serif}
    div.nav {margin-top: 1ex}
    div.nav A {font-size: 10pt; font-family: arial,sans-serif}
    span.nav {font-size: 10pt; font-family: arial,sans-serif; font-weight: bold}
    div.nav A,span.big {font-size: 12pt; color: #0000cc}
    div.nav A {font-size: 10pt; color: black}
    A.l:link {color: #6f6f6f}
    A.u:link {color: green}
    //--></style>
    </head>
    <body text=#000000 bgcolor=#ffffff>
    <table border=0 cellpadding=2 cellspacing=0 width=100%>
    <tr><td bgcolor=#3366cc><font face=arial,sans-serif color=#ffffff><b>Message From LocalProxy</b></td></tr>
    <tr><td> </td></tr></table>
    <blockquote>
    <H1>$banner</H1>
    $detail
    <p>
    </blockquote>
    <table width=100% cellpadding=0 cellspacing=0><tr><td bgcolor=#3366cc><img alt="" width=1 height=4></td></tr></table>
    </body></html>
    '''
    return string.Template(MESSAGE_TEMPLATE).substitute(title=title, banner=banner, detail=detail)


try:
    from Crypto.Cipher.ARC4 import new as RC4Cipher
except ImportError:
    logging.warn('Load Crypto.Cipher.ARC4 Failed, Use Pure Python Instead.')
    class RC4Cipher(object):
        def __init__(self, key):
            x = 0
            box = range(256)
            for i, y in enumerate(box):
                x = (x + y + ord(key[i % len(key)])) & 0xff
                box[i], box[x] = box[x], y
            self.__box = box
            self.__x = 0
            self.__y = 0
        def encrypt(self, data):
            out = []
            out_append = out.append
            x = self.__x
            y = self.__y
            box = self.__box
            for char in data:
                x = (x + 1) & 0xff
                y = (y + box[x]) & 0xff
                box[x], box[y] = box[y], box[x]
                out_append(chr(ord(char) ^ box[(box[x] + box[y]) & 0xff]))
            self.__x = x
            self.__y = y
            return ''.join(out)


class XORCipher(object):
    """XOR Cipher Class"""
    def __init__(self, key):
        self.__key_gen = itertools.cycle([ord(x) for x in key]).next
        self.__key_xor = lambda s: ''.join(chr(ord(x) ^ self.__key_gen()) for x in s)
        if len(key) == 1:
            try:
                from Crypto.Util.strxor import strxor_c
                c = ord(key)
                self.__key_xor = lambda s: strxor_c(s, c)
            except ImportError:
                sys.stderr.write('Load Crypto.Util.strxor Failed, Use Pure Python Instead.\n')

    def encrypt(self, data):
        return self.__key_xor(data)


class CipherFileObject(object):
    """fileobj wrapper for cipher"""
    def __init__(self, fileobj, cipher):
        self.__fileobj = fileobj
        self.__cipher = cipher
    def __getattr__(self, attr):
        if attr not in ('__fileobj', '__cipher'):
            return getattr(self.__fileobj, attr)
    def read(self, size=-1):
        return self.__cipher.encrypt(self.__fileobj.read(size))


class LocalProxyServer(SocketServer.ThreadingTCPServer):
    """Local Proxy Server"""
    allow_reuse_address = True
    daemon_threads = True

    def close_request(self, request):
        try:
            request.close()
        except StandardError:
            pass

    def finish_request(self, request, client_address):
        try:
            self.RequestHandlerClass(request, client_address, self)
        except NetWorkIOError as e:
            if e[0] not in (errno.ECONNABORTED, errno.ECONNRESET, errno.EPIPE):
                raise

    def handle_error(self, *args):
        """make ThreadingTCPServer happy"""
        exc_info = sys.exc_info()
        error = exc_info and len(exc_info) and exc_info[1]
        if isinstance(error, NetWorkIOError) and len(error.args) > 1 and 'bad write retry' in error.args[1]:
            exc_info = error = None
        else:
            del exc_info, error
            SocketServer.ThreadingTCPServer.handle_error(self, *args)


class UserAgentFilter(BaseProxyHandlerFilter):
    """user agent filter"""
    def filter(self, handler):
        if common.USERAGENT_ENABLE:
            handler.headers['User-Agent'] = common.USERAGENT_STRING


class WithGAEFilter(BaseProxyHandlerFilter):
    """with gae filter"""
    def filter(self, handler):
        if handler.host in common.HTTP_WITHGAE:
            logging.debug('WithGAEFilter metched %r %r', handler.path, handler.headers)
            # assume the last one handler is GAEFetchFilter
            return handler.handler_filters[-1].filter(handler)


class ForceHttpsFilter(BaseProxyHandlerFilter):
    """force https filter"""
    def filter(self, handler):
        if handler.command != 'CONNECT' and handler.host in common.HTTP_FORCEHTTPS and not handler.headers.get('Referer', '').startswith('https://') and not handler.path.startswith('https://'):
            logging.debug('ForceHttpsFilter metched %r %r', handler.path, handler.headers)
            headers = {'Location': handler.path.replace('http://', 'https://', 1), 'Connection': 'close'}
            return [handler.MOCK, 301, headers, '']


class FakeHttpsFilter(BaseProxyHandlerFilter):
    """fake https filter"""
    def filter(self, handler):
        if handler.command == 'CONNECT' and handler.host in common.HTTP_FAKEHTTPS:
            logging.debug('FakeHttpsFilter metched %r %r', handler.path, handler.headers)
            return [handler.STRIP, True, None]


class HostsFilter(BaseProxyHandlerFilter):
    """force https filter"""
    def filter_localfile(self, handler, filename):
        content_type = None
        try:
            import mimetypes
            content_type = mimetypes.types_map.get(os.path.splitext(filename)[1])
        except StandardError as e:
            logging.error('import mimetypes failed: %r', e)
        try:
            with open(filename, 'rb') as fp:
                data = fp.read()
                headers = {'Connection': 'close', 'Content-Length': str(len(data))}
                if content_type:
                    headers['Content-Type'] = content_type
                return [handler.MOCK, 200, headers, data]
        except StandardError as e:
            return [handler.MOCK, 403, {'Connection': 'close'}, 'read %r %r' % (filename, e)]

    def filter(self, handler):
        host, port = handler.host, handler.port
        hostport = handler.path if handler.command == 'CONNECT' else '%s:%d' % (host, port)
        hostname = ''
        if host in common.HOST_MAP:
            hostname = common.HOST_MAP[host] or host
        elif host.endswith(common.HOST_POSTFIX_ENDSWITH):
            hostname = next(common.HOST_POSTFIX_MAP[x] for x in common.HOST_POSTFIX_MAP if host.endswith(x)) or host
            common.HOST_MAP[host] = hostname
        if hostport in common.HOSTPORT_MAP:
            hostname = common.HOSTPORT_MAP[hostport] or host
        elif hostport.endswith(common.HOSTPORT_POSTFIX_ENDSWITH):
            hostname = next(common.HOSTPORT_POSTFIX_MAP[x] for x in common.HOSTPORT_POSTFIX_MAP if hostport.endswith(x)) or host
            common.HOSTPORT_MAP[hostport] = hostname
        if handler.command != 'CONNECT' and common.URLRE_MAP:
            try:
                hostname = next(common.URLRE_MAP[x] for x in common.URLRE_MAP if x(handler.path)) or host
            except StopIteration:
                pass
        if not hostname:
            return None
        elif hostname in common.IPLIST_MAP:
            handler.dns_cache[host] = common.IPLIST_MAP[hostname]
        elif hostname == host and host.endswith(common.DNS_TCPOVER) and host not in handler.dns_cache:
            try:
                iplist = dnslib_record2iplist(dnslib_resolve_over_tcp(host, handler.dns_servers, timeout=4, blacklist=handler.dns_blacklist))
                logging.info('HostsFilter dnslib_resolve_over_tcp %r with %r return %s', host, handler.dns_servers, iplist)
                handler.dns_cache[host] = iplist
            except socket.error as e:
                logging.warning('HostsFilter dnslib_resolve_over_tcp %r with %r failed: %r', host, handler.dns_servers, e)
        elif re.match(r'^\d+\.\d+\.\d+\.\d+$', hostname) or ':' in hostname:
            handler.dns_cache[host] = [hostname]
        elif hostname.startswith('file://'):
            filename = hostname.lstrip('file://')
            if os.name == 'nt':
                filename = filename.lstrip('/')
            return self.filter_localfile(handler, filename)
        cache_key = '%s:%s' % (hostname, port)
        if handler.command == 'CONNECT':
            return [handler.FORWARD, host, port, handler.connect_timeout, {'cache_key': cache_key}]
        else:
            if host.endswith(common.HTTP_CRLFSITES):
                handler.close_connection = True
                return [handler.DIRECT, {'crlf': True}]
            else:
                return [handler.DIRECT, {'cache_key': cache_key}]


class DirectRegionFilter(BaseProxyHandlerFilter):
    """direct region filter"""
    geoip = pygeoip.GeoIP(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'GeoIP.dat')) if pygeoip and common.GAE_REGIONS else None
    region_cache = LRUCache(16*1024)

    def get_country_code(self, hostname, dnsservers):
        """http://dev.maxmind.com/geoip/legacy/codes/iso3166/"""
        try:
            return self.region_cache[hostname]
        except KeyError:
            pass
        try:
            if re.match(r'^\d+\.\d+\.\d+\.\d+$', hostname) or ':' in hostname:
                iplist = [hostname]
            elif dnsservers:
                iplist = dnslib_record2iplist(dnslib_resolve_over_udp(hostname, dnsservers, timeout=2))
            else:
                iplist = socket.gethostbyname_ex(hostname)[-1]
            country_code = self.geoip.country_code_by_addr(iplist[0])
        except StandardError as e:
            logging.warning('DirectRegionFilter cannot determine region for hostname=%r %r', hostname, e)
            country_code = ''
        self.region_cache[hostname] = country_code
        return country_code

    def filter(self, handler):
        if self.geoip:
            country_code = self.get_country_code(handler.host, handler.dns_servers)
            if country_code in common.GAE_REGIONS:
                if handler.command == 'CONNECT':
                    return [handler.FORWARD, handler.host, handler.port, handler.connect_timeout]
                else:
                    return [handler.DIRECT, {}]


class AutoRangeFilter(BaseProxyHandlerFilter):
    """force https filter"""
    def filter(self, handler):
        path = urlparse.urlsplit(handler.path).path
        need_autorange = any(x(handler.host) for x in common.AUTORANGE_HOSTS_MATCH) or path.endswith(common.AUTORANGE_ENDSWITH)
        if path.endswith(common.AUTORANGE_NOENDSWITH) or 'range=' in urlparse.urlsplit(path).query or handler.command == 'HEAD':
            need_autorange = False
        if handler.command != 'HEAD' and handler.headers.get('Range'):
            m = re.search(r'bytes=(\d+)-', handler.headers['Range'])
            start = int(m.group(1) if m else 0)
            handler.headers['Range'] = 'bytes=%d-%d' % (start, start+common.AUTORANGE_MAXSIZE-1)
            logging.info('autorange range=%r match url=%r', handler.headers['Range'], handler.path)
        elif need_autorange:
            logging.info('Found [autorange]endswith match url=%r', handler.path)
            m = re.search(r'bytes=(\d+)-', handler.headers.get('Range', ''))
            start = int(m.group(1) if m else 0)
            handler.headers['Range'] = 'bytes=%d-%d' % (start, start+common.AUTORANGE_MAXSIZE-1)


class GAEFetchFilter(BaseProxyHandlerFilter):
    """force https filter"""
    def filter(self, handler):
        """https://developers.google.com/appengine/docs/python/urlfetch/"""
        if handler.command == 'CONNECT':
            do_ssl_handshake = 440 <= handler.port <= 450 or 1024 <= handler.port <= 65535
            return [handler.STRIP, do_ssl_handshake, self if not common.URLRE_MAP else None]
        elif handler.command in ('GET', 'POST', 'HEAD', 'PUT', 'DELETE', 'PATCH'):
            kwargs = {}
            if common.GAE_PASSWORD:
                kwargs['password'] = common.GAE_PASSWORD
            if common.GAE_VALIDATE:
                kwargs['validate'] = 1
            fetchservers = ['%s://%s.appspot.com%s' % (common.GAE_MODE, x, common.GAE_PATH) for x in common.GAE_APPIDS]
            return [handler.URLFETCH, fetchservers, common.FETCHMAX_LOCAL, kwargs]
        else:
            if common.PHP_ENABLE:
                return PHPProxyHandler.handler_filters[-1].filter(handler)
            else:
                logging.warning('"%s %s" not supported by GAE, please enable PHP mode!', handler.command, handler.host)
                return [handler.DIRECT, {}]


class GAEProxyHandler(AdvancedProxyHandler):
    """GAE Proxy Handler"""
    handler_filters = [UserAgentFilter(), WithGAEFilter(), FakeHttpsFilter(), ForceHttpsFilter(), HostsFilter(), DirectRegionFilter(), AutoRangeFilter(), GAEFetchFilter()]

    def first_run(self):
        """GAEProxyHandler setup, init domain/iplist map"""
        if not common.PROXY_ENABLE:
            logging.info('resolve common.IPLIST_MAP names=%s to iplist', list(common.IPLIST_MAP))
            common.resolve_iplist()
        random.shuffle(common.GAE_APPIDS)
        for appid in common.GAE_APPIDS:
            host = '%s.appspot.com' % appid
            if host not in common.HOST_MAP:
                common.HOST_MAP[host] = common.HOST_POSTFIX_MAP['.appspot.com']
            if host not in self.dns_cache:
                self.dns_cache[host] = common.IPLIST_MAP[common.HOST_MAP[host]]

    def handle_urlfetch_error(self, fetchserver, response):
        gae_appid = urlparse.urlsplit(fetchserver).netloc.split('.')[-3]
        if response.app_status == 503:
            # appid over qouta, switch to next appid
            if gae_appid == common.GAE_APPIDS[0] and len(common.GAE_APPIDS) > 1:
                common.GAE_APPIDS.append(common.GAE_APPIDS.pop(0))
                logging.info('gae_appid=%r over qouta, switch next appid=%r', gae_appid, common.GAE_APPIDS[0])


class PHPFetchFilter(BaseProxyHandlerFilter):
    """force https filter"""
    def filter(self, handler):
        if handler.command == 'CONNECT':
            return [handler.STRIP, True, self]
        else:
            kwargs = {}
            if common.PHP_PASSWORD:
                kwargs['password'] = common.PHP_PASSWORD
            if common.PHP_VALIDATE:
                kwargs['validate'] = 1
            return [handler.URLFETCH, [common.PHP_FETCHSERVER], 1, kwargs]


class PHPProxyHandler(AdvancedProxyHandler):
    """PHP Proxy Handler"""
    first_run_lock = threading.Lock()
    handler_filters = [UserAgentFilter(), FakeHttpsFilter(), ForceHttpsFilter(), PHPFetchFilter()]

    def first_run(self):
        if common.PHP_USEHOSTS:
            self.handler_filters.insert(-1, HostsFilter())
        if not common.PROXY_ENABLE:
            common.resolve_iplist()
            fetchhost = re.sub(r':\d+$', '', urlparse.urlsplit(common.PHP_FETCHSERVER).netloc)
            logging.info('resolve common.PHP_FETCHSERVER domain=%r to iplist', fetchhost)
            if common.PHP_USEHOSTS and fetchhost in common.HOST_MAP:
                hostname = common.HOST_MAP[fetchhost]
                fetchhost_iplist = sum([socket.gethostbyname_ex(x)[-1] for x in common.IPLIST_MAP.get(hostname) or hostname.split('|')], [])
            else:
                fetchhost_iplist = self.gethostbyname2(fetchhost)
            if len(fetchhost_iplist) == 0:
                logging.error('resolve %r domain return empty! please use ip list to replace domain list!', fetchhost)
                sys.exit(-1)
            self.dns_cache[fetchhost] = list(set(fetchhost_iplist))
            logging.info('resolve common.PHP_FETCHSERVER domain to iplist=%r', fetchhost_iplist)
        return True


class ProxyChainMixin:
    """proxy chain mixin"""

    def gethostbyname2(self, hostname):
        try:
            return socket.gethostbyname_ex(hostname)[-1]
        except socket.error:
            return [hostname]

    def create_tcp_connection(self, hostname, port, timeout, **kwargs):
        sock = socket.create_connection((common.PROXY_HOST, int(common.PROXY_PORT)))
        if hostname.endswith('.appspot.com'):
            hostname = 'www.google.com'
        request_data = 'CONNECT %s:%s HTTP/1.1\r\n' % (hostname, port)
        if common.PROXY_USERNAME and common.PROXY_PASSWROD:
            request_data += 'Proxy-Authorization: Basic %s\r\n' % base64.b64encode(('%s:%s' % (common.PROXY_USERNAME, common.PROXY_PASSWROD)).encode()).decode().strip()
        request_data += '\r\n'
        sock.sendall(request_data)
        response = httplib.HTTPResponse(sock)
        response.fp.close()
        response.fp = sock.makefile('rb', 0)
        response.begin()
        if response.status >= 400:
            raise httplib.BadStatusLine('%s %s %s' % (response.version, response.status, response.reason))
        return sock

    def create_ssl_connection(self, hostname, port, timeout, **kwargs):
        sock = self.create_tcp_connection(hostname, port, timeout, **kwargs)
        ssl_sock = ssl.wrap_socket(sock)
        return ssl_sock


class GreenForwardMixin:
    """green forward mixin"""

    @staticmethod
    def io_copy(dest, source, timeout, bufsize):
        try:
            dest.settimeout(timeout)
            source.settimeout(timeout)
            while 1:
                data = source.recv(bufsize)
                if not data:
                    break
                dest.sendall(data)
        except socket.timeout:
            pass
        except NetWorkIOError as e:
            if e.args[0] not in (errno.ECONNABORTED, errno.ECONNRESET, errno.ENOTCONN, errno.EPIPE):
                raise
            if e.args[0] in (errno.EBADF,):
                return
        finally:
            for sock in (dest, source):
                try:
                    sock.close()
                except StandardError:
                    pass

    def forward_socket(self, local, remote, timeout):
        """forward socket"""
        bufsize = self.bufsize
        thread.start_new_thread(GreenForwardMixin.io_copy, (remote.dup(), local.dup(), timeout, bufsize))
        GreenForwardMixin.io_copy(local, remote, timeout, bufsize)


class ProxyChainGAEProxyHandler(ProxyChainMixin, GAEProxyHandler):
    pass


class ProxyChainPHPProxyHandler(ProxyChainMixin, PHPProxyHandler):
    pass


class GreenForwardGAEProxyHandler(GreenForwardMixin, GAEProxyHandler):
    pass


class GreenForwardPHPProxyHandler(GreenForwardMixin, PHPProxyHandler):
    pass


class ProxyChainGreenForwardGAEProxyHandler(ProxyChainMixin, GreenForwardGAEProxyHandler):
    pass


class ProxyChainGreenForwardPHPProxyHandler(ProxyChainMixin, GreenForwardPHPProxyHandler):
    pass


def get_uptime():
    if os.name == 'nt':
        import ctypes
        try:
            tick = ctypes.windll.kernel32.GetTickCount64()
        except AttributeError:
            tick = ctypes.windll.kernel32.GetTickCount()
        return tick / 1000.0
    elif os.path.isfile('/proc/uptime'):
        with open('/proc/uptime', 'rb') as fp:
            uptime = fp.readline().strip().split()[0].strip()
            return float(uptime)
    elif any(os.path.isfile(os.path.join(x, 'uptime')) for x in os.environ['PATH'].split(os.pathsep)):
        # http://www.opensource.apple.com/source/lldb/lldb-69/test/pexpect-2.4/examples/uptime.py
        pattern = r'up\s+(.*?),\s+([0-9]+) users?,\s+load averages?: ([0-9]+\.[0-9][0-9]),?\s+([0-9]+\.[0-9][0-9]),?\s+([0-9]+\.[0-9][0-9])'
        output = os.popen('uptime').read()
        duration, _, _, _, _ = re.search(pattern, output).groups()
        days, hours, mins = 0, 0, 0
        if 'day' in duration:
            m = re.search(r'([0-9]+)\s+day', duration)
            days = int(m.group(1))
        if ':' in duration:
            m = re.search(r'([0-9]+):([0-9]+)', duration)
            hours = int(m.group(1))
            mins = int(m.group(2))
        if 'min' in duration:
            m = re.search(r'([0-9]+)\s+min', duration)
            mins = int(m.group(1))
        return days * 86400 + hours * 3600 + mins * 60
    else:
        #TODO: support other platforms
        return None


class PacUtil(object):
    """GoAgent Pac Util"""

    @staticmethod
    def update_pacfile(filename):
        listen_ip = '127.0.0.1'
        autoproxy = '%s:%s' % (listen_ip, common.LISTEN_PORT)
        blackhole = '%s:%s' % (listen_ip, common.PAC_PORT)
        default = 'PROXY %s:%s' % (common.PROXY_HOST, common.PROXY_PORT) if common.PROXY_ENABLE else 'DIRECT'
        opener = urllib2.build_opener(urllib2.ProxyHandler({'http': autoproxy, 'https': autoproxy}))
        content = ''
        need_update = True
        with open(filename, 'rb') as fp:
            content = fp.read()
        try:
            placeholder = '// AUTO-GENERATED RULES, DO NOT MODIFY!'
            content = content[:content.index(placeholder)+len(placeholder)]
            content = re.sub(r'''blackhole\s*=\s*['"]PROXY [\.\w:]+['"]''', 'blackhole = \'PROXY %s\'' % blackhole, content)
            content = re.sub(r'''autoproxy\s*=\s*['"]PROXY [\.\w:]+['"]''', 'autoproxy = \'PROXY %s\'' % autoproxy, content)
            content = re.sub(r'''defaultproxy\s*=\s*['"](DIRECT|PROXY [\.\w:]+)['"]''', 'defaultproxy = \'%s\'' % default, content)
            content = re.sub(r'''host\s*==\s*['"][\.\w:]+['"]\s*\|\|\s*isPlainHostName''', 'host == \'%s\' || isPlainHostName' % listen_ip, content)
            if content.startswith('//'):
                line = '// Proxy Auto-Config file generated by autoproxy2pac, %s\r\n' % time.strftime('%Y-%m-%d %H:%M:%S')
                content = line + '\r\n'.join(content.splitlines()[1:])
        except ValueError:
            need_update = False
        try:
            if common.PAC_ADBLOCK:
                admode = common.PAC_ADMODE
                logging.info('try download %r to update_pacfile(%r)', common.PAC_ADBLOCK, filename)
                adblock_content = opener.open(common.PAC_ADBLOCK).read()
                logging.info('%r downloaded, try convert it with adblock2pac', common.PAC_ADBLOCK)
                if 'gevent' in sys.modules and time.sleep is getattr(sys.modules['gevent'], 'sleep', None) and hasattr(gevent.get_hub(), 'threadpool'):
                    jsrule = gevent.get_hub().threadpool.apply_e(Exception, PacUtil.adblock2pac, (adblock_content, 'FindProxyForURLByAdblock', blackhole, default, admode))
                else:
                    jsrule = PacUtil.adblock2pac(adblock_content, 'FindProxyForURLByAdblock', blackhole, default, admode)
                content += '\r\n' + jsrule + '\r\n'
                logging.info('%r downloaded and parsed', common.PAC_ADBLOCK)
            else:
                content += '\r\nfunction FindProxyForURLByAdblock(url, host) {return "DIRECT";}\r\n'
        except StandardError as e:
            need_update = False
            logging.exception('update_pacfile failed: %r', e)
        try:
            logging.info('try download %r to update_pacfile(%r)', common.PAC_GFWLIST, filename)
            autoproxy_content = base64.b64decode(opener.open(common.PAC_GFWLIST).read())
            logging.info('%r downloaded, try convert it with autoproxy2pac_lite', common.PAC_GFWLIST)
            if 'gevent' in sys.modules and time.sleep is getattr(sys.modules['gevent'], 'sleep', None) and hasattr(gevent.get_hub(), 'threadpool'):
                jsrule = gevent.get_hub().threadpool.apply_e(Exception, PacUtil.autoproxy2pac_lite, (autoproxy_content, 'FindProxyForURLByAutoProxy', autoproxy, default))
            else:
                jsrule = PacUtil.autoproxy2pac_lite(autoproxy_content, 'FindProxyForURLByAutoProxy', autoproxy, default)
            content += '\r\n' + jsrule + '\r\n'
            logging.info('%r downloaded and parsed', common.PAC_GFWLIST)
        except StandardError as e:
            need_update = False
            logging.exception('update_pacfile failed: %r', e)
        if need_update:
            with open(filename, 'wb') as fp:
                fp.write(content)
            logging.info('%r successfully updated', filename)

    @staticmethod
    def autoproxy2pac(content, func_name='FindProxyForURLByAutoProxy', proxy='127.0.0.1:8087', default='DIRECT', indent=4):
        """Autoproxy to Pac, based on https://github.com/iamamac/autoproxy2pac"""
        jsLines = []
        for line in content.splitlines()[1:]:
            if line and not line.startswith("!"):
                use_proxy = True
                if line.startswith("@@"):
                    line = line[2:]
                    use_proxy = False
                return_proxy = 'PROXY %s' % proxy if use_proxy else default
                if line.startswith('/') and line.endswith('/'):
                    jsLine = 'if (/%s/i.test(url)) return "%s";' % (line[1:-1], return_proxy)
                elif line.startswith('||'):
                    domain = line[2:].lstrip('.')
                    if len(jsLines) > 0 and ('host.indexOf(".%s") >= 0' % domain in jsLines[-1] or 'host.indexOf("%s") >= 0' % domain in jsLines[-1]):
                        jsLines.pop()
                    jsLine = 'if (dnsDomainIs(host, ".%s") || host == "%s") return "%s";' % (domain, domain, return_proxy)
                elif line.startswith('|'):
                    jsLine = 'if (url.indexOf("%s") == 0) return "%s";' % (line[1:], return_proxy)
                elif '*' in line:
                    jsLine = 'if (shExpMatch(url, "*%s*")) return "%s";' % (line.strip('*'), return_proxy)
                elif '/' not in line:
                    jsLine = 'if (host.indexOf("%s") >= 0) return "%s";' % (line, return_proxy)
                else:
                    jsLine = 'if (url.indexOf("%s") >= 0) return "%s";' % (line, return_proxy)
                jsLine = ' ' * indent + jsLine
                if use_proxy:
                    jsLines.append(jsLine)
                else:
                    jsLines.insert(0, jsLine)
        function = 'function %s(url, host) {\r\n%s\r\n%sreturn "%s";\r\n}' % (func_name, '\n'.join(jsLines), ' '*indent, default)
        return function

    @staticmethod
    def autoproxy2pac_lite(content, func_name='FindProxyForURLByAutoProxy', proxy='127.0.0.1:8087', default='DIRECT', indent=4):
        """Autoproxy to Pac, based on https://github.com/iamamac/autoproxy2pac"""
        direct_domain_set = set([])
        proxy_domain_set = set([])
        for line in content.splitlines()[1:]:
            if line and not line.startswith(('!', '|!', '||!')):
                use_proxy = True
                if line.startswith("@@"):
                    line = line[2:]
                    use_proxy = False
                domain = ''
                if line.startswith('/') and line.endswith('/'):
                    line = line[1:-1]
                    if line.startswith('^https?:\\/\\/[^\\/]+') and re.match(r'^(\w|\\\-|\\\.)+$', line[18:]):
                        domain = line[18:].replace(r'\.', '.')
                    else:
                        logging.warning('unsupport gfwlist regex: %r', line)
                elif line.startswith('||'):
                    domain = line[2:].lstrip('*').rstrip('/')
                elif line.startswith('|'):
                    domain = urlparse.urlsplit(line[1:]).netloc.lstrip('*')
                elif line.startswith(('http://', 'https://')):
                    domain = urlparse.urlsplit(line).netloc.lstrip('*')
                elif re.search(r'^([\w\-\_\.]+)([\*\/]|$)', line):
                    domain = re.split(r'[\*\/]', line)[0]
                else:
                    pass
                if '*' in domain:
                    domain = domain.split('*')[-1]
                if not domain or re.match(r'^\w+$', domain):
                    logging.debug('unsupport gfwlist rule: %r', line)
                    continue
                if use_proxy:
                    proxy_domain_set.add(domain)
                else:
                    direct_domain_set.add(domain)
        proxy_domain_list = sorted(set(x.lstrip('.') for x in proxy_domain_set))
        autoproxy_host = ',\r\n'.join('%s"%s": 1' % (' '*indent, x) for x in proxy_domain_list)
        template = '''\
                    var autoproxy_host = {
                    %(autoproxy_host)s
                    };
                    function %(func_name)s(url, host) {
                        var lastPos;
                        do {
                            if (autoproxy_host.hasOwnProperty(host)) {
                                return 'PROXY %(proxy)s';
                            }
                            lastPos = host.indexOf('.') + 1;
                            host = host.slice(lastPos);
                        } while (lastPos >= 1);
                        return '%(default)s';
                    }'''
        template = re.sub(r'(?m)^\s{%d}' % min(len(re.search(r' +', x).group()) for x in template.splitlines()), '', template)
        template_args = {'autoproxy_host': autoproxy_host,
                         'func_name': func_name,
                         'proxy': proxy,
                         'default': default}
        return template % template_args

    @staticmethod
    def urlfilter2pac(content, func_name='FindProxyForURLByUrlfilter', proxy='127.0.0.1:8086', default='DIRECT', indent=4):
        """urlfilter.ini to Pac, based on https://github.com/iamamac/autoproxy2pac"""
        jsLines = []
        for line in content[content.index('[exclude]'):].splitlines()[1:]:
            if line and not line.startswith(';'):
                use_proxy = True
                if line.startswith("@@"):
                    line = line[2:]
                    use_proxy = False
                return_proxy = 'PROXY %s' % proxy if use_proxy else default
                if '*' in line:
                    jsLine = 'if (shExpMatch(url, "%s")) return "%s";' % (line, return_proxy)
                else:
                    jsLine = 'if (url == "%s") return "%s";' % (line, return_proxy)
                jsLine = ' ' * indent + jsLine
                if use_proxy:
                    jsLines.append(jsLine)
                else:
                    jsLines.insert(0, jsLine)
        function = 'function %s(url, host) {\r\n%s\r\n%sreturn "%s";\r\n}' % (func_name, '\n'.join(jsLines), ' '*indent, default)
        return function

    @staticmethod
    def adblock2pac(content, func_name='FindProxyForURLByAdblock', proxy='127.0.0.1:8086', default='DIRECT', admode=1, indent=4):
        """adblock list to Pac, based on https://github.com/iamamac/autoproxy2pac"""
        white_conditions = {'host': [], 'url.indexOf': [], 'shExpMatch': []}
        black_conditions = {'host': [], 'url.indexOf': [], 'shExpMatch': []}
        for line in content.splitlines()[1:]:
            if not line or line.startswith('!') or '##' in line or '#@#' in line:
                continue
            use_proxy = True
            use_start = False
            use_end = False
            use_domain = False
            use_postfix = []
            if '$' in line:
                posfixs = line.split('$')[-1].split(',')
                if any('domain' in x for x in posfixs):
                    continue
                if 'image' in posfixs:
                    use_postfix += ['.jpg', '.gif']
                elif 'script' in posfixs:
                    use_postfix += ['.js']
                else:
                    continue
            line = line.split('$')[0]
            if line.startswith("@@"):
                line = line[2:]
                use_proxy = False
            if '||' == line[:2]:
                line = line[2:]
                if '/' not in line:
                    use_domain = True
                else:
                    use_start = True
            elif '|' == line[0]:
                line = line[1:]
                use_start = True
            if line[-1] in ('^', '|'):
                line = line[:-1]
                if not use_postfix:
                    use_end = True
            line = line.replace('^', '*').strip('*')
            conditions = black_conditions if use_proxy else white_conditions
            if use_start and use_end:
                conditions['shExpMatch'] += ['*%s*' % line]
            elif use_start:
                if '*' in line:
                    if use_postfix:
                        conditions['shExpMatch'] += ['*%s*%s' % (line, x) for x in use_postfix]
                    else:
                        conditions['shExpMatch'] += ['*%s*' % line]
                else:
                    conditions['url.indexOf'] += [line]
            elif use_domain and use_end:
                if '*' in line:
                    conditions['shExpMatch'] += ['%s*' % line]
                else:
                    conditions['host'] += [line]
            elif use_domain:
                if line.split('/')[0].count('.') <= 1:
                    if use_postfix:
                        conditions['shExpMatch'] += ['*.%s*%s' % (line, x) for x in use_postfix]
                    else:
                        conditions['shExpMatch'] += ['*.%s*' % line]
                else:
                    if '*' in line:
                        if use_postfix:
                            conditions['shExpMatch'] += ['*%s*%s' % (line, x) for x in use_postfix]
                        else:
                            conditions['shExpMatch'] += ['*%s*' % line]
                    else:
                        if use_postfix:
                            conditions['shExpMatch'] += ['*%s*%s' % (line, x) for x in use_postfix]
                        else:
                            conditions['url.indexOf'] += ['http://%s' % line]
            else:
                if use_postfix:
                    conditions['shExpMatch'] += ['*%s*%s' % (line, x) for x in use_postfix]
                else:
                    conditions['shExpMatch'] += ['*%s*' % line]
        templates = ['''\
                    function %(func_name)s(url, host) {
                        return '%(default)s';
                    }''',
                    '''\
                    var blackhole_host = {
                    %(blackhole_host)s
                    };
                    function %(func_name)s(url, host) {
                        // untrusted ablock plus list, disable whitelist until chinalist come back.
                        if (blackhole_host.hasOwnProperty(host)) {
                            return 'PROXY %(proxy)s';
                        }
                        return '%(default)s';
                    }''',
                    '''\
                    var blackhole_host = {
                    %(blackhole_host)s
                    };
                    var blackhole_url_indexOf = [
                    %(blackhole_url_indexOf)s
                    ];
                    function %s(url, host) {
                        // untrusted ablock plus list, disable whitelist until chinalist come back.
                        if (blackhole_host.hasOwnProperty(host)) {
                            return 'PROXY %(proxy)s';
                        }
                        for (i = 0; i < blackhole_url_indexOf.length; i++) {
                            if (url.indexOf(blackhole_url_indexOf[i]) >= 0) {
                                return 'PROXY %(proxy)s';
                            }
                        }
                        return '%(default)s';
                    }''',
                    '''\
                    var blackhole_host = {
                    %(blackhole_host)s
                    };
                    var blackhole_url_indexOf = [
                    %(blackhole_url_indexOf)s
                    ];
                    var blackhole_shExpMatch = [
                    %(blackhole_shExpMatch)s
                    ];
                    function %(func_name)s(url, host) {
                        // untrusted ablock plus list, disable whitelist until chinalist come back.
                        if (blackhole_host.hasOwnProperty(host)) {
                            return 'PROXY %(proxy)s';
                        }
                        for (i = 0; i < blackhole_url_indexOf.length; i++) {
                            if (url.indexOf(blackhole_url_indexOf[i]) >= 0) {
                                return 'PROXY %(proxy)s';
                            }
                        }
                        for (i = 0; i < blackhole_shExpMatch.length; i++) {
                            if (shExpMatch(url, blackhole_shExpMatch[i])) {
                                return 'PROXY %(proxy)s';
                            }
                        }
                        return '%(default)s';
                    }''']
        template = re.sub(r'(?m)^\s{%d}' % min(len(re.search(r' +', x).group()) for x in templates[admode].splitlines()), '', templates[admode])
        template_kwargs = {'blackhole_host': ',\r\n'.join("%s'%s': 1" % (' '*indent, x) for x in sorted(black_conditions['host'])),
                           'blackhole_url_indexOf': ',\r\n'.join("%s'%s'" % (' '*indent, x) for x in sorted(black_conditions['url.indexOf'])),
                           'blackhole_shExpMatch': ',\r\n'.join("%s'%s'" % (' '*indent, x) for x in sorted(black_conditions['shExpMatch'])),
                           'func_name': func_name,
                           'proxy': proxy,
                           'default': default}
        return template % template_kwargs


class PacFileFilter(BaseProxyHandlerFilter):
    """pac file filter"""

    def filter(self, handler):
        is_local_client = handler.client_address[0] in ('127.0.0.1', '::1')
        pacfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), common.PAC_FILE)
        urlparts = urlparse.urlsplit(handler.path)
        if handler.command == 'GET' and urlparts.path.lstrip('/') == common.PAC_FILE:
            if urlparts.query == 'flush':
                if is_local_client:
                    thread.start_new_thread(PacUtil.update_pacfile, (pacfile,))
                else:
                    return [handler.MOCK, 403, {'Content-Type': 'text/plain'}, 'client address %r not allowed' % handler.client_address[0]]
            if time.time() - os.path.getmtime(pacfile) > common.PAC_EXPIRED:
                # check system uptime > 30 minutes
                uptime = get_uptime()
                if uptime and uptime > 1800:
                    thread.start_new_thread(lambda: os.utime(pacfile, (time.time(), time.time())) or PacUtil.update_pacfile(pacfile), tuple())
            with open(pacfile, 'rb') as fp:
                content = fp.read()
                if not is_local_client:
                    listen_ip = ProxyUtil.get_listen_ip()
                    content = content.replace('127.0.0.1', listen_ip)
                headers = {'Content-Type': 'text/plain'}
                if 'gzip' in handler.headers.get('Accept-Encoding', ''):
                    headers['Content-Encoding'] = 'gzip'
                    compressobj = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION, zlib.DEFLATED, -zlib.MAX_WBITS, zlib.DEF_MEM_LEVEL, 0)
                    dataio = io.BytesIO()
                    dataio.write('\x1f\x8b\x08\x00\x00\x00\x00\x00\x02\xff')
                    dataio.write(compressobj.compress(content))
                    dataio.write(compressobj.flush())
                    dataio.write(struct.pack('<LL', zlib.crc32(content) & 0xFFFFFFFFL, len(content) & 0xFFFFFFFFL))
                    content = dataio.getvalue()
                return [handler.MOCK, 200, headers, content]


class StaticFileFilter(BaseProxyHandlerFilter):
    """static file filter"""
    index_file = 'index.html'

    def format_index_html(self, dirname):
        INDEX_TEMPLATE = u'''
        <html>
        <title>Directory listing for $dirname</title>
        <body>
        <h2>Directory listing for $dirname</h2>
        <hr>
        <ul>
        $html
        </ul>
        <hr>
        </body></html>
        '''
        html = ''
        if not isinstance(dirname, unicode):
            dirname = dirname.decode(sys.getfilesystemencoding())
        for name in os.listdir(dirname):
            fullname = os.path.join(dirname, name)
            suffix = u'/' if os.path.isdir(fullname) else u''
            html += u'<li><a href="%s%s">%s%s</a>\r\n' % (name, suffix, name, suffix)
        return string.Template(INDEX_TEMPLATE).substitute(dirname=dirname, html=html)

    def filter(self, handler):
        path = urlparse.urlsplit(handler.path).path
        if path.startswith('/'):
            path = urllib.unquote_plus(path.lstrip('/') or '.').decode('utf8')
            if os.path.isdir(path):
                index_file = os.path.join(path, self.index_file)
                if not os.path.isfile(index_file):
                    content = self.format_index_html(path).encode('UTF-8')
                    headers = {'Content-Type': 'text/html; charset=utf-8', 'Connection': 'close'}
                    return [handler.MOCK, 200, headers, content]
                else:
                    path = index_file
            if os.path.isfile(path):
                content_type = 'application/octet-stream'
                try:
                    import mimetypes
                    content_type = mimetypes.types_map.get(os.path.splitext(path)[1])
                except StandardError as e:
                    logging.error('import mimetypes failed: %r', e)
                with open(path, 'rb') as fp:
                    content = fp.read()
                    headers = {'Connection': 'close', 'Content-Type': content_type}
                    return [handler.MOCK, 200, headers, content]


class BlackholeFilter(BaseProxyHandlerFilter):
    """blackhole filter"""
    one_pixel_gif = 'GIF89a\x01\x00\x01\x00\x80\xff\x00\xc0\xc0\xc0\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'

    def filter(self, handler):
        if handler.command == 'CONNECT':
            return [handler.STRIP, True, self]
        elif handler.path.startswith(('http://', 'https://')):
            headers = {'Cache-Control': 'max-age=86400',
                       'Expires': 'Oct, 01 Aug 2100 00:00:00 GMT',
                       'Connection': 'close'}
            content = ''
            if urlparse.urlsplit(handler.path).path.lower().endswith(('.jpg', '.gif', '.png','.jpeg', '.bmp')):
                headers['Content-Type'] = 'image/gif'
                content = self.one_pixel_gif
            return [handler.MOCK, 200, headers, content]
        else:
            return [handler.MOCK, 404, {'Connection': 'close'}, '']


class PACProxyHandler(SimpleProxyHandler):
    """pac proxy handler"""
    handler_filters = [PacFileFilter(), StaticFileFilter(), BlackholeFilter()]


def get_process_list():
    import os
    import glob
    import ctypes
    import collections
    Process = collections.namedtuple('Process', 'pid name exe')
    process_list = []
    if os.name == 'nt':
        PROCESS_QUERY_INFORMATION = 0x0400
        PROCESS_VM_READ = 0x0010
        lpidProcess = (ctypes.c_ulong * 1024)()
        cb = ctypes.sizeof(lpidProcess)
        cbNeeded = ctypes.c_ulong()
        ctypes.windll.psapi.EnumProcesses(ctypes.byref(lpidProcess), cb, ctypes.byref(cbNeeded))
        nReturned = cbNeeded.value/ctypes.sizeof(ctypes.c_ulong())
        pidProcess = [i for i in lpidProcess][:nReturned]
        has_queryimage = hasattr(ctypes.windll.kernel32, 'QueryFullProcessImageNameA')
        for pid in pidProcess:
            hProcess = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, 0, pid)
            if hProcess:
                modname = ctypes.create_string_buffer(2048)
                count = ctypes.c_ulong(ctypes.sizeof(modname))
                if has_queryimage:
                    ctypes.windll.kernel32.QueryFullProcessImageNameA(hProcess, 0, ctypes.byref(modname), ctypes.byref(count))
                else:
                    ctypes.windll.psapi.GetModuleFileNameExA(hProcess, 0, ctypes.byref(modname), ctypes.byref(count))
                exe = modname.value
                name = os.path.basename(exe)
                process_list.append(Process(pid=pid, name=name, exe=exe))
                ctypes.windll.kernel32.CloseHandle(hProcess)
    elif sys.platform.startswith('linux'):
        for filename in glob.glob('/proc/[0-9]*/cmdline'):
            pid = int(filename.split('/')[2])
            exe_link = '/proc/%d/exe' % pid
            if os.path.exists(exe_link):
                exe = os.readlink(exe_link)
                name = os.path.basename(exe)
                process_list.append(Process(pid=pid, name=name, exe=exe))
    else:
        try:
            import psutil
            process_list = psutil.get_process_list()
        except StandardError as e:
            logging.exception('psutil.get_process_list() failed: %r', e)
    return process_list

def pre_start():
    if sys.platform == 'cygwin':
        logging.info('cygwin is not officially supported, please continue at your own risk :)')
        #sys.exit(-1)
    elif os.name == 'posix':
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_NOFILE, (8192, -1))
        except ValueError:
            pass
    elif os.name == 'nt':
        import ctypes
        ctypes.windll.kernel32.SetConsoleTitleW(u'GoAgent v%s' % __version__)
        if not common.LISTEN_VISIBLE:
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
        else:
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 1)
        if common.LOVE_ENABLE and random.randint(1, 100) <= 5:
            title = ctypes.create_unicode_buffer(1024)
            ctypes.windll.kernel32.GetConsoleTitleW(ctypes.byref(title), len(title)-1)
            ctypes.windll.kernel32.SetConsoleTitleW('%s %s' % (title.value, random.choice(common.LOVE_TIP)))
        blacklist = {'360safe': False,
                     'QQProtect': False, }
        softwares = [k for k, v in blacklist.items() if v]
        if softwares:
            tasklist = '\n'.join(x.name for x in get_process_list()).lower()
            softwares = [x for x in softwares if x.lower() in tasklist]
            if softwares:
                title = u'GoAgent 建议'
                error = u'某些安全软件(如 %s)可能和本软件存在冲突，造成 CPU 占用过高。\n如有此现象建议暂时退出此安全软件来继续运行GoAgent' % ','.join(softwares)
                ctypes.windll.user32.MessageBoxW(None, error, title, 0)
                #sys.exit(0)
    if os.path.isfile('/proc/cpuinfo'):
        with open('/proc/cpuinfo', 'rb') as fp:
            m = re.search(r'(?im)(BogoMIPS|cpu MHz)\s+:\s+([\d\.]+)', fp.read())
            if m and float(m.group(2)) < 1000:
                logging.warning("*NOTE*, Please set [gae]window=2 [gae]keepalive=1")
    if GAEProxyHandler.max_window != common.GAE_WINDOW:
        GAEProxyHandler.max_window = common.GAE_WINDOW
    if common.GAE_KEEPALIVE and common.GAE_MODE == 'https':
        GAEProxyHandler.ssl_connection_keepalive = True
    if common.GAE_SSLVERSION:
        GAEProxyHandler.ssl_version = getattr(ssl, 'PROTOCOL_%s' % common.GAE_SSLVERSION)
    if common.GAE_APPIDS[0] == 'goagent':
        logging.critical('please edit %s to add your appid to [gae] !', common.CONFIG_FILENAME)
        sys.exit(-1)
    if common.GAE_MODE == 'http' and common.GAE_PASSWORD == '':
        logging.critical('to enable http mode, you should set %r [gae]password = <your_pass> and [gae]options = rc4', common.CONFIG_FILENAME)
        sys.exit(-1)
    if common.GAE_TRANSPORT:
        GAEProxyHandler.disable_transport_ssl = False
    if common.GAE_REGIONS and not pygeoip:
        logging.critical('to enable [gae]regions mode, you should install pygeoip')
        sys.exit(-1)
    if common.PAC_ENABLE:
        pac_ip = ProxyUtil.get_listen_ip() if common.PAC_IP in ('', '::', '0.0.0.0') else common.PAC_IP
        url = 'http://%s:%d/%s' % (pac_ip, common.PAC_PORT, common.PAC_FILE)
        spawn_later(600, urllib2.build_opener(urllib2.ProxyHandler({})).open, url)
    if not dnslib:
        logging.error('dnslib not found, please put dnslib-0.8.3.egg to %r!', os.path.dirname(os.path.abspath(__file__)))
        sys.exit(-1)
    if not common.DNS_ENABLE:
        if not common.HTTP_DNS:
            common.HTTP_DNS = common.DNS_SERVERS[:]
        for dnsservers_ref in (common.HTTP_DNS, common.DNS_SERVERS):
            any(dnsservers_ref.insert(0, x) for x in [y for y in get_dnsserver_list() if y not in dnsservers_ref])
        AdvancedProxyHandler.dns_servers = common.HTTP_DNS
        AdvancedProxyHandler.dns_blacklist = common.DNS_BLACKLIST
    else:
        AdvancedProxyHandler.dns_servers = common.HTTP_DNS or common.DNS_SERVERS
        AdvancedProxyHandler.dns_blacklist = common.DNS_BLACKLIST
    if not OpenSSL:
        logging.warning('python-openssl not found, please install it!')
    RangeFetch.threads = common.AUTORANGE_THREADS
    RangeFetch.maxsize = common.AUTORANGE_MAXSIZE
    RangeFetch.bufsize = common.AUTORANGE_BUFSIZE
    RangeFetch.waitsize = common.AUTORANGE_WAITSIZE
    if common.LISTEN_USERNAME and common.LISTEN_PASSWORD:
        GAEProxyHandler.handler_filters.insert(0, AuthFilter(common.LISTEN_USERNAME, common.LISTEN_PASSWORD))


def main():
    global __file__
    __file__ = os.path.abspath(__file__)
    if os.path.islink(__file__):
        __file__ = getattr(os, 'readlink', lambda x: x)(__file__)
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    logging.basicConfig(level=logging.DEBUG if common.LISTEN_DEBUGINFO else logging.INFO, format='%(levelname)s - %(asctime)s %(message)s', datefmt='[%b %d %H:%M:%S]')
    pre_start()
    CertUtil.check_ca()
    sys.stderr.write(common.info())

    uvent_enabled = 'uvent.loop' in sys.modules and isinstance(gevent.get_hub().loop, __import__('uvent').loop.UVLoop)

    if common.PHP_ENABLE:
        host, port = common.PHP_LISTEN.split(':')
        HandlerClass = ((PHPProxyHandler, GreenForwardPHPProxyHandler) if not common.PROXY_ENABLE else (ProxyChainPHPProxyHandler, ProxyChainGreenForwardPHPProxyHandler))[uvent_enabled]
        server = LocalProxyServer((host, int(port)), HandlerClass)
        thread.start_new_thread(server.serve_forever, tuple())

    if common.PAC_ENABLE:
        server = LocalProxyServer((common.PAC_IP, common.PAC_PORT), PACProxyHandler)
        thread.start_new_thread(server.serve_forever, tuple())

    if common.DNS_ENABLE:
        try:
            sys.path += ['.']
            from dnsproxy import DNSServer
            host, port = common.DNS_LISTEN.split(':')
            server = DNSServer((host, int(port)), dns_servers=common.DNS_SERVERS, dns_blacklist=common.DNS_BLACKLIST, dns_tcpover=common.DNS_TCPOVER)
            thread.start_new_thread(server.serve_forever, tuple())
        except ImportError:
            logging.exception('GoAgent DNSServer requires dnslib and gevent 1.0')
            sys.exit(-1)

    HandlerClass = ((GAEProxyHandler, GreenForwardGAEProxyHandler) if not common.PROXY_ENABLE else (ProxyChainGAEProxyHandler, ProxyChainGreenForwardGAEProxyHandler))[uvent_enabled]
    server = LocalProxyServer((common.LISTEN_IP, common.LISTEN_PORT), HandlerClass)
    try:
        server.serve_forever()
    except SystemError as e:
        if '(libev) select: ' in repr(e):
            logging.error('PLEASE START GOAGENT BY uvent.bat')
            sys.exit(-1)

if __name__ == '__main__':
    main()

########NEW FILE########
__FILENAME__ = gae
#!/usr/bin/env python
# coding:utf-8

__version__ = '3.1.11'
__password__ = ''
__hostsdeny__ = ()  # __hostsdeny__ = ('.youtube.com', '.youku.com')
__content_type__ = 'image/gif'
__mirror_userjs__ = ()  # __mirror_userjs__ = '//www.example.com/user.js'

import os
import re
import time
import struct
import zlib
import base64
import logging
import urlparse
import io
import string

from google.appengine.api import urlfetch
from google.appengine.api.taskqueue.taskqueue import MAX_URL_LENGTH
from google.appengine.runtime import apiproxy_errors

URLFETCH_MAX = 2
URLFETCH_MAXSIZE = 4*1024*1024
URLFETCH_DEFLATE_MAXSIZE = 4*1024*1024
URLFETCH_TIMEOUT = 60

def message_html(title, banner, detail=''):
    MESSAGE_TEMPLATE = '''
    <html><head>
    <meta http-equiv="content-type" content="text/html;charset=utf-8">
    <title>$title</title>
    <style><!--
    body {font-family: arial,sans-serif}
    div.nav {margin-top: 1ex}
    div.nav A {font-size: 10pt; font-family: arial,sans-serif}
    span.nav {font-size: 10pt; font-family: arial,sans-serif; font-weight: bold}
    div.nav A,span.big {font-size: 12pt; color: #0000cc}
    div.nav A {font-size: 10pt; color: black}
    A.l:link {color: #6f6f6f}
    A.u:link {color: green}
    //--></style>
    </head>
    <body text=#000000 bgcolor=#ffffff>
    <table border=0 cellpadding=2 cellspacing=0 width=100%>
    <tr><td bgcolor=#3366cc><font face=arial,sans-serif color=#ffffff><b>Message From FetchServer</b></td></tr>
    <tr><td> </td></tr></table>
    <blockquote>
    <H1>$banner</H1>
    $detail
    <p>
    </blockquote>
    <table width=100% cellpadding=0 cellspacing=0><tr><td bgcolor=#3366cc><img alt="" width=1 height=4></td></tr></table>
    </body></html>
    '''
    return string.Template(MESSAGE_TEMPLATE).substitute(title=title, banner=banner, detail=detail)


try:
    from Crypto.Cipher.ARC4 import new as RC4Cipher
except ImportError:
    logging.warn('Load Crypto.Cipher.ARC4 Failed, Use Pure Python Instead.')
    class RC4Cipher(object):
        def __init__(self, key):
            x = 0
            box = range(256)
            for i, y in enumerate(box):
                x = (x + y + ord(key[i % len(key)])) & 0xff
                box[i], box[x] = box[x], y
            self.__box = box
            self.__x = 0
            self.__y = 0
        def encrypt(self, data):
            out = []
            out_append = out.append
            x = self.__x
            y = self.__y
            box = self.__box
            for char in data:
                x = (x + 1) & 0xff
                y = (y + box[x]) & 0xff
                box[x], box[y] = box[y], box[x]
                out_append(chr(ord(char) ^ box[(box[x] + box[y]) & 0xff]))
            self.__x = x
            self.__y = y
            return ''.join(out)


def application(environ, start_response):
    cookie = environ.get('HTTP_COOKIE', '')
    options = environ.get('HTTP_X_GOA_OPTIONS', '')
    if environ['REQUEST_METHOD'] == 'GET' and not cookie:
        if '204' in environ['QUERY_STRING']:
            start_response('204 No Content', [])
            yield ''
        else:
            timestamp = long(os.environ['CURRENT_VERSION_ID'].split('.')[1])/2**28
            ctime = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(timestamp+8*3600))
            html = u'GoAgent Python Server %s \u5df2\u7ecf\u5728\u5de5\u4f5c\u4e86\uff0c\u90e8\u7f72\u65f6\u95f4 %s\n' % (__version__, ctime)
            start_response('200 OK', [('Content-Type', 'text/plain; charset=utf-8')])
            yield html.encode('utf8')
        raise StopIteration

    inflate = lambda x: zlib.decompress(x, -zlib.MAX_WBITS)
    deflate = lambda x: zlib.compress(x)[2:-4]
    rc4crypt = lambda s, k: RC4Cipher(k).encrypt(s) if k else s

    wsgi_input = environ['wsgi.input']
    input_data = wsgi_input.read()

    try:
        if cookie:
            if 'rc4' not in options:
                metadata = inflate(base64.b64decode(cookie))
                payload = input_data or ''
            else:
                metadata = inflate(rc4crypt(base64.b64decode(cookie), __password__))
                payload = rc4crypt(input_data, __password__) if input_data else ''
        else:
            if 'rc4' in options:
                input_data = rc4crypt(input_data, __password__)
            metadata_length, = struct.unpack('!h', input_data[:2])
            metadata = inflate(input_data[2:2+metadata_length])
            payload = input_data[2+metadata_length:]
        headers = dict(x.split(':', 1) for x in metadata.splitlines() if x)
        method = headers.pop('G-Method')
        url = headers.pop('G-Url')
    except (zlib.error, KeyError, ValueError):
        import traceback
        start_response('500 Internal Server Error', [('Content-Type', 'text/html')])
        yield message_html('500 Internal Server Error', 'Bad Request (metadata) - Possible Wrong Password', '<pre>%s</pre>' % traceback.format_exc())
        raise StopIteration

    kwargs = {}
    any(kwargs.__setitem__(x[2:].lower(), headers.pop(x)) for x in headers.keys() if x.startswith('G-'))

    if 'Content-Encoding' in headers:
        if headers['Content-Encoding'] == 'deflate':
            payload = inflate(payload)
            headers['Content-Length'] = str(len(payload))
            del headers['Content-Encoding']

    logging.info('%s "%s %s %s" - -', environ['REMOTE_ADDR'], method, url, 'HTTP/1.1')
    #logging.info('request headers=%s', headers)

    if __password__ and __password__ != kwargs.get('password', ''):
        start_response('403 Forbidden', [('Content-Type', 'text/html')])
        yield message_html('403 Wrong password', 'Wrong password(%r)' % kwargs.get('password', ''), 'GoAgent proxy.ini password is wrong!')
        raise StopIteration

    netloc = urlparse.urlparse(url).netloc

    if __hostsdeny__ and netloc.endswith(__hostsdeny__):
        start_response('403 Forbidden', [('Content-Type', 'text/html')])
        yield message_html('403 Hosts Deny', 'Hosts Deny(%r)' % netloc, detail='url=%r' % url)
        raise StopIteration

    if len(url) > MAX_URL_LENGTH:
        start_response('400 Bad Request', [('Content-Type', 'text/html')])
        yield message_html('400 Bad Request', 'length of URL too long(greater than %r)' % MAX_URL_LENGTH, detail='url=%r' % url)
        raise StopIteration

    if netloc.startswith(('127.0.0.', '::1', 'localhost')):
        start_response('400 Bad Request', [('Content-Type', 'text/html')])
        html = ''.join('<a href="https://%s/">%s</a><br/>' % (x, x) for x in ('google.com', 'mail.google.com'))
        yield message_html('GoAgent %s is Running' % __version__, 'Now you can visit some websites', html)
        raise StopIteration

    fetchmethod = getattr(urlfetch, method, None)
    if not fetchmethod:
        start_response('405 Method Not Allowed', [('Content-Type', 'text/html')])
        yield message_html('405 Method Not Allowed', 'Method Not Allowed: %r' % method, detail='Method Not Allowed URL=%r' % url)
        raise StopIteration

    deadline = URLFETCH_TIMEOUT
    validate_certificate = bool(int(kwargs.get('validate', 0)))
    # https://www.freebsdchina.org/forum/viewtopic.php?t=54269
    accept_encoding = headers.get('Accept-Encoding', '') or headers.get('Bccept-Encoding', '')
    errors = []
    for i in xrange(int(kwargs.get('fetchmax', URLFETCH_MAX))):
        try:
            response = urlfetch.fetch(url, payload, fetchmethod, headers, allow_truncated=False, follow_redirects=False, deadline=deadline, validate_certificate=validate_certificate)
            break
        except apiproxy_errors.OverQuotaError as e:
            time.sleep(5)
        except urlfetch.DeadlineExceededError as e:
            errors.append('%r, deadline=%s' % (e, deadline))
            logging.error('DeadlineExceededError(deadline=%s, url=%r)', deadline, url)
            time.sleep(1)
            deadline = URLFETCH_TIMEOUT * 2
        except urlfetch.DownloadError as e:
            errors.append('%r, deadline=%s' % (e, deadline))
            logging.error('DownloadError(deadline=%s, url=%r)', deadline, url)
            time.sleep(1)
            deadline = URLFETCH_TIMEOUT * 2
        except urlfetch.ResponseTooLargeError as e:
            errors.append('%r, deadline=%s' % (e, deadline))
            response = e.response
            logging.error('ResponseTooLargeError(deadline=%s, url=%r) response(%r)', deadline, url, response)
            m = re.search(r'=\s*(\d+)-', headers.get('Range') or headers.get('range') or '')
            if m is None:
                headers['Range'] = 'bytes=0-%d' % int(kwargs.get('fetchmaxsize', URLFETCH_MAXSIZE))
            else:
                headers.pop('Range', '')
                headers.pop('range', '')
                start = int(m.group(1))
                headers['Range'] = 'bytes=%s-%d' % (start, start+int(kwargs.get('fetchmaxsize', URLFETCH_MAXSIZE)))
            deadline = URLFETCH_TIMEOUT * 2
        except urlfetch.SSLCertificateError as e:
            errors.append('%r, should validate=0 ?' % e)
            logging.error('%r, deadline=%s', e, deadline)
        except Exception as e:
            errors.append(str(e))
            if i == 0 and method == 'GET':
                deadline = URLFETCH_TIMEOUT * 2
    else:
        start_response('500 Internal Server Error', [('Content-Type', 'text/html')])
        error_string = '<br />\n'.join(errors)
        if not error_string:
            logurl = 'https://appengine.google.com/logs?&app_id=%s' % os.environ['APPLICATION_ID']
            error_string = 'Internal Server Error. <p/>try <a href="javascript:window.location.reload(true);">refresh</a> or goto <a href="%s" target="_blank">appengine.google.com</a> for details' % logurl
        yield message_html('502 Urlfetch Error', 'Python Urlfetch Error: %r' % method,  error_string)
        raise StopIteration

    #logging.debug('url=%r response.status_code=%r response.headers=%r response.content[:1024]=%r', url, response.status_code, dict(response.headers), response.content[:1024])

    data = response.content
    response_headers = response.headers
    content_type = response_headers.get('content-type', '')
    if 'content-encoding' not in response_headers and 512 < len(response.content) < URLFETCH_DEFLATE_MAXSIZE and content_type.startswith(('text/', 'application/json', 'application/javascript')):
        if 'gzip' in accept_encoding:
            response_headers['Content-Encoding'] = 'gzip'
            compressobj = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION, zlib.DEFLATED, -zlib.MAX_WBITS, zlib.DEF_MEM_LEVEL, 0)
            dataio = io.BytesIO()
            dataio.write('\x1f\x8b\x08\x00\x00\x00\x00\x00\x02\xff')
            dataio.write(compressobj.compress(data))
            dataio.write(compressobj.flush())
            dataio.write(struct.pack('<LL', zlib.crc32(data) & 0xFFFFFFFFL, len(data) & 0xFFFFFFFFL))
            data = dataio.getvalue()
        elif 'deflate' in accept_encoding:
            response_headers['Content-Encoding'] = 'deflate'
            data = deflate(data)
    response_headers['Content-Length'] = str(len(data))
    response_headers_data = deflate('\n'.join('%s:%s' % (k.title(), v) for k, v in response_headers.items() if not k.startswith('x-google-')))
    if 'rc4' not in options or content_type.startswith(('audio/', 'image/', 'video/')):
        start_response('200 OK', [('Content-Type', __content_type__)])
        yield struct.pack('!hh', int(response.status_code), len(response_headers_data))+response_headers_data
        yield data
    else:
        start_response('200 OK', [('Content-Type', __content_type__), ('X-GOA-Options', 'rc4')])
        yield struct.pack('!hh', int(response.status_code), len(response_headers_data))
        yield rc4crypt(response_headers_data, __password__)
        yield rc4crypt(data, __password__)


class LegacyHandler(object):
    """GoAgent 1.x GAE Fetch Server"""
    @classmethod
    def application(cls, environ, start_response):
        return cls()(environ, start_response)

    def __call__(self, environ, start_response):
        self.environ = environ
        self.start_response = start_response
        return self.process_request()

    def send_response(self, status, headers, content, content_type=__content_type__):
        headers['Content-Length'] = str(len(content))
        strheaders = '&'.join('%s=%s' % (k, v.encode('hex')) for k, v in headers.iteritems() if v)
        #logging.debug('response status=%s, headers=%s, content length=%d', status, headers, len(content))
        if headers.get('content-type', '').startswith(('text/', 'application/json', 'application/javascript')):
            data = '1' + zlib.compress('%s%s%s' % (struct.pack('>3I', status, len(strheaders), len(content)), strheaders, content))
        else:
            data = '0%s%s%s' % (struct.pack('>3I', status, len(strheaders), len(content)), strheaders, content)
        self.start_response('200 OK', [('Content-type', content_type)])
        return [data]

    def send_notify(self, method, url, status, content):
        logging.warning('%r Failed: url=%r, status=%r', method, url, status)
        content = '<h2>Python Server Fetch Info</h2><hr noshade="noshade"><p>%s %r</p><p>Return Code: %d</p><p>Message: %s</p>' % (method, url, status, content)
        return self.send_response(status, {'content-type': 'text/html'}, content)

    def process_request(self):
        environ = self.environ
        if environ['REQUEST_METHOD'] == 'GET':
            redirect_url = 'https://%s/2' % environ['HTTP_HOST']
            self.start_response('302 Redirect', [('Location', redirect_url)])
            return [redirect_url]

        data = zlib.decompress(environ['wsgi.input'].read(int(environ['CONTENT_LENGTH'])))
        request = dict((k, v.decode('hex')) for k, _, v in (x.partition('=') for x in data.split('&')))

        method = request['method']
        url = request['url']
        payload = request['payload']

        if __password__ and __password__ != request.get('password', ''):
            return self.send_notify(method, url, 403, 'Wrong password.')

        if __hostsdeny__ and urlparse.urlparse(url).netloc.endswith(__hostsdeny__):
            return self.send_notify(method, url, 403, 'Hosts Deny: url=%r' % url)

        fetchmethod = getattr(urlfetch, method, '')
        if not fetchmethod:
            return self.send_notify(method, url, 501, 'Invalid Method')

        deadline = URLFETCH_TIMEOUT

        headers = dict((k.title(), v.lstrip()) for k, _, v in (line.partition(':') for line in request['headers'].splitlines()))
        headers['Connection'] = 'close'

        errors = []
        for _ in xrange(URLFETCH_MAX if 'fetchmax' not in request else int(request['fetchmax'])):
            try:
                response = urlfetch.fetch(url, payload, fetchmethod, headers, False, False, deadline, False)
                break
            except apiproxy_errors.OverQuotaError as e:
                time.sleep(4)
            except urlfetch.DeadlineExceededError as e:
                errors.append('DeadlineExceededError %s(deadline=%s)' % (e, deadline))
                logging.error('DeadlineExceededError(deadline=%s, url=%r)', deadline, url)
                time.sleep(1)
            except urlfetch.DownloadError as e:
                errors.append('DownloadError %s(deadline=%s)' % (e, deadline))
                logging.error('DownloadError(deadline=%s, url=%r)', deadline, url)
                time.sleep(1)
            except urlfetch.InvalidURLError as e:
                return self.send_notify(method, url, 501, 'Invalid URL: %s' % e)
            except urlfetch.ResponseTooLargeError as e:
                response = e.response
                logging.error('ResponseTooLargeError(deadline=%s, url=%r) response(%r)', deadline, url, response)
                m = re.search(r'=\s*(\d+)-', headers.get('Range') or headers.get('range') or '')
                if m is None:
                    headers['Range'] = 'bytes=0-%d' % URLFETCH_MAXSIZE
                else:
                    headers.pop('Range', '')
                    headers.pop('range', '')
                    start = int(m.group(1))
                    headers['Range'] = 'bytes=%s-%d' % (start, start+URLFETCH_MAXSIZE)
                deadline = URLFETCH_TIMEOUT * 2
            except Exception as e:
                errors.append('Exception %s(deadline=%s)' % (e, deadline))
        else:
            return self.send_notify(method, url, 500, 'Python Server: Urlfetch error: %s' % errors)

        headers = response.headers
        if 'content-length' not in headers:
            headers['content-length'] = str(len(response.content))
        headers['connection'] = 'close'
        return self.send_response(response.status_code, headers, response.content)

########NEW FILE########
__FILENAME__ = index
#!/usr/bin/env python
# coding:utf-8

__version__ = '3.1.4'
__password__ = '123456'
__hostsdeny__ = ()  # __hostsdeny__ = ('.youtube.com', '.youku.com')
__content_type__ = 'image/gif'
__timeout__ = 20

try:
    import gevent
    import gevent.queue
    import gevent.monkey
    gevent.monkey.patch_all()
except ImportError:
    pass

import sys
import re
import time
import itertools
import functools
import logging
import string
import urlparse
import httplib
import struct
import zlib
import collections
import Queue

normcookie = functools.partial(re.compile(', ([^ =]+(?:=|$))').sub, '\\r\\nSet-Cookie: \\1')

def message_html(title, banner, detail=''):
    MESSAGE_TEMPLATE = '''
    <html><head>
    <meta http-equiv="content-type" content="text/html;charset=utf-8">
    <title>$title</title>
    <style><!--
    body {font-family: arial,sans-serif}
    div.nav {margin-top: 1ex}
    div.nav A {font-size: 10pt; font-family: arial,sans-serif}
    span.nav {font-size: 10pt; font-family: arial,sans-serif; font-weight: bold}
    div.nav A,span.big {font-size: 12pt; color: #0000cc}
    div.nav A {font-size: 10pt; color: black}
    A.l:link {color: #6f6f6f}
    A.u:link {color: green}
    //--></style>
    </head>
    <body text=#000000 bgcolor=#ffffff>
    <table border=0 cellpadding=2 cellspacing=0 width=100%>
    <tr><td bgcolor=#3366cc><font face=arial,sans-serif color=#ffffff><b>Message</b></td></tr>
    <tr><td> </td></tr></table>
    <blockquote>
    <H1>$banner</H1>
    $detail
    <p>
    </blockquote>
    <table width=100% cellpadding=0 cellspacing=0><tr><td bgcolor=#3366cc><img alt="" width=1 height=4></td></tr></table>
    </body></html>
    '''
    return string.Template(MESSAGE_TEMPLATE).substitute(title=title, banner=banner, detail=detail)


class XORCipher(object):
    """XOR Cipher Class"""
    def __init__(self, key):
        self.__key_gen = itertools.cycle([ord(x) for x in key]).next
        self.__key_xor = lambda s: ''.join(chr(ord(x) ^ self.__key_gen()) for x in s)
        if len(key) == 1:
            try:
                from Crypto.Util.strxor import strxor_c
                c = ord(key)
                self.__key_xor = lambda s: strxor_c(s, c)
            except ImportError:
                sys.stderr.write('Load Crypto.Util.strxor Failed, Use Pure Python Instead.\n')

    def encrypt(self, data):
        return self.__key_xor(data)


def decode_request(data):
    metadata_length, = struct.unpack('!h', data[:2])
    metadata = zlib.decompress(data[2:2+metadata_length], -zlib.MAX_WBITS)
    body = data[2+metadata_length:]
    headers = dict(x.split(':', 1) for x in metadata.splitlines() if x)
    method = headers.pop('G-Method')
    url = headers.pop('G-Url')
    kwargs = {}
    any(kwargs.__setitem__(x[2:].lower(), headers.pop(x)) for x in headers.keys() if x.startswith('G-'))
    if headers.get('Content-Encoding', '') == 'deflate':
        body = zlib.decompress(body, -zlib.MAX_WBITS)
        headers['Content-Length'] = str(len(body))
        del headers['Content-Encoding']
    return method, url, headers, kwargs, body


HTTP_CONNECTION_CACHE = collections.defaultdict(Queue.PriorityQueue)

def application(environ, start_response):
    if environ['REQUEST_METHOD'] == 'GET':
        start_response('302 Found', [('Location', 'https://www.google.com')])
        raise StopIteration

    post_data = environ['wsgi.input'].read(int(environ.get('CONTENT_LENGTH') or -1))
    method, url, headers, kwargs, body = decode_request(post_data)
    scheme, netloc, path, _, query, _ = urlparse.urlparse(url)
    cipher = XORCipher(__password__[0])

    if __password__ != kwargs.get('password'):
        start_response('403 Forbidden', [('Content-Type', 'text/html')])
        yield message_html('403 Wrong Password', 'Wrong Password(%s)' % kwargs.get('password'), detail='please edit proxy.ini')
        raise StopIteration

    if __hostsdeny__ and netloc.endswith(__hostsdeny__):
        start_response('200 OK', [('Content-Type', __content_type__)])
        yield cipher.encrypt('HTTP/1.1 403 Forbidden\r\nContent-type: text/html\r\n\r\n')
        yield cipher.encrypt(message_html('403 Forbidden Host', 'Hosts Deny(%s)' % netloc, detail='url=%r' % url))
        raise StopIteration

    timeout = int(kwargs.get('timeout') or __timeout__)
    fetchmax = int(kwargs.get('fetchmax') or 3)
    ConnectionType = httplib.HTTPSConnection if scheme == 'https' else httplib.HTTPConnection
    header_sent = False
    try:
        connection = None
        response = None
        for i in xrange(fetchmax):
            try:
                while True:
                    try:
                        mtime, connection = HTTP_CONNECTION_CACHE[(scheme, netloc)].get_nowait()
                        if time.time() - mtime < 16:
                            break
                        else:
                            connection.close()
                    except Queue.Empty:
                        connection = ConnectionType(netloc, timeout=timeout)
                        break
                connection.request(method, '%s?%s' % (path, query) if query else path, body=body, headers=headers)
                response = connection.getresponse(buffering=True)
                break
            except Exception as e:
                if i == fetchmax - 1:
                    raise
        need_encrypt = not response.getheader('Content-Type', '').startswith(('audio/', 'image/', 'video/', 'application/octet-stream'))
        start_response('200 OK', [('Content-Type', __content_type__ if need_encrypt else 'image/x-png')])
        header_sent = True
        if response.getheader('Set-Cookie'):
            response.msg['Set-Cookie'] = normcookie(response.getheader('Set-Cookie'))
        content = 'HTTP/1.1 %s %s\r\n%s\r\n' % (response.status, httplib.responses.get(response.status, 'Unknown'), ''.join('%s: %s\r\n' % (k.title(), v) for k, v in response.getheaders() if k.title() != 'Transfer-Encoding'))
        if need_encrypt:
            content = cipher.encrypt(content)
        yield content
        # bufsize = 32768 if int(response.getheader('Content-Length', 0)) > 512*1024 else 8192
        bufsize = 8192
        while True:
            data = response.read(bufsize)
            if not data:
                response.close()
                if connection.sock:
                    HTTP_CONNECTION_CACHE[(scheme, netloc)].put((time.time(), connection))
                return
            if need_encrypt:
                data = cipher.encrypt(data)
            yield data
            del data
    except Exception as e:
        import traceback
        if not header_sent:
            start_response('200 OK', [('Content-Type', __content_type__)])
        yield cipher.encrypt('HTTP/1.1 500 Internal Server Error\r\nContent-type: text/html\r\n\r\n')
        yield cipher.encrypt(message_html('500 Internal Server Error', 'urlfetch %r: %r' % (url, e), '<pre>%s</pre>' % traceback.format_exc()))
        raise StopIteration

try:
    import sae
    application = sae.create_wsgi_app(application)
except ImportError:
    pass

try:
    import bae.core.wsgi
    application = bae.core.wsgi.WSGIApplication(application)
except ImportError:
    pass


def run_wsgi_app(address, app):
    try:
        from gunicorn.app.wsgiapp import WSGIApplication
        class GunicornApplication(WSGIApplication):
            def init(self, parser, opts, args):
                return {'bind': '%s:%d' % (address[0], int(address[1])),
                        'workers': 2,
                        'worker_class': 'gevent'}
            def load(self):
                return application
        GunicornApplication().run()
    except ImportError:
        from gevent.wsgi import WSGIServer
        WSGIServer(address, app).serve_forever()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s - - %(asctime)s %(message)s', datefmt='[%b %d %H:%M:%S]')
    host, _, port = sys.argv[1].rpartition(':')
    logging.info('local python application serving at %s:%s', host, port)
    run_wsgi_app((host, int(port)), application)

########NEW FILE########
