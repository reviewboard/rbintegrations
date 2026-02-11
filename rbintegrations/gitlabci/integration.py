"""Integration for building changes with GitLab CI.

Version Added:
    5.0
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

import gitlab
import pydantic
from django.utils.translation import gettext_lazy as _
from djblets.util.decorators import cached_property

from rbintegrations.baseci.errors import CIBuildError
from rbintegrations.baseci.integration import BaseCIIntegration, BuildPrepData
from rbintegrations.gitlabci.forms import (
    GitLabCIIntegrationConfigForm,
    TokenChoices,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from djblets.util.typing import JSONDict, JSONValue
    from reviewboard.integrations.models import IntegrationConfig
    from reviewboard.reviews.models import ReviewRequest, StatusUpdate
    from reviewboard.scmtools.models import Repository


logger = logging.getLogger(__name__)


class GitLabCIConfiguration(pydantic.BaseModel):
    """Configuration settings for the GitLab CI integration.

    These correspond to the fields in
    :py:class:`rbintegrations.gitlabci.forms.GitLabCIIntegrationConfigForm`.

    Version Added:
        5.0
    """

    #: The URL for the GitLab server.
    gitlab_endpoint: str

    #: JSON data for any inputs to pass to the pipeline.
    gitlab_inputs: str

    #: The GitLab project name or ID.
    gitlab_name: str

    #: The branch, tag, or other Git refname to use.
    gitlab_ref: str

    #: Whether to report build state in a review.
    gitlab_report_job_state: bool

    #: The type of token to use for invoking the pipeline.
    gitlab_token_type: TokenChoices

    #: The token content.
    gitlab_token: str

    #: JSON data for additional variables to pass to the pipeline.
    gitlab_vars: str

    #: The secret token to use for validating WebHook responses.
    gitlab_webhook_secret_token: (str | None) = None


class GitLabCIIntegration(BaseCIIntegration):
    """Integration for building changes with GitLab CI.

    Version Added:
        5.0
    """

    name = 'GitLab CI'
    description = _('Builds diffs posted to Review Board using GitLab CI.')
    config_form_cls = GitLabCIIntegrationConfigForm

    status_update_service_id = 'gitlab-ci'

    bot_username = 'gitlab-ci'
    bot_user_first_name = 'GitLab'
    bot_user_last_name = 'CI'

    @cached_property
    def icon_static_urls(self) -> Mapping[str, str]:
        """The icons used for the integration.

        Type:
            dict
        """
        from rbintegrations.extension import RBIntegrationsExtension

        extension = RBIntegrationsExtension.instance
        assert extension is not None

        return {
            '1x': extension.get_static_url('images/gitlabci/icon.png'),
            '2x': extension.get_static_url('images/gitlabci/icon@2x.png'),
        }

    def start_build(
        self,
        *,
        prep_data: BuildPrepData,
        config: IntegrationConfig,
        status_update: StatusUpdate,
    ) -> None:
        """Start a new build.

        This will trigger a gitlab-ci build for the given review request and
        configuration.

        Args:
            prep_data (rbintegrations.baseci.integration.BuildPrepData):
                The builds preparation data.

            config (reviewboard.integrations.models.IntegrationConfig):
                The configuration for the integration triggering this build.

            status_update (reviewboard.reviews.models.StatusUpdate):
                The status update indicating the status of this build.

        Raises:
            rbintegrations.baseci.errors.CIBuildError:
                There was an error invoking the build.
        """
        diffset = prep_data.diffset
        local_site = prep_data.local_site
        repository = prep_data.repository
        review_request = prep_data.review_request

        try:
            gitlab_config = GitLabCIConfiguration.model_validate(
                config.settings)
        except pydantic.ValidationError as e:
            logger.error('Error validating GitLab CI configuration for '
                         'integration config pk=%s: %s',
                         config.pk, str(e))
            return

        name = self._replace_variables(
            name=gitlab_config.gitlab_name,
            repository=repository,
            review_request=review_request)

        logger.debug('Triggering GitLab CI build for review request '
                     '%s (diffset revision %d) on %s',
                     review_request.get_absolute_url(),
                     diffset.revision,
                     name)

        try:
            gitlab_vars = self._replace_variables_json(
                encoded=gitlab_config.gitlab_vars,
                repository=repository,
                review_request=review_request)
        except json.JSONDecodeError as e:
            logger.error('Unable to decode gitlab_vars in GitLab CI '
                         'integration configuration pk=%s: %s',
                         config.pk, str(e))
            return

        api_token = self.get_or_create_api_token(user=prep_data.user,
                                                 local_site=local_site)

        pipeline_name = (
            f'Review Request #{review_request.display_id}: '
            f'{review_request.summary}'
        )

        variables = {
            'REVIEWBOARD_API_TOKEN': api_token.token,
            'REVIEWBOARD_DIFF_REVISION': diffset.revision,
            'REVIEWBOARD_GITLAB_INTEGRATION_CONFIG_ID': config.pk,
            'REVIEWBOARD_PIPELINE_NAME': pipeline_name,
            'REVIEWBOARD_REVIEW_REQUEST': review_request.display_id,
            'REVIEWBOARD_SERVER': prep_data.server_url,
            'REVIEWBOARD_STATUS_UPDATE_ID': status_update.pk,
            **gitlab_vars,
        }

        try:
            inputs = self._replace_variables_json(
                encoded=gitlab_config.gitlab_inputs,
                repository=repository,
                review_request=review_request)
        except json.JSONDecodeError as e:
            logger.error('Unable to decode gitlab_inputs in GitLab CI '
                         'integration configuration pk=%s: %s',
                         config.pk, str(e))
            return

        target_ref = self._replace_variables(
            name=gitlab_config.gitlab_ref,
            repository=repository,
            review_request=review_request)

        try:
            if gitlab_config.gitlab_token_type == TokenChoices.TRIGGER_TOKEN:
                gl = gitlab.Gitlab(url=gitlab_config.gitlab_endpoint)
                project = gl.projects.get(name, lazy=True)

                pipeline = project.trigger_pipeline(
                    target_ref,
                    gitlab_config.gitlab_token,
                    inputs=inputs,
                    variables=variables,
                )
            else:
                gl = gitlab.Gitlab(url=gitlab_config.gitlab_endpoint,
                                   private_token=gitlab_config.gitlab_token)
                gl.auth()
                project = gl.projects.get(name)

                data: JSONDict = {
                    'inputs': inputs,
                    'ref': target_ref,
                    'variables': [
                        {
                            'key': key,
                            'value': value,
                        }
                        for key, value in variables.items()
                    ],
                }

                pipeline = project.pipelines.create(data)
        except Exception as e:
            raise CIBuildError(str(e))

        self.update_status(status_update,
                           url=pipeline.web_url,
                           url_text='View Pipeline')

    def _replace_variables_json(
        self,
        *,
        encoded: str | None,
        repository: Repository,
        review_request: ReviewRequest,
    ) -> JSONDict:
        """Replace variables in a JSON structure.

        Args:
            encoded (str):
                The encoded JSON string.

            repository (reviewboard.scmtools.models.Repository):
                The repository.

            review_request (reviewboard.reviews.models.ReviewRequest):
                The review request.

        Returns:
            djblets.util.typing.JSONDict:
            The decoded JSON structure, with variables replaced in values.

        Raises:
            json.JSONDecodeError:
                The value could not be parsed as JSON.
        """
        if not encoded:
            return {}

        def _replace_in_value(
            value: JSONValue,
        ) -> JSONValue:
            if isinstance(value, str):
                return self._replace_variables(
                    name=value,
                    repository=repository,
                    review_request=review_request)
            elif isinstance(value, list):
                return [
                    self._replace_variables(
                        name=item,
                        repository=repository,
                        review_request=review_request)
                    for item in value
                ]
            else:
                return value

        return {
            key: _replace_in_value(value)
            for key, value in json.loads(encoded).items()
        }

    def _replace_variables(
        self,
        *,
        name: str,
        repository: Repository,
        review_request: ReviewRequest,
    ) -> str:
        """Replace variables in a configured name.

        This will replace the following variables:

        ``{branch}``:
            The branch name.

        ``{repository_name}``:
            The configured repository name.

        Args:
            name (str):
                The template string for the name.

            repository (reviewboard.scmtools.models.Repository):
                The repository for the change being built.

            review_request (reviewboard.reviews.models.ReviewRequest):
                The review request for the change being built.

        Returns:
            str:
            The resulting name.
        """
        var_map = {
            'repository_name': repository.name,
            'branch': review_request.branch,
        }

        keys = '|'.join(re.escape(key) for key in var_map)

        return re.sub(
            fr'\{{({keys})\}}',
            lambda m: var_map[m.group(1)],
            name)
