
import os
import time
import traceback

import docker
import requests

from impulse.hal import api
from impulse.host import libhost
from impulse.rpc import rpc
from nginxweb import nginxio


PROXY_HOST_TEMPLATE = '''
# {server_name}
server_name {server_name};
listen 80;
location / {{
  proxy_pass http://localhost:{port};
  proxy_http_version 1.1;
  proxy_set_header Host $host;
}}
'''


ENVIRON = {
  'NGINX_CONFIG': '/etc/nginx/nginx.conf',
}
ENVIRON.update(os.environ)
def VAR(var):
  return ENVIRON.get(var, None)


class Host(api.Resource('host')):
  def __init__(self, name, status):
    super().__init__()
    self.name = name
    self.status = status

  def get_id(self):
    return self.name

  def get_core_json(self):
    return { }

  def type(self):
    return self.__class__

  def SetPort(self, portno):
    raise TypeError(
      f"Can't set port on {self.name} (type: {self.type().__name__})")


class ReverseProxy(Host):
  def __init__(self, name, nginxLocation):
    super().__init__(name, status='stopped')
    self._locationObj = nginxLocation
    proxy = nginxLocation.NamedProperty('proxy_pass')
    self.host, self.port = proxy.rsplit(':', 1)

  def SerializeToJSON(self):
    return {'host': self.host, 'port': self.port}

  def SetPort(self, portno):
    self.port = portno
    proxy_pass = ':'.join([self.host, self.port])
    self._locationObj.SetNamedProperty('proxy_pass', proxy_pass)


class FileHost(Host):
  def __init__(self, name, nginxLocations):
    super().__init__(name, status='filehost')
    self.paths = {}
    for location in nginxLocations:
      self.paths[location.location] = {
        t:v.value for (t,v) in location._tagsByName.items()}

  def SerializeToJSON(self):
    return {'paths': self.paths}


class HostManager(api.ProvidesResources(Host)):
  def __init__(self):
    super().__init__(explorer=True)
    logger = api.GetFlaskInstance().Logger()
    self._nginx = NginxManagerThread(logger, VAR('NGINX_CONFIG'))
    self._docker = DockerThread(logger, self._nginx)

  @api.METHODS.get('/all')
  def get_all_build(self) -> [Host]:
    return self._nginx.Hosts()

  @api.METHODS.get('/alive')
  def get_alive_builds(self) -> [Host]:
    return [
      h for h in self._nginx.Hosts() if h.status in ('running', 'filehost')
    ]

  @api.METHODS.get('/<hostname>')
  def byHostname(self, hostname) -> Host:
    build = self._nginx.Host(hostname)
    if build:
      return build
    raise api.ServiceError(404, 'Host not found')


class DockerContainer(object):
  __slots__ = ('_hostname', '_wrapped', '_port')
  def __init__(self, container):
    self._port = None
    self._hostname = None
    self._wrapped = container
    self._setup()

  def ID(self):
    return self._wrapped.id

  def Host(self):
    return self._hostname

  def _setup(self):
    ports = self._wrapped.attrs['NetworkSettings']['Ports']
    for boundAs, hostPort in ports.items():
      if boundAs.endswith('/tcp') and hostPort[0]['HostIp'] == '0.0.0.0':
        port = hostPort[0]['HostPort']
        self._hostname = self._keepTryingNetworkRequest(
          f'http://localhost:{port}/api/impulse/identify', timeout=2, tries=3)
        if self._hostname is not None:
          self._port = port
          break

    if self._hostname is None:
      raise Warning(f'This host ({self.ID()}) is not proxyable')

  def _keepTryingNetworkRequest(self, url, timeout=5, tries=1):
    try:
      response = requests.get(url)
      if response.status_code != 200:
        return None
      return response.content.decode('utf-8')
    except:
      time.sleep(timeout)
      if tries >= 1:
        return self._keepTryingNetworkRequest(url, timeout, tries-1)
      return None

  def CommunicateNginx(self, nginx_thread_handle):
    if self._port is None or self._hostname is None:
      raise ValueError('DockerContainer was never initialized')

    server = nginx_thread_handle.Host(self._hostname)
    if server == None:
      server = self._nginx_thread.CreateProxyHost(self._hostname, self._port)
    else:
      nginx_thread_handle.SetPort(server, self._port)


