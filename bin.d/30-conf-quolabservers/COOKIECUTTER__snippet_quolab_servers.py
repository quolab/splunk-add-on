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
from logging import getLogger
logger = getLogger()


################################################################################
# Use quolab_servers.conf in a modular input(s)
################################################################################

# Imports


class YourModularInput:

    # Copy this method into your custom class

    def fetch_quolab_servers(self, entity_name):

        logger.debug("Fetching API endpoint configurations from Splunkd (quolab_servers.conf)")
        try:
            data = Entity(self.service, "quolab/quolab_servers/{}/full".format(self.server))
        except HTTPError as e:
            logger.info("No known server named '%s', check quolab_servers.conf", self.server)
            return None
        except Exception as e:
            self.logger.exception(
                "Unhandled exception while fetching data from quolab_servers.conf")
            raise
        return data

    def _stream_events(self, inputs, event_writer):
        for input_name, input_item in inputs.inputs.items():

            # Add the following to your code -->

            server_name = input_item["server"]
            # Load reference content from quolab_servers.conf
            server = self.fetch_quolab_servers(self, server_name)
            if not server:
                # Skip current input due to reference failure
                continue
            secret_value = server["secret"]


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


# COOKIECUTER-TODO: Delete THIS file :-)
