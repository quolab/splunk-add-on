""" Custom REST EAI handler for the new "/quolab/quolab_servers" handler.  This is a very simple wrapper granting
access to the custom "quolab_servers.conf" configuration file with secret values.

A listing of the REST endpoints and their functions are provided in the top-level README.md.
"""


import splunk
import splunk.admin as admin
import splunk.entity as en
import splunk.rest as rest

# Manipulate python path to ensure the correct version of 'requests' gets loaded
import os
import sys
lib_dir = os.path.join(os.path.dirname(__file__), "..", "lib")
sys.path.insert(0, lib_dir)
del lib_dir, os, sys
APP_NAME = "TA-quolab"
SECRET_KEY = ":quolab_servers_secret__{}:"

FIELD_NAMES = [
    "url",
    "username",
    "max_batch_size",
    "max_execution_time",
    "verify"
]


class ConfigApp(admin.MConfigHandler):
    def __init__(self, *args, **kwargs):
        super(ConfigApp, self).__init__(*args, **kwargs)
        # Only allow certain capabilities to read/write these config settings via this endpoint
        self.capabilityRead = "read_quolab_servers_config"
        self.capabilityWrite = "edit_quolab_servers_config"

    def setup(self):
        '''
        Set up supported arguments
        '''
        if self.requestedAction == admin.ACTION_EDIT:
            for arg in FIELD_NAMES:
                self.supportedArgs.addReqArg(arg)
            self.supportedArgs.addOptArg("secret")

    def _fetch_secret(self, stanza):
        import requests
        import json
        url = '{}/services/quolab/quolab_servers_secret/{}'.format(
            splunk.getLocalServerInfo(), stanza)
        try:
            r = requests.post(url, verify=False, headers={
                'Authorization': 'Splunk ' + self.getSessionKey(),
                "Decrypt": "1"})
            content = r.text
            try:
                d = json.loads(content)
            except ValueError:
                raise ValueError("Payload is not JSON:  %r" % content)
            return d.get("secret", "")
        except Exception as e:
            raise
            # raise admin.ServiceUnavailableException("{}".format(e))

    def _store_secret(self, stanza, secret):
        '''
        Store the SECRET in the storage/password endpoint to prevent unauthorized access via
        the built-in configuration and properties endpoints as well as provide on-disk encryption.
        '''
        password_name = SECRET_KEY.format(stanza)
        ### self.logger.info(" Stanza:  %s", stanza)
        url = en.buildEndpoint("storage/passwords", password_name,
                               namespace=APP_NAME, owner="nobody")
        if rest.checkResourceExists(url, sessionKey=self.getSessionKey()):
            # Check to see if and updated secret was provided.  If not, assume no password change was desired
            if secret:
                # Update existing password
                rest.simpleRequest(url, postargs={"password": secret},
                                   sessionKey=self.getSessionKey())
        else:
            if not secret:
                raise admin.ArgValidationException(
                    "New quolab_servers entries require a value for 'secret'")
            # Create new password storage entry
            url = en.buildEndpoint("storage/passwords", namespace=APP_NAME, owner="nobody")
            realm, name, _ = password_name.split(":", 3)
            rest.simpleRequest(url, postargs={"realm": realm, "name": name, "password": secret},
                               sessionKey=self.getSessionKey())

    def _remove_secret(self, stanza):
        password_name = SECRET_KEY.format(stanza)
        url = en.deleteEntity("storage/passwords", password_name, namespace=APP_NAME, owner="nobody",
                              sessionKey=self.getSessionKey())

    def handleList(self, confInfo):
        confDict = self.readConf("quolab_servers")
        if confDict is not None:
            for stanza, settings in confDict.items():
                for key, val in settings.items():
                    if key in FIELD_NAMES and val in [None, '']:
                        val = ''
                    confInfo[stanza].append(key, val)
                    # Fetch encrypted password from storage/passwords
                    confInfo[stanza].append("secret", self._fetch_secret(stanza))

    def handleEdit(self, confInfo):
        '''
        After user clicks Save on setup page, take updated parameters,
        normalize them, and save them somewhere
        '''
        stanza = self.callerArgs.id

        if self.callerArgs.data['url'][0] in [None, '']:
            self.callerArgs.data['url'][0] = ''
        # What's the stanza name here?
        if "secret" in self.callerArgs.data:
            self._store_secret(stanza, self.callerArgs.data["secret"][0])
            # Safety/upgrade scenario.  Mask out "secret" if stored directly in quolab_servers.conf as this
            # value will always be accessible to the user via /services/properties/quolab_servers/<stanza>/secret
            # with the 'rest_properties_get' capability enabled (which is by default for the 'user' role)
            self.callerArgs.data["secret"] = ["HIDDEN"]
        self.writeConf('quolab_servers', stanza, self.callerArgs.data)

    def handleRemove(self, confInfo):
        stanza = self.callerArgs.id
        try:
            en.deleteEntity("configs/conf-quolab_servers", stanza,
                            namespace=APP_NAME, owner="nobody", sessionKey=self.getSessionKey())
            self._remove_secret(stanza)
        except splunk.ResourceNotFound:
            # If already deleted, silently ignore
            pass


# initialize the handler
admin.init(ConfigApp, admin.CONTEXT_NONE)
