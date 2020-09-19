"""Views for the Travis CI integration (webhook listener)."""

from __future__ import unicode_literals

import base64
import json
import logging

import cryptography
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.generic import View
from reviewboard.integrations.models import IntegrationConfig
from reviewboard.reviews.models.status_update import StatusUpdate

from rbintegrations.travisci.api import TravisAPI


logger = logging.getLogger(__name__)


class TravisCIWebHookView(View):
    """The view to handle webhook notifications from a Travis CI build."""

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
        payload = json.loads(request.POST['payload'])

        try:
            payload_env = payload['matrix'][0]['config']['env']
        except (IndexError, KeyError):
            error = 'Got event without an env in config.'
            logger.error('Travis CI webhook: %s', error, request=request)
            return HttpResponseBadRequest(error)

        integration_config_id = None
        status_update_id = None

        for line in payload_env:
            key, value = line.split('=', 1)

            if key == 'REVIEWBOARD_STATUS_UPDATE_ID':
                status_update_id = int(value)
            elif key == 'REVIEWBOARD_TRAVIS_INTEGRATION_CONFIG_ID':
                integration_config_id = int(value)

        if status_update_id is None:
            error = 'Unable to find REVIEWBOARD_STATUS_UPDATE_ID in payload.'
            logger.error('Travis CI webhook: %s', error, request=request)
            return HttpResponseBadRequest(error)

        if integration_config_id is None:
            error = ('Unable to find REVIEWBOARD_TRAVIS_INTEGRATION_CONFIG_ID '
                     'in payload.')
            logger.error('Travis CI webhook: %s', error, request=request)
            return HttpResponseBadRequest(error)

        logger.debug('Got Travis CI webhook event for Integration Config %d '
                     '(status update %d)',
                     integration_config_id, status_update_id, request=request)

        try:
            integration_config = IntegrationConfig.objects.get(
                pk=integration_config_id)
        except IntegrationConfig.DoesNotExist:
            error = ('Unable to find matching integration config ID %d.'
                     % integration_config_id)
            logger.error('Travis CI webhook: %s', error, request=request)
            return HttpResponseBadRequest(error)

        if not self._validate_signature(request, integration_config):
            error = ('Invalid Travis CI webhook signature for status '
                     'update %d.'
                     % status_update_id)
            return HttpResponseBadRequest(error)

        try:
            status_update = StatusUpdate.objects.get(pk=status_update_id)
        except StatusUpdate.DoesNotExist:
            error = ('Unable to find matching status update ID %d.'
                     % status_update_id)
            logger.error('Travis CI webhook: %s', error, request=request)
            return HttpResponseBadRequest(error)

        status_update.url = payload['build_url']
        status_update.url_text = 'View Build'

        build_state = payload['state']

        if build_state == 'passed':
            status_update.state = StatusUpdate.DONE_SUCCESS
            status_update.description = 'build succeeded.'
        elif build_state == 'started':
            status_update.state = StatusUpdate.PENDING
            status_update.description = 'building...'
        elif build_state in ('errored', 'failed'):
            status_update.state = StatusUpdate.DONE_FAILURE
            status_update.description = 'build failed.'
        else:
            logger.warning('Got unexpected Travis CI build state "%s"',
                           build_state)

        status_update.save()

        return HttpResponse()

    def _validate_signature(self, request, integration_config):
        """Validate the webhook signature.

        This will fetch the public key from the appropriate Travis CI server
        and use it to verify the signature of the payload.

        Args:
            request (django.http.HttpRequest):
                The HTTP request for the webhook.

            integration_config (reviewboard.integrations.models.
                                IntegrationConfig):
                The integration configuration that requested the Travis CI job.

        Returns:
            bool:
            True if the signature validated correctly.
        """
        api = TravisAPI(integration_config)

        try:
            data = api.get_config()
        except Exception as e:
            logger.error('Failed to fetch config information from Travis CI '
                         'server at %s: %s',
                         api.endpoint, e, request=request)
            return False

        try:
            crypto_primitives = cryptography.hazmat.primitives

            signature = base64.b64decode(request.META['HTTP_SIGNATURE'])
            backend = cryptography.hazmat.backends.default_backend()
            public_key = \
                data['config']['notifications']['webhook']['public_key']
            key = crypto_primitives.serialization.load_pem_public_key(
                public_key.encode('ascii'), backend)

            key.verify(
                signature,
                request.POST['payload'].encode('ascii'),
                crypto_primitives.asymmetric.padding.PKCS1v15(),
                crypto_primitives.hashes.SHA1())
            return True
        except cryptography.exceptions.InvalidSignature:
            logger.error('Unable to verify signature for Travis CI webhook.',
                         request=request)
            return False
        except Exception as e:
            logger.exception('Unexpected error while verifying Travis CI '
                             'signature: %s',
                             e, request=request)
            return False
