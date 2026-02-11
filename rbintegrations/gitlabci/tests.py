"""Unit tests for the GitLab CI integration.

Version Added:
    5.0
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

import gitlab
import kgb
from django.urls import reverse
from djblets.conditions import ConditionSet, Condition
from gitlab.v4.objects import (
    Project,
    ProjectManager,
    ProjectPipeline,
    ProjectPipelineManager,
)
from reviewboard.integrations.models import IntegrationConfig
from reviewboard.reviews.conditions import ReviewRequestRepositoriesChoice
from reviewboard.reviews.models import StatusUpdate
from reviewboard.reviews.signals import status_update_request_run

from rbintegrations.gitlabci.forms import GitLabCIIntegrationConfigForm
from rbintegrations.gitlabci.integration import GitLabCIIntegration
from rbintegrations.testing.testcases import IntegrationTestCase

if TYPE_CHECKING:
    from typing import Any

    from reviewboard.reviews.models import ReviewRequest


class BaseGitLabCITestCase(IntegrationTestCase[GitLabCIIntegration]):
    """Base class for GitLab CI tests.

    Version Added:
        5.0
    """

    integration_cls = GitLabCIIntegration
    fixtures = ['test_scmtools', 'test_site', 'test_users']

    def _create_config(
        self,
        *,
        self_hosted: bool = False,
        with_local_site: bool = False,
        run_manually: bool = False,
        use_trigger_token: bool = False,
        gitlab_name: (str | None) = None,
        gitlab_ref: (str | None) = None,
        gitlab_vars: (str | None) = None,
        gitlab_inputs: (str | None) = None,
        gitlab_webhook_secret_token: (str | None) = None,
    ) -> IntegrationConfig:
        """Create an integration config.

        Args:
            self_hosted (bool, optional):
                Whether to test with a self-hosted GitLab URL.

            with_local_site (bool, optional):
                Whether to test with a local site.

            run_manually (bool, optional):
                Whether to set up the integration configuration to run
                only when manually triggered.

            use_trigger_token (bool, optional):
                Whether to use trigger token instead of private token.

            gitlab_name (str, optional):
                Custom GitLab project name.

            gitlab_ref (str, optional):
                Custom GitLab ref.

            gitlab_vars (str, optional):
                Custom GitLab variables as JSON string.

            gitlab_inputs (str, optional):
                Custom GitLab inputs as JSON string.

            gitlab_webhook_secret_token (str, optional):
                Secret token for webhook validation.

        Returns:
            reviewboard.integrations.models.IntegrationConfig:
            The new integration configuration.
        """
        choice = ReviewRequestRepositoriesChoice()
        condition_set = ConditionSet(conditions=[
            Condition(choice=choice,
                      operator=choice.get_operator('any')),
        ])

        if with_local_site:
            self.local_site = self.get_local_site(name=self.local_site_name)
        else:
            self.local_site = None

        config = self.integration.create_config(
            name='Config 1',
            enabled=True,
            local_site=self.local_site,
            save=False,
        )
        config.set('conditions', condition_set.serialize())
        config.set('run_manually', run_manually)

        if self_hosted:
            config.set('gitlab_endpoint', 'https://gitlab.example.com')
        else:
            config.set('gitlab_endpoint', 'https://gitlab.com')

        if use_trigger_token:
            config.set('gitlab_token_type', 'trigger_token')
            config.set('gitlab_token', 'test-trigger-token')
        else:
            config.set('gitlab_token_type', 'private_token')
            config.set('gitlab_token', 'test-private-token')

        config.set('gitlab_name', gitlab_name or '{repository_name}')
        config.set('gitlab_ref', gitlab_ref or '{branch}')
        config.set('gitlab_vars', gitlab_vars or '{}')
        config.set('gitlab_inputs', gitlab_inputs or '{}')
        config.set('gitlab_report_job_state', False)

        if gitlab_webhook_secret_token:
            config.set('gitlab_webhook_secret_token',
                       gitlab_webhook_secret_token)

        config.save()

        return cast(IntegrationConfig, config)


class GitLabCIIntegrationTests(BaseGitLabCITestCase):
    """Unit tests for GitLab CI.

    Version Added:
        5.0
    """

    def test_build_new_review_request(self) -> None:
        """Testing GitLabCIIntegration builds a new review request"""
        review_request = self._setup_build_test()

        @self.spy_for(ProjectManager.get, owner=ProjectManager)
        def _get_project(
            self: ProjectManager,
            id: str,
            lazy: bool = False,
            **kwargs,
        ) -> Project:
            return Project(self, {})

        @self.spy_for(ProjectPipelineManager.create,
                      owner=ProjectPipelineManager)
        def _create_pipeline(
            self: ProjectPipelineManager,
            data: (dict[str, Any] | None) = None,
            **kwargs,
        ) -> ProjectPipeline:
            return ProjectPipeline(self, {})

        self.spy_on(gitlab.Gitlab.auth,
                    owner=gitlab.Gitlab,
                    call_original=False)

        review_request.publish(review_request.submitter)

        api_token = self.integration.get_or_create_api_token(
            user=self.integration.get_or_create_user(),
            local_site=self.local_site)

        self.assertSpyCalledWith(
            ProjectPipelineManager.create,
            data={
                'inputs': {},
                'ref': 'my-branch',
                'variables': [
                    {
                        'key': 'REVIEWBOARD_API_TOKEN',
                        'value': api_token.token,
                    },
                    {
                        'key': 'REVIEWBOARD_DIFF_REVISION',
                        'value': 1,
                    },
                    {
                        'key': 'REVIEWBOARD_GITLAB_INTEGRATION_CONFIG_ID',
                        'value': self.config.pk,
                    },
                    {
                        'key': 'REVIEWBOARD_PIPELINE_NAME',
                        'value': 'Review Request #1: Test Summary',
                    },
                    {
                        'key': 'REVIEWBOARD_REVIEW_REQUEST',
                        'value': review_request.display_id,
                    },
                    {
                        'key': 'REVIEWBOARD_SERVER',
                        'value': 'http://example.com/',
                    },
                    {
                        'key': 'REVIEWBOARD_STATUS_UPDATE_ID',
                        'value': 1,
                    },
                ],
            })

    def test_build_new_review_request_with_trigger_token(self) -> None:
        """Testing GitLabCIIntegration builds a new review request with
        trigger token
        """
        review_request = self._setup_build_test(use_trigger_token=True)

        @self.spy_for(ProjectManager.get, owner=ProjectManager)
        def _get_project(
            self: ProjectManager,
            id: str,
            lazy: bool = False,
            **kwargs,
        ) -> Project:
            return Project(self, {})

        @self.spy_for(Project.trigger_pipeline, owner=Project)
        def _trigger_pipeline(
            self: Project,
            *args,
            **kwargs,
        ) -> ProjectPipeline:
            return ProjectPipeline(self, {})

        review_request.publish(review_request.submitter)

        api_token = self.integration.get_or_create_api_token(
            user=self.integration.get_or_create_user(),
            local_site=self.local_site)

        self.assertSpyCalledWith(
            Project.trigger_pipeline,
            'my-branch',
            'test-trigger-token',
            inputs={},
            variables={
                'REVIEWBOARD_API_TOKEN': api_token.token,
                'REVIEWBOARD_DIFF_REVISION': 1,
                'REVIEWBOARD_GITLAB_INTEGRATION_CONFIG_ID': self.config.pk,
                'REVIEWBOARD_PIPELINE_NAME': 'Review Request #1: Test Summary',
                'REVIEWBOARD_REVIEW_REQUEST': review_request.display_id,
                'REVIEWBOARD_SERVER': 'http://example.com/',
                'REVIEWBOARD_STATUS_UPDATE_ID': 1,
            })

    def test_build_new_review_request_with_local_site(self) -> None:
        """Testing GitLabCIIntegration builds a new review request with a
        local site
        """
        review_request = self._setup_build_test(with_local_site=True)

        @self.spy_for(ProjectManager.get, owner=ProjectManager)
        def _get_project(
            self: ProjectManager,
            id: str,
            lazy: bool = False,
            **kwargs,
        ) -> Project:
            return Project(self, {'id': 1})

        @self.spy_for(ProjectPipelineManager.create,
                      owner=ProjectPipelineManager)
        def _create_pipeline(
            self: ProjectPipelineManager,
            data: dict[str, Any] | None = None,
            **kwargs,
        ) -> ProjectPipeline:
            return ProjectPipeline(self, {'id': 1})

        self.spy_on(gitlab.Gitlab.auth,
                    owner=gitlab.Gitlab,
                    call_original=False)

        review_request.publish(review_request.submitter)

        api_token = self.integration.get_or_create_api_token(
            user=self.integration.get_or_create_user(),
            local_site=self.local_site)

        self.assertSpyCalledWith(
            ProjectPipelineManager.create,
            data={
                'inputs': {},
                'ref': 'my-branch',
                'variables': [
                    {
                        'key': 'REVIEWBOARD_API_TOKEN',
                        'value': api_token.token,
                    },
                    {
                        'key': 'REVIEWBOARD_DIFF_REVISION',
                        'value': 1,
                    },
                    {
                        'key': 'REVIEWBOARD_GITLAB_INTEGRATION_CONFIG_ID',
                        'value': self.config.pk,
                    },
                    {
                        'key': 'REVIEWBOARD_PIPELINE_NAME',
                        'value': (
                            f'Review Request #{review_request.display_id}: '
                            f'Test Summary'
                        ),
                    },
                    {
                        'key': 'REVIEWBOARD_REVIEW_REQUEST',
                        'value': review_request.display_id,
                    },
                    {
                        'key': 'REVIEWBOARD_SERVER',
                        'value': (
                            f'http://example.com/s/{self.local_site_name}/'
                        ),
                    },
                    {
                        'key': 'REVIEWBOARD_STATUS_UPDATE_ID',
                        'value': 1,
                    },
                ],
            })

    def test_manual_run_no_build_on_publish(self) -> None:
        """Testing GitLabCIIntegration with manual trigger does not
        build on publish
        """
        review_request = self._setup_build_test(run_manually=True)

        @self.spy_for(ProjectManager.get, owner=ProjectManager)
        def _get_project(
            self: ProjectManager,
            id: str,
            lazy: bool = False,
            **kwargs,
        ) -> Project:
            return Project(self, {})

        @self.spy_for(ProjectPipelineManager.create,
                      owner=ProjectPipelineManager)
        def _create_pipeline(
            self: ProjectPipelineManager,
            data: dict[str, Any] | None = None,
            **kwargs,
        ) -> ProjectPipeline:
            return ProjectPipeline(self, {})

        @self.spy_for(Project.trigger_pipeline, owner=Project)
        def _trigger_pipeline(
            self: Project,
            *args,
            **kwargs,
        ) -> ProjectPipeline:
            return ProjectPipeline(self, {})

        review_request.publish(review_request.submitter)

        self.assertSpyNotCalled(ProjectPipelineManager.create)
        self.assertSpyNotCalled(Project.trigger_pipeline)

    def test_build_manual_run(self) -> None:
        """Testing GitLabCIIntegration build via a manual trigger"""
        review_request = self._setup_build_test(run_manually=True)

        @self.spy_for(ProjectManager.get, owner=ProjectManager)
        def _get_project(
            self: ProjectManager,
            id: str,
            lazy: bool = False,
            **kwargs,
        ) -> Project:
            return Project(self, {})

        @self.spy_for(ProjectPipelineManager.create,
                      owner=ProjectPipelineManager)
        def _create_pipeline(
            self: ProjectPipelineManager,
            data: dict[str, Any] | None = None,
            **kwargs,
        ) -> ProjectPipeline:
            return ProjectPipeline(self, {})

        self.spy_on(gitlab.Gitlab.auth,
                    owner=gitlab.Gitlab,
                    call_original=False)

        status_update = self.create_status_update(
            service_id='gitlab-ci',
            review_request=review_request)

        status_update_request_run.send(
            sender=self.__class__,
            status_update=status_update)

        self.assertSpyCalled(ProjectPipelineManager.create)

    def test_variable_replacement(self) -> None:
        """Testing GitLabCIIntegration variable replacement in project name
        and ref
        """
        review_request = self._setup_build_test(
            gitlab_name='{repository_name}-ci',
            gitlab_ref='{branch}',
            repository_name='Test Repo')

        @self.spy_for(ProjectManager.get, owner=ProjectManager)
        def _get_project(
            self: ProjectManager,
            id: str,
            lazy: bool = False,
            **kwargs,
        ) -> Project:
            return Project(self, {})

        @self.spy_for(ProjectPipelineManager.create,
                      owner=ProjectPipelineManager)
        def _create_pipeline(
            self: ProjectPipelineManager,
            data: dict[str, Any] | None = None,
            **kwargs,
        ) -> ProjectPipeline:
            return ProjectPipeline(self, {})

        self.spy_on(gitlab.Gitlab.auth,
                    owner=gitlab.Gitlab,
                    call_original=False)

        review_request.publish(review_request.submitter)

        self.assertSpyCalledWith(ProjectManager.get, 'Test Repo-ci')

    def test_variable_replacement_in_json_fields(self) -> None:
        """Testing GitLabCIIntegration variable replacement in JSON fields"""
        review_request = self._setup_build_test(
            gitlab_vars='{"REPO": "{repository_name}", "BR": "{branch}"}',
            gitlab_inputs='{"input1": "{repository_name}"}')

        @self.spy_for(ProjectManager.get, owner=ProjectManager)
        def _get_project(
            self: ProjectManager,
            id: str,
            lazy: bool = False,
            **kwargs,
        ) -> Project:
            return Project(self, {})

        @self.spy_for(ProjectPipelineManager.create,
                      owner=ProjectPipelineManager)
        def _create_pipeline(
            self: ProjectPipelineManager,
            data: dict[str, Any] | None = None,
            **kwargs,
        ) -> ProjectPipeline:
            return ProjectPipeline(self, {})

        self.spy_on(gitlab.Gitlab.auth,
                    owner=gitlab.Gitlab,
                    call_original=False)

        review_request.publish(review_request.submitter)

        api_token = self.integration.get_or_create_api_token(
            user=self.integration.get_or_create_user(),
            local_site=self.local_site)

        self.assertSpyCalledWith(
            ProjectPipelineManager.create,
            data={
                'inputs': {
                    'input1': 'Test Repo',
                },
                'ref': 'my-branch',
                'variables': [
                    {
                        'key': 'REVIEWBOARD_API_TOKEN',
                        'value': api_token.token,
                    },
                    {
                        'key': 'REVIEWBOARD_DIFF_REVISION',
                        'value': 1,
                    },
                    {
                        'key': 'REVIEWBOARD_GITLAB_INTEGRATION_CONFIG_ID',
                        'value': self.config.pk,
                    },
                    {
                        'key': 'REVIEWBOARD_PIPELINE_NAME',
                        'value': 'Review Request #1: Test Summary',
                    },
                    {
                        'key': 'REVIEWBOARD_REVIEW_REQUEST',
                        'value': review_request.display_id,
                    },
                    {
                        'key': 'REVIEWBOARD_SERVER',
                        'value': 'http://example.com/',
                    },
                    {
                        'key': 'REVIEWBOARD_STATUS_UPDATE_ID',
                        'value': 1,
                    },
                    {
                        'key': 'REPO',
                        'value': 'Test Repo',
                    },
                    {
                        'key': 'BR',
                        'value': 'my-branch',
                    },
                ],
            })

    def _setup_build_test(
        self,
        *,
        with_local_site: bool = False,
        run_manually: bool = False,
        use_trigger_token: bool = False,
        gitlab_name: str | None = None,
        gitlab_ref: str | None = None,
        gitlab_vars: str | None = None,
        gitlab_inputs: str | None = None,
        repository_name: str = 'Test Repo',
    ) -> ReviewRequest:
        """Set up a basic build test.

        Args:
            with_local_site (bool, optional):
                Whether to create with a local site.

            run_manually (bool, optional):
                Whether to configure manual runs.

            use_trigger_token (bool, optional):
                Whether to use trigger token.

            gitlab_name (str, optional):
                Custom GitLab project name.

            gitlab_ref (str, optional):
                Custom GitLab ref.

            gitlab_vars (str, optional):
                Custom GitLab variables as JSON string.

            gitlab_inputs (str, optional):
                Custom GitLab inputs as JSON string.

            repository_name (str, optional):
                Name for the repository.

        Returns:
            reviewboard.reviews.models.ReviewRequest:
            The created review request.
        """
        repository = self.create_repository(
            name=repository_name,
            with_local_site=with_local_site)
        review_request = self.create_review_request(
            repository=repository,
            with_local_site=with_local_site,
            branch='my-branch')
        diffset = self.create_diffset(
            review_request=review_request,
            base_commit_id='8fd69d70f07b57c21ad8733c1c04ae604d21493f')
        diffset.save()

        self.config = self._create_config(
            with_local_site=with_local_site,
            run_manually=run_manually,
            use_trigger_token=use_trigger_token,
            gitlab_name=gitlab_name,
            gitlab_ref=gitlab_ref,
            gitlab_vars=gitlab_vars,
            gitlab_inputs=gitlab_inputs)
        self.integration.enable_integration()

        return review_request


class GitLabCIIntegrationConfigFormTests(BaseGitLabCITestCase):
    """Unit tests for GitLabCIIntegrationConfigForm.

    Version Added:
        5.0
    """

    def test_gitlabci_config_form_valid(self) -> None:
        """Testing GitLabCIIntegrationConfigForm validation success"""
        form = GitLabCIIntegrationConfigForm(
            integration=self.integration,
            request=None,
            data={
                'conditions_last_id': 0,
                'conditions_mode': 'always',
                'name': 'test',
                'gitlab_endpoint': 'https://gitlab.com',
                'gitlab_token_type': 'private_token',
                'gitlab_token': 'test-token',
                'gitlab_name': 'project-name',
                'gitlab_ref': 'main',
                'gitlab_inputs': '{}',
                'gitlab_vars': '{}',
            })

        self.spy_on(gitlab.Gitlab.auth,
                    owner=gitlab.Gitlab,
                    call_original=False)
        self.assertTrue(form.is_valid())

    def test_gitlabci_config_form_json_failure(self) -> None:
        """Testing GitLabCIIntegrationConfigForm validation failure with a JSON
        parse error
        """
        form = GitLabCIIntegrationConfigForm(
            integration=self.integration,
            request=None,
            data={
                'conditions_last_id': 0,
                'conditions_mode': 'always',
                'name': 'test',
                'gitlab_endpoint': 'https://gitlab.com',
                'gitlab_token_type': 'private_token',
                'gitlab_token': 'test-token',
                'gitlab_name': 'project-name',
                'gitlab_ref': 'main',
                'gitlab_inputs': 'invalid json',
                'gitlab_vars': '{}',
            })

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors['gitlab_inputs'],
            [
                'Unable to parse JSON: Expecting value: line 1 column 1 '
                '(char 0)',
            ])

    def test_gitlabci_config_form_auth_failure(self) -> None:
        """Testing GitLabCIIntegrationConfigForm validation failure with
        authentication failure
        """
        form = GitLabCIIntegrationConfigForm(
            integration=self.integration,
            request=None,
            data={
                'conditions_last_id': 0,
                'conditions_mode': 'always',
                'name': 'test',
                'gitlab_endpoint': 'https://gitlab.com',
                'gitlab_token_type': 'private_token',
                'gitlab_token': 'bad-token',
                'gitlab_name': 'project-name',
                'gitlab_ref': 'main',
                'gitlab_inputs': '{}',
                'gitlab_vars': '{}',
            })

        self.spy_on(
            gitlab.Gitlab.auth,
            owner=gitlab.Gitlab,
            op=kgb.SpyOpRaise(
                gitlab.GitlabAuthenticationError('Authentication failed.')
            ))
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['gitlab_endpoint'],
                         ['Authentication failed.'])


class GitLabCIWebHookTests(BaseGitLabCITestCase):
    """Unit tests for the GitLab CI webhook handler.

    Version Added:
        5.0
    """

    def setUp(self) -> None:
        """Set up the test case."""
        super().setUp()

        self.repository = self.create_repository()
        self.review_request = self.create_review_request(
            repository=self.repository,
            public=True)

        self.status_update = self.create_status_update(self.review_request)

        self.config = self._create_config()
        self.integration.enable_integration()

        self.webhook_url = reverse('gitlab-ci-webhook')

    def test_webhook_bad_json(self) -> None:
        """Testing GitLabCIWebHookView with invalid JSON"""
        response = self.client.post(
            self.webhook_url,
            data='invalid json',
            content_type='application/json')

        self.assertEqual(response.status_code, 400)

    def test_webhook_missing_object_kind(self) -> None:
        """Testing GitLabCIWebHookView with missing object_kind"""
        payload = json.dumps({})
        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type='application/json')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content, b'Missing pipeline event')

    def test_webhook_wrong_object_kind(self) -> None:
        """Testing GitLabCIWebHookView with wrong object_kind"""
        payload = json.dumps({'object_kind': 'build'})
        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type='application/json')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content, b'Missing pipeline event')

    def test_webhook_missing_variables(self) -> None:
        """Testing GitLabCIWebHookView with missing variables"""
        payload = json.dumps({
            'object_kind': 'pipeline',
            'builds': [],
            'object_attributes': {
                'id': 123,
                'source': 'api',
                'status': 'success',
                'url': 'https://gitlab.example.com/pipeline/123',
                'variables': None,
            },
            'project': {
                'web_url': 'https://gitlab.example.com/project',
            },
        })
        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type='application/json')

        self.assertEqual(response.status_code, 202)

    def test_webhook_missing_required_variables(self) -> None:
        """Testing GitLabCIWebHookView with missing required variables"""
        payload = json.dumps({
            'object_kind': 'pipeline',
            'builds': [],
            'object_attributes': {
                'id': 123,
                'source': 'api',
                'status': 'success',
                'url': 'https://gitlab.example.com/pipeline/123',
                'variables': [
                    {'key': 'OTHER_VAR', 'value': 'value'},
                ],
            },
            'project': {
                'web_url': 'https://gitlab.example.com/project',
            },
        })
        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type='application/json')

        self.assertEqual(response.status_code, 202)

    def test_webhook_invalid_config_id(self) -> None:
        """Testing GitLabCIWebHookView with invalid config ID"""
        payload = json.dumps({
            'object_kind': 'pipeline',
            'builds': [],
            'object_attributes': {
                'id': 123,
                'source': 'api',
                'status': 'success',
                'url': 'https://gitlab.example.com/pipeline/123',
                'variables': [
                    {
                        'key': 'REVIEWBOARD_REVIEW_REQUEST',
                        'value': str(self.review_request.display_id),
                    },
                    {
                        'key': 'REVIEWBOARD_STATUS_UPDATE_ID',
                        'value': str(self.status_update.pk),
                    },
                    {
                        'key': 'REVIEWBOARD_GITLAB_INTEGRATION_CONFIG_ID',
                        'value': '99999',
                    },
                ],
            },
            'project': {
                'web_url': 'https://gitlab.example.com/project',
            },
        })
        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type='application/json')

        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Unable to find integration config', response.content)

    def test_webhook_wrong_secret_token(self) -> None:
        """Testing GitLabCIWebHookView with wrong secret token"""
        self.config.set('gitlab_webhook_secret_token', 'correct-secret')
        self.config.save()

        payload = json.dumps({
            'object_kind': 'pipeline',
            'builds': [],
            'object_attributes': {
                'id': 123,
                'source': 'api',
                'status': 'success',
                'url': 'https://gitlab.example.com/pipeline/123',
                'variables': [
                    {
                        'key': 'REVIEWBOARD_REVIEW_REQUEST',
                        'value': str(self.review_request.display_id),
                    },
                    {
                        'key': 'REVIEWBOARD_STATUS_UPDATE_ID',
                        'value': str(self.status_update.pk),
                    },
                    {
                        'key': 'REVIEWBOARD_GITLAB_INTEGRATION_CONFIG_ID',
                        'value': str(self.config.pk),
                    },
                ],
            },
            'project': {
                'web_url': 'https://gitlab.example.com/project',
            },
        })
        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type='application/json',
            HTTP_X_GITLAB_TOKEN='wrong-secret')

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.content,
                         b'WebHook secret token does not match')

    def test_webhook_invalid_status_update_id(self) -> None:
        """Testing GitLabCIWebHookView with invalid status update ID"""
        payload = json.dumps({
            'object_kind': 'pipeline',
            'builds': [],
            'object_attributes': {
                'id': 123,
                'source': 'api',
                'status': 'success',
                'url': 'https://gitlab.example.com/pipeline/123',
                'variables': [
                    {
                        'key': 'REVIEWBOARD_REVIEW_REQUEST',
                        'value': str(self.review_request.display_id),
                    },
                    {
                        'key': 'REVIEWBOARD_STATUS_UPDATE_ID',
                        'value': '99999',
                    },
                    {
                        'key': 'REVIEWBOARD_GITLAB_INTEGRATION_CONFIG_ID',
                        'value': str(self.config.pk),
                    },
                ],
            },
            'project': {
                'web_url': 'https://gitlab.example.com/project',
            },
        })
        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type='application/json')

        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Unable to find matching status update',
                      response.content)

    def test_webhook_pipeline_success(self) -> None:
        """Testing GitLabCIWebHookView with successful pipeline"""
        payload = json.dumps({
            'object_kind': 'pipeline',
            'builds': [
                {
                    'id': 123,
                    'name': 'test-job',
                    'status': 'success',
                },
            ],
            'object_attributes': {
                'id': 123,
                'source': 'api',
                'status': 'success',
                'url': 'https://gitlab.example.com/pipeline/123',
                'variables': [
                    {
                        'key': 'REVIEWBOARD_REVIEW_REQUEST',
                        'value': str(self.review_request.display_id),
                    },
                    {
                        'key': 'REVIEWBOARD_STATUS_UPDATE_ID',
                        'value': str(self.status_update.pk),
                    },
                    {
                        'key': 'REVIEWBOARD_GITLAB_INTEGRATION_CONFIG_ID',
                        'value': str(self.config.pk),
                    },
                ],
            },
            'project': {
                'web_url': 'https://gitlab.example.com/project',
            },
        })
        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type='application/json')

        self.assertEqual(response.status_code, 200)

        status_update = StatusUpdate.objects.get(pk=self.status_update.pk)
        self.assertEqual(status_update.state, StatusUpdate.DONE_SUCCESS)
        self.assertEqual(status_update.url,
                         'https://gitlab.example.com/pipeline/123')

    def test_webhook_pipeline_failure(self) -> None:
        """Testing GitLabCIWebHookView with failed pipeline"""
        payload = json.dumps({
            'object_kind': 'pipeline',
            'builds': [],
            'object_attributes': {
                'id': 123,
                'source': 'api',
                'status': 'failed',
                'url': 'https://gitlab.example.com/pipeline/123',
                'variables': [
                    {
                        'key': 'REVIEWBOARD_REVIEW_REQUEST',
                        'value': str(self.review_request.display_id),
                    },
                    {
                        'key': 'REVIEWBOARD_STATUS_UPDATE_ID',
                        'value': str(self.status_update.pk),
                    },
                    {
                        'key': 'REVIEWBOARD_GITLAB_INTEGRATION_CONFIG_ID',
                        'value': str(self.config.pk),
                    },
                ],
            },
            'project': {
                'web_url': 'https://gitlab.example.com/project',
            },
        })
        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type='application/json')

        self.assertEqual(response.status_code, 200)

        status_update = StatusUpdate.objects.get(pk=self.status_update.pk)
        self.assertEqual(status_update.state, StatusUpdate.DONE_FAILURE)

    def test_webhook_pipeline_running(self) -> None:
        """Testing GitLabCIWebHookView with running pipeline"""
        payload = json.dumps({
            'object_kind': 'pipeline',
            'builds': [],
            'object_attributes': {
                'id': 123,
                'source': 'api',
                'status': 'running',
                'url': 'https://gitlab.example.com/pipeline/123',
                'variables': [
                    {
                        'key': 'REVIEWBOARD_REVIEW_REQUEST',
                        'value': str(self.review_request.display_id),
                    },
                    {
                        'key': 'REVIEWBOARD_STATUS_UPDATE_ID',
                        'value': str(self.status_update.pk),
                    },
                    {
                        'key': 'REVIEWBOARD_GITLAB_INTEGRATION_CONFIG_ID',
                        'value': str(self.config.pk),
                    },
                ],
            },
            'project': {
                'web_url': 'https://gitlab.example.com/project',
            },
        })
        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type='application/json')

        self.assertEqual(response.status_code, 200)

        status_update = StatusUpdate.objects.get(pk=self.status_update.pk)
        self.assertEqual(status_update.state, StatusUpdate.PENDING)

    def test_webhook_with_job_reporting(self) -> None:
        """Testing GitLabCIWebHookView with job state reporting enabled"""
        self.config.set('gitlab_report_job_state', True)
        self.config.save()

        payload = json.dumps({
            'object_kind': 'pipeline',
            'builds': [
                {
                    'id': 123,
                    'name': 'test-job-1',
                    'status': 'success',
                },
                {
                    'id': 124,
                    'name': 'test-job-2',
                    'status': 'failed',
                },
            ],
            'object_attributes': {
                'id': 123,
                'source': 'api',
                'status': 'failed',
                'url': 'https://gitlab.example.com/pipeline/123',
                'variables': [
                    {
                        'key': 'REVIEWBOARD_REVIEW_REQUEST',
                        'value': str(self.review_request.display_id),
                    },
                    {
                        'key': 'REVIEWBOARD_STATUS_UPDATE_ID',
                        'value': str(self.status_update.pk),
                    },
                    {
                        'key': 'REVIEWBOARD_GITLAB_INTEGRATION_CONFIG_ID',
                        'value': str(self.config.pk),
                    },
                ],
            },
            'project': {
                'web_url': 'https://gitlab.example.com/project',
            },
        })
        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type='application/json')

        self.assertEqual(response.status_code, 200)

        status_update = StatusUpdate.objects.get(pk=self.status_update.pk)
        self.assertEqual(
            status_update.extra_data.get('gitlab_ci_builds', {}),
            {
                '123': {
                    'name': 'test-job-1',
                    'status': 'success',
                    'url': 'https://gitlab.example.com/project/-/jobs/123',
                },
                '124': {
                    'name': 'test-job-2',
                    'status': 'failed',
                    'url': 'https://gitlab.example.com/project/-/jobs/124',
                },
            })

    def test_webhook_child_pipeline(self) -> None:
        """Testing GitLabCIWebHookView with child pipeline event"""
        self.config.set('gitlab_report_job_state', True)
        self.config.save()

        payload = json.dumps({
            'object_kind': 'pipeline',
            'builds': [
                {
                    'id': 125,
                    'name': 'child-job',
                    'status': 'success',
                },
            ],
            'object_attributes': {
                'id': 124,
                'source': 'parent_pipeline',
                'status': 'success',
                'url': 'https://gitlab.example.com/pipeline/124',
                'variables': [
                    {
                        'key': 'REVIEWBOARD_REVIEW_REQUEST',
                        'value': str(self.review_request.display_id),
                    },
                    {
                        'key': 'REVIEWBOARD_STATUS_UPDATE_ID',
                        'value': str(self.status_update.pk),
                    },
                    {
                        'key': 'REVIEWBOARD_GITLAB_INTEGRATION_CONFIG_ID',
                        'value': str(self.config.pk),
                    },
                ],
            },
            'project': {
                'web_url': 'https://gitlab.example.com/project',
            },
        })
        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type='application/json')

        self.assertEqual(response.status_code, 200)

        status_update = StatusUpdate.objects.get(pk=self.status_update.pk)
        gitlab_ci_builds = status_update.extra_data.get('gitlab_ci_builds', {})
        self.assertIn('125', gitlab_ci_builds)
