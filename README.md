# TA-quolab
*QuoLab add-on for Splunk*


## Sourcetypes

| Sourcetype | Type | Purpose |
| ---------- | ---- | ------- |
| command:quolabquery | monitor | Internal logs and stats related to QuoLab data ingestion. |


## Troubleshooting

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


To setup a new 'test' configuratation stanza from the CLI, run:

```bash
curl -ks -u admin:changeme -X POST \
    https://127.0.0.1:8089/servicesNS/nobody/TA-quolab/quolab_servers/quolab_serversendpoint/quolab \
    -d url=https://server.example/path/v1/api\
    -d username=admin\
    -d verify=Default for Verify\
    -d token=SECRET-VALUE
```

## Development

If you would like to develop or build this TA from source, see the [development](./DEVELOPMENT.md) documentation.


## Troubleshoot

### Rest endpoint

**Show errors thrown in Admin Manager extention:**
```
index=_internal sourcetype=splunkd ERROR AdminManagerExternal TA-quolab quolab_servers_python_handler.py | eval _raw=replace(_raw, "\\\n", urldecode("%0a"))
```

Not sure which one this is:

```
index=_internal sourcetype=splunkd SetupAdminHandler quolab_servers/quolab_serversendpoint
```





## Reference

 * **API Docs**:  https://....


This addon was built from the [Kintyre rest addon](https://github.com/Kintyre/cypress_ta_rest) [cookiecutter](https://github.com/audreyr/cookiecutter) project.

