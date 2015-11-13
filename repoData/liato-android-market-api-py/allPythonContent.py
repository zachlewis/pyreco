__FILENAME__ = androidmarket
import base64
import gzip
import pprint
import StringIO
import urllib
import urllib2

from google.protobuf import descriptor
from google.protobuf.internal.containers import RepeatedCompositeFieldContainer

import market_proto

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

class MarketSession(object):
    SERVICE = "android";
    URL_LOGIN = "https://www.google.com/accounts/ClientLogin"
    ACCOUNT_TYPE_GOOGLE = "GOOGLE"
    ACCOUNT_TYPE_HOSTED = "HOSTED"
    ACCOUNT_TYPE_HOSTED_OR_GOOGLE = "HOSTED_OR_GOOGLE"
    PROTOCOL_VERSION = 2
    authSubToken = None
    context = None

    def __init__(self):
        self.context = market_proto.RequestContext()
        self.context.isSecure = 0
        self.context.version = 1002012
        self.context.androidId = "0123456789123456" # change me :(
        self.context.userLanguage = "en"
        self.context.userCountry = "US"
        self.context.deviceAndSdkVersion = "crespo:10"
        self.setOperatorTMobile()

    def _toDict(self, protoObj):
        iterable = False
        if isinstance(protoObj, RepeatedCompositeFieldContainer):
            iterable = True
        else:
            protoObj = [protoObj]
        retlist = []
        for po in protoObj:
            msg = dict()
            for fielddesc, value in po.ListFields():
                #print value, type(value), getattr(value, '__iter__', False)
                if fielddesc.type == descriptor.FieldDescriptor.TYPE_GROUP or isinstance(value, RepeatedCompositeFieldContainer):
                    msg[fielddesc.name.lower()] = self._toDict(value)
                else:
                    msg[fielddesc.name.lower()] = value
            retlist.append(msg)
        if not iterable:
            if len(retlist) > 0:
                return retlist[0]
            else:
                return None
        return retlist

    def setOperatorSimple(self, alpha, numeric):
        self.setOperator(alpha, alpha, numeric, numeric);

    def setOperatorTMobile(self):
        self.setOperatorSimple("T-Mobile", "310260")

    def setOperatorSFR(self):
        self.setOperatorSimple("F SFR", "20810")

    def setOperatorO2(self):
        self.setOperatorSimple("o2 - de", "26207")

    def setOperatorSimyo(self):
        self.setOperator("E-Plus", "simyo", "26203", "26203")

    def setOperatorSunrise(self):
        self.setOperatorSimple("sunrise", "22802")

    def setOperator(self, alpha, simAlpha, numeric, simNumeric):
        self.context.operatorAlpha = alpha
        self.context.simOperatorAlpha = simAlpha
        self.context.operatorNumeric = numeric
        self.context.simOperatorNumeric = simNumeric

    def setAuthSubToken(self, authSubToken):
        self.context.authSubToken = authSubToken
        self.authSubToken = authSubToken

    def login(self, email, password, accountType = ACCOUNT_TYPE_HOSTED_OR_GOOGLE):
        params = {"Email": email, "Passwd": password, "service": self.SERVICE,
                  "accountType": accountType}
        try:
            data = urllib2.urlopen(self.URL_LOGIN, urllib.urlencode(params)).read()
            data = data.split()
            params = {}
            for d in data:
                k, v = d.split("=")
                params[k.strip().lower()] = v.strip()
            if "auth" in params:
                self.setAuthSubToken(params["auth"])
            else:
                raise LoginError("Auth token not found.")
        except urllib2.HTTPError, e:
            if e.code == 403:
                data = e.fp.read().split()
                params = {}
                for d in data:
                    k, v = d.split("=", 1)
                    params[k.strip().lower()] = v.strip()
                if "error" in params:
                    raise LoginError(params["error"])
                else:
                    raise LoginError("Login failed.")
            else:
                raise e

    def execute(self, request):
        request.context.CopyFrom(self.context)
        try:
            headers = {"Cookie": "ANDROID="+self.authSubToken,
                       "User-Agent": "Android-Market/2 (sapphire PLAT-RC33); gzip",
                       "Content-Type": "application/x-www-form-urlencoded",
                       "Accept-Charset": "ISO-8859-1,utf-8;q=0.7,*;q=0.7"}
            data = request.SerializeToString()
            data = "version=%d&request=%s" % (self.PROTOCOL_VERSION, base64.urlsafe_b64encode(data))

            if self.context.isSecure == 1 or self.context.isSecure == True:
                http = "https://"
            else:
                http = "http://"

            request = urllib2.Request(http + "android.clients.google.com/market/api/ApiRequest",
                                      data, headers)
            data = urllib2.urlopen(request).read()
            data = StringIO.StringIO(data)
            gzipper = gzip.GzipFile(fileobj=data)
            data = gzipper.read()
            response = market_proto.Response()
            response.ParseFromString(data)
            return response
        except Exception, e:
            raise RequestError(e)

    def searchApp(self, query, startIndex = 0, entriesCount = 10, extendedInfo = True):
        appsreq = market_proto.AppsRequest()
        appsreq.query = query
        appsreq.startIndex = startIndex
        appsreq.entriesCount = entriesCount
        appsreq.withExtendedInfo = extendedInfo
        request = market_proto.Request()
        request.requestgroup.add(appsRequest = appsreq)
        response = self.execute(request)
        retlist = []
        for rg in response.responsegroup:
            if rg.HasField("appsResponse"):
                for app in rg.appsResponse.app:
                    retlist.append(self._toDict(app))
        return retlist

    def getComments(self, appid, startIndex = 0, entriesCount = 10):
        req = market_proto.CommentsRequest()
        req.appId = appid
        req.startIndex = startIndex
        req.entriesCount = entriesCount
        request = market_proto.Request()
        request.requestgroup.add(commentsRequest = req)
        response = self.execute(request)
        retlist = []
        for rg in response.responsegroup:
            if rg.HasField("commentsResponse"):
                for comment in rg.commentsResponse.comments:
                    retlist.append(self._toDict(comment))
        return retlist

    def getImage(self, appid, imageid = "0", imagetype = market_proto.GetImageRequest.SCREENSHOT):
        req = market_proto.GetImageRequest()
        req.appId = appid
        req.imageId = imageid
        req.imageUsage = imagetype
        request = market_proto.Request()
        request.requestgroup.add(imageRequest = req)
        response = self.execute(request)
        for rg in response.responsegroup:
            if rg.HasField("imageResponse"):
                return rg.imageResponse.imageData

    def getCategories(self):
        req = market_proto.CategoriesRequest()
        request = market_proto.Request()
        request.requestgroup.add(categoriesRequest = req)
        response = self.execute(request)
        retlist = []
        for rg in response.responsegroup:
            if rg.HasField("categoriesResponse"):
                for cat in rg.categoriesResponse.categories:
                    retlist.append(self._toDict(cat))
        return retlist

    def getSubCategories(self, apptype):
        req = market_proto.SubCategoriesRequest()
        req.appType = apptype
        request = market_proto.Request()
        request.requestgroup.add(subCategoriesRequest = req)
        response = self.execute(request)
        retlist = []
        for rg in response.responsegroup:
            if rg.HasField("subCategoriesResponse"):
                for cat in rg.subCategoriesResponse.category:
                    retlist.append(self._toDict(cat))
        return retlist

