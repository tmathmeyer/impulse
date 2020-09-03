
import abc
import collections
import flask
import pkgutil
import re
import types
import typing
import uuid


def _url_path_join(*args):
  components = ['']
  for arg in args:
    stripped = arg.strip('/')
    if stripped:
      components.append(stripped)
  return '/'.join(components)



class ServiceError(Exception):
  def __init__(self, err_code, err_msg=''):
    super().__init__('{}: {}'.format(err_code, err_msg))
    self.err_code = err_code
    self.err_msg = err_msg


VERBS = ('get', 'put', 'patch', 'post', 'delete')
__METHOD = collections.namedtuple('__METHOD', VERBS)


class _HAL_BASE(object):
  _HAS_SELF_LINK = True
  def _other_links(self):
    return {}


def __GetResourceBase(name, isHal):
  class __RESOURCE_BASE(_HAL_BASE, metaclass=abc.ABCMeta):
    _resource_name = name
    _isHal = isHal

    def __init__(self):
      self.__id = str(uuid.uuid4())

    def get_id(self):
      return self.__id

    def is_hal(self):
      return self._isHal

    def _get_HAL_id(self):
      return self.get_id()

    def _get_resource_name(self):
      return self._resource_name
    
    @abc.abstractmethod
    def get_core_json(self):
      pass

    @classmethod
    def DefaultProvider(clazz, explorer=False):
      if not hasattr(clazz, '_default_provider'):
        class DefaultResourceProvider(ProvidesResources(clazz)):
          def __init__(self):
            super().__init__(explorer)
            self._instances = {}

          @METHODS.post('/')
          def create(self, inst:clazz):
            self._instances[inst.get_id()] = inst

          @METHODS.get('/')
          def get_all(self) -> [clazz]:
            return list(self._instances.values())

          @METHODS.get('/<instance_id>')
          def get_one(self, instance_id) -> clazz:
            return self._instances.get(instance_id, None)

          @METHODS.put('/<instance_id>')
          def update(self, inst:clazz, instance_id):
            raise ServiceError(500, 'put not implemented')

          @METHODS.patch('/<instance_id>')
          def update(self, inst:clazz, instance_id):
            raise ServiceError(500, 'patch not implemented')

          @METHODS.delete('/<instance_id>')
          def update(self, instance_id):
            raise ServiceError(500, 'delete not implemented')
        clazz._default_provider = DefaultResourceProvider()

      return clazz._default_provider

  return __RESOURCE_BASE


def Resource(name, isHal=True):
  return __GetResourceBase(name, isHal)


def ResourceOf(parent, name):
  rname = parent._resource_name
  class __NESTED_RESOURCE(__GetResourceBase(parent._resource_name)):
    def __init__(self):
      super().__init__()
      finder = r'/'.join([rname, r'(.*)', name])
      owner_id = re.search(finder, str(flask.request.path)).group(1)
      self._owner_id = owner_id

    def _get_HAL_id(self):
      return '/'.join([self._owner_id, name, super()._get_HAL_id()])

  return __NESTED_RESOURCE


def ResourceTypeStruct():
  class __TYPE_STRUCT(_HAL_BASE):
    _HAS_SELF_LINK = False
    def get_core_json(self):
      return self.__dict__
    def _get_HAL_id(self):
      return self.get_id()
  return __TYPE_STRUCT


def make_verb_decorator(verb_name):
  def decorator(sub_path_component):
    def decorator_handler(func):
      func.rest_verb = (verb_name.upper(), sub_path_component)
      return func
    return decorator_handler
  return decorator


METHODS = __METHOD(**{k: make_verb_decorator(k) for k in VERBS})


class _RESOURCE_PROVIDER(object):
  def __init__(self, types, explorer):
    self._explorer = explorer
    self._types = types

  def _get_method_handlers(self):
    paths = collections.defaultdict(dict)
    for method in self.__class__.__dict__.values():
      if isinstance(method, types.FunctionType):
        if hasattr(method, 'rest_verb'):
          verb_name, sub_path_component = method.rest_verb
          paths[sub_path_component][verb_name] = method
    return dict(paths)

  def _get_provider_url_stub(self):
    return _url_path_join('api', self._types[0]._resource_name)


def ProvidesResources(*types):
  assert len(types) > 0
  class __TYPED_PROVIDER(_RESOURCE_PROVIDER):
    def __init__(self, explorer=False):
      super().__init__(types, explorer)
  return __TYPED_PROVIDER


def _REC_HAL(p, some):
  if type(some) is dict:
    return {k: _REC_HAL(p, v) for k, v in some.items()}

  if type(some) is list:
    if len(some) == 0:
      return []
    if isinstance(some[0], _HAL_BASE):
      return _HAL_LIST(p, some)
    return [_REC_HAL(p, v) for v in some]

  if isinstance(some, _HAL_BASE):
    return _HAL(p, some)

  return some


