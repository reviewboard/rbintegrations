"""Forms for Microsoft Teams Integration.

Version Added:
    4.0
"""

from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _
from reviewboard.integrations.forms import IntegrationConfigForm
from reviewboard.reviews.conditions import ReviewRequestConditionChoices

from rbintegrations.util.conditions import ReviewRequestConditionsField


MS_TEAMS_INTEGRATION_DOCS_URL = (
    'https://www.reviewboard.org/integrations/'
    'microsoft-teams/#microsoft-teams-setup'
)


class MSTeamsIntegrationConfigForm(IntegrationConfigForm):
    """Admin configuration form for Microsoft Teams.

    This allows an administrator to set up a chat configuration for sending
    messages to a given Microsoft Teams WebHook URL based on the specified
    conditions.

    Version Added:
        4.0
    """

    conditions = ReviewRequestConditionsField()

    webhook_url = forms.CharField(
        label=_('WebHook URL'),
        required=True,
        help_text=_('Your Microsoft Teams WebHook URL.'),
        widget=forms.TextInput(attrs={
            'size': 80,
        }))

    class Meta:
        fieldsets = (
            ('What To Post', {
                'description': _(
                    'You can choose which review requests would be posted by '
                    'choosing the repositories and groups to match against.'
                ),
                'fields': ('conditions',),
            }),
            ('Where To Post', {
                'description': _(
                    f'Create a new Incoming WebHook on Microsoft Teams then '
                    f'enter its WebHook URL below. See '
                    f'<a href="{MS_TEAMS_INTEGRATION_DOCS_URL}">'
                    f'here</a> for more information.'
                ),
                'fields': ('webhook_url',),
                'classes': ('wide',)
            }),
        )
