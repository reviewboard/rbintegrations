"""Forms for Discord Integration."""

from __future__ import unicode_literals

from django import forms
from django.utils.translation import ugettext_lazy as _
from djblets.forms.fields import ConditionsField
from reviewboard.integrations.forms import IntegrationConfigForm
from reviewboard.reviews.conditions import ReviewRequestConditionChoices


class DiscordIntegrationConfigForm(IntegrationConfigForm):
    """Admin configuration form for Discord.

    This allows an administrator to set up a chat configuration for sending
    messages to a given Discord WebHook URL based on the specified
    conditions.
    """

    conditions = ConditionsField(ReviewRequestConditionChoices,
                                 label=_('Conditions'))

    webhook_url = forms.CharField(
        label=_('Webhook URL'),
        required=True,
        help_text=_('Your unique Discord webhook URL. This can be found at '
                    'the "Integration" page after selecting '
                    '"Server Settings".'),
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
                'fields': ('conditions', ),
            }),
            ('Where To Post', {
                'description': _(
                    'To start, add a new webhook service integration on '
                    'Discord. You can then provide the unique webhook URL '
                    'below. Please ensure that the Discord webhook is tied '
                    'to the correct channel.'
                ),
                'fields': ('webhook_url', ),
                'classes': ('wide', )
            }),
        )
