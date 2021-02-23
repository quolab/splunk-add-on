#!/usr/bin/env python
# coding=utf-8

from __future__ import absolute_import, division, print_function, unicode_literals

__version__ = "0.3.2"

import os
import sys
import re
import json
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))  # nopep8

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
    'fact': [
        'autonomous-system',
        'certificate',
        'domain',
        'email',
        'envelope',
        'file',
        'function',
        'hostname',
        'import-table',
        'ip-address',
        'mutex',
        'process',
        'registry-key',
        'url',
        'wallet',
        'export-table',
        'malware',
        'blob',
        'ttp',
        'organization',
        'persona',
        'region',
        'tor-descriptor',
        'transaction',
        'yara-rule',
    ],
    'reference': [
        'accesses',
        'contains',
        'creates',
        'identified-as',
        'loads',
        'matches',
        'relates-to',
        'signed-by',
        'receives-from',
        'sends-to',
        'delivered',
        'resolved-to',
    ],
    'annotation': [
        'attribute',
        'text',
        'interpreted-as',
        'known-as',
        'geodata',
        'report',
    ],
    'sysfact': [
        'case',
        'resource',
        'script',
        'tag',
        'timeline',
        'text',
        'user',
        'group',
        'subscription',
        'connector',
        'regulator',
        'endpoint',
    ],
    'sysref': [
        'queued',
        'scheduled',
        'executed',
        'canceled',
        'failed',
        'observed-by',
        'commented-by',
        'monitors',
        'associated-with',
        'encases',
        'tagged',
        'uses',
        'synchronized-with',
        'implies',
        'authorizes',
        'member-of',
        'produced',
    ]
}


facets = [
    'cases',
    'contributors',
    'document.magic',
    'commented',
    'document',
    'sources',
    'producers',
    'refcount',
    'vault-stored',
    'display',
    'actions',
    'endpoints',
    'latest-internal-observation',
    'tagged',
]

quolab_types = set()
quolab_class_from_type = {}

resolve_override = {
    "text": "sysfact",
}


def init():
    for class_, types in quolab_classes.items():
        for type_ in types:
            if type_ in quolab_types:
                if type_ in resolve_override:
                    class_ = resolve_override[type_]
                else:
                    # XXX: This assertion would be better as a unittest
                    raise AssertionError("Duplicate entry for {}:  {} vs {}".format(
                        type_, quolab_class_from_type[type_], class_))
            quolab_types.add(type_)
            quolab_class_from_type[type_] = class_


init()


