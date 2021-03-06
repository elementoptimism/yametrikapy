#!/usr/bin/env python
# -*- coding: UTF-8 -*-

#-------------------------
# Name:        core
# Purpose:
#
# Author:      Sergey Pikhovkin (s@pikhovkin.ru)
#
# Created:     12.05.2011
# Copyright:   &#169; Sergey Pikhovkin 2011
# Licence:     MIT
#-------------------------

from simplejson import loads, dumps
import datetime


def _json_format(obj):
  if isinstance(obj, (datetime.datetime, datetime.date)):
      return obj.isoformat()
  return None

dumps = lambda data: dumps(data, use_decimal=True, default=_json_format)


from client import APIClient


class BaseClass(object):
  pass


class ClientError(Exception):
  pass


class BadRequestError(ClientError):
  """ 400 http-status """
  pass


class UnauthorizedError(ClientError):
  """ 401 http-status """
  pass


class ForbiddenError(ClientError):
  """ 403 http-status """
  pass


class MethodNotAllowedError(ClientError):
  """ 405 http-status """
  pass


class APIException(Exception):
  def __init__(self, msg, code=None):
      self.message = msg
      self.code = code

  def __repr__(self):
      return '<APIException: %s, code %s>' % (self.message.encode('utf-8'), self.code)

  __str__ = __repr__


class Dict2obj(object):
  def __init__(self, dct):
      self.__dict__ = dct


class JSON2Obj(object):
  def __init__(self, page):
      self.__dict__ = loads(page)


class BaseMetrika(object):
  OAUTH_TOKEN = 'https://oauth.yandex.ru/token'
  _UserAgent = 'yametrikapy'

  def __init__(self, client_id, username='', password='', token='', code=''):
      self._ClientId = client_id
      self._Username = username
      self._Password = password
      self._Token = token
      self._Code = code

      self._client = APIClient()
      self._client.UserAgent = self._UserAgent
      self._data = ''

  @property
  def UserAgent(self):
      return self._UserAgent

  @UserAgent.setter
  def UserAgent(self, user_agent):
      self._UserAgent = user_agent

  def _GetResponseObject(f):
      """
      """
      def wrapper(self):
          # lets make dict from json
          obj = loads(self._data)
          if 'errors' in obj:
              if len(obj['errors']) == 1:
                  if isinstance(self, MetrikaV1):
                      raise APIException(obj['errors'][0]['error_type'], obj['errors'][0].get('message') or obj['code'])
                  raise APIException(obj['errors'][0]['text'], obj['errors'][0]['code'])
              raise APIException('\n'.join([error['text'] for error in obj['errors']]))
          if 'error' in obj:
              if obj['error'] == 'invalid_client':
                  raise UnauthorizedError
              raise APIException(obj['error'], obj['code'])

          return f(self, obj)
      return wrapper

  @_GetResponseObject
  def _AuthorizeHandle(self, obj):
      # obj - dict from yandex json response
      if 'access_token' in obj:
          self._Token = obj['access_token']

  def _Authorize(self):
      params = {
          'grant_type': 'authorization_code' if self._Code else 'password',
          'client_id': self._ClientId
      }
      if self._Code:
          params['code'] = self._Code
      else:
          params['username'] = self._Username
          params['password'] = self._Password
      self._data = self._client.request('POST', self.OAUTH_TOKEN, params=params)
      self._AuthorizeHandle()

  def _Auth(f):
      def wrapper(self, *args, **kwargs):
          if not self._Token:
              self._Authorize()
          return f(self, *args, **kwargs)
      return wrapper

  def _GetHeaders(self):
      header = {
          'User-Agent': self._UserAgent,
          'Accept': 'application/x-yametrika+json',
          'Accept-Language': 'ru,en-us;q=0.7,en;q=0.3',
          'Accept-Encoding': 'gzip,deflate',
          'Accept-Charset': 'utf-8;q=0.7,*;q=0.7',
          'Keep-Alive': '300',
          'Connection': 'keep-alive',
          'Authorization': 'OAuth %s' % self._Token
      }
      return header

  @_Auth
  def _GetData(self, method, uri, params={}):
      headers = self._GetHeaders()
      self._data = self._client.request(method, uri, params=params, headers=headers)
      if self._client.Status == 400:
          raise BadRequestError('%d %s' % (self._client.Status, 'Check your request'))
      if self._client.Status == 401:
          raise UnauthorizedError('%d: %s' % (self._client.Status, 'Check your token'))
      if self._client.Status == 403:
          raise ForbiddenError('%d: %s' % (self._client.Status, 'Check your access rigths to object'))
      if self._client.Status == 405:
          allowed = self._client.GetHeader('Allowed')
          raise MethodNotAllowedError('%d: %s\nUse %s' % (self._client.Status, 'Method not allowed', allowed))
      return self._ResponseHandle()

  _GetResponseObject = staticmethod(_GetResponseObject)


