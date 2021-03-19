# TA-quolab

_QuoLab add-on for Splunk_


[![Build Status](https://github.com/quolab/splunk-add-on/actions/workflows/build.yml/badge.svg?branch=main)](https://github.com/quolab/splunk-add-on/actions)


## Install



This app is available for download and installation on [Splunkbase](https://splunkbase.splunk.com/apps/#/search/TA-quolab/).
Additional details can be found at [here](./.splunkbase/details.md).



## Sourcetypes

| Sourcetype | Purpose |
| ---------- | ------- |
| command:quolabquery | Internal logs and stats related to custom QuoLab SPL command. |

## Troubleshooting

Find internal/script errors:

```
index=_internal (source=*quolab.log*) OR (sourcetype=splunkd quolab_query.py)
```

Review SPL search command logs:

```
index=_internal sourcetype=command:quolabquery | transaction host Pid
```

## Development

If you would like to develop or build this TA from source, see the [development](./DEVELOPMENT.md) documentation.

## Reference

 * **API Docs**:  https://....


This addon was built from the [Kintyre spl addon](https://github.com/Kintyre/cypress_ta_spl) (version 0.7.1) [cookiecutter](https://github.com/audreyr/cookiecutter) project.