def _HAL(rtype, resource, full=False):
  if full or not resource._isHal:
    exported = resource.__dict__
  else:
    exported = resource.get_core_json()

  result = {}

  for key, value in exported.items():
    if not key.startswith('_'):
      result[key] = _REC_HAL(rtype, value)

  if not resource._isHal:
    return result

  if '_RESOURCE_BASE__id' in result:
    del result['_RESOURCE_BASE__id']

  if resource._HAS_SELF_LINK:
    result['_links'] = {
      'self': {
        'href': '{}/{}'.format(
          rtype._get_provider_url_stub(), resource._get_HAL_id())
      }
    }

  if full:
    if '_links' not in result:
      result['_links'] = {}
    if rtype.__class__.__name__ != '__API_HANDLER':
      result['_links'].update({
        'spec': {
          'href': '{}/_meta/types/{}'.format(
            rtype._get_provider_url_stub(),
            resource.__class__.__name__)
        }
      })
    result['_links'].update(resource._other_links())

  return result

def _HAL_LIST(rtype, resources):
  return [_REC_HAL(rtype, r) for r in resources]


def _CREATE_STUB_HANDLER(provider, verb_to_fn, full_path):
  class InstantiationError(Exception):
      def __init__(self, inst, chain):
        super().__init__()
        if not chain or type(chain) == str:
          self.chain = [inst, chain]
        else:
          self.chain = [inst] + chain.chain
      def __repr__(self):
        return str(self.chain)

  def instantiate(clazz, d):
    def _c(typehints, name, value):
      if name not in typehints:
        return value
      return instantiate(typehints[name], value)
    if type(d) == dict:
      try:
        return clazz(**{
          k:_c(typing.get_type_hints(clazz.__init__), k, v) for k,v in d.items()
        })
      except TypeError as e:
        raise InstantiationError(str(clazz), str(e))
      except InstantiationError as e:
        raise InstantiationError(str(clazz), e)
    return clazz(d)

  def __STUB_FUNCTION(*args, **kwargs):
    method = flask.request.method
    handler_function = verb_to_fn[method]
    handler_typehints = typing.get_type_hints(handler_function)

    if method in ('POST', 'PATCH', 'PUT'):
      assert 'return' not in handler_typehints.keys()
      assert len(handler_typehints) == 1
      type_name, conv_type = list(handler_typehints.items())[0]

      try:
        kwargs[type_name] = instantiate(conv_type, flask.request.get_json())
        kwargs[type_name]._HalURL = 'http:/' + _url_path_join(
          flask.request.host,
          provider._get_provider_url_stub(),
          kwargs[type_name]._get_HAL_id())
      except InstantiationError as e:
        return 'Error - Instantiation: ' + str(e.chain), 500

      try:
        ret = handler_function(provider, *args, **kwargs)
        if ret != None:
          return str(ret), 500
        return flask.jsonify(_HAL(provider, kwargs[type_name])), 200
      except ServiceError as e:
        return e.err_msg, e.err_code

    if method == 'GET':
      try:
        result = handler_function(provider, *args, **kwargs)
        if result == None:
          return 'Error - handler failed to return', 500

        return_type = handler_typehints.get('return', None)
        if (type(return_type) == list):
          return flask.jsonify(_HAL_LIST(provider, result)), 200

        if (return_type == str):
          print(result)
          return result, 200

        return flask.jsonify(_HAL(provider, result, full=True)), 200
      except ServiceError as e:
        return e.err_msg, e.err_code


  __STUB_FUNCTION.__name__ = ('__api__' + full_path.replace('/', '.'))
  return __STUB_FUNCTION


from flask.json import JSONEncoder
class HalJSONEncoder(JSONEncoder):
  def default(self, obj):
    if hasattr(obj, 'SerializeToJSON'):
      return getattr(obj, 'SerializeToJSON')()
    return obj