class MetrikaV1(BaseMetrika):
  """
  Class for the V1 version of Yandex Metrika
  """
  HOST = 'https://beta.api-metrika.yandex.ru'

  def __init__(self, token):
      super(MetrikaV1, self).__init__('', token=token)

  def getDS(self, **params):
      return self._GetData('GET', self.HOST + '/stat/v1/data', params)

  def GetCounterList(self, **params):
      """
      https://tech.yandex.ru/metrika/doc/beta/management/counters/counters-docpage/
      """
      data = self._GetData('GET', self.HOST + '/management/v1/counters', params)
      if data['rows'] > 0:
          return data['counters']

      return []

  def GetCounter(self, counter_id, field=''):
      """
      https://tech.yandex.ru/metrika/doc/beta/management/counters/counter-docpage/

      field - Один или несколько дополнительных параметров возвращаемого объекта.
      Названия дополнительных параметров указываются в любом порядке через запятую, без пробелов.
      Например: field=goals,mirrors,grants,filters,operation
      """
      data = self._GetData('GET', self.HOST + '/management/v1/counter/%d' % counter_id, {'field': field})
      return data['counter']


  @BaseMetrika._GetResponseObject
  def _ResponseHandle(self, dct):
      return dct


class Metrika(BaseMetrika):
  """
  Class for the API of Yandex Metrika
  """
  HOST = 'https://api-metrika.yandex.ru/'

  _COUNTERS = 'counters'
  _COUNTER = 'counter/%d'
  _GOALS = _COUNTER + '/goals'
  _GOAL = _COUNTER + '/goal/%d'
  _FILTERS = _COUNTER + '/filters'
  _FILTER = _COUNTER + '/filter/%d'
  _OPERATIONS = _COUNTER + '/operations'
  _OPERATION = _COUNTER + '/operation/%d'
  _GRANTS = _COUNTER + '/grants'
  _GRANT = _COUNTER + '/grant/%s'
  _DELEGATES = 'delegates'
  _DELEGATE = 'delegate/%s'
  _ACCOUNTS = 'accounts'
  _ACCOUNT = 'account/%s'

  _STAT = 'stat'

  _STAT_TRAFFIC = _STAT + '/traffic'
  _STAT_TRAFFIC_SUMMARY = _STAT_TRAFFIC + '/summary'
  _STAT_TRAFFIC_DEEPNESS = _STAT_TRAFFIC + '/deepness'
  _STAT_TRAFFIC_HOURLY = _STAT_TRAFFIC + '/hourly'
  _STAT_TRAFFIC_LOAD = _STAT_TRAFFIC + '/load'

  _STAT_SOURCES = _STAT + '/sources'
  _STAT_SOURCES_SUMMARY = _STAT_SOURCES + '/summary'
  _STAT_SOURCES_SITES = _STAT_SOURCES + '/sites'
  _STAT_SOURCES_SEARCH_ENGINES = _STAT_SOURCES + '/search_engines'
  _STAT_SOURCES_PHRASES = _STAT_SOURCES + '/phrases'
  _STAT_SOURCES_MARKETING = _STAT_SOURCES + '/marketing'
  _STAT_SOURCES_DIRECT = _STAT_SOURCES + '/direct'
  _STAT_SOURCES_DIRECT_SUMMARY = _STAT_SOURCES_DIRECT + '/summary'
  _STAT_SOURCES_DIRECT_PLATFORMS = _STAT_SOURCES_DIRECT + '/platforms'
  _STAT_SOURCES_DIRECT_REGIONS = _STAT_SOURCES_DIRECT + '/regions'
  _STAT_SOURCES_TAGS = _STAT_SOURCES + '/tags'

  _STAT_CONTENT = _STAT + '/content'
  _STAT_CONTENT_POPULAR = _STAT_CONTENT + '/popular'
  _STAT_CONTENT_ENTRANCE = _STAT_CONTENT + '/entrance'
  _STAT_CONTENT_EXIT = _STAT_CONTENT + '/exit'
  _STAT_CONTENT_TITLES = _STAT_CONTENT + '/titles'
  _STAT_CONTENT_URL_PARAM = _STAT_CONTENT + '/url_param'

  _STAT_GEO = _STAT + '/geo'

  _STAT_DEMOGRAPHY = _STAT + '/demography'
  _STAT_DEMOGRAPHY_AGE_GENDER = _STAT_DEMOGRAPHY + '/age_gender'
  _STAT_DEMOGRAPHY_STRUCTURE = _STAT_DEMOGRAPHY + '/structure'

  _STAT_TECH = _STAT + '/tech'
  _STAT_TECH_BROWSERS = _STAT_TECH + '/browsers'
  _STAT_TECH_OS = _STAT_TECH + '/os'
  _STAT_TECH_DISPLAY = _STAT_TECH + '/display'
  _STAT_TECH_MOBILE = _STAT_TECH + '/mobile'
  _STAT_TECH_FLASH = _STAT_TECH + '/flash'
  _STAT_TECH_SILVERLIGHT = _STAT_TECH + '/silverlight'
  _STAT_TECH_DOTNET = _STAT_TECH + '/dotnet'
  _STAT_TECH_JAVA = _STAT_TECH + '/java'
  _STAT_TECH_COOKIES = _STAT_TECH + '/cookies'
  _STAT_TECH_JAVASCRIPT = _STAT_TECH + '/javascript'

  @BaseMetrika._GetResponseObject
  def _ResponseHandle(self, dct):
      # lets make object from yandex response dict
      obj = Dict2obj(dct)
      return obj

  def _GetURI(self, methodname, params=''):
      uri = '%s%s.json' % (self.HOST, methodname)
      if params:
          uri += '?%s' % params
      return uri

  def GetData(self):
      return self._data

  # Counters

  def GetCounterList(self, type='', permission='', ulogin='', field=''):
      """
      Returns a list of existing counters available to the user.
      """
      uri = self._GetURI(self._COUNTERS)
      params = {
          'type': type,
          'permission': permission,
          'ulogin': ulogin,
          'field': field
      }
      obj = self._GetData('GET', uri, params)

      result = BaseClass()
      result.counters = []
      result.counters.extend(obj.counters)

      while hasattr(obj, 'links') and 'next' in obj.links:
          obj = self._GetData('GET', obj.links['next'])
          result.counters.extend(obj.counters)

      return result

  def GetCounter(self, id, field=''):
      """
      Returns information about the specified counter.
      """
      uri = self._GetURI(self._COUNTER % id)
      params = {'field': field}
      return self._GetData('GET', uri, params)

  def AddCounter(self, name, site, **kwargs):
      """
      Creates a counter with the specified parameters.
      """
      uri = self._GetURI(self._COUNTERS)
      kwargs['name'] = name
      kwargs['site'] = site
      params = {'counter': kwargs}
      return self._GetData('POST', uri, dumps(params))

  def EditCounter(self, id, **kwargs):
      """
      Modifies the data for the specified counter.
      """
      uri = self._GetURI(self._COUNTER % id)
      params = {'counter': kwargs}
      return self._GetData('PUT', uri, dumps(params))

  def DeleteCounter(self, id):
      """
      Removes the specified counter.
      """
      uri = self._GetURI(self._COUNTER % id)
      return self._GetData('DELETE', uri)

  # Goals

  def GetCounterGoalList(self, id):
      """
      Returns information about the goals of counter.
      """
      uri = self._GetURI(self._GOALS % id)
      return self._GetData('GET', uri)

  def GetCounterGoal(self, id, goal_id):
      """
      Returns information about the specified goal of counter.
      """
      uri = self._GetURI(self._GOAL % (id, goal_id))
      return self._GetData('GET', uri)

  def AddCounterGoal(self, id, name, type, depth, conditions=[], flag=''):
      """
      Creates the goal of counter.
      """
      uri = self._GetURI(self._GOALS % id)
      params = {
          'goal': {
              'name': name,
              'type': type,
              'depth': depth,
              'flag': flag,
              'conditions': conditions
          }
      }
      return self._GetData('POST', uri, dumps(params))

  def EditCounterGoal(self, id, goal_id, name, type, depth, conditions=[],
      flag=''):
      """
      Changes the settings specified goal of counter.
      """
      uri = self._GetURI(self._GOAL % (id, goal_id))
      params = {
          'goal': {
              'name': name,
              'type': type,
              'depth': depth,
              'conditions': conditions,
              'flag': flag
          }
      }
      return self._GetData('PUT', uri, dumps(params))

  def DeleteCounterGoal(self, id, goal_id):
      """
      Removes the goal of counter.
      """
      uri = self._GetURI(self._GOAL % (id, goal_id))
      return self._GetData('DELETE', uri)

  # Filters

  def GetCounterFilterList(self, id):
      """
      Returns information about the filter of counter.
      """
      uri = self._GetURI(self._FILTERS % id)
      return self._GetData('GET', uri)

  def GetCounterFilter(self, id, filter_id):
      """
      Returns information about the specified filter of counter.
      """
      uri = self._GetURI(self._FILTER % (id, filter_id))
      return self._GetData('GET', uri)

  def AddCounterFilter(self, id, action, attr, type, value, status):
      """
      Creates a filter of counter.
      """
      uri = self._GetURI(self._FILTERS % id)
      params = {
          'filter': {
              'action': action,
              'attr': attr,
              'type': type,
              'value': value,
              'status': status
          }
      }
      return self._GetData('POST', uri, dumps(params))

  def EditCounterFilter(self, id, filter_id, action, attr, type, value,
      status):
      """
      Modifies the configuration of the specified filter of counter.
      """
      uri = self._GetURI(self._FILTER % (id, filter_id))
      params = {
          'filter': {
              'action': action,
              'attr': attr,
              'type': type,
              'value': value,
              'status': status
          }
      }
      return self._GetData('PUT', uri, dumps(params))

  def DeleteCounterFilter(self, id, filter_id):
      """
      Removes the filter of counter.
      """
      uri = self._GetURI(self._FILTER % (id, filter_id))
      return self._GetData('DELETE', uri)

  # Operations

  def GetCounterOperationList(self, id):
      """
      Returns information about the operations of counter.
      """
      uri = self._GetURI(self._OPERATIONS % id)
      return self._GetData('GET', uri)

  def GetCounterOperation(self, id, operation_id):
      """
      Returns information about the specified operation of counter.
      """
      uri = self._GetURI(self._OPERATION % (id, operation_id))
      return self._GetData('GET', uri)

  def AddCounterOperation(self, id, action, attr, value, status):
      """
      Создает операцию для счетчика.
      """
      uri = self._GetURI(self._OPERATIONS % id)
      params = {
          'operation': {
              'action': action,
              'attr': attr,
              'value': value,
              'status': status
          }
      }
      return self._GetData('POST', uri, dumps(params))

  def EditCounterOperation(self, id, operation_id, action, attr, value,
      status):
      """
      Modifies the configuration of the specified operation of counter.
      """
      uri = self._GetURI(self._OPERATION % (id, operation_id))
      params = {
          'operation': {
              'action': action,
              'attr': attr,
              'value': value,
              'status': status
          }
      }
      return self._GetData('PUT', uri, dumps(params))

  def DeleteCounterOperation(self, id, operation_id):
      """
      Removes an operation of counter.
      """
      uri = self._GetURI(self._OPERATION % (id, operation_id))
      return self._GetData('DELETE', uri)

  # Grants

  def GetCounterGrantList(self, id):
      """
      Returns information about the permissions to manage the counter and
      statistics.
      """
      uri = self._GetURI(self._GRANTS % id)
      return self._GetData('GET', uri)

  def GetCounterGrant(self, id, user_login):
      """
      Returns information about a specific permit to control the counter and
      statistics.
      """
      uri = self._GetURI(self._GRANT % (id, user_login))
      return self._GetData('GET', uri)

  def AddCounterGrant(self, id, user_login, perm):
      """
      Creates a permission to manage the counter and statistics.
      """
      uri = self._GetURI(self._GRANTS % id)
      params = {
          'grant': {
              'perm': perm,
              'user_login': user_login
          }
      }
      return self._GetData('POST', uri, dumps(params))

  def EditCounterGrant(self, id, user_login, perm):
      """
      Modifies the configuration of the specified permission to manage
      the counter and statistics.
      """
      uri = self._GetURI(self._GRANT % (id, user_login))
      params = {
          'grant': {
              'perm': perm
          }
      }
      return self._GetData('PUT', uri, dumps(params))

  def DeleteCounterGrant(self, id, user_login):
      """
      Removes the permissions to manage the counter and statistics.
      """
      uri = self._GetURI(self._GRANT % (id, user_login))
      return self._GetData('DELETE', uri)

  # Delegates

  def GetDelegates(self):
      """
      Returns list of delegates who have been granted full access to
      the account of the current user.
      """
      uri = self._GetURI(self._DELEGATES)
      return self._GetData('GET', uri)

  def AddDelegate(self, user_login):
      """
      Modifies the list of delegates for the current user account.
      """
      uri = self._GetURI(self._DELEGATES)
      params = {
          'delegate': {
              'user_login': user_login
          }
      }
      return self._GetData('POST', uri, dumps(params))

  def EditDelegates(self, delegates):
      """
      Adds a user login in the list of delegates for the current account.
      """
      uri = self._GetURI(self._DELEGATES)
      params = {'delegates': delegates}
      return self._GetData('PUT', uri, dumps(params))

  def DeleteDelegate(self, user_login):
      """
      Removes the user's login from the list of delegates for
      the current account.
      """
      uri = self._GetURI(self._DELEGATE % user_login)
      return self._GetData('DELETE', uri)

  # Accounts

  def GetAccounts(self):
      """
      Returns a list of accounts, the delegate of which is the current user.
      """
      uri = self._GetURI(self._ACCOUNTS)
      return self._GetData('GET', uri)

  def EditAccounts(self, accounts):
      """
      Modifies the list of accounts whose delegate is the current user.
      Account list is updated in accordance with the list of usernames
      input structure.
      ! If the input structure does not specify a login user delegated by
      the current user, full access to the this user account will be
      revoked.
      ! If the input structure of the specified user's login, not included in
      the current list of accounts, full access to the account of this user
      NOT available.
      """
      uri = self._GetURI(self._ACCOUNTS)
      params = {'accounts': accounts}
      return self._GetData('PUT', uri, dumps(params))

  def DeleteAccount(self, user_login):
      """
      Removes the user's login from the list of accounts, which are delegate
      is the current user.
      ! When you delete a user name from the list of accounts full access to
      your account will be revoked.
      """
      uri = self._GetURI(self._ACCOUNT % user_login)
      return self._GetData('DELETE', uri)

  # Statistics

  def GetStatTrafficSummary(self, id, goal_id=None, date1='', date2='',
      group='day', per_page=100, next=''):
      """
      Returns data about traffic of site.
      """
      params = next[next.find('?') + 1:] if next else ''
      uri = self._GetURI(self._STAT_TRAFFIC_SUMMARY, params)
      params = {}
      if not next:
          params = {
              'id': id,
              'date1': date1,
              'date2': date2,
              'group': group,
              'per_page': str(per_page)
          }
          if not goal_id is None:
              params['goal_id'] = str(goal_id)
      return self._GetData('GET', uri, params)

  def GetStatTrafficDeepness(self, id, goal_id=None, date1='', date2=''):
      """
      Returns data on the number of pages viewed and time visitors
      spent on the site.
      """
      uri = self._GetURI(self._STAT_TRAFFIC_DEEPNESS)
      params = {
          'id': id,
          'date1': date1,
          'date2': date2
      }
      if not goal_id is None:
          params['goal_id'] = goal_id
      return self._GetData('GET', uri, params)

  def GetStatTrafficHourly(self, id, goal_id=None, date1='', date2=''):
      """
      Returns data on the distribution of traffic on the site by time of day,
      for each hourly of period.
      """
      uri = self._GetURI(self._STAT_TRAFFIC_HOURLY)
      params = {
          'id': id,
          'date1': date1,
          'date2': date2
      }
      if not goal_id is None:
          params['goal_id'] = goal_id
      return self._GetData('GET', uri, params)

  def GetStatTrafficLoad(self, id, date1='', date2='', group='day',
      per_page=100, next=''):
      """
      Returns the maximum number of requests (alarms counter) per second and
      the maximum number of online visitors each day selected time period.
      """
      params = next[next.find('?') + 1:] if next else ''
      uri = self._GetURI(self._STAT_TRAFFIC_LOAD, params)
      params = {}
      if not next:
          params = {
              'id': id,
              'date1': date1,
              'date2': date2,
              'group': group,
              'per_page': per_page
          }
      return self._GetData('GET', uri, params)

  def GetStatSourcesSummary(self, id, goal_id=None, date1='', date2='',
      sort='visits', reverse=1):
      """
      Returns the conversion data from all sources on the site,
      where installed the specified counter.
      """
      uri = self._GetURI(self._STAT_SOURCES_SUMMARY)
      params = {
          'id': id,
          'date1': date1,
          'date2': date2,
          'sort': sort,
          'reverse': reverse
      }
      if not goal_id is None:
          params['goal_id'] = goal_id
      return self._GetData('GET', uri, params)

  def GetStatSourcesSites(self, id, goal_id=None, date1='', date2='',
      table_mode='plain', per_page=100, sort='visits', reverse=1, next=''):
      """
      Returns the conversion data from other sites on the web site,
      where installed the specified counter.
      """
      params = next[next.find('?') + 1:] if next else ''
      uri = self._GetURI(self._STAT_SOURCES_SITES, params)
      params = {}
      if not next:
          params = {
              'id': id,
              'date1': date1,
              'date2': date2,
              'table_mode': table_mode,
              'per_page': per_page,
              'sort': sort,
              'reverse': reverse
          }
          if not goal_id is None:
              params['goal_id'] = goal_id
      return self._GetData('GET', uri, params)

  def GetStatSourcesSearchEngines(self, id, goal_id=None, date1='', date2='',
      table_mode='plain', per_page=100, sort='visits', reverse=1, next=''):
      """
      Returns the conversion data from the search engine's website,
      where installed the specified counter.
      """
      params = next[next.find('?') + 1:] if next else ''
      uri = self._GetURI(self._STAT_SOURCES_SEARCH_ENGINES, params)
      params = {}
      if not next:
          params = {
              'id': id,
              'date1': date1,
              'date2': date2,
              'table_mode': table_mode,
              'per_page': per_page,
              'sort': sort,
              'reverse': reverse
          }
          if not goal_id is None:
              params['goal_id'] = goal_id
      return self._GetData('GET', uri, params)

  def GetStatSourcesPhrases(self, counter_id, goal_id=None, se_id=None, date1='',
      date2='', per_page=100, sort='visits', reverse=1, next=''):
      """
      Returns information about the search phrases that visitors find
      link to the site with installed a counter.
      """
      params = next[next.find('?') + 1:] if next else ''
      uri = self._GetURI(self._STAT_SOURCES_PHRASES, params)
      params = {}
      if not next:
          params = {
              'id': counter_id,
              'date1': date1,
              'date2': date2,
              'sort': sort,
              'reverse': reverse,
              'per_page': per_page
          }
          if not goal_id is None:
              params['goal_id'] = goal_id
          if not se_id is None:
              params['se_id'] = se_id
      return self._GetData('GET', uri, params)

  def GetStatSourcesMarketing(self, id, goal_id=None, date1='', date2='',
      table_mode='plain', per_page=100, sort='visits', reverse=1, next=''):
      """
      Returns the conversion data from the advertising system on the site,
      where installed the specified counter.
      """
      params = next[next.find('?') + 1:] if next else ''
      uri = self._GetURI(self._STAT_SOURCES_MARKETING, params)
      params = {}
      if not next:
          params = {
              'id': id,
              'date1': date1,
              'date2': date2,
              'table_mode': table_mode,
              'per_page': per_page,
              'sort': sort,
              'reverse': reverse
          }
          if not goal_id is None:
              params['goal_id'] = goal_id
      return self._GetData('GET', uri, params)

  def GetStatSourcesDirectSummary(self, id, goal_id=None, date1='', date2='',
      table_mode='plain', per_page=100, sort='visits', reverse=1, next=''):
      """
      Returns record of advertising campaigns Yandex.Direct, ad which
      visitors to a site.
      """
      params = next[next.find('?') + 1:] if next else ''
      uri = self._GetURI(self._STAT_SOURCES_DIRECT_SUMMARY, params)
      params = {}
      if not next:
          params = {
              'id': id,
              'date1': date1,
              'date2': date2,
              'table_mode': table_mode,
              'per_page': per_page,
              'sort': sort,
              'reverse': reverse
          }
          if not goal_id is None:
              params['goal_id'] = goal_id
      return self._GetData('GET', uri, params)

  def GetStatSourcesDirectPlatforms(self, id, goal_id=None, date1='', date2='',
      per_page=100, sort='visits', reverse=1, next=''):
      """
      Returns a report on areas with which the transition through
      advertisements on the advertiser's site.
      """
      params = next[next.find('?') + 1:] if next else ''
      uri = self._GetURI(self._STAT_SOURCES_DIRECT_PLATFORMS, params)
      params = {}
      if not next:
          params = {
              'id': id,
              'date1': date1,
              'date2': date2,
              'per_page': per_page,
              'sort': sort,
              'reverse': reverse
          }
          if not goal_id is None:
              params['goal_id'] = goal_id
      return self._GetData('GET', uri, params)

  def GetStatSourcesDirectRegions(self, id, goal_id=None, date1='', date2='',
      table_mode='plain', per_page=100, sort='visits', reverse=1, next=''):
      """
      Returns information about membership of visitors who clicked on the site
      through advertisements to a particular geographical region.
      """
      params = next[next.find('?') + 1:] if next else ''
      uri = self._GetURI(self._STAT_SOURCES_DIRECT_REGIONS, params)
      params = {}
      if not next:
          params = {
              'id': id,
              'date1': date1,
              'date2': date2,
              'table_mode': table_mode,
              'per_page': per_page,
              'sort': sort,
              'reverse': reverse
          }
          if not goal_id is None:
              params['goal_id'] = goal_id
      return self._GetData('GET', uri, params)

  def GetStatSourcesTags(self, id, goal_id=None, date1='', date2='',
      table_mode='plain', per_page=100, sort='visits', reverse=1, next=''):
      """
      Returns information about visits to a site on the links, which contain
      any of the four most frequently used tags: utm, openstat, from, glcid.
      """
      params = next[next.find('?') + 1:] if next else ''
      uri = self._GetURI(self._STAT_SOURCES_TAGS, params)
      params = {}
      if not next:
          params = {
              'id': id,
              'date1': date1,
              'date2': date2,
              'table_mode': table_mode,
              'per_page': per_page,
              'sort': sort,
              'reverse': reverse
          }
          if not goal_id is None:
              params['goal_id'] = goal_id
      return self._GetData('GET', uri, params)

  def GetStatContentPopular(self, id, mirror_id='', date1='', date2='',
      table_mode='plain', per_page=100, sort='visits', reverse=1, next=''):
      """
      Returns attendance rating web pages in descending order of display.
      """
      params = next[next.find('?') + 1:] if next else ''
      uri = self._GetURI(self._STAT_CONTENT_POPULAR, params)
      params = {}
      if not next:
          params = {
              'id': id,
              'mirror_id': mirror_id,
              'date1': date1,
              'date2': date2,
              'table_mode': table_mode,
              'per_page': per_page,
              'sort': sort,
              'reverse': reverse
          }
      return self._GetData('GET', uri, params)

  def GetStatContentEntrance(self, id, goal_id=None, mirror_id='', date1='',
      date2='', table_mode='plain', per_page=100, sort='visits', reverse=1,
      next=''):
      """
      Returns information about entry points to the site
      (the first pages of visits).
      """
      params = next[next.find('?') + 1:] if next else ''
      uri = self._GetURI(self._STAT_CONTENT_ENTRANCE, params)
      params = {}
      if not next:
          params = {
              'id': id,
              'mirror_id': mirror_id,
              'date1': date1,
              'date2': date2,
              'table_mode': table_mode,
              'per_page': per_page,
              'sort': sort,
              'reverse': reverse
          }
          if not goal_id is None:
              params['goal_id'] = goal_id
      return self._GetData('GET', uri, params)

  def GetStatContentExit(self, id, mirror_id='', date1='', date2='',
      table_mode='plain', per_page=100, sort='visits', reverse=1, next=''):
      """
      Returns information about exits from the site
      (the last pages of visits).
      """
      params = next[next.find('?') + 1:] if next else ''
      uri = self._GetURI(self._STAT_CONTENT_EXIT, params)
      params = {}
      if not next:
          params = {
              'id': id,
              'mirror_id': mirror_id,
              'date1': date1,
              'date2': date2,
              'table_mode': table_mode,
              'per_page': per_page,
              'sort': sort,
              'reverse': reverse
          }
      return self._GetData('GET', uri, params)

  def GetStatContentTitles(self, id, date1='', date2='', per_page=100,
      sort='visits', reverse=1, next=''):
      """
      Returns the rating of attendance page of the site showing their titles
      (from the tag title).
      """
      params = next[next.find('?') + 1:] if next else ''
      uri = self._GetURI(self._STAT_CONTENT_TITLES, params)
      params = {}
      if not next:
          params = {
              'id': id,
              'date1': date1,
              'date2': date2,
              'per_page': per_page,
              'sort': sort,
              'reverse': reverse
          }
      return self._GetData('GET', uri, params)

  def GetStatContentUrlParam(self, id, date1='', date2='', table_mode='plain',
      per_page=100, sort='visits', reverse=1, next=''):
      """
      Returns data about the parameters mentioned Metrika in the URL visited
      site pages.
      """
      params = next[next.find('?') + 1:] if next else ''
      uri = self._GetURI(self._STAT_CONTENT_URL_PARAM, params)
      params = {}
      if not next:
          params = {
              'id': id,
              'date1': date1,
              'date2': date2,
              'table_mode': table_mode,
              'per_page': per_page,
              'sort': sort,
              'reverse': reverse
          }
      return self._GetData('GET', uri, params)

  def GetStatGeo(self, id, goal_id=None, date1='', date2='',
      table_mode='plain', per_page=100, sort='visits', reverse=1, next=''):
      """
      Returns information about users belonging to the geographical regions.
      List of regions can be grouped by regions, countries and continents.
      """
      params = next[next.find('?') + 1:] if next else ''
      uri = self._GetURI(self._STAT_GEO, params)
      params = {}
      if not next:
          params = {
              'id': id,
              'date1': date1,
              'date2': date2,
              'table_mode': table_mode,
              'per_page': per_page,
              'sort': sort,
              'reverse': reverse
          }
          if not goal_id is None:
              params['goal_id'] = goal_id
      return self._GetData('GET', uri, params)

  def GetStatDemographyAgeGender(self, id, goal_id=None, date1='', date2=''):
      """
      Returns the data separately by sex and age of visitors.
      """
      uri = self._GetURI(self._STAT_DEMOGRAPHY_AGE_GENDER)
      params = {
          'id': id,
          'date1': date1,
          'date2': date2
      }
      if not goal_id is None:
          params['goal_id'] = goal_id
      return self._GetData('GET', uri, params)

  def GetStatDemographyStructure(self, id, goal_id=None, date1='', date2=''):
      """
      Returns merged data by sex and age.
      """
      uri = self._GetURI(self._STAT_DEMOGRAPHY_STRUCTURE)
      params = {
          'id': id,
          'date1': date1,
          'date2': date2
      }
      if not goal_id is None:
          params['goal_id'] = goal_id
      return self._GetData('GET', uri, params)

  def GetStatTechBrowsers(self, id, goal_id=None, date1='', date2='',
      table_mode='plain', per_page=100, sort='visits', reverse=1, next=''):
      """
      Returns data about the visitor's browser.
      """
      params = next[next.find('?') + 1:] if next else ''
      uri = self._GetURI(self._STAT_TECH_BROWSERS, params)
      params = {}
      if not next:
          params = {
              'id': id,
              'date1': date1,
              'date2': date2,
              'table_mode': table_mode,
              'per_page': per_page,
              'sort': sort,
              'reverse': reverse
          }
          if not goal_id is None:
              params['goal_id'] = goal_id
      return self._GetData('GET', uri, params)

  def GetStatTechOs(self, id, goal_id=None, date1='', date2='',
      table_mode='plain', per_page=100, sort='visits', reverse=1, next=''):
      """
      Returns data about the operating systems of visitors.
      """
      params = next[next.find('?') + 1:] if next else ''
      uri = self._GetURI(self._STAT_TECH_OS, params)
      params = {}
      if not next:
          params = {
              'id': id,
              'date1': date1,
              'date2': date2,
              'table_mode': table_mode,
              'per_page': per_page,
              'sort': sort,
              'reverse': reverse
          }
          if not goal_id is None:
              params['goal_id'] = goal_id
      return self._GetData('GET', uri, params)

  def GetStatTechDisplay(self, id, goal_id=None, date1='', date2='',
      table_mode='plain', per_page=100, sort='visits', reverse=1, next=''):
      """
      Returns data on the display resolution of site visitors.
      """
      params = next[next.find('?') + 1:] if next else ''
      uri = self._GetURI(self._STAT_TECH_DISPLAY, params)
      params = {}
      if not next:
          params = {
              'id': id,
              'date1': date1,
              'date2': date2,
              'table_mode': table_mode,
              'per_page': per_page,
              'sort': sort,
              'reverse': reverse
          }
          if not goal_id is None:
              params['goal_id'] = goal_id
      return self._GetData('GET', uri, params)

  def GetStatTechMobile(self, id, goal_id=None, date1='', date2='',
      table_mode='plain', per_page=100, sort='visits', reverse=1, next=''):
      """
      Returns data about visitors who come to the site from mobile devices.
      """
      params = next[next.find('?') + 1:] if next else ''
      uri = self._GetURI(self._STAT_TECH_MOBILE, params)
      params = {}
      if not next:
          params = {
              'id': id,
              'date1': date1,
              'date2': date2,
              'table_mode': table_mode,
              'per_page': per_page,
              'sort': sort,
              'reverse': reverse
          }
          if not goal_id is None:
              params['goal_id'] = goal_id
      return self._GetData('GET', uri, params)

  def GetStatTechFlash(self, id, goal_id=None, date1='', date2='',
      table_mode='plain', per_page=100, sort='visits', reverse=1, next=''):
      """
      Returns data about the versions of Flash-plugin on visitors' computers.
      """
      params = next[next.find('?') + 1:] if next else ''
      uri = self._GetURI(self._STAT_TECH_FLASH, params)
      params = {}
      if not next:
          params = {
              'id': id,
              'date1': date1,
              'date2': date2,
              'table_mode': table_mode,
              'per_page': per_page,
              'sort': sort,
              'reverse': reverse
          }
          if not goal_id is None:
              params['goal_id'] = goal_id
      return self._GetData('GET', uri, params)

  def GetStatTechSilverlight(self, id, goal_id=None, date1='', date2='',
      table_mode='plain', per_page=100, sort='visits', reverse=1, next=''):
      """
      Returns data on the distribution of different versions of plugin
      Silverlight.
      """
      params = next[next.find('?') + 1:] if next else ''
      uri = self._GetURI(self._STAT_TECH_SILVERLIGHT, params)
      params = {}
      if not next:
          params = {
              'id': id,
              'date1': date1,
              'date2': date2,
              'table_mode': table_mode,
              'per_page': per_page,
              'sort': sort,
              'reverse': reverse
          }
          if not goal_id is None:
              params['goal_id'] = goal_id
      return self._GetData('GET', uri, params)

  def GetStatTechDotNet(self, id, goal_id=None, date1='', date2='',
      table_mode='plain', per_page=100, sort='visits', reverse=1, next=''):
      """
      Returns version information .NET framework on visitors' computers.
      """
      params = next[next.find('?') + 1:] if next else ''
      uri = self._GetURI(self._STAT_TECH_DOTNET, params)
      params = {}
      if not next:
          params = {
              'id': id,
              'date1': date1,
              'date2': date2,
              'table_mode': table_mode,
              'per_page': per_page,
              'sort': sort,
              'reverse': reverse
          }
          if not goal_id is None:
              params['goal_id'] = goal_id
      return self._GetData('GET', uri, params)

  def GetStatTechJava(self, id, goal_id=None, date1='', date2='',
      sort='visits', reverse=1):
      """
      Returns data on the availability of the Java platform
      on visitors' computers.
      """
      uri = self._GetURI(self._STAT_TECH_JAVA)
      params = {
          'id': id,
          'date1': date1,
          'date2': date2,
          'sort': sort,
          'reverse': reverse
      }
      if not goal_id is None:
          params['goal_id'] = goal_id
      return self._GetData('GET', uri, params)

  def GetStatTechCookies(self, id, goal_id=None, date1='', date2='',
      sort='visits', reverse=1):
      """
      Returns data about visits visitors with disabled Cookies.
      """
      uri = self._GetURI(self._STAT_TECH_COOKIES)
      params = {
          'id': id,
          'date1': date1,
          'date2': date2,
          'sort': sort,
          'reverse': reverse
      }
      if not goal_id is None:
          params['goal_id'] = goal_id
      return self._GetData('GET', uri, params)

  def GetStatTechJavascript(self, id, goal_id=None, date1='', date2='',
      sort='visits', reverse=1):
      """
      Returns data about visits visitors with disabled JavaScript
      (ECMAScript).
      """
      uri = self._GetURI(self._STAT_TECH_JAVASCRIPT)
      params = {
          'id': id,
          'date1': date1,
          'date2': date2,
          'sort': sort,
          'reverse': reverse
      }
      if not goal_id is None:
          params['goal_id'] = goal_id
      return self._GetData('GET', uri, params)


def main():
  pass

if __name__ == '__main__':
  main()
