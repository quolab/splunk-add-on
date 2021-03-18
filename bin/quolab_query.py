#!/usr/bin/env python
# coding=utf-8

from __future__ import absolute_import, division, print_function, unicode_literals

__version__ = "0.1.0"

import os
import sys
import re
import json
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))  # nopep8

import six
import requests
from cypresspoint.datatype import as_bool
from cypresspoint.searchcommand import ensure_fields

from cypresspoint.spath import splunk_dot_notation

from requests.auth import HTTPBasicAuth
from splunklib.client import Entity
from splunklib.searchcommands import dispatch, GeneratingCommand, Configuration, Option, validators


""" http debug logging
import logging
from http.client import HTTPConnection  # py3

log = logging.getLogger('urllib3')
log.setLevel(logging.DEBUG)
"""


@Configuration()
class QuoLabQueryCommand(GeneratingCommand):
    """

    ##Syntax

    .. code-block::
        quolabquery server=my_server field=input

    ##Description

    ##Example
    """
    server = Option(
        require=False,
        default="QuoLab",
        validate=validators.Match("server", "[a-zA-Z0-9._]+"))

    output = Option(
        require=True,
        validate=validators.Fieldname())

    field_set = Option(
        require=False,
        validate=validators.Set("a", "b", "c"))

    field_int = Option(
        require=False,
        default=32,
        validate=validators.Integer(1, 128))

    field_bool = Option(
        require=False,
        default=True,
        validate=validators.Boolean())

    """ COOKIECUTTER-TODO:  Use or delete these tips'n'tricks

    *** Class-level stuff ***

    # Always run on the searchhead (not the indexers)
    distributed = False

    # Don't allow this to run in preview mode to limit API hits
    run_in_preview = False


    *** Method-level stuff ***

    # Log the commands given to the SPL command:
    self.logger.debug('QuoLabQueryCommand: %s', self)

    # Access metadata about the search, such as earliest_time for the selected time range
    self.metadata.searchinfo.earliest_time


    *** Runtime / testing ***

    Enable debug logging:

         | quolabquery logging_level=DEBUG ...

    """

    def __init__(self):
        # COOKIECUTTER-TODO: initialize these variables as appropriate  (url, username, max_batch_size, max_execution_time, verify)
        self.api_url = None
        self.api_username = None
        self.api_max_batch_size = None
        self.api_max_execution_time = None
        self.verify = True
        self.api_secret = None
        # self._cache = {}
        super(QuoLabQueryCommand, self).__init__()

    def prepare(self):
        super(QuoLabQueryCommand, self).prepare()
        self.logger.info("Launching version %s", __version__)
        self.logger.debug("Fetching API endpoint configurations from Splunkd (quolab_servers.conf)")

        # Determine name of stanza to load
        server_name = self.server or "default"
        try:
            api = Entity(self.service, "quolab/quolab_servers/{}".format(server_name))
        except Exception:
            self.error_exit("No known server named '{}', check quolab_servers.conf)".format(self.server),
                            "Check value provided for 'server=' option.")

        # COOKIECUTTER-TODO: Handle all variables here

        self.api_url = api["url"]
        self.api_username = api["username"]
        self.api_max_batch_size = api["max_batch_size"]
        self.api_max_execution_time = api["max_execution_time"]
        self.verify = as_bool(api["verify"])
        self.logger.debug("Entity api: %r", self.api_url)
        self.api_secret = api["secret"]
        if not self.api_secret:
            self.error_exit("Check the configuration.  Unable to fetch data from {} without secret.".format(self.api_url),
                            "Missing secret.  Did you run setup?")

    def _query_external_api(self, query_string):
        # COOKIECUTTER-TODO: Implement remote QuoLab API query here
        """ Handle the query to QuoLab API that drives this SPL command
        Returns (error, payload)
        """
        query_params = {
            "search": query_string
        }
        headers = {
            'content-type': "application/json",
            'x-api-secret': self.api_secret,
            'cache-control': "no-cache"
        }
        try:
            response = requests.request("GET", self.api_url, headers=headers, params=query_params)
        except Exception:
            self.logger.exception("Failure while calling QuoLab API")
            return ("API Call failed", {})
        result = response.json()
        if isinstance(result, dict) and "message" in result:
            return ("API returned message:  {}".format(result["message"]), result)
        elif len(result) == 0:
            result = []
        return (None, result)

    def generate(self):
        # COOKIECUTTER-TODO: Replace this code with your own generating logic
        for i in range(100):
            yield {"_raw": "Sample event {}".format(i),
                   self.output: "This is the field with a new value!",
                   "server": self.server,
                   "UNUSED_ARGUMENTS": self.fieldnames,
                   "_time": time.time()}


if __name__ == '__main__':
    dispatch(QuoLabQueryCommand, sys.argv, sys.stdin, sys.stdout, __name__)
