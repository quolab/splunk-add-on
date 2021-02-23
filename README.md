
# TA-quolab
*QuoLab add-on for Splunk*


## Sourcetypes

| Sourcetype | Type | Purpose |
| ---------- | ---- | ------- |
| command:quolabquery | monitor | Internal logs and stats related to custom QuoLab SPL command. |


## Troubleshooting


Enable debug logging:
```
| quolabquery logging_level=DEBUG query=...
```

Internal/script errors:
```
index=_internal (source=*quolab.log*) OR (sourcetype=splunkd quolab_query.py)
```

Review all modular input logs:
```
index=_internal sourcetype=command:quolabquery | transaction host Pid
```

## REST Endpoints

Information available via various REST endpoints:


| REST endpoint | Script | Information shown |
| ------------- | ------ | ----------------- |
| `/services/quolab_servers/quolab_serversendpoint/<name>` | `quolab_servers_python_handler.py` | Shows unencrypted 'token'; restricted via capabilities.  Only `read_quolab_servers_config` can read, and `edit_quolab_servers_config` can write.|
| `/servicesNS/-/-/configs/conf-quolab_servers` | N/A (native) | Shows 'token' as "HIDDEN" |
| `/servicesNS/-/-/properties/quolab_servers/<name>/token` | N/A (native) | Shows 'value' as "HIDDEN" |
| `/servicesNS/-/-/storage/passwords` | N/A (native) | Will show `password` in encrypted form (as stored in `passwords.conf`) and `clear_password` (unencrypted).  Access is restricted to users with the `list_storage_passwords` capability. |
| `/services/quolab_servers_fetch_token` | `quolab_servers_rh_settings.py` | Show unencrypted `token` and is restricted via capabilities.  Uses the scripted rest handler with `passSystemAuth` enabled so that the necessary secret can be obtained without being an admin. |


To setup a new 'test' configuration stanza from the CLI, run:

```bash
curl -ks -u admin:changeme -X POST \
    https://127.0.0.1:8089/servicesNS/nobody/TA-quolab/quolab_servers/quolab_serversendpoint/quolab \
    -d url=https://server.example/path/v1/api\
    -d username=admin\
    -d verify=true\
    -d token=SECRET-VALUE
```

## Development

If you would like to develop or build this TA from source, see the [development](./DEVELOPMENT.md) documentation.


## Example usage

```
| quolabquery query="{'query':{'class': 'sysfact', 'type': 'case' },'limit': 15, 'facets': {'display': 1,'tagged': true}}"

| quolabquery query="[{'class': 'sysfact', 'type': 'endpoint'}, {'class': 'sysfact', 'type': 'connector'}]" limit=100

| quolabquery query="{'class': 'sysfact', 'type': 'endpoint'}" limit=100 facets=display

| quolabquery type=endpoint limit=100 facets=display value=tlsh:tlsh=virtual

```

## Troubleshoot

### Rest endpoint

**Show errors thrown in Admin Manager extension:**
```
index=_internal sourcetype=splunkd ERROR AdminManagerExternal TA-quolab quolab_servers_python_handler.py | eval _raw=replace(_raw, "\\\n", urldecode("%0a"))
```

Not sure which one this is:

```
index=_internal sourcetype=splunkd SetupAdminHandler quolab_servers/quolab_serversendpoint
```





## Reference

See the API documentation from the web interface of your local QuoLab server.  Click *Help* -> *API Documentation*.  The documentation is available in the OpenAPI specification.

This SPL command uses the following API calls:

 * `v1/catalog/query` - the "swiss-army-knife" of quolab data querying. Objects can be queried from QuoLab's graph data model, and aggregated, and/or enriched using facets as necessary.


This addon was built from the [Kintyre spl addon](https://github.com/Kintyre/cypress_ta_spl) (version 0.3.0) [cookiecutter](https://github.com/audreyr/cookiecutter) project.

