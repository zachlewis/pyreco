__FILENAME__ = admin
""" Add ADRest related models to Django admin.
"""
from django.contrib import admin


try:
    from .models import Access

    class AccessAdmin(admin.ModelAdmin):
        list_display = (
            'created_at',
            'identifier',
            'method',
            'status_code',
            'uri',
            'version'
        )
        list_filter = 'method', 'version'
        search_fields = 'uri', 'identifier'
        date_hierarchy = 'created_at'

    admin.site.register(Access, AccessAdmin)

except ImportError:
    pass


try:
    from .models import AccessKey

    class AccessKeyAdmin(admin.ModelAdmin):
        list_display = 'key', 'user', 'created'
        search_fields = '=key', '=user'
        raw_id_fields = 'user',

    admin.site.register(AccessKey, AccessKeyAdmin)

except ImportError:
    pass

########NEW FILE########
__FILENAME__ = api
"""
You can use :class:`adrest.Api` for bind multiple :class:`adrest.ResourceView`
together with version prefix.

Create API
----------

Default use: ::

    from adrest.api import Api
    from myresources import Resource1, Resource2

    api = Api('0.1')


Register a resource
-------------------
After creation you can register some resources with that Api. ::

    api.register(Resource1)
    api.register(Resource2)

You can use `api.register` method as decorator: ::

    @api.register
    class SomeResource():
        ...


Enable API Map
--------------

You can enable API Map for quick reference on created resources. Use `api_map`
param. ::

    api = Api('1.0b', api_map=True)

By default access to map is anonimous. If you want use a custom authenticator
register map resource by manualy. ::

    from adrest.resources.map import MapResource

    api = Api('1.0')
    api.register(MapResource, authenticators=UserLoggedInAuthenticator)


Auto JSONRPC from REST
----------------------

If you are created some REST api with adrest, you already have JSON RPC too.
Use `api_rpc` param. ::

    api = Api('1.0', api_rpc=True)


"""
import logging

from django.conf.urls import patterns
from django.dispatch import Signal
from django.http import HttpRequest

from .resources.map import MapResource
from .resources.rpc import AutoJSONRPC
from .views import ResourceView
from .utils import exceptions, status, emitter


__all__ = 'Api',


logger = logging.getLogger('adrest')


class Api(object):

    """ Implements a registry to tie together resources that make up an API.

    Especially useful for navigation, providing multiple versions of your
    API.

    :param version: Version info as string or iterable.
    :param api_map: Enable :ref:`apimap`
    :param api_prefix: Prefix for URL and URL-name
    :param api_rpc: Enable :ref:`jsonrpc`
    :param **meta: Redefine Meta options for resource classes

    """

    def __init__(self, version=None, api_map=True, api_prefix='api',
                 api_rpc=False, **meta):
        self.version = self.str_version = version
        self.prefix = api_prefix
        self.resources = dict()
        self.request_started = Signal()
        self.request_finished = Signal()

        if not isinstance(self.str_version, basestring):
            try:
                self.str_version = '.'.join(map(str, version or list()))
            except TypeError:
                self.str_version = str(version)

        self.meta = dict()

        if api_map:
            self.register(MapResource)

        if api_rpc:
            self.register(AutoJSONRPC, emitters=[
                emitter.JSONPEmitter, emitter.JSONEmitter
            ])

        self.meta = meta

    def __str__(self):
        return self.str_version

    def register(self, resource=None, **meta):
        """ Add resource to the API.

        :param resource: Resource class for registration
        :param **meta: Redefine Meta options for the resource

        :return adrest.views.Resource: Generated resource.

        """
        if resource is None:
            def wrapper(resource):
                return self.register(resource, **meta)
            return wrapper

        # Must be instance of ResourceView
        if not issubclass(resource, ResourceView):
            raise AssertionError("%s not subclass of ResourceView" % resource)

        # Cannot be abstract
        if resource._meta.abstract:
            raise AssertionError("Attempt register of abstract resource: %s."
                                 % resource)

        # Fabric of resources
        meta = dict(self.meta, **meta)
        meta['name'] = meta.get('name', resource._meta.name)
        options = type('Meta', tuple(), meta)

        params = dict(api=self, Meta=options, **meta)

        params['__module__'] = '%s.%s' % (
            self.prefix, self.str_version.replace('.', '_'))

        params['__doc__'] = resource.__doc__

        new_resource = type(
            '%s%s' % (resource.__name__, len(self.resources)),
            (resource,), params)

        if self.resources.get(new_resource._meta.url_name):
            logger.warning(
                "A resource '%r' is replacing the existing record for '%s'",
                new_resource, self.resources.get(new_resource._meta.url_name))

        self.resources[new_resource._meta.url_name] = new_resource

        return resource

    @property
    def urls(self):
        """ Provide URLconf details for the ``Api``.

        And all registered ``Resources`` beneath it.

            :return list: URL's patterns

        """
        urls = []

        for url_name in sorted(self.resources.keys()):

            resource = self.resources[url_name]
            urls.append(resource.as_url(
                api=self,
                name_prefix='-'.join(
                    (self.prefix, self.str_version)).strip('-'),
                url_prefix=self.str_version
            ))

        return patterns(self.prefix, *urls)

    def call(self, name, request=None, **params):
        """ Call resource by ``Api`` name.

        :param name: The resource's name (short form)
        :param request: django.http.Request instance
        :param **params: Params for a resource's call

        :return object: Result of resource's execution

        """
        if not name in self.resources:
            raise exceptions.HttpError('Unknown method \'%s\'' % name,
                                       status=status.HTTP_501_NOT_IMPLEMENTED)
        request = request or HttpRequest()
        resource = self.resources[name]
        view = resource.as_view(api=self)
        return view(request, **params)

    @property
    def testCase(self):
        """ Generate class for testing this API.

        :return TestCase: A testing class

        """
        from adrest.tests import AdrestTestCase

        return type('TestCase', (AdrestTestCase, ), dict(api=self))


# lint_ignore=W0212

########NEW FILE########
__FILENAME__ = forms
""" Default ADRest form for Django models. """
from django.db.models import Model
from django.db.models.fields import AutoField
from django.db.models.fields.related import ManyToManyField
from django.forms.models import ModelForm


class PartitialForm(ModelForm):

    """ Default ADRest form for models.

    Allows partitial updates and parses a finded resources.

    """

    def __init__(self, data=None, instance=None, initial=None, prefix=None,
                 label_suffix=':', empty_permitted=False, **kwargs):

        formdata = self.__get_initial_from_model(instance)
        formdata.update(data or dict())

        resources = dict((k, v if not isinstance(
            v, Model) else v.pk) for k, v in kwargs.iteritems())
        formdata.update(resources)

        super(PartitialForm, self).__init__(
            formdata, instance=instance, prefix=prefix,
            label_suffix=label_suffix, empty_permitted=empty_permitted)

    def __get_initial_from_model(self, instance):
        required_fields = [
            f for f in self._meta.model._meta.fields
            if not isinstance(f, (ManyToManyField, AutoField))
        ]

        gen = (
            (f.name, f.value_from_object(instance) if instance
             else f.get_default()) for f in required_fields
        )
        return dict(item for item in gen if not item[1] is None)


# lint_ignore=W0212,R0924

########NEW FILE########
__FILENAME__ = auth
""" ADRest authentication support.
"""
from ..settings import ADREST_ALLOW_OPTIONS
from ..utils import status
from ..utils.meta import MixinBaseMeta
from ..utils.auth import AnonimousAuthenticator, AbstractAuthenticator
from ..utils.exceptions import HttpError
from ..utils.tools import as_tuple


__all__ = 'AuthMixin',


class AuthMeta(MixinBaseMeta):

    """ Convert cls.meta.authenticators to tuple and check them. """

    def __new__(mcs, name, bases, params):
        cls = super(AuthMeta, mcs).__new__(mcs, name, bases, params)

        cls._meta.authenticators = as_tuple(cls._meta.authenticators)

        if not cls._meta.authenticators:
            raise AssertionError(
                "Should be defined at least one authenticator.")

        for a in cls._meta.authenticators:
            if not issubclass(a, AbstractAuthenticator):
                raise AssertionError(
                    "Meta.authenticators should be subclasses of "
                    "`adrest.utils.auth.AbstractAuthenticator`"
                )

        return cls


class AuthMixin(object):

    """ Adds pluggable authentication behaviour. """

    __metaclass__ = AuthMeta

    class Meta:
        authenticators = AnonimousAuthenticator

    def __init__(self, *args, **kwargs):
        self.auth = None

    def authenticate(self, request):
        """ Attempt to authenticate the request.

        :param request: django.http.Request instance

        :return bool: True if success else raises HTTP_401

        """
        authenticators = self._meta.authenticators

        if request.method == 'OPTIONS' and ADREST_ALLOW_OPTIONS:
            self.auth = AnonimousAuthenticator(self)
            return True

        error_message = "Authorization required."
        for authenticator in authenticators:
            auth = authenticator(self)
            try:
                if not auth.authenticate(request):
                    raise AssertionError(error_message)

                self.auth = auth
                auth.configure(request)
                return True
            except AssertionError, e:
                error_message = str(e)

        raise HttpError(error_message, status=status.HTTP_401_UNAUTHORIZED)

    def check_rights(self, resources, request=None):
        """ Check rights for resources.

        :return bool: True if operation is success else HTTP_403_FORBIDDEN

        """
        if not self.auth:
            return True

        try:
            if not self.auth.test_rights(resources, request=request):
                raise AssertionError()

        except AssertionError, e:
            raise HttpError(
                "Access forbiden. {0}".format(e),
                status=status.HTTP_403_FORBIDDEN
            )

########NEW FILE########
__FILENAME__ = dynamic
""" Filters and sorting support. """
from django.core.exceptions import FieldError
from logging import getLogger

from ..settings import ADREST_LIMIT_PER_PAGE
from ..utils import UpdatedList
from ..utils.meta import MixinBaseMeta, MixinBase
from ..utils.paginator import Paginator


logger = getLogger('django.request')

# Separator used to split filter strings apart.
LOOKUP_SEP = '__'


class Meta:

    """ Options for dynamic mixin.

    Setup parameters for filtering and sorting a resources.

    ::
        class SomeResource(DynamicMixin, View):

            class Meta:
                dyn_prefix = 'dyn-'

    """

    #: Prefix for dynamic fields
    dyn_prefix = 'adr-'

    #: Limit per page for pagination
    #: Set to `0` for disable pagination in resource, but user can still force
    #: it with `?max=...`
    limit_per_page = ADREST_LIMIT_PER_PAGE

    #: Define queryset for resource's operation.
    #: By default: self.Meta.model.objects.all()
    queryset = None


class DynamicMixinMeta(MixinBaseMeta):

    """ Prepare dynamic class. """

    def __new__(mcs, name, bases, params):

        cls = super(DynamicMixinMeta, mcs).__new__(mcs, name, bases, params)

        if not cls._meta.dyn_prefix:
            raise AssertionError("Resource.Meta.dyn_prefix should be defined.")

        if cls._meta.model and cls._meta.queryset is None:
            cls._meta.queryset = cls._meta.model.objects.all()

        return cls


class DynamicMixin(MixinBase):

    """ Implement filters and sorting.

    ADRest DynamicMixin supports filtering and sorting collection from query
    params.

    """

    __metaclass__ = DynamicMixinMeta

    Meta = Meta

    def __init__(self, *args, **kwargs):
        """ Copy self queryset for prevent query caching. """

        super(DynamicMixin, self).__init__(*args, **kwargs)

        if not self._meta.queryset is None:
            self._meta.queryset = self._meta.queryset.all()

    def get_collection(self, request, **resources):
        """ Get filters and return filtered result.

        :return collection: collection of related resources.

        """

        if self._meta.queryset is None:
            return []

        # Filter collection
        filters = self.get_filters(request, **resources)
        filters.update(self.get_default_filters(**resources))
        qs = self._meta.queryset
        for key, (value, exclude) in filters.items():
            try:
                if exclude:
                    qs = qs.exclude(**{key: value})

                else:
                    qs = qs.filter(**{key: value})
            except FieldError, e:
                logger.warning(e)

        sorting = self.get_sorting(request, **resources)
        if sorting:
            qs = qs.order_by(*sorting)

        return qs

    def get_default_filters(self, **resources):
        """ Return default filters by a model fields.

        :return dict: name, field

        """
        return dict((k, (v, False)) for k, v in resources.items()
                    if k in self._meta.fields)

    def get_filters(self, request, **resources):
        """ Make filters from GET variables.

        :return dict: filters

        """
        filters = dict()

        if not self._meta.fields:
            return filters

        for field in request.GET.iterkeys():
            tokens = field.split(LOOKUP_SEP)
            field_name = tokens[0]

            if not field_name in self._meta.fields:
                continue

            exclude = False
            if tokens[-1] == 'not':
                exclude = True
                tokens.pop()

            converter = self._meta.model._meta.get_field(
                field_name).to_python if len(tokens) == 1 else lambda v: v
            value = map(converter, request.GET.getlist(field))

            if len(value) > 1:
                tokens.append('in')
            else:
                value = value.pop()

            filters[LOOKUP_SEP.join(tokens)] = (value, exclude)

        return filters

    def get_sorting(self, request, **resources):
        """ Get sorting options.

        :return list: sorting order

        """
        sorting = []

        if not request.GET:
            return sorting

        prefix = self._meta.dyn_prefix + 'sort'
        return request.GET.getlist(prefix)

    def paginate(self, request, collection):
        """ Paginate collection.

        :return object: Collection or paginator

        """
        p = Paginator(request, self, collection)
        return p.paginator and p or UpdatedList(collection)

########NEW FILE########
__FILENAME__ = emitter
""" ADRest serialization support. """
import mimeparse
from django.http import HttpResponse

from ..utils.emitter import JSONEmitter, BaseEmitter
from ..utils.meta import MixinBaseMeta
from ..utils.paginator import Paginator
from ..utils.tools import as_tuple


__all__ = 'EmitterMixin',


class Meta:

    """ Emitter options. Setup parameters for resource's serialization.

    ::

        class SomeResource(EmitterMixin, View):

            class Meta:
                emitters = JSONEmitter

    """

    #: :class:`adrest.utils.Emitter` (or collection of them)
    #: Defined available emitters for resource.
    #: ::
    #:
    #:     class SomeResource(EmitterMixin, View):
    #:         class Meta:
    #:             emitters = JSONEmitter, XMLEmitter
    #:
    emitters = JSONEmitter

    #: Options for low-level serialization
    #: Example for JSON serialization
    #:
    #: ::
    #:
    #:     class SomeResource(EmitterMixin, View):
    #:         class Meta:
    #:             emit_options = dict(indent=2, sort_keys=True)
    #:
    emit_options = None

    #: Dictionary with emitter's options for relations
    #:
    #: * emit_models['fields'] -- Set serialized fields by manual
    #: * emit_models['exclude'] -- Exclude some fields
    #: * emit_models['include'] -- Include some fields
    #: * emit_models['related'] -- Options for relations.
    #:
    #: Example: ::
    #:
    #:     class SomeResource(EmitterMixin, View):
    #:         class Meta:
    #:             model = Role
    #:             emit_models = dict(
    #:                  include = 'group_count',
    #:                  exclude = ['password', 'service'],
    #:                  related = dict(
    #:                      user = dict(
    #:                          fields = 'username'
    #:                      )
    #:                  )
    #:
    #:              )

    #: You can use a shortcuts for `emit_models` option, as is `emit_fields` or
    #: `emit_include`. That same as bellow::
    #:
    #:     class SomeResource(EmitterMixin, View):
    #:         class Meta:
    #:             model = Role
    #:             emit_include = 'group_count'
    #:             emit_exclude = 'password', 'service'
    #:             emit_related = dict(
    #:                 user = dict(
    #:                         fields = 'username'
    #:                 )
    #:             )
    emit_models = None

    #: Define template for template-based emitters by manualy
    #: Otherwise template name will be generated from resource name
    #: (or resource.Meta.model)
    emit_template = None

    #: Serialization format. Set 'django' for django like view:

    #: ::
    #:
    #:     {
    #:         'pk': ...,
    #:         'model': ...,
    #:         'fields': {
    #:             'name': ...,
    #:             ...
    #:         }
    #:     }
    #:
    #: Or set 'simple' for simpliest serialization:
    #: ::
    #:
    #:     {
    #:         'id': ...,
    #:         'name': ...,
    #:     }
    #:
    emit_format = 'django'


class EmitterMeta(MixinBaseMeta):

    """ Prepare resource's emiters. """

    def __new__(mcs, name, bases, params):
        cls = super(EmitterMeta, mcs).__new__(mcs, name, bases, params)

        cls._meta.emitters = as_tuple(cls._meta.emitters)
        cls._meta.emitters_dict = dict(
            (e.media_type, e) for e in cls._meta.emitters
        )
        if not cls._meta.emitters:
            raise AssertionError("Should be defined at least one emitter.")

        for e in cls._meta.emitters:
            if not issubclass(e, BaseEmitter):
                raise AssertionError(
                    "Emitter should be subclass of "
                    "`adrest.utils.emitter.BaseEmitter`"
                )

        if cls._meta.emit_models is None:
            cls._meta.emit_models = dict()

        if cls._meta.emit_include:
            cls._meta.emit_models['include'] = cls._meta.emit_include

        if cls._meta.emit_exclude:
            cls._meta.emit_models['exclude'] = cls._meta.emit_exclude

        if cls._meta.emit_fields:
            cls._meta.emit_models['fields'] = cls._meta.emit_fields

        if cls._meta.emit_related:
            cls._meta.emit_models['related'] = cls._meta.emit_related

        return cls


class EmitterMixin(object):

    """ Serialize response.

    .. autoclass:: adrest.mixin.emitter.Meta
       :members:

    Example: ::

        class SomeResource():
            class Meta:
                emit_fields = ['pk', 'user', 'customfield']
                emit_related = {
                    'user': {
                        fields: ['username']
                    }
                }

            def to_simple__customfield(self, user):
                return "I'm hero! " + user.username

    """

    __metaclass__ = EmitterMeta

    # Set default options
    Meta = Meta

    def emit(self, content, request=None, emitter=None):
        """ Serialize response.

        :return response: Instance of django.http.Response

        """
        # Get emitter for request
        emitter = emitter or self.determine_emitter(request)
        emitter = emitter(self, request=request, response=content)

        # Serialize the response content
        response = emitter.emit()

        if not isinstance(response, HttpResponse):
            raise AssertionError("Emitter must return HttpResponse")

        # Append pagination headers
        if isinstance(content, Paginator):
            linked_resources = []
            if content.next_page:
                linked_resources.append('<{0}>; rel="next"'.format(
                    content.next_page))
            if content.previous_page:
                linked_resources.append(
                    '<{0}>; rel="previous"'.format(content.previous_page))
            response["Link"] = ", ".join(linked_resources)

        return response

    @staticmethod
    def to_simple(content, simple, serializer=None):
        """ Abstract method for modification a structure before serialization.

        :param content: response from called method
        :param simple: structure is prepared to serialization
        :param serializer: current serializer

        :return object: structure for serialization

        ::

            class SomeResource(ResourceView):
                def get(self, request, **resources):
                    return dict(true=False)

                def to_simple(self, content, simple, serializer):
                    simple['true'] = True
                    return simple

        """
        return simple

    @classmethod
    def determine_emitter(cls, request):
        """ Get emitter for request.

        :return emitter: Instance of adrest.utils.emitters.BaseEmitter

        """
        default_emitter = cls._meta.emitters[0]
        if not request:
            return default_emitter

        if request.method == 'OPTIONS':
            return JSONEmitter

        accept = request.META.get('HTTP_ACCEPT', '*/*')
        if accept == '*/*':
            return default_emitter

        base_format = mimeparse.best_match(cls._meta.emitters_dict.keys(),
                                           accept)
        return cls._meta.emitters_dict.get(
            base_format,
            default_emitter)

