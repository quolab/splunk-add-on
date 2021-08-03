[quolab_timeline://]

server = <string>
* Name of QuoLab server
* Default: quolab
* (required)
timeline = <string>
* Timeline id from QuoLab
* (required)
facets = <string>
* List one or more facets to apply to events returned from the timeline.  Multiple facets should be separated by a comma.
* Default: display
* (optional)
backfill = <bool>
* If enabled, the first run will retrieve all existing events from the queue
* Default: True
* (optional)
log_level = <string>
* Logging level for internal logging
* Choices: DEBUG, INFO, WARN, ERROR
* Default: INFO
* (required)

disabled = <bool>
