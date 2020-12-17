"""The form for configuring the Jenkins CI integration."""

from __future__ import unicode_literals

import logging

from django import forms
from django.utils import six
from django.utils.six.moves.urllib.error import HTTPError, URLError
from django.utils.translation import ugettext, ugettext_lazy as _
from djblets.forms.fields import ConditionsField
from reviewboard.integrations.forms import IntegrationConfigForm
from reviewboard.reviews.conditions import ReviewRequestConditionChoices
from reviewboard.webapi.models import WebAPIToken
try:
    from reviewboard.reviews.signals import status_update_request_run
except ImportError:
    status_update_request_run = None

from rbintegrations.jenkinsci.api import JenkinsAPI
from rbintegrations.jenkinsci.common import get_or_create_jenkins_user


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

    def __init__(self, *args, **kwargs):
        """Initialize the form.

        Args:
            *args (tuple):
                Arguments for the form.

            **kwargs (dict):
                Keyword arguments for the form.
        """
        super(JenkinsCIIntegrationConfigForm, self).__init__(*args, **kwargs)

        user = get_or_create_jenkins_user()
        local_site = self.fields['local_site'].initial

        # Fetch the user's API token using the current local site
        try:
            token = user.webapi_tokens.filter(local_site=local_site)[0]
        except IndexError:
            token = WebAPIToken.objects.generate_token(
                user, local_site=local_site, auto_generated=True)

        self.initial['jenkins_user_token'] = token.token

    def load(self):
        """Load the form."""
        # Supporting APIs for these features were added in RB 3.0.19
        if status_update_request_run is None:
            self.disabled_fields = ['run_manually']
            self.disabled_reasons = {
                'run_manually': ugettext(
                    'Requires Review Board 3.0.19 or newer.'),
            }
            self.fields['run_manually'].initial = False
        super(IntegrationConfigForm, self).load()

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

        api = JenkinsAPI(cleaned_data.get('jenkins_endpoint'),
                         cleaned_data.get('jenkins_job_name'),
                         cleaned_data.get('jenkins_username'),
                         cleaned_data.get('jenkins_password'))

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
                message = six.text_type(e)

            self._errors['jenkins_username'] = self.error_class([message])
            self._errors['jenkins_password'] = self.error_class([message])

            return cleaned_data
        except URLError as e:
            self._errors['jenkins_endpoint'] = self.error_class([e])
            return cleaned_data

        return cleaned_data
