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




# May way to invert this
quolab_fact_from_type = {
    "ip-address" : "fact",
}


quolab_clases = {
    "sysfact" :
        {
            "case",
            "timeline"
            "connector",
            "endpoint",
            "user",
            "group",
            "tag",
        },
    "fact":
        {
            "ip-address",
            "url",
            "hostname",
            "hash"          #?  MD5 vs sha256?
            "file",
            "email",
            "domain",
        },
    "sysref":
        {
            "observed-by",
            "commented-by",
        },
    "ref":
         {

         },
}






def sanitize_fieldname(field):
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


def as_bool(s):
    return s.lower()[0] in ("t", "y", "e", "1")




@Configuration()
class QuoLabQueryCommand(GeneratingCommand):
    """
    ##Syntax

    .. code-block::
        quolab_query type=X value
        quolab_query type=ip-address value=1.2.3.4
        quolab_query type=ip-address 1.2.3.4d

    ##Description

    ##Example
    """

    server = Option(
        require=False,
        default="quolab",
        validate=validators.Match("server", r"[a-zA-Z0-9._]+"))

    type = Option(
        require=False,
        validate=validators.Set("ip-address", "url", "hostname")
    )

    value = Option(
        require=False
    )

    query = Option(
        require=False
    )

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


    *** Runtime / testing ***

    Enable debug logging:

        | quolabquery logging_level=DEBUG ...

    """

    def __init__(self):
        # COOKIECUTTER-TODO: initialize these variables as appropriate  (url,username,verify)
        self.api_url = None
        self.api_username = None
        self.api_token = None
        self.session = requests.Session()
        self.verify = False

        # self._cache = {}
        super(QuoLabQueryCommand, self).__init__()

    def prepare(self):
        super(QuoLabQueryCommand, self).prepare()
        self.logger.info("Launching version %s", __version__)


        if self.query:
            self.mode = "advanced"
        elif self.type and self.value:
            self.mode = "simple"
        else:
            self.write_error("Must provide either 'query' or both 'type' and 'value'")
            sys.exit(1)


        self.logger.debug("Fetching API endpoint configurations from Splunkd (quolab_servers.conf)")

        # Determine name of stanza to load
        try:
            api = Entity(self.service, "quolab_servers/quolab_serversendpoint/{}".format(self.server))
        except Exception:
            self.error_exit("No known server named '{}', check quolab_servers.conf)".format(self.server),
                            "Unknown server named '{}'.  Please update 'server=' option.".format(self.server))

        # COOKIECUTTER-TODO: Handle all variables here

        self.api_url = api["url"]
        self.api_username = api["username"]
        self.verify = as_bool(api["verify"])
        self.logger.debug("Entity api: %r", self.api_url)
        self.api_token = api["token"]
        if not self.api_token:
            self.error_exit("Check the configuration. Unable to fetch data from {} without token.".format(self.api_url),
                            "Missing 'token'.  Did you run setup?")

    def _query_catalog(self, query_string):
        """ Handle the query to QuoLab API that drives this SPL command
        Returns (error, results)
        """
        # CATALOG QUERY
        session = self.session

        try:
            query = json.loads(query_string)
        except ValueError as e:
            #? logger??  or not?
            self.write_error("Invalid Json:  {}".format(e), "Invalid Json")
            return

        url = "{}/v1/catalog/query".format(self.api_url)
        headers = {
            'content-type': "application/json",
        }
        response = session.request("POST", url,
                data=json.dumps(query),
                headers=headers,
                auth=HTTPBasicAuth(self.api_username, self.api_token),
                verify=self.verify)

        body = response.json()

        if "status" in body or "message" in body:
            status = body.get("status", response.status_code)
            message = body.get("message", "N/A")
            self.logger.error("Unexpected status response from query.  status=%r message=%r query=%r", status, message, query)
            self.write_error(
                "QuoLab API returned: status={} message={!r} query={!r}".format(status, message, query),
                "QuoLab query failed:  [{}]  {}}".format(status, query))
            return

        response.raise_for_status()

        # Make this debug?
        self.logger.info("Response body:   %s", body)

        # XXX:  Explict check for missing "records"  (not empty -- that's okay)

        for record in body["records"]:
            result = (splunk_dot_notation(record))
            result["_raw"] = json.dumps(record)
            result["_time"] = time.time()
            yield result


    def test01_TAGS(self):
        # TAG
        session = self.session
        url = "{}/v1/tag".format(self.api_url)
        response = session.request("GET", url,
                                   auth=HTTPBasicAuth(self.api_username, self.api_token),
                                   verify=self.verify)

        body = response.json()

        # Typical patttern
        # { "root" : [  {content}  ] }

        # Quolab query for   /v1/tags
        # { "tags: { "key" : { content }, } }
        root_name = "tags"

        # root is an object, with direct discenents

        for (tag, value) in body[root_name].items():
            item = dict(id=tag, tag=value)
            row = (splunk_dot_notation(item))
            row["_raw"] = json.dumps(item)
            row["_time"] = time.time()
            yield row

    def generate(self):

        session = requests.Session()
        #results = list(self.test01_TAGS())
        # results = list(self.test02_QUERY())



        '''
        query  = {
            "query": {
                "class": "sysfact",
                "type": "case"
            },
            "limit": 5,
            "facets": {
                "display": 1,
                "tagged": True
            }
        }
        '''

        if self.mode == "advanced":
            #results = self._query_catalog(json.dumps(query))

            query = self.query.replace("'", '"')
            results = self._query_catalog(query)

        return ensure_fields(results)


if __name__ == '__main__':
    dispatch(QuoLabQueryCommand, sys.argv, sys.stdin, sys.stdout, __name__)
