from __future__ import unicode_literals

from django.conf.urls import include, url
from django.utils.translation import ugettext_lazy as _
from reviewboard.extensions.base import Extension
from reviewboard.extensions.hooks import IntegrationHook, URLHook
from reviewboard.urls import reviewable_url_names, review_request_url_names

from rbintegrations.asana.integration import AsanaIntegration
from rbintegrations.circleci.integration import CircleCIIntegration
from rbintegrations.discord.integration import DiscordIntegration
from rbintegrations.idonethis.integration import IDoneThisIntegration
from rbintegrations.jenkinsci.integration import JenkinsCIIntegration
from rbintegrations.mattermost.integration import MattermostIntegration
from rbintegrations.slack.integration import SlackIntegration
from rbintegrations.travisci.integration import TravisCIIntegration
from rbintegrations.trello.integration import TrelloIntegration


class RBIntegrationsExtension(Extension):
    """Extends Review Board with support for many common integrations."""

    metadata = {
        'Name': _('Review Board Integrations'),
        'Summary': _('A set of third-party service integrations for '
                     'Review Board.'),
    }

    integrations = [
        AsanaIntegration,
        CircleCIIntegration,
        DiscordIntegration,
        IDoneThisIntegration,
        JenkinsCIIntegration,
        MattermostIntegration,
        SlackIntegration,
        TravisCIIntegration,
        TrelloIntegration
    ]

    css_bundles = {
        'fields': {
            'source_filenames': [
                'css/asana/asana.less',
                'css/trello/trello.less',
            ],
            'apply_to': reviewable_url_names + review_request_url_names,
        },
        'asana-integration-config': {
            'source_filenames': ['css/asana/integration-config.less'],
        },
        'travis-ci-integration-config': {
            'source_filenames': ['css/travisci/integration-config.less'],
        },
    }

    js_bundles = {
        'fields': {
            'source_filenames': [
                'js/asana/asanaFieldView.es6.js',
                'js/trello/trelloFieldView.es6.js',
            ],
            'apply_to': reviewable_url_names + review_request_url_names,
        },
        'asana-integration-config': {
            'source_filenames': ['js/asana/integrationConfig.es6.js'],
        },
        'travis-ci-integration-config': {
            'source_filenames': ['js/travisci/integrationConfig.es6.js'],
        },
    }

    def initialize(self):
        """Initialize the extension."""
        for integration_cls in self.integrations:
            IntegrationHook(self, integration_cls)

        URLHook(self, [
            url(r'^rbintegrations/asana/',
                include('rbintegrations.asana.urls')),
            url(r'^rbintegrations/circle-ci/',
                include('rbintegrations.circleci.urls')),
            url(r'^rbintegrations/travis-ci/',
                include('rbintegrations.travisci.urls')),
            url(r'^rbintegrations/trello/',
                include('rbintegrations.trello.urls')),
        ])
