"""Base form for configuring CI integrations.

Version Added:
    4.0
"""

from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _
from djblets.forms.fields import ConditionsField

from reviewboard.integrations.forms import IntegrationConfigForm
from reviewboard.reviews.conditions import ReviewRequestConditionChoices


class BaseCIIntegrationConfigForm(IntegrationConfigForm):
    """Base form for configuring CI integrations.

    Version Added:
        4.0
    """

    conditions = ConditionsField(
        ReviewRequestConditionChoices,
        label=_('Conditions'))

    run_manually = forms.BooleanField(
        label=_('Run builds manually'),
        required=False,
        help_text=_(
            'Wait to run this service until manually started. This will add '
            'a "Run" button to the build entry.'
        ),
        initial=False)

    class Meta:
        pass
