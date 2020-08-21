
import os
import time

import docker
import requests

from impulse.hal import api
from impulse.hal import logger
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
  def __init__(self, name):
    super().__init__()
    self.name = name

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
    super().__init__(name)
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
    super().__init__(name)
    self.paths = {}
    for location in nginxLocations:
      self.paths[location.location] = {
        t:v.value for (t,v) in location._tagsByName.items()}

  def SerializeToJSON(self):
    return {'paths': self.paths}


class HostManager(api.ProvidesResources(Host)):
  def __init__(self, logs):
    super().__init__(explorer=True)
    self._nginx = NginxManagerThread(logs, VAR('NGINX_CONFIG'))
    self._docker = DockerThread(logs, self._nginx)
    self._logs = logs

  @api.METHODS.get('/')
  def get_all_build(self) -> [Host]:
    return self._nginx.Hosts()

  @api.METHODS.get('/<hostname>')
  def byHostname(self, hostname) -> Host:
    build = self._nginx.Host(hostname)
    if build:
      return build
    raise api.ServiceError(404, 'Host not found')


@rpc.RPC
class DockerThread(object):
  def __init__(self, logs, nginx_thread_handle):
    self._client = docker.from_env()
    self._nginx_thread = nginx_thread_handle
    self._logs = logs
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
    self._logs.Log('Container started')
    container = self._client.containers.get(event['id'])
    ports = container.attrs['NetworkSettings']['Ports']
    for boundAs, hostPort in ports.items():
      if boundAs.endswith('/tcp') and hostPort[0]['HostIp'] == '0.0.0.0':
        port = hostPort[0]['HostPort']
        hostname = self._keepTryingNetworkRequest(
          f'http://localhost:{port}/api/impulse/identify', timeout=2, tries=3)
        if hostname == None:
          self._logs.Log(f'Failed to query container on port {port}')
          return
        try:
          server = self._nginx_thread.Host(hostname)
          if server == None:
            self._logs.Log(f'Creating new nginx proxy entry for {hostname}')
            server = self._nginx_thread.CreateProxyHost(hostname, port)
          else:
            self._logs.Log(f'setting port for {hostname} to {port}')
            self._nginx_thread.SetPort(server, port)
        except Exception as e:
          self._logs.Log(e)

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


@rpc.RPC
class NginxManagerThread(object):
  __slots__ = ('_logs', '_config', '_servers', '_nginx_config_location')
  def __init__(self, logs, nginx_config_location):
    self._logs = logs
    self._nginx_config_location = nginx_config_location
    self._config = nginxio.NginXConfig.FromFile(nginx_config_location)
    self._servers = self._parseConfig()

  def _parseConfig(self):
    servers = {}
    for server in self._config.http.servers:
      if len(server.locations) == 0:
        continue
      if not self._validListen(server):
        continue

      server_name = server.NamedProperty('server_name')
      if server.HasProperty('root'):
        servers[server_name] = FileHost(server_name, server.locations)
        continue

      location = server.locations[0]
      if location.HasProperty('proxy_pass'):
        servers[server_name] = ReverseProxy(server_name, location)
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
    self._servers = self._parseConfig()
    os.system('sudo systemctl reload nginx.service')


def main():
  # Create an api app
  app = api.GetFlask()

  # Setup the hosting mechanism
  libhost.SetupContainerService(app, 'services.tedm.io')

  # Setup the logger
  logs = logger.LogHost.AttachMemoryLogManager(app)

  logs.Log('Starting')
  app.RegisterResourceProvider(HostManager(logs))
  app.run(host='0.0.0.0', port=1234)
