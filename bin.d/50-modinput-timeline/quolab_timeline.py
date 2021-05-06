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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))  # noqa

import cypresspoint.monkeypatch  # noqa
from splunklib.modularinput import Event, Argument, Scheme  # nopqa

from cypresspoint import setup_logging
from cypresspoint.compat import dt_to_epoch
from cypresspoint.datatype import as_bool, reltime_to_timedelta
from cypresspoint.modinput import ScriptWithSimpleSecret
from cypresspoint.checkpoint import ModInputCheckpoint


import requests
import six

from requests.auth import HTTPBasicAuth
from six.moves.urllib.parse import quote, urlsplit, urlunsplit, urlencode

logger = getLogger("QuoLab")

DEBUG = True

setup_logging(
    os.path.join(os.environ['SPLUNK_HOME'], "var", "log", "splunk", "quolab_timeline.log"),
    debug=DEBUG)


class QuoLabTimelineModularInput(ScriptWithSimpleSecret):
    def get_scheme(self):
        scheme = Scheme("QuoLab")
        scheme.description = "Poll QuoLab API for events"
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

    def validate_input(self, validation_definition):
        try:
            self._validate_input(validation_definition)
        except Exception:
            logger.exception("Validation error")
            raise

    def _validate_input(self, validation_definition):
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

            # FOR DEVELOPMENT -- Risks sensitive data leaks
            # logger.info("input_item :   %s", input_item)
            # logger.info("inputs.metadata :   %s", inputs.metadata)

            # Monkey patch!
            app = input_item["__app"]

            server = input_item['server']
            timeline = input_item['timeline']
            backfill = as_bool(input_item['backfill'])
            log_level = input_item['log_level']
            # COOKIECUTTER-TODO:  Handle secret, like so, when using a script with a simple secret
            # token = self.handle_secret(input_name, input_item["token"], app)

            logger.info('Processing input input_name="%s" app=%s ta_version=%s',
                        input_name, app, __version__)
            cp = ModInputCheckpoint(checkpoint_dir, input_name)
            cp.load()

            # COOKIECUTTER-TODO:  Add code to handle your use case
            '''
            api = QuoLabAPI(your_variable_name_goes_here)
            api.login_token(username, token)
            '''
            start_time = cp.get("start_time", None)
            if start_time is None:
                start_time = now - backfill_range
                logger.debug("First run.  Reading from %s (backfill range: %s)",
                             start_time, backfill_range)
            else:
                start_time = datetime.fromtimestamp(start_time, timezone.utc)
                logger.debug("Starting to read from %s", start_time)

            logger.info("Launching QuoLab something or other API:  start_time=%s",
                        start_time)

            total_events = 0

            for record in your_data_iterable_goes_here:
                ew.write_event(
                    Event(sourcetype="quolab:timeline", unbroken=True,
                          data=json.dumps(record, sort_keys=True, separators=(',', ':'))))
                # COOKIECUTTER-TODO:  Incremental updates to 'start_time' checkpoint
                cp["start_time"] = dt_to_epoch(datetime.strptime(
                    record["updated_at"], "%Y-%m-%dT%H:%M:%S %z"))
                total_events += 1
            cp.dump()
            del cp

            logger.info('Done processing:  input_name="%s" total_events=%d',
                        input_name, total_events)


if __name__ == "__main__":
    try:
        modinput = QuoLabTimelineModularInput()
        sys.exit(modinput.run(sys.argv))
    except Exception:
        logger.exception("Unhandled top-level exception.")