########NEW FILE########
__FILENAME__ = handler
""" Implement REST functionality. """
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.http import HttpResponse
from logging import getLogger

from ..forms import PartitialForm
from ..settings import ADREST_ALLOW_OPTIONS
from ..utils import status, UpdatedList
from ..utils.exceptions import HttpError, FormError
from ..utils.tools import as_tuple
from .dynamic import DynamicMixin, DynamicMixinMeta


__all__ = 'HandlerMixin',

logger = getLogger('django.request')


__all__ = 'HandlerMixin',


class Meta:

    """ Handler options. Setup parameters for REST implementation.

    ::

        class SomeResource(HandlerMixin, View):

            class Meta:
                allowed_methods = 'get', 'post'
                model = 'app.model'

    """

    #: List of allowed methods (or simple one)
    allowed_methods = 'GET',

    #: Map HTTP methods to handler methods
    callmap = dict(
        (m.upper(), m) for m in (
            'get', 'post', 'put', 'delete', 'patch', 'options', 'head')
    )

    #: Set form for resource by manual
    form = None

    #: Specify field's names for automatic a model form
    form_fields = None

    #: Exclude field's names for automatic a model form
    form_exclude = None


class HandlerMeta(DynamicMixinMeta):

    """ Prepare handler class. """

    def __new__(mcs, name, bases, params):

        cls = super(HandlerMeta, mcs).__new__(mcs, name, bases, params)

        # Prepare allowed methods
        cls._meta.allowed_methods = mcs.__prepare_methods(
            cls._meta.allowed_methods)

        if not cls._meta.model:
            return cls

        cls._meta.name = cls._meta.name or cls._meta.model._meta.module_name

        # Create form if not exist
        if not cls._meta.form:

            class DynForm(PartitialForm):

                class Meta:
                    model = cls._meta.model
                    fields = cls._meta.form_fields
                    exclude = cls._meta.form_exclude

            cls._meta.form = DynForm

        return cls

    @staticmethod
    def __prepare_methods(methods):

        methods = tuple([str(m).upper() for m in as_tuple(methods)])

        if not 'OPTIONS' in methods and ADREST_ALLOW_OPTIONS:
            methods += 'OPTIONS',

        if not 'HEAD' in methods and 'GET' in methods:
            methods += 'HEAD',

        return methods


