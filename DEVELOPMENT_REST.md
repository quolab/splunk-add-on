## REST Endpoints

The following table highlights how the REST endpoint protects your server secret in a secure way, using Splunk's password storage capabilities.  The trick here is granting access to a custom capability without granting access to the entire password storage system for non-admin users.


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