class _FLASK_WRAPPER(object):
  def __init__(self):
    self.flask_app = flask.Flask(__name__)
    self.flask_app.json_encoder = HalJSONEncoder
    self._explorer = None
    self._logger = None

  def RegisterResourceProvider(self, provider:_RESOURCE_PROVIDER):
    meta_path = _url_path_join(provider._get_provider_url_stub(), '_meta')
    meta_handler = self._CreateMetaAPI(meta_path, provider)
    self._CreateAPI(provider)
    self._CreateAPIExplorer(provider, meta_handler)

  def _CreateAPI(self, provider):
    for path, verb_to_handler in provider._get_method_handlers().items():
      full_path = _url_path_join(provider._get_provider_url_stub(), path)
      router = self.flask_app.route(full_path, methods=verb_to_handler.keys())
      router(_CREATE_STUB_HANDLER(provider, verb_to_handler, full_path))

  def _CreateAPIExplorer(self, provider, meta_handler):
    if not provider._explorer:
      return

    if not self._explorer:
      class _API_LIST(Resource('explore')):
        def __init__(self):
          super().__init__()
          self.api_specs = []

        def get_core_json(self):
          return self.__dict__

      class __API_HANDLER(ProvidesResources(_API_LIST)):
        def __init__(self):
          super().__init__()
          self._list = _API_LIST()

        def add_api(self, API):
          self._list.api_specs.append(API)

        def serve_webpage(self):
          return pkgutil.get_data('impulse.hal', 'frontend.html')

        @METHODS.get('/')
        def get_meta_api_info(self) -> _API_LIST:
          return self._list

      self._explorer = __API_HANDLER()
      self._CreateAPI(self._explorer)
      self.flask_app.route('/api/explore/web')(self._explorer.serve_webpage)
    self._explorer.add_api(meta_handler._api_inst)

  def _CreateMetaAPI(self, meta_path, provider):
    class _API(Resource('__api__')):
      def __init__(self):
        super().__init__()
        self.name = meta_path
        self._HAS_SELF_LINK = False
        self._types = {}
        self._methods = {}
        self.types = []
        self.methods = []
        self._populate_methods_and_types()

      def get_core_json(self):
        return { "href" : self.name }

      def _populate_methods_and_types(self):
        for path, verb2handler in provider._get_method_handlers().items():
          for verb, handler in verb2handler.items():
            method = _API_METHOD(verb, path, handler)
            self._methods[method.get_id()] = method
            self.methods.append(method)

        for clazz in provider._types:
          api_type = _API_TYPE(clazz)
          self._types[clazz.__name__] = api_type
          self.types.append(api_type)


    class _API_TYPE(Resource('__api_type__')):
      def __init__(self, clazz):
        super().__init__()
        self._classname = clazz.__name__
        self.nested = any(
          str(CX.__name__).endswith('__NESTED_RESOURCE')
          for CX in clazz.__bases__)
        typehints = typing.get_type_hints(clazz.__init__)
        self.arguments = {
          name: atype.__name__ for name, atype in typehints.items()
        }

      def _other_links(self):
        return { "api" : { "href": meta_path}}

      def get_id(self):
        return 'types/' + self._classname

      def get_core_json(self):
        return {}


    class _API_METHOD(Resource('__api_method__')):
      def __init__(self, verb, path, func):
        super().__init__()
        self.verb = verb
        self.path = path
        self.types = {}

        typehints = typing.get_type_hints(func)
        if 'return' in typehints:
          self.return_type = self._add_type_get_fmt(typehints['return'])

        if verb == 'POST':
          ret_type = list(typehints.values())[0]
          self.return_type = self._add_type_get_fmt(ret_type)

      def _add_type_get_fmt(self, clazz):
        if type(clazz) is list:
          self.types[clazz[0].__name__] = _API_TYPE(clazz[0])
          return {
            'type': 'List',
            'of': clazz[0].__name__,
          }

        self.types[clazz.__name__] = _API_TYPE(clazz)
        return {
          'type': clazz.__name__
        }

      def _other_links(self):
        return { "api" : { "href": meta_path}}

      def get_core_json(self):
        return { "verb": self.verb, "path": self.path }

      def _get_HAL_id(self):
        return 'methods/' + self.get_id()


    class __API_HANDLER(ProvidesResources(_API, _API_TYPE, _API_METHOD)):
      def __init__(self):
        super().__init__()
        self._api_inst = _API()

      def _get_provider_url_stub(self):
        return meta_path

      @METHODS.get('/')
      def get_meta_api_info(self) -> _API:
        return self._api_inst

      @METHODS.get('/types/<typename>')
      def get_meta_type_info(self, typename) -> _API_TYPE:
        return self._api_inst._types.get(typename, None)

      @METHODS.get('/methods/<method_id>')
      def get_meta_method_info(self, method_id) -> _API_METHOD:
        return self._api_inst._methods.get(method_id, None)

    handler = __API_HANDLER()
    self._CreateAPI(handler)
    return handler

  def Log(self, *args, **kwargs):
    self.Logger().Log(*args, **kwargs)

  def Logger(self):
    return self._logger

  def HostFiles(self, primary, mappings=None):
    mappings = mappings or {}
    def serve(pkg, file):
      try:
        data = pkgutil.get_data(pkg, file)
        if data is None:
          return 'File not found', 404
        return data
      except Exception as e:
        self.Log(str(e))
        return 'File not found', 404
    def root():
      return serve(primary, 'index.html')
    def root_serve(file):
      return serve(primary, file)

    self.flask_app.route('/')(root)
    self.flask_app.route('/<file>')(root_serve)

    for path, pkg in mappings.items():
      serve_file = lambda file: serve(pkg, file)
      self.flask_app.route(f'{path}/<file>')(serve_file)
      self.flask_app.route(package_url)(serve_file)

  def run(self, *args, **kwargs):
    self.flask_app.run(*args, **kwargs)


__flask_instance = None
def GetFlaskInstance():
  global __flask_instance
  if __flask_instance is None:
    __flask_instance = _FLASK_WRAPPER()
    from impulse.hal import logger
    __flask_instance._logger = logger.LogHost.AttachMemoryLogManager(__flask_instance)
  return __flask_instance
