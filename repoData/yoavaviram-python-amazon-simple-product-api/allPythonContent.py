__FILENAME__ = api
#!/usr/bin/python
#
# Copyright (C) 2012 Yoav Aviram.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import datetime
from itertools import islice

import bottlenose
from lxml import objectify, etree
import dateutil.parser


# https://kdp.amazon.com/help?topicId=A1CT8LK6UW2FXJ
# CN not listed
DOMAINS = {
    'CA': 'ca',
    'DE': 'de',
    'ES': 'es',
    'FR': 'fr',
    'IT': 'it',
    'JP': 'co.jp',
    'UK': 'co.uk',
    'US': 'com',
}

AMAZON_ASSOCIATES_BASE_URL = 'http://www.amazon.{domain}/dp/'


class AmazonException(Exception):
    """Base Class for Amazon Api Exceptions.
    """
    pass


class AsinNotFound(AmazonException):
    """ASIN Not Found Exception.
    """
    pass


class LookupException(AmazonException):
    """Lookup Exception.
    """
    pass


class SearchException(AmazonException):
    """Search Exception.
    """
    pass


class NoMorePages(SearchException):
    """No More Pages Exception.
    """
    pass


class SimilartyLookupException(AmazonException):
    """Similarty Lookup Exception.
    """
    pass


class BrowseNodeLookupException(AmazonException):
    """Browse Node Lookup Exception.
    """
    pass


class AmazonAPI(object):
    def __init__(self, aws_key, aws_secret, aws_associate_tag, region="US"):
        """Initialize an Amazon API Proxy.

        :param aws_key:
            A string representing an AWS authentication key.
        :param aws_secret:
            A string representing an AWS authentication secret.
        :param aws_associate_tag:
            A string representing an AWS associate tag.
        :param region:
            A string representing the region, defaulting to "US" (amazon.com)
            See keys of bottlenose.api.SERVICE_DOMAINS for options, which were
            CA, CN, DE, ES, FR, IT, JP, UK, US at the time of writing.
        """
        self.api = bottlenose.Amazon(
            aws_key, aws_secret, aws_associate_tag, Region=region)
        self.aws_associate_tag = aws_associate_tag
        self.region = region

    def lookup(self, ResponseGroup="Large", **kwargs):
        """Lookup an Amazon Product.

        :return:
            An instance of :class:`~.AmazonProduct` if one item was returned,
            or a list of  :class:`~.AmazonProduct` instances if multiple
            items where returned.
        """
        response = self.api.ItemLookup(ResponseGroup=ResponseGroup, **kwargs)
        root = objectify.fromstring(response)
        if root.Items.Request.IsValid == 'False':
            code = root.Items.Request.Errors.Error.Code
            msg = root.Items.Request.Errors.Error.Message
            raise LookupException(
                "Amazon Product Lookup Error: '{0}', '{1}'".format(code, msg))
        if not hasattr(root.Items, 'Item'):
            raise AsinNotFound("ASIN(s) not found: '{0}'".format(
                etree.tostring(root, pretty_print=True)))
        if len(root.Items.Item) > 1:
            return [
                AmazonProduct(
                    item,
                    self.aws_associate_tag,
                    self,
                    region=self.region) for item in root.Items.Item
            ]
        else:
            return AmazonProduct(
                root.Items.Item,
                self.aws_associate_tag,
                self,
                region=self.region
            )

    def similarity_lookup(self, ResponseGroup="Large", **kwargs):
        """Similarty Lookup.

        Returns up to ten products that are similar to all items
        specified in the request.

        Example:
            >>> api.similarity_lookup(ItemId='B002L3XLBO,B000LQTBKI')
        """
        response = self.api.SimilarityLookup(
            ResponseGroup=ResponseGroup, **kwargs)
        root = objectify.fromstring(response)
        if root.Items.Request.IsValid == 'False':
            code = root.Items.Request.Errors.Error.Code
            msg = root.Items.Request.Errors.Error.Message
            raise SimilartyLookupException(
                "Amazon Similarty Lookup Error: '{0}', '{1}'".format(
                    code, msg))
        return [
            AmazonProduct(
                item,
                self.aws_associate_tag,
                self.api,
                region=self.region
            )
            for item in getattr(root.Items, 'Item', [])
        ]

    def browse_node_lookup(self, ResponseGroup="BrowseNodeInfo", **kwargs):
        """Browse Node Lookup.

        Returns the specified browse node's name, children, and ancestors.
        Example:
            >>> api.browse_node_lookup(BrowseNodeId='163357')
        """
        response = self.api.BrowseNodeLookup(
            ResponseGroup=ResponseGroup, **kwargs)
        root = objectify.fromstring(response)
        if root.BrowseNodes.Request.IsValid == 'False':
            code = root.BrowseNodes.Request.Errors.Error.Code
            msg = root.BrowseNodes.Request.Errors.Error.Message
            raise BrowseNodeLookupException(
                "Amazon BrowseNode Lookup Error: '{0}', '{1}'".format(
                    code, msg))
        return [AmazonBrowseNode(node.BrowseNode) for node in root.BrowseNodes]

    def search(self, **kwargs):
        """Search.

        :return:
            An :class:`~.AmazonSearch` iterable.
        """
        region = kwargs.get('region', self.region)
        kwargs.update({'region': region})
        return AmazonSearch(self.api, self.aws_associate_tag, **kwargs)

    def search_n(self, n, **kwargs):
        """Search and return first N results..

        :param n:
            An integer specifying the number of results to return.
        :return:
            A list of :class:`~.AmazonProduct`.
        """
        region = kwargs.get('region', self.region)
        kwargs.update({'region': region})
        items = AmazonSearch(self.api, self.aws_associate_tag, **kwargs)
        return list(islice(items, n))


