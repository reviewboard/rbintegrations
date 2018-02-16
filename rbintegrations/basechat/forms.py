"""Forms for chat integrations."""

from __future__ import unicode_literals

from django import forms
from django.utils.translation import ugettext_lazy as _
from djblets.forms.fields import ConditionsField
from reviewboard.integrations.forms import IntegrationConfigForm
from reviewboard.reviews.conditions import ReviewRequestConditionChoices


class BaseChatIntegrationConfigForm(IntegrationConfigForm):
    """Form for configuring chat integration.

    This allows an administrator to set up a chat configuration for sending
    messages to a given WebHook URL based on the specified
    conditions.
    """

    conditions = ConditionsField(ReviewRequestConditionChoices,
                                 label=_('Conditions'))

    webhook_url = forms.CharField(
        label=_('Webhook URL'),
        required=True,
        help_text=_('Your unique webhook URL. This can be '
                    'found in the "Setup Instructions" box inside the '
                    'Incoming WebHooks integration.'),
        widget=forms.TextInput(attrs={
            'size': 80,
        }))

    channel = forms.CharField(
        label=_('Send to Channel'),
        required=False,
        help_text=_('The optional name of the channel review request updates '
                    'are sent to. By default, the configured channel on the '
                    'Incoming Webhook will be used.'),
        widget=forms.TextInput(attrs={
            'size': 40,
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
                    'To start, add a new "Incoming WebHooks" service '
                    'integration. You can then provide the "Unique WebHook '
                    'URL" below, and optionally choose a custom channel to '
                    'send notifications to.'
                ),
                'fields': ('webhook_url', 'channel'),
                'classes': ('wide',)
            }),
        )
