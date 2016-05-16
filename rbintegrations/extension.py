from __future__ import unicode_literals

from reviewboard.extensions.base import Extension
from reviewboard.extensions.hooks import IntegrationHook

from rbintegrations.slack.integration import SlackIntegration


class RBIntegrationsExtension(Extension):
    """Extends Review Board with support for many common integrations."""

    metadata = {
        'Name': 'Review Board Integrations',
        'Summary': 'A set of third-party serivce integrations for '
                   'Review Board.',
    }

    integrations = [
    ]

    def initialize(self):
        """Initialize the extension."""
        for integration_cls in self.integrations:
            IntegrationHook(self, integration_cls)