def sanitize_fieldname(field):
    clean = re.sub(r'[^A-Za-z0-9_.{}\[\]-]', "_", field)
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
        validate=validators.Set(*facets)
    )

    # Always run on the searchhead (not the indexers)
    distributed = False

    # Don't allow this to run in preview mode to limit API hits
    run_in_preview = False

    def __init__(self):
        # COOKIECUTTER-TODO: initialize these variables as appropriate  (url, username, verify)
        self.api_url = None
        self.api_username = None
        self.api_token = None
        self.session = requests.Session()
        self.verify = True

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
            self.error_exit("Check the configuration.  Unable to fetch data from {} without token.".format(self.api_url),
                            "Missing token.  Did you run setup?")

    def _query_catalog(self, query, query_limit, max_batch_size=250):
        """ Handle the query to QuoLab API that drives this SPL command
        Returns [results]
        """
        # CATALOG QUERY
        session = self.session

        url = "{}/v1/catalog/query".format(self.api_url)
        headers = {
            'content-type': "application/json",
        }
        # XXX: Revise this logic to better handle query_limit that's within a few % of max_batch_size.
        #   Example:  if limit=501, don't query 3 x 250 records, and then throw away the 249.  Should be able to optimize per-query limit to accommodate.
        query["limit"] = query_limit if query_limit < max_batch_size else max_batch_size
        i = http_calls = 0
        while True:
            response = session.request(
                "POST", url,
                data=json.dumps(query),
                headers=headers,
                auth=HTTPBasicAuth(self.api_username, self.api_token),
                verify=self.verify)
            http_calls += 1

            body = response.json()
            if "status" in body or "message" in body:
                status = body.get("status", response.status_code)
                message = body.get("message", "")
                self.logger.error("QuoLab API returned unexpected status response from query.  "
                                  "status=%r message=%r query=%r", status, message, query)
                self.write_error("QuoLab query failed:  {} ({})", message, status)
                return

            # If a non-success exit code was returned, and the resulting object doesn't have message/status, then just raise an exception.
            response.raise_for_status()

            self.logger.debug("Response body:   %s", body)

            records = body["records"]
            for record in body["records"]:
                result = (splunk_dot_notation(record))
                result["_raw"] = json.dumps(record)
                # Q:  Are there ever fields that should be returned as _time instead of system clock time?
                result["_time"] = time.time()
                yield result
                i += 1
                if i >= query_limit:
                    break

            # XXX: Add overall timeout check
            if i >= query_limit:
                break

            ellipsis = body.get("ellipsis", None)
            if ellipsis:
                self.logger.debug("Query next batch.  i=%d, query_limit=%d, limit=%d, ellipsis=%s",
                                  i, query_limit, query["limit"], ellipsis)
                query["resume"] = ellipsis
            else:
                break
        self.logger.info("Query/return efficiency: http_calls=%d, query_limit=%d, per_post_limit=%d",
                         http_calls, query_limit, query["limit"])

    def generate(self):
        # Because the splunklib search interface does a *really* bad job a reporting exceptions / logging stack traces :-(
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

        if not "order" in query:
            # Q: Support ordering by different fields/keys?  Or require full query syntax for that?
            query["order"] = ["id", self.order]

        if self.facets:
            query.setdefault("facets", {})[self.facets] = 1

        self.write_info("Query sent to {} server: {}", self.server, json.dumps(query))
        results = self._query_catalog(query, self.limit)

        return ensure_fields(results)


def build_searchbnf(stream=sys.stdout):
    """
    >>> import quolab_query
    >>> quolab_query.build_searchbnf()
    """
    stream.write("[quolab-types]\n")
    types = []
    # Don't bother showing reference/sysref in the UI docs (to keep the list
    # from becoming too long and unreadable)
    for class_ in ["sysfact", "fact", "annotation"]:
        types.extend(quolab_classes[class_])
    stream.write("syntax = ({})\n".format("|".join(types)))

    stream.write("[quolab-facets]\n")
    stream.write("syntax = ({})\n".format("|".join(sorted(facets))))


def build_facets(data):
    """ Data from facets-serves.json

    Data structure:
    { "services" : [
        {"(type)": "quolab...ClassName",
        "id": "<name>"}
     ] }
    """
    deprecated = {"casetree", "cache-id", "indirect"}
    services = [service["id"] for service in data["services"]
                if service["id"] not in deprecated]
    return services


def build_types(data):
    """ Extract datetypes from model-types.json
    API:    /v1/catalog/model/types

    Data Structure:
    { "types: {
        "<class>: [
            {"type": "<type>"}
        ]
    }}

    data = json.load(open("model-types.json"))
    build_types(data)
    """
    deprecated = {"ipynb", "misp-blob", "source", "sink", "task", "sighted-by"}
    qlc = {}
    for class_, types in data["types"].items():
        type_names = [t["type"] for t in types if t["type"] not in deprecated]
        qlc[class_] = type_names
    # print(repr(qlc))
    return qlc


def build_from_json(output=sys.stdout):
    # TODO:  Make list output show up on the following line.   Something like:  replace(": ['", ": [\n    '").  Maybe just use json dump?
    from pprint import pprint
    pp_args = {
        "compact": False
    }
    if sys.version_info > (3, 8):
        pp_args["sort_dicts"] = False
    data = json.load(open("model-types.json"))
    qlc = build_types(data)
    output.write("quolab_classes = ")
    pprint(qlc, stream=output, **pp_args)
    output.write("\n\n")

    data = json.load(open("facet-services.json"))
    facets = build_facets(data)
    output.write("facets = ")
    pprint(facets, stream=output, **pp_args)
    output.write("\n\n")


if __name__ == '__main__':
    dispatch(QuoLabQueryCommand, sys.argv, sys.stdin, sys.stdout, __name__)
