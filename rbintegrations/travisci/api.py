"""Utilities for interacting with the Travis CI API."""

from __future__ import unicode_literals

import logging
import json

from django.utils.http import urlquote_plus
from django.utils.six.moves.urllib.request import urlopen
from django.utils.translation import ugettext_lazy as _

from rbintegrations.util.urlrequest import URLRequest


logger = logging.getLogger(__name__)


class TravisAPI(object):
    """Object for interacting with the Travis CI API."""

    OPEN_SOURCE_ENDPOINT = 'O'
    PRIVATE_PROJECT_ENDPOINT = 'P'
    ENTERPRISE_ENDPOINT = 'E'

    ENDPOINT_CHOICES = (
        (OPEN_SOURCE_ENDPOINT, _('Open Source (travis-ci.org)')),
        (PRIVATE_PROJECT_ENDPOINT, _('Private Projects (travis-ci.com)')),
        (ENTERPRISE_ENDPOINT, _('Enterprise (custom domain)')),
    )

    OPEN_SOURCE_ENDPOINT_URL = 'https://api.travis-ci.org'
    PRIVATE_PROJECT_ENDPOINT_URL = 'https://api.travis-ci.com'

    def __init__(self, config):
        """Initialize the object.

        Args:
            config (dict):
                The integration config to use.

        Raises:
            ValueError:
                The provided endpoint type was not valid.
        """
        endpoint = config.get('travis_endpoint')

        if endpoint == self.OPEN_SOURCE_ENDPOINT:
            self.endpoint = self.OPEN_SOURCE_ENDPOINT_URL
        elif endpoint == self.PRIVATE_PROJECT_ENDPOINT:
            self.endpoint = self.PRIVATE_PROJECT_ENDPOINT_URL
        elif endpoint == self.ENTERPRISE_ENDPOINT:
            custom_endpoint = config.get('travis_custom_endpoint')

            if custom_endpoint.endswith('/'):
                custom_endpoint = custom_endpoint[:-1]

            self.endpoint = '%s/api' % custom_endpoint
        else:
            raise ValueError('Unexpected value for Travis CI endpoint: %s'
                             % endpoint)

        self.token = config.get('travis_ci_token')

    def lint(self, travis_yml):
        """Lint a prospective travis.yml file.

        Args:
            travis_yml (unicode):
                The contents of the travis.yml file to validate.

        Returns:
            dict:
            The parsed contents of the JSON response.

        Raises:
            urllib2.URLError:
                The HTTP request failed.

            Exception:
                Some other exception occurred when trying to parse the results.
        """
        data = self._make_request('%s/lint' % self.endpoint,
                                  body=travis_yml,
                                  method='POST',
                                  content_type='text/yaml')
        return json.loads(data)

    def get_config(self):
        """Return the Travis CI server's config.

        Returns:
            dict:
            The parsed contents of the JSON response.

        Raises:
            urllib2.URLError:
                The HTTP request failed.
        """
        # This request can't go through _make_request because this endpoint
        # isn't available with API version 3 and doesn't require
        # authentication.
        u = urlopen(URLRequest('%s/config' % self.endpoint))
        return json.loads(u.read())

    def get_user(self):
        """Return the Travis CI user.

        Returns:
            dict:
            The parsed contents of the JSON response.

        Raises:
            urllib2.URLError:
                The HTTP request failed.
        """
        data = self._make_request('%s/user' % self.endpoint)
        return json.loads(data)

    def start_build(self, repo_slug, travis_config, commit_message,
                    branch=None):
        """Start a build.

        Args:
            repo_slug (unicode):
                The "slug" for the repository based on it's location on GitHub.

            travis_config (unicode):
                The contents of the travis config to use when doing the build.

            commit_message (unicode):
                The text to use as the commit message displayed in the Travis
                UI.

            branch (unicode, optional):
                The branch name to use.

        Returns:
            dict:
            The parsed contents of the JSON response.

        Raises:
            urllib2.URLError:
                The HTTP request failed.
        """
        travis_config['merge_mode'] = 'replace'

        request_data = {
            'request': {
                'message': commit_message,
                'config': travis_config,
            },
        }

        if branch:
            request_data['request']['branch'] = branch

        data = self._make_request(
            '%s/repo/%s/requests' % (self.endpoint,
                                     urlquote_plus(repo_slug)),
            body=json.dumps(request_data),
            method='POST',
            content_type='application/json')

        return json.loads(data)

    def _make_request(self, url, body=None, method='GET',
                      content_type='application/json'):
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
        logger.debug('Making request to Travis CI %s', url)

        headers = {
            'Accept': 'application/json',
            'Authorization': 'token %s' % self.token,
            'Travis-API-Version': '3',
        }

        if content_type:
            headers['Content-Type'] = content_type

        request = URLRequest(
            url,
            body=body,
            method=method,
            headers=headers)

        u = urlopen(request)
        return u.read()
