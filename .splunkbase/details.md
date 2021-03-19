# QuoLab Add-on for Splunk

## Introduction

COOKIECUTTER-TODO: Include a brief description of the goals and features of your product.

## Prerequisites

COOKIECUTTER-TODO: List any content that your product needs to function correctly.
List any specific hardware or licensing requirements that your product needs. Explain any technologies or concepts that your users need.

## Architecture

COOKIECUTTER-TODO: Describe the structure of your product.  (How does quolabquery talk to the backend service?)
If your product contains many components and/or is to be installed on different Splunk components (such as forwarders, deployment servers, indexers, search heads, etc), then a diagram is especially helpful. You can upload images if you are hosting your documentation on Splunkbase.

## Installation

COOKIECUTTER-TODO: Provide detailed, sequence-ordered steps for installing your product. If required, explain any specific commands.

If you need additional help, please refer to Splunk's docs: [About installing Splunk add-ons](https://docs.splunk.com/Documentation/AddOns/released/Overview/Installingadd-ons).

Steps:

  1. Install the app
  1. Configure app via UI (as an `admin`).  Note that the add on will automatically direct you to the setup page the first time your load it from the Splunk web interface.
  1. Configure one or more QuoLab servers.  If only a single QuoLab server exists in your environment, make a new entry called `quolab` and this server will be used by default. Otherwise, add as many servers as you need.
  1. COOKIECUTTER-TODO:  Add information about how to test the quolabquery command.
  1. Grant authorization to users who should be allow to run quolabquery common.  Either add users directly to the `quolab_servers_user` role, or inherit that roles from role(s) that already exist within your organization.  Members of the `admin` role will be able to run this automatically.

## Use cases

COOKIECUTTER-TODO: Explain how to use your product to reach the goals you state in your introduction.
If possible, provide a separate section for each unique use case, with detailed instructions for achieving the desired outcome.

## Upgrade instructions

COOKIECUTTER-TODO: If you can upgrade this version release of your product from a previous version, provide detailed instructions on how to do so, as well as any relevant changes in structure or operation your existing users should expect.

## Reference material

COOKIECUTTER-TODO: If your product includes lookup tables, saved searches, scripted inputs, or other similar knowledge objects, it's useful to provide details about them so your users know what's included and how to use them in your product.
You can list them in detail, or describe where to find them within your product's file structure.

### Search commands

#### quolabquery

Usage:

```
quolabquery server=my_server field=input
```

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
