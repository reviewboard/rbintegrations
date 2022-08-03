"""The form for configuring the Circle CI integration."""

from django import forms
from django.utils.translation import gettext_lazy as _
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

    run_manually = forms.BooleanField(
        label=_('Run builds manually'),
        required=False,
        help_text=_('Wait to run this service until manually started. This '
                    'will add a "Run" button to the CircleCI entry.'),
        initial=False)
