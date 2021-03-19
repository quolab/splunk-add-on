# QuoLab add-on for Splunk

## Introduction

COOKIECUTTER-TODO: Include a brief description of the goals and features of your product.

## Prerequisites

 * Splunk
 * QuoLab server

## Architecture

COOKIECUTTER-TODO: Describe the structure of your product.  (How does quolabquery talk to the backend service?)
If your product contains many components and/or is to be installed on different Splunk components (such as forwarders, deployment servers, indexers, search heads, etc), then a diagram is especially helpful. You can upload images if you are hosting your documentation on Splunkbase.

## Installation

Steps:

  1. Install the app on your search head or standalone Splunk instance using the normal process.
     If you need additional help, please refer to Splunk's docs: [About installing Splunk add-ons](https://docs.splunk.com/Documentation/AddOns/released/Overview/Installingadd-ons).
  1. Configure app via UI (as an `admin`).
     The add on will automatically direct you to the setup page the first time your load it from the Splunk web interface.
     Here you will be prompted to configure a QuoLab server.
  1. Configure one or more QuoLab servers.
     If only a single QuoLab server exists in your environment, name the server `quolab` to simplify your usage later.
     Add as many servers as you need, now or later.
  1. To confirm that a quolab server is setup correctly, run the `quolabquery` search to test for a response.
     Run the search `| quolabquery type=ip-address value="8.8.8.8`.
     If you created more than one server, or named your something other than "quolab", you can test it by running `| quolabquery server=MY-SERVER-NAME type=ip-address value="8.8.8.8`
  1. Grant authorization to users who should be allow to run quolabquery.
     Either add users directly to the `quolab_servers_user` role, or inherit that roles from role(s) that already exist within your organization.
     Members of the `admin` role will be able to run this automatically.

## Use cases

COOKIECUTTER-TODO: Explain how to use your product to reach the goals you state in your introduction.
If possible, provide a separate section for each unique use case, with detailed instructions for achieving the desired outcome.

## Upgrade instructions

No special upgrade procedure necessary.

## Reference material

### Configuration: QuoLab Server

This add on creates a new collection of entities called `quolab_servers`.
At least one server must be defined to use the custom SPL command.

Each server contains the following attributes:
| Attribute | Type     | Description |
| --------- | -------- | ----------- |
| `url` | URL | Server name and port where QuoLab API requests will be sent |
| `username` | String | Name of the user account to authenticate as |
| `secret` | Password | The password associated with the given `username`.  (Token based authentication is planned but not yet supported.  In which case the username would simply be left blank.) |
| `verify` | Boolean | Is the the QuoLab HTTPS listener using a publicly signed certificate.  Please understand the security implications of settings this to false.  This should never be false if your QuoLab server is accessed across via a public Internet connection. |
| `max_batch_size` | Integer | Maximum number of results that can be fetched in a single query to the API.  If more events are requested at search time then multiple queries will be send to the API using the supported pagination technique. |
| `max_execution_time` | Integer | Longest duration in seconds that any individual query may last. |


### Search command: quolabquery

The `quolabquery` command supports simple and advanced queries against a QuoLab catalog.
In _simple_ mode, a user can specify just the `type` of object to query and optionally specify one or more specific ids to search for.
In _advanced_ mode you can specify a query in JSON mode so the full power of the QuoLab query language is at your disposal.

Simple Usage:
```
| quolabquery [server=<server>] type=<quolab-type> [value=<list>]
```

Advanced Usage:
```
| quolabquery [server=<server>] query="<json-query>"
```

Parameters:

 * `type=<type>`:  For simple searches, simply provide one of the QuoLab catalog data types here.
    For example `case`, `endpoint`, or `ip-address`.
    Note that under the covers the quolabquery command determines the correct `class` associated with each `type`.
 * `value=<value>`: For simple searches, this can be used to specify one or more values (`id`s) to search for.
    To search for multiple values at once, simply enclose the values in double quotes and separate them with a comma.
 * `query=<json-query>`: In advanced mode, a custom query can be provided in JSON mode.
    To avoid escaping double quotes, the `quolabquery` command accepts a JSON-like syntax that uses single quotes as shown in some of the examples later.
    The query can be top-level query (one that explicitly provides it's own `query` key), or a simpler query where it's assumed that the entire JSON body is the child of the `query` key.  (If none of that made sense to you, start with the simple query.)

Optional parameters:

 * `server=<quolab-server>`: Use this to determine which backend QuoLab server to query.
    If not provided, the default server name is `quolab`.
 * `limit=<int>`:  Restrict the number of query results
 * `facets=<facet>`: Related data to be fetched and returned along with the primary data.
    To retrieve multiple facets at once, a comma separated list can be provided in double quotes.
 * `order=[-+]<field>`: Return results based on field ordering.
    The field name should be provided in dot-notation.
    Precede the field name with a `+` to sort in ascending order and `-` to sort in descending order.
    To sort by multiple fields, use a comma separated list surrounded by double quotes.


Example searches:

* `| quolabquery server=quolab type=wallet`
* `| quolabquery type=ip-address value="8.8.8.8, 1.2.3.4"`
* `| quolabquery type=endpoint value=tlsh:tlsh=virtual facets=display`
* `| quolabquery query="{'query':{'class': 'sysfact', 'type': 'case' },'limit': 15, 'facets': {'display': 1,'tagged': true}}"`
* `| quolabquery query="[{'class': 'sysfact', 'type': 'endpoint'}, {'class': 'sysfact', 'type': 'connector'}]" limit=100`
* `| quolabquery query="{'class': 'sysfact', 'type': 'endpoint'}" limit=100 facets="refcount,display"`


HINT: If you're trying to learn the query language, you can use the `quolabquery` command with a simple query, and view the actual JSON query sent to QuoLab at the top of Splunk's Job Inspector.


### Sourcetypes

| Sourcetype | Purpose |
| ---------- | ------- |
| command:quolabquery | Internal logs and stats related to custom QuoLab SPL command. |


### Authorization

| Role | Capability | Description |
| ---- | ---------- | ----------- |
| `admin` | `edit_quolab_servers_config` <br/> `read_quolab_servers_config` | By default, administrators can both edit server entries and execute the quolabquery command. |
| `quolab_servers_user` | `read_quolab_servers_config` | Users with this role can execute the quolabquery command. |


### Configuration files
This addon creates a custom configuration file named `quolab_servers.conf`.
For security reasons, the secret for each server is stored securely in `passwords.conf` and is encrypted at rest.
Typically there is no reason to modify these files directly.


## Source & Licensing

This is an open source project, see `LICENSE` for full details.
Full source code for TA-quolab is available on [GitHub](https://github.com/quolab/splunk-add-on).
Please check us out and send us your ideas about how to improve it. Pull request are greatly appreciated!

## Support

Community support is available on best-effort basis. For information about commercial support, contact [Kintyre](mailto:hello@kintyre.co).
Issues are tracked via [GitHub issues](https://github.com/quolab/splunk-add-on/issues).

## History

See the full [change log](https://github.com/quolab/splunk-add-on/releases).
