#!/usr/bin/env python
# coding=utf-8

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))  # nopep8

from cypresspoint.datatype import as_bool
from cypresspoint.searchcommand import ensure_fields
from splunklib.client import Entity, HTTPError
from splunklib.searchcommands import (Configuration, GeneratingCommand, Option,
                                      dispatch, validators)
from ta_quolab import __version__
from ta_quolab.api import QuoLabAPI
from ta_quolab.const import facets, quolab_class_from_type, quolab_types


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
        self.quolab_api = None
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
            api = Entity(self.service, "quolab/quolab_servers/{}/full".format(self.server))
        except HTTPError:
            self.error_exit("No known server named '{}', check quolab_servers.conf".format(self.server),
                            "Unknown server named '{}'.  Please update 'server=' option.".format(self.server))
        except Exception as e:
            self.logger.exception("Unhandled exception: ")
            self.write_error("Aborting due to internal error:  {}", e)

        self.api_url = api["url"]
        self.api_username = api["username"]
        self.api_fetch_count = int(api["max_batch_size"])
        self.api_timeout = int(api["max_execution_time"])
        self.verify = as_bool(api["verify"])
        if not self.verify:
            import urllib3
            urllib3.disable_warnings()
        self.logger.debug("Entity api: %r", self.api_url)
        self.api_secret = api["secret"]
        if not self.api_secret:
            self.error_exit("Check the configuration.  Unable to fetch data "
                            "from {} without secret.".format(self.api_url),
                            "Missing secret.  Did you run setup?")

        # Setup quolab interface
        self.quolab_api = QuoLabAPI(self.api_url, verify=self.verify)
        if self.api_username == "<TOKEN>":
            self.quolab_api.login_token(self.api_secret)
        else:
            self.quolab_api.login(self.api_username, self.api_secret)

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
        # Return generator function
        return self.quolab_api.query_catalog(query, query_limit,
                                             timeout=self.api_timeout,
                                             fetch_count=self.api_fetch_count,
                                             write_error=self.write_error)

    def generate(self):
        # Because the splunklib search interface does a bad job a reporting exceptions / logging stack traces :-(
        try:
            return self._generate()
        except Exception as e:
            self.logger.exception("Unhandled top-level exception.  To enable "
                                  "additional logging, re-run the same command "
                                  "with 'logging_level=DEBUG'.")
            self.write_error("Internal error:   {}  See internal logs for additional details.", e)
            sys.exit(1)

    def _generate(self):

        if self.mode == "advanced":
            query = self.query.replace("'", '"')
            try:
                query = json.loads(query)
            except ValueError as e:
                self.logger.info("Invalid JSON given as input.  %s  Input:\n%s", e, query)
                self.write_error("Invalid JSON:  {}", e)
                sys.exit(1)

            # Force use of a top-level 'query' for consistant querying
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


if __name__ == '__main__':
    dispatch(QuoLabQueryCommand, sys.argv, sys.stdin, sys.stdout, __name__)
