"""Views for the Asana integration."""

from __future__ import annotations

import json
import logging
from typing import Iterable, cast

import asana
import asana.rest
from django.http import HttpRequest, HttpResponse
from django.views.generic import View
from djblets.util.typing import JSONValue
from reviewboard.accounts.mixins import CheckLoginRequiredViewMixin
from reviewboard.integrations.base import get_integration_manager
from reviewboard.reviews.views import ReviewRequestViewMixin
from reviewboard.site.mixins import CheckLocalSiteAccessViewMixin


logger = logging.getLogger(__name__)


class AsanaTaskSearchView(ReviewRequestViewMixin, View):
    """The view to search for tasks (for use with auto-complete)."""

    def get(
        self,
        request: HttpRequest,
        **kwargs,
    ) -> HttpResponse:
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
        integration_id = AsanaIntegration.integration_id
        assert integration_id is not None

        integration_manager = get_integration_manager()
        integration = cast(
            AsanaIntegration,
            integration_manager.get_integration(integration_id))

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
            'opt_fields': 'completed,name,notes',
        }

        for config in configs:
            try:
                asana_config = asana.Configuration()
                asana_config.access_token = \
                    config.settings['asana_access_token']

                api_client = asana.ApiClient(asana_config)
                typeahead_api = asana.TypeaheadApi(api_client)

                workspace = config.settings['asana_workspace']

                tasks = cast(
                    Iterable[JSONValue],
                    typeahead_api.typeahead_for_workspace(
                        workspace, 'task', params))

                results.append({
                    'workspace': config.settings['asana_workspace_name'],
                    'workspace_id': workspace,
                    'tasks': list(tasks),
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

    def get(
        self,
        request: HttpRequest,
    ) -> HttpResponse:
        """Return the available workspaces.

        Args:
            request (django.http.HttpRequest):
                The request.

        Returns:
            django.http.HttpResponse:
            A response containing JSON with a list of available Asana
            workspaces.
        """
        asana_api_key = request.GET.get('api_key')
        assert asana_api_key is not None

        try:
            configuration = asana.Configuration()
            configuration.access_token = asana_api_key

            api_client = asana.ApiClient(configuration)
            workspaces_api = asana.WorkspacesApi(api_client)
            workspaces = cast(
                Iterable[JSONValue],
                workspaces_api.get_workspaces({}))

            results = {
                'result': 'success',
                'data': list(workspaces),
            }
        except asana.rest.ApiException as e:
            results = {
                'result': 'error',
                'error': f'Could not communicate with Asana: {e.reason}',
            }
        except Exception as e:
            results = {
                'result': 'error',
                'error': str(e),
            }

        return HttpResponse(json.dumps(results),
                            content_type='application/json')
