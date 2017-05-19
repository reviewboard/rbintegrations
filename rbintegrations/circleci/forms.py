"""The form for configuring the Circle CI integration."""

from __future__ import unicode_literals

from django import forms
from django.utils.translation import ugettext_lazy as _
from djblets.forms.fields import ConditionsField
from reviewboard.integrations.forms import IntegrationConfigForm
from reviewboard.reviews.conditions import ReviewRequestConditionChoices


class CircleCIIntegrationConfigForm(IntegrationConfigForm):
    """Form for configuring Circle CI."""

    conditions = ConditionsField(ReviewRequestConditionChoices,
                                 label=_('Conditions'))

    circle_api_token = forms.CharField(
        label=_('API Token'),
        help_text=_('Your CircleCI API token. You can create these tokens '
                    'in the CircleCI repository settings under "API '
                    'Permissions".'))

    branch_name = forms.CharField(
        label=_('Build Branch'),
        required=False,
        help_text=_('An optional branch name to use for review request '
                    'builds within the CircleCI user interface.'))
