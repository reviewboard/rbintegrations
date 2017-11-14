"""The form for configuring the Trello integration."""

from __future__ import unicode_literals

from django import forms
from django.utils.translation import ugettext_lazy as _
from djblets.forms.fields import ConditionsField
from reviewboard.integrations.forms import IntegrationConfigForm
from reviewboard.reviews.conditions import ReviewRequestConditionChoices


class TrelloIntegrationConfigForm(IntegrationConfigForm):
    """Form for configuring Trello."""

    conditions = ConditionsField(ReviewRequestConditionChoices,
                                 label=_('Conditions'))

    trello_api_key = forms.CharField(
        label=_('Trello API Key'),
        help_text=_('Your Trello API key. This can be found on '
                    '<a href="https://trello.com/app-key">Trello Developer '
                    'API Keys</a>.'),
        min_length=32,
        max_length=32,
        widget=forms.widgets.TextInput(attrs={
            'size': 40,
        }))

    trello_api_token = forms.CharField(
        label=_('Trello API Token'),
        help_text=_('An access token for the Trello API. To create this, go '
                    'to <a href="https://trello.com/app-key">Trello Developer '
                    'API Keys</a> and select "manually generate a Token".'),
        min_length=64,
        max_length=64,
        widget=forms.widgets.TextInput(attrs={
            'size': 40,
        }))
