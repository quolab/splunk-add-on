# QuoLab Add-on for Splunk

## Introduction

The QuoLab Add-On for Splunk adds the `quolabquery` generating command to a Splunk environment, allowing an authorized user to make requests to one or more QuoLab servers to bring in data to Splunk for additional forensic and analytic investigation.

## Prerequisites

 * Splunk
 * a QuoLab server

## Architecture

This add-on comprises an authentication lookup and a python script that implements `quolabquery`, a generating command. `quolabquery` wraps and simplifies requests to the QuoLab REST API. Requests will be sent through web hooks to the same url as the user interface.

## Installation

Steps:

  1. **Install the app** on your search head or standalone Splunk instance using the normal process.
     If you need additional help, please refer to Splunk's docs: [About installing Splunk add-ons](https://docs.splunk.com/Documentation/AddOns/released/Overview/Installingadd-ons).
  1. **Configure app via UI** (as an `admin`).
     The add on will automatically direct you to the setup page the first time you load it from the Splunk web interface.
     Here you will be prompted to configure a QuoLab server.
  1. **Configure one or more QuoLab servers**.
     If only a single QuoLab server exists in your environment, name the server `quolab` to simplify your usage later.
     Add as many servers as you need, now or later.
  1. **Confirm that a quolab server is setup correctly** by running the `quolabquery` search to test for a response.
     For example, run the search `| quolabquery type=ip-address id="8.8.8.8"`.
     If you created more than one server or named it something other than "quolab", you can test it by running `| quolabquery server=MY-SERVER-NAME type=ip-address id="8.8.8.8"`
  1. **Grant authorization** to users who should be allow to run quolabquery.
     Either add users directly to the `quolab_servers_user` role, or inherit that roles from role(s) that already exist within your organization.
     Members of the `admin` role will be able to run this automatically.

## Use cases

QuoLab users looking to further enrich their investigations can now bring QuoLab artifacts into Splunk to leverage Splunk's ecosystem and analytics.  See _Combining QuoLab with Splunk_ below for expanded examples.

### Find a specific domain

```
| quolabquery type=domain id=google.com
```

### Find facets associated with multiple cases

```
| quolabquery type=case facets="display,tagged" limit=30
```

### Find cases where a specific IP address was targeted

```
| quolabquery query="{'class': 'sysref', 'type': 'encases', 'target': {'id': '1.2.3.4', 'class': 'fact', 'type': 'ip-address'}}"
```

## Upgrade instructions

No special upgrade procedures are necessary.

## Reference material

### Configuration: QuoLab Server

This add-on creates a new collection of entities called `quolab_servers`.
At least one server must be defined to use the custom SPL command.

Each server contains the following attributes:

| Attribute | Type     | Description |
| --------- | -------- | ----------- |
| `url` | URL | The server name and port where QuoLab API requests will be sent |
| `username` | String | Name of the QuoLab user account, or `<TOKEN>` if using token-based authentication |
| `secret` | Password <br/> or Token | The password associated with the given `username` or a token |
| `verify` | Boolean | The QuoLab HTTPS listener using a publicly signed certificate.<br/> Please understand the security implications of settings this to `false`.<br/>  This should never be `false` if your QuoLab server is accessed on a public internet connection. |
| `max_batch_size` | Integer | The maximum number of results that can be fetched in a single query to the API.<br/> If more events are requested at search time then multiple queries will be send to the API<br/> using the supported pagination technique. |
| `max_execution_time` | Integer | The longest duration in seconds that any individual query may last. |


### Search command: quolabquery

The `quolabquery` command supports simple and advanced queries against a QuoLab catalog.
In _simple_ mode, a user can specify just the `type` of object to query and optionally specify one or more specific ids to search for.
In _advanced_ mode you can specify a query in JSON mode so the full power of the QuoLab query language is at your disposal.

Simple Usage:
```
| quolabquery [server=<server>] type=<quolab-type> [id=<list>]
```

Advanced Usage:
```
| quolabquery [server=<server>] query="<json-query>"
```

