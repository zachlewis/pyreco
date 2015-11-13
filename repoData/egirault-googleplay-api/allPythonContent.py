__FILENAME__ = androproto
#!/usr/bin/python
# This script analyzes an APK and tries to recover its .proto file, assuming
# the APK is using Micro-Protobuf. It has only been tested on Google Play
# Android client (sha1: 0f214c312f9800b01e2a5a7b9766dc880efda110).
#
# Use it at your own risk!

import sys

from pprint import pprint

from androguard.core import *
from androguard.core.androgen import *
from androguard.core.androconf import *
from androguard.core.bytecode import *
from androguard.core.bytecodes.jvm import *
from androguard.core.bytecodes.dvm import *
from androguard.core.bytecodes.apk import *
from androguard.core.analysis.analysis import *

# Find mergeFrom() method in class with name cn
def find_mergeFrom(dvm, cn):
    l = filter(lambda m: m.get_name() == "mergeFrom" and not m.get_descriptor().endswith("MessageMicro;"), dvm.get_methods_class(cn))
    if (len(l) != 1):
        raise Exception("Unable to find mergeFrom() in class %s" % cn)
    return l[0]

def index_basic_blocks(dvm, vma, cn):
    m = find_mergeFrom(dvm, cn)
    ma = vma.get_method(m)
    bbs = ma.basic_blocks.gets()

    # Find the basic block which ends with a sparse-switch (usually the first)
    l = filter(lambda bb: bb.get_instructions()[-1].get_name() == "sparse-switch", bbs)
    if (len(l) != 1):
        return {} # TODO
        # raise Exception("Unable to find a basic block ending with a sparse-switch in mergeFrom() method of class %s" % cn)
        # TODO handle packed-switch (cf 1ere classe dans proto_class_names)
    ss = l[0]

    # Get the offset of the sparse-switch, and the sparse-switch-payload
    # instruction.
    n = ss.get_nb_instructions()
    offset_ss = sum(i.get_length() for i in ss.get_instructions()[:n-1])
    ssp = ss.get_special_ins(offset_ss)

    # Fill the list {key: bb} for this class
    d = {}
    for key, target in zip(ssp.get_keys(), ssp.get_targets()):
        d[key >> 3] = ma.basic_blocks.get_basic_block(offset_ss + target*2)

    return d

def get_invoked_method_info(i):
    m = i.cm.get_method_ref(i.BBBB)
    return (m.get_class_name(), m.get_name(), m.get_descriptor())

def classname_to_messagename(cn):
    return cn.split('/')[-1].replace(';', '')

def ulfirst(s):
    return s[0].lower() + s[1:]

def analyse_bb(bb, k, cn):
    message_type = None
    l = []

    # Index all invoke-virtual instructions. There should be 2 per basic block;
    # one for reading from the stream, the other for setting the appropriate
    # class member.
    for i in bb.get_instructions():
        n = i.get_name()
        if n == "invoke-virtual":
            icn, imn, imd = get_invoked_method_info(i)
            l.append( imn ) # class name : icn.split("/")[-1]

        if n == "invoke-direct":
            icn, imn, _ = get_invoked_method_info(i)

            if (imn == "<init>"):
                message_type = classname_to_messagename(icn)


    if (len(l) == 0): # no calls, probably the switch basic block. skip it.
        return None

    if (len(l) != 2):
        raise Exception("There are %d invoke-virtual calls in this basic block, wtf is this shit?!" % len(l)) # TODO

    if (not l[0].startswith("read")):
        raise Exception("The first invoke-virtual call is not a readXXX(), dafuq?")

    typ = l[0][4:].lower()
    method = l[1]
    field = method[3:]

    if (typ == "message"):
        typ = message_type

    if (method.startswith("set")):    # optional (or required?) # TODO
        return (field, typ, "optional")

    if (method.startswith("add")):    # repeated
        return (field, typ, "repeated")

##############################################################
# Main program starts here
##############################################################

if (len(sys.argv) != 2):
    print "Usage: %s <apk>" % sys.argv[0]
    print "Tries to recover the .proto file used by the given APK."
    print "Works only with Micro-Protobuf apps, and has only been tested with Google Play."
    print "For more information: http://www.segmentationfault.fr/publications/reversing-google-play-and-micro-protobuf-applications/"
    print
    sys.exit(0)

apk = APK(sys.argv[1])
dvm = DalvikVMFormat(apk.get_dex())
vma = uVMAnalysis(dvm)

proto_classes = filter(lambda c: "MessageMicro;" in c.get_superclassname(), dvm.get_classes())
if (len(proto_classes) == 0):
    print "Unable to find protobuf micro classes."
    sys.exit(0)

proto_class_names = map(lambda c: c.get_name(), proto_classes)

"""
cn = proto_class_names[1]
print cn
pprint([(i.split('/')[-1], sorted([(k >> 3) for k in index_basic_blocks(dvm, vma, i).keys()])) for i in proto_class_names])
"""

messages_info = {}
for pcn in proto_class_names:
    mn = classname_to_messagename(pcn)
    d = {}
    for (k, bb) in index_basic_blocks(dvm, vma, pcn).items():
        info = analyse_bb(bb, k, pcn)
        if (info is not None):
            d[k] = info
    messages_info[mn] = d
#pprint(messages_info)

def treeify(seq):
    """Resolve message dependencies
    http://stackoverflow.com/questions/3464975/how-to-efficiently-merge-multiple-list-of-different-length-into-a-tree-dictonary
    """
    ret = {}
    for path in seq:
        cur = ret
        for node in path:
            cur = cur.setdefault(node, {})
    return ret

messages_dep = treeify([k.split('$') for k in messages_info])
#pprint(messages_dep)

def print_proto(d, parent = (), indent=0):
    """Display all protos"""
    for m, sd in sorted(d.items(), cmp=lambda x,y: cmp(x[0],y[0])):
        full_name_l = parent+(m,)
        full_name = '$'.join(full_name_l)

        is_message_or_group = full_name in messages_info

        if (is_message_or_group):
            print_message(m, sd, parent, indent)
        else:
            print_proto(sd, full_name_l, indent)


def print_message(name, sd, parent, indent, title="message", extras=[]):
    full_name_l = parent+(name,)
    full_name = '$'.join(full_name_l)

    #if (messages_printed[full_name]):         # TODO useless
    #    return False

    # messages_printed[full_name] = True

    if (title == "message"):
        print indent*"    " + "message %s {" % (name)
    else:
        print indent*"    " + "%s group %s = %d {" % (extras[0], name, extras[1])

    i = indent+1
    infos = messages_info[full_name]

    # Display sub-messages, except groups
    groups = [field for (field, typ, _) in infos.values() if typ == 'group']
    print_proto(dict([(k, m) for (k, m) in sd.items() if k not in groups]), full_name_l, i)

    for k, info in sorted(infos.items(), cmp=lambda x,y: cmp(x[0],y[0])):
        field, typ, rule = info

        if (typ == 'group'):
            print_message(field, sd[field], full_name_l, i, "group", (rule, k))
        else:
            print '    '*i + ' '.join([rule, typ.split('$')[-1], ulfirst(field)]) + ' = %d;' % k

    print indent*"    " + "}"

print_proto(messages_dep)


########NEW FILE########
__FILENAME__ = apishell
#!/usr/bin/python

# Do not remove
GOOGLE_LOGIN = GOOGLE_PASSWORD = AUTH_TOKEN = None

BANNER = """
Google Play Unofficial API Interactive Shell
Successfully logged in using your Google account. The variable 'api' holds the API object.
Feel free to use help(api).
"""

import sys
import urlparse
import code
from pprint import pprint
from google.protobuf import text_format

from config import *
from googleplay import GooglePlayAPI

api = GooglePlayAPI(ANDROID_ID)
api.login(GOOGLE_LOGIN, GOOGLE_PASSWORD, AUTH_TOKEN)
code.interact(BANNER, local=locals())

########NEW FILE########
__FILENAME__ = categories
#!/usr/bin/python

# Do not remove
GOOGLE_LOGIN = GOOGLE_PASSWORD = AUTH_TOKEN = None

import sys
import urlparse
from pprint import pprint
from google.protobuf import text_format

from config import *
from googleplay import GooglePlayAPI

api = GooglePlayAPI(ANDROID_ID)
api.login(GOOGLE_LOGIN, GOOGLE_PASSWORD, AUTH_TOKEN)
response = api.browse()

print SEPARATOR.join(["ID", "Name"])
for c in response.category:
  print SEPARATOR.join(i.encode('utf8') for i in [urlparse.parse_qs(c.dataUrl)['cat'][0], c.name])


########NEW FILE########
__FILENAME__ = config
# separator used by search.py, categories.py, ...
SEPARATOR = ";"

LANG            = "en_US" # can be en_US, fr_FR, ...
ANDROID_ID      = None # "xxxxxxxxxxxxxxxx"
GOOGLE_LOGIN    = None # "username@gmail.com"
GOOGLE_PASSWORD = None
AUTH_TOKEN      = None # "yyyyyyyyy"

# force the user to edit this file
if any([each == None for each in [ANDROID_ID, GOOGLE_LOGIN, GOOGLE_PASSWORD]]):
    raise Exception("config.py not updated")


########NEW FILE########
__FILENAME__ = download
#!/usr/bin/python

# Do not remove
GOOGLE_LOGIN = GOOGLE_PASSWORD = AUTH_TOKEN = None

import sys
from pprint import pprint

from config import *
from googleplay import GooglePlayAPI
from helpers import sizeof_fmt

if (len(sys.argv) < 2):
    print "Usage: %s packagename [filename]"
    print "Download an app."
    print "If filename is not present, will write to packagename.apk."
    sys.exit(0)

packagename = sys.argv[1]

if (len(sys.argv) == 3):
    filename = sys.argv[2]
else:
    filename = packagename + ".apk"

# Connect
api = GooglePlayAPI(ANDROID_ID)
api.login(GOOGLE_LOGIN, GOOGLE_PASSWORD, AUTH_TOKEN)

# Get the version code and the offer type from the app details
m = api.details(packagename)
doc = m.docV2
vc = doc.details.appDetails.versionCode
ot = doc.offer[0].offerType

# Download
print "Downloading %s..." % sizeof_fmt(doc.details.appDetails.installationSize),
data = api.download(packagename, vc, ot)
open(filename, "wb").write(data)
print "Done"


########NEW FILE########
__FILENAME__ = googleplay
#!/usr/bin/python

import base64
import gzip
import pprint
import StringIO
import requests

from google.protobuf import descriptor
from google.protobuf.internal.containers import RepeatedCompositeFieldContainer
from google.protobuf import text_format
from google.protobuf.message import Message, DecodeError

import googleplay_pb2
import config

class LoginError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class RequestError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class GooglePlayAPI(object):
    """Google Play Unofficial API Class

    Usual APIs methods are login(), search(), details(), bulkDetails(),
    download(), browse(), reviews() and list().

    toStr() can be used to pretty print the result (protobuf object) of the
    previous methods.

    toDict() converts the result into a dict, for easier introspection."""

    SERVICE = "androidmarket"
    URL_LOGIN = "https://android.clients.google.com/auth" # "https://www.google.com/accounts/ClientLogin"
    ACCOUNT_TYPE_GOOGLE = "GOOGLE"
    ACCOUNT_TYPE_HOSTED = "HOSTED"
    ACCOUNT_TYPE_HOSTED_OR_GOOGLE = "HOSTED_OR_GOOGLE"
    authSubToken = None

    def __init__(self, androidId=None, lang=None, debug=False): # you must use a device-associated androidId value
        self.preFetch = {}
        if androidId == None:
            androidId = config.ANDROID_ID
        if lang == None:
            lang = config.LANG
        self.androidId = androidId
        self.lang = lang
        self.debug = debug

    def toDict(self, protoObj):
        """Converts the (protobuf) result from an API call into a dict, for
        easier introspection."""
        iterable = False
        if isinstance(protoObj, RepeatedCompositeFieldContainer):
            iterable = True
        else:
            protoObj = [protoObj]
        retlist = []

        for po in protoObj:
            msg = dict()
            for fielddesc, value in po.ListFields():
                #print value, type(value), getattr(value, "__iter__", False)
                if fielddesc.type == descriptor.FieldDescriptor.TYPE_GROUP or isinstance(value, RepeatedCompositeFieldContainer) or isinstance(value, Message):
                    msg[fielddesc.name] = self.toDict(value)
                else:
                    msg[fielddesc.name] = value
            retlist.append(msg)
        if not iterable:
            if len(retlist) > 0:
                return retlist[0]
            else:
                return None
        return retlist

    def toStr(self, protoObj):
        """Used for pretty printing a result from the API."""
        return text_format.MessageToString(protoObj)

    def _try_register_preFetch(self, protoObj):
        fields = [i.name for (i,_) in protoObj.ListFields()]
        if ("preFetch" in fields):
            for p in protoObj.preFetch:
                self.preFetch[p.url] = p.response

    def setAuthSubToken(self, authSubToken):
        self.authSubToken = authSubToken

        # put your auth token in config.py to avoid multiple login requests
        if self.debug:
            print "authSubToken: " + authSubToken

    def login(self, email=None, password=None, authSubToken=None):
        """Login to your Google Account. You must provide either:
        - an email and password
        - a valid Google authSubToken"""
        if (authSubToken is not None):
            self.setAuthSubToken(authSubToken)
        else:
            if (email is None or password is None):
                raise Exception("You should provide at least authSubToken or (email and password)")
            params = {"Email": email,
                                "Passwd": password,
                                "service": self.SERVICE,
                                "accountType": self.ACCOUNT_TYPE_HOSTED_OR_GOOGLE,
                                "has_permission": "1",
                                "source": "android",
                                "androidId": self.androidId,
                                "app": "com.android.vending",
                                #"client_sig": self.client_sig,
                                "device_country": "fr",
                                "operatorCountry": "fr",
                                "lang": "fr",
                                "sdk_version": "16"}
            headers = {
                "Accept-Encoding": "",
            }
            response = requests.post(self.URL_LOGIN, data=params, headers=headers, verify=False)
            data = response.text.split()
            params = {}
            for d in data:
                if not "=" in d: continue
                k, v = d.split("=")
                params[k.strip().lower()] = v.strip()
            if "auth" in params:
                self.setAuthSubToken(params["auth"])
            elif "error" in params:
                raise LoginError("server says: " + params["error"])
            else:
                raise LoginError("Auth token not found.")

    def executeRequestApi2(self, path, datapost=None, post_content_type="application/x-www-form-urlencoded; charset=UTF-8"):
        if (datapost is None and path in self.preFetch):
            data = self.preFetch[path]
        else:
            headers = { "Accept-Language": self.lang,
                                    "Authorization": "GoogleLogin auth=%s" % self.authSubToken,
                                    "X-DFE-Enabled-Experiments": "cl:billing.select_add_instrument_by_default",
                                    "X-DFE-Unsupported-Experiments": "nocache:billing.use_charging_poller,market_emails,buyer_currency,prod_baseline,checkin.set_asset_paid_app_field,shekel_test,content_ratings,buyer_currency_in_app,nocache:encrypted_apk,recent_changes",
                                    "X-DFE-Device-Id": self.androidId,
                                    "X-DFE-Client-Id": "am-android-google",
                                    #"X-DFE-Logging-Id": self.loggingId2, # Deprecated?
                                    "User-Agent": "Android-Finsky/3.7.13 (api=3,versionCode=8013013,sdk=16,device=crespo,hardware=herring,product=soju)",
                                    "X-DFE-SmallestScreenWidthDp": "320",
                                    "X-DFE-Filter-Level": "3",
                                    "Accept-Encoding": "",
                                    "Host": "android.clients.google.com"}

            if datapost is not None:
                headers["Content-Type"] = post_content_type

            url = "https://android.clients.google.com/fdfe/%s" % path
            if datapost is not None:
                response = requests.post(url, data=datapost, headers=headers, verify=False)
            else:
                response = requests.get(url, headers=headers, verify=False)
            data = response.content

        '''
        data = StringIO.StringIO(data)
        gzipper = gzip.GzipFile(fileobj=data)
        data = gzipper.read()
        '''
        message = googleplay_pb2.ResponseWrapper.FromString(data)
        self._try_register_preFetch(message)

        # Debug
        #print text_format.MessageToString(message)
        return message

    #####################################
    # Google Play API Methods
    #####################################

    def search(self, query, nb_results=None, offset=None):
        """Search for apps."""
        path = "search?c=3&q=%s" % requests.utils.quote(query) # TODO handle categories
        if (nb_results is not None):
            path += "&n=%d" % int(nb_results)
        if (offset is not None):
            path += "&o=%d" % int(offset)

        message = self.executeRequestApi2(path)
        return message.payload.searchResponse

    def details(self, packageName):
        """Get app details from a package name.
        packageName is the app unique ID (usually starting with 'com.')."""
        path = "details?doc=%s" % requests.utils.quote(packageName)
        message = self.executeRequestApi2(path)
        return message.payload.detailsResponse

    def bulkDetails(self, packageNames):
        """Get several apps details from a list of package names.

        This is much more efficient than calling N times details() since it
        requires only one request.

        packageNames is a list of app ID (usually starting with 'com.')."""
        path = "bulkDetails"
        req = googleplay_pb2.BulkDetailsRequest()
        req.docid.extend(packageNames)
        data = req.SerializeToString()
        message = self.executeRequestApi2(path, data, "application/x-protobuf")
        return message.payload.bulkDetailsResponse

    def browse(self, cat=None, ctr=None):
        """Browse categories.
        cat (category ID) and ctr (subcategory ID) are used as filters."""
        path = "browse?c=3"
        if (cat != None):
            path += "&cat=%s" % requests.utils.quote(cat)
        if (ctr != None):
            path += "&ctr=%s" % requests.utils.quote(ctr)
        message = self.executeRequestApi2(path)
        return message.payload.browseResponse

    def list(self, cat, ctr=None, nb_results=None, offset=None):
        """List apps.

        If ctr (subcategory ID) is None, returns a list of valid subcategories.

        If ctr is provided, list apps within this subcategory."""
        path = "list?c=3&cat=%s" % requests.utils.quote(cat)
        if (ctr != None):
            path += "&ctr=%s" % requests.utils.quote(ctr)
        if (nb_results != None):
            path += "&n=%s" % requests.utils.quote(nb_results)
        if (offset != None):
            path += "&o=%s" % requests.utils.quote(offset)
        message = self.executeRequestApi2(path)
        return message.payload.listResponse
    
    def reviews(self, packageName, filterByDevice=False, sort=2, nb_results=None, offset=None):
        """Browse reviews.
        packageName is the app unique ID.
        If filterByDevice is True, return only reviews for your device."""
        path = "rev?doc=%s&sort=%d" % (requests.utils.quote(packageName), sort)
        if (nb_results is not None):
            path += "&n=%d" % int(nb_results)
        if (offset is not None):
            path += "&o=%d" % int(offset)
        if(filterByDevice):
            path += "&dfil=1"
        message = self.executeRequestApi2(path)
        return message.payload.reviewResponse
    
    def download(self, packageName, versionCode, offerType=1):
        """Download an app and return its raw data (APK file).

        packageName is the app unique ID (usually starting with 'com.').

        versionCode can be grabbed by using the details() method on the given
        app."""
        path = "purchase"
        data = "ot=%d&doc=%s&vc=%d" % (offerType, packageName, versionCode)
        message = self.executeRequestApi2(path, data)

        url = message.payload.buyResponse.purchaseStatusResponse.appDeliveryData.downloadUrl
        cookie = message.payload.buyResponse.purchaseStatusResponse.appDeliveryData.downloadAuthCookie[0]

        cookies = {
            str(cookie.name): str(cookie.value) # python-requests #459 fixes this
        }

        headers = {
                   "User-Agent" : "AndroidDownloadManager/4.1.1 (Linux; U; Android 4.1.1; Nexus S Build/JRO03E)",
                   "Accept-Encoding": "",
                  }

        response = requests.get(url, headers=headers, cookies=cookies, verify=False)
        return response.content


########NEW FILE########
__FILENAME__ = googleplay_pb2
# Generated by the protocol buffer compiler.  DO NOT EDIT!

from google.protobuf import descriptor
from google.protobuf import message
from google.protobuf import reflection
from google.protobuf import descriptor_pb2
# @@protoc_insertion_point(imports)


DESCRIPTOR = descriptor.FileDescriptor(
  name='googleplay.proto',
  package='',
  serialized_pb='\n\x10googleplay.proto\"\x19\n\x17\x41\x63kNotificationResponse\"\x8b\x03\n\x16\x41ndroidAppDeliveryData\x12\x14\n\x0c\x64ownloadSize\x18\x01 \x01(\x03\x12\x11\n\tsignature\x18\x02 \x01(\t\x12\x13\n\x0b\x64ownloadUrl\x18\x03 \x01(\t\x12(\n\x0e\x61\x64\x64itionalFile\x18\x04 \x03(\x0b\x32\x10.AppFileMetadata\x12\'\n\x12\x64ownloadAuthCookie\x18\x05 \x03(\x0b\x32\x0b.HttpCookie\x12\x15\n\rforwardLocked\x18\x06 \x01(\x08\x12\x15\n\rrefundTimeout\x18\x07 \x01(\x03\x12\x17\n\x0fserverInitiated\x18\x08 \x01(\x08\x12%\n\x1dpostInstallRefundWindowMillis\x18\t \x01(\x03\x12\x1c\n\x14immediateStartNeeded\x18\n \x01(\x08\x12\'\n\tpatchData\x18\x0b \x01(\x0b\x32\x14.AndroidAppPatchData\x12+\n\x10\x65ncryptionParams\x18\x0c \x01(\x0b\x32\x11.EncryptionParams\"\x85\x01\n\x13\x41ndroidAppPatchData\x12\x17\n\x0f\x62\x61seVersionCode\x18\x01 \x01(\x05\x12\x15\n\rbaseSignature\x18\x02 \x01(\t\x12\x13\n\x0b\x64ownloadUrl\x18\x03 \x01(\t\x12\x13\n\x0bpatchFormat\x18\x04 \x01(\x05\x12\x14\n\x0cmaxPatchSize\x18\x05 \x01(\x03\"[\n\x0f\x41ppFileMetadata\x12\x10\n\x08\x66ileType\x18\x01 \x01(\x05\x12\x13\n\x0bversionCode\x18\x02 \x01(\x05\x12\x0c\n\x04size\x18\x03 \x01(\x03\x12\x13\n\x0b\x64ownloadUrl\x18\x04 \x01(\t\"K\n\x10\x45ncryptionParams\x12\x0f\n\x07version\x18\x01 \x01(\x05\x12\x15\n\rencryptionKey\x18\x02 \x01(\t\x12\x0f\n\x07hmacKey\x18\x03 \x01(\t\")\n\nHttpCookie\x12\x0c\n\x04name\x18\x01 \x01(\t\x12\r\n\x05value\x18\x02 \x01(\t\"\xad\x02\n\x07\x41\x64\x64ress\x12\x0c\n\x04name\x18\x01 \x01(\t\x12\x14\n\x0c\x61\x64\x64ressLine1\x18\x02 \x01(\t\x12\x14\n\x0c\x61\x64\x64ressLine2\x18\x03 \x01(\t\x12\x0c\n\x04\x63ity\x18\x04 \x01(\t\x12\r\n\x05state\x18\x05 \x01(\t\x12\x12\n\npostalCode\x18\x06 \x01(\t\x12\x15\n\rpostalCountry\x18\x07 \x01(\t\x12\x19\n\x11\x64\x65pendentLocality\x18\x08 \x01(\t\x12\x13\n\x0bsortingCode\x18\t \x01(\t\x12\x14\n\x0clanguageCode\x18\n \x01(\t\x12\x13\n\x0bphoneNumber\x18\x0b \x01(\t\x12\x11\n\tisReduced\x18\x0c \x01(\x08\x12\x11\n\tfirstName\x18\r \x01(\t\x12\x10\n\x08lastName\x18\x0e \x01(\t\x12\r\n\x05\x65mail\x18\x0f \x01(\t\"J\n\nBookAuthor\x12\x0c\n\x04name\x18\x01 \x01(\t\x12\x17\n\x0f\x64\x65precatedQuery\x18\x02 \x01(\t\x12\x15\n\x05\x64ocid\x18\x03 \x01(\x0b\x32\x06.Docid\"\xc3\x03\n\x0b\x42ookDetails\x12\x1d\n\x07subject\x18\x03 \x03(\x0b\x32\x0c.BookSubject\x12\x11\n\tpublisher\x18\x04 \x01(\t\x12\x17\n\x0fpublicationDate\x18\x05 \x01(\t\x12\x0c\n\x04isbn\x18\x06 \x01(\t\x12\x15\n\rnumberOfPages\x18\x07 \x01(\x05\x12\x10\n\x08subtitle\x18\x08 \x01(\t\x12\x1b\n\x06\x61uthor\x18\t \x03(\x0b\x32\x0b.BookAuthor\x12\x11\n\treaderUrl\x18\n \x01(\t\x12\x17\n\x0f\x64ownloadEpubUrl\x18\x0b \x01(\t\x12\x16\n\x0e\x64ownloadPdfUrl\x18\x0c \x01(\t\x12\x17\n\x0f\x61\x63sEpubTokenUrl\x18\r \x01(\t\x12\x16\n\x0e\x61\x63sPdfTokenUrl\x18\x0e \x01(\t\x12\x15\n\repubAvailable\x18\x0f \x01(\x08\x12\x14\n\x0cpdfAvailable\x18\x10 \x01(\x08\x12\x16\n\x0e\x61\x62outTheAuthor\x18\x11 \x01(\t\x12+\n\nidentifier\x18\x12 \x03(\n2\x17.BookDetails.Identifier\x1a.\n\nIdentifier\x12\x0c\n\x04type\x18\x13 \x01(\x05\x12\x12\n\nidentifier\x18\x14 \x01(\t\"=\n\x0b\x42ookSubject\x12\x0c\n\x04name\x18\x01 \x01(\t\x12\r\n\x05query\x18\x02 \x01(\t\x12\x11\n\tsubjectId\x18\x03 \x01(\t\"+\n\nBrowseLink\x12\x0c\n\x04name\x18\x01 \x01(\t\x12\x0f\n\x07\x64\x61taUrl\x18\x03 \x01(\t\"w\n\x0e\x42rowseResponse\x12\x13\n\x0b\x63ontentsUrl\x18\x01 \x01(\t\x12\x10\n\x08promoUrl\x18\x02 \x01(\t\x12\x1d\n\x08\x63\x61tegory\x18\x03 \x03(\x0b\x32\x0b.BrowseLink\x12\x1f\n\nbreadcrumb\x18\x04 \x03(\x0b\x32\x0b.BrowseLink\"\x8f\x02\n\x10\x41\x64\x64ressChallenge\x12\x1c\n\x14responseAddressParam\x18\x01 \x01(\t\x12\x1f\n\x17responseCheckboxesParam\x18\x02 \x01(\t\x12\r\n\x05title\x18\x03 \x01(\t\x12\x17\n\x0f\x64\x65scriptionHtml\x18\x04 \x01(\t\x12\x1f\n\x08\x63heckbox\x18\x05 \x03(\x0b\x32\r.FormCheckbox\x12\x19\n\x07\x61\x64\x64ress\x18\x06 \x01(\x0b\x32\x08.Address\x12.\n\x0f\x65rrorInputField\x18\x07 \x03(\x0b\x32\x15.InputValidationError\x12\x11\n\terrorHtml\x18\x08 \x01(\t\x12\x15\n\rrequiredField\x18\t \x03(\x05\"\xef\x01\n\x17\x41uthenticationChallenge\x12\x1a\n\x12\x61uthenticationType\x18\x01 \x01(\x05\x12\'\n\x1fresponseAuthenticationTypeParam\x18\x02 \x01(\t\x12\x1f\n\x17responseRetryCountParam\x18\x03 \x01(\t\x12\x15\n\rpinHeaderText\x18\x04 \x01(\t\x12\x1e\n\x16pinDescriptionTextHtml\x18\x05 \x01(\t\x12\x16\n\x0egaiaHeaderText\x18\x06 \x01(\t\x12\x1f\n\x17gaiaDescriptionTextHtml\x18\x07 \x01(\t\"\x81\t\n\x0b\x42uyResponse\x12\x37\n\x10purchaseResponse\x18\x01 \x01(\x0b\x32\x1d.PurchaseNotificationResponse\x12/\n\x0c\x63heckoutinfo\x18\x02 \x01(\n2\x19.BuyResponse.CheckoutInfo\x12\x16\n\x0e\x63ontinueViaUrl\x18\x08 \x01(\t\x12\x19\n\x11purchaseStatusUrl\x18\t \x01(\t\x12\x19\n\x11\x63heckoutServiceId\x18\x0c \x01(\t\x12\x1d\n\x15\x63heckoutTokenRequired\x18\r \x01(\x08\x12\x17\n\x0f\x62\x61seCheckoutUrl\x18\x0e \x01(\t\x12\x17\n\x0ftosCheckboxHtml\x18% \x03(\t\x12\x1a\n\x12iabPermissionError\x18& \x01(\x05\x12\x37\n\x16purchaseStatusResponse\x18\' \x01(\x0b\x32\x17.PurchaseStatusResponse\x12\x16\n\x0epurchaseCookie\x18. \x01(\t\x12\x1d\n\tchallenge\x18\x31 \x01(\x0b\x32\n.Challenge\x1a\xdc\x05\n\x0c\x43heckoutInfo\x12\x17\n\x04item\x18\x03 \x01(\x0b\x32\t.LineItem\x12\x1a\n\x07subItem\x18\x04 \x03(\x0b\x32\t.LineItem\x12@\n\x0e\x63heckoutoption\x18\x05 \x03(\n2(.BuyResponse.CheckoutInfo.CheckoutOption\x12\x1d\n\x15\x64\x65precatedCheckoutUrl\x18\n \x01(\t\x12\x18\n\x10\x61\x64\x64InstrumentUrl\x18\x0b \x01(\t\x12\x12\n\nfooterHtml\x18\x14 \x03(\t\x12 \n\x18\x65ligibleInstrumentFamily\x18\x1f \x03(\x05\x12\x14\n\x0c\x66ootnoteHtml\x18$ \x03(\t\x12\'\n\x12\x65ligibleInstrument\x18, \x03(\x0b\x32\x0b.Instrument\x1a\xa6\x03\n\x0e\x43heckoutOption\x12\x15\n\rformOfPayment\x18\x06 \x01(\t\x12\x1b\n\x13\x65ncodedAdjustedCart\x18\x07 \x01(\t\x12\x14\n\x0cinstrumentId\x18\x0f \x01(\t\x12\x17\n\x04item\x18\x10 \x03(\x0b\x32\t.LineItem\x12\x1a\n\x07subItem\x18\x11 \x03(\x0b\x32\t.LineItem\x12\x18\n\x05total\x18\x12 \x01(\x0b\x32\t.LineItem\x12\x12\n\nfooterHtml\x18\x13 \x03(\t\x12\x18\n\x10instrumentFamily\x18\x1d \x01(\x05\x12.\n&deprecatedInstrumentInapplicableReason\x18\x1e \x03(\x05\x12\x1a\n\x12selectedInstrument\x18  \x01(\x08\x12\x1a\n\x07summary\x18! \x01(\x0b\x32\t.LineItem\x12\x14\n\x0c\x66ootnoteHtml\x18# \x03(\t\x12\x1f\n\ninstrument\x18+ \x01(\x0b\x32\x0b.Instrument\x12\x16\n\x0epurchaseCookie\x18- \x01(\t\x12\x16\n\x0e\x64isabledReason\x18\x30 \x03(\t\"s\n\tChallenge\x12+\n\x10\x61\x64\x64ressChallenge\x18\x01 \x01(\x0b\x32\x11.AddressChallenge\x12\x39\n\x17\x61uthenticationChallenge\x18\x02 \x01(\x0b\x32\x18.AuthenticationChallenge\"F\n\x0c\x46ormCheckbox\x12\x13\n\x0b\x64\x65scription\x18\x01 \x01(\t\x12\x0f\n\x07\x63hecked\x18\x02 \x01(\x08\x12\x10\n\x08required\x18\x03 \x01(\x08\"\\\n\x08LineItem\x12\x0c\n\x04name\x18\x01 \x01(\t\x12\x13\n\x0b\x64\x65scription\x18\x02 \x01(\t\x12\x15\n\x05offer\x18\x03 \x01(\x0b\x32\x06.Offer\x12\x16\n\x06\x61mount\x18\x04 \x01(\x0b\x32\x06.Money\"F\n\x05Money\x12\x0e\n\x06micros\x18\x01 \x01(\x03\x12\x14\n\x0c\x63urrencyCode\x18\x02 \x01(\t\x12\x17\n\x0f\x66ormattedAmount\x18\x03 \x01(\t\"\x80\x01\n\x1cPurchaseNotificationResponse\x12\x0e\n\x06status\x18\x01 \x01(\x05\x12\x1d\n\tdebugInfo\x18\x02 \x01(\x0b\x32\n.DebugInfo\x12\x1d\n\x15localizedErrorMessage\x18\x03 \x01(\t\x12\x12\n\npurchaseId\x18\x04 \x01(\t\"\xf9\x01\n\x16PurchaseStatusResponse\x12\x0e\n\x06status\x18\x01 \x01(\x05\x12\x11\n\tstatusMsg\x18\x02 \x01(\t\x12\x13\n\x0bstatusTitle\x18\x03 \x01(\t\x12\x14\n\x0c\x62riefMessage\x18\x04 \x01(\t\x12\x0f\n\x07infoUrl\x18\x05 \x01(\t\x12%\n\rlibraryUpdate\x18\x06 \x01(\x0b\x32\x0e.LibraryUpdate\x12\'\n\x12rejectedInstrument\x18\x07 \x01(\x0b\x32\x0b.Instrument\x12\x30\n\x0f\x61ppDeliveryData\x18\x08 \x01(\x0b\x32\x17.AndroidAppDeliveryData\"\xa2\x01\n\x17\x43heckInstrumentResponse\x12\x1e\n\x16userHasValidInstrument\x18\x01 \x01(\x08\x12\x1d\n\x15\x63heckoutTokenRequired\x18\x02 \x01(\x08\x12\x1f\n\ninstrument\x18\x04 \x03(\x0b\x32\x0b.Instrument\x12\'\n\x12\x65ligibleInstrument\x18\x05 \x03(\x0b\x32\x0b.Instrument\"Q\n\x17UpdateInstrumentRequest\x12\x1f\n\ninstrument\x18\x01 \x01(\x0b\x32\x0b.Instrument\x12\x15\n\rcheckoutToken\x18\x02 \x01(\t\"\xd4\x01\n\x18UpdateInstrumentResponse\x12\x0e\n\x06result\x18\x01 \x01(\x05\x12\x14\n\x0cinstrumentId\x18\x02 \x01(\t\x12\x17\n\x0fuserMessageHtml\x18\x03 \x01(\t\x12.\n\x0f\x65rrorInputField\x18\x04 \x03(\x0b\x32\x15.InputValidationError\x12\x1d\n\x15\x63heckoutTokenRequired\x18\x05 \x01(\x08\x12*\n\rredeemedOffer\x18\x06 \x01(\x0b\x32\x13.RedeemedPromoOffer\"0\n\x1bInitiateAssociationResponse\x12\x11\n\tuserToken\x18\x01 \x01(\t\"n\n\x19VerifyAssociationResponse\x12\x0e\n\x06status\x18\x01 \x01(\x05\x12 \n\x0e\x62illingAddress\x18\x02 \x01(\x0b\x32\x08.Address\x12\x1f\n\ncarrierTos\x18\x03 \x01(\x0b\x32\x0b.CarrierTos\"\xcc\x01\n\x17\x41\x64\x64\x43reditCardPromoOffer\x12\x12\n\nheaderText\x18\x01 \x01(\t\x12\x17\n\x0f\x64\x65scriptionHtml\x18\x02 \x01(\t\x12\x15\n\x05image\x18\x03 \x01(\x0b\x32\x06.Image\x12\x1c\n\x14introductoryTextHtml\x18\x04 \x01(\t\x12\x12\n\nofferTitle\x18\x05 \x01(\t\x12\x1b\n\x13noActionDescription\x18\x06 \x01(\t\x12\x1e\n\x16termsAndConditionsHtml\x18\x07 \x01(\t\"K\n\x13\x41vailablePromoOffer\x12\x34\n\x12\x61\x64\x64\x43reditCardOffer\x18\x01 \x01(\x0b\x32\x18.AddCreditCardPromoOffer\"\x92\x01\n\x17\x43heckPromoOfferResponse\x12,\n\x0e\x61vailableOffer\x18\x01 \x03(\x0b\x32\x14.AvailablePromoOffer\x12*\n\rredeemedOffer\x18\x02 \x01(\x0b\x32\x13.RedeemedPromoOffer\x12\x1d\n\x15\x63heckoutTokenRequired\x18\x03 \x01(\x08\"X\n\x12RedeemedPromoOffer\x12\x12\n\nheaderText\x18\x01 \x01(\t\x12\x17\n\x0f\x64\x65scriptionHtml\x18\x02 \x01(\t\x12\x15\n\x05image\x18\x03 \x01(\x0b\x32\x06.Image\"<\n\x05\x44ocid\x12\x14\n\x0c\x62\x61\x63kendDocid\x18\x01 \x01(\t\x12\x0c\n\x04type\x18\x02 \x01(\x05\x12\x0f\n\x07\x62\x61\x63kend\x18\x03 \x01(\x05\">\n\x07Install\x12\x11\n\tandroidId\x18\x01 \x01(\x06\x12\x0f\n\x07version\x18\x02 \x01(\x05\x12\x0f\n\x07\x62undled\x18\x03 \x01(\x08\"\x80\x03\n\x05Offer\x12\x0e\n\x06micros\x18\x01 \x01(\x03\x12\x14\n\x0c\x63urrencyCode\x18\x02 \x01(\t\x12\x17\n\x0f\x66ormattedAmount\x18\x03 \x01(\t\x12\x1e\n\x0e\x63onvertedPrice\x18\x04 \x03(\x0b\x32\x06.Offer\x12\x1c\n\x14\x63heckoutFlowRequired\x18\x05 \x01(\x08\x12\x17\n\x0f\x66ullPriceMicros\x18\x06 \x01(\x03\x12\x1b\n\x13\x66ormattedFullAmount\x18\x07 \x01(\t\x12\x11\n\tofferType\x18\x08 \x01(\x05\x12!\n\x0brentalTerms\x18\t \x01(\x0b\x32\x0c.RentalTerms\x12\x12\n\nonSaleDate\x18\n \x01(\x03\x12\x16\n\x0epromotionLabel\x18\x0b \x03(\t\x12-\n\x11subscriptionTerms\x18\x0c \x01(\x0b\x32\x12.SubscriptionTerms\x12\x15\n\rformattedName\x18\r \x01(\t\x12\x1c\n\x14\x66ormattedDescription\x18\x0e \x01(\t\"\xb1\x01\n\rOwnershipInfo\x12\x1f\n\x17initiationTimestampMsec\x18\x01 \x01(\x03\x12\x1f\n\x17validUntilTimestampMsec\x18\x02 \x01(\x03\x12\x14\n\x0c\x61utoRenewing\x18\x03 \x01(\x08\x12\"\n\x1arefundTimeoutTimestampMsec\x18\x04 \x01(\x03\x12$\n\x1cpostDeliveryRefundWindowMsec\x18\x05 \x01(\x03\"H\n\x0bRentalTerms\x12\x1a\n\x12grantPeriodSeconds\x18\x01 \x01(\x05\x12\x1d\n\x15\x61\x63tivatePeriodSeconds\x18\x02 \x01(\x05\"[\n\x11SubscriptionTerms\x12$\n\x0frecurringPeriod\x18\x01 \x01(\x0b\x32\x0b.TimePeriod\x12 \n\x0btrialPeriod\x18\x02 \x01(\x0b\x32\x0b.TimePeriod\")\n\nTimePeriod\x12\x0c\n\x04unit\x18\x01 \x01(\x05\x12\r\n\x05\x63ount\x18\x02 \x01(\x05\"G\n\x12\x42illingAddressSpec\x12\x1a\n\x12\x62illingAddressType\x18\x01 \x01(\x05\x12\x15\n\rrequiredField\x18\x02 \x03(\x05\">\n\x19\x43\x61rrierBillingCredentials\x12\r\n\x05value\x18\x01 \x01(\t\x12\x12\n\nexpiration\x18\x02 \x01(\x03\"\xa9\x02\n\x18\x43\x61rrierBillingInstrument\x12\x15\n\rinstrumentKey\x18\x01 \x01(\t\x12\x13\n\x0b\x61\x63\x63ountType\x18\x02 \x01(\t\x12\x14\n\x0c\x63urrencyCode\x18\x03 \x01(\t\x12\x18\n\x10transactionLimit\x18\x04 \x01(\x03\x12\x1c\n\x14subscriberIdentifier\x18\x05 \x01(\t\x12\x39\n\x17\x65ncryptedSubscriberInfo\x18\x06 \x01(\x0b\x32\x18.EncryptedSubscriberInfo\x12/\n\x0b\x63redentials\x18\x07 \x01(\x0b\x32\x1a.CarrierBillingCredentials\x12\'\n\x12\x61\x63\x63\x65ptedCarrierTos\x18\x08 \x01(\x0b\x32\x0b.CarrierTos\"\xca\x01\n\x1e\x43\x61rrierBillingInstrumentStatus\x12\x1f\n\ncarrierTos\x18\x01 \x01(\x0b\x32\x0b.CarrierTos\x12\x1b\n\x13\x61ssociationRequired\x18\x02 \x01(\x08\x12\x18\n\x10passwordRequired\x18\x03 \x01(\x08\x12.\n\x15\x63\x61rrierPasswordPrompt\x18\x04 \x01(\x0b\x32\x0f.PasswordPrompt\x12\x12\n\napiVersion\x18\x05 \x01(\x05\x12\x0c\n\x04name\x18\x06 \x01(\t\"\x8e\x01\n\nCarrierTos\x12 \n\x06\x64\x63\x62Tos\x18\x01 \x01(\x0b\x32\x10.CarrierTosEntry\x12 \n\x06piiTos\x18\x02 \x01(\x0b\x32\x10.CarrierTosEntry\x12\x1d\n\x15needsDcbTosAcceptance\x18\x03 \x01(\x08\x12\x1d\n\x15needsPiiTosAcceptance\x18\x04 \x01(\x08\"/\n\x0f\x43\x61rrierTosEntry\x12\x0b\n\x03url\x18\x01 \x01(\t\x12\x0f\n\x07version\x18\x02 \x01(\t\"\xa2\x01\n\x14\x43reditCardInstrument\x12\x0c\n\x04type\x18\x01 \x01(\x05\x12\x14\n\x0c\x65scrowHandle\x18\x02 \x01(\t\x12\x12\n\nlastDigits\x18\x03 \x01(\t\x12\x17\n\x0f\x65xpirationMonth\x18\x04 \x01(\x05\x12\x16\n\x0e\x65xpirationYear\x18\x05 \x01(\x05\x12!\n\x0e\x65scrowEfeParam\x18\x06 \x03(\x0b\x32\t.EfeParam\"&\n\x08\x45\x66\x65Param\x12\x0b\n\x03key\x18\x01 \x01(\x05\x12\r\n\x05value\x18\x02 \x01(\t\"@\n\x14InputValidationError\x12\x12\n\ninputField\x18\x01 \x01(\x05\x12\x14\n\x0c\x65rrorMessage\x18\x02 \x01(\t\"\xc2\x02\n\nInstrument\x12\x14\n\x0cinstrumentId\x18\x01 \x01(\t\x12 \n\x0e\x62illingAddress\x18\x02 \x01(\x0b\x32\x08.Address\x12)\n\ncreditCard\x18\x03 \x01(\x0b\x32\x15.CreditCardInstrument\x12\x31\n\x0e\x63\x61rrierBilling\x18\x04 \x01(\x0b\x32\x19.CarrierBillingInstrument\x12/\n\x12\x62illingAddressSpec\x18\x05 \x01(\x0b\x32\x13.BillingAddressSpec\x12\x18\n\x10instrumentFamily\x18\x06 \x01(\x05\x12=\n\x14\x63\x61rrierBillingStatus\x18\x07 \x01(\x0b\x32\x1f.CarrierBillingInstrumentStatus\x12\x14\n\x0c\x64isplayTitle\x18\x08 \x01(\t\";\n\x0ePasswordPrompt\x12\x0e\n\x06prompt\x18\x01 \x01(\t\x12\x19\n\x11\x66orgotPasswordUrl\x18\x02 \x01(\t\"\x92\x01\n\x11\x43ontainerMetadata\x12\x11\n\tbrowseUrl\x18\x01 \x01(\t\x12\x13\n\x0bnextPageUrl\x18\x02 \x01(\t\x12\x11\n\trelevance\x18\x03 \x01(\x01\x12\x18\n\x10\x65stimatedResults\x18\x04 \x01(\x03\x12\x17\n\x0f\x61nalyticsCookie\x18\x05 \x01(\t\x12\x0f\n\x07ordered\x18\x06 \x01(\x08\"\x15\n\x13\x46lagContentResponse\"i\n\tDebugInfo\x12\x0f\n\x07message\x18\x01 \x03(\t\x12!\n\x06timing\x18\x02 \x03(\n2\x11.DebugInfo.Timing\x1a(\n\x06Timing\x12\x0c\n\x04name\x18\x03 \x01(\t\x12\x10\n\x08timeInMs\x18\x04 \x01(\x01\"T\n\x10\x44\x65liveryResponse\x12\x0e\n\x06status\x18\x01 \x01(\x05\x12\x30\n\x0f\x61ppDeliveryData\x18\x02 \x01(\x0b\x32\x17.AndroidAppDeliveryData\"\'\n\x10\x42ulkDetailsEntry\x12\x13\n\x03\x64oc\x18\x01 \x01(\x0b\x32\x06.DocV2\"=\n\x12\x42ulkDetailsRequest\x12\r\n\x05\x64ocid\x18\x01 \x03(\t\x12\x18\n\x10includeChildDocs\x18\x02 \x01(\x08\"7\n\x13\x42ulkDetailsResponse\x12 \n\x05\x65ntry\x18\x01 \x03(\x0b\x32\x11.BulkDetailsEntry\"\x89\x01\n\x0f\x44\x65tailsResponse\x12\x15\n\x05\x64ocV1\x18\x01 \x01(\x0b\x32\x06.DocV1\x12\x17\n\x0f\x61nalyticsCookie\x18\x02 \x01(\t\x12\x1b\n\nuserReview\x18\x03 \x01(\x0b\x32\x07.Review\x12\x15\n\x05\x64ocV2\x18\x04 \x01(\x0b\x32\x06.DocV2\x12\x12\n\nfooterHtml\x18\x05 \x01(\t\"\xb5\x03\n\x18\x44\x65viceConfigurationProto\x12\x13\n\x0btouchScreen\x18\x01 \x01(\x05\x12\x10\n\x08keyboard\x18\x02 \x01(\x05\x12\x12\n\nnavigation\x18\x03 \x01(\x05\x12\x14\n\x0cscreenLayout\x18\x04 \x01(\x05\x12\x17\n\x0fhasHardKeyboard\x18\x05 \x01(\x08\x12\x1c\n\x14hasFiveWayNavigation\x18\x06 \x01(\x08\x12\x15\n\rscreenDensity\x18\x07 \x01(\x05\x12\x13\n\x0bglEsVersion\x18\x08 \x01(\x05\x12\x1b\n\x13systemSharedLibrary\x18\t \x03(\t\x12\x1e\n\x16systemAvailableFeature\x18\n \x03(\t\x12\x16\n\x0enativePlatform\x18\x0b \x03(\t\x12\x13\n\x0bscreenWidth\x18\x0c \x01(\x05\x12\x14\n\x0cscreenHeight\x18\r \x01(\x05\x12\x1d\n\x15systemSupportedLocale\x18\x0e \x03(\t\x12\x13\n\x0bglExtension\x18\x0f \x03(\t\x12\x13\n\x0b\x64\x65viceClass\x18\x10 \x01(\x05\x12\x1c\n\x14maxApkDownloadSizeMb\x18\x11 \x01(\x05\"\xff\x03\n\x08\x44ocument\x12\x15\n\x05\x64ocid\x18\x01 \x01(\x0b\x32\x06.Docid\x12\x1a\n\nfetchDocid\x18\x02 \x01(\x0b\x32\x06.Docid\x12\x1b\n\x0bsampleDocid\x18\x03 \x01(\x0b\x32\x06.Docid\x12\r\n\x05title\x18\x04 \x01(\t\x12\x0b\n\x03url\x18\x05 \x01(\t\x12\x0f\n\x07snippet\x18\x06 \x03(\t\x12\x1f\n\x0fpriceDeprecated\x18\x07 \x01(\x0b\x32\x06.Offer\x12#\n\x0c\x61vailability\x18\t \x01(\x0b\x32\r.Availability\x12\x15\n\x05image\x18\n \x03(\x0b\x32\x06.Image\x12\x18\n\x05\x63hild\x18\x0b \x03(\x0b\x32\t.Document\x12)\n\x0f\x61ggregateRating\x18\r \x01(\x0b\x32\x10.AggregateRating\x12\x15\n\x05offer\x18\x0e \x03(\x0b\x32\x06.Offer\x12*\n\x11translatedSnippet\x18\x0f \x03(\x0b\x32\x0f.TranslatedText\x12)\n\x0f\x64ocumentVariant\x18\x10 \x03(\x0b\x32\x10.DocumentVariant\x12\x12\n\ncategoryId\x18\x11 \x03(\t\x12\x1d\n\ndecoration\x18\x12 \x03(\x0b\x32\t.Document\x12\x19\n\x06parent\x18\x13 \x03(\x0b\x32\t.Document\x12\x18\n\x10privacyPolicyUrl\x18\x14 \x01(\t\"\x81\x02\n\x0f\x44ocumentVariant\x12\x15\n\rvariationType\x18\x01 \x01(\x05\x12\x13\n\x04rule\x18\x02 \x01(\x0b\x32\x05.Rule\x12\r\n\x05title\x18\x03 \x01(\t\x12\x0f\n\x07snippet\x18\x04 \x03(\t\x12\x15\n\rrecentChanges\x18\x05 \x01(\t\x12(\n\x0f\x61utoTranslation\x18\x06 \x03(\x0b\x32\x0f.TranslatedText\x12\x15\n\x05offer\x18\x07 \x03(\x0b\x32\x06.Offer\x12\x11\n\tchannelId\x18\t \x01(\x03\x12\x18\n\x05\x63hild\x18\n \x03(\x0b\x32\t.Document\x12\x1d\n\ndecoration\x18\x0b \x03(\x0b\x32\t.Document\"\xba\x02\n\x05Image\x12\x11\n\timageType\x18\x01 \x01(\x05\x12#\n\tdimension\x18\x02 \x01(\n2\x10.Image.Dimension\x12\x10\n\x08imageUrl\x18\x05 \x01(\t\x12\x18\n\x10\x61ltTextLocalized\x18\x06 \x01(\t\x12\x11\n\tsecureUrl\x18\x07 \x01(\t\x12\x1a\n\x12positionInSequence\x18\x08 \x01(\x05\x12\x1e\n\x16supportsFifeUrlOptions\x18\t \x01(\x08\x12!\n\x08\x63itation\x18\n \x01(\n2\x0f.Image.Citation\x1a*\n\tDimension\x12\r\n\x05width\x18\x03 \x01(\x05\x12\x0e\n\x06height\x18\x04 \x01(\x05\x1a/\n\x08\x43itation\x12\x16\n\x0etitleLocalized\x18\x0b \x01(\t\x12\x0b\n\x03url\x18\x0c \x01(\t\"J\n\x0eTranslatedText\x12\x0c\n\x04text\x18\x01 \x01(\t\x12\x14\n\x0csourceLocale\x18\x02 \x01(\t\x12\x14\n\x0ctargetLocale\x18\x03 \x01(\t\"@\n\x05\x42\x61\x64ge\x12\r\n\x05title\x18\x01 \x01(\t\x12\x15\n\x05image\x18\x02 \x03(\x0b\x32\x06.Image\x12\x11\n\tbrowseUrl\x18\x03 \x01(\t\"-\n\x13\x43ontainerWithBanner\x12\x16\n\x0e\x63olorThemeArgb\x18\x01 \x01(\t\">\n\x0c\x44\x65\x61lOfTheDay\x12\x16\n\x0e\x66\x65\x61turedHeader\x18\x01 \x01(\t\x12\x16\n\x0e\x63olorThemeArgb\x18\x02 \x01(\t\"\x8e\x01\n\x18\x45\x64itorialSeriesContainer\x12\x13\n\x0bseriesTitle\x18\x01 \x01(\t\x12\x16\n\x0eseriesSubtitle\x18\x02 \x01(\t\x12\x14\n\x0c\x65pisodeTitle\x18\x03 \x01(\t\x12\x17\n\x0f\x65pisodeSubtitle\x18\x04 \x01(\t\x12\x16\n\x0e\x63olorThemeArgb\x18\x05 \x01(\t\"\x13\n\x04Link\x12\x0b\n\x03uri\x18\x01 \x01(\t\"i\n\x0bPlusOneData\x12\x11\n\tsetByUser\x18\x01 \x01(\x08\x12\r\n\x05total\x18\x02 \x01(\x03\x12\x14\n\x0c\x63irclesTotal\x18\x03 \x01(\x03\x12\"\n\rcirclesPeople\x18\x04 \x03(\x0b\x32\x0b.PlusPerson\":\n\nPlusPerson\x12\x13\n\x0b\x64isplayName\x18\x02 \x01(\t\x12\x17\n\x0fprofileImageUrl\x18\x04 \x01(\t\"r\n\x0bPromotedDoc\x12\r\n\x05title\x18\x01 \x01(\t\x12\x10\n\x08subtitle\x18\x02 \x01(\t\x12\x15\n\x05image\x18\x03 \x03(\x0b\x32\x06.Image\x12\x17\n\x0f\x64\x65scriptionHtml\x18\x04 \x01(\t\x12\x12\n\ndetailsUrl\x18\x05 \x01(\t\"G\n\x06Reason\x12\x13\n\x0b\x62riefReason\x18\x01 \x01(\t\x12\x16\n\x0e\x64\x65tailedReason\x18\x02 \x01(\t\x12\x10\n\x08uniqueId\x18\x03 \x01(\t\"^\n\x0fSectionMetadata\x12\x0e\n\x06header\x18\x01 \x01(\t\x12\x0f\n\x07listUrl\x18\x02 \x01(\t\x12\x11\n\tbrowseUrl\x18\x03 \x01(\t\x12\x17\n\x0f\x64\x65scriptionHtml\x18\x04 \x01(\t\"\xd5\x01\n\rSeriesAntenna\x12\x13\n\x0bseriesTitle\x18\x01 \x01(\t\x12\x16\n\x0eseriesSubtitle\x18\x02 \x01(\t\x12\x14\n\x0c\x65pisodeTitle\x18\x03 \x01(\t\x12\x17\n\x0f\x65pisodeSubtitle\x18\x04 \x01(\t\x12\x16\n\x0e\x63olorThemeArgb\x18\x05 \x01(\t\x12\'\n\rsectionTracks\x18\x06 \x01(\x0b\x32\x10.SectionMetadata\x12\'\n\rsectionAlbums\x18\x07 \x01(\x0b\x32\x10.SectionMetadata\"\x8f\x04\n\x08Template\x12%\n\rseriesAntenna\x18\x01 \x01(\x0b\x32\x0e.SeriesAntenna\x12%\n\x0etileGraphic2X1\x18\x02 \x01(\x0b\x32\r.TileTemplate\x12%\n\x0etileGraphic4X2\x18\x03 \x01(\x0b\x32\r.TileTemplate\x12\x31\n\x1atileGraphicColoredTitle2X1\x18\x04 \x01(\x0b\x32\r.TileTemplate\x12\x33\n\x1ctileGraphicUpperLeftTitle2X1\x18\x05 \x01(\x0b\x32\r.TileTemplate\x12\x35\n\x1etileDetailsReflectedGraphic2X2\x18\x06 \x01(\x0b\x32\r.TileTemplate\x12\'\n\x10tileFourBlock4X2\x18\x07 \x01(\x0b\x32\r.TileTemplate\x12\x31\n\x13\x63ontainerWithBanner\x18\x08 \x01(\x0b\x32\x14.ContainerWithBanner\x12#\n\x0c\x64\x65\x61lOfTheDay\x18\t \x01(\x0b\x32\r.DealOfTheDay\x12\x31\n\x1atileGraphicColoredTitle4X2\x18\n \x01(\x0b\x32\r.TileTemplate\x12;\n\x18\x65\x64itorialSeriesContainer\x18\x0b \x01(\x0b\x32\x19.EditorialSeriesContainer\"=\n\x0cTileTemplate\x12\x16\n\x0e\x63olorThemeArgb\x18\x01 \x01(\t\x12\x15\n\rcolorTextArgb\x18\x02 \x01(\t\"#\n\x07Warning\x12\x18\n\x10localizedMessage\x18\x01 \x01(\t\"c\n\x0c\x41lbumDetails\x12\x0c\n\x04name\x18\x01 \x01(\t\x12\x1e\n\x07\x64\x65tails\x18\x02 \x01(\x0b\x32\r.MusicDetails\x12%\n\rdisplayArtist\x18\x03 \x01(\x0b\x32\x0e.ArtistDetails\"\x8e\x03\n\nAppDetails\x12\x15\n\rdeveloperName\x18\x01 \x01(\t\x12\x1a\n\x12majorVersionNumber\x18\x02 \x01(\x05\x12\x13\n\x0bversionCode\x18\x03 \x01(\x05\x12\x15\n\rversionString\x18\x04 \x01(\t\x12\r\n\x05title\x18\x05 \x01(\t\x12\x13\n\x0b\x61ppCategory\x18\x07 \x03(\t\x12\x15\n\rcontentRating\x18\x08 \x01(\x05\x12\x18\n\x10installationSize\x18\t \x01(\x03\x12\x12\n\npermission\x18\n \x03(\t\x12\x16\n\x0e\x64\x65veloperEmail\x18\x0b \x01(\t\x12\x18\n\x10\x64\x65veloperWebsite\x18\x0c \x01(\t\x12\x14\n\x0cnumDownloads\x18\r \x01(\t\x12\x13\n\x0bpackageName\x18\x0e \x01(\t\x12\x19\n\x11recentChangesHtml\x18\x0f \x01(\t\x12\x12\n\nuploadDate\x18\x10 \x01(\t\x12\x1b\n\x04\x66ile\x18\x11 \x03(\x0b\x32\r.FileMetadata\x12\x0f\n\x07\x61ppType\x18\x12 \x01(\t\"^\n\rArtistDetails\x12\x12\n\ndetailsUrl\x18\x01 \x01(\t\x12\x0c\n\x04name\x18\x02 \x01(\t\x12+\n\rexternalLinks\x18\x03 \x01(\x0b\x32\x14.ArtistExternalLinks\"b\n\x13\x41rtistExternalLinks\x12\x12\n\nwebsiteUrl\x18\x01 \x03(\t\x12\x1c\n\x14googlePlusProfileUrl\x18\x02 \x01(\t\x12\x19\n\x11youtubeChannelUrl\x18\x03 \x01(\t\"\xc6\x03\n\x0f\x44ocumentDetails\x12\x1f\n\nappDetails\x18\x01 \x01(\x0b\x32\x0b.AppDetails\x12#\n\x0c\x61lbumDetails\x18\x02 \x01(\x0b\x32\r.AlbumDetails\x12%\n\rartistDetails\x18\x03 \x01(\x0b\x32\x0e.ArtistDetails\x12!\n\x0bsongDetails\x18\x04 \x01(\x0b\x32\x0c.SongDetails\x12!\n\x0b\x62ookDetails\x18\x05 \x01(\x0b\x32\x0c.BookDetails\x12#\n\x0cvideoDetails\x18\x06 \x01(\x0b\x32\r.VideoDetails\x12\x31\n\x13subscriptionDetails\x18\x07 \x01(\x0b\x32\x14.SubscriptionDetails\x12)\n\x0fmagazineDetails\x18\x08 \x01(\x0b\x32\x10.MagazineDetails\x12%\n\rtvShowDetails\x18\t \x01(\x0b\x32\x0e.TvShowDetails\x12)\n\x0ftvSeasonDetails\x18\n \x01(\x0b\x32\x10.TvSeasonDetails\x12+\n\x10tvEpisodeDetails\x18\x0b \x01(\x0b\x32\x11.TvEpisodeDetails\"C\n\x0c\x46ileMetadata\x12\x10\n\x08\x66ileType\x18\x01 \x01(\x05\x12\x13\n\x0bversionCode\x18\x02 \x01(\x05\x12\x0c\n\x04size\x18\x03 \x01(\x03\"\x94\x01\n\x0fMagazineDetails\x12\x18\n\x10parentDetailsUrl\x18\x01 \x01(\t\x12)\n!deviceAvailabilityDescriptionHtml\x18\x02 \x01(\t\x12\x16\n\x0epsvDescription\x18\x03 \x01(\t\x12$\n\x1c\x64\x65liveryFrequencyDescription\x18\x04 \x01(\t\"\xbb\x01\n\x0cMusicDetails\x12\x11\n\tcensoring\x18\x01 \x01(\x05\x12\x13\n\x0b\x64urationSec\x18\x02 \x01(\x05\x12\x1b\n\x13originalReleaseDate\x18\x03 \x01(\t\x12\r\n\x05label\x18\x04 \x01(\t\x12\x1e\n\x06\x61rtist\x18\x05 \x03(\x0b\x32\x0e.ArtistDetails\x12\r\n\x05genre\x18\x06 \x03(\t\x12\x13\n\x0breleaseDate\x18\x07 \x01(\t\x12\x13\n\x0breleaseType\x18\x08 \x03(\x05\"\x9e\x01\n\x0bSongDetails\x12\x0c\n\x04name\x18\x01 \x01(\t\x12\x1e\n\x07\x64\x65tails\x18\x02 \x01(\x0b\x32\r.MusicDetails\x12\x11\n\talbumName\x18\x03 \x01(\t\x12\x13\n\x0btrackNumber\x18\x04 \x01(\x05\x12\x12\n\npreviewUrl\x18\x05 \x01(\t\x12%\n\rdisplayArtist\x18\x06 \x01(\x0b\x32\x0e.ArtistDetails\"1\n\x13SubscriptionDetails\x12\x1a\n\x12subscriptionPeriod\x18\x01 \x01(\x05\"e\n\x07Trailer\x12\x11\n\ttrailerId\x18\x01 \x01(\t\x12\r\n\x05title\x18\x02 \x01(\t\x12\x14\n\x0cthumbnailUrl\x18\x03 \x01(\t\x12\x10\n\x08watchUrl\x18\x04 \x01(\t\x12\x10\n\x08\x64uration\x18\x05 \x01(\t\"W\n\x10TvEpisodeDetails\x12\x18\n\x10parentDetailsUrl\x18\x01 \x01(\t\x12\x14\n\x0c\x65pisodeIndex\x18\x02 \x01(\x05\x12\x13\n\x0breleaseDate\x18\x03 \x01(\t\"j\n\x0fTvSeasonDetails\x12\x18\n\x10parentDetailsUrl\x18\x01 \x01(\t\x12\x13\n\x0bseasonIndex\x18\x02 \x01(\x05\x12\x13\n\x0breleaseDate\x18\x03 \x01(\t\x12\x13\n\x0b\x62roadcaster\x18\x04 \x01(\t\"]\n\rTvShowDetails\x12\x13\n\x0bseasonCount\x18\x01 \x01(\x05\x12\x11\n\tstartYear\x18\x02 \x01(\x05\x12\x0f\n\x07\x65ndYear\x18\x03 \x01(\x05\x12\x13\n\x0b\x62roadcaster\x18\x04 \x01(\t\"?\n\x0bVideoCredit\x12\x12\n\ncreditType\x18\x01 \x01(\x05\x12\x0e\n\x06\x63redit\x18\x02 \x01(\t\x12\x0c\n\x04name\x18\x03 \x03(\t\"\xdb\x01\n\x0cVideoDetails\x12\x1c\n\x06\x63redit\x18\x01 \x03(\x0b\x32\x0c.VideoCredit\x12\x10\n\x08\x64uration\x18\x02 \x01(\t\x12\x13\n\x0breleaseDate\x18\x03 \x01(\t\x12\x15\n\rcontentRating\x18\x04 \x01(\t\x12\r\n\x05likes\x18\x05 \x01(\x03\x12\x10\n\x08\x64islikes\x18\x06 \x01(\x03\x12\r\n\x05genre\x18\x07 \x03(\t\x12\x19\n\x07trailer\x18\x08 \x03(\x0b\x32\x08.Trailer\x12$\n\nrentalTerm\x18\t \x03(\x0b\x32\x10.VideoRentalTerm\"\xa0\x01\n\x0fVideoRentalTerm\x12\x11\n\tofferType\x18\x01 \x01(\x05\x12\x19\n\x11offerAbbreviation\x18\x02 \x01(\t\x12\x14\n\x0crentalHeader\x18\x03 \x01(\t\x12#\n\x04term\x18\x04 \x03(\n2\x15.VideoRentalTerm.Term\x1a$\n\x04Term\x12\x0e\n\x06header\x18\x05 \x01(\t\x12\x0c\n\x04\x62ody\x18\x06 \x01(\t\"\xf9\x01\n\x06\x42ucket\x12\x18\n\x08\x64ocument\x18\x01 \x03(\x0b\x32\x06.DocV1\x12\x13\n\x0bmultiCorpus\x18\x02 \x01(\x08\x12\r\n\x05title\x18\x03 \x01(\t\x12\x0f\n\x07iconUrl\x18\x04 \x01(\t\x12\x17\n\x0f\x66ullContentsUrl\x18\x05 \x01(\t\x12\x11\n\trelevance\x18\x06 \x01(\x01\x12\x18\n\x10\x65stimatedResults\x18\x07 \x01(\x03\x12\x17\n\x0f\x61nalyticsCookie\x18\x08 \x01(\t\x12\x1b\n\x13\x66ullContentsListUrl\x18\t \x01(\t\x12\x13\n\x0bnextPageUrl\x18\n \x01(\t\x12\x0f\n\x07ordered\x18\x0b \x01(\x08\"<\n\x0cListResponse\x12\x17\n\x06\x62ucket\x18\x01 \x03(\x0b\x32\x07.Bucket\x12\x13\n\x03\x64oc\x18\x02 \x03(\x0b\x32\x06.DocV2\"\x94\x03\n\x05\x44ocV1\x12\x1c\n\tfinskyDoc\x18\x01 \x01(\x0b\x32\t.Document\x12\r\n\x05\x64ocid\x18\x02 \x01(\t\x12\x12\n\ndetailsUrl\x18\x03 \x01(\t\x12\x12\n\nreviewsUrl\x18\x04 \x01(\t\x12\x16\n\x0erelatedListUrl\x18\x05 \x01(\t\x12\x15\n\rmoreByListUrl\x18\x06 \x01(\t\x12\x10\n\x08shareUrl\x18\x07 \x01(\t\x12\x0f\n\x07\x63reator\x18\x08 \x01(\t\x12!\n\x07\x64\x65tails\x18\t \x01(\x0b\x32\x10.DocumentDetails\x12\x17\n\x0f\x64\x65scriptionHtml\x18\n \x01(\t\x12\x18\n\x10relatedBrowseUrl\x18\x0b \x01(\t\x12\x17\n\x0fmoreByBrowseUrl\x18\x0c \x01(\t\x12\x15\n\rrelatedHeader\x18\r \x01(\t\x12\x14\n\x0cmoreByHeader\x18\x0e \x01(\t\x12\r\n\x05title\x18\x0f \x01(\t\x12!\n\x0bplusOneData\x18\x10 \x01(\x0b\x32\x0c.PlusOneData\x12\x16\n\x0ewarningMessage\x18\x11 \x01(\t\"\xcd\x04\n\x0b\x41nnotations\x12(\n\x0esectionRelated\x18\x01 \x01(\x0b\x32\x10.SectionMetadata\x12\'\n\rsectionMoreBy\x18\x02 \x01(\x0b\x32\x10.SectionMetadata\x12!\n\x0bplusOneData\x18\x03 \x01(\x0b\x32\x0c.PlusOneData\x12\x19\n\x07warning\x18\x04 \x03(\x0b\x32\x08.Warning\x12+\n\x11sectionBodyOfWork\x18\x05 \x01(\x0b\x32\x10.SectionMetadata\x12,\n\x12sectionCoreContent\x18\x06 \x01(\x0b\x32\x10.SectionMetadata\x12\x1b\n\x08template\x18\x07 \x01(\x0b\x32\t.Template\x12\x1f\n\x0f\x62\x61\x64geForCreator\x18\x08 \x03(\x0b\x32\x06.Badge\x12\x1b\n\x0b\x62\x61\x64geForDoc\x18\t \x03(\x0b\x32\x06.Badge\x12\x13\n\x04link\x18\n \x01(\x0b\x32\x05.Link\x12*\n\x10sectionCrossSell\x18\x0b \x01(\x0b\x32\x10.SectionMetadata\x12/\n\x15sectionRelatedDocType\x18\x0c \x01(\x0b\x32\x10.SectionMetadata\x12!\n\x0bpromotedDoc\x18\r \x03(\x0b\x32\x0c.PromotedDoc\x12\x11\n\tofferNote\x18\x0e \x01(\t\x12\x1c\n\x0csubscription\x18\x10 \x03(\x0b\x32\x06.DocV2\x12\x17\n\x06reason\x18\x11 \x01(\x0b\x32\x07.Reason\x12\x18\n\x10privacyPolicyUrl\x18\x12 \x01(\t\"\xa8\x04\n\x05\x44ocV2\x12\r\n\x05\x64ocid\x18\x01 \x01(\t\x12\x14\n\x0c\x62\x61\x63kendDocid\x18\x02 \x01(\t\x12\x0f\n\x07\x64ocType\x18\x03 \x01(\x05\x12\x11\n\tbackendId\x18\x04 \x01(\x05\x12\r\n\x05title\x18\x05 \x01(\t\x12\x0f\n\x07\x63reator\x18\x06 \x01(\t\x12\x17\n\x0f\x64\x65scriptionHtml\x18\x07 \x01(\t\x12\x15\n\x05offer\x18\x08 \x03(\x0b\x32\x06.Offer\x12#\n\x0c\x61vailability\x18\t \x01(\x0b\x32\r.Availability\x12\x15\n\x05image\x18\n \x03(\x0b\x32\x06.Image\x12\x15\n\x05\x63hild\x18\x0b \x03(\x0b\x32\x06.DocV2\x12-\n\x11\x63ontainerMetadata\x18\x0c \x01(\x0b\x32\x12.ContainerMetadata\x12!\n\x07\x64\x65tails\x18\r \x01(\x0b\x32\x10.DocumentDetails\x12)\n\x0f\x61ggregateRating\x18\x0e \x01(\x0b\x32\x10.AggregateRating\x12!\n\x0b\x61nnotations\x18\x0f \x01(\x0b\x32\x0c.Annotations\x12\x12\n\ndetailsUrl\x18\x10 \x01(\t\x12\x10\n\x08shareUrl\x18\x11 \x01(\t\x12\x12\n\nreviewsUrl\x18\x12 \x01(\t\x12\x12\n\nbackendUrl\x18\x13 \x01(\t\x12\x1a\n\x12purchaseDetailsUrl\x18\x14 \x01(\t\x12\x17\n\x0f\x64\x65tailsReusable\x18\x15 \x01(\x08\x12\x10\n\x08subtitle\x18\x16 \x01(\t\"\x99\x01\n\x17\x45ncryptedSubscriberInfo\x12\x0c\n\x04\x64\x61ta\x18\x01 \x01(\t\x12\x14\n\x0c\x65ncryptedKey\x18\x02 \x01(\t\x12\x11\n\tsignature\x18\x03 \x01(\t\x12\x12\n\ninitVector\x18\x04 \x01(\t\x12\x18\n\x10googleKeyVersion\x18\x05 \x01(\x05\x12\x19\n\x11\x63\x61rrierKeyVersion\x18\x06 \x01(\x05\"\xbd\x03\n\x0c\x41vailability\x12\x13\n\x0brestriction\x18\x05 \x01(\x05\x12\x11\n\tofferType\x18\x06 \x01(\x05\x12\x13\n\x04rule\x18\x07 \x01(\x0b\x32\x05.Rule\x12X\n perdeviceavailabilityrestriction\x18\t \x03(\n2..Availability.PerDeviceAvailabilityRestriction\x12\x18\n\x10\x61vailableIfOwned\x18\r \x01(\x08\x12\x19\n\x07install\x18\x0e \x03(\x0b\x32\x08.Install\x12)\n\nfilterInfo\x18\x10 \x01(\x0b\x32\x15.FilterEvaluationInfo\x12%\n\rownershipInfo\x18\x11 \x01(\x0b\x32\x0e.OwnershipInfo\x1a\x8e\x01\n PerDeviceAvailabilityRestriction\x12\x11\n\tandroidId\x18\n \x01(\x06\x12\x19\n\x11\x64\x65viceRestriction\x18\x0b \x01(\x05\x12\x11\n\tchannelId\x18\x0c \x01(\x03\x12)\n\nfilterInfo\x18\x0f \x01(\x0b\x32\x15.FilterEvaluationInfo\"?\n\x14\x46ilterEvaluationInfo\x12\'\n\x0eruleEvaluation\x18\x01 \x03(\x0b\x32\x0f.RuleEvaluation\"\xd4\x01\n\x04Rule\x12\x0e\n\x06negate\x18\x01 \x01(\x08\x12\x10\n\x08operator\x18\x02 \x01(\x05\x12\x0b\n\x03key\x18\x03 \x01(\x05\x12\x11\n\tstringArg\x18\x04 \x03(\t\x12\x0f\n\x07longArg\x18\x05 \x03(\x03\x12\x11\n\tdoubleArg\x18\x06 \x03(\x01\x12\x16\n\x07subrule\x18\x07 \x03(\x0b\x32\x05.Rule\x12\x14\n\x0cresponseCode\x18\x08 \x01(\x05\x12\x0f\n\x07\x63omment\x18\t \x01(\t\x12\x15\n\rstringArgHash\x18\n \x03(\x06\x12\x10\n\x08\x63onstArg\x18\x0b \x03(\x05\"\x8d\x01\n\x0eRuleEvaluation\x12\x13\n\x04rule\x18\x01 \x01(\x0b\x32\x05.Rule\x12\x19\n\x11\x61\x63tualStringValue\x18\x02 \x03(\t\x12\x17\n\x0f\x61\x63tualLongValue\x18\x03 \x03(\x03\x12\x17\n\x0f\x61\x63tualBoolValue\x18\x04 \x03(\x08\x12\x19\n\x11\x61\x63tualDoubleValue\x18\x05 \x03(\x01\"v\n\x11LibraryAppDetails\x12\x17\n\x0f\x63\x65rtificateHash\x18\x02 \x01(\t\x12\"\n\x1arefundTimeoutTimestampMsec\x18\x03 \x01(\x03\x12$\n\x1cpostDeliveryRefundWindowMsec\x18\x04 \x01(\x03\"\xc4\x01\n\x0fLibraryMutation\x12\x15\n\x05\x64ocid\x18\x01 \x01(\x0b\x32\x06.Docid\x12\x11\n\tofferType\x18\x02 \x01(\x05\x12\x14\n\x0c\x64ocumentHash\x18\x03 \x01(\x03\x12\x0f\n\x07\x64\x65leted\x18\x04 \x01(\x08\x12&\n\nappDetails\x18\x05 \x01(\x0b\x32\x12.LibraryAppDetails\x12\x38\n\x13subscriptionDetails\x18\x06 \x01(\x0b\x32\x1b.LibrarySubscriptionDetails\"\x95\x01\n\x1aLibrarySubscriptionDetails\x12\x1f\n\x17initiationTimestampMsec\x18\x01 \x01(\x03\x12\x1f\n\x17validUntilTimestampMsec\x18\x02 \x01(\x03\x12\x14\n\x0c\x61utoRenewing\x18\x03 \x01(\x08\x12\x1f\n\x17trialUntilTimestampMsec\x18\x04 \x01(\x03\"\x8c\x01\n\rLibraryUpdate\x12\x0e\n\x06status\x18\x01 \x01(\x05\x12\x0e\n\x06\x63orpus\x18\x02 \x01(\x05\x12\x13\n\x0bserverToken\x18\x03 \x01(\x0c\x12\"\n\x08mutation\x18\x04 \x03(\x0b\x32\x10.LibraryMutation\x12\x0f\n\x07hasMore\x18\x05 \x01(\x08\x12\x11\n\tlibraryId\x18\x06 \x01(\t\"c\n\x12\x43lientLibraryState\x12\x0e\n\x06\x63orpus\x18\x01 \x01(\x05\x12\x13\n\x0bserverToken\x18\x02 \x01(\x0c\x12\x13\n\x0bhashCodeSum\x18\x03 \x01(\x03\x12\x13\n\x0blibrarySize\x18\x04 \x01(\x05\"F\n\x19LibraryReplicationRequest\x12)\n\x0clibraryState\x18\x01 \x03(\x0b\x32\x13.ClientLibraryState\"<\n\x1aLibraryReplicationResponse\x12\x1e\n\x06update\x18\x01 \x03(\x0b\x32\x0e.LibraryUpdate\"l\n\rClickLogEvent\x12\x11\n\teventTime\x18\x01 \x01(\x03\x12\x0b\n\x03url\x18\x02 \x01(\t\x12\x0e\n\x06listId\x18\x03 \x01(\t\x12\x13\n\x0breferrerUrl\x18\x04 \x01(\t\x12\x16\n\x0ereferrerListId\x18\x05 \x01(\t\"0\n\nLogRequest\x12\"\n\nclickEvent\x18\x01 \x03(\x0b\x32\x0e.ClickLogEvent\"\r\n\x0bLogResponse\"B\n\x1a\x41ndroidAppNotificationData\x12\x13\n\x0bversionCode\x18\x01 \x01(\x05\x12\x0f\n\x07\x61ssetId\x18\x02 \x01(\t\"M\n\x15InAppNotificationData\x12\x17\n\x0f\x63heckoutOrderId\x18\x01 \x01(\t\x12\x1b\n\x13inAppNotificationId\x18\x02 \x01(\t\"#\n\x10LibraryDirtyData\x12\x0f\n\x07\x62\x61\x63kend\x18\x01 \x01(\x05\"\x97\x04\n\x0cNotification\x12\x18\n\x10notificationType\x18\x01 \x01(\x05\x12\x11\n\ttimestamp\x18\x03 \x01(\x03\x12\x15\n\x05\x64ocid\x18\x04 \x01(\x0b\x32\x06.Docid\x12\x10\n\x08\x64ocTitle\x18\x05 \x01(\t\x12\x11\n\tuserEmail\x18\x06 \x01(\t\x12,\n\x07\x61ppData\x18\x07 \x01(\x0b\x32\x1b.AndroidAppNotificationData\x12\x30\n\x0f\x61ppDeliveryData\x18\x08 \x01(\x0b\x32\x17.AndroidAppDeliveryData\x12\x31\n\x13purchaseRemovalData\x18\t \x01(\x0b\x32\x14.PurchaseRemovalData\x12\x33\n\x14userNotificationData\x18\n \x01(\x0b\x32\x15.UserNotificationData\x12\x35\n\x15inAppNotificationData\x18\x0b \x01(\x0b\x32\x16.InAppNotificationData\x12\x33\n\x14purchaseDeclinedData\x18\x0c \x01(\x0b\x32\x15.PurchaseDeclinedData\x12\x16\n\x0enotificationId\x18\r \x01(\t\x12%\n\rlibraryUpdate\x18\x0e \x01(\x0b\x32\x0e.LibraryUpdate\x12+\n\x10libraryDirtyData\x18\x0f \x01(\x0b\x32\x11.LibraryDirtyData\"@\n\x14PurchaseDeclinedData\x12\x0e\n\x06reason\x18\x01 \x01(\x05\x12\x18\n\x10showNotification\x18\x02 \x01(\x08\"(\n\x13PurchaseRemovalData\x12\x11\n\tmalicious\x18\x01 \x01(\x08\"\x88\x01\n\x14UserNotificationData\x12\x19\n\x11notificationTitle\x18\x01 \x01(\t\x12\x18\n\x10notificationText\x18\x02 \x01(\t\x12\x12\n\ntickerText\x18\x03 \x01(\t\x12\x13\n\x0b\x64ialogTitle\x18\x04 \x01(\t\x12\x12\n\ndialogText\x18\x05 \x01(\t\"\x11\n\x0fPlusOneResponse\"\x1e\n\x1cRateSuggestedContentResponse\"\xa7\x02\n\x0f\x41ggregateRating\x12\x0c\n\x04type\x18\x01 \x01(\x05\x12\x12\n\nstarRating\x18\x02 \x01(\x02\x12\x14\n\x0cratingsCount\x18\x03 \x01(\x04\x12\x16\n\x0eoneStarRatings\x18\x04 \x01(\x04\x12\x16\n\x0etwoStarRatings\x18\x05 \x01(\x04\x12\x18\n\x10threeStarRatings\x18\x06 \x01(\x04\x12\x17\n\x0f\x66ourStarRatings\x18\x07 \x01(\x04\x12\x17\n\x0f\x66iveStarRatings\x18\x08 \x01(\x04\x12\x15\n\rthumbsUpCount\x18\t \x01(\x04\x12\x17\n\x0fthumbsDownCount\x18\n \x01(\x04\x12\x14\n\x0c\x63ommentCount\x18\x0b \x01(\x04\x12\x1a\n\x12\x62\x61yesianMeanRating\x18\x0c \x01(\x01\"c\n\x0e\x44irectPurchase\x12\x12\n\ndetailsUrl\x18\x01 \x01(\t\x12\x15\n\rpurchaseDocid\x18\x02 \x01(\t\x12\x13\n\x0bparentDocid\x18\x03 \x01(\t\x12\x11\n\tofferType\x18\x04 \x01(\x05\"\x89\x01\n\x13ResolveLinkResponse\x12\x12\n\ndetailsUrl\x18\x01 \x01(\t\x12\x11\n\tbrowseUrl\x18\x02 \x01(\t\x12\x11\n\tsearchUrl\x18\x03 \x01(\t\x12\'\n\x0e\x64irectPurchase\x18\x04 \x01(\x0b\x32\x0f.DirectPurchase\x12\x0f\n\x07homeUrl\x18\x05 \x01(\t\"\xb5\t\n\x07Payload\x12#\n\x0clistResponse\x18\x01 \x01(\x0b\x32\r.ListResponse\x12)\n\x0f\x64\x65tailsResponse\x18\x02 \x01(\x0b\x32\x10.DetailsResponse\x12\'\n\x0ereviewResponse\x18\x03 \x01(\x0b\x32\x0f.ReviewResponse\x12!\n\x0b\x62uyResponse\x18\x04 \x01(\x0b\x32\x0c.BuyResponse\x12\'\n\x0esearchResponse\x18\x05 \x01(\x0b\x32\x0f.SearchResponse\x12!\n\x0btocResponse\x18\x06 \x01(\x0b\x32\x0c.TocResponse\x12\'\n\x0e\x62rowseResponse\x18\x07 \x01(\x0b\x32\x0f.BrowseResponse\x12\x37\n\x16purchaseStatusResponse\x18\x08 \x01(\x0b\x32\x17.PurchaseStatusResponse\x12;\n\x18updateInstrumentResponse\x18\t \x01(\x0b\x32\x19.UpdateInstrumentResponse\x12!\n\x0blogResponse\x18\n \x01(\x0b\x32\x0c.LogResponse\x12\x39\n\x17\x63heckInstrumentResponse\x18\x0b \x01(\x0b\x32\x18.CheckInstrumentResponse\x12)\n\x0fplusOneResponse\x18\x0c \x01(\x0b\x32\x10.PlusOneResponse\x12\x31\n\x13\x66lagContentResponse\x18\r \x01(\x0b\x32\x14.FlagContentResponse\x12\x39\n\x17\x61\x63kNotificationResponse\x18\x0e \x01(\x0b\x32\x18.AckNotificationResponse\x12\x41\n\x1binitiateAssociationResponse\x18\x0f \x01(\x0b\x32\x1c.InitiateAssociationResponse\x12=\n\x19verifyAssociationResponse\x18\x10 \x01(\x0b\x32\x1a.VerifyAssociationResponse\x12?\n\x1alibraryReplicationResponse\x18\x11 \x01(\x0b\x32\x1b.LibraryReplicationResponse\x12\'\n\x0erevokeResponse\x18\x12 \x01(\x0b\x32\x0f.RevokeResponse\x12\x31\n\x13\x62ulkDetailsResponse\x18\x13 \x01(\x0b\x32\x14.BulkDetailsResponse\x12\x31\n\x13resolveLinkResponse\x18\x14 \x01(\x0b\x32\x14.ResolveLinkResponse\x12+\n\x10\x64\x65liveryResponse\x18\x15 \x01(\x0b\x32\x11.DeliveryResponse\x12-\n\x11\x61\x63\x63\x65ptTosResponse\x18\x16 \x01(\x0b\x32\x12.AcceptTosResponse\x12\x43\n\x1crateSuggestedContentResponse\x18\x17 \x01(\x0b\x32\x1d.RateSuggestedContentResponse\x12\x39\n\x17\x63heckPromoOfferResponse\x18\x18 \x01(\x0b\x32\x18.CheckPromoOfferResponse\"U\n\x08PreFetch\x12\x0b\n\x03url\x18\x01 \x01(\t\x12\x10\n\x08response\x18\x02 \x01(\x0c\x12\x0c\n\x04\x65tag\x18\x03 \x01(\t\x12\x0b\n\x03ttl\x18\x04 \x01(\x03\x12\x0f\n\x07softTtl\x18\x05 \x01(\x03\"\x91\x01\n\x0fResponseWrapper\x12\x19\n\x07payload\x18\x01 \x01(\x0b\x32\x08.Payload\x12!\n\x08\x63ommands\x18\x02 \x01(\x0b\x32\x0f.ServerCommands\x12\x1b\n\x08preFetch\x18\x03 \x03(\x0b\x32\t.PreFetch\x12#\n\x0cnotification\x18\x04 \x03(\x0b\x32\r.Notification\"]\n\x0eServerCommands\x12\x12\n\nclearCache\x18\x01 \x01(\x08\x12\x1b\n\x13\x64isplayErrorMessage\x18\x02 \x01(\t\x12\x1a\n\x12logErrorStacktrace\x18\x03 \x01(\t\"D\n\x12GetReviewsResponse\x12\x17\n\x06review\x18\x01 \x03(\x0b\x32\x07.Review\x12\x15\n\rmatchingCount\x18\x02 \x01(\x03\"\xf3\x01\n\x06Review\x12\x12\n\nauthorName\x18\x01 \x01(\t\x12\x0b\n\x03url\x18\x02 \x01(\t\x12\x0e\n\x06source\x18\x03 \x01(\t\x12\x17\n\x0f\x64ocumentVersion\x18\x04 \x01(\t\x12\x15\n\rtimestampMsec\x18\x05 \x01(\x03\x12\x12\n\nstarRating\x18\x06 \x01(\x05\x12\r\n\x05title\x18\x07 \x01(\t\x12\x0f\n\x07\x63omment\x18\x08 \x01(\t\x12\x11\n\tcommentId\x18\t \x01(\t\x12\x12\n\ndeviceName\x18\x13 \x01(\t\x12\x11\n\treplyText\x18\x1d \x01(\t\x12\x1a\n\x12replyTimestampMsec\x18\x1e \x01(\x03\"O\n\x0eReviewResponse\x12(\n\x0bgetResponse\x18\x01 \x01(\x0b\x32\x13.GetReviewsResponse\x12\x13\n\x0bnextPageUrl\x18\x02 \x01(\t\"7\n\x0eRevokeResponse\x12%\n\rlibraryUpdate\x18\x01 \x01(\x0b\x32\x0e.LibraryUpdate\"g\n\rRelatedSearch\x12\x11\n\tsearchUrl\x18\x01 \x01(\t\x12\x0e\n\x06header\x18\x02 \x01(\t\x12\x11\n\tbackendId\x18\x03 \x01(\x05\x12\x0f\n\x07\x64ocType\x18\x04 \x01(\x05\x12\x0f\n\x07\x63urrent\x18\x05 \x01(\x08\"\xac\x01\n\x0eSearchResponse\x12\x15\n\roriginalQuery\x18\x01 \x01(\t\x12\x16\n\x0esuggestedQuery\x18\x02 \x01(\t\x12\x16\n\x0e\x61ggregateQuery\x18\x03 \x01(\x08\x12\x17\n\x06\x62ucket\x18\x04 \x03(\x0b\x32\x07.Bucket\x12\x13\n\x03\x64oc\x18\x05 \x03(\x0b\x32\x06.DocV2\x12%\n\rrelatedSearch\x18\x06 \x03(\x0b\x32\x0e.RelatedSearch\"X\n\x0e\x43orpusMetadata\x12\x0f\n\x07\x62\x61\x63kend\x18\x01 \x01(\x05\x12\x0c\n\x04name\x18\x02 \x01(\t\x12\x12\n\nlandingUrl\x18\x03 \x01(\t\x12\x13\n\x0blibraryName\x18\x04 \x01(\t\"#\n\x0b\x45xperiments\x12\x14\n\x0c\x65xperimentId\x18\x01 \x03(\t\"\x8c\x02\n\x0bTocResponse\x12\x1f\n\x06\x63orpus\x18\x01 \x03(\x0b\x32\x0f.CorpusMetadata\x12\x1c\n\x14tosVersionDeprecated\x18\x02 \x01(\x05\x12\x12\n\ntosContent\x18\x03 \x01(\t\x12\x0f\n\x07homeUrl\x18\x04 \x01(\t\x12!\n\x0b\x65xperiments\x18\x05 \x01(\x0b\x32\x0c.Experiments\x12&\n\x1etosCheckboxTextMarketingEmails\x18\x06 \x01(\t\x12\x10\n\x08tosToken\x18\x07 \x01(\t\x12#\n\x0cuserSettings\x18\x08 \x01(\x0b\x32\r.UserSettings\x12\x17\n\x0ficonOverrideUrl\x18\t \x01(\t\"9\n\x0cUserSettings\x12)\n!tosCheckboxMarketingEmailsOptedIn\x18\x01 \x01(\x08\"\x13\n\x11\x41\x63\x63\x65ptTosResponse\"~\n\x1c\x41\x63kNotificationsRequestProto\x12\x16\n\x0enotificationId\x18\x01 \x03(\t\x12*\n\rsignatureHash\x18\x02 \x01(\x0b\x32\x13.SignatureHashProto\x12\x1a\n\x12nackNotificationId\x18\x03 \x03(\t\"\x1f\n\x1d\x41\x63kNotificationsResponseProto\"\x9f\x01\n\x0c\x41\x64\x64ressProto\x12\x10\n\x08\x61\x64\x64ress1\x18\x01 \x01(\t\x12\x10\n\x08\x61\x64\x64ress2\x18\x02 \x01(\t\x12\x0c\n\x04\x63ity\x18\x03 \x01(\t\x12\r\n\x05state\x18\x04 \x01(\t\x12\x12\n\npostalCode\x18\x05 \x01(\t\x12\x0f\n\x07\x63ountry\x18\x06 \x01(\t\x12\x0c\n\x04name\x18\x07 \x01(\t\x12\x0c\n\x04type\x18\x08 \x01(\t\x12\r\n\x05phone\x18\t \x01(\t\"*\n\x0c\x41ppDataProto\x12\x0b\n\x03key\x18\x01 \x01(\t\x12\r\n\x05value\x18\x02 \x01(\t\"<\n\x12\x41ppSuggestionProto\x12&\n\tassetInfo\x18\x01 \x01(\x0b\x32\x13.ExternalAssetProto\"Q\n\x14\x41ssetIdentifierProto\x12\x13\n\x0bpackageName\x18\x01 \x01(\t\x12\x13\n\x0bversionCode\x18\x02 \x01(\x05\x12\x0f\n\x07\x61ssetId\x18\x03 \x01(\t\"\x8c\x03\n\x12\x41ssetsRequestProto\x12\x11\n\tassetType\x18\x01 \x01(\x05\x12\r\n\x05query\x18\x02 \x01(\t\x12\x12\n\ncategoryId\x18\x03 \x01(\t\x12\x0f\n\x07\x61ssetId\x18\x04 \x03(\t\x12\x1e\n\x16retrieveVendingHistory\x18\x05 \x01(\x08\x12\x1c\n\x14retrieveExtendedInfo\x18\x06 \x01(\x08\x12\x11\n\tsortOrder\x18\x07 \x01(\x05\x12\x12\n\nstartIndex\x18\x08 \x01(\x03\x12\x12\n\nnumEntries\x18\t \x01(\x03\x12\x12\n\nviewFilter\x18\n \x01(\x05\x12\x13\n\x0brankingType\x18\x0b \x01(\t\x12\x1e\n\x16retrieveCarrierChannel\x18\x0c \x01(\x08\x12\x1e\n\x16pendingDownloadAssetId\x18\r \x03(\t\x12!\n\x19reconstructVendingHistory\x18\x0e \x01(\x08\x12\x19\n\x11unfilteredResults\x18\x0f \x01(\x08\x12\x0f\n\x07\x62\x61\x64geId\x18\x10 \x03(\t\"\xd0\x01\n\x13\x41ssetsResponseProto\x12\"\n\x05\x61sset\x18\x01 \x03(\x0b\x32\x13.ExternalAssetProto\x12\x17\n\x0fnumTotalEntries\x18\x02 \x01(\x03\x12\x16\n\x0e\x63orrectedQuery\x18\x03 \x01(\t\x12%\n\x08\x61ltAsset\x18\x04 \x03(\x0b\x32\x13.ExternalAssetProto\x12\x1b\n\x13numCorrectedEntries\x18\x05 \x01(\x03\x12\x0e\n\x06header\x18\x06 \x01(\t\x12\x10\n\x08listType\x18\x07 \x01(\x05\"\xbb\x01\n\x18\x42illingEventRequestProto\x12\x11\n\teventType\x18\x01 \x01(\x05\x12\x1b\n\x13\x62illingParametersId\x18\x02 \x01(\t\x12\x15\n\rresultSuccess\x18\x03 \x01(\x08\x12\x15\n\rclientMessage\x18\x04 \x01(\t\x12\x41\n\x11\x63\x61rrierInstrument\x18\x05 \x01(\x0b\x32&.ExternalCarrierBillingInstrumentProto\"\x1b\n\x19\x42illingEventResponseProto\"\xbc\x03\n\x15\x42illingParameterProto\x12\n\n\x02id\x18\x01 \x01(\t\x12\x0c\n\x04name\x18\x02 \x01(\t\x12\x0e\n\x06mncMcc\x18\x03 \x03(\t\x12\x12\n\nbackendUrl\x18\x04 \x03(\t\x12\x0e\n\x06iconId\x18\x05 \x01(\t\x12\x1d\n\x15\x62illingInstrumentType\x18\x06 \x01(\x05\x12\x15\n\rapplicationId\x18\x07 \x01(\t\x12\x0e\n\x06tosUrl\x18\x08 \x01(\t\x12\x1d\n\x15instrumentTosRequired\x18\t \x01(\x08\x12\x12\n\napiVersion\x18\n \x01(\x05\x12)\n!perTransactionCredentialsRequired\x18\x0b \x01(\x08\x12\x32\n*sendSubscriberIdWithCarrierBillingRequests\x18\x0c \x01(\x08\x12\x1f\n\x17\x64\x65viceAssociationMethod\x18\r \x01(\x05\x12\x1f\n\x17userTokenRequestMessage\x18\x0e \x01(\t\x12\x1f\n\x17userTokenRequestAddress\x18\x0f \x01(\t\x12\x1a\n\x12passphraseRequired\x18\x10 \x01(\x08\"Q\n\x1e\x43\x61rrierBillingCredentialsProto\x12\x13\n\x0b\x63redentials\x18\x01 \x01(\t\x12\x1a\n\x12\x63redentialsTimeout\x18\x02 \x01(\x03\"\xff\x01\n\rCategoryProto\x12\x11\n\tassetType\x18\x02 \x01(\x05\x12\x12\n\ncategoryId\x18\x03 \x01(\t\x12\x17\n\x0f\x63\x61tegoryDisplay\x18\x04 \x01(\t\x12\x18\n\x10\x63\x61tegorySubtitle\x18\x05 \x01(\t\x12\x19\n\x11promotedAssetsNew\x18\x06 \x03(\t\x12\x1a\n\x12promotedAssetsHome\x18\x07 \x03(\t\x12%\n\rsubCategories\x18\x08 \x03(\x0b\x32\x0e.CategoryProto\x12\x1a\n\x12promotedAssetsPaid\x18\t \x03(\t\x12\x1a\n\x12promotedAssetsFree\x18\n \x03(\t\":\n!CheckForNotificationsRequestProto\x12\x15\n\ralarmDuration\x18\x01 \x01(\x03\"$\n\"CheckForNotificationsResponseProto\"S\n\x18\x43heckLicenseRequestProto\x12\x13\n\x0bpackageName\x18\x01 \x01(\t\x12\x13\n\x0bversionCode\x18\x02 \x01(\x05\x12\r\n\x05nonce\x18\x03 \x01(\x03\"X\n\x19\x43heckLicenseResponseProto\x12\x14\n\x0cresponseCode\x18\x01 \x01(\x05\x12\x12\n\nsignedData\x18\x02 \x01(\t\x12\x11\n\tsignature\x18\x03 \x01(\t\"\x87\x01\n\x14\x43ommentsRequestProto\x12\x0f\n\x07\x61ssetId\x18\x01 \x01(\t\x12\x12\n\nstartIndex\x18\x02 \x01(\x03\x12\x12\n\nnumEntries\x18\x03 \x01(\x03\x12\x1f\n\x17shouldReturnSelfComment\x18\x04 \x01(\x08\x12\x15\n\rassetReferrer\x18\x05 \x01(\t\"\x84\x01\n\x15\x43ommentsResponseProto\x12&\n\x07\x63omment\x18\x01 \x03(\x0b\x32\x15.ExternalCommentProto\x12\x17\n\x0fnumTotalEntries\x18\x02 \x01(\x03\x12*\n\x0bselfComment\x18\x03 \x01(\x0b\x32\x15.ExternalCommentProto\"\xc0\x03\n\x17\x43ontentSyncRequestProto\x12\x13\n\x0bincremental\x18\x01 \x01(\x08\x12\x45\n\x11\x61ssetinstallstate\x18\x02 \x03(\n2*.ContentSyncRequestProto.AssetInstallState\x12\x35\n\tsystemapp\x18\n \x03(\n2\".ContentSyncRequestProto.SystemApp\x12\x1a\n\x12sideloadedAppCount\x18\x0e \x01(\x05\x1a\xa5\x01\n\x11\x41ssetInstallState\x12\x0f\n\x07\x61ssetId\x18\x03 \x01(\t\x12\x12\n\nassetState\x18\x04 \x01(\x05\x12\x13\n\x0binstallTime\x18\x05 \x01(\x03\x12\x15\n\runinstallTime\x18\x06 \x01(\x03\x12\x13\n\x0bpackageName\x18\x07 \x01(\t\x12\x13\n\x0bversionCode\x18\x08 \x01(\x05\x12\x15\n\rassetReferrer\x18\t \x01(\t\x1aN\n\tSystemApp\x12\x13\n\x0bpackageName\x18\x0b \x01(\t\x12\x13\n\x0bversionCode\x18\x0c \x01(\x05\x12\x17\n\x0f\x63\x65rtificateHash\x18\r \x03(\t\"7\n\x18\x43ontentSyncResponseProto\x12\x1b\n\x13numUpdatesAvailable\x18\x01 \x01(\x05\"D\n\x10\x44\x61taMessageProto\x12\x10\n\x08\x63\x61tegory\x18\x01 \x01(\t\x12\x1e\n\x07\x61ppData\x18\x03 \x03(\x0b\x32\r.AppDataProto\"P\n\x11\x44ownloadInfoProto\x12\x0f\n\x07\x61pkSize\x18\x01 \x01(\x03\x12*\n\x0e\x61\x64\x64itionalFile\x18\x02 \x03(\x0b\x32\x12.FileMetadataProto\"\xe6\n\n\x12\x45xternalAssetProto\x12\n\n\x02id\x18\x01 \x01(\t\x12\r\n\x05title\x18\x02 \x01(\t\x12\x11\n\tassetType\x18\x03 \x01(\x05\x12\r\n\x05owner\x18\x04 \x01(\t\x12\x0f\n\x07version\x18\x05 \x01(\t\x12\r\n\x05price\x18\x06 \x01(\t\x12\x15\n\raverageRating\x18\x07 \x01(\t\x12\x12\n\nnumRatings\x18\x08 \x01(\x03\x12\x44\n\x13purchaseinformation\x18\t \x01(\n2\'.ExternalAssetProto.PurchaseInformation\x12\x36\n\x0c\x65xtendedinfo\x18\x0c \x01(\n2 .ExternalAssetProto.ExtendedInfo\x12\x0f\n\x07ownerId\x18\x16 \x01(\t\x12\x13\n\x0bpackageName\x18\x18 \x01(\t\x12\x13\n\x0bversionCode\x18\x19 \x01(\x05\x12\x14\n\x0c\x62undledAsset\x18\x1d \x01(\x08\x12\x15\n\rpriceCurrency\x18  \x01(\t\x12\x13\n\x0bpriceMicros\x18! \x01(\x03\x12\x14\n\x0c\x66ilterReason\x18# \x01(\t\x12\x19\n\x11\x61\x63tualSellerPrice\x18( \x01(\t\x12%\n\x08\x61ppBadge\x18/ \x03(\x0b\x32\x13.ExternalBadgeProto\x12\'\n\nownerBadge\x18\x30 \x03(\x0b\x32\x13.ExternalBadgeProto\x1a\x7f\n\x13PurchaseInformation\x12\x14\n\x0cpurchaseTime\x18\n \x01(\x03\x12\x19\n\x11refundTimeoutTime\x18\x0b \x01(\x03\x12\x19\n\x11refundStartPolicy\x18- \x01(\x05\x12\x1c\n\x14refundWindowDuration\x18. \x01(\x03\x1a\xca\x05\n\x0c\x45xtendedInfo\x12\x13\n\x0b\x64\x65scription\x18\r \x01(\t\x12\x15\n\rdownloadCount\x18\x0e \x01(\x03\x12\x1f\n\x17\x61pplicationPermissionId\x18\x0f \x03(\t\x12 \n\x18requiredInstallationSize\x18\x10 \x01(\x03\x12\x13\n\x0bpackageName\x18\x11 \x01(\t\x12\x10\n\x08\x63\x61tegory\x18\x12 \x01(\t\x12\x15\n\rforwardLocked\x18\x13 \x01(\x08\x12\x14\n\x0c\x63ontactEmail\x18\x14 \x01(\t\x12\x1b\n\x13\x65verInstalledByUser\x18\x15 \x01(\x08\x12\x1b\n\x13\x64ownloadCountString\x18\x17 \x01(\t\x12\x14\n\x0c\x63ontactPhone\x18\x1a \x01(\t\x12\x16\n\x0e\x63ontactWebsite\x18\x1b \x01(\t\x12\x1e\n\x16nextPurchaseRefundable\x18\x1c \x01(\x08\x12\x16\n\x0enumScreenshots\x18\x1e \x01(\x05\x12\x1e\n\x16promotionalDescription\x18\x1f \x01(\t\x12\x18\n\x10serverAssetState\x18\" \x01(\x05\x12\x1a\n\x12\x63ontentRatingLevel\x18$ \x01(\x05\x12\x1b\n\x13\x63ontentRatingString\x18% \x01(\t\x12\x15\n\rrecentChanges\x18& \x01(\t\x12M\n\x11packagedependency\x18\' \x03(\n22.ExternalAssetProto.ExtendedInfo.PackageDependency\x12\x11\n\tvideoLink\x18+ \x01(\t\x12(\n\x0c\x64ownloadInfo\x18\x31 \x01(\x0b\x32\x12.DownloadInfoProto\x1a\x41\n\x11PackageDependency\x12\x13\n\x0bpackageName\x18) \x01(\t\x12\x17\n\x0fskipPermissions\x18* \x01(\x08\"5\n\x17\x45xternalBadgeImageProto\x12\r\n\x05usage\x18\x01 \x01(\x05\x12\x0b\n\x03url\x18\x02 \x01(\t\"\x8a\x01\n\x12\x45xternalBadgeProto\x12\x16\n\x0elocalizedTitle\x18\x01 \x01(\t\x12\x1c\n\x14localizedDescription\x18\x02 \x01(\t\x12,\n\nbadgeImage\x18\x03 \x03(\x0b\x32\x18.ExternalBadgeImageProto\x12\x10\n\x08searchId\x18\x04 \x01(\t\"\xe0\x02\n%ExternalCarrierBillingInstrumentProto\x12\x15\n\rinstrumentKey\x18\x01 \x01(\t\x12\x1c\n\x14subscriberIdentifier\x18\x02 \x01(\t\x12\x13\n\x0b\x61\x63\x63ountType\x18\x03 \x01(\t\x12\x1a\n\x12subscriberCurrency\x18\x04 \x01(\t\x12\x18\n\x10transactionLimit\x18\x05 \x01(\x04\x12\x16\n\x0esubscriberName\x18\x06 \x01(\t\x12\x10\n\x08\x61\x64\x64ress1\x18\x07 \x01(\t\x12\x10\n\x08\x61\x64\x64ress2\x18\x08 \x01(\t\x12\x0c\n\x04\x63ity\x18\t \x01(\t\x12\r\n\x05state\x18\n \x01(\t\x12\x12\n\npostalCode\x18\x0b \x01(\t\x12\x0f\n\x07\x63ountry\x18\x0c \x01(\t\x12\x39\n\x17\x65ncryptedSubscriberInfo\x18\r \x01(\x0b\x32\x18.EncryptedSubscriberInfo\"r\n\x14\x45xternalCommentProto\x12\x0c\n\x04\x62ody\x18\x01 \x01(\t\x12\x0e\n\x06rating\x18\x02 \x01(\x05\x12\x13\n\x0b\x63reatorName\x18\x03 \x01(\t\x12\x14\n\x0c\x63reationTime\x18\x04 \x01(\x03\x12\x11\n\tcreatorId\x18\x05 \x01(\t\"\xfb\x01\n\x12\x45xternalCreditCard\x12\x0c\n\x04type\x18\x01 \x01(\t\x12\x12\n\nlastDigits\x18\x02 \x01(\t\x12\x0f\n\x07\x65xpYear\x18\x03 \x01(\x05\x12\x10\n\x08\x65xpMonth\x18\x04 \x01(\x05\x12\x12\n\npersonName\x18\x05 \x01(\t\x12\x13\n\x0b\x63ountryCode\x18\x06 \x01(\t\x12\x12\n\npostalCode\x18\x07 \x01(\t\x12\x13\n\x0bmakeDefault\x18\x08 \x01(\x08\x12\x10\n\x08\x61\x64\x64ress1\x18\t \x01(\t\x12\x10\n\x08\x61\x64\x64ress2\x18\n \x01(\t\x12\x0c\n\x04\x63ity\x18\x0b \x01(\t\x12\r\n\x05state\x18\x0c \x01(\t\x12\r\n\x05phone\x18\r \x01(\t\"\xb5\x01\n\x1d\x45xternalPaypalInstrumentProto\x12\x15\n\rinstrumentKey\x18\x01 \x01(\t\x12\x16\n\x0epreapprovalKey\x18\x02 \x01(\t\x12\x13\n\x0bpaypalEmail\x18\x03 \x01(\t\x12$\n\rpaypalAddress\x18\x04 \x01(\x0b\x32\r.AddressProto\x12*\n\"multiplePaypalInstrumentsSupported\x18\x05 \x01(\x08\"]\n\x11\x46ileMetadataProto\x12\x10\n\x08\x66ileType\x18\x01 \x01(\x05\x12\x13\n\x0bversionCode\x18\x02 \x01(\x05\x12\x0c\n\x04size\x18\x03 \x01(\x03\x12\x13\n\x0b\x64ownloadUrl\x18\x04 \x01(\t\"Z\n\x1dGetAddressSnippetRequestProto\x12\x39\n\x17\x65ncryptedSubscriberInfo\x18\x01 \x01(\x0b\x32\x18.EncryptedSubscriberInfo\"8\n\x1eGetAddressSnippetResponseProto\x12\x16\n\x0e\x61\x64\x64ressSnippet\x18\x01 \x01(\t\"B\n\x14GetAssetRequestProto\x12\x0f\n\x07\x61ssetId\x18\x01 \x01(\t\x12\x19\n\x11\x64irectDownloadKey\x18\x02 \x01(\t\"\xda\x03\n\x15GetAssetResponseProto\x12\x39\n\x0cinstallasset\x18\x01 \x01(\n2#.GetAssetResponseProto.InstallAsset\x12*\n\x0e\x61\x64\x64itionalFile\x18\x0f \x03(\x0b\x32\x12.FileMetadataProto\x1a\xd9\x02\n\x0cInstallAsset\x12\x0f\n\x07\x61ssetId\x18\x02 \x01(\t\x12\x11\n\tassetName\x18\x03 \x01(\t\x12\x11\n\tassetType\x18\x04 \x01(\t\x12\x14\n\x0c\x61ssetPackage\x18\x05 \x01(\t\x12\x0f\n\x07\x62lobUrl\x18\x06 \x01(\t\x12\x16\n\x0e\x61ssetSignature\x18\x07 \x01(\t\x12\x11\n\tassetSize\x18\x08 \x01(\x03\x12\x1b\n\x13refundTimeoutMillis\x18\t \x01(\x03\x12\x15\n\rforwardLocked\x18\n \x01(\x08\x12\x0f\n\x07secured\x18\x0b \x01(\x08\x12\x13\n\x0bversionCode\x18\x0c \x01(\x05\x12\x1e\n\x16\x64ownloadAuthCookieName\x18\r \x01(\t\x12\x1f\n\x17\x64ownloadAuthCookieValue\x18\x0e \x01(\t\x12%\n\x1dpostInstallRefundWindowMillis\x18\x10 \x01(\x03\"\x1c\n\x1aGetCarrierInfoRequestProto\"\xb8\x01\n\x1bGetCarrierInfoResponseProto\x12\x1d\n\x15\x63\x61rrierChannelEnabled\x18\x01 \x01(\x08\x12\x17\n\x0f\x63\x61rrierLogoIcon\x18\x02 \x01(\x0c\x12\x15\n\rcarrierBanner\x18\x03 \x01(\x0c\x12\x17\n\x0f\x63\x61rrierSubtitle\x18\x04 \x01(\t\x12\x14\n\x0c\x63\x61rrierTitle\x18\x05 \x01(\t\x12\x1b\n\x13\x63\x61rrierImageDensity\x18\x06 \x01(\x05\"6\n\x19GetCategoriesRequestProto\x12\x19\n\x11prefetchPromoData\x18\x01 \x01(\x08\"@\n\x1aGetCategoriesResponseProto\x12\"\n\ncategories\x18\x01 \x03(\x0b\x32\x0e.CategoryProto\"\xbb\x01\n\x14GetImageRequestProto\x12\x0f\n\x07\x61ssetId\x18\x01 \x01(\t\x12\x12\n\nimageUsage\x18\x03 \x01(\x05\x12\x0f\n\x07imageId\x18\x04 \x01(\t\x12\x1b\n\x13screenPropertyWidth\x18\x05 \x01(\x05\x12\x1c\n\x14screenPropertyHeight\x18\x06 \x01(\x05\x12\x1d\n\x15screenPropertyDensity\x18\x07 \x01(\x05\x12\x13\n\x0bproductType\x18\x08 \x01(\x05\"@\n\x15GetImageResponseProto\x12\x11\n\timageData\x18\x01 \x01(\x0c\x12\x14\n\x0cimageDensity\x18\x02 \x01(\x05\"\xf4\x01\n\x1dGetMarketMetadataRequestProto\x12\x17\n\x0flastRequestTime\x18\x01 \x01(\x03\x12\x36\n\x13\x64\x65viceConfiguration\x18\x02 \x01(\x0b\x32\x19.DeviceConfigurationProto\x12\x15\n\rdeviceRoaming\x18\x03 \x01(\x08\x12\x1b\n\x13marketSignatureHash\x18\x04 \x03(\t\x12\x15\n\rcontentRating\x18\x05 \x01(\x05\x12\x17\n\x0f\x64\x65viceModelName\x18\x06 \x01(\t\x12\x1e\n\x16\x64\x65viceManufacturerName\x18\x07 \x01(\t\"\xb7\x02\n\x1eGetMarketMetadataResponseProto\x12\x1f\n\x17latestClientVersionCode\x18\x01 \x01(\x05\x12\x17\n\x0flatestClientUrl\x18\x02 \x01(\t\x12\x17\n\x0fpaidAppsEnabled\x18\x03 \x01(\x08\x12\x30\n\x10\x62illingParameter\x18\x04 \x03(\x0b\x32\x16.BillingParameterProto\x12\x1a\n\x12\x63ommentPostEnabled\x18\x05 \x01(\x08\x12\x1c\n\x14\x62illingEventsEnabled\x18\x06 \x01(\x08\x12\x16\n\x0ewarningMessage\x18\x07 \x01(\t\x12\x1b\n\x13inAppBillingEnabled\x18\x08 \x01(\x08\x12!\n\x19inAppBillingMaxApiVersion\x18\t \x01(\x05\"1\n\x1cGetSubCategoriesRequestProto\x12\x11\n\tassetType\x18\x01 \x01(\x05\"\xa2\x01\n\x1dGetSubCategoriesResponseProto\x12?\n\x0bsubcategory\x18\x01 \x03(\n2*.GetSubCategoriesResponseProto.SubCategory\x1a@\n\x0bSubCategory\x12\x1a\n\x12subCategoryDisplay\x18\x02 \x01(\t\x12\x15\n\rsubCategoryId\x18\x03 \x01(\t\"\xb0\x01\n$InAppPurchaseInformationRequestProto\x12*\n\rsignatureHash\x18\x01 \x01(\x0b\x32\x13.SignatureHashProto\x12\r\n\x05nonce\x18\x02 \x01(\x03\x12\x16\n\x0enotificationId\x18\x03 \x03(\t\x12\x1a\n\x12signatureAlgorithm\x18\x04 \x01(\t\x12\x19\n\x11\x62illingApiVersion\x18\x05 \x01(\x05\"\xbb\x01\n%InAppPurchaseInformationResponseProto\x12(\n\x0esignedResponse\x18\x01 \x01(\x0b\x32\x10.SignedDataProto\x12:\n\x15statusBarNotification\x18\x02 \x03(\x0b\x32\x1b.StatusBarNotificationProto\x12,\n\x0epurchaseResult\x18\x03 \x01(\x0b\x32\x14.PurchaseResultProto\"\x98\x01\n$InAppRestoreTransactionsRequestProto\x12*\n\rsignatureHash\x18\x01 \x01(\x0b\x32\x13.SignatureHashProto\x12\r\n\x05nonce\x18\x02 \x01(\x03\x12\x1a\n\x12signatureAlgorithm\x18\x03 \x01(\t\x12\x19\n\x11\x62illingApiVersion\x18\x04 \x01(\x05\"\x7f\n%InAppRestoreTransactionsResponseProto\x12(\n\x0esignedResponse\x18\x01 \x01(\x0b\x32\x10.SignedDataProto\x12,\n\x0epurchaseResult\x18\x02 \x01(\x0b\x32\x14.PurchaseResultProto\"\xba\x01\n\x19ModifyCommentRequestProto\x12\x0f\n\x07\x61ssetId\x18\x01 \x01(\t\x12&\n\x07\x63omment\x18\x02 \x01(\x0b\x32\x15.ExternalCommentProto\x12\x15\n\rdeleteComment\x18\x03 \x01(\x08\x12\x11\n\tflagAsset\x18\x04 \x01(\x08\x12\x10\n\x08\x66lagType\x18\x05 \x01(\x05\x12\x13\n\x0b\x66lagMessage\x18\x06 \x01(\t\x12\x13\n\x0bnonFlagFlow\x18\x07 \x01(\x08\"\x1c\n\x1aModifyCommentResponseProto\"v\n\x16PaypalCountryInfoProto\x12\x19\n\x11\x62irthDateRequired\x18\x01 \x01(\x08\x12\x0f\n\x07tosText\x18\x02 \x01(\t\x12\x1c\n\x14\x62illingAgreementText\x18\x03 \x01(\t\x12\x12\n\npreTosText\x18\x04 \x01(\t\"y\n\x1fPaypalCreateAccountRequestProto\x12\x11\n\tfirstName\x18\x01 \x01(\t\x12\x10\n\x08lastName\x18\x02 \x01(\t\x12\x1e\n\x07\x61\x64\x64ress\x18\x03 \x01(\x0b\x32\r.AddressProto\x12\x11\n\tbirthDate\x18\x04 \x01(\t\"<\n PaypalCreateAccountResponseProto\x12\x18\n\x10\x63reateAccountKey\x18\x01 \x01(\t\"E\n\x16PaypalCredentialsProto\x12\x16\n\x0epreapprovalKey\x18\x01 \x01(\t\x12\x13\n\x0bpaypalEmail\x18\x02 \x01(\t\"B\n PaypalMassageAddressRequestProto\x12\x1e\n\x07\x61\x64\x64ress\x18\x01 \x01(\x0b\x32\r.AddressProto\"C\n!PaypalMassageAddressResponseProto\x12\x1e\n\x07\x61\x64\x64ress\x18\x01 \x01(\x0b\x32\r.AddressProto\"^\n(PaypalPreapprovalCredentialsRequestProto\x12\x15\n\rgaiaAuthToken\x18\x01 \x01(\t\x12\x1b\n\x13\x62illingInstrumentId\x18\x02 \x01(\t\"n\n)PaypalPreapprovalCredentialsResponseProto\x12\x12\n\nresultCode\x18\x01 \x01(\x05\x12\x18\n\x10paypalAccountKey\x18\x02 \x01(\t\x12\x13\n\x0bpaypalEmail\x18\x03 \x01(\t\"R\n$PaypalPreapprovalDetailsRequestProto\x12\x12\n\ngetAddress\x18\x01 \x01(\x08\x12\x16\n\x0epreapprovalKey\x18\x02 \x01(\t\"\\\n%PaypalPreapprovalDetailsResponseProto\x12\x13\n\x0bpaypalEmail\x18\x01 \x01(\t\x12\x1e\n\x07\x61\x64\x64ress\x18\x02 \x01(\x0b\x32\r.AddressProto\"\x1f\n\x1dPaypalPreapprovalRequestProto\"8\n\x1ePaypalPreapprovalResponseProto\x12\x16\n\x0epreapprovalKey\x18\x01 \x01(\t\"]\n\x19PendingNotificationsProto\x12\'\n\x0cnotification\x18\x01 \x03(\x0b\x32\x11.DataMessageProto\x12\x17\n\x0fnextCheckMillis\x18\x02 \x01(\x03\"e\n\x15PrefetchedBundleProto\x12$\n\x07request\x18\x01 \x01(\x0b\x32\x13.SingleRequestProto\x12&\n\x08response\x18\x02 \x01(\x0b\x32\x14.SingleResponseProto\"\xbc\x01\n\x15PurchaseCartInfoProto\x12\x11\n\titemPrice\x18\x01 \x01(\t\x12\x14\n\x0ctaxInclusive\x18\x02 \x01(\t\x12\x14\n\x0ctaxExclusive\x18\x03 \x01(\t\x12\r\n\x05total\x18\x04 \x01(\t\x12\x12\n\ntaxMessage\x18\x05 \x01(\t\x12\x15\n\rfooterMessage\x18\x06 \x01(\t\x12\x15\n\rpriceCurrency\x18\x07 \x01(\t\x12\x13\n\x0bpriceMicros\x18\x08 \x01(\x03\"\x93\x04\n\x11PurchaseInfoProto\x12\x15\n\rtransactionId\x18\x01 \x01(\t\x12(\n\x08\x63\x61rtInfo\x18\x02 \x01(\x0b\x32\x16.PurchaseCartInfoProto\x12\x41\n\x12\x62illinginstruments\x18\x03 \x01(\n2%.PurchaseInfoProto.BillingInstruments\x12\x18\n\x10\x65rrorInputFields\x18\t \x03(\x05\x12\x14\n\x0crefundPolicy\x18\n \x01(\t\x12\x15\n\ruserCanAddGdd\x18\x0c \x01(\x08\x12\x1f\n\x17\x65ligibleInstrumentTypes\x18\r \x03(\x05\x12\x0f\n\x07orderId\x18\x0f \x01(\t\x1a\x80\x02\n\x12\x42illingInstruments\x12R\n\x11\x62illinginstrument\x18\x04 \x03(\n27.PurchaseInfoProto.BillingInstruments.BillingInstrument\x12\"\n\x1a\x64\x65\x66\x61ultBillingInstrumentId\x18\x08 \x01(\t\x1ar\n\x11\x42illingInstrument\x12\n\n\x02id\x18\x05 \x01(\t\x12\x0c\n\x04name\x18\x06 \x01(\t\x12\x11\n\tisInvalid\x18\x07 \x01(\x08\x12\x16\n\x0einstrumentType\x18\x0b \x01(\x05\x12\x18\n\x10instrumentStatus\x18\x0e \x01(\x05\"i\n\x1cPurchaseMetadataRequestProto\x12*\n\"deprecatedRetrieveBillingCountries\x18\x01 \x01(\x08\x12\x1d\n\x15\x62illingInstrumentType\x18\x02 \x01(\x05\"\x87\x04\n\x1dPurchaseMetadataResponseProto\x12;\n\tcountries\x18\x01 \x01(\n2(.PurchaseMetadataResponseProto.Countries\x1a\xa8\x03\n\tCountries\x12\x41\n\x07\x63ountry\x18\x02 \x03(\n20.PurchaseMetadataResponseProto.Countries.Country\x1a\xd7\x02\n\x07\x43ountry\x12\x13\n\x0b\x63ountryCode\x18\x03 \x01(\t\x12\x13\n\x0b\x63ountryName\x18\x04 \x01(\t\x12\x32\n\x11paypalCountryInfo\x18\x05 \x01(\x0b\x32\x17.PaypalCountryInfoProto\x12#\n\x1b\x61llowsReducedBillingAddress\x18\x06 \x01(\x08\x12\x65\n\x15instrumentaddressspec\x18\x07 \x03(\n2F.PurchaseMetadataResponseProto.Countries.Country.InstrumentAddressSpec\x1a\x62\n\x15InstrumentAddressSpec\x12\x18\n\x10instrumentFamily\x18\x08 \x01(\x05\x12/\n\x12\x62illingAddressSpec\x18\t \x01(\x0b\x32\x13.BillingAddressSpec\"\xe2\x03\n\x19PurchaseOrderRequestProto\x12\x15\n\rgaiaAuthToken\x18\x01 \x01(\t\x12\x0f\n\x07\x61ssetId\x18\x02 \x01(\t\x12\x15\n\rtransactionId\x18\x03 \x01(\t\x12\x1b\n\x13\x62illingInstrumentId\x18\x04 \x01(\t\x12\x13\n\x0btosAccepted\x18\x05 \x01(\x08\x12\x42\n\x19\x63\x61rrierBillingCredentials\x18\x06 \x01(\x0b\x32\x1f.CarrierBillingCredentialsProto\x12\x17\n\x0f\x65xistingOrderId\x18\x07 \x01(\t\x12\x1d\n\x15\x62illingInstrumentType\x18\x08 \x01(\x05\x12\x1b\n\x13\x62illingParametersId\x18\t \x01(\t\x12\x32\n\x11paypalCredentials\x18\n \x01(\x0b\x32\x17.PaypalCredentialsProto\x12,\n\x0eriskHeaderInfo\x18\x0b \x01(\x0b\x32\x14.RiskHeaderInfoProto\x12\x13\n\x0bproductType\x18\x0c \x01(\x05\x12*\n\rsignatureHash\x18\r \x01(\x0b\x32\x13.SignatureHashProto\x12\x18\n\x10\x64\x65veloperPayload\x18\x0e \x01(\t\"\xb6\x01\n\x1aPurchaseOrderResponseProto\x12\x1c\n\x14\x64\x65precatedResultCode\x18\x01 \x01(\x05\x12(\n\x0cpurchaseInfo\x18\x02 \x01(\x0b\x32\x12.PurchaseInfoProto\x12\"\n\x05\x61sset\x18\x03 \x01(\x0b\x32\x13.ExternalAssetProto\x12,\n\x0epurchaseResult\x18\x04 \x01(\x0b\x32\x14.PurchaseResultProto\"\x92\x04\n\x18PurchasePostRequestProto\x12\x15\n\rgaiaAuthToken\x18\x01 \x01(\t\x12\x0f\n\x07\x61ssetId\x18\x02 \x01(\t\x12\x15\n\rtransactionId\x18\x03 \x01(\t\x12N\n\x15\x62illinginstrumentinfo\x18\x04 \x01(\n2/.PurchasePostRequestProto.BillingInstrumentInfo\x12\x13\n\x0btosAccepted\x18\x07 \x01(\x08\x12\x17\n\x0f\x63\x62InstrumentKey\x18\x08 \x01(\t\x12\x1b\n\x13paypalAuthConfirmed\x18\x0b \x01(\x08\x12\x13\n\x0bproductType\x18\x0c \x01(\x05\x12*\n\rsignatureHash\x18\r \x01(\x0b\x32\x13.SignatureHashProto\x1a\xda\x01\n\x15\x42illingInstrumentInfo\x12\x1b\n\x13\x62illingInstrumentId\x18\x05 \x01(\t\x12\'\n\ncreditCard\x18\x06 \x01(\x0b\x32\x13.ExternalCreditCard\x12\x41\n\x11\x63\x61rrierInstrument\x18\t \x01(\x0b\x32&.ExternalCarrierBillingInstrumentProto\x12\x38\n\x10paypalInstrument\x18\n \x01(\x0b\x32\x1e.ExternalPaypalInstrumentProto\"\xaa\x02\n\x19PurchasePostResponseProto\x12\x1c\n\x14\x64\x65precatedResultCode\x18\x01 \x01(\x05\x12(\n\x0cpurchaseInfo\x18\x02 \x01(\x0b\x32\x12.PurchaseInfoProto\x12\x19\n\x11termsOfServiceUrl\x18\x03 \x01(\t\x12\x1a\n\x12termsOfServiceText\x18\x04 \x01(\t\x12\x1a\n\x12termsOfServiceName\x18\x05 \x01(\t\x12\"\n\x1atermsOfServiceCheckboxText\x18\x06 \x01(\t\x12 \n\x18termsOfServiceHeaderText\x18\x07 \x01(\t\x12,\n\x0epurchaseResult\x18\x08 \x01(\x0b\x32\x14.PurchaseResultProto\"q\n\x1bPurchaseProductRequestProto\x12\x13\n\x0bproductType\x18\x01 \x01(\x05\x12\x11\n\tproductId\x18\x02 \x01(\t\x12*\n\rsignatureHash\x18\x03 \x01(\x0b\x32\x13.SignatureHashProto\"p\n\x1cPurchaseProductResponseProto\x12\r\n\x05title\x18\x01 \x01(\t\x12\x11\n\titemTitle\x18\x02 \x01(\t\x12\x17\n\x0fitemDescription\x18\x03 \x01(\t\x12\x15\n\rmerchantField\x18\x04 \x01(\t\"D\n\x13PurchaseResultProto\x12\x12\n\nresultCode\x18\x01 \x01(\x05\x12\x19\n\x11resultCodeMessage\x18\x02 \x01(\t\"W\n\x14QuerySuggestionProto\x12\r\n\x05query\x18\x01 \x01(\t\x12\x1b\n\x13\x65stimatedNumResults\x18\x02 \x01(\x05\x12\x13\n\x0bqueryWeight\x18\x03 \x01(\x05\"A\n\x1bQuerySuggestionRequestProto\x12\r\n\x05query\x18\x01 \x01(\t\x12\x13\n\x0brequestType\x18\x02 \x01(\x05\"\x90\x02\n\x1cQuerySuggestionResponseProto\x12<\n\nsuggestion\x18\x01 \x03(\n2(.QuerySuggestionResponseProto.Suggestion\x12\"\n\x1a\x65stimatedNumAppSuggestions\x18\x04 \x01(\x05\x12$\n\x1c\x65stimatedNumQuerySuggestions\x18\x05 \x01(\x05\x1ah\n\nSuggestion\x12*\n\rappSuggestion\x18\x02 \x01(\x0b\x32\x13.AppSuggestionProto\x12.\n\x0fquerySuggestion\x18\x03 \x01(\x0b\x32\x15.QuerySuggestionProto\"T\n\x17RateCommentRequestProto\x12\x0f\n\x07\x61ssetId\x18\x01 \x01(\t\x12\x11\n\tcreatorId\x18\x02 \x01(\t\x12\x15\n\rcommentRating\x18\x03 \x01(\x05\"\x1a\n\x18RateCommentResponseProto\">\n\x1fReconstructDatabaseRequestProto\x12\x1b\n\x13retrieveFullHistory\x18\x01 \x01(\x08\"H\n ReconstructDatabaseResponseProto\x12$\n\x05\x61sset\x18\x01 \x03(\x0b\x32\x15.AssetIdentifierProto\"%\n\x12RefundRequestProto\x12\x0f\n\x07\x61ssetId\x18\x01 \x01(\t\"_\n\x13RefundResponseProto\x12\x0e\n\x06result\x18\x01 \x01(\x05\x12\"\n\x05\x61sset\x18\x02 \x01(\x0b\x32\x13.ExternalAssetProto\x12\x14\n\x0cresultDetail\x18\x03 \x01(\t\"*\n\x17RemoveAssetRequestProto\x12\x0f\n\x07\x61ssetId\x18\x01 \x01(\t\"\xcd\x02\n\x16RequestPropertiesProto\x12\x15\n\ruserAuthToken\x18\x01 \x01(\t\x12\x1b\n\x13userAuthTokenSecure\x18\x02 \x01(\x08\x12\x17\n\x0fsoftwareVersion\x18\x03 \x01(\x05\x12\x0b\n\x03\x61id\x18\x04 \x01(\t\x12\x1d\n\x15productNameAndVersion\x18\x05 \x01(\t\x12\x14\n\x0cuserLanguage\x18\x06 \x01(\t\x12\x13\n\x0buserCountry\x18\x07 \x01(\t\x12\x14\n\x0coperatorName\x18\x08 \x01(\t\x12\x17\n\x0fsimOperatorName\x18\t \x01(\t\x12\x1b\n\x13operatorNumericName\x18\n \x01(\t\x12\x1e\n\x16simOperatorNumericName\x18\x0b \x01(\t\x12\x10\n\x08\x63lientId\x18\x0c \x01(\t\x12\x11\n\tloggingId\x18\r \x01(\t\"\xbe\x11\n\x0cRequestProto\x12\x32\n\x11requestProperties\x18\x01 \x01(\x0b\x32\x17.RequestPropertiesProto\x12&\n\x07request\x18\x02 \x03(\n2\x15.RequestProto.Request\x1a\xd1\x10\n\x07Request\x12\x42\n\x19requestSpecificProperties\x18\x03 \x01(\x0b\x32\x1f.RequestSpecificPropertiesProto\x12)\n\x0c\x61ssetRequest\x18\x04 \x01(\x0b\x32\x13.AssetsRequestProto\x12.\n\x0f\x63ommentsRequest\x18\x05 \x01(\x0b\x32\x15.CommentsRequestProto\x12\x38\n\x14modifyCommentRequest\x18\x06 \x01(\x0b\x32\x1a.ModifyCommentRequestProto\x12\x36\n\x13purchasePostRequest\x18\x07 \x01(\x0b\x32\x19.PurchasePostRequestProto\x12\x38\n\x14purchaseOrderRequest\x18\x08 \x01(\x0b\x32\x1a.PurchaseOrderRequestProto\x12\x34\n\x12\x63ontentSyncRequest\x18\t \x01(\x0b\x32\x18.ContentSyncRequestProto\x12.\n\x0fgetAssetRequest\x18\n \x01(\x0b\x32\x15.GetAssetRequestProto\x12.\n\x0fgetImageRequest\x18\x0b \x01(\x0b\x32\x15.GetImageRequestProto\x12*\n\rrefundRequest\x18\x0c \x01(\x0b\x32\x13.RefundRequestProto\x12>\n\x17purchaseMetadataRequest\x18\r \x01(\x0b\x32\x1d.PurchaseMetadataRequestProto\x12;\n\x14subCategoriesRequest\x18\x0e \x01(\x0b\x32\x1d.GetSubCategoriesRequestProto\x12<\n\x16uninstallReasonRequest\x18\x10 \x01(\x0b\x32\x1c.UninstallReasonRequestProto\x12\x34\n\x12rateCommentRequest\x18\x11 \x01(\x0b\x32\x18.RateCommentRequestProto\x12\x36\n\x13\x63heckLicenseRequest\x18\x12 \x01(\x0b\x32\x19.CheckLicenseRequestProto\x12@\n\x18getMarketMetadataRequest\x18\x13 \x01(\x0b\x32\x1e.GetMarketMetadataRequestProto\x12\x38\n\x14getCategoriesRequest\x18\x15 \x01(\x0b\x32\x1a.GetCategoriesRequestProto\x12:\n\x15getCarrierInfoRequest\x18\x16 \x01(\x0b\x32\x1b.GetCarrierInfoRequestProto\x12\x34\n\x12removeAssetRequest\x18\x17 \x01(\x0b\x32\x18.RemoveAssetRequestProto\x12\x44\n\x1arestoreApplicationsRequest\x18\x18 \x01(\x0b\x32 .RestoreApplicationsRequestProto\x12<\n\x16querySuggestionRequest\x18\x19 \x01(\x0b\x32\x1c.QuerySuggestionRequestProto\x12\x36\n\x13\x62illingEventRequest\x18\x1a \x01(\x0b\x32\x19.BillingEventRequestProto\x12@\n\x18paypalPreapprovalRequest\x18\x1b \x01(\x0b\x32\x1e.PaypalPreapprovalRequestProto\x12N\n\x1fpaypalPreapprovalDetailsRequest\x18\x1c \x01(\x0b\x32%.PaypalPreapprovalDetailsRequestProto\x12\x44\n\x1apaypalCreateAccountRequest\x18\x1d \x01(\x0b\x32 .PaypalCreateAccountRequestProto\x12V\n#paypalPreapprovalCredentialsRequest\x18\x1e \x01(\x0b\x32).PaypalPreapprovalCredentialsRequestProto\x12N\n\x1finAppRestoreTransactionsRequest\x18\x1f \x01(\x0b\x32%.InAppRestoreTransactionsRequestProto\x12N\n\x1finAppPurchaseInformationRequest\x18  \x01(\x0b\x32%.InAppPurchaseInformationRequestProto\x12H\n\x1c\x63heckForNotificationsRequest\x18! \x01(\x0b\x32\".CheckForNotificationsRequestProto\x12>\n\x17\x61\x63kNotificationsRequest\x18\" \x01(\x0b\x32\x1d.AckNotificationsRequestProto\x12<\n\x16purchaseProductRequest\x18# \x01(\x0b\x32\x1c.PurchaseProductRequestProto\x12\x44\n\x1areconstructDatabaseRequest\x18$ \x01(\x0b\x32 .ReconstructDatabaseRequestProto\x12\x46\n\x1bpaypalMassageAddressRequest\x18% \x01(\x0b\x32!.PaypalMassageAddressRequestProto\x12@\n\x18getAddressSnippetRequest\x18& \x01(\x0b\x32\x1e.GetAddressSnippetRequestProto\"5\n\x1eRequestSpecificPropertiesProto\x12\x13\n\x0bifNoneMatch\x18\x01 \x01(\t\"\xbe\x01\n\x17ResponsePropertiesProto\x12\x0e\n\x06result\x18\x01 \x01(\x05\x12\x0e\n\x06maxAge\x18\x02 \x01(\x05\x12\x0c\n\x04\x65tag\x18\x03 \x01(\t\x12\x15\n\rserverVersion\x18\x04 \x01(\x05\x12\x18\n\x10maxAgeConsumable\x18\x06 \x01(\x05\x12\x14\n\x0c\x65rrorMessage\x18\x07 \x01(\t\x12.\n\x0f\x65rrorInputField\x18\x08 \x03(\x0b\x32\x15.InputValidationError\"\xf7\x11\n\rResponseProto\x12)\n\x08response\x18\x01 \x03(\n2\x17.ResponseProto.Response\x12\x38\n\x14pendingNotifications\x18& \x01(\x0b\x32\x1a.PendingNotificationsProto\x1a\x80\x11\n\x08Response\x12\x34\n\x12responseProperties\x18\x02 \x01(\x0b\x32\x18.ResponsePropertiesProto\x12,\n\x0e\x61ssetsResponse\x18\x03 \x01(\x0b\x32\x14.AssetsResponseProto\x12\x30\n\x10\x63ommentsResponse\x18\x04 \x01(\x0b\x32\x16.CommentsResponseProto\x12:\n\x15modifyCommentResponse\x18\x05 \x01(\x0b\x32\x1b.ModifyCommentResponseProto\x12\x38\n\x14purchasePostResponse\x18\x06 \x01(\x0b\x32\x1a.PurchasePostResponseProto\x12:\n\x15purchaseOrderResponse\x18\x07 \x01(\x0b\x32\x1b.PurchaseOrderResponseProto\x12\x36\n\x13\x63ontentSyncResponse\x18\x08 \x01(\x0b\x32\x19.ContentSyncResponseProto\x12\x30\n\x10getAssetResponse\x18\t \x01(\x0b\x32\x16.GetAssetResponseProto\x12\x30\n\x10getImageResponse\x18\n \x01(\x0b\x32\x16.GetImageResponseProto\x12,\n\x0erefundResponse\x18\x0b \x01(\x0b\x32\x14.RefundResponseProto\x12@\n\x18purchaseMetadataResponse\x18\x0c \x01(\x0b\x32\x1e.PurchaseMetadataResponseProto\x12=\n\x15subCategoriesResponse\x18\r \x01(\x0b\x32\x1e.GetSubCategoriesResponseProto\x12>\n\x17uninstallReasonResponse\x18\x0f \x01(\x0b\x32\x1d.UninstallReasonResponseProto\x12\x36\n\x13rateCommentResponse\x18\x10 \x01(\x0b\x32\x19.RateCommentResponseProto\x12\x38\n\x14\x63heckLicenseResponse\x18\x11 \x01(\x0b\x32\x1a.CheckLicenseResponseProto\x12\x42\n\x19getMarketMetadataResponse\x18\x12 \x01(\x0b\x32\x1f.GetMarketMetadataResponseProto\x12\x30\n\x10prefetchedBundle\x18\x13 \x03(\x0b\x32\x16.PrefetchedBundleProto\x12:\n\x15getCategoriesResponse\x18\x14 \x01(\x0b\x32\x1b.GetCategoriesResponseProto\x12<\n\x16getCarrierInfoResponse\x18\x15 \x01(\x0b\x32\x1c.GetCarrierInfoResponseProto\x12\x45\n\x1arestoreApplicationResponse\x18\x17 \x01(\x0b\x32!.RestoreApplicationsResponseProto\x12>\n\x17querySuggestionResponse\x18\x18 \x01(\x0b\x32\x1d.QuerySuggestionResponseProto\x12\x38\n\x14\x62illingEventResponse\x18\x19 \x01(\x0b\x32\x1a.BillingEventResponseProto\x12\x42\n\x19paypalPreapprovalResponse\x18\x1a \x01(\x0b\x32\x1f.PaypalPreapprovalResponseProto\x12P\n paypalPreapprovalDetailsResponse\x18\x1b \x01(\x0b\x32&.PaypalPreapprovalDetailsResponseProto\x12\x46\n\x1bpaypalCreateAccountResponse\x18\x1c \x01(\x0b\x32!.PaypalCreateAccountResponseProto\x12X\n$paypalPreapprovalCredentialsResponse\x18\x1d \x01(\x0b\x32*.PaypalPreapprovalCredentialsResponseProto\x12P\n inAppRestoreTransactionsResponse\x18\x1e \x01(\x0b\x32&.InAppRestoreTransactionsResponseProto\x12P\n inAppPurchaseInformationResponse\x18\x1f \x01(\x0b\x32&.InAppPurchaseInformationResponseProto\x12J\n\x1d\x63heckForNotificationsResponse\x18  \x01(\x0b\x32#.CheckForNotificationsResponseProto\x12@\n\x18\x61\x63kNotificationsResponse\x18! \x01(\x0b\x32\x1e.AckNotificationsResponseProto\x12>\n\x17purchaseProductResponse\x18\" \x01(\x0b\x32\x1d.PurchaseProductResponseProto\x12\x46\n\x1breconstructDatabaseResponse\x18# \x01(\x0b\x32!.ReconstructDatabaseResponseProto\x12H\n\x1cpaypalMassageAddressResponse\x18$ \x01(\x0b\x32\".PaypalMassageAddressResponseProto\x12\x42\n\x19getAddressSnippetResponse\x18% \x01(\x0b\x32\x1f.GetAddressSnippetResponseProto\"\x86\x01\n\x1fRestoreApplicationsRequestProto\x12\x17\n\x0f\x62\x61\x63kupAndroidId\x18\x01 \x01(\t\x12\x12\n\ntosVersion\x18\x02 \x01(\t\x12\x36\n\x13\x64\x65viceConfiguration\x18\x03 \x01(\x0b\x32\x19.DeviceConfigurationProto\"I\n RestoreApplicationsResponseProto\x12%\n\x05\x61sset\x18\x01 \x03(\x0b\x32\x16.GetAssetResponseProto\"/\n\x13RiskHeaderInfoProto\x12\x18\n\x10hashedDeviceInfo\x18\x01 \x01(\t\"L\n\x12SignatureHashProto\x12\x13\n\x0bpackageName\x18\x01 \x01(\t\x12\x13\n\x0bversionCode\x18\x02 \x01(\x05\x12\x0c\n\x04hash\x18\x03 \x01(\x0c\"8\n\x0fSignedDataProto\x12\x12\n\nsignedData\x18\x01 \x01(\t\x12\x11\n\tsignature\x18\x02 \x01(\t\"\xdf\x10\n\x12SingleRequestProto\x12\x42\n\x19requestSpecificProperties\x18\x03 \x01(\x0b\x32\x1f.RequestSpecificPropertiesProto\x12)\n\x0c\x61ssetRequest\x18\x04 \x01(\x0b\x32\x13.AssetsRequestProto\x12.\n\x0f\x63ommentsRequest\x18\x05 \x01(\x0b\x32\x15.CommentsRequestProto\x12\x38\n\x14modifyCommentRequest\x18\x06 \x01(\x0b\x32\x1a.ModifyCommentRequestProto\x12\x36\n\x13purchasePostRequest\x18\x07 \x01(\x0b\x32\x19.PurchasePostRequestProto\x12\x38\n\x14purchaseOrderRequest\x18\x08 \x01(\x0b\x32\x1a.PurchaseOrderRequestProto\x12\x34\n\x12\x63ontentSyncRequest\x18\t \x01(\x0b\x32\x18.ContentSyncRequestProto\x12.\n\x0fgetAssetRequest\x18\n \x01(\x0b\x32\x15.GetAssetRequestProto\x12.\n\x0fgetImageRequest\x18\x0b \x01(\x0b\x32\x15.GetImageRequestProto\x12*\n\rrefundRequest\x18\x0c \x01(\x0b\x32\x13.RefundRequestProto\x12>\n\x17purchaseMetadataRequest\x18\r \x01(\x0b\x32\x1d.PurchaseMetadataRequestProto\x12;\n\x14subCategoriesRequest\x18\x0e \x01(\x0b\x32\x1d.GetSubCategoriesRequestProto\x12<\n\x16uninstallReasonRequest\x18\x10 \x01(\x0b\x32\x1c.UninstallReasonRequestProto\x12\x34\n\x12rateCommentRequest\x18\x11 \x01(\x0b\x32\x18.RateCommentRequestProto\x12\x36\n\x13\x63heckLicenseRequest\x18\x12 \x01(\x0b\x32\x19.CheckLicenseRequestProto\x12@\n\x18getMarketMetadataRequest\x18\x13 \x01(\x0b\x32\x1e.GetMarketMetadataRequestProto\x12\x38\n\x14getCategoriesRequest\x18\x15 \x01(\x0b\x32\x1a.GetCategoriesRequestProto\x12:\n\x15getCarrierInfoRequest\x18\x16 \x01(\x0b\x32\x1b.GetCarrierInfoRequestProto\x12\x34\n\x12removeAssetRequest\x18\x17 \x01(\x0b\x32\x18.RemoveAssetRequestProto\x12\x44\n\x1arestoreApplicationsRequest\x18\x18 \x01(\x0b\x32 .RestoreApplicationsRequestProto\x12<\n\x16querySuggestionRequest\x18\x19 \x01(\x0b\x32\x1c.QuerySuggestionRequestProto\x12\x36\n\x13\x62illingEventRequest\x18\x1a \x01(\x0b\x32\x19.BillingEventRequestProto\x12@\n\x18paypalPreapprovalRequest\x18\x1b \x01(\x0b\x32\x1e.PaypalPreapprovalRequestProto\x12N\n\x1fpaypalPreapprovalDetailsRequest\x18\x1c \x01(\x0b\x32%.PaypalPreapprovalDetailsRequestProto\x12\x44\n\x1apaypalCreateAccountRequest\x18\x1d \x01(\x0b\x32 .PaypalCreateAccountRequestProto\x12V\n#paypalPreapprovalCredentialsRequest\x18\x1e \x01(\x0b\x32).PaypalPreapprovalCredentialsRequestProto\x12N\n\x1finAppRestoreTransactionsRequest\x18\x1f \x01(\x0b\x32%.InAppRestoreTransactionsRequestProto\x12Q\n\"getInAppPurchaseInformationRequest\x18  \x01(\x0b\x32%.InAppPurchaseInformationRequestProto\x12H\n\x1c\x63heckForNotificationsRequest\x18! \x01(\x0b\x32\".CheckForNotificationsRequestProto\x12>\n\x17\x61\x63kNotificationsRequest\x18\" \x01(\x0b\x32\x1d.AckNotificationsRequestProto\x12<\n\x16purchaseProductRequest\x18# \x01(\x0b\x32\x1c.PurchaseProductRequestProto\x12\x44\n\x1areconstructDatabaseRequest\x18$ \x01(\x0b\x32 .ReconstructDatabaseRequestProto\x12\x46\n\x1bpaypalMassageAddressRequest\x18% \x01(\x0b\x32!.PaypalMassageAddressRequestProto\x12@\n\x18getAddressSnippetRequest\x18& \x01(\x0b\x32\x1e.GetAddressSnippetRequestProto\"\xdc\x10\n\x13SingleResponseProto\x12\x34\n\x12responseProperties\x18\x02 \x01(\x0b\x32\x18.ResponsePropertiesProto\x12,\n\x0e\x61ssetsResponse\x18\x03 \x01(\x0b\x32\x14.AssetsResponseProto\x12\x30\n\x10\x63ommentsResponse\x18\x04 \x01(\x0b\x32\x16.CommentsResponseProto\x12:\n\x15modifyCommentResponse\x18\x05 \x01(\x0b\x32\x1b.ModifyCommentResponseProto\x12\x38\n\x14purchasePostResponse\x18\x06 \x01(\x0b\x32\x1a.PurchasePostResponseProto\x12:\n\x15purchaseOrderResponse\x18\x07 \x01(\x0b\x32\x1b.PurchaseOrderResponseProto\x12\x36\n\x13\x63ontentSyncResponse\x18\x08 \x01(\x0b\x32\x19.ContentSyncResponseProto\x12\x30\n\x10getAssetResponse\x18\t \x01(\x0b\x32\x16.GetAssetResponseProto\x12\x30\n\x10getImageResponse\x18\n \x01(\x0b\x32\x16.GetImageResponseProto\x12,\n\x0erefundResponse\x18\x0b \x01(\x0b\x32\x14.RefundResponseProto\x12@\n\x18purchaseMetadataResponse\x18\x0c \x01(\x0b\x32\x1e.PurchaseMetadataResponseProto\x12=\n\x15subCategoriesResponse\x18\r \x01(\x0b\x32\x1e.GetSubCategoriesResponseProto\x12>\n\x17uninstallReasonResponse\x18\x0f \x01(\x0b\x32\x1d.UninstallReasonResponseProto\x12\x36\n\x13rateCommentResponse\x18\x10 \x01(\x0b\x32\x19.RateCommentResponseProto\x12\x38\n\x14\x63heckLicenseResponse\x18\x11 \x01(\x0b\x32\x1a.CheckLicenseResponseProto\x12\x42\n\x19getMarketMetadataResponse\x18\x12 \x01(\x0b\x32\x1f.GetMarketMetadataResponseProto\x12:\n\x15getCategoriesResponse\x18\x14 \x01(\x0b\x32\x1b.GetCategoriesResponseProto\x12<\n\x16getCarrierInfoResponse\x18\x15 \x01(\x0b\x32\x1c.GetCarrierInfoResponseProto\x12\x45\n\x1arestoreApplicationResponse\x18\x17 \x01(\x0b\x32!.RestoreApplicationsResponseProto\x12>\n\x17querySuggestionResponse\x18\x18 \x01(\x0b\x32\x1d.QuerySuggestionResponseProto\x12\x38\n\x14\x62illingEventResponse\x18\x19 \x01(\x0b\x32\x1a.BillingEventResponseProto\x12\x42\n\x19paypalPreapprovalResponse\x18\x1a \x01(\x0b\x32\x1f.PaypalPreapprovalResponseProto\x12P\n paypalPreapprovalDetailsResponse\x18\x1b \x01(\x0b\x32&.PaypalPreapprovalDetailsResponseProto\x12\x46\n\x1bpaypalCreateAccountResponse\x18\x1c \x01(\x0b\x32!.PaypalCreateAccountResponseProto\x12X\n$paypalPreapprovalCredentialsResponse\x18\x1d \x01(\x0b\x32*.PaypalPreapprovalCredentialsResponseProto\x12P\n inAppRestoreTransactionsResponse\x18\x1e \x01(\x0b\x32&.InAppRestoreTransactionsResponseProto\x12S\n#getInAppPurchaseInformationResponse\x18\x1f \x01(\x0b\x32&.InAppPurchaseInformationResponseProto\x12J\n\x1d\x63heckForNotificationsResponse\x18  \x01(\x0b\x32#.CheckForNotificationsResponseProto\x12@\n\x18\x61\x63kNotificationsResponse\x18! \x01(\x0b\x32\x1e.AckNotificationsResponseProto\x12>\n\x17purchaseProductResponse\x18\" \x01(\x0b\x32\x1d.PurchaseProductResponseProto\x12\x46\n\x1breconstructDatabaseResponse\x18# \x01(\x0b\x32!.ReconstructDatabaseResponseProto\x12H\n\x1cpaypalMassageAddressResponse\x18$ \x01(\x0b\x32\".PaypalMassageAddressResponseProto\x12\x42\n\x19getAddressSnippetResponse\x18% \x01(\x0b\x32\x1f.GetAddressSnippetResponseProto\"[\n\x1aStatusBarNotificationProto\x12\x12\n\ntickerText\x18\x01 \x01(\t\x12\x14\n\x0c\x63ontentTitle\x18\x02 \x01(\t\x12\x13\n\x0b\x63ontentText\x18\x03 \x01(\t\">\n\x1bUninstallReasonRequestProto\x12\x0f\n\x07\x61ssetId\x18\x01 \x01(\t\x12\x0e\n\x06reason\x18\x02 \x01(\x05\"\x1e\n\x1cUninstallReasonResponseProto')




_ACKNOTIFICATIONRESPONSE = descriptor.Descriptor(
  name='AckNotificationResponse',
  full_name='AckNotificationResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=20,
  serialized_end=45,
)


_ANDROIDAPPDELIVERYDATA = descriptor.Descriptor(
  name='AndroidAppDeliveryData',
  full_name='AndroidAppDeliveryData',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='downloadSize', full_name='AndroidAppDeliveryData.downloadSize', index=0,
      number=1, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='signature', full_name='AndroidAppDeliveryData.signature', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='downloadUrl', full_name='AndroidAppDeliveryData.downloadUrl', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='additionalFile', full_name='AndroidAppDeliveryData.additionalFile', index=3,
      number=4, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='downloadAuthCookie', full_name='AndroidAppDeliveryData.downloadAuthCookie', index=4,
      number=5, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='forwardLocked', full_name='AndroidAppDeliveryData.forwardLocked', index=5,
      number=6, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='refundTimeout', full_name='AndroidAppDeliveryData.refundTimeout', index=6,
      number=7, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='serverInitiated', full_name='AndroidAppDeliveryData.serverInitiated', index=7,
      number=8, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='postInstallRefundWindowMillis', full_name='AndroidAppDeliveryData.postInstallRefundWindowMillis', index=8,
      number=9, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='immediateStartNeeded', full_name='AndroidAppDeliveryData.immediateStartNeeded', index=9,
      number=10, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='patchData', full_name='AndroidAppDeliveryData.patchData', index=10,
      number=11, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='encryptionParams', full_name='AndroidAppDeliveryData.encryptionParams', index=11,
      number=12, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=48,
  serialized_end=443,
)


_ANDROIDAPPPATCHDATA = descriptor.Descriptor(
  name='AndroidAppPatchData',
  full_name='AndroidAppPatchData',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='baseVersionCode', full_name='AndroidAppPatchData.baseVersionCode', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='baseSignature', full_name='AndroidAppPatchData.baseSignature', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='downloadUrl', full_name='AndroidAppPatchData.downloadUrl', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='patchFormat', full_name='AndroidAppPatchData.patchFormat', index=3,
      number=4, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='maxPatchSize', full_name='AndroidAppPatchData.maxPatchSize', index=4,
      number=5, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=446,
  serialized_end=579,
)


_APPFILEMETADATA = descriptor.Descriptor(
  name='AppFileMetadata',
  full_name='AppFileMetadata',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='fileType', full_name='AppFileMetadata.fileType', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='versionCode', full_name='AppFileMetadata.versionCode', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='size', full_name='AppFileMetadata.size', index=2,
      number=3, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='downloadUrl', full_name='AppFileMetadata.downloadUrl', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=581,
  serialized_end=672,
)


_ENCRYPTIONPARAMS = descriptor.Descriptor(
  name='EncryptionParams',
  full_name='EncryptionParams',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='version', full_name='EncryptionParams.version', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='encryptionKey', full_name='EncryptionParams.encryptionKey', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='hmacKey', full_name='EncryptionParams.hmacKey', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=674,
  serialized_end=749,
)


_HTTPCOOKIE = descriptor.Descriptor(
  name='HttpCookie',
  full_name='HttpCookie',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='name', full_name='HttpCookie.name', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='value', full_name='HttpCookie.value', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=751,
  serialized_end=792,
)


_ADDRESS = descriptor.Descriptor(
  name='Address',
  full_name='Address',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='name', full_name='Address.name', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='addressLine1', full_name='Address.addressLine1', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='addressLine2', full_name='Address.addressLine2', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='city', full_name='Address.city', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='state', full_name='Address.state', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='postalCode', full_name='Address.postalCode', index=5,
      number=6, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='postalCountry', full_name='Address.postalCountry', index=6,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='dependentLocality', full_name='Address.dependentLocality', index=7,
      number=8, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='sortingCode', full_name='Address.sortingCode', index=8,
      number=9, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='languageCode', full_name='Address.languageCode', index=9,
      number=10, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='phoneNumber', full_name='Address.phoneNumber', index=10,
      number=11, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='isReduced', full_name='Address.isReduced', index=11,
      number=12, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='firstName', full_name='Address.firstName', index=12,
      number=13, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='lastName', full_name='Address.lastName', index=13,
      number=14, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='email', full_name='Address.email', index=14,
      number=15, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=795,
  serialized_end=1096,
)


_BOOKAUTHOR = descriptor.Descriptor(
  name='BookAuthor',
  full_name='BookAuthor',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='name', full_name='BookAuthor.name', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='deprecatedQuery', full_name='BookAuthor.deprecatedQuery', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='docid', full_name='BookAuthor.docid', index=2,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=1098,
  serialized_end=1172,
)


_BOOKDETAILS_IDENTIFIER = descriptor.Descriptor(
  name='Identifier',
  full_name='BookDetails.Identifier',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='type', full_name='BookDetails.Identifier.type', index=0,
      number=19, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='identifier', full_name='BookDetails.Identifier.identifier', index=1,
      number=20, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=1580,
  serialized_end=1626,
)

_BOOKDETAILS = descriptor.Descriptor(
  name='BookDetails',
  full_name='BookDetails',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='subject', full_name='BookDetails.subject', index=0,
      number=3, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='publisher', full_name='BookDetails.publisher', index=1,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='publicationDate', full_name='BookDetails.publicationDate', index=2,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='isbn', full_name='BookDetails.isbn', index=3,
      number=6, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='numberOfPages', full_name='BookDetails.numberOfPages', index=4,
      number=7, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='subtitle', full_name='BookDetails.subtitle', index=5,
      number=8, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='author', full_name='BookDetails.author', index=6,
      number=9, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='readerUrl', full_name='BookDetails.readerUrl', index=7,
      number=10, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='downloadEpubUrl', full_name='BookDetails.downloadEpubUrl', index=8,
      number=11, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='downloadPdfUrl', full_name='BookDetails.downloadPdfUrl', index=9,
      number=12, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='acsEpubTokenUrl', full_name='BookDetails.acsEpubTokenUrl', index=10,
      number=13, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='acsPdfTokenUrl', full_name='BookDetails.acsPdfTokenUrl', index=11,
      number=14, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='epubAvailable', full_name='BookDetails.epubAvailable', index=12,
      number=15, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='pdfAvailable', full_name='BookDetails.pdfAvailable', index=13,
      number=16, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='aboutTheAuthor', full_name='BookDetails.aboutTheAuthor', index=14,
      number=17, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='identifier', full_name='BookDetails.identifier', index=15,
      number=18, type=10, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_BOOKDETAILS_IDENTIFIER, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=1175,
  serialized_end=1626,
)


_BOOKSUBJECT = descriptor.Descriptor(
  name='BookSubject',
  full_name='BookSubject',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='name', full_name='BookSubject.name', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='query', full_name='BookSubject.query', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='subjectId', full_name='BookSubject.subjectId', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=1628,
  serialized_end=1689,
)


_BROWSELINK = descriptor.Descriptor(
  name='BrowseLink',
  full_name='BrowseLink',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='name', full_name='BrowseLink.name', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='dataUrl', full_name='BrowseLink.dataUrl', index=1,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=1691,
  serialized_end=1734,
)


_BROWSERESPONSE = descriptor.Descriptor(
  name='BrowseResponse',
  full_name='BrowseResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='contentsUrl', full_name='BrowseResponse.contentsUrl', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='promoUrl', full_name='BrowseResponse.promoUrl', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='category', full_name='BrowseResponse.category', index=2,
      number=3, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='breadcrumb', full_name='BrowseResponse.breadcrumb', index=3,
      number=4, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=1736,
  serialized_end=1855,
)


_ADDRESSCHALLENGE = descriptor.Descriptor(
  name='AddressChallenge',
  full_name='AddressChallenge',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='responseAddressParam', full_name='AddressChallenge.responseAddressParam', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='responseCheckboxesParam', full_name='AddressChallenge.responseCheckboxesParam', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='title', full_name='AddressChallenge.title', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='descriptionHtml', full_name='AddressChallenge.descriptionHtml', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='checkbox', full_name='AddressChallenge.checkbox', index=4,
      number=5, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='address', full_name='AddressChallenge.address', index=5,
      number=6, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='errorInputField', full_name='AddressChallenge.errorInputField', index=6,
      number=7, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='errorHtml', full_name='AddressChallenge.errorHtml', index=7,
      number=8, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='requiredField', full_name='AddressChallenge.requiredField', index=8,
      number=9, type=5, cpp_type=1, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=1858,
  serialized_end=2129,
)


_AUTHENTICATIONCHALLENGE = descriptor.Descriptor(
  name='AuthenticationChallenge',
  full_name='AuthenticationChallenge',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='authenticationType', full_name='AuthenticationChallenge.authenticationType', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='responseAuthenticationTypeParam', full_name='AuthenticationChallenge.responseAuthenticationTypeParam', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='responseRetryCountParam', full_name='AuthenticationChallenge.responseRetryCountParam', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='pinHeaderText', full_name='AuthenticationChallenge.pinHeaderText', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='pinDescriptionTextHtml', full_name='AuthenticationChallenge.pinDescriptionTextHtml', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='gaiaHeaderText', full_name='AuthenticationChallenge.gaiaHeaderText', index=5,
      number=6, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='gaiaDescriptionTextHtml', full_name='AuthenticationChallenge.gaiaDescriptionTextHtml', index=6,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=2132,
  serialized_end=2371,
)


_BUYRESPONSE_CHECKOUTINFO_CHECKOUTOPTION = descriptor.Descriptor(
  name='CheckoutOption',
  full_name='BuyResponse.CheckoutInfo.CheckoutOption',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='formOfPayment', full_name='BuyResponse.CheckoutInfo.CheckoutOption.formOfPayment', index=0,
      number=6, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='encodedAdjustedCart', full_name='BuyResponse.CheckoutInfo.CheckoutOption.encodedAdjustedCart', index=1,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='instrumentId', full_name='BuyResponse.CheckoutInfo.CheckoutOption.instrumentId', index=2,
      number=15, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='item', full_name='BuyResponse.CheckoutInfo.CheckoutOption.item', index=3,
      number=16, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='subItem', full_name='BuyResponse.CheckoutInfo.CheckoutOption.subItem', index=4,
      number=17, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='total', full_name='BuyResponse.CheckoutInfo.CheckoutOption.total', index=5,
      number=18, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='footerHtml', full_name='BuyResponse.CheckoutInfo.CheckoutOption.footerHtml', index=6,
      number=19, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='instrumentFamily', full_name='BuyResponse.CheckoutInfo.CheckoutOption.instrumentFamily', index=7,
      number=29, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='deprecatedInstrumentInapplicableReason', full_name='BuyResponse.CheckoutInfo.CheckoutOption.deprecatedInstrumentInapplicableReason', index=8,
      number=30, type=5, cpp_type=1, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='selectedInstrument', full_name='BuyResponse.CheckoutInfo.CheckoutOption.selectedInstrument', index=9,
      number=32, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='summary', full_name='BuyResponse.CheckoutInfo.CheckoutOption.summary', index=10,
      number=33, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='footnoteHtml', full_name='BuyResponse.CheckoutInfo.CheckoutOption.footnoteHtml', index=11,
      number=35, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='instrument', full_name='BuyResponse.CheckoutInfo.CheckoutOption.instrument', index=12,
      number=43, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='purchaseCookie', full_name='BuyResponse.CheckoutInfo.CheckoutOption.purchaseCookie', index=13,
      number=45, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='disabledReason', full_name='BuyResponse.CheckoutInfo.CheckoutOption.disabledReason', index=14,
      number=48, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=3105,
  serialized_end=3527,
)

_BUYRESPONSE_CHECKOUTINFO = descriptor.Descriptor(
  name='CheckoutInfo',
  full_name='BuyResponse.CheckoutInfo',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='item', full_name='BuyResponse.CheckoutInfo.item', index=0,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='subItem', full_name='BuyResponse.CheckoutInfo.subItem', index=1,
      number=4, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='checkoutoption', full_name='BuyResponse.CheckoutInfo.checkoutoption', index=2,
      number=5, type=10, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='deprecatedCheckoutUrl', full_name='BuyResponse.CheckoutInfo.deprecatedCheckoutUrl', index=3,
      number=10, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='addInstrumentUrl', full_name='BuyResponse.CheckoutInfo.addInstrumentUrl', index=4,
      number=11, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='footerHtml', full_name='BuyResponse.CheckoutInfo.footerHtml', index=5,
      number=20, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='eligibleInstrumentFamily', full_name='BuyResponse.CheckoutInfo.eligibleInstrumentFamily', index=6,
      number=31, type=5, cpp_type=1, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='footnoteHtml', full_name='BuyResponse.CheckoutInfo.footnoteHtml', index=7,
      number=36, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='eligibleInstrument', full_name='BuyResponse.CheckoutInfo.eligibleInstrument', index=8,
      number=44, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_BUYRESPONSE_CHECKOUTINFO_CHECKOUTOPTION, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=2795,
  serialized_end=3527,
)

_BUYRESPONSE = descriptor.Descriptor(
  name='BuyResponse',
  full_name='BuyResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='purchaseResponse', full_name='BuyResponse.purchaseResponse', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='checkoutinfo', full_name='BuyResponse.checkoutinfo', index=1,
      number=2, type=10, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='continueViaUrl', full_name='BuyResponse.continueViaUrl', index=2,
      number=8, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='purchaseStatusUrl', full_name='BuyResponse.purchaseStatusUrl', index=3,
      number=9, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='checkoutServiceId', full_name='BuyResponse.checkoutServiceId', index=4,
      number=12, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='checkoutTokenRequired', full_name='BuyResponse.checkoutTokenRequired', index=5,
      number=13, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='baseCheckoutUrl', full_name='BuyResponse.baseCheckoutUrl', index=6,
      number=14, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='tosCheckboxHtml', full_name='BuyResponse.tosCheckboxHtml', index=7,
      number=37, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='iabPermissionError', full_name='BuyResponse.iabPermissionError', index=8,
      number=38, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='purchaseStatusResponse', full_name='BuyResponse.purchaseStatusResponse', index=9,
      number=39, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='purchaseCookie', full_name='BuyResponse.purchaseCookie', index=10,
      number=46, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='challenge', full_name='BuyResponse.challenge', index=11,
      number=49, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_BUYRESPONSE_CHECKOUTINFO, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=2374,
  serialized_end=3527,
)


_CHALLENGE = descriptor.Descriptor(
  name='Challenge',
  full_name='Challenge',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='addressChallenge', full_name='Challenge.addressChallenge', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='authenticationChallenge', full_name='Challenge.authenticationChallenge', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=3529,
  serialized_end=3644,
)


_FORMCHECKBOX = descriptor.Descriptor(
  name='FormCheckbox',
  full_name='FormCheckbox',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='description', full_name='FormCheckbox.description', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='checked', full_name='FormCheckbox.checked', index=1,
      number=2, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='required', full_name='FormCheckbox.required', index=2,
      number=3, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=3646,
  serialized_end=3716,
)


_LINEITEM = descriptor.Descriptor(
  name='LineItem',
  full_name='LineItem',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='name', full_name='LineItem.name', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='description', full_name='LineItem.description', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='offer', full_name='LineItem.offer', index=2,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='amount', full_name='LineItem.amount', index=3,
      number=4, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=3718,
  serialized_end=3810,
)


_MONEY = descriptor.Descriptor(
  name='Money',
  full_name='Money',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='micros', full_name='Money.micros', index=0,
      number=1, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='currencyCode', full_name='Money.currencyCode', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='formattedAmount', full_name='Money.formattedAmount', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=3812,
  serialized_end=3882,
)


_PURCHASENOTIFICATIONRESPONSE = descriptor.Descriptor(
  name='PurchaseNotificationResponse',
  full_name='PurchaseNotificationResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='status', full_name='PurchaseNotificationResponse.status', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='debugInfo', full_name='PurchaseNotificationResponse.debugInfo', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='localizedErrorMessage', full_name='PurchaseNotificationResponse.localizedErrorMessage', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='purchaseId', full_name='PurchaseNotificationResponse.purchaseId', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=3885,
  serialized_end=4013,
)


_PURCHASESTATUSRESPONSE = descriptor.Descriptor(
  name='PurchaseStatusResponse',
  full_name='PurchaseStatusResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='status', full_name='PurchaseStatusResponse.status', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='statusMsg', full_name='PurchaseStatusResponse.statusMsg', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='statusTitle', full_name='PurchaseStatusResponse.statusTitle', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='briefMessage', full_name='PurchaseStatusResponse.briefMessage', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='infoUrl', full_name='PurchaseStatusResponse.infoUrl', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='libraryUpdate', full_name='PurchaseStatusResponse.libraryUpdate', index=5,
      number=6, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='rejectedInstrument', full_name='PurchaseStatusResponse.rejectedInstrument', index=6,
      number=7, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='appDeliveryData', full_name='PurchaseStatusResponse.appDeliveryData', index=7,
      number=8, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=4016,
  serialized_end=4265,
)


_CHECKINSTRUMENTRESPONSE = descriptor.Descriptor(
  name='CheckInstrumentResponse',
  full_name='CheckInstrumentResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='userHasValidInstrument', full_name='CheckInstrumentResponse.userHasValidInstrument', index=0,
      number=1, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='checkoutTokenRequired', full_name='CheckInstrumentResponse.checkoutTokenRequired', index=1,
      number=2, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='instrument', full_name='CheckInstrumentResponse.instrument', index=2,
      number=4, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='eligibleInstrument', full_name='CheckInstrumentResponse.eligibleInstrument', index=3,
      number=5, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=4268,
  serialized_end=4430,
)


_UPDATEINSTRUMENTREQUEST = descriptor.Descriptor(
  name='UpdateInstrumentRequest',
  full_name='UpdateInstrumentRequest',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='instrument', full_name='UpdateInstrumentRequest.instrument', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='checkoutToken', full_name='UpdateInstrumentRequest.checkoutToken', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=4432,
  serialized_end=4513,
)


_UPDATEINSTRUMENTRESPONSE = descriptor.Descriptor(
  name='UpdateInstrumentResponse',
  full_name='UpdateInstrumentResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='result', full_name='UpdateInstrumentResponse.result', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='instrumentId', full_name='UpdateInstrumentResponse.instrumentId', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='userMessageHtml', full_name='UpdateInstrumentResponse.userMessageHtml', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='errorInputField', full_name='UpdateInstrumentResponse.errorInputField', index=3,
      number=4, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='checkoutTokenRequired', full_name='UpdateInstrumentResponse.checkoutTokenRequired', index=4,
      number=5, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='redeemedOffer', full_name='UpdateInstrumentResponse.redeemedOffer', index=5,
      number=6, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=4516,
  serialized_end=4728,
)


_INITIATEASSOCIATIONRESPONSE = descriptor.Descriptor(
  name='InitiateAssociationResponse',
  full_name='InitiateAssociationResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='userToken', full_name='InitiateAssociationResponse.userToken', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=4730,
  serialized_end=4778,
)


_VERIFYASSOCIATIONRESPONSE = descriptor.Descriptor(
  name='VerifyAssociationResponse',
  full_name='VerifyAssociationResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='status', full_name='VerifyAssociationResponse.status', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='billingAddress', full_name='VerifyAssociationResponse.billingAddress', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='carrierTos', full_name='VerifyAssociationResponse.carrierTos', index=2,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=4780,
  serialized_end=4890,
)


_ADDCREDITCARDPROMOOFFER = descriptor.Descriptor(
  name='AddCreditCardPromoOffer',
  full_name='AddCreditCardPromoOffer',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='headerText', full_name='AddCreditCardPromoOffer.headerText', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='descriptionHtml', full_name='AddCreditCardPromoOffer.descriptionHtml', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='image', full_name='AddCreditCardPromoOffer.image', index=2,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='introductoryTextHtml', full_name='AddCreditCardPromoOffer.introductoryTextHtml', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='offerTitle', full_name='AddCreditCardPromoOffer.offerTitle', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='noActionDescription', full_name='AddCreditCardPromoOffer.noActionDescription', index=5,
      number=6, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='termsAndConditionsHtml', full_name='AddCreditCardPromoOffer.termsAndConditionsHtml', index=6,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=4893,
  serialized_end=5097,
)


_AVAILABLEPROMOOFFER = descriptor.Descriptor(
  name='AvailablePromoOffer',
  full_name='AvailablePromoOffer',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='addCreditCardOffer', full_name='AvailablePromoOffer.addCreditCardOffer', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=5099,
  serialized_end=5174,
)


_CHECKPROMOOFFERRESPONSE = descriptor.Descriptor(
  name='CheckPromoOfferResponse',
  full_name='CheckPromoOfferResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='availableOffer', full_name='CheckPromoOfferResponse.availableOffer', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='redeemedOffer', full_name='CheckPromoOfferResponse.redeemedOffer', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='checkoutTokenRequired', full_name='CheckPromoOfferResponse.checkoutTokenRequired', index=2,
      number=3, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=5177,
  serialized_end=5323,
)


_REDEEMEDPROMOOFFER = descriptor.Descriptor(
  name='RedeemedPromoOffer',
  full_name='RedeemedPromoOffer',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='headerText', full_name='RedeemedPromoOffer.headerText', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='descriptionHtml', full_name='RedeemedPromoOffer.descriptionHtml', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='image', full_name='RedeemedPromoOffer.image', index=2,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=5325,
  serialized_end=5413,
)


_DOCID = descriptor.Descriptor(
  name='Docid',
  full_name='Docid',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='backendDocid', full_name='Docid.backendDocid', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='type', full_name='Docid.type', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='backend', full_name='Docid.backend', index=2,
      number=3, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=5415,
  serialized_end=5475,
)


_INSTALL = descriptor.Descriptor(
  name='Install',
  full_name='Install',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='androidId', full_name='Install.androidId', index=0,
      number=1, type=6, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='version', full_name='Install.version', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='bundled', full_name='Install.bundled', index=2,
      number=3, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=5477,
  serialized_end=5539,
)


_OFFER = descriptor.Descriptor(
  name='Offer',
  full_name='Offer',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='micros', full_name='Offer.micros', index=0,
      number=1, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='currencyCode', full_name='Offer.currencyCode', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='formattedAmount', full_name='Offer.formattedAmount', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='convertedPrice', full_name='Offer.convertedPrice', index=3,
      number=4, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='checkoutFlowRequired', full_name='Offer.checkoutFlowRequired', index=4,
      number=5, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='fullPriceMicros', full_name='Offer.fullPriceMicros', index=5,
      number=6, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='formattedFullAmount', full_name='Offer.formattedFullAmount', index=6,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='offerType', full_name='Offer.offerType', index=7,
      number=8, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='rentalTerms', full_name='Offer.rentalTerms', index=8,
      number=9, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='onSaleDate', full_name='Offer.onSaleDate', index=9,
      number=10, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='promotionLabel', full_name='Offer.promotionLabel', index=10,
      number=11, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='subscriptionTerms', full_name='Offer.subscriptionTerms', index=11,
      number=12, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='formattedName', full_name='Offer.formattedName', index=12,
      number=13, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='formattedDescription', full_name='Offer.formattedDescription', index=13,
      number=14, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=5542,
  serialized_end=5926,
)


_OWNERSHIPINFO = descriptor.Descriptor(
  name='OwnershipInfo',
  full_name='OwnershipInfo',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='initiationTimestampMsec', full_name='OwnershipInfo.initiationTimestampMsec', index=0,
      number=1, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='validUntilTimestampMsec', full_name='OwnershipInfo.validUntilTimestampMsec', index=1,
      number=2, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='autoRenewing', full_name='OwnershipInfo.autoRenewing', index=2,
      number=3, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='refundTimeoutTimestampMsec', full_name='OwnershipInfo.refundTimeoutTimestampMsec', index=3,
      number=4, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='postDeliveryRefundWindowMsec', full_name='OwnershipInfo.postDeliveryRefundWindowMsec', index=4,
      number=5, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=5929,
  serialized_end=6106,
)


_RENTALTERMS = descriptor.Descriptor(
  name='RentalTerms',
  full_name='RentalTerms',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='grantPeriodSeconds', full_name='RentalTerms.grantPeriodSeconds', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='activatePeriodSeconds', full_name='RentalTerms.activatePeriodSeconds', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=6108,
  serialized_end=6180,
)


_SUBSCRIPTIONTERMS = descriptor.Descriptor(
  name='SubscriptionTerms',
  full_name='SubscriptionTerms',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='recurringPeriod', full_name='SubscriptionTerms.recurringPeriod', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='trialPeriod', full_name='SubscriptionTerms.trialPeriod', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=6182,
  serialized_end=6273,
)


_TIMEPERIOD = descriptor.Descriptor(
  name='TimePeriod',
  full_name='TimePeriod',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='unit', full_name='TimePeriod.unit', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='count', full_name='TimePeriod.count', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=6275,
  serialized_end=6316,
)


_BILLINGADDRESSSPEC = descriptor.Descriptor(
  name='BillingAddressSpec',
  full_name='BillingAddressSpec',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='billingAddressType', full_name='BillingAddressSpec.billingAddressType', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='requiredField', full_name='BillingAddressSpec.requiredField', index=1,
      number=2, type=5, cpp_type=1, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=6318,
  serialized_end=6389,
)


_CARRIERBILLINGCREDENTIALS = descriptor.Descriptor(
  name='CarrierBillingCredentials',
  full_name='CarrierBillingCredentials',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='value', full_name='CarrierBillingCredentials.value', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='expiration', full_name='CarrierBillingCredentials.expiration', index=1,
      number=2, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=6391,
  serialized_end=6453,
)


_CARRIERBILLINGINSTRUMENT = descriptor.Descriptor(
  name='CarrierBillingInstrument',
  full_name='CarrierBillingInstrument',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='instrumentKey', full_name='CarrierBillingInstrument.instrumentKey', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='accountType', full_name='CarrierBillingInstrument.accountType', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='currencyCode', full_name='CarrierBillingInstrument.currencyCode', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='transactionLimit', full_name='CarrierBillingInstrument.transactionLimit', index=3,
      number=4, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='subscriberIdentifier', full_name='CarrierBillingInstrument.subscriberIdentifier', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='encryptedSubscriberInfo', full_name='CarrierBillingInstrument.encryptedSubscriberInfo', index=5,
      number=6, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='credentials', full_name='CarrierBillingInstrument.credentials', index=6,
      number=7, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='acceptedCarrierTos', full_name='CarrierBillingInstrument.acceptedCarrierTos', index=7,
      number=8, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=6456,
  serialized_end=6753,
)


_CARRIERBILLINGINSTRUMENTSTATUS = descriptor.Descriptor(
  name='CarrierBillingInstrumentStatus',
  full_name='CarrierBillingInstrumentStatus',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='carrierTos', full_name='CarrierBillingInstrumentStatus.carrierTos', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='associationRequired', full_name='CarrierBillingInstrumentStatus.associationRequired', index=1,
      number=2, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='passwordRequired', full_name='CarrierBillingInstrumentStatus.passwordRequired', index=2,
      number=3, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='carrierPasswordPrompt', full_name='CarrierBillingInstrumentStatus.carrierPasswordPrompt', index=3,
      number=4, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='apiVersion', full_name='CarrierBillingInstrumentStatus.apiVersion', index=4,
      number=5, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='name', full_name='CarrierBillingInstrumentStatus.name', index=5,
      number=6, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=6756,
  serialized_end=6958,
)


_CARRIERTOS = descriptor.Descriptor(
  name='CarrierTos',
  full_name='CarrierTos',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='dcbTos', full_name='CarrierTos.dcbTos', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='piiTos', full_name='CarrierTos.piiTos', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='needsDcbTosAcceptance', full_name='CarrierTos.needsDcbTosAcceptance', index=2,
      number=3, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='needsPiiTosAcceptance', full_name='CarrierTos.needsPiiTosAcceptance', index=3,
      number=4, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=6961,
  serialized_end=7103,
)


_CARRIERTOSENTRY = descriptor.Descriptor(
  name='CarrierTosEntry',
  full_name='CarrierTosEntry',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='url', full_name='CarrierTosEntry.url', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='version', full_name='CarrierTosEntry.version', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=7105,
  serialized_end=7152,
)


_CREDITCARDINSTRUMENT = descriptor.Descriptor(
  name='CreditCardInstrument',
  full_name='CreditCardInstrument',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='type', full_name='CreditCardInstrument.type', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='escrowHandle', full_name='CreditCardInstrument.escrowHandle', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='lastDigits', full_name='CreditCardInstrument.lastDigits', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='expirationMonth', full_name='CreditCardInstrument.expirationMonth', index=3,
      number=4, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='expirationYear', full_name='CreditCardInstrument.expirationYear', index=4,
      number=5, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='escrowEfeParam', full_name='CreditCardInstrument.escrowEfeParam', index=5,
      number=6, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=7155,
  serialized_end=7317,
)


_EFEPARAM = descriptor.Descriptor(
  name='EfeParam',
  full_name='EfeParam',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='key', full_name='EfeParam.key', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='value', full_name='EfeParam.value', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=7319,
  serialized_end=7357,
)


_INPUTVALIDATIONERROR = descriptor.Descriptor(
  name='InputValidationError',
  full_name='InputValidationError',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='inputField', full_name='InputValidationError.inputField', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='errorMessage', full_name='InputValidationError.errorMessage', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=7359,
  serialized_end=7423,
)


_INSTRUMENT = descriptor.Descriptor(
  name='Instrument',
  full_name='Instrument',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='instrumentId', full_name='Instrument.instrumentId', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='billingAddress', full_name='Instrument.billingAddress', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='creditCard', full_name='Instrument.creditCard', index=2,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='carrierBilling', full_name='Instrument.carrierBilling', index=3,
      number=4, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='billingAddressSpec', full_name='Instrument.billingAddressSpec', index=4,
      number=5, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='instrumentFamily', full_name='Instrument.instrumentFamily', index=5,
      number=6, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='carrierBillingStatus', full_name='Instrument.carrierBillingStatus', index=6,
      number=7, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='displayTitle', full_name='Instrument.displayTitle', index=7,
      number=8, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=7426,
  serialized_end=7748,
)


_PASSWORDPROMPT = descriptor.Descriptor(
  name='PasswordPrompt',
  full_name='PasswordPrompt',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='prompt', full_name='PasswordPrompt.prompt', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='forgotPasswordUrl', full_name='PasswordPrompt.forgotPasswordUrl', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=7750,
  serialized_end=7809,
)


_CONTAINERMETADATA = descriptor.Descriptor(
  name='ContainerMetadata',
  full_name='ContainerMetadata',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='browseUrl', full_name='ContainerMetadata.browseUrl', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='nextPageUrl', full_name='ContainerMetadata.nextPageUrl', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='relevance', full_name='ContainerMetadata.relevance', index=2,
      number=3, type=1, cpp_type=5, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='estimatedResults', full_name='ContainerMetadata.estimatedResults', index=3,
      number=4, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='analyticsCookie', full_name='ContainerMetadata.analyticsCookie', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='ordered', full_name='ContainerMetadata.ordered', index=5,
      number=6, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=7812,
  serialized_end=7958,
)


_FLAGCONTENTRESPONSE = descriptor.Descriptor(
  name='FlagContentResponse',
  full_name='FlagContentResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=7960,
  serialized_end=7981,
)


_DEBUGINFO_TIMING = descriptor.Descriptor(
  name='Timing',
  full_name='DebugInfo.Timing',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='name', full_name='DebugInfo.Timing.name', index=0,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='timeInMs', full_name='DebugInfo.Timing.timeInMs', index=1,
      number=4, type=1, cpp_type=5, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=8048,
  serialized_end=8088,
)

_DEBUGINFO = descriptor.Descriptor(
  name='DebugInfo',
  full_name='DebugInfo',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='message', full_name='DebugInfo.message', index=0,
      number=1, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='timing', full_name='DebugInfo.timing', index=1,
      number=2, type=10, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_DEBUGINFO_TIMING, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=7983,
  serialized_end=8088,
)


_DELIVERYRESPONSE = descriptor.Descriptor(
  name='DeliveryResponse',
  full_name='DeliveryResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='status', full_name='DeliveryResponse.status', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='appDeliveryData', full_name='DeliveryResponse.appDeliveryData', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=8090,
  serialized_end=8174,
)


_BULKDETAILSENTRY = descriptor.Descriptor(
  name='BulkDetailsEntry',
  full_name='BulkDetailsEntry',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='doc', full_name='BulkDetailsEntry.doc', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=8176,
  serialized_end=8215,
)


_BULKDETAILSREQUEST = descriptor.Descriptor(
  name='BulkDetailsRequest',
  full_name='BulkDetailsRequest',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='docid', full_name='BulkDetailsRequest.docid', index=0,
      number=1, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='includeChildDocs', full_name='BulkDetailsRequest.includeChildDocs', index=1,
      number=2, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=8217,
  serialized_end=8278,
)


_BULKDETAILSRESPONSE = descriptor.Descriptor(
  name='BulkDetailsResponse',
  full_name='BulkDetailsResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='entry', full_name='BulkDetailsResponse.entry', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=8280,
  serialized_end=8335,
)


_DETAILSRESPONSE = descriptor.Descriptor(
  name='DetailsResponse',
  full_name='DetailsResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='docV1', full_name='DetailsResponse.docV1', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='analyticsCookie', full_name='DetailsResponse.analyticsCookie', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='userReview', full_name='DetailsResponse.userReview', index=2,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='docV2', full_name='DetailsResponse.docV2', index=3,
      number=4, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='footerHtml', full_name='DetailsResponse.footerHtml', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=8338,
  serialized_end=8475,
)


_DEVICECONFIGURATIONPROTO = descriptor.Descriptor(
  name='DeviceConfigurationProto',
  full_name='DeviceConfigurationProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='touchScreen', full_name='DeviceConfigurationProto.touchScreen', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='keyboard', full_name='DeviceConfigurationProto.keyboard', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='navigation', full_name='DeviceConfigurationProto.navigation', index=2,
      number=3, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='screenLayout', full_name='DeviceConfigurationProto.screenLayout', index=3,
      number=4, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='hasHardKeyboard', full_name='DeviceConfigurationProto.hasHardKeyboard', index=4,
      number=5, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='hasFiveWayNavigation', full_name='DeviceConfigurationProto.hasFiveWayNavigation', index=5,
      number=6, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='screenDensity', full_name='DeviceConfigurationProto.screenDensity', index=6,
      number=7, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='glEsVersion', full_name='DeviceConfigurationProto.glEsVersion', index=7,
      number=8, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='systemSharedLibrary', full_name='DeviceConfigurationProto.systemSharedLibrary', index=8,
      number=9, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='systemAvailableFeature', full_name='DeviceConfigurationProto.systemAvailableFeature', index=9,
      number=10, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='nativePlatform', full_name='DeviceConfigurationProto.nativePlatform', index=10,
      number=11, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='screenWidth', full_name='DeviceConfigurationProto.screenWidth', index=11,
      number=12, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='screenHeight', full_name='DeviceConfigurationProto.screenHeight', index=12,
      number=13, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='systemSupportedLocale', full_name='DeviceConfigurationProto.systemSupportedLocale', index=13,
      number=14, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='glExtension', full_name='DeviceConfigurationProto.glExtension', index=14,
      number=15, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='deviceClass', full_name='DeviceConfigurationProto.deviceClass', index=15,
      number=16, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='maxApkDownloadSizeMb', full_name='DeviceConfigurationProto.maxApkDownloadSizeMb', index=16,
      number=17, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=8478,
  serialized_end=8915,
)


_DOCUMENT = descriptor.Descriptor(
  name='Document',
  full_name='Document',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='docid', full_name='Document.docid', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='fetchDocid', full_name='Document.fetchDocid', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='sampleDocid', full_name='Document.sampleDocid', index=2,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='title', full_name='Document.title', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='url', full_name='Document.url', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='snippet', full_name='Document.snippet', index=5,
      number=6, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='priceDeprecated', full_name='Document.priceDeprecated', index=6,
      number=7, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='availability', full_name='Document.availability', index=7,
      number=9, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='image', full_name='Document.image', index=8,
      number=10, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='child', full_name='Document.child', index=9,
      number=11, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='aggregateRating', full_name='Document.aggregateRating', index=10,
      number=13, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='offer', full_name='Document.offer', index=11,
      number=14, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='translatedSnippet', full_name='Document.translatedSnippet', index=12,
      number=15, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='documentVariant', full_name='Document.documentVariant', index=13,
      number=16, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='categoryId', full_name='Document.categoryId', index=14,
      number=17, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='decoration', full_name='Document.decoration', index=15,
      number=18, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='parent', full_name='Document.parent', index=16,
      number=19, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='privacyPolicyUrl', full_name='Document.privacyPolicyUrl', index=17,
      number=20, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=8918,
  serialized_end=9429,
)


_DOCUMENTVARIANT = descriptor.Descriptor(
  name='DocumentVariant',
  full_name='DocumentVariant',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='variationType', full_name='DocumentVariant.variationType', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='rule', full_name='DocumentVariant.rule', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='title', full_name='DocumentVariant.title', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='snippet', full_name='DocumentVariant.snippet', index=3,
      number=4, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='recentChanges', full_name='DocumentVariant.recentChanges', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='autoTranslation', full_name='DocumentVariant.autoTranslation', index=5,
      number=6, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='offer', full_name='DocumentVariant.offer', index=6,
      number=7, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='channelId', full_name='DocumentVariant.channelId', index=7,
      number=9, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='child', full_name='DocumentVariant.child', index=8,
      number=10, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='decoration', full_name='DocumentVariant.decoration', index=9,
      number=11, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=9432,
  serialized_end=9689,
)


_IMAGE_DIMENSION = descriptor.Descriptor(
  name='Dimension',
  full_name='Image.Dimension',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='width', full_name='Image.Dimension.width', index=0,
      number=3, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='height', full_name='Image.Dimension.height', index=1,
      number=4, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=9915,
  serialized_end=9957,
)

_IMAGE_CITATION = descriptor.Descriptor(
  name='Citation',
  full_name='Image.Citation',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='titleLocalized', full_name='Image.Citation.titleLocalized', index=0,
      number=11, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='url', full_name='Image.Citation.url', index=1,
      number=12, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=9959,
  serialized_end=10006,
)

_IMAGE = descriptor.Descriptor(
  name='Image',
  full_name='Image',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='imageType', full_name='Image.imageType', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='dimension', full_name='Image.dimension', index=1,
      number=2, type=10, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='imageUrl', full_name='Image.imageUrl', index=2,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='altTextLocalized', full_name='Image.altTextLocalized', index=3,
      number=6, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='secureUrl', full_name='Image.secureUrl', index=4,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='positionInSequence', full_name='Image.positionInSequence', index=5,
      number=8, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='supportsFifeUrlOptions', full_name='Image.supportsFifeUrlOptions', index=6,
      number=9, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='citation', full_name='Image.citation', index=7,
      number=10, type=10, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_IMAGE_DIMENSION, _IMAGE_CITATION, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=9692,
  serialized_end=10006,
)


_TRANSLATEDTEXT = descriptor.Descriptor(
  name='TranslatedText',
  full_name='TranslatedText',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='text', full_name='TranslatedText.text', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='sourceLocale', full_name='TranslatedText.sourceLocale', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='targetLocale', full_name='TranslatedText.targetLocale', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=10008,
  serialized_end=10082,
)


_BADGE = descriptor.Descriptor(
  name='Badge',
  full_name='Badge',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='title', full_name='Badge.title', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='image', full_name='Badge.image', index=1,
      number=2, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='browseUrl', full_name='Badge.browseUrl', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=10084,
  serialized_end=10148,
)


_CONTAINERWITHBANNER = descriptor.Descriptor(
  name='ContainerWithBanner',
  full_name='ContainerWithBanner',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='colorThemeArgb', full_name='ContainerWithBanner.colorThemeArgb', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=10150,
  serialized_end=10195,
)


_DEALOFTHEDAY = descriptor.Descriptor(
  name='DealOfTheDay',
  full_name='DealOfTheDay',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='featuredHeader', full_name='DealOfTheDay.featuredHeader', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='colorThemeArgb', full_name='DealOfTheDay.colorThemeArgb', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=10197,
  serialized_end=10259,
)


_EDITORIALSERIESCONTAINER = descriptor.Descriptor(
  name='EditorialSeriesContainer',
  full_name='EditorialSeriesContainer',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='seriesTitle', full_name='EditorialSeriesContainer.seriesTitle', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='seriesSubtitle', full_name='EditorialSeriesContainer.seriesSubtitle', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='episodeTitle', full_name='EditorialSeriesContainer.episodeTitle', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='episodeSubtitle', full_name='EditorialSeriesContainer.episodeSubtitle', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='colorThemeArgb', full_name='EditorialSeriesContainer.colorThemeArgb', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=10262,
  serialized_end=10404,
)


_LINK = descriptor.Descriptor(
  name='Link',
  full_name='Link',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='uri', full_name='Link.uri', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=10406,
  serialized_end=10425,
)


_PLUSONEDATA = descriptor.Descriptor(
  name='PlusOneData',
  full_name='PlusOneData',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='setByUser', full_name='PlusOneData.setByUser', index=0,
      number=1, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='total', full_name='PlusOneData.total', index=1,
      number=2, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='circlesTotal', full_name='PlusOneData.circlesTotal', index=2,
      number=3, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='circlesPeople', full_name='PlusOneData.circlesPeople', index=3,
      number=4, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=10427,
  serialized_end=10532,
)


_PLUSPERSON = descriptor.Descriptor(
  name='PlusPerson',
  full_name='PlusPerson',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='displayName', full_name='PlusPerson.displayName', index=0,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='profileImageUrl', full_name='PlusPerson.profileImageUrl', index=1,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=10534,
  serialized_end=10592,
)


_PROMOTEDDOC = descriptor.Descriptor(
  name='PromotedDoc',
  full_name='PromotedDoc',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='title', full_name='PromotedDoc.title', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='subtitle', full_name='PromotedDoc.subtitle', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='image', full_name='PromotedDoc.image', index=2,
      number=3, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='descriptionHtml', full_name='PromotedDoc.descriptionHtml', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='detailsUrl', full_name='PromotedDoc.detailsUrl', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=10594,
  serialized_end=10708,
)


_REASON = descriptor.Descriptor(
  name='Reason',
  full_name='Reason',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='briefReason', full_name='Reason.briefReason', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='detailedReason', full_name='Reason.detailedReason', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='uniqueId', full_name='Reason.uniqueId', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=10710,
  serialized_end=10781,
)


_SECTIONMETADATA = descriptor.Descriptor(
  name='SectionMetadata',
  full_name='SectionMetadata',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='header', full_name='SectionMetadata.header', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='listUrl', full_name='SectionMetadata.listUrl', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='browseUrl', full_name='SectionMetadata.browseUrl', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='descriptionHtml', full_name='SectionMetadata.descriptionHtml', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=10783,
  serialized_end=10877,
)


_SERIESANTENNA = descriptor.Descriptor(
  name='SeriesAntenna',
  full_name='SeriesAntenna',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='seriesTitle', full_name='SeriesAntenna.seriesTitle', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='seriesSubtitle', full_name='SeriesAntenna.seriesSubtitle', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='episodeTitle', full_name='SeriesAntenna.episodeTitle', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='episodeSubtitle', full_name='SeriesAntenna.episodeSubtitle', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='colorThemeArgb', full_name='SeriesAntenna.colorThemeArgb', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='sectionTracks', full_name='SeriesAntenna.sectionTracks', index=5,
      number=6, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='sectionAlbums', full_name='SeriesAntenna.sectionAlbums', index=6,
      number=7, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=10880,
  serialized_end=11093,
)


_TEMPLATE = descriptor.Descriptor(
  name='Template',
  full_name='Template',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='seriesAntenna', full_name='Template.seriesAntenna', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='tileGraphic2X1', full_name='Template.tileGraphic2X1', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='tileGraphic4X2', full_name='Template.tileGraphic4X2', index=2,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='tileGraphicColoredTitle2X1', full_name='Template.tileGraphicColoredTitle2X1', index=3,
      number=4, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='tileGraphicUpperLeftTitle2X1', full_name='Template.tileGraphicUpperLeftTitle2X1', index=4,
      number=5, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='tileDetailsReflectedGraphic2X2', full_name='Template.tileDetailsReflectedGraphic2X2', index=5,
      number=6, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='tileFourBlock4X2', full_name='Template.tileFourBlock4X2', index=6,
      number=7, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='containerWithBanner', full_name='Template.containerWithBanner', index=7,
      number=8, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='dealOfTheDay', full_name='Template.dealOfTheDay', index=8,
      number=9, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='tileGraphicColoredTitle4X2', full_name='Template.tileGraphicColoredTitle4X2', index=9,
      number=10, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='editorialSeriesContainer', full_name='Template.editorialSeriesContainer', index=10,
      number=11, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=11096,
  serialized_end=11623,
)


_TILETEMPLATE = descriptor.Descriptor(
  name='TileTemplate',
  full_name='TileTemplate',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='colorThemeArgb', full_name='TileTemplate.colorThemeArgb', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='colorTextArgb', full_name='TileTemplate.colorTextArgb', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=11625,
  serialized_end=11686,
)


_WARNING = descriptor.Descriptor(
  name='Warning',
  full_name='Warning',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='localizedMessage', full_name='Warning.localizedMessage', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=11688,
  serialized_end=11723,
)


_ALBUMDETAILS = descriptor.Descriptor(
  name='AlbumDetails',
  full_name='AlbumDetails',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='name', full_name='AlbumDetails.name', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='details', full_name='AlbumDetails.details', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='displayArtist', full_name='AlbumDetails.displayArtist', index=2,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=11725,
  serialized_end=11824,
)


_APPDETAILS = descriptor.Descriptor(
  name='AppDetails',
  full_name='AppDetails',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='developerName', full_name='AppDetails.developerName', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='majorVersionNumber', full_name='AppDetails.majorVersionNumber', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='versionCode', full_name='AppDetails.versionCode', index=2,
      number=3, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='versionString', full_name='AppDetails.versionString', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='title', full_name='AppDetails.title', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='appCategory', full_name='AppDetails.appCategory', index=5,
      number=7, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='contentRating', full_name='AppDetails.contentRating', index=6,
      number=8, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='installationSize', full_name='AppDetails.installationSize', index=7,
      number=9, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='permission', full_name='AppDetails.permission', index=8,
      number=10, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='developerEmail', full_name='AppDetails.developerEmail', index=9,
      number=11, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='developerWebsite', full_name='AppDetails.developerWebsite', index=10,
      number=12, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='numDownloads', full_name='AppDetails.numDownloads', index=11,
      number=13, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='packageName', full_name='AppDetails.packageName', index=12,
      number=14, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='recentChangesHtml', full_name='AppDetails.recentChangesHtml', index=13,
      number=15, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='uploadDate', full_name='AppDetails.uploadDate', index=14,
      number=16, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='file', full_name='AppDetails.file', index=15,
      number=17, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='appType', full_name='AppDetails.appType', index=16,
      number=18, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=11827,
  serialized_end=12225,
)


_ARTISTDETAILS = descriptor.Descriptor(
  name='ArtistDetails',
  full_name='ArtistDetails',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='detailsUrl', full_name='ArtistDetails.detailsUrl', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='name', full_name='ArtistDetails.name', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='externalLinks', full_name='ArtistDetails.externalLinks', index=2,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=12227,
  serialized_end=12321,
)


_ARTISTEXTERNALLINKS = descriptor.Descriptor(
  name='ArtistExternalLinks',
  full_name='ArtistExternalLinks',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='websiteUrl', full_name='ArtistExternalLinks.websiteUrl', index=0,
      number=1, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='googlePlusProfileUrl', full_name='ArtistExternalLinks.googlePlusProfileUrl', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='youtubeChannelUrl', full_name='ArtistExternalLinks.youtubeChannelUrl', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=12323,
  serialized_end=12421,
)


_DOCUMENTDETAILS = descriptor.Descriptor(
  name='DocumentDetails',
  full_name='DocumentDetails',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='appDetails', full_name='DocumentDetails.appDetails', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='albumDetails', full_name='DocumentDetails.albumDetails', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='artistDetails', full_name='DocumentDetails.artistDetails', index=2,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='songDetails', full_name='DocumentDetails.songDetails', index=3,
      number=4, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='bookDetails', full_name='DocumentDetails.bookDetails', index=4,
      number=5, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='videoDetails', full_name='DocumentDetails.videoDetails', index=5,
      number=6, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='subscriptionDetails', full_name='DocumentDetails.subscriptionDetails', index=6,
      number=7, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='magazineDetails', full_name='DocumentDetails.magazineDetails', index=7,
      number=8, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='tvShowDetails', full_name='DocumentDetails.tvShowDetails', index=8,
      number=9, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='tvSeasonDetails', full_name='DocumentDetails.tvSeasonDetails', index=9,
      number=10, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='tvEpisodeDetails', full_name='DocumentDetails.tvEpisodeDetails', index=10,
      number=11, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=12424,
  serialized_end=12878,
)


_FILEMETADATA = descriptor.Descriptor(
  name='FileMetadata',
  full_name='FileMetadata',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='fileType', full_name='FileMetadata.fileType', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='versionCode', full_name='FileMetadata.versionCode', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='size', full_name='FileMetadata.size', index=2,
      number=3, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=12880,
  serialized_end=12947,
)


_MAGAZINEDETAILS = descriptor.Descriptor(
  name='MagazineDetails',
  full_name='MagazineDetails',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='parentDetailsUrl', full_name='MagazineDetails.parentDetailsUrl', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='deviceAvailabilityDescriptionHtml', full_name='MagazineDetails.deviceAvailabilityDescriptionHtml', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='psvDescription', full_name='MagazineDetails.psvDescription', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='deliveryFrequencyDescription', full_name='MagazineDetails.deliveryFrequencyDescription', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=12950,
  serialized_end=13098,
)


_MUSICDETAILS = descriptor.Descriptor(
  name='MusicDetails',
  full_name='MusicDetails',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='censoring', full_name='MusicDetails.censoring', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='durationSec', full_name='MusicDetails.durationSec', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='originalReleaseDate', full_name='MusicDetails.originalReleaseDate', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='label', full_name='MusicDetails.label', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='artist', full_name='MusicDetails.artist', index=4,
      number=5, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='genre', full_name='MusicDetails.genre', index=5,
      number=6, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='releaseDate', full_name='MusicDetails.releaseDate', index=6,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='releaseType', full_name='MusicDetails.releaseType', index=7,
      number=8, type=5, cpp_type=1, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=13101,
  serialized_end=13288,
)


_SONGDETAILS = descriptor.Descriptor(
  name='SongDetails',
  full_name='SongDetails',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='name', full_name='SongDetails.name', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='details', full_name='SongDetails.details', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='albumName', full_name='SongDetails.albumName', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='trackNumber', full_name='SongDetails.trackNumber', index=3,
      number=4, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='previewUrl', full_name='SongDetails.previewUrl', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='displayArtist', full_name='SongDetails.displayArtist', index=5,
      number=6, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=13291,
  serialized_end=13449,
)


_SUBSCRIPTIONDETAILS = descriptor.Descriptor(
  name='SubscriptionDetails',
  full_name='SubscriptionDetails',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='subscriptionPeriod', full_name='SubscriptionDetails.subscriptionPeriod', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=13451,
  serialized_end=13500,
)


_TRAILER = descriptor.Descriptor(
  name='Trailer',
  full_name='Trailer',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='trailerId', full_name='Trailer.trailerId', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='title', full_name='Trailer.title', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='thumbnailUrl', full_name='Trailer.thumbnailUrl', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='watchUrl', full_name='Trailer.watchUrl', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='duration', full_name='Trailer.duration', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=13502,
  serialized_end=13603,
)


_TVEPISODEDETAILS = descriptor.Descriptor(
  name='TvEpisodeDetails',
  full_name='TvEpisodeDetails',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='parentDetailsUrl', full_name='TvEpisodeDetails.parentDetailsUrl', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='episodeIndex', full_name='TvEpisodeDetails.episodeIndex', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='releaseDate', full_name='TvEpisodeDetails.releaseDate', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=13605,
  serialized_end=13692,
)


_TVSEASONDETAILS = descriptor.Descriptor(
  name='TvSeasonDetails',
  full_name='TvSeasonDetails',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='parentDetailsUrl', full_name='TvSeasonDetails.parentDetailsUrl', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='seasonIndex', full_name='TvSeasonDetails.seasonIndex', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='releaseDate', full_name='TvSeasonDetails.releaseDate', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='broadcaster', full_name='TvSeasonDetails.broadcaster', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=13694,
  serialized_end=13800,
)


_TVSHOWDETAILS = descriptor.Descriptor(
  name='TvShowDetails',
  full_name='TvShowDetails',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='seasonCount', full_name='TvShowDetails.seasonCount', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='startYear', full_name='TvShowDetails.startYear', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='endYear', full_name='TvShowDetails.endYear', index=2,
      number=3, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='broadcaster', full_name='TvShowDetails.broadcaster', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=13802,
  serialized_end=13895,
)


_VIDEOCREDIT = descriptor.Descriptor(
  name='VideoCredit',
  full_name='VideoCredit',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='creditType', full_name='VideoCredit.creditType', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='credit', full_name='VideoCredit.credit', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='name', full_name='VideoCredit.name', index=2,
      number=3, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=13897,
  serialized_end=13960,
)


_VIDEODETAILS = descriptor.Descriptor(
  name='VideoDetails',
  full_name='VideoDetails',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='credit', full_name='VideoDetails.credit', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='duration', full_name='VideoDetails.duration', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='releaseDate', full_name='VideoDetails.releaseDate', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='contentRating', full_name='VideoDetails.contentRating', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='likes', full_name='VideoDetails.likes', index=4,
      number=5, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='dislikes', full_name='VideoDetails.dislikes', index=5,
      number=6, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='genre', full_name='VideoDetails.genre', index=6,
      number=7, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='trailer', full_name='VideoDetails.trailer', index=7,
      number=8, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='rentalTerm', full_name='VideoDetails.rentalTerm', index=8,
      number=9, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=13963,
  serialized_end=14182,
)


_VIDEORENTALTERM_TERM = descriptor.Descriptor(
  name='Term',
  full_name='VideoRentalTerm.Term',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='header', full_name='VideoRentalTerm.Term.header', index=0,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='body', full_name='VideoRentalTerm.Term.body', index=1,
      number=6, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=14309,
  serialized_end=14345,
)

_VIDEORENTALTERM = descriptor.Descriptor(
  name='VideoRentalTerm',
  full_name='VideoRentalTerm',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='offerType', full_name='VideoRentalTerm.offerType', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='offerAbbreviation', full_name='VideoRentalTerm.offerAbbreviation', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='rentalHeader', full_name='VideoRentalTerm.rentalHeader', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='term', full_name='VideoRentalTerm.term', index=3,
      number=4, type=10, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_VIDEORENTALTERM_TERM, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=14185,
  serialized_end=14345,
)


_BUCKET = descriptor.Descriptor(
  name='Bucket',
  full_name='Bucket',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='document', full_name='Bucket.document', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='multiCorpus', full_name='Bucket.multiCorpus', index=1,
      number=2, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='title', full_name='Bucket.title', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='iconUrl', full_name='Bucket.iconUrl', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='fullContentsUrl', full_name='Bucket.fullContentsUrl', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='relevance', full_name='Bucket.relevance', index=5,
      number=6, type=1, cpp_type=5, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='estimatedResults', full_name='Bucket.estimatedResults', index=6,
      number=7, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='analyticsCookie', full_name='Bucket.analyticsCookie', index=7,
      number=8, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='fullContentsListUrl', full_name='Bucket.fullContentsListUrl', index=8,
      number=9, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='nextPageUrl', full_name='Bucket.nextPageUrl', index=9,
      number=10, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='ordered', full_name='Bucket.ordered', index=10,
      number=11, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=14348,
  serialized_end=14597,
)


_LISTRESPONSE = descriptor.Descriptor(
  name='ListResponse',
  full_name='ListResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='bucket', full_name='ListResponse.bucket', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='doc', full_name='ListResponse.doc', index=1,
      number=2, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=14599,
  serialized_end=14659,
)


_DOCV1 = descriptor.Descriptor(
  name='DocV1',
  full_name='DocV1',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='finskyDoc', full_name='DocV1.finskyDoc', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='docid', full_name='DocV1.docid', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='detailsUrl', full_name='DocV1.detailsUrl', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='reviewsUrl', full_name='DocV1.reviewsUrl', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='relatedListUrl', full_name='DocV1.relatedListUrl', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='moreByListUrl', full_name='DocV1.moreByListUrl', index=5,
      number=6, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='shareUrl', full_name='DocV1.shareUrl', index=6,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='creator', full_name='DocV1.creator', index=7,
      number=8, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='details', full_name='DocV1.details', index=8,
      number=9, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='descriptionHtml', full_name='DocV1.descriptionHtml', index=9,
      number=10, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='relatedBrowseUrl', full_name='DocV1.relatedBrowseUrl', index=10,
      number=11, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='moreByBrowseUrl', full_name='DocV1.moreByBrowseUrl', index=11,
      number=12, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='relatedHeader', full_name='DocV1.relatedHeader', index=12,
      number=13, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='moreByHeader', full_name='DocV1.moreByHeader', index=13,
      number=14, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='title', full_name='DocV1.title', index=14,
      number=15, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='plusOneData', full_name='DocV1.plusOneData', index=15,
      number=16, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='warningMessage', full_name='DocV1.warningMessage', index=16,
      number=17, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=14662,
  serialized_end=15066,
)


_ANNOTATIONS = descriptor.Descriptor(
  name='Annotations',
  full_name='Annotations',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='sectionRelated', full_name='Annotations.sectionRelated', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='sectionMoreBy', full_name='Annotations.sectionMoreBy', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='plusOneData', full_name='Annotations.plusOneData', index=2,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='warning', full_name='Annotations.warning', index=3,
      number=4, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='sectionBodyOfWork', full_name='Annotations.sectionBodyOfWork', index=4,
      number=5, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='sectionCoreContent', full_name='Annotations.sectionCoreContent', index=5,
      number=6, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='template', full_name='Annotations.template', index=6,
      number=7, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='badgeForCreator', full_name='Annotations.badgeForCreator', index=7,
      number=8, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='badgeForDoc', full_name='Annotations.badgeForDoc', index=8,
      number=9, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='link', full_name='Annotations.link', index=9,
      number=10, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='sectionCrossSell', full_name='Annotations.sectionCrossSell', index=10,
      number=11, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='sectionRelatedDocType', full_name='Annotations.sectionRelatedDocType', index=11,
      number=12, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='promotedDoc', full_name='Annotations.promotedDoc', index=12,
      number=13, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='offerNote', full_name='Annotations.offerNote', index=13,
      number=14, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='subscription', full_name='Annotations.subscription', index=14,
      number=16, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='reason', full_name='Annotations.reason', index=15,
      number=17, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='privacyPolicyUrl', full_name='Annotations.privacyPolicyUrl', index=16,
      number=18, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=15069,
  serialized_end=15658,
)


_DOCV2 = descriptor.Descriptor(
  name='DocV2',
  full_name='DocV2',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='docid', full_name='DocV2.docid', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='backendDocid', full_name='DocV2.backendDocid', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='docType', full_name='DocV2.docType', index=2,
      number=3, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='backendId', full_name='DocV2.backendId', index=3,
      number=4, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='title', full_name='DocV2.title', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='creator', full_name='DocV2.creator', index=5,
      number=6, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='descriptionHtml', full_name='DocV2.descriptionHtml', index=6,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='offer', full_name='DocV2.offer', index=7,
      number=8, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='availability', full_name='DocV2.availability', index=8,
      number=9, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='image', full_name='DocV2.image', index=9,
      number=10, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='child', full_name='DocV2.child', index=10,
      number=11, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='containerMetadata', full_name='DocV2.containerMetadata', index=11,
      number=12, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='details', full_name='DocV2.details', index=12,
      number=13, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='aggregateRating', full_name='DocV2.aggregateRating', index=13,
      number=14, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='annotations', full_name='DocV2.annotations', index=14,
      number=15, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='detailsUrl', full_name='DocV2.detailsUrl', index=15,
      number=16, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='shareUrl', full_name='DocV2.shareUrl', index=16,
      number=17, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='reviewsUrl', full_name='DocV2.reviewsUrl', index=17,
      number=18, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='backendUrl', full_name='DocV2.backendUrl', index=18,
      number=19, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='purchaseDetailsUrl', full_name='DocV2.purchaseDetailsUrl', index=19,
      number=20, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='detailsReusable', full_name='DocV2.detailsReusable', index=20,
      number=21, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='subtitle', full_name='DocV2.subtitle', index=21,
      number=22, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=15661,
  serialized_end=16213,
)


_ENCRYPTEDSUBSCRIBERINFO = descriptor.Descriptor(
  name='EncryptedSubscriberInfo',
  full_name='EncryptedSubscriberInfo',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='data', full_name='EncryptedSubscriberInfo.data', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='encryptedKey', full_name='EncryptedSubscriberInfo.encryptedKey', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='signature', full_name='EncryptedSubscriberInfo.signature', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='initVector', full_name='EncryptedSubscriberInfo.initVector', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='googleKeyVersion', full_name='EncryptedSubscriberInfo.googleKeyVersion', index=4,
      number=5, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='carrierKeyVersion', full_name='EncryptedSubscriberInfo.carrierKeyVersion', index=5,
      number=6, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=16216,
  serialized_end=16369,
)


_AVAILABILITY_PERDEVICEAVAILABILITYRESTRICTION = descriptor.Descriptor(
  name='PerDeviceAvailabilityRestriction',
  full_name='Availability.PerDeviceAvailabilityRestriction',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='androidId', full_name='Availability.PerDeviceAvailabilityRestriction.androidId', index=0,
      number=10, type=6, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='deviceRestriction', full_name='Availability.PerDeviceAvailabilityRestriction.deviceRestriction', index=1,
      number=11, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='channelId', full_name='Availability.PerDeviceAvailabilityRestriction.channelId', index=2,
      number=12, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='filterInfo', full_name='Availability.PerDeviceAvailabilityRestriction.filterInfo', index=3,
      number=15, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=16675,
  serialized_end=16817,
)

_AVAILABILITY = descriptor.Descriptor(
  name='Availability',
  full_name='Availability',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='restriction', full_name='Availability.restriction', index=0,
      number=5, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='offerType', full_name='Availability.offerType', index=1,
      number=6, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='rule', full_name='Availability.rule', index=2,
      number=7, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='perdeviceavailabilityrestriction', full_name='Availability.perdeviceavailabilityrestriction', index=3,
      number=9, type=10, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='availableIfOwned', full_name='Availability.availableIfOwned', index=4,
      number=13, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='install', full_name='Availability.install', index=5,
      number=14, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='filterInfo', full_name='Availability.filterInfo', index=6,
      number=16, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='ownershipInfo', full_name='Availability.ownershipInfo', index=7,
      number=17, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_AVAILABILITY_PERDEVICEAVAILABILITYRESTRICTION, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=16372,
  serialized_end=16817,
)


_FILTEREVALUATIONINFO = descriptor.Descriptor(
  name='FilterEvaluationInfo',
  full_name='FilterEvaluationInfo',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='ruleEvaluation', full_name='FilterEvaluationInfo.ruleEvaluation', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=16819,
  serialized_end=16882,
)


_RULE = descriptor.Descriptor(
  name='Rule',
  full_name='Rule',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='negate', full_name='Rule.negate', index=0,
      number=1, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='operator', full_name='Rule.operator', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='key', full_name='Rule.key', index=2,
      number=3, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='stringArg', full_name='Rule.stringArg', index=3,
      number=4, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='longArg', full_name='Rule.longArg', index=4,
      number=5, type=3, cpp_type=2, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='doubleArg', full_name='Rule.doubleArg', index=5,
      number=6, type=1, cpp_type=5, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='subrule', full_name='Rule.subrule', index=6,
      number=7, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='responseCode', full_name='Rule.responseCode', index=7,
      number=8, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='comment', full_name='Rule.comment', index=8,
      number=9, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='stringArgHash', full_name='Rule.stringArgHash', index=9,
      number=10, type=6, cpp_type=4, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='constArg', full_name='Rule.constArg', index=10,
      number=11, type=5, cpp_type=1, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=16885,
  serialized_end=17097,
)


_RULEEVALUATION = descriptor.Descriptor(
  name='RuleEvaluation',
  full_name='RuleEvaluation',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='rule', full_name='RuleEvaluation.rule', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='actualStringValue', full_name='RuleEvaluation.actualStringValue', index=1,
      number=2, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='actualLongValue', full_name='RuleEvaluation.actualLongValue', index=2,
      number=3, type=3, cpp_type=2, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='actualBoolValue', full_name='RuleEvaluation.actualBoolValue', index=3,
      number=4, type=8, cpp_type=7, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='actualDoubleValue', full_name='RuleEvaluation.actualDoubleValue', index=4,
      number=5, type=1, cpp_type=5, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=17100,
  serialized_end=17241,
)


_LIBRARYAPPDETAILS = descriptor.Descriptor(
  name='LibraryAppDetails',
  full_name='LibraryAppDetails',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='certificateHash', full_name='LibraryAppDetails.certificateHash', index=0,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='refundTimeoutTimestampMsec', full_name='LibraryAppDetails.refundTimeoutTimestampMsec', index=1,
      number=3, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='postDeliveryRefundWindowMsec', full_name='LibraryAppDetails.postDeliveryRefundWindowMsec', index=2,
      number=4, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=17243,
  serialized_end=17361,
)


_LIBRARYMUTATION = descriptor.Descriptor(
  name='LibraryMutation',
  full_name='LibraryMutation',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='docid', full_name='LibraryMutation.docid', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='offerType', full_name='LibraryMutation.offerType', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='documentHash', full_name='LibraryMutation.documentHash', index=2,
      number=3, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='deleted', full_name='LibraryMutation.deleted', index=3,
      number=4, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='appDetails', full_name='LibraryMutation.appDetails', index=4,
      number=5, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='subscriptionDetails', full_name='LibraryMutation.subscriptionDetails', index=5,
      number=6, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=17364,
  serialized_end=17560,
)


_LIBRARYSUBSCRIPTIONDETAILS = descriptor.Descriptor(
  name='LibrarySubscriptionDetails',
  full_name='LibrarySubscriptionDetails',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='initiationTimestampMsec', full_name='LibrarySubscriptionDetails.initiationTimestampMsec', index=0,
      number=1, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='validUntilTimestampMsec', full_name='LibrarySubscriptionDetails.validUntilTimestampMsec', index=1,
      number=2, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='autoRenewing', full_name='LibrarySubscriptionDetails.autoRenewing', index=2,
      number=3, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='trialUntilTimestampMsec', full_name='LibrarySubscriptionDetails.trialUntilTimestampMsec', index=3,
      number=4, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=17563,
  serialized_end=17712,
)


_LIBRARYUPDATE = descriptor.Descriptor(
  name='LibraryUpdate',
  full_name='LibraryUpdate',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='status', full_name='LibraryUpdate.status', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='corpus', full_name='LibraryUpdate.corpus', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='serverToken', full_name='LibraryUpdate.serverToken', index=2,
      number=3, type=12, cpp_type=9, label=1,
      has_default_value=False, default_value="",
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='mutation', full_name='LibraryUpdate.mutation', index=3,
      number=4, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='hasMore', full_name='LibraryUpdate.hasMore', index=4,
      number=5, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='libraryId', full_name='LibraryUpdate.libraryId', index=5,
      number=6, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=17715,
  serialized_end=17855,
)


_CLIENTLIBRARYSTATE = descriptor.Descriptor(
  name='ClientLibraryState',
  full_name='ClientLibraryState',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='corpus', full_name='ClientLibraryState.corpus', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='serverToken', full_name='ClientLibraryState.serverToken', index=1,
      number=2, type=12, cpp_type=9, label=1,
      has_default_value=False, default_value="",
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='hashCodeSum', full_name='ClientLibraryState.hashCodeSum', index=2,
      number=3, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='librarySize', full_name='ClientLibraryState.librarySize', index=3,
      number=4, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=17857,
  serialized_end=17956,
)


_LIBRARYREPLICATIONREQUEST = descriptor.Descriptor(
  name='LibraryReplicationRequest',
  full_name='LibraryReplicationRequest',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='libraryState', full_name='LibraryReplicationRequest.libraryState', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=17958,
  serialized_end=18028,
)


_LIBRARYREPLICATIONRESPONSE = descriptor.Descriptor(
  name='LibraryReplicationResponse',
  full_name='LibraryReplicationResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='update', full_name='LibraryReplicationResponse.update', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=18030,
  serialized_end=18090,
)


_CLICKLOGEVENT = descriptor.Descriptor(
  name='ClickLogEvent',
  full_name='ClickLogEvent',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='eventTime', full_name='ClickLogEvent.eventTime', index=0,
      number=1, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='url', full_name='ClickLogEvent.url', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='listId', full_name='ClickLogEvent.listId', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='referrerUrl', full_name='ClickLogEvent.referrerUrl', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='referrerListId', full_name='ClickLogEvent.referrerListId', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=18092,
  serialized_end=18200,
)


_LOGREQUEST = descriptor.Descriptor(
  name='LogRequest',
  full_name='LogRequest',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='clickEvent', full_name='LogRequest.clickEvent', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=18202,
  serialized_end=18250,
)


_LOGRESPONSE = descriptor.Descriptor(
  name='LogResponse',
  full_name='LogResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=18252,
  serialized_end=18265,
)


_ANDROIDAPPNOTIFICATIONDATA = descriptor.Descriptor(
  name='AndroidAppNotificationData',
  full_name='AndroidAppNotificationData',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='versionCode', full_name='AndroidAppNotificationData.versionCode', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='assetId', full_name='AndroidAppNotificationData.assetId', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=18267,
  serialized_end=18333,
)


_INAPPNOTIFICATIONDATA = descriptor.Descriptor(
  name='InAppNotificationData',
  full_name='InAppNotificationData',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='checkoutOrderId', full_name='InAppNotificationData.checkoutOrderId', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='inAppNotificationId', full_name='InAppNotificationData.inAppNotificationId', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=18335,
  serialized_end=18412,
)


_LIBRARYDIRTYDATA = descriptor.Descriptor(
  name='LibraryDirtyData',
  full_name='LibraryDirtyData',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='backend', full_name='LibraryDirtyData.backend', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=18414,
  serialized_end=18449,
)


_NOTIFICATION = descriptor.Descriptor(
  name='Notification',
  full_name='Notification',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='notificationType', full_name='Notification.notificationType', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='timestamp', full_name='Notification.timestamp', index=1,
      number=3, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='docid', full_name='Notification.docid', index=2,
      number=4, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='docTitle', full_name='Notification.docTitle', index=3,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='userEmail', full_name='Notification.userEmail', index=4,
      number=6, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='appData', full_name='Notification.appData', index=5,
      number=7, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='appDeliveryData', full_name='Notification.appDeliveryData', index=6,
      number=8, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='purchaseRemovalData', full_name='Notification.purchaseRemovalData', index=7,
      number=9, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='userNotificationData', full_name='Notification.userNotificationData', index=8,
      number=10, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='inAppNotificationData', full_name='Notification.inAppNotificationData', index=9,
      number=11, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='purchaseDeclinedData', full_name='Notification.purchaseDeclinedData', index=10,
      number=12, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='notificationId', full_name='Notification.notificationId', index=11,
      number=13, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='libraryUpdate', full_name='Notification.libraryUpdate', index=12,
      number=14, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='libraryDirtyData', full_name='Notification.libraryDirtyData', index=13,
      number=15, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=18452,
  serialized_end=18987,
)


_PURCHASEDECLINEDDATA = descriptor.Descriptor(
  name='PurchaseDeclinedData',
  full_name='PurchaseDeclinedData',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='reason', full_name='PurchaseDeclinedData.reason', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='showNotification', full_name='PurchaseDeclinedData.showNotification', index=1,
      number=2, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=18989,
  serialized_end=19053,
)


_PURCHASEREMOVALDATA = descriptor.Descriptor(
  name='PurchaseRemovalData',
  full_name='PurchaseRemovalData',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='malicious', full_name='PurchaseRemovalData.malicious', index=0,
      number=1, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=19055,
  serialized_end=19095,
)


_USERNOTIFICATIONDATA = descriptor.Descriptor(
  name='UserNotificationData',
  full_name='UserNotificationData',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='notificationTitle', full_name='UserNotificationData.notificationTitle', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='notificationText', full_name='UserNotificationData.notificationText', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='tickerText', full_name='UserNotificationData.tickerText', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='dialogTitle', full_name='UserNotificationData.dialogTitle', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='dialogText', full_name='UserNotificationData.dialogText', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=19098,
  serialized_end=19234,
)


_PLUSONERESPONSE = descriptor.Descriptor(
  name='PlusOneResponse',
  full_name='PlusOneResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=19236,
  serialized_end=19253,
)


_RATESUGGESTEDCONTENTRESPONSE = descriptor.Descriptor(
  name='RateSuggestedContentResponse',
  full_name='RateSuggestedContentResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=19255,
  serialized_end=19285,
)


_AGGREGATERATING = descriptor.Descriptor(
  name='AggregateRating',
  full_name='AggregateRating',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='type', full_name='AggregateRating.type', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='starRating', full_name='AggregateRating.starRating', index=1,
      number=2, type=2, cpp_type=6, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='ratingsCount', full_name='AggregateRating.ratingsCount', index=2,
      number=3, type=4, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='oneStarRatings', full_name='AggregateRating.oneStarRatings', index=3,
      number=4, type=4, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='twoStarRatings', full_name='AggregateRating.twoStarRatings', index=4,
      number=5, type=4, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='threeStarRatings', full_name='AggregateRating.threeStarRatings', index=5,
      number=6, type=4, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='fourStarRatings', full_name='AggregateRating.fourStarRatings', index=6,
      number=7, type=4, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='fiveStarRatings', full_name='AggregateRating.fiveStarRatings', index=7,
      number=8, type=4, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='thumbsUpCount', full_name='AggregateRating.thumbsUpCount', index=8,
      number=9, type=4, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='thumbsDownCount', full_name='AggregateRating.thumbsDownCount', index=9,
      number=10, type=4, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='commentCount', full_name='AggregateRating.commentCount', index=10,
      number=11, type=4, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='bayesianMeanRating', full_name='AggregateRating.bayesianMeanRating', index=11,
      number=12, type=1, cpp_type=5, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=19288,
  serialized_end=19583,
)


_DIRECTPURCHASE = descriptor.Descriptor(
  name='DirectPurchase',
  full_name='DirectPurchase',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='detailsUrl', full_name='DirectPurchase.detailsUrl', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='purchaseDocid', full_name='DirectPurchase.purchaseDocid', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='parentDocid', full_name='DirectPurchase.parentDocid', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='offerType', full_name='DirectPurchase.offerType', index=3,
      number=4, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=19585,
  serialized_end=19684,
)


_RESOLVELINKRESPONSE = descriptor.Descriptor(
  name='ResolveLinkResponse',
  full_name='ResolveLinkResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='detailsUrl', full_name='ResolveLinkResponse.detailsUrl', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='browseUrl', full_name='ResolveLinkResponse.browseUrl', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='searchUrl', full_name='ResolveLinkResponse.searchUrl', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='directPurchase', full_name='ResolveLinkResponse.directPurchase', index=3,
      number=4, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='homeUrl', full_name='ResolveLinkResponse.homeUrl', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=19687,
  serialized_end=19824,
)


_PAYLOAD = descriptor.Descriptor(
  name='Payload',
  full_name='Payload',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='listResponse', full_name='Payload.listResponse', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='detailsResponse', full_name='Payload.detailsResponse', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='reviewResponse', full_name='Payload.reviewResponse', index=2,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='buyResponse', full_name='Payload.buyResponse', index=3,
      number=4, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='searchResponse', full_name='Payload.searchResponse', index=4,
      number=5, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='tocResponse', full_name='Payload.tocResponse', index=5,
      number=6, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='browseResponse', full_name='Payload.browseResponse', index=6,
      number=7, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='purchaseStatusResponse', full_name='Payload.purchaseStatusResponse', index=7,
      number=8, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='updateInstrumentResponse', full_name='Payload.updateInstrumentResponse', index=8,
      number=9, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='logResponse', full_name='Payload.logResponse', index=9,
      number=10, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='checkInstrumentResponse', full_name='Payload.checkInstrumentResponse', index=10,
      number=11, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='plusOneResponse', full_name='Payload.plusOneResponse', index=11,
      number=12, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='flagContentResponse', full_name='Payload.flagContentResponse', index=12,
      number=13, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='ackNotificationResponse', full_name='Payload.ackNotificationResponse', index=13,
      number=14, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='initiateAssociationResponse', full_name='Payload.initiateAssociationResponse', index=14,
      number=15, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='verifyAssociationResponse', full_name='Payload.verifyAssociationResponse', index=15,
      number=16, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='libraryReplicationResponse', full_name='Payload.libraryReplicationResponse', index=16,
      number=17, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='revokeResponse', full_name='Payload.revokeResponse', index=17,
      number=18, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='bulkDetailsResponse', full_name='Payload.bulkDetailsResponse', index=18,
      number=19, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='resolveLinkResponse', full_name='Payload.resolveLinkResponse', index=19,
      number=20, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='deliveryResponse', full_name='Payload.deliveryResponse', index=20,
      number=21, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='acceptTosResponse', full_name='Payload.acceptTosResponse', index=21,
      number=22, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='rateSuggestedContentResponse', full_name='Payload.rateSuggestedContentResponse', index=22,
      number=23, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='checkPromoOfferResponse', full_name='Payload.checkPromoOfferResponse', index=23,
      number=24, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=19827,
  serialized_end=21032,
)


_PREFETCH = descriptor.Descriptor(
  name='PreFetch',
  full_name='PreFetch',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='url', full_name='PreFetch.url', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='response', full_name='PreFetch.response', index=1,
      number=2, type=12, cpp_type=9, label=1,
      has_default_value=False, default_value="",
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='etag', full_name='PreFetch.etag', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='ttl', full_name='PreFetch.ttl', index=3,
      number=4, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='softTtl', full_name='PreFetch.softTtl', index=4,
      number=5, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=21034,
  serialized_end=21119,
)


_RESPONSEWRAPPER = descriptor.Descriptor(
  name='ResponseWrapper',
  full_name='ResponseWrapper',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='payload', full_name='ResponseWrapper.payload', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='commands', full_name='ResponseWrapper.commands', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='preFetch', full_name='ResponseWrapper.preFetch', index=2,
      number=3, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='notification', full_name='ResponseWrapper.notification', index=3,
      number=4, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=21122,
  serialized_end=21267,
)


_SERVERCOMMANDS = descriptor.Descriptor(
  name='ServerCommands',
  full_name='ServerCommands',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='clearCache', full_name='ServerCommands.clearCache', index=0,
      number=1, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='displayErrorMessage', full_name='ServerCommands.displayErrorMessage', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='logErrorStacktrace', full_name='ServerCommands.logErrorStacktrace', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=21269,
  serialized_end=21362,
)


_GETREVIEWSRESPONSE = descriptor.Descriptor(
  name='GetReviewsResponse',
  full_name='GetReviewsResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='review', full_name='GetReviewsResponse.review', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='matchingCount', full_name='GetReviewsResponse.matchingCount', index=1,
      number=2, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=21364,
  serialized_end=21432,
)


_REVIEW = descriptor.Descriptor(
  name='Review',
  full_name='Review',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='authorName', full_name='Review.authorName', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='url', full_name='Review.url', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='source', full_name='Review.source', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='documentVersion', full_name='Review.documentVersion', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='timestampMsec', full_name='Review.timestampMsec', index=4,
      number=5, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='starRating', full_name='Review.starRating', index=5,
      number=6, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='title', full_name='Review.title', index=6,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='comment', full_name='Review.comment', index=7,
      number=8, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='commentId', full_name='Review.commentId', index=8,
      number=9, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='deviceName', full_name='Review.deviceName', index=9,
      number=19, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='replyText', full_name='Review.replyText', index=10,
      number=29, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='replyTimestampMsec', full_name='Review.replyTimestampMsec', index=11,
      number=30, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=21435,
  serialized_end=21678,
)


_REVIEWRESPONSE = descriptor.Descriptor(
  name='ReviewResponse',
  full_name='ReviewResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='getResponse', full_name='ReviewResponse.getResponse', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='nextPageUrl', full_name='ReviewResponse.nextPageUrl', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=21680,
  serialized_end=21759,
)


_REVOKERESPONSE = descriptor.Descriptor(
  name='RevokeResponse',
  full_name='RevokeResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='libraryUpdate', full_name='RevokeResponse.libraryUpdate', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=21761,
  serialized_end=21816,
)


_RELATEDSEARCH = descriptor.Descriptor(
  name='RelatedSearch',
  full_name='RelatedSearch',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='searchUrl', full_name='RelatedSearch.searchUrl', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='header', full_name='RelatedSearch.header', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='backendId', full_name='RelatedSearch.backendId', index=2,
      number=3, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='docType', full_name='RelatedSearch.docType', index=3,
      number=4, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='current', full_name='RelatedSearch.current', index=4,
      number=5, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=21818,
  serialized_end=21921,
)


_SEARCHRESPONSE = descriptor.Descriptor(
  name='SearchResponse',
  full_name='SearchResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='originalQuery', full_name='SearchResponse.originalQuery', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='suggestedQuery', full_name='SearchResponse.suggestedQuery', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='aggregateQuery', full_name='SearchResponse.aggregateQuery', index=2,
      number=3, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='bucket', full_name='SearchResponse.bucket', index=3,
      number=4, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='doc', full_name='SearchResponse.doc', index=4,
      number=5, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='relatedSearch', full_name='SearchResponse.relatedSearch', index=5,
      number=6, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=21924,
  serialized_end=22096,
)


_CORPUSMETADATA = descriptor.Descriptor(
  name='CorpusMetadata',
  full_name='CorpusMetadata',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='backend', full_name='CorpusMetadata.backend', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='name', full_name='CorpusMetadata.name', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='landingUrl', full_name='CorpusMetadata.landingUrl', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='libraryName', full_name='CorpusMetadata.libraryName', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=22098,
  serialized_end=22186,
)


_EXPERIMENTS = descriptor.Descriptor(
  name='Experiments',
  full_name='Experiments',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='experimentId', full_name='Experiments.experimentId', index=0,
      number=1, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=22188,
  serialized_end=22223,
)


_TOCRESPONSE = descriptor.Descriptor(
  name='TocResponse',
  full_name='TocResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='corpus', full_name='TocResponse.corpus', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='tosVersionDeprecated', full_name='TocResponse.tosVersionDeprecated', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='tosContent', full_name='TocResponse.tosContent', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='homeUrl', full_name='TocResponse.homeUrl', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='experiments', full_name='TocResponse.experiments', index=4,
      number=5, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='tosCheckboxTextMarketingEmails', full_name='TocResponse.tosCheckboxTextMarketingEmails', index=5,
      number=6, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='tosToken', full_name='TocResponse.tosToken', index=6,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='userSettings', full_name='TocResponse.userSettings', index=7,
      number=8, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='iconOverrideUrl', full_name='TocResponse.iconOverrideUrl', index=8,
      number=9, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=22226,
  serialized_end=22494,
)


_USERSETTINGS = descriptor.Descriptor(
  name='UserSettings',
  full_name='UserSettings',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='tosCheckboxMarketingEmailsOptedIn', full_name='UserSettings.tosCheckboxMarketingEmailsOptedIn', index=0,
      number=1, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=22496,
  serialized_end=22553,
)


_ACCEPTTOSRESPONSE = descriptor.Descriptor(
  name='AcceptTosResponse',
  full_name='AcceptTosResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=22555,
  serialized_end=22574,
)


_ACKNOTIFICATIONSREQUESTPROTO = descriptor.Descriptor(
  name='AckNotificationsRequestProto',
  full_name='AckNotificationsRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='notificationId', full_name='AckNotificationsRequestProto.notificationId', index=0,
      number=1, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='signatureHash', full_name='AckNotificationsRequestProto.signatureHash', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='nackNotificationId', full_name='AckNotificationsRequestProto.nackNotificationId', index=2,
      number=3, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=22576,
  serialized_end=22702,
)


_ACKNOTIFICATIONSRESPONSEPROTO = descriptor.Descriptor(
  name='AckNotificationsResponseProto',
  full_name='AckNotificationsResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=22704,
  serialized_end=22735,
)


_ADDRESSPROTO = descriptor.Descriptor(
  name='AddressProto',
  full_name='AddressProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='address1', full_name='AddressProto.address1', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='address2', full_name='AddressProto.address2', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='city', full_name='AddressProto.city', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='state', full_name='AddressProto.state', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='postalCode', full_name='AddressProto.postalCode', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='country', full_name='AddressProto.country', index=5,
      number=6, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='name', full_name='AddressProto.name', index=6,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='type', full_name='AddressProto.type', index=7,
      number=8, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='phone', full_name='AddressProto.phone', index=8,
      number=9, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=22738,
  serialized_end=22897,
)


_APPDATAPROTO = descriptor.Descriptor(
  name='AppDataProto',
  full_name='AppDataProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='key', full_name='AppDataProto.key', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='value', full_name='AppDataProto.value', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=22899,
  serialized_end=22941,
)


_APPSUGGESTIONPROTO = descriptor.Descriptor(
  name='AppSuggestionProto',
  full_name='AppSuggestionProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='assetInfo', full_name='AppSuggestionProto.assetInfo', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=22943,
  serialized_end=23003,
)


_ASSETIDENTIFIERPROTO = descriptor.Descriptor(
  name='AssetIdentifierProto',
  full_name='AssetIdentifierProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='packageName', full_name='AssetIdentifierProto.packageName', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='versionCode', full_name='AssetIdentifierProto.versionCode', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='assetId', full_name='AssetIdentifierProto.assetId', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=23005,
  serialized_end=23086,
)


_ASSETSREQUESTPROTO = descriptor.Descriptor(
  name='AssetsRequestProto',
  full_name='AssetsRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='assetType', full_name='AssetsRequestProto.assetType', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='query', full_name='AssetsRequestProto.query', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='categoryId', full_name='AssetsRequestProto.categoryId', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='assetId', full_name='AssetsRequestProto.assetId', index=3,
      number=4, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='retrieveVendingHistory', full_name='AssetsRequestProto.retrieveVendingHistory', index=4,
      number=5, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='retrieveExtendedInfo', full_name='AssetsRequestProto.retrieveExtendedInfo', index=5,
      number=6, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='sortOrder', full_name='AssetsRequestProto.sortOrder', index=6,
      number=7, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='startIndex', full_name='AssetsRequestProto.startIndex', index=7,
      number=8, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='numEntries', full_name='AssetsRequestProto.numEntries', index=8,
      number=9, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='viewFilter', full_name='AssetsRequestProto.viewFilter', index=9,
      number=10, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='rankingType', full_name='AssetsRequestProto.rankingType', index=10,
      number=11, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='retrieveCarrierChannel', full_name='AssetsRequestProto.retrieveCarrierChannel', index=11,
      number=12, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='pendingDownloadAssetId', full_name='AssetsRequestProto.pendingDownloadAssetId', index=12,
      number=13, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='reconstructVendingHistory', full_name='AssetsRequestProto.reconstructVendingHistory', index=13,
      number=14, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='unfilteredResults', full_name='AssetsRequestProto.unfilteredResults', index=14,
      number=15, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='badgeId', full_name='AssetsRequestProto.badgeId', index=15,
      number=16, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=23089,
  serialized_end=23485,
)


_ASSETSRESPONSEPROTO = descriptor.Descriptor(
  name='AssetsResponseProto',
  full_name='AssetsResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='asset', full_name='AssetsResponseProto.asset', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='numTotalEntries', full_name='AssetsResponseProto.numTotalEntries', index=1,
      number=2, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='correctedQuery', full_name='AssetsResponseProto.correctedQuery', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='altAsset', full_name='AssetsResponseProto.altAsset', index=3,
      number=4, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='numCorrectedEntries', full_name='AssetsResponseProto.numCorrectedEntries', index=4,
      number=5, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='header', full_name='AssetsResponseProto.header', index=5,
      number=6, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='listType', full_name='AssetsResponseProto.listType', index=6,
      number=7, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=23488,
  serialized_end=23696,
)


_BILLINGEVENTREQUESTPROTO = descriptor.Descriptor(
  name='BillingEventRequestProto',
  full_name='BillingEventRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='eventType', full_name='BillingEventRequestProto.eventType', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='billingParametersId', full_name='BillingEventRequestProto.billingParametersId', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='resultSuccess', full_name='BillingEventRequestProto.resultSuccess', index=2,
      number=3, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='clientMessage', full_name='BillingEventRequestProto.clientMessage', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='carrierInstrument', full_name='BillingEventRequestProto.carrierInstrument', index=4,
      number=5, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=23699,
  serialized_end=23886,
)


_BILLINGEVENTRESPONSEPROTO = descriptor.Descriptor(
  name='BillingEventResponseProto',
  full_name='BillingEventResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=23888,
  serialized_end=23915,
)


_BILLINGPARAMETERPROTO = descriptor.Descriptor(
  name='BillingParameterProto',
  full_name='BillingParameterProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='id', full_name='BillingParameterProto.id', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='name', full_name='BillingParameterProto.name', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='mncMcc', full_name='BillingParameterProto.mncMcc', index=2,
      number=3, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='backendUrl', full_name='BillingParameterProto.backendUrl', index=3,
      number=4, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='iconId', full_name='BillingParameterProto.iconId', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='billingInstrumentType', full_name='BillingParameterProto.billingInstrumentType', index=5,
      number=6, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='applicationId', full_name='BillingParameterProto.applicationId', index=6,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='tosUrl', full_name='BillingParameterProto.tosUrl', index=7,
      number=8, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='instrumentTosRequired', full_name='BillingParameterProto.instrumentTosRequired', index=8,
      number=9, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='apiVersion', full_name='BillingParameterProto.apiVersion', index=9,
      number=10, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='perTransactionCredentialsRequired', full_name='BillingParameterProto.perTransactionCredentialsRequired', index=10,
      number=11, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='sendSubscriberIdWithCarrierBillingRequests', full_name='BillingParameterProto.sendSubscriberIdWithCarrierBillingRequests', index=11,
      number=12, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='deviceAssociationMethod', full_name='BillingParameterProto.deviceAssociationMethod', index=12,
      number=13, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='userTokenRequestMessage', full_name='BillingParameterProto.userTokenRequestMessage', index=13,
      number=14, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='userTokenRequestAddress', full_name='BillingParameterProto.userTokenRequestAddress', index=14,
      number=15, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='passphraseRequired', full_name='BillingParameterProto.passphraseRequired', index=15,
      number=16, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=23918,
  serialized_end=24362,
)


_CARRIERBILLINGCREDENTIALSPROTO = descriptor.Descriptor(
  name='CarrierBillingCredentialsProto',
  full_name='CarrierBillingCredentialsProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='credentials', full_name='CarrierBillingCredentialsProto.credentials', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='credentialsTimeout', full_name='CarrierBillingCredentialsProto.credentialsTimeout', index=1,
      number=2, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=24364,
  serialized_end=24445,
)


_CATEGORYPROTO = descriptor.Descriptor(
  name='CategoryProto',
  full_name='CategoryProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='assetType', full_name='CategoryProto.assetType', index=0,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='categoryId', full_name='CategoryProto.categoryId', index=1,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='categoryDisplay', full_name='CategoryProto.categoryDisplay', index=2,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='categorySubtitle', full_name='CategoryProto.categorySubtitle', index=3,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='promotedAssetsNew', full_name='CategoryProto.promotedAssetsNew', index=4,
      number=6, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='promotedAssetsHome', full_name='CategoryProto.promotedAssetsHome', index=5,
      number=7, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='subCategories', full_name='CategoryProto.subCategories', index=6,
      number=8, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='promotedAssetsPaid', full_name='CategoryProto.promotedAssetsPaid', index=7,
      number=9, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='promotedAssetsFree', full_name='CategoryProto.promotedAssetsFree', index=8,
      number=10, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=24448,
  serialized_end=24703,
)


_CHECKFORNOTIFICATIONSREQUESTPROTO = descriptor.Descriptor(
  name='CheckForNotificationsRequestProto',
  full_name='CheckForNotificationsRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='alarmDuration', full_name='CheckForNotificationsRequestProto.alarmDuration', index=0,
      number=1, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=24705,
  serialized_end=24763,
)


_CHECKFORNOTIFICATIONSRESPONSEPROTO = descriptor.Descriptor(
  name='CheckForNotificationsResponseProto',
  full_name='CheckForNotificationsResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=24765,
  serialized_end=24801,
)


_CHECKLICENSEREQUESTPROTO = descriptor.Descriptor(
  name='CheckLicenseRequestProto',
  full_name='CheckLicenseRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='packageName', full_name='CheckLicenseRequestProto.packageName', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='versionCode', full_name='CheckLicenseRequestProto.versionCode', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='nonce', full_name='CheckLicenseRequestProto.nonce', index=2,
      number=3, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=24803,
  serialized_end=24886,
)


_CHECKLICENSERESPONSEPROTO = descriptor.Descriptor(
  name='CheckLicenseResponseProto',
  full_name='CheckLicenseResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='responseCode', full_name='CheckLicenseResponseProto.responseCode', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='signedData', full_name='CheckLicenseResponseProto.signedData', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='signature', full_name='CheckLicenseResponseProto.signature', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=24888,
  serialized_end=24976,
)


_COMMENTSREQUESTPROTO = descriptor.Descriptor(
  name='CommentsRequestProto',
  full_name='CommentsRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='assetId', full_name='CommentsRequestProto.assetId', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='startIndex', full_name='CommentsRequestProto.startIndex', index=1,
      number=2, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='numEntries', full_name='CommentsRequestProto.numEntries', index=2,
      number=3, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='shouldReturnSelfComment', full_name='CommentsRequestProto.shouldReturnSelfComment', index=3,
      number=4, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='assetReferrer', full_name='CommentsRequestProto.assetReferrer', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=24979,
  serialized_end=25114,
)


_COMMENTSRESPONSEPROTO = descriptor.Descriptor(
  name='CommentsResponseProto',
  full_name='CommentsResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='comment', full_name='CommentsResponseProto.comment', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='numTotalEntries', full_name='CommentsResponseProto.numTotalEntries', index=1,
      number=2, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='selfComment', full_name='CommentsResponseProto.selfComment', index=2,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=25117,
  serialized_end=25249,
)


_CONTENTSYNCREQUESTPROTO_ASSETINSTALLSTATE = descriptor.Descriptor(
  name='AssetInstallState',
  full_name='ContentSyncRequestProto.AssetInstallState',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='assetId', full_name='ContentSyncRequestProto.AssetInstallState.assetId', index=0,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='assetState', full_name='ContentSyncRequestProto.AssetInstallState.assetState', index=1,
      number=4, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='installTime', full_name='ContentSyncRequestProto.AssetInstallState.installTime', index=2,
      number=5, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='uninstallTime', full_name='ContentSyncRequestProto.AssetInstallState.uninstallTime', index=3,
      number=6, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='packageName', full_name='ContentSyncRequestProto.AssetInstallState.packageName', index=4,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='versionCode', full_name='ContentSyncRequestProto.AssetInstallState.versionCode', index=5,
      number=8, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='assetReferrer', full_name='ContentSyncRequestProto.AssetInstallState.assetReferrer', index=6,
      number=9, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=25455,
  serialized_end=25620,
)

_CONTENTSYNCREQUESTPROTO_SYSTEMAPP = descriptor.Descriptor(
  name='SystemApp',
  full_name='ContentSyncRequestProto.SystemApp',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='packageName', full_name='ContentSyncRequestProto.SystemApp.packageName', index=0,
      number=11, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='versionCode', full_name='ContentSyncRequestProto.SystemApp.versionCode', index=1,
      number=12, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='certificateHash', full_name='ContentSyncRequestProto.SystemApp.certificateHash', index=2,
      number=13, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=25622,
  serialized_end=25700,
)

_CONTENTSYNCREQUESTPROTO = descriptor.Descriptor(
  name='ContentSyncRequestProto',
  full_name='ContentSyncRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='incremental', full_name='ContentSyncRequestProto.incremental', index=0,
      number=1, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='assetinstallstate', full_name='ContentSyncRequestProto.assetinstallstate', index=1,
      number=2, type=10, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='systemapp', full_name='ContentSyncRequestProto.systemapp', index=2,
      number=10, type=10, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='sideloadedAppCount', full_name='ContentSyncRequestProto.sideloadedAppCount', index=3,
      number=14, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_CONTENTSYNCREQUESTPROTO_ASSETINSTALLSTATE, _CONTENTSYNCREQUESTPROTO_SYSTEMAPP, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=25252,
  serialized_end=25700,
)


_CONTENTSYNCRESPONSEPROTO = descriptor.Descriptor(
  name='ContentSyncResponseProto',
  full_name='ContentSyncResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='numUpdatesAvailable', full_name='ContentSyncResponseProto.numUpdatesAvailable', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=25702,
  serialized_end=25757,
)


_DATAMESSAGEPROTO = descriptor.Descriptor(
  name='DataMessageProto',
  full_name='DataMessageProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='category', full_name='DataMessageProto.category', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='appData', full_name='DataMessageProto.appData', index=1,
      number=3, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=25759,
  serialized_end=25827,
)


_DOWNLOADINFOPROTO = descriptor.Descriptor(
  name='DownloadInfoProto',
  full_name='DownloadInfoProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='apkSize', full_name='DownloadInfoProto.apkSize', index=0,
      number=1, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='additionalFile', full_name='DownloadInfoProto.additionalFile', index=1,
      number=2, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=25829,
  serialized_end=25909,
)


_EXTERNALASSETPROTO_PURCHASEINFORMATION = descriptor.Descriptor(
  name='PurchaseInformation',
  full_name='ExternalAssetProto.PurchaseInformation',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='purchaseTime', full_name='ExternalAssetProto.PurchaseInformation.purchaseTime', index=0,
      number=10, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='refundTimeoutTime', full_name='ExternalAssetProto.PurchaseInformation.refundTimeoutTime', index=1,
      number=11, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='refundStartPolicy', full_name='ExternalAssetProto.PurchaseInformation.refundStartPolicy', index=2,
      number=45, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='refundWindowDuration', full_name='ExternalAssetProto.PurchaseInformation.refundWindowDuration', index=3,
      number=46, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=26450,
  serialized_end=26577,
)

_EXTERNALASSETPROTO_EXTENDEDINFO_PACKAGEDEPENDENCY = descriptor.Descriptor(
  name='PackageDependency',
  full_name='ExternalAssetProto.ExtendedInfo.PackageDependency',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='packageName', full_name='ExternalAssetProto.ExtendedInfo.PackageDependency.packageName', index=0,
      number=41, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='skipPermissions', full_name='ExternalAssetProto.ExtendedInfo.PackageDependency.skipPermissions', index=1,
      number=42, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=27229,
  serialized_end=27294,
)

_EXTERNALASSETPROTO_EXTENDEDINFO = descriptor.Descriptor(
  name='ExtendedInfo',
  full_name='ExternalAssetProto.ExtendedInfo',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='description', full_name='ExternalAssetProto.ExtendedInfo.description', index=0,
      number=13, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='downloadCount', full_name='ExternalAssetProto.ExtendedInfo.downloadCount', index=1,
      number=14, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='applicationPermissionId', full_name='ExternalAssetProto.ExtendedInfo.applicationPermissionId', index=2,
      number=15, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='requiredInstallationSize', full_name='ExternalAssetProto.ExtendedInfo.requiredInstallationSize', index=3,
      number=16, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='packageName', full_name='ExternalAssetProto.ExtendedInfo.packageName', index=4,
      number=17, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='category', full_name='ExternalAssetProto.ExtendedInfo.category', index=5,
      number=18, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='forwardLocked', full_name='ExternalAssetProto.ExtendedInfo.forwardLocked', index=6,
      number=19, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='contactEmail', full_name='ExternalAssetProto.ExtendedInfo.contactEmail', index=7,
      number=20, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='everInstalledByUser', full_name='ExternalAssetProto.ExtendedInfo.everInstalledByUser', index=8,
      number=21, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='downloadCountString', full_name='ExternalAssetProto.ExtendedInfo.downloadCountString', index=9,
      number=23, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='contactPhone', full_name='ExternalAssetProto.ExtendedInfo.contactPhone', index=10,
      number=26, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='contactWebsite', full_name='ExternalAssetProto.ExtendedInfo.contactWebsite', index=11,
      number=27, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='nextPurchaseRefundable', full_name='ExternalAssetProto.ExtendedInfo.nextPurchaseRefundable', index=12,
      number=28, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='numScreenshots', full_name='ExternalAssetProto.ExtendedInfo.numScreenshots', index=13,
      number=30, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='promotionalDescription', full_name='ExternalAssetProto.ExtendedInfo.promotionalDescription', index=14,
      number=31, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='serverAssetState', full_name='ExternalAssetProto.ExtendedInfo.serverAssetState', index=15,
      number=34, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='contentRatingLevel', full_name='ExternalAssetProto.ExtendedInfo.contentRatingLevel', index=16,
      number=36, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='contentRatingString', full_name='ExternalAssetProto.ExtendedInfo.contentRatingString', index=17,
      number=37, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='recentChanges', full_name='ExternalAssetProto.ExtendedInfo.recentChanges', index=18,
      number=38, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='packagedependency', full_name='ExternalAssetProto.ExtendedInfo.packagedependency', index=19,
      number=39, type=10, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='videoLink', full_name='ExternalAssetProto.ExtendedInfo.videoLink', index=20,
      number=43, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='downloadInfo', full_name='ExternalAssetProto.ExtendedInfo.downloadInfo', index=21,
      number=49, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_EXTERNALASSETPROTO_EXTENDEDINFO_PACKAGEDEPENDENCY, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=26580,
  serialized_end=27294,
)

_EXTERNALASSETPROTO = descriptor.Descriptor(
  name='ExternalAssetProto',
  full_name='ExternalAssetProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='id', full_name='ExternalAssetProto.id', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='title', full_name='ExternalAssetProto.title', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='assetType', full_name='ExternalAssetProto.assetType', index=2,
      number=3, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='owner', full_name='ExternalAssetProto.owner', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='version', full_name='ExternalAssetProto.version', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='price', full_name='ExternalAssetProto.price', index=5,
      number=6, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='averageRating', full_name='ExternalAssetProto.averageRating', index=6,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='numRatings', full_name='ExternalAssetProto.numRatings', index=7,
      number=8, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='purchaseinformation', full_name='ExternalAssetProto.purchaseinformation', index=8,
      number=9, type=10, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='extendedinfo', full_name='ExternalAssetProto.extendedinfo', index=9,
      number=12, type=10, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='ownerId', full_name='ExternalAssetProto.ownerId', index=10,
      number=22, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='packageName', full_name='ExternalAssetProto.packageName', index=11,
      number=24, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='versionCode', full_name='ExternalAssetProto.versionCode', index=12,
      number=25, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='bundledAsset', full_name='ExternalAssetProto.bundledAsset', index=13,
      number=29, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='priceCurrency', full_name='ExternalAssetProto.priceCurrency', index=14,
      number=32, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='priceMicros', full_name='ExternalAssetProto.priceMicros', index=15,
      number=33, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='filterReason', full_name='ExternalAssetProto.filterReason', index=16,
      number=35, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='actualSellerPrice', full_name='ExternalAssetProto.actualSellerPrice', index=17,
      number=40, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='appBadge', full_name='ExternalAssetProto.appBadge', index=18,
      number=47, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='ownerBadge', full_name='ExternalAssetProto.ownerBadge', index=19,
      number=48, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_EXTERNALASSETPROTO_PURCHASEINFORMATION, _EXTERNALASSETPROTO_EXTENDEDINFO, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=25912,
  serialized_end=27294,
)


_EXTERNALBADGEIMAGEPROTO = descriptor.Descriptor(
  name='ExternalBadgeImageProto',
  full_name='ExternalBadgeImageProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='usage', full_name='ExternalBadgeImageProto.usage', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='url', full_name='ExternalBadgeImageProto.url', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=27296,
  serialized_end=27349,
)


_EXTERNALBADGEPROTO = descriptor.Descriptor(
  name='ExternalBadgeProto',
  full_name='ExternalBadgeProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='localizedTitle', full_name='ExternalBadgeProto.localizedTitle', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='localizedDescription', full_name='ExternalBadgeProto.localizedDescription', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='badgeImage', full_name='ExternalBadgeProto.badgeImage', index=2,
      number=3, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='searchId', full_name='ExternalBadgeProto.searchId', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=27352,
  serialized_end=27490,
)


_EXTERNALCARRIERBILLINGINSTRUMENTPROTO = descriptor.Descriptor(
  name='ExternalCarrierBillingInstrumentProto',
  full_name='ExternalCarrierBillingInstrumentProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='instrumentKey', full_name='ExternalCarrierBillingInstrumentProto.instrumentKey', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='subscriberIdentifier', full_name='ExternalCarrierBillingInstrumentProto.subscriberIdentifier', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='accountType', full_name='ExternalCarrierBillingInstrumentProto.accountType', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='subscriberCurrency', full_name='ExternalCarrierBillingInstrumentProto.subscriberCurrency', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='transactionLimit', full_name='ExternalCarrierBillingInstrumentProto.transactionLimit', index=4,
      number=5, type=4, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='subscriberName', full_name='ExternalCarrierBillingInstrumentProto.subscriberName', index=5,
      number=6, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='address1', full_name='ExternalCarrierBillingInstrumentProto.address1', index=6,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='address2', full_name='ExternalCarrierBillingInstrumentProto.address2', index=7,
      number=8, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='city', full_name='ExternalCarrierBillingInstrumentProto.city', index=8,
      number=9, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='state', full_name='ExternalCarrierBillingInstrumentProto.state', index=9,
      number=10, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='postalCode', full_name='ExternalCarrierBillingInstrumentProto.postalCode', index=10,
      number=11, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='country', full_name='ExternalCarrierBillingInstrumentProto.country', index=11,
      number=12, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='encryptedSubscriberInfo', full_name='ExternalCarrierBillingInstrumentProto.encryptedSubscriberInfo', index=12,
      number=13, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=27493,
  serialized_end=27845,
)


_EXTERNALCOMMENTPROTO = descriptor.Descriptor(
  name='ExternalCommentProto',
  full_name='ExternalCommentProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='body', full_name='ExternalCommentProto.body', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='rating', full_name='ExternalCommentProto.rating', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='creatorName', full_name='ExternalCommentProto.creatorName', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='creationTime', full_name='ExternalCommentProto.creationTime', index=3,
      number=4, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='creatorId', full_name='ExternalCommentProto.creatorId', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=27847,
  serialized_end=27961,
)


_EXTERNALCREDITCARD = descriptor.Descriptor(
  name='ExternalCreditCard',
  full_name='ExternalCreditCard',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='type', full_name='ExternalCreditCard.type', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='lastDigits', full_name='ExternalCreditCard.lastDigits', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='expYear', full_name='ExternalCreditCard.expYear', index=2,
      number=3, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='expMonth', full_name='ExternalCreditCard.expMonth', index=3,
      number=4, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='personName', full_name='ExternalCreditCard.personName', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='countryCode', full_name='ExternalCreditCard.countryCode', index=5,
      number=6, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='postalCode', full_name='ExternalCreditCard.postalCode', index=6,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='makeDefault', full_name='ExternalCreditCard.makeDefault', index=7,
      number=8, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='address1', full_name='ExternalCreditCard.address1', index=8,
      number=9, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='address2', full_name='ExternalCreditCard.address2', index=9,
      number=10, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='city', full_name='ExternalCreditCard.city', index=10,
      number=11, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='state', full_name='ExternalCreditCard.state', index=11,
      number=12, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='phone', full_name='ExternalCreditCard.phone', index=12,
      number=13, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=27964,
  serialized_end=28215,
)


_EXTERNALPAYPALINSTRUMENTPROTO = descriptor.Descriptor(
  name='ExternalPaypalInstrumentProto',
  full_name='ExternalPaypalInstrumentProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='instrumentKey', full_name='ExternalPaypalInstrumentProto.instrumentKey', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='preapprovalKey', full_name='ExternalPaypalInstrumentProto.preapprovalKey', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='paypalEmail', full_name='ExternalPaypalInstrumentProto.paypalEmail', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='paypalAddress', full_name='ExternalPaypalInstrumentProto.paypalAddress', index=3,
      number=4, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='multiplePaypalInstrumentsSupported', full_name='ExternalPaypalInstrumentProto.multiplePaypalInstrumentsSupported', index=4,
      number=5, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=28218,
  serialized_end=28399,
)


_FILEMETADATAPROTO = descriptor.Descriptor(
  name='FileMetadataProto',
  full_name='FileMetadataProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='fileType', full_name='FileMetadataProto.fileType', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='versionCode', full_name='FileMetadataProto.versionCode', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='size', full_name='FileMetadataProto.size', index=2,
      number=3, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='downloadUrl', full_name='FileMetadataProto.downloadUrl', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=28401,
  serialized_end=28494,
)


_GETADDRESSSNIPPETREQUESTPROTO = descriptor.Descriptor(
  name='GetAddressSnippetRequestProto',
  full_name='GetAddressSnippetRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='encryptedSubscriberInfo', full_name='GetAddressSnippetRequestProto.encryptedSubscriberInfo', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=28496,
  serialized_end=28586,
)


_GETADDRESSSNIPPETRESPONSEPROTO = descriptor.Descriptor(
  name='GetAddressSnippetResponseProto',
  full_name='GetAddressSnippetResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='addressSnippet', full_name='GetAddressSnippetResponseProto.addressSnippet', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=28588,
  serialized_end=28644,
)


_GETASSETREQUESTPROTO = descriptor.Descriptor(
  name='GetAssetRequestProto',
  full_name='GetAssetRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='assetId', full_name='GetAssetRequestProto.assetId', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='directDownloadKey', full_name='GetAssetRequestProto.directDownloadKey', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=28646,
  serialized_end=28712,
)


_GETASSETRESPONSEPROTO_INSTALLASSET = descriptor.Descriptor(
  name='InstallAsset',
  full_name='GetAssetResponseProto.InstallAsset',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='assetId', full_name='GetAssetResponseProto.InstallAsset.assetId', index=0,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='assetName', full_name='GetAssetResponseProto.InstallAsset.assetName', index=1,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='assetType', full_name='GetAssetResponseProto.InstallAsset.assetType', index=2,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='assetPackage', full_name='GetAssetResponseProto.InstallAsset.assetPackage', index=3,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='blobUrl', full_name='GetAssetResponseProto.InstallAsset.blobUrl', index=4,
      number=6, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='assetSignature', full_name='GetAssetResponseProto.InstallAsset.assetSignature', index=5,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='assetSize', full_name='GetAssetResponseProto.InstallAsset.assetSize', index=6,
      number=8, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='refundTimeoutMillis', full_name='GetAssetResponseProto.InstallAsset.refundTimeoutMillis', index=7,
      number=9, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='forwardLocked', full_name='GetAssetResponseProto.InstallAsset.forwardLocked', index=8,
      number=10, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='secured', full_name='GetAssetResponseProto.InstallAsset.secured', index=9,
      number=11, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='versionCode', full_name='GetAssetResponseProto.InstallAsset.versionCode', index=10,
      number=12, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='downloadAuthCookieName', full_name='GetAssetResponseProto.InstallAsset.downloadAuthCookieName', index=11,
      number=13, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='downloadAuthCookieValue', full_name='GetAssetResponseProto.InstallAsset.downloadAuthCookieValue', index=12,
      number=14, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='postInstallRefundWindowMillis', full_name='GetAssetResponseProto.InstallAsset.postInstallRefundWindowMillis', index=13,
      number=16, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=28844,
  serialized_end=29189,
)

_GETASSETRESPONSEPROTO = descriptor.Descriptor(
  name='GetAssetResponseProto',
  full_name='GetAssetResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='installasset', full_name='GetAssetResponseProto.installasset', index=0,
      number=1, type=10, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='additionalFile', full_name='GetAssetResponseProto.additionalFile', index=1,
      number=15, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_GETASSETRESPONSEPROTO_INSTALLASSET, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=28715,
  serialized_end=29189,
)


_GETCARRIERINFOREQUESTPROTO = descriptor.Descriptor(
  name='GetCarrierInfoRequestProto',
  full_name='GetCarrierInfoRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=29191,
  serialized_end=29219,
)


_GETCARRIERINFORESPONSEPROTO = descriptor.Descriptor(
  name='GetCarrierInfoResponseProto',
  full_name='GetCarrierInfoResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='carrierChannelEnabled', full_name='GetCarrierInfoResponseProto.carrierChannelEnabled', index=0,
      number=1, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='carrierLogoIcon', full_name='GetCarrierInfoResponseProto.carrierLogoIcon', index=1,
      number=2, type=12, cpp_type=9, label=1,
      has_default_value=False, default_value="",
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='carrierBanner', full_name='GetCarrierInfoResponseProto.carrierBanner', index=2,
      number=3, type=12, cpp_type=9, label=1,
      has_default_value=False, default_value="",
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='carrierSubtitle', full_name='GetCarrierInfoResponseProto.carrierSubtitle', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='carrierTitle', full_name='GetCarrierInfoResponseProto.carrierTitle', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='carrierImageDensity', full_name='GetCarrierInfoResponseProto.carrierImageDensity', index=5,
      number=6, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=29222,
  serialized_end=29406,
)


_GETCATEGORIESREQUESTPROTO = descriptor.Descriptor(
  name='GetCategoriesRequestProto',
  full_name='GetCategoriesRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='prefetchPromoData', full_name='GetCategoriesRequestProto.prefetchPromoData', index=0,
      number=1, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=29408,
  serialized_end=29462,
)


_GETCATEGORIESRESPONSEPROTO = descriptor.Descriptor(
  name='GetCategoriesResponseProto',
  full_name='GetCategoriesResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='categories', full_name='GetCategoriesResponseProto.categories', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=29464,
  serialized_end=29528,
)


_GETIMAGEREQUESTPROTO = descriptor.Descriptor(
  name='GetImageRequestProto',
  full_name='GetImageRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='assetId', full_name='GetImageRequestProto.assetId', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='imageUsage', full_name='GetImageRequestProto.imageUsage', index=1,
      number=3, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='imageId', full_name='GetImageRequestProto.imageId', index=2,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='screenPropertyWidth', full_name='GetImageRequestProto.screenPropertyWidth', index=3,
      number=5, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='screenPropertyHeight', full_name='GetImageRequestProto.screenPropertyHeight', index=4,
      number=6, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='screenPropertyDensity', full_name='GetImageRequestProto.screenPropertyDensity', index=5,
      number=7, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='productType', full_name='GetImageRequestProto.productType', index=6,
      number=8, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=29531,
  serialized_end=29718,
)


_GETIMAGERESPONSEPROTO = descriptor.Descriptor(
  name='GetImageResponseProto',
  full_name='GetImageResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='imageData', full_name='GetImageResponseProto.imageData', index=0,
      number=1, type=12, cpp_type=9, label=1,
      has_default_value=False, default_value="",
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='imageDensity', full_name='GetImageResponseProto.imageDensity', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=29720,
  serialized_end=29784,
)


_GETMARKETMETADATAREQUESTPROTO = descriptor.Descriptor(
  name='GetMarketMetadataRequestProto',
  full_name='GetMarketMetadataRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='lastRequestTime', full_name='GetMarketMetadataRequestProto.lastRequestTime', index=0,
      number=1, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='deviceConfiguration', full_name='GetMarketMetadataRequestProto.deviceConfiguration', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='deviceRoaming', full_name='GetMarketMetadataRequestProto.deviceRoaming', index=2,
      number=3, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='marketSignatureHash', full_name='GetMarketMetadataRequestProto.marketSignatureHash', index=3,
      number=4, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='contentRating', full_name='GetMarketMetadataRequestProto.contentRating', index=4,
      number=5, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='deviceModelName', full_name='GetMarketMetadataRequestProto.deviceModelName', index=5,
      number=6, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='deviceManufacturerName', full_name='GetMarketMetadataRequestProto.deviceManufacturerName', index=6,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=29787,
  serialized_end=30031,
)


_GETMARKETMETADATARESPONSEPROTO = descriptor.Descriptor(
  name='GetMarketMetadataResponseProto',
  full_name='GetMarketMetadataResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='latestClientVersionCode', full_name='GetMarketMetadataResponseProto.latestClientVersionCode', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='latestClientUrl', full_name='GetMarketMetadataResponseProto.latestClientUrl', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='paidAppsEnabled', full_name='GetMarketMetadataResponseProto.paidAppsEnabled', index=2,
      number=3, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='billingParameter', full_name='GetMarketMetadataResponseProto.billingParameter', index=3,
      number=4, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='commentPostEnabled', full_name='GetMarketMetadataResponseProto.commentPostEnabled', index=4,
      number=5, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='billingEventsEnabled', full_name='GetMarketMetadataResponseProto.billingEventsEnabled', index=5,
      number=6, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='warningMessage', full_name='GetMarketMetadataResponseProto.warningMessage', index=6,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='inAppBillingEnabled', full_name='GetMarketMetadataResponseProto.inAppBillingEnabled', index=7,
      number=8, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='inAppBillingMaxApiVersion', full_name='GetMarketMetadataResponseProto.inAppBillingMaxApiVersion', index=8,
      number=9, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=30034,
  serialized_end=30345,
)


_GETSUBCATEGORIESREQUESTPROTO = descriptor.Descriptor(
  name='GetSubCategoriesRequestProto',
  full_name='GetSubCategoriesRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='assetType', full_name='GetSubCategoriesRequestProto.assetType', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=30347,
  serialized_end=30396,
)


_GETSUBCATEGORIESRESPONSEPROTO_SUBCATEGORY = descriptor.Descriptor(
  name='SubCategory',
  full_name='GetSubCategoriesResponseProto.SubCategory',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='subCategoryDisplay', full_name='GetSubCategoriesResponseProto.SubCategory.subCategoryDisplay', index=0,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='subCategoryId', full_name='GetSubCategoriesResponseProto.SubCategory.subCategoryId', index=1,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=30497,
  serialized_end=30561,
)

_GETSUBCATEGORIESRESPONSEPROTO = descriptor.Descriptor(
  name='GetSubCategoriesResponseProto',
  full_name='GetSubCategoriesResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='subcategory', full_name='GetSubCategoriesResponseProto.subcategory', index=0,
      number=1, type=10, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_GETSUBCATEGORIESRESPONSEPROTO_SUBCATEGORY, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=30399,
  serialized_end=30561,
)


_INAPPPURCHASEINFORMATIONREQUESTPROTO = descriptor.Descriptor(
  name='InAppPurchaseInformationRequestProto',
  full_name='InAppPurchaseInformationRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='signatureHash', full_name='InAppPurchaseInformationRequestProto.signatureHash', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='nonce', full_name='InAppPurchaseInformationRequestProto.nonce', index=1,
      number=2, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='notificationId', full_name='InAppPurchaseInformationRequestProto.notificationId', index=2,
      number=3, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='signatureAlgorithm', full_name='InAppPurchaseInformationRequestProto.signatureAlgorithm', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='billingApiVersion', full_name='InAppPurchaseInformationRequestProto.billingApiVersion', index=4,
      number=5, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=30564,
  serialized_end=30740,
)


_INAPPPURCHASEINFORMATIONRESPONSEPROTO = descriptor.Descriptor(
  name='InAppPurchaseInformationResponseProto',
  full_name='InAppPurchaseInformationResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='signedResponse', full_name='InAppPurchaseInformationResponseProto.signedResponse', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='statusBarNotification', full_name='InAppPurchaseInformationResponseProto.statusBarNotification', index=1,
      number=2, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='purchaseResult', full_name='InAppPurchaseInformationResponseProto.purchaseResult', index=2,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=30743,
  serialized_end=30930,
)


_INAPPRESTORETRANSACTIONSREQUESTPROTO = descriptor.Descriptor(
  name='InAppRestoreTransactionsRequestProto',
  full_name='InAppRestoreTransactionsRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='signatureHash', full_name='InAppRestoreTransactionsRequestProto.signatureHash', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='nonce', full_name='InAppRestoreTransactionsRequestProto.nonce', index=1,
      number=2, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='signatureAlgorithm', full_name='InAppRestoreTransactionsRequestProto.signatureAlgorithm', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='billingApiVersion', full_name='InAppRestoreTransactionsRequestProto.billingApiVersion', index=3,
      number=4, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=30933,
  serialized_end=31085,
)


_INAPPRESTORETRANSACTIONSRESPONSEPROTO = descriptor.Descriptor(
  name='InAppRestoreTransactionsResponseProto',
  full_name='InAppRestoreTransactionsResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='signedResponse', full_name='InAppRestoreTransactionsResponseProto.signedResponse', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='purchaseResult', full_name='InAppRestoreTransactionsResponseProto.purchaseResult', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=31087,
  serialized_end=31214,
)


_MODIFYCOMMENTREQUESTPROTO = descriptor.Descriptor(
  name='ModifyCommentRequestProto',
  full_name='ModifyCommentRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='assetId', full_name='ModifyCommentRequestProto.assetId', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='comment', full_name='ModifyCommentRequestProto.comment', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='deleteComment', full_name='ModifyCommentRequestProto.deleteComment', index=2,
      number=3, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='flagAsset', full_name='ModifyCommentRequestProto.flagAsset', index=3,
      number=4, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='flagType', full_name='ModifyCommentRequestProto.flagType', index=4,
      number=5, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='flagMessage', full_name='ModifyCommentRequestProto.flagMessage', index=5,
      number=6, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='nonFlagFlow', full_name='ModifyCommentRequestProto.nonFlagFlow', index=6,
      number=7, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=31217,
  serialized_end=31403,
)


_MODIFYCOMMENTRESPONSEPROTO = descriptor.Descriptor(
  name='ModifyCommentResponseProto',
  full_name='ModifyCommentResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=31405,
  serialized_end=31433,
)


_PAYPALCOUNTRYINFOPROTO = descriptor.Descriptor(
  name='PaypalCountryInfoProto',
  full_name='PaypalCountryInfoProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='birthDateRequired', full_name='PaypalCountryInfoProto.birthDateRequired', index=0,
      number=1, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='tosText', full_name='PaypalCountryInfoProto.tosText', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='billingAgreementText', full_name='PaypalCountryInfoProto.billingAgreementText', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='preTosText', full_name='PaypalCountryInfoProto.preTosText', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=31435,
  serialized_end=31553,
)


_PAYPALCREATEACCOUNTREQUESTPROTO = descriptor.Descriptor(
  name='PaypalCreateAccountRequestProto',
  full_name='PaypalCreateAccountRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='firstName', full_name='PaypalCreateAccountRequestProto.firstName', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='lastName', full_name='PaypalCreateAccountRequestProto.lastName', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='address', full_name='PaypalCreateAccountRequestProto.address', index=2,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='birthDate', full_name='PaypalCreateAccountRequestProto.birthDate', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=31555,
  serialized_end=31676,
)


_PAYPALCREATEACCOUNTRESPONSEPROTO = descriptor.Descriptor(
  name='PaypalCreateAccountResponseProto',
  full_name='PaypalCreateAccountResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='createAccountKey', full_name='PaypalCreateAccountResponseProto.createAccountKey', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=31678,
  serialized_end=31738,
)


_PAYPALCREDENTIALSPROTO = descriptor.Descriptor(
  name='PaypalCredentialsProto',
  full_name='PaypalCredentialsProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='preapprovalKey', full_name='PaypalCredentialsProto.preapprovalKey', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='paypalEmail', full_name='PaypalCredentialsProto.paypalEmail', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=31740,
  serialized_end=31809,
)


_PAYPALMASSAGEADDRESSREQUESTPROTO = descriptor.Descriptor(
  name='PaypalMassageAddressRequestProto',
  full_name='PaypalMassageAddressRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='address', full_name='PaypalMassageAddressRequestProto.address', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=31811,
  serialized_end=31877,
)


_PAYPALMASSAGEADDRESSRESPONSEPROTO = descriptor.Descriptor(
  name='PaypalMassageAddressResponseProto',
  full_name='PaypalMassageAddressResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='address', full_name='PaypalMassageAddressResponseProto.address', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=31879,
  serialized_end=31946,
)


_PAYPALPREAPPROVALCREDENTIALSREQUESTPROTO = descriptor.Descriptor(
  name='PaypalPreapprovalCredentialsRequestProto',
  full_name='PaypalPreapprovalCredentialsRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='gaiaAuthToken', full_name='PaypalPreapprovalCredentialsRequestProto.gaiaAuthToken', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='billingInstrumentId', full_name='PaypalPreapprovalCredentialsRequestProto.billingInstrumentId', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=31948,
  serialized_end=32042,
)


_PAYPALPREAPPROVALCREDENTIALSRESPONSEPROTO = descriptor.Descriptor(
  name='PaypalPreapprovalCredentialsResponseProto',
  full_name='PaypalPreapprovalCredentialsResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='resultCode', full_name='PaypalPreapprovalCredentialsResponseProto.resultCode', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='paypalAccountKey', full_name='PaypalPreapprovalCredentialsResponseProto.paypalAccountKey', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='paypalEmail', full_name='PaypalPreapprovalCredentialsResponseProto.paypalEmail', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=32044,
  serialized_end=32154,
)


_PAYPALPREAPPROVALDETAILSREQUESTPROTO = descriptor.Descriptor(
  name='PaypalPreapprovalDetailsRequestProto',
  full_name='PaypalPreapprovalDetailsRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='getAddress', full_name='PaypalPreapprovalDetailsRequestProto.getAddress', index=0,
      number=1, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='preapprovalKey', full_name='PaypalPreapprovalDetailsRequestProto.preapprovalKey', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=32156,
  serialized_end=32238,
)


_PAYPALPREAPPROVALDETAILSRESPONSEPROTO = descriptor.Descriptor(
  name='PaypalPreapprovalDetailsResponseProto',
  full_name='PaypalPreapprovalDetailsResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='paypalEmail', full_name='PaypalPreapprovalDetailsResponseProto.paypalEmail', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='address', full_name='PaypalPreapprovalDetailsResponseProto.address', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=32240,
  serialized_end=32332,
)


_PAYPALPREAPPROVALREQUESTPROTO = descriptor.Descriptor(
  name='PaypalPreapprovalRequestProto',
  full_name='PaypalPreapprovalRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=32334,
  serialized_end=32365,
)


_PAYPALPREAPPROVALRESPONSEPROTO = descriptor.Descriptor(
  name='PaypalPreapprovalResponseProto',
  full_name='PaypalPreapprovalResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='preapprovalKey', full_name='PaypalPreapprovalResponseProto.preapprovalKey', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=32367,
  serialized_end=32423,
)


_PENDINGNOTIFICATIONSPROTO = descriptor.Descriptor(
  name='PendingNotificationsProto',
  full_name='PendingNotificationsProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='notification', full_name='PendingNotificationsProto.notification', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='nextCheckMillis', full_name='PendingNotificationsProto.nextCheckMillis', index=1,
      number=2, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=32425,
  serialized_end=32518,
)


_PREFETCHEDBUNDLEPROTO = descriptor.Descriptor(
  name='PrefetchedBundleProto',
  full_name='PrefetchedBundleProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='request', full_name='PrefetchedBundleProto.request', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='response', full_name='PrefetchedBundleProto.response', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=32520,
  serialized_end=32621,
)


_PURCHASECARTINFOPROTO = descriptor.Descriptor(
  name='PurchaseCartInfoProto',
  full_name='PurchaseCartInfoProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='itemPrice', full_name='PurchaseCartInfoProto.itemPrice', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='taxInclusive', full_name='PurchaseCartInfoProto.taxInclusive', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='taxExclusive', full_name='PurchaseCartInfoProto.taxExclusive', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='total', full_name='PurchaseCartInfoProto.total', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='taxMessage', full_name='PurchaseCartInfoProto.taxMessage', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='footerMessage', full_name='PurchaseCartInfoProto.footerMessage', index=5,
      number=6, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='priceCurrency', full_name='PurchaseCartInfoProto.priceCurrency', index=6,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='priceMicros', full_name='PurchaseCartInfoProto.priceMicros', index=7,
      number=8, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=32624,
  serialized_end=32812,
)


_PURCHASEINFOPROTO_BILLINGINSTRUMENTS_BILLINGINSTRUMENT = descriptor.Descriptor(
  name='BillingInstrument',
  full_name='PurchaseInfoProto.BillingInstruments.BillingInstrument',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='id', full_name='PurchaseInfoProto.BillingInstruments.BillingInstrument.id', index=0,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='name', full_name='PurchaseInfoProto.BillingInstruments.BillingInstrument.name', index=1,
      number=6, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='isInvalid', full_name='PurchaseInfoProto.BillingInstruments.BillingInstrument.isInvalid', index=2,
      number=7, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='instrumentType', full_name='PurchaseInfoProto.BillingInstruments.BillingInstrument.instrumentType', index=3,
      number=11, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='instrumentStatus', full_name='PurchaseInfoProto.BillingInstruments.BillingInstrument.instrumentStatus', index=4,
      number=14, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=33232,
  serialized_end=33346,
)

_PURCHASEINFOPROTO_BILLINGINSTRUMENTS = descriptor.Descriptor(
  name='BillingInstruments',
  full_name='PurchaseInfoProto.BillingInstruments',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='billinginstrument', full_name='PurchaseInfoProto.BillingInstruments.billinginstrument', index=0,
      number=4, type=10, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='defaultBillingInstrumentId', full_name='PurchaseInfoProto.BillingInstruments.defaultBillingInstrumentId', index=1,
      number=8, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_PURCHASEINFOPROTO_BILLINGINSTRUMENTS_BILLINGINSTRUMENT, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=33090,
  serialized_end=33346,
)

_PURCHASEINFOPROTO = descriptor.Descriptor(
  name='PurchaseInfoProto',
  full_name='PurchaseInfoProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='transactionId', full_name='PurchaseInfoProto.transactionId', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='cartInfo', full_name='PurchaseInfoProto.cartInfo', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='billinginstruments', full_name='PurchaseInfoProto.billinginstruments', index=2,
      number=3, type=10, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='errorInputFields', full_name='PurchaseInfoProto.errorInputFields', index=3,
      number=9, type=5, cpp_type=1, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='refundPolicy', full_name='PurchaseInfoProto.refundPolicy', index=4,
      number=10, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='userCanAddGdd', full_name='PurchaseInfoProto.userCanAddGdd', index=5,
      number=12, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='eligibleInstrumentTypes', full_name='PurchaseInfoProto.eligibleInstrumentTypes', index=6,
      number=13, type=5, cpp_type=1, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='orderId', full_name='PurchaseInfoProto.orderId', index=7,
      number=15, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_PURCHASEINFOPROTO_BILLINGINSTRUMENTS, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=32815,
  serialized_end=33346,
)


_PURCHASEMETADATAREQUESTPROTO = descriptor.Descriptor(
  name='PurchaseMetadataRequestProto',
  full_name='PurchaseMetadataRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='deprecatedRetrieveBillingCountries', full_name='PurchaseMetadataRequestProto.deprecatedRetrieveBillingCountries', index=0,
      number=1, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='billingInstrumentType', full_name='PurchaseMetadataRequestProto.billingInstrumentType', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=33348,
  serialized_end=33453,
)


_PURCHASEMETADATARESPONSEPROTO_COUNTRIES_COUNTRY_INSTRUMENTADDRESSSPEC = descriptor.Descriptor(
  name='InstrumentAddressSpec',
  full_name='PurchaseMetadataResponseProto.Countries.Country.InstrumentAddressSpec',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='instrumentFamily', full_name='PurchaseMetadataResponseProto.Countries.Country.InstrumentAddressSpec.instrumentFamily', index=0,
      number=8, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='billingAddressSpec', full_name='PurchaseMetadataResponseProto.Countries.Country.InstrumentAddressSpec.billingAddressSpec', index=1,
      number=9, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=33877,
  serialized_end=33975,
)

_PURCHASEMETADATARESPONSEPROTO_COUNTRIES_COUNTRY = descriptor.Descriptor(
  name='Country',
  full_name='PurchaseMetadataResponseProto.Countries.Country',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='countryCode', full_name='PurchaseMetadataResponseProto.Countries.Country.countryCode', index=0,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='countryName', full_name='PurchaseMetadataResponseProto.Countries.Country.countryName', index=1,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='paypalCountryInfo', full_name='PurchaseMetadataResponseProto.Countries.Country.paypalCountryInfo', index=2,
      number=5, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='allowsReducedBillingAddress', full_name='PurchaseMetadataResponseProto.Countries.Country.allowsReducedBillingAddress', index=3,
      number=6, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='instrumentaddressspec', full_name='PurchaseMetadataResponseProto.Countries.Country.instrumentaddressspec', index=4,
      number=7, type=10, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_PURCHASEMETADATARESPONSEPROTO_COUNTRIES_COUNTRY_INSTRUMENTADDRESSSPEC, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=33632,
  serialized_end=33975,
)

_PURCHASEMETADATARESPONSEPROTO_COUNTRIES = descriptor.Descriptor(
  name='Countries',
  full_name='PurchaseMetadataResponseProto.Countries',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='country', full_name='PurchaseMetadataResponseProto.Countries.country', index=0,
      number=2, type=10, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_PURCHASEMETADATARESPONSEPROTO_COUNTRIES_COUNTRY, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=33551,
  serialized_end=33975,
)

_PURCHASEMETADATARESPONSEPROTO = descriptor.Descriptor(
  name='PurchaseMetadataResponseProto',
  full_name='PurchaseMetadataResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='countries', full_name='PurchaseMetadataResponseProto.countries', index=0,
      number=1, type=10, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_PURCHASEMETADATARESPONSEPROTO_COUNTRIES, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=33456,
  serialized_end=33975,
)


_PURCHASEORDERREQUESTPROTO = descriptor.Descriptor(
  name='PurchaseOrderRequestProto',
  full_name='PurchaseOrderRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='gaiaAuthToken', full_name='PurchaseOrderRequestProto.gaiaAuthToken', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='assetId', full_name='PurchaseOrderRequestProto.assetId', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='transactionId', full_name='PurchaseOrderRequestProto.transactionId', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='billingInstrumentId', full_name='PurchaseOrderRequestProto.billingInstrumentId', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='tosAccepted', full_name='PurchaseOrderRequestProto.tosAccepted', index=4,
      number=5, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='carrierBillingCredentials', full_name='PurchaseOrderRequestProto.carrierBillingCredentials', index=5,
      number=6, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='existingOrderId', full_name='PurchaseOrderRequestProto.existingOrderId', index=6,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='billingInstrumentType', full_name='PurchaseOrderRequestProto.billingInstrumentType', index=7,
      number=8, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='billingParametersId', full_name='PurchaseOrderRequestProto.billingParametersId', index=8,
      number=9, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='paypalCredentials', full_name='PurchaseOrderRequestProto.paypalCredentials', index=9,
      number=10, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='riskHeaderInfo', full_name='PurchaseOrderRequestProto.riskHeaderInfo', index=10,
      number=11, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='productType', full_name='PurchaseOrderRequestProto.productType', index=11,
      number=12, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='signatureHash', full_name='PurchaseOrderRequestProto.signatureHash', index=12,
      number=13, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='developerPayload', full_name='PurchaseOrderRequestProto.developerPayload', index=13,
      number=14, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=33978,
  serialized_end=34460,
)


_PURCHASEORDERRESPONSEPROTO = descriptor.Descriptor(
  name='PurchaseOrderResponseProto',
  full_name='PurchaseOrderResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='deprecatedResultCode', full_name='PurchaseOrderResponseProto.deprecatedResultCode', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='purchaseInfo', full_name='PurchaseOrderResponseProto.purchaseInfo', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='asset', full_name='PurchaseOrderResponseProto.asset', index=2,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='purchaseResult', full_name='PurchaseOrderResponseProto.purchaseResult', index=3,
      number=4, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=34463,
  serialized_end=34645,
)


_PURCHASEPOSTREQUESTPROTO_BILLINGINSTRUMENTINFO = descriptor.Descriptor(
  name='BillingInstrumentInfo',
  full_name='PurchasePostRequestProto.BillingInstrumentInfo',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='billingInstrumentId', full_name='PurchasePostRequestProto.BillingInstrumentInfo.billingInstrumentId', index=0,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='creditCard', full_name='PurchasePostRequestProto.BillingInstrumentInfo.creditCard', index=1,
      number=6, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='carrierInstrument', full_name='PurchasePostRequestProto.BillingInstrumentInfo.carrierInstrument', index=2,
      number=9, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='paypalInstrument', full_name='PurchasePostRequestProto.BillingInstrumentInfo.paypalInstrument', index=3,
      number=10, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=34960,
  serialized_end=35178,
)

_PURCHASEPOSTREQUESTPROTO = descriptor.Descriptor(
  name='PurchasePostRequestProto',
  full_name='PurchasePostRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='gaiaAuthToken', full_name='PurchasePostRequestProto.gaiaAuthToken', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='assetId', full_name='PurchasePostRequestProto.assetId', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='transactionId', full_name='PurchasePostRequestProto.transactionId', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='billinginstrumentinfo', full_name='PurchasePostRequestProto.billinginstrumentinfo', index=3,
      number=4, type=10, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='tosAccepted', full_name='PurchasePostRequestProto.tosAccepted', index=4,
      number=7, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='cbInstrumentKey', full_name='PurchasePostRequestProto.cbInstrumentKey', index=5,
      number=8, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='paypalAuthConfirmed', full_name='PurchasePostRequestProto.paypalAuthConfirmed', index=6,
      number=11, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='productType', full_name='PurchasePostRequestProto.productType', index=7,
      number=12, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='signatureHash', full_name='PurchasePostRequestProto.signatureHash', index=8,
      number=13, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_PURCHASEPOSTREQUESTPROTO_BILLINGINSTRUMENTINFO, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=34648,
  serialized_end=35178,
)


_PURCHASEPOSTRESPONSEPROTO = descriptor.Descriptor(
  name='PurchasePostResponseProto',
  full_name='PurchasePostResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='deprecatedResultCode', full_name='PurchasePostResponseProto.deprecatedResultCode', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='purchaseInfo', full_name='PurchasePostResponseProto.purchaseInfo', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='termsOfServiceUrl', full_name='PurchasePostResponseProto.termsOfServiceUrl', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='termsOfServiceText', full_name='PurchasePostResponseProto.termsOfServiceText', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='termsOfServiceName', full_name='PurchasePostResponseProto.termsOfServiceName', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='termsOfServiceCheckboxText', full_name='PurchasePostResponseProto.termsOfServiceCheckboxText', index=5,
      number=6, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='termsOfServiceHeaderText', full_name='PurchasePostResponseProto.termsOfServiceHeaderText', index=6,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='purchaseResult', full_name='PurchasePostResponseProto.purchaseResult', index=7,
      number=8, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=35181,
  serialized_end=35479,
)


_PURCHASEPRODUCTREQUESTPROTO = descriptor.Descriptor(
  name='PurchaseProductRequestProto',
  full_name='PurchaseProductRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='productType', full_name='PurchaseProductRequestProto.productType', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='productId', full_name='PurchaseProductRequestProto.productId', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='signatureHash', full_name='PurchaseProductRequestProto.signatureHash', index=2,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=35481,
  serialized_end=35594,
)


_PURCHASEPRODUCTRESPONSEPROTO = descriptor.Descriptor(
  name='PurchaseProductResponseProto',
  full_name='PurchaseProductResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='title', full_name='PurchaseProductResponseProto.title', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='itemTitle', full_name='PurchaseProductResponseProto.itemTitle', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='itemDescription', full_name='PurchaseProductResponseProto.itemDescription', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='merchantField', full_name='PurchaseProductResponseProto.merchantField', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=35596,
  serialized_end=35708,
)


_PURCHASERESULTPROTO = descriptor.Descriptor(
  name='PurchaseResultProto',
  full_name='PurchaseResultProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='resultCode', full_name='PurchaseResultProto.resultCode', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='resultCodeMessage', full_name='PurchaseResultProto.resultCodeMessage', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=35710,
  serialized_end=35778,
)


_QUERYSUGGESTIONPROTO = descriptor.Descriptor(
  name='QuerySuggestionProto',
  full_name='QuerySuggestionProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='query', full_name='QuerySuggestionProto.query', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='estimatedNumResults', full_name='QuerySuggestionProto.estimatedNumResults', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='queryWeight', full_name='QuerySuggestionProto.queryWeight', index=2,
      number=3, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=35780,
  serialized_end=35867,
)


_QUERYSUGGESTIONREQUESTPROTO = descriptor.Descriptor(
  name='QuerySuggestionRequestProto',
  full_name='QuerySuggestionRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='query', full_name='QuerySuggestionRequestProto.query', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='requestType', full_name='QuerySuggestionRequestProto.requestType', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=35869,
  serialized_end=35934,
)


_QUERYSUGGESTIONRESPONSEPROTO_SUGGESTION = descriptor.Descriptor(
  name='Suggestion',
  full_name='QuerySuggestionResponseProto.Suggestion',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='appSuggestion', full_name='QuerySuggestionResponseProto.Suggestion.appSuggestion', index=0,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='querySuggestion', full_name='QuerySuggestionResponseProto.Suggestion.querySuggestion', index=1,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=36105,
  serialized_end=36209,
)

_QUERYSUGGESTIONRESPONSEPROTO = descriptor.Descriptor(
  name='QuerySuggestionResponseProto',
  full_name='QuerySuggestionResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='suggestion', full_name='QuerySuggestionResponseProto.suggestion', index=0,
      number=1, type=10, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='estimatedNumAppSuggestions', full_name='QuerySuggestionResponseProto.estimatedNumAppSuggestions', index=1,
      number=4, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='estimatedNumQuerySuggestions', full_name='QuerySuggestionResponseProto.estimatedNumQuerySuggestions', index=2,
      number=5, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_QUERYSUGGESTIONRESPONSEPROTO_SUGGESTION, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=35937,
  serialized_end=36209,
)


_RATECOMMENTREQUESTPROTO = descriptor.Descriptor(
  name='RateCommentRequestProto',
  full_name='RateCommentRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='assetId', full_name='RateCommentRequestProto.assetId', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='creatorId', full_name='RateCommentRequestProto.creatorId', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='commentRating', full_name='RateCommentRequestProto.commentRating', index=2,
      number=3, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=36211,
  serialized_end=36295,
)


_RATECOMMENTRESPONSEPROTO = descriptor.Descriptor(
  name='RateCommentResponseProto',
  full_name='RateCommentResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=36297,
  serialized_end=36323,
)


_RECONSTRUCTDATABASEREQUESTPROTO = descriptor.Descriptor(
  name='ReconstructDatabaseRequestProto',
  full_name='ReconstructDatabaseRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='retrieveFullHistory', full_name='ReconstructDatabaseRequestProto.retrieveFullHistory', index=0,
      number=1, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=36325,
  serialized_end=36387,
)


_RECONSTRUCTDATABASERESPONSEPROTO = descriptor.Descriptor(
  name='ReconstructDatabaseResponseProto',
  full_name='ReconstructDatabaseResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='asset', full_name='ReconstructDatabaseResponseProto.asset', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=36389,
  serialized_end=36461,
)


_REFUNDREQUESTPROTO = descriptor.Descriptor(
  name='RefundRequestProto',
  full_name='RefundRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='assetId', full_name='RefundRequestProto.assetId', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=36463,
  serialized_end=36500,
)


_REFUNDRESPONSEPROTO = descriptor.Descriptor(
  name='RefundResponseProto',
  full_name='RefundResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='result', full_name='RefundResponseProto.result', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='asset', full_name='RefundResponseProto.asset', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='resultDetail', full_name='RefundResponseProto.resultDetail', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=36502,
  serialized_end=36597,
)


_REMOVEASSETREQUESTPROTO = descriptor.Descriptor(
  name='RemoveAssetRequestProto',
  full_name='RemoveAssetRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='assetId', full_name='RemoveAssetRequestProto.assetId', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=36599,
  serialized_end=36641,
)


_REQUESTPROPERTIESPROTO = descriptor.Descriptor(
  name='RequestPropertiesProto',
  full_name='RequestPropertiesProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='userAuthToken', full_name='RequestPropertiesProto.userAuthToken', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='userAuthTokenSecure', full_name='RequestPropertiesProto.userAuthTokenSecure', index=1,
      number=2, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='softwareVersion', full_name='RequestPropertiesProto.softwareVersion', index=2,
      number=3, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='aid', full_name='RequestPropertiesProto.aid', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='productNameAndVersion', full_name='RequestPropertiesProto.productNameAndVersion', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='userLanguage', full_name='RequestPropertiesProto.userLanguage', index=5,
      number=6, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='userCountry', full_name='RequestPropertiesProto.userCountry', index=6,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='operatorName', full_name='RequestPropertiesProto.operatorName', index=7,
      number=8, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='simOperatorName', full_name='RequestPropertiesProto.simOperatorName', index=8,
      number=9, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='operatorNumericName', full_name='RequestPropertiesProto.operatorNumericName', index=9,
      number=10, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='simOperatorNumericName', full_name='RequestPropertiesProto.simOperatorNumericName', index=10,
      number=11, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='clientId', full_name='RequestPropertiesProto.clientId', index=11,
      number=12, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='loggingId', full_name='RequestPropertiesProto.loggingId', index=12,
      number=13, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=36644,
  serialized_end=36977,
)


_REQUESTPROTO_REQUEST = descriptor.Descriptor(
  name='Request',
  full_name='RequestProto.Request',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='requestSpecificProperties', full_name='RequestProto.Request.requestSpecificProperties', index=0,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='assetRequest', full_name='RequestProto.Request.assetRequest', index=1,
      number=4, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='commentsRequest', full_name='RequestProto.Request.commentsRequest', index=2,
      number=5, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='modifyCommentRequest', full_name='RequestProto.Request.modifyCommentRequest', index=3,
      number=6, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='purchasePostRequest', full_name='RequestProto.Request.purchasePostRequest', index=4,
      number=7, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='purchaseOrderRequest', full_name='RequestProto.Request.purchaseOrderRequest', index=5,
      number=8, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='contentSyncRequest', full_name='RequestProto.Request.contentSyncRequest', index=6,
      number=9, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='getAssetRequest', full_name='RequestProto.Request.getAssetRequest', index=7,
      number=10, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='getImageRequest', full_name='RequestProto.Request.getImageRequest', index=8,
      number=11, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='refundRequest', full_name='RequestProto.Request.refundRequest', index=9,
      number=12, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='purchaseMetadataRequest', full_name='RequestProto.Request.purchaseMetadataRequest', index=10,
      number=13, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='subCategoriesRequest', full_name='RequestProto.Request.subCategoriesRequest', index=11,
      number=14, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='uninstallReasonRequest', full_name='RequestProto.Request.uninstallReasonRequest', index=12,
      number=16, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='rateCommentRequest', full_name='RequestProto.Request.rateCommentRequest', index=13,
      number=17, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='checkLicenseRequest', full_name='RequestProto.Request.checkLicenseRequest', index=14,
      number=18, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='getMarketMetadataRequest', full_name='RequestProto.Request.getMarketMetadataRequest', index=15,
      number=19, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='getCategoriesRequest', full_name='RequestProto.Request.getCategoriesRequest', index=16,
      number=21, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='getCarrierInfoRequest', full_name='RequestProto.Request.getCarrierInfoRequest', index=17,
      number=22, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='removeAssetRequest', full_name='RequestProto.Request.removeAssetRequest', index=18,
      number=23, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='restoreApplicationsRequest', full_name='RequestProto.Request.restoreApplicationsRequest', index=19,
      number=24, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='querySuggestionRequest', full_name='RequestProto.Request.querySuggestionRequest', index=20,
      number=25, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='billingEventRequest', full_name='RequestProto.Request.billingEventRequest', index=21,
      number=26, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='paypalPreapprovalRequest', full_name='RequestProto.Request.paypalPreapprovalRequest', index=22,
      number=27, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='paypalPreapprovalDetailsRequest', full_name='RequestProto.Request.paypalPreapprovalDetailsRequest', index=23,
      number=28, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='paypalCreateAccountRequest', full_name='RequestProto.Request.paypalCreateAccountRequest', index=24,
      number=29, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='paypalPreapprovalCredentialsRequest', full_name='RequestProto.Request.paypalPreapprovalCredentialsRequest', index=25,
      number=30, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='inAppRestoreTransactionsRequest', full_name='RequestProto.Request.inAppRestoreTransactionsRequest', index=26,
      number=31, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='inAppPurchaseInformationRequest', full_name='RequestProto.Request.inAppPurchaseInformationRequest', index=27,
      number=32, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='checkForNotificationsRequest', full_name='RequestProto.Request.checkForNotificationsRequest', index=28,
      number=33, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='ackNotificationsRequest', full_name='RequestProto.Request.ackNotificationsRequest', index=29,
      number=34, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='purchaseProductRequest', full_name='RequestProto.Request.purchaseProductRequest', index=30,
      number=35, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='reconstructDatabaseRequest', full_name='RequestProto.Request.reconstructDatabaseRequest', index=31,
      number=36, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='paypalMassageAddressRequest', full_name='RequestProto.Request.paypalMassageAddressRequest', index=32,
      number=37, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='getAddressSnippetRequest', full_name='RequestProto.Request.getAddressSnippetRequest', index=33,
      number=38, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=37089,
  serialized_end=39218,
)

_REQUESTPROTO = descriptor.Descriptor(
  name='RequestProto',
  full_name='RequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='requestProperties', full_name='RequestProto.requestProperties', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='request', full_name='RequestProto.request', index=1,
      number=2, type=10, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_REQUESTPROTO_REQUEST, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=36980,
  serialized_end=39218,
)


_REQUESTSPECIFICPROPERTIESPROTO = descriptor.Descriptor(
  name='RequestSpecificPropertiesProto',
  full_name='RequestSpecificPropertiesProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='ifNoneMatch', full_name='RequestSpecificPropertiesProto.ifNoneMatch', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=39220,
  serialized_end=39273,
)


_RESPONSEPROPERTIESPROTO = descriptor.Descriptor(
  name='ResponsePropertiesProto',
  full_name='ResponsePropertiesProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='result', full_name='ResponsePropertiesProto.result', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='maxAge', full_name='ResponsePropertiesProto.maxAge', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='etag', full_name='ResponsePropertiesProto.etag', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='serverVersion', full_name='ResponsePropertiesProto.serverVersion', index=3,
      number=4, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='maxAgeConsumable', full_name='ResponsePropertiesProto.maxAgeConsumable', index=4,
      number=6, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='errorMessage', full_name='ResponsePropertiesProto.errorMessage', index=5,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='errorInputField', full_name='ResponsePropertiesProto.errorInputField', index=6,
      number=8, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=39276,
  serialized_end=39466,
)


_RESPONSEPROTO_RESPONSE = descriptor.Descriptor(
  name='Response',
  full_name='ResponseProto.Response',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='responseProperties', full_name='ResponseProto.Response.responseProperties', index=0,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='assetsResponse', full_name='ResponseProto.Response.assetsResponse', index=1,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='commentsResponse', full_name='ResponseProto.Response.commentsResponse', index=2,
      number=4, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='modifyCommentResponse', full_name='ResponseProto.Response.modifyCommentResponse', index=3,
      number=5, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='purchasePostResponse', full_name='ResponseProto.Response.purchasePostResponse', index=4,
      number=6, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='purchaseOrderResponse', full_name='ResponseProto.Response.purchaseOrderResponse', index=5,
      number=7, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='contentSyncResponse', full_name='ResponseProto.Response.contentSyncResponse', index=6,
      number=8, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='getAssetResponse', full_name='ResponseProto.Response.getAssetResponse', index=7,
      number=9, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='getImageResponse', full_name='ResponseProto.Response.getImageResponse', index=8,
      number=10, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='refundResponse', full_name='ResponseProto.Response.refundResponse', index=9,
      number=11, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='purchaseMetadataResponse', full_name='ResponseProto.Response.purchaseMetadataResponse', index=10,
      number=12, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='subCategoriesResponse', full_name='ResponseProto.Response.subCategoriesResponse', index=11,
      number=13, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='uninstallReasonResponse', full_name='ResponseProto.Response.uninstallReasonResponse', index=12,
      number=15, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='rateCommentResponse', full_name='ResponseProto.Response.rateCommentResponse', index=13,
      number=16, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='checkLicenseResponse', full_name='ResponseProto.Response.checkLicenseResponse', index=14,
      number=17, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='getMarketMetadataResponse', full_name='ResponseProto.Response.getMarketMetadataResponse', index=15,
      number=18, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='prefetchedBundle', full_name='ResponseProto.Response.prefetchedBundle', index=16,
      number=19, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='getCategoriesResponse', full_name='ResponseProto.Response.getCategoriesResponse', index=17,
      number=20, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='getCarrierInfoResponse', full_name='ResponseProto.Response.getCarrierInfoResponse', index=18,
      number=21, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='restoreApplicationResponse', full_name='ResponseProto.Response.restoreApplicationResponse', index=19,
      number=23, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='querySuggestionResponse', full_name='ResponseProto.Response.querySuggestionResponse', index=20,
      number=24, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='billingEventResponse', full_name='ResponseProto.Response.billingEventResponse', index=21,
      number=25, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='paypalPreapprovalResponse', full_name='ResponseProto.Response.paypalPreapprovalResponse', index=22,
      number=26, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='paypalPreapprovalDetailsResponse', full_name='ResponseProto.Response.paypalPreapprovalDetailsResponse', index=23,
      number=27, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='paypalCreateAccountResponse', full_name='ResponseProto.Response.paypalCreateAccountResponse', index=24,
      number=28, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='paypalPreapprovalCredentialsResponse', full_name='ResponseProto.Response.paypalPreapprovalCredentialsResponse', index=25,
      number=29, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='inAppRestoreTransactionsResponse', full_name='ResponseProto.Response.inAppRestoreTransactionsResponse', index=26,
      number=30, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='inAppPurchaseInformationResponse', full_name='ResponseProto.Response.inAppPurchaseInformationResponse', index=27,
      number=31, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='checkForNotificationsResponse', full_name='ResponseProto.Response.checkForNotificationsResponse', index=28,
      number=32, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='ackNotificationsResponse', full_name='ResponseProto.Response.ackNotificationsResponse', index=29,
      number=33, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='purchaseProductResponse', full_name='ResponseProto.Response.purchaseProductResponse', index=30,
      number=34, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='reconstructDatabaseResponse', full_name='ResponseProto.Response.reconstructDatabaseResponse', index=31,
      number=35, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='paypalMassageAddressResponse', full_name='ResponseProto.Response.paypalMassageAddressResponse', index=32,
      number=36, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='getAddressSnippetResponse', full_name='ResponseProto.Response.getAddressSnippetResponse', index=33,
      number=37, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=39588,
  serialized_end=41764,
)

_RESPONSEPROTO = descriptor.Descriptor(
  name='ResponseProto',
  full_name='ResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='response', full_name='ResponseProto.response', index=0,
      number=1, type=10, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='pendingNotifications', full_name='ResponseProto.pendingNotifications', index=1,
      number=38, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_RESPONSEPROTO_RESPONSE, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=39469,
  serialized_end=41764,
)


_RESTOREAPPLICATIONSREQUESTPROTO = descriptor.Descriptor(
  name='RestoreApplicationsRequestProto',
  full_name='RestoreApplicationsRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='backupAndroidId', full_name='RestoreApplicationsRequestProto.backupAndroidId', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='tosVersion', full_name='RestoreApplicationsRequestProto.tosVersion', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='deviceConfiguration', full_name='RestoreApplicationsRequestProto.deviceConfiguration', index=2,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=41767,
  serialized_end=41901,
)


_RESTOREAPPLICATIONSRESPONSEPROTO = descriptor.Descriptor(
  name='RestoreApplicationsResponseProto',
  full_name='RestoreApplicationsResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='asset', full_name='RestoreApplicationsResponseProto.asset', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=41903,
  serialized_end=41976,
)


_RISKHEADERINFOPROTO = descriptor.Descriptor(
  name='RiskHeaderInfoProto',
  full_name='RiskHeaderInfoProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='hashedDeviceInfo', full_name='RiskHeaderInfoProto.hashedDeviceInfo', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=41978,
  serialized_end=42025,
)


_SIGNATUREHASHPROTO = descriptor.Descriptor(
  name='SignatureHashProto',
  full_name='SignatureHashProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='packageName', full_name='SignatureHashProto.packageName', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='versionCode', full_name='SignatureHashProto.versionCode', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='hash', full_name='SignatureHashProto.hash', index=2,
      number=3, type=12, cpp_type=9, label=1,
      has_default_value=False, default_value="",
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=42027,
  serialized_end=42103,
)


_SIGNEDDATAPROTO = descriptor.Descriptor(
  name='SignedDataProto',
  full_name='SignedDataProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='signedData', full_name='SignedDataProto.signedData', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='signature', full_name='SignedDataProto.signature', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=42105,
  serialized_end=42161,
)


_SINGLEREQUESTPROTO = descriptor.Descriptor(
  name='SingleRequestProto',
  full_name='SingleRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='requestSpecificProperties', full_name='SingleRequestProto.requestSpecificProperties', index=0,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='assetRequest', full_name='SingleRequestProto.assetRequest', index=1,
      number=4, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='commentsRequest', full_name='SingleRequestProto.commentsRequest', index=2,
      number=5, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='modifyCommentRequest', full_name='SingleRequestProto.modifyCommentRequest', index=3,
      number=6, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='purchasePostRequest', full_name='SingleRequestProto.purchasePostRequest', index=4,
      number=7, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='purchaseOrderRequest', full_name='SingleRequestProto.purchaseOrderRequest', index=5,
      number=8, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='contentSyncRequest', full_name='SingleRequestProto.contentSyncRequest', index=6,
      number=9, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='getAssetRequest', full_name='SingleRequestProto.getAssetRequest', index=7,
      number=10, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='getImageRequest', full_name='SingleRequestProto.getImageRequest', index=8,
      number=11, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='refundRequest', full_name='SingleRequestProto.refundRequest', index=9,
      number=12, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='purchaseMetadataRequest', full_name='SingleRequestProto.purchaseMetadataRequest', index=10,
      number=13, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='subCategoriesRequest', full_name='SingleRequestProto.subCategoriesRequest', index=11,
      number=14, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='uninstallReasonRequest', full_name='SingleRequestProto.uninstallReasonRequest', index=12,
      number=16, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='rateCommentRequest', full_name='SingleRequestProto.rateCommentRequest', index=13,
      number=17, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='checkLicenseRequest', full_name='SingleRequestProto.checkLicenseRequest', index=14,
      number=18, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='getMarketMetadataRequest', full_name='SingleRequestProto.getMarketMetadataRequest', index=15,
      number=19, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='getCategoriesRequest', full_name='SingleRequestProto.getCategoriesRequest', index=16,
      number=21, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='getCarrierInfoRequest', full_name='SingleRequestProto.getCarrierInfoRequest', index=17,
      number=22, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='removeAssetRequest', full_name='SingleRequestProto.removeAssetRequest', index=18,
      number=23, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='restoreApplicationsRequest', full_name='SingleRequestProto.restoreApplicationsRequest', index=19,
      number=24, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='querySuggestionRequest', full_name='SingleRequestProto.querySuggestionRequest', index=20,
      number=25, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='billingEventRequest', full_name='SingleRequestProto.billingEventRequest', index=21,
      number=26, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='paypalPreapprovalRequest', full_name='SingleRequestProto.paypalPreapprovalRequest', index=22,
      number=27, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='paypalPreapprovalDetailsRequest', full_name='SingleRequestProto.paypalPreapprovalDetailsRequest', index=23,
      number=28, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='paypalCreateAccountRequest', full_name='SingleRequestProto.paypalCreateAccountRequest', index=24,
      number=29, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='paypalPreapprovalCredentialsRequest', full_name='SingleRequestProto.paypalPreapprovalCredentialsRequest', index=25,
      number=30, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='inAppRestoreTransactionsRequest', full_name='SingleRequestProto.inAppRestoreTransactionsRequest', index=26,
      number=31, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='getInAppPurchaseInformationRequest', full_name='SingleRequestProto.getInAppPurchaseInformationRequest', index=27,
      number=32, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='checkForNotificationsRequest', full_name='SingleRequestProto.checkForNotificationsRequest', index=28,
      number=33, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='ackNotificationsRequest', full_name='SingleRequestProto.ackNotificationsRequest', index=29,
      number=34, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='purchaseProductRequest', full_name='SingleRequestProto.purchaseProductRequest', index=30,
      number=35, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='reconstructDatabaseRequest', full_name='SingleRequestProto.reconstructDatabaseRequest', index=31,
      number=36, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='paypalMassageAddressRequest', full_name='SingleRequestProto.paypalMassageAddressRequest', index=32,
      number=37, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='getAddressSnippetRequest', full_name='SingleRequestProto.getAddressSnippetRequest', index=33,
      number=38, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=42164,
  serialized_end=44307,
)


_SINGLERESPONSEPROTO = descriptor.Descriptor(
  name='SingleResponseProto',
  full_name='SingleResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='responseProperties', full_name='SingleResponseProto.responseProperties', index=0,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='assetsResponse', full_name='SingleResponseProto.assetsResponse', index=1,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='commentsResponse', full_name='SingleResponseProto.commentsResponse', index=2,
      number=4, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='modifyCommentResponse', full_name='SingleResponseProto.modifyCommentResponse', index=3,
      number=5, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='purchasePostResponse', full_name='SingleResponseProto.purchasePostResponse', index=4,
      number=6, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='purchaseOrderResponse', full_name='SingleResponseProto.purchaseOrderResponse', index=5,
      number=7, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='contentSyncResponse', full_name='SingleResponseProto.contentSyncResponse', index=6,
      number=8, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='getAssetResponse', full_name='SingleResponseProto.getAssetResponse', index=7,
      number=9, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='getImageResponse', full_name='SingleResponseProto.getImageResponse', index=8,
      number=10, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='refundResponse', full_name='SingleResponseProto.refundResponse', index=9,
      number=11, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='purchaseMetadataResponse', full_name='SingleResponseProto.purchaseMetadataResponse', index=10,
      number=12, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='subCategoriesResponse', full_name='SingleResponseProto.subCategoriesResponse', index=11,
      number=13, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='uninstallReasonResponse', full_name='SingleResponseProto.uninstallReasonResponse', index=12,
      number=15, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='rateCommentResponse', full_name='SingleResponseProto.rateCommentResponse', index=13,
      number=16, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='checkLicenseResponse', full_name='SingleResponseProto.checkLicenseResponse', index=14,
      number=17, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='getMarketMetadataResponse', full_name='SingleResponseProto.getMarketMetadataResponse', index=15,
      number=18, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='getCategoriesResponse', full_name='SingleResponseProto.getCategoriesResponse', index=16,
      number=20, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='getCarrierInfoResponse', full_name='SingleResponseProto.getCarrierInfoResponse', index=17,
      number=21, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='restoreApplicationResponse', full_name='SingleResponseProto.restoreApplicationResponse', index=18,
      number=23, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='querySuggestionResponse', full_name='SingleResponseProto.querySuggestionResponse', index=19,
      number=24, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='billingEventResponse', full_name='SingleResponseProto.billingEventResponse', index=20,
      number=25, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='paypalPreapprovalResponse', full_name='SingleResponseProto.paypalPreapprovalResponse', index=21,
      number=26, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='paypalPreapprovalDetailsResponse', full_name='SingleResponseProto.paypalPreapprovalDetailsResponse', index=22,
      number=27, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='paypalCreateAccountResponse', full_name='SingleResponseProto.paypalCreateAccountResponse', index=23,
      number=28, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='paypalPreapprovalCredentialsResponse', full_name='SingleResponseProto.paypalPreapprovalCredentialsResponse', index=24,
      number=29, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='inAppRestoreTransactionsResponse', full_name='SingleResponseProto.inAppRestoreTransactionsResponse', index=25,
      number=30, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='getInAppPurchaseInformationResponse', full_name='SingleResponseProto.getInAppPurchaseInformationResponse', index=26,
      number=31, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='checkForNotificationsResponse', full_name='SingleResponseProto.checkForNotificationsResponse', index=27,
      number=32, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='ackNotificationsResponse', full_name='SingleResponseProto.ackNotificationsResponse', index=28,
      number=33, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='purchaseProductResponse', full_name='SingleResponseProto.purchaseProductResponse', index=29,
      number=34, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='reconstructDatabaseResponse', full_name='SingleResponseProto.reconstructDatabaseResponse', index=30,
      number=35, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='paypalMassageAddressResponse', full_name='SingleResponseProto.paypalMassageAddressResponse', index=31,
      number=36, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='getAddressSnippetResponse', full_name='SingleResponseProto.getAddressSnippetResponse', index=32,
      number=37, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=44310,
  serialized_end=46450,
)


_STATUSBARNOTIFICATIONPROTO = descriptor.Descriptor(
  name='StatusBarNotificationProto',
  full_name='StatusBarNotificationProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='tickerText', full_name='StatusBarNotificationProto.tickerText', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='contentTitle', full_name='StatusBarNotificationProto.contentTitle', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='contentText', full_name='StatusBarNotificationProto.contentText', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=46452,
  serialized_end=46543,
)


_UNINSTALLREASONREQUESTPROTO = descriptor.Descriptor(
  name='UninstallReasonRequestProto',
  full_name='UninstallReasonRequestProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='assetId', full_name='UninstallReasonRequestProto.assetId', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='reason', full_name='UninstallReasonRequestProto.reason', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=46545,
  serialized_end=46607,
)


_UNINSTALLREASONRESPONSEPROTO = descriptor.Descriptor(
  name='UninstallReasonResponseProto',
  full_name='UninstallReasonResponseProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=46609,
  serialized_end=46639,
)


_ANDROIDAPPDELIVERYDATA.fields_by_name['additionalFile'].message_type = _APPFILEMETADATA
_ANDROIDAPPDELIVERYDATA.fields_by_name['downloadAuthCookie'].message_type = _HTTPCOOKIE
_ANDROIDAPPDELIVERYDATA.fields_by_name['patchData'].message_type = _ANDROIDAPPPATCHDATA
_ANDROIDAPPDELIVERYDATA.fields_by_name['encryptionParams'].message_type = _ENCRYPTIONPARAMS
_BOOKAUTHOR.fields_by_name['docid'].message_type = _DOCID
_BOOKDETAILS_IDENTIFIER.containing_type = _BOOKDETAILS;
_BOOKDETAILS.fields_by_name['subject'].message_type = _BOOKSUBJECT
_BOOKDETAILS.fields_by_name['author'].message_type = _BOOKAUTHOR
_BOOKDETAILS.fields_by_name['identifier'].message_type = _BOOKDETAILS_IDENTIFIER
_BROWSERESPONSE.fields_by_name['category'].message_type = _BROWSELINK
_BROWSERESPONSE.fields_by_name['breadcrumb'].message_type = _BROWSELINK
_ADDRESSCHALLENGE.fields_by_name['checkbox'].message_type = _FORMCHECKBOX
_ADDRESSCHALLENGE.fields_by_name['address'].message_type = _ADDRESS
_ADDRESSCHALLENGE.fields_by_name['errorInputField'].message_type = _INPUTVALIDATIONERROR
_BUYRESPONSE_CHECKOUTINFO_CHECKOUTOPTION.fields_by_name['item'].message_type = _LINEITEM
_BUYRESPONSE_CHECKOUTINFO_CHECKOUTOPTION.fields_by_name['subItem'].message_type = _LINEITEM
_BUYRESPONSE_CHECKOUTINFO_CHECKOUTOPTION.fields_by_name['total'].message_type = _LINEITEM
_BUYRESPONSE_CHECKOUTINFO_CHECKOUTOPTION.fields_by_name['summary'].message_type = _LINEITEM
_BUYRESPONSE_CHECKOUTINFO_CHECKOUTOPTION.fields_by_name['instrument'].message_type = _INSTRUMENT
_BUYRESPONSE_CHECKOUTINFO_CHECKOUTOPTION.containing_type = _BUYRESPONSE_CHECKOUTINFO;
_BUYRESPONSE_CHECKOUTINFO.fields_by_name['item'].message_type = _LINEITEM
_BUYRESPONSE_CHECKOUTINFO.fields_by_name['subItem'].message_type = _LINEITEM
_BUYRESPONSE_CHECKOUTINFO.fields_by_name['checkoutoption'].message_type = _BUYRESPONSE_CHECKOUTINFO_CHECKOUTOPTION
_BUYRESPONSE_CHECKOUTINFO.fields_by_name['eligibleInstrument'].message_type = _INSTRUMENT
_BUYRESPONSE_CHECKOUTINFO.containing_type = _BUYRESPONSE;
_BUYRESPONSE.fields_by_name['purchaseResponse'].message_type = _PURCHASENOTIFICATIONRESPONSE
_BUYRESPONSE.fields_by_name['checkoutinfo'].message_type = _BUYRESPONSE_CHECKOUTINFO
_BUYRESPONSE.fields_by_name['purchaseStatusResponse'].message_type = _PURCHASESTATUSRESPONSE
_BUYRESPONSE.fields_by_name['challenge'].message_type = _CHALLENGE
_CHALLENGE.fields_by_name['addressChallenge'].message_type = _ADDRESSCHALLENGE
_CHALLENGE.fields_by_name['authenticationChallenge'].message_type = _AUTHENTICATIONCHALLENGE
_LINEITEM.fields_by_name['offer'].message_type = _OFFER
_LINEITEM.fields_by_name['amount'].message_type = _MONEY
_PURCHASENOTIFICATIONRESPONSE.fields_by_name['debugInfo'].message_type = _DEBUGINFO
_PURCHASESTATUSRESPONSE.fields_by_name['libraryUpdate'].message_type = _LIBRARYUPDATE
_PURCHASESTATUSRESPONSE.fields_by_name['rejectedInstrument'].message_type = _INSTRUMENT
_PURCHASESTATUSRESPONSE.fields_by_name['appDeliveryData'].message_type = _ANDROIDAPPDELIVERYDATA
_CHECKINSTRUMENTRESPONSE.fields_by_name['instrument'].message_type = _INSTRUMENT
_CHECKINSTRUMENTRESPONSE.fields_by_name['eligibleInstrument'].message_type = _INSTRUMENT
_UPDATEINSTRUMENTREQUEST.fields_by_name['instrument'].message_type = _INSTRUMENT
_UPDATEINSTRUMENTRESPONSE.fields_by_name['errorInputField'].message_type = _INPUTVALIDATIONERROR
_UPDATEINSTRUMENTRESPONSE.fields_by_name['redeemedOffer'].message_type = _REDEEMEDPROMOOFFER
_VERIFYASSOCIATIONRESPONSE.fields_by_name['billingAddress'].message_type = _ADDRESS
_VERIFYASSOCIATIONRESPONSE.fields_by_name['carrierTos'].message_type = _CARRIERTOS
_ADDCREDITCARDPROMOOFFER.fields_by_name['image'].message_type = _IMAGE
_AVAILABLEPROMOOFFER.fields_by_name['addCreditCardOffer'].message_type = _ADDCREDITCARDPROMOOFFER
_CHECKPROMOOFFERRESPONSE.fields_by_name['availableOffer'].message_type = _AVAILABLEPROMOOFFER
_CHECKPROMOOFFERRESPONSE.fields_by_name['redeemedOffer'].message_type = _REDEEMEDPROMOOFFER
_REDEEMEDPROMOOFFER.fields_by_name['image'].message_type = _IMAGE
_OFFER.fields_by_name['convertedPrice'].message_type = _OFFER
_OFFER.fields_by_name['rentalTerms'].message_type = _RENTALTERMS
_OFFER.fields_by_name['subscriptionTerms'].message_type = _SUBSCRIPTIONTERMS
_SUBSCRIPTIONTERMS.fields_by_name['recurringPeriod'].message_type = _TIMEPERIOD
_SUBSCRIPTIONTERMS.fields_by_name['trialPeriod'].message_type = _TIMEPERIOD
_CARRIERBILLINGINSTRUMENT.fields_by_name['encryptedSubscriberInfo'].message_type = _ENCRYPTEDSUBSCRIBERINFO
_CARRIERBILLINGINSTRUMENT.fields_by_name['credentials'].message_type = _CARRIERBILLINGCREDENTIALS
_CARRIERBILLINGINSTRUMENT.fields_by_name['acceptedCarrierTos'].message_type = _CARRIERTOS
_CARRIERBILLINGINSTRUMENTSTATUS.fields_by_name['carrierTos'].message_type = _CARRIERTOS
_CARRIERBILLINGINSTRUMENTSTATUS.fields_by_name['carrierPasswordPrompt'].message_type = _PASSWORDPROMPT
_CARRIERTOS.fields_by_name['dcbTos'].message_type = _CARRIERTOSENTRY
_CARRIERTOS.fields_by_name['piiTos'].message_type = _CARRIERTOSENTRY
_CREDITCARDINSTRUMENT.fields_by_name['escrowEfeParam'].message_type = _EFEPARAM
_INSTRUMENT.fields_by_name['billingAddress'].message_type = _ADDRESS
_INSTRUMENT.fields_by_name['creditCard'].message_type = _CREDITCARDINSTRUMENT
_INSTRUMENT.fields_by_name['carrierBilling'].message_type = _CARRIERBILLINGINSTRUMENT
_INSTRUMENT.fields_by_name['billingAddressSpec'].message_type = _BILLINGADDRESSSPEC
_INSTRUMENT.fields_by_name['carrierBillingStatus'].message_type = _CARRIERBILLINGINSTRUMENTSTATUS
_DEBUGINFO_TIMING.containing_type = _DEBUGINFO;
_DEBUGINFO.fields_by_name['timing'].message_type = _DEBUGINFO_TIMING
_DELIVERYRESPONSE.fields_by_name['appDeliveryData'].message_type = _ANDROIDAPPDELIVERYDATA
_BULKDETAILSENTRY.fields_by_name['doc'].message_type = _DOCV2
_BULKDETAILSRESPONSE.fields_by_name['entry'].message_type = _BULKDETAILSENTRY
_DETAILSRESPONSE.fields_by_name['docV1'].message_type = _DOCV1
_DETAILSRESPONSE.fields_by_name['userReview'].message_type = _REVIEW
_DETAILSRESPONSE.fields_by_name['docV2'].message_type = _DOCV2
_DOCUMENT.fields_by_name['docid'].message_type = _DOCID
_DOCUMENT.fields_by_name['fetchDocid'].message_type = _DOCID
_DOCUMENT.fields_by_name['sampleDocid'].message_type = _DOCID
_DOCUMENT.fields_by_name['priceDeprecated'].message_type = _OFFER
_DOCUMENT.fields_by_name['availability'].message_type = _AVAILABILITY
_DOCUMENT.fields_by_name['image'].message_type = _IMAGE
_DOCUMENT.fields_by_name['child'].message_type = _DOCUMENT
_DOCUMENT.fields_by_name['aggregateRating'].message_type = _AGGREGATERATING
_DOCUMENT.fields_by_name['offer'].message_type = _OFFER
_DOCUMENT.fields_by_name['translatedSnippet'].message_type = _TRANSLATEDTEXT
_DOCUMENT.fields_by_name['documentVariant'].message_type = _DOCUMENTVARIANT
_DOCUMENT.fields_by_name['decoration'].message_type = _DOCUMENT
_DOCUMENT.fields_by_name['parent'].message_type = _DOCUMENT
_DOCUMENTVARIANT.fields_by_name['rule'].message_type = _RULE
_DOCUMENTVARIANT.fields_by_name['autoTranslation'].message_type = _TRANSLATEDTEXT
_DOCUMENTVARIANT.fields_by_name['offer'].message_type = _OFFER
_DOCUMENTVARIANT.fields_by_name['child'].message_type = _DOCUMENT
_DOCUMENTVARIANT.fields_by_name['decoration'].message_type = _DOCUMENT
_IMAGE_DIMENSION.containing_type = _IMAGE;
_IMAGE_CITATION.containing_type = _IMAGE;
_IMAGE.fields_by_name['dimension'].message_type = _IMAGE_DIMENSION
_IMAGE.fields_by_name['citation'].message_type = _IMAGE_CITATION
_BADGE.fields_by_name['image'].message_type = _IMAGE
_PLUSONEDATA.fields_by_name['circlesPeople'].message_type = _PLUSPERSON
_PROMOTEDDOC.fields_by_name['image'].message_type = _IMAGE
_SERIESANTENNA.fields_by_name['sectionTracks'].message_type = _SECTIONMETADATA
_SERIESANTENNA.fields_by_name['sectionAlbums'].message_type = _SECTIONMETADATA
_TEMPLATE.fields_by_name['seriesAntenna'].message_type = _SERIESANTENNA
_TEMPLATE.fields_by_name['tileGraphic2X1'].message_type = _TILETEMPLATE
_TEMPLATE.fields_by_name['tileGraphic4X2'].message_type = _TILETEMPLATE
_TEMPLATE.fields_by_name['tileGraphicColoredTitle2X1'].message_type = _TILETEMPLATE
_TEMPLATE.fields_by_name['tileGraphicUpperLeftTitle2X1'].message_type = _TILETEMPLATE
_TEMPLATE.fields_by_name['tileDetailsReflectedGraphic2X2'].message_type = _TILETEMPLATE
_TEMPLATE.fields_by_name['tileFourBlock4X2'].message_type = _TILETEMPLATE
_TEMPLATE.fields_by_name['containerWithBanner'].message_type = _CONTAINERWITHBANNER
_TEMPLATE.fields_by_name['dealOfTheDay'].message_type = _DEALOFTHEDAY
_TEMPLATE.fields_by_name['tileGraphicColoredTitle4X2'].message_type = _TILETEMPLATE
_TEMPLATE.fields_by_name['editorialSeriesContainer'].message_type = _EDITORIALSERIESCONTAINER
_ALBUMDETAILS.fields_by_name['details'].message_type = _MUSICDETAILS
_ALBUMDETAILS.fields_by_name['displayArtist'].message_type = _ARTISTDETAILS
_APPDETAILS.fields_by_name['file'].message_type = _FILEMETADATA
_ARTISTDETAILS.fields_by_name['externalLinks'].message_type = _ARTISTEXTERNALLINKS
_DOCUMENTDETAILS.fields_by_name['appDetails'].message_type = _APPDETAILS
_DOCUMENTDETAILS.fields_by_name['albumDetails'].message_type = _ALBUMDETAILS
_DOCUMENTDETAILS.fields_by_name['artistDetails'].message_type = _ARTISTDETAILS
_DOCUMENTDETAILS.fields_by_name['songDetails'].message_type = _SONGDETAILS
_DOCUMENTDETAILS.fields_by_name['bookDetails'].message_type = _BOOKDETAILS
_DOCUMENTDETAILS.fields_by_name['videoDetails'].message_type = _VIDEODETAILS
_DOCUMENTDETAILS.fields_by_name['subscriptionDetails'].message_type = _SUBSCRIPTIONDETAILS
_DOCUMENTDETAILS.fields_by_name['magazineDetails'].message_type = _MAGAZINEDETAILS
_DOCUMENTDETAILS.fields_by_name['tvShowDetails'].message_type = _TVSHOWDETAILS
_DOCUMENTDETAILS.fields_by_name['tvSeasonDetails'].message_type = _TVSEASONDETAILS
_DOCUMENTDETAILS.fields_by_name['tvEpisodeDetails'].message_type = _TVEPISODEDETAILS
_MUSICDETAILS.fields_by_name['artist'].message_type = _ARTISTDETAILS
_SONGDETAILS.fields_by_name['details'].message_type = _MUSICDETAILS
_SONGDETAILS.fields_by_name['displayArtist'].message_type = _ARTISTDETAILS
_VIDEODETAILS.fields_by_name['credit'].message_type = _VIDEOCREDIT
_VIDEODETAILS.fields_by_name['trailer'].message_type = _TRAILER
_VIDEODETAILS.fields_by_name['rentalTerm'].message_type = _VIDEORENTALTERM
_VIDEORENTALTERM_TERM.containing_type = _VIDEORENTALTERM;
_VIDEORENTALTERM.fields_by_name['term'].message_type = _VIDEORENTALTERM_TERM
_BUCKET.fields_by_name['document'].message_type = _DOCV1
_LISTRESPONSE.fields_by_name['bucket'].message_type = _BUCKET
_LISTRESPONSE.fields_by_name['doc'].message_type = _DOCV2
_DOCV1.fields_by_name['finskyDoc'].message_type = _DOCUMENT
_DOCV1.fields_by_name['details'].message_type = _DOCUMENTDETAILS
_DOCV1.fields_by_name['plusOneData'].message_type = _PLUSONEDATA
_ANNOTATIONS.fields_by_name['sectionRelated'].message_type = _SECTIONMETADATA
_ANNOTATIONS.fields_by_name['sectionMoreBy'].message_type = _SECTIONMETADATA
_ANNOTATIONS.fields_by_name['plusOneData'].message_type = _PLUSONEDATA
_ANNOTATIONS.fields_by_name['warning'].message_type = _WARNING
_ANNOTATIONS.fields_by_name['sectionBodyOfWork'].message_type = _SECTIONMETADATA
_ANNOTATIONS.fields_by_name['sectionCoreContent'].message_type = _SECTIONMETADATA
_ANNOTATIONS.fields_by_name['template'].message_type = _TEMPLATE
_ANNOTATIONS.fields_by_name['badgeForCreator'].message_type = _BADGE
_ANNOTATIONS.fields_by_name['badgeForDoc'].message_type = _BADGE
_ANNOTATIONS.fields_by_name['link'].message_type = _LINK
_ANNOTATIONS.fields_by_name['sectionCrossSell'].message_type = _SECTIONMETADATA
_ANNOTATIONS.fields_by_name['sectionRelatedDocType'].message_type = _SECTIONMETADATA
_ANNOTATIONS.fields_by_name['promotedDoc'].message_type = _PROMOTEDDOC
_ANNOTATIONS.fields_by_name['subscription'].message_type = _DOCV2
_ANNOTATIONS.fields_by_name['reason'].message_type = _REASON
_DOCV2.fields_by_name['offer'].message_type = _OFFER
_DOCV2.fields_by_name['availability'].message_type = _AVAILABILITY
_DOCV2.fields_by_name['image'].message_type = _IMAGE
_DOCV2.fields_by_name['child'].message_type = _DOCV2
_DOCV2.fields_by_name['containerMetadata'].message_type = _CONTAINERMETADATA
_DOCV2.fields_by_name['details'].message_type = _DOCUMENTDETAILS
_DOCV2.fields_by_name['aggregateRating'].message_type = _AGGREGATERATING
_DOCV2.fields_by_name['annotations'].message_type = _ANNOTATIONS
_AVAILABILITY_PERDEVICEAVAILABILITYRESTRICTION.fields_by_name['filterInfo'].message_type = _FILTEREVALUATIONINFO
_AVAILABILITY_PERDEVICEAVAILABILITYRESTRICTION.containing_type = _AVAILABILITY;
_AVAILABILITY.fields_by_name['rule'].message_type = _RULE
_AVAILABILITY.fields_by_name['perdeviceavailabilityrestriction'].message_type = _AVAILABILITY_PERDEVICEAVAILABILITYRESTRICTION
_AVAILABILITY.fields_by_name['install'].message_type = _INSTALL
_AVAILABILITY.fields_by_name['filterInfo'].message_type = _FILTEREVALUATIONINFO
_AVAILABILITY.fields_by_name['ownershipInfo'].message_type = _OWNERSHIPINFO
_FILTEREVALUATIONINFO.fields_by_name['ruleEvaluation'].message_type = _RULEEVALUATION
_RULE.fields_by_name['subrule'].message_type = _RULE
_RULEEVALUATION.fields_by_name['rule'].message_type = _RULE
_LIBRARYMUTATION.fields_by_name['docid'].message_type = _DOCID
_LIBRARYMUTATION.fields_by_name['appDetails'].message_type = _LIBRARYAPPDETAILS
_LIBRARYMUTATION.fields_by_name['subscriptionDetails'].message_type = _LIBRARYSUBSCRIPTIONDETAILS
_LIBRARYUPDATE.fields_by_name['mutation'].message_type = _LIBRARYMUTATION
_LIBRARYREPLICATIONREQUEST.fields_by_name['libraryState'].message_type = _CLIENTLIBRARYSTATE
_LIBRARYREPLICATIONRESPONSE.fields_by_name['update'].message_type = _LIBRARYUPDATE
_LOGREQUEST.fields_by_name['clickEvent'].message_type = _CLICKLOGEVENT
_NOTIFICATION.fields_by_name['docid'].message_type = _DOCID
_NOTIFICATION.fields_by_name['appData'].message_type = _ANDROIDAPPNOTIFICATIONDATA
_NOTIFICATION.fields_by_name['appDeliveryData'].message_type = _ANDROIDAPPDELIVERYDATA
_NOTIFICATION.fields_by_name['purchaseRemovalData'].message_type = _PURCHASEREMOVALDATA
_NOTIFICATION.fields_by_name['userNotificationData'].message_type = _USERNOTIFICATIONDATA
_NOTIFICATION.fields_by_name['inAppNotificationData'].message_type = _INAPPNOTIFICATIONDATA
_NOTIFICATION.fields_by_name['purchaseDeclinedData'].message_type = _PURCHASEDECLINEDDATA
_NOTIFICATION.fields_by_name['libraryUpdate'].message_type = _LIBRARYUPDATE
_NOTIFICATION.fields_by_name['libraryDirtyData'].message_type = _LIBRARYDIRTYDATA
_RESOLVELINKRESPONSE.fields_by_name['directPurchase'].message_type = _DIRECTPURCHASE
_PAYLOAD.fields_by_name['listResponse'].message_type = _LISTRESPONSE
_PAYLOAD.fields_by_name['detailsResponse'].message_type = _DETAILSRESPONSE
_PAYLOAD.fields_by_name['reviewResponse'].message_type = _REVIEWRESPONSE
_PAYLOAD.fields_by_name['buyResponse'].message_type = _BUYRESPONSE
_PAYLOAD.fields_by_name['searchResponse'].message_type = _SEARCHRESPONSE
_PAYLOAD.fields_by_name['tocResponse'].message_type = _TOCRESPONSE
_PAYLOAD.fields_by_name['browseResponse'].message_type = _BROWSERESPONSE
_PAYLOAD.fields_by_name['purchaseStatusResponse'].message_type = _PURCHASESTATUSRESPONSE
_PAYLOAD.fields_by_name['updateInstrumentResponse'].message_type = _UPDATEINSTRUMENTRESPONSE
_PAYLOAD.fields_by_name['logResponse'].message_type = _LOGRESPONSE
_PAYLOAD.fields_by_name['checkInstrumentResponse'].message_type = _CHECKINSTRUMENTRESPONSE
_PAYLOAD.fields_by_name['plusOneResponse'].message_type = _PLUSONERESPONSE
_PAYLOAD.fields_by_name['flagContentResponse'].message_type = _FLAGCONTENTRESPONSE
_PAYLOAD.fields_by_name['ackNotificationResponse'].message_type = _ACKNOTIFICATIONRESPONSE
_PAYLOAD.fields_by_name['initiateAssociationResponse'].message_type = _INITIATEASSOCIATIONRESPONSE
_PAYLOAD.fields_by_name['verifyAssociationResponse'].message_type = _VERIFYASSOCIATIONRESPONSE
_PAYLOAD.fields_by_name['libraryReplicationResponse'].message_type = _LIBRARYREPLICATIONRESPONSE
_PAYLOAD.fields_by_name['revokeResponse'].message_type = _REVOKERESPONSE
_PAYLOAD.fields_by_name['bulkDetailsResponse'].message_type = _BULKDETAILSRESPONSE
_PAYLOAD.fields_by_name['resolveLinkResponse'].message_type = _RESOLVELINKRESPONSE
_PAYLOAD.fields_by_name['deliveryResponse'].message_type = _DELIVERYRESPONSE
_PAYLOAD.fields_by_name['acceptTosResponse'].message_type = _ACCEPTTOSRESPONSE
_PAYLOAD.fields_by_name['rateSuggestedContentResponse'].message_type = _RATESUGGESTEDCONTENTRESPONSE
_PAYLOAD.fields_by_name['checkPromoOfferResponse'].message_type = _CHECKPROMOOFFERRESPONSE
_RESPONSEWRAPPER.fields_by_name['payload'].message_type = _PAYLOAD
_RESPONSEWRAPPER.fields_by_name['commands'].message_type = _SERVERCOMMANDS
_RESPONSEWRAPPER.fields_by_name['preFetch'].message_type = _PREFETCH
_RESPONSEWRAPPER.fields_by_name['notification'].message_type = _NOTIFICATION
_GETREVIEWSRESPONSE.fields_by_name['review'].message_type = _REVIEW
_REVIEWRESPONSE.fields_by_name['getResponse'].message_type = _GETREVIEWSRESPONSE
_REVOKERESPONSE.fields_by_name['libraryUpdate'].message_type = _LIBRARYUPDATE
_SEARCHRESPONSE.fields_by_name['bucket'].message_type = _BUCKET
_SEARCHRESPONSE.fields_by_name['doc'].message_type = _DOCV2
_SEARCHRESPONSE.fields_by_name['relatedSearch'].message_type = _RELATEDSEARCH
_TOCRESPONSE.fields_by_name['corpus'].message_type = _CORPUSMETADATA
_TOCRESPONSE.fields_by_name['experiments'].message_type = _EXPERIMENTS
_TOCRESPONSE.fields_by_name['userSettings'].message_type = _USERSETTINGS
_ACKNOTIFICATIONSREQUESTPROTO.fields_by_name['signatureHash'].message_type = _SIGNATUREHASHPROTO
_APPSUGGESTIONPROTO.fields_by_name['assetInfo'].message_type = _EXTERNALASSETPROTO
_ASSETSRESPONSEPROTO.fields_by_name['asset'].message_type = _EXTERNALASSETPROTO
_ASSETSRESPONSEPROTO.fields_by_name['altAsset'].message_type = _EXTERNALASSETPROTO
_BILLINGEVENTREQUESTPROTO.fields_by_name['carrierInstrument'].message_type = _EXTERNALCARRIERBILLINGINSTRUMENTPROTO
_CATEGORYPROTO.fields_by_name['subCategories'].message_type = _CATEGORYPROTO
_COMMENTSRESPONSEPROTO.fields_by_name['comment'].message_type = _EXTERNALCOMMENTPROTO
_COMMENTSRESPONSEPROTO.fields_by_name['selfComment'].message_type = _EXTERNALCOMMENTPROTO
_CONTENTSYNCREQUESTPROTO_ASSETINSTALLSTATE.containing_type = _CONTENTSYNCREQUESTPROTO;
_CONTENTSYNCREQUESTPROTO_SYSTEMAPP.containing_type = _CONTENTSYNCREQUESTPROTO;
_CONTENTSYNCREQUESTPROTO.fields_by_name['assetinstallstate'].message_type = _CONTENTSYNCREQUESTPROTO_ASSETINSTALLSTATE
_CONTENTSYNCREQUESTPROTO.fields_by_name['systemapp'].message_type = _CONTENTSYNCREQUESTPROTO_SYSTEMAPP
_DATAMESSAGEPROTO.fields_by_name['appData'].message_type = _APPDATAPROTO
_DOWNLOADINFOPROTO.fields_by_name['additionalFile'].message_type = _FILEMETADATAPROTO
_EXTERNALASSETPROTO_PURCHASEINFORMATION.containing_type = _EXTERNALASSETPROTO;
_EXTERNALASSETPROTO_EXTENDEDINFO_PACKAGEDEPENDENCY.containing_type = _EXTERNALASSETPROTO_EXTENDEDINFO;
_EXTERNALASSETPROTO_EXTENDEDINFO.fields_by_name['packagedependency'].message_type = _EXTERNALASSETPROTO_EXTENDEDINFO_PACKAGEDEPENDENCY
_EXTERNALASSETPROTO_EXTENDEDINFO.fields_by_name['downloadInfo'].message_type = _DOWNLOADINFOPROTO
_EXTERNALASSETPROTO_EXTENDEDINFO.containing_type = _EXTERNALASSETPROTO;
_EXTERNALASSETPROTO.fields_by_name['purchaseinformation'].message_type = _EXTERNALASSETPROTO_PURCHASEINFORMATION
_EXTERNALASSETPROTO.fields_by_name['extendedinfo'].message_type = _EXTERNALASSETPROTO_EXTENDEDINFO
_EXTERNALASSETPROTO.fields_by_name['appBadge'].message_type = _EXTERNALBADGEPROTO
_EXTERNALASSETPROTO.fields_by_name['ownerBadge'].message_type = _EXTERNALBADGEPROTO
_EXTERNALBADGEPROTO.fields_by_name['badgeImage'].message_type = _EXTERNALBADGEIMAGEPROTO
_EXTERNALCARRIERBILLINGINSTRUMENTPROTO.fields_by_name['encryptedSubscriberInfo'].message_type = _ENCRYPTEDSUBSCRIBERINFO
_EXTERNALPAYPALINSTRUMENTPROTO.fields_by_name['paypalAddress'].message_type = _ADDRESSPROTO
_GETADDRESSSNIPPETREQUESTPROTO.fields_by_name['encryptedSubscriberInfo'].message_type = _ENCRYPTEDSUBSCRIBERINFO
_GETASSETRESPONSEPROTO_INSTALLASSET.containing_type = _GETASSETRESPONSEPROTO;
_GETASSETRESPONSEPROTO.fields_by_name['installasset'].message_type = _GETASSETRESPONSEPROTO_INSTALLASSET
_GETASSETRESPONSEPROTO.fields_by_name['additionalFile'].message_type = _FILEMETADATAPROTO
_GETCATEGORIESRESPONSEPROTO.fields_by_name['categories'].message_type = _CATEGORYPROTO
_GETMARKETMETADATAREQUESTPROTO.fields_by_name['deviceConfiguration'].message_type = _DEVICECONFIGURATIONPROTO
_GETMARKETMETADATARESPONSEPROTO.fields_by_name['billingParameter'].message_type = _BILLINGPARAMETERPROTO
_GETSUBCATEGORIESRESPONSEPROTO_SUBCATEGORY.containing_type = _GETSUBCATEGORIESRESPONSEPROTO;
_GETSUBCATEGORIESRESPONSEPROTO.fields_by_name['subcategory'].message_type = _GETSUBCATEGORIESRESPONSEPROTO_SUBCATEGORY
_INAPPPURCHASEINFORMATIONREQUESTPROTO.fields_by_name['signatureHash'].message_type = _SIGNATUREHASHPROTO
_INAPPPURCHASEINFORMATIONRESPONSEPROTO.fields_by_name['signedResponse'].message_type = _SIGNEDDATAPROTO
_INAPPPURCHASEINFORMATIONRESPONSEPROTO.fields_by_name['statusBarNotification'].message_type = _STATUSBARNOTIFICATIONPROTO
_INAPPPURCHASEINFORMATIONRESPONSEPROTO.fields_by_name['purchaseResult'].message_type = _PURCHASERESULTPROTO
_INAPPRESTORETRANSACTIONSREQUESTPROTO.fields_by_name['signatureHash'].message_type = _SIGNATUREHASHPROTO
_INAPPRESTORETRANSACTIONSRESPONSEPROTO.fields_by_name['signedResponse'].message_type = _SIGNEDDATAPROTO
_INAPPRESTORETRANSACTIONSRESPONSEPROTO.fields_by_name['purchaseResult'].message_type = _PURCHASERESULTPROTO
_MODIFYCOMMENTREQUESTPROTO.fields_by_name['comment'].message_type = _EXTERNALCOMMENTPROTO
_PAYPALCREATEACCOUNTREQUESTPROTO.fields_by_name['address'].message_type = _ADDRESSPROTO
_PAYPALMASSAGEADDRESSREQUESTPROTO.fields_by_name['address'].message_type = _ADDRESSPROTO
_PAYPALMASSAGEADDRESSRESPONSEPROTO.fields_by_name['address'].message_type = _ADDRESSPROTO
_PAYPALPREAPPROVALDETAILSRESPONSEPROTO.fields_by_name['address'].message_type = _ADDRESSPROTO
_PENDINGNOTIFICATIONSPROTO.fields_by_name['notification'].message_type = _DATAMESSAGEPROTO
_PREFETCHEDBUNDLEPROTO.fields_by_name['request'].message_type = _SINGLEREQUESTPROTO
_PREFETCHEDBUNDLEPROTO.fields_by_name['response'].message_type = _SINGLERESPONSEPROTO
_PURCHASEINFOPROTO_BILLINGINSTRUMENTS_BILLINGINSTRUMENT.containing_type = _PURCHASEINFOPROTO_BILLINGINSTRUMENTS;
_PURCHASEINFOPROTO_BILLINGINSTRUMENTS.fields_by_name['billinginstrument'].message_type = _PURCHASEINFOPROTO_BILLINGINSTRUMENTS_BILLINGINSTRUMENT
_PURCHASEINFOPROTO_BILLINGINSTRUMENTS.containing_type = _PURCHASEINFOPROTO;
_PURCHASEINFOPROTO.fields_by_name['cartInfo'].message_type = _PURCHASECARTINFOPROTO
_PURCHASEINFOPROTO.fields_by_name['billinginstruments'].message_type = _PURCHASEINFOPROTO_BILLINGINSTRUMENTS
_PURCHASEMETADATARESPONSEPROTO_COUNTRIES_COUNTRY_INSTRUMENTADDRESSSPEC.fields_by_name['billingAddressSpec'].message_type = _BILLINGADDRESSSPEC
_PURCHASEMETADATARESPONSEPROTO_COUNTRIES_COUNTRY_INSTRUMENTADDRESSSPEC.containing_type = _PURCHASEMETADATARESPONSEPROTO_COUNTRIES_COUNTRY;
_PURCHASEMETADATARESPONSEPROTO_COUNTRIES_COUNTRY.fields_by_name['paypalCountryInfo'].message_type = _PAYPALCOUNTRYINFOPROTO
_PURCHASEMETADATARESPONSEPROTO_COUNTRIES_COUNTRY.fields_by_name['instrumentaddressspec'].message_type = _PURCHASEMETADATARESPONSEPROTO_COUNTRIES_COUNTRY_INSTRUMENTADDRESSSPEC
_PURCHASEMETADATARESPONSEPROTO_COUNTRIES_COUNTRY.containing_type = _PURCHASEMETADATARESPONSEPROTO_COUNTRIES;
_PURCHASEMETADATARESPONSEPROTO_COUNTRIES.fields_by_name['country'].message_type = _PURCHASEMETADATARESPONSEPROTO_COUNTRIES_COUNTRY
_PURCHASEMETADATARESPONSEPROTO_COUNTRIES.containing_type = _PURCHASEMETADATARESPONSEPROTO;
_PURCHASEMETADATARESPONSEPROTO.fields_by_name['countries'].message_type = _PURCHASEMETADATARESPONSEPROTO_COUNTRIES
_PURCHASEORDERREQUESTPROTO.fields_by_name['carrierBillingCredentials'].message_type = _CARRIERBILLINGCREDENTIALSPROTO
_PURCHASEORDERREQUESTPROTO.fields_by_name['paypalCredentials'].message_type = _PAYPALCREDENTIALSPROTO
_PURCHASEORDERREQUESTPROTO.fields_by_name['riskHeaderInfo'].message_type = _RISKHEADERINFOPROTO
_PURCHASEORDERREQUESTPROTO.fields_by_name['signatureHash'].message_type = _SIGNATUREHASHPROTO
_PURCHASEORDERRESPONSEPROTO.fields_by_name['purchaseInfo'].message_type = _PURCHASEINFOPROTO
_PURCHASEORDERRESPONSEPROTO.fields_by_name['asset'].message_type = _EXTERNALASSETPROTO
_PURCHASEORDERRESPONSEPROTO.fields_by_name['purchaseResult'].message_type = _PURCHASERESULTPROTO
_PURCHASEPOSTREQUESTPROTO_BILLINGINSTRUMENTINFO.fields_by_name['creditCard'].message_type = _EXTERNALCREDITCARD
_PURCHASEPOSTREQUESTPROTO_BILLINGINSTRUMENTINFO.fields_by_name['carrierInstrument'].message_type = _EXTERNALCARRIERBILLINGINSTRUMENTPROTO
_PURCHASEPOSTREQUESTPROTO_BILLINGINSTRUMENTINFO.fields_by_name['paypalInstrument'].message_type = _EXTERNALPAYPALINSTRUMENTPROTO
_PURCHASEPOSTREQUESTPROTO_BILLINGINSTRUMENTINFO.containing_type = _PURCHASEPOSTREQUESTPROTO;
_PURCHASEPOSTREQUESTPROTO.fields_by_name['billinginstrumentinfo'].message_type = _PURCHASEPOSTREQUESTPROTO_BILLINGINSTRUMENTINFO
_PURCHASEPOSTREQUESTPROTO.fields_by_name['signatureHash'].message_type = _SIGNATUREHASHPROTO
_PURCHASEPOSTRESPONSEPROTO.fields_by_name['purchaseInfo'].message_type = _PURCHASEINFOPROTO
_PURCHASEPOSTRESPONSEPROTO.fields_by_name['purchaseResult'].message_type = _PURCHASERESULTPROTO
_PURCHASEPRODUCTREQUESTPROTO.fields_by_name['signatureHash'].message_type = _SIGNATUREHASHPROTO
_QUERYSUGGESTIONRESPONSEPROTO_SUGGESTION.fields_by_name['appSuggestion'].message_type = _APPSUGGESTIONPROTO
_QUERYSUGGESTIONRESPONSEPROTO_SUGGESTION.fields_by_name['querySuggestion'].message_type = _QUERYSUGGESTIONPROTO
_QUERYSUGGESTIONRESPONSEPROTO_SUGGESTION.containing_type = _QUERYSUGGESTIONRESPONSEPROTO;
_QUERYSUGGESTIONRESPONSEPROTO.fields_by_name['suggestion'].message_type = _QUERYSUGGESTIONRESPONSEPROTO_SUGGESTION
_RECONSTRUCTDATABASERESPONSEPROTO.fields_by_name['asset'].message_type = _ASSETIDENTIFIERPROTO
_REFUNDRESPONSEPROTO.fields_by_name['asset'].message_type = _EXTERNALASSETPROTO
_REQUESTPROTO_REQUEST.fields_by_name['requestSpecificProperties'].message_type = _REQUESTSPECIFICPROPERTIESPROTO
_REQUESTPROTO_REQUEST.fields_by_name['assetRequest'].message_type = _ASSETSREQUESTPROTO
_REQUESTPROTO_REQUEST.fields_by_name['commentsRequest'].message_type = _COMMENTSREQUESTPROTO
_REQUESTPROTO_REQUEST.fields_by_name['modifyCommentRequest'].message_type = _MODIFYCOMMENTREQUESTPROTO
_REQUESTPROTO_REQUEST.fields_by_name['purchasePostRequest'].message_type = _PURCHASEPOSTREQUESTPROTO
_REQUESTPROTO_REQUEST.fields_by_name['purchaseOrderRequest'].message_type = _PURCHASEORDERREQUESTPROTO
_REQUESTPROTO_REQUEST.fields_by_name['contentSyncRequest'].message_type = _CONTENTSYNCREQUESTPROTO
_REQUESTPROTO_REQUEST.fields_by_name['getAssetRequest'].message_type = _GETASSETREQUESTPROTO
_REQUESTPROTO_REQUEST.fields_by_name['getImageRequest'].message_type = _GETIMAGEREQUESTPROTO
_REQUESTPROTO_REQUEST.fields_by_name['refundRequest'].message_type = _REFUNDREQUESTPROTO
_REQUESTPROTO_REQUEST.fields_by_name['purchaseMetadataRequest'].message_type = _PURCHASEMETADATAREQUESTPROTO
_REQUESTPROTO_REQUEST.fields_by_name['subCategoriesRequest'].message_type = _GETSUBCATEGORIESREQUESTPROTO
_REQUESTPROTO_REQUEST.fields_by_name['uninstallReasonRequest'].message_type = _UNINSTALLREASONREQUESTPROTO
_REQUESTPROTO_REQUEST.fields_by_name['rateCommentRequest'].message_type = _RATECOMMENTREQUESTPROTO
_REQUESTPROTO_REQUEST.fields_by_name['checkLicenseRequest'].message_type = _CHECKLICENSEREQUESTPROTO
_REQUESTPROTO_REQUEST.fields_by_name['getMarketMetadataRequest'].message_type = _GETMARKETMETADATAREQUESTPROTO
_REQUESTPROTO_REQUEST.fields_by_name['getCategoriesRequest'].message_type = _GETCATEGORIESREQUESTPROTO
_REQUESTPROTO_REQUEST.fields_by_name['getCarrierInfoRequest'].message_type = _GETCARRIERINFOREQUESTPROTO
_REQUESTPROTO_REQUEST.fields_by_name['removeAssetRequest'].message_type = _REMOVEASSETREQUESTPROTO
_REQUESTPROTO_REQUEST.fields_by_name['restoreApplicationsRequest'].message_type = _RESTOREAPPLICATIONSREQUESTPROTO
_REQUESTPROTO_REQUEST.fields_by_name['querySuggestionRequest'].message_type = _QUERYSUGGESTIONREQUESTPROTO
_REQUESTPROTO_REQUEST.fields_by_name['billingEventRequest'].message_type = _BILLINGEVENTREQUESTPROTO
_REQUESTPROTO_REQUEST.fields_by_name['paypalPreapprovalRequest'].message_type = _PAYPALPREAPPROVALREQUESTPROTO
_REQUESTPROTO_REQUEST.fields_by_name['paypalPreapprovalDetailsRequest'].message_type = _PAYPALPREAPPROVALDETAILSREQUESTPROTO
_REQUESTPROTO_REQUEST.fields_by_name['paypalCreateAccountRequest'].message_type = _PAYPALCREATEACCOUNTREQUESTPROTO
_REQUESTPROTO_REQUEST.fields_by_name['paypalPreapprovalCredentialsRequest'].message_type = _PAYPALPREAPPROVALCREDENTIALSREQUESTPROTO
_REQUESTPROTO_REQUEST.fields_by_name['inAppRestoreTransactionsRequest'].message_type = _INAPPRESTORETRANSACTIONSREQUESTPROTO
_REQUESTPROTO_REQUEST.fields_by_name['inAppPurchaseInformationRequest'].message_type = _INAPPPURCHASEINFORMATIONREQUESTPROTO
_REQUESTPROTO_REQUEST.fields_by_name['checkForNotificationsRequest'].message_type = _CHECKFORNOTIFICATIONSREQUESTPROTO
_REQUESTPROTO_REQUEST.fields_by_name['ackNotificationsRequest'].message_type = _ACKNOTIFICATIONSREQUESTPROTO
_REQUESTPROTO_REQUEST.fields_by_name['purchaseProductRequest'].message_type = _PURCHASEPRODUCTREQUESTPROTO
_REQUESTPROTO_REQUEST.fields_by_name['reconstructDatabaseRequest'].message_type = _RECONSTRUCTDATABASEREQUESTPROTO
_REQUESTPROTO_REQUEST.fields_by_name['paypalMassageAddressRequest'].message_type = _PAYPALMASSAGEADDRESSREQUESTPROTO
_REQUESTPROTO_REQUEST.fields_by_name['getAddressSnippetRequest'].message_type = _GETADDRESSSNIPPETREQUESTPROTO
_REQUESTPROTO_REQUEST.containing_type = _REQUESTPROTO;
_REQUESTPROTO.fields_by_name['requestProperties'].message_type = _REQUESTPROPERTIESPROTO
_REQUESTPROTO.fields_by_name['request'].message_type = _REQUESTPROTO_REQUEST
_RESPONSEPROPERTIESPROTO.fields_by_name['errorInputField'].message_type = _INPUTVALIDATIONERROR
_RESPONSEPROTO_RESPONSE.fields_by_name['responseProperties'].message_type = _RESPONSEPROPERTIESPROTO
_RESPONSEPROTO_RESPONSE.fields_by_name['assetsResponse'].message_type = _ASSETSRESPONSEPROTO
_RESPONSEPROTO_RESPONSE.fields_by_name['commentsResponse'].message_type = _COMMENTSRESPONSEPROTO
_RESPONSEPROTO_RESPONSE.fields_by_name['modifyCommentResponse'].message_type = _MODIFYCOMMENTRESPONSEPROTO
_RESPONSEPROTO_RESPONSE.fields_by_name['purchasePostResponse'].message_type = _PURCHASEPOSTRESPONSEPROTO
_RESPONSEPROTO_RESPONSE.fields_by_name['purchaseOrderResponse'].message_type = _PURCHASEORDERRESPONSEPROTO
_RESPONSEPROTO_RESPONSE.fields_by_name['contentSyncResponse'].message_type = _CONTENTSYNCRESPONSEPROTO
_RESPONSEPROTO_RESPONSE.fields_by_name['getAssetResponse'].message_type = _GETASSETRESPONSEPROTO
_RESPONSEPROTO_RESPONSE.fields_by_name['getImageResponse'].message_type = _GETIMAGERESPONSEPROTO
_RESPONSEPROTO_RESPONSE.fields_by_name['refundResponse'].message_type = _REFUNDRESPONSEPROTO
_RESPONSEPROTO_RESPONSE.fields_by_name['purchaseMetadataResponse'].message_type = _PURCHASEMETADATARESPONSEPROTO
_RESPONSEPROTO_RESPONSE.fields_by_name['subCategoriesResponse'].message_type = _GETSUBCATEGORIESRESPONSEPROTO
_RESPONSEPROTO_RESPONSE.fields_by_name['uninstallReasonResponse'].message_type = _UNINSTALLREASONRESPONSEPROTO
_RESPONSEPROTO_RESPONSE.fields_by_name['rateCommentResponse'].message_type = _RATECOMMENTRESPONSEPROTO
_RESPONSEPROTO_RESPONSE.fields_by_name['checkLicenseResponse'].message_type = _CHECKLICENSERESPONSEPROTO
_RESPONSEPROTO_RESPONSE.fields_by_name['getMarketMetadataResponse'].message_type = _GETMARKETMETADATARESPONSEPROTO
_RESPONSEPROTO_RESPONSE.fields_by_name['prefetchedBundle'].message_type = _PREFETCHEDBUNDLEPROTO
_RESPONSEPROTO_RESPONSE.fields_by_name['getCategoriesResponse'].message_type = _GETCATEGORIESRESPONSEPROTO
_RESPONSEPROTO_RESPONSE.fields_by_name['getCarrierInfoResponse'].message_type = _GETCARRIERINFORESPONSEPROTO
_RESPONSEPROTO_RESPONSE.fields_by_name['restoreApplicationResponse'].message_type = _RESTOREAPPLICATIONSRESPONSEPROTO
_RESPONSEPROTO_RESPONSE.fields_by_name['querySuggestionResponse'].message_type = _QUERYSUGGESTIONRESPONSEPROTO
_RESPONSEPROTO_RESPONSE.fields_by_name['billingEventResponse'].message_type = _BILLINGEVENTRESPONSEPROTO
_RESPONSEPROTO_RESPONSE.fields_by_name['paypalPreapprovalResponse'].message_type = _PAYPALPREAPPROVALRESPONSEPROTO
_RESPONSEPROTO_RESPONSE.fields_by_name['paypalPreapprovalDetailsResponse'].message_type = _PAYPALPREAPPROVALDETAILSRESPONSEPROTO
_RESPONSEPROTO_RESPONSE.fields_by_name['paypalCreateAccountResponse'].message_type = _PAYPALCREATEACCOUNTRESPONSEPROTO
_RESPONSEPROTO_RESPONSE.fields_by_name['paypalPreapprovalCredentialsResponse'].message_type = _PAYPALPREAPPROVALCREDENTIALSRESPONSEPROTO
_RESPONSEPROTO_RESPONSE.fields_by_name['inAppRestoreTransactionsResponse'].message_type = _INAPPRESTORETRANSACTIONSRESPONSEPROTO
_RESPONSEPROTO_RESPONSE.fields_by_name['inAppPurchaseInformationResponse'].message_type = _INAPPPURCHASEINFORMATIONRESPONSEPROTO
_RESPONSEPROTO_RESPONSE.fields_by_name['checkForNotificationsResponse'].message_type = _CHECKFORNOTIFICATIONSRESPONSEPROTO
_RESPONSEPROTO_RESPONSE.fields_by_name['ackNotificationsResponse'].message_type = _ACKNOTIFICATIONSRESPONSEPROTO
_RESPONSEPROTO_RESPONSE.fields_by_name['purchaseProductResponse'].message_type = _PURCHASEPRODUCTRESPONSEPROTO
_RESPONSEPROTO_RESPONSE.fields_by_name['reconstructDatabaseResponse'].message_type = _RECONSTRUCTDATABASERESPONSEPROTO
_RESPONSEPROTO_RESPONSE.fields_by_name['paypalMassageAddressResponse'].message_type = _PAYPALMASSAGEADDRESSRESPONSEPROTO
_RESPONSEPROTO_RESPONSE.fields_by_name['getAddressSnippetResponse'].message_type = _GETADDRESSSNIPPETRESPONSEPROTO
_RESPONSEPROTO_RESPONSE.containing_type = _RESPONSEPROTO;
_RESPONSEPROTO.fields_by_name['response'].message_type = _RESPONSEPROTO_RESPONSE
_RESPONSEPROTO.fields_by_name['pendingNotifications'].message_type = _PENDINGNOTIFICATIONSPROTO
_RESTOREAPPLICATIONSREQUESTPROTO.fields_by_name['deviceConfiguration'].message_type = _DEVICECONFIGURATIONPROTO
_RESTOREAPPLICATIONSRESPONSEPROTO.fields_by_name['asset'].message_type = _GETASSETRESPONSEPROTO
_SINGLEREQUESTPROTO.fields_by_name['requestSpecificProperties'].message_type = _REQUESTSPECIFICPROPERTIESPROTO
_SINGLEREQUESTPROTO.fields_by_name['assetRequest'].message_type = _ASSETSREQUESTPROTO
_SINGLEREQUESTPROTO.fields_by_name['commentsRequest'].message_type = _COMMENTSREQUESTPROTO
_SINGLEREQUESTPROTO.fields_by_name['modifyCommentRequest'].message_type = _MODIFYCOMMENTREQUESTPROTO
_SINGLEREQUESTPROTO.fields_by_name['purchasePostRequest'].message_type = _PURCHASEPOSTREQUESTPROTO
_SINGLEREQUESTPROTO.fields_by_name['purchaseOrderRequest'].message_type = _PURCHASEORDERREQUESTPROTO
_SINGLEREQUESTPROTO.fields_by_name['contentSyncRequest'].message_type = _CONTENTSYNCREQUESTPROTO
_SINGLEREQUESTPROTO.fields_by_name['getAssetRequest'].message_type = _GETASSETREQUESTPROTO
_SINGLEREQUESTPROTO.fields_by_name['getImageRequest'].message_type = _GETIMAGEREQUESTPROTO
_SINGLEREQUESTPROTO.fields_by_name['refundRequest'].message_type = _REFUNDREQUESTPROTO
_SINGLEREQUESTPROTO.fields_by_name['purchaseMetadataRequest'].message_type = _PURCHASEMETADATAREQUESTPROTO
_SINGLEREQUESTPROTO.fields_by_name['subCategoriesRequest'].message_type = _GETSUBCATEGORIESREQUESTPROTO
_SINGLEREQUESTPROTO.fields_by_name['uninstallReasonRequest'].message_type = _UNINSTALLREASONREQUESTPROTO
_SINGLEREQUESTPROTO.fields_by_name['rateCommentRequest'].message_type = _RATECOMMENTREQUESTPROTO
_SINGLEREQUESTPROTO.fields_by_name['checkLicenseRequest'].message_type = _CHECKLICENSEREQUESTPROTO
_SINGLEREQUESTPROTO.fields_by_name['getMarketMetadataRequest'].message_type = _GETMARKETMETADATAREQUESTPROTO
_SINGLEREQUESTPROTO.fields_by_name['getCategoriesRequest'].message_type = _GETCATEGORIESREQUESTPROTO
_SINGLEREQUESTPROTO.fields_by_name['getCarrierInfoRequest'].message_type = _GETCARRIERINFOREQUESTPROTO
_SINGLEREQUESTPROTO.fields_by_name['removeAssetRequest'].message_type = _REMOVEASSETREQUESTPROTO
_SINGLEREQUESTPROTO.fields_by_name['restoreApplicationsRequest'].message_type = _RESTOREAPPLICATIONSREQUESTPROTO
_SINGLEREQUESTPROTO.fields_by_name['querySuggestionRequest'].message_type = _QUERYSUGGESTIONREQUESTPROTO
_SINGLEREQUESTPROTO.fields_by_name['billingEventRequest'].message_type = _BILLINGEVENTREQUESTPROTO
_SINGLEREQUESTPROTO.fields_by_name['paypalPreapprovalRequest'].message_type = _PAYPALPREAPPROVALREQUESTPROTO
_SINGLEREQUESTPROTO.fields_by_name['paypalPreapprovalDetailsRequest'].message_type = _PAYPALPREAPPROVALDETAILSREQUESTPROTO
_SINGLEREQUESTPROTO.fields_by_name['paypalCreateAccountRequest'].message_type = _PAYPALCREATEACCOUNTREQUESTPROTO
_SINGLEREQUESTPROTO.fields_by_name['paypalPreapprovalCredentialsRequest'].message_type = _PAYPALPREAPPROVALCREDENTIALSREQUESTPROTO
_SINGLEREQUESTPROTO.fields_by_name['inAppRestoreTransactionsRequest'].message_type = _INAPPRESTORETRANSACTIONSREQUESTPROTO
_SINGLEREQUESTPROTO.fields_by_name['getInAppPurchaseInformationRequest'].message_type = _INAPPPURCHASEINFORMATIONREQUESTPROTO
_SINGLEREQUESTPROTO.fields_by_name['checkForNotificationsRequest'].message_type = _CHECKFORNOTIFICATIONSREQUESTPROTO
_SINGLEREQUESTPROTO.fields_by_name['ackNotificationsRequest'].message_type = _ACKNOTIFICATIONSREQUESTPROTO
_SINGLEREQUESTPROTO.fields_by_name['purchaseProductRequest'].message_type = _PURCHASEPRODUCTREQUESTPROTO
_SINGLEREQUESTPROTO.fields_by_name['reconstructDatabaseRequest'].message_type = _RECONSTRUCTDATABASEREQUESTPROTO
_SINGLEREQUESTPROTO.fields_by_name['paypalMassageAddressRequest'].message_type = _PAYPALMASSAGEADDRESSREQUESTPROTO
_SINGLEREQUESTPROTO.fields_by_name['getAddressSnippetRequest'].message_type = _GETADDRESSSNIPPETREQUESTPROTO
_SINGLERESPONSEPROTO.fields_by_name['responseProperties'].message_type = _RESPONSEPROPERTIESPROTO
_SINGLERESPONSEPROTO.fields_by_name['assetsResponse'].message_type = _ASSETSRESPONSEPROTO
_SINGLERESPONSEPROTO.fields_by_name['commentsResponse'].message_type = _COMMENTSRESPONSEPROTO
_SINGLERESPONSEPROTO.fields_by_name['modifyCommentResponse'].message_type = _MODIFYCOMMENTRESPONSEPROTO
_SINGLERESPONSEPROTO.fields_by_name['purchasePostResponse'].message_type = _PURCHASEPOSTRESPONSEPROTO
_SINGLERESPONSEPROTO.fields_by_name['purchaseOrderResponse'].message_type = _PURCHASEORDERRESPONSEPROTO
_SINGLERESPONSEPROTO.fields_by_name['contentSyncResponse'].message_type = _CONTENTSYNCRESPONSEPROTO
_SINGLERESPONSEPROTO.fields_by_name['getAssetResponse'].message_type = _GETASSETRESPONSEPROTO
_SINGLERESPONSEPROTO.fields_by_name['getImageResponse'].message_type = _GETIMAGERESPONSEPROTO
_SINGLERESPONSEPROTO.fields_by_name['refundResponse'].message_type = _REFUNDRESPONSEPROTO
_SINGLERESPONSEPROTO.fields_by_name['purchaseMetadataResponse'].message_type = _PURCHASEMETADATARESPONSEPROTO
_SINGLERESPONSEPROTO.fields_by_name['subCategoriesResponse'].message_type = _GETSUBCATEGORIESRESPONSEPROTO
_SINGLERESPONSEPROTO.fields_by_name['uninstallReasonResponse'].message_type = _UNINSTALLREASONRESPONSEPROTO
_SINGLERESPONSEPROTO.fields_by_name['rateCommentResponse'].message_type = _RATECOMMENTRESPONSEPROTO
_SINGLERESPONSEPROTO.fields_by_name['checkLicenseResponse'].message_type = _CHECKLICENSERESPONSEPROTO
_SINGLERESPONSEPROTO.fields_by_name['getMarketMetadataResponse'].message_type = _GETMARKETMETADATARESPONSEPROTO
_SINGLERESPONSEPROTO.fields_by_name['getCategoriesResponse'].message_type = _GETCATEGORIESRESPONSEPROTO
_SINGLERESPONSEPROTO.fields_by_name['getCarrierInfoResponse'].message_type = _GETCARRIERINFORESPONSEPROTO
_SINGLERESPONSEPROTO.fields_by_name['restoreApplicationResponse'].message_type = _RESTOREAPPLICATIONSRESPONSEPROTO
_SINGLERESPONSEPROTO.fields_by_name['querySuggestionResponse'].message_type = _QUERYSUGGESTIONRESPONSEPROTO
_SINGLERESPONSEPROTO.fields_by_name['billingEventResponse'].message_type = _BILLINGEVENTRESPONSEPROTO
_SINGLERESPONSEPROTO.fields_by_name['paypalPreapprovalResponse'].message_type = _PAYPALPREAPPROVALRESPONSEPROTO
_SINGLERESPONSEPROTO.fields_by_name['paypalPreapprovalDetailsResponse'].message_type = _PAYPALPREAPPROVALDETAILSRESPONSEPROTO
_SINGLERESPONSEPROTO.fields_by_name['paypalCreateAccountResponse'].message_type = _PAYPALCREATEACCOUNTRESPONSEPROTO
_SINGLERESPONSEPROTO.fields_by_name['paypalPreapprovalCredentialsResponse'].message_type = _PAYPALPREAPPROVALCREDENTIALSRESPONSEPROTO
_SINGLERESPONSEPROTO.fields_by_name['inAppRestoreTransactionsResponse'].message_type = _INAPPRESTORETRANSACTIONSRESPONSEPROTO
_SINGLERESPONSEPROTO.fields_by_name['getInAppPurchaseInformationResponse'].message_type = _INAPPPURCHASEINFORMATIONRESPONSEPROTO
_SINGLERESPONSEPROTO.fields_by_name['checkForNotificationsResponse'].message_type = _CHECKFORNOTIFICATIONSRESPONSEPROTO
_SINGLERESPONSEPROTO.fields_by_name['ackNotificationsResponse'].message_type = _ACKNOTIFICATIONSRESPONSEPROTO
_SINGLERESPONSEPROTO.fields_by_name['purchaseProductResponse'].message_type = _PURCHASEPRODUCTRESPONSEPROTO
_SINGLERESPONSEPROTO.fields_by_name['reconstructDatabaseResponse'].message_type = _RECONSTRUCTDATABASERESPONSEPROTO
_SINGLERESPONSEPROTO.fields_by_name['paypalMassageAddressResponse'].message_type = _PAYPALMASSAGEADDRESSRESPONSEPROTO
_SINGLERESPONSEPROTO.fields_by_name['getAddressSnippetResponse'].message_type = _GETADDRESSSNIPPETRESPONSEPROTO

class AckNotificationResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _ACKNOTIFICATIONRESPONSE
  
  # @@protoc_insertion_point(class_scope:AckNotificationResponse)

class AndroidAppDeliveryData(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _ANDROIDAPPDELIVERYDATA
  
  # @@protoc_insertion_point(class_scope:AndroidAppDeliveryData)

class AndroidAppPatchData(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _ANDROIDAPPPATCHDATA
  
  # @@protoc_insertion_point(class_scope:AndroidAppPatchData)

class AppFileMetadata(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _APPFILEMETADATA
  
  # @@protoc_insertion_point(class_scope:AppFileMetadata)

class EncryptionParams(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _ENCRYPTIONPARAMS
  
  # @@protoc_insertion_point(class_scope:EncryptionParams)

class HttpCookie(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _HTTPCOOKIE
  
  # @@protoc_insertion_point(class_scope:HttpCookie)

class Address(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _ADDRESS
  
  # @@protoc_insertion_point(class_scope:Address)

class BookAuthor(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _BOOKAUTHOR
  
  # @@protoc_insertion_point(class_scope:BookAuthor)

class BookDetails(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  
  class Identifier(message.Message):
    __metaclass__ = reflection.GeneratedProtocolMessageType
    DESCRIPTOR = _BOOKDETAILS_IDENTIFIER
    
    # @@protoc_insertion_point(class_scope:BookDetails.Identifier)
  DESCRIPTOR = _BOOKDETAILS
  
  # @@protoc_insertion_point(class_scope:BookDetails)

class BookSubject(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _BOOKSUBJECT
  
  # @@protoc_insertion_point(class_scope:BookSubject)

class BrowseLink(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _BROWSELINK
  
  # @@protoc_insertion_point(class_scope:BrowseLink)

class BrowseResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _BROWSERESPONSE
  
  # @@protoc_insertion_point(class_scope:BrowseResponse)

class AddressChallenge(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _ADDRESSCHALLENGE
  
  # @@protoc_insertion_point(class_scope:AddressChallenge)

class AuthenticationChallenge(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _AUTHENTICATIONCHALLENGE
  
  # @@protoc_insertion_point(class_scope:AuthenticationChallenge)

class BuyResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  
  class CheckoutInfo(message.Message):
    __metaclass__ = reflection.GeneratedProtocolMessageType
    
    class CheckoutOption(message.Message):
      __metaclass__ = reflection.GeneratedProtocolMessageType
      DESCRIPTOR = _BUYRESPONSE_CHECKOUTINFO_CHECKOUTOPTION
      
      # @@protoc_insertion_point(class_scope:BuyResponse.CheckoutInfo.CheckoutOption)
    DESCRIPTOR = _BUYRESPONSE_CHECKOUTINFO
    
    # @@protoc_insertion_point(class_scope:BuyResponse.CheckoutInfo)
  DESCRIPTOR = _BUYRESPONSE
  
  # @@protoc_insertion_point(class_scope:BuyResponse)

class Challenge(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _CHALLENGE
  
  # @@protoc_insertion_point(class_scope:Challenge)

class FormCheckbox(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _FORMCHECKBOX
  
  # @@protoc_insertion_point(class_scope:FormCheckbox)

class LineItem(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _LINEITEM
  
  # @@protoc_insertion_point(class_scope:LineItem)

class Money(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _MONEY
  
  # @@protoc_insertion_point(class_scope:Money)

class PurchaseNotificationResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PURCHASENOTIFICATIONRESPONSE
  
  # @@protoc_insertion_point(class_scope:PurchaseNotificationResponse)

class PurchaseStatusResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PURCHASESTATUSRESPONSE
  
  # @@protoc_insertion_point(class_scope:PurchaseStatusResponse)

class CheckInstrumentResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _CHECKINSTRUMENTRESPONSE
  
  # @@protoc_insertion_point(class_scope:CheckInstrumentResponse)

class UpdateInstrumentRequest(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _UPDATEINSTRUMENTREQUEST
  
  # @@protoc_insertion_point(class_scope:UpdateInstrumentRequest)

class UpdateInstrumentResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _UPDATEINSTRUMENTRESPONSE
  
  # @@protoc_insertion_point(class_scope:UpdateInstrumentResponse)

class InitiateAssociationResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _INITIATEASSOCIATIONRESPONSE
  
  # @@protoc_insertion_point(class_scope:InitiateAssociationResponse)

class VerifyAssociationResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _VERIFYASSOCIATIONRESPONSE
  
  # @@protoc_insertion_point(class_scope:VerifyAssociationResponse)

class AddCreditCardPromoOffer(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _ADDCREDITCARDPROMOOFFER
  
  # @@protoc_insertion_point(class_scope:AddCreditCardPromoOffer)

class AvailablePromoOffer(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _AVAILABLEPROMOOFFER
  
  # @@protoc_insertion_point(class_scope:AvailablePromoOffer)

class CheckPromoOfferResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _CHECKPROMOOFFERRESPONSE
  
  # @@protoc_insertion_point(class_scope:CheckPromoOfferResponse)

class RedeemedPromoOffer(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _REDEEMEDPROMOOFFER
  
  # @@protoc_insertion_point(class_scope:RedeemedPromoOffer)

class Docid(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _DOCID
  
  # @@protoc_insertion_point(class_scope:Docid)

class Install(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _INSTALL
  
  # @@protoc_insertion_point(class_scope:Install)

class Offer(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _OFFER
  
  # @@protoc_insertion_point(class_scope:Offer)

class OwnershipInfo(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _OWNERSHIPINFO
  
  # @@protoc_insertion_point(class_scope:OwnershipInfo)

class RentalTerms(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _RENTALTERMS
  
  # @@protoc_insertion_point(class_scope:RentalTerms)

class SubscriptionTerms(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _SUBSCRIPTIONTERMS
  
  # @@protoc_insertion_point(class_scope:SubscriptionTerms)

class TimePeriod(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _TIMEPERIOD
  
  # @@protoc_insertion_point(class_scope:TimePeriod)

class BillingAddressSpec(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _BILLINGADDRESSSPEC
  
  # @@protoc_insertion_point(class_scope:BillingAddressSpec)

class CarrierBillingCredentials(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _CARRIERBILLINGCREDENTIALS
  
  # @@protoc_insertion_point(class_scope:CarrierBillingCredentials)

class CarrierBillingInstrument(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _CARRIERBILLINGINSTRUMENT
  
  # @@protoc_insertion_point(class_scope:CarrierBillingInstrument)

class CarrierBillingInstrumentStatus(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _CARRIERBILLINGINSTRUMENTSTATUS
  
  # @@protoc_insertion_point(class_scope:CarrierBillingInstrumentStatus)

class CarrierTos(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _CARRIERTOS
  
  # @@protoc_insertion_point(class_scope:CarrierTos)

class CarrierTosEntry(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _CARRIERTOSENTRY
  
  # @@protoc_insertion_point(class_scope:CarrierTosEntry)

class CreditCardInstrument(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _CREDITCARDINSTRUMENT
  
  # @@protoc_insertion_point(class_scope:CreditCardInstrument)

class EfeParam(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _EFEPARAM
  
  # @@protoc_insertion_point(class_scope:EfeParam)

class InputValidationError(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _INPUTVALIDATIONERROR
  
  # @@protoc_insertion_point(class_scope:InputValidationError)

class Instrument(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _INSTRUMENT
  
  # @@protoc_insertion_point(class_scope:Instrument)

class PasswordPrompt(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PASSWORDPROMPT
  
  # @@protoc_insertion_point(class_scope:PasswordPrompt)

class ContainerMetadata(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _CONTAINERMETADATA
  
  # @@protoc_insertion_point(class_scope:ContainerMetadata)

class FlagContentResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _FLAGCONTENTRESPONSE
  
  # @@protoc_insertion_point(class_scope:FlagContentResponse)

class DebugInfo(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  
  class Timing(message.Message):
    __metaclass__ = reflection.GeneratedProtocolMessageType
    DESCRIPTOR = _DEBUGINFO_TIMING
    
    # @@protoc_insertion_point(class_scope:DebugInfo.Timing)
  DESCRIPTOR = _DEBUGINFO
  
  # @@protoc_insertion_point(class_scope:DebugInfo)

class DeliveryResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _DELIVERYRESPONSE
  
  # @@protoc_insertion_point(class_scope:DeliveryResponse)

class BulkDetailsEntry(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _BULKDETAILSENTRY
  
  # @@protoc_insertion_point(class_scope:BulkDetailsEntry)

class BulkDetailsRequest(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _BULKDETAILSREQUEST
  
  # @@protoc_insertion_point(class_scope:BulkDetailsRequest)

class BulkDetailsResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _BULKDETAILSRESPONSE
  
  # @@protoc_insertion_point(class_scope:BulkDetailsResponse)

class DetailsResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _DETAILSRESPONSE
  
  # @@protoc_insertion_point(class_scope:DetailsResponse)

class DeviceConfigurationProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _DEVICECONFIGURATIONPROTO
  
  # @@protoc_insertion_point(class_scope:DeviceConfigurationProto)

class Document(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _DOCUMENT
  
  # @@protoc_insertion_point(class_scope:Document)

class DocumentVariant(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _DOCUMENTVARIANT
  
  # @@protoc_insertion_point(class_scope:DocumentVariant)

class Image(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  
  class Dimension(message.Message):
    __metaclass__ = reflection.GeneratedProtocolMessageType
    DESCRIPTOR = _IMAGE_DIMENSION
    
    # @@protoc_insertion_point(class_scope:Image.Dimension)
  
  class Citation(message.Message):
    __metaclass__ = reflection.GeneratedProtocolMessageType
    DESCRIPTOR = _IMAGE_CITATION
    
    # @@protoc_insertion_point(class_scope:Image.Citation)
  DESCRIPTOR = _IMAGE
  
  # @@protoc_insertion_point(class_scope:Image)

class TranslatedText(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _TRANSLATEDTEXT
  
  # @@protoc_insertion_point(class_scope:TranslatedText)

class Badge(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _BADGE
  
  # @@protoc_insertion_point(class_scope:Badge)

class ContainerWithBanner(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _CONTAINERWITHBANNER
  
  # @@protoc_insertion_point(class_scope:ContainerWithBanner)

class DealOfTheDay(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _DEALOFTHEDAY
  
  # @@protoc_insertion_point(class_scope:DealOfTheDay)

class EditorialSeriesContainer(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _EDITORIALSERIESCONTAINER
  
  # @@protoc_insertion_point(class_scope:EditorialSeriesContainer)

class Link(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _LINK
  
  # @@protoc_insertion_point(class_scope:Link)

class PlusOneData(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PLUSONEDATA
  
  # @@protoc_insertion_point(class_scope:PlusOneData)

class PlusPerson(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PLUSPERSON
  
  # @@protoc_insertion_point(class_scope:PlusPerson)

class PromotedDoc(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PROMOTEDDOC
  
  # @@protoc_insertion_point(class_scope:PromotedDoc)

class Reason(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _REASON
  
  # @@protoc_insertion_point(class_scope:Reason)

class SectionMetadata(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _SECTIONMETADATA
  
  # @@protoc_insertion_point(class_scope:SectionMetadata)

class SeriesAntenna(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _SERIESANTENNA
  
  # @@protoc_insertion_point(class_scope:SeriesAntenna)

class Template(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _TEMPLATE
  
  # @@protoc_insertion_point(class_scope:Template)

class TileTemplate(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _TILETEMPLATE
  
  # @@protoc_insertion_point(class_scope:TileTemplate)

class Warning(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _WARNING
  
  # @@protoc_insertion_point(class_scope:Warning)

class AlbumDetails(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _ALBUMDETAILS
  
  # @@protoc_insertion_point(class_scope:AlbumDetails)

class AppDetails(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _APPDETAILS
  
  # @@protoc_insertion_point(class_scope:AppDetails)

class ArtistDetails(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _ARTISTDETAILS
  
  # @@protoc_insertion_point(class_scope:ArtistDetails)

class ArtistExternalLinks(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _ARTISTEXTERNALLINKS
  
  # @@protoc_insertion_point(class_scope:ArtistExternalLinks)

class DocumentDetails(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _DOCUMENTDETAILS
  
  # @@protoc_insertion_point(class_scope:DocumentDetails)

class FileMetadata(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _FILEMETADATA
  
  # @@protoc_insertion_point(class_scope:FileMetadata)

class MagazineDetails(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _MAGAZINEDETAILS
  
  # @@protoc_insertion_point(class_scope:MagazineDetails)

class MusicDetails(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _MUSICDETAILS
  
  # @@protoc_insertion_point(class_scope:MusicDetails)

class SongDetails(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _SONGDETAILS
  
  # @@protoc_insertion_point(class_scope:SongDetails)

class SubscriptionDetails(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _SUBSCRIPTIONDETAILS
  
  # @@protoc_insertion_point(class_scope:SubscriptionDetails)

class Trailer(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _TRAILER
  
  # @@protoc_insertion_point(class_scope:Trailer)

class TvEpisodeDetails(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _TVEPISODEDETAILS
  
  # @@protoc_insertion_point(class_scope:TvEpisodeDetails)

class TvSeasonDetails(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _TVSEASONDETAILS
  
  # @@protoc_insertion_point(class_scope:TvSeasonDetails)

class TvShowDetails(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _TVSHOWDETAILS
  
  # @@protoc_insertion_point(class_scope:TvShowDetails)

class VideoCredit(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _VIDEOCREDIT
  
  # @@protoc_insertion_point(class_scope:VideoCredit)

class VideoDetails(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _VIDEODETAILS
  
  # @@protoc_insertion_point(class_scope:VideoDetails)

class VideoRentalTerm(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  
  class Term(message.Message):
    __metaclass__ = reflection.GeneratedProtocolMessageType
    DESCRIPTOR = _VIDEORENTALTERM_TERM
    
    # @@protoc_insertion_point(class_scope:VideoRentalTerm.Term)
  DESCRIPTOR = _VIDEORENTALTERM
  
  # @@protoc_insertion_point(class_scope:VideoRentalTerm)

class Bucket(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _BUCKET
  
  # @@protoc_insertion_point(class_scope:Bucket)

class ListResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _LISTRESPONSE
  
  # @@protoc_insertion_point(class_scope:ListResponse)

class DocV1(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _DOCV1
  
  # @@protoc_insertion_point(class_scope:DocV1)

class Annotations(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _ANNOTATIONS
  
  # @@protoc_insertion_point(class_scope:Annotations)

class DocV2(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _DOCV2
  
  # @@protoc_insertion_point(class_scope:DocV2)

class EncryptedSubscriberInfo(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _ENCRYPTEDSUBSCRIBERINFO
  
  # @@protoc_insertion_point(class_scope:EncryptedSubscriberInfo)

class Availability(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  
  class PerDeviceAvailabilityRestriction(message.Message):
    __metaclass__ = reflection.GeneratedProtocolMessageType
    DESCRIPTOR = _AVAILABILITY_PERDEVICEAVAILABILITYRESTRICTION
    
    # @@protoc_insertion_point(class_scope:Availability.PerDeviceAvailabilityRestriction)
  DESCRIPTOR = _AVAILABILITY
  
  # @@protoc_insertion_point(class_scope:Availability)

class FilterEvaluationInfo(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _FILTEREVALUATIONINFO
  
  # @@protoc_insertion_point(class_scope:FilterEvaluationInfo)

class Rule(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _RULE
  
  # @@protoc_insertion_point(class_scope:Rule)

class RuleEvaluation(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _RULEEVALUATION
  
  # @@protoc_insertion_point(class_scope:RuleEvaluation)

class LibraryAppDetails(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _LIBRARYAPPDETAILS
  
  # @@protoc_insertion_point(class_scope:LibraryAppDetails)

class LibraryMutation(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _LIBRARYMUTATION
  
  # @@protoc_insertion_point(class_scope:LibraryMutation)

class LibrarySubscriptionDetails(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _LIBRARYSUBSCRIPTIONDETAILS
  
  # @@protoc_insertion_point(class_scope:LibrarySubscriptionDetails)

class LibraryUpdate(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _LIBRARYUPDATE
  
  # @@protoc_insertion_point(class_scope:LibraryUpdate)

class ClientLibraryState(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _CLIENTLIBRARYSTATE
  
  # @@protoc_insertion_point(class_scope:ClientLibraryState)

class LibraryReplicationRequest(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _LIBRARYREPLICATIONREQUEST
  
  # @@protoc_insertion_point(class_scope:LibraryReplicationRequest)

class LibraryReplicationResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _LIBRARYREPLICATIONRESPONSE
  
  # @@protoc_insertion_point(class_scope:LibraryReplicationResponse)

class ClickLogEvent(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _CLICKLOGEVENT
  
  # @@protoc_insertion_point(class_scope:ClickLogEvent)

class LogRequest(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _LOGREQUEST
  
  # @@protoc_insertion_point(class_scope:LogRequest)

class LogResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _LOGRESPONSE
  
  # @@protoc_insertion_point(class_scope:LogResponse)

class AndroidAppNotificationData(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _ANDROIDAPPNOTIFICATIONDATA
  
  # @@protoc_insertion_point(class_scope:AndroidAppNotificationData)

class InAppNotificationData(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _INAPPNOTIFICATIONDATA
  
  # @@protoc_insertion_point(class_scope:InAppNotificationData)

class LibraryDirtyData(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _LIBRARYDIRTYDATA
  
  # @@protoc_insertion_point(class_scope:LibraryDirtyData)

class Notification(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _NOTIFICATION
  
  # @@protoc_insertion_point(class_scope:Notification)

class PurchaseDeclinedData(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PURCHASEDECLINEDDATA
  
  # @@protoc_insertion_point(class_scope:PurchaseDeclinedData)

class PurchaseRemovalData(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PURCHASEREMOVALDATA
  
  # @@protoc_insertion_point(class_scope:PurchaseRemovalData)

class UserNotificationData(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _USERNOTIFICATIONDATA
  
  # @@protoc_insertion_point(class_scope:UserNotificationData)

class PlusOneResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PLUSONERESPONSE
  
  # @@protoc_insertion_point(class_scope:PlusOneResponse)

class RateSuggestedContentResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _RATESUGGESTEDCONTENTRESPONSE
  
  # @@protoc_insertion_point(class_scope:RateSuggestedContentResponse)

class AggregateRating(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _AGGREGATERATING
  
  # @@protoc_insertion_point(class_scope:AggregateRating)

class DirectPurchase(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _DIRECTPURCHASE
  
  # @@protoc_insertion_point(class_scope:DirectPurchase)

class ResolveLinkResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _RESOLVELINKRESPONSE
  
  # @@protoc_insertion_point(class_scope:ResolveLinkResponse)

class Payload(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PAYLOAD
  
  # @@protoc_insertion_point(class_scope:Payload)

class PreFetch(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PREFETCH
  
  # @@protoc_insertion_point(class_scope:PreFetch)

class ResponseWrapper(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _RESPONSEWRAPPER
  
  # @@protoc_insertion_point(class_scope:ResponseWrapper)

class ServerCommands(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _SERVERCOMMANDS
  
  # @@protoc_insertion_point(class_scope:ServerCommands)

class GetReviewsResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _GETREVIEWSRESPONSE
  
  # @@protoc_insertion_point(class_scope:GetReviewsResponse)

class Review(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _REVIEW
  
  # @@protoc_insertion_point(class_scope:Review)

class ReviewResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _REVIEWRESPONSE
  
  # @@protoc_insertion_point(class_scope:ReviewResponse)

class RevokeResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _REVOKERESPONSE
  
  # @@protoc_insertion_point(class_scope:RevokeResponse)

class RelatedSearch(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _RELATEDSEARCH
  
  # @@protoc_insertion_point(class_scope:RelatedSearch)

class SearchResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _SEARCHRESPONSE
  
  # @@protoc_insertion_point(class_scope:SearchResponse)

class CorpusMetadata(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _CORPUSMETADATA
  
  # @@protoc_insertion_point(class_scope:CorpusMetadata)

class Experiments(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _EXPERIMENTS
  
  # @@protoc_insertion_point(class_scope:Experiments)

class TocResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _TOCRESPONSE
  
  # @@protoc_insertion_point(class_scope:TocResponse)

class UserSettings(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _USERSETTINGS
  
  # @@protoc_insertion_point(class_scope:UserSettings)

class AcceptTosResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _ACCEPTTOSRESPONSE
  
  # @@protoc_insertion_point(class_scope:AcceptTosResponse)

class AckNotificationsRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _ACKNOTIFICATIONSREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:AckNotificationsRequestProto)

class AckNotificationsResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _ACKNOTIFICATIONSRESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:AckNotificationsResponseProto)

class AddressProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _ADDRESSPROTO
  
  # @@protoc_insertion_point(class_scope:AddressProto)

class AppDataProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _APPDATAPROTO
  
  # @@protoc_insertion_point(class_scope:AppDataProto)

class AppSuggestionProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _APPSUGGESTIONPROTO
  
  # @@protoc_insertion_point(class_scope:AppSuggestionProto)

class AssetIdentifierProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _ASSETIDENTIFIERPROTO
  
  # @@protoc_insertion_point(class_scope:AssetIdentifierProto)

class AssetsRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _ASSETSREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:AssetsRequestProto)

class AssetsResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _ASSETSRESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:AssetsResponseProto)

class BillingEventRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _BILLINGEVENTREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:BillingEventRequestProto)

class BillingEventResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _BILLINGEVENTRESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:BillingEventResponseProto)

class BillingParameterProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _BILLINGPARAMETERPROTO
  
  # @@protoc_insertion_point(class_scope:BillingParameterProto)

class CarrierBillingCredentialsProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _CARRIERBILLINGCREDENTIALSPROTO
  
  # @@protoc_insertion_point(class_scope:CarrierBillingCredentialsProto)

class CategoryProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _CATEGORYPROTO
  
  # @@protoc_insertion_point(class_scope:CategoryProto)

class CheckForNotificationsRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _CHECKFORNOTIFICATIONSREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:CheckForNotificationsRequestProto)

class CheckForNotificationsResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _CHECKFORNOTIFICATIONSRESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:CheckForNotificationsResponseProto)

class CheckLicenseRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _CHECKLICENSEREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:CheckLicenseRequestProto)

class CheckLicenseResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _CHECKLICENSERESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:CheckLicenseResponseProto)

class CommentsRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _COMMENTSREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:CommentsRequestProto)

class CommentsResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _COMMENTSRESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:CommentsResponseProto)

class ContentSyncRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  
  class AssetInstallState(message.Message):
    __metaclass__ = reflection.GeneratedProtocolMessageType
    DESCRIPTOR = _CONTENTSYNCREQUESTPROTO_ASSETINSTALLSTATE
    
    # @@protoc_insertion_point(class_scope:ContentSyncRequestProto.AssetInstallState)
  
  class SystemApp(message.Message):
    __metaclass__ = reflection.GeneratedProtocolMessageType
    DESCRIPTOR = _CONTENTSYNCREQUESTPROTO_SYSTEMAPP
    
    # @@protoc_insertion_point(class_scope:ContentSyncRequestProto.SystemApp)
  DESCRIPTOR = _CONTENTSYNCREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:ContentSyncRequestProto)

class ContentSyncResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _CONTENTSYNCRESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:ContentSyncResponseProto)

class DataMessageProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _DATAMESSAGEPROTO
  
  # @@protoc_insertion_point(class_scope:DataMessageProto)

class DownloadInfoProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _DOWNLOADINFOPROTO
  
  # @@protoc_insertion_point(class_scope:DownloadInfoProto)

class ExternalAssetProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  
  class PurchaseInformation(message.Message):
    __metaclass__ = reflection.GeneratedProtocolMessageType
    DESCRIPTOR = _EXTERNALASSETPROTO_PURCHASEINFORMATION
    
    # @@protoc_insertion_point(class_scope:ExternalAssetProto.PurchaseInformation)
  
  class ExtendedInfo(message.Message):
    __metaclass__ = reflection.GeneratedProtocolMessageType
    
    class PackageDependency(message.Message):
      __metaclass__ = reflection.GeneratedProtocolMessageType
      DESCRIPTOR = _EXTERNALASSETPROTO_EXTENDEDINFO_PACKAGEDEPENDENCY
      
      # @@protoc_insertion_point(class_scope:ExternalAssetProto.ExtendedInfo.PackageDependency)
    DESCRIPTOR = _EXTERNALASSETPROTO_EXTENDEDINFO
    
    # @@protoc_insertion_point(class_scope:ExternalAssetProto.ExtendedInfo)
  DESCRIPTOR = _EXTERNALASSETPROTO
  
  # @@protoc_insertion_point(class_scope:ExternalAssetProto)

class ExternalBadgeImageProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _EXTERNALBADGEIMAGEPROTO
  
  # @@protoc_insertion_point(class_scope:ExternalBadgeImageProto)

class ExternalBadgeProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _EXTERNALBADGEPROTO
  
  # @@protoc_insertion_point(class_scope:ExternalBadgeProto)

class ExternalCarrierBillingInstrumentProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _EXTERNALCARRIERBILLINGINSTRUMENTPROTO
  
  # @@protoc_insertion_point(class_scope:ExternalCarrierBillingInstrumentProto)

class ExternalCommentProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _EXTERNALCOMMENTPROTO
  
  # @@protoc_insertion_point(class_scope:ExternalCommentProto)

class ExternalCreditCard(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _EXTERNALCREDITCARD
  
  # @@protoc_insertion_point(class_scope:ExternalCreditCard)

class ExternalPaypalInstrumentProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _EXTERNALPAYPALINSTRUMENTPROTO
  
  # @@protoc_insertion_point(class_scope:ExternalPaypalInstrumentProto)

class FileMetadataProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _FILEMETADATAPROTO
  
  # @@protoc_insertion_point(class_scope:FileMetadataProto)

class GetAddressSnippetRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _GETADDRESSSNIPPETREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:GetAddressSnippetRequestProto)

class GetAddressSnippetResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _GETADDRESSSNIPPETRESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:GetAddressSnippetResponseProto)

class GetAssetRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _GETASSETREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:GetAssetRequestProto)

class GetAssetResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  
  class InstallAsset(message.Message):
    __metaclass__ = reflection.GeneratedProtocolMessageType
    DESCRIPTOR = _GETASSETRESPONSEPROTO_INSTALLASSET
    
    # @@protoc_insertion_point(class_scope:GetAssetResponseProto.InstallAsset)
  DESCRIPTOR = _GETASSETRESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:GetAssetResponseProto)

class GetCarrierInfoRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _GETCARRIERINFOREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:GetCarrierInfoRequestProto)

class GetCarrierInfoResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _GETCARRIERINFORESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:GetCarrierInfoResponseProto)

class GetCategoriesRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _GETCATEGORIESREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:GetCategoriesRequestProto)

class GetCategoriesResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _GETCATEGORIESRESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:GetCategoriesResponseProto)

class GetImageRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _GETIMAGEREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:GetImageRequestProto)

class GetImageResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _GETIMAGERESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:GetImageResponseProto)

class GetMarketMetadataRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _GETMARKETMETADATAREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:GetMarketMetadataRequestProto)

class GetMarketMetadataResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _GETMARKETMETADATARESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:GetMarketMetadataResponseProto)

class GetSubCategoriesRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _GETSUBCATEGORIESREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:GetSubCategoriesRequestProto)

class GetSubCategoriesResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  
  class SubCategory(message.Message):
    __metaclass__ = reflection.GeneratedProtocolMessageType
    DESCRIPTOR = _GETSUBCATEGORIESRESPONSEPROTO_SUBCATEGORY
    
    # @@protoc_insertion_point(class_scope:GetSubCategoriesResponseProto.SubCategory)
  DESCRIPTOR = _GETSUBCATEGORIESRESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:GetSubCategoriesResponseProto)

class InAppPurchaseInformationRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _INAPPPURCHASEINFORMATIONREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:InAppPurchaseInformationRequestProto)

class InAppPurchaseInformationResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _INAPPPURCHASEINFORMATIONRESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:InAppPurchaseInformationResponseProto)

class InAppRestoreTransactionsRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _INAPPRESTORETRANSACTIONSREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:InAppRestoreTransactionsRequestProto)

class InAppRestoreTransactionsResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _INAPPRESTORETRANSACTIONSRESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:InAppRestoreTransactionsResponseProto)

class ModifyCommentRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _MODIFYCOMMENTREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:ModifyCommentRequestProto)

class ModifyCommentResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _MODIFYCOMMENTRESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:ModifyCommentResponseProto)

class PaypalCountryInfoProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PAYPALCOUNTRYINFOPROTO
  
  # @@protoc_insertion_point(class_scope:PaypalCountryInfoProto)

class PaypalCreateAccountRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PAYPALCREATEACCOUNTREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:PaypalCreateAccountRequestProto)

class PaypalCreateAccountResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PAYPALCREATEACCOUNTRESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:PaypalCreateAccountResponseProto)

class PaypalCredentialsProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PAYPALCREDENTIALSPROTO
  
  # @@protoc_insertion_point(class_scope:PaypalCredentialsProto)

class PaypalMassageAddressRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PAYPALMASSAGEADDRESSREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:PaypalMassageAddressRequestProto)

class PaypalMassageAddressResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PAYPALMASSAGEADDRESSRESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:PaypalMassageAddressResponseProto)

class PaypalPreapprovalCredentialsRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PAYPALPREAPPROVALCREDENTIALSREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:PaypalPreapprovalCredentialsRequestProto)

class PaypalPreapprovalCredentialsResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PAYPALPREAPPROVALCREDENTIALSRESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:PaypalPreapprovalCredentialsResponseProto)

class PaypalPreapprovalDetailsRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PAYPALPREAPPROVALDETAILSREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:PaypalPreapprovalDetailsRequestProto)

class PaypalPreapprovalDetailsResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PAYPALPREAPPROVALDETAILSRESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:PaypalPreapprovalDetailsResponseProto)

class PaypalPreapprovalRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PAYPALPREAPPROVALREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:PaypalPreapprovalRequestProto)

class PaypalPreapprovalResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PAYPALPREAPPROVALRESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:PaypalPreapprovalResponseProto)

class PendingNotificationsProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PENDINGNOTIFICATIONSPROTO
  
  # @@protoc_insertion_point(class_scope:PendingNotificationsProto)

class PrefetchedBundleProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PREFETCHEDBUNDLEPROTO
  
  # @@protoc_insertion_point(class_scope:PrefetchedBundleProto)

class PurchaseCartInfoProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PURCHASECARTINFOPROTO
  
  # @@protoc_insertion_point(class_scope:PurchaseCartInfoProto)

class PurchaseInfoProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  
  class BillingInstruments(message.Message):
    __metaclass__ = reflection.GeneratedProtocolMessageType
    
    class BillingInstrument(message.Message):
      __metaclass__ = reflection.GeneratedProtocolMessageType
      DESCRIPTOR = _PURCHASEINFOPROTO_BILLINGINSTRUMENTS_BILLINGINSTRUMENT
      
      # @@protoc_insertion_point(class_scope:PurchaseInfoProto.BillingInstruments.BillingInstrument)
    DESCRIPTOR = _PURCHASEINFOPROTO_BILLINGINSTRUMENTS
    
    # @@protoc_insertion_point(class_scope:PurchaseInfoProto.BillingInstruments)
  DESCRIPTOR = _PURCHASEINFOPROTO
  
  # @@protoc_insertion_point(class_scope:PurchaseInfoProto)

class PurchaseMetadataRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PURCHASEMETADATAREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:PurchaseMetadataRequestProto)

class PurchaseMetadataResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  
  class Countries(message.Message):
    __metaclass__ = reflection.GeneratedProtocolMessageType
    
    class Country(message.Message):
      __metaclass__ = reflection.GeneratedProtocolMessageType
      
      class InstrumentAddressSpec(message.Message):
        __metaclass__ = reflection.GeneratedProtocolMessageType
        DESCRIPTOR = _PURCHASEMETADATARESPONSEPROTO_COUNTRIES_COUNTRY_INSTRUMENTADDRESSSPEC
        
        # @@protoc_insertion_point(class_scope:PurchaseMetadataResponseProto.Countries.Country.InstrumentAddressSpec)
      DESCRIPTOR = _PURCHASEMETADATARESPONSEPROTO_COUNTRIES_COUNTRY
      
      # @@protoc_insertion_point(class_scope:PurchaseMetadataResponseProto.Countries.Country)
    DESCRIPTOR = _PURCHASEMETADATARESPONSEPROTO_COUNTRIES
    
    # @@protoc_insertion_point(class_scope:PurchaseMetadataResponseProto.Countries)
  DESCRIPTOR = _PURCHASEMETADATARESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:PurchaseMetadataResponseProto)

class PurchaseOrderRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PURCHASEORDERREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:PurchaseOrderRequestProto)

class PurchaseOrderResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PURCHASEORDERRESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:PurchaseOrderResponseProto)

class PurchasePostRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  
  class BillingInstrumentInfo(message.Message):
    __metaclass__ = reflection.GeneratedProtocolMessageType
    DESCRIPTOR = _PURCHASEPOSTREQUESTPROTO_BILLINGINSTRUMENTINFO
    
    # @@protoc_insertion_point(class_scope:PurchasePostRequestProto.BillingInstrumentInfo)
  DESCRIPTOR = _PURCHASEPOSTREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:PurchasePostRequestProto)

class PurchasePostResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PURCHASEPOSTRESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:PurchasePostResponseProto)

class PurchaseProductRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PURCHASEPRODUCTREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:PurchaseProductRequestProto)

class PurchaseProductResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PURCHASEPRODUCTRESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:PurchaseProductResponseProto)

class PurchaseResultProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PURCHASERESULTPROTO
  
  # @@protoc_insertion_point(class_scope:PurchaseResultProto)

class QuerySuggestionProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _QUERYSUGGESTIONPROTO
  
  # @@protoc_insertion_point(class_scope:QuerySuggestionProto)

class QuerySuggestionRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _QUERYSUGGESTIONREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:QuerySuggestionRequestProto)

class QuerySuggestionResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  
  class Suggestion(message.Message):
    __metaclass__ = reflection.GeneratedProtocolMessageType
    DESCRIPTOR = _QUERYSUGGESTIONRESPONSEPROTO_SUGGESTION
    
    # @@protoc_insertion_point(class_scope:QuerySuggestionResponseProto.Suggestion)
  DESCRIPTOR = _QUERYSUGGESTIONRESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:QuerySuggestionResponseProto)

class RateCommentRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _RATECOMMENTREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:RateCommentRequestProto)

class RateCommentResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _RATECOMMENTRESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:RateCommentResponseProto)

class ReconstructDatabaseRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _RECONSTRUCTDATABASEREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:ReconstructDatabaseRequestProto)

class ReconstructDatabaseResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _RECONSTRUCTDATABASERESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:ReconstructDatabaseResponseProto)

class RefundRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _REFUNDREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:RefundRequestProto)

class RefundResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _REFUNDRESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:RefundResponseProto)

class RemoveAssetRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _REMOVEASSETREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:RemoveAssetRequestProto)

class RequestPropertiesProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _REQUESTPROPERTIESPROTO
  
  # @@protoc_insertion_point(class_scope:RequestPropertiesProto)

class RequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  
  class Request(message.Message):
    __metaclass__ = reflection.GeneratedProtocolMessageType
    DESCRIPTOR = _REQUESTPROTO_REQUEST
    
    # @@protoc_insertion_point(class_scope:RequestProto.Request)
  DESCRIPTOR = _REQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:RequestProto)

class RequestSpecificPropertiesProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _REQUESTSPECIFICPROPERTIESPROTO
  
  # @@protoc_insertion_point(class_scope:RequestSpecificPropertiesProto)

class ResponsePropertiesProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _RESPONSEPROPERTIESPROTO
  
  # @@protoc_insertion_point(class_scope:ResponsePropertiesProto)

class ResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  
  class Response(message.Message):
    __metaclass__ = reflection.GeneratedProtocolMessageType
    DESCRIPTOR = _RESPONSEPROTO_RESPONSE
    
    # @@protoc_insertion_point(class_scope:ResponseProto.Response)
  DESCRIPTOR = _RESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:ResponseProto)

class RestoreApplicationsRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _RESTOREAPPLICATIONSREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:RestoreApplicationsRequestProto)

class RestoreApplicationsResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _RESTOREAPPLICATIONSRESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:RestoreApplicationsResponseProto)

class RiskHeaderInfoProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _RISKHEADERINFOPROTO
  
  # @@protoc_insertion_point(class_scope:RiskHeaderInfoProto)

class SignatureHashProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _SIGNATUREHASHPROTO
  
  # @@protoc_insertion_point(class_scope:SignatureHashProto)

class SignedDataProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _SIGNEDDATAPROTO
  
  # @@protoc_insertion_point(class_scope:SignedDataProto)

class SingleRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _SINGLEREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:SingleRequestProto)

class SingleResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _SINGLERESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:SingleResponseProto)

class StatusBarNotificationProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _STATUSBARNOTIFICATIONPROTO
  
  # @@protoc_insertion_point(class_scope:StatusBarNotificationProto)

class UninstallReasonRequestProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _UNINSTALLREASONREQUESTPROTO
  
  # @@protoc_insertion_point(class_scope:UninstallReasonRequestProto)

class UninstallReasonResponseProto(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _UNINSTALLREASONRESPONSEPROTO
  
  # @@protoc_insertion_point(class_scope:UninstallReasonResponseProto)

# @@protoc_insertion_point(module_scope)

########NEW FILE########
__FILENAME__ = helpers
from config import SEPARATOR

def sizeof_fmt(num):
    for x in ['bytes','KB','MB','GB','TB']:
        if num < 1024.0:
            return "%3.1f%s" % (num, x)
        num /= 1024.0

def print_header_line():
    l = [ "Title",
                "Package name",
                "Creator",
                "Super Dev",
                "Price",
                "Offer Type",
                "Version Code",
                "Size",
                "Rating",
                "Num Downloads",
             ]
    print SEPARATOR.join(l)

def print_result_line(c):
    #c.offer[0].micros/1000000.0
    #c.offer[0].currencyCode
    l = [ c.title,
                c.docid,
                c.creator,
                len(c.annotations.badgeForCreator), # Is Super Developer?
                c.offer[0].formattedAmount,
                c.offer[0].offerType,
                c.details.appDetails.versionCode,
                sizeof_fmt(c.details.appDetails.installationSize),
                "%.2f" % c.aggregateRating.starRating,
                c.details.appDetails.numDownloads]
    print SEPARATOR.join(unicode(i).encode('utf8') for i in l)


########NEW FILE########
__FILENAME__ = list
#!/usr/bin/python

# Do not remove
GOOGLE_LOGIN = GOOGLE_PASSWORD = AUTH_TOKEN = None

import sys
from pprint import pprint

from config import *
from googleplay import GooglePlayAPI
from helpers import sizeof_fmt, print_header_line, print_result_line

if (len(sys.argv) < 2):
    print "Usage: %s category [subcategory] [nb_results] [offset]" % sys.argv[0]
    print "List subcategories and apps within them."
    print "category: To obtain a list of supported catagories, use categories.py"
    print "subcategory: You can get a list of all subcategories available, by supplying a valid category"
    sys.exit(0)

cat = sys.argv[1]
ctr = None
nb_results = None
offset = None

if (len(sys.argv) >= 3):
    ctr = sys.argv[2]
if (len(sys.argv) >= 4):
    nb_results = sys.argv[3]
if (len(sys.argv) == 5):
    offset = sys.argv[4]

api = GooglePlayAPI(ANDROID_ID)
api.login(GOOGLE_LOGIN, GOOGLE_PASSWORD, AUTH_TOKEN)
try:
    message = api.list(cat, ctr, nb_results, offset)
except:
    print "Error: HTTP 500 - one of the provided parameters is invalid"

if (ctr is None):
    print SEPARATOR.join(["Subcategory ID", "Name"])
    for doc in message.doc:
        print SEPARATOR.join([doc.docid.encode('utf8'), doc.title.encode('utf8')])
else:
    print_header_line()
    doc = message.doc[0]
    for c in doc.child:
        print_result_line(c)


########NEW FILE########
__FILENAME__ = permissions
#!/usr/bin/python

# Do not remove
GOOGLE_LOGIN = GOOGLE_PASSWORD = AUTH_TOKEN = None

import sys
import urlparse
from pprint import pprint
from google.protobuf import text_format

from config import *
from googleplay import GooglePlayAPI

if (len(sys.argv) < 2):
    print "Usage: %s packagename1 [packagename2 [...]]" % sys.argv[0]
    print "Display permissions required to install the specified app(s)."
    sys.exit(0)

packagenames = sys.argv[1:]

api = GooglePlayAPI(ANDROID_ID)
api.login(GOOGLE_LOGIN, GOOGLE_PASSWORD, AUTH_TOKEN)

# Only one app
if (len(packagenames) == 1):
    response = api.details(packagenames[0])
    print "\n".join(i.encode('utf8') for i in response.docV2.details.appDetails.permission)

else: # More than one app
    response = api.bulkDetails(packagenames)

    for entry in response.entry:
        if (not not entry.ListFields()): # if the entry is not empty
            print entry.doc.docid + ":"
            print "\n".join("    "+i.encode('utf8') for i in entry.doc.details.appDetails.permission)
            print


########NEW FILE########
__FILENAME__ = search
#!/usr/bin/python

# Do not remove
GOOGLE_LOGIN = GOOGLE_PASSWORD = AUTH_TOKEN = None

import sys
from pprint import pprint

from config import *
from googleplay import GooglePlayAPI
from helpers import sizeof_fmt, print_header_line, print_result_line

if (len(sys.argv) < 2):
    print "Usage: %s request [nb_results] [offset]" % sys.argv[0]
    print "Search for an app."
    print "If request contains a space, don't forget to surround it with \"\""
    sys.exit(0)

request = sys.argv[1]
nb_res = None
offset = None

if (len(sys.argv) >= 3):
    nb_res = int(sys.argv[2])

if (len(sys.argv) >= 4):
    offset = int(sys.argv[3])

api = GooglePlayAPI(ANDROID_ID)
api.login(GOOGLE_LOGIN, GOOGLE_PASSWORD, AUTH_TOKEN)

try:
    message = api.search(request, nb_res, offset)
except:
    print "Error: something went wrong. Maybe the nb_res you specified was too big?"
    sys.exit(1)

print_header_line()
doc = message.doc[0]
for c in doc.child:
    print_result_line(c)


########NEW FILE########
