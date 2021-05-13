# COOKECUTTER-TODO: Integrate sample code for quolab_servers.conf into your application's code
"""
Copy this snippet into your application's custom code base.  That could be
either a custom search code, modular input or other.  Samples are provided for
typical use cases.

Note that for cookiecutter validation reasons, the following code is presented
in throwaway classes.  This allows for valid Python syntax and also means that
code here should match the indention levels in your code.
Copy imports and method sippets into the destination application code methods
"""

# Ignore this code.  This code is here to avoid validation errors
from splunklib.client import Entity, HTTPError
from cypresspoint.datatype import as_bool, reltime_to_timedelta
import sys
import json
from logging import getLogger
logger = getLogger()


# Some imports that you *may* need


################################################################################
# Use quolab_servers.conf in a modular input(s)
################################################################################

# Imports


class YourModularInput:

    # Copy this method into your custom class

    def fetch_quolab_servers(self, server):
        logger.debug("Fetching API endpoint configurations from Splunkd (quolab_servers.conf)")
        try:
            data = Entity(self.service, "quolab/quolab_servers/{}/full".format(server))
        except HTTPError as e:
            logger.info("No known server named '%s', check quolab_servers.conf", server)
            return None
        except Exception as e:
            logger.exception("Unhandled exception while fetching data from quolab_servers.conf")
            raise
        return data

    def _stream_events(self, inputs, event_writer):
        for input_name, input_item in inputs.inputs.items():

            # Add the following to your code -->

            server_name = input_item["server"]
            # Load reference content from quolab_servers.conf
            server_config = self.fetch_quolab_servers(self, server_name)
            if not server_config:
                # Skip current input due to reference failure
                continue

            server_url = server_config["url"]
            server_username = server_config["username"]
            server_secret = server_config["secret"]
            server_verify = as_bool(server_config["verify"])
            server_max_batch_size = int(server_config["max_batch_size"])
            server_max_execution_time = int(server_config["max_execution_time"])
            server_disabled = as_bool(server_config["disabled"])


################################################################################
# Use quolab_servers.conf for a custom SPL search command
################################################################################
# Imports


class YourCustomSearchCommand:

    def __init__(self):
        # Set defaults for quolab_servers server

        self.api_url = None
        self.api_username = None
        self.api_secret = "HIDDEN"
        self.api_verify = True
        self.api_max_batch_size = 500
        self.api_max_execution_time = 300
        self.api_disabled = False

    def prepare(self):
        # Put this at the END of your prepare() method

        self.logger.debug("Fetching API endpoint configurations from Splunkd (quolab_servers.conf)")
        try:
            api = Entity(self.service, "quolab/quolab_servers/{}/full".format(self.server))
        except HTTPError:
            self.error_exit("No known server named '{}', check quolab_servers.conf".format(self.server),
                            "Unknown server named '{}'.  Check value provided for 'server=' option.".format(self.server))
        except Exception as e:
            self.logger.exception("Unhandled exception: ")
            self.write_error("Aborting due to internal error:  {}", e)

        # COOKIECUTTER-TODO: Handle all variables here

        self.api_url = api["url"]
        self.api_username = api["username"]
        self.api_verify = as_bool(api["verify"])
        self.api_max_batch_size = int(api["max_batch_size"])
        self.api_max_execution_time = int(api["max_execution_time"])
        self.api_disabled = as_bool(api["disabled"])

        self.logger.debug("Entity api: %r", self.api_url)
        self.api_secret = api["secret"]
        if not self.api_secret:
            self.error_exit("Check the configuration.  Unable to fetch data "
                            "from {} without secret.".format(self.api_url),
                            "Missing secret.  Did you run setup?")


################################################################################
# Use quolab_servers.conf for a modular alert action
################################################################################
# Imports & Globals
APP_NAME = "TA-quolab"


def splunklib_client(url, session_key, app=None, owner=None):
    import splunklib.client
    from six.moves.urllib.parse import urlparse
    u = urlparse(url)
    service = splunklib.client.connect(
        host=u.hostname,
        port=u.port,
        scheme=u.scheme,
        token=session_key,
        app=app or APP_NAME,
        owner=owner or "nobody",
        autologin=False)
    return service


def fetch_quolab_servers(service, server):
    logger.debug("Fetching API endpoint configurations from Splunkd (quolab_servers.conf)")
    try:
        data = Entity(service, "quolab/quolab_servers/{}/full".format(server))
    except HTTPError as e:
        logger.info("No known server named '%s', check quolab_servers.conf", server)
        return None
    except Exception as e:
        logger.exception("Unhandled exception while fetching data from quolab_servers.conf")
        raise
    return {
        "url":  data["url"],
        "username":  data["username"],
        "verify": as_bool(data["verify"]),
        "max_batch_size": int(data["max_batch_size"]),
        "max_execution_time": int(data["max_execution_time"]),
        "disabled": as_bool(data["disabled"]),
    }


# Whatever your processsing function is named....

def alert_main():
    settings = json.loads(sys.stdin.read())
    session = splunklib_client(settings["server_uri"],
                               settings["session_key"],
                               settings["app"],
                               settings["owner"])

    configuration = settings['configuration']
    server_name = configuration["server"]
    server_config = fetch_quolab_servers(session, server_name)
    if not server_config:
        # CONF entity not found.  Abort.
        return

    # PICK YOUR OWN ADVENTURE:

    # Option 1:  Access the quolab_servers properties with standard dictionary access
    FIELD_NAME = server_config["FIELD_NAME"]

    # Option 2:  Add expanded conf settings to the configuration variable under a new key:
    configuration["server_conf"] = server_config

    # Option 3:  Flatten everyting into 'configuration', assuming no naming collisions between alert_actions.conf & quolab_servers.conf
    configuration.update(server_config)

# COOKIECUTER-TODO: Delete THIS file :-)
