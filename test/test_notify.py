import io
import json
import pytest
import requests

from contextlib import redirect_stdout
from unittest import mock

from constellation.notifier import Notifier


def test_notifier_requires_webhook():
    obj = Notifier(None)
    assert not obj.enabled
    # just check no massive failure here:
    assert obj.post("message") is None


def test_notifier_can_post():
    url = "https://example.com/hook"
    message = "hello"
    obj = Notifier(url)
    assert obj.enabled
    assert obj.headers == {'Content-Type': 'application/json'}
    ret = mock.Mock(spec=requests.Response)
    ret.status_code = 200
    with mock.patch("requests.post", return_value=ret) as requests_post:
        obj.post(message)
    requests_post.assert_called_once_with(
        obj.url, data=json.dumps({"text": message}), headers=obj.headers)


def test_notifier_gracefully_handles_http_error():
    url = "https://example.com/hook"
    message = "hello"
    obj = Notifier(url)

    ret = mock.Mock(spec=requests.Response)
    ret.status_code = 404
    ret.reason = "not found"

    f = io.StringIO()
    with mock.patch("requests.post", return_value=ret) as requests_post:
        with redirect_stdout(f):
            obj.post(message)

    msg = "Problem sending the slack message:\nnot found\n"
    assert f.getvalue() == msg
    assert not obj.enabled


def test_notifier_gracefully_handles_other_error():
    url = "https://example.com/hook"
    message = "hello"
    obj = Notifier(url)

    f = io.StringIO()
    with mock.patch("requests.post") as requests_post:
        requests_post.side_effect = Exception("Unhandled error")
        with redirect_stdout(f):
            obj.post(message)

    msg = "Problem sending the slack message:\nUnhandled error\n"
    assert f.getvalue() == msg
    assert not obj.enabled
