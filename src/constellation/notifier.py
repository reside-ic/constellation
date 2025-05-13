import json

import requests


class Notifier:
    def __init__(self, webhook):
        self.enabled = webhook is not None
        if self.enabled:
            self.url = webhook
            self.headers = {"Content-Type": "application/json"}

    def post(self, message):
        if not self.enabled:
            return
        data = json.dumps({"text": message})
        # There are two ways that this can fail: (1) the slack server
        # can respond with an error (e.g., if the incoming webhook is
        # removed or expires, the slack server is down for
        # maintenence but still largely functioning, etc).  In that
        # case we'll get a nice HTTP error code and we can just print
        # that.  (2) the communication with the server fails because
        # the network is down, slack is really down, etc.  In that
        # case requests will Raise and that needs catching.
        #
        # In either case, as soon as one request fails, don't send
        # future notifications as they're highly unlikely to work,
        # and if they're timing out that'll get tedious.
        error = None
        try:
            r = requests.post(self.url, data=data, headers=self.headers)
            # Ignore "magic number" 300 here for non-successful HTTP
            # return code
            if r.status_code >= 300:  # noqa: PLR2004
                error = r.reason
        except Exception as e:
            error = str(e)

        if error:
            self.enabled = False
            print(f"Problem sending the slack message:\n{error}")