class HandlerMixin(DynamicMixin):

    """ Implement REST API.


    .. autoclass:: adrest.mixin.handler.Meta
       :members:

    Example: ::

        class SomeResource(HandlerMixin, View):

            class Meta:
                allowed_methods = 'get', 'post'
                model = 'app.model'

            def dispatch(self, request, **resources):

                self.check_method_allowed(request)

                resources = self.get_resources(request, **resources)

                return self.handle_request(request, **resources)

    """

    __metaclass__ = HandlerMeta

    Meta = Meta

    def handle_request(self, request, **resources):
        """ Get a method for request and execute.

        :return object: method result

        """
        if not request.method in self._meta.callmap.keys():
            raise HttpError(
                'Unknown or unsupported method \'%s\'' % request.method,
                status=status.HTTP_501_NOT_IMPLEMENTED)

        # Get the appropriate create/read/update/delete function
        view = getattr(self, self._meta.callmap[request.method])

        # Get function data
        return view(request, **resources)

    @staticmethod
    def head(*args, **kwargs):
        """ Just return empty response.

        :return django.http.Response: empty response.

        """

        return HttpResponse()

    def get(self, request, **resources):
        """ Default GET method. Return instance (collection) by model.

        :return object: instance or collection from self model

        """

        instance = resources.get(self._meta.name)
        if not instance is None:
            return instance

        return self.paginate(
            request, self.get_collection(request, **resources))

    def post(self, request, **resources):
        """ Default POST method. Uses the handler's form.

        :return object: saved instance or raise form's error

        """
        if not self._meta.form:
            return None

        form = self._meta.form(request.data, **resources)
        if form.is_valid():
            return form.save()

        raise FormError(form)

    def put(self, request, **resources):
        """ Default PUT method. Uses self form. Allow bulk update.

        :return object: changed instance or raise form's error

        """
        if not self._meta.form:
            return None

        if not self._meta.name in resources or not resources[self._meta.name]:
            raise HttpError(
                "Resource not found.", status=status.HTTP_404_NOT_FOUND)
        resource = resources.pop(self._meta.name)

        updated = UpdatedList()
        for o in as_tuple(resource):
            form = self._meta.form(data=request.data, instance=o, **resources)

            if not form.is_valid():
                raise FormError(form)

            updated.append(form.save())

        return updated if len(updated) > 1 else updated[-1]

    def delete(self, request, **resources):
        """ Default DELETE method. Allow bulk delete.

        :return django.http.response: empty response

        """

        resource = resources.get(self._meta.name)
        if not resource:
            raise HttpError("Bad request", status=status.HTTP_404_NOT_FOUND)

        for o in as_tuple(resource):
            o.delete()

        return HttpResponse("")

    def patch(self, request, **resources):
        """ Default PATCH method.

        :return object: changed instance or raise form's error

        """
        return self.put(request, **resources)

    @staticmethod
    def options(request, **resources):
        """ Default OPTIONS method.

        :return django.http.response: 'OK' response

        """

        return HttpResponse("OK")

    @classmethod
    def check_method_allowed(cls, request):
        """ Ensure the request HTTP method is permitted for this resource.

        Raising a ResourceException if it is not.

        """
        if not request.method in cls._meta.allowed_methods:
            raise HttpError(
                'Method \'%s\' not allowed on this resource.' % request.method,
                status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def get_resources(self, request, **resources):
        """ Parse resource objects from URL and request.

        :return dict: Resources.

        """

        if self.parent:
            resources = self.parent.get_resources(request, **resources)

        pks = (
            resources.get(self._meta.name) or
            request.REQUEST.getlist(self._meta.name) or
            getattr(request, 'data', None) and request.data.get(
                self._meta.name))

        if not pks or self._meta.queryset is None:
            return resources

        pks = as_tuple(pks)

        try:
            if len(pks) == 1:
                resources[self._meta.name] = self._meta.queryset.get(pk=pks[0])

            else:
                resources[self._meta.name] = self._meta.queryset.filter(
                    pk__in=pks)

        except (ObjectDoesNotExist, ValueError, AssertionError):
            raise HttpError("Resource not found.",
                            status=status.HTTP_404_NOT_FOUND)

        except MultipleObjectsReturned:
            raise HttpError("Resources conflict.",
                            status=status.HTTP_409_CONFLICT)

        return resources


# pymode:lint_ignore=E1102,W0212,R0924

########NEW FILE########
__FILENAME__ = parser
""" ADRest parse data. """
from ..utils.meta import MixinBaseMeta
from ..utils.parser import FormParser, XMLParser, JSONParser, AbstractParser
from ..utils.tools import as_tuple

__all__ = 'ParserMixin',


class ParserMeta(MixinBaseMeta):

    """ Prepare resource's parsers. """

    def __new__(mcs, name, bases, params):
        cls = super(ParserMeta, mcs).__new__(mcs, name, bases, params)

        cls._meta.parsers = as_tuple(cls._meta.parsers)
        if not cls._meta.parsers:
            raise AssertionError("Should be defined at least one parser.")

        cls._meta.default_parser = cls._meta.parsers[0]
        cls._meta.parsers_dict = dict()

        for p in cls._meta.parsers:
            if not issubclass(p, AbstractParser):
                raise AssertionError(
                    "Parser must be subclass of AbstractParser.")

            cls._meta.parsers_dict[p.media_type] = p

        return cls


class ParserMixin(object):

    """ Parse user data. """

    __metaclass__ = ParserMeta

    class Meta:
        parsers = FormParser, XMLParser, JSONParser

    def parse(self, request):
        """ Parse request content.

        :return dict: parsed data.

        """
        if request.method in ('POST', 'PUT', 'PATCH'):
            content_type = self.determine_content(request)
            if content_type:
                split = content_type.split(';', 1)
                if len(split) > 1:
                    content_type = split[0]
                content_type = content_type.strip()

            parser = self._meta.parsers_dict.get(
                content_type, self._meta.default_parser)
            data = parser(self).parse(request)
            return dict() if isinstance(data, basestring) else data
        return dict()

    @staticmethod
    def determine_content(request):
        """ Determine request content.

        :return str: request content type

        """

        if not request.META.get('CONTENT_LENGTH', None) \
           and not request.META.get('TRANSFER_ENCODING', None):
            return None

        return request.META.get('CONTENT_TYPE', None)

########NEW FILE########
__FILENAME__ = throttle
""" Safe API. """
from ..utils import status
from ..utils.meta import MixinBaseMeta
from ..utils.exceptions import HttpError
from ..utils.throttle import NullThrottle, AbstractThrottle

__all__ = 'ThrottleMixin',


class ThrottleMeta(MixinBaseMeta):

    """ Prepare throtles. """

    def __new__(mcs, name, bases, params):
        cls = super(ThrottleMeta, mcs).__new__(mcs, name, bases, params)

        if not issubclass(cls._meta.throttle, AbstractThrottle):
            raise AssertionError(
                "'cls.Meta.throttle' must be subclass of AbstractThrottle"
            )

        return cls


class ThrottleMixin(object):

    """ Throttle request. """

    __metaclass__ = ThrottleMeta

    class Meta:
        throttle = NullThrottle

    def throttle_check(self):
        """ Check for throttling. """
        throttle = self._meta.throttle()
        wait = throttle.should_be_throttled(self)
        if wait:
            raise HttpError(
                "Throttled, wait {0} seconds.".format(wait),
                status=status.HTTP_503_SERVICE_UNAVAILABLE)

########NEW FILE########
__FILENAME__ = models
""" ASRest related models. """
from django.db import models
from django.utils.encoding import smart_unicode

from . import settings
from .signals import api_request_finished


# Preloads ADREST tags
try:
    from django.template.base import builtins
    from .templatetags import register

    builtins.append(register)

except ImportError:
    pass


# Access log
# -----------
if settings.ADREST_ACCESS_LOG:

    class Access(models.Model):
        """ Log api queries.
        """
        created_at = models.DateTimeField(auto_now_add=True)
        uri = models.CharField(max_length=100)
        status_code = models.PositiveIntegerField()
        version = models.CharField(max_length=25)
        method = models.CharField(max_length=10, choices=(
            ('GET', 'GET'),
            ('POST', 'POST'),
            ('PUT', 'PUT'),
            ('DELETE', 'DELETE'),
            ('OPTIONS', 'OPTIONS'),
        ))
        request = models.TextField()
        response = models.TextField()
        identifier = models.CharField(max_length=255)

        class Meta():
            ordering = ["-created_at"]
            verbose_name_plural = "Access"

        def __unicode__(self):
            return "#{0} {1}:{2}:{3}".format(
                self.pk, self.method, self.status_code, self.uri)

    def save_log(sender, response=None, request=None, **resources):

        resource = sender

        if not resource._meta.log:
            return

        try:
            content = smart_unicode(response.content)[:5000]
        except (UnicodeDecodeError, UnicodeEncodeError):
            if response and response['Content-Type'].lower() not in \
                    [emitter.media_type.lower()
                        for emitter in resource.emitters]:
                content = 'Invalid response content encoding'
            else:
                content = response.content[:5000]

        Access.objects.create(
            uri=request.path_info,
            method=request.method,
            version=str(resource.api or ''),
            status_code=response.status_code,
            request='%s\n\n%s' % (str(request.META), str(
                getattr(request, 'data', ''))),
            identifier=resource.identifier or request.META.get(
                'REMOTE_ADDR', 'anonymous'),
            response=content)

    api_request_finished.connect(save_log)


# Access keys
# -----------
if settings.ADREST_ACCESSKEY:

    import uuid
    from django.contrib.auth.models import User

    class AccessKey(models.Model):
        """ API key.
        """
        key = models.CharField(max_length=40, blank=True)
        user = models.ForeignKey(User)
        created = models.DateTimeField(auto_now_add=True)

        class Meta():
            ordering = ["-created"]
            unique_together = 'user', 'key'

        def __unicode__(self):
            return u'#%s %s "%s"' % (self.pk, self.user, self.key)

        def save(self, **kwargs):
            self.key = self.key or str(uuid.uuid4()).replace('-', '')
            super(AccessKey, self).save(**kwargs)

    # Auto create key for created user
    def create_api_key(sender, created=False, instance=None, **kwargs):
        if created and instance:
            AccessKey.objects.create(user=instance)

    # Connect create handler to user save event
    if settings.ADREST_AUTO_CREATE_ACCESSKEY:
        models.signals.post_save.connect(create_api_key, sender=User)


# pymode:lint_ignore=W0704

########NEW FILE########
__FILENAME__ = ga
""" Proxy request to Google Analytics. """
from pyga.requests import Tracker, Visitor, Session, Page

from ..views import ResourceView


__all__ = 'GaResource',


class GaResource(ResourceView):

    """ Google Analytics support.

    Track GA from server.

    Example: ::

        api.register(GaResource, account_id="UA-123456", domain="test")

    """

    class Meta:
        url_regex = r'^ga(?P<path>.*)$'
        domain = None
        account_id = None

    def get(self, request, path=None, **resources):
        """ Proxy request to GA. """
        tracker = Tracker(
            self._meta.account_id,
            self._meta.domain or request.META.get('SERVER_NAME'))
        visitor = Visitor()
        visitor.extract_from_server_meta(request.META)
        session = Session()
        page = Page(path)
        tracker.track_pageview(page, session, visitor)

# lint_ignore=F0401

########NEW FILE########
__FILENAME__ = map
""" Generate a resource's map. """
from django.forms.models import ModelChoiceField
from django.utils.encoding import smart_unicode

from ..settings import ADREST_MAP_TEMPLATE
from ..utils.auth import AnonimousAuthenticator
from ..utils.emitter import HTMLTemplateEmitter, JSONEmitter
from ..views import ResourceView


__all__ = 'MapResource',


class MapResource(ResourceView):

    """ Simple Api Map. """

    class Meta:
        authenticators = AnonimousAuthenticator
        emit_template = ADREST_MAP_TEMPLATE
        emitters = HTMLTemplateEmitter, JSONEmitter
        log = False
        url_regex = r'^map$'

    def get(self, *args, **Kwargs):
        """ Render map.

        :return list: list of resources.

        """
        return list(self.__gen_apimap())

    def __gen_apimap(self):
        for url_name in sorted(self.api.resources.iterkeys()):
            resource = self.api.resources[url_name]
            info = dict(
                resource=resource,
                url_name=resource._meta.url_name,
                allowed_methods=resource._meta.allowed_methods,
                doc=resource.__doc__,
                emitters=', '.join(
                    [e.media_type for e in resource._meta.emitters]),
                fields=[],
                model=None,
            )
            if resource._meta.model:
                info['model'] = dict(
                    name="{0}.{1}".format(
                        resource._meta.model._meta.module_name, # nolint
                        resource._meta.model._meta.object_name, # nolint
                    ),
                    fields=resource._meta.model._meta.fields # nolint
                )

            models = [
                p._meta.model for p in resource._meta.parents if p._meta.model]

            if resource._meta.form and (
                'POST' in resource._meta.allowed_methods
                    or 'PUT' in resource._meta.allowed_methods):
                info['fields'] += [
                    (name, dict(
                        required=f.required and f.initial is None,
                        label=f.label,
                        help=smart_unicode(f.help_text + ''))
                     )
                    for name, f in resource._meta.form.base_fields.iteritems()
                    if not (isinstance(f, ModelChoiceField)
                            and f.choices.queryset.model in models)
                ]

            for a in resource._meta.authenticators:
                info['fields'] += a.get_fields()

            info['auth'] = set(
                a.__doc__ or 'Custom' for a in resource._meta.authenticators)

            key = resource._meta.url_regex\
                .replace("(?P", "")\
                .replace("[^/]+)", "")\
                .replace("?:", "")\
                .replace("$", "")\
                .replace("^", "/")

            if getattr(resource, "methods", None):
                import inspect
                info['methods'] = dict()
                for name, method in resource.methods.items():
                    info['methods'][name] = inspect.getargspec(method)
            yield key, info

# lint_ignore=W0212

########NEW FILE########
__FILENAME__ = rpc
""" RPC support. """
from django.http import QueryDict, HttpResponse
from django.utils import simplejson, importlib

from ..utils.emitter import JSONPEmitter, JSONEmitter
from ..utils.parser import JSONParser, FormParser
from ..utils.tools import as_tuple
from ..utils.response import SerializedHttpResponse
from ..views import ResourceView, ResourceMetaClass


__all__ = 'get_request', 'RPCResource', 'AutoJSONRPC'


def get_request(func):
    """ Mark function as needed in request.

    :return function: marked function.

    """
    func.request = True
    return func


class RPCMeta(ResourceMetaClass):

    """ Setup RPC methods by Scheme. """

    def __new__(mcs, name, bases, params):
        cls = super(RPCMeta, mcs).__new__(mcs, name, bases, params)
        cls.configure_rpc()
        return cls


class RPCResource(ResourceView):

    """ JSON RPC support.

    Implementation of remote procedure call encoded in JSON.
    Allows for notifications (info sent to the server that does not require
    a response) and for multiple calls to be sent to the server which may
    be answered out of order.

    """

    class Meta:
        allowed_methods = 'get', 'post'
        emitters = JSONEmitter, JSONPEmitter
        parsers = JSONParser, FormParser
        scheme = None
        url_regex = r'^rpc$'

    methods = dict()
    scheme_name = ''

    __metaclass__ = RPCMeta

    def __init__(self, scheme=None, **kwargs):
        if scheme:
            self.configure_rpc(scheme)
        super(RPCResource, self).__init__(**kwargs)

    @classmethod
    def configure_rpc(cls, scheme=None):
        """ Get methods from scheme. """
        scheme = scheme or cls._meta.scheme

        if not scheme:
            return

        if isinstance(scheme, basestring):
            scheme = importlib.import_module(scheme)

        cls.scheme_name = scheme.__name__

        methods = getattr(scheme, '__all__', None) \
            or [m for m in dir(scheme) if not m.startswith('_')]

        for mname in methods:
            method = getattr(scheme, mname)
            if hasattr(method, '__call__'):
                cls.methods["{0}.{1}".format(
                    cls.scheme_name, method.__name__)] = method

    def handle_request(self, request, **resources):
        """ Call RPC method.

        :return object: call's result

        """

        if request.method == 'OPTIONS':
            return super(RPCResource, self).handle_request(
                request, **resources)

        payload = request.data

        try:

            if request.method == 'GET':
                payload = request.GET.get('payload')
                try:
                    payload = simplejson.loads(payload)
                except TypeError:
                    raise AssertionError("Invalid RPC Call.")

            if 'method' not in payload:
                raise AssertionError("Invalid RPC Call.")
            return self.rpc_call(request, **payload)

        except Exception, e:
            return SerializedHttpResponse(
                dict(error=dict(message=str(e))),
                error=True
            )

    def rpc_call(self, request, method=None, params=None, **kwargs):
        """ Call a RPC method.

        return object: a result

        """
        args = []
        kwargs = dict()
        if isinstance(params, dict):
            kwargs.update(params)
        else:
            args = list(as_tuple(params))

        method_key = "{0}.{1}".format(self.scheme_name, method)
        if method_key not in self.methods:
            raise AssertionError("Unknown method: {0}".format(method))
        method = self.methods[method_key]

        if hasattr(method, 'request'):
            args.insert(0, request)

        return method(*args, **kwargs)


class AutoJSONRPC(RPCResource):

    """ Automatic JSONRPC Api from REST.

    Automatic Implementation of remote procedure call based on your REST.

    """

    separator = '.'

    class Meta:
        url_name = 'autojsonrpc'

    @staticmethod
    def configure_rpc(scheme=None):
        """ Do nothing. """
        pass

    def rpc_call(self, request, method=None, **payload):
        """ Call REST API with RPC force.

        return object: a result

        """
        if not method or self.separator not in method:
            raise AssertionError("Wrong method name: {0}".format(method))

        resource_name, method = method.split(self.separator, 1)
        if resource_name not in self.api.resources:
            raise AssertionError("Unknown method " + method)

        data = QueryDict('', mutable=True)
        data.update(payload.get('data', dict()))
        data['callback'] = payload.get('callback') or request.GET.get(
            'callback') or request.GET.get('jsonp') or 'callback'
        for h, v in payload.get('headers', dict()).iteritems():
            request.META["HTTP_%s" % h.upper().replace('-', '_')] = v

        request.POST = request.PUT = request.GET = data
        delattr(request, '_request')
        request.method = method.upper()
        request.META['CONTENT_TYPE'] = 'application/x-www-form-urlencoded'
        params = payload.pop('params', dict())
        response = self.api.call(resource_name, request, **params)

        if not isinstance(response, SerializedHttpResponse):
            return response

        if response['Content-type'] in self._meta.emitters_dict:
            return HttpResponse(response.content, status=response.status_code)

        if response.status_code == 200:
            return response.response

        raise AssertionError(response.response)


# pymode:lint_ignore=E1103,W0703

########NEW FILE########
__FILENAME__ = settings
"""
    Configuration
    =============

    You should add ``adrest`` to your ``INSTALLED_APPS`` in Django settings.

    Also you can redefine default **ADRest** settings writen bellow.


"""
try:
    from django.core.exceptions import ImproperlyConfigured
    from django.conf import settings

    getattr(settings, 'DEBUG')

except (ImportError, ImproperlyConfigured):

    settings.configure()

from .utils.tools import as_tuple


#: Enable ADRest API logs. Information about requests and responses will be
#: saved in database.
ADREST_ACCESS_LOG = getattr(settings, 'ADREST_ACCESS_LOG', False)

#: Create `adrest.models.AccessKey` models for authorisation by keys
ADREST_ACCESSKEY = getattr(
    settings, 'ADREST_ACCESSKEY',
    'django.contrib.auth' in getattr(settings, 'INSTALLED_APPS', tuple()))

#: Create AccessKey for Users automaticly
ADREST_AUTO_CREATE_ACCESSKEY = getattr(
    settings, 'ADREST_AUTO_CREATE_ACCESSKEY', False)

#: Set default number resources per page for pagination
#: ADREST_LIMIT_PER_PAGE = 0 -- Disabled pagination by default
ADREST_LIMIT_PER_PAGE = int(getattr(settings, 'ADREST_LIMIT_PER_PAGE', 50))

#: Dont parse a exceptions. Show standart Django 500 page.
ADREST_DEBUG = getattr(settings, 'ADREST_DEBUG', False)

#: List of errors for ADRest's errors mails.
#: Set ADREST_MAIL_ERRORS = None for disable this functionality
ADREST_MAIL_ERRORS = as_tuple(getattr(settings, 'ADREST_MAIL_ERRORS', 500))

#: Set maximum requests per timeframe
ADREST_THROTTLE_AT = getattr(settings, 'ADREST_THROTTLE_AT', 120)

#: Set timeframe length
ADREST_THROTTLE_TIMEFRAME = getattr(settings, 'ADREST_THROTTLE_TIMEFRAME', 60)

#: We do not restrict access for OPTIONS request.
ADREST_ALLOW_OPTIONS = getattr(settings, 'ADREST_ALLOW_OPTIONS', False)

#: Template path for ADRest map
ADREST_MAP_TEMPLATE = getattr(settings, 'ADREST_MAP_TEMPLATE', 'api/map.html')

########NEW FILE########
__FILENAME__ = signals
from django.dispatch import Signal


api_request_started = Signal()
api_request_finished = Signal()

########NEW FILE########
__FILENAME__ = templatetags
""" ADRest inclusion tags. """
from django.template import Library, VariableDoesNotExist
from django.template.base import TagHelperNode, parse_bits
from django.template.loader import get_template


register = Library()

# Fix django templatetags module loader
__path__ = ""


class AdrestInclusionNode(TagHelperNode):

    """ Service class for tags. """

    def render(self, context):
        """ Render node.

        :return str: Rendered string.

        """
        try:
            args, ctx = self.get_resolved_arguments(context)
            target = args[0]
            if not target:
                return ''
            ctx['content'] = target
        except VariableDoesNotExist:
            return ''

        emitter = context.get('emitter')
        t_name = emitter.get_template_path(target)
        t = get_template(t_name)
        context.dicts.append(ctx)
        response = t.nodelist.render(context)
        context.pop()
        return response


def adrest_include(parser, token):
    """ Include adrest_template for any objects.

    :return str: Rendered string.

    """
    bits = token.split_contents()[1:]
    args, kwargs = parse_bits(
        parser, bits, ['content'], 'args', 'kwargs', tuple(),
        False, 'adrest_include')
    return AdrestInclusionNode(False, args, kwargs)
adrest_include = register.tag(adrest_include)


def adrest_jsonify(content, **options):
    """ Serialize any object to JSON .

    :return str: Rendered string.

    """
    from adrest.utils.serializer import JSONSerializer
    worker = JSONSerializer(**options)
    return worker.serialize(content)
adrest_jsonify = register.simple_tag(adrest_jsonify)

########NEW FILE########
__FILENAME__ = utils
""" ADRest test's helpers. """
from StringIO import StringIO
from urlparse import urlparse
from collections import defaultdict

from django.core.urlresolvers import reverse
from django.conf import settings
from django.db.models import Model
from django.test import TestCase, client
from django.utils import simplejson
from django.utils.http import urlencode
from django.utils.functional import curry
from django.utils.encoding import smart_str


__all__ = 'AdrestRequestFactory', 'AdrestClient', 'AdrestTestCase'


def generic_method(
    rf, path, data=None, content_type=client.MULTIPART_CONTENT, follow=False,
        method='PUT', **extra):
    """ Fix django.

    :return request: request

    """

    if content_type is client.MULTIPART_CONTENT:
        data = rf._encode_data(data, content_type)
    else:
        data = smart_str(data, encoding=settings.DEFAULT_CHARSET)

    parsed = urlparse(path)
    r = {
        'CONTENT_LENGTH': len(data),
        'CONTENT_TYPE': content_type,
        'PATH_INFO': rf._get_path(parsed),
        'QUERY_STRING': parsed[4],
        'REQUEST_METHOD': method,
        'wsgi.input': FakePayload(data),
    }
    r.update(extra)
    return rf.request(**r)


class AdrestRequestFactory(client.RequestFactory):

    """ Path methods. """

    put = curry(generic_method, method="PUT")
    patch = curry(generic_method, method="PATCH")


class AdrestClient(client.Client):

    """ Patch client. """

    def put(self, path, data=None, content_type=client.MULTIPART_CONTENT,
            follow=False, method='PUT', **extra):
        """ Implement PUT.

        :return response: A result.

        """

        data = data or dict()
        response = generic_method(
            self, path, data=data, content_type=content_type, follow=follow,
            method=method, **extra)
        if follow:
            response = self._handle_redirects(response, **extra)
        return response

    patch = curry(put, method='PATCH')

    def delete(self, path, data=None, **extra):
        """ Implement DELETE.

        :return response: A result.

        """

        data = data or dict()

        parsed = urlparse(path)
        r = {
            'PATH_INFO':       self._get_path(parsed),
            'QUERY_STRING':    urlencode(data, doseq=True) or parsed[4],
            'REQUEST_METHOD': 'DELETE',
        }
        r.update(extra)
        return self.request(**r)


class AdrestTestCase(TestCase):

    """ TestCase for ADRest related tests. """

    api = None
    client_class = AdrestClient

    @classmethod
    def reverse(cls, resource, **resources):
        """ Reverse resource by ResourceClass or name.

        :param resource: Resource Class or String name.
        :param **resources: Uri params

        :return str: URI string

        """
        if not cls.api:
            raise AssertionError("AdrestTestCase must have the api attribute.")

        if isinstance(resource, basestring):
            url_name = resource
            if not cls.api.resources.get(url_name):
                raise AssertionError("Invalid resource name: %s" % url_name)

        else:
            url_name = resource._meta.url_name

        params = dict()
        query = defaultdict(list)

        for name, resource in resources.items():

            if isinstance(resource, Model):
                resource = resource.pk

            if name in params:
                query[name].append(params[name])
                query[name].append(resource)
                del params[name]
                continue

            params[name] = resource

        name_ver = '' if not str(cls.api) else '%s-' % str(cls.api)
        uri = reverse(
            '%s-%s%s' % (cls.api.prefix, name_ver, url_name), kwargs=params)

        if query:
            uri += '?'
            for name, values in query:
                uri += '&'.join('%s=%s' % (name, value) for value in values)

        return uri

    def get_params(self, resource, headers=None, data=None, key=None, **kwargs):  # nolint
        headers = headers or dict()
        data = data or dict()
        if isinstance(key, Model):
            key = key.key
        headers['HTTP_AUTHORIZATION'] = key or headers.get(
            'HTTP_AUTHORIZATION')
        resource = self.reverse(resource, **kwargs)
        return resource, headers, data

    def get_resource(self, resource, method='get', data=None, headers=None, json=False, **kwargs):  # nolint
        """ Simply run resource method.

        :param resource: Resource Class or String name.
        :param data: Request data
        :param json: Make JSON request
        :param headers: Request headers
        :param key: HTTP_AUTHORIZATION token

        :return object: result

        """
        method = getattr(self.client, method)
        resource, headers, data = self.get_params(
            resource, headers, data, **kwargs)

        # Support JSON request
        if json:
            headers['content_type'] = 'application/json'
            data = simplejson.dumps(data)

        response = method(resource, data=data, **headers)
        return self._jsonify(response)

    def rpc(self, resource, rpc=None, headers=None, callback=None, **kwargs):
        """ Emulate RPC call.

        :param resource: Resource Class or String name.
        :param rpc: RPC params.
        :param headers: Send headers
        :param callback: JSONP callback

        :return object: result

        """
        resource, headers, data = self.get_params(
            resource, headers, data=rpc, **kwargs)

        if callback:
            headers['HTTP_ACCEPT'] = 'text/javascript'
            method = self.client.get
            data = dict(
                callback=callback,
                payload=simplejson.dumps(data))

        else:
            headers['HTTP_ACCEPT'] = 'application/json'
            method = self.client.post
            data = simplejson.dumps(data)

        response = method(
            resource, data=data, content_type='application/json', **headers)
        return self._jsonify(response)

    @staticmethod
    def _jsonify(response):
        if response.get('Content-type') == 'application/json':
            try:
                response.json = simplejson.loads(response.content)
            except ValueError:
                return response
        return response

    put_resource = curry(get_resource, method='put')
    post_resource = curry(get_resource, method='post')
    patch_resource = curry(get_resource, method='patch')
    delete_resource = curry(get_resource, method='delete')


class FakePayload(object):

    """ Fake payload.

    A wrapper around StringIO that restricts what can be read since data from
    the network can't be seeked and cannot be read outside of its content
    length. This makes sure that views can't do anything under the test client
    that wouldn't work in Real Life.

    """

    def __init__(self, content):
        self.__content = StringIO(content)
        self.__len = len(content)

    def read(self, num_bytes=None):
        """ READ.

        :return str: content

        """
        if num_bytes is None:
            num_bytes = self.__len or 0
        assert self.__len >= num_bytes, "Cannot read more than the available bytes from the HTTP incoming data."  # nolint
        content = self.__content.read(num_bytes)
        self.__len -= num_bytes
        return content

# lint_ignore=W0212,F0401

########NEW FILE########
__FILENAME__ = auth
import abc
import base64

from django.contrib.auth import authenticate


class AbstractAuthenticator(object):
    " Abstract base authenticator "

    __meta__ = abc.ABCMeta

    def __init__(self, resource):
        self.resource = resource
        self.identifier = ''

    @abc.abstractmethod
    def authenticate(self, request):
        raise NotImplementedError

    @abc.abstractmethod
    def configure(self, request):
        raise NotImplementedError

    @staticmethod
    def test_rights(resources, request=None):
        return True

    @staticmethod
    def get_fields():
        return []


class AnonimousAuthenticator(AbstractAuthenticator):
    " Anonymous access. Set identifier by IP address. "

    def authenticate(self, request):
        return True

    def configure(self, request):
        pass


class UserLoggedInAuthenticator(AbstractAuthenticator):
    " Check auth by session. "

    def __init__(self, *args, **kwargs):
        self.user = None
        super(UserLoggedInAuthenticator, self).__init__(*args, **kwargs)

    def authenticate(self, request):
        user = getattr(request, 'user', None)
        return user and user.is_active

    def configure(self, request):
        self.user = request.user
        self.resource.identifier = self.user.username


class BasicAuthenticator(UserLoggedInAuthenticator):
    " HTTP Basic authentication. "

    def authenticate(self, request=None):
        if 'HTTP_AUTHORIZATION' in request.META:
            auth = request.META['HTTP_AUTHORIZATION'].split()
            if len(auth) == 2 and auth[0].lower() == "basic":
                uname, passwd = base64.b64decode(auth[1]).split(':')
                user = authenticate(username=uname, password=passwd)
                if user and user.is_active:
                    request.user = user
                    return True

        return False


class UserAuthenticator(UserLoggedInAuthenticator):
    " Authorization by login and password "

    username_fieldname = 'username'
    password_fieldname = 'password'

    def authenticate(self, request=None):
        try:
            username = request.REQUEST.get(self.username_fieldname)
            password = request.REQUEST.get(self.password_fieldname)
            request.user = authenticate(username=username, password=password)
            return request.user and request.user.is_active

        except KeyError:
            return False

    @classmethod
    def get_fields(cls):
        return [(cls.username_fieldname, dict(required=True)), (cls.password_fieldname, dict(required=True))]


try:
    from ..models import AccessKey

    class AccessKeyAuthenticator(UserLoggedInAuthenticator):
        " Authorization by API token. "

        def authenticate(self, request=None):
            """ Authenticate user using AccessKey from HTTP Header or GET params.
            """
            try:
                token = request.META.get('HTTP_AUTHORIZATION') or request.REQUEST['key']
                accesskey = AccessKey.objects.select_related('user').get(key=token)
                request.user = accesskey.user
                return request.user and request.user.is_active

            except(KeyError, AccessKey.DoesNotExist):
                return False

except ImportError:
    pass

########NEW FILE########
__FILENAME__ = emitter
""" ADRest emitters. """

from datetime import datetime
from os import path as op
from time import mktime

from django.db.models.base import ModelBase, Model
from django.template import RequestContext, loader

from ..utils import UpdatedList
from .paginator import Paginator
from .response import SerializedHttpResponse
from .serializer import JSONSerializer, XMLSerializer
from .status import HTTP_200_OK


class EmitterMeta(type):

    """ Preload format attribute. """

    def __new__(mcs, name, bases, params):
        cls = super(EmitterMeta, mcs).__new__(mcs, name, bases, params)
        if not cls.format and cls.media_type:
            cls.format = str(cls.media_type).split('/')[-1]
        return cls


class BaseEmitter(object):

    """ Base class for emitters.

    All emitters must extend this class, set the media_type attribute, and
    override the serialize() function.

    """

    __metaclass__ = EmitterMeta

    media_type = None
    format = None

    def __init__(self, resource, request=None, response=None):
        self.resource = resource
        self.request = request
        self.response = SerializedHttpResponse(
            response,
            mimetype=self.media_type,
            status=HTTP_200_OK)

    def emit(self):
        """ Serialize response.

        :return response: Instance of django.http.Response

        """
        # Skip serialize
        if not isinstance(self.response, SerializedHttpResponse):
            return self.response

        self.response.content = self.serialize(self.response.response)
        self.response['Content-type'] = self.media_type
        return self.response

    @staticmethod
    def serialize(content):
        """ Low level serialization.

        :return response:

        """
        return content


class NullEmitter(BaseEmitter):

    """ Return data as is. """

    media_type = 'unknown/unknown'

    def emit(self):
        """ Do nothing.

        :return response:

        """
        return self.response


class TextEmitter(BaseEmitter):

    """ Serialize to unicode. """

    media_type = 'text/plain'

    @staticmethod
    def serialize(content):
        """ Get content and return string.

        :return unicode:

        """
        return unicode(content)


class JSONEmitter(BaseEmitter):

    """ Serialize to JSON. """

    media_type = 'application/json'

    def serialize(self, content):
        """ Serialize to JSON.

        :return string: serializaed JSON

        """
        worker = JSONSerializer(
            scheme=self.resource,
            options=self.resource._meta.emit_options,
            format=self.resource._meta.emit_format,
            **self.resource._meta.emit_models
        )
        return worker.serialize(content)


class JSONPEmitter(JSONEmitter):

    """ Serialize to JSONP. """

    media_type = 'text/javascript'

    def serialize(self, content):
        """ Serialize to JSONP.

        :return string: serializaed JSONP

        """
        content = super(JSONPEmitter, self).serialize(content)
        callback = self.request.GET.get('callback', 'callback')
        return u'%s(%s)' % (callback, content)


class XMLEmitter(BaseEmitter):

    """ Serialize to XML. """

    media_type = 'application/xml'
    xmldoc_tpl = '<?xml version="1.0" encoding="utf-8"?>\n<response success="%s" version="%s" timestamp="%s">%s</response>' # nolint

    def serialize(self, content):
        """ Serialize to XML.

        :return string: serialized XML

        """
        worker = XMLSerializer(
            scheme=self.resource,
            format=self.resource._meta.emit_format,
            options=self.resource._meta.emit_options,
            **self.resource._meta.emit_models
        )
        return self.xmldoc_tpl % (
            'true' if not self.response.error else 'false',
            str(self.resource.api or ''),
            int(mktime(datetime.now().timetuple())),
            worker.serialize(content)
        )


class TemplateEmitter(BaseEmitter):

    """ Serialize by django templates. """

    def serialize(self, content):
        """ Render Django template.

        :return string: rendered content

        """
        if self.response.error:
            template_name = op.join('api', 'error.%s' % self.format)
        else:
            template_name = (self.resource._meta.emit_template
                             or self.get_template_path(content))

        template = loader.get_template(template_name)

        return template.render(RequestContext(self.request, dict(
            content=content,
            emitter=self,
            resource=self.resource)))

    def get_template_path(self, content=None):
        """ Find template.

        :return string: remplate path

        """

        if isinstance(content, Paginator):
            return op.join('api', 'paginator.%s' % self.format)

        if isinstance(content, UpdatedList):
            return op.join('api', 'updated.%s' % self.format)

        app = ''
        name = self.resource._meta.name

        if not content:
            content = self.resource._meta.model

        if isinstance(content, (Model, ModelBase)):
            app = content._meta.app_label # nolint
            name = content._meta.module_name # nolint

        basedir = 'api'
        if getattr(self.resource, 'api', None):
            basedir = self.resource.api.prefix

        return op.join(
            basedir,
            str(self.resource.api or ''), app, "%s.%s" % (name, self.format)
        )


class JSONTemplateEmitter(TemplateEmitter):

    """ Template emitter with JSON media type. """

    media_type = 'application/json'


class JSONPTemplateEmitter(TemplateEmitter):

    """ Template emitter with javascript media type. """

    media_type = 'text/javascript'
    format = 'json'

    def serialize(self, content):
        """ Move rendered content to callback.

        :return string: JSONP

        """
        content = super(JSONPTemplateEmitter, self).serialize(content)
        callback = self.request.GET.get('callback', 'callback')
        return '%s(%s)' % (callback, content)


class HTMLTemplateEmitter(TemplateEmitter):

    """ Template emitter with HTML media type. """

    media_type = 'text/html'


class XMLTemplateEmitter(TemplateEmitter):

    """ Template emitter with XML media type. """

    media_type = 'application/xml'
    xmldoc_tpl = '<?xml version="1.0" encoding="utf-8"?>\n<response success="%s" version="%s" timestamp="%s">%s</response>' # nolint

    def serialize(self, content):
        """ Serialize to xml.

        :return string:

        """
        return self.xmldoc_tpl % (
            'true' if self.response.status_code == HTTP_200_OK else 'false',
            str(self.resource.api or ''),
            int(mktime(datetime.now().timetuple())),
            super(XMLTemplateEmitter, self).serialize(content)
        )


try:
    from bson import BSON

    class BSONEmitter(BaseEmitter):
        media_type = 'application/bson'

        @staticmethod
        def serialize(content):
            return BSON.encode(content)

except ImportError:
    pass

# pymode:lint_ignore=F0401,W0704

########NEW FILE########
__FILENAME__ = exceptions
from django.core.exceptions import ValidationError

from .status import HTTP_400_BAD_REQUEST


class HttpError(Exception):
    " Represents HTTP Error. "

    def __init__(self, content, status=HTTP_400_BAD_REQUEST, emitter=None):
        self.content, self.status, self.emitter = content, status, emitter
        super(HttpError, self).__init__(content)

    def __str__(self):
        return self.content

    __repr__ = __str__


class FormError(ValidationError):
    " Represents Form Error. "

    def __init__(self, form, emitter=None):
        self.form, self.emitter = form, emitter
        super(FormError, self).__init__(form.errors.as_text())

########NEW FILE########
__FILENAME__ = mail
""" ADRest mail utils. """
import traceback
import sys
from django.core.mail import mail_admins
from ..settings import ADREST_MAIL_ERRORS


def adrest_errors_mail(response, request):
    """ Send a mail about ADRest errors.

    :return bool: status of operation

    """

    if not response.status_code in ADREST_MAIL_ERRORS:
        return False

    subject = 'ADREST API Error (%s): %s' % (
        response.status_code, request.path)
    stack_trace = '\n'.join(traceback.format_exception(*sys.exc_info()))
    message = """
Stacktrace:
===========
%s

Handler data:
=============
%s

Request information:
====================
%s

""" % (stack_trace, repr(getattr(request, 'data', None)), repr(request))
    return mail_admins(subject, message, fail_silently=True)

########NEW FILE########
__FILENAME__ = meta
""" Meta support for ADRest classes.
"""
from django.db.models import get_model, Model


__all__ = 'MixinBaseMeta', 'MixinBase'


class MetaOptions(dict):

    """ Storage for Meta options. """

    def __getattr__(self, name):
        return self.get(name)

    __setattr__ = dict.__setitem__


class Meta:

    """ Base options for all ADRest mixins.

    With Meta options you can setup your resources.

    """

    # Link to parent resource. Used for create a resource's hierarchy.
    parent = None

    #: Setup Django ORM model.
    #: Value could be a model class or string path like 'app.model'.
    model = None


class MixinBaseMeta(type):

    """ Init meta options.

    Merge Meta options from class bases.

    """

    def __new__(mcs, name, bases, params):
        params['_meta'] = params.get('_meta', MetaOptions())
        cls = super(MixinBaseMeta, mcs).__new__(mcs, name, bases, params)

        meta = dict()
        for parent in reversed(cls.mro()):
            if hasattr(parent, 'Meta'):
                meta.update(parent.Meta.__dict__)

        cls._meta.update(dict(
            (attr, meta[attr]) for attr in meta
            if not attr.startswith('_')
        ))

        # Prepare hierarchy
        cls._meta.parents = []
        if cls._meta.parent:
            cls._meta.parents = (
                cls._meta.parent._meta.parents + [cls._meta.parent])

        if not cls._meta.model:
            return cls

        # Create model from string
        if isinstance(cls._meta.model, basestring):
            if not '.' in cls._meta.model:
                raise AssertionError(
                    "'model_class' must be either a model"
                    " or a model name in the format"
                    " app_label.model_name")
            cls._meta.model = get_model(*cls._meta.model.split("."))

        # Check meta.name and queryset
        if not issubclass(cls._meta.model, Model):
            raise AssertionError("'model' attribute must be subclass of Model")

        cls._meta.fields = set(f.name for f in cls._meta.model._meta.fields)

        return cls


class MixinBase(object):

    """ Base class for all ADRest mixins.

    .. autoclass:: adrest.utils.meta.Meta
       :members:

    """

    Meta = Meta

    __metaclass__ = MixinBaseMeta

    __parent__ = None

    @property
    def parent(self):
        """ Cache a instance of self parent class.

        :return object: instance of self.Meta.parent class

        """
        if not self._meta.parent:
            return None

        if not self.__parent__:
            self.__parent__ = self._meta.parent()

        return self.__parent__

########NEW FILE########
__FILENAME__ = paginator
""" Pagination support. """

from urllib import urlencode

from django.core.paginator import InvalidPage, Paginator as DjangoPaginator

from .exceptions import HttpError
from .status import HTTP_400_BAD_REQUEST


class Paginator(object):

    """ Paginate collections. """

    def __init__(self, request, resource, response):
        self.query_dict = dict(request.GET.items())
        self.path = request.path

        try:
            per_page = resource._meta.dyn_prefix + 'max'
            self.paginator = DjangoPaginator(
                response,
                self.query_dict.get(per_page) or resource._meta.limit_per_page)

            if not self.paginator.per_page:
                self.paginator = None

        except (ValueError, AssertionError):
            self.paginator = None

        self._page = None

    def to_simple(self, serializer=None):
        """ Prepare to serialization.

        :return dict: paginator params

        """
        return dict(
            count=self.paginator.count,
            page=self.page_number,
            num_pages=self.paginator.num_pages,
            next=self.next_page,
            prev=self.previous_page,
            resources=self.resources,
        )

    @property
    def page(self):
        """ Get current page.

        :return int: page number

        """
        if not self._page:
            try:
                self._page = self.paginator.page(
                    self.query_dict.get('page', 1))
            except InvalidPage:
                raise HttpError("Invalid page", status=HTTP_400_BAD_REQUEST)
        return self._page

    @property
    def page_number(self):
        """Get page number

        :return: int

        """
        return self.page.number if self.page else 1

    @property
    def count(self):
        """ Get resources count.

        :return int: resources amount

        """
        return self.paginator.count

    @property
    def resources(self):
        """ Return list of current page resources.

        :return list:

        """
        return self.page.object_list

    @property
    def next_page(self):
        """ Return URL for next page.

        :return str:

        """
        if self.page.has_next():
            self.query_dict['page'] = self.page.next_page_number()
            return "%s?%s" % (self.path, urlencode(self.query_dict))
        return ""

    @property
    def previous_page(self):
        """ Return URL for previous page.

        :return str:

        """
        if self.page.has_previous():
            previous = self.page.previous_page_number()
            if previous == 1:
                if 'page' in self.query_dict:
                    del self.query_dict['page']
            else:
                self.query_dict['page'] = previous
            return "%s?%s" % (self.path, urlencode(self.query_dict))
        return ""

########NEW FILE########
__FILENAME__ = parser
from django.utils import simplejson as json
import abc

from .exceptions import HttpError
from .status import HTTP_400_BAD_REQUEST
from .tools import FrozenDict


class AbstractParser(object):
    " Base class for parsers. "

    media_type = None

    __meta__ = abc.ABCMeta

    def __init__(self, resource):
        self.resource = resource

    @abc.abstractmethod
    def parse(self, request):
        raise NotImplementedError


class RawParser(AbstractParser):
    " Return raw post data. "

    media_type = 'text/plain'

    @staticmethod
    def parse(request):
        return request.body


class FormParser(AbstractParser):
    " Parse user data from form data. "

    media_type = 'application/x-www-form-urlencoded'

    @staticmethod
    def parse(request):
        return FrozenDict((k, v if len(v) > 1 else v[0])
                          for k, v in request.POST.iterlists())


class JSONParser(AbstractParser):
    """ Parse user data from JSON.
        http://en.wikipedia.org/wiki/JSON
    """

    media_type = 'application/json'

    @staticmethod
    def parse(request):
        try:
            return json.loads(request.body)
        except ValueError, e:
            raise HttpError('JSON parse error - %s'.format(e),
                            status=HTTP_400_BAD_REQUEST)


class XMLParser(RawParser):
    " Parse user data from XML. "

    media_type = 'application/xml'


try:
    from bson import BSON

    class BSONParser(AbstractParser):
        """ Parse user data from bson.
            http://en.wikipedia.org/wiki/BSON
        """

        media_type = 'application/bson'

        @staticmethod
        def parse(request):
            try:
                return BSON(request.body).decode()
            except ValueError, e:
                raise HttpError('BSON parse error - %s'.format(e),
                                status=HTTP_400_BAD_REQUEST)

except ImportError:
    pass

########NEW FILE########
__FILENAME__ = response
from django.http import HttpResponse

from .status import HTTP_200_OK


class SerializedMeta(type):

    def __call__(cls, content, *args, **kwargs):
        """ Don't create clones.
        """
        if isinstance(content, HttpResponse):
            return content

        return super(SerializedMeta, cls).__call__(
            content, *args, **kwargs
        )


class SerializedHttpResponse(HttpResponse): # nolint
    """ Response has will be serialized.
        Django http response will be returned as is.

        :param error: Force error in response.
    """
    __metaclass__ = SerializedMeta

    def __init__(self, content='', mimetype=None, status=None,
                 content_type=None, error=False):
        """
            Save original response.
        """
        self.response = content
        self._error = error
        self._content_type = content_type

        super(SerializedHttpResponse, self).__init__(
            content,
            mimetype=mimetype,
            status=status,
            content_type=content_type)

    @property
    def error(self):
        return self._error or self.status_code != HTTP_200_OK

    def __repr__(self):
        return "<SerializedHttpResponse %s>" % self.status_code

# pymode:lint_ignore=E1103

########NEW FILE########
__FILENAME__ = serializer
""" ADRest serializers. """
import collections
import inspect
from numbers import Number
from datetime import datetime, date, time
from decimal import Decimal

from django.db.models import Model, Manager
from django.utils import simplejson
from django.utils.encoding import smart_unicode

from .tools import as_tuple


class BaseSerializer(object):

    """ Abstract class for serializers. """

    def __init__(
            self, scheme=None, options=None, format='django', **model_options):
        self.scheme = scheme
        self.format = format
        self.serializer_options = options or dict()
        self.model_options = self.init_options(**model_options)

    @staticmethod
    def init_options(fields=None, include=None, exclude=None, related=None):
        options = dict(
            fields=set(as_tuple(fields)),
            include=set(as_tuple(include)),
            exclude=set(as_tuple(exclude)),
            related=related or dict(),
        )
        return options

    def to_simple(self, value, **options):  # nolint
        " Simplify object. "

        # (string, unicode)
        if isinstance(value, basestring):
            return smart_unicode(value)

        # (int, long, float, real, complex, decimal)
        if isinstance(value, Number):
            return float(str(value)) if isinstance(value, Decimal) else value

        # (datetime, data, time)
        if isinstance(value, (datetime, date, time)):
            return self.to_simple_datetime(value)

        # (dict, ordereddict, mutable mapping)
        if isinstance(value, collections.MutableMapping):
            return dict(
                (k, self.to_simple(v, **options)) for k, v in value.items())

        # (tuple, list, set, iterators)
        if isinstance(value, collections.Iterable):
            return [self.to_simple(o, **options) for o in value]

        # (None, True, False)
        if value is None or value is True or value is False:
            return value

        if hasattr(value, 'to_simple') and not inspect.isclass(value):
            return self.to_simple(
                value.to_simple(self),
                **options
            )

        if isinstance(value, Model):
            return self.to_simple_model(value, **options)

        return str(value)

    @staticmethod
    def to_simple_datetime(value):
        result = value.isoformat()
        if isinstance(value, datetime):
            if value.microsecond:
                result = result[:23] + result[26:]
            if result.endswith('+00:00'):
                result = result[:-6] + 'Z'
        elif isinstance(value, time) and value.microsecond:
            result = result[:12]
        return result

    def to_simple_model(self, instance, **options): # nolint
        """ Convert model to simple python structure.
        """
        options = self.init_options(**options)
        fields, include, exclude, related = options['fields'], options['include'], options['exclude'], options['related'] # nolint

        result = dict(
            model=smart_unicode(instance._meta),
            pk=smart_unicode(
                instance._get_pk_val(), strings_only=True),
            fields=dict(),
        )

        m2m_fields = [f.name for f in instance._meta.many_to_many]
        o2m_fields = [f.get_accessor_name()
                      for f in instance._meta.get_all_related_objects()]
        default_fields = set([field.name for field in instance._meta.fields
                              if field.serialize])
        serialized_fields = fields or (default_fields | include) - exclude

        for fname in serialized_fields:

            # Respect `to_simple__<fname>`
            to_simple = getattr(
                self.scheme, 'to_simple__{0}'.format(fname), None)

            if to_simple:
                result['fields'][fname] = to_simple(instance, serializer=self)
                continue

            related_options = related.get(fname, dict())
            if related_options:
                related_options = self.init_options(**related_options)

            if fname in default_fields and not related_options:
                field = instance._meta.get_field(fname)
                value = field.value_from_object(instance)

            else:
                value = getattr(instance, fname, None)
                if isinstance(value, Manager):
                    value = value.all()

            result['fields'][fname] = self.to_simple(
                value, **related_options)

        if self.format != 'django':
            fields = result['fields']
            fields['id'] = result['pk']
            result = fields

        return result

    def serialize(self, value):
        simple = self.to_simple(value, **self.model_options)
        if self.scheme:
            to_simple = getattr(self.scheme, 'to_simple', lambda s: s)
            simple = to_simple(value, simple, serializer=self)

        return simple


class JSONSerializer(BaseSerializer):

    def serialize(self, value):
        simple = super(JSONSerializer, self).serialize(value)
        return simplejson.dumps(simple, **self.serializer_options)


class XMLSerializer(BaseSerializer):

    def serialize(self, value):
        simple = super(XMLSerializer, self).serialize(value)
        return ''.join(s for s in self._dumps(simple))

    def _dumps(self, value):  # nolint
        tag = it = None

        if isinstance(value, list):
            tag = 'items'
            it = iter(value)

        elif isinstance(value, dict) and 'model' in value:
            tag = value.get('model').split('.')[1]
            it = value.iteritems()

        elif isinstance(value, dict):
            it = value.iteritems()

        elif isinstance(value, tuple):
            tag = str(value[0])
            it = (i for i in value[1:])

        else:
            yield str(value)

        if tag:
            yield "<%s>" % tag

        if it:
            try:
                while True:
                    v = next(it)
                    yield ''.join(self._dumps(v))
            except StopIteration:
                yield ''

        if tag:
            yield "</%s>" % tag


# lint_ignore=W901,R0911,W0212,W0622

########NEW FILE########
__FILENAME__ = status
" Descriptive HTTP status codes, for code readability. "


# status codes informational
HTTP_100_CONTINUE = 100
HTTP_101_SWITCHING_PROTOCOLS = 101

# successful
HTTP_200_OK = 200
HTTP_201_CREATED = 201
HTTP_202_ACCEPTED = 202
HTTP_203_NON_AUTHORITATIVE_INFORMATION = 203
HTTP_204_NO_CONTENT = 204
HTTP_205_RESET_CONTENT = 205
HTTP_206_PARTIAL_CONTENT = 206

# redirection
HTTP_300_MULTIPLE_CHOICES = 300
HTTP_301_MOVED_PERMANENTLY = 301
HTTP_302_FOUND = 302
HTTP_303_SEE_OTHER = 303
HTTP_304_NOT_MODIFIED = 304
HTTP_305_USE_PROXY = 305
HTTP_306_RESERVED = 306
HTTP_307_TEMPORARY_REDIRECT = 307

# client error
HTTP_400_BAD_REQUEST = 400
HTTP_401_UNAUTHORIZED = 401
HTTP_402_PAYMENT_REQUIRED = 402
HTTP_403_FORBIDDEN = 403
HTTP_404_NOT_FOUND = 404
HTTP_405_METHOD_NOT_ALLOWED = 405
HTTP_406_NOT_ACCEPTABLE = 406
HTTP_407_PROXY_AUTHENTICATION_REQUIRED = 407
HTTP_408_REQUEST_TIMEOUT = 408
HTTP_409_CONFLICT = 409
HTTP_410_GONE = 410
HTTP_411_LENGTH_REQUIRED = 411
HTTP_412_PRECONDITION_FAILED = 412
HTTP_413_REQUEST_ENTITY_TOO_LARGE = 413
HTTP_414_REQUEST_URI_TOO_LONG = 414
HTTP_415_UNSUPPORTED_MEDIA_TYPE = 415
HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE = 416
HTTP_417_EXPECTATION_FAILED = 417

# server error
HTTP_500_INTERNAL_SERVER_ERROR = 500
HTTP_501_NOT_IMPLEMENTED = 501
HTTP_502_BAD_GATEWAY = 502
HTTP_503_SERVICE_UNAVAILABLE = 503
HTTP_504_GATEWAY_TIMEOUT = 504
HTTP_505_HTTP_VERSION_NOT_SUPPORTED = 505

########NEW FILE########
__FILENAME__ = throttle
import abc
import time
import hashlib

from django.core.cache import cache

from ..settings import ADREST_THROTTLE_AT, ADREST_THROTTLE_TIMEFRAME


class AbstractThrottle(object):
    """ Fake throttle class.
    """

    __meta__ = abc.ABCMeta

    throttle_at = ADREST_THROTTLE_AT
    timeframe = ADREST_THROTTLE_TIMEFRAME

    @abc.abstractmethod
    def should_be_throttled(self, resource):
        """ Returns whether or not the user has exceeded their throttle limit.
        """
        pass

    @staticmethod
    def convert_identifier_to_key(identifier):
        """ Takes an identifier (like a username or IP address) and converts it
            into a key usable by the cache system.
        """
        key = ''.join(c for c in identifier if c.isalnum() or c in '_.-')
        if len(key) > 230:
            key = key[:150] + '-' + hashlib.md5(key).hexdigest()

        return "%s_accesses" % key


class NullThrottle(AbstractThrottle):
    " Anybody never be throttled. "

    @staticmethod
    def should_be_throttled(resource):
        return 0


class CacheThrottle(AbstractThrottle):
    """ A throttling mechanism that uses just the cache.
    """
    def should_be_throttled(self, resource):
        key = self.convert_identifier_to_key(resource.identifier)
        count, expiration, now = self._get_params(key)
        if count >= self.throttle_at and expiration > now:
            return expiration - now

        cache.set(key, (count + 1, expiration), (expiration - now))
        return 0

    def _get_params(self, key):
        count, expiration = cache.get(key, (1, None))
        now = time.time()
        if expiration is None:
            expiration = now + self.timeframe
        return count, expiration, now

########NEW FILE########
__FILENAME__ = tools
import collections


def as_tuple(obj):
    " Given obj return a tuple "

    if not obj:
        return tuple()

    if isinstance(obj, (tuple, set, list)):
        return tuple(obj)

    if hasattr(obj, '__iter__') and not isinstance(obj, dict):
        return obj

    return obj,


def gen_url_name(resource):
    " URL name for resource class generator. "

    if resource._meta.parent:
        yield resource._meta.parent._meta.url_name

    if resource._meta.prefix:
        yield resource._meta.prefix

    for p in resource._meta.url_params:
        yield p

    yield resource._meta.name


def gen_url_regex(resource):
    " URL regex for resource class generator. "

    if resource._meta.parent:
        yield resource._meta.parent._meta.url_regex.rstrip('/$').lstrip('^')

    for p in resource._meta.url_params:
        yield '%(name)s/(?P<%(name)s>[^/]+)' % dict(name=p)

    if resource._meta.prefix:
        yield resource._meta.prefix

    yield '%(name)s/(?P<%(name)s>[^/]+)?' % dict(name=resource._meta.name)


def fix_request(request):
    methods = "PUT", "PATCH"

    if request.method in methods\
            and not getattr(request, request.method, None):

        if hasattr(request, '_post'):
            del(request._post)
            del(request._files)

        if hasattr(request, '_request'):
            del(request._request)

        request.method, method = "POST", request.method
        setattr(request, method, request.POST)
        request.method = method

    request.adrest_fixed = True

    return request


class FrozenDict(collections.Mapping): # nolint
    """ Immutable dict. """

    def __init__(self, *args, **kwargs):
        self._d = dict(*args, **kwargs)
        self._hash = None

    def __iter__(self):
        return iter(self._d)

    def __len__(self):
        return len(self._d)

    def __getitem__(self, key):
        return self._d[key]

    def __hash__(self):
        # It would have been simpler and maybe more obvious to
        # use hash(tuple(sorted(self._d.iteritems()))) from this discussion
        # so far, but this solution is O(n). I don't know what kind of
        # n we are going to run into, but sometimes it's hard to resist the
        # urge to optimize when it will gain improved algorithmic performance.
        if self._hash is None:
            self._hash = 0
            for key, value in self.iteritems():
                self._hash ^= hash(key)
                self._hash ^= hash(value)
        return self._hash

    def __str__(self):
        return str(dict(self.iteritems()))

    def __repr__(self):
        return "<FrozenDict: %s>" % repr(dict(self.iteritems()))

########NEW FILE########
__FILENAME__ = views
""" Base request resource. """

from django.conf.urls import url
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from logging import getLogger

from .mixin import auth, emitter, handler, parser, throttle
from .settings import ADREST_ALLOW_OPTIONS, ADREST_DEBUG
from .signals import api_request_started, api_request_finished
from .utils import status
from .utils.exceptions import HttpError, FormError
from .utils.mail import adrest_errors_mail
from .utils.response import SerializedHttpResponse
from .utils.tools import as_tuple, gen_url_name, gen_url_regex, fix_request


logger = getLogger('django.request')


__all__ = 'ResourceView',


class ResourceMetaClass(
    handler.HandlerMeta, throttle.ThrottleMeta, emitter.EmitterMeta,
        parser.ParserMeta, auth.AuthMeta):

    """ MetaClass for ResourceView. Create meta options. """

    def __new__(mcs, name, bases, params):

        # Run other meta classes
        cls = super(ResourceMetaClass, mcs).__new__(mcs, name, bases, params)

        meta = params.get('Meta')

        cls._meta.abstract = meta and getattr(meta, 'abstract', False)
        if cls._meta.abstract:
            return cls

        # Meta name (maybe precalculate in handler)
        cls._meta.name = cls._meta.name or ''.join(
            bit for bit in name.split('Resource') if bit).lower()

        # Prepare urls
        cls._meta.url_params = list(as_tuple(cls._meta.url_params))
        cls._meta.url_name = cls._meta.url_name or '-'.join(gen_url_name(cls))
        cls._meta.url_regex = cls._meta.url_regex or '/'.join(
            gen_url_regex(cls))

        return cls


class ResourceView(
    handler.HandlerMixin, throttle.ThrottleMixin, emitter.EmitterMixin,
        parser.ParserMixin, auth.AuthMixin, View):

    """ REST Resource. """

    # Create meta options
    __metaclass__ = ResourceMetaClass

    # Link to api if connected
    api = None

    # Instance's identifier
    identifier = None

    class Meta:

        # This abstract class
        abstract = True

        # Name (By default this set from model or class name)
        name = None

        # Save access log if ADRest logging is enabled
        log = True

        # Some custom URI params here
        url_params = None
        url_regex = None
        url_name = None

        # Custom prefix for url name and regex
        prefix = ''

        # If children object in hierarchy has FK=Null to parent,
        # allow to get this object (default: True)
        allow_public_access = False

    @csrf_exempt
    def dispatch(self, request, **resources):
        """ Try to dispatch the request.

        :return object: result

        """

        # Fix PUT and PATH methods in Django request
        request = fix_request(request)

        # Set self identifier
        self.identifier = request.META.get('REMOTE_ADDR', 'anonymous')

        # Send ADREST started signal
        api_request_started.send(self, request=request)

        # Send current api started signal
        if self.api:
            self.api.request_started.send(self, request=request)

        try:

            # Check request method
            self.check_method_allowed(request)

            # Authentificate
            self.authenticate(request)

            # Throttle check
            self.throttle_check()

            if request.method != 'OPTIONS' or not ADREST_ALLOW_OPTIONS:

                # Parse content
                request.data = self.parse(request)

                # Get required resources
                resources = self.get_resources(
                    request, **resources)

                # Check owners
                self.check_owners(request, **resources)

                # Check rights for resources with this method
                self.check_rights(resources, request=request)

            response = self.handle_request(request, **resources)

            # Serialize response
            response = self.emit(response, request=request)

        except Exception as e:
            response = self.handle_exception(e, request=request)

        response["Allow"] = ', '.join(self._meta.allowed_methods)
        response["Vary"] = 'Authenticate, Accept'

        # Send errors on mail
        adrest_errors_mail(response, request)

        # Send finished signal
        api_request_finished.send(
            self, request=request, response=response, **resources)

        # Send finished signal in API context
        if self.api:
            self.api.request_finished.send(
                self, request=request, response=response, **resources)

        return response

    def check_owners(self, request, **resources):
        """ Check parents of current resource.

        Recursive scanning of the fact that the child has FK
        to the parent and in resources we have right objects.

        We check that in request like /author/1/book/2/page/3

        Page object with pk=3 has ForeignKey field linked to Book object
        with pk=2 and Book with pk=2 has ForeignKey field linked to Author
        object with pk=1.

        :return bool: If success else raise Exception

        """

        if self._meta.allow_public_access or not self._meta.parent:
            return True

        self.parent.check_owners(request, **resources)

        objects = resources.get(self._meta.name)
        if self._meta.model and self._meta.parent._meta.model and objects:
            pr = resources.get(self._meta.parent._meta.name)
            check = all(
                pr.pk == getattr(
                    o, "%s_id" % self._meta.parent._meta.name, None)
                for o in as_tuple(objects))

            if not pr or not check:
                # 403 Error if there is error in parent-children relationship
                raise HttpError(
                    "Access forbidden.", status=status.HTTP_403_FORBIDDEN)

        return True

    def handle_exception(self, e, request=None):
        """ Handle code exception.

        :return response: Http response

        """
        if isinstance(e, HttpError):
            response = SerializedHttpResponse(e.content, status=e.status)
            return self.emit(
                response, request=request, emitter=e.emitter)

        if isinstance(e, (AssertionError, ValidationError)):

            content = unicode(e)

            if isinstance(e, FormError):
                content = e.form.errors

            response = SerializedHttpResponse(
                content, status=status.HTTP_400_BAD_REQUEST)

            return self.emit(response, request=request)

        if ADREST_DEBUG:
            raise

        logger.exception('\nADREST API Error: %s', request.path)

        return HttpResponse(str(e), status=500)

    @classmethod
    def as_url(cls, api=None, name_prefix='', url_prefix=''):
        """ Generate url for resource.

        :return RegexURLPattern: Django URL

        """
        url_prefix = url_prefix and "%s/" % url_prefix
        name_prefix = name_prefix and "%s-" % name_prefix

        url_regex = '^%s%s/?$' % (
            url_prefix, cls._meta.url_regex.lstrip('^').rstrip('/$'))
        url_regex = url_regex.replace('//', '/')
        url_name = '%s%s' % (name_prefix, cls._meta.url_name)

        return url(url_regex, cls.as_view(api=api), name=url_name)



# pymode:lint_ignore=E1120,W0703,W0212

########NEW FILE########
__FILENAME__ = conf
""" Build docs. """
import os
import sys
import datetime

from adrest import __version__ as release

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))

