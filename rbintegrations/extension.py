from __future__ import unicode_literals

from django.conf.urls import include, url
from django.utils.translation import ugettext_lazy as _
from reviewboard.extensions.base import Extension
from reviewboard.extensions.hooks import IntegrationHook, URLHook

from rbintegrations.circleci.integration import CircleCIIntegration
from rbintegrations.idonethis.integration import IDoneThisIntegration
from rbintegrations.slack.integration import SlackIntegration
from rbintegrations.travisci.integration import TravisCIIntegration


class RBIntegrationsExtension(Extension):
    """Extends Review Board with support for many common integrations."""

    metadata = {
        'Name': _('Review Board Integrations'),
        'Summary': _('A set of third-party service integrations for '
                     'Review Board.'),
    }

    integrations = [
        CircleCIIntegration,
        IDoneThisIntegration,
        SlackIntegration,
        TravisCIIntegration,
    ]

    css_bundles = {
        'travis-ci-integration-config': {
            'source_filenames': ['css/travisci/integration-config.less'],
        },
    }

    js_bundles = {
        'travis-ci-integration-config': {
            'source_filenames': ['js/travisci/integrationConfig.es6.js'],
        },
    }

    def initialize(self):
        """Initialize the extension."""
        for integration_cls in self.integrations:
            IntegrationHook(self, integration_cls)

        URLHook(self, [
            url(r'^rbintegrations/travis-ci/',
                include('rbintegrations.travisci.urls')),
            url(r'^rbintegrations/circle-ci/',
                include('rbintegrations.circleci.urls')),
        ])
