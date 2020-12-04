"""Utilities for interacting with the Jenkins CI API."""

from __future__ import unicode_literals

import json
import logging

from django.utils.six.moves.urllib.error import HTTPError
from django.utils.six.moves.urllib.parse import (quote, urlencode)
from django.utils.six.moves.urllib.request import urlopen

try:
    # Review Board 4.0
    from reviewboard.hostingsvcs.service import HostingServiceHTTPRequest
except ImportError:
    # Review Board 3.0
    from reviewboard.hostingsvcs.service import URLRequest as \
        HostingServiceHTTPRequest


logger = logging.getLogger(__name__)


class JenkinsAPI(object):
    """Object for interacting with the Jenkins CI API."""

    csrf_protection_enabled = True
    crumb = None
    crumb_request_field = None

    def __init__(self, endpoint, job_name, username, password):
        """Initialize the object.

        Args:
            endpoint (unicode):
                Jenkins server endpoint.

            job_name (unicode):
                Job name on Jenkins.

            username (unicode):
                Jenkins username.

            password (unicode):
                Jenkins password.
        """
        self.endpoint = endpoint
        self.job_name = job_name
        self.username = username
        self.password = password

    def test_connection(self):
        """Test the connection to the Jenkins server.

        This is used for verifying both the URL and user credentials are
        correct.
        """
        self._make_request('%s/api/json?pretty=true' % self.endpoint,
                           method='GET')

    def start_build(self, patch_info):
        """Start a build.

        Args:
            patch_info (dict):
                Contains the review ID, review diff revision and the status
                update ID.

        Raises:
            urllib2.URLError:
                The HTTP request failed.
        """
        data = {
            'parameter': [
                {
                    'name': 'REVIEWBOARD_SERVER',
                    'value': patch_info['reviewboard_server']
                },
                {
                    'name': 'REVIEWBOARD_REVIEW_ID',
                    'value': patch_info['review_id']
                },
                {
                    'name': 'REVIEWBOARD_DIFF_REVISION',
                    'value': patch_info['diff_revision']
                },
                {
                    'name': 'REVIEWBOARD_STATUS_UPDATE_ID',
                    'value': patch_info['status_update_id']
                }
            ]
        }

        # This is not part of the official REST API, but is however listed in
        # the Jenkins wiki as the correct way to initiate a remote build.
        #
        # This method of passing in the build parameters may change in the
        # future.
        self._make_request(
            '%s/job/%s/build' % (self.endpoint,
                                 quote(self.job_name)),
            body=urlencode({
                'json': json.dumps(data)
            }),
            content_type='application/x-www-form-urlencoded',
            method='POST'
        )

    def _fetch_csrf_token(self):
        """Fetches a CSRF token from the Jenkins server.

        This is required for making requests to API endpoints when using basic
        authentication. A crumb is no longer required when using API token
        authentication to access buildWithParameters.
        """
        data = self._make_raw_request('%s/crumbIssuer/api/json'
                                      % self.endpoint)

        result = json.loads(data)

        self.crumb = result['crumb']
        self.crumb_request_field = result['crumbRequestField']

    def _make_request(self, url, body=None, method='GET',
                      content_type=''):
        """Make an HTTP request.

        This will first attempt to fetch a CSRF token if we do not currently
        have one.

        Args:
            url (unicode):
                The URL to make the request against.

            body (unicode or bytes, optional):
                The content of the request.

            method (unicode, optional):
                The request method. If not provided, it defaults to a ``GET``
                request.

            content_type (unicode, optional):
                The type of the content being POSTed.

        Returns:
            bytes:
            The contents of the HTTP response body.

        Raises:
            urllib2.URLError:
                The HTTP request failed.
        """
        if self.csrf_protection_enabled and not self.crumb:
            try:
                self._fetch_csrf_token()
            except HTTPError as e:
                if e.code == 404:
                    self.csrf_protection_enabled = False
                else:
                    raise e

        return self._make_raw_request(url, body, method, content_type)

    def _make_raw_request(self, url, body=None, method='GET',
                          content_type=''):
        """Make an HTTP request.

        Args:
            url (unicode):
                The URL to make the request against.

            body (unicode or bytes, optional):
                The content of the request.

            method (unicode, optional):
                The request method. If not provided, it defaults to a ``GET``
                request.

            content_type (unicode, optional):
                The type of the content being POSTed.

        Returns:
            bytes:
            The contents of the HTTP response body.

        Raises:
            urllib2.URLError:
                The HTTP request failed.
        """
        logger.debug('Making request to Jenkins CI %s', url)

        headers = {}

        if self.crumb:
            headers[self.crumb_request_field] = self.crumb

        if content_type:
            headers['Content-Type'] = content_type

        request = HostingServiceHTTPRequest(
            url,
            body=body,
            method=method,
            headers=headers)

        request.add_basic_auth(self.username, self.password)

        if hasattr(request, 'open'):
            # Review Board >= 4.0
            response = request.open()
            data = response.data
        else:
            # Review Board 3.x
            response = urlopen(request)
            data = response.read()

        return data
