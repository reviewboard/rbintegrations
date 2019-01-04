"""URL Request utilities."""

from __future__ import unicode_literals

from django.utils.six.moves.urllib.request import Request as BaseURLRequest


class URLRequest(BaseURLRequest):
    """A request that can use any HTTP method.

    By default, the :py:class:`urllib2.Request` class only supports HTTP GET
    and HTTP POST methods. This subclass allows for any HTTP method to be
    specified for the request.
    """

    def __init__(self, url, body='', headers=None, method='GET'):
        """
        Initialize the URLRequest.

        Args:
            url (unicode):
                The URL to make the request against.

            body (unicode or bytes):
                The content of the request.

            headers (dict, optional):
                Additional headers to attach to the request.

            method (unicode, optional):
                The request method. If not provided, it defaults to a ``GET``
                request.
        """
        BaseURLRequest.__init__(self, url, body, headers or {})
        self.method = method

    def get_method(self):
        """Return the HTTP method of the request.

        Returns:
            unicode:
            The HTTP method of the request.
        """
        return self.method
