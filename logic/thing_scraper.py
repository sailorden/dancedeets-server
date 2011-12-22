import cgi
import datetime
import logging
import urlparse

import facebook

from events import eventdata
import fb_api
from logic import event_classifier
from logic import potential_events
from logic import thing_db

from util import fb_mapreduce

def scrape_events_from_source(batch_lookup, source):
    # don't scrape sources that prove useless and give mostly garbage events
    if source.fraction_potential_are_real() < 0.05:
        return

    batch_lookup = batch_lookup.copy(allow_cache=False)
    batch_lookup.lookup_thing_feed(source.graph_id)
    batch_lookup.finish_loading()

    event_ids = []
    try:
        thing_feed = batch_lookup.data_for_thing_feed(source.graph_id)
        event_ids = process_thing_feed(source, thing_feed, batch_lookup.copy(allow_cache=True))
    except fb_api.NoFetchedDataException, e:
        logging.error("Failed to fetch data for thing: %s", str(e))
    return event_ids

def scrape_source(source):
    batch_lookup = fb_mapreduce.get_batch_lookup()
    event_ids = scrape_events_from_source(batch_lookup, source)

def mapreduce_scrape_all_sources(batch_lookup):
    fb_mapreduce.start_map(
        batch_lookup.copy(allow_cache=False), # Force refresh of thing feeds
        'Scrape All Sources',
        'logic.thing_scraper.scrape_source',
        'logic.thing_db.Source'
    )

def create_source_from_event(event):
    batch_lookup = fb_mapreduce.get_batch_lookup()
    thing_db.create_source_from_event(event, batch_lookup)

def mapreduce_create_sources_from_events(batch_lookup):
    fb_mapreduce.start_map(
        batch_lookup,
        'Create Sources from Events',
        'logic.thing_scraper.create_source_from_event',
        'events.eventdata.DBEvent'
    )

def process_thing_feed(source, thing_feed, batch_lookup):
    if thing_feed['deleted']:
        return []
    # TODO(lambert): do we really need to scrape the 'info' to get the id, or we can we half the number of calls by just getting the feed? should we trust that the type-of-the-thing-is-legit for all time, which is one case we use 'info'?
    if 'data' not in thing_feed['feed']:
        logging.error("No 'data' found in: %s", thing_feed['feed'])
        return []
    
    # save new name, feed_history_in_seconds
    source.compute_derived_properties(thing_feed)
    source.last_scrape_time = datetime.datetime.now()
    source.put()

    event_ids = []
    source_ids = []
    for post in thing_feed['feed']['data']:
        if 'link' in post:
            p = urlparse.urlparse(post['link'])
            if p.netloc == 'www.facebook.com' and (p.path == '/event.php' or p.path.startswith('/events/')):
                event_id = None
                qs = cgi.parse_qs(p.query)
                if 'eid' in qs:
                    eid = qs['eid'][0]
                if p.path.startswith('/events/'):
                    eid = p.path.split('/')[2]
                if eid:
                    event_ids.append(eid)
                    if 'from' in post:
                        source_ids.append(post['from']['id'])
                else:
                    logging.error("broken link is %s", post['link'])

    # TODO(lambert): maybe trim any ids from posts with dates "past" the last time we scraped? tricky to get correct though
    for event_id in event_ids:
        batch_lookup.lookup_event(event_id)
    batch_lookup.finish_loading()

    for event_id in event_ids:
        fb_event = batch_lookup.data_for_event(event_id)
        if fb_event['deleted']:
            continue
        match_score = event_classifier.get_classified_event(fb_event).match_score()
        potential_events.make_potential_event_with_source(event_id, match_score, source=source, source_field=thing_db.FIELD_FEED)
            

    existing_source_ids = set([x.graph_id for x in thing_db.Source.get_by_key_name(source_ids) if x])
    new_source_ids = [x for x in source_ids if x not in existing_source_ids]
    for source_id in new_source_ids:
        s = thing_db.create_source_for_id(source_id, fb_data=None) #TODO(lambert): we know it doesn't exist, why does create_source_for_id check datastore?
        s.put()
        

    return event_ids
