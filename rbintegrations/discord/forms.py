"""Forms for Discord Integration."""

from django import forms
from django.utils.translation import gettext_lazy as _
from reviewboard.integrations.forms import IntegrationConfigForm

from rbintegrations.util.conditions import ReviewRequestConditionsField


class DiscordIntegrationConfigForm(IntegrationConfigForm):
    """Admin configuration form for Discord.

    This allows an administrator to set up a chat configuration for sending
    messages to a given Discord WebHook URL based on the specified
    conditions.
    """

    conditions = ReviewRequestConditionsField()

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
