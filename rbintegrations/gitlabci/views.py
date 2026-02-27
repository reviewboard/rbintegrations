"""Views for the GitLab CI integration.

Version Added:
    5.0
"""

from __future__ import annotations

import json
import logging
from typing import List, Literal, Optional, TYPE_CHECKING

import pydantic
from django.core.exceptions import ObjectDoesNotExist
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseServerError,
)
from django.utils.translation import gettext as _
from django.views.generic import View
from reviewboard.integrations.models import IntegrationConfig
from reviewboard.reviews.models import GeneralComment, Review, StatusUpdate

from rbintegrations.gitlabci.integration import (
    GitLabCIIntegration,
    GitLabCIConfiguration,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any, ClassVar

    from django.http import HttpRequest
    from djblets.util.typing import JSONValue
    from typing_extensions import TypeAlias


logger = logging.getLogger(__name__)


#: The possible status values for pipelines and jobs.
#:
#: This is retrieved from
#: https://gitlab.com/gitlab-org/gitlab/-/blob/master/app/models/concerns/ci/has_status.rb
#:
#: This may or may not be an authoritative list of the possible status values
#: but it's the best I've found.
#:
#: Version Added:
#:     5.0
GitLabStatus: TypeAlias = Literal[
    'canceled',
    'canceling',
    'created',
    'failed',
    'manual',
    'pending',
    'preparing',
    'running',
    'scheduled',
    'skipped',
    'success',
    'waiting_for_callback',
    'waiting_for_resource',
]


class _WebHookPayload(pydantic.BaseModel):
    """Data for the payload from the GitLab WebHook pipeline event.

    Version Added:
        5.0
    """

    class BuildData(pydantic.BaseModel):
        id: int
        name: str
        stage: str
        status: GitLabStatus

    class ObjectAttributes(pydantic.BaseModel):
        class PipelineVariable(pydantic.BaseModel):
            key: str
            value: str

        id: int
        source: str
        stages: List[str]
        status: GitLabStatus
        url: str
        variables: Optional[List[PipelineVariable]] = None

    class ProjectData(pydantic.BaseModel):
        web_url: str

    builds: List[BuildData]
    object_attributes: ObjectAttributes
    project: ProjectData


class GitlabCIWebHookView(View):
    """A view to handle webhook notifications from a GitLab CI build.

    Version Added:
        5.0
    """

    STATUS_STATE_MAP: ClassVar[Mapping[GitLabStatus, str]] = {
        'canceled': StatusUpdate.ERROR,  # Handled specially below.
        'canceling': StatusUpdate.PENDING,
        'created': StatusUpdate.PENDING,
        'failed': StatusUpdate.ERROR,
        'manual': StatusUpdate.NOT_YET_RUN,
        'pending': StatusUpdate.PENDING,
        'preparing': StatusUpdate.PENDING,
        'running': StatusUpdate.PENDING,
        'scheduled': StatusUpdate.PENDING,  # Handled specially below.
        'skipped': StatusUpdate.ERROR,
        'success': StatusUpdate.DONE_SUCCESS,
        'waiting_for_callback': StatusUpdate.PENDING,
        'waiting_for_resource': StatusUpdate.PENDING,
    }

    PIPELINE_STATUS_DESCRIPTION_MAP: ClassVar[Mapping[GitLabStatus, str]] = {
        'canceled': 'pipeline was canceled before completion.',
        'canceling': 'pipeline is in the process of cancelling.',
        'created': 'pipeline has been created.',
        'failed': 'pipeline failed.',
        'manual': 'pipeline needs to be manually run.',
        'pending': 'pipeline has not started running yet.',
        'preparing': 'pipeline is preparing to run.',
        'running': 'pipeline is running.',
        'scheduled': 'pipeline is scheduled to run.',
        'skipped': 'pipeline was skipped.',
        'success': 'pipeline completed successfully.',
        'waiting_for_callback': 'pipeline is waiting for an external action.',
        'waiting_for_resource': (
            'pipeline is waiting for a resource such as a runner.'
        ),
    }

    JOB_STATUS_DESCRIPTION_MAP: ClassVar[Mapping[GitLabStatus, str]] = {
        'canceled': 'cancelled',
        'canceling': 'cancelling',
        'created': 'created',
        'failed': 'failed',
        'manual': 'needs to be manually run',
        'pending': 'not started running yet',
        'preparing': 'preparing to run',
        'running': 'running',
        'scheduled': 'scheduled',
        'skipped': 'skipped',
        'success': 'succeeded',
        'waiting_for_callback': 'waiting for an external action',
        'waiting_for_resource': 'waiting for a resource',
    }

    def post(
        self,
        request: HttpRequest,
        *args,
        **kwargs,
    ) -> HttpResponse:
        """Handle the POST.

        Args:
            request (django.http.HttpRequest):
                The HTTP request.

            *args (tuple):
                Additional positional arguments, parsed from the URL.

            **kwargs (dict):
                Additional keyword arguments, parsed from the URL.

        Returns:
            django.http.HttpResponse:
            A response.
        """
        try:
            decoded: JSONValue = json.loads(request.body)
        except json.JSONDecodeError as e:
            return HttpResponseBadRequest(str(e))

        if (not isinstance(decoded, dict) or
            decoded.get('object_kind') != 'pipeline'):
            return HttpResponseBadRequest('Missing pipeline event')

        try:
            payload = _WebHookPayload.model_validate(decoded)
        except pydantic.ValidationError as e:
            error = f'Unable to validate WebHook payload: {e}'
            logger.error('gitlab-ci webhook: %s',
                         error,
                         extra={'request': request})
            return HttpResponseBadRequest(error)

        object_attributes = payload.object_attributes

        if object_attributes.variables is None:
            # This WebHook notification was for a pipeline that was not
            # triggered by Review Board. Report a 202 code back to GitLab.
            return HttpResponse(status=202)

        variables = {
            item.key: item.value
            for item in object_attributes.variables
        }

        if ('REVIEWBOARD_REVIEW_REQUEST' not in variables or
            'REVIEWBOARD_STATUS_UPDATE_ID' not in variables or
            'REVIEWBOARD_GITLAB_INTEGRATION_CONFIG_ID' not in variables):
            # This WebHook notification was for a pipeline that was not
            # triggered by Review Board. Report a 202 code back to GitLab.
            return HttpResponse(status=202)

        pipeline_id = object_attributes.id

        try:
            review_request_id = int(variables['REVIEWBOARD_REVIEW_REQUEST'])
            status_update_id = int(variables['REVIEWBOARD_STATUS_UPDATE_ID'])
            config_id = int(
                variables['REVIEWBOARD_GITLAB_INTEGRATION_CONFIG_ID'])
        except ValueError:
            error = 'Variables were not in expected format.'
            logger.error('gitlab-ci webhook (pipeline %s): %s',
                         pipeline_id, error,
                         extra={'request': request})

            return HttpResponseBadRequest(error)

        logger.debug(
            'gitlab-ci webhook (pipeline %s): processing webhook for review '
            'request %s (status update %s)',
            pipeline_id,
            review_request_id,
            status_update_id,
            extra={'request': request},
        )

        try:
            integration_config = IntegrationConfig.objects.get(pk=config_id)
        except ObjectDoesNotExist:
            error = f'Unable to find integration config {config_id}'
            logger.error('gitlab-ci webhook (pipeline %s): %s',
                         pipeline_id, error,
                         extra={'request': request})

            return HttpResponseBadRequest(error)

        try:
            gitlab_config = GitLabCIConfiguration.model_validate(
                integration_config.settings)
        except pydantic.ValidationError as e:
            error = (
                f'Error validating GitLab CI configuration for '
                f'integration config pk={integration_config.pk}: {e}'
            )
            logger.error('gitlab-ci webhook (pipeline %s): %s',
                         pipeline_id, error,
                         extra={'request': request})

            return HttpResponseServerError(error)

        webhook_token = request.META.get('HTTP_X_GITLAB_TOKEN', '')
        expected_webhook_token = gitlab_config.gitlab_webhook_secret_token

        if (expected_webhook_token is not None and
            webhook_token != expected_webhook_token):
            error = 'WebHook secret token does not match'
            logger.error('gitlab-ci webhook (pipeline %s): %s',
                         pipeline_id, error,
                         extra={'request': request})

            return HttpResponseForbidden(error)

        try:
            status_update = StatusUpdate.objects.get(pk=status_update_id)
        except ObjectDoesNotExist:
            error = \
                f'Unable to find matching status update ID {status_update_id}'
            logger.error('gitlab-ci webhook (pipeline %s): %s',
                         pipeline_id, error,
                         extra={'request': request})

            return HttpResponseBadRequest(error)

        if status_update.review_request.display_id != review_request_id:
            error = (
                f'Wrong review request {review_request_id} for status update '
                f'ID {status_update_id}'
            )
            logger.error('gitlab-ci webhook (pipeline %s): %s',
                         pipeline_id, error,
                         extra={'request': request})

            return HttpResponseBadRequest(error)

        integration = integration_config.integration
        assert isinstance(integration, GitLabCIIntegration)

        try:
            self._update_from_payload(
                status_update=status_update,
                gitlab_config=gitlab_config,
                integration=integration,
                pipeline_id=pipeline_id,
                payload=payload)
        except Exception as e:
            logger.error('gitlab-ci webhook (pipeline %s): %s',
                         pipeline_id, e,
                         extra={'request': request})

            return HttpResponseBadRequest(e)

        return HttpResponse()

    def _update_from_payload(
        self,
        *,
        status_update: StatusUpdate,
        gitlab_config: GitLabCIConfiguration,
        integration: GitLabCIIntegration,
        pipeline_id: int,
        payload: _WebHookPayload,
    ) -> None:
        """Update the status update with the data from the payload.

        Args:
            status_update (reviewboard.reviews.models.StatusUpdate):
                The status update.

            gitlab_config (rbintegrations.gitlabci.integration.
                           GitLabCIConfiguration):
                The configuration settings.

            integration (rbintegrations.gitlabci.integration.
                         GitLabCIIntegration):
                The integration instance.

            pipeline_id (int):
                The ID of the pipeline triggering the WebHook event.

            payload (_WebHookPayload):
                The payload from the WebHook.

        Raises:
            Exception:
                An error occurred while processing the payload.
        """
        object_attributes = payload.object_attributes
        source = object_attributes.source

        if source == 'api':
            # This is an update for the main pipeline that we ourselves
            # triggered.
            build_status = object_attributes.status

            try:
                # The CANCELLED state was added in Review Board 7.1. If it's
                # available, we want to use it. If not, fall back on the
                # definition in STATUS_STATE_MAP.
                if (build_status in {'canceled', 'skipped'} and
                    hasattr(StatusUpdate, 'CANCELLED')):
                    new_state = getattr(StatusUpdate, 'CANCELLED')
                else:
                    new_state = self.STATUS_STATE_MAP[build_status]
            except KeyError:
                raise Exception(f'Unknown build status {build_status}')

            url = object_attributes.url
            assert isinstance(url, str)

            if gitlab_config.gitlab_report_job_state:
                self._update_build_status(payload, status_update,
                                          integration)
                status_extra_fields = ['extra_data', 'review']
            else:
                status_extra_fields = None

            integration.update_status(
                status_update,
                state=new_state,
                description=self.PIPELINE_STATUS_DESCRIPTION_MAP[build_status],
                url=url,
                url_text=_('View pipeline'),
                extra_fields=status_extra_fields,
            )
        elif source == 'parent_pipeline':
            # This is an update for a child pipeline that was triggered from
            # the main pipeline. We don't want to change the state, URL, or
            # other fields, but we do want to update build status if
            # appropriate.
            if gitlab_config.gitlab_report_job_state:
                self._update_build_status(payload, status_update,
                                          integration)
                integration.update_status(
                    status_update,
                    extra_fields=['extra_data', 'review'])

    def _update_build_status(
        self,
        payload: _WebHookPayload,
        status_update: StatusUpdate,
        integration: GitLabCIIntegration,
    ) -> None:
        """Update the build status for the pipeline.

        Args:
            payload (_WebHookPayload):
                The webhook payload.

            status_update (reviewboard.reviews.models.StatusUpdate):
                The status update for the pipeline.

            integration (rbintegrations.gitlabci.integration.
                         GitLabCIIntegration):
                The integration instance.
        """
        build_info = status_update.extra_data.get('gitlab_ci_builds', {})
        pipeline_info = status_update.extra_data.get('gitlab_ci_pipelines', {})
        project_url = payload.project.web_url
        object_attributes = payload.object_attributes

        if object_attributes.source == 'parent_pipeline':
            # This event is from a child pipeline.
            pipeline_id = str(object_attributes.id)

            pipeline_info[pipeline_id] = {
                'stages': object_attributes.stages,
                'status': object_attributes.status,
                'url': object_attributes.url,
            }

        for build in payload.builds:
            job_id = str(build.id)

            build_info[job_id] = {
                'name': build.name,
                'stage': build.stage,
                'status': build.status,
                'url': f'{project_url}/-/jobs/{job_id}',
            }

        status_update.extra_data['gitlab_ci_builds'] = build_info
        status_update.extra_data['gitlab_ci_pipelines'] = pipeline_info

        job_status = self._make_status_text(pipeline_info, build_info)

        if status_update.review:
            review = status_update.review

            try:
                comment = review.general_comments.all()[0]
                comment.text = job_status
                comment.save(update_fields=['text'])
            except ObjectDoesNotExist:
                logger.error(
                    'Unable to get general comment for GitLab CI job '
                    'summary review pk=%s',
                    review.pk)
        else:
            # Ideally we'd publish a review with the job summary as the
            # body_top, but the _status_update_review_section.html template in
            # Review Board only includes review content if they have any
            # comments. We therefore stick the job summary into a general
            # comment.
            review = Review.objects.create(
                review_request=status_update.review_request,
                user=integration.get_or_create_user(),
                public=False,
            )
            comment = GeneralComment.objects.create(
                text=job_status,
                rich_text=True,
            )
            review.general_comments.add(comment)
            review.publish()

            status_update.review = review
            status_update.save(update_fields=['review'])

    def _make_status_text(
        self,
        pipeline_info: Mapping[str, Mapping[str, Any]],
        build_info: Mapping[str, Mapping[str, Any]],
    ) -> str:
        """Return the text to use for build status in the review.

        Args:
            pipeline_info (dict):
                The stored child pipeline info.

            build_info (dict):
                The stored build info.

        Returns:
            str:
            Text for the build status.
        """
        status_lines: list[str] = []

        if pipeline_info:
            status_lines.append('# Child pipelines:')

            # Keys are stored as strings but we want to sort them numerically.
            for pipeline_id in sorted(pipeline_info.keys(), key=int):
                info = pipeline_info[pipeline_id]
                status = info['status']
                url = info['url']

                try:
                    description = self.PIPELINE_STATUS_DESCRIPTION_MAP[status]
                except KeyError:
                    logger.error('gitlab-ci webhook: Unknown job status '
                                 'value %s for pipeline %s',
                                 status, pipeline_id)
                    description = 'unknown'

                status_lines.append(
                    f'[{pipeline_id}]({url}): {description}'
                )

        status_lines.append('# Job summary:')

        # Keys are stored as strings but we want to sort them numerically.
        for build_id in sorted(build_info.keys(), key=int):
            info = build_info[build_id]
            url = info['url']
            name = info['name']
            status = info['status']

            try:
                description = self.JOB_STATUS_DESCRIPTION_MAP[status]
            except KeyError:
                logger.error('gitlab-ci webhook: Unknown job status value %s '
                             'for job %s',
                             status, build_id)
                description = 'unknown'

            status_lines.append(
                f'[{name}]({url}): {description}'
            )

        return '\n'.join(status_lines)