if __name__ == "__main__":
    print "No command line interface available, yet."

########NEW FILE########
__FILENAME__ = examples
from pprint import pprint

import market_proto
from androidmarket import MarketSession

if __name__ == "__main__":
    # Start a new session and login
    session = MarketSession()
    session.login("user@gmail.com", "password")

    # Search for "bankdroid" on the market and print the first result
    results = session.searchApp("bankdroid")
    if len(results) == 0:
        print "No results found"
        exit()

    app = results[0]
    pprint(app)

    # Print the last two comments for the app
    results = session.getComments(app["id"])
    pprint(results[:2])

    # Download and save the first screenshot
    data = session.getImage(app["id"])
    f = open("screenshot.png", "wb")
    f.write(data)
    f.close()

    # Download and save the app icon
    data = session.getImage(app["id"], imagetype=market_proto.GetImageRequest.ICON)
    f = open("icon.png", "wb")
    f.write(data)
    f.close()

    # Get all the categories and subcategories
    results = session.getCategories()
    pprint(results)

########NEW FILE########
__FILENAME__ = market_proto
# Generated by the protocol buffer compiler.  DO NOT EDIT!

from google.protobuf import descriptor
from google.protobuf import message
from google.protobuf import reflection
from google.protobuf import descriptor_pb2
# @@protoc_insertion_point(imports)

