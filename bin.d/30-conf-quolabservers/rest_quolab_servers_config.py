""" Custom REST EAI handler for the new "/quolab/quolab_servers" handler.  This is a very simple wrapper granting
access to the custom "quolab_servers.conf" configuration file with secret values.

A listing of the REST endpoints and their functions are provided in the top-level README.md.
"""
import re
import json

import splunk
import splunk.admin as admin
import splunk.entity as en
import splunk.rest as rest

# Manipulate python path to ensure the correct version of 'requests' gets loaded
import os
import sys
lib_dir = os.path.join(os.path.dirname(__file__), "..", "lib")  # noqa
sys.path.insert(0, lib_dir)
del lib_dir, os, sys
APP_NAME = "TA-quolab"
SECRET_KEY = ":quolab_servers_secret__{}:"


FIELD_CONFIG = json.loads(r"""[
    {
    "description": "The server name and port where QuoLab API requests will be sent",
    "display": {
        "class": "input-xlarge"
    },
    "example": "https://example.server.com:1080/service",
    "help": "This is the same URL used for accessing the QuoLab web user interface",
    "label": "URL",
    "name": "url",
    "required": true,
    "type": "url",
    "validation": {
        "type": "regex",
        "value": "^https?://[^\\s]+$"
    }
}
    ,
    {
    "description": "Username for the QuoLab server.",
    "example": "jdoe",
    "help": "Username can be a regular user account name, or 'TOKEN' when using token-based authentication.",
    "label": "Username",
    "name": "user",
    "required": true,
    "type": "string",
    "validation": {
        "type": "regex",
        "value": "^[\\w_.-]+$"
    }
}
    ,
    {
    "default": "HIDDEN",
    "description": "The password associated with the given username or a token",
    "display": {
        "hidden": true
    },
    "label": "Password",
    "name": "secret",
    "required": true,
    "type": "secret"
}
    ,
    {
    "default": true,
    "description": "Use HTTPS certificate validation",
    "help": "The QuoLab HTTPS listener using a publicly signed certificate.  Please understand the security implications of settings this to false.  This should never be false if your QuoLab server is accessed on a public internet connection.",
    "label": "Verify",
    "name": "verify",
    "required": false,
    "type": "bool"
}
    ,
    {
    "default": 500,
    "description": "Number of catalog items to fetch per HTTP call",
    "help": "The maximum number of results that can be fetched in a single query to the API.  If more events are requested at search time then multiple queries will be sent to the API using the supported pagination technique.",
    "label": "Max Batch Size",
    "name": "max_batch_size",
    "required": true,
    "type": "int"
}
    ,
    {
    "default": 300,
    "description": "The longest duration in seconds that any individual query may last.",
    "label": "Max Execution Time",
    "name": "max_execution_time",
    "required": true,
    "type": "int"
}
    ,
    {
    "default": false,
    "description": "Toggle configuration entry status",
    "label": "Disabled",
    "name": "disabled",
    "required": false,
    "type": "bool"
}

]""")
FIELD_NAMES = [f["name"] for f in FIELD_CONFIG]
SECRET_FIELD_NAME = "secret"
SECRET_MASKED_VALUE = "HIDDEN"
CUSTOM_ACTION = "full"


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
            for field_info in FIELD_CONFIG:
                field_name = field_info["name"]
                required = field_info["required"]
                if required:
                    self.supportedArgs.addReqArg(field_name)
                else:
                    self.supportedArgs.addOptArg(field_name)

    def _fetch_secret(self, stanza):
        import requests
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
                raise admin.ArgValidationException("New quolab_servers entries require a secret")
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
                    confInfo[stanza].addCustomAction(CUSTOM_ACTION)

    def handleCustom(self, confInfo):
        if self.requestedAction == admin.ACTION_LIST and \
                self.customAction == CUSTOM_ACTION:
            confDict = self.readConf("quolab_servers")
            stanza = self.callerArgs.id
            for key, val in confDict[stanza].items():
                confInfo[stanza].append(key, val)
            # Fetch encrypted password from storage/passwords
            confInfo[stanza].append(SECRET_FIELD_NAME, self._fetch_secret(stanza))

    def handleEdit(self, confInfo):
        '''
        After user clicks Save on setup page, take updated parameters,
        normalize them, and save them somewhere

        If the EAI endpoint receives a secret value that matches the masked value it will skip
        updating to the secret stored in Splunk's password storage.  This allows the front end to
        use the masked value as a placeholder when the intention is to updated other (non-secret)
        attributes, this also means that:
            (1) The browser doesn't need the actual plainttext secret
            (2) You cannot use "HIDDEN" as a literal password value
        '''
        stanza = self.callerArgs.id
        if not re.match(r"^[\w._-]+$", stanza):
            raise admin.ArgValidationException(
                "Stanza name {!r} not accepted.  Avoid using symbols.".format(stanza))

        for field in FIELD_NAMES:
            if self.callerArgs.data[field][0] in [None, '']:
                self.callerArgs.data[field][0] = ''
        secret_value = self.callerArgs.data[SECRET_FIELD_NAME][0]
        if secret_value and secret_value != SECRET_MASKED_VALUE:
            self._store_secret(stanza, secret_value)
            # Safety/upgrade scenario.  Mask out "secret" directly in quolab_servers.conf as this
            # value will always be accessible to the user via /services/properties/quolab_servers/<stanza>/secret
            # with the 'rest_properties_get' capability enabled (which is by default for the 'user' role)
            self.callerArgs.data[SECRET_FIELD_NAME] = [SECRET_MASKED_VALUE]
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
