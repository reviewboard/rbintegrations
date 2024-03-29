"""The form for configuring the Jenkins CI integration."""

import logging
from urllib.error import HTTPError, URLError

from django import forms
from django.utils.translation import gettext_lazy as _
from djblets.forms.fields import ConditionsField
from reviewboard.integrations.forms import IntegrationConfigForm
from reviewboard.reviews.conditions import ReviewRequestConditionChoices

from rbintegrations.jenkinsci.api import JenkinsAPI


logger = logging.getLogger(__name__)


class JenkinsCIIntegrationConfigForm(IntegrationConfigForm):
    """Form for configuring Jenkins CI"""

    conditions = ConditionsField(ReviewRequestConditionChoices,
                                 label=_('Conditions'))

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

    run_manually = forms.BooleanField(
        label=_('Run builds manually'),
        required=False,
        help_text=_('Wait to run this service until manually started. This '
                    'will add a "Run" button to the Jenkins entry.'),
        initial=False)

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
