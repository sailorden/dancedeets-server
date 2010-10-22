
import datetime
import logging
import time
import urllib

from django.utils import simplejson
from google.appengine.ext.webapp import RequestHandler
from google.appengine.api import mail

import base_servlet
from events import eventdata
from events import users
import facebook
import fb_api
from logic import backgrounder
from logic import email_events
from logic import potential_events
from logic import rankings

# How long to wait before retrying on a failure. Intended to prevent hammering the server.
RETRY_ON_FAIL_DELAY = 60

class BaseTaskRequestHandler(RequestHandler):
    def requires_login(self):
        return False


class BaseTaskFacebookRequestHandler(BaseTaskRequestHandler):
    def requires_login(self):
        return False

    def initialize(self, request, response):
        return_value = super(BaseTaskFacebookRequestHandler, self).initialize(request, response)

        self.fb_uid = int(self.request.get('user_id'))
        self.user = users.User.get_cached(self.fb_uid)
        assert self.user.fb_access_token, "Can't execute background task for user %s without access_token" % self.fb_uid
        self.fb_graph = facebook.GraphAPI(self.user.fb_access_token)
        self.allow_cache = bool(int(self.request.get('allow_cache', 1)))
        self.batch_lookup = fb_api.CommonBatchLookup(self.fb_uid, self.fb_graph, allow_cache=self.allow_cache)
        return return_value

class TrackNewUserFriendsHandler(BaseTaskFacebookRequestHandler):
    def get(self):
        app_friend_list = self.fb_graph.api_request('method/friends.getAppUsers')
        user_friends = users.UserFriendsAtSignup.get_by_key_name(str(self.fb_uid))
        user_friends.registered_friend_ids = app_friend_list
        user_friends.put()
    post=get

class LoadEventHandler(BaseTaskFacebookRequestHandler):
    def get(self):
        event_ids = [x for x in self.request.get('event_ids').split(',') if x]
        for event_id in event_ids:
            self.batch_lookup.lookup_event(event_id)
        self.batch_lookup.finish_loading()
        db_events = eventdata.DBEvent.get_by_key_name(event_ids)
        failed_fb_event_ids = []
        for event_id, db_event in zip(event_ids, db_events):
            if not db_event:
                continue # could be due to uncache-able events that we don't save here
            try:
                fb_event = self.batch_lookup.data_for_event(db_event.fb_event_id)
                db_event.make_findable_for(fb_event)
                db_event.put()
            except:
                logging.exception("Error loading event, going to retry eid=%s", event_id)
                failed_fb_event_ids.append(event_id)
        backgrounder.load_events(failed_fb_event_ids, self.allow_cache, countdown=RETRY_ON_FAIL_DELAY)
    post=get

class LoadEventMembersHandler(BaseTaskFacebookRequestHandler):
    def get(self):
        event_ids = [x for x in self.request.get('event_ids').split(',') if x]
        for event_id in event_ids:
            self.batch_lookup.lookup_event_members(event_id)
        self.batch_lookup.finish_loading()
        failed_fb_event_ids = []
        for event_id in event_ids:
            try:
                self.batch_lookup.data_for_event_members(event_id)
            except:
                logging.exception("Error loading event, going to retry eid=%s", event_id)
                failed_fb_event_ids.append(event_id)
        backgrounder.load_event_members(failed_fb_event_ids, self.allow_cache, countdown=RETRY_ON_FAIL_DELAY)
    post=get

class LoadUserHandler(BaseTaskFacebookRequestHandler):
    def get(self):
        user_ids = [x for x in self.request.get('user_ids').split(',') if x]
        for user_id in user_ids:
            self.batch_lookup.lookup_user(user_id)
        self.batch_lookup.finish_loading()
        failed_fb_user_ids = []
        for user_id in user_ids:
            try:
                self.batch_lookup.data_for_user(user_id)
            except:
                logging.exception("Error loading user, going to retry uid=%s", user_id)
                failed_fb_user_ids.append(user_id)
        load_users = users.User.get_by_key_name(user_ids)
        for user in load_users:
            user.compute_derived_properties(self.batch_lookup.data_for_user(user_id))
            user.put()
        backgrounder.load_users(failed_fb_user_ids, self.allow_cache, countdown=RETRY_ON_FAIL_DELAY)

    post=get

