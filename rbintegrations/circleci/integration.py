"""Integration for building changes on CircleCI."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING
from urllib.parse import quote_plus
from urllib.request import urlopen

from django.utils.functional import cached_property

from rbintegrations.baseci.errors import CIBuildError
from rbintegrations.baseci.integration import (BaseCIIntegration,
                                               BuildPrepData)
from rbintegrations.circleci.forms import CircleCIIntegrationConfigForm
from rbintegrations.util.urlrequest import URLRequest

if TYPE_CHECKING:
    from reviewboard.integrations.models import IntegrationConfig
    from reviewboard.reviews.models.status_update import StatusUpdate


logger = logging.getLogger(__name__)


class CircleCIIntegration(BaseCIIntegration):
    """Integrates Review Board with CircleCI."""

    name = 'CircleCI'
    description = 'Builds diffs posted to Review Board using CircleCI.'
    config_form_cls = CircleCIIntegrationConfigForm

    status_update_service_id = 'circle-ci'

    bot_username = 'circle-ci'
    bot_user_first_name = 'Circle'
    bot_user_last_name = 'CI'

    @cached_property
    def icon_static_urls(self):
        """Return the icons used for the integration.

        Returns:
            dict:
            The icons for CircleCI.
        """
        from rbintegrations.extension import RBIntegrationsExtension

        extension = RBIntegrationsExtension.instance

        return {
            '1x': extension.get_static_url('images/circleci/icon.png'),
            '2x': extension.get_static_url('images/circleci/icon@2x.png'),
        }

    def prepare_builds(
        self,
        prep_data: BuildPrepData,
    ) -> bool:
        """Prepare for builds.

        This will check if the change is on a supported hosting service
        (GitHub or Bitbucket), and only permit the build if it is.

        Version Added:
            3.1

        Args:
            prep_data (BuildPrepData):
                The builds preparation data to modify.

        Returns:
            bool:
            ``True`` if the builds should proceed. ``False`` if builds should
            be skipped.
        """
        # Only build changes against GitHub or Bitbucket repositories.
        repository = prep_data.repository

        if not repository or not repository.hosting_account:
            return False

        service_name = repository.hosting_account.service_name

        # This may look weird, but it's here for defensive purposes.
        # Currently, the possible values for CircleCI's "vcs-type" field in
        # their API happens to match up perfectly with our service names,
        # but that's not necessarily always going to be the case.
        vcs_type: str

        if service_name == 'github':
            vcs_type = 'github'
        elif service_name == 'bitbucket':
            vcs_type = 'bitbucket'
        else:
            return False

        prep_data.extra_state['vcs_type'] = vcs_type

        return True

    def start_build(
        self,
        *,
        prep_data: BuildPrepData,
        config: IntegrationConfig,
        status_update: StatusUpdate,
    ) -> None:
        """Start a new build.

        This will trigger a CircleCI build for the given review request and
        configuration.

        Version Added:
            3.1

        Args:
            prep_data (BuildPrepData):
                The builds preparation data containing information for the
                build.

            config (reviewboard.integrations.models.IntegrationConfig):
                The configuration for the integration triggering this build.

            status_update (reviewboard.reviews.models.status_update.
                           StatusUpdate):
                The status update indicating the status of this build.

        Raises:
            rbintegrations.baseci.errors.CIBuildError:
                There was an error invoking the build.
        """
        vcs_type = prep_data.extra_state['vcs_type']
        diffset = prep_data.diffset
        local_site = prep_data.local_site
        repository = prep_data.repository
        review_request = prep_data.review_request

        org_name, repo_name = self._get_repo_ids(vcs_type, repository)
        circleci_api_token = config.get('circle_api_token')

        if not circleci_api_token:
            logger.error('Unable to make CircleCI API request for '
                         'integration config %d: api_token is missing.',
                         config.pk)
            raise CIBuildError('missing API token.')

        url = ('https://circleci.com/api/v1.1/project/%s/%s/%s/tree/%s'
               '?circle-token=%s'
               % (vcs_type, org_name, repo_name,
                  config.get('branch_name') or 'master',
                  quote_plus(circleci_api_token.encode('utf-8'))))

        api_token = self.get_or_create_api_token(user=prep_data.user,
                                                 local_site=local_site)

        body = {
            'revision': diffset.base_commit_id,
            'build_parameters': {
                'CIRCLE_JOB': 'reviewboard',
                'REVIEWBOARD_SERVER': prep_data.server_url,
                'REVIEWBOARD_REVIEW_REQUEST': review_request.display_id,
                'REVIEWBOARD_DIFF_REVISION': diffset.revision,
                'REVIEWBOARD_API_TOKEN': api_token.token,
                'REVIEWBOARD_STATUS_UPDATE_ID': status_update.pk,
            },
        }

        if local_site:
            body['build_parameters']['REVIEWBOARD_LOCAL_SITE'] = \
                local_site.name

        logger.info('Making CircleCI API request: %s', url)

        request = URLRequest(
            url,
            body=json.dumps(body),
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            },
            method='POST')

        u = urlopen(request)
        data = json.loads(u.read())

        self.update_status(status_update,
                           url=data['build_url'],
                           url_text='View Build')

    def _get_repo_ids(self, service_name, repository):
        """Return the organization and repo name for the given repository.

        Args:
            service_name (unicode):
                The version control service name.

            repository (reviewboard.scmtools.models.Repository):
                The repository.

        Returns:
            tuple of unicode:
            A two-tuple consisting of the organization (or user) and repository
            names.
        """
        extra_data = repository.extra_data
        plan = extra_data['repository_plan']

        if service_name == 'github':
            if plan == 'public':
                return (repository.hosting_account.username,
                        extra_data['github_public_repo_name'])
            elif plan == 'public-org':
                return (extra_data['github_public_org_name'],
                        extra_data['github_public_org_repo_name'])
            elif plan == 'private':
                return (repository.hosting_account.username,
                        extra_data['github_private_repo_name'])
            elif plan == 'private-org':
                return (extra_data['github_private_org_name'],
                        extra_data['github_private_org_repo_name'])
            else:
                raise ValueError('Unexpected plan for GitHub repository %d: %s'
                                 % (repository.pk, plan))
        elif service_name == 'bitbucket':
            if plan == 'personal':
                return (extra_data['bitbucket_account_username'],
                        extra_data['bitbucket_repo_name'])
            elif plan == 'other-user':
                return (extra_data['bitbucket_other_user_username'],
                        extra_data['bitbucket_other_user_repo_name'])
            elif plan == 'team':
                return (extra_data['bitbucket_team_name'],
                        extra_data['bitbucket_team_repo_name'])
            else:
                raise ValueError('Unexpected plan for Bitbucket repository '
                                 '%d: %s'
                                 % (repository.pk, plan))
        else:
            raise ValueError('Unexpected service_name %s' % service_name)
