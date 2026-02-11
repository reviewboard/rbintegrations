"""The form for configuring the GitLab CI integration.

Version Added:
    5.0
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import gitlab
from django import forms
from django.core.exceptions import ValidationError
from django.db.models import TextChoices
from django.utils.translation import gettext_lazy as _

from rbintegrations.baseci.forms import BaseCIIntegrationConfigForm

if TYPE_CHECKING:
    from typing import Any

    from rbintegrations.gitlabci.integration import GitLabCIIntegration


logger = logging.getLogger(__name__)


def validate_json(
    value: str,
) -> None:
    """Validate that a given string is parseable as JSON.

    Version Added:
        5.0

    Args:
        value (str):
            The value to validate.

    Raises:
        django.core.exceptions.ValidationError:
            The value could not be parsed.
    """
    try:
        json.loads(value)
    except Exception as e:
        raise ValidationError(
            _('Unable to parse JSON: %s') % str(e))


class TokenChoices(TextChoices):
    """The choices for the gitlab_token_type field.

    Version Added:
        5.0
    """

    PRIVATE_TOKEN = 'private_token', _('Private API token')
    TRIGGER_TOKEN = 'trigger_token', _('Trigger token')


class GitLabCIIntegrationConfigForm(BaseCIIntegrationConfigForm):
    """Form for configuring the GitLab CI integration.

    Version Added:
        5.0
    """

    gitlab_endpoint = forms.URLField(
        label=_('Server'),
        help_text=_(
            'The URL to your GitLab server. For example, '
            '<code>https://gitlab.example.com/</code>'
        ),
        widget=forms.widgets.TextInput(attrs={
            'size': 40,
        }),
    )

    gitlab_token_type = forms.ChoiceField(
        label=_('Token type'),
        help_text=_('The type of access token used to create pipelines.'),
        choices=TokenChoices.choices,
    )

    gitlab_token = forms.CharField(
        label=_('Token'),
        help_text=_('The API token used for authentication.'),
        widget=forms.PasswordInput(render_value=True),
    )

    gitlab_name = forms.CharField(
        label=_('Project name or ID'),
        initial='{repository_name}',
        help_text=_(
            'Name or ID (required for trigger token). This can include the '
            'following variables: <code>{repository_name}</code>.'
        ),
    )

    gitlab_ref = forms.CharField(
        label=_('Git refname'),
        initial='{branch}',
        help_text=_(
            'Branch, tag, or other Git refname (if not equal to the review '
            'request "branch" field). This can include the following '
            'variables: <code>{branch}</code>.'
        ),
    )

    gitlab_inputs = forms.CharField(
        label=_('Pipeline inputs'),
        initial='{}',
        help_text=_(
            'Inputs for the GitLab CI pipeline. This should be formatted as '
            'a JSON object. Values in this can use the special variables '
            '<code>{branch}</code> and <code>{repository_name}</code>.'
        ),
        widget=forms.widgets.Textarea(attrs={
            'cols': '80',
            'rows': '10',
        }),
        validators=[validate_json],
    )

    gitlab_vars = forms.CharField(
        label=_('Additional variables'),
        initial='{}',
        help_text=_(
            'Additional variables to provide to the GitLab CI pipeline. This '
            'should be formatted as a JSON object. Values in this can use the '
            'special variables <code>{branch}</code> and '
            '<code>{repository_name}</code>.'
        ),
        widget=forms.widgets.Textarea(attrs={
            'cols': '80',
            'rows': '10',
        }),
        validators=[validate_json],
    )

    gitlab_report_job_state = forms.BooleanField(
        label=_('Report job state'),
        required=False,
        help_text=_(
            'If checked, GitLab results will include a summary of all jobs '
            'within the pipeline.'
        ),
    )

    gitlab_webhook_secret_token = forms.CharField(
        label=_('GitLab WebHook secret token'),
        required=False,
        help_text=_(
            'The secret token configured in the GitLab Webhook '
            'configuration. This is optional, but setting this both here and '
            'in the Webhook configuration can ensure '
        ),
        widget=forms.PasswordInput(render_value=True),
    )

    ######################
    # Instance variables #
    ######################

    #: The integration being configured.
    integration: GitLabCIIntegration

    def clean(self) -> dict[str, Any] | None:
        """Clean the form.

        This validates the user credentials that have been provided.

        Returns:
            dict:
            The cleaned form data.
        """
        cleaned_data = super().clean()

        if not self.is_valid() or not cleaned_data:
            # Form validation has already failed.
            return cleaned_data

        assert cleaned_data is not None

        try:
            if cleaned_data['gitlab_token_type'] == 'private_token':
                gl = gitlab.Gitlab(
                    url=cleaned_data['gitlab_endpoint'],
                    private_token=cleaned_data['gitlab_token'],
                )
                gl.auth()
        except gitlab.GitlabError as e:
            self.add_error('gitlab_endpoint', str(e))

        return cleaned_data

    class Meta(BaseCIIntegrationConfigForm.Meta):
        """Metadata for the form."""

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
            (_('Where To Build'), {
                'description': _(
                    'Configure the address and authentication credentials '
                    'for the GitLab server handling your builds.'
                ),
                'fields': (
                    'gitlab_endpoint',
                    'gitlab_token_type',
                    'gitlab_token',
                ),
            }),
            (_('How To Build'), {
                'fields': (
                    'gitlab_name',
                    'gitlab_ref',
                    'gitlab_inputs',
                    'gitlab_vars',
                ),
            }),
            (_('When To Build'), {
                'fields': (
                    'run_manually',
                    'timeout',
                ),
            }),
            (_('Reporting Results'), {
                'fields': (
                    'gitlab_report_job_state',
                    'gitlab_webhook_secret_token',
                ),
            }),
        )
