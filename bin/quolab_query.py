#!/usr/bin/env python
# coding=utf-8

from __future__ import absolute_import, division, print_function, unicode_literals

__version__ = "0.2.1"

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



""" http debug logging
import logging
from http.client import HTTPConnection  # py3

log = logging.getLogger('urllib3')
log.setLevel(logging.DEBUG)
"""


quolab_classes = {
    "sysfact": {
        "case",
        "timeline"
        "connector",
        "endpoint",
        "user",
        "group",
        "tag",
    },
    "fact":  {
        "ip-address",
        "url",
        "hostname",
        "hash"  # ?  MD5 vs sha256?
        "file",
        "email",
        "domain",
    },
    "sysref": {
        "observed-by",
        "commented-by",
    },
    "ref": {
    },
}
quolab_types = set()
quolab_class_from_type = {}


def init():
    for class_, types in quolab_classes.items():
        for type_ in types:
            # XXX: This assertion would be better as a unittest
            assert type_ not in quolab_types, \
                "Duplicate entry for {}:  {} vs {}".format(type_, quolab_class_from_type[type_], class_)
            quolab_types.add(type_)
            quolab_class_from_type[type_] = class_
init()


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
    """
    Convert json object (python dictionary) into a list of fields as Splunk does by default.
    Think of this as the same as calling Splunk's "spath" SPL command.
    """
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
        validate=validators.Set(*quolab_types)
    )

    value = Option(
        require=False
    )

    query = Option(
        require=False
    )

    limit = Option(
        require=False,
        default=100,
        validate=validators.Integer(1, 100000)
    )

    order = Option(
        require=False,
        default="ascending",
        # XXX: Find out what the API values are legit:
        validate=validators.Set("ascending", "descending")
    )

    # XXX:  Figure out a way to accept multiple values here:  comma sep?
    facets = Option(
        require=False,
        default=None,
        validate=validators.Set("display", "tagged", "actions", "sources")
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

        if self.query and not self.type:
            self.mode = "advanced"
        elif self.type and not self.query:
            self.mode = "simple"
            # XXX:  Confirm NOT:  self.query and not self.value
        else:
            self.write_error("Must provide either 'query' or 'type' but not both")
            sys.exit(1)

        self.logger.debug("Fetching API endpoint configurations from Splunkd (quolab_servers.conf)")

        # Determine name of stanza to load
        try:
            api = Entity(self.service, "quolab_servers/quolab_serversendpoint/{}".format(self.server))
        except Exception:
            self.error_exit("No known server named '{}', check quolab_servers.conf)".format(self.server),
                            "Unknown server named '{}'.  Please update 'server=' option.".format(self.server))

        self.api_url = api["url"]
        self.api_username = api["username"]
        self.verify = as_bool(api["verify"])
        self.logger.debug("Entity api: %r", self.api_url)
        self.api_token = api["token"]
        if not self.api_token:
            self.error_exit("Check the configuration. Unable to fetch data from {} without token.".format(self.api_url),
                            "Missing 'token'.  Did you run setup?")

    def _query_catalog(self, query):
        """ Handle the query to QuoLab API that drives this SPL command
        Returns [results]
        """
        # CATALOG QUERY
        session = self.session

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
            message = body.get("message", "")
            self.logger.error("QuoLab API returned unexpected status response from query.  status=%r message=%r query=%r", status, message, query)
            self.write_error("QuoLab query failed:  {} ({})", message, status)
            return

        # If a non-sucess exit code was returned, and the resulting object doesn't have message/status, then just raise an execption.
        response.raise_for_status()

        self.logger.debug("Response body:   %s", body)

        # XXX:  Add explict check for missing "records"  (not empty -- that's okay)
        for record in body["records"]:
            result = (splunk_dot_notation(record))
            result["_raw"] = json.dumps(record)
            # Q:  Are there ever fields that should be returned as _time instead of system clock time?
            result["_time"] = time.time()
            yield result

    '''
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
    '''


    def generate(self):
        try:
            return self._generate()
        except Exception:
            self.logger.exception("Unhandled top-level exception")
            sys.exit(1)

    def _generate(self):
        session = requests.Session()

        if self.mode == "advanced":
            query = self.query.replace("'", '"')
            try:
                query = json.loads(query)
            except ValueError as e:
                self.logger.info("Invalid JSON given as input.  %s  Input:\n%s", e, query)
                self.write_error("Invalid JSON:  {}", e)
                sys.exit(1)

            # Handle scenario where top-level 'query' is provided.  Otherwise, assume given content should be placed under 'query'
            # The QuoLab API handles this either way, but to add limit and facets an explicit 'query' must be present.
            if "query" not in query:
                query = {"query": query}

        elif self.mode == "simple":
            try:
                class_ = quolab_class_from_type[self.type]
            except KeyError:
                self.write_error("No class known for type={}", self.type)
                sys.exit(1)

            query = {
                "query": {
                    "class": class_,
                    "type": self.type,
                }
            }
            # XXX:  Support multiple values
            if self.value:
                query["query"]["id"] = self.value

        if self.limit:
            query["limit"] = self.limit
        if not "order" in query:
            # Q: Support ordering by different fields/keys?  Or require full query syntax for that?
            query["order"] = ["id", self.order]

        if self.facets:
            query.setdefault("facets", {})[self.facets] = 1

        results = self._query_catalog(query)

        return ensure_fields(results)


def build_searchbnf(stream=sys.stdout):
    """
    >>> import quolab_query
    >>> quolab_query.build_searchbnf()
    """
    stream.write("[quolab-types]\n")
    stream.write("syntax = ({})\n".format("|".join(sorted(quolab_types))))


if __name__ == '__main__':
    dispatch(QuoLabQueryCommand, sys.argv, sys.stdin, sys.stdout, __name__)