class AmazonSearch(object):
    """ Amazon Search.

    A class providing an iterable over amazon search results.
    """
    def __init__(self, api, aws_associate_tag, **kwargs):
        """Initialise

        Initialise a search

        :param api:
            An instance of :class:`~.bottlenose.Amazon`.
        :param aws_associate_tag:
            An string representing an Amazon Associates tag.
        """
        self.kwargs = kwargs
        self.current_page = 1
        self.api = api
        self.aws_associate_tag = aws_associate_tag

    def __iter__(self):
        """Iterate.

        A generator which iterate over all paginated results
        returning :class:`~.AmazonProduct` for each item.

        :return:
            Yields a :class:`~.AmazonProduct` for each result item.
        """
        for page in self.iterate_pages():
            for item in getattr(page.Items, 'Item', []):
                yield AmazonProduct(
                    item, self.aws_associate_tag, self.api, **self.kwargs)

    def iterate_pages(self):
        """Iterate Pages.

        A generator which iterates over all pages.
        Keep in mind that Amazon limits the number of pages it makes available.

        :return:
            Yields lxml root elements.
        """
        try:
            while True:
                yield self._query(ItemPage=self.current_page, **self.kwargs)
                self.current_page += 1
        except NoMorePages:
            pass

    def _query(self, ResponseGroup="Large", **kwargs):
        """Query.

        Query Amazon search and check for errors.

        :return:
            An lxml root element.
        """
        response = self.api.ItemSearch(ResponseGroup=ResponseGroup, **kwargs)
        root = objectify.fromstring(response)
        if root.Items.Request.IsValid == 'False':
            code = root.Items.Request.Errors.Error.Code
            msg = root.Items.Request.Errors.Error.Message
            if code == 'AWS.ParameterOutOfRange':
                raise NoMorePages(msg)
            else:
                raise SearchException(
                    "Amazon Search Error: '{0}', '{1}'".format(code, msg))
        return root


class AmazonBrowseNode(object):

    def __init__(self, element):
        self.element = element

    @property
    def id(self):
        """Browse Node ID.

        A positive integer that uniquely identifies a parent product category.

        :return:
            ID (integer)
        """
        if hasattr(self.element, 'BrowseNodeId'):
            return int(self.element['BrowseNodeId'])
        return None

    @property
    def name(self):
        """Browse Node Name.

        :return:
            Name (string)
        """
        return getattr(self.element, 'Name', None)

    @property
    def is_category_root(self):
        """Boolean value that specifies if the browse node is at the top of
        the browse node tree.
        """
        return getattr(self.element, 'IsCategoryRoot', False)

    @property
    def ancestor(self):
        """This browse node's immediate ancestor in the browse node tree.

        :return:
            The ancestor as an :class:`~.AmazonBrowseNode`, or None.
        """
        ancestors = getattr(self.element, 'Ancestors', None)
        if hasattr(ancestors, 'BrowseNode'):
            return AmazonBrowseNode(ancestors['BrowseNode'])
        return None

    @property
    def ancestors(self):
        """A list of this browse node's ancestors in the browse node tree.

        :return:
            List of :class:`~.AmazonBrowseNode` objects.
        """
        ancestors = []
        node = self.ancestor
        while node is not None:
            ancestors.append(node)
            node = node.ancestor
        return ancestors

    @property
    def children(self):
        """This browse node's children in the browse node tree.

    :return:
    A list of this browse node's children in the browse node tree.
    """
        children = []
        child_nodes = getattr(self.element, 'Children')
        for child in getattr(child_nodes, 'BrowseNode', []):
                children.append(AmazonBrowseNode(child))
        return children


