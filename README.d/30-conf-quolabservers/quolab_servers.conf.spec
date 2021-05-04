[<quolab_servers>]
# Note that 'secret' is stored in passwords.conf

url = <url>
* The server name and port where QuoLab API requests will be sent
* Example: https://example.server.com:1080/service
* (required)
username = <string>
* Username for the QuoLab server.
* Example: jdoe
* (required)
secret = <secret>
* The password associated with the given username or a token
* Default: HIDDEN
* (required)
verify = <bool>
* Use HTTPS certificate validation
* Default: True
* (optional)
max_batch_size = <int>
* Number of catalog items to fetch per HTTP call
* Default: 500
* (required)
max_execution_time = <int>
* The longest duration in seconds that any individual query may last.
* Default: 300
* (required)
disabled = <bool>
* Toggle configuration entry status
* Default: False
* (optional)
