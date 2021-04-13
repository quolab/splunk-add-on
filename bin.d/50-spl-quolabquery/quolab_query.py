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
        default="quolab",
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
        super(QuoLabQueryCommand, self).__init__()
        # COOKIECUTTER-TODO: initialize any custom variables in __init__()

    def prepare(self):
        super(QuoLabQueryCommand, self).prepare()
        # COOKIECUTTER-TODO: Customize or DELETE prepare() - arg validation & REST/CONF fetch

        will_execute = bool(self.metadata.searchinfo.sid and
                            not self.metadata.searchinfo.sid.startswith("searchparsetmp_"))
        if will_execute:
            self.logger.info("Launching version %s", __version__)

        ''' COOKIECUTTER-TODO: Enable/delete: this block of code will prevent unused/unknown paramaters
        # Check to see if an unused arguments remain after argument parsing
        if self.fieldnames:
            self.write_error("The following arguments to quolabquery are "
                             "unknown:  {!r}  Please check the syntax.", self.fieldnames)
            sys.exit(1)
        '''
        # COOKIECUTTER-TODO:  Implement argument validation here, if needed

        if not will_execute:
            return
        # COOKIECUTTER-TODO:  Add custom REST endpoint/conf snippet here, if needed

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
            'x-api-auth': self.api_auth,
            'cache-control': "no-cache"
        }
        try:
            response = requests.request("GET", self.api_url, headers=headers, params=query_params)
        except requests.ConnectionError as e:
            self.logger.error("Aborting due to API connection failure.  %s", e)
            return ("QuoLab Connection failure:  {}".format(e), [])
        except Exception:
            self.logger.exception("Failure while calling API")
            return ("QuoLab API Call failed", [])
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