class AmazonProduct(object):
    """A wrapper class for an Amazon product.
    """

    def __init__(self, item, aws_associate_tag, api, *args, **kwargs):
        """Initialize an Amazon Product Proxy.

        :param item:
            Lxml Item element.
        """
        self.item = item
        self.aws_associate_tag = aws_associate_tag
        self.api = api
        self.parent = None
        self.region = kwargs.get('region', 'US')

    def to_string(self):
        """Convert Item XML to string.

        :return:
            A string representation of the Item xml.
        """
        return etree.tostring(self.item, pretty_print=True)

    def _safe_get_element(self, path, root=None):
        """Safe Get Element.

        Get a child element of root (multiple levels deep) failing silently
        if any descendant does not exist.

        :param root:
            Lxml element.
        :param path:
            String path (i.e. 'Items.Item.Offers.Offer').
        :return:
            Element or None.
        """
        elements = path.split('.')
        parent = root if root is not None else self.item
        for element in elements[:-1]:
            parent = getattr(parent, element, None)
            if parent is None:
                return None
        return getattr(parent, elements[-1], None)

    def _safe_get_element_text(self, path, root=None):
        """Safe get element text.

        Get element as string or None,
        :param root:
            Lxml element.
        :param path:
            String path (i.e. 'Items.Item.Offers.Offer').
        :return:
            String or None.
        """
        element = self._safe_get_element(path, root)
        if element is not None:
            return element.text
        else:
            return None

    def _safe_get_element_date(self, path, root=None):
        """Safe get elemnent date.

        Get element as datetime.date or None,
        :param root:
            Lxml element.
        :param path:
            String path (i.e. 'Items.Item.Offers.Offer').
        :return:
            datetime.date or None.
        """
        value = self._safe_get_element_text(path=path, root=root)
        if value is not None:
            try:
                value = dateutil.parser.parse(value)
                if value:
                    value = value.date()
            except ValueError:
                value = None

        return value

    @property
    def price_and_currency(self):
        """Get Offer Price and Currency.

        Return price according to the following process:

        * If product has a sale return Sales Price, otherwise,
        * Return Price, otherwise,
        * Return lowest offer price, otherwise,
        * Return None.

        :return:
            A tuple containing:

                1. Float representation of price.
                2. ISO Currency code (string).
        """
        price = self._safe_get_element_text(
            'Offers.Offer.OfferListing.SalePrice.Amount')
        if price:
            currency = self._safe_get_element_text(
                'Offers.Offer.OfferListing.SalePrice.CurrencyCode')
        else:
            price = self._safe_get_element_text(
                'Offers.Offer.OfferListing.Price.Amount')
            if price:
                currency = self._safe_get_element_text(
                    'Offers.Offer.OfferListing.Price.CurrencyCode')
            else:
                price = self._safe_get_element_text(
                    'OfferSummary.LowestNewPrice.Amount')
                currency = self._safe_get_element_text(
                    'OfferSummary.LowestNewPrice.CurrencyCode')
        if price:
            return float(price) / 100, currency
        else:
            return None, None

    @property
    def asin(self):
        """ASIN (Amazon ID)

        :return:
            ASIN (string).
        """
        return self._safe_get_element_text('ASIN')

    @property
    def sales_rank(self):
        """Sales Rank

        :return:
            Sales Rank (integer).
        """
        return self._safe_get_element_text('SalesRank')

    @property
    def offer_url(self):
        """Offer URL

        :return:
            Offer URL (string).
        """
        return "{0}{1}/?tag={2}".format(
            AMAZON_ASSOCIATES_BASE_URL.format(domain=DOMAINS[self.region]),
            self.asin,
            self.aws_associate_tag)

    @property
    def author(self):
        """Author.

        Depricated, please use `authors`.
        :return:
            Author (string).
        """
        authors = self.authors
        if len(authors):
            return authors[0]
        else:
            return None

    @property
    def authors(self):
        """Authors.

        :return:
            Returns of list of authors
        """
        result = []
        authors = self._safe_get_element('ItemAttributes.Author')
        if authors is not None:
            for author in authors:
                result.append(author.text)
        return result

    @property
    def creators(self):
        """Creators.

        Creators are not the authors. These are usually editors, translators,
        narrators, etc.

        :return:
            Returns a list of creators where each is a tuple containing:

                1. The creators name (string).
                2. The creators role (string).

        """
        # return tuples of name and role
        result = []
        creators = self._safe_get_element('ItemAttributes.Creator')
        if creators is not None:
            for creator in creators:
                role = creator.attrib['Role'] if 'Role' in creator.attrib else None
                result.append((creator.text, role))
        return result

    @property
    def publisher(self):
        """Publisher.

        :return:
            Publisher (string)
        """
        return self._safe_get_element_text('ItemAttributes.Publisher')

    @property
    def label(self):
        """Label.

        :return:
            Label (string)
        """
        return self._safe_get_element_text('ItemAttributes.Label')

    @property
    def manufacturer(self):
        """Manufacturer.

        :return:
            Manufacturer (string)
        """
        return self._safe_get_element_text('ItemAttributes.Manufacturer')

    @property
    def brand(self):
        """Brand.

        :return:
            Brand (string)
        """
        return self._safe_get_element_text('ItemAttributes.Brand')

    @property
    def isbn(self):
        """ISBN.

        :return:
            ISBN (string)
        """
        return self._safe_get_element_text('ItemAttributes.ISBN')

    @property
    def eisbn(self):
        """EISBN (The ISBN of eBooks).

        :return:
            EISBN (string)
        """
        return self._safe_get_element_text('ItemAttributes.EISBN')

    @property
    def binding(self):
        """Binding.

        :return:
            Binding (string)
        """
        return self._safe_get_element_text('ItemAttributes.Binding')

    @property
    def pages(self):
        """Pages.

        :return:
            Pages (string)
        """
        return self._safe_get_element_text('ItemAttributes.NumberOfPages')

    @property
    def publication_date(self):
        """Pubdate.

        :return:
            Pubdate (datetime.date)
        """
        return self._safe_get_element_date('ItemAttributes.PublicationDate')

    @property
    def release_date(self):
        """Release date .

        :return:
            Release date (datetime.date)
        """
        return self._safe_get_element_date('ItemAttributes.ReleaseDate')

    @property
    def edition(self):
        """Edition.

        :return:
            Edition (string)
        """
        return self._safe_get_element_text('ItemAttributes.Edition')

    @property
    def large_image_url(self):
        """Large Image URL.

        :return:
            Large image url (string)
        """
        return self._safe_get_element_text('LargeImage.URL')

    @property
    def medium_image_url(self):
        """Medium Image URL.

        :return:
            Medium image url (string)
        """
        return self._safe_get_element_text('MediumImage.URL')

    @property
    def small_image_url(self):
        """Small Image URL.

        :return:
            Small image url (string)
        """
        return self._safe_get_element_text('SmallImage.URL')

    @property
    def tiny_image_url(self):
        """Tiny Image URL.

        :return:
            Tiny image url (string)
        """
        return self._safe_get_element_text('TinyImage.URL')

    @property
    def reviews(self):
        """Customer Reviews.

        Get a iframe URL for customer reviews.
        :return:
            A tuple of: has_reviews (bool), reviews url (string)
        """
        iframe = self._safe_get_element_text('CustomerReviews.IFrameURL')
        has_reviews = self._safe_get_element_text('CustomerReviews.HasReviews')
        if has_reviews and has_reviews == 'true':
            has_reviews = True
        else:
            has_reviews = False
        return has_reviews, iframe

    @property
    def ean(self):
        """EAN.

        :return:
            EAN (string)
        """
        ean = self._safe_get_element_text('ItemAttributes.EAN')
        if ean is None:
            ean_list = self._safe_get_element_text('ItemAttributes.EANList')
            if ean_list:
                ean = self._safe_get_element_text(
                    'EANListElement', root=ean_list[0])
        return ean

    @property
    def upc(self):
        """UPC.

        :return:
            UPC (string)
        """
        upc = self._safe_get_element_text('ItemAttributes.UPC')
        if upc is None:
            upc_list = self._safe_get_element_text('ItemAttributes.UPCList')
            if upc_list:
                upc = self._safe_get_element_text(
                    'UPCListElement', root=upc_list[0])
        return upc

    @property
    def sku(self):
        """SKU.

        :return:
            SKU (string)
        """
        return self._safe_get_element_text('ItemAttributes.SKU')

    @property
    def mpn(self):
        """MPN.

        :return:
            MPN (string)
        """
        return self._safe_get_element_text('ItemAttributes.MPN')

    @property
    def model(self):
        """Model Name.

        :return:
            Model (string)
        """
        return self._safe_get_element_text('ItemAttributes.Model')

    @property
    def part_number(self):
        """Part Number.

        :return:
            Part Number (string)
        """
        return self._safe_get_element_text('ItemAttributes.PartNumber')

    @property
    def title(self):
        """Title.

        :return:
            Title (string)
        """
        return self._safe_get_element_text('ItemAttributes.Title')

    @property
    def editorial_review(self):
        """Editorial Review.

        Returns an editorial review text.

        :return:
            Editorial Review (string)
        """
        reviews = self.editorial_reviews
        if reviews:
            return reviews[0]
        return ''

    @property
    def editorial_reviews(self):
        """Editorial Review.

        Returns a list of all editorial reviews.

        :return:
            A list containing:

                Editorial Review (string)
        """
        result = []
        reviews_node = self._safe_get_element('EditorialReviews')

        if reviews_node is not None:
            for review_node in reviews_node.iterchildren():
                content_node = getattr(review_node, 'Content')
                if content_node is not None:
                    result.append(content_node.text)
        return result

    @property
    def languages(self):
        """Languages.

        Returns a set of languages in lower-case.
        :return:
            Returns a set of languages in lower-case (strings).
        """
        result = set()
        languages = self._safe_get_element('ItemAttributes.Languages')
        if languages is not None:
            for language in languages.iterchildren():
                text = self._safe_get_element_text('Name', language)
                if text:
                    result.add(text.lower())
        return result

    @property
    def features(self):
        """Features.

        Returns a list of feature descriptions.
        :return:
            Returns a list of 'ItemAttributes.Feature' elements (strings).
        """
        result = []
        features = self._safe_get_element('ItemAttributes.Feature')
        if features is not None:
            for feature in features:
                result.append(feature.text)
        return result

    @property
    def list_price(self):
        """List Price.

        :return:
            A tuple containing:

                1. Float representation of price.
                2. ISO Currency code (string).
        """
        price = self._safe_get_element_text('ItemAttributes.ListPrice.Amount')
        currency = self._safe_get_element_text(
            'ItemAttributes.ListPrice.CurrencyCode')
        if price:
            return float(price) / 100, currency
        else:
            return None, None

    def get_attribute(self, name):
        """Get Attribute

        Get an attribute (child elements of 'ItemAttributes') value.

        :param name:
            Attribute name (string)
        :return:
            Attribute value (string) or None if not found.
        """
        return self._safe_get_element_text("ItemAttributes.{0}".format(name))

    def get_attribute_details(self, name):
        """Get Attribute Details

        Gets XML attributes of the product attribute. These usually contain
        details about the product attributes such as units.
        :param name:
            Attribute name (string)
        :return:
            A name/value dictionary.
        """
        return self._safe_get_element("ItemAttributes.{0}".format(name)).attrib

    def get_attributes(self, name_list):
        """Get Attributes

        Get a list of attributes as a name/value dictionary.

        :param name_list:
            A list of attribute names (strings).
        :return:
            A name/value dictionary (both names and values are strings).
        """
        properties = {}
        for name in name_list:
            value = self.get_attribute(name)
            if value is not None:
                properties[name] = value
        return properties

    @property
    def parent_asin(self):
        """Parent ASIN.

        Can be used to test if product has a parent.
        :return:
            Parent ASIN if product has a parent.
        """
        return self._safe_get_element('ParentASIN')

    def get_parent(self):
        """Get Parent.

        Fetch parent product if it exists.
        Use `parent_asin` to check if a parent exist before fetching.
        :return:
            An instance of :class:`~.AmazonProduct` representing the
            parent product.
        """
        if not self.parent:
            parent = self._safe_get_element('ParentASIN')
            if parent:
                self.parent = self.api.lookup(ItemId=parent)
        return self.parent

    @property
    def browse_nodes(self):
        """Browse Nodes.

        :return:
            A list of :class:`~.AmazonBrowseNode` objects.
        """
        root = self._safe_get_element('BrowseNodes')
        if root is None:
            return []

        return [AmazonBrowseNode(child) for child in root.iterchildren()]

