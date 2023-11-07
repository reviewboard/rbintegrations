"""The form for configuring the Trello integration."""

from django import forms
from django.utils.translation import gettext_lazy as _
from djblets.forms.fields import ConditionsField
from reviewboard.integrations.forms import IntegrationConfigForm
from reviewboard.reviews.conditions import ReviewRequestConditionChoices


class TrelloIntegrationConfigForm(IntegrationConfigForm):
    """Form for configuring Trello."""

    conditions = ConditionsField(ReviewRequestConditionChoices,
                                 label=_('Conditions'))

    trello_api_key = forms.CharField(
        label=_('Trello API Key'),
        help_text=_('Your Trello API key. This can be created by registering '
                    'an application in the <a '
                    'href="https://trello.com/power-ups/admin/">Trello '
                    'Power-Up Admin Portal</a>.'),
        widget=forms.widgets.TextInput(attrs={
            'size': 40,
        }))

    trello_api_token = forms.CharField(
        label=_('Trello API Token'),
        help_text=_('An access token for the Trello API. To create this, '
                    'after creating a Power-Up in the <a '
                    'href="https://trello.com/power-ups/admin/">Trello '
                    'Power-Up Admin Portal</a>, select "manually generate a '
                    'Token".'),
        widget=forms.widgets.TextInput(attrs={
            'size': 40,
        }))
