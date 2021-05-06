
import json
import re
from logging import getLogger

import requests
import six

try:
    import thread
except ImportError:
    import _thread as thread

from cypresspoint.datatype import as_bool
from cypresspoint.searchcommand import ensure_fields
from requests.auth import AuthBase, HTTPBasicAuth
from requests.utils import default_user_agent

logger = getLogger("quolab.common")


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
        if facets is None:
            facets = {}
        #r = self._paginated_call("GET", "/api/v99/blah/blah")
        # return r

    def subscribe_timeline(self, recv_message_callback, timeline_id, facets=None):
        # if facets is None:
        #   facets = {}

        qws = QuoLabWebSocket(self.url, self.get_auth(), timeline_id, recv_message_callback)

        # XXX:  Figure out alternates to run_forever()?  Background launch?
        qws.connect()

    def query_catalog(self, query, query_limit):
        """ Handle the query to QuoLab API that drives this SPL command
        Returns [results]
        """
        # XXX:  COMPLETE MIGRATION OF THIS METHOD!!
        # XXX:  REPLACE THIS CODE IN quolab_query.py

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

        auth = self.get_auth()

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


class QuoLabWebSocket(object):

    def __init__(self, url, auth, timeline, message_callback):
        self.url = url
        self.auth = auth
        self.timeline = timeline
        self.message_callback = message_callback

    @staticmethod
    def _convert_request_auth_headers(auth):
        class C(object):
            pass
        o = C()
        o.headers = {}
        auth(o)
        return "Authorization: {}".format(o.headers["Authorization"])

    def connect(self):
        import websocket
        auth_header = self._convert_request_auth_headers(self.auth)
        ws_url = "{}/v1/socket".format(re.sub('^http', 'ws', self.url))
        logger.info("WEB socket URL = %s", ws_url)
        ws = websocket.WebSocketApp(ws_url,
                                    header=[auth_header],
                                    on_message=self.on_message,
                                    on_error=self.on_error,
                                    on_open=self.on_open,
                                    on_close=self.on_close)
        ws.run_forever()

    def on_message(self, ws, msg):
        j = json.loads(msg)
        logger.debug('[Websocket Message]\n%s', json.dumps(j, indent=4))

        if j['name'] != 'event':
            return

        # XXX:  CUSTOM CALLBACK HAPPENS HERE!!!

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
        self.message_callback(j)

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
            logger.debug("Request payload:  %s", req)
            ws.send(json.dumps(req))
        thread.start_new_thread(run, ())

    def on_close(self, ws):
        ws.close()
        logger.info('[Websocket Closed]')