extensions = ['sphinx.ext.autodoc', 'sphinx.ext.intersphinx']
source_suffix = '.rst'
master_doc = 'index'
project = u'ADRest'
copyright = u'%s, Kirill Klenov' % datetime.datetime.now().year
version = '.'.join(release.split('.')[:2])
exclude_patterns = ['_build']
html_use_modindex = False
htmlhelp_basename = 'ADRestdoc'
man_pages = [
    ('index', 'adrest', u'ADRest Documentation', [u'Kirill Klenov'], 1)
]
pygments_style = 'tango'

# lint_ignore=W0622

########NEW FILE########
__FILENAME__ = api
""" Create Api and resources. """
from adrest.api import Api
from adrest.views import ResourceView
from adrest.resources.rpc import RPCResource

from . import rpc


api = Api(version='0.1')
api.register(RPCResource, scheme=rpc)


@api.register
class AuthorResource(ResourceView):

    """ Get authors from db. """

    class Meta:
        model = 'main.author'


@api.register
class BookResource(ResourceView):

    """ Works with books. Nested resource. """

    class Meta:
        allowed_methods = 'get', 'post', 'put'
        model = 'main.book'
        parent = AuthorResource

########NEW FILE########
__FILENAME__ = models
""" Hello Django tests runner!
"""

