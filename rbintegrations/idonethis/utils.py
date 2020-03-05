"""Utility functions for I Done This integration."""

from __future__ import unicode_literals

import json
import logging

from django.core.cache import cache
from django.utils.six.moves.urllib.error import HTTPError, URLError
from django.utils.six.moves.urllib.request import Request, urlopen
from djblets.cache.backend import cache_memoize, make_cache_key
from reviewboard.scmtools.crypto_utils import decrypt_password


IDONETHIS_API_BASE_URL = 'https://beta.idonethis.com/api/v2'
TEAM_IDS_CACHE_EXPIRATION = 24 * 60 * 60  # 1 day


def create_idonethis_request(request_path, api_token, json_payload=None):
    """Create a urllib request for the I Done This API.

    Args:
        request_path (unicode):
            The API request path, relative to the base API URL.

        api_token (unicode):
            The user's API token for authorization.

        json_payload (unicode, optional):
            JSON payload for a POST request. If this is omitted,
            the request will be a GET.

    Returns:
        urllib2.Request:
        The I Done This API request with the provided details.
    """
    url = '%s/%s' % (IDONETHIS_API_BASE_URL, request_path)
    headers = {
        'Authorization': 'Token %s' % api_token,
    }

    if json_payload is not None:
        headers['Content-Type'] = 'application/json'
        json_payload = json_payload.encode('utf-8')

    return Request(url, json_payload, headers)


def get_user_api_token(user):
    """Return the user's API token for I Done This.

    Args:
        user (django.contrib.auth.models.User):
            The user whose API token should be retrieved.

    Returns:
        unicode:
        The user's API token, or ``None`` if the user has not set one.
    """
    try:
        settings = user.get_profile().settings['idonethis']
        return decrypt_password(settings['api_token'])
    except KeyError:
        return None


def get_user_team_ids(user):
    """Return a set of I Done This team IDs that the user belongs to.

    Retrieves the set of teams from the I Done This API and caches it to
    avoid excessive requests. Team membership is not expected to change
    frequently, but the cache can be manually deleted if necessary.

    Args:
        user (django.contrib.auth.models.User):
            The user whose cached team IDs should be retrieved.

    Returns:
        set:
        The user's team IDs, or ``None`` if they could not be retrieved.
    """
    def _get_user_team_ids_uncached():
        request = create_idonethis_request(request_path='teams',
                                           api_token=api_token)
        logging.debug('IDoneThis: Loading teams for user "%s", '
                      'request "%s %s"',
                      user.username,
                      request.get_method(),
                      request.get_full_url())

        try:
            teams_data = urlopen(request).read()
        except (HTTPError, URLError) as e:
            if isinstance(e, HTTPError):
                error_info = '%s, error data: %s' % (e, e.read())
            else:
                error_info = e.reason

            logging.error('IDoneThis: Failed to load teams for user "%s", '
                          'request "%s %s": %s',
                          user.username,
                          request.get_method(),
                          request.get_full_url(),
                          error_info)
            raise

        return set(t['hash_id'] for t in json.loads(teams_data))

    api_token = get_user_api_token(user)

    if not api_token:
        return None

    try:
        return set(cache_memoize(_make_user_team_ids_cache_key(user),
                                 _get_user_team_ids_uncached,
                                 expiration=TEAM_IDS_CACHE_EXPIRATION))
    except Exception as e:
        logging.error('IDoneThis: Failed to load teams for user "%s": %s',
                      user.username,
                      e)
        return None


def delete_cached_user_team_ids(user):
    """Delete the user's cached I Done This team IDs.

    Args:
        user (django.contrib.auth.models.User):
            The user whose cached team IDs should be deleted.
    """
    logging.debug('IDoneThis: Deleting cached team IDs for user "%s"',
                  user.username)
    cache.delete(make_cache_key(_make_user_team_ids_cache_key(user)))


def _make_user_team_ids_cache_key(user):
    """Make a cache key for the user's I Done This team IDs.

    Args:
        user (django.contrib.auth.models.User):
            The user to generate the cache key for.

    Returns:
        unicode:
        The cache key for the user's team IDs.
    """
    return 'idonethis-team_ids-%s' % user.username
