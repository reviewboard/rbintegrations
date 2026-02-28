"""Review Board extension for common integrations."""

from __future__ import annotations

from django.urls import include, path
from django.utils.translation import gettext_lazy as _
from reviewboard.extensions.base import Extension
from reviewboard.extensions.hooks import IntegrationHook, URLHook
from reviewboard.urls import reviewable_url_names, review_request_url_names


class RBIntegrationsExtension(Extension):
    """Extends Review Board with support for many common integrations."""

    metadata = {
        'Name': _('Review Board Integrations'),
        'Summary': _('A set of third-party service integrations for '
                     'Review Board.'),
    }

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
                'js/fields/index.ts',
                'js/trello/trelloFieldView.es6.js',
            ],
            'apply_to': reviewable_url_names + review_request_url_names,
        },
        'asana-integration-config': {
            'source_filenames': [
                'js/asana/integrationConfig.ts',
            ],
        },
        'travis-ci-integration-config': {
            'source_filenames': ['js/travisci/integrationConfig.es6.js'],
        },
    }

    def initialize(self) -> None:
        """Initialize the extension."""
        from rbintegrations.asana.integration import AsanaIntegration
        from rbintegrations.circleci.integration import CircleCIIntegration
        from rbintegrations.discord.integration import DiscordIntegration
        from rbintegrations.gitlabci.integration import GitLabCIIntegration
        from rbintegrations.idonethis.integration import IDoneThisIntegration
        from rbintegrations.jenkinsci.integration import JenkinsCIIntegration
        from rbintegrations.matrix.integration import MatrixIntegration
        from rbintegrations.mattermost.integration import MattermostIntegration
        from rbintegrations.msteams.integration import MSTeamsIntegration
        from rbintegrations.slack.integration import SlackIntegration
        from rbintegrations.travisci.integration import TravisCIIntegration
        from rbintegrations.trello.integration import TrelloIntegration

        IntegrationHook(self, AsanaIntegration)
        IntegrationHook(self, CircleCIIntegration)
        IntegrationHook(self, DiscordIntegration)
        IntegrationHook(self, GitLabCIIntegration)
        IntegrationHook(self, IDoneThisIntegration)
        IntegrationHook(self, JenkinsCIIntegration)
        IntegrationHook(self, MatrixIntegration)
        IntegrationHook(self, MattermostIntegration)
        IntegrationHook(self, MSTeamsIntegration)
        IntegrationHook(self, SlackIntegration)
        IntegrationHook(self, TravisCIIntegration)
        IntegrationHook(self, TrelloIntegration)

        URLHook(self, [
            path('rbintegrations/asana/',
                 include('rbintegrations.asana.urls')),
            path('rbintegrations/circle-ci/',
                 include('rbintegrations.circleci.urls')),
            path('rbintegrations/gitlab-ci/',
                 include('rbintegrations.gitlabci.urls')),
            path('rbintegrations/travis-ci/',
                 include('rbintegrations.travisci.urls')),
            path('rbintegrations/trello/',
                 include('rbintegrations.trello.urls')),
        ])
