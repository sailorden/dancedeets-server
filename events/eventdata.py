import logging

from google.appengine.ext import ndb

from loc import gmaps_api
from util import urls

REGION_RADIUS = 200 # kilometers
CHOOSE_RSVPS = ['attending', 'maybe', 'declined']

TIME_PAST = 'PAST'
TIME_FUTURE = 'FUTURE'

def get_event_image_url(fb_event):
    picture_url = fb_event.get('fql_info')
    # TODO(FB2.0): cleanup!
    if fb_event.get('picture'):
        return fb_event['picture']['data']['url']
    elif picture_url and picture_url['data']:
        return picture_url['data'][0]['pic_big']
    else:
        logging.error("Error loading picture for event id %s", fb_event['info']['id'])
        return urls.fb_event_image_url(fb_event['info']['id'])

def get_largest_cover(fb_event):
    if 'cover_info' in fb_event:
        cover = fb_event['cover_info'][fb_event['info']['cover']['cover_id']]
        max_cover = max(cover['images'], key=lambda x: x['height'])
        return max_cover
    else:
        return None

CM_AUTO = 'CM_AUTO'
CM_ADMIN = 'CM_ADMIN'
CM_USER = 'CM_USER'

class DBEvent(ndb.Model):
    """Stores custom data about our Event"""
    fb_event_id = property(lambda x: str(x.key.string_id()))

    # TODO(lambert): right now this is unused, but maybe we want to cache our "ish" tags or something to that effect?
    # Was originally used to track manually-applied tags
    tags = ndb.StringProperty(indexed=False, repeated=True)

    # real data
    owner_fb_uid = ndb.StringProperty()
    #STR_ID_MIGRATE
    creating_fb_uid = ndb.IntegerProperty(indexed=False)
    creation_time = ndb.DateTimeProperty(indexed=False, auto_now_add=True)
    # could be AUTO, ADMIN, USER, etc? Helps for maintaining a proper training corpus
    #TODO(lambert): start using this field in auto-created events
    creating_method = ndb.StringProperty(indexed=False)

    # searchable properties
    search_time_period = ndb.StringProperty()
    start_time = ndb.DateTimeProperty()
    end_time = ndb.DateTimeProperty()
    attendee_count = ndb.IntegerProperty()

    # extra cached properties
    address = ndb.StringProperty(indexed=False) # manually overridden address
    actual_city_name = ndb.StringProperty(indexed=False) # city for this event
    city_name = ndb.StringProperty() # largest nearby city for this event
    latitude = ndb.FloatProperty()
    longitude = ndb.FloatProperty()
    anywhere = ndb.BooleanProperty()

    location_geocode = ndb.JsonProperty()
    fb_event = ndb.JsonProperty()

    event_keywords = ndb.StringProperty(indexed=False, repeated=True)

    def get_geocode(self):
        return gmaps_api.parse_geocode(self.location_geocode)

    def has_geocode(self):
        return self.location_geocode is not None

    @classmethod
    def get_by_ids(cls, id_list):
        return ndb.get_multi([ndb.Key(DBEvent, x) for x in id_list])
