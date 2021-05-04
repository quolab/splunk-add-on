# TA-quolab

_QuoLab Add-on for Splunk_


# Modular input

QuoLab Add-on for Splunk provides events ingestion for Splunk

This add-on includes the `quolab_timeline` modular input.

## Sourcetypes

| Sourcetype | Type | Purpose |
| ---------- | ---- | ------- |
| quolab:timeline | modular input | Events collected from the QuoLab API |
| quolab:modinput:timeline | monitor | Internal logs and stats related to QuoLab data ingestion. |


## Troubleshooting

Internal/script errors:
```
index=_internal (source=*quolab_timeline*.log) OR (sourcetype=splunkd ExecProcessor "message from" quolab_timeline.py) OR (component=ModularInputs quolab_timeline)
```

Review all modular input logs:
```
index=_internal sourcetype=quolab:modinput:timeline | transaction host process_id
```

Search to show indexing lag:  (Delay is shown in hours).  You should be able to compare the backfilled events vs live events with this chart:
```
sourcetype="quolab:timeline" | eval index_delay = (_indextime-_time)/3600 | timechart avg(index_delay)
```




Looking deeper:

```
splunk cmd splunkd print-modinput-config --debug quolab_timeline quolab_timeline://YourStanzaNameHere
```

See Splunk's docs for more [help](https://docs.splunk.com/Documentation/Splunk/latest/AdvancedDev/ModInputsDevTools).



## Reference

 * **API Docs**:  https://....