########NEW FILE########
__FILENAME__ = rpc
def hello(name):
    return "Hello {0}!".format(name)

########NEW FILE########
__FILENAME__ = admin
from django.contrib import admin
from django.db.models.loading import get_models, get_app


# Register main models in admin
app = get_app('main')
for model in get_models(app):
    admin.site.register(model, admin.ModelAdmin)

########NEW FILE########
__FILENAME__ = models
from django.db import models


class Author(models.Model):
    name = models.CharField(max_length=200, help_text='Name of author')


class Book(models.Model):
    name = models.CharField(max_length=200, help_text='Name of book')
    author = models.ForeignKey(Author)

########NEW FILE########
__FILENAME__ = base
from django.test import TestCase


class BaseTestCase(TestCase):

    def test_response(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

        from django.contrib.auth.models import User

        user = User.objects.create(username='testuser')
        user.set_password('testpassword')
        user.save()

        self.client.login(username='testuser', password='testpassword')

        response = self.client.get('/')
        self.assertContains(response, 'logout')

        response = self.client.get('/logout', follow=True)
        self.assertNotContains(response, 'logout')

########NEW FILE########
__FILENAME__ = urls
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.views.defaults import page_not_found, server_error

from . import views as mainviews
from api.api import api

try:
    from django.conf.urls import url, patterns, include
# Support Django<=1.5
except ImportError:
    from django.conf.urls.defaults import url, patterns, include


# 404 and 500 handlers
handler404 = page_not_found
handler500 = server_error

# Project urls
urlpatterns = patterns(
    '',
    url('^$', mainviews.Index.as_view(), name='index'),
    url('^logout/$', 'django.contrib.auth.views.logout', name='logout'),

    # Api urls
    url('^api/', include(api.urls)),
)

# Django admin
admin.autodiscover()
urlpatterns += [url(r'^admin/', include(admin.site.urls)), ]

# Debug static files serve
urlpatterns += staticfiles_urlpatterns()

# lint_ignore=E1120

########NEW FILE########
__FILENAME__ = cache
import hashlib
import logging
import re

from django.core.cache import cache
from django.db.models import Model, get_model
from django.db.models.base import ModelBase
from django.db.models.query import QuerySet
from django.utils.encoding import smart_str


LOG = logging.getLogger('cache')


def cached_instance(model, timeout=None, **filters):
    """ Auto cached model instance.
    """
    if isinstance(model, basestring):
        model = _str_to_model(model)

    cache_key = generate_cache_key(model, **filters)
    return get_cached(cache_key, model.objects.select_related().get, kwargs=filters)


def cached_query(qs, timeout=None):
    """ Auto cached queryset and generate results.
    """
    cache_key = generate_cache_key(qs)
    return get_cached(cache_key, list, args=(qs,), timeout=None)


def clean_cache(cached, **kwargs):
    " Generate cache key and clean cached value. "

    if isinstance(cached, basestring):
        cached = _str_to_model(cached)

    cache_key = generate_cache_key(cached, **kwargs)
    cache.delete(cache_key)


def generate_cache_key(cached, **kwargs):
    """ Auto generate cache key for model or queryset
    """

    if isinstance(cached, QuerySet):
        key = str(cached.query)

    elif isinstance(cached, (Model, ModelBase)):
        key = '%s.%s:%s' % (cached._meta.app_label,
                            cached._meta.module_name,
                            ','.join('%s=%s' % item for item in kwargs.iteritems()))

    else:
        raise AttributeError("Objects must be queryset or model.")

    if not key:
        raise Exception('Cache key cannot be empty.')

    key = clean_cache_key(key)
    return key


def clean_cache_key(key):
    """ Replace spaces with '-' and hash if length is greater than 250.
    """
    cache_key = re.sub(r'\s+', '-', key)
    cache_key = smart_str(cache_key)

    if len(cache_key) > 200:
        cache_key = cache_key[:150] + '-' + hashlib.md5(cache_key).hexdigest()

    return cache_key


def get_cached(cache_key, func, timeout=None, args=None, kwargs=None):
    args = args or list()
    kwargs = kwargs or dict()
    result = cache.get(cache_key)

    if result is None:

        if timeout is None:
            timeout = cache.default_timeout

        result = func(*args, **kwargs)
        cache.set(cache_key, result, timeout=timeout)

    return result


def _str_to_model(string):
    assert '.' in string, ("'model_class' must be either a model"
                           " or a model name in the format"
                           " app_label.model_name")
    app_label, model_name = string.split(".")
    return get_model(app_label, model_name)

########NEW FILE########
__FILENAME__ = files
from hashlib import md5
from os import path
from time import time


def upload_to(instance, filename, prefix=None):
    """ Auto upload function for File and Image fields.
    """
    ext = path.splitext(filename)[1]
    name = str(instance.pk or time()) + filename

    # We think that we use utf8 based OS file system
    filename = md5(name.encode('utf8')).hexdigest() + ext
    basedir = path.join(instance._meta.app_label, instance._meta.module_name)
    if prefix:
        basedir = path.join(basedir, prefix)
    return path.join(basedir, filename[:2], filename[2:4], filename)

########NEW FILE########
__FILENAME__ = models
import operator

from django.db.models import signals
from django.db.models.expressions import F, ExpressionNode


EXPRESSION_NODE_CALLBACKS = {
    ExpressionNode.ADD: operator.add,
    ExpressionNode.SUB: operator.sub,
    ExpressionNode.MUL: operator.mul,
    ExpressionNode.DIV: operator.div,
    ExpressionNode.MOD: operator.mod,
    ExpressionNode.AND: operator.and_,
    ExpressionNode.OR: operator.or_,
}


class CannotResolve(Exception):
    pass


def _resolve(instance, node):
    if isinstance(node, F):
        return getattr(instance, node.name)
    elif isinstance(node, ExpressionNode):
        return _resolve(instance, node)
    return node


def resolve_expression_node(instance, node):
    op = EXPRESSION_NODE_CALLBACKS.get(node.connector, None)
    if not op:
        raise CannotResolve
    runner = _resolve(instance, node.children[0])
    for n in node.children[1:]:
        runner = op(runner, _resolve(instance, n))
    return runner


def update(instance, full_clean=True, post_save=False, **kwargs):
    "Atomically update instance, setting field/value pairs from kwargs"

    # apply the updated args to the instance to mimic the change
    # note that these might slightly differ from the true database values
    # as the DB could have been updated by another thread. callers should
    # retrieve a new copy of the object if up-to-date values are required
    for k, v in kwargs.iteritems():
        if isinstance(v, ExpressionNode):
            v = resolve_expression_node(instance, v)
        setattr(instance, k, v)

    # clean instance before update
    if full_clean:
        instance.full_clean()

    # fields that use auto_now=True should be updated corrected, too!
    for field in instance._meta.fields:
        if hasattr(field, 'auto_now') and field.auto_now and field.name not in kwargs:
            kwargs[field.name] = field.pre_save(instance, False)

    rows_affected = instance.__class__._default_manager.filter(
        pk=instance.pk).update(**kwargs)

    if post_save:
        signals.post_save.send(sender=instance.__class__, instance=instance)

    return rows_affected


class Choices(object):

    def __init__(self, *choices):
        self._choices = []
        self._choice_dict = {}
        self._labels = {}

        for choice in choices:
            if isinstance(choice, (list, tuple)):
                if len(choice) == 2:
                    choice = (choice[0], choice[0], choice[1])

                elif len(choice) != 3:
                    raise ValueError("Choices can't handle a list/tuple of length %s, only 2 or 3" % len(choice))
            else:
                choice = (choice, choice, choice)

            self._choices.append((choice[0], choice[2]))
            self._choice_dict[choice[1]] = choice[0]

    def __getattr__(self, attname):
        try:
            return self._choice_dict[attname]
        except KeyError:
            raise AttributeError(attname)

    def __iter__(self):
        return iter(self._choices)

    def __getitem__(self, index):
        return self._choices[index]

    def __repr__(self):
        values, names = zip(*self._choices)
        labels = self._labels.itervalues()
        return '%s(%s)' % (self.__class__.__name__,
                           repr(zip(values, labels, names)))

########NEW FILE########
__FILENAME__ = views
from StringIO import StringIO

from django import http
from django.core.serializers.json import Serializer
from django.db.models.query import QuerySet
from django.views.generic import TemplateView


class TemplateContextView(TemplateView):
    """ Allow define context in as_view method.
    """
    context = dict()

    def __init__(self, context=None, **kwargs):
        self.context = context or dict()
        super(TemplateContextView, self).__init__(**kwargs)

    def get(self, request, *args, **kwargs):
        self.context.update(self.get_context_data(**kwargs))
        return self.render_to_response(self.context)


class AbstractResponseMixin(object):
    """ Abstract class for data serialize.
    """
    mimetype = "application/text"

    @staticmethod
    def render_template(context):
        "String representation of given context."
        return str(context)

    def render_to_response(self, context):
        "Return HttpResponse."
        return http.HttpResponse(
            self.render_template(context),
            content_type=self.mimetype)


class JSONResponseMixin(AbstractResponseMixin):
    """ Serialize queryset or any objects context in JSON.
    """
    mimetype = "application/json"

    def render_template(self, context):
        encoder = Serializer()
        if isinstance(context, QuerySet):
            return encoder.serialize(context, ensure_ascii=False)

        else:
            encoder.objects = context
            encoder.options = dict()
            encoder.stream = StringIO()
            encoder.end_serialization()
            return encoder.getvalue()


class JSONView(JSONResponseMixin, TemplateView):
    """ Render view context in JSON.
    """
    pass

########NEW FILE########
__FILENAME__ = views
from django.views.generic import TemplateView


class Index(TemplateView):
    """ Example view.
    """
    template_name = 'main/index.html'

########NEW FILE########
__FILENAME__ = manage
#!/usr/bin/env python
import os
import sys


if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.development")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)

########NEW FILE########
__FILENAME__ = core
"""
    Immutable settings.
    Common for all projects.

"""
from os import path as op
import logging

ENVIRONMENT_NAME = 'core'

PROJECT_ROOT = op.abspath(op.dirname(op.dirname(__file__)))
PROJECT_NAME = "{0}.{1}".format(
    op.basename(op.dirname(PROJECT_ROOT)), op.basename(PROJECT_ROOT))

SECRET_KEY = "CHANGE_ME_{0}".format(PROJECT_NAME)

# Databases
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'django_master.sqlite',
        'USER': '',
        'PASSWORD': '',
        'TEST_CHARSET': 'utf8',
    }
}

