"""Views for the Trello integration."""

from __future__ import unicode_literals

import json
import logging

from django.http import HttpResponse
from django.utils.six.moves.urllib.parse import urlencode
from django.utils.six.moves.urllib.request import urlopen
from django.views.generic import View

from reviewboard.integrations.base import get_integration_manager
from reviewboard.reviews.views import ReviewRequestViewMixin


logger = logging.getLogger(__name__)


class TrelloCardSearchView(ReviewRequestViewMixin, View):
    """The view to search for Trello cards (for use with auto-complete)."""

    def get(self, request, **kwargs):
        """Perform a search for cards.

        Args:
            request (django.http.HttpRequest):
                The request.

            **kwargs (dict):
                Additional keyword arguments.

        Returns:
            django.http.HttpResponse:
            A response containing JSON with a list of cards matching the
            search criteria.
        """
        from rbintegrations.trello.integration import TrelloIntegration

        integration_manager = get_integration_manager()
        integration = integration_manager.get_integration(
            TrelloIntegration.integration_id)

        configs = (
            config
            for config in integration.get_configs(
                self.review_request.local_site)
            if config.match_conditions(form_cls=integration.config_form_cls,
                                       review_request=self.review_request)
        )

        results = []

        params = {
            'card_board': 'true',
            'card_fields': 'id,name,shortUrl',
            'card_list': 'true',
            'cards_limit': 20,
            'modelTypes': 'cards',
            'partial': 'true',
            'query': request.GET.get('q'),
        }

        for config in configs:
            params['key'] = config.settings['trello_api_key']
            params['token'] = config.settings['trello_api_token']

            url = 'https://api.trello.com/1/search?%s' % urlencode(params)

            try:
                response = urlopen(url)
                data = json.loads(response.read())

                for card in data['cards']:
                    results.append({
                        'id': card['id'],
                        'name': card['name'],
                        'board': card.get('board', {}).get('name', ''),
                        'list': card.get('list', {}).get('name', ''),
                        'url': card['shortUrl'],
                    })
            except Exception as e:
                logger.exception('Unexpected error when searching for Trello '
                                 'cards: %s',
                                 e)

        return HttpResponse(json.dumps(results),
                            content_type='application/json')
