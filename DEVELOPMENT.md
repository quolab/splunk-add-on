# Developing TA-quolab

## Python packages

Externally required Python packages are listed in the [requirements.txt](./requirements.txt) file.
These packages are automatically downloaded and installed into the `lib` folder of the addon during the build process.

**Gotchas:**  Avoid packages that *only* work on a specific version of Python or has OS-specific compiled libraries.
Python 2.7 support is going away for more and more packages, so pinning older versions may be required until targeting only Splunk 8+ for compatibility.
The default build script only builds with a single version of Python, and doesn't attempt to separate packages based on OS or Python version.

## Development

Setup a local virtual environment in the top level of the package to install the necessary build and runtime requirements.

    python -m virtualenv venv
    . venv/bin/activate
    python -m pip install -U -r requirements-dev.txt


## Building

You can build the QuoLab Add-on for Splunk using the following steps:

First install:

    ./build.py && "$SPLUNK_HOME/bin/splunk" install app "$(<.release_path)"

To quickly reload the app on a local Splunk instance during development:

    ./build.py && "$SPLUNK_HOME/bin/splunk" install app "$(<.release_path)" -update 1




### Information available via various REST endpoints

| REST endpoint | Script | Information shown |
| ------------- | ------ | ----------------- |
| `/servicesNS/-/-/quolab/quolab_servers/<name>` | `rest_quolab_servers_config.py` | Write properties and unencrypted 'secret'; restricted via capabilities.  Only `read_quolab_servers_config` can read, and `edit_quolab_servers_config` can write.|
| `/servicesNS/-/-/quolab/quolab_servers/<name>/full` | `rest_quolab_servers_config.py` | Read properties and unencrypted 'secret'; restricted same as above. |
| `/servicesNS/-/-/configs/conf-quolab_servers` | N/A (native) | Shows 'secret' as "HIDDEN" |
| `/servicesNS/-/-/properties/quolab_servers/<name>/secret` | N/A (native) | Shows 'value' as "HIDDEN" |
| `/servicesNS/-/-/storage/passwords` | N/A (native) | Will show `password` in encrypted form (as stored in `passwords.conf`) and `clear_password` (unencrypted).  Access is restricted to users with the `list_storage_passwords` capability. |
| `/services/quolab/quolab_servers_secret` | `rest_quolab_servers_secret.py` | Show unencrypted `secret` and is restricted via capabilities.  Uses the scripted rest handler with `passSystemAuth` enabled so that the necessary secret can be obtained without being an admin. |

### Manually creating a new entry

Normally entries are created via the *Configuration* page via SplunkWeb.  However, if the UI is unavailable or for automation purposes, here's an example of how this can be done from the CLI.
This `curl` command creates a new 'quolab' configuration stanza:

```bash
curl -ks -u admin:changeme -X POST \
    https://127.0.0.1:8089/servicesNS/nobody/TA-quolab/quolab/quolab_servers/quolab \
    -d url="https://example.server.com:1080/service"\
    -d username="jdoe"\
    -d secret="HIDDEN"\
    -d max_batch_size="500"\
    -d max_execution_time="300"\
```

### Troubleshooting

Show errors regarding the Admin Manager extension (EAI endpoint):

```
index=_internal sourcetype=splunkd ERROR AdminManagerExternal OR PersistentScript TA-quolab rest_quolab_servers_config.py
| eval _raw=replace(_raw, "\\\n", urldecode("%0a"))
```

Find errors related to secret handler:

```
index=_internal sourcetype=splunkd SetupAdminHandler quolab/quolab_servers_secret
```



#### Troubleshooting Modular input

Looking deeper:

```
splunk cmd splunkd print-modinput-config --debug quolab_timeline quolab_timeline://YourStanzaNameHere
```

See Splunk's docs for more [help](https://docs.splunk.com/Documentation/Splunk/latest/AdvancedDev/ModInputsDevTools).




## Tools

 * [Cookiecutter](https://github.com/audreyr/cookiecutter) is use to kickstart the development of new addons.
 * [bump2version](https://pypi.org/project/bump2version/) Version bump your addon with a single command!
 * [ksconf](https://ksconf.readthedocs.io/) Kintyre Splunk CONF tool
 * [pre-commit](https://pre-commit.com/) a framework for managing and maintaining pre-commit hooks for git.
