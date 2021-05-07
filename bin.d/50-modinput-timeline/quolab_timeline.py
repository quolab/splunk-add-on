"""
Modular Input for stuff
"""
from __future__ import absolute_import, print_function, unicode_literals


import os
import sys
import re
import json
import functools
import time

from datetime import datetime, timedelta, timezone
from logging import getLogger
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))  # noqa

import cypresspoint.monkeypatch  # noqa
from splunklib.modularinput import Event, Argument, Scheme  # nopqa
from splunklib.client import Entity, HTTPError

from cypresspoint import setup_logging
from cypresspoint.compat import dt_to_epoch
from cypresspoint.datatype import as_bool, reltime_to_timedelta
from cypresspoint.modinput import ScriptWithSimpleSecret
from cypresspoint.checkpoint import ModInputCheckpoint

from quolab_ta import QuoLabAPI, __version__

import requests
import six

logger = getLogger("QuoLab.Input.Timeline")

DEBUG = True

setup_logging(
    os.path.join(os.environ['SPLUNK_HOME'], "var", "log", "splunk", "quolab_timeline.log"),
    debug=DEBUG)


class QuoLabTimelineModularInput(ScriptWithSimpleSecret):
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
            logger.info("No known server named '%s', check quolab_servers.conf", server)
            return None
        except Exception as e:
            self.logger.exception(
                "Unhandled exception while fetching data from quolab_servers.conf")
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

    def stream_events(self, inputs, ew):
        # Workaround for Splunk SDK's poor modinput error capturing.  Logging enhancement
        try:
            self._stream_events(inputs, ew)
        except Exception:
            logger.exception("Exception while trying to stream events.")
            sys.exit(1)

    def _stream_events(self, inputs, ew):
        checkpoint_dir = inputs.metadata.get("checkpoint_dir")
        now = datetime.now(timezone.utc)

        for input_name, input_item in six.iteritems(inputs.inputs):

            counter = Counter()

            # FOR DEVELOPMENT -- Risks sensitive data leaks
            # logger.info("input_item :   %s", input_item)
            # logger.info("inputs.metadata :   %s", inputs.metadata)

            # Monkey patch!
            app = input_item["__app"]

            server = input_item['server']
            timeline = input_item['timeline']
            backfill = as_bool(input_item['backfill'])

            # XXX: Add these as param :=)
            facets = ["display"]
            stats_interval = 300

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
                        'server=%s', input_name, app, __version__, server)
            cp = ModInputCheckpoint(checkpoint_dir, input_name)
            cp.load()

            api = QuoLabAPI(api_url, verify=api_verify)
            if api_username == "<TOKEN>":
                api.login_token(api_secret)
            else:
                api.login(api_username, api_secret)

            load_from_buffer = True

            # Keep track of which event ids have been previously loaded
            known_ids = cp.get("event_ids", [])
            if known_ids is None:
                if backfill:
                    logger.info("First run.  Will backfill with events from queue.")
                else:
                    logger.info("First run.  Skipping backfill.")
                    load_from_buffer = False

            if load_from_buffer:
                current_ids = []
                logger.info("Query QuoLab timeline for buffered events.  "
                            "(%d known ids cached)", len(known_ids))
                for body in api.get_timeline_events(timeline, facets):
                    event_id = body["id"]
                    current_ids.append(event_id)
                    if event_id not in known_ids:
                        logger.info("Ingesting (new) id %s", event_id)
                        body["TA_CODEPATH"] = "backfill"
                        e = Event(sourcetype="quolab:timeline", unbroken=True,
                                  data=json.dumps(body, sort_keys=True, separators=(',', ':')))
                        ew.write_event(e)
                        counter["backfill_events"] += 1
                    else:
                        logger.info("Skipping dup %s", event_id)
                        counter["backfill_skip"] += 1
                # Assumption here is that after filtering out dups for the backfill ingestion (to find events
                # triggered while this modular input was offline), can be replaced with a new list of ids
                # just pulled from the server.  Items expired from the buffer will never re-occur.

                logger.info("known_ids=%r   current_ids=%r", known_ids, current_ids)
                #known_ids = current_ids
                known_ids.clear()
                known_ids.extend(current_ids)
                logger.info("Loaded %d events from queue buffer.  %d skipped",
                            counter["backfill_events"], counter["backfill_skip"])

            # XXX: Technically, there's a race-condition here.
            # Q:  Should the websocket stream should be established before the backfill?
            logger.info("Starting websocket listening....")

            def write_event(record):
                body = record["body"]
                body["TA_CODEPATH"] = "stream"
                event_id = body["id"]
                msg = json.dumps(body, sort_keys=True, separators=(',', ':'))
                e = Event(sourcetype="quolab:timeline", unbroken=True, data=msg)
                ew.write_event(e)
                # XXX: Add 'id' to event_ids.  ALSO come up with a max queue size (or just query for it
                # against /v1/timeline directly) so that we have an idea of how many back items to store.
                # Another approach would be to re-query /v1/timeline/<ID>/event periodically, using the
                # same cleanup logic used above.

                known_ids.append(event_id)
                cp["event_ids"] = known_ids
                counter["stream_events"] += 1

            ws = api.subscribe_timeline(write_event, timeline, facets)

            try:
                while not ws.is_done.wait(stats_interval):
                    logger.info('Processing stats:  input_name="%s" '
                                'Event counts:  backfill=%d streamed=%d', input_name,
                                counter["backfill_events"], counter["stream_events"])
                    cp.dump()
            except (KeyboardInterrupt, SystemExit):
                # Just existing the above loop is good enough
                pass

            logger.info('Done processing:  input_name="%s" '
                        'Event counts:  backfill=%d streamed=%d', input_name,
                        counter["backfill_events"], counter["stream_events"])
            cp.dump()
            del cp


if __name__ == "__main__":
    try:
        modinput = QuoLabTimelineModularInput()
        sys.exit(modinput.run(sys.argv))
    except Exception:
        logger.exception("Unhandled top-level exception.")
