""" QuoLab Add on for Splunk share code for QuoLab API access
"""

import json
import re
import ssl
import time
from logging import getLogger
from threading import Event, Thread

import requests

from cypresspoint.spath import splunk_dot_notation
from requests.auth import AuthBase, HTTPBasicAuth
from requests.utils import default_user_agent

try:
    from time import monotonic
except ImportError:
    # Good-enough fallback for PY2 users
    from time import time as monotonic

from . import __version__

logger = getLogger("quolab.common")


""" http debug logging
import logging
from http.client import HTTPConnection  # py3

log = logging.getLogger('urllib3')
log.setLevel(logging.DEBUG)
"""


class QuolabAuth(AuthBase):
    def __init__(self, token):
        self._token = token

    def __call__(self, request):
        request.headers['Authorization'] = "Quoken {}".format(self._token)
        return request


class QuoLabAPI(object):
    base_headers = {
        "Accept": "application/json",
    }

    def __init__(self, url, verify=None):
        self.session = requests.Session()
        self.token = None
        self.username = None
        self.password = None
        self.url = url
        self.verify = verify
        if verify is False:
            import urllib3
            urllib3.disable_warnings()
            logger.info("SSL Certificate validation has been disabled.")

    def login(self, username, password):
        self.username = username
        self.password = password
        self.token = None

    def login_token(self, token):
        self.token = token
        self.username = None
        self.password = None

    def get_auth(self):
        if self.token:
            auth = QuolabAuth(self.token)
        else:
            auth = HTTPBasicAuth(self.username, self.password)
        return auth

    '''
    def _call(self, method, partial_url, params=None, data=None, headers=None):
        h = dict(self.base_headers)
        if headers is not None:
            h.update(headers)
        # print("Headers:  {!r}".format(headers))
        r = self.session.request(method, self.url + partial_url, params, data, h,
                                 auth=HTTPBasicAuth(self.username, self.password),
                                 verify=self.verify)
        return r

    def _paginated_call(self, session, method, partial_url, params=None, data=None, headers=None):
        h = dict(self.base_headers)
        if headers is not None:
            h.update(headers)
        session.request(method, self.url + partial_url, params=params, data=data, headers=h,
                        auth=HTTPBasicAuth(self.username, self.password),
                        verify=self.verify)
    '''

    def get_timeline_events(self, timeline_id, facets=None):
        """ Call /v1/timeline/<timeline_id>/event to return events within the timeline's buffer. """
        # https://node77.cloud.quolab.com/v1/timeline/51942b79b8b34827bf721077fa22a590/event?facets.display=1
        url = "{}/v1/timeline/{}/event".format(self.url, timeline_id)
        if facets is None:
            facets = ["display"]

        headers = {
            'content-type': "application/json",
            'user-agent': "ta-quolab/{} {}".format(__version__, default_user_agent())
        }
        data = {}
        for facet in facets:
            data["facets.{}".format(facet)] = 1
        auth = self.get_auth()

        try:
            response = self.session.request(
                "GET", url,
                data=data,
                headers=headers,
                auth=auth,
                verify=self.verify)
        except requests.ConnectionError as e:
            logger.error("QuoLab API failed due to %s", e)

        response.raise_for_status()
        try:
            data = response.json()
        except ValueError as e:
            raw = response.content
            content_length = len(raw)
            logger.error("QuoLab API response could not be parsed.  url=%s content-length=%d  %s",
                         url, content_length, e)
            logger.debug("QuoLab API raw response: url=%s \n%s", url, raw)
            raise
        # debugging
        logger.info("QuoLab API response was parsed as json successfully!")
        assert data["status"] == "OK"

        for record in data.get("records", []):
            yield record

    def subscribe_timeline(self, recv_message_callback, timeline_id, facets=None):
        # if facets is None:
        #   facets = {}
        qws = QuoLabWebSocket(self.url, self.get_auth(), timeline_id,
                              recv_message_callback, self.verify)

        # Run server_forever() in it's own thread, so we can return to the caller
        # thread.start_new_thread(qws.connect, ())
        # Python 3 use:  Thread(target=qws.connect, daemon=True).start()
        t = Thread(target=qws.connect)
        t.daemon = True
        t.start()

        if not qws.is_setup.wait(15):
            logger.error("Too too long to setup websocket to {}", self.url)
            # XXX: Trigger a clean shutdown
            raise SystemExit(3)

        return qws

    def query_catalog(self, query, query_limit, timeout=30, fetch_count=1000, write_error=None):
        """ Handle the query to QuoLab API that drives this SPL command
        Returns [results]
        """
        if write_error is None:
            def write_error(s, *args, **kwargs): pass

        # XXX:  COMPLETE MIGRATION OF THIS METHOD!!
        # XXX:  REPLACE THIS CODE IN quolab_query.py

        # CATALOG QUERY
        session = self.session

        start = monotonic()
        # Allow total run time to be 10x the individual query limit
        expire = start + (timeout * 10)

        url = "{}/v1/catalog/query".format(self.url)
        headers = {
            'content-type': "application/json",
            'user-agent': "ta-quolab/{} {}".format(__version__, default_user_agent())
        }
        # XXX: Per query limit optimization?  Maybe based on type, or number of facets enabled?
        query["limit"] = min(query_limit, fetch_count)

        # Q: What do query results look like when time has been exceeded?  Any special handling required?
        query.setdefault("hints", {})["timeout"] = timeout
        i = http_calls = 0

        auth = self.get_auth()

        while True:
            data = json.dumps(query)
            logger.debug("Sending query to API:  %r   headers=%r auth=%s",
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
                logger.error("QuoLab API failed due to %s", e)
                write_error("QuoLab server connection failed to {}", url)
                return

            if response.status_code >= 400 and response.status_code < 500:
                body = response.json()
                if "status" in body or "message" in body:
                    status = body.get("status", response.status_code)
                    message = body.get("message", "")
                    logger.error("QuoLab API returned unexpected status response from query.  "
                                 "status=%r message=%r query=%r", status, message, query)
                    write_error("QuoLab query failed:  {} ({})", message, status)
                    return

            # When non-success status code without a message/status, then just raise an exception.
            try:
                response.raise_for_status()
                body = response.json()
            except Exception as e:
                logger.debug("Body response for %s:   %s", e, response.text)
                raise

            logger.debug("Response body:   %s", body)

            records = body["records"]
            for record in records:
                result = (splunk_dot_notation(record))
                result["_raw"] = json.dumps(record)
                # Q:  Are there ever fields that should be returned as _time instead of system clock time?
                result["_time"] = time.time()
                yield result
                i += 1
                if i >= query_limit:
                    break

            if monotonic() > expire:
                logger.warning("Aborting query due to time expiration")
                break

            if i >= query_limit:
                break

            ellipsis = body.get("ellipsis", None)
            if ellipsis:
                logger.debug("Query next batch.  i=%d, query_limit=%d, limit=%d, ellipsis=%s",
                             i, query_limit, query["limit"], ellipsis)
                query["resume"] = ellipsis
            else:
                break
        logger.info("Query/return efficiency: http_calls=%d, query_limit=%d, per_post_limit=%d duration=%0.3f",
                    http_calls, query_limit, query["limit"], monotonic()-start)


class QuoLabWebSocket(object):

    def __init__(self, url, auth, timeline, message_callback, verify):
        self.url = url
        self.auth = auth
        self.timeline = timeline
        self.message_callback = message_callback
        self.verify = verify
        self.is_done = Event()
        self.is_setup = Event()

    @staticmethod
    def _convert_request_auth_headers(auth):
        class C(object):
            pass
        o = C()
        o.headers = {}
        auth(o)
        return o.headers

    def connect(self):
        import websocket
        auth_header = self._convert_request_auth_headers(self.auth)
        ws_url = "{}/v1/socket".format(re.sub('^http', 'ws', self.url))
        logger.info("WEB socket URL = %s", ws_url)
        ws = websocket.WebSocketApp(ws_url,
                                    header=auth_header,
                                    on_message=self.on_message,
                                    on_error=self.on_error,
                                    on_open=self.on_open,
                                    on_close=self.on_close)
        kw = {}
        if self.verify is False:

            kw["sslopt"] = {"cert_reqs": ssl.CERT_NONE}
        # Set ping_interval to cause enable_multithread=True in WebSocket() constructor
        ws.run_forever(ping_interval=90, ping_timeout=10, **kw)

    def on_message(self, ws, msg):
        j = json.loads(msg)
        msg_formatted = json.dumps(j, indent=4)
        # XXX: Remove the following debug message after initial development
        logger.debug('[Websocket Message]\n%s', msg_formatted)
        event_name = j.get('name')

        if event_name == "event":
            self.message_callback(j)
            return

        if event_name == "bound":
            logger.info("Websocket bound to %s", j["cid"])
        else:
            logger.info("Unknown '%s', message not ingested:  %s", event_name, msg_formatted)

        '''
        # Indexing the rest
        try:
            t = float(j['body']['data']['document']['first:Min'])
            j['body']['data']['document']['first:Min'] = int(t * 1000)
            t = float(j['body']['data']['document']['last:Max'])
            j['body']['data']['document']['last:Max'] = int(t * 1000)
            t = float(j['body']['timestamp'])
            j['body']['timestamp'] = int(t * 1000)
        except:
            return
        '''

    def on_error(self, ws, err):
        logger.error("[Websocket Error] %s", err)
        # Q:  Does this always/automatically trigger a shutdown?  Should it?

    def _build_bind_request(self, facets=None):
        if facets is None:
            facets = ["display"]
        doc = {
            "attach": {
                "ns": "activity-stream",
                "name": "event",
                "cid": self.timeline,
            },
            "body": {
                "composition": {
                    "catalog": {
                        "facets": {},
                        "object": "object"
                    }
                }
            },
            "cid": "activity-stream-event-{}".format(self.timeline),
            "name": "bind",
            "ns": "link/binding"
        }
        for facet in facets:
            doc["body"]["composition"]["catalog"]["facets"][facet] = True
        return doc

    def on_open(self, ws):
        logger.debug("[Websocket Open].   Request timeline=%s", self.timeline)

        def run(*args):
            req = self._build_bind_request()   # XXX:  Support facets here!
            logger.debug("[Websocket Open:run()] Request payload:  %s", req)
            ws.send(json.dumps(req))
            self.is_setup.set()

        import _thread as thread
        thread.start_new_thread(run, ())
        # Thread(target=run).start()

    def on_close(self, ws):
        ws.close()
        logger.info('[Websocket Closed]')
        self.is_done.set()