########NEW FILE########
__FILENAME__ = tests
from unittest import TestCase

from nose.tools import assert_equals, assert_true, assert_false

import datetime
from amazon.api import AmazonAPI
from test_settings import (AMAZON_ACCESS_KEY,
                           AMAZON_SECRET_KEY,
                           AMAZON_ASSOC_TAG)


PRODUCT_ATTRIBUTES = [
    'asin', 'author', 'binding', 'brand', 'browse_nodes', 'ean', 'edition',
    'editorial_review', 'eisbn', 'features', 'get_parent', 'isbn', 'label',
    'large_image_url', 'list_price', 'manufacturer', 'medium_image_url',
    'model', 'mpn', 'offer_url', 'parent_asin', 'part_number',
    'price_and_currency', 'publication_date', 'publisher', 'region',
    'release_date', 'reviews', 'sku', 'small_image_url', 'tiny_image_url',
    'title', 'upc'
]


class TestAmazonApi(TestCase):
    """Test Amazon API

    Test Class for Amazon simple API wrapper.
    """
    def setUp(self):
        """Set Up.

        Initialize the Amazon API wrapper. The following values:

        * AMAZON_ACCESS_KEY
        * AMAZON_SECRET_KEY
        * AMAZON_ASSOC_TAG

        Are imported from a custom file named: 'test_settings.py'
        """
        self.amazon = AmazonAPI(
            AMAZON_ACCESS_KEY, AMAZON_SECRET_KEY, AMAZON_ASSOC_TAG)

    def test_lookup(self):
        """Test Product Lookup.

        Tests that a product lookup for a kindle returns results and that the
        main methods are working.
        """
        product = self.amazon.lookup(ItemId="B007HCCNJU")
        assert_true('Kindle' in product.title)
        assert_equals(product.ean, '0814916017775')
        assert_equals(
            product.large_image_url,
            'http://ecx.images-amazon.com/images/I/41VZlVs8agL.jpg'
        )
        assert_equals(
            product.get_attribute('Publisher'),
            'Amazon'
        )
        assert_equals(product.get_attributes(
            ['ItemDimensions.Width', 'ItemDimensions.Height']),
            {'ItemDimensions.Width': '650', 'ItemDimensions.Height': '130'})
        assert_true(len(product.browse_nodes) > 0)
        assert_true(product.price_and_currency[0] is not None)
        assert_true(product.price_and_currency[1] is not None)
        assert_equals(product.browse_nodes[0].id, 2642129011)
        assert_equals(product.browse_nodes[0].name, 'eBook Readers')

    def test_batch_lookup(self):
        """Test Batch Product Lookup.

        Tests that a batch product lookup request returns multiple results.
        """
        asins = ['B00AWH595M', 'B007HCCNJU', 'B00BWYQ9YE',
                 'B00BWYRF7E', 'B00D2KJDXA']
        products = self.amazon.lookup(ItemId=','.join(asins))
        assert_equals(len(products), 5)
        for i, product in enumerate(products):
            assert_equals(asins[i], product.asin)

    def test_search(self):
        """Test Product Search.

        Tests that a product search is working (by testing that results are
        returned). And that each result has a title attribute. The test
        fails if no results where returned.
        """
        products = self.amazon.search(Keywords='kindle', SearchIndex='All')
        for product in products:
            assert_true(hasattr(product, 'title'))
            break
        else:
            assert_true(False, 'No search results returned.')

    def test_search_n(self):
        """Test Product Search N.

        Tests that a product search n is working by testing that N results are
        returned.
        """
        products = self.amazon.search_n(
            1,
            Keywords='kindle',
            SearchIndex='All'
        )
        assert_equals(len(products), 1)

    def test_amazon_api_defaults_to_US(self):
        """Test Amazon API defaults to the US store."""
        amazon = AmazonAPI(
            AMAZON_ACCESS_KEY,
            AMAZON_SECRET_KEY,
            AMAZON_ASSOC_TAG
        )
        assert_equals(amazon.api.Region, "US")

    def test_search_amazon_uk(self):
        """Test Poduct Search on Amazon UK.

        Tests that a product search on Amazon UK is working and that the
        currency of any of the returned products is GBP. The test fails if no
        results were returned.
        """
        amazon = AmazonAPI(
            AMAZON_ACCESS_KEY,
            AMAZON_SECRET_KEY,
            AMAZON_ASSOC_TAG,
            region="UK"
        )
        assert_equals(amazon.api.Region, "UK", "Region has not been set to UK")

        products = amazon.search(Keywords='Kindle', SearchIndex='All')
        currencies = [product.price_and_currency[1] for product in products]
        assert_true(len(currencies), "No products found")

        is_gbp = 'GBP' in currencies
        assert_true(is_gbp, "Currency is not GBP, cannot be Amazon UK, though")

    def test_similarity_lookup(self):
        """Test Similarity Lookup.

        Tests that a similarity lookup for a kindle returns 10 results.
        """
        products = self.amazon.similarity_lookup(ItemId="B0051QVF7A")
        assert_true(len(products) > 5)

    def test_product_attributes(self):
        """Test Product Attributes.

        Tests that all product that are supposed to be accessible are.
        """
        product = self.amazon.lookup(ItemId="B0051QVF7A")
        for attribute in PRODUCT_ATTRIBUTES:
            getattr(product, attribute)

    def test_browse_node_lookup(self):
        """Test Browse Node Lookup.

        Test that a lookup by Brose Node ID returns appropriate node.
        """
        bnid = 2642129011
        bn = self.amazon.browse_node_lookup(BrowseNodeId=bnid)[0]
        assert_equals(bn.id, bnid)
        assert_equals(bn.name, 'eBook Readers')
        assert_equals(bn.is_category_root, False)

    def test_obscure_date(self):
        """Test Obscure Date Formats

        Test a product with an obscure date format
        """
        product = self.amazon.lookup(ItemId="0933635869")
        assert_equals(product.publication_date.year, 1992)
        assert_equals(product.publication_date.month, 5)
        assert_true(isinstance(product.publication_date, datetime.date))

    def test_single_creator(self):
        """Test a product with a single creator
        """
        product = self.amazon.lookup(ItemId="B00005NZJA")
        creators = dict(product.creators)
        assert_equals(creators[u"Jonathan Davis"], u"Narrator")
        assert_equals(len(creators.values()), 1)

    def test_multiple_creators(self):
        """Test a product with multiple creators
        """
        product = self.amazon.lookup(ItemId="B007V8RQC4")
        creators = dict(product.creators)
        assert_equals(creators[u"John Gregory Betancourt"], u"Editor")
        assert_equals(creators[u"Colin Azariah-Kribbs"], u"Editor")
        assert_equals(len(creators.values()), 2)

    def test_no_creators(self):
        """Test a product with no creators
        """
        product = self.amazon.lookup(ItemId="8420658537")
        assert_false(product.creators)

    def test_single_editorial_review(self):
        product = self.amazon.lookup(ItemId="1930846258")
        expected = u'In the title piece, Alan Turing'
        assert_equals(product.editorial_reviews[0][:len(expected)], expected)
        assert_equals(product.editorial_review, product.editorial_reviews[0])
        assert_equals(len(product.editorial_reviews), 1)

    def test_multiple_editorial_reviews(self):
        product = self.amazon.lookup(ItemId="B000FBJCJE")
        expected = u'Only once in a great'
        assert_equals(product.editorial_reviews[0][:len(expected)], expected)
        expected = u'From the opening line'
        assert_equals(product.editorial_reviews[1][:len(expected)], expected)
        # duplicate data, amazon user data is great...
        expected = u'Only once in a great'
        assert_equals(product.editorial_reviews[2][:len(expected)], expected)

        assert_equals(len(product.editorial_reviews), 3)

    def test_languages_english(self):
        """Test Language Data

        Test an English product
        """
        product = self.amazon.lookup(ItemId="1930846258")
        assert_true('english' in product.languages)
        assert_equals(len(product.languages), 1)

    def test_languages_spanish(self):
        """Test Language Data

        Test an English product
        """
        product = self.amazon.lookup(ItemId="8420658537")
        assert_true('spanish' in product.languages)
        assert_equals(len(product.languages), 1)

########NEW FILE########
