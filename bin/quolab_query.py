#!/usr/bin/env python
# coding=utf-8

from __future__ import absolute_import, division, print_function, unicode_literals

__version__ = "0.1.0"

import os
import sys
import re
import json
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

import six
import requests
from requests.auth import HTTPBasicAuth
from splunklib.client import Entity
from splunklib.searchcommands import dispatch, GeneratingCommand, Configuration, Option, validators



""" http debug loggig
import logging
from http.client import HTTPConnection  # py3

log = logging.getLogger('urllib3')
log.setLevel(logging.DEBUG)
"""




def sanitize_fieldname(field):
    # XXX: Add caching, if needed
    clean = re.sub(r'[^A-Za-z0-9_.{}\[\]]', "_", field)
    # Remove leading/trailing underscores
    clean = clean.strip("_")
    return clean


def dict_to_splunk_fields(obj, prefix=()):
    """
    Input:  Object   (dict, list, str/int/float)
    Output:  [  ( (name,name), value) ]

    Convention:  Arrays suffixed with "{}"
    """
    output = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            key = sanitize_fieldname(key)
            output.extend(dict_to_splunk_fields(value, prefix=prefix+(key,)))
    elif isinstance(obj, (list, list)):
        if prefix:
            prefix = prefix[:-1] + (prefix[-1] + "{}",)
            for item in obj:
                output.extend(dict_to_splunk_fields(item, prefix=prefix))
    elif isinstance(obj, bool):
        output.append((prefix, "true" if obj else "false"))
    elif isinstance(obj, (str, int, float)) or obj is None:
        output.append((prefix, obj))
    else:
        raise TypeError("Unsupported datatype {}".format(type(obj)))
    return output


def splunk_dot_notation(obj):
    d = {}
    if not isinstance(obj, dict):
        raise ValueError("Expected obj to be a dictionary, received {}".format(type(obj)))
    for field_pair, value in dict_to_splunk_fields(obj):
        field_name = ".".join(field_pair)
        if field_name in d:
            if not isinstance(d[field_name], list):
                d[field_name] = [d[field_name]]
            d[field_name].append(value)
        else:
            d[field_name] = value
    return d




def ensure_fields(results):
    """ Ensure that the first result has a placeholder for *ALL* the fields """
    field_set = set()
    output = []
    for result in results:
        field_set.update(result.keys())
        output.append(result)
    if output:
        # Apply *all* fields to the first result; all other rows are left alone
        output[0] = {k: output[0].get(k, None) for k in field_set}
    return output


@Configuration()
class QuoLabQueryCommand(GeneratingCommand):
    """

    ##Syntax

    .. code-block::
        quolabquery field=input

    ##Description

    ##Example
    """
    server = Option(
        requred=False,
        validate=validators.Match("[a-zA-Z0-9._]+"))

    output = Option(
        require=True,
        validate=validators.Fieldname())

    field_set = Option(
        require=True,
        validate=validators.Set("a", "b", "c"))

    field_int = Option(
        require=False,
        default=32,
        validate=validators.Integer(1,128))

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

    # Access metadata about the search, such as earliset_time for the selected time range
    self.metadata.searchinfo.earliest_time
    """

    def __init__(self):
        # COOKIECUTTER-TODO: initialize these variables as appropriate  (url,username)
        self.api_url = None
        self.api_username = None
        self.api_token = None
        # self._cache = {}
        super(QuoLabQueryCommand, self).__init__()

    def prepare(self):
        super(QuoLabQueryCommand, self).prepare()
        self.logger.info("Launching version %s", __version__)
        self.logger.debug("Fetching API endpoint configurations from Splunkd (quolab_server.conf)")

        # Determine name of stanza to load
        server_name = self.server or "default"
        api = Entity(self.service, "quolab_server/quolab_serverendpoint/{}".format(server_name))
        # COOKIECUTTER-TODO: Handle all varaibles here

        self.api_url = api["url"]
        self.api_username = api["username"]
        self.logger.debug("Entity api: %r", api["url"])
        self.api_token = api["token"]
        if not self.api_token:
            self.error_exit("Missing api_token.  Did you run setup?",
                            "Check the configuration.  Unable to fetch data with token.")

    def _query_external_api(self, query_string):
        # COOKIECUTTER-TODO: Implement remote QuoLab API query here
        """ Handle the query to QuoLab API that drives this SPL command
        Returns (error, payload)
        """
        query_params = {
            "search" : query_string
        }
        headers = {
            'content-type': "application/json",
            'x-api-token': self.api_token,
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
        for i in range(100):
            yield { "_raw": "Sample event {}".format(i),
                    self.output: "This is the field with a new value!",
                    "_time" : time.time()}





if __name__ == '__main__':
    dispatch(QuoLabQueryCommand, sys.argv, sys.stdin, sys.stdout, __name__)
