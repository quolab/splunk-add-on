#!/usr/bin/env python
# coding=utf-8

from __future__ import absolute_import, division, print_function, unicode_literals

__version__ = "0.8.2"

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
from requests.auth import AuthBase, HTTPBasicAuth
from requests.utils import default_user_agent
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


class QuolabAuth(AuthBase):
    def __init__(self, token):
        self._token = token

    def __call__(self, request):
        request.headers['Authorization'] = "Quoken {}".format(self._token)
        return request


@Configuration()
class QuoLabQueryCommand(GeneratingCommand):
    """
    ##Syntax

    .. code-block::
        quolabquery type=X id=Y
        quolabquery type=ip-address id="1.2.3.4, 2.3.4.5"

    ##Description

    ##Example
    """

    order_param_regex = r'^(?P<order>[+-])?(?P<field>(?:[a-z_-]+\.)*[a-z_-]+)$'

    server = Option(
        require=False,
        default="quolab",
        validate=validators.Match("server", r"[a-zA-Z0-9._]+"))

    type = Option(
        require=False,
        validate=validators.Set(*quolab_types)
    )

    id = Option(
        require=False,
        validate=validators.List()
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
        default=[],
        validate=validators.List(validators.Match(name="[+-]<field>",
                                                  pattern=order_param_regex))
    )

    facets = Option(
        require=False,
        default=None,
        validate=validators.List(validator=validators.Set(*facets))
    )

    # Always run on the searchhead (not the indexers)
    distributed = False

    # Don't allow this to run in preview mode to limit API hits
    run_in_preview = False

    def __init__(self):
        self.session = requests.Session()
        self.api_url = None
        self.api_username = None
        self.verify = True
        self.api_fetch_count = None
        self.api_timeout = None
        self.api_secret = None
        super(QuoLabQueryCommand, self).__init__()

    def prepare(self):
        super(QuoLabQueryCommand, self).prepare()
        will_execute = bool(self.metadata.searchinfo.sid and
                            not self.metadata.searchinfo.sid.startswith("searchparsetmp_"))
        if will_execute:
            self.logger.info("Launching version %s", __version__)

        # Check required params based on query mode:  simple vs advanced
        if self.query and not self.type:
            self.mode = "advanced"
        elif self.type and not self.query:
            self.mode = "simple"
            # XXX:  Confirm NOT:  self.query and not self.id
        else:
            self.write_error("Must provide either 'query' or 'type' but not both")
            sys.exit(1)

        # Check to see if an unused arguments remain after argument parsing
        if self.fieldnames:
            self.write_error("The following arguments to quolabquery are "
                             "unknown:  {!r}  Please check the syntax.", self.fieldnames)
            sys.exit(1)

        if not will_execute:
            # Nothing else can be done/checked in this pre-execution mode
            return

        self.logger.debug("Fetching API endpoint configurations from Splunkd (quolab_servers.conf)")

        # Determine name of stanza to load
        try:
            api = Entity(self.service, "quolab/quolab_servers/{}".format(self.server))
        except Exception:
            self.error_exit("No known server named '{}', check quolab_servers.conf)".format(self.server),
                            "Unknown server named '{}'.  Please update 'server=' option.".format(self.server))

        self.api_url = api["url"]
        self.api_username = api["username"]
        self.api_fetch_count = int(api["max_batch_size"])
        self.api_timeout = int(api["max_execution_time"])
        self.verify = as_bool(api["verify"])
        self.logger.debug("Entity api: %r", self.api_url)
        self.api_secret = api["secret"]
        if not self.api_secret:
            self.error_exit("Check the configuration.  Unable to fetch data "
                            "from {} without secret.".format(self.api_url),
                            "Missing secret.  Did you run setup?")

    @classmethod
    def _order_to_dict(cls, order_option, query):
        """ Build the order portion of a query document given a dot-notation
        field hierarchy.  Here are a few examples:

        Order expression            JSON order syntax
            id                      {"order": [["id", "ascending"]]}
            +document.description   {"documents": {"order": [["description", "ascending"]]}}
            -document.match.type    {"documents": {"order": [["match.type", "descending"]]}}
        """
        # Note:  No test for re.match() as argument validation already occurred
        match = re.match(cls.order_param_regex, order_option)
        order = "descending" if match.group("order") == "-" else "ascending"
        field = match.group("field").split(".")
        if len(field) > 1 and field[0] not in ("document",):
            raise ValueError("Sorting fields under '{}' is not supported.  "
                             "Top-level and fields under document can be sorted."
                             .format(field[0]))
        if len(field) > 1:
            # 'document' becomes 'documents' for projection/sorting purposes
            doc = query.setdefault(field.pop(0) + "s", {})
        else:
            doc = query
        doc = doc.setdefault("order", [])
        doc.append([".".join(field), order])

    def _query_catalog(self, query, query_limit):
        """ Handle the query to QuoLab API that drives this SPL command
        Returns [results]
        """
        def monotonic():
            # PY3:  Switch to time.monotonic()
            return time.time()

        # CATALOG QUERY
        session = self.session

        start = monotonic()
        # Allow total run time to be 10x the individual query limit
        expire = start + (self.api_timeout * 10)

        url = "{}/v1/catalog/query".format(self.api_url)
        headers = {
            'content-type': "application/json",
            'user-agent': "ta-quolab/{} {}".format(__version__, default_user_agent())
        }
        # XXX: Per query limit optimization?  Maybe based on type, or number of facets enabled?
        query["limit"] = min(query_limit, self.api_fetch_count)

        # Q: What do query results look like when time has been exceeded?  Any special handling required?
        query.setdefault("hints", {})["timeout"] = self.api_timeout
        i = http_calls = 0

        if self.api_username == "<TOKEN>":
            auth = QuolabAuth(self.api_secret)
        else:
            auth = HTTPBasicAuth(self.api_username, self.api_secret)

        while True:
            data = json.dumps(query)
            self.logger.debug("Sending query to API:  %r   headers=%r auth=%s",
                              data, headers, auth.__class__.__name__)
            try:
                response = session.request(
                    "POST", url,
                    data=data,
                    headers=headers,
                    auth=auth,
                    verify=self.verify)
                http_calls += 1
            except requests.ConnectionError as e:
                self.logger.error("QuoLab API failed due to %s", e)
                self.write_error("QuoLab server connection failed to {}", url)
                return

            if response.status_code >= 400 and response.status_code < 500:
                body = response.json()
                if "status" in body or "message" in body:
                    status = body.get("status", response.status_code)
                    message = body.get("message", "")
                    self.logger.error("QuoLab API returned unexpected status response from query.  "
                                      "status=%r message=%r query=%r", status, message, query)
                    self.write_error("QuoLab query failed:  {} ({})", message, status)
                    return

            # If a non-success exit code was returned, and the resulting object doesn't have message/status, then just raise an exception.
            try:
                response.raise_for_status()
                body = response.json()
            except Exception as e:
                self.logger.debug("Body response for %s:   %s", e, response.text)
                raise

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

            if monotonic() > expire:
                self.logger.warning("Aborting query due to time expiration")
                break

            if i >= query_limit:
                break

            ellipsis = body.get("ellipsis", None)
            if ellipsis:
                self.logger.debug("Query next batch.  i=%d, query_limit=%d, limit=%d, ellipsis=%s",
                                  i, query_limit, query["limit"], ellipsis)
                query["resume"] = ellipsis
            else:
                break
        self.logger.info("Query/return efficiency: http_calls=%d, query_limit=%d, per_post_limit=%d duration=%0.3f",
                         http_calls, query_limit, query["limit"], monotonic()-start)

    def generate(self):
        # Because the splunklib search interface does a *really* bad job a reporting exceptions / logging stack traces :-(
        try:
            return self._generate()
        except Exception as e:
            self.logger.exception("Unhandled top-level exception.  To enable "
                                  "additional logging, re-run the same command "
                                  "with 'logging_level=DEBUG'.")
            self.write_error("Internal error:   {}  See internal logs for additional details.", e)
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
            if self.id:
                query["query"]["id"] = self.id

        # Build 'order' structure.   Defaults to 'id' to enable pagination
        for order in self.order or ["id"]:
            try:
                self._order_to_dict(order, query)
            except ValueError as e:
                # Abort with error to user
                self.write_error("Unable to order results based on '{}' "
                                 "because: {}", order, e)
                break

        if self.facets:
            query_facets = query.setdefault("facets", {})
            for facet in self.facets:
                query_facets[facet] = 1

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