DESCRIPTOR = descriptor.FileDescriptor(
  name='market.proto',
  package='',
  serialized_pb='\n\x0cmarket.proto\"\xe4\x02\n\x0b\x41ppsRequest\x12\x19\n\x07\x61ppType\x18\x01 \x01(\x0e\x32\x08.AppType\x12\r\n\x05query\x18\x02 \x01(\t\x12\x12\n\ncategoryId\x18\x03 \x01(\t\x12\r\n\x05\x61ppId\x18\x04 \x01(\t\x12\x18\n\x10withExtendedInfo\x18\x06 \x01(\x08\x12/\n\torderType\x18\x07 \x01(\x0e\x32\x16.AppsRequest.OrderType:\x04NONE\x12\x12\n\nstartIndex\x18\x08 \x01(\x04\x12\x14\n\x0c\x65ntriesCount\x18\t \x01(\x05\x12,\n\x08viewType\x18\n \x01(\x0e\x32\x15.AppsRequest.ViewType:\x03\x41LL\"<\n\tOrderType\x12\x08\n\x04NONE\x10\x00\x12\x0b\n\x07POPULAR\x10\x01\x12\n\n\x06NEWEST\x10\x02\x12\x0c\n\x08\x46\x45\x41TURED\x10\x03\"\'\n\x08ViewType\x12\x07\n\x03\x41LL\x10\x00\x12\x08\n\x04\x46REE\x10\x01\x12\x08\n\x04PAID\x10\x02\"7\n\x0c\x41ppsResponse\x12\x11\n\x03\x61pp\x18\x01 \x03(\x0b\x32\x04.App\x12\x14\n\x0c\x65ntriesCount\x18\x02 \x01(\x05\"r\n\x08\x43\x61tegory\x12\x0f\n\x07\x61ppType\x18\x02 \x01(\x05\x12\r\n\x05title\x18\x04 \x01(\t\x12\x12\n\ncategoryId\x18\x03 \x01(\t\x12\x10\n\x08subtitle\x18\x05 \x01(\t\x12 \n\rsubCategories\x18\x08 \x03(\x0b\x32\t.Category\"J\n\x0f\x43ommentsRequest\x12\r\n\x05\x61ppId\x18\x01 \x01(\t\x12\x12\n\nstartIndex\x18\x02 \x01(\x05\x12\x14\n\x0c\x65ntriesCount\x18\x03 \x01(\x05\"D\n\x10\x43ommentsResponse\x12\x1a\n\x08\x63omments\x18\x01 \x03(\x0b\x32\x08.Comment\x12\x14\n\x0c\x65ntriesCount\x18\x02 \x01(\x05\"\xf8\x04\n\x03\x41pp\x12\n\n\x02id\x18\x01 \x01(\t\x12\r\n\x05title\x18\x02 \x01(\t\x12\x1f\n\x07\x61ppType\x18\x03 \x01(\x0e\x32\x08.AppType:\x04NONE\x12\x0f\n\x07\x63reator\x18\x04 \x01(\t\x12\x0f\n\x07version\x18\x05 \x01(\t\x12\r\n\x05price\x18\x06 \x01(\t\x12\x0e\n\x06rating\x18\x07 \x01(\t\x12\x14\n\x0cratingsCount\x18\x08 \x01(\x05\x12\'\n\x0c\x65xtendedinfo\x18\x0c \x01(\n2\x11.App.ExtendedInfo\x12\x11\n\tcreatorId\x18\x16 \x01(\t\x12\x13\n\x0bpackageName\x18\x18 \x01(\t\x12\x13\n\x0bversionCode\x18\x19 \x01(\x05\x12\x15\n\rpriceCurrency\x18  \x01(\t\x12\x13\n\x0bpriceMicros\x18! \x01(\x05\x1a\xcb\x02\n\x0c\x45xtendedInfo\x12\x13\n\x0b\x64\x65scription\x18\r \x01(\t\x12\x16\n\x0e\x64ownloadsCount\x18\x0e \x01(\x05\x12\x14\n\x0cpermissionId\x18\x0f \x03(\t\x12\x13\n\x0binstallSize\x18\x10 \x01(\x05\x12\x13\n\x0bpackageName\x18\x11 \x01(\t\x12\x10\n\x08\x63\x61tegory\x18\x12 \x01(\t\x12\x14\n\x0c\x63ontactEmail\x18\x14 \x01(\t\x12\x1a\n\x12\x64ownloadsCountText\x18\x17 \x01(\t\x12\x14\n\x0c\x63ontactPhone\x18\x1a \x01(\t\x12\x16\n\x0e\x63ontactWebsite\x18\x1b \x01(\t\x12\x18\n\x10screenshotsCount\x18\x1e \x01(\x05\x12\x11\n\tpromoText\x18\x1f \x01(\t\x12\x15\n\rrecentChanges\x18& \x01(\t\x12\x18\n\x10promotionalVideo\x18+ \x01(\t\"c\n\x07\x43omment\x12\x0c\n\x04text\x18\x01 \x01(\t\x12\x0e\n\x06rating\x18\x02 \x01(\x05\x12\x12\n\nauthorName\x18\x03 \x01(\t\x12\x14\n\x0c\x63reationTime\x18\x04 \x01(\x04\x12\x10\n\x08\x61uthorId\x18\x05 \x01(\t\"\x13\n\x11\x43\x61tegoriesRequest\"3\n\x12\x43\x61tegoriesResponse\x12\x1d\n\ncategories\x18\x01 \x03(\x0b\x32\t.Category\"1\n\x14SubCategoriesRequest\x12\x19\n\x07\x61ppType\x18\x01 \x01(\x0e\x32\x08.AppType\"g\n\x15SubCategoriesResponse\x12\x1b\n\x08\x63\x61tegory\x18\x01 \x03(\x0b\x32\t.Category\x12\x1a\n\x12subCategoryDisplay\x18\x02 \x01(\t\x12\x15\n\rsubCategoryId\x18\x03 \x01(\x05\"\x8a\x02\n\x0eRequestContext\x12\x14\n\x0c\x61uthSubToken\x18\x01 \x02(\t\x12\x10\n\x08isSecure\x18\x02 \x02(\x08\x12\x0f\n\x07version\x18\x03 \x02(\x05\x12\x11\n\tandroidId\x18\x04 \x02(\t\x12\x1b\n\x13\x64\x65viceAndSdkVersion\x18\x05 \x01(\t\x12\x14\n\x0cuserLanguage\x18\x06 \x01(\t\x12\x13\n\x0buserCountry\x18\x07 \x01(\t\x12\x15\n\roperatorAlpha\x18\x08 \x01(\t\x12\x18\n\x10simOperatorAlpha\x18\t \x01(\t\x12\x17\n\x0foperatorNumeric\x18\n \x01(\t\x12\x1a\n\x12simOperatorNumeric\x18\x0b \x01(\t\"\xcc\x01\n\x0fGetImageRequest\x12\r\n\x05\x61ppId\x18\x01 \x01(\t\x12\x32\n\nimageUsage\x18\x03 \x01(\x0e\x32\x1e.GetImageRequest.AppImageUsage\x12\x0f\n\x07imageId\x18\x04 \x01(\t\"e\n\rAppImageUsage\x12\x08\n\x04ICON\x10\x00\x12\x0e\n\nSCREENSHOT\x10\x01\x12\x18\n\x14SCREENSHOT_THUMBNAIL\x10\x02\x12\x0f\n\x0bPROMO_BADGE\x10\x03\x12\x0f\n\x0b\x42ILING_ICON\x10\x04\"=\n\x0fGetAssetRequest\x12\x0f\n\x07\x61ssetId\x18\x01 \x02(\t\x12\x19\n\x11\x64irectDownloadKey\x18\x02 \x01(\t\"%\n\x10GetImageResponse\x12\x11\n\timageData\x18\x01 \x01(\x0c\"\xf7\x02\n\x10GetAssetResponse\x12\x34\n\x0cinstallasset\x18\x01 \x03(\n2\x1e.GetAssetResponse.InstallAsset\x1a\xac\x02\n\x0cInstallAsset\x12\x0f\n\x07\x61ssetId\x18\x02 \x01(\t\x12\x11\n\tassetName\x18\x03 \x01(\t\x12\x11\n\tassetType\x18\x04 \x01(\t\x12\x14\n\x0c\x61ssetPackage\x18\x05 \x01(\t\x12\x0f\n\x07\x62lobUrl\x18\x06 \x01(\t\x12\x16\n\x0e\x61ssetSignature\x18\x07 \x01(\t\x12\x11\n\tassetSize\x18\x08 \x01(\x04\x12\x15\n\rrefundTimeout\x18\t \x01(\x04\x12\x15\n\rforwardLocked\x18\n \x01(\x08\x12\x0f\n\x07secured\x18\x0b \x01(\x08\x12\x13\n\x0bversionCode\x18\x0c \x01(\x05\x12\x1e\n\x16\x64ownloadAuthCookieName\x18\r \x01(\t\x12\x1f\n\x17\x64ownloadAuthCookieValue\x18\x0e \x01(\t\"\xee\x02\n\x07Request\x12 \n\x07\x63ontext\x18\x01 \x01(\x0b\x32\x0f.RequestContext\x12+\n\x0crequestgroup\x18\x02 \x03(\n2\x15.Request.RequestGroup\x1a\x93\x02\n\x0cRequestGroup\x12!\n\x0b\x61ppsRequest\x18\x04 \x01(\x0b\x32\x0c.AppsRequest\x12)\n\x0f\x63ommentsRequest\x18\x05 \x01(\x0b\x32\x10.CommentsRequest\x12)\n\x0fgetAssetRequest\x18\n \x01(\x0b\x32\x10.GetAssetRequest\x12&\n\x0cimageRequest\x18\x0b \x01(\x0b\x32\x10.GetImageRequest\x12\x33\n\x14subCategoriesRequest\x18\x0e \x01(\x0b\x32\x15.SubCategoriesRequest\x12-\n\x11\x63\x61tegoriesRequest\x18\x15 \x01(\x0b\x32\x12.CategoriesRequest\"\xde\x01\n\x0fResponseContext\x12+\n\x06result\x18\x01 \x01(\x0e\x32\x1b.ResponseContext.ResultType\x12\x0e\n\x06maxAge\x18\x02 \x01(\x05\x12\x0c\n\x04\x65tag\x18\x03 \x01(\t\x12\x15\n\rserverVersion\x18\x04 \x01(\x05\"i\n\nResultType\x12\x06\n\x02OK\x10\x00\x12\x0f\n\x0b\x42\x41\x44_REQUEST\x10\x01\x12\x1a\n\x16INTERNAL_SERVICE_ERROR\x10\x02\x12\x10\n\x0cNOT_MODIFIED\x10\x03\x12\x14\n\x10USER_INPUT_ERROR\x10\x04\"\x80\x03\n\x08Response\x12.\n\rresponsegroup\x18\x01 \x03(\n2\x17.Response.ResponseGroup\x1a\xc3\x02\n\rResponseGroup\x12!\n\x07\x63ontext\x18\x02 \x01(\x0b\x32\x10.ResponseContext\x12#\n\x0c\x61ppsResponse\x18\x03 \x01(\x0b\x32\r.AppsResponse\x12+\n\x10\x63ommentsResponse\x18\x04 \x01(\x0b\x32\x11.CommentsResponse\x12+\n\x10getAssetResponse\x18\t \x01(\x0b\x32\x11.GetAssetResponse\x12(\n\rimageResponse\x18\n \x01(\x0b\x32\x11.GetImageResponse\x12/\n\x12\x63\x61tegoriesResponse\x18\x14 \x01(\x0b\x32\x13.CategoriesResponse\x12\x35\n\x15subCategoriesResponse\x18\r \x01(\x0b\x32\x16.SubCategoriesResponse*K\n\x07\x41ppType\x12\x08\n\x04NONE\x10\x00\x12\x0f\n\x0b\x41PPLICATION\x10\x01\x12\x0c\n\x08RINGTONE\x10\x02\x12\r\n\tWALLPAPER\x10\x03\x12\x08\n\x04GAME\x10\x04\x42!\n\x1f\x63om.gc.android.market.api.model')

