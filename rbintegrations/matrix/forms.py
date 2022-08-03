"""Forms for Matrix chat integrations."""

from django import forms
from django.utils.translation import gettext_lazy as _
from djblets.forms.fields import ConditionsField
from reviewboard.integrations.forms import IntegrationConfigForm
from reviewboard.reviews.conditions import ReviewRequestConditionChoices


class MatrixIntegrationConfigForm(IntegrationConfigForm):
    """Form for configuring Matrix integration.

    This allows an administrator to set up a chat configuration for sending
    messages based on a given access token based on the specified
    conditions.
    """

    conditions = ConditionsField(ReviewRequestConditionChoices,
                                 label=_('Conditions'))

    access_token = forms.CharField(
        label=_('Access Token'),
        required=True,
        help_text=_('Your unique access Token. In Element, this can be found '
                    'by going to Profile > All settings > Help & About > '
                    'Advanced.'),
        widget=forms.TextInput(attrs={
            'size': 80,
        }))

    room_id = forms.CharField(
        label=_('Room ID'),
        required=True,
        help_text=_('The ID of the room that review request updates will be '
                    'sent to. In Element, this can be found by clicking on '
                    'the 3 dots beside the room icon to access Settings and '
                    'clicking on the "Advanced" tab.'),
        widget=forms.TextInput(attrs={
            'size': 80,
        }))

    server = forms.CharField(
        label=_('Server URL'),
        required=True,
        help_text=_('The server HTTP requests will be sent to (e.g., '
                    'https://matrix.org).'),
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
                    'To start, create a Matrix account on and add a new room. '
                    'For best compatibility, we recommend using element.io '
                    'for this.'

                ),
                'fields': ('access_token', 'room_id', 'server'),
                'classes': ('wide',),
            }),
        )
