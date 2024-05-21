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

    class Meta:
        fieldsets = (
            (_('What To Build'), {
                'description': _(
                    'You can choose which review requests to build using this '
                    'configuration by setting conditions here. At a minimum, '
                    'this should include the specific repository to use '
                    'this configuration for.'
                ),
                'fields': (
                    'conditions',
                ),
            }),
            (_('How To Build'), {
                'description': _(
                    "Builds performed on the code in review requests will use "
                    "a completely separate configuration from commits which "
                    "are pushed to the source code repository. The "
                    "configuration listed here will be used instead of the "
                    "contents of the repository's "
                    "<code>.circleci/config.yml</code> file. Note that "
                    "this should not contain any secret environment "
                    "variables."
                    "\n"
                    "It's also recommended to create a special branch head "
                    "in the repository to use for these builds, so they "
                    "don't appear to be happening on your main development "
                    "branch. This branch can contain anything (or even be "
                    "empty), since the code will come from the review "
                    "request."
                ),
                'fields': (
                    'circle_api_token',
                    'branch_name',
                ),
            }),
            (_('When To Build'), {
                'fields': (
                    'run_manually',
                ),
            }),
        )
