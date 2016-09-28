from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy as _
from reviewboard.extensions.base import Extension
from reviewboard.extensions.hooks import IntegrationHook

from rbintegrations.slack.integration import SlackIntegration


class RBIntegrationsExtension(Extension):
    """Extends Review Board with support for many common integrations."""

    metadata = {
        'Name': _('Review Board Integrations'),
        'Summary': _('A set of third-party service integrations for '
                     'Review Board.'),
    }

    integrations = [
        SlackIntegration,
    ]

    def initialize(self):
        """Initialize the extension."""
        for integration_cls in self.integrations:
            IntegrationHook(self, integration_cls)
