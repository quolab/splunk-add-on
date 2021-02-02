""" Custom REST EAI handler for the new "/quolab_server" handler.  This is a very simple wrapper granting
access to the custom "quolab_server.conf" configuration file.

Various ideas and code inspired and/or borrowed from:

 https://dev.splunk.com/enterprise/docs/devtools/customrestendpoints/customresteai/
 https://answers.splunk.com/answers/105339/how-do-i-allow-users-to-edit-credentials-using-the-setup-screen.html

A listing of the REST endpoints and their functions are provided in the top-level README.md.
"""

import splunk.admin as admin
import splunk.entity as en
import splunk.rest as rest


# So that the correct version of requests gets loaded
import os, sys
lib_dir = os.path.join(os.path.dirname(__file__), "..", "lib")
sys.path.insert(0, lib_dir)
del lib_dir, os, sys


APP_NAME = "TA-quolab"
SECRET_KEY = ":quolab_server_token__{}:"


class ConfigApp(admin.MConfigHandler):
    def __init__(self, *args, **kwargs):
        super(ConfigApp, self).__init__(*args, **kwargs)
        # Only allow certain capabilities to read/write these config settings via this endpoint
        self.capabilityRead = "read_quolab_server_config"
        self.capabilityWrite = "edit_quolab_server_config"

    def setup(self):
        '''
        Set up supported arguments
        '''
        if self.requestedAction == admin.ACTION_EDIT:
            for arg in [ 'url', 'username', 'token' ]:
                self.supportedArgs.addReqArg(arg)

    def _fetch_token(self, stanza):
        import splunk, requests, json
        url = '{}/services/quolab_server_fetch_token/{}'.format(splunk.getLocalServerInfo(), stanza)
        try:
            r = requests.post(url, verify=False,
            headers={'Authorization': 'Splunk ' + self.getSessionKey(), "Decrypt":"1"})
            content = r.text
            try:
                d = json.loads(content)
            except ValueError:
                raise ValueError("Payload is not JSON:  %r" % content)
            return d.get("token", "")
        except Exception as e:
            raise
            # raise admin.ServiceUnavailableException("{}".format(e))

    def _store_token(self, stanza, secret):
        '''
        Store the TOKEN in the storage/password endpoint to prevent unauthorized access via
        the built-in configuration and properties endpoints as well as provide on-disk encryption.
        '''
        password_name = SECRET_KEY.format(stanza)
        ### self.logger.info(" Stanza:  %s", stanza)
        url = en.buildEndpoint("storage/passwords", password_name, namespace=APP_NAME, owner="nobody")
        if rest.checkResourceExists(url, sessionKey=self.getSessionKey()):
            # Update existing password
            rest.simpleRequest(url, postargs={"password": secret},
                               sessionKey=self.getSessionKey())
        else:
            # Create new password storage entry
            url = en.buildEndpoint("storage/passwords", namespace=APP_NAME, owner="nobody")
            realm, name, _ = password_name.split(":", 3)
            rest.simpleRequest(url, postargs={"realm": realm, "name": name, "password": secret},
                               sessionKey=self.getSessionKey())

    def handleList(self, confInfo):
        confDict = self.readConf("quolab_server")
        if confDict is not None:
            for stanza, settings in confDict.items():
                for key, val in settings.items():

                    if key in ['url'] and val in [None, '']:
                        val = ''
                    confInfo[stanza].append(key, val)
                    # Fetch encrypted password from storage/passwords
                    confInfo[stanza].append("token", self._fetch_token(stanza))

    def handleEdit(self, confInfo):
        '''
        After user clicks Save on setup page, take updated parameters,
        normalize them, and save them somewhere
        '''
        stanza = self.callerArgs.id

        if self.callerArgs.data['url'][0] in [None, '']:
            self.callerArgs.data['url'][0] = ''
        # What's the stanza name here?
        if "token" in self.callerArgs.data:
            self._store_token(stanza, self.callerArgs.data["token"][0])
            # Safety/upgrade scenario.  Mask out "token" if stored directly in quolab_server.conf as this
            # value will always be accessible to the user via /services/properties/quolab_server/<stanza>/token
            # with the 'rest_properties_get' capability enabled (which is by default for the 'user' role)
            self.callerArgs.data["token"] = [ "HIDDEN" ]
        self.writeConf('quolab_server', stanza, self.callerArgs.data)


# initialize the handler
admin.init(ConfigApp, admin.CONTEXT_NONE)