@rpc.RPC
class DockerThread(object):
  __slots__ = ('_client', '_nginx_thread', '_logs',
               '_containers_by_id', '_containers_by_host')
  def __init__(self, logs, nginx_thread_handle):
    self._client = docker.from_env()
    self._nginx_thread = nginx_thread_handle
    self._logs = logs
    self._containers_by_id = {}
    self._containers_by_host = {}
    self.OnStart()

  def ContainerExists(self, hostname):
    return hostname in self._containers_by_host

  def _addContainer(self, external_container):
    try:
      container = DockerContainer(external_container)
      container.CommunicateNginx(self._nginx_thread)
      if container.ID() in self._containers_by_id:
        raise ValueError('Duplicate container ID.')
      if container.Host() in self._containers_by_host:
        raise ValueError('Duplicate container Hostname.')
      self._containers_by_id[container.ID()] = container
      self._containers_by_host[container.Host()] = container
      self._nginx_thread.NotifyContainerHostAlive(container.Host())
    except Exception as e:
      self._logs.Log(traceback.format_exc())

  def _removeContainer(self, external_container):
    try:
      container = self._containers_by_id.get(external_container.id, None)
      if container is None:
        self._logs.Log(f'Removing unhosted container: {external_container.id}')
      else:
        self._containers_by_id.pop(container.ID())
        self._containers_by_host.pop(container.Host())
        self._nginx_thread.NotifyContainerHostDead(container.Host())
    except Exception as e:
      self._logs.Log(traceback.format_exc())

  def OnStart(self):
    for container in self._client.containers.list():
      self._addContainer(container)
    self._logs.Log(
      f'detected containers on start: {list(self._containers_by_host.keys())}')
    self.Listen()

  def Listen(self):
    for event in self._client.events(decode=True):
      if event['Type'] == 'container':
        getattr(self, event['status'], self._unhandled)(event)

  # Docker event default handler
  def _unhandled(self, event):
    self._logs.Log(event)

  # Docker event start handler
  def start(self, event):
    self._logs.Log(f'container {event["id"]} started')
    self._addContainer(self._client.containers.get(event['id']))

  # Docker event stop handler
  def stop(self, event):
    self._logs.Log(f'container {event["id"]} stopped')
    self._removeContainer(self._client.containers.get(event['id']))

  # Docker event die handler
  def die(self, event):
    self._logs.Log(f'container {event["id"]} died')
    self._removeContainer(self._client.containers.get(event['id']))

  # Docker event kill handler
  def kill(self, event):
    pass

  # Docker event attach handler
  def attach(self, event):
    pass

  # Docker event create handler
  def create(self, event):
    pass

  # Docker event destroy handler
  def destroy(self, event):
    pass


@rpc.RPC
class NginxManagerThread(object):
  __slots__ = ('_logs', '_config', '_servers', '_nginx_config_location')
  def __init__(self, logs, nginx_config_location):
    self._logs = logs
    self._nginx_config_location = nginx_config_location
    self._config = nginxio.NginXConfig.FromFile(nginx_config_location)
    self._servers = self._parseConfig()

  def _parseConfig(self, old_config=None):
    servers = {}
    for server in self._config.http.servers:
      if len(server.locations) == 0:
        continue
      if not self._validListen(server):
        continue

      server_name = server.NamedProperty('server_name')
      location = server.locations[0]
      if location.HasProperty('proxy_pass'):
        servers[server_name] = ReverseProxy(server_name, location)
        if old_config and server_name in old_config:
          servers[server_name] = old_config[server_name].status
        continue

      if server.HasProperty('root'):
        servers[server_name] = FileHost(server_name, server.locations)
        continue
    return servers

  def _validListen(self, server):
    listen = server.NamedProperty('listen')
    if listen == '443 ssl':
      return True
    if listen == '80':
      return True
    return False

  def Hosts(self):
    return self._servers.values()

  def Host(self, hostname):
    return self._servers.get(hostname, None)

  def CreateProxyHost(self, hostname, port):
    content = PROXY_HOST_TEMPLATE.format(server_name=hostname, port=port)
    server = nginxio.NginXServer.FromString(content)
    self._config.http.servers.append(server)
    self.Synchronize()
    return server

  def SetPort(self, server, port):
    server = self._servers.get(server.name)
    server.SetPort(port)
    self.Synchronize()

  def Synchronize(self):
    self._logs.Log('Synchronizing nginx config')
    self._config.WriteToFile(self._nginx_config_location)
    self._servers = self._parseConfig(self._servers)
    os.system('systemctl reload nginx.service')

  def NotifyContainerHostDead(self, host):
    self._logs.Log(f'setting container {host} to stopped')
    self._servers.get(host).status = 'stopped'
  
  def NotifyContainerHostAlive(self, host):
    self._logs.Log(f'setting container {host} to running')
    self._servers.get(host).status = 'running'



def main():
  # Setup the hosting mechanism
  libhost.SetupContainerService('hosts.tedm.io')

  app = api.GetFlaskInstance()
  app.HostFiles('impulse.host.frontend')
  app.Log('Starting')

  app.RegisterResourceProvider(HostManager())
  app.run(host='0.0.0.0', port=1234)
