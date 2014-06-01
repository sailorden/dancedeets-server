import json
from google.appengine.api import urlfetch

import fb_api

def get_object(string_key):
    return json.loads(open('test_data/FacebookCachedObject/%s' % string_key).read())

class Stub(object):
    def activate(self, memory_memcache=True, disk_db=True):
        self.real_fb_api = fb_api.FBAPI
        if memory_memcache:
            fb_api.FBAPI = MemoryFBAPI
        self.real_db_cache = fb_api.DBCache
        if disk_db:
            fb_api.DBCache = DiskDBCache

    def deactivate(self):
        fb_api.FBAPI = self.real_fb_api
        fb_api.DBCache = self.real_db_cache

class DiskDBCache(fb_api.DBCache):
    def fetch_keys(self, keys):
        fetched_objects = {}
        for key in keys:
            try:
                fetched_objects[key] = get_object(self.key_to_cache_key(key))
            except IOError:
                pass
        return fetched_objects

class FakeRequest(object):
    def __init__(self, url):
        self._url = url

    def url(self):
        return self._url

class FakeRPC(object):
    def __init__(self, url):
        self.url = url
        self.request = FakeRequest(url)

    def get_result(self):
        if self.url in MemoryFBAPI.results:
            status_code, content = MemoryFBAPI.results[self.url]
            return FakeResult(status_code, content)
        else:
            raise urlfetch.DownloadError('no backend data found')

class FakeResult(object):
    def __init__(self, status_code, content):
        self.status_code = status_code
        self.content = json.dumps(content)

class MemoryFBAPI(fb_api.FBAPI):
    results = {}

    def _create_rpc_for_url(self, url):
        return FakeRPC(url)