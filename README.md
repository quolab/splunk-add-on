# TA-quolab

_QuoLab Add-on for Splunk_

## Example usage

QuoLab Add-on for Splunk implements a generating custom SPL search command called `quolabquery`.

```
| quolabquery type=robot height=tall

| quolabquery action=ping target=fancy_pig
```

## Sourcetypes

| Sourcetype | Purpose |
| ---------- | ------- |
| command:quolabquery | Internal logs and stats related to custom QuoLab SPL command. |


## Troubleshooting

Find internal/script errors:

### Enable debug logging

Add `logging_level=DEBUG` to your existing query to enable additional debug logs:

```
| quolabquery logging_level=DEBUG query=...
```

### Search internal logs

Search for the above debug logs, or other messages from or about the QuoLabSPL search command:

```
index=_internal (source=*quolab.log*) OR (sourcetype=splunkd quolab_query.py)
```

Review SPL search command logs group by request:

```
index=_internal sourcetype=command:quolabquery | transaction host Pid
```

## License

## Development

If you would like to develop or build this TA from source, see the [development](./DEVELOPMENT.md) documentation.

## Reference

 * **API Docs**:  https://....


This addon was built from the [Kintyre Splunk App builder](https://github.com/Kintyre/cypress-cookiecutter) (version 1.5.0) [cookiecutter](https://github.com/audreyr/cookiecutter) project.
