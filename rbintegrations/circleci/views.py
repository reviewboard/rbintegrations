"""Views for the CircleCI integration (webhook listener)."""

from __future__ import unicode_literals

import json
import logging

from django.http import HttpResponse, HttpResponseBadRequest
from django.views.generic import View
from reviewboard.reviews.models.status_update import StatusUpdate


logger = logging.getLogger(__name__)


class CircleCIWebHookView(View):
    """The view to handle webhook notifications from a CircleCI build."""

    STATUS_STATE_MAP = {
        'canceled': StatusUpdate.DONE_FAILURE,
        'infrastructure_fail': StatusUpdate.ERROR,
        'failed': StatusUpdate.DONE_FAILURE,
        'fixed': StatusUpdate.DONE_SUCCESS,
        'success': StatusUpdate.DONE_SUCCESS,
        'queued': StatusUpdate.PENDING,
        'running': StatusUpdate.PENDING,
        'scheduled': StatusUpdate.PENDING,
        'timedout': StatusUpdate.TIMEOUT,
    }

    STATUS_DESCRIPTION_MAP = {
        'canceled': 'build canceled.',
        'infrastructure_fail': 'build infrastructure failure.',
        'failed': 'build failed.',
        'fixed': 'build succeeded.',
        'success': 'build succeded.',
        'queued': 'build queued.',
        'running': 'build running.',
        'scheduled': 'build scheduled.',
        'timedout': 'build running.',
    }

    def post(self, request, *args, **kwargs):
        """Handle the POST.

        Args:
            request (django.http.HttpRequest):
                The HTTP request.

            *args (tuple):
                Additional positional arguments, parsed from the URL.

            **kwargs (dict):
                Additional keyword arguments, parsed from the URL.

        Returns:
            django.http.HttpResponse:
            A response.
        """
        payload = json.loads(request.body)

        try:
            build_parameters = payload['payload']['build_parameters']
        except KeyError:
            error = 'Unable to find build_parameters in payload.'
            logger.error('CircleCI webhook: %s', error, request=request)
            return HttpResponseBadRequest(error)

        try:
            review_request_id = \
                build_parameters['REVIEWBOARD_REVIEW_REQUEST']
            local_site_name = \
                build_parameters.get('REVIEWBOARD_LOCAL_SITE')
            status_update_id = \
                build_parameters['REVIEWBOARD_STATUS_UPDATE_ID']

            if local_site_name:
                local_site_log = ' (local_site %s)' % local_site_name
            else:
                local_site_log = ''
        except KeyError:
            # This was a normal build, not a review request.
            return HttpResponse()

        logger.debug('Got CircleCI webhook event for review request %d%s '
                     '(status update %d)',
                     review_request_id, local_site_log, status_update_id,
                     request=request)

        try:
            status_update = StatusUpdate.objects.get(pk=status_update_id)
        except StatusUpdate.DoesNotExist:
            error = ('Unable to find matching status update ID %d'
                     % status_update_id)
            logger.error('CircleCI webhook: %s', error, request=request)
            return HttpResponseBadRequest(error)

        status = payload['payload']['status']

        try:
            status_update.state = self.STATUS_STATE_MAP[status]
            status_update.description = self.STATUS_DESCRIPTION_MAP[status]
            status_update.save()
        except KeyError:
            # There are a few other possibilities for the "status" field but
            # we don't care about them.
            pass

        return HttpResponse()
