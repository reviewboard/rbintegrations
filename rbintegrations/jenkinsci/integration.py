"""Integration for building changes on Jenkins CI."""

from __future__ import annotations

import logging
import re
from typing import Dict, TYPE_CHECKING
from urllib.error import HTTPError

from djblets.util.decorators import cached_property

from rbintegrations.baseci.errors import CIBuildError
from rbintegrations.baseci.integration import BaseCIIntegration, BuildPrepData
from rbintegrations.jenkinsci.api import JenkinsAPI
from rbintegrations.jenkinsci.forms import JenkinsCIIntegrationConfigForm

if TYPE_CHECKING:
    from reviewboard.integrations.models import IntegrationConfig
    from reviewboard.reviews.models import ReviewRequest, StatusUpdate
    from reviewboard.scmtools.models import Repository


logger = logging.getLogger(__name__)


class JenkinsCIIntegration(BaseCIIntegration):
    """Integrates Review Board with Jenkins CI."""

    name = 'Jenkins CI'
    description = 'Builds diffs posted to Review Board using Jenkins CI.'
    config_form_cls = JenkinsCIIntegrationConfigForm

    status_update_service_id = 'jenkins-ci'

    bot_username = 'jenkins-ci'
    bot_user_first_name = 'Jenkins'
    bot_user_last_name = 'CI'

    @cached_property
    def icon_static_urls(self) -> Dict:
        """The icons used for the integration.

        Type:
            dict
        """
        from rbintegrations.extension import RBIntegrationsExtension

        extension = RBIntegrationsExtension.instance

        return {
            '1x': extension.get_static_url('images/jenkinsci/icon.png'),
            '2x': extension.get_static_url('images/jenkinsci/icon@2x.png'),
        }

    def prepare_builds(
        self,
        prep_data: BuildPrepData,
    ) -> bool:
        """Prepare for builds.

        This will set some initial information common to all Jenkins builds.

        Version Added:
            3.1

        Args:
            prep_data (BuildPrepData):
                The builds preparation data to modify.

        Returns:
            bool:
            ``True``, always.
        """
        review_request = prep_data.review_request

        prep_data.extra_state['patch_info'] = {
            'diff_revision': prep_data.diffset.revision,
            'review_branch': review_request.branch,
            'review_id': review_request.display_id,
            'reviewboard_server': prep_data.server_url,
        }

        return True

    def start_build(
        self,
        *,
        prep_data: BuildPrepData,
        config: IntegrationConfig,
        status_update: StatusUpdate,
    ) -> None:
        """Start a new build.

        This will trigger a Jenkins build for the given review request and
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
        patch_info = prep_data.extra_state['patch_info'].copy()
        patch_info['status_update_id'] = status_update.pk

        diffset = prep_data.diffset
        repository = prep_data.repository
        review_request = prep_data.review_request

        job_name = self._replace_job_variables(config.get('jenkins_job_name'),
                                               repository,
                                               review_request)

        # Time to kick off the build!
        logger.info('Triggering Jenkins CI build for review request '
                    '%s (diffset revision %d)',
                    review_request.get_absolute_url(),
                    diffset.revision)

        api = JenkinsAPI(endpoint=config.get('jenkins_endpoint'),
                         job_name=job_name,
                         username=config.get('jenkins_username'),
                         password=config.get('jenkins_password'))

        try:
            api.start_build(patch_info)
        except HTTPError as e:
            if e.code == 404:
                raise CIBuildError('failed, job does not exist.')
            else:
                raise CIBuildError('failed to communicate with Jenkins.')

    def _replace_job_variables(
        self,
        job_name: str,
        repository: Repository,
        review_request: ReviewRequest,
    ) -> str:
        """Replace variables in the Jenkins job name.

        This will replace the following variables:

        ``{branch_name}``:
            The unmodified branch name.

        ``{repository_name}``:
            The unmodified configured repository name.

        ``{noslash_branch_name}``:
            The branch name with slashes replaced with underscores.

        ``{noslash_repository_name}``:
            The configured repository name with slashes replaced with
            underscores.

        ``{branch}``:
            Legacy equivalent to ``{noslash_branch_name}``.

        ``{repository_name}``:
            Legacy equivalent to ``{noslash_repository_name}``.

        Version Changed:
            4.0:
            * Added support for ``{branch_name}``, ``{repository_name}``,
              ``{noslash_branch_name}``, and ``{noslash_repository_name}``.
            * The job name itself is no longer normalized, just specific
              variables within it.

        Args:
            job_name (str):
                The template string for the Jenkins job name.

            repository (reviewboard.scmtools.models.Repository):
                The repository for the change being built.

            review_request (reviewboard.reviews.models.review_request.
                            ReviewRequest):
                The review request for the change being built.

        Returns:
            str:
            The resulting job name.
        """
        branch = review_request.branch
        repo_name = repository.name
        noslash_branch = branch.replace('/', '_')
        noslash_repo_name = repo_name.replace('/', '_')

        var_map: dict[str, str] = {
            # Plain variables
            'branch_name': branch,
            'repository_name': repo_name,

            # No-slash variations
            'noslash_branch_name': noslash_branch,
            'noslash_repository_name': noslash_repo_name,

            # Legacy variables
            'branch': noslash_branch,
            'repository': noslash_repo_name,
        }

        return re.sub(
            r'\{(%s)\}' % '|'.join(var_map.keys()),
            lambda m: var_map[m.group(1)],
            job_name)
