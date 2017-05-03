"""The form for configuring the Travis CI integration."""

from __future__ import unicode_literals

import logging

from django import forms
from django.utils import six
from django.utils.six.moves.urllib.error import HTTPError, URLError
from django.utils.translation import ugettext_lazy as _
from djblets.forms.fields import ConditionsField
from djblets.conditions.choices import ConditionChoices
from reviewboard.integrations.forms import IntegrationConfigForm
from reviewboard.reviews.conditions import (ReviewRequestConditionChoiceMixin,
                                            ReviewRequestConditionChoices,
                                            ReviewRequestRepositoriesChoice,
                                            ReviewRequestRepositoryTypeChoice)
from reviewboard.scmtools.conditions import RepositoriesChoice
from reviewboard.scmtools.models import Repository

from rbintegrations.travisci.api import TravisAPI


logger = logging.getLogger(__name__)


class GitHubRepositoriesChoice(ReviewRequestConditionChoiceMixin,
                               RepositoriesChoice):
    """A condition choice for matching a review request's repositories.

    This works the same as the built-in ``ReviewRequestRepositoriesChoice``,
    but limits the queryset to only be GitHub repositories.
    """

    queryset = Repository.objects.filter(
        hosting_account__service_name='github')

    def get_match_value(self, review_request, **kwargs):
        """Return the repository used for matching.

        Args:
            review_request (reviewboard.scmtools.models.review_request.
                            ReviewRequest):
                The provided review request.

            **kwargs (dict):
                Unused keyword arguments.

        Returns:
            reviewboard.scmtools.models.Repository:
            The review request's repository.
        """
        return review_request.repository


class GitHubOnlyConditionChoices(ConditionChoices):
    """A set of condition choices which limits to GitHub repositories.

    The basic ReviewRequestConditionChoices allows a little too much freedom to
    select repositories which can never work with Travis CI. This gets rid of
    the repository type condition, and limits the repository condition to only
    show GitHub repositories.
    """

    choice_classes = list(
        (set(ReviewRequestConditionChoices.choice_classes) - {
            ReviewRequestRepositoriesChoice,
            ReviewRequestRepositoryTypeChoice,
        }) | {
            GitHubRepositoriesChoice,
        }
    )


