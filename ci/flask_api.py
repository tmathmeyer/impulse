
import abc
import collections
import flask
import types

VERSION = 'v0'
VERBS = ('get', 'put', 'patch', 'post', 'delete')

_Method = collections.namedtuple('_Method', VERBS)

class ServiceError(Exception):
  def __init__(self, err_code, err_msg=''):
    super(ServiceError, self).__init__('{}: {}'.format(err_code, err_msg))
    self.err_code = err_code
    self.err_msg = err_msg

def make_verb_decorator(verb_name):
  def decorator(sub_path_component):
    def decorator_handler(func):
      func.rest_verb = (verb_name.upper(), sub_path_component)
      return func
    return decorator_handler
  return decorator

METHODS = _Method(**{k: make_verb_decorator(k) for k in VERBS})

def _url_path_join(*args):
  components = ['']
  for arg in args:
    stripped = arg.strip('/')
    if stripped:
      components.append(stripped)
  return '/'.join(components)

class ResourceProvider(object):
  def __init__(self, resource_name, flask_app):
    self._resource = resource_name
    self._version = VERSION
    self.__parse_rest_verbs(flask_app)

  def HAL(self, resource, full=False):
    if full:
      result = resource.get_full_json()
    else:
      result = resource.get_core_json()
    if '_links' not in result:
      result['_links'] = {}

    result['_links'].update({
      'self': {
        'href': '{}/{}'.format(self.get_provider_url_stub(), resource.get_id())
      }
    })
    return result

  def HALList(self, resources):
    return [self.HAL(r) for r in resources]

  def __parse_rest_verbs(self, flask_app):
    path_dict = self._inspect_self_for_method_handlers()
    for path, verb_to_handler in path_dict.items():
      full_router_path = _url_path_join(self.get_provider_url_stub(), path)
      stub_function = self._create_handler(verb_to_handler, full_router_path)
      print(full_router_path)
      flask_router = flask_app.route(
        full_router_path, methods=verb_to_handler.keys())
      flask_router(stub_function)

  def _inspect_self_for_method_handlers(self):
    paths = collections.defaultdict(dict)
    for method in self.__class__.__dict__.values():
      if isinstance(method, types.FunctionType):
        if hasattr(method, 'rest_verb'):
          verb_name, sub_path_component = method.rest_verb
          paths[sub_path_component][verb_name] = method
    return dict(paths)

  def _create_handler(self, verb_to_handler, full_router_path):
    def stub_function(*args, **kwargs):
      handler = verb_to_handler[flask.request.method]
      if flask.request.method.lower() in ('post', 'patch', 'put'):
        assert 'data' not in kwargs
        kwargs['data'] = flask.request.get_json()

      try:
        return flask.jsonify(handler(self, *args, **kwargs)), 200
      except ServiceError as e:
        return e.err_msg, e.err_code

    stub_function.__name__ = ('__api__' + full_router_path.replace('/', '.'))
    return stub_function

  def get_provider_url_stub(self):
    return _url_path_join('api', self._version, self._resource)


class Resource(object, metaclass=abc.ABCMeta):

  @abc.abstractmethod
  def get_full_json(self):
    pass
  
  @abc.abstractmethod
  def get_core_json(self):
    pass

  @abc.abstractmethod
  def get_id(self):
    pass