class ReloadAllUsersHandler(BaseTaskRequestHandler):
    def get(self):
        user_ids = [user.fb_uid for user in users.User.all()]
        backgrounder.load_users(user_ids, allow_cache=False)    
    post=get

class ResaveAllUsersHandler(BaseTaskRequestHandler):
    def get(self):
        user_ids = [user.fb_uid for user in users.User.all()]
        backgrounder.load_users(user_ids)
    post=get

class ResaveAllEventsHandler(BaseTaskRequestHandler):
    def get(self):
        event_ids = [db_event.fb_event_id for db_event in eventdata.DBEvent.all()]
        backgrounder.load_events_full(event_ids)
    post=get

class ReloadAllEventsHandler(BaseTaskRequestHandler):
    def get(self):
        event_ids = [db_event.fb_event_id for db_event in eventdata.DBEvent.all()]
        backgrounder.load_events_full(event_ids, allow_cache=False)
    post=get

class ReloadPastEventsHandler(BaseTaskRequestHandler):
    def get(self):
        gm_today = datetime.datetime(*time.gmtime(time.time())[:6])
        event_ids = [db_event.fb_event_id for db_event in eventdata.DBEvent.gql("WHERE start_time < :1", gm_today)]
        backgrounder.load_events_full(event_ids, allow_cache=False)
    post=get

class ReloadFutureEventsHandler(BaseTaskRequestHandler):
    def get(self):
        gm_yesterday = datetime.datetime(*time.gmtime(time.time())[:6]) - datetime.timedelta(days=1)
        event_ids = [db_event.fb_event_id for db_event in eventdata.DBEvent.gql('WHERE end_time > :1', gm_yesterday)]
        backgrounder.load_events_full(event_ids, allow_cache=False)    
    post=get

class EmailAllUsersHandler(BaseTaskRequestHandler):
    def get(self):
        user_ids = [user.fb_uid for user in users.User.all()]
        backgrounder.email_users(user_ids)    
    post=get

class EmailUserHandler(BaseTaskFacebookRequestHandler):
    def get(self):
        self.batch_lookup.lookup_user(self.user.fb_uid)
        self.batch_lookup.finish_loading()
        email_events.email_for_user(self.user, self.batch_lookup, self.fb_graph)
    post=get

class CleanupWorkHandler(RequestHandler):
    def get(self):
        event_ids = [db_event.fb_event_id for db_event in eventdata.DBEvent.gql("WHERE address = null and start_time != null")]
        if event_ids:
            event_urls = ['http://www.dancedeets.com/events/admin_edit?event_id=%s' % x for x in event_ids]
            html = "Events missing addresses:\n\n" + "\n".join(event_urls)
            message = mail.EmailMessage(
                sender="events@dancedeets.com",
                to="mlambert@gmail.com",
                subject="Events missing addresses",
                html=html
            )

class ComputeRankingsHandler(RequestHandler):
    def get(self):
        rankings.begin_ranking_calculations()

class LoadAllPotentialEventsHandler(RequestHandler):
    #OPT: maybe some day make this happen immediately after reloading users, so we can guarantee the latest users' state, rather than adding another day to the pipeline delay
    #TODO(lambert): email me when we get the latest batch of things completed.
    def get(self):
        user_ids = [user.fb_uid for user in users.User.all()]
        backgrounder.load_potential_events_for_users(user_ids)

class LoadPotentialEventsForUserHandler(BaseTaskFacebookRequestHandler):
    def get(self):
        user_ids = [x for x in self.request.get('user_ids').split(',') if x]
        load_users = users.User.get_by_key_name(user_ids)
        for user in load_users:
            self.batch_lookup.lookup_user(user.fb_uid)
        self.batch_lookup.finish_loading()
        for user in load_users:
            potential_events.get_potential_dance_events(self.batch_lookup, user)

class UpdateLastLoginTimeHandler(RequestHandler):
    def get(self):
        user = users.User.get_by_key_name(self.request.get('user_id'))
        user.last_login_time = datetime.datetime.now()
        try:
            user.put()
        except apiproxy_errors.CapabilityDisabledError:
            pass # read-only mode!