class TravisCIIntegrationConfigForm(IntegrationConfigForm):
    """Form for configuring Travis CI."""

    conditions = ConditionsField(
        GitHubOnlyConditionChoices,
        label=_('Conditions'),
        help_text=_('You can choose which review requests will be built using '
                    'this Travis CI configuration.'))

    travis_endpoint = forms.ChoiceField(
        label=_('Travis CI'),
        choices=TravisAPI.ENDPOINT_CHOICES,
        help_text=_('The Travis CI endpoint for your project.'))

    travis_custom_endpoint = forms.URLField(
        label=_('CI Server'),
        required=False,
        help_text=_('The URL to your enterprise Travis CI server. For '
                    'example, <code>https://travis.example.com/</code>.'))

    travis_ci_token = forms.CharField(
        label=_('API Token'),
        help_text=(
            _('The Travis CI API token. To get an API token, follow the '
              'instructions at <a href="%(url)s">%(url)s</a>.')
            % {'url': 'https://developer.travis-ci.com/authentication'}))

    travis_yml = forms.CharField(
        label=_('Build Config'),
        help_text=_('The configuration needed to do a test build, without '
                    'any notification or deploy stages.'),
        widget=forms.Textarea(attrs={'cols': '80'}))

    branch_name = forms.CharField(
        label=_('Build Branch'),
        required=False,
        help_text=_('An optional branch name to use for review request '
                    'builds within the Travis CI user interface.'))

    def __init__(self, *args, **kwargs):
        """Initialize the form.

        Args:
            *args (tuple):
                Arguments for the form.

            **kwargs (dict):
                Keyword arguments for the form.
        """
        super(TravisCIIntegrationConfigForm, self).__init__(*args, **kwargs)

        from rbintegrations.extension import RBIntegrationsExtension
        extension = RBIntegrationsExtension.instance

        travis_integration_config_bundle = \
            extension.get_bundle_id('travis-ci-integration-config')
        self.css_bundle_names = [travis_integration_config_bundle]
        self.js_bundle_names = [travis_integration_config_bundle]

    def clean(self):
        """Clean the form.

        This validates that the configured settings are correct. It checks that
        the API token works, and uses Travis' lint API to validate the
        ``travis_yml`` field.

        Returns:
            dict:
            The cleaned data.
        """
        cleaned_data = super(TravisCIIntegrationConfigForm, self).clean()

        if self._errors:
            # If individual form field validation already failed, don't try to
            # do any of the below.
            return cleaned_data

        endpoint = cleaned_data['travis_endpoint']

        if (endpoint == TravisAPI.ENTERPRISE_ENDPOINT and
            not cleaned_data['travis_custom_endpoint']):
            self._errors['travis_custom_endpoint'] = self.error_class([
                _('The server URL is required when using an enterprise '
                  'Travis CI server.')
            ])
            return cleaned_data

        try:
            api = TravisAPI(cleaned_data)
        except ValueError as e:
            self._errors['travis_endpoint'] = self.error_class(
                [six.text_type(e)])

        # First try fetching the "user" endpoint. We don't actually do anything
        # with the data returned by this, but it's a good check to see if the
        # API token is correct because it requires authentication.
        try:
            api.get_user()
        except HTTPError as e:
            if e.code == 403:
                message = _('Unable to authenticate with this API token.')
            else:
                message = six.text_type(e)

            self._errors['travis_ci_token'] = self.error_class([message])

            return cleaned_data
        except URLError as e:
            self._errors['travis_endpoint'] = self.error_class([e])
            return cleaned_data

        # Use the Travis API's "lint" endpoint to verify that the provided
        # config is valid.
        try:
            lint_results = api.lint(cleaned_data['travis_yml'])

            for warning in lint_results['warnings']:
                if warning['key']:
                    if isinstance(warning['key'], list):
                        key = '.'.join(warning['key'])
                    else:
                        key = warning['key']

                    message = (_('In %s section: %s')
                               % (key, warning['message']))
                else:
                    message = warning['message']

                self._errors['travis_yml'] = self.error_class([message])
        except URLError as e:
            logger.exception('Unexpected error when trying to lint Travis CI '
                             'config: %s',
                             e,
                             request=self.request)
            self._errors['travis_endpoint'] = self.error_class([
                _('Unable to communicate with Travis CI server.')
            ])
        except Exception as e:
            logger.exception('Unexpected error when trying to lint Travis CI '
                             'config: %s',
                             e,
                             request=self.request)
            self._errors['travis_endpoint'] = self.error_class([e])

        return cleaned_data

    class Meta:
        fieldsets = (
            (_('What To Build'), {
                'description': _(
                    'You can choose which review requests to build using this '
                    'configuration by setting conditions here. At a minimum, '
                    'this should include the specific repository to use '
                    'this configuration for.'
                ),
                'fields': ('conditions',),
            }),
            (_('Where To Build'), {
                'description': _(
                    'Travis CI offers several different servers depending on '
                    'your project. Select that here and set up your API key '
                    'for the correct server.'
                ),
                'fields': ('travis_endpoint', 'travis_custom_endpoint',
                           'travis_ci_token'),
            }),
            (_('How To Build'), {
                'description': _(
                    "Builds performed on the code in review requests will use "
                    "a completely separate configuration from commits which "
                    "are pushed to the GitHub repository. The configuration "
                    "listed here will be used instead of the contents of the "
                    "repository's <code>.travis.yml</code> file. Note that "
                    "this should not contain any secret environment "
                    "variables.\n"
                    "It's also recommended to create a special branch head "
                    "in the GitHub repository to use for these builds, so "
                    "they don't appear to be happening on "
                    "<code>master</code>. This branch can contain anything "
                    "(or even be empty), since the code will come from the "
                    "review request."
                ),
                'fields': ('travis_yml', 'branch_name'),
                'classes': ('wide',)
            }),
        )
