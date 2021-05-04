[quolab_timeline://]

timeline = <string>
* GUID of timeline in QuoLab
* (required)
backfill_range = <relative-time>
* Duration of backfill on first run.
* Default: 5d
* Example: ['5d', '3h', '10m']
* (optional)
batch_size = <int>
* Number of events to fetch per HTTPS call
* Default: 1000
* (required)
log_level = <string>
* Logging level for internal logging
* Choices: DEBUG, INFO, WARN, ERROR
* Default: INFO
* (required)

disabled = <bool>
