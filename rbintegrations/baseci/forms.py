"""Base form for configuring CI integrations.

Version Added:
    4.0
"""

from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _
from djblets.forms.widgets import AmountSelectorWidget
from reviewboard.integrations.forms import IntegrationConfigForm

from rbintegrations.util.conditions import ReviewRequestConditionsField


class BaseCIIntegrationConfigForm(IntegrationConfigForm):
    """Base form for configuring CI integrations.

    Version Added:
        4.0
    """

    conditions = ReviewRequestConditionsField()

    run_manually = forms.BooleanField(
        label=_('Run builds manually'),
        required=False,
        help_text=_(
            'Wait to run this service until manually started. This will add '
            'a "Run" button to the build entry.'
        ),
        initial=False)

    timeout = forms.IntegerField(
        label=_('Build timeout'),
        required=False,
        help_text=_(
            'The amount of time until the build is considered to have timed '
            'out. If the build takes longer than this, it will be marked as '
            'timed out and can be re-run.'
        ),
        initial=None,
        widget=AmountSelectorWidget(
            unit_choices=[
                (1, _('seconds')),
                (60, _('minutes')),
                (60 * 60, _('hours')),
                (None, _('Never')),
            ],
            number_attrs={
                'min': 0,
            }))

    class Meta:
        pass
