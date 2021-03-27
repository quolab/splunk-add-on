# TA-quolab

_QuoLab Add-on for Splunk_

[![Build Status](https://github.com/quolab/splunk-add-on/actions/workflows/build.yml/badge.svg)](https://github.com/quolab/splunk-add-on/actions)

## Install

This app is available for download and installation on [Splunkbase](https://splunkbase.splunk.com/app/5456).
Additional details can be found at [here](./.splunkbase/details.md).

## Sourcetypes

## Example usage

```
| quolabquery type=ip-address id="8.8.8.8, 1.2.3.4"

| quolabquery query="{'query':{'class': 'sysfact', 'type': 'case' },'limit': 15, 'facets': {'display': 1,'tagged': true}}"

| quolabquery query="[{'class': 'sysfact', 'type': 'endpoint'}, {'class': 'sysfact', 'type': 'connector'}]" limit=100

| quolabquery query="{'class': 'sysfact', 'type': 'endpoint'}" limit=100 facets="refcount,display"

| quolabquery type=endpoint id=tlsh:tlsh=virtual facets=display
```

## Troubleshooting

Find internal/script errors:

Enable debug logging by adding `logging_level=DEBUG` to your existing query, like so:

```
| quolabquery logging_level=DEBUG query=...
```

Search for the above debug logs, or other messages from or about the QuoLab SPL search command:

```
index=_internal (source=*quolabquery.log*) OR (sourcetype=splunkd quolab_query.py)
```

Review SPL search command logs group by request:

```
index=_internal sourcetype=command:quolabquery | transaction host Pid
```

## License

TA-quolab is available under the [Apache 2](https://www.apache.org/licenses/LICENSE-2.0) license.
## Development

If you would like to develop or build this TA from source, see the [development](./DEVELOPMENT.md) documentation.

## Reference

See the API documentation from the web interface of your local QuoLab server. Click _Help_ -> _API Documentation_. The documentation is available in the OpenAPI specification.

This SPL command uses the following API calls:

-   `v1/catalog/query` - the "swiss-army-knife" of quolab data querying. Objects can be queried from QuoLab's graph data model, and aggregated, and/or enriched using facets as necessary.

This addon was built from the [Kintyre spl addon](https://github.com/Kintyre/cypress_ta_spl) (version 0.7.3) [cookiecutter](https://github.com/audreyr/cookiecutter) project.