# Caches
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'KEY_PREFIX': '_'.join((PROJECT_NAME, 'CORE'))
    }
}

# Base urls config
ROOT_URLCONF = 'main.urls'

# Media settigns
MEDIA_ROOT = op.join(PROJECT_ROOT, 'media')
STATIC_ROOT = op.join(PROJECT_ROOT, 'static')
MEDIA_URL = '/media/'
STATIC_URL = '/static/'

# Templates settings
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.core.context_processors.static',
    'django.core.context_processors.request',
    'django.contrib.auth.context_processors.auth',
    'django.contrib.messages.context_processors.messages',
)

# Applications
INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.admin',
    'django.contrib.staticfiles',
)

# Base apps settings
MESSAGE_STORAGE = 'django.contrib.messages.storage.cookie.CookieStorage'

# Middleware
MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
)

# Localization
USE_I18N = True
USE_L10N = True
USE_TZ = True
MIDDLEWARE_CLASSES += ('django.middleware.locale.LocaleMiddleware',)
TEMPLATE_CONTEXT_PROCESSORS += ('django.core.context_processors.i18n',)

# Debug
INTERNAL_IPS = ('127.0.0.1',)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
    datefmt='%d.%m %H:%M:%S',
)
logging.info("Core settings loaded.")

########NEW FILE########
__FILENAME__ = development
""" Development related settings.
"""
from .production import * # nolint
from .core import TEMPLATE_LOADERS

assert TEMPLATE_LOADERS

ENVIRONMENT_NAME = 'development'

# Caches
CACHES['default']['KEY_PREFIX'] = '_'.join((PROJECT_NAME, 'DEV'))

# Debug
DEBUG = True
TEMPLATE_DEBUG = True
if DEBUG:
    INTERNAL_IPS += tuple('192.168.1.%s' % x for x in range(1, 111))
    TEMPLATE_CONTEXT_PROCESSORS += 'django.core.context_processors.debug',
    MIDDLEWARE_CLASSES += (
        'debug_toolbar.middleware.DebugToolbarMiddleware', )
    INSTALLED_APPS += ('debug_toolbar', )
    DEBUG_TOOLBAR_CONFIG = dict(INTERCEPT_REDIRECTS=False)

# Logging
LOGGING['loggers']['django.request']['level'] = 'DEBUG'
LOGGING['loggers']['celery']['level'] = 'DEBUG'
logging.info('Development settings are loaded.')

########NEW FILE########
__FILENAME__ = production
""" Production's settings.
"""
from .core import * # nolint

# Hack for adrest loading in example project
import sys
sys.path.insert(0, op.abspath(op.dirname(op.dirname(op.dirname(__file__)))))


ENVIRONMENT_NAME = 'production'

# Applications
INSTALLED_APPS += (

    # Community apps
    'south',

    # Base project app
    'main',

    # API
    'adrest',

)

# Caches
CACHES['default']['KEY_PREFIX'] = '_'.join((PROJECT_NAME, 'PRJ'))

# Sessions
SESSION_ENGINE = "django.contrib.sessions.backends.cache"

# Templates cache
TEMPLATE_LOADERS = (
    ('django.template.loaders.cached.Loader', TEMPLATE_LOADERS),
)

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
        },
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler'
        }
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
        'celery': {
            'handlers': ['console'],
            'level': 'ERROR',
        },
    }
}

logging.info('Production settings are loaded.')

########NEW FILE########
__FILENAME__ = test
""" Testing settings.
"""
from .production import * # nolint

ENVIRONMENT_NAME = 'test'

# Databases
DATABASES['default']['ENGINE'] = 'django.db.backends.sqlite3'
DATABASES['default']['NAME'] = ':memory:'

# Caches
CACHES['default']['BACKEND'] = 'django.core.cache.backends.locmem.LocMemCache'
CACHES['default']['KEY_PREFIX'] = '_'.join((PROJECT_NAME, 'TST'))

# Disable south migrations on db creation in tests
SOUTH_TESTS_MIGRATE = False

# CELERY
BROKER_BACKEND = 'memory'
CELERY_ALWAYS_EAGER = True

logging.info('Test settings are loaded.')

########NEW FILE########
__FILENAME__ = wsgi
#!/usr/bin/env python
import os

from django.core.wsgi import get_wsgi_application


os.environ['DJANGO_SETTINGS_MODULE'] = os.environ.get(
    'DJANGO_SETTINGS_MODULE', 'settings.dev')
application = get_wsgi_application()

if 'dev' in os.environ['DJANGO_SETTINGS_MODULE']:
    from werkzeug.debug import DebuggedApplication
    from django.views import debug

    def null_technical_500_response(request, exc_type, exc_value, tb):
        raise exc_type, exc_value, tb
    debug.technical_500_response = null_technical_500_response
    application = DebuggedApplication(application, evalex=True)

########NEW FILE########
__FILENAME__ = runtests
#! /usr/bin/env python

sources = """
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
"""

import sys
import base64
import zlib

class DictImporter(object):
    def __init__(self, sources):
        self.sources = sources

    def find_module(self, fullname, path=None):
        if fullname == "argparse" and sys.version_info >= (2,7):
            # we were generated with <python2.7 (which pulls in argparse)
            # but we are running now on a stdlib which has it, so use that.
            return None
        if fullname in self.sources:
            return self
        if fullname + '.__init__' in self.sources:
            return self
        return None

    def load_module(self, fullname):
        # print "load_module:",  fullname
        from types import ModuleType
        try:
            s = self.sources[fullname]
            is_pkg = False
        except KeyError:
            s = self.sources[fullname + '.__init__']
            is_pkg = True

        co = compile(s, fullname, 'exec')
        module = sys.modules.setdefault(fullname, ModuleType(fullname))
        module.__file__ = "%s/%s" % (__file__, fullname)
        module.__loader__ = self
        if is_pkg:
            module.__path__ = [fullname]

        do_exec(co, module.__dict__)
        return sys.modules[fullname]

    def get_source(self, name):
        res = self.sources.get(name)
        if res is None:
            res = self.sources.get(name + '.__init__')
        return res

if __name__ == "__main__":
    if sys.version_info >= (3, 0):
        exec("def do_exec(co, loc): exec(co, loc)\n")
        import pickle
        sources = sources.encode("ascii") # ensure bytes
        sources = pickle.loads(zlib.decompress(base64.decodebytes(sources)))
    else:
        import cPickle as pickle
        exec("def do_exec(co, loc): exec co in loc\n")
        sources = pickle.loads(zlib.decompress(base64.decodestring(sources)))

    importer = DictImporter(sources)
    sys.meta_path.insert(0, importer)

    entry = "import py; raise SystemExit(py.test.cmdline.main(['-s']))"
    do_exec(entry, locals())

########NEW FILE########
__FILENAME__ = api
""" Simple API for tests. """
from adrest.views import ResourceView
from adrest.api import Api


api = Api(api_rpc=True)


@api.register
class PirateResource(ResourceView):

    """ Part of simple API for tests. """

    class Meta:
        allowed_methods = 'get', 'POST', 'pUt', 'delete', 'Patch'
        model = 'core.pirate'


@api.register
class BoatResource(ResourceView):

    """ Part of simple API for tests. """

    class Meta:
        allowed_methods = 'get', 'post', 'put', 'delete'
        model = 'core.boat'
        parent = PirateResource


api2 = Api('1.0.0')
api2.register(PirateResource)

########NEW FILE########
__FILENAME__ = models
""" Models for tests. """

from django.db import models


class Pirate(models.Model):

    """ Mighty pirates. """

    name = models.CharField(max_length=50)
    captain = models.BooleanField(default=False)
    character = models.CharField(max_length=10, choices=(
        ('good', 'good'),
        ('evil', 'evil'),
        ('sorrow', 'sorrow'),
    ))

    def __unicode__(self):
        return self.name


class Island(models.Model):

    """ Magical islands. """

    title = models.CharField(max_length=50)


class Treasure(models.Model):

    """ Incrediable treasures. """

    created_at = models.DateTimeField(auto_now_add=True)
    pirate = models.ForeignKey(Pirate, null=True, blank=True)
    island = models.ForeignKey(Island)


class Boat(models.Model):

    """ Fastest boats. """

    title = models.CharField(max_length=50)
    pirate = models.ForeignKey(Pirate)

########NEW FILE########
__FILENAME__ = admin
""" Test the integration with Django admin.
"""

from django.test import TestCase


class CoreAdminTest(TestCase):

    """ Check ADRest models in Django admin. """

    def test_admin(self):
        """ Checking for ADRest models are registered. """
        from django.contrib import admin
        admin.autodiscover()

        from adrest.models import AccessKey
        self.assertTrue(AccessKey in admin.site._registry)

        from adrest.models import Access
        self.assertTrue(Access in admin.site._registry)

# lint_ignore=W0212

########NEW FILE########
__FILENAME__ = api
""" Test ADRest API module. """
from django.test import TestCase, RequestFactory

from adrest.views import ResourceView
from adrest.utils.emitter import XMLEmitter


class CoreApiTest(TestCase):

    """ Test api. """

    def test_base(self):
        """ Test main functionality. """
        from adrest.api import Api

        api = Api('1.0.0')
        self.assertEqual(api.version, '1.0.0')
        self.assertTrue(api.urls)

        class Resource(ResourceView):

            class Meta:
                model = 'core.pirate'

        api.register(Resource)
        self.assertEqual(len(api.urls), 2)
        self.assertTrue(api.resources.get('pirate'))

        class TreasureResource(ResourceView):

            class Meta:
                parent = Resource
                model = 'core.treasure'

        api.register(TreasureResource)
        self.assertEqual(len(api.urls), 3)
        self.assertTrue(api.resources.get('pirate-treasure'))

        class PrefixResource(TreasureResource):
            class Meta:
                prefix = 'more'

        api.register(PrefixResource)
        self.assertEqual(len(api.urls), 4)
        self.assertTrue(api.resources.get('pirate-more-treasure'))

        class Resource2(ResourceView):

            class Meta:
                model = 'core.pirate'
                emitters = XMLEmitter

        api.register(Resource2, name='wow')
        resource = api.resources.get('wow')
        self.assertEqual(resource._meta.emitters, (XMLEmitter,))
        self.assertEqual(resource._meta.name, 'wow')

    def test_register(self):
        """ Test register method. """
        from adrest.api import Api

        api = Api('1.0.0')

        class TestResource(ResourceView):

            class Meta:
                name = 'test1'

        api.register(TestResource, name='test2')
        resource = api.resources.get('test2')
        self.assertEqual(resource._meta.name, 'test2')

        @api.register
        class TestResource(ResourceView):

            class Meta:
                name = 'test3'

        self.assertTrue('test3' in api.resources)

        @api.register()
        class TestResource(ResourceView):

            class Meta:
                name = 'test4'

        self.assertTrue('test4' in api.resources)

        @api.register(name='test6')
        class TestResource(ResourceView):

            class Meta:
                name = 'test5'

        self.assertFalse('test5' in api.resources)
        self.assertTrue('test6' in api.resources)

    def test_fabric(self):
        from adrest.api import Api

        api = Api('1.0.0')

        @api.register
        class PirateResource(ResourceView):

            class Meta:
                model = 'core.pirate'

            def get_collection(self, request, **resources):
                return super(PirateResource, self).get_collection(
                    request, **resources)

        resource = api.resources['pirate']
        rf = RequestFactory()
        response = resource().dispatch(rf.get('/'))
        self.assertContains(response, 'resources')

    def test_version(self):
        """ Test version. """
        from ..api import api2

        resource = api2.resources.get('pirate')
        self.assertEqual(resource.api, api2)

        uri = api2.testCase.reverse('pirate')
        self.assertEqual(uri, '/pirates2/1.0.0/pirate/')



# lint_ignore=E0102,W0404,C0110

########NEW FILE########
__FILENAME__ = auth
""" Tests ADRest auth mixin.
"""
from django.views.generic import View

from ..api import api as API
from adrest.mixin import AuthMixin
from adrest.tests import AdrestTestCase
from adrest.utils.auth import UserAuthenticator


class CoreAuthTest(AdrestTestCase):

    """ Auth related tests. """

    api = API

    def test_meta(self):
        """ Test a meta attribute generation. """

        class Resource(View, AuthMixin):

            class Meta:
                model = 'core.pirate'
                authenticators = UserAuthenticator

        self.assertTrue(Resource._meta)
        self.assertTrue(Resource._meta.authenticators)
        self.assertEqual(Resource._meta.authenticators, (UserAuthenticator,))

# lint_ignore=W0212

########NEW FILE########
__FILENAME__ = dynamic
from django.test import RequestFactory
from django.views.generic import View
from mixer.backend.django import mixer

from ..api import api as API
from adrest.mixin import DynamicMixin


class CoreDynamicTest(API.testCase):

    def test_base(self):

        pirates = mixer.cycle(3).blend('core.pirate')

        class SomeResource(DynamicMixin, View):

            class Meta:
                model = 'core.pirate'

            def dispatch(self, request, **resources):
                return self.get_collection(request, **resources)

        rf = RequestFactory()
        resource = SomeResource()

        response = resource.dispatch(rf.get('/'))
        self.assertEqual(len(response), len(pirates))

        response = resource.dispatch(rf.get('/?name=' + pirates[0].name))
        self.assertEqual(list(response), [pirates[0]])

        response = resource.dispatch(
            rf.get('/?adr-sort=name&adr-sort=captain'))
        self.assertEqual(list(response), sorted(
            pirates, key=lambda p: (p.name, p.captain)))

    def test_pagination(self):

        pirates = mixer.cycle(3).blend('core.pirate')

        class SomeResource(DynamicMixin, View):

            class Meta:
                model = 'core.pirate'
                limit_per_page = 2

            def dispatch(self, request, **resources):
                collection = self.get_collection(request, **resources)
                return self.paginate(request, collection)

        rf = RequestFactory()
        resource = SomeResource()

        response = resource.dispatch(rf.get('/'))
        self.assertEqual(len(response.resources), 2)

        resource._meta.limit_per_page = 0
        response = resource.dispatch(rf.get('/'))
        self.assertEqual(len(response), len(pirates))

        response = resource.dispatch(rf.get('/?adr-max=1'))
        self.assertEqual(len(response.resources), 1)

# lint_ignore=C0110,E1103

########NEW FILE########
__FILENAME__ = emitter
""" Tests ADRest emitter mixin.
"""
from django.views.generic import View

from ..api import api as API
from adrest.mixin import EmitterMixin
from adrest.tests import AdrestTestCase
from mixer.backend.django import mixer


class CoreEmitterTest(AdrestTestCase):

    """ Emitter related tests. """

    api = API

    def test_meta(self):
        """ Test a meta attribute generation. """

        class Resource(View, EmitterMixin):

            class Meta:
                model = 'core.pirate'

        self.assertTrue(Resource._meta)
        self.assertTrue(Resource._meta.emitters)

    def test_to_simple(self):
        """ Test resource's to simple method.

        :return :

        """

        pirates = mixer.cycle(2).blend('core.pirate')

        class Resource(View, EmitterMixin):

            class Meta:
                model = 'core.pirate'

            def to_simple(self, content, simple, serializer=None):

                return simple + ['HeyHey!']

        resource = Resource()
        response = resource.emit(pirates)
        self.assertTrue('HeyHey!' in response.content)

        class Resource(View, EmitterMixin):

            class Meta:
                model = 'core.pirate'

            @staticmethod
            def to_simple__name(pirate, serializer=None):

                return 'Evil ' + pirate.name

        resource = Resource()
        pirate = pirates[0]
        response = resource.emit(pirate)
        self.assertTrue('Evil ' + pirate.name in response.content)

    def test_model_options(self):

        boats = mixer.cycle(2).blend('core.boat')

        class Resource(View, EmitterMixin):

            class Meta:
                model = 'core.boat'
                emit_models = dict(
                    include='hooray'
                )

            @staticmethod
            def to_simple__hooray(boat, serializer=None):
                return 'hooray'

        resource = Resource()
        response = resource.emit(boats)
        self.assertTrue('hooray' in response.content)

        boat = boats[0]
        resource._meta.emit_models['exclude'] = 'title'
        response = resource.emit(boat)
        self.assertFalse(boat.title in response.content)

        resource._meta.emit_models['related'] = dict(
            pirate=dict(
                fields='name'
            )
        )
        response = resource.emit(boat)
        self.assertTrue(boat.pirate.name in response.content)

        class Resource(View, EmitterMixin):

            class Meta:
                model = 'core.boat'
                emit_include = 'hooray'

            @staticmethod
            def to_simple__hooray(boat, serializer=None):
                return 'hooray'

        resource = Resource()
        response = resource.emit(boats)
        self.assertTrue('hooray' in response.content)

    def test_format(self):
        pirate = mixer.blend('core.pirate')

        class Resource(View, EmitterMixin):
            class Meta:
                model = 'core.pirate'

        resource = Resource()
        response = resource.emit(pirate)
        self.assertTrue('fields' in response.content)

        resource._meta.emit_format = 'simple'
        response = resource.emit(pirate)
        self.assertFalse('fields' in response.content)


# lint_ignore=W0212,E0102,C0110

########NEW FILE########
__FILENAME__ = handler
from django.db import models
from django.views.generic import View
from django.test import RequestFactory
from mixer.backend.django import mixer

from adrest.mixin import HandlerMixin
from ..api import api as API


class CoreHandlerTest(API.testCase):

    def test_meta_model(self):

        class Resource(View, HandlerMixin):

            class Meta:
                model = 'core.pirate'

        self.assertTrue(issubclass(Resource._meta.model, models.Model))

    def test_meta_name(self):

        class Resource(View, HandlerMixin):

            class Meta:
                model = 'core.pirate'

        self.assertEqual(Resource._meta.name, 'pirate')

        class IslandResource(View, HandlerMixin):

            class Meta:
                name = 'map'
                model = 'core.island'

        self.assertEqual(IslandResource._meta.name, 'map')

        class TreasureResource(View, HandlerMixin):

            class Meta:
                parent = Resource
                model = 'core.treasure'

        self.assertEqual(TreasureResource._meta.name, 'treasure')

    def test_allowed_methods(self):

        resource = self.api.resources.get('pirate')
        self.assertEqual(
            resource._meta.allowed_methods,
            ('GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'))

    def test_methods(self):

        for _ in xrange(3):
            pirate = mixer.blend('core.pirate', character='good')

        response = self.get_resource('pirate')
        self.assertContains(response, '"count": 3')

        response = self.post_resource('pirate', data=dict(
            name='John',
            character='evil',
        ))
        self.assertContains(response, '"name": "John"')

        john = response.response
        response = self.put_resource('pirate', pirate=john, data=dict(
            name='Billy'
        ))
        self.assertContains(response, '"name": "Billy"')
        billy = response.response
        self.assertEqual(john, billy)

        response = self.delete_resource('pirate', pirate=billy)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(billy).objects.filter(name='Billy').count(), 0)

        response = self.patch_resource('pirate', data=dict(
            pirate=[1, 2],
            name='Tom'
        ))
        self.assertEqual(len(response.response), 2)

        for pirate in response.response:
            self.assertEqual(pirate.name, 'Tom')
            self.assertTrue(pirate.pk in [1, 2])

    def test_mixin(self):

        pirate = mixer.blend('core.pirate')

        class SomeResource(HandlerMixin, View):

            class Meta:
                allowed_methods = 'get', 'post'
                model = 'core.pirate'

            def dispatch(self, request, **resources):

                self.check_method_allowed(request)

                resources = self.get_resources(request, **resources)

                return self.handle_request(request, **resources)

        rf = RequestFactory()
        request = rf.get('/')
        resource = SomeResource()
        response = resource.dispatch(request)
        self.assertTrue(pirate in response.resources)

    def test_resources(self):
        pirates = mixer.cycle(2).blend('core.pirate', character='evil')
        response = self.put_resource(
            'pirate', data=dict(
                pirate=[p.pk for p in pirates],
                character='good',
            )
        )
        for p in response.json:
            self.assertEqual(p['fields']['character'], 'good')

        response = self.put_resource(
            'pirate', data=dict(
                pirate=[p.pk for p in pirates],
                character='sorrow',
            ), json=True
        )
        for p in response.json:
            self.assertEqual(p['fields']['character'], 'sorrow')


