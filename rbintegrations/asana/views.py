"""Views for the Asana integration."""

from __future__ import unicode_literals

import json
import logging

import asana
from django.http import HttpResponse
from django.utils import six
from django.views.generic import View

from reviewboard.accounts.mixins import CheckLoginRequiredViewMixin
from reviewboard.integrations.base import get_integration_manager
from reviewboard.reviews.views import ReviewRequestViewMixin
from reviewboard.site.mixins import CheckLocalSiteAccessViewMixin


logger = logging.getLogger(__name__)


class AsanaTaskSearchView(ReviewRequestViewMixin, View):
    """The view to search for tasks (for use with auto-complete)."""

    def get(self, request, **kwargs):
        """Perform a search for tasks.

        Args:
            request (django.http.HttpRequest):
                The request.

            **kwargs (dict):
                Additional keyword arguments.

        Returns:
            django.http.HttpResponse:
            A response containing JSON with a list of tasks matching the
            search criteria.
        """
        from rbintegrations.asana.integration import AsanaIntegration

        integration_manager = get_integration_manager()
        integration = integration_manager.get_integration(
            AsanaIntegration.integration_id)

        configs = (
            config
            for config in integration.get_configs(
                self.review_request.local_site)
            if config.match_conditions(form_cls=integration.config_form_cls,
                                       review_request=self.review_request)
        )

        results = []

        params = {
            'type': 'task',
            'query': request.GET.get('q'),
            'count': 20,
            'opt_fields': ['completed', 'name', 'notes'],
        }

        for config in configs:
            try:
                client = asana.Client.access_token(
                    config.settings['asana_access_token'])

                workspace = config.settings['asana_workspace']

                results.append({
                    'workspace': config.settings['asana_workspace_name'],
                    'workspace_id': workspace,
                    'tasks': list(
                        client.workspaces.typeahead(workspace, params)),
                })
            except Exception as e:
                logger.exception('Unexpected error when searching for Asana '
                                 'tasks: %s',
                                 e)

        return HttpResponse(json.dumps(results),
                            content_type='application/json')


class AsanaWorkspaceListView(CheckLoginRequiredViewMixin,
                             CheckLocalSiteAccessViewMixin, View):
    """The view to fetch the available workspaces.

    This is used by the integration config form to select a workspace.
    """

    def get(self, request):
        """Return the available workspaces.

        Args:
            request (django.http.HttpRequest):
                The request.

        Returns:
            django.http.HttpResponse:
            A response containing JSON with a list of avaliable Asana
            workspaces.
        """
        asana_api_key = request.GET.get('api_key')

        try:
            client = asana.Client.access_token(asana_api_key)
            results = {
                'result': 'success',
                'data': list(client.workspaces.find_all())
            }
        except asana.error.NoAuthorizationError:
            results = {
                'result': 'error',
                'error': 'Authentication failed',
            }
        except Exception as e:
            results = {
                'result': 'error',
                'error': six.text_type(e)
            }

        return HttpResponse(json.dumps(results),
                            content_type='application/json')
