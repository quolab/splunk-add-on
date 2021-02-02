"""
This REST handler is a password fetching workaround for the /quolab_servers endpoint.  This endpoint simply
returns the token (password) for non-admin users.

Starting in Splunk 6.5 reading from /storage/passsword requires the "list_storage_passwords"
capability, however doing so grants the rights to read ANY password for any app.  Prior to 6.5,
reading a password required the "admin_all_objects" capability, which also allows for full-control
of control of ALL objects (bypassing all typical ACL restrictions).  As of Splunk 7.0 there is no
ACL support on individual passwords (unlike most other knowledge objects)

This rest endpoint safely gets around the above limitations by:
  1.)  Using the "passSystemAuth" rest script option to essentially gain access to the
        splunk-system-user account, which isn't an option for custom admin_external REST endpoints.
  2.)  Setting the "capability" settings to limit access to the specific capability assigned
       to specific roles, which are assigned to a limited number of users.


XXX:  Ideally this endpoint should be written as a drop-in replacement for the EAI /quolab_servers endpoint,
      but hand-coding a EAI endpoint is unlikely to be worth the effort.  So for now, this code ONLY
      does one thing, and we have extra internal API calls for every invocation of quolabquery.


Docs:

"""

APP_NAME = "TA-quolab"
SECRET_KEY = ":quolab_servers_token__{}:"

import json

import splunk.entity as en
from splunk import AuthorizationFailed
from splunk.persistconn.application import PersistentServerConnectionApplication


class Quolab_serversSettingsHandler(PersistentServerConnectionApplication):

    def __init__(self, command_line, command_arg):
        del command_line, command_arg
        PersistentServerConnectionApplication.__init__(self)

    @staticmethod
    def _get_session_context(sessionKey):
        e = en.getEntity(["authentication"], "current-context", sessionKey=sessionKey)
        d = {}
        for field in "title roles realname email capabilities".split():
            d[field] = e[field]
        return d

    def _fetch_token(self, stanza, sessionKey, decrypt=True):
        try:
            e = en.getEntity(["storage", "passwords"], SECRET_KEY.format(stanza), namespace=APP_NAME,
                             owner="-", sessionKey=sessionKey)
        except AuthorizationFailed:
            # XXX:  Is there a more appropriate exception to raise?
            raise ValueError("Authentication failed when fetching token.   SessionContext=%s" %
                             self._get_session_context(sessionKey))
        if e:
            if decrypt:
                return e["clear_password"]
            else:
                return e["password"]
        else:
            return ""

    def handle(self, in_string):
        request = json.loads(in_string)
        response = {}
        # Simple header trick to keep prevent the password from being leaked via "rest" SPL command.
        do_decrypt = False
        for (header, value) in request.get("headers", []):
            if header.lower() == "decrypt" and value == "1":
                do_decrypt = True
        stanza = request["path_info"]
        response["stanza"] = stanza
        sessionKey = request.get("system_authtoken", request["session"]["authtoken"])
        try:
            response["token"] = self._fetch_token(stanza, sessionKey, do_decrypt)
            status = 200
        except Exception as e:
            response["error"] = "{}".format(e)
            status = 500
        response["decrypt"] = do_decrypt
        return {'payload' : response,
                'status': status        # HTTP status code
        }