# lint_ignore=F0401,C,E1103

########NEW FILE########
__FILENAME__ = resource
from mixer.backend.django import mixer

from ..api import api as API
from adrest.tests import AdrestTestCase
from adrest.views import ResourceView


class CoreResourceTest(AdrestTestCase):

    api = API

    def test_meta(self):

        class AlphaResource(ResourceView):
            pass
        self.assertEqual(AlphaResource._meta.name, 'alpha')

        class BetaResource(ResourceView):
            pass
        self.assertEqual(BetaResource._meta.name, 'beta')
        self.assertEqual(BetaResource._meta.url_name, 'beta')

        class GammaResource(ResourceView):

            class Meta:
                parent = BetaResource

        self.assertEqual(GammaResource._meta.parents, [BetaResource])
        self.assertEqual(GammaResource._meta.name, 'gamma')
        self.assertEqual(GammaResource._meta.url_name, 'beta-gamma')

    def test_resources(self):

        pirate = mixer.blend('core.pirate')
        for _ in xrange(3):
            mixer.blend('core.boat', pirate=pirate)

        self.assertEqual(pirate.boat_set.count(), 3)

        self.delete_resource('pirate-boat', pirate=pirate, data=dict(
            boat=[b.pk for b in pirate.boat_set.all()[:2]]
        ))
        self.assertEqual(pirate.boat_set.count(), 1)

    def test_urls(self):
        class AlphaResource(ResourceView):
            pass

        self.assertEqual(
            AlphaResource._meta.url_regex, 'alpha/(?P<alpha>[^/]+)?')

        class BetaResource(ResourceView):
            class Meta:
                parent = AlphaResource

        self.assertEqual(
            BetaResource._meta.url_regex,
            'alpha/(?P<alpha>[^/]+)?/beta/(?P<beta>[^/]+)?')

        class GammaResource(BetaResource):
            class Meta:
                prefix = 'gamma-prefix'

        self.assertEqual(
            GammaResource._meta.url_regex,
            'alpha/(?P<alpha>[^/]+)?/gamma-prefix/gamma/(?P<gamma>[^/]+)?')

        class ZetaResource(ResourceView):
            class Meta:
                parent = GammaResource

        self.assertEqual(
            ZetaResource._meta.url_regex,
            'alpha/(?P<alpha>[^/]+)?/gamma-prefix/gamma/(?P<gamma>[^/]+)?/zeta/(?P<zeta>[^/]+)?') # nolint

# lint_ignore=F0401,C0110

########NEW FILE########
__FILENAME__ = rpc
from ..api import api as API


class AutoJSONRPCTest(API.testCase):

    def test_base(self):
        self.assertTrue('autojsonrpc' in self.api.resources)

        uri = self.reverse('autojsonrpc')
        self.assertEqual(uri, '/pirates/rpc')

        response = self.get_resource('autojsonrpc')
        self.assertContains(response, 'Invalid RPC Call.')

# lint_ignore=C0110

########NEW FILE########
__FILENAME__ = serializer
from django.test import TestCase
from mixer.backend.django import mixer


class CoreSerializerTest(TestCase):

    def setUp(self):
        for _ in range(1, 10):
            mixer.blend('main.book')

    def test_base_types(self):
        """ Testing serialization of base types.
        """
        from adrest.utils.serializer import BaseSerializer
        try:
            from collections import OrderedDict
        except ImportError:
            from ordereddict import OrderedDict # nolint

        from datetime import datetime
        from decimal import Decimal

        serializer = BaseSerializer()
        data = dict(
            string_='test',
            unicode_=unicode('test'),
            datetime_=datetime(2007, 01, 01),
            odict_=OrderedDict(value=1),
            dict_=dict(
                list_=[1, 2.35, Decimal(3), False]
            )
        )

        value = serializer.serialize(data)
        self.assertEqual(value, dict(
            string_=u'test',
            unicode_=u'test',
            datetime_='2007-01-01T00:00:00',
            odict_=dict(value=1),
            dict_=dict(
                list_=[1, 2.35, 3.0, False]
            )
        ))

    def test_django_model(self):
        from adrest.utils.serializer import BaseSerializer

        pirate = mixer.blend('core.pirate', name='Billy')
        data = [
            mixer.blend('core.boat', pirate=pirate),
            mixer.blend('core.boat', pirate=pirate),
            28, 'string']

        serializer = BaseSerializer(
            exclude='fake',
            include='pk',
            related=dict(
                pirate=dict(fields='character')
            ),
        )
        self.assertEqual(serializer.model_options['exclude'], set(['fake']))

        out = serializer.to_simple(data, **serializer.model_options)
        self.assertTrue(out[0]['fields']['pk'])
        self.assertEqual(out[0]['fields']['pirate']['fields']['character'],
                         data[0].pirate.character)

        # Test m2o serialization
        serializer = BaseSerializer(
            include="boat_set",
            related=dict(
                boat_set=dict(
                    fields=[])
            ),
        )
        out = serializer.to_simple(pirate, **serializer.model_options)

        self.assertEquals(len(out['fields']['boat_set']), 2)
        for boat in out['fields']['boat_set']:
            self.assertEquals(boat['fields']['pirate'], pirate.pk)
            self.assertTrue('title' in boat['fields'].keys())

        out = serializer.to_simple(pirate)
        self.assertTrue('model' in out)

        out = serializer.to_simple(pirate, include=['boat_set'])
        self.assertTrue(out['fields']['boat_set'])
        self.assertEqual(len(list(out['fields']['boat_set'])), 2)

    def test_paginator(self):
        from adrest.mixin import EmitterMixin
        from django.views.generic import View
        from django.test import RequestFactory
        from tests.core.models import Pirate
        from adrest.utils.paginator import Paginator

        pirates = mixer.cycle(3).blend('core.pirate')

        class SomeResource(EmitterMixin, View):

            class Meta:
                model = 'core.pirate'
                dyn_prefix = 'adr-'
                limit_per_page = 2

            def dispatch(self, request, **resources):
                p = Paginator(request, self, Pirate.objects.all())
                return self.emit(p, request=request)

        rf = RequestFactory()
        resource = SomeResource()

        response = resource.dispatch(rf.get('/'))
        self.assertContains(response, '"page": 1')
        self.assertContains(response, '"num_pages": 2')

    def test_xml(self):
        from adrest.utils.serializer import XMLSerializer
        from ...main.models import Book

        for _ in range(1, 10):
            mixer.blend(Book)
        worker = XMLSerializer()
        test = worker.serialize(Book.objects.all())
        self.assertTrue("author" in test)

    def test_json(self):
        from ...main.models import Author
        from adrest.utils.serializer import JSONSerializer

        authors = Author.objects.all()
        worker = JSONSerializer(options=dict(
            separators=(',', ':')
        ))
        test = worker.serialize(authors)
        self.assertTrue("main.author" in test)
        self.assertTrue('"fields":{"active":true,"name"' in test)

# lint_ignore=C0110,F0401

########NEW FILE########
__FILENAME__ = test
from mixer.backend.django import mixer

from ..api import api as API
from adrest.tests import AdrestTestCase


class CoreAdrestTests(AdrestTestCase):

    api = API

    def test_json(self):
        pirate = mixer.blend('core.pirate', character='good')

        response = self.put_resource(
            'pirate', pirate=pirate, json=True, data=dict(name='John'))
        self.assertContains(response, '"name": "John"')

# lint_ignore=F0401,C

########NEW FILE########
__FILENAME__ = utils
from django.test import TestCase
from adrest.utils import tools
from adrest.tests import AdrestRequestFactory


class UtilsTests(TestCase):

    def test_as_tuple(self):
        self.assertEqual(tools.as_tuple(None), tuple())
        self.assertEqual(tools.as_tuple(''), tuple())
        self.assertEqual(tools.as_tuple([]), tuple())
        self.assertEqual(tools.as_tuple([1, 2]), (1, 2))
        self.assertEqual(tools.as_tuple(set([1, 2])), (1, 2))
        self.assertEqual(tools.as_tuple({1: 1}), ({1: 1},))
        test = object()
        self.assertEqual(tools.as_tuple(test), (test,))

    def test_fix_request(self):
        rf = AdrestRequestFactory()
        request = rf.put('/test', {
            'foo': 'bar'
        })
        self.assertFalse(request.REQUEST.items())

        fixed = tools.fix_request(request)
        self.assertTrue(fixed.adrest_fixed)
        self.assertTrue(fixed.REQUEST.items())

########NEW FILE########
__FILENAME__ = urls
""" Collect URLS from apps. """
from django.conf.urls import include, patterns

from ..main.api import API as main
from ..main.resources import DummyResource
from ..rpc.api import API as rpc
from .api import api as pirates, api2 as pirates2


urlpatterns = main.urls + patterns(
    '',
    DummyResource.as_url(),
    (r'^rpc/', include(rpc.urls)),

    (r'^pirates/', include(pirates.urls)),
    (r'^pirates2/', include(pirates2.urls)),

)

########NEW FILE########
__FILENAME__ = api
from .resources import (
    AuthorResource, BookPrefixResource, ArticleResource, SomeOtherResource,
    CustomResource, BSONResource, CSVResource)
from adrest.api import Api
from adrest.utils.auth import AnonimousAuthenticator, AccessKeyAuthenticator, \
    UserAuthenticator
from adrest.utils.emitter import XMLTemplateEmitter, JSONEmitter, BSONEmitter
from adrest.utils.parser import BSONParser
from adrest.utils.throttle import CacheThrottle


class CustomUserAuth(UserAuthenticator):
    username_fieldname = 'nickname'


API = Api(
    version=(1, 0, 0), emitters=(XMLTemplateEmitter, JSONEmitter),
    throttle=CacheThrottle, api_prefix='main')

API.register(AuthorResource,
             authenticators=(CustomUserAuth, AnonimousAuthenticator))
API.register(BookPrefixResource)
API.register(CustomResource)
API.register(ArticleResource, authenticators=AccessKeyAuthenticator)
API.register(SomeOtherResource, url_name='test', url_regex='test/mem/$')
API.register(BSONResource, parsers=(BSONParser,), emitters=(BSONEmitter,))
API.register(CSVResource)

# lint_ignore=C

########NEW FILE########
__FILENAME__ = models
#!/usr/bin/env python
# coding: utf-8
from django.contrib.auth.models import User
from django.db import models


class Author(models.Model):
    name = models.CharField(max_length=100,
            help_text=u"Имя автора")
    user = models.ForeignKey(User)
    active = models.BooleanField(default=True)


class Publisher(models.Model):
    title = models.CharField(max_length=100)


class Book(models.Model):
    title = models.CharField(max_length=100)
    status = models.IntegerField(choices=(
        (1, 'new'),
        (2, 'published'),
        (3, 'archived'),
    ))
    author = models.ForeignKey(Author)
    price = models.PositiveIntegerField(default=0, blank=True)
    publisher = models.ForeignKey(Publisher, null=True, blank=True)
    books = models.ManyToManyField('self', blank=True)


class Article(models.Model):
    title = models.CharField(max_length=100)
    book = models.ForeignKey(Book)

########NEW FILE########
__FILENAME__ = resources
from .models import Book

from django.http import HttpResponse

from adrest.utils.emitter import JSONEmitter
from adrest.utils.exceptions import HttpError
from adrest.views import ResourceView


class AuthorResource(ResourceView):

    class Meta:
        allowed_methods = 'GET', 'POST', 'PATCH'
        model = 'main.author'
        url_regex = '^owner/$'


class BookResource(ResourceView):

    class Meta:
        allowed_methods = 'GET', 'post', 'pUt', 'DELETE'
        parent = AuthorResource
        model = 'main.book'


class BookPrefixResource(BookResource):

    class Meta:
        prefix = 'test'


class ArticleResource(ResourceView):

    class Meta:
        allowed_methods = 'GET', 'PUT', 'DELETE'
        parent = BookPrefixResource
        model = 'main.article'

    def put(self, request, **kwargs):
        assert False, "Assertion error"

    def delete(self, request, **kwargs):
        raise Exception("Some error")


class OtherResource(ResourceView):

    class Meta:
        parent = BookResource

    def get(self, request, **kwargs):
        return True


class SomeOtherResource(ResourceView):

    class Meta:
        parent = AuthorResource
        url_params = 'device',

    def get(self, request, **kwargs):
        return self.paginate(request, [1, 2, 3])


class CustomResource(ResourceView):

    class Meta:
        allowed_methods = 'GET', 'POST'
        model = 'main.book'
        queryset = Book.objects.all()
        emit_template = 'main/custom.xml'

    def get(self, request, **kwargs):
        return list(self._meta.queryset)

    def post(self, request, **resources):
        try:
            request.data['test'] = 123
        except TypeError, e:
            raise HttpError(dict(error=str(
                e)), status=400, emitter=JSONEmitter)


class DummyResource(ResourceView):

    class Meta:
        name = 'iamdummy'

    def get(self, request, **resources):
        return True


class BSONResource(ResourceView):

    class Meta:
        allowed_methods = 'GET', 'POST'

    COUNTER = 1

    def get(self, request, **resources):
        return dict(counter=self.COUNTER)

    def post(self, request, **resources):
        self.COUNTER += request.data.get('counter', 0)
        return dict(counter=self.COUNTER)


class CSVResource(ResourceView):

    class Meta:
        allowed_methods = 'GET'

    def get(self, request, **resources):
        return HttpResponse('value'.encode("utf-16"), mimetype="text/csv")

# lint_ignore=C

########NEW FILE########
__FILENAME__ = tests
import random
import re
from decimal import Decimal

from django.contrib.auth.models import User
from django.core import mail
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.test import TestCase, Client, RequestFactory
from django.views.generic import View
from mixer.backend.django import mixer

from .api import API as api
from .models import Author, Book
from .resources import (AuthorResource, BookPrefixResource,
                        ArticleResource, SomeOtherResource, BookResource)
from adrest.mixin.emitter import EmitterMixin
from adrest.models import Access
from adrest.tests.utils import AdrestTestCase
from adrest.utils import emitter, parser


class MixinTest(TestCase):

    def setUp(self):
        self.rf = RequestFactory()

    def test_emitter(self):
        request = self.rf.get("/")

        class Test(View, EmitterMixin):

            def get(self, request):
                content = self.emit('test')
                response = HttpResponse(content)
                return response

        test = Test()
        response = test.dispatch(request)
        self.assertContains(response, 'test')

        content = emitter.JSONSerializer().serialize([1, Decimal('3.4'), None])
        self.assertTrue('3.' in content and 'null' in content)


class MetaTest(TestCase):

    def test_meta(self):
        self.assertTrue(AuthorResource._meta)
        self.assertEqual(AuthorResource._meta.allowed_methods, (
            'GET', 'POST', 'PATCH', 'OPTIONS', 'HEAD'
        ))
        self.assertEqual(AuthorResource._meta.name, 'author')
        self.assertEqual(AuthorResource._meta.url_name, 'author')
        self.assertEqual(AuthorResource._meta.url_regex, '^owner/$')
        self.assertEqual(AuthorResource._meta.parents, [])
        self.assertEqual(AuthorResource._meta.emitters_dict, {
            emitter.JSONEmitter.media_type: emitter.JSONEmitter,
        })
        self.assertEqual(AuthorResource._meta.parsers_dict, {
            parser.FormParser.media_type: parser.FormParser,
            parser.XMLParser.media_type: parser.XMLParser,
            parser.JSONParser.media_type: parser.JSONParser,
        })
        self.assertEqual(
            AuthorResource._meta.default_parser, parser.FormParser)

    def test_meta_parents(self):
        self.assertEqual(AuthorResource._meta.parents, [])
        self.assertEqual(BookPrefixResource._meta.parents, [AuthorResource])
        self.assertEqual(ArticleResource._meta.parents, [
                         AuthorResource, BookPrefixResource])

    def test_meta_name(self):
        self.assertEqual(AuthorResource._meta.name, 'author')
        self.assertEqual(BookPrefixResource._meta.name, 'book')
        self.assertEqual(SomeOtherResource._meta.name, 'someother')

    def test_meta_url_name(self):
        self.assertEqual(AuthorResource._meta.url_name, 'author')
        self.assertEqual(BookResource._meta.url_name, 'author-book')
        self.assertEqual(BookPrefixResource._meta.url_name, 'author-test-book')
        self.assertEqual(
            ArticleResource._meta.url_name, 'author-test-book-article')
        self.assertEqual(
            SomeOtherResource._meta.url_name, 'author-device-someother')

    def test_meta_url_regex(self):
        self.assertEqual(AuthorResource._meta.url_regex, '^owner/$')
        self.assertEqual(BookPrefixResource._meta.url_regex,
                         'owner/test/book/(?P<book>[^/]+)?')

        self.assertEqual(
            ArticleResource._meta.url_regex,
            'owner/test/book/(?P<book>[^/]+)?/article/(?P<article>[^/]+)?')

        self.assertEqual(
            SomeOtherResource._meta.url_regex,
            'owner/device/(?P<device>[^/]+)/someother/(?P<someother>[^/]+)?')


class ApiTest(AdrestTestCase):

    api = api

    def test_api(self):
        self.assertTrue(api.version)
        self.assertEqual(str(api), "1.0.0")
        self.assertTrue(api.urls)

    def test_urls(self):
        uri = self.reverse('test')
        self.assertEqual(uri, '/1.0.0/test/mem')
        response = self.client.get('/1.0.0/test/mem')
        self.assertContains(response, 'true')

        response = self.client.get('/1.0.0/test/mem/')
        self.assertContains(response, 'true')


