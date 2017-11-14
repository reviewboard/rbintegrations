"""Integration for associating review requests with Trello cards."""

from __future__ import unicode_literals

from django.utils.functional import cached_property
from reviewboard.extensions.hooks import ReviewRequestFieldsHook
from reviewboard.integrations import Integration

from rbintegrations.trello.fields import TrelloField
from rbintegrations.trello.forms import TrelloIntegrationConfigForm


class TrelloIntegration(Integration):
    """Integrates Review Board with Trello."""

    name = 'Trello'
    description = 'Associate Trello cards with your review requests.'
    config_form_cls = TrelloIntegrationConfigForm

    def initialize(self):
        """Initialize the integration hooks."""
        ReviewRequestFieldsHook(self, 'main', [TrelloField])

    @cached_property
    def icon_static_urls(self):
        """The icons used for the integration."""
        from rbintegrations.extension import RBIntegrationsExtension

        extension = RBIntegrationsExtension.instance

        return {
            '1x': extension.get_static_url('images/trello/icon.png'),
            '2x': extension.get_static_url('images/trello/icon@2x.png'),
        }
