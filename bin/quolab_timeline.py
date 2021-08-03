"""
Modular Input for QuoLab timeline activity stream indexing
"""

from __future__ import absolute_import, print_function, unicode_literals

import functools
import json
import os
import sys
import threading
import time
from collections import Counter
from datetime import timedelta
from logging import getLogger, Formatter
from queue import Empty, Queue

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))  # noqa

import cypresspoint.monkeypatch  # noqa
import six
from cypresspoint import setup_logging
from cypresspoint.checkpoint import ModInputCheckpoint
from cypresspoint.datatype import as_bool
from cypresspoint.modinput import ScriptWithSimpleSecret
from splunklib.client import Entity, HTTPError
from splunklib.modularinput import Argument, Event, Scheme  # nopqa

from ta_quolab.api import QuoLabAPI, __version__, monotonic

logger = getLogger("QuoLab.Input.Timeline")

DEBUG = True

setup_logging(
    os.path.join(os.environ['SPLUNK_HOME'], "var", "log", "splunk", "quolab_timeline.log"),
    formatter=Formatter(
        '%(asctime)s [%(process)d:%(threadName)s] %(levelname)s %(name)s:  %(message)s'),
    max_size_mb=25,
    backup_count=10,
    debug=DEBUG)


def log_exception(f):
    @functools.wraps(f)
    def wrap(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception:
            logger.exception("Unhandled exception in %s", f.__name__)
            raise
    return wrap


def counter_to_kv(c):
    return " ".join("{}={}".format(k, v) for k, v in c.items())


# Track if subscribing binding has been completed or not.
subscribed = threading.Event()
shutdown = threading.Event()


class QuoLabTimelineModularInput(ScriptWithSimpleSecret):

    # XXX: Make this a configurable parameter
    queue_size = 1024

    def get_scheme(self):
        scheme = Scheme("QuoLab Timeline")
        scheme.description = "Ingest QuoLab timeline using Web Sockets"
        scheme.use_single_instance = False
        scheme.use_external_validation = True

        scheme.add_argument(
            Argument("server",
                     title="Server",
                     description="Name of QuoLab server",
                     data_type=Argument.data_type_string,
                     required_on_create=True
                     ))
        scheme.add_argument(
            Argument("timeline",
                     title="Timeline",
                     description="Timeline id from QuoLab",
                     data_type=Argument.data_type_string,
                     required_on_create=True
                     ))
        scheme.add_argument(
            Argument("backfill",
                     title="Enable Backfill",
                     description="If enabled, the first run will retrieve all existing events from the queue",
                     data_type=Argument.data_type_boolean,
                     ))
        scheme.add_argument(
            Argument("log_level",
                     title="Log_level",
                     description="Logging level for internal logging",
                     required_on_create=True
                     ))
        return scheme

    def fetch_quolab_servers(self, server):
        logger.debug("Fetching API endpoint configurations from Splunkd (quolab_servers.conf)")
        try:
            data = Entity(self.service, "quolab/quolab_servers/{}/full".format(server))
        except HTTPError as e:
            logger.info(
                "No known server named '%s', check quolab_servers.conf.  (Exception: %s)", server, e)
            return None
        except Exception:
            logger.exception("Unhandled exception while fetching data from quolab_servers.conf")
            raise
        return data

    def validate_input(self, validation_definition):
        try:
            self._validate_input(validation_definition)
        except Exception:
            logger.exception("Validation error")
            raise

    def _validate_input(self, validation_definition):
        # XXX:  Do validation on 'server' (look it up)
        # XXX:  Make call to /v1/timeline to confirm that timeline_id exists

        params = validation_definition.parameters
        valid_log_level_values = ["DEBUG", "INFO", "WARN", "ERROR"]
        if params["log_level"] not in valid_log_level_values:
            raise ValueError("Unexpected value for 'log_level'. "
                             "Please pick from {}".format(" ".join(valid_log_level_values)))

    @staticmethod
    @log_exception
    def backfill_reader(api, timeline, queue, facets, counter, retry=0):
        """ This will be launched in its own thread. """
        logger.info("backfill thread activated.  Waiting for subscription event.")
        wait_return = subscribed.wait(100)
        logger.info("backfill thread subscription received. return=%r", wait_return)

        # XXX: We likely don't need this anymore?
        time.sleep(.5)
        logger.info("Reading from the queue to backfill missing events")
        try:
            for body in api.get_timeline_events(timeline, facets):
                queue.put(("backfill", body["id"], body))
                counter["backfill_queued"] += 1
        except Exception:
            logger.exception("Failed to retrieve all backfill events.")

            # XXX: Experimental attempt to workaround this an elusive issue
            if retry <= 3:
                retry += 1
                logger.info("Will attempt to re-run the backfill (retry=%d)", retry)
                time.sleep(5)
                threading.Thread(target=QuoLabTimelineModularInput.backfill_reader,
                                 args=(api, timeline, queue, facets, counter),
                                 kwargs={"retry": retry}).start()
            else:
                logger.error("Too many retry attempts for backfill (retry=%d)  Giving up.", retry)
                return

        # We can't easily determine how many events were written vs skipped, without waiting for the queue to drain
        timeout_limit = 600
        timeout = timeout_limit
        while timeout > 0:
            time.sleep(1)
            timeout -= 1
            if queue.empty():
                # There's still a race condition here :-(   there could be a gap between queue.get() in the receiver
                time.sleep(1)
                break

        logger.info("Loaded %d of %d events from queue buffer.  %d skipped  quiesce_time_s=%d attempt=%d",
                    counter["backfill_ingested"],
                    counter["backfill_queued"],
                    counter["backfill_skipped"],
                    timeout_limit - timeout,
                    retry)

    @staticmethod
    @log_exception
    def websocket_reader(api, timeline, queue, facets, counter):
        global shutdown

        @log_exception
        def put_event_queue(record):
            body = record["body"]
            event_id = body["id"]
            queue.put(("websocket", event_id, body))
            counter["websocket_queued"] += 1

        @log_exception
        def out_of_band(type, *info):
            if type == "bound":
                logger.info("OOB Callback:  Triggering backfill")
                subscribed.set()
            elif type == "error":
                logger.info("OOB Callback:  Error encountered:  %s", info)
            elif type == "close":
                logger.info("OOB Callback:  Close socket")

        logger.info("Starting websocket listening....")
        ws = api.subscribe_timeline(put_event_queue, out_of_band, timeline, facets)
        shutdown = ws.is_done
        logger.info("Registed shutdown event")

    def stream_events(self, inputs, ew):
        # Workaround for Splunk SDK's poor modinput error capturing.  Logging enhancement
        try:
            self._stream_events(inputs, ew)
        except Exception:
            logger.exception("Exception while trying to stream events.")
            sys.exit(1)

    def _stream_events(self, inputs, ew):
        checkpoint_dir = inputs.metadata.get("checkpoint_dir")
        self.lifetime_counter = Counter()

        # XXX: Make this check more 'official' and drop the loop below / dedent.
        # One input is fundamental limitation of this design at this point.
        if len(inputs.inputs) != 1:
            raise AssertionError("Expecting exactly 1 input!")

        for input_name, input_item in six.iteritems(inputs.inputs):
            # Q:  is a counter thread safe?
            # A:  Kinda, thread-safe enough.  It's subclass of dict so that helps, but
            #     d[x] += 1 is NOT threadsafe in general, but if we avoid updating the
            #     same key multiples places, that should be safe.  To put this in
            #     perspective, worse case is an invalid count, so an acceptable risk.
            counter = Counter(inputs_processed=1)

            # FOR DEVELOPMENT -- Risks sensitive data leaks
            # logger.info("input_item :   %s", input_item)
            # logger.info("inputs.metadata :   %s", inputs.metadata)

            # Monkey patch!
            app = input_item["__app"]

            server = input_item['server']
            timeline = input_item['timeline']
            backfill = as_bool(input_item['backfill'])
            history_size = 10000

            # XXX: Add these as param :=)
            facets = ["display"]
            # stats_interval = 300

            log_level = input_item['log_level']

            # Load reference content from quolab_servers.conf
            server = self.fetch_quolab_servers(server)
            if not server:
                # Skip current input due to reference failure
                continue
            api_url = server["url"]
            api_username = server["username"]
            api_secret = server["secret"]
            api_verify = as_bool(server["verify"])

            logger.info('Processing input input_name="%s" app=%s ta_version=%s '
                        'server=%s', input_name, app, __version__, api_url)
            cp = ModInputCheckpoint(checkpoint_dir, input_name)
            cp.load()
            cp.dump_after_updates = 50

            # Use queue to safely manage work from backfill websocket streams
            queue = Queue(self.queue_size)

            api = QuoLabAPI(api_url, verify=api_verify)
            if api_username == "<TOKEN>":
                api.login_token(api_secret)
            else:
                api.login(api_username, api_secret)

            load_from_buffer = True
            backfill_thread = None

            # Keep track of which event ids have been previously loaded
            known_ids = cp.get("event_ids", [])
            if known_ids is None:
                if backfill:
                    logger.info("First run.  Will backfill with events from queue.")
                else:
                    logger.info("First run.  Skipping backfill.")
                    load_from_buffer = False

            if load_from_buffer:
                backfill_thread = threading.Thread(target=self.backfill_reader,
                                                   args=(api, timeline, queue, facets, counter))
                backfill_thread.start()

            # XXX: Technically, there's a race-condition here.
            # Q:  Should the websocket stream should be established before the backfill?
            # A:  Per Fred/Tiago:  YES
            # Doh, there is still a race condition.  Because we don't known exactly when the websocket is subscribed

            # XXX: Not sure why calling this function directly doesn't seem to work; but the thread approach works
            # self.websocket_reader(api, timeline, queue, facets, counter)
            websocket_thread = threading.Thread(target=self.websocket_reader,
                                                args=(api, timeline, queue, facets, counter))
            websocket_thread.start()

            maint_interval = 30
            dump_max_interval = timedelta(seconds=45)
            next_maint = monotonic() + maint_interval

            # XXX:  For debugging where duplicates are comming from
            PID = os.getpid()
            EVENT_ID = 0

            # Fetch queued events and send them to Splunk
            try:
                while not shutdown.is_set():
                    do_maint = False
                    try:
                        queue_source, event_id, record = queue.get(timeout=maint_interval)
                        # Q: should we only check for dups for queue_source=="backfill"?  (check counter)
                        if event_id in known_ids:
                            counter["{}_skipped".format(queue_source)] += 1
                            continue

                        # XXX:  'TA_CODEPATH' for debugging where events come from.
                        record["TA_CODEPATH"] = queue_source
                        record["TA_PID"] = PID
                        EVENT_ID += 1
                        record["TA_EVENT_ID"] = EVENT_ID

                        msg = json.dumps(record, separators=(',', ':'))
                        e = Event(sourcetype="quolab:timeline", unbroken=True, data=msg)
                        ew.write_event(e)

                        known_ids.append(event_id)
                        cp["event_ids"] = known_ids
                        counter["{}_ingested".format(queue_source)] += 1
                        counter["events_ingested"] += 1

                        if monotonic() > next_maint:
                            do_maint = True

                    except Empty:
                        logger.debug("timeout waiting for events in queue.  Trigger maint tasks.")
                        do_maint = True

                    if do_maint:
                        logger.info('Processing stats:  input_name="%s" '
                                    'Event counts:  %s', input_name,
                                    counter_to_kv(counter))

                        # XXX: Improve cleanup logic to probe /v1/timeline for queue length at startup
                        if len(known_ids) > history_size:
                            logger.debug("Cleaning up event_id history.   "
                                         "Had %d entries, capping at %d", len(known_ids), history_size)
                            known_ids = known_ids[history_size:]
                            cp["event_ids"] = known_ids
                        cp.dump_on_interval(dump_max_interval)
                        next_maint = monotonic() + maint_interval

            except (KeyboardInterrupt, SystemExit) as e:
                # Note that using 'get()' in python 2.7 and on Windows, this get() with timeout may not be interuptable
                # See https://docs.python.org/3/library/queue.html#queue.Queue.get the implications are not clear to me
                # Just existing the above loop is good enough
                logger.info("Exiting loop due to %s", e)
                pass

            logger.info('Done processing:  input_name="%s" shutdown_reason=%s'
                        'Event counts:  backfill=%d streamed=%d events_ingested=%d  |  %s', input_name,
                        "requested" if shutdown.isSet() else "exception",
                        counter["backfill_ingested"], counter["websocket_ingested"],
                        counter["events_ingested"], counter_to_kv(counter))
            self.lifetime_counter += counter
            cp.dump()
            del cp

        if self.lifetime_counter["inputs_processed"] > 1:
            logger.info("Modular input shutting down.  Lifetime stats:  %s",
                        counter_to_kv(self.lifetime_counter))


if __name__ == "__main__":
    try:
        modinput = QuoLabTimelineModularInput()
        sys.exit(modinput.run(sys.argv))
    except Exception:
        logger.exception("Unhandled top-level exception.")