class AdrestTest(AdrestTestCase):

    api = api

    def setUp(self):
        self.author = mixer.blend('main.author')
        self.book = mixer.blend('main.book', author=self.author)

    def test_urls(self):
        uri = reverse('iamdummy')
        self.assertEqual(uri, '/iamdummy/')

    def test_methods(self):
        uri = self.reverse('author')
        self.assertEqual(uri, '/1.0.0/owner')
        response = self.client.get(uri)
        self.assertContains(response, 'true')

        response = self.client.put(uri)
        self.assertContains(response, 'false', status_code=405)

        response = self.client.head(uri)
        self.assertEqual(response.status_code, 200)

    def test_owners_checking(self):
        response = self.get_resource(
            'author-test-book-article', book=self.book.pk, data=dict(
            author=self.author.pk
            ))
        self.assertContains(response, 'false', status_code=401)

        response = self.get_resource(
            'author-test-book-article',
            key=self.author.user.accesskey_set.get(),
            book=self.book.pk, data=dict(author=self.author.pk))
        self.assertContains(response, 'true')

    def test_access_logging(self):
        uri = self.reverse('author-test-book-article', book=self.book.pk)
        self.client.get(uri)
        access = Access.objects.get()
        self.assertEqual(access.uri, uri)
        self.assertEqual(access.version, str(api))

        # Do not write to access log
        response = self.get_resource('csv')
        self.assertEquals(response['Content-Type'], 'text/csv')
        access = Access.objects.filter(uri=response.request['PATH_INFO'])
        self.assertEquals(access.count(), 1)
        self.assertEquals(
            access.get().response, "Invalid response content encoding")

    def test_options(self):
        self.assertTrue('OPTIONS' in ArticleResource._meta.allowed_methods)
        uri = self.reverse('author-test-book-article', book=self.book.pk)
        response = self.client.options(uri, data=dict(author=self.author.pk))
        self.assertContains(response, 'OK')

        author = mixer.blend('main.author')
        response = self.client.options(uri, data=dict(author=author.pk))
        self.assertContains(response, 'OK')


class ResourceTest(AdrestTestCase):

    api = api

    def setUp(self):
        super(ResourceTest, self).setUp()
        for i in range(5):
            user = User.objects.create(username='test%s' % i)
            self.author = Author.objects.create(name='author%s' % i, user=user)

        for i in range(148):
            Book.objects.create(author=self.author, title="book%s" %
                                i, status=random.choice((1, 2, 3)), price=432)

    def test_patch(self):
        response = self.patch_resource('author')
        self.assertContains(response, 'found', status_code=404)

    def test_author(self):
        response = self.get_resource('author')
        self.assertContains(response, 'count="5"')

        response = self.post_resource('author', data=dict(
            name="new author",
            user=User.objects.create(username="new user").pk))
        self.assertContains(response, 'new author')

        response = self.post_resource('author', data=dict(name="author 22"))
        self.assertContains(response, 'field is required', status_code=400)

    def test_collection_put_delete(self):
        status1 = Book.objects.filter(status=1)
        response = self.put_resource('author-test-book', data=dict(
            status=3,
            author=self.author.pk,
            book=[b.pk for b in status1]
        ))
        self.assertContains(response, 'count="%s"' % len(status1))
        self.assertContains(response, '<status>3</status>')
        self.assertNotContains(response, '<status>1</status>')
        self.assertFalse(Book.objects.filter(status=1).count())

        status2 = Book.objects.filter(status=2)
        response = self.delete_resource('author-test-book', data=dict(
            author=self.author.pk,
            book=[b.pk for b in status2]
        ))
        self.assertContains(response, '')
        self.assertFalse(Book.objects.filter(status=2).count())

    def test_book(self):
        uri = self.reverse('author-test-book')
        self.assertEqual(uri, "/1.0.0/owner/test/book/")

        response = self.get_resource('author-test-book', data=dict(
            author=self.author.pk
        ))
        self.assertContains(response, 'count="%s"' %
                            Book.objects.filter(author=self.author).count())
        self.assertContains(response, '<name>%s</name>' % self.author.name)
        self.assertContains(response, '<book_price>432</book_price>')

        response = self.get_resource('author-test-book', data=dict(
            title__startswith="book1",
            title__megadeath=12,
        ))
        self.assertContains(response, 'count="%s"' % Book.objects.filter(
            title__startswith='book1').count())

        response = self.post_resource('author-test-book', data=dict(
            title="new book",
            status=2,
            author=self.author.pk))
        self.assertContains(response, '<price>0</price>')
        self.assertContains(
            response,
            '<json>{"fields": {"status": 2}, "model": "main.book", "pk": 149}</json>')  # nolint

        response = self.post_resource('author-test-book', json=True, data=dict(
            title="new book",
            status=2,
            author=self.author.pk))
        self.assertContains(response, '<price>0</price>')

        uri = self.reverse('author-test-book', book=1)
        uri = "%s?author=%s" % (uri, self.author.pk)
        response = self.client.put(uri, data=dict(
            price=199
        ))
        self.assertContains(response, '<price>199</price>')

        response = self.client.delete(uri)
        self.assertContains(response, '')

    def test_filter(self):
        uri = self.reverse('author-test-book')
        response = self.client.get(uri, data=dict(
            author=self.author.pk,
            title="book2"))
        self.assertContains(response, 'count="1"')

        response = self.client.get(uri, data=dict(
            author=self.author.pk,
            status=[1, 2, 3]))
        self.assertContains(
            response, 'count="%s"' % Book.objects.all().count())

        response = self.client.get(uri, data=dict(
            author=self.author.pk,
            status=[1, 3]))
        self.assertNotContains(response, '<status>2</status>')

        response = self.client.get(
            uri + "?title=book2&title=book3&author=%s" % self.author.pk)
        self.assertContains(response, 'count="2"')

    def test_not_filter(self):
        uri = self.reverse('author-test-book')

        exclude_author = Author.objects.create(
            name="exclude_author",
            user=User.objects.create(username="exclude_user"))

        for i in xrange(5):
            Book.objects.create(
                author=exclude_author, title="book_for_exclude%s" % i,
                status=i % 3 + 1, price=482)

        response = self.client.get(uri, data=dict(
            author__not=self.author.pk))

        self.assertContains(response, '<results count="5" page="1">')
        self.assertContains(response, '<name>exclude_author</name>')

        for i in xrange(5):
            self.assertContains(
                response, '<title>book_for_exclude%s</title>' % i)

        response = self.client.get(uri, data=dict(
            author__not=self.author.pk,
            status__not=[1, 3]))

        self.assertContains(response, '<results count="%s" page="1">' %
                            Book.objects.filter(author=exclude_author).
                            exclude(status__in=[1, 3]).count())
        self.assertNotContains(response, '<status>3</status>')
        self.assertNotContains(response, '<status>1</status>')
        self.assertContains(response, '<status>2</status>')
        self.assertContains(response, '<name>exclude_author</name>')

    def test_custom(self):
        uri = self.reverse('book')
        response = self.client.get(uri)
        self.assertContains(
            response, 'count="%s"' % Book.objects.all().count())
        book = Book.objects.create(author=self.author, title="book", status=1)
        response = self.client.get(uri)
        self.assertContains(
            response, 'count="%s"' % Book.objects.all().count())

        uri = self.reverse('author-test-book-article',
                           book=book.pk) + "?author=" + str(self.author.pk)
        response = self.client.delete(
            uri,
            HTTP_AUTHORIZATION=self.author.user.accesskey_set.get().key)
        self.assertContains(response, 'Some error', status_code=500)
        # self.assertEqual(len(mail.outbox), 1)

        self.assertEqual(
            mail.outbox[
                -1].subject, '[Django] ADREST API Error (500): /1.0.0/owner/test/book/%s/article/' % Book.objects.all().count())  # nolint

        response = self.client.put(
            uri, HTTP_AUTHORIZATION=self.author.user.accesskey_set.get().key)
        self.assertContains(response, 'Assertion error', status_code=400)
        # self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(
            mail.outbox[
                -1].subject, '[Django] ADREST API Error (400): /1.0.0/owner/test/book/%s/article/' % Book.objects.all().count())  # nolint

        response = self.post_resource('book')
        self.assertContains(response, '{"error": "\'Frozen', status_code=400)

    def test_some_other(self):
        response = self.get_resource('test')
        self.assertContains(response, 'count="3"')
        self.assertContains(response, '<someother>1</someother>')
        self.assertContains(response, '<method>GET</method>')

    def test_books(self):
        """Test response Link header

        Example: </1.0.0/author/5/test/book/?page=2>; rel="next"
        """
        link_re = re.compile(r'<(?P<link>[^>]+)>\; rel=\"(?P<rel>[^\"]+)\"')

        response = self.get_resource('author-test-book',
                                     data=dict(author=self.author.pk))
        self.assertTrue(response.has_header("Link"))
        self.assertEquals(
            response[
                "Link"], '<%s?page=2&author=5>; rel="next"' % self.reverse('author-test-book'))  # nolint
        # Get objects by links on Link header
        response = self.client.get(link_re.findall(response['Link'])[0][0])

        links = link_re.findall(response['Link'])

        self.assertEquals(links[0][0], '%s?page=3&author=5' %
                          self.reverse('author-test-book'))
        self.assertEquals(links[0][1], 'next')

        self.assertEquals(
            links[1][0], '%s?author=5' % self.reverse('author-test-book'))
        self.assertEquals(links[1][1], 'previous')

        response = self.get_resource(
            'author-test-book', data={
                'author': self.author.pk, 'adr-max': 0
            })
        self.assertFalse(response.has_header("Link"))

        response = self.get_resource(
            'author-test-book',
            data={
                'author': self.author.pk, 'adr-max': 'all'
            })
        self.assertEquals(response.status_code, 200)
        self.assertFalse(response.has_header("Link"))

    def test_bson(self):
        " Test BSON support. "

        from bson import BSON

        response = self.get_resource('bson')
        test = BSON(response.content).decode()
        self.assertEqual(test['counter'], 1)

        bson = BSON.encode(dict(counter=4))
        uri = self.reverse('bson')
        response = self.client.post(
            uri, data=bson, content_type='application/bson')
        test = BSON(response.content).decode()
        self.assertEqual(test['counter'], 5)


class AdrestMapTest(TestCase):

    def setUp(self):
        self.client = Client()

    def test_methods(self):
        uri = reverse("main-%s-map" % str(api))
        self.assertEqual(uri, "/%s/map" % api)
        response = self.client.get(uri)
        self.assertContains(response, 'API')
        self.assertContains(response, 'nickname')

        response = self.client.get(uri, HTTP_ACCEPT="application/json")
        self.assertContains(response, '"price", {"required": false')


# lint_ignore=F0401,C0110

########NEW FILE########
__FILENAME__ = api
from adrest.api import Api
from adrest.utils.auth import AnonimousAuthenticator
from adrest.utils.emitter import XMLEmitter, JSONTemplateEmitter
from adrest.views import ResourceView
from adrest.resources.rpc import RPCResource, JSONEmitter, JSONPEmitter


API = Api('1.0.0', api_rpc=True, emitters=XMLEmitter)


class TestAuth(AnonimousAuthenticator):

    def authenticate(self, request):
        return request.META.get('HTTP_AUTHORIZATION')

    def configure(self, request):
        self.resource.identifier = request.META.get('HTTP_AUTHORIZATION')


class TestResource(ResourceView):

    class Meta:
        allowed_methods = 'GET', 'POST', 'PUT'
        model = 'rpc.test'

    def get(self, request, **resources):
        assert not 'error' in request.GET, "Custom error"
        return True


class RootResource(ResourceView):

    class Meta:
        allowed_methods = 'GET', 'POST', 'PUT'
        model = 'rpc.root'


@API.register
class ChildResource(ResourceView):

    class Meta:
        allowed_methods = 'GET', 'POST', 'PUT'
        parent = RootResource
        model = 'rpc.child'


class CustomResource(ResourceView):

    class Meta:
        model = 'rpc.custom'


API.register(ChildResource)
API.register(CustomResource, emitters=JSONTemplateEmitter)
API.register(RootResource, authenticators=TestAuth)
API.register(RPCResource, url_regex=r'^rpc2$', url_name='rpc2',
             scheme='tests.rpc.dummy', emitters=(JSONEmitter, JSONPEmitter))
API.register(TestResource)

# lint_ignore=C

########NEW FILE########
__FILENAME__ = dummy
from adrest.resources.rpc import get_request


def method1(name):
    return "Hello {0}".format(name)


def method2(start=1, end=100):
    from random import randint
    return randint(start, end)


def error_method():
    raise Exception('Error here')


@get_request
def method3(request, name):
    return request.method + name


def __private_method():
    raise Exception("I am hidden!")

########NEW FILE########
__FILENAME__ = models
from django.db import models


class Test(models.Model):
    name = models.CharField(max_length=100)


class Root(models.Model):
    name = models.CharField(max_length=100)


class Child(models.Model):
    name = models.CharField(max_length=100)
    odd = models.IntegerField(default=0)
    root = models.ForeignKey(Root)


class Custom(models.Model):
    name = models.CharField(max_length=100)

########NEW FILE########
__FILENAME__ = tests
from adrest.tests.utils import AdrestTestCase
from django.utils import simplejson
from mixer.backend.django import mixer

from .api import API
from .models import Root, Child


class RPCTestCase(AdrestTestCase):
    api = API

    def setUp(self):
        self.root1 = Root.objects.create(name='test_root1')
        for i in xrange(10):
            Child.objects.create(root=self.root1, name='test_child1')

        self.root2 = Root.objects.create(name='test_root2')
        for i in xrange(10):
            Child.objects.create(
                root=self.root2, name='test_child2', odd=i % 2)

    def test_base_rpc(self):

        response = self.get_resource('rpc2', method='options')
        self.assertEqual(response.content, 'OK')

        # POST args
        response = self.rpc(
            'rpc2',
            rpc=dict(
                jsonrpc='2.0',
                method='method1',
                params=['test'],
            ))
        self.assertEqual(response.content, '"Hello test"')

        # POST kwargs
        response = self.rpc(
            'rpc2',
            rpc=dict(
                jsonrpc='2.0',
                method='method2',
                params=dict(
                    start=200,
                    end=300
                )
            ))
        response = simplejson.loads(response.content)
        self.assertTrue(200 <= response <= 300)

        response = self.rpc(
            'rpc2',
            rpc=dict(
                jsonrpc='2.0',
                method='wrongmethodname',
            ))
        self.assertContains(response, "Unknown method")

        # Handle Errors
        response = self.rpc(
            'rpc2',
            rpc=dict(
                jsonrpc='2.0',
                method='error_method',
            ))
        response = simplejson.loads(response.content)
        self.assertEqual(response['error']['message'], 'Error here')

        # GET JSONRPC
        response = self.rpc(
            'rpc2',
            callback='answer',
            rpc=dict(
                jsonrpc='2.0',
                method='method1',
                params=['test'],
            ))
        self.assertEqual(response.content, 'answer("Hello test")')

    def test_base(self):
        uri = self.reverse('test')
        self.assertEqual(uri, '/rpc/1.0.0/test/')

        response = self.get_resource('test')
        self.assertContains(response, 'true')

    def test_autojsonrpc(self):
        uri = self.reverse('autojsonrpc')
        self.assertEqual(uri, '/rpc/1.0.0/rpc')

        response = self.get_resource('autojsonrpc')
        self.assertContains(response, 'Invalid RPC Call.')

        response = self.rpc(
            'autojsonrpc',
            callback='answer',
            rpc=dict(
                method="iamwrongmethod",
            )
        )
        self.assertContains(response, 'Wrong method')

        response = self.rpc(
            'autojsonrpc',
            callback='answer',
            rpc=dict(method='bla.bla'))
        self.assertContains(response, 'Unknown method')

        response = self.rpc(
            'autojsonrpc',
            rpc=dict(
            method='test.bla'))
        self.assertContains(response, 'not allowed')

        response = self.rpc(
            'autojsonrpc',
            rpc=dict(
            method='test.get'))
        self.assertContains(response, 'true')

        response = self.rpc(
            'autojsonrpc',
            rpc=dict(
            method='root.get'))
        self.assertContains(response, 'Authorization required')

        response = self.rpc(
            'autojsonrpc',
            rpc=dict(
                headers=dict(Authorization=111),
                method='root.get'))
        self.assertContains(response, 'test_root')

        response = self.rpc(
            'autojsonrpc',
            rpc=dict(
                params=dict(root=self.root1.pk),
                method='root-child.get'))
        self.assertContains(response, '"count": 10')
        self.assertContains(response, 'test_child1')
        self.assertNotContains(response, 'test_child2')

        response = self.rpc(
            'autojsonrpc',
            rpc=dict(
                params=dict(root=self.root2.pk),
                data=dict(odd=1),
                method='root-child.get'))
        self.assertContains(response, '"count": 5')

        response = self.rpc(
            'autojsonrpc',
            key=111,
            rpc=dict(
                data=dict(name='root3'),
                method='root.post'))
        self.assertContains(response, 'root3')

        response = self.rpc(
            'autojsonrpc',
            key=111,
            rpc=dict(
                data=dict(name='child3'),
                params=dict(root=self.root1.pk),
                method='root-child.post'))
        self.assertContains(response, 'child3')

        child = Child.objects.get(name='child3')
        self.assertEqual(child.root, self.root1)

        response = self.rpc(
            'autojsonrpc',
            key=111,
            rpc=dict(
                data=dict(name='child4', root=self.root2.pk),
                params=dict(root=self.root1.pk),
                method='root-child.post'))
        self.assertContains(response, 'child4')

        child = Child.objects.get(name='child4')
        self.assertEqual(child.root, self.root1)

        response = self.rpc(
            'autojsonrpc',
            key=111,
            rpc=dict(
                data=dict(name='New name'),
                params=dict(root=self.root1.pk,
                            child=self.root1.child_set.all()[0].pk),
                method='root-child.put'))
        self.assertContains(response, 'New name')
        child = self.root1.child_set.all()[0]
        self.assertEqual(child.name, 'New name')

        response = self.rpc(
            'autojsonrpc',
            callback='test1234',
            rpc=dict(method='test.get'))
        self.assertContains(response, 'test1234')

        response = self.rpc(
            'autojsonrpc',
            callback='test',
            rpc=dict(
                method='test.get',
                callback='test1234'))
        self.assertContains(response, 'test1234')

    def test_custom(self):
        mixer.blend('rpc.custom')
        response = self.rpc(
            'autojsonrpc',
            rpc=dict(method='custom.get'))
        self.assertContains(response, 'Custom template')

    def test_request(self):
        response = self.rpc(
            'rpc2',
            rpc=dict(
                jsonrpc='2.0',
                method='method3',
                params=['test'],
            ))
        self.assertEqual(response.content, '"POSTtest"')

    def test_private(self):
        response = self.rpc(
            'rpc2',
            rpc=dict(
                jsonrpc='2.0',
                method='__private_method',
            ))
        self.assertContains(response, 'error')

# lint_ignore=C,F0401

########NEW FILE########
__FILENAME__ = test_adrest
""" Prepare a Django project for tests. """
from django.conf import settings

# Configure Django
settings.configure(
    ADMINS=('test', 'test@test.com'),

    ROOT_URLCONF='tests.core.urls',
    DEBUG=True,

    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
            'USER': '',
            'PASSWORD': '',
            'TEST_CHARSET': 'utf8',
        }
    },
    CACHE_BACKEND='locmem://',

    INSTALLED_APPS=(
        'django.contrib.contenttypes',
        'django.contrib.auth',
        'adrest',
        'tests.core', 'tests.main', 'tests.rpc',
    ),

    TEMPLATE_DEBUG=True,
    TEMPLATE_CONTEXT_PROCESSORS = (
        'django.core.context_processors.static',
        'django.core.context_processors.request',
        'django.contrib.auth.context_processors.auth',
    ),

    EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend',

    ADREST_ACCESS_LOG=True,
    ADREST_ALLOW_OPTIONS=True,
    ADREST_MAIL_ERRORS=(500, 400),
    ADREST_AUTO_CREATE_ACCESSKEY=True,
)

# Setup tests
from django.core.management import call_command
call_command('syncdb', interactive=False)

from .core.tests   import *
from .main.tests   import *
from .rpc.tests    import *

# lint_ignore=W0614,W0401,E272

########NEW FILE########
