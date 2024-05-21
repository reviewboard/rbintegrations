"""The form for configuring the Jenkins CI integration."""

import logging
from urllib.error import HTTPError, URLError

from django import forms
from django.utils.translation import gettext_lazy as _
from reviewboard.integrations.forms import IntegrationConfigForm
from reviewboard.reviews.conditions import ReviewRequestConditionChoices

from rbintegrations.baseci.forms import BaseCIIntegrationConfigForm
from rbintegrations.jenkinsci.api import JenkinsAPI


logger = logging.getLogger(__name__)


class JenkinsCIIntegrationConfigForm(BaseCIIntegrationConfigForm):
    """Form for configuring Jenkins CI."""

    jenkins_endpoint = forms.URLField(
        label=_('Server'),
        help_text=_('Server endpoint URL.'))

    jenkins_job_name = forms.CharField(
        label=_('Job Name'),
        help_text=_('Job name. This can include the following variables: '
                    '{repository}, {branch}.'))

    jenkins_username = forms.CharField(
        label=_('Username'),
        help_text=_('User who has access to the above job.'))

    jenkins_password = forms.CharField(
        label=_('API Token / Password'),
        help_text=_('The API token used for authentication. Older versions '
                    'may require a user password instead.'),
        widget=forms.PasswordInput)

    jenkins_user_token = forms.CharField(
        label=_('Review Board API Token'),
        help_text=_('This API token is used by Jenkins to update build '
                    'status. Please specify this in the Jenkins-side '
                    'configuration. Note that if you switch the local site '
                    'this API token will be updated upon saving.'),
        required=False,
        widget=forms.TextInput(attrs={'readonly': True}))

    def __init__(self, *args, **kwargs) -> None:
        """Initialize the form.

        Args:
            *args (tuple):
                Arguments for the form.

            **kwargs (dict):
                Keyword arguments for the form.
        """
        super().__init__(*args, **kwargs)

        integration = self.integration
        local_site = self.fields['local_site'].initial
        user = integration.get_or_create_user()

        token = integration.get_or_create_api_token(
            user=user,
            local_site=local_site)

        self.initial['jenkins_user_token'] = token.token

    def clean(self):
        """Clean the form.

        This validates the user credentials that have been provided.

        Returns:
            dict:
            The cleaned data.
        """
        cleaned_data = super(JenkinsCIIntegrationConfigForm, self).clean()

        if self._errors:
            # Form validation has already failed.
            return cleaned_data

        api = JenkinsAPI(endpoint=cleaned_data.get('jenkins_endpoint'),
                         job_name=cleaned_data.get('jenkins_job_name'),
                         username=cleaned_data.get('jenkins_username'),
                         password=cleaned_data.get('jenkins_password'))

        try:
            # Tests a simple endpoint to ensure the user credentials are
            # correct.
            api.test_connection()
        except HTTPError as e:
            if e.code == 403:
                message = _('Unable to authenticate with the provided user.')
            elif e.code == 401:
                message = _('Provided user credentials are incorrect.')
            else:
                message = str(e)

            self._errors['jenkins_username'] = self.error_class([message])
            self._errors['jenkins_password'] = self.error_class([message])

            return cleaned_data
        except URLError as e:
            self._errors['jenkins_endpoint'] = self.error_class([e])
            return cleaned_data

        return cleaned_data

    class Meta(BaseCIIntegrationConfigForm.Meta):
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
                    'for the Jenkins server handling your builds.'
                ),
                'fields': (
                    'jenkins_endpoint',
                    'jenkins_username',
                    'jenkins_password',
                ),
            }),
            (_('How To Build'), {
                'description': _(
                    "Builds performed on the code in review requests will use "
                    "a completely separate configuration from commits which "
                    "are pushed to the GitHub repository. The configuration "
                    "listed here will be used instead of the contents of the "
                    "repository's <code>.travis.yml</code> file. Note that "
                    "this should not contain any secret environment "
                    "variables."
                    "\n"
                    "It's also recommended to create a special branch head "
                    "in the GitHub repository to use for these builds, so "
                    "they don't appear to be happening on your main "
                    "development branch. This branch can contain anything "
                    "(or even be empty), since the code will come from the "
                    "review request."
                ),
                'fields': (
                    'jenkins_job_name',
                    'jenkins_user_token',
                ),
            }),
            (_('When To Build'), {
                'fields': (
                    'run_manually',
                ),
            }),
        )