_APPTYPE = descriptor.EnumDescriptor(
  name='AppType',
  full_name='AppType',
  filename=None,
  file=DESCRIPTOR,
  values=[
    descriptor.EnumValueDescriptor(
      name='NONE', index=0, number=0,
      options=None,
      type=None),
    descriptor.EnumValueDescriptor(
      name='APPLICATION', index=1, number=1,
      options=None,
      type=None),
    descriptor.EnumValueDescriptor(
      name='RINGTONE', index=2, number=2,
      options=None,
      type=None),
    descriptor.EnumValueDescriptor(
      name='WALLPAPER', index=3, number=3,
      options=None,
      type=None),
    descriptor.EnumValueDescriptor(
      name='GAME', index=4, number=4,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=3597,
  serialized_end=3672,
)


NONE = 0
APPLICATION = 1
RINGTONE = 2
WALLPAPER = 3
GAME = 4

_APPSREQUEST_ORDERTYPE = descriptor.EnumDescriptor(
  name='OrderType',
  full_name='AppsRequest.OrderType',
  filename=None,
  file=DESCRIPTOR,
  values=[
    descriptor.EnumValueDescriptor(
      name='NONE', index=0, number=0,
      options=None,
      type=None),
    descriptor.EnumValueDescriptor(
      name='POPULAR', index=1, number=1,
      options=None,
      type=None),
    descriptor.EnumValueDescriptor(
      name='NEWEST', index=2, number=2,
      options=None,
      type=None),
    descriptor.EnumValueDescriptor(
      name='FEATURED', index=3, number=3,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=272,
  serialized_end=332,
)

_APPSREQUEST_VIEWTYPE = descriptor.EnumDescriptor(
  name='ViewType',
  full_name='AppsRequest.ViewType',
  filename=None,
  file=DESCRIPTOR,
  values=[
    descriptor.EnumValueDescriptor(
      name='ALL', index=0, number=0,
      options=None,
      type=None),
    descriptor.EnumValueDescriptor(
      name='FREE', index=1, number=1,
      options=None,
      type=None),
    descriptor.EnumValueDescriptor(
      name='PAID', index=2, number=2,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=334,
  serialized_end=373,
)

_GETIMAGEREQUEST_APPIMAGEUSAGE = descriptor.EnumDescriptor(
  name='AppImageUsage',
  full_name='GetImageRequest.AppImageUsage',
  filename=None,
  file=DESCRIPTOR,
  values=[
    descriptor.EnumValueDescriptor(
      name='ICON', index=0, number=0,
      options=None,
      type=None),
    descriptor.EnumValueDescriptor(
      name='SCREENSHOT', index=1, number=1,
      options=None,
      type=None),
    descriptor.EnumValueDescriptor(
      name='SCREENSHOT_THUMBNAIL', index=2, number=2,
      options=None,
      type=None),
    descriptor.EnumValueDescriptor(
      name='PROMO_BADGE', index=3, number=3,
      options=None,
      type=None),
    descriptor.EnumValueDescriptor(
      name='BILING_ICON', index=4, number=4,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=2033,
  serialized_end=2134,
)

_RESPONSECONTEXT_RESULTTYPE = descriptor.EnumDescriptor(
  name='ResultType',
  full_name='ResponseContext.ResultType',
  filename=None,
  file=DESCRIPTOR,
  values=[
    descriptor.EnumValueDescriptor(
      name='OK', index=0, number=0,
      options=None,
      type=None),
    descriptor.EnumValueDescriptor(
      name='BAD_REQUEST', index=1, number=1,
      options=None,
      type=None),
    descriptor.EnumValueDescriptor(
      name='INTERNAL_SERVICE_ERROR', index=2, number=2,
      options=None,
      type=None),
    descriptor.EnumValueDescriptor(
      name='NOT_MODIFIED', index=3, number=3,
      options=None,
      type=None),
    descriptor.EnumValueDescriptor(
      name='USER_INPUT_ERROR', index=4, number=4,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=3103,
  serialized_end=3208,
)

_APPSREQUEST = descriptor.Descriptor(
  name='AppsRequest',
  full_name='AppsRequest',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='appType', full_name='AppsRequest.appType', index=0,
      number=1, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='query', full_name='AppsRequest.query', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='categoryId', full_name='AppsRequest.categoryId', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='appId', full_name='AppsRequest.appId', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='withExtendedInfo', full_name='AppsRequest.withExtendedInfo', index=4,
      number=6, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='orderType', full_name='AppsRequest.orderType', index=5,
      number=7, type=14, cpp_type=8, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='startIndex', full_name='AppsRequest.startIndex', index=6,
      number=8, type=4, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='entriesCount', full_name='AppsRequest.entriesCount', index=7,
      number=9, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='viewType', full_name='AppsRequest.viewType', index=8,
      number=10, type=14, cpp_type=8, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
    _APPSREQUEST_ORDERTYPE,
    _APPSREQUEST_VIEWTYPE,
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=17,
  serialized_end=373,
)

_APPSRESPONSE = descriptor.Descriptor(
  name='AppsResponse',
  full_name='AppsResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='app', full_name='AppsResponse.app', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='entriesCount', full_name='AppsResponse.entriesCount', index=1,
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
  serialized_start=375,
  serialized_end=430,
)

_CATEGORY = descriptor.Descriptor(
  name='Category',
  full_name='Category',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='appType', full_name='Category.appType', index=0,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='title', full_name='Category.title', index=1,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='categoryId', full_name='Category.categoryId', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='subtitle', full_name='Category.subtitle', index=3,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='subCategories', full_name='Category.subCategories', index=4,
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
  serialized_start=432,
  serialized_end=546,
)

_COMMENTSREQUEST = descriptor.Descriptor(
  name='CommentsRequest',
  full_name='CommentsRequest',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='appId', full_name='CommentsRequest.appId', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='startIndex', full_name='CommentsRequest.startIndex', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='entriesCount', full_name='CommentsRequest.entriesCount', index=2,
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
  serialized_start=548,
  serialized_end=622,
)

_COMMENTSRESPONSE = descriptor.Descriptor(
  name='CommentsResponse',
  full_name='CommentsResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='comments', full_name='CommentsResponse.comments', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='entriesCount', full_name='CommentsResponse.entriesCount', index=1,
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
  serialized_start=624,
  serialized_end=692,
)

_APP_EXTENDEDINFO = descriptor.Descriptor(
  name='ExtendedInfo',
  full_name='App.ExtendedInfo',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='description', full_name='App.ExtendedInfo.description', index=0,
      number=13, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='downloadsCount', full_name='App.ExtendedInfo.downloadsCount', index=1,
      number=14, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='permissionId', full_name='App.ExtendedInfo.permissionId', index=2,
      number=15, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='installSize', full_name='App.ExtendedInfo.installSize', index=3,
      number=16, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='packageName', full_name='App.ExtendedInfo.packageName', index=4,
      number=17, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='category', full_name='App.ExtendedInfo.category', index=5,
      number=18, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='contactEmail', full_name='App.ExtendedInfo.contactEmail', index=6,
      number=20, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='downloadsCountText', full_name='App.ExtendedInfo.downloadsCountText', index=7,
      number=23, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='contactPhone', full_name='App.ExtendedInfo.contactPhone', index=8,
      number=26, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='contactWebsite', full_name='App.ExtendedInfo.contactWebsite', index=9,
      number=27, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='screenshotsCount', full_name='App.ExtendedInfo.screenshotsCount', index=10,
      number=30, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='promoText', full_name='App.ExtendedInfo.promoText', index=11,
      number=31, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='recentChanges', full_name='App.ExtendedInfo.recentChanges', index=12,
      number=38, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='promotionalVideo', full_name='App.ExtendedInfo.promotionalVideo', index=13,
      number=43, type=9, cpp_type=9, label=1,
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
  serialized_start=996,
  serialized_end=1327,
)

_APP = descriptor.Descriptor(
  name='App',
  full_name='App',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='id', full_name='App.id', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='title', full_name='App.title', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='appType', full_name='App.appType', index=2,
      number=3, type=14, cpp_type=8, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='creator', full_name='App.creator', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='version', full_name='App.version', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='price', full_name='App.price', index=5,
      number=6, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='rating', full_name='App.rating', index=6,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='ratingsCount', full_name='App.ratingsCount', index=7,
      number=8, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='extendedinfo', full_name='App.extendedinfo', index=8,
      number=12, type=10, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='creatorId', full_name='App.creatorId', index=9,
      number=22, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='packageName', full_name='App.packageName', index=10,
      number=24, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='versionCode', full_name='App.versionCode', index=11,
      number=25, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='priceCurrency', full_name='App.priceCurrency', index=12,
      number=32, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='priceMicros', full_name='App.priceMicros', index=13,
      number=33, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_APP_EXTENDEDINFO, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=695,
  serialized_end=1327,
)

_COMMENT = descriptor.Descriptor(
  name='Comment',
  full_name='Comment',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='text', full_name='Comment.text', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='rating', full_name='Comment.rating', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='authorName', full_name='Comment.authorName', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='creationTime', full_name='Comment.creationTime', index=3,
      number=4, type=4, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='authorId', full_name='Comment.authorId', index=4,
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
  serialized_start=1329,
  serialized_end=1428,
)

_CATEGORIESREQUEST = descriptor.Descriptor(
  name='CategoriesRequest',
  full_name='CategoriesRequest',
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
  serialized_start=1430,
  serialized_end=1449,
)

_CATEGORIESRESPONSE = descriptor.Descriptor(
  name='CategoriesResponse',
  full_name='CategoriesResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='categories', full_name='CategoriesResponse.categories', index=0,
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
  serialized_start=1451,
  serialized_end=1502,
)

_SUBCATEGORIESREQUEST = descriptor.Descriptor(
  name='SubCategoriesRequest',
  full_name='SubCategoriesRequest',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='appType', full_name='SubCategoriesRequest.appType', index=0,
      number=1, type=14, cpp_type=8, label=1,
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
  serialized_start=1504,
  serialized_end=1553,
)

_SUBCATEGORIESRESPONSE = descriptor.Descriptor(
  name='SubCategoriesResponse',
  full_name='SubCategoriesResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='category', full_name='SubCategoriesResponse.category', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='subCategoryDisplay', full_name='SubCategoriesResponse.subCategoryDisplay', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='subCategoryId', full_name='SubCategoriesResponse.subCategoryId', index=2,
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
  serialized_start=1555,
  serialized_end=1658,
)

_REQUESTCONTEXT = descriptor.Descriptor(
  name='RequestContext',
  full_name='RequestContext',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='authSubToken', full_name='RequestContext.authSubToken', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='isSecure', full_name='RequestContext.isSecure', index=1,
      number=2, type=8, cpp_type=7, label=2,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='version', full_name='RequestContext.version', index=2,
      number=3, type=5, cpp_type=1, label=2,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='androidId', full_name='RequestContext.androidId', index=3,
      number=4, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='deviceAndSdkVersion', full_name='RequestContext.deviceAndSdkVersion', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='userLanguage', full_name='RequestContext.userLanguage', index=5,
      number=6, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='userCountry', full_name='RequestContext.userCountry', index=6,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='operatorAlpha', full_name='RequestContext.operatorAlpha', index=7,
      number=8, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='simOperatorAlpha', full_name='RequestContext.simOperatorAlpha', index=8,
      number=9, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='operatorNumeric', full_name='RequestContext.operatorNumeric', index=9,
      number=10, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='simOperatorNumeric', full_name='RequestContext.simOperatorNumeric', index=10,
      number=11, type=9, cpp_type=9, label=1,
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
  serialized_start=1661,
  serialized_end=1927,
)

_GETIMAGEREQUEST = descriptor.Descriptor(
  name='GetImageRequest',
  full_name='GetImageRequest',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='appId', full_name='GetImageRequest.appId', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='imageUsage', full_name='GetImageRequest.imageUsage', index=1,
      number=3, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='imageId', full_name='GetImageRequest.imageId', index=2,
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
    _GETIMAGEREQUEST_APPIMAGEUSAGE,
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=1930,
  serialized_end=2134,
)

_GETASSETREQUEST = descriptor.Descriptor(
  name='GetAssetRequest',
  full_name='GetAssetRequest',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='assetId', full_name='GetAssetRequest.assetId', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='directDownloadKey', full_name='GetAssetRequest.directDownloadKey', index=1,
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
  serialized_start=2136,
  serialized_end=2197,
)

_GETIMAGERESPONSE = descriptor.Descriptor(
  name='GetImageResponse',
  full_name='GetImageResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='imageData', full_name='GetImageResponse.imageData', index=0,
      number=1, type=12, cpp_type=9, label=1,
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
  serialized_start=2199,
  serialized_end=2236,
)

_GETASSETRESPONSE_INSTALLASSET = descriptor.Descriptor(
  name='InstallAsset',
  full_name='GetAssetResponse.InstallAsset',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='assetId', full_name='GetAssetResponse.InstallAsset.assetId', index=0,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='assetName', full_name='GetAssetResponse.InstallAsset.assetName', index=1,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='assetType', full_name='GetAssetResponse.InstallAsset.assetType', index=2,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='assetPackage', full_name='GetAssetResponse.InstallAsset.assetPackage', index=3,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='blobUrl', full_name='GetAssetResponse.InstallAsset.blobUrl', index=4,
      number=6, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='assetSignature', full_name='GetAssetResponse.InstallAsset.assetSignature', index=5,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='assetSize', full_name='GetAssetResponse.InstallAsset.assetSize', index=6,
      number=8, type=4, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='refundTimeout', full_name='GetAssetResponse.InstallAsset.refundTimeout', index=7,
      number=9, type=4, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='forwardLocked', full_name='GetAssetResponse.InstallAsset.forwardLocked', index=8,
      number=10, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='secured', full_name='GetAssetResponse.InstallAsset.secured', index=9,
      number=11, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='versionCode', full_name='GetAssetResponse.InstallAsset.versionCode', index=10,
      number=12, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='downloadAuthCookieName', full_name='GetAssetResponse.InstallAsset.downloadAuthCookieName', index=11,
      number=13, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='downloadAuthCookieValue', full_name='GetAssetResponse.InstallAsset.downloadAuthCookieValue', index=12,
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
  serialized_start=2314,
  serialized_end=2614,
)

_GETASSETRESPONSE = descriptor.Descriptor(
  name='GetAssetResponse',
  full_name='GetAssetResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='installasset', full_name='GetAssetResponse.installasset', index=0,
      number=1, type=10, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_GETASSETRESPONSE_INSTALLASSET, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=2239,
  serialized_end=2614,
)

_REQUEST_REQUESTGROUP = descriptor.Descriptor(
  name='RequestGroup',
  full_name='Request.RequestGroup',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='appsRequest', full_name='Request.RequestGroup.appsRequest', index=0,
      number=4, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='commentsRequest', full_name='Request.RequestGroup.commentsRequest', index=1,
      number=5, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='getAssetRequest', full_name='Request.RequestGroup.getAssetRequest', index=2,
      number=10, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='imageRequest', full_name='Request.RequestGroup.imageRequest', index=3,
      number=11, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='subCategoriesRequest', full_name='Request.RequestGroup.subCategoriesRequest', index=4,
      number=14, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='categoriesRequest', full_name='Request.RequestGroup.categoriesRequest', index=5,
      number=21, type=11, cpp_type=10, label=1,
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
  serialized_start=2708,
  serialized_end=2983,
)

_REQUEST = descriptor.Descriptor(
  name='Request',
  full_name='Request',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='context', full_name='Request.context', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='requestgroup', full_name='Request.requestgroup', index=1,
      number=2, type=10, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_REQUEST_REQUESTGROUP, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=2617,
  serialized_end=2983,
)

_RESPONSECONTEXT = descriptor.Descriptor(
  name='ResponseContext',
  full_name='ResponseContext',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='result', full_name='ResponseContext.result', index=0,
      number=1, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='maxAge', full_name='ResponseContext.maxAge', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='etag', full_name='ResponseContext.etag', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='serverVersion', full_name='ResponseContext.serverVersion', index=3,
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
    _RESPONSECONTEXT_RESULTTYPE,
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=2986,
  serialized_end=3208,
)

_RESPONSE_RESPONSEGROUP = descriptor.Descriptor(
  name='ResponseGroup',
  full_name='Response.ResponseGroup',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='context', full_name='Response.ResponseGroup.context', index=0,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='appsResponse', full_name='Response.ResponseGroup.appsResponse', index=1,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='commentsResponse', full_name='Response.ResponseGroup.commentsResponse', index=2,
      number=4, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='getAssetResponse', full_name='Response.ResponseGroup.getAssetResponse', index=3,
      number=9, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='imageResponse', full_name='Response.ResponseGroup.imageResponse', index=4,
      number=10, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='categoriesResponse', full_name='Response.ResponseGroup.categoriesResponse', index=5,
      number=20, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='subCategoriesResponse', full_name='Response.ResponseGroup.subCategoriesResponse', index=6,
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
  serialized_start=3272,
  serialized_end=3595,
)

_RESPONSE = descriptor.Descriptor(
  name='Response',
  full_name='Response',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='responsegroup', full_name='Response.responsegroup', index=0,
      number=1, type=10, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_RESPONSE_RESPONSEGROUP, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=3211,
  serialized_end=3595,
)

_APPSREQUEST.fields_by_name['appType'].enum_type = _APPTYPE
_APPSREQUEST.fields_by_name['orderType'].enum_type = _APPSREQUEST_ORDERTYPE
_APPSREQUEST.fields_by_name['viewType'].enum_type = _APPSREQUEST_VIEWTYPE
_APPSREQUEST_ORDERTYPE.containing_type = _APPSREQUEST;
_APPSREQUEST_VIEWTYPE.containing_type = _APPSREQUEST;
_APPSRESPONSE.fields_by_name['app'].message_type = _APP
_CATEGORY.fields_by_name['subCategories'].message_type = _CATEGORY
_COMMENTSRESPONSE.fields_by_name['comments'].message_type = _COMMENT
_APP_EXTENDEDINFO.containing_type = _APP;
_APP.fields_by_name['appType'].enum_type = _APPTYPE
_APP.fields_by_name['extendedinfo'].message_type = _APP_EXTENDEDINFO
_CATEGORIESRESPONSE.fields_by_name['categories'].message_type = _CATEGORY
_SUBCATEGORIESREQUEST.fields_by_name['appType'].enum_type = _APPTYPE
_SUBCATEGORIESRESPONSE.fields_by_name['category'].message_type = _CATEGORY
_GETIMAGEREQUEST.fields_by_name['imageUsage'].enum_type = _GETIMAGEREQUEST_APPIMAGEUSAGE
_GETIMAGEREQUEST_APPIMAGEUSAGE.containing_type = _GETIMAGEREQUEST;
_GETASSETRESPONSE_INSTALLASSET.containing_type = _GETASSETRESPONSE;
_GETASSETRESPONSE.fields_by_name['installasset'].message_type = _GETASSETRESPONSE_INSTALLASSET
_REQUEST_REQUESTGROUP.fields_by_name['appsRequest'].message_type = _APPSREQUEST
_REQUEST_REQUESTGROUP.fields_by_name['commentsRequest'].message_type = _COMMENTSREQUEST
_REQUEST_REQUESTGROUP.fields_by_name['getAssetRequest'].message_type = _GETASSETREQUEST
_REQUEST_REQUESTGROUP.fields_by_name['imageRequest'].message_type = _GETIMAGEREQUEST
_REQUEST_REQUESTGROUP.fields_by_name['subCategoriesRequest'].message_type = _SUBCATEGORIESREQUEST
_REQUEST_REQUESTGROUP.fields_by_name['categoriesRequest'].message_type = _CATEGORIESREQUEST
_REQUEST_REQUESTGROUP.containing_type = _REQUEST;
_REQUEST.fields_by_name['context'].message_type = _REQUESTCONTEXT
_REQUEST.fields_by_name['requestgroup'].message_type = _REQUEST_REQUESTGROUP
_RESPONSECONTEXT.fields_by_name['result'].enum_type = _RESPONSECONTEXT_RESULTTYPE
_RESPONSECONTEXT_RESULTTYPE.containing_type = _RESPONSECONTEXT;
_RESPONSE_RESPONSEGROUP.fields_by_name['context'].message_type = _RESPONSECONTEXT
_RESPONSE_RESPONSEGROUP.fields_by_name['appsResponse'].message_type = _APPSRESPONSE
_RESPONSE_RESPONSEGROUP.fields_by_name['commentsResponse'].message_type = _COMMENTSRESPONSE
_RESPONSE_RESPONSEGROUP.fields_by_name['getAssetResponse'].message_type = _GETASSETRESPONSE
_RESPONSE_RESPONSEGROUP.fields_by_name['imageResponse'].message_type = _GETIMAGERESPONSE
_RESPONSE_RESPONSEGROUP.fields_by_name['categoriesResponse'].message_type = _CATEGORIESRESPONSE
_RESPONSE_RESPONSEGROUP.fields_by_name['subCategoriesResponse'].message_type = _SUBCATEGORIESRESPONSE
_RESPONSE_RESPONSEGROUP.containing_type = _RESPONSE;
_RESPONSE.fields_by_name['responsegroup'].message_type = _RESPONSE_RESPONSEGROUP
DESCRIPTOR.message_types_by_name['AppsRequest'] = _APPSREQUEST
DESCRIPTOR.message_types_by_name['AppsResponse'] = _APPSRESPONSE
DESCRIPTOR.message_types_by_name['Category'] = _CATEGORY
DESCRIPTOR.message_types_by_name['CommentsRequest'] = _COMMENTSREQUEST
DESCRIPTOR.message_types_by_name['CommentsResponse'] = _COMMENTSRESPONSE
DESCRIPTOR.message_types_by_name['App'] = _APP
DESCRIPTOR.message_types_by_name['Comment'] = _COMMENT
DESCRIPTOR.message_types_by_name['CategoriesRequest'] = _CATEGORIESREQUEST
DESCRIPTOR.message_types_by_name['CategoriesResponse'] = _CATEGORIESRESPONSE
DESCRIPTOR.message_types_by_name['SubCategoriesRequest'] = _SUBCATEGORIESREQUEST
DESCRIPTOR.message_types_by_name['SubCategoriesResponse'] = _SUBCATEGORIESRESPONSE
DESCRIPTOR.message_types_by_name['RequestContext'] = _REQUESTCONTEXT
DESCRIPTOR.message_types_by_name['GetImageRequest'] = _GETIMAGEREQUEST
DESCRIPTOR.message_types_by_name['GetAssetRequest'] = _GETASSETREQUEST
DESCRIPTOR.message_types_by_name['GetImageResponse'] = _GETIMAGERESPONSE
DESCRIPTOR.message_types_by_name['GetAssetResponse'] = _GETASSETRESPONSE
DESCRIPTOR.message_types_by_name['Request'] = _REQUEST
DESCRIPTOR.message_types_by_name['ResponseContext'] = _RESPONSECONTEXT
DESCRIPTOR.message_types_by_name['Response'] = _RESPONSE

class AppsRequest(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _APPSREQUEST

  # @@protoc_insertion_point(class_scope:AppsRequest)

class AppsResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _APPSRESPONSE

  # @@protoc_insertion_point(class_scope:AppsResponse)

class Category(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _CATEGORY

  # @@protoc_insertion_point(class_scope:Category)

class CommentsRequest(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _COMMENTSREQUEST

  # @@protoc_insertion_point(class_scope:CommentsRequest)

class CommentsResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _COMMENTSRESPONSE

  # @@protoc_insertion_point(class_scope:CommentsResponse)

class App(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType

  class ExtendedInfo(message.Message):
    __metaclass__ = reflection.GeneratedProtocolMessageType
    DESCRIPTOR = _APP_EXTENDEDINFO

    # @@protoc_insertion_point(class_scope:App.ExtendedInfo)
  DESCRIPTOR = _APP

  # @@protoc_insertion_point(class_scope:App)

class Comment(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _COMMENT

  # @@protoc_insertion_point(class_scope:Comment)

class CategoriesRequest(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _CATEGORIESREQUEST

  # @@protoc_insertion_point(class_scope:CategoriesRequest)

class CategoriesResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _CATEGORIESRESPONSE

  # @@protoc_insertion_point(class_scope:CategoriesResponse)

class SubCategoriesRequest(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _SUBCATEGORIESREQUEST

  # @@protoc_insertion_point(class_scope:SubCategoriesRequest)

class SubCategoriesResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _SUBCATEGORIESRESPONSE

  # @@protoc_insertion_point(class_scope:SubCategoriesResponse)

class RequestContext(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _REQUESTCONTEXT

  # @@protoc_insertion_point(class_scope:RequestContext)

class GetImageRequest(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _GETIMAGEREQUEST

  # @@protoc_insertion_point(class_scope:GetImageRequest)

class GetAssetRequest(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _GETASSETREQUEST

  # @@protoc_insertion_point(class_scope:GetAssetRequest)

class GetImageResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _GETIMAGERESPONSE

  # @@protoc_insertion_point(class_scope:GetImageResponse)

class GetAssetResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType

  class InstallAsset(message.Message):
    __metaclass__ = reflection.GeneratedProtocolMessageType
    DESCRIPTOR = _GETASSETRESPONSE_INSTALLASSET

    # @@protoc_insertion_point(class_scope:GetAssetResponse.InstallAsset)
  DESCRIPTOR = _GETASSETRESPONSE

  # @@protoc_insertion_point(class_scope:GetAssetResponse)

class Request(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType

  class RequestGroup(message.Message):
    __metaclass__ = reflection.GeneratedProtocolMessageType
    DESCRIPTOR = _REQUEST_REQUESTGROUP

    # @@protoc_insertion_point(class_scope:Request.RequestGroup)
  DESCRIPTOR = _REQUEST

  # @@protoc_insertion_point(class_scope:Request)

class ResponseContext(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _RESPONSECONTEXT

  # @@protoc_insertion_point(class_scope:ResponseContext)

class Response(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType

  class ResponseGroup(message.Message):
    __metaclass__ = reflection.GeneratedProtocolMessageType
    DESCRIPTOR = _RESPONSE_RESPONSEGROUP

    # @@protoc_insertion_point(class_scope:Response.ResponseGroup)
  DESCRIPTOR = _RESPONSE

  # @@protoc_insertion_point(class_scope:Response)

# @@protoc_insertion_point(module_scope)

########NEW FILE########