Parameters:

 * `type=<type>`:  For simple searches, provide one of the QuoLab catalog types here.
    For example: `case`, `endpoint`, or `ip-address`.
    The quolabquery command will determine the correct `class` associated with each `type`.
 * `id=<value>`: For simple searches, this can be used to specify one or more values (`id`s) to search for.
    To search for multiple ids, simply enclose the id in double quotes and separate them with a comma.
 * `query=<json-query>`: In advanced mode, a custom query can be provided in JSON mode.
    To avoid escaping double quotes, the `quolabquery` command accepts a JSON-like syntax that uses single quotes as shown in some of the examples later.
    The query can be top-level query (one that explicitly provides it's own `query` key), or a simpler query where it's assumed that the entire JSON body is the child of the `query` key.  (If none of that made sense to you, start with the simple query.)

Optional parameters:

 * `server=<quolab-server>`: Use this to determine which backend QuoLab server to query.
    If not provided, the default server name is `quolab`.
 * `limit=<int>`:  Restrict the number of query results.
 * `facets=<facet>`: Facets are related data to be fetched and returned along with the primary data.
    To retrieve multiple facets at once, provide a comma separated list in double quotes.
 * `order=[-+]<field>`: Return results based on field ordering.
    The field name should be provided in dot-notation.
    Precede the field name with a `+` to sort in ascending order and `-` to sort in descending order.
    To sort by multiple fields, use a comma separated list surrounded by double quotes.


Example searches:

* `| quolabquery server=quolab type=wallet`
* `| quolabquery type=ip-address id="8.8.8.8, 1.2.3.4"`
* `| quolabquery type=endpoint id=tlsh:tlsh=virtual facets=display`
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
| `admin` | `edit_quolab_servers_config` <br/> `read_quolab_servers_config` | By default, administrators can both<br/> edit server entries and execute the quolabquery command. |
| `quolab_servers_user` | `read_quolab_servers_config` | Users with this role can execute the quolabquery command. |


### Configuration files
This add-on creates a custom configuration file named `quolab_servers.conf`.
For security reasons, the secret for each server is stored securely in `passwords.conf` and is encrypted at rest.
Typically there is no reason to modify these files directly.


## Combining QuoLab with Splunk

The real power of the `quolabquery` command is that it can be combined with other Splunk search commands.  We'd love to expand this section to showcase real-life use cases.  Please reach out with with your success stories.  In the meantime, here are some ideas to get you started:

### Capturing Tor descriptors to a lookup using 'outputlookup'

Combining the `quolabquery` command with `outputlookup` allows you to overwrite or append an existing [lookup](https://docs.splunk.com/Documentation/Splunk/8.1.3/Knowledge/Aboutlookupsandfieldactions) table within Splunk.

```
| quolabquery limit=5000 type=known-as facets=refcount | search fact.type="tor-descriptor"
| rename fact.* as * | table id type label refcount.*
| outputlookup quolab_tor_descriptor.csv
```

### Search for firewall events related to QuoLab cases with a subsearch

This technique uses Splunk's [subsearch](https://docs.splunk.com/Documentation/Splunk/8.1.3/Search/Aboutsubsearches) feature to insert specific fields returned by `quolabquery` command into a dynamic search.  In this example, Splunk looks in the `firewall` index for ip addresses in the `src_ip` field.

```
index=firewall [
    | quolabquery query="{'class': 'sysref', 'type': 'encases', 'target': {'class': 'fact', 'type': 'ip-address'}}" facets="display"
    | return 1000 src_ip=target.display.label ]
| table _time, sourcetype, src_ip, src_port, dest_ip, dest_port, action
```

The final search Splunk executes will look like:
```
index=firewall (src_ip="1.2.3.4") OR (src_ip="99.99.99.99") OR ...
| table _time, sourcetype, src_ip, src_port, dest_ip, dest_port, action
```

### Check the QuoLab catalog for cases involving threats known to Splunk

This search uses Splunk's `map` command to launch the `quolabquery` command using a template search.  Here is an example where threat ip address (the `src_ip` field in Splunk) is used to check for cases containing that IP address in QuoLab.

```
index=threat | top 10 src_ip
| map search="| quolabquery query=\"{'class': 'sysref', 'type': 'encases', 'target': {'class': 'fact', 'type': 'ip-address', 'id': '$src_ip$'}}\" facets=display"
| eval _time='document.created-at'
| table _time source.type source.display.label target.display.label document.created-by
```

Be aware that there are many limitations to the use of the Splunk `map` command.  This approach is not very efficient or scalable, it requires escaping the search string, and any `src_ip` on the input that doesn't match in the QuoLab catalog is dropped from the output.  These are all standard limitations of `map`.  If augmenting Splunk data with QuoLab catalog data is an important use case for you please contact us.  A future lookup-like search command has been considered, hearing from you will help with prioritizing new features.

### Collect recent QuoLab cases in a Splunk index

QuoLab Add-On for Splunk doesn't natively support sending QuoLab catalog data into a Splunk index, it can be done relatively easily using a [summary index](https://docs.splunk.com/Splexicon:Summaryindex) technique.   Here is an example that will find any cases updated within the last day and send selected fields to a summary index for later searches in Splunk.

If this is a use case you find yourself using frequently, please reach out.  There's several inherit limitations of this approach and gotchas with summary indexing, especially around timing.  Let us know if natively supporting this would be a valuable feature.

```
| quolabquery type=case limit=1000
| where 'document.updated-at' > relative_time(now(), "-1d@d")
| table class, type, id, document.type, document.name, document.priority, document.created-by, document.created-at, document.updated-at, document.created-by
| eval _time='document.updated-at'
| collect index=summary source=quolab-cases
```

This data can then be searched in Splunk by running the query:

```
index=summary source=quolab-cases
```


## Source & Licensing

This is an open source project. See `LICENSE` for full details.
Full source code for TA-quolab is available on [GitHub](https://github.com/quolab/splunk-add-on).
Please check it out and send us your ideas about how to improve it. Pull requests are greatly appreciated!

## Support

Community support is available on a best-effort basis. For information about commercial support, contact [Kintyre](mailto:hello@kintyre.co).
Issues are tracked via [GitHub issues](https://github.com/quolab/splunk-add-on/issues).

## History

See the full [change log](https://github.com/quolab/splunk-add-on/releases).
