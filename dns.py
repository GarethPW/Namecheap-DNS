import time
import requests, xmltodict
import config

API_URL = 'https://dynamicdns.park-your-domain.com/update'


class Host:
  HOSTS = []

  def __init__(self, *, domain, subdomain):
    self.domain = domain
    self.subdomain = subdomain

    self.__class__.HOSTS.append(self)


class Domain:
  DOMAINS = []

  def __init__(self, *, name, password, subdomains):
    self.name = name
    self.password = password

    self.hosts = [
      Host(domain=self, subdomain=subdomain) for subdomain in subdomains
    ]

    self.__class__.DOMAINS.append(self)


class HostUpdater:
  class DnsUpdateError(RuntimeError):
    '''Something prevented the DNS update from succeeding.'''

  class BadResponseError(DnsUpdateError, KeyError):
    '''The response from the API could not be read.'''

  class NotDoneError(DnsUpdateError):
    '''The API did not fulfil the request nor report any errors.'''

  class RichError(DnsUpdateError):
    '''The API returned one or multiple errors.'''

    def __init__(self, *args, **kwargs):
      self.errors = kwargs.pop('errors')
      super().__init__(self, *args, **kwargs)


  def __init__(self, host, **kwargs):
    self.host = host
    self.requests_module = kwargs.pop('requests_module', requests)
    self.api_url = kwargs.pop('api_url', API_URL)
    self.xmltodict_module = kwargs.pop('xmltodict_module', xmltodict)

  def update_dns(self):
    with self.requests_module.get(self.api_url, params={
      'domain': self.host.domain.name,
      'password': self.host.domain.password,
      'host': self.host.subdomain
    }) as req:
      try:
        response = self.xmltodict_module.parse(req.text)
      except Exception:
        raise HostUpdater.BadResponseError()

    try:
      response = response['interface-response']

      if response["ErrCount"] != '0':
        raise HostUpdater.RichError(errors=response["errors"])

      if response['Done'] == 'false':
        raise HostUpdater.NotDoneError()

    except KeyError:
      raise HostUpdater.BadResponseError()


def main():
  while True:
    for host in Host.HOSTS:
      if config.verbose:
        print(f'Updating {host.domain.name}: {host.subdomain}')

      try:
        HostUpdater(host).update_dns()
      except HostUpdater.BadResponseError:
        print(f'[{host.domain.name}: {host.subdomain}] Bad response')
      except HostUpdater.NotDoneError:
        print(f'[{host.domain.name}: {host.subdomain}] Not updated')
      except HostUpdater.RichError as error:
        print(
          f'[{host.domain.name}: {host.subdomain}] Errors:',
          *(f'  {k}: {v}' for k, v in error.errors.items()),
          sep='\n'
        )
      except Exception:
        print(f'[{host.domain.name}: {host.subdomain}] Unknown error')
      else:
        if config.verbose:
          print(f'[{host.domain.name}: {host.subdomain}] Successful!')

      time.sleep(config.interval)


for domain in config.records:
  Domain(
    name=domain['domain'],
    password=domain['password'],
    subdomains=domain['hosts']
  )

if __name__ == '__main__':
  main()